/* physis-frota.js — aba Frota e combustível da plataforma (caminhões, carros, tratores e máquinas). EM DESENVOLVIMENTO.
   Contrato com a plataforma: define telaFrota() (HTML da aba inteira, com o único título h1), window.FROTA = { contas puras,
   testáveis, paraCarbono, resumoGestao } e window.FROTA_I18N (português → inglês, para juntar ao I18N) com
   window.FROTA_I18N_RX (frases com números); os dois vão copiados em sistema/physis-i18n-modulos.json.
   Espelho de physis-hub/physis_hub/frota.py (mesmas premissas frota.*, fórmulas e constantes; teste em tests/test_frota.py).
   Dados: no modo hub, GET api/frota/estado e api/frota/rota (cópia guardada neste aparelho para ver sem ligação); sem
   veículo cadastrado, ou fora do modo hub, uma frota SIMULADA (3 veículos em volta do local da instalação, marcados
   como tal), que nunca entra no Carbono nem na Gestão. Mapa: SVG desenhado aqui (projeção local, como o mapa da
   Economia circular e o localizador do receptor), sem biblioteca nem fundo de terceiros, com a tabela ao lado.
   Globais usadas se existirem: esc, n2, numBr, el, ui, desenhar, localDaInstalacao, PhysisCalc, PhysisCarbono, brl. */
(function () {
"use strict";
const CHAVE = "physis-frota-cache";
const R_TERRA_KM = 6371.0088, K_MAD = 0.6745, INTERVALO_MAX_S = 900;
/* reserva das premissas frota.* (as mesmas de sistema/physis-premissas.json; todas "conferir") */
const PREMISSAS_RESERVA = { "frota.anomalia_z":3.5, "frota.anomalia_desvio_min_pct":15.0, "frota.anomalia_amostra_min":8, "frota.ewma_alfa":0.3, "frota.queda_nivel_pct":5.0,
  "frota.parado_distancia_km":0.2, "frota.marcha_lenta_vel_kmh":3.0, "frota.marcha_lenta_min":20.0, "frota.gps_salto_kmh":200.0, "frota.retencao_dias":365 };
const TIPOS = { caminhao:"Caminhão", carro:"Carro", trator:"Trator", maquina:"Máquina", outro:"Outro" };
const COMBUSTIVEIS = ["diesel_b", "gasolina_c", "etanol_hidratado", "gnv", "biodiesel", "diesel"];
const NOME_COMB = { diesel_b:"Diesel B (com biodiesel)", gasolina_c:"Gasolina C (com etanol)", etanol_hidratado:"Etanol hidratado", gnv:"GNV (m³)", biodiesel:"Biodiesel (B100)", diesel:"Diesel A" };
const UNIDADES = { l_100km:"L/100 km", l_h:"L/h" };
const FONTES_PRECO = { nota:"Nota fiscal", cartao:"Cartão-combustível", bomba:"Preço da bomba", estimado:"Estimado" };
const COR = { caminhao:"var(--al-t,#7A2214)", carro:"var(--agua,#2F7D5B)", trator:"var(--at-t,#5C3F00)", maquina:"var(--in-t,#4A4F44)", outro:"var(--tinta2,#4A4F44)" };
const PONTO_EXEMPLO = { lat:-22.5051, lon:-43.1784 };   /* o mesmo ponto de exemplo das demonstrações da Saúde */
function premissa(id) { try { if (typeof PhysisCalc !== "undefined") { const v = PhysisCalc.premissa(id); if (typeof v === "number" && isFinite(v)) return v; } } catch (e) {} return PREMISSAS_RESERVA[id]; }
const P = () => Object.fromEntries(Object.keys(PREMISSAS_RESERVA).map(k => [k, premissa(k)]));

/* ════════ Contas puras (espelho de frota.py) ════════ */
function haversineKm(la1, lo1, la2, lo2) { const r = Math.PI / 180, dp = (la2 - la1) * r, dl = (lo2 - lo1) * r;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(la1 * r) * Math.cos(la2 * r) * Math.sin(dl / 2) ** 2; return 2 * R_TERRA_KM * Math.asin(Math.sqrt(Math.min(1, a))); }
const temPos = p => p.lat != null && p.lon != null;
function distancia(pontos, saltoKmh) { let km = 0, desc = 0, ant = null;
  for (const p of pontos) { if (!temPos(p)) continue;
    if (ant) { const d = haversineKm(ant.lat, ant.lon, p.lat, p.lon), dt = p.ts - ant.ts; if (dt > 0 && d / (dt / 3600) > saltoKmh) { desc++; continue; } km += d; }
    ant = p; }
  const odos = pontos.filter(p => p.odo != null).map(p => p.odo), kmOdo = odos.length >= 2 && odos[odos.length - 1] >= odos[0] ? odos[odos.length - 1] - odos[0] : null, usa = kmOdo != null && kmOdo > 0;
  return { km: usa ? kmOdo : km, km_gps: km, km_odometro: kmOdo, fonte: usa ? "odometro" : "gps", descartados: desc }; }
function litrosDoFluxo(pontos) { const c = pontos.filter(p => p.flx != null); if (c.length < 2) return null; let t = 0;
  for (let i = 1; i < c.length; i++) { const dt = c[i].ts - c[i - 1].ts; if (dt > 0 && dt <= INTERVALO_MAX_S) t += (c[i - 1].flx + c[i].flx) / 2 * dt / 3600; } return t; }
/* litros, km e horas só nos trechos com vazão nas duas pontas: a base do consumo (espelho de trechos_com_vazao) */
function trechosComVazao(pontos, salto) { let litros = 0, km = 0, horas = 0, n = 0;
  for (let i = 1; i < pontos.length; i++) { const a = pontos[i - 1], b = pontos[i]; if (a.flx == null || b.flx == null) continue; const dt = b.ts - a.ts; if (!(dt > 0 && dt <= INTERVALO_MAX_S)) continue;
    n++; litros += (a.flx + b.flx) / 2 * dt / 3600; if (a.flx > 0 || b.flx > 0) horas += dt / 3600;
    if (temPos(a) && temPos(b)) { const d = haversineKm(a.lat, a.lon, b.lat, b.lon); if (d / (dt / 3600) <= salto) km += d; } }
  return { litros: n ? litros : null, km, horas }; }
const motorLigado = p => p.ign != null ? !!p.ign : p.flx != null ? p.flx > 0 : null;
function horasMotor(pontos) { const hs = pontos.filter(p => p.hor != null).map(p => p.hor); if (hs.length >= 2 && hs[hs.length - 1] >= hs[0]) return hs[hs.length - 1] - hs[0];
  let t = 0, tem = false; for (let i = 0; i + 1 < pontos.length; i++) { const l = motorLigado(pontos[i]); if (l == null) continue; tem = true; const dt = pontos[i + 1].ts - pontos[i].ts; if (l && dt > 0 && dt <= INTERVALO_MAX_S) t += dt / 3600; }
  return tem ? t : null; }
function marchaLenta(pontos, velLim, minLim) { let horas = 0, ini = null, ult = null; const ev = [];
  const fecha = () => { if (ini && ult) { const m = (ult.ts - ini.ts) / 60; if (m >= minLim) ev.push({ ts_ini: ini.ts, ts_fim: ult.ts, min: m, lat: ini.lat, lon: ini.lon }); } };
  for (const p of pontos) { const parado = p.vel != null && p.vel < velLim && motorLigado(p) === true;
    if (parado && ini && p.ts - ult.ts > INTERVALO_MAX_S) { fecha(); ini = null; }
    if (parado) { if (!ini) ini = p; else horas += (p.ts - ult.ts) / 3600; ult = p; }
    else if (ini) { fecha(); ini = null; ult = null; } }
  fecha(); return { horas, eventos: ev }; }
function consumo(litros, km, horas) { return { l_100km: litros != null && km > 0 ? litros / km * 100 : null, l_h: litros != null && horas > 0 ? litros / horas : null, km_l: litros > 0 && km != null ? km / litros : null }; }
const mediana = v => { const s = v.slice().sort((a, b) => a - b), n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : null; };
function normalAprendido(amostras, alfa) { const v = amostras.filter(x => x != null && isFinite(x)); if (!v.length) return { n: 0, mediana: null, mad: null, ewma: null };
  const med = mediana(v), mad = mediana(v.map(x => Math.abs(x - med))); let e = v[0]; for (let i = 1; i < v.length; i++) e = alfa * v[i] + (1 - alfa) * e;
  return { n: v.length, mediana: med, mad, ewma: e }; }
function anomaliaConsumo(valor, hist, zLim, nMin, alfa, desvioMin) { const nm = normalAprendido(hist, alfa), o = Object.assign({}, nm, { valor, z: null, anomalo: false, motivo: "" });
  if (nm.n < nMin) { o.motivo = "aprendendo"; return o; } if (!nm.mad) { o.motivo = "sem variação"; return o; }
  o.z = K_MAD * (valor - nm.mediana) / nm.mad; o.anomalo = o.z > zLim && valor >= nm.mediana * (1 + (desvioMin || 0) / 100); return o; }
function pontoNoPoligono(lat, lon, pol) { let dentro = false; const n = pol.length; if (n < 3) return false;
  for (let i = 0, j = n - 1; i < n; j = i++) { const yi = pol[i][0], xi = pol[i][1], yj = pol[j][0], xj = pol[j][1];
    if ((yi > lat) !== (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) dentro = !dentro; } return dentro; }
function saidasDaCerca(pontos, cercas, veiculo) { const out = [];
  for (const c of cercas) { if (c.ativa === false || !c.poligono || c.poligono.length < 3) continue; if (c.veiculos && c.veiculos.length && veiculo != null && c.veiculos.indexOf(veiculo) < 0) continue;
    let antes = null; for (const p of pontos) { if (!temPos(p)) continue; const agora = pontoNoPoligono(p.lat, p.lon, c.poligono);
      if (antes === true && !agora) out.push({ cerca: c.id, nome: c.nome || "", ts: p.ts, lat: p.lat, lon: p.lon }); antes = agora; } }
  return out; }
function quedasSemAndar(pontos, quedaPct, distMax, velLim, tanque) { const c = pontos.filter(p => p.niv != null), out = []; let i = 0;
  while (i < c.length) { const s = c[i]; let j = i + 1, ev = null, litros = 0;
    while (j < c.length) { const p = c[j], o = c[j - 1], andou = (temPos(s) && temPos(p) && haversineKm(s.lat, s.lon, p.lat, p.lon) > distMax) || (p.vel != null && p.vel >= velLim) || p.ts - o.ts > 6 * 3600 || p.ts - s.ts > 48 * 3600;
      if (andou || p.niv > o.niv + 0.5) break;
      const dt = p.ts - o.ts; if (p.flx != null && o.flx != null && dt > 0 && dt <= INTERVALO_MAX_S) litros += (p.flx + o.flx) / 2 * dt / 3600;
      const gasto = tanque ? litros / tanque * 100 : 0, q = s.niv - p.niv - gasto;
      if (q >= quedaPct && (!ev || q >= ev.queda_pct)) ev = { ts_ini: s.ts, ts_fim: p.ts, queda_pct: q, litros: tanque ? q / 100 * tanque : null, lat: p.lat, lon: p.lon };   /* um evento só por janela */
      j++; }
    if (ev) out.push(ev); i = ev ? j : i + 1; }
  return out; }
const FUSO_MS = 3 * 3600 * 1000;   /* Brasília (UTC−3), o mesmo fuso do hub */
const diaDe = ts => new Date(ts * 1000 - FUSO_MS).toISOString().slice(0, 10);
function porDia(pontos, salto, velLim, minLim) { const g = {}; pontos.forEach(p => (g[diaDe(p.ts)] = g[diaDe(p.ts)] || []).push(p)); const out = {};
  Object.keys(g).sort().forEach(d => { const ps = g[d], dist = distancia(ps, salto), lf = litrosDoFluxo(ps), hm = horasMotor(ps), ml = marchaLenta(ps, velLim, minLim), tv = trechosComVazao(ps, salto), c = consumo(tv.litros, tv.km, tv.horas);
    out[d] = { km: dist.km, km_fonte: dist.fonte, litros_fluxo: lf, horas_motor: hm, horas_marcha_lenta: ml.horas, l_100km: c.l_100km, l_h: c.l_h, pontos: ps.length }; });
  return out; }
function consumoEntreAbastecimentos(abast, unidade) { const campo = unidade === "l_h" ? "horimetro" : "odometro";
  const ab = abast.filter(a => a[campo] != null).sort((a, b) => a.data < b.data ? -1 : a.data > b.data ? 1 : a[campo] - b[campo]), out = [];
  for (let i = 1; i < ab.length; i++) { const d = ab[i][campo] - ab[i - 1][campo]; if (d > 0) out.push({ data: ab[i].data, valor: ab[i].litros / d * (unidade === "l_h" ? 1 : 100), abastecimento: ab[i].id }); }
  return out; }
function amostrasConsumo(dias, abast, unidade, hoje) { const k = unidade === "l_h" ? "l_h" : "l_100km";   /* só dias completos: hoje não entra */
  const med = Object.keys(dias).sort().filter(d => dias[d][k] != null && dias[d].litros_fluxo && (!hoje || d < hoje)).map(d => ({ data: d, valor: dias[d][k], fonte: "vazão" }));
  return med.length ? med : consumoEntreAbastecimentos(abast, unidade).map(x => Object.assign({}, x, { fonte: "abastecimentos" })); }
/* CO₂e: o MESMO caminho do Carbono (PhysisCarbono.calcular com uma linha de combustão móvel) */
function co2e(comb, litros) { try { const C = window.PhysisCarbono; if (!C || !C.calcular) return null; const R = C.calcular({ v:2, movel:[{ comb, qtd: String(litros || 0), q:"medido" }], estac:[] }, {});
  if (!R) return null; const l = R.linhas.filter(x => x.grupo === "movel"); return { t: l.reduce((s, x) => s + x.t, 0), bio_t: l.reduce((s, x) => s + x.bio_t, 0) }; } catch (e) { return null; } }
function paraCarbonoDe(veiculos, abast, ano, fluxo) { const comb = {}; veiculos.forEach(v => comb[v.id] = v.combustivel); const soma = {}, com = new Set();
  abast.forEach(a => { if (String(a.data || "").slice(0, 4) !== String(ano) || !(a.veiculo in comb)) return; const x = soma[comb[a.veiculo]] = soma[comb[a.veiculo]] || { qtd: 0, n: 0, fluxo: 0 }; x.qtd += +a.litros; x.n++; com.add(a.veiculo); });
  Object.entries(fluxo || {}).forEach(([id, l]) => { id = +id; if (id in comb && !com.has(id) && l > 0) { const x = soma[comb[id]] = soma[comb[id]] || { qtd: 0, n: 0, fluxo: 0 }; x.qtd += l; x.fluxo += l; } });
  return COMBUSTIVEIS.filter(c => soma[c] && soma[c].qtd > 0).map(c => { const x = soma[c], partes = [];
    if (x.n) partes.push(x.n + " abastecimento" + (x.n !== 1 ? "s" : "") + " de " + ano); if (x.fluxo) partes.push(x.fluxo.toFixed(0) + " L pela vazão");
    return { comb: c, qtd: Math.round(x.qtd * 1000) / 1000, q: "medido", fonte: "Frota e combustível: " + partes.join(" e ") }; }); }
function custosPorMes(abast) { const o = {}; abast.forEach(a => { const m = String(a.data || "").slice(0, 7), x = o[m] = o[m] || { litros: 0, custo: 0, sem_preco: 0 }; x.litros += +a.litros; if (a.preco_l != null) x.custo += +a.litros * +a.preco_l; else x.sem_preco++; });
  return Object.fromEntries(Object.keys(o).sort().map(k => [k, o[k]])); }
function analise(v, pontos, abast, cercas) { const p = P(), dias = porDia(pontos, p["frota.gps_salto_kmh"], p["frota.marcha_lenta_vel_kmh"], p["frota.marcha_lenta_min"]);
  const am = amostrasConsumo(dias, abast, v.consumo_unidade, diaDe(Date.now() / 1000)), al = []; let normal;
  if (am.length) { const u = am[am.length - 1], r = anomaliaConsumo(u.valor, am.slice(0, -1).map(a => a.valor), p["frota.anomalia_z"], p["frota.anomalia_amostra_min"], p["frota.ewma_alfa"], p["frota.anomalia_desvio_min_pct"]); normal = r;
    if (r.anomalo) al.push({ tipo:"consumo", nivel:"atencao", ts:null, data:u.data, valor:u.valor, unidade:UNIDADES[v.consumo_unidade], z:r.z, mediana:r.mediana, ewma:r.ewma, n:r.n, fonte:u.fonte }); }
  else normal = Object.assign(normalAprendido([], p["frota.ewma_alfa"]), { motivo:"sem amostras" });
  quedasSemAndar(pontos, p["frota.queda_nivel_pct"], p["frota.parado_distancia_km"], p["frota.marcha_lenta_vel_kmh"], v.tanque_l).forEach(q => al.push(Object.assign({}, q, { tipo:"queda_nivel", nivel:"alarme", ts:q.ts_fim })));
  marchaLenta(pontos, p["frota.marcha_lenta_vel_kmh"], p["frota.marcha_lenta_min"]).eventos.forEach(m => al.push(Object.assign({}, m, { tipo:"marcha_lenta", nivel:"atencao", ts:m.ts_fim })));
  saidasDaCerca(pontos, cercas, v.id).forEach(s => al.push(Object.assign({}, s, { tipo:"cerca", nivel:"alarme" })));
  const ult = pontos.slice().reverse().find(temPos), u2 = pontos[pontos.length - 1];
  return { dias, amostras: am.slice(-60), normal, alertas: al, ultima: u2 ? Object.assign({ ts:u2.ts, vel:u2.vel, rumo:u2.rumo, flx:u2.flx, niv:u2.niv, hor:u2.hor, odo:u2.odo, ign:u2.ign, origem:u2.origem }, ult ? { lat:ult.lat, lon:ult.lon, ts_pos:ult.ts } : {}) : null,
    simulado: pontos.some(x => /simulado$/.test(String(x.origem || ""))) }; }

/* ════════ Utilidades (com reserva quando a plataforma não as tem) ════════ */
const E = s => typeof esc === "function" ? esc(s) : String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));
const N = (v, c) => typeof n2 === "function" ? n2(v, c) : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c });
const f1 = (v, c) => v == null || !isFinite(v) ? "—" : N(v, c == null ? 1 : c);
const num = s => { if (s == null || String(s).trim() === "") return null; const v = typeof numBr === "function" ? numBr(s) : parseFloat(String(s).replace(",", ".")); return v == null || !isFinite(v) ? null : v; };
const U = () => (typeof ui !== "undefined" && ui) ? ui : (window.__frUi = window.__frUi || {});
const pega = id => typeof el === "function" ? el(id) : document.getElementById(id);
const redesenhar = () => { if (typeof desenhar === "function") desenhar(false); };
const emHub = () => U().modo === "hub";
const quando = ts => { if (!ts) return "—"; const d = new Date(ts * 1000); return d.toLocaleDateString("pt-BR", { day:"2-digit", month:"2-digit" }) + " " + d.toLocaleTimeString("pt-BR", { hour:"2-digit", minute:"2-digit" }); };
const dataBr = s => s ? String(s).split("-").reverse().join("/") : "—";
const real = v => v == null || !isFinite(v) ? "—" : (typeof brl === "function" ? brl(Math.round(v * 100) / 100) : "R$ " + N(v, 2));
const tx = s => s;   /* o texto vai inteiro em português: a plataforma traduz depois de desenhar (FROTA_I18N e FROTA_I18N_RX) */
function centro() { try { if (typeof localDaInstalacao === "function") { const l = localDaInstalacao(); if (l && l.lat != null) return { lat: +l.lat, lon: +l.lon, exemplo: false }; } } catch (e) {} return Object.assign({ exemplo: true }, PONTO_EXEMPLO); }
function cacheLer() { try { return JSON.parse(localStorage.getItem(CHAVE) || "null") || {}; } catch (e) { return {}; } }
function cacheGravar(o) { try { localStorage.setItem(CHAVE, JSON.stringify(o)); } catch (e) {} }

