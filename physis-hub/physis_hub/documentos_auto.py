"""Documentos automáticos: modelos → rascunho → revisão → aprovação → emissão. Só biblioteca padrão.

Decisões de 15/11/2026 (docs/DOCUMENTOS_AUTOMATICOS.md):
  * Emissão a partir de MODELOS (ODT ou Markdown) com as marcações dos sites: {{campo}} é preenchido com os dados do
    sistema (compra da loja, cliente, preços, pedido de consultoria); [MARCADOR: …] fica para a pessoa completar.
    Campo sem dado vira [MARCADOR: campo] — nada é inventado.
    Pastas de modelos, nesta ordem: PHYSIS_MODELOS_PASTA (os modelos reais que a equipe mandar, no servidor) e
    physis-hub/modelos/ (modelos de partida do repositório).
  * NF: o sistema monta os DADOS da nota (tomador, itens, valor); a emissão de fato é do provedor de pagamento/NF
    (doc 21: Asaas recomendado) — Fase 2. O ponto de encaixe é EmissorNF (adaptador).
  * Projetos personalizados e editais: biblioteca de documentos parecidos (pasta + índice SQLite), busca BM25 no
    texto + tipo, setor e porte; a IA (Claude, sem dados pessoais) adapta o mais parecido ao pedido novo → rascunho.
  * Relatório formal por módulo: cada módulo tem o seu modelo (modelos/relatorios/<modulo>.md); um relatório de
    vários módulos junta os modelos na ordem das abas da plataforma. "Baixar esta tela" continua como está.
  * Manual por compra: só os módulos comprados (modelos/manual/), nas seções do manual da Santa Clara.
  * TODO documento passa por rascunho → em_revisao → aprovado (direção, com quem e quando) → emitido. Sem aprovação,
    a emissão é recusada. Mudar um documento aprovado devolve para revisão. Cada passo vai para o registro encadeado.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import io
import json
import math
import os
import re
import secrets
import zipfile
from collections import Counter
from pathlib import Path

from . import documentos as odf
from . import seguranca as seg

RAIZ = Path(__file__).resolve().parent.parent
MODELOS_REPO = RAIZ / "modelos"
REPO = RAIZ.parent

ESTADOS = ("rascunho", "em_revisao", "aprovado", "emitido")
TIPOS = ("proposta", "contrato", "nf", "consultoria", "relatorio", "manual", "adaptado", "livre")
TEXTO_MAX = 400_000
_ID = re.compile(r"^[A-Za-z0-9_-]{12,40}$")
_CAMPO = re.compile(r"\{\{\s*([A-Za-z0-9_.\-]+)\s*\}\}")
_MARCADOR = re.compile(r"\[MARCADOR(?::\s*([^\]]*))?\]")

# Ordem das abas da plataforma (web/painel.html, const ABAS) e o módulo de cada aba
ORDEM_ABAS = ("planejador", "sustainkit", "solar", "avac", "servidor-verde", "turbinas", "agua", "sbn", "circular", "carbono",
              "resiliencia", "zonas", "campo", "secador", "animais", "saude", "supervisao", "resumo", "certificacoes", "gestao", "cursos")
ABA_DO_MODULO = {"monitoramento": "campo", "coleiras": "animais", "comedouros": "animais", "medicamentos": "saude",
                 "pulseira": "saude", "scada": "supervisao", "equipamentos": "avac", "painel": "resumo", "acessibilidade": "resumo"}
APELIDOS_MODULO = {"scada": "supervisao", "campo": "monitoramento", "coleiras": "animais", "comedouros": "animais",
                   "medicamentos": "saude", "pulseira": "saude"}
# Módulos à venda na loja (web/painel.html, LOJA_VENDA → hub.ITEM_MODULOS): os que têm seção própria no manual
VENDAVEIS = ("monitoramento", "planejador", "solar", "agua", "sustainkit", "certificacoes", "supervisao", "gestao")
NOMES_PADRAO = {"monitoramento": "Monitoramento verde", "supervisao": "SCADA", "agua": "Qualidade da água", "gestao": "Gestão",
                "sustainkit": "SustainKit", "solar": "Energia solar", "planejador": "Planejador", "certificacoes": "Certificações",
                "animais": "Animais", "saude": "Saúde", "zonas": "Caixinha Physis IoT", "cursos": "Cursos"}
# Seções do manual (estrutura do manual da Fazenda Santa Clara)
SECOES_MANUAL = (("como-validar", "Como validar"), ("apresentacao", "Apresentação"), ("primeiro-acesso", "Primeiro acesso"),
                 ("as-telas", "As telas"), ("equipamentos", "Equipamentos"), ("alertas", "Alertas"), ("rotina", "Rotina"),
                 ("seguranca", "Segurança"), ("pontos-em-aberto", "Pontos em aberto"))


# ══════════════════════════ modelos e marcações ══════════════════════════
def pastas_modelos() -> list[Path]:
    p = (os.environ.get("PHYSIS_MODELOS_PASTA") or "").strip()
    return ([Path(p)] if p else []) + [MODELOS_REPO]


def achar_modelo(rel: str) -> Path | None:
    """Primeiro arquivo que existir: pasta do servidor antes da do repositório; .odt antes de .md."""
    rel = rel.strip("/").replace("\\", "/")
    if ".." in rel.split("/"):
        return None
    for pasta in pastas_modelos():
        for ext in (".odt", ".md"):
            arq = pasta / (rel + ext)
            if arq.is_file():
                return arq
    return None


def nomes_modulos() -> dict:
    nomes = dict(NOMES_PADRAO)
    try:
        d = json.loads((REPO / "ferramentas" / "kits" / "modulos.json").read_text(encoding="utf-8"))
        for m in d.get("modulos") or []:
            if m.get("tipo") == "modulo" and m.get("id") and m.get("nome"):
                nomes.setdefault(APELIDOS_MODULO.get(m["id"], m["id"]), m["nome"])
    except (OSError, ValueError):
        pass
    return nomes


def normalizar_modulos(modulos) -> list[str]:
    """Ids da loja/plataforma/kits → ids de modelo, sem repetir, na ordem das abas."""
    vistos: list[str] = []
    for m in modulos or []:
        m = APELIDOS_MODULO.get(str(m).strip(), str(m).strip())
        if m and re.fullmatch(r"[a-z0-9-]{2,40}", m) and m not in vistos:
            vistos.append(m)
    aba = lambda m: ABA_DO_MODULO.get(m, m)
    return sorted(vistos, key=lambda m: (ORDEM_ABAS.index(aba(m)) if aba(m) in ORDEM_ABAS else len(ORDEM_ABAS), vistos.index(m)))


def _valor(dados: dict, caminho: str):
    """Campo com id do mapa de variáveis (ex.: "agua.leituras") vale direto; senão, caminho por pontos."""
    if isinstance(dados, dict) and caminho in dados:
        return dados[caminho]
    v = dados
    for parte in caminho.split("."):
        if isinstance(v, dict) and parte in v:
            v = v[parte]
        else:
            return None
    return v


def brl(v) -> str:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return ""
    s = f"{abs(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if n < 0 else "") + "R$ " + s


def _texto_valor(v) -> str | None:
    if v is None or v == "" or v == []:
        return None
    if isinstance(v, bool):
        return "sim" if v else "não"
    if isinstance(v, float):
        return f"{v:.2f}".replace(".", ",")
    if isinstance(v, (list, tuple)):
        return ", ".join(str(x) for x in v if x not in (None, ""))
    return str(v)


def preencher(texto: str, dados: dict) -> tuple[str, list[str]]:
    """{{campo}} → valor; sem valor → [MARCADOR: campo]. Devolve o texto e a lista do que ficou pendente."""
    def troca(m):
        v = _texto_valor(_valor(dados, m.group(1)))
        return v if v is not None else f"[MARCADOR: {m.group(1)}]"
    t = _CAMPO.sub(troca, texto or "")
    return t, pendencias(t)


def pendencias(texto: str) -> list[str]:
    vistos: list[str] = []
    for m in _MARCADOR.finditer(texto or ""):
        p = (m.group(1) or "").strip() or "(sem descrição)"
        if p not in vistos:
            vistos.append(p)
    return vistos


def _xml(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def preencher_odt(modelo: bytes, dados: dict) -> tuple[bytes, str, list[str]]:
    """Preenche {{campo}} dentro do content.xml/styles.xml de um modelo ODT. Marcação partida por estilo no meio
    (ex.: {{cli<span>ente}}) não é achada: fica como está e aparece na revisão. Devolve (odt, texto puro, pendências)."""
    entrada = zipfile.ZipFile(io.BytesIO(modelo))
    saida = io.BytesIO()
    texto_puro = ""
    with zipfile.ZipFile(saida, "w") as z:
        for info in entrada.infolist():
            dados_arq = entrada.read(info.filename)
            if info.filename in ("content.xml", "styles.xml"):
                xml = dados_arq.decode("utf-8")
                xml = _CAMPO.sub(lambda m: _xml(_texto_valor(_valor(dados, m.group(1))) or f"[MARCADOR: {m.group(1)}]"), xml)
                dados_arq = xml.encode("utf-8")
                if info.filename == "content.xml":
                    texto_puro = re.sub(r"\s+\n", "\n", re.sub(r"<text:(p|h)[^>]*>", "\n", xml))
                    texto_puro = re.sub(r"<[^>]+>", "", texto_puro).replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&").strip()
            novo = zipfile.ZipInfo(info.filename, info.date_time)
            novo.compress_type = zipfile.ZIP_STORED if info.filename == "mimetype" else zipfile.ZIP_DEFLATED
            z.writestr(novo, dados_arq)
    return saida.getvalue(), texto_puro, pendencias(texto_puro)


def texto_de_odt(odt: bytes) -> str:
    try:
        xml = zipfile.ZipFile(io.BytesIO(odt)).read("content.xml").decode("utf-8", "replace")
    except (zipfile.BadZipFile, KeyError):
        return ""
    xml = re.sub(r"<text:(p|h)[^>]*>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml).replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").strip()


def md_para_blocos(texto: str) -> tuple[str, list[dict]]:
    """Markdown simples → (título, blocos do documentos.odt): #, ##, ###, listas, tabelas com |, parágrafos."""
    titulo, blocos, tabela = "", [], None
    def fechar_tabela():
        nonlocal tabela
        if tabela:
            blocos.append({"tabela": {"cab": tabela[0], "linhas": tabela[1:]}})
        tabela = None
    for linha in (texto or "").replace("\r\n", "\n").split("\n"):
        s = linha.strip()
        if s.startswith("|") and s.endswith("|"):
            cel = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cel if c):
                continue
            tabela = (tabela or []) + [cel]
            continue
        fechar_tabela()
        if not s:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", s)
        if m:
            if len(m.group(1)) == 1 and not titulo:
                titulo = m.group(2).strip()
            else:
                blocos.append({"h": max(1, len(m.group(1)) - 1), "t": m.group(2).strip()})
        elif re.match(r"^[-*]\s+", s):
            blocos.append({"t": re.sub(r"^[-*]\s+", "", s), "lista": True})
        elif re.match(r"^\d+[.)]\s+", s):
            blocos.append({"t": re.sub(r"^\d+[.)]\s+", "", s), "lista": "ol"})
        elif s.startswith(">"):
            blocos.append({"t": s.lstrip("> ").strip()})
        else:
            blocos.append({"t": re.sub(r"\*\*(.+?)\*\*", r"\1", s)})
    fechar_tabela()
    return titulo, blocos


