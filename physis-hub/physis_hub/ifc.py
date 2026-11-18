"""BIM aberto (IFC4, ISO 16739-1) só com a biblioteca padrão: escrever, ler o básico.

escrever(d) → texto STEP (ISO 10303-21) com IfcProject, IfcSite (latitude e longitude), IfcBuilding, IfcBuildingStorey e
os sistemas que os módulos pré-dimensionam, como elementos tipados do IFC4 (ou IfcBuildingElementProxy quando o IFC4 não
tem um tipo próprio), cada um com uma caixa envolvente (IfcBoundingBox) e conjuntos de propriedades com unidade:
  pv (IfcSolarDevice .SOLARPANEL.), inversor (IfcTransformer .INVERTER.), cisterna (IfcTank .STORAGE.),
  calha (IfcPipeSegment .GUTTER.), condutor (IfcPipeSegment .RIGIDSEGMENT.), avac (IfcUnitaryEquipment .SPLITSYSTEM.),
  quadro (IfcElectricDistributionBoard .DISTRIBUTIONBOARD.), turbina (IfcElectricGenerator .USERDEFINED.),
  biodigestor, canteiro e rack (IfcBuildingElementProxy .USERDEFINED.).
Elétrica: todo elemento com potência leva Physis_Eletrica com fator de potência, potência ativa (kW), reativa (kvar) e
aparente (kVA). O fator vem do projeto ou da premissa eletrica.fator_potencia_padrao; sem os dois, o fator e as potências
reativa e aparente ficam vazios ($) com a nota [CONFERIR] — nunca um número inventado.
Materiais: ligados à base sistema/physis-materiais.json (quantidade e carbono incorporado, com a unidade).

ler(bytes) → resumo sem núcleo de geometria: esquema, projeto, terrenos (lat/lon), edificações, pavimentos, contagem de
elementos por tipo e a caixa envolvente aproximada (origens das peças + IfcBoundingBox, sem rotações). Ver a geometria
completa fica para um visualizador IFC aberto (docs/MAPEAMENTO.md).
"""
from __future__ import annotations

import json
import math
import os
import re
import time
import uuid
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[2]
ALFABETO_GUID = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"
PREMISSA_FP = "eletrica.fator_potencia_padrao"
MAX_IFC_BYTES = 50 * 1024 * 1024


# ═══════════════ GUID e texto STEP ═══════════════
def guid_ifc(u: uuid.UUID | None = None) -> str:
    """GUID comprimido do IFC (22 caracteres, base 64 própria do IFC)."""
    n = (u or uuid.uuid4()).int
    out = []
    for _ in range(22):
        out.append(ALFABETO_GUID[n % 64])
        n //= 64
    return "".join(reversed(out))


def guid_estavel(*partes) -> str:
    return guid_ifc(uuid.uuid5(uuid.NAMESPACE_OID, "physis:" + ":".join(str(p) for p in partes)))


GUID_RX = re.compile(r"^[0-3][0-9A-Za-z_$]{21}$")


def s_(txt) -> str:
    """Texto STEP: aspas dobradas, barra invertida dobrada e não-ASCII em \\X2\\…\\X0\\ (UTF-16)."""
    if txt is None:
        return "$"
    out = []
    for ch in str(txt):
        if ch == "'":
            out.append("''")
        elif ch == "\\":
            out.append("\\\\")
        elif 32 <= ord(ch) < 127:
            out.append(ch)
        else:
            out.append("\\X2\\" + ch.encode("utf-16-be").hex().upper() + "\\X0\\")
    return "'" + "".join(out) + "'"


def r_(v) -> str:
    if v is None:
        return "$"
    v = float(v)
    if not math.isfinite(v):
        return "$"
    t = repr(v).upper()
    if "E" in t:
        m, e = t.split("E")
        if "." not in m:
            m += "."
        return f"{m}E{int(e)}"
    return t if "." in t else t + "."


def _texto_step(s: str) -> str:
    s = re.sub(r"\\X2\\([0-9A-Fa-f]+)\\X0\\", lambda m: bytes.fromhex(m.group(1)).decode("utf-16-be"), s)
    return s.replace("\\\\", "\\")


