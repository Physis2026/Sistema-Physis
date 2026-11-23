"""Relevo aberto (dem_cog): GeoTIFF em blocos, deflate e preditor de ponto flutuante, só com a biblioteca padrão.

Protege: a leitura da janela (com o preditor 3 do Copernicus, desfeito byte a byte), a grade .asc em graus que o
Planejador importa, e, quando o tile Copernicus S23 W044 está na máquina, que o entorno do lote tem as cotas do
levantamento (875 a 903 m) dentro da faixa do modelo de superfície.
"""
import os
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from physis_hub import dem_cog as D

TILE = Path(r"C:\physis\ferramentas-abertas\dados\relevo\Copernicus_DSM_COG_10_S23_00_W044_00_DEM.tif")


def _tiff_sintetico(caminho, W=8, H=8, tw=4, th=4, f=lambda r, c: 900.0 + r - 0.5 * c):
    """TIFF clássico em blocos, float32, deflate, preditor 3, geográfico (como o Copernicus)."""
    blocos = []
    for br in range(0, H, th):
        for bc in range(0, W, tw):
            dados = bytearray()
            for r in range(th):
                bs = [struct.pack(">f", f(br + r, bc + c)) for c in range(tw)]
                linha = bytearray(b[k] for k in range(4) for b in bs)       # bytes do mais significativo ao menos
                dif = bytearray(linha[:1]) + bytearray((linha[i] - linha[i - 1]) & 0xFF for i in range(1, len(linha)))
                dados += dif
            blocos.append(zlib.compress(bytes(dados)))
    tags = [(256, 3, 1, W), (257, 3, 1, H), (258, 3, 1, 32), (259, 3, 1, 8), (277, 3, 1, 1), (317, 3, 1, 3),
            (322, 3, 1, tw), (323, 3, 1, th), (339, 3, 1, 3)]
    corpo = bytearray(b"II*\x00" + struct.pack("<I", 0))
    offs = []
    for b in blocos:
        offs.append(len(corpo))
        corpo += b
    extra = {}
    def anexar(fmt, vals):
        pos = len(corpo)
        corpo.extend(struct.pack("<" + fmt * len(vals), *vals))
        return pos
    extra[324] = (4, len(offs), anexar("I", offs))
    extra[325] = (4, len(blocos), anexar("I", [len(b) for b in blocos]))
    extra[33550] = (12, 3, anexar("d", [0.5, 0.5, 0.0]))
    extra[33922] = (12, 6, anexar("d", [0, 0, 0, -44.0, -22.0, 0.0]))
    ifd = len(corpo)
    entradas = [(t, ty, n, struct.pack("<HH", v, 0) if ty == 3 else struct.pack("<I", v)) for t, ty, n, v in tags]
    entradas += [(t, ty, n, struct.pack("<I", pos)) for t, (ty, n, pos) in extra.items()]
    entradas.sort()
    corpo += struct.pack("<H", len(entradas))
    for t, ty, n, v in entradas:
        corpo += struct.pack("<HHI", t, ty, n) + v
    corpo += struct.pack("<I", 0)
    corpo[4:8] = struct.pack("<I", ifd)
    Path(caminho).write_bytes(bytes(corpo))


class DemCog(unittest.TestCase):
    def test_janela_com_preditor_de_ponto_flutuante(self):
        with tempfile.TemporaryDirectory() as d:
            arq = os.path.join(d, "t.tif")
            _tiff_sintetico(arq)
            # centro na linha 4, coluna 5 (lat = −22 − 4·0,5; lon = −44 + 5·0,5): atravessa os 4 blocos
            linhas, lon0, lat0, passo = D.janela(arq, -24.0, -41.5, 2)
            self.assertEqual((len(linhas), len(linhas[0]), passo), (5, 5, 0.5))
            for i, r in enumerate(range(2, 7)):
                for j, c in enumerate(range(3, 8)):
                    self.assertAlmostEqual(linhas[i][j], 900.0 + r - 0.5 * c, places=4)
            asc = os.path.join(d, "t.asc")
            D.escrever_asc(asc, linhas, lon0, lat0, passo)
            cab = Path(asc).read_text(encoding="ascii").splitlines()
            self.assertEqual(cab[0], "ncols 5")
            self.assertTrue(cab[2].startswith("xllcorner -42.75"))
            with self.assertRaises(ValueError):
                D.janela(arq, -22.0, -44.0, 2)            # borda do tile

    @unittest.skipUnless(TILE.exists(), "tile Copernicus S23 W044 não está nesta máquina")
    def test_entorno_do_lote_no_copernicus(self):
        linhas, _, _, _ = D.janela(TILE, -22.4255, -43.1427, 2)
        vals = [v for l in linhas for v in l]
        self.assertTrue(850 < min(vals) and max(vals) < 930, vals)   # levantamento: 875 a 903 m (+ copa das árvores)


if __name__ == "__main__":
    unittest.main()
