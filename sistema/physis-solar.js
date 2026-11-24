/* physis-solar.js — aba Energia solar com a conta revista: perdas uma a uma, PR calculado (não mais 0,78 fixo),
   inversor (relação CC/CA), strings e janela de MPPT, energia mês a mês com a irradiação e a temperatura da base
   aberta, degradação e retorno pelo analiseInvest da plataforma.
   Contrato com a plataforma: define telaSolar() (aba inteira, com o único título h1), window.SOLAR.calcular(p)
   (função pura, testável; espelho Python em physis-hub/tests/test_solar.py) e window.SOLAR.compat(), que devolve
   os mesmos campos do solarCalc() antigo (kwp, ger, rend, H, invest, econ, placas, area, bat…) para o Carbono,
   os Custos e o ranking de investimentos continuarem iguais.
   Globais usadas na hora de desenhar: esc, n2, numBr, brl, el, ui, desenhar; se existirem: calcLer, calcGravar,
   carregarGisSolar, mapaCalorSolar, carregarGis, solMensal, latDoLugar, carbCalc, carbLer, analiseInvest.
   Equipamentos: lê a base <script id="base-equipamentos"> (sistema/physis-equipamentos.json) se estiver embutida;
   senão usa as classes genéricas abaixo. Valores elétricos de módulo e de inversor marcados "verificar":
   são classes típicas de folha de dados, não um modelo comercial. Estado: calcLer("solar") (chaves antigas mantidas). */
