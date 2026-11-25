"""Gêmeo digital da Casa Physis na plataforma do cliente (25/11/2026): leitura da semente e do IFC para a aba
"Gêmeo digital", dentro do Planejador da plataforma. Só leitura: nada aqui muda a semente (gemeo.py valida).

Onde a semente fica (o primeiro que existir):
  1. PHYSIS_GEMEO (pasta com casa-physis-rev0.json e .ifc);
  2. pasta "gemeo" ao lado do instancia.json (montar.py copia para as fichas casa-physis*);
  3. modulos/planejador/gemeo do repositório (hub rodando direto do repositório).
Sem semente, a aba não aparece (instância sem gêmeo).
"""
from __future__ import annotations

import os
from pathlib import Path

from . import gemeo as G

AQUI = Path(__file__).resolve().parent
NOME = "casa-physis-rev0"


def pasta_gemeo(instancia_dir: Path | None = None) -> Path | None:
    cands = []
    if os.environ.get("PHYSIS_GEMEO"):
        cands.append(Path(os.environ["PHYSIS_GEMEO"]))
    if instancia_dir is not None:
        cands.append(Path(instancia_dir) / "gemeo")
    cands.append(AQUI.parent / "gemeo")
    cands.append(AQUI.parents[1] / "modulos" / "planejador" / "gemeo")
    for c in cands:
        if (c / f"{NOME}.json").is_file():
            return c
    return None


def resumo(pasta: Path) -> dict:
    proj = G.carregar(pasta / f"{NOME}.json")
    els = G.elementos(proj)
    estados: dict = {}
    for e in els:
        estados[e["estado_de_vida"]] = estados.get(e["estado_de_vida"], 0) + 1
    zonas = []
    for z, lista in G.por_zona(proj).items():
        zonas.append({"zona": z, "nome": G.ZONAS[z].get("nome", z), "entidade": G.ZONAS[z]["entidade"],
                      "elementos": len(lista), "area_m2": round(sum((e.get("area_m2") or 0) for e in lista), 2),
                      "itens": [{"chave": e["chave"], "nome": (e.get("item") or {}).get("nome") or e.get("nome") or e["chave"],
                                 "estado": e["estado_de_vida"], "area_m2": e.get("area_m2")} for e in lista]})
    meta = proj.get("meta") or {}
    ter = proj.get("terreno") or {}
    abertos, marc = G.conferir_abertos(proj), G.marcadores(proj)
    return {"ok": True, "nome": meta.get("nome"), "municipio": meta.get("municipio"), "uf": meta.get("uf"),
            "revisao": G.gemeo(proj).get("revisao"), "lat0": ter.get("lat0"), "lon0": ter.get("lon0"),
            "totais": G.totais(proj), "estados": estados, "zonas": zonas, "validacao": G.validar(proj),
            "conferir": [{"campo": k, "divergencia": v} for k, v in list(abertos.items())[:50]], "conferir_total": len(abertos),
            "marcadores": [{"campo": k, "marcador": v} for k, v in list(marc.items())[:50]], "marcadores_total": len(marc),
            "medido": G.camada_medida(proj), "ifc": (pasta / f"{NOME}.ifc").is_file(),
            "aviso": "Versão de TESTE: estudo preliminar; valores estimados com fonte; não substitui projeto executivo."}


def rota(caminho: str, instancia_dir: Path | None = None):
    """(código, dict) ou ("bytes", nome, tipo, dados)."""
    pasta = pasta_gemeo(instancia_dir)
    if pasta is None:
        return 404, {"ok": False, "erro": "esta instalação não tem gêmeo digital"}
    c = caminho.rstrip("/")
    try:
        if c == "/api/gemeo":
            return 200, resumo(pasta)
        if c == "/api/gemeo/semente":
            return ("bytes", f"{NOME}.json", "application/json; charset=utf-8", (pasta / f"{NOME}.json").read_bytes())
        if c == "/api/gemeo/ifc" and (pasta / f"{NOME}.ifc").is_file():
            return ("bytes", f"{NOME}.ifc", "application/x-step", (pasta / f"{NOME}.ifc").read_bytes())
    except (OSError, ValueError, KeyError) as e:
        return 500, {"ok": False, "erro": f"semente do gêmeo ilegível: {e}"}
    return 404, {"ok": False, "erro": "rota desconhecida"}
