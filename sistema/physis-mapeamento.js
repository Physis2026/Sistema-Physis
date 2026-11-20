/* physis-mapeamento.js — aba Mapeamento da plataforma: o "contexto do lugar" que os outros módulos leem. EM DESENVOLVIMENTO.
   Contrato com a plataforma: define telaMapeamentoModulo(telaBases) (HTML da aba inteira, com o único título h1; telaBases
   é a função antiga telaMapeamento do painel, que vira a parte "Bases abertas"), window.MAPEAMENTO = { contas puras } e
   window.MAPEAMENTO_I18N / MAPEAMENTO_I18N_RX (português → inglês). Espelho em physis-hub/physis_hub/mapeamento.py
   (incidência, carta solar, curva diária, sombra entre fileiras e arranjo; teste em tests/test_mapeamento.py) e
   physis-hub/physis_hub/ifc.py (BIM). Depende do Início (local único: localDaInstalacao()) e do lote do Planejador
   (localStorage physis.terreno.v1). Reaproveita a aba Solar (window.SOLAR: tCelula, fTemp, strings, calcular,
   PERDAS_PADRAO, MODULOS, INVERSORES) e PhysisCalc (premissas e fatorPlano): nada de fórmula repetida da aba Solar.
   Saídas para os outros módulos (localStorage, mesmo formato "physis-calc-*" do Planejador, fonte "Mapeamento"):
   physis-contexto-lugar, physis-calc-incidencia (Solar e AVAC) e physis-calc-planta-solar (Solar). Entradas de BIM:
   physis-bim-elementos ({modulo: [elementos no formato do ifc.py]}), que cada módulo grava com MAPEAMENTO.enviarParaBim.
   Módulo EM DESENVOLVIMENTO: mostra o selo até a plataforma marcar window.MAPEAMENTO_PRONTO = true. */
(function () {
"use strict";

/* ════════ Constantes (as mesmas do mapeamento.py) ════════ */
const DIAS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
const DIA_REP = [17,47,75,105,135,162,198,228,258,288,318,344];
const DIA_21 = [21, 52, 80, 111, 141, 172, 202, 233, 264, 294, 325, 355];
const PASSOS_DIA = 240, SETORES = 36, RAD = Math.PI / 180;
const SOLSTICIO_JUN = 172, SOLSTICIO_DEZ = 355, EQUINOCIO_MAR = 80, EQUINOCIO_SET = 266;
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const PREMISSA_FP = "eletrica.fator_potencia_padrao";
/* regras do arranjo: premissas a criar em sistema/physis-premissas.json ([CONFERIR]); sem elas, o campo fica para digitar */
const PREM = { afastamento: "solar.arranjo_afastamento_borda", folga: "solar.arranjo_folga_modulos", hora_ini: "solar.arranjo_hora_critica_inicio", hora_fim: "solar.arranjo_hora_critica_fim" };
const RAMPA = ["#F6EAD0", "#E5D5AE", "#C9A227", "#C08A1E", "#A85432", "#7A2214"];

/* ════════ Utilidades (com reserva quando a plataforma não as tem) ════════ */
const E = s => typeof esc === "function" ? esc(s) : String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));
const N = (v, c) => typeof n2 === "function" ? n2(v, c) : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c });
const f1 = (v, c) => v == null || !isFinite(v) ? "—" : N(v, c == null ? 1 : c);
const num = s => { if (s == null || String(s).trim() === "") return null; const v = typeof numBr === "function" ? numBr(s) : parseFloat(String(s).replace(",", ".")); return v == null || !isFinite(v) ? null : v; };
const U = () => (typeof ui !== "undefined" && ui) ? ui : (window.__mpUi = window.__mpUi || {});
const pega = id => typeof el === "function" ? el(id) : document.getElementById(id);
const redesenhar = () => { if (typeof desenhar === "function") desenhar(false); };
const emHub = () => U().modo === "hub";
const lerLS = k => { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (e) { return null; } };
const gravarLS = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } };
const PC = () => (typeof PhysisCalc !== "undefined" ? PhysisCalc : (window.PhysisCalc || null));
const SOL = () => window.SOLAR || null;
const premissa = id => { const p = PC(); return p && typeof p.premissa === "function" ? p.premissa(id) : null; };
function T(s) { try { if (!/^en/i.test(document.documentElement.lang || "")) return s; const D = window.MAPEAMENTO_I18N || {}, k = String(s).replace(/\s+/g, " ").trim();
  if (Object.prototype.hasOwnProperty.call(D, k)) return D[k];
  for (const [a, r] of (window.MAPEAMENTO_I18N_RX || [])) { const m = k.match(new RegExp(a)); if (m) return r.replace(/\$(\d)/g, (_, i) => m[+i] == null ? "" : m[+i]); } } catch (e) {} return s; }
function estado() { const u = U(); u.mp = u.mp || {}; const o = lerLS("physis-mapeamento") || {}; u.mp.cfg = Object.assign({}, o, u.mp.cfg || {}); return u.mp; }
function guardarCfg(c) { gravarLS("physis-mapeamento", c); }

/* ════════ Lugar (Início) e lote (Planejador) ════════ */
function lugar() { const L = typeof localDaInstalacao === "function" ? localDaInstalacao() : (typeof gisLugar === "function" ? gisLugar() : null);
  return L && L.lat != null && L.lon != null ? L : null; }
function planejador() { const s = lerLS("physis.terreno.v1"); return s && s.schema === "physis.terreno/1.0" ? s : null; }
function loteLonLat(S) { const t = S && S.terreno; if (!t || t.lat0 == null || t.lon0 == null || !(t.poly || []).length) return null;
  const k = 111320 * Math.cos(t.lat0 * RAD); return t.poly.map(p => [t.lon0 + p[0] / k, t.lat0 + p[1] / 110540]); }
/* grade do terreno a partir dos pontos com cota do Planejador (inverso da distância, 8 vizinhos), como o Planejador */
function gradeDoLote(S, n) { const t = S && S.terreno; if (!t || !(t.poly || []).length) return null; n = n || 50;
  const xs = t.poly.map(p => p[0]), ys = t.poly.map(p => p[1]), m = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)) * 0.04 + 1;
  const x0 = Math.min(...xs) - m, y0 = Math.min(...ys) - m, cs = Math.max(Math.max(...xs) + m - x0, Math.max(...ys) + m - y0) / n;
  const nx = Math.ceil((Math.max(...xs) + m - x0) / cs) + 1, ny = Math.ceil((Math.max(...ys) + m - y0) / cs) + 1, P = t.pontos || [], Z = new Array(nx * ny).fill(0);
  if (P.length) for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) { const x = x0 + i * cs, y = y0 + j * cs;
    const viz = P.map(q => [Math.hypot(q[0] - x, q[1] - y), q[2]]).sort((a, b) => a[0] - b[0]).slice(0, 8);
    if (viz[0][0] < 1e-6) { Z[j * nx + i] = viz[0][1]; continue; } let a = 0, b = 0; viz.forEach(([d, z]) => { a += z / (d * d); b += 1 / (d * d); }); Z[j * nx + i] = a / b; }
  return { x0, y0, cs, nx, ny, Z, plano: !P.length }; }
function dentroPoligono(p, anel) { let c = false; for (let i = 0, j = anel.length - 1; i < anel.length; j = i++) { const [xi, yi] = anel[i], [xj, yj] = anel[j];
  if ((yi > p[1]) !== (yj > p[1]) && p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi) c = !c; } return c; }
/* edificações do Planejador como caixas; a altura vem do item (h) ou de pavimentos × altura por pavimento digitada */
function caixasDoLote(S, g, hPav) { return ((S && S.itens) || []).filter(i => i && i.w > 0 && i.d > 0 && i.tipo !== "acesso" && (i.incl != null || i.pav != null || i.h != null))
  .map((i, k) => { const h = i.h > 0 ? +i.h : (hPav > 0 ? (i.pav || 1) * hPav : null); return h == null ? null : { id: i.id || "ed" + k, nome: i.nome || "Edificação " + (k + 1), x: +i.x || 0, y: +i.y || 0, w: +i.w, d: +i.d,
    rot: +i.rot || 0, h, z0: g ? zGrade(g, +i.x || 0, +i.y || 0) : 0, incl: i.incl === "" ? null : i.incl, azim: i.azim === "" ? 0 : i.azim, aguas: i.aguas }; }).filter(Boolean); }

/* ════════ Irradiação: a mesma base da aba Solar (NASA POWER guardada no servidor), senão o contexto do servidor ════════ */
function irradiacao(L) { const u = U(); if (!L) return null; const k = L.lat.toFixed(2) + "," + L.lon.toFixed(2);
  if (typeof carregarGisSolar === "function") { try { carregarGisSolar(L.lat, L.lon); } catch (e) {} }
  const g = u.gisSolar; if (g && g.ponto && Array.isArray(g.ponto.meses) && u.gisSolarKey === k) return { H: g.ponto.meses, fonte: "NASA POWER, média de longo prazo (mesma base da aba Solar)" };
  const c = u.mp && u.mp.ctx && u.mp.ctx.campos && u.mp.ctx.campos.irradiacao; if (c && c.valor && Array.isArray(c.valor.mensal_kwh_m2_dia)) return { H: c.valor.mensal_kwh_m2_dia, fonte: c.fonte };
  /* sem servidor (arquivo aberto, sem internet, demonstração): a estimativa da aba Solar pela latitude (índice de claridade) */
  if (!emHub()) { const S = SOL(); try { const cp = S && S.compat ? S.compat() : null; if (cp && !cp.semLocal && Array.isArray(cp.H) && cp.H.length === 12 && cp.H.some(x => x > 0))
    return { H: cp.H, fonte: (cp.medido ? "NASA POWER (guardado neste navegador)" : "estimativa pela latitude e o índice de claridade da aba Solar") + " · " + NAV_TXT, navegador: true }; } catch (e) {} }
  return null; }
function temperaturas(L) { if (!L) return null; if (typeof carregarGis === "function") { try { carregarGis("temperatura", L.lat, L.lon); } catch (e) {} }
  const g = U().gis && U().gis.temperatura; return g && g.ponto && Array.isArray(g.ponto.meses) ? g.ponto.meses : null; }

/* ════════ Sol (espelho do mapeamento.py) ════════ */
function h0Mensal(lat) { const f = lat * RAD; return DIA_REP.map(n => { const d = 23.45 * Math.sin(RAD * 360 * (284 + n) / 365) * RAD, ws = Math.acos(Math.max(-1, Math.min(1, -Math.tan(f) * Math.tan(d))));
  return 24 / Math.PI * 1.367 * (1 + 0.033 * Math.cos(2 * Math.PI * n / 365)) * (Math.cos(f) * Math.cos(d) * Math.sin(ws) + ws * Math.sin(f) * Math.sin(d)); }); }
const normal = (incl, azim) => { const b = incl * RAD, A = azim * RAD; return [Math.sin(b) * Math.sin(A), Math.sin(b) * Math.cos(A), Math.cos(b)]; };
const setor = az => Math.round(((az / RAD % 360) + 360) % 360 / (360 / SETORES)) % SETORES;
const declinacao = dn => 23.45 * Math.sin(RAD * 360 * (284 + dn) / 365) * RAD;
const vetorSol = (f, d, w) => [-Math.cos(d) * Math.sin(w), Math.sin(d) * Math.cos(f) - Math.cos(d) * Math.sin(f) * Math.cos(w), Math.sin(f) * Math.sin(d) + Math.cos(f) * Math.cos(d) * Math.cos(w)];
const fracaoDifusa = (kt, ws) => ws <= 81.4 * RAD ? 1.391 - 3.560 * kt + 4.189 * kt * kt - 2.137 * kt * kt * kt : 1.311 - 3.022 * kt + 3.427 * kt * kt - 1.821 * kt * kt * kt;
function incidenciaSuperficie(H, lat, incl, azim, hz, albedo) {
  const temHz = !!hz; hz = hz || new Array(SETORES).fill(0); albedo = albedo == null ? (premissa("solar.albedo") != null ? premissa("solar.albedo") : 0.2) : albedo;
  const svf = hz.reduce((s, h) => s + Math.cos(Math.max(0, h)) ** 2, 0) / hz.length, n = normal(incl, azim), b = incl * RAD, f = lat * RAD, H0 = h0Mensal(lat);
  const mensal = [], sem = [], fator = [];
  DIA_REP.forEach((dn, m) => { const h = +H[m] || 0; if (!(h > 0)) { mensal.push(0); sem.push(0); fator.push(1); return; }
    const d = declinacao(dn), ws = Math.acos(Math.max(-1, Math.min(1, -Math.tan(f) * Math.tan(d)))); let sP = 0, sPs = 0, sH = 0;
    for (let k = 0; k < PASSOS_DIA; k++) { const w = -ws + (k + 0.5) * 2 * ws / PASSOS_DIA, s = vetorSol(f, d, w); if (s[2] <= 0) continue; sH += s[2];
      const c = Math.max(0, n[0] * s[0] + n[1] * s[1] + n[2] * s[2]); sP += c; if (c > 0 && Math.asin(Math.min(1, s[2])) > hz[setor(Math.atan2(s[0], s[1]))]) sPs += c; }
    const Rb = sH > 0 ? sP / sH : 1, Rbs = sH > 0 ? sPs / sH : 1, kt = Math.max(0.3, Math.min(0.8, h / H0[m])), fd = fracaoDifusa(kt, ws);
    let fs = (1 - fd) * Rb + fd * (1 + Math.cos(b)) / 2 + albedo * (1 - Math.cos(b)) / 2, fc = (1 - fd) * Rbs + fd * (1 + Math.cos(b)) / 2 * svf + albedo * (1 - Math.cos(b)) / 2;
    if (b === 0 && !temHz) { fs = 1; fc = 1; } mensal.push(h * fc); sem.push(h * fs); fator.push(fc); });
  const soma = a => a.reduce((s, v, m) => s + v * DIAS[m], 0), anual = soma(mensal), anualSem = soma(sem), anualH = soma(H.map(v => +v || 0));
  return { mensal_kwh_m2_dia: mensal, fator_mensal: fator, anual_kwh_m2: anual, anual_sem_sombra_kwh_m2: anualSem, fator_anual: anualH > 0 ? anual / anualH : null,
    sombra_pct: anualSem > 0 ? 100 * (1 - anual / anualSem) : 0, ceu_visivel: svf }; }
function zGrade(g, x, y) { const fi = Math.min(Math.max((x - g.x0) / g.cs, 0), g.nx - 1.001), fj = Math.min(Math.max((y - g.y0) / g.cs, 0), g.ny - 1.001);
  const i = Math.floor(fi), j = Math.floor(fj), u = fi - i, v = fj - j, Z = g.Z, n = g.nx;
  return Z[j * n + i] * (1 - u) * (1 - v) + Z[j * n + i + 1] * u * (1 - v) + Z[(j + 1) * n + i] * (1 - u) * v + Z[(j + 1) * n + i + 1] * u * v; }
function raioCaixa(px, py, dx, dy, c) { const r = -(c.rot || 0) * RAD, ox = px - c.x, oy = py - c.y;
  const lx = ox * Math.cos(r) - oy * Math.sin(r), ly = ox * Math.sin(r) + oy * Math.cos(r), vx = dx * Math.cos(r) - dy * Math.sin(r), vy = dx * Math.sin(r) + dy * Math.cos(r);
  let t0 = -Infinity, t1 = Infinity;
  for (const [o, v, meia] of [[lx, vx, c.w / 2], [ly, vy, c.d / 2]]) { if (Math.abs(v) < 1e-12) { if (Math.abs(o) > meia) return null; continue; }
    const a = (-meia - o) / v, b = (meia - o) / v; t0 = Math.max(t0, Math.min(a, b)); t1 = Math.min(t1, Math.max(a, b)); }
  return t1 < Math.max(t0, 0) ? null : Math.max(t0, 0); }