def secoes_md(texto: str) -> dict[str, str]:
    """Texto por seção de nível 2 (## Título) → {slug: texto}. Usado no manual e nos relatórios."""
    out: dict[str, list[str]] = {}
    atual = "_inicio"
    for linha in (texto or "").replace("\r\n", "\n").split("\n"):
        m = re.match(r"^##\s+(.*)", linha)
        if m and not linha.startswith("###"):
            atual = _slug(m.group(1))
            out.setdefault(atual, [])
            continue
        out.setdefault(atual, []).append(linha)
    return {k: "\n".join(v).strip() for k, v in out.items()}


def _slug(s: str) -> str:
    import unicodedata
    s = "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _ler_md(rel: str) -> str | None:
    arq = achar_modelo(rel)
    if arq is None or arq.suffix != ".md":
        return None
    return arq.read_text(encoding="utf-8")


# ══════════════════════════ dados do sistema ══════════════════════════
def _md_tabela(cab: list[str], linhas: list[list]) -> str:
    if not linhas:
        return "[MARCADOR: itens]"
    t = "| " + " | ".join(cab) + " |\n|" + "|".join("---" for _ in cab) + "|\n"
    return t + "\n".join("| " + " | ".join(str(c if c not in (None, "") else "[MARCADOR]") for c in l) + " |" for l in linhas)


def dados_da_compra(compra: dict, numero: str = "", hoje: str = "") -> dict:
    """Compra da loja (central tipo 'compra', formato physis-compra/1) → campos dos modelos."""
    c = compra if isinstance(compra, dict) else {}
    pag = c.get("pagador") if isinstance(c.get("pagador"), dict) else {}
    itens = [i for i in (c.get("itens") or []) if isinstance(i, dict)]
    linhas = [[i.get("d") or i.get("nome") or i.get("descricao") or "", _texto_valor(i.get("qtd")) or "",
               brl(i.get("unit")) if i.get("unit") is not None else "", brl(i.get("total")) if i.get("total") is not None else ""]
              for i in itens]
    nomes = nomes_modulos()
    mods = normalizar_modulos(c.get("modulos") or [])
    return {
        "hoje": hoje or _dt.date.today().strftime("%d/%m/%Y"),
        "cliente": {"nome": pag.get("nome"), "documento": pag.get("doc") or pag.get("cpf") or pag.get("cnpj"),
                    "email": pag.get("email"), "telefone": pag.get("telefone"), "endereco": pag.get("endereco")},
        "pedido": {"numero": c.get("numero") or numero, "recibo": c.get("recibo"), "data": c.get("data"), "fatura": c.get("fatura"),
                   "forma": c.get("forma"), "total": brl(c.get("total")) if c.get("total") is not None else None,
                   "anual": brl(c.get("anual")) if c.get("anual") else None,
                   "modulos": ", ".join(nomes.get(m, m) for m in mods) or None},
        "itens_tabela": _md_tabela(["Item", "Qtd.", "Unitário", "Total"], linhas),
        "_itens": itens, "_modulos": mods,
    }


