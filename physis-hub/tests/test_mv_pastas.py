"""Pastas de documentos do OneDrive (23/11/2026): as 6 pastas, nome "Global Sourh Alliance", frentes e agenda curta."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from physis_hub import mv_bots, mv_cli, mv_kit


class Frentes(unittest.TestCase):
    def test_frente_de(self):
        D = r"C:\\Users\\rafae\\OneDrive - Physis Engineering\\Documents"
        casos = {"Casa Physis\\cardapio.docx": "casa", "Global Sourh Alliance\\concept note.docx": "transversal",
                 "Global South Alliance\\x.pdf": "transversal", "Estermic\\proposta.docx": "engineering",
                 "Sistema Physis\\a.md": "engineering", "Instituto Physis\\b.md": "instituto",
                 "Instituto Physis\\InovaSTEM\\c.md": "inovastem", "Marketing Physis\\plano.md": "transversal"}
        for rel, fr in casos.items():
            self.assertEqual(mv_bots.frente_de(D + "\\" + rel), fr, rel)
            self.assertEqual(mv_bots.frente_de("/home/r/Documents/" + rel.replace("\\", "/")), fr, rel)


class Pastas(unittest.TestCase):
    def test_sourh_e_south(self):
        d = Path(tempfile.mkdtemp())
        for n in ("Sistema Physis", "Casa Physis", "Global Sourh Alliance"):
            (d / n).mkdir()
        with mock.patch.object(mv_bots, "DOCS", d):
            nomes = [p.name for p in mv_bots.pastas_documentos()]
            self.assertEqual(nomes, ["Sistema Physis", "Casa Physis", "Instituto Physis", "Global Sourh Alliance", "Estermic"])
            (d / "Global Sourh Alliance").rmdir(); (d / "Global South Alliance").mkdir()
            self.assertIn("Global South Alliance", [p.name for p in mv_bots.pastas_documentos()])

    def test_achar_docs_onedrive_commercial(self):
        base = Path(tempfile.mkdtemp())
        (base / "Documents" / "Sistema Physis").mkdir(parents=True)
        env = {k: v for k, v in os.environ.items() if k != "PHYSIS_DOCS"}
        env["OneDriveCommercial"] = str(base)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(mv_bots.achar_docs(), base / "Documents")
        with mock.patch.dict(os.environ, {"PHYSIS_DOCS": "/x/y"}):
            self.assertEqual(mv_bots.achar_docs(), Path("/x/y"))

    def test_kit_gsa_e_marketing(self):
        self.assertTrue(mv_kit._conta_para("gsa", "Global Sourh Alliance/apresentacao.pptx", "transversal"))
        self.assertFalse(mv_kit._conta_para("gsa", "Marketing Physis/apresentacao.pptx", "transversal"))
        self.assertFalse(mv_kit._conta_para("ecossistema", "Global Sourh Alliance/apresentacao.pptx", "transversal"))
        self.assertTrue(mv_kit._conta_para("casa", "Casa Physis/artigo.docx", "casa"))


class Agenda(unittest.TestCase):
    def test_tr_cabe_no_windows_com_pasta_longa(self):
        with mock.patch.object(mv_cli, "RAIZ_HUB", Path(r"C:\\physis\\physis-ma-20261122-1bd599e\\physis-hub")), \
             mock.patch.object(mv_cli.sys, "executable", r"C:\\Users\\rafae\\AppData\\Local\\Programs\\Python\\Python313\\python.exe"):
            self.assertEqual(mv_cli.tr_longos(), [])
            self.assertIn("bots diario", " ".join(" ".join(c) for c in mv_cli.comandos_agenda()))
        self.assertEqual(mv_cli.expandir(["diario"]), mv_cli.RODADA_DIARIA)
        for b in mv_cli.RODADA_DIARIA:
            self.assertIn(b, mv_bots.BOTS, b)