function horizonte(x, y, z, g, caixas, ignorar) { const out = new Array(SETORES).fill(0), alc = g ? Math.hypot(g.nx, g.ny) * g.cs : 0;
  for (let k = 0; k < SETORES; k++) { const az = k * 360 / SETORES * RAD, dx = Math.sin(az), dy = Math.cos(az); let m = 0;
    if (g) for (let t = g.cs; t <= alc; t += g.cs * 0.5) { const qx = x + dx * t, qy = y + dy * t;
      if (!(qx >= g.x0 && qx <= g.x0 + (g.nx - 1) * g.cs && qy >= g.y0 && qy <= g.y0 + (g.ny - 1) * g.cs)) break; m = Math.max(m, Math.atan2(zGrade(g, qx, qy) - z, t)); }
    (caixas || []).forEach(c => { if (ignorar != null && c.id === ignorar) return; const t = raioCaixa(x, y, dx, dy, c); if (t == null || t < 0.01) return;
      m = Math.max(m, Math.atan2((c.z0 || 0) + c.h - z, t)); });
    out[k] = m; }
  return out; }
function planosTelhado(c) { if (c.incl == null || c.incl === "") return []; const incl = +c.incl, az0 = +c.azim || 0; let n = +c.aguas || 1; if (![1, 2, 4].includes(n)) n = 1;
  return Array.from({ length: n }, (_, k) => ({ id: `${c.id}-agua${k + 1}`, nome: `${c.nome} · água ${k + 1}`, tipo: "telhado", x: c.x, y: c.y, z: (c.z0 || 0) + c.h + 0.05, incl,
    azim: (az0 + k * 360 / n) % 360, area_m2: c.w * c.d / n / Math.max(0.05, Math.cos(incl * RAD)), largura_m: n === 4 && k % 2 ? c.d : c.w,
    comprimento_agua_m: (n === 1 ? c.d : n === 2 ? c.d / 2 : (k % 2 ? c.w : c.d) / 2) / Math.max(0.05, Math.cos(incl * RAD)), caixa: c.id })); }
function fachadas(c) { const r = (c.rot || 0) * RAD;
  return [[0, -c.d / 2, c.w], [c.w / 2, 0, c.d], [0, c.d / 2, c.w], [-c.w / 2, 0, c.d]].map(([lx, ly, larg], k) => { const ex = lx * Math.cos(r) - ly * Math.sin(r), ey = lx * Math.sin(r) + ly * Math.cos(r), n = Math.hypot(ex, ey) || 1;
    return { id: `${c.id}-fachada${k + 1}`, nome: `${c.nome} · fachada ${k + 1}`, tipo: "fachada", x: c.x + ex + 0.05 * ex / n, y: c.y + ey + 0.05 * ey / n, z: (c.z0 || 0) + c.h / 2, incl: 90,
      azim: ((Math.atan2(ex, ey) / RAD) % 360 + 360) % 360, area_m2: larg * c.h, caixa: c.id }; }); }
function celulasTerreno(g, maxc, dentro) { const { nx, ny, cs, Z } = g, passo = Math.max(1, Math.ceil(Math.sqrt(Math.max(1, (nx - 2) * (ny - 2)) / (maxc || 400)))), out = [];
  for (let j = 1; j < ny - 1; j += passo) for (let i = 1; i < nx - 1; i += passo) { const x = g.x0 + i * cs, y = g.y0 + j * cs; if (dentro && !dentro([x, y])) continue;
    const dx = (Z[j * nx + i + 1] - Z[j * nx + i - 1]) / (2 * cs), dy = (Z[(j + 1) * nx + i] - Z[(j - 1) * nx + i]) / (2 * cs);
    out.push({ id: `t${i}-${j}`, tipo: "terreno", i, j, x, y, z: Z[j * nx + i] + 0.05, incl: Math.atan(Math.hypot(dx, dy)) / RAD, azim: ((Math.atan2(-dx, -dy) / RAD) % 360 + 360) % 360, area_m2: (cs * passo) ** 2 }); }
  return out; }
function incidencia(H, lat, sups, g, caixas) { return sups.map(s => Object.assign({}, s, incidenciaSuperficie(H, lat, +s.incl || 0, +s.azim || 0, (g || (caixas && caixas.length)) ? horizonte(s.x, s.y, s.z, g, caixas, s.caixa) : null))); }

/* ════════ Planta solar: carta solar, curva desde o nascer do sol, sombra entre fileiras e arranjo ════════ */
function solEm(lat, dn, hora) { const s = vetorSol(lat * RAD, declinacao(dn), (hora - 12) * 15 * RAD);
  return { altura: Math.asin(Math.max(-1, Math.min(1, s[2]))) / RAD, azimute: ((Math.atan2(s[0], s[1]) / RAD) % 360 + 360) % 360 }; }
function nascerPor(lat, dn) { const ws = Math.acos(Math.max(-1, Math.min(1, -Math.tan(lat * RAD) * Math.tan(declinacao(dn))))) / RAD; return [12 - ws / 15, 12 + ws / 15]; }
function cartaSolar(lat) { return DIA_21.map((dn, m) => { const [n0, n1] = nascerPor(lat, dn), pts = [];
  for (let h = Math.ceil(n0); h <= Math.floor(n1); h++) { const s = solEm(lat, dn, h); if (s.altura > 0) pts.push(Object.assign({ hora: h }, s)); }
  return { mes: m + 1, dia_do_ano: dn, nascer_h: n0, por_h: n1, pontos: pts }; }); }
function curvaDiaria(Hdia, lat, dn, incl, azim, hz, albedo, passoH, totalPlano) { hz = hz || new Array(SETORES).fill(0); albedo = albedo == null ? 0.2 : albedo; passoH = passoH || 0.25;
  const svf = hz.reduce((s, h) => s + Math.cos(Math.max(0, h)) ** 2, 0) / hz.length, f = lat * RAD, d = declinacao(dn), ws = Math.acos(Math.max(-1, Math.min(1, -Math.tan(f) * Math.tan(d))));
  const n = normal(incl, azim), b = incl * RAD, h0 = 24 / Math.PI * 1.367 * (1 + 0.033 * Math.cos(2 * Math.PI * dn / 365)) * (Math.cos(f) * Math.cos(d) * Math.sin(ws) + ws * Math.sin(f) * Math.sin(d));
  const kt = h0 > 0 ? Math.max(0.3, Math.min(0.8, Hdia / h0)) : 0.5, Hd = fracaoDifusa(kt, ws) * Hdia;
  const a = 0.409 + 0.5016 * Math.sin(ws - 60 * RAD), bb = 0.6609 - 0.4767 * Math.sin(ws - 60 * RAD), den = Math.sin(ws) - ws * Math.cos(ws);
  const n0 = 12 - ws / RAD / 15, n1 = 12 + ws / RAD / 15, np = Math.max(1, Math.ceil((n1 - n0) / passoH)); passoH = (n1 - n0) / np; let pts = [];
  for (let k = 0; k < np; k++) { const h = n0 + (k + 0.5) * passoH, w = (h - 12) * 15 * RAD, rd = (Math.PI / 24) * (Math.cos(w) - Math.cos(ws)) / den, rt = rd * (a + bb * Math.cos(w));
    const I = Hdia * rt, Id = Hd * rd, Ib = Math.max(0, I - Id), s = vetorSol(f, d, w), cz = Math.max(s[2], 0), ct = Math.max(0, n[0] * s[0] + n[1] * s[1] + n[2] * s[2]);
    const vis = cz > 0 && Math.asin(Math.min(1, cz)) > hz[setor(Math.atan2(s[0], s[1]))], rb = cz > 0.02 ? ct / cz : 0;
    pts.push([h, Math.max(0, (vis ? Ib * rb : 0) + Id * (1 + Math.cos(b)) / 2 * svf + I * albedo * (1 - Math.cos(b)) / 2) * 1000]); }
  let soma = pts.reduce((s, p) => s + p[1], 0) * passoH / 1000;
  if (totalPlano != null && soma > 0) { const k = totalPlano / soma; pts = pts.map(p => [p[0], p[1] * k]); soma = totalPlano; }
  return { dia_do_ano: dn, nascer_h: n0, por_h: n1, passo_h: passoH, pontos: pts, total_kwh_m2: soma }; }
/* potência CA estimada: kWp × G/1000 × fator de temperatura × perdas, com as funções e as perdas da aba Solar */
function potenciaCA(curva, kwp, tAmb, modulo, eta) { const S = SOL(); if (!S) return null; const L = S.PERDAS_PADRAO;
  const fixo = (1 - L.sombra / 100) * (1 - L.sujeira / 100) * (1 - L.mismatch / 100) * (1 - L.cabos_cc / 100) * eta * (1 - L.cabos_ca / 100);
  return curva.pontos.map(([h, g]) => [h, kwp * g / 1000 * S.fTemp(S.tCelula(tAmb, modulo.noct, g), modulo.gamma_pmax) * fixo]); }
function sombraEntreFileiras(lat, incl, azim, prof, alt, passo, dia, horas) { const vao = passo - prof; let pior = 0; const det = [];
  (horas || [9, 15]).forEach(h => { const s = solEm(lat, dia, h); if (s.altura <= 0) { det.push({ hora: h, altura: s.altura, sombra_m: null }); return; }
    const L = alt * Math.cos((s.azimute - azim) * RAD) / Math.tan(s.altura * RAD); pior = Math.max(pior, L); det.push({ hora: h, altura: s.altura, azimute: s.azimute, sombra_m: L }); });
  return { sombreia: pior > vao + 1e-9, vao_m: vao, sombra_max_m: pior, passo_minimo_m: prof + pior, dia, horas: horas || [9, 15], detalhe: det }; }
function distSeg(p, a, c) { const dx = c[0] - a[0], dy = c[1] - a[1], t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy || 1))); return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy); }
function cabe(cantos, pol, af) { return cantos.every(q => dentroPoligono(q, pol) && (!(af > 0) || Math.min(...pol.map((p, i) => distSeg(q, p, pol[(i + 1) % pol.length]))) >= af - 1e-9)); }
function arranjo(pol, mod, o) { const L = +mod.comprimento_m, W = +mod.largura_m; if (!(L > 0 && W > 0 && mod.pmax > 0)) throw new Error("módulo sem dimensões ou potência");
  const [dv, du] = o.orientacao === "paisagem" ? [W, L] : [L, W], n = Math.max(1, Math.round(o.empilhados || 1)), af = o.afastamento_m, folga = o.folga_m;
  let A = 0, prof, alt, sombra = null, passo;
  if (o.plano === "telhado") { prof = n * dv; alt = 0; passo = prof + folga; }
  else { A = (o.azim || 0) * RAD; prof = n * dv * Math.cos((o.incl || 0) * RAD); alt = n * dv * Math.sin((o.incl || 0) * RAD);
    const dc = o.dia_critico != null ? o.dia_critico : ((o.lat || 0) < 0 ? SOLSTICIO_JUN : SOLSTICIO_DEZ);
    if (o.lat != null && o.incl > 0) sombra = sombraEntreFileiras(o.lat, o.incl, o.azim || 0, prof, alt, prof, dc, o.horas);
    passo = o.passo_m > 0 ? o.passo_m : (sombra ? Math.max(prof + folga, sombra.passo_minimo_m) : prof + folga);
    if (sombra) sombra = sombraEntreFileiras(o.lat, o.incl, o.azim || 0, prof, alt, passo, dc, o.horas); }
  const fx = Math.sin(A), fy = Math.cos(A), ux = fy, uy = -fx, loc = pol.map(p => [p[0] * ux + p[1] * uy, p[0] * fx + p[1] * fy]), glob = (u, v) => [u * ux + v * fx, u * uy + v * fy];
  const us = loc.map(p => p[0]), vs = loc.map(p => p[1]), pos = []; let mesas = 0;
  /* obstáculos (edificações no solo, com o afastamento): polígonos no mesmo sistema da área */
  const obs = (o.obstaculos || []).map(ob => ob.map(p => [p[0] * ux + p[1] * uy, p[0] * fx + p[1] * fy]));
  for (let v = Math.max(...vs) - af - prof; v >= Math.min(...vs) + af - 1e-9; v -= passo)
    for (let u = Math.min(...us) + af; u + du <= Math.max(...us) - af + 1e-9; u += du + folga) {
      const cantos = [[u, v], [u + du, v], [u + du, v + prof], [u, v + prof]];
      if (!cabe(cantos, loc, af) || obs.some(ob => cantos.concat([[u + du / 2, v + prof / 2]]).some(q => dentroPoligono(q, ob)) || ob.some(q => dentroPoligono(q, cantos)))) continue; mesas++;
      for (let k = 0; k < n; k++) { const g = glob(u + du / 2, v + prof - (k + 0.5) * prof / n); pos.push({ x: g[0], y: g[1] }); } }
  return { modulos: pos.length, mesas, kwp: pos.length * mod.pmax / 1000, area_modulos_m2: pos.length * L * W, area_ocupada_m2: mesas * du * prof, passo_m: passo,
    profundidade_mesa_m: prof, altura_mesa_m: alt, orientacao: o.orientacao || "retrato", empilhados: n, plano: o.plano || "solo", sombra_entre_fileiras: sombra, posicoes: pos, du, dv }; }
/* P, Q e S pelo fator de potência: PhysisCalc.potencias (FP digitado vale antes da premissa eletrica.fator_potencia_padrao) */
function potencias(p, fp) { const pc = PC(); if (pc && typeof pc.potencias === "function") { const r = pc.potencias(p, fp); return { P: r.p, Q: r.q, S: r.s, fp: r.fp, fonte: r.fonte, bruto: r }; }
  return { P: p, Q: null, S: null, fp: null, fonte: "sem fator de potência", bruto: null }; }
/* dimensões do módulo: da base de equipamentos ("≈ 2,28 × 1,13 m" na descrição); senão digitadas */
function dimensoesModulo(id) { try { const s = document.getElementById("base-equipamentos"), j = s ? JSON.parse(s.textContent) : (window.EQUIPAMENTOS || null);
  const x = j && (j.itens || []).find(i => i.id === id), m = x && String(x.descricao || "").match(/([\d]+[,.][\d]+)\s*×\s*([\d]+[,.][\d]+)\s*m/);
  if (m) return { comprimento_m: +m[1].replace(",", "."), largura_m: +m[2].replace(",", "."), fonte: "base de equipamentos (" + id + ")" }; } catch (e) {} return null; }

/* ════════ BIM: o que os módulos mandaram de volta ════════ */
function enviarParaBim(modulo, elementos) { const o = lerLS("physis-bim-elementos") || {}; o[modulo] = (elementos || []).map(e => Object.assign({ origem: modulo }, e)); return gravarLS("physis-bim-elementos", o); }
function elementosBim() { const o = lerLS("physis-bim-elementos") || {}, out = [];
  Object.keys(o).forEach(k => (o[k] || []).forEach(e => out.push(e)));
  const bio = lerLS("physis-calc-biogas"); if (bio && bio.biodigestor_m3 > 0 && !out.some(e => e.tipo === "biodigestor"))
    out.push({ id: "biodigestor", tipo: "biodigestor", origem: "Planejador", propriedades: { volume_m3: bio.biodigestor_m3, biogas_m3_dia: bio.biogas_m3_dia } });
  return out; }

