"""Auditoria cruzada (mv_auditoria.py), caixa de perguntas das pendências, bot páginas, sala e demonstração com o mapa."""
import json
import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from physis_hub import mv_auditoria as A, mv_bots, mv_bots_extra as X, mv_comandos, mv_mock, mv_paginas, mv_sala
from physis_hub.mv import MV


class Caixa(unittest.TestCase):
    def test_perguntas_unicas_e_limite_respondido_vale_no_bot(self):
        mv = MV(":memory:")
        mv.alertar("atrasos", "marco_estourado", "k:j2", "alerta", "Passa do marco X: J2 termina +26 d")
        r1, r2 = A._caixa(mv), A._caixa(mv)
        self.assertEqual(r1["perguntas"], r2["perguntas"])                       # não duplica
        ps = mv_comandos.perguntas(mv)
        self.assertEqual(len(ps), r1["perguntas"])
        self.assertTrue(any(p["origem"] == "pendencia:marco:k:j2" and "Antecipar a tarefa" in p["opcoes"] for p in ps))
        # resposta numérica na caixa vira o limite do bot dados_iot
        pid = next(p["id"] for p in ps if p["origem"] == A.origem_limite("PHYSIS_IOT_MUDO_H"))
        mv_comandos.responder(mv, pid, "3 horas")
        self.assertEqual(A.limite_respondido(mv, "PHYSIS_IOT_MUDO_H"), 3.0)
        d = Path(tempfile.mkdtemp())
        con = sqlite3.connect(d / "hub.db")
        con.execute("CREATE TABLE leitura (seq INTEGER PRIMARY KEY, no INTEGER, ts INTEGER, recebido REAL, origem TEXT, linha TEXT)")
        con.execute("INSERT INTO leitura (no,ts,recebido,origem,linha) VALUES (5,1,?,'x','')", (time.time() - 5 * 3600,))
        con.commit(); con.close()
        with mock.patch.dict(os.environ, {"PHYSIS_IOT_MUDO_H": ""}):
            X.BOTS_EXTRA["dados_iot"](mv, d / "hub.db")
        abertos = {r[0] for r in mv.db.execute("SELECT tipo||':'||ref FROM mv_alerta WHERE bot='dados_iot' AND resolvido IS NULL")}
        self.assertEqual(abertos, {"no_mudo:5"})


class Cruzamento(unittest.TestCase):
    def test_tudo_ligado(self):
        cr = A.cruzar(conferir_copias=False)
        self.assertEqual(cr["falhas"], [], cr["falhas"])
        self.assertEqual(cr["modulos_sem_uso"], [])
        self.assertEqual(cr["variaveis_sem_doc"], [], "rode ferramentas/listar_variaveis.py")
        self.assertIn("auditoria", mv_bots.BOTS)

    def test_plano_de_intervencao(self):
        mv = MV(":memory:")
        mv.alertar("sentinela", "servico", "x", "alerta", "porta 8700 não responde", "Ver o serviço")
        d = Path(tempfile.mkdtemp())
        r = mv_bots.BOTS["auditoria"](mv, d, conferir_copias=False)
        md = (d / "plano-de-intervencao.md").read_text(encoding="utf-8")
        self.assertIn("porta 8700 não responde", md)
        self.assertIn("Caixa de perguntas", md)
        self.assertGreater(r["perguntas_abertas"], 0)
        self.assertTrue(json.loads((d / "plano-de-intervencao.json").read_text(encoding="utf-8"))["itens"])


class Paginas(unittest.TestCase):
    def test_razao_social_no_rodape(self):
        base = '<html lang="pt-BR"><head><title>Tela X</title><meta name="viewport"></head><body><main></main>{}</body></html>'
        ok = {i["cod"]: i["ok"] for i in mv_paginas.conferir(base.format("<footer>Physis Engineering Ltda.</footer>"), "x", set())}
        nao = {i["cod"]: i["ok"] for i in mv_paginas.conferir(base.format("<footer>Physis</footer>"), "x", set())}
        self.assertTrue(ok["razao"])
        self.assertFalse(nao["razao"])
        self.assertTrue(ok["cnpj"])                                           # decisão de 22/11/2026: rodapé SEM CNPJ e sem cidade
        com_cnpj = {i["cod"]: i["ok"] for i in mv_paginas.conferir(base.format("<footer>Physis Engineering Ltda. CNPJ 00</footer>"), "x", set())}
        self.assertFalse(com_cnpj["cnpj"])
        self.assertNotIn("termos", ok)

    def test_bot_paginas_roda(self):
        mv = MV(":memory:")
        with mock.patch.object(mv_paginas, "INSTITUTO", Path(tempfile.mkdtemp()) / "sem-instituto"):   # só as telas deste repositório
            r = mv_bots.BOTS["paginas"](mv)
        self.assertEqual(r["paginas"], r["completas"])                         # todas as telas completas


class SalaEDemo(unittest.TestCase):
    def test_sala(self):
        mv = MV(":memory:")
        mv.registrar_execucao("vigia", time.time(), "{}")
        d = Path(tempfile.mkdtemp())
        r = mv_sala.bot_sala(mv, d / "sala.html")
        h = (d / "sala.html").read_text(encoding="utf-8")
        self.assertIn("Sala dos bots", h)
        self.assertIn("auditoria", h)
        self.assertGreaterEqual(r.get("parado", 0), 1)                         # bots que nunca rodaram aparecem como parados

    def test_demo_tem_mapa_e_three(self):
        d = Path(tempfile.mkdtemp())
        p = mv_mock.gerar(d / "demo.html")
        h = Path(p).read_text(encoding="utf-8")
        self.assertIn('"/api/mv/integracoes"', h)
        self.assertIn("THREE", h)


if __name__ == "__main__":
    unittest.main()
