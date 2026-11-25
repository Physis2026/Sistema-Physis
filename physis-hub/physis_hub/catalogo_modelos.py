"""Catálogo técnico de modelos dos fabricantes (25/11/2026: "o bot de fabricantes e de pesquisa de mercado preenche os
catálogos no banco, multi-split etc." e "AVAC: seleção de condensadoras multi-split pelo catálogo").

O que guarda (um banco próprio, compartilhado pelas instalações: PHYSIS_CATALOGO = caminho do .db; sem ela, ao lado do banco
da instalação): um modelo comercial por linha (fabricante, linha, modelo, tipo) com os dados de catálogo que a seleção e o
quadro elétrico usam: capacidade de refrigeração (BTU/h e kW), aquecimento, potência elétrica, eficiência, nº máximo de
evaporadoras (saídas), faixa de combinação (% da capacidade nominal), evaporadoras compatíveis, tensão, fases, corrente máxima
(MCA) e disjuntor máximo (MOP) do fabricante, refrigerante e limites de tubulação.

Regra 1 (nada é inventado):
- toda linha nasce com FONTE (endereço ou nome do arquivo do catálogo), REFERÊNCIA (página/tabela) e DATA da fonte; sem elas a
  linha é recusada. Unidade só é convertida (1 kW = 3.412,142 BTU/h), nunca estimada;
- 25/11/2026 ("tudo automático pelos bots, nada manual"): o bot de modelos lê os catálogos e grava sozinho. A linha do bot ou do
  Inmetro que passa em TODAS as conferências automáticas (fonte e página, data, unidades, faixas, campos completos, eficiência ×
  capacidade/potência, MCA ≤ MOP) vira "conferido_bot" e já entra na seleção, marcada assim; com qualquer aviso fica "a_conferir".
  A direção pode trocar o estado quando quiser (opcional, não é passo obrigatório);
- o que falta fica escrito ("faltam dados: ...") e a seleção diz por que cada condensadora ficou de fora.
Histórico só cresce (cadeia SHA-256, como fornecedores.py). Exportação para parceiros: só conferido, com fonte e resumo.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import threading
import time
import unicodedata
from pathlib import Path

from . import seguranca as seg

RAIZ = Path(__file__).resolve().parents[2]
BTU_POR_KW = 3412.142
TIPOS = {"condensadora_multi": "Condensadora multi-split", "evaporadora_multi": "Evaporadora de multi-split",
         "split": "Split (interna + externa)", "vrf_externa": "Condensadora VRF", "vrf_interna": "Unidade interna VRF",
         "chiller": "Chiller", "fancoil": "Fancoil", "bomba": "Bomba", "motor": "Motor elétrico",
         "inversor_fv": "Inversor fotovoltaico", "modulo_fv": "Módulo fotovoltaico", "inversor_freq": "Inversor de frequência"}
ESTADOS = {"a_conferir": "A conferir", "conferido_bot": "Conferido pelo bot", "conferido": "Conferido", "descartado": "Descartado"}
VALIDOS = ("conferido", "conferido_bot")          # entram na seleção e na exportação
ORIGENS = ("planilha", "inmetro", "bot", "manual")
# coluna: (mínimo, máximo, inteiro). Faixas largas só para pegar erro de digitação (vírgula fora do lugar), não de projeto.
NUMEROS = {"cap_resf_btuh": (1000, 7_000_000, False), "cap_resf_kw": (0.3, 2000, False), "cap_aquec_kw": (0.3, 2000, False),
           "pot_eletrica_kw": (0.01, 1000, False), "eficiencia": (0.5, 15, False), "saidas_max": (1, 64, True),
           "comb_min_pct": (10, 150, False), "comb_max_pct": (50, 200, False), "evap_min_btuh": (1000, 200_000, False),
           "evap_max_btuh": (1000, 200_000, False), "tensao_v": (100, 690, False), "fases": (1, 3, True),
           "corrente_max_a": (0.1, 2000, False), "disjuntor_max_a": (1, 4000, False), "tubo_total_max_m": (0, 2000, False),
           "tubo_ramal_max_m": (0, 500, False), "desnivel_max_m": (0, 200, False)}
TEXTOS = {"tipo": 30, "fabricante": 60, "linha": 80, "modelo": 60, "classe": 60, "eficiencia_indicador": 12, "evaps_compativeis": 2000,
          "refrigerante": 20, "fonte": 400, "fonte_ref": 120, "data_fonte": 10, "estado": 12}
COLUNAS = ("tipo", "fabricante", "linha", "modelo", "classe", "cap_resf_btuh", "cap_resf_kw", "cap_aquec_kw", "pot_eletrica_kw",
           "eficiencia_indicador", "eficiencia", "saidas_max", "comb_min_pct", "comb_max_pct", "evap_min_btuh", "evap_max_btuh",
           "evaps_compativeis", "tensao_v", "fases", "corrente_max_a", "disjuntor_max_a", "refrigerante", "tubo_total_max_m",
           "tubo_ramal_max_m", "desnivel_max_m", "fonte", "fonte_ref", "data_fonte", "estado")
DADOS = tuple(c for c in COLUNAS if c not in ("tipo", "fabricante", "linha", "modelo", "classe", "fonte", "fonte_ref", "data_fonte", "estado"))
INDICADORES = ("EER", "COP", "IDRS", "SEER", "IEER", "IPLV", "η")
# o que cada tipo precisa para ser selecionado (sem isto, "faltam dados")
PRECISA = {"condensadora_multi": ("cap_resf_btuh", "saidas_max", "comb_min_pct", "comb_max_pct"),
           "evaporadora_multi": ("cap_resf_btuh",), "split": ("cap_resf_btuh",), "vrf_externa": ("cap_resf_btuh",),
           "vrf_interna": ("cap_resf_btuh",), "chiller": ("cap_resf_kw",), "fancoil": ("cap_resf_kw",)}
# o que o quadro elétrico precisa (corrente do fabricante; sem ela, potência + tensão + fases)
PRECISA_QUADRO = ("tensao_v", "fases", "corrente_max_a")
CSV_MAX = 1024 * 1024
LINHAS_MAX = 5000
AMBIENTES_MAX = 16
PREMISSA_ANOS = "catalogo.anos_validade"          # catálogo mais velho que isto: aviso (só se a premissa existir)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS catalogo_modelo (
  id TEXT PRIMARY KEY, tipo TEXT NOT NULL, fabricante TEXT NOT NULL, linha TEXT NOT NULL DEFAULT '', modelo TEXT NOT NULL,
  classe TEXT NOT NULL DEFAULT '', dados TEXT NOT NULL DEFAULT '{}', fonte TEXT NOT NULL, fonte_ref TEXT NOT NULL DEFAULT '',
  data_fonte TEXT NOT NULL, origem TEXT NOT NULL, importacao INTEGER, estado TEXT NOT NULL DEFAULT 'a_conferir',
  faltam TEXT NOT NULL DEFAULT '[]', avisos TEXT NOT NULL DEFAULT '[]', conferido_por TEXT NOT NULL DEFAULT '', conferido_em REAL,
  criado REAL NOT NULL, atualizado REAL NOT NULL, por TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS catalogo_modelo_tipo ON catalogo_modelo(tipo, fabricante);
CREATE TABLE IF NOT EXISTS catalogo_importacao (
  id INTEGER PRIMARY KEY AUTOINCREMENT, origem TEXT NOT NULL, nome_arquivo TEXT NOT NULL DEFAULT '', sha256 TEXT NOT NULL,
  linhas INTEGER NOT NULL, gravadas INTEGER NOT NULL, iguais INTEGER NOT NULL, recusadas INTEGER NOT NULL, quando REAL NOT NULL,
  por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS catalogo_historico (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, quando REAL NOT NULL, quem TEXT NOT NULL, modelo TEXT NOT NULL DEFAULT '',
  o_que TEXT NOT NULL, detalhe TEXT NOT NULL, anterior TEXT NOT NULL, resumo TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS catalogo_historico_sem_mudar BEFORE UPDATE ON catalogo_historico
  BEGIN SELECT RAISE(ABORT, 'historico so cresce'); END;
CREATE TRIGGER IF NOT EXISTS catalogo_historico_sem_apagar BEFORE DELETE ON catalogo_historico
  BEGIN SELECT RAISE(ABORT, 'historico so cresce'); END;
"""

