#!/usr/bin/env python3
"""Monta a entrega completa do Sistema Physis, tudo na MESMA versão (um commit), conforme o
documento 20 (checklist de envio):

  python ferramentas/emitir_entrega.py --docs "<pasta Documents/Sistema Physis>" [--saida <pasta>]

Antes de montar, confere:
- repositório sem mudanças fora do Git;
- testes passando;
- nenhum banco de teste, .env ou segredo nos arquivos de saída.

Tudo sai de um `git archive` do commit atual, nunca da pasta de trabalho, para que pacotes, módulos,
kits, memos e tarefas sejam a mesma versão. No fim grava `MANIFESTO.json` com o SHA-256 de cada arquivo.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
GIT = shutil.which("git") or r"C:\Program Files\Git\cmd\git.exe"
PY = sys.executable
SEGREDO = re.compile(r"(BEGIN [A-Z ]*PRIVATE KEY|phk_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[0-9A-Za-z-]{10,})")
PROIBIDOS = (".db", ".db-wal", ".db-shm", ".env", ".jks", ".keystore", ".pfx", ".p12")
DOCS_INICIAIS = re.compile(r"^[0-2]\d[a-z]?_.+\.(md|json|ods)$")   # 00 a 29, também 23b_; planilhas .ods (mapeamento semanal)


def rodar(cmd, cwd=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise SystemExit(f"falhou: {' '.join(map(str, cmd))}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r


def apagar_pasta(pasta: Path, tentativas: int = 6):
    """Apaga a entrega anterior. Na pasta do OneDrive um arquivo pode ficar preso por instantes (sincronização):
    tira o "somente leitura", espera e tenta de novo; se continuar preso, para com uma mensagem clara."""
    import os
    import stat
    import time

    def destravar(func, caminho, _erro):
        try:
            os.chmod(caminho, stat.S_IWRITE)
            func(caminho)
        except OSError:
            pass
    for n in range(tentativas):
        shutil.rmtree(pasta, onexc=destravar) if sys.version_info >= (3, 12) else shutil.rmtree(pasta, onerror=destravar)
        if not pasta.exists():
            return
        time.sleep(2 + 2 * n)
    raise SystemExit(f"não consegui apagar {pasta}: o OneDrive (ou outro programa) está usando um arquivo dela. "
                     "Pause a sincronização do OneDrive por alguns minutos ou feche o que estiver aberto e rode de novo.")


PAGINAS_PEDIDAS = ["site-loja-e-plataforma.html", "consultoria.html", "gestao-interna.html", "scada-supervisorio.html",
                   "sustainkit.html", "planejador.html", "painel-municipal.html", "documento-para-comentarios.html",
                   "baixar-o-app.html", "index.html"]
DOCS_PEDIDOS = ["00_", "01_", "04_", "10_", "17_", "18_", "20_", "21_", "22_", "23_", "23b_", "24_"]


def conferir_inventario(saida: Path, rep: Path, mapa: list) -> list[str]:
    """Lista o que falta na entrega em relação ao que já foi pedido (páginas, demos, pacotes de cada cliente, kits e
    módulos de cada item do mapa, documentos, memos, tarefas, pastas por pessoa, índice)."""
    faltas = []
    pg = saida / "02_Paginas_completas"
    faltas += [f"página {n}" for n in PAGINAS_PEDIDAS if not (pg / n).is_file()]
    demos_repo = sorted(p.name for p in (rep / "demos").glob("*.html")) if (rep / "demos").is_dir() else []
    faltas += [f"demo {n}" for n in demos_repo if not (saida / "03_Demos_site" / n).is_file()]
    try:
        clientes = json.loads((rep / "clientes" / "clientes.json").read_text(encoding="utf-8"))
        lista = clientes["clientes"] if isinstance(clientes, dict) and "clientes" in clientes else clientes
        orgs = [c.get("org") for c in lista if isinstance(c, dict) and c.get("org")]
    except (OSError, ValueError, KeyError, TypeError):
        orgs = []
        faltas.append("clientes/clientes.json ilegível")
    pacotes = [p.name for p in (saida / "04_Pacotes_instalacao").glob("*.zip")]
    faltas += [f"pacote do cliente {o}" for o in orgs if not any(o in n for n in pacotes)]
    for k in mapa:
        if not list((saida / "06_Kits_revisao").glob(f"kit-{k['id']}-*.zip")):
            faltas.append(f"kit {k['id']}")
        if not list((saida / "05_Modulos").glob(f"modulo-{k['id']}_*.zip")):
            faltas.append(f"módulo {k['id']}")
        if not k.get("responsaveis"):
            faltas.append(f"responsável do kit {k['id']}")
    docs = [p.name for p in (saida / "01_Documentos").glob("*")]
    faltas += [f"documento {d}*" for d in DOCS_PEDIDOS if not any(n.startswith(d) for n in docs)]
    memos = saida / "01_Documentos" / "19_Memos_Fase2"
    if not memos.is_dir() or len(list(memos.glob("*.md"))) < 12:
        faltas.append("memos da Fase 2 (12)")
    if not list((saida / "10_Gestao_tarefas_Fase2").glob("*.json")):
        faltas.append("tarefas da Gestão")
    for n in ("00_INDICE_DE_ENVIO.md", "00_O_que_e_cada_parte.md"):   # o LEIA-ME é escrito depois, junto do manifesto
        if not (saida / n).is_file():
            faltas.append(n)
    if not (saida / "00_Envio_por_pessoa").is_dir() or not any((saida / "00_Envio_por_pessoa").iterdir()):
        faltas.append("pastas por pessoa")
    return faltas


def zipar(pasta: Path, destino: Path, raiz_nome: str | None = None):
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as z:
        for arq in sorted(pasta.rglob("*")):
            if arq.is_file() and not arq.name.endswith(PROIBIDOS) and "__pycache__" not in arq.parts:
                z.write(arq, Path(raiz_nome or pasta.name) / arq.relative_to(pasta))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--docs", type=Path, required=True)
    ap.add_argument("--saida", type=Path)
    ap.add_argument("--sem-testes", action="store_true", help="só para ensaio: não roda a suíte")
    ap.add_argument("--intermediaria", action="store_true",
                    help="versão intermediária: sai da pasta de trabalho como está, substitui a saída e registra os testes sem bloquear")
    a = ap.parse_args()

    # 1. mesma versão: final = repositório limpo e um commit; intermediária = retrato da pasta de trabalho
    base = rodar([GIT, "rev-parse", "--short", "HEAD"], cwd=RAIZ).stdout.strip()
    sujo = rodar([GIT, "status", "--porcelain"], cwd=RAIZ).stdout.strip()
    if sujo and not a.intermediaria:
        raise SystemExit("há mudanças fora do Git. Faça o commit antes de emitir (ou use --intermediaria):\n" + sujo[:2000])
    commit = base + ("-intermediaria" if a.intermediaria else "")
    hoje = datetime.date.today().isoformat()
    saida = a.saida or a.docs / "sistema_physis_fase1"
    if saida.exists():
        if not a.intermediaria and not (saida / "MANIFESTO.json").is_file():
            raise SystemExit(f"{saida} existe e não é uma entrega; escolha outra --saida")
        apagar_pasta(saida)           # mesma pasta, versão nova (a anterior é substituída)

    tmp = Path(tempfile.mkdtemp(prefix="physis-entrega-"))
    resultado_testes = "não rodados"
    try:
        rep = tmp / "repo"
        arq_zip = tmp / "repo.zip"
        if a.intermediaria:
            shutil.copytree(RAIZ, rep, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.db", "*.db-wal", "*.db-shm",
                                                                       "node_modules", "www", "*.env", "*.jks", "*.keystore"))
            zipar(rep, arq_zip, "sistema-physis")
        else:
            rodar([GIT, "archive", "--format=zip", "-o", str(arq_zip), "HEAD"], cwd=RAIZ)
            with zipfile.ZipFile(arq_zip) as z:
                z.extractall(rep)
        if not a.sem_testes:
            r = rodar([PY, "-m", "unittest", "discover", "-s", "tests"], cwd=rep / "physis-hub", check=False)
            resumo = [l for l in (r.stderr or "").splitlines() if l.startswith(("Ran ", "OK", "FAILED", "FAIL:", "ERROR:"))]
            resultado_testes = " · ".join(resumo[-6:]) or "sem resumo"
            if r.returncode != 0 and not a.intermediaria:
                raise SystemExit("os testes não passaram; nada foi emitido.\n" + r.stderr[-3000:])
        saida.mkdir(parents=True)
        P = lambda nome: (saida / nome).mkdir(parents=True, exist_ok=True) or saida / nome

        # 01 documentos: iniciais (00–2x), memos da Fase 2, tarefas da Gestão
        d = P("01_Documentos")
        for f in sorted(a.docs.iterdir()):
            if f.is_file() and DOCS_INICIAIS.match(f.name):
                shutil.copy2(f, d / f.name)
        if (a.docs / "19_Memos_Fase2").is_dir():
            shutil.copytree(a.docs / "19_Memos_Fase2", d / "19_Memos_Fase2")
        g = P("10_Gestao_tarefas_Fase2")
        if (a.docs / "18_Checklist_para_importar_na_Gestao.json").is_file():
            shutil.copy2(a.docs / "18_Checklist_para_importar_na_Gestao.json", g / "tarefas_fase2_importar_na_gestao.json")

        # 02 páginas completas (abrem direto no navegador)
        pg = P("02_Paginas_completas")
        paginas = {"physis-hub/web/painel.html": "site-loja-e-plataforma.html", "physis-hub/web/consultoria.html": "consultoria.html",
                   "sistema/gestao-interna-physis.html": "gestao-interna.html", "sistema/physis-scada-demo.html": "scada-supervisorio.html",
                   "sistema/SustainKit_Definitivo.html": "sustainkit.html", "modulos/planejador/planejador-physis.html": "planejador.html",
                   "physis-hub/web/municipio.html": "painel-municipal.html",
                   "physis-hub/web/documento.html": "documento-para-comentarios.html", "app-nativo/site/baixar.html": "baixar-o-app.html"}
        for orig, nome in paginas.items():
            if (rep / orig).is_file():
                shutil.copy2(rep / orig, pg / nome)
        (pg / "index.html").write_text(capa(sorted(p.name for p in pg.glob("*.html")), commit, hoje), encoding="utf-8")

        # 03 demos do site (dados simulados)
        if (rep / "demos").is_dir():
            dm = P("03_Demos_site")
            for f in (rep / "demos").glob("*.html"):
                shutil.copy2(f, dm / f.name)

        # 04 pacotes de instalação de cada cliente e do servidor da Physis (montar_clientes)
        pc = P("04_Pacotes_instalacao")
        rodar([PY, "montar_clientes.py", "--saida", str(tmp / "pacotes")], cwd=rep / "physis-hub")
        for z in (tmp / "pacotes").glob("*.zip"):
            shutil.copy2(z, pc / z.name)

        # 05 pacote de cada módulo (código + dados + manuais + testes, só leitura)
        mapa = json.loads((rep / "ferramentas" / "kits" / "modulos.json").read_text(encoding="utf-8"))["modulos"]
        md = P("05_Modulos")
        for k in mapa:
            arqs = {e["arquivo"] if isinstance(e, dict) else e for e in k.get("editaveis", [])} | set(k.get("referencia", []))
            alvo = tmp / "mod" / f"modulo-{k['id']}"
            for rel in sorted(arqs):
                if (rep / rel).is_file():
                    (alvo / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(rep / rel, alvo / rel)
            if alvo.exists():
                (alvo / "LEIA-ME.txt").write_text(f"{k['nome']} · responsáveis: {', '.join(k['responsaveis'])} · versão {commit}\n"
                                                  "Cópia só para leitura. Para revisar e devolver, use o kit de revisão deste módulo.\n", encoding="utf-8")
                zipar(alvo, md / f"modulo-{k['id']}_{commit}.zip")

        # 06 kits de revisão (24) com manifestos
        kt = P("06_Kits_revisao")
        rodar([PY, str(rep / "ferramentas" / "gerar_kits_revisao.py"), "--saida", str(kt)], cwd=rep)

        # 07 implantação e serviços abertos · 08 app nativo · 09 código-fonte
        im = P("07_Implantacao_e_servicos")
        for nome in ("implantacao", "servicos"):
            if (rep / nome).is_dir():
                zipar(rep / nome, im / f"{nome}_{commit}.zip")
        if (rep / "app-nativo").is_dir():
            zipar(rep / "app-nativo", P("08_App_nativo") / f"app-nativo_{commit}.zip")
        shutil.copy2(arq_zip, P("09_Codigo_fonte") / f"sistema-physis_{commit}.zip")

        # 11 metodologia, modelagem e informações da Fase 1, legíveis sem abrir o código
        mt = P("11_Metodologia_e_Modelagem")
        if (rep / "physis-hub" / "docs").is_dir():
            shutil.copytree(rep / "physis-hub" / "docs", mt / "documentacao_tecnica",
                            ignore=shutil.ignore_patterns("*.js", "*.db*"))
        bases = mt / "bases_e_modelos"
        bases.mkdir(exist_ok=True)
        for rel in ("sistema/physis-metodologia.json", "sistema/physis-premissas.json", "sistema/physis-variaveis.json",
                    "sistema/physis-fatores-emissao.json", "sistema/physis-certificacoes.json", "sistema/physis-simulacao-premissas.json",
                    "sistema/loja-catalogo-inicial.json"):
            if (rep / rel).is_file():
                shutil.copy2(rep / rel, bases / Path(rel).name)
        for rel, nome in (("sistema/simulacao-exemplos", "exemplos_simulacao"), ("modulos/mapeamento/exemplos", "exemplos_mapeamento")):
            if (rep / rel).is_dir():
                shutil.copytree(rep / rel, mt / nome)
        conf = mt / "paginas_de_conferencia"
        conf.mkdir(exist_ok=True)
        for f in (rep / "ferramentas" / "testes-navegador").glob("conferir-*.html"):
            shutil.copy2(f, conf / f.name)

        # 00 versão de envio: uma pasta por pessoa e o índice de tudo (pedido de 15/11/2026: "todos os itens, projetos,
        #    módulos e páginas claramente indicados para a versão de envio")
        montar_envio(saida, a.docs, mapa, commit, hoje, rep)

        # inventário: tudo o que já foi pedido tem de estar na entrega (nada some sem alguém perceber)
        faltas = conferir_inventario(saida, rep, mapa)
        if faltas:
            if a.intermediaria:
                print("AVISO, falta na entrega:\n- " + "\n- ".join(faltas))
            else:
                raise SystemExit("entrega incompleta; falta:\n- " + "\n- ".join(faltas))

        # verificação: nada proibido, nenhum segredo
        problemas = []
        for f in saida.rglob("*"):
            if f.is_file():
                if f.name.endswith(PROIBIDOS):
                    problemas.append(f"arquivo proibido: {f.relative_to(saida)}")
                if f.suffix == ".zip":
                    with zipfile.ZipFile(f) as z:
                        for n in z.namelist():
                            if n.endswith(PROIBIDOS):
                                problemas.append(f"{f.name}: contém {n}")
                elif f.suffix in (".md", ".html", ".json", ".txt", ".py", ".js") and SEGREDO.search(f.read_text("utf-8", "replace")):
                    problemas.append(f"possível segredo em {f.relative_to(saida)}")
        if problemas:
            raise SystemExit("entrega recusada:\n" + "\n".join(problemas[:50]))

        # manifesto e leia-me
        lista = {str(f.relative_to(saida)).replace("\\", "/"): hashlib.sha256(f.read_bytes()).hexdigest()
                 for f in sorted(saida.rglob("*")) if f.is_file()}
        (saida / "MANIFESTO.json").write_text(json.dumps({"commit": commit, "data": hoje, "intermediaria": a.intermediaria,
                                                          "testes": resultado_testes, "arquivos": lista}, ensure_ascii=False, indent=1), encoding="utf-8")
        aviso = ("\n> **Versão intermediária** (trabalho em andamento sobre a versão salva " + base + "). Testes: " + resultado_testes +
                 ". Será substituída pela versão final nesta mesma pasta.\n") if a.intermediaria else ""
        (saida / "LEIA-ME.md").write_text(LEIA.format(commit=commit, hoje=hoje, n=len(lista), nkits=len(mapa)) + aviso, encoding="utf-8")
        print(f"entrega pronta: {saida} ({len(lista)} arquivos, versão {commit})")

        # cópia da versão de envio inteira na pasta de backup (onde a equipe procura), com a versão no nome
        bk = a.docs / "_backup_arquivos"
        bk.mkdir(exist_ok=True)
        destino = bk / f"{saida.name}_ENVIO_{commit}_{hoje}.zip"
        zipar(saida, destino, saida.name)
        print(f"cópia de envio: {destino}")
        # sempre uma versão também na pasta Casa Physis, com o Physis M&V atualizado (decisão de 18/11/2026)
        sys.path.insert(0, str(RAIZ / "ferramentas" / "documentos"))
        import salvar_casa_physis  # noqa: E402
        salvar_casa_physis.salvar([destino])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


"""Situação de cada módulo (decisão de 15/11/2026): os prontos aparecem no site e na loja; os outros estão em
desenvolvimento, fora do site, mas instalados e usados na Casa Physis; o hardware vai a teste de campo na Fase 2."""
PRONTOS = {"planejador", "sustainkit", "solar", "agua", "monitoramento", "scada", "certificacoes"}
SITUACAO_PRONTO = "Pronto: no site e na loja"
SITUACAO_DEV = "Em desenvolvimento: fora do site, instalado na Casa Physis"
SITUACAO_HW = "Hardware: protótipo, teste de campo na Fase 2"


def situacao_modulo(k: dict) -> str:
    if k["id"] in PRONTOS:
        return SITUACAO_PRONTO
    if k["id"].startswith("hw-"):
        return SITUACAO_HW
    if k["id"] == "servidor":
        return "Infraestrutura: instalação pelo Eric Oliveira (Fase 2)"
    return SITUACAO_DEV


def secoes_por_pessoa(texto: str) -> dict:
    """Separa o memo "Quem faz o quê" em uma parte por pessoa (títulos "## Nome · N tarefas")."""
    out, nome, linhas = {}, None, []
    for l in texto.splitlines():
        m = re.match(r"^## (.+?) · \d+ tarefas?", l)
        if m:
            if nome:
                out[nome] = "\n".join(linhas).strip() + "\n"
            nome, linhas = m.group(1).strip(), [l]
        elif nome:
            linhas.append(l)
    if nome:
        out[nome] = "\n".join(linhas).strip() + "\n"
    return out


def seguro(nome: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def montar_envio(saida: Path, docs: Path, mapa: list, commit: str, hoje: str, rep: Path):
    """00_Envio_por_pessoa/<Pessoa>/ com o LEIA-ME, a parte dela no memo, os kits e os pacotes de módulo dela;
    e o índice de envio (INDICE_DE_ENVIO.md e .ods) com cada página, demo, pacote, módulo, kit e documento."""
    itens = []   # (tipo, item, arquivo, situação, responsáveis, enviar para)
    paginas = {a: (n, o, q) for a, n, o, q in TELAS}
    for f in sorted((saida / "02_Paginas_completas").glob("*.html")):
        if f.name == "index.html":
            continue
        n, o, q = paginas.get(f.name, (f.stem, "", "equipe"))
        itens.append(("Página completa", n, f"02_Paginas_completas/{f.name}",
                      "Só uso interno" if "gestao" in f.name else "Pronta", "Rafaella (revisão)", q))
    for f in sorted((saida / "03_Demos_site").glob("*.html")):
        itens.append(("Demonstração do site", f.stem.replace("physis-demo-", "Demo ").replace("-", " "), f"03_Demos_site/{f.name}",
                      "Pronta · dados simulados", "Rafaella", "site público"))
    for f in sorted((saida / "04_Pacotes_instalacao").glob("*.zip")):
        itens.append(("Pacote de instalação", f.stem.replace("physis-", "").replace("-", " "), f"04_Pacotes_instalacao/{f.name}",
                      "Pronto para instalar (Fase 2)", "Eric Oliveira", "Eric Oliveira"))
    kits = {p.name.split("-2")[0].replace("kit-", ""): p for p in (saida / "06_Kits_revisao").glob("kit-*.zip")}
    for k in mapa:
        mz = next((saida / "05_Modulos").glob(f"modulo-{k['id']}_*.zip"), None)
        if mz:
            itens.append(("Módulo (só leitura)", k["nome"], f"05_Modulos/{mz.name}", situacao_modulo(k),
                          ", ".join(k["responsaveis"]), ", ".join(k["responsaveis"])))
        kz = kits.get(k["id"])
        if kz:
            itens.append(("Kit de revisão (editar e devolver)", k["nome"], f"06_Kits_revisao/{kz.name}", situacao_modulo(k),
                          ", ".join(k["responsaveis"]), ", ".join(k["responsaveis"]) + " → devolve ao Eric Oliveira"))
    for f in sorted((saida / "01_Documentos").glob("*.*")):
        itens.append(("Documento", f.stem.replace("_", " "), f"01_Documentos/{f.name}", "Pronto",
                      "Rafaella", "Eric Oliveira (só o 10)" if f.name.startswith("10_") else "equipe Physis (interno)"))
    for f in sorted((saida / "01_Documentos" / "19_Memos_Fase2").glob("*.md")) if (saida / "01_Documentos" / "19_Memos_Fase2").is_dir() else []:
        itens.append(("Memo da Fase 2", f.stem.replace("_", " "), f"01_Documentos/19_Memos_Fase2/{f.name}", "Pronto", "Rafaella", "equipe Physis (interno)"))
    for pasta, tipo, quem in (("07_Implantacao_e_servicos", "Implantação e serviços", "Eric Oliveira"),
                              ("08_App_nativo", "App nativo", "Rafaella, Eric Oliveira"),
                              ("09_Codigo_fonte", "Código-fonte completo", "Eric Oliveira"),
                              ("10_Gestao_tarefas_Fase2", "Tarefas da Fase 2 para a Gestão", "Rafaella")):
        for f in sorted((saida / pasta).glob("*")):
            if f.is_file():
                itens.append((tipo, f.stem, f"{pasta}/{f.name}", "Pronto", quem, quem))

    # pasta de cada pessoa: o que ela recebe, a parte dela no memo, cópia dos kits e dos módulos dela
    memo = docs / "19_Memos_Fase2" / "11_Quem_faz_o_que.md"
    partes = secoes_por_pessoa(memo.read_text(encoding="utf-8")) if memo.is_file() else {}
    pessoas = sorted({p for k in mapa for p in k["responsaveis"]} | set(partes))
    base = saida / "00_Envio_por_pessoa"
    for p in pessoas:
        alvo = base / seguro(p)
        alvo.mkdir(parents=True, exist_ok=True)
        meus = [k for k in mapa if p in k["responsaveis"]]
        linhas = [f"# Envio para {p} · Sistema Physis · versão {commit} · {hoje}", "",
                  "Tudo nesta pasta é da mesma versão da entrega. Abra primeiro este arquivo.",
                  "O que é o site, a plataforma, a loja, a consultoria e as outras páginas: `00_O_que_e_cada_parte.md`, na raiz da entrega.", ""]
        if meus:
            linhas += ["## Seus módulos", "", "| Módulo | Situação | Kit para revisar e devolver | Cópia só para leitura |", "|---|---|---|---|"]
            for k in meus:
                kz = kits.get(k["id"])
                mz = next((saida / "05_Modulos").glob(f"modulo-{k['id']}_*.zip"), None)
                if kz:
                    shutil.copy2(kz, alvo / kz.name)
                if mz:
                    shutil.copy2(mz, alvo / mz.name)
                linhas.append(f"| {k['nome']} | {situacao_modulo(k)} | {kz.name if kz else '—'} | {mz.name if mz else '—'} |")
            linhas += ["", "Como revisar: abra o kit, siga o LEIA-ME dele, edite só os arquivos editáveis e devolva o kit ao Eric Oliveira, "
                       "que valida e aplica sem mexer na estrutura do sistema.", ""]
        if p == "Eric Oliveira":
            linhas += ["## Instalação e servidor", "", "- Pacotes de cada cliente e do servidor: `04_Pacotes_instalacao/`",
                       "- Implantação e serviços abertos: `07_Implantacao_e_servicos/`", "- Código-fonte completo: `09_Codigo_fonte/`",
                       "- Lista para detalhar o servidor (a única que sai para fora): `01_Documentos/10_Perguntas_Eric_Infraestrutura.md`", ""]
        if p == "Rafaella":
            linhas += ["## Gestão", "", "- Tarefas da Fase 2 para importar na Gestão: `10_Gestao_tarefas_Fase2/`",
                       "- Todas as páginas: `02_Paginas_completas/index.html` · demos do site: `03_Demos_site/`", ""]
        if p in partes:
            (alvo / "Minhas_tarefas_Fase2.md").write_text(partes[p], encoding="utf-8")
            linhas += ["## Suas tarefas da Fase 2", "", "Estão em `Minhas_tarefas_Fase2.md`, nesta pasta (tiradas do memo \"Quem faz o quê\").", ""]
        (alvo / "LEIA-ME.md").write_text("\n".join(linhas), encoding="utf-8")
        itens.append(("Pasta de envio por pessoa", p, f"00_Envio_por_pessoa/{seguro(p)}/", "Pronta", p, p))

    (saida / "00_O_que_e_cada_parte.md").write_text(PARTES.format(commit=commit, hoje=hoje), encoding="utf-8")
    itens.append(("Explicação", "O que é cada parte (site, plataforma, loja, consultoria e outras páginas)",
                  "00_O_que_e_cada_parte.md", "Pronto", "Rafaella", "equipe Physis"))

    cab = ["Nº", "Tipo", "Item", "Arquivo", "Situação", "Responsáveis", "Enviar para"]
    linhas = [f"# Índice de envio · Sistema Physis · versão {commit} · {hoje}", "",
              "Cada item da entrega, com a situação e para quem vai. Comece por `00_Envio_por_pessoa/<seu nome>/LEIA-ME.md`.",
              f"Módulos: **{SITUACAO_PRONTO}** · **{SITUACAO_DEV}** · **{SITUACAO_HW}**.", "",
              "| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    for i, it in enumerate(itens, 1):
        linhas.append("| " + " | ".join([str(i)] + [str(x).replace("|", "/") for x in it]) + " |")
    (saida / "00_INDICE_DE_ENVIO.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    try:   # a mesma tabela em planilha aberta (.ods), pelo gerador do próprio sistema
        sys.path.insert(0, str(rep / "physis-hub"))
        from physis_hub import documentos
        dados = documentos.ods(f"Índice de envio {commit}", [{"nome": "Envio", "cab": cab,
                                                              "linhas": [[str(i)] + list(it) for i, it in enumerate(itens, 1)]}])
        (saida / "00_INDICE_DE_ENVIO.ods").write_bytes(dados)
    except Exception as exc:  # noqa: BLE001 — o .md continua valendo
        print("índice .ods não gerado:", exc)


PARTES = """# O que é cada parte do Sistema Physis · versão {commit} · {hoje}