/* ════════ Peças de tela ════════ */
const cartao = (id, tit, numero, un) => `<section class="cartao" aria-labelledby="h-${id}"><h3 id="h-${id}" class="t3">${E(T(tit))}</h3><span class="numero">${numero}</span><span class="t2">${E(T(un))}</span></section>`;
const campo = (k, rot, val, ph, ajuda) => `<div><label for="mp-${k}">${E(T(rot))}</label><input id="mp-${k}" type="text" inputmode="decimal" data-mp-k="${k}" value="${E(val == null ? "" : val)}" placeholder="${E(ph || "")}" style="width:100%"${ajuda ? ` aria-describedby="mp-${k}-a"` : ""}>${ajuda ? `<span id="mp-${k}-a" class="t2 pq">${E(T(ajuda))}</span>` : ""}</div>`;
const lista = (k, rot, ops, atual) => `<div><label for="mp-${k}">${E(T(rot))}</label><select id="mp-${k}" data-mp-k="${k}" style="width:100%">${ops.map(([v, n]) => `<option value="${E(v)}" ${String(v) === String(atual) ? "selected" : ""}>${E(T(n))}</option>`).join("")}</select></div>`;
const NAV_TXT = "calculado no navegador (sem servidor)";
const notaNav = () => emHub() ? "" : `<p class="t2 pq"><span class="selo in">${E(T("calculado no navegador (sem servidor)"))}</span> ${E(T("Com o servidor da instalação, o resultado usa as camadas instaladas e pode mudar."))}</p>`;
const faixa = (tipo, forte, txt) => `<div class="faixa ${tipo}" role="note"><strong>${E(T(forte))}</strong> <span>${E(T(txt))}</span></div>`;
const cor = (v, a, b) => { const t = b > a ? Math.max(0, Math.min(1, (v - a) / (b - a))) : 0.5; return RAMPA[Math.min(RAMPA.length - 1, Math.floor(t * RAMPA.length))]; };
const conforto = () => { const c = document.documentElement.classList; return c.contains("physis-conforto") || c.contains("a11y-simples") || c.contains("a11y-calma"); };
function graficoLinhas(id, titulo, series, un, rotX) { const W = 640, H = 220, m = { l: 48, r: 12, t: 12, b: 28 }, todos = series.flatMap(s => s.pts);
  if (!todos.length) return `<p class="t2">${E(T("Sem dados para o gráfico."))}</p>`;
  const xs = todos.map(p => p[0]), ys = todos.map(p => p[1]), x0 = Math.min(...xs), x1 = Math.max(...xs, x0 + 1e-9), y1 = Math.max(...ys, 1e-9);
  const sx = x => m.l + (x - x0) / (x1 - x0) * (W - m.l - m.r), sy = y => H - m.b - y / y1 * (H - m.t - m.b);
  const lin = s => `<polyline fill="none" style="stroke:${s.cor}" stroke-width="2.5"${s.tracejado ? ' stroke-dasharray="6 4"' : ""} points="${s.pts.map(p => sx(p[0]).toFixed(1) + "," + sy(p[1]).toFixed(1)).join(" ")}"/>`;
  return `<figure style="margin:0"><svg id="${id}" viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px" role="img" aria-labelledby="${id}-t"><title id="${id}-t">${E(T(titulo))}</title>
    <line x1="${m.l}" y1="${H - m.b}" x2="${W - m.r}" y2="${H - m.b}" style="stroke:var(--linha,#D9D3C2)"/><line x1="${m.l}" y1="${m.t}" x2="${m.l}" y2="${H - m.b}" style="stroke:var(--linha,#D9D3C2)"/>
    <text x="${m.l - 6}" y="${m.t + 10}" font-size="11" text-anchor="end" style="fill:var(--tinta2,#4A4F44)">${f1(y1, 0)}</text><text x="${m.l - 6}" y="${H - m.b}" font-size="11" text-anchor="end" style="fill:var(--tinta2,#4A4F44)">0</text>
    <text x="${m.l}" y="${H - 8}" font-size="11" style="fill:var(--tinta2,#4A4F44)">${E(rotX(x0))}</text><text x="${W - m.r}" y="${H - 8}" font-size="11" text-anchor="end" style="fill:var(--tinta2,#4A4F44)">${E(rotX(x1))}</text>
    <text x="${m.l + 4}" y="${m.t + 10}" font-size="11" style="fill:var(--tinta2,#4A4F44)">${E(un)}</text>${series.map(lin).join("")}</svg>
    <figcaption>${series.map(s => `<span class="t2 pq" style="margin-right:12px"><span aria-hidden="true" style="display:inline-block;width:18px;height:3px;vertical-align:middle;background:${s.cor}"></span> ${E(T(s.nome))}</span>`).join("")}</figcaption></figure>`; }
const horaTxt = h => { const t = Math.round(h * 60); return String(Math.floor(t / 60)).padStart(2, "0") + ":" + String(t % 60).padStart(2, "0"); };

/* ════════ Parte: contexto do lugar ════════ */
function buscarContexto(force) { const u = U(), st = estado(); if (!emHub() || (st.ctxCarregando && !force)) return;
  if (st.ctx && !force) return; st.ctxCarregando = true;
  const L = lugar(), ir = irradiacao(L), corpo = { lote: planejador(), irradiacao_solar: ir ? { meses: ir.H, fonte: ir.fonte } : null };
  fetch("api/mapeamento/contexto", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo), cache: "no-store" })
    .then(r => r.ok ? r.json() : null).then(j => { st.ctx = j && j.contexto ? j.contexto : null; st.ctxErro = j ? "" : "O servidor não respondeu."; if (st.ctx) gravarLS("physis-contexto-lugar", st.ctx); })
    .catch(() => { st.ctxErro = "O servidor não respondeu."; }).finally(() => { st.ctxCarregando = false; redesenhar(); }); }
function valorTxt(v) { if (v == null) return "—"; if (typeof v === "number") return f1(v, 1); if (Array.isArray(v)) return v.slice(0, 6).map(x => x && typeof x === "object" ? (x.nome || x.classe) + (x.fracao != null ? " " + f1(100 * x.fracao, 0) + " %" : "") : f1(x, 2)).join("; ");
  if (typeof v === "object") return Object.entries(v).filter(([, x]) => x != null && typeof x !== "object").slice(0, 6).map(([k, x]) => k + ": " + (typeof x === "number" ? f1(x, 1) : x)).join(" · "); return String(v); }
const ROTULOS = { cep: "CEP", coordenadas: "Coordenadas", municipio: "Município", area_lote_m2: "Área do lote", declividade: "Declividade", altitude_m: "Altitude", hidrografia: "Rios e nascentes", uso_solo: "Uso do solo",
  solos: "Solo", limites: "Limites", car: "CAR", risco: "Áreas de risco", rede_eletrica: "Rede elétrica", osm: "Edificações e vias", clima: "Clima (EPW)", irradiacao: "Irradiação solar", vento: "Vento" };
/* contexto do lugar no navegador (sem servidor): o que dá para saber aqui, com a fonte; as camadas do servidor aparecem como
   "disponível com o servidor" (nunca um valor inventado) */
const CAMADAS_SERVIDOR = ["declividade", "altitude_m", "hidrografia", "uso_solo", "solos", "limites", "car", "risco", "rede_eletrica", "osm", "clima", "vento"];
function contextoNavegador(L, S) { const ir = irradiacao(L), area = S && S.terreno && (S.terreno.poly || []).length >= 3 ? Math.abs(S.terreno.poly.reduce((s, p, i, a) => { const q = a[(i + 1) % a.length]; return s + p[0] * q[1] - q[0] * p[1]; }, 0)) / 2 : (L.area_m2 || null);
  const linha = (k, v, un, fonte) => `<tr><th scope="row">${E(T(ROTULOS[k] || k))}</th><td>${v == null ? `<span class="selo in">${E(T("sem dado"))}</span>` : E(v)} ${v != null && un ? `<span class="t2 pq">${E(un)}</span>` : ""}</td><td class="t2 pq">${E(T(fonte))}</td></tr>`;
  const anual = ir ? ir.H.reduce((s, h) => s + h, 0) / 12 : null;
  const linhas = linha("coordenadas", f1(L.lat, 5) + ", " + f1(L.lon, 5), "graus (WGS 84)", "local da instalação (" + (L.fonte || "—") + (L.fonte_coordenadas ? ", " + L.fonte_coordenadas : "") + ")")
    + linha("municipio", L.municipio ? L.municipio + (L.uf ? " – " + L.uf : "") : null, "", "Início (dados obrigatórios do cliente)")
    + linha("cep", L.cep || null, "", "Início")
    + linha("area_lote_m2", area != null ? f1(area, 0) : null, "m²", S ? "Planejador (lote)" : "Início (área)")
    + linha("irradiacao", anual != null ? f1(anual, 2) : null, "kWh/m² por dia (média do ano)", ir ? ir.fonte : "aba Solar sem o local");
  const fora = CAMADAS_SERVIDOR.map(k => `<li>${E(T(ROTULOS[k] || k))}: <span class="selo at">${E(T("disponível com o servidor"))}</span></li>`).join("");
  const doc = { esquema: "physis-contexto-lugar/1", navegador: true, campos: { coordenadas: { valor: { lat: L.lat, lon: L.lon }, fonte: L.fonte }, municipio: { valor: { municipio: L.municipio, uf: L.uf } },
    area_lote_m2: { valor: area }, irradiacao: ir ? { valor: { mensal_kwh_m2_dia: ir.H }, fonte: ir.fonte } : { valor: null } }, faltam: CAMADAS_SERVIDOR.map(k => ({ camada: k, motivo: "disponível com o servidor" })) };
  gravarLS("physis-contexto-lugar", doc);
  return `<section class="cartao" aria-labelledby="h-mp-ctx"><h2 id="h-mp-ctx">${E(T("Contexto do lugar"))}</h2>${notaNav()}<div class="rolagem"><table><caption>${E(T("Cada campo com a fonte"))}</caption><thead><tr><th scope="col">${E(T("Campo"))}</th><th scope="col">${E(T("Valor"))}</th><th scope="col">${E(T("Fonte"))}</th></tr></thead><tbody>${linhas}</tbody></table></div></section>
    <section class="cartao" aria-labelledby="h-mp-faltam"><h2 id="h-mp-faltam">${E(T("Camadas que dependem do servidor"))}</h2><ul>${fora}</ul><p class="t2 pq">${E(T("Relevo, rios, uso do solo, solos, CAR, risco, rede elétrica, prédios, clima e vento vêm das bases instaladas no servidor da instalação. Nenhum valor é inventado no lugar delas."))}</p></section>`; }
function parteContexto() { const st = estado(), L = lugar(), S = planejador();
  if (!L) return faixa("in", "Falta a localização.", "O Mapeamento depende do Início: preencha os dados obrigatórios do cliente (localização) no Início ou desenhe o lote no Planejador.") +
    `<p><button type="button" data-mp-acao="inicio">${E(T("Ir para o Início"))}</button></p>`;
  let html = `<p class="t2">${E(T("Lugar"))}: ${f1(L.lat, 5)}, ${f1(L.lon, 5)} · ${E(T("fonte"))}: ${E(L.fonte || "—")}. ${S ? E(T("Lote do Planejador encontrado.")) : E(T("Sem lote no Planejador: a área vem do Início."))}</p>`;
  if (!emHub()) return html + contextoNavegador(L, S);
  buscarContexto(false);
  if (st.ctxCarregando && !st.ctx) return html + `<p class="t2" role="status">${E(T("Montando o contexto do lugar…"))}</p>`;
  if (!st.ctx) return html + `<p class="t2" role="status">${E(T(st.ctxErro || "Contexto indisponível agora."))}</p>`;
  const c = st.ctx, linhas = Object.entries(c.campos || {}).map(([k, v]) => `<tr><th scope="row">${E(T(ROTULOS[k] || k))}</th><td>${v.situacao === "camada_nao_instalada" ? `<span class="selo at">${E(T("camada não instalada"))}</span>` : v.situacao === "sem_dado" ? `<span class="selo in">${E(T("sem dado"))}</span>` : E(valorTxt(v.valor))} ${v.unidade && v.valor != null ? `<span class="t2 pq">${E(v.unidade)}</span>` : ""}</td><td class="t2 pq">${E(v.fonte || "")}${v.nota ? "<br>" + E(v.nota) : ""}</td></tr>`).join("");
  const faltam = (c.faltam || []).length ? `<section class="cartao" aria-labelledby="h-mp-faltam"><h2 id="h-mp-faltam">${E(T("Camadas que faltam neste servidor"))}</h2><ul>${c.faltam.map(f => `<li><strong>${E(f.nome && (f.nome.pt || f.nome))}</strong>: ${E(T(f.motivo))} <span class="t2 pq">(${E(f.como_instalar)})</span></li>`).join("")}</ul><p class="t2 pq">${E(T("A instalação das bases nacionais no servidor está na Fase 2 (docs/MAPEAMENTO.md). Nenhum valor é inventado no lugar de uma camada que falta."))}</p></section>` : "";
  return html + `<section class="cartao" aria-labelledby="h-mp-ctx"><h2 id="h-mp-ctx">${E(T("Contexto do lugar"))}</h2><div class="rolagem"><table><caption>${E(T("Cada campo com a fonte"))}</caption><thead><tr><th scope="col">${E(T("Campo"))}</th><th scope="col">${E(T("Valor"))}</th><th scope="col">${E(T("Fonte"))}</th></tr></thead><tbody>${linhas}</tbody></table></div>
    <p class="t2 pq">${E(T("Integridade"))} (SHA-256): <code>${E((c.integridade || {}).sha256 || "")}</code></p><button type="button" data-mp-acao="ctx">${E(T("Atualizar o contexto"))}</button></section>` + faltam; }

/* ════════ Parte: camadas e arquivos do cliente ════════ */
function buscar(chave, url) { const st = estado(); if (!emHub() || st[chave + "Carregando"] || st[chave]) return; st[chave + "Carregando"] = true;
  fetch(url, { cache: "no-store" }).then(r => r.ok ? r.json() : null).then(j => { st[chave] = j || { ok: false }; }).catch(() => { st[chave] = { ok: false }; }).finally(() => { st[chave + "Carregando"] = false; redesenhar(); }); }
function parteCamadas() { if (!emHub()) return `<section class="cartao" aria-labelledby="h-mp-cat"><h2 id="h-mp-cat">${E(T("Catálogo de camadas"))}</h2>${notaNav()}<ul>${CAMADAS_SERVIDOR.concat(["irradiacao"]).map(k => `<li>${E(T(ROTULOS[k] || k))}: ${k === "irradiacao" ? `<span class="selo in">${E(T("estimativa no navegador"))}</span>` : `<span class="selo at">${E(T("disponível com o servidor"))}</span>`}</li>`).join("")}</ul></section>`;
  buscar("cat", "api/mapeamento/camadas"); const st = estado(); if (!st.cat) return `<p class="t2" role="status">${E(T("Carregando o catálogo…"))}</p>`;
  const cs = st.cat.camadas || [];
  return `<section class="cartao" aria-labelledby="h-mp-cat"><h2 id="h-mp-cat">${E(T("Catálogo de camadas"))}</h2><div class="rolagem"><table><caption>${E(T("Bases abertas que o Mapeamento usa; fonte e licença a conferir"))}</caption><thead><tr><th scope="col">${E(T("Camada"))}</th><th scope="col">${E(T("Para quê"))}</th><th scope="col">${E(T("Quem usa"))}</th><th scope="col">${E(T("Fonte e licença"))}</th><th scope="col">${E(T("Formato e lugar no servidor"))}</th><th scope="col">${E(T("Situação"))}</th></tr></thead><tbody>
    ${cs.map(c => `<tr><th scope="row">${E(T(c.nome.pt))}</th><td>${E(T(c.finalidade.pt))}</td><td>${E(c.consumidores.join(", "))}</td><td class="t2 pq">${E(c.fonte.produto)} — ${E(c.fonte.nome)}; ${E(c.fonte.licenca)}</td><td class="t2 pq">${E(c.formato)} · ${E(c.chave_config)}</td><td>${c.status === "instalada" ? `<span class="selo ok">${E(T("instalada"))}</span>` : `<span class="selo at">${E(T("camada não instalada"))}</span>`}</td></tr>`).join("")}</tbody></table></div>
    <p class="t2 pq">${E(T("[CONFERIR]: o nome do produto, a versão e a licença de cada base são conferidos na página oficial antes de instalar. Nenhum dado vem copiado no sistema."))}</p></section>`; }
