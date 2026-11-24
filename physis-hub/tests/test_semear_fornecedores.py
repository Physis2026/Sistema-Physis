"""Fabricantes de AVAC e instalações na planilha de equipamentos, só da base interna (24/11/2026)."""
import importlib.util
import json
import unittest
from pathlib import Path

from physis_hub.fornecedores import CATEGORIAS, SEGMENTO_CATEGORIA, Fornecedores
from physis_hub.hub import Hub

RAIZ = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("semear", RAIZ / "ferramentas" / "semear_fornecedores.py")
sm = importlib.util.module_from_spec(spec); spec.loader.exec_module(sm)


class Semear(unittest.TestCase):
    def test_marcas_sem_inventar_modelo(self):
        base = json.loads((RAIZ / "sistema" / "physis-equipamentos.json").read_text(encoding="utf-8"))
        f = Fornecedores(Hub(org="sem-forn"))
        r = sm.semear(f, base)
        self.assertGreater(r["marcas"], 50)
        self.assertEqual(r["pulados"], [])
        self.assertTrue(set(SEGMENTO_CATEGORIA.values()) <= set(CATEGORIAS))
        linhas = f._db.execute("SELECT categoria, marca, modelo FROM fornecedor_equipamento").fetchall()
        self.assertTrue(all(m == "" for _, _, m in linhas), "modelo comercial vazio até a cotação")
        self.assertEqual(sm.semear(f, base)["marcas"], r["marcas"])      # rodar de novo não duplica (upsert)
        self.assertEqual(len(f._db.execute("SELECT id FROM fornecedor_equipamento").fetchall()), len(linhas))