# ═══════════════ Bases (premissas e materiais) ═══════════════
def _json_base(env: str, nome: str) -> dict:
    p = os.environ.get(env) or str(RAIZ_REPO / "sistema" / nome)
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def premissa(id_: str, base: dict | None = None):
    b = base if base is not None else _json_base("PHYSIS_PREMISSAS", "physis-premissas.json")
    for p in b.get("premissas") or []:
        if p.get("id") == id_:
            return p.get("valor_padrao")
    return None


def materiais_base() -> dict:
    b = _json_base("PHYSIS_MATERIAIS", "physis-materiais.json")
    return {m["id"]: m for m in b.get("materiais") or [] if isinstance(m, dict) and m.get("id")}


def potencias(p_kw, fp) -> dict:
    """P (kW), Q (kvar) = P·tan(acos fp), S (kVA) = P/fp. fp vazio = Q e S vazios."""
    if p_kw is None:
        return {"P_kW": None, "Q_kvar": None, "S_kVA": None, "fp": fp}
    if fp is None or not (0 < float(fp) <= 1):
        return {"P_kW": float(p_kw), "Q_kvar": None, "S_kVA": None, "fp": None}
    fp = float(fp)
    return {"P_kW": float(p_kw), "Q_kvar": float(p_kw) * math.tan(math.acos(fp)), "S_kVA": float(p_kw) / fp, "fp": fp}


def carbono_material(mat: dict, base: dict) -> dict:
    """Quantidade em kg (de kg, t, m³ pela densidade, ou m² pela espessura típica) × carbono incorporado (kgCO2e/kg)."""
    b = base.get(mat.get("id"))
    q, un = mat.get("quantidade"), str(mat.get("unidade") or "kg")
    out = {"id": mat.get("id"), "nome": b["nome"] if b else None, "quantidade": q, "unidade": un, "kg": None, "kgco2e": None,
           "fator_kgco2e_kg": None, "fonte": None, "nota": ""}
    if not b:
        out["nota"] = "material fora da base sistema/physis-materiais.json"
        return out
    ci = b.get("carbono_incorporado") or {}
    out["fator_kgco2e_kg"], out["fonte"] = ci.get("valor"), ci.get("fonte")
    if q is None:
        return out
    q = float(q)
    kg = {"kg": q, "t": q * 1000}.get(un)
    if kg is None and un in ("m3", "m³") and b.get("densidade"):
        kg = q * b["densidade"]
    if kg is None and un in ("m2", "m²") and b.get("densidade") and b.get("espessura_tipica_m"):
        kg = q * b["espessura_tipica_m"] * b["densidade"]
        out["nota"] = "m² convertido pela espessura típica da base (conferir a espessura do projeto)"
    out["kg"] = kg
    if kg is not None and ci.get("valor") is not None and str(ci.get("unidade", "")).startswith("kgCO2e/kg"):
        out["kgco2e"] = kg * ci["valor"]
    return out


# ═══════════════ Tipos de elemento ═══════════════
# tipo → (entidade IFC, tipo pré-definido, ObjectType, nome do conjunto de propriedades, elétrico?)
TIPOS = {
    "pv": ("IFCSOLARDEVICE", "SOLARPANEL", "Arranjo fotovoltaico", "Physis_Solar", True),
    "modulo_pv": ("IFCSOLARDEVICE", "SOLARPANEL", "Módulo fotovoltaico", "Physis_Solar", False),
    "inversor": ("IFCTRANSFORMER", "INVERTER", "Inversor fotovoltaico", "Physis_Inversor", True),
    "cisterna": ("IFCTANK", "STORAGE", "Cisterna de água de chuva", "Physis_Agua", False),
    "calha": ("IFCPIPESEGMENT", "GUTTER", "Calha", "Physis_Drenagem", False),
    "condutor": ("IFCPIPESEGMENT", "RIGIDSEGMENT", "Condutor vertical", "Physis_Drenagem", False),
    "avac": ("IFCUNITARYEQUIPMENT", "SPLITSYSTEM", "Equipamento de climatização", "Physis_AVAC", True),
    "quadro": ("IFCELECTRICDISTRIBUTIONBOARD", "DISTRIBUTIONBOARD", "Quadro elétrico", "Physis_Quadro", True),
    "turbina": ("IFCELECTRICGENERATOR", "USERDEFINED", "Microturbina hidráulica", "Physis_Turbina", True),
    "biodigestor": ("IFCBUILDINGELEMENTPROXY", "USERDEFINED", "Biodigestor", "Physis_Biodigestor", False),
    "canteiro": ("IFCBUILDINGELEMENTPROXY", "USERDEFINED", "Canteiro de viveiro", "Physis_Viveiro", False),
    "rack": ("IFCBUILDINGELEMENTPROXY", "USERDEFINED", "Estrutura de fixação (rack)", "Physis_Estrutura", False),
}
# unidade de cada chave conhecida das propriedades (o resto pode vir como {"valor": …, "unidade": …})
UNIDADES = {"kwp": "kWp", "potencia_kw": "kW", "potencia_ca_kw": "kW", "volume_m3": "m³", "volume_l": "L", "secao_mm": "mm",
            "diametro_mm": "mm", "largura_mm": "mm", "lamina_mm": "mm", "btu_h": "BTU/h", "incl_graus": "°", "azim_graus": "°",
            "passo_fileiras_m": "m", "area_m2": "m²", "vazao_l_min": "L/min", "vazao_m3_h": "m³/h", "circuitos": "un",
            "modulos": "un", "energia_kwh_ano": "kWh/ano", "biogas_m3_dia": "m³/dia", "comprimento_m": "m", "massa_g": "g",
            "strings": "un", "modulos_por_string": "un", "irradiacao_kwh_m2_ano": "kWh/m²·ano", "mudas": "un", "altura_queda_m": "m"}
