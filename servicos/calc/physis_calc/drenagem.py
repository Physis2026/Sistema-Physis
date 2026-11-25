"""/drenagem — escoamento de uma bacia (sub-bacia única) no SWMM (via pyswmm).

Entrada:
  {"area_ha", "impermeabilidade_pct", "declividade_pct", "largura_m"? (padrão: √área),
   "chuva": {"intensidades_mm_h": [...], "passo_min": 5}      # hietograma
         ou {"total_mm": 60, "duracao_min": 60},               # bloco uniforme
   "n_imperm"?, "n_perm"?, "armaz_imperm_mm"?, "armaz_perm_mm"?,
   "horton": {"max_mm_h", "min_mm_h", "decaimento_h"}?}
Padrões: valores típicos do Manual de Referência do SWMM (EPA, vol. I — Hidrologia, tabelas de rugosidade de
Manning para escoamento superficial, armazenamento em depressões e parâmetros de Horton). [CONFERIR] com o
solo e a cobertura do lugar antes de usar em projeto.
"""
from __future__ import annotations

import math
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from .comum import EntradaInvalida, exigir, lista_num, num

PADROES = {"n_imperm": 0.012, "n_perm": 0.15, "armaz_imperm_mm": 1.27, "armaz_perm_mm": 5.08,
           "horton": {"max_mm_h": 76.2, "min_mm_h": 3.81, "decaimento_h": 4.0}}
INICIO = datetime(2026, 1, 1, 0, 0)


def validar(e: dict) -> dict:
    p = {"area_ha": num(e, "area_ha", None, 0.001, 10000), "imperm": num(e, "impermeabilidade_pct", None, 0, 100),
         "decliv": num(e, "declividade_pct", None, 0.01, 100)}
    p["largura_m"] = num(e, "largura_m", math.sqrt(p["area_ha"] * 10000), 1, 1e5)
    for k in ("n_imperm", "n_perm", "armaz_imperm_mm", "armaz_perm_mm"):
        p[k] = num(e, k, PADROES[k], 0, 500)
    h = e.get("horton") if isinstance(e.get("horton"), dict) else {}
    p["horton"] = {k: num(h, k, v, 0, 1000) for k, v in PADROES["horton"].items()}
    ch = e.get("chuva")
    if not isinstance(ch, dict):
        raise EntradaInvalida("informe 'chuva'")
    if ch.get("intensidades_mm_h") is not None:
        p["passo_min"] = int(num(ch, "passo_min", 5, 1, 60))
        p["intensidades"] = lista_num(ch, "intensidades_mm_h", 0, 500, 1, 2880)
    else:
        total, dur = num(ch, "total_mm", None, 0.1, 2000), num(ch, "duracao_min", None, 5, 2880)
        p["passo_min"] = 5
        n = max(1, int(round(dur / 5)))
        p["intensidades"] = [total / (n * 5 / 60)] * n
    p["usou_padroes"] = [k for k in ("n_imperm", "n_perm", "armaz_imperm_mm", "armaz_perm_mm") if k not in e] + (
        ["horton"] if not h else [])
    return p


def _hhmm(minutos: int) -> str:
    return f"{minutos // 60}:{minutos % 60:02d}"