/* ════════ Frota SIMULADA (demonstração e instalação sem veículo) ════════ */
function rng(sem) { let h = 1779033703 ^ sem.length; for (let i = 0; i < sem.length; i++) { h = Math.imul(h ^ sem.charCodeAt(i), 3432918353); h = h << 13 | h >>> 19; }
  return () => { h = Math.imul(h ^ h >>> 16, 2246822507); h = Math.imul(h ^ h >>> 13, 3266489909); h ^= h >>> 16; return (h >>> 0) / 4294967296; }; }
const desloca = (c, kmL, kmN) => ({ lat: c.lat + kmN / 110.574, lon: c.lon + kmL / (111.32 * Math.cos(c.lat * Math.PI / 180)) });
function demoMundo() { const u = U(), c = centro(), hoje = Math.floor(Date.now() / 1000 / 600) * 600, chave = c.lat.toFixed(4) + c.lon.toFixed(4) + Math.floor(hoje / 3600);
  if (u.frDemo && u.frDemo.chave === chave) return u.frDemo;
  const V = [{ id: 1, tipo:"caminhao", placa:"SIM-1A01", nome:"Caminhão (SIMULADO)", combustivel:"diesel_b", tanque_l:300, consumo_esperado:35, consumo_unidade:"l_100km", no:87, motorista:"" },
    { id: 2, tipo:"carro", placa:"SIM-2B02", nome:"Carro (SIMULADO)", combustivel:"gasolina_c", tanque_l:50, consumo_esperado:10, consumo_unidade:"l_100km", no:88, motorista:"" },
    { id: 3, tipo:"trator", placa:"SIM-3C03", nome:"Trator (SIMULADO)", combustivel:"diesel_b", tanque_l:120, consumo_esperado:8, consumo_unidade:"l_h", no:89, motorista:"" }];
  const cercas = [{ id: 1, nome:"Cerca da propriedade (SIMULADO)", poligono:[[-4, -4], [-4, 5], [4, 5], [4, -4]].map(([n, l]) => { const p = desloca(c, l, n); return [p.lat, p.lon]; }), veiculos: [], ativa: true }];
  const PASSO = 180, ini = hoje - 7 * 86400, r = rng("frota" + chave);
  /* posição de cada veículo (km a leste, km ao norte) e se o motor está ligado, a cada instante (hora de Brasília) */
  const ao = (wps, f) => { let tot = 0; const seg = []; for (let i = 1; i < wps.length; i++) { const d = Math.hypot(wps[i][0] - wps[i - 1][0], wps[i][1] - wps[i - 1][1]); seg.push(d); tot += d; }
    let a = Math.max(0, Math.min(1, f)) * tot; for (let i = 0; i < seg.length; i++) { if (a <= seg[i]) { const k = seg[i] ? a / seg[i] : 0; return [wps[i][0] + k * (wps[i + 1][0] - wps[i][0]), wps[i][1] + k * (wps[i + 1][1] - wps[i][1])]; } a -= seg[i]; } return wps[wps.length - 1]; };
  const ESTRADA = [[0, 0], [1.2, 0.4], [2.2, 1.6], [3.0, 2.5]], VIZINHO = [[0, 0], [1.5, -1.2], [2.4, -2.6]], FORA = [[0, 0], [-1.5, -3.0], [-2.0, -7.0]];
  function estado(id, t) { const d = new Date(t * 1000 - FUSO_MS), h = d.getUTCHours() + d.getUTCMinutes() / 60, ult = hoje - t < 86400;
    if (id === 1) { /* caminhão: de hora em hora, 6 min até a cidade, carrega com o motor desligado, 6 min de volta; no último dia, 36 min parado com o motor ligado ao meio-dia */
      if (h >= 7 && h < 17) { const m = (h - 7) * 60 % 60;
        if (ult && h >= 12 && h < 12.6) return { xy: [3.0, 2.5], ign: 1 };
        if (m < 6) return { xy: ao(ESTRADA, m / 6), ign: 1 }; if (m < 30) return { xy: [3.0, 2.5], ign: 0 }; if (m < 36) return { xy: ao(ESTRADA, 1 - (m - 30) / 6), ign: 1 }; }
      return { xy: [0.05, -0.03], ign: 0 }; }
    if (id === 2) { /* carro: ida às 8 h, volta às 10 h 40; no último dia sai da cerca (7 km ao sul) */
      const w = ult ? FORA : VIZINHO, dur = ult ? 0.2 : 0.1;
      if (h >= 8 && h < 8 + dur) return { xy: ao(w, (h - 8) / dur), ign: 1 }; if (h >= 8 + dur && h < 10.67) return { xy: w[w.length - 1], ign: 0 };
      if (h >= 10.67 && h < 10.67 + dur) return { xy: ao(w, 1 - (h - 10.67) / dur), ign: 1 }; return { xy: [-0.04, 0.02], ign: 0 }; }
    /* trator: linhas de 0,8 km num talhão a oeste, a cerca de 6 km/h */
    if (h >= 7.5 && h < 16) { const k = (h - 7.5) * 7.5, n = Math.floor(k), fr = k - n; return { xy: [-2.6 + 0.03 * (n % 30), 0.6 + (n % 2 ? 1 - fr : fr) * 0.8], ign: 1 }; }
    return { xy: [-2.5, 0.5], ign: 0 }; }
  const pts = { 1: [], 2: [], 3: [] }, ab = [], niv = { 1: 80, 2: 70, 3: 90 }, hor = { 3: 1520 }, odo = { 1: 84200, 2: 31200 }, ant = {};
  for (let t = ini; t <= hoje; t += PASSO) { const d = new Date(t * 1000 - FUSO_MS), h = d.getUTCHours() + d.getUTCMinutes() / 60, ultDia = hoje - t < 86400;
    V.forEach(v => { const id = v.id, e = estado(id, t), p = desloca(c, e.xy[0], e.xy[1]), a = ant[id] || p, km = haversineKm(a.lat, a.lon, p.lat, p.lon), vel = km / (PASSO / 3600);
      const anda = vel >= 1, flx = e.ign ? (anda ? (id === 1 ? 13 + 2 * r() : id === 2 ? 4.5 + r() : 9 + 1.5 * r()) : (id === 3 ? 0 : 2.2)) : 0;
      niv[id] -= flx * PASSO / 3600 / v.tanque_l * 100;
      if (id === 1 && ultDia && h >= 2 && h < 2.7) niv[id] -= 0.55;          /* ANOMALIA: o nível cai parado de madrugada (vazamento ou furto) */
      if (odo[id] != null) odo[id] += km; if (hor[id] != null && e.ign) hor[id] += PASSO / 3600;
      if (niv[id] < 25) { ab.push({ id: ab.length + 1, veiculo: id, data: diaDe(t), litros: Math.round((95 - niv[id]) / 100 * v.tanque_l), preco_l: null, preco_fonte:"", odometro: odo[id] != null ? Math.round(odo[id]) : null, horimetro: hor[id] != null ? Math.round(hor[id] * 10) / 10 : null, motorista:"", comprovante: null, origem:"simulado" }); niv[id] = 95; }
      const lat = p.lat + (anda ? 0 : (r() - 0.5) * 1e-5), lon = p.lon + (anda ? 0 : (r() - 0.5) * 1e-5);
      if (e.ign || h % 0.5 < PASSO / 3600 || (id === 1 && ultDia && h >= 1.5 && h < 3)) pts[id].push({ ts: t, lat, lon, vel: Math.round(vel * 10) / 10, rumo: anda ? Math.round((Math.atan2(p.lon - a.lon, p.lat - a.lat) * 180 / Math.PI + 360) % 360) : null, flx: Math.round(flx * 100) / 100, niv: Math.round(niv[id] * 10) / 10, hor: hor[id] != null ? Math.round(hor[id] * 100) / 100 : null, odo: odo[id] != null ? Math.round(odo[id] * 10) / 10 : null, ign: e.ign, origem:"simulado" });
      ant[id] = p; }); }
  u.frDemo = { chave, veiculos: V, cercas: (cacheLer().demoCercas || cercas), pontos: pts, abastecimentos: ab, centro: c };
  return u.frDemo; }
function estadoDemo() { const u = U(), m = demoMundo(), ab = m.abastecimentos.concat(u.frDemoAb || []), memo = m.chave + "|" + ab.length + "|" + JSON.stringify(m.cercas);
  if (u.frDemoEst && u.frDemoEst.memo === memo) return u.frDemoEst.est;
  const est = estadoDemoCalc(m, ab); u.frDemoEst = { memo, est }; return est; }
function estadoDemoCalc(m, ab) {
  const vs = m.veiculos.map(v => { const a = ab.filter(x => x.veiculo === v.id).sort((x, y) => x.data < y.data ? -1 : 1), an = analise(v, m.pontos[v.id], a, m.cercas), e = co2e(v.combustivel, a.reduce((s, x) => s + x.litros, 0));
    return Object.assign({}, v, { analise: an, litros_abastecidos: a.reduce((s, x) => s + x.litros, 0), co2e_t: e ? e.t : null, co2_bio_t: e ? e.bio_t : null }); });
  const alertas = []; vs.forEach(v => v.analise.alertas.forEach(a => alertas.push(Object.assign({ veiculo: v.id, placa: v.placa }, a)))); alertas.sort((a, b) => (b.ts || 0) - (a.ts || 0));
  return { ok: true, demo: true, veiculos: vs, abastecimentos: ab.slice().reverse(), cercas: m.cercas, alertas, nos_sem_veiculo: [], para_carbono: [], custos_por_mes: custosPorMes(ab),
    retencao_dias: premissa("frota.retencao_dias"), centro: m.centro }; }
function rotaDemo(vid, dia) { const m = demoMundo(), ps = (m.pontos[vid] || []).filter(p => diaDe(p.ts) === dia), p = P(), d = distancia(ps, p["frota.gps_salto_kmh"]), lf = litrosDoFluxo(ps), hm = horasMotor(ps), tv = trechosComVazao(ps, p["frota.gps_salto_kmh"]);
  return { ok: true, pontos: ps, distancia: d, litros_fluxo: lf, horas_motor: hm, consumo: consumo(tv.litros, tv.km, tv.horas), marcha_lenta: marchaLenta(ps, p["frota.marcha_lenta_vel_kmh"], p["frota.marcha_lenta_min"]) }; }

