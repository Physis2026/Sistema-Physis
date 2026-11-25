"""Programas do PC pela plataforma (programas_externos.py): receitas fechadas, parâmetros conferidos, zip seguro, trabalho isolado."""
import io, json, os, stat, sys, tempfile, time, unittest, zipfile
from pathlib import Path
from physis_hub import programas_externos as pe

FAKE = """#!%s
import os, sys, json
sai = os.environ.get("PHYSIS_SAIDA", ".")
open(os.path.join(sai, "resumo.json"), "w").write(json.dumps({"argv": sys.argv[1:]}))
print("rodou")
""" % sys.executable

class Programas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.d = Path(self.tmp.name)
        f = self.d / "fake.py"; f.write_text(FAKE); f.chmod(f.stat().st_mode | stat.S_IEXEC)
        self.pg = pe.Programas(self.d / "trab", localizar_=lambda prog: str(f) if prog not in ("python",) else sys.executable)

    def tearDown(self):
        self.tmp.cleanup()

    def test_receitas_e_disponibilidade(self):
        ids = {r["id"] for r in pe.disponiveis()}
        for k in ("freecad.solido", "qgis.vetor", "qgis.raster", "blender.glb", "kicad.gerber", "prusaslicer.fatiar", "librecad.pdf",
                  "calculix.rodar", "gmsh.malha", "tesseract.ocr", "rdkit.descritores", "energyplus.idf", "openstudio.osw", "elmer.sif",
                  "lammps.in", "copasi.cps", "psi4.energia", "opensim.ferramenta", "servicos.saude"):
            self.assertIn(k, ids)

    def test_roda_e_guarda(self):
        r = self.pg.iniciar("kicad.gerber", b"(kicad_pcb)", "placa.kicad_pcb", {}, "eq", esperar=True)
        self.assertTrue(r["ok"], r)
        e = self.pg.estado(r["id"])
        self.assertEqual(e["estado"], "ok", e); self.assertEqual(e["resumo"]["argv"][:3], ["pcb", "export", "gerbers"])
        self.assertIsNotNone(self.pg.arquivo(r["id"], "registro.txt"))
        self.assertIsNone(self.pg.arquivo(r["id"], "../trabalho.json"))

    def test_entrada_e_parametros_conferidos(self):
        self.assertFalse(self.pg.iniciar("kicad.gerber", b"x", "virus.exe", {}, "eq")["ok"])
        self.assertFalse(self.pg.iniciar("tesseract.ocr", b"x", "a.png", {"idioma": "rm -rf"}, "eq")["ok"])
        self.assertFalse(self.pg.iniciar("prusaslicer.fatiar", b"x", "a.stl", {"camada_mm": "9"}, "eq")["ok"])
        self.assertFalse(self.pg.iniciar("prusaslicer.fatiar", b"x", "a.stl", {"extra": "1"}, "eq")["ok"])
        self.assertEqual(self.pg.iniciar("nada", b"", "", {}, "eq").get("codigo"), 404)

    def test_zip_que_sai_da_pasta_e_recusado(self):
        b = io.BytesIO(); z = zipfile.ZipFile(b, "w"); z.writestr("../../fora.sif", "x"); z.close()
        self.assertFalse(self.pg.iniciar("elmer.sif", b.getvalue(), "caso.zip", {}, "eq")["ok"])
        b = io.BytesIO(); z = zipfile.ZipFile(b, "w"); z.writestr("caso/caso.sif", "Header"); z.close()
        r = self.pg.iniciar("elmer.sif", b.getvalue(), "caso.zip", {}, "eq", esperar=True)
        self.assertTrue(r["ok"], r); self.assertEqual(self.pg.estado(r["id"])["estado"], "ok")

    def test_servicos(self):
        r = self.pg.iniciar("servicos.saude", None, "", {}, "eq", esperar=True)
        self.assertIn("mosquitto", self.pg.estado(r["id"])["resumo"])

    def test_programa_ausente(self):
        pg = pe.Programas(self.d / "t2", localizar_=lambda p: None)
        r = pg.iniciar("freecad.solido", b"x", "a.step", {}, "eq", esperar=True)
        self.assertIn("não está instalado", pg.estado(r["id"])["erro"])

if __name__ == "__main__":
    unittest.main()
