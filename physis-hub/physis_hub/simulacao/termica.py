"""Transferência de calor, Fase 1 (espelho de SIMULACAO.termica em sistema/physis-simulacao.js).

1. u_valor: condução 1D em regime permanente através de camadas (U = 1/(Rsi + Σe/λ + ΣRar + Rse)), capacidade
   térmica e carbono incorporado por m², com as propriedades da base de materiais (nunca inventadas: material sem
   condutividade vira [MARCADOR]). Rsi e Rse são premissas (sim.termica.resistencias_superficiais).
2. transiente_1d: diferenças finitas (volumes finitos) 1D com método θ (θ = 0 explícito, 1 implícito, ½ Crank-
   Nicolson), contorno de convecção ou temperatura; com temperatura externa senoidal dá o atraso (h) e o fator de
   amortecimento (amplitude do fluxo interno ÷ U·amplitude externa).
3. placa_2d: diferenças finitas 2D em corte (ponte térmica, peça impressa), regime permanente por SOR
   (Gauss-Seidel sobrerrelaxado, ordem fixa de linhas) ou transiente explícito.
4. Convecção e radiação por coeficientes (premissas): h_conveccao_vento, h_radiacao, temperatura sol-ar.
"""
from __future__ import annotations

import math

from .comum import FaltaDado, MARCADOR, composicao, material, premissa, resultado, tridiagonal, usada

SIGMA = 5.670374419e-8      # constante de Stefan-Boltzmann (W/m²·K⁴), constante física


def resistencias(tipo: str = "parede") -> tuple[float, float]:
    rs = premissa("sim.termica.resistencias_superficiais") or {}
    v = rs.get(tipo) or rs.get("parede")
    if not v:
        raise FaltaDado(f"{MARCADOR} resistências superficiais (premissa sim.termica.resistencias_superficiais)")
    return float(v["rsi"]), float(v["rse"])


def camada(c: dict) -> dict:
    """Uma camada com as propriedades resolvidas. Aceita {material, espessura} (base), {resistencia, nome} (câmara
    de ar, valor tabelado) ou {nome, espessura, condutividade, densidade?, calor_especifico?} digitado."""
    if c.get("resistencia") is not None:
        return {"nome": c.get("nome", "câmara de ar"), "espessura": float(c.get("espessura") or 0.0), "R": float(c["resistencia"]),
                "k": None, "rho": None, "cp": None, "carbono": None, "ar": True}
    e = float(c["espessura"])
    if c.get("material"):
        m = material(c["material"])
        k, rho, cp = m.get("condutividade"), m.get("densidade"), m.get("calor_especifico")
        ci = (m.get("carbono_incorporado") or {}).get("valor")
        nome = m.get("nome", c["material"])
    else:
        k, rho, cp, ci, nome = c.get("condutividade"), c.get("densidade"), c.get("calor_especifico"), c.get("carbono"), c.get("nome", "camada")
    if k is None:
        raise FaltaDado(f"{MARCADOR} condutividade de '{nome}' (a base não tem; digite do ensaio ou da folha de dados)")
    return {"nome": nome, "espessura": e, "R": e / float(k), "k": float(k), "rho": rho, "cp": cp, "carbono": ci, "ar": False,
            "material": c.get("material")}