S, NUM = str, (int, float)
ESQUEMAS = {   # corpos JSON das rotas (entram em seg.ESQUEMAS pelo servidor; validação estrita)
    "cat_conferir": {"ids": (list, 500, False), "importacao": (int, 10**12, False), "estado": (S, 12, True), "nota": (S, 400, False)},
    "cat_multisplit": {"ambientes": (list, AMBIENTES_MAX, True), "fabricante": (S, 60, False), "simultaneidade": (NUM, 1, False),
                       "incluir_a_conferir": (bool, None, False), "max_opcoes": (int, 20, False), "titulo": (S, 120, False)},
}


def norm(s) -> str:
    """Comparação sem acento, sem caixa e sem espaço repetido (\"Daikin \" = \"daikin\")."""
    t = "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c) != "Mn")
    return " ".join(t.lower().split())


def numero(v) -> float | None:
    """Número de planilha pt-BR ou en: "18.000" → 18000; "5,3" → 5.3; "1.234,5" → 1234.5; "" → None. Texto → ValueError."""
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip().replace("\u00a0", "").replace(" ", "")
    if s == "":
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        x = float(s)
    except ValueError:
        raise ValueError(f"número inválido: {v!r}") from None
    if x != x or x in (float("inf"), float("-inf")):
        raise ValueError(f"número inválido: {v!r}")
    return x


def id_modelo(tipo: str, fabricante: str, modelo: str) -> str:
    return "cm-" + hashlib.sha1(f"{tipo}|{norm(fabricante)}|{norm(modelo)}".encode("utf-8")).hexdigest()[:16]


def caminho_padrao(banco_instancia: str | Path | None = None) -> Path:
    """PHYSIS_CATALOGO (um arquivo para todas as instalações) ou catalogo-modelos.db ao lado do banco da instalação."""
    amb = os.environ.get("PHYSIS_CATALOGO", "").strip()
    if amb:
        return Path(amb)
    if banco_instancia is not None and str(banco_instancia) == ":memory:":
        return Path(":memory:")                       # hub em memória (testes): catálogo em memória também
    if banco_instancia:
        return Path(banco_instancia).resolve().parent / "catalogo-modelos.db"
    return RAIZ / "dados" / "catalogo-modelos.db"


