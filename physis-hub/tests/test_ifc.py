"""BIM aberto (physis_hub/ifc.py), 15/11/2026.

Protege:
1. O IFC4 escrito tem o cabeçalho STEP certo, as entidades obrigatórias (IfcProject, IfcSite com latitude e longitude,
   IfcBuilding, IfcBuildingStorey) e os elementos dos sistemas, e o leitor próprio lê tudo de volta.
2. GlobalId: 22 caracteres do alfabeto do IFC, únicos e estáveis entre duas exportações.
3. Elétrica: fator de potência, P, Q e S sempre juntos; sem fator no projeto e sem a premissa, ficam vazios (nada inventado).
4. Materiais da base com quantidade e carbono; texto com acento codificado em \\X2\\.
5. Planta solar: arranjo com módulos agregados e o conjunto de propriedades (contagem, kWp, inclinação, azimute, passo,
   inversor, fator de potência) volta pelo leitor.
6. Memorial: elemento com memorial vira IfcDocumentReference ligado ao elemento.
"""
import math
import re
import sys
import unittest
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))
from physis_hub import ifc  # noqa: E402

MATS = [{"id": "concreto_normal", "nome": "Concreto normal", "grupo": "concreto", "densidade": 2300,
         "carbono_incorporado": {"valor": 0.13, "unidade": "kgCO2e/kg", "fonte": "teste"}}]


def projeto(**extra):
    d = {"projeto": {"id": "p-teste", "nome": "Casa Ação"},
         "site": {"nome": "Lote 1", "lat": -22.512345, "lon": -43.178901, "altitude_m": 840},
         "edificacoes": [{"id": "casa", "nome": "Casa", "pavimentos": [{"id": "terreo", "nome": "Térreo", "elevacao_m": 0},
                                                                       {"id": "cobertura", "nome": "Cobertura", "elevacao_m": 3.0}]}],
         "elementos": [
             {"id": "pv1", "tipo": "pv", "nome": "Arranjo norte", "pavimento": "cobertura", "posicao": {"x": 1, "y": 2, "z": 0.2},
              "caixa": {"dx": 6.9, "dy": 4.6, "dz": 0.3},
              "propriedades": {"modulos": 12, "kwp": 6.6, "incl_graus": 20, "azim_graus": 0, "passo_fileiras_m": 2.3,
                               "inversor": "inv-string-mono-3-6", "strings": 2, "modulos_por_string": 6},
              "modulos": [{"x": 1 + k, "y": 2, "z": 0.2} for k in range(12)]},
             {"id": "inv1", "tipo": "inversor", "propriedades": {"potencia_kw": 5, "fator_potencia": 1.0}},
             {"id": "cist", "tipo": "cisterna", "propriedades": {"volume_m3": 10}, "materiais": [{"id": "concreto_normal", "quantidade": 1.2, "unidade": "m3"}]},
             {"id": "calha1", "tipo": "calha", "propriedades": {"largura_mm": 150, "lamina_mm": 75}},
             {"id": "cond1", "tipo": "condutor", "propriedades": {"diametro_mm": 100}},
             {"id": "ac1", "tipo": "avac", "propriedades": {"potencia_kw": 1.1, "btu_h": 12000, "fator_potencia": 0.9}},
             {"id": "qd", "tipo": "quadro", "propriedades": {"circuitos": 12, "potencia_kw": 8}},
             {"id": "bio", "tipo": "biodigestor", "propriedades": {"volume_m3": 4, "biogas_m3_dia": 1.2}},
             {"id": "tb1", "tipo": "turbina", "propriedades": {"potencia_kw": 0.3}},
             {"id": "cant", "tipo": "canteiro", "propriedades": {"area_m2": 12, "mudas": 300}}],
         "materiais_base": MATS}
    d.update(extra)
    return d


