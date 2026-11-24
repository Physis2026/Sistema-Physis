"""Banco de fornecedores e equipamentos (solar primeiro; outras áreas na Fase 2), atualizado região por região.

Tabelas (no banco do hub): fornecedor, fornecedor_contato, fornecedor_regiao, fornecedor_equipamento, fornecedor_oferta,
fornecedor_preco, fornecedor_arquivo, fornecedor_importacao, fornecedor_tarefa e fornecedor_historico (só cresce).

Quem faz o quê:
- a EQUIPE cadastra o fornecedor (empresa, CNPJ conferido pelos dígitos como em parceiros.py), os contatos (cada um
  com consentimento, LGPD art. 7º I), a abrangência (nacional, regional, estadual, local), as regiões atendidas (UF e/ou
  município pelo código IBGE), o local da sede (lat/lon digitados: sem serviço de geocodificação de terceiros), os
  equipamentos (marca/modelo, ligados ao id da base sistema/physis-equipamentos.json quando há classe igual), catálogos e
  folhas de dados (PDF/imagem, guardados no servidor), prazo de entrega, pedido mínimo e preços;
- preço só entra com DATA, REGIÃO e FONTE (cotação ou catálogo). Nada é inventado e nada aparece sem a data;
- cada região tem a data da última atualização; passou do limite (premissa fornecedores.dias_desatualizado, status
  "conferir") fica "desatualizada". A fila por região é do Ryan (fornecedores); "pedir atualização" cria uma tarefa na
  Gestão (chave gestao-physis:fornecedores-tarefas). Importação CSV por região, validada, com resumo SHA-256;
- só a DIREÇÃO muda a curadoria (em_analise, aprovado, suspenso) e marca arquivo como público;
- o CLIENTE (aba Energia solar, "Fornecedores na sua região") vê só fornecedor aprovado e ativo, com campos públicos:
  nome, site, região (com a data e se está desatualizada), produtos, prazo/pedido mínimo, preço de catálogo com data e
  fonte e arquivo marcado público. Nada de CNPJ, contato, nota interna, cotação, local da sede, nem arquivo interno;
- instalação/integração não é fornecedor: é link para os profissionais parceiros (parceiros.py), sem duplicar cadastro.
Toda alteração vai para o histórico (quem, quando, o quê; só metadados, nunca nome/e-mail/telefone de contato), numa
cadeia de resumos SHA-256 como o registro do hub, e para hub.registrar. O histórico não aceita UPDATE nem DELETE.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path

from . import clima as clima_mod
from . import integridade
from . import parceiros as parc
from . import seguranca as seg

RAIZ = Path(__file__).resolve().parents[2]
_WEB = Path(__file__).resolve().parents[1] / "web"
ARQ_EQUIPAMENTOS = (RAIZ / "sistema" / "physis-equipamentos.json", _WEB / "physis-equipamentos.json")
ARQ_PREMISSAS = (RAIZ / "sistema" / "physis-premissas.json", _WEB / "physis-premissas.json")
PREMISSA_DIAS = "fornecedores.dias_desatualizado"
DIAS_PADRAO = 90                      # reserva sem a base de premissas; política a conferir (status "conferir")
RESPONSAVEL = {"id": "ryan", "nome": "Ryan", "area": "fornecedores"}
CHAVE_GESTAO = "gestao-physis:fornecedores-tarefas"
VERSAO_TERMO = "1"
FINALIDADE_CONTATO = ("Contato comercial do fornecedor com a Physis: pedir cotação, catálogo e atualização dos dados. "
                      "Só a equipe da Physis vê; a pessoa pode pedir a exclusão a qualquer momento.")
SEGMENTOS = {"solar": "Energia solar"}          # Fase 2: água, AVAC, materiais de bioconstrução
CATEGORIAS = {"modulos": "Módulos fotovoltaicos", "inversores": "Inversores", "estruturas": "Estruturas de fixação",
              "baterias": "Baterias", "protecao": "String box e proteção", "cabos": "Cabos e conectores",
              "kits": "Kits completos", "instalacao": "Instalação e integração (profissionais parceiros)",
              # 24/11/2026: AVAC e instalações (fabricantes da planilha PHYSIS_AVAC-5, sem base externa)
              "ar_condicionado": "Ar-condicionado (split, VRF, fancoil, self, rooftop)", "chillers": "Chillers e torres de resfriamento",
              "ventilacao": "Ventiladores, exaustores e filtragem", "difusao": "Difusores, grelhas, dampers e dutos", "bombas": "Bombas hidráulicas",
              "valvulas": "Válvulas, atuadores e isolamento", "aquecimento": "Aquecedores a gás, solar e bombas de calor", "piscina": "Equipamentos de piscina",
              "automacao": "Automação predial e inversores de frequência"}
SEGMENTO_CATEGORIA = {"Split e multi-split": "ar_condicionado", "VRF / fluxo variável": "ar_condicionado", "Fancoils e UTAs": "ar_condicionado",
                      "Rooftop e self-contained": "ar_condicionado", "Desumidificação": "ar_condicionado", "Chillers": "chillers", "Torres de resfriamento": "chillers",
                      "Ventiladores industriais": "ventilacao", "Exaustores residenciais": "ventilacao", "Filtragem de ar": "ventilacao",
                      "Difusores, grelhas e dampers": "difusao", "Dutos flexíveis": "difusao", "Bombas hidráulicas": "bombas", "Válvulas e atuadores": "valvulas",
                      "Isolamento térmico": "valvulas", "Aquecimento solar": "aquecimento", "Aquecedores a gás": "aquecimento", "Bombas de calor para piscina": "aquecimento",
                      "Equipamentos de piscina": "piscina", "Automação predial": "automacao", "Inversores de frequência": "automacao"}
CATEGORIA_DA_BASE = {"módulos fotovoltaicos": "modulos", "inversores": "inversores", "baterias": "baterias",
                     "componentes de quadro": "protecao"}
ABRANGENCIAS = {"nacional": "Nacional", "regional": "Regional", "estadual": "Estadual", "local": "Local"}
STATUS = {"em_analise": "Em análise", "aprovado": "Aprovado", "suspenso": "Suspenso"}
FONTES_PRECO = {"cotacao": "Cotação", "catalogo": "Catálogo"}
NACIONAL = "BR"
UFS = parc.UFS
ARQ_MAX = 20 * 1024 * 1024
ARQ_TIPOS = {".pdf": ("application/pdf", (b"%PDF-",)), ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
             ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)), ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
             ".webp": ("image/webp", (b"RIFF",))}
CSV_MAX = 1024 * 1024
CSV_LINHAS_MAX = 5000
CSV_COLUNAS = ("cnpj", "categoria", "marca", "modelo", "equipamento_id", "prazo_entrega_dias", "pedido_minimo_brl",
               "preco", "preco_unidade", "preco_data", "preco_fonte", "preco_fonte_ref")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS fornecedor (
  id INTEGER PRIMARY KEY AUTOINCREMENT, cnpj TEXT NOT NULL UNIQUE, nome TEXT NOT NULL, nome_publico TEXT NOT NULL,
  segmento TEXT NOT NULL DEFAULT 'solar', site TEXT NOT NULL DEFAULT '', abrangencia TEXT NOT NULL DEFAULT 'local',
  endereco TEXT NOT NULL DEFAULT '', municipio TEXT NOT NULL DEFAULT '', uf TEXT NOT NULL DEFAULT '', ibge TEXT NOT NULL DEFAULT '',
  lat REAL, lon REAL, raio_km REAL, categorias TEXT NOT NULL DEFAULT '[]', parceiros TEXT NOT NULL DEFAULT '[]',
  descricao TEXT NOT NULL DEFAULT '', notas_internas TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'em_analise', status_motivo TEXT NOT NULL DEFAULT '', status_por TEXT NOT NULL DEFAULT '', status_em REAL,
  ativo INTEGER NOT NULL DEFAULT 1, criado REAL NOT NULL, atualizado REAL NOT NULL, por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fornecedor_contato (
  id INTEGER PRIMARY KEY AUTOINCREMENT, fornecedor INTEGER NOT NULL, nome TEXT NOT NULL, cargo TEXT NOT NULL DEFAULT '',
  email TEXT NOT NULL DEFAULT '', telefone TEXT NOT NULL DEFAULT '', consentimento REAL NOT NULL, versao_termo TEXT NOT NULL,
  criado REAL NOT NULL, por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fornecedor_regiao (
  id INTEGER PRIMARY KEY AUTOINCREMENT, fornecedor INTEGER NOT NULL, chave TEXT NOT NULL, uf TEXT NOT NULL,
  ibge TEXT NOT NULL DEFAULT '', municipio TEXT NOT NULL DEFAULT '', prazo_entrega_dias INTEGER, pedido_minimo_brl REAL,
  atualizado REAL NOT NULL, atualizado_por TEXT NOT NULL, UNIQUE (fornecedor, chave));
CREATE TABLE IF NOT EXISTS fornecedor_equipamento (
  id INTEGER PRIMARY KEY AUTOINCREMENT, categoria TEXT NOT NULL, marca TEXT NOT NULL DEFAULT '', modelo TEXT NOT NULL DEFAULT '',
  equipamento_id TEXT NOT NULL DEFAULT '', ficha_url TEXT NOT NULL DEFAULT '', notas_internas TEXT NOT NULL DEFAULT '',
  criado REAL NOT NULL, atualizado REAL NOT NULL, por TEXT NOT NULL, UNIQUE (categoria, marca, modelo));
CREATE TABLE IF NOT EXISTS fornecedor_oferta (
  id INTEGER PRIMARY KEY AUTOINCREMENT, fornecedor INTEGER NOT NULL, equipamento INTEGER NOT NULL, criado REAL NOT NULL,
  por TEXT NOT NULL, UNIQUE (fornecedor, equipamento));
CREATE TABLE IF NOT EXISTS fornecedor_preco (
  id INTEGER PRIMARY KEY AUTOINCREMENT, oferta INTEGER NOT NULL, uf TEXT NOT NULL, ibge TEXT NOT NULL DEFAULT '',
  valor REAL NOT NULL, unidade TEXT NOT NULL, data TEXT NOT NULL, fonte TEXT NOT NULL, fonte_ref TEXT NOT NULL DEFAULT '',
  importacao INTEGER, criado REAL NOT NULL, por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fornecedor_arquivo (
  id INTEGER PRIMARY KEY AUTOINCREMENT, fornecedor INTEGER, equipamento INTEGER, tipo_doc TEXT NOT NULL, nome TEXT NOT NULL,
  mime TEXT NOT NULL, tamanho INTEGER NOT NULL, sha256 TEXT NOT NULL, arquivo TEXT NOT NULL, publico INTEGER NOT NULL DEFAULT 0,
  criado REAL NOT NULL, por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fornecedor_importacao (
  id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT NOT NULL, uf TEXT NOT NULL, ibge TEXT NOT NULL DEFAULT '',
  municipio TEXT NOT NULL DEFAULT '', nome_arquivo TEXT NOT NULL DEFAULT '', linhas INTEGER NOT NULL, resumo TEXT NOT NULL,
  arquivo_sha256 TEXT NOT NULL, quando REAL NOT NULL, por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS fornecedor_tarefa (
  id TEXT PRIMARY KEY, chave TEXT NOT NULL, uf TEXT NOT NULL, ibge TEXT NOT NULL DEFAULT '', municipio TEXT NOT NULL DEFAULT '',
  titulo TEXT NOT NULL, responsavel TEXT NOT NULL, prazo TEXT NOT NULL DEFAULT '', estado TEXT NOT NULL DEFAULT 'aberta',
  criado REAL NOT NULL, por TEXT NOT NULL, fechado REAL, fechado_por TEXT NOT NULL DEFAULT '', gestao INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS fornecedor_historico (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, quando REAL NOT NULL, quem TEXT NOT NULL, fornecedor INTEGER, o_que TEXT NOT NULL,
  detalhe TEXT NOT NULL, anterior TEXT NOT NULL, resumo TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS fornecedor_historico_sem_mudar BEFORE UPDATE ON fornecedor_historico
  BEGIN SELECT RAISE(ABORT, 'historico so cresce'); END;
CREATE TRIGGER IF NOT EXISTS fornecedor_historico_sem_apagar BEFORE DELETE ON fornecedor_historico
  BEGIN SELECT RAISE(ABORT, 'historico so cresce'); END;
"""