def u_valor(camadas: list, tipo: str = "parede", rsi: float | None = None, rse: float | None = None,
            ti: float | None = None, te: float | None = None) -> dict:
    r_si, r_se = resistencias(tipo)
    rsi = r_si if rsi is None else rsi
    rse = r_se if rse is None else rse
    cs = [camada(c) for c in camadas]
    rt = rsi + sum(c["R"] for c in cs) + rse
    u = 1.0 / rt
    ct = sum(c["espessura"] * c["rho"] * c["cp"] / 1000.0 for c in cs if not c["ar"] and c["rho"] and c["cp"])
    sem_ct = [c["nome"] for c in cs if not c["ar"] and not (c["rho"] and c["cp"])]
    massa = sum(c["espessura"] * c["rho"] for c in cs if not c["ar"] and c["rho"])
    carb = None
    if all(c["ar"] or (c["carbono"] is not None and c["rho"]) for c in cs):
        carb = sum(c["espessura"] * c["rho"] * c["carbono"] for c in cs if not c["ar"])
    temps = None
    if ti is not None and te is not None:
        q = u * (ti - te)
        temps, t = [], ti - q * rsi
        temps.append(t)
        for c in reversed(cs):          # camadas listadas de fora para dentro: anda de dentro para fora
            t -= q * c["R"]
            temps.append(t)
        temps.reverse()
    av = [f"{MARCADOR} densidade ou calor específico de: {', '.join(sem_ct)} (capacidade térmica incompleta)"] if sem_ct else []
    if carb is None:
        av.append(f"{MARCADOR} carbono incorporado de alguma camada: total por m² não calculado")
    return resultado(
        "Condução 1D em regime permanente, camadas homogêneas em série (método da ABNT NBR 15220-2, redação própria)",
        ["fluxo perpendicular à parede", "camadas homogêneas, sem pontes térmicas", "propriedades da base de materiais"],
        [usada("sim.termica.resistencias_superficiais", {"rsi": rsi, "rse": rse})],
        {"camadas": len(cs)},
        "Válido para camadas contínuas; pontes térmicas (montantes, pilares, juntas) pedem a placa_2d. "
        "Umidade muda a condutividade da terra e das fibras.",
        {"u": u, "r_total": rt, "ct_kj_m2k": ct, "massa_kg_m2": massa, "carbono_kgco2e_m2": carb,
         "temperaturas_interfaces": temps, "camadas": [{k: c[k] for k in ("nome", "espessura", "R", "k")} for c in cs]}, av)


def u_composicao(cid: str) -> dict:
    """U de uma composição da base (taipa, adobe, BTC, cob, fardo de palha, cânhamo-cal, telhado verde…)."""
    c = composicao(cid)
    tipo = "parede" if c.get("tipo") == "parede" else "cobertura_verao"
    if not c.get("camadas"):
        tab = c.get("tabelado") or {}
        return resultado("Valor tabelado da base (composição sem camadas)", ["valor de tabela"], [], None,
                         "Tabelado: não recalculado.", {"u": tab.get("u"), "ct_kj_m2k": tab.get("ct"), "id": cid,
                                                         "fonte_tabela": tab.get("fonte")})
    r = u_valor(c["camadas"], tipo)
    r["id"] = cid
    r["u_base"] = (c.get("calculo") or {}).get("u")
    return r


def perda_envoltoria(itens: list, ti: float, te: float) -> dict:
    """Carga de condução da envoltória (AVAC, câmara do Secador): Σ U·A·ΔT. itens: [{nome, area, u | camadas | composicao}]."""
    linhas, tot = [], 0.0
    for it in itens:
        if it.get("u") is not None:
            u = float(it["u"])
        elif it.get("composicao"):
            u = u_composicao(it["composicao"])["u"]
        else:
            u = u_valor(it["camadas"], it.get("tipo", "parede"))["u"]
        w = u * float(it["area"]) * (ti - te)
        tot += w
        linhas.append({"nome": it.get("nome", ""), "u": u, "area": float(it["area"]), "w": w})
    return resultado("Σ U·A·ΔT (condução em regime permanente)", ["ΔT constante", "sem radiação solar (use sol-ar)"],
                     [usada("sim.termica.resistencias_superficiais")], {"itens": len(itens)},
                     "Carga de pico simplificada; a carga térmica completa é a da aba AVAC (NBR 16401-1).",
                     {"itens": linhas, "w_total": tot})


# ── coeficientes ──
def h_conveccao_vento(v: float) -> float:
    c = premissa("sim.termica.h_conv_vento") or {}
    if c.get("a") is None or c.get("b") is None:
        raise FaltaDado(f"{MARCADOR} premissa sim.termica.h_conv_vento")
    return c["a"] + c["b"] * v


