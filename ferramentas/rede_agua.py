#!/usr/bin/env python3
r"""Rede de água urbana preliminar com dados abertos do Brasil → arquivo do EPANET (.inp) (24/11/2026).

    py ferramentas\rede_agua.py --vias C:\physis\camadas\osm.geojson --relevo C:\physis\camadas\relevo.asc ^
        --populacao 12000 --per-capita 150 --reservatorio=-43.18,-22.50,860 --saida rede.inp

  vias      OpenStreetMap (ferramentas/baixar_camadas.py → osm.geojson): as ruas são o eixo da rede
  relevo    TOPODATA (INPE) ou SRTM, grade ESRI ASCII (.asc) em graus: cota de cada nó
  população IBGE (setores censitários da área) e consumo per capita do SNIS (L/hab·dia) → demanda distribuída pelos nós
  reservatório  lon,lat,nível da água (m): fonte da rede (caixa d'água ou ETA vista na imagem de satélite)

Premissas que os dados abertos não trazem (todas [CONFERIR] e mudáveis por opção): diâmetro por classe de via (--diametros),
Hazen-Williams C (--c, padrão do PVC/PEAD informado pela pessoa), coeficientes de dia e hora de maior consumo (--k1, --k2).
Sem C ou sem os coeficientes informados, o arquivo NÃO é gerado (nada é inventado). Sem dependências (Python 3.10).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

CLASSES = ("primary", "secondary", "tertiary", "residential", "unclassified", "living_street", "service")


def ler_asc(caminho: Path) -> dict:
    cab, linhas = {}, caminho.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(linhas) and linhas[i].split() and linhas[i].split()[0].lower() in ("ncols", "nrows", "xllcorner", "yllcorner", "xllcenter", "yllcenter", "cellsize", "nodata_value"):
        k, v = linhas[i].split()[:2]
        cab[k.lower()] = float(v)
        i += 1
    z = [float(x) for l in linhas[i:] for x in l.split()]
    x0 = cab.get("xllcorner", cab.get("xllcenter", 0)); y0 = cab.get("yllcorner", cab.get("yllcenter", 0))
    return {"nx": int(cab["ncols"]), "ny": int(cab["nrows"]), "x0": x0, "y0": y0, "cel": cab["cellsize"], "sem": cab.get("nodata_value", -9999), "z": z}


def cota(g: dict, lon: float, lat: float) -> float | None:
    i = int((lon - g["x0"]) / g["cel"]); j = g["ny"] - 1 - int((lat - g["y0"]) / g["cel"])
    if not (0 <= i < g["nx"] and 0 <= j < g["ny"]):
        return None
    v = g["z"][j * g["nx"] + i]
    return None if v == g["sem"] else v


def dist_m(a, b) -> float:
    la = math.radians((a[1] + b[1]) / 2)
    return math.hypot((b[0] - a[0]) * 111320 * math.cos(la), (b[1] - a[1]) * 110574)


def montar(vias: dict, relevo: dict, pop: float, per_capita: float, k1: float, k2: float, c_hw: float, diam: dict, reserv: tuple) -> dict:
    nos, chave, tubos = {}, {}, []
    def no(p):
        k = (round(p[0], 6), round(p[1], 6))
        if k not in chave:
            chave[k] = f"N{len(chave) + 1}"
            nos[chave[k]] = {"lon": k[0], "lat": k[1], "cota": cota(relevo, *k), "grau": 0}
        nos[chave[k]]["grau"] += 1
        return chave[k]
    for f in vias.get("features", []):
        pr, g = f.get("properties", {}), f.get("geometry") or {}
        if pr.get("tipo") != "via" or g.get("type") != "LineString" or pr.get("classe") not in CLASSES or pr.get("classe") not in diam:
            continue
        cs = g["coordinates"]
        for a, b in zip(cs, cs[1:]):            # cada segmento vira trecho: os cruzamentos (pontos iguais) viram nós
            na, nb = no(a), no(b)
            if na != nb:
                tubos.append({"id": f"P{len(tubos) + 1}", "de": na, "para": nb, "L": round(dist_m(a, b), 2), "D": diam[pr["classe"]], "classe": pr["classe"]})
    if not tubos:
        raise ValueError("nenhuma via com classe e diâmetro definidos")
    sem_cota = [k for k, v in nos.items() if v["cota"] is None]
    q_media = pop * per_capita / 86400.0                          # L/s
    q_max = q_media * k1 * k2
    por_no = q_max / len(nos)
    rid = "R1"; perto = min(nos, key=lambda k: dist_m((nos[k]["lon"], nos[k]["lat"]), reserv[:2]))
    tubos.append({"id": f"P{len(tubos) + 1}", "de": rid, "para": perto, "L": round(max(1.0, dist_m(reserv[:2], (nos[perto]["lon"], nos[perto]["lat"]))), 2),
                  "D": max(diam.values()), "classe": "adutora"})
    return {"nos": nos, "tubos": tubos, "reservatorio": {"id": rid, "lon": reserv[0], "lat": reserv[1], "nivel": reserv[2]},
            "q_media_Ls": q_media, "q_max_Ls": q_max, "demanda_no_Ls": por_no, "c_hw": c_hw, "sem_cota": sem_cota}


def inp(rede: dict) -> str:
    L = ["[TITLE]", "Rede preliminar Physis (dados abertos: OSM, TOPODATA/SRTM, IBGE, SNIS) - premissas [CONFERIR]", "",
         "[JUNCTIONS]", ";ID  Elev  Demand"]
    for k, v in rede["nos"].items():
        L.append(f"{k}  {(v['cota'] if v['cota'] is not None else 0):.2f}  {rede['demanda_no_Ls']:.5f}")
    L += ["", "[RESERVOIRS]", ";ID  Head", f"{rede['reservatorio']['id']}  {rede['reservatorio']['nivel']:.2f}", "", "[PIPES]", ";ID  Node1  Node2  Length  Diameter  Roughness  MinorLoss  Status"]
    for t in rede["tubos"]:
        L.append(f"{t['id']}  {t['de']}  {t['para']}  {t['L']:.2f}  {t['D']:.1f}  {rede['c_hw']:.1f}  0  Open")
    L += ["", "[OPTIONS]", "Units LPS", "Headloss H-W", "", "[COORDINATES]"]
    for k, v in rede["nos"].items():
        L.append(f"{k}  {v['lon']:.6f}  {v['lat']:.6f}")
    r = rede["reservatorio"]
    L += [f"{r['id']}  {r['lon']:.6f}  {r['lat']:.6f}", "", "[END]", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--vias", required=True); ap.add_argument("--relevo", required=True)
    ap.add_argument("--populacao", type=float, required=True, help="habitantes (IBGE)"); ap.add_argument("--per-capita", type=float, required=True, help="L/hab·dia (SNIS)")
    ap.add_argument("--k1", type=float, help="coeficiente do dia de maior consumo [CONFERIR]"); ap.add_argument("--k2", type=float, help="coeficiente da hora de maior consumo [CONFERIR]")
    ap.add_argument("--c", type=float, help="Hazen-Williams C dos tubos [CONFERIR]")
    ap.add_argument("--diametros", help='JSON {classe: mm}, ex.: {"primary":200,"secondary":150,"tertiary":100,"residential":75}')
    ap.add_argument("--reservatorio", required=True, help="lon,lat,nível (m)"); ap.add_argument("--saida", default="rede.inp")
    a = ap.parse_args(argv)
    faltam = [n for n, v in (("--k1", a.k1), ("--k2", a.k2), ("--c", a.c), ("--diametros", a.diametros)) if v is None]
    if faltam:
        print("Faltam premissas (nada é inventado):", ", ".join(faltam))
        return 2
    rede = montar(json.loads(Path(a.vias).read_text(encoding="utf-8")), ler_asc(Path(a.relevo)), a.populacao, a.per_capita, a.k1, a.k2, a.c,
                  {k: float(v) for k, v in json.loads(a.diametros).items()}, tuple(float(x) for x in a.reservatorio.split(",")))
    Path(a.saida).write_text(inp(rede), encoding="utf-8")
    print(f"{a.saida}: {len(rede['nos'])} nós, {len(rede['tubos'])} trechos, vazão máxima {rede['q_max_Ls']:.2f} L/s"
          + (f"; {len(rede['sem_cota'])} nó(s) fora do relevo (cota 0: conferir)" if rede["sem_cota"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
