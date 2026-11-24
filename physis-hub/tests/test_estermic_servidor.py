"""Sistema Estermic à parte (24/11/2026): porta própria, estado no servidor com histórico, AVAC completo e IFC de instalações."""
import base64
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

from physis_hub import estermic_servidor as es
from physis_hub import mv_cli, mv_comandos

RAIZ = Path(__file__).resolve().parents[2]


class Servidor(unittest.TestCase):
    def setUp(self):
        self.b = es.Banco(":memory:")

    def subir(self, senha=None):
        env = {"PHYSIS_ESTERMIC_SENHA": senha} if senha else {}
        with mock.patch.dict(os.environ, env, clear=False):
            if not senha:
                os.environ.pop("PHYSIS_ESTERMIC_SENHA", None)
            s = es.servir(0, "127.0.0.1", self.b)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        self.addCleanup(s.shutdown)
        return f"http://127.0.0.1:{s.server_address[1]}"

    def test_pagina_estado_e_historico(self):
        u = self.subir()
        r = urllib.request.urlopen(u + "/")
        self.assertIn("estermic-avac.html?cliente=estermic", r.url)
        self.assertEqual(json.loads(urllib.request.urlopen(u + "/api/estermic/estado").read())["estado"], None)
        for nome in ("A", "B", "B"):
            req = urllib.request.Request(u + "/api/estermic/estado", json.dumps({"estado": {"cliente": {"nome": nome}, "subprojetos": []}}).encode(),
                                         {"Content-Type": "application/json"}, method="PUT")
            self.assertTrue(json.loads(urllib.request.urlopen(req).read())["ok"])
        self.assertEqual(json.loads(urllib.request.urlopen(u + "/api/estermic/estado").read())["estado"]["cliente"]["nome"], "B")
        self.assertEqual(len(self.b.historico()), 2, "versão igual não duplica")

    def test_so_pastas_permitidas(self):
        u = self.subir()
        self.assertEqual(urllib.request.urlopen(u + "/sistema/physis-avac.js").status, 200)
        for ruim in ("/physis-hub/physis_hub/mv.py", "/sistema/../CLAUDE.md", "/dados/physis-mv.db"):
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(u + ruim)

    def test_estado_invalido(self):
        with self.assertRaises(ValueError):
            self.b.gravar({"sem": "subprojetos"})

    def test_senha(self):
        u = self.subir("segredo-teste")
        with self.assertRaises(urllib.error.HTTPError) as c:
            urllib.request.urlopen(u + "/api/estermic/saude")
        self.assertEqual(c.exception.code, 401)
        req = urllib.request.Request(u + "/api/estermic/saude", headers={"Authorization": "Basic " + base64.b64encode(b"physis:segredo-teste").decode()})
        self.assertTrue(json.loads(urllib.request.urlopen(req).read())["ok"])

    def test_rede_exige_senha(self):
        with mock.patch.dict(os.environ, {"PHYSIS_ESTERMIC_SENHA": ""}):
            with self.assertRaises(SystemExit):
                es.servir(0, "0.0.0.0", self.b)


class Integracao(unittest.TestCase):
    def test_aprovacao_no_ma_agenda_e_ifc(self):
        ids = {a["id"]: a for a in mv_comandos.APROVACOES_23_11}
        self.assertIn("8704", ids["ap-p0-estermic-sistema"]["item"])
        self.assertTrue(any("estermic_8704" in " ".join(c) and "estermic_servidor" in " ".join(c) for c in mv_cli.comandos_agenda()))
        ifc = (RAIZ / "sistema" / "physis-ifc.js").read_text(encoding="utf-8")
        for c in ("IFCCHILLER", "IFCPUMP", "IFCFAN", "IFCAIRTERMINAL", "IFCDUCTSEGMENT", "IFCCOOLINGTOWER"):
            self.assertIn(c, ifc)
        est = (RAIZ / "modulos" / "estermic" / "estermic-avac.js").read_text(encoding="utf-8")
        self.assertIn("tipo:tipoIfc(q)", est)
        pag = (RAIZ / "modulos" / "estermic" / "estermic-avac.html").read_text(encoding="utf-8")
        self.assertIn('fetch("/api/estermic/estado"', pag)
        self.assertIn('src="avac-estermic-copia.js"', pag)
        self.assertEqual((RAIZ / "modulos" / "estermic" / "avac-estermic-copia.js").read_bytes(), (RAIZ / "sistema" / "physis-avac.js").read_bytes(),
                         "a Estermic leva o AVAC completo (água gelada, piscina, sauna, churrasqueira)")
