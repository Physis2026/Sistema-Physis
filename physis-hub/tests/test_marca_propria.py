"""Marca própria da instalação (Casa Physis inicial, 20/11/2026): ficha → montar.py → instancia.json → painel."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AQUI))

import montar  # noqa: E402
import montar_clientes  # noqa: E402


class MarcaPropria(unittest.TestCase):
    def ficha(self) -> dict:
        base = json.loads(montar_clientes.FICHAS.read_text(encoding="utf-8"))
        return next(f for f in base["clientes"] if f["org"] == "casa-physis-inicial")

    def test_ficha_casa_physis_inicial(self):
        f = self.ficha()
        self.assertTrue(f["pesquisa"])
        self.assertFalse(f.get("gestao_interna"))          # Gestão interna é da Physis Engineering, não da Casa
        m = montar_clientes.marca_da_ficha(f)
        for tom in ("clara", "escura"):
            self.assertTrue(Path(m[f"logo_{tom}"]).is_file(), tom)
        self.assertNotIn("_leia", m)
        # a versão de pesquisa continua ao lado, sem marca própria
        base = json.loads(montar_clientes.FICHAS.read_text(encoding="utf-8"))
        pesq = next(x for x in base["clientes"] if x["org"] == "casa-physis")
        self.assertIsNone(montar_clientes.marca_da_ficha(pesq))

    def test_montar_leva_logos_e_marca(self):
        m = montar_clientes.marca_da_ficha(self.ficha())
        with tempfile.TemporaryDirectory() as tmp:
            montar.montar("casa-teste", "lote-168", ["monitoramento"], Path(tmp), None, montar.LICENCA_PADRAO, marca=m)
            pasta = Path(tmp) / "physis-casa-teste"
            inst = json.loads((pasta / "instancia.json").read_text(encoding="utf-8"))
            self.assertEqual(inst["instalacao"], "casa-teste")
            self.assertEqual(inst["marca"]["nome"], "Casa Physis")
            self.assertEqual(inst["marca"]["logo_clara"], "/marca/logo-clara.svg")
            self.assertTrue((pasta / "web" / "marca" / "logo-escura.svg").is_file())

    def test_sem_marca_nada_muda(self):
        with tempfile.TemporaryDirectory() as tmp:
            montar.montar("sem-marca", "lugar01", [], Path(tmp), None, montar.LICENCA_PADRAO)
            pasta = Path(tmp) / "physis-sem-marca"
            inst = json.loads((pasta / "instancia.json").read_text(encoding="utf-8"))
            self.assertNotIn("marca", inst)
            self.assertFalse((pasta / "web" / "marca").exists())

    def test_painel_troca_logo_pelo_tema(self):
        html = (AQUI / "web" / "painel.html").read_text(encoding="utf-8")
        self.assertIn("function logoMarca()", html)
        self.assertIn('attributeFilter: ["data-tema"]', html)
        self.assertIn('/^\\/marca\\/logo-(clara|escura)\\.svg$/', html)


if __name__ == "__main__":
    unittest.main()
