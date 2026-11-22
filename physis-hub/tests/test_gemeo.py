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
        cis = [d["valor"] for p, d in self.fv.items() if p.startswith("agua.cisterna.") and p.endswith(".volume_m3")]
        self.assertAlmostEqual(sum(cis), self.fv["agua.reservacao_total_m3"]["valor"], delta=0.05)
        self.assertEqual(self.fv["energia.fv.placas"]["valor"],
                         self.fv["energia.fv.placas_acumuladas.fase3"]["valor"])
        imp = self.fv["areas.impermeavel_m2"]["valor"] + self.fv["areas.permeavel_m2"]["valor"]
        self.assertAlmostEqual(imp, self.fv["lote.area_m2"]["valor"], delta=0.1)
        for cam in ("agua.balanco_mensal.captacao_m3", "agua.balanco_mensal.demanda_nao_potavel_m3"):
            self.assertEqual(len(self.fv[cam]["valor"]), 12)

    def test_divergencias_conferir(self):
        ab = G.conferir_abertos(self.p)
        self.assertEqual(sorted(set(ab.values())), ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9"])
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


class IFC3D(unittest.TestCase):
    """G3: IFC4 do lote gerado da semente (aberto no 3D do Planejador pela plataforma)."""

    @classmethod
    def setUpClass(cls):
        from physis_hub import gemeo_ifc as GI, ifc
        cls.GI, cls.ifc = GI, ifc
        cls.p = G.carregar(SEMENTE)
        cls.txt = GI.escrever(cls.p)
        cls.r = ifc.ler(cls.txt.encode("utf-8"))

    def test_reconta_os_elementos(self):
        self.assertEqual(self.r["esquema"], "IFC4")
        self.assertEqual(self.r["elementos_por_tipo"]["IFCBUILDINGELEMENTPROXY"], 92)
        com_area = sum(1 for e in self.p["gemeo"]["elementos"].values() if not e["sem_area"])
        # toda massa com área tem perfil (os demais perfis são de blocos, muro, contraventos, tubos, caixas e tanques)
        self.assertGreaterEqual(self.r["tipos"]["IFCRECTANGLEPROFILEDEF"] + self.r["tipos"]["IFCCIRCLEPROFILEDEF"], com_area)
        self.assertEqual(self.r["tipos"]["IFCZONE"], 3)
        self.assertEqual(self.r["tipos"]["IFCTRIANGULATEDFACESET"], 2)  # terreno + cobertura cônica
        for chave in self.p["gemeo"]["elementos"]:
            self.assertIn(f"'{chave}',.USERDEFINED.", self.txt)

    def test_marcado_estudo_preliminar_sem_georreferencia(self):
        self.assertIn("ESTUDO PRELIMINAR (revis", self.txt)
        self.assertEqual(self.r["terrenos"][0]["lat"], None)
        self.assertEqual(self.r["terrenos"][0]["lon"], None)

    def test_alturas_vem_da_03_ou_sao_de_desenho(self):
        h, fonte = self.GI.altura_pavimento(self.p["gemeo"]["elementos"])
        self.assertAlmostEqual(h, 2.90, places=3)
        self.assertIn("pg:16228b14d400", fonte)
        self.assertIn("[CONFERIR]", fonte)
        perfis = set(re.findall(r"#(\d+)=IFC(?:RECTANGLE|CIRCLE)PROFILEDEF", self.txt))
        alturas = [float(h) for pf, h in re.findall(r"IFCEXTRUDEDAREASOLID\(#(\d+),#\d+,#\d+,([^)]+)\)", self.txt)
                   if pf in perfis]
        self.assertTrue({2.9, 0.2, 2.59, 3.2} <= set(round(a, 3) for a in alturas))
        # alturas e coberturas da 02b (pg:58d2e859f36a, pg:74fabc0568d2)
        its = {i["id"][2:]: i for i in self.p["itens"]}
        els = self.p["gemeo"]["elementos"]
        cp = lambda k: self.GI.corpo_edificacao(k, self.GI.forma(els[k], its[k]), self.p, 2.9, "03")
        self.assertAlmostEqual(cp("LF1")["total"], 5.0, places=3)
        self.assertAlmostEqual(cp("LF4")["total"], 5.0, places=3)
        self.assertEqual((cp("LF1")["cob"], cp("LF1")["pct"]), ("agua", 15.0))
        self.assertAlmostEqual(cp("bar")["total"], 4.0, places=3)
        self.assertEqual(cp("bar")["cob"], "cone")
        self.assertAlmostEqual(cp("gourmet")["total"], 3.2, places=3)
        self.assertIn("[MARCADOR]", cp("gourmet")["cob_origem"])
        self.assertAlmostEqual(cp("casa")["paredes"], 2.59, places=3)
        self.assertEqual(cp("lab")["paredes"], 2.9)
        self.assertEqual(cp("mec_up")["cob"], "plana")
        self.assertIn("02b", self.p["gemeo"]["fonte_por_valor"]["alturas.total.lofts_m"]["fonte"])
        self.assertEqual(self.p["gemeo"]["fonte_por_valor"]["alturas.pavimento_m"]["conferir"]["alternativas"][0]["valor"], 2.59)
        self.assertIn("[CONFERIR] o acervo n", self.txt)  # nota da cor (sem código de cor no acervo) [CONFERIR]

    def test_relacao_com_o_terreno(self):
        els = self.p["gemeo"]["elementos"]
        T = self.GI.terreno_planejador(self.p)
        its = {i["id"][2:]: i for i in self.p["itens"]}
        r = {k: self.GI.relacao_terreno(e, e["piso_topo_m"], T.z(its[k]["x"], its[k]["y"]))
             for k, e in els.items() if not e["sem_area"]}
        for k in ("cist1", "cist4", "biodig", "fossa", "piscina", "garagem"):
            self.assertIn("intencional", r[k], k)
        self.assertIn("[CONFERIR", r["comum"])
        self.assertNotIn("intencional", r["viveiro_s"])               # "sobre o biodigestor enterrado" não é enterrado
        self.assertGreaterEqual(sum("intencional" in x for x in r.values()), 12)
        els = dict(self.p["gemeo"]["elementos"])
        els["mec_up"] = {**els["mec_up"], "piso_topo_m": els["mec_up"]["piso_topo_m"] + 0.5}
        with self.assertRaises(self.GI.SementeIncompleta):
            self.GI.altura_pavimento(els)

    def test_forma_telhados_e_placas_da_planilha(self):
        its = {i["id"][2:]: i for i in self.p["itens"]}
        els = self.p["gemeo"]["elementos"]
        giros = {k: round(self.GI.forma(els[k], its[k])["giro"]) for k in ("LF1", "LF2", "LF3", "LF4", "LF5")}
        self.assertEqual(giros, {"LF1": 58, "LF2": 62, "LF3": 62, "LF4": 17, "LF5": 32})
        f4 = self.GI.forma(els["LF4"], its["LF4"])
        self.assertEqual((f4["a"], f4["b"]), (4.0, 5.0))  # a medida que reproduz a caixa 5,30 × 5,96 da 03
        self.assertEqual(self.GI.forma(els["bar"], its["bar"])["tipo"], "circ")
        self.assertEqual(self.GI.forma(els["casa"], its["casa"])["giro"], 0.0)  # sem giro na descrição
        self.assertEqual(self.r["elementos_por_tipo"]["IFCSOLARDEVICE"], 11)
        placas = [float(x) for x in re.findall(r"IFCPROPERTYSINGLEVALUE\('Placas',\$,IFC(?:INTEGER|REAL)\(([\d.]+)\)", self.txt)]
        self.assertEqual(sum(placas), self.p["gemeo"]["fonte_por_valor"]["energia.fv.placas"]["valor"])  # 56 da 20
        self.assertIn("ncia D3) [CONFERIR]", self.txt)  # texto STEP com acentos escapados
        self.assertEqual(self.p["gemeo"]["fonte_por_valor"]["telhados.inclinacao_graus"]["valor"], 14.0)
        self.assertGreaterEqual(self.txt.count("IFCARBITRARYCLOSEDPROFILEDEF"), 13)  # telhados + placas

    def test_terreno_pelas_curvas(self):
        """O terreno do IFC é a grade do Planejador (a mesma do comparador e da vista 3D)."""
        T = self.GI.terreno_planejador(self.p)
        v, tri = self.GI.malha_terreno(self.p, T)
        self.assertTrue(all(0 <= i < len(v) for t in tri for i in t))
        self.assertAlmostEqual(T.z(5, 30), 888.3558, places=3)            # o mesmo valor lido no Planejador
        self.assertAlmostEqual(self.GI.cota_no_terreno(v, tri, 0.5, 0.5), 902.3, delta=0.4)  # perto de V1 (902,40)
        self.assertTrue(all(870 < z < 905 for _, _, z in v))

    def test_estrutura_ate_o_terreno(self):
        """Casas não 'voam': pilares tubulares e blocos com as quantidades da 20 e as regras da 02b."""
        ep = self.r["elementos_por_tipo"]
        self.assertGreater(ep["IFCCOLUMN"], 20)
        self.assertGreater(ep["IFCFOOTING"], 30)
        self.assertIn("IFCRECTANGLEHOLLOWPROFILEDEF(.AREA.,$,", self.txt)  # pilar tubular 100 × 100 × 4,75
        its = {i["id"][2:]: i for i in self.p["itens"]}
        els = self.p["gemeo"]["elementos"]
        ap = lambda k: self.GI.apoios(k, self.GI.forma(els[k], its[k]), self.p)
        self.assertEqual(len(ap("casa")[0]), 15)                      # A1 a A15
        self.assertEqual(len(ap("lab")[0]), 8)
        self.assertEqual(len(ap("LF1")[0]), 8)
        self.assertEqual(len(ap("bar")[0]), 9)                        # C0 a C8
        self.assertEqual(len(ap("deck1")[0]), 5)                      # D1 a D10, 5 por deck
        self.assertIsNone(ap("hortaA"))                               # sem regra nas fontes: sem pilar inventado
        self.assertIn("[CONFERIR]", self.txt)

    def test_estrutura_completa_e_contencoes(self):
        """Camada estrutural (tarefa casa-gemeo-estrutura, decisão pg:ee988f1fe957): vigas, contraventos e contenções
        pelas regras da 02b; números de desenho sempre marcados."""
        legivel = re.sub(r"\\X2\\([0-9A-F]+)\\X0\\",
                         lambda m: "".join(chr(int(m.group(1)[k:k + 4], 16)) for k in range(0, len(m.group(1)), 4)), self.txt)
        ep = self.r["elementos_por_tipo"]
        its = {i["id"][2:]: i for i in self.p["itens"]}
        els = self.p["gemeo"]["elementos"]
        ap = self.GI.apoios("lab", self.GI.forma(els["lab"], its["lab"]), self.p)[0]
        self.assertEqual(len(ap), 8)                                   # P1–P4 + P5–P8
        self.assertEqual(sum(1 for q in ap if len(q) == 3), 4)         # P5–P8 vão até o contêiner de cima
        self.assertTrue(all(q[2] == els["lab_up"]["piso_topo_m"] for q in ap if len(q) == 3))
        # vigas: LAB 2 + MEC 2 + 5 lofts × 3 + restaurante 16 (8 radiais + 8 do anel) + Casa 1 V3 = 36
        self.assertEqual(ep["IFCBEAM"], 2 + 2 + 5 * 3 + 16 + 1)
        self.assertIn("IFCISHAPEPROFILEDEF(.AREA.,'W 200 × 15'", legivel)
        self.assertGreater(ep.get("IFCMEMBER", 0), 0)                  # contraventamento em X
        self.assertEqual(ep["IFCWALL"], 1)                             # um muro: platô da Rua G
        self.assertGreater(ep["IFCGEOGRAPHICELEMENT"], 0)              # taludes 1:1 com gabião e vetiver
        self.assertRegex(legivel, r"altura no modelo [\d.]+ m × até ≈ 4.7 m na 02b")
        for marca in ("seção da barra [MARCADOR]", "Espessura', $" if False else "[MARCADOR] desenho 0,20 m",
                      "[CONFERIR no catálogo]", "[MARCADOR] desenho 0,30 m"):
            self.assertIn(marca, legivel)
        self.assertIsNone(self.GI.apoios("hortaA", self.GI.forma(els["hortaA"], its["hortaA"]), self.p))

    def test_hidraulica_esgoto_e_drenagem(self):
        """Camada casa-gemeo-hidraulica: rede de esgoto da 20 com as cotas de fundo exatas, caixas, tanques e
        cisternas com as dimensões úteis da 20; o que não tem posição entra sem geometria."""
        ep = self.r["elementos_por_tipo"]
        nos, tubos, avisos = self.GI.rede_esgoto(self.p)
        self.assertEqual(ep["IFCPIPESEGMENT"], len(tubos))
        self.assertEqual(len(tubos), 11)
        self.assertEqual(avisos, [])                                    # os trechos da 20 fecham com as distâncias
        fv = self.p["gemeo"]["fonte_por_valor"]
        t0 = next(tb for tb in tubos if tb["nome"] == "Casa → CI-1")
        self.assertEqual((t0["z0"], t0["z1"]), (fv["esgoto.trecho.casa_ci_1.fundo_inicio_m"]["valor"],
                                                fv["esgoto.trecho.casa_ci_1.fundo_fim_m"]["valor"]))
        self.assertEqual(set(nos) - set(self.GI.ANCORAS_ESGOTO), {"CI-1", "CI-2", "CI-3", "CI-4", "CI-5", "CI-6", "CI-7", "CGord"})
        self.assertEqual(ep["IFCTANK"], 9)       # biodigestor, fossa, filtro, C1, C2 (2 tanques), C3, C4–C7, C8–C10
        legivel = re.sub(r"\\X2\\([0-9A-F]+)\\X0\\",
                         lambda m: "".join(chr(int(m.group(1)[k:k + 4], 16)) for k in range(0, len(m.group(1)), 4)), self.txt)
        self.assertIn("fossa 2.6 + filtro 2.2 = 4.8 m > 4.1 m da 03", legivel)
        self.assertIn("[MARCADOR] a 03 não desenha", legivel)          # C4–C10 sem posição
        self.assertIn("D9: cota 884.5 (20) × 880 (03)", legivel)        # Loft 4: cota da 20 × geometria da 03

    def test_reprodutivel_e_arquivo_em_dia(self):
        self.assertEqual(self.GI.escrever(self.p), self.txt)
        gravado = SEMENTE.with_suffix(".ifc").read_text(encoding="utf-8")
        self.assertEqual(gravado, self.txt, "IFC desatualizado: rodar python -m physis_hub.gemeo_ifc")


class Versoes(unittest.TestCase):
    """Comparador de versões de planta (critério da dona, M&A pg:97b6e5a48dcf)."""

    @classmethod
    def setUpClass(cls):
        from physis_hub import gemeo_versoes as V
        cls.V = V
        cls.base = G.carregar(SEMENTE)
        cls.lote = V.lote_da_semente(cls.base)
        cls.ter = V.TerrenoPlanejador(cls.lote["poly"], cls.lote["pontos"])
        cls.rev0 = V.versao_da_semente(cls.base)

    def _versao(self, mudar):
        v = copy.deepcopy(self.rev0)
        mudar({e["chave"]: e for e in v["elementos"]}, v)
        return v

    def test_espelho_do_planejador(self):
        """Valores lidos no Planejador (run().terra e T.z) em 21/11/2026 com esta semente: regra 4."""
        its = {i["id"][2:]: i for i in self.base["itens"]}
        esperado = {"casa": 2.1246, "vagas_h": 2.1353, "rampa_h": 2.3002, "bar": 2.8333, "LF1": 2.8444,
                    "garagem": 6.4241, "piscina": 2.9095}
        for k, dz in esperado.items():
            i = its[k]
            self.assertAlmostEqual(self.ter.desnivel(i["x"], i["y"], i["w"], i["d"]), dz, places=3, msg=k)
        self.assertAlmostEqual(self.ter.z(5, 30), 888.3558, places=3)
        self.assertAlmostEqual(self.ter.z(11, 50), 880.3377, places=3)
        src = _planejador_src()
        self.assertIn("if(dz>1.5&&TIPOS[i.tipo].cat!=='perm')", src)  # mesmo limiar
        self.assertIn("const n=110;", src)

    def test_rev0_passa_com_alertas(self):
        a = self.V.avaliar(self.rev0, self.lote, self.ter)
        self.assertTrue(a["passa"], a["falhas"])
        self.assertEqual(a["elementos"], 92)
        self.assertEqual(a["lofts"], 5)
        self.assertTrue(all(a["modulos"].values()))
        self.assertTrue(any(x.startswith("casa: desnível de 2.1 m") for x in a["alertas"]))
        self.assertIn("[MARCADOR]", a["custo_marcador"])

    def test_filtro_elimina_com_motivo(self):
        fora = self._versao(lambda e, v: e["casa"].update(x_03=18.0))
        sobre = self._versao(lambda e, v: e["LF2"].update(x_03=e["LF1"]["x_03"], y_03=e["LF1"]["y_03"],
                                                          piso_topo_m=e["LF1"]["piso_topo_m"]))
        cheia = self._versao(lambda e, v: e["comum"].update(chave="casa_grande", area_m2=600.0))
        for e in cheia["elementos"]:
            if e["chave"] == "casa_grande":
                e["chave"] = "casa2"
        r = self.V.comparar([self.V.avaliar(v, self.lote, self.ter) for v in (
            {**fora, "nome": "fora"}, {**sobre, "nome": "sobre"}, {**cheia, "nome": "cheia"}, self.rev0)])
        self.assertEqual(r["plantas"], ["rev0"])
        self.assertIn("casa sai do perímetro do lote", r["eliminadas"]["fora"])
        self.assertIn("LF1 e LF2 se sobrepõem no mesmo nível", r["eliminadas"]["sobre"])
        self.assertTrue(any("acima do limite de 40 %" in f for f in r["eliminadas"]["cheia"]))

    def test_empilhado_nao_e_sobreposicao(self):
        a = self.V.avaliar(self.rev0, self.lote, self.ter)
        self.assertFalse(any("lab e lab_up" in f or "mec e mec_up" in f for f in a["falhas"]))

    def test_csv_modelo_ida_e_volta(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            arq = os.path.join(d, "versao_B.csv")
            self.V.escrever_modelo_csv(self.rev0, arq)
            v = self.V.ler_versao(arq)
            self.assertEqual(v["nome"], "versao_B")
            a, b = self.V.avaliar(v, self.lote, self.ter), self.V.avaliar(self.rev0, self.lote, self.ter)
            for k in ("passa", "elementos", "por_zona", "area_edificacoes_m2", "lofts", "terra_movida_m3", "alertas"):
                self.assertEqual(a[k], b[k], k)
            Path(arq).write_text("chave;zona\ncasa;Zona 1\n", encoding="utf-8")
            with self.assertRaises(I.FonteAusente):
                self.V.ler_versao(arq)
            pr = os.path.join(d, "precos.csv")
            Path(pr).write_text("tipo;preco_m2;fonte\nresidencia;1000;\n", encoding="utf-8")
            with self.assertRaises(I.FonteAusente):  # preço sem fonte é recusado
                self.V.ler_precos(pr)
        modelo = RAIZ / "modulos" / "planejador" / "gemeo" / "versoes" / "MODELO_precos.csv"
        self.assertEqual(self.V.ler_precos(modelo), {})  # o modelo vem sem nenhum preço (nada inventado)
        self.assertEqual(len(self.V.ler_versao(modelo.with_name("MODELO_versao.csv"))["elementos"]), 92)

    def test_custo_so_com_preco_de_fonte(self):
        tipos = {I.tipo_planejador(e["chave"]) for e in self.rev0["elementos"]}
        precos = {t: (100.0, "tabela de teste") for t in tipos}
        a = self.V.avaliar(self.rev0, self.lote, self.ter, precos)
        self.assertEqual(a["custo_m2_rs"], 100.0)
        self.assertIsNone(a["custo_marcador"])
        del precos["hospedagem"]
        b = self.V.avaliar(self.rev0, self.lote, self.ter, precos)
        self.assertIsNone(b["custo_rs"])
        self.assertIn("hospedagem", b["custo_marcador"])

    def test_versao_vira_projeto_e_ifc(self):
        from physis_hub import gemeo_ifc, ifc
        v = self._versao(lambda e, v: e["casa"].update(x_03=3.0))
        v["nome"] = "B"
        pj = self.V.projeto_da_versao(v, self.base)
        self.assertEqual(G.validar(pj), [])
        self.assertNotIn("energia.fv.kwp", pj["gemeo"]["fonte_por_valor"])  # números da 20 são da rev0
        r = ifc.ler(gemeo_ifc.escrever(pj, altura=(2.9, "teste")).encode("utf-8"))
        self.assertEqual(r["elementos"], 92)

    @unittest.skipUnless(TEM_ACERVO, "planilha 03 do acervo não está nesta máquina")
    def test_masterplans_da_03(self):
        vs = self.V.versoes_masterplan(I.Planilha("03", P03))
        self.assertEqual([v["nome"] for v in vs], ["M1 + C1", "M1 + C2", "M2 + C1", "M2 + C2", "M3 + C1", "M3 + C2"])
        r = self.V.comparar([self.V.avaliar(v, self.lote) for v in vs])
        self.assertEqual(r["resumos"][0], "M2 + C2")  # menor terraplenagem (R$ 40.000), mais lofts


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

    def test_textos_da_prancha_02b_no_pdf(self):
        import shutil, subprocess
        pdf = I.PASTA_PADRAO.parent / "PDF" / "02b_Pranchas_Tecnicas_A3.pdf"
        if not (shutil.which("pdftotext") and pdf.exists()):
            self.skipTest("sem pdftotext ou sem o PDF da 02b")
        txt = subprocess.run(["pdftotext", "-enc", "UTF-8", "-layout", str(pdf), "-"], capture_output=True).stdout.decode("utf-8")
        txt = re.sub(r"\s+", " ", txt)
        for trecho in I.TEXTOS_02B:
            self.assertIn(trecho, txt)

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