def validar_linha(bruta: dict) -> tuple[dict | None, str | None, list[str]]:
    """(linha normalizada, erro, avisos). Erro = linha recusada; avisos = gravada com aviso."""
    g = {k: str(bruta.get(k) if bruta.get(k) is not None else "").strip() for k in COLUNAS}
    for k, n in TEXTOS.items():
        if len(g[k]) > n:
            return None, f"{k} com mais de {n} caracteres", []
    if g["tipo"] not in TIPOS:
        return None, f"tipo desconhecido: {g['tipo'] or '(vazio)'} (use: {', '.join(TIPOS)})", []
    for k in ("fabricante", "modelo"):
        if not g[k]:
            return None, f"{k} vazio", []
    if not g["fonte"]:
        return None, "sem fonte (endereço ou nome do arquivo do catálogo): regra 1, nada entra sem fonte", []
    if not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", g["data_fonte"]):
        return None, "data_fonte vazia ou fora do formato AAAA, AAAA-MM ou AAAA-MM-DD (data do catálogo, não a de hoje)", []
    if g["eficiencia_indicador"] and g["eficiencia_indicador"] not in INDICADORES:
        return None, f"eficiencia_indicador desconhecido: {g['eficiencia_indicador']} (use: {', '.join(INDICADORES)})", []
    d, avisos = {}, []
    for k, (lo, hi, inteiro) in NUMEROS.items():
        try:
            x = numero(g[k])
        except ValueError as e:
            return None, f"{k}: {e}", []
        if x is None:
            continue
        if not lo <= x <= hi:
            return None, f"{k} = {x:g} fora da faixa aceita ({lo:g} a {hi:g}); conferir a unidade", []
        if inteiro and x != int(x):
            return None, f"{k} precisa ser inteiro", []
        d[k] = int(x) if inteiro else x
    if d.get("cap_resf_btuh") is not None and d.get("cap_resf_kw") is not None:
        if abs(d["cap_resf_btuh"] / BTU_POR_KW - d["cap_resf_kw"]) > 0.03 * d["cap_resf_kw"]:
            avisos.append("capacidade em BTU/h e em kW não batem (diferença acima de 3 %): conferir no catálogo")
    elif d.get("cap_resf_btuh") is not None:
        d["cap_resf_kw"] = round(d["cap_resf_btuh"] / BTU_POR_KW, 3)
    elif d.get("cap_resf_kw") is not None:
        d["cap_resf_btuh"] = round(d["cap_resf_kw"] * BTU_POR_KW)
    if d.get("comb_min_pct") is not None and d.get("comb_max_pct") is not None and d["comb_min_pct"] >= d["comb_max_pct"]:
        return None, "comb_min_pct precisa ser menor que comb_max_pct", []
    if d.get("evap_min_btuh") is not None and d.get("evap_max_btuh") is not None and d["evap_min_btuh"] > d["evap_max_btuh"]:
        return None, "evap_min_btuh maior que evap_max_btuh", []
    if g["eficiencia"] and not g["eficiencia_indicador"]:
        return None, "eficiência sem o indicador (EER, COP, IDRS...)", []
    if g["eficiencia_indicador"]:
        d["eficiencia_indicador"] = g["eficiencia_indicador"]
    if g["refrigerante"]:
        d["refrigerante"] = g["refrigerante"]
    comp = [x.strip() for x in re.split(r"[|;]", g["evaps_compativeis"]) if x.strip()]
    if comp:
        d["evaps_compativeis"] = comp[:60]
    ind, ef, cap, pot = d.get("eficiencia_indicador"), d.get("eficiencia"), d.get("cap_resf_kw"), d.get("pot_eletrica_kw")
    if ind in ("EER", "COP") and ef and cap and pot and abs(cap / pot - ef) > 0.15 * ef:
        avisos.append(f"{ind} {ef:g} × capacidade/potência {cap / pot:.2f}: diferença acima de 15 %, conferir")
    if d.get("corrente_max_a") and d.get("disjuntor_max_a") and d["corrente_max_a"] > d["disjuntor_max_a"]:
        avisos.append("corrente máxima (MCA) acima do disjuntor máximo (MOP): conferir no catálogo")
    faltam = [k for k in PRECISA.get(g["tipo"], ()) if d.get(k) is None]
    if g["tipo"] in ("condensadora_multi", "split", "vrf_externa", "chiller") and not d.get("corrente_max_a") and not (
            d.get("pot_eletrica_kw") and d.get("tensao_v") and d.get("fases")):
        faltam.append("dados elétricos (corrente máxima ou potência + tensão + fases) para o quadro")
    linha = {"tipo": g["tipo"], "fabricante": " ".join(g["fabricante"].split()), "linha": " ".join(g["linha"].split()),
             "modelo": " ".join(g["modelo"].split()), "classe": g["classe"], "dados": d, "fonte": g["fonte"],
             "fonte_ref": g["fonte_ref"], "data_fonte": g["data_fonte"], "estado": g["estado"], "faltam": faltam}
    return linha, None, avisos


