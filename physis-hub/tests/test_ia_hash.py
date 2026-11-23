"""Linhas de SHA256 não entram no índice da IA Physis (resposta da missão vinha com hashes, 23/11/2026)."""
import unittest

from physis_hub import ia_physis


class SemHash(unittest.TestCase):
    def test_linha_de_hash_sai(self):
        t = ("# Missão\n\nA missão da Physis é levar engenharia sustentável a quem produz no campo.\n"
             "d855eff5d6c9489adeed1763b94d3ca7b1ab3d6df0da91bfb4c40de117bf339c Missao_v1_TESTE.odt arquivo de teste da missão\n")
        txt = " ".join(x for _, x in ia_physis.trechos(t))
        self.assertIn("engenharia sustentável", txt)
        self.assertNotIn("d855eff5", txt)
