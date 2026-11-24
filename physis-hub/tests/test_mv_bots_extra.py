"""Bots compartilhados (physis_hub/mv_bots_extra.py): limites só por variável, alertas que fecham sozinhos, nada inventado."""
import json
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from physis_hub import mv_bots, mv_bots_extra as X, mv_cli
from physis_hub.mv import MV


def abertos(mv, bot):
    return {r[0]: r[1] for r in mv.db.execute("SELECT tipo||':'||ref, gravidade FROM mv_alerta WHERE bot=? AND resolvido IS NULL", (bot,))}


class Registro(unittest.TestCase):
    def test_todos_na_lista_na_agenda_e_no_vigia(self):
        from physis_hub import mv_vigia
        agenda = mv_cli.texto_agenda()
        for b in X.BOTS_EXTRA:
            self.assertIn(b, mv_bots.BOTS)
            self.assertIn(b, agenda)
            self.assertIn(b, mv_vigia.LIMITE_H)


class SemLimiteNaoInventa(unittest.TestCase):
    def test_iot_sem_limite_so_mede(self):
        d = Path(tempfile.mkdtemp())
        b = d / "hub.db"
        con = sqlite3.connect(b)
        con.execute("CREATE TABLE leitura (seq INTEGER PRIMARY KEY, no INTEGER, ts INTEGER, recebido REAL, origem TEXT, linha TEXT)")
        agora = time.time()
        con.execute("INSERT INTO leitura (no,ts,recebido,origem,linha) VALUES (7,1,?, 'x','')", (agora - 5 * 3600,))
        con.execute("INSERT INTO leitura (no,ts,recebido,origem,linha) VALUES (8,1,?, 'x','')", (agora - 600,))
        con.commit(); con.close()
        mv = MV(":memory:")
        with mock.patch.dict(os.environ, {"PHYSIS_IOT_MUDO_H": ""}):
            r = X.bot_dados_iot(mv, b, agora)
        self.assertEqual(r["nos"], 2)
        self.assertEqual(abertos(mv, "dados_iot"), {"sem_limite:PHYSIS_IOT_MUDO_H": "info"})
        with mock.patch.dict(os.environ, {"PHYSIS_IOT_MUDO_H": "2"}):
            X.bot_dados_iot(mv, b, agora)
        self.assertEqual(abertos(mv, "dados_iot"), {"no_mudo:7": "alerta"})


class Editais(unittest.TestCase):
    def test_prazo_e_vencido(self):
        from physis_hub import mv as mvmod
        from datetime import date
        mvmod.HOJE = lambda: date(2026, 11, 22)
        d = Path(tempfile.mkdtemp())
        csv = d / "banco.csv"
        csv.write_text("chave;titulo;prazo;frente_mais_aderente\nA;Edital A;2026-11-30;instituto\nB;Edital B;2026-11-01;instituto\n",
                       encoding="utf-8")
        mv = MV(":memory:")
        with mock.patch.dict(os.environ, {"PHYSIS_EDITAIS_AVISO_DIAS": "15"}):
            r = X.bot_editais(mv, csv)
        self.assertEqual((r["abertos"], r["vencidos"], r["proximos"]), (2, 1, 1))
        tipos = {k.split(":")[0] for k in abertos(mv, "editais")}
        self.assertEqual(tipos, {"vencido", "prazo"})


class Gestoes(unittest.TestCase):
    def test_nao_importada(self):
        d = Path(tempfile.mkdtemp())
        (d / "casa.json").write_text("{}")
        mv = MV(":memory:")
        with mock.patch.dict(os.environ, {"PHYSIS_GESTOES_MAX_H": "48", "PHYSIS_GESTAO_BANCOS": "nenhum"}):   # não lê a Gestão real
            r = X.bot_gestoes(mv, d)
        self.assertEqual(r["arquivos"], 1)
        self.assertIn("nao_importada:casa.json", abertos(mv, "gestoes"))


class Simulacao(unittest.TestCase):
    def test_casos_em_dia(self):
        mv = MV(":memory:")
        r = X.bot_simulacao(mv)
        self.assertTrue(r["em_dia"] and r["premissas_js"], r)
        self.assertEqual(abertos(mv, "simulacao"), {})


class Bancos(unittest.TestCase):
    def test_integridade_certificado_e_segredo(self):
        d = Path(tempfile.mkdtemp())
        bom = d / "a.db"
        sqlite3.connect(bom).execute("CREATE TABLE t(x)").connection.commit()
        ruim = d / "b.db"
        ruim.write_bytes(b"isto nao e sqlite" * 100)
        mv = MV(":memory:")
        with mock.patch.dict(os.environ, {"PHYSIS_DOMINIO": "exemplo.local", "PHYSIS_CERT_AVISO_DIAS": "20"}):
            r = X.bot_bancos(mv, [bom, ruim], d, validade=lambda h: 10.0)
        self.assertEqual(r["bancos"]["a.db"], "ok")
        a = abertos(mv, "bancos")
        self.assertIn(f"integridade:{ruim}", a)
        self.assertEqual(a["certificado:exemplo.local"], "atencao")
        self.assertTrue(X.SEGREDOS.search("firmware/x/secrets.h"))
        self.assertFalse(X.SEGREDOS.search("servicos/env/hub.env.exemplo"))


class Acervo(unittest.TestCase):
    def test_sem_trilhas_pede_e_com_trilhas_propoe(self):
        d = Path(tempfile.mkdtemp())
        (d / "acervo").mkdir()
        (d / "acervo" / "introducao_python.pdf").write_bytes(b"x")
        (d / "acervo" / "outra_coisa.pdf").write_bytes(b"x")
        mv = MV(":memory:")
        X.bot_acervo(mv, d / "acervo", d / "trilhas.json")
        self.assertIn("sem_trilhas:" + str(d / "trilhas.json"), abertos(mv, "acervo"))
        (d / "trilhas.json").write_text(json.dumps({"T1": {"nome": "Programação", "palavras": ["python"]}}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"PHYSIS_IA_URL": ""}):
            r = X.bot_acervo(mv, d / "acervo", d / "trilhas.json")
            r2 = X.bot_acervo(mv, d / "acervo", d / "trilhas.json")
        self.assertEqual((r["materiais"], r["propostas_novas"], r["sem_trilha"]), (2, 1, 1))
        self.assertEqual(r2["propostas_novas"], 0)          # não repete
        self.assertNotIn("sem_trilhas:" + str(d / "trilhas.json"), abertos(mv, "acervo"))

    def test_ia_sem_configuracao_e_none(self):
        with mock.patch.dict(os.environ, {"PHYSIS_IA_URL": ""}):
            self.assertIsNone(X.ia_local("oi"))


if __name__ == "__main__":
    unittest.main()
