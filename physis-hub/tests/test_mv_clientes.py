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

    def test_projeto_novo_entra_no_monitoramento_e_nos_editais(self):
        r = self.c.salvar({"nome": "Biogás Serra", "tipo": "futuro", "core": "biodigestor e hidrogênio verde em fazendas"})
        t = self.mv.tarefa("conta-biogas-serra-ficha")
        self.assertEqual((t["projeto"], t["estado"]), ("Biogás Serra", "a_fazer"))
        self.assertIn("conta-biogas-serra-ficha", [x["id"] for x in self.mv.gantt()])
        self.assertTrue(any(a["ref"] == "biogas-serra" for a in self.mv.alertas()))
        from physis_hub import mv_editais
        ed = mv_editais.Editais(self.mv)
        self.mv.db.execute("INSERT INTO mv_edital (id,titulo,temas,criado,atualizado) VALUES ('ed:x','Chamada hidrogenio verde','energia',0,0)")
        self.assertIn("biogas-serra", next(d for d in ed.listar() if d["id"] == "ed:x")["contas_relacionadas"])
        self.assertTrue(self.mv.tarefa("conta-estermic-sp1-ficha") is None and self.mv.tarefa("conta-estermic-sp1"))

    def test_projetos_anteriores_sugeridos_e_confirmados(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            (raiz / "Egypt").mkdir()
            (raiz / "Egypt" / "260324_GIZ ADVANCE_Report.docx").write_text("x")
            (raiz / "2_Proposta_Comercial_Physis_WWF_MecfinUC.docx").write_text("x")
            sg = {s["nome"]: s for s in self.c.sugerir_anteriores(raiz)}
            giz = sg["GIZ ADVANCE · Egito (eficiência de recursos)"]
            self.assertEqual((giz["cliente"], giz["pais"], giz["ano"]), ("GIZ", "Egito", "2026"))
            self.assertIn("WWF · MecfinUC (proposta técnica e comercial)", sg)
            r = self.c.criar_anterior({**giz, "escopo": "Eficiência de recursos em 4 indústrias"})
            self.assertEqual((r["tipo"], r["estado"]), ("anterior", "concluido"))
            self.assertIsNone(self.mv.tarefa(f"conta-{r['id']}-ficha"))            # concluído: sem tarefa nem alerta
            self.assertNotIn(giz["nome"], {s["nome"] for s in self.c.sugerir_anteriores(raiz)})

    def test_analisar_vai_para_fila(self):
        r = self.c.analisar("estermic")
        self.assertEqual((r["tipo"], r["estado"], r["origem"]), ("autonomo", "rascunho", "conta:estermic"))
        self.assertIn("[MARCADOR]", r["comando"])


class TestInovacao(unittest.TestCase):
    def test_pesquisa_diaria_sem_claude_e_aprovacao_vira_tarefa(self):
        from physis_hub import mv_inovacao
        mv = MV(":memory:")
        atom = (b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>r170 lan\xc3\xa7ado</title>'
                b'<link href="https://github.com/mrdoob/three.js/releases/tag/r170"/></entry></feed>')
        fontes = [("three.js", "x", "3D"), ("fora do ar", "y", "z")]

        def buscar(url):
            if url == "y":
                raise OSError("sem internet")
            return atom
        r = mv_inovacao.rodar(mv, buscar, fontes, agora=1000.0)
        self.assertEqual((r["novos"], r["erros"]), (1, ["fora do ar: OSError"]))
        self.assertEqual(mv_inovacao.rodar(mv, buscar, fontes, agora=2000.0)["novos"], 0)   # não repete o mesmo link
        c = mv_comandos.Comandos(mv)
        p = [x for x in c.fila() if x["tipo"] == "inovacao"][0]
        c.decidir_pedido(p["id"], "aprovado")
        t = mv.tarefa(f"inov-{p['id']}")
        self.assertIn("three.js", t["titulo"])
        self.assertEqual(t["frente"], "transversal")


if __name__ == "__main__":
    unittest.main()
