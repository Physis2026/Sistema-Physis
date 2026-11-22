"""Casa Physis · propostas net zero (VERSÃO DE TESTE, 22/11/2026; physis-hub/docs/casa-physis/).

Protege os pedidos da dona: todos os itens da lista inicial rearranjados (92 peças da semente rev0, nenhuma sem área),
7 lofts, norte sempre indicado na planta (norte de projeto e verdadeiro), números sem fonte marcados.
"""
import unittest
from pathlib import Path

PASTA = Path(__file__).resolve().parents[1] / "docs" / "casa-physis"
NO_REPO = (PASTA / "versao_A_netzero.csv").is_file()


def linhas():
    t = [l for l in (PASTA / "versao_A_netzero.csv").read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]
    cols = t[0].split(";")
    return [dict(zip(cols, l.split(";"))) for l in t[1:]]


@unittest.skipUnless(NO_REPO, "só no repositório")
class CasaNetZero(unittest.TestCase):
    def test_lista_inicial_completa(self):
        r = linhas()
        self.assertEqual(len(r), 92)
        self.assertEqual({z: sum(1 for x in r if x["zona"] == z) for z in ("Zona 1", "Zona 2", "Zona 3")},
                         {"Zona 1": 18, "Zona 2": 40, "Zona 3": 34})
        f = lambda v: float(v.replace(",", ".")) if v else 0.0
        for k in ("LF6", "LF7", "loja", "var6", "var7"):            # os três itens sem lugar na rev0 ganharam lugar
            e = next(x for x in r if x["chave"] == k)
            self.assertGreater(f(e["area_m2"]), 0, k)
        self.assertEqual(sum(1 for x in r if x["chave"].startswith("LF") and f(x["area_m2"]) > 0), 7)

    def test_norte_na_planta(self):
        s = (PASTA / "planta_A_netzero.svg").read_text(encoding="utf-8")
        self.assertIn(">NP<", s)
        self.assertIn(">NV<", s)
        self.assertIn("[CONFERIR] com o topógrafo", s)

    def test_documento_marca_o_que_falta(self):
        d = (PASTA / "PROPOSTAS_NETZERO.md").read_text(encoding="utf-8")
        for t in ("[MARCADOR]", "[CONFERIR]", "norte verdadeiro", "92 de 92", "100,02 %"):
            self.assertIn(t, d)


if __name__ == "__main__":
    unittest.main()
