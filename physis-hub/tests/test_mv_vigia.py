"""Vigia dos bots e sentinela (physis_hub/mv_vigia.py)."""
import tempfile
import time
import unittest
from pathlib import Path

from physis_hub import mv_bots, mv_vigia
from physis_hub.mv import MV


def abertos(mv, bot):
    return {r[0] for r in mv.db.execute("SELECT tipo||':'||ref FROM mv_alerta WHERE bot=? AND resolvido IS NULL", (bot,))}


class Vigia(unittest.TestCase):
    def test_parado_erro_e_fecha_sozinho(self):
        mv = MV(":memory:")
        lim = {"atrasos": 2, "resumo": 26, "links": 26}
        agora = time.time()
        mv.registrar_execucao("atrasos", agora - 3 * 3600)
        mv.db.execute("UPDATE mv_execucao SET fim=? WHERE bot='atrasos'", (agora - 3 * 3600,))
        mv.registrar_execucao("resumo", agora - 60, "", "ValueError()")
        r = mv_vigia.bot_vigia(mv, agora, lim)
        self.assertEqual(r["atrasos"]["estado"], "parado")
        self.assertEqual(r["resumo"]["estado"], "erro")
        self.assertIsNone(r["links"]["idade_h"])
        self.assertIn("bot_com_erro:resumo", abertos(mv, "vigia"))
        for b in lim:
            mv.registrar_execucao(b, time.time())
        mv_vigia.bot_vigia(mv, time.time() + 1, lim)
        self.assertEqual(abertos(mv, "vigia"), set())

    def test_registrado_em_BOTS(self):
        self.assertIn("vigia", mv_bots.BOTS)
        self.assertIn("sentinela", mv_bots.BOTS)


class Sentinela(unittest.TestCase):
    def test_falha_aviso_e_conteiner(self):
        mv = MV(":memory:")
        raiz = Path(tempfile.mkdtemp())
        (raiz / "implantacao").mkdir()
        (raiz / "implantacao" / "verificar.sh").write_text("")
        (raiz / "servicos").mkdir()
        (raiz / "servicos" / "docker-compose.yml").write_text("")

        def falso(cmd, timeout=120):
            if cmd[0] == "docker":
                return 0, '{"Service":"hub","State":"running"}\n{"Service":"calc","State":"exited"}\n'
            return 1, "  [ OK  ] a\n  [FALHA] porta 8700 não responde\n  [AVISO] disco 85%\n"
        r = mv_vigia.bot_sentinela(mv, falso, raiz, which=lambda n: "/x/" + n)
        self.assertEqual(r["conteineres"], {"total": 2, "com_problema": 1})
        self.assertEqual((r["falhas"], r["avisos"]), (2, 1))
        self.assertIn("conteiner:calc", abertos(mv, "sentinela"))


class Carencia(unittest.TestCase):
    def test_bot_novo_aguarda_e_erro_continua_aparecendo(self):
        mv = MV(":memory:")
        agora = time.time()
        mv.registrar_execucao("atrasos", agora - 60)
        r = mv_vigia.bot_vigia(mv, agora, {"atrasos": 2, "semanal": 174})
        self.assertEqual(r["semanal"]["estado"], "aguardando 1ª rodada")       # instalado há 1 min: sem alarme
        r = mv_vigia.bot_vigia(mv, agora + 200 * 3600, {"semanal": 174})
        self.assertEqual(r["semanal"]["estado"], "parado")                      # passou do prazo: cobra


if __name__ == "__main__":
    unittest.main()
