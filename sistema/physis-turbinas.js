/* physis-turbinas.js — aba Turbinas da plataforma, com duas partes: Hidráulica e Eólica.
   Contrato com a plataforma: define telaTurbinas() (HTML da aba inteira, com o único título h1) e
   window.TURBINAS = { hidraulica(params), eolica(params), ... } (funções puras, testáveis).
   Espelho de physis-hub/physis_hub/vento.py (mesmas fórmulas e constantes; teste em tests/test_turbinas.py).
   Globais usadas só na hora de desenhar: esc, n2, numBr, brl, el, ui, desenhar; e, se existirem, calcLer, calcGravar,
   gisLugar, gisX, carbCalc, carbLer, analiseInvest. Estado: calcLer("turb") (hidráulica, chaves antigas mantidas)
   e calcLer("turb-eol") (eólica); parte aberta em ui.turbSub. Dado do vento: GET api/gis/vento (guardado no servidor).
   Faixas e modelos marcados "verificar" são referências de literatura ou classes genéricas, não catálogo de fabricante. */
(function () {
"use strict";

/* ════════ Constantes (as mesmas do vento.py) ════════ */
const DIAS_MES = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const G = 9.81, BETZ = 16 / 27, NU_AGUA = 1.004e-6;
/* α da lei de potência por terreno (Masters, 2004, tabela 7.3) */
const ALFA_TERRENO = { agua:[0.10, "Água calma ou terreno liso e duro"], aberto:[0.15, "Campo aberto, grama alta"], rural:[0.20, "Lavoura alta, cercas vivas e arbustos"],
  floresta:[0.25, "Mata densa"], cidade_pequena:[0.30, "Cidade pequena com árvores e arbustos"], urbano:[0.40, "Cidade com prédios altos"] };
/* faixas típicas (queda m, vazão m³/s, eficiência) em micro e mini centrais — ESHA 2004; Paish 2002. Verificar com o fabricante. */
const TIPOS_HIDRO = [["pelton", "Pelton", [30, 1000], [0.002, 5], [0.80, 0.90]], ["turgo", "Turgo", [20, 300], [0.005, 5], [0.80, 0.85]],
  ["francis", "Francis", [10, 350], [0.05, 50], [0.80, 0.92]], ["kaplan", "Kaplan ou hélice", [2, 30], [0.1, 50], [0.80, 0.90]],
  ["banki", "Michell-Banki (fluxo cruzado)", [3, 200], [0.01, 10], [0.65, 0.80]], ["pat", "Bomba funcionando como turbina", [5, 100], [0.002, 0.5], [0.50, 0.75]]];
/* rugosidade ε (mm) e C de Hazen-Williams de tubo novo (Moody; Porto, Hidráulica Básica). Verificar com o fabricante do tubo. */
const TUBOS = { pvc:[0.0015, 150, "PVC"], pead:[0.007, 140, "PEAD (polietileno)"], aco:[0.045, 120, "Aço"], ferro:[0.26, 100, "Ferro fundido"], concreto:[0.3, 120, "Concreto"] };
/* classes genéricas de turbinas eólicas pequenas: NÃO são modelos comerciais; conferir a curva do fabricante */
const PRESETS_EOL = [
  { id:"g1", nome:"Classe 1 kW (genérica, verificar)", diametro:2.5, p_nom:1, v_in:3, v_nom:11, v_out:25, cp:0.30 },
  { id:"g3", nome:"Classe 3 kW (genérica, verificar)", diametro:4, p_nom:3, v_in:3, v_nom:11, v_out:25, cp:0.30 },
  { id:"g5", nome:"Classe 5 kW (genérica, verificar)", diametro:5.5, p_nom:5, v_in:3, v_nom:11, v_out:25, cp:0.30 },
  { id:"g10", nome:"Classe 10 kW (genérica, verificar)", diametro:7.5, p_nom:10, v_in:3, v_nom:11, v_out:25, cp:0.30 },
  { id:"g20", nome:"Classe 20 kW (genérica, verificar)", diametro:10.5, p_nom:20, v_in:3, v_nom:11, v_out:25, cp:0.30 }];

/* ════════ Contas do vento ════════ */
function gama(z) { /* aproximação de Lanczos (g = 7) */
  if (z < 0.5) return Math.PI / (Math.sin(Math.PI * z) * gama(1 - z));
  z -= 1; const c = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059, 12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
  let x = c[0]; for (let i = 1; i < 9; i++) x += c[i] / (z + i); const t = z + 7.5; return Math.sqrt(2 * Math.PI) * Math.pow(t, z + 0.5) * Math.exp(-t) * x; }
/* ρ = p/(R·T), p = 101325·(1 − 2,25577·10⁻⁵·h)^5,25588 */
const densidadeAr = (alt, tC) => 101325 * Math.pow(1 - 2.25577e-5 * (alt || 0), 5.25588) / (287.05 * ((tC == null ? 15 : tC) + 273.15));
const cisalhamento = (vRef, hRef, h, alfa) => vRef * Math.pow(h / hRef, alfa);
const alfaMedido = (v10, v50) => (v10 > 0 && v50 > 0) ? Math.log(v50 / v10) / Math.log(50 / 10) : null;
const weibullC = (vm, k) => vm / gama(1 + 1 / k);
const weibullPdf = (v, k, c) => (v < 0 || c <= 0) ? 0 : (k / c) * Math.pow(v / c, k - 1) * Math.exp(-Math.pow(v / c, k));
const weibullCdf = (v, k, c) => (v <= 0 || c <= 0) ? 0 : 1 - Math.exp(-Math.pow(v / c, k));
function turbinaEolica(diametro, cp, vIn, vNom, vOut, pNom, rho) {
  cp = Math.max(0, Math.min(cp == null ? 0.30 : cp, BETZ)); rho = rho || 1.225; const area = Math.PI * diametro * diametro / 4;
  if (!pNom && vNom) pNom = 0.5 * rho * area * Math.pow(vNom, 3) * cp / 1000;
  return { area, cp, v_in:vIn || 0, v_nom:vNom || null, v_out:vOut || null, p_nom:pNom || null, rho }; }
/* curva de potência do fabricante (IEC 61400-12-1): pares [v (m/s), kW] em ordem; interpolação linear entre os pontos,
   zero antes do primeiro e depois do último (ou do corte). Na densidade em que o fabricante mediu (sem correção aqui). */
function curvaFabricante(c) { if (!Array.isArray(c)) return null; const l = c.filter(x => Array.isArray(x) && x.length >= 2 && isFinite(x[0]) && isFinite(x[1]) && x[1] >= 0).map(x => [+x[0], +x[1]]).sort((a, b) => a[0] - b[0]);
  return l.length >= 2 ? l : null; }
function potenciaCurva(v, c) { if (v < c[0][0] || v > c[c.length - 1][0]) return 0;
  for (let i = 1; i < c.length; i++) if (v <= c[i][0]) { const [v0, p0] = c[i - 1], [v1, p1] = c[i]; return v1 === v0 ? p1 : p0 + (p1 - p0) * (v - v0) / (v1 - v0); }
  return 0; }
function potenciaVento(v, t) { /* kW: ½·ρ·A·v³·Cp entre a partida e a nominal; nominal até o corte; zero fora. Com a curva do fabricante, a curva. */
  if (t.curva) return t.v_out && v >= t.v_out ? 0 : potenciaCurva(v, t.curva);
  if (v < t.v_in || (t.v_out && v >= t.v_out)) return 0;
  if (t.p_nom && t.v_nom && v >= t.v_nom) return t.p_nom;
  const p = 0.5 * t.rho * t.area * v * v * v * t.cp / 1000; return t.p_nom ? Math.min(p, t.p_nom) : p; }
function energiaWeibull(t, k, c, horas, passo, vMax) { /* kWh = horas·∫P(v)f(v)dv, ponto médio */
  horas = horas == null ? 8760 : horas; passo = passo || 0.05; vMax = vMax || 40; const n = Math.round(vMax / passo); let s = 0;
  for (let i = 0; i < n; i++) { const v = (i + 0.5) * passo; s += potenciaVento(v, t) * weibullPdf(v, k, c); } return s * passo * horas; }

function invest(custo, ganhoMes, vida, taxa, infl) {
  const f = (typeof window !== "undefined" && typeof window.analiseInvest === "function") ? window.analiseInvest : (typeof analiseInvest === "function" ? analiseInvest : null);
  if (!f || !(custo > 0) || !(ganhoMes > 0)) return null; return f(custo, ganhoMes, vida == null ? 20 : vida, taxa == null ? 10 : taxa, infl == null ? 4 : infl); }

/* Espelho de vento.eolica. Parâmetros numéricos; veja vento.py para a lista. */
function eolica(p) { p = p || {}; const g = (k, d) => (p[k] == null || p[k] === "" || (typeof p[k] === "number" && !isFinite(p[k]))) ? d : p[k], avisos = [];
  const rho = densidadeAr(g("altitude", 0), g("temperatura", 25));
  let alfa = g("alfa", null); if (alfa == null) { if (!ALFA_TERRENO[g("terreno", "aberto")]) avisos.push('Terreno não reconhecido: usado "aberto" (α 0,15)'); alfa = (ALFA_TERRENO[g("terreno", "aberto")] || ALFA_TERRENO.aberto)[0]; }
  if (alfa >= 0.30 && (g("v_ref", 0) || 0) > 0) avisos.push("Terreno rugoso (α ≥ 0,30): o vento de referência precisa ser medido no próprio local; dado de estação em campo aberto superestima a energia");
  const hRef = g("h_ref", 10), h = g("altura_cubo", 12), cpIn = g("cp", 0.30);
  if (cpIn > BETZ) avisos.push("Cp acima do limite de Betz (0,593): usado 0,593");
  if (cpIn <= 0 && !p.curva) avisos.push("Cp zero ou negativo: a turbina não gera energia");
  if ((g("diametro", 0) || 0) <= 0 && !p.curva) avisos.push("Diâmetro do rotor não informado ou zero: energia zero");
  const t = turbinaEolica(g("diametro", 0), cpIn, g("v_in", 0), g("v_nom", null), g("v_out", null), g("p_nom", null), rho), cf = curvaFabricante(p.curva);
  if (cf) { t.curva = cf; t.p_nom = Math.max(...cf.map(x => x[1])); }
  const k = g("k", 2) || 2, vRef = g("v_ref", 0) || 0, vCubo = vRef > 0 ? cisalhamento(vRef, hRef, h, alfa) : 0, perdas = Math.max(0, Math.min(g("perdas", 0), 100)) / 100;
  let meses = null, aep;
  const mr = p.meses_ref;
  if (Array.isArray(mr) && mr.length === 12 && mr.every(x => typeof x === "number" && x > 0)) {
    meses = mr.map((vm, i) => { const vc = cisalhamento(vm, hRef, h, alfa); return { mes:i + 1, v_cubo:vc, kwh:energiaWeibull(t, k, weibullC(vc, k), DIAS_MES[i] * 24) * (1 - perdas) }; });
    aep = meses.reduce((s, m) => s + m.kwh, 0);
  } else aep = vCubo > 0 ? energiaWeibull(t, k, weibullC(vCubo, k)) * (1 - perdas) : 0;
  const c = vCubo > 0 ? weibullC(vCubo, k) : 0, fc = t.p_nom ? aep / (t.p_nom * 8760) : null;
  let viab = vCubo < 4 ? ["pouco_viavel", "Pouco viável: vento médio abaixo de 4 m/s na altura do cubo"]
    : vCubo < 5 ? ["marginal", "Marginal: entre 4 e 5 m/s; só com medição no local e custo baixo"]
    : ["viavel", "Viável a confirmar: 5 m/s ou mais na altura do cubo; confirmar com medição no local"];
  if (fc != null && fc < 0.10 && viab[0] === "viavel") viab = ["marginal", "Marginal: fator de capacidade abaixo de 10%"];
  const inv = (g("custo", 0) && g("tarifa", 0) && aep > 0) ? invest(g("custo", 0), aep / 12 * g("tarifa", 0), g("vida", 20), g("taxa", 10), g("infl", 4)) : null;
  if (inv && inv.vpl != null && inv.vpl < 0 && viab[0] === "viavel") viab = ["marginal", "Marginal: há vento, mas o investimento não se paga (VPL negativo) nas premissas informadas"];
  const vmax = Math.max(26, Math.ceil((t.v_out || 25) + 1)), curva = [];
  for (let v = 0; v <= vmax; v++) curva.push({ v, kw:potenciaVento(v, t), horas:c > 0 ? (weibullCdf(v + 0.5, k, c) - weibullCdf(Math.max(0, v - 0.5), k, c)) * 8760 : 0 });
  return { rho, alfa, v_cubo:vCubo, k, c, area:t.area, cp:t.cp, p_nom:t.p_nom, aep_kwh:aep, fc, meses, curva, curva_fabricante:!!cf, viabilidade:viab[0], mensagem:viab[1],
    invest:inv, avisos }; }

/* ════════ Contas da água ════════ */
const potenciaHidraulica = (q, h, eta) => 1000 * G * (q / 3600) * h * eta / 1000;   /* kW, Q em m³/h */
function perdaDarcy(q, dmm, L, rug, kLocal) { /* Darcy-Weisbach + Swamee-Jain; 64/Re abaixo de Re 2000 */
  const Q = q / 3600, d = dmm / 1000; if (!(Q > 0) || !(d > 0)) return { hf:0, v:0, re:0, f:null };
  const v = Q / (Math.PI * d * d / 4), re = v * d / NU_AGUA, f = re < 2000 ? 64 / re : 0.25 / Math.pow(Math.log10(rug / 1000 / (3.7 * d) + 5.74 / Math.pow(re, 0.9)), 2), hv = v * v / (2 * G);
  return { hf:f * L / d * hv + (kLocal || 0) * hv, v, re, f }; }
function perdaHazen(q, dmm, L, C, kLocal) { /* hf = 10,67·L·Q^1,852/(C^1,852·D^4,87) */
  const Q = q / 3600, d = dmm / 1000; if (!(Q > 0) || !(d > 0)) return { hf:0, v:0 };
  const v = Q / (Math.PI * d * d / 4); return { hf:10.67 * L * Math.pow(Q, 1.852) / (Math.pow(C, 1.852) * Math.pow(d, 4.87)) + (kLocal || 0) * v * v / (2 * G), v }; }
function sugerirTipos(H, qM3h) { const q = qM3h / 3600; if (!(H > 0) || !(q > 0)) return [];
  const ln = Math.log, r = TIPOS_HIDRO.map(([id, nome, [h0, h1], [q0, q1], eta]) => {
    const ch = Math.abs(ln(H) - (ln(h0) + ln(h1)) / 2) / ((ln(h1) - ln(h0)) / 2), cq = Math.abs(ln(q) - (ln(q0) + ln(q1)) / 2) / ((ln(q1) - ln(q0)) / 2);
    return { id, nome, dentro:h0 <= H && H <= h1 && q0 <= q && q <= q1, nota:Math.max(ch, cq), eta, queda:[h0, h1], vazao_m3s:[q0, q1] }; });
  return r.sort((a, b) => (a.dentro === b.dentro ? a.nota - b.nota : a.dentro ? -1 : 1)); }
/* Espelho de vento.hidraulica */
function hidraulica(p) { p = p || {}; const g = (k, d) => (p[k] == null || p[k] === "" || (typeof p[k] === "number" && !isFinite(p[k]))) ? d : p[k];
  /* vazão ecológica (remanescente no rio), definida pelo órgão gestor na outorga: sai da vazão disponível; sem ela, só o aviso */
  const qEco = Math.max(0, g("vazao_ecologica", 0) || 0), qd = Math.max(0, g("vazao", 0) - qEco), bruta = p.un === "bar" ? g("queda", 0) * 10.2 : g("queda", 0), eta = g("eta", 0.6), horas = g("horas", 12), n = g("n", 1);
  const tubo = p.tubo || {}, mat = TUBOS[tubo.material || "pvc"] || TUBOS.pvc;
  const perda = q => (p.pressao_dinamica || !tubo.diametro_mm || !tubo.comprimento_m) ? { hf:0, v:0 }
    : tubo.metodo === "hazen" ? perdaHazen(q, tubo.diametro_mm, tubo.comprimento_m, mat[1], tubo.k_local || 0) : perdaDarcy(q, tubo.diametro_mm, tubo.comprimento_m, mat[0], tubo.k_local || 0);
  const pd = perda(qd), liquida = Math.max(0, bruta - pd.hf), kw = potenciaHidraulica(qd, liquida, eta), vm = p.vazoes_mes;
  const usaMes = Array.isArray(vm) && vm.length === 12 && vm.every(x => typeof x === "number" && x >= 0);
  const meses = DIAS_MES.map((dias, i) => { const q = usaMes ? Math.min(Math.max(0, vm[i] - qEco), qd) : qd, hl = Math.max(0, bruta - perda(q).hf), pk = potenciaHidraulica(q, hl, eta);
    return { mes:i + 1, vazao:q, kw:pk * n, kwh:pk * horas * dias * n }; });
  const kwh = meses.reduce((s, m) => s + m.kwh, 0), avisos = [];
  if (bruta > 0 && pd.hf / bruta > 0.10) avisos.push("perda na tubulação acima de 10% da queda: aumente o diâmetro");
  if ((pd.v || 0) > 3) avisos.push("velocidade na tubulação acima de 3 m/s: risco de golpe de aríete e desgaste");
  const outorga = "Usar a água do rio para gerar energia exige outorga de direito de uso (Lei 9.433/1997) da ANA ou do órgão estadual e licença ambiental; a outorga fixa a vazão ecológica, que tem de continuar no rio." + (qEco > 0 ? "" : " Vazão ecológica não informada: a conta usa toda a vazão digitada [MARCADOR: valor do órgão gestor].");
  return { queda_bruta:bruta, perda_m:pd.hf, queda_liquida:liquida, velocidade:pd.v || 0, kw, kw_total:kw * n, kwh_ano:kwh, meses, tipos:sugerirTipos(liquida, qd), vazao_ecologica:qEco, aviso_outorga:outorga,
    invest:(g("custo", 0) && g("tarifa", 0) && kwh > 0) ? invest(g("custo", 0), kwh / 12 * g("tarifa", 0), g("vida", 20), g("taxa", 10), g("infl", 4)) : null, avisos }; }

/* ════════ Estado ════════ */
const CHAVE = { h:"turb", e:"turb-eol" };
function ler(m) { if (typeof calcLer === "function") return calcLer(CHAVE[m]) || {};
  try { return JSON.parse(localStorage.getItem("physis-calc-" + CHAVE[m]) || "{}") || {}; } catch (e) { return {}; } }
function gravar(m, o) { if (typeof calcGravar === "function") return calcGravar(CHAVE[m], o);
  try { localStorage.setItem("physis-calc-" + CHAVE[m], JSON.stringify(o)); } catch (e) {} }
const ou = (a, b) => a == null ? b : a;
const num = s => { if (s == null || String(s).trim() === "") return null; const v = typeof numBr === "function" ? numBr(s) : parseFloat(String(s).replace(",", ".")); return v == null || !isFinite(v) ? null : v; };
/* "3 0,1; 5 0,6; 8 2,1" → [[3, 0.1], [5, 0.6], [8, 2.1]] */
const pares = s => { const l = String(s || "").split(";").map(x => x.trim().split(/\s+/).map(num)).filter(x => x.length >= 2 && x[0] != null && x[1] != null); return l.length >= 2 ? l : null; };
const lista12 = s => { const l = String(s || "").split(/[;\s]+/).filter(Boolean).map(num); return l.length === 12 && l.every(x => x != null && x >= 0) ? l : null; };

/* vento do lugar (servidor). Usa o carregador comum da plataforma (gisX) se existir. */
function ventoDoLugar() { const L = typeof gisLugar === "function" ? gisLugar() : null; if (!L) return null;
  if (ui.modo !== "hub") return { semServidor:true };
  if (typeof gisX === "function") return gisX("vento");
  const k = L.lat.toFixed(3) + "," + L.lon.toFixed(3); ui.turbVento = ui.turbVento || {};
  if (ui.turbVento.k === k) return ui.turbVento; if (ui.modo !== "hub") return null; ui.turbVento = { k, carregando:true };
  fetch(`api/gis/vento?lat=${L.lat}&lon=${L.lon}`, { cache:"no-store" }).then(r => r.json()).then(j => { ui.turbVento = Object.assign(j, { k }); desenhar(false); }).catch(() => { ui.turbVento = { k, ok:false }; desenhar(false); });
  return ui.turbVento; }

/* ════════ Desenho ════════ */
const f1 = (v, c) => v == null || !isFinite(v) ? "—" : n2(v, c == null ? 1 : c);
const campo = (m, o, k, rot, ph, ajuda) => `<div><label for="tu-${m}-${k}">${rot}</label><input id="tu-${m}-${k}" type="text" inputmode="decimal" data-turb-m="${m}" data-turb-k="${k}" value="${esc(o[k] == null ? "" : o[k])}" placeholder="${esc(ph)}" style="width:100%"${ajuda ? ` aria-describedby="tu-${m}-${k}-a"` : ""}>${ajuda ? `<span id="tu-${m}-${k}-a" class="t2 pq">${ajuda}</span>` : ""}</div>`;
const lista = (m, o, k, rot, ops, padrao) => { const atual = o[k] == null || o[k] === "" ? padrao : o[k];
  return `<div><label for="tu-${m}-${k}">${rot}</label><select id="tu-${m}-${k}" data-turb-m="${m}" data-turb-k="${k}" style="width:100%">${ops.map(([v, n]) => `<option value="${esc(v)}" ${String(atual) === String(v) ? "selected" : ""}>${esc(n)}</option>`).join("")}</select></div>`; };
const caixa = (m, o, k, rot) => `<div><label><input type="checkbox" id="tu-${m}-${k}" data-turb-m="${m}" data-turb-k="${k}" ${o[k] ? "checked" : ""}> ${rot}</label></div>`;
const cartao = (id, tit, numero, un, extra) => `<section class="cartao" aria-labelledby="h-${id}"><h3 id="h-${id}" class="t3">${tit}</h3><span class="numero">${numero}</span><span class="t2">${un}</span>${extra || ""}</section>`;
const lstAvisos = l => l.length ? `<ul>${l.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : "";

/* barras verticais simples (12 meses), com tabela ao lado como alternativa */
function barras(id, titulo, valores, rotulos, un) { const W = 360, H = 150, m = 24, mx = Math.max(1e-9, ...valores), bw = (W - m) / valores.length;
  const b = valores.map((v, i) => { const h = (H - 34) * v / mx, x = m + i * bw + 2, y = H - 20 - h;
    return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${(bw - 4).toFixed(1)}" height="${Math.max(0, h).toFixed(1)}" fill="#4B7547"><title>${esc(rotulos[i])}: ${f1(v, 0)} ${esc(un)}</title></rect><text x="${(x + (bw - 4) / 2).toFixed(1)}" y="${H - 6}" font-size="10" text-anchor="middle" fill="#4A4F44">${esc(rotulos[i])}</text>`; }).join("");
  return `<svg id="${id}" viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px" role="img" aria-label="${esc(titulo)}: de ${f1(Math.min(...valores), 0)} a ${f1(mx, 0)} ${esc(un)}; os números estão na tabela"><line x1="${m}" y1="${H - 20}" x2="${W}" y2="${H - 20}" stroke="#C9D2C4"/>${b}</svg>`; }

