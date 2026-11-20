"""Clientes, projetos e parceiros do Physis M&A (20/11/2026): semente das contas pedidas pela dona, resumo a conferir, propostas do
bot que só valem confirmadas, inclusão de projeto futuro, finanças em níveis e pedido de nota ao contador só como rascunho."""
import unittest

from physis_hub import mv_arquivos, mv_clientes, mv_comandos
from physis_hub.mv import MV, ErroMV


class TestClientes(unittest.TestCase):
    def setUp(self):
        self.mv = MV(":memory:")
        mv_arquivos.Arquivos(self.mv)
        self.c = mv_clientes.Clientes(self.mv)
        self.c.semear()

    def test_contas_pedidas(self):
        ids = {x["id"] for x in self.c.contas()}
        self.assertTrue({"giz-ptx", "estermic", "gsa", "rede-tacas-turbinas", "fazenda-mf", "fazenda-santa-clara"} <= ids)
        self.assertEqual(self.c.semear(), {"cnpjs": 0, "contas": 0, "subprojetos": 0})       # idempotente
        e = self.c.conta("estermic")
        self.assertEqual(len(e["subprojetos"]), 4)
        self.assertEqual(e["template"], "cliente")
        self.assertEqual(self.c.conta("gsa")["template"], "parceria")
        pe = next(x for x in self.c.cnpjs() if x["id"] == "physis-eng")
        self.assertEqual((pe["cnpj"], pe["regime"]), ("44.982.448/0001-23", "Simples Nacional"))

    def test_proposta_so_vale_confirmada(self):
        self.c.propor("estermic", {"contato": "x@[MARCADOR]", "campo_inexistente": "y"})
        self.assertEqual(self.c.conta("estermic")["contato"], "[MARCADOR]")
        self.assertEqual(list(self.c.conta("estermic")["propostas"]), ["contato"])
        self.assertEqual(self.c.confirmar("estermic", "contato")["contato"], "x@[MARCADOR]")
        self.c.propor("estermic", {"moeda": "USD"})
        self.assertEqual(self.c.confirmar("estermic", "moeda", aceitar=False)["moeda"], "BRL")
        with self.assertRaises(ErroMV):
            self.c.confirmar("estermic", "moeda")

    def test_inclusao_de_projeto_futuro(self):
        r = self.c.salvar({"nome": "Projeto Futuro X", "tipo": "futuro"})
        self.assertEqual((r["id"], r["estado"], r["template"]), ("projeto-futuro-x", "futuro", "physis"))
        with self.assertRaises(ErroMV):
            self.c.salvar({"nome": "Y", "tipo": "qualquer"})
        with self.assertRaises(ErroMV):
            self.c.salvar({"nome": "Z", "cnpj_emissor": "nao-existe"})

    def test_financeiro_em_niveis_e_nota_rascunho(self):
        a = self.c.lancar({"entidade": "engineering", "data": "2026-11-20", "tipo": "receita", "valor": 1000, "descricao": "Fase 0",
                           "conta": "estermic", "subprojeto": "estermic-sp1", "sistema": "AVAC", "membro": "Ryan", "cnpj_emissor": "physis-eng"})
        self.c.lancar({"entidade": "engineering", "data": "2026-11-20", "tipo": "despesa", "valor": 200, "descricao": "Material",
                       "conta": "estermic", "membro": "Ryan"})
        self.assertEqual(self.c.financeiro("conta")[0]["a_conferir"], {"despesa": 200.0, "receita": 1000.0})
        self.assertEqual({x["chave"] for x in self.c.financeiro("membro")}, {"Ryan"})
        self.assertEqual(self.c.financeiro("sistema", "AVAC")[0]["a_conferir"], {"receita": 1000.0})
        with self.assertRaises(ErroMV):
            self.c.financeiro("cor")
        with self.assertRaises(ErroMV):
            self.c.lancar({"entidade": "engineering", "data": "2026-11-20", "tipo": "receita", "valor": 1, "conta": "nao-existe"})
        p = self.c.pedir_nota(a)
        self.assertEqual((p["tipo"], p["estado"]), ("email_contador", "rascunho"))
        self.assertIn("44.982.448/0001-23", p["resultado"])
        self.assertIn("Nada foi enviado", p["resultado"])
        self.assertTrue(self.c.lancamentos("estermic")[-1]["nf"].startswith("rascunho:") or self.c.lancamentos("estermic")[0]["nf"])

    def test_analisar_vai_para_fila(self):
        r = self.c.analisar("estermic")
        self.assertEqual((r["tipo"], r["estado"], r["origem"]), ("claude", "na_fila", "conta:estermic"))
        self.assertIn("[MARCADOR]", r["comando"])


if __name__ == "__main__":
    unittest.main()
