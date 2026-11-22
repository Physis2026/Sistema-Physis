"""Gêmeo digital da Casa Physis · G0–G1 (versão de TESTE; desenho no doc 47, aprovado em 21/11/2026).

Protege:
1. A semente `casa-physis-rev0` é um projeto do Planejador (`physis.terreno/1.0`) com o campo `gemeo`, e os itens têm
   o mesmo formato que o Planejador cria (tipos que existem em TIPOS; chaves de `novo()`).
2. Todos os elementos da 03 › Implantação aparecem, por zona, com a entidade dona da zona (Z1 Engineering,
   Z2 Instituto, Z3 Casa) e o estado de vida "projetado".
3. Área do lote e totais batem com a fonte (lote 1.455,95 m²; corte e aterro da linha Total da 03; quadro de áreas
   e cisternas da 20 somam o próprio total).
4. Cada valor tem fonte e procedência; D1–D6 ficam [CONFERIR] com valor alternativo e fonte; o que falta é [MARCADOR].
5. Camada medida vazia ("aguardando sensores"); pontos e cenários existem só no esquema SQL.
6. O importador lê .xlsx sem dependências, entende números em pt-BR e PARA quando falta um rótulo (não inventa).
7. Com as planilhas do acervo presentes, a semente gravada é a mesma que o importador gera hoje (senão: semente
   desatualizada, rodar `python -m physis_hub.gemeo_importar --saida ...`).
"""
import copy
import io
import json
import re
import sqlite3
import unittest
import zipfile
from pathlib import Path

from physis_hub import gemeo as G
from physis_hub import gemeo_importar as I

RAIZ = Path(__file__).resolve().parents[2]
SEMENTE = RAIZ / "modulos" / "planejador" / "gemeo" / "casa-physis-rev0.json"
PLANEJADOR = RAIZ / "modulos" / "planejador" / "planejador-physis.html"
P20, P03, P18 = (I.PASTA_PADRAO / a for a in (I.ARQ_20, I.ARQ_03, I.ARQ_18))
TEM_ACERVO = P20.exists() and P03.exists()


def _planejador_src():
    return PLANEJADOR.read_text(encoding="utf-8")


def _tipos_planejador():
    src = _planejador_src()
    bloco = src[src.index("const TIPOS={"):src.index("};", src.index("const TIPOS={"))]
    return set(re.findall(r"^\s*([a-z_]+):\{n:", bloco, re.M))


