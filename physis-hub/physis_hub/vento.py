"""Vento do lugar (10 m e 50 m) e as contas das turbinas: eólica e hidráulica.

Fonte aberta: NASA POWER (climatologia de longo prazo, comunidade RE): WS10M e WS50M (vento a 10 m e a 50 m,
médias mensais e anual), T2M (temperatura, para a densidade do ar) e a altitude do ponto da grade.
Mesmo jeito do gis.py: o hub busca UMA vez por lugar, guarda na tabela gis_cache (Irradiacao._guardado/_guardar)
e entrega sempre do banco; depois da primeira busca funciona sem internet.

As contas abaixo são o espelho de sistema/physis-turbinas.js (window.TURBINAS.eolica e .hidraulica).
Regra 4 do CLAUDE.md: mudou aqui, muda lá, com teste (tests/test_turbinas.py).
"""
from __future__ import annotations

import math
import os
import urllib.error

from .gis import MESES, _arred
from .investimento import analise

URL_VENTO = ("https://power.larc.nasa.gov/api/temporal/climatology/point?parameters=WS10M,WS50M,T2M"
             "&community=RE&longitude={lon}&latitude={lat}&format=JSON")
DIAS_MES = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
G = 9.81
BETZ = 16 / 27          # 0,593: limite teórico de Betz para o Cp

# Expoente α da lei de potência v(h) = v_ref·(h/h_ref)^α, por classe de terreno.
# Valores típicos de literatura (Masters, "Renewable and Efficient Electric Power Systems", 2004, tabela 7.3).
ALFA_TERRENO = {
    "agua": (0.10, "Água calma ou terreno liso e duro"),
    "aberto": (0.15, "Campo aberto, grama alta"),
    "rural": (0.20, "Lavoura alta, cercas vivas e arbustos"),
    "floresta": (0.25, "Mata densa"),
    "cidade_pequena": (0.30, "Cidade pequena com árvores e arbustos"),
    "urbano": (0.40, "Cidade com prédios altos"),
}

# Hidráulica: faixas típicas de aplicação (queda líquida em m, vazão em m³/s) e de eficiência de cada tipo de
# turbina em micro e mini centrais. Aproximações de literatura (ESHA, "Guide on How to Develop a Small
# Hydropower Plant", 2004; Paish, "Small hydro power: technology and current status", 2002). Conferir com o fabricante.
TIPOS_HIDRO = [
    ("pelton", "Pelton", (30, 1000), (0.002, 5), (0.80, 0.90)),
    ("turgo", "Turgo", (20, 300), (0.005, 5), (0.80, 0.85)),
    ("francis", "Francis", (10, 350), (0.05, 50), (0.80, 0.92)),
    ("kaplan", "Kaplan ou hélice", (2, 30), (0.1, 50), (0.80, 0.90)),
    ("banki", "Michell-Banki (fluxo cruzado)", (3, 200), (0.01, 10), (0.65, 0.80)),
    ("pat", "Bomba funcionando como turbina", (5, 100), (0.002, 0.5), (0.50, 0.75)),
]
# Tubulação forçada: rugosidade absoluta ε (mm, Darcy) e coeficiente C (Hazen-Williams) de tubo novo.
# Valores típicos de tabela (diagrama de Moody; Porto, "Hidráulica Básica"). Conferir com o fabricante do tubo.
TUBOS = {
    "pvc": (0.0015, 150, "PVC"),
    "pead": (0.007, 140, "PEAD (polietileno)"),
    "aco": (0.045, 120, "Aço"),
    "ferro": (0.26, 100, "Ferro fundido"),
    "concreto": (0.3, 120, "Concreto"),
}
NU_AGUA = 1.004e-6          # viscosidade cinemática da água a 20 °C (m²/s)


# ═══════════════ Dado do vento (NASA POWER, guardado no hub) ═══════════════

def _serie(p: dict, par: str):
    s = p.get(par) or {}
    meses = [s.get(m) for m in MESES]
    if any(v is None or v <= -999 for v in meses):
        return None
    return {"meses": meses, "anual": s.get("ANN")}