Situação dos módulos (decisão de 15/11/2026): **pronto** = no site e na loja; **em desenvolvimento** = fora do site,
instalado e usado na Casa Physis; **hardware** = protótipo, teste de campo na Fase 2.

## Site público
Porta de entrada da Physis. Apresenta a empresa, os serviços e as demonstrações (Planejador, SustainKit, SCADA,
Monitoramento e Cliente, marcadas "Demonstração · dados simulados") e a página "Baixar o app". Mostra só módulos prontos.
Responsável: Rafaella (bloco 7: site, loja, marketing, gestão e editais). Arquivos: `03_Demos_site/`, `02_Paginas_completas/baixar-o-app.html`.

## Plataforma
O sistema que o cliente usa: mapear → modelar → checar → documentar. Abas dos módulos comprados, "Baixar esta tela"
(Documento .odt, PDF, Planilha .ods) e preferências (acessibilidade, conforto, inglês, claro/escuro). Sem servidor, abre em
demonstração; na Casa Physis mostra todas as telas, com as em desenvolvimento marcadas. Cada aba fica com o responsável do
módulo; revisão geral das telas: Rafaella. Arquivo: `02_Paginas_completas/site-loja-e-plataforma.html`.

## Loja
No mesmo arquivo da plataforma. Módulos, kits de hardware e cursos. Vende só o que está pronto (Planejador, SustainKit,
Solar, Água, Monitoramento, SCADA, Gestão, Certificação); "Experimente agora" abre a demonstração. Item novo: a equipe grava,
revisa e publica; item em desenvolvimento nunca vai ao público. Em aberto: preço de Solar e Certificação; pagamento real
(Pix e boleto) depende do provedor. Responsável: Rafaella.

