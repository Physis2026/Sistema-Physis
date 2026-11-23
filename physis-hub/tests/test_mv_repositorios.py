"""Repositórios fora do sistema (marketing-physis) no M&A: Git só local, documentos e IA Physis."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from physis_hub import ia_physis, mv_bots, mv_repositorios as RP
from physis_hub.mv import MV


@unittest.skipUnless(shutil.which("git"), "sem git")
class Marketing(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp()) / "marketing-physis"
        (self.d / "planilhas").mkdir(parents=True)
        (self.d / "logos").mkdir()
        (self.d / "plano.md").write_text("# Plano de marketing\n\nValidação de dezembro: testar os temas com os clientes iniciais e medir o engajamento orgânico.\n",
                                         encoding="utf-8")
        (self.d / "planilhas" / "metricas.csv").write_text("tema;impressoes\n", encoding="utf-8")
        (self.d / "logos" / "physis.svg").write_text("<svg/>", encoding="utf-8")
        g = lambda *a: subprocess.run(["git", "-C", str(self.d), *a], check=True, capture_output=True,  # noqa: E731
                                      env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})
        subprocess.run(["git", "init", "-q", str(self.d)], check=True)
        g("checkout", "-q", "-b", "main")
        g("add", "-A")
        g("commit", "-q", "-m", "Fase 2: plano, planilhas, validação de dezembro, integrações e logos")
        self.env = mock.patch.dict(os.environ, {"PHYSIS_REPOSITORIOS": json.dumps([{"id": "marketing-physis", "nome": "Marketing Physis",
                                                                                    "caminho": str(self.d), "area": "marketing"}])})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_estado_e_alertas(self):
        mv = MV(":memory:")
        r = mv_bots.BOTS["repositorios"](mv)
        e = r["repositorios"][0]
        self.assertEqual(e["ramo"], "main")
        self.assertIn("validação de dezembro", e["ultimo_commit"]["mensagem"])
        self.assertEqual(e["nao_salvos"], 0)
        self.assertEqual(e["inventario"], {"documentos": 1, "planilhas": 1, "logos_imagens": 1, "dados": 0})
        tipos = {t for (t,) in mv.db.execute("SELECT tipo FROM mv_alerta WHERE bot='repositorios' AND resolvido IS NULL")}
        self.assertEqual(tipos, {"sem_copia"})
        (self.d / "plano.md").write_text("alterado", encoding="utf-8")
        mv_bots.BOTS["repositorios"](mv)
        tipos = {t for (t,) in mv.db.execute("SELECT tipo FROM mv_alerta WHERE bot='repositorios' AND resolvido IS NULL")}
        self.assertIn("nao_salvos", tipos)

    def test_documentos_e_ia(self):
        self.assertIn(self.d, mv_bots._repos())
        self.assertIn(self.d, ia_physis.fontes_padrao()["repositorios"])
        ia = ia_physis.IAPhysis(Path(tempfile.mkdtemp()) / "ia.db")
        ia.indexar({"repositorios": [self.d]})
        r = ia.perguntar("validação de dezembro do marketing")
        self.assertTrue(r["fontes"] and r["fontes"][0]["fonte"].endswith("plano.md"), r)

    def test_ausente_so_avisa(self):
        mv = MV(":memory:")
        with mock.patch.dict(os.environ, {"PHYSIS_REPOSITORIOS": json.dumps([{"id": "x", "caminho": "/nao/existe"}])}):
            mv_bots.BOTS["repositorios"](mv)
        self.assertEqual(mv.db.execute("SELECT gravidade FROM mv_alerta WHERE bot='repositorios'").fetchone()[0], "info")


class PadraoOneDrive(unittest.TestCase):
    def test_acha_marketing_no_onedrive_sem_configurar(self):
        docs = Path(tempfile.mkdtemp()) / "OneDrive - Physis Engineering" / "Documents"
        (docs / "Marketing Physis").mkdir(parents=True)
        with mock.patch.object(mv_bots, "DOCS", docs), mock.patch.dict(os.environ, {"PHYSIS_REPOSITORIOS": ""}), \
                mock.patch.object(mv_bots, "SAIDA", docs / "nada"):
            self.assertEqual(Path(RP.lista()[0]["caminho"]), docs / "Marketing Physis")
            self.assertIn(docs / "Marketing Physis", RP.caminhos_existentes())


if __name__ == "__main__":
    unittest.main()