/* ════════ Dados do hub (com cópia neste aparelho para ver sem ligação) ════════ */
let csrf = null;
async function api(metodo, url, corpo, bruto) { const op = { credentials:"same-origin", cache:"no-store" };
  if (metodo === "POST") { if (csrf == null) { try { const i = await fetch("/api/instancia", op).then(r => r.json()); csrf = i.csrf || ""; U().frPapel = i.papel || null; } catch (e) { csrf = ""; } }
    op.method = "POST"; op.headers = { "Content-Type": bruto ? "application/octet-stream" : "application/json" }; if (csrf) op.headers["X-Physis-CSRF"] = csrf; op.body = bruto || JSON.stringify(corpo || {}); }
  let r, j = {}; try { r = await fetch(url, op); try { j = await r.json(); } catch (e) {} } catch (e) { return { ok: false, erro: "sem ligação com o computador central", rede: true }; }
  if (r && !r.ok && j.ok == null) j.ok = false; return j; }
function carregarEstado(forcar) { const u = U(); if (!emHub()) return; const c = u.frEst || {};
  if (!forcar && (c.carregando || (c.em && Date.now() - c.em < 60000))) return;
  u.frEst = Object.assign({}, c, { carregando: true });
  api("GET", "api/frota/estado").then(j => { if (j && j.ok) { u.frEst = { em: Date.now(), dados: j }; const k = cacheLer(); k.estado = j; k.em = Date.now(); cacheGravar(k); }
    else { const k = cacheLer(); u.frEst = { em: Date.now(), dados: k.estado || null, offline: !!j.rede, erro: j.erro || "" }; } redesenhar(); }); }
function carregarRota(vid, dia) { const u = U(), k = vid + "|" + dia; u.frRotas = u.frRotas || {}; const c = u.frRotas[k];
  if (c && (c.carregando || Date.now() - c.em < 60000)) return c.dados || null;
  u.frRotas[k] = Object.assign({}, c || {}, { carregando: true, em: Date.now() });
  api("GET", `api/frota/rota?veiculo=${encodeURIComponent(vid)}&dia=${encodeURIComponent(dia)}`).then(j => { const cache = cacheLer(); cache.rotas = cache.rotas || {};
    if (j && j.ok) { u.frRotas[k] = { em: Date.now(), dados: j }; cache.rotas[k] = j; const ks = Object.keys(cache.rotas); if (ks.length > 20) delete cache.rotas[ks[0]]; cacheGravar(cache); }
    else u.frRotas[k] = { em: Date.now(), dados: cache.rotas[k] || null, offline: true }; redesenhar(); });
  return c && c.dados ? c.dados : null; }
/* O que a tela usa: { est, demo, semVeiculo, offline } */
function fonte() { const u = U();
  if (emHub()) { carregarEstado(false); const c = u.frEst || {}, d = c.dados;
    if (d && d.veiculos && d.veiculos.length) return { est: d, demo: false, offline: !!c.offline };
    if (!d && c.carregando) return { est: null, carregando: true };
    return { est: estadoDemo(), demo: true, semVeiculo: true, hubDados: d }; }
  return { est: estadoDemo(), demo: true }; }
function rotaDe(F, vid, dia) { return F.demo ? rotaDemo(vid, dia) : carregarRota(vid, dia); }

/* ════════ Ligações com Carbono e Gestão (só dado real; a frota simulada nunca entra) ════════ */
function paraCarbono(ano) { const u = U(); if (!emHub()) return []; const d = (u.frEst && u.frEst.dados) || cacheLer().estado; if (!d || !d.veiculos || !d.veiculos.length) return [];
  if (String(d.ano) === String(ano) && Array.isArray(d.para_carbono)) return d.para_carbono;
  return paraCarbonoDe(d.veiculos, d.abastecimentos || [], ano, {}); }
function resumoGestao() { const u = U(); if (!emHub()) return {}; const d = (u.frEst && u.frEst.dados) || cacheLer().estado; return d && d.veiculos && d.veiculos.length ? (d.custos_por_mes || {}) : {}; }

/* ════════ Mapa (SVG; projeção local em volta dos pontos) ════════ */
function moldura(pts, c) { let la0 = Infinity, la1 = -Infinity, lo0 = Infinity, lo1 = -Infinity; pts.concat([c]).forEach(p => { if (!p || p.lat == null) return; la0 = Math.min(la0, p.lat); la1 = Math.max(la1, p.lat); lo0 = Math.min(lo0, p.lon); lo1 = Math.max(lo1, p.lon); });
  const kx = Math.cos(((la0 + la1) / 2) * Math.PI / 180), mLa = Math.max(0.004, (la1 - la0) * 0.12), mLo = Math.max(0.004, (lo1 - lo0) * 0.12); la0 -= mLa; la1 += mLa; lo0 -= mLo; lo1 += mLo;
  const W = 640, H = 420, esc = Math.min(W / ((lo1 - lo0) * kx), H / (la1 - la0)), ox = (W - (lo1 - lo0) * kx * esc) / 2, oy = (H - (la1 - la0) * esc) / 2;
  return { W, H, la0, la1, lo0, lo1, kx, esc, ox, oy, x: lon => ox + (lon - lo0) * kx * esc, y: lat => H - oy - (lat - la0) * esc,
    lat: y => la0 + (H - oy - y) / esc, lon: x => lo0 + (x - ox) / (kx * esc) }; }
function marcador(v, u, sel, F) { const M = F.m, x = M.x(u.lon), y = M.y(u.lat), cor = COR[v.tipo] || COR.outro, s = sel ? 9 : 7, mov = u.vel != null && u.vel >= premissa("frota.marcha_lenta_vel_kmh");
  const rot = mov && u.rumo != null ? `<path d="M${x.toFixed(1)} ${(y - s - 7).toFixed(1)} l-4 6 h8 z" transform="rotate(${Math.round(u.rumo)} ${x.toFixed(1)} ${y.toFixed(1)})" style="fill:${cor}"/>` : "";
  const nome = `${v.placa} · ${tx(TIPOS[v.tipo] || v.tipo)} · ${mov ? tx("em movimento") : tx("parado")}`;
  return `<g class="fr-v" id="fr-v-${v.id}" tabindex="0" role="button" aria-pressed="${sel}" aria-label="${E(nome)}" data-fr-v="${v.id}"><title>${E(nome)}</title>${rot}<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${s}" style="fill:${cor};stroke:var(--sup,#FFFFFF)" stroke-width="2.5"/>
    <text x="${(x + s + 4).toFixed(1)}" y="${(y + 4).toFixed(1)}" font-size="12" font-weight="700" style="fill:var(--tinta,#1B1F23);stroke:var(--sup,#FFFFFF)" stroke-width="3" paint-order="stroke">${E(v.placa)}</text></g>`; }
function mapaSvg(F, opc) { const est = F.est, c = est.centro || centro(), vs = est.veiculos, sel = opc.sel, rota = opc.rota, cercas = est.cercas || [], ed = opc.editar;
  const todos = vs.map(v => v.analise && v.analise.ultima).filter(u => u && u.lat != null).concat(rota && rota.pontos ? rota.pontos.filter(temPos) : []).concat(cercas.flatMap(k => k.poligono.map(p => ({ lat: p[0], lon: p[1] })))).concat(ed ? ed.map(p => ({ lat: p[0], lon: p[1] })) : []);
  const M = moldura(todos, c); F.m = M; U().frMold = M;
  const kmVao = (M.lo1 - M.lo0) * M.kx * 111.32, passo = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50].find(k => k >= kmVao / 5) || 100, barra = passo * M.esc / 111.32;
  const cer = cercas.filter(k => k.ativa !== false).map(k => `<polygon points="${k.poligono.map(p => M.x(p[1]).toFixed(1) + "," + M.y(p[0]).toFixed(1)).join(" ")}" style="fill:var(--ok-f,#DCEBD8);fill-opacity:.35;stroke:var(--ok-t,#1F4A1C)" stroke-width="2" stroke-dasharray="6 4"><title>${E(tx("Cerca") + ": " + k.nome)}</title></polygon>`).join("");
  const vcor = sel != null ? COR[(vs.find(v => v.id === sel) || {}).tipo] || COR.outro : COR.outro;
  const linha = rota && rota.pontos && rota.pontos.filter(temPos).length > 1 ? `<polyline fill="none" style="stroke:${vcor}" stroke-width="3" stroke-linejoin="round" points="${rota.pontos.filter(temPos).map(p => M.x(p.lon).toFixed(1) + "," + M.y(p.lat).toFixed(1)).join(" ")}"/>` : "";
  const ev = (opc.eventos || []).map(a => `<g aria-hidden="true"><circle cx="${M.x(a.lon).toFixed(1)}" cy="${M.y(a.lat).toFixed(1)}" r="11" style="fill:none;stroke:var(--al-t,#7A2214)" stroke-width="2.5"/><path d="M${M.x(a.lon).toFixed(1)} ${(M.y(a.lat) - 6).toFixed(1)}v7m0 3v1" style="stroke:var(--al-t,#7A2214)" stroke-width="2.5"/></g>`).join("");
  const edit = ed ? `<polyline fill="none" points="${ed.concat(ed.length > 2 ? [ed[0]] : []).map(p => M.x(p[1]).toFixed(1) + "," + M.y(p[0]).toFixed(1)).join(" ")}" style="stroke:var(--acao,#1A4D2E)" stroke-width="2.5"/>${ed.map((p, i) => `<circle cx="${M.x(p[1]).toFixed(1)}" cy="${M.y(p[0]).toFixed(1)}" r="5" style="fill:var(--acao,#1A4D2E)"/><text x="${(M.x(p[1]) + 7).toFixed(1)}" y="${(M.y(p[0]) - 6).toFixed(1)}" font-size="11" style="fill:var(--tinta,#1B1F23)">${i + 1}</text>`).join("")}` : "";
  const cur = ed && opc.cursor ? `<g aria-hidden="true"><path d="M${M.x(opc.cursor.lon).toFixed(1)} ${(M.y(opc.cursor.lat) - 12).toFixed(1)}v24M${(M.x(opc.cursor.lon) - 12).toFixed(1)} ${M.y(opc.cursor.lat).toFixed(1)}h24" style="stroke:var(--tinta,#1B1F23)" stroke-width="2"/></g>` : "";
  const marc = vs.filter(v => v.analise && v.analise.ultima && v.analise.ultima.lat != null).map(v => marcador(v, v.analise.ultima, v.id === sel, F)).join("");
  const nome = ed ? tx("Mapa para desenhar a cerca: clique para pôr um vértice; com o teclado, as setas movem a mira e Enter põe o vértice") : tx("Mapa da frota: última posição de cada veículo e a rota do dia escolhido; a tabela abaixo tem a mesma informação");
  return `<svg id="fr-mapa" viewBox="0 0 ${M.W} ${M.H}" width="100%" style="max-width:${M.W}px;background:var(--sup,#FFFFFF);border:1px solid var(--linha,#D9D3C2);border-radius:10px;touch-action:manipulation" role="group" aria-label="${E(nome)}"${ed ? ' tabindex="0" data-fr-mapa="editar"' : ""}>
    ${cer}${linha}${ev}${edit}${cur}<circle cx="${M.x(c.lon).toFixed(1)}" cy="${M.y(c.lat).toFixed(1)}" r="6" style="fill:none;stroke:var(--marca,#4A8A5A)" stroke-width="3"><title>${E(tx(c.exemplo ? "Ponto de exemplo (sem local da instalação)" : "Local da instalação"))}</title></circle>${marc}
    <text x="${M.W - 16}" y="22" font-size="13" font-weight="700" text-anchor="middle" style="fill:var(--tinta,#1B1F23)">N</text><path d="M${M.W - 16} 26 l-5 12 h10 z" style="fill:var(--tinta,#1B1F23)"/>
    <line x1="12" y1="${M.H - 14}" x2="${(12 + barra).toFixed(1)}" y2="${M.H - 14}" style="stroke:var(--tinta,#1B1F23)" stroke-width="3"/><text x="12" y="${M.H - 20}" font-size="11" style="fill:var(--tinta,#1B1F23)">${f1(passo, passo < 1 ? 1 : 0)} km</text></svg>`; }

/* ════════ Peças da tela ════════ */
const cartao = (id, tit, numero, un) => `<section class="cartao" aria-labelledby="h-${id}"><h3 id="h-${id}" class="t3">${tit}</h3><span class="numero">${numero}</span><span class="t2">${un}</span></section>`;
const campo = (k, rot, val, ph, ajuda, tipo) => `<div><label for="fr-${k}">${rot}</label><input id="fr-${k}" type="${tipo || "text"}"${tipo ? "" : ' inputmode="decimal"'} data-fr-k="${k}" value="${E(val == null ? "" : val)}" placeholder="${E(ph || "")}" style="width:100%"${ajuda ? ` aria-describedby="fr-${k}-a"` : ""}>${ajuda ? `<span id="fr-${k}-a" class="t2 pq">${ajuda}</span>` : ""}</div>`;
const selecao = (k, rot, ops, atual) => `<div><label for="fr-${k}">${rot}</label><select id="fr-${k}" data-fr-k="${k}" style="width:100%">${ops.map(([v, n]) => `<option value="${E(v)}" ${String(v) === String(atual) ? "selected" : ""}>${E(n)}</option>`).join("")}</select></div>`;
const tabela = (cap, cab, linhas) => `<div class="rolagem"><table><caption>${E(cap)}</caption><thead><tr>${cab.map(h => `<th scope="col">${h}</th>`).join("")}</tr></thead><tbody>${linhas.join("")}</tbody></table></div>`;
const nomeV = v => `${v.placa}${v.nome ? " · " + v.nome : ""}`;
function aviso(F) { const ls = [];
  if (F.demo) ls.push(`<div class="faixa in" role="note"><strong>${F.semVeiculo ? "Nenhum veículo cadastrado ainda." : "Frota SIMULADA de exemplo."}</strong> <span>${F.semVeiculo ? "Abaixo, uma frota SIMULADA. Cadastre um veículo na parte Veículos e ligue o rastreador (linha TIPO:VEI) para ver os dados reais." : "Três veículos SIMULADOS em volta do local da instalação. Nada daqui entra no Carbono nem na Gestão."}</span></div>`);
  if (F.offline) ls.push(`<div class="faixa at" role="status"><strong>Sem ligação com o computador central.</strong> <span>Mostrando os pontos guardados neste aparelho.</span></div>`);
  if (F.est && F.est.centro && F.est.centro.exemplo) ls.push(`<p class="t2 pq">Mapa em volta de um ponto de exemplo.</p>`, `<div class="t2 pq">${typeof avisoSemLocal === "function" ? avisoSemLocal() : "Local não informado: preencha na página Início."}</div>`);
  return ls.join(""); }
const lgpd = () => `<p class="faixa in" role="note"><strong>LGPD.</strong> <span>A posição de um veículo mostra onde a pessoa que dirige está: é dado pessoal. Avise quem dirige, use só para a gestão da frota e guarde pelo tempo da retenção. O motorista é só um código opcional; a exportação sai sem ele.</span></p>`;
function diaEscolhido(u) { return u.frDia && /^\d{4}-\d{2}-\d{2}$/.test(u.frDia) ? u.frDia : diaDe(Date.now() / 1000); }
function situacao(v) { const a = v.analise && v.analise.ultima; if (!a) return "sem leitura"; const parado = !(a.vel >= premissa("frota.marcha_lenta_vel_kmh")); return a.ign === 0 || (a.ign == null && a.flx === 0) ? "desligado" : parado ? "parado, motor ligado" : "em movimento"; }