class Escrita(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.txt = ifc.escrever(projeto(premissas={"eletrica.fator_potencia_padrao": None}), agora=1794600000)
        cls.r = ifc.ler(cls.txt.encode("utf-8"))

    def test_cabecalho_step(self):
        t = self.txt
        self.assertTrue(t.startswith("ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION("))
        self.assertIn("FILE_SCHEMA(('IFC4'));", t)
        self.assertRegex(t, r"FILE_NAME\('Casa_A[^']*\.ifc','2026-11-1\dT")
        self.assertTrue(t.rstrip().endswith("END-ISO-10303-21;"))
        self.assertEqual(t.count("ENDSEC;"), 2)
        self.assertTrue(all(ord(c) < 128 for c in t), "STEP só com ASCII")
        self.assertIn("\\X2\\00E7\\X0\\", t)        # "ç" de "Ação"

    def test_entidades_obrigatorias_e_leitura(self):
        r = self.r
        self.assertEqual(r["esquema"], "IFC4")
        self.assertEqual(r["projeto"], "Casa Ação")
        for t in ("IFCPROJECT", "IFCSITE", "IFCBUILDING", "IFCBUILDINGSTOREY", "IFCUNITASSIGNMENT", "IFCOWNERHISTORY",
                  "IFCRELAGGREGATES", "IFCRELCONTAINEDINSPATIALSTRUCTURE", "IFCPROPERTYSET", "IFCRELDEFINESBYPROPERTIES"):
            self.assertIn(t, r["tipos"], t)
        self.assertAlmostEqual(r["terrenos"][0]["lat"], -22.512345, places=6)
        self.assertAlmostEqual(r["terrenos"][0]["lon"], -43.178901, places=6)
        self.assertEqual([p["nome"] for p in r["pavimentos"]], ["Térreo", "Cobertura"])
        self.assertEqual(r["elementos"], 10)
        e = r["elementos_por_tipo"]
        self.assertEqual((e["IFCSOLARDEVICE"], e["IFCPIPESEGMENT"], e["IFCBUILDINGELEMENTPROXY"]), (1, 2, 2))
        for t in ("IFCTRANSFORMER", "IFCTANK", "IFCUNITARYEQUIPMENT", "IFCELECTRICDISTRIBUTIONBOARD", "IFCELECTRICGENERATOR"):
            self.assertEqual(e[t], 1, t)
        self.assertEqual(r["tipos"]["IFCSOLARDEVICE"], 13)    # arranjo + 12 módulos agregados
        cx = r["caixa"]
        self.assertAlmostEqual(cx["max"][0], 7.9)               # x 1 + 6,9
        self.assertAlmostEqual(cx["max"][2], 3.5)               # cobertura 3,0 + z 0,2 + 0,3

    def test_guid(self):
        g = re.findall(r"^#\d+=IFC\w+\('([^']{22})'", self.txt, re.M)
        self.assertGreater(len(g), 40)
        self.assertTrue(all(ifc.GUID_RX.match(x) for x in g))
        self.assertEqual(len(g), len(set(g)), "GlobalId repetido")
        outra = ifc.escrever(projeto(premissas={"eletrica.fator_potencia_padrao": None}), agora=1794600000)
        self.assertEqual(outra, self.txt, "mesma entrada, mesmo arquivo")
        self.assertEqual(len(ifc.guid_ifc()), 22)

    def test_eletrica_sempre_com_fp_p_q_s(self):
        t = self.txt
        self.assertEqual(t.count("'Physis_Eletrica'"), 5)   # pv, inversor, avac, quadro, turbina
        # AVAC com fp 0,9 do projeto: Q = P·tan(acos 0,9), S = P/0,9
        q, s = 1.1 * math.tan(math.acos(0.9)), 1.1 / 0.9
        self.assertIn(f"IFCREAL({ifc.r_(q)})", t)
        self.assertIn(f"IFCREAL({ifc.r_(s)})", t)
        # quadro sem fp e sem premissa: fator vazio e a nota [CONFERIR]
        self.assertIn("'FatorPotencia','[CONFERIR] premissa eletrica.fator_potencia_padrao", t)
        self.assertRegex(t, r"IFCPROPERTYSINGLEVALUE\('FatorPotencia','\[CONFERIR\][^']*',\$,\$\)")
        com = ifc.escrever(projeto(premissas={"eletrica.fator_potencia_padrao": 0.92}))
        self.assertIn("'FatorPotencia','premissa eletrica.fator_potencia_padrao',IFCRATIOMEASURE(0.92)", com)
        self.assertEqual(ifc.potencias(10, None)["Q_kvar"], None)
        p = ifc.potencias(10, 0.8)
        self.assertAlmostEqual(p["S_kVA"], 12.5)
        self.assertAlmostEqual(p["Q_kvar"], 7.5)

    def test_planta_solar_e_unidades(self):
        t = self.txt
        for nome in ("modulos", "kwp", "incl_graus", "azim_graus", "passo_fileiras_m", "inversor"):
            self.assertIn(f"IFCPROPERTYSINGLEVALUE('{nome}'", t)
        self.assertIn("IFCCONTEXTDEPENDENTUNIT(", t)
        self.assertIn("'kWp'", t)
        self.assertIn("'DEGREE'", t)
        self.assertIn("IFCSIUNIT(*,.POWERUNIT.,.KILO.,.WATT.)", t)

    def test_materiais_com_carbono(self):
        c = ifc.carbono_material({"id": "concreto_normal", "quantidade": 1.2, "unidade": "m3"}, {m["id"]: m for m in MATS})
        self.assertAlmostEqual(c["kg"], 2760)
        self.assertAlmostEqual(c["kgco2e"], 358.8)
        self.assertIn("IFCMATERIALCONSTITUENTSET(", self.txt)
        self.assertIn(f"IFCREAL({ifc.r_(358.8)})", self.txt)
        self.assertIn("kgCO2e", self.txt)
        fora = ifc.carbono_material({"id": "xis", "quantidade": 1, "unidade": "kg"}, {})
        self.assertIsNone(fora["kgco2e"])

    def test_entradas_recusadas(self):
        with self.assertRaises(ValueError):
            ifc.escrever({"site": {}})
        with self.assertRaises(ValueError):
            ifc.escrever(projeto(elementos=[{"tipo": "foguete"}]))
        with self.assertRaises(ValueError):
            ifc.ler(b"nada disso")


class Memorial(unittest.TestCase):
    def test_elemento_com_memorial_vira_referencia_de_documento(self):
        el = {"id": "rack1", "tipo": "rack", "nome": "Suporte da placa", "caixa": {"dx": 0.12, "dy": 0.05, "dz": 0.08},
              "posicao": {"x": 1, "y": 2, "z": 3}, "memorial": {"id": "MEM-001", "uri": "memoriais/MEM-001.odt"}}
        txt = ifc.escrever(projeto(elementos=[el]))
        self.assertIn("IFCDOCUMENTREFERENCE('memoriais/MEM-001.odt','MEM-001'", txt)
        self.assertIn("IFCRELASSOCIATESDOCUMENT(", txt)
        self.assertEqual(ifc.ler(txt.encode())["elementos_por_tipo"], {"IFCBUILDINGELEMENTPROXY": 1})


if __name__ == "__main__":
    unittest.main()
