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
    desc, w, d = str(e.get("descricao") or ""), it["w"], it["d"]
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
                return {"tipo": "ret", "a": a, "b": b, "giro": math.degrees(t),
                        "origem": f"{md.group(0)} m girado {g.group(1)}° (descrição da 03; reproduz a caixa "
                                  f"{w} × {d}); sentido do giro [CONFERIR]"}
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

def malha_terreno(projeto):
    """Triângulos entre os lados x≈0 e x≈22 do lote, pelos pontos com cota da semente (curvas + vértices)."""
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


def relacao_terreno(e, z, z_terreno):
    """Onde a peça fica em relação ao terreno aproximado (pedido da sessão de renderização, 22/11)."""
    if e.get("piso_topo_m") is None:
        return "na cota do terreno (interpolada: a 03 não dá cota)"
    dz = z - z_terreno
    desc = str(e.get("descricao") or "").lower()
    if dz < -0.3:
        if (e.get("corte_m3") or 0) > 0 or "(enterrad" in desc or desc.startswith(("c3 (sob o", "fossa")):
            motivo = f"corte de {e['corte_m3']:g} m³ na 03" if (e.get("corte_m3") or 0) > 0 else "descrição da 03"
            return f"abaixo do terreno {abs(dz):.1f} m: corte ou peça enterrada intencional ({motivo})"
        return (f"abaixo do terreno aproximado {abs(dz):.1f} m sem corte na 03 [CONFERIR com a topografia: o terreno "
                "do modelo é aproximado pelas curvas]")
    if dz > 0.3:
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
    v, tri = malha_terreno(projeto)
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
    sitio = W.add(f"IFCSITE({W.guid('site')},{oh},'Lote 168',{s_('terreno aproximado pelas curvas de nível da 03 e cotas da 20')},"
                  f"$,{pl_site},{rep_site},$,.ELEMENT.,$,$,$,$,$)")
    W.add(f"IFCRELAGGREGATES({W.guid('agg-proj')},{oh},$,$,{projeto_ifc},({sitio}))")

    refs, por_zona = [], {z: [] for z in G.ZONAS}
    estado = g["estado_de_vida"]
    for chave, e in els.items():
        it = itens[e["item_id"]]
        if e["piso_topo_m"] is not None:
            z, z_orig = e["piso_topo_m"], "03 › Implantação (piso / topo)"
        else:
            z, z_orig = round(cota_no_terreno(v, tri, it["x"], it["y"]), 3), "cota do terreno interpolada (a 03 não traz)"
        fm = forma(e, it)
        if chave in EDIFICACOES and not e["sem_area"]:
            cp = corpo_edificacao(chave, fm, projeto, h_pav, f_pav)
        else:
            cp = {"paredes": ESPESSURA_DESENHO_M, "total": ESPESSURA_DESENHO_M, "cob": None, "pct": 0.0,
                  "origem": "placa de desenho de 0,20 m (não é dado de projeto)", "cob_origem": "sem cobertura",
                  "material": None}
        alt = cp["paredes"]
        rel = relacao_terreno(e, z, cota_no_terreno(v, tri, it["x"], it["y"]))
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
                pv_ref = W.add(f"IFCSOLARDEVICE({W.guid('pv', chave)},{oh},{s_(f'Placas solares · {it['nome'][:80]}')},$,"
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
        props = [W.propriedade("Chave", chave), W.propriedade("Zona", e["zona"]), W.propriedade("Entidade", e["entidade"]),
                 W.propriedade("Fonte", e["fonte"]), W.propriedade("Procedencia", e["procedencia"]),
                 W.propriedade("EstadoDeVida", estado["por_elemento"].get(chave, estado["padrao"])),
                 W.propriedade("AreaPlanilha", e["area_m2"], "m²"), W.propriedade("Cota", z, "m"),
                 W.propriedade("CotaOrigem", z_orig), W.propriedade("AlturaModelo", round(cp["total"], 3), "m"),
                 W.propriedade("AlturaOrigem", cp["origem"]), W.propriedade("SemArea", bool(e["sem_area"])),
                 W.propriedade("Forma", fm["origem"]), W.propriedade("Telhado", cp["cob_origem"]),
                 W.propriedade("RelacaoTerreno", rel)]
        W.pset(oh, "Physis_Gemeo", props, [ref], chave)
        if chave in EDIFICACOES:
            W.pset(oh, "Physis_Material", [
                W.propriedade("Cobertura", cp["cob_origem"]), W.propriedade("Material", cp["material"] or "[MARCADOR]"),
                W.propriedade("Cor", COR_NOTA + (" Andar de cima da Casa 1: contêineres laranja e azul (doc 10, 01, 09b), "
                                                 "não modelado." if chave == "casa" else ""))], [ref], "mat-" + chave)
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
