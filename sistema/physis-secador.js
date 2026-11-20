/* physis-secador.js — aba Secador solar da plataforma (produto P23 da loja: frutas, ervas, cogumelos e café).
   Contrato com a plataforma: define telaSecador() (HTML da aba inteira, com o único título h1),
   window.SECADOR = { contas puras, testáveis } e window.SECADOR_I18N (português → inglês, para juntar ao I18N) com
   window.SECADOR_I18N_RX (frases com números); os dois vão copiados em sistema/physis-i18n-modulos.json.
   Espelho de physis-hub/physis_hub/secador.py (mesmas premissas, fórmulas e constantes; teste em tests/test_secador.py).
   Dados: no modo hub, os nós TIPO:SEC de GET api/painel (ui.dados.nos) e as séries de GET api/serie; nos outros
   modos, um secador simulado (dados de exemplo, marcados como tal). Globais usadas se existirem: esc, n2, numBr, el,
   ui, desenhar, calcLer, calcGravar, enviarComando, gisLugar, carregarGis. Estado: calcLer("secador") (lotes e
   dimensionamento); parte aberta em ui.secSub. Premissas de produto marcadas "verificar" são de literatura geral. */
(function () {
"use strict";

/* ════════ Premissas por produto (as mesmas do secador.py; todas "verificar") ════════ */
const PRODUTOS = {
  cafe: { nome:"Café (cereja ou pergaminho)", t_ideal:[35, 40], t_max: 45, u0: 60, alvo: 11.5, ue: 10, k: 0.024,
    fonte:"Embrapa Café / Consórcio Pesquisa Café: massa até 40 °C para qualidade, 45 °C no máximo; sementes até 35 °C; armazenar com 11 a 12 % b.u. — verificar" },
  ervas: { nome:"Ervas e folhas (medicinais, aromáticas)", t_ideal:[30, 35], t_max: 40, u0: 80, alvo: 10, ue: 8, k: 0.06,
    fonte:"literatura de plantas medicinais (óleos essenciais se perdem acima de 35 a 40 °C) — verificar" },
  frutas: { nome:"Frutas em fatias", t_ideal:[50, 60], t_max: 65, u0: 85, alvo: 18, ue: 15, k: 0.03,
    fonte:"manuais de frutas desidratadas: 55 a 65 °C; umidade final de 15 a 20 % b.u. — verificar" },
  cogumelos: { nome:"Cogumelos", t_ideal:[40, 50], t_max: 55, u0: 90, alvo: 10, ue: 8, k: 0.05,
    fonte:"literatura de secagem de cogumelos: 40 a 55 °C; umidade final perto de 10 % b.u. — verificar" },
  outro: { nome:"Outro produto", t_ideal:[40, 55], t_max: 60, u0: 70, alvo: 12, ue: 10, k: 0.03,
    fonte:"valores genéricos — trocar pelos do produto" }
};
const UMIDADE_INTERNA_ALTA = 80;      /* % UR dentro do secador sem ventilação: atenção (verificar) */
const CHUVA_PREVISTA_MM = 1.0, CHUVA_PREVISTA_PROB = 60;
const CALOR_LATENTE_MJ_KG = 2.45, CP_AR_KJ_KG_K = 1.006, RHO_AR = 1.15, MJ_POR_KWH = 3.6, PCI_LENHA_MJ_KG = 13.0;
const GWP_CH4 = 28, GWP_N2O = 265, LENHA_CH4_KG_TJ = 300, LENHA_N2O_KG_TJ = 4, LENHA_CO2_KG_TJ = 112000;
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const produto = k => PRODUTOS[String(k || "").toLowerCase()] || PRODUTOS.outro;

/* ════════ Balanço de massa ════════ */
const materiaSeca = (peso, u) => peso * (1 - u / 100);
const pesoNaUmidade = (peso0, u0, u) => materiaSeca(peso0, u0) / (1 - u / 100);
const aguaARemover = (peso0, u0, alvo) => alvo >= u0 ? 0 : peso0 * (u0 - alvo) / (100 - alvo);
const umidadeDoPeso = (peso0, u0, peso) => !(peso > 0) ? null : 100 * (1 - materiaSeca(peso0, u0) / peso);
const rendimento = (peso0, pf) => peso0 > 0 ? 100 * pf / peso0 : null;

/* ════════ Modelo exponencial (Lewis): W(t) = We + (W0 − We)·e^(−k·t) ════════ */
function reta(ts, ys) { const n = ts.length, mt = ts.reduce((s, x) => s + x, 0) / n, my = ys.reduce((s, x) => s + x, 0) / n;
  let sxx = 0, sxy = 0; for (let i = 0; i < n; i++) { sxx += (ts[i] - mt) * (ts[i] - mt); sxy += (ts[i] - mt) * (ys[i] - my); }
  if (sxx <= 0) return null; const b = sxy / sxx; return [my - b * mt, b]; }
function ajusteComWe(ts, ws, we) { if (ws.some(w => w <= we)) return null; const r = reta(ts, ws.map(w => Math.log(w - we))); if (!r) return null;
  const a = r[0], k = -r[1]; let sse = 0; for (let i = 0; i < ts.length; i++) { const d = we + Math.exp(a - k * ts[i]) - ws[i]; sse += d * d; } return [sse, a, k]; }
/* serie: [[horas desde o início, kg]] → { we, w0, k, sse, n } ou null. Grade de 100 passos + 40 de seção áurea. */
function ajustar(serie) {
  const pts = (serie || []).filter(p => p && p[1] > 0 && p[0] != null && isFinite(p[0])).map(p => [+p[0], +p[1]]).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  if (pts.length < 3) return null; const ts = pts.map(p => p[0]), ws = pts.map(p => p[1]), teto = Math.min(...ws) * 0.999, passos = 100;
  let melhor = null;
  for (let i = 0; i < passos; i++) { const we = teto * i / passos, r = ajusteComWe(ts, ws, we); if (r && (!melhor || r[0] < melhor[0])) melhor = [r[0], we, i]; }
  if (!melhor) return null;
  let lo = teto * Math.max(0, melhor[2] - 1) / passos, hi = teto * Math.min(passos - 1, melhor[2] + 1) / passos;
  const phi = (Math.sqrt(5) - 1) / 2, f = we => { const r = ajusteComWe(ts, ws, we); return r ? r[0] : Infinity; };
  let x1 = hi - phi * (hi - lo), x2 = lo + phi * (hi - lo), f1 = f(x1), f2 = f(x2);
  for (let i = 0; i < 40; i++) { if (f1 <= f2) { hi = x2; x2 = x1; f2 = f1; x1 = hi - phi * (hi - lo); f1 = f(x1); } else { lo = x1; x1 = x2; f1 = f2; x2 = lo + phi * (hi - lo); f2 = f(x2); } }
  let we = (lo + hi) / 2, r = ajusteComWe(ts, ws, we);
  if (!r || melhor[0] < r[0]) { we = melhor[1]; r = ajusteComWe(ts, ws, we); }
  if (!(r[2] > 0)) return null;
  return { we, w0: we + Math.exp(r[1]), k: r[2], sse: r[0], n: pts.length }; }
const pesoPrevisto = (m, t) => m.we + (m.w0 - m.we) * Math.exp(-m.k * t);
function horasAte(m, alvo) { if (alvo <= m.we || !(m.k > 0)) return null; if (alvo >= m.w0) return 0; return -Math.log((alvo - m.we) / (m.w0 - m.we)) / m.k; }
function modeloEstimado(peso0, u0, prod, k) { const p = produto(prod), we = p.ue < u0 ? pesoNaUmidade(peso0, u0, p.ue) : peso0 * 0.999;
  return { we, w0: peso0, k: k || p.k, sse: null, n: 0, estimado: true }; }
function previsaoLote(l, serie) { const peso0 = +l.peso0, u0 = +l.u0, alvo = l.alvo != null && l.alvo !== "" ? +l.alvo : produto(l.produto).alvo;
  let m = serie && serie.length ? ajustar(serie) : null; if (!m) m = modeloEstimado(peso0, u0, l.produto);
  const pa = pesoNaUmidade(peso0, u0, alvo);
  return { peso_alvo: pa, agua_kg: aguaARemover(peso0, u0, alvo), modelo: m, horas_fim: horasAte(m, pa), medido: !m.estimado }; }

/* ════════ Dimensionamento (secador de ar forçado com coletor solar) ════════ */
/* fator da rede (tCO2/MWh): o padrão da base de fatores de emissão (o mesmo do Carbono); sem ela, a premissa
   rede.fator_emissao; sem nenhuma, null (CO2 evitado elétrico não calculado). Espelho de secador.fator_rede_padrao (R9). */
function fatorRedePadrao() { const b = fatorRedeBase(); if (b != null) return b;
  try { const v = typeof PhysisCalc !== "undefined" ? +PhysisCalc.premissa("rede.fator_emissao") : NaN; return isFinite(v) && v > 0 ? v : null; } catch (e) { return null; } }
function dimensionar(p) { p = p || {}; const g = (k, d) => (p[k] == null || p[k] === "" || !isFinite(+p[k])) ? d : +p[k], avisos = [];
  /* irradiação: a do lugar ou a digitada; sem ela, "local não informado" (como secador.py) */
  const massa = g("massa", 0), u0 = g("u0", 60), alvo = g("alvo", 12), H = g("irradiacao", null), eta = g("eta_coletor", 0.40), aprov = g("aproveitamento", 0.5);
  const dias = g("dias", 5), horas = g("horas_sol", 8), dT = g("delta_t", 15);
  if (H == null) avisos.push("local não informado: sem a irradiação do lugar, a área do coletor não é calculada");
  const agua = aguaARemover(massa, u0, alvo), qEvap = agua * CALOR_LATENTE_MJ_KG, qAr = aprov > 0 ? qEvap / aprov : 0, porM2 = H != null ? H * MJ_POR_KWH * eta * dias : null;
  const area = porM2 > 0 ? qAr / porM2 : null, dw = CP_AR_KJ_KG_K * dT * aprov / (CALOR_LATENTE_MJ_KG * 1000), mAr = dw > 0 ? agua / dw : null;
  const vazao = mAr && dias * horas > 0 ? mAr / RHO_AR / (dias * horas) : null;
  const etaEl = g("eta_eletrico", 0.5), etaLe = g("eta_lenha", 0.35), lotes = g("lotes_ano", 10), fRede = g("fator_rede", fatorRedePadrao());
  if (fRede == null) avisos.push("fator da rede não informado: CO2 evitado elétrico não calculado");
  const kwhEl = etaEl > 0 ? qEvap / etaEl / MJ_POR_KWH : null, kgLenha = etaLe > 0 ? qEvap / (PCI_LENHA_MJ_KG * etaLe) : null;
  const co2El = kwhEl != null && fRede != null ? kwhEl * fRede : null;
  let co2Le = null; if (kgLenha != null) { const tj = kgLenha * PCI_LENHA_MJ_KG / 1e6; co2Le = tj * (LENHA_CH4_KG_TJ * GWP_CH4 + LENHA_N2O_KG_TJ * GWP_N2O); if (p.lenha_nao_renovavel) co2Le += tj * LENHA_CO2_KG_TJ; }
  return { agua_kg: agua, q_evap_mj: qEvap, q_ar_mj: qAr, mj_m2_lote: porM2, area_m2: area, dw_kg_kg: dw, ar_kg: mAr, vazao_m3h: vazao,
    kwh_eletrico_lote: kwhEl, kg_lenha_lote: kgLenha, kwh_eletrico_ano: kwhEl != null ? kwhEl * lotes : null, kg_lenha_ano: kgLenha != null ? kgLenha * lotes : null,
    co2_eletrico_kg_ano: co2El != null ? co2El * lotes : null, co2_lenha_kg_ano: co2Le != null ? co2Le * lotes : null, fator_rede: fRede, avisos }; }

/* ════════ Alertas (os mesmos do hub, mais a chuva da previsão da tela) ════════ */
function alertas(est, prod, chuva) { const out = [], p = produto(prod), ti = est.ti;
  if (ti != null && ti > p.t_max) out.push(["al", `Superaquecimento: ${f1(ti)} °C dentro do secador, acima de ${f1(p.t_max, 0)} °C para ${p.nome.toLowerCase()}.`]);
  if (est.ui != null && est.ui >= UMIDADE_INTERNA_ALTA && !est.vent) out.push(["at", `Umidade alta dentro do secador (${f1(est.ui, 0)} %) com o ventilador desligado.`]);
  if (chuva && est.abt !== false) { const mm = chuva.mm_6h, pr = chuva.prob_hoje;
    if ((mm != null && mm >= CHUVA_PREVISTA_MM) || (pr != null && pr >= CHUVA_PREVISTA_PROB)) out.push(["at", "Chuva prevista e o secador está aberto: feche a tampa ou recolha o produto."]); }
  if (ti == null && est.ui == null) out.push(["al", "Sensor de temperatura e umidade interna sem leitura."]);
  return out; }

/* ════════ Utilidades (com reserva quando a plataforma não as tem) ════════ */
const E = s => typeof esc === "function" ? esc(s) : String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));
const N = (v, c) => typeof n2 === "function" ? n2(v, c) : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c });
const f1 = (v, c) => v == null || !isFinite(v) ? "—" : N(v, c == null ? 1 : c);
const num = s => { if (s == null || String(s).trim() === "") return null; const v = typeof numBr === "function" ? numBr(s) : parseFloat(String(s).replace(",", ".")); return v == null || !isFinite(v) ? null : v; };
const U = () => (typeof ui !== "undefined" && ui) ? ui : (window.__secUi = window.__secUi || {});
const pega = id => typeof el === "function" ? el(id) : document.getElementById(id);
const redesenhar = () => { if (typeof desenhar === "function") desenhar(false); };
const quando = ms => { const d = new Date(ms); return d.toLocaleDateString("pt-BR", { day:"2-digit", month:"2-digit" }) + " " + d.toLocaleTimeString("pt-BR", { hour:"2-digit", minute:"2-digit" }); };
const duracao = h => h == null ? "—" : h < 48 ? f1(h, 0) + " h" : f1(h / 24, 1) + " dias";
function ler() { let o = null; if (typeof calcLer === "function") o = calcLer("secador");
  else { try { o = JSON.parse(localStorage.getItem("physis-calc-secador") || "null"); } catch (e) {} }
  o = o && typeof o === "object" ? o : {}; o.lotes = Array.isArray(o.lotes) ? o.lotes : []; o.dim = o.dim && typeof o.dim === "object" ? o.dim : {}; return o; }