function blocoInvest(r, kwhAno, tarifa) { if (!r) return `<p class="t2 pq">Informe o custo instalado e a tarifa para ver o retorno (mesma conta dos investimentos da Gestão).</p>`;
  return `<div class="rolagem"><table><caption>Retorno do investimento (economia de ${brl(Math.round(kwhAno * tarifa))} no primeiro ano)</caption><thead><tr><th scope="col">Retorno simples</th><th scope="col">Retorno descontado</th><th scope="col">VPL</th><th scope="col">TIR ao ano</th></tr></thead><tbody><tr>
    <td>${r.simples != null ? f1(r.simples / 12, 1) + " anos" : "não se paga"}</td><td>${r.descontado != null ? f1(r.descontado / 12, 1) + " anos" : "—"}</td><td>${r.vpl != null ? brl(Math.round(r.vpl)) : "—"}</td><td>${r.tir != null ? f1(r.tir, 1) + "%" : "—"}</td></tr></tbody></table></div>`; }

function paramsHid(o) { const mat = o.mat || "pvc";
  return { vazao:num(o.vazao) || 0, vazao_ecologica:num(o.eco) || 0, queda:num(o.queda) || 0, un:o.un === "bar" ? "bar" : "m", eta:ou(num(o.eta), 0.6), horas:ou(num(o.horas), 12), n:ou(num(o.n), 1),
    vazoes_mes:lista12(o.meses), pressao_dinamica:!!o.din, tubo:{ material:mat, diametro_mm:num(o.diam), comprimento_m:num(o.comp), metodo:o.metodo === "hazen" ? "hazen" : "darcy", k_local:num(o.kloc) || 0 },
    custo:num(o.custo), tarifa:num(o.tarifa), vida:num(o.vida), taxa:num(o.taxa), infl:num(o.infl) }; }
