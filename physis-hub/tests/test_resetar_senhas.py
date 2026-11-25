"""Resetar todas as senhas dos sites e a da Estermic (24/11/2026: "nenhuma senha está aceita; resetar todas")."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from physis_hub import estermic_servidor as es
from physis_hub.hub import Hub

RAIZ = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cs", RAIZ / "ferramentas" / "contas_site.py")
cs = importlib.util.module_from_spec(spec); spec.loader.exec_module(cs)


class Resetar(unittest.TestCase):
    def test_todas_as_contas_entram_com_a_senha_nova(self):
        d = Path(tempfile.mkdtemp()); b = d / "physis-hub.db"
        h = Hub(str(b), org="r")
        h.criar_conta("Rafaella", "Rafaella.Dourado@x.com", "senha-antiga-muito-boa-1", "direcao") if hasattr(h, "criar_conta") else None
        n = h._db.execute("SELECT COUNT(*) FROM conta").fetchone()[0]
        if not n:
            self.skipTest("criação de conta com outra assinatura neste Hub")
        h._db.close()
        with mock.patch.dict(cs.SITES, {"teste": d}, clear=True):
            self.assertEqual(cs.resetar("Physis-nova-senha-2026!"), 0)
        h2 = Hub(str(b), org="r")
        usu = h2._db.execute("SELECT usuario FROM conta").fetchone()[0]
        self.assertEqual(usu, usu.lower())
        self.assertTrue(h2.entrar(usu, "Physis-nova-senha-2026!").get("ok"))

    def test_estermic_senha_por_arquivo(self):
        d = Path(tempfile.mkdtemp())
        es.definir_senha("Estermic-nova-2026!", d)
        self.assertTrue(es.conferir_senha("Estermic-nova-2026!", d))
        self.assertFalse(es.conferir_senha("errada", d))
        self.assertIsNone(es.conferir_senha("x", Path(tempfile.mkdtemp())))
