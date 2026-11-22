"""Gêmeo digital · importador das planilhas da Casa Physis → projeto do Planejador (versão de TESTE, G0–G1).

    python -m physis_hub.gemeo_importar [--editaveis PASTA] [--saida ARQUIVO.json]

Fontes (decisão R1-1 da dona, 21/11/2026):
- planilha 20 (`20_Detalhamento_Estimado.xlsx`) = fonte única dos números de sistemas;
- planilha 03 (`03_Planilha_Tecnica.xlsx`, abas Implantação e Levantamento) = geometria;
- divergências antigas do acervo (D1–D6, doc 47 §2.4) ficam marcadas `[CONFERIR]` no próprio valor, com o valor
  alternativo e a fonte. A planilha 18 só é lida para citar o valor alternativo de D5.

Saída: projeto `physis.terreno/1.0` do Planejador (itens[], sistemas{}, prov, terreno, clima) com o campo `gemeo`
(revisão, fonte por valor, estado de vida, elementos por zona e entidade). O Planejador abre o arquivo como está
("Abrir projeto"); nada nele foi mudado (regra 2).

Nada é inventado: se a planilha mudar de forma e um rótulo esperado sumir, o importador para com erro em vez de
preencher. Sem dependências (Python 3.10): o .xlsx é lido com zipfile + xml.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from . import gemeo as G
from .gemeo import LOTE, valor

SEMENTE = "casa-physis-rev0"
REVISAO = "rev0"
ARQ_20 = "20_Detalhamento_Estimado.xlsx"
ARQ_03 = "03_Planilha_Tecnica.xlsx"
ARQ_18 = "18_Equipamentos_e_Consumo.xlsx"
PASTA_PADRAO = Path(os.environ.get("PHYSIS_CASA_EDITAVEIS") or (
    Path.home() / "OneDrive - Physis Engineering" / "Documents" / "Casa Physis" / "1_Tecnico_Casa_Physis" / "Editaveis"))
SEMENTE_ARQ = Path(__file__).resolve().parents[2] / "modulos" / "planejador" / "gemeo" / f"{SEMENTE}.json"

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
_NUM = re.compile(r"-?\d+(?:\.\d{3})*(?:,\d+)?")


class FonteAusente(ValueError):
    """Um rótulo ou célula esperada não está na planilha: a semente não é gerada."""


# ---------------------------------------------------------------- leitura de .xlsx (só biblioteca padrão)

def ler_xlsx(caminho):
    """{aba: {linha: {coluna: valor}}}. Número → float; texto → str."""
    z = zipfile.ZipFile(caminho)
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
            ss.append("".join(t.text or "" for t in si.iter("{%s}t" % _NS["m"])))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    alvo = {r.get("Id"): r.get("Target") for r in rels}
    abas = {}
    for s in wb.find("m:sheets", _NS):
        arq = alvo[s.get("{%s}id" % _NS["r"])].lstrip("/")
        arq = arq if arq.startswith("xl/") else "xl/" + arq
        linhas = {}
        for row in ET.fromstring(z.read(arq)).iter("{%s}row" % _NS["m"]):
            vals = {}
            for c in row.findall("m:c", _NS):
                col = re.match(r"[A-Z]+", c.get("r")).group(0)
                v, t = c.find("m:v", _NS), c.get("t")
                if t == "s" and v is not None:
                    vals[col] = ss[int(v.text)]
                elif t == "inlineStr":
                    vals[col] = "".join(x.text or "" for x in c.iter("{%s}t" % _NS["m"]))
                elif t in ("str", "e") and v is not None:
                    vals[col] = v.text
                elif t == "b" and v is not None:
                    vals[col] = v.text == "1"
                elif v is not None and v.text is not None:
                    vals[col] = float(v.text)
            if vals:
                linhas[int(row.get("r"))] = vals
        abas[s.get("name")] = linhas
    return abas


def numeros_br(s):
    """Números de um texto em pt-BR ('1.455,95 m²' → [1455.95]; '+18 (56)' → [18, 56])."""
    if isinstance(s, bool) or s is None:
        return []
    if isinstance(s, (int, float)):
        return [float(s)]
    return [float(m.replace(".", "").replace(",", ".")) for m in _NUM.findall(str(s))]


def num_br(s):
    n = numeros_br(s)
    if not n:
        raise FonteAusente(f"sem número em {s!r}")
    return n[0]


def sha256(caminho):
    return hashlib.sha256(Path(caminho).read_bytes()).hexdigest()


class Planilha:
    """Uma planilha com endereço legível para cada célula lida (vira a `fonte` do valor)."""

    def __init__(self, sigla, caminho):
        self.sigla, self.caminho = sigla, Path(caminho)
        self.abas = ler_xlsx(self.caminho)

    def aba(self, nome):
        if nome not in self.abas:
            raise FonteAusente(f"planilha {self.sigla}: aba {nome!r} não existe")
        return self.abas[nome]

    def fonte(self, aba, linha, col=None):
        return f"planilha {self.sigla} › {aba}, linha {linha}" + (f", col. {col}" if col else "")

    def linha(self, aba, rotulo, col="A"):
        """(nº da linha, valores) da primeira linha cuja coluna `col` começa com `rotulo`."""
        for n, v in sorted(self.aba(aba).items()):
            if str(v.get(col, "")).strip().startswith(rotulo):
                return n, v
        raise FonteAusente(f"planilha {self.sigla} › {aba}: rótulo {rotulo!r} não encontrado")

    def celula(self, aba, rotulo, col, rot_col="A"):
        """(valor bruto, fonte) da coluna `col` na linha do `rotulo`."""
        n, v = self.linha(aba, rotulo, rot_col)
        if col not in v:
            raise FonteAusente(f"planilha {self.sigla} › {aba}, linha {n}: coluna {col} vazia")
        return v[col], self.fonte(aba, n, col)


def _conferir(div, *alternativas):
    return {"divergencia": div, "alternativas": [{"valor": a, "fonte": f} for a, f in alternativas]}


# ---------------------------------------------------------------- G0/G1 · elementos da 03 › Implantação

# Classificação de desenho para o Planejador (só define a cor e a categoria do item no mapa; nenhum número).
# A revisar na G2 (vista). Ordem importa: o primeiro prefixo que casa vale.
TIPO_PLANEJADOR = [
    ("casa", "residencia"), ("LF", "hospedagem"), ("var", "deck"),
    ("lab", "escritorio"), ("mec", "deposito"), ("apoio", "deposito"), ("bar", "restaurante"),
    ("gourmet", "edicula"), ("staff", "edicula"), ("lavabos", "edicula"), ("loja", "escritorio"),
    ("pet", "deposito"), ("coelhos", "deposito"), ("aves", "deposito"), ("cabritos", "deposito"),
    ("cogu", "deposito"), ("residuos", "deposito"), ("abelhas", "horta"),
    ("piscina", "piscina"), ("peixes", "piscina"), ("lago", "piscina"), ("minilago", "piscina"),
    ("cist", "cisterna"), ("biodig", "biodigestor"), ("fossa", "tratamento"), ("filtr", "tratamento"),
    ("chuva", "infiltracao"), ("horta", "horta"), ("pomar", "horta"), ("viveiro", "horta"),
    ("flor", "mata"), ("jardim", "gramado"),
    ("vagas", "estacionamento"), ("garagem", "estacionamento"),
    ("deck", "deck"), ("comum", "deck"), ("t3", "deck"), ("patio", "deck"), ("lazer", "deck"),
]


# Prancha 02b (02b_Pranchas_Tecnicas_A3.pdf, idêntico em Documents e na cópia de Downloads, conferido por sha256 em
# 22/11/2026). Valores copiados como estão escritos; TEXTOS_02B são os trechos que o teste procura no PDF.
F02B_SOMBRAS = "02b_Pranchas_Tecnicas_A3.pdf › estudo de sombras (\"Alturas: casa, LAB e MEC 5,8 m; lofts 5,0 m; restaurante 4,0 m; gourmet 3,2 m\")"
F02B_CORTES = "02b_Pranchas_Tecnicas_A3.pdf › Cortes arquitetônicos das edificações (1:100)"
F02B_PLACAS = "02b_Pranchas_Tecnicas_A3.pdf › energia (\"Placas de 550 W (≈ 1,13 × 2,28 m) a 15–20°\")"
TEXTOS_02B = ["Alturas: casa, LAB e MEC 5,8 m; lofts 5,0 m; restaurante 4,0 m; gourmet 3,2 m",
              "cobertura 3% + placas a 15–20°", "água única 15%, telha com isolamento", "cônica 45%, rufos e calha periférica",
              "telhado de madeira com telha cerâmica", "+2,59", "+5,18", "a 15–20°",
              "pilar tubular 100 × 100 × 4,75", "bloco 0,70 × 0,70 × 0,60", "tracejado 0,60 × 0,60",
              "A1 a A15: apoios nos cantos e no meio dos contêineres de 40 pés, sobre blocos de concreto aflorando 30 cm",
              "pilares na grade de 4 m", "contêineres em T sobre 8 pilares",
              "C0 a C8: pilares da cozinha (centro e anel a cada 45°); D1 a D10: pilares dos decks",
              "P1 a P4: cantos do contêiner inferior; P5 a P8: extremidades do contêiner de cima, além do inferior (balanços de 1,81 m) · vigas W 150",
              "de borda W 150 × 13 e viga central W 200 × 15 (vão de 4 m; ver documento 20) · contraventamento em X (prancha 36)",
              "vigas radiais e anel em W 150 galvanizado", "V3 · reforço W 200 da pAa8rede aberta",
              "muro de contenção drenado (até ≈ 4,7 m) + guarda-corpo 1,10 m", "Taludes 1:1 com gabião e vetiver"]
F02B_ESTRUTURA = "02b_Pranchas_Tecnicas_A3.pdf › Estrutura geral e fundações; plantas de forma e detalhes"
PRANCHA_02B = [  # caminho, valor, fonte, unidade, zona, nota
    ("alturas.total.casa_lab_mec_m", 5.8, F02B_SOMBRAS, "m", LOTE, "LAB e MEC: a 03 dá baixo + cima = 5,80 m (igual)"),
    ("alturas.total.lofts_m", 5.0, F02B_SOMBRAS, "m", "Z3",
     "a tabela de cortes cita também \"5,00 (20 m²) e 3,00 (16 m²)\" em leiaute ambíguo [CONFERIR]"),
    ("alturas.total.restaurante_m", 4.0, F02B_SOMBRAS, "m", "Z2", None),
    ("alturas.total.gourmet_m", 3.2, F02B_SOMBRAS, "m", "Z1", "pé-direito 3,20 na tabela de cortes"),
    ("casa1.altura_conteiner_m", 2.59, F02B_CORTES, "m", "Z1", "níveis ±0,00, +2,59 e +5,18 no corte longitudinal"),
    ("telhados.conteineres", "plana 3% com placas a 15–20°", F02B_CORTES, None, LOTE, "Casa 1, LAB e MEC"),
    ("telhados.lofts_pct", 15.0, F02B_CORTES, "%", "Z3", "água única, telha com isolamento"),
    ("telhados.restaurante_pct", 45.0, F02B_CORTES, "%", "Z2", "cônica, rufos e calha periférica; telha sanduíche"),
    ("telhados.gourmet", "telhado de madeira com telha cerâmica", F02B_CORTES, None, "Z1",
     "inclinação [MARCADOR]: a prancha não dá"),
    ("energia.fv.placa_inclinacao", "15–20°", F02B_PLACAS, None, LOTE, "placas voltadas à Rua G (norte de projeto)"),
    ("estrutura.pilar", "tubular 100 × 100 × 4,75", F02B_ESTRUTURA, "mm", LOTE, "lofts, restaurante e pergolados"),
    ("estrutura.bloco", "0,70 × 0,70 × 0,60", F02B_ESTRUTURA, "m", LOTE, "tracejado 0,60 × 0,60 indicativo na Casa 1 e nos lofts"),
    ("estrutura.bloco_aflorando_m", 0.30, F02B_ESTRUTURA, "m", LOTE, "blocos de concreto aflorando 30 cm do solo"),
    ("estrutura.casa1", "A1 a A15 nos cantos e no meio dos contêineres de 40 pés", F02B_ESTRUTURA, None, "Z1", None),
    ("estrutura.lab_mec", "contêineres em T sobre 8 pilares", F02B_ESTRUTURA, None, "Z2", None),
    ("estrutura.lofts", "pilares na grade de 4 m", F02B_ESTRUTURA, None, "Z3", None),
    ("estrutura.restaurante", "C0 a C8: centro e anel a cada 45°; D1 a D10 nos decks", F02B_ESTRUTURA, None, "Z2", None),
    ("estrutura.lab_mec_pilares", "P1 a P4 nos cantos do contêiner inferior; P5 a P8 nas extremidades do de cima (balanços de 1,81 m)",
     F02B_ESTRUTURA, None, "Z2", "a 03 dá balanços de 1,23 m (LAB e MEC de cima × de baixo) [CONFERIR]"),
    ("estrutura.vigas.lab_mec", "W 150", F02B_ESTRUTURA, None, "Z2", "sob o contêiner de cima"),
    ("estrutura.vigas.lofts_borda", "W 150 × 13", F02B_ESTRUTURA, None, "Z3", "vão de 4 m"),
    ("estrutura.vigas.lofts_central", "W 200 × 15", F02B_ESTRUTURA, None, "Z3", "vão de 4 m (W 150 × 13 não atende a flecha)"),
    ("estrutura.vigas.restaurante", "W 150", F02B_ESTRUTURA, None, "Z2", "vigas radiais e anel, galvanizado"),
    ("estrutura.vigas.casa1_v3", "W 200", F02B_ESTRUTURA, None, "Z1", "V3: reforço da parede aberta entre os contêineres de 40 pés"),
    ("estrutura.contraventamento", "em X nos lofts e no restaurante", F02B_ESTRUTURA, None, LOTE, "seção da barra [MARCADOR]"),
    ("contencao.muro_rua_g", "muro de contenção drenado (até ≈ 4,7 m) + guarda-corpo 1,10 m", F02B_ESTRUTURA, None, "Z3",
     "platô da Rua G (prancha 21); espessura [MARCADOR]"),
    ("contencao.muro_altura_max_m", 4.7, F02B_ESTRUTURA, "m", "Z3", "valor aproximado na fonte (≈)"),
    ("contencao.taludes", "taludes 1:1 com gabião e vetiver", F02B_ESTRUTURA, None, LOTE, "platôs sem muro"),
]


def tipo_planejador(chave):
    for pre, tipo in TIPO_PLANEJADOR:
        if chave.startswith(pre):
            return tipo
    return "pavimento"  # caminhos, rampas, passarelas, escadas, trilhas, fogo de chão, calçadas (calc_*)


def nome_curto(chave, desc):
    if not desc:
        return chave
    s = re.split(r" · | \(|:", str(desc))[0].strip()
    if len(s) > 48:
        s = s[:48].rsplit(" ", 1)[0] + "…"
    return s or chave


def elementos_implantacao(p03):
    """Linhas da 03 › Implantação que têm zona (≈ 92): cada uma vira um elemento do gêmeo."""
    aba = "Implantação"
    out = []
    for n, v in sorted(p03.aba(aba).items()):
        zona = G.zona_de(v.get("C"))
        if not zona or not v.get("A"):
            continue
        f = lambda col: v.get(col) if isinstance(v.get(col), float) else None
        out.append({
            "chave": str(v["A"]).strip(), "linha_03": n, "zona": zona, "entidade": G.ZONAS[zona]["entidade"],
            "descricao": v.get("B"), "x_03": f("D"), "y_03": f("E"), "larg_m": f("F"), "prof_m": f("G"),
            "area_m2": f("H"), "piso_topo_m": f("I"), "pilar_max_m": f("J"), "corte_m3": f("K"), "aterro_m3": f("L"),
            "fonte": p03.fonte(aba, n), "procedencia": "estimado",
        })
    if not out:
        raise FonteAusente("planilha 03 › Implantação sem elementos com zona")
    chaves = [e["chave"] for e in out]
    if len(set(chaves)) != len(chaves):
        raise FonteAusente("planilha 03 › Implantação com chave repetida")
    return out


def item_planejador(e, ocupacao):
    """Item do Planejador (x/y no CENTRO, como o Planejador desenha); a 03 dá o canto (ver convenções)."""
    w, d = e["larg_m"] or 0.0, e["prof_m"] or 0.0
    return {"id": "g-" + e["chave"], "tipo": tipo_planejador(e["chave"]), "nome": nome_curto(e["chave"], e["descricao"]),
            "x": round((e["x_03"] or 0) + w / 2, 3), "y": round((e["y_03"] or 0) + d / 2, 3),
            "w": w, "d": d, "rot": 0, "pav": 1, "ocup": ocupacao, "cota": e["piso_topo_m"]}


# ---------------------------------------------------------------- G0 · números de sistemas (planilha 20)

ZONA_QUADRO_AREAS = {  # edificação da 20 → zona da linha correspondente na 03 › Implantação
    "Casa 1": "Z1", "Gourmet": "Z1", "LAB": "Z2", "MEC": "Z2", "Restaurante": "Z2", "Lofts 1 a 4": "Z3",
    "Lofts 5 e 6": "Z3", "Lofts": "Z3", "Apoio e lavabos": "Z2", "Cogumelário e canil": "Z2", "Loja 24 h": "Z3"}
ZONA_QUADRO_CARGAS = {  # quadros que servem a uma zona só; os demais são do lote
    "Restaurante": "Z2", "Casa 1": "Z1", "MEC": "Z2", "LAB": "Z2", "Apoio de funcionários": "Z2",
    "Loja 24 h": "Z3", "Piscina natural": "Z1", "Cisterna C2": "Z2", "Gourmet": "Z1",
    "Peixes, criação e viveiro": "Z2", "Fossa e filtro": "Z3", "Gourmet e deck": "Z1"}
ZONA_CISTERNA = {"C1": "Z1", "C2": "Z2", "C3": "Z3", "C8 a C10 (modulares)": "Z3"}  # pelo "Local" da 20
ZONA_TRATAMENTO = {"Biodigestor": "Z2", "Caixa de gordura": "Z2", "Fossa séptica": "Z3", "Filtro anaeróbio": "Z3",
                   "Floresta filtrante": "Z3"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def _slug(s):
    s = str(s).lower()
    for a, b in (("áàâã", "a"), ("éê", "e"), ("í", "i"), ("óôõ", "o"), ("ú", "u"), ("ç", "c")):
        for c in a:
            s = s.replace(c, b)
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def sistemas_e_divergencias(p20, p03, p18, els):
    fv = {}

    def put(caminho, v, fonte, **kw):
        if caminho in fv:
            raise ValueError(f"valor repetido: {caminho}")
        fv[caminho] = valor(v, fonte, **kw)

    # --- lote e áreas (D4, D6)
    a, f = p20.celula("Índices", "Área do lote", "B")
    rgi, f_rgi = p03.celula("Levantamento", "Área do RGI", "B")
    lev, f_lev = p03.celula("Levantamento", "Área do novo levantamento", "B")
    put("lote.area_m2", num_br(a), f, unidade="m²",
        conferir=_conferir("D6", (num_br(rgi), f_rgi + " (área do RGI e da planta do loteamento; retificação pendente)")),
        nota=f"coincide com o levantamento ({lev} m², {f_lev})")
    n_or, orl = p03.linha("Levantamento", "Orientação")
    m_or = re.search(r"aponta a cerca de (\d+(?:,\d+)?)°", str(orl["A"]))
    if not m_or:
        raise FonteAusente("planilha 03 › Levantamento: orientação do eixo do lote não encontrada")
    put("lote.norte_verdadeiro_graus", num_br(m_or.group(1)), p03.fonte("Levantamento", n_or, "A"), unidade="°",
        nota="o eixo do lote (y local, Rua G = norte de projeto) aponta ≈ 17° a leste do norte verdadeiro; no IFC, "
             "TrueNorth = (−sen, cos) [CONFERIR com o topógrafo: seta e rumos da prancha girados ≈ 90°; M&A pg:afe44bbf677a]")
    # 20 › Perímetro: azimutes dos lados. +y (V2→V3) a 17° e −y (V4→V1) a 197° concordam; +x (V1→V2) a 287° só
    # fecha com +y a 17° se a planta local estiver espelhada (num sistema destro seria 107°): D10 [CONFERIR]
    n_v12, v12 = p20.linha("Perímetro", "V1 → V2")
    n_v23, v23 = p20.linha("Perímetro", "V2 → V3")
    az12, az23 = numeros_br(v12["C"])[0], numeros_br(v23["C"])[0]
    esperado = (az23 + 90) % 360
    put("lote.azimute_eixo_x_graus", az12, p20.fonte("Perímetro", n_v12, "C"), unidade="°",
        conferir=_conferir("D10", (esperado, f"cálculo: +y a {az23:g}° ({p20.fonte('Perímetro', n_v23, 'C')}) num sistema "
                                             "destro; 287° indica planta espelhada ou rumo lido ao contrário")) if abs(az12 - esperado) > 1 else None,
        nota="conferir com o topógrafo junto com a seta do norte (M&A pg:afe44bbf677a)")
    per, f = p03.celula("Levantamento", "Perímetro", "B")
    put("lote.perimetro_m", num_br(per), f, unidade="m")

    v, f = p20.celula("Índices", "Área construída total", "B")
    put("areas.construida_total_m2", num_br(v), f, unidade="m²")
    v, f = p20.celula("Índices", "Projeção das edificações", "B")
    proj_03, f_p03 = p03.celula("Implantação", "Projeção das construções", "H")
    to_03, f_to03 = p03.celula("Implantação", "Taxa de ocupação", "H")
    put("areas.projecao_m2", numeros_br(v)[0], f, unidade="m²",
        conferir=_conferir("D4", (proj_03, f_p03 + " (sem decks e varandas)")))
    put("areas.projecao_pct", numeros_br(v)[1], f, unidade="%",
        conferir=_conferir("D4", (round(to_03 * 100, 1), f_to03 + " (taxa de ocupação × 100)")))
    for rot, cam in (("Pavimentos", "areas.pavimentos_m2"), ("Área impermeável", "areas.impermeavel"),
                     ("Área permeável", "areas.permeavel")):
        v, f = p20.celula("Índices", rot, "B")
        n = numeros_br(v)
        if cam == "areas.pavimentos_m2":
            put(cam, n[0], f, unidade="m²")
        else:
            put(cam + "_m2", n[0], f, unidade="m²")
            put(cam + "_pct", n[1], f, unidade="%")
    v, f = p20.celula("Índices", "Coeficiente de aproveitamento", "B")
    put("areas.coef_aproveitamento", num_br(v), f)

    aba = "Quadro de áreas"
    for n, lv in sorted(p20.aba(aba).items()):
        ed = str(lv.get("A", "")).strip()
        if n == 1 or not ed or ed.startswith("Total"):
            continue
        z = ZONA_QUADRO_AREAS.get(ed, LOTE)
        base = f"areas.quadro.{_slug(ed)}" + (f".{_slug(lv['B'])}" if lv.get("B") else "")
        put(base + ".construida_m2", num_br(lv["C"]), p20.fonte(aba, n, "C"), unidade="m²", zona=z)
        put(base + ".projecao_m2", num_br(lv["D"]), p20.fonte(aba, n, "D"), unidade="m²", zona=z)
    n, lv = p20.linha(aba, "Total")
    put("areas.quadro.total.construida_m2", num_br(lv["C"]), p20.fonte(aba, n, "C"), unidade="m²")
    put("areas.quadro.total.projecao_m2", num_br(lv["D"]), p20.fonte(aba, n, "D"), unidade="m²")

    # --- programa: lofts (D3) e Casa 1 (D2)
    n1, l1 = p20.linha(aba, "Lofts 1 a 4")
    n2, l2 = p20.linha(aba, "Lofts 5 e 6")
    q = lambda s: (lambda a: int(a[-1] - a[0] + 1))(numeros_br(s))
    lofts_03 = [e for e in els if e["chave"].startswith("LF") and (e["area_m2"] or 0) > 0]
    sem_lugar = [e["chave"] for e in els if e["chave"].startswith("LF") and not (e["area_m2"] or 0) > 0]
    put("programa.lofts", q(l1["A"]) + q(l2["A"]), f"planilha 20 › {aba}, linhas {n1} e {n2}", unidade="lofts",
        zona="Z3", conferir=_conferir("D3", (len(lofts_03), "planilha 03 › Implantação, "
                                                            + ", ".join(e["chave"] for e in lofts_03)
                                                            + f" ({', '.join(sem_lugar)}: \"não cabe\")")))
    v, f = p20.celula("Água vertical", "Casa 1", "B")
    put("casa1.cota_piso_m", num_br(v), f, unidade="m", zona="Z1",
        conferir=_conferir("D2", ("≈ 889 a 891 (platô intermediário)", "doc 10 (Casa 1), citado no doc 47 §2.4")),
        nota="a 03 › Implantação traz o mesmo valor (linha da Casa 1)")

    # --- energia (D1, D5)
    aba = "Strings FV"
    ultimo = None
    for n, lv in sorted(p20.aba(aba).items()):
        if n == 1 or not lv.get("A"):
            continue
        fase = int(num_br(lv["A"]))
        put(f"energia.fv.placas_acumuladas.fase{fase}", numeros_br(lv["B"])[-1], p20.fonte(aba, n, "B"),
            unidade="placas")
        ultimo = (n, lv)
    sol_n, sol = p03.linha("Solar", "Total")
    put("energia.fv.placas", numeros_br(ultimo[1]["B"])[-1], p20.fonte(aba, ultimo[0], "B"), unidade="placas",
        conferir=_conferir("D1", (sol["F"], p03.fonte("Solar", sol_n, "F"))))
    pn, pl = None, None
    for n, lv in sorted(p03.aba("Placas solares").items()):
        if str(lv.get("A", "")).startswith("Fase"):
            pn, pl = n, lv
    if pl is None:
        raise FonteAusente("planilha 03 › Placas solares sem fases")
    put("energia.fv.kwp", pl["F"], p03.fonte("Placas solares", pn, "F"), unidade="kWp",
        conferir=_conferir("D1", (sol["H"], p03.fonte("Solar", sol_n, "H"))),
        nota="a planilha 20 não traz o kWp; a 03 › Placas solares soma as mesmas 56 placas da 20 › Strings FV")
    # onde ficam as placas (03 › Placas solares soma as mesmas 56 da 20) e a placa (03 › Premissas): para o 3D
    for n, lv in sorted(p03.aba("Placas solares").items()):
        if str(lv.get("A", "")).startswith("Fase") and isinstance(lv.get("C"), float):
            put(f"energia.fv.local.{_slug(lv['B'])}.placas", lv["C"], p03.fonte("Placas solares", n, "C"),
                unidade="placas", nota=f"{lv['A']} · {lv['B']}")
    v, f = p03.celula("Premissas", "Potência da placa", "B")
    put("energia.fv.placa_kwp", v, f, unidade="kWp")
    v, f = p03.celula("Premissas", "Área da placa", "B")
    put("energia.fv.placa_area_m2", v, f, unidade="m²")
    n_tel, tel = p03.linha("Solar", "Norte = Rua G")
    m = re.search(r"caem para o norte a (\d+(?:,\d+)?)°", str(tel["A"]))
    if not m:
        raise FonteAusente("planilha 03 › Solar: inclinação dos telhados não encontrada")
    put("telhados.inclinacao_graus", num_br(m.group(1)), p03.fonte("Solar", n_tel, "A"), unidade="°",
        nota="todos os telhados caem para o norte (Rua G, +y local); o 3D usa as coberturas da 02b (pg:74fabc0568d2)",
        conferir=_conferir("D7", ("plana 3% (contêineres), água única 15% (lofts), cônica 45% (restaurante), telha "
                                  "cerâmica (gourmet)", F02B_CORTES)))
    # prancha 02b (PDF do acervo): alturas e coberturas que a 20 e a 03 não têm (decisões pg:58d2e859f36a e
    # pg:74fabc0568d2); os textos são conferidos no PDF pelo teste Acervo quando o pdftotext existe
    for cam, v, fonte, un, zona, nota in PRANCHA_02B:
        put(cam, v, fonte, unidade=un, zona=zona, nota=nota)
    put("alturas.pavimento_m", 2.90, "planilha 03 › Implantação: LAB e MEC de cima − de baixo (891,36 → 894,26; "
        "892,86 → 895,76)", unidade="m", conferir=_conferir("D8", (2.59, F02B_CORTES + ": níveis +2,59 e +5,18 dos "
                                                                       "contêineres da Casa 1")))
    inv = {}
    for n, lv in sorted(p20.aba(aba).items()):
        m = re.search(r"inversor híbrido (\d+) \((\d+(?:,\d+)?) kW", str(lv.get("C", "")))
        if m:
            inv[int(m.group(1))] = (num_br(m.group(2)), p20.fonte(aba, n, "C"))
    for k, (kw, f) in sorted(inv.items()):
        put(f"energia.fv.inversor{k}_kw", kw, f, unidade="kW")
    for n, lv in sorted(p20.aba("Cronograma").items()):
        m = re.search(r"baterias (\d+(?:,\d+)?) kWh", str(lv.get("E", "")))
        if m:
            put("energia.baterias_kwh", num_br(m.group(1)), p20.fonte("Cronograma", n, "E"), unidade="kWh")
    aba = "Quadro de cargas"
    for n, lv in sorted(p20.aba(aba).items()):
        nome = str(lv.get("A", "")).strip()
        if n == 1 or not nome:
            continue
        if nome.startswith("Total"):
            put("energia.potencia_instalada_kw", num_br(lv["B"]), p20.fonte(aba, n, "B"), unidade="kW",
                nota="com simultaneidade de 0,75 entre quadros")
            put("energia.demanda_kw", num_br(lv["D"]), p20.fonte(aba, n, "D"), unidade="kW")
            put("energia.corrente_a", num_br(lv["E"]), p20.fonte(aba, n, "E"), unidade="A")
        else:
            put(f"energia.quadro.{_slug(nome)}.instalada_kw", num_br(lv["B"]), p20.fonte(aba, n, "B"), unidade="kW",
                zona=ZONA_QUADRO_CARGAS.get(nome, LOTE))
            put(f"energia.quadro.{_slug(nome)}.demanda_kw", num_br(lv["D"]), p20.fonte(aba, n, "D"), unidade="kW",
                zona=ZONA_QUADRO_CARGAS.get(nome, LOTE))
    c03, f03 = p03.celula("Energia", "Total", "B")
    alts = [(c03, f03 + " (base conservadora de dimensionamento)")]
    if p18 is not None:
        c18, f18 = p18.celula("Resumo por grupo", "Total", "B")
        alts.append((c18, f18 + " (equipamentos com ocupação plena)"))
    else:
        alts.append((2939.4, "planilha 18 › Resumo, citada no doc 47 §2.4"))
    put("energia.consumo_kwh_mes", None, "planilha 20 (não traz consumo mensal)", unidade="kWh/mês",
        marcador="[MARCADOR] consumo mensal fora da planilha 20, que é a fonte única", conferir=_conferir("D5", *alts),
        nota="mantido vazio por decisão da dona em 21/11/2026 (M&A pg:310a1c0db09d)")

    # --- água
    aba = "Cisternas"
    for n, lv in sorted(p20.aba(aba).items()):
        nome = str(lv.get("A", "")).strip()
        if n == 1 or not nome:
            continue
        if nome.startswith("Total"):
            put("agua.reservacao_total_m3", num_br(lv["C"]), p20.fonte(aba, n, "C"), unidade="m³")
            continue
        z = ZONA_CISTERNA.get(nome, LOTE)
        put(f"agua.cisterna.{_slug(nome)}.volume_m3", num_br(lv["C"]), p20.fonte(aba, n, "C"), unidade="m³", zona=z,
            nota=f"{lv.get('B', '')}; fase {lv.get('E', '')}")
    aba = "Balanço hídrico"
    linhas = {str(lv.get("A", "")).strip(): (n, lv) for n, lv in p20.aba(aba).items()}
    if any(m not in linhas for m in MESES):
        raise FonteAusente("planilha 20 › Balanço hídrico sem os 12 meses")
    ns = [linhas[m][0] for m in MESES]
    for col, cam in (("B", "captacao_m3"), ("C", "demanda_nao_potavel_m3"), ("D", "estoque_fim_m3")):
        put(f"agua.balanco_mensal.{cam}", [num_br(linhas[m][1][col]) for m in MESES],
            f"planilha 20 › {aba}, linhas {min(ns)} a {max(ns)}, col. {col} (jan a dez)", unidade="m³/mês")
    aba = "Balanço por fase"
    for n, lv in sorted(p20.aba(aba).items()):
        if n == 1 or not lv.get("A"):
            continue
        r = int(num_br(lv["A"]))
        put(f"agua.balanco_fase.reservacao_{r}m3.cobertura_pct", num_br(lv["B"]), p20.fonte(aba, n, "B"), unidade="%")
        put(f"agua.balanco_fase.reservacao_{r}m3.rede_m3_ano", num_br(lv["D"]), p20.fonte(aba, n, "D"), unidade="m³/ano",
            nota=f"meses com complemento da rede: {lv.get('C', '')}")

    # --- esgoto, biogás e drenagem
    aba = "Tratamento"
    for nome, z in ZONA_TRATAMENTO.items():
        v, f = p20.celula(aba, nome, "B")
        un = "m²" if "m²" in str(v) else "L" if re.search(r"\bL\b", str(v)) else "m³"
        put(f"esgoto.{_slug(nome)}", num_br(v), f, unidade=un, zona=z,
            nota=("valor aproximado na fonte (≈)" if "≈" in str(v) else None))
    v, f = p20.celula("Drenagem", "Jardim de chuva", "D")
    put("drenagem.jardim_de_chuva_m3", num_br(v), f, unidade="m³", zona="Z1", nota="valor aproximado na fonte (≈)")
    v, f = p20.celula("Drenagem", "Detenção", "D")
    put("drenagem.detencao_m3", num_br(v), f, unidade="m³", zona="Z3", nota=str(v))

    # --- hidráulica e esgoto (camada casa-gemeo-hidraulica, decisão pg:ee988f1fe957)
    aba = "Esgoto trechos"
    for n, lv in sorted(p20.aba(aba).items()):
        tr = str(lv.get("A", "")).strip()
        if n == 1 or "→" not in tr:
            continue
        base = f"esgoto.trecho.{_slug(tr)}"
        put(base + ".dn_mm", num_br(lv["B"]), p20.fonte(aba, n, "B"), unidade="mm", nota=tr)
        put(base + ".comprimento_m", num_br(lv["C"]), p20.fonte(aba, n, "C"), unidade="m", nota=tr)
        put(base + ".declividade_pct", num_br(lv["D"]), p20.fonte(aba, n, "D"), unidade="%", nota=tr)
        put(base + ".terreno_inicio_m", num_br(lv["E"]), p20.fonte(aba, n, "E"), unidade="m", nota=tr)
        put(base + ".fundo_inicio_m", num_br(lv["F"]), p20.fonte(aba, n, "F"), unidade="m", nota=tr)
        put(base + ".terreno_fim_m", num_br(lv["G"]), p20.fonte(aba, n, "G"), unidade="m", nota=tr)
        put(base + ".fundo_fim_m", num_br(lv["H"]), p20.fonte(aba, n, "H"), unidade="m", nota=f"{tr}; {lv.get('I', '')}")
    aba = "Tratamento"
    for nome in ("Biodigestor", "Caixa de gordura", "Fossa séptica", "Filtro anaeróbio", "Floresta filtrante", "Caixas de inspeção"):
        v, f = p20.celula(aba, nome, "C")
        put(f"esgoto.dimensoes.{_slug(nome)}", str(v), f, zona=ZONA_TRATAMENTO.get(nome, LOTE),
            nota="dimensões úteis (m), como escritas na planilha")
    aba = "Cisternas"
    for n, lv in sorted(p20.aba(aba).items()):
        nome = str(lv.get("A", "")).strip()
        if n == 1 or not nome or nome.startswith("Total"):
            continue
        put(f"agua.cisterna.{_slug(nome)}.dimensoes", str(lv.get("D", "")), p20.fonte(aba, n, "D"),
            zona=ZONA_CISTERNA.get(nome, LOTE), nota="dimensões úteis (m), como escritas na planilha")
    # água por cota: a cota do ponto é da 20; a geometria é da 03 (R1-1): diferença vira D9 [CONFERIR]
    aba = "Água vertical"
    ref03 = {"Casa 1": "casa", "Gourmet": "gourmet", "LAB inferior": "lab", "MEC superior": "mec_up",
             "Restaurante": "bar", "Loft 4": "LF4", "Loft 2": "LF2", "Platô da Rua G": "garagem"}
    cotas03 = {e["chave"]: (e["piso_topo_m"], e["fonte"]) for e in els}
    for n, lv in sorted(p20.aba(aba).items()):
        nome = str(lv.get("A", "")).strip()
        if n == 1 or not nome:
            continue
        cota = num_br(lv["B"])
        chave = next((c for pre, c in ref03.items() if nome.startswith(pre)), None)
        conf = None
        if chave and cotas03.get(chave, (None,))[0] is not None and abs(cotas03[chave][0] - cota) > 0.05:
            conf = _conferir("D9", (cotas03[chave][0], cotas03[chave][1] + f" ({chave}, geometria da 03)"))
        base = f"agua.ponto.{_slug(nome)}"
        put(base + ".cota_m", cota, p20.fonte(aba, n, "B"), unidade="m", conferir=conf,
            nota=f"elemento da 03: {chave}" if chave else None)
        put(base + ".pressao_mca", num_br(lv["D"]), p20.fonte(aba, n, "D"), unidade="m.c.a.",
            nota=f"pressão estática da rede; {lv.get('E', '')}")
    aba = "Drenagem"
    for n, lv in sorted(p20.aba(aba).items()):
        nome = str(lv.get("A", "")).strip()
        if n == 1 or not nome:
            continue
        put(f"drenagem.elemento.{_slug(nome)}", f"{lv.get('B', '')} · {lv.get('C', '')} · {lv.get('D', '')}",
            p20.fonte(aba, n), nota="dimensão · declividade · capacidade, como escritas; posição [MARCADOR]")

    # --- estrutura: apoios por edificação (20 › Fundações)
    aba = "Fundações"
    for n, lv in sorted(p20.aba(aba).items()):
        nome = str(lv.get("A", "")).strip()
        if n == 1 or not nome or "B" not in lv:
            continue
        z = {"Casa 1": "Z1", "Gourmet": "Z1", "Restaurante": "Z2", "LAB ou MEC": "Z2"}.get(nome, "Z3" if nome.startswith("Loft") else LOTE)
        put(f"estrutura.apoios.{_slug(nome)}", num_br(lv["B"]), p20.fonte(aba, n, "B"), unidade="apoios", zona=z,
            nota=f"bloco indicativo {lv.get('E', '')}; carga total {lv.get('C', '')} kN")

    # --- totais da 03 › Implantação (conferência do cadastro)
    n, lv = p03.linha("Implantação", "Total")
    put("implantacao.corte_total_m3", lv["K"], p03.fonte("Implantação", n, "K"), unidade="m³")
    put("implantacao.aterro_total_m3", lv["L"], p03.fonte("Implantação", n, "L"), unidade="m³")
    return fv


# ---------------------------------------------------------------- terreno e clima (Planejador)

def area_poligono(poly):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2


def _dentro(p, poly):
    x, y, d = p[0], p[1], False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            d = not d
    return d


def _com_arcos(poly, linhas, fonte, passos=12):
    """Troca a corda de um lado em arco ('arco R 19,464 m' na col. D) por pontos do arco menor com o raio do
    levantamento, com a flecha para dentro do lote. A planilha não diz o lado da flecha: com ela para dentro a área do
    polígono dá a área do levantamento (1.455,95 m²); para fora daria ≈ 76 m² a mais. O teste confere a área."""
    import math
    out, notas = [], []
    for i, (p, lv) in enumerate(zip(poly, linhas)):
        out.append(p)
        m = re.search(r"arco R (\d+(?:,\d+)?) m", str(lv.get("D", "")))
        if not m:
            continue
        r = num_br(m.group(1))
        a, b = p, poly[(i + 1) % len(poly)]
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        c = math.hypot(b[0] - a[0], b[1] - a[1])
        h = math.sqrt(max(r * r - (c / 2) ** 2, 0.0))
        ux, uy = -(b[1] - a[1]) / c, (b[0] - a[0]) / c  # normal à corda
        escolhido = None
        for s in (1, -1):
            cx, cy = mx + s * h * ux, my + s * h * uy
            meio = (cx + r * (mx - cx) / h, cy + r * (my - cy) / h) if h else (mx, my)
            if _dentro(meio, poly):
                escolhido = (cx, cy)
        if escolhido is None:
            continue
        cx, cy = escolhido
        t0, t1 = math.atan2(a[1] - cy, a[0] - cx), math.atan2(b[1] - cy, b[0] - cx)
        dt = (t1 - t0 + math.pi) % (2 * math.pi) - math.pi  # arco menor
        for k in range(1, passos):
            t = t0 + dt * k / passos
            out.append([round(cx + r * math.cos(t), 3), round(cy + r * math.sin(t), 3)])
        notas.append(f"lado {lv.get('D')} desenhado como arco de raio {m.group(1)} m com a flecha para dentro do lote "
                     f"({passos} trechos; {fonte})")
    return out, ("; ".join(notas) or "lados retos entre os vértices")


def terreno(p03, p20):
    aba = "Levantamento"
    n0, _ = p03.linha(aba, "Vértice")
    poly, nv = [], []
    for n, lv in sorted(p03.aba(aba).items()):
        if n > n0 and re.match(r"P-\d+", str(lv.get("A", ""))):
            poly.append([lv["B"], lv["C"]])
            nv.append(n)
    if len(poly) < 3:
        raise FonteAusente("planilha 03 › Levantamento sem vértices")
    poly, nota_arco = _com_arcos(poly, [p03.aba(aba)[n] for n in nv], p03.fonte(aba, nv[0], "D"))
    pontos, fontes = [], []
    for n, lv in sorted(p20.aba("Vértices").items()):
        if n > 1 and lv.get("D"):
            pontos.append([num_br(lv["B"]), num_br(lv["C"]), num_br(lv["D"])])
    fontes.append("planilha 20 › Vértices (cotas dos vértices)")
    nc, _ = p03.linha(aba, "Curva de nível")
    _, cab = p03.linha(aba, "Curva de nível")
    x_b, x_c = numeros_br(cab["B"])[-1], numeros_br(cab["C"])[-1]  # 'x = 0' e 'x = 22'
    for n, lv in sorted(p03.aba(aba).items()):
        if n > nc and isinstance(lv.get("A"), float):
            pontos.append([x_b, lv["B"], lv["A"]])
            pontos.append([x_c, lv["C"], lv["A"]])
    fontes.append(f"planilha 03 › {aba}, curvas de nível (linha {nc} em diante)")
    t = {"fonte": f"planilha 03 › {aba} (vértices P-01 a P-0{len(poly)}) + cotas da 20", "crs": "local (metros)",
         "lat0": None, "lon0": None, "poly": poly, "pontos": pontos, "grade": None, "matricula": None}
    prov = {
        "terreno.poly": {"st": "est", "src": f"planilha 03 › {aba}, linhas {nv[0]} a {nv[-1]} (x/y local, P-01 = 0,0); "
                         f"{nota_arco}; sem lat/long oficial [MARCADOR L-01]"},
        "terreno.pontos": {"st": "est", "src": "; ".join(fontes)},
    }
    return t, prov


def clima(p03):
    aba = "Premissas"
    nc, ch = p03.linha(aba, "Chuva")
    nt, te = p03.linha(aba, "Temperatura")
    nh, hh = p03.linha(aba, "Sol pleno horizontal")
    pr_valor, pr_fonte = p03.celula(aba, "Desempenho do sistema FV", "B")
    cols = "BCDEFGHIJKLM"
    serie = lambda lv: [lv[c] for c in cols]
    temp = serie(te)
    c = {"H": serie(hh), "chuva": serie(ch), "kt": 0.5, "pr": pr_valor,
         "idf": {"K": None, "a": None, "b": None, "c": None, "nome": ""}, "temp": round(sum(temp) / 12, 2)}
    prov = {
        "clima.chuva": {"st": "est", "src": p03.fonte(aba, nc) + " (mm, jan a dez)"},
        "clima.H": {"st": "est", "src": p03.fonte(aba, nh) + " (kWh/m²·dia, jan a dez)"},
        "clima.temp": {"st": "est", "src": "média dos 12 meses de " + p03.fonte(aba, nt)},
        "clima.pr": {"st": "est", "src": pr_fonte},
        "clima.kt": {"st": "est", "src": "padrão do Planejador (a planilha 03 não traz kt)"},
    }
    return c, prov


def ocupacoes(p03):
    """Ocupação dos itens de moradia e hospedagem (03 › Premissas); os demais ficam 0."""
    mor, f_mor = p03.celula("Premissas", "Moradores da casa", "B")
    hos_n, hos = p03.linha("Premissas", "Hóspedes")
    por_loft = numeros_br(hos["A"])[-1]  # 'Hóspedes (7 lofts × 4)'
    return {"casa": (int(mor), f_mor), "LF": (int(por_loft), p03.fonte("Premissas", hos_n, "A") + " (× por loft)")}


# ---------------------------------------------------------------- montagem

def importar(caminho_20, caminho_03, caminho_18=None, data=None):
    p20 = Planilha("20", caminho_20)
    p03 = Planilha("03", caminho_03)
    p18 = Planilha("18", caminho_18) if caminho_18 and Path(caminho_18).exists() else None
    els = elementos_implantacao(p03)
    fv = sistemas_e_divergencias(p20, p03, p18, els)
    ter, prov_t = terreno(p03, p20)
    fv["lote.area_poligono_m2"] = valor(round(area_poligono(ter["poly"]), 2), "calculada do polígono do terreno: "
                                        + prov_t["terreno.poly"]["src"], unidade="m²",
                                        nota="conferência da geometria com lote.area_m2")
    cli, prov_c = clima(p03)
    ocup = ocupacoes(p03)

    itens, elementos = [], {}
    for e in els:
        oc, f_oc = 0, None
        if (e["area_m2"] or 0) > 0:
            for pre, (q, f) in ocup.items():
                if e["chave"].startswith(pre):
                    oc, f_oc = q, f
        it = item_planejador(e, oc)
        itens.append(it)
        ch = e.pop("chave")
        elementos[ch] = {**e, "item_id": it["id"], "tipo_planejador": it["tipo"], "sem_area": not (e["area_m2"] or 0) > 0,
                         **({"ocupacao_fonte": f_oc} if f_oc else {})}

    _, to = p03.linha("Implantação", "Taxa de ocupação")
    n_to = p03.linha("Implantação", "Taxa de ocupação")[0]
    to_lim = numeros_br(to["A"])[0]  # '(limite 40%)'
    regras = {"to": to_lim, "ca": None, "perm": None, "recFrente": None, "recLat": None, "recFundo": None, "gabarito": None}
    prov = {**prov_t, **prov_c,
            "regras.to": {"st": "est", "src": p03.fonte("Implantação", n_to, "A") + " (limite citado na planilha)"},
            "sistemas.solar": {"st": "est", "src": "planilha 20 › Strings FV"},
            "sistemas.biogas": {"st": "est", "src": "planilha 20 › Tratamento (biodigestor com gasômetro)"},
            "sistemas.chuva": {"st": "est", "src": "planilha 20 › Cisternas e Balanço hídrico"},
            "sistemas.baterias": {"st": "est", "src": fv["energia.baterias_kwh"]["fonte"]},
            "sistemas.reuso": {"st": "est", "src": "[CONFERIR] reúso não aparece na planilha 20; mantido desligado"}}

    fontes = {}
    for sig, pl in (("20", p20), ("03", p03), ("18", p18)):
        if pl is not None:
            fontes[sig] = {"arquivo": pl.caminho.name, "sha256": sha256(pl.caminho)}

    hoje = data or date.today().isoformat()
    return {
        "schema": G.SCHEMA_PLANEJADOR,
        "meta": {"nome": "Casa Physis · Lote 168 · gêmeo digital (semente rev0, TESTE)", "municipio": "", "uf": "",
                 "responsavel": "", "criado": hoje},
        "terreno": ter,
        "clima": cli,
        "solo": {"classe": "", "sadm": None, "ci": None, "spt": ""},
        "regras": regras,
        "itens": itens,
        "hidro": {"rios": [], "nascentes": []},
        "sistemas": {"solar": True, "biogas": True, "chuva": True, "reuso": False, "baterias": True},
        "premissas": {"coefC": {"telhado": 0.95, "pav": 0.9, "grama": 0.25, "mata": 0.15, "solo": 0.35},
                      "Tr": 25, "tc": 10, "negras": 20},
        "prov": prov,
        "log": [{"t": hoje, "d": f"semente {SEMENTE} importada das planilhas 20 e 03 (gemeo_importar)"}],
        "inicio": {"obras": [], "blocos": ["implantacao"], "nivel": "basico", "lat": None, "lon": None, "area": None,
                   "docs": []},
        "gemeo": {
            "esquema": G.ESQUEMA,
            "semente": SEMENTE,
            "revisao": REVISAO,
            "revisao_desc": "estudo preliminar (revisão 0)",
            "versao": "TESTE",
            "decisoes": ["R1-1 pg:178d054ba7c7", "R1-2 pg:e8443161d98c", "R2-1 pg:fc7006fb00a2",
                         "R2-3 pg:cfddb1061265", "D5 vazio pg:310a1c0db09d", "x/y da 03 = canto pg:8d264ca11dc1"],
            "politica_dados": "R2-3: público = planta, sistemas, simulado e medido agregado (dia/mês); interno = "
                              "leituras de 5–15 min, ocupação, pessoas; nunca dado pessoal. Esta semente só tem "
                              "dados de projeto.",
            "fontes": fontes,
            "zonas": G.ZONAS,
            "convencoes": {
                "origem": "x/y local em metros, P-01 = (0, 0); y cresce da Rua H para a Rua G; sem georreferência",
                "x_y_03": "a 03 › Implantação dá o canto do retângulo (x, y), confirmado pela dona em 21/11/2026 "
                          "(M&A pg:8d264ca11dc1); o item do Planejador guarda o centro (x + larg/2, y + prof/2)",
                "giro": "nos lofts girados a 03 dá larg./prof. da caixa envolvente; o giro fica só na descrição (rot = 0)",
                "sem_area": "linhas com 0,01 m e área 0 na 03 (desativadas ou só de cálculo) entram como elemento, "
                            "marcadas sem_area",
                "tipo_planejador": "classificação de desenho (cor e categoria no mapa), a revisar na G2",
            },
            "estado_de_vida": {"padrao": "projetado", "por_elemento": {k: "projetado" for k in elementos}},
            "camadas": {
                "estatico": {"situacao": "semeado", "revisao": REVISAO},
                "simulado": {"situacao": "a fazer (G4)", "cenarios": []},
                "medido": {"situacao": "aguardando sensores", "pontos": []},
            },
            "elementos": elementos,
            "fonte_por_valor": fv,
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Planilhas 20 e 03 da Casa Physis → semente do gêmeo (Planejador)")
    ap.add_argument("--editaveis", default=str(PASTA_PADRAO), help="pasta com as planilhas 03, 18 e 20")
    ap.add_argument("--saida", default=None, help="arquivo .json (padrão: mostra o resumo e não grava)")
    ap.add_argument("--data", default=None, help="data da importação (AAAA-MM-DD)")
    a = ap.parse_args(argv)
    pasta = Path(a.editaveis)
    proj = importar(pasta / ARQ_20, pasta / ARQ_03, pasta / ARQ_18, data=a.data)
    prob = G.validar(proj)
    t = G.totais(proj)
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{t['elementos']} elementos {t['por_zona']}; corte {t['corte_m3']} m³, aterro {t['aterro_m3']} m³")
    print(f"[CONFERIR] abertos: {sorted(set(G.conferir_abertos(proj).values()))}; marcadores: {len(G.marcadores(proj))}")
    if prob:
        print("PROBLEMAS:", *prob, sep="\n  ")
        return 1
    if a.saida:
        Path(a.saida).write_text(json.dumps(proj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("gravado em", a.saida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
