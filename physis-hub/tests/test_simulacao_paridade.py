"""Paridade Python × navegador das simulações, nos casos comuns de sistema/simulacao-exemplos/.

O Python não roda JavaScript (sem Node no hub). A paridade fecha assim:
1. este teste regera os casos na memória e confere que casos.json, casos.js e o bloco de premissas dentro de
   sistema/physis-simulacao.js estão em dia (os valores "python" gravados são os que o Python calcula hoje);
2. confere aqui as soluções analíticas de cada caso (benchmarks);
3. a página ferramentas/testes-navegador/conferir-simulacao.html roda os MESMOS casos no navegador com
   physis-simulacao.js e compara com os valores "python" (tolerância relativa 1e-7) e com os analíticos;
   ela precisa mostrar "TUDO OK" (título da página "OK") — conferido em 15/11/2026, 156 valores;
4. confere o contrato do módulo da tela (sem internet, nomes exportados, todo solver dos casos tratado no JS,
   exemplos marcados como fictícios).
"""
import json
import re
import unittest
from pathlib import Path

from physis_hub.simulacao import casos

RAIZ = Path(__file__).resolve().parents[2]
JS = RAIZ / "sistema" / "physis-simulacao.js"
PAG = RAIZ / "ferramentas" / "testes-navegador" / "conferir-simulacao.html"


def _igual(v, esp, rel=0.0, ab=0.0):
    if isinstance(esp, bool) or esp is None or isinstance(esp, str):
        return v == esp
    if isinstance(esp, (int, float)):
        return isinstance(v, (int, float)) and abs(v - esp) <= ab + rel * abs(esp)
    if isinstance(esp, list):
        return isinstance(v, list) and len(v) == len(esp) and all(_igual(a, b, rel, ab) for a, b in zip(v, esp))
    if isinstance(esp, dict):
        return isinstance(v, dict) and all(_igual(v.get(k), x, rel, ab) for k, x in esp.items())
    return v == esp


class Arquivos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.j, cls.js, cls.bloco = casos.textos()

    def test_casos_em_dia(self):
        # Compara por valor, não por texto: o último dígito de um float muda entre Windows e Linux (CI, D22)
        # e resíduos numéricos perto de zero (~1e-10) variam com a ordem das operações. Tolerância bem abaixo
        # da usada pela página do navegador; estrutura, textos, booleanos e tamanhos continuam exatos.
        msg = "rode: python -m physis_hub.simulacao.casos --gravar"
        def conferir(gravado, atual):
            self.assertTrue(_igual(atual, gravado, 1e-9, 1e-8) and _igual(gravado, atual, 1e-9, 1e-8), msg)
        conferir(json.loads((casos.PASTA / "casos.json").read_text(encoding="utf-8")), json.loads(self.j))
        def do_js(t):
            return json.loads(t[t.index("{"):t.rindex("}") + 1].replace("<\\/", "</"))
        conferir(do_js((casos.PASTA / "casos.js").read_text(encoding="utf-8")), do_js(self.js))

    def test_premissas_copiadas_no_js(self):
        t = JS.read_text(encoding="utf-8")
        self.assertIn(self.bloco, t, "premissas do JS desatualizadas: rode casos --gravar")

    def test_exemplos_pedidos_existem_e_sao_ficticios(self):
        d = json.loads(self.j)
        ids = {c["id"] for c in d["casos"]}
        for pedido in ("ex_parede_taipa_u", "ex_parede_taipa_transiente", "ex_rack_solar", "ex_torre_turbina",
                       "ex_terreno_d8", "ex_terreno_scs", "ex_ventilacao_secador", "ex_lbm", "ex_monte_carlo_solar",
                       "ex_qubo_paineis", "ex_biogas_bovino", "ex_biogas_ambiente"):
            self.assertIn(pedido, ids)
        for c in d["casos"]:
            if c["exemplo"]:
                self.assertTrue(c["descricao"].startswith(casos.FICTICIO), c["id"])

    def test_benchmarks_pedidos_existem(self):
        ids = {c["id"] for c in json.loads(self.j)["casos"]}
        for b in ("bench_decaimento_1d", "bench_placa_quadrada", "bench_viga_balanco", "bench_trelica", "bench_euler", "bench_cst_patch",
                  "bench_d8_plano", "bench_scs", "bench_lbm_conservacao", "bench_mc_media", "bench_qubo_rota", "bench_biogas_manual",
                  "bench_biogas_trh_longo", "bench_fatores_carbono"):
            self.assertIn(b, ids)


