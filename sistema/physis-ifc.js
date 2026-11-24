/* physis-ifc.js — IFC4 (texto STEP) no NAVEGADOR: o mesmo escritor e o mesmo leitor de physis-hub/physis_hub/ifc.py, para o
   Mapeamento funcionar sem servidor (pedido de 15/11/2026: "garantir que aba mapeamento funcione sem servidor").
   Contrato: window.PhysisIFC = { escrever(d, {agora, materiais, premissa}), ler(texto), guidEstavel(...partes), s_, r_, TIPOS }.
   Paridade: ferramentas/testes-navegador/conferir-modelos.html gera o modelo de exemplo daqui e compara com o modelo.ifc
   gerado pelo ifc.py (mesmo texto). Só funções puras; nada de internet. */
(function (global) {
"use strict";
const ALFABETO = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$";
const PREMISSA_FP = "eletrica.fator_potencia_padrao";
const NS_OID = [0x6b, 0xa7, 0xb8, 0x12, 0x9d, 0xad, 0x11, 0xd1, 0x80, 0xb4, 0x00, 0xc0, 0x4f, 0xd4, 0x30, 0xc8];

/* SHA-1 (síncrono, para o uuid5 igual ao do Python) */
function sha1(bytes) {
  const ml = bytes.length, n = (((ml + 8) >> 6) + 1) * 16, w = new Array(n).fill(0);
  for (let i = 0; i < ml; i++) w[i >> 2] |= bytes[i] << (24 - (i % 4) * 8);
  w[ml >> 2] |= 0x80 << (24 - (ml % 4) * 8); w[n - 1] = ml * 8;
  let h0 = 0x67452301, h1 = 0xEFCDAB89, h2 = 0x98BADCFE, h3 = 0x10325476, h4 = 0xC3D2E1F0; const W = new Array(80);
  const rol = (x, c) => (x << c) | (x >>> (32 - c));
  for (let b = 0; b < n; b += 16) {
    for (let t = 0; t < 80; t++) W[t] = t < 16 ? w[b + t] | 0 : rol(W[t - 3] ^ W[t - 8] ^ W[t - 14] ^ W[t - 16], 1);
    let a = h0, bb = h1, c = h2, d = h3, e = h4;
    for (let t = 0; t < 80; t++) {
      const f = t < 20 ? (bb & c) | (~bb & d) : t < 40 ? bb ^ c ^ d : t < 60 ? (bb & c) | (bb & d) | (c & d) : bb ^ c ^ d;
      const k = t < 20 ? 0x5A827999 : t < 40 ? 0x6ED9EBA1 : t < 60 ? 0x8F1BBCDC : 0xCA62C1D6;
      const tmp = (rol(a, 5) + f + e + k + W[t]) | 0; e = d; d = c; c = rol(bb, 30); bb = a; a = tmp; }
    h0 = (h0 + a) | 0; h1 = (h1 + bb) | 0; h2 = (h2 + c) | 0; h3 = (h3 + d) | 0; h4 = (h4 + e) | 0; }
  const out = []; [h0, h1, h2, h3, h4].forEach(h => { for (let i = 3; i >= 0; i--) out.push((h >>> (i * 8)) & 255); }); return out; }
const utf8 = s => Array.from(new TextEncoder().encode(String(s)));
function guidEstavel(...partes) {
  const h = sha1(NS_OID.concat(utf8("physis:" + partes.map(p => String(p)).join(":")))).slice(0, 16);
  h[6] = (h[6] & 0x0f) | 0x50; h[8] = (h[8] & 0x3f) | 0x80;
  let n = 0n; h.forEach(b => { n = (n << 8n) | BigInt(b); });
  const out = []; for (let i = 0; i < 22; i++) { out.push(ALFABETO[Number(n % 64n)]); n /= 64n; } return out.reverse().join(""); }

/* texto e número STEP (como s_ e r_ do ifc.py) */
function s_(txt) { if (txt == null) return "$"; let o = "";
  for (const ch of String(txt)) { const c = ch.codePointAt(0);
    if (ch === "'") o += "''"; else if (ch === "\\") o += "\\\\"; else if (c >= 32 && c < 127) o += ch;
    else { let hex = ""; for (let i = 0; i < ch.length; i++) hex += ch.charCodeAt(i).toString(16).toUpperCase().padStart(4, "0"); o += "\\X2\\" + hex + "\\X0\\"; } }
  return "'" + o + "'"; }
function r_(v) { if (v == null) return "$"; v = Number(v); if (!isFinite(v)) return "$";
  const a = Math.abs(v); let t;
  if (v !== 0 && (a < 1e-4 || a >= 1e16)) t = v.toExponential().toUpperCase().replace("E+", "E");   /* repr do Python usa expoente fora de [1e-4, 1e16) */
  else t = Number.isInteger(v) ? v.toFixed(1) : String(v);
  if (t.includes("E")) { let [m, e] = t.split("E"); if (!m.includes(".")) m += "."; return m + "E" + parseInt(e, 10); }
  return t.includes(".") ? t : t + "."; }
const num = v => { const x = Number(v); return v === null || v === undefined || v === "" || !isFinite(x) ? null : x; };

const TIPOS = {
  pv: ["IFCSOLARDEVICE", "SOLARPANEL", "Arranjo fotovoltaico", "Physis_Solar", true],
  modulo_pv: ["IFCSOLARDEVICE", "SOLARPANEL", "Módulo fotovoltaico", "Physis_Solar", false],
  inversor: ["IFCTRANSFORMER", "INVERTER", "Inversor fotovoltaico", "Physis_Inversor", true],
  cisterna: ["IFCTANK", "STORAGE", "Cisterna de água de chuva", "Physis_Agua", false],
  calha: ["IFCPIPESEGMENT", "GUTTER", "Calha", "Physis_Drenagem", false],
  condutor: ["IFCPIPESEGMENT", "RIGIDSEGMENT", "Condutor vertical", "Physis_Drenagem", false],
  avac: ["IFCUNITARYEQUIPMENT", "SPLITSYSTEM", "Equipamento de climatização", "Physis_AVAC", true],
  quadro: ["IFCELECTRICDISTRIBUTIONBOARD", "DISTRIBUTIONBOARD", "Quadro elétrico", "Physis_Quadro", true],
  /* instalações (MEP) de AVAC, 24/11/2026: abrem no Bonsai/FreeCAD como classes nativas do IFC4 */
  chiller: ["IFCCHILLER", "NOTDEFINED", "Chiller", "Physis_AVAC", true],
  bomba: ["IFCPUMP", "NOTDEFINED", "Bomba", "Physis_AVAC", true],
  ventilador: ["IFCFAN", "NOTDEFINED", "Ventilador ou exaustor", "Physis_AVAC", true],
  difusor: ["IFCAIRTERMINAL", "DIFFUSER", "Difusor ou grelha", "Physis_AVAC", false],
  duto: ["IFCDUCTSEGMENT", "RIGIDSEGMENT", "Duto", "Physis_AVAC", false],
  tubo: ["IFCPIPESEGMENT", "RIGIDSEGMENT", "Tubulação", "Physis_AVAC", false],
  torre: ["IFCCOOLINGTOWER", "NOTDEFINED", "Torre de resfriamento", "Physis_AVAC", true],
  tanque: ["IFCTANK", "NOTDEFINED", "Tanque (termoacumulação ou expansão)", "Physis_AVAC", false],
  skid: ["IFCUNITARYEQUIPMENT", "USERDEFINED", "Skid (conjunto montado)", "Physis_AVAC", true],
  valvula: ["IFCVALVE", "NOTDEFINED", "Registro ou válvula", "Physis_AVAC", false],
  filtro: ["IFCFILTER", "NOTDEFINED", "Filtro", "Physis_AVAC", false],
  aquecedor: ["IFCBOILER", "NOTDEFINED", "Aquecedor (passagem, gás ou acumulação)", "Physis_AVAC", true],
  turbina: ["IFCELECTRICGENERATOR", "USERDEFINED", "Microturbina hidráulica", "Physis_Turbina", true],
  biodigestor: ["IFCBUILDINGELEMENTPROXY", "USERDEFINED", "Biodigestor", "Physis_Biodigestor", false],
  canteiro: ["IFCBUILDINGELEMENTPROXY", "USERDEFINED", "Canteiro de viveiro", "Physis_Viveiro", false],
  rack: ["IFCBUILDINGELEMENTPROXY", "USERDEFINED", "Estrutura de fixação (rack)", "Physis_Estrutura", false] };
const UNIDADES = { kwp: "kWp", potencia_kw: "kW", potencia_ca_kw: "kW", volume_m3: "m³", volume_l: "L", secao_mm: "mm", diametro_mm: "mm", largura_mm: "mm", lamina_mm: "mm",
  btu_h: "BTU/h", incl_graus: "°", azim_graus: "°", passo_fileiras_m: "m", area_m2: "m²", vazao_l_min: "L/min", vazao_m3_h: "m³/h", circuitos: "un", modulos: "un",
  energia_kwh_ano: "kWh/ano", biogas_m3_dia: "m³/dia", comprimento_m: "m", massa_g: "g", strings: "un", modulos_por_string: "un", irradiacao_kwh_m2_ano: "kWh/m²·ano", mudas: "un", altura_queda_m: "m" };
const SI = { "m": ["LENGTHUNIT", null, "METRE"], "m²": ["AREAUNIT", null, "SQUARE_METRE"], "m³": ["VOLUMEUNIT", null, "CUBIC_METRE"], "kW": ["POWERUNIT", "KILO", "WATT"],
  "kg": ["MASSUNIT", "KILO", "GRAM"], "g": ["MASSUNIT", null, "GRAM"], "mm": ["LENGTHUNIT", "MILLI", "METRE"] };

function potencias(p, fp) { if (p == null) return { P_kW: null, Q_kvar: null, S_kVA: null, fp };
  if (fp == null || !(fp > 0 && fp <= 1)) return { P_kW: +p, Q_kvar: null, S_kVA: null, fp: null };
  return { P_kW: +p, Q_kvar: +p * Math.tan(Math.acos(fp)), S_kVA: +p / fp, fp: +fp }; }
function carbonoMaterial(mat, base) { const b = base[mat.id], q = mat.quantidade, un = String(mat.unidade || "kg");
  const out = { id: mat.id, nome: b ? b.nome : null, quantidade: q, unidade: un, kg: null, kgco2e: null, fator_kgco2e_kg: null, fonte: null, nota: "" };
  if (!b) { out.nota = "material fora da base sistema/physis-materiais.json"; return out; }
  const ci = b.carbono_incorporado || {}; out.fator_kgco2e_kg = ci.valor == null ? null : ci.valor; out.fonte = ci.fonte == null ? null : ci.fonte;
  if (q == null) return out; const qq = +q; let kg = { kg: qq, t: qq * 1000 }[un]; if (kg === undefined) kg = null;
  if (kg == null && (un === "m3" || un === "m³") && b.densidade) kg = qq * b.densidade;
  if (kg == null && (un === "m2" || un === "m²") && b.densidade && b.espessura_tipica_m) { kg = qq * b.espessura_tipica_m * b.densidade; out.nota = "m² convertido pela espessura típica da base (conferir a espessura do projeto)"; }
  out.kg = kg; if (kg != null && ci.valor != null && String(ci.unidade || "").startsWith("kgCO2e/kg")) out.kgco2e = kg * ci.valor; return out; }

class Escritor {
  constructor(chave) { this.linhas = []; this.chave = chave; this.unidades = {}; }
  add(t) { this.linhas.push(t); return "#" + this.linhas.length; }
  guid(...p) { return s_(guidEstavel(this.chave, ...p)); }
  unidade(un) { if (un in this.unidades) return this.unidades[un]; let ref;
    if (SI[un]) { const [t, pre, nome] = SI[un]; ref = this.add(`IFCSIUNIT(*,.${t}.,${pre ? "." + pre + "." : "$"},.${nome}.)`); }
    else if (un === "°") ref = this.unidades["°"] = this.grau();
    else { const dims = this.unidades._dims || this.add("IFCDIMENSIONALEXPONENTS(0,0,0,0,0,0,0)"); this.unidades._dims = dims; ref = this.add(`IFCCONTEXTDEPENDENTUNIT(${dims},.USERDEFINED.,${s_(un)})`); }
    this.unidades[un] = ref; return ref; }
  grau() { const rad = this.unidades.rad || this.add("IFCSIUNIT(*,.PLANEANGLEUNIT.,$,.RADIAN.)"); this.unidades.rad = rad;
    const dims = this.unidades._dims || this.add("IFCDIMENSIONALEXPONENTS(0,0,0,0,0,0,0)"); this.unidades._dims = dims;
    const m = this.add(`IFCMEASUREWITHUNIT(IFCPLANEANGLEMEASURE(${r_(Math.PI / 180)}),${rad})`); return this.add(`IFCCONVERSIONBASEDUNIT(${dims},.PLANEANGLEUNIT.,'DEGREE',${m})`); }
  ponto(x, y, z) { return this.add(`IFCCARTESIANPOINT((${r_(x)},${r_(y)},${r_(z)}))`); }
  colocacao(rel, x, y, z) { const ax = this.add(`IFCAXIS2PLACEMENT3D(${this.ponto(x || 0, y || 0, z || 0)},$,$)`); return this.add(`IFCLOCALPLACEMENT(${rel || "$"},${ax})`); }
  propriedade(nome, valor, unidade, descricao) { let v, un;
    if (typeof valor === "boolean") { v = `IFCBOOLEAN(.${valor ? "T" : "F"}.)`; un = null; }
    else if (typeof valor === "number" && Number.isInteger(valor) && !valor.__float && (unidade == null || unidade === "un")) { v = `IFCINTEGER(${valor})`; un = null; }
    else if (typeof valor === "number" || valor instanceof Number) { v = `IFCREAL(${r_(+valor)})`; un = unidade; }
    else if (valor == null) { v = "$"; un = unidade; }
    else { v = `IFCLABEL(${s_(String(valor).slice(0, 255))})`; un = null; }
    return this.add(`IFCPROPERTYSINGLEVALUE(${s_(nome)},${descricao ? s_(descricao) : "$"},${v},${un ? this.unidade(un) : "$"})`); }
  pset(oh, nome, props, objetos, chave) { if (!props.length || !objetos.length) return;
    const ps = this.add(`IFCPROPERTYSET(${this.guid("pset", chave, nome)},${oh},${s_(nome)},$,(${props.join(",")}))`);
    this.add(`IFCRELDEFINESBYPROPERTIES(${this.guid("rdp", chave, nome)},${oh},$,$,(${objetos.join(",")}),${ps})`); }
}
const valorUnidade = (k, v) => v && typeof v === "object" && "valor" in v ? [v.valor, v.unidade || UNIDADES[k] || null] : [v, UNIDADES[k] || null];
function dms(v) { const sinal = v < 0 ? -1 : 1, a = Math.abs(v), g = Math.trunc(a), m = Math.trunc((a - g) * 60), s = Math.trunc((a - g - m / 60) * 3600);
  let mi = Math.round(((a - g - m / 60) * 3600 - s) * 1e6), ss = s; if (mi >= 1000000) { ss += 1; mi -= 1000000; }
  const z = x => (x === 0 ? 0 : x); return `(${z(sinal * g)},${z(sinal * m)},${z(sinal * ss)},${z(sinal * mi)})`; }
const pad = n => String(n).padStart(2, "0");

/* d: o mesmo JSON do ifc.escrever; op: { agora (s), materiais: {id: material} (senão a base embutida), premissa(id) } */
function escrever(d, op) { op = op || {};
  if (!d || typeof d !== "object") throw new Error("entrada: objeto JSON");
  const proj = d.projeto || {}, chave = String(proj.id || proj.nome || "projeto"), nomeProj = String(proj.nome || "Projeto Physis").slice(0, 120), site = d.site || {};
  const lat = num(site.lat), lon = num(site.lon);
  if (lat == null || lon == null || !(lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180)) throw new Error("site.lat e site.lon são obrigatórios (o lugar vem do Início/Mapeamento)");
  const elementos = d.elementos || []; if (elementos.length > 5000) throw new Error("elementos demais (máximo 5.000)");
  const prem = d.premissas || {}, premissa = op.premissa || (id => (global.PhysisCalc && global.PhysisCalc.premissa) ? global.PhysisCalc.premissa(id) : null);
  const fpPadrao = PREMISSA_FP in prem ? prem[PREMISSA_FP] : premissa(PREMISSA_FP);
  let mats = op.materiais; if (Array.isArray(d.materiais_base)) { mats = {}; d.materiais_base.forEach(m => { mats[m.id] = m; }); }
  if (!mats) { mats = {}; try { const b = JSON.parse(document.getElementById("base-materiais").textContent); (b.materiais || []).forEach(m => { if (m && m.id) mats[m.id] = m; }); } catch (e) {} }
  const W = new Escritor(chave), t = Math.trunc(op.agora != null ? op.agora : Date.now() / 1000);
  const pe = W.add("IFCPERSON($,$,'Physis',$,$,$,$,$)"), org = W.add("IFCORGANIZATION($,'Physis Engineering',$,$,$)"), po = W.add(`IFCPERSONANDORGANIZATION(${pe},${org},$)`);
  const app = W.add(`IFCAPPLICATION(${org},'0.1','Physis Mapeamento','physis-mapeamento')`), oh = W.add(`IFCOWNERHISTORY(${po},${app},$,.ADDED.,$,$,$,${t})`);
  const origem = W.add(`IFCAXIS2PLACEMENT3D(${W.ponto(0, 0, 0)},$,$)`), norte = W.add("IFCDIRECTION((0.,1.))");
  const ctx = W.add(`IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,${origem},${norte})`);
  const baseUn = ["m", "m²", "m³", "°", "kW", "kg"].map(u => W.unidade(u)), ua = W.add(`IFCUNITASSIGNMENT((${baseUn.join(",")}))`);
  const projeto = W.add(`IFCPROJECT(${W.guid("projeto")},${oh},${s_(nomeProj)},$,$,$,$,(${ctx}),${ua})`);
  const plSite = W.colocacao(null);
  const sitio = W.add(`IFCSITE(${W.guid("site")},${oh},${s_(site.nome || "Terreno")},$,$,${plSite},$,$,.ELEMENT.,${dms(lat)},${dms(lon)},${r_(num(site.altitude_m))},$,$)`);
  W.add(`IFCRELAGGREGATES(${W.guid("agg-proj")},${oh},$,$,${projeto},(${sitio}))`);
  const edifs = d.edificacoes || [{ id: "ed1", nome: "Edificação", pavimentos: [{ id: "terreo", nome: "Térreo", elevacao_m: 0 }] }];
  const pavRef = {}, pavPl = {}, bloco = [];
  edifs.forEach(e => { const eid = String(e.id || e.nome), pl = W.colocacao(plSite);
    const b = W.add(`IFCBUILDING(${W.guid("ed", eid)},${oh},${s_(e.nome || "Edificação")},$,$,${pl},$,$,.ELEMENT.,$,$,$)`); bloco.push(b); const pvs = [];
    (e.pavimentos || [{ id: "terreo", nome: "Térreo", elevacao_m: 0 }]).forEach(p => { const pid = String(p.id || p.nome), el = num(p.elevacao_m) || 0, ppl = W.colocacao(pl, 0, 0, el);
      const st = W.add(`IFCBUILDINGSTOREY(${W.guid("pav", eid, pid)},${oh},${s_(p.nome || pid)},$,$,${ppl},$,$,.ELEMENT.,${r_(el)})`); pvs.push(st);
      if (!(pid in pavRef)) pavRef[pid] = st; if (!(pid in pavPl)) pavPl[pid] = ppl; if (!("_primeiro" in pavRef)) pavRef._primeiro = st; if (!("_primeiro" in pavPl)) pavPl._primeiro = ppl; });
    W.add(`IFCRELAGGREGATES(${W.guid("agg-ed", eid)},${oh},$,$,${b},(${pvs.join(",")}))`); });
  W.add(`IFCRELAGGREGATES(${W.guid("agg-site")},${oh},$,$,${sitio},(${bloco.join(",")}))`);
  const contidos = {}, ordem = [];
  elementos.forEach((el, i) => { const tipo = String(el.tipo || "");
    if (!TIPOS[tipo]) throw new Error(`tipo de elemento desconhecido: ${tipo.slice(0, 30)} (aceitos: ${Object.keys(TIPOS).join(", ")})`);
    const [ent, pre, otype, psnome, eletrico] = TIPOS[tipo], eid = String(el.id || `${tipo}-${i + 1}`), pid = String(el.pavimento || "_primeiro");
    if (!(pid in pavRef)) throw new Error("pavimento desconhecido: " + pid.slice(0, 40));
    const pos = el.posicao || {}, pl = W.colocacao(pavPl[pid], num(pos.x) || 0, num(pos.y) || 0, num(pos.z) || 0);
    let rep = "$"; const cx = el.caixa || {};
    if (["dx", "dy", "dz"].every(k => num(cx[k]) && num(cx[k]) > 0)) { const bb = W.add(`IFCBOUNDINGBOX(${W.ponto(0, 0, 0)},${r_(cx.dx)},${r_(cx.dy)},${r_(cx.dz)})`);
      const sr = W.add(`IFCSHAPEREPRESENTATION(${ctx},'Box','BoundingBox',(${bb}))`); rep = W.add(`IFCPRODUCTDEFINITIONSHAPE($,$,(${sr}))`); }
    const nome = s_(String(el.nome || otype).slice(0, 120)), ot = s_(el.object_type || otype), guid = W.guid("el", eid);
    const ref = W.add(`${ent}(${guid},${oh},${nome},$,${ot},${pl},${rep},${s_(eid)},.${pre}.)`);
    if (!contidos[pid]) { contidos[pid] = []; ordem.push(pid); } contidos[pid].push(ref);
    const props = el.propriedades || {}, lista = [W.propriedade("Origem", String(el.origem || "Physis"))];
    Object.keys(props).forEach(k => { if (k === "fator_potencia") return; const [val, un] = valorUnidade(k, props[k]); lista.push(W.propriedade(k, val, un)); });
    W.pset(oh, psnome, lista, [ref], eid);
    const pkw = props.potencia_kw != null ? num(valorUnidade("potencia_kw", props.potencia_kw)[0]) : (tipo === "pv" ? num(valorUnidade("kwp", props.kwp)[0]) : null);
    if (eletrico || pkw != null) { const fpProj = num(props.fator_potencia), fp = fpProj != null ? fpProj : num(fpPadrao), pq = potencias(pkw, fp);
      const orig = fpProj != null ? "projeto" : fp != null ? "premissa " + PREMISSA_FP : `[CONFERIR] premissa ${PREMISSA_FP} ainda não existe na base: fator, Q e S ficam vazios`;
      W.pset(oh, "Physis_Eletrica", [W.add(`IFCPROPERTYSINGLEVALUE('FatorPotencia',${s_(orig)},${pq.fp != null ? "IFCRATIOMEASURE(" + r_(pq.fp) + ")" : "$"},$)`),
        W.propriedade("PotenciaAtiva", flt(pq.P_kW), "kW"), W.propriedade("PotenciaReativa", flt(pq.Q_kvar), "kvar"), W.propriedade("PotenciaAparente", flt(pq.S_kVA), "kVA")], [ref], eid); }
    const mlist = el.materiais || [];
    if (mlist.length) { const cs = [], mp = []; let tot = 0;
      mlist.forEach(m => { const c = carbonoMaterial(m, mats), mat = W.add(`IFCMATERIAL(${s_(c.nome || m.id)},$,${s_((mats[m.id] || {}).grupo)})`);
        cs.push(W.add(`IFCMATERIALCONSTITUENT(${s_(m.id)},$,${mat},$,$)`));
        mp.push(W.propriedade(m.id + ".quantidade", flt(num(c.quantidade)), c.unidade.replace("m3", "m³").replace("m2", "m²")));
        mp.push(W.propriedade(m.id + ".carbono", flt(c.kgco2e), "kgCO2e", c.fonte || c.nota || null)); tot += c.kgco2e || 0; });
      const mset = W.add(`IFCMATERIALCONSTITUENTSET(${s_("Materiais " + eid)},$,(${cs.join(",")}))`);
      W.add(`IFCRELASSOCIATESMATERIAL(${W.guid("mat", eid)},${oh},$,$,(${ref}),${mset})`);
      mp.push(W.propriedade("CarbonoIncorporadoTotal", flt(tot), "kgCO2e", "soma dos materiais com fator na base")); W.pset(oh, "Physis_Materiais", mp, [ref], eid); }
    const memo = el.memorial || {};
    if (memo.id || memo.uri) { const dr = W.add(`IFCDOCUMENTREFERENCE(${s_(memo.uri)},${s_(memo.id)},${s_(memo.nome || "Memorial")},$,$)`);
      W.add(`IFCRELASSOCIATESDOCUMENT(${W.guid("doc", eid)},${oh},$,$,(${ref}),${dr})`); }
    const filhos = (el.modulos || []).map((mo, k) => { const mpl = W.colocacao(pavPl[pid], num(mo.x) || 0, num(mo.y) || 0, num(mo.z) || 0);
      return W.add(`IFCSOLARDEVICE(${W.guid("mod", eid, k)},${oh},${s_("Módulo " + (k + 1))},$,${s_("Módulo fotovoltaico")},${mpl},$,${s_(eid + "-m" + (k + 1))},.SOLARPANEL.)`); });
    if (filhos.length) W.add(`IFCRELAGGREGATES(${W.guid("agg-mod", eid)},${oh},$,$,${ref},(${filhos.join(",")}))`); });
  ordem.forEach(pid => W.add(`IFCRELCONTAINEDINSPATIALSTRUCTURE(${W.guid("cont", pid)},${oh},$,$,(${contidos[pid].join(",")}),${pavRef[pid]})`));
  const dt = new Date(t * 1000), data = `${dt.getUTCFullYear()}-${pad(dt.getUTCMonth() + 1)}-${pad(dt.getUTCDate())}T${pad(dt.getUTCHours())}:${pad(dt.getUTCMinutes())}:${pad(dt.getUTCSeconds())}`;
  const arq = nomeProj.replace(/[^A-Za-z0-9_.-]/g, "_").slice(0, 60) + ".ifc";
  const cab = ["ISO-10303-21;", "HEADER;", "FILE_DESCRIPTION(('ViewDefinition [ReferenceView_V1.2]'),'2;1');",
    `FILE_NAME(${s_(arq)},'${data}',('Physis'),('Physis Engineering'),'Physis Mapeamento 0.1','Physis Sistema','');`, "FILE_SCHEMA(('IFC4'));", "ENDSEC;", "DATA;"];
  return cab.concat(W.linhas.map((x, i) => `#${i + 1}=${x};`), ["ENDSEC;", "END-ISO-10303-21;", ""]).join("\n"); }
/* valores calculados (float no Python) vão sempre como IFCREAL, mesmo inteiros */
function flt(v) { if (v == null) return null; const o = new Number(v); return o; }

/* ═══ Leitor mínimo (o mesmo resumo do ifc.ler) ═══ */
function instancias(dados) { const i = dados.indexOf("DATA;"); if (i < 0) throw new Error("arquivo IFC sem seção DATA");
  const fim = dados.lastIndexOf("ENDSEC;"), corpo = dados.slice(i + 5, fim > i ? fim : dados.length), out = new Map(); let atual = "", aspas = false;
  for (let j = 0; j < corpo.length; j++) { const c = corpo[j];
    if (c === "'") { if (aspas && corpo[j + 1] === "'") { atual += "''"; j++; continue; } aspas = !aspas; }
    if (c === ";" && !aspas) { const m = /^#(\d+)\s*=\s*([A-Za-z0-9_]+)\s*\(([\s\S]*)\)\s*$/.exec(atual.trim()); atual = ""; if (m) out.set(+m[1], [m[2].toUpperCase(), m[3]]); }
    else atual += c; }
  return out; }
const textoStep = s => s.replace(/\\X2\\([0-9A-Fa-f]+)\\X0\\/g, (_, h) => { let r = ""; for (let i = 0; i < h.length; i += 4) r += String.fromCharCode(parseInt(h.slice(i, i + 4), 16)); return r; }).replace(/\\\\/g, "\\");
function argumentos(s0) { const s = s0 + ")"; let pos = 0; const ws = () => { while (" \r\n\t".includes(s[pos])) pos++; };
  function valor() { ws(); const c = s[pos];
    if (c === "(") { pos++; const l = []; for (;;) { ws(); if (s[pos] === ")") { pos++; return l; } l.push(valor()); ws(); if (s[pos] === ",") pos++; } }
    if (c === "'") { let j = pos + 1, b = ""; for (;;) { if (s[j] === "'") { if (s[j + 1] === "'") { b += "'"; j += 2; continue; } break; } b += s[j]; j++; } pos = j + 1; return textoStep(b); }
    if (c === "#") { const m = /^#(\d+)/.exec(s.slice(pos)); pos += m[0].length; return { ref: +m[1] }; }
    if (c === "$" || c === "*") { pos++; return null; }
    if (c === ".") { const j = s.indexOf(".", pos + 1), v = s.slice(pos + 1, j); pos = j + 1; return { enum: v }; }
    let m = /^[A-Za-z_][A-Za-z0-9_]*/.exec(s.slice(pos)); if (m) { pos += m[0].length; return { tipo: m[0].toUpperCase(), valor: valor() }; }
    m = /^[-+0-9.Ee]+/.exec(s.slice(pos)); pos += m[0].length; return /[.Ee]/.test(m[0]) ? parseFloat(m[0]) : parseInt(m[0], 10); }
  const out = []; for (;;) { while (pos < s.length && " \r\n\t".includes(s[pos])) pos++; if (s[pos] === ")") return out; out.push(valor()); ws(); if (s[pos] === ",") pos++; } }
const grauDms = v => Array.isArray(v) && v.length >= 3 ? v[0] + v[1] / 60 + v[2] / 3600 + (v.length > 3 ? v[3] : 0) / 3.6e9 : null;
function ler(txt) { txt = String(txt || ""); if (txt.length > 50 * 1024 * 1024) throw new Error("IFC grande demais para o leitor básico (máximo 50 MB)");
  if (!txt.trimStart().startsWith("ISO-10303-21;")) throw new Error("não é um arquivo IFC em texto STEP (ISO-10303-21)");
  const esq = /FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'/.exec(txt), ins = instancias(txt), cache = new Map();
  const a = n => { if (!cache.has(n)) cache.set(n, argumentos(ins.get(n)[1])); return cache.get(n); }, ref = v => v && typeof v === "object" && "ref" in v ? v.ref : null;
  function origem(pl, prof) { prof = prof || 0; if (pl == null || prof > 50 || !ins.has(pl) || ins.get(pl)[0] !== "IFCLOCALPLACEMENT") return [0, 0, 0];
    const ar = a(pl), base = origem(ref(ar[0]), prof + 1), ax = ref(ar[1]); let p = [0, 0, 0];
    if (ins.has(ax) && ins.get(ax)[0].startsWith("IFCAXIS2PLACEMENT")) { const pt = ref(a(ax)[0]); if (ins.has(pt) && ins.get(pt)[0] === "IFCCARTESIANPOINT") { const c = a(pt)[0].concat([0, 0, 0]); p = [+c[0], +c[1], +c[2]]; } }
    return [0, 1, 2].map(i => base[i] + p[i]); }
  const porTipo = {}, tipos = {}; ins.forEach(([t]) => { tipos[t] = (tipos[t] || 0) + 1; });
  let projeto = null; for (const [n, [t]] of ins) if (t === "IFCPROJECT") { projeto = a(n)[2]; break; }
  const sites = [], edifs = [], pavs = [];
  ins.forEach(([t], n) => { if (t === "IFCSITE") sites.push({ nome: a(n)[2], lat: grauDms(a(n)[9]), lon: grauDms(a(n)[10]), altitude_m: a(n)[11] });
    if (t === "IFCBUILDING") edifs.push({ nome: a(n)[2] }); if (t === "IFCBUILDINGSTOREY") pavs.push({ nome: a(n)[2], elevacao_m: a(n).length > 9 ? a(n)[9] : null }); });
  const mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity]; let nEl = 0;
  ins.forEach(([t], n) => { if (t !== "IFCRELCONTAINEDINSPATIALSTRUCTURE") return;
    (a(n)[4] || []).forEach(e0 => { const e = ref(e0); if (!ins.has(e)) return; const te = ins.get(e)[0]; porTipo[te] = (porTipo[te] || 0) + 1; nEl++;
      const ae = a(e), o = origem(ae.length > 5 ? ref(ae[5]) : null); let dims = [0, 0, 0]; const rp = ae.length > 6 ? ref(ae[6]) : null;
      if (ins.has(rp) && ins.get(rp)[0] === "IFCPRODUCTDEFINITIONSHAPE") (a(rp)[2] || []).forEach(sr0 => { const sr = ref(sr0);
        if (ins.has(sr) && ins.get(sr)[0] === "IFCSHAPEREPRESENTATION") (a(sr)[3] || []).forEach(it0 => { const it = ref(it0); if (ins.has(it) && ins.get(it)[0] === "IFCBOUNDINGBOX") { const b = a(it); dims = [+b[1], +b[2], +b[3]]; } }); });
      for (let k = 0; k < 3; k++) { mn[k] = Math.min(mn[k], o[k]); mx[k] = Math.max(mx[k], o[k] + dims[k]); } }); });
  let unidade = "m"; ins.forEach(([t], n) => { if (t !== "IFCSIUNIT") return; const x = a(n); if (x[1] && x[1].enum === "LENGTHUNIT" && x[2] && x[2].enum) unidade = { MILLI: "mm", CENTI: "cm" }[x[2].enum] || unidade; });
  const ord = {}; Object.keys(porTipo).sort().forEach(k => { ord[k] = porTipo[k]; });
  return { esquema: esq ? esq[1] : null, projeto, entidades: ins.size, terrenos: sites, edificacoes: edifs, pavimentos: pavs, elementos: nEl, elementos_por_tipo: ord,
    caixa: nEl ? { min: mn, max: mx, unidade, nota: "origens das peças mais IfcBoundingBox, sem rotações" } : null, tipos }; }


/* Espaços (IfcSpace) com área e altura, para preencher os cálculos sozinho (24/11/2026). Ordem de confiança: quantidade
   (IfcQuantityArea NetFloorArea/GrossFloorArea), propriedade (área em Pset) e geometria (perfil retangular ou poligonal extrudado).
   Sem nenhuma das três, a área fica null (nada é inventado). */
function espacos(txt) {
  txt = String(txt || ""); if (!txt.trimStart().startsWith("ISO-10303-21;")) throw new Error("não é um arquivo IFC em texto STEP (ISO-10303-21)");
  const ins = instancias(txt), cache = new Map();
  const a = n => { if (!cache.has(n)) cache.set(n, argumentos(ins.get(n)[1])); return cache.get(n); }, ref = v => v && typeof v === "object" && "ref" in v ? v.ref : null;
  const tipo = n => ins.has(n) ? ins.get(n)[0] : "", numv = v => typeof v === "number" ? v : (v && typeof v === "object" && typeof v.valor === "number" ? v.valor : v && typeof v === "object" && Array.isArray(v.valor) && typeof v.valor[0] === "number" ? v.valor[0] : (v && typeof v === "object" && Array.isArray(v.args) && typeof v.args[0] === "number" ? v.args[0] : null));
  let fL = 1, fA = 1; ins.forEach(([t], n) => { if (t !== "IFCSIUNIT") return; const x = a(n), pre = x[2] && x[2].enum, k = { MILLI: 1e-3, CENTI: 1e-2, DECI: 1e-1 }[pre] || 1;
    if (x[1] && x[1].enum === "LENGTHUNIT") fL = k; if (x[1] && x[1].enum === "AREAUNIT") fA = k * k; });
  const rels = []; ins.forEach(([t], n) => { if (t === "IFCRELDEFINESBYPROPERTIES") rels.push(n); });
  const props = {}; rels.forEach(n => { const x = a(n), def = ref(x[5]); (x[4] || []).forEach(o => { const id = ref(o); (props[id] = props[id] || []).push(def); }); });
  function areaQtd(id) { let net = null, gross = null;
    (props[id] || []).forEach(d => { if (tipo(d) !== "IFCELEMENTQUANTITY") return; (a(d)[5] || []).forEach(q0 => { const q = ref(q0); if (tipo(q) !== "IFCQUANTITYAREA") return; const x = a(q), nm = String(x[0] || "").toLowerCase(), v = numv(x[3]);
      if (v == null) return; if (/net/.test(nm)) net = v * fA; else if (/gross|area/.test(nm) && gross == null) gross = v * fA; }); });
    return net != null ? net : gross; }
  function areaProp(id) { let v = null;
    (props[id] || []).forEach(d => { if (tipo(d) !== "IFCPROPERTYSET") return; (a(d)[4] || []).forEach(p0 => { const p = ref(p0); if (tipo(p) !== "IFCPROPERTYSINGLEVALUE") return; const x = a(p), nm = String(x[0] || "").toLowerCase();
      if (v == null && /area|área/.test(nm) && !/perim/.test(nm)) { const val = x[2]; if (val && typeof val === "object" && /AREAMEASURE/.test(val.tipo || "")) v = numv(val) * fA; else if (typeof numv(val) === "number" && /area/.test(nm)) v = numv(val) * fA; } }); });
    return v; }
  function poligono(pts) { let s = 0; for (let i = 0; i < pts.length; i++) { const p = pts[i], q = pts[(i + 1) % pts.length]; s += p[0] * q[1] - q[0] * p[1]; } return Math.abs(s) / 2; }
  function geom(id) { const x = a(id), rp = x.length > 6 ? ref(x[6]) : null; let area = null, alt = null;
    if (tipo(rp) !== "IFCPRODUCTDEFINITIONSHAPE") return { area, alt };
    (a(rp)[2] || []).forEach(sr0 => { const sr = ref(sr0); if (tipo(sr) !== "IFCSHAPEREPRESENTATION") return;
      (a(sr)[3] || []).forEach(it0 => { const it = ref(it0); if (tipo(it) !== "IFCEXTRUDEDAREASOLID" || area != null) return; const ex = a(it), pf = ref(ex[0]); alt = numv(ex[3]) != null ? numv(ex[3]) * fL : null;
        if (tipo(pf) === "IFCRECTANGLEPROFILEDEF") { const p = a(pf); area = numv(p[3]) * numv(p[4]) * fL * fL; }
        else if (tipo(pf) === "IFCARBITRARYCLOSEDPROFILEDEF") { const c = ref(a(pf)[2]); if (tipo(c) === "IFCPOLYLINE") { const pts = (a(c)[0] || []).map(r => a(ref(r))[0]).filter(Array.isArray); if (pts.length >= 3) area = poligono(pts) * fL * fL; } } }); });
    return { area, alt }; }
  const out = []; ins.forEach(([t], n) => { if (t !== "IFCSPACE") return; const x = a(n), q = areaQtd(n), pr = q == null ? areaProp(n) : null, g = geom(n);
    const area = q != null ? q : pr != null ? pr : g.area;
    out.push({ nome: String(x[2] || ""), nome_longo: String(x[7] || ""), area_m2: area == null ? null : Math.round(area * 100) / 100, altura_m: g.alt == null ? null : Math.round(g.alt * 100) / 100,
      fonte: q != null ? "quantidade do IFC" : pr != null ? "propriedade do IFC" : g.area != null ? "geometria do IFC" : "sem área no IFC" }); });
  /* sem IfcSpace (ex.: IFC do gêmeo da Casa Physis, que modela as edificações como elementos): usa os elementos de edificação
     pelo ObjectType, com a área da propriedade (AreaPlanilha) ou da geometria */
  if (!out.length) { const EDIF = { deposito:"técnico", edicula:"edícula", escritorio:"escritório", hospedagem:"hospedagem", residencia:"residência", restaurante:"restaurante", piscina:"piscina", estacionamento:"garagem" };
    ins.forEach(([t], n) => { if (t !== "IFCBUILDINGELEMENTPROXY") return; const x = a(n), ot = String(x[4] || "").toLowerCase(); if (!(ot in EDIF)) return;
      const pr = areaProp(n), g = geom(n), area = pr != null ? pr : g.area;
      out.push({ nome: String(x[2] || ""), nome_longo: String(x[2] || ""), tipo: EDIF[ot], area_m2: area == null ? null : Math.round(area * 100) / 100, altura_m: g.alt == null ? null : Math.round(g.alt * 100) / 100,
        fonte: pr != null ? "propriedade do IFC (elemento " + ot + ")" : g.area != null ? "geometria do IFC (elemento " + ot + ")" : "sem área no IFC" }); }); }
  return out; }
global.PhysisIFC = { escrever, ler, espacos, guidEstavel, s_, r_, TIPOS, sha1 };
})(typeof window !== "undefined" ? window : this);
