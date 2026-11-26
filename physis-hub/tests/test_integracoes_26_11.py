"""Integrações abertas de 26/11/2026: miniPaint (editor de imagem), Flowy (fluxogramas do M&A), Whisper local, páginas de 20,
partes nas telas longas, fornecedores num menu só."""
import re, tempfile, unittest
from pathlib import Path
from physis_hub import mv_fluxogramas, programas_externos as pe
from physis_hub.mv import MV

RAIZ = Path(__file__).resolve().parents[2]


class Integracoes(unittest.TestCase):
    def test_vendor_abertos_com_licenca(self):
        for f in ("vendor/minipaint/index.html", "vendor/minipaint/dist/bundle.js", "vendor/minipaint/LICENSE", "vendor/flowy/flowy.min.js", "vendor/flowy/LICENSE"):
            self.assertTrue((RAIZ / f).is_file(), f)
        self.assertNotRegex((RAIZ / "vendor/minipaint/index.html").read_text(encoding="utf-8"), r"og:image|twitter:image")

    def test_fluxogramas(self):
        mv = MV(":memory:")
        self.assertTrue(mv_fluxogramas.gravar(mv, "Fluxo atual", {"html": "<div></div>", "blocks": []})["ok"])
        self.assertEqual(mv_fluxogramas.ler(mv, "Fluxo atual")["dados"]["blocks"], [])
        self.assertFalse(mv_fluxogramas.gravar(mv, "../x", {})["ok"])

    def test_whisper_receita(self):
        self.assertIn("whisper.transcrever", pe.RECEITAS)
        self.assertIn("faster_whisper", pe.WHISPER_PY)

    def test_paginas_e_partes(self):
        js = (RAIZ / "sistema/physis-paginas.js").read_text(encoding="utf-8")
        self.assertIn("var N = 20", js)
        painel = (RAIZ / "physis-hub/web/painel.html").read_text(encoding="utf-8")
        for k in ('<script id="physis-paginas">', '<script id="pp-partes">', '<script id="pp-referencias">'):
            self.assertIn(k, painel)

    def test_fornecedores_um_menu(self):
        g = (RAIZ / "sistema/gestao-interna-physis.html").read_text(encoding="utf-8")
        self.assertIn('["fornequip", "Fornecedores", null]', g)
        self.assertIn("#gp-m-forn{display:none!important}", g)


if __name__ == "__main__":
    unittest.main()