SI = {"m": ("LENGTHUNIT", None, "METRE"), "m²": ("AREAUNIT", None, "SQUARE_METRE"), "m³": ("VOLUMEUNIT", None, "CUBIC_METRE"),
      "kW": ("POWERUNIT", "KILO", "WATT"), "kg": ("MASSUNIT", "KILO", "GRAM"), "g": ("MASSUNIT", None, "GRAM"), "mm": ("LENGTHUNIT", "MILLI", "METRE")}


class Escritor:
    def __init__(self, chave: str):
        self.linhas: list[str] = []
        self.chave = chave
        self.unidades: dict = {}

    def add(self, txt: str) -> str:
        self.linhas.append(txt)
        return f"#{len(self.linhas)}"

    def guid(self, *p) -> str:
        return s_(guid_estavel(self.chave, *p))

    def unidade(self, un: str) -> str:
        if un in self.unidades:
            return self.unidades[un]
        if un in SI:
            t, pre, nome = SI[un]
            ref = self.add(f"IFCSIUNIT(*,.{t}.,{'.' + pre + '.' if pre else '$'},.{nome}.)")
        elif un == "°":
            ref = self.unidades["°"] = self._grau()
        else:
            dims = self.unidades.get("_dims") or self.add("IFCDIMENSIONALEXPONENTS(0,0,0,0,0,0,0)")
            self.unidades["_dims"] = dims
            ref = self.add(f"IFCCONTEXTDEPENDENTUNIT({dims},.USERDEFINED.,{s_(un)})")
        self.unidades[un] = ref
        return ref

    def _grau(self) -> str:
        rad = self.unidades.get("rad") or self.add("IFCSIUNIT(*,.PLANEANGLEUNIT.,$,.RADIAN.)")
        self.unidades["rad"] = rad
        dims = self.unidades.get("_dims") or self.add("IFCDIMENSIONALEXPONENTS(0,0,0,0,0,0,0)")
        self.unidades["_dims"] = dims
        m = self.add(f"IFCMEASUREWITHUNIT(IFCPLANEANGLEMEASURE({r_(math.pi / 180)}),{rad})")
        return self.add(f"IFCCONVERSIONBASEDUNIT({dims},.PLANEANGLEUNIT.,'DEGREE',{m})")

    def ponto(self, x, y, z) -> str:
        return self.add(f"IFCCARTESIANPOINT(({r_(x)},{r_(y)},{r_(z)}))")

    def colocacao(self, rel: str | None, x=0.0, y=0.0, z=0.0) -> str:
        ax = self.add(f"IFCAXIS2PLACEMENT3D({self.ponto(x, y, z)},$,$)")
        return self.add(f"IFCLOCALPLACEMENT({rel or '$'},{ax})")

    def propriedade(self, nome: str, valor, unidade: str | None = None, descricao: str | None = None) -> str:
        if isinstance(valor, bool):
            v, un = f"IFCBOOLEAN(.{'T' if valor else 'F'}.)", None
        elif isinstance(valor, int) and unidade in (None, "un"):
            v, un = f"IFCINTEGER({valor})", None
        elif isinstance(valor, (int, float)):
            v, un = f"IFCREAL({r_(valor)})", unidade
        elif valor is None:
            v, un = "$", unidade
        else:
            v, un = f"IFCLABEL({s_(str(valor)[:255])})", None
        return self.add(f"IFCPROPERTYSINGLEVALUE({s_(nome)},{s_(descricao) if descricao else '$'},{v},{self.unidade(un) if un else '$'})")

    def pset(self, oh: str, nome: str, props: list[str], objetos: list[str], chave) -> None:
        if not props or not objetos:
            return
        ps = self.add(f"IFCPROPERTYSET({self.guid('pset', chave, nome)},{oh},{s_(nome)},$,({','.join(props)}))")
        self.add(f"IFCRELDEFINESBYPROPERTIES({self.guid('rdp', chave, nome)},{oh},$,$,({','.join(objetos)}),{ps})")


