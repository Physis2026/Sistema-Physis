"""Validação (M&V) · modelos, métricas, incerteza e limpeza de dados. Só biblioteca padrão. Espelho em
sistema/physis-validacao.js (mesmas fórmulas; teste em tests/test_validacao.py). Normas citadas só pelo nome (IPMVP,
ISO 50006, ISO 50015, ASHRAE Guideline 14); nenhum texto delas foi copiado. Todo limite é premissa validacao.* "conferir".

- metricas(): R², CV(RMSE), NMBE e erro padrão, com p parâmetros do modelo.
- ajustar_cp() / escolher_modelo(): regressões com ponto de mudança 2P, 3P, 4P e 5P (busca em grade do ponto de mudança
  e mínimos quadrados de aprendizado.regressao), escolhidas pelo ajuste; o modelo de vizinhos (k-NN, "tipo ML") só entra
  com dados bastantes (validacao.ml_amostra_min) e se ganhar dos de ponto de mudança na validação deixando um de fora.
- incerteza_economia(): incerteza fracional da economia no nível de confiança combinado (estilo ASHRAE Guideline 14,
  com autocorrelação dos resíduos) e o veredito "dentro" ou "fora do limite".
- limpar_serie(): lacunas, valores atípicos, carimbo de tempo (duplicado, fora de ordem, futuro), valor travado e valor
  negativo ou impossível. O valor ORIGINAL fica sempre ao lado, com a marca; nada é trocado em silêncio.
"""
from __future__ import annotations

import math
import statistics
from statistics import NormalDist

from . import aprendizado

GRADE_CP = 21                 # resolução da busca do ponto de mudança (pontos da grade entre os quantis 10 % e 90 %)
FATOR_G14 = 1.26              # coeficiente empírico da incerteza fracional (ASHRAE Guideline 14, só citado) [CONFERIR]
NAO_NEGATIVAS = {"vazao", "chuva", "irradiancia", "nivel", "umidade", "umidade_solo", "corrente"}
P_MODELO = {"2P": 2, "3P": 3, "4P": 4, "5P": 5}


# ══ Métricas ═══════════════════════════════════════════════════════════════════════════════════
def metricas(ys: list[float], yh: list[float], p: int) -> dict:
    """R² = 1 − SSE/SST; CV(RMSE) = √(SSE/(n−p)) ÷ ȳ; NMBE = Σ(y − ŷ) ÷ ((n−p)·ȳ); erro padrão = √(SSE/(n−p))."""
    n = len(ys)
    if n <= p or not n:
        return {"n": n, "p": p, "r2": None, "cv_rmse_pct": None, "nmbe_pct": None, "erro_padrao": None}
    my = sum(ys) / n
    sse = sum((y - h) ** 2 for y, h in zip(ys, yh))
    sst = sum((y - my) ** 2 for y in ys)
    ep = math.sqrt(sse / (n - p))
    return {"n": n, "p": p, "r2": 1 - sse / sst if sst > 0 else None, "cv_rmse_pct": ep / my * 100 if my else None,
            "nmbe_pct": sum(y - h for y, h in zip(ys, yh)) / ((n - p) * my) * 100 if my else None, "erro_padrao": ep}


# ══ Modelos com ponto de mudança ═════════════════════════════════════════════════════════════
def _colunas(tipo: str, x: float, c: tuple) -> list[float]:
    if tipo == "2P":
        return [1.0, x]
    if tipo == "3PC":
        return [1.0, max(0.0, x - c[0])]
    if tipo == "3PH":
        return [1.0, max(0.0, c[0] - x)]
    if tipo == "4P":
        return [1.0, min(0.0, x - c[0]), max(0.0, x - c[0])]
    return [1.0, max(0.0, c[0] - x), max(0.0, x - c[1])]          # 5P


def prever(m: dict, x: float) -> float | None:
    if m is None or x is None:
        return None
    if m["tipo"] == "ML":
        viz = sorted(m["dados"], key=lambda d: abs(d[0] - x))[:m["k"]]
        return sum(d[1] for d in viz) / len(viz)
    return sum(b * v for b, v in zip(m["coef"], _colunas(m["forma"], x, tuple(m["cps"]))))


def _grade(xs: list[float]) -> list[float]:
    s = sorted(xs)
    lo, hi = s[int(0.1 * (len(s) - 1))], s[int(math.ceil(0.9 * (len(s) - 1)))]
    if hi <= lo:
        return []
    return [lo + (hi - lo) * i / (GRADE_CP - 1) for i in range(GRADE_CP)]


