"""Relevo aberto (Copernicus DEM GLO-30 e outros GeoTIFF em blocos) só com a biblioteca padrão.

    python -m physis_hub.dem_cog ARQUIVO.tif --lat −22.4253 --lon −43.1427 --raio 36 --saida entorno.asc

Lê a janela em volta de um ponto de um GeoTIFF clássico em blocos (tiled), float32, sem compressão ou com deflate
(compressão 8 ou 32946), com ou sem preditor (1, 2 ou 3 = ponto flutuante), em coordenadas geográficas
(ModelPixelScale + ModelTiepoint), e grava em ESRI ASCII Grid (.asc), que o Planejador importa no passo 1.
Substitui a API do OpenTopography (que pede cadastro) pelo tile aberto do bucket público do Copernicus (regra 11).
"""
from __future__ import annotations

import argparse
import struct
import sys
import zlib
from pathlib import Path

_TAM = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 16: 8}
_FMT = {1: "B", 3: "H", 4: "I", 8: "h", 9: "i", 11: "f", 12: "d", 16: "Q"}


def _tags(f):
    f.seek(0)
    cab = f.read(16)
    bo = "<" if cab[:2] == b"II" else ">"
    if struct.unpack(bo + "H", cab[2:4])[0] != 42:
        raise ValueError("só TIFF clássico (não BigTIFF)")
    f.seek(struct.unpack(bo + "I", cab[4:8])[0])
    n = struct.unpack(bo + "H", f.read(2))[0]
    tags = {}
    for _ in range(n):
        tag, typ, cnt = struct.unpack(bo + "HHI", f.read(8))
        raw = f.read(4)
        sz = _TAM[typ] * cnt
        if sz > 4:
            pos = f.tell()
            f.seek(struct.unpack(bo + "I", raw)[0])
            raw = f.read(sz)
            f.seek(pos)
        if typ == 2:
            tags[tag] = raw[:sz].rstrip(b"\0").decode("latin-1")
        elif typ in _FMT:
            tags[tag] = struct.unpack(bo + _FMT[typ] * cnt, raw[:sz])
    return bo, tags


def _bloco(f, bo, tags, k, tw, th):
    f.seek(tags[324][k])
    dados = f.read(tags[325][k])
    comp = tags.get(259, (1,))[0]
    if comp in (8, 32946):
        dados = zlib.decompress(dados)
    elif comp != 1:
        raise ValueError(f"compressão {comp} não suportada")
    pred = tags.get(317, (1,))[0]
    vals = []
    if pred == 3:            # preditor de ponto flutuante: diferenças por byte, bytes do mais significativo ao menos
        for r in range(th):
            linha = bytearray(dados[r * tw * 4:(r + 1) * tw * 4])
            for i in range(1, len(linha)):
                linha[i] = (linha[i] + linha[i - 1]) & 0xFF
            vals.extend(struct.unpack(">f", bytes((linha[j], linha[tw + j], linha[2 * tw + j], linha[3 * tw + j])))[0]
                        for j in range(tw))
    else:
        vals = list(struct.unpack(bo + "f" * (tw * th), dados[:tw * th * 4]))
        if pred == 2:
            for r in range(th):
                for j in range(1, tw):
                    vals[r * tw + j] += vals[r * tw + j - 1]
    return vals


def janela(caminho, lat, lon, raio):
    """(linhas, lon0, lat_topo, passo): grade (2·raio+1)² de cotas em volta de (lat, lon), norte para cima."""
    with open(caminho, "rb") as f:
        bo, tags = _tags(f)
        if tags.get(258, (32,))[0] != 32 or tags.get(339, (3,))[0] != 3:
            raise ValueError("só float32")
        W, H = tags[256][0], tags[257][0]
        tw, th = tags[322][0], tags[323][0]
        dx, dy = tags[33550][0], tags[33550][1]
        lon_or, lat_or = tags[33922][3], tags[33922][4]
        col, lin = round((lon - lon_or) / dx), round((lat_or - lat) / dy)
        if not (raio <= col < W - raio and raio <= lin < H - raio):
            raise ValueError("ponto perto demais da borda do tile")
        por_lin = (W + tw - 1) // tw
        cache, out = {}, []
        for r in range(lin - raio, lin + raio + 1):
            linha = []
            for c in range(col - raio, col + raio + 1):
                k = (r // th) * por_lin + c // tw
                if k not in cache:
                    cache[k] = _bloco(f, bo, tags, k, tw, th)
                linha.append(cache[k][(r % th) * tw + c % tw])
            out.append(linha)
        return out, lon_or + (col - raio) * dx, lat_or - (lin - raio) * dy, dx


def escrever_asc(caminho, linhas, lon0, lat_topo, passo):
    """ESRI ASCII Grid em graus (o Planejador reconhece coordenadas geográficas e converte para metros locais)."""
    n_l, n_c = len(linhas), len(linhas[0])
    cab = [f"ncols {n_c}", f"nrows {n_l}", f"xllcorner {lon0 - passo / 2:.9f}",
           f"yllcorner {lat_topo - (n_l - 1) * passo - passo / 2:.9f}", f"cellsize {passo:.12f}", "NODATA_value -9999"]
    corpo = [" ".join(f"{v:.2f}" for v in l) for l in linhas]
    Path(caminho).write_text("\n".join(cab + corpo) + "\n", encoding="ascii")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Recorta um GeoTIFF (Copernicus DEM) em volta de um ponto e grava .asc")
    ap.add_argument("tif")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--raio", type=int, default=36, help="pixels para cada lado (36 ≈ 1 km no Copernicus 30 m)")
    ap.add_argument("--saida", required=True)
    a = ap.parse_args(argv)
    linhas, lon0, lat0, passo = janela(a.tif, a.lat, a.lon, a.raio)
    escrever_asc(a.saida, linhas, lon0, lat0, passo)
    vals = [v for l in linhas for v in l]
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{len(linhas)}×{len(linhas[0])} células; cota {min(vals):.1f} a {max(vals):.1f} m; gravado em {a.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
