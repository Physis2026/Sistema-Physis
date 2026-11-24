"""Gêmeo digital · conferente automático com aprendizado contínuo (pedido da dona, 22/11/2026).

Protege:
1. detectar() acha sozinho o que foi conferido à mão: divergências D1–D8, peças fora do nível do terreno sem
   explicação, elementos sem área, soma das partes × total; cada achado com opções fechadas (nunca número novo).
2. Exemplos iniciais = decisões reais já registradas no M&A (pg:…); o modelo aprende com elas e mede o acerto.
3. Ciclo: grava os achados uma vez, publica no M&A até o limite, lê as respostas, retreina (versão nova).
4. Uma correção da dona muda a próxima sugestão (aprendizado contínuo) e responde a pergunta do M&A.
5. Determinístico: mesmos exemplos, mesmo modelo.
"""
import os
import tempfile
import unittest
from pathlib import Path

from physis_hub import gemeo as G
from physis_hub import gemeo_conferente as K
from physis_hub.mv import MV

RAIZ = Path(__file__).resolve().parents[2]
SEMENTE = RAIZ / "modulos" / "planejador" / "gemeo" / "casa-physis-rev0.json"


class Conferente(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = G.carregar(SEMENTE)
        cls.ach = K.detectar(cls.p)

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.mv = MV(os.path.join(self.dir.name, "mv.db"))

    def tearDown(self):
        self.mv.db.close()
        self.dir.cleanup()

    def test_detecta_o_que_era_feito_a_mao(self):
        tipos = {a["tipo"] for a in self.ach}
        self.assertTrue({"divergencia", "terreno", "sem_area"} <= tipos)
        divs = {a["atributos"]["divergencia"] for a in self.ach if a["tipo"] == "divergencia"}
        self.assertEqual(divs, {"D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9"})   # D10 resolvida
        self.assertIn("esgoto.fossa_filtro_cabe", {a["chave"] for a in self.ach if a["tipo"] == "soma"})
        terreno = {a["chave"] for a in self.ach if a["tipo"] == "terreno"}
        self.assertIn("comum", terreno)                  # abaixo do terreno sem corte na 03
        self.assertNotIn("cist1", terreno)               # corte intencional: não pergunta
        for a in self.ach:
            self.assertEqual(a["opcoes"], [k for k, _ in K.OPCOES[a["tipo"]]])
            self.assertTrue(a["id"].startswith("ga:"))
        self.assertEqual(len({a["id"] for a in self.ach}), len(self.ach))
        self.assertEqual(self.ach, sorted(self.ach, key=lambda a: -a["prioridade"]))

    def test_exemplos_iniciais_sao_decisoes_do_mea(self):
        ex = K.exemplos_iniciais(self.p)
        self.assertEqual(len(ex), 10)
        for e in ex:
            self.assertRegex(e["nota"], r"pg:[0-9a-f]{12}")
        esc = {e["chave"]: e["escolha"] for e in ex}
        self.assertEqual(esc["telhados.inclinacao_graus"], "alternativa")   # 02b escolhida (pg:74fabc0568d2)
        self.assertEqual(esc["energia.consumo_kwh_mes"], "marcador")        # D5 vazio (pg:310a1c0db09d)
        m = K.treinar(ex, agora=0)
        self.assertEqual(m["modelos"]["divergencia"]["modo"], "logistica")
        self.assertIsNotNone(m["metricas"]["divergencia"]["acerto_loo"])
        self.assertEqual(K.treinar(ex, agora=0), m)                          # determinístico
        a = next(x for x in self.ach if x["chave"] == "lote.area_m2")
        sug, conf, expl = K.sugerir(m, a)
        self.assertEqual(sug, "atual")
        self.assertIn("aprendido com 10 decisões", expl)

    def test_sem_exemplos_vale_a_regra_inicial(self):
        a = next(x for x in self.ach if x["tipo"] == "terreno")
        self.assertEqual(K.sugerir(None, a), ("aguardar", 0.5, K.sugerir(None, a)[2]))
        self.assertIn("regra inicial", K.sugerir(None, a)[2])

    def test_ciclo_publica_no_mea_uma_vez(self):
        r = K.ciclo(self.mv, self.p, limite=3, agora=1000.0)
        self.assertEqual((r["exemplos_iniciais"], r["perguntas_novas"], r["modelo_versao"]), (10, 3, 1))
        perguntas = self.mv.db.execute("SELECT * FROM mv_pergunta WHERE origem='casa-gemeo-digital'").fetchall()
        self.assertEqual(len(perguntas), 3)
        self.assertIn("(sugestão do sistema,", perguntas[0]["opcoes"])
        r2 = K.ciclo(self.mv, self.p, limite=3, agora=2000.0)
        self.assertEqual((r2["exemplos_iniciais"], r2["modelo_versao"]), (0, 2))
        self.assertEqual(self.mv.db.execute("SELECT COUNT(*) FROM mv_pergunta").fetchone()[0], 6)  # 3 novas, sem repetir

    def test_resposta_e_correcao_ensinam_o_sistema(self):
        from physis_hub import mv_comandos as C
        K.ciclo(self.mv, self.p, limite=60, agora=1000.0)
        db = self.mv.db
        terr = [r for r in db.execute("SELECT * FROM gemeo_achado WHERE tipo='terreno' AND pergunta_id IS NOT NULL")]
        self.assertGreaterEqual(len(terr), 4)
        rot = dict(K.OPCOES["terreno"])
        # a dona responde no M&A: as peças abaixo do terreno sem corte são plataformas intencionais
        for r in terr[:4]:
            C.responder(self.mv, r["pergunta_id"], rot["intencional"], "plataforma cortada; a 03 não lançou o volume")
        r2 = K.ciclo(self.mv, self.p, limite=0, agora=2000.0)
        self.assertEqual(r2["respostas_novas"], 4)
        # e corrige uma (erro do sistema): o sistema passa a ter duas escolhas e um modelo
        K.corrigir(self.mv, terr[4]["id"], "erro_cota", "cota digitada errada na 03")
        r3 = K.ciclo(self.mv, self.p, limite=0, agora=3000.0)
        modelo, v = K.ultimo_modelo(db)
        self.assertEqual(v, 3)
        self.assertEqual(modelo["modelos"]["terreno"]["modo"], "logistica")
        self.assertIn("terreno: 5 decisões", r3["explicacao"])
        pend = db.execute("SELECT sugestao, confianca FROM gemeo_achado WHERE tipo='terreno' AND escolha IS NULL").fetchall()
        # aprendeu: as sugestões saem das escolhas da dona (intencional / erro_cota), não mais da regra inicial
        self.assertTrue(pend)
        self.assertTrue(all(p["sugestao"] in ("intencional", "erro_cota") for p in pend))
        self.assertTrue(all(p["confianca"] != 0.5 for p in pend))
        p = db.execute("SELECT resposta, nota FROM mv_pergunta WHERE id=?", (terr[4]["pergunta_id"],)).fetchone()
        self.assertEqual(p["resposta"], rot["erro_cota"])
        self.assertIn("correção", p["nota"])
        with self.assertRaises(ValueError):
            K.corrigir(self.mv, terr[4]["id"], "inventada")


    def test_politica_aplica_sozinho_so_com_10_decisoes_e_90_por_cento(self):
        """Decisão pg:068bf675d5b9: ≥ 10 decisões humanas e acerto ≥ 90% → aplica e registra; senão pergunta."""
        from physis_hub import mv_comandos as C
        K.ciclo(self.mv, self.p, limite=60, agora=1000.0)
        db = self.mv.db
        terr = [r for r in db.execute("SELECT * FROM gemeo_achado WHERE tipo='terreno' AND pergunta_id IS NOT NULL")]
        rot = dict(K.OPCOES["terreno"])
        for r in terr[:9]:
            C.responder(self.mv, r["pergunta_id"], rot["intencional"], "plataforma")
        r1 = K.ciclo(self.mv, self.p, limite=0, agora=2000.0)
        self.assertEqual(r1["aplicadas_sozinho"], 0)                          # 9 decisões: ainda pergunta
        C.responder(self.mv, terr[9]["pergunta_id"], rot["intencional"], "plataforma")
        r2 = K.ciclo(self.mv, self.p, limite=0, agora=3000.0)
        self.assertGreater(r2["aplicadas_sozinho"], 0)                        # 10 decisões, 100%: aplica
        auto = db.execute("SELECT * FROM gemeo_achado WHERE origem_resposta='automatico'").fetchall()
        self.assertTrue(all(a["escolha"] == "intencional" for a in auto))
        p = db.execute("SELECT resposta, nota FROM mv_pergunta WHERE id=?", (auto[0]["pergunta_id"],)).fetchone()
        self.assertIn("aplicado pelo sistema", p["nota"])
        self.assertEqual(len(K.exemplos_do_banco(db)), 10 + 10)              # o automático não ensina
        self.assertIn("aplica sozinho neste tipo", r2["explicacao"])
        K.corrigir(self.mv, auto[0]["id"], "erro_cota", "este não")          # a correção vira exemplo
        self.assertEqual(len(K.exemplos_do_banco(db)), 21)


if __name__ == "__main__":
    unittest.main()