(function () {
"use strict";

const DIAS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
/* módulos: classes típicas de folha de dados (verificar com o modelo escolhido) */
const MODULOS = [
  { id:"fv-perc-144", nome:"Mono PERC 144 meias-células ≈ 550 W (genérico, verificar)", pmax:550, voc:49.9, vmp:41.9, isc:14.0, imp:13.13, beta_voc:-0.27, gamma_pmax:-0.35, noct:45, area:2.58, deg:0.55 },
  { id:"fv-perc-108", nome:"Mono PERC 108 meias-células ≈ 415 W (genérico, verificar)", pmax:415, voc:37.9, vmp:31.6, isc:13.9, imp:13.13, beta_voc:-0.27, gamma_pmax:-0.35, noct:45, area:1.94, deg:0.55 },
  { id:"fv-topcon-144", nome:"TOPCon 144 meias-células ≈ 580 W (genérico, verificar)", pmax:580, voc:51.5, vmp:43.0, isc:14.3, imp:13.49, beta_voc:-0.25, gamma_pmax:-0.29, noct:45, area:2.58, deg:0.40 }];
/* inversores: classes típicas (verificar a tensão máxima de entrada, a janela e a corrente do MPPT no modelo escolhido) */
const INVERSORES = [
  { id:"inv-string-mono-3-6", nome:"String monofásico 3 a 6 kW, 2 MPPT (genérico, verificar)", pca:5, eta:0.973, vdc_max:600, mppt_min:80, mppt_max:550, n_mppt:2, imax_mppt:16 },
  { id:"inv-string-mono-8-10", nome:"String monofásico 8 a 10 kW (genérico, verificar)", pca:10, eta:0.975, vdc_max:600, mppt_min:80, mppt_max:550, n_mppt:3, imax_mppt:16 },
  { id:"inv-string-tri-15-30", nome:"String trifásico 15 a 30 kW (genérico, verificar)", pca:25, eta:0.980, vdc_max:1100, mppt_min:180, mppt_max:1000, n_mppt:3, imax_mppt:32 }];
/* perdas típicas de partida (%, ajustar ao projeto): faixas usuais de literatura e de simuladores de mercado */
const PERDAS_PADRAO = { sombra:0, sujeira:2, mismatch:1.5, cabos_cc:1.5, cabos_ca:1 };

/* base de equipamentos da plataforma: só os campos que ela tem (coeficiente de Pmax, degradação, η, MPPT) */
function base() { try { const s = document.getElementById("base-equipamentos"); const j = s ? JSON.parse(s.textContent) : (window.EQUIPAMENTOS || null); return j && Array.isArray(j.itens) ? j.itens : []; } catch (e) { return []; } }
function modulos() { const b = base(); return MODULOS.map(m => { const x = b.find(i => i.id === m.id); if (!x) return m;
  return Object.assign({}, m, { gamma_pmax:x.coef_temperatura_pmax_pct_por_C != null ? x.coef_temperatura_pmax_pct_por_C : m.gamma_pmax, deg:x.degradacao_anual_pct != null ? x.degradacao_anual_pct : m.deg, daBase:true }); }); }
function inversores() { const b = base(); return INVERSORES.map(v => { const x = b.find(i => i.id === v.id); if (!x) return v; const r = Object.assign({}, v, { daBase:true });
  if (x.eficiencia && x.eficiencia.tipico) r.eta = x.eficiencia.tipico / 100;
  const m = String(x.faixa_mppt || "").match(/(\d+)\s*[–-]\s*(\d+)/); if (m) { r.mppt_min = +m[1]; r.mppt_max = +m[2]; } return r; }); }

/* ════════ Contas (espelho em tests/test_solar.py) ════════ */
/* temperatura da célula pelo método NOCT: Tc = Ta + (NOCT − 20)/800 · G */
const tCelula = (ta, noct, g) => ta + (noct - 20) / 800 * g;
/* fator de temperatura da potência: 1 + γ/100 · (Tc − 25) */
const fTemp = (tc, gamma) => 1 + gamma / 100 * (tc - 25);
function strings(p) { const m = p.modulo, v = p.inversor, b = m.beta_voc / 100, av = [];
  const tcMax = tCelula(p.tmax, m.noct, 1000), vocFrio = m.voc * (1 + b * (p.tmin - 25)), vmpFrio = m.vmp * (1 + b * (p.tmin - 25)), vmpQuente = m.vmp * (1 + b * (tcMax - 25));
  const nMax = Math.floor(v.vdc_max / vocFrio), nMaxMppt = Math.floor(v.mppt_max / vmpFrio), nMin = Math.ceil(v.mppt_min / vmpQuente), nSup = Math.min(nMax, nMaxMppt);
  const N = p.placas || 0; let s = 0, n = 0, porMppt = 0;
  if (nSup >= nMin && N > 0) { s = Math.ceil(N / nSup); n = Math.max(nMin, Math.ceil(N / s));
    /* prefere strings iguais que somem exatamente N (menos strings primeiro) */
    for (let k = s; k * nMin <= N; k++) { if (N % k === 0 && N / k <= nSup) { s = k; n = N / k; break; } }
    porMppt = Math.ceil(s / Math.max(1, v.n_mppt)); }
  if (nSup < nMin) av.push("Nenhum número de módulos em série cabe na janela do MPPT com estas temperaturas: troque o inversor ou o módulo.");
  if (porMppt && m.isc * porMppt > v.imax_mppt) av.push(`Corrente de ${porMppt} strings em paralelo (${(m.isc * porMppt).toFixed(1)} A de curto-circuito) passa da corrente do MPPT (${v.imax_mppt} A): use mais MPPTs ou outro inversor.`);
  if (s && s * n !== N) av.push(`Para fechar strings iguais, ${s} × ${n} = ${s * n} módulos (em vez de ${N}).`);
  return { tc_max:tcMax, voc_frio:vocFrio, vmp_frio:vmpFrio, vmp_quente:vmpQuente, n_max:nMax, n_max_mppt:nMaxMppt, n_min:nMin, n_sup:nSup, strings:s, em_serie:n, por_mppt:porMppt,
    voc_string:n * vocFrio, ok:nSup >= nMin && !(porMppt && m.isc * porMppt > v.imax_mppt), avisos:av }; }

/* p: H[12] kWh/m²·dia (horizontal), T[12] °C, fator_plano (número ou 12 valores, um por mês: plano inclinado pelo modelo
   isotrópico de PhysisCalc.fatorPlano), consumo kWh/ano, cobertura (0–1), kwp (sem consumo),
   modulo, inversor, perdas {% …}, eta_inv, g_op W/m², deg %/ano, vida, razao (CC/CA alvo), pca (kW, opcional),
   tmin, tmax (°C ambiente), tarifa, custo_kwp, taxa, infl;
   Lei 14.300: autoconsumo (0–1), fio_b (R$/kWh), ano (1º ano de geração), regra ("lei14300" | "antiga"), disponibilidade (kWh/mês) */
function calcular(p) { p = p || {}; const H = p.H || [], T = Array.isArray(p.T) && p.T.length === 12 ? p.T : DIAS.map(() => 25);
  const fpM = Array.isArray(p.fator_plano) && p.fator_plano.length === 12 ? p.fator_plano : DIAS.map(() => (p.fator_plano > 0 ? p.fator_plano : 1));
  const m = p.modulo || MODULOS[0], v = p.inversor || INVERSORES[0], L = Object.assign({}, PERDAS_PADRAO, p.perdas || {}), eta = p.eta_inv > 0 ? p.eta_inv : v.eta, g = p.g_op > 0 ? p.g_op : 800;
  const fixo = (1 - L.sombra / 100) * (1 - L.sujeira / 100) * (1 - L.mismatch / 100) * (1 - L.cabos_cc / 100) * eta * (1 - L.cabos_ca / 100);
  const meses = H.map((h, i) => { const tc = tCelula(T[i], m.noct, g), ft = fTemp(tc, m.gamma_pmax); return { H:h, T:T[i], tc, f_temp:ft, pr:fixo * ft, fp:fpM[i], kwh_kwp:h * fpM[i] * DIAS[i] * fixo * ft }; });
  const rend = meses.reduce((s, x) => s + x.kwh_kwp, 0), hPlano = H.reduce((s, h, i) => s + h * fpM[i] * DIAS[i], 0), pr = hPlano ? rend / hPlano : null;
  const alvo = p.consumo > 0 ? p.consumo * (p.cobertura == null ? 1 : p.cobertura) : null;
  const kwpNec = p.kwp_fixo > 0 ? p.kwp_fixo : alvo != null && rend > 0 ? alvo / rend : (p.kwp || 0), placas = Math.ceil(kwpNec * 1000 / m.pmax - 1e-9), kwp = placas * m.pmax / 1000;
  const ger = kwp * rend, deg = (p.deg != null ? p.deg : m.deg) / 100, vida = p.vida || 25;
  let somaVida = 0; for (let a = 0; a < vida; a++) somaVida += ger * Math.pow(1 - deg, a);
  /* cascata de perdas (kWh por ano, na ordem aplicada) */
  const bruta = kwp * hPlano, fTempMedio = hPlano ? meses.reduce((s, x, i) => s + x.H * fpM[i] * DIAS[i] * x.f_temp, 0) / hPlano : 1;
  const etapas = [["Sombreamento", 1 - L.sombra / 100], ["Sujeira", 1 - L.sujeira / 100], ["Temperatura", fTempMedio], ["Descasamento (mismatch)", 1 - L.mismatch / 100],
    ["Cabos CC", 1 - L.cabos_cc / 100], ["Inversor", eta], ["Cabos CA", 1 - L.cabos_ca / 100]];
  let e = bruta; const cascata = etapas.map(([nome, f]) => { const perda = e * (1 - f); e *= f; return { nome, pct:(1 - f) * 100, kwh:perda }; });
  const pca = p.pca > 0 ? p.pca : (kwp && p.razao > 0 ? kwp / p.razao : (kwp ? kwp / 1.2 : 0)), razao = pca ? kwp / pca : null, avisos = [];
  if (razao != null && (razao < 1.1 || razao > 1.35)) avisos.push(`Relação CC/CA de ${razao.toFixed(2)}: fora da faixa usual de 1,10 a 1,35 (abaixo, o inversor fica ocioso; acima, corta a geração no pico).`);
  const st = strings({ modulo:m, inversor:v, placas, tmin:p.tmin != null ? p.tmin : 0, tmax:p.tmax != null ? p.tmax : 40 });
  /* economia: com as contas comuns, separa autoconsumo e energia injetada (Lei 14.300, art. 27: Fio B da injetada) e
     mantém o custo de disponibilidade; sem elas (ou sem tarifa), a conta antiga geração × tarifa */
  const PC = typeof PhysisCalc !== "undefined" ? PhysisCalc : (typeof window !== "undefined" ? window.PhysisCalc : null);
  const gerMes = meses.map(x => x.kwh_kwp * kwp), ano0 = p.ano > 0 ? p.ano : new Date().getFullYear();
  const lei = p.tarifa > 0 && PC ? anos => PC.economiaSolar({ ger_meses:gerMes, consumo_ano:p.consumo, autoconsumo:p.autoconsumo == null ? 1 : p.autoconsumo, tarifa:p.tarifa,
    fio_b:p.fio_b, ano:anos, regra:p.regra, disponibilidade:p.disponibilidade }) : null;
  const ec = lei ? lei(ano0) : null, porAno = lei ? [0, 1, 2, 3, 4, 5, 6].map(k => { const x = lei(ano0 + k); return { ano:ano0 + k, pct:x.pct_fio_b, economia:x.economia }; }) : [];
  const invest = p.custo_kwp > 0 ? kwp * p.custo_kwp : null, econ = ec ? ec.economia : (p.tarifa > 0 ? ger * p.tarifa : null);
  /* degradação entra como redução do reajuste: (1 + reajuste)·(1 − degradação) − 1 */
  const inflEf = ((1 + (p.infl != null ? p.infl : 4) / 100) * (1 - deg) - 1) * 100;
  const fin = invest && econ ? analise(invest, econ / 12, vida, p.taxa != null ? p.taxa : 10, inflEf) : null;
  return { meses, rend, h_plano:hPlano, pr, kwp_necessario:kwpNec, placas, kwp, area:placas * m.area, ger, ger_media_vida:somaVida / vida, deg, cascata, bruta, f_temp_medio:fTempMedio,
    pca, razao, strings:st, invest, econ, economia:ec, economia_por_ano:porAno, fator_plano:fpM, infl_efetiva:inflEf, fin, avisos:avisos.concat(st.avisos, ec ? ec.avisos : []), eta }; }
function analise(valor, ganhoMes, anos, taxa, infl) { const f = (typeof window !== "undefined" && typeof window.analiseInvest === "function") ? window.analiseInvest : (typeof analiseInvest === "function" ? analiseInvest : null);
  return f ? f(valor, ganhoMes, anos, taxa, infl) : null; }

/* ════════ Estado e dados do lugar ════════ */
function ler() { if (typeof calcLer === "function") return calcLer("solar") || {}; try { return JSON.parse(localStorage.getItem("physis-calc-solar") || "{}") || {}; } catch (e) { return {}; } }
function gravar(o) { if (typeof calcGravar === "function") return calcGravar("solar", o); try { localStorage.setItem("physis-calc-solar", JSON.stringify(o)); } catch (e) {} }
const num = s => { if (s == null || String(s).trim() === "") return null; const v = typeof numBr === "function" ? numBr(s) : parseFloat(String(s).replace(",", ".")); return v == null || !isFinite(v) ? null : v; };
const ou = (a, b) => a == null ? b : a;
/* o local único da plataforma (localDaInstalacao: Planejador > Início > Monitoramento); sem ele, nada de ponto padrão */
function lugar(o) { const L = typeof localDaInstalacao === "function" ? localDaInstalacao() : { lat:null, lon:null }, lat = ou(num(o.lat), L.lat), lon = ou(num(o.lon), L.lon); return { lat, lon, fonte:num(o.lat) != null ? "digitado" : L.fonte }; }
function sol(o, P) { if (P.lat == null || P.lon == null) return { H:null, medido:false }; const k = P.lat.toFixed(2) + "," + P.lon.toFixed(2);
  if (typeof carregarGisSolar === "function") carregarGisSolar(P.lat, P.lon);
  const g = ui.gisSolar, medido = g && g.ponto && ui.gisSolarKey === k ? g.ponto.meses : null;
  if (medido) return { H:medido, medido:true };
  if (typeof solMensal === "function") return { H:solMensal(P.lat, ou(num(o.kt), 0.5)), medido:false };
  return { H:null, medido:false }; }
function temperatura(P) { if (P.lat == null) return null; if (typeof carregarGis === "function") { try { carregarGis("temperatura", P.lat, P.lon); } catch (e) {} }
  const g = ui.gis && ui.gis.temperatura; return g && g.ponto && Array.isArray(g.ponto.meses) ? g.ponto.meses : null; }

/* telhado gravado pelo Planejador (mesmo navegador): inclinação e orientação da água escolhida para as placas */
function telhadoPlanejador() { try { const t = JSON.parse(localStorage.getItem("physis-calc-telhado") || "null"); return t && t.incl != null ? t : null; } catch (e) { return null; } }
const PCx = () => (typeof PhysisCalc !== "undefined" ? PhysisCalc : null);
/* planta solar enviada (physis-calc-planta-solar, da sub-aba Planta solar): quando existe e não foi desligada, o
   dimensionamento usa o kWp, o módulo e o plano da planta, e a geração desta aba é a única mostrada */
function plantaSalva() { try { const p = JSON.parse(localStorage.getItem("physis-calc-planta-solar") || "null"); return p && p.kwp > 0 ? p : null; } catch (e) { return null; } }
function entradas(o) { const P = lugar(o), S = sol(o, P), Tm = temperatura(P), mods = modulos(), invs = inversores();
  const PL = o.usar_planta === "0" ? null : plantaSalva();
  const m0 = mods.find(x => x.id === o.mod) || (PL && PL.modulo && mods.find(x => x.id === PL.modulo.id)) || mods[0], v0 = invs.find(x => x.id === o.inv) || invs[0];
  const m = Object.assign({}, m0, { pmax:ou(num(o.placa), m0.pmax), area:ou(num(o.m2placa), m0.area), voc:ou(num(o.voc), m0.voc), vmp:ou(num(o.vmp), m0.vmp), isc:ou(num(o.isc), m0.isc),
    beta_voc:ou(num(o.beta), m0.beta_voc), gamma_pmax:ou(num(o.gamma), m0.gamma_pmax), noct:ou(num(o.noct), m0.noct) });
  const v = Object.assign({}, v0, { vdc_max:ou(num(o.vdc_max), v0.vdc_max), mppt_min:ou(num(o.mppt_min), v0.mppt_min), mppt_max:ou(num(o.mppt_max), v0.mppt_max), n_mppt:ou(num(o.n_mppt), v0.n_mppt), imax_mppt:ou(num(o.imax_mppt), v0.imax_mppt) });
  let consumo = num(o.consumo); if (consumo == null) { try { if (typeof carbCalc === "function" && typeof carbLer === "function") { const ca = carbCalc(carbLer()); if (ca && ca.kwh != null) consumo = ca.kwh; } } catch (e) {} }
  const tAmb = num(o.tamb), T = tAmb != null ? DIAS.map(() => tAmb) : Tm;
  /* plano das placas: inclinação e orientação digitadas, senão as do telhado do Planejador, senão o fator digitado (1 = horizontal) */
  const tp = telhadoPlanejador(), incl = ou(num(o.incl), PL && PL.incl != null ? +PL.incl : tp ? +tp.incl : null), azim = ou(num(o.azim), PL && PL.azim != null ? +PL.azim : tp ? +tp.azim : 0), Hh = S.H || DIAS.map(() => 0);
  const pl = PL && num(o.incl) == null && Array.isArray(PL.fator_plano_mensal) && PL.fator_plano_mensal.length === 12 ? { fator:PL.fator_plano_mensal, anual:PL.fator_plano_mensal.reduce((s, f, i) => s + f * Hh[i] * DIAS[i], 0) / Math.max(1e-9, Hh.reduce((s, h, i) => s + h * DIAS[i], 0)), planta:true }
    : incl != null && PCx() ? PCx().fatorPlano(Hh, P.lat, incl, azim) : null;
  const disp = PCx() ? PCx().premissa("tarifa.custo_disponibilidade") : null, lig = o.ligacao || "bifasico";
  return { P, S, m, v, mods, invs, temBase:base().length > 0, planta:PL, temPlanta:!!plantaSalva(), Tfonte:tAmb != null ? "digitada" : Tm ? "base" : "padrão",
    plano:{ incl, azim, fonte:num(o.incl) != null ? "digitada" : PL ? "Planta solar" : tp ? "Planejador" : null, fator:pl, telhado:tp },
    p:{ H:Hh, T, fator_plano:pl ? pl.fator : ou(num(o.fp), 1),
      autoconsumo:ou(num(o.autoconsumo), 100) / 100, fio_b:num(o.fio_b), ano:ou(num(o.ano), new Date().getFullYear()), regra:o.regra || "lei14300",
      disponibilidade:disp && disp[lig] != null ? disp[lig] : null, consumo:consumo || 0, cobertura:ou(num(o.cobertura), 100) / 100, kwp:num(o.kwp) || 0, kwp_fixo:PL ? +PL.kwp : 0, modulo:m, inversor:v,
      perdas:{ sombra:ou(num(o.sombra), PERDAS_PADRAO.sombra), sujeira:ou(num(o.sujeira), PERDAS_PADRAO.sujeira), mismatch:ou(num(o.mismatch), PERDAS_PADRAO.mismatch), cabos_cc:ou(num(o.cabos_cc), PERDAS_PADRAO.cabos_cc), cabos_ca:ou(num(o.cabos_ca), PERDAS_PADRAO.cabos_ca) },
      eta_inv:num(o.eta_inv) != null ? num(o.eta_inv) / 100 : v.eta, g_op:ou(num(o.g_op), 800), deg:ou(num(o.deg), m.deg), vida:ou(num(o.vida), 25), razao:ou(num(o.razao), 1.2), pca:num(o.pca),
      tmin:ou(num(o.tmin), 0), tmax:ou(num(o.tmax), 40), tarifa:num(o.tarifa), custo_kwp:num(o.custo_kwp), taxa:num(o.taxa), infl:num(o.infl) } }; }

/* campos do solarCalc() antigo, para o resto da plataforma */
/* banco de baterias: regra única (PhysisCalc.bateria = consumo diário × horas ÷ 24 ÷ DoD ÷ rendimento, premissas bateria.*) */
const bateriaKwh = (consumoAno, autH, dod) => { const pc = PCx(); return autH > 0 && consumoAno > 0 ? (pc ? pc.bateria(consumoAno / 365, autH, dod) : consumoAno / 365 / 24 * autH / dod / 0.95) : 0; };
function compat() { const o = ler(), E = entradas(o);
  if (E.P.lat == null) return { semLocal:true, lat:null, kt:0.5, pr:null, consumo:E.p.consumo, kwp:0, placas:0, area:0, ger:0, rend:0, H:[], hpsMin:0, tarifa:E.p.tarifa, invest:null, econ:null, bat:0, autH:0, dod:0.9, medido:false };
  const R0 = null, R = calcular(E.p), autH = ou(num(o.autonomia), 0), dod = { litio:0.9, agm:0.5 }[o.bateria || "litio"] || 0.9, consumo = E.p.consumo;
  return { lat:E.P.lat, kt:ou(num(o.kt), 0.5), pr:R.pr, consumo, kwp:R.kwp, placas:R.placas, area:R.area, ger:R.ger, rend:R.rend, H:E.p.H, hpsMin:Math.min.apply(null, E.p.H),
    tarifa:E.p.tarifa, invest:R.invest, econ:R.econ, bat:bateriaKwh(consumo, autH, dod), autH, dod, medido:E.S.medido }; }

/* ════════ Desenho ════════ */
const f1 = (x, c) => x == null || !isFinite(x) ? "—" : n2(x, c == null ? 1 : c);
const campo = (o, k, rot, ph, ajuda) => `<div><label for="so-${k}">${rot}</label><input id="so-${k}" type="text" inputmode="decimal" data-sol-k="${k}" value="${esc(o[k] == null ? "" : o[k])}" placeholder="${esc(ph)}" style="width:100%"${ajuda ? ` aria-describedby="so-${k}-a"` : ""}>${ajuda ? `<span id="so-${k}-a" class="t2 pq">${ajuda}</span>` : ""}</div>`;
const lista = (o, k, rot, ops, padrao) => { const a = o[k] == null || o[k] === "" ? padrao : o[k];
  return `<div><label for="so-${k}">${rot}</label><select id="so-${k}" data-sol-k="${k}" style="width:100%">${ops.map(([x, n]) => `<option value="${esc(x)}" ${String(a) === String(x) ? "selected" : ""}>${esc(n)}</option>`).join("")}</select></div>`; };
const cartao = (id, tit, numero, un, extra) => `<section class="cartao" aria-labelledby="h-${id}"><h3 id="h-${id}" class="t3">${tit}</h3><span class="numero">${numero}</span><span class="t2">${un}</span>${extra || ""}</section>`;
function hbar(titulo, itens, un) { const W = 360, lh = 24, H = itens.length * lh + 6, Lx = 150, mx = Math.max(1e-9, ...itens.map(x => x.v));
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px" role="img" aria-label="${esc(titulo)}; os números estão na tabela">${itens.map((x, i) => { const w = (W - Lx - 60) * x.v / mx, y = 3 + i * lh;
    return `<text x="${Lx - 6}" y="${y + 14}" font-size="11" text-anchor="end" fill="#1B1F23">${esc(x.rot)}</text><rect x="${Lx}" y="${y + 3}" width="${Math.max(0, w).toFixed(1)}" height="15" fill="#A85432"><title>${esc(x.rot)}: ${f1(x.v, 0)} ${esc(un)}</title></rect><text x="${(Lx + w + 4).toFixed(1)}" y="${y + 14}" font-size="11" fill="#4A4F44">${f1(x.v, 0)}</text>`; }).join("")}</svg>`; }

function metodologia() { return `<details class="cartao"><summary><h2 style="display:inline">Metodologia e normas</h2></summary>
  <ul><li><strong>Sol do lugar:</strong> irradiação global horizontal média de cada mês (NASA POWER, climatologia de longo prazo, guardada no servidor); sem a base, estimativa pela latitude (Duffie e Beckman) com o índice de claridade.</li>
  <li><strong>Sol no plano das placas:</strong> modelo isotrópico (Liu e Jordan, Duffie e Beckman): a parte direta do sol é levada ao plano mês a mês pela geometria do dia médio; a parte difusa vem da correlação mensal de Erbs com o índice de claridade; o reflexo do chão usa o albedo da base de premissas. Inclinação e orientação digitadas ou do telhado do Planejador; plano deitado dá o mesmo resultado do chão.</li>
  <li><strong>Economia (Lei 14.300):</strong> mês a mês, a energia usada na hora vale a tarifa cheia; a injetada vira crédito que abate o consumo da rede, mas paga a parte do Fio B do ano pela escala do art. 27 (percentuais na base de premissas, a conferir); a conta nunca fica abaixo do custo de disponibilidade do tipo de ligação (REN ANEEL 1.000/2021). Créditos que sobram não viram dinheiro.</li>
  <li><strong>Bateria:</strong> regra única da Physis (a mesma do SustainKit): consumo diário × horas ÷ 24 ÷ profundidade de descarga ÷ rendimento de ida e volta (premissas bateria.dod e bateria.rendimento).</li>
  <li><strong>Temperatura:</strong> célula pelo método NOCT, Tc = Ta + (NOCT − 20)/800 · G, com G de operação editável; perda = γ(Pmax) · (Tc − 25 °C). Ta vem da temperatura média mensal da base (inclui a noite: o valor tende a subestimar o calor do meio-dia; a irradiância de operação de 800 W/m² compensa em parte).</li>
  <li><strong>Perdas:</strong> sombreamento, sujeira, descasamento, cabos CC, inversor (eficiência europeia, ponderada) e cabos CA, multiplicadas em cascata. PR = energia entregue ÷ (kWp × irradiação no plano). Os padrões são valores típicos de partida; o projeto troca pelos seus.</li>
  <li><strong>Inversor:</strong> relação CC/CA usual de 1,10 a 1,35; o corte no pico (clipping) acima disso não entra na conta mensal.</li>
  <li><strong>Strings e MPPT:</strong> Voc na mínima (coeficiente β de Voc) contra a tensão máxima de entrada; Vmp na mínima contra o topo da janela; Vmp na célula mais quente (máxima ambiente + NOCT a 1.000 W/m²) contra o piso da janela; corrente de curto-circuito das strings em paralelo contra a do MPPT. Vmp usa o mesmo coeficiente de Voc (aproximação usual; confira o coeficiente de Vmp da folha de dados se houver).</li>
  <li><strong>Degradação e retorno:</strong> geração cai a cada ano pela taxa do módulo; no retorno (analiseInvest, o mesmo da Gestão) a degradação reduz o reajuste da tarifa: (1 + reajuste)·(1 − degradação) − 1.</li></ul>
  <p class="t2"><strong>Normas e regras</strong> (citadas pelo número; ler o texto vigente):</p><ul>
  <li>ABNT NBR 16690:2019 — projeto elétrico do arranjo fotovoltaico: tensão máxima do arranjo com a temperatura mínima, dimensionamento de condutores e proteções pela corrente de curto-circuito, seccionamento e aterramento.</li>
  <li>ABNT NBR 16149:2013 — características da interface de conexão com a rede (tensão, frequência, fator de potência, ilhamento); ABNT NBR 16150:2013 — ensaios de conformidade dessa interface; ABNT NBR IEC 62116 — anti-ilhamento.</li>
  <li>ABNT NBR 16274:2014 — comissionamento, ensaios e documentação do sistema conectado (inspeção, curva I-V, isolamento, registro entregue ao cliente).</li>
  <li>ABNT NBR 5410 (baixa tensão) e NBR 5419 (proteção contra descargas atmosféricas) no lado CA e na estrutura.</li>
  <li>Lei 14.300/2022 — marco da micro e minigeração distribuída e do sistema de compensação de energia (inclusive a transição da cobrança pelo uso da rede); ANEEL REN 1.059/2023 — regras de acesso, prazos e faturamento que regulamentam a lei; PRODIST Módulo 3 — procedimentos de acesso da distribuidora.</li>
  <li>Inmetro — registro de módulos e inversores (conferir a portaria vigente).</li></ul></details>`; }

const TITULO_SOLAR = "<h1>Energia solar</h1>";   /* um só título (com ou sem o local) */
const SUBS_SOLAR = [["calculo", "Dimensionamento"], ["planta", "Planta solar (BIM)"], ["fornecedores", "Fornecedores na sua região"]];
/* sub-aba: padrão Dimensionamento; a escolha vale só nesta sessão do navegador (sessionStorage) */
function subSolar() { let s = null; try { s = sessionStorage.getItem("physis-solar-sub"); } catch (e) {} if (typeof ui !== "undefined" && ui && ui.solSub) s = ui.solSub; return SUBS_SOLAR.some(x => x[0] === s) ? s : "calculo"; }
function chipsSolar() { const at = subSolar();
  return `<div class="chips" role="group" aria-label="Partes da Energia solar">${SUBS_SOLAR.map(([k, n]) => `<button type="button" id="so-sub-${k}" data-sol-sub="${k}" aria-pressed="${k === at}">${n}${k === "planta" ? ' <span class="selo at">Em desenvolvimento</span>' : ""}</button>`).join("")}</div>`; }
function telaSolar() { if (subSolar() === "fornecedores") return TITULO_SOLAR + chipsSolar() + (window.FORNECEDORES ? FORNECEDORES.htmlSolar() : `<p class="faixa in" role="status">Fornecedores: módulo não instalado.</p>`);
  if (subSolar() === "planta") return TITULO_SOLAR + chipsSolar() + (window.PhysisMapeamento && PhysisMapeamento.telaPlantaSolar ? PhysisMapeamento.telaPlantaSolar() : `<p class="faixa in" role="status">A planta solar vem do módulo Mapeamento, que não está nesta instalação.</p>`);
  const o = ler(), E = entradas(o);
  if (E.P.lat == null) return `${TITULO_SOLAR}${chipsSolar()}${typeof avisoSemLocal === "function" ? avisoSemLocal() : '<p class="faixa at" role="status">Local não informado — preencha na página Início.</p>'}<p class="t2">Sem o local, a solar não calcula o sol do lugar nem a geração. Também dá para digitar latitude e longitude só para esta tela:</p><div class="precos">${campo(o, "lat", "Latitude", "ex.: -22,505")}${campo(o, "lon", "Longitude", "ex.: -43,183")}</div>${metodologia()}`;
  const R = calcular(E.p), M = E.m, V = E.v;
  const fontS = E.S.medido ? "Irradiação medida por satélite (NASA POWER, média de longo prazo), guardada no servidor." : E.S.H ? "Estimativa pela latitude (a base ainda não respondeu para este ponto)." : "Sem dado de sol: informe a localização.";
  const fontT = { base:"temperatura média mensal da base aberta (NASA POWER)", digitada:"temperatura digitada", "padrão":"25 °C (sem a base; digite a média do lugar)" }[E.Tfonte];
  const ent = `<section class="cartao" aria-labelledby="h-so-ent"><h2 id="h-so-ent">Dados do lugar e do consumo</h2><div class="precos">
    ${campo(o, "consumo", "Consumo de eletricidade (kWh por ano)", E.p.consumo ? n2(E.p.consumo, 0) : "ex.: 24000", "Vazio = o do Carbono ou das contas do Início.")}${campo(o, "cobertura", "Quanto do consumo a solar deve cobrir (%)", "100")}
    ${campo(o, "kwp", "Potência desejada (kWp), sem consumo", "ex.: 5")}${campo(o, "lat", "Latitude", n2(E.P.lat, 4))}${campo(o, "lon", "Longitude", n2(E.P.lon, 4))}
    ${campo(o, "kt", "Índice de claridade (só sem a base)", "0,5")}
    ${campo(o, "incl", "Inclinação das placas (°)", E.plano.telhado ? n2(+E.plano.telhado.incl, 0) + " (Planejador)" : "0 = deitadas", "Vazio = a do telhado do Planejador; sem ele, o fator abaixo.")}
    ${campo(o, "azim", "Para onde as placas apontam (°)", E.plano.telhado ? n2(+E.plano.telhado.azim, 0) + " (Planejador)" : "0 = norte", "0 norte, 90 leste, 180 sul, 270 oeste.")}
    ${E.plano.incl == null ? campo(o, "fp", "Fator do plano (sem inclinação)", "1", "1 = horizontal. Com a inclinação acima, o fator é calculado mês a mês.") : ""}
    ${campo(o, "tamb", "Temperatura ambiente média (°C)", E.Tfonte === "base" ? "da base" : "25", "Vazio = média mensal da base aberta.")}
    ${campo(o, "tmin", "Mínima histórica do lugar (°C)", "0", "Para a tensão máxima das strings; 0 °C é conservador.")}${campo(o, "tmax", "Máxima histórica do lugar (°C)", "40", "Para a tensão mínima das strings; 40 °C é conservador.")}</div>
    <p class="t2 pq">${esc(fontS)} Temperatura: ${esc(fontT)}.${E.plano.fator ? ` Plano das placas: ${f1(E.plano.incl, 0)}° de inclinação, apontando para ${f1(E.plano.azim, 0)}°${E.plano.fonte === "Planejador" ? " (telhado do Planejador)" : ""}; no ano o plano recebe ${f1(E.plano.fator.anual * 100, 0)}% do sol do chão (modelo isotrópico).` : ""}</p></section>`;
  const eq = `<section class="cartao" aria-labelledby="h-so-eq"><h2 id="h-so-eq">Módulo e inversor</h2><div class="precos">
    ${lista(o, "mod", "Módulo", E.mods.map(x => [x.id, x.nome]), E.mods[0].id)}${campo(o, "placa", "Potência do módulo (W)", n2(M.pmax, 0))}${campo(o, "m2placa", "Área do módulo (m²)", n2(M.area, 2))}
    ${campo(o, "voc", "Voc (V)", n2(M.voc, 1))}${campo(o, "vmp", "Vmp (V)", n2(M.vmp, 1))}${campo(o, "isc", "Isc (A)", n2(M.isc, 2))}
    ${campo(o, "beta", "Coeficiente de Voc (%/°C)", n2(M.beta_voc, 2))}${campo(o, "gamma", "Coeficiente de Pmax (%/°C)", n2(M.gamma_pmax, 2))}${campo(o, "noct", "NOCT (°C)", n2(M.noct, 0))}
    ${lista(o, "inv", "Inversor", E.invs.map(x => [x.id, x.nome]), E.invs[0].id)}${campo(o, "pca", "Potência CA escolhida (kW)", "vazio = kWp ÷ relação alvo")}${campo(o, "razao", "Relação CC/CA alvo", "1,2")}
    ${campo(o, "eta_inv", "Eficiência europeia do inversor (%)", n2(V.eta * 100, 1))}${campo(o, "vdc_max", "Tensão máxima de entrada (V)", n2(V.vdc_max, 0))}${campo(o, "mppt_min", "MPPT mínimo (V)", n2(V.mppt_min, 0))}
    ${campo(o, "mppt_max", "MPPT máximo (V)", n2(V.mppt_max, 0))}${campo(o, "n_mppt", "Quantidade de MPPTs", n2(V.n_mppt, 0))}${campo(o, "imax_mppt", "Corrente máxima por MPPT (A)", n2(V.imax_mppt, 0))}</div>
    <p class="t2 pq"><span class="selo at">Verificar</span> Classes genéricas de folha de dados${E.temBase ? " (coeficiente, degradação, eficiência e janela do MPPT vindos da base de equipamentos da Physis)" : ""}: troque pelos valores do modelo comprado.</p></section>`;
  const per = `<section class="cartao" aria-labelledby="h-so-per"><h2 id="h-so-per">Perdas</h2><div class="precos">
    ${campo(o, "sombra", "Sombreamento (%)", "0", "Do estudo de sombra do Planejador ou medição.")}${campo(o, "sujeira", "Sujeira (%)", "2")}${campo(o, "mismatch", "Descasamento entre módulos (%)", "1,5")}
    ${campo(o, "cabos_cc", "Cabos CC (%)", "1,5")}${campo(o, "cabos_ca", "Cabos CA (%)", "1")}${campo(o, "g_op", "Irradiância de operação para a temperatura (W/m²)", "800")}
    ${campo(o, "deg", "Degradação anual (%)", n2(M.deg, 2))}${campo(o, "vida", "Vida útil (anos)", "25")}</div><p class="t2 pq">Padrões típicos de partida; ajuste ao projeto.</p></section>`;
  const fonteSis = E.planta ? `Fonte: planta solar (${esc(E.planta.superficie && E.planta.superficie.nome || "")}), com as contas desta aba` : "Fonte: dimensionado pelo consumo (ou pela potência digitada)";
  const usar = E.temPlanta ? `<div class="precos">${lista(o, "usar_planta", "Sistema usado nas contas", [["1", "O da planta solar"], ["0", "Dimensionar pelo consumo"]], "1")}</div>` : "";
  const res = `${usar}<div class="grade">${cartao("so-kwp", "Potência", f1(R.kwp, 2), "kWp · " + R.placas + " módulos · " + f1(R.area, 0) + " m²", `<span class="t2 pq">${fonteSis}</span>`)}
    ${cartao("so-ger", "Geração no 1º ano", f1(R.ger, 0), "kWh · " + f1(R.rend, 0) + " kWh por kWp · média na vida útil " + f1(R.ger_media_vida, 0) + " kWh/ano", `<span class="t2 pq">${fonteSis}</span>`)}
    ${cartao("so-pr", "Rendimento global (PR)", R.pr == null ? "—" : f1(R.pr * 100, 1) + "%", "calculado pelas perdas abaixo")}
    ${cartao("so-inv", "Inversor", f1(R.pca, 2), "kW CA · relação CC/CA " + f1(R.razao, 2))}</div>
    ${typeof PhysisCalc !== "undefined" && PhysisCalc.potencias ? PhysisCalc.potenciasHtml([["Inversor na potência nominal", PhysisCalc.potencias(R.pca, num(o.fp_inv))]], /^en/i.test(document.documentElement.lang), "Potências na saída do inversor (FP: o da folha do inversor, se digitado)") + campo(o, "fp_inv", "Fator de potência do inversor (0 a 1)", "da folha de dados", "Vazio = premissa da base (a conferir).") : ""}${R.avisos.length ? `<div class="faixa at" role="status"><ul>${R.avisos.map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>` : ""}`;
  const casc = `<section class="cartao" aria-labelledby="h-so-casc"><h2 id="h-so-casc">Para onde vai a energia</h2>${hbar("Perdas por etapa, kWh por ano", R.cascata.map(x => ({ rot:x.nome, v:x.kwh })), "kWh/ano")}
    <div class="rolagem"><table><caption>Perdas em cascata: de ${f1(R.bruta, 0)} kWh (potência nominal × sol no plano) a ${f1(R.ger, 0)} kWh entregues</caption><thead><tr><th scope="col">Etapa</th><th scope="col">Perda (%)</th><th scope="col">Perda (kWh/ano)</th></tr></thead><tbody>
    ${R.cascata.map(x => `<tr><th scope="row">${esc(x.nome)}</th><td>${f1(x.pct, 1)}</td><td>${f1(x.kwh, 0)}</td></tr>`).join("")}</tbody></table></div></section>`;
  const mes = `<section class="cartao" aria-labelledby="h-so-mes"><h2 id="h-so-mes">Mês a mês</h2><div class="rolagem"><table><caption>Sol, temperatura, PR e geração de cada mês</caption><thead><tr><th scope="col">Mês</th><th scope="col">Sol (kWh/m²·dia)</th><th scope="col">Ambiente (°C)</th><th scope="col">Célula (°C)</th><th scope="col">PR (%)</th><th scope="col">Geração (kWh)</th></tr></thead><tbody>
    ${R.meses.map((x, i) => `<tr><th scope="row">${MESES[i]}</th><td>${f1(x.H, 2)}</td><td>${f1(x.T, 1)}</td><td>${f1(x.tc, 1)}</td><td>${f1(x.pr * 100, 1)}</td><td>${f1(x.kwh_kwp * R.kwp, 0)}</td></tr>`).join("")}</tbody></table></div></section>`;
  const S = R.strings, st = `<section class="cartao" aria-labelledby="h-so-str"><h2 id="h-so-str">Strings e MPPT</h2><div class="rolagem"><table><caption>Conferência das tensões e correntes com o inversor</caption><thead><tr><th scope="col">Item</th><th scope="col">Valor</th><th scope="col">Limite</th></tr></thead><tbody>
    <tr><th scope="row">Voc do módulo a ${f1(E.p.tmin, 0)} °C</th><td>${f1(S.voc_frio, 1)} V</td><td>${S.n_max} em série até ${f1(V.vdc_max, 0)} V</td></tr>
    <tr><th scope="row">Vmp do módulo a ${f1(E.p.tmin, 0)} °C</th><td>${f1(S.vmp_frio, 1)} V</td><td>${S.n_max_mppt} em série até o topo do MPPT (${f1(V.mppt_max, 0)} V)</td></tr>
    <tr><th scope="row">Vmp do módulo a ${f1(S.tc_max, 0)} °C de célula</th><td>${f1(S.vmp_quente, 1)} V</td><td>pelo menos ${S.n_min} em série para o piso do MPPT (${f1(V.mppt_min, 0)} V)</td></tr>
    <tr><th scope="row">Arranjo sugerido</th><td>${S.strings ? S.strings + " string(s) de " + S.em_serie + " módulos" : "—"}</td><td>${S.por_mppt ? S.por_mppt + " string(s) por MPPT · Voc da string " + f1(S.voc_string, 0) + " V" : ""}</td></tr></tbody></table></div>
    <p>${S.ok ? `<span class="selo ok">Cabe no inversor</span>` : `<span class="selo al">Não cabe: veja os avisos</span>`}</p></section>`;
  const finTab = R.fin ? `<div class="rolagem"><table><caption>Retorno do investimento de ${brl(Math.round(R.invest))} (economia de ${brl(Math.round(R.econ))} no 1º ano; reajuste efetivo ${f1(R.infl_efetiva, 2)}% ao ano)</caption><thead><tr><th scope="col">Retorno simples</th><th scope="col">Retorno descontado</th><th scope="col">VPL</th><th scope="col">TIR ao ano</th></tr></thead><tbody><tr>
    <td>${R.fin.simples != null ? f1(R.fin.simples / 12, 1) + " anos" : "não se paga"}</td><td>${R.fin.descontado != null ? f1(R.fin.descontado / 12, 1) + " anos" : "—"}</td><td>${R.fin.vpl != null ? brl(Math.round(R.fin.vpl)) : "—"}</td><td>${R.fin.tir != null ? f1(R.fin.tir, 1) + "%" : "—"}</td></tr></tbody></table></div>` : `<p class="t2 pq">Informe a tarifa e o custo por kWp para ver o retorno.</p>`;
  const ec = R.economia, leiTab = ec ? `<div class="rolagem"><table><caption>Economia pela Lei 14.300: ${f1(ec.auto, 0)} kWh usados na hora (tarifa cheia) e ${f1(ec.compensada, 0)} kWh compensados pela rede no 1º ano</caption><thead><tr><th scope="col">Ano</th><th scope="col">Parte do Fio B paga pela energia injetada</th><th scope="col">Economia no ano</th></tr></thead><tbody>
    ${R.economia_por_ano.map(x => `<tr><th scope="row">${x.ano}</th><td>${x.pct == null ? "—" : f1(x.pct * 100, 0) + "%"}</td><td>${brl(Math.round(x.economia))}</td></tr>`).join("")}</tbody></table></div>
    <p class="t2 pq">Percentuais da base de premissas (solar.fio_b_escala, <span class="selo at">conferir</span> na Lei 14.300, art. 27). O retorno acima usa a economia do 1º ano.</p>` : "";
  const autH = ou(num(o.autonomia), 0), dod = { litio:0.9, agm:0.5 }[o.bateria || "litio"] || 0.9, bat = bateriaKwh(E.p.consumo, autH, dod);
  const fin = `<section class="cartao" aria-labelledby="h-so-fin"><h2 id="h-so-fin">Custo, retorno e bateria</h2><div class="precos">${campo(o, "tarifa", "Tarifa de energia (R$ por kWh)", "ex.: 0,95")}${campo(o, "custo_kwp", "Custo instalado (R$ por kWp)", "ex.: 3800")}
    ${campo(o, "taxa", "Taxa de desconto (% ao ano)", "10")}${campo(o, "infl", "Reajuste da tarifa (% ao ano)", "4")}${campo(o, "autonomia", "Bateria: horas de autonomia", "0 = sem bateria")}
    ${lista(o, "bateria", "Tipo de bateria", [["litio", "Lítio (LiFePO₄), pode usar 90%"], ["agm", "Chumbo-ácido (AGM), pode usar 50%"]], "litio")}</div>
    <h3 class="t3">Conta de luz com a solar (Lei 14.300)</h3><div class="precos">${campo(o, "autoconsumo", "Parte da geração usada na hora (%)", "100", "O resto vai para a rede e volta como crédito.")}
    ${campo(o, "fio_b", "Fio B da tarifa (R$ por kWh)", "da conta ou da ANEEL", "Parte da tarifa de uso da rede (TUSD Fio B) da sua distribuidora.")}${campo(o, "ano", "1º ano de geração", String(new Date().getFullYear()))}
    ${lista(o, "ligacao", "Tipo de ligação", [["monofasico", "Monofásica"], ["bifasico", "Bifásica"], ["trifasico", "Trifásica"]], "bifasico")}
    ${lista(o, "regra", "Pedido de acesso à rede", [["lei14300", "Depois de 07/01/2023 (regra de transição)"], ["antiga", "Até 07/01/2023 (regra antiga até 2045)"]], "lei14300")}</div>${leiTab}${finTab}${bat ? `<p class="t2">Bateria: <strong>${f1(bat, 1)} kWh</strong> para ${f1(autH, 0)} h de autonomia.</p>` : ""}</section>`;
  const mapa = typeof mapaCalorSolar === "function" ? mapaCalorSolar(E.P.lat, E.P.lon) : "";
  return `${TITULO_SOLAR}${chipsSolar()}${typeof avisoLocalCep === "function" ? avisoLocalCep() : ""}<p class="t2 apoio">Potencial do lugar, perdas uma a uma, tamanho do sistema, inversor e strings, e o retorno. A geração calculada aqui vai para o Carbono e para a Gestão (compras e investimentos).</p>${ent}${eq}${per}${mapa}${res}${casc}${mes}${st}${fin}${metodologia()}`; }

/* ════════ Eventos (atributos data-sol-…) ════════ */
if (typeof document !== "undefined" && !window.__solEventos) { window.__solEventos = true;
  document.addEventListener("change", ev => { const t = ev.target; if (!t || !t.dataset || !t.dataset.solK) return; const o = Object.assign({}, ler()), k = t.dataset.solK; o[k] = t.value.trim();
    if (k === "mod") ["placa", "m2placa", "voc", "vmp", "isc", "beta", "gamma", "noct", "deg"].forEach(x => { o[x] = ""; });
    if (k === "inv") ["eta_inv", "vdc_max", "mppt_min", "mppt_max", "n_mppt", "imax_mppt"].forEach(x => { o[x] = ""; });
    gravar(o); const id = t.id; desenhar(false); const x = el(id); if (x) x.focus(); });
  document.addEventListener("click", ev => { const b = ev.target && ev.target.closest ? ev.target.closest("button[data-sol-sub]") : null; if (!b) return;
    if (typeof ui !== "undefined" && ui) ui.solSub = b.dataset.solSub; try { sessionStorage.setItem("physis-solar-sub", b.dataset.solSub); } catch (e) {} desenhar(false); const x = el(b.id); if (x) x.focus(); }); }

window.SOLAR = { calcular, strings, tCelula, fTemp, compat, plantaSalva, MODULOS, INVERSORES, PERDAS_PADRAO };
window.telaSolar = telaSolar;   /* global: a plataforma chama telaSolar() na hora de desenhar */
})();
