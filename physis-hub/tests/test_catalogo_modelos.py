"""Catálogo técnico de modelos (catalogo_modelos.py). Dados de TESTE (fabricante fictício), não são modelos reais."""
import json, unittest
from physis_hub import catalogo_modelos as cm

CAB = ";".join(cm.COLUNAS)
def L(**k):
    return ";".join(str(k.get(c, "")) for c in cm.COLUNAS)
F = dict(fonte="catalogo-teste.pdf", fonte_ref="p. 3", data_fonte="2025-06", fabricante="Fab Teste", linha="L1")
CSV = "\n".join([CAB,
    L(tipo="condensadora_multi", modelo="C18", cap_resf_btuh="18.000", saidas_max=2, comb_min_pct=50, comb_max_pct=130, corrente_max_a="10,5", disjuntor_max_a=16, tensao_v=220, fases=1, **F),
    L(tipo="condensadora_multi", modelo="C27", cap_resf_btuh="27.000", saidas_max=3, comb_min_pct=50, comb_max_pct=130, corrente_max_a=20, disjuntor_max_a=16, tensao_v=220, fases=1, **F),
    L(tipo="evaporadora_multi", modelo="E9", cap_resf_btuh=9000, **F),
    L(tipo="evaporadora_multi", modelo="E12", cap_resf_btuh=12000, **F),
    L(tipo="split", modelo="S1", fabricante="Fab Teste", cap_resf_kw="3,5", fonte="", data_fonte="2025"),
])
EQ, DIR = {"usuario": "eq", "papel": "operador"}, {"usuario": "dir", "papel": "administrador"}

class Catalogo(unittest.TestCase):
    def setUp(self):
        self.c = cm.Catalogo(":memory:")
        self.r = self.c.importar_csv(CSV, "eq", "t.csv")

    def test_importa_recusa_sem_fonte(self):
        self.assertEqual(self.r["gravadas"], 4)
        self.assertIn("sem fonte", self.r["recusadas"][0]["erro"])
        self.assertTrue(all(m["estado"] == "a_conferir" for m in self.c.modelos()))
        self.assertEqual(self.c.importar_csv(CSV, "eq")["iguais"], 4)

    def test_selecao_so_conferido(self):
        amb = [{"nome": "Sala", "btuh": 9000}, {"nome": "Quarto", "btuh": 8000}]
        self.assertFalse(self.c.multisplit(amb)["ok"])
        self.c.conferir("dir", "conferido", importacao=self.r["importacao"])
        s = self.c.multisplit(amb)
        self.assertTrue(s["ok"], s)
        o = s["opcoes"][0]
        self.assertEqual(o["modelo"], "C18")  # 17.000 BTU/h cabe na de 18.000
        self.assertEqual([e["modelo"] for e in o["evaporadoras"]], ["E9", "E9"])
        self.assertEqual(o["combinacao_pct"], 100.0)
        tres = amb + [{"nome": "Suíte", "btuh": 9000}]
        s3 = self.c.multisplit(tres)
        self.assertEqual(s3["opcoes"][0]["modelo"], "C27")
        self.assertTrue(any("saídas" in d["motivo"] for d in s3["descartadas"]))

    def test_auditoria_mca_mop_e_exportacao(self):
        self.c.conferir("dir", "conferido", importacao=self.r["importacao"])
        a = self.c.auditoria()
        self.assertTrue(any("MOP" in x for p in a["problemas"] for x in p["problemas"]))
        nome, _, dados = self.c.exportar("json")
        d = json.loads(dados)
        self.assertNotIn("C27", [i["modelo"] for i in d["itens"]])
        self.assertTrue(self.c.verificar_historico()[0])

    def test_rotas_papeis(self):
        cli = {"usuario": "c", "papel": "cliente"}
        self.assertEqual(self.c.rota("GET", "/api/catalogo/modelos", cli, None, {})[1]["modelos"], [])
        self.assertEqual(self.c.rota("POST", "/api/catalogo/conferir", EQ, b'{"estado":"conferido","importacao":1}')[0], 403)
        self.assertEqual(self.c.rota("POST", "/api/catalogo/conferir", DIR, b'{"estado":"conferido","importacao":1}')[0], 200)
        self.assertEqual(len(self.c.rota("GET", "/api/catalogo/modelos", cli, None, {})[1]["modelos"]), 4)
        cod, r = self.c.rota("POST", "/api/avac/multisplit", cli, json.dumps({"ambientes": [{"nome": "a", "btuh": 8000}, {"nome": "b", "btuh": 8000}]}).encode())
        self.assertEqual(cod, 200, r)

if __name__ == "__main__":
    unittest.main()
