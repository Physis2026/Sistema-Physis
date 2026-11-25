"""Cadastro aberto (InovaSTEM) e login exigido na rede local (25/11/2026)."""
import json
import os
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from physis_hub.hub import Hub

SENHA = "Senha-Forte-2026-xyz!"


class Cadastro(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.h = Hub(str(Path(self.tmp.name) / "h.db"), org="inovastem", lugar="t")
        self.assertTrue(self.h.criar_conta("Dona", "dona@x.org", SENHA)["ok"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_fechado_exige_admin(self):
        self.assertFalse(self.h.criar_conta("Ana", "ana@x.org", SENHA)["ok"])

    def test_aberto_cria_sempre_cliente(self):
        r = self.h.criar_conta("Ana", "ana@x.org", SENHA, papel="administrador", aberto=True)
        self.assertTrue(r["ok"], r)
        papel = {c["usuario"]: c["papel"] for c in self.h.contas()}["ana@x.org"]
        self.assertEqual(papel, "cliente")


class Servidor(unittest.TestCase):
    def _servidor(self, env):
        from physis_hub.servidor import iniciar
        antes = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v) for k, v in antes.items()])
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        h = Hub(str(Path(tmp.name) / "h.db"), org="inovastem", lugar="t")
        h.criar_conta("Dona", "dona@x.org", SENHA)
        srv = iniciar(h, 0, endereco="127.0.0.1"); self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        return srv.server_address[1]

    def _post(self, porta, rota, corpo):
        req = urllib.request.Request(f"http://127.0.0.1:{porta}{rota}", data=json.dumps(corpo).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read()), r.headers.get("Set-Cookie") or ""
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}"), ""

    def test_cadastro_aberto_entra_direto(self):
        p = self._servidor({"PHYSIS_CADASTRO_ABERTO": "1", "PHYSIS_EXIGIR_LOGIN": "1"})
        with urllib.request.urlopen(f"http://127.0.0.1:{p}/api/instancia", timeout=10) as r:
            j = json.loads(r.read())
        self.assertTrue(j["cadastro_aberto"]); self.assertTrue(j["exige_login"])
        cod, j, ck = self._post(p, "/api/conta/criar", {"nome": "Bia", "usuario": "bia@x.org", "senha": SENHA})
        self.assertEqual(cod, 200, j)
        self.assertIn("physis_sessao=", ck)

    def test_fechado_recusa(self):
        p = self._servidor({"PHYSIS_CADASTRO_ABERTO": "0"})
        cod, j, _ = self._post(p, "/api/conta/criar", {"nome": "Bia", "usuario": "bia@x.org", "senha": SENHA})
        self.assertEqual(cod, 400, j)


if __name__ == "__main__":
    unittest.main()
