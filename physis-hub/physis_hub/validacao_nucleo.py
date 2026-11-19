"""Validação (M&V) · núcleo M&V 2.0: dados de intervalo, modelos diário e horário, escolha por validação cruzada,
deriva (CUSUM), Monte Carlo, eventos não rotineiros (NRE), FDD contra o intervalo de previsão, projeção por persistência,
R$ em risco, pacote de auditoria reproduzível e contrafactual da opção D. Só biblioteca padrão; funciona sem internet.

Métodos citados só pelo nome (IPMVP, ISO 50015, ISO 50006, ASHRAE Guideline 14, CalTRACK, NMEC Rulebook); nenhum texto
deles foi copiado. Todo limite é premissa validacao.* com status "conferir". O gerador aleatório do Monte Carlo tem
semente fixa (tirada do resumo dos dados), então o mesmo dado dá sempre o mesmo intervalo.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from datetime import datetime
from statistics import NormalDist

from . import aprendizado
from . import validacao_modelos as vm

POLITICAS = {"excluir": "Excluir o período sem dado", "linear": "Preencher por interpolação linear",
             "modelo": "Preencher pelo modelo da linha de base"}
CLASSES_NRE = {"equipamento_novo": "Equipamento novo (subiu a carga de base, noite e dia)",
               "ocupacao": "Mudança de ocupação (subiu só nas horas ocupadas)",
               "horario": "Mudança de horário (o consumo mudou de hora)",
               "indefinida": "Mudança de nível sem padrão claro"}
FONTES_INCERTEZA = {"medidor": "Exatidão do medidor", "modelo": "Erro do modelo", "faltantes": "Dados faltantes preenchidos"}


def canonico(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def resumo(obj) -> str:
    return hashlib.sha256(canonico(obj)).hexdigest()


# ══ Dados de intervalo → dia e hora (política de faltantes) ═════════════════════════════════
def agregar(pontos: list[dict], fuso, politica: str = "excluir", cobertura_min_pct: float = 90.0) -> dict:
    """pontos limpos (validacao_modelos.limpar_serie: ts, valor = potência em kW, None = não usar). A energia de cada
    intervalo é potência × passo. Política: excluir (dia com cobertura abaixo do mínimo sai), linear (intervalos faltantes
    preenchidos entre os vizinhos) ou modelo (o dia vazio é preenchido depois, pela linha de base). Devolve dias, horas e
    a taxa de faltantes de cada mês."""
    val = sorted((p["ts"], p["valor"]) for p in pontos if p.get("valor") is not None and p.get("ts"))
    if len(val) < 2:
        return {"dias": {}, "horas": {}, "faltantes": {}, "politica": politica, "passo_s": None}
    passo = statistics.median([b[0] - a[0] for a, b in zip(val, val[1:]) if b[0] > a[0]])
    serie = list(val)
    imput = set()
    if politica == "linear":
        cheia = []
        for (t0, v0), (t1, v1) in zip(val, val[1:]):
            cheia.append((t0, v0))
            k = int(round((t1 - t0) / passo))
            for j in range(1, k):
                t = t0 + j * passo
                cheia.append((t, v0 + (v1 - v0) * j / k))
                imput.add(t)
        cheia.append(val[-1])
        serie = cheia
    por_dia_n: dict[str, int] = {}
    dias: dict[str, dict] = {}
    horas: dict[str, float] = {}
    for t, v in serie:
        dt = datetime.fromtimestamp(t, fuso)
        d, h = dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m-%dT%H")
        e = v * passo / 3600.0
        x = dias.setdefault(d, {"y": 0.0, "n": 0, "imputados": 0})
        x["y"] += e
        x["n"] += 1
        x["imputados"] += t in imput
        horas[h] = horas.get(h, 0.0) + e
        if t not in imput:
            por_dia_n[d] = por_dia_n.get(d, 0) + 1
    esperado = 86400 / passo
    falt: dict[str, dict] = {}
    for d, x in list(dias.items()):
        x["cobertura_pct"] = min(100.0, por_dia_n.get(d, 0) / esperado * 100)
        m = falt.setdefault(d[:7], {"esperados": 0.0, "medidos": 0})
        m["esperados"] += esperado
        m["medidos"] += por_dia_n.get(d, 0)
        if x["n"] < esperado * 0.999 and politica != "excluir":
            x["y"] *= esperado / max(1, x["n"])                 # escala o que faltou no fim/início do dia
        if politica == "excluir" and x["cobertura_pct"] < cobertura_min_pct:
            x["excluido"] = True
    for m in falt.values():
        m["faltantes_pct"] = max(0.0, (1 - m["medidos"] / m["esperados"]) * 100) if m["esperados"] else None
    return {"dias": dias, "horas": horas, "faltantes": falt, "politica": politica, "passo_s": passo}


# ══ Modelos: diário (2P a 5P) e horário (hora do dia + temperatura), escolha por validação cruzada ═══
def ajustar_horario(horas: list[tuple[str, float, float]], cp: float | None = None) -> dict | None:
    """y_h = a_hora + b1·max(0, cp − T) + b2·max(0, T − cp): 24 constantes da hora do dia e o ponto de mudança da
    temperatura. horas: [(AAAA-MM-DDTHH, y, T)]."""
    if len(horas) < 24 * 7:
        return None
    ts = [h[2] for h in horas]
    cp = statistics.median(ts) if cp is None else cp
    X = [[1.0 if int(h[0][11:13]) == k else 0.0 for k in range(24)] + [max(0.0, cp - h[2]), max(0.0, h[2] - cp)] for h in horas]
    coef = aprendizado.regressao([[1.0] + r[1:] for r in X], [h[1] for h in horas])
    m = {"tipo": "horario", "forma": "horario", "cps": [cp], "coef": coef}
    yh = [prever_horario(m, h[0], h[2]) for h in horas]
    m["metricas"] = vm.metricas([h[1] for h in horas], yh, 26)
    return m


def prever_horario(m: dict, quando: str, t: float) -> float:
    k = int(quando[11:13])
    c = m["coef"]
    return c[0] + (c[k] if k > 0 else 0.0) + c[24] * max(0.0, m["cps"][0] - t) + c[25] * max(0.0, t - m["cps"][0])


def validacao_cruzada(tipo: str, xs: list[float], ys: list[float], k: int) -> float | None:
    """CV(RMSE) fora da amostra em k blocos seguidos (o tempo não se mistura entre treino e teste)."""
    n = len(xs)
    if n < 2 * k:
        return None
    err, tot = 0.0, 0.0
    for f in range(k):
        a, b = f * n // k, (f + 1) * n // k
        tr_x, tr_y = xs[:a] + xs[b:], ys[:a] + ys[b:]
        m = vm.ajustar_cp(tipo, tr_x, tr_y) if tipo != "ML" else vm.ajustar_ml(tr_x, tr_y, 7)
        if not m:
            return None
        for x, y in zip(xs[a:b], ys[a:b]):
            err += (y - vm.prever(m, x)) ** 2
            tot += y
    return math.sqrt(err / n) / (tot / n) * 100 if tot else None


def escolher_por_cv(xs: list[float], ys: list[float], P: dict) -> dict:
    """Ajusta 2P a 5P (e o k-NN com dados bastantes) e escolhe o de menor erro na validação cruzada; empate (dentro de
    validacao.modelo_ganho_min_pct) fica com o mais simples."""
    k = int(P["validacao.cv_k"])
    tipos = list(vm.P_MODELO) + (["ML"] if len(xs) >= P["validacao.ml_amostra_min"] else [])
    cands = []
    for t in tipos:
        m = vm.ajustar_cp(t, xs, ys) if t != "ML" else vm.ajustar_ml(xs, ys, int(P["validacao.ml_k"]))
        if not m:
            continue
        m["cv_fora_pct"] = validacao_cruzada(t, xs, ys, k)
        if m["cv_fora_pct"] is not None:
            cands.append(m)
    if not cands:
        return {"candidatos": [], "escolhido": None}
    best = min(c["cv_fora_pct"] for c in cands)
    ordem = sorted(cands, key=lambda c: vm.P_MODELO.get(c["tipo"], 9))
    esc = next(c for c in ordem if c["cv_fora_pct"] <= best * (1 + P["validacao.modelo_ganho_min_pct"] / 100))
    return {"candidatos": cands, "escolhido": esc}


def aceite_minimo(m: dict | None, P: dict) -> dict:
    """Ajuste mínimo (CalTRACK/NMEC citados só pelo nome): R² acima de validacao.aceite_r2_min OU CV(RMSE) abaixo de
    validacao.aceite_cvrmse_ou_max_pct."""
    if not m:
        return {"ok": False, "motivo": "sem modelo"}
    x = m["metricas"]
    ok = (x["r2"] is not None and x["r2"] > P["validacao.aceite_r2_min"]) or \
         (x["cv_rmse_pct"] is not None and x["cv_rmse_pct"] < P["validacao.aceite_cvrmse_ou_max_pct"])
    return {"ok": ok, "motivo": "" if ok else "R² e CV(RMSE) fora do mínimo"}


def _inversa(a: list[list[float]]) -> list[list[float]] | None:
    n = len(a)
    m = [list(r) + [1.0 if i == j else 0.0 for j in range(n)] for i, r in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        if abs(m[p][c]) < 1e-12:
            return None
        m[c], m[p] = m[p], m[c]
        piv = m[c][c]
        m[c] = [v / piv for v in m[c]]
        for r in range(n):
            if r != c and m[r][c]:
                f = m[r][c]
                m[r] = [v - f * w for v, w in zip(m[r], m[c])]
    return [r[n:] for r in m]


def diagnostico(m: dict, xs: list[float], ys: list[float]) -> dict:
    """Valores-p dos coeficientes (t = b ÷ erro do coeficiente, aproximação normal) e análise dos resíduos: média,
    Durbin-Watson, autocorrelação, assimetria, curtose e parte fora de ±2σ."""
    if not m or m["tipo"] in ("ML", "horario"):
        return {"p_valores": [], "residuos": {}}
    X = [vm._colunas(m["forma"], x, tuple(m["cps"])) for x in xs]
    res = [y - vm.prever(m, x) for x, y in zip(xs, ys)]
    n, p = len(res), len(X[0])
    s2 = sum(r * r for r in res) / max(1, n - p)
    inv = _inversa([[sum(r[i] * r[j] for r in X) for j in range(p)] for i in range(p)])
    pv = []
    for i, b in enumerate(m["coef"]):
        se = math.sqrt(max(0.0, inv[i][i] * s2)) if inv else None
        t = b / se if se else None
        pv.append({"coef": b, "erro": se, "t": t, "p": None if t is None else 2 * (1 - NormalDist().cdf(abs(t)))})
    sd = math.sqrt(s2) if s2 > 0 else 0.0
    mr = sum(res) / n
    dw = sum((res[i] - res[i - 1]) ** 2 for i in range(1, n)) / sum(r * r for r in res) if any(res) else None
    pad = statistics.pstdev(res) or 1.0
    return {"p_valores": pv, "residuos": {"media": mr, "durbin_watson": dw, "autocorrelacao": vm.autocorrelacao(res),
            "assimetria": sum(((r - mr) / pad) ** 3 for r in res) / n, "curtose": sum(((r - mr) / pad) ** 4 for r in res) / n - 3,
            "fora_2sigma_pct": sum(abs(r) > 2 * sd for r in res) / n * 100 if sd else 0.0}}


def versao_modelo(m: dict, dados_hash: str, ciclo: str) -> dict:
    """Versão do modelo com os parâmetros e o resumo: um auditor refaz a conta a partir dos dados brutos."""
    par = {"tipo": m["tipo"], "forma": m["forma"], "cps": m["cps"], "coef": m["coef"], "k": m.get("k")}
    return {"ciclo": ciclo, "parametros": par, "dados_hash": dados_hash, "hash": resumo({"parametros": par, "dados": dados_hash})}


# ══ Deriva (CUSUM) ════════════════════════════════════════════════════════════════════════════
def cusum(valores: list[float], P: dict, media: float | None = None, desvio: float | None = None) -> dict:
    """CUSUM tabular em z: S⁺ = max(0, S⁺ + z − k), S⁻ = max(0, S⁻ − z − k); alarme quando passa de h (validacao.cusum_k e
    validacao.cusum_h). Sem média e desvio de referência, usa os da própria série."""
    v = [x for x in valores if x is not None]
    if len(v) < 3:
        return {"alarme": False, "indice": None, "lado": None, "s_mais": [], "s_menos": []}
    mu = statistics.mean(v) if media is None else media
    sd = (statistics.pstdev(v) if desvio is None else desvio) or 1.0
    k, h = P["validacao.cusum_k"], P["validacao.cusum_h"]
    sp = sn = 0.0
    smais, smenos, idx, lado = [], [], None, None
    for i, x in enumerate(v):
        z = (x - mu) / sd
        sp, sn = max(0.0, sp + z - k), max(0.0, sn - z - k)
        smais.append(sp)
        smenos.append(sn)
        if idx is None and (sp > h or sn > h):
            idx, lado = i, "acima" if sp > h else "abaixo"
    return {"alarme": idx is not None, "indice": idx, "lado": lado, "s_mais": smais, "s_menos": smenos}


# ══ Intervalo de previsão, FDD, persistência e R$ em risco ═══════════════════════════════════
def intervalo_previsao(yhat: float, erro_padrao: float, n: int, P: dict) -> tuple[float, float]:
    """ŷ ± t·s·√(1 + 1/n), t da Student no nível validacao.ip_confianca_pct."""
    t = vm.t_student(P["validacao.ip_confianca_pct"], max(1, n - 2))
    d = t * erro_padrao * math.sqrt(1 + 1 / max(1, n))
    return yhat - d, yhat + d


def fdd_intervalo(serie: list[dict], erro_padrao: float, n: int, P: dict, tarifa: float | None = None) -> list[dict]:
    """Alarme só quando o medido sai do intervalo de previsão por validacao.fdd_dias_min dias seguidos (não por um
    desvio em % simples). R$ em risco = energia fora do intervalo × tarifa do plano (sem tarifa: None)."""
    nmin, out, cur = int(P["validacao.fdd_dias_min"]), [], []
    for s in serie + [None]:
        if s is not None:
            lo, hi = intervalo_previsao(s["esperado"], erro_padrao, n, P)
            if s["medido"] > hi or s["medido"] < lo:
                cur.append(dict(s, lim_inf=lo, lim_sup=hi, lado="acima" if s["medido"] > hi else "abaixo"))
                continue
        if len(cur) >= nmin:
            exc = sum((c["medido"] - c["lim_sup"]) if c["lado"] == "acima" else 0.0 for c in cur)
            e, m = sum(c["esperado"] for c in cur), sum(c["medido"] for c in cur)
            out.append({"inicio": cur[0]["dia"], "fim": cur[-1]["dia"], "dias": len(cur), "esperado": e, "medido": m,
                        "desvio_pct": (m - e) / e * 100 if e else None, "lado": cur[0]["lado"], "excesso": exc,
                        "rs_em_risco": exc * tarifa if tarifa is not None else None})
        cur = []
    return out


def ordenar_por_risco(alertas: list[dict]) -> list[dict]:
    """Maior R$ em risco primeiro; sem tarifa, pela energia em excesso, depois deles."""
    return sorted(alertas, key=lambda a: (a.get("rs_em_risco") is None, -(a.get("rs_em_risco") or 0), -(a.get("excesso") or 0)))


def projecao_persistencia(serie: list[dict], dias_total: int, meta: float | None, tarifa: float | None = None) -> dict:
    """Projeta a economia até o fim do período de relatório pela persistência da média diária até agora e marca
    "risco de não atingir a meta" antes de o período acabar."""
    d = len(serie)
    if not d:
        return {"projetada": None, "meta": meta, "risco": None}
    acc = serie[-1]["acumulada"]
    proj = acc / d * dias_total
    risco = None if meta is None else proj < meta
    return {"ate_agora": acc, "dias": d, "dias_total": dias_total, "projetada": proj, "meta": meta, "risco": risco,
            "falta": None if meta is None else max(0.0, meta - proj),
            "rs_em_risco": None if meta is None or tarifa is None else max(0.0, meta - proj) * tarifa}


# ══ Monte Carlo ═══════════════════════════════════════════════════════════════════════════════
def monte_carlo(esperado: float, medido: float, m_dias: int, erro_padrao: float, rho: float, exatidao_pct: float | None,
                imputados: int, P: dict, semente: str, so: str | None = None) -> dict:
    """Economia = Σ esperado + erro do modelo − Σ medido × (1 + erro do medidor) − erro dos dias preenchidos.
    Fontes: exatidão do medidor (tratada como limite a 95 %: σ = exatidão ÷ 1,96 [CONFERIR]), erro do modelo (σ do dia
    × √(m·(1 + ρ)/(1 − ρ))) e dados faltantes (σ do dia × √(dias preenchidos)). Semente fixa: mesmo dado, mesmo IC."""
    rnd = random.Random(semente)
    n = int(P["validacao.mc_n"])
    r = max(-0.9, min(0.9, rho))
    s_mod = erro_padrao * math.sqrt(m_dias * (1 + r) / (1 - r))
    s_med = (exatidao_pct / 100 / 1.96) if exatidao_pct is not None else 0.0
    s_fal = erro_padrao * math.sqrt(max(0, imputados))
    usa = lambda f: so is None or so == f
    am = sorted(esperado + (rnd.gauss(0, s_mod) if usa("modelo") else 0.0)
                - medido * (1 + (rnd.gauss(0, s_med) if usa("medidor") else 0.0))
                - (rnd.gauss(0, s_fal) if usa("faltantes") else 0.0) for _ in range(n))
    a = (100 - P["validacao.mc_confianca_pct"]) / 200
    lo, hi = am[int(a * (n - 1))], am[int((1 - a) * (n - 1))]
    return {"economia": esperado - medido, "media": statistics.mean(am), "ic_inf": lo, "ic_sup": hi,
            "confianca_pct": P["validacao.mc_confianca_pct"], "n": n, "desvio": statistics.pstdev(am),
            "exatidao_conhecida": exatidao_pct is not None}


def sensibilidade(args: dict, P: dict, semente: str) -> list[dict]:
    """Cada fonte sozinha (as outras zeradas): a parte da variância de cada uma, da maior para a menor."""
    v = {f: monte_carlo(**args, P=P, semente=semente, so=f)["desvio"] ** 2 for f in FONTES_INCERTEZA}
    tot = sum(v.values()) or 1.0
    return sorted(({"fonte": f, "nome": FONTES_INCERTEZA[f], "variancia": x, "parte_pct": x / tot * 100} for f, x in v.items()),
                  key=lambda d: -d["variancia"])


# ══ Eventos não rotineiros (NRE) ═════════════════════════════════════════════════════════════
def detectar_nre(residuos: list[tuple[str, float]], esperado_medio: float, P: dict, horas: dict | None = None) -> dict | None:
    """Degrau sustentado nos resíduos (medido − esperado) que o modelo não explica: o ponto que mais separa a média de
    antes da de depois, com os dois lados de pelo menos validacao.nre_dias_min dias, tamanho acima de
    validacao.nre_limite_pct do esperado e t acima de validacao.nre_z. Classe pelo perfil dos RESÍDUOS horários (medido − modelo
    horário), antes × depois do degrau, quando houver dado por hora."""
    nmin = int(P["validacao.nre_dias_min"])
    v = [r for _, r in residuos]
    n = len(v)
    if n < 2 * nmin or not esperado_medio:
        return None
    melhor = None
    for i in range(nmin, n - nmin + 1):
        a, b = v[:i], v[i:]
        ma, mb = statistics.mean(a), statistics.mean(b)
        sd = math.sqrt((statistics.pvariance(a) * len(a) + statistics.pvariance(b) * len(b)) / n) or 1e-9
        t = abs(mb - ma) / (sd * math.sqrt(1 / len(a) + 1 / len(b)))
        if melhor is None or t > melhor[0]:
            melhor = (t, i, ma, mb)
    t, i, ma, mb = melhor
    nivel = mb - ma
    if t < P["validacao.nre_z"] or abs(nivel) / esperado_medio * 100 < P["validacao.nre_limite_pct"]:
        return None
    classe = "indefinida"
    if horas:
        ini = residuos[i][0]
        perfil = lambda hs, pos: [statistics.mean([v for k, v in hs.items() if int(k[11:13]) == h and ((k[:10] >= ini) == pos)] or [0.0]) for h in range(24)]
        depois, antes = perfil(horas, True), perfil(horas, False)          # resíduos do relatório: antes × depois do degrau
        dif = [d - a for d, a in zip(depois, antes)]
        noite, dia = statistics.mean(dif[0:5]), statistics.mean(dif[9:17])
        sobe = [h for h in range(24) if dif[h] > 0.5 * max(dif)] if max(dif) > 0 else []
        desce = [h for h in range(24) if dif[h] < 0.5 * min(dif)] if min(dif) < 0 else []
        if sobe and desce and abs(min(dif)) > 0.5 * max(dif):
            classe = "horario"                                   # umas horas subiram e outras desceram: a carga mudou de hora
        elif dia and noite / dia > 0.6:
            classe = "equipamento_novo"
        elif dia and noite / dia < 0.3:
            classe = "ocupacao"
    dias_depois = n - i
    return {"inicio": residuos[i][0], "dias_depois": dias_depois, "nivel_dia": nivel, "t": t,
            "nivel_pct": nivel / esperado_medio * 100, "classe": classe, "classe_nome": CLASSES_NRE[classe],
            "impacto": nivel * dias_depois, "ajuste_proposto": nivel * dias_depois, "situacao": "pendente"}


# ══ Pacote de auditoria (reproduzível) ═══════════════════════════════════════════════════════
def calcular_economia(pacote: dict, P: dict) -> dict:
    """A conta inteira a partir do pacote: limpa os brutos, agrega por dia, prevê com os parâmetros guardados e soma.
    Serve tanto para gerar o pacote quanto para o auditor refazer a conta."""
    from datetime import timedelta, timezone
    fuso = timezone(timedelta(minutes=pacote["fuso_min"]))
    lim = vm.limpar_serie(pacote["dados_brutos"], P, pacote["grandeza"], tuple(pacote["faixa"]), pacote["agora"])
    ag = agregar(lim["pontos"], fuso, pacote["politica"], P["validacao.cobertura_min_pct"])
    par = pacote["modelo"]["parametros"]
    mod = dict(par, metricas={})
    esp = med = 0.0
    dias = 0
    for d, x in sorted(ag["dias"].items()):
        if not (pacote["relatorio"][0] <= d <= pacote["relatorio"][1]) or x.get("excluido"):
            continue
        t = pacote["temperaturas"].get(d)
        if t is None:
            continue
        esp += vm.prever(mod, t)
        med += x["y"]
        dias += 1
    marcas = {str(o["id"]): o["marcas"] for o in lim["pontos"] if o["marcas"]}
    return {"esperado": esp, "medido": med, "economia": esp - med, "dias": dias, "marcas": marcas,
            "faltantes": ag["faltantes"]}


def montar_pacote(brutos: list[dict], grandeza: str, faixa: tuple, agora: float, fuso_min: int, politica: str,
                  temperaturas: dict, modelo_versao: dict, relatorio: tuple[str, str], P: dict, premissas_usadas: dict) -> dict:
    pac = {"formato": "physis-validacao-auditoria/1", "grandeza": grandeza, "faixa": list(faixa), "agora": agora, "fuso_min": fuso_min,
           "politica": politica, "dados_brutos": brutos, "temperaturas": temperaturas, "modelo": modelo_versao,
           "relatorio": list(relatorio), "premissas": premissas_usadas}
    calc = calcular_economia(pac, P)
    pac["limpeza"] = calc["marcas"]
    pac["calculo"] = {k: calc[k] for k in ("esperado", "medido", "economia", "dias")}
    pac["hashes"] = {"dados_brutos": resumo(brutos), "temperaturas": resumo(temperaturas), "modelo": modelo_versao["hash"],
                     "calculo": resumo(pac["calculo"])}
    return pac


def conferir_pacote(pac: dict, P: dict) -> dict:
    """O auditor refaz a conta a partir do pacote e confere os resumos."""
    calc = calcular_economia(pac, P)
    novo = {k: calc[k] for k in ("esperado", "medido", "economia", "dias")}
    return {"ok": resumo(novo) == pac["hashes"]["calculo"] and resumo(pac["dados_brutos"]) == pac["hashes"]["dados_brutos"],
            "economia": novo["economia"], "economia_pacote": pac["calculo"]["economia"]}


# ══ Opção D: contrafactual pela simulação térmica da plataforma ═══════════════════════════════
def contrafactual_d(sim: dict, temperaturas: dict) -> dict:
    """"E se" da opção D com o motor de simulação da plataforma (simulacao.termica.perda_envoltoria): carga de condução
    da envoltória antes e depois da medida, por dia, ÷ COP do plano. Guarda o programa, a versão e o resumo dos arquivos
    de entrada e saída. A calibração contínua do gêmeo digital é Fase 2."""
    from .simulacao import termica
    ent = {"antes": sim["envoltoria_antes"], "depois": sim["envoltoria_depois"], "ti": sim["ti"], "cop": sim["cop"],
           "temperaturas": temperaturas}
    dias = {}
    for d, te in sorted(temperaturas.items()):
        if te is None:
            continue
        a = termica.perda_envoltoria(sim["envoltoria_antes"], sim["ti"], te)["w_total"]
        b = termica.perda_envoltoria(sim["envoltoria_depois"], sim["ti"], te)["w_total"]
        dias[d] = {"kwh_antes": abs(a) * 24 / 1000 / sim["cop"], "kwh_depois": abs(b) * 24 / 1000 / sim["cop"]}
    saida = {"dias": dias, "economia_kwh": sum(x["kwh_antes"] - x["kwh_depois"] for x in dias.values())}
    return {"software": "Sistema Physis · simulacao.termica (perda_envoltoria)", "versao": "validacao-2",
            "arquivos": [{"nome": "entrada.json", "papel": "entrada", "sha256": resumo(ent)},
                         {"nome": "saida.json", "papel": "saida", "sha256": resumo(saida)}], "saida": saida}


# ══ Perfil PEE (ANEEL) e amostragem ══════════════════════════════════════════════════════════
PERFIS = {"geral": "Geral (IPMVP)", "pee": "PEE (ANEEL)"}
PREMISSAS_PEE = ("validacao.pee.confianca_pct", "validacao.pee.precisao_pct", "validacao.pee.amostra_min",
                 "validacao.pee.duracao_medicao_dias", "validacao.pee.vida_util_anos", "validacao.pee.taxa_desconto_pct",
                 "validacao.pee.rcb_max", "validacao.pee.custo_mv_max_pct", "validacao.pee.prazo_relatorio_dias")


def tamanho_amostra(N: int, cv: float, confianca_pct: float, precisao_pct: float) -> int:
    """Fórmula estatística GENÉRICA (não é a da ANEEL): n₀ = (z·CV ÷ e)², com correção de população finita
    n = n₀ ÷ (1 + n₀ ÷ N). CV e precisão em fração; z da normal bicaudal no nível de confiança."""
    z = NormalDist().inv_cdf(0.5 + confianca_pct / 200)
    n0 = (z * cv / (precisao_pct / 100)) ** 2
    return max(1, min(int(N), math.ceil(n0 / (1 + n0 / N)))) if N else 0


def precisao_alcancada(N: int, n: int, media: float, desvio: float, confianca_pct: float) -> float | None:
    """Precisão relativa alcançada depois de medir (genérica): z·(s ÷ média) ÷ √n · √(1 − n ÷ N), em %."""
    if not n or not media or not N:
        return None
    z = NormalDist().inv_cdf(0.5 + confianca_pct / 200)
    return z * (desvio / media) / math.sqrt(n) * math.sqrt(max(0.0, 1 - n / N)) * 100


def plano_amostral(estratos: list[dict], confianca_pct: float | None, precisao_pct: float | None) -> dict:
    """Muitas unidades parecidas (lâmpadas, geladeiras, aparelhos de ar): população, estratos, tamanho da amostra pela
    confiança e precisão (do plano; a exigência do PEE é [MARCADOR]) e a precisão alcançada quando houver medição."""
    if confianca_pct is None or precisao_pct is None:
        return {"ok": False, "motivo": "confiança e precisão ainda sem número (premissas validacao.pee.* " + "[MARCADOR])",
                "estratos": estratos, "populacao": sum(int(e.get("N") or 0) for e in estratos)}
    out = []
    for e in estratos:
        n = tamanho_amostra(int(e.get("N") or 0), float(e.get("cv") or 0.5), confianca_pct, precisao_pct)
        alc = precisao_alcancada(int(e.get("N") or 0), int(e.get("n_medido") or 0), e.get("media"), e.get("desvio") or 0.0, confianca_pct) \
            if e.get("media") else None
        out.append(dict(e, n_amostra=n, precisao_alcancada_pct=alc, atende=None if alc is None else alc <= precisao_pct))
    return {"ok": True, "confianca_pct": confianca_pct, "precisao_pct": precisao_pct, "estratos": out,
            "populacao": sum(int(e.get("N") or 0) for e in estratos), "amostra_total": sum(e["n_amostra"] for e in out),
            "formula": "genérica: n₀ = (z·CV ÷ e)²; n = n₀ ÷ (1 + n₀ ÷ N) (não é a fórmula da ANEEL)"}


def resumo_pee(pee: dict, P: dict) -> dict:
    """Campos do perfil PEE e o teste do custo da M&V. Toda exigência numérica vem das premissas validacao.pee.*, que
    ficam [MARCADOR] até o Guia de M&V da ANEEL ser lido: sem número, o teste diz que aguarda o Guia."""
    cm, ct = pee.get("custo_mv"), pee.get("custo_total")
    parte = cm / ct * 100 if cm is not None and ct else None
    lim = P.get("validacao.pee.custo_mv_max_pct")
    custo = {"parte_pct": parte, "limite_pct": lim,
             "situacao": "sem dado" if parte is None else "aguardando Guia" if lim is None else "dentro" if parte <= lim else "fora do limite"}
    exig = {k: P.get(k) for k in PREMISSAS_PEE}
    return {"energia_economizada_mwh_ano": pee.get("energia_economizada_mwh_ano"), "reducao_demanda_ponta_kw": pee.get("reducao_demanda_ponta_kw"),
            "rcb": pee.get("rcb"), "rcb_entradas": pee.get("rcb_entradas") or {}, "custo_mv": cm, "custo_total": ct, "custo_mv": cm,
            "erro_pct": pee.get("erro_pct"), "precisao_pct": pee.get("precisao_pct"), "confianca_pct": pee.get("confianca_pct"),
            "custo_check": custo, "exigencias": exig, "amostragem": plano_amostral(pee.get("estratos") or [], pee.get("confianca_pct"), pee.get("precisao_pct")),
            "aguardando_guia": [k for k, v in exig.items() if v is None]}
