"""CAR pelo WFS do SICAR (25/11/2026): o bot pede só a janela ao ogr2ogr, sem baixar arquivo."""
import tempfile, unittest
from pathlib import Path
from unittest import mock
from physis_hub import camadas_bot as cb

URL = "https://geoserver.car.gov.br/geoserver/sicar/wfs"


class Wfs(unittest.TestCase):
    def test_reconhece(self):
        self.assertTrue(cb.eh_wfs(URL)); self.assertTrue(cb.eh_wfs(URL + "?service=WFS")); self.assertTrue(cb.eh_wfs("WFS:" + URL))
        self.assertFalse(cb.eh_wfs("https://x/solos.zip"))

    def test_fontes_e_comando(self):
        d = Path(tempfile.mkdtemp())
        (d / "fontes-camadas.txt").write_text("car;" + URL + "#sicar:imoveis\n", encoding="utf-8")
        self.assertEqual(cb.ler_fontes(d)["car"], URL + "#sicar:imoveis")
        visto = {}
        def rodar(args, **k):
            visto["a"] = args; Path(args[args.index("RFC7946=YES") + 3]).write_text('{"type":"FeatureCollection","features":[]}')
            return mock.Mock(returncode=0, stderr="")
        js = [{"lon": -43.2, "lat": -22.9}]
        with mock.patch.object(cb, "achar_gdal", lambda p: "ogr2ogr"), mock.patch.object(cb, "uniao", lambda j: (-44, -23, -43, -22)), \
             mock.patch.object(cb, "baixar_para", side_effect=AssertionError("não baixa")):
            out = cb.oficial("car", URL + "#sicar:imoveis", d, d / "brutos", js, rodar=rodar)
        self.assertTrue(Path(out).is_file())
        self.assertIn("WFS:" + URL, visto["a"]); self.assertEqual(visto["a"][-1], "sicar:imoveis"); self.assertIn("-spat", visto["a"])


if __name__ == "__main__":
    unittest.main()