## Consultoria
Página própria: serviços, fases, consultoria personalizada com equipe multidisciplinar, diárias, casos e pedido de proposta.
Revisão: Leonardo Macedo e Rafaella. Arquivo: `02_Paginas_completas/consultoria.html`.

## Gestão interna (só equipe Physis)
| Área | O que tem | Quem cuida (Fase 2) |
|---|---|---|
| Propostas e contratos | Modelos de proposta e contrato, pedido de proposta da consultoria | Rafaella, Laura, Arthur |
| Financeiro | Contas, entradas e saídas, investimentos | Rafaella |
| Fornecedores e compras | Cadastro e compras de equipamentos e materiais | Ryan, Arthur, Erick Lopes, Rafael, Emerson |
| Central de clientes e chamados | Clientes, chamados de suporte, resposta por e-mail e WhatsApp | Arthur, Rafaella, Erick Lopes, Rafael |
| Cursos e turmas | Cursos, carga horária, turmas, inscritos e concluintes | Rafaella, Laura |
| Equipe e contas | Contas da equipe (vindas do servidor), convites e 2 etapas | Rafaella |
| Parceiros | Profissionais parceiros, curadoria e pedidos de orçamento | Rafaella (curadoria), Eric Oliveira (servidor) |
| Plano de ação | Tarefas da Fase 2 por bloco e por pessoa (importadas de `10_Gestao_tarefas_Fase2/`) | Rafaella |

