#!/usr/bin/env python3
r"""Monta camadas em MOSAICO para estados inteiros (pedido de 24/11/2026: DF, GO, BA, SP, RJ, MG).

O servidor lê no máximo 256 MB por arquivo; um estado inteiro passa disso. Aqui o arquivo oficial (GeoTIFF, VRT,
Shapefile, GeoPackage...) vira ladrilhos de --ladrilho graus com --sobra graus de sobreposição em cada lado, mais um
indice.json. Como a sobra é maior que a janela máxima do servidor (0,25°), toda consulta cabe num ladrilho só.

    # no "OSGeo4W Shell" do QGIS (traz gdalwarp, gdal_translate e ogr2ogr):
    py ferramentas\mosaico_camadas.py --ufs DF,GO,BA,SP,RJ,MG --camada relevo --entrada D:\dados\copernicus.vrt --pasta C:\physis\camadas
    py ferramentas\mosaico_camadas.py --ufs RJ --camada hidrografia --entrada D:\dados\bho_trechos.gpkg --pasta C:\physis\camadas
    --simular       só mostra os ladrilhos e os comandos
    --classes       raster de classes (uso do solo): reamostragem pelo vizinho mais próximo

A janela de cada estado vem da malha oficial do IBGE (API de malhas, baixada uma vez) ou de --bboxes <arquivo.json>
({"RJ": [oeste, sul, leste, norte], ...}) para trabalhar sem internet. Nenhuma coordenada vem escrita aqui.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

URL_UF = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}"
URL_MALHA = "https://servicodados.ibge.gov.br/api/v3/malhas/estados/{cod}?formato=application/vnd.geo+json&qualidade=minima"
JANELA_MAX = 0.25          # igual a mapeamento.MAX_BBOX_GRAUS
MAX_BYTES = 256 * 1024 * 1024
RASTER = {"relevo", "uso_solo", "irradiacao", "vento"}
VETOR = {"limites", "hidrografia", "solos", "car", "risco", "rede_eletrica", "osm"}


def _baixar(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Physis-mosaico/1"}), timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def _bbox_geo(gj) -> list[float]:
    xs, ys = [], []

    def anda(c):
        if c and isinstance(c[0], (int, float)):
            xs.append(c[0]); ys.append(c[1])
        else:
            for x in c:
                anda(x)
    feats = gj.get("features") or ([gj] if gj.get("type") == "Feature" else [])
    for f in feats:
        anda((f.get("geometry") or {}).get("coordinates") or [])
    if not xs:
        raise ValueError("malha sem coordenadas")
    return [min(xs), min(ys), max(xs), max(ys)]


def bbox_uf(uf: str, baixar=_baixar) -> list[float]:
    cod = baixar(URL_UF.format(uf=uf.lower()))["id"]
    return _bbox_geo(baixar(URL_MALHA.format(cod=cod)))


def ladrilhos(bboxes: dict, passo: float = 1.0, sobra: float = 0.3) -> list[dict]:
    """Grade de passo° alinhada em graus inteiros, só onde toca algum estado; cada ladrilho ganha 'sobra' em volta."""
    if sobra < JANELA_MAX:
        raise ValueError(f"sobra precisa ser >= {JANELA_MAX}° para toda janela caber num ladrilho")
    vistos, out = set(), []
    for uf, (o, s, l, n) in sorted(bboxes.items()):
        for i in range(math.floor(o / passo), math.ceil(l / passo)):
            for j in range(math.floor(s / passo), math.ceil(n / passo)):
                if (i, j) in vistos:
                    continue
                vistos.add((i, j))
                x0, y0 = i * passo, j * passo
                nome = f"{'S' if y0 < 0 else 'N'}{abs(y0):05.1f}_{'W' if x0 < 0 else 'E'}{abs(x0):05.1f}".replace(".", "p")
                out.append({"nome": nome, "nucleo": [x0, y0, x0 + passo, y0 + passo],
                            "bbox": [round(x0 - sobra, 6), round(y0 - sobra, 6), round(x0 + passo + sobra, 6), round(y0 + passo + sobra, 6)]})
    return out


def comandos(camada: str, entrada: str, destino: Path, t: dict, classes: bool = False) -> list[list[str]]:
    o, s, l, n = t["bbox"]
    if camada in RASTER:
        tmp = destino / f"{t['nome']}.tif"
        asc = destino / f"{t['nome']}.asc"
        return [["gdalwarp", "-overwrite", "-t_srs", "EPSG:4326", "-te", str(o), str(s), str(l), str(n),
                 "-r", "near" if classes else "bilinear", entrada, str(tmp)],
                ["gdal_translate", "-of", "AAIGrid", str(tmp), str(asc)]]
    return [["ogr2ogr", "-f", "GeoJSON", "-t_srs", "EPSG:4326", "-clipsrc", str(o), str(s), str(l), str(n),
             str(destino / f"{t['nome']}.geojson"), entrada]]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ufs", required=True)
    ap.add_argument("--camada", required=True, choices=sorted(RASTER | VETOR))
    ap.add_argument("--entrada", required=True)
    ap.add_argument("--pasta", required=True)
    ap.add_argument("--bboxes", help="JSON {UF: [oeste, sul, leste, norte]} (sem internet)")
    ap.add_argument("--ladrilho", type=float, default=1.0)
    ap.add_argument("--sobra", type=float, default=0.3)
    ap.add_argument("--classes", action="store_true")
    ap.add_argument("--simular", action="store_true")
    a = ap.parse_args(argv)
    ufs = [u.strip().upper() for u in a.ufs.split(",") if u.strip()]
    dadas = json.loads(Path(a.bboxes).read_text(encoding="utf-8")) if a.bboxes else {}
    bbs = {}
    for uf in ufs:
        bbs[uf] = dadas.get(uf) or bbox_uf(uf)
        print(f"{uf}: janela {[round(x, 3) for x in bbs[uf]]}")
    ts = ladrilhos(bbs, a.ladrilho, a.sobra)
    destino = Path(a.pasta) / a.camada
    print(f"{len(ts)} ladrilhos de {a.ladrilho}° (+{a.sobra}° de sobra) em {destino}")
    if not a.simular:
        for p in ("gdalwarp", "gdal_translate") if a.camada in RASTER else ("ogr2ogr",):
            if not shutil.which(p):
                print(f"{p} não encontrado: rode no 'OSGeo4W Shell' do QGIS.")
                return 2
        destino.mkdir(parents=True, exist_ok=True)
    indice, grandes = [], []
    for k, t in enumerate(ts, 1):
        cmds = comandos(a.camada, a.entrada, destino, t, a.classes)
        if a.simular:
            if k <= 3:
                print("  " + " && ".join(" ".join(c) for c in cmds))
            continue
        for c in cmds:
            r = subprocess.run(c, capture_output=True, text=True)
            if r.returncode != 0:
                print(f"ERRO no ladrilho {t['nome']}: {(r.stderr or r.stdout)[-400:]}")
                return 1
        arq = destino / (t["nome"] + (".asc" if a.camada in RASTER else ".geojson"))
        (destino / f"{t['nome']}.tif").unlink(missing_ok=True)
        if arq.stat().st_size > MAX_BYTES:
            grandes.append(arq.name)
        indice.append({"arquivo": arq.name, "bbox": t["bbox"]})
        print(f"  {k}/{len(ts)} {arq.name} ({arq.stat().st_size / 1e6:.1f} MB)")
    if not a.simular:
        (destino / "indice.json").write_text(json.dumps(indice, indent=1), encoding="utf-8")
        print(f"indice.json com {len(indice)} ladrilhos")
        if grandes:
            print("AVISO: acima de 256 MB (o servidor recusa): use --ladrilho 0.5 →", ", ".join(grandes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
