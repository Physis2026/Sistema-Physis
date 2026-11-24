"""Download das camadas com serviço público (IBGE e OpenStreetMap), sem rede no teste; gêmeo digital no Planejador (24/11/2026)."""
import importlib.util
import json
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("baixar_camadas", RAIZ / "ferramentas" / "baixar_camadas.py")
bc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bc)


class Camadas(unittest.TestCase):
    def test_limites(self):
        gj = bc.limites("3303906", pegar=lambda u, d=None: json.dumps({"type": "FeatureCollection", "features": []}).encode())
        self.assertIn("3303906", gj["_fonte"]["url"])
        with self.assertRaises(ValueError):
            bc.limites("33", pegar=lambda u, d=None: b"{}")

    def test_osm(self):
        resp = {"elements": [
            {"type": "way", "id": 1, "tags": {"building": "yes"}, "geometry": [{"lon": 0, "lat": 0}, {"lon": 1, "lat": 0}, {"lon": 1, "lat": 1}, {"lon": 0, "lat": 0}]},
            {"type": "way", "id": 2, "tags": {"highway": "residential", "name": "Rua A"}, "geometry": [{"lon": 0, "lat": 0}, {"lon": 0.1, "lat": 0.1}]}]}
        g = bc.osm([-43.2, -22.5, -43.1, -22.4], pegar=lambda u, d=None: json.dumps(resp).encode())
        self.assertEqual([f["geometry"]["type"] for f in g["features"]], ["Polygon", "LineString"])
        self.assertIn("ODbL", g["_fonte"]["licenca"])
        with self.assertRaises(ValueError):
            bc.osm([-44, -23, -43, -22], pegar=lambda u, d=None: b"{}")


class Gemeo(unittest.TestCase):
    def test_modulo_no_planejador(self):
        t = (RAIZ / "modulos" / "planejador" / "planejador-physis.html").read_text(encoding="utf-8")
        self.assertIn("id: 'gemeo', nome: 'Gêmeo digital'", t)
        self.assertIn("S && S.gemeo", t)
