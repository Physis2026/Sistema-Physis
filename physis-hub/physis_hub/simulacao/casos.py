"""Casos comuns (exemplos e benchmarks) das simulações: a mesma lista roda no Python (testes) e no navegador
(ferramentas/testes-navegador/conferir-simulacao.html e a aba Simulação).

    python -m physis_hub.simulacao.casos --gravar     (de dentro de physis-hub/)

grava sistema/simulacao-exemplos/casos.json e casos.js (window.SIMULACAO_CASOS) com:
- entrada de cada caso (exemplos marcados "exemplo / dados fictícios");
- "python": os valores que o Python calculou (o navegador tem de dar os mesmos: paridade);
- "analitico": o valor de referência analítico (benchmark), com tolerância;
e copia as premissas de sistema/physis-simulacao-premissas.json (e as 4 gerais usadas) para dentro de
sistema/physis-simulacao.js, entre SIM-PREMISSAS-INICIO e SIM-PREMISSAS-FIM.
O teste tests/test_simulacao_paridade.py regera tudo na memória e confere que os arquivos estão em dia.
"""
from __future__ import annotations

import itertools
import json
import math
import sys

from . import biogas, estrutura, fluidos, incerteza, qubo, termica, terreno
from .comum import ARQ_MATERIAIS, ARQ_PREMISSAS, ARQ_PREMISSAS_GERAIS, SISTEMA, _ler

PASTA = SISTEMA / "simulacao-exemplos"
JS = SISTEMA / "physis-simulacao.js"
GERAIS = ("biogas.pci", "glp.pci", "eletrica.fator_potencia_padrao", "eletrica.fator_potencia_minimo")
FICTICIO = "Exemplo / dados fictícios."


def rodar_caso(c: dict) -> dict:
    e, s = c["entrada"], c["solver"]
    if s == "termica.u_composicao":
        return termica.u_composicao(e["composicao"])
    if s == "termica.u_valor":
        return termica.u_valor(e["camadas"], e.get("tipo", "parede"), e.get("rsi"), e.get("rse"), e.get("ti"), e.get("te"))
    if s == "termica.transiente_1d":
        return termica.transiente_1d(e)
    if s == "termica.placa_2d":
        return termica.placa_2d(e)
    if s == "estrutura.portico":
        r = estrutura.portico(e)
        if e.get("verificar"):
            r["verificacao"] = estrutura.verificar(r, e.get("apoio_flambagem", "biapoiada"))
        return r
    if s == "estrutura.cst":
        return estrutura.cst(e)
    if s == "estrutura.euler":
        return estrutura.euler(e["E"], e["I"], e["L"], e.get("apoio", "biapoiada"), e.get("K"))
    if s == "fluidos.ventilacao_natural":
        return fluidos.ventilacao_natural(e)
    if s == "fluidos.lbm":
        return fluidos.lbm(e)
    if s == "fluidos.eolica_serie":
        return fluidos.eolica_serie(e)
    if s == "terreno.escoamento":
        return terreno.escoamento(e["grade"])
    if s == "terreno.escoamento_scs":
        return terreno.escoamento_scs(e["grade"], e["chuva_mm"], e["usos"], e["grupo"])
    if s == "terreno.usle":
        return terreno.usle(e["grade"], e.get("R"), e.get("K"), e.get("C"), e.get("P"), e.get("comprimento_m"))
    if s == "terreno.visada":
        return terreno.visada(e["grade"], e["i"], e["j"], e.get("altura_obs", 1.6), e.get("altura_alvo", 0.0))
    if s == "terreno.declividade_aspecto":
        return terreno.declividade_aspecto(e["grade"])
    if s == "terreno.scs_cn":
        return {"q_mm": terreno.scs_cn(e["chuva_mm"], e["cn"])}
    if s == "incerteza.monte_carlo":
        return incerteza.monte_carlo(e["entradas"], e["modelo"], e.get("n"), e.get("semente"))
    if s in ("qubo.paineis", "qubo.rota", "qubo.topologia"):
        return getattr(qubo, s.split(".")[1])(e)
    if s == "biogas.simular":
        return biogas.simular(e, c.get("fatores"))
    if s == "biogas.fatores_carbono":
        return biogas.fatores_carbono(e["F"])
    raise ValueError(s)


def pega(o, caminho: str):
    for k in str(caminho).split("."):
        if o is None:
            return None
        o = o[int(k)] if isinstance(o, list) else o.get(k)
    return o


