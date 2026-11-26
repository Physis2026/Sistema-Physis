#!/usr/bin/env python3
"""Gera os kits de revisão por módulo: cada responsável recebe só os arquivos do seu módulo.

    python ferramentas/gerar_kits_revisao.py --saida <pasta> [--modulo id] [--data AAAA-MM-DD]
                                             [--documentos <pasta dos documentos 17 e 18>] [--sem-zip]

Para cada módulo de ferramentas/kits/modulos.json cria a pasta (e o ZIP) "kit-<id>-<data>" com:
  LEIA-ME.md         o que revisar, como mudar sem estragar, como ver o resultado e como devolver
  FICHA_REVISAO.md   modelo para o revisor contar o que mudou, por quê e com qual fonte
  MANIFESTO.json     SHA-256 de cada arquivo no momento da geração e o commit do repositório
  editaveis/         cópias do que o revisor pode mudar (arquivo inteiro ou só a parte do módulo)
  referencia/        cópias para ler (código, documentos, testes, páginas de conferência); não mudar
Também guarda uma cópia do manifesto em <saida>/_manifestos/<kit>.json: é a que o
ferramentas/validar_devolucao.py usa (o revisor não precisa devolver o manifesto).

Só a biblioteca padrão do Python. Não muda nada no repositório.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MAPA_PADRAO = RAIZ / "ferramentas" / "kits" / "modulos.json"
FORMATO = "physis-kit-revisao/1"
DOCS_PADRAO = Path(os.environ.get("PHYSIS_DOCUMENTOS") or
                   Path.home() / "OneDrive - Physis Engineering" / "Documents" / "Sistema Physis")
DOC17 = "17_Metodologia_e_Normas.md"
DOC18 = "18_Checklist_Implantacao_e_Responsaveis.md"
CHAVES_NOME = ("nome", "grandeza", "descricao", "titulo", "assunto", "cientifico")
ARQ_KIT = "_KIT.json"


# ---------------------------------------------------------------- utilidades comuns (também usadas pelo validador)

def git_exe() -> str:
    achado = shutil.which("git")
    if achado:
        return achado
    for c in (r"C:\Program Files\Git\cmd\git.exe", r"C:\Program Files\Git\bin\git.exe"):
        if Path(c).is_file():
            return c
    return "git"


def git(raiz: Path, *args: str, checar: bool = False) -> subprocess.CompletedProcess:
    r = subprocess.run([git_exe(), *args], cwd=str(raiz), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if checar and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} falhou: {r.stderr.strip() or r.stdout.strip()}")
    return r


def commit_atual(raiz: Path) -> str | None:
    try:
        r = git(raiz, "rev-parse", "HEAD")
    except OSError:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_arquivo(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def sha_canonico(valor) -> str:
    """Hash do conteúdo (não da formatação): mesma informação → mesmo hash."""
    texto = json.dumps(valor, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_bytes(texto.encode("utf-8"))


def ler_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def carregar_mapa(caminho: Path = MAPA_PADRAO) -> dict:
    mapa = ler_json(caminho)
    ids = [m["id"] for m in mapa["modulos"]]
    if len(ids) != len(set(ids)):
        raise SystemExit("modulos.json: id de módulo repetido")
    return mapa


def _seg_registro(seg: str):
    if isinstance(seg, str) and "=" in seg:
        k, v = seg.split("=", 1)
        return k, v
    return None


def pegar(dados, caminho: list):
    """Valor no caminho. Segmento 'id=x' escolhe, numa lista, o registro cujo campo id vale x."""
    atual = dados
    for seg in caminho:
        reg = _seg_registro(seg) if isinstance(atual, list) else None
        if reg:
            k, v = reg
            achados = [x for x in atual if isinstance(x, dict) and str(x.get(k)) == v]
            if len(achados) != 1:
                raise KeyError(f"registro {seg} não encontrado (ou repetido)")
            atual = achados[0]
        elif isinstance(atual, dict):
            if seg not in atual:
                raise KeyError(f"chave {seg!r} não encontrada")
            atual = atual[seg]
        elif isinstance(atual, list) and isinstance(seg, int):
            atual = atual[seg]
        else:
            raise KeyError(f"caminho inválido em {seg!r}")
    return atual


def trocar(dados, caminho: list, valor):
    if not caminho:
        return valor
    pai = pegar(dados, caminho[:-1])
    seg = caminho[-1]
    reg = _seg_registro(seg) if isinstance(pai, list) else None
    if reg:
        k, v = reg
        for i, x in enumerate(pai):
            if isinstance(x, dict) and str(x.get(k)) == v:
                pai[i] = valor
                return dados
        raise KeyError(seg)
    pai[seg] = valor
    return dados


def caminho_texto(caminho: list) -> str:
    return " › ".join(str(s) for s in caminho) if caminho else "(arquivo inteiro)"


TELA_EXT = (".js", ".html")
TELA_PREFIXOS = ("sistema/", "physis-hub/web/", "modulos/")
TROCA_PREFIXOS = ("sistema/", "physis-hub/web/", "modulos/", "physis-hub/docs/", "firmware/")
TROCA_PROIBIDOS = ("sistema/physis-metodologia.js",)
PAINEL_REL = "physis-hub/web/painel.html"
_CACHE_I18N: dict = {}


def pode_trocar_texto(rel: str) -> bool:
    """Arquivo de tela ou de documento onde uma troca literal de texto é aceita (nunca lógica em Python, firmware ou dados)."""
    return (rel.endswith((".js", ".html", ".md")) and rel.startswith(TROCA_PREFIXOS)
            and rel not in TROCA_PROIBIDOS and "/tests/" not in rel)


def arquivos_de_tela(mod: dict) -> list:
    arqs = list(mod.get("referencia", [])) + [c["arquivo"] for c in mod.get("conferir", [])]
    return [r for r in dict.fromkeys(arqs) if r.endswith(TELA_EXT) and r.startswith(TELA_PREFIXOS)
            and r not in TROCA_PROIBIDOS]


def chaves_i18n_em(arquivos: list, chaves: list, raiz: Path) -> set:
    achadas = set()
    for rel in arquivos:
        p = raiz / rel
        if not p.is_file():
            continue
        cache = (str(p), p.stat().st_mtime_ns, len(chaves))
        if cache not in _CACHE_I18N:
            texto = p.read_text(encoding="utf-8", errors="replace")
            _CACHE_I18N[cache] = {k for k in chaves if any(f"{a}{k}{b}" in texto for a, b in
                                                         (('"', '"'), ("'", "'"), ("`", "`"), (">", "<")))}
        achadas |= _CACHE_I18N[cache]
    return achadas


def partes_i18n(ed: dict, mod: dict, mapa: dict | None, raiz: Path) -> list:
    base = ler_json(raiz / ed["arquivo"])
    chaves = list(base.get("I18N", {}))
    if ed["i18n_de"] == "resto":
        outras = set()
        for m in (mapa or {}).get("modulos", []):
            if m["id"] != mod["id"] and any(e.get("i18n_de") == "referencia" for e in m.get("editaveis", [])):
                outras |= chaves_i18n_em(arquivos_de_tela(m), chaves, raiz)
        sel = [k for k in chaves if k not in outras]
        return [["I18N", k] for k in sel] + ([["I18N_RX"]] if "I18N_RX" in base else [])
    sel = chaves_i18n_em(arquivos_de_tela(mod), chaves, raiz)
    return [["I18N", k] for k in chaves if k in sel]


def expandir_partes(ed: dict, raiz: Path, mod: dict | None = None, mapa: dict | None = None) -> list | None:
    """Lista de caminhos editáveis do arquivo; None = arquivo inteiro."""
    partes = [list(p) for p in ed.get("partes") or []]
    if ed.get("i18n_de"):
        partes += partes_i18n(ed, mod or {}, mapa, raiz)
    mod_n, mod_p = ed.get("normas_de"), ed.get("premissas_de")
    if mod_n or mod_p:
        met = ler_json(raiz / "sistema" / "physis-metodologia.json")
        if mod_n:
            calc_n = (met.get("modulos", {}).get(mod_n) or {}).get("calculos", [])
            codigos = sorted({n.get("codigo") for c in calc_n for n in c.get("normas", [])
                              if n.get("codigo") in met.get("normas", {})})
            partes += [["normas", c] for c in codigos]
        if mod_p:
            calc = (met.get("modulos", {}).get(mod_p) or {}).get("calculos", [])
            ids = sorted({p for c in calc for p in c.get("premissas", [])})
            prem = ler_json(raiz / ed["arquivo"]) if ed["arquivo"].endswith("premissas.json") else None
            existentes = {p.get("id") for p in (prem or {}).get("premissas", [])}
            partes += [["premissas", f"id={i}"] for i in ids if i in existentes]
    if ed.get("partes") is None and not (mod_n or mod_p or ed.get("i18n_de")):
        return None
    vistos, unicas = set(), []
    for p in partes:
        t = json.dumps(p, ensure_ascii=False)
        if t not in vistos:
            vistos.add(t)
            unicas.append(p)
    return unicas


def nome_extrato(arquivo: str, mod_id: str) -> str:
    p = Path(arquivo)
    return str(p.with_name(f"{p.stem}__parte-{mod_id}{p.suffix}")).replace("\\", "/")


def rotulo(valor) -> str:
    if isinstance(valor, dict):
        for k in CHAVES_NOME:
            if isinstance(valor.get(k), str) and valor[k]:
                t = valor[k]
                return t if len(t) <= 50 else t[:47] + "…"
    return ""


def pendencias(valor, caminho=None, saida=None):
    """Itens marcados para conferir: verificar=true, a_conferir não vazio, [MARCADOR]/[CONFERIR], situação 'conferir'."""
    caminho = caminho or []
    saida = [] if saida is None else saida
    if isinstance(valor, dict):
        nome = rotulo(valor)
        onde = caminho_texto(caminho) + (f" ({nome})" if nome else "")
        if valor.get("verificar") is True:
            saida.append((onde, "marcado 'verificar'"))
        if isinstance(valor.get("a_conferir"), list) and valor["a_conferir"]:
            saida.append((onde, "a conferir: " + ", ".join(map(str, valor["a_conferir"]))[:120]))
        if valor.get("situacao") == "conferir":
            saida.append((onde, "edição da norma a conferir"))
        for k, v in valor.items():
            if isinstance(v, str) and re.search(r"\[(MARCADOR|CONFERIR)[^\]]*\]", v):
                saida.append((caminho_texto(caminho + [k]), "marcador para preencher"))
            elif isinstance(v, (dict, list)):
                pendencias(v, caminho + [k], saida)
    elif isinstance(valor, list):
        for i, x in enumerate(valor):
            seg = i
            if isinstance(x, dict):
                for k in ("id", "n", "codigo"):
                    if k in x:
                        seg = f"{k}={x[k]}"
                        break
            pendencias(x, caminho + [seg], saida)
    return saida


# ---------------------------------------------------------------- textos do kit

def secao_doc(doc: Path, titulo: str | None) -> str:
    if not titulo or not doc.is_file():
        return ""
    linhas = doc.read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(linhas):
        if ln.strip() == f"### {titulo}":
            fim = i + 1
            while fim < len(linhas) and not linhas[fim].startswith(("### ", "## ")):
                fim += 1
            return "\n".join(linhas[i + 1:fim]).strip()
    return ""


def linha_doc18(doc: Path, nome: str) -> str:
    if not doc.is_file():
        return ""
    for ln in doc.read_text(encoding="utf-8").splitlines():
        cel = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cel) >= 3 and cel[0].replace("*", "") == nome:
            return cel[-1]
    return ""


def tabela_md(cab: list, linhas: list) -> str:
    def c(x):
        return str(x).replace("|", "/").replace("\n", " ")
    out = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    out += ["| " + " | ".join(c(x) for x in ln) + " |" for ln in linhas]
    return "\n".join(out)


REGRAS_EDICAO = """\
1. **Mude só valores.** Não apague, não renomeie e não troque de lugar nenhuma chave (o nome antes dos dois-pontos) nem nenhum `id`. Se um item não serve mais, escreva isso na ficha: quem apaga é o Eric, no sistema.
2. **Mantenha o tipo.** Número continua número (`0.8`, com ponto, sem aspas), texto continua texto (entre aspas), lista continua lista (`[ ]`). Um valor vazio (`null`) ou um `[MARCADOR]` pode virar o número conferido.
3. **Pode acrescentar registros** numa lista de registros (por exemplo, uma planta nova ou um equipamento novo), copiando um registro parecido e trocando o `id` por um que ainda não existe. Todos os campos do modelo têm de estar lá.
4. **Marque o que conferiu.** No item que tinha `"verificar": true`, troque para `false` e acrescente, no mesmo item:
   `"conferido": {"por": "Seu Nome", "em": "AAAA-MM-DD", "fonte": "norma ou tabela, edição e item"}`.
   Na base de plantas, tire da lista `a_conferir` o que conferiu e acrescente o mesmo `conferido`. Numa norma do catálogo, troque `situacao` de "conferir" para "vigente" e anote na `nota` a data e quem conferiu.
