"""Patch de integração das simulações (só IMPRIME; quem aplica é o agente/pessoa dona de cada arquivo).

    python -m physis_hub.simulacao.integracao variaveis   → entradas para sistema/physis-variaveis.json
    python -m physis_hub.simulacao.integracao premissas   → entradas para sistema/physis-premissas.json

As premissas novas ficam em sistema/physis-simulacao-premissas.json (status "conferir") até a junção.
"""
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[3]
prem = json.loads((R / "sistema" / "physis-simulacao-premissas.json").read_text(encoding="utf-8"))["premissas"]
PY = "physis-hub/physis_hub/simulacao/"
JS = "sistema/physis-simulacao.js"


def calc(id_, pt, en, un, modulo, formula, py, js, consumidores, premissas, entradas, nota=""):
    return {"id": id_, "nome": {"pt": pt, "en": en}, "unidade": un, "tipo": "calculated", "modulo": modulo, "produtores": [modulo],
            "origem": {"calculo": f"{py} (espelho {JS})"}, "formula": formula,
            "onde": [{"arquivo": PY + py.split(".")[0] + ".py", "linha": 0, "simbolo": py.split(".")[1]}, {"arquivo": JS, "linha": 0, "simbolo": js}],
            "consumidores": consumidores, "armazenamento": ["calculado na hora"], "frequencia": "a cada abertura ou mudança do projeto",
            "agregacao": "por caso", "faixa": {"min": None, "max": None, "fonte": "a definir [CONFERIR]"},
            "qualidade": ["pré-dimensionamento: revisão do engenheiro", "premissas 'conferir'"], "lote": "nao",
            "premissas": premissas, "entradas": entradas, "nota": nota}


def c(mod, tela, nec=False, modo="sugestao"):
    return {"modulo": mod, "tela": tela, "necessario": nec, "modo": modo}