# ── entradas ──
def _grade_vale(nx=16, ny=12, dx=10.0):
    z = []
    for i in range(ny):
        for j in range(nx):
            z.append(round(100 - 2.0 * i + 0.6 * abs(j - nx // 2) + 0.3 * math.sin(0.9 * j + 0.4 * i), 4))
    return {"nx": nx, "ny": ny, "dx": dx, "dy": dx, "z": z}


def _rack():
    nos = [[0.0, 0.0], [1.6, 0.0], [0.0, 0.3], [1.6, 1.2], [0.8, 0.75]]
    tubo = {"tipo": "tubo", "d": 0.0483, "t": 0.0026}
    els = [{"i": 0, "j": 2, "tipo": "barra", "material": "aco_estrutural", "secao": tubo},
           {"i": 1, "j": 3, "tipo": "barra", "material": "aco_estrutural", "secao": tubo},
           {"i": 2, "j": 4, "tipo": "viga", "material": "aco_estrutural", "secao": tubo},
           {"i": 4, "j": 3, "tipo": "viga", "material": "aco_estrutural", "secao": tubo},
           {"i": 0, "j": 4, "tipo": "barra", "material": "aco_estrutural", "secao": tubo},
           {"i": 1, "j": 4, "tipo": "barra", "material": "aco_estrutural", "secao": tubo},
           {"i": 0, "j": 1, "tipo": "barra", "material": "aco_estrutural", "secao": tubo}]
    # vento de exemplo (valores FICTÍCIOS, não da norma): V0 35 m/s, S1 1, S2 0,9, S3 1, Cf 1,2, área 2 m²
    fv = estrutura.carga_vento(2.0, cf=1.2, v0=35.0, s1=1.0, s2=0.9, s3=1.0)["forca_n"]
    dx, dy = 1.6, 0.9
    L = math.hypot(dx, dy)
    nxv, nyv = dy / L, -dx / L            # normal à placa, empurrando para baixo e para trás
    peso_placas = 2 * 22.0 * 9.81         # 2 placas de 22 kg (fictício)
    cargas = []
    for no, frac in ((2, 0.25), (4, 0.5), (3, 0.25)):
        cargas.append({"no": no, "F": [round(fv * frac * nxv, 6), round(fv * frac * nyv - peso_placas * frac, 6), 0.0]})
    return {"dim": 2, "nos": nos, "elementos": els, "apoios": [{"no": 0, "restr": [1, 1, 0]}, {"no": 1, "restr": [1, 1, 0]}],
            "cargas": cargas, "peso_proprio": {"g": 9.81}, "verificar": True}


def _torre():
    H, n = 12.0, 3
    tubo = {"tipo": "tubo", "d": 0.2, "t": 0.006}
    E = 200e9
    F = round(estrutura.empuxo_rotor(3.0, 12.0)["forca_n"], 6)        # vento de 12 m/s (fictício)
    q = round(0.613 * 20.0 ** 2 * 0.7 * 0.2, 6)                         # arrasto na torre: v 20 m/s, Cf 0,7 (fictícios)
    nos = [[0.0, H * k / n] for k in range(n + 1)]
    els = [{"i": k, "j": k + 1, "E": E, "secao": tubo, "material": "aco_estrutural", "q": [0.0, -q]} for k in range(n)]
    # eixo local x sobe; y local aponta para −x global: carga em +x global = q_local_y negativo
    return {"dim": 2, "nos": nos, "elementos": els, "apoios": [{"no": 0, "restr": [1, 1, 1]}],
            "cargas": [{"no": n, "F": [F, 0.0, 0.0]}], "peso_proprio": {"g": 9.81}, "verificar": True,
            "apoio_flambagem": "engaste_livre"}, F, q, H, E, estrutura.secao(tubo)["Iz"]


def _obstaculo(nx, ny, x0, x1, h):
    return [1 if (x0 <= x <= x1 and y < h) else 0 for y in range(ny) for x in range(nx)]


def _fatores_base_min() -> dict:
    F = _ler(str(SISTEMA / "physis-fatores-emissao.json"))
    return {"gwp": F["gwp"], "combustiveis": {k: F["combustiveis"][k] for k in ("glp", "diesel", "biodiesel")},
            "misturas": {"diesel_b": F["misturas"]["diesel_b"]}, "rede": {"padrao": F["rede"]["padrao"], "anual": F["rede"]["anual"]},
            "agro": {"rebanho": F["agro"]["rebanho"]}}


def definir() -> list:
    cs = []

    def add(id_, nome, solver, entrada, saidas, analitico=None, exemplo=False, descricao="", tol=None, extra=None):
        c = {"id": id_, "nome": nome, "solver": solver, "entrada": entrada, "saidas": saidas, "analitico": analitico or [],
             "exemplo": exemplo, "descricao": (FICTICIO + " " + descricao).strip() if exemplo else descricao}
        if tol:
            c["tolerancia"] = tol
        if extra:
            c.update(extra)
        cs.append(c)
    # ── calor ──
    add("ex_parede_taipa_u", "Parede de taipa 30 cm: transmitância (U)", "termica.u_composicao", {"composicao": "taipa_30"},
        ["u", "r_total", "ct_kj_m2k", "massa_kg_m2", "carbono_kgco2e_m2"],
        [{"nome": "U igual ao da base de materiais", "caminho": "u", "valor": 2.259, "tol_abs": 5e-4}], True,
        "Taipa de pilão de 30 cm, propriedades da base de materiais (Bioconstrução).")
    add("ex_parede_taipa_transiente", "Parede de taipa 30 cm: atraso térmico (10 dias de sol)", "termica.transiente_1d",
        {"camadas": [{"material": "terra_taipa", "espessura": 0.3}], "te": {"senoide": {"media": 25, "amplitude": 8, "periodo_h": 24}},
         "ti": 25, "t0": 25, "duracao_h": 240, "dt": 900, "theta": 1, "dx_max": 0.01},
        ["u", "atraso_h", "amortecimento", "serie.5.q_int", "serie.239.q_int", "perfil_final"], [], True,
        "Temperatura externa senoidal 25 ± 8 °C, interna 25 °C; implícito, células de 1 cm.")
    L, n = 0.2, 40
    x = [(i + 0.5) * L / n for i in range(n)]
    alfa = 1.0 / (1000.0 * 1000.0)
    add("bench_decaimento_1d", "Decaimento 1D contra a solução analítica", "termica.transiente_1d",
        {"camadas": [{"nome": "placa", "espessura": L, "condutividade": 1.0, "densidade": 1000.0, "calor_especifico": 1000.0}],
         "dx_max": L / n, "dt": 60, "theta": 0.5, "duracao_h": 10, "te": 0, "ti": 0, "saida_s": 3600,
         "contorno_ext": {"tipo": "temperatura"}, "contorno_int": {"tipo": "temperatura"},
         "t0": [math.sin(math.pi * xi / L) for xi in x]},
        ["serie.10.t_meio", "perfil_final"],
        [{"nome": "T(centro, 10 h) = e^(−απ²t/L²)", "caminho": "serie.10.t_meio",
          "valor": math.exp(-alfa * math.pi ** 2 * 36000 / L ** 2) * math.sin(math.pi * x[n // 2] / L), "tol_rel": 0.01}])
    N = 21
    dur = {"tipo": "temperatura", "T": 0.0}
    add("bench_placa_quadrada", "Placa quadrada 2D em regime permanente", "termica.placa_2d",
        {"nx": N, "ny": N, "dx": 1.0 / N, "dy": 1.0 / N, "k": 1.0, "tol": 1e-10,
         "contornos": {"topo": {"tipo": "temperatura", "T": 100.0}, "base": dur, "esquerda": dur, "direita": dur}},
        ["T", "malha.iteracoes"],
        [{"nome": "centro = 25 (simetria)", "caminho": f"T.{(N // 2) * N + N // 2}", "valor": 25.0, "tol_abs": 1e-6},
         {"nome": "ponto (0,52; 0,74) contra a série de Fourier", "caminho": f"T.{5 * N + 10}",
          "valor": termica.placa_analitica(10.5 / N, 1 - 5.5 / N, 1, 1, 100), "tol_rel": 0.01}])
    nxp, nyp = 15, 30
    K = [1.75 if 12 <= i <= 17 else 1.1 for i in range(nyp) for j in range(nxp)]
    add("ex_ponte_termica", "Ponte térmica: pilar de concreto numa parede de taipa", "termica.placa_2d",
        {"nx": nxp, "ny": nyp, "dx": 0.02, "dy": 0.02, "k": K, "tol": 1e-8,
         "contornos": {"esquerda": {"tipo": "conveccao", "h": 25.0, "T": 35.0}, "direita": {"tipo": "conveccao", "h": 7.7, "T": 24.0}}},
        ["T", "fluxos_w_por_m.esquerda", "fluxos_w_por_m.direita"],
        [{"nome": "fluxo que entra = fluxo que sai", "caminho": "fluxos_w_por_m.esquerda",
          "valor": None, "igual_a": "fluxos_w_por_m.direita", "negativo": True, "tol_rel": 1e-5}], True,
        "Corte horizontal de 60 cm de parede (taipa k 1,1) com pilar de concreto (k 1,75); fora 35 °C, dentro 24 °C.")
    add("bench_u_camadas", "U de camadas digitadas", "termica.u_valor",
        {"camadas": [{"nome": "bloco", "espessura": 0.2, "condutividade": 0.5}], "tipo": "parede"}, ["u"],
        [{"nome": "U = 1/(0,13 + 0,2/0,5 + 0,04)", "caminho": "u", "valor": 1 / (0.13 + 0.4 + 0.04), "tol_rel": 1e-12}])
    # ── estrutura ──
    add("ex_rack_solar", "Suporte de placas solares (treliça e viga de aço)", "estrutura.portico", _rack(),
        ["deslocamentos", "elementos.2.N", "elementos.2.M_max", "elementos.4.N", "verificacao.todos_ok", "reacoes"], [], True,
        "Duas placas (22 kg cada), vento pelo método da pressão dinâmica com V0, S1, S2, S3 e Cf FICTÍCIOS (os do projeto vêm da norma).")
    E, I, Lc, P = 200e9, 1e-6, 2.0, 1000.0
    add("bench_viga_balanco", "Viga em balanço: flecha PL³/3EI", "estrutura.portico",
        {"dim": 2, "nos": [[0, 0], [1, 0], [2, 0]], "elementos": [{"i": 0, "j": 1, "E": E, "secao": {"A": 1e-3, "Iz": I, "c": 0.05}},
                                                                  {"i": 1, "j": 2, "E": E, "secao": {"A": 1e-3, "Iz": I, "c": 0.05}}],
         "apoios": [{"no": 0, "restr": [1, 1, 1]}], "cargas": [{"no": 2, "F": [0, -P, 0]}]},
        ["deslocamentos", "elementos.0.M_max"],
        [{"nome": "flecha = PL³/3EI", "caminho": "deslocamentos.2.1", "valor": -P * Lc ** 3 / (3 * E * I), "tol_rel": 1e-9},
         {"nome": "momento no engaste = PL", "caminho": "elementos.0.M_max", "valor": P * Lc, "tol_rel": 1e-9}])
    add("bench_viga_balanco_3d", "Viga em balanço 3D (tubo)", "estrutura.portico",
        {"dim": 3, "nos": [[0, 0, 0], [2, 0, 0]], "elementos": [{"i": 0, "j": 1, "E": E, "G": 80e9, "secao": {"tipo": "tubo", "d": 0.1, "t": 0.005}}],
         "apoios": [{"no": 0, "restr": [1, 1, 1, 1, 1, 1]}], "cargas": [{"no": 1, "F": [0, 0, -P, 0, 0, 0]}]},
        ["deslocamentos"],
        [{"nome": "flecha = PL³/3EI", "caminho": "deslocamentos.1.2", "valor": -P * 8 / (3 * E * estrutura.secao({"tipo": "tubo", "d": 0.1, "t": 0.005})["Iy"]), "tol_rel": 1e-9}])
    s13 = 3 / math.sqrt(13)
    add("bench_trelica", "Treliça triangular: equilíbrio dos nós", "estrutura.portico",
        {"dim": 2, "nos": [[0, 0], [4, 0], [2, 3]], "elementos": [{"i": 0, "j": 1, "tipo": "barra", "E": E, "secao": {"A": 1e-3}},
                                                                {"i": 0, "j": 2, "tipo": "barra", "E": E, "secao": {"A": 1e-3}},
                                                                {"i": 1, "j": 2, "tipo": "barra", "E": E, "secao": {"A": 1e-3}}],
         "apoios": [{"no": 0, "restr": [1, 1, 0]}, {"no": 1, "restr": [0, 1, 0]}], "cargas": [{"no": 2, "F": [0, -P, 0]}]},
        ["elementos.0.N", "elementos.1.N", "elementos.2.N", "reacoes"],
        [{"nome": "banzo inferior = P/3 (tração)", "caminho": "elementos.0.N", "valor": P / 3, "tol_rel": 1e-9},
         {"nome": "diagonal = −P/(2·senθ)", "caminho": "elementos.1.N", "valor": -P / (2 * s13), "tol_rel": 1e-9}])
    add("bench_euler", "Carga crítica de Euler (engaste-livre)", "estrutura.euler",
        {"E": E, "I": I, "L": 3.0, "apoio": "engaste_livre"}, ["pcr"],
        [{"nome": "Pcr = π²EI/(2L)²", "caminho": "pcr", "valor": math.pi ** 2 * E * I / (2 * 3.0) ** 2, "tol_rel": 1e-12}])
    m = estrutura.malha_de_mascara([1] * 8, 4, 2, 0.25, 0.25)
    nos = m["nos"]
    esq = [k for k, (xx, yy) in enumerate(nos) if xx == 0]
    dr = [k for k, (xx, yy) in enumerate(nos) if abs(xx - 1) < 1e-12]
    add("bench_cst_patch", "Teste da placa (patch test) do CST em tração uniforme", "estrutura.cst",
        {"nos": nos, "tris": m["tris"], "E": 1e9, "nu": 0.3, "t": 0.01,
         "apoios": [{"no": k, "restr": [1, 1 if nos[k][1] == 0 else 0]} for k in esq],
         "cargas": [{"no": k, "F": [1000 * (0.5 if nos[k][1] in (0, 0.5) else 1) / 2, 0]} for k in dr]},
        ["tensoes", "deslocamentos"],
        [{"nome": f"σx = P/A no triângulo {t}", "caminho": f"tensoes.{t}.sx", "valor": 1000 / (0.5 * 0.01), "tol_rel": 1e-9} for t in range(16)]
        + [{"nome": "u na borda = PL/(EA)", "caminho": f"deslocamentos.{dr[0]}.0", "valor": 1000 * 1.0 / (1e9 * 0.5 * 0.01), "tol_rel": 1e-9}])
    torre, F, q, H, Et, It = _torre()
    add("ex_torre_turbina", "Torre de turbina eólica de 12 m (balanço)", "estrutura.portico", torre,
        ["deslocamentos", "elementos.0.M_max", "elementos.0.sigma_max", "verificacao.todos_ok"],
        [{"nome": "deslocamento do topo = FH³/3EI + qH⁴/8EI", "caminho": "deslocamentos.3.0",
          "valor": F * H ** 3 / (3 * Et * It) + q * H ** 4 / (8 * Et * It), "tol_rel": 1e-9}], True,
        "Rotor de 3 m com empuxo do disco atuador a 12 m/s e arrasto na torre a 20 m/s (velocidades fictícias), mais peso próprio.")
    # ── fluidos ──
    add("ex_ventilacao_secador", "Ventilação natural da câmara do Secador", "fluidos.ventilacao_natural",
        {"a1": 0.05, "a2": 0.05, "h": 1.2, "ti": 45.0, "te": 25.0, "v": 1.5, "volume": 0.8},
        ["q_m3s", "q_chamine_m3s", "q_vento_m3s", "trocas_h"],
        [{"nome": "chaminé: Cd·A*·√(2gh·ΔT/Tm)", "caminho": "q_chamine_m3s",
          "valor": 0.6 * (0.05 / math.sqrt(2)) * math.sqrt(2 * 9.81 * 1.2 * 20 / (35 + 273.15)), "tol_rel": 1e-12}], True,
        "Duas aberturas de 5 × 10 cm, 1,2 m de altura entre elas, 45 °C dentro e 25 °C fora, vento de 1,5 m/s.")
    nxl, nyl = 48, 20
    add("ex_lbm", "Vento em volta de um corte de casa (LBM D2Q9, qualitativo)", "fluidos.lbm",
        {"nx": nxl, "ny": nyl, "obstaculo": _obstaculo(nxl, nyl, 14, 19, 7), "u_entrada": 0.06, "tau": 0.6, "passos": 400, "modo": "canal"},
        [], [{"nome": "marcado como qualitativo", "caminho": "qualitativo", "valor": True}], True,
        "Canal de 48 × 20 células com um bloco (a casa) no chão; mostra a aceleração no telhado e a esteira. Só o navegador desenha (o Python confere o caso menor).",
        extra={"so_navegador": True})
    add("bench_lbm_canal", "LBM em canal pequeno (paridade Python × navegador)", "fluidos.lbm",
        {"nx": 30, "ny": 12, "obstaculo": _obstaculo(30, 12, 9, 11, 4), "u_entrada": 0.05, "tau": 0.7, "passos": 150, "modo": "canal"},
        ["vel", "massa_final"], [{"nome": "estável (sem avisos)", "caminho": "avisos", "valor": []}], tol={"rel": 1e-9, "abs": 1e-12})
    nxc, nyc = 16, 8
    add("bench_lbm_conservacao", "LBM em caixa periódica: massa conservada", "fluidos.lbm",
        {"nx": nxc, "ny": nyc, "modo": "periodico", "passos": 60, "tau": 0.8,
         "u0_campo": [[0.05 * math.sin(2 * math.pi * (s // nxc) / nyc) for s in range(nxc * nyc)], [0.0] * (nxc * nyc)]},
        ["massa_final", "vel"], [{"nome": "massa final = inicial", "caminho": "massa_final", "valor": float(nxc * nyc), "tol_rel": 1e-12}])
    add("ex_eolica_serie", "Turbina eólica pequena com série de vento", "fluidos.eolica_serie",
        {"serie": [3, 5, 7, 6, 4, 8, 9, 5, 4, 6, 2, 3, 7, 10, 6, 5] * 6, "passo_h": 1, "h_ref": 10, "altura_cubo": 12, "terreno": "aberto",
         "turbina": {"diametro": 3.0, "cp": 0.35, "v_in": 3.0, "v_nom": 11.0, "v_out": 25.0}},
        ["kwh_serie", "kwh_weibull", "k", "c"], [], True, "Série horária fictícia de 4 dias; contas de vento.py / physis-turbinas.js.")
    # ── terreno ──
    g = _grade_vale()
    usos = ["mata" if abs(j - 8) > 5 else "pasto_bom" for i in range(g["ny"]) for j in range(g["nx"])]
    add("ex_terreno_d8", "Caminho da água num vale pequeno (D8)", "terreno.escoamento", {"grade": g},
        ["direcoes", "acumulacao", "sumidouros"], [], True, "Grade de 16 × 12 células de 10 m, vale descendo para o sul.")
    add("ex_terreno_scs", "Enxurrada de uma chuva de 80 mm (SCS-CN)", "terreno.escoamento_scs",
        {"grade": g, "chuva_mm": 80.0, "usos": usos, "grupo": "C"}, ["volume_acumulado_m3", "volume_total_m3", "lamina_mm"], [], True,
        "Mata nas bordas e pasto no fundo do vale, solo do grupo C (fictício).")
    add("ex_terreno_usle", "Perda de solo (USLE) no vale", "terreno.usle",
        {"grade": g, "R": 6000.0, "K": 0.03, "C": 0.05, "P": 1.0}, ["perda_t_ha_ano", "media"], [], True,
        "R, K, C e P fictícios (os reais vêm do estudo do lugar).")
    add("ex_terreno_visada", "O que se vê do alto do vale", "terreno.visada", {"grade": g, "i": 0, "j": 8, "altura_obs": 1.6},
        ["visivel", "fracao_visivel"], [], True, "Observador de 1,6 m no topo.")
    plano = {"nx": 6, "ny": 4, "dx": 10.0, "dy": 10.0, "z": [100 - 1.0 * j for i in range(4) for j in range(6)]}
    add("bench_d8_plano", "D8 num plano inclinado para leste", "terreno.escoamento", {"grade": plano}, ["direcoes", "acumulacao"],
        [{"nome": "toda célula escoa para leste (exceto a última coluna)", "caminho": "direcoes", "valor": [0, 0, 0, 0, 0, -1] * 4},
         {"nome": "acumulação = número da coluna", "caminho": "acumulacao", "valor": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0] * 4}])
    add("bench_scs", "SCS-CN: CN 80 e chuva de 100 mm", "terreno.scs_cn", {"chuva_mm": 100.0, "cn": 80.0}, ["q_mm"],
        [{"nome": "Q = (P − 0,2S)²/(P + 0,8S), S = 63,5 mm", "caminho": "q_mm", "valor": (100 - 12.7) ** 2 / (100 - 12.7 + 63.5), "tol_rel": 1e-12}])
    # ── Monte Carlo ──
    add("ex_monte_carlo_solar", "Faixa da geração solar de 5 kWp (Monte Carlo)", "incerteza.monte_carlo",
        {"entradas": {"kwp": 5.0, "h": {"tipo": "normal", "media": 5.2, "dp": 0.4}, "pr": {"tipo": "triangular", "min": 0.70, "moda": 0.78, "max": 0.82}},
         "modelo": "solar", "n": 3000, "semente": 42}, ["media", "dp", "percentis"], [], True,
        "Irradiação 5,2 ± 0,4 kWh/m²·dia e PR entre 0,70 e 0,82 (fictícios).")
    add("bench_mc_media", "Monte Carlo: média de uma uniforme", "incerteza.monte_carlo",
        {"entradas": {"kwp": 1.0, "h": {"tipo": "uniforme", "min": 0.0, "max": 1.0}, "pr": 1.0}, "modelo": "solar", "n": 4000, "semente": 7},
        ["media", "percentis"], [{"nome": "média = 365 × 0,5 (± 3σ/√n)", "caminho": "media", "valor": 182.5, "tol_abs": 3 * 365 / math.sqrt(12) / math.sqrt(4000)}])
    # ── QUBO ──
    pin = {"ganho": [10.0, 9.0, 8.0, 7.0, 3.0], "sombra": [[0, 1, 6.0], [2, 3, 1.0]], "k": 2}
    best = None
    for comb in itertools.combinations(range(5), 2):
        v = sum(pin["ganho"][i] for i in comb) - sum(s for i, j, s in pin["sombra"] if i in comb and j in comb)
        if best is None or v > best[0]:
            best = (v, list(comb))
    add("ex_qubo_paineis", "QUBO: 2 placas em 5 posições com sombra", "qubo.paineis", pin, ["escolhidas", "kwh_ano", "solucao.energia"],
        [{"nome": "ótimo por força bruta", "caminho": "escolhidas", "valor": best[1]}], True,
        "Posição 0 e 1 se sombreiam (6 kWh), 2 e 3 pouco (1 kWh). Ganhos fictícios.")
    add("bench_qubo_rota", "QUBO: caminho de tubo numa grade 3 × 2", "qubo.rota",
        {"nx": 3, "ny": 2, "origem": 0, "destino": 5, "custo": {"0,1": 5.0}}, ["custo", "arestas", "solucao.energia"],
        [{"nome": "custo = Dijkstra", "caminho": "igual_ao_classico", "valor": True}])
    add("bench_qubo_topologia", "QUBO: topologia grossa 4 × 3", "qubo.topologia",
        {"nx": 4, "ny": 3, "energia": [1.0, 0.2, 0.2, 1.0, 0.8, 0.1, 0.1, 0.8, 1.0, 0.3, 0.3, 1.0], "fracao": 0.5, "fixas": [0, 8]},
        ["mascara", "celulas"], [{"nome": "volume alvo atendido", "caminho": "celulas", "valor": 6}])
    # ── biogás ──
    fat = biogas.fatores_carbono()
    add("bench_fatores_carbono", "Fatores do Carbono usados no biogás (mesma conta do carbono.py)", "biogas.fatores_carbono",
        {"F": _fatores_base_min()}, ["glp_t_por_kg", "diesel_t_por_l", "rede_t_por_mwh", "gwp_ch4"])
    k37 = 0.15 * 1.06 ** 2
    f40 = k37 * 40 / (1 + k37 * 40)
    add("bench_biogas_manual", "Biogás conferido à mão: 100 kg/dia de restos de alimentos", "biogas.simular",
        {"substratos": [{"tipo": "restos_alimentos", "kg_dia": 100.0}], "digestor": {"tipo": "mistura_completa", "volume_m3": 4.0},
         "regime": "mesofilico", "mc": 300, "semente": 3},
        ["biogas_m3_dia", "ch4_m3_dia", "trh_dias", "cov_kg_sv_m3_dia", "energia", "gerador", "evitadas_t_ano", "faixa_ch4_m3_dia", "digestato"],
        [{"nome": "biogás = 100 × 0,2 × 0,9 × 0,65 × kθ/(1 + kθ)", "caminho": "biogas_m3_dia", "valor": 100 * 0.2 * 0.9 * 0.65 * f40, "tol_rel": 1e-9},
         {"nome": "TRH = 4 m³ ÷ 0,1 m³/dia", "caminho": "trh_dias", "valor": 40.0, "tol_rel": 1e-12},
         {"nome": "COV = 18 kg SV ÷ 4 m³", "caminho": "cov_kg_sv_m3_dia", "valor": 4.5, "tol_rel": 1e-12},
         {"nome": "aviso de sobrecarga", "caminho": "avisos", "contem": "Sobrecarga"}], extra={"fatores": fat})
    add("bench_biogas_trh_longo", "Biogás: TRH muito longo alcança o BMP", "biogas.simular",
        {"substratos": [{"tipo": "esterco_bovino", "kg_dia": 100.0}], "digestor": {"tipo": "tubular"}, "trh_alvo_dias": 3000,
         "regime": "mesofilico", "mc": 200},
        ["fracao_media_bmp", "biogas_m3_dia", "dimensionamento"],
        [{"nome": "fração do BMP → 1", "caminho": "fracao_media_bmp", "valor": 1.0, "tol_abs": 1e-9}], extra={"fatores": fat})
    add("ex_biogas_bovino", "Biodigestor tubular com esterco de 20 vacas", "biogas.simular",
        {"substratos": [{"tipo": "esterco_bovino", "kg_dia": 500.0, "cabecas": 20}], "agua_l_dia": 0.0,
         "digestor": {"tipo": "tubular", "volume_m3": 15.0}, "regime": "mesofilico", "usos": {"glp": 0.6, "eletricidade": 0.4},
         "manejo_dejetos": True, "horas_gerador": 8, "mc": 500},
        ["biogas_m3_dia", "ch4_m3_dia", "mensal", "energia", "gerador", "evitadas_t_ano", "faixa_ch4_m3_dia", "digestato", "carbono_ctx"], [], True,
        "500 kg/dia de esterco (20 vacas), 15 m³ úteis, mesofílico; 60 % do biogás no fogão (no lugar do GLP), 40 % no gerador 8 h/dia.",
        extra={"fatores": fat})
    add("ex_biogas_ambiente", "Biodigestor sem aquecimento: produção mês a mês", "biogas.simular",
        {"substratos": [{"tipo": "esterco_suino", "kg_dia": 300.0}, {"tipo": "restos_alimentos", "kg_dia": 20.0}],
         "digestor": {"tipo": "indiano", "volume_m3": 12.0}, "regime": "ambiente",
         "temperatura_mensal": [24.0, 24.2, 23.5, 21.6, 19.4, 18.0, 17.6, 18.5, 19.7, 21.0, 22.3, 23.4], "mc": 500},
        ["biogas_m3_dia", "mensal", "temperatura_dia_c", "evitadas_t_ano", "faixa_ch4_m3_dia"], [], True,
        "Temperatura mensal FICTÍCIA (no uso real vem do local da instalação, NASA POWER); suínos e restos de cozinha.",
        extra={"fatores": fat})
    return cs


def gerar() -> dict:
    cs = definir()
    for c in cs:
        if c.get("so_navegador"):
            c.pop("saidas")
            c["python"] = {}
            continue
        r = rodar_caso(c)
        c["python"] = {s: pega(r, s) for s in c.pop("saidas")}
        for a in c["analitico"]:
            if a.get("igual_a"):
                a["valor"] = -pega(r, a["igual_a"]) if a.get("negativo") else pega(r, a["igual_a"])
                a.pop("igual_a"), a.pop("negativo", None)
    mats, comps = set(), set()

    def varrer(o):
        if isinstance(o, dict):
            if isinstance(o.get("material"), str):
                mats.add(o["material"])
            if isinstance(o.get("composicao"), str):
                comps.add(o["composicao"])
            for v in o.values():
                varrer(v)
        elif isinstance(o, list):
            for v in o:
                varrer(v)
    varrer([c["entrada"] for c in cs])
    base = _ler(str(ARQ_MATERIAIS))
    cps = [c for c in base["composicoes"] if c["id"] in comps]
    for c in cps:
        for cam in c.get("camadas") or []:
            if cam.get("material"):
                mats.add(cam["material"])
    return {"_leia": "Casos comuns das simulações (exemplos marcados 'exemplo / dados fictícios' e benchmarks analíticos). "
                     "Gerado por python -m physis_hub.simulacao.casos --gravar; não editar à mão.",
            "versao": 1, "casos": cs,
            "materiais": {"materiais": [m for m in base["materiais"] if m["id"] in mats], "composicoes": cps},
            "fatores_base": _fatores_base_min()}


def bloco_premissas() -> str:
    sim = _ler(str(ARQ_PREMISSAS)).get("premissas") or []
    ger = [p for p in (_ler(str(ARQ_PREMISSAS_GERAIS)).get("premissas") or []) if p["id"] in GERAIS]
    return "var PREM = " + json.dumps({"premissas": sim + ger}, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + ";"


def textos() -> tuple[str, str, str]:
    d = gerar()
    j = json.dumps(d, ensure_ascii=False, indent=1, allow_nan=False) + "\n"
    js = ("/* Gerado por python -m physis_hub.simulacao.casos --gravar (de sistema/simulacao-exemplos/casos.json). "
          "Exemplo / dados fictícios. Não editar à mão. */\nwindow.SIMULACAO_CASOS = "
          + json.dumps(d, ensure_ascii=False, separators=(",", ":"), allow_nan=False).replace("</", "<\\/") + ";\n")
    return j, js, bloco_premissas()


def js_com_premissas(texto_js: str, bloco: str) -> str:
    a, b = "/*SIM-PREMISSAS-INICIO*/\n", "\n/*SIM-PREMISSAS-FIM*/"
    i, k = texto_js.index(a) + len(a), texto_js.index(b)
    return texto_js[:i] + bloco + texto_js[k:]


def gravar() -> None:
    j, js, bloco = textos()
    PASTA.mkdir(exist_ok=True)
    (PASTA / "casos.json").write_text(j, encoding="utf-8", newline="\n")
    (PASTA / "casos.js").write_text(js, encoding="utf-8", newline="\n")
    JS.write_text(js_com_premissas(JS.read_text(encoding="utf-8"), bloco), encoding="utf-8", newline="\n")
    print("gravado:", PASTA / "casos.json", PASTA / "casos.js", JS)


if __name__ == "__main__":
    if "--gravar" in sys.argv:
        gravar()
    else:
        print(__doc__)
