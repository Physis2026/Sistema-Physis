"""IA Physis (índice próprio, resposta com fonte, sem inventar), bot cursos e mapa de integrações."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from physis_hub import ia_physis as IA, mv_bots, mv_cli, mv_cursos, mv_integracoes as I
from physis_hub.mv import MV


def base(d: Path) -> dict:
    (d / "a.md").write_text("# Água\n\nNa água, nenhum limite vem de fábrica, e limite provisório não gera alerta nenhum na plataforma.\n", encoding="utf-8")
    (d / "b.md").write_text("# Energia solar\n\nO dimensionamento de energia solar usa a irradiação do local e a planta solar com strings e inversores.\n"
                            "\n## Curso\n\nTrilha de energia solar para técnicos: irradiação, módulos, inversores e segurança elétrica.\n", encoding="utf-8")
    (d / "c.md").write_text("# Oficina\n\nOficina prática de energia solar com montagem de módulos e inversores em bancada.\n", encoding="utf-8")
    return {"t": [d]}


class IAPhysisTeste(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.ia = IA.IAPhysis(self.d / "ia.db")
        self.r = self.ia.indexar(base(self.d))

    def test_responde_com_fonte(self):
        r = self.ia.perguntar("limite de água de fábrica")
        self.assertIn("nenhum limite vem de fábrica", r["resposta"])
        self.assertTrue(r["fontes"] and r["fontes"][0]["fonte"].endswith("a.md"))
        self.assertTrue(r["revisao_humana"])

    def test_nao_inventa(self):
        r = self.ia.perguntar("preço do bitcoin")
        self.assertEqual(r["fontes"], [])
        self.assertTrue(r["resposta"].startswith("Não encontrei"))

    def test_incremental_e_remocao(self):
        self.assertEqual(self.r["atualizados"], 3)
        self.assertEqual(self.ia.indexar(base(self.d))["atualizados"], 0)
        (self.d / "c.md").unlink()
        self.assertEqual(self.ia.indexar({"t": [self.d]})["removidos"], 1)

    def test_tabela_vira_frase(self):
        p = self.d / "t.md"
        p.write_text("# Robôs\n\n| Robô | O que faz |\n|---|---|\n| marketing | Aprende quais temas engajam mais nas redes sociais da Physis |\n",
                     encoding="utf-8")
        self.ia.indexar({"t": [self.d]})
        r = self.ia.perguntar("o que o robô marketing faz com temas")
        self.assertIn("engajam", r["resposta"])

    def test_temas(self):
        t = self.ia.temas([str(self.d)], min_docs=2)
        nomes = [x["tema"] for x in t]
        self.assertTrue(any("solar" in n or "inversores" in n for n in nomes), nomes)


class Cursos(unittest.TestCase):
    def test_mapa_e_rechecagem(self):
        d = Path(tempfile.mkdtemp())
        base(d)
        mv = MV(":memory:")
        ia = IA.IAPhysis(d / "ia.db")
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"PHYSIS_CURSOS_PASTAS": json.dumps({"InovaSTEM": [str(d)], "Instituto Physis": [str(d / "nada")]})}):
            r = mv_cursos.bot_cursos(mv, ia, date(2026, 11, 22), d / "saida")
            r2 = mv_cursos.bot_cursos(mv, ia, date(2026, 12, 1), d / "saida")
        self.assertTrue(r["fase"].startswith("mapeamento"))
        self.assertTrue(r2["fase"].startswith("trilhas ativas"))
        self.assertGreater(r["temas_novos"], 0)
        self.assertEqual(r2["temas_novos"], 0)             # não repete o mesmo tema
        self.assertTrue((d / "saida" / "mapa-de-cursos.json").is_file())
        self.assertIn("sem_pasta:Instituto Physis", {r[0] for r in mv.db.execute("SELECT tipo||':'||ref FROM mv_alerta WHERE resolvido IS NULL")})


class Integracoes(unittest.TestCase):
    def test_consistente(self):
        ids = {n[0] for n in I.NOS}
        self.assertEqual(len(ids), len(I.NOS))
        for a in I.ARESTAS:
            self.assertIn(a[0], ids)
            self.assertIn(a[1], ids)
        for no, bot in I.BOT_DO_NO.items():
            self.assertIn(no, ids)
            self.assertIn(bot, mv_bots.BOTS)
        for b in mv_bots.BOTS:                              # todo bot do M&A aparece no mapa
            self.assertIn(b, I.BOT_DO_NO.values())
        for p in ("inovastem_plat", "physis3d", "cursos_plat", "r_marketing", "quantica", "ia_physis"):
            self.assertIn(p, ids)
        e = I.estado(MV(":memory:"))
        self.assertEqual(e["estado"]["b_vigia"]["estado"], "parado")

    def test_ia_e_cursos_na_agenda(self):
        agenda = mv_cli.texto_agenda()
        for b in ("ia", "cursos"):
            self.assertIn(b, agenda)


if __name__ == "__main__":
    unittest.main()
