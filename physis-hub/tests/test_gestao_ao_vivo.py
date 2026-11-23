"""Gestão ao vivo → M&A (23/11/2026): lê o banco do site da Physis só para leitura e importa quando muda."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from physis_hub import mv_bots_extra as X
from physis_hub.mv import MV

ESTADO = {"equipe": [{"id": "rafaella", "nome": "Rafaella", "admin": True}],
          "tarefas": [{"id": "t1", "pessoa": "rafaella", "h": "micro", "projeto": "Fase 0", "texto": "Abrir CNPJ do Instituto"},
                      {"id": "t2", "pessoa": "rafaella", "h": "media", "projeto": "Fase 0", "texto": "Contrato social", "depende": "t1"}],
          "feitas": {"t1": "2026-11-22"}}


def banco(caminho, estado, versao=1):
    db = sqlite3.connect(caminho)
    db.execute("CREATE TABLE IF NOT EXISTS gestao_estado (chave TEXT PRIMARY KEY, valor TEXT NOT NULL, versao INTEGER NOT NULL, atualizado REAL NOT NULL, por TEXT NOT NULL)")
    db.execute("INSERT OR REPLACE INTO gestao_estado VALUES (?,?,?,?,?)", (X.CHAVE_GESTAO, json.dumps(estado), versao, 1000.0 + versao, "rafaella"))
    db.commit()
    db.close()


class AoVivo(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.b = self.d / "physis-hub.db"
        banco(self.b, ESTADO)
        self.env = mock.patch.dict(os.environ, {"PHYSIS_GESTAO_BANCOS": f"engineering={self.b}", "PHYSIS_MV_GESTOES": str(self.d / "gestoes")})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_importa_e_so_quando_muda(self):
        mv = MV(":memory:")
        r = X.bot_gestoes(mv)
        self.assertIn("2 tarefa", r["ao_vivo"]["engineering"])
        t1, t2 = mv.tarefa("gestao:t1"), mv.tarefa("gestao:t2")
        self.assertEqual(t1["estado"], "feita")
        self.assertEqual(t2["responsavel"], "Rafaella")
        self.assertEqual(X.bot_gestoes(mv)["ao_vivo"]["engineering"], "sem mudança")
        novo = dict(ESTADO, tarefas=ESTADO["tarefas"] + [{"id": "t3", "pessoa": "rafaella", "h": "longa", "projeto": "Lote", "texto": "Projeto do lote"}])
        banco(self.b, novo, versao=2)
        self.assertIn("3 tarefa", X.bot_gestoes(mv)["ao_vivo"]["engineering"])
        self.assertIsNotNone(mv.tarefa("gestao:t3"))

    def test_nao_escreve_no_banco_da_gestao(self):
        antes = self.b.read_bytes()
        X.bot_gestoes(MV(":memory:"))
        self.assertEqual(self.b.read_bytes(), antes)

    def test_sem_banco_avisa(self):
        with mock.patch.dict(os.environ, {"PHYSIS_GESTAO_BANCOS": f"engineering={self.d / 'nao-existe.db'}"}):
            mv = MV(":memory:")
            self.assertEqual(X.bot_gestoes(mv)["ao_vivo"]["engineering"], "sem banco")
            self.assertTrue(any(a["tipo"] == "sem_gestao" for a in mv.alertas()))