def montar_inp(p: dict) -> str:
    dur = len(p["intensidades"]) * p["passo_min"]
    fim = INICIO + timedelta(minutes=dur + 360)          # 6 h depois da chuva para a bacia esvaziar
    f = "%m/%d/%Y"
    o = ["[TITLE]", "Physis - drenagem (sub-bacia unica)", "",
         "[OPTIONS]", "FLOW_UNITS LPS", "INFILTRATION HORTON", "FLOW_ROUTING KINWAVE",
         f"START_DATE {INICIO:{f}}", "START_TIME 00:00:00", f"REPORT_START_DATE {INICIO:{f}}", "REPORT_START_TIME 00:00:00",
         f"END_DATE {fim:{f}}", f"END_TIME {fim:%H:%M:%S}", "WET_STEP 00:01:00", "DRY_STEP 00:15:00",
         "ROUTING_STEP 0:00:30", "REPORT_STEP 00:01:00", "",
         "[RAINGAGES]", ";Name Format Interval SCF Source",
         f"P1 INTENSITY {_hhmm(p['passo_min'])} 1.0 TIMESERIES Chuva", "",
         "[SUBCATCHMENTS]", ";Name Raingage Outlet Area %Imperv Width %Slope CurbLen",
         f"S1 P1 Saida {p['area_ha']:.4f} {p['imperm']:.2f} {p['largura_m']:.2f} {p['decliv']:.3f} 0", "",
         "[SUBAREAS]", ";Subcatch N-Imperv N-Perv S-Imperv S-Perv PctZero RouteTo",
         f"S1 {p['n_imperm']:.4f} {p['n_perm']:.4f} {p['armaz_imperm_mm']:.3f} {p['armaz_perm_mm']:.3f} 25 OUTLET", "",
         "[INFILTRATION]", ";Subcatch MaxRate MinRate Decay DryTime MaxInfil",
         f"S1 {p['horton']['max_mm_h']:.3f} {p['horton']['min_mm_h']:.3f} {p['horton']['decaimento_h']:.3f} 7 0", "",
         "[OUTFALLS]", ";Name Elevation Type", "Saida 0 FREE", "",
         "[TIMESERIES]", ";Name Time Value"]
    for i, v in enumerate(p["intensidades"]):
        o.append(f"Chuva {_hhmm(i * p['passo_min'])} {v:.4f}")
    o.append(f"Chuva {_hhmm(dur)} 0")
    o += ["", "[REPORT]", "SUBCATCHMENTS ALL", "", "[END]", ""]
    return "\n".join(o)


def calcular(e: dict, somente_inp: bool = False) -> dict:
    p = validar(e)
    inp = montar_inp(p)
    if somente_inp:
        return {"ok": True, "inp": inp}
    exigir("pyswmm")
    import pyswmm
    from pyswmm import Simulation, Subcatchments

    serie = []
    with tempfile.TemporaryDirectory(prefix="swmm-", ignore_cleanup_errors=True) as d:
        arq = Path(d) / "bacia.inp"
        arq.write_text(inp, encoding="utf-8")
        with Simulation(str(arq)) as sim:
            sim.step_advance(60)
            s = Subcatchments(sim)["S1"]
            ant = sim.start_time
            for _ in sim:
                agora = sim.current_time
                serie.append(((agora - INICIO).total_seconds() / 60, float(s.runoff), (agora - ant).total_seconds()))
                ant = agora
    vol_m3 = sum(q * dt for _, q, dt in serie) / 1000.0           # L/s * s -> L -> m³
    chuva_mm = sum(i * p["passo_min"] / 60 for i in p["intensidades"])
    chuva_m3 = chuva_mm / 1000 * p["area_ha"] * 10000
    pico = max(serie, key=lambda x: x[1]) if serie else (0, 0.0, 0)
    return {"ok": True, "motor": f"SWMM via pyswmm {pyswmm.__version__}",
            "chuva_mm": round(chuva_mm, 2), "volume_escoado_m3": round(vol_m3, 2),
            "coeficiente_escoamento": round(vol_m3 / chuva_m3, 3) if chuva_m3 else 0.0,
            "vazao_pico_ls": round(pico[1], 2), "minuto_do_pico": round(pico[0], 1),
            "hidrograma_ls": [[round(t, 1), round(q, 3)] for t, q, _ in serie[::5]],
            "padroes_usados": p["usou_padroes"],
            "avisos": ["Parâmetros padrão do manual do SWMM usados: " + ", ".join(p["usou_padroes"]) + ". Ajuste ao lugar."]
            if p["usou_padroes"] else []}
