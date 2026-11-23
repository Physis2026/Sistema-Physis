"""Bots que vieram do GitHub em 22/11/2026 (desenvolvimento e sincronização), ligados ao M&A: rodam sem quebrar fora do servidor."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from physis_hub import mv_bots, mv_desenvolvimento, mv_sincronizacao
from physis_hub.mv import MV


class Desenvolvimento(unittest.TestCase):
    def test_grava_painel(self):
        mv = MV(":memory:")
        raiz = Path(tempfile.mkdtemp())
        (raiz / "sistema").mkdir()
        r = mv_desenvolvimento.gravar(mv, raiz)
        self.assertTrue((raiz / "sistema" / "desenvolvimento-dados.js").is_file(), r)
        self.assertIn("desenvolvimento", mv_bots.BOTS)


class Sincronizacao(unittest.TestCase):
    def test_sem_repositorios_nao_quebra_nem_commita(self):
        mv = MV(":memory:")
        base = Path(tempfile.mkdtemp())
        with mock.patch.object(mv_sincronizacao, "REPOS", {"Sistema Physis (oficial)": base / "nao-existe"}), \
                mock.patch.object(mv_sincronizacao, "PLATAFORMAS", base / "nada"):
            r = mv_sincronizacao.rodar(mv, aplicar=False)
        self.assertIsInstance(r, dict)
        self.assertIn("sincronizacao", mv_bots.BOTS)


@unittest.skipUnless(__import__("shutil").which("git"), "sem git")
class CommitSemIdentidade(unittest.TestCase):
    def test_commit_com_identidade_do_bot(self):
        import os, subprocess
        d = Path(tempfile.mkdtemp())
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update({"HOME": str(d), "GIT_CONFIG_NOSYSTEM": "1", "XDG_CONFIG_HOME": str(d)})      # Git sem nome/e-mail
        subprocess.run(["git", "init", "-q", str(d / "r")], check=True, env=env)
        (d / "r" / "a.txt").write_text("1")
        with mock.patch.dict(os.environ, env, clear=True):
            r = mv_sincronizacao._git(d / "r", "config", "user.email").stdout.strip()
            self.assertEqual(r, b"")
            ident = ["-c", "user.name=Physis M&A (sincronização)", "-c", "user.email=ma@physis.local"]
            subprocess.run(["git", "-C", str(d / "r"), "add", "-A"], check=True)
            c = subprocess.run(["git", *ident, "-C", str(d / "r"), "commit", "-q", "-m", "x"], capture_output=True)
        self.assertEqual(c.returncode, 0, c.stderr)
        self.assertIn("ma@physis.local", subprocess.run(["git", "-C", str(d / "r"), "log", "-1", "--format=%ae"], capture_output=True, text=True).stdout)


if __name__ == "__main__":
    unittest.main()
