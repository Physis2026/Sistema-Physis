"""Aba Gêmeo digital da Casa Physis na plataforma (gemeo_painel.py e /api/gemeo)."""
import json
import os
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from physis_hub import gemeo_painel as gp

RAIZ = Path(__file__).resolve().parents[2]
PAINEL = RAIZ / "physis-hub" / "web" / "painel.html"


class Semente(unittest.TestCase):
    def test_resumo_da_semente_do_repositorio(self):
        p = gp.pasta_gemeo()
        self.assertIsNotNone(p)
        r = gp.resumo(p)
        self.assertTrue(r["ok"])
        self.assertEqual(r["validacao"], [])
        self.assertEqual(r["totais"]["elementos"], sum(z["elementos"] for z in r["zonas"]))
        self.assertEqual({z["entidade"] for z in r["zonas"]}, {"Physis Engineering", "Instituto Physis", "Casa Physis"})

    def test_rotas(self):
        self.assertEqual(gp.rota("/api/gemeo")[0], 200)
        b = gp.rota("/api/gemeo/semente")
        self.assertEqual(b[0], "bytes")
        self.assertIn("gemeo", json.loads(b[3]))
        self.assertEqual(gp.rota("/api/gemeo/xyz")[0], 404)

    def test_sem_semente_nao_tem_aba(self):
        with tempfile.TemporaryDirectory() as d:
            antes = os.environ.pop("PHYSIS_GEMEO", None)
            orig = gp.AQUI
            try:
                os.environ["PHYSIS_GEMEO"] = d
                gp.AQUI = Path(d) / "a" / "b"
                self.assertIsNone(gp.pasta_gemeo(Path(d)))
                self.assertEqual(gp.rota("/api/gemeo", Path(d))[0], 404)
            finally:
                gp.AQUI = orig
                os.environ.pop("PHYSIS_GEMEO", None)
                if antes:
                    os.environ["PHYSIS_GEMEO"] = antes


class Painel(unittest.TestCase):
    def test_sub_aba_no_planejador_com_nome_acessivel(self):
        h = PAINEL.read_text(encoding="utf-8")
        self.assertIn("function telaGemeo()", h)
        self.assertIn("data-plan-sub=", h)
        self.assertIn('aria-label="Planejador ou gêmeo digital"', h)
        self.assertIn("ui.inst.gemeo", h)


class Servidor(unittest.TestCase):
    def test_rota_responde_ou_pede_sessao(self):
        from physis_hub.hub import Hub
        from physis_hub.servidor import iniciar
        with tempfile.TemporaryDirectory() as d:
            hub = Hub(str(Path(d) / "h.db"), org="casa-physis-inicial", lugar="t")
            srv = iniciar(hub, 0, endereco="127.0.0.1")
            try:
                porta = srv.server_address[1]
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/gemeo", timeout=10) as r:
                        cod, j = r.status, json.loads(r.read())
                except urllib.error.HTTPError as e:
                    cod, j = e.code, json.loads(e.read() or b"{}")
                self.assertIn(cod, (200, 401))
                if cod == 200:
                    self.assertTrue(j["ok"])
            finally:
                srv.shutdown()
                srv.server_close()


if __name__ == "__main__":
    unittest.main()