# Esquemas dos corpos JSON (entram em seg.ESQUEMAS pelo servidor; o módulo também valida, estrito)
S, NUM = str, (int, float)
_CAD = {"cnpj": (S, 20, True), "nome": (S, 160, True), "nome_publico": (S, 120, False), "segmento": (S, 20, False),
        "site": (S, 300, False), "abrangencia": (S, 20, False), "endereco": (S, 300, False), "municipio": (S, 80, False),
        "uf": (S, 2, False), "ibge": (S, 7, False), "lat": (NUM, 90, False), "lon": (NUM, 180, False), "raio_km": (NUM, 5000, False),
        "categorias": (list, 20, False), "parceiros": (list, 50, False), "descricao": (S, 1000, False),
        "notas_internas": (S, 4000, False), "regioes": (list, 200, False), "contatos": (list, 10, False)}
ESQUEMAS = {
    "forn_cadastro": _CAD,
    "forn_editar": dict({k: (v[0], v[1], False) for k, v in _CAD.items() if k not in ("regioes", "contatos")},
                        ativo=(bool, None, False)),
    "forn_regiao": {"uf": (S, 2, True), "ibge": (S, 7, False), "municipio": (S, 80, False),
                    "prazo_entrega_dias": (int, 365, False), "pedido_minimo_brl": (NUM, 10**9, False)},
    "forn_id": {"id": (int, 10**12, True)},
    "forn_equipamento": {"id": (int, 10**12, False), "categoria": (S, 20, False), "marca": (S, 80, False), "modelo": (S, 120, False),
                         "equipamento_id": (S, 60, False), "ficha_url": (S, 300, False), "notas_internas": (S, 2000, False)},
    "forn_oferta": {"equipamento": (int, 10**12, True)},
    "forn_preco": {"oferta": (int, 10**12, True), "valor": (NUM, 10**9, True), "unidade": (S, 20, True), "data": (S, 10, True),
                   "fonte": (S, 20, True), "fonte_ref": (S, 200, False), "uf": (S, 2, True), "ibge": (S, 7, False)},
    "forn_contato": {"nome": (S, 120, True), "cargo": (S, 80, False), "email": (S, 160, False), "telefone": (S, 20, False),
                     "consentimento": (bool, None, False)},
    "forn_curadoria": {"status": (S, 20, True), "motivo": (S, 600, False)},
    "forn_arquivo_publico": {"id": (int, 10**12, True), "publico": (bool, None, True)},
    "forn_importar": {"uf": (S, 2, True), "ibge": (S, 7, False), "municipio": (S, 80, False), "csv": (S, CSV_MAX, True),
                      "nome": (S, 160, False), "simular": (bool, None, False)},
    "forn_pedir": {"uf": (S, 2, True), "ibge": (S, 7, False), "municipio": (S, 80, False), "prazo": (S, 10, False)},
    "vazio": {},
}

_EMAIL = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_URL = re.compile(r"^https?://[^\s<>\"']{3,290}$", re.I)


