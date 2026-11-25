"""Bot de modelos → catálogo técnico automático (25/11/2026). Texto de TESTE, fabricante fictício."""
import unittest
from pathlib import Path
import tempfile
from physis_hub import mv_modelos as mm, catalogo_modelos as cm

TXT = """Catálogo Multi-Split FabTeste  Rev. 03/2025
Condensadora MX18A 18.000 BTU/h 2x1 combinação 50 a 130 % 220 V monofásico MCA 12,5 A MOP 20 A
Evaporadora hi-wall EV09A 9.000 BTU/h
Evaporadora hi-wall EV12A 12.000 BTU/h
\fpágina sem nada útil 18000 BTU/h
"""
FABS = {"FabTeste": "Split e multi-split"}

class Bot(unittest.TestCase):
    def test_propoe_e_grava_sozinho(self):
        p = mm.propor_tecnicos(TXT, "fabteste.pdf", FABS)
        self.assertEqual([(x["tipo"], x["modelo"]) for x in p], [("condensadora_multi", "MX18A"), ("evaporadora_multi", "EV09A"), ("evaporadora_multi", "EV12A")])
        c = p[0]
        self.assertEqual((c["cap_resf_btuh"], c["saidas_max"], c["comb_min_pct"], c["comb_max_pct"], c["corrente_max_a"], c["disjuntor_max_a"], c["data_fonte"], c["fonte_ref"]),
                         ("18000", "2", "50", "130", "12,5", "20", "2025-03", "p. 1"))
        with tempfile.TemporaryDirectory() as d:
            cat = cm.Catalogo(":memory:")
            r = mm.catalogo_automatico(Path(d), FABS, {"fabteste.pdf": TXT}, cat)
            self.assertEqual(r["gravadas"], 3)
            self.assertEqual(r["por_estado"], {"conferido_bot": 3})
            s = cat.multisplit([{"nome": "Sala", "btuh": 11000}, {"nome": "Quarto", "btuh": 6000}])
            self.assertTrue(s["ok"], s); self.assertTrue(s["opcoes"][0]["conferido_por_bot"])

    def test_sem_data_nao_inventa(self):
        p = mm.propor_tecnicos(TXT.replace("Rev. 03/2025", ""), "fabteste.pdf", FABS)
        self.assertTrue(all(x["data_fonte"] == "" for x in p))
        r = cm.Catalogo(":memory:").importar_linhas(p, "bot", origem="bot")
        self.assertEqual(r["gravadas"], 0)

    def test_download_sem_internet(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "fontes.txt").write_text("FabTeste;https://exemplo.invalid/cat.pdf\n", encoding="utf-8")
            def falha(u): raise OSError("sem rede")
            r = mm.baixar_fontes(Path(d), falha)
            self.assertEqual((r["fontes"], r["baixados"], len(r["falhas"])), (1, 0, 1))
            r = mm.baixar_fontes(Path(d), lambda u: b"%PDF-1.4 teste")
            self.assertEqual(r["baixados"], 1)

if __name__ == "__main__":
    unittest.main()
