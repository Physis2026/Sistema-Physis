"""Kit aprovado no M&A vira documento oficial; tarefas Executar que os bots fazem sozinhos (24/11/2026)."""
import tempfile
import unittest
from pathlib import Path

from physis_hub import mv_comandos, mv_kit
from physis_hub.mv import MV


class Kit(unittest.TestCase):
    def test_aprovado_vira_oficial_e_tarefa_feita(self):
        mv = MV(":memory:"); c = mv_comandos.Comandos(mv); d = Path(tempfile.mkdtemp())
        v0 = d / "pitch.odt"; v0.write_bytes(b"odt")
        p = c._pedido("kit", "kit:engineering:pitch", "", "rascunho", "versão zero", str(v0), origem="kit")
        c.decidir_pedido(p["id"], "aprovado")
        outro = c._pedido("claude", "algo que só a equipe faz", "", "rascunho", "x")
        c.decidir_pedido(outro["id"], "aprovado")
        r = mv_kit.executar_tarefas(mv, d / "oficial")
        self.assertEqual(len(r["kit"]["gerados"]), 1)
        alvo = Path(r["kit"]["gerados"][0]["arquivo"])
        self.assertTrue(alvo.is_file()); self.assertIn("Physis Engineering", str(alvo))
        self.assertEqual([t["id"] for t in r["feitas"]], [f"exec-ped{p['id']}"])
        self.assertEqual([t["id"] for t in r["restantes"]], [f"exec-ped{outro['id']}"], "o que o bot não faz não é marcado como feito")