def ler_vento(j: dict) -> dict:
    p = (j.get("properties") or {}).get("parameter") or {}
    ws10, ws50, t2m = _serie(p, "WS10M"), _serie(p, "WS50M"), _serie(p, "T2M")
    if ws10 is None and ws50 is None:
        raise ValueError("série de vento incompleta")
    c = (j.get("geometry") or {}).get("coordinates") or []
    elev = c[2] if len(c) >= 3 and isinstance(c[2], (int, float)) and c[2] > -999 else None
    return {"ws10": ws10, "ws50": ws50, "t2m": t2m, "elevacao_m": elev}


class Vento:
    """Vento a 10 m e 50 m do lugar, guardado no banco do hub (tabela gis_cache, a mesma do gis.py)."""

    def __init__(self, base):
        self.b = base

    def consultar(self, lat: float, lon: float) -> dict:
        if not (-35.0 <= lat <= 6.0 and -75.0 <= lon <= -28.0):
            return {"ok": False, "erro": "coordenadas fora do Brasil"}
        la, lo = _arred(lat), _arred(lon)
        chave = f"vento_alturas:{la}:{lo}"          # não usar "vento:" (é a camada WS2M do gis.py)
        d, avisos = self.b._guardado(chave), []
        if d is None:
            try:
                d = ler_vento(self.b.buscar(os.environ.get("PHYSIS_VENTO_URL", URL_VENTO).format(lat=la, lon=lo)))
                self.b._guardar(chave, d)
            except (urllib.error.URLError, OSError, ValueError, TypeError, AttributeError) as exc:
                avisos.append(f"vento do lugar indisponível agora; o servidor tenta de novo na próxima abertura ({exc})")
        if d is None:
            return {"ok": False, "lat": lat, "lon": lon, "avisos": avisos}
        a = None
        if d.get("ws10") and d.get("ws50"):
            a = alfa_medido(d["ws10"]["anual"], d["ws50"]["anual"])
        return {"ok": True, "lat": lat, "lon": lon, **d, "alfa_medido": None if a is None else round(a, 3),
                "fonte": "NASA POWER (MERRA-2, climatologia de longo prazo, grade de ~50 km): vento a 10 m e 50 m, "
                         "temperatura a 2 m; guardado no servidor",
                "avisos": avisos + ["média de grade regional: não vê prédios, árvores e morros do lugar; "
                                    "meça no local (anemômetro na altura do cubo, 12 meses) antes de comprar"]}


# ═══════════════ Contas do vento ═══════════════

def densidade_ar(altitude_m: float = 0.0, temperatura_c: float = 15.0) -> float:
    """ρ = p / (R·T), com p da atmosfera padrão: p = 101325·(1 − 2,25577·10⁻⁵·h)^5,25588."""
    p = 101325.0 * (1 - 2.25577e-5 * altitude_m) ** 5.25588
    return p / (287.05 * (temperatura_c + 273.15))


def cisalhamento(v_ref: float, h_ref: float, h: float, alfa: float) -> float:
    """Lei de potência: v(h) = v_ref·(h/h_ref)^α."""
    return v_ref * (h / h_ref) ** alfa


def alfa_medido(v10: float, v50: float) -> float | None:
    if not v10 or not v50 or v10 <= 0 or v50 <= 0:
        return None
    return math.log(v50 / v10) / math.log(50 / 10)


def weibull_c(v_media: float, k: float = 2.0) -> float:
    """Parâmetro de escala: c = v̄ / Γ(1 + 1/k). Com k = 2 é a distribuição de Rayleigh."""
    return v_media / math.gamma(1 + 1 / k)


def weibull_pdf(v: float, k: float, c: float) -> float:
    if v < 0 or c <= 0:
        return 0.0
    return (k / c) * (v / c) ** (k - 1) * math.exp(-((v / c) ** k))


def turbina_eolica(diametro: float, cp: float = 0.30, v_in: float = 0.0, v_nom: float | None = None,
                   v_out: float | None = None, p_nom: float | None = None, rho: float = 1.225) -> dict:
    """Normaliza a curva: Cp limitado a Betz; sem potência nominal, ela sai da velocidade nominal."""
    cp = max(0.0, min(cp, BETZ))
    area = math.pi * diametro ** 2 / 4
    if not p_nom and v_nom:
        p_nom = 0.5 * rho * area * v_nom ** 3 * cp / 1000
    return {"area": area, "cp": cp, "v_in": v_in or 0.0, "v_nom": v_nom, "v_out": v_out, "p_nom": p_nom or None, "rho": rho}