# ══ Bases (equipamentos e premissas) ══════════════════════════════════════════════════════════════
def _ler_json(caminhos):
    for c in caminhos:
        try:
            return json.loads(Path(c).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return None


def base_equipamentos(dados=None) -> dict[str, dict]:
    """{id: {categoria (do fornecedor), descricao}} só das classes que viram categoria de fornecedor."""
    j = dados if dados is not None else _ler_json(ARQ_EQUIPAMENTOS) or {}
    out = {}
    for it in j.get("itens") or []:
        cat = CATEGORIA_DA_BASE.get(str(it.get("categoria") or ""))
        if cat and it.get("id"):
            out[str(it["id"])] = {"categoria": cat, "descricao": str(it.get("descricao") or "")}
    return out


def premissa_dias(dados=None) -> tuple[int, str]:
    """(dias, status) da premissa fornecedores.dias_desatualizado; sem a base, (90, 'conferir')."""
    j = dados if dados is not None else _ler_json(ARQ_PREMISSAS) or {}
    for p in j.get("premissas") or []:
        if p.get("id") == PREMISSA_DIAS:
            try:
                return max(1, int(p.get("valor_padrao"))), str(p.get("status") or "")
            except (TypeError, ValueError):
                break
    return DIAS_PADRAO, "conferir"


def pasta_padrao(banco: str | os.PathLike) -> Path:
    """PHYSIS_FORNECEDORES_PASTA ou a pasta do banco + /fornecedores-arquivos."""
    return Path(os.environ.get("PHYSIS_FORNECEDORES_PASTA") or (Path(banco).resolve().parent / "fornecedores-arquivos"))


# ══ Regras puras (testadas sem banco) ═════════════════════════════════════════════════════════════
def _sem(s) -> str:
    return clima_mod._sem_acento(str(s or "")).strip()


def _hoje(agora: float) -> str:
    return datetime.fromtimestamp(agora, clima_mod.FUSO).strftime("%Y-%m-%d")


def _dia(agora: float) -> str:
    return _hoje(agora)


def chave_regiao(uf: str, ibge: str = "", municipio: str = "") -> str:
    uf = (uf or "").upper()
    if uf == NACIONAL:
        return "BR:*"
    return f"{uf}:{ibge or _sem(municipio) or '*'}"


def rotulo_regiao(uf: str, ibge: str = "", municipio: str = "") -> str:
    if (uf or "").upper() == NACIONAL:
        return "Brasil (todo o país)"
    if municipio:
        return f"{municipio}/{uf}"
    if ibge:
        return f"IBGE {ibge}/{uf}"
    return f"{uf} (estado todo)"


def validar_regiao(r) -> tuple[dict | None, str]:
    r = r if isinstance(r, dict) else {"uf": r}
    uf = str(r.get("uf") or "").strip().upper()
    if uf != NACIONAL and uf not in UFS:
        return None, f"UF inválida: {uf or '(vazia)'}"
    ibge = str(r.get("ibge") or "").strip()
    if ibge and not re.fullmatch(r"\d{7}", ibge):
        return None, "código IBGE do município tem 7 dígitos"
    if uf == NACIONAL:
        return {"uf": NACIONAL, "ibge": "", "municipio": ""}, ""
    return {"uf": uf, "ibge": ibge, "municipio": str(r.get("municipio") or "").strip()[:80]}, ""


def distancia_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(min(1.0, math.sqrt(a)))


def alcance(f: dict, regioes: list[dict], uf: str, ibge: str = "", municipio: str = "", lat=None, lon=None) -> tuple[int, dict | None]:
    """3 = atende o município (citado, ou raio do fornecedor local cobre o ponto); 2 = o estado todo; 1 = o Brasil todo;
    0 = não atende. Devolve também a linha de região usada (para a data da última atualização)."""
    uf, mun = (uf or "").upper(), _sem(municipio)
    melhor, linha = 0, None
    for r in regioes:
        n = 0
        if r["uf"] == NACIONAL:
            n = 1
        elif r["uf"] == uf:
            if not r.get("ibge") and not r.get("municipio"):
                n = 2
            elif (ibge and r.get("ibge") == ibge) or (mun and _sem(r.get("municipio")) == mun):
                n = 3
        if n > melhor:
            melhor, linha = n, r
    if melhor < 3 and f.get("raio_km") and f.get("lat") is not None and lat is not None and lon is not None:
        if distancia_km(f["lat"], f["lon"], lat, lon) <= float(f["raio_km"]) and regioes:
            melhor, linha = 3, max(regioes, key=lambda r: r["atualizado"])
    if melhor < 1 and f.get("abrangencia") == "nacional" and regioes:
        melhor, linha = 1, max(regioes, key=lambda r: r["atualizado"])
    return melhor, linha


NIVEIS = {3: "municipio", 2: "uf", 1: "nacional", 0: "nenhum"}


def rotulo_nivel(nivel: int, uf: str, municipio: str) -> str:
    lugar = f"{municipio}/{uf}" if municipio else uf
    if nivel == 3:
        return f"Fornecedores que atendem {lugar}"
    if nivel == 2:
        return (f"Nenhum fornecedor cadastrado só para {lugar}: mostrando os que atendem todo o estado ({uf})"
                if municipio else f"Fornecedores que atendem todo o estado ({uf})")
    if nivel == 1:
        return f"Nenhum fornecedor cadastrado para {lugar} nem para o estado ({uf}): mostrando os que atendem todo o Brasil"
    return "Nenhum fornecedor cadastrado para a sua região ainda"


def desatualizado(atualizado: float, agora: float, dias: int) -> bool:
    return (agora - float(atualizado)) > dias * 86400


def validar_preco(d: dict, hoje: str) -> tuple[dict | None, str]:
    """Preço só com valor, unidade, DATA (não futura), REGIÃO (UF ou BR) e FONTE (cotação ou catálogo)."""
    try:
        valor = float(str(d.get("valor")).replace(",", ".")) if not isinstance(d.get("valor"), (int, float)) else float(d["valor"])
    except (TypeError, ValueError):
        return None, "preço: valor numérico"
    if not math.isfinite(valor) or valor <= 0:
        return None, "preço: valor maior que zero"
    unidade = str(d.get("unidade") or "").strip()[:20]
    if not unidade:
        return None, "preço: unidade (ex.: R$/un, R$/Wp)"
    data = str(d.get("data") or "").strip()
    try:
        ok = bool(_DATA.match(data)) and date.fromisoformat(data).isoformat() == data
    except ValueError:
        ok = False
    if not ok:
        return None, "preço sem data: informe a data no formato AAAA-MM-DD"
    if data > hoje:
        return None, "preço com data no futuro"
    fonte = str(d.get("fonte") or "").strip().lower().replace("ç", "c").replace("ã", "a").replace("á", "a")
    if fonte not in FONTES_PRECO:
        return None, "preço sem fonte: cotação ou catálogo"
    reg, erro = validar_regiao({"uf": d.get("uf"), "ibge": d.get("ibge")})
    if not reg or not d.get("uf"):
        return None, "preço sem região: " + (erro or "informe a UF")
    return {"valor": round(valor, 4), "unidade": unidade, "data": data, "fonte": fonte,
            "fonte_ref": str(d.get("fonte_ref") or "").strip()[:200], "uf": reg["uf"], "ibge": reg["ibge"]}, ""


def preco_mostravel(p: dict) -> bool:
    """Defesa extra na saída: sem data, fonte ou região o preço não sai, nem para a equipe."""
    return bool(p.get("data") and _DATA.match(str(p["data"])) and p.get("fonte") in FONTES_PRECO and p.get("uf"))


def _num_br(v):
    s = str(v or "").strip().replace("R$", "").replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def _celula_segura(v) -> str:
    """Contra injeção de fórmula ao abrir o CSV numa planilha."""
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def _site(v) -> tuple[str | None, str]:
    s = str(v or "").strip()
    if not s:
        return "", ""
    if not s.lower().startswith(("http://", "https://")):
        s = "https://" + s
    return (s, "") if _URL.match(s) else (None, "site: endereço http(s) válido")


def validar_cadastro(d: dict, parcial: bool = False) -> tuple[dict | None, str]:
    if not isinstance(d, dict):
        return None, "json invalido"
    out: dict = {}
    if not parcial or "cnpj" in d:
        cnpj = parc.so_digitos(d.get("cnpj"))
        if not parc.cnpj_valido(cnpj):
            return None, "CNPJ inválido"
        out["cnpj"] = cnpj
    if not parcial or "nome" in d:
        nome = str(d.get("nome") or "").strip()
        if not 2 <= len(nome) <= 160:
            return None, "razão social obrigatória (até 160 letras)"
        out["nome"] = nome
    if not parcial or "nome_publico" in d or "nome" in d:
        out["nome_publico"] = (str(d.get("nome_publico") or "").strip() or out.get("nome") or "")[:120]
    if not parcial or "segmento" in d:
        seg_ = str(d.get("segmento") or "solar")
        if seg_ not in SEGMENTOS:
            return None, "segmento: " + ", ".join(SEGMENTOS)
        out["segmento"] = seg_
    if not parcial or "site" in d:
        s, erro = _site(d.get("site"))
        if s is None:
            return None, erro
        out["site"] = s
    if not parcial or "abrangencia" in d:
        a = str(d.get("abrangencia") or "local")
        if a not in ABRANGENCIAS:
            return None, "abrangência: nacional, regional, estadual ou local"
        out["abrangencia"] = a
    for k, n in (("endereco", 300), ("municipio", 80), ("descricao", 1000), ("notas_internas", 4000)):
        if not parcial or k in d:
            out[k] = str(d.get(k) or "").strip()[:n]
    if not parcial or "uf" in d:
        uf = str(d.get("uf") or "").strip().upper()
        if uf and uf not in UFS:
            return None, f"UF inválida: {uf}"
        out["uf"] = uf
    if not parcial or "ibge" in d:
        ibge = str(d.get("ibge") or "").strip()
        if ibge and not re.fullmatch(r"\d{7}", ibge):
            return None, "código IBGE do município tem 7 dígitos"
        out["ibge"] = ibge
    if not parcial or "lat" in d or "lon" in d:
        la, lo = d.get("lat"), d.get("lon")
        if la in (None, "") and lo in (None, ""):
            out["lat"] = out["lon"] = None
        else:
            loc, erro = clima_mod.validar_local({"lat": la, "lon": lo})
            if not loc:
                return None, "local da sede: latitude e longitude válidas"
            out["lat"], out["lon"] = loc["lat"], loc["lon"]
    if not parcial or "raio_km" in d:
        r = d.get("raio_km")
        if r in (None, ""):
            out["raio_km"] = None
        else:
            try:
                r = float(r)
            except (TypeError, ValueError):
                return None, "raio de atendimento em km"
            if not 0 < r <= 5000:
                return None, "raio de atendimento entre 0 e 5000 km"
            out["raio_km"] = r
    if not parcial or "categorias" in d:
        cats = d.get("categorias") or []
        if not isinstance(cats, list) or any(c not in CATEGORIAS for c in cats):
            return None, "categorias: " + ", ".join(CATEGORIAS)
        out["categorias"] = sorted(set(cats))
    if not parcial or "parceiros" in d:
        ps = d.get("parceiros") or []
        if not isinstance(ps, list) or any(isinstance(p, bool) or not isinstance(p, int) for p in ps):
            return None, "parceiros: lista de ids de profissionais parceiros"
        out["parceiros"] = sorted(set(ps))
    if out.get("abrangencia") == "local" and out.get("raio_km") and out.get("lat") is None and not parcial:
        return None, "fornecedor local com raio precisa do local da sede (lat/lon)"
    return out, ""


def validar_contato(d) -> tuple[dict | None, str]:
    if not isinstance(d, dict) or d.get("consentimento") is not True:
        return None, "contato só com o consentimento da pessoa (LGPD)"
    nome = str(d.get("nome") or "").strip()[:120]
    if len(nome) < 2:
        return None, "nome do contato"
    email = str(d.get("email") or "").strip()[:160]
    if email and not _EMAIL.match(email):
        return None, "e-mail inválido"
    tel = parc.so_digitos(d.get("telefone"))[:13]
    if tel and len(tel) < 10:
        return None, "telefone com DDD"
    if not (email or tel):
        return None, "informe e-mail ou telefone do contato"
    return {"nome": nome, "cargo": str(d.get("cargo") or "").strip()[:80], "email": email, "telefone": tel}, ""


def tipo_arquivo(nome: str, dados: bytes) -> tuple[str | None, str]:
    """(mime, erro): só PDF, PNG, JPEG e WEBP, conferidos pelo conteúdo e pela extensão; até 20 MB."""
    if not dados:
        return None, "arquivo vazio"
    if len(dados) > ARQ_MAX:
        return None, "arquivo maior que 20 MB"
    if seg.eh_executavel(dados):
        return None, "arquivo executável não é aceito"
    ext = os.path.splitext((nome or "").lower())[1]
    if ext not in ARQ_TIPOS:
        return None, "tipo não aceito: PDF, PNG, JPEG ou WEBP"
    mime, assin = ARQ_TIPOS[ext]
    if not any(dados.startswith(a) for a in assin) or (ext == ".webp" and dados[8:12] != b"WEBP"):
        return None, "o conteúdo do arquivo não confere com a extensão"
    return mime, ""


# ══ Banco ════════════════════════════════════════════════════════════════════════════════════════
class Fornecedores:
    COLS = ("id", "cnpj", "nome", "nome_publico", "segmento", "site", "abrangencia", "endereco", "municipio", "uf", "ibge",
            "lat", "lon", "raio_km", "categorias", "parceiros", "descricao", "notas_internas", "status", "status_motivo",
            "status_por", "status_em", "ativo", "criado", "atualizado", "por")

    def __init__(self, hub, relogio=None, pasta: str | Path | None = None, equipamentos=None, premissas=None):
        self.hub = hub
        self.relogio = relogio or hub.relogio
        self.base = base_equipamentos(equipamentos)
        self.dias, self.dias_status = premissa_dias(premissas)
        self.pasta = Path(pasta or os.environ.get("PHYSIS_FORNECEDORES_PASTA") or (RAIZ / "dados" / "fornecedores-arquivos"))
        with hub._trava:
            hub._db.executescript(ESQUEMA)
            r = hub._db.execute("SELECT resumo FROM fornecedor_historico ORDER BY seq DESC LIMIT 1").fetchone()
            self._ultimo = r[0] if r else "0" * 64
            hub._db.commit()
        self._pendente_gestao = False

    @property
    def _db(self):
        return self.hub._db

    # ── histórico (só cresce; cadeia de resumos) ─────────────────────────────────────────────
    @staticmethod
    def _resumo(anterior, quando, quem, fornecedor, o_que, detalhe) -> str:
        return hashlib.sha256("|".join([anterior, repr(float(quando)), quem, str(fornecedor or ""), o_que, detalhe]).encode("utf-8")).hexdigest()

    def _hist(self, quem: str, fornecedor, o_que: str, detalhe: dict | None = None) -> None:
        """Chamar com a trava; só metadados (ids, campos), nunca dado pessoal de contato."""
        quando, txt = self.relogio(), json.dumps(detalhe or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        res = self._resumo(self._ultimo, quando, quem or "?", fornecedor, o_que, txt)
        self._db.execute("INSERT INTO fornecedor_historico(quando,quem,fornecedor,o_que,detalhe,anterior,resumo) VALUES(?,?,?,?,?,?,?)",
                         (quando, quem or "?", fornecedor, o_que, txt, self._ultimo, res))
        self._ultimo = res
        self.hub.registrar("fornecedor", quem or "?", {"o_que": o_que, "id": fornecedor})

    def verificar_historico(self) -> tuple[bool, int]:
        ant, n = "0" * 64, 0
        for quando, quem, f, o, det, a, r in self._db.execute(
                "SELECT quando,quem,fornecedor,o_que,detalhe,anterior,resumo FROM fornecedor_historico ORDER BY seq"):
            if a != ant or self._resumo(ant, quando, quem, f, o, det) != r:
                return False, n
            ant, n = r, n + 1
        return True, n

    def historico(self, fornecedor: int | None = None, limite: int = 200) -> dict:
        sql = "SELECT seq,quando,quem,fornecedor,o_que,detalhe FROM fornecedor_historico"
        par: tuple = ()
        if fornecedor:
            sql, par = sql + " WHERE fornecedor=?", (int(fornecedor),)
        linhas = self._db.execute(sql + " ORDER BY seq DESC LIMIT ?", (*par, int(limite))).fetchall()
        integro, n = self.verificar_historico()
        return {"ok": True, "integro": integro, "total": n, "itens": [
            {"seq": s, "quando": q, "data": _dia(q), "quem": w, "fornecedor": f, "o_que": o, "detalhe": json.loads(d)}
            for s, q, w, f, o, d in linhas]}

    # ── leitura ──────────────────────────────────────────────────────────────────────────────
    def _ler(self, ident) -> dict | None:
        try:
            r = self._db.execute("SELECT " + ",".join(self.COLS) + " FROM fornecedor WHERE id=?", (int(ident),)).fetchone()
        except (TypeError, ValueError):
            return None
        if not r:
            return None
        f = dict(zip(self.COLS, r))
        f["categorias"], f["parceiros"], f["ativo"] = json.loads(f["categorias"]), json.loads(f["parceiros"]), bool(f["ativo"])
        return f

    def _regioes(self, fid: int) -> list[dict]:
        cols = ("id", "chave", "uf", "ibge", "municipio", "prazo_entrega_dias", "pedido_minimo_brl", "atualizado", "atualizado_por")
        return [dict(zip(cols, r)) for r in self._db.execute("SELECT " + ",".join(cols) + " FROM fornecedor_regiao WHERE fornecedor=? "
                                                             "ORDER BY uf, municipio", (fid,))]

    def _ofertas(self, fid: int) -> list[dict]:
        cols = ("oferta", "equipamento", "categoria", "marca", "modelo", "equipamento_id", "ficha_url", "notas_internas")
        return [dict(zip(cols, r)) for r in self._db.execute(
            "SELECT o.id, e.id, e.categoria, e.marca, e.modelo, e.equipamento_id, e.ficha_url, e.notas_internas FROM fornecedor_oferta o "
            "JOIN fornecedor_equipamento e ON e.id=o.equipamento WHERE o.fornecedor=? ORDER BY e.categoria, e.marca, e.modelo", (fid,))]

    def _precos(self, ofertas: list[int]) -> list[dict]:
        if not ofertas:
            return []
        cols = ("id", "oferta", "uf", "ibge", "valor", "unidade", "data", "fonte", "fonte_ref", "criado", "por")
        q = ",".join("?" * len(ofertas))
        return [dict(zip(cols, r)) for r in self._db.execute(
            f"SELECT {','.join(cols)} FROM fornecedor_preco WHERE oferta IN ({q}) ORDER BY data DESC, id DESC", ofertas)]

    def _arquivos(self, fid: int | None = None, equipamento: int | None = None) -> list[dict]:
        cols = ("id", "fornecedor", "equipamento", "tipo_doc", "nome", "mime", "tamanho", "sha256", "publico", "criado", "por")
        if fid is not None:
            w, p = "fornecedor=?", (fid,)
        else:
            w, p = "equipamento=?", (equipamento,)
        return [dict(zip(cols, r), publico=bool(r[8])) for r in self._db.execute(
            f"SELECT {','.join(cols)} FROM fornecedor_arquivo WHERE {w} ORDER BY criado DESC", p)]

    def _contatos(self, fid: int) -> list[dict]:
        cols = ("id", "nome", "cargo", "email", "telefone", "consentimento", "versao_termo")
        return [dict(zip(cols, r)) for r in self._db.execute("SELECT " + ",".join(cols) + " FROM fornecedor_contato WHERE fornecedor=?", (fid,))]

    def _ids(self) -> list[int]:
        return [r[0] for r in self._db.execute("SELECT id FROM fornecedor ORDER BY nome")]

    # ── cadastro e edição ────────────────────────────────────────────────────────────────────
    def _gravar_regiao(self, fid: int, reg: dict, quem: str, prazo=None, pedido=None, tocar: bool = True) -> int:
        chave, agora = chave_regiao(reg["uf"], reg["ibge"], reg["municipio"]), self.relogio()
        r = self._db.execute("SELECT id FROM fornecedor_regiao WHERE fornecedor=? AND chave=?", (fid, chave)).fetchone()
        if r:
            sets, vals = [], []
            if prazo is not None:
                sets.append("prazo_entrega_dias=?"), vals.append(prazo)
            if pedido is not None:
                sets.append("pedido_minimo_brl=?"), vals.append(pedido)
            if tocar:
                sets += ["atualizado=?", "atualizado_por=?"]
                vals += [agora, quem]
            if sets:
                self._db.execute(f"UPDATE fornecedor_regiao SET {', '.join(sets)} WHERE id=?", (*vals, r[0]))
            return r[0]
        return self._db.execute("INSERT INTO fornecedor_regiao(fornecedor,chave,uf,ibge,municipio,prazo_entrega_dias,pedido_minimo_brl,"
                                "atualizado,atualizado_por) VALUES(?,?,?,?,?,?,?,?,?)",
                                (fid, chave, reg["uf"], reg["ibge"], reg["municipio"], prazo, pedido, agora, quem)).lastrowid

    def cadastrar(self, d: dict, quem: str) -> dict:
        f, erro = validar_cadastro(d)
        if not f:
            return {"ok": False, "erro": erro}
        regs = []
        for r in d.get("regioes") or []:
            reg, erro = validar_regiao(r)
            if not reg:
                return {"ok": False, "erro": erro}
            regs.append(reg)
        contatos = []
        for c in d.get("contatos") or []:
            c2, erro = validar_contato(c)
            if not c2:
                return {"ok": False, "erro": erro, "finalidade": FINALIDADE_CONTATO}
            contatos.append(c2)
        agora = self.relogio()
        with self.hub._trava:
            if self._db.execute("SELECT 1 FROM fornecedor WHERE cnpj=?", (f["cnpj"],)).fetchone():
                return {"ok": False, "erro": "já existe um fornecedor com este CNPJ"}
            cur = self._db.execute(
                "INSERT INTO fornecedor(cnpj,nome,nome_publico,segmento,site,abrangencia,endereco,municipio,uf,ibge,lat,lon,raio_km,"
                "categorias,parceiros,descricao,notas_internas,criado,atualizado,por) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f["cnpj"], f["nome"], f["nome_publico"], f["segmento"], f["site"], f["abrangencia"], f["endereco"], f["municipio"],
                 f["uf"], f["ibge"], f["lat"], f["lon"], f["raio_km"], json.dumps(f["categorias"]), json.dumps(f["parceiros"]),
                 f["descricao"], f["notas_internas"], agora, agora, quem))
            fid = cur.lastrowid
            if f["abrangencia"] == "local" and not regs and f["uf"]:
                regs.append({"uf": f["uf"], "ibge": f["ibge"], "municipio": f["municipio"]})       # a sede
            if f["abrangencia"] == "nacional" and not any(r["uf"] == NACIONAL for r in regs):
                regs.insert(0, {"uf": NACIONAL, "ibge": "", "municipio": ""})
            for reg in regs:
                self._gravar_regiao(fid, reg, quem)
            for c in contatos:
                self._db.execute("INSERT INTO fornecedor_contato(fornecedor,nome,cargo,email,telefone,consentimento,versao_termo,criado,por) "
                                 "VALUES(?,?,?,?,?,?,?,?,?)", (fid, c["nome"], c["cargo"], c["email"], c["telefone"], agora, VERSAO_TERMO, agora, quem))
            self._hist(quem, fid, "cadastro", {"regioes": len(regs), "contatos": len(contatos)})
            self._db.commit()
        return {"ok": True, "id": fid, "status": "em_analise"}

    def editar(self, fid: int, d: dict, quem: str) -> dict:
        if not self._ler(fid):
            return {"ok": False, "erro": "fornecedor desconhecido", "codigo": 404}
        campos, erro = validar_cadastro({k: v for k, v in (d or {}).items() if k != "ativo"}, parcial=True)
        if campos is None:
            return {"ok": False, "erro": erro}
        if isinstance((d or {}).get("ativo"), bool):
            campos["ativo"] = 1 if d["ativo"] else 0
        if not campos:
            return {"ok": True}
        with self.hub._trava:
            if "cnpj" in campos and self._db.execute("SELECT 1 FROM fornecedor WHERE cnpj=? AND id<>?", (campos["cnpj"], fid)).fetchone():
                return {"ok": False, "erro": "CNPJ já cadastrado em outro fornecedor"}
            for k in ("categorias", "parceiros"):
                if k in campos:
                    campos[k] = json.dumps(campos[k])
            sets = ", ".join(f"{k}=?" for k in campos)
            self._db.execute(f"UPDATE fornecedor SET {sets}, atualizado=? WHERE id=?", (*campos.values(), self.relogio(), int(fid)))
            self._hist(quem, int(fid), "editado", {"campos": sorted(campos)})
            self._db.commit()
        return {"ok": True}

    def curar(self, fid: int, status: str, motivo: str, quem: str, eh_direcao: bool) -> dict:
        if not eh_direcao:
            return {"ok": False, "erro": "só a direção muda a curadoria", "codigo": 403}
        if status not in STATUS:
            return {"ok": False, "erro": "status: " + ", ".join(STATUS)}
        f = self._ler(fid)
        if not f:
            return {"ok": False, "erro": "fornecedor desconhecido", "codigo": 404}
        motivo = str(motivo or "").strip()[:300]
        if status == "aprovado":
            pend = []
            if not self._regioes(fid):
                pend.append("pelo menos uma região atendida")
            if not self._ofertas(fid) and not f["parceiros"]:
                pend.append("pelo menos um equipamento oferecido ou um parceiro de instalação ligado")
            if pend:
                return {"ok": False, "erro": "falta para aprovar: " + "; ".join(pend), "pendencias": pend}
        if status == "suspenso" and not motivo:
            return {"ok": False, "erro": "diga o motivo da suspensão"}
        with self.hub._trava:
            self._db.execute("UPDATE fornecedor SET status=?, status_motivo=?, status_por=?, status_em=?, atualizado=? WHERE id=?",
                             (status, motivo, quem, self.relogio(), self.relogio(), int(fid)))
            self._hist(quem, int(fid), "curadoria", {"status": status})
            self._db.commit()
        return {"ok": True, "status": status}

    # ── regiões ──────────────────────────────────────────────────────────────────────────────
    def regiao(self, fid: int, d: dict, quem: str) -> dict:
        if not self._ler(fid):
            return {"ok": False, "erro": "fornecedor desconhecido", "codigo": 404}
        reg, erro = validar_regiao(d)
        if not reg:
            return {"ok": False, "erro": erro}
        prazo, pedido = d.get("prazo_entrega_dias"), d.get("pedido_minimo_brl")
        if prazo is not None and (isinstance(prazo, bool) or not isinstance(prazo, int) or not 0 <= prazo <= 365):
            return {"ok": False, "erro": "prazo de entrega em dias (0 a 365)"}
        if pedido is not None and (isinstance(pedido, bool) or not isinstance(pedido, (int, float)) or pedido < 0):
            return {"ok": False, "erro": "pedido mínimo em reais (0 ou mais)"}
        with self.hub._trava:
            rid = self._gravar_regiao(int(fid), reg, quem, prazo, pedido)
            self._hist(quem, int(fid), "regiao", {"regiao": chave_regiao(reg["uf"], reg["ibge"], reg["municipio"])})
            self._fechar_tarefas_se_em_dia(reg, quem)
            self._db.commit()
        self._sincronizar_se_preciso(quem)
        return {"ok": True, "id": rid}

    def regiao_remover(self, fid: int, rid: int, quem: str) -> dict:
        with self.hub._trava:
            cur = self._db.execute("DELETE FROM fornecedor_regiao WHERE id=? AND fornecedor=?", (int(rid), int(fid)))
            if cur.rowcount:
                self._hist(quem, int(fid), "regiao removida", {"regiao_id": int(rid)})
            self._db.commit()
        return {"ok": cur.rowcount > 0}

    def regiao_conferida(self, fid: int, rid: int, quem: str) -> dict:
        """A equipe conferiu os dados desta região com o fornecedor (telefone, e-mail, catálogo): renova a data."""
        with self.hub._trava:
            r = self._db.execute("SELECT uf, ibge, municipio FROM fornecedor_regiao WHERE id=? AND fornecedor=?", (int(rid), int(fid))).fetchone()
            if not r:
                return {"ok": False, "erro": "região desconhecida", "codigo": 404}
            self._db.execute("UPDATE fornecedor_regiao SET atualizado=?, atualizado_por=? WHERE id=?", (self.relogio(), quem, int(rid)))
            self._hist(quem, int(fid), "regiao conferida", {"regiao": chave_regiao(*r)})
            self._fechar_tarefas_se_em_dia({"uf": r[0], "ibge": r[1], "municipio": r[2]}, quem)
            self._db.commit()
        self._sincronizar_se_preciso(quem)
        return {"ok": True}

    # ── equipamentos (planilha) e ofertas ────────────────────────────────────────────────────
    def _validar_equip(self, d: dict, atual: dict | None = None) -> tuple[dict | None, str]:
        e = dict(atual or {"categoria": "", "marca": "", "modelo": "", "equipamento_id": "", "ficha_url": "", "notas_internas": ""})
        for k in ("categoria", "marca", "modelo", "equipamento_id", "notas_internas"):
            if k in d:
                e[k] = str(d.get(k) or "").strip()[: {"marca": 80, "modelo": 120, "notas_internas": 2000}.get(k, 60)]
        if e["categoria"] not in CATEGORIAS or e["categoria"] == "instalacao":
            return None, "categoria de equipamento: " + ", ".join(k for k in CATEGORIAS if k != "instalacao") + \
                         " (instalação/integração: ligar um profissional parceiro ao fornecedor)"
        if e["equipamento_id"]:
            b = self.base.get(e["equipamento_id"])
            if not b:
                return None, f"equipamento_id fora da base de equipamentos: {e['equipamento_id']}"
            if b["categoria"] != e["categoria"]:
                return None, f"equipamento_id {e['equipamento_id']} é da categoria {b['categoria']}"
        if "ficha_url" in d:
            s, erro = _site(d.get("ficha_url"))
            if s is None:
                return None, "folha de dados: endereço http(s) válido"
            e["ficha_url"] = s
        if not (e["marca"] or e["modelo"] or e["equipamento_id"]):
            return None, "informe marca/modelo ou o id da base de equipamentos"
        return e, ""

    def _upsert_equip(self, e: dict, quem: str) -> int:
        r = self._db.execute("SELECT id FROM fornecedor_equipamento WHERE categoria=? AND marca=? AND modelo=?",
                             (e["categoria"], e["marca"], e["modelo"])).fetchone()
        agora = self.relogio()
        if r:
            if e.get("equipamento_id"):
                self._db.execute("UPDATE fornecedor_equipamento SET equipamento_id=?, atualizado=? WHERE id=?", (e["equipamento_id"], agora, r[0]))
            return r[0]
        return self._db.execute("INSERT INTO fornecedor_equipamento(categoria,marca,modelo,equipamento_id,ficha_url,notas_internas,criado,atualizado,por) "
                                "VALUES(?,?,?,?,?,?,?,?,?)", (e["categoria"], e["marca"], e["modelo"], e.get("equipamento_id", ""),
                                                              e.get("ficha_url", ""), e.get("notas_internas", ""), agora, agora, quem)).lastrowid

    def equipamento(self, d: dict, quem: str) -> dict:
        """Cria (sem id) ou edita (com id) uma linha da planilha de equipamentos."""
        d = d or {}
        atual = None
        if d.get("id"):
            cols = ("categoria", "marca", "modelo", "equipamento_id", "ficha_url", "notas_internas")
            r = self._db.execute("SELECT " + ",".join(cols) + " FROM fornecedor_equipamento WHERE id=?", (int(d["id"]),)).fetchone()
            if not r:
                return {"ok": False, "erro": "equipamento desconhecido", "codigo": 404}
            atual = dict(zip(cols, r))
        e, erro = self._validar_equip(d, atual)
        if not e:
            return {"ok": False, "erro": erro}
        with self.hub._trava:
            if atual:
                try:
                    self._db.execute("UPDATE fornecedor_equipamento SET categoria=?, marca=?, modelo=?, equipamento_id=?, ficha_url=?, "
                                     "notas_internas=?, atualizado=? WHERE id=?", (e["categoria"], e["marca"], e["modelo"], e["equipamento_id"],
                                                                                   e["ficha_url"], e["notas_internas"], self.relogio(), int(d["id"])))
                except Exception:      # noqa: BLE001 — UNIQUE(categoria, marca, modelo)
                    return {"ok": False, "erro": "já existe este equipamento na planilha"}
                eid = int(d["id"])
            else:
                eid = self._upsert_equip(e, quem)
            self._hist(quem, None, "equipamento", {"equipamento": eid, "campos": sorted(k for k in d if k != "id")})
            self._db.commit()
        return {"ok": True, "id": eid}

    def equipamento_remover(self, eid: int, quem: str) -> dict:
        with self.hub._trava:
            cur = self._db.execute("DELETE FROM fornecedor_equipamento WHERE id=?", (int(eid),))
            if cur.rowcount:
                ofs = [r[0] for r in self._db.execute("SELECT id FROM fornecedor_oferta WHERE equipamento=?", (int(eid),))]
                self._db.execute("DELETE FROM fornecedor_oferta WHERE equipamento=?", (int(eid),))
                if ofs:
                    self._db.execute(f"DELETE FROM fornecedor_preco WHERE oferta IN ({','.join('?' * len(ofs))})", ofs)
                self._apagar_arquivos("equipamento=?", (int(eid),))
                self._hist(quem, None, "equipamento removido", {"equipamento": int(eid)})
            self._db.commit()
        return {"ok": cur.rowcount > 0}

    def oferta(self, fid: int, d: dict, quem: str) -> dict:
        """Liga o fornecedor a um equipamento da planilha ({equipamento: id}) ou cria o equipamento e liga."""
        if not self._ler(fid):
            return {"ok": False, "erro": "fornecedor desconhecido", "codigo": 404}
        d = d or {}
        with self.hub._trava:
            if d.get("equipamento"):
                if not self._db.execute("SELECT 1 FROM fornecedor_equipamento WHERE id=?", (int(d["equipamento"]),)).fetchone():
                    return {"ok": False, "erro": "equipamento desconhecido"}
                eid = int(d["equipamento"])
            else:
                e, erro = self._validar_equip(d)
                if not e:
                    return {"ok": False, "erro": erro}
                eid = self._upsert_equip(e, quem)
            r = self._db.execute("SELECT id FROM fornecedor_oferta WHERE fornecedor=? AND equipamento=?", (int(fid), eid)).fetchone()
            oid = r[0] if r else self._db.execute("INSERT INTO fornecedor_oferta(fornecedor,equipamento,criado,por) VALUES(?,?,?,?)",
                                                   (int(fid), eid, self.relogio(), quem)).lastrowid
            self._hist(quem, int(fid), "oferta", {"equipamento": eid})
            self._db.commit()
        return {"ok": True, "id": oid, "equipamento": eid}

    def oferta_remover(self, fid: int, oid: int, quem: str) -> dict:
        with self.hub._trava:
            cur = self._db.execute("DELETE FROM fornecedor_oferta WHERE id=? AND fornecedor=?", (int(oid), int(fid)))
            if cur.rowcount:
                self._db.execute("DELETE FROM fornecedor_preco WHERE oferta=?", (int(oid),))
                self._hist(quem, int(fid), "oferta removida", {"oferta": int(oid)})
            self._db.commit()
        return {"ok": cur.rowcount > 0}

    def preco(self, fid: int, d: dict, quem: str) -> dict:
        f = self._ler(fid)
        if not f:
            return {"ok": False, "erro": "fornecedor desconhecido", "codigo": 404}
        try:
            oid = int((d or {}).get("oferta"))
        except (TypeError, ValueError):
            oid = 0
        if not self._db.execute("SELECT 1 FROM fornecedor_oferta WHERE id=? AND fornecedor=?", (oid, int(fid))).fetchone():
            return {"ok": False, "erro": "escolha um equipamento deste fornecedor"}
        p, erro = validar_preco(d, _hoje(self.relogio()))
        if not p:
            return {"ok": False, "erro": erro}
        regs = self._regioes(int(fid))
        atende = (p["uf"] == NACIONAL or any(r["uf"] in (p["uf"], NACIONAL) for r in regs) if not p["ibge"]
                  else alcance(f, regs, p["uf"], p["ibge"])[0] > 0)
        if not atende:
            return {"ok": False, "erro": "o fornecedor não atende a região deste preço"}
        with self.hub._trava:
            pid = self._db.execute("INSERT INTO fornecedor_preco(oferta,uf,ibge,valor,unidade,data,fonte,fonte_ref,criado,por) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                   (oid, p["uf"], p["ibge"], p["valor"], p["unidade"], p["data"], p["fonte"], p["fonte_ref"], self.relogio(), quem)).lastrowid
            self._hist(quem, int(fid), "preco", {"oferta": oid, "uf": p["uf"], "data": p["data"], "fonte": p["fonte"]})
            self._db.commit()
        return {"ok": True, "id": pid}

    # ── contatos (LGPD) ──────────────────────────────────────────────────────────────────────
    def contato(self, fid: int, d: dict, quem: str) -> dict:
        if not self._ler(fid):
            return {"ok": False, "erro": "fornecedor desconhecido", "codigo": 404}
        c, erro = validar_contato(d)
        if not c:
            return {"ok": False, "erro": erro, "finalidade": FINALIDADE_CONTATO}
        agora = self.relogio()
        with self.hub._trava:
            cid = self._db.execute("INSERT INTO fornecedor_contato(fornecedor,nome,cargo,email,telefone,consentimento,versao_termo,criado,por) "
                                   "VALUES(?,?,?,?,?,?,?,?,?)", (int(fid), c["nome"], c["cargo"], c["email"], c["telefone"], agora,
                                                                 VERSAO_TERMO, agora, quem)).lastrowid
            self._hist(quem, int(fid), "contato", {"contato": cid, "termo": VERSAO_TERMO})
            self._db.commit()
        return {"ok": True, "id": cid}

    def contato_remover(self, fid: int, cid: int, quem: str) -> dict:
        """Eliminação (LGPD art. 18 VI): apaga o contato; o histórico só tem o id."""
        with self.hub._trava:
            cur = self._db.execute("DELETE FROM fornecedor_contato WHERE id=? AND fornecedor=?", (int(cid), int(fid)))
            if cur.rowcount:
                self._hist(quem, int(fid), "contato apagado (LGPD)", {"contato": int(cid)})
            self._db.commit()
        return {"ok": cur.rowcount > 0}

    # ── arquivos (catálogos e folhas de dados) ───────────────────────────────────────────────
    def arquivo_por(self, nome: str, dados: bytes, quem: str, fornecedor: int | None = None, equipamento: int | None = None,
                    tipo_doc: str = "catalogo") -> dict:
        if bool(fornecedor) == bool(equipamento):
            return {"ok": False, "erro": "diga o fornecedor ou o equipamento do arquivo"}
        if fornecedor and not self._ler(fornecedor):
            return {"ok": False, "erro": "fornecedor desconhecido", "codigo": 404}
        if equipamento and not self._db.execute("SELECT 1 FROM fornecedor_equipamento WHERE id=?", (int(equipamento),)).fetchone():
            return {"ok": False, "erro": "equipamento desconhecido", "codigo": 404}
        if tipo_doc not in ("catalogo", "ficha", "outro"):
            return {"ok": False, "erro": "tipo: catalogo, ficha ou outro"}
        nome = (nome or "arquivo").replace("\\", "/").rsplit("/", 1)[-1].strip()[:120] or "arquivo"
        mime, erro = tipo_arquivo(nome, dados)
        if not mime:
            return {"ok": False, "erro": erro}
        sha = hashlib.sha256(dados).hexdigest()
        self.pasta.mkdir(parents=True, exist_ok=True)
        arq = sha + os.path.splitext(nome.lower())[1]           # nome no disco = resumo (sem nada vindo de quem enviou)
        destino = self.pasta / arq
        if not destino.is_file():
            tmp = destino.with_suffix(destino.suffix + ".tmp")
            tmp.write_bytes(dados)
            os.replace(tmp, destino)
        with self.hub._trava:
            aid = self._db.execute("INSERT INTO fornecedor_arquivo(fornecedor,equipamento,tipo_doc,nome,mime,tamanho,sha256,arquivo,criado,por) "
                                   "VALUES(?,?,?,?,?,?,?,?,?,?)", (fornecedor, equipamento, tipo_doc, nome, mime, len(dados), sha, arq,
                                                                   self.relogio(), quem)).lastrowid
            self._hist(quem, fornecedor, "arquivo", {"arquivo": aid, "equipamento": equipamento, "sha256": sha, "bytes": len(dados)})
            self._db.commit()
        return {"ok": True, "id": aid, "sha256": sha, "tamanho": len(dados)}

    def arquivo(self, aid: int, equipe: bool) -> tuple[str, str, bytes] | None:
        """(nome, mime, bytes). Equipe: qualquer um. Cliente: só arquivo público de fornecedor aprovado e ativo."""
        r = self._db.execute("SELECT fornecedor, nome, mime, sha256, arquivo, publico FROM fornecedor_arquivo WHERE id=?", (int(aid),)).fetchone()
        if not r:
            return None
        if not equipe:
            f = self._ler(r[0]) if r[0] else None
            if not r[5] or not f or f["status"] != "aprovado" or not f["ativo"]:
                return None
        try:
            dados = (self.pasta / r[4]).read_bytes()
        except OSError:
            return None
        if hashlib.sha256(dados).hexdigest() != r[3]:
            return None                                          # arquivo mexido no disco: não entrega
        return r[1], r[2], dados

    def arquivo_publico(self, aid: int, publico: bool, quem: str, eh_direcao: bool) -> dict:
        if not eh_direcao:
            return {"ok": False, "erro": "só a direção torna um arquivo público", "codigo": 403}
        with self.hub._trava:
            r = self._db.execute("SELECT fornecedor FROM fornecedor_arquivo WHERE id=?", (int(aid),)).fetchone()
            if not r:
                return {"ok": False, "erro": "arquivo desconhecido", "codigo": 404}
            self._db.execute("UPDATE fornecedor_arquivo SET publico=? WHERE id=?", (1 if publico else 0, int(aid)))
            self._hist(quem, r[0], "arquivo publico" if publico else "arquivo interno", {"arquivo": int(aid)})
            self._db.commit()
        return {"ok": True}

    def _apagar_arquivos(self, onde: str, par: tuple) -> None:
        for (arq,) in self._db.execute(f"SELECT arquivo FROM fornecedor_arquivo WHERE {onde}", par).fetchall():
            self._db.execute(f"DELETE FROM fornecedor_arquivo WHERE {onde} AND arquivo=?", (*par, arq))
            if not self._db.execute("SELECT 1 FROM fornecedor_arquivo WHERE arquivo=?", (arq,)).fetchone():
                try:
                    (self.pasta / arq).unlink()
                except OSError:
                    pass

    def arquivo_remover(self, aid: int, quem: str) -> dict:
        with self.hub._trava:
            r = self._db.execute("SELECT fornecedor FROM fornecedor_arquivo WHERE id=?", (int(aid),)).fetchone()
            if not r:
                return {"ok": False, "erro": "arquivo desconhecido", "codigo": 404}
            self._apagar_arquivos("id=?", (int(aid),))
            self._hist(quem, r[0], "arquivo removido", {"arquivo": int(aid)})
            self._db.commit()
        return {"ok": True}

    def apagar(self, fid: int, quem: str) -> dict:
        with self.hub._trava:
            cur = self._db.execute("DELETE FROM fornecedor WHERE id=?", (int(fid),))
            if cur.rowcount:
                ofs = [r[0] for r in self._db.execute("SELECT id FROM fornecedor_oferta WHERE fornecedor=?", (int(fid),))]
                if ofs:
                    self._db.execute(f"DELETE FROM fornecedor_preco WHERE oferta IN ({','.join('?' * len(ofs))})", ofs)
                for t in ("fornecedor_oferta", "fornecedor_regiao", "fornecedor_contato"):
                    self._db.execute(f"DELETE FROM {t} WHERE fornecedor=?", (int(fid),))
                self._apagar_arquivos("fornecedor=?", (int(fid),))
                self._hist(quem, int(fid), "apagado", {})
            self._db.commit()
        return {"ok": cur.rowcount > 0}

    # ── visões ───────────────────────────────────────────────────────────────────────────────
    def _completo(self, f: dict, agora: float) -> dict:
        regs, ofs = self._regioes(f["id"]), self._ofertas(f["id"])
        precos = [p for p in self._precos([o["oferta"] for o in ofs]) if preco_mostravel(p)]
        for r in regs:
            r.update(data=_dia(r["atualizado"]), desatualizado=desatualizado(r["atualizado"], agora, self.dias),
                     rotulo=rotulo_regiao(r["uf"], r["ibge"], r["municipio"]))
        for o in ofs:
            o["precos"] = [dict(p, fonte_nome=FONTES_PRECO[p["fonte"]]) for p in precos if p["oferta"] == o["oferta"]]
        ultima = min((r["atualizado"] for r in regs), default=None)
        return dict(f, regioes=regs, ofertas=ofs, contatos=self._contatos(f["id"]), arquivos=self._arquivos(f["id"]),
                    desatualizado=any(r["desatualizado"] for r in regs), ultima_atualizacao=_dia(ultima) if ultima else None,
                    abrangencia_nome=ABRANGENCIAS.get(f["abrangencia"], f["abrangencia"]))

    def interno(self) -> dict:
        """Planilha da Gestão (só equipe): fornecedores completos e equipamentos."""
        agora = self.relogio()
        forns = [self._completo(self._ler(i), agora) for i in self._ids()]
        cols = ("id", "categoria", "marca", "modelo", "equipamento_id", "ficha_url", "notas_internas", "atualizado", "por")
        equips = []
        for r in self._db.execute("SELECT " + ",".join(cols) + " FROM fornecedor_equipamento ORDER BY categoria, marca, modelo"):
            e = dict(zip(cols, r))
            e["fornecedores"] = [x for (x,) in self._db.execute("SELECT fornecedor FROM fornecedor_oferta WHERE equipamento=?", (e["id"],))]
            e["arquivos"] = self._arquivos(equipamento=e["id"])
            e["base"] = self.base.get(e["equipamento_id"], {}).get("descricao", "")
            equips.append(e)
        return {"ok": True, "fornecedores": forns, "equipamentos": equips, "categorias": CATEGORIAS, "abrangencias": ABRANGENCIAS,
                "status": STATUS, "fontes_preco": FONTES_PRECO, "base": self.base, "responsavel": RESPONSAVEL,
                "dias_desatualizado": self.dias, "premissa": {"id": PREMISSA_DIAS, "status": self.dias_status}, "hoje": _hoje(agora)}

    def _publico(self, f: dict, linha: dict | None, nivel: int, uf: str, ibge: str, agora: float) -> dict:
        """Só campos públicos. Preço: só de catálogo, da região, com data e fonte. Arquivo: só o marcado público."""
        ofs = self._ofertas(f["id"])
        precos = [p for p in self._precos([o["oferta"] for o in ofs])
                  if preco_mostravel(p) and p["fonte"] == "catalogo" and (p["uf"] == NACIONAL or (p["uf"] == uf and p["ibge"] in ("", ibge)))]
        out_ofs = []
        for o in ofs:
            ps = [p for p in precos if p["oferta"] == o["oferta"]]
            out_ofs.append({"categoria": o["categoria"], "categoria_nome": CATEGORIAS[o["categoria"]], "marca": o["marca"], "modelo": o["modelo"],
                            "equipamento_id": o["equipamento_id"],
                            "precos": [{"valor": p["valor"], "unidade": p["unidade"], "data": p["data"], "fonte": FONTES_PRECO[p["fonte"]],
                                        "regiao": rotulo_regiao(p["uf"], p["ibge"])} for p in ps[:1]]})
        return {"id": f["id"], "nome": f["nome_publico"], "site": f["site"], "descricao": f["descricao"],
                "abrangencia": ABRANGENCIAS.get(f["abrangencia"], ""), "alcance": NIVEIS[nivel],
                "regiao": rotulo_regiao(linha["uf"], linha["ibge"], linha["municipio"]) if linha else "",
                "ultima_atualizacao": _dia(linha["atualizado"]) if linha else None,
                "desatualizado": desatualizado(linha["atualizado"], agora, self.dias) if linha else True,
                "prazo_entrega_dias": linha.get("prazo_entrega_dias") if linha else None,
                "pedido_minimo_brl": linha.get("pedido_minimo_brl") if linha else None,
                "categorias": sorted({o["categoria"] for o in ofs} | set(f["categorias"])),
                "produtos": out_ofs,
                "catalogos": [{"id": a["id"], "nome": a["nome"], "tipo": a["mime"]} for a in self._arquivos(f["id"]) if a["publico"]]}

    def _itens(self, itens) -> list[dict]:
        out = []
        for it in itens or []:
            it = str(it or "").strip()[:60]
            if it in self.base:
                out.append({"id": it, "categoria": self.base[it]["categoria"], "nome": self.base[it]["descricao"]})
            elif it in CATEGORIAS and not any(x["categoria"] == it and not x["id"] for x in out):
                out.append({"id": "", "categoria": it, "nome": CATEGORIAS[it]})
        return out[:12]

    def na_regiao(self, uf: str = "", ibge: str = "", municipio: str = "", itens=None, equipe: bool = False,
                  lat=None, lon=None) -> dict:
        """Aba Energia solar: fornecedores da região, município → estado → Brasil (cada passo só se o anterior não tiver
        ninguém), por item do projeto. Cliente: só aprovado e ativo, só campos públicos; equipe: tudo."""
        uf, ibge, municipio = str(uf or "").strip().upper()[:2], str(ibge or "").strip()[:7], str(municipio or "").strip()[:80]
        base_resp = {"ok": True, "dias_desatualizado": self.dias, "premissa": {"id": PREMISSA_DIAS, "status": self.dias_status},
                     "responsavel": RESPONSAVEL["nome"] if equipe else None}
        if uf not in UFS:
            return dict(base_resp, nivel="sem_local", aviso="local não informado — preencha no Início", fornecedores=[], itens=[])
        agora = self.relogio()
        cand = []
        for i in self._ids():
            f = self._ler(i)
            if not equipe and (f["status"] != "aprovado" or not f["ativo"]):
                continue
            n, linha = alcance(f, self._regioes(i), uf, ibge, municipio, lat, lon)
            if n:
                cand.append((n, linha, f))

        def cascata(lista):
            nivel = max((n for n, _, _ in lista), default=0)
            return nivel, [x for x in lista if x[0] == nivel]

        def mostrar(n, linha, f):
            if equipe:
                c = self._completo(f, agora)
                c.update(alcance=NIVEIS[n], regiao=rotulo_regiao(linha["uf"], linha["ibge"], linha["municipio"]) if linha else "",
                         ultima_atualizacao=_dia(linha["atualizado"]) if linha else None,
                         desatualizado=desatualizado(linha["atualizado"], agora, self.dias) if linha else True)
                return c
            return self._publico(f, linha, n, uf, ibge, agora)

        nivel, sel = cascata(cand)
        forns = sorted((mostrar(*x) for x in sel), key=lambda x: (x["desatualizado"], x.get("nome_publico", x["nome"]).lower()))
        out_itens = []
        for it in self._itens(itens):
            com = []
            for n, linha, f in cand:
                if it["categoria"] == "instalacao":
                    if f["parceiros"]:
                        com.append((n, linha, f, "categoria"))
                    continue
                ofs = self._ofertas(f["id"])
                if it["id"] and any(o["equipamento_id"] == it["id"] for o in ofs):
                    com.append((n, linha, f, "exato"))
                elif any(o["categoria"] == it["categoria"] for o in ofs) or it["categoria"] in f["categorias"]:
                    com.append((n, linha, f, "categoria"))
            nv = max((x[0] for x in com), default=0)
            lst = [dict(mostrar(n, linha, f), casamento=c) for n, linha, f, c in com if n == nv]
            lst.sort(key=lambda x: (x["casamento"] != "exato", x["desatualizado"], x.get("nome_publico", x["nome"]).lower()))
            item = dict(it, nivel=NIVEIS[nv], rotulo=rotulo_nivel(nv, uf, municipio), fornecedores=lst)
            if it["categoria"] == "instalacao":
                item["parceiros_vitrine"] = "/api/parceiros?servico=solar&uf=" + uf      # o cliente pede orçamento lá
            out_itens.append(item)
        return dict(base_resp, nivel=NIVEIS[nivel], rotulo=rotulo_nivel(nivel, uf, municipio),
                    local={"uf": uf, "municipio": municipio, "ibge": ibge}, fornecedores=forns, itens=out_itens)

    # ── fila por região e tarefas na Gestão ──────────────────────────────────────────────────
    def fila(self) -> dict:
        agora, regs = self.relogio(), {}
        for fid, chave, uf, ibge, mun, atu in self._db.execute("SELECT fornecedor, chave, uf, ibge, municipio, atualizado FROM fornecedor_regiao"):
            g = regs.setdefault(chave, {"chave": chave, "uf": uf, "ibge": ibge, "municipio": mun, "rotulo": rotulo_regiao(uf, ibge, mun),
                                        "fornecedores": 0, "desatualizados": 0, "mais_antiga": None})
            g["fornecedores"] += 1
            g["desatualizados"] += desatualizado(atu, agora, self.dias)
            g["mais_antiga"] = atu if g["mais_antiga"] is None else min(g["mais_antiga"], atu)
        try:
            loc = self.hub.local_da_instalacao()
        except Exception:          # noqa: BLE001
            loc = {}
        if loc.get("uf") in UFS:
            ch = chave_regiao(loc["uf"], loc.get("ibge", ""), loc.get("municipio", ""))
            regs.setdefault(ch, {"chave": ch, "uf": loc["uf"], "ibge": loc.get("ibge", ""), "municipio": loc.get("municipio", ""),
                                 "rotulo": rotulo_regiao(loc["uf"], loc.get("ibge", ""), loc.get("municipio", "")),
                                 "fornecedores": 0, "desatualizados": 0, "mais_antiga": None})["instalacao"] = True
        abertas = {c: t for t, c in self._db.execute("SELECT id, chave FROM fornecedor_tarefa WHERE estado='aberta'")}
        lst = []
        for g in regs.values():
            g["tarefa"] = abertas.get(g["chave"])
            g["mais_antiga_data"] = _dia(g["mais_antiga"]) if g["mais_antiga"] else None
            g["situacao"] = "sem fornecedores" if not g["fornecedores"] else "desatualizada" if g["desatualizados"] else "em dia"
            lst.append(g)
        lst.sort(key=lambda g: (g["situacao"] == "em dia", -g["desatualizados"], g["mais_antiga"] or 0))
        return {"ok": True, "responsavel": RESPONSAVEL, "dias_desatualizado": self.dias, "regioes": lst,
                "tarefas": self.tarefas()}

    def tarefas(self) -> list[dict]:
        cols = ("id", "chave", "uf", "ibge", "municipio", "titulo", "responsavel", "prazo", "estado", "criado", "por", "fechado", "gestao")
        return [dict(zip(cols, r)) for r in self._db.execute("SELECT " + ",".join(cols) + " FROM fornecedor_tarefa ORDER BY criado DESC LIMIT 200")]

    def _gestao_sincronizar(self, quem: str) -> bool:
        """Grava a lista de tarefas na chave da Gestão (com controle de versão; tenta de novo se outra pessoa gravou)."""
        tarefas = [{"id": t["id"], "titulo": t["titulo"], "responsavel": t["responsavel"], "area": RESPONSAVEL["area"],
                    "origem": "fornecedores", "regiao": {"uf": t["uf"], "ibge": t["ibge"], "municipio": t["municipio"]},
                    "prazo": t["prazo"], "estado": t["estado"], "criado": _dia(t["criado"]), "por": t["por"]} for t in self.tarefas()]
        valor = json.dumps({"_formato": "physis-fornecedores-tarefas/1", "tarefas": tarefas}, ensure_ascii=False)
        for _ in range(3):
            atual = self.hub.gestao_ler().get(CHAVE_GESTAO)
            r = self.hub.gestao_gravar(CHAVE_GESTAO, valor, atual["versao"] if atual else 0, quem)
            if r.get("ok"):
                return True
        return False

    def _sincronizar_se_preciso(self, quem: str) -> None:
        if self._pendente_gestao:
            self._pendente_gestao = False
            self._gestao_sincronizar(quem)

    def pedir_atualizacao(self, d: dict, quem: str) -> dict:
        reg, erro = validar_regiao(d or {})
        if not reg:
            return {"ok": False, "erro": erro}
        prazo = str((d or {}).get("prazo") or "")
        if prazo and not _DATA.match(prazo):
            return {"ok": False, "erro": "prazo no formato AAAA-MM-DD"}
        chave = chave_regiao(reg["uf"], reg["ibge"], reg["municipio"])
        with self.hub._trava:
            r = self._db.execute("SELECT id FROM fornecedor_tarefa WHERE chave=? AND estado='aberta'", (chave,)).fetchone()
            if r:
                return {"ok": True, "id": r[0], "ja_existia": True}
            tid = "FN-" + datetime.fromtimestamp(self.relogio(), clima_mod.FUSO).strftime("%y%m%d") + "-" + secrets.token_hex(3).upper()
            titulo = f"Atualizar fornecedores de {rotulo_regiao(reg['uf'], reg['ibge'], reg['municipio'])}"
            self._db.execute("INSERT INTO fornecedor_tarefa(id,chave,uf,ibge,municipio,titulo,responsavel,prazo,criado,por) VALUES(?,?,?,?,?,?,?,?,?,?)",
                             (tid, chave, reg["uf"], reg["ibge"], reg["municipio"], titulo, RESPONSAVEL["id"], prazo, self.relogio(), quem))
            self._hist(quem, None, "pedir atualizacao", {"tarefa": tid, "regiao": chave})
            self._db.commit()
        ok = self._gestao_sincronizar(quem)
        if ok:
            with self.hub._trava:
                self._db.execute("UPDATE fornecedor_tarefa SET gestao=1 WHERE id=?", (tid,))
                self._db.commit()
        return {"ok": True, "id": tid, "titulo": titulo, "responsavel": RESPONSAVEL["nome"], "gestao": ok}

    def _fechar_tarefas_se_em_dia(self, reg: dict, quem: str) -> None:
        """Chamar com a trava. Região sem nenhum fornecedor desatualizado: a tarefa aberta dela fica 'feita'."""
        chave, agora = chave_regiao(reg["uf"], reg.get("ibge", ""), reg.get("municipio", "")), self.relogio()
        velhos = [a for (a,) in self._db.execute("SELECT atualizado FROM fornecedor_regiao WHERE chave=?", (chave,)) if desatualizado(a, agora, self.dias)]
        if velhos:
            return
        cur = self._db.execute("UPDATE fornecedor_tarefa SET estado='feita', fechado=?, fechado_por=? WHERE chave=? AND estado='aberta'",
                               (agora, quem, chave))
        if cur.rowcount:
            self._hist(quem, None, "tarefa feita", {"regiao": chave})
            self._pendente_gestao = True

    # ── CSV por região ───────────────────────────────────────────────────────────────────────
    def _validar_csv(self, texto: str, reg: dict) -> tuple[list[dict], list[str]]:
        texto = (texto or "").lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
        if len(texto.encode("utf-8")) > CSV_MAX:
            return [], ["CSV maior que 1 MB: divida por região"]
        if "\x00" in texto:
            return [], ["o CSV não parece ser texto"]
        primeira = texto.split("\n", 1)[0]
        sep = ";" if primeira.count(";") >= primeira.count(",") else ","
        leitor = csv.reader(io.StringIO(texto), delimiter=sep)
        try:
            cab = [c.strip().lower() for c in next(leitor)]
        except StopIteration:
            return [], ["CSV vazio"]
        desconhecidas = [c for c in cab if c not in CSV_COLUNAS]
        if desconhecidas:
            return [], ["colunas desconhecidas: " + ", ".join(desconhecidas[:5]) + " (aceitas: " + ", ".join(CSV_COLUNAS) + ")"]
        if "cnpj" not in cab or "categoria" not in cab:
            return [], ["faltam as colunas cnpj e categoria"]
        hoje, linhas, erros = _hoje(self.relogio()), [], []
        cnpjs = {c: i for i, c in self._db.execute("SELECT id, cnpj FROM fornecedor")}
        for n, cel in enumerate(leitor, start=2):
            if not any(x.strip() for x in cel):
                continue
            if len(linhas) >= CSV_LINHAS_MAX:
                erros.append(f"mais de {CSV_LINHAS_MAX} linhas")
                break
            if len(cel) != len(cab):
                erros.append(f"linha {n}: {len(cel)} colunas, esperado {len(cab)}")
                continue
            v = {k: (x.strip()[1:] if x.strip()[:2] in ("'=", "'+", "'-", "'@") else x.strip()) for k, x in zip(cab, cel)}
            cnpj = parc.so_digitos(v.get("cnpj"))
            if not parc.cnpj_valido(cnpj):
                erros.append(f"linha {n}: CNPJ inválido")
                continue
            if cnpj not in cnpjs:
                erros.append(f"linha {n}: fornecedor não cadastrado (CNPJ {cnpj}); cadastre antes de importar")
                continue
            e, erro = self._validar_equip({k: v.get(k, "") for k in ("categoria", "marca", "modelo", "equipamento_id")})
            if not e:
                erros.append(f"linha {n}: {erro}")
                continue
            linha = {"fornecedor": cnpjs[cnpj], "cnpj": cnpj, "equip": e, "prazo": None, "pedido": None, "preco": None}
            try:
                if v.get("prazo_entrega_dias"):
                    linha["prazo"] = int(v["prazo_entrega_dias"])
                    if not 0 <= linha["prazo"] <= 365:
                        raise ValueError
            except ValueError:
                erros.append(f"linha {n}: prazo de entrega em dias (0 a 365)")
                continue
            try:
                if v.get("pedido_minimo_brl"):
                    linha["pedido"] = _num_br(v["pedido_minimo_brl"])
                    if linha["pedido"] < 0 or not math.isfinite(linha["pedido"]):
                        raise ValueError
            except ValueError:
                erros.append(f"linha {n}: pedido mínimo em reais")
                continue
            if any(v.get(k) for k in ("preco", "preco_unidade", "preco_data", "preco_fonte", "preco_fonte_ref")):
                try:
                    valor = _num_br(v.get("preco"))
                except ValueError:
                    valor = None
                p, erro = validar_preco({"valor": valor, "unidade": v.get("preco_unidade"), "data": v.get("preco_data"),
                                         "fonte": v.get("preco_fonte"), "fonte_ref": v.get("preco_fonte_ref"),
                                         "uf": reg["uf"], "ibge": reg["ibge"]}, hoje)
                if not p:
                    erros.append(f"linha {n}: {erro}")
                    continue
                linha["preco"] = p
            linhas.append(linha)
        if not linhas and not erros:
            erros.append("nenhuma linha de dados")
        return linhas, erros

    @staticmethod
    def resumo_importacao(reg: dict, linhas: list[dict]) -> str:
        """Resumo SHA-256 do conteúdo canônico (mesmo resultado com ; ou , e com CRLF ou LF)."""
        return integridade.resumo({"regiao": chave_regiao(reg["uf"], reg["ibge"], reg["municipio"]), "colunas": list(CSV_COLUNAS),
                                   "linhas": [{"cnpj": x["cnpj"], "equip": {k: x["equip"][k] for k in ("categoria", "marca", "modelo", "equipamento_id")},
                                               "prazo": x["prazo"], "pedido": x["pedido"], "preco": x["preco"]} for x in linhas]})

    def importar(self, d: dict, quem: str) -> dict:
        reg, erro = validar_regiao(d or {})
        if not reg or not (d or {}).get("uf"):
            return {"ok": False, "erro": erro or "informe a região (UF)"}
        texto = str(d.get("csv") or "")
        linhas, erros = self._validar_csv(texto, reg)
        if erros:
            return {"ok": False, "erro": "CSV recusado: nada foi gravado", "erros": erros[:50]}
        resumo = self.resumo_importacao(reg, linhas)
        bruto = hashlib.sha256(texto.lstrip("﻿").replace("\r\n", "\n").encode("utf-8")).hexdigest()
        forns = sorted({x["fornecedor"] for x in linhas})
        info = {"linhas": len(linhas), "fornecedores": len(forns), "precos": sum(1 for x in linhas if x["preco"]),
                "resumo": resumo, "arquivo_sha256": bruto, "regiao": rotulo_regiao(reg["uf"], reg["ibge"], reg["municipio"])}
        if d.get("simular"):
            return dict(info, ok=True, simulado=True)
        with self.hub._trava:
            imp = self._db.execute("INSERT INTO fornecedor_importacao(chave,uf,ibge,municipio,nome_arquivo,linhas,resumo,arquivo_sha256,quando,por) "
                                   "VALUES(?,?,?,?,?,?,?,?,?,?)", (chave_regiao(reg["uf"], reg["ibge"], reg["municipio"]), reg["uf"], reg["ibge"],
                                                                   reg["municipio"], str(d.get("nome") or "")[:160], len(linhas), resumo, bruto,
                                                                   self.relogio(), quem)).lastrowid
            for x in linhas:
                eid = self._upsert_equip(x["equip"], quem)
                r = self._db.execute("SELECT id FROM fornecedor_oferta WHERE fornecedor=? AND equipamento=?", (x["fornecedor"], eid)).fetchone()
                oid = r[0] if r else self._db.execute("INSERT INTO fornecedor_oferta(fornecedor,equipamento,criado,por) VALUES(?,?,?,?)",
                                                       (x["fornecedor"], eid, self.relogio(), quem)).lastrowid
                self._gravar_regiao(x["fornecedor"], reg, quem, x["prazo"], x["pedido"])
                if x["preco"]:
                    p = x["preco"]
                    self._db.execute("INSERT INTO fornecedor_preco(oferta,uf,ibge,valor,unidade,data,fonte,fonte_ref,importacao,criado,por) "
                                     "VALUES(?,?,?,?,?,?,?,?,?,?,?)", (oid, p["uf"], p["ibge"], p["valor"], p["unidade"], p["data"], p["fonte"],
                                                                       p["fonte_ref"], imp, self.relogio(), quem))
            for fid in forns:
                self._hist(quem, fid, "importacao", {"importacao": imp, "resumo": resumo})
            self._fechar_tarefas_se_em_dia(reg, quem)
            self._db.commit()
        self._sincronizar_se_preciso(quem)
        return dict(info, ok=True, importacao=imp)

    def conferir_importacao(self, imp: int, texto: str) -> dict:
        """O arquivo guardado fora bate com a importação registrada? (mesmo resumo do conteúdo)"""
        r = self._db.execute("SELECT uf, ibge, municipio, resumo FROM fornecedor_importacao WHERE id=?", (int(imp),)).fetchone()
        if not r:
            return {"ok": False, "erro": "importação desconhecida"}
        reg = {"uf": r[0], "ibge": r[1], "municipio": r[2]}
        linhas, erros = self._validar_csv(texto, reg)
        atual = self.resumo_importacao(reg, linhas) if not erros else None
        return {"ok": True, "confere": atual == r[3], "resumo": r[3], "resumo_arquivo": atual}

    def importacoes(self) -> dict:
        cols = ("id", "chave", "uf", "ibge", "municipio", "nome_arquivo", "linhas", "resumo", "arquivo_sha256", "quando", "por")
        return {"ok": True, "importacoes": [dict(zip(cols, r)) for r in self._db.execute(
            "SELECT " + ",".join(cols) + " FROM fornecedor_importacao ORDER BY quando DESC LIMIT 200")]}

    def exportar_csv(self, uf: str, ibge: str = "", municipio: str = "") -> tuple[str | None, str]:
        reg, erro = validar_regiao({"uf": uf, "ibge": ibge, "municipio": municipio})
        if not reg or not uf:
            return None, erro or "informe a região (UF)"
        chave = chave_regiao(reg["uf"], reg["ibge"], reg["municipio"])
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";", lineterminator="\n")
        w.writerow(CSV_COLUNAS)
        fmt = lambda x: "" if x is None else (str(x).replace(".", ",") if isinstance(x, float) else str(x))
        for fid, cnpj, prazo, pedido in self._db.execute(
                "SELECT f.id, f.cnpj, r.prazo_entrega_dias, r.pedido_minimo_brl FROM fornecedor_regiao r JOIN fornecedor f ON f.id=r.fornecedor "
                "WHERE r.chave=? ORDER BY f.nome", (chave,)).fetchall():
            for o in self._ofertas(fid):
                p = next((x for x in self._precos([o["oferta"]]) if x["uf"] == reg["uf"] and x["ibge"] == reg["ibge"] and preco_mostravel(x)), None)
                w.writerow([_celula_segura(c) for c in (cnpj, o["categoria"], o["marca"], o["modelo"], o["equipamento_id"], fmt(prazo), fmt(pedido),
                                                        fmt(p["valor"]) if p else "", p["unidade"] if p else "", p["data"] if p else "",
                                                        p["fonte"] if p else "", p["fonte_ref"] if p else "")])
        return buf.getvalue(), f"fornecedores-{chave.replace(':', '-').replace('*', 'todo')}.csv"

    # ── mapa (GIS, só equipe) ────────────────────────────────────────────────────────────────
    def instalacoes_clientes(self) -> list[dict]:
        """Local das instalações dos clientes (cadastro do Início, physis-perfil.c) — só para a equipe, no mapa."""
        out = []
        try:
            linhas = self._db.execute("SELECT org, valor FROM cliente_estado WHERE chave='physis-perfil'").fetchall()
        except Exception:          # noqa: BLE001
            linhas = []
        for org, valor in linhas:
            try:
                c = (json.loads(valor) or {}).get("c") or {}
            except (ValueError, AttributeError):
                continue
            loc, _ = clima_mod.validar_local({"lat": c.get("lat"), "lon": c.get("lon")}) if c.get("lat") not in (None, "") else (None, "")
            out.append({"org": org, "municipio": str(c.get("municipio") or "")[:80], "uf": str(c.get("uf") or "").upper()[:2],
                        "ibge": str(c.get("ibge") or "")[:7], "lat": loc["lat"] if loc else None, "lon": loc["lon"] if loc else None})
        return out

    def mapa(self, abrangencia: str = "", categoria: str = "", situacao: str = "") -> dict:
        """Camadas do mapa da Gestão: fornecedores (sede, abrangência, regiões, raio) e instalações dos clientes com quantos
        fornecedores atendem cada uma (município / estado / Brasil). Filtros: abrangência, categoria, situação."""
        agora, forns = self.relogio(), []
        for i in self._ids():
            c = self._completo(self._ler(i), agora)
            cats = sorted({o["categoria"] for o in c["ofertas"]} | set(c["categorias"]) | ({"instalacao"} if c["parceiros"] else set()))
            if abrangencia and c["abrangencia"] != abrangencia:
                continue
            if categoria and categoria not in cats:
                continue
            if situacao == "desatualizado" and not c["desatualizado"] or situacao == "em_dia" and c["desatualizado"]:
                continue
            forns.append({"id": c["id"], "nome": c["nome_publico"], "abrangencia": c["abrangencia"], "status": c["status"], "ativo": c["ativo"],
                          "lat": c["lat"], "lon": c["lon"], "raio_km": c["raio_km"], "uf": c["uf"], "municipio": c["municipio"],
                          "categorias": cats, "desatualizado": c["desatualizado"], "ultima_atualizacao": c["ultima_atualizacao"],
                          "regioes": [{"uf": r["uf"], "municipio": r["municipio"], "ibge": r["ibge"], "desatualizado": r["desatualizado"]} for r in c["regioes"]],
                          "_f": c})
        clientes = []
        for cl in self.instalacoes_clientes():
            cont = {"municipio": 0, "uf": 0, "nacional": 0}
            for f in forns:
                n, _ = alcance(f["_f"], f["_f"]["regioes"], cl["uf"], cl["ibge"], cl["municipio"], cl["lat"], cl["lon"])
                if n:
                    cont[NIVEIS[n]] += 1
            clientes.append(dict(cl, fornecedores=cont, perto=cont["municipio"] > 0))
        for f in forns:
            f.pop("_f")
        return {"ok": True, "fornecedores": forns, "clientes": clientes, "abrangencias": ABRANGENCIAS, "categorias": CATEGORIAS,
                "geocodificacao": "manual (lat/lon digitados). Busca de endereço só com Nominatim hospedado pela Physis (Fase 2)."}

    # ── rotas (o servidor confere sessão, CSRF, limite por IP e senha recente antes) ─────────
    def rota(self, metodo: str, caminho: str, conta: dict | None, corpo=None, consulta: dict | None = None):
        """(código, resposta). Resposta dict, ou ("bytes", nome, mime, dados) para CSV e arquivos.
        GET  /api/fornecedores/regiao?uf&ibge&municipio&itens   cliente+ (cliente: só público)
        GET  /api/fornecedores/interno | fila | mapa | historico | importacoes | exportar | arquivo/<id>   equipe
             (arquivo/<id>: cliente só se público)
        POST /api/fornecedores/cadastro | equipamento | equipamento/remover | importar | pedir-atualizacao   equipe
        POST /api/fornecedores/arquivo?fornecedor=|equipamento=&nome=&tipo=   corpo = bytes do arquivo, equipe
        POST /api/fornecedores/arquivo/publico (direção) | arquivo/remover (equipe)
        POST /api/fornecedores/<id>/(editar|regiao|regiao/remover|regiao/conferida|oferta|oferta/remover|preco|contato|
             contato/remover|curadoria|apagar)   equipe; curadoria e apagar só a direção"""
        if not caminho.startswith("/api/fornecedores"):
            return None
        if not conta:
            return 401, {"ok": False, "erro": "entre com usuario e senha", "login": True}
        consulta = consulta or {}
        g = lambda k, n=80: str((consulta.get(k) or [""])[0])[:n]
        equipe, direcao, quem = seg.pode(conta, seg.EQUIPE), seg.pode(conta, seg.DIRECAO), conta.get("usuario") or "?"
        negado = (403, {"ok": False, "erro": "o seu papel não permite esta ação"})
        resp = lambda r: (r.pop("codigo", 200 if r.get("ok") else 400), r)
        p = caminho.rstrip("/")
        if metodo == "GET":
            if p == "/api/fornecedores/regiao":
                if not seg.pode(conta, seg.CLIENTE):
                    return negado
                uf, ibge, mun, lat, lon = g("uf", 2), g("ibge", 7), g("municipio"), None, None
                if not uf:
                    try:
                        loc = self.hub.local_da_instalacao()
                    except Exception:      # noqa: BLE001
                        loc = {}
                    uf, ibge, mun, lat, lon = loc.get("uf") or "", loc.get("ibge") or "", loc.get("municipio") or "", loc.get("lat"), loc.get("lon")
                return 200, self.na_regiao(uf, ibge, mun, [x for x in g("itens", 800).split(",") if x], equipe=equipe, lat=lat, lon=lon)
            m = re.fullmatch(r"/api/fornecedores/arquivo/(\d{1,12})", p)
            if m:
                a = self.arquivo(int(m.group(1)), equipe)
                if not a:
                    return 404, {"ok": False, "erro": "arquivo não encontrado"}
                return 200, ("bytes", a[0], a[1], a[2])
            if not equipe:
                return negado
            if p == "/api/fornecedores/interno":
                return 200, self.interno()
            if p == "/api/fornecedores/fila":
                return 200, self.fila()
            if p == "/api/fornecedores/mapa":
                return 200, self.mapa(g("abrangencia", 20), g("categoria", 20), g("situacao", 20))
            if p == "/api/fornecedores/importacoes":
                return 200, self.importacoes()
            if p == "/api/fornecedores/historico":
                f = g("fornecedor", 12)
                return 200, self.historico(int(f) if f.isdigit() else None)
            if p == "/api/fornecedores/exportar":
                txt, nome = self.exportar_csv(g("uf", 2), g("ibge", 7), g("municipio"))
                if txt is None:
                    return 400, {"ok": False, "erro": nome}
                return 200, ("bytes", nome, "text/csv; charset=utf-8", ("﻿" + txt).encode("utf-8"))
            return 404, {"ok": False, "erro": "rota desconhecida"}
        if metodo != "POST":
            return 405, {"ok": False, "erro": "método não aceito"}
        if not equipe:
            return negado
        if p == "/api/fornecedores/arquivo":
            dados = corpo if isinstance(corpo, (bytes, bytearray)) else (corpo or "").encode("utf-8")
            fo, eq = g("fornecedor", 12), g("equipamento", 12)
            return resp(self.arquivo_por(g("nome", 160), bytes(dados), quem, int(fo) if fo.isdigit() else None,
                                         int(eq) if eq.isdigit() else None, g("tipo", 20) or "catalogo"))
        rotas_fixas = {"/api/fornecedores/cadastro": "forn_cadastro", "/api/fornecedores/equipamento": "forn_equipamento",
                       "/api/fornecedores/equipamento/remover": "forn_id", "/api/fornecedores/importar": "forn_importar",
                       "/api/fornecedores/pedir-atualizacao": "forn_pedir", "/api/fornecedores/arquivo/publico": "forn_arquivo_publico",
                       "/api/fornecedores/arquivo/remover": "forn_id"}
        m = re.fullmatch(r"/api/fornecedores/(\d{1,12})/(editar|regiao|regiao/remover|regiao/conferida|oferta|oferta/remover|preco|contato|"
                         r"contato/remover|curadoria|apagar)", p)
        if p not in rotas_fixas and not m:
            return 404, {"ok": False, "erro": "rota desconhecida"}
        acao = m.group(2) if m else None
        nome_esq = rotas_fixas.get(p) or {"editar": "forn_editar", "regiao": "forn_regiao", "oferta": "forn_equipamento", "preco": "forn_preco",
                                           "contato": "forn_contato", "curadoria": "forn_curadoria"}.get(acao, "forn_id" if acao and acao.endswith(
                                               ("remover", "conferida")) else "vazio")
        try:
            d = seg.carregar_json(corpo or "{}")
        except ValueError:
            return 400, {"ok": False, "erro": "json invalido"}
        if acao == "oferta" and isinstance(d, dict) and set(d) == {"equipamento"}:
            nome_esq = "forn_oferta"
        erro = seg.validar(d, seg.ESQUEMAS.get(nome_esq) or ESQUEMAS[nome_esq], estrito=True)
        if erro:
            return 400, {"ok": False, "erro": erro}
        if not m:
            return resp({"/api/fornecedores/cadastro": lambda: self.cadastrar(d, quem),
                         "/api/fornecedores/equipamento": lambda: self.equipamento(d, quem),
                         "/api/fornecedores/equipamento/remover": lambda: self.equipamento_remover(d["id"], quem),
                         "/api/fornecedores/importar": lambda: self.importar(d, quem),
                         "/api/fornecedores/pedir-atualizacao": lambda: self.pedir_atualizacao(d, quem),
                         "/api/fornecedores/arquivo/publico": lambda: self.arquivo_publico(d["id"], d["publico"], quem, direcao),
                         "/api/fornecedores/arquivo/remover": lambda: self.arquivo_remover(d["id"], quem)}[p]())
        fid = int(m.group(1))
        if acao in ("curadoria", "apagar") and not direcao:
            return negado
        return resp({"editar": lambda: self.editar(fid, d, quem), "regiao": lambda: self.regiao(fid, d, quem),
                     "regiao/remover": lambda: self.regiao_remover(fid, d["id"], quem),
                     "regiao/conferida": lambda: self.regiao_conferida(fid, d["id"], quem),
                     "oferta": lambda: self.oferta(fid, d, quem), "oferta/remover": lambda: self.oferta_remover(fid, d["id"], quem),
                     "preco": lambda: self.preco(fid, d, quem), "contato": lambda: self.contato(fid, d, quem),
                     "contato/remover": lambda: self.contato_remover(fid, d["id"], quem),
                     "curadoria": lambda: self.curar(fid, d.get("status"), d.get("motivo"), quem, direcao),
                     "apagar": lambda: self.apagar(fid, quem)}[acao]())