function parteMapa(F) { const u = U(), est = F.est, vs = est.veiculos, sel = vs.some(v => v.id === u.frSel) ? u.frSel : vs[0].id, dia = diaEscolhido(u), v = vs.find(x => x.id === sel);
  u.frSel = sel; const rota = rotaDe(F, sel, dia), ev = est.alertas.filter(a => a.veiculo === sel && a.lat != null && a.ts && diaDe(a.ts) === dia);
  const ctrl = `<div class="precos">${selecao("sel", "Veículo", vs.map(x => [x.id, nomeV(x)]), sel)}${campo("dia", "Dia da rota", dia, "", null, "date")}</div>`;
  const lin = vs.map(x => { const a = x.analise && x.analise.ultima || {}; return `<tr><th scope="row">${E(nomeV(x))}</th><td>${E(TIPOS[x.tipo] || x.tipo)}</td><td>${E(situacao(x))}</td><td>${f1(a.vel, 0)}</td><td>${f1(a.niv, 0)}</td><td>${a.lat != null ? a.lat.toFixed(5).replace(".", ",") : "—"}</td><td>${a.lon != null ? a.lon.toFixed(5).replace(".", ",") : "—"}</td><td>${E(quando(a.ts))}</td></tr>`; });
  const r = rota && rota.pontos ? rota : null, ml = r ? r.marcha_lenta : null;
  const resumo = r ? `<div class="grade">${cartao("fr-km", "Distância no dia", f1(r.distancia.km, 1), r.distancia.fonte === "odometro" ? "km pelo odômetro" : "km pelo GPS")}${cartao("fr-l", "Combustível pela vazão", f1(r.litros_fluxo, 1), "litros")}
    ${cartao("fr-c", "Consumo no dia", f1(v.consumo_unidade === "l_h" ? r.consumo.l_h : r.consumo.l_100km, 1), UNIDADES[v.consumo_unidade])}${cartao("fr-ml", "Marcha lenta", f1(ml ? ml.horas : null, 1), "horas")}</div>` : `<p class="t2" role="status">${emHub() && !F.demo ? "Carregando a rota…" : "Sem pontos neste dia."}</p>`;
  const pts = r ? r.pontos : [];
  const tabRota = pts.length ? `<details><summary>Ver os pontos da rota (${pts.length})</summary>${tabela("Pontos da rota do dia: hora, posição, velocidade e nível", ["Hora", "Latitude", "Longitude", "km/h", "Vazão (L/h)", "Nível (%)"],
    pts.filter((p, i) => i % Math.max(1, Math.ceil(pts.length / 200)) === 0).map(p => `<tr><th scope="row">${E(quando(p.ts))}</th><td>${p.lat != null ? p.lat.toFixed(5).replace(".", ",") : "—"}</td><td>${p.lon != null ? p.lon.toFixed(5).replace(".", ",") : "—"}</td><td>${f1(p.vel, 0)}</td><td>${f1(p.flx, 1)}</td><td>${f1(p.niv, 0)}</td></tr>`))}</details>` : "";
  const soltos = (F.hubDados || est).nos_sem_veiculo || [];
  return `<section class="cartao" aria-labelledby="h-fr-mapa"><h2 id="h-fr-mapa">Onde está cada veículo</h2>${ctrl}${mapaSvg(F, { sel, rota: r, eventos: ev })}
    <p class="t2 pq">Escolha um veículo no mapa (clique ou Enter) ou na lista. Círculo vermelho: alerta naquele dia. Tracejado verde: cerca.</p>${resumo}</section>
    <section class="cartao" aria-labelledby="h-fr-lista"><h2 id="h-fr-lista">Veículos e última posição</h2>${tabela("Veículos: situação, velocidade, nível, posição e última leitura", ["Veículo", "Tipo", "Situação", "km/h", "Nível (%)", "Latitude", "Longitude", "Última leitura"], lin)}${tabRota}
    ${soltos.length ? `<p class="t2">${soltos.map(s => `<span>Nó ${String(s.no).padStart(2, "0")} manda pontos e não tem veículo ligado.</span>`).join(" ")}</p>` : ""}</section>`; }

