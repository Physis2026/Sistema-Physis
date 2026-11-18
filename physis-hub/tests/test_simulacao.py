"""Simulações da Fase 1 (physis_hub/simulacao): benchmarks analíticos, premissas, envelope do resultado, biogás
e a regra de que o hub nunca importa qiskit.

1. Calor: U de parede igual à base de materiais; decaimento 1D contra a solução analítica; placa quadrada 2D.
2. Estrutura: balanço PL³/3EI (2D e 3D), treliça pelo equilíbrio dos nós, Euler, patch test do CST, verificação
   com [MARCADOR] quando falta fy.
3. Fluidos: ventilação por chaminé; LBM conserva massa e fica estável; eólica pela série reusa vento.py.
4. Terreno: D8 num plano inclinado, SCS-CN conhecido, USLE pede os fatores.
5. Monte Carlo: média da uniforme; mesma semente, mesmo resultado.
6. QUBO: ótimo exato igual à força bruta; recozimento acha o ótimo pequeno; Ising exportado tem a mesma energia.
7. Biogás: caso conferido à mão; TRH longo → BMP; frio reduz; aviso de sobrecarga; CO₂e evitado igual ao carbono.py;
   sem local não há temperatura padrão.
8. Todo resultado traz método, hipóteses, premissas, malha, limites e o aviso de pré-dimensionamento.
"""
import itertools
import json
import math
import re
import unittest
from pathlib import Path

from physis_hub import carbono
from physis_hub.simulacao import AVISO, FaltaDado, biogas, estrutura, fluidos, incerteza, qubo, rota, termica, terreno
from physis_hub.simulacao.comum import Rng

RAIZ = Path(__file__).resolve().parents[2]
PREM = RAIZ / "sistema" / "physis-simulacao-premissas.json"
MAT = RAIZ / "sistema" / "physis-materiais.json"
PACOTE = RAIZ / "physis-hub" / "physis_hub"
CAMPOS = ("metodo", "hipoteses", "premissas_usadas", "malha", "limites_validade", "aviso")


def envelope(tc, r):
    for k in CAMPOS:
        tc.assertIn(k, r)
    tc.assertEqual(r["aviso"], AVISO)


class Premissas(unittest.TestCase):
    def test_formato_e_status(self):
        d = json.loads(PREM.read_text(encoding="utf-8"))
        ids = [p["id"] for p in d["premissas"]]
        self.assertEqual(len(ids), len(set(ids)))
        for p in d["premissas"]:
            self.assertEqual(p["status"], "conferir", p["id"])
            for k in ("grandeza", "valor_padrao", "unidade", "fonte", "nota"):
                self.assertIn(k, p, p["id"])
            self.assertTrue(p["id"].startswith("sim."), p["id"])

    def test_resistencias_iguais_a_base_de_materiais(self):
        d = {p["id"]: p for p in json.loads(PREM.read_text(encoding="utf-8"))["premissas"]}
        base = json.loads(MAT.read_text(encoding="utf-8"))["resistencias_superficiais"]
        v = d["sim.termica.resistencias_superficiais"]["valor_padrao"]
        for tipo in ("parede", "cobertura_verao"):
            self.assertEqual(v[tipo], {"rsi": base[tipo]["rsi"], "rse": base[tipo]["rse"]})

    def test_vento_da_norma_sem_numero_inventado(self):
        d = {p["id"]: p for p in json.loads(PREM.read_text(encoding="utf-8"))["premissas"]}
        v = d["sim.vento.pressao_dinamica"]["valor_padrao"]
        self.assertTrue(all(v[k] is None for k in ("v0", "s1", "s2", "s3", "cf")))
        self.assertIn("[CONFERIR NA NORMA]", d["sim.vento.pressao_dinamica"]["fonte"])
        with self.assertRaises(FaltaDado):
            estrutura.carga_vento(1.0)


