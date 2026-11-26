"""Regressão de 26/11/2026 (pedidos da dona): aba Quadros elétricos visível, logo própria da Casa Physis no tema escuro e no
fundo verde, Turbinas ligada ao GIS e ao BIM e kits de revisão por pessoa."""
import json, re, unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PAINEL = (RAIZ / "physis-hub" / "web" / "painel.html").read_text(encoding="utf-8")


class Regressao(unittest.TestCase):
    def test_quadros_tem_regra_de_visibilidade(self):
        i = PAINEL.index("const abasAtivas = ()")
        self.assertIn("quadros: emPesquisa()", PAINEL[i:i + 1500])   # sem a chave, a aba nunca aparecia

    def test_logo_propria_nas_duas_imagens(self):
        i = PAINEL.index("function logoMarca()")
        trecho = PAINEL[i:i + 1500]
        self.assertIn("querySelectorAll(\".px-faixa .px-id img\")", trecho)
        self.assertIn("logo-escura", trecho)

    def test_turbinas_liga_gis_e_bim(self):
        js = (RAIZ / "sistema" / "physis-turbinas.js").read_text(encoding="utf-8")
        for t in ('data-ir="mapeamento"', 'data-ir="planejador"', "Lugar e modelo (GIS e BIM)"):
            self.assertIn(t, js); self.assertIn(t, PAINEL)

    def test_kits_tem_responsaveis_e_quadros(self):
        mods = json.loads((RAIZ / "ferramentas" / "kits" / "modulos.json").read_text(encoding="utf-8"))["modulos"]
        q = next(m for m in mods if m["id"] == "quadros")
        self.assertEqual(q["responsaveis"], ["Erick Lopes"])                 # decisão da dona, 26/11/2026
        self.assertIn("sistema/physis-quadros.js", q["referencia"])
        self.assertTrue((RAIZ / "ferramentas" / "kits_por_pessoa.py").is_file())

    def test_arquivos_do_projeto_no_inicio(self):
        i = PAINEL.index("function telaPerfil(d)")
        self.assertIn("entradaProjeto(p)", PAINEL[i:i + 1500])        # primeira coisa do Início, antes do perfil
        for t in ('id="in-entrada"', ".ifc", "data-entrada-levar", "#mp-ifc", "#mp-arquivo", 'if (t.id === "in-entrada")'):
            self.assertIn(t, PAINEL)


if __name__ == "__main__":
    unittest.main()
