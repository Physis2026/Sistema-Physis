#!/usr/bin/env python3
r"""Baixa as camadas que têm serviço público estável e grava na pasta PHYSIS_CAMADAS (24/11/2026).

    py ferramentas\baixar_camadas.py --pasta C:\physis\camadas --municipio 3303906 --bbox=-43.25,-22.55,-43.10,-22.40

  limites.geojson  ← IBGE, API de malhas (código IBGE do município; Petrópolis/RJ = 3303906 [CONFERIR])
  osm.geojson      ← OpenStreetMap via Overpass (edificações e vias na janela --bbox, até 0,25°; ODbL: citar a fonte)

As outras camadas (relevo, hidrografia, uso do solo, solos, CAR, clima EPW, risco, irradiação, vento, rede elétrica) não têm
serviço simples e estável: o guia implantacao/PROGRAMAS-E-CAMADAS-ACER.md diz onde baixar. Internet só durante o download; depois
tudo funciona sem ela (regra 11). Cada arquivo leva _fonte com a URL, a data e a licença.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

URL_IBGE = "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{cod}?formato=application/vnd.geo+json"
URL_OVERPASS = "https://overpass-api.de/api/interpreter"
MAX_BBOX = 0.25


def buscar(url: str, dados: bytes | None = None, tempo: int = 120) -> bytes:
    req = urllib.request.Request(url, data=dados, headers={"User-Agent": "Physis-camadas/1 (servidor da Physis)"})
    with urllib.request.urlopen(req, timeout=tempo) as r:
        return r.read()


def limites(cod: str, pegar=buscar) -> dict:
    if not cod.isdigit() or len(cod) != 7:
        raise ValueError("código IBGE do município tem 7 dígitos")
    url = URL_IBGE.format(cod=cod)
    gj = json.loads(pegar(url).decode("utf-8"))
    if gj.get("type") not in ("FeatureCollection", "Feature"):
        raise ValueError("resposta do IBGE sem GeoJSON")
    gj["_fonte"] = {"url": url, "baixado": time.strftime("%Y-%m-%d"), "licenca": "dados públicos do IBGE, citar a fonte [CONFERIR]"}
    return gj


def osm(bbox: list[float], pegar=buscar) -> dict:
    o, s, l, n = bbox
    if not (l > o and n > s) or (l - o) > MAX_BBOX or (n - s) > MAX_BBOX:
        raise ValueError(f"janela inválida ou maior que {MAX_BBOX}° (use oeste,sul,leste,norte)")
    q = f'[out:json][timeout:90];(way["building"]({s},{o},{n},{l});way["highway"]({s},{o},{n},{l}););out geom;'
    j = json.loads(pegar(URL_OVERPASS, urllib.parse.urlencode({"data": q}).encode()).decode("utf-8"))
    feats = []
    for el in j.get("elements", []):
        g = el.get("geometry") or []
        if el.get("type") != "way" or len(g) < 2:
            continue
        cs = [[p["lon"], p["lat"]] for p in g]
        tags = el.get("tags", {})
        if "building" in tags and cs[0] == cs[-1] and len(cs) >= 4:
            geom = {"type": "Polygon", "coordinates": [cs]}
            props = {"tipo": "edificacao", "niveis": tags.get("building:levels"), "altura": tags.get("height")}
        else:
            geom = {"type": "LineString", "coordinates": cs}
            props = {"tipo": "via", "classe": tags.get("highway"), "nome": tags.get("name")}
        props["osm_id"] = el.get("id")
        feats.append({"type": "Feature", "geometry": geom, "properties": {k: v for k, v in props.items() if v is not None}})
    return {"type": "FeatureCollection", "features": feats,
            "_fonte": {"url": URL_OVERPASS, "baixado": time.strftime("%Y-%m-%d"), "licenca": "© colaboradores do OpenStreetMap, ODbL 1.0", "janela": bbox}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pasta", default=os.environ.get("PHYSIS_CAMADAS") or "")
    ap.add_argument("--municipio", help="código IBGE (7 dígitos)")
    ap.add_argument("--bbox", help="oeste,sul,leste,norte em graus (até 0,25°)")
    a = ap.parse_args(argv)
    if not a.pasta:
        print("Informe --pasta ou defina PHYSIS_CAMADAS.")
        return 2
    pasta = Path(a.pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    feitos, erros = [], []
    if a.municipio:
        try:
            (pasta / "limites.geojson").write_text(json.dumps(limites(a.municipio), ensure_ascii=False), encoding="utf-8")
            feitos.append("limites.geojson")
        except Exception as e:  # noqa: BLE001
            erros.append(f"limites: {e}")
    if a.bbox:
        try:
            g = osm([float(x) for x in a.bbox.split(",")])
            (pasta / "osm.geojson").write_text(json.dumps(g, ensure_ascii=False), encoding="utf-8")
            feitos.append(f"osm.geojson ({len(g['features'])} feições)")
        except Exception as e:  # noqa: BLE001
            erros.append(f"osm: {e}")
    print("Gravado em", pasta, ":", ", ".join(feitos) or "nada")
    for e in erros:
        print("ERRO", e)
    print("As outras camadas: ver implantacao/PROGRAMAS-E-CAMADAS-ACER.md (seção 8).")
    return 0 if not erros else 1


if __name__ == "__main__":
    sys.exit(main())
