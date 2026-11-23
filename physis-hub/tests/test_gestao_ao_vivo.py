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


class SemRepetir(unittest.TestCase):
    def test_titulo_que_ja_existe_nao_duplica(self):
        d = Path(tempfile.mkdtemp())
        b = d / "physis-hub.db"
        banco(b, ESTADO)
        with mock.patch.dict(os.environ, {"PHYSIS_GESTAO_BANCOS": f"engineering={b}", "PHYSIS_MV_GESTOES": str(d / "g")}):
            mv = MV(":memory:")
            mv.salvar_tarefa({"id": "f0-cnpj", "frente": "instituto", "titulo": "Abrir CNPJ do instituto", "responsavel": "Rafaella", "estado": "a_fazer"})
            r = X.bot_gestoes(mv)["ao_vivo"]["engineering"]
            self.assertIn("1 já existiam", r)
            self.assertIsNone(mv.tarefa("gestao:t1"))
            self.assertEqual(mv.tarefa("f0-cnpj")["estado"], "feita")
            self.assertEqual(mv.tarefa("gestao:t2")["depende_de"], [])

    def test_repetida_dentro_da_gestao(self):
        d = Path(tempfile.mkdtemp())
        b = d / "physis-hub.db"
        est = {"equipe": [], "tarefas": [{"id": f"imp-{i}", "texto": "Revisar Physis 3D", "projeto": "3D", "pessoa": "ana"} for i in range(5)],
               "feitas": {"imp-3": "2026-11-20"}}
        banco(b, est)
        with mock.patch.dict(os.environ, {"PHYSIS_GESTAO_BANCOS": f"engineering={b}", "PHYSIS_MV_GESTOES": str(d / "g")}):
            mv = MV(":memory:")
            X.bot_gestoes(mv)
            ts = [t for t in mv.db.execute("SELECT id, estado FROM mv_tarefa WHERE titulo='Revisar Physis 3D'")]
            self.assertEqual(len(ts), 1)
            self.assertEqual(ts[0][1], "feita")

    def test_mesma_tarefa_de_pessoas_diferentes_fica_separada(self):
        d = Path(tempfile.mkdtemp())
        b = d / "physis-hub.db"
        est = {"equipe": [{"id": "ana", "nome": "Ana"}, {"id": "bia", "nome": "Bia"}],
               "tarefas": [{"id": "a", "texto": "Ler o edital", "pessoa": "ana"}, {"id": "b", "texto": "Ler o edital", "pessoa": "bia"}],
               "feitas": {"b": "2026-11-23"}}
        banco(b, est)
        with mock.patch.dict(os.environ, {"PHYSIS_GESTAO_BANCOS": f"engineering={b}", "PHYSIS_MV_GESTOES": str(d / "g")}):
            mv = MV(":memory:")
            X.bot_gestoes(mv)
            self.assertEqual(mv.tarefa("gestao:a")["estado"], "a_fazer")
            self.assertEqual(mv.tarefa("gestao:b")["estado"], "feita")
            # Bia desmarca na Gestão: volta a fazer no M&A
            banco(b, dict(est, feitas={}), versao=2)
            X.bot_gestoes(mv)
            self.assertEqual(mv.tarefa("gestao:b")["estado"], "a_fazer")
