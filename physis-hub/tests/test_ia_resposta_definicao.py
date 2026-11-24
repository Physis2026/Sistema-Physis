"""IA Physis: definição oficial na frente de listas de arquivos e de versões de teste; índice refeito quando a leitura muda."""
import tempfile
import unittest
from pathlib import Path

from physis_hub import ia_physis


class Definicao(unittest.TestCase):
    def test_missao_oficial(self):
        d = Path(tempfile.mkdtemp())
        (d / "oficial").mkdir()
        (d / "Revisao_TESTE").mkdir()
        (d / "oficial" / "41_Mapa.md").write_text("# Missão\n\nMissão: levar engenharia sustentável e acessível a quem produz no campo e na cidade.\n", encoding="utf-8")
        (d / "Revisao_TESTE" / "LEIA-ME.md").write_text("# Revisão da missão\n\nFontes da missão: Missao_v1_TESTE.odt, Missao_v1_TESTE.pdf e Missao_v2_TESTE.odt recomendadas na revisão da missão.\n"
                                                    "A missão foi discutida nas reuniões de novembro com a equipe toda da Physis.\n", encoding="utf-8")
        ia = ia_physis.IAPhysis(d / "ia.db")
        ia.indexar({"documentos": [d]})
        r = ia.perguntar("qual é a missão da Physis")
        self.assertTrue(r["resposta"].startswith("Missão: levar engenharia"), r["resposta"])
        self.assertNotIn(".odt", r["resposta"])

    def test_versao_nova_refaz_indice(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.md").write_text("# A\n\nTexto de teste com bastante palavras para virar trecho.\n", encoding="utf-8")
        ia = ia_physis.IAPhysis(d / "ia.db")
        self.assertEqual(ia.indexar({"documentos": [d]})["atualizados"], 1)
        self.assertEqual(ia.indexar({"documentos": [d]})["atualizados"], 0)
        ia.db.execute("UPDATE ia_meta SET valor='antiga'")
        self.assertEqual(ia.indexar({"documentos": [d]})["atualizados"], 1)
        self.assertEqual(ia.indexar({"documentos": [d]}, refazer=True)["atualizados"], 1)