## Editais
Aba da Gestão: fontes de editais, triagem, resumo e encaixe com a Physis, montagem e envio das propostas.
| Etapa | Quem |
|---|---|
| Acesso aos editais | Rafaella, Erick Lopes, Marzia |
| Conferir cada fonte marcada "a conferir" e fazer a triagem | toda a equipe |
| Montar as propostas | Rafaella, Marzia, Erick Lopes |
| Aprovação final e envio | Rafaella, Laura, Arthur, Erick Lopes, Marzia |
Robô de editais (resumo e encaixe): com a IA (Claude, conta da Physis) desde a Fase 1; sempre sugestão para revisão humana.

## Marketing
Aba da Gestão: posts, artigos, roteiros de vídeo, enquete de segunda e métricas.
| Etapa | Quem |
|---|---|
| Produzir posts, artigos e roteiros de vídeo | Rafaella, Marzia |
| Aprovar antes de publicar | Rafaella, Marzia |
| Enquete de segunda | automática pelo sistema, com coleta de dados pela IA |
| Acompanhar as métricas | Rafaella, Marzia |
| Cadastrar os links dos modelos do Canva na Gestão | Rafaella, Marzia, Laura |

## Loja (tarefas)
| Etapa | Quem |
|---|---|
| Revisar e publicar os módulos prontos, com preço e situação | Rafaella, Marzia, Laura, Arthur |
| Trocar os marcadores da consultoria (diárias, prazo de resposta, resultados dos casos) | Rafaella |
| Revisar as páginas da consultoria (textos, serviços, casos, inglês, modo escuro, acessibilidade) | Leonardo Macedo, Rafaella |
| Provedor de pagamento (Pix e boleto) e nota fiscal: recomendação em `01_Documentos/21_Pagamento_Provedor_e_Integracao.md`; ligar na Fase 2 | Rafaella (decisão), Eric Oliveira (integração) |
Preços decididos em 15/11/2026: Solar a partir de R$ 300,00; cada certificação é um módulo, a partir de R$ 750,00;
consultoria personalizada a partir de R$ 5.000,00. Os demais itens ficam "sob consulta" até a direção definir.

