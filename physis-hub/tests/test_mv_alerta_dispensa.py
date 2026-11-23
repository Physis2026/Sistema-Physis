"""Alerta resolvido na tela não volta na rodada seguinte do bot (23/11/2026)."""
import time
import unittest

from physis_hub import mv_cli
from physis_hub.mv import MV


class Dispensa(unittest.TestCase):
    def test_resolvido_fica_resolvido(self):
        mv = MV(":memory:")
        aid = mv.alertar("documentos", "falha", "a.docx", "atencao", "falha")
        mv.resolver_alerta(aid)
        mv.alertar("documentos", "falha", "a.docx", "atencao", "falha de novo")
        self.assertEqual([a["id"] for a in mv.alertas()], [])
        mv.db.execute("UPDATE mv_alerta_dispensa SET ate=?", (time.time() - 1,))
        mv.alertar("documentos", "falha", "a.docx", "atencao", "ainda com falha")
        self.assertEqual([a["id"] for a in mv.alertas()], [aid])

    def test_agenda_liga_o_hub(self):
        t = mv_cli.texto_agenda()
        self.assertIn("PhysisMV\\hub", t)
        self.assertIn("physis_hub.servidor", t)