def curva_fabricante(c) -> list | None:
    """Curva do fabricante (IEC 61400-12-1): pares [v, kW] válidos, em ordem; None com menos de 2 pontos."""
    if not isinstance(c, list):
        return None
    l = sorted([float(x[0]), float(x[1])] for x in c if isinstance(x, (list, tuple)) and len(x) >= 2 and x[1] >= 0)
    return l if len(l) >= 2 else None


def potencia_curva(v: float, c: list) -> float:
    """Interpolação linear na curva; zero fora dela."""
    if v < c[0][0] or v > c[-1][0]:
        return 0.0
    for (v0, p0), (v1, p1) in zip(c, c[1:]):
        if v <= v1:
            return p1 if v1 == v0 else p0 + (p1 - p0) * (v - v0) / (v1 - v0)
    return 0.0


def potencia_vento(v: float, t: dict) -> float:
    """kW na velocidade v: P = ½·ρ·A·v³·Cp entre a partida e a nominal; nominal até o corte; zero fora.
    Com a curva do fabricante (t["curva"]), a curva."""
    if t.get("curva"):
        return 0.0 if t["v_out"] and v >= t["v_out"] else potencia_curva(v, t["curva"])
    if v < t["v_in"] or (t["v_out"] and v >= t["v_out"]):
        return 0.0
    if t["p_nom"] and t["v_nom"] and v >= t["v_nom"]:
        return t["p_nom"]
    p = 0.5 * t["rho"] * t["area"] * v ** 3 * t["cp"] / 1000
    return min(p, t["p_nom"]) if t["p_nom"] else p


def energia_weibull(t: dict, k: float, c: float, horas: float = 8760.0, passo: float = 0.05, v_max: float = 40.0) -> float:
    """kWh = horas · ∫ P(v)·f(v) dv (regra do ponto médio)."""
    n, s = int(round(v_max / passo)), 0.0
    for i in range(n):
        v = (i + 0.5) * passo
        s += potencia_vento(v, t) * weibull_pdf(v, k, c)
    return s * passo * horas