## Outras páginas
| Página | O que é | Para quem |
|---|---|---|
| Gestão interna | Atividades, propostas, contratos, financeiro, editais, eventos, marketing, e-mails, chamados, parceiros | só a equipe Physis |
| SCADA · supervisório | Bombas, válvulas e energia, histórico e balanço de carbono do cliente | operação |
| Painel municipal | Chuva medida, alertas por bairro, rio e risco | Defesa Civil e prefeituras |
| Documento para comentários | Relatórios para revisão com comentários por parágrafo | equipe e revisores convidados |
| Baixar o app | App Android e iPhone | clientes |

Todas abrem por `02_Paginas_completas/index.html`.
"""


TELAS = [  # arquivo, nome, o que faz, para quem
    ("site-loja-e-plataforma.html", "Site, loja e plataforma", "A plataforma completa (mapear → modelar → checar → documentar) com a loja; abre em modo de demonstração quando aberta como arquivo.", "clientes e equipe"),
    ("consultoria.html", "Consultoria", "Serviços, fases, consultoria personalizada com equipe multidisciplinar, diárias, casos e pedido de proposta.", "site público"),
    ("planejador.html", "Planejador", "Terreno, GIS, BIM, relevo, APP e normas por bloco. Mapa e BIM completos só com o servidor.", "clientes e equipe"),
    ("sustainkit.html", "SustainKit", "Diagnóstico por blocos: energia, solar, água, resíduos, carbono, certificações, custos.", "clientes e equipe"),
    ("scada-supervisorio.html", "SCADA · supervisório", "Supervisão e controle de bombas, válvulas e energia, com histórico.", "operação"),
    ("gestao-interna.html", "Gestão interna Physis", "Atividades, propostas, contratos, financeiro, editais, eventos, marketing, e-mails, chamados, parceiros.", "só equipe Physis"),
    ("painel-municipal.html", "Painel municipal de resiliência", "Chuva medida, alertas por bairro, rio e risco para Defesa Civil e prefeituras.", "municípios"),
    ("documento-para-comentarios.html", "Documento para comentários", "Relatórios publicados para revisão com comentários por parágrafo.", "equipe e revisores"),
    ("baixar-o-app.html", "Baixar o app", "App para Android e iPhone, APK direto e instalação pelo navegador.", "clientes"),
]


def capa(arquivos, commit, hoje):
    import html as h
    cards = "".join(f'<a class="c" href="{h.escape(a)}"><strong>{h.escape(n)}</strong><span>{h.escape(o)}</span><em>{h.escape(q)}</em></a>'
                    for a, n, o, q in TELAS if a in arquivos)
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sistema Physis · todas as telas</title><style>
:root{{--f:#F4F6F1;--s:#fff;--t:#1C2B21;--t2:#4A5446;--v:#33512F;--l:#C9D2C4}}
@media (prefers-color-scheme:dark){{:root{{--f:#141B16;--s:#1C2620;--t:#E6EDE4;--t2:#B3C0AF;--v:#9CCB92;--l:#334236}}}}
body{{margin:0;background:var(--f);color:var(--t);font:16px/1.5 Lexend,system-ui,sans-serif}}
main{{max-width:1000px;margin:0 auto;padding:24px 16px}}h1{{font:600 2rem/1.2 Fraunces,Georgia,serif;color:var(--v);margin:0 0 6px}}
p{{color:var(--t2)}}.g{{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}}
.c{{display:grid;gap:6px;padding:16px;border:1px solid var(--l);border-radius:10px;background:var(--s);color:var(--t);text-decoration:none}}
.c:hover,.c:focus-visible{{border-color:var(--v);outline:3px solid var(--v);outline-offset:2px}}.c strong{{color:var(--v);font-size:1.1rem}}
.c span{{color:var(--t2)}}.c em{{font-style:normal;font-size:.85rem;color:var(--t2)}}</style></head><body><main>
<h1>Sistema Physis · todas as telas</h1><p>Fase 1 · versão {commit} · {hoje}. Cada cartão abre a página correspondente. As demonstrações do site estão na pasta 03_Demos_site.</p>
<div class="g">{cards}</div></main></body></html>"""