def dados_do_pedido(pedido: dict, numero: str = "", hoje: str = "") -> dict:
    """Pedido de projeto personalizado / consultoria (central tipo 'pedido') → campos dos modelos."""
    p = pedido if isinstance(pedido, dict) else {}
    cont = p.get("contato") if isinstance(p.get("contato"), dict) else p.get("pagador") if isinstance(p.get("pagador"), dict) else {}
    return {
        "hoje": hoje or _dt.date.today().strftime("%d/%m/%Y"),
        "cliente": {"nome": cont.get("nome") or p.get("nome"), "documento": cont.get("doc") or cont.get("cpf") or cont.get("cnpj"),
                    "email": cont.get("email") or p.get("email"), "telefone": cont.get("telefone") or p.get("telefone"),
                    "organizacao": p.get("org") or p.get("organizacao") or cont.get("org")},
        "pedido": {"numero": p.get("numero") or numero, "setor": p.get("setor"), "porte": p.get("porte"),
                   "descricao": p.get("descricao") or p.get("mensagem") or p.get("texto"), "prazo": p.get("prazo"),
                   "local": p.get("municipio") or p.get("local"), "modulos": ", ".join(normalizar_modulos(p.get("modulos") or [])) or None},
    }


# ══════════════════════════ NF: dados agora, emissão no provedor (Fase 2) ══════════════════════════
def dados_nf(compra: dict, numero: str = "", hoje: str = "") -> dict:
    """Dados da nota de serviço a partir da compra. O que é do prestador (CNPJ, inscrição municipal, código de
    serviço, alíquota) vem da configuração do servidor (PHYSIS_NF_*), nunca do código: sem ela, [MARCADOR]."""
    d = dados_da_compra(compra, numero, hoje)
    env = os.environ.get
    d["prestador"] = {"razao_social": env("PHYSIS_NF_RAZAO_SOCIAL"), "cnpj": env("PHYSIS_NF_CNPJ"),
                      "inscricao_municipal": env("PHYSIS_NF_INSCRICAO_MUNICIPAL"), "municipio": env("PHYSIS_NF_MUNICIPIO")}
    d["servico"] = {"codigo": env("PHYSIS_NF_CODIGO_SERVICO"), "aliquota_iss": env("PHYSIS_NF_ALIQUOTA_ISS"),
                    "descricao": "; ".join(str(i.get("d") or i.get("nome") or "") for i in d["_itens"] if i.get("d") or i.get("nome")) or None}
    d["nf"] = {"valor_total": d["pedido"]["total"], "competencia": (hoje or _dt.date.today().strftime("%d/%m/%Y"))[3:]}
    return d


class EmissorNF:
    """Ponto de encaixe do provedor de NF (Fase 2). emitir(dados) → {"ok", "numero"?, "link"?, "pendente"?, "erro"?}."""
    nome = "manual"

    def emitir(self, dados: dict) -> dict:
        return {"ok": True, "pendente": True, "provedor": self.nome,
                "mensagem": "Emissão automática da NF é Fase 2: emitir no provedor com os dados aprovados e anexar o número."}


class EmissorAsaas(EmissorNF):
    """Fase 2: provedor recomendado no doc 21. Chave em PHYSIS_ASAAS_CHAVE (servidor), nunca no código."""
    nome = "asaas"

    def emitir(self, dados: dict) -> dict:          # pragma: no cover — Fase 2
        raise NotImplementedError("Fase 2: integração com o Asaas ainda não feita (docs/DOCUMENTOS_AUTOMATICOS.md)")


def emissor_nf_do_ambiente() -> EmissorNF:
    return EmissorAsaas() if os.environ.get("PHYSIS_NF_PROVEDOR") == "asaas" else EmissorNF()


# ══════════════════════════ composição: documentos, relatórios e manuais ══════════════════════════
def compor_documento(tipo: str, dados: dict) -> dict:
    """Modelo do tipo (modelos/documentos/<tipo>) preenchido. {"texto", "odt" (bytes ou None), "pendencias", "modelo"}."""
    arq = achar_modelo(f"documentos/{tipo}")
    if arq is None:
        texto = f"# {tipo.capitalize()}\n\n[MARCADOR: modelo de {tipo} ainda não enviado pela equipe]"
        return {"texto": texto, "odt": None, "pendencias": pendencias(texto), "modelo": None}
    if arq.suffix == ".odt":
        odt_bytes, texto, pend = preencher_odt(arq.read_bytes(), dados)
        return {"texto": texto, "odt": odt_bytes, "pendencias": pend, "modelo": arq.name}
    texto, pend = preencher(arq.read_text(encoding="utf-8"), dados)
    return {"texto": texto, "odt": None, "pendencias": pend, "modelo": arq.name}


def compor_relatorio(modulos, dados: dict, titulo: str = "") -> dict:
    """Relatório formal de um ou mais módulos: capa + o modelo de cada módulo (na ordem das abas) + fecho."""
    mods = normalizar_modulos(modulos)
    nomes = nomes_modulos()
    partes = [_ler_md("relatorios/_capa") or "# Relatório Physis\n\n{{cliente.nome}} · {{hoje}}"]
    usados = []
    for m in mods:
        t = _ler_md(f"relatorios/{m}")
        if t is None:
            t = f"## {nomes.get(m, m)}\n\n[MARCADOR: modelo de relatório do módulo {m} ainda não escrito]"
        partes.append(t)
        usados.append(m)
    partes.append(_ler_md("relatorios/_fecho") or "## Responsável técnico\n\n[MARCADOR: nome, registro profissional e assinatura]")
    base = dict(dados or {})
    base.setdefault("relatorio", {})
    if titulo:
        base["relatorio"] = dict(base["relatorio"], titulo=titulo)
    base["relatorio"].setdefault("modulos", ", ".join(nomes.get(m, m) for m in usados))
    texto, pend = preencher("\n\n".join(partes), base)
    return {"texto": texto, "pendencias": pend, "modulos": usados}


