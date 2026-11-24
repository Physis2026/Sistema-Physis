"""Projetos municipais → Editais (24/11/2026)."""
import importlib.util
import unittest
from pathlib import Path

from physis_hub import mv_clientes
from physis_hub.mv import MV

RAIZ = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("me", RAIZ / "ferramentas" / "municipais_para_editais.py")
me = importlib.util.module_from_spec(spec); spec.loader.exec_module(me)


class Mover(unittest.TestCase):
    def test_previa_e_aplicar(self):
        mv = MV(":memory:"); cl = mv_clientes.Clientes(mv)
        cl.salvar({"id": "pesq-mun", "nome": "Pesquisa municipal Petrópolis", "tipo": "futuro"})
        mv.salvar_tarefa({"id": "t1", "frente": "engineering", "projeto": "Prefeitura de Itirapuã · diagnóstico", "titulo": "Levantar dados", "responsavel": "Rafaella"})
        p = me.planejar(mv)
        self.assertEqual([c["id"] for c in p["contas"]], ["pesq-mun"])
        self.assertEqual(p["projetos"], {"Prefeitura de Itirapuã · diagnóstico": 1})
        me.aplicar(mv, p)
        self.assertEqual(cl.conta("pesq-mun")["estado"], "arquivada")
        self.assertEqual(mv.db.execute("SELECT COUNT(*) FROM mv_edital").fetchone()[0], 2)
        self.assertTrue(mv.tarefa("t1")["projeto"].startswith("Edital · "))
        self.assertEqual(me.planejar(mv)["projetos"], {}, "rodar de novo não repete")
