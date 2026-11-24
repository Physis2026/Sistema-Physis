"""Gêmeo digital · G3 (versão de TESTE): IFC4 do lote a partir da semente do Planejador.

    python -m physis_hub.gemeo_ifc [--semente ARQ.json] [--saida ARQ.ifc]

O que entra no IFC (tudo vem da semente; nada é inventado):
- IfcProject marcado "ESTUDO PRELIMINAR (revisão 0) · TESTE";
- IfcSite "Lote 168" sem latitude/longitude (L-01: não há georreferência oficial; x/y local, P-01 = 0,0; z = cota);
  a superfície do terreno é uma malha de triângulos entre as curvas de nível da 03 › Levantamento e as cotas dos
  vértices da 20 (aproximação, não é levantamento 3D);
- um IfcBuildingElementProxy por elemento da 03 › Implantação (os 92), com o conjunto Physis_Gemeo (chave, zona,
  entidade, fonte, procedência, estado de vida, cota e a origem da altura) e cor da entidade da zona (PALETA.md);
- três IfcZone (Z1 Physis Engineering, Z2 Instituto Physis, Z3 Casa Physis) agrupando os elementos.

Altura das massas (decisões da dona: pg:16228b14d400 em 21/11 e pg:58d2e859f36a em 22/11): lofts, restaurante,
gourmet e Casa 1 com as alturas da prancha 02b; LAB e MEC e as demais edificações do 20 › Quadro de áreas com a altura
de pavimento da 03 (2,90 m; D8 × 2,59 da 02b); o resto é placa de 0,20 m só de desenho. Coberturas da 02b
(pg:74fabc0568d2): plana 3% nos contêineres, água única 15% nos lofts, cônica 45% no restaurante (D7 × 14° da 03).
Cada peça leva a relação com o terreno (corte intencional ou [CONFERIR]). Tudo [CONFERIR] até o projeto executivo. Elementos sem cota na 03 ficam na cota do terreno interpolada.
Elementos sem área na 03 (0,01 m) entram sem geometria, para a contagem bater.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

from . import gemeo as G
from .ifc import Escritor, r_, s_

ESPESSURA_DESENHO_M = 0.20  # só de desenho (decisão pg:16228b14d400), não é dado de projeto
# chaves da 03 que são edificações no 20 › Quadro de áreas (Casa 1, Gourmet, LAB, MEC, Restaurante, Lofts,
# Apoio e lavabos, Cogumelário e canil, Loja 24 h)
EDIFICACOES = ("casa", "gourmet", "lab", "lab_up", "mec", "mec_up", "bar", "staff", "lavabos", "cogu", "pet", "loja")
def eh_edificacao(chave):
    """Edificação do 20 › Quadro de áreas: as chaves de EDIFICACOES e os lofts (LF*)."""
    return chave in EDIFICACOES or chave.startswith("LF")


COR_ENTIDADE = {"Z1": "#1A4D2E", "Z2": "#4A8A5A", "Z3": "#BB6B4A"}  # PALETA.md (guia de identidade)
COR_TERRENO = "#B9A97F"  # areia, PALETA.md
SEMENTE_PADRAO = Path(__file__).resolve().parents[2] / "modulos" / "planejador" / "gemeo" / "casa-physis-rev0.json"


class SementeIncompleta(ValueError):
    pass


# ---------------------------------------------------------------- forma de cada elemento (refinamento, 21/11)

COR_TELHADO = "#C9D2C4"  # linha, PALETA.md
COR_PLACA = "#1B1F23"  # carvão, PALETA.md
# trecho "Onde" da 03 › Placas solares (chave na semente) → elementos que recebem as placas (divididas por igual)
PLACAS_LOCAL = {"casa_cobertura_dos_20_pes": ("casa",), "pergolado_do_terraco_da_casa": ("casa",),
                "pergolados_do_lab_e_do_mec": ("lab_up", "mec_up"), "coberturas_do_lab_e_do_mec": ("lab_up", "mec_up"),
                "gourmet": ("gourmet",), "restaurante_face_norte": ("bar",)}


def forma(e, it):
    """Forma real quando a descrição da 03 diz: 'Ø 5,0 m' (redondo) ou 'A × B … giro N°' (retângulo girado). A medida
    só é aceita se reproduz a caixa envolvente da 03 (larg. × prof.) com 6 cm de folga; senão fica a caixa."""
    import math
    from .gemeo_importar import numeros_br
    desc = str(e.get("descricao") or "")
    w, d = (e.get("larg_m") or it["w"]), (e.get("prof_m") or it["d"])
    caixa = {"tipo": "ret", "a": w, "b": d, "giro": 0.0, "origem": "caixa da 03 (larg. × prof.)"}
    m = re.search(r"Ø\s*(\d+(?:,\d+)?)\s*m", desc)
    if m:
        dia = numeros_br(m.group(1))[0]
        if abs(dia - w) < 0.06 and abs(dia - d) < 0.06:
            return {"tipo": "circ", "r": dia / 2, "giro": 0.0, "origem": f"redondo Ø {m.group(1)} m (descrição da 03)"}
    g = re.search(r"giro (\d+(?:,\d+)?)°", desc)
    md = re.search(r"(\d+(?:,\d+)?) × (\d+(?:,\d+)?)", desc)
    if g and md:
        t = math.radians(numeros_br(g.group(1))[0])
        A, B = numeros_br(md.group(1))[0], numeros_br(md.group(2))[0]
        for a, b in ((A, B), (B, A)):
            bw, bd = a * math.cos(t) + b * math.sin(t), a * math.sin(t) + b * math.cos(t)
            if abs(bw - w) < 0.06 and abs(bd - d) < 0.06:
                sinal = -1 if G.ESPELHO_X else 1
                return {"tipo": "ret", "a": a, "b": b, "giro": sinal * math.degrees(t),
                        "origem": f"{md.group(0)} m girado {g.group(1)}° (descrição da 03; reproduz a caixa "
                                  f"{w} × {d}); no gêmeo espelhado o giro troca de sinal; sentido [CONFERIR]"}
    return caixa


def _coloc(W, rel, x, y, z, giro=0.0):
    import math
    p = W.ponto(x, y, z)
    if giro:
        t = math.radians(giro)
        ax = W.add(f"IFCAXIS2PLACEMENT3D({p},{W.add('IFCDIRECTION((0.,0.,1.))')},"
                   f"{W.add(f'IFCDIRECTION(({r_(math.cos(t))},{r_(math.sin(t))},0.))')})")
    else:
        ax = W.add(f"IFCAXIS2PLACEMENT3D({p},$,$)")
    return W.add(f"IFCLOCALPLACEMENT({rel},{ax})")


def _prisma_x(W, comprimento, pts_yz, z0=0.0):
    """Sólido com perfil no plano (y, z) local, estendido ao longo de x (centrado)."""
    pts = [W.add(f"IFCCARTESIANPOINT(({r_(y)},{r_(z)}))") for y, z in pts_yz]
    poly = W.add(f"IFCPOLYLINE(({','.join(pts + pts[:1])}))")
    perfil = W.add(f"IFCARBITRARYCLOSEDPROFILEDEF(.AREA.,$,{poly})")
    pos = W.add(f"IFCAXIS2PLACEMENT3D({W.ponto(-comprimento / 2, 0, z0)},{W.add('IFCDIRECTION((1.,0.,0.))')},"
                f"{W.add('IFCDIRECTION((0.,1.,0.))')})")
    return W.add(f"IFCEXTRUDEDAREASOLID({perfil},{pos},{W.add('IFCDIRECTION((0.,0.,1.))')},{r_(comprimento)})")


def placas_por_elemento(projeto):
    """{chave: (placas, [fontes])} pela 03 › Placas solares; lofts: 'N por loft' em cada loft com área. O que não
    tem lugar (loft sem área na 03, divergência D3) volta em '_sem_lugar'."""
    fv, els = projeto["gemeo"]["fonte_por_valor"], projeto["gemeo"]["elementos"]
    out = {}
    for cam, d in fv.items():
        m = re.match(r"energia\.fv\.local\.(.+)\.placas$", cam)
        if not m:
            continue
        local, n = m.group(1), d["valor"]
        ml = re.match(r"lofts_(\d+)_por_loft_(\d+)$", local)
        if ml:
            por, lofts = int(ml.group(1)), sorted(k for k, e in els.items() if k.startswith("LF") and not e["sem_area"])
            alvo = [(k, por) for k in lofts]
            resto = n - por * len(lofts)
            if resto:
                alvo.append(("_sem_lugar", resto))
        elif local in PLACAS_LOCAL:
            alvo = [(k, n / len(PLACAS_LOCAL[local])) for k in PLACAS_LOCAL[local]]
        else:
            alvo = [("_sem_lugar", n)]
        for k, q in alvo:
            tot, fs = out.get(k, (0, []))
            out[k] = (tot + q, fs + [d["fonte"]])
    return out


def altura_pavimento(els):
    """Altura de pavimento que a 03 dá: cota de cima − cota de baixo de LAB e de MEC (têm de concordar)."""
    difs = {}
    for baixo, cima in (("lab", "lab_up"), ("mec", "mec_up")):
        b, c = els.get(baixo, {}).get("piso_topo_m"), els.get(cima, {}).get("piso_topo_m")
        if b is None or c is None:
            raise SementeIncompleta(f"sem cota de {baixo}/{cima} para a altura de pavimento")
        difs[baixo] = round(c - b, 3)
    if len(set(difs.values())) != 1:
        raise SementeIncompleta(f"LAB e MEC dão alturas diferentes: {difs}")
    h = difs["lab"]
    fonte = (f"03 › Implantação: LAB {els['lab']['piso_topo_m']} → {els['lab_up']['piso_topo_m']} e "
             f"MEC {els['mec']['piso_topo_m']} → {els['mec_up']['piso_topo_m']} (decisão pg:16228b14d400) [CONFERIR]")
    return h, fonte


# ---------------------------------------------------------------- terreno

def terreno_planejador(projeto):
    """A mesma superfície do Planejador (grade de 110 células, inverso do quadrado da distância): o 3D, o comparador e
    o Planejador passam a concordar (antes, a malha só das curvas laterais punha peças 'voando' ou 'enterradas')."""
    from .gemeo_versoes import TerrenoPlanejador
    return TerrenoPlanejador(projeto["terreno"]["poly"], projeto["terreno"]["pontos"])


def malha_terreno(projeto, T=None):
    """Malha do terreno para o IFC: nós da grade do Planejador e triângulos das células que tocam o lote."""
    from .gemeo_versoes import dentro
    T = T or terreno_planejador(projeto)
    poly = projeto["terreno"]["poly"]
    v = [(T.x0 + i * T.cs, T.y0 + j * T.cs, T.Z[j * T.nx + i]) for j in range(T.ny) for i in range(T.nx)]
    ins = [dentro((x, y), poly) for x, y, _ in v]
    idx = lambda i, j: j * T.nx + i
    tri = []
    for j in range(T.ny - 1):
        for i in range(T.nx - 1):
            c = (idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1))
            if any(ins[k] for k in c):
                tri += [(c[0], c[1], c[2]), (c[0], c[2], c[3])]
    usados = sorted({k for t in tri for k in t})
    novo = {k: n for n, k in enumerate(usados)}
    return [v[k] for k in usados], [tuple(novo[k] for k in t) for t in tri]


def malha_curvas(projeto):
    """Malha antiga (até 22/11): triângulos só entre os lados x≈0 e x≈22 (curvas + vértices). Fica para comparação."""
    pts = projeto["terreno"]["pontos"]
    if len(pts) < 4:
        raise SementeIncompleta("terreno sem pontos com cota")
    xs = [p[0] for p in pts]
    meio = (min(xs) + max(xs)) / 2
    esq = sorted((p for p in pts if p[0] <= meio), key=lambda p: p[1])
    dir_ = sorted((p for p in pts if p[0] > meio), key=lambda p: p[1])
    # o lado direito pode ter curva além do fim do lote (875 em y = 74 > 72,27): fica fora do lote, sai da malha
    ymax = max(p[1] for p in projeto["terreno"]["poly"])
    dir_ = [p for p in dir_ if p[1] <= ymax + 1e-6]
    esq = [p for p in esq if p[1] <= ymax + 1e-6]
    if len(esq) < 2 or len(dir_) < 2:
        raise SementeIncompleta("terreno sem pontos nos dois lados do lote")
    v = esq + dir_
    ie, id_ = list(range(len(esq))), list(range(len(esq), len(v)))
    tri, a, b = [], 0, 0
    while a < len(ie) - 1 or b < len(id_) - 1:  # zíper: avança o lado cujo próximo ponto está mais perto da Rua H
        if b >= len(id_) - 1 or (a < len(ie) - 1 and v[ie[a + 1]][1] <= v[id_[b + 1]][1]):
            tri.append((ie[a], ie[a + 1], id_[b]))
            a += 1
        else:
            tri.append((ie[a], id_[b + 1], id_[b]))
            b += 1
    return v, tri


def cota_no_terreno(v, tri, x, y):
    """z do terreno em (x, y) pelos triângulos; fora da malha, a cota do ponto mais próximo."""
    for i, j, k in tri:
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = v[i], v[j], v[k]
        d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if abs(d) < 1e-12:
            continue
        l1 = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / d
        l2 = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / d
        l3 = 1 - l1 - l2
        if min(l1, l2, l3) >= -1e-9:
            return l1 * z1 + l2 * z2 + l3 * z3
    return min(v, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)[2]


# ---------------------------------------------------------------- escrita

def _rgb(hexa):
    h = hexa.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


# ---------------------------------------------------------------- estrutura até o terreno (22/11)
# Pedido da dona: "as casas estão voando". Pilares e blocos com as quantidades da 20 › Fundações e as regras da 02b
# (Casa 1: A1–A15 nos cantos e no meio dos contêineres; LAB/MEC: 8 pilares; lofts: grade, 8 apoios; restaurante:
# C0–C8 centro e anel a cada 45°; pilar tubular 100 × 100 × 4,75; bloco 0,70 × 0,70 × 0,60 aflorando 30 cm, 0,60 nos
# lofts e na Casa 1). A posição de cada apoio é distribuição regular pela regra escrita: [CONFERIR] no executivo.
COR_PILAR = "#4A4F44"   # PALETA.md (texto secundário): aço galvanizado
COR_BLOCO = "#C9D2C4"   # PALETA.md (linha): concreto
PILAR_M, PAREDE_M = 0.100, 0.00475


def _mundo(fm, it, xl, yl):
    t = math.radians(fm["giro"])
    return it["x"] + xl * math.cos(t) - yl * math.sin(t), it["y"] + xl * math.sin(t) + yl * math.cos(t)


def _pontos_planta(fm, it):
    if fm["tipo"] == "circ":
        r = fm["r"]
        loc = [(0, 0)] + [(r * math.cos(k * math.pi / 4), r * math.sin(k * math.pi / 4)) for k in range(8)]
    else:
        a, b = fm["a"] / 2, fm["b"] / 2
        loc = [(0, 0), (-a, -b), (a, -b), (a, b), (-a, b)]
    return [_mundo(fm, it, x, y) for x, y in loc]


def apoios(chave, fm, projeto):
    """(posições locais, lado do bloco, fonte) dos apoios da edificação, ou None se as fontes não dão regra."""
    fv = lambda c: _fv(projeto, c)
    if chave == "bar" and fm["tipo"] == "circ":
        n, f = fv("estrutura.apoios.restaurante")
        if n is None:
            return None
        r = fm["r"]
        return ([(0.0, 0.0)] + [(r * math.cos(k * math.pi / 4), r * math.sin(k * math.pi / 4)) for k in range(8)], 0.70,
                f"C0 a C8 ({fv('estrutura.restaurante')[1]}); a 20 soma {n:g} apoios com os D1 a D10 dos decks ({f})")
    if fm["tipo"] != "ret":
        return None
    if chave in ("lab", "mec"):
        n, f = fv("estrutura.apoios.lab_ou_mec")
        txt, ft = fv("estrutura.lab_mec_pilares")
        cima = _elemento_e_item(projeto, chave + "_up")
        if n is None or txt is None or cima is None or int(n) != 8:
            return None
        ec, ic = cima
        a, b = fm["a"] / 2, fm["b"] / 2
        host = _elemento_e_item(projeto, chave)[1]
        p14 = [(-a, -b), (a, -b), (a, b), (-a, b)]
        ca, cb = ic["w"] / 2, ic["d"] / 2
        p58 = [(ic["x"] - host["x"] + sx * ca, ic["y"] - host["y"] + sy * cb, ec["piso_topo_m"])
               for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        return p14 + p58, 0.70, f"{txt} ({ft}); 8 apoios ({f})"
    regras = {"casa": ("estrutura.apoios.casa_1", 5, 3, 0.60, "estrutura.casa1"),
              "gourmet": ("estrutura.apoios.gourmet", 3, 2, 0.70, None)}
    if chave.startswith("LF"):
        cam = "estrutura.apoios.loft_20_m" if fm["a"] * fm["b"] >= 19.5 else "estrutura.apoios.loft_16_m"
        regra = (cam, 4, 2, 0.60, "estrutura.lofts")
    elif chave in ("deck1", "deck2"):
        n, f = fv("estrutura.restaurante")
        if n is None:
            return None
        a, b = fm["a"], fm["b"]
        return [(-a / 2 + a * i / 4, 0.0) for i in range(5)], 0.70, f"D1 a D10 dos decks, 5 por deck ({f})"
    elif chave in regras:
        regra = regras[chave]
    else:
        return None
    cam, nl, nc, lado, cam_txt = regra
    n, f = fv(cam)
    if n is None or nl * nc != int(n):
        return None
    a, b = fm["a"], fm["b"]
    if b > a:
        nl, nc = nc, nl
    pts = [(-a / 2 + a * i / (nl - 1), -b / 2 + b * j / (nc - 1)) for i in range(nl) for j in range(nc)]
    txt = fv(cam_txt)[0] if cam_txt else None
    return pts, lado, f"{int(n)} apoios ({f})" + (f"; {txt}" if txt else "")


EMPILHADOS = {"lab_up": "lab", "mec_up": "mec"}   # 03: LAB e MEC de cima sobre os de baixo
COR_CONTENCAO = "#4A4F44"   # PALETA.md
COR_TALUDE = "#8FB183"      # PALETA.md (verde claro): vetiver sobre o talude
TANQUES = ("cist", "fossa", "biodig", "piscina", "peixes", "lago", "minilago")


def _elemento_e_item(projeto, chave):
    e = projeto["gemeo"]["elementos"].get(chave)
    if not e:
        return None
    it = next((i for i in projeto["itens"] if i["id"] == e["item_id"]), None)
    return (e, it) if it else None


def _perfil_w(W, desig):
    """Perfil I a partir da designação ('W 200 × 15'): altura = o número da designação (mm); mesa = metade da altura
    e espessuras de desenho, a conferir no catálogo [CONFERIR]."""
    m = re.search(r"W\s*(\d+)", desig or "")
    d = (int(m.group(1)) if m else 150) / 1000
    p2 = W.add(f"IFCAXIS2PLACEMENT2D({W.add('IFCCARTESIANPOINT((0.,0.))')},$)")
    return W.add(f"IFCISHAPEPROFILEDEF(.AREA.,{s_(desig)},{p2},{r_(d / 2)},{r_(d)},{r_(d * 0.04)},{r_(d * 0.06)},$,$,$)"), d


def _barra(W, oh, corpo, estilo, pl_site, p0, p1, perfil, cor, entidade, tipo, nome, tag, guid_partes, props):
    """Peça linear entre dois pontos 3D (viga, contravento): perfil no plano perpendicular, estendido no eixo."""
    dx, dy, dz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    L = math.sqrt(dx * dx + dy * dy + dz * dz)
    if L < 0.05:
        return None
    ax = (dx / L, dy / L, dz / L)
    ref = (-ax[1], ax[0], 0.0) if abs(ax[2]) < 0.99 else (1.0, 0.0, 0.0)
    n = math.sqrt(sum(c * c for c in ref))
    ref = tuple(c / n for c in ref)
    pos = W.add(f"IFCAXIS2PLACEMENT3D({W.ponto(*p0)},{W.add(f'IFCDIRECTION(({r_(ax[0])},{r_(ax[1])},{r_(ax[2])}))')},"
                f"{W.add(f'IFCDIRECTION(({r_(ref[0])},{r_(ref[1])},{r_(ref[2])}))')})")
    sol = W.add(f"IFCEXTRUDEDAREASOLID({perfil},{W.add(f'IFCAXIS2PLACEMENT3D({W.ponto(0, 0, 0)},$,$)')},"
                f"{W.add('IFCDIRECTION((0.,0.,1.))')},{r_(L)})")
    W.add(f"IFCSTYLEDITEM({sol},({estilo(cor)}),$)")
    rep = W.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({W.add(f'IFCSHAPEREPRESENTATION({corpo},{chr(39)}Body{chr(39)},{chr(39)}SweptSolid{chr(39)},({sol}))')}))")
    predef = {"IFCBEAM": "BEAM", "IFCMEMBER": "BRACE", "IFCPIPESEGMENT": "RIGIDSEGMENT"}.get(entidade, "USERDEFINED")
    ref_el = W.add(f"{entidade}({W.guid(*guid_partes)},{oh},{s_(nome)},$,{s_(tipo)},{W.add(f'IFCLOCALPLACEMENT({pl_site},{pos})')},"
                   f"{rep},{s_(tag)},.{predef}.)")
    W.pset(oh, "Physis_Estrutura", [W.propriedade(k, v, "m" if k == "Comprimento" else None) for k, v in props] +
           [W.propriedade("Comprimento", round(L, 3), "m")], [ref_el], "/".join(map(str, guid_partes)))
    return ref_el


# ---------------------------------------------------------------- hidráulica, esgoto e drenagem (22/11)
# Camada casa-gemeo-hidraulica (decisão pg:ee988f1fe957). A 20 dá a rede de esgoto trecho a trecho (DN, comprimento,
# cotas de fundo) e as dimensões úteis das unidades; a posição em planta das caixas não existe: elas ficam ao longo
# da reta entre as peças conhecidas, na proporção dos comprimentos da 20 [CONFERIR]. Sem posição: sem geometria.
COR_ESGOTO = "#8A6410"     # PALETA.md (atenção, ocre)
COR_AGUA = "#C9D2C4"       # PALETA.md (linha)
ANCORAS_ESGOTO = {"Casa": "casa", "LAB": "lab", "Biodigestor": "biodig", "Restaurante": "bar", "Fossa e filtro": "fossa"}


def _medidas(txt):
    from .gemeo_importar import numeros_br
    return numeros_br(re.split(r"\(", str(txt or ""))[0])


def rede_esgoto(projeto):
    """Nós (nome → (x, y)), tubos (de, para, DN, z0, z1, comprimento da 20, terreno no início) e avisos de coerência."""
    fv = projeto["gemeo"]["fonte_por_valor"]
    trechos = {}
    for cam, d in fv.items():
        m = re.match(r"esgoto\.trecho\.(.+)\.(dn_mm|comprimento_m|fundo_inicio_m|fundo_fim_m|terreno_inicio_m|terreno_fim_m)$", cam)
        if m:
            tr = trechos.setdefault(m.group(1), {"nome": d.get("nota", "").split(";")[0], "fonte": d["fonte"]})
            tr[m.group(2)] = d["valor"]
    if not trechos:
        return {}, [], []
    lista = list(trechos.values())
    for tr in lista:
        a, b = [s.strip() for s in tr["nome"].split("→")]
        tr["de"], tr["para"] = a, b
    # cadeias contínuas (fim de um = início do outro)
    cadeias, usados = [], set()
    for tr in lista:
        if any(o["para"] == tr["de"] for o in lista) or id(tr) in usados:
            continue
        c, atual = [], tr
        while atual and id(atual) not in usados:
            usados.add(id(atual))
            c.append(atual)
            atual = next((o for o in lista if o["de"] == atual["para"]), None)
        cadeias.append(c)
    els = projeto["gemeo"]["elementos"]
    itens = {i["id"]: i for i in projeto["itens"]}
    pos_anc = {n: (itens[els[k]["item_id"]]["x"], itens[els[k]["item_id"]]["y"]) for n, k in ANCORAS_ESGOTO.items() if k in els}
    nos, avisos = dict(pos_anc), []
    for c in cadeias:
        nomes = [c[0]["de"]] + [tr["para"] for tr in c]
        idx = [i for i, n in enumerate(nomes) if n in pos_anc]
        for i0, i1 in zip(idx, idx[1:]):
            p0, p1 = pos_anc[nomes[i0]], pos_anc[nomes[i1]]
            comps = [c[k]["comprimento_m"] for k in range(i0, i1)]
            soma, reta = sum(comps), math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            if reta > soma + 0.5:
                avisos.append({"de": nomes[i0], "para": nomes[i1], "soma_20_m": round(soma, 2), "reta_03_m": round(reta, 2)})
            acum = 0.0
            for k in range(i0 + 1, i1):
                acum += comps[k - i0 - 1]
                f = acum / soma if soma else 0
                nos.setdefault(nomes[k], (p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f))
    tubos = [{**tr, "z0": tr["fundo_inicio_m"], "z1": tr["fundo_fim_m"]} for c in cadeias for tr in c
             if tr["de"] in nos and tr["para"] in nos]
    return nos, tubos, avisos


def _caixa(W, corpo, estilo, cor, dx, dy, dz, centro=False):
    p2 = W.add(f"IFCAXIS2PLACEMENT2D({W.add('IFCCARTESIANPOINT((0.,0.))')},$)")
    sol = W.add(f"IFCEXTRUDEDAREASOLID({W.add(f'IFCRECTANGLEPROFILEDEF(.AREA.,$,{p2},{r_(dx)},{r_(dy)})')},"
                f"{W.add(f'IFCAXIS2PLACEMENT3D({W.ponto(0, 0, 0)},$,$)')},{W.add('IFCDIRECTION((0.,0.,1.))')},{r_(dz)})")
    W.add(f"IFCSTYLEDITEM({sol},({estilo(cor)}),$)")
    return W.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({W.add(f'IFCSHAPEREPRESENTATION({corpo},{chr(39)}Body{chr(39)},{chr(39)}SweptSolid{chr(39)},({sol}))')}))")


def _cilindro(W, corpo, estilo, cor, r, h):
    p2 = W.add(f"IFCAXIS2PLACEMENT2D({W.add('IFCCARTESIANPOINT((0.,0.))')},$)")
    sol = W.add(f"IFCEXTRUDEDAREASOLID({W.add(f'IFCCIRCLEPROFILEDEF(.AREA.,$,{p2},{r_(r)})')},"
                f"{W.add(f'IFCAXIS2PLACEMENT3D({W.ponto(0, 0, 0)},$,$)')},{W.add('IFCDIRECTION((0.,0.,1.))')},{r_(h)})")
    W.add(f"IFCSTYLEDITEM({sol},({estilo(cor)}),$)")
    return W.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({W.add(f'IFCSHAPEREPRESENTATION({corpo},{chr(39)}Body{chr(39)},{chr(39)}SweptSolid{chr(39)},({sol}))')}))")


def _hidraulica(W, oh, corpo, estilo, pl_site, projeto, T, ref_por_chave):
    """Rede de esgoto, unidades de tratamento, cisternas, pontos de água e drenagem. Devolve (refs, zona de cada ref)."""
    fv = projeto["gemeo"]["fonte_por_valor"]
    els = projeto["gemeo"]["elementos"]
    itens = {i["id"]: i for i in projeto["itens"]}
    out = []
    pos = lambda k: (itens[els[k]["item_id"]]["x"], itens[els[k]["item_id"]]["y"])
    nos, tubos, avisos = rede_esgoto(projeto)
    # tubos
    for k, tb in enumerate(tubos, 1):
        (x0, y0), (x1, y1) = nos[tb["de"]], nos[tb["para"]]
        p2 = W.add(f"IFCAXIS2PLACEMENT2D({W.add('IFCCARTESIANPOINT((0.,0.))')},$)")
        r = tb["dn_mm"] / 2000
        perf = W.add(f"IFCCIRCLEPROFILEDEF(.AREA.,{s_('DN ' + format(tb['dn_mm'], 'g'))},{p2},{r_(r)})")
        ref = _barra(W, oh, corpo, estilo, pl_site, (x0, y0, tb["z0"] + r), (x1, y1, tb["z1"] + r), perf, COR_ESGOTO,
                     "IFCPIPESEGMENT", "tubo de esgoto", f"Esgoto {tb['nome']}", f"ESG-{k}", ("esg", k),
                     [("Trecho", tb["nome"]), ("DN", f"{tb['dn_mm']:g} mm"), ("ComprimentoPlanilha", f"{tb['comprimento_m']:g} m"),
                      ("Fonte", tb["fonte"]), ("Cotas", f"fundo {tb['z0']:g} → {tb['z1']:g} m (20)"),
                      ("Posicao", "traçado em planta pela reta entre as peças conhecidas [CONFERIR]")])
        if ref:
            out.append((ref, "Z2"))
    # caixas de inspeção e de gordura nos nós intermediários (do fundo ao terreno)
    dim_ci = _medidas((fv.get("esgoto.dimensoes.caixas_de_inspecao") or {}).get("valor")) or [0.6, 0.6]
    dim_cg = _medidas((fv.get("esgoto.dimensoes.caixa_de_gordura") or {}).get("valor"))
    for nome, (x, y) in nos.items():
        if nome in ANCORAS_ESGOTO:
            continue
        sai = next((tb for tb in tubos if tb["de"] == nome), None)
        chega = next((tb for tb in tubos if tb["para"] == nome), None)
        fundo = min(v for v in ((sai or {}).get("z0"), (chega or {}).get("z1")) if v is not None)
        terreno = (sai or {}).get("terreno_inicio_m") or (chega or {}).get("terreno_fim_m") or T.z(x, y)
        gord = nome.lower().startswith("cgord")
        dx, dy = (dim_cg[0], dim_cg[1]) if gord and len(dim_cg) >= 2 else (dim_ci[0], dim_ci[1])
        h = max(terreno - fundo, dim_cg[2] if gord and len(dim_cg) >= 3 else 0.3)
        rep = _caixa(W, corpo, estilo, COR_ESGOTO, dx, dy, h)
        el = W.add(f"IFCDISTRIBUTIONCHAMBERELEMENT({W.guid('ci', nome)},{oh},{s_(nome)},$,"
                   f"{s_('caixa de gordura' if gord else 'caixa de inspeção')},{W.colocacao(pl_site, x, y, fundo)},{rep},{s_(nome)},"
                   f".{'USERDEFINED' if gord else 'INSPECTIONCHAMBER'}.)")
        W.pset(oh, "Physis_Esgoto", [W.propriedade("Fundo", round(fundo, 3), "m"), W.propriedade("Terreno", round(terreno, 3), "m"),
                                     W.propriedade("Fonte", (sai or chega)["fonte"]),
                                     W.propriedade("Posicao", "na proporção dos comprimentos da 20 [CONFERIR]")], [el], "ci-" + nome)
        out.append((el, "Z2"))
    # unidades de tratamento
    def tanque(chave_el, nome, rep, z0, props, zona, tag):
        x, y = pos(chave_el)
        el = W.add(f"IFCTANK({W.guid('tq', tag)},{oh},{s_(nome)},$,{s_(nome)},{W.colocacao(pl_site, x + tag_off.get(tag, 0.0), y, z0)},"
                   f"{rep},{s_(tag)},.USERDEFINED.)")
        W.pset(oh, "Physis_Tanque", [W.propriedade(k, v) for k, v in props], [el], "tq-" + tag)
        out.append((el, zona))
    tag_off = {}
    bio = _medidas((fv.get("esgoto.dimensoes.biodigestor") or {}).get("valor"))
    if "biodig" in els and len(bio) >= 2:
        zt = els["biodig"]["piso_topo_m"]
        tanque("biodig", "Biodigestor", _cilindro(W, corpo, estilo, COR_ESGOTO, bio[0] / 2, bio[1]), zt - bio[1],
               [("Dimensoes", fv["esgoto.dimensoes.biodigestor"]["valor"]), ("Volume", f"{fv['esgoto.biodigestor']['valor']:g} m³"),
                ("Fonte", fv["esgoto.dimensoes.biodigestor"]["fonte"]), ("Topo", "no piso / topo da 03")], "Z2", "biodigestor")
    fos = _medidas((fv.get("esgoto.dimensoes.fossa_septica") or {}).get("valor"))
    fil = _medidas((fv.get("esgoto.dimensoes.filtro_anaerobio") or {}).get("valor"))
    if "fossa" in els and len(fos) >= 3 and len(fil) >= 3:
        larg03 = itens[els["fossa"]["item_id"]]["w"]
        cabe = fos[0] + fil[0] <= larg03 + 0.05
        conf = "" if cabe else f" [CONFERIR: fossa {fos[0]:g} + filtro {fil[0]:g} = {fos[0] + fil[0]:g} m > {larg03:g} m da 03]"
        zt = els["fossa"]["piso_topo_m"]
        tag_off.update({"fossa": -(fos[0] + fil[0]) / 2 + fos[0] / 2, "filtro": (fos[0] + fil[0]) / 2 - fil[0] / 2})
        tanque("fossa", "Fossa séptica", _caixa(W, corpo, estilo, COR_ESGOTO, fos[0], fos[1], fos[2]), zt - fos[2],
               [("Dimensoes", fv["esgoto.dimensoes.fossa_septica"]["valor"]), ("Fonte", fv["esgoto.dimensoes.fossa_septica"]["fonte"]),
                ("Posicao", "lado a lado no platô da Rua G" + conf)], "Z3", "fossa")
        tanque("fossa", "Filtro anaeróbio", _caixa(W, corpo, estilo, COR_ESGOTO, fil[0], fil[1], fil[2]), zt - fil[2],
               [("Dimensoes", fv["esgoto.dimensoes.filtro_anaerobio"]["valor"]), ("Fonte", fv["esgoto.dimensoes.filtro_anaerobio"]["fonte"]),
                ("Posicao", "lado a lado no platô da Rua G" + conf)], "Z3", "filtro")
    # cisternas: C1, C2, C3 nos elementos da 03; C4–C10 sem posição (sem geometria)
    for cist, chave_el in (("c1", "cist1"), ("c2", "cist2"), ("c3", "cist4")):
        d = fv.get(f"agua.cisterna.{cist}.dimensoes")
        vol = fv.get(f"agua.cisterna.{cist}.volume_m3")
        med = _medidas(d["valor"]) if d else []
        if chave_el not in els or not d or len(med) < 3:
            continue
        n_tq = int(med[0]) if med[0] < 5 and len(med) >= 4 else 1           # "2 tanques de 3,1 × 1,6 × 2,0"
        dims = med[1:4] if n_tq > 1 else med[0:3]
        zt = els[chave_el]["piso_topo_m"]
        for j in range(n_tq):
            tag_off[f"{cist}-{j}"] = j * (dims[0] + 0.3)
            tanque(chave_el, f"Cisterna {cist.upper()}" + (f" · tanque {j + 1}" if n_tq > 1 else ""),
                   _caixa(W, corpo, estilo, COR_AGUA, dims[0], dims[1], dims[2]), zt - dims[2],
                   [("Dimensoes", d["valor"]), ("Volume", f"{vol['valor']:g} m³" if vol else "[MARCADOR]"), ("Fonte", d["fonte"]),
                    ("Posicao", "no elemento da 03" + (" (2º tanque ao lado: a 03 só desenha um) [CONFERIR]" if j else ""))],
                   els[chave_el]["zona"], f"{cist}-{j}")
    for cist in ("c4_a_c7_modulares", "c8_a_c10_modulares"):
        d, vol = fv.get(f"agua.cisterna.{cist}.dimensoes"), fv.get(f"agua.cisterna.{cist}.volume_m3")
        if d and vol:
            el = W.add(f"IFCTANK({W.guid('tq', cist)},{oh},{s_('Cisternas ' + cist.split('_')[0].upper() + ' a ' + cist.split('_')[2].upper())},"
                       f"$,'cisternas modulares',{W.colocacao(pl_site)},$,{s_(cist)},.USERDEFINED.)")
            W.pset(oh, "Physis_Tanque", [W.propriedade("Volume", f"{vol['valor']:g} m³"), W.propriedade("Dimensoes", d["valor"]),
                                         W.propriedade("Fonte", vol["fonte"]), W.propriedade("Local", vol.get("nota") or ""),
                                         W.propriedade("Posicao", "[MARCADOR] a 03 não desenha")], [el], "tq-" + cist)
            out.append((el, vol["zona"] if vol["zona"] in G.ZONAS else "Z2"))
    # pontos de água (cota e pressão da 20) nos elementos da 03
    for cam, d in fv.items():
        m = re.match(r"agua\.ponto\.(.+)\.cota_m$", cam)
        chave_el = (d.get("nota") or "").replace("elemento da 03: ", "") if m else None
        if not m or chave_el not in ref_por_chave:
            continue
        pr = fv.get(f"agua.ponto.{m.group(1)}.pressao_mca", {})
        props = [W.propriedade("CotaPlanilha20", d["valor"], "m"), W.propriedade("PressaoEstatica", pr.get("valor"), "m.c.a."),
                 W.propriedade("Solucao", pr.get("nota") or ""), W.propriedade("Fonte", d["fonte"])]
        if d.get("conferir"):
            alt = d["conferir"]["alternativas"][0]
            props.append(W.propriedade("Conferir", f"{d['conferir']['divergencia']}: cota {d['valor']:g} (20) × {alt['valor']:g} (03)"))
        W.pset(oh, "Physis_Agua", props, [ref_por_chave[chave_el]], "agua-" + m.group(1))
    # drenagem: dados da 20 sem posição (sem geometria), jardim de chuva no elemento da 03
    for cam, d in fv.items():
        m = re.match(r"drenagem\.elemento\.(.+)$", cam)
        if not m:
            continue
        if m.group(1).startswith("jardim_de_chuva") and "chuva_h" in ref_por_chave:
            W.pset(oh, "Physis_Drenagem", [W.propriedade("Dados", d["valor"]), W.propriedade("Fonte", d["fonte"])],
                   [ref_por_chave["chuva_h"]], "dren-" + m.group(1))
            continue
        el = W.add(f"IFCDISTRIBUTIONCHAMBERELEMENT({W.guid('dren', m.group(1))},{oh},{s_(m.group(1).replace('_', ' '))},$,"
                   f"'drenagem',{W.colocacao(pl_site)},$,{s_('DREN-' + m.group(1)[:20])},.USERDEFINED.)")
        W.pset(oh, "Physis_Drenagem", [W.propriedade("Dados", d["valor"]), W.propriedade("Fonte", d["fonte"]),
                                       W.propriedade("Posicao", "[MARCADOR] traçado sem planta (DWG)")], [el], "dren-" + m.group(1))
        out.append((el, "Z3"))
    # avisos de coerência da rede (viram achados do conferente)
    for av in avisos:
        el = W.add(f"IFCDISTRIBUTIONCHAMBERELEMENT({W.guid('aviso', av['de'], av['para'])},{oh},"
                   f"{s_('Aviso de rede: ' + av['de'] + ' → ' + av['para'])},$,'aviso',{W.colocacao(pl_site)},$,'AVISO',.USERDEFINED.)")
        W.pset(oh, "Physis_Esgoto", [W.propriedade("Conferir", f"soma dos trechos {av['soma_20_m']} m (20) menor que a reta "
                                                              f"{av['reta_03_m']} m entre as peças (03) [CONFERIR]")], [el], "aviso-" + av["de"])
        out.append((el, "Z2"))
    return out


def _vigas_e_contraventos(W, oh, corpo, estilo, pl_site, chave, e, fm, it, z, T, projeto):
    """Vigas (IfcBeam) e contraventos em X (IfcMember) pelas regras da 02b; posições pela regra escrita [CONFERIR]."""
    fv = lambda c: _fv(projeto, c)
    refs, segs = [], []          # segs: (p0, p1, designação, fonte, nome)
    M = lambda xl, yl, zz: (*_mundo(fm, it, xl, yl), zz)
    if chave in ("lab", "mec"):
        des, f = fv("estrutura.vigas.lab_mec")
        cima = _elemento_e_item(projeto, chave + "_up")
        if des and cima:
            ec, ic = cima
            zc = ec["piso_topo_m"]
            for sx in (-1, 1):
                x = ic["x"] + sx * ic["w"] / 2
                segs.append(((x, ic["y"] - ic["d"] / 2, zc), (x, ic["y"] + ic["d"] / 2, zc), des, f, "viga sob o contêiner de cima"))
    elif chave.startswith("LF") and fm["tipo"] == "ret":
        db_, fb = fv("estrutura.vigas.lofts_borda")
        dc, fc = fv("estrutura.vigas.lofts_central")
        if db_ and dc:
            a, b = fm["a"] / 2, fm["b"] / 2
            for yl, des, f, nome in ((-b, db_, fb, "viga de borda"), (0.0, dc, fc, "viga central"), (b, db_, fb, "viga de borda")):
                segs.append((M(-a, yl, z), M(a, yl, z), des, f, nome))
    elif chave == "bar" and fm["tipo"] == "circ":
        des, f = fv("estrutura.vigas.restaurante")
        if des:
            r = fm["r"]
            anel = [M(r * math.cos(k * math.pi / 4), r * math.sin(k * math.pi / 4), z) for k in range(8)]
            for k in range(8):
                segs.append((M(0, 0, z), anel[k], des, f, "viga radial"))
                segs.append((anel[k], anel[(k + 1) % 8], des, f, "anel"))
    elif chave == "casa" and fm["tipo"] == "ret":
        des, f = fv("estrutura.vigas.casa1_v3")
        hc = fv("casa1.altura_conteiner_m")[0]
        if des and hc:
            a = fm["a"] / 2
            segs.append((M(-a, 0.0, z + hc), M(a, 0.0, z + hc), des, f, "V3 · reforço da parede aberta"))
    for k, (p0, p1, des, f, nome) in enumerate(segs, 1):
        perfil, d = _perfil_w(W, des)
        q0, q1 = (p0[0], p0[1], p0[2] - d / 2), (p1[0], p1[1], p1[2] - d / 2)
        v = _barra(W, oh, corpo, estilo, pl_site, q0, q1, perfil, COR_PILAR, "IFCBEAM", f"viga {des}",
                   f"{nome.capitalize()} · {chave}", f"{chave}-V{k}", ("viga", chave, k),
                   [("Hospedeiro", chave), ("Peca", f"{nome} {des}"), ("Fonte", f),
                    ("Perfil", "altura da designação; mesa e espessuras de desenho [CONFERIR no catálogo]"),
                    ("Posicao", "pela regra escrita da 02b [CONFERIR]")])
        if v:
            refs.append(v)
    # contraventamento em X (lofts e restaurante) onde os pilares passam de 1 m
    txt, fcv = fv("estrutura.contraventamento")
    reg = apoios(chave, fm, projeto) if txt and (chave.startswith("LF") or chave == "bar") else None
    if reg:
        afl = fv("estrutura.bloco_aflorando_m")[0] or 0.30
        pts = [(*_mundo(fm, it, p[0], p[1]),) for p in reg[0]]
        base = [(x, y, T.z(x, y) + afl) for x, y in pts]
        if chave == "bar":
            pares = [(1 + 2 * k, 1 + (2 * k + 1) % 8) for k in range(4)]  # 4 vãos alternados do anel
        else:                                                              # 2 linhas: vãos das pontas de cada linha
            n = len(pts) // 2
            pares = [(0, 1), (n - 2, n - 1), (n, n + 1), (2 * n - 2, 2 * n - 1)] if fm["b"] > fm["a"] else \
                    [(0, 2), (1, 3), (len(pts) - 4, len(pts) - 2), (len(pts) - 3, len(pts) - 1)]
        ponto0 = W.add("IFCCARTESIANPOINT((0.,0.))")          # sem f-string aninhada: o sistema roda em Python 3.10 (23/11/2026)
        eixo0 = W.add(f"IFCAXIS2PLACEMENT2D({ponto0},$)")
        perfil_c = W.add(f"IFCRECTANGLEPROFILEDEF(.AREA.,$,{eixo0},0.03,0.03)")
        for k, (i, j) in enumerate(pares, 1):
            if i >= len(pts) or j >= len(pts) or min(z - base[i][2], z - base[j][2]) < 1.0:
                continue
            for m, (a0, a1) in enumerate((((*pts[i], base[i][2]), (*pts[j], z)), ((*pts[j], base[j][2]), (*pts[i], z)))):
                v = _barra(W, oh, corpo, estilo, pl_site, a0, a1, perfil_c, COR_PILAR, "IFCMEMBER", "contravento",
                           f"Contravento {k}{'ab'[m]} · {chave}", f"{chave}-X{k}{'ab'[m]}", ("cv", chave, k, m),
                           [("Hospedeiro", chave), ("Peca", f"contraventamento {txt}"), ("Fonte", fcv),
                            ("Perfil", "seção da barra [MARCADOR]: desenho 30 × 30 mm"),
                            ("Posicao", "vão escolhido pela regra de desenho [CONFERIR]")])
                if v:
                    refs.append(v)
    return refs


def _contencao(W, oh, corpo, estilo, pl_site, chave, e, fm, it, z, T, projeto):
    """Muro drenado no platô da Rua G (02b, prancha 21) e taludes 1:1 com gabião e vetiver nos outros platôs
    cortados (02b), nas bordas onde o terreno passa 0,3 m acima do piso. Espessuras [MARCADOR], desenho."""
    if fm["tipo"] != "ret" or e["sem_area"] or e.get("piso_topo_m") is None or chave.startswith(TANQUES):
        return []
    if not ((e.get("corte_m3") or 0) > 0):
        return []
    fv = lambda c: _fv(projeto, c)
    muro_txt, fm_ = fv("contencao.muro_rua_g")
    hmax_fonte = fv("contencao.muro_altura_max_m")[0]
    tal_txt, ft = fv("contencao.taludes")
    a, b = fm["a"] / 2, fm["b"] / 2
    bordas = [((-a, -b), (a, -b), (0, -1)), ((a, -b), (a, b), (1, 0)), ((a, b), (-a, b), (0, 1)), ((-a, b), (-a, -b), (-1, 0))]
    refs = []
    alt_borda = []
    for q0, q1, nrm in bordas:
        amostras = [(q0[0] + (q1[0] - q0[0]) * s + nrm[0] * 0.3, q0[1] + (q1[1] - q0[1]) * s + nrm[1] * 0.3) for s in (0, .25, .5, .75, 1)]
        alt_borda.append(max(T.z(*_mundo(fm, it, x, y)) - z for x, y in amostras))
    k_muro = max(range(4), key=lambda i: alt_borda[i])     # o muro fica na face de maior corte (02b: um muro)
    for k, (q0, q1, nrm) in enumerate(bordas, 1):
        h = alt_borda[k - 1]
        if h < 0.3:
            continue
        L = math.hypot(q1[0] - q0[0], q1[1] - q0[1])
        mx, my = (q0[0] + q1[0]) / 2, (q0[1] + q1[1]) / 2
        ang = math.degrees(math.atan2(q1[1] - q0[1], q1[0] - q0[0])) + fm["giro"]
        wx, wy = _mundo(fm, it, mx, my)
        p2 = W.add(f"IFCAXIS2PLACEMENT2D({W.add('IFCCARTESIANPOINT((0.,0.))')},$)")
        cima = W.add("IFCDIRECTION((0.,0.,1.))")
        if chave == "garagem" and muro_txt and k - 1 == k_muro:
            esp = 0.20
            perf = W.add(f"IFCRECTANGLEPROFILEDEF(.AREA.,$,{p2},{r_(L)},{r_(esp)})")
            sol = W.add(f"IFCEXTRUDEDAREASOLID({perf},{W.add(f'IFCAXIS2PLACEMENT3D({W.ponto(0, esp / 2, 0)},$,$)')},{cima},{r_(h)})")
            W.add(f"IFCSTYLEDITEM({sol},({estilo(COR_CONTENCAO)}),$)")
            rep = W.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({W.add(f'IFCSHAPEREPRESENTATION({corpo},{chr(39)}Body{chr(39)},{chr(39)}SweptSolid{chr(39)},({sol}))')}))")
            el = W.add(f"IFCWALL({W.guid('muro', chave, k)},{oh},{s_('Muro de contenção drenado · ' + chave)},$,"
                       f"'muro de contenção drenado',{_coloc(W, pl_site, wx, wy, z, ang)},{rep},{s_(f'{chave}-M{k}')},.SOLIDWALL.)")
            conf = (f"altura no modelo {h:.2f} m × até ≈ {hmax_fonte:g} m na 02b" + (" [CONFERIR]" if hmax_fonte and abs(h - hmax_fonte) > 0.5 else ""))
            W.pset(oh, "Physis_Contencao", [W.propriedade("Hospedeiro", chave), W.propriedade("Peca", muro_txt),
                                            W.propriedade("Altura", round(h, 2), "m"), W.propriedade("Fonte", fm_),
                                            W.propriedade("Conferencia", conf),
                                            W.propriedade("Espessura", "[MARCADOR] desenho 0,20 m")], [el], f"muro-{chave}-{k}")
            refs.append(el)
        elif tal_txt:
            # face do talude 1:1: placa inclinada de 0,30 m (gabião e vetiver, desenho), do pé (piso) ao topo (terreno)
            perf = W.add(f"IFCARBITRARYCLOSEDPROFILEDEF(.AREA.,$,{W.add('IFCPOLYLINE((' + ','.join(W.add(f'IFCCARTESIANPOINT(({r_(y)},{r_(zz)}))') for y, zz in ((0, 0), (h, h), (h + 0.3, h), (0.3, 0), (0, 0))) + '))')})")
            pos = W.add(f"IFCAXIS2PLACEMENT3D({W.ponto(-L / 2, 0, 0)},{W.add('IFCDIRECTION((1.,0.,0.))')},{W.add('IFCDIRECTION((0.,1.,0.))')})")
            sol = W.add(f"IFCEXTRUDEDAREASOLID({perf},{pos},{cima},{r_(L)})")
            W.add(f"IFCSTYLEDITEM({sol},({estilo(COR_TALUDE)}),$)")
            rep = W.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({W.add(f'IFCSHAPEREPRESENTATION({corpo},{chr(39)}Body{chr(39)},{chr(39)}SweptSolid{chr(39)},({sol}))')}))")
            el = W.add(f"IFCGEOGRAPHICELEMENT({W.guid('talude', chave, k)},{oh},{s_('Talude 1:1 · ' + chave)},$,"
                       f"'talude 1:1 com gabião e vetiver',{_coloc(W, pl_site, wx, wy, z, ang)},{rep},{s_(f'{chave}-T{k}')},.TERRAIN.)")
            W.pset(oh, "Physis_Contencao", [W.propriedade("Hospedeiro", chave), W.propriedade("Peca", tal_txt),
                                            W.propriedade("Altura", round(h, 2), "m"), W.propriedade("Fonte", ft),
                                            W.propriedade("Revestimento", "[MARCADOR] desenho 0,30 m")], [el], f"talude-{chave}-{k}")
            refs.append(el)
    return refs


def apoio_de(chave, fm, projeto):
    """Texto do apoio quando as fontes explicam por que a peça está acima do terreno; senão None."""
    if chave in EMPILHADOS:
        return f"sobre o contêiner de baixo ({EMPILHADOS[chave]}, 03 › Implantação)"
    if apoios(chave, fm, projeto) is not None:
        return "sobre pilares e blocos (20 › Fundações e 02b)"
    return None


def _estrutura(W, oh, corpo, estilo, pl_site, chave, e, fm, it, z, T, projeto):
    """Pilares (IfcColumn) e blocos (IfcFooting) da edificação até o terreno do Planejador."""
    reg = apoios(chave, fm, projeto)
    if not reg:
        return []
    pts, lado, fonte = reg
    afl = _fv(projeto, "estrutura.bloco_aflorando_m")[0] or 0.30
    pilar_txt = _fv(projeto, "estrutura.pilar")[0]
    refs = []
    for k, pt in enumerate(pts, 1):
        xl, yl = pt[0], pt[1]
        z_apoio = pt[2] if len(pt) > 2 else z
        wx, wy = _mundo(fm, it, xl, yl)
        zt = T.z(wx, wy)
        if z_apoio < zt:           # piso abaixo do terreno (plataforma cortada): apoio enterrado, não aparece
            continue
        topo = zt + afl
        p2 = W.add(f"IFCAXIS2PLACEMENT2D({W.add('IFCCARTESIANPOINT((0.,0.))')},$)")
        cima = W.add("IFCDIRECTION((0.,0.,1.))")
        sb = W.add(f"IFCEXTRUDEDAREASOLID({W.add(f'IFCRECTANGLEPROFILEDEF(.AREA.,$,{p2},{r_(lado)},{r_(lado)})')},"
                   f"{W.add(f'IFCAXIS2PLACEMENT3D({W.ponto(0, 0, 0)},$,$)')},{cima},0.6)")
        W.add(f"IFCSTYLEDITEM({sb},({estilo(COR_BLOCO)}),$)")
        rb = W.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({W.add(f'IFCSHAPEREPRESENTATION({corpo},{chr(39)}Body{chr(39)},{chr(39)}SweptSolid{chr(39)},({sb}))')}))")
        bloco = W.add(f"IFCFOOTING({W.guid('bloco', chave, k)},{oh},{s_(f'Bloco {k} · {chave}')},$,'bloco de concreto',"
                      f"{W.colocacao(pl_site, wx, wy, topo - 0.6)},{rb},{s_(f'{chave}-B{k}')},.PAD_FOOTING.)")
        refs.append(bloco)
        props = [W.propriedade("Hospedeiro", chave), W.propriedade("Peca", f"bloco {lado:g} × {lado:g} × 0,60 m, aflorando {afl:g} m"),
                 W.propriedade("Fonte", fonte), W.propriedade("Posicao", "distribuição regular pela regra escrita [CONFERIR]")]
        h = z_apoio - topo
        if h > 0.05:
            pp = W.add(f"IFCRECTANGLEHOLLOWPROFILEDEF(.AREA.,$,{p2},{r_(PILAR_M)},{r_(PILAR_M)},{r_(PAREDE_M)},$,$)")
            sp = W.add(f"IFCEXTRUDEDAREASOLID({pp},{W.add(f'IFCAXIS2PLACEMENT3D({W.ponto(0, 0, 0)},$,$)')},{cima},{r_(h)})")
            W.add(f"IFCSTYLEDITEM({sp},({estilo(COR_PILAR)}),$)")
            rp = W.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({W.add(f'IFCSHAPEREPRESENTATION({corpo},{chr(39)}Body{chr(39)},{chr(39)}SweptSolid{chr(39)},({sp}))')}))")
            pilar = W.add(f"IFCCOLUMN({W.guid('pilar', chave, k)},{oh},{s_(f'Pilar {k} · {chave}')},$,{s_('pilar ' + str(pilar_txt))},"
                          f"{W.colocacao(pl_site, wx, wy, topo)},{rp},{s_(f'{chave}-P{k}')},.COLUMN.)")
            refs.append(pilar)
            W.pset(oh, "Physis_Estrutura", [W.propriedade("Hospedeiro", chave), W.propriedade("Peca", f"pilar {pilar_txt} mm"),
                                            W.propriedade("Altura", round(h, 3), "m"), W.propriedade("Fonte", fonte),
                                            W.propriedade("Posicao", "distribuição regular pela regra escrita [CONFERIR]")],
                   [pilar], f"pilar-{chave}-{k}")
        W.pset(oh, "Physis_Estrutura", props, [bloco], f"bloco-{chave}-{k}")
    return refs


# ---------------------------------------------------------------- alturas e coberturas da prancha 02b (22/11)
# Decisões da dona: alturas da 02b onde a 03 se cala (pg:58d2e859f36a); coberturas da 02b por edificação, com os 14°
# da 03 › Solar como D7 [CONFERIR] (pg:74fabc0568d2). O acervo não traz código de cor: a cor fica a da entidade.
COR_NOTA = "[CONFERIR] o acervo não traz código de cor (só nomes); no modelo, cor da entidade da zona."


def _fv(projeto, cam):
    d = projeto["gemeo"]["fonte_por_valor"].get(cam)
    return (d["valor"], d["fonte"]) if d else (None, None)


def corpo_edificacao(chave, fm, projeto, h_pav, f_pav):
    """Paredes, cobertura e origem de cada edificação. `total` = altura no ponto mais alto da cobertura."""
    fv = lambda c: _fv(projeto, c)
    d = {"paredes": h_pav, "cob": None, "pct": 0.0, "origem": f_pav, "material": None,
         "cob_origem": "a 02b não dá a cobertura desta edificação: topo plano no modelo [MARCADOR]"}
    prof = fm["b"] if fm["tipo"] == "ret" else 0.0
    if chave.startswith("LF"):
        tot, ft = fv("alturas.total.lofts_m")
        pct, fp = fv("telhados.lofts_pct")
        if tot and pct:
            d.update(cob="agua", pct=pct, paredes=tot - prof * pct / 100, material="telha com isolamento (02b)",
                     origem=f"altura total {tot:g} m ({ft}) [CONFERIR: a tabela de cortes cita 5,00 e 3,00]",
                     cob_origem=f"água única {pct:g}% para o norte do loft ({fp})")
    elif chave == "bar" and fm["tipo"] == "circ":
        tot, ft = fv("alturas.total.restaurante_m")
        pct, fp = fv("telhados.restaurante_pct")
        if tot and pct:
            d.update(cob="cone", pct=pct, paredes=tot - fm["r"] * pct / 100, material="telha sanduíche (02b)",
                     origem=f"altura total {tot:g} m ({ft})", cob_origem=f"cônica {pct:g}% ({fp})")
    elif chave == "gourmet":
        tot, ft = fv("alturas.total.gourmet_m")
        tg, fg = fv("telhados.gourmet")
        if tot:
            d.update(paredes=tot, origem=f"altura {tot:g} m ({ft})", material="madeira e telha cerâmica (02b)",
                     cob_origem=f"{tg}: inclinação [MARCADOR], topo plano no modelo ({fg})")
    elif chave == "casa":
        hc, fc = fv("casa1.altura_conteiner_m")
        tc, ftc = fv("telhados.conteineres")
        if hc:
            d.update(paredes=hc, cob="plana", pct=3.0, material="contêiner metálico; manta no terraço (02b)",
                     origem=f"contêiner de baixo {hc:g} m ({fc}); andar de cima em L não modelado [MARCADOR]",
                     cob_origem=f"{tc} ({ftc})")
    elif chave in ("lab_up", "mec_up"):
        tc, ftc = fv("telhados.conteineres")
        if tc:
            d.update(cob="plana", pct=3.0, material="contêiner metálico; terraço-viveiro com manta (02b)",
                     cob_origem=f"{tc} ({ftc})")
    elif chave in ("lab", "mec"):
        d.update(material="contêiner metálico (02b)", cob_origem="sem cobertura: o contêiner de cima fica sobre ele")
    rise = (prof * d["pct"] / 100) if d["cob"] in ("agua", "plana") else (
        fm["r"] * d["pct"] / 100 if d["cob"] == "cone" else 0.0)
    d["total"] = d["paredes"] + rise
    return d


def relacao_terreno(e, z, z_terreno, apoiado=False):
    """Onde a peça fica em relação ao terreno do modelo (o do Planejador). `apoiado`: edificação com pilares e blocos
    das fontes (20 › Fundações e 02b). Só vira [CONFERIR] o que nenhuma fonte explica."""
    if e.get("piso_topo_m") is None:
        return "na cota do terreno (interpolada: a 03 não dá cota)"
    dz = z - z_terreno
    desc = str(e.get("descricao") or "").lower()
    intencional = (e.get("corte_m3") or 0) > 0 or "(enterrad" in desc or desc.startswith(("c3 (sob o", "fossa"))
    motivo = f"corte de {e['corte_m3']:g} m³ na 03" if (e.get("corte_m3") or 0) > 0 else "descrição da 03"
    if intencional and abs(dz) > 0.3:
        lado = "abaixo" if dz < 0 else "acima"
        return (f"{lado} do terreno do modelo {abs(dz):.1f} m: corte ou peça enterrada intencional ({motivo}); "
                "a diferença é do terreno aproximado")
    if dz < -0.3:
        return (f"abaixo do terreno aproximado {abs(dz):.1f} m sem corte na 03 [CONFERIR com a topografia: o terreno "
                "do modelo é aproximado]")
    if dz > 0.3:
        if apoiado:
            return f"acima do terreno {dz:.1f} m, {apoiado if isinstance(apoiado, str) else 'sobre pilares e blocos (20 › Fundações e 02b)'}"
        if (e.get("aterro_m3") or 0) > 0:
            return f"acima do terreno {dz:.1f} m sobre aterro ({e['aterro_m3']:g} m³ na 03)"
        pil = e.get("pilar_max_m")
        return f"acima do terreno {dz:.1f} m" + (f" (sobre pilares, máx. {pil:g} m na 03)" if pil else
                                                 " (aterro ou estrutura elevada [CONFERIR])")
    return "no nível do terreno aproximado"


def _cobertura(W, cp, fm, alt):
    if cp["cob"] in ("agua", "plana") and fm["tipo"] == "ret":
        t = cp["pct"] / 100
        return _prisma_x(W, fm["a"], [(-fm["b"] / 2, 0.0), (fm["b"] / 2, 0.0), (-fm["b"] / 2, fm["b"] * t)], alt)
    if cp["cob"] == "cone" and fm["tipo"] == "circ":
        r, h, n = fm["r"], fm["r"] * cp["pct"] / 100, 24
        pts = [(0.0, 0.0, alt + h), (0.0, 0.0, alt)] + [
            (r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), alt) for k in range(n)]
        lista = W.add("IFCCARTESIANPOINTLIST3D((" + ",".join(f"({r_(x)},{r_(y)},{r_(z)})" for x, y, z in pts) + "))")
        faces = [(1, 3 + k, 3 + (k + 1) % n) for k in range(n)] + [(2, 3 + (k + 1) % n, 3 + k) for k in range(n)]
        return W.add(f"IFCTRIANGULATEDFACESET({lista},$,.T.,(" + ",".join(f"({a},{b},{c})" for a, b, c in faces) + "),$)")
    return None


def _placas(W, cp, fm, alt, area, incl):
    """Placas sobre a cobertura: nas planas, inclinadas a `incl` (limite inferior da faixa 15–20° da 02b) voltadas ao
    norte; na água única, paralelas ao telhado; no cone, na face norte."""
    if fm["tipo"] == "circ":
        r = fm["r"]
        th = math.atan(cp["pct"] / 100) if cp["cob"] == "cone" else 0.0
        h = r * cp["pct"] / 100 if cp["cob"] == "cone" else 0.0
        w = min(math.sqrt(area), r * 1.2)
        dp = min(r * 0.85, area * math.cos(th) / w)
        zc = lambda y: alt + h * (1 - y / r)
        y1, y2 = 0.15, 0.15 + dp
        pl = _prisma_x(W, w, [(y1, zc(y1) + 0.03), (y2, zc(y2) + 0.03), (y2, zc(y2) + 0.08), (y1, zc(y1) + 0.08)])
        return pl, f"face norte da cobertura cônica; {area:.1f} m² de placas [CONFERIR]"
    a, b = fm["a"] * 0.9, fm["b"]
    if cp["cob"] == "agua":
        t = cp["pct"] / 100
        dp = min(b * 0.9, area * math.cos(math.atan(t)) / a)
        zt = lambda y: alt + (b / 2 - y) * t
        y1, y2 = -dp / 2, dp / 2
        pl = _prisma_x(W, a, [(y1, zt(y1) + 0.03), (y2, zt(y2) + 0.03), (y2, zt(y2) + 0.08), (y1, zt(y1) + 0.08)])
        return pl, "paralelas à água única do loft; posição real no projeto [CONFERIR]"
    t_cob = cp["pct"] / 100
    ti = math.tan(math.radians(incl or 0))
    dp = min(b * 0.9, area * math.cos(math.radians(incl or 0)) / a)
    y1, y2 = -dp / 2, dp / 2
    zr = lambda y: alt + (b / 2 - y) * t_cob + 0.15
    zp = lambda y: zr(y2) + (y2 - y) * ti
    pl = _prisma_x(W, a, [(y1, zp(y1)), (y2, zp(y2)), (y2, zp(y2) + 0.05), (y1, zp(y1) + 0.05)])
    return pl, (f"inclinadas a {incl:g}° para o norte sobre a cobertura (faixa 15–20° da 02b; desenho no limite "
                "inferior) [CONFERIR]")


def escrever(projeto, agora=0, altura=None):
    """Texto STEP do IFC4. `agora` fixo por padrão para o arquivo ser reprodutível (mesma semente, mesmo IFC).
    `altura` = (m, fonte) para versões sem LAB/MEC empilhados (o comparador passa a da rev0)."""
    if G.validar(projeto):
        raise SementeIncompleta("semente inválida: " + "; ".join(G.validar(projeto)[:3]))
    g = projeto["gemeo"]
    els = g["elementos"]
    itens = {i["id"]: i for i in projeto["itens"]}
    h_pav, f_pav = altura or altura_pavimento(els)
    T = terreno_planejador(projeto)
    v, tri = malha_terreno(projeto, T)
    fvs = g["fonte_por_valor"]
    inc = (fvs.get("telhados.inclinacao_graus") or {}).get("valor")
    inc_fonte = (fvs.get("telhados.inclinacao_graus") or {}).get("fonte")
    pv_kwp = (fvs.get("energia.fv.placa_kwp") or {}).get("valor")
    pv_area = (fvs.get("energia.fv.placa_area_m2") or {}).get("valor")
    placas = placas_por_elemento(projeto) if pv_kwp and pv_area else {}
    incl_txt = (fvs.get("energia.fv.placa_inclinacao") or {}).get("valor")
    pv_incl = float(re.match(r"(\d+)", incl_txt).group(1)) if incl_txt else 0.0
    W = Escritor("gemeo-" + g["semente"])

    pe = W.add("IFCPERSON($,$,'Physis',$,$,$,$,$)")
    org = W.add("IFCORGANIZATION($,'Physis Engineering',$,$,$)")
    po = W.add(f"IFCPERSONANDORGANIZATION({pe},{org},$)")
    app = W.add(f"IFCAPPLICATION({org},'0.1','Physis Gêmeo digital','physis-gemeo')")
    oh = W.add(f"IFCOWNERHISTORY({po},{app},$,.ADDED.,$,$,$,{int(agora)})")
    origem = W.add(f"IFCAXIS2PLACEMENT3D({W.ponto(0, 0, 0)},$,$)")
    nv = (g["fonte_por_valor"].get("lote.norte_verdadeiro_graus") or {}).get("valor")
    if nv is not None:   # norte verdadeiro em coordenadas locais (o y local é o norte de projeto) [CONFERIR]
        norte = W.add(f"IFCDIRECTION(({r_(-math.sin(math.radians(nv)))},{r_(math.cos(math.radians(nv)))}))")
    else:
        norte = W.add("IFCDIRECTION((0.,1.))")
    ctx = W.add(f"IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,{origem},{norte})")
    corpo = W.add(f"IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,{ctx},$,.MODEL_VIEW.,$)")
    ua = W.add(f"IFCUNITASSIGNMENT(({','.join(W.unidade(u) for u in ('m', 'm²', 'm³'))}))")
    aviso = f"ESTUDO PRELIMINAR (revisão 0) · TESTE · semente {g['semente']} · sem georreferência (L-01)"
    projeto_ifc = W.add(f"IFCPROJECT({W.guid('projeto')},{oh},{s_('Casa Physis · Lote 168 · gêmeo digital')},"
                        f"{s_(aviso)},$,$,'estudo preliminar',({ctx}),{ua})")

    estilos = {}

    def estilo(cor):
        if cor not in estilos:
            r, gg, b = _rgb(cor)
            c = W.add(f"IFCCOLOURRGB($,{r_(r)},{r_(gg)},{r_(b)})")
            sh = W.add(f"IFCSURFACESTYLESHADING({c},$)")
            estilos[cor] = W.add(f"IFCSURFACESTYLE({s_(cor)},.BOTH.,({sh}))")
        return estilos[cor]

    # sítio com a superfície do terreno
    pl_site = W.colocacao(None)
    lista = W.add("IFCCARTESIANPOINTLIST3D((" + ",".join(f"({r_(x)},{r_(y)},{r_(z)})" for x, y, z in v) + "))")
    fs = W.add(f"IFCTRIANGULATEDFACESET({lista},$,.T.,(" + ",".join(f"({i + 1},{j + 1},{k + 1})" for i, j, k in tri) + "),$)")
    W.add(f"IFCSTYLEDITEM({fs},({estilo(COR_TERRENO)}),$)")
    sr = W.add(f"IFCSHAPEREPRESENTATION({corpo},'Body','Tessellation',({fs}))")
    rep_site = W.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({sr}))")
    def _dms(v):
        if v is None:
            return "$"
        sg, a_ = (-1 if v < 0 else 1), abs(v)
        gr = int(a_); mi = int((a_ - gr) * 60); se = int((a_ - gr - mi / 60) * 3600)
        mic = int(round(((a_ - gr - mi / 60) * 3600 - se) * 1e6))
        return f"({sg * gr},{sg * mi},{sg * se},{sg * mic})"
    lat_s = (g["fonte_por_valor"].get("lote.latitude") or {}).get("valor")
    lon_s = (g["fonte_por_valor"].get("lote.longitude") or {}).get("valor")
    sitio = W.add(f"IFCSITE({W.guid('site')},{oh},'Lote 168',{s_('terreno pela grade do Planejador; lat/long do levantamento (grade UTM SAD-69 lida na imagem) [CONFERIR]')},"
                  f"$,{pl_site},{rep_site},$,.ELEMENT.,{_dms(lat_s)},{_dms(lon_s)},$,$,$)")
    W.add(f"IFCRELAGGREGATES({W.guid('agg-proj')},{oh},$,$,{projeto_ifc},({sitio}))")

    refs, por_zona, ref_por_chave = [], {z: [] for z in G.ZONAS}, {}
    estado = g["estado_de_vida"]
    for chave, e in els.items():
        it = itens[e["item_id"]]
        if e["piso_topo_m"] is not None:
            z, z_orig = e["piso_topo_m"], "03 › Implantação (piso / topo)"
        else:
            z, z_orig = round(T.z(it["x"], it["y"]), 3), "cota do terreno interpolada (a 03 não traz)"
        fm = forma(e, it)
        if eh_edificacao(chave) and not e["sem_area"]:
            cp = corpo_edificacao(chave, fm, projeto, h_pav, f_pav)
        else:
            cp = {"paredes": ESPESSURA_DESENHO_M, "total": ESPESSURA_DESENHO_M, "cob": None, "pct": 0.0,
                  "origem": "placa de desenho de 0,20 m (não é dado de projeto)", "cob_origem": "sem cobertura",
                  "material": None}
        alt = cp["paredes"]
        rel = relacao_terreno(e, z, T.z(it["x"], it["y"]),
                              apoiado=None if e["sem_area"] else apoio_de(chave, fm, projeto))
        pl = _coloc(W, pl_site, it["x"], it["y"], z, fm["giro"])
        rep = "$"
        if not e["sem_area"]:
            p2 = W.add(f"IFCAXIS2PLACEMENT2D({W.add('IFCCARTESIANPOINT((0.,0.))')},$)")
            if fm["tipo"] == "circ":
                perfil = W.add(f"IFCCIRCLEPROFILEDEF(.AREA.,$,{p2},{r_(fm['r'])})")
            else:
                perfil = W.add(f"IFCRECTANGLEPROFILEDEF(.AREA.,$,{p2},{r_(fm['a'])},{r_(fm['b'])})")
            pos = W.add(f"IFCAXIS2PLACEMENT3D({W.ponto(0, 0, 0)},$,$)")
            cima = W.add("IFCDIRECTION((0.,0.,1.))")
            solido = W.add(f"IFCEXTRUDEDAREASOLID({perfil},{pos},{cima},{r_(alt)})")
            W.add(f"IFCSTYLEDITEM({solido},({estilo(COR_ENTIDADE[e['zona']])}),$)")
            itens_rep = [solido]
            if not eh_edificacao(chave) and (e.get("aterro_m3") or 0) > 0:  # plataforma de aterro até o terreno (03)
                zmin = min(T.z(*p) for p in _pontos_planta(fm, it))
                if z - zmin > 0.05:
                    pos_a = W.add(f"IFCAXIS2PLACEMENT3D({W.ponto(0, 0, zmin - z)},$,$)")
                    ater = W.add(f"IFCEXTRUDEDAREASOLID({perfil},{pos_a},{cima},{r_(z - zmin)})")
                    W.add(f"IFCSTYLEDITEM({ater},({estilo(COR_TERRENO)}),$)")
                    itens_rep.append(ater)
                    rel += "; aterro desenhado até o terreno"
            tel = _cobertura(W, cp, fm, alt)
            if tel:
                W.add(f"IFCSTYLEDITEM({tel},({estilo(COR_TELHADO)}),$)")
                itens_rep.append(tel)
            sr = W.add(f"IFCSHAPEREPRESENTATION({corpo},'Body','SweptSolid',({','.join(itens_rep)}))")
            rep = W.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({sr}))")
            if chave in placas:
                n, fontes = placas[chave]
                area = n * pv_area
                pl_item, disp = _placas(W, cp, fm, alt, area, pv_incl)
                W.add(f"IFCSTYLEDITEM({pl_item},({estilo(COR_PLACA)}),$)")
                srp = W.add(f"IFCSHAPEREPRESENTATION({corpo},'Body','SweptSolid',({pl_item}))")
                rpp = W.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({srp}))")
                plp = _coloc(W, pl_site, it["x"], it["y"], z, fm["giro"])
                nome_pv = s_("Placas solares · " + it["nome"][:80])
                pv_ref = W.add(f"IFCSOLARDEVICE({W.guid('pv', chave)},{oh},{nome_pv},$,"
                               f"'Placas fotovoltaicas',{plp},{rpp},{s_('pv-' + chave)},.SOLARPANEL.)")
                refs.append(pv_ref)
                por_zona[e["zona"]].append(pv_ref)
                W.pset(oh, "Physis_Solar", [
                    W.propriedade("Placas", n), W.propriedade("Potencia", round(n * pv_kwp, 3), "kWp"),
                    W.propriedade("AreaPlacas", round(area, 2), "m²"), W.propriedade("Fonte", "; ".join(sorted(set(fontes)))),
                    W.propriedade("Disposicao", disp)], [pv_ref], "pv-" + chave)
        ref = W.add(f"IFCBUILDINGELEMENTPROXY({W.guid('el', chave)},{oh},{s_(it['nome'][:120])},"
                    f"{s_((e.get('descricao') or '')[:255]) if e.get('descricao') else '$'},{s_(it['tipo'])},{pl},{rep},"
                    f"{s_(chave)},.USERDEFINED.)")
        refs.append(ref)
        por_zona[e["zona"]].append(ref)
        ref_por_chave[chave] = ref
        if not e["sem_area"]:
            for est in (_estrutura(W, oh, corpo, estilo, pl_site, chave, e, fm, it, z, T, projeto)
                        + _vigas_e_contraventos(W, oh, corpo, estilo, pl_site, chave, e, fm, it, z, T, projeto)
                        + _contencao(W, oh, corpo, estilo, pl_site, chave, e, fm, it, z, T, projeto)):
                refs.append(est)
                por_zona[e["zona"]].append(est)
        props = [W.propriedade("Chave", chave), W.propriedade("Zona", e["zona"]), W.propriedade("Entidade", e["entidade"]),
                 W.propriedade("Fonte", e["fonte"]), W.propriedade("Procedencia", e["procedencia"]),
                 W.propriedade("EstadoDeVida", estado["por_elemento"].get(chave, estado["padrao"])),
                 W.propriedade("AreaPlanilha", e["area_m2"], "m²"), W.propriedade("Cota", z, "m"),
                 W.propriedade("CotaOrigem", z_orig), W.propriedade("AlturaModelo", round(cp["total"], 3), "m"),
                 W.propriedade("AlturaOrigem", cp["origem"]), W.propriedade("SemArea", bool(e["sem_area"])),
                 W.propriedade("Forma", fm["origem"]), W.propriedade("Telhado", cp["cob_origem"]),
                 W.propriedade("RelacaoTerreno", rel)]
        W.pset(oh, "Physis_Gemeo", props, [ref], chave)
        if eh_edificacao(chave):
            W.pset(oh, "Physis_Material", [
                W.propriedade("Cobertura", cp["cob_origem"]), W.propriedade("Material", cp["material"] or "[MARCADOR]"),
                W.propriedade("Cor", COR_NOTA + (" Andar de cima da Casa 1: contêineres laranja e azul (doc 10, 01, 09b), "
                                                 "não modelado." if chave == "casa" else ""))], [ref], "mat-" + chave)
    for ref_h, zona_h in _hidraulica(W, oh, corpo, estilo, pl_site, projeto, T, ref_por_chave):
        refs.append(ref_h)
        por_zona[zona_h].append(ref_h)
    if "_sem_lugar" in placas:  # placas sem elemento com área na 03 (D3): entram sem geometria, para somar 56
        n, fontes = placas["_sem_lugar"]
        pv_ref = W.add(f"IFCSOLARDEVICE({W.guid('pv', '_sem_lugar')},{oh},'Placas solares sem lugar no modelo',"
                       f"{s_('loft sem área na 03 (divergência D3) [CONFERIR]')},'Placas fotovoltaicas',"
                       f"{W.colocacao(pl_site)},$,'pv-sem-lugar',.SOLARPANEL.)")
        refs.append(pv_ref)
        W.pset(oh, "Physis_Solar", [W.propriedade("Placas", n), W.propriedade("Potencia", round(n * pv_kwp, 3), "kWp"),
                                    W.propriedade("Fonte", "; ".join(sorted(set(fontes))))], [pv_ref], "pv-sem-lugar")
    W.add(f"IFCRELCONTAINEDINSPATIALSTRUCTURE({W.guid('cont-site')},{oh},$,$,({','.join(refs)}),{sitio})")
    for z, rs in por_zona.items():
        info = G.ZONAS[z]
        zona = W.add(f"IFCZONE({W.guid('zona', z)},{oh},{s_(info['nome'] + ' · ' + info['entidade'])},$,{s_(z)},$)")
        W.add(f"IFCRELASSIGNSTOGROUP({W.guid('grupo', z)},{oh},$,$,({','.join(rs)}),$,{zona})")

    cab = ["ISO-10303-21;", "HEADER;", "FILE_DESCRIPTION(('ViewDefinition [ReferenceView_V1.2]'),'2;1');",
           f"FILE_NAME({s_(g['semente'] + '.ifc')},'2026-11-21T00:00:00',('Physis'),('Physis Engineering'),"
           "'Physis Gemeo 0.1','Physis Sistema','estudo preliminar');",
           "FILE_SCHEMA(('IFC4'));", "ENDSEC;", "DATA;"]
    return "\n".join(cab + [f"#{i + 1}={x};" for i, x in enumerate(W.linhas)] + ["ENDSEC;", "END-ISO-10303-21;", ""])


def main(argv=None):
    ap = argparse.ArgumentParser(description="Semente do gêmeo (Planejador) → IFC4 do lote")
    ap.add_argument("--semente", default=str(SEMENTE_PADRAO))
    ap.add_argument("--saida", default=None)
    a = ap.parse_args(argv)
    txt = escrever(G.carregar(a.semente))
    sys.stdout.reconfigure(encoding="utf-8")
    saida = Path(a.saida) if a.saida else Path(a.semente).with_suffix(".ifc")
    saida.write_text(txt, encoding="utf-8", newline="\n")
    print("gravado em", saida, f"({len(txt.encode('utf-8')) // 1024} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