def compor_manual(modulos, dados: dict) -> dict:
    """Manual da compra: as seções da Santa Clara, com a parte comum e a de cada módulo comprado (ordem das abas).
    Toda compra leva primeiro acesso, segurança e LGPD, alertas dos módulos, rotina e pontos em aberto."""
    mods = normalizar_modulos(modulos)
    nomes = nomes_modulos()
    comum = secoes_md(_ler_md("manual/comum") or "")
    por_mod = {m: secoes_md(_ler_md(f"manual/modulos/{m}") or "") for m in mods}
    linhas = [comum.get("_inicio") or "# Manual da plataforma Physis"]
    for slug, nome in SECOES_MANUAL:
        linhas.append(f"## {nome}")
        if comum.get(slug):
            linhas.append(comum[slug])
        for m in mods:
            sec = por_mod[m].get(slug)
            if sec:
                linhas.append(f"### {nomes.get(m, m)}\n\n{sec}")
            elif slug in ("as-telas", "alertas", "rotina") and not por_mod[m]:
                linhas.append(f"### {nomes.get(m, m)}\n\n[MARCADOR: seção \"{nome}\" do manual do módulo {m} ainda não escrita]")
    base = dict(dados or {})
    base.setdefault("manual", {})
    base["manual"] = dict(base["manual"], modulos=", ".join(nomes.get(m, m) for m in mods) or "plataforma básica (Início e Cursos)")
    texto, pend = preencher("\n\n".join(linhas), base)
    return {"texto": texto, "pendencias": pend, "modulos": mods}


def odt_de_texto(texto: str, titulo_padrao: str = "Documento Physis", quando=None, rascunho: bool = False) -> bytes:
    titulo, blocos = md_para_blocos(texto)
    titulo = titulo or titulo_padrao
    if rascunho:
        blocos.insert(0, {"t": "RASCUNHO — documento ainda não emitido (precisa de revisão e aprovação)."})
    return odf.odt(titulo, blocos, quando=quando)


# ══════════════════════════ biblioteca de documentos parecidos (BM25) ══════════════════════════
_PARADAS = set("""a o e é de da do das dos em no na nos nas um uma uns umas para por com sem que se ao aos à às como mais
menos ou ser ter tem foi são está isso esse essa este esta pelo pela pelos pelas sobre entre até também já não sim""".split())


def _termos(t: str) -> list[str]:
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", t or "") if unicodedata.category(c) != "Mn").lower()
    out = []
    for w in re.findall(r"[a-z0-9]+", t):
        if len(w) < 3 or w in _PARADAS or w.isdigit():
            continue
        out.append(w[:-1][:8] if len(w) > 4 and w.endswith("s") else w[:8])
    return out


def bm25(consulta: str, textos: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    docs = [Counter(_termos(t)) for t in textos]
    n = len(docs)
    if not n:
        return []
    media = sum(sum(d.values()) for d in docs) / n or 1.0
    df = Counter(w for d in docs for w in d)
    q = _termos(consulta)
    notas = []
    for d in docs:
        tam = sum(d.values()) or 1
        s = 0.0
        for w in q:
            f = d.get(w, 0)
            if f:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * tam / media))
        notas.append(s)
    return notas


TABELAS = """
CREATE TABLE IF NOT EXISTS docauto (
  id TEXT PRIMARY KEY, tipo TEXT NOT NULL, titulo TEXT NOT NULL, estado TEXT NOT NULL, texto TEXT NOT NULL,
  arquivo BLOB, dados TEXT NOT NULL DEFAULT '{}', pendencias TEXT NOT NULL DEFAULT '[]', origem TEXT NOT NULL DEFAULT '',
  modelo TEXT NOT NULL DEFAULT '', ia TEXT NOT NULL DEFAULT '', versao INTEGER NOT NULL DEFAULT 1, resumo TEXT NOT NULL,
  criado_por TEXT NOT NULL, criado_em REAL NOT NULL, atualizado_em REAL NOT NULL,
  enviado_por TEXT, enviado_em REAL, aprovado_por TEXT, aprovado_em REAL, resumo_aprovado TEXT,
  emitido_por TEXT, emitido_em REAL, emitido_arquivo BLOB, emitido_pdf BLOB, resultado TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS docauto_v1 (
  doc_id TEXT PRIMARY KEY, titulo TEXT NOT NULL, texto TEXT NOT NULL, arquivo BLOB, guardado_em REAL NOT NULL);
CREATE TABLE IF NOT EXISTS docauto_hist (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, doc_id TEXT NOT NULL, quando REAL NOT NULL, quem TEXT NOT NULL,
  acao TEXT NOT NULL, de TEXT, para TEXT, nota TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS docauto_hist_doc ON docauto_hist(doc_id);
CREATE TABLE IF NOT EXISTS docbib (
  id TEXT PRIMARY KEY, titulo TEXT NOT NULL, tipo TEXT NOT NULL DEFAULT '', setor TEXT NOT NULL DEFAULT '',
  porte TEXT NOT NULL DEFAULT '', arquivo TEXT NOT NULL DEFAULT '', texto TEXT NOT NULL, resumo TEXT NOT NULL,
  criado_em REAL NOT NULL);
"""


def _resumo(texto: str, arquivo: bytes | None) -> str:
    h = hashlib.sha256((texto or "").encode("utf-8"))
    if arquivo:
        h.update(hashlib.sha256(arquivo).digest())
    return h.hexdigest()


def _limpo(t, n: int) -> str:
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(t or "")).strip()[:n]