function gravar(o) { if (typeof calcGravar === "function") return calcGravar("secador", o); try { localStorage.setItem("physis-calc-secador", JSON.stringify(o)); } catch (e) {} }
const emHub = () => U().modo === "hub";

/* ════════ Dados: secador simulado (demonstração) ════════ */
const DEMO_ID = 41, DEMO_PASSO_S = 1800;
function demoInicio(agora) { return Math.floor((agora - 70 * 3600) / 3600) * 3600; }
function demoPonto(s, ini) { const hd = (((s / 3600 - 3) % 24) + 24) % 24, sol = Math.max(0, Math.sin(Math.PI * (hd - 6) / 12)), nuvem = 0.5 + 0.5 * Math.sin(s / 7777);
  const irr = 900 * sol * (1 - 0.3 * nuvem), te = 19 + 9 * sol, ue = 88 - 38 * sol, tc = te + 32 * sol * (1 - 0.3 * nuvem), ti = te + 14 * sol * (1 - 0.3 * nuvem);
  const ui_ = Math.max(20, ue - 34 * sol), vent = irr > 120 ? 1 : 0, t = (s - ini) / 3600, w0 = 120, we = pesoNaUmidade(120, 60, 10);
  const peso = t < 0 ? null : we + (w0 - we) * Math.exp(-0.03 * t) + 0.15 * Math.sin(s / 977);
  return { ts: s, ti, ui: ui_, te, ue, tc, irr, vent, peso, abt: 1 }; }
function demoSerie(agora) { const ini = demoInicio(agora), out = []; for (let s = ini - 6 * 3600; s <= agora; s += DEMO_PASSO_S) out.push(demoPonto(s - s % DEMO_PASSO_S, ini)); return out; }
function demoNo(agora) { const u = U(), p = demoPonto(agora - agora % 60, demoInicio(agora)); if (u.secDemoVent != null) p.vent = u.secDemoVent;
  return Object.assign({ id: DEMO_ID, tipo: "SEC", online: true, ha_s: 20, bat: 3.95, demo: true }, p); }
function demoLote(agora) { return { id: "demo", produto: "cafe", peso0: 120, u0: 60, alvo: 11.5, inicio: demoInicio(agora) * 1000, no: DEMO_ID, pesagens: [], demo: true }; }

/* ════════ Dados: hub (nós TIPO:SEC e séries) ════════ */
function nosSec() { const d = U().dados; return (d && Array.isArray(d.nos) ? d.nos : []).filter(n => n && n.tipo === "SEC"); }
const SERIES = [["ti", "temperatura_interna", ""], ["ui", "umidade_interna", ""], ["tc", "temperatura_coletor", ""], ["te", "temperatura", "-ext"],
  ["ue", "umidade", "-ext"], ["peso", "peso_produto", ""], ["irr", "irradiancia", ""], ["vent", "estado", "-ventilador"]];
function serieHub(id) { const u = U(), lugar = (u.dados && u.dados.lugar) || "", base = `${lugar}-no${String(id).padStart(2, "0")}`, k = base;
  u.secSerie = u.secSerie || {}; const c = u.secSerie[k];
  if (c && (c.carregando || Date.now() - c.em < 60000)) return c.pontos || null;
  u.secSerie[k] = Object.assign({}, c || {}, { carregando: true, em: Date.now() });
  Promise.all(SERIES.map(([, g, suf]) => fetch(`api/serie?ativo=${encodeURIComponent(base + suf)}&grandeza=${g}`, { cache:"no-store" }).then(r => r.ok ? r.json() : []).catch(() => [])))
    .then(listas => { const porTs = new Map();
      listas.forEach((l, i) => (Array.isArray(l) ? l : []).forEach(x => { if (!x || !x.ts) return; const p = porTs.get(x.ts) || { ts: x.ts }; p[SERIES[i][0]] = x.valor; porTs.set(x.ts, p); }));
      u.secSerie[k] = { em: Date.now(), pontos: [...porTs.values()].sort((a, b) => a.ts - b.ts) }; redesenhar(); })
    .catch(() => { u.secSerie[k] = { em: Date.now(), pontos: [] }; });
  return c && c.pontos ? c.pontos : null; }

/* O que a tela usa: { nos, no (selecionado), serie, demo } */
function fonte() { const u = U(), agora = Date.now() / 1000;
  if (emHub()) { const nos = nosSec(); if (nos.length) { const no = nos.find(n => n.id === u.secNo) || nos[0]; return { nos, no, serie: serieHub(no.id) || [], demo: false }; }
    return { nos: [], no: demoNo(agora), serie: demoSerie(agora), demo: true, semNo: true }; }
  return { nos: [], no: demoNo(agora), serie: demoSerie(agora), demo: true }; }
function chuvaDaTela() { const c = U().clima, om = c && c.fontes && c.fontes.openmeteo; if (!om || !om.atual || !om.dados) return null;
  const d = om.dados; return { mm_6h: d.proximas_6h_mm, prob_hoje: d.dias && d.dias[0] ? d.dias[0].prob : null }; }
function loteAtivo(o, F) { const id = F.no && F.no.id; const vivos = o.lotes.filter(l => !l.fim && (l.no == null || l.no === id || l.no === ""));
  return vivos[vivos.length - 1] || (F.demo ? demoLote(Date.now() / 1000) : null); }
/* série de pesos do lote em horas desde o início: balança do nó (PESO) ou pesagens à mão */
function pesosDoLote(l, F) { const ini = l.inicio / 1000;
  const sensor = (l.demo || !F.demo ? F.serie || [] : []).filter(p => p.peso != null && p.ts >= ini).map(p => [(p.ts - ini) / 3600, p.peso]);
  if (sensor.length >= 3) return { pts: sensor, origem: "balança do secador" };
  const mao = (l.pesagens || []).map(p => [(p.t - l.inicio) / 3.6e6, +p.kg]).filter(p => p[0] >= 0 && p[1] > 0);
  if (mao.length) return { pts: [[0, +l.peso0]].concat(mao), origem: "pesagens à mão" };
  return { pts: [], origem: "" }; }