5. **Fonte sempre.** Todo número novo tem fonte (norma e item, tabela pública com ano, SINAPI do estado e mês, cotação com data). Sem fonte, deixe `[MARCADOR]`. Não invente preço, limite técnico nem texto legal.
6. **Não copie texto de norma.** Cite só o número, a edição e o item, com palavras suas.
7. **Sem endereço de internet e sem código.** Não escreva `http://`, `www.`, `<script>` nem tags HTML nos valores: o sistema funciona sem internet e a validação recusa.
8. **Salve em UTF-8**, sem mudar o nome do arquivo. Para conferir se o arquivo continua válido, abra-o no navegador (arrastar o arquivo para uma aba): se aparecer erro, falta uma vírgula ou aspas.
9. Arquivo `…__parte-<módulo>.json`: é só o pedaço do arquivo do sistema que é deste módulo. Mude só dentro de `"valor"`; não mexa em `"caminho"`, `"_leia"` nem `"_arquivo"`.
"""


def leia_me(mod: dict, kit: str, data: str, commit: str | None, editaveis: list, referencia: list,
            met: dict, docs: Path, pend: list, previa: bool = False) -> str:
    resp = ", ".join(mod["responsaveis"])
    out = [f"# Kit de revisão · {mod['nome']}", "",
           f"- **Kit:** `{kit}` (gerado em {data})",
           f"- **Quem revisa:** {resp}",
           f"- **Versão do sistema:** {(commit or 'sem Git')[:12]}",
           "- **Quem incorpora no sistema:** Eric Oliveira (servidor)", "",
           "Este kit tem só os arquivos do seu módulo. Você muda o que está em `editaveis/`, preenche a "
           "`FICHA_REVISAO.md` e devolve as duas coisas. O Eric confere, aplica numa cópia separada do sistema, "
           "roda os testes e só então junta ao sistema. Nada do que você mudar quebra a estrutura: o que estiver "
           "fora das regras volta com a explicação.", "",
           "## 1. O que revisar", ""]
    texto18 = linha_doc18(docs / DOC18, mod["nome"]) or mod.get("o_que_revisar", "")
    out += [f"Do documento 18 (Checklist de implantação e responsáveis): {texto18}", ""]
    if mod.get("o_que_revisar") and mod["o_que_revisar"].rstrip(". ") != texto18.rstrip(". "):
        out += [mod["o_que_revisar"], ""]
    out += ["Para cada módulo (documento 18, seção 4):", "",
            "- [ ] Resolver os itens marcados \"verificar\" ou \"a conferir\": marcar como conferidos, com fonte e data.",
            "- [ ] Conferir um caso real à mão: o resultado bate com o sistema dentro da tolerância combinada.",
            "- [ ] Passar as normas de \"simplificado\" ou \"só citado\" para \"conforme\", ou justificar (documento 17).",
            "- [ ] Revisar as telas nos dois idiomas, nos dois temas e no celular (o que for de tela vai na ficha).", ""]
    chaves = [k for k in [mod.get("metodologia"), *mod.get("metodologia_extra", [])] if k]
    calcs = [c for k in chaves for c in (met.get("modulos", {}).get(k) or {}).get("calculos", [])]
    if calcs:
        out += ["## 2. Cálculos deste módulo e situação diante da norma", "",
                tabela_md(["Cálculo", "id", "Situação", "O que falta"],
                          [[c.get("nome", ""), f"`{c.get('id', '')}`", c.get("status", ""),
                            c.get("o_que_falta") or "—"] for c in calcs]), ""]
        ids = {c.get("id") for c in calcs}
        adeq = [a for a in met.get("adequacoes", []) if ids & set(a.get("calculos", []))]
        if adeq:
            out += ["### Adequações do documento 17 que tocam este módulo", "",
                    tabela_md(["Prioridade", "O que", "Quem", "Pronto quando"],
                              [[a.get("prioridade", ""), a.get("titulo", ""), a.get("quem", ""),
                                a.get("criterio_de_aceite", "")] for a in adeq]), ""]
    out += ["## 3. Itens marcados para conferir nos arquivos editáveis", ""]
    if pend:
        out += [f"{len(pend)} item(ns). Os primeiros:", ""]
        out += [f"- `{a}` · {o}: {d}" for a, o, d in pend[:40]]
        if len(pend) > 40:
            out += [f"- … e mais {len(pend) - 40}."]
    else:
        out += ["Nenhum item marcado. Confira mesmo assim os valores e as fontes."]
    out += ["", "## 4. O que tem neste kit", "",
            "| Pasta ou arquivo | Para quê |", "|---|---|",
            "| `editaveis/` | O que você pode mudar. |",
            "| `referencia/` | Código, documentos, testes e páginas de conferência, para ler. **Não mude**: mudança aqui é recusada. |",
            "| `FICHA_REVISAO.md` | O que você mudou, por quê e com qual fonte. |",
            "| `MANIFESTO.json` | Lista dos arquivos com a \"impressão digital\" (SHA-256) de cada um. Não mexa. |", "",
            "Arquivos que você pode mudar:", ""]
    for e in editaveis:
        if e["tipo"] == "trocas":
            continue
        if e["fonte"].endswith("physis-i18n-modulos.json") and e["partes"] is not None:
            out.append(f"- `{e['arquivo_kit']}` (no sistema: `{e['fonte']}`) — o inglês das telas deste módulo: "
                       f"{sum(1 for p in e['partes'] if p[0] == 'I18N')} frases. A chave (\"caminho\") é a frase em "
                       "português; mude só o inglês (\"valor\").")
            continue
        if e["partes"] is None:
            onde = "arquivo inteiro"
        else:
            onde = "só: " + "; ".join(caminho_texto(p) for p in e["partes"][:12])
            if len(e["partes"]) > 12:
                onde += f" (e mais {len(e['partes']) - 12})"
        out.append(f"- `{e['arquivo_kit']}` (no sistema: `{e['fonte']}`) — {onde}")
    if not [e for e in editaveis if e["tipo"] != "trocas"]:
        out.append("- Nenhum arquivo de dados neste módulo: a revisão vai na `FICHA_REVISAO.md` e nas trocas de texto.")
    trocas = [e for e in editaveis if e["tipo"] == "trocas"]
    if trocas:
        perm = trocas[0]["arquivos_permitidos"]
        out.append("- `editaveis/trocas-de-texto.json` — troca literal de texto de tela ou de documento, nestes arquivos: "
                   + (", ".join(f"`{x}`" for x in perm) if perm else "nenhum (este kit não tem tela)") + ".")
    out += ["", "## 5. Como mudar um arquivo sem estragar", "", REGRAS_EDICAO,
            "10. **Textos de tela** (erro de digitação, frase confusa, termo técnico errado): use "
            "`editaveis/trocas-de-texto.json`. Copie o texto exatamente como está no arquivo (antes), escreva o novo "
            "(depois) e o motivo. O texto de antes tem de aparecer **uma vez só** no arquivo; até 400 caracteres, "
            "numa linha, sem os sinais de código (menor, maior, chaves, crase, ponto e vírgula, seta) e sem endereço de "
            "internet. Em `physis-hub/web/painel.html` (a plataforma) vale o texto que você vê na tela.",
            "11. **Inglês**: no arquivo `physis-i18n-modulos__parte-….json`, a chave é a frase em português e o valor é "
            "o inglês. Mude só o inglês. Se trocar uma frase em português pela troca de texto, avise na ficha: o inglês "
            "dela precisa de chave nova.",
            "12. **Conta, regra, comportamento ou código**: não dá para mudar pelo kit. Descreva na `FICHA_REVISAO.md` "
            "(o que, onde, por quê, fonte); o Eric leva para quem mexe no código.", ""]
    if any(e["tipo"] == "texto" for e in editaveis):
        out += ["Arquivos de texto (`.h`, `.yaml`, `.md`): mude só o necessário, sem senha, chave nem número "
                "pessoal (segredos ficam fora do kit, em `secrets.h` ou `secrets.yaml` de cada aparelho).", ""]
    out += ["## 6. Como ver o resultado", ""]
    if previa:
        out += [f"**Na hora:** abra `ABRIR-PREVIA.html` (duplo clique). Escolha no botão os arquivos que você mudou "
                f"em `editaveis/` (pode escolher vários). A página abre a plataforma de demonstração já com as suas "
                f"mudanças, na aba **{mod.get('aba') or 'resumo'}**, e lista o que mudou. Funciona sem internet e não "
                "grava nada. Bases que não aparecem na plataforma (casos de teste, parâmetros de aparelho) ficam só "
                "na lista. As premissas aparecem na seção \"Metodologia e normas\" de cada aba (linha \"Premissas da base\").", ""]
    if mod.get("conferir"):
        for c in mod["conferir"]:
            out.append(f"- `referencia/{c['arquivo']}` — {c['como']}")
        out += ["", "As páginas funcionam sem internet. Se o navegador bloquear a leitura automática de arquivos, "
                "use o botão de escolher arquivo da própria página."]
    else:
        out.append("- Não há página de conferência para este módulo: confira pelos documentos de `referencia/` e "
                   "pelos testes de bancada; anote os resultados na ficha.")
    if mod.get("testes"):
        out += ["", "Testes automáticos que conferem este módulo (o Eric roda): " +
                ", ".join(f"`{t}`" for t in mod["testes"]) + "."]
    out += ["", "## 7. Como devolver", "",
            "1. Feche os arquivos e confira a `FICHA_REVISAO.md` preenchida (o que mudou, por quê, fonte).",
            f"2. Compacte **só** a pasta `editaveis/` e a `FICHA_REVISAO.md` num ZIP com o nome "
            f"`devolucao-{kit}-SeuNome.zip` (botão direito → Enviar para → Pasta compactada).",
            "3. Mande o ZIP ao Eric Oliveira. Não mande a pasta `referencia/`.",
            "4. O Eric responde com o relatório da validação: o que entrou, o que foi recusado e por quê.", "",
            "Não mude o arquivo `editaveis/_KIT.json`: é ele que diz de qual kit veio a devolução.", ""]
    det = secao_doc(docs / DOC17, mod.get("doc17_secao"))
    if det:
        out += ["## Anexo · Como o sistema calcula hoje (documento 17)", "", det, ""]
    out += ["---", "Validação preliminar: não substitui o projeto com ART (ou RRT) de um profissional habilitado. "
            "As normas são citadas só pelo número e pelo item, com redação própria da Physis.", ""]
    return "\n".join(out)


def ficha(mod: dict, kit: str) -> str:
    return f"""# Ficha de revisão · {mod['nome']}

