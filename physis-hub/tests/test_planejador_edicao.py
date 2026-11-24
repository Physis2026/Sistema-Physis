"""Casa Physis: Planejador sempre na edição completa, sem ativação de licença (decisão da dona de 24/11/2026)."""
import shutil
import tempfile
import unittest
from pathlib import Path

import montar

PLAN = Path(__file__).resolve().parents[2] / "modulos" / "planejador" / "planejador-physis.html"


class EdicaoCompleta(unittest.TestCase):
    def test_planejador_tem_edicao_completa(self):
        t = PLAN.read_text(encoding="utf-8")
        self.assertIn("completa()", t)
        self.assertIn("if (!LIC.completa()) el.append(card('Licença'", t)
        self.assertIn("origem: 'edição completa'", t)

    def test_marcacao_uma_vez(self):
        d = Path(tempfile.mkdtemp()) / "planejador.html"
        shutil.copy(PLAN, d)
        montar.edicao_completa(d)
        montar.edicao_completa(d)
        t = d.read_text(encoding="utf-8")
        self.assertEqual(t.count('data-edicao="completa"'), 1)
        self.assertTrue(t.startswith('<!doctype html><html data-edicao="completa"'))

    def test_montar_casa_usa_edicao_completa(self):
        self.assertIn('org.startswith("casa-physis")', (Path(montar.__file__)).read_text(encoding="utf-8"))
