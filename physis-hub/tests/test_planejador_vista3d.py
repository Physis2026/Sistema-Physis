"""Planejador · módulo Profissional "Vista 3D do terreno e das massas" (versão de TESTE, 22/11/2026).

Protege:
1. O módulo existe e está disponível no plano Profissional; saiu do catálogo de planejados (sem registro duplo).
2. Altura sem número inventado (decisão da dona, M&A pg:99df166fe3f6): a do item (alt); sem ela, pé-direito do projeto
   × pavimentos; sem os dois, placa de desenho de 0,20 m com aviso. O pé-direito padrão é vazio.
3. Edição direta (decisão pg:4bd340f67b73): clicar seleciona, arrastar move, altura/giro/cota na ficha e no teclado;
   tudo por mutate (Desfazer). Sol por SOL.pos do núcleo; terreno pela grade do núcleo (T.build).
4. Acessível (regra 5): rótulos nos campos, teclado, nome no canvas; cores da PALETA.md (regra 6).
5. Correção do laço: run() chama as verificações dos módulos antes de existir CALC; MOD.res recebe o resultado R e não
   chama run() de novo (antes, com a página de módulos aberta, qualquer mudança travava o Planejador).
"""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PLANEJADOR = RAIZ / "modulos" / "planejador" / "planejador-physis.html"
PALETA = RAIZ / "physis-hub" / "docs" / "PALETA.md"


class Vista3D(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = PLANEJADOR.read_text(encoding="utf-8")
        i = cls.src.index("// Módulo Profissional · Vista 3D do terreno e das massas")
        cls.mod = cls.src[i:cls.src.index("// Catálogo de módulos planejados", i)]

    def test_registrado_disponivel_profissional(self):
        self.assertIn("id: 'vista3d', nome: 'Vista 3D do terreno e das massas', plano: 'profissional', estado: 'disponível'", self.mod)
        self.assertEqual(self.src.count("id: 'vista3d'"), 1)  # um registro só
        cat = self.src[self.src.index("// Catálogo de módulos planejados"):]
        cat = cat[:cat.index("].forEach(")]
        self.assertNotIn("'vista3d'", cat)
        self.assertIn("SPDX-License-Identifier: BUSL-1.1", self.src[self.src.index("// Módulo Profissional · Vista 3D") - 40:][:80])

    def test_altura_sem_numero_inventado(self):
        self.assertIn("padrao: { pd: null, dia: 172, hora: 10 }", self.mod)
        self.assertIn("if (it.alt != null) return { h: +it.alt", self.mod)
        self.assertIn("p.pd * (it.pav || 1)", self.mod)
        self.assertIn("const V3D_PLACA = 0.2;", self.mod)
        self.assertIn("informe a altura", self.mod)
        self.assertIn("pg:99df166fe3f6", self.mod)

    def test_edicao_por_mutate_e_teclado(self):
        self.assertIn("pg:4bd340f67b73", self.mod)
        self.assertIn("movido na vista 3D", self.mod)
        for tecla in ("ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "'+'", "'-'", "q:", "e:"):
            self.assertIn(tecla, self.mod)
        self.assertGreaterEqual(self.mod.count("mutate("), 5)
        self.assertIn("SOL.pos(", self.mod)
        self.assertIn("const g = T.build()", self.mod)
        self.assertIn("VENDOR.temServidor()", self.mod)
        self.assertIn("toDataURL('image/png')", self.mod)  # baixar imagem

    def test_acessivel_e_paleta(self):
        self.assertIn("'aria-label': 'Vista 3D do terreno e das massas", self.mod)
        self.assertIn("tabindex: 0", self.mod)
        self.assertIn("'aria-label': 'Escolher a massa para editar'", self.mod)
        self.assertIn("h('label', { for: id }, rot)", self.mod)
        paleta = {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}", PALETA.read_text(encoding="utf-8"))}
        for hexa in re.findall(r"0x([0-9A-Fa-f]{6})", self.mod):
            if hexa.upper() in ("FFFFFF", "8A7F63"):  # luz branca e cor do chão da luz hemisférica (não é cor de tela)
                continue
            self.assertIn("#" + hexa.upper(), paleta, hexa)

    def test_sem_laco_nas_verificacoes(self):
        self.assertIn("res(id, R) {", self.src)
        self.assertIn("if (R && !CALC) { try { return m.calcular(R, MOD.p(id)); }", self.src)
        self.assertIn("const r = MOD.res(m.id, R);\n      if (r && !r.erro) m.verificar(r, C, R);", self.src)
        self.assertIn("MOD.verificar(R,C);", self.src)  # chamado antes de CALC=R: por isso o R vai junto


if __name__ == "__main__":
    unittest.main()