def ler_csv(texto: str) -> list[dict]:
    """Linhas de CSV (; ou ,) com cabeçalho; aceita BOM e CRLF. Linha começando com # é comentário."""
    texto = texto.lstrip("\ufeff")
    linhas = [l for l in texto.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    if not linhas:
        return []
    sep = ";" if linhas[0].count(";") >= linhas[0].count(",") else ","
    rd = csv.DictReader(io.StringIO("\n".join(linhas)), delimiter=sep)
    cab = [c.strip().lower() for c in (rd.fieldnames or [])]
    faltando = [c for c in ("tipo", "fabricante", "modelo", "fonte", "data_fonte") if c not in cab]
    if faltando:
        raise ValueError("cabeçalho sem as colunas: " + ", ".join(faltando) + " (baixe a planilha-modelo)")
    rd.fieldnames = cab
    return [{k: v for k, v in r.items() if k} for r in rd]


def planilha_modelo() -> str:
    """Cabeçalho + uma linha de comentário por coluna (o importador ignora linhas que começam com #)."""
    ajuda = ["# Catálogo técnico Physis: uma linha por modelo. Copie do catálogo do fabricante; não estime nada.",
             "# tipo: " + ", ".join(TIPOS) + ". estado: só a direção marca conferido.",
             "# números: 18.000 ou 18000 (BTU/h), 5,3 (kW). Capacidade em BTU/h OU kW (o sistema converte).",
             "# saidas_max = nº máximo de evaporadoras; comb_min_pct/comb_max_pct = faixa da soma das evaporadoras (% da condensadora).",
             "# evaps_compativeis = modelos de evaporadora separados por | quando o catálogo limita as combinações.",
             "# corrente_max_a = corrente máxima do circuito (MCA); disjuntor_max_a = disjuntor máximo (MOP) do fabricante.",
             "# fonte = endereço ou nome do arquivo do catálogo; fonte_ref = página/tabela; data_fonte = data do catálogo (AAAA-MM)."]
    return "\n".join(ajuda) + "\n" + ";".join(COLUNAS) + "\n"


def selecionar_multisplit(modelos: list[dict], ambientes: list[dict], fabricante: str = "", simultaneidade: float = 1.0,
                          incluir_a_conferir: bool = False, max_opcoes: int = 5) -> dict:
    """Seleção pura (sem banco): condensadora multi-split + uma evaporadora por ambiente, do MESMO fabricante e linha (ou da
    lista de compatíveis do catálogo). Para cada condensadora, cada ambiente leva a menor evaporadora com capacidade ≥ a carga
    do ambiente; vale se nº de ambientes ≤ saídas, soma das evaporadoras dentro da faixa de combinação e capacidade da
    condensadora ≥ carga simultânea (soma das cargas × simultaneidade; 1,0 = todos no pico ao mesmo tempo, o conservador).
    Ordem: menor condensadora que atende, combinação mais perto de 100 %, maior eficiência. Uma opção por fabricante e linha."""
    erro = None
    if not isinstance(ambientes, list) or not ambientes:
        erro = "informe os ambientes (nome e carga em BTU/h)"
    elif len(ambientes) > AMBIENTES_MAX:
        erro = f"até {AMBIENTES_MAX} ambientes por condensadora"
    amb = []
    for i, a in enumerate(ambientes if not erro else []):
        if not isinstance(a, dict):
            erro = f"ambiente {i + 1}: formato inválido"; break
        try:
            btuh = numero(a.get("btuh"))
        except ValueError:
            btuh = None
        if btuh is None or not 100 <= btuh <= 200_000:
            erro = f"ambiente {i + 1}: carga em BTU/h entre 100 e 200.000"; break
        amb.append({"nome": str(a.get("nome") or f"Ambiente {i + 1}")[:80], "btuh": btuh})
    try:
        sim = 1.0 if simultaneidade is None else float(simultaneidade)
    except (TypeError, ValueError):
        sim = -1
    if not erro and not 0.3 <= sim <= 1.0:
        erro = "simultaneidade entre 0,3 e 1,0 (1,0 = todos os ambientes no pico ao mesmo tempo)"
    if erro:
        return {"ok": False, "erro": erro}
    estados = VALIDOS + ("a_conferir",) if incluir_a_conferir else VALIDOS
    fab = norm(fabricante)
    base = [m for m in modelos if m.get("estado") in estados and (not fab or norm(m.get("fabricante")) == fab)]
    conds = [m for m in base if m["tipo"] == "condensadora_multi"]
    evaps = [m for m in base if m["tipo"] == "evaporadora_multi"]
    carga = sum(a["btuh"] for a in amb)
    carga_sim = carga * sim
    premissas = {"simultaneidade": sim, "carga_total_btuh": round(carga), "carga_simultanea_btuh": round(carga_sim),
                 "so_conferidos": not incluir_a_conferir, "fabricante": fabricante or "todos"}
    if not conds:
        qual = "conferidas" if not incluir_a_conferir else "cadastradas"
        return {"ok": False, "premissas": premissas, "opcoes": [], "descartadas": [],
                "faltam": [f"catálogo: nenhuma condensadora multi-split {qual}" + (f" de {fabricante}" if fabricante else "")
                           + " (Gestão → Fornecedores → Catálogo técnico: importar a planilha do catálogo do fabricante)"]}
    ok, fora = [], []
    for c in sorted(conds, key=lambda m: (m["fabricante"], m["linha"], m["modelo"])):
        d = c.get("dados") or {}
        rot = {"fabricante": c["fabricante"], "linha": c["linha"], "modelo": c["modelo"]}
        falta = [k for k in PRECISA["condensadora_multi"] if d.get(k) is None]
        if falta:
            fora.append(dict(rot, motivo="faltam dados: " + ", ".join(falta))); continue
        lista = {norm(x) for x in d.get("evaps_compativeis") or []}
        comp = [e for e in evaps if norm(e["fabricante"]) == norm(c["fabricante"]) and (e.get("dados") or {}).get("cap_resf_btuh")
                and ((norm(e["modelo"]) in lista) if lista else norm(e["linha"]) == norm(c["linha"]))]
        comp.sort(key=lambda e: (e["dados"]["cap_resf_btuh"], e["modelo"]))
        if len(amb) > d["saidas_max"]:
            fora.append(dict(rot, motivo=f"{len(amb)} ambientes para {d['saidas_max']} saídas")); continue
        if not comp:
            fora.append(dict(rot, motivo="nenhuma evaporadora compatível no catálogo (mesmo fabricante e linha, ou a lista do catálogo)")); continue
        esc, motivo = [], None
        for a in amb:
            cand = [e for e in comp if e["dados"]["cap_resf_btuh"] >= a["btuh"] - 1e-9
                    and (d.get("evap_min_btuh") is None or e["dados"]["cap_resf_btuh"] >= d["evap_min_btuh"] - 1e-9)
                    and (d.get("evap_max_btuh") is None or e["dados"]["cap_resf_btuh"] <= d["evap_max_btuh"] + 1e-9)]
            if not cand:
                motivo = f"nenhuma evaporadora ≥ {round(a['btuh'])} BTU/h para {a['nome']}"; break
            esc.append((a, cand[0]))
        if motivo:
            fora.append(dict(rot, motivo=motivo)); continue
        cap = d["cap_resf_btuh"]
        soma = sum(e["dados"]["cap_resf_btuh"] for _, e in esc)
        pct = soma / cap * 100
        if pct < d["comb_min_pct"] - 1e-9:
            fora.append(dict(rot, motivo=f"combinação {pct:.0f} % abaixo do mínimo de {d['comb_min_pct']:g} %")); continue
        if pct > d["comb_max_pct"] + 1e-9:
            fora.append(dict(rot, motivo=f"combinação {pct:.0f} % acima do máximo de {d['comb_max_pct']:g} %")); continue
        if cap < carga_sim - 1e-9:
            fora.append(dict(rot, motivo=f"capacidade {round(cap)} BTU/h abaixo da carga simultânea {round(carga_sim)} BTU/h")); continue
        partes = [c] + [e for _, e in esc]
        fontes = []
        for m in partes:
            f = f"{m['fonte']}" + (f" ({m['fonte_ref']})" if m.get("fonte_ref") else "") + f", {m['data_fonte']}"
            if f not in fontes:
                fontes.append(f)
        elet = {k: d.get(k) for k in ("tensao_v", "fases", "corrente_max_a", "disjuntor_max_a", "pot_eletrica_kw")}
        falta_q = [] if d.get("corrente_max_a") or (d.get("pot_eletrica_kw") and d.get("tensao_v") and d.get("fases")) else [
            "dados elétricos da condensadora (corrente máxima, ou potência + tensão + fases)"]
        ok.append(dict(rot, id=c["id"], cap_btuh=round(cap), cap_kw=round(d["cap_resf_kw"], 2), saidas=d["saidas_max"],
                       faixa_pct=[d["comb_min_pct"], d["comb_max_pct"]], soma_evap_btuh=round(soma), combinacao_pct=round(pct, 1),
                       sobra_pct=round((cap - carga_sim) / carga_sim * 100, 1) if carga_sim else None,
                       eficiencia={"indicador": d.get("eficiencia_indicador"), "valor": d.get("eficiencia")},
                       evaporadoras=[{"ambiente": a["nome"], "carga_btuh": round(a["btuh"]), "modelo": e["modelo"], "id": e["id"],
                                      "cap_btuh": round(e["dados"]["cap_resf_btuh"])} for a, e in esc],
                       eletrica=elet, faltam_quadro=falta_q, refrigerante=d.get("refrigerante"),
                       tubulacao={k: d.get(k) for k in ("tubo_total_max_m", "tubo_ramal_max_m", "desnivel_max_m")},
                       a_conferir=any(m["estado"] not in VALIDOS for m in partes),
                       conferido_por_bot=any(m["estado"] == "conferido_bot" for m in partes), fontes=fontes))
    ok.sort(key=lambda o: (o["cap_btuh"], abs(o["combinacao_pct"] - 100), -(o["eficiencia"]["valor"] or 0), o["fabricante"], o["modelo"]))
    vistos, opcoes = set(), []
    for o in ok:
        k = (norm(o["fabricante"]), norm(o["linha"]))
        if k in vistos:
            continue
        vistos.add(k)
        opcoes.append(o)
        if len(opcoes) >= max(1, min(int(max_opcoes or 5), 20)):
            break
    faltam = [] if opcoes else ["nenhuma combinação do catálogo atende a estes ambientes (ver o motivo de cada condensadora)"]
    return {"ok": bool(opcoes), "premissas": premissas, "opcoes": opcoes, "descartadas": fora, "faltam": faltam}


class Catalogo:
    COLS = ("id", "tipo", "fabricante", "linha", "modelo", "classe", "dados", "fonte", "fonte_ref", "data_fonte", "origem",
            "importacao", "estado", "faltam", "avisos", "conferido_por", "conferido_em", "criado", "atualizado", "por")

    def __init__(self, caminho: str | Path | None = None, hub=None, relogio=None, premissas: dict | None = None):
        self.hub = hub
        self.relogio = relogio or (hub.relogio if hub is not None else time.time)
        self.caminho = str(caminho or caminho_padrao())
        if self.caminho != ":memory:":
            Path(self.caminho).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.caminho, check_same_thread=False, timeout=15)
        self._trava = threading.RLock()
        with self._trava:
            if self.caminho != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(ESQUEMA)
            r = self._db.execute("SELECT resumo FROM catalogo_historico ORDER BY seq DESC LIMIT 1").fetchone()
            self._ultimo = r[0] if r else "0" * 64
            self._db.commit()
        self.anos_validade = None
        try:
            prem = premissas if premissas is not None else json.loads((RAIZ / "sistema" / "physis-premissas.json").read_text(encoding="utf-8"))
            for p in prem.get("premissas", []):
                if p.get("id") == PREMISSA_ANOS and isinstance(p.get("valor_padrao"), (int, float)):
                    self.anos_validade = p["valor_padrao"]
        except (OSError, ValueError):
            pass

    def fechar(self) -> None:
        with self._trava:
            self._db.close()

    # ── histórico (só cresce; cadeia de resumos) ─────────────────────────────────────────────
    @staticmethod
    def _resumo(anterior, quando, quem, modelo, o_que, detalhe) -> str:
        return hashlib.sha256("|".join([anterior, repr(float(quando)), quem, modelo or "", o_que, detalhe]).encode("utf-8")).hexdigest()

    def _hist(self, quem: str, modelo: str, o_que: str, detalhe: dict | None = None) -> None:
        quando, txt = self.relogio(), json.dumps(detalhe or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        res = self._resumo(self._ultimo, quando, quem or "?", modelo, o_que, txt)
        self._db.execute("INSERT INTO catalogo_historico(quando,quem,modelo,o_que,detalhe,anterior,resumo) VALUES(?,?,?,?,?,?,?)",
                         (quando, quem or "?", modelo or "", o_que, txt, self._ultimo, res))
        self._ultimo = res

    def verificar_historico(self) -> tuple[bool, int]:
        ant, n = "0" * 64, 0
        for quando, quem, m, o, det, a, r in self._db.execute(
                "SELECT quando,quem,modelo,o_que,detalhe,anterior,resumo FROM catalogo_historico ORDER BY seq"):
            if a != ant or self._resumo(ant, quando, quem, m, o, det) != r:
                return False, n
            ant, n = r, n + 1
        return True, n

    def historico(self, limite: int = 200) -> dict:
        with self._trava:
            rows = self._db.execute("SELECT seq,quando,quem,modelo,o_que,detalhe FROM catalogo_historico ORDER BY seq DESC LIMIT ?",
                                    (limite,)).fetchall()
            integro, n = self.verificar_historico()
        return {"ok": True, "integro": integro, "registros": n,
                "itens": [{"seq": s, "quando": q, "quem": w, "modelo": m, "o_que": o, "detalhe": json.loads(d)} for s, q, w, m, o, d in rows]}

    # ── leitura ──────────────────────────────────────────────────────────────────────────────
    def _linha(self, r) -> dict:
        m = dict(zip(self.COLS, r))
        for k in ("dados", "faltam", "avisos"):
            m[k] = json.loads(m[k] or ("{}" if k == "dados" else "[]"))
        return m

    def modelos(self, tipo: str = "", fabricante: str = "", estado: str = "") -> list[dict]:
        sql, par = "SELECT " + ",".join(self.COLS) + " FROM catalogo_modelo WHERE 1=1", []
        if tipo:
            tipos = [t for t in tipo.split(",") if t in TIPOS]
            sql += " AND tipo IN (" + ",".join("?" * len(tipos)) + ")" if tipos else " AND 0"
            par += tipos
        if estado:
            sql += " AND estado=?"
            par.append(estado)
        with self._trava:
            rows = [self._linha(r) for r in self._db.execute(sql + " ORDER BY tipo, fabricante, linha, modelo", par)]
        if fabricante:
            rows = [m for m in rows if norm(m["fabricante"]) == norm(fabricante)]
        return rows

    @staticmethod
    def publico(m: dict) -> dict:
        """O que o cliente vê: dados técnicos e fonte do modelo conferido (nada de quem conferiu nem da importação)."""
        return {k: m[k] for k in ("id", "tipo", "fabricante", "linha", "modelo", "classe", "dados", "fonte", "fonte_ref", "data_fonte", "faltam")}

    # ── gravação ─────────────────────────────────────────────────────────────────────────────
    def importar_linhas(self, brutas: list[dict], quem: str, origem: str = "planilha", nome_arquivo: str = "",
                        direcao: bool = False, sha256: str = "") -> dict:
        if origem not in ORIGENS:
            return {"ok": False, "erro": "origem desconhecida"}
        if len(brutas) > LINHAS_MAX:
            return {"ok": False, "erro": f"até {LINHAS_MAX} linhas por importação"}
        agora = self.relogio()
        gravadas, iguais, recusadas, vistas = 0, 0, [], set()
        with self._trava:
            cur = self._db.execute("INSERT INTO catalogo_importacao(origem,nome_arquivo,sha256,linhas,gravadas,iguais,recusadas,quando,por)"
                                   " VALUES(?,?,?,?,0,0,0,?,?)", (origem, nome_arquivo[:200], sha256, len(brutas), agora, quem))
            imp = cur.lastrowid
            for n, b in enumerate(brutas, start=2):
                linha, erro, avisos = validar_linha(b)
                if erro:
                    recusadas.append({"linha": n, "modelo": str(b.get("modelo") or "")[:60], "erro": erro}); continue
                mid = id_modelo(linha["tipo"], linha["fabricante"], linha["modelo"])
                if mid in vistas:
                    recusadas.append({"linha": n, "modelo": linha["modelo"], "erro": "modelo repetido nesta planilha"}); continue
                vistas.add(mid)
                if direcao and linha["estado"] in ESTADOS:
                    estado = linha["estado"]
                elif origem in ("bot", "inmetro") and not avisos and not linha["faltam"] and linha["fonte_ref"]:
                    estado = "conferido_bot"          # passou em todas as conferências automáticas
                else:
                    estado = "a_conferir"
                dados_txt = json.dumps(linha["dados"], ensure_ascii=False, sort_keys=True)
                ant = self._db.execute("SELECT dados,fonte,fonte_ref,data_fonte,linha,classe,estado FROM catalogo_modelo WHERE id=?",
                                       (mid,)).fetchone()
                novo = (dados_txt, linha["fonte"], linha["fonte_ref"], linha["data_fonte"], linha["linha"], linha["classe"])
                if ant and tuple(ant[:6]) == novo and not (direcao and linha["estado"] in ESTADOS and linha["estado"] != ant[6]):
                    iguais += 1; continue
                if ant:
                    self._db.execute("UPDATE catalogo_modelo SET linha=?,classe=?,dados=?,fonte=?,fonte_ref=?,data_fonte=?,origem=?,"
                                     "importacao=?,estado=?,faltam=?,avisos=?,conferido_por=?,conferido_em=?,atualizado=?,por=? WHERE id=?",
                                     (linha["linha"], linha["classe"], dados_txt, linha["fonte"], linha["fonte_ref"], linha["data_fonte"],
                                      origem, imp, estado, json.dumps(linha["faltam"], ensure_ascii=False),
                                      json.dumps(avisos, ensure_ascii=False), quem if estado == "conferido" else "",
                                      agora if estado == "conferido" else None, agora, quem, mid))
                    self._hist(quem, mid, "atualizado", {"importacao": imp, "estado": estado, "antes": ant[6]})
                else:
                    self._db.execute("INSERT INTO catalogo_modelo(" + ",".join(self.COLS) + ") VALUES(" + ",".join("?" * len(self.COLS)) + ")",
                                     (mid, linha["tipo"], linha["fabricante"], linha["linha"], linha["modelo"], linha["classe"], dados_txt,
                                      linha["fonte"], linha["fonte_ref"], linha["data_fonte"], origem, imp, estado,
                                      json.dumps(linha["faltam"], ensure_ascii=False), json.dumps(avisos, ensure_ascii=False),
                                      quem if estado == "conferido" else "", agora if estado == "conferido" else None, agora, agora, quem))
                    self._hist(quem, mid, "criado", {"importacao": imp, "estado": estado, "tipo": linha["tipo"]})
                gravadas += 1
            self._db.execute("UPDATE catalogo_importacao SET gravadas=?,iguais=?,recusadas=? WHERE id=?", (gravadas, iguais, len(recusadas), imp))
            self._hist(quem, "", "importacao", {"id": imp, "origem": origem, "linhas": len(brutas), "gravadas": gravadas,
                                                "iguais": iguais, "recusadas": len(recusadas), "sha256": sha256})
            self._db.commit()
        if self.hub is not None:
            try:
                self.hub.registrar("catalogo", quem, {"importacao": imp, "gravadas": gravadas, "recusadas": len(recusadas)})
            except Exception:  # noqa: BLE001 — o registro do hub é complementar
                pass
        return {"ok": True, "importacao": imp, "linhas": len(brutas), "gravadas": gravadas, "iguais": iguais,
                "recusadas": recusadas, "estado": "a_conferir" if not direcao else "conforme a planilha"}

    def importar_csv(self, texto: str | bytes, quem: str, nome_arquivo: str = "", origem: str = "planilha", direcao: bool = False) -> dict:
        bruto = texto if isinstance(texto, bytes) else texto.encode("utf-8")
        if len(bruto) > CSV_MAX:
            return {"ok": False, "erro": "planilha maior que 1 MB: divida por fabricante"}
        try:
            txt = bruto.decode("utf-8-sig")
        except UnicodeDecodeError:
            txt = bruto.decode("latin-1")
        try:
            linhas = ler_csv(txt)
        except (ValueError, csv.Error) as e:
            return {"ok": False, "erro": str(e)}
        if not linhas:
            return {"ok": False, "erro": "planilha sem linhas"}
        return self.importar_linhas(linhas, quem, origem, nome_arquivo, direcao, hashlib.sha256(bruto).hexdigest())

    def conferir(self, quem: str, estado: str, ids: list[str] | None = None, importacao: int | None = None, nota: str = "") -> dict:
        """Só a direção (a rota confere o papel). Conferido = alguém da Physis abriu o catálogo e bateu os números."""
        if estado not in ESTADOS:
            return {"ok": False, "erro": "estado: " + ", ".join(ESTADOS)}
        if not ids and importacao is None:
            return {"ok": False, "erro": "informe ids ou importacao"}
        agora = self.relogio()
        with self._trava:
            if importacao is not None:
                alvo = [r[0] for r in self._db.execute("SELECT id FROM catalogo_modelo WHERE importacao=?", (importacao,))]
            else:
                alvo = [i for i in (ids or []) if isinstance(i, str) and re.fullmatch(r"cm-[0-9a-f]{16}", i)]
            feitos = 0
            for mid in alvo:
                r = self._db.execute("UPDATE catalogo_modelo SET estado=?,conferido_por=?,conferido_em=?,atualizado=?,por=? WHERE id=?",
                                     (estado, quem if estado == "conferido" else "", agora if estado == "conferido" else None, agora, quem, mid))
                if r.rowcount:
                    feitos += 1
                    self._hist(quem, mid, "estado", {"estado": estado, "nota": nota[:400]})
            self._db.commit()
        return {"ok": True, "alterados": feitos, "estado": estado}

    # ── seleção, lacunas, auditoria e exportação ─────────────────────────────────────────────
    def multisplit(self, ambientes, fabricante="", simultaneidade=1.0, incluir_a_conferir=False, max_opcoes=5) -> dict:
        mods = self.modelos("condensadora_multi,evaporadora_multi")
        r = selecionar_multisplit(mods, ambientes, fabricante, simultaneidade, incluir_a_conferir, max_opcoes)
        r["catalogo"] = {"condensadoras": sum(1 for m in mods if m["tipo"] == "condensadora_multi"),
                         "conferidas": sum(1 for m in mods if m["tipo"] == "condensadora_multi" and m["estado"] in VALIDOS),
                         "evaporadoras": sum(1 for m in mods if m["tipo"] == "evaporadora_multi")}
        return r

    def lacunas(self, fabricantes: dict[str, list[str]] | None = None) -> dict:
        """Por fabricante da lista da Physis (physis-equipamentos.json, segmento Split e multi-split): quantas condensadoras e
        evaporadoras multi-split há, conferidas e a conferir. Fabricante sem condensadora conferida = lacuna."""
        if fabricantes is None:
            fabricantes = {}
            try:
                base = json.loads((RAIZ / "sistema" / "physis-equipamentos.json").read_text(encoding="utf-8"))
                for seg_, info in (base.get("fabricantes_por_segmento") or {}).items():
                    if not seg_.startswith("_"):
                        fabricantes[seg_] = list(info.get("fabricantes") or [])
            except (OSError, ValueError):
                pass
        mods = self.modelos()
        cont = {}
        for m in mods:
            c = cont.setdefault(norm(m["fabricante"]), {})
            k = (m["tipo"], m["estado"])
            c[k] = c.get(k, 0) + 1
        segs = []
        for seg_, fabs in fabricantes.items():
            tipos = ("condensadora_multi", "evaporadora_multi") if "multi" in norm(seg_) else \
                ("vrf_externa", "vrf_interna") if "vrf" in norm(seg_) else ("chiller",) if "chiller" in norm(seg_) else ()
            if not tipos:
                continue
            linhas = []
            for f in fabs:
                c = cont.get(norm(f), {})
                linhas.append({"fabricante": f, **{t: {"conferido": c.get((t, "conferido"), 0), "a_conferir": c.get((t, "a_conferir"), 0)} for t in tipos},
                               "lacuna": c.get((tipos[0], "conferido"), 0) + c.get((tipos[0], "conferido_bot"), 0) == 0})
            segs.append({"segmento": seg_, "tipos": list(tipos), "fabricantes": linhas, "lacunas": sum(1 for l in linhas if l["lacuna"])})
        incompletos = [{"id": m["id"], "fabricante": m["fabricante"], "modelo": m["modelo"], "tipo": m["tipo"], "faltam": m["faltam"]}
                       for m in mods if m["faltam"] and m["estado"] != "descartado"]
        return {"ok": True, "segmentos": segs, "incompletos": incompletos, "total": len(mods)}

    def auditoria(self, hoje: float | None = None) -> dict:
        """Base completa e consistente para mandar a parceiros: por modelo, o que impede (faltam dados, avisos de
        consistência, compatível inexistente, mesmo modelo em dois tipos, catálogo velho) e o total pronto."""
        mods = self.modelos()
        hoje = hoje or self.relogio()
        por_modelo: dict[str, list[str]] = {}
        nomes = {}
        for m in mods:
            nomes.setdefault((norm(m["fabricante"]), norm(m["modelo"])), set()).add(m["tipo"])
        evap_por_fab = {}
        for m in mods:
            if m["tipo"] == "evaporadora_multi":
                evap_por_fab.setdefault(norm(m["fabricante"]), set()).add(norm(m["modelo"]))
        for m in mods:
            if m["estado"] == "descartado":
                continue
            p = ["faltam dados: " + f for f in m["faltam"]] + list(m["avisos"])
            for x in (m["dados"].get("evaps_compativeis") or []):
                if norm(x) not in evap_por_fab.get(norm(m["fabricante"]), set()):
                    p.append(f"evaporadora compatível {x} não está no catálogo")
            if len(nomes[(norm(m["fabricante"]), norm(m["modelo"]))]) > 1:
                p.append("mesmo fabricante e modelo cadastrados em mais de um tipo")
            if self.anos_validade:
                try:
                    ano = int(m["data_fonte"][:4])
                    if time.gmtime(hoje).tm_year - ano > self.anos_validade:
                        p.append(f"catálogo de {ano}: mais velho que {self.anos_validade:g} anos (premissa {PREMISSA_ANOS})")
                except ValueError:
                    pass
            if m["estado"] not in VALIDOS:
                p.append("a conferir (não passou nas conferências automáticas)")
            por_modelo[m["id"]] = p
        prontos = [mid for mid, p in por_modelo.items() if not p]
        problemas = [{"id": m["id"], "tipo": m["tipo"], "fabricante": m["fabricante"], "modelo": m["modelo"], "problemas": por_modelo[m["id"]]}
                     for m in mods if por_modelo.get(m["id"])]
        est = {}
        for m in mods:
            est[m["estado"]] = est.get(m["estado"], 0) + 1
        integro, n = self.verificar_historico()
        return {"ok": True, "total": len(mods), "por_estado": est, "prontos_para_parceiros": len(prontos), "problemas": problemas,
                "historico_integro": integro, "registros_historico": n,
                "validade_catalogo": self.anos_validade if self.anos_validade else f"sem premissa {PREMISSA_ANOS}: idade do catálogo não conferida"}

    def exportar(self, formato: str = "csv", so_prontos: bool = True) -> tuple[str, str, bytes]:
        """(nome, mime, bytes). Para parceiros: só o conferido sem pendência (so_prontos), com fonte e resumo SHA-256."""
        aud = self.auditoria()
        pend = {p["id"] for p in aud["problemas"]}
        mods = [m for m in self.modelos() if m["estado"] != "descartado" and (not so_prontos or m["id"] not in pend)]
        if formato == "json":
            itens = [dict(self.publico(m), estado=m["estado"]) for m in mods]
            corpo = json.dumps(itens, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            doc = {"formato": "physis-catalogo/1", "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.relogio())),
                   "so_prontos": so_prontos, "total": len(itens), "sha256_itens": hashlib.sha256(corpo.encode("utf-8")).hexdigest(),
                   "regra": "dados copiados de catálogos de fabricantes e tabelas públicas; cada item traz a fonte, a página e a data",
                   "itens": itens}
            return "catalogo-physis.json", "application/json; charset=utf-8", json.dumps(doc, ensure_ascii=False, indent=1).encode("utf-8")
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";", lineterminator="\n")
        w.writerow(("id",) + COLUNAS)
        for m in mods:
            d = m["dados"]
            linha = [m["id"]]
            for c in COLUNAS:
                if c in ("tipo", "fabricante", "linha", "modelo", "classe", "fonte", "fonte_ref", "data_fonte", "estado"):
                    linha.append(m[c])
                elif c == "evaps_compativeis":
                    linha.append("|".join(d.get(c) or []))
                else:
                    v = d.get(c)
                    linha.append("" if v is None else (str(v).replace(".", ",") if isinstance(v, float) else str(v)))
            w.writerow(linha)
        return "catalogo-physis.csv", "text/csv; charset=utf-8", ("\ufeff" + buf.getvalue()).encode("utf-8")

    # ── rotas HTTP ───────────────────────────────────────────────────────────────────────────
    def rota(self, metodo: str, caminho: str, conta: dict | None, corpo=None, consulta: dict | None = None):
        """(código, resposta). Resposta dict, ou ("bytes", nome, mime, dados).
        GET  /api/catalogo/modelos?tipo&fabricante&estado      cliente+ (cliente: só conferido, campos públicos)
        GET  /api/catalogo/lacunas | auditoria | historico | importacoes | planilha-modelo | exportar?formato=csv|json&tudo=1   equipe
        POST /api/catalogo/importar?nome=   corpo = CSV (até 1 MB)   equipe (estado da planilha só vale para a direção)
        POST /api/catalogo/conferir {ids|importacao, estado, nota}   direção
        POST /api/avac/multisplit {ambientes:[{nome, btuh}], fabricante, simultaneidade, incluir_a_conferir}   cliente+"""
        if not conta:
            return 401, {"ok": False, "erro": "entre com usuario e senha", "login": True}
        consulta = consulta or {}
        g = lambda k, n=80: str((consulta.get(k) or [""])[0])[:n]
        equipe, direcao, quem = seg.pode(conta, seg.EQUIPE), seg.pode(conta, seg.DIRECAO), conta.get("usuario") or "?"
        negado = (403, {"ok": False, "erro": "o seu papel não permite esta ação"})
        p = caminho.rstrip("/")
        if metodo == "GET":
            if p == "/api/catalogo/modelos":
                if equipe:
                    return 200, {"ok": True, "tipos": TIPOS, "estados": ESTADOS, "modelos": self.modelos(g("tipo", 200), g("fabricante"), g("estado", 12))}
                return 200, {"ok": True, "tipos": TIPOS, "modelos": [self.publico(m) for m in self.modelos(g("tipo", 200), g("fabricante")) if m["estado"] in VALIDOS]}
            if not equipe:
                return negado
            if p == "/api/catalogo/lacunas":
                return 200, self.lacunas()
            if p == "/api/catalogo/auditoria":
                return 200, self.auditoria()
            if p == "/api/catalogo/historico":
                return 200, self.historico()
            if p == "/api/catalogo/importacoes":
                with self._trava:
                    rows = self._db.execute("SELECT id,origem,nome_arquivo,sha256,linhas,gravadas,iguais,recusadas,quando,por"
                                            " FROM catalogo_importacao ORDER BY id DESC LIMIT 100").fetchall()
                cols = ("id", "origem", "nome_arquivo", "sha256", "linhas", "gravadas", "iguais", "recusadas", "quando", "por")
                return 200, {"ok": True, "importacoes": [dict(zip(cols, r)) for r in rows]}
            if p == "/api/catalogo/planilha-modelo":
                return 200, ("bytes", "catalogo-modelo.csv", "text/csv; charset=utf-8", ("\ufeff" + planilha_modelo()).encode("utf-8"))
            if p == "/api/catalogo/exportar":
                nome, mime, dados = self.exportar("json" if g("formato", 8) == "json" else "csv", so_prontos=g("tudo", 2) != "1")
                return 200, ("bytes", nome, mime, dados)
            return 404, {"ok": False, "erro": "rota desconhecida"}
        if metodo != "POST":
            return 405, {"ok": False, "erro": "método não aceito"}
        if p == "/api/avac/multisplit":
            try:
                d = seg.carregar_json(corpo or b"{}")
            except ValueError:
                return 400, {"ok": False, "erro": "json invalido"}
            erro = seg.validar(d, ESQUEMAS["cat_multisplit"], True)
            if erro:
                return 400, {"ok": False, "erro": erro}
            r = self.multisplit(d["ambientes"], d.get("fabricante") or "", d.get("simultaneidade", 1.0),
                                bool(d.get("incluir_a_conferir")) and equipe, d.get("max_opcoes") or 5)
            if "erro" in r:
                return 400, r
            if d.get("incluir_a_conferir") and not equipe:
                r["aviso"] = "modelos a conferir só aparecem para a equipe"
            return 200, r
        if not equipe:
            return negado
        if p == "/api/catalogo/importar":
            bruto = corpo if isinstance(corpo, bytes) else str(corpo or "").encode("utf-8")
            r = self.importar_csv(bruto, quem, g("nome", 200), "planilha", direcao=direcao)
            return (200 if r.get("ok") else 400), r
        if p == "/api/catalogo/conferir":
            if not direcao:
                return negado
            try:
                d = seg.carregar_json(corpo or b"{}")
            except ValueError:
                return 400, {"ok": False, "erro": "json invalido"}
            erro = seg.validar(d, ESQUEMAS["cat_conferir"], True)
            if erro:
                return 400, {"ok": False, "erro": erro}
            r = self.conferir(quem, d["estado"], d.get("ids"), d.get("importacao"), d.get("nota") or "")
            return (200 if r.get("ok") else 400), r
        return 404, {"ok": False, "erro": "rota desconhecida"}