/* energia por ano do que foi planejado nas duas partes (para o Carbono, emissões evitadas): só conta a parte que tem
   dados salvos (vazão e queda; diâmetro ou modelo da eólica); sem nada, null */
function kwhAnoPlanejado() { let t = 0, tem = false;
  try { const h = ler("h"); if (num(h.vazao) > 0 && num(h.queda) > 0) { const r = hidraulica(paramsHid(h)); if (r && r.kwh_ano > 0) { t += r.kwh_ano; tem = true; } } } catch (e) {}
  try { const e = ler("e"); if (num(e.diametro) > 0 || e.preset) { const r = eolica(paramsEol(e)); if (r && r.aep_kwh > 0) { t += r.aep_kwh; tem = true; } } } catch (e) {}
  return tem ? t : null; }
function parteHidraulica() { const o = ler("h"), mat = o.mat || "pvc";
  const P = paramsHid(o);
  const R = hidraulica(P);
  let parte = null; try { if (typeof carbCalc === "function" && typeof carbLer === "function") { const ca = carbCalc(carbLer()); if (ca && ca.kwh) parte = R.kwh_ano / ca.kwh; } } catch (e) {}
  const ent = `<section class="cartao" aria-labelledby="h-tu-ent"><h2 id="h-tu-ent">Cada turbina</h2><div class="precos">
      ${campo("h", o, "vazao", "Vazão de projeto (m³ por hora)", "ex.: 12")}${campo("h", o, "queda", "Queda bruta ou pressão", "ex.: 25")}
      ${lista("h", o, "un", "Unidade da queda", [["m", "metros de coluna d'água"], ["bar", "bar"]], "m")}
      ${campo("h", o, "eta", "Eficiência do conjunto (0 a 1)", "0,6")}${campo("h", o, "horas", "Horas com água por dia", "12")}${campo("h", o, "n", "Quantidade de turbinas", "1")}
      ${campo("h", o, "fp", "Fator de potência do gerador (0 a 1)", "da placa", "Vazio = premissa da base (a conferir).")}${campo("h", o, "eco", "Vazão ecológica que fica no rio (m³ por hora)", "da outorga", "O órgão gestor define na outorga; ela sai da vazão disponível.")}</div>
      ${campo("h", o, "meses", "Vazão de cada mês (m³/h, 12 valores separados por ;)", "ex.: 20;22;18;15;12;10;8;8;9;12;15;18", "Opcional. Acima da vazão de projeto, o excesso passa pelo vertedouro; vazio = vazão de projeto o ano todo.")}</section>
    <section class="cartao" aria-labelledby="h-tu-tubo"><h2 id="h-tu-tubo">Tubulação forçada (perdas)</h2><div class="precos">
      ${lista("h", o, "mat", "Material", Object.entries(TUBOS).map(([k, v]) => [k, v[2]]), "pvc")}${campo("h", o, "diam", "Diâmetro interno (mm)", "ex.: 100")}${campo("h", o, "comp", "Comprimento (m)", "ex.: 120")}
      ${lista("h", o, "metodo", "Método", [["darcy", "Darcy-Weisbach (Swamee-Jain)"], ["hazen", "Hazen-Williams"]], "darcy")}${campo("h", o, "kloc", "Soma dos coeficientes de perdas localizadas (K)", "ex.: 2")}</div>
      ${caixa("h", o, "din", "A pressão foi medida com a água correndo (as perdas já estão na medida)")}</section>`;
  const res = `<div class="grade">${cartao("tu-kw", "Potência de cada turbina", f1(R.kw, 2), "kW" + (P.n > 1 ? " · " + f1(R.kw_total, 2) + " kW no total" : ""))}
      ${cartao("tu-kwh", "Energia por ano", f1(R.kwh_ano, 0), "kWh" + (parte != null ? " · " + f1(parte * 100, 1) + "% do consumo" : ""))}
      ${cartao("tu-hl", "Queda líquida", f1(R.queda_liquida, 1), "m · perda de " + f1(R.perda_m, 2) + " m" + (R.velocidade ? " · " + f1(R.velocidade, 2) + " m/s no tubo" : ""))}</div>
    ${R.avisos.length ? `<div class="faixa at" role="status">${lstAvisos(R.avisos)}</div>` : ""}<p class="faixa in" role="note">${esc(R.aviso_outorga)}</p>
    ${typeof PhysisCalc !== "undefined" && PhysisCalc.potencias ? PhysisCalc.potenciasHtml([["Cada turbina", PhysisCalc.potencias(R.kw, num(o.fp))], ["Todas as turbinas", PhysisCalc.potencias(R.kw_total, num(o.fp))]], /^en/i.test(document.documentElement.lang), "Potências do gerador") : ""}`;
  const tipos = R.tipos.length ? `<section class="cartao" aria-labelledby="h-tu-tipo"><h2 id="h-tu-tipo">Tipo de turbina indicado</h2><div class="rolagem"><table><caption>Tipos de turbina pela queda líquida (${f1(R.queda_liquida, 1)} m) e vazão (${f1(P.vazao / 3600, 4)} m³/s), do mais indicado ao menos</caption>
      <thead><tr><th scope="col">Tipo</th><th scope="col">Queda típica</th><th scope="col">Vazão típica</th><th scope="col">Eficiência típica</th><th scope="col">Serve aqui?</th></tr></thead><tbody>
      ${R.tipos.map(t => `<tr><th scope="row">${esc(t.nome)}</th><td>${f1(t.queda[0], 0)} a ${f1(t.queda[1], 0)} m</td><td>${f1(t.vazao_m3s[0] * 1000, 0)} a ${f1(t.vazao_m3s[1] * 1000, 0)} L/s</td><td>${f1(t.eta[0] * 100, 0)} a ${f1(t.eta[1] * 100, 0)}%</td><td>${t.dentro ? `<span class="selo ok">Sim</span>` : `<span class="selo in">Fora da faixa</span>`}</td></tr>`).join("")}</tbody></table></div>
      <p class="t2 pq">Faixas típicas de literatura (ESHA 2004; Paish 2002) para micro e mini centrais — verificar com o fabricante. A eficiência do conjunto (turbina × gerador × controle) é menor que a da turbina sozinha.</p></section>` : "";
  const mes = R.meses.map(m => m.kwh), tabMes = `<section class="cartao" aria-labelledby="h-tu-mes"><h2 id="h-tu-mes">Energia mês a mês</h2>${barras("tu-g-mes", "Energia por mês", mes, MESES, "kWh")}
      <div class="rolagem"><table><caption>Vazão turbinada e energia de cada mês</caption><thead><tr><th scope="col">Mês</th><th scope="col">Vazão turbinada (m³/h)</th><th scope="col">Potência (kW)</th><th scope="col">Energia (kWh)</th></tr></thead><tbody>
      ${R.meses.map((m, i) => `<tr><th scope="row">${MESES[i]}</th><td>${f1(m.vazao, 1)}</td><td>${f1(m.kw, 2)}</td><td>${f1(m.kwh, 0)}</td></tr>`).join("")}</tbody></table></div></section>`;
  const inv = `<section class="cartao" aria-labelledby="h-tu-inv"><h2 id="h-tu-inv">Custo e retorno</h2><div class="precos">${campo("h", o, "custo", "Custo instalado (R$)", "ex.: 25000")}${campo("h", o, "tarifa", "Tarifa de energia (R$/kWh)", "ex.: 0,95")}${campo("h", o, "vida", "Vida útil (anos)", "20")}${campo("h", o, "taxa", "Taxa de desconto (% ao ano)", "10")}${campo("h", o, "infl", "Reajuste da tarifa (% ao ano)", "4")}</div>${blocoInvest(R.invest, R.kwh_ano, P.tarifa || 0)}</section>`;
  return ent + res + tipos + tabMes + inv + `<p class="t2 pq">Potência = 1.000 kg/m³ × 9,81 m/s² × vazão (m³/s) × queda líquida (m) × eficiência. 1 bar ≈ 10,2 m. Perdas: Darcy-Weisbach hf = f·(L/D)·v²/2g (f de Swamee-Jain) ou Hazen-Williams hf = 10,67·L·Q^1,852/(C^1,852·D^4,87), mais ΣK·v²/2g. Com sensores (ESP32 de vazão e pressão), a geração medida entra aqui pelo protocolo V6 (tipo TURB, a homologar).</p>` + metodoHidro(); }

