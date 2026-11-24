"""Marketing da Gestão no M&A: Rafaella aprova daqui, Marzia pela Gestão; aprovados vão para o robô do Marketing."""
import csv
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from physis_hub import mv_bots_extra as X

ITENS = [{"id": "p1", "titulo": "Post solar", "texto": "Texto", "redes": ["instagram", "linkedin"], "estado": "aguardando",
          "dataSugerida": "2026-12-01", "aprovacoes": {}},
         {"id": "p2", "titulo": "Rascunho", "estado": "rascunho", "aprovacoes": {}}]


class Marketing(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.b = self.d / "physis-hub.db"
        db = sqlite3.connect(self.b)
        db.execute("CREATE TABLE gestao_estado (chave TEXT PRIMARY KEY, valor TEXT NOT NULL, versao INTEGER NOT NULL, atualizado REAL NOT NULL, por TEXT NOT NULL)")
        db.execute("INSERT INTO gestao_estado VALUES (?,?,?,?,?)", (X.CHAVE_MKT, json.dumps(ITENS), 3, 100.0, "marzia"))
        db.commit(); db.close()
        (self.d / "dados").mkdir()
        self.env = mock.patch.dict(os.environ, {"PHYSIS_GESTAO_BANCOS": f"engineering={self.b}", "PHYSIS_MARKETING_DADOS": str(self.d / "dados")})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_uma_aprovacao_basta_e_exporta(self):
        self.assertEqual(X.marketing_exportar(), 0)
        r = X.marketing_decidir("p1", "aprovar", quem="marzia")
        self.assertEqual((r["estado"], r["aprovado_por"]), ("aprovado", "marzia"))
        self.assertEqual(X.marketing_exportar(), 1)
        linhas = list(csv.reader(open(self.d / "dados" / "conteudos_aprovados.csv", encoding="utf-8-sig"), delimiter=";"))
        self.assertEqual(linhas[1][:4], ["p1", "2026-12-01", "", "instagram,linkedin"])
        self.assertEqual(linhas[1][-1], "marzia")
        v = sqlite3.connect(self.b).execute("SELECT versao, por FROM gestao_estado").fetchone()
        self.assertEqual(v, (4, "marzia (M&A)"))

    def test_rafaella_e_avisada_quando_a_marzia_aprova(self):
        from physis_hub.mv import MV
        X.marketing_decidir("p1", "aprovar", quem="marzia")
        mv = MV(":memory:")
        X.bot_gestoes(mv, self.d / "gestoes")
        self.assertTrue(any(a["tipo"] == "mkt_aprovado" and "Marzia" in a["texto"] for a in mv.alertas()))

    def test_ajuste_e_estado_errado(self):
        X.marketing_decidir("p1", "ajuste", "trocar a foto")
        c = {x["id"]: x for x in X.marketing_conteudos()}
        self.assertEqual((c["p1"]["estado"], c["p1"]["aprovacoes"]), ("ajuste", {}))
        with self.assertRaises(ValueError):
            X.marketing_decidir("p2", "aprovar")