/* ════════ Desenho: gráficos em SVG (com tabela ao lado) ════════ */
const CORES = { ti:"#A63A28", te:"#4A4F44", tc:"#C08A1E", ui:"#2F7D5B", ue:"#8FB183", peso:"#1A4D2E", modelo:"#8A6410" };
function grafico(id, titulo, linhas, un, opc) { opc = opc || {}; const W = 640, H = 220, m = { l: 44, r: 12, t: 12, b: 28 };
  const todos = linhas.flatMap(l => l.pts.filter(p => p[1] != null && isFinite(p[1])));
  if (!todos.length) return `<p class="t2">Sem dados para ${E(titulo.toLowerCase())} ainda.</p>`;
  const xs = todos.map(p => p[0]), ys = todos.map(p => p[1]).concat(opc.extraY || []);
  const x0 = Math.min(...xs), x1 = Math.max(...xs, x0 + 1e-9), y0 = Math.floor(Math.min(...ys)), y1 = Math.ceil(Math.max(...ys, y0 + 1));
  const sx = x => m.l + (x - x0) / (x1 - x0 || 1) * (W - m.l - m.r), sy = y => H - m.b - (y - y0) / (y1 - y0 || 1) * (H - m.t - m.b);
  const traco = l => { const pts = l.pts.filter(p => p[1] != null && isFinite(p[1])); if (!pts.length) return "";
    return `<polyline fill="none" style="stroke:${l.cor}" stroke-width="${l.tracejado ? 2 : 2.5}"${l.tracejado ? ' stroke-dasharray="6 4"' : ""} points="${pts.map(p => sx(p[0]).toFixed(1) + "," + sy(p[1]).toFixed(1)).join(" ")}"/>`; };
  const ref = (opc.refs || []).map(r => `<line x1="${m.l}" x2="${W - m.r}" y1="${sy(r[0]).toFixed(1)}" y2="${sy(r[0]).toFixed(1)}" style="stroke:${r[2] || "#8A6410"}" stroke-dasharray="3 3"/><text x="${W - m.r}" y="${(sy(r[0]) - 4).toFixed(1)}" font-size="11" text-anchor="end" style="fill:${r[2] || "#8A6410"}">${E(r[1])}</text>`).join("");
  const eixoX = opc.rotX || (x => quando(x * 1000));
  const legenda = linhas.map(l => `<span class="t2 pq" style="display:inline-flex;align-items:center;gap:4px;margin-right:12px"><svg width="18" height="6" aria-hidden="true"><line x1="0" y1="3" x2="18" y2="3" style="stroke:${l.cor}" stroke-width="3"${l.tracejado ? ' stroke-dasharray="4 3"' : ""}/></svg>${E(l.nome)}</span>`).join("");
  /* nome acessível = título + resumo de cada linha, em textos separados (cada um tem o seu par em inglês) */
  const resumo = linhas.filter(l => l.pts.length).map(l => { const v = l.pts.map(p => p[1]).filter(x => x != null && isFinite(x)); return v.length ? `${l.nome}: de ${f1(Math.min(...v))} a ${f1(Math.max(...v))} ${un}` : ""; }).filter(Boolean);
  return `<figure style="margin:0"><svg id="${id}" viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px" role="img" aria-labelledby="${id}-t ${id}-d"><title id="${id}-t">${E(titulo)}</title>
    <line x1="${m.l}" y1="${H - m.b}" x2="${W - m.r}" y2="${H - m.b}" style="stroke:var(--linha,#D9D3C2)"/><line x1="${m.l}" y1="${m.t}" x2="${m.l}" y2="${H - m.b}" style="stroke:var(--linha,#D9D3C2)"/>
    <text x="${m.l - 6}" y="${m.t + 10}" font-size="11" text-anchor="end" style="fill:var(--tinta2,#4A4F44)">${f1(y1, 0)}</text><text x="${m.l - 6}" y="${H - m.b}" font-size="11" text-anchor="end" style="fill:var(--tinta2,#4A4F44)">${f1(y0, 0)}</text>
    <text x="${m.l}" y="${H - 8}" font-size="11" style="fill:var(--tinta2,#4A4F44)">${E(eixoX(x0))}</text><text x="${W - m.r}" y="${H - 8}" font-size="11" text-anchor="end" style="fill:var(--tinta2,#4A4F44)">${E(eixoX(x1))}</text>
    <text x="${m.l + 4}" y="${m.t + 10}" font-size="11" style="fill:var(--tinta2,#4A4F44)">${E(un)}</text>${ref}${linhas.map(traco).join("")}</svg>
    <figcaption>${legenda}<span id="${id}-d" class="so-leitor">${resumo.map(r => `<span>${E(r)}</span>`).join("; ")}</span></figcaption></figure>`; }
function tabelaSerie(cap, serie, cols) { const ult = serie.slice(-12).reverse();
  return `<details><summary>Ver os números (${E(cap)})</summary><div class="rolagem"><table><caption>${E(cap)}: as 12 leituras mais novas</caption><thead><tr><th scope="col">Quando</th>${cols.map(c => `<th scope="col">${E(c[1])}</th>`).join("")}</tr></thead><tbody>
    ${ult.map(p => `<tr><th scope="row">${E(quando(p.ts * 1000))}</th>${cols.map(c => `<td>${f1(p[c[0]], c[2] == null ? 1 : c[2])}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`; }

/* ════════ Peças da tela ════════ */
const cartao = (id, tit, numero, un, extra) => `<section class="cartao" aria-labelledby="h-${id}"><h3 id="h-${id}" class="t3">${tit}</h3><span class="numero">${numero}</span><span class="t2">${un}</span>${extra || ""}</section>`;
const campo = (k, rot, val, ph, ajuda, grupo) => `<div><label for="sec-${k}">${rot}</label><input id="sec-${k}" type="text" inputmode="decimal" data-sec-k="${k}"${grupo ? ` data-sec-m="${grupo}"` : ""} value="${E(val == null ? "" : val)}" placeholder="${E(ph || "")}" style="width:100%"${ajuda ? ` aria-describedby="sec-${k}-a"` : ""}>${ajuda ? `<span id="sec-${k}-a" class="t2 pq">${ajuda}</span>` : ""}</div>`;
const selProduto = (id, atual, grupo) => `<div><label for="${id}">Produto</label><select id="${id}" data-sec-k="${id.replace("sec-", "")}"${grupo ? ` data-sec-m="${grupo}"` : ""} style="width:100%">${Object.entries(PRODUTOS).map(([k, p]) => `<option value="${k}" ${k === atual ? "selected" : ""}>${E(p.nome)}</option>`).join("")}</select></div>`;
const avisoDemo = F => F.demo ? `<div class="faixa in" role="note"><strong>${F.semNo ? "Nenhum secador ligado a este computador central ainda." : "Exemplo com dados simulados."}</strong> ${F.semNo ? "Abaixo, um secador de exemplo (café). Ligue o secador pelo MQTT ou pelo Wi-Fi (linha TIPO:SEC) para ver os dados reais." : "Um secador de café de exemplo, para conhecer a tela. Na plataforma ligada ao computador central aparecem os secadores de verdade."}</div>` : "";

function parteAgora(o, F) { const n = F.no, l = loteAtivo(o, F), prod = l ? l.produto : null, p = produto(prod);
  const al = alertas(n, prod, chuvaDaTela());
  if (!n.online && !n.demo) al.unshift(["al", `Secador sem falar há ${f1((n.ha_s || 0) / 60, 0)} min: confira a energia e a rede.`]);
  const chip = (tit, ok, txt) => `<span class="selo ${ok === true ? "ok" : ok === false ? "at" : "in"}" title="${E(tit)}">${E(txt)}</span>`;
  const faixaT = n.ti == null ? null : n.ti > p.t_max ? false : (n.ti >= p.t_ideal[0] && n.ti <= p.t_ideal[1]) ? true : null;
  const chips = `<p class="chips" aria-label="Situação">${chip("Comunicação", n.online !== false, n.online === false ? "Sem falar" : "Falando")}
    ${chip("Temperatura", faixaT, n.ti == null ? "Temperatura: sem leitura" : faixaT === false ? "Quente demais" : faixaT ? "Temperatura boa" : "Temperatura fora da faixa ideal")}
    ${chip("Ventilador", n.vent ? true : null, n.vent ? "Ventilador ligado" : "Ventilador desligado")}
    ${n.abt == null ? "" : chip("Tampa", n.abt ? null : true, n.abt ? "Aberto" : "Fechado")}</p>`;
  const lista = F.nos.length > 1 ? `<div><label for="sec-no">Secador</label><select id="sec-no" data-sec-acao="no">${F.nos.map(x => `<option value="${x.id}" ${x.id === n.id ? "selected" : ""}>Nó ${String(x.id).padStart(2, "0")}</option>`).join("")}</select></div>` : "";
  const cards = `<div class="grade">${cartao("sec-ti", "Dentro do secador", f1(n.ti), "°C · " + f1(n.ui, 0) + " % de umidade")}
    ${cartao("sec-te", "Lá fora", f1(n.te), "°C · " + f1(n.ue, 0) + " % de umidade")}
    ${cartao("sec-tc", "Coletor solar", f1(n.tc), "°C" + (n.irr != null ? " · sol " + f1(n.irr, 0) + " W/m²" : ""))}
    ${cartao("sec-peso", "Peso do produto", f1(n.peso, 1), n.peso == null ? "sem balança: pese à mão em Lotes" : "kg")}</div>`;
  const alertasH = al.length ? `<div class="faixa ${al.some(a => a[0] === "al") ? "al" : "at"}" role="alert"><ul>${al.map(a => `<li>${E(a[1])}</li>`).join("")}</ul></div>` : `<div class="faixa ok" role="status">Tudo certo no secador agora.</div>`;
  let lote = `<section class="cartao" aria-labelledby="h-sec-lote"><h2 id="h-sec-lote">Lote de agora</h2><p class="t2">Nenhum lote secando. Registre um em <button type="button" class="link" data-sec-sub="lotes">Lotes</button>.</p></section>`;
  if (l) { const ps = pesosDoLote(l, F), pv = previsaoLote(l, ps.pts), agoraH = (Date.now() - l.inicio) / 3.6e6, pesoAgora = n.peso != null && ps.origem === "balança do secador" ? n.peso : pesoPrevisto(pv.modelo, agoraH);
    const fim = pv.horas_fim == null ? null : l.inicio + pv.horas_fim * 3.6e6;
    lote = `<section class="cartao" aria-labelledby="h-sec-lote"><h2 id="h-sec-lote">Lote de agora: ${E(produto(l.produto).nome)}</h2>
      <p>Começou em ${E(quando(l.inicio))} com ${f1(+l.peso0, 1)} kg e ${f1(+l.u0, 0)} % de umidade. Meta: ${f1(+l.alvo, 1)} % (${f1(pv.peso_alvo, 1)} kg).</p>
      <p>Umidade ${ps.pts.length ? "medida pelo peso" : "estimada"}: <strong>${f1(umidadeDoPeso(+l.peso0, +l.u0, pesoAgora), 1)} %</strong>. Fim previsto: <strong>${fim == null ? "este ar não chega à meta (veja Lotes)" : fim <= Date.now() ? "já na meta: confira com o medidor de umidade" : E(quando(fim))}</strong>${pv.medido ? "" : " (estimado sem balança)"}.</p></section>`; }
  const vent = `<section class="cartao" aria-labelledby="h-sec-vent"><h2 id="h-sec-vent">Ventilador</h2><p class="t2">${n.vent ? "Ligado." : "Desligado."} Com o secador quente demais, o próprio aparelho liga o ventilador e não deixa desligar até esfriar.</p>
    <button type="button" data-sec-acao="vent" data-sec-v="${n.vent ? 0 : 1}" id="sec-b-vent">${n.vent ? "Desligar ventilador" : "Ligar ventilador"}</button><span id="sec-vent-msg" class="t2 pq" role="status">${E(U().secMsg || "")}</span></section>`;
  return avisoDemo(F) + lista + chips + alertasH + cards + lote + vent; }

function parteLotes(o, F) { const u = U(), fm = u.secForm || {}, prodF = fm.produto || "cafe", pF = produto(prodF);
  const novo = `<section class="cartao" aria-labelledby="h-sec-novo"><h2 id="h-sec-novo">Registrar um lote</h2><div class="precos">
    ${selProduto("sec-produto", prodF, "form")}${campo("peso0", "Peso no começo (kg)", fm.peso0, "ex.: 120", null, "form")}
    ${campo("u0", "Umidade no começo (% base úmida)", fm.u0, f1(pF.u0, 0), "Do medidor de umidade; vazio = valor típico do produto (verificar).", "form")}
    ${campo("alvo", "Umidade final desejada (%)", fm.alvo, f1(pF.alvo, 1), pF === PRODUTOS.cafe ? "Café: 11 a 12 % base úmida para guardar." : "", "form")}
    <div><label for="sec-inicio">Começo</label><input id="sec-inicio" type="datetime-local" data-sec-k="inicio" data-sec-m="form" value="${E(fm.inicio || "")}" style="width:100%"></div></div>
    <button type="button" data-sec-acao="novo" id="sec-b-novo">Começar o lote</button><span class="t2 pq" role="status" id="sec-novo-msg">${E(u.secLoteMsg || "")}</span></section>`;
  const l = loteAtivo(o, F);
  let ativo = "";
  if (l) { const ps = pesosDoLote(l, F), pv = previsaoLote(l, ps.pts), m = pv.modelo, hAgora = Math.max(0, (Date.now() - l.inicio) / 3.6e6);
    const hMax = Math.max(hAgora, pv.horas_fim || 0, 24) * 1.1, curva = []; for (let i = 0; i <= 60; i++) { const h = hMax * i / 60; curva.push([h, pesoPrevisto(m, h)]); }
    const fim = pv.horas_fim == null ? null : l.inicio + pv.horas_fim * 3.6e6;
    const g = grafico("sec-g-curva", "Curva de secagem", [{ nome: ps.origem ? "Peso medido (" + ps.origem + ")" : "Sem pesagens", cor: CORES.peso, pts: ps.pts },
      { nome: pv.medido ? "Modelo ajustado" : "Curva estimada (sem balança)", cor: CORES.modelo, pts: curva, tracejado: true }], "kg",
      { refs: [[pv.peso_alvo, "meta " + f1(pv.peso_alvo, 1) + " kg", "#1F4A1C"]], extraY: [pv.peso_alvo], rotX: h => f1(h, 0) + " h" });
    ativo = `<section class="cartao" aria-labelledby="h-sec-ativo"><h2 id="h-sec-ativo">Lote secando: ${E(produto(l.produto).nome)}${l.demo ? " (exemplo)" : ""}</h2>
      <div class="grade">${cartao("sec-l-agua", "Água para tirar", f1(pv.agua_kg, 1), "kg no lote")}${cartao("sec-l-fim", "Fim previsto", fim == null ? "—" : E(quando(fim)), fim == null ? "o equilíbrio fica acima da meta: mais calor ou mais ar" : "em " + duracao(pv.horas_fim) + " desde o começo")}
      ${cartao("sec-l-k", "Velocidade de secagem", f1(m.k * 100, 2), "% por hora do que falta (k = " + f1(m.k, 4) + " 1/h)")}</div>${g}
      <p class="t2 pq">${pv.medido ? `Modelo ajustado a ${m.n} pesagens: peso de equilíbrio ${f1(m.we, 1)} kg.` : ps.pts.length ? "Poucas pesagens ainda (o ajuste pede 3 ou mais pontos): curva estimada com a velocidade típica do produto (verificar)." : "Sem balança e sem pesagens: curva estimada com a velocidade típica do produto (verificar). Pese uma bandeja de amostra uma vez por dia para a previsão valer."}</p>
      ${l.demo ? "" : `<div class="precos">${campo("pesar", "Pesagem à mão agora (kg)", "", "ex.: 95", "Peso do lote inteiro, ou da bandeja de amostra vezes o número de bandejas.")}</div>
      <button type="button" data-sec-acao="pesar" data-sec-lote="${E(l.id)}">Guardar pesagem</button>
      <div class="precos">${campo("final", "Peso no fim (kg)", "", "ex.: 52")}</div><button type="button" data-sec-acao="fim" data-sec-lote="${E(l.id)}">Terminar o lote</button>`}</section>`; }
  const feitos = o.lotes.filter(x => x.fim);
  const hist = feitos.length ? `<section class="cartao" aria-labelledby="h-sec-feitos"><h2 id="h-sec-feitos">Lotes terminados</h2><div class="rolagem"><table><caption>Rendimento e umidade final de cada lote</caption><thead><tr><th scope="col">Produto</th><th scope="col">Começo</th><th scope="col">Duração</th><th scope="col">Peso inicial</th><th scope="col">Peso final</th><th scope="col">Rendimento</th><th scope="col">Umidade final calculada</th></tr></thead><tbody>
    ${feitos.slice().reverse().map(x => `<tr><th scope="row">${E(produto(x.produto).nome)}</th><td>${E(quando(x.inicio))}</td><td>${duracao((x.fim - x.inicio) / 3.6e6)}</td><td>${f1(+x.peso0, 1)} kg</td><td>${f1(+x.peso_final, 1)} kg</td><td>${f1(rendimento(+x.peso0, +x.peso_final), 1)} %</td><td>${f1(umidadeDoPeso(+x.peso0, +x.u0, +x.peso_final), 1)} %</td></tr>`).join("")}</tbody></table></div>
    <p class="t2 pq">Umidade final calculada pela matéria seca: confira com o medidor de umidade antes de ensacar.</p></section>` : "";
  return avisoDemo(F) + ativo + novo + hist; }

function parteHistorico(o, F) { const s = F.serie || [], t = p => p.ts;
  const linha = (k, nome) => ({ nome, cor: CORES[k], pts: s.map(p => [t(p), p[k]]) });
  const l = loteAtivo(o, F), p = produto(l ? l.produto : null);
  return avisoDemo(F) + `<section class="cartao" aria-labelledby="h-sec-ht"><h2 id="h-sec-ht">Temperatura</h2>${grafico("sec-g-t", "Temperatura", [linha("ti", "Dentro"), linha("tc", "Coletor"), linha("te", "Lá fora")], "°C", { refs: [[p.t_max, "máximo " + f1(p.t_max, 0) + " °C", "#7A2214"]] })}${tabelaSerie("temperatura", s, [["ti", "Dentro (°C)"], ["tc", "Coletor (°C)"], ["te", "Lá fora (°C)"]])}</section>
    <section class="cartao" aria-labelledby="h-sec-hu"><h2 id="h-sec-hu">Umidade do ar</h2>${grafico("sec-g-u", "Umidade do ar", [linha("ui", "Dentro"), linha("ue", "Lá fora")], "%")}${tabelaSerie("umidade", s, [["ui", "Dentro (%)", 0], ["ue", "Lá fora (%)", 0]])}</section>
    <section class="cartao" aria-labelledby="h-sec-hp"><h2 id="h-sec-hp">Peso do produto</h2>${grafico("sec-g-p", "Peso do produto", [linha("peso", "Peso")], "kg")}${tabelaSerie("peso", s, [["peso", "Peso (kg)", 2], ["irr", "Sol (W/m²)", 0]])}</section>
    <p class="t2 pq">${F.demo ? "Dados simulados de exemplo." : "Leituras guardadas no computador central (as 200 mais novas de cada sensor)."}</p>`; }

/* irradiação do lugar (NASA POWER, base aberta guardada no servidor) */
function irradiacaoDoLugar() { const u = U(), L = typeof gisLugar === "function" ? gisLugar() : null;
  if (L && emHub() && typeof carregarGis === "function") carregarGis("irradiacao", L.lat, L.lon);
  const g = u.gis && u.gis.irradiacao; return g && g.ponto && Array.isArray(g.ponto.meses) ? g.ponto : null; }
function fatorRedeBase() { try { const s = document.getElementById("base-fatores-emissao"), b = s ? JSON.parse(s.textContent) : (window.PHYSIS_FATORES_EMISSAO || null);
  if (b && b.rede && b.rede.anual) { const a = b.rede.anual[b.rede.padrao]; if (a && a.valor > 0) return a.valor; } } catch (e) {} return null; }

function parteDimensionamento(o) { const d = o.dim, prod = d.produto || "cafe", p = produto(prod), ir = irradiacaoDoLugar(), mes = d.mes == null || d.mes === "" ? "" : String(d.mes);
  const irBase = ir ? (mes === "" ? Math.min(...ir.meses) : ir.meses[+mes]) : null, fr = fatorRedePadrao();
  const P = { massa: num(d.massa) || 0, u0: num(d.u0) != null ? num(d.u0) : p.u0, alvo: num(d.alvo) != null ? num(d.alvo) : p.alvo,
    irradiacao: num(d.irradiacao) != null ? num(d.irradiacao) : irBase, eta_coletor: num(d.eta_coletor) != null ? num(d.eta_coletor) : 0.4,
    aproveitamento: num(d.aproveitamento) != null ? num(d.aproveitamento) : 0.5, dias: num(d.dias) || 5, horas_sol: num(d.horas_sol) || 8, delta_t: num(d.delta_t) || 15,
    lotes_ano: num(d.lotes_ano) != null ? num(d.lotes_ano) : 10, eta_eletrico: num(d.eta_eletrico) || 0.5, eta_lenha: num(d.eta_lenha) || 0.35,
    fator_rede: num(d.fator_rede) != null ? num(d.fator_rede) : fr, lenha_nao_renovavel: !!d.lenha_nr };
  /* sem o local (página Início) e sem irradiação digitada: a área de coletor, que depende do sol do lugar, não é calculada */
  const semLocal = !ir && num(d.irradiacao) == null;   /* sem a irradiação do lugar e sem a digitada: a área não é calculada */
  const R = dimensionar(P);
  const origemIr = semLocal ? (typeof avisoSemLocal === "function" ? avisoSemLocal() : "Local não informado — preencha na página Início.") + " Ou digite a irradiação no coletor abaixo." : ir ? `Irradiação do lugar (NASA POWER, média de longo prazo): de ${f1(Math.min(...ir.meses), 2)} a ${f1(Math.max(...ir.meses), 2)} kWh/m² por dia. Campo vazio usa ${mes === "" ? "o mês mais fraco" : "o mês escolhido"}.`
    : "";
  const ent = `<section class="cartao" aria-labelledby="h-sec-dent"><h2 id="h-sec-dent">O que vai secar</h2><div class="precos">
    ${selProduto("sec-produto-d", prod, "dim")}${campo("massa", "Produto por lote (kg)", d.massa, "ex.: 200", null, "dim")}
    ${campo("u0", "Umidade no começo (%)", d.u0, f1(p.u0, 0), null, "dim")}${campo("alvo", "Umidade final (%)", d.alvo, f1(p.alvo, 1), null, "dim")}
    ${campo("dias", "Dias de sol por lote", d.dias, "5", null, "dim")}${campo("horas_sol", "Horas de ventilador por dia", d.horas_sol, "8", null, "dim")}
    ${campo("lotes_ano", "Lotes por ano", d.lotes_ano, "10", null, "dim")}</div></section>
    <section class="cartao" aria-labelledby="h-sec-dsol"><h2 id="h-sec-dsol">Sol e coletor</h2><div class="t2" role="status">${origemIr}</div><div class="precos">
    ${ir ? `<div><label for="sec-mes">Mês de projeto</label><select id="sec-mes" data-sec-k="mes" data-sec-m="dim" style="width:100%"><option value="" ${mes === "" ? "selected" : ""}>Mês mais fraco</option>${MESES.map((x, i) => `<option value="${i}" ${mes === String(i) ? "selected" : ""}>${x} · ${f1(ir.meses[i], 2)}</option>`).join("")}</select></div>` : ""}
    ${campo("irradiacao", "Irradiação no coletor (kWh/m² por dia)", d.irradiacao, irBase != null ? f1(irBase, 2) : "", null, "dim")}
    ${campo("eta_coletor", "Eficiência do coletor (0 a 1)", d.eta_coletor, "0,4", "Coletor de ar com cobertura: tipicamente 0,3 a 0,6 (verificar com o ensaio do coletor).", "dim")}
    ${campo("aproveitamento", "Aproveitamento do ar quente (0 a 1)", d.aproveitamento, "0,5", "Parte do calor do ar que vira evaporação; o resto sai com o ar.", "dim")}
    ${campo("delta_t", "Aquecimento do ar no coletor (°C)", d.delta_t, "15", null, "dim")}</div></section>`;
  const res = `<div class="grade">${cartao("sec-d-agua", "Água para tirar", f1(R.agua_kg, 1), "kg por lote")}${cartao("sec-d-area", "Área de coletor", semLocal ? "—" : f1(R.area_m2, 1), semLocal ? "falta o local" : "m²")}
    ${cartao("sec-d-ar", "Vazão de ar", f1(R.vazao_m3h, 0), "m³/h no ventilador")}${cartao("sec-d-en", "Calor no ar", f1(R.q_ar_mj, 0), "MJ por lote (" + f1(R.q_ar_mj / MJ_POR_KWH, 0) + " kWh)")}</div>`;
  const comp = `<section class="cartao" aria-labelledby="h-sec-dcomp"><h2 id="h-sec-dcomp">Comparado com secador elétrico ou a lenha</h2><div class="precos">
    ${campo("eta_eletrico", "Eficiência do secador elétrico (0 a 1)", d.eta_eletrico, "0,5", null, "dim")}${campo("eta_lenha", "Eficiência da fornalha a lenha (0 a 1)", d.eta_lenha, "0,35", null, "dim")}
    ${campo("fator_rede", "Fator da rede elétrica (tCO₂/MWh)", d.fator_rede, fr != null ? f1(fr, 4) : "", fr != null ? "Da base de fatores do Carbono (ou da premissa rede.fator_emissao)." : "Sem a base de fatores: digite o fator do ano.", "dim")}
    <div><label><input type="checkbox" id="sec-lenha_nr" data-sec-k="lenha_nr" data-sec-m="dim" ${d.lenha_nr ? "checked" : ""}> Lenha sem reposição (conta o CO₂ da queima)</label></div></div>
    <div class="rolagem"><table><caption>Energia e CO₂ que o sol evita por ano (${f1(P.lotes_ano, 0)} lotes)</caption><thead><tr><th scope="col">Secador trocado</th><th scope="col">Energia por lote</th><th scope="col">Energia por ano</th><th scope="col">CO₂ evitado por ano</th></tr></thead><tbody>
    <tr><th scope="row">Elétrico</th><td>${f1(R.kwh_eletrico_lote, 0)} kWh</td><td>${f1(R.kwh_eletrico_ano, 0)} kWh</td><td>${f1(R.co2_eletrico_kg_ano, 0)} kg</td></tr>
    <tr><th scope="row">A lenha</th><td>${f1(R.kg_lenha_lote, 0)} kg de lenha</td><td>${f1(R.kg_lenha_ano, 0)} kg de lenha</td><td>${f1(R.co2_lenha_kg_ano, 0)} kg</td></tr></tbody></table></div>
    <p class="t2 pq">O ventilador gasta energia também: some a potência dele × horas no ano antes de comparar. A rede brasileira tem fator baixo; com lenha de manejo sustentável, o CO₂ da queima é biogênico e só o metano e o óxido nitroso contam.</p></section>`;
  return ent + res + comp + `<p class="t2 pq">Contas: água = massa × (u₀ − u)/(100 − u); calor = água × 2,45 MJ/kg ÷ aproveitamento; área = calor ÷ (irradiação × 3,6 × eficiência × dias); ar = água ÷ Δw, com Δw = 1,006 × ΔT × aproveitamento ÷ 2.450; vazão = ar ÷ 1,15 kg/m³ ÷ horas. Resultado de pré-projeto: conferir com o fornecedor do coletor e do ventilador.</p>`; }

function parteMetodologia() { return `<section class="cartao" aria-labelledby="h-sec-met"><h2 id="h-sec-met">Metodologia e normas</h2><ul>
  <li><strong>Como o secador funciona:</strong> o coletor esquenta o ar, o ventilador empurra esse ar pelas bandejas e o ar leva a água do produto. Ar mais quente segura mais água; por isso o ar de dentro fica mais seco que o de fora quando o sol bate.</li>
  <li><strong>Umidade do produto:</strong> sempre em base úmida (água ÷ peso total). A matéria seca não muda durante a secagem, então o peso diz a umidade: u = 100 × (1 − matéria seca ÷ peso).</li>
  <li><strong>Curva de secagem:</strong> modelo exponencial simples (de Lewis, ou de Newton): o peso cai em direção a um peso de equilíbrio, sempre mais devagar. Com 3 ou mais pesagens, a tela ajusta o modelo aos pesos (mínimos quadrados) e prevê a hora do fim. Sem pesagens, usa uma velocidade típica do produto (verificar). Na secagem real há fases (aquecimento, taxa constante, taxa decrescente) e o dia e a noite; modelos de duas fases (Page, Henderson e Pabis) podem entrar depois, com os dados do próprio secador.</li>
  <li><strong>Temperaturas por produto:</strong> café com a massa até 40 °C para qualidade e nunca acima de 45 °C (sementes até 35 °C), guardado com 11 a 12 % de umidade, conforme as recomendações da Embrapa Café e do Consórcio Pesquisa Café; ervas medicinais e aromáticas entre 30 e 40 °C para não perder óleos essenciais; frutas em fatias entre 55 e 65 °C; cogumelos entre 40 e 55 °C. Todos marcados "verificar": a equipe técnica confere com a literatura do produto e com o comprador.</li>
  <li><strong>Dimensionamento:</strong> balanço de massa (água a tirar), balanço de energia (calor latente de 2,45 MJ por kg de água a cerca de 25 °C) e psicrometria simplificada (o ar esquenta no coletor e esfria ao pegar água, com calor específico de 1,006 kJ/kg·K). A eficiência do coletor de ar segue os fundamentos do ASHRAE Handbook (Fundamentals, psicrometria) e da norma ASHRAE 93 (ensaio de coletores solares); a irradiação vem da NASA POWER (média de longo prazo do lugar).</li>
  <li><strong>Energia e CO₂ evitados:</strong> energia que um secador elétrico ou a lenha gastaria para tirar a mesma água, com a eficiência de cada um; CO₂ pela base de fatores do Carbono (rede elétrica do SIN; lenha pelos fatores do IPCC, GWP do AR5).</li>
  <li><strong>Alertas:</strong> superaquecimento pelo produto do lote; umidade de dentro acima de ${UMIDADE_INTERNA_ALTA} % com o ventilador desligado; chuva prevista (Open-Meteo, já usada na plataforma) com o secador aberto; aparelho sem falar. A segurança de temperatura fica no próprio aparelho: ele liga o ventilador sozinho no limite, mesmo sem rede.</li></ul>
  <p class="t2"><strong>Referências para conferir (redação própria; ler o texto vigente)</strong></p><ul>
  <li>Embrapa Café e Consórcio Pesquisa Café — recomendações de secagem e armazenamento do café (temperatura da massa e umidade final).</li>
  <li>MAPA — Instrução Normativa 8/2003 (Regulamento Técnico de Identidade e de Qualidade do café beneficiado grão cru): umidade máxima do café para comercialização — verificar a redação vigente.</li>
  <li>ANVISA — boas práticas de fabricação para alimentos (RDC 275/2002 e RDC 216/2004) quando o produto seco for vendido; ervas medicinais com regras próprias — verificar.</li>
  <li>ASHRAE Handbook — Fundamentals (psicrometria) e ASHRAE 93 (método de ensaio de coletores solares); Duffie e Beckman, Solar Engineering of Thermal Processes (coletores de ar).</li>
  <li>Literatura de secagem solar de produtos agrícolas (FAO e manuais de extensão rural) para a eficiência de secadores solares de ar forçado — tipicamente de 10 a 30 % no conjunto.</li></ul></section>`; }

function telaSecador() { const u = U(), SUBS = [["agora", "Agora"], ["lotes", "Lotes"], ["historico", "Histórico"], ["dimensionamento", "Dimensionamento"], ["metodologia", "Metodologia e normas"]];
  const sub = SUBS.some(s => s[0] === u.secSub) ? u.secSub : "agora", o = ler(), F = fonte();
  const chips = `<div class="chips" role="group" aria-label="Partes do secador solar">${SUBS.map(([k, n]) => `<button type="button" id="sec-sub-${k}" data-sec-sub="${k}" aria-pressed="${k === sub}">${n}</button>`).join("")}</div>`;
  const corpo = sub === "lotes" ? parteLotes(o, F) : sub === "historico" ? parteHistorico(o, F) : sub === "dimensionamento" ? parteDimensionamento(o) : sub === "metodologia" ? parteMetodologia() : parteAgora(o, F);
  return `<h1>Secador solar</h1><p class="t2 apoio">Secagem de café, frutas, ervas e cogumelos com o sol: temperatura e umidade ao vivo, lotes com previsão do fim, histórico e o tamanho do coletor.</p>${chips}<div id="sec-corpo">${corpo}</div>`; }

/* ════════ Eventos (atributos data-sec-…; um ouvinte só, protegido) ════════ */
function refocar(id) { const x = pega(id); if (x) x.focus(); }
function dataLocal(s) { const t = s ? new Date(s).getTime() : NaN; return isFinite(t) ? t : Date.now(); }
async function acao(b) { const u = U(), a = b.dataset.secAcao, o = ler();
  if (a === "vent") { const v = b.dataset.secV === "1" ? 1 : 0, F = fonte();
    if (F.demo) { u.secDemoVent = v; u.secMsg = v ? "Ventilador ligado (exemplo)." : "Ventilador desligado (exemplo)."; }
    else if (typeof enviarComando === "function") { u.secMsg = "Enviando…"; redesenhar(); try { await enviarComando(`CMD:${String(F.no.id).padStart(2, "0")}:VENT:${v}`); u.secMsg = "Pedido enviado ao secador; confirma na próxima leitura."; } catch (e) { u.secMsg = "Não foi possível enviar agora."; } }
    else u.secMsg = "Sem ligação com o computador central.";
    redesenhar(); refocar("sec-b-vent"); return; }
  if (a === "novo") { const fm = u.secForm || {}, pr = fm.produto || "cafe", p = produto(pr), peso0 = num(fm.peso0);
    if (!(peso0 > 0)) { u.secLoteMsg = "Informe o peso no começo."; redesenhar(); refocar("sec-peso0"); return; }
    const u0 = num(fm.u0) != null ? num(fm.u0) : p.u0, alvo = num(fm.alvo) != null ? num(fm.alvo) : p.alvo;
    if (!(u0 > 0 && u0 < 100 && alvo >= 0 && alvo < u0)) { u.secLoteMsg = "A umidade final tem de ser menor que a do começo (as duas entre 0 e 100 %)."; redesenhar(); refocar("sec-alvo"); return; }
    const F = fonte();
    o.lotes.push({ id: "L" + Date.now().toString(36), produto: pr, peso0, u0, alvo, inicio: dataLocal(fm.inicio), no: F.demo ? null : F.no.id, pesagens: [] });
    gravar(o); u.secForm = {}; u.secLoteMsg = "Lote registrado."; redesenhar(); refocar("sec-b-novo"); return; }
  const l = o.lotes.find(x => x.id === b.dataset.secLote); if (!l) return;
  if (a === "pesar") { const kg = num((pega("sec-pesar") || {}).value); if (!(kg > 0)) { refocar("sec-pesar"); return; }
    l.pesagens = (l.pesagens || []).concat([{ t: Date.now(), kg }]); gravar(o); redesenhar(); refocar("sec-pesar"); return; }
  if (a === "fim") { const kg = num((pega("sec-final") || {}).value); if (!(kg > 0)) { refocar("sec-final"); return; }
    l.fim = Date.now(); l.peso_final = kg; gravar(o); u.secLoteMsg = `Lote terminado: rendimento de ${f1(rendimento(+l.peso0, kg), 1)} %.`; redesenhar(); refocar("sec-b-novo"); } }
if (typeof document !== "undefined" && !window.__secEventos) { window.__secEventos = true;
  document.addEventListener("change", ev => { const t = ev.target; if (!t || !t.dataset) return; const u = U();
    if (t.dataset.secAcao === "no") { u.secNo = +t.value; redesenhar(); refocar("sec-no"); return; }
    if (!t.dataset.secK || !t.dataset.secM) return;
    const k = t.dataset.secK.replace(/-d$/, ""), v = t.type === "checkbox" ? (t.checked ? 1 : "") : t.value;
    if (t.dataset.secM === "form") { u.secForm = Object.assign({}, u.secForm, { [k]: v }); }
    else if (t.dataset.secM === "dim") { const o = ler(); o.dim = Object.assign({}, o.dim, { [k]: v }); gravar(o); }
    const id = t.id; redesenhar(); refocar(id); });
  document.addEventListener("click", ev => { const b = ev.target && ev.target.closest ? ev.target.closest("button") : null; if (!b || !b.dataset) return;
    if (b.dataset.secSub) { U().secSub = b.dataset.secSub; redesenhar(); refocar("sec-sub-" + b.dataset.secSub); return; }
    if (b.dataset.secAcao) acao(b); }); }

/* ════════ Inglês (o integrador junta ao I18N da plataforma) ════════ */
window.SECADOR_I18N = {
  "Secador solar": "Solar dryer",
  "Agora": "Now",
  "Lotes": "Batches",
  "Histórico": "History",
  "Dimensionamento": "Sizing",
  "Metodologia e normas": "Methodology and standards",
  "Partes do secador solar": "Solar dryer sections",
  "Secagem de café, frutas, ervas e cogumelos com o sol: temperatura e umidade ao vivo, lotes com previsão do fim, histórico e o tamanho do coletor.": "Drying coffee, fruit, herbs and mushrooms with the sun: live temperature and humidity, batches with a predicted end, history and collector size.",
  "Dentro do secador": "Inside the dryer",
  "Lá fora": "Outside",
  "Coletor solar": "Solar collector",
  "Peso do produto": "Product weight",
  "Falando": "Online",
  "Sem falar": "Offline",
  "Temperatura boa": "Good temperature",
  "Quente demais": "Too hot",
  "Temperatura fora da faixa ideal": "Temperature outside the ideal range",
  "Ventilador ligado": "Fan on",
  "Ventilador desligado": "Fan off",
  "Aberto": "Open",
  "Fechado": "Closed",
  "Tudo certo no secador agora.": "All good in the dryer now.",
  "Ventilador": "Fan",
  "Ligar ventilador": "Turn fan on",
  "Desligar ventilador": "Turn fan off",
  "Lote de agora": "Current batch",
  "Registrar um lote": "Register a batch",
  "Produto": "Product",
  "Peso no começo (kg)": "Starting weight (kg)",
  "Umidade no começo (% base úmida)": "Starting moisture (% wet basis)",
  "Umidade final desejada (%)": "Target final moisture (%)",
  "Começo": "Start",
  "Começar o lote": "Start the batch",
  "Guardar pesagem": "Save weighing",
  "Pesagem à mão agora (kg)": "Manual weighing now (kg)",
  "Peso no fim (kg)": "Final weight (kg)",
  "Terminar o lote": "Finish the batch",
  "Lotes terminados": "Finished batches",
  "Água para tirar": "Water to remove",
  "Fim previsto": "Predicted end",
  "Velocidade de secagem": "Drying rate",
  "Rendimento": "Efficiency",
  "Umidade final calculada": "Calculated final moisture",
  "Temperatura": "Temperature",
  "Umidade do ar": "Air humidity",
  "Dentro": "Inside",
  "Coletor": "Collector",
  "Peso": "Weight",
  "O que vai secar": "What will be dried",
  "Produto por lote (kg)": "Product per batch (kg)",
  "Dias de sol por lote": "Sunny days per batch",
  "Horas de ventilador por dia": "Fan hours per day",
  "Lotes por ano": "Batches per year",
  "Sol e coletor": "Sun and collector",
  "Mês de projeto": "Design month",
  "Mês mais fraco": "Weakest month",
  "Irradiação no coletor (kWh/m² por dia)": "Irradiation on the collector (kWh/m² per day)",
  "Eficiência do coletor (0 a 1)": "Collector efficiency (0 to 1)",
  "Aproveitamento do ar quente (0 a 1)": "Use of the hot air (0 to 1)",
  "Aquecimento do ar no coletor (°C)": "Air temperature rise in the collector (°C)",
  "Área de coletor": "Collector area",
  "Vazão de ar": "Air flow",
  "Calor no ar": "Heat in the air",
  "Comparado com secador elétrico ou a lenha": "Compared with an electric or firewood dryer",
  "Eficiência do secador elétrico (0 a 1)": "Electric dryer efficiency (0 to 1)",
  "Eficiência da fornalha a lenha (0 a 1)": "Firewood furnace efficiency (0 to 1)",
  "Fator da rede elétrica (tCO₂/MWh)": "Grid emission factor (tCO₂/MWh)",
  "Lenha sem reposição (conta o CO₂ da queima)": "Firewood without replanting (counts combustion CO₂)",
  "Elétrico": "Electric",
  "A lenha": "Firewood",
  "Café (cereja ou pergaminho)": "Coffee (cherry or parchment)",
  "Ervas e folhas (medicinais, aromáticas)": "Herbs and leaves (medicinal, aromatic)",
  "Frutas em fatias": "Sliced fruit",
  "Cogumelos": "Mushrooms",
  "Outro produto": "Other product",
  "Exemplo com dados simulados.": "Example with simulated data.",
  "Nenhum secador ligado a este computador central ainda.": "No dryer connected to this central computer yet.",
  "Secador": "Dryer",
  "Comunicação": "Communication",
  "Tampa": "Lid",
  "Situação": "Status",
  "Temperatura: sem leitura": "Temperature: no reading",
  "Sensor de temperatura e umidade interna sem leitura.": "Inside temperature and humidity sensor without a reading.",
  "Chuva prevista e o secador está aberto: feche a tampa ou recolha o produto.": "Rain forecast and the dryer is open: close the lid or bring the product in.",
  "sem balança: pese à mão em Lotes": "no scale: weigh by hand in Batches",
  "Nenhum lote secando. Registre um em": "No batch drying. Register one in",
  "Umidade medida pelo peso:": "Moisture measured by weight:",
  "Umidade estimada:": "Estimated moisture:",
  ". Fim previsto:": ". Predicted end:",
  "este ar não chega à meta (veja Lotes)": "this air will not reach the target (see Batches)",
  "já na meta: confira com o medidor de umidade": "already at target: check with the moisture meter",
  "(estimado sem balança).": "(estimated without a scale).",
  "Ligado. Com o secador quente demais, o próprio aparelho liga o ventilador e não deixa desligar até esfriar.": "On. If the dryer gets too hot, the device itself turns the fan on and keeps it on until it cools down.",
  "Desligado. Com o secador quente demais, o próprio aparelho liga o ventilador e não deixa desligar até esfriar.": "Off. If the dryer gets too hot, the device itself turns the fan on and does not let it turn off until it cools down.",
  "Abaixo, um secador de exemplo (café). Ligue o secador pelo MQTT ou pelo Wi-Fi (linha TIPO:SEC) para ver os dados reais.": "Below, an example dryer (coffee). Connect the dryer through MQTT or Wi-Fi (TIPO:SEC line) to see the real data.",
  "Um secador de café de exemplo, para conhecer a tela. Na plataforma ligada ao computador central aparecem os secadores de verdade.": "An example coffee dryer, to get to know the screen. On the platform connected to the central computer, the real dryers appear.",
  "Do medidor de umidade; vazio = valor típico do produto (verificar).": "From the moisture meter; blank = typical value for the product (to be verified).",
  "Café: 11 a 12 % base úmida para guardar.": "Coffee: 11 to 12 % wet basis for storage.",
  "kg no lote": "kg in the batch",
  "o equilíbrio fica acima da meta: mais calor ou mais ar": "equilibrium is above the target: more heat or more air",
  "Poucas pesagens ainda (o ajuste pede 3 ou mais pontos): curva estimada com a velocidade típica do produto (verificar).": "Few weighings so far (the fit needs 3 or more points): curve estimated with the typical drying rate of the product (to be verified).",
  "Sem balança e sem pesagens: curva estimada com a velocidade típica do produto (verificar). Pese uma bandeja de amostra uma vez por dia para a previsão valer.": "No scale and no weighings: curve estimated with the typical drying rate of the product (to be verified). Weigh a sample tray once a day for the forecast to hold.",
  "Peso do lote inteiro, ou da bandeja de amostra vezes o número de bandejas.": "Weight of the whole batch, or of the sample tray times the number of trays.",
  "Curva de secagem": "Drying curve",
  "Peso medido (balança do secador)": "Measured weight (dryer scale)",
  "Peso medido (pesagens à mão)": "Measured weight (manual weighings)",
  "Sem pesagens": "No weighings",
  "Modelo ajustado": "Fitted model",
  "Curva estimada (sem balança)": "Estimated curve (no scale)",
  "Quando": "When",
  "Dentro (°C)": "Inside (°C)",
  "Coletor (°C)": "Collector (°C)",
  "Lá fora (°C)": "Outside (°C)",
  "Dentro (%)": "Inside (%)",
  "Lá fora (%)": "Outside (%)",
  "Peso (kg)": "Weight (kg)",
  "Sol (W/m²)": "Sun (W/m²)",
  "temperatura": "temperature",
  "umidade": "humidity",
  "peso": "weight",
  "Dados simulados de exemplo.": "Simulated example data.",
  "Leituras guardadas no computador central (as 200 mais novas de cada sensor).": "Readings stored on the central computer (the 200 latest from each sensor).",
  "Rendimento e umidade final de cada lote": "Yield and final moisture of each batch",
  "Duração": "Duration",
  "Peso inicial": "Initial weight",
  "Peso final": "Final weight",
  "Umidade final calculada pela matéria seca: confira com o medidor de umidade antes de ensacar.": "Final moisture calculated from the dry matter: check it with the moisture meter before bagging.",
  "Sem a irradiação do lugar no servidor: digite a irradiação; vazio usa 5 kWh/m² por dia.": "Without the site irradiation on the server: type the irradiation; blank uses 5 kWh/m² per day.",
  "Ou digite a irradiação no coletor abaixo.": "Or type the collector irradiation below.",
  "Da base de fatores do Carbono (ou da premissa rede.fator_emissao).": "From the Carbon emission-factor base (or the rede.fator_emissao assumption).",
  "Sem a base de fatores: digite o fator do ano.": "Without the factor base: type the factor for the year.",
  "fator da rede não informado: CO2 evitado elétrico não calculado": "grid factor not provided: avoided electric CO2 not calculated",
  "local não informado: sem a irradiação do lugar, a área do coletor não é calculada": "site not provided: without the site irradiation, the collector area is not calculated", "falta o local": "site missing",
  "Umidade no começo (%)": "Starting moisture (%)",
  "Umidade final (%)": "Final moisture (%)",
  "Coletor de ar com cobertura: tipicamente 0,3 a 0,6 (verificar com o ensaio do coletor).": "Glazed air collector: typically 0.3 to 0.6 (verify with the collector test report).",
  "Parte do calor do ar que vira evaporação; o resto sai com o ar.": "Share of the air heat that turns into evaporation; the rest leaves with the air.",
  "kg por lote": "kg per batch",
  "m³/h no ventilador": "m³/h at the fan",
  "Da base de fatores do Carbono.": "From the Carbon emission factor database.",
  "Padrão do núcleo physis/1 (verificar o ano).": "physis/1 core default (verify the year).",
  "Secador trocado": "Dryer replaced",
  "Energia por lote": "Energy per batch",
  "Energia por ano": "Energy per year",
  "CO₂ evitado por ano": "CO₂ avoided per year",
  "O ventilador gasta energia também: some a potência dele × horas no ano antes de comparar. A rede brasileira tem fator baixo; com lenha de manejo sustentável, o CO₂ da queima é biogênico e só o metano e o óxido nitroso contam.": "The fan also uses energy: add its power × hours per year before comparing. The Brazilian grid has a low emission factor; with sustainably managed firewood, combustion CO₂ is biogenic and only methane and nitrous oxide count.",
  "Contas: água = massa × (u₀ − u)/(100 − u); calor = água × 2,45 MJ/kg ÷ aproveitamento; área = calor ÷ (irradiação × 3,6 × eficiência × dias); ar = água ÷ Δw, com Δw = 1,006 × ΔT × aproveitamento ÷ 2.450; vazão = ar ÷ 1,15 kg/m³ ÷ horas. Resultado de pré-projeto: conferir com o fornecedor do coletor e do ventilador.": "Calculations: water = mass × (u₀ − u)/(100 − u); heat = water × 2.45 MJ/kg ÷ air use; area = heat ÷ (irradiation × 3.6 × efficiency × days); air = water ÷ Δw, with Δw = 1.006 × ΔT × air use ÷ 2,450; flow = air ÷ 1.15 kg/m³ ÷ hours. Pre-design result: check with the collector and fan suppliers.",
  "Como o secador funciona:": "How the dryer works:",
  "o coletor esquenta o ar, o ventilador empurra esse ar pelas bandejas e o ar leva a água do produto. Ar mais quente segura mais água; por isso o ar de dentro fica mais seco que o de fora quando o sol bate.": "the collector heats the air, the fan pushes this air through the trays and the air carries away the water from the product. Warmer air holds more water; that is why the inside air is drier than the outside air when the sun is out.",
  "Umidade do produto:": "Product moisture:",
  "sempre em base úmida (água ÷ peso total). A matéria seca não muda durante a secagem, então o peso diz a umidade: u = 100 × (1 − matéria seca ÷ peso).": "always on a wet basis (water ÷ total weight). The dry matter does not change during drying, so the weight gives the moisture: u = 100 × (1 − dry matter ÷ weight).",
  "Curva de secagem:": "Drying curve:",
  "modelo exponencial simples (de Lewis, ou de Newton): o peso cai em direção a um peso de equilíbrio, sempre mais devagar. Com 3 ou mais pesagens, a tela ajusta o modelo aos pesos (mínimos quadrados) e prevê a hora do fim. Sem pesagens, usa uma velocidade típica do produto (verificar). Na secagem real há fases (aquecimento, taxa constante, taxa decrescente) e o dia e a noite; modelos de duas fases (Page, Henderson e Pabis) podem entrar depois, com os dados do próprio secador.": "simple exponential model (Lewis, or Newton): the weight falls towards an equilibrium weight, ever more slowly. With 3 or more weighings, the screen fits the model to the weights (least squares) and predicts the end time. Without weighings, it uses a typical drying rate for the product (to be verified). Real drying has phases (warm-up, constant rate, falling rate) and day and night; two-phase models (Page, Henderson and Pabis) can be added later, using the dryer's own data.",
  "Temperaturas por produto:": "Temperatures by product:",
  "café com a massa até 40 °C para qualidade e nunca acima de 45 °C (sementes até 35 °C), guardado com 11 a 12 % de umidade, conforme as recomendações da Embrapa Café e do Consórcio Pesquisa Café; ervas medicinais e aromáticas entre 30 e 40 °C para não perder óleos essenciais; frutas em fatias entre 55 e 65 °C; cogumelos entre 40 e 55 °C. Todos marcados \"verificar\": a equipe técnica confere com a literatura do produto e com o comprador.": "coffee bean mass up to 40 °C for quality and never above 45 °C (seeds up to 35 °C), stored at 11 to 12 % moisture, following the recommendations of Embrapa Café and the Consórcio Pesquisa Café; medicinal and aromatic herbs between 30 and 40 °C so as not to lose essential oils; sliced fruit between 55 and 65 °C; mushrooms between 40 and 55 °C. All marked \"to be verified\": the technical team checks them against the product literature and with the buyer.",
  "Dimensionamento:": "Sizing:",
  "balanço de massa (água a tirar), balanço de energia (calor latente de 2,45 MJ por kg de água a cerca de 25 °C) e psicrometria simplificada (o ar esquenta no coletor e esfria ao pegar água, com calor específico de 1,006 kJ/kg·K). A eficiência do coletor de ar segue os fundamentos do ASHRAE Handbook (Fundamentals, psicrometria) e da norma ASHRAE 93 (ensaio de coletores solares); a irradiação vem da NASA POWER (média de longo prazo do lugar).": "mass balance (water to remove), energy balance (latent heat of 2.45 MJ per kg of water at about 25 °C) and simplified psychrometrics (the air warms in the collector and cools as it picks up water, with a specific heat of 1.006 kJ/kg·K). The air collector efficiency follows the fundamentals of the ASHRAE Handbook (Fundamentals, psychrometrics) and the ASHRAE 93 standard (testing of solar collectors); the irradiation comes from NASA POWER (long-term average for the site).",
  "Energia e CO₂ evitados:": "Energy and CO₂ avoided:",
  "energia que um secador elétrico ou a lenha gastaria para tirar a mesma água, com a eficiência de cada um; CO₂ pela base de fatores do Carbono (rede elétrica do SIN; lenha pelos fatores do IPCC, GWP do AR5).": "energy that an electric or firewood dryer would use to remove the same water, with the efficiency of each; CO₂ from the Carbon emission factor database (SIN power grid; firewood from IPCC factors, AR5 GWP).",
  "Alertas:": "Alerts:",
  "superaquecimento pelo produto do lote; umidade de dentro acima de 80 % com o ventilador desligado; chuva prevista (Open-Meteo, já usada na plataforma) com o secador aberto; aparelho sem falar. A segurança de temperatura fica no próprio aparelho: ele liga o ventilador sozinho no limite, mesmo sem rede.": "overheating for the batch product; inside humidity above 80 % with the fan off; rain forecast (Open-Meteo, already used on the platform) with the dryer open; device offline. Temperature safety lives in the device itself: it turns the fan on by itself at the limit, even without a network.",
  "Referências para conferir (redação própria; ler o texto vigente)": "References to check (our own wording; read the current text)",
  "Embrapa Café e Consórcio Pesquisa Café — recomendações de secagem e armazenamento do café (temperatura da massa e umidade final).": "Embrapa Café and Consórcio Pesquisa Café — recommendations for drying and storing coffee (bean mass temperature and final moisture).",
  "MAPA — Instrução Normativa 8/2003 (Regulamento Técnico de Identidade e de Qualidade do café beneficiado grão cru): umidade máxima do café para comercialização — verificar a redação vigente.": "MAPA — Normative Instruction 8/2003 (Technical Regulation on the Identity and Quality of hulled raw coffee beans): maximum coffee moisture for trade — verify the current wording.",
  "ANVISA — boas práticas de fabricação para alimentos (RDC 275/2002 e RDC 216/2004) quando o produto seco for vendido; ervas medicinais com regras próprias — verificar.": "ANVISA — good manufacturing practices for food (RDC 275/2002 and RDC 216/2004) when the dried product is sold; medicinal herbs have their own rules — to be verified.",
  "ASHRAE Handbook — Fundamentals (psicrometria) e ASHRAE 93 (método de ensaio de coletores solares); Duffie e Beckman, Solar Engineering of Thermal Processes (coletores de ar).": "ASHRAE Handbook — Fundamentals (psychrometrics) and ASHRAE 93 (test method for solar collectors); Duffie and Beckman, Solar Engineering of Thermal Processes (air collectors).",
  "Literatura de secagem solar de produtos agrícolas (FAO e manuais de extensão rural) para a eficiência de secadores solares de ar forçado — tipicamente de 10 a 30 % no conjunto.": "Literature on solar drying of agricultural products (FAO and rural extension manuals) for the efficiency of forced-air solar dryers — typically 10 to 30 % overall.",
  "Ventilador ligado (exemplo).": "Fan on (example).",
  "Ventilador desligado (exemplo).": "Fan off (example).",
  "Pedido enviado ao secador; confirma na próxima leitura.": "Request sent to the dryer; confirmed on the next reading.",
  "Não foi possível enviar agora.": "Could not send right now.",
  "Sem ligação com o computador central.": "No connection to the central computer.",
  "Informe o peso no começo.": "Enter the starting weight.",
  "A umidade final tem de ser menor que a do começo (as duas entre 0 e 100 %).": "The final moisture must be lower than the starting moisture (both between 0 and 100 %).",
  "Lote registrado.": "Batch registered.",
  "café (cereja ou pergaminho)": "coffee (cherry or parchment)",
  "ervas e folhas (medicinais, aromáticas)": "herbs and leaves (medicinal, aromatic)",
  "frutas em fatias": "sliced fruit",
  "cogumelos": "mushrooms",
  "outro produto": "other product",
  "Superaquecimento": "Overheating"
};
/* regras com números (o painel lê a cópia em sistema/physis-i18n-modulos.json) */
window.SECADOR_I18N_RX = [
  ["^°C · ([\\d.,]+|—) % de umidade$", "°C · $1 % humidity"],
  ["^°C · sol ([\\d.,]+) W/m²$", "°C · sun $1 W/m²"],
  ["^Lote de agora: (.+)$", "Current batch: $1"],
  ["^Lote secando: (.+) \\(exemplo\\)$", "Batch drying: $1 (example)"],
  ["^Lote secando: (.+)$", "Batch drying: $1"],
  ["^Começou em (.+) com ([\\d.,]+|—) kg e ([\\d.,]+|—) % de umidade\\. Meta: ([\\d.,]+|—) % \\(([\\d.,]+|—) kg\\)\\.$", "Started on $1 with $2 kg at $3 % moisture. Target: $4 % ($5 kg)."],
  ["^Superaquecimento: ([\\d.,]+) °C dentro do secador, acima de ([\\d.,]+) °C para (.+)\\.$", "Overheating: $1 °C inside the dryer, above $2 °C for $3."],
  ["^Umidade alta dentro do secador \\(([\\d.,]+) %\\) com o ventilador desligado\\.$", "High humidity inside the dryer ($1 %) with the fan off."],
  ["^Secador sem falar há ([\\d.,]+) min: confira a energia e a rede\\.$", "Dryer offline for $1 min: check the power and the network."],
  ["^Nó (\\d+)$", "Node $1"],
  ["^em (.+) desde o começo$", "$1 after the start"],
  ["^([\\d.,]+) dias$", "$1 days"],
  ["^% por hora do que falta \\(k = ([\\d.,]+) 1/h\\)$", "% per hour of the remaining water (k = $1 1/h)"],
  ["^Modelo ajustado a (\\d+) pesagens: peso de equilíbrio ([\\d.,]+) kg\\.$", "Model fitted to $1 weighings: equilibrium weight $2 kg."],
  ["^meta ([\\d.,]+) kg$", "target $1 kg"],
  ["^(.+): de ([\\d.,−—-]+) a ([\\d.,−—-]+) (°C|%|kg)$", "$1: from $2 to $3 $4"],
  ["^máximo ([\\d.,]+) °C$", "maximum $1 °C"],
  ["^Sem dados para (.+) ainda\\.$", "No data for $1 yet."],
  ["^Ver os números \\((.+)\\)$", "See the numbers ($1)"],
  ["^(.+): as 12 leituras mais novas$", "$1: the 12 latest readings"],
  ["^Irradiação do lugar \\(NASA POWER, média de longo prazo\\): de ([\\d.,]+) a ([\\d.,]+) kWh/m² por dia\\. Campo vazio usa o mês mais fraco\\.$", "Site irradiation (NASA POWER, long-term average): from $1 to $2 kWh/m² per day. A blank field uses the weakest month."],
  ["^Irradiação do lugar \\(NASA POWER, média de longo prazo\\): de ([\\d.,]+) a ([\\d.,]+) kWh/m² por dia\\. Campo vazio usa o mês escolhido\\.$", "Site irradiation (NASA POWER, long-term average): from $1 to $2 kWh/m² per day. A blank field uses the chosen month."],
  ["^MJ por lote \\(([\\d.,]+) kWh\\)$", "MJ per batch ($1 kWh)"],
  ["^Energia e CO₂ que o sol evita por ano \\(([\\d.,]+) lotes\\)$", "Energy and CO₂ the sun avoids per year ($1 batches)"],
  ["^([\\d.,]+|—) kg de lenha$", "$1 kg of firewood"],
  ["^Lote terminado: rendimento de ([\\d.,]+|—) %\\.$", "Batch finished: yield of $1 %."]
];

window.SECADOR = { PRODUTOS, UMIDADE_INTERNA_ALTA, materiaSeca, pesoNaUmidade, aguaARemover, umidadeDoPeso, rendimento, ajustar, pesoPrevisto, horasAte,
  modeloEstimado, previsaoLote, dimensionar, alertas, demoSerie, CALOR_LATENTE_MJ_KG, CP_AR_KJ_KG_K, RHO_AR, fatorRedePadrao, linhaExemplo: "ID:41,TIPO:SEC,TI:38.5,UI:42.0,TE:27.1,UE:70.0,TC:52.3,VENT:1,PESO:84.20,IRR:820,BAT:3.95,TS:1794600000" };
window.telaSecador = telaSecador;   /* global: a plataforma chama telaSecador() na hora de desenhar */
})();