def ajustar_cp(tipo: str, xs: list[float], ys: list[float]) -> dict | None:
    """Melhor modelo do tipo (2P, 3P, 4P ou 5P) pelo menor erro; None se não couber nos dados ou violar o sentido físico
    (no 3P e no 5P, consumo sobe para longe do ponto de mudança)."""
    p, n = P_MODELO[tipo], len(xs)
    if n < p + 2:
        return None
    formas = {"2P": [("2P", ())], "3P": [("3PC", (c,)) for c in _grade(xs)] + [("3PH", (c,)) for c in _grade(xs)],
              "4P": [("4P", (c,)) for c in _grade(xs)],
              "5P": [("5P", (a, b)) for a in _grade(xs) for b in _grade(xs) if b > a]}[tipo]
    melhor = None
    for forma, cps in formas:
        X = [_colunas(forma, x, cps) for x in xs]
        if forma != "2P" and any(all(r[j] == 0 for r in X) for j in range(1, len(X[0]))):
            continue                                              # coluna toda zero: ponto de mudança fora dos dados
        coef = aprendizado.regressao(X, ys)
        if (forma in ("3PC", "3PH") and coef[1] <= 0) or (forma == "5P" and (coef[1] <= 0 or coef[2] <= 0)):
            continue
        yh = [sum(b * v for b, v in zip(coef, r)) for r in X]
        sse = sum((y - h) ** 2 for y, h in zip(ys, yh))
        if melhor is None or sse < melhor[0]:
            melhor = (sse, forma, cps, coef, yh)
    if melhor is None:
        return None
    _, forma, cps, coef, yh = melhor
    return {"tipo": tipo, "forma": forma, "cps": list(cps), "coef": coef, "metricas": metricas(ys, yh, p)}


def ajustar_ml(xs: list[float], ys: list[float], k: int) -> dict | None:
    """Vizinhos mais próximos (k-NN) em x, com a validação deixando um de fora (as métricas são dessa validação)."""
    n = len(xs)
    if n <= k + 1:
        return None
    dados = list(zip(xs, ys))
    yh = []
    for i in range(n):
        viz = sorted((d for j, d in enumerate(dados) if j != i), key=lambda d: abs(d[0] - xs[i]))[:k]
        yh.append(sum(d[1] for d in viz) / k)
    return {"tipo": "ML", "forma": "ML", "cps": [], "coef": [], "k": k, "dados": dados, "metricas": metricas(ys, yh, 1)}


def escolher_modelo(xs: list[float], ys: list[float], P: dict) -> dict:
    """Ajusta 2P, 3P, 4P e 5P e escolhe pelo ajuste: o mais simples cujo CV(RMSE) fica até validacao.modelo_ganho_min_pct
    acima do melhor. O k-NN só entra com validacao.ml_amostra_min amostras e só se ganhar por essa mesma margem.
    Aceite: R² ≥ validacao.aceite_r2_min, |NMBE| ≤ validacao.aceite_nmbe_max_pct, CV(RMSE) ≤ o limite do passo."""
    cands = [m for m in (ajustar_cp(t, xs, ys) for t in P_MODELO) if m and m["metricas"]["cv_rmse_pct"] is not None]
    ganho = P["validacao.modelo_ganho_min_pct"] / 100
    escolhido = None
    if cands:
        best = min(m["metricas"]["cv_rmse_pct"] for m in cands)
        escolhido = next(m for m in sorted(cands, key=lambda m: P_MODELO[m["tipo"]]) if m["metricas"]["cv_rmse_pct"] <= best * (1 + ganho))
    ml = None
    if len(xs) >= P["validacao.ml_amostra_min"]:
        ml = ajustar_ml(xs, ys, int(P["validacao.ml_k"]))
        if ml and escolhido and ml["metricas"]["cv_rmse_pct"] is not None \
                and ml["metricas"]["cv_rmse_pct"] < escolhido["metricas"]["cv_rmse_pct"] * (1 - ganho):
            escolhido = ml
        elif ml and not escolhido:
            escolhido = ml
    return {"candidatos": cands + ([ml] if ml else []), "escolhido": escolhido, "aceite": aceite(escolhido, P)}


