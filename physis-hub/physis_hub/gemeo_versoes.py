"""Gêmeo digital · comparador de versões de planta do mesmo lote (versão de TESTE).

    python -m physis_hub.gemeo_versoes [VERSAO.xlsx|.csv ...] [--masterplan] [--precos PRECOS.csv]
                                       [--saida RELATORIO.json] [--ifc PASTA]

Critério (decisão da dona em 21/11/2026, M&A pg:97b6e5a48dcf): normas e segurança ELIMINAM; entre as versões que
passam, ganha a de melhor custo-benefício.

1. Filtro (passa / não passa), cada falha com o motivo:
   - toda edificação dentro do perímetro do lote (como o Planejador: "sai do perímetro do lote");
   - nenhuma edificação sobre outra no mesmo nível (em planta e com diferença de cota menor que um pavimento);
   - ocupação (soma da coluna Área das edificações ÷ área do lote) ≤ limite da 03 (40 %).
   Sinalizado, sem eliminar: desnível sob a projeção > 1,5 m (mesma conta e limiar do Planejador, NBR 11682).
2. Ranking das que passam: custo por m² de edificação (só com preço real, de `--precos` com fonte); sem preço, o custo
   fica [MARCADOR] e o ranking usa só os módulos: módulos presentes na planta, depois mais lofts, depois menos terra
   movida (corte + aterro da planilha).

Formatos de versão: planilha .xlsx com a aba "Implantação" no leiaute da 03, ou .csv (separador ;) com as colunas de
`COLUNAS_CSV` (o modelo é a rev0 exportada por `--modelo`). Versões resumidas: as combinações da 03 › Estudos de
masterplan entram só com os números da linha (avaliação parcial: sem planta, sem filtro geométrico).

Mesmo lote para todas: perímetro, pontos com cota, área e limite de ocupação vêm da semente rev0.
Nada é inventado: o que a versão não traz fica [MARCADOR].
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

from . import gemeo as G
from . import gemeo_importar as I

LIMIAR_DESNIVEL_M = 1.5  # o mesmo do Planejador (verificação "desnível sob a projeção")
# categorias do Planejador (TIPOS): edificação, pavimento e água entram na conta de desnível; 'perm' não
CAT_PLANEJADOR = {"residencia": "ed", "multifamiliar": "ed", "hospedagem": "ed", "escritorio": "ed", "restaurante": "ed",
                  "edicula": "ed", "garagem": "ed", "deposito": "ed", "sauna": "ed", "piscina": "agua", "deck": "pav",
                  "pavimento": "pav", "estacionamento": "pav", "gramado": "perm", "horta": "perm", "mata": "perm",
                  "cisterna": "inf", "tratamento": "inf", "biodigestor": "inf", "infiltracao": "inf", "solar_solo": "inf"}
MODULOS = {  # módulo do sistema → como aparece na planta (prefixo da chave)
    "cisternas": ("cist",), "biodigestor": ("biodig",), "tratamento_esgoto": ("fossa", "filtr"),
    "drenagem_natural": ("chuva", "infiltr"), "producao_alimentos": ("horta", "pomar", "viveiro"),
}
COLUNAS_CSV = ["chave", "elemento", "zona", "x", "y", "larg", "prof", "area_m2", "piso_topo", "corte_m3", "aterro_m3"]
TOL_M = 0.05


# ---------------------------------------------------------------- terreno: espelho do Planejador (T.build / T.z)

class TerrenoPlanejador:
    """Mesma grade do Planejador: 110 células no maior lado, inverso do quadrado da distância aos ≥ 8 pontos mais
    próximos (por baldes de 10 células) e interpolação bilinear. Espelho de `T.build`/`T.z` (regra 4)."""

    def __init__(self, poly, pontos):
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        m = max(max(xs) - min(xs), max(ys) - min(ys)) * 0.04 + 1
        self.x0, x1, self.y0, y1 = min(xs) - m, max(xs) + m, min(ys) - m, max(ys) + m
        n = 110
        self.cs = cs = max(x1 - self.x0, y1 - self.y0) / n
        self.nx, self.ny = math.ceil((x1 - self.x0) / cs) + 1, math.ceil((y1 - self.y0) / cs) + 1
        B, bk = 10, {}
        for p in pontos:
            bk.setdefault((math.floor((p[0] - self.x0) / (cs * B)), math.floor((p[1] - self.y0) / (cs * B))), []).append(p)
        self.Z = Z = [0.0] * (self.nx * self.ny)
        for j in range(self.ny):
            for i in range(self.nx):
                x, y = self.x0 + i * cs, self.y0 + j * cs
                if not pontos:
                    continue
                near, r = [], 0
                while len(near) < 8 and r < 20:
                    near = []
                    bi, bj = math.floor((x - self.x0) / (cs * B)), math.floor((y - self.y0) / (cs * B))
                    for a in range(-r, r + 1):
                        for b in range(-r, r + 1):
                            near.extend(bk.get((bi + a, bj + b), []))
                    r += 1
                num = den = 0.0
                hit = None
                for q in near:
                    d = math.hypot(q[0] - x, q[1] - y)
                    if d < 1e-6:
                        hit = q[2]
                        break
                    w = 1 / (d * d)
                    num += w * q[2]
                    den += w
                Z[j * self.nx + i] = hit if hit is not None else num / den

    def z(self, x, y):
        cl = lambda v, a, b: min(b, max(a, v))
        fi = cl((x - self.x0) / self.cs, 0, self.nx - 1.001)
        fj = cl((y - self.y0) / self.cs, 0, self.ny - 1.001)
        i, j = math.floor(fi), math.floor(fj)
        u, v = fi - i, fj - j
        Z, n = self.Z, self.nx
        return (Z[j * n + i] * (1 - u) * (1 - v) + Z[j * n + i + 1] * u * (1 - v) + Z[(j + 1) * n + i] * (1 - u) * v
                + Z[(j + 1) * n + i + 1] * u * v)

    def desnivel(self, cx, cy, w, d):
        """dz sob a projeção (item sem giro), como o Planejador: amostras a cada max(0,5; menor lado/8) m."""
        st = max(0.5, min(w, d) / 8)
        zs = []
        a = -w / 2 + st / 2
        while a < w / 2:
            b = -d / 2 + st / 2
            while b < d / 2:
                zs.append(self.z(cx + a, cy + b))
                b += st
            a += st
        return max(zs) - min(zs) if zs else 0.0


def dentro(p, poly):
    """Ponto no polígono (par-ímpar) com tolerância de TOL_M até a borda."""
    x, y, d = p[0], p[1], False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            d = not d
    if d:
        return True
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy or 1)))
        if math.hypot(x - (x1 + t * dx), y - (y1 + t * dy)) <= TOL_M:
            return True
    return False


# ---------------------------------------------------------------- versões

def _f(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    n = I.numeros_br(v)
    return n[0] if n else None


def versao_da_semente(projeto, nome="rev0"):
    els = [{"chave": k, **e} for k, e in projeto["gemeo"]["elementos"].items()]
    return {"nome": nome, "tipo": "planta", "fonte": f"semente {projeto['gemeo']['semente']}", "elementos": els}


def ler_versao(caminho, nome=None):
    caminho = Path(caminho)
    nome = nome or caminho.stem
    if caminho.suffix.lower() == ".xlsx":
        els = I.elementos_implantacao(I.Planilha(nome, caminho))
        return {"nome": nome, "tipo": "planta", "fonte": f"{caminho.name} › Implantação", "elementos": els}
    if caminho.suffix.lower() != ".csv":
        raise I.FonteAusente(f"{caminho.name}: use .xlsx (aba Implantação) ou .csv (colunas {';'.join(COLUNAS_CSV)})")
    els = []
    with open(caminho, encoding="utf-8-sig", newline="") as fh:
        linhas = [l for l in fh if l.strip() and not l.lstrip().startswith("#")]
    leitor = csv.DictReader(linhas, delimiter=";")
    falta = [c for c in COLUNAS_CSV if c not in (leitor.fieldnames or [])]
    if falta:
        raise I.FonteAusente(f"{caminho.name}: faltam as colunas {', '.join(falta)}")
    for n, r in enumerate(leitor, 2):
        zona = G.zona_de(r["zona"]) or (r["zona"].strip().upper() if r["zona"].strip().upper() in G.ZONAS else None)
        if not r["chave"].strip() or not zona:
            raise I.FonteAusente(f"{caminho.name}, linha {n}: chave ou zona inválida")
        els.append({"chave": r["chave"].strip(), "linha_03": n, "zona": zona, "entidade": G.ZONAS[zona]["entidade"],
                    "descricao": r["elemento"].strip() or None, "x_03": _f(r["x"]), "y_03": _f(r["y"]),
                    "larg_m": _f(r["larg"]), "prof_m": _f(r["prof"]), "area_m2": _f(r["area_m2"]),
                    "piso_topo_m": _f(r["piso_topo"]), "corte_m3": _f(r["corte_m3"]), "aterro_m3": _f(r["aterro_m3"]),
                    "fonte": f"{caminho.name}, linha {n}", "procedencia": "estimado"})
    return {"nome": nome, "tipo": "planta", "fonte": caminho.name, "elementos": els}


def escrever_modelo_csv(versao, caminho):
    """CSV modelo (a rev0) para preencher outras versões."""
    with open(caminho, "w", encoding="utf-8", newline="") as fh:
        fh.write("# Modelo de versão de planta do Lote 168 (gêmeo digital). Uma linha por elemento; x e y = canto do\n"
                 "# retângulo em metros locais (P-01 = 0,0; y da Rua H para a Rua G); zona = Zona 1, Zona 2 ou Zona 3;\n"
                 "# decimais com vírgula. Copie, renomeie (ex.: versao_B.csv) e altere.\n")
        w = csv.writer(fh, delimiter=";")
        w.writerow(COLUNAS_CSV)
        br = lambda v: "" if v is None else (f"{v:.3f}".rstrip("0").rstrip(".").replace(".", ","))
        for e in versao["elementos"]:
            w.writerow([e["chave"], e.get("descricao") or "", G.ZONAS[e["zona"]]["nome"], br(e["x_03"]), br(e["y_03"]),
                        br(e["larg_m"]), br(e["prof_m"]), br(e["area_m2"]), br(e["piso_topo_m"]), br(e["corte_m3"]),
                        br(e["aterro_m3"])])


def versoes_masterplan(p03):
    """Combinações da 03 › Estudos de masterplan (só números da linha: avaliação parcial)."""
    aba = "Estudos de masterplan"
    out = []
    for n, lv in sorted(p03.aba(aba).items()):
        if n == 1 or not lv.get("A"):
            continue
        out.append({"nome": str(lv["A"]).strip(), "tipo": "resumo", "fonte": p03.fonte(aba, n),
                    "lofts": _f(lv.get("B")), "vagas": lv.get("C"), "cota_casa_m": _f(lv.get("D")),
                    "corte_m3": _f(lv.get("E")), "aterro_m3": _f(lv.get("F")), "ocupacao_m2": _f(lv.get("G")),
                    "terraplenagem_rs": _f(lv.get("H")), "acesso": lv.get("I")})
    if not out:
        raise I.FonteAusente("planilha 03 › Estudos de masterplan vazia")
    return out


def ler_precos(caminho):
    """CSV `tipo;preco_m2;fonte` (tipo = tipo do Planejador, ex.: residencia). Sem fonte, o preço é recusado."""
    precos = {}
    with open(caminho, encoding="utf-8-sig", newline="") as fh:
        for n, r in enumerate(csv.DictReader((l for l in fh if not l.lstrip().startswith("#")), delimiter=";"), 2):
            if _f(r.get("preco_m2")) is None:
                continue  # linha do modelo ainda sem preço: o tipo fica sem custo ([MARCADOR])
            if not (r.get("fonte") or "").strip():
                raise I.FonteAusente(f"{Path(caminho).name}, linha {n}: preço sem fonte")
            precos[r["tipo"].strip()] = (_f(r["preco_m2"]), r["fonte"].strip())
    return precos


# ---------------------------------------------------------------- avaliação

def lote_da_semente(projeto):
    fv = projeto["gemeo"]["fonte_por_valor"]
    return {"poly": projeto["terreno"]["poly"], "pontos": projeto["terreno"]["pontos"],
            "area_m2": fv["lote.area_m2"]["valor"], "limite_ocupacao_pct": projeto["regras"]["to"],
            "fonte_limite": projeto["prov"]["regras.to"]["src"],
            "altura_pavimento_m": 2.90, "fonte_altura": "03 › Implantação, LAB/MEC de cima − de baixo (pg:16228b14d400)"}


def _ret(e):
    x, y, w, d = e["x_03"] or 0, e["y_03"] or 0, e["larg_m"] or 0, e["prof_m"] or 0
    return x, y, x + w, y + d


def avaliar(versao, lote, terreno=None, precos=None):
    if versao["tipo"] == "resumo":
        return _avaliar_resumo(versao, lote)
    terreno = terreno or TerrenoPlanejador(lote["poly"], lote["pontos"])
    els = [e for e in versao["elementos"] if (e.get("area_m2") or 0) > 0]
    tipo = {e["chave"]: I.tipo_planejador(e["chave"]) for e in els}
    eds = [e for e in els if CAT_PLANEJADOR.get(tipo[e["chave"]]) == "ed"]
    falhas, alertas = [], []
    for e in eds:
        x0, y0, x1, y1 = _ret(e)
        if not all(dentro(p, lote["poly"]) for p in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))):
            falhas.append(f"{e['chave']} sai do perímetro do lote")
    hp = lote["altura_pavimento_m"]
    for i, a in enumerate(eds):
        for b in eds[i + 1:]:
            ax0, ay0, ax1, ay1 = _ret(a)
            bx0, by0, bx1, by1 = _ret(b)
            sob = min(ax1, bx1) - max(ax0, bx0) > TOL_M and min(ay1, by1) - max(ay0, by0) > TOL_M
            ca, cb = a.get("piso_topo_m"), b.get("piso_topo_m")
            mesmo_nivel = ca is None or cb is None or abs(ca - cb) < hp - 0.01
            if sob and mesmo_nivel:
                falhas.append(f"{a['chave']} e {b['chave']} se sobrepõem no mesmo nível")
    area_ed = round(sum(e["area_m2"] for e in eds), 2)
    ocup = round(area_ed / lote["area_m2"] * 100, 2)
    if ocup > lote["limite_ocupacao_pct"] + 1e-9:
        falhas.append(f"ocupação {ocup:.1f} % acima do limite de {lote['limite_ocupacao_pct']:.0f} %")
    desn = []
    for e in els:
        cat = CAT_PLANEJADOR.get(tipo[e["chave"]])
        if cat not in ("ed", "pav", "agua"):
            continue
        x0, y0, x1, y1 = _ret(e)
        dz = terreno.desnivel((x0 + x1) / 2, (y0 + y1) / 2, x1 - x0, y1 - y0)
        if dz > LIMIAR_DESNIVEL_M:
            desn.append({"chave": e["chave"], "desnivel_m": round(dz, 2)})
    for d in sorted(desn, key=lambda d: -d["desnivel_m"]):
        alertas.append(f"{d['chave']}: desnível de {d['desnivel_m']:.1f} m sob a projeção; prever contenção ou "
                       "estrutura elevada (NBR 11682)")
    mods = {m: any(e["chave"].startswith(pre) for e in els for pre in pres) for m, pres in MODULOS.items()}
    lofts = sum(1 for e in els if tipo[e["chave"]] == "hospedagem")
    terra = round(sum((e.get("corte_m3") or 0) + (e.get("aterro_m3") or 0) for e in versao["elementos"]), 1)
    custo, custo_fonte, sem_preco = None, [], []
    if precos:
        total = 0.0
        for e in eds:
            pr = precos.get(tipo[e["chave"]])
            if pr is None or pr[0] is None:
                sem_preco.append(tipo[e["chave"]])
                continue
            total += e["area_m2"] * pr[0]
            custo_fonte.append(pr[1])
        if not sem_preco:
            custo = round(total, 2)
    return {
        "nome": versao["nome"], "tipo": "planta", "fonte": versao["fonte"], "passa": not falhas, "falhas": falhas,
        "alertas": alertas, "elementos": len(versao["elementos"]),
        "por_zona": {z: sum(1 for e in versao["elementos"] if e["zona"] == z) for z in G.ZONAS},
        "area_edificacoes_m2": area_ed, "ocupacao_pct": ocup, "lofts": lofts, "terra_movida_m3": terra,
        "modulos": mods, "modulos_presentes": sum(mods.values()),
        "custo_rs": custo, "custo_m2_rs": round(custo / area_ed, 2) if custo is not None and area_ed else None,
        "custo_marcador": None if custo is not None else (
            "[MARCADOR] sem preço com fonte para: " + ", ".join(sorted(set(sem_preco))) if sem_preco
            else "[MARCADOR] sem tabela de preços (--precos)"),
        "custo_fontes": sorted(set(custo_fonte)),
    }


def _avaliar_resumo(v, lote):
    falhas = []
    ocup = round(v["ocupacao_m2"] / lote["area_m2"] * 100, 2) if v.get("ocupacao_m2") is not None else None
    if ocup is not None and ocup > lote["limite_ocupacao_pct"]:
        falhas.append(f"ocupação {ocup:.1f} % acima do limite de {lote['limite_ocupacao_pct']:.0f} %")
    return {"nome": v["nome"], "tipo": "resumo", "fonte": v["fonte"], "passa": not falhas, "falhas": falhas,
            "alertas": ["avaliação parcial: sem planta, perímetro, sobreposição e desnível não conferidos"],
            "ocupacao_pct": ocup, "lofts": int(v["lofts"]) if v.get("lofts") is not None else None,
            "terra_movida_m3": round((v.get("corte_m3") or 0) + (v.get("aterro_m3") or 0), 1),
            "terraplenagem_rs": v.get("terraplenagem_rs"), "cota_casa_m": v.get("cota_casa_m"), "acesso": v.get("acesso"),
            "custo_marcador": "[MARCADOR] só a terraplenagem tem custo na 03"}


def comparar(avaliacoes):
    """Ranking: plantas que passam (custo/m² se todas têm preço; senão módulos, lofts, menos terra); depois resumos que
    passam (menor terraplenagem, mais lofts); as que não passam ficam fora, com o motivo."""
    plantas = [a for a in avaliacoes if a["tipo"] == "planta" and a["passa"]]
    if plantas and all(a["custo_m2_rs"] is not None for a in plantas):
        criterio = "custo por m² de edificação (menor), depois módulos presentes, lofts e terra movida"
        plantas.sort(key=lambda a: (a["custo_m2_rs"], -a["modulos_presentes"], -a["lofts"], a["terra_movida_m3"]))
    else:
        criterio = ("[MARCADOR] custo sem preço com fonte: ranking só por módulos presentes (mais), lofts (mais) e terra "
                    "movida (menos)")
        plantas.sort(key=lambda a: (-a["modulos_presentes"], -a["lofts"], a["terra_movida_m3"]))
    resumos = sorted((a for a in avaliacoes if a["tipo"] == "resumo" and a["passa"]),
                     key=lambda a: (a["terraplenagem_rs"] if a["terraplenagem_rs"] is not None else math.inf,
                                    -(a["lofts"] or 0), a["terra_movida_m3"]))
    for k, a in enumerate(plantas, 1):
        a["posicao"] = k
    for k, a in enumerate(resumos, 1):
        a["posicao_resumo"] = k
    return {"criterio": "normas e segurança eliminam; entre as que passam, melhor custo-benefício (M&A pg:97b6e5a48dcf)",
            "ranking_plantas": criterio,
            "ranking_resumos": "versões só com números (03 › Estudos de masterplan): menor terraplenagem, mais lofts, menos terra",
            "plantas": [a["nome"] for a in plantas], "resumos": [a["nome"] for a in resumos],
            "eliminadas": {a["nome"]: a["falhas"] for a in avaliacoes if not a["passa"]}, "avaliacoes": avaliacoes}


# ---------------------------------------------------------------- projeto e IFC por versão

def projeto_da_versao(versao, base):
    """Projeto do Planejador da versão: lote, clima e regras da base (rev0); itens e elementos da versão. Os números
    de sistemas da planilha 20 valem para a rev0 e NÃO são copiados (só os do lote)."""
    p = json.loads(json.dumps(base))
    ocup = {"casa": 6, "LF": 4}
    p["itens"], p["gemeo"]["elementos"] = [], {}
    for e in versao["elementos"]:
        e = dict(e)
        oc = next((q for pre, q in ocup.items() if e["chave"].startswith(pre)), 0) if (e.get("area_m2") or 0) > 0 else 0
        it = I.item_planejador(e, oc)
        p["itens"].append(it)
        ch = e.pop("chave")
        p["gemeo"]["elementos"][ch] = {**e, "item_id": it["id"], "tipo_planejador": it["tipo"],
                                       "sem_area": not (e.get("area_m2") or 0) > 0}
    p["gemeo"]["fonte_por_valor"] = {k: v for k, v in base["gemeo"]["fonte_por_valor"].items() if k.startswith("lote.")}
    p["gemeo"]["estado_de_vida"] = {"padrao": "projetado", "por_elemento": {k: "projetado" for k in p["gemeo"]["elementos"]}}
    p["gemeo"]["semente"] = f"casa-physis-{versao['nome']}".replace(" ", "_")
    p["gemeo"]["revisao"] = versao["nome"]
    p["meta"]["nome"] = f"Casa Physis · Lote 168 · versão {versao['nome']} (TESTE)"
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compara versões de planta do Lote 168 (gêmeo digital)")
    ap.add_argument("versoes", nargs="*", help=".xlsx (aba Implantação) ou .csv")
    ap.add_argument("--semente", default=str(I.SEMENTE_ARQ))
    ap.add_argument("--masterplan", action="store_true", help="inclui as combinações da 03 › Estudos de masterplan")
    ap.add_argument("--editaveis", default=str(I.PASTA_PADRAO))
    ap.add_argument("--precos", default=None, help="CSV tipo;preco_m2;fonte")
    ap.add_argument("--saida", default=None, help="relatório .json")
    ap.add_argument("--ifc", default=None, help="pasta para o projeto e o IFC de cada versão de planta")
    ap.add_argument("--modelo", default=None, help="grava o CSV modelo (a rev0) neste arquivo e sai")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    base = G.carregar(a.semente)
    rev0 = versao_da_semente(base)
    if a.modelo:
        escrever_modelo_csv(rev0, a.modelo)
        print("modelo gravado em", a.modelo)
        return 0
    lote = lote_da_semente(base)
    ter = TerrenoPlanejador(lote["poly"], lote["pontos"])
    versoes = [rev0] + [ler_versao(v) for v in a.versoes]
    if a.masterplan:
        versoes += versoes_masterplan(I.Planilha("03", Path(a.editaveis) / I.ARQ_03))
    precos = ler_precos(a.precos) if a.precos else None
    rel = comparar([avaliar(v, lote, ter, precos) for v in versoes])
    for av in rel["avaliacoes"]:
        pos = av.get("posicao") or av.get("posicao_resumo")
        st = f"{pos}º" if av["passa"] else "eliminada"
        print(f"{av['nome']:<10} {av['tipo']:<7} {st:<10} ocupação {av['ocupacao_pct']} % · lofts {av['lofts']} · "
              f"terra {av['terra_movida_m3']} m³" + (f" · {'; '.join(av['falhas'])}" if av["falhas"] else ""))
    print("ranking:", rel["ranking_plantas"])
    if a.ifc:
        from . import gemeo_ifc
        pasta = Path(a.ifc)
        pasta.mkdir(parents=True, exist_ok=True)
        for v in versoes:
            if v["tipo"] != "planta" or v is rev0:
                continue
            pj = projeto_da_versao(v, base)
            (pasta / f"{v['nome']}.json").write_text(json.dumps(pj, ensure_ascii=False, indent=1), encoding="utf-8")
            (pasta / f"{v['nome']}.ifc").write_text(gemeo_ifc.escrever(pj, altura=(lote["altura_pavimento_m"],
                                                                                     lote["fonte_altura"])),
                                                    encoding="utf-8", newline="\n")
    if a.saida:
        Path(a.saida).write_text(json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
        print("relatório em", a.saida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
