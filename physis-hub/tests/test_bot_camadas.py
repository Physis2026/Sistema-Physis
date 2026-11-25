"""Bot de camadas (camadas_bot.py). Respostas falsas no lugar da internet e do GDAL."""
import json, tempfile, unittest, zipfile, io
from pathlib import Path
from physis_hub import camadas_bot as cb, mapeamento as mp

CID = [{"id": "x", "nome": "X", "uf": "RJ", "lat": -22.5, "lon": -43.2, "raio_km": 10}]

def pegar(url, dados=None):
    if "overpass" in url:
        return json.dumps({"elements": [
            {"type": "way", "id": 1, "tags": {"waterway": "river", "name": "Rio Teste"}, "geometry": [{"lon": -43.21, "lat": -22.5}, {"lon": -43.2, "lat": -22.49}]},
            {"type": "node", "id": 2, "tags": {"natural": "spring"}, "lon": -43.2, "lat": -22.5},
            {"type": "way", "id": 3, "tags": {"power": "line", "voltage": "138000"}, "geometry": [{"lon": -43.3, "lat": -22.6}, {"lon": -43.1, "lat": -22.4}]}]}).encode()
    if "power.larc" in url:
        sol = {m: 4.0 + i * 0.1 for i, m in enumerate(cb.MESES)}; sol["ANN"] = 4.5
        return json.dumps({"properties": {"parameter": {"ALLSKY_SFC_SW_DWN": sol, "WS50M": {"ANN": 5.2}}}}).encode()
    if url.endswith(".zip"):
        b = io.BytesIO(); z = zipfile.ZipFile(b, "w"); z.writestr("BRA_X.epw", "LOCATION,X\n"); z.close(); return b.getvalue()
    raise OSError("sem rede")

class Bot(unittest.TestCase):
    def test_automaticas_e_faltas(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "camadas"
            r = cb.rodar_bot(p, CID, pegar=pegar)
            c = r["camadas"]
            self.assertIn("provisória", c["hidrografia"]["situacao"]); self.assertIn("provisória", c["vento"]["situacao"])
            self.assertEqual(sorted(r["faltam"]), ["car", "clima", "risco", "solos", "uso_solo"])
            self.assertTrue((p / "fontes-camadas.txt").is_file())
            gj = json.loads((p / "hidrografia.geojson").read_text(encoding="utf-8"))
            self.assertEqual(len(gj["features"]), 3)            # mesma consulta para rios e nascentes (falsa); rede usa outra
            meta = json.loads((p / "vento.asc.fonte.json").read_text(encoding="utf-8"))
            self.assertTrue(meta["provisoria"])
            j = mp.ler_asc_janela(p / "vento.asc", (-43.6, -22.6, -42.9, -22.4))
            self.assertTrue(j["valores"]) ; self.assertEqual(set(j["valores"]), {5.2})
            self.assertTrue((p / "irradiacao_12.asc").is_file())
            # segunda rodada: nada a refazer
            r2 = cb.rodar_bot(p, CID, pegar=lambda *a, **k: (_ for _ in ()).throw(OSError("não devia baixar")))
            self.assertEqual(r2["camadas"]["vento"]["situacao"], "ok")
            # fonte oficial do clima
            (p / "fontes-camadas.txt").write_text("clima;https://exemplo.org/BRA_X.zip\n", encoding="utf-8")
            r3 = cb.rodar_bot(p, CID, ["clima"], pegar=pegar)
            self.assertEqual(r3["camadas"]["clima"]["situacao"], "baixada (oficial)")
            self.assertTrue((p / "clima" / "BRA_X.epw").is_file())

    def test_sem_internet(self):
        with tempfile.TemporaryDirectory() as d:
            r = cb.rodar_bot(Path(d), CID, ["hidrografia", "vento"], pegar=lambda *a, **k: (_ for _ in ()).throw(OSError("sem rede")))
            self.assertEqual(sorted(r["faltam"]), ["hidrografia", "vento"])

class Brasil(unittest.TestCase):
    def test_brasil_limites_e_grade(self):
        def pg(url, dados=None):
            if "malhas/paises/BR" in url:
                return json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"codarea": "1"},
                    "geometry": {"type": "Polygon", "coordinates": [[[-44.0, -23.0], [-43.0, -23.0], [-43.0, -22.0], [-44.0, -22.0], [-44.0, -23.0]]]}}]}).encode()
            return pegar(url)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "camadas"
            r = cb.brasil(p, ["limites", "irradiacao", "vento"], pegar=pg, pausa=0)
            self.assertEqual(r["faltam"], [])
            self.assertEqual(r["camadas"]["irradiacao"]["pontos"], 9)          # -44..-43 × -23..-22 em 0,5°
            self.assertTrue(json.loads((p / "limites.geojson.fonte.json").read_text(encoding="utf-8"))["oficial"])
            self.assertEqual(set(mp.ler_asc_janela(p / "vento.asc", (-44.1, -23.1, -42.9, -21.9))["valores"]), {5.2})

    def test_gdal_sem_qgis(self):
        import unittest.mock as um
        with um.patch.object(cb, "achar_gdal", return_value=None):
            with self.assertRaises(ValueError):
                cb.gdal(["ogr2ogr"])


class GradeGrossa(unittest.TestCase):
    def test_lote_pequeno_pega_a_celula_do_centro(self):
        with tempfile.TemporaryDirectory() as d:
            a = Path(d) / "v.asc"
            a.write_text("ncols 2\nnrows 2\nxllcenter -43.5\nyllcenter -23.0\ncellsize 0.5\nNODATA_value -9999\n1 2\n3 4\n", encoding="ascii")
            j = mp.ler_asc_janela(a, (-43.25, -22.55, -43.10, -22.40))     # centro -43.175, -22.475: célula de cima à direita
            self.assertEqual(j["valores"], [2.0])
            self.assertEqual(mp.ler_asc_janela(a, (-40.0, -20.0, -39.9, -19.9))["valores"], [])   # fora da grade

if __name__ == "__main__":
    unittest.main()