function paramsEol(o) { const V = ventoDoLugar(), temV = V && V.ok, hRef = o.href === "50" ? 50 : 10, serie = temV ? (hRef === 50 ? V.ws50 : V.ws10) : null;
  const pre = PRESETS_EOL.find(x => x.id === o.preset) || null, d = (k, base) => num(o[k]) != null ? num(o[k]) : (pre && pre[k] != null ? pre[k] : base);
  return { diametro:d("diametro", 0), cp:d("cp", 0.30), v_in:d("v_in", 3), v_nom:d("v_nom", null), v_out:d("v_out", 25), p_nom:d("p_nom", null), altura_cubo:ou(num(o.altura), 12), h_ref:hRef,
    terreno:o.terreno || "aberto", alfa:num(o.alfa), altitude:ou(num(o.altitude), (temV && V.elevacao_m != null ? V.elevacao_m : 0)), temperatura:ou(num(o.temp), (temV && V.t2m ? V.t2m.anual : 25)),
    v_ref:ou(num(o.v_ref), (serie ? serie.anual : 0)), meses_ref:num(o.v_ref) == null && serie ? serie.meses : null, k:ou(num(o.k), 2), perdas:ou(num(o.perdas), 0),
    custo:num(o.custo), tarifa:num(o.tarifa), vida:num(o.vida), taxa:num(o.taxa), infl:num(o.infl), curva:pares(o.curva) }; }
