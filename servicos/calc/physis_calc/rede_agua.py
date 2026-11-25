"""/rede-agua — rede de distribuição de água no EPANET (via wntr), a partir de um JSON simples.

Entrada (unidades SI; vazão em L/s):
  {"nos": [{"id": "N1", "cota": 10, "demanda_ls": 1.2}],
   "reservatorios": [{"id": "R1", "carga": 50}],          # nível de água (m)
   "tubos": [{"id": "T1", "de": "R1", "para": "N1", "comprimento": 100, "diametro_mm": 100, "rugosidade": 130}],
   "formula": "H-W" | "D-W" | "C-M"}                       # Hazen-Williams (C), Darcy-Weisbach (mm), Chezy-Manning (n)
Saída: pressão em cada nó (m.c.a.), vazão e velocidade em cada tubo, e os piores pontos.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from .comum import EntradaInvalida, exigir, ident, num

FORMULAS = {"H-W", "D-W", "C-M"}
MAX_ELEMENTOS = 5000


def validar(e: dict) -> dict:
    nos = e.get("nos") or []
    res = e.get("reservatorios") or []
    tubos = e.get("tubos") or []
    if not isinstance(nos, list) or not isinstance(res, list) or not isinstance(tubos, list):
        raise EntradaInvalida("'nos', 'reservatorios' e 'tubos' devem ser listas")
    if not res:
        raise EntradaInvalida("informe ao menos um reservatório (carga fixa)")
    if not tubos:
        raise EntradaInvalida("informe ao menos um tubo")
    if len(nos) + len(res) + len(tubos) > MAX_ELEMENTOS:
        raise EntradaInvalida(f"rede grande demais para este serviço (> {MAX_ELEMENTOS} elementos)")
    formula = str(e.get("formula") or "H-W").upper()
    if formula not in FORMULAS:
        raise EntradaInvalida("'formula' deve ser H-W, D-W ou C-M")
    p = {"formula": formula, "nos": [], "reservatorios": [], "tubos": []}
    ids = set()

    def novo(i, onde):
        if i in ids:
            raise EntradaInvalida(f"id repetido: {i}")
        ids.add(i)
        return i

    for n in nos:
        p["nos"].append({"id": novo(ident(n.get("id"), "nó"), "nó"), "cota": num(n, "cota", None, -500, 9000),
                         "demanda_ls": num(n, "demanda_ls", 0, 0, 1e5)})
    for r in res:
        p["reservatorios"].append({"id": novo(ident(r.get("id"), "reservatório"), "reservatório"),
                                   "carga": num(r, "carga", None, -500, 9000)})
    vertices = {x["id"] for x in p["nos"]} | {x["id"] for x in p["reservatorios"]}
    for t in tubos:
        de, para = ident(t.get("de"), "tubo.de"), ident(t.get("para"), "tubo.para")
        if de not in vertices or para not in vertices:
            raise EntradaInvalida(f"tubo {t.get('id')}: liga nó que não existe")
        if de == para:
            raise EntradaInvalida(f"tubo {t.get('id')}: liga um nó a ele mesmo")
        p["tubos"].append({"id": novo(ident(t.get("id"), "tubo"), "tubo"), "de": de, "para": para,
                           "comprimento": num(t, "comprimento", None, 0.1, 1e5),
                           "diametro_mm": num(t, "diametro_mm", None, 5, 5000),
                           "rugosidade": num(t, "rugosidade", None, 0.0001, 200)})
    # todo nó precisa chegar a um reservatório (senão o EPANET para com "nó desconectado")
    viz = {v: set() for v in vertices}
    for t in p["tubos"]:
        viz[t["de"]].add(t["para"])
        viz[t["para"]].add(t["de"])
    vistos, fila = set(), [r["id"] for r in p["reservatorios"]]
    while fila:
        v = fila.pop()
        if v not in vistos:
            vistos.add(v)
            fila.extend(viz[v] - vistos)
    soltos = sorted(vertices - vistos)
    if soltos:
        raise EntradaInvalida("nós sem caminho até um reservatório: " + ", ".join(soltos[:10]))
    return p


def montar_inp(p: dict) -> str:
    o = ["[TITLE]", "Physis - rede de agua", "", "[JUNCTIONS]", ";ID  Elev  Demand"]
    o += [f"{n['id']}  {n['cota']:.3f}  {n['demanda_ls']:.4f}" for n in p["nos"]]
    o += ["", "[RESERVOIRS]", ";ID  Head"]
    o += [f"{r['id']}  {r['carga']:.3f}" for r in p["reservatorios"]]
    o += ["", "[PIPES]", ";ID  Node1  Node2  Length  Diameter  Roughness  MinorLoss  Status"]
    o += [f"{t['id']}  {t['de']}  {t['para']}  {t['comprimento']:.3f}  {t['diametro_mm']:.2f}  {t['rugosidade']:.5g}  0  Open"
          for t in p["tubos"]]
    o += ["", "[OPTIONS]", "Units  LPS", f"Headloss  {p['formula']}", "", "[TIMES]", "Duration  0:00", "",
          "[REPORT]", "Status  No", "", "[END]", ""]
    return "\n".join(o)


def calcular(e: dict, somente_inp: bool = False) -> dict:
    p = validar(e)
    inp = montar_inp(p)
    if somente_inp:
        return {"ok": True, "inp": inp}
    exigir("wntr")
    import wntr

    with tempfile.TemporaryDirectory(prefix="epanet-", ignore_cleanup_errors=True) as d:
        arq = Path(d) / "rede.inp"
        arq.write_text(inp, encoding="utf-8")
        wn = wntr.network.WaterNetworkModel(str(arq))
        r = wntr.sim.EpanetSimulator(wn).run_sim(file_prefix=str(Path(d) / "saida"))
    pres = r.node["pressure"].iloc[0]
    vaz = r.link["flowrate"].iloc[0] * 1000.0          # m³/s -> L/s
    vel = r.link["velocity"].iloc[0]
    nos = {n["id"]: round(float(pres[n["id"]]), 2) for n in p["nos"]}
    tubos = {t["id"]: {"vazao_ls": round(float(vaz[t["id"]]), 3), "velocidade_ms": round(float(vel[t["id"]]), 3)}
             for t in p["tubos"]}
    pior = min(nos.items(), key=lambda x: x[1]) if nos else None
    rapido = max(tubos.items(), key=lambda x: x[1]["velocidade_ms"]) if tubos else None
    return {"ok": True, "motor": f"EPANET via wntr {wntr.__version__}", "pressao_m": nos, "tubos": tubos,
            "menor_pressao": {"no": pior[0], "m": pior[1]} if pior else None,
            "maior_velocidade": {"tubo": rapido[0], "ms": rapido[1]["velocidade_ms"]} if rapido else None,
            "avisos": ["Regime permanente (instante 0). Limites de pressão e velocidade: conferir a norma aplicável ao projeto."]}
