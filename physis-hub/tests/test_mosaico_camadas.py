"""Camadas em mosaico (estados inteiros): ladrilhos, índice e escolha do ladrilho pela janela."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ferramentas"))
import mosaico_camadas as mc  # noqa: E402
from physis_hub import mapeamento as m  # noqa: E402

ASC = "ncols 4\nnrows 4\nxllcorner {x}\nyllcorner {y}\ncellsize {c}\nNODATA_value -9999\n" + "\n".join(["900 901 902 903"] * 4) + "\n"


class Mosaico(unittest.TestCase):
    def test_toda_janela_cabe_num_ladrilho(self):
        ts = mc.ladrilhos({"X": [-44.2, -23.4, -41.9, -20.7]}, 1.0, 0.3)
        self.assertEqual(len(ts), 4 * 4)            # de -45 a -41 e de -24 a -20, graus inteiros
        b = [-43.27, -22.13, -43.02, -21.88]          # janela de 0,25° cruzando a divisa de dois ladrilhos
        ok = [t for t in ts if t["bbox"][0] <= b[0] and t["bbox"][1] <= b[1] and t["bbox"][2] >= b[2] and t["bbox"][3] >= b[3]]
        self.assertTrue(ok)
        with self.assertRaises(ValueError):
            mc.ladrilhos({"X": [0, 0, 1, 1]}, 1.0, 0.1)

    def test_bbox_da_malha(self):
        gj = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-48, -16], [-47, -16], [-47, -15], [-48, -16]]]}}]}
        self.assertEqual(mc._bbox_geo(gj), [-48, -16, -47, -15])
        self.assertEqual(mc.bbox_uf("DF", baixar=lambda u: {"id": 53} if "localidades" in u else gj), [-48, -16, -47, -15])

    def test_servidor_le_o_ladrilho_certo(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            p = Path(d) / "relevo"
            p.mkdir()
            (p / "a.asc").write_text(ASC.format(x=-44.3, y=-23.3, c=0.4), encoding="utf-8")
            (p / "indice.json").write_text(json.dumps([{"arquivo": "a.asc", "bbox": [-44.3, -23.3, -42.7, -21.7]}]), encoding="utf-8")
            cat = {c["id"]: c["status"] for c in m.catalogo(d)}
            self.assertEqual(cat["relevo"], "instalada")
            r = m.camada("relevo", [-43.2, -22.6, -43.0, -22.4], pasta=d)
            self.assertTrue(r.get("ok"), r)
            fora = m.camada("relevo", [-50.2, -10.6, -50.0, -10.4], pasta=d)
            self.assertFalse(fora["ok"])
            self.assertTrue(fora.get("sem_camada"))

    def test_simular_sem_gdal(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            bb = Path(d) / "b.json"
            bb.write_text(json.dumps({"DF": [-48.3, -16.1, -47.3, -15.5]}), encoding="utf-8")
            self.assertEqual(mc.main(["--ufs", "DF", "--camada", "relevo", "--entrada", "x.tif", "--pasta", d, "--bboxes", str(bb), "--simular"]), 0)


if __name__ == "__main__":
    unittest.main()
