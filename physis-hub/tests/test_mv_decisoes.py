"""Depois de decidir (23/11/2026): lista limpa, aprovado vira execução, ajuste vai para a Rafaella, reprovado/descartado para antigos."""
import tempfile
import unittest
from pathlib import Path

from physis_hub import mv_comandos
from physis_hub.mv import MV


class Decisoes(unittest.TestCase):
    def setUp(self):
        self.mv = MV(":memory:")
        self.c = mv_comandos.Comandos(self.mv)
        self.c.semear_aprovacoes([{"id": "ap-a", "item": "Item A", "prazo": "2026-11-30"},
                                  {"id": "ap-b", "item": "Item B", "prazo": "2026-11-30"},
                                  {"id": "ap-c", "item": "Item C", "prazo": "2026-11-30"}])

    def test_lista_limpa_e_tarefas(self):
        self.c.decidir("ap-a", "aprovado")
        self.c.decidir("ap-b", "ajustar", "trocar o título")
        self.c.decidir("ap-c", "reprovado")
        self.assertEqual(self.c.aprovacoes(), [])
        self.assertEqual({a["id"] for a in self.c.aprovacoes(antigos=True)}, {"ap-a", "ap-b", "ap-c"})
        ex = self.mv.tarefa("exec-ap-a")
        self.assertEqual((ex["estado"], ex["titulo"]), ("fazendo", "Executar: Item A"))
        aj = self.mv.tarefa("ajuste-ap-b")
        self.assertEqual(aj["responsavel"], "Rafaella")
        self.assertIn("trocar o título", aj["titulo"])
        self.assertIsNone(self.mv.tarefa("exec-ap-c"))

    def test_descartado_vai_para_antigos(self):
        d = Path(tempfile.mkdtemp()) / "versao-zero" / "casa"
        d.mkdir(parents=True)
        arq = d / "artigo.odt"
        arq.write_bytes(b"x")
        p = self.c._pedido("kit", "kit:casa:artigo", "", "rascunho", "versão zero", str(arq), origem="kit")
        r = self.c.decidir_pedido(p["id"], "descartado")
        self.assertFalse(arq.exists())
        self.assertTrue((d / "antigos" / "artigo.odt").is_file())
        self.assertEqual(r["arquivo"], str(d / "antigos" / "artigo.odt"))

    def test_pedido_ajuste_vira_tarefa_da_rafaella(self):
        p = self.c._pedido("kit", "kit:gsa:act", "", "rascunho", "versão zero", "", origem="kit")
        self.c.decidir_pedido(p["id"], "ajustar", "incluir parceiros")
        self.assertEqual(self.mv.tarefa(f"ajuste-ped{p['id']}")["responsavel"], "Rafaella")
