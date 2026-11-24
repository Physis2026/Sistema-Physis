"""Aba Net zero do Planejador (VERSÃO DE TESTE, 22/11/2026; decisão da dona M&A pg:b880e775e565).

Protege: as quatro partes, uma por plano (Livre, Profissional, Especialista, Empresa); a cópia igual dentro do Planejador
(sincronizar.py) depois do núcleo; a aba no lugar certo (antes do Documento EP) e fora da aba Módulos; norte sempre
indicado (rosa NP/NV, [MARCADOR] sem norte verdadeiro); mesma regra de pressão do núcleo (40 m, NBR 5626); sem internet;
só cores da paleta; inglês dos textos fixos.
"""
import json
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MOD = RAIZ / "sistema" / "planejador-netzero.js"
PLAN = RAIZ / "modulos" / "planejador" / "planejador-physis.html"
PALETA = RAIZ / "physis-hub" / "docs" / "PALETA.md"
NO_REPO = MOD.is_file() and PLAN.is_file()
ler = lambda p: p.read_text(encoding="utf-8")


@unittest.skipUnless(NO_REPO, "só no repositório")
class AbaNetZero(unittest.TestCase):
    def test_uma_parte_por_plano(self):
        m = ler(MOD)
        achados = dict(re.findall(r'id: "(nz_\w+)", aba: "netzero", nome: "[^"]+", plano: "(\w+)"', m))
        self.assertEqual(achados, {"nz_livre": "livre", "nz_prof": "profissional", "nz_esp": "especialista", "nz_emp": "empresa"})

    def test_copia_igual_depois_do_nucleo(self):
        p = ler(PLAN)
        abre = '<script id="planejador-netzero">\n'
        i = p.index(abre)
        self.assertEqual(p[i + len(abre):p.index("</script>", i)], ler(MOD).replace("\r\n", "\n"))
        self.assertLess(p.index("\ninit();\n"), i, "o bloco vem depois do núcleo (registra a aba e chama route())")

    def test_aba_antes_do_documento_e_fora_de_modulos(self):
        m, p = ler(MOD), ler(PLAN)
        self.assertIn('s[0] === "documento"', m)
        self.assertIn('["netzero", "Net zero"]', m)
        self.assertIn("if (m.estado !== 'disponível' || m.aba) continue;", p)

    def test_norte_sempre_indicado(self):
        m = ler(MOD)
        for t in ("NP", "NV?", "Norte verdadeiro não informado: [MARCADOR]", "norteVerdadeiro"):
            self.assertIn(t, m)

    def test_mesma_regra_de_pressao_do_nucleo(self):
        self.assertIn("LIMITE_PRESSAO_M = 40", ler(MOD))
        self.assertIn("desnível acima de 40 m: válvulas redutoras de pressão (NBR 5626)", ler(PLAN))

    def test_sem_internet_e_so_paleta(self):
        m = ler(MOD).replace("http://www.w3.org/2000/svg", "")
        self.assertNotRegex(m, r"https?://")
        paleta = {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}", ler(PALETA))}
        self.assertFalse({c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}\b", m)} - paleta)

    def test_ingles_dos_textos_fixos(self):
        p = ler(PLAN)
        for t in ("Net zero · essencial", "Guardar a planta atual como variante", "Item sem lugar", "Nota mínima de aptidão"):
            self.assertIn(json.dumps(t, ensure_ascii=False) + ":", p)


if __name__ == "__main__":
    unittest.main()