def eolica(p: dict) -> dict:
    """Espelho de TURBINAS.eolica (sistema/physis-turbinas.js). Entradas:
    diametro (m), cp, v_in, v_nom, v_out (m/s), p_nom (kW), altura_cubo (m), terreno (chave de ALFA_TERRENO) ou
    alfa, altitude (m), temperatura (°C), v_ref (m/s) medida em h_ref (m), k (Weibull), perdas (%),
    meses_ref (12 médias mensais em h_ref, opcional), custo (R$), tarifa (R$/kWh), vida, taxa, infl."""
    g = lambda k, d=None: d if p.get(k) is None else p.get(k)
    avisos = []
    rho = densidade_ar(g("altitude", 0.0), g("temperatura", 25.0))
    alfa = g("alfa")
    if alfa is None:
        if g("terreno", "aberto") not in ALFA_TERRENO:
            avisos.append('Terreno não reconhecido: usado "aberto" (α 0,15)')
        alfa = ALFA_TERRENO.get(g("terreno", "aberto"), ALFA_TERRENO["aberto"])[0]
    if alfa >= 0.30 and (g("v_ref", 0.0) or 0.0) > 0:
        avisos.append("Terreno rugoso (α ≥ 0,30): o vento de referência precisa ser medido no próprio local; dado de estação em campo aberto superestima a energia")
    h_ref, h = g("h_ref", 10.0), g("altura_cubo", 12.0)
    cp_in = g("cp", 0.30)
    if cp_in > BETZ:
        avisos.append("Cp acima do limite de Betz (0,593): usado 0,593")
    if cp_in <= 0 and not p.get("curva"):
        avisos.append("Cp zero ou negativo: a turbina não gera energia")
    if (g("diametro", 0.0) or 0.0) <= 0 and not p.get("curva"):
        avisos.append("Diâmetro do rotor não informado ou zero: energia zero")
    t = turbina_eolica(g("diametro", 0.0), cp_in, g("v_in", 0.0), g("v_nom"), g("v_out"), g("p_nom"), rho)
    cf = curva_fabricante(p.get("curva"))
    if cf:
        t["curva"], t["p_nom"] = cf, max(x[1] for x in cf)
    k = g("k", 2.0) or 2.0
    v_ref = g("v_ref", 0.0) or 0.0
    v_cubo = cisalhamento(v_ref, h_ref, h, alfa) if v_ref > 0 else 0.0
    perdas = max(0.0, min(g("perdas", 0.0), 100.0)) / 100
    meses = None
    if isinstance(p.get("meses_ref"), list) and len(p["meses_ref"]) == 12 and all(isinstance(x, (int, float)) and x > 0 for x in p["meses_ref"]):
        meses = []
        for i, vm in enumerate(p["meses_ref"]):
            vc = cisalhamento(vm, h_ref, h, alfa)
            meses.append({"mes": i + 1, "v_cubo": vc, "kwh": energia_weibull(t, k, weibull_c(vc, k), DIAS_MES[i] * 24) * (1 - perdas)})
        aep = sum(m["kwh"] for m in meses)
    else:
        aep = energia_weibull(t, k, weibull_c(v_cubo, k)) * (1 - perdas) if v_cubo > 0 else 0.0
    c = weibull_c(v_cubo, k) if v_cubo > 0 else 0.0
    fc = aep / (t["p_nom"] * 8760) if t["p_nom"] else None
    if v_cubo < 4:
        viab = ("pouco_viavel", "Pouco viável: vento médio abaixo de 4 m/s na altura do cubo")
    elif v_cubo < 5:
        viab = ("marginal", "Marginal: entre 4 e 5 m/s; só com medição no local e custo baixo")
    else:
        viab = ("viavel", "Viável a confirmar: 5 m/s ou mais na altura do cubo; confirmar com medição no local")
    if fc is not None and fc < 0.10 and viab[0] == "viavel":
        viab = ("marginal", "Marginal: fator de capacidade abaixo de 10%")
    inv = None
    if g("custo") and g("tarifa") and aep > 0:
        inv = analise(g("custo"), aep / 12 * g("tarifa"), g("vida", 20), g("taxa", 10), g("infl", 4))
    if inv and inv.get("vpl") is not None and inv["vpl"] < 0 and viab[0] == "viavel":
        viab = ("marginal", "Marginal: há vento, mas o investimento não se paga (VPL negativo) nas premissas informadas")
    return {"rho": rho, "alfa": alfa, "v_cubo": v_cubo, "k": k, "c": c, "area": t["area"], "cp": t["cp"],
            "p_nom": t["p_nom"], "aep_kwh": aep, "fc": fc, "meses": meses, "viabilidade": viab[0], "mensagem": viab[1],
            "invest": inv, "avisos": avisos, "curva_fabricante": bool(cf)}


# ═══════════════ Contas da água (hidráulica) ═══════════════

def potencia_hidraulica(vazao_m3h: float, queda_m: float, eta: float) -> float:
    """kW: P = ρ·g·Q·H·η = 1000 · 9,81 · (Q/3600) · H · η / 1000."""
    return 1000 * G * (vazao_m3h / 3600) * queda_m * eta / 1000


def perda_darcy(vazao_m3h: float, diametro_mm: float, comprimento_m: float, rugosidade_mm: float,
                k_local: float = 0.0) -> dict:
    """Darcy-Weisbach: hf = f·(L/D)·v²/2g + ΣK·v²/2g; f de Swamee-Jain (64/Re abaixo de Re 2000)."""
    q, d = vazao_m3h / 3600, diametro_mm / 1000
    if q <= 0 or d <= 0:
        return {"hf": 0.0, "v": 0.0, "re": 0.0, "f": None}
    v = q / (math.pi * d ** 2 / 4)
    re = v * d / NU_AGUA
    if re < 2000:
        f = 64 / re
    else:
        f = 0.25 / math.log10(rugosidade_mm / 1000 / (3.7 * d) + 5.74 / re ** 0.9) ** 2
    hv = v ** 2 / (2 * G)
    return {"hf": f * comprimento_m / d * hv + k_local * hv, "v": v, "re": re, "f": f}


def perda_hazen(vazao_m3h: float, diametro_mm: float, comprimento_m: float, c: float, k_local: float = 0.0) -> dict:
    """Hazen-Williams (SI): hf = 10,67·L·Q^1,852 / (C^1,852·D^4,87) + ΣK·v²/2g."""
    q, d = vazao_m3h / 3600, diametro_mm / 1000
    if q <= 0 or d <= 0:
        return {"hf": 0.0, "v": 0.0}
    v = q / (math.pi * d ** 2 / 4)
    return {"hf": 10.67 * comprimento_m * q ** 1.852 / (c ** 1.852 * d ** 4.87) + k_local * v ** 2 / (2 * G), "v": v}