def _num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _valor_unidade(k, v):
    if isinstance(v, dict) and "valor" in v:
        return v["valor"], v.get("unidade") or UNIDADES.get(k)
    return v, UNIDADES.get(k)


def escrever(d: dict, agora: float | None = None) -> str:
    """Arquivo IFC4 (texto STEP) a partir do JSON dos módulos (formato em docs/MAPEAMENTO.md)."""
    if not isinstance(d, dict):
        raise ValueError("entrada: objeto JSON")
    proj = d.get("projeto") or {}
    chave = str(proj.get("id") or proj.get("nome") or "projeto")
    nome_proj = str(proj.get("nome") or "Projeto Physis")[:120]
    site = d.get("site") or {}
    lat, lon = _num(site.get("lat")), _num(site.get("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("site.lat e site.lon são obrigatórios (o lugar vem do Início/Mapeamento)")
    elementos = d.get("elementos") or []
    if len(elementos) > 5000:
        raise ValueError("elementos demais (máximo 5.000)")
    prem = d.get("premissas") or {}
    fp_padrao = prem.get(PREMISSA_FP, premissa(PREMISSA_FP))
    mats = materiais_base() if d.get("materiais_base") is None else {m["id"]: m for m in d["materiais_base"]}
    W = Escritor(chave)
    t = int(agora if agora is not None else time.time())
    # contexto, pessoas e unidades
    pe = W.add("IFCPERSON($,$,'Physis',$,$,$,$,$)")
    org = W.add("IFCORGANIZATION($,'Physis Engineering',$,$,$)")
    po = W.add(f"IFCPERSONANDORGANIZATION({pe},{org},$)")
    app = W.add(f"IFCAPPLICATION({org},'0.1','Physis Mapeamento','physis-mapeamento')")
    oh = W.add(f"IFCOWNERHISTORY({po},{app},$,.ADDED.,$,$,$,{t})")
    origem = W.add(f"IFCAXIS2PLACEMENT3D({W.ponto(0, 0, 0)},$,$)")
    norte = W.add("IFCDIRECTION((0.,1.))")
    ctx = W.add(f"IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,{origem},{norte})")
    base_un = [W.unidade(u) for u in ("m", "m²", "m³", "°", "kW", "kg")]
    ua = W.add(f"IFCUNITASSIGNMENT(({','.join(base_un)}))")
    projeto = W.add(f"IFCPROJECT({W.guid('projeto')},{oh},{s_(nome_proj)},$,$,$,$,({ctx}),{ua})")

    def dms(v):
        sinal = -1 if v < 0 else 1
        a = abs(v)
        g = int(a)
        m = int((a - g) * 60)
        s = int((a - g - m / 60) * 3600)
        mi = int(round(((a - g - m / 60) * 3600 - s) * 1e6))
        if mi >= 1_000_000:
            s, mi = s + 1, mi - 1_000_000
        return f"({sinal * g},{sinal * m},{sinal * s},{sinal * mi})"
    pl_site = W.colocacao(None)
    sitio = W.add(f"IFCSITE({W.guid('site')},{oh},{s_(site.get('nome') or 'Terreno')},$,$,{pl_site},$,$,.ELEMENT.,{dms(lat)},{dms(lon)},"
                  f"{r_(_num(site.get('altitude_m')))},$,$)")
    W.add(f"IFCRELAGGREGATES({W.guid('agg-proj')},{oh},$,$,{projeto},({sitio}))")
    edifs = d.get("edificacoes") or [{"id": "ed1", "nome": "Edificação", "pavimentos": [{"id": "terreo", "nome": "Térreo", "elevacao_m": 0}]}]
    pav_ref, pav_pl, bloco = {}, {}, []
    for e in edifs:
        eid = str(e.get("id") or e.get("nome"))
        pl = W.colocacao(pl_site)
        b = W.add(f"IFCBUILDING({W.guid('ed', eid)},{oh},{s_(e.get('nome') or 'Edificação')},$,$,{pl},$,$,.ELEMENT.,$,$,$)")
        bloco.append(b)
        pvs = []
        for p in e.get("pavimentos") or [{"id": "terreo", "nome": "Térreo", "elevacao_m": 0}]:
            pid = str(p.get("id") or p.get("nome"))
            el = _num(p.get("elevacao_m")) or 0.0
            ppl = W.colocacao(pl, 0, 0, el)
            st = W.add(f"IFCBUILDINGSTOREY({W.guid('pav', eid, pid)},{oh},{s_(p.get('nome') or pid)},$,$,{ppl},$,$,.ELEMENT.,{r_(el)})")
            pvs.append(st)
            pav_ref.setdefault(pid, st)
            pav_pl.setdefault(pid, ppl)
            pav_ref.setdefault("_primeiro", st)
            pav_pl.setdefault("_primeiro", ppl)
        W.add(f"IFCRELAGGREGATES({W.guid('agg-ed', eid)},{oh},$,$,{b},({','.join(pvs)}))")
    W.add(f"IFCRELAGGREGATES({W.guid('agg-site')},{oh},$,$,{sitio},({','.join(bloco)}))")
    contidos: dict = {}
    doc_ref = None
    for i, el in enumerate(elementos):
        tipo = str(el.get("tipo") or "")
        if tipo not in TIPOS:
            raise ValueError(f"tipo de elemento desconhecido: {tipo[:30]} (aceitos: {', '.join(TIPOS)})")
        ent, pre, otype, psnome, eletrico = TIPOS[tipo]
        eid = str(el.get("id") or f"{tipo}-{i + 1}")
        pid = str(el.get("pavimento") or "_primeiro")
        if pid not in pav_ref:
            raise ValueError(f"pavimento desconhecido: {pid[:40]}")
        pos = el.get("posicao") or {}
        pl = W.colocacao(pav_pl[pid], _num(pos.get("x")) or 0.0, _num(pos.get("y")) or 0.0, _num(pos.get("z")) or 0.0)
        rep = "$"
        cx = el.get("caixa") or {}
        if all(_num(cx.get(k)) and _num(cx.get(k)) > 0 for k in ("dx", "dy", "dz")):
            bb = W.add(f"IFCBOUNDINGBOX({W.ponto(0, 0, 0)},{r_(cx['dx'])},{r_(cx['dy'])},{r_(cx['dz'])})")
            sr = W.add(f"IFCSHAPEREPRESENTATION({ctx},'Box','BoundingBox',({bb}))")
            rep = W.add(f"IFCPRODUCTDEFINITIONSHAPE($,$,({sr}))")
        nome = s_(str(el.get("nome") or otype)[:120])
        ot = s_(el.get("object_type") or otype)
        guid = W.guid("el", eid)
        if ent == "IFCBUILDINGELEMENTPROXY":
            ref = W.add(f"{ent}({guid},{oh},{nome},$,{ot},{pl},{rep},{s_(eid)},.{pre}.)")
        else:
            ref = W.add(f"{ent}({guid},{oh},{nome},$,{ot},{pl},{rep},{s_(eid)},.{pre}.)")
        contidos.setdefault(pid, []).append(ref)
        props = el.get("propriedades") or {}
        lista = [W.propriedade("Origem", str(el.get("origem") or "Physis"))]
        for k, v in props.items():
            if k in ("fator_potencia",):
                continue
            val, un = _valor_unidade(k, v)
            lista.append(W.propriedade(k, val, un))
        W.pset(oh, psnome, lista, [ref], eid)
        # elétrica: fator de potência, P, Q e S sempre juntos
        p_kw = _num(_valor_unidade("potencia_kw", props.get("potencia_kw"))[0]) if props.get("potencia_kw") is not None else (
            _num(_valor_unidade("kwp", props.get("kwp"))[0]) if tipo == "pv" else None)
        if eletrico or p_kw is not None:
            fp_proj = _num(props.get("fator_potencia"))
            fp = fp_proj if fp_proj is not None else _num(fp_padrao)
            pq = potencias(p_kw, fp)
            orig = ("projeto" if fp_proj is not None else f"premissa {PREMISSA_FP}" if fp is not None
                    else f"[CONFERIR] premissa {PREMISSA_FP} ainda não existe na base: fator, Q e S ficam vazios")
            W.pset(oh, "Physis_Eletrica", [
                W.add(f"IFCPROPERTYSINGLEVALUE('FatorPotencia',{s_(orig)},{('IFCRATIOMEASURE(' + r_(pq['fp']) + ')') if pq['fp'] is not None else '$'},$)"),
                W.propriedade("PotenciaAtiva", pq["P_kW"], "kW"), W.propriedade("PotenciaReativa", pq["Q_kvar"], "kvar"),
                W.propriedade("PotenciaAparente", pq["S_kVA"], "kVA")], [ref], eid)
        # materiais da base, com quantidade e carbono
        mlist = el.get("materiais") or []
        if mlist:
            cs, mp, tot = [], [], 0.0
            for m in mlist:
                c = carbono_material(m, mats)
                mat = W.add(f"IFCMATERIAL({s_(c['nome'] or m.get('id'))},$,{s_((mats.get(m.get('id')) or {}).get('grupo'))})")
                cs.append(W.add(f"IFCMATERIALCONSTITUENT({s_(m.get('id'))},$,{mat},$,$)"))
                mp.append(W.propriedade(f"{m.get('id')}.quantidade", _num(c["quantidade"]), c["unidade"].replace("m3", "m³").replace("m2", "m²")))
                mp.append(W.propriedade(f"{m.get('id')}.carbono", c["kgco2e"], "kgCO2e", (c["fonte"] or c["nota"] or None)))
                tot += c["kgco2e"] or 0.0
            mset = W.add(f"IFCMATERIALCONSTITUENTSET({s_('Materiais ' + eid)},$,({','.join(cs)}))")
            W.add(f"IFCRELASSOCIATESMATERIAL({W.guid('mat', eid)},{oh},$,$,({ref}),{mset})")
            mp.append(W.propriedade("CarbonoIncorporadoTotal", tot, "kgCO2e", "soma dos materiais com fator na base"))
            W.pset(oh, "Physis_Materiais", mp, [ref], eid)
        # memorial (peça impressa em 3D e outros): referência a documento
        memo = el.get("memorial") or {}
        if memo.get("id") or memo.get("uri"):
            doc_ref = W.add(f"IFCDOCUMENTREFERENCE({s_(memo.get('uri'))},{s_(memo.get('id'))},{s_(memo.get('nome') or 'Memorial')},$,$)")
            W.add(f"IFCRELASSOCIATESDOCUMENT({W.guid('doc', eid)},{oh},$,$,({ref}),{doc_ref})")
        # módulos do arranjo como peças filhas (IfcRelAggregates)
        filhos = []
        for k, mo in enumerate(el.get("modulos") or []):
            mpl = W.colocacao(pav_pl[pid], _num(mo.get("x")) or 0.0, _num(mo.get("y")) or 0.0, _num(mo.get("z")) or 0.0)
            filhos.append(W.add(f"IFCSOLARDEVICE({W.guid('mod', eid, k)},{oh},{s_(f'Módulo {k + 1}')},$,{s_('Módulo fotovoltaico')},{mpl},$,{s_(f'{eid}-m{k + 1}')},.SOLARPANEL.)"))
        if filhos:
            W.add(f"IFCRELAGGREGATES({W.guid('agg-mod', eid)},{oh},$,$,{ref},({','.join(filhos)}))")
    for pid, refs in contidos.items():
        W.add(f"IFCRELCONTAINEDINSPATIALSTRUCTURE({W.guid('cont', pid)},{oh},$,$,({','.join(refs)}),{pav_ref[pid]})")
    data = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t))
    arq = re.sub(r"[^A-Za-z0-9_.-]", "_", nome_proj)[:60] + ".ifc"
    cab = ["ISO-10303-21;", "HEADER;", "FILE_DESCRIPTION(('ViewDefinition [ReferenceView_V1.2]'),'2;1');",
           f"FILE_NAME({s_(arq)},'{data}',('Physis'),('Physis Engineering'),'Physis Mapeamento 0.1','Physis Sistema','');",
           "FILE_SCHEMA(('IFC4'));", "ENDSEC;", "DATA;"]
    return "\n".join(cab + [f"#{i + 1}={x};" for i, x in enumerate(W.linhas)] + ["ENDSEC;", "END-ISO-10303-21;", ""])