def h_radiacao(eps: float | None, t1_c: float, t2_c: float) -> float:
    """h_r = ε·σ·(T1² + T2²)·(T1 + T2) (K), troca com o entorno a T2."""
    eps = premissa("sim.termica.emissividade") if eps is None else eps
    a, b = t1_c + 273.15, t2_c + 273.15
    return eps * SIGMA * (a * a + b * b) * (a + b)


def sol_ar(te: float, alfa: float, irradiancia: float, he: float) -> float:
    """Temperatura sol-ar: Te + α·I/he (sem a parcela de onda longa)."""
    return te + alfa * irradiancia / he


# ── 1D transiente ──
def _func(spec, padrao: float = 0.0):
    if spec is None:
        return lambda t: padrao
    if isinstance(spec, (int, float)):
        return lambda t: float(spec)
    if "constante" in spec:
        v = float(spec["constante"])
        return lambda t: v
    if "senoide" in spec:
        s = spec["senoide"]
        m, a, per, f = float(s["media"]), float(s["amplitude"]), float(s.get("periodo_h", 24)) * 3600, float(s.get("fase_h", 0)) * 3600
        return lambda t: m + a * math.sin(2 * math.pi * (t - f) / per)
    if "serie" in spec:
        ser, ps = spec["serie"], float(spec["passo_s"])
        return lambda t: float(ser[min(len(ser) - 1, int(t // ps + 1e-9))])
    raise ValueError("temperatura: use número, {constante}, {senoide} ou {serie, passo_s}")


def _celulas(camadas: list, dx_max: float):
    cel = []
    for c in camadas:
        cc = camada(c)
        if cc["ar"]:
            raise FaltaDado("câmara de ar no transiente: troque por camada equivalente (k = e/R, ρ do ar) [MARCADOR]")
        if not (cc["rho"] and cc["cp"]):
            raise FaltaDado(f"{MARCADOR} densidade e calor específico de '{cc['nome']}' (transiente precisa)")
        n = max(1, int(math.ceil(cc["espessura"] / dx_max - 1e-9)))
        for _ in range(n):
            cel.append((cc["espessura"] / n, cc["k"], cc["rho"] * cc["cp"]))
    return cel


def transiente_1d(p: dict) -> dict:
    """p: camadas (de fora para dentro), dx_max (m, 0,01), dt (s, 300), theta (1), duracao_h (72), saida_s (3600),
    te e ti (número, {constante}, {senoide:{media, amplitude, periodo_h, fase_h}} ou {serie, passo_s}),
    contorno_ext / contorno_int ({tipo: conveccao, h} ou {tipo: temperatura}; padrão convecção com 1/Rse e 1/Rsi),
    t0 (número ou lista por célula), tipo ('parede' | 'cobertura_verao')."""
    tipo = p.get("tipo", "parede")
    rsi, rse = resistencias(tipo)
    cel = _celulas(p["camadas"], float(p.get("dx_max", 0.01)))
    n = len(cel)
    dt, theta = float(p.get("dt", 300.0)), float(p.get("theta", 1.0))
    dur = float(p.get("duracao_h", 72.0)) * 3600
    te_f, ti_f = _func(p.get("te"), 0.0), _func(p.get("ti"), 0.0)
    ce = p.get("contorno_ext") or {"tipo": "conveccao", "h": 1.0 / rse}
    ci = p.get("contorno_int") or {"tipo": "conveccao", "h": 1.0 / rsi}

    def g_bnd(c, dxk):
        return 1.0 / dxk if c.get("tipo") == "temperatura" else 1.0 / (dxk + 1.0 / float(c["h"]))
    g = [1.0 / (cel[i][0] / (2 * cel[i][1]) + cel[i + 1][0] / (2 * cel[i + 1][1])) for i in range(n - 1)]
    ge, gi = g_bnd(ce, cel[0][0] / (2 * cel[0][1])), g_bnd(ci, cel[-1][0] / (2 * cel[-1][1]))
    cap = [c[0] * c[2] for c in cel]
    gl = [ge] + g                     # condutância à esquerda (fora) de cada célula
    gr = g + [gi]                     # à direita (dentro)
    avisos = []
    nsub = 1
    if theta < 0.5:
        dtc = min(cap[i] / ((1 - theta) * (gl[i] + gr[i])) for i in range(n))
        if dt > 0.9 * dtc:
            nsub = int(math.ceil(dt / (0.9 * dtc)))
            avisos.append(f"passo explícito instável: cada passo foi dividido em {nsub} (limite {dtc:.1f} s)")
    h = dt / nsub
    t0 = p.get("t0", te_f(0.0))
    T = [float(x) for x in t0] if isinstance(t0, list) else [float(t0)] * n
    if len(T) != n:
        raise ValueError(f"t0 com {len(T)} valores; a malha tem {n} células")
    passos = int(round(dur / dt))
    cada = max(1, int(round(float(p.get("saida_s", 3600.0)) / dt)))
    U = 1.0 / (1.0 / ge + sum(1.0 / x for x in g) + 1.0 / gi)
    serie, todos = [], []

    def q_int(T, t):
        return gi * (T[-1] - ti_f(t))
    a, b, c, d = [0.0] * n, [0.0] * n, [0.0] * n, [0.0] * n
    t = 0.0
    serie.append({"t_h": 0.0, "te": te_f(0.0), "ti": ti_f(0.0), "q_int": q_int(T, 0.0), "t_meio": T[n // 2]})
    for k in range(1, passos + 1):
        for _ in range(nsub):
            t1 = t + h
            e0, e1, i0, i1 = te_f(t), te_f(t1), ti_f(t), ti_f(t1)
            for j in range(n):
                left0 = e0 if j == 0 else T[j - 1]
                right0 = i0 if j == n - 1 else T[j + 1]
                expl = gl[j] * (left0 - T[j]) + gr[j] * (right0 - T[j])
                a[j] = -theta * gl[j] if j > 0 else 0.0
                c[j] = -theta * gr[j] if j < n - 1 else 0.0
                b[j] = cap[j] / h + theta * (gl[j] + gr[j])
                d[j] = cap[j] / h * T[j] + (1 - theta) * expl
                if j == 0:
                    d[j] += theta * gl[j] * e1
                if j == n - 1:
                    d[j] += theta * gr[j] * i1
            T = tridiagonal(a, b, c, d) if theta > 0 else [d[j] / b[j] for j in range(n)]
            t = t1
        todos.append((t, te_f(t), q_int(T, t)))
        if k % cada == 0:
            serie.append({"t_h": t / 3600, "te": te_f(t), "ti": ti_f(t), "q_int": q_int(T, t), "t_meio": T[n // 2]})
    atraso = amort = None
    sen = (p.get("te") or {}).get("senoide") if isinstance(p.get("te"), dict) else None
    if sen:
        per = float(sen.get("periodo_h", 24)) * 3600
        ult = [x for x in todos if x[0] > dur - per + 1e-9]
        if dur >= 2 * per and ult:
            tq = max(ult, key=lambda x: x[2])
            tt = max(ult, key=lambda x: x[1])
            atraso = ((tq[0] - tt[0]) % per) / 3600
            qa = (max(x[2] for x in ult) - min(x[2] for x in ult)) / 2
            amort = qa / (U * float(sen["amplitude"])) if sen["amplitude"] else None
        else:
            avisos.append("duração menor que 2 períodos: atraso e amortecimento não calculados")
    return resultado(
        f"Diferenças finitas 1D (volumes finitos), método θ = {theta:g} ({'implícito' if theta == 1 else 'explícito' if theta == 0 else 'Crank-Nicolson' if theta == 0.5 else 'θ'})",
        ["propriedades constantes", "sem umidade nem mudança de fase", "contato perfeito entre camadas"],
        [usada("sim.termica.resistencias_superficiais", {"rsi": rsi, "rse": rse})],
        {"celulas": n, "dt_s": dt, "subpassos": nsub, "passos": passos},
        "Atraso e amortecimento valem para regime periódico (vários dias simulados). Terra crua e fibras mudam com a umidade.",
        {"serie": serie, "perfil_final": T, "x_celulas": _centros(cel), "u": U, "atraso_h": atraso, "amortecimento": amort}, avisos)


def _centros(cel):
    x, out = 0.0, []
    for c in cel:
        out.append(x + c[0] / 2)
        x += c[0]
    return out


# ── 2D ──
LADOS = ("topo", "base", "esquerda", "direita")


def placa_2d(p: dict) -> dict:
    """p: nx, ny, dx, dy (m); k (número ou lista ny·nx, linha 0 = topo); mascara (lista 0/1, 1 = material);
    contornos {topo|base|esquerda|direita: {tipo: temperatura, T} | {tipo: conveccao, h, T}} (sem = adiabático);
    vazio: contorno nas faces voltadas para células fora da máscara (padrão adiabático); fixos [[índice, T], …];
    regime permanente: omega (1,6), tol (1e-6 K), max_iter (20000).
    transiente: {rho_cp (número ou lista), t0, duracao_s, dt (opcional; limitado pela estabilidade explícita)}."""
    nx, ny, dx, dy = int(p["nx"]), int(p["ny"]), float(p["dx"]), float(p["dy"])
    N = nx * ny
    kk = p["k"]
    K = [float(kk)] * N if isinstance(kk, (int, float)) else [float(x) for x in kk]
    M = p.get("mascara") or [1] * N
    cont = p.get("contornos") or {}
    vazio = p.get("vazio")
    fixos = {int(i): float(t) for i, t in (p.get("fixos") or [])}
    # vizinhos: lista de (índice, G) e contorno: lista de (G, T, lado)
    viz = [[] for _ in range(N)]
    bnd = [[] for _ in range(N)]

    def gb(c, meia):
        return None if not c else (1.0 / meia if c["tipo"] == "temperatura" else 1.0 / (meia + 1.0 / float(c["h"])))
    for i in range(ny):
        for j in range(nx):
            s = i * nx + j
            if not M[s]:
                continue
            for di, dj, lado in ((-1, 0, "topo"), (1, 0, "base"), (0, -1, "esquerda"), (0, 1, "direita")):
                horiz = dj != 0
                meia = (dx if horiz else dy) / (2 * K[s])
                area = dy if horiz else dx
                ii, jj = i + di, j + dj
                if 0 <= ii < ny and 0 <= jj < nx:
                    o = ii * nx + jj
                    if M[o]:
                        viz[s].append((o, area / (meia + (dx if horiz else dy) / (2 * K[o]))))
                    elif vazio:
                        bnd[s].append((area * gb(vazio, meia), float(vazio["T"]), "vazio"))
                else:
                    c = cont.get(lado)
                    if c:
                        bnd[s].append((area * gb(c, meia), float(c["T"]), lado))
    tr = p.get("transiente")
    T = [0.0] * N
    avisos, iters = [], 0
    if tr:
        rc = tr["rho_cp"]
        RC = [float(rc)] * N if isinstance(rc, (int, float)) else [float(x) for x in rc]
        t0 = tr.get("t0", 0.0)
        T = [float(t0)] * N if isinstance(t0, (int, float)) else [float(x) for x in t0]
        cap = [RC[s] * dx * dy for s in range(N)]
        lim = min((cap[s] / (sum(g for _, g in viz[s]) + sum(g for g, _, _ in bnd[s])) for s in range(N)
                   if M[s] and (viz[s] or bnd[s])), default=1.0)
        dt = float(tr.get("dt") or 0.9 * lim)
        if dt > 0.9 * lim:
            avisos.append(f"dt reduzido para {0.9 * lim:.3g} s (estabilidade explícita)")
            dt = 0.9 * lim
        passos = int(math.ceil(float(tr["duracao_s"]) / dt))
        for s, v in fixos.items():
            T[s] = v
        for _ in range(passos):
            Tn = T[:]
            for s in range(N):
                if not M[s] or s in fixos:
                    continue
                fl = 0.0
                for o, g in viz[s]:
                    fl += g * (T[o] - T[s])
                for g, tb, _ in bnd[s]:
                    fl += g * (tb - T[s])
                Tn[s] = T[s] + dt * fl / cap[s]
            T = Tn
        iters = passos
        metodo = "Diferenças finitas 2D, transiente explícito (Euler para frente)"
        malha = {"nx": nx, "ny": ny, "dx": dx, "dy": dy, "dt_s": dt, "passos": passos}
    else:
        om, tol, mx = float(p.get("omega", 1.6)), float(p.get("tol", 1e-6)), int(p.get("max_iter", 20000))
        tb_med = [t for c in cont.values() if c for t in [float(c["T"])]]
        T = [sum(tb_med) / len(tb_med) if tb_med else 0.0] * N
        for s, v in fixos.items():
            T[s] = v
        for it in range(1, mx + 1):
            dmax = 0.0
            for s in range(N):
                if not M[s] or s in fixos:
                    continue
                num = den = 0.0
                for o, g in viz[s]:
                    num += g * T[o]
                    den += g
                for g, tb, _ in bnd[s]:
                    num += g * tb
                    den += g
                if den == 0.0:
                    continue
                novo = (1 - om) * T[s] + om * num / den
                dv = abs(novo - T[s])
                if dv > dmax:
                    dmax = dv
                T[s] = novo
            iters = it
            if dmax < tol:
                break
        else:
            avisos.append("SOR não convergiu no máximo de iterações")
        metodo = "Diferenças finitas 2D (volumes finitos), regime permanente por SOR"
        malha = {"nx": nx, "ny": ny, "dx": dx, "dy": dy, "iteracoes": iters, "omega": om, "tol": tol}
    fluxos = {}
    for s in range(N):
        if M[s]:
            for g, tb, lado in bnd[s]:
                fluxos[lado] = fluxos.get(lado, 0.0) + g * (T[s] - tb)     # W por metro de profundidade, saindo
    vals = [T[s] for s in range(N) if M[s]]
    return resultado(metodo, ["condução 2D, propriedades constantes por célula", "profundidade unitária (1 m)",
                              "contato perfeito entre células"], [], malha,
                     "Malha grossa erra perto de cantos e de materiais muito diferentes: refine (dx menor) e compare. "
                     "Peça impressa: preenchimento (infill) entra como k equivalente da célula [CONFERIR com ensaio].",
                     {"T": T, "t_min": min(vals) if vals else None, "t_max": max(vals) if vals else None,
                      "fluxos_w_por_m": fluxos}, avisos)


def placa_analitica(x: float, y: float, a: float, b: float, t_topo: float, termos: int = 201) -> float:
    """Solução em série de uma placa a×b com T = t_topo em y = b e 0 nos outros lados."""
    s = 0.0
    for n in range(1, termos + 1, 2):
        s += 4 * t_topo / (n * math.pi) * math.sin(n * math.pi * x / a) * math.sinh(n * math.pi * y / a) / math.sinh(n * math.pi * b / a)
    return s


# ── polígonos → máscara ──
def mascara_de_segmentos(segmentos: list, x0: float, y0: float, nx: int, ny: int, dx: float, dy: float) -> list:
    """Célula dentro quando o raio horizontal a partir do centro cruza um número ímpar de segmentos (par-ímpar).
    Funciona com uma 'sopa' de segmentos, sem montar contornos. Linha 0 = topo (y maior)."""
    M = [0] * (nx * ny)
    for i in range(ny):
        yc = y0 + (ny - i - 0.5) * dy
        xs = []
        for (ax, ay), (bx, by) in segmentos:
            if (ay > yc) != (by > yc):
                xs.append(ax + (yc - ay) * (bx - ax) / (by - ay))
        xs.sort()
        for j in range(nx):
            xc = x0 + (j + 0.5) * dx
            cnt = 0
            for x in xs:
                if x > xc:
                    cnt += 1
            M[i * nx + j] = cnt % 2
    return M


def poligonos_para_segmentos(poligonos: list) -> list:
    seg = []
    for pol in poligonos:
        for k in range(len(pol)):
            seg.append((tuple(pol[k]), tuple(pol[(k + 1) % len(pol)])))
    return seg