- **Kit:** `{kit}`
- **Revisor(a):**
- **Data da revisão:**
- **Responsáveis do módulo:** {', '.join(mod['responsaveis'])}

## 1. O que mudou

Uma linha por mudança. "Onde" é o arquivo e o item (por exemplo: `physis-plantas.json › plantas › n=12 › espacamento`).

| # | Onde | Valor antes | Valor depois | Por quê | Fonte (norma ou tabela, edição, item; ou cotação com data) |
|---|---|---|---|---|---|
| 1 |  |  |  |  |  |

## 2. Itens conferidos sem mudança

| Onde | Fonte | Data |
|---|---|---|
|  |  |  |

## 3. Caso conferido à mão

Entradas usadas, resultado à mão, resultado do sistema e a diferença (tolerância combinada):

## 4. O que não deu para mudar nos arquivos

Telas, textos em inglês, regras de cálculo no código, itens a apagar: descreva aqui. O Eric leva para quem mexe no código.

## 5. Itens que ficaram sem conferir (e por quê)

## Declaração

- [ ] Mudei só valores dos arquivos de `editaveis/`, sem apagar chaves nem ids.
- [ ] Todo número novo tem fonte; o que não tem ficou como `[MARCADOR]`.
- [ ] Não copiei texto de norma (só número, edição e item, com redação própria).
"""


# ---------------------------------------------------------------- geração

def leia_extrato(arquivo: str, nome_modulo: str) -> str:
    return (f"Parte do arquivo {arquivo} que é do módulo {nome_modulo}. Mude só dentro de "
            "\"valor\"; não mexa em \"caminho\", \"_leia\" nem \"_arquivo\".")


ARQ_TROCAS = "editaveis/trocas-de-texto.json"
LIMITE_TROCA = 400


def leia_trocas() -> str:
    return ("Troca literal de texto de tela ou de documento (erro de digitação, frase confusa, termo técnico). "
            "Cada troca: {\"arquivo\": um de arquivos_permitidos, \"antes\": o texto exatamente como está (tem de aparecer "
            "uma vez só no arquivo), \"depois\": o texto novo, \"motivo\": por quê}. Até 400 caracteres, numa linha só, "
            "sem os sinais < > { } ` ; => e sem endereço de internet; as aspas e barras invertidas do 'depois' têm de ser "
            "as mesmas do 'antes'. Exemplo: {\"arquivo\": \"sistema/physis-sbn.js\", \"antes\": \"Espacamento\", "
            "\"depois\": \"Espaçamento\", \"motivo\": \"acento\"}. Mudança de conta, regra ou comportamento NÃO vai aqui: "
            "vai na FICHA_REVISAO.md. O inglês das telas muda no arquivo physis-i18n-modulos.")


def arquivos_troca(mod: dict, editaveis_fontes: set, raiz: Path) -> list:
    arqs = list(mod.get("referencia", [])) + [c["arquivo"] for c in mod.get("conferir", [])]
    ok = [r for r in dict.fromkeys(arqs) if pode_trocar_texto(r) and r not in editaveis_fontes
          and (raiz / r).is_file()]
    if mod.get("aba") and (raiz / PAINEL_REL).is_file() and PAINEL_REL not in ok:
        ok.append(PAINEL_REL)
    return ok


def preparar_editavel(ed: dict, mod: dict, raiz: Path, mapa: dict | None = None) -> dict | None:
    fonte = raiz / ed["arquivo"]
    bruto = fonte.read_bytes()
    info = {"fonte": ed["arquivo"], "sha256_fonte": sha256_bytes(bruto),
            "pos_aplicar": [], "partes": None, "bloqueadas": [list(c) for c in ed.get("bloqueadas", [])]}
    if ed.get("texto"):
        info.update(tipo="texto", arquivo_kit="editaveis/" + ed["arquivo"], conteudo=bruto,
                    hash_partes={"": sha256_bytes(bruto)})
        return info
    dados = json.loads(bruto.decode("utf-8-sig"))
    partes = expandir_partes(ed, raiz, mod, mapa)
    if partes is None:
        info.update(tipo="json", arquivo_kit="editaveis/" + ed["arquivo"], conteudo=bruto,
                    hash_partes={"": sha_canonico(dados)}, _valor=dados, _original=dados)
        return info
    if not partes:
        return None
    extrato = {"_leia": leia_extrato(ed["arquivo"], mod["nome"]), "_arquivo": ed["arquivo"], "partes": []}
    hashes = {}
    for p in partes:
        v = pegar(dados, p)
        extrato["partes"].append({"caminho": p, "valor": v})
        hashes[json.dumps(p, ensure_ascii=False)] = sha_canonico(v)
    texto = json.dumps(extrato, ensure_ascii=False, indent=2) + "\n"
    info.update(tipo="json-partes", arquivo_kit="editaveis/" + nome_extrato(ed["arquivo"], mod["id"]),
                conteudo=texto.encode("utf-8"), partes=partes, hash_partes=hashes, _valor=extrato, _original=dados)
    return info


# ---------------------------------------------------------------- prévia (ABRIR-PREVIA.html)

MODULOS_PREVIA = ["planejador", "sustainkit", "solar", "avac", "turbinas", "agua", "monitoramento", "campo", "zonas",
                  "animais", "saude", "supervisao", "gestao", "certificacoes", "sbn", "circular", "carbono",
                  "resiliencia", "cursos"]
_CACHE_PLATAFORMA: dict = {}
LINHA_PREMISSAS = 'linha("Premissas da base", pr.join(", "))'
LINHA_PREMISSAS_PREVIA = ('linha("Premissas da base", pr.map(function (p) { var b = window.__previaPremissa ? '
                          'window.__previaPremissa(p) : ""; return b ? p + " = " + b : p; }).join(", "))')
SCRIPT_PREMISSAS = ('<script>window.__previaPremissa = function (id) { try { var d = JSON.parse(document.getElementById('
                    '"base-premissas-previa").textContent); var x = (d.premissas || []).filter(function (p) { return p.id === id; })[0]; '
                    'return x ? x.valor_padrao + " " + (x.unidade || "") : ""; } catch (e) { return ""; } };</script>')


def json_em_script(dados) -> str:
    return (json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
            .replace("</", "<\\/").replace("<!--", "<\\u0021--"))


def plataforma_previa(raiz: Path, avisos: list) -> str | None:
    """Plataforma de demonstração com todos os módulos ligados (mesmos ajustes de demos/gerar_demos.py)."""
    painel = raiz / PAINEL_REL
    chave = (str(raiz), painel.stat().st_mtime_ns if painel.is_file() else 0)
    if chave in _CACHE_PLATAFORMA:
        avisos += _CACHE_PLATAFORMA[chave][1]
        return _CACHE_PLATAFORMA[chave][0]
    proprios, texto = [], None
    script = raiz / "demos" / "gerar_demos.py"
    if painel.is_file() and script.is_file():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("_physis_gerar_demos", script)
            gd = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(gd)
            gd.PAINEL = painel
            gd.MODULOS_DEMO = list(MODULOS_PREVIA)
            texto = gd.plataforma("physis-demo-cliente.html", "resumo", gd.MODULOS_DEMO, "{ campo:6, zonas:1, col:0, com:0 }", "plataforma")
        except (SystemExit, Exception) as e:  # o original mudou e um ajuste não cabe mais
            proprios.append(f"prévia: não deu para preparar a plataforma a partir do painel ({e}); usei a demo pronta")
            texto = None
    if texto is None and (raiz / "demos" / "physis-demo-cliente.html").is_file():
        texto = (raiz / "demos" / "physis-demo-cliente.html").read_text(encoding="utf-8")
    if texto is None:
        proprios.append("prévia: sem painel nem demo no repositório; o kit vai sem ABRIR-PREVIA.html")
    else:
        prem = raiz / "sistema" / "physis-premissas.json"
        if prem.is_file() and LINHA_PREMISSAS in texto:
            bloco = ('<script type="application/json" id="base-premissas-previa">' + json_em_script(ler_json(prem))
                     + "</script>\n" + SCRIPT_PREMISSAS + "\n")
            texto = texto.replace(LINHA_PREMISSAS, LINHA_PREMISSAS_PREVIA, 1)
            texto = texto.replace("</head>", bloco + "</head>", 1)
        elif prem.is_file():
            proprios.append("prévia: não achei onde mostrar as premissas na plataforma; elas aparecem só na lista de mudanças")
    _CACHE_PLATAFORMA[chave] = (texto, proprios)
    avisos += proprios
    return texto


def bloco_da_base(fonte: str, plataforma: str) -> str | None:
    nome = Path(fonte).name
    if nome == "physis-metodologia.json":
        return "mod-metodologia" if '<script id="mod-metodologia">' in plataforma else None
    if nome == "physis-premissas.json":
        ident = "base-premissas-previa"
    else:
        ident = "base-" + Path(fonte).stem.replace("physis-", "")
    return ident if f'<script type="application/json" id="{ident}">' in plataforma else None


def escrever_previa(pasta: Path, mod: dict, kit: str, editaveis: list, originais: dict, raiz: Path,
                    avisos: list) -> dict | None:
    modelo = raiz / "ferramentas" / "kits" / "previsualizar.html"
    if not modelo.is_file():
        avisos.append("prévia: ferramentas/kits/previsualizar.html não existe")
        return None
    plat = plataforma_previa(raiz, avisos)
    texto_modelo = modelo.read_text(encoding="utf-8")
    ref = pasta / "referencia" / "ferramentas" / "kits" / "previsualizar.html"
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_bytes(modelo.read_bytes())
    if plat is None:
        return {"referencia": ref}
    marca = '<script type="application/json" id="previa-dados">null</script>'
    if texto_modelo.count(marca) != 1:
        avisos.append("prévia: o modelo previsualizar.html não tem o bloco previa-dados")
        return {"referencia": ref}
    dados = {"kit": kit, "modulo": mod["id"], "nome": mod["nome"], "aba": mod.get("aba") or "resumo",
             "editaveis": [{"nome": e["arquivo_kit"].split("/")[-1], "arquivo_kit": e["arquivo_kit"],
                            "fonte": e.get("fonte"), "tipo": e["tipo"]} for e in editaveis],
             "originais": {f: v for f, v in originais.items()},
             "blocos": {e["fonte"]: bloco_da_base(e["fonte"], plat) for e in editaveis
                        if e["tipo"] in ("json", "json-partes")},
             "plataforma": plat}
    final = texto_modelo.replace(marca, '<script type="application/json" id="previa-dados">'
                                 + json_em_script(dados) + "</script>")
    atalho = pasta / "ABRIR-PREVIA.html"
    atalho.write_text(final, encoding="utf-8", newline="\n")
    return {"referencia": ref, "atalho": atalho}


def gerar_kit(mod: dict, mapa: dict, saida: Path, data: str, raiz: Path = RAIZ,
              docs: Path = DOCS_PADRAO, zipar: bool = True, commit: str | None = None,
              previa: bool = True) -> dict:
    kit = f"kit-{mod['id']}-{data}"
    pasta = saida / kit
    if pasta.exists():
        shutil.rmtree(pasta)
    (pasta / "editaveis").mkdir(parents=True)
    commit = commit if commit is not None else commit_atual(raiz)
    avisos = []
    pos = mapa.get("arquivos_pos_aplicar", {})
    editaveis, pend, originais = [], [], {}
    for ed in mod.get("editaveis", []):
        if not (raiz / ed["arquivo"]).is_file():
            avisos.append(f"editável não encontrado: {ed['arquivo']}")
            continue
        info = preparar_editavel(ed, mod, raiz, mapa)
        if info is None:
            continue
        info["pos_aplicar"] = list(pos.get(ed["arquivo"], []))
        destino = pasta / info["arquivo_kit"]
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(info.pop("conteudo"))
        info["sha256_kit"] = sha256_arquivo(destino)
        valor = info.pop("_valor", None)
        original = info.pop("_original", None)
        if original is not None:
            originais[info["fonte"]] = original
        if info["tipo"] == "json":
            pend += [(info["arquivo_kit"].split("/")[-1], a, d) for a, d in pendencias(valor)]
        elif info["tipo"] == "json-partes":
            for parte in valor["partes"]:
                pend += [(info["arquivo_kit"].split("/")[-1], a, d)
                         for a, d in pendencias(parte["valor"], list(parte["caminho"]))]
        editaveis.append(info)
    # troca literal de texto de tela (sempre presente; lista vazia = nada a trocar)
    permitidos = arquivos_troca(mod, {e["fonte"] for e in editaveis}, raiz)
    trocas = {"_leia": leia_trocas(), "arquivos_permitidos": permitidos, "trocas": []}
    (pasta / ARQ_TROCAS).write_text(json.dumps(trocas, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8", newline="\n")
    editaveis.append({"tipo": "trocas", "arquivo_kit": ARQ_TROCAS, "fonte": None, "arquivos_permitidos": permitidos,
                      "sha256_kit": sha256_arquivo(pasta / ARQ_TROCAS), "pos_aplicar": [], "partes": None,
                      "bloqueadas": []})
    referencia = []
    arquivos_ref = list(dict.fromkeys(list(mod.get("referencia", [])) +
                                      [c["arquivo"] for c in mod.get("conferir", [])] +
                                      [e["fonte"] for e in editaveis if e["tipo"] == "json-partes"]))
    for rel in arquivos_ref:
        origem = raiz / rel
        if not origem.is_file():
            avisos.append(f"referência não encontrada: {rel}")
            continue
        if re.search(r"(^|/)(secrets\.(h|ya?ml)|\.env)$", rel):
            avisos.append(f"segredo fora do kit: {rel}")
            continue
        destino = pasta / "referencia" / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        conteudo = origem.read_bytes()
        if rel.endswith("teste-avac.html"):
            # a página gerada aponta para o arquivo no computador de quem gerou; no kit, caminho relativo
            conteudo = re.sub(rb'src="file:///[^"]*?/sistema/physis-avac\.js"',
                              b'src="../../sistema/physis-avac.js"', conteudo)
            js = raiz / "sistema" / "physis-avac.js"
            if js.is_file() and "sistema/physis-avac.js" not in arquivos_ref:
                (pasta / "referencia" / "sistema").mkdir(parents=True, exist_ok=True)
                (pasta / "referencia" / "sistema" / "physis-avac.js").write_bytes(js.read_bytes())
                referencia.append({"arquivo_kit": "referencia/sistema/physis-avac.js",
                                   "fonte": "sistema/physis-avac.js",
                                   "sha256": sha256_arquivo(pasta / "referencia/sistema/physis-avac.js")})
        destino.write_bytes(conteudo)
        referencia.append({"arquivo_kit": "referencia/" + rel, "fonte": rel, "sha256": sha256_bytes(conteudo)})
    prev = escrever_previa(pasta, mod, kit, editaveis, originais, raiz, avisos) if previa else None
    if prev:
        referencia.append({"arquivo_kit": "referencia/ferramentas/kits/previsualizar.html",
                           "fonte": "ferramentas/kits/previsualizar.html", "sha256": sha256_arquivo(prev["referencia"])})
    nota = pasta / "referencia" / "LEIA-ME-REFERENCIA.txt"
    nota.parent.mkdir(parents=True, exist_ok=True)
    nota.write_text("Arquivos só para leitura. Não mude nada aqui: a devolução com mudança nesta pasta é "
                    "recusada. O que precisar mudar no código, descreva na FICHA_REVISAO.md.\n",
                    encoding="utf-8", newline="\n")
    referencia.append({"arquivo_kit": "referencia/LEIA-ME-REFERENCIA.txt", "fonte": None,
                       "sha256": sha256_arquivo(nota)})
    met_arq = raiz / "sistema" / "physis-metodologia.json"
    met = ler_json(met_arq) if met_arq.is_file() else {}
    (pasta / "LEIA-ME.md").write_text(leia_me(mod, kit, data, commit, editaveis, referencia, met, docs, pend,
                                              bool(prev and prev.get("atalho"))),
                                      encoding="utf-8", newline="\n")
    (pasta / "FICHA_REVISAO.md").write_text(ficha(mod, kit), encoding="utf-8", newline="\n")
    marca = {"kit": kit, "modulo": mod["id"], "commit": commit,
             "_leia": "Não mude este arquivo: diz de qual kit veio a devolução."}
    (pasta / "editaveis" / ARQ_KIT).write_text(json.dumps(marca, ensure_ascii=False, indent=1) + "\n",
                                               encoding="utf-8", newline="\n")
    sujos = []
    if commit:
        fontes = [e["fonte"] for e in editaveis if e["fonte"]] + [r["fonte"] for r in referencia if r["fonte"]]
        r = git(raiz, "status", "--porcelain", "--", *fontes) if fontes else None
        if r is not None and r.returncode == 0:
            sujos = sorted({ln[3:].strip() for ln in r.stdout.splitlines() if ln.strip()})
    outros = {n: sha256_arquivo(pasta / n) for n in ("LEIA-ME.md", "FICHA_REVISAO.md")}
    outros["editaveis/" + ARQ_KIT] = sha256_arquivo(pasta / "editaveis" / ARQ_KIT)
    if (pasta / "ABRIR-PREVIA.html").is_file():
        outros["ABRIR-PREVIA.html"] = sha256_arquivo(pasta / "ABRIR-PREVIA.html")
    manifesto = {
        "formato": FORMATO, "kit": kit, "modulo": mod["id"], "nome": mod["nome"],
        "responsaveis": mod["responsaveis"], "data": data, "aba": mod.get("aba"),
        "gerado_em": _dt.datetime.now().isoformat(timespec="seconds"),
        "commit": commit, "arquivos_com_mudanca_nao_salva_no_git": sujos,
        "editaveis": editaveis, "referencia": referencia, "outros": outros,
        "testes": list(mod.get("testes", [])), "avisos": avisos,
    }
    texto_man = json.dumps(manifesto, ensure_ascii=False, indent=1) + "\n"
    (pasta / "MANIFESTO.json").write_text(texto_man, encoding="utf-8", newline="\n")
    guarda = saida / "_manifestos"
    guarda.mkdir(parents=True, exist_ok=True)
    (guarda / f"{kit}.json").write_text(texto_man, encoding="utf-8", newline="\n")
    zip_path = None
    if zipar:
        zip_path = saida / f"{kit}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for arq in sorted(pasta.rglob("*")):
                if arq.is_file():
                    z.write(arq, f"{kit}/{arq.relative_to(pasta).as_posix()}")
    return {"kit": kit, "pasta": pasta, "zip": zip_path, "manifesto": manifesto, "avisos": avisos}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gera os kits de revisão por módulo.")
    ap.add_argument("--saida", required=True, help="pasta onde os kits são criados")
    ap.add_argument("--modulo", action="append", help="id do módulo (pode repetir); sem isto, todos")
    ap.add_argument("--data", default=_dt.date.today().isoformat(), help="data do kit (AAAA-MM-DD)")
    ap.add_argument("--documentos", default=str(DOCS_PADRAO), help="pasta com os documentos 17 e 18 (opcional)")
    ap.add_argument("--raiz", default=str(RAIZ), help="raiz do repositório (padrão: este repositório)")
    ap.add_argument("--mapa", default=None, help="arquivo de mapa (padrão: ferramentas/kits/modulos.json)")
    ap.add_argument("--sem-zip", action="store_true", help="não cria o ZIP, só a pasta")
    ap.add_argument("--sem-previa", action="store_true", help="não cria o ABRIR-PREVIA.html (kit menor)")
    a = ap.parse_args(argv)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.data):
        raise SystemExit("--data tem de ser AAAA-MM-DD")
    raiz = Path(a.raiz).resolve()
    mapa = carregar_mapa(Path(a.mapa) if a.mapa else raiz / "ferramentas" / "kits" / "modulos.json")
    mods = mapa["modulos"]
    if a.modulo:
        conhecidos = {m["id"] for m in mods}
        faltam = [x for x in a.modulo if x not in conhecidos]
        if faltam:
            raise SystemExit(f"módulo desconhecido: {', '.join(faltam)}. Existem: {', '.join(sorted(conhecidos))}")
        mods = [m for m in mods if m["id"] in a.modulo]
    saida = Path(a.saida).resolve()
    saida.mkdir(parents=True, exist_ok=True)
    commit = commit_atual(raiz)
    for m in mods:
        r = gerar_kit(m, mapa, saida, a.data, raiz, Path(a.documentos), not a.sem_zip, commit, not a.sem_previa)
        man = r["manifesto"]
        print(f"{r['kit']}: {len(man['editaveis'])} editável(is), {len(man['referencia'])} de referência"
              + (f", ZIP {r['zip'].name}" if r["zip"] else ""))
        for av in r["avisos"]:
            print("  aviso:", av)
        if man["arquivos_com_mudanca_nao_salva_no_git"]:
            print("  aviso: arquivos com mudança ainda não salva no Git:",
                  ", ".join(man["arquivos_com_mudanca_nao_salva_no_git"]))
    print(f"manifestos guardados em {saida / '_manifestos'} (o validador usa estes)")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
