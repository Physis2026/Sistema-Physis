"""Banco criado por outra versão com colunas a mais em mv_alerta (diagnóstico de 22/11: 13 colunas × 11 valores)."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from physis_hub.mv import MV


class ColunasAMais(unittest.TestCase):
    def test_alertar_com_13_colunas(self):
        f = Path(tempfile.mkdtemp()) / "physis-mv.db"
        db = sqlite3.connect(f)
        db.execute("CREATE TABLE mv_alerta (id TEXT PRIMARY KEY, bot TEXT NOT NULL, tipo TEXT NOT NULL, ref TEXT NOT NULL DEFAULT '', "
                   "frente TEXT NOT NULL DEFAULT '', gravidade TEXT NOT NULL, texto TEXT NOT NULL, acao TEXT NOT NULL DEFAULT '', "
                   "criado REAL NOT NULL, visto REAL NOT NULL, resolvido REAL, responsavel TEXT, roteado_por TEXT)")
        db.commit(); db.close()
        mv = MV(str(f))
        aid = mv.alertar("teste", "t", "r", "info", "texto")
        self.assertEqual(mv.db.execute("SELECT texto FROM mv_alerta WHERE id=?", (aid,)).fetchone()[0], "texto")
