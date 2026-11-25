"""ferramentas_simulacao no Windows: programas em Arquivos de Programas fora do PATH (PC-PHYSIS, 24/11/2026)."""
import unittest

from physis_hub import ferramentas_simulacao as fs


class Windows(unittest.TestCase):
    def test_acha_fora_do_path(self):
        achados = {"C:/Program Files/FreeCAD 1.0/bin/FreeCAD.exe", "C:/Program Files/KiCad/9.0/bin/kicad.exe"}
        achar = lambda p: [x for x in achados if __import__("fnmatch").fnmatch(x, p)]
        s = {x["id"]: x["instalado"] for x in fs.situacao(which=lambda _: None, windows=True, achar=achar)}
        self.assertTrue(s["freecad"])
        self.assertTrue(s["kicad"])
        self.assertFalse(s["avogadro"])

    def test_linux_nao_procura_pastas_do_windows(self):
        s = {x["id"]: x["instalado"] for x in fs.situacao(which=lambda _: None, windows=False, achar=lambda p: ["x"])}
        self.assertFalse(s["freecad"])


if __name__ == "__main__":
    unittest.main()