class Semente(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = G.carregar(SEMENTE)
        cls.g = cls.p["gemeo"]
        cls.fv = cls.g["fonte_por_valor"]

    def test_integra(self):
        self.assertEqual(G.validar(self.p), [])
        self.assertEqual(self.p["schema"], "physis.terreno/1.0")
        self.assertEqual(self.g["esquema"], G.ESQUEMA)
        self.assertEqual(self.g["revisao"], "rev0")
        self.assertEqual(self.g["versao"], "TESTE")
        self.assertNotIn("[CONFERIR", self.g["convencoes"]["x_y_03"])  # canto, confirmado (pg:8d264ca11dc1)

    def test_formato_do_planejador(self):
        src = _planejador_src()
        novo = src[src.index("function novo(){"):src.index("function save(")]
        for chave in ("meta", "terreno", "clima", "solo", "regras", "itens", "hidro", "sistemas", "premissas",
                      "prov", "log", "inicio"):
            self.assertIn(chave + ":", novo)
            self.assertIn(chave, self.p, chave)
        for s in ("solar", "biogas", "chuva", "reuso", "baterias"):
            self.assertIsInstance(self.p["sistemas"][s], bool)
        tipos = _tipos_planejador()
        self.assertIn("residencia", tipos)
        add = re.search(r"function addItem\(.*?const it=\{(.*?)\};", src).group(1)
        campos = set(re.findall(r"(?:^|,)([a-z]\w*)(?::|(?=,|$))", add))  # chave: valor e chave abreviada
        self.assertTrue({"id", "tipo", "nome", "x", "y", "w", "d", "rot", "pav", "ocup", "cota"} <= campos, campos)
        for it in self.p["itens"]:
            self.assertIn(it["tipo"], tipos, it["id"])
            self.assertTrue(campos <= set(it), (it["id"], campos - set(it)))
        for path, pv in self.p["prov"].items():
            self.assertIn(pv["st"], ("est", "conf", "ter"), path)
            self.assertTrue(pv["src"], path)

    def test_elementos_por_zona_e_entidade(self):
        t = G.totais(self.p)
        self.assertEqual(t["elementos"], 92)
        self.assertEqual(t["por_zona"], {"Z1": 18, "Z2": 40, "Z3": 34})
        ents = {"Z1": "Physis Engineering", "Z2": "Instituto Physis", "Z3": "Casa Physis"}
        for e in G.elementos(self.p):
            self.assertEqual(e["entidade"], ents[e["zona"]], e["chave"])
            self.assertEqual(e["estado_de_vida"], "projetado")
            self.assertTrue(e["fonte"].startswith("planilha 03 › Implantação, linha "))
            self.assertEqual(e["procedencia"], "estimado")
            self.assertIsNotNone(e["item"], e["chave"])
        z = G.por_zona(self.p)
        self.assertIn("casa", [e["chave"] for e in z["Z1"]])
        self.assertIn("bar", [e["chave"] for e in z["Z2"]])
        self.assertEqual(sorted(e["chave"] for e in z["Z3"] if e["chave"].startswith("LF")),
                         ["LF1", "LF2", "LF3", "LF4", "LF5", "LF6", "LF7"])

    def test_centro_do_item_e_canto_da_03(self):
        for e in G.elementos(self.p):
            it = e["item"]
            self.assertAlmostEqual(it["x"], e["x_03"] + e["larg_m"] / 2, places=3)
            self.assertAlmostEqual(it["y"], e["y_03"] + e["prof_m"] / 2, places=3)
            self.assertEqual((it["w"], it["d"], it["cota"]), (e["larg_m"], e["prof_m"], e["piso_topo_m"]))
            self.assertEqual(e["sem_area"], not (e["area_m2"] or 0) > 0)

    def test_lote_e_totais_batem_com_a_fonte(self):
        self.assertEqual(self.fv["lote.area_m2"]["valor"], 1455.95)
        self.assertEqual(self.fv["lote.area_m2"]["fonte"], "planilha 20 › Índices, linha 2, col. B")
        t = G.totais(self.p)
        self.assertAlmostEqual(t["corte_m3"], self.fv["implantacao.corte_total_m3"]["valor"], delta=0.05)
        self.assertAlmostEqual(t["aterro_m3"], self.fv["implantacao.aterro_total_m3"]["valor"], delta=0.05)
        self.assertEqual(self.fv["implantacao.corte_total_m3"]["valor"], 489.3)
        self.assertEqual(self.fv["implantacao.aterro_total_m3"]["valor"], 24.8)
        for campo in ("construida_m2", "projecao_m2"):
            linhas = [d["valor"] for p, d in self.fv.items()
                      if p.startswith("areas.quadro.") and p.endswith(campo) and ".total." not in p]
            self.assertAlmostEqual(sum(linhas), self.fv[f"areas.quadro.total.{campo}"]["valor"], delta=0.05)
        self.assertEqual(self.fv["areas.quadro.total.construida_m2"]["valor"],
                         self.fv["areas.construida_total_m2"]["valor"])
        self.assertEqual(self.fv["areas.quadro.total.projecao_m2"]["valor"], self.fv["areas.projecao_m2"]["valor"])
        cis = [d["valor"] for p, d in self.fv.items() if p.startswith("agua.cisterna.")]
        self.assertAlmostEqual(sum(cis), self.fv["agua.reservacao_total_m3"]["valor"], delta=0.05)
        self.assertEqual(self.fv["energia.fv.placas"]["valor"],
                         self.fv["energia.fv.placas_acumuladas.fase3"]["valor"])
        imp = self.fv["areas.impermeavel_m2"]["valor"] + self.fv["areas.permeavel_m2"]["valor"]
        self.assertAlmostEqual(imp, self.fv["lote.area_m2"]["valor"], delta=0.1)
        for cam in ("agua.balanco_mensal.captacao_m3", "agua.balanco_mensal.demanda_nao_potavel_m3"):
            self.assertEqual(len(self.fv[cam]["valor"]), 12)

    def test_divergencias_conferir(self):
        ab = G.conferir_abertos(self.p)
        self.assertEqual(sorted(set(ab.values())), ["D1", "D2", "D3", "D4", "D5", "D6"])
        esperado = {"lote.area_m2": ("D6", 1216.0), "areas.projecao_m2": ("D4", 244.4),
                    "energia.fv.placas": ("D1", 70.0), "energia.fv.kwp": ("D1", 38.5),
                    "programa.lofts": ("D3", 5)}
        for cam, (div, alt) in esperado.items():
            c = self.fv[cam]["conferir"]
            self.assertEqual(c["divergencia"], div)
            self.assertEqual(c["alternativas"][0]["valor"], alt)
            self.assertTrue(c["alternativas"][0]["fonte"])
        self.assertEqual((self.fv["energia.fv.kwp"]["valor"], self.fv["programa.lofts"]["valor"]), (30.8, 6))
        self.assertEqual(self.fv["casa1.cota_piso_m"]["valor"], 901.22)
        d5 = self.fv["energia.consumo_kwh_mes"]
        self.assertIsNone(d5["valor"])
        self.assertIn("[MARCADOR]", d5["marcador"])
        self.assertEqual(sorted(a["valor"] for a in d5["conferir"]["alternativas"]), [2939.4, 3341.0])

    def test_cada_valor_tem_fonte_zona_entidade(self):
        for cam, d in self.fv.items():
            self.assertTrue(d["fonte"], cam)
            self.assertIn(d["procedencia"], G.PROCEDENCIAS, cam)
            self.assertEqual(d["entidade"], G.entidade_de(d["zona"]), cam)
        self.assertEqual(self.fv["agua.cisterna.c1.volume_m3"]["zona"], "Z1")
        self.assertEqual(self.fv["esgoto.biodigestor"]["entidade"], "Instituto Physis")
        self.assertEqual(self.fv["esgoto.fossa_septica"]["entidade"], "Casa Physis")

    def test_camadas(self):
        self.assertEqual(G.camada_medida(self.p), {"situacao": "aguardando sensores", "pontos": []})
        self.assertEqual(self.g["camadas"]["simulado"]["cenarios"], [])

    def test_terreno_local(self):
        t = self.p["terreno"]
        self.assertEqual(t["poly"][0], [0.0, 0.0])
        self.assertEqual(len(t["poly"]), 5 + 11)  # 5 vértices + 11 pontos do arco P-04→P-05
        self.assertEqual(t["poly"][3], [16.45, 72.1])  # P-04
        self.assertEqual(t["poly"][-1], [0.09, 60.46])  # P-05
        # a geometria reproduz a área do levantamento (com o arco; pela corda dariam ≈ 1.494 m²)
        self.assertAlmostEqual(I.area_poligono(t["poly"]), self.p["gemeo"]["fonte_por_valor"]["lote.area_m2"]["valor"],
                               delta=1.0)
        self.assertIsNone(t["lat0"])
        self.assertIn("[MARCADOR L-01]", self.p["prov"]["terreno.poly"]["src"])
        self.assertTrue(all(len(p) == 3 for p in t["pontos"]))
        self.assertEqual(len(self.p["clima"]["chuva"]), 12)


class Validacao(unittest.TestCase):
    def setUp(self):
        self.p = G.carregar(SEMENTE)

    def test_acusa_falta_de_fonte_e_de_alternativa(self):
        p = copy.deepcopy(self.p)
        p["gemeo"]["fonte_por_valor"]["lote.perimetro_m"]["fonte"] = ""
        p["gemeo"]["fonte_por_valor"]["lote.area_m2"]["conferir"]["alternativas"] = []
        p["gemeo"]["elementos"]["casa"]["entidade"] = "Instituto Physis"
        p["gemeo"]["estado_de_vida"]["por_elemento"]["bar"] = "inventado"
        prob = "\n".join(G.validar(p))
        for trecho in ("lote.perimetro_m: sem fonte", "lote.area_m2: [CONFERIR] sem", "casa: entidade",
                       "bar: estado de vida inválido"):
            self.assertIn(trecho, prob)

    def test_valor_vazio_exige_marcador(self):
        p = copy.deepcopy(self.p)
        del p["gemeo"]["fonte_por_valor"]["energia.consumo_kwh_mes"]["marcador"]
        self.assertIn("energia.consumo_kwh_mes: valor vazio sem [MARCADOR]", G.validar(p))

    def test_valor_rejeita_zona_e_procedencia(self):
        with self.assertRaises(ValueError):
            G.valor(1, "x", procedencia="chute")
        with self.assertRaises(ValueError):
            G.valor(1, "x", zona="Z9")
        self.assertEqual(G.zona_de("Zona 3"), "Z3")
        self.assertIsNone(G.zona_de("Total"))

    def test_esquema_sql_so_desenho(self):
        con = sqlite3.connect(":memory:")
        con.executescript(G.ESQUEMA_SQL)
        nomes = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(nomes, {"gemeo_ponto", "gemeo_cenario"})
        hub = (RAIZ / "physis-hub" / "physis_hub" / "hub.py").read_text(encoding="utf-8")
        self.assertNotIn("gemeo_ponto", hub)  # o hub ainda não cria as tabelas (G5/G6)


def _xlsx_minimo(abas):
    """.xlsx mínimo: {aba: {linha: {col: valor}}} (texto vira shared string)."""
    ss, idx = [], {}
    def s(t):
        if t not in idx:
            idx[t] = len(ss); ss.append(t)
        return idx[t]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        sheets, rels = [], []
        for i, (nome, linhas) in enumerate(abas.items(), 1):
            rows = []
            for r, cols in linhas.items():
                cs = "".join(f'<c r="{c}{r}" t="s"><v>{s(v)}</v></c>' if isinstance(v, str)
                             else f'<c r="{c}{r}"><v>{v}</v></c>' for c, v in cols.items())
                rows.append(f'<row r="{r}">{cs}</row>')
            z.writestr(f"xl/worksheets/sheet{i}.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>' + "".join(rows) + "</sheetData></worksheet>")
            sheets.append(f'<sheet name="{nome}" sheetId="{i}" r:id="rId{i}"/>')
            rels.append(f'<Relationship Id="rId{i}" Target="worksheets/sheet{i}.xml" Type="x"/>')
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + "".join(sheets) + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(rels) + "</Relationships>")
        z.writestr("xl/sharedStrings.xml", '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' + "".join(f"<si><t>{t}</t></si>" for t in ss) + "</sst>")
    return buf


class Importador(unittest.TestCase):
    def test_numeros_br(self):
        self.assertEqual(I.numeros_br("1.455,95 m²"), [1455.95])
        self.assertEqual(I.numeros_br("343,2 m² (23,6%)"), [343.2, 23.6])
        self.assertEqual(I.numeros_br("+18 (56)"), [18.0, 56.0])
        self.assertEqual(I.numeros_br(0.30), [0.3])
        self.assertEqual(I.numeros_br("—"), [])
        with self.assertRaises(I.FonteAusente):
            I.num_br("a confirmar")

    def test_le_xlsx_sem_dependencias(self):
        b = _xlsx_minimo({"Índices": {1: {"A": "Índice", "B": "Valor"}, 2: {"A": "Área do lote", "B": "1.455,95 m²"}},
                          "Implantação": {4: {"A": "casa", "C": "Zona 1", "D": 2, "H": 62.4}}})
        abas = I.ler_xlsx(b)
        self.assertEqual(abas["Índices"][2]["B"], "1.455,95 m²")
        self.assertEqual(abas["Implantação"][4]["H"], 62.4)

    def test_para_quando_falta_rotulo(self):
        import tempfile, os
        b = _xlsx_minimo({"Índices": {1: {"A": "Índice"}}, "Implantação": {4: {"A": "casa", "C": "Zona 1"}}})
        with tempfile.TemporaryDirectory() as d:
            arq = os.path.join(d, "x.xlsx")
            Path(arq).write_bytes(b.getvalue())
            with self.assertRaises(I.FonteAusente):
                I.importar(arq, arq)

    def test_tipo_planejador_existe(self):
        tipos = _tipos_planejador()
        for _, t in I.TIPO_PLANEJADOR:
            self.assertIn(t, tipos)
        self.assertEqual(I.tipo_planejador("calc_lab"), "pavimento")


@unittest.skipUnless(TEM_ACERVO, "planilhas 20 e 03 do acervo não estão nesta máquina")
class Acervo(unittest.TestCase):
    """Só roda onde as planilhas do acervo existem (PHYSIS_CASA_EDITAVEIS ou a pasta padrão)."""

    @classmethod
    def setUpClass(cls):
        cls.novo = I.importar(P20, P03, P18, data="2026-11-21")
        cls.gravado = G.carregar(SEMENTE)

    def test_todos_os_elementos_da_implantacao_por_zona(self):
        abas = I.ler_xlsx(P03)
        esperado = {(str(v["A"]).strip(), G.zona_de(v.get("C"))) for v in abas["Implantação"].values()
                    if G.zona_de(v.get("C")) and v.get("A")}
        tem = {(k, e["zona"]) for k, e in self.gravado["gemeo"]["elementos"].items()}
        self.assertEqual(tem, esperado)

    def test_semente_gravada_esta_em_dia(self):
        a, b = copy.deepcopy(self.novo), copy.deepcopy(self.gravado)
        for p in (a, b):
            p["meta"].pop("criado"); p.pop("log")
        if a["gemeo"]["fontes"] != b["gemeo"]["fontes"]:
            self.fail("planilhas mudaram: semente desatualizada; rodar python -m physis_hub.gemeo_importar --saida "
                      + str(SEMENTE))
        self.assertEqual(json.loads(json.dumps(a)), b)


if __name__ == "__main__":
    unittest.main()