V = [
    calc("sim.u_envoltoria", "Transmitância (U) e capacidade térmica de paredes e coberturas", "Wall and roof U-value and heat capacity",
         "W/(m²·K); kJ/(m²·K)", "simulacao", "U = 1/(Rsi + Σe/λ + ΣRar + Rse)", "termica.u_valor", "uValor",
         [c("avac", "Carga térmica · envoltória"), c("planejador", "bioconstrução · paredes"), c("sbn", "telhado verde"), c("secador", "câmara")],
         ["sim.termica.resistencias_superficiais"], ["plan.materiais"]),
    calc("sim.inercia_termica", "Atraso térmico e fator de amortecimento da parede", "Wall time lag and decrement factor", "h; adimensional",
         "simulacao", "diferenças finitas 1D, método θ, regime periódico", "termica.transiente_1d", "transiente1d",
         [c("avac", "Carga térmica · envoltória"), c("planejador", "bioconstrução")], ["sim.termica.resistencias_superficiais"], ["sim.u_envoltoria"]),
    calc("sim.ponte_termica", "Fluxo de calor no corte 2D (ponte térmica)", "2D section heat flow (thermal bridge)",
         "W/m; °C", "simulacao", "diferenças finitas 2D, SOR", "termica.placa_2d", "placa2d",
         [c("avac", "Carga térmica")], [], ["sim.u_envoltoria"]),
    calc("sim.estrutura", "Deslocamentos, esforços, tensões e utilização (treliça, pórtico, chapa CST)",
         "Displacements, internal forces, stresses and utilisation", "m; N; N·m; Pa; adimensional", "simulacao",
         "K·u = F (barra + viga de Euler-Bernoulli; CST); σ ≤ fy/FS; |N| ≤ Pcr/FS", "estrutura.portico", "portico",
         [c("solar", "suporte das placas"), c("turbinas", "torre"), c("planejador", "pérgola, bambu e madeira"), c("sbn", "viveiro e estufa")],
         ["sim.estrutura.materiais", "sim.estrutura.k_flambagem", "sim.estrutura.fs_tensao", "sim.estrutura.fs_flambagem", "sim.vento.pressao_dinamica", "sim.turbinas.ct_empuxo"], []),
    calc("sim.ventilacao_natural", "Vazão por ventilação natural (chaminé e vento)", "Natural ventilation flow (stack and wind)", "m³/s; trocas/h",
         "simulacao", "Q = Cd·A*·√(2gh·ΔT/T); Q = Cd·A*·v·√ΔCp", "fluidos.ventilacao_natural", "ventilacaoNatural",
         [c("avac", "Ventilação"), c("secador", "câmara"), c("planejador", "bioconstrução")], ["sim.ventilacao.cd", "sim.ventilacao.cp_vento"], ["gis.vento"]),
    calc("sim.lbm_campo", "Campo de velocidade do ar (LBM D2Q9, qualitativo, Fase 1)", "Air velocity field (LBM D2Q9, qualitative, Phase 1)",
         "unidades de rede", "simulacao", "Lattice-Boltzmann D2Q9, BGK", "fluidos.lbm", "lbm",
         [c("avac", "estudo qualitativo"), c("secador", "fluxo na câmara")], [], [], "Qualitativo: nunca número de projeto."),
    calc("sim.terreno_escoamento", "Direção D8, acumulação de fluxo, declividade e aspecto", "D8 flow direction, accumulation, slope and aspect",
         "células; m²; graus", "simulacao", "D8 (maior queda); Horn 3×3", "terreno.escoamento", "escoamento",
         [c("mapeamento", "relevo"), c("resiliencia", "enxurrada e encosta"), c("agua", "onde captar"), c("sbn", "onde plantar, valas em nível")], [], ["plan.terreno"]),
    calc("sim.enxurrada", "Escoamento superficial do evento (SCS-CN) e volume acumulado", "Event runoff (SCS-CN) and accumulated volume", "mm; m³",
         "simulacao", "Q = (P − Ia)²/(P − Ia + S)", "terreno.escoamento_scs", "escoamentoScs",
         [c("resiliencia", "enxurrada"), c("sbn", "jardim de chuva, valas"), c("agua", "captação")], ["sim.hidro.cn_por_uso", "sim.hidro.ia_razao"], ["plan.terreno"]),
    calc("sim.erosao", "Perda de solo (USLE)", "Soil loss (USLE)", "t/(ha·ano)", "simulacao", "A = R·K·LS·C·P", "terreno.usle", "usle",
         [c("resiliencia", "encosta"), c("sbn", "cobertura do solo")], ["sim.erosao.ls"], ["plan.terreno"]),
    calc("sim.visada", "Visada a partir de um ponto", "Viewshed from a point", "0/1 por célula", "simulacao", "linha de visada", "terreno.visada", "visada",
         [c("mapeamento", "relevo")], [], ["plan.terreno"]),
    calc("sim.faixa_incerteza", "Faixa de incerteza (Monte Carlo, percentis)", "Uncertainty band (Monte Carlo percentiles)", "unidade da saída",
         "simulacao", "amostragem aleatória, mulberry32 com semente", "incerteza.monte_carlo", "monteCarlo",
         [c("carbono", "inventário"), c("solar", "geração"), c("gestao", "retorno do investimento"), c("circular", "biodigestor")], ["sim.mc.amostras", "sim.mc.semente"], []),
    calc("sim.qubo", "Solução de otimização em QUBO (clássica) e exportação para a trilha quântica", "QUBO optimisation result (classical) and quantum-track export",
         "adimensional", "simulacao", "min xᵀQx; exato (Gray) ou recozimento", "qubo.paineis", "qPaineis",
         [c("solar", "posições das placas"), c("agua", "traçado de tubo")], ["sim.qubo.penalidade_fator", "sim.qubo.limite_exato"], [],
         "Quântico é P&D: nunca em relatório nem certificação."),
    {**calc("bio.substratos", "Substratos do biodigestor (tipo e kg/dia)", "Digester feedstocks (type and kg/day)", "kg/dia", "circular",
            None, "biogas.simular", "biogasSimular", [c("circular", "biodigestor", True, "automatico")], ["sim.biogas.substratos"], ["rc.plano"]),
     "tipo": "typed", "origem": {"tela": "Economia circular · biodigestor (ou plano RC com rota biodigestor)"}},
    calc("bio.producao", "Biogás e metano por dia e por mês (simulador)", "Biogas and methane per day and per month", "m³/dia; m³/mês", "circular",
         "Σ kg·ST·SV·BMP·f(k(T), TRH)", "biogas.simular", "biogasSimular",
         [c("circular", "biodigestor", True, "automatico"), c("carbono", "evitadas · biogás no lugar do GLP", True, "automatico")],
         ["sim.biogas.substratos", "sim.biogas.cinetica", "sim.biogas.temperaturas", "sim.biogas.cov_max", "sim.biogas.trh_min_dias"],
         ["bio.substratos", "gis.temperatura_mensal", "lugar.coordenadas"], "Grava biogas_m3_dia em physis-calc-biogas (mesmo registro que rc.biogas e o Carbono já leem)."),
    calc("bio.energia", "Energia do biogás: térmica, elétrica, GLP equivalente, horas de queimador, calor útil", "Biogas energy", "kWh/dia; kg/dia; h/dia",
         "circular", "E = biogás × biogas.pci; elétrica × η", "biogas.simular", "biogasSimular",
         [c("circular", "biodigestor"), c("secador", "calor do biogás"), c("avac", "aquecimento de água")], ["biogas.pci", "glp.pci", "sim.biogas.eta_eletrica", "sim.biogas.eta_termica", "sim.biogas.queimador_m3_h"], ["bio.producao"]),
    calc("bio.gerador", "Gerador a biogás: P, Q, S e fator de potência", "Biogas genset P, Q, S and power factor", "kW; kvar; kVA",
         "circular", "S = P/FP; Q = √(S² − P²)", "biogas.simular", "biogasSimular", [c("circular", "biodigestor"), c("supervisao", "energia")],
         ["eletrica.fator_potencia_padrao", "eletrica.fator_potencia_minimo", "sim.biogas.horas_gerador"], ["bio.energia"]),
    calc("bio.evitadas", "CO₂e evitado pelo biogás (GLP, rede, diesel, manejo de dejetos, menos vazamento)", "CO2e avoided by biogas", "tCO2e/ano",
         "circular", "GLP: m³ × biogas.pci ÷ glp.pci × fator do GLP (igual ao carbono.py)", "biogas.simular", "biogasSimular",
         [c("carbono", "evitadas", True, "automatico")], ["biogas.pci", "glp.pci", "sim.biogas.vazamento"], ["bio.producao", "carb.fator_rede"]),
    calc("bio.digestato", "Digestato (volume) e N-P-K estimado", "Digestate volume and estimated N-P-K", "m³/dia; kg/dia", "circular",
         "volume = entrada − massa do biogás", "biogas.simular", "biogasSimular", [c("circular", "biodigestor"), c("sbn", "adubação")],
         ["sim.biogas.substratos", "sim.biogas.densidade_biogas"], ["bio.producao"]),
]
for p in prem:
    V.append({"id": "premissa." + p["id"], "nome": {"pt": p["grandeza"], "en": p["grandeza"] + " [EN: a traduzir]"}, "unidade": p["unidade"],
              "tipo": "premissa", "modulo": "bases", "produtores": ["bases"], "origem": {"base": "sistema/physis-premissas.json", "id": p["id"]},
              "formula": None, "onde": [{"arquivo": "sistema/physis-premissas.json", "linha": 0, "simbolo": '"' + p["id"] + '"'}],
              "consumidores": [{"modulo": "simulacao" if not p["id"].startswith("sim.biogas") else "circular", "tela": "Simulação", "necessario": True, "modo": "automatico"}],
              "armazenamento": ["sistema/physis-premissas.json (cópia em physis-simulacao.js)"], "frequencia": "versionada (atualizado 2026-11-15)",
              "agregacao": "valor padrão; o projeto pode trocar com motivo", "faixa": {"min": None, "max": None, "fonte": "opções da base"},
              "qualidade": ["status 'conferir'"], "lote": "nao", "premissas": [p["id"]], "entradas": []})