class Analiticos(unittest.TestCase):
    def test_cada_caso_confere_no_python(self):
        d = json.loads((casos.PASTA / "casos.json").read_text(encoding="utf-8"))
        n = 0
        for c in d["casos"]:
            if c.get("so_navegador"):
                continue
            r = casos.rodar_caso(c)
            for a in c["analitico"]:
                v = casos.pega(r, a["caminho"])
                if "contem" in a:
                    self.assertIn(a["contem"], json.dumps(v, ensure_ascii=False), f"{c['id']}: {a['nome']}")
                else:
                    self.assertTrue(_igual(v, a["valor"], a.get("tol_rel", 0.0), a.get("tol_abs", 0.0)), f"{c['id']}: {a['nome']} → {v} × {a['valor']}")
                n += 1
        self.assertGreater(n, 30)


class ContratoJS(unittest.TestCase):
    def setUp(self):
        self.t = JS.read_text(encoding="utf-8")

    def test_sem_internet_e_exporta(self):
        self.assertIsNone(re.search(r"\bfetch\(|XMLHttpRequest|https?://", self.t))
        for nome in ("global.SIMULACAO =", "global.telaSimulacao", "global.SIMULACAO_I18N", "painel:", "autoteste:", "biogas:", "qubo:"):
            self.assertIn(nome, self.t)
        self.assertEqual(self.t.count("<h1>"), 1)

    def test_todo_solver_dos_casos_tem_espelho(self):
        d = json.loads((casos.PASTA / "casos.json").read_text(encoding="utf-8"))
        for s in {c["solver"] for c in d["casos"]}:
            self.assertIn(f'case "{s}"', self.t, s)

    def test_cores_da_paleta(self):
        pal = set(re.findall(r"#[0-9A-F]{6}", (RAIZ / "physis-hub" / "docs" / "PALETA.md").read_text(encoding="utf-8")))
        usadas = set(c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}\b", self.t))
        self.assertFalse(usadas - pal, f"cores fora da paleta: {usadas - pal}")

    def test_pagina_de_conferencia(self):
        p = PAG.read_text(encoding="utf-8")
        for s in ("physis-simulacao.js", "simulacao-exemplos/casos.js", "physis-turbinas.js", "SIMULACAO.autoteste()", 'lang="pt-BR"'):
            self.assertIn(s, p)


class Integracao(unittest.TestCase):
    def test_patch_de_variaveis_e_premissas(self):
        from physis_hub.simulacao import integracao
        p = integracao.variaveis_patch()
        atuais = json.loads((RAIZ / "sistema" / "physis-variaveis.json").read_text(encoding="utf-8"))
        ids_atuais = {v["id"] for v in atuais["variaveis"]}
        novos = [v["id"] for v in p["variaveis_acrescentar"]]
        self.assertEqual(len(novos), len(set(novos)))
        # já juntado ao mapa (integração de 15/11/2026): a variável do patch tem de ser a mesma que está lá
        aplicadas = {v["id"]: v for v in atuais["variaveis"]}
        for v in p["variaveis_acrescentar"]:
            if v["id"] in ids_atuais:
                self.assertEqual(aplicadas[v["id"]]["modulo"], v["modulo"], f"variável nova colide com uma existente: {v['id']}")
        conhecidos = ids_atuais | set(novos)
        for v in p["variaveis_acrescentar"]:
            for e in v["entradas"]:
                self.assertIn(e, conhecidos, f"{v['id']}: entrada {e}")
            for o in v["onde"]:
                if o["arquivo"].endswith((".py", ".js")):
                    self.assertIn(o["simbolo"], (RAIZ / o["arquivo"]).read_text(encoding="utf-8"), o)
        for f in p["fluxos_acrescentar"]:
            self.assertIn(f["variavel"], conhecidos)
        gerais = {x["id"] for x in json.loads((RAIZ / "sistema" / "physis-premissas.json").read_text(encoding="utf-8"))["premissas"]}
        base = {x["id"]: x for x in json.loads((RAIZ / "sistema" / "physis-premissas.json").read_text(encoding="utf-8"))["premissas"]}
        for x in integracao.premissas_patch():          # juntadas em 15/11/2026: têm de ser iguais às da base
            if x["id"] in gerais:
                self.assertEqual(base[x["id"]]["valor_padrao"], x["valor_padrao"], f"premissa nova colide com physis-premissas.json: {x['id']}")


if __name__ == "__main__":
    unittest.main()
