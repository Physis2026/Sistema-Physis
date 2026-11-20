"""Correções da auditoria 39 (19/11/2026): R-01 datas preservadas e nota honesta; R-02 backup, resumo, rotina e falhas da CLI;
R-03 validação de entrada; R-04 cabeçalhos e links seguros."""
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from physis_hub import mv as mvmod
from physis_hub import mv_bots, mv_cli, mv_servidor
from physis_hub.mv import MV, ErroMV


def gestao(tmp: Path, n=2) -> Path:
    d = {"tabelas": {"pessoa": [{"pessoa_id": "p1", "nome": "Ana"}], "projeto": [{"projeto_id": "j1", "nome": "Proj"}],
                     "tarefa": [{"tarefa_id": i, "titulo": f"T{i}", "pessoa_id": "p1", "projeto_id": "j1", "horizonte": "micro"}
                                for i in range(1, n + 1)]}}
    p = tmp / "g.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    return p


class TestR01(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mv = MV(":memory:")

    def tearDown(self):
        mvmod.HOJE = lambda: date.today()
        self.tmp.cleanup()

    def test_reimportacao_preserva_datas(self):
        g = gestao(Path(self.tmp.name))
        self.mv.importar_gestao(g, inicio=date(2026, 11, 1))
        t = self.mv.tarefa("gestao:1")
        t.update(inicio="2026-11-03", fim="2026-11-05", duracao_d=3, data_estimada=False)
        self.mv.salvar_tarefa(t, "gestao")
        self.mv.importar_gestao(g, inicio=date(2026, 12, 1))          # reimportação um mês depois
        t1, t2 = self.mv.tarefa("gestao:1"), self.mv.tarefa("gestao:2")
        self.assertEqual((t1["inicio"], t1["fim"], t1["data_estimada"]), ("2026-11-03", "2026-11-05", 0))
        self.assertEqual(t2["inicio"], "2026-11-01")                    # a estimada também não "volta o relógio"
        mvmod.HOJE = lambda: date(2026, 11, 20)
        self.assertTrue(self.mv.atrasada(t1))

    def test_nota_sem_dados_com_datas_estimadas(self):
        mvmod.HOJE = lambda: date(2026, 11, 19)
        self.mv.importar_gestao(gestao(Path(self.tmp.name), 4), inicio=date(2026, 11, 19))
        f = self.mv.saude()["frentes"]["engineering"]
        self.assertIsNone(f["nota"])
        self.assertEqual((f["confianca_pct"], f["nota_calculada"]), (0, 100))
        self.assertIsNone(self.mv.saude()["frentes"]["casa"]["nota"])   # frente sem tarefas: sem dados
        for i in range(1, 4):
            t = self.mv.tarefa(f"gestao:{i}")
            t["data_estimada"] = False
            self.mv.salvar_tarefa(t, "gestao")
        f = self.mv.saude()["frentes"]["engineering"]
        self.assertEqual((f["confianca_pct"], f["nota"]), (75, 100))


class TestR02(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.mv = MV(self.dir / "mv.db")
        self.mv.salvar_tarefa({"id": "a", "frente": "casa", "titulo": "A", "inicio": "2026-11-19", "fim": "2026-11-20"})

    def tearDown(self):
        self.mv.db.close()
        self.tmp.cleanup()

    def test_backup_confere_e_restaura(self):
        r = mv_bots.backup(self.mv, self.dir / "bk", hoje=date(2026, 11, 22))   # domingo: testa restauração
        self.assertTrue(r["ok"])
        self.assertTrue(r["restauracao_testada"])
        self.assertTrue(Path(r["arquivo"]).is_file())

    def test_resumo_gera_md_e_odt(self):
        r = mv_bots.resumo(self.mv, self.dir / "res", hoje=date(2026, 11, 19))
        arqs = sorted(p.suffix for p in (self.dir / "res" / "resumos").iterdir())
        self.assertIn(".md", arqs)
        self.assertIn(".odt", arqs)
        md = next((self.dir / "res" / "resumos").glob("*.md")).read_text(encoding="utf-8")
        self.assertIn("confiança", md)

    def test_rotina_alerta_backup_e_resumo_parados(self):
        r = mv_bots.conferir_rotina(self.mv, self.dir / "vazio")
        tipos = {a["tipo"] for a in self.mv.alertas()}
        self.assertEqual((r["backup_h"], r["resumo_h"]), (None, None))
        self.assertTrue({"backup_atrasado", "resumo_atrasado"} <= tipos)
        mv_bots.backup(self.mv, self.dir / "bk", hoje=date(2026, 11, 19))
        mv_bots.resumo(self.mv, self.dir / "res", hoje=date(2026, 11, 19))
        mv_bots.conferir_rotina(self.mv, self.dir / "bk")
        self.assertFalse({"backup_atrasado", "resumo_atrasado"} & {a["tipo"] for a in self.mv.alertas()})
        velho = time.time() + 27 * 3600
        mv_bots.conferir_rotina(self.mv, self.dir / "bk", agora=velho)
        self.assertIn("backup_atrasado", {a["tipo"] for a in self.mv.alertas()})

    def test_falha_da_cli_fica_registrada(self):
        antes = os.environ.get("PHYSIS_MV_DADOS")
        os.environ["PHYSIS_MV_DADOS"] = str(self.dir / "dados")
        try:
            self.assertEqual(mv_cli.main(["importar", str(self.dir / "nao-existe.json")]), 1)
            log = (self.dir / "dados" / "mv_cli.log").read_text(encoding="utf-8")
            self.assertIn("FileNotFoundError", log)
            m = MV()
            self.assertTrue(any(a["tipo"] == "cli_falhou" for a in m.alertas()))
            m.db.close()
        finally:
            if antes is None:
                os.environ.pop("PHYSIS_MV_DADOS", None)
            else:
                os.environ["PHYSIS_MV_DADOS"] = antes


class TestR03(unittest.TestCase):
    def setUp(self):
        self.mv = MV(":memory:")
        self.base = {"id": "x", "frente": "casa", "titulo": "X"}

    def test_entradas_invalidas_recusadas(self):
        ruins = [{"duracao_d": 10 ** 12}, {"duracao_d": "abc"}, {"depende_de": 5}, {"depende_de": ["../x"]},
                 {"inicio": "2026-02-30"}, {"versao": "final"}, {"prioridade": "alta"}, {"prioridade": 99},
                 {"titulo": "x" * 501}]
        for r in ruins:
            with self.assertRaises(ErroMV, msg=r):
                self.mv.salvar_tarefa({**self.base, **r})
        self.assertEqual(self.mv.tarefas(), [])
        for l in [{"valor": float("inf")}, {"valor": "nan"}, {"valor": 1e13}, {"data": "2026-13-01"}]:
            with self.assertRaises(ErroMV, msg=l):
                self.mv.lancar({"entidade": "casa", "tipo": "receita", "data": "2026-11-19", "valor": 1, **l})
        self.mv.saude()      # o painel continua lendo

    def test_dependencia_desconhecida_vira_erro(self):
        with self.assertRaises(ErroMV):
            self.mv.salvar_tarefa({**self.base, "depende_de": ["nao-existe"]}, conferir_deps=True)


class TestR04Servidor(unittest.TestCase):
    def setUp(self):
        self.mv = MV(":memory:")
        self.srv = mv_servidor.servir(self.mv, 0)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def _get(self, p, cab=None):
        req = urllib.request.Request(self.url + p, headers=cab or {})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def test_cabecalhos_de_seguranca(self):
        st, h, _ = self._get("/")
        self.assertEqual(st, 200)
        self.assertIn("frame-ancestors 'none'", h["Content-Security-Policy"])
        self.assertEqual(h["X-Frame-Options"], "DENY")
        self.assertEqual(h["Referrer-Policy"], "no-referrer")

    def test_exportacao_exige_navegacao_do_proprio_painel(self):
        st, _, _ = self._get("/api/mv/exportar?vista=tarefas&formato=ods", {"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(st, 403)
        st, _, b = self._get("/api/mv/exportar?vista=tarefas&formato=ods", {"Sec-Fetch-Site": "same-origin"})
        self.assertEqual(st, 200)
        self.assertEqual(b[:2], b"PK")

    def test_erro_interno_vira_json_500(self):
        orig = self.mv.saude
        self.mv.saude = lambda: 1 / 0
        try:
            st, h, b = self._get("/api/mv/saude")
        finally:
            self.mv.saude = orig
        self.assertEqual(st, 500)
        self.assertIn("erro", json.loads(b))

    def test_link_de_edital_so_http(self):
        from physis_hub import mv_editais
        self.assertEqual(mv_editais.link_seguro("javascript:alert(1)"), "")
        self.assertEqual(mv_editais.link_seguro(" https://x.org/a "), "https://x.org/a")
        self.assertEqual(mv_editais.link_seguro("data:text/html,x"), "")


if __name__ == "__main__":
    unittest.main()