LEIA = """# Entrega do Sistema Physis · versão {commit} · {hoje}

Tudo nesta pasta é a **mesma versão** ({commit}). A conferência de cada arquivo (SHA-256) está em `MANIFESTO.json`. São {n} arquivos.

**Para enviar aos colegas:** cada pessoa recebe a sua pasta em `00_Envio_por_pessoa/` (LEIA-ME, tarefas, kits e módulos dela).
O índice de tudo, com a situação de cada item e para quem vai, está em `00_INDICE_DE_ENVIO.md` (e `.ods`).
Uma cópia desta pasta inteira em ZIP fica em `_backup_arquivos/`.

| Pasta | O que é | Para quem |
|---|---|---|
| 00_Envio_por_pessoa | Uma pasta por pessoa: o que enviar a cada colega | Cada pessoa |
| 01_Documentos | Documentos iniciais (00 a 2x) e memos da Fase 2 (um por bloco e "Quem faz o quê") | Equipe toda. Só a lista do Eric (10) sai para fora. |
| 02_Paginas_completas | Site com loja e plataforma, consultoria, Gestão interna, SCADA, SustainKit, Planejador, painel municipal, documento para comentários, página do app | Equipe (Gestão interna: só uso interno) |
| 03_Demos_site | Versões reduzidas para o site, com "Demonstração · dados simulados" | Site público |
| 04_Pacotes_instalacao | Pacote de cada cliente e do servidor da Physis | Eric (instalação) |
| 05_Modulos | Código, dados, manuais e testes de cada módulo, só leitura | Responsáveis dos módulos |
| 06_Kits_revisao | {nkits} kits para revisar e devolver (LEIA-ME, editáveis, prévia, ficha) | Cada responsável; o Eric valida e aplica |
| 07_Implantacao_e_servicos | Instalador do Raspberry Pi e mini PC, backup, serviços abertos | Eric |
| 08_App_nativo | Projeto do app Android e iPhone e página de download | Rafaella, Eric |
| 09_Codigo_fonte | Repositório completo desta versão | Eric |
| 10_Gestao_tarefas_Fase2 | Arquivo para importar na Gestão (Plano de ação → Importar → Substituir) | Rafaella |
| 11_Metodologia_e_Modelagem | Documentação técnica (metodologia, simulação, mapeamento, variáveis, IA, documentos, fornecedores, suporte), bases e premissas, exemplos de modelos e as páginas de conferência | Equipe toda |

Nenhum banco de teste, senha, chave ou arquivo `.env` vai nesta entrega.
"""

if __name__ == "__main__":
    main()