class DocumentosAuto:
    """Fila de emissão e biblioteca. Guarda no SQLite do hub (hub._db, hub._trava); cada passo no registro encadeado."""

    def __init__(self, hub, pasta_biblioteca: str | Path | None = None, ia=None, emissor: EmissorNF | None = None):
        self.hub = hub
        self.ia = ia                                       # robos.CadeiaIA (Claude → local); None = sem IA
        self.emissor = emissor or emissor_nf_do_ambiente()
        self.pasta_bib = Path(pasta_biblioteca or os.environ.get("PHYSIS_BIBLIOTECA_PASTA") or (RAIZ / "dados" / "biblioteca"))
        with hub._trava:
            hub._db.executescript(TABELAS)
            hub._db.commit()

    # ── registro ──
    def _hist(self, doc_id: str, quem: str, acao: str, de: str | None, para: str | None, nota: str = "", extra: dict | None = None):
        agora = self.hub.relogio()
        self.hub._db.execute("INSERT INTO docauto_hist(doc_id,quando,quem,acao,de,para,nota) VALUES(?,?,?,?,?,?,?)",
                             (doc_id, agora, quem, acao, de, para, _limpo(nota, 500)))
        conteudo = {"o_que": acao, "doc": doc_id[:10], "de": de, "para": para}
        conteudo.update(extra or {})
        self.hub.registrar("documento_auto", quem, conteudo)

    # ── criar e ler ──
    def criar(self, tipo: str, titulo: str, texto: str, quem: str, dados: dict | None = None, origem: str = "",
              modelo: str = "", arquivo: bytes | None = None, ia: dict | None = None) -> dict:
        if tipo not in TIPOS:
            return {"ok": False, "codigo": 400, "erro": "tipo de documento desconhecido"}
        texto = str(texto or "")
        if len(texto) > TEXTO_MAX:
            return {"ok": False, "codigo": 413, "erro": "documento grande demais"}
        ident = secrets.token_urlsafe(15)
        agora = self.hub.relogio()
        pend = pendencias(texto)
        publicos = {k: v for k, v in (dados or {}).items() if not str(k).startswith("_")}
        with self.hub._trava:
            self.hub._db.execute(
                "INSERT INTO docauto(id,tipo,titulo,estado,texto,arquivo,dados,pendencias,origem,modelo,ia,versao,resumo,criado_por,criado_em,atualizado_em) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,1,?,?,?,?)",
                (ident, tipo, _limpo(titulo, 200) or tipo, "rascunho", texto, arquivo, json.dumps(publicos, ensure_ascii=False, default=str),
                 json.dumps(pend, ensure_ascii=False), _limpo(origem, 200), _limpo(modelo, 200),
                 json.dumps(ia, ensure_ascii=False) if ia else "", _resumo(texto, arquivo), quem, agora, agora))
            extra = {"tipo": tipo, "origem": _limpo(origem, 80), "pendencias": len(pend)}
            if ia:
                extra.update(ia={"provedor": ia.get("tipo"), "modelo": ia.get("modelo"), "quando": ia.get("quando")})
            self._hist(ident, quem, "criado", None, "rascunho", extra=extra)
            self.hub._db.commit()
        return {"ok": True, "id": ident, "estado": "rascunho", "pendencias": pend}

    def _linha(self, doc_id: str):
        return self.hub._db.execute(
            "SELECT id,tipo,titulo,estado,texto,arquivo IS NOT NULL,dados,pendencias,origem,modelo,ia,versao,resumo,criado_por,criado_em,"
            "atualizado_em,enviado_por,enviado_em,aprovado_por,aprovado_em,resumo_aprovado,emitido_por,emitido_em,resultado,"
            "emitido_pdf IS NOT NULL FROM docauto WHERE id=?", (doc_id,)).fetchone()

    @staticmethod
    def _dict(r, com_texto: bool = True) -> dict:
        d = {"id": r[0], "tipo": r[1], "titulo": r[2], "estado": r[3], "tem_odt_modelo": bool(r[5]), "pendencias": json.loads(r[7] or "[]"),
             "origem": r[8], "modelo": r[9], "ia": json.loads(r[10]) if r[10] else None, "versao": r[11], "resumo": r[12],
             "criado_por": r[13], "criado_em": r[14], "atualizado_em": r[15], "enviado_por": r[16], "enviado_em": r[17],
             "aprovado_por": r[18], "aprovado_em": r[19], "emitido_por": r[21], "emitido_em": r[22],
             "resultado": json.loads(r[23]) if r[23] else None, "tem_pdf": bool(r[24])}
        if com_texto:
            d["texto"] = r[4]
            d["dados"] = json.loads(r[6] or "{}")
        return d

    def ver(self, doc_id: str) -> dict:
        with self.hub._trava:
            r = self._linha(doc_id)
            if not r:
                return {"ok": False, "codigo": 404, "erro": "documento não encontrado"}
            hist = self.hub._db.execute("SELECT quando,quem,acao,de,para,nota FROM docauto_hist WHERE doc_id=? ORDER BY seq", (doc_id,)).fetchall()
        d = self._dict(r)
        d["historico"] = [{"quando": q, "quem": w, "acao": a, "de": de, "para": pa, "nota": n} for q, w, a, de, pa, n in hist]
        return {"ok": True, "documento": d}

    def fila(self, estado: str | None = None) -> list[dict]:
        with self.hub._trava:
            sql = ("SELECT id,tipo,titulo,estado,'',arquivo IS NOT NULL,'{}',pendencias,origem,modelo,ia,versao,resumo,criado_por,criado_em,"
                   "atualizado_em,enviado_por,enviado_em,aprovado_por,aprovado_em,resumo_aprovado,emitido_por,emitido_em,resultado,"
                   "emitido_pdf IS NOT NULL FROM docauto")
            linhas = self.hub._db.execute(sql + (" WHERE estado=?" if estado else "") + " ORDER BY atualizado_em DESC",
                                          (estado,) if estado else ()).fetchall()
        ordem = {"em_revisao": 0, "rascunho": 1, "aprovado": 2, "emitido": 3}
        out = [self._dict(r, com_texto=False) for r in linhas]
        out.sort(key=lambda d: ordem.get(d["estado"], 9))
        return out

    # ── fluxo ──
    def editar(self, doc_id: str, texto: str, quem: str, titulo: str | None = None) -> dict:
        texto = str(texto or "")
        if len(texto) > TEXTO_MAX:
            return {"ok": False, "codigo": 413, "erro": "documento grande demais"}
        with self.hub._trava:
            r = self.hub._db.execute("SELECT estado, texto, versao, titulo FROM docauto WHERE id=?", (doc_id,)).fetchone()
            if not r:
                return {"ok": False, "codigo": 404, "erro": "documento não encontrado"}
            estado, antigo, versao, tit = r
            if estado == "emitido":
                return {"ok": False, "codigo": 409, "erro": "documento já emitido: crie um novo (retificação)"}
            if texto == antigo and (titulo is None or _limpo(titulo, 200) == tit):
                return {"ok": True, "igual": True, "estado": estado}
            novo_estado = "em_revisao" if estado == "aprovado" else estado       # aprovado e mudou: volta para revisão
            agora = self.hub.relogio()
            pend = pendencias(texto)
            # 26/11/2026: a PRIMEIRA versão gerada pelo sistema fica guardada antes da 1ª edição (vai no pacote da equipe)
            self.hub._db.execute("INSERT OR IGNORE INTO docauto_v1(doc_id, titulo, texto, arquivo, guardado_em) "
                                 "SELECT id, titulo, texto, arquivo, ? FROM docauto WHERE id=?", (agora, doc_id))
            # editar à mão troca o modelo ODT pelo texto (o ODT preenchido deixa de valer)
            self.hub._db.execute("UPDATE docauto SET texto=?, titulo=?, arquivo=NULL, pendencias=?, versao=?, resumo=?, estado=?, "
                                 "atualizado_em=?, aprovado_por=CASE WHEN ?='em_revisao' THEN NULL ELSE aprovado_por END, "
                                 "aprovado_em=CASE WHEN ?='em_revisao' THEN NULL ELSE aprovado_em END, "
                                 "resumo_aprovado=CASE WHEN ?='em_revisao' THEN NULL ELSE resumo_aprovado END WHERE id=?",
                                 (texto, _limpo(titulo, 200) if titulo else tit, json.dumps(pend, ensure_ascii=False), versao + 1,
                                  _resumo(texto, None), novo_estado, agora, novo_estado, novo_estado, novo_estado, doc_id))
            self._hist(doc_id, quem, "editado", estado, novo_estado, extra={"versao": versao + 1})
            self.hub._db.commit()
        return {"ok": True, "estado": novo_estado, "versao": versao + 1, "voltou_para_revisao": estado == "aprovado"}

    def _mudar(self, doc_id: str, quem: str, de: tuple, para: str, acao: str, nota: str = "", campos: str = "", valores: tuple = ()) -> dict:
        with self.hub._trava:
            r = self.hub._db.execute("SELECT estado FROM docauto WHERE id=?", (doc_id,)).fetchone()
            if not r:
                return {"ok": False, "codigo": 404, "erro": "documento não encontrado"}
            if r[0] not in de:
                return {"ok": False, "codigo": 409, "erro": f"não dá para {acao} um documento em {r[0]}", "estado": r[0]}
            self.hub._db.execute(f"UPDATE docauto SET estado=?, atualizado_em=?{campos} WHERE id=?",
                                 (para, self.hub.relogio()) + valores + (doc_id,))
            self._hist(doc_id, quem, acao, r[0], para, nota)
            self.hub._db.commit()
        return {"ok": True, "estado": para}

    def enviar_revisao(self, doc_id: str, quem: str) -> dict:
        return self._mudar(doc_id, quem, ("rascunho",), "em_revisao", "enviar para revisão",
                           campos=", enviado_por=?, enviado_em=?", valores=(quem, self.hub.relogio()))

    def aprovar(self, doc_id: str, quem: str, nota: str = "") -> dict:
        """Só quem tem o papel certo chega aqui (a rota exige a direção). Guarda quem, quando e o resumo aprovado."""
        with self.hub._trava:
            r = self.hub._db.execute("SELECT resumo, pendencias FROM docauto WHERE id=?", (doc_id,)).fetchone()
        if not r:
            return {"ok": False, "codigo": 404, "erro": "documento não encontrado"}
        return self._mudar(doc_id, quem, ("em_revisao",), "aprovado", "aprovar", nota,
                           campos=", aprovado_por=?, aprovado_em=?, resumo_aprovado=?", valores=(quem, self.hub.relogio(), r[0]))

    def devolver(self, doc_id: str, quem: str, motivo: str = "") -> dict:
        return self._mudar(doc_id, quem, ("em_revisao", "aprovado"), "rascunho", "devolver", motivo,
                           campos=", aprovado_por=NULL, aprovado_em=NULL, resumo_aprovado=NULL")

    def emitir(self, doc_id: str, quem: str, converter_pdf=None) -> dict:
        """Recusa sem aprovação, ou se o texto mudou depois de aprovado. Gera o ODT final (e o PDF/A se houver LibreOffice)."""
        with self.hub._trava:
            r = self.hub._db.execute("SELECT estado, resumo, resumo_aprovado, aprovado_por, texto, arquivo, titulo, tipo, dados FROM docauto WHERE id=?",
                                     (doc_id,)).fetchone()
            if not r:
                return {"ok": False, "codigo": 404, "erro": "documento não encontrado"}
            estado, resumo, resumo_ap, aprovado_por, texto, arquivo, titulo, tipo, dados = r
            if estado != "aprovado" or not aprovado_por or not resumo_ap:
                self._hist(doc_id, quem, "emissão recusada", estado, estado, "sem aprovação")
                self.hub._db.commit()
                return {"ok": False, "codigo": 409, "erro": "emissão recusada: o documento precisa ser aprovado antes", "estado": estado}
            if resumo != resumo_ap:
                self._hist(doc_id, quem, "emissão recusada", estado, estado, "mudou depois da aprovação")
                self.hub._db.commit()
                return {"ok": False, "codigo": 409, "erro": "emissão recusada: o documento mudou depois da aprovação"}
        quando = _dt.datetime.fromtimestamp(self.hub.relogio())
        final = bytes(arquivo) if arquivo else odt_de_texto(texto, titulo, quando=quando)
        pdf = None
        conv = converter_pdf if converter_pdf is not None else odf.converter_pdfa
        try:
            rp = conv(final) if conv else {"ok": False}
            pdf = rp.get("pdf") if isinstance(rp, dict) and rp.get("ok") else None
        except Exception:                          # sem LibreOffice: emite o ODT; o PDF/A sai depois
            pdf = None
        resultado = {"odt_sha256": hashlib.sha256(final).hexdigest(), "pdf": bool(pdf)}
        if tipo == "nf":
            try:
                resultado["nf"] = self.emissor.emitir(json.loads(dados or "{}"))
            except NotImplementedError as exc:
                resultado["nf"] = {"ok": False, "pendente": True, "erro": str(exc)}
        with self.hub._trava:
            agora = self.hub.relogio()
            self.hub._db.execute("UPDATE docauto SET estado='emitido', emitido_por=?, emitido_em=?, emitido_arquivo=?, emitido_pdf=?, "
                                 "resultado=?, atualizado_em=? WHERE id=? AND estado='aprovado'",
                                 (quem, agora, final, pdf, json.dumps(resultado, ensure_ascii=False), agora, doc_id))
            self._hist(doc_id, quem, "emitir", "aprovado", "emitido", extra={"odt_sha256": resultado["odt_sha256"], "aprovado_por": aprovado_por})
            self.hub._db.commit()
        return {"ok": True, "estado": "emitido", "resultado": resultado}

    def arquivo(self, doc_id: str, formato: str = "odt") -> dict:
        """Emitido: o arquivo oficial. Antes disso: prévia em ODT marcada RASCUNHO (nunca PDF)."""
        with self.hub._trava:
            r = self.hub._db.execute("SELECT estado, texto, titulo, arquivo, emitido_arquivo, emitido_pdf FROM docauto WHERE id=?", (doc_id,)).fetchone()
        if not r:
            return {"ok": False, "codigo": 404, "erro": "documento não encontrado"}
        estado, texto, titulo, arquivo, emit, pdf = r
        nome = re.sub(r"[^A-Za-z0-9_-]+", "-", titulo)[:60] or "documento"
        if formato == "pdf":
            if estado != "emitido" or not pdf:
                return {"ok": False, "codigo": 404, "erro": "PDF só depois da emissão e com o LibreOffice no servidor"}
            return {"ok": True, "bytes": bytes(pdf), "tipo": "application/pdf", "nome": nome + ".pdf"}
        if estado == "emitido" and emit:
            return {"ok": True, "bytes": bytes(emit), "tipo": odf.MIME_ODT, "nome": nome + ".odt"}
        dados = odt_de_texto(texto, titulo, rascunho=True) if not arquivo else bytes(arquivo)
        return {"ok": True, "bytes": dados, "tipo": odf.MIME_ODT, "nome": nome + "-RASCUNHO.odt"}

    # ── geração a partir do sistema ──
    def _central(self, tipo: str, numero: str) -> dict | None:
        with self.hub._trava:
            r = self.hub._db.execute("SELECT dados FROM central WHERE tipo=? AND numero=?", (tipo, numero)).fetchone()
        return json.loads(r[0]) if r else None

    def gerar(self, pedido: dict, quem: str) -> dict:
        """{tipo, fonte: {tipo: compra|pedido, numero} | dados: {...}, modulos?, titulo?} → rascunho na fila."""
        tipo = str(pedido.get("tipo") or "")
        if tipo not in TIPOS or tipo in ("adaptado",):
            return {"ok": False, "codigo": 400, "erro": "tipo de documento desconhecido"}
        fonte = pedido.get("fonte") if isinstance(pedido.get("fonte"), dict) else {}
        hoje = _dt.datetime.fromtimestamp(self.hub.relogio()).strftime("%d/%m/%Y")
        if fonte:
            bruto = self._central(str(fonte.get("tipo") or ""), str(fonte.get("numero") or ""))
            if bruto is None:
                return {"ok": False, "codigo": 404, "erro": "compra ou pedido não encontrado"}
            numero = str(fonte.get("numero"))
            if tipo == "nf":
                dados = dados_nf(bruto, numero, hoje)
            elif fonte.get("tipo") == "compra":
                dados = dados_da_compra(bruto, numero, hoje)
            else:
                dados = dados_do_pedido(bruto, numero, hoje)
            origem = f"{fonte.get('tipo')}:{numero}"
        else:
            dados = dict(pedido.get("dados") or {}) if isinstance(pedido.get("dados"), dict) else {}
            dados.setdefault("hoje", hoje)
            origem = "manual"
        modulos = pedido.get("modulos") or dados.get("_modulos") or []
        if tipo == "relatorio":
            c = compor_relatorio(modulos, dados, str(pedido.get("titulo") or ""))
            return self.criar(tipo, pedido.get("titulo") or f"Relatório · {', '.join(c['modulos']) or 'plataforma'}", c["texto"], quem,
                              dados, origem, "relatorios/" + "+".join(c["modulos"]))
        if tipo == "manual":
            c = compor_manual(modulos, dados)
            return self.criar(tipo, pedido.get("titulo") or f"Manual · {(dados.get('cliente') or {}).get('nome') or 'cliente'}",
                              c["texto"], quem, dados, origem, "manual/" + "+".join(c["modulos"]))
        c = compor_documento(tipo, dados)
        titulo = pedido.get("titulo") or f"{tipo.capitalize()} · {(dados.get('pedido') or {}).get('numero') or (dados.get('cliente') or {}).get('nome') or hoje}"
        return self.criar(tipo, titulo, c["texto"], quem, dados, origem, c["modelo"] or "", arquivo=c["odt"])

    def manual_da_compra(self, numero_compra: str, modulos: list[str], quem: str = "sistema") -> dict:
        """Chamado quando a compra é aprovada (instalação montada): o rascunho do manual entra na fila."""
        bruto = self._central("compra", numero_compra) or {}
        dados = dados_da_compra(bruto, numero_compra, _dt.datetime.fromtimestamp(self.hub.relogio()).strftime("%d/%m/%Y"))
        c = compor_manual(modulos, dados)
        return self.criar("manual", f"Manual · {(dados.get('cliente') or {}).get('nome') or numero_compra}", c["texto"], quem,
                          dados, f"compra:{numero_compra}", "manual/" + "+".join(c["modulos"]))

    def documentos_da_compra(self, numero_compra: str, modulos: list[str], quem: str = "sistema") -> dict:
        """Compra aprovada: rascunhos do manual, do contrato e dos dados da NF entram sozinhos na fila de revisão."""
        out = {"manual": self.manual_da_compra(numero_compra, modulos, quem).get("id")}
        for tipo in ("contrato", "nf"):
            out[tipo] = self.gerar({"tipo": tipo, "fonte": {"tipo": "compra", "numero": numero_compra}}, quem).get("id")
        return out

    # ── biblioteca ──
    def bib_acrescentar(self, titulo: str, texto: str, quem: str, tipo: str = "", setor: str = "", porte: str = "", arquivo: str = "") -> dict:
        texto = str(texto or "")
        if not _limpo(titulo, 200) or not texto.strip():
            return {"ok": False, "codigo": 400, "erro": "falta título ou texto"}
        resumo = hashlib.sha256(texto.encode("utf-8")).hexdigest()
        with self.hub._trava:
            ja = self.hub._db.execute("SELECT id FROM docbib WHERE resumo=?", (resumo,)).fetchone()
            if ja:
                return {"ok": True, "id": ja[0], "repetido": True}
            ident = secrets.token_urlsafe(12)
            self.hub._db.execute("INSERT INTO docbib(id,titulo,tipo,setor,porte,arquivo,texto,resumo,criado_em) VALUES(?,?,?,?,?,?,?,?,?)",
                                 (ident, _limpo(titulo, 200), _limpo(tipo, 60), _limpo(setor, 80), _limpo(porte, 40), _limpo(arquivo, 300),
                                  texto[:TEXTO_MAX], resumo, self.hub.relogio()))
            self.hub.registrar("biblioteca", quem, {"o_que": "documento na biblioteca", "doc": ident[:10], "tipo": _limpo(tipo, 60)})
            self.hub._db.commit()
        return {"ok": True, "id": ident, "repetido": False}

    def bib_indexar(self, quem: str = "sistema") -> dict:
        """Lê a pasta da biblioteca (.md, .txt, .odt). Metadados opcionais em <arquivo>.json: {titulo,tipo,setor,porte}."""
        if not self.pasta_bib.is_dir():
            return {"ok": True, "novos": 0, "pasta": str(self.pasta_bib), "aviso": "pasta da biblioteca ainda não existe"}
        novos = 0
        for arq in sorted(self.pasta_bib.rglob("*")):
            if not arq.is_file() or arq.suffix.lower() not in (".md", ".txt", ".odt"):
                continue
            meta = {}
            lado = arq.with_suffix(arq.suffix + ".json")
            if lado.is_file():
                try:
                    meta = json.loads(lado.read_text(encoding="utf-8"))
                except ValueError:
                    meta = {}
            texto = texto_de_odt(arq.read_bytes()) if arq.suffix.lower() == ".odt" else arq.read_text(encoding="utf-8", errors="replace")
            r = self.bib_acrescentar(meta.get("titulo") or arq.stem, texto, quem, meta.get("tipo", ""), meta.get("setor", ""),
                                     meta.get("porte", ""), arq.relative_to(self.pasta_bib).as_posix())
            novos += bool(r.get("ok") and not r.get("repetido"))
        return {"ok": True, "novos": novos, "pasta": str(self.pasta_bib)}

    def bib_listar(self) -> list[dict]:
        with self.hub._trava:
            linhas = self.hub._db.execute("SELECT id,titulo,tipo,setor,porte,arquivo,length(texto),criado_em FROM docbib ORDER BY criado_em DESC").fetchall()
        return [{"id": i, "titulo": t, "tipo": tp, "setor": s, "porte": p, "arquivo": a, "tamanho": n, "criado_em": c}
                for i, t, tp, s, p, a, n, c in linhas]

    def bib_buscar(self, texto: str, tipo: str = "", setor: str = "", porte: str = "", k: int = 5) -> list[dict]:
        """BM25 no texto (título conta em dobro) + bônus de metadados: mesmo tipo +30%, mesmo setor +20%, mesmo porte +10%."""
        with self.hub._trava:
            linhas = self.hub._db.execute("SELECT id,titulo,tipo,setor,porte,texto FROM docbib").fetchall()
        if not linhas:
            return []
        notas = bm25(texto, [f"{t} {t} {x}" for _, t, _, _, _, x in linhas])
        out = []
        for (i, t, tp, s, p, _x), n in zip(linhas, notas):
            bonus = 1.0 + (0.3 if tipo and _slug(tp) == _slug(tipo) else 0) + (0.2 if setor and _slug(s) == _slug(setor) else 0) \
                + (0.1 if porte and _slug(p) == _slug(porte) else 0)
            nota = n * bonus if n > 0 else 0.0
            if nota > 0:
                out.append({"id": i, "titulo": t, "tipo": tp, "setor": s, "porte": p, "nota": round(nota, 4)})
        out.sort(key=lambda x: (-x["nota"], x["titulo"]))
        return out[:k]

    def adaptar(self, pedido: dict, quem: str, nomes=()) -> dict:
        """Acha o documento mais parecido e pede à IA para adaptá-lo aos requisitos do pedido novo. Sempre rascunho.
        pedido: {texto (requisitos), tipo, setor, porte, titulo?}. Sem IA: o documento parecido entra com os requisitos
        no topo como [MARCADOR], para a pessoa adaptar."""
        req = str(pedido.get("texto") or "").strip()
        if not req:
            return {"ok": False, "codigo": 400, "erro": "faltam os requisitos do pedido novo"}
        achados = self.bib_buscar(req, pedido.get("tipo", ""), pedido.get("setor", ""), pedido.get("porte", ""), k=3)
        if not achados:
            return {"ok": False, "codigo": 404, "erro": "nenhum documento parecido na biblioteca"}
        with self.hub._trava:
            base_txt = self.hub._db.execute("SELECT texto FROM docbib WHERE id=?", (achados[0]["id"],)).fetchone()[0]
        titulo = _limpo(pedido.get("titulo"), 200) or f"Adaptado de {achados[0]['titulo']}"
        ia_info, texto = None, None
        if self.ia is not None and getattr(self.ia, "ativa", False):
            sistema = ("Você adapta documentos técnicos da Physis Engenharia (propostas, projetos para editais) a um pedido novo. "
                       "Português do Brasil. Mantenha a estrutura e o tom do documento base. Troque só o que os requisitos pedem. "
                       "Não invente números, preços, prazos, parceiros nem resultados: onde faltar dado, escreva [MARCADOR: o que falta]. "
                       "Responda só com o documento em Markdown.")
            entrada = f"Requisitos do pedido novo:\n{req[:8000]}\n\nDocumento base (\"{achados[0]['titulo']}\"):\n{base_txt[:60000]}"
            texto = self.ia.gerar(sistema, entrada, robo="documentos", nomes=nomes)
            if texto:
                ia_info = dict(getattr(self.ia, "ultimo", None) or {"tipo": getattr(self.ia, "tipo", "ia")})
                ia_info.setdefault("quando", _dt.datetime.fromtimestamp(self.hub.relogio()).isoformat(timespec="seconds"))
        if not texto:
            from .robos import anonimizar
            texto = (f"# {titulo}\n\n[MARCADOR: adaptar este documento aos requisitos do pedido novo: {anonimizar(req, nomes)[:1500]}]\n\n"
                     + base_txt)
        r = self.criar("adaptado", titulo, texto, quem, {"base": achados[0], "requisitos_anonimizados": True},
                       f"biblioteca:{achados[0]['id']}", "", ia=ia_info)
        if r.get("ok"):
            r.update(base=achados[0], parecidos=achados, ia=ia_info)
        return r

    # ── rotas ──
    def rota(self, metodo: str, caminho: str, conta: dict | None, corpo=None, consulta: dict | None = None):
        """/api/emissao…: (código, json). Arquivo: (200, {"_bytes", "_tipo", "_nome"}). Papéis: equipe gera, edita,
        envia e emite (só aprovado); a direção aprova e devolve. CSRF é conferido pelo servidor antes daqui."""
        if not caminho.startswith("/api/emissao"):
            return None
        if not conta:
            return 401, {"ok": False, "erro": "entre com usuario e senha", "login": True}
        if not seg.pode(conta, seg.EQUIPE):
            return 403, {"ok": False, "erro": "o seu papel não permite esta ação"}
        quem = conta.get("usuario") or "?"
        direcao = seg.pode(conta, seg.DIRECAO)
        partes = [p for p in caminho.split("/") if p][2:]
        try:
            d = seg.carregar_json((corpo.decode("utf-8", "replace") if isinstance(corpo, bytes) else corpo) or "{}") if metodo == "POST" else {}
        except ValueError:
            return 400, {"ok": False, "erro": "json invalido"}
        if not isinstance(d, dict):
            return 400, {"ok": False, "erro": "json invalido"}
        resp = lambda r: (r.pop("codigo", 200 if r.get("ok") else 400), r)
        q = consulta or {}
        if metodo == "GET":
            if not partes:
                est = (q.get("estado") or [None])[0]
                return 200, {"ok": True, "documentos": self.fila(est if est in ESTADOS else None), "pode_aprovar": direcao}
            if partes == ["modelos"]:
                return 200, {"ok": True, "tipos": list(TIPOS), "vendaveis": list(VENDAVEIS), "ordem_abas": list(ORDEM_ABAS),
                             "nomes": nomes_modulos(), "pastas": [str(p) for p in pastas_modelos() if p.is_dir()]}
            if partes == ["biblioteca"]:
                return 200, {"ok": True, "documentos": self.bib_listar()}
            if len(partes) == 1 and _ID.match(partes[0]):
                return resp(self.ver(partes[0]))
            if len(partes) == 2 and _ID.match(partes[0]) and partes[1] == "arquivo":
                r = self.arquivo(partes[0], (q.get("formato") or ["odt"])[0])
                if not r.get("ok"):
                    return resp(r)
                return 200, {"_bytes": r["bytes"], "_tipo": r["tipo"], "_nome": r["nome"]}
            return 404, {"ok": False, "erro": "rota desconhecida"}
        if metodo != "POST":
            return 405, {"ok": False, "erro": "método não aceito"}
        if partes == ["gerar"]:
            return resp(self.gerar(d, quem))
        if partes == ["biblioteca"]:
            return resp(self.bib_acrescentar(d.get("titulo"), d.get("texto"), quem, d.get("tipo", ""), d.get("setor", ""), d.get("porte", "")))
        if partes == ["biblioteca", "indexar"]:
            return resp(self.bib_indexar(quem))
        if partes == ["biblioteca", "buscar"]:
            return 200, {"ok": True, "parecidos": self.bib_buscar(str(d.get("texto") or ""), d.get("tipo", ""), d.get("setor", ""), d.get("porte", ""))}
        if partes == ["adaptar"]:
            return resp(self.adaptar(d, quem))
        if len(partes) == 2 and _ID.match(partes[0]):
            doc_id, acao = partes
            if acao == "editar":
                return resp(self.editar(doc_id, d.get("texto"), quem, d.get("titulo")))
            if acao == "enviar":
                return resp(self.enviar_revisao(doc_id, quem))
            if acao in ("aprovar", "devolver"):
                if not direcao:
                    return 403, {"ok": False, "erro": "só a direção aprova ou devolve documentos"}
                return resp(self.aprovar(doc_id, quem, d.get("nota", "")) if acao == "aprovar" else self.devolver(doc_id, quem, d.get("motivo", "")))
            if acao == "emitir":
                return resp(self.emitir(doc_id, quem))
        return 404, {"ok": False, "erro": "rota desconhecida"}