# ═══════════════ Leitor mínimo ═══════════════
def _instancias(dados: str) -> dict:
    """{id: (TIPO, texto dos argumentos)} da seção DATA, cortando por ';' fora de textos."""
    i = dados.find("DATA;")
    if i < 0:
        raise ValueError("arquivo IFC sem seção DATA")
    fim = dados.rfind("ENDSEC;")
    corpo = dados[i + 5:fim if fim > i else len(dados)]
    out, atual, aspas, j = {}, [], False, 0
    while j < len(corpo):
        c = corpo[j]
        if c == "'":
            if aspas and j + 1 < len(corpo) and corpo[j + 1] == "'":
                atual.append("''")
                j += 2
                continue
            aspas = not aspas
        if c == ";" and not aspas:
            txt = "".join(atual).strip()
            atual = []
            m = re.match(r"#(\d+)\s*=\s*([A-Za-z0-9_]+)\s*\((.*)\)\s*$", txt, re.S)
            if m:
                out[int(m.group(1))] = (m.group(2).upper(), m.group(3))
        else:
            atual.append(c)
        j += 1
    return out


def argumentos(s: str) -> list:
    """Argumentos STEP: listas, textos, #ref (int em dict {'ref': n}), $ (None), enumerações, números e valores tipados."""
    pos = 0

    def valor():
        nonlocal pos
        while s[pos] in " \r\n\t":
            pos += 1
        c = s[pos]
        if c == "(":
            pos += 1
            lst = []
            while True:
                while s[pos] in " \r\n\t":
                    pos += 1
                if s[pos] == ")":
                    pos += 1
                    return lst
                lst.append(valor())
                while s[pos] in " \r\n\t":
                    pos += 1
                if s[pos] == ",":
                    pos += 1
        if c == "'":
            j = pos + 1
            buf = []
            while True:
                if s[j] == "'":
                    if j + 1 < len(s) and s[j + 1] == "'":
                        buf.append("'")
                        j += 2
                        continue
                    break
                buf.append(s[j])
                j += 1
            pos = j + 1
            return _texto_step("".join(buf))
        if c == "#":
            m = re.match(r"#(\d+)", s[pos:])
            pos += len(m.group(0))
            return {"ref": int(m.group(1))}
        if c in "$*":
            pos += 1
            return None
        if c == ".":
            j = s.index(".", pos + 1)
            v = s[pos + 1:j]
            pos = j + 1
            return {"enum": v}
        m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", s[pos:])
        if m:
            pos += len(m.group(0))
            return {"tipo": m.group(0).upper(), "valor": valor()}
        m = re.match(r"[-+0-9.Ee]+", s[pos:])
        pos += len(m.group(0))
        t = m.group(0)
        return float(t) if any(x in t for x in ".Ee") else int(t)
    out = []
    s = s + ")"
    while True:
        while pos < len(s) and s[pos] in " \r\n\t":
            pos += 1
        if s[pos] == ")":
            return out
        out.append(valor())
        while s[pos] in " \r\n\t":
            pos += 1
        if s[pos] == ",":
            pos += 1


