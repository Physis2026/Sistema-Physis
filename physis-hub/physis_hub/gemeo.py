"""Gêmeo digital · núcleo (versão de TESTE, G0–G1; desenho no doc 47 do Sistema Physis, aprovado em 21/11/2026).

O gêmeo é o próprio projeto do Planejador (`physis.terreno/1.0`) com um campo a mais, `gemeo`. Nada de formato novo.

Três camadas sobre um mesmo cadastro de elementos:
- estático (projeto): geometria, zonas, sistemas. É o que a semente G0/G1 grava;
- simulado (esperado): séries que o projeto deveria produzir (etapa G4, ainda não feita);
- medido (real): leituras dos sensores (etapa G6). Fica vazia, "aguardando sensores", até haver obra e sensores.

Este módulo faz só a parte de elementos (ler a semente, agrupar por zona, somar, validar a procedência de cada
valor). Pontos de sensor (`gemeo_ponto`) e cenários de simulação (`gemeo_cenario`) existem só no esquema
(`ESQUEMA_SQL`): o hub ainda não cria essas tabelas.

Regras: nenhum número sai daqui que não esteja na semente com fonte; o que falta é `[MARCADOR]`, o que diverge no
acervo é `[CONFERIR]`, com o valor alternativo e a fonte. Sem dependências (Python 3.10).
"""
from __future__ import annotations

import json
from pathlib import Path

ESQUEMA = "physis.gemeo/0.1"
SCHEMA_PLANEJADOR = "physis.terreno/1.0"

CAMADAS = ("estatico", "simulado", "medido")
ESTADOS_DE_VIDA = ("projetado", "licenciado", "construído", "medido", "calibrado")
PROCEDENCIAS = ("estimado", "confirmado")

# Zonas e entidade dona de cada uma (doc 48 F1; D70: os dados das três entidades não se misturam).
# Faixas em y local, da Rua H para a Rua G (doc 01 §1/§3 e planilha 03).
ZONAS = {
    "Z1": {"nome": "Zona 1", "entidade": "Physis Engineering", "faixa_y_m": [0.0, 19.6]},
    "Z2": {"nome": "Zona 2", "entidade": "Instituto Physis", "faixa_y_m": [19.6, 38.9]},
    "Z3": {"nome": "Zona 3", "entidade": "Casa Physis", "faixa_y_m": [38.9, None]},
}
# Valores do lote inteiro (totais, sistemas que servem a mais de uma zona).
LOTE = "lote"
ENTIDADE_LOTE = "lote (as três entidades)"

# Esquema das tabelas que o hub vai ter (G5/G6). Só desenho: nada aqui é executado pelo hub nesta versão.
ESQUEMA_SQL = """
CREATE TABLE IF NOT EXISTS gemeo_ponto (
    id          INTEGER PRIMARY KEY,
    semente     TEXT NOT NULL,          -- ex.: casa-physis-rev0
    elemento    TEXT NOT NULL,          -- chave do elemento na semente (ex.: cist1)
    ativo       TEXT NOT NULL,          -- ativo do sensor no hub (tópico physis/{org}/{grandeza}/{ativo})
    grandeza    TEXT NOT NULL,          -- ENE, HID, PLUV, SEC, ZONA… (protocolo V6)
    unidade     TEXT,
    desde       TEXT,                   -- ISO 8601
    ate         TEXT,
    UNIQUE (semente, elemento, ativo, grandeza)
);
CREATE TABLE IF NOT EXISTS gemeo_cenario (
    id          INTEGER PRIMARY KEY,
    semente     TEXT NOT NULL,
    revisao     TEXT NOT NULL,
    modulo      TEXT NOT NULL,          -- ex.: simulacao.termica, agua, carbono
    entrada     TEXT NOT NULL,          -- JSON dos parâmetros
    hash        TEXT NOT NULL,          -- sha256 da entrada canônica (mesmo hash, mesmo resultado)
    saida       TEXT,                   -- JSON da série
    criado      TEXT NOT NULL,
    UNIQUE (semente, modulo, hash)
);
"""


# ---------------------------------------------------------------- valores com procedência

def valor(v, fonte, procedencia="estimado", zona=LOTE, unidade=None, conferir=None, marcador=None, nota=None):
    """Um valor da semente com a sua fonte. `conferir` = {divergencia, alternativas: [{valor, fonte}]}."""
    if procedencia not in PROCEDENCIAS:
        raise ValueError(f"procedência inválida: {procedencia}")
    if zona != LOTE and zona not in ZONAS:
        raise ValueError(f"zona inválida: {zona}")
    d = {"valor": v, "unidade": unidade, "fonte": fonte, "procedencia": procedencia,
         "zona": zona, "entidade": entidade_de(zona)}
    if conferir:
        d["conferir"] = conferir
    if marcador:
        d["marcador"] = marcador
    if nota:
        d["nota"] = nota
    return d


def entidade_de(zona):
    return ENTIDADE_LOTE if zona == LOTE else ZONAS[zona]["entidade"]