function parteArquivos() { const st = estado(); if (!emHub()) { const ls = lerLS("physis-mapeamento-arquivos") || [];
    return `<section class="cartao" aria-labelledby="h-mp-up"><h2 id="h-mp-up">${E(T("Abrir arquivo do cliente"))}</h2>${notaNav()}<p class="t2">${E(T("GeoJSON, KML/KMZ ou Shapefile (.zip com .shp, .dbf e .prj), em WGS 84 ou SIRGAS 2000 geográfico. Sem servidor, o arquivo é lido aqui e guardado só neste navegador; vai para o servidor quando ele existir."))}</p>
      <div><label for="mp-arquivo">${E(T("Arquivo"))}</label><input id="mp-arquivo" type="file" accept=".geojson,.json,.kml,.kmz,.zip" data-mp-arquivo="upload"></div><p class="t2" role="status" id="mp-up-msg">${E(T(st.upMsg || ""))}</p></section>
      <section class="cartao" aria-labelledby="h-mp-ups"><h2 id="h-mp-ups">${E(T("Arquivos neste navegador"))}</h2>${ls.length ? `<div class="rolagem"><table><caption>${E(T("Lidos no navegador (sem servidor)"))}</caption><thead><tr><th scope="col">${E(T("Nome"))}</th><th scope="col">${E(T("Formato"))}</th><th scope="col">${E(T("Feições"))}</th><th scope="col">${E(T("Tipos"))}</th></tr></thead><tbody>
      ${ls.map(x => `<tr><th scope="row">${E(x.nome)}</th><td>${E(x.formato)}</td><td>${E(x.feicoes)}</td><td>${E((x.tipos || []).join(", "))}</td></tr>`).join("")}</tbody></table></div>` : `<p class="t2">${E(T("Nenhum arquivo ainda."))}</p>`}</section>`; }
  buscar("ups", "api/mapeamento/uploads"); const ups = (st.ups && st.ups.uploads) || [];
  return `<section class="cartao" aria-labelledby="h-mp-up"><h2 id="h-mp-up">${E(T("Enviar arquivo do cliente"))}</h2><p class="t2">${E(T("GeoJSON, KML/KMZ ou Shapefile (.zip com .shp, .dbf e .prj). Coordenadas em WGS 84 (EPSG:4326) ou SIRGAS 2000 geográfico (EPSG:4674). Até 20 MB."))}</p>
    <div><label for="mp-arquivo">${E(T("Arquivo"))}</label><input id="mp-arquivo" type="file" accept=".geojson,.json,.kml,.kmz,.zip" data-mp-arquivo="upload"></div><p class="t2" role="status" id="mp-up-msg">${E(T(st.upMsg || ""))}</p></section>
    <section class="cartao" aria-labelledby="h-mp-ups"><h2 id="h-mp-ups">${E(T("Arquivos guardados"))}</h2>${ups.length ? `<div class="rolagem"><table><caption>${E(T("Arquivos do cliente com o resumo de integridade"))}</caption><thead><tr><th scope="col">${E(T("Nome"))}</th><th scope="col">${E(T("Formato"))}</th><th scope="col">${E(T("Sistema de coordenadas"))}</th><th scope="col">${E(T("Feições"))}</th><th scope="col">SHA-256</th></tr></thead><tbody>
    ${ups.map(x => `<tr><th scope="row">${E(x.nome)}</th><td>${E(x.formato)}</td><td>${E(x.crs)}${x.nota_crs ? `<br><span class="t2 pq">${E(T(x.nota_crs))}</span>` : ""}</td><td>${E(x.feicoes)}</td><td><code>${E(String(x.sha256).slice(0, 16))}…</code></td></tr>`).join("")}</tbody></table></div>` : `<p class="t2">${E(T("Nenhum arquivo ainda."))}</p>`}</section>`; }

/* ════════ Leitores de arquivo no navegador (sem servidor): os mesmos formatos do mapeamento.ler_arquivo ════════ */
async function inflarRaw(bytes) { const ds = new DecompressionStream("deflate-raw"), s = new Blob([bytes]).stream().pipeThrough(ds); return new Uint8Array(await new Response(s).arrayBuffer()); }
async function lerZip(buf) { const u = new Uint8Array(buf), dv = new DataView(buf), out = {};
  let e = -1; for (let i = u.length - 22; i >= Math.max(0, u.length - 65557); i--) if (dv.getUint32(i, true) === 0x06054b50) { e = i; break; }
  if (e < 0) throw new Error("zip sem diretório central");
  let p = dv.getUint32(e + 16, true); const n = dv.getUint16(e + 10, true);
  for (let k = 0; k < n; k++) { if (dv.getUint32(p, true) !== 0x02014b50) break;
    const met = dv.getUint16(p + 10, true), tam = dv.getUint32(p + 20, true), ln = dv.getUint16(p + 28, true), lx = dv.getUint16(p + 30, true), lc = dv.getUint16(p + 32, true), off = dv.getUint32(p + 42, true);
    const nome = new TextDecoder().decode(u.subarray(p + 46, p + 46 + ln)), ini = off + 30 + dv.getUint16(off + 26, true) + dv.getUint16(off + 28, true), dados = u.subarray(ini, ini + tam);
    out[nome] = met === 0 ? dados : met === 8 ? await inflarRaw(dados) : null; p += 46 + ln + lx + lc; }
  return out; }
function lerShp(shp, dbf) { const dv = new DataView(shp.buffer, shp.byteOffset, shp.byteLength), feats = []; let p = 100;
  while (p + 8 <= dv.byteLength) { const len = dv.getInt32(p + 4) * 2, r = p + 8, tipo = dv.getInt32(r, true); let g = null;
    if (tipo === 1 || tipo === 11 || tipo === 21) g = { type: "Point", coordinates: [dv.getFloat64(r + 4, true), dv.getFloat64(r + 12, true)] };
    else if ([3, 5, 13, 15, 23, 25].includes(tipo)) { const np = dv.getInt32(r + 36, true), nn = dv.getInt32(r + 40, true), partes = [], pts = [];
      for (let i = 0; i < np; i++) partes.push(dv.getInt32(r + 44 + 4 * i, true)); const b = r + 44 + 4 * np;
      for (let i = 0; i < nn; i++) pts.push([dv.getFloat64(b + 16 * i, true), dv.getFloat64(b + 16 * i + 8, true)]);
      const aneis = partes.map((s, i) => pts.slice(s, i + 1 < np ? partes[i + 1] : nn)); g = tipo % 10 === 5 ? { type: "Polygon", coordinates: aneis } : { type: "MultiLineString", coordinates: aneis }; }
    else if (tipo !== 0) throw new Error("tipo de geometria do Shapefile não aceito (" + tipo + ")");
    if (g) feats.push({ type: "Feature", geometry: g, properties: {} }); p = r + len; }
  if (dbf) { const d = new DataView(dbf.buffer, dbf.byteOffset, dbf.byteLength), nreg = d.getUint32(4, true), hl = d.getUint16(8, true), rl = d.getUint16(10, true), campos = [];
    for (let o = 32; o < hl - 1 && dbf[o] !== 0x0d; o += 32) campos.push({ nome: new TextDecoder("latin1").decode(dbf.subarray(o, o + 11)).replace(/\0.*$/, "").trim(), tam: dbf[o + 16] });
    for (let i = 0; i < Math.min(nreg, feats.length); i++) { let o = hl + i * rl + 1; campos.forEach(c => { feats[i].properties[c.nome] = new TextDecoder("latin1").decode(dbf.subarray(o, o + c.tam)).trim(); o += c.tam; }); } }
  return { type: "FeatureCollection", features: feats }; }
function lerKml(txt) { const doc = new DOMParser().parseFromString(txt, "application/xml"), feats = [];
  const coords = el => (el.textContent || "").trim().split(/\s+/).filter(Boolean).map(s => s.split(",").slice(0, 2).map(Number));
  [...doc.getElementsByTagName("Placemark")].forEach(pm => { const nome = (pm.getElementsByTagName("name")[0] || {}).textContent || "";
    [...pm.getElementsByTagName("Point")].forEach(p => feats.push({ type: "Feature", properties: { nome }, geometry: { type: "Point", coordinates: coords(p.getElementsByTagName("coordinates")[0])[0] } }));
    [...pm.getElementsByTagName("LineString")].forEach(p => feats.push({ type: "Feature", properties: { nome }, geometry: { type: "LineString", coordinates: coords(p.getElementsByTagName("coordinates")[0]) } }));
    [...pm.getElementsByTagName("Polygon")].forEach(p => feats.push({ type: "Feature", properties: { nome }, geometry: { type: "Polygon", coordinates: [...p.getElementsByTagName("coordinates")].map(coords) } })); });
  return { type: "FeatureCollection", features: feats }; }
async function lerArquivoNavegador(nome, buf) { const ext = (nome.split(".").pop() || "").toLowerCase(); let fc, formato;
  if (ext === "geojson" || ext === "json") { fc = JSON.parse(new TextDecoder().decode(buf)); formato = "GeoJSON"; if (fc.type === "Feature") fc = { type: "FeatureCollection", features: [fc] }; }
  else if (ext === "kml") { fc = lerKml(new TextDecoder().decode(buf)); formato = "KML"; }
  else if (ext === "kmz" || ext === "zip") { const z = await lerZip(buf), nomes = Object.keys(z), kml = nomes.find(n => /\.kml$/i.test(n)), shp = nomes.find(n => /\.shp$/i.test(n));
    if (kml) { fc = lerKml(new TextDecoder().decode(z[kml])); formato = "KMZ"; }
    else if (shp) { const prj = nomes.find(n => /\.prj$/i.test(n)), wkt = prj ? new TextDecoder().decode(z[prj]) : "";
      if (/PROJCS/i.test(wkt)) throw new Error("Shapefile em coordenadas projetadas (UTM): reprojete para WGS 84 ou SIRGAS 2000 geográfico.");
      fc = lerShp(z[shp], z[nomes.find(n => /\.dbf$/i.test(n))]); formato = "Shapefile"; }
    else throw new Error("o .zip não tem .shp nem .kml"); }
  else throw new Error("formato não aceito: use GeoJSON, KML/KMZ ou Shapefile em .zip");
  const feats = (fc && fc.features) || [];
  if (!feats.length) throw new Error("nenhuma feição no arquivo");
  const fora = feats.some(f => { const c = JSON.stringify(f.geometry && f.geometry.coordinates || []).match(/-?\d+(\.\d+)?/g) || []; for (let i = 0; i + 1 < c.length; i += 2) if (Math.abs(+c[i]) > 180 || Math.abs(+c[i + 1]) > 90) return true; return false; });
  if (fora) throw new Error("coordenadas fora de graus (projetadas?): reprojete para WGS 84 ou SIRGAS 2000 geográfico");
  return { nome, formato, feicoes: feats.length, tipos: [...new Set(feats.map(f => f.geometry && f.geometry.type))], geojson: fc }; }

/* ════════ Parte: sol nas superfícies (mapa de calor) ════════ */
function calcularSuperficies() { const st = estado(), L = lugar(), ir = irradiacao(L), S = planejador(), hp = num(st.cfg.altura_pav);
  if (!L || !ir) return { erro: !L ? "Falta a localização (Início)." : "Sem a irradiação do lugar (a mesma da aba Solar): abra com o servidor ou espere a base carregar." };
  const g = S ? gradeDoLote(S, 40) : null, cx = caixasDoLote(S, g, hp), lat = (S && S.terreno && S.terreno.lat0) != null ? S.terreno.lat0 : L.lat;
  const chave = JSON.stringify([ir.H, lat, hp, S && S.log && S.log[0] && S.log[0].t, S && (S.itens || []).length]);
  if (st.sup && st.supChave === chave) return st.sup;
  const pol = S && S.terreno && S.terreno.poly && S.terreno.poly.length ? S.terreno.poly : null;
  const cel = g ? celulasTerreno(g, 300, pol ? p => dentroPoligono(p, pol) : null) : [], tel = cx.flatMap(planosTelhado), fac = cx.flatMap(fachadas);
  st.sup = { lat, H: ir.H, fonte: ir.fonte, grade: g, caixas: cx, terreno: incidencia(ir.H, lat, cel, g, cx), telhados: incidencia(ir.H, lat, tel, g, cx), fachadas: incidencia(ir.H, lat, fac, g, cx),
    semAltura: !(hp > 0) && ((S && S.itens) || []).some(i => i && i.pav != null && !(i.h > 0)) };
  st.supChave = chave; return st.sup; }