def aceite(m: dict | None, P: dict, cv_max: float | None = None) -> dict:
    if not m:
        return {"ok": False, "motivos": ["sem modelo"]}
    x, mot = m["metricas"], []
    cvm = P["validacao.baseline_cvrmse_max_pct"] if cv_max is None else cv_max
    if x["r2"] is None or x["r2"] < P["validacao.aceite_r2_min"]:
        mot.append("r2")
    if x["cv_rmse_pct"] is None or x["cv_rmse_pct"] > cvm:
        mot.append("cv_rmse")
    if x["nmbe_pct"] is None or abs(x["nmbe_pct"]) > P["validacao.aceite_nmbe_max_pct"]:
        mot.append("nmbe")
    return {"ok": not mot, "motivos": mot}


# ══ Incerteza ═══════════════════════════════════════════════════════════════════════════════
def t_student(conf_pct: float, gl: float) -> float:
    """Quantil bicaudal da t de Student pela expansão de Cornish-Fisher sobre a normal (só biblioteca padrão)."""
    z = NormalDist().inv_cdf(0.5 + conf_pct / 200)
    g = max(1.0, gl)
    return z + (z ** 3 + z) / (4 * g) + (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * g ** 2)


def autocorrelacao(res: list[float]) -> float:
    n = len(res)
    if n < 3:
        return 0.0
    m = sum(res) / n
    den = sum((r - m) ** 2 for r in res)
    return sum((res[i] - m) * (res[i - 1] - m) for i in range(1, n)) / den if den else 0.0


def incerteza_economia(cv_rmse_pct: float | None, n: int, m: int, fracao_economia: float | None, P: dict,
                       p: int = 2, rho: float = 0.0) -> dict:
    """Incerteza fracional da economia (estilo ASHRAE Guideline 14): ΔE/E = t · 1,26 · CV · √((n/n′)·(1 + 2/n)·(1/m)) ÷ F,
    com n′ = n·(1 − ρ)/(1 + ρ). Veredito: dentro se ΔE/E ≤ validacao.incerteza_max_pct."""
    lim, conf = P["validacao.incerteza_max_pct"], P["validacao.incerteza_confianca_pct"]
    if cv_rmse_pct is None or not n or not m or not fracao_economia or fracao_economia <= 0:
        return {"incerteza_pct": None, "veredito": "sem_dado", "limite_pct": lim, "confianca_pct": conf}
    rho = max(-0.9, min(0.9, rho))
    n_ef = n * (1 - rho) / (1 + rho)
    t = t_student(conf, n - p)
    u = t * FATOR_G14 * (cv_rmse_pct / 100) * math.sqrt((n / n_ef) * (1 + 2 / n) / m) / fracao_economia * 100
    return {"incerteza_pct": u, "veredito": "dentro" if u <= lim else "fora do limite", "limite_pct": lim, "confianca_pct": conf,
            "t": t, "n_efetivo": n_ef, "rho": rho}


# ══ Qualidade e limpeza ══════════════════════════════════════════════════════════════════════
def granularidade(passo_s: float | None) -> str:
    if not passo_s:
        return "sem dado"
    return "15 min" if passo_s <= 20 * 60 else "hora" if passo_s <= 90 * 60 else "dia" if passo_s <= 2 * 86400 else "mês"