class Calor(unittest.TestCase):
    def test_u_das_composicoes_de_bioconstrucao(self):
        for cid in ("taipa_30", "adobe_25", "btc_15", "cob_40", "fardo_palha_45", "canhamo_cal_30", "telhado_verde_extensivo"):
            r = termica.u_composicao(cid)
            envelope(self, r)
            self.assertAlmostEqual(r["u"], r["u_base"], delta=6e-4, msg=cid)

    def test_material_sem_condutividade_vira_marcador(self):
        with self.assertRaises(FaltaDado) as e:
            termica.u_valor([{"material": "cal_hidratada", "espessura": 0.02}])
        self.assertIn("[MARCADOR]", str(e.exception))

    def test_decaimento_1d(self):
        L, n = 0.2, 40
        x = [(i + 0.5) * L / n for i in range(n)]
        for theta in (0.5, 1.0, 0.0):
            r = termica.transiente_1d({"camadas": [{"nome": "p", "espessura": L, "condutividade": 1, "densidade": 1000, "calor_especifico": 1000}],
                                       "dx_max": L / n, "dt": 10, "theta": theta, "duracao_h": 5, "te": 0, "ti": 0,
                                       "contorno_ext": {"tipo": "temperatura"}, "contorno_int": {"tipo": "temperatura"},
                                       "t0": [math.sin(math.pi * xi / L) for xi in x]})
            ana = math.exp(-1e-6 * math.pi ** 2 * 5 * 3600 / L ** 2) * math.sin(math.pi * x[n // 2] / L)
            self.assertAlmostEqual(r["serie"][-1]["t_meio"], ana, delta=0.01 * ana, msg=f"theta {theta}")

    def test_parede_pesada_atrasa_mais(self):
        def atraso(cid_mat, e):
            return termica.transiente_1d({"camadas": [{"material": cid_mat, "espessura": e}], "te": {"senoide": {"media": 25, "amplitude": 8}},
                                          "ti": 25, "t0": 25, "duracao_h": 168, "dt": 900})["atraso_h"]
        self.assertGreater(atraso("terra_taipa", 0.3), atraso("terra_taipa", 0.1))

    def test_placa_quadrada(self):
        N = 21
        z = {"tipo": "temperatura", "T": 0.0}
        r = termica.placa_2d({"nx": N, "ny": N, "dx": 1 / N, "dy": 1 / N, "k": 1, "tol": 1e-10,
                              "contornos": {"topo": {"tipo": "temperatura", "T": 100.0}, "base": z, "esquerda": z, "direita": z}})
        envelope(self, r)
        self.assertAlmostEqual(r["T"][(N // 2) * N + N // 2], 25.0, places=5)
        self.assertAlmostEqual(r["T"][5 * N + 10], termica.placa_analitica(10.5 / N, 1 - 5.5 / N, 1, 1, 100), delta=0.6)
        self.assertAlmostEqual(sum(r["fluxos_w_por_m"].values()), 0.0, delta=1e-5)

    def test_poligono_vira_mascara(self):
        quad = [[0, 0], [0.04, 0], [0.04, 0.02], [0, 0.02]]
        M = termica.mascara_de_segmentos(termica.poligonos_para_segmentos([quad]), 0, 0, 4, 2, 0.01, 0.01)
        self.assertEqual(M, [1] * 8)


class Estrutura(unittest.TestCase):
    E, I, P = 200e9, 1e-6, 1000.0

    def test_balanco(self):
        r = estrutura.portico({"dim": 2, "nos": [[0, 0], [2, 0]], "elementos": [{"i": 0, "j": 1, "E": self.E, "secao": {"A": 1e-3, "Iz": self.I, "c": 0.05}}],
                               "apoios": [{"no": 0, "restr": [1, 1, 1]}], "cargas": [{"no": 1, "F": [0, -self.P, 0]}]})
        envelope(self, r)
        self.assertAlmostEqual(r["deslocamentos"][1][1] / (-self.P * 8 / (3 * self.E * self.I)), 1.0, places=9)
        self.assertAlmostEqual(r["elementos"][0]["M_max"], 2000.0, places=6)

    def test_carga_distribuida_e_3d(self):
        q, L = 500.0, 3.0
        r = estrutura.portico({"dim": 2, "nos": [[0, 0], [1.5, 0], [3, 0]], "elementos": [{"i": 0, "j": 1, "E": self.E, "secao": {"A": 1e-3, "Iz": self.I}, "q": [0, -q]},
                                                                                         {"i": 1, "j": 2, "E": self.E, "secao": {"A": 1e-3, "Iz": self.I}, "q": [0, -q]}],
                               "apoios": [{"no": 0, "restr": [1, 1, 1]}]})
        self.assertAlmostEqual(r["deslocamentos"][2][1] / (-q * L ** 4 / (8 * self.E * self.I)), 1.0, places=9)
        sc = estrutura.secao({"tipo": "tubo", "d": 0.1, "t": 0.005})
        r3 = estrutura.portico({"dim": 3, "nos": [[0, 0, 0], [0, 2, 0]], "elementos": [{"i": 0, "j": 1, "E": self.E, "G": 80e9, "secao": {"tipo": "tubo", "d": 0.1, "t": 0.005}}],
                                "apoios": [{"no": 0, "restr": [1] * 6}], "cargas": [{"no": 1, "F": [self.P, 0, 0, 0, 0, 0]}]})
        self.assertAlmostEqual(r3["deslocamentos"][1][0] / (self.P * 8 / (3 * self.E * sc["Iz"])), 1.0, places=9)

    def test_trelica(self):
        r = estrutura.portico({"dim": 2, "nos": [[0, 0], [4, 0], [2, 3]],
                               "elementos": [{"i": a, "j": b, "tipo": "barra", "E": self.E, "secao": {"A": 1e-3}} for a, b in ((0, 1), (0, 2), (1, 2))],
                               "apoios": [{"no": 0, "restr": [1, 1, 0]}, {"no": 1, "restr": [0, 1, 0]}], "cargas": [{"no": 2, "F": [0, -self.P, 0]}]})
        self.assertAlmostEqual(r["elementos"][0]["N"], self.P / 3, places=6)
        self.assertAlmostEqual(r["elementos"][1]["N"], -self.P / (2 * 3 / math.sqrt(13)), places=6)
        self.assertAlmostEqual(sum(x["valor"] for x in r["reacoes"] if x["gl"] == 1), self.P, places=6)
        v = estrutura.verificar(r)
        self.assertIn("[MARCADOR]", v["linhas"][0]["tensao"])
        self.assertFalse(v["todos_ok"])

    def test_euler_e_instavel(self):
        self.assertAlmostEqual(estrutura.euler(self.E, self.I, 3.0, "engaste_livre")["pcr"], math.pi ** 2 * self.E * self.I / 36, places=6)
        with self.assertRaises(FaltaDado):
            estrutura.portico({"dim": 2, "nos": [[0, 0], [1, 0]], "elementos": [{"i": 0, "j": 1, "E": self.E, "secao": {"A": 1e-3, "Iz": self.I}}],
                               "apoios": [{"no": 0, "restr": [0, 1, 0]}], "cargas": [{"no": 1, "F": [0, -1, 0]}]})

    def test_bambu_sem_modulo_vira_marcador(self):
        with self.assertRaises(FaltaDado) as e:
            estrutura.portico({"dim": 2, "nos": [[0, 0], [1, 0]], "elementos": [{"i": 0, "j": 1, "material": "bambu", "secao": {"tipo": "tubo", "d": 0.08, "t": 0.008}}],
                               "apoios": [{"no": 0, "restr": [1, 1, 1]}]})
        self.assertIn("[MARCADOR]", str(e.exception))

    def test_cst_patch(self):
        m = estrutura.malha_de_mascara([1] * 8, 4, 2, 0.25, 0.25)
        nos = m["nos"]
        esq = [k for k, (x, y) in enumerate(nos) if x == 0]
        dr = [k for k, (x, y) in enumerate(nos) if abs(x - 1) < 1e-12]
        r = estrutura.cst({"nos": nos, "tris": m["tris"], "E": 1e9, "nu": 0.3, "t": 0.01,
                           "apoios": [{"no": k, "restr": [1, 1 if nos[k][1] == 0 else 0]} for k in esq],
                           "cargas": [{"no": k, "F": [1000 * (0.5 if nos[k][1] in (0, 0.5) else 1) / 2, 0]} for k in dr]})
        envelope(self, r)
        for t in r["tensoes"]:
            self.assertAlmostEqual(t["sx"], 200000.0, delta=1e-3)
            self.assertAlmostEqual(t["sy"], 0.0, delta=1e-3)
            self.assertAlmostEqual(t["txy"], 0.0, delta=1e-3)


class Fluidos(unittest.TestCase):
    def test_chamine(self):
        r = fluidos.ventilacao_natural({"a1": 1.0, "a2": 1.0, "h": 3.0, "ti": 30.0, "te": 20.0})
        envelope(self, r)
        self.assertAlmostEqual(r["q_m3s"], 0.6 / math.sqrt(2) * math.sqrt(2 * 9.81 * 3 * 10 / 298.15), places=12)

    def test_lbm_conserva_e_estavel(self):
        nx, ny = 12, 6
        r = fluidos.lbm({"nx": nx, "ny": ny, "modo": "periodico", "passos": 40, "tau": 0.8,
                         "u0_campo": [[0.04 * math.sin(2 * math.pi * (s // nx) / ny) for s in range(nx * ny)], [0.0] * (nx * ny)]})
        self.assertAlmostEqual(r["massa_final"], r["massa_inicial"], places=10)
        self.assertTrue(r["qualitativo"])
        self.assertIn("QUALITATIVO", r["metodo"])
        self.assertTrue(all(v == v and v < 0.04 for v in r["vel"]))      # decai (viscosidade), sem NaN
        with self.assertRaises(ValueError):
            fluidos.lbm({"nx": 4, "ny": 4, "tau": 0.5})

    def test_eolica_serie_reusa_vento(self):
        from physis_hub import vento
        r = fluidos.eolica_serie({"serie": [6.0] * 24 + [4.0] * 24, "h_ref": 12, "altura_cubo": 12, "alfa": 0.0,
                                  "turbina": {"diametro": 3.0, "cp": 0.3, "v_in": 3, "v_nom": 11, "v_out": 25}})
        t = vento.turbina_eolica(3.0, 0.3, 3, 11, 25, None, r["rho"])
        self.assertAlmostEqual(r["kwh_serie"], 24 * vento.potencia_vento(6.0, t) + 24 * vento.potencia_vento(4.0, t), places=9)


class Terreno(unittest.TestCase):
    def test_d8_plano(self):
        g = {"nx": 6, "ny": 4, "dx": 10.0, "dy": 10.0, "z": [100 - 1.0 * j for i in range(4) for j in range(6)]}
        r = terreno.escoamento(g)
        self.assertEqual(r["direcoes"], [0, 0, 0, 0, 0, -1] * 4)
        self.assertEqual(r["acumulacao"], [1.0, 2.0, 3.0, 4.0, 5.0, 6.0] * 4)
        d = terreno.declividade_aspecto(g)
        self.assertAlmostEqual(d["declividade_graus"][7], math.degrees(math.atan(0.1)), places=9)
        self.assertAlmostEqual(d["aspecto_graus"][7], 90.0, places=9)        # desce para leste

    def test_scs(self):
        self.assertAlmostEqual(terreno.scs_cn(100, 80), 87.3 ** 2 / 150.8, places=9)
        self.assertEqual(terreno.scs_cn(10, 80), 0.0)
        with self.assertRaises(FaltaDado):
            terreno.cn_de("agrofloresta", "B")

    def test_usle_pede_fatores_e_grade_do_mapeamento(self):
        g = {"nx": 3, "ny": 3, "dx": 10.0, "dy": 10.0, "z": [9, 9, 9, 8, 8, 8, 7, 7, 7]}
        with self.assertRaises(FaltaDado):
            terreno.usle(g, R=5000)
        r = terreno.usle(g, 5000, 0.03, 0.1, 1.0)
        self.assertGreater(r["media"], 0)
        geo = {"esquema": "physis-geometria-lugar/1", "terreno": {"x0": 0, "y0": 0, "cs": 5.0, "nx": 2, "ny": 2, "Z": [1, 2, 3, 4]}}
        self.assertEqual(terreno.grade_da_geometria(geo)["z"], [3, 4, 1, 2])           # linha de cima = norte
        gm = terreno.grade_do_mapeamento({"nx": 2, "ny": 2, "cs": 0.001, "valores": [1, 2, 3, 4], "lat0": -22.5, "lon0": -43.2})
        self.assertAlmostEqual(gm["dy"], 110.54, places=6)


class MonteCarlo(unittest.TestCase):
    def test_media_e_semente(self):
        a = incerteza.monte_carlo({"x": {"tipo": "uniforme", "min": 0, "max": 1}}, lambda x: x["x"], n=5000, semente=11)
        self.assertAlmostEqual(a["media"], 0.5, delta=3 * (1 / math.sqrt(12)) / math.sqrt(5000))
        b = incerteza.monte_carlo({"x": {"tipo": "uniforme", "min": 0, "max": 1}}, lambda x: x["x"], n=5000, semente=11)
        self.assertEqual(a["percentis"], b["percentis"])
        n = incerteza.monte_carlo({"x": {"tipo": "normal", "media": 10, "dp": 2}}, lambda x: x["x"], n=8000, semente=5)
        self.assertAlmostEqual(n["media"], 10, delta=3 * 2 / math.sqrt(8000))
        self.assertAlmostEqual(n["dp"], 2, delta=0.1)

    def test_rng_mulberry32_conhecido(self):
        # valores tirados do navegador (SIMULACAO.comum.Rng): o mesmo gerador nos dois lados
        r = Rng(42)
        self.assertEqual([r(), r(), r()], [0.6011037519201636, 0.44829055899754167, 0.8524657934904099])
        self.assertAlmostEqual(Rng(1).normal(), 0.9659740590152261, places=14)


class Qubo(unittest.TestCase):
    def test_exato_igual_forca_bruta(self):
        Q = qubo.novo(6)
        rng = Rng(9)
        for i in range(6):
            qubo.soma(Q, i, i, rng() * 4 - 2)
            for j in range(i + 1, 6):
                qubo.soma(Q, i, j, rng() * 4 - 2)
        bf = min((qubo.energia(Q, list(x)), list(x)) for x in itertools.product((0, 1), repeat=6))
        ex = qubo.exato(Q)
        self.assertAlmostEqual(ex["energia"], bf[0], places=9)
        self.assertAlmostEqual(qubo.recozimento(Q, 1)["energia"], bf[0], places=9)

    def test_problemas_e_exportacao_ising(self):
        r = qubo.paineis({"ganho": [10, 9, 8, 7, 3], "sombra": [[0, 1, 6], [2, 3, 1]], "k": 2})
        self.assertEqual(r["escolhidas"], [0, 2])
        self.assertIn("P&D", r["aviso_quantico"])
        ro = qubo.rota({"nx": 3, "ny": 2, "origem": 0, "destino": 5, "custo": {"0,1": 5}})
        self.assertTrue(ro["igual_ao_classico"])
        ex = qubo.exportar(r["Q"], "paineis", r["solucao"])
        self.assertEqual(ex["formato"], "physis-qubo/1")
        for x in itertools.product((0, 1), repeat=ex["n"]):
            s = [1 - 2 * xi for xi in x]
            ei = ex["ising"]["offset"] + sum(h * si for h, si in zip(ex["ising"]["h"], s)) + sum(w * s[i] * s[j] for i, j, w in ex["ising"]["J"])
            self.assertAlmostEqual(ei, qubo.energia(r["Q"], list(x)), places=6)

    def test_hub_nunca_importa_qiskit(self):
        for f in PACOTE.rglob("*.py"):
            if "conteiner" in f.parts:
                continue
            t = f.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"^\s*(import|from)\s+(qiskit|pennylane)", t, re.M), str(f))
        self.assertFalse((PACOTE / "simulacao" / "conteiner" / "__init__.py").exists())


class Biogas(unittest.TestCase):
    def setUp(self):
        self.fat = biogas.fatores_carbono()

    def base(self, **kw):
        p = {"substratos": [{"tipo": "restos_alimentos", "kg_dia": 100.0}], "digestor": {"tipo": "mistura_completa", "volume_m3": 4.0},
             "regime": "mesofilico", "mc": 200}
        p.update(kw)
        return biogas.simular(p, self.fat)

    def test_conferido_a_mao(self):
        r = self.base()
        envelope(self, r)
        k = 0.15 * 1.06 ** 2
        f = k * 40 / (1 + k * 40)
        self.assertAlmostEqual(r["trh_dias"], 40.0, places=12)
        self.assertAlmostEqual(r["biogas_m3_dia"], 100 * 0.2 * 0.9 * 0.65 * f, places=9)
        self.assertAlmostEqual(r["ch4_m3_dia"], r["biogas_m3_dia"] * 0.6, places=9)
        self.assertAlmostEqual(r["energia"]["termica_kwh_dia"], r["biogas_m3_dia"] * 6.0, places=9)
        self.assertAlmostEqual(r["energia"]["glp_kg_dia"], r["biogas_m3_dia"] * 6.0 / 12.8, places=9)
        g = r["gerador"]
        self.assertAlmostEqual(g["s_kva"], g["p_kw"] / g["fp"], places=12)
        self.assertAlmostEqual(g["q_kvar"] ** 2 + g["p_kw"] ** 2, g["s_kva"] ** 2, places=9)
        self.assertLess(r["faixa_ch4_m3_dia"]["5"], r["ch4_m3_dia"])
        self.assertGreater(r["faixa_ch4_m3_dia"]["95"], r["ch4_m3_dia"])
        self.assertTrue(any("H₂S" in a for a in r["avisos"]))

    def test_trh_longo_alcanca_bmp(self):
        r = self.base(digestor={"tipo": "tubular"}, trh_alvo_dias=3000)
        self.assertAlmostEqual(r["fracao_media_bmp"], 1.0, places=9)
        self.assertAlmostEqual(r["dimensionamento"]["volume_total_m3"], 0.1 * 3000 * 1.25, places=9)
        self.assertLess(biogas.fracao_bmp(0.1, 10, "mistura"), biogas.fracao_bmp(0.1, 100, "mistura"))

    def test_frio_reduz(self):
        quente = self.base(digestor={"tipo": "mistura_completa", "volume_m3": 8.0})
        frio = self.base(digestor={"tipo": "mistura_completa", "volume_m3": 8.0}, regime="ambiente", temperatura_mensal=[12.0] * 12)
        self.assertLess(frio["biogas_m3_dia"], quente["biogas_m3_dia"])
        self.assertTrue(any("Temperatura baixa" in a for a in frio["avisos"]))
        with self.assertRaises(FaltaDado) as e:
            self.base(regime="ambiente")
        self.assertIn("local não informado", str(e.exception))

    def test_aviso_de_sobrecarga_e_trh(self):
        r = self.base()
        self.assertAlmostEqual(r["cov_kg_sv_m3_dia"], 4.5, places=12)
        self.assertTrue(any("Sobrecarga" in a for a in r["avisos"]))
        ok = self.base(digestor={"tipo": "mistura_completa", "volume_m3": 10.0})
        self.assertFalse(any("Sobrecarga" in a for a in ok["avisos"]))
        curto = self.base(digestor={"tipo": "mistura_completa", "volume_m3": 1.0})
        self.assertTrue(any("TRH curto" in a for a in curto["avisos"]))

    def test_evitadas_iguais_ao_carbono(self):
        r = self.base(usos={"glp": 1.0})
        c = carbono.calcular({}, {"biogas": r["carbono_ctx"]})
        self.assertAlmostEqual(r["evitadas_t_ano"]["glp"], c["evitadas"]["biogas"], places=12)
        self.assertAlmostEqual(c["biogas_m3"], r["biogas_m3_dia"] * 365, places=9)

    def test_substrato_sem_dado_vira_marcador(self):
        with self.assertRaises(FaltaDado) as e:
            self.base(substratos=[{"tipo": "outro", "kg_dia": 10.0}])
        self.assertIn("[MARCADOR]", str(e.exception))


class Rotas(unittest.TestCase):
    def test_rota_e_marcador(self):
        s, r = rota("/api/simulacao/termica/u", {"composicao": "taipa_30"})
        self.assertEqual(s, 200)
        self.assertAlmostEqual(r["u"], 2.259, delta=5e-4)
        s, r = rota("/api/simulacao/estrutura/portico", {"dim": 2, "nos": [[0, 0], [1, 0]], "elementos": [{"i": 0, "j": 1, "material": "bambu", "secao": {"tipo": "circular", "d": 0.05}}], "apoios": []})
        self.assertEqual(s, 422)
        self.assertTrue(r["marcador"])
        s, r = rota("/api/simulacao/biogas", {"substratos": [{"tipo": "esterco_suino", "kg_dia": 100}], "digestor": {"volume_m3": 5}, "regime": "ambiente", "mc": 50},
                    {"temperatura_mensal": [22.0] * 12, "local": {"municipio": "teste"}})
        self.assertEqual(s, 200)
        self.assertEqual(r["local"]["municipio"], "teste")
        s, r = rota("/api/simulacao/fluidos/lbm", {"nx": 500, "ny": 500, "passos": 10})
        self.assertEqual(s, 400)
        s, r = rota("/api/simulacao/qubo/paineis", {"ganho": [3, 2, 1], "k": 1})
        self.assertEqual(r["exportacao"]["formato"], "physis-qubo/1")
        self.assertEqual(rota("/api/simulacao/nada", {})[0], 404)


if __name__ == "__main__":
    unittest.main()