def sugerir_tipos(queda_m: float, vazao_m3h: float) -> list[dict]:
    """Tipos de turbina cuja faixa típica contém a queda e a vazão, do mais centrado ao menos (escala log)."""
    q = vazao_m3h / 3600
    if queda_m <= 0 or q <= 0:
        return []
    r = []
    for tid, nome, (h0, h1), (q0, q1), eta in TIPOS_HIDRO:
        dentro = h0 <= queda_m <= h1 and q0 <= q <= q1
        ch = abs(math.log(queda_m) - (math.log(h0) + math.log(h1)) / 2) / ((math.log(h1) - math.log(h0)) / 2)
        cq = abs(math.log(q) - (math.log(q0) + math.log(q1)) / 2) / ((math.log(q1) - math.log(q0)) / 2)
        r.append({"id": tid, "nome": nome, "dentro": dentro, "nota": max(ch, cq), "eta": list(eta),
                  "queda": [h0, h1], "vazao_m3s": [q0, q1]})
    r.sort(key=lambda x: (not x["dentro"], x["nota"]))
    return r


def hidraulica(p: dict) -> dict:
    """Espelho de TURBINAS.hidraulica. Entradas: vazao (m³/h, de projeto), queda (m, ou bar com un='bar'), eta,
    horas (por dia), n (turbinas), vazoes_mes (12 valores em m³/h, opcional), tubo {material, diametro_mm,
    comprimento_m, metodo 'darcy'|'hazen', k_local}, pressao_dinamica (perdas já medidas), custo, tarifa, vida, taxa, infl."""
    g = lambda k, d=None: d if p.get(k) is None else p.get(k)
    qd = g("vazao", 0.0)
    bruta = g("queda", 0.0) * 10.2 if p.get("un") == "bar" else g("queda", 0.0)
    eta, horas, n = g("eta", 0.6), g("horas", 12.0), g("n", 1)
    tubo = p.get("tubo") or {}
    mat = TUBOS.get(tubo.get("material") or "pvc", TUBOS["pvc"])

    def perda(q):
        if p.get("pressao_dinamica") or not tubo.get("diametro_mm") or not tubo.get("comprimento_m"):
            return {"hf": 0.0, "v": 0.0}
        if tubo.get("metodo") == "hazen":
            return perda_hazen(q, tubo["diametro_mm"], tubo["comprimento_m"], mat[1], tubo.get("k_local") or 0)
        return perda_darcy(q, tubo["diametro_mm"], tubo["comprimento_m"], mat[0], tubo.get("k_local") or 0)

    pd = perda(qd)
    liquida = max(0.0, bruta - pd["hf"])
    kw = potencia_hidraulica(qd, liquida, eta)
    vm = p.get("vazoes_mes")
    usa_mes = isinstance(vm, list) and len(vm) == 12 and all(isinstance(x, (int, float)) and x >= 0 for x in vm)
    meses = []
    for i in range(12):
        q = min(vm[i], qd) if usa_mes else qd
        hl = max(0.0, bruta - perda(q)["hf"])
        meses.append({"mes": i + 1, "vazao": q, "kw": potencia_hidraulica(q, hl, eta) * n,
                      "kwh": potencia_hidraulica(q, hl, eta) * horas * DIAS_MES[i] * n})
    kwh = sum(m["kwh"] for m in meses)
    avisos = []
    if bruta > 0 and pd["hf"] / bruta > 0.10:
        avisos.append("perda na tubulação acima de 10% da queda: aumente o diâmetro")
    if pd.get("v", 0) > 3:
        avisos.append("velocidade na tubulação acima de 3 m/s: risco de golpe de aríete e desgaste")
    inv = None
    if g("custo") and g("tarifa") and kwh > 0:
        inv = analise(g("custo"), kwh / 12 * g("tarifa"), g("vida", 20), g("taxa", 10), g("infl", 4))
    return {"queda_bruta": bruta, "perda_m": pd["hf"], "queda_liquida": liquida, "velocidade": pd.get("v", 0.0),
            "kw": kw, "kw_total": kw * n, "kwh_ano": kwh, "meses": meses, "tipos": sugerir_tipos(liquida, qd),
            "invest": inv, "avisos": avisos}
