"""Edição manual de textos e da ordem dos blocos (24/11/2026): módulo único, só com conta, grava pela rota da direção."""
import re
import unittest
from pathlib import Path

from physis_hub.hub import Hub

RAIZ = Path(__file__).resolve().parents[2]


class Edicao(unittest.TestCase):
    def test_modulo_nas_paginas(self):
        js = (RAIZ / "sistema" / "physis-edicao.js").read_text(encoding="utf-8")
        for p in ("painel.html", "municipio.html"):
            self.assertIn(js, (RAIZ / "physis-hub" / "web" / p).read_text(encoding="utf-8"), p)
        self.assertIn("data-edicao-propria", (RAIZ / "physis-hub" / "web" / "consultoria.html").read_text(encoding="utf-8")[:200])
        self.assertIn('fetch("/api/instancia"', js)
        cores = set(re.findall(r"#[0-9A-Fa-f]{6}", js))
        paleta = (RAIZ / "physis-hub" / "docs" / "PALETA.md").read_text(encoding="utf-8").upper()
        for c in cores:
            self.assertIn(c.upper(), paleta, c)

    def test_chaves_aceitas_pelo_servidor(self):
        h = Hub(org="ed-teste")
        r = h.site_gravar("ed-inicio", {"t.1jdp24e": "Texto novo", "layout.ordem": "b.119841j,b.2m8fce", "layout.ocultos": ""}, "dona")
        self.assertTrue(r["ok"], r)
        self.assertEqual(h.site_textos("ed-inicio")["textos"]["t.1jdp24e"], "Texto novo")