def zona_de(texto):
    """'Zona 2' → 'Z2'. Devolve None se o texto não é uma zona."""
    t = str(texto or "").strip().lower().replace("zona", "").strip()
    return {"1": "Z1", "2": "Z2", "3": "Z3"}.get(t)


# ---------------------------------------------------------------- leitura da semente

def carregar(caminho):
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def gemeo(projeto):
    g = projeto.get("gemeo")
    if not isinstance(g, dict):
        raise ValueError("projeto sem o campo gemeo")
    return g


def elementos(projeto):
    """Lista de elementos (ficha do gêmeo + item do Planejador), na ordem da planilha."""
    g = gemeo(projeto)
    itens = {i["id"]: i for i in projeto.get("itens", [])}
    out = []
    for chave, e in g["elementos"].items():
        it = itens.get(e.get("item_id"))
        out.append({"chave": chave, **e, "item": it,
                    "estado_de_vida": g["estado_de_vida"]["por_elemento"].get(chave, g["estado_de_vida"]["padrao"])})
    return out


def por_zona(projeto):
    z = {k: [] for k in ZONAS}
    for e in elementos(projeto):
        z[e["zona"]].append(e)
    return z


def totais(projeto):
    """Somas dos elementos (para conferir com a linha Total da planilha 03 › Implantação)."""
    els = elementos(projeto)
    soma = lambda campo: round(sum((e.get(campo) or 0) for e in els), 3)
    return {
        "elementos": len(els),
        "por_zona": {k: len(v) for k, v in por_zona(projeto).items()},
        "area_m2": soma("area_m2"),
        "corte_m3": soma("corte_m3"),
        "aterro_m3": soma("aterro_m3"),
    }


def conferir_abertos(projeto):
    """Valores com divergência no acervo ([CONFERIR]) ainda não resolvidos: caminho → divergência."""
    fv = gemeo(projeto)["fonte_por_valor"]
    return {p: d["conferir"]["divergencia"] for p, d in fv.items() if d.get("conferir")}


def marcadores(projeto):
    fv = gemeo(projeto)["fonte_por_valor"]
    return {p: d["marcador"] for p, d in fv.items() if d.get("marcador")}


def camada_medida(projeto):
    """Camada medida: vazia nesta versão (decisão R1-2)."""
    m = gemeo(projeto).get("camadas", {}).get("medido", {})
    return {"situacao": m.get("situacao", "aguardando sensores"), "pontos": m.get("pontos", [])}


# ---------------------------------------------------------------- validação

def validar(projeto):
    """Lista de problemas (vazia = semente íntegra). Não muda nada."""
    p = []
    if projeto.get("schema") != SCHEMA_PLANEJADOR:
        p.append(f"schema diferente de {SCHEMA_PLANEJADOR}")
    try:
        g = gemeo(projeto)
    except ValueError as e:
        return p + [str(e)]
    if g.get("esquema") != ESQUEMA:
        p.append(f"gemeo.esquema diferente de {ESQUEMA}")
    for campo in ("revisao", "fonte_por_valor", "estado_de_vida", "elementos"):
        if campo not in g:
            p.append(f"gemeo sem {campo}")
    if p:
        return p
    ids = {i.get("id") for i in projeto.get("itens", [])}
    ev = g["estado_de_vida"]
    if ev.get("padrao") not in ESTADOS_DE_VIDA:
        p.append(f"estado de vida padrão inválido: {ev.get('padrao')}")
    for chave, e in g["elementos"].items():
        if e.get("zona") not in ZONAS:
            p.append(f"{chave}: zona inválida {e.get('zona')}")
        elif e.get("entidade") != ZONAS[e["zona"]]["entidade"]:
            p.append(f"{chave}: entidade não é a da zona")
        if not e.get("fonte"):
            p.append(f"{chave}: sem fonte")
        if e.get("procedencia") not in PROCEDENCIAS:
            p.append(f"{chave}: procedência inválida")
        if e.get("item_id") not in ids:
            p.append(f"{chave}: item do Planejador ausente")
        est = ev["por_elemento"].get(chave, ev["padrao"])
        if est not in ESTADOS_DE_VIDA:
            p.append(f"{chave}: estado de vida inválido {est}")
    for caminho, d in g["fonte_por_valor"].items():
        if not d.get("fonte"):
            p.append(f"{caminho}: sem fonte")
        if d.get("procedencia") not in PROCEDENCIAS:
            p.append(f"{caminho}: procedência inválida")
        z = d.get("zona")
        if z != LOTE and z not in ZONAS:
            p.append(f"{caminho}: zona inválida")
        elif d.get("entidade") != entidade_de(z):
            p.append(f"{caminho}: entidade não é a da zona")
        if d.get("valor") is None and not d.get("marcador"):
            p.append(f"{caminho}: valor vazio sem [MARCADOR]")
        c = d.get("conferir")
        if c is not None:
            if not c.get("divergencia") or not c.get("alternativas"):
                p.append(f"{caminho}: [CONFERIR] sem divergência ou sem valor alternativo")
            for a in c.get("alternativas", []):
                if not a.get("fonte"):
                    p.append(f"{caminho}: valor alternativo sem fonte")
    return p