def _grau_dms(v) -> float | None:
    if not isinstance(v, list) or len(v) < 3:
        return None
    return v[0] + v[1] / 60 + v[2] / 3600 + (v[3] if len(v) > 3 else 0) / 3.6e9


def ler(dados: bytes) -> dict:
    """Resumo do IFC: esquema, projeto, terrenos, edificações, pavimentos, elementos por tipo e caixa envolvente."""
    if len(dados) > MAX_IFC_BYTES:
        raise ValueError("IFC grande demais para o leitor básico (máximo 50 MB)")
    txt = dados.decode("utf-8", errors="replace")
    if not txt.lstrip().startswith("ISO-10303-21;"):
        raise ValueError("não é um arquivo IFC em texto STEP (ISO-10303-21)")
    m = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", txt)
    ins = _instancias(txt)
    cache: dict = {}

    def a(n):
        if n not in cache:
            cache[n] = argumentos(ins[n][1])
        return cache[n]

    def ref(v):
        return v.get("ref") if isinstance(v, dict) else None

    def origem(pl, prof=0):
        """Soma as translações da cadeia de IfcLocalPlacement (sem rotações)."""
        if pl is None or prof > 50 or pl not in ins or ins[pl][0] != "IFCLOCALPLACEMENT":
            return (0.0, 0.0, 0.0)
        ar = a(pl)
        base = origem(ref(ar[0]), prof + 1)
        ax = ref(ar[1])
        p = (0.0, 0.0, 0.0)
        if ax in ins and ins[ax][0].startswith("IFCAXIS2PLACEMENT"):
            pt = ref(a(ax)[0])
            if pt in ins and ins[pt][0] == "IFCCARTESIANPOINT":
                c = list(a(pt)[0]) + [0.0, 0.0, 0.0]
                p = (float(c[0]), float(c[1]), float(c[2]))
        return tuple(base[i] + p[i] for i in range(3))
    por_tipo: dict = {}
    tipos: dict = {}
    for n, (t, _) in ins.items():
        tipos[t] = tipos.get(t, 0) + 1
    projeto = next((a(n)[2] for n, (t, _) in ins.items() if t == "IFCPROJECT"), None)
    sites = [{"nome": a(n)[2], "lat": _grau_dms(a(n)[9]), "lon": _grau_dms(a(n)[10]), "altitude_m": a(n)[11]} for n, (t, _) in ins.items() if t == "IFCSITE"]
    edifs = [{"nome": a(n)[2]} for n, (t, _) in ins.items() if t == "IFCBUILDING"]
    pavs = [{"nome": a(n)[2], "elevacao_m": a(n)[9] if len(a(n)) > 9 else None} for n, (t, _) in ins.items() if t == "IFCBUILDINGSTOREY"]
    mn, mx, n_el = [math.inf] * 3, [-math.inf] * 3, 0
    for n, (t, _) in ins.items():
        if t != "IFCRELCONTAINEDINSPATIALSTRUCTURE":
            continue
        for e in a(n)[4] or []:
            e = ref(e)
            if e not in ins:
                continue
            te = ins[e][0]
            por_tipo[te] = por_tipo.get(te, 0) + 1
            n_el += 1
            ae = a(e)
            o = origem(ref(ae[5]) if len(ae) > 5 else None)
            dims = (0.0, 0.0, 0.0)
            rp = ref(ae[6]) if len(ae) > 6 else None
            if rp in ins and ins[rp][0] == "IFCPRODUCTDEFINITIONSHAPE":
                for sr in a(rp)[2] or []:
                    sr = ref(sr)
                    if sr in ins and ins[sr][0] == "IFCSHAPEREPRESENTATION":
                        for it in a(sr)[3] or []:
                            it = ref(it)
                            if it in ins and ins[it][0] == "IFCBOUNDINGBOX":
                                b = a(it)
                                dims = (float(b[1]), float(b[2]), float(b[3]))
            for k in range(3):
                mn[k] = min(mn[k], o[k])
                mx[k] = max(mx[k], o[k] + dims[k])
    unidade = "m"
    for n, (t, _) in ins.items():
        if t == "IFCSIUNIT":
            x = a(n)
            if isinstance(x[1], dict) and x[1].get("enum") == "LENGTHUNIT" and isinstance(x[2], dict):
                unidade = {"MILLI": "mm", "CENTI": "cm"}.get(x[2]["enum"], unidade)
    return {"esquema": m.group(1) if m else None, "projeto": projeto, "entidades": len(ins), "terrenos": sites, "edificacoes": edifs,
            "pavimentos": pavs, "elementos": n_el, "elementos_por_tipo": dict(sorted(por_tipo.items())),
            "caixa": {"min": mn, "max": mx, "unidade": unidade, "nota": "origens das peças mais IfcBoundingBox, sem rotações"} if n_el else None,
            "tipos": tipos}