def limpar_serie(pontos: list[dict], P: dict, grandeza: str = "", faixa: tuple | None = None, agora: float | None = None) -> dict:
    """pontos: [{id, ts, valor}] na ordem em que chegaram. Devolve cada ponto com original, valor (None = não usar) e
    marcas, mais o resumo, a granularidade nativa (o passo mediano, que não é mudado), as lacunas e a perda de dados."""
    out = [{"id": p.get("id"), "ts": p["ts"], "original": p["valor"], "valor": p["valor"], "marcas": []} for p in pontos]
    vistos, ult = set(), None
    for o in out:
        if o["ts"] is None or o["ts"] <= 0:
            o["marcas"].append("ts_invalido")
        elif agora is not None and o["ts"] > agora + 300:
            o["marcas"].append("ts_futuro")
        elif o["ts"] in vistos:
            o["marcas"].append("ts_duplicado")
        elif ult is not None and o["ts"] < ult:
            o["marcas"].append("ts_fora_de_ordem")       # fica: só a ordem é corrigida para as contas
        if o["ts"]:
            vistos.add(o["ts"])
            ult = o["ts"] if ult is None else max(ult, o["ts"])
        v = o["original"]
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            o["marcas"].append("impossivel")
        elif v < 0 and grandeza in NAO_NEGATIVAS:
            o["marcas"].append("negativo")
        elif faixa and ((faixa[0] is not None and grandeza in NAO_NEGATIVAS and v < faixa[0]) or (faixa[1] is not None and abs(v) > faixa[1])):
            o["marcas"].append("impossivel")
    # atípico: salto isolado (pico ou vale) — o ponto se afasta do anterior E do seguinte no mesmo sentido, e o menor dos
    # dois saltos, em z robusto sobre o MAD dos passos da série, passa de validacao.limpeza_z. Degrau de operação (liga às
    # 8 h, desliga às 18 h) e o ciclo do dia não viram atípico.
    bons = sorted([o for o in out if not o["marcas"] or o["marcas"] == ["ts_fora_de_ordem"]], key=lambda o: o["ts"])
    vals = [o["original"] for o in bons]
    if len(vals) >= 5:
        mad = statistics.median([abs(b - a) for a, b in zip(vals, vals[1:])])
        if mad:
            for i in range(1, len(vals) - 1):
                d1, d2 = vals[i] - vals[i - 1], vals[i] - vals[i + 1]
                if d1 * d2 > 0 and 0.6745 * min(abs(d1), abs(d2)) / mad > P["validacao.limpeza_z"]:
                    bons[i]["marcas"].append("atipico")
    seq, n_trav = [], int(P["validacao.travado_n"])
    ordem = sorted([o for o in out if o["ts"] and o["ts"] > 0 and "ts_duplicado" not in o["marcas"]], key=lambda o: o["ts"])
    for o in ordem + [None]:
        if o is not None and seq and o["original"] == seq[-1]["original"]:
            seq.append(o)
            continue
        if len(seq) >= n_trav:
            for s in seq[1:]:
                s["marcas"].append("travado")
        seq = [o] if o is not None else []
    for o in out:
        if any(mk != "ts_fora_de_ordem" for mk in o["marcas"]):
            o["valor"] = None
    validos = sorted(o["ts"] for o in out if o["valor"] is not None)
    passos = [b - a for a, b in zip(validos, validos[1:]) if b > a]
    passo = statistics.median(passos) if passos else None
    lacunas = [{"de": a, "ate": b} for a, b in zip(validos, validos[1:]) if passo and b - a > 2 * passo]
    esperado = int(round((validos[-1] - validos[0]) / passo)) + 1 if passo else len(validos)
    perda = (1 - len(validos) / esperado) * 100 if esperado else 0.0
    resumo: dict[str, int] = {}
    for o in out:
        for mk in o["marcas"]:
            resumo[mk] = resumo.get(mk, 0) + 1
    return {"pontos": out, "resumo": resumo, "passo_s": passo, "granularidade": granularidade(passo), "lacunas": lacunas,
            "n": len(out), "validos": len(validos), "perda_pct": max(0.0, perda),
            "perda_ok": max(0.0, perda) <= P["validacao.perda_dados_max_pct"]}


# ══ M&V 2.0: economia acumulada e alarmes (FDD) ═════════════════════════════════════════════
def economia_acumulada(modelo: dict | None, dias: list[dict]) -> list[dict]:
    """dias: [{dia, y, x}] do período de relatório → [{dia, esperado, medido, economia, acumulada}]."""
    out, acc = [], 0.0
    for d in dias:
        e = prever(modelo, d.get("x"))
        if e is None or d.get("y") is None:
            continue
        acc += e - d["y"]
        out.append({"dia": d["dia"], "esperado": e, "medido": d["y"], "economia": e - d["y"], "acumulada": acc})
    return out


def trechos_fdd(serie: list[dict], P: dict) -> list[dict]:
    """Dias seguidos (≥ validacao.fdd_dias_min) com o medido acima do esperado pela linha de base mais que o limite."""
    lim, nmin = P["validacao.desvio_limite_pct"], int(P["validacao.fdd_dias_min"])
    out, cur = [], []
    for s in serie + [None]:
        if s is not None and s["esperado"] > 0 and (s["medido"] - s["esperado"]) / s["esperado"] * 100 > lim:
            cur.append(s)
            continue
        if len(cur) >= nmin:
            e, m = sum(c["esperado"] for c in cur), sum(c["medido"] for c in cur)
            out.append({"inicio": cur[0]["dia"], "fim": cur[-1]["dia"], "dias": len(cur), "esperado": e, "medido": m,
                        "desvio_pct": (m - e) / e * 100})
        cur = []
    return out