function parteEolica() { const o = ler("e"), V = ventoDoLugar(), temV = V && V.ok, hRef = o.href === "50" ? 50 : 10, serie = temV ? (hRef === 50 ? V.ws50 : V.ws10) : null;
  const pre = PRESETS_EOL.find(x => x.id === o.preset) || null;
  const P = paramsEol(o);
  const R = eolica(P), classe = { viavel:"ok", marginal:"at", pouco_viavel:"al" }[R.viabilidade];
  const origem = !V ? "Local não informado — preencha na página Início para trazer o vento da base aberta, ou digite a velocidade medida."
    : V.semServidor ? "Sem o servidor da plataforma não há base de vento: digite a velocidade média medida."
    : V.carregando ? "Carregando o vento do lugar…" : !temV ? "Vento do lugar indisponível agora: digite a velocidade média medida."
    : `Base aberta no lugar: ${f1(V.ws10 && V.ws10.anual, 2)} m/s a 10 m e ${f1(V.ws50 && V.ws50.anual, 2)} m/s a 50 m${V.alfa_medido != null ? " (α entre as duas alturas: " + f1(V.alfa_medido, 2) + ")" : ""}; ${esc(V.fonte || "")}. Campos vazios usam esses valores.`;
  const terrenos = Object.entries(ALFA_TERRENO).map(([k, [a, n]]) => [k, n + " (α " + n2(a, 2) + ")"]);
  const ent = `<section class="cartao" aria-labelledby="h-te-lugar"><h2 id="h-te-lugar">Vento do lugar</h2><p class="t2" role="status">${origem}</p><div class="precos">
      ${campo("e", o, "v_ref", "Velocidade média de referência (m/s)", temV && serie ? n2(serie.anual, 2) : "ex.: 4,5")}${lista("e", o, "href", "Altura da referência", [["10", "10 m"], ["50", "50 m"]], "10")}
      ${campo("e", o, "altura", "Altura do cubo (m)", "12")}${lista("e", o, "terreno", "Terreno em volta (cisalhamento)", terrenos, "aberto")}
      ${campo("e", o, "alfa", "Expoente α (opcional, substitui o terreno)", "ex.: 0,2")}${campo("e", o, "k", "Forma da distribuição de Weibull (k)", "2", "k = 2 é a distribuição de Rayleigh, usada sem medição.")}
      ${campo("e", o, "altitude", "Altitude (m)", temV && V.elevacao_m != null ? n2(V.elevacao_m, 0) : "0")}${campo("e", o, "temp", "Temperatura média (°C)", temV && V.t2m ? n2(V.t2m.anual, 1) : "25")}</div></section>
    <section class="cartao" aria-labelledby="h-te-turb"><h2 id="h-te-turb">Turbina</h2><div class="precos">
      ${lista("e", o, "preset", "Modelo de partida", [["", "Digitar os dados"]].concat(PRESETS_EOL.map(x => [x.id, x.nome])), "")}
      ${campo("e", o, "diametro", "Diâmetro do rotor (m)", pre ? n2(pre.diametro, 1) : "ex.: 4")}${campo("e", o, "cp", "Coeficiente de potência Cp (até 0,593)", pre ? n2(pre.cp, 2) : "0,30", "Pequenas turbinas: tipicamente 0,25 a 0,40.")}
      ${campo("e", o, "p_nom", "Potência nominal (kW)", pre ? n2(pre.p_nom, 0) : "ex.: 3")}${campo("e", o, "v_in", "Velocidade de partida (m/s)", pre ? n2(pre.v_in, 1) : "3")}
      ${campo("e", o, "v_nom", "Velocidade nominal (m/s)", pre ? n2(pre.v_nom, 1) : "ex.: 11")}${campo("e", o, "v_out", "Velocidade de corte (m/s)", pre ? n2(pre.v_out, 1) : "25")}
      ${campo("e", o, "perdas", "Perdas e indisponibilidade (%)", "0")}</div>
      ${campo("e", o, "curva", "Curva de potência do fabricante (velocidade m/s e kW, pares separados por ;)", "ex.: 3 0,1; 5 0,6; 8 2,1; 11 3,0; 25 3,0", "Curva certificada (IEC 61400-12-1) da folha do fabricante. Preenchida, ela substitui o modelo por Cp no cálculo da energia.")}
      ${R.curva_fabricante ? `<p class="t2 pq"><span class="selo ok">Curva do fabricante</span> A energia sai da curva digitada; o Cp e o diâmetro não entram na conta.</p>` : ""}
      ${pre ? `<p class="t2 pq"><span class="selo at">Verificar</span> Classe genérica, não é um modelo comercial: troque pelos dados e pela curva do fabricante.</p>` : ""}</section>`;
  const res = `<div class="faixa ${classe}" role="status"><strong>${esc(R.mensagem)}</strong></div>
    ${typeof PhysisCalc !== "undefined" && PhysisCalc.potencias && R.p_nom ? PhysisCalc.potenciasHtml([["Turbina na potência nominal", PhysisCalc.potencias(R.p_nom, num(o.fp))]], /^en/i.test(document.documentElement.lang), "Potências do gerador") : ""}
    <div class="grade">${cartao("te-v", "Vento no cubo", f1(R.v_cubo, 2), "m/s de média · α " + f1(R.alfa, 2) + " · c " + f1(R.c, 2) + " m/s")}
      ${cartao("te-e", "Energia por ano", f1(R.aep_kwh, 0), "kWh" + (R.meses ? " (soma dos 12 meses)" : ""))}
      ${cartao("te-fc", "Fator de capacidade", R.fc == null ? "—" : f1(R.fc * 100, 1) + "%", R.p_nom ? "de " + f1(R.p_nom, 1) + " kW nominais" : "informe a potência nominal")}
      ${cartao("te-rho", "Densidade do ar", f1(R.rho, 3), "kg/m³ · área do rotor " + f1(R.area, 1) + " m²")}</div>${R.avisos.length ? `<div class="faixa at">${lstAvisos(R.avisos)}</div>` : ""}`;
  const pts = R.curva, W = 360, H = 170, mxP = Math.max(1e-9, ...pts.map(x => x.kw)), vx = pts[pts.length - 1].v, sx = v => 30 + v / vx * (W - 40), sy = p => H - 24 - p / mxP * (H - 40);
  const svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px" role="img" aria-label="Curva de potência: até ${f1(mxP, 1)} kW; os números estão na tabela"><line x1="30" y1="${H - 24}" x2="${W - 10}" y2="${H - 24}" stroke="#C9D2C4"/><line x1="30" y1="10" x2="30" y2="${H - 24}" stroke="#C9D2C4"/>
    <polyline fill="none" stroke="#33512F" stroke-width="2.5" points="${pts.map(x => sx(x.v).toFixed(1) + "," + sy(x.kw).toFixed(1)).join(" ")}"/>${R.v_cubo > 0 ? `<line x1="${sx(R.v_cubo).toFixed(1)}" y1="10" x2="${sx(R.v_cubo).toFixed(1)}" y2="${H - 24}" stroke="#8A6410" stroke-dasharray="4 3"/>` : ""}
    <text x="${W - 10}" y="${H - 6}" font-size="10" text-anchor="end" fill="#4A4F44">vento (m/s)</text><text x="34" y="18" font-size="10" fill="#4A4F44">${f1(mxP, 1)} kW</text></svg>`;
  const curva = `<section class="cartao" aria-labelledby="h-te-curva"><h2 id="h-te-curva">Curva de potência e horas por ano</h2>${svg}<p class="t2 pq">P = ½·ρ·A·v³·Cp, limitada à potência nominal; zero abaixo da partida e acima do corte. Linha tracejada: média no cubo.</p>
    <div class="rolagem"><table><caption>Potência e horas por ano em cada velocidade (Weibull k ${f1(R.k, 1)}, c ${f1(R.c, 2)} m/s)</caption><thead><tr><th scope="col">Vento (m/s)</th><th scope="col">Potência (kW)</th><th scope="col">Horas por ano</th></tr></thead><tbody>
    ${pts.map(x => `<tr><th scope="row">${x.v}</th><td>${f1(x.kw, 2)}</td><td>${f1(x.horas, 0)}</td></tr>`).join("")}</tbody></table></div></section>`;
  const meses = R.meses ? `<section class="cartao" aria-labelledby="h-te-mes"><h2 id="h-te-mes">Energia mês a mês</h2>${barras("te-g-mes", "Energia por mês", R.meses.map(m => m.kwh), MESES, "kWh")}
    <div class="rolagem"><table><caption>Vento no cubo e energia de cada mês</caption><thead><tr><th scope="col">Mês</th><th scope="col">Vento no cubo (m/s)</th><th scope="col">Energia (kWh)</th></tr></thead><tbody>
    ${R.meses.map((m, i) => `<tr><th scope="row">${MESES[i]}</th><td>${f1(m.v_cubo, 2)}</td><td>${f1(m.kwh, 0)}</td></tr>`).join("")}</tbody></table></div></section>` : "";
  const inv = `<section class="cartao" aria-labelledby="h-te-inv"><h2 id="h-te-inv">Custo e retorno</h2><div class="precos">${campo("e", o, "custo", "Custo instalado (R$)", "ex.: 40000")}${campo("e", o, "tarifa", "Tarifa de energia (R$/kWh)", "ex.: 0,95")}${campo("e", o, "vida", "Vida útil (anos)", "20")}${campo("e", o, "taxa", "Taxa de desconto (% ao ano)", "10")}${campo("e", o, "infl", "Reajuste da tarifa (% ao ano)", "4")}</div>${blocoInvest(R.invest, R.aep_kwh, P.tarifa || 0)}</section>`;
  const cuidados = `<section class="cartao" aria-labelledby="h-te-cuid"><h2 id="h-te-cuid">Cuidados antes de instalar</h2><ul>
    <li>Meça antes de comprar: anemômetro na altura do cubo por 12 meses. A base aberta é média de grade regional (cerca de 50 km) e não vê prédios, árvores nem morros do lugar.</li>
    <li>Na cidade e em telhados o vento é turbulento e fraco: a energia real costuma ficar bem abaixo da conta. Prefira torre afastada de obstáculos, com o rotor bem acima de tudo o que estiver em volta.</li>
    <li>Ruído e distância: confira o nível de ruído do fabricante na distância das casas vizinhas contra os limites da NBR 10151 para a zona; vibração e sombra intermitente também incomodam.</li>
    <li>Torre: fundação, estrutura e para-raios com projeto e ART; consulte a prefeitura (altura, recuos) e, perto de aeródromos, as regras de obstáculo.</li>
    <li>Ligação à rede: microgeração distribuída pela distribuidora (inversor homologado e pedido de acesso).</li></ul>
    <p class="t2 pq">Contas: densidade ρ = p/(287,05·T) com p da atmosfera padrão; cisalhamento v(h) = v_ref·(h/h_ref)^α; Weibull c = v̄/Γ(1+1/k); energia = 8.760·∫P(v)·f(v)dv; fator de capacidade = energia/(potência nominal·8.760). Cp nunca acima de Betz (16/27).</p></section>`;
  return ent + res + curva + meses + inv + cuidados + metodoEolica(); }

/* ════════ Metodologia e normas (redação própria; normas citadas pelo número, ler o texto vigente) ════════ */
const NORMAS_CONEXAO = `<li>Conexão à rede como micro ou minigeração: Lei 14.300/2022 (marco legal e compensação de energia), ANEEL REN 1.059/2023 (acesso, prazos e faturamento) e PRODIST Módulo 3 (procedimentos de acesso), além da norma técnica de acesso da distribuidora. A ABNT NBR 16149:2013 (interface com a rede) e a NBR 16150:2013 (ensaios dessa interface) foram escritas para inversores fotovoltaicos; para gerador hidráulico ou eólico, a distribuidora aplica as proteções do PRODIST e da sua norma; inversores com certificação para a rede costumam passar pelos mesmos ensaios.</li>
  <li>ABNT NBR 5410 (instalações de baixa tensão) e NBR 5419 (proteção contra descargas atmosféricas); projeto elétrico e estrutural com ART.</li>`;
function metodoHidro() { return `<details class="cartao"><summary><h2 style="display:inline">Metodologia e normas</h2></summary><ul>
  <li><strong>Potência:</strong> P = ρ·g·Q·H·η (balanço de energia). η é do conjunto: turbina × transmissão × gerador × controle; a faixa da tabela de tipos é só da turbina.</li>
  <li><strong>Queda líquida:</strong> queda bruta menos a perda de carga da tubulação forçada. Se a pressão foi medida na entrada da turbina com a água correndo, a perda já está na medida.</li>
  <li><strong>Perda distribuída:</strong> Darcy-Weisbach com o fator de atrito de Swamee e Jain (1976), explícito e válido para escoamento turbulento (Re de cerca de 5·10³ a 10⁸ e rugosidade relativa de 10⁻⁶ a 10⁻²); abaixo de Re 2.000, 64/Re. Entre 2.000 e 5.000 (transição) o resultado é aproximado. Hazen-Williams é empírica: só para água fria, regime turbulento e tubos de diâmetro médio e grande; serve de conferência.</li>
  <li><strong>Perdas localizadas:</strong> ΣK·v²/2g (entrada, curvas, válvulas, grade). Os valores de K vêm do catálogo da peça ou de tabelas de hidráulica.</li>
  <li><strong>Velocidade e golpe de aríete:</strong> acima de 3 m/s o sistema avisa; o projeto confere a sobrepressão de fechamento (Joukowsky, Δh = a·Δv/g, com a celeridade do tubo) e o tempo de manobra das válvulas.</li>
  <li><strong>Energia mês a mês:</strong> vazão do mês limitada à de projeto (o resto passa pelo vertedouro), perda recalculada com a vazão do mês, eficiência constante (sem curva de carga parcial: Kaplan, Pelton e Banki mantêm melhor a eficiência com pouca água que Francis e bomba como turbina).</li>
  <li><strong>Tipo de turbina:</strong> faixas de queda e vazão de literatura para micro e mini centrais (ESHA 2004; Paish 2002). A escolha final é do fabricante, pela rotação específica.</li>
  <li><strong>Retorno:</strong> analiseInvest da plataforma (o mesmo da Gestão), com a energia do ano × tarifa.</li></ul>
  <p class="t2"><strong>Normas e regras</strong></p><ul>
  <li>IEC 61116 — guia do equipamento eletromecânico de pequenas centrais hidrelétricas; IEC 60041 — ensaios de campo para medir o rendimento de turbinas; IEC 60193 — ensaios em modelo reduzido.</li>
  <li>ABNT NBR 12214 — projeto de sistemas de bombeamento para abastecimento: referência para quem usa bomba como turbina e para a adutora.</li>
  <li>Eletrobras — Diretrizes para estudos e projetos de PCH e Manual de microcentrais hidrelétricas; ASCE Manual 79 para tubulação forçada de aço.</li>
  <li>Uso da água: outorga de direito de uso (Lei 9.433/1997) com a ANA ou o órgão estadual, e licença ambiental. Central de até 5 MW (CGH): dispensada de concessão ou autorização, só comunicada à ANEEL (Lei 9.074/1995, com a redação da Lei 13.360/2016).</li>
  ${NORMAS_CONEXAO}</ul></details>`; }
function metodoEolica() { return `<details class="cartao"><summary><h2 style="display:inline">Metodologia e normas</h2></summary><ul>
  <li><strong>Curva de potência:</strong> P = ½·ρ·A·v³·Cp, com Cp nunca acima do limite de Betz (16/27); zero abaixo da partida e acima do corte; limitada à potência nominal. Com a curva medida do fabricante, use-a: ela já inclui as perdas do rotor, do gerador e do controle.</li>
  <li><strong>Densidade do ar:</strong> atmosfera padrão (ISO 2533) pela altitude e gás ideal pela temperatura. A curva do fabricante vem na densidade padrão (1,225 kg/m³); a IEC 61400-12-1 normaliza a medição pela densidade.</li>
  <li><strong>Vento na altura do cubo:</strong> lei de potência v(h) = v_ref·(h/h_ref)^α, com α pelo terreno (Masters 2004) ou o α medido entre 10 m e 50 m da base aberta. A IEC 61400-1 usa α = 0,2 no perfil de vento normal de projeto.</li>
  <li><strong>Distribuição do vento:</strong> Weibull com k = 2 (Rayleigh) quando não há medição — a mesma hipótese da IEC 61400-12-1 para a energia anual de referência; c = v̄/Γ(1 + 1/k).</li>
  <li><strong>Energia anual:</strong> 8.760 h × ∫P(v)·f(v)dv (integração numérica a cada 0,05 m/s); com as 12 médias mensais, a soma dos meses. Fator de capacidade = energia ÷ (potência nominal × 8.760 h).</li>
  <li><strong>Viabilidade:</strong> abaixo de 4 m/s de média no cubo, pouco viável; de 4 a 5 m/s, marginal; acima, viável a confirmar com 12 meses de medição no local (anemômetro na altura do cubo).</li></ul>
  <p class="t2"><strong>Normas e regras</strong></p><ul>
  <li>IEC 61400-2 — pequenas turbinas eólicas (área varrida até 200 m²): classes de vento, cargas de projeto, ensaios de desempenho, durabilidade e segurança. Peça ao fabricante o certificado ou o relatório de ensaio.</li>
  <li>IEC 61400-12-1 — medição da curva de potência e cálculo da energia anual; IEC 61400-11 — medição de ruído acústico.</li>
  <li>ABNT NBR 10151:2019 — ruído em áreas habitadas (limites por tipo de área e período); ABNT NBR 6123 — forças do vento na torre e na estrutura.</li>
  <li>Perto de aeródromos: regras do DECEA para objetos que sobem no espaço aéreo; altura e recuos pela prefeitura.</li>
  ${NORMAS_CONEXAO}</ul></details>`; }

function telaTurbinas() { const sub = ui.turbSub === "eolica" ? "eolica" : "hidraulica", SUBS = [["hidraulica", "Hidráulica"], ["eolica", "Eólica"]];
  const chips = `<div class="chips" role="group" aria-label="Tipo de turbina">${SUBS.map(([k, n]) => `<button type="button" id="turb-sub-${k}" data-turb-sub="${k}" aria-pressed="${k === sub}">${n}</button>`).join("")}</div>`;
  const apoio = sub === "hidraulica" ? "Energia das descidas de água: tipo de turbina, perdas na tubulação, potência, energia mês a mês e retorno."
    : "Energia do vento: vento do lugar na altura do cubo, curva de potência, energia por ano, fator de capacidade e se vale a pena.";
  return `<h1>Turbinas</h1><p class="t2 apoio">${apoio}</p>${chips}<div id="turb-corpo">${sub === "hidraulica" ? parteHidraulica() : parteEolica()}</div>`; }

/* ════════ Eventos (atributos data-turb-…) ════════ */
function refocar(id) { const x = el(id); if (x) x.focus(); }
if (typeof document !== "undefined" && !window.__turbEventos) { window.__turbEventos = true;
  document.addEventListener("change", ev => { const t = ev.target; if (!t || !t.dataset || !t.dataset.turbK || !CHAVE[t.dataset.turbM]) return;
    const m = t.dataset.turbM, k = t.dataset.turbK, o = Object.assign({}, ler(m));
    o[k] = t.type === "checkbox" ? (t.checked ? 1 : "") : t.value;
    if (m === "e" && k === "preset") ["diametro", "cp", "p_nom", "v_in", "v_nom", "v_out"].forEach(x => { o[x] = ""; });   /* o modelo escolhido preenche */
    gravar(m, o); const id = t.id; desenhar(false); refocar(id); });
  document.addEventListener("click", ev => { const b = ev.target.closest ? ev.target.closest("button") : null; if (!b || !b.dataset || !b.dataset.turbSub) return;
    ui.turbSub = b.dataset.turbSub; desenhar(false); refocar("turb-sub-" + b.dataset.turbSub); }); }

window.TURBINAS = { hidraulica, eolica, kwhAnoPlanejado, densidadeAr, cisalhamento, alfaMedido, weibullC, weibullPdf, turbinaEolica, potenciaVento, energiaWeibull,
  potenciaHidraulica, perdaDarcy, perdaHazen, sugerirTipos, gama, ALFA_TERRENO, TIPOS_HIDRO, TUBOS, PRESETS_EOL, BETZ };
window.telaTurbinas = telaTurbinas;   /* global: a plataforma chama telaTurbinas() na hora de desenhar */
})();
