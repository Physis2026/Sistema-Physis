"""Ações do sistema pedidas em texto livre (27/11/2026) e o sistema sem Claude."""
import tempfile
import unittest
from pathlib import Path

from physis_hub import mv as mvmod
from physis_hub import mv_autonomo as au
from physis_hub import mv_comandos


class TestAcoes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mv = mvmod.MV(str(Path(self.tmp.name) / "mv.db"))
        self.cmd = mv_comandos.Comandos(self.mv)

    def tearDown(self):
        self.mv.db.close(); self.tmp.cleanup()

    def test_interpretar(self):
        a = au.interpretar_acao("Crie uma tarefa: revisar o contrato da Estermic para Marzia até 05/12/2026")
        self.assertEqual((a["acao"], a["titulo"], a["responsavel"], a["fim"]), ("criar_tarefa", "revisar o contrato da Estermic", "Marzia", "2026-12-05"))
        self.assertEqual(au.interpretar_acao("inclua tarefa no InovaSTEM: montar a trilha de impressão 3D")["frente"], "inovastem")
        self.assertEqual(au.interpretar_acao("rode o resumo todo dia"), {"acao": "programar", "comando": "/rodar resumo", "frequencia": "dia"})
        self.assertEqual(au.interpretar_acao("conclua a tarefa #t12")["id"], "t12")
        self.assertEqual(au.interpretar_acao("altere a cor do botão da loja")["acao"], "nao_reconhecida")
        self.assertIsNone(au.interpretar_acao("como criar uma tarefa?"))          # pergunta vai para a IA
        self.assertIsNone(au.interpretar_acao("quais tarefas estão atrasadas"))
        self.assertIn("data inválida", au.descrever_acao(au.interpretar_acao("crie a tarefa pagar a guia até 31/02/2026")))

    def test_so_executa_depois_de_aprovar(self):
        p = au.responder(self.cmd, "Crie uma tarefa: conferir o backup externo para Rafaella até 10/12/2026")
        self.assertEqual((p["tipo"], p["estado"]), ("acao", "rascunho"))
        self.assertIsNone(self.mv.tarefa(f"acao-{p['id']}"))                    # nada criado antes da aprovação
        r = self.cmd.decidir_pedido(p["id"], "aprovado")
        t = self.mv.tarefa(f"acao-{p['id']}")
        self.assertEqual((t["titulo"], t["responsavel"], t["fim"]), ("conferir o backup externo", "Rafaella", "2026-12-10"))
        self.assertIn("Tarefa criada", r["resultado"])
        self.cmd.decidir_pedido(p["id"], "aprovado")                              # aprovar de novo não duplica
        self.assertEqual(self.mv.db.execute("SELECT COUNT(*) FROM mv_tarefa WHERE id LIKE 'acao-%'").fetchone()[0], 1)

    def test_descartada_nao_executa_e_nao_reconhecida_vira_melhoria(self):
        p = au.responder(self.cmd, "crie uma tarefa: algo que não quero")
        self.cmd.decidir_pedido(p["id"], "descartado")
        self.assertIsNone(self.mv.tarefa(f"acao-{p['id']}"))
        q = au.responder(self.cmd, "apague todos os clientes antigos")
        self.assertEqual(q["tipo"], "acao_nao_reconhecida")
        self.assertIn("Nada foi mudado", q["resultado"])

    def test_concluir_tarefa(self):
        self.mv.salvar_tarefa({"id": "t1", "frente": "transversal", "titulo": "Teste"})
        p = au.responder(self.cmd, "conclua a tarefa #t1")
        self.cmd.decidir_pedido(p["id"], "aprovado")
        self.assertEqual(self.mv.tarefa("t1")["estado"], "feita")

    def test_atrasadas_le_o_banco(self):
        self.mv.salvar_tarefa({"id": "t9", "frente": "transversal", "titulo": "Atrasada", "fim": "2020-01-01"})
        self.mv.salvar_tarefa({"id": "t8", "frente": "transversal", "titulo": "Pronta", "fim": "2020-01-01", "estado": "feita"})
        txt = au._resumo_tarefas(self.mv, True)
        self.assertIn("#t9", txt); self.assertNotIn("#t8", txt); self.assertNotIn("Não consegui", txt)


if __name__ == "__main__":
    unittest.main()
