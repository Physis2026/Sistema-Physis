"""IA Physis generativa (24/11/2026): modelo aberto local, fluxo busca → diretrizes → skill → geração → trava → rascunho."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from physis_hub import ia_generativa as g
from physis_hub import mv_comandos
from physis_hub.ia_physis import IAPhysis
from physis_hub.mv import MV


def ia_com_doc():
    d = Path(tempfile.mkdtemp())
    (d / "missao.md").write_text("# Identidade\n\nMissão da Physis: projetar soluções de engenharia sustentável para o campo e a cidade.\n\n"
                                 "## Prazos\n\nO relatório do Projeto Alfa sai em 12 de dezembro, com 3 visitas de campo.\n", encoding="utf-8")
    ia = IAPhysis(d / "ia.db")
    ia.indexar({"docs": [d]})
    return ia


class Fluxo(unittest.TestCase):
    def setUp(self):
        self.ia = ia_com_doc()
        self.mv = MV(":memory:")
        mv_comandos.perguntar(self.mv, "Assinatura dos e-mails?")
        mv_comandos.responder(self.mv, mv_comandos.perguntas(self.mv)[0]["id"], "Equipe Physis")

    def test_prompt_tem_regras_decisoes_skill_e_fontes(self):
        vistos = {}
        def falso(msgs):
            vistos["m"] = msgs
            return "A missão é projetar soluções de engenharia sustentável [1]."
        r = g.gerar("qual é a missão da Physis", self.mv, ia=self.ia, chamar=falso)
        sis, usu = vistos["m"][0]["content"], vistos["m"][1]["content"]
        self.assertIn("Nunca invente", sis)
        self.assertIn("Só cores", sis)                      # regras do CLAUDE.md
        self.assertIn("Equipe Physis", sis)                 # decisão da dona
        self.assertIn("TAREFA (resposta)", sis)
        self.assertIn("[1] (", usu)
        self.assertEqual((r["modo"], r["avisos"]), ("generativa", []))
        self.assertTrue(r["fontes"])

    def test_trava_numero_inventado(self):
        r = g.gerar("quando sai o relatório do Projeto Alfa", self.mv, ia=self.ia,
                    chamar=lambda m: "Sai em 12 de dezembro, com 3 visitas e custo de R$ 48.000 [1].")
        self.assertIn("12 de dezembro", r["resposta"])
        self.assertIn("3 visitas", r["resposta"])
        self.assertNotIn("48.000", r["resposta"])
        self.assertIn("[MARCADOR]", r["resposta"])
        self.assertTrue(any("sem origem" in a for a in r["avisos"]))

    def test_sem_citacao_gera_aviso_e_citacao_falsa_sai(self):
        r = g.gerar("missão da Physis", self.mv, ia=self.ia, chamar=lambda m: "Engenharia sustentável [9].")
        self.assertNotIn("[9]", r["resposta"])
        self.assertTrue(any("sem citação" in a for a in r["avisos"]))

    def test_modelo_desligado_cai_no_extrativo(self):
        def erro(m):
            raise ConnectionRefusedError()
        r = g.gerar("qual é a missão da Physis", self.mv, ia=self.ia, chamar=erro)
        self.assertEqual(r["modo"], "extrativa")
        self.assertIn("projetar soluções", r["resposta"])
        self.assertTrue(r["avisos"])

    def test_modo_extrativo_forcado_nao_chama(self):
        with mock.patch.dict(os.environ, {"PHYSIS_IA_MODO": "extrativa"}):
            r = g.gerar("missão", self.mv, ia=self.ia, chamar=lambda m: self.fail("não devia chamar"))
        self.assertEqual(r["modo"], "extrativa")

    def test_skills(self):
        self.assertEqual(g.skill_para("Escreva um e-mail ao cliente"), "email")
        self.assertEqual(g.skill_para("post para o Instagram sobre o curso"), "post")
        self.assertEqual(g.skill_para("nota para o contador de novembro"), "contador")
        self.assertEqual(g.skill_para("checklist da instalação"), "checklist")
        self.assertEqual(g.skill_para("qual a missão"), "resposta")
        for s in g.SKILLS.values():
            self.assertTrue(len(s) > 40)

    def test_aprendizagem_entra(self):
        c = mv_comandos.Comandos(self.mv)
        p = c._pedido("autonomo", "post sobre o curso", "", "rascunho", "texto")
        c.decidir_pedido(p["id"], "ajustar", "tirar emojis")
        self.assertIn("tirar emojis", g.diretrizes(self.mv)["aprendizagens"])

    def test_caixa_de_comandos_usa_o_fluxo(self):
        c = mv_comandos.Comandos(self.mv)
        import threading
        from physis_hub import mv_autonomo
        # trava própria: no PC com Ollama, threads de testes anteriores podem segurar a trava global esperando o modelo real
        with mock.patch.object(g, "chamar_modelo", lambda m: "A missão é engenharia sustentável [1]."), \
             mock.patch.object(mv_autonomo, "_TRAVA", threading.Lock()):
            r = mv_autonomo.responder(c, "qual é a missão da Physis", ia=self.ia)
            self.assertEqual(r["estado"], "rascunho")
            self.assertIn("modo extrativa", r["resultado"])          # resposta na hora, sem esperar o modelo
            import threading
            import time
            for _ in range(600):                                       # até 60 s, com o modelo falso ainda no lugar
                final = c.pedido(r["id"])["resultado"]
                if "modo generativa" in final:
                    break
                time.sleep(0.1)
        self.assertIn("modo generativa", final)                      # o modelo substitui em segundo plano
        self.assertIn("Fontes:", final)


if __name__ == "__main__":
    unittest.main()