function mapaCalor(r) { const cel = r.terreno; if (!cel.length || !r.grade) return `<p class="t2">${E(T("Sem lote desenhado no Planejador: só os telhados e as fachadas."))}</p>`;
  const g = r.grade, W = 360, H = Math.round(W * g.ny / g.nx), k = W / ((g.nx - 1) * g.cs), vs = cel.map(c => c.anual_kwh_m2), a = Math.min(...vs), b = Math.max(...vs);
  const passo = Math.max(1, Math.round(Math.sqrt(((g.nx - 2) * (g.ny - 2)) / cel.length))), lado = g.cs * passo * k;
  const rects = cel.map(c => `<rect x="${((c.x - g.x0) * k - lado / 2).toFixed(1)}" y="${(H - (c.y - g.y0) * k - lado / 2).toFixed(1)}" width="${(lado + 0.5).toFixed(1)}" height="${(lado + 0.5).toFixed(1)}" fill="${cor(c.anual_kwh_m2, a, b)}"/>`).join("");
  const caixas = r.caixas.map(c => { const rr = (c.rot || 0) * RAD, pts = [[-c.w / 2, -c.d / 2], [c.w / 2, -c.d / 2], [c.w / 2, c.d / 2], [-c.w / 2, c.d / 2]].map(([x, y]) => [c.x + x * Math.cos(rr) - y * Math.sin(rr), c.y + x * Math.sin(rr) + y * Math.cos(rr)]);
    return `<polygon points="${pts.map(p => ((p[0] - g.x0) * k).toFixed(1) + "," + (H - (p[1] - g.y0) * k).toFixed(1)).join(" ")}" fill="none" stroke="#1B1F23" stroke-width="1.5"/>`; }).join("");
  const svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px;border-radius:8px" role="img" aria-label="${E(T("Sol no terreno"))}: ${f1(a, 0)} a ${f1(b, 0)} kWh/m²·ano">${rects}${caixas}<text x="${W - 6}" y="14" font-size="12" text-anchor="end" style="fill:#1B1F23">N ↑</text></svg>
    <span class="t2 pq"><span aria-hidden="true" style="display:inline-block;width:80px;height:9px;vertical-align:middle;background:linear-gradient(90deg,${RAMPA.join(",")})"></span> ${f1(a, 0)} ${E(T("a"))} ${f1(b, 0)} kWh/m²·${E(T("ano"))}</span>`;
  return conforto() ? `<details><summary>${E(T("Ver o mapa de calor"))}</summary>${svg}</details>` : svg; }
function tabelaSup(tit, l) { if (!l.length) return ""; return `<div class="rolagem"><table><caption>${E(T(tit))}</caption><thead><tr><th scope="col">${E(T("Superfície"))}</th><th scope="col">${E(T("Inclinação"))}</th><th scope="col">${E(T("Orientação"))}</th><th scope="col">kWh/m²·${E(T("ano"))}</th><th scope="col">${E(T("Sombra"))}</th></tr></thead><tbody>
  ${l.map(s => `<tr><th scope="row">${E(T(s.nome || s.id))}</th><td>${f1(s.incl, 0)}°</td><td>${f1(s.azim, 0)}°</td><td>${f1(s.anual_kwh_m2, 0)}</td><td>${f1(s.sombra_pct, 0)} %</td></tr>`).join("")}</tbody></table></div>`; }
function parteSol() { const st = estado(), r = calcularSuperficies();
  const alt = `<div class="precos">${campo("altura_pav", "Altura por pavimento (m)", st.cfg.altura_pav, "conferir no projeto", "Usada só quando o Planejador não traz a altura da edificação. Vazio: prédios sem altura não fazem sombra.")}</div>`;
  if (r.erro) return alt + faixa("in", "Ainda não dá para calcular.", r.erro);
  return alt + (r.semAltura ? faixa("at", "Atenção.", "Há edificações sem altura: informe a altura por pavimento para elas entrarem na sombra.") : "") +
    `<section class="cartao" aria-labelledby="h-mp-sol"><h2 id="h-mp-sol">${E(T("Sol nas superfícies"))}</h2><p class="t2">${E(T("Irradiação"))}: ${E(T(r.fonte))}. ${E(T("Sombra do terreno e dos prédios por marcha de raio em 36 direções."))}</p>${mapaCalor(r)}
    ${tabelaSup("Telhados", r.telhados)}${tabelaSup("Fachadas (para o AVAC)", r.fachadas)}
    <p><button type="button" data-mp-acao="enviar-incidencia">${E(T("Enviar para Solar e AVAC"))}</button> <span class="t2" role="status">${E(T(st.incMsg || ""))}</span></p></section>`; }
function enviarIncidencia() { const r = calcularSuperficies(); if (r.erro) return "";
  const pack = s => ({ id: s.id, nome: s.nome || s.id, tipo: s.tipo, incl: s.incl, azim: s.azim, area_m2: s.area_m2, anual_kwh_m2: s.anual_kwh_m2, mensal_kwh_m2_dia: s.mensal_kwh_m2_dia, sombra_pct: s.sombra_pct, fator_mensal: s.fator_mensal });
  gravarLS("physis-calc-incidencia", { esquema: "physis-incidencia/1", superficies: r.telhados.concat(r.fachadas).map(pack), terreno_resumo: r.terreno.length ? { celulas: r.terreno.length, min: Math.min(...r.terreno.map(c => c.anual_kwh_m2)), max: Math.max(...r.terreno.map(c => c.anual_kwh_m2)) } : null,
    irradiacao_fonte: r.fonte, lat: r.lat, fonte: "Mapeamento", atualizado: new Date().toISOString() });
  gravarLS("physis-geometria-lugar", geometriaParaSimulacao());
  return "Enviado: a aba Solar e o AVAC leem physis-calc-incidencia."; }
/* contrato com o motor de simulação (physis-geometria-lugar/1; espelho de mapeamento.geometria_para_simulacao): só dados */
function geometriaParaSimulacao() { const r = calcularSuperficies(), L = lugar(); if (r.erro) return null;
  return { esquema: "physis-geometria-lugar/1", origem: { lat: L ? L.lat : null, lon: L ? L.lon : null }, terreno: r.grade ? { x0: r.grade.x0, y0: r.grade.y0, cs: r.grade.cs, nx: r.grade.nx, ny: r.grade.ny, Z: r.grade.Z, unidade: "m" } : null,
    edificacoes: r.caixas.map(c => ({ id: c.id, nome: c.nome, x: c.x, y: c.y, w: c.w, d: c.d, rot: c.rot, h: c.h, z0: c.z0 })),
    superficies: r.telhados.concat(r.fachadas, r.terreno).map(s => ({ id: s.id, tipo: s.tipo, x: s.x, y: s.y, z: s.z, incl: s.incl, azim: s.azim, area_m2: s.area_m2, anual_kwh_m2: s.anual_kwh_m2, mensal_kwh_m2_dia: s.mensal_kwh_m2_dia })),
    elementos_bim: elementosBim().map(e => ({ id: e.id, tipo: e.tipo, posicao_m: e.posicao || {}, caixa_m: e.caixa || {}, materiais: e.materiais || [] })), fonte: "Mapeamento", atualizado: new Date().toISOString() }; }

/* ════════ Parte: planta solar (BIM) ════════ */
function superficiesPlanta() { const r = calcularSuperficies(), S = planejador(), out = [];
  if (!r.erro) r.telhados.forEach(s => out.push({ id: s.id, nome: s.nome, plano: "telhado", incl: s.incl, azim: s.azim, anual: s.anual_kwh_m2, fator: s.fator_mensal,
    poligono: [[0, 0], [s.largura_m, 0], [s.largura_m, s.comprimento_agua_m], [0, s.comprimento_agua_m]] }));
  if (S && S.terreno && (S.terreno.poly || []).length >= 3) out.push({ id: "lote", nome: "Área no solo: lote inteiro", plano: "solo", poligono: S.terreno.poly });
  const c = estado().cfg, w = num(c.solo_w), d = num(c.solo_d), tw = num(c.tel_w), tc = num(c.tel_c), ti = num(c.tel_incl), ta = num(c.tel_azim);
  if (tw > 0 && tc > 0 && ti != null && ta != null) out.push({ id: "telhado-digitado", nome: "Telhado digitado", plano: "telhado", incl: ti, azim: ta, anual: null, fator: null,
    poligono: [[0, 0], [tw, 0], [tw, tc], [0, tc]] });
  if (w > 0 && d > 0) { const x = num(c.solo_x) || 0, y = num(c.solo_y) || 0, rr = (num(c.solo_rot) || 0) * RAD;
    out.push({ id: "retangulo", nome: "Área no solo: retângulo desenhado", plano: "solo", poligono: [[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]].map(([a, b]) => [x + a * Math.cos(rr) - b * Math.sin(rr), y + a * Math.sin(rr) + b * Math.cos(rr)]) }); }
  return out; }
function calcularPlanta() { const st = estado(), c = st.cfg, L = lugar(), S = SOL(), r = calcularSuperficies();
  if (!S) return { erro: "A aba Solar não está carregada: a planta usa as contas dela (módulos, inversores, perdas e strings)." };
  if (r.erro) return { erro: r.erro };
  const sups = superficiesPlanta(), sup = sups.find(s => s.id === c.superficie) || sups[0];
  if (!sup) return { erro: "Nenhuma superfície: desenhe o lote ou as edificações com telhado no Planejador, ou digite abaixo uma área no solo ou um telhado.", semSuperficie: true };
  const mods = S.MODULOS, m0 = mods.find(m => m.id === c.modulo) || mods[0], dims = dimensoesModulo(m0.id) || {};
  const mod = Object.assign({}, m0, { comprimento_m: num(c.mod_c) || dims.comprimento_m, largura_m: num(c.mod_l) || dims.largura_m, fonte_dim: num(c.mod_c) ? "digitada" : dims.fonte });
  const af = num(c.afastamento) != null ? num(c.afastamento) : premissa(PREM.afastamento), fo = num(c.folga) != null ? num(c.folga) : premissa(PREM.folga);
  const h0 = num(c.hora_ini) != null ? num(c.hora_ini) : premissa(PREM.hora_ini), h1 = num(c.hora_fim) != null ? num(c.hora_fim) : premissa(PREM.hora_fim);
  const faltam = [[mod.comprimento_m, "comprimento do módulo"], [mod.largura_m, "largura do módulo"], [af, "afastamento das bordas (premissa " + PREM.afastamento + " [CONFERIR])"], [fo, "folga entre módulos (premissa " + PREM.folga + " [CONFERIR])"]]
    .concat(sup.plano === "solo" ? [[h0, "hora crítica de início (premissa " + PREM.hora_ini + " [CONFERIR])"], [h1, "hora crítica de fim (premissa " + PREM.hora_fim + " [CONFERIR])"]] : []).filter(x => x[0] == null).map(x => x[1]);
  if (faltam.length) return { sup, sups, mod, falta: faltam };
  const incl = sup.plano === "telhado" ? sup.incl : (num(c.incl) != null ? num(c.incl) : Math.round(Math.abs(r.lat))), azim = sup.plano === "telhado" ? sup.azim : (num(c.azim) != null ? num(c.azim) : (r.lat < 0 ? 0 : 180));
  const A = arranjo(sup.poligono, mod, { orientacao: c.orientacao || "retrato", empilhados: num(c.empilhados) || 1, incl, azim, afastamento_m: af, folga_m: fo, passo_m: num(c.passo), plano: sup.plano, lat: r.lat, horas: [h0, h1],
    obstaculos: sup.plano === "solo" ? r.caixas.map(b => { const rr = (b.rot || 0) * RAD, w = b.w / 2 + af, d = b.d / 2 + af; return [[-w, -d], [w, -d], [w, d], [-w, d]].map(([x, y]) => [b.x + x * Math.cos(rr) - y * Math.sin(rr), b.y + x * Math.sin(rr) + y * Math.cos(rr)]); }) : [] });
  /* sombra do horizonte no centro da superfície e irradiação no plano das placas */
  const ctr = sup.plano === "telhado" ? (r.telhados.find(t => t.id === sup.id) || { x: 0, y: 0, z: num(c.tel_altura) != null ? num(c.tel_altura) : 3 }) : { x: sup.poligono.reduce((s, p) => s + p[0], 0) / sup.poligono.length, y: sup.poligono.reduce((s, p) => s + p[1], 0) / sup.poligono.length };
  const z = sup.plano === "telhado" ? ctr.z : (r.grade ? zGrade(r.grade, ctr.x, ctr.y) + 1 : 1), hz = (r.grade || r.caixas.length) ? horizonte(ctr.x || 0, ctr.y || 0, z, r.grade, r.caixas, sup.plano === "telhado" ? ctr.caixa : null) : null;
  const inc = incidenciaSuperficie(r.H, r.lat, incl, azim, hz), Tm = temperaturas(L), invs = S.INVERSORES, inv = invs.find(v => v.id === c.inversor) || invs[0];
  /* energia do mês e do ano: a conta da aba Solar, com o fator do plano daqui (já com a sombra do horizonte) */
  const R = A.kwp > 0 ? S.calcular({ H: r.H, T: Tm || undefined, fator_plano: inc.fator_mensal, kwp: A.kwp, modulo: mod, inversor: inv, pca: inv.pca, tmin: num(c.tmin) != null ? num(c.tmin) : undefined, tmax: num(c.tmax) != null ? num(c.tmax) : undefined }) : null;
  const pq = potencias(inv.pca, num(c.fp)), fp = pq.fp;
  return { sup, sups, mod, A, inc, hz, R, inv, fp, pq, incl, azim, lat: r.lat, H: r.H, T: Tm, fonte: r.fonte }; }
function cartaSVG(lat, hz) { const W = 320, c = W / 2, R = W / 2 - 24, p = (alt, az) => { const r = R * (90 - alt) / 90; return [c + r * Math.sin(az * RAD), c - r * Math.cos(az * RAD)]; };
  const aneis = [0, 30, 60].map(a => `<circle cx="${c}" cy="${c}" r="${(R * (90 - a) / 90).toFixed(1)}" fill="none" style="stroke:var(--linha,#D9D3C2)"/>`).join("");
  const hor = hz ? `<path d="${hz.map((h, k) => { const q = p(h / RAD, k * 10); return (k ? "L" : "M") + q[0].toFixed(1) + " " + q[1].toFixed(1); }).join(" ")} Z M ${c + R} ${c} A ${R} ${R} 0 1 0 ${c - R} ${c} A ${R} ${R} 0 1 0 ${c + R} ${c} Z" fill="#B9A97F" fill-opacity=".45" fill-rule="evenodd"/>` : "";
  const dias = [[SOLSTICIO_JUN, "#2F7D5B", "junho"], [EQUINOCIO_MAR, "#4A8A5A", "março e setembro"], [SOLSTICIO_DEZ, "#A85432", "dezembro"]].map(([dn, cr]) => { const [n0, n1] = nascerPor(lat, dn), pts = [];
    for (let h = n0; h <= n1; h += 0.25) { const s = solEm(lat, dn, h); if (s.altura >= 0) pts.push(p(s.altura, s.azimute)); }
    return `<polyline fill="none" style="stroke:${cr}" stroke-width="2.5" points="${pts.map(q => q[0].toFixed(1) + "," + q[1].toFixed(1)).join(" ")}"/>`; }).join("");
  const rot = [["N", 0], ["L", 90], ["S", 180], ["O", 270]].map(([t, a]) => { const q = p(-10, a); return `<text x="${q[0].toFixed(1)}" y="${(q[1] + 4).toFixed(1)}" font-size="12" text-anchor="middle" style="fill:var(--tinta2,#4A4F44)">${t}</text>`; }).join("");
  return `<figure style="margin:0"><svg viewBox="0 0 ${W} ${W}" width="100%" style="max-width:${W}px" role="img" aria-label="${E(T("Carta solar do lugar com o horizonte"))}">${hor}${aneis}${dias}${rot}</svg>
    <figcaption class="t2 pq">${E(T("Azul: solstício de junho; verde: equinócios; laranja: solstício de dezembro. Areia: horizonte (terreno e prédios vizinhos). Anéis: 0°, 30° e 60° de altura."))}</figcaption></figure>`; }
/* área no solo (retângulo) e telhado digitado: a planta funciona sem o Planejador (instalações só com a Solar) */
function formsSuperficie(c, abrir) {
  return `<details${abrir ? " open" : ""}><summary>${E(T("Área no solo (retângulo): largura × comprimento"))}</summary><div class="precos">${campo("solo_w", "Largura (m)", c.solo_w)}${campo("solo_d", "Profundidade (m)", c.solo_d)}${campo("solo_x", "Centro x (m)", c.solo_x, "0")}${campo("solo_y", "Centro y (m)", c.solo_y, "0")}${campo("solo_rot", "Giro (°)", c.solo_rot, "0")}${campo("incl", "Inclinação das placas (°)", c.incl)}${campo("azim", "Azimute das placas (°, 0 = norte)", c.azim)}</div></details>
    <details${abrir ? " open" : ""}><summary>${E(T("Telhado digitado (sem o Planejador)"))}</summary><div class="precos">${campo("tel_w", "Largura do telhado (m)", c.tel_w)}${campo("tel_c", "Comprimento da água (m)", c.tel_c)}${campo("tel_incl", "Inclinação do telhado (°)", c.tel_incl)}${campo("tel_azim", "Para onde a água aponta (°, 0 = norte)", c.tel_azim)}${campo("tel_altura", "Altura do telhado (m)", c.tel_altura, "3")}</div></details>`; }
function partePlanta() { const st = estado(), c = st.cfg, P = calcularPlanta(), Sx = SOL();
  if (P.erro) return faixa("in", "Ainda não dá para montar a planta.", P.erro) + (P.semSuperficie ? formsSuperficie(c, true) : "");
  const sel = lista("superficie", "Onde vai a planta", P.sups.map(s => [s.id, s.nome + (s.anual != null ? ` · ${f1(s.anual, 0)} kWh/m²·ano` : "")]), P.sup.id);
  const solo = formsSuperficie(c, false);
  const modSel = lista("modulo", "Módulo (base de equipamentos)", Sx.MODULOS.map(m => [m.id, m.nome]), P.mod.id);
  const arr = `<div class="precos">${modSel}${campo("mod_c", "Comprimento do módulo (m)", c.mod_c, P.mod.comprimento_m != null ? f1(P.mod.comprimento_m, 2) : "da folha de dados", P.mod.fonte_dim ? "Vazio: " + P.mod.fonte_dim : "")}${campo("mod_l", "Largura do módulo (m)", c.mod_l, P.mod.largura_m != null ? f1(P.mod.largura_m, 2) : "da folha de dados")}
    ${lista("orientacao", "Posição do módulo", [["retrato", "Retrato (em pé)"], ["paisagem", "Paisagem (deitado)"]], c.orientacao || "retrato")}${campo("empilhados", "Módulos por mesa (na inclinação)", c.empilhados, "1")}
    ${P.sup.plano === "solo" ? campo("passo", "Passo entre fileiras (m)", c.passo, "vazio: o mínimo sem sombra") : ""}
    ${campo("afastamento", "Afastamento das bordas (m)", c.afastamento, premissa(PREM.afastamento) != null ? f1(premissa(PREM.afastamento), 2) : "premissa a criar [CONFERIR]")}${campo("folga", "Folga entre módulos (m)", c.folga, premissa(PREM.folga) != null ? f1(premissa(PREM.folga), 2) : "premissa a criar [CONFERIR]")}
    ${P.sup.plano === "solo" ? campo("hora_ini", "Hora crítica, início (hora solar)", c.hora_ini, premissa(PREM.hora_ini) != null ? f1(premissa(PREM.hora_ini), 0) : "premissa a criar [CONFERIR]") + campo("hora_fim", "Hora crítica, fim (hora solar)", c.hora_fim, premissa(PREM.hora_fim) != null ? f1(premissa(PREM.hora_fim), 0) : "premissa a criar [CONFERIR]") : ""}</div>`;
  if (P.falta) return sel + solo + arr + faixa("at", "Falta informar:", P.falta.join("; ") + ".");
  const A = P.A, sb = A.sombra_entre_fileiras;
  const res = `<div class="grade">${cartao("mp-n", "Módulos", f1(A.modulos, 0), A.mesas + " mesas")}${cartao("mp-kwp", "Potência", f1(A.kwp, 2), "kWp")}${cartao("mp-area", "Área dos módulos", f1(A.area_modulos_m2, 1), "m² (ocupada " + f1(A.area_ocupada_m2, 1) + " m²)")}${cartao("mp-passo", "Passo entre fileiras", f1(A.passo_m, 2), "m")}</div>
    ${sb ? (sb.sombreia ? faixa("al", "Sombra entre fileiras.", `No solstício de inverno, entre ${f1(sb.horas[0], 0)} h e ${f1(sb.horas[1], 0)} h (hora solar), a sombra chega a ${f1(sb.sombra_max_m, 2)} m e o vão é de ${f1(sb.vao_m, 2)} m: aumente o passo para ${f1(sb.passo_minimo_m, 2)} m.`) : faixa("ok", "Sem sombra entre fileiras", `no solstício de inverno, entre ${f1(sb.horas[0], 0)} h e ${f1(sb.horas[1], 0)} h (hora solar).`)) : ""}`;
  const W = 360, xs = P.sup.poligono.map(p => p[0]), ys = P.sup.poligono.map(p => p[1]), x0 = Math.min(...xs), y0 = Math.min(...ys), esc = W / Math.max(Math.max(...xs) - x0, Math.max(...ys) - y0, 1), Hh = Math.round((Math.max(...ys) - y0) * esc) + 2;
  const pol = `<polygon points="${P.sup.poligono.map(p => ((p[0] - x0) * esc).toFixed(1) + "," + (Hh - (p[1] - y0) * esc).toFixed(1)).join(" ")}" fill="#EFE8D6" stroke="#4A4F44"/>`;
  const r0 = (P.sup.plano === "telhado" ? 0 : P.azim) * RAD, mw = A.du * esc, mh = A.dv * (P.sup.plano === "telhado" ? 1 : Math.cos(P.incl * RAD)) * esc;
  const mods = A.posicoes.length <= 3000 ? A.posicoes.map(q => `<rect x="${((q.x - x0) * esc - mw / 2).toFixed(1)}" y="${(Hh - (q.y - y0) * esc - mh / 2).toFixed(1)}" width="${mw.toFixed(1)}" height="${mh.toFixed(1)}" fill="#4A4F44" stroke="#EFE8D6" stroke-width=".5" transform="rotate(${(r0 / RAD).toFixed(1)} ${((q.x - x0) * esc).toFixed(1)} ${(Hh - (q.y - y0) * esc).toFixed(1)})"/>`).join("") : "";
  const desenho = `<svg viewBox="0 0 ${W} ${Hh}" width="100%" style="max-width:${W}px" role="img" aria-label="${E(T("Arranjo das placas na superfície"))}: ${A.modulos} ${E(T("módulos"))}">${pol}${mods}</svg>`;
  /* curva do dia desde o nascer do sol */
  const dias = DIA_REP.map((d, m) => [String(d), MESES[m] + " (dia médio)"]).concat([[String(SOLSTICIO_JUN), "solstício de junho"], [String(SOLSTICIO_DEZ), "solstício de dezembro"], [String(EQUINOCIO_MAR), "equinócio de março"], [String(EQUINOCIO_SET), "equinócio de setembro"]]);
  const dn = +(c.dia || SOLSTICIO_JUN), mIdx = dn === SOLSTICIO_JUN ? 5 : dn === SOLSTICIO_DEZ ? 11 : dn === EQUINOCIO_MAR ? 2 : dn === EQUINOCIO_SET ? 8 : Math.max(0, DIA_REP.indexOf(dn));
  const cv = curvaDiaria(P.H[mIdx], P.lat, dn, P.incl, P.azim, P.hz, null, 0.25, P.inc.mensal_kwh_m2_dia[mIdx]), tA = P.T ? P.T[mIdx] : 25;
  const pca = potenciaCA(cv, A.kwp, tA, P.mod, P.inv.eta) || [];
  const curva = `${lista("dia", "Dia da curva", dias, String(dn))}<p class="t2">${E(T("Nascer do sol"))} ${horaTxt(cv.nascer_h)} · ${E(T("pôr do sol"))} ${horaTxt(cv.por_h)} (${E(T("hora solar"))}) · ${f1(cv.total_kwh_m2, 2)} kWh/m² ${E(T("no plano das placas"))}${P.T ? "" : " · " + E(T("temperatura de 25 °C (sem a base de temperatura)"))}</p>
    ${graficoLinhas("mp-g-curva", "Irradiância no plano das placas, do nascer ao pôr do sol", [{ nome: "Irradiância (W/m²)", cor: "#C08A1E", pts: cv.pontos }], "W/m²", horaTxt)}
    ${graficoLinhas("mp-g-ca", "Potência CA estimada", [{ nome: "Potência CA (kW)", cor: "#1A4D2E", pts: pca }], "kW", horaTxt)}
    <details><summary>${E(T("Ver os números da curva"))}</summary><div class="rolagem"><table><caption>${E(T("Hora a hora"))}</caption><thead><tr><th scope="col">${E(T("Hora"))}</th><th scope="col">W/m²</th><th scope="col">kW</th></tr></thead><tbody>${cv.pontos.filter((_, i) => i % 4 === 2).map((p, i) => `<tr><th scope="row">${horaTxt(p[0])}</th><td>${f1(p[1], 0)}</td><td>${f1((pca[i * 4 + 2] || [0, null])[1], 2)}</td></tr>`).join("")}</tbody></table></div></details>`;
  const R = P.R, ener = R ? `<div class="rolagem"><table><caption>${E(T("Energia mês a mês (contas da aba Solar)"))}</caption><thead><tr><th scope="col">${E(T("Mês"))}</th><th scope="col">kWh/m²·${E(T("dia no plano"))}</th><th scope="col">kWh</th></tr></thead><tbody>${R.meses.map((x, m) => `<tr><th scope="row">${E(T(MESES[m]))}</th><td>${f1(x.H * x.fp, 2)}</td><td>${f1(x.kwh_kwp * R.kwp, 0)}</td></tr>`).join("")}</tbody><tfoot><tr><th scope="row">${E(T("Ano"))}</th><td>${f1(R.h_plano, 0)} kWh/m²</td><td>${f1(R.ger, 0)}</td></tr></tfoot></table></div><p class="t2 pq">PR ${f1(R.pr * 100, 1)} % · ${E(T("sombra do horizonte"))} ${f1(P.inc.sombra_pct, 1)} %</p>` : "";
  const st_ = R && R.strings, ele = `<div class="precos">${lista("inversor", "Inversor (base de equipamentos)", Sx.INVERSORES.map(v => [v.id, v.nome]), P.inv.id)}${campo("tmin", "Temperatura mínima do lugar (°C)", c.tmin, "a da aba Solar")}${campo("tmax", "Temperatura máxima do lugar (°C)", c.tmax, "a da aba Solar")}${campo("fp", "Fator de potência", c.fp, premissa(PREMISSA_FP) != null ? f1(premissa(PREMISSA_FP), 2) : "premissa " + PREMISSA_FP + " [CONFERIR]")}</div>
    ${st_ ? `<p>${st_.strings ? `${E(T("Strings"))}: <strong>${st_.strings} × ${st_.em_serie}</strong> ${E(T("módulos em série"))} (${E(T("faixa que cabe no MPPT"))}: ${st_.n_min} ${E(T("a"))} ${st_.n_sup}); ${E(T("tensão de circuito aberto no frio"))} ${f1(st_.voc_string, 0)} V.` : ""}</p>${(st_.avisos || []).map(a => `<p class="t2">${E(T(a))}</p>`).join("")}` : ""}
    ${P.pq.bruto && PC().potenciasHtml ? PC().potenciasHtml([[P.inv.nome, P.pq.bruto]], /^en/i.test(document.documentElement.lang || ""), T("Potência na saída CA do inversor")) : `<p>${E(T("Fator de potência"))} [CONFERIR] ${E(PREMISSA_FP)}</p>`}`;
  return sel + solo + `<section class="cartao" aria-labelledby="h-mp-arr"><h2 id="h-mp-arr">${E(T("Arranjo das placas"))}</h2>${arr}${res}${desenho}</section>
    <section class="cartao" aria-labelledby="h-mp-carta"><h2 id="h-mp-carta">${E(T("Carta solar e horizonte"))}</h2>${cartaSVG(P.lat, P.hz)}</section>
    <section class="cartao" aria-labelledby="h-mp-curva"><h2 id="h-mp-curva">${E(T("O dia desde o nascer do sol"))}</h2>${curva}</section>
    <section class="cartao" aria-labelledby="h-mp-ener"><h2 id="h-mp-ener">${E(T("Energia no mês e no ano"))}</h2>${ener}</section>
    <section class="cartao" aria-labelledby="h-mp-ele"><h2 id="h-mp-ele">${E(T("Elétrica"))}</h2>${ele}</section>
    <p><button type="button" data-mp-acao="enviar-planta">${E(T("Enviar para a aba Solar e para o BIM"))}</button> <span class="t2" role="status">${E(T(st.plMsg || ""))}</span></p>`; }
function enviarPlanta() { const P = calcularPlanta(); if (P.erro || P.falta) return "Complete a planta antes de enviar.";
  const A = P.A, R = P.R, st_ = R && R.strings;
  gravarLS("physis-calc-planta-solar", { esquema: "physis-planta-solar/1", superficie: { id: P.sup.id, nome: P.sup.nome, plano: P.sup.plano }, modulo: { id: P.mod.id, pmax: P.mod.pmax, comprimento_m: P.mod.comprimento_m, largura_m: P.mod.largura_m },
    modulos: A.modulos, kwp: A.kwp, area_modulos_m2: A.area_modulos_m2, incl: P.incl, azim: P.azim, passo_m: A.passo_m, orientacao: A.orientacao, sombra_entre_fileiras: A.sombra_entre_fileiras ? A.sombra_entre_fileiras.sombreia : null,
    fator_plano_mensal: P.inc.fator_mensal, irradiacao_plano_kwh_m2_ano: P.inc.anual_kwh_m2, sombra_horizonte_pct: P.inc.sombra_pct, geracao_kwh_ano: R ? R.ger : null, geracao_kwh_mes: R ? R.meses.map(x => x.kwh_kwp * R.kwp) : null,
    inversor: P.inv.id, strings: st_ ? st_.strings : null, modulos_por_string: st_ ? st_.em_serie : null, fator_potencia: P.fp, P_kW: P.pq.P, Q_kvar: P.pq.Q, S_kVA: P.pq.S,
    posicoes: A.posicoes.slice(0, 3000), irradiacao_fonte: P.fonte, fonte: "Mapeamento", atualizado: new Date().toISOString() });
  enviarParaBim("solar", [{ id: "pv-" + P.sup.id, tipo: "pv", nome: "Arranjo fotovoltaico · " + P.sup.nome, propriedades: { modulos: A.modulos, kwp: A.kwp, incl_graus: P.incl, azim_graus: P.azim, passo_fileiras_m: A.passo_m, inversor: P.inv.id,
      strings: st_ ? st_.strings : null, modulos_por_string: st_ ? st_.em_serie : null, energia_kwh_ano: R ? R.ger : null, fator_potencia: P.fp }, caixa: { dx: Math.max(0.1, A.du), dy: Math.max(0.1, A.dv), dz: 0.05 },
      modulos: P.sup.plano === "solo" ? A.posicoes.slice(0, 2000).map(q => ({ x: q.x, y: q.y, z: 0 })) : [] },
    { id: "inv-" + P.sup.id, tipo: "inversor", nome: P.inv.nome, propriedades: { potencia_kw: P.inv.pca, fator_potencia: P.fp } }]);
  return "Enviado: a aba Solar lê physis-calc-planta-solar e o BIM recebeu o arranjo e o inversor."; }

/* ════════ Parte: BIM (IFC) ════════ */
function parteBim() { const st = estado(), els = elementosBim(), L = lugar();
  const tab = els.length ? `<div class="rolagem"><table><caption>${E(T("Sistemas que os módulos mandaram"))}</caption><thead><tr><th scope="col">${E(T("Elemento"))}</th><th scope="col">${E(T("Tipo"))}</th><th scope="col">${E(T("Origem"))}</th></tr></thead><tbody>${els.map(e => `<tr><th scope="row">${E(e.nome || e.id)}</th><td>${E(e.tipo)}</td><td>${E(e.origem || "")}</td></tr>`).join("")}</tbody></table></div>` : `<p class="t2">${E(T("Nenhum sistema enviado ainda: a planta solar, a cisterna, as calhas, o AVAC, o quadro, o biodigestor, as turbinas e o viveiro aparecem aqui quando os módulos mandarem."))}</p>`;
  return `<section class="cartao" aria-labelledby="h-mp-bim"><h2 id="h-mp-bim">${E(T("Modelo BIM aberto (IFC4)"))}</h2>${tab}
    ${notaNav()}<p><button type="button" data-mp-acao="ifc"${!L || !els.length || (!emHub() && !window.PhysisIFC) ? " disabled" : ""}>${E(T("Baixar o IFC"))}</button> <span class="t2" role="status">${E(T(st.ifcMsg || ""))}</span></p>
    <p class="t2 pq">${E(T("Fator de potência, potência ativa, reativa e aparente vão em todo equipamento elétrico (premissa eletrica.fator_potencia_padrao)."))}</p></section>
    <section class="cartao" aria-labelledby="h-mp-ler"><h2 id="h-mp-ler">${E(T("Abrir um IFC"))}</h2><p class="t2">${E(T("Leitura básica: terreno, edificações, pavimentos, quantos elementos de cada tipo e o tamanho. A geometria completa fica para um visualizador IFC aberto (Fase 2)."))}</p>
    <div><label for="mp-ifc">${E(T("Arquivo IFC"))}</label><input id="mp-ifc" type="file" accept=".ifc" data-mp-arquivo="ifc"${emHub() || window.PhysisIFC ? "" : " disabled"}></div>${st.ifcLido ? resumoIfc(st.ifcLido) : ""}</section>`; }
function resumoIfc(r) { return `<div class="rolagem"><table><caption>${E(T("Resumo do IFC"))}</caption><tbody><tr><th scope="row">${E(T("Esquema"))}</th><td>${E(r.esquema)}</td></tr><tr><th scope="row">${E(T("Projeto"))}</th><td>${E(r.projeto)}</td></tr>
  ${(r.terrenos || []).map(s => `<tr><th scope="row">${E(T("Terreno"))}</th><td>${E(s.nome)} · ${f1(s.lat, 5)}, ${f1(s.lon, 5)}</td></tr>`).join("")}<tr><th scope="row">${E(T("Edificações"))}</th><td>${(r.edificacoes || []).map(e => E(e.nome)).join(", ")}</td></tr>
  <tr><th scope="row">${E(T("Pavimentos"))}</th><td>${(r.pavimentos || []).map(p => E(p.nome)).join(", ")}</td></tr>${Object.entries(r.elementos_por_tipo || {}).map(([k, v]) => `<tr><th scope="row">${E(k)}</th><td>${v}</td></tr>`).join("")}
  ${r.caixa ? `<tr><th scope="row">${E(T("Tamanho"))}</th><td>${r.caixa.max.map((x, i) => f1(x - r.caixa.min[i], 1)).join(" × ")} ${E(r.caixa.unidade)}</td></tr>` : ""}</tbody></table></div>`; }
async function baixarIfc() { const L = lugar(), els = elementosBim(), S = planejador();
  const d = { projeto: { id: (S && S.meta && S.meta.criado) || "projeto", nome: (S && S.meta && S.meta.nome) || "Projeto Physis" }, site: { nome: "Terreno", lat: L.lat, lon: L.lon }, elementos: els };
  const fp = premissa(PREMISSA_FP); if (fp != null) d.premissas = { [PREMISSA_FP]: fp };
  if (!emHub()) { if (!window.PhysisIFC) return "Sem servidor e sem o escritor de IFC do navegador.";   /* sem servidor: o mesmo escritor do ifc.py, aqui */
    const txt = window.PhysisIFC.escrever(d), b = new Blob([txt], { type: "application/x-step" }), a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "physis-modelo.ifc";
    document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000); return "IFC gerado no navegador (sem servidor)."; }
  const r = await fetch("api/mapeamento/ifc", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(d) });
  if (!r.ok) { const j = await r.json().catch(() => ({})); return j.erro || "Não foi possível gerar o IFC."; }
  const b = await r.blob(), a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "physis-modelo.ifc"; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  return "IFC gerado."; }

/* ════════ Parte: método e licenças ════════ */
function parteMetodo() { return `<section class="cartao" aria-labelledby="h-mp-met"><h2 id="h-mp-met">${E(T("Como o Mapeamento calcula"))}</h2><ul>
  <li>${E(T("Contexto do lugar: o servidor junta o Início, o lote do Planejador, as camadas instaladas e os arquivos do cliente; cada campo diz de onde veio. Camada que falta aparece como camada não instalada."))}</li>
  <li>${E(T("Sol nas superfícies: a mesma conta da aba Solar (Liu e Jordan, fração difusa de Erbs) mais a sombra do horizonte, calculada por marcha de raio no terreno e nas caixas dos prédios, em 36 direções."))}</li>
  <li>${E(T("Curva do dia: a irradiação do dia distribuída hora a hora (Collares-Pereira e Rabl para a global, Liu e Jordan para a difusa) e reescalada para fechar com o total do mês da aba Solar; potência CA com a temperatura da célula e as perdas da aba Solar."))}</li>
  <li>${E(T("Sombra entre fileiras: a sombra da fileira da frente no solstício de inverno, nas horas críticas (premissas a conferir), comparada com o vão entre as fileiras."))}</li>
  <li>${E(T("BIM: IFC4 aberto, com fator de potência, potência ativa, reativa e aparente em todo equipamento elétrico."))}</li></ul>
  <p class="t2 pq">${E(T("Licenças e fontes estão em docs/MAPEAMENTO.md. Pré-projeto: conferir com o projetista."))}</p></section>`; }

/* ════════ Planta solar dentro da aba Energia solar (pedido de 15/11/2026: "planta solar deve estar na mesma aba de
   energia solar"). A aba Solar chama PhysisMapeamento.telaPlantaSolar(); o Mapeamento só aponta para lá. ════════ */
function telaPlantaSolar() { let corpo;
  try { corpo = partePlanta(); } catch (e) { corpo = faixa("al", "Erro nesta parte.", String(e && e.message || e)); }
  const dev = window.MAPEAMENTO_PRONTO === true ? "" : `<p><span class="selo at">${E(T("Em desenvolvimento"))}</span> <span class="t2 pq">${E(T("Planta solar em construção: confira com a equipe Physis antes de usar num projeto."))}</span></p>`;
  return `<section aria-labelledby="h-so-planta"><h2 id="h-so-planta">${E(T("Planta solar (BIM)"))}</h2>${dev}${typeof window.avisoLocalCep === "function" ? window.avisoLocalCep() : ""}<p class="t2 apoio">${E(T("Arranjo das placas no telhado ou no solo, carta solar, curva do dia, strings e fator de potência, com o sol de cada superfície do Mapeamento. Ao enviar, o dimensionamento desta aba passa a usar a planta: um número só de geração."))}</p><div id="mp-corpo">${corpo}</div></section>`; }
function apontarSolar() { return `<div class="faixa in" role="note"><strong>${E(T("A planta solar fica na aba Energia solar."))}</strong> <span>${E(T("O Sol nas superfícies continua aqui: é o contexto que a Solar e o AVAC leem."))}</span> <button type="button" data-mp-acao="ir-solar">${E(T("Abrir a planta solar"))}</button></div>`; }

/* ════════ Tela ════════ */
function telaMapeamentoModulo(telaBases) { const st = estado(), SUBS = [["contexto", "Contexto do lugar"], ["camadas", "Camadas"], ["arquivos", "Arquivos do cliente"], ["sol", "Sol nas superfícies"], ["planta", "Planta solar (BIM)"], ["bim", "BIM (IFC)"], ["bases", "Bases abertas"], ["metodo", "Método e licenças"]];
  const sub = SUBS.some(s => s[0] === st.sub) ? st.sub : "contexto";
  const chips = `<div class="chips" role="group" aria-label="${E(T("Partes do Mapeamento"))}">${SUBS.map(([k, n]) => `<button type="button" id="mp-sub-${k}" data-mp-sub="${k}" aria-pressed="${k === sub}">${E(T(n))}</button>`).join("")}</div>`;
  const dev = window.MAPEAMENTO_PRONTO === true ? "" : `<p><span class="selo at">${E(T("Em desenvolvimento"))}</span> <span class="t2 pq">${E(T("Módulo em construção, só na instalação de pesquisa: confira tudo antes de entregar."))}</span></p>`;
  let corpo;
  try { corpo = sub === "camadas" ? parteCamadas() : sub === "arquivos" ? parteArquivos() : sub === "sol" ? parteSol() : sub === "planta" ? apontarSolar() : sub === "bim" ? parteBim() : sub === "metodo" ? parteMetodo()
    : sub === "bases" ? (typeof telaBases === "function" ? String(telaBases()).replace(/<h1\b[\s\S]*?<\/h1>/, "") : `<p class="t2">${E(T("As bases abertas aparecem na plataforma."))}</p>`) : parteContexto(); }
  catch (e) { corpo = faixa("al", "Erro nesta parte.", String(e && e.message || e)); }
  return `<h1>${E(T("Mapeamento"))}</h1><p class="t2 apoio">${E(T("O contexto do lugar que os outros módulos leem: camadas abertas, arquivos do cliente, sol em cada superfície, a planta solar e o modelo BIM aberto."))}</p>${dev}${chips}<div id="mp-corpo">${corpo}</div>`; }

/* ════════ Eventos (atributos data-mp-…; um ouvinte só, protegido) ════════ */
function refocar(id) { const x = pega(id); if (x) x.focus(); }
async function enviarArquivo(inp) { const st = estado(), f = inp.files && inp.files[0]; if (!f) return; const tipo = inp.dataset.mpArquivo;
  st[tipo === "ifc" ? "ifcMsg" : "upMsg"] = "Enviando…"; redesenhar();
  if (!emHub()) {   /* sem servidor: lido aqui; o arquivo do cliente fica neste navegador e vai ao servidor quando ele existir */
    try { const b = await f.arrayBuffer();
      if (tipo === "ifc") { if (!window.PhysisIFC) throw new Error("leitor de IFC indisponível"); st.ifcLido = window.PhysisIFC.ler(new TextDecoder().decode(b)); st.ifcMsg = "Lido no navegador (sem servidor)."; }
      else { const r = await lerArquivoNavegador(f.name, b), ls = (lerLS("physis-mapeamento-arquivos") || []).filter(x => x.nome !== r.nome);
        const leve = JSON.stringify(r.geojson).length <= 1500000 ? r : Object.assign({}, r, { geojson: null, nota: "grande demais para guardar neste navegador" });
        ls.push(Object.assign(leve, { lido_em: new Date().toISOString(), navegador: true })); gravarLS("physis-mapeamento-arquivos", ls.slice(-20));
        st.upMsg = "Arquivo lido no navegador (sem servidor): " + r.feicoes + " feições. Vai para o servidor quando ele existir."; } }
    catch (e) { st[tipo === "ifc" ? "ifcMsg" : "upMsg"] = String(e && e.message || e); }
    redesenhar(); refocar(tipo === "ifc" ? "mp-ifc" : "mp-arquivo"); return; }
  try { const b = await f.arrayBuffer(), url = tipo === "ifc" ? "api/mapeamento/ifc/ler" : "api/mapeamento/upload";
    const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/octet-stream", "X-Physis-Nome": encodeURIComponent(f.name) }, body: b }), j = await r.json().catch(() => ({}));
    if (tipo === "ifc") { st.ifcLido = j.ok ? j.resumo : null; st.ifcMsg = j.ok ? "" : (j.erro || "IFC ilegível."); }
    else { st.upMsg = j.ok ? (j.repetido ? "Este arquivo já estava guardado." : "Arquivo guardado.") + (j.nota_crs ? " " + j.nota_crs : "") : (j.erro || "Arquivo recusado."); st.ups = null; st.ctx = null; } }
  catch (e) { st[tipo === "ifc" ? "ifcMsg" : "upMsg"] = "Não foi possível enviar agora."; }
  redesenhar(); refocar(tipo === "ifc" ? "mp-ifc" : "mp-arquivo"); }
if (typeof document !== "undefined" && !window.__mpEventos) { window.__mpEventos = true;
  document.addEventListener("change", ev => { const t = ev.target; if (!t || !t.dataset) return;
    if (t.dataset.mpArquivo) { enviarArquivo(t); return; }
    if (t.dataset.mpK == null) return; const st = estado(); st.cfg = Object.assign({}, st.cfg, { [t.dataset.mpK]: t.value }); guardarCfg(st.cfg); st.sup = null; const id = t.id; redesenhar(); refocar(id); });
  document.addEventListener("click", async ev => { const b = ev.target && ev.target.closest ? ev.target.closest("button") : null; if (!b || !b.dataset) return; const st = estado();
    if (b.dataset.mpSub) { st.sub = b.dataset.mpSub; redesenhar(); refocar("mp-sub-" + b.dataset.mpSub); return; }
    const a = b.dataset.mpAcao; if (!a) return;
    if (a === "inicio") { if (typeof irPara === "function") irPara("inicio"); return; }
    if (a === "ir-solar") { if (typeof ui !== "undefined" && ui) ui.solSub = "planta"; if (typeof irPara === "function") irPara("solar"); return; }
    if (a === "ctx") { st.ctx = null; buscarContexto(true); redesenhar(); return; }
    if (a === "enviar-incidencia") st.incMsg = enviarIncidencia();
    if (a === "enviar-planta") st.plMsg = enviarPlanta();
    if (a === "ifc") { st.ifcMsg = "Gerando…"; redesenhar(); try { st.ifcMsg = await baixarIfc(); } catch (e) { st.ifcMsg = "Não foi possível gerar o IFC agora."; } }
    const id = b.id; redesenhar(); if (id) refocar(id); }); }

/* ════════ Inglês (o integrador junta ao I18N da plataforma) ════════ */
window.MAPEAMENTO_I18N = {
  "calculado no navegador (sem servidor)": "calculated in the browser (no server)", "Com o servidor da instalação, o resultado usa as camadas instaladas e pode mudar.": "With the installation's server, the result uses the installed layers and may change.",
  "disponível com o servidor": "available with the server", "estimativa no navegador": "browser estimate", "Camadas que dependem do servidor": "Layers that depend on the server",
  "Relevo, rios, uso do solo, solos, CAR, risco, rede elétrica, prédios, clima e vento vêm das bases instaladas no servidor da instalação. Nenhum valor é inventado no lugar delas.": "Relief, rivers, land use, soils, CAR, risk, power grid, buildings, climate and wind come from the bases installed on the installation's server. No value is invented in their place.",
  "Abrir arquivo do cliente": "Open a client file", "Arquivos neste navegador": "Files in this browser", "Lidos no navegador (sem servidor)": "Read in the browser (no server)", "Tipos": "Types",
  "GeoJSON, KML/KMZ ou Shapefile (.zip com .shp, .dbf e .prj), em WGS 84 ou SIRGAS 2000 geográfico. Sem servidor, o arquivo é lido aqui e guardado só neste navegador; vai para o servidor quando ele existir.": "GeoJSON, KML/KMZ or Shapefile (.zip with .shp, .dbf and .prj), in WGS 84 or geographic SIRGAS 2000. Without a server, the file is read here and kept only in this browser; it goes to the server when there is one.",
  "Lido no navegador (sem servidor).": "Read in the browser (no server).", "IFC gerado no navegador (sem servidor).": "IFC generated in the browser (no server).", "CEP": "Postal code",
  "Nenhuma superfície: desenhe o lote ou as edificações com telhado no Planejador, ou digite abaixo uma área no solo ou um telhado.": "No surface: draw the plot or buildings with roofs in the Planner, or type a ground area or a roof below.",
  "Área no solo (retângulo): largura × comprimento": "Ground area (rectangle): width × length", "Telhado digitado (sem o Planejador)": "Typed roof (without the Planner)",
  "Telhado digitado": "Typed roof", "Largura do telhado (m)": "Roof width (m)", "Comprimento da água (m)": "Roof slope length (m)", "Inclinação do telhado (°)": "Roof pitch (°)",
  "Para onde a água aponta (°, 0 = norte)": "Where the roof faces (°, 0 = north)", "Altura do telhado (m)": "Roof height (m)",
  "Planta solar em construção: confira com a equipe Physis antes de usar num projeto.": "Solar layout under construction: check with the Physis team before using it in a project.",
  "Arranjo das placas no telhado ou no solo, carta solar, curva do dia, strings e fator de potência, com o sol de cada superfície do Mapeamento. Ao enviar, o dimensionamento desta aba passa a usar a planta: um número só de geração.": "Panel layout on the roof or on the ground, sun-path chart, daily curve, strings and power factor, with the sun on each surface from Mapping. Once sent, this tab's sizing uses the layout: a single generation figure.",
  "A planta solar fica na aba Energia solar.": "The solar layout is in the Solar energy tab.",
  "O Sol nas superfícies continua aqui: é o contexto que a Solar e o AVAC leem.": "Sun on surfaces stays here: it is the context that Solar and HVAC read.",
  "Abrir a planta solar": "Open the solar layout",
  "Mapeamento": "Mapping",
  "Em desenvolvimento": "In development",
  "Módulo em construção, só na instalação de pesquisa: confira tudo antes de entregar.": "Module under construction, research installation only: check everything before delivery.",
  "O contexto do lugar que os outros módulos leem: camadas abertas, arquivos do cliente, sol em cada superfície, a planta solar e o modelo BIM aberto.": "The site context the other modules read: open layers, client files, sun on each surface, the solar plant and the open BIM model.",
  "Partes do Mapeamento": "Mapping sections",
  "Contexto do lugar": "Site context",
  "Camadas": "Layers",
  "Arquivos do cliente": "Client files",
  "Sol nas superfícies": "Sun on surfaces",
  "Planta solar (BIM)": "Solar plant (BIM)",
  "BIM (IFC)": "BIM (IFC)",
  "Bases abertas": "Open data",
  "Método e licenças": "Method and licences",
  "Falta a localização.": "Location missing.",
  "O Mapeamento depende do Início: preencha os dados obrigatórios do cliente (localização) no Início ou desenhe o lote no Planejador.": "Mapping depends on Home: fill in the client's mandatory data (location) on Home or draw the plot in the Planner.",
  "Ir para o Início": "Go to Home",
  "Lugar": "Site",
  "fonte": "source",
  "Lote do Planejador encontrado.": "Planner plot found.",
  "Sem lote no Planejador: a área vem do Início.": "No plot in the Planner: the area comes from Home.",
  "Sem servidor.": "No server.",
  "O contexto completo é montado pelo servidor da instalação com as camadas instaladas. Aberta sem ele, esta parte mostra só o lugar.": "The full context is built by the installation server from the installed layers. Opened without it, this section shows only the site.",
  "Montando o contexto do lugar…": "Building the site context…",
  "Contexto indisponível agora.": "Context unavailable now.",
  "O servidor não respondeu.": "The server did not respond.",
  "camada não instalada": "layer not installed",
  "sem dado": "no data",
  "Camadas que faltam neste servidor": "Layers missing on this server",
  "A instalação das bases nacionais no servidor está na Fase 2 (docs/MAPEAMENTO.md). Nenhum valor é inventado no lugar de uma camada que falta.": "Installing the national datasets on the server is Phase 2 (docs/MAPEAMENTO.md). No value is invented in place of a missing layer.",
  "Cada campo com a fonte": "Each field with its source",
  "Campo": "Field",
  "Valor": "Value",
  "Fonte": "Source",
  "Integridade": "Integrity",
  "Atualizar o contexto": "Refresh the context",
  "Coordenadas": "Coordinates",
  "Município": "Municipality",
  "Área do lote": "Plot area",
  "Declividade": "Slope",
  "Altitude": "Elevation",
  "Rios e nascentes": "Rivers and springs",
  "Uso do solo": "Land use",
  "Solo": "Soil",
  "Limites": "Boundaries",
  "CAR": "CAR",
  "Áreas de risco": "Risk areas",
  "Rede elétrica": "Power grid",
  "Edificações e vias": "Buildings and roads",
  "Clima (EPW)": "Climate (EPW)",
  "Irradiação solar": "Solar irradiation",
  "Vento": "Wind",
  "O catálogo mostra o que está instalado no servidor da instalação.": "The catalogue shows what is installed on the installation server.",
  "Carregando o catálogo…": "Loading the catalogue…",
  "Catálogo de camadas": "Layer catalogue",
  "Bases abertas que o Mapeamento usa; fonte e licença a conferir": "Open datasets Mapping uses; source and licence to be checked",
  "Camada": "Layer",
  "Para quê": "Purpose",
  "Quem usa": "Used by",
  "Fonte e licença": "Source and licence",
  "Formato e lugar no servidor": "Format and server location",
  "Situação": "Status",
  "instalada": "installed",
  "[CONFERIR]: o nome do produto, a versão e a licença de cada base são conferidos na página oficial antes de instalar. Nenhum dado vem copiado no sistema.": "[CHECK]: each dataset's product name, version and licence are checked on the official page before installing. No data is copied into the system.",
  "Os arquivos do cliente ficam guardados no servidor da instalação, com o resumo SHA-256.": "Client files are stored on the installation server with their SHA-256 digest.",
  "Enviar arquivo do cliente": "Upload a client file",
  "GeoJSON, KML/KMZ ou Shapefile (.zip com .shp, .dbf e .prj). Coordenadas em WGS 84 (EPSG:4326) ou SIRGAS 2000 geográfico (EPSG:4674). Até 20 MB.": "GeoJSON, KML/KMZ or Shapefile (.zip with .shp, .dbf and .prj). Coordinates in WGS 84 (EPSG:4326) or geographic SIRGAS 2000 (EPSG:4674). Up to 20 MB.",
  "Arquivo": "File",
  "Arquivos guardados": "Stored files",
  "Arquivos do cliente com o resumo de integridade": "Client files with the integrity digest",
  "Nome": "Name",
  "Formato": "Format",
  "Sistema de coordenadas": "Coordinate system",
  "Feições": "Features",
  "Nenhum arquivo ainda.": "No files yet.",
  "Enviando…": "Uploading…",
  "Arquivo guardado.": "File stored.",
  "Este arquivo já estava guardado.": "This file was already stored.",
  "Arquivo recusado.": "File refused.",
  "Não foi possível enviar agora.": "Could not upload now.",
  "Altura por pavimento (m)": "Height per storey (m)",
  "conferir no projeto": "check in the design",
  "Usada só quando o Planejador não traz a altura da edificação. Vazio: prédios sem altura não fazem sombra.": "Used only when the Planner has no building height. Blank: buildings without height cast no shadow.",
  "Ainda não dá para calcular.": "Cannot calculate yet.",
  "Falta a localização (Início).": "Location missing (Home).",
  "Sem a irradiação do lugar (a mesma da aba Solar): abra com o servidor ou espere a base carregar.": "No site irradiation (the same as the Solar tab): open with the server or wait for the data to load.",
  "Atenção.": "Attention.",
  "Há edificações sem altura: informe a altura por pavimento para elas entrarem na sombra.": "Some buildings have no height: enter the height per storey so they cast shadows.",
  "Irradiação": "Irradiation",
  "Sombra do terreno e dos prédios por marcha de raio em 36 direções.": "Terrain and building shading by ray marching in 36 directions.",
  "Sem lote desenhado no Planejador: só os telhados e as fachadas.": "No plot drawn in the Planner: roofs and facades only.",
  "Sol no terreno": "Sun on the terrain",
  "a": "to",
  "ano": "year",
  "Ver o mapa de calor": "See the heat map",
  "Telhados": "Roofs",
  "Fachadas (para o AVAC)": "Facades (for HVAC)",
  "Superfície": "Surface",
  "Inclinação": "Tilt",
  "Orientação": "Orientation",
  "Sombra": "Shading",
  "Enviar para Solar e AVAC": "Send to Solar and HVAC",
  "Enviado: a aba Solar e o AVAC leem physis-calc-incidencia.": "Sent: the Solar tab and HVAC read physis-calc-incidencia.",
  "A aba Solar não está carregada: a planta usa as contas dela (módulos, inversores, perdas e strings).": "The Solar tab is not loaded: the plant uses its calculations (modules, inverters, losses and strings).",
  "Nenhuma superfície: desenhe o lote ou as edificações com telhado no Planejador, ou um retângulo no solo abaixo.": "No surface: draw the plot or buildings with roofs in the Planner, or a ground rectangle below.",
  "Ainda não dá para montar a planta.": "Cannot lay out the plant yet.",
  "Onde vai a planta": "Where the plant goes",
  "Área no solo: lote inteiro": "Ground area: whole plot",
  "Área no solo: retângulo desenhado": "Ground area: drawn rectangle",
  "Desenhar um retângulo no solo (metros do Planejador: x leste, y norte)": "Draw a ground rectangle (Planner metres: x east, y north)",
  "Centro x (m)": "Centre x (m)",
  "Centro y (m)": "Centre y (m)",
  "Largura (m)": "Width (m)",
  "Profundidade (m)": "Depth (m)",
  "Giro (°)": "Rotation (°)",
  "Módulo (base de equipamentos)": "Module (equipment base)",
  "Comprimento do módulo (m)": "Module length (m)",
  "Largura do módulo (m)": "Module width (m)",
  "da folha de dados": "from the datasheet",
  "Posição do módulo": "Module orientation",
  "Retrato (em pé)": "Portrait",
  "Paisagem (deitado)": "Landscape",
  "Módulos por mesa (na inclinação)": "Modules per table (up the tilt)",
  "Inclinação das placas (°)": "Panel tilt (°)",
  "Azimute das placas (°, 0 = norte)": "Panel azimuth (°, 0 = north)",
  "Passo entre fileiras (m)": "Row pitch (m)",
  "vazio: o mínimo sem sombra": "blank: the minimum without shading",
  "Afastamento das bordas (m)": "Edge setback (m)",
  "Folga entre módulos (m)": "Gap between modules (m)",
  "premissa a criar [CONFERIR]": "assumption to be created [CHECK]",
  "Hora crítica, início (hora solar)": "Critical time, start (solar time)",
  "Hora crítica, fim (hora solar)": "Critical time, end (solar time)",
  "Falta informar:": "Still missing:",
  "Módulos": "Modules",
  "Potência": "Power",
  "Área dos módulos": "Module area",
  "Passo entre fileiras": "Row pitch",
  "Sombra entre fileiras.": "Inter-row shading.",
  "Sem sombra entre fileiras": "No inter-row shading",
  "Arranjo das placas na superfície": "Panel layout on the surface",
  "módulos": "modules",
  "Arranjo das placas": "Panel layout",
  "Carta solar e horizonte": "Sun-path chart and horizon",
  "Carta solar do lugar com o horizonte": "Site sun-path chart with the horizon",
  "Azul: solstício de junho; verde: equinócios; laranja: solstício de dezembro. Areia: horizonte (terreno e prédios vizinhos). Anéis: 0°, 30° e 60° de altura.": "Blue: June solstice; green: equinoxes; orange: December solstice. Sand: horizon (terrain and neighbouring buildings). Rings: 0°, 30° and 60° altitude.",
  "O dia desde o nascer do sol": "The day from sunrise",
  "Dia da curva": "Day of the curve",
  "Nascer do sol": "Sunrise",
  "pôr do sol": "sunset",
  "hora solar": "solar time",
  "no plano das placas": "on the panel plane",
  "temperatura de 25 °C (sem a base de temperatura)": "25 °C temperature (no temperature data)",
  "Irradiância no plano das placas, do nascer ao pôr do sol": "Irradiance on the panel plane, sunrise to sunset",
  "Irradiância (W/m²)": "Irradiance (W/m²)",
  "Potência CA estimada": "Estimated AC power",
  "Potência CA (kW)": "AC power (kW)",
  "Ver os números da curva": "See the curve numbers",
  "Hora a hora": "Hour by hour",
  "Hora": "Time",
  "Sem dados para o gráfico.": "No data for the chart.",
  "Energia no mês e no ano": "Monthly and annual energy",
  "Energia mês a mês (contas da aba Solar)": "Energy month by month (Solar tab calculations)",
  "Mês": "Month",
  "dia no plano": "day on the plane",
  "Ano": "Year",
  "sombra do horizonte": "horizon shading",
  "Elétrica": "Electrical",
  "Inversor (base de equipamentos)": "Inverter (equipment base)",
  "Temperatura mínima do lugar (°C)": "Site minimum temperature (°C)",
  "Temperatura máxima do lugar (°C)": "Site maximum temperature (°C)",
  "a da aba Solar": "the Solar tab's",
  "Fator de potência": "Power factor",
  "Strings": "Strings",
  "módulos em série": "modules in series",
  "faixa que cabe no MPPT": "range that fits the MPPT",
  "tensão de circuito aberto no frio": "cold open-circuit voltage",
  "Potência na saída CA do inversor": "Power at the inverter AC output",
  "Enviar para a aba Solar e para o BIM": "Send to the Solar tab and to BIM",
  "Complete a planta antes de enviar.": "Complete the plant before sending.",
  "Enviado: a aba Solar lê physis-calc-planta-solar e o BIM recebeu o arranjo e o inversor.": "Sent: the Solar tab reads physis-calc-planta-solar and BIM received the array and the inverter.",
  "Complete a planta antes de pedir o suporte.": "Complete the plant before requesting the bracket.",
  "Modelo BIM aberto (IFC4)": "Open BIM model (IFC4)",
  "Sistemas que os módulos mandaram": "Systems the modules sent",
  "Elemento": "Element",
  "Tipo": "Type",
  "Origem": "Origin",
  "Nenhum sistema enviado ainda: a planta solar, a cisterna, as calhas, o AVAC, o quadro, o biodigestor, as turbinas e o viveiro aparecem aqui quando os módulos mandarem.": "No systems sent yet: the solar plant, cistern, gutters, HVAC, panel board, biodigester, turbines and nursery appear here when the modules send them.",
  "Baixar o IFC": "Download the IFC",
  "Gerando…": "Generating…",
  "IFC gerado.": "IFC generated.",
  "Não foi possível gerar o IFC.": "Could not generate the IFC.",
  "Não foi possível gerar o IFC agora.": "Could not generate the IFC now.",
  "Fator de potência, potência ativa, reativa e aparente vão em todo equipamento elétrico (premissa eletrica.fator_potencia_padrao).": "Power factor and active, reactive and apparent power go on every electrical item (assumption eletrica.fator_potencia_padrao).",
  "Abrir um IFC": "Open an IFC",
  "Leitura básica: terreno, edificações, pavimentos, quantos elementos de cada tipo e o tamanho. A geometria completa fica para um visualizador IFC aberto (Fase 2).": "Basic reading: site, buildings, storeys, element counts by type and size. Full geometry is for an open IFC viewer (Phase 2).",
  "Arquivo IFC": "IFC file",
  "IFC ilegível.": "Unreadable IFC.",
  "Resumo do IFC": "IFC summary",
  "Esquema": "Schema",
  "Projeto": "Project",
  "Terreno": "Site",
  "Edificações": "Buildings",
  "Pavimentos": "Storeys",
  "Tamanho": "Size",
  "As bases abertas aparecem na plataforma.": "Open data appears in the platform.",
  "Erro nesta parte.": "Error in this section.",
  "Como o Mapeamento calcula": "How Mapping calculates",
  "Contexto do lugar: o servidor junta o Início, o lote do Planejador, as camadas instaladas e os arquivos do cliente; cada campo diz de onde veio. Camada que falta aparece como camada não instalada.": "Site context: the server combines Home, the Planner plot, the installed layers and the client files; each field says where it came from. A missing layer shows as layer not installed.",
  "Sol nas superfícies: a mesma conta da aba Solar (Liu e Jordan, fração difusa de Erbs) mais a sombra do horizonte, calculada por marcha de raio no terreno e nas caixas dos prédios, em 36 direções.": "Sun on surfaces: the same calculation as the Solar tab (Liu and Jordan, Erbs diffuse fraction) plus horizon shading, by ray marching over the terrain and building boxes in 36 directions.",
  "Curva do dia: a irradiação do dia distribuída hora a hora (Collares-Pereira e Rabl para a global, Liu e Jordan para a difusa) e reescalada para fechar com o total do mês da aba Solar; potência CA com a temperatura da célula e as perdas da aba Solar.": "Daily curve: the day's irradiation spread hour by hour (Collares-Pereira and Rabl for global, Liu and Jordan for diffuse) and rescaled to match the Solar tab's monthly total; AC power with the Solar tab's cell temperature and losses.",
  "Sombra entre fileiras: a sombra da fileira da frente no solstício de inverno, nas horas críticas (premissas a conferir), comparada com o vão entre as fileiras.": "Inter-row shading: the front row's shadow at the winter solstice, at the critical times (assumptions to be checked), compared with the gap between rows.",
  "BIM: IFC4 aberto, com fator de potência, potência ativa, reativa e aparente em todo equipamento elétrico.": "BIM: open IFC4, with power factor and active, reactive and apparent power on every electrical item.",
  "Licenças e fontes estão em docs/MAPEAMENTO.md. Pré-projeto: conferir com o projetista.": "Licences and sources are in docs/MAPEAMENTO.md. Preliminary design: check with the designer."
};
window.MAPEAMENTO_I18N_RX = [
  ["^No solstício de inverno, entre ([\\d.,]+) h e ([\\d.,]+) h \\(hora solar\\), a sombra chega a ([\\d.,]+) m e o vão é de ([\\d.,]+) m: aumente o passo para ([\\d.,]+) m\\.$", "At the winter solstice, between $1 h and $2 h (solar time), the shadow reaches $3 m and the gap is $4 m: increase the pitch to $5 m."],
  ["^no solstício de inverno, entre ([\\d.,]+) h e ([\\d.,]+) h \\(hora solar\\)\\.$", "at the winter solstice, between $1 h and $2 h (solar time)."],
  ["^([\\d.,]+) mesas$", "$1 tables"],
  ["^m² \\(ocupada ([\\d.,]+) m²\\)$", "m² (footprint $1 m²)"],
  ["^(.+) · água (\\d+)$", "$1 · roof plane $2"],
  ["^(.+) · fachada (\\d+)$", "$1 · facade $2"],
  ["^([a-z]{3}) \\(dia médio\\)$", "$1 (mean day)"],
  ["^Vazio: (.+)$", "Blank: $1"]
];

window.MAPEAMENTO = { DIA_REP, DIA_21, PASSOS_DIA, SETORES, PREMISSA_FP, PREM, incidenciaSuperficie, horizonte, zGrade, planosTelhado, fachadas, celulasTerreno, incidencia,
  solEm, nascerPor, cartaSolar, curvaDiaria, potenciaCA, sombraEntreFileiras, arranjo, potencias, gradeDoLote, enviarParaBim, elementosBim, dimensoesModulo, geometriaParaSimulacao, cartaSVG, calcularPlanta, calcularSuperficies };
window.telaMapeamentoModulo = telaMapeamentoModulo;
window.PhysisMapeamento = { telaPlantaSolar };   /* a aba Energia solar mostra a planta (sub-aba "Planta solar (BIM)") */   /* global: a plataforma chama telaMapeamentoModulo(telaMapeamento) na hora de desenhar */
})();