fluxos = [
    {"de": "circular", "para": "carbono", "variavel": "bio.producao", "modo": "automatico", "necessario": True, "tela": "Carbono · evitadas (physis-calc-biogas)"},
    {"de": "circular", "para": "secador", "variavel": "bio.energia", "modo": "sugestao", "necessario": False, "tela": "Secador · calor do biogás"},
    {"de": "circular", "para": "avac", "variavel": "bio.energia", "modo": "sugestao", "necessario": False, "tela": "AVAC · aquecimento"},
    {"de": "simulacao", "para": "avac", "variavel": "sim.u_envoltoria", "modo": "sugestao", "necessario": False, "tela": "Carga térmica · envoltória"},
    {"de": "mapeamento", "para": "simulacao", "variavel": "plan.terreno", "modo": "automatico", "necessario": True, "tela": "Simulação · terreno"},
    {"de": "simulacao", "para": "sbn", "variavel": "sim.enxurrada", "modo": "sugestao", "necessario": False, "tela": "SbN · onde plantar"},
    {"de": "simulacao", "para": "resiliencia", "variavel": "sim.enxurrada", "modo": "sugestao", "necessario": False, "tela": "Resiliência · enxurrada"},
    {"de": "externo", "para": "circular", "variavel": "gis.temperatura_mensal", "modo": "automatico", "necessario": True, "tela": "biodigestor sem aquecimento"},
]
def variaveis_patch() -> dict:
    return {"modulos_ja_existentes": ["simulacao"], "variaveis_acrescentar": V, "fluxos_acrescentar": fluxos,
            "rc.biogas_produtores_acrescentar": ["simulacao (physis_hub.simulacao.biogas → physis-calc-biogas)"]}


def premissas_patch() -> list:
    return prem


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "variaveis":
        print(json.dumps(variaveis_patch(), ensure_ascii=False, indent=1))
    elif arg == "premissas":
        print(json.dumps(premissas_patch(), ensure_ascii=False, indent=1))
    else:
        print(__doc__)