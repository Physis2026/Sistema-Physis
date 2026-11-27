"""Camadas EXTRAS (27/11/2026): fontes-camadas.txt extra:..., bot --extras, catálogo, camada e contexto do Mapeamento;
uso do solo GLAD/OpenGeoHub como PROVISÓRIO (nunca com a legenda do MapBiomas)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from physis_hub import camadas_bot as cb
from physis_hub import mapeamento as mp

CID = [{"nome": "Teste", "lat": -22.5, "lon": -43.2, "raio_km": 5}]
QUADRADO = {"type": "Polygon", "coordinates": [[[-43.3, -22.6], [-43.1, -22.6], [-43.1, -22.4], [-43.3, -22.4], [-43.3, -22.6]]]}


def asc(caminho: Path, valor=5):
    linhas = ["ncols 4", "nrows 4", "xllcorner -43.3", "yllcorner -22.6", "cellsize 0.05", "NODATA_value -9999"]
    linhas += [" ".join([str(valor)] * 4) for _ in range(4)]
    caminho.write_text("\n".join(linhas) + "\n", encoding="ascii")


class FakeGdal:
    """Faz o papel do ogr2ogr/gdalwarp/gdal_translate/gdalinfo: escreve o arquivo de saída esperado."""
    def __init__(self):
        self.chamadas = []

    def __call__(self, args, **k):
        self.chamadas.append(args)
        r = mock.Mock(returncode=0, stderr="", stdout="")
        prog = Path(args[0]).name
        if prog == "ogr2ogr":
            saida = next(a for a in args if a.endswith(".geojson"))
            Path(saida).write_text(json.dumps({"type": "FeatureCollection", "features": [
                {"type": "Feature", "properties": {"nome": "APP do rio"}, "geometry": QUADRADO}]}), encoding="utf-8")
        elif prog == "gdalwarp":
            Path(args[-1]).write_bytes(b"tif")
        elif prog == "gdal_translate":
            asc(Path(args[-1]), 55)
        elif prog == "gdalinfo":
            r.stdout = json.dumps({"bands": [{"type": "Int16", "noDataValue": -32768, "scale": 0.1}]})
        return r


class TestExtras(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name)
        mp._CACHE.clear()
        self.patches = [mock.patch.object(cb, "achar_gdal", lambda n: n), mock.patch.object(cb, "gdal", lambda a: a)]
        for x in self.patches:
            x.start()

    def tearDown(self):
        for x in self.patches:
            x.stop()
        self.tmp.cleanup()

    def fontes(self, linhas):
        (self.p / "fontes-camadas.txt").write_text("\n".join(linhas) + "\n", encoding="utf-8")

    def test_ler_extras_valida_id(self):
        self.fontes(["uso_solo;C:/x.tif", "extra:x_car_app;C:/APPS/APPS_1.shp;APP (CAR);ambiental",
                     "extra:../../etc;C:/a.shp", "extra:X_MAIUSCULA;C:/a.shp", "extra:x_so_arquivo;C:/b.shp"])
        ex = cb.ler_extras(self.p)
        self.assertEqual([e["id"] for e in ex], ["x_car_app", "x_so_arquivo"])
        self.assertEqual(ex[0]["grupo"], "ambiental")
        self.assertEqual(ex[1]["nome"], "so arquivo")

    def test_rodar_extras_vetor_e_raster_com_fonte(self):
        tif = self.p / "opengeohub_ph_solo_rj.tif"; tif.write_bytes(b"x")
        (self.p / "opengeohub_ph_solo_rj.json").write_text(json.dumps({"fonte": "https://ceph.opengeohub.org/arco/soildb/ph.tif", "licenca": "CC-BY-4.0"}), encoding="utf-8")
        self.fontes(["extra:x_car_app;C:/APPS/APPS_1.shp;APP (CAR);ambiental", "extra:x_ogh_ph_solo;" + str(tif) + ";pH do solo;opengeohub"])
        g = FakeGdal()
        r = cb.rodar_extras(self.p, CID, rodar=g)
        self.assertEqual(r["x_car_app"]["situacao"], "instalada")
        self.assertEqual(r["x_ogh_ph_solo"]["situacao"], "instalada")
        ind = json.loads((self.p / "extras" / "indice.json").read_text(encoding="utf-8"))
        ph = next(x for x in ind if x["id"] == "x_ogh_ph_solo")
        self.assertEqual(ph["formato"], "raster")
        self.assertEqual(ph["fonte"]["licenca"], "CC-BY-4.0")
        self.assertEqual(ph["banda"]["scale"], 0.1)
        self.assertTrue(ph["chave_config"].startswith("fontes-camadas.txt"))
        # segunda rodada: já instalada, nada é refeito
        n = len(g.chamadas)
        r2 = cb.rodar_extras(self.p, CID, rodar=g)
        self.assertEqual(r2["x_car_app"]["situacao"], "ok")
        self.assertEqual(len(g.chamadas), n)

    def test_falha_vira_falta_sem_quebrar(self):
        self.fontes(["extra:x_ruim;C:/nao/existe.shp;Ruim;teste"])
        r = cb.rodar_extras(self.p, CID, rodar=lambda a, **k: mock.Mock(returncode=1, stderr="erro do GDAL"))
        self.assertEqual(r["x_ruim"]["situacao"], "falta")
        self.assertIn("conversão falhou", r["x_ruim"]["motivo"])

    def test_mapeamento_catalogo_camada_contexto(self):
        self.fontes(["extra:x_car_app;C:/APPS/APPS_1.shp;APP (CAR);ambiental", "extra:x_ogh_argila;C:/a.tif;Argila;opengeohub"])
        cb.rodar_extras(self.p, CID, rodar=FakeGdal())
        cat = mp.catalogo(self.p)
        ext = [c for c in cat if c.get("extra")]
        self.assertEqual({c["id"] for c in ext}, {"x_car_app", "x_ogh_argila"})
        self.assertTrue(all(c["status"] == "instalada" for c in ext))
        self.assertTrue(all(c["chave_config"] and c["fonte"]["licenca"] for c in ext))
        v = mp.camada("x_car_app", "-43.25,-22.55,-43.15,-22.45", self.p)
        self.assertTrue(v["ok"]); self.assertEqual(v["tipo"], "vetor"); self.assertEqual(len(v["geojson"]["features"]), 1)
        self.assertFalse(mp.camada("x_inexistente", "-43.25,-22.55,-43.15,-22.45", self.p)["ok"])
        doc = mp.construir_contexto({"lat": -22.5, "lon": -43.2, "fonte": "teste"}, None, self.p)
        ex = {x["id"]: x for x in doc["extras"]}
        self.assertEqual(ex["x_car_app"]["valor"]["no_lote"], 1)
        self.assertEqual(ex["x_ogh_argila"]["situacao"], "ok")
        self.assertIn("escala", ex["x_ogh_argila"]["nota"])          # gdalinfo disse scale 0.1: a tela avisa, não converte sozinha

    def test_indice_adulterado_e_ignorado(self):
        d = self.p / "extras"; d.mkdir()
        (d / "indice.json").write_text(json.dumps([{"id": "x_mau", "formato": "vetor", "arquivo": "../../segredo.geojson"},
                                                   {"id": "nao_extra", "formato": "vetor", "arquivo": "extras/a.geojson"},
                                                   {"id": "x_bom", "formato": "vetor", "arquivo": "extras/x_bom.geojson"}]), encoding="utf-8")
        self.assertEqual([x["id"] for x in mp.extras(self.p)], ["x_bom"])
        (d / "indice.json").write_text("{quebrado", encoding="utf-8"); mp._CACHE.clear()
        self.assertEqual(mp.extras(self.p), [])

    def test_uso_solo_glad_e_provisorio_sem_legenda_mapbiomas(self):
        asc(self.p / "uso_solo.asc", 3)
        (self.p / "uso_solo.legenda.json").write_text(json.dumps({"3": "Formação Florestal"}), encoding="utf-8")
        cb._fonte(self.p / "uso_solo.asc", url="C:/physis/dados-brutos/opengeohub_uso_solo_glad_rj.tif", provisoria=True,
                  produto="GLAD GLCLUC (UMD) via OpenGeoHub/OpenLandMap", legenda="GLAD: códigos próprios")
        r = mp.camada("uso_solo", "-43.25,-22.55,-43.15,-22.45", self.p)
        self.assertTrue(r["ok"]); self.assertIn("GLAD", r["provisoria"])
        self.assertFalse(any(c.get("nome") for c in r["classes"]))     # legenda do MapBiomas NÃO aplicada
        doc = mp.construir_contexto({"lat": -22.5, "lon": -43.2, "fonte": "teste"}, None, self.p)
        self.assertIn("PROVISÓRIA", doc["campos"]["uso_solo"]["nota"])

    def test_bot_marca_glad_como_provisoria_e_nao_rebaixa(self):
        tif = self.p / "opengeohub_uso_solo_glad_rj.tif"; tif.write_bytes(b"x")
        self.fontes(["uso_solo;" + str(tif)])
        g = FakeGdal()
        r = cb.rodar_bot(self.p, CID, ["uso_solo"], rodar=g, brutos=self.p / "brutos")
        self.assertIn("provisória", r["camadas"]["uso_solo"]["situacao"])
        meta = json.loads((self.p / "uso_solo.asc.fonte.json").read_text(encoding="utf-8"))
        self.assertTrue(meta["provisoria"]); self.assertFalse(meta["oficial"])
        n = len(g.chamadas)
        r2 = cb.rodar_bot(self.p, CID, ["uso_solo"], rodar=g, brutos=self.p / "brutos")
        self.assertEqual(r2["camadas"]["uso_solo"]["situacao"], "ok")             # mesma fonte: não refaz toda noite
        self.assertEqual(len(g.chamadas), n)



class TestRiscoSGB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.p = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_paginas_e_janela(self):
        pedidos = []
        def pegar(url):
            pedidos.append(url)
            off = int(url.split("resultOffset=")[1].split("&")[0])
            n = 2 if off < 4 else 1
            return json.dumps({"type": "FeatureCollection", "features": [
                {"type": "Feature", "properties": {"grau_risco": "R4", "municipio": "Petrópolis"}, "geometry": QUADRADO}] * n}).encode()
        arq = cb.oficial_arcgis("risco", cb.SGB_RISCO, self.p, cb.janelas(CID), pegar, lote=2)
        gj = json.loads(Path(arq).read_text(encoding="utf-8"))
        self.assertEqual(len(gj["features"]), 5)                          # 2 + 2 + 1: parou na página incompleta
        self.assertIn("geometryType=esriGeometryEnvelope", pedidos[0]); self.assertIn("outSR=4326", pedidos[0])
        meta = json.loads(Path(arq + ".fonte.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["feicoes"], 5); self.assertTrue(meta["oficial"])

    def test_erro_do_servico_e_vazio(self):
        with self.assertRaises(ValueError):
            cb.oficial_arcgis("risco", cb.SGB_RISCO, self.p, cb.janelas(CID), lambda u: b'{"error": {"code": 500}}')
        with self.assertRaises(ValueError):
            cb.oficial_arcgis("risco", cb.SGB_RISCO, self.p, cb.janelas(CID), lambda u: b"<html>fora do ar</html>")
        arq = cb.oficial_arcgis("risco", cb.SGB_RISCO, self.p, cb.janelas(CID), lambda u: b'{"type": "FeatureCollection", "features": []}')
        self.assertIn("nenhum setor", json.loads(Path(arq + ".fonte.json").read_text(encoding="utf-8"))["nota"])

    def test_risco_entra_sozinho_pelo_bot(self):
        def pegar(url):
            return json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": QUADRADO}]}).encode()
        r = cb.rodar_bot(self.p, CID, ["risco"], pegar=pegar)
        self.assertEqual(r["camadas"]["risco"]["situacao"], "baixada (oficial)")
        self.assertTrue(cb.eh_arcgis(cb.SGB_RISCO)); self.assertFalse(cb.eh_arcgis("https://x.org/a.zip"))


if __name__ == "__main__":
    unittest.main()
