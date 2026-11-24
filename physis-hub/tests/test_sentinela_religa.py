"""Sentinela religa pela agenda o serviço fora do ar (24/11/2026: o M&A caiu e só voltava no próximo login)."""
import unittest

from physis_hub import mv_vigia
from physis_hub.mv import MV


class Religa(unittest.TestCase):
    def test_religa_so_o_que_caiu(self):
        mv = MV(":memory:"); chamadas = []
        def executar(cmd):
            chamadas.append(cmd); return 0, "ok"
        r = mv_vigia.religar_servicos(mv, executar, escutando=lambda p: p != 8710, windows=True)
        self.assertEqual([x["porta"] for x in r], [8710])
        self.assertEqual(chamadas, [["schtasks", "/Run", "/TN", "PhysisMV\\painel"]])
        self.assertTrue(any(a["tipo"] == "religado" for a in mv.alertas()))

    def test_linux_so_avisa(self):
        mv = MV(":memory:")
        r = mv_vigia.religar_servicos(mv, lambda c: self.fail("não roda nada"), escutando=lambda p: p != 8704, windows=False)
        self.assertEqual((r[0]["porta"], r[0]["religado"]), (8704, False))