function parteAbastecimentos(F) { const u = U(), est = F.est, vs = est.veiculos, fm = u.frAb || {}, sel = fm.veiculo || vs[0].id, ab = est.abastecimentos || [];
  const form = `<section class="cartao" aria-labelledby="h-fr-abn"><h2 id="h-fr-abn">Registrar um abastecimento</h2><div class="precos">${selecao("ab-veiculo", "Veículo", vs.map(x => [x.id, nomeV(x)]), sel)}
    ${campo("ab-data", "Data", fm.data || diaDe(Date.now() / 1000), "", null, "date")}${campo("ab-litros", "Litros (ou m³ de GNV)", fm.litros, "ex.: 120")}
    ${campo("ab-preco_l", "Preço por litro (R$), opcional", fm.preco_l, "ex.: 6,19")}${selecao("ab-preco_fonte", "Fonte do preço", [["", "—"]].concat(Object.entries(FONTES_PRECO)), fm.preco_fonte || "")}
    ${campo("ab-odometro", "Odômetro (km), opcional", fm.odometro, "")}${campo("ab-horimetro", "Horímetro (h), opcional", fm.horimetro, "")}
    ${campo("ab-motorista", "Código do motorista, opcional", fm.motorista, "ex.: M03", "Só um código. Nada de nome nem documento.")}
    ${emHub() && !F.demo ? `<div><label for="fr-ab-arquivo">Comprovante (PDF ou foto, até 10 MB), opcional</label><input id="fr-ab-arquivo" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" style="width:100%"><span class="t2 pq">Só a equipe vê.</span></div>` : ""}</div>
    <button type="button" id="fr-b-ab" class="principal" data-fr-acao="abastecer">Guardar abastecimento</button>${u.frAbMsg ? `<p class="t2" role="status">${E(u.frAbMsg)}</p>` : ""}</section>`;
  const placa = id => (vs.find(v => v.id === id) || {}).placa || "—";
  const lin = ab.slice(0, 200).map(a => `<tr><th scope="row">${E(dataBr(a.data))}</th><td>${E(placa(a.veiculo))}</td><td>${f1(a.litros, 1)}</td><td>${a.preco_l != null ? real(a.preco_l) : "—"}</td><td>${a.preco_l != null ? E(FONTES_PRECO[a.preco_fonte] || a.preco_fonte) : "sem preço"}</td><td>${a.preco_l != null ? real(a.preco_l * a.litros) : "—"}</td><td>${f1(a.odometro, 0)}</td><td>${f1(a.horimetro, 1)}</td><td>${a.comprovante ? `<a href="api/frota/comprovante/${+a.comprovante}">Ver comprovante</a>` : "—"}</td>${!F.demo && emHub() ? `<td><button type="button" data-fr-acao="ab-remover" data-fr-id="${+a.id}" aria-label="${E(tx("Apagar o abastecimento de") + " " + dataBr(a.data))}">Apagar</button></td>` : ""}</tr>`);
  return form + `<section class="cartao" aria-labelledby="h-fr-abl"><h2 id="h-fr-abl">Abastecimentos</h2>${ab.length ? tabela("Abastecimentos: data, veículo, litros, preço com a fonte, custo, odômetro, horímetro e comprovante", ["Data", "Veículo", "Litros", "Preço por litro", "Fonte do preço", "Custo", "Odômetro", "Horímetro", "Comprovante"].concat(!F.demo && emHub() ? ["<span class=\"so-leitor\">Ações</span>"] : []), lin) : `<p class="t2">Nenhum abastecimento ainda.</p>`}
    <p class="t2 pq">Preço só com a fonte (nota, cartão, bomba ou estimado). Sem preço, o abastecimento conta os litros e não o custo.</p>${emHub() && !F.demo ? `<p><a class="botao" href="api/frota/exportar?tipo=abastecimentos">Baixar os abastecimentos (CSV, sem motorista)</a> <a class="botao" href="api/frota/exportar?tipo=pontos">Baixar os pontos de GPS (CSV)</a></p>` : ""}</section>`; }

function graficoConsumo(v) { const am = (v.analise && v.analise.amostras) || [], nm = v.analise && v.analise.normal || {}, un = UNIDADES[v.consumo_unidade];
  if (!am.length) return `<p class="t2">Sem amostras de consumo ainda: precisa da vazão do rastreador ou de abastecimentos com odômetro (ou horímetro).</p>`;
  const W = 640, H = 220, m = { l: 48, r: 12, t: 14, b: 30 }, ys = am.map(a => a.valor).concat(nm.mediana != null ? [nm.mediana] : []), y1 = Math.max(...ys) * 1.15 || 1;
  const bw = (W - m.l - m.r) / am.length, sy = y => H - m.b - y / y1 * (H - m.t - m.b);
  const barras = am.map((a, i) => `<rect x="${(m.l + i * bw + bw * 0.15).toFixed(1)}" y="${sy(a.valor).toFixed(1)}" width="${(bw * 0.7).toFixed(1)}" height="${(H - m.b - sy(a.valor)).toFixed(1)}" style="fill:${COR[v.tipo] || COR.outro}"><title>${E(dataBr(a.data) + ": " + f1(a.valor, 1) + " " + un)}</title></rect>`).join("");
  const ref = nm.mediana != null ? `<line x1="${m.l}" x2="${W - m.r}" y1="${sy(nm.mediana).toFixed(1)}" y2="${sy(nm.mediana).toFixed(1)}" style="stroke:var(--tinta,#1B1F23)" stroke-dasharray="5 4" stroke-width="1.5"/><text x="${W - m.r}" y="${(sy(nm.mediana) - 4).toFixed(1)}" font-size="11" text-anchor="end" style="fill:var(--tinta,#1B1F23)">${E(tx("normal") + " " + f1(nm.mediana, 1))}</text>` : "";
  const esp = v.consumo_esperado ? `<line x1="${m.l}" x2="${W - m.r}" y1="${sy(v.consumo_esperado).toFixed(1)}" y2="${sy(v.consumo_esperado).toFixed(1)}" style="stroke:var(--agua,#2F7D5B)" stroke-dasharray="2 3" stroke-width="1.5"/>` : "";
  return `<figure style="margin:0"><svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px" role="img" aria-label="${E(tx("Consumo de") + " " + v.placa + ", " + un + ": " + am.length + " " + tx("amostras"))}">
    <line x1="${m.l}" y1="${H - m.b}" x2="${W - m.r}" y2="${H - m.b}" style="stroke:var(--linha,#D9D3C2)"/><text x="${m.l - 6}" y="${m.t + 8}" font-size="11" text-anchor="end" style="fill:var(--tinta2,#4A4F44)">${f1(y1, 0)}</text><text x="${m.l - 6}" y="${H - m.b}" font-size="11" text-anchor="end" style="fill:var(--tinta2,#4A4F44)">0</text>
    <text x="${m.l}" y="${H - 10}" font-size="11" style="fill:var(--tinta2,#4A4F44)">${E(dataBr(am[0].data))}</text><text x="${W - m.r}" y="${H - 10}" font-size="11" text-anchor="end" style="fill:var(--tinta2,#4A4F44)">${E(dataBr(am[am.length - 1].data))}</text>${barras}${ref}${esp}</svg>
    <figcaption class="t2 pq"><span>${E(un)}</span> ${nm.mediana != null ? `<span>Tracejado escuro: normal aprendido (mediana).</span>` : ""} ${v.consumo_esperado ? `<span>Pontilhado azul: consumo esperado do cadastro.</span>` : ""}</figcaption></figure>
    <details><summary>Ver os números do consumo</summary>${tabela("Amostras de consumo: data, valor e de onde veio", ["Data", un, "Fonte"], am.slice().reverse().map(a => `<tr><th scope="row">${E(dataBr(a.data))}</th><td>${f1(a.valor, 2)}</td><td>${E(a.fonte)}</td></tr>`))}</details>`; }

function parteConsumo(F) { const u = U(), est = F.est, vs = est.veiculos, sel = vs.some(v => v.id === u.frSelC) ? u.frSelC : vs[0].id, v = vs.find(x => x.id === sel), nm = v.analise.normal || {};
  const meses = {}; vs.forEach(x => Object.entries(x.analise.dias || {}).forEach(([d, o]) => { const k = d.slice(0, 7) + "|" + x.id, y = meses[k] = meses[k] || { mes: d.slice(0, 7), v: x, km: 0, lf: 0, hm: 0, ml: 0 }; y.km += o.km || 0; y.lf += o.litros_fluxo || 0; y.hm += o.horas_motor || 0; y.ml += o.horas_marcha_lenta || 0; }));
  const abMes = {}; (est.abastecimentos || []).forEach(a => { const k = String(a.data).slice(0, 7) + "|" + a.veiculo, y = abMes[k] = abMes[k] || { l: 0, c: 0 }; y.l += a.litros; if (a.preco_l != null) y.c += a.litros * a.preco_l; });
  const linM = Object.keys(meses).sort().reverse().map(k => { const y = meses[k], a = abMes[k] || { l: 0, c: 0 }; return `<tr><th scope="row">${E(y.mes.split("-").reverse().join("/"))}</th><td>${E(y.v.placa)}</td><td>${f1(y.km, 0)}</td><td>${f1(y.lf, 0)}</td><td>${f1(a.l, 0)}</td><td>${f1(y.hm, 1)}</td><td>${f1(y.ml, 1)}</td><td>${a.c ? real(a.c) : "—"}</td></tr>`; });
  const linD = Object.entries(v.analise.dias || {}).sort((a, b) => a[0] < b[0] ? 1 : -1).slice(0, 31).map(([d, o]) => `<tr><th scope="row">${E(dataBr(d))}</th><td>${f1(o.km, 1)}</td><td>${f1(o.litros_fluxo, 1)}</td><td>${f1(o.horas_motor, 1)}</td><td>${f1(o.horas_marcha_lenta, 1)}</td><td>${f1(o.l_100km, 1)}</td><td>${f1(o.l_h, 1)}</td></tr>`);
  const linE = vs.map(x => `<tr><th scope="row">${E(nomeV(x))}</th><td>${E(NOME_COMB[x.combustivel] || x.combustivel)}</td><td>${f1(x.litros_abastecidos, 0)}</td><td>${f1(x.co2e_t, 2)}</td><td>${f1(x.co2_bio_t, 2)}</td></tr>`);
  const normalTxt = nm.n ? `<p class="t2"><span>Normal aprendido:</span> <strong>${f1(nm.mediana, 1)} ${E(UNIDADES[v.consumo_unidade])}</strong> <span>(mediana; média móvel exponencial</span> <strong>${f1(nm.ewma, 1)}</strong><span>)</span> <span>com</span> <strong>${nm.n}</strong> <span>amostras.</span>${nm.n < premissa("frota.anomalia_amostra_min") ? ` <span>Ainda aprendendo: o alerta de consumo começa com</span> <strong>${premissa("frota.anomalia_amostra_min")}</strong> <span>amostras.</span>` : ""}</p>` : "";
  return `<section class="cartao" aria-labelledby="h-fr-cg"><h2 id="h-fr-cg">Consumo por veículo</h2><div class="precos">${selecao("selc", "Veículo", vs.map(x => [x.id, nomeV(x)]), sel)}</div>${graficoConsumo(v)}${normalTxt}</section>
    <section class="cartao" aria-labelledby="h-fr-cd"><h2 id="h-fr-cd">Por dia</h2>${linD.length ? tabela("Por dia: distância, combustível pela vazão, horas de motor, marcha lenta e consumo", ["Dia", "km", "Litros (vazão)", "Horas de motor", "Marcha lenta (h)", "L/100 km", "L/h"], linD) : `<p class="t2">Sem pontos de GPS ainda.</p>`}</section>
    <section class="cartao" aria-labelledby="h-fr-cm"><h2 id="h-fr-cm">Por mês</h2>${linM.length ? tabela("Por mês e veículo: distância, litros, horas e custo", ["Mês", "Veículo", "km", "Litros (vazão)", "Litros abastecidos", "Horas de motor", "Marcha lenta (h)", "Custo"], linM) : `<p class="t2">Sem dados no mês.</p>`}</section>
    <section class="cartao" aria-labelledby="h-fr-ce"><h2 id="h-fr-ce">Emissões dos abastecimentos</h2>${tabela("Emissões por veículo, pelos fatores do Carbono", ["Veículo", "Combustível", "Litros abastecidos", "tCO₂e (fóssil)", "tCO₂ biogênico (à parte)"], linE)}
    <p class="t2 pq"><span>Mesma conta e mesmos fatores do Carbono (combustão móvel, GHG Protocol).</span> <span>${F.demo ? "A frota SIMULADA não entra no inventário." : "No Carbono, a combustão móvel passa a usar estes litros medidos (o digitado fica de reserva)."}</span></p></section>`; }

function textoAlerta(a, vs) { const v = vs.find(x => x.id === a.veiculo) || {}, un = a.unidade || "";
  if (a.tipo === "consumo") return [`Consumo acima do normal`, `${f1(a.valor, 1)} ${un} em ${dataBr(a.data)}; normal ${f1(a.mediana, 1)} ${un}, z robusto ${f1(a.z, 1)}, n = ${a.n} amostras (${a.fonte})`];
  if (a.tipo === "queda_nivel") return [`Nível caiu com o veículo parado`, `${f1(a.queda_pct, 1)} % do tanque${a.litros != null ? ` (cerca de ${f1(a.litros, 0)} L)` : ""} entre ${quando(a.ts_ini)} e ${quando(a.ts_fim)}: vazamento ou furto possível`];
  if (a.tipo === "marcha_lenta") return [`Marcha lenta longa`, `${f1(a.min, 0)} min parado com o motor ligado, até ${quando(a.ts_fim)}`];
  if (a.tipo === "cerca") return [`Saiu da cerca`, `${a.nome} em ${quando(a.ts)}`];
  return [a.tipo, ""]; }
function parteAlertas(F) { const est = F.est, al = est.alertas || [], p = P();
  const lin = al.slice(0, 100).map(a => { const [t, d] = textoAlerta(a, est.veiculos); return `<tr><th scope="row">${E(a.placa || "")}</th><td><span class="selo ${a.nivel === "alarme" ? "al" : "at"}">${E(t)}</span></td><td>${E(d)}</td><td>${a.lat != null ? a.lat.toFixed(5).replace(".", ",") + " ; " + a.lon.toFixed(5).replace(".", ",") : "—"}</td></tr>`; });
  return `<section class="cartao" aria-labelledby="h-fr-al"><h2 id="h-fr-al">Alertas</h2>${al.length ? `<div class="faixa ${al.some(a => a.nivel === "alarme") ? "al" : "at"}" role="status"><strong>${al.length}</strong> <span>alertas nos últimos 31 dias.</span></div>` + tabela("Alertas: veículo, tipo, o que aconteceu e onde", ["Veículo", "Tipo", "O que aconteceu", "Onde"], lin) : `<div class="faixa ok" role="status">Nenhum alerta na frota agora.</div>`}</section>
    <section class="cartao" aria-labelledby="h-fr-lim"><h2 id="h-fr-lim">Limites usados</h2>${tabela("Limites dos alertas (premissas, todas a conferir)", ["Limite", "Valor", "Situação"], [
      ["Consumo acima do normal: z robusto maior que", f1(p["frota.anomalia_z"], 1)], ["e pelo menos acima da mediana (%)", f1(p["frota.anomalia_desvio_min_pct"], 0)], ["Amostras antes de dizer o normal", f1(p["frota.anomalia_amostra_min"], 0)], ["Peso da média móvel exponencial", f1(p["frota.ewma_alfa"], 2)],
      ["Queda de nível parado (% do tanque)", f1(p["frota.queda_nivel_pct"], 1)], ["Distância que ainda conta como parado (km)", f1(p["frota.parado_distancia_km"], 2)], ["Marcha lenta: abaixo de (km/h)", f1(p["frota.marcha_lenta_vel_kmh"], 1)],
      ["Marcha lenta longa (min)", f1(p["frota.marcha_lenta_min"], 0)], ["Salto de GPS descartado acima de (km/h)", f1(p["frota.gps_salto_kmh"], 0)]].map(([n, v]) => `<tr><th scope="row">${E(n)}</th><td>${v}</td><td><span class="selo at">conferir</span></td></tr>`))}</section>`; }

function parteCercas(F) { const u = U(), est = F.est, ed = u.frEd || null, c = est.centro || centro();
  if (ed && !u.frCursor) u.frCursor = { lat: c.lat, lon: c.lon };
  const lista = (est.cercas || []).map(k => `<tr><th scope="row">${E(k.nome)}</th><td>${k.poligono.length}</td><td>${k.ativa === false ? "desligada" : "ligada"}</td><td>${k.veiculos && k.veiculos.length ? E(k.veiculos.map(id => (est.veiculos.find(v => v.id === id) || {}).placa || id).join(", ")) : "todos"}</td><td><button type="button" data-fr-acao="cerca-editar" data-fr-id="${k.id}" aria-label="${E(tx("Mudar a cerca") + " " + k.nome)}">Editar</button> <button type="button" data-fr-acao="cerca-remover" data-fr-id="${k.id}" aria-label="${E(tx("Apagar a cerca") + " " + k.nome)}">Apagar</button></td></tr>`);
  const editor = ed ? `<section class="cartao" aria-labelledby="h-fr-ed"><h2 id="h-fr-ed">Desenhar a cerca</h2><div class="precos">${campo("ced-nome", "Nome da cerca", ed.nome || "", "ex.: Sede e talhões")}</div>
    ${mapaSvg(F, { editar: ed.poligono, cursor: u.frCursor })}<p class="t2 pq" id="fr-ed-ajuda">Clique no mapa para pôr um vértice. Pelo teclado: foque o mapa, mova a mira com as setas (Shift anda mais) e aperte Enter. Ou digite a latitude e a longitude abaixo.</p>
    <div class="precos">${campo("ced-lat", "Latitude do vértice", u.frCursor ? u.frCursor.lat.toFixed(6).replace(".", ",") : "", "-22,50")}${campo("ced-lon", "Longitude do vértice", u.frCursor ? u.frCursor.lon.toFixed(6).replace(".", ",") : "", "-43,18")}</div>
    <p style="display:flex;flex-wrap:wrap;gap:8px"><button type="button" id="fr-b-vert" data-fr-acao="vertice">Acrescentar vértice</button><button type="button" data-fr-acao="vertice-tirar">Tirar o último vértice</button><button type="button" id="fr-b-cerca" class="principal" data-fr-acao="cerca-gravar">Guardar cerca</button><button type="button" data-fr-acao="cerca-cancelar">Cancelar</button></p>
    ${ed.poligono.length ? tabela("Vértices da cerca", ["Vértice", "Latitude", "Longitude"], ed.poligono.map((p, i) => `<tr><th scope="row">${i + 1}</th><td>${p[0].toFixed(6).replace(".", ",")}</td><td>${p[1].toFixed(6).replace(".", ",")}</td></tr>`)) : `<p class="t2">Nenhum vértice ainda (a cerca precisa de 3 ou mais).</p>`}
    ${u.frCercaMsg ? `<p class="t2" role="status">${E(u.frCercaMsg)}</p>` : ""}</section>` : `<p><button type="button" id="fr-b-nova-cerca" class="principal" data-fr-acao="cerca-nova">Desenhar uma cerca nova</button></p>`;
  return `<section class="cartao" aria-labelledby="h-fr-ce2"><h2 id="h-fr-ce2">Cercas</h2><p class="t2 apoio">Um alerta aparece quando um veículo sai de uma cerca ligada.</p>${lista.length ? tabela("Cercas: nome, vértices, situação e veículos", ["Cerca", "Vértices", "Situação", "Veículos", "<span class=\"so-leitor\">Ações</span>"], lista) : `<p class="t2">Nenhuma cerca ainda.</p>`}${u.frCercaMsg && !ed ? `<p class="t2" role="status">${E(u.frCercaMsg)}</p>` : ""}</section>${editor}`; }

function parteVeiculos(F) { const u = U(), est = F.est, fm = u.frVe || {}, soltos = (F.hubDados || est).nos_sem_veiculo || [];
  const lin = est.veiculos.map(v => `<tr><th scope="row">${E(nomeV(v))}</th><td>${E(TIPOS[v.tipo] || v.tipo)}</td><td>${E(NOME_COMB[v.combustivel] || v.combustivel)}</td><td>${f1(v.tanque_l, 0)}</td><td>${v.consumo_esperado != null ? f1(v.consumo_esperado, 1) + " " + E(UNIDADES[v.consumo_unidade]) : "—"}</td><td>${v.no != null ? "Nó " + String(v.no).padStart(2, "0") : "—"}</td>${!F.demo ? `<td><button type="button" data-fr-acao="ve-editar" data-fr-id="${v.id}" aria-label="${E(tx("Editar") + " " + v.placa)}">Editar</button></td>` : ""}</tr>`);
  const form = `<section class="cartao" aria-labelledby="h-fr-ven"><h2 id="h-fr-ven">${fm.id ? "Editar veículo" : "Cadastrar veículo"}</h2><div class="precos">${selecao("ve-tipo", "Tipo", Object.entries(TIPOS), fm.tipo || "caminhao")}
    ${campo("ve-placa", "Placa ou etiqueta", fm.placa, "ex.: ABC1D23 ou TR-02")}${campo("ve-nome", "Apelido, opcional", fm.nome, "ex.: Caminhão do leite")}
    ${selecao("ve-combustivel", "Combustível", COMBUSTIVEIS.map(k => [k, NOME_COMB[k]]), fm.combustivel || "diesel_b")}${campo("ve-tanque_l", "Tanque (litros)", fm.tanque_l, "ex.: 300")}
    ${campo("ve-consumo_esperado", "Consumo esperado", fm.consumo_esperado, "ex.: 35", "Do manual ou da medição; serve só de referência.")}${selecao("ve-consumo_unidade", "Unidade do consumo", Object.entries(UNIDADES), fm.consumo_unidade || ((fm.tipo || "caminhao") === "trator" || fm.tipo === "maquina" ? "l_h" : "l_100km"))}
    ${campo("ve-no", "Nó V6 do rastreador (1 a 99), opcional", fm.no, soltos.length ? "ex.: " + soltos[0].no : "ex.: 61")}${campo("ve-motorista", "Código do motorista, opcional", fm.motorista, "ex.: M03", "Só um código (LGPD).")}</div>
    <button type="button" id="fr-b-ve" class="principal" data-fr-acao="ve-gravar"${F.demo && !emHub() ? " disabled" : ""}>${fm.id ? "Guardar alteração" : "Cadastrar"}</button>${fm.id ? ` <button type="button" data-fr-acao="ve-cancelar">Cancelar</button> <button type="button" data-fr-acao="ve-remover" data-fr-id="${+fm.id}">Apagar o veículo e os dados dele</button>` : ""}
    ${F.demo && !emHub() ? `<p class="t2 pq">Na demonstração, a frota é SIMULADA: o cadastro funciona na plataforma instalada.</p>` : ""}${u.frVeMsg ? `<p class="t2" role="status">${E(u.frVeMsg)}</p>` : ""}</section>`;
  return `<section class="cartao" aria-labelledby="h-fr-vl"><h2 id="h-fr-vl">Veículos</h2>${tabela("Veículos cadastrados: tipo, combustível, tanque, consumo esperado e nó", ["Veículo", "Tipo", "Combustível", "Tanque (L)", "Consumo esperado", "Nó V6"].concat(!F.demo ? ["<span class=\"so-leitor\">Ações</span>"] : []), lin)}</section>${form}`; }

function parteImportar(F) { const u = U(), est = F.est, fm = u.frIm || {}, r = u.frImRes;
  if (F.demo) return `<section class="cartao" aria-labelledby="h-fr-im"><h2 id="h-fr-im">Importar CSV</h2><p class="t2">Na plataforma instalada: o arquivo exportado do rastreador ou do cartão-combustível entra por veículo, conferido inteiro antes de gravar (tudo ou nada), com o resumo SHA-256.</p>${colunasCsv()}</section>`;
  return `<section class="cartao" aria-labelledby="h-fr-im"><h2 id="h-fr-im">Importar CSV</h2><p class="t2 apoio">O arquivo exportado do rastreador ou do cartão-combustível, por veículo. Primeiro o sistema confere o arquivo inteiro; se uma linha estiver errada, nada é gravado.</p>
    <div class="precos">${selecao("im-veiculo", "Veículo", est.veiculos.map(x => [x.id, nomeV(x)]), fm.veiculo || est.veiculos[0].id)}${selecao("im-tipo", "Tipo do arquivo", [["rastreador", "Rastreador (pontos de GPS)"], ["cartao", "Cartão-combustível (abastecimentos)"]], fm.tipo || "rastreador")}
    <div><label for="fr-im-arquivo">Arquivo CSV</label><input id="fr-im-arquivo" type="file" accept=".csv,text/csv" style="width:100%"></div></div>
    <p style="display:flex;flex-wrap:wrap;gap:8px"><button type="button" id="fr-b-im" data-fr-acao="importar-conferir">Conferir o arquivo</button>${r && r.ok && r.simulado ? `<button type="button" id="fr-b-im2" class="principal" data-fr-acao="importar-gravar">Gravar as ${r.linhas} linhas</button>` : ""}</p>
    ${r ? `<div class="faixa ${r.ok ? "ok" : "al"}" role="status">${r.ok ? `<strong>${r.simulado ? "Arquivo conferido." : "Importado."}</strong> <span>Linhas:</span> <strong>${r.linhas}</strong>${r.novas != null ? ` <span>novas:</span> <strong>${r.novas}</strong>` : ""} <span>Resumo SHA-256:</span> <code>${E(r.resumo)}</code>` : `<strong>${E(r.erro || "Arquivo recusado.")}</strong>${r.erros ? `<ul>${r.erros.map(x => `<li>${E(x)}</li>`).join("")}</ul>` : ""}`}</div>` : ""}${colunasCsv()}</section>`; }
const colunasCsv = () => `<details><summary>Colunas aceitas</summary><ul><li><strong>Rastreador:</strong> <code>data_hora;lat;lon;vel;rumo;flx;niv;hor;odo</code> <span>(data_hora em AAAA-MM-DD HH:MM, hora de Brasília; obrigatórias: data_hora, lat e lon)</span></li>
  <li><strong>Cartão-combustível:</strong> <code>data;litros;preco_l;odometro;horimetro;motorista</code> <span>(obrigatórias: data e litros; preço do cartão)</span></li></ul><p class="t2 pq">Separador ; (com vírgula decimal) ou , (com ponto). Renomeie as colunas do arquivo do fornecedor para estes nomes.</p></details>`;

function parteMetodologia(F) { const u = U(), ret = F.est && F.est.retencao_dias;
  return `${lgpd()}<section class="cartao" aria-labelledby="h-fr-ret"><h2 id="h-fr-ret">Retenção dos pontos de GPS</h2><p class="t2"><span>Os pontos ficam guardados por</span> <strong>${ret != null ? ret : premissa("frota.retencao_dias")}</strong> <span>dias e depois são apagados.</span></p>
    ${emHub() && !F.demo ? `<div class="precos">${campo("ret", "Dias de retenção (só a direção muda)", u.frRet || "", String(ret || ""))}</div><button type="button" id="fr-b-ret" data-fr-acao="retencao">Mudar a retenção</button>${u.frRetMsg ? `<p class="t2" role="status">${E(u.frRetMsg)}</p>` : ""}` : ""}</section>
  <section class="cartao" aria-labelledby="h-fr-met"><h2 id="h-fr-met">Metodologia e normas</h2><ul>
  <li><strong>Distância:</strong> fórmula de haversine entre pontos de GPS seguidos (raio médio da Terra, 6.371 km). Trecho com velocidade implícita acima do limite é salto de GPS e sai da soma. Com odômetro no começo e no fim, vale o odômetro.</li>
  <li><strong>Combustível pela vazão:</strong> soma da vazão (L/h) no tempo, pela regra dos trapézios; buraco de mais de 15 min sem leitura não entra.</li>
  <li><strong>Consumo:</strong> litros ÷ km × 100 (L/100 km) para quem roda; litros ÷ horas de motor (L/h) para trator e máquina, com litros, km e horas dos mesmos trechos com vazão medida; só dias completos viram amostra. Sem vazão, pelo método do tanque cheio: litros do abastecimento ÷ km (ou horas) desde o abastecimento anterior.</li>
  <li><strong>Normal aprendido e consumo acima do normal:</strong> mediana e desvio absoluto mediano (MAD) das amostras do próprio veículo, com média móvel exponencial para acompanhar a tendência. Alerta quando o z robusto (0,6745 × diferença ÷ MAD) passa do limite; o sistema diz o tamanho da amostra e só decide depois do mínimo de amostras.</li>
  <li><strong>Vazamento ou furto possível:</strong> o nível do tanque cai além do limite com o veículo parado, já descontado o que a vazão mediu.</li>
  <li><strong>Marcha lenta:</strong> motor ligado (ignição ou vazão) com velocidade abaixo do limite; alerta quando dura mais que o limite.</li>
  <li><strong>Cerca:</strong> ponto dentro ou fora do polígono pelo método do raio (conta quantas arestas um raio cruza).</li>
  <li><strong>Emissões:</strong> as mesmas do Carbono: combustão móvel pelo GHG Protocol (Programa Brasileiro GHG Protocol), fatores do IPCC 2006 (volume 2, capítulo 3), teor de mistura do diesel B e da gasolina C pela base de fatores; o CO₂ da parte bio é informado à parte.</li>
  <li><strong>Limites dos alertas:</strong> premissas frota.* da base, todas a conferir com os dados da frota.</li></ul>
  <p class="t2"><strong>Referências para conferir (redação própria; ler o texto vigente)</strong></p><ul>
  <li>GHG Protocol e Programa Brasileiro GHG Protocol: combustão móvel no escopo 1.</li><li>IPCC 2006, volume 2, capítulo 3 (transporte rodoviário e fora de estrada).</li>
  <li>Iglewicz e Hoaglin (1993): z modificado com mediana e MAD.</li><li>Lei 13.709/2018 (LGPD): finalidade, aviso a quem dirige e prazo de guarda.</li></ul></section>`; }

function telaFrota() { const u = U(), SUBS = [["mapa", "Mapa"], ["abastecimentos", "Abastecimentos"], ["consumo", "Consumo"], ["alertas", "Alertas"], ["cercas", "Cercas"], ["veiculos", "Veículos"], ["importar", "Importar"], ["metodologia", "Metodologia e LGPD"]];
  const sub = SUBS.some(s => s[0] === u.frSub) ? u.frSub : "mapa", F = fonte();
  const chips = `<div class="chips" role="group" aria-label="Partes da frota">${SUBS.map(([k, n]) => `<button type="button" id="fr-sub-${k}" data-fr-sub="${k}" aria-pressed="${k === sub}">${n}${k === "alertas" && F.est && F.est.alertas && F.est.alertas.length ? ` <span class="selo al">${F.est.alertas.length}</span>` : ""}</button>`).join("")}</div>`;
  let corpo;
  if (F.carregando) corpo = `<p class="t2" role="status">Carregando a frota…</p>`;
  else corpo = aviso(F) + (sub === "abastecimentos" ? parteAbastecimentos(F) : sub === "consumo" ? parteConsumo(F) : sub === "alertas" ? parteAlertas(F) : sub === "cercas" ? parteCercas(F)
    : sub === "veiculos" ? parteVeiculos(F) : sub === "importar" ? parteImportar(F) : sub === "metodologia" ? parteMetodologia(F) : parteMapa(F)) + (sub === "mapa" ? lgpd() : "");
  return `<h1>Frota e combustível</h1><p class="t2 apoio">Caminhões, carros, tratores e máquinas: onde está cada um, abastecimentos, consumo, alertas e o combustível que vai para o Carbono.</p>${chips}<div id="fr-corpo">${corpo}</div>`; }

/* ════════ Eventos (atributos data-fr-…; um ouvinte só, protegido) ════════ */
function refocar(id) { const x = pega(id); if (x && x.focus) x.focus(); }
const lerArquivo = (inp, comoTexto) => new Promise((ok, er) => { const f = inp && inp.files && inp.files[0]; if (!f) return ok(null); const r = new FileReader(); r.onload = () => ok({ nome: f.name, dados: r.result, tam: f.size }); r.onerror = () => er(r.error); if (comoTexto) r.readAsText(f, "utf-8"); else r.readAsArrayBuffer(f); });
function valor(k) { const x = pega("fr-" + k); return x ? x.value : ""; }
function addVertice(lat, lon) { const u = U(); if (!u.frEd || lat == null || lon == null || !isFinite(lat) || !isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return false; u.frEd.poligono.push([+lat.toFixed(7), +lon.toFixed(7)]); u.frCursor = { lat, lon }; return true; }
async function acao(b) { const u = U(), a = b.dataset.frAcao, F = fonte(), est = F.est;
  if (a === "abastecer") { const d = { veiculo: +valor("ab-veiculo"), data: valor("ab-data"), litros: num(valor("ab-litros")), preco_l: num(valor("ab-preco_l")), preco_fonte: valor("ab-preco_fonte") || undefined, odometro: num(valor("ab-odometro")), horimetro: num(valor("ab-horimetro")), motorista: valor("ab-motorista").trim() || undefined };
    Object.keys(d).forEach(k => { if (d[k] == null || d[k] === "") delete d[k]; }); u.frAb = Object.assign({}, d);
    if (!(d.litros > 0)) { u.frAbMsg = "Informe os litros."; redesenhar(); refocar("fr-ab-litros"); return; }
    if (d.preco_l != null && !d.preco_fonte) { u.frAbMsg = "O preço precisa da fonte."; redesenhar(); refocar("fr-ab-preco_fonte"); return; }
    if (F.demo) { u.frDemoAb = (u.frDemoAb || []).concat([Object.assign({ id: 9000 + (u.frDemoAb || []).length, comprovante: null, origem:"exemplo", preco_fonte:"" }, d)]); u.frAb = {}; u.frAbMsg = "Abastecimento de exemplo guardado só nesta tela."; redesenhar(); refocar("fr-b-ab"); return; }
    let arq = null; try { arq = await lerArquivo(pega("fr-ab-arquivo"), false); } catch (e) {}   /* antes de redesenhar: o campo do arquivo é refeito */
    u.frAbMsg = "Enviando…"; redesenhar();
    try { if (arq) { if (arq.tam > 10 * 1024 * 1024) { u.frAbMsg = "Comprovante maior que 10 MB."; redesenhar(); return; }
        const r = await api("POST", `api/frota/comprovante?veiculo=${d.veiculo}&nome=${encodeURIComponent(arq.nome)}`, null, arq.dados); if (!r.ok) { u.frAbMsg = r.erro || "Comprovante recusado."; redesenhar(); return; } d.comprovante = r.id; } } catch (e) {}
    const r = await api("POST", "api/frota/abastecimento", d); u.frAbMsg = r.ok ? "Abastecimento guardado." + (r.avisos && r.avisos.length ? " " + r.avisos.join(" ") : "") : (r.erro || "Não foi possível guardar.");
    if (r.ok) { u.frAb = {}; carregarEstado(true); } redesenhar(); refocar("fr-b-ab"); return; }
  if (a === "ab-remover") { const r = await api("POST", "api/frota/abastecimento/remover", { id: +b.dataset.frId }); u.frAbMsg = r.ok ? "Abastecimento apagado." : (r.erro || "Não foi possível apagar."); carregarEstado(true); redesenhar(); refocar("fr-b-ab"); return; }
  if (a === "cerca-nova") { u.frEd = { nome: "", poligono: [] }; u.frCursor = null; u.frCercaMsg = ""; redesenhar(); refocar("fr-ced-nome"); return; }
  if (a === "cerca-editar") { const k = (est.cercas || []).find(x => String(x.id) === b.dataset.frId); if (k) { u.frEd = { id: k.id, nome: k.nome, poligono: k.poligono.map(p => p.slice()), veiculos: k.veiculos || [] }; u.frCursor = null; } redesenhar(); refocar("fr-ced-nome"); return; }
  if (a === "cerca-cancelar") { u.frEd = null; redesenhar(); refocar("fr-b-nova-cerca"); return; }
  if (a === "vertice") { if (!addVertice(num(valor("ced-lat")), num(valor("ced-lon")))) u.frCercaMsg = "Latitude e longitude em graus (ex.: -22,5 e -43,18)."; else u.frCercaMsg = ""; redesenhar(); refocar("fr-b-vert"); return; }
  if (a === "vertice-tirar") { if (u.frEd) u.frEd.poligono.pop(); redesenhar(); refocar("fr-b-vert"); return; }
  if (a === "cerca-gravar") { const ed = u.frEd; if (!ed) return; ed.nome = valor("ced-nome").trim() || ed.nome;
    if (!ed.nome || ed.poligono.length < 3) { u.frCercaMsg = "Dê um nome e pelo menos 3 vértices."; redesenhar(); refocar(ed.nome ? "fr-b-vert" : "fr-ced-nome"); return; }
    if (F.demo) { const c = cacheLer(), cs = (c.demoCercas || est.cercas || []).filter(x => x.id !== ed.id); cs.push({ id: ed.id || Date.now() % 100000, nome: ed.nome, poligono: ed.poligono, veiculos: [], ativa: true }); c.demoCercas = cs; cacheGravar(c); if (u.frDemo) u.frDemo.cercas = cs; u.frEd = null; u.frCercaMsg = "Cerca de exemplo guardada neste aparelho."; redesenhar(); refocar("fr-b-nova-cerca"); return; }
    const r = await api("POST", "api/frota/cerca", Object.assign({ nome: ed.nome, poligono: ed.poligono, veiculos: ed.veiculos || [] }, ed.id ? { id: ed.id } : {}));
    u.frCercaMsg = r.ok ? "Cerca guardada." : (r.erro || "Não foi possível guardar."); if (r.ok) { u.frEd = null; carregarEstado(true); } redesenhar(); refocar(r.ok ? "fr-b-nova-cerca" : "fr-b-cerca"); return; }
  if (a === "cerca-remover") { if (F.demo) { const c = cacheLer(); c.demoCercas = (c.demoCercas || est.cercas || []).filter(x => String(x.id) !== b.dataset.frId); cacheGravar(c); if (u.frDemo) u.frDemo.cercas = c.demoCercas; redesenhar(); refocar("fr-b-nova-cerca"); return; }
    const r = await api("POST", "api/frota/cerca/remover", { id: +b.dataset.frId }); u.frCercaMsg = r.ok ? "Cerca apagada." : (r.erro || "Não foi possível apagar."); carregarEstado(true); redesenhar(); refocar("fr-b-nova-cerca"); return; }
  if (a === "ve-editar") { const v = est.veiculos.find(x => String(x.id) === b.dataset.frId); if (v) u.frVe = { id: v.id, tipo: v.tipo, placa: v.placa, nome: v.nome, combustivel: v.combustivel, tanque_l: v.tanque_l, consumo_esperado: v.consumo_esperado, consumo_unidade: v.consumo_unidade, no: v.no, motorista: v.motorista }; redesenhar(); refocar("fr-ve-placa"); return; }
  if (a === "ve-cancelar") { u.frVe = {}; redesenhar(); refocar("fr-b-ve"); return; }
  if (a === "ve-gravar") { const d = { tipo: valor("ve-tipo"), placa: valor("ve-placa").trim(), nome: valor("ve-nome").trim(), combustivel: valor("ve-combustivel"), tanque_l: num(valor("ve-tanque_l")), consumo_esperado: num(valor("ve-consumo_esperado")), consumo_unidade: valor("ve-consumo_unidade"), no: num(valor("ve-no")), motorista: valor("ve-motorista").trim() };
    Object.keys(d).forEach(k => { if (d[k] == null || d[k] === "") delete d[k]; }); if (d.no != null) d.no = Math.round(d.no); if ((u.frVe || {}).id) d.id = u.frVe.id; u.frVe = Object.assign({}, d);
    if (!d.placa) { u.frVeMsg = "Informe a placa ou a etiqueta."; redesenhar(); refocar("fr-ve-placa"); return; }
    const r = await api("POST", "api/frota/veiculo", d); u.frVeMsg = r.ok ? "Veículo guardado." : (r.erro || "Não foi possível guardar."); if (r.ok) { u.frVe = {}; carregarEstado(true); } redesenhar(); refocar("fr-b-ve"); return; }
  if (a === "ve-remover") { const r = await api("POST", "api/frota/veiculo/remover", { id: +b.dataset.frId }); u.frVeMsg = r.ok ? "Veículo apagado." : (r.erro || "Não foi possível apagar."); if (r.ok) u.frVe = {}; carregarEstado(true); redesenhar(); refocar("fr-b-ve"); return; }
  if (a === "importar-conferir" || a === "importar-gravar") { const fm = { veiculo: +valor("im-veiculo"), tipo: valor("im-tipo") }; u.frIm = fm;
    if (a === "importar-conferir") { let arq = null; try { arq = await lerArquivo(pega("fr-im-arquivo"), true); } catch (e) {} if (!arq) { u.frImRes = { ok: false, erro: "Escolha o arquivo CSV." }; redesenhar(); refocar("fr-im-arquivo"); return; } u.frImTxt = arq; }
    const t = u.frImTxt; if (!t) return; const r = await api("POST", "api/frota/importar", { veiculo: fm.veiculo, tipo: fm.tipo, csv: String(t.dados), nome: t.nome, simular: a === "importar-conferir" });
    u.frImRes = r; if (r.ok && !r.simulado) { u.frImTxt = null; carregarEstado(true); } redesenhar(); refocar(r.ok && r.simulado ? "fr-b-im2" : "fr-b-im"); return; }
  if (a === "retencao") { const dias = Math.round(num(valor("ret")) || 0); const r = await api("POST", "api/frota/config", { retencao_dias: dias }); u.frRetMsg = r.ok ? "Retenção mudada." : (r.erro || "Não foi possível mudar."); carregarEstado(true); redesenhar(); refocar("fr-b-ret"); } }
function moverCursor(dx, dy, grande) { const u = U(), M = u.frMold; if (!M || !u.frCursor) return; const p = grande ? 0.1 : 0.02; u.frCursor = { lat: u.frCursor.lat + dy * (M.la1 - M.la0) * p, lon: u.frCursor.lon + dx * (M.lo1 - M.lo0) * p }; redesenhar(); refocar("fr-mapa"); }
if (typeof document !== "undefined" && !window.__frEventos) { window.__frEventos = true;
  document.addEventListener("change", ev => { const t = ev.target; if (!t || !t.dataset || !t.dataset.frK) return; const u = U(), k = t.dataset.frK;
    if (k === "sel") { u.frSel = +t.value; redesenhar(); refocar("fr-sel"); return; }
    if (k === "selc") { u.frSelC = +t.value; redesenhar(); refocar("fr-selc"); return; }
    if (k === "dia") { u.frDia = t.value; redesenhar(); refocar("fr-dia"); return; }
    if (k === "ve-tipo") { u.frVe = Object.assign({}, u.frVe, { tipo: t.value }); redesenhar(); refocar("fr-ve-tipo"); return; }
    if (k === "ret") { u.frRet = t.value; } });
  document.addEventListener("click", ev => { const tg = ev.target; if (!tg || !tg.closest) return; const u = U();
    const g = tg.closest("[data-fr-v]"); if (g) { u.frSel = +g.dataset.frV; redesenhar(); const x = document.querySelector(`[data-fr-v="${g.dataset.frV}"]`); if (x) x.focus(); return; }
    const svg = tg.closest("svg[data-fr-mapa='editar']"); if (svg && u.frMold) { const r = svg.getBoundingClientRect(), M = u.frMold, x = (ev.clientX - r.left) * M.W / r.width, y = (ev.clientY - r.top) * M.H / r.height; addVertice(M.lat(y), M.lon(x)); redesenhar(); refocar("fr-mapa"); return; }
    const b = tg.closest("button"); if (!b || !b.dataset) return;
    if (b.dataset.frSub) { u.frSub = b.dataset.frSub; redesenhar(); refocar("fr-sub-" + b.dataset.frSub); return; }
    if (b.dataset.frAcao) acao(b); });
  document.addEventListener("keydown", ev => { const t = ev.target; if (!t || !t.closest) return; const u = U();
    const g = t.closest("[data-fr-v]"); if (g && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); u.frSel = +g.dataset.frV; redesenhar(); const x = document.querySelector(`[data-fr-v="${g.dataset.frV}"]`); if (x) x.focus(); return; }
    if (t.id === "fr-mapa" && t.dataset.frMapa === "editar") { const m = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }[ev.key];
      if (m) { ev.preventDefault(); moverCursor(m[0], m[1], ev.shiftKey); return; }
      if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); if (u.frCursor) addVertice(u.frCursor.lat, u.frCursor.lon); redesenhar(); refocar("fr-mapa"); } } }); }

window.FROTA = { haversineKm, distancia, litrosDoFluxo, trechosComVazao, horasMotor, marchaLenta, consumo, normalAprendido, anomaliaConsumo, pontoNoPoligono, saidasDaCerca,
  quedasSemAndar, porDia, consumoEntreAbastecimentos, amostrasConsumo, paraCarbonoDe, custosPorMes, analise, co2e, paraCarbono, resumoGestao, premissa,
  estadoDemo, rotaDemo, R_TERRA_KM, K_MAD, INTERVALO_MAX_S, TIPOS, COMBUSTIVEIS };
window.telaFrota = telaFrota;   /* global: a plataforma chama telaFrota() ao desenhar a aba */

/* ════════ Inglês (o integrador junta ao I18N da plataforma) ════════ */
window.FROTA_I18N = {
  "Frota e combustível": "Fleet and fuel",
  "Caminhões, carros, tratores e máquinas: onde está cada um, abastecimentos, consumo, alertas e o combustível que vai para o Carbono.": "Trucks, cars, tractors and machines: where each one is, refuelling, consumption, alerts and the fuel that goes to Carbon.",
  "Partes da frota": "Fleet sections",
  "Mapa": "Map",
  "Abastecimentos": "Refuelling",
  "Consumo": "Consumption",
  "Alertas": "Alerts",
  "Cercas": "Geofences",
  "Veículos": "Vehicles",
  "Importar": "Import",
  "Metodologia e LGPD": "Methodology and LGPD",
  "Carregando a frota…": "Loading the fleet…",
  "Carregando a rota…": "Loading the route…",
  "Nenhum veículo cadastrado ainda.": "No vehicle registered yet.",
  "Abaixo, uma frota SIMULADA. Cadastre um veículo na parte Veículos e ligue o rastreador (linha TIPO:VEI) para ver os dados reais.": "Below, a SIMULATED fleet. Register a vehicle in Vehicles and connect the tracker (TIPO:VEI line) to see real data.",
  "Frota SIMULADA de exemplo.": "SIMULATED example fleet.",
  "Três veículos SIMULADOS em volta do local da instalação. Nada daqui entra no Carbono nem na Gestão.": "Three SIMULATED vehicles around the installation site. Nothing here goes into Carbon or Management.",
  "Sem ligação com o computador central.": "No connection to the central computer.",
  "Mostrando os pontos guardados neste aparelho.": "Showing the points stored on this device.",
  "Mapa em volta de um ponto de exemplo.": "Map around an example point.",
  "Local não informado: preencha na página Início.": "Location not provided: fill it in on the Home page.",
  "LGPD.": "LGPD (Brazilian data protection law).",
  "A posição de um veículo mostra onde a pessoa que dirige está: é dado pessoal. Avise quem dirige, use só para a gestão da frota e guarde pelo tempo da retenção. O motorista é só um código opcional; a exportação sai sem ele.": "A vehicle's position shows where the driver is: it is personal data. Tell the drivers, use it only to manage the fleet and keep it only for the retention period. The driver is just an optional code; exports leave it out.",
  "Onde está cada veículo": "Where each vehicle is",
  "Veículo": "Vehicle",
  "Dia da rota": "Route day",
  "Escolha um veículo no mapa (clique ou Enter) ou na lista. Círculo vermelho: alerta naquele dia. Tracejado verde: cerca.": "Pick a vehicle on the map (click or Enter) or in the list. Red circle: alert on that day. Green dashes: geofence.",
  "Distância no dia": "Distance in the day",
  "km pelo odômetro": "km by odometer",
  "km pelo GPS": "km by GPS",
  "Combustível pela vazão": "Fuel by flow meter",
  "litros": "litres",
  "Consumo no dia": "Consumption in the day",
  "Marcha lenta": "Idling",
  "horas": "hours",
  "Sem pontos neste dia.": "No points on this day.",
  "Veículos e última posição": "Vehicles and last position",
  "Veículos: situação, velocidade, nível, posição e última leitura": "Vehicles: status, speed, level, position and last reading",
  "Tipo": "Type",
  "Situação": "Status",
  "km/h": "km/h",
  "Nível (%)": "Level (%)",
  "Latitude": "Latitude",
  "Longitude": "Longitude",
  "Última leitura": "Last reading",
  "Hora": "Time",
  "Vazão (L/h)": "Flow (L/h)",
  "Pontos da rota do dia: hora, posição, velocidade e nível": "Route points of the day: time, position, speed and level",
  "em movimento": "moving",
  "parado": "stopped",
  "parado, motor ligado": "stopped, engine on",
  "desligado": "off",
  "sem leitura": "no reading",
  "Caminhão": "Truck",
  "Carro": "Car",
  "Trator": "Tractor",
  "Máquina": "Machine",
  "Outro": "Other",
  "Caminhão (SIMULADO)": "Truck (SIMULATED)",
  "Carro (SIMULADO)": "Car (SIMULATED)",
  "Trator (SIMULADO)": "Tractor (SIMULATED)",
  "Cerca da propriedade (SIMULADO)": "Property geofence (SIMULATED)",
  "Diesel B (com biodiesel)": "Diesel B (with biodiesel)",
  "Gasolina C (com etanol)": "Gasoline C (with ethanol)",
  "Etanol hidratado": "Hydrous ethanol",
  "GNV (m³)": "CNG (m³)",
  "Biodiesel (B100)": "Biodiesel (B100)",
  "Diesel A": "Diesel A",
  "Nota fiscal": "Invoice",
  "Cartão-combustível": "Fuel card",
  "Preço da bomba": "Pump price",
  "Estimado": "Estimated",
  "Local da instalação": "Installation site",
  "Ponto de exemplo (sem local da instalação)": "Example point (no installation site)",
  "Cerca": "Geofence",
  "N": "N",
  "Mapa da frota: última posição de cada veículo e a rota do dia escolhido; a tabela abaixo tem a mesma informação": "Fleet map: last position of each vehicle and the route of the chosen day; the table below has the same information",
  "Mapa para desenhar a cerca: clique para pôr um vértice; com o teclado, as setas movem a mira e Enter põe o vértice": "Map to draw the geofence: click to place a vertex; with the keyboard, the arrows move the crosshair and Enter places the vertex",
  "Registrar um abastecimento": "Record a refuelling",
  "Data": "Date",
  "Litros (ou m³ de GNV)": "Litres (or m³ of CNG)",
  "Preço por litro (R$), opcional": "Price per litre (R$), optional",
  "Fonte do preço": "Price source",
  "—": "—",
  "Odômetro (km), opcional": "Odometer (km), optional",
  "Horímetro (h), opcional": "Hour meter (h), optional",
  "Código do motorista, opcional": "Driver code, optional",
  "Só um código. Nada de nome nem documento.": "Just a code. No name or ID document.",
  "Comprovante (PDF ou foto, até 10 MB), opcional": "Receipt (PDF or photo, up to 10 MB), optional",
  "Só a equipe vê.": "Only the team can see it.",
  "Guardar abastecimento": "Save refuelling",
  "Abastecimentos: data, veículo, litros, preço com a fonte, custo, odômetro, horímetro e comprovante": "Refuelling: date, vehicle, litres, price with its source, cost, odometer, hour meter and receipt",
  "Litros": "Litres",
  "Preço por litro": "Price per litre",
  "Custo": "Cost",
  "Odômetro": "Odometer",
  "Horímetro": "Hour meter",
  "Comprovante": "Receipt",
  "Ver comprovante": "View receipt",
  "Apagar": "Delete",
  "Ações": "Actions",
  "sem preço": "no price",
  "Nenhum abastecimento ainda.": "No refuelling yet.",
  "Preço só com a fonte (nota, cartão, bomba ou estimado). Sem preço, o abastecimento conta os litros e não o custo.": "Price only with its source (invoice, card, pump or estimated). Without a price, the refuelling counts the litres and not the cost.",
  "Baixar os abastecimentos (CSV, sem motorista)": "Download refuelling (CSV, without driver)",
  "Baixar os pontos de GPS (CSV)": "Download GPS points (CSV)",
  "Apagar o abastecimento de": "Delete the refuelling of",
  "Informe os litros.": "Enter the litres.",
  "O preço precisa da fonte.": "The price needs its source.",
  "Abastecimento de exemplo guardado só nesta tela.": "Example refuelling kept only on this screen.",
  "Enviando…": "Uploading…",
  "Comprovante maior que 10 MB.": "Receipt larger than 10 MB.",
  "Comprovante recusado.": "Receipt refused.",
  "Abastecimento guardado.": "Refuelling saved.",
  "Não foi possível guardar.": "Could not save.",
  "Abastecimento apagado.": "Refuelling deleted.",
  "Não foi possível apagar.": "Could not delete.",
  "Consumo por veículo": "Consumption per vehicle",
  "Por dia": "Per day",
  "Por mês": "Per month",
  "Sem amostras de consumo ainda: precisa da vazão do rastreador ou de abastecimentos com odômetro (ou horímetro).": "No consumption samples yet: it needs the tracker's fuel flow or refuelling with odometer (or hour meter).",
  "normal": "normal",
  "Consumo de": "Consumption of",
  "amostras": "samples",
  "Tracejado escuro: normal aprendido (mediana).": "Dark dashes: learned normal (median).",
  "Pontilhado azul: consumo esperado do cadastro.": "Blue dots: expected consumption from the register.",
  "Ver os números do consumo": "See the consumption numbers",
  "Amostras de consumo: data, valor e de onde veio": "Consumption samples: date, value and source",
  "Fonte": "Source",
  "vazão": "flow rate",
  "abastecimentos": "refuelling",
  "Normal aprendido:": "Learned normal:",
  "(mediana; média móvel exponencial": "(median; exponential moving average",
  ")": ")",
  "com": "with",
  "amostras.": "samples.",
  "Ainda aprendendo: o alerta de consumo começa com": "Still learning: the consumption alert starts with",
  "Por dia: distância, combustível pela vazão, horas de motor, marcha lenta e consumo": "Per day: distance, fuel by flow meter, engine hours, idling and consumption",
  "Dia": "Day",
  "km": "km",
  "Litros (vazão)": "Litres (flow)",
  "Horas de motor": "Engine hours",
  "Marcha lenta (h)": "Idling (h)",
  "L/100 km": "L/100 km",
  "L/h": "L/h",
  "Sem pontos de GPS ainda.": "No GPS points yet.",
  "Por mês e veículo: distância, litros, horas e custo": "Per month and vehicle: distance, litres, hours and cost",
  "Mês": "Month",
  "Litros abastecidos": "Litres refuelled",
  "Sem dados no mês.": "No data in the month.",
  "Emissões dos abastecimentos": "Emissions from refuelling",
  "Emissões por veículo, pelos fatores do Carbono": "Emissions per vehicle, with the Carbon factors",
  "Combustível": "Fuel",
  "tCO₂e (fóssil)": "tCO₂e (fossil)",
  "tCO₂ biogênico (à parte)": "biogenic tCO₂ (reported separately)",
  "Mesma conta e mesmos fatores do Carbono (combustão móvel, GHG Protocol).": "Same calculation and same factors as Carbon (mobile combustion, GHG Protocol).",
  "A frota SIMULADA não entra no inventário.": "The SIMULATED fleet does not go into the inventory.",
  "No Carbono, a combustão móvel passa a usar estes litros medidos (o digitado fica de reserva).": "In Carbon, mobile combustion now uses these measured litres (the typed value stays as a fallback).",
  "Consumo acima do normal": "Consumption above normal",
  "Nível caiu com o veículo parado": "Level dropped with the vehicle stopped",
  "Marcha lenta longa": "Long idling",
  "Saiu da cerca": "Left the geofence",
  "alertas nos últimos 31 dias.": "alerts in the last 31 days.",
  "Alertas: veículo, tipo, o que aconteceu e onde": "Alerts: vehicle, type, what happened and where",
  "O que aconteceu": "What happened",
  "Onde": "Where",
  "Nenhum alerta na frota agora.": "No fleet alerts now.",
  "Limites usados": "Thresholds used",
  "Limites dos alertas (premissas, todas a conferir)": "Alert thresholds (assumptions, all to be checked)",
  "Limite": "Limit",
  "Valor": "Amount",
  "conferir": "to check",
  "Consumo acima do normal: z robusto maior que": "Consumption above normal: robust z greater than",
  "e pelo menos acima da mediana (%)": "and at least above the median (%)",
  "Amostras antes de dizer o normal": "Samples before stating the normal",
  "Peso da média móvel exponencial": "Exponential moving average weight",
  "Queda de nível parado (% do tanque)": "Level drop while stopped (% of tank)",
  "Distância que ainda conta como parado (km)": "Distance that still counts as stopped (km)",
  "Marcha lenta: abaixo de (km/h)": "Idling: below (km/h)",
  "Marcha lenta longa (min)": "Long idling (min)",
  "Salto de GPS descartado acima de (km/h)": "GPS jump discarded above (km/h)",
  "Desenhar a cerca": "Draw the geofence",
  "Nome da cerca": "Geofence name",
  "ex.: Sede e talhões": "e.g. Headquarters and plots",
  "Clique no mapa para pôr um vértice. Pelo teclado: foque o mapa, mova a mira com as setas (Shift anda mais) e aperte Enter. Ou digite a latitude e a longitude abaixo.": "Click on the map to place a vertex. With the keyboard: focus the map, move the crosshair with the arrows (Shift moves further) and press Enter. Or type the latitude and longitude below.",
  "Latitude do vértice": "Vertex latitude",
  "Longitude do vértice": "Vertex longitude",
  "Acrescentar vértice": "Add vertex",
  "Tirar o último vértice": "Remove the last vertex",
  "Guardar cerca": "Save geofence",
  "Cancelar": "Cancel",
  "Vértices da cerca": "Geofence vertices",
  "Vértice": "Vertex",
  "Nenhum vértice ainda (a cerca precisa de 3 ou mais).": "No vertex yet (the geofence needs 3 or more).",
  "Desenhar uma cerca nova": "Draw a new geofence",
  "Um alerta aparece quando um veículo sai de uma cerca ligada.": "An alert appears when a vehicle leaves an active geofence.",
  "Cercas: nome, vértices, situação e veículos": "Geofences: name, vertices, status and vehicles",
  "Vértices": "Vertices",
  "Nenhuma cerca ainda.": "No geofence yet.",
  "desligada": "inactive",
  "ligada": "active",
  "todos": "all",
  "Editar": "Edit",
  "Mudar a cerca": "Change the geofence",
  "Apagar a cerca": "Delete the geofence",
  "Latitude e longitude em graus (ex.: -22,5 e -43,18).": "Latitude and longitude in degrees (e.g. -22.5 and -43.18).",
  "Dê um nome e pelo menos 3 vértices.": "Give a name and at least 3 vertices.",
  "Cerca de exemplo guardada neste aparelho.": "Example geofence saved on this device.",
  "Cerca guardada.": "Geofence saved.",
  "Cerca apagada.": "Geofence deleted.",
  "Veículos cadastrados: tipo, combustível, tanque, consumo esperado e nó": "Registered vehicles: type, fuel, tank, expected consumption and node",
  "Tanque (L)": "Tank (L)",
  "Consumo esperado": "Expected consumption",
  "Nó V6": "V6 node",
  "Cadastrar veículo": "Register vehicle",
  "Editar veículo": "Edit vehicle",
  "Placa ou etiqueta": "Plate or tag",
  "ex.: ABC1D23 ou TR-02": "e.g. ABC1D23 or TR-02",
  "Apelido, opcional": "Nickname, optional",
  "ex.: Caminhão do leite": "e.g. Milk truck",
  "Tanque (litros)": "Tank (litres)",
  "Do manual ou da medição; serve só de referência.": "From the manual or from measurement; reference only.",
  "Unidade do consumo": "Consumption unit",
  "Nó V6 do rastreador (1 a 99), opcional": "Tracker V6 node (1 to 99), optional",
  "Só um código (LGPD).": "Just a code (LGPD).",
  "Cadastrar": "Register",
  "Guardar alteração": "Save change",
  "Apagar o veículo e os dados dele": "Delete the vehicle and its data",
  "Na demonstração, a frota é SIMULADA: o cadastro funciona na plataforma instalada.": "In the demo, the fleet is SIMULATED: registration works on the installed platform.",
  "Informe a placa ou a etiqueta.": "Enter the plate or tag.",
  "Veículo guardado.": "Vehicle saved.",
  "Veículo apagado.": "Vehicle deleted.",
  "Importar CSV": "Import CSV",
  "Na plataforma instalada: o arquivo exportado do rastreador ou do cartão-combustível entra por veículo, conferido inteiro antes de gravar (tudo ou nada), com o resumo SHA-256.": "On the installed platform: the file exported from the tracker or the fuel card goes in per vehicle, fully checked before saving (all or nothing), with the SHA-256 digest.",
  "O arquivo exportado do rastreador ou do cartão-combustível, por veículo. Primeiro o sistema confere o arquivo inteiro; se uma linha estiver errada, nada é gravado.": "The file exported from the tracker or the fuel card, per vehicle. First the system checks the whole file; if one row is wrong, nothing is saved.",
  "Tipo do arquivo": "File type",
  "Rastreador (pontos de GPS)": "Tracker (GPS points)",
  "Cartão-combustível (abastecimentos)": "Fuel card (refuelling)",
  "Arquivo CSV": "CSV file",
  "Conferir o arquivo": "Check the file",
  "Arquivo conferido.": "File checked.",
  "Importado.": "Imported.",
  "Linhas:": "Rows:",
  "novas:": "new:",
  "Resumo SHA-256:": "SHA-256 digest:",
  "Arquivo recusado.": "File refused.",
  "Escolha o arquivo CSV.": "Choose the CSV file.",
  "Colunas aceitas": "Accepted columns",
  "Rastreador:": "Tracker:",
  "Cartão-combustível:": "Fuel card:",
  "(data_hora em AAAA-MM-DD HH:MM, hora de Brasília; obrigatórias: data_hora, lat e lon)": "(data_hora as YYYY-MM-DD HH:MM, Brasília time; required: data_hora, lat and lon)",
  "(obrigatórias: data e litros; preço do cartão)": "(required: data and litros; price from the card)",
  "Separador ; (com vírgula decimal) ou , (com ponto). Renomeie as colunas do arquivo do fornecedor para estes nomes.": "Separator ; (with decimal comma) or , (with decimal point). Rename the supplier file's columns to these names.",
  "Retenção dos pontos de GPS": "GPS point retention",
  "Os pontos ficam guardados por": "Points are kept for",
  "dias e depois são apagados.": "days and then deleted.",
  "Dias de retenção (só a direção muda)": "Retention days (only management can change it)",
  "Mudar a retenção": "Change retention",
  "Retenção mudada.": "Retention changed.",
  "Não foi possível mudar.": "Could not change.",
  "Metodologia e normas": "Methodology and standards",
  "Distância:": "Distance:",
  "fórmula de haversine entre pontos de GPS seguidos (raio médio da Terra, 6.371 km). Trecho com velocidade implícita acima do limite é salto de GPS e sai da soma. Com odômetro no começo e no fim, vale o odômetro.": "haversine formula between consecutive GPS points (mean Earth radius, 6,371 km). A stretch with implied speed above the threshold is a GPS jump and is left out. With odometer readings at the start and end, the odometer wins.",
  "Combustível pela vazão:": "Fuel by flow meter:",
  "soma da vazão (L/h) no tempo, pela regra dos trapézios; buraco de mais de 15 min sem leitura não entra.": "sum of the flow (L/h) over time, by the trapezoidal rule; gaps of more than 15 min without a reading are left out.",
  "Consumo:": "Consumption:",
  "litros ÷ km × 100 (L/100 km) para quem roda; litros ÷ horas de motor (L/h) para trator e máquina, com litros, km e horas dos mesmos trechos com vazão medida; só dias completos viram amostra. Sem vazão, pelo método do tanque cheio: litros do abastecimento ÷ km (ou horas) desde o abastecimento anterior.": "litres ÷ km × 100 (L/100 km) for road vehicles; litres ÷ engine hours (L/h) for tractors and machines, with litres, km and hours from the same stretches with measured flow; only complete days become samples. Without flow, by the full-tank method: litres refuelled ÷ km (or hours) since the previous refuelling.",
  "Normal aprendido e consumo acima do normal:": "Learned normal and consumption above normal:",
  "mediana e desvio absoluto mediano (MAD) das amostras do próprio veículo, com média móvel exponencial para acompanhar a tendência. Alerta quando o z robusto (0,6745 × diferença ÷ MAD) passa do limite; o sistema diz o tamanho da amostra e só decide depois do mínimo de amostras.": "median and median absolute deviation (MAD) of the vehicle's own samples, with an exponential moving average to follow the trend. It alerts when the robust z (0.6745 × difference ÷ MAD) goes over the threshold; the system states the sample size and only decides after the minimum number of samples.",
  "Vazamento ou furto possível:": "Possible leak or theft:",
  "o nível do tanque cai além do limite com o veículo parado, já descontado o que a vazão mediu.": "the tank level drops beyond the threshold with the vehicle stopped, after subtracting what the flow meter measured.",
  "Marcha lenta:": "Idling:",
  "motor ligado (ignição ou vazão) com velocidade abaixo do limite; alerta quando dura mais que o limite.": "engine on (ignition or flow) with speed below the threshold; it alerts when it lasts longer than the threshold.",
  "Cerca:": "Geofence:",
  "ponto dentro ou fora do polígono pelo método do raio (conta quantas arestas um raio cruza).": "point inside or outside the polygon by ray casting (counts how many edges a ray crosses).",
  "Emissões:": "Emissions:",
  "as mesmas do Carbono: combustão móvel pelo GHG Protocol (Programa Brasileiro GHG Protocol), fatores do IPCC 2006 (volume 2, capítulo 3), teor de mistura do diesel B e da gasolina C pela base de fatores; o CO₂ da parte bio é informado à parte.": "the same as Carbon: mobile combustion by the GHG Protocol (Brazilian GHG Protocol Programme), IPCC 2006 factors (volume 2, chapter 3), blend content of diesel B and gasoline C from the factor base; the CO₂ from the bio part is reported separately.",
  "Limites dos alertas:": "Alert thresholds:",
  "premissas frota.* da base, todas a conferir com os dados da frota.": "frota.* assumptions from the base, all to be checked against the fleet data.",
  "Referências para conferir (redação própria; ler o texto vigente)": "References to check (our own wording; read the current text)",
  "GHG Protocol e Programa Brasileiro GHG Protocol: combustão móvel no escopo 1.": "GHG Protocol and Brazilian GHG Protocol Programme: mobile combustion in scope 1.",
  "IPCC 2006, volume 2, capítulo 3 (transporte rodoviário e fora de estrada).": "IPCC 2006, volume 2, chapter 3 (road and off-road transport).",
  "Iglewicz e Hoaglin (1993): z modificado com mediana e MAD.": "Iglewicz and Hoaglin (1993): modified z with median and MAD.",
  "Lei 13.709/2018 (LGPD): finalidade, aviso a quem dirige e prazo de guarda.": "Law 13,709/2018 (LGPD): purpose, notice to drivers and retention period.",
  "Em desenvolvimento.": "In development.",
  "Versão 0.1: nada foi testado em veículo ainda. Os limites dos alertas são premissas a conferir.": "Version 0.1: nothing has been tested on a vehicle yet. The alert thresholds are assumptions to be checked.",
  "Frota e combustível:": "Fleet and fuel:",
  "sem ligação com o computador central": "no connection to the central computer",
  "sem amostras": "no samples",
  "sem variação": "no variation",
  "aprendendo": "learning",
  "Ver os pontos da rota": "See the route points",
  "Combustão móvel medida na aba Frota e combustível": "Mobile combustion measured in the Fleet and fuel tab",
  "Usar o medido na frota (o digitado abaixo fica de reserva)": "Use the fleet measurement (the typed values below stay as a fallback)",
  "A caixa está desmarcada: o inventário usa as linhas digitadas abaixo.": "The box is unchecked: the inventory uses the typed rows below.",
  "Combustível da frota (abastecimentos)": "Fleet fuel (refuelling)",
  "Combustível da frota (custo)": "Fleet fuel (cost)",
  "Combustível da frota (litros)": "Fleet fuel (litres)",
  "Uso interno": "Internal use",
  "GPS de caminhões, carros e tratores, abastecimentos, consumo e alertas; o combustível medido vai para o Carbono.": "GPS of trucks, cars and tractors, refuelling, consumption and alerts; the measured fuel goes to Carbon."
};
window.FROTA_I18N_RX = [
  [
    "^Ver os pontos da rota \\((\\d+)\\)$",
    "See the route points ($1)"
  ],
  [
    "^Nó (\\d+) manda pontos e não tem veículo ligado\\.$",
    "Node $1 sends points and has no vehicle linked."
  ],
  [
    "^normal ([\\d.,]+)$",
    "normal $1"
  ],
  [
    "^Consumo de (.+), (.+): (\\d+) amostras$",
    "Consumption of $1, $2: $3 samples"
  ],
  [
    "^Cerca: (.+)$",
    "Geofence: $1"
  ],
  [
    "^(.+) · (Caminhão|Carro|Trator|Máquina|Outro) · (em movimento|parado)$",
    "$1 · $2 · $3"
  ],
  [
    "^Apagar o abastecimento de (.+)$",
    "Delete the refuelling of $1"
  ],
  [
    "^Mudar a cerca (.+)$",
    "Change the geofence $1"
  ],
  [
    "^Apagar a cerca (.+)$",
    "Delete the geofence $1"
  ],
  [
    "^Gravar as (\\d+) linhas$",
    "Save the $1 rows"
  ],
  [
    "^Nó (\\d+)$",
    "Node $1"
  ],
  [
    "^([\\d.,]+) (L/100 km|L/h) em (\\d\\d/\\d\\d/\\d{4}); normal ([\\d.,]+) (L/100 km|L/h), z robusto ([\\d.,]+), n = (\\d+) amostras \\((vazão|abastecimentos)\\)$",
    "$1 $2 on $3; normal $4 $5, robust z $6, n = $7 samples ($8)"
  ],
  [
    "^([\\d.,]+) % do tanque \\(cerca de ([\\d.,]+) L\\) entre (.+) e (.+): vazamento ou furto possível$",
    "$1 % of the tank (about $2 L) between $3 and $4: possible leak or theft"
  ],
  [
    "^([\\d.,]+) % do tanque entre (.+) e (.+): vazamento ou furto possível$",
    "$1 % of the tank between $2 and $3: possible leak or theft"
  ],
  [
    "^([\\d.,]+) min parado com o motor ligado, até (.+)$",
    "$1 min stopped with the engine on, until $2"
  ],
  [
    "^(.+) em (\\d\\d/\\d\\d \\d\\d:\\d\\d)$",
    "$1 at $2"
  ],
  [
    "^Frota e combustível: (\\d+) abastecimentos? de (\\d{4}) e (\\d+) L pela vazão$",
    "Fleet and fuel: $1 refuelling(s) in $2 and $3 L by flow meter"
  ],
  [
    "^Frota e combustível: (\\d+) abastecimentos? de (\\d{4})$",
    "Fleet and fuel: $1 refuelling(s) in $2"
  ],
  [
    "^Frota e combustível: (\\d+) L pela vazão$",
    "Fleet and fuel: $1 L by flow meter"
  ],
  [
    "^O inventário usa o medido: ([\\d.,]+) tCO₂e\\. As linhas digitadas abaixo não entram enquanto a caixa estiver marcada\\.$",
    "The inventory uses the measurement: $1 tCO₂e. The typed rows below are left out while the box is checked."
  ],
  [
    "^\\((Frota e combustível: .+)\\)$",
    "($1)"
  ]
];
})();
