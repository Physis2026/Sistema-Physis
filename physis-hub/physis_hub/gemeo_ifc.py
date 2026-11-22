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

Altura das massas (decisão da dona em 21/11/2026, M&A pg:16228b14d400): edificações do 20 › Quadro de áreas com a
altura de pavimento que a própria 03 dá (LAB e MEC de cima − de baixo = 2,90 m); o resto é placa de 0,20 m só de
desenho. Tudo [CONFERIR] até o projeto executivo. Elementos sem cota na 03 ficam na cota do terreno interpolada.
Elementos sem área na 03 (0,01 m) entram sem geometria, para a contagem bater.
"""
from __future__ import annotations

import argparse
import json
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


def escrever(projeto, agora=0):
    """Texto STEP do IFC4. `agora` fixo por padrão para o arquivo ser reprodutível (mesma semente, mesmo IFC)."""
    if G.validar(projeto):
        raise SementeIncompleta("semente inválida: " + "; ".join(G.validar(projeto)[:3]))
    g = projeto["gemeo"]
    els = g["elementos"]
    itens = {i["id"]: i for i in projeto["itens"]}
    h_pav, f_pav = altura_pavimento(els)
    v, tri = malha_terreno(projeto)
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
        if chave in EDIFICACOES:
            alt, alt_orig = h_pav, f_pav
        else:
            alt, alt_orig = ESPESSURA_DESENHO_M, "placa de desenho de 0,20 m (não é dado de projeto)"
        pl = W.colocacao(pl_site, it["x"], it["y"], z)
        rep = "$"
        if not e["sem_area"]:
            p2 = W.add(f"IFCAXIS2PLACEMENT2D({W.add('IFCCARTESIANPOINT((0.,0.))')},$)")
            perfil = W.add(f"IFCRECTANGLEPROFILEDEF(.AREA.,$,{p2},{r_(it['w'])},{r_(it['d'])})")
            pos = W.add(f"IFCAXIS2PLACEMENT3D({W.ponto(0, 0, 0)},$,$)")
            cima = W.add("IFCDIRECTION((0.,0.,1.))")
            solido = W.add(f"IFCEXTRUDEDAREASOLID({perfil},{pos},{cima},{r_(alt)})")
            W.add(f"IFCSTYLEDITEM({solido},({estilo(COR_ENTIDADE[e['zona']])}),$)")
            sr = W.add(f"IFCSHAPEREPRESENTATION({corpo},'Body','SweptSolid',({solido}))")
            rep = W.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({sr}))")
        ref = W.add(f"IFCBUILDINGELEMENTPROXY({W.guid('el', chave)},{oh},{s_(it['nome'][:120])},"
                    f"{s_((e.get('descricao') or '')[:255]) if e.get('descricao') else '$'},{s_(it['tipo'])},{pl},{rep},"
                    f"{s_(chave)},.USERDEFINED.)")
        refs.append(ref)
        por_zona[e["zona"]].append(ref)
        props = [W.propriedade("Chave", chave), W.propriedade("Zona", e["zona"]), W.propriedade("Entidade", e["entidade"]),
                 W.propriedade("Fonte", e["fonte"]), W.propriedade("Procedencia", e["procedencia"]),
                 W.propriedade("EstadoDeVida", estado["por_elemento"].get(chave, estado["padrao"])),
                 W.propriedade("AreaPlanilha", e["area_m2"], "m²"), W.propriedade("Cota", z, "m"),
                 W.propriedade("CotaOrigem", z_orig), W.propriedade("AlturaModelo", alt, "m"),
                 W.propriedade("AlturaOrigem", alt_orig), W.propriedade("SemArea", bool(e["sem_area"]))]
        W.pset(oh, "Physis_Gemeo", props, [ref], chave)
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
