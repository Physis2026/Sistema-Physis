/* physis-validacao.js — aba Validação · planejado × gerado (M&V) da plataforma. EM DESENVOLVIMENTO.
   Produto 3 do SustainKit (decisão de 18/11/2026): o planejado (dimensionamento, Planejador, premissas) × o medido (leituras
   do hub), mês a mês: QUANTO (desvio), QUANDO (primeiro mês fora e duração), COMO (equipamento e variável) e POR QUÊ
   (regras com evidência e confiança). Não confundir com physis_hub/mv*.py (gestão interna de M&V da Physis).
   Contrato com a plataforma: telaValidacao() (HTML da aba, com o único título h1), window.VALIDACAO = { contas puras,
   testáveis, ipmvp (a equação geral do IPMVP que a aba Certificações também usa, em mvEconomia) } e window.VALIDACAO_I18N
   (português → inglês) com window.VALIDACAO_I18N_RX; os dois vão copiados em sistema/physis-i18n-modulos.json.
   Espelho de physis-hub/physis_hub/validacao.py (mesmas premissas validacao.*, fórmulas e regras; teste em
   tests/test_validacao.py). Dados: no modo hub, GET api/validacao/estado (cópia guardada neste aparelho para ver sem
   ligação); fora dele, ou sem nenhum plano gravado, dados SIMULADOS da Casa Physis (marcados como tal), com um desvio
   explicado pelo clima e outro por equipamento desligado.
   Globais usadas se existirem: esc, n2, numBr, ui, desenhar, localDaInstalacao, solMensal, abasAtivas, PhysisCalc,
   PhysisCarbono, PhysisODF, PhysisExportar, FROTA, SOLAR, TURBINAS. */
(function () {
"use strict";
const CHAVE = "physis-validacao-cache";
/* reserva das premissas validacao.* (as mesmas de sistema/physis-premissas.json; todas "conferir") */
const PREMISSAS_RESERVA = { "validacao.desvio_limite_pct":10.0, "validacao.cobertura_min_pct":90.0, "validacao.clima_min_pct":10.0,
  "validacao.premissa_meses_min":3, "validacao.premissa_variacao_max_pct":15.0, "validacao.plano_plano_max_pct":2.0, "validacao.anomalia_z":3.5,
  "validacao.anomalia_amostra_min":6, "validacao.grau_dia_base_c":18.3, "validacao.baseline_meses_min":12, "validacao.baseline_cvrmse_max_pct":15.0,
  "validacao.aceite_r2_min":0.75, "validacao.aceite_nmbe_max_pct":5.0, "validacao.aceite_cvrmse_diario_max_pct":25.0, "validacao.modelo_ganho_min_pct":5.0,
  "validacao.ml_amostra_min":365, "validacao.ml_k":7, "validacao.incerteza_confianca_pct":68.0, "validacao.incerteza_max_pct":50.0, "validacao.perda_dados_max_pct":10.0,
  "validacao.limpeza_z":5.0, "validacao.travado_n":12, "validacao.inspecao_dias_max":90, "validacao.revisao_aviso_dias":30, "validacao.fdd_dias_min":3,
  "validacao.cv_k":5, "validacao.aceite_cvrmse_ou_max_pct":20.0, "validacao.cusum_k":0.5, "validacao.cusum_h":5.0, "validacao.ip_confianca_pct":95.0,
  "validacao.mc_n":2000, "validacao.mc_confianca_pct":95.0, "validacao.nre_dias_min":14, "validacao.nre_limite_pct":10.0, "validacao.nre_z":3.0 };
/* perfil PEE (ANEEL): exigências sem número até a leitura do Guia de M&V ([MARCADOR]); a tela mostra "aguardando Guia" */
const PREMISSAS_PEE = ["validacao.pee.confianca_pct", "validacao.pee.precisao_pct", "validacao.pee.amostra_min", "validacao.pee.duracao_medicao_dias", "validacao.pee.vida_util_anos",
  "validacao.pee.taxa_desconto_pct", "validacao.pee.rcb_max", "validacao.pee.custo_mv_max_pct", "validacao.pee.prazo_relatorio_dias"];
const MODULOS = {
  solar:{ nome:"Energia solar (geração)", unidade:"kWh", grandeza:"energia", sentido:"gerar", clima:"irradiancia", sinal:1 },
  agua:{ nome:"Água (consumo e reúso)", unidade:"m³", grandeza:"vazao", sentido:"consumir", clima:"chuva", sinal:-1 },
  energia:{ nome:"Energia e AVAC (consumo)", unidade:"kWh", grandeza:"energia", sentido:"consumir", clima:"graus_dia", sinal:1 },
  turbinas:{ nome:"Turbinas (geração)", unidade:"kWh", grandeza:"energia", sentido:"gerar", clima:null, sinal:1 },
  frota:{ nome:"Frota (combustível)", unidade:"L", grandeza:null, sentido:"consumir", clima:null, sinal:1 },
  carbono:{ nome:"Carbono (emissões)", unidade:"tCO₂e", grandeza:null, sentido:"consumir", clima:null, sinal:1 } };
const SEM_PLANO = {
  solar:"Sem plano: grave o planejado da usina (aba Energia solar · dimensionamento) para comparar.",
  agua:"Sem plano: grave o consumo planejado (premissa de consumo por pessoa, projeto ou Planejador) para comparar.",
  energia:"Sem plano: grave o consumo planejado (projeto, AVAC ou Planejador) para comparar.",
  turbinas:"Sem plano: grave a energia planejada (aba Turbinas) para comparar.",
  frota:"Sem plano: nenhum veículo tem o consumo esperado no cadastro da Frota.",
  carbono:"Sem plano: o Carbono nasce dos planejados de Energia e da Frota, e nenhum dos dois tem plano." };
const CAUSAS = { falha_dado:"Equipamento desligado ou falha de dado", clima:"Clima diferente do esperado", consumo_anormal:"Consumo fora do normal aprendido",
  premissa:"Premissa do projeto diverge do medido", sazonal:"Efeito sazonal", nao_identificada:"Causa não identificada" };
const VARIAVEIS_BASE = { graus_dia:"Graus-dia de resfriamento", irradiancia:"Irradiação (kWh/m²·dia)", producao:"Produção ou ocupação (Gestão)" };
const NOME_CLIMA = { irradiancia:"Irradiação (kWh/m²·dia)", chuva:"Chuva do mês (mm)", graus_dia:"Graus-dia de resfriamento" };
function premissa(id) { try { if (typeof PhysisCalc !== "undefined") { const v = PhysisCalc.premissa(id); if (typeof v === "number" && isFinite(v)) return v; } } catch (e) {} return PREMISSAS_RESERVA[id] == null ? null : PREMISSAS_RESERVA[id]; }
const P = () => Object.fromEntries(Object.keys(PREMISSAS_RESERVA).concat(PREMISSAS_PEE).map(k => [k, premissa(k)]));
const alfaFrota = () => { try { if (window.FROTA && FROTA.premissa) { const v = FROTA.premissa("frota.ewma_alfa"); if (typeof v === "number") return v; } } catch (e) {} return 0.3; };

/* ════════ Contas puras (espelho de validacao.py) ════════ */
function desvio(p, m) { if (p == null || m == null) return { abs: null, pct: null }; return { abs: m - p, pct: p > 0 ? (m - p) / p * 100 : null }; }
const diasDoMes = mes => new Date(Date.UTC(+mes.slice(0, 4), +mes.slice(5, 7), 0)).getUTCDate();
function mesesAte(ultimo, n) { let a = +ultimo.slice(0, 4), m = +ultimo.slice(5, 7); const out = [];
  for (let i = 0; i < n; i++) { out.push(a + "-" + String(m).padStart(2, "0")); m--; if (m === 0) { a--; m = 12; } } return out.reverse(); }
function planoDoMes(meses, mes) { if (!meses) return null; let v = meses[mes]; if (v === undefined) v = meses[mes.slice(5, 7)]; return typeof v === "number" && isFinite(v) ? v : null; }
function cvPct(vals) { const v = vals.filter(x => x != null); if (v.length < 2) return v.length ? 0 : null; const m = v.reduce((s, x) => s + x, 0) / v.length;
  if (!m) return null; const sd = Math.sqrt(v.reduce((s, x) => s + (x - m) ** 2, 0) / v.length); return sd / Math.abs(m) * 100; }
function planoPlano(meses, p) { const v = Object.values(meses || {}).filter(x => typeof x === "number"), c = cvPct(v); return v.length >= 2 && c != null && c <= p["validacao.plano_plano_max_pct"]; }
function comparar(plano, medido, meses, clima, climaEsp) { return meses.map(mes => { const p = planoDoMes(plano, mes), m = (medido || {})[mes] || {}, v = m.valor == null ? null : m.valor;
  const dm = m.dias_mes || diasDoMes(mes), dias = m.dias == null ? null : m.dias, d = desvio(p, v), cm = (clima || {})[mes];
  return { mes, planejado: p, medido: v, abs: d.abs, pct: d.pct, dias, dias_mes: dm, cobertura_pct: dias == null ? null : dias / dm * 100, clima_medido: cm == null ? null : cm, clima_esperado: planoDoMes(climaEsp, mes) }; }); }
const fora = (l, p) => l.pct != null && Math.abs(l.pct) > p["validacao.desvio_limite_pct"];
function quando(linhas, p) { const tr = []; let ini = null;
  linhas.forEach((l, i) => { if (fora(l, p)) { if (ini == null) ini = i; } else if (ini != null) { tr.push([ini, i - 1]); ini = null; } });
  if (ini != null) tr.push([ini, linhas.length - 1]); if (!tr.length) return null; const [a, b] = tr[0];
  return { primeiro_mes: linhas[a].mes, duracao_meses: b - a + 1, ultimo_mes: linhas[b].mes, continua: tr[tr.length - 1][1] === linhas.length - 1,
    trechos: tr.map(([x, y]) => ({ inicio: linhas[x].mes, fim: linhas[y].mes, meses: y - x + 1 })) }; }
const nivel = c => c >= 0.7 ? "alta" : c >= 0.45 ? "média" : c > 0 ? "baixa" : "—";
const sinal = x => (x > 0) - (x < 0);
const causa = (codigo, conf, evidencia) => { const c = Math.round(Math.max(0, Math.min(1, conf)) * 100) / 100; return { codigo, nome: CAUSAS[codigo], confianca: c, nivel: nivel(c), evidencia }; };
/* POR QUÊ: as mesmas cinco regras de validacao.causas(), na mesma ordem e com os mesmos limites (janela = o período todo do item) */
function causas(linha, hist, info, p, alfa, janela) { const out = [], pct = linha.pct, jan = janela || hist.concat([linha]); if (pct == null) return [causa("nao_identificada", 0, {})];
  const lim = p["validacao.desvio_limite_pct"], cob = linha.cobertura_pct, cobMin = p["validacao.cobertura_min_pct"];
  if (cob != null && cob < cobMin) out.push(causa("falha_dado", cob === 0 ? 0.95 : Math.min(0.9, 0.5 + (cobMin - cob) / 100), { dias: linha.dias, dias_mes: linha.dias_mes, cobertura_pct: cob, cobertura_min_pct: cobMin }));
  const cm = linha.clima_medido, ce = linha.clima_esperado;
  if (info.clima && cm != null && ce) { const dc = (cm - ce) / ce * 100;
    if (Math.abs(dc) >= p["validacao.clima_min_pct"] && sinal(dc) * (info.sinal || 1) === sinal(pct)) out.push(causa("clima", 0.35 + 0.5 * Math.min(Math.abs(dc), Math.abs(pct)) / Math.max(Math.abs(dc), Math.abs(pct)), { variavel: info.clima, medido: cm, esperado: ce, diferenca_pct: dc })); }
  if (info.sentido === "consumir" && pct > 0 && linha.medido != null && linha.planejado && window.FROTA && FROTA.anomaliaConsumo) {
    const h = hist.filter(x => x.medido != null && x.planejado && (x.cobertura_pct == null || x.cobertura_pct >= cobMin)).map(x => x.medido / x.planejado);
    const a = FROTA.anomaliaConsumo(linha.medido / linha.planejado, h, p["validacao.anomalia_z"], Math.round(p["validacao.anomalia_amostra_min"]), alfa, lim);
    if (a.anomalo) out.push(causa("consumo_anormal", 0.7, { z: a.z, razao: a.valor, mediana: a.mediana, n: a.n })); }
  let sazonal = false;
  if (info.plano_plano) { const meds = jan.filter(h => h.medido != null).map(h => h.medido);
    if (meds.length >= 3) { const mm = meds.reduce((s, x) => s + x, 0) / meds.length;
      if (mm && sinal(linha.medido - mm) === sinal(pct) && Math.abs(linha.medido - mm) / mm * 100 >= lim / 2) { sazonal = true; out.push(causa("sazonal", 0.5, { media_medida: mm, medido: linha.medido })); } } }
  const seq = [linha]; for (let i = hist.length - 1; i >= 0; i--) { const h = hist[i]; if (h.pct == null || Math.abs(h.pct) <= lim || sinal(h.pct) !== sinal(pct) || (h.cobertura_pct != null && h.cobertura_pct < cobMin)) break; seq.push(h); }
  const t0 = jan.filter(h => h.pct != null).map(h => h.pct), todos = t0.length ? t0 : [pct], mediaAno = todos.reduce((s, x) => s + x, 0) / todos.length;
  if (!sazonal && (cob == null || cob >= cobMin) && seq.length >= p["validacao.premissa_meses_min"] && sinal(mediaAno) === sinal(pct) && Math.abs(mediaAno) >= lim / 2) {
    const c = cvPct(seq.filter(s => s.planejado).map(s => s.medido / s.planejado));
    if (c != null && c <= p["validacao.premissa_variacao_max_pct"]) out.push(causa("premissa", info.premissa ? 0.65 : 0.6, { meses: seq.length, media_pct: seq.reduce((s, x) => s + x.pct, 0) / seq.length, cv_pct: c, premissa: info.premissa || null })); }
  if (!out.length) out.push(causa("nao_identificada", 0, {}));
  return out.sort((a, b) => b.confianca - a.confianca); }
function como(itens, mes) { const l = itens.map(it => [it, it.linhas.find(x => x.mes === mes)]).filter(([, x]) => x && x.abs != null); if (!l.length) return null;
  const total = l.reduce((s, [, x]) => s + x.abs, 0), [it, x] = l.reduce((a, b) => Math.abs(b[1].abs) > Math.abs(a[1].abs) ? b : a);
  return { item: it.item, nome: it.nome || it.item, ativo: it.ativo || "", variavel: it.grandeza || "", abs: x.abs, pct: x.pct, parte_pct: total ? Math.abs(x.abs) / Math.abs(total) * 100 : null }; }
function somarItens(itens, meses) { return meses.map((mes, i) => { const ls = itens.map(it => it.linhas[i]), pl = ls.filter(l => l.planejado != null), me = ls.filter(l => l.medido != null && l.planejado != null);
  const p = pl.length ? pl.reduce((s, l) => s + l.planejado, 0) : null, m = me.length ? me.reduce((s, l) => s + l.medido, 0) : null, d = desvio(p, m), cobs = ls.filter(l => l.cobertura_pct != null).map(l => l.cobertura_pct);
  return { mes, planejado: p, medido: m, abs: d.abs, pct: d.pct, cobertura_pct: cobs.length ? Math.min(...cobs) : null }; }); }
function analisarModulo(mod, itens, meses, p, alfa) { const cfg = MODULOS[mod], comPlano = itens.filter(it => it.plano && Object.keys(it.plano).length);
  const base = { modulo: mod, nome: cfg.nome, unidade: cfg.unidade, sentido: cfg.sentido, meses };
  if (!comPlano.length) return Object.assign(base, { tem_plano: false, sem_plano: SEM_PLANO[mod], itens: [], linhas: [], quando: null, explicacoes: [], total: null, itens_sem_plano: itens.map(it => it.nome || it.item) });
  const its = comPlano.map(it => ({ item: it.item, nome: it.nome || it.item, ativo: it.ativo || "", grandeza: it.grandeza || cfg.grandeza || "", fonte: it.fonte || "", premissa: it.premissa || "",
    plano_plano: planoPlano(it.plano, p), linhas: comparar(it.plano, it.medido, meses, it.clima, it.clima_esperado), extra: it.extra || {} }));
  const linhas = somarItens(its, meses), expl = [];
  linhas.forEach((l, i) => { if (!fora(l, p)) return; const c = como(its, l.mes), it = (c && its.find(x => x.item === c.item)) || its[0];
    expl.push({ mes: l.mes, abs: l.abs, pct: l.pct, como: c, causas: causas(it.linhas[i], it.linhas.slice(0, i), { sentido: cfg.sentido, sinal: cfg.sinal, clima: cfg.clima, plano_plano: it.plano_plano, premissa: it.premissa }, p, alfa, it.linhas) }); });
  const tp = linhas.filter(l => l.planejado != null && l.medido != null), tP = tp.reduce((s, l) => s + l.planejado, 0), tM = tp.reduce((s, l) => s + l.medido, 0);
  return Object.assign(base, { tem_plano: true, sem_plano: "", itens: its, linhas, quando: quando(linhas, p), explicacoes: expl, total: Object.assign(desvio(tP, tM), { planejado: tP, medido: tM, meses: tp.length }),
    itens_sem_plano: itens.filter(it => !it.plano || !Object.keys(it.plano).length).map(it => it.nome || it.item) }); }
/* Linha de base e IPMVP. A equação geral é UMA só na plataforma: a aba Certificações (mvEconomia) chama esta. */
function ipmvp(base, rel, aj) { const a = aj || 0; if (base == null || rel == null || !isFinite(base) || !isFinite(rel)) return { econ: null, baseAj: base == null ? null : base + a, pct: null };
  const econ = base - rel + a, baseAj = base + a; return { econ, baseAj, pct: baseAj > 0 ? econ / baseAj * 100 : null }; }
const grausDia = (temps, base) => temps.filter(t => t != null).reduce((s, t) => s + Math.max(0, t - base), 0);
/* (inclinação, intercepto, r²) da reta y = a·x + b: espelho de aprendizado.reta */
function reta(xs, ys) { const n = xs.length; if (n < 2) return [0, ys.length ? ys[0] : 0, 0]; const mx = xs.reduce((s, x) => s + x, 0) / n, my = ys.reduce((s, y) => s + y, 0) / n;
  const sxx = xs.reduce((s, x) => s + (x - mx) ** 2, 0); if (sxx <= 0) return [0, my, 0]; const a = xs.reduce((s, x, i) => s + (x - mx) * (ys[i] - my), 0) / sxx, b = my - a * mx;
  const sst = ys.reduce((s, y) => s + (y - my) ** 2, 0), sse = ys.reduce((s, y, i) => s + (y - (a * xs[i] + b)) ** 2, 0); return [a, b, sst > 0 ? 1 - sse / sst : 0]; }
function linhaDeBase(am, p) { const v = am.filter(s => s.y != null && s.x != null), n = v.length;
  if (n < 3) return { ok: false, n, a: null, b: null, r2: null, cv_rmse_pct: null, avisos: ["poucos"] };
  const xs = v.map(s => s.x), ys = v.map(s => s.y), [a, b, r2] = reta(xs, ys), sse = ys.reduce((s, y, i) => s + (y - (a * xs[i] + b)) ** 2, 0), my = ys.reduce((s, y) => s + y, 0) / n;
  const cv = n > 2 && my ? Math.sqrt(sse / (n - 2)) / my * 100 : null, avisos = [];
  if (n < p["validacao.baseline_meses_min"]) avisos.push("curta"); if (cv != null && cv > p["validacao.baseline_cvrmse_max_pct"]) avisos.push("cv");
  return { ok: !avisos.length, n, a, b, r2, cv_rmse_pct: cv, avisos }; }
const esperado = (m, x) => m.a == null || x == null ? null : m.a * x + m.b;
function ipmvpRegressao(baseAm, relAm, p, ajNaoRot) { const mod = linhaDeBase(baseAm, p);
  if (mod.a == null) return { modelo: mod, base: null, relatorio: null, ajuste_rotineiro: null, ajuste_nao_rotineiro: ajNaoRot || 0, esperado_relatorio: null, economia: ipmvp(null, null) };
  const yb = baseAm.filter(s => s.y != null).reduce((s, x) => s + x.y, 0), rel = relAm.filter(s => s.y != null && s.x != null), yr = rel.reduce((s, x) => s + x.y, 0), er = rel.reduce((s, x) => s + esperado(mod, x.x), 0), aj = er - yb;
  return { modelo: mod, base: yb, relatorio: yr, ajuste_rotineiro: aj, ajuste_nao_rotineiro: ajNaoRot || 0, esperado_relatorio: er, meses_relatorio: rel.length,
    linhas: rel.map(s => Object.assign({}, s, { esperado: esperado(mod, s.x) })), economia: ipmvp(yb, yr, aj + (ajNaoRot || 0)) }; }

/* ════════ Plano de M&V, modelos, métricas, incerteza e limpeza (espelho de validacao.py e validacao_modelos.py) ════════
   Normas só pelo nome (IPMVP, ISO 50006, ISO 50015, ASHRAE Guideline 14); nenhum texto delas copiado. */
const VERSAO_CODIGO = "validacao-2", GRADE_CP = 21, FATOR_G14 = 1.26;   /* 1,26: coeficiente empírico da Guideline 14 [CONFERIR] */
const OPCOES_IPMVP = { A:"Medição isolada do parâmetro-chave", B:"Medição isolada de todos os parâmetros", C:"Instalação inteira (fatura ou medidor geral)", D:"Simulação calibrada" };
const PAPEIS = { coleta:"Coleta dos dados", analise:"Análise", arquivo:"Arquivo", relatorio:"Relatório" };
const SECOES_RELATORIO = ["Descrição do projeto", "Método e opção IPMVP", "Dados observados", "Comparação com as metas", "Análise de incerteza", "Evidências", "Recomendações", "Anexo de rastreabilidade"];
const ACOES = { falha_dado:"Conferir a alimentação e a comunicação do medidor e do nó; repor os dias perdidos se houver outra fonte.",
  clima:"Nada a corrigir no equipamento: registrar o clima do período e levar à linha de base.",
  consumo_anormal:"Inspecionar o equipamento e a operação (horário, ajuste, vazamento) e registrar a inspeção.",
  premissa:"Revisar a premissa com a equipe e registrar a mudança no plano de M&V (com o motivo).",
  sazonal:"Trocar o planejado igual todo mês por um planejado com estação.",
  nao_identificada:"Inspeção em campo; registrar o que foi achado no diário de lições." };
const NAO_NEGATIVAS = new Set(["vazao", "chuva", "irradiancia", "nivel", "umidade", "umidade_solo", "corrente"]), P_MODELO = { "2P":2, "3P":3, "4P":4, "5P":5 };
function metricas(ys, yh, p) { const n = ys.length; if (!n || n <= p) return { n, p, r2: null, cv_rmse_pct: null, nmbe_pct: null, erro_padrao: null };
  const my = ys.reduce((s, y) => s + y, 0) / n, sse = ys.reduce((s, y, i) => s + (y - yh[i]) ** 2, 0), sst = ys.reduce((s, y) => s + (y - my) ** 2, 0), ep = Math.sqrt(sse / (n - p));
  return { n, p, r2: sst > 0 ? 1 - sse / sst : null, cv_rmse_pct: my ? ep / my * 100 : null, nmbe_pct: my ? ys.reduce((s, y, i) => s + y - yh[i], 0) / ((n - p) * my) * 100 : null, erro_padrao: ep }; }
/* mínimos quadrados com uma pitada de L2 fora da constante: espelho de aprendizado.regressao (Gauss com pivô parcial) */
function regressao(X, y) { const p = X[0].length, A = [], b = [];
  for (let i = 0; i < p; i++) { A.push([]); for (let j = 0; j < p; j++) A[i].push(X.reduce((s, r) => s + r[i] * r[j], 0) + (i === j && i > 0 ? 1e-6 : 0)); b.push(X.reduce((s, r, k) => s + r[i] * y[k], 0)); }
  const m = A.map((r, i) => r.concat([b[i]]));
  for (let c = 0; c < p; c++) { let pv = c; for (let r = c; r < p; r++) if (Math.abs(m[r][c]) > Math.abs(m[pv][c])) pv = r; if (Math.abs(m[pv][c]) < 1e-12) continue;
    [m[c], m[pv]] = [m[pv], m[c]]; for (let r = 0; r < p; r++) if (r !== c && m[r][c]) { const k = m[r][c] / m[c][c]; for (let q = c; q <= p; q++) m[r][q] -= k * m[c][q]; } }
  return m.map((r, i) => Math.abs(r[i]) > 1e-12 ? r[p] / r[i] : 0); }
function colunas(forma, x, c) { return forma === "2P" ? [1, x] : forma === "3PC" ? [1, Math.max(0, x - c[0])] : forma === "3PH" ? [1, Math.max(0, c[0] - x)]
  : forma === "4P" ? [1, Math.min(0, x - c[0]), Math.max(0, x - c[0])] : [1, Math.max(0, c[0] - x), Math.max(0, x - c[1])]; }
function prever(m, x) { if (!m || x == null) return null; if (m.tipo === "ML") { const v = m.dados.slice().sort((a, b) => Math.abs(a[0] - x) - Math.abs(b[0] - x)).slice(0, m.k); return v.reduce((s, d) => s + d[1], 0) / v.length; }
  return colunas(m.forma, x, m.cps).reduce((s, v, i) => s + v * m.coef[i], 0); }
function grade(xs) { const s = xs.slice().sort((a, b) => a - b), lo = s[Math.floor(0.1 * (s.length - 1))], hi = s[Math.ceil(0.9 * (s.length - 1))]; if (!(hi > lo)) return [];
  return Array.from({ length: GRADE_CP }, (_, i) => lo + (hi - lo) * i / (GRADE_CP - 1)); }
function ajustarCP(tipo, xs, ys) { const p = P_MODELO[tipo]; if (xs.length < p + 2) return null; const g = grade(xs);
  const formas = tipo === "2P" ? [["2P", []]] : tipo === "3P" ? g.map(c => ["3PC", [c]]).concat(g.map(c => ["3PH", [c]])) : tipo === "4P" ? g.map(c => ["4P", [c]]) : g.flatMap(a => g.filter(b => b > a).map(b => ["5P", [a, b]]));
  let melhor = null;
  for (const [forma, cps] of formas) { const X = xs.map(x => colunas(forma, x, cps)); if (forma !== "2P" && X[0].slice(1).some((_, j) => X.every(r => r[j + 1] === 0))) continue;
    const coef = regressao(X, ys); if (((forma === "3PC" || forma === "3PH") && coef[1] <= 0) || (forma === "5P" && (coef[1] <= 0 || coef[2] <= 0))) continue;
    const yh = X.map(r => r.reduce((s, v, i) => s + v * coef[i], 0)), sse = ys.reduce((s, y, i) => s + (y - yh[i]) ** 2, 0);
    if (!melhor || sse < melhor[0]) melhor = [sse, forma, cps, coef, yh]; }
  if (!melhor) return null; const [, forma, cps, coef, yh] = melhor; return { tipo, forma, cps, coef, metricas: metricas(ys, yh, p) }; }
function ajustarML(xs, ys, k) { const n = xs.length; if (n <= k + 1) return null; const dados = xs.map((x, i) => [x, ys[i]]);
  const yh = xs.map((x, i) => { const v = dados.filter((_, j) => j !== i).sort((a, b) => Math.abs(a[0] - x) - Math.abs(b[0] - x)).slice(0, k); return v.reduce((s, d) => s + d[1], 0) / k; });
  return { tipo: "ML", forma: "ML", cps: [], coef: [], k, dados, metricas: metricas(ys, yh, 1) }; }
function aceite(m, p, cvMax) { if (!m) return { ok: false, motivos: ["sem modelo"] }; const x = m.metricas, mot = [], cv = cvMax == null ? p["validacao.baseline_cvrmse_max_pct"] : cvMax;
  if (x.r2 == null || x.r2 < p["validacao.aceite_r2_min"]) mot.push("r2"); if (x.cv_rmse_pct == null || x.cv_rmse_pct > cv) mot.push("cv_rmse"); if (x.nmbe_pct == null || Math.abs(x.nmbe_pct) > p["validacao.aceite_nmbe_max_pct"]) mot.push("nmbe");
  return { ok: !mot.length, motivos: mot }; }
function escolherModelo(xs, ys, p) { const cands = Object.keys(P_MODELO).map(t => ajustarCP(t, xs, ys)).filter(m => m && m.metricas.cv_rmse_pct != null), ganho = p["validacao.modelo_ganho_min_pct"] / 100;
  let esc = null; if (cands.length) { const best = Math.min(...cands.map(m => m.metricas.cv_rmse_pct)); esc = cands.slice().sort((a, b) => P_MODELO[a.tipo] - P_MODELO[b.tipo]).find(m => m.metricas.cv_rmse_pct <= best * (1 + ganho)); }
  let ml = null; if (xs.length >= p["validacao.ml_amostra_min"]) { ml = ajustarML(xs, ys, Math.round(p["validacao.ml_k"]));
    if (ml && esc && ml.metricas.cv_rmse_pct != null && ml.metricas.cv_rmse_pct < esc.metricas.cv_rmse_pct * (1 - ganho)) esc = ml; else if (ml && !esc) esc = ml; }
  return { candidatos: cands.concat(ml ? [ml] : []), escolhido: esc, aceite: aceite(esc, p) }; }
/* inversa da normal (Acklam) e quantil bicaudal da t de Student por Cornish-Fisher: espelho de validacao_modelos.t_student */
function invNormal(q) { const a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00],
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01],
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00],
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00], pl = 0.02425;
  if (q < pl) { const r = Math.sqrt(-2 * Math.log(q)); return (((((c[0] * r + c[1]) * r + c[2]) * r + c[3]) * r + c[4]) * r + c[5]) / ((((d[0] * r + d[1]) * r + d[2]) * r + d[3]) * r + 1); }
  if (q > 1 - pl) return -invNormal(1 - q);
  const r = q - 0.5, s = r * r; return (((((a[0] * s + a[1]) * s + a[2]) * s + a[3]) * s + a[4]) * s + a[5]) * r / (((((b[0] * s + b[1]) * s + b[2]) * s + b[3]) * s + b[4]) * s + 1); }
function tStudent(conf, gl) { const z = invNormal(0.5 + conf / 200), g = Math.max(1, gl); return z + (z ** 3 + z) / (4 * g) + (5 * z ** 5 + 16 * z ** 3 + 3 * z) / (96 * g * g); }
function autocorrelacao(r) { const n = r.length; if (n < 3) return 0; const m = r.reduce((s, x) => s + x, 0) / n, den = r.reduce((s, x) => s + (x - m) ** 2, 0); let num = 0; for (let i = 1; i < n; i++) num += (r[i] - m) * (r[i - 1] - m); return den ? num / den : 0; }
function incertezaEconomia(cv, n, m, F, p, np, rho) { const lim = p["validacao.incerteza_max_pct"], conf = p["validacao.incerteza_confianca_pct"];
  if (cv == null || !n || !m || !F || F <= 0) return { incerteza_pct: null, veredito: "sem_dado", limite_pct: lim, confianca_pct: conf };
  const r = Math.max(-0.9, Math.min(0.9, rho || 0)), nef = n * (1 - r) / (1 + r), t = tStudent(conf, n - (np || 2)), u = t * FATOR_G14 * (cv / 100) * Math.sqrt((n / nef) * (1 + 2 / n) / m) / F * 100;
  return { incerteza_pct: u, veredito: u <= lim ? "dentro" : "fora do limite", limite_pct: lim, confianca_pct: conf, t, n_efetivo: nef, rho: r }; }
const granularidade = s => !s ? "sem dado" : s <= 1200 ? "15 min" : s <= 5400 ? "hora" : s <= 172800 ? "dia" : "mês";
const mediana2 = v => { const s = v.slice().sort((a, b) => a - b), n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : null; };
/* limpeza: o ORIGINAL fica ao lado de cada ponto, com a marca; nada é trocado em silêncio (espelho de limpar_serie) */
function limparSerie(pontos, p, grandeza, faixa, agora) { const out = pontos.map(x => ({ id: x.id, ts: x.ts, original: x.valor, valor: x.valor, marcas: [] })), vistos = new Set(); let ult = null;
  out.forEach(o => { if (o.ts == null || o.ts <= 0) o.marcas.push("ts_invalido"); else if (agora != null && o.ts > agora + 300) o.marcas.push("ts_futuro"); else if (vistos.has(o.ts)) o.marcas.push("ts_duplicado"); else if (ult != null && o.ts < ult) o.marcas.push("ts_fora_de_ordem");
    if (o.ts) { vistos.add(o.ts); ult = ult == null ? o.ts : Math.max(ult, o.ts); }
    const v = o.original; if (v == null || !isFinite(v)) o.marcas.push("impossivel"); else if (v < 0 && NAO_NEGATIVAS.has(grandeza)) o.marcas.push("negativo");
    else if (faixa && ((faixa[0] != null && NAO_NEGATIVAS.has(grandeza) && v < faixa[0]) || (faixa[1] != null && Math.abs(v) > faixa[1]))) o.marcas.push("impossivel"); });
  const bons = out.filter(o => !o.marcas.length || (o.marcas.length === 1 && o.marcas[0] === "ts_fora_de_ordem")).sort((a, b) => a.ts - b.ts), vals = bons.map(o => o.original);
  if (vals.length >= 5) { const mad = mediana2(vals.slice(1).map((v, i) => Math.abs(v - vals[i])));   /* salto isolado: longe do anterior E do seguinte, no mesmo sentido */
    if (mad) for (let i = 1; i < vals.length - 1; i++) { const d1 = vals[i] - vals[i - 1], d2 = vals[i] - vals[i + 1]; if (d1 * d2 > 0 && 0.6745 * Math.min(Math.abs(d1), Math.abs(d2)) / mad > p["validacao.limpeza_z"]) bons[i].marcas.push("atipico"); } }
  const nT = Math.round(p["validacao.travado_n"]), ordem = out.filter(o => o.ts > 0 && o.marcas.indexOf("ts_duplicado") < 0).sort((a, b) => a.ts - b.ts); let seq = [];
  ordem.concat([null]).forEach(o => { if (o && seq.length && o.original === seq[seq.length - 1].original) { seq.push(o); return; } if (seq.length >= nT) seq.slice(1).forEach(s => s.marcas.push("travado")); seq = o ? [o] : []; });
  out.forEach(o => { if (o.marcas.some(m => m !== "ts_fora_de_ordem")) o.valor = null; });
  const val = out.filter(o => o.valor != null).map(o => o.ts).sort((a, b) => a - b), passos = val.slice(1).map((b, i) => b - val[i]).filter(x => x > 0), passo = passos.length ? mediana2(passos) : null;
  const lac = val.slice(1).map((b, i) => [val[i], b]).filter(([a, b]) => passo && b - a > 2 * passo).map(([a, b]) => ({ de: a, ate: b })), esp = passo ? Math.round((val[val.length - 1] - val[0]) / passo) + 1 : val.length;
  const perda = Math.max(0, esp ? (1 - val.length / esp) * 100 : 0), resumo = {}; out.forEach(o => o.marcas.forEach(m => resumo[m] = (resumo[m] || 0) + 1));
  return { pontos: out, resumo, passo_s: passo, granularidade: granularidade(passo), lacunas: lac, n: out.length, validos: val.length, perda_pct: perda, perda_ok: perda <= p["validacao.perda_dados_max_pct"] }; }
function economiaAcumulada(m, dias) { let acc = 0; const out = []; dias.forEach(d => { const e = prever(m, d.x); if (e == null || d.y == null) return; acc += e - d.y; out.push({ dia: d.dia, esperado: e, medido: d.y, economia: e - d.y, acumulada: acc }); }); return out; }
function trechosFdd(serie, p) { const lim = p["validacao.desvio_limite_pct"], nmin = Math.round(p["validacao.fdd_dias_min"]), out = []; let cur = [];
  serie.concat([null]).forEach(s => { if (s && s.esperado > 0 && (s.medido - s.esperado) / s.esperado * 100 > lim) { cur.push(s); return; }
    if (cur.length >= nmin) { const e = cur.reduce((a, c) => a + c.esperado, 0), m = cur.reduce((a, c) => a + c.medido, 0); out.push({ inicio: cur[0].dia, fim: cur[cur.length - 1].dia, dias: cur.length, esperado: e, medido: m, desvio_pct: (m - e) / e * 100 }); } cur = []; });
  return out; }
function alertasMedidor(m, hoje) { const out = [];
  if (!m.cal_proxima) out.push({ tipo: "sem_calibracao" }); else if (m.cal_proxima < hoje) out.push({ tipo: "calibracao_vencida" });
  if (m.exatidao_pct == null) out.push({ tipo: "exatidao_desconhecida" }); if (!m.certificado_sha256) out.push({ tipo: "sem_certificado" }); return out; }
/* plano de M&V: as mesmas exigências de validacao.validar_plano_mv (a tela avisa antes de mandar; o servidor confere de novo) */
function validarPlanoMv(d) { if (!OPCOES_IPMVP[d.opcao]) return "Escolha a opção IPMVP (A, B, C ou D).";
  for (const [k, n] of [["escopo", "o escopo"], ["fronteira", "a fronteira de medição"], ["justificativa", "a justificativa da opção"], ["metodo", "o método de cálculo"]]) if (!String(d[k] || "").trim()) return "Falta " + n + ".";
  if (d.opcao === "D") { const s = d.simulacao || {}; if (!s.software || !s.versao) return "Opção D: informe o programa de simulação e a versão.";
    if (!(s.arquivos || []).length || s.arquivos.some(a => !/^[0-9a-f]{64}$/.test(a.sha256 || ""))) return "Opção D: guarde as cópias dos arquivos de entrada e saída (nome e SHA-256)."; }
  return ""; }
function enpis(pm, b, r) { pm = pm || {}; return [["kWh/m²", "energia_kwh", pm.area_m2, "área do plano de M&V"], ["kWh por unidade produzida", "energia_kwh", "producao", "produção da Gestão"], ["m³/pessoa", "agua_m3", pm.ocupantes, "ocupantes do plano de M&V"], ["L/100 km", "frota_l", "frota_km", "km medidos da frota"]].map(([nome, k, nm, fonte]) => {
  const val = c => { const v = c[k], d = typeof nm === "string" ? c[nm] : nm; return v == null || !d ? null : v / d * (nome === "L/100 km" ? 100 : 1); }, vb = val(b), vr = val(r);
  return { enpi: nome, fonte_normalizador: fonte, base: vb, relatorio: vr, variacao_pct: vb && vr != null ? (vr - vb) / vb * 100 : null, enb: b[k] == null ? null : b[k], sem_dado: vb == null && vr == null }; }); }

/* ════════ Núcleo M&V 2.0 (espelho de validacao_nucleo.py; o Monte Carlo do navegador usa o seu próprio gerador com semente:
   os números oficiais são os do computador central) ════════ */
const POLITICAS = { excluir:"Excluir o período sem dado", linear:"Preencher por interpolação linear", modelo:"Preencher pelo modelo da linha de base" };
const CLASSES_NRE = { equipamento_novo:"Equipamento novo (subiu a carga de base, noite e dia)", ocupacao:"Mudança de ocupação (subiu só nas horas ocupadas)", horario:"Mudança de horário (o consumo mudou de hora)", indefinida:"Mudança de nível sem padrão claro" };
const FONTES_INCERTEZA = { medidor:"Exatidão do medidor", modelo:"Erro do modelo", faltantes:"Dados faltantes preenchidos" };
const PERFIS = { geral:"Geral (IPMVP)", pee:"PEE (ANEEL)" };
function cusum(v, p, media, desvio) { v = v.filter(x => x != null); if (v.length < 3) return { alarme: false, indice: null, lado: null };
  const mu = media == null ? v.reduce((s, x) => s + x, 0) / v.length : media, sd = (desvio == null ? Math.sqrt(v.reduce((s, x) => s + (x - mu) ** 2, 0) / v.length) : desvio) || 1, k = p["validacao.cusum_k"], h = p["validacao.cusum_h"];
  let sp = 0, sn = 0, idx = null, lado = null; v.forEach((x, i) => { const z = (x - mu) / sd; sp = Math.max(0, sp + z - k); sn = Math.max(0, sn - z - k); if (idx == null && (sp > h || sn > h)) { idx = i; lado = sp > h ? "acima" : "abaixo"; } });
  return { alarme: idx != null, indice: idx, lado, s_mais: sp, s_menos: sn }; }
function intervaloPrevisao(yh, se, n, p) { const d = tStudent(p["validacao.ip_confianca_pct"], Math.max(1, n - 2)) * se * Math.sqrt(1 + 1 / Math.max(1, n)); return [yh - d, yh + d]; }
function fddIntervalo(serie, se, n, p, tarifa) { const nmin = Math.round(p["validacao.fdd_dias_min"]), out = []; let cur = [];
  serie.concat([null]).forEach(s => { if (s) { const [lo, hi] = intervaloPrevisao(s.esperado, se, n, p); if (s.medido > hi || s.medido < lo) { cur.push(Object.assign({}, s, { lim_inf: lo, lim_sup: hi, lado: s.medido > hi ? "acima" : "abaixo" })); return; } }
    if (cur.length >= nmin) { const exc = cur.reduce((a, c) => a + (c.lado === "acima" ? c.medido - c.lim_sup : 0), 0), e = cur.reduce((a, c) => a + c.esperado, 0), m = cur.reduce((a, c) => a + c.medido, 0);
      out.push({ inicio: cur[0].dia, fim: cur[cur.length - 1].dia, dias: cur.length, esperado: e, medido: m, desvio_pct: e ? (m - e) / e * 100 : null, lado: cur[0].lado, excesso: exc, rs_em_risco: tarifa != null ? exc * tarifa : null }); }
    cur = []; });
  return out; }
const ordenarPorRisco = a => a.slice().sort((x, y) => ((x.rs_em_risco == null) - (y.rs_em_risco == null)) || ((y.rs_em_risco || 0) - (x.rs_em_risco || 0)) || ((y.excesso || 0) - (x.excesso || 0)));
function projecaoPersistencia(serie, total, meta, tarifa) { const d = serie.length; if (!d) return { projetada: null, meta, risco: null }; const acc = serie[d - 1].acumulada, proj = acc / d * total;
  return { ate_agora: acc, dias: d, dias_total: total, projetada: proj, meta, risco: meta == null ? null : proj < meta, falta: meta == null ? null : Math.max(0, meta - proj), rs_em_risco: meta == null || tarifa == null ? null : Math.max(0, meta - proj) * tarifa }; }
function gauss(r) { let u = 0, v = 0; while (!u) u = r(); while (!v) v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }
function monteCarlo(a, p, semente, so) { const r = rng(semente), n = Math.round(p["validacao.mc_n"]), rh = Math.max(-0.9, Math.min(0.9, a.rho || 0)), sMod = a.erro_padrao * Math.sqrt(a.m_dias * (1 + rh) / (1 - rh)),
    sMed = a.exatidao_pct != null ? a.exatidao_pct / 100 / 1.96 : 0, sFal = a.erro_padrao * Math.sqrt(Math.max(0, a.imputados)), usa = f => so == null || so === f, am = [];
  for (let i = 0; i < n; i++) am.push(a.esperado + (usa("modelo") ? gauss(r) * sMod : 0) - a.medido * (1 + (usa("medidor") ? gauss(r) * sMed : 0)) - (usa("faltantes") ? gauss(r) * sFal : 0));
  am.sort((x, y) => x - y); const q = (100 - p["validacao.mc_confianca_pct"]) / 200, m = am.reduce((s, x) => s + x, 0) / n;
  return { economia: a.esperado - a.medido, media: m, ic_inf: am[Math.floor(q * (n - 1))], ic_sup: am[Math.floor((1 - q) * (n - 1))], confianca_pct: p["validacao.mc_confianca_pct"], n, desvio: Math.sqrt(am.reduce((s, x) => s + (x - m) ** 2, 0) / n), exatidao_conhecida: a.exatidao_pct != null }; }
function sensibilidade(a, p, semente) { const v = Object.fromEntries(Object.keys(FONTES_INCERTEZA).map(f => [f, monteCarlo(a, p, semente, f).desvio ** 2])), tot = Object.values(v).reduce((s, x) => s + x, 0) || 1;
  return Object.keys(v).map(f => ({ fonte: f, nome: FONTES_INCERTEZA[f], variancia: v[f], parte_pct: v[f] / tot * 100 })).sort((x, y) => y.variancia - x.variancia); }
function detectarNre(res, espMedio, p) { const nmin = Math.round(p["validacao.nre_dias_min"]), v = res.map(x => x[1]), n = v.length; if (n < 2 * nmin || !espMedio) return null; let best = null;
  const mean = a => a.reduce((s, x) => s + x, 0) / a.length, pvar = a => { const m = mean(a); return a.reduce((s, x) => s + (x - m) ** 2, 0) / a.length; };
  for (let i = nmin; i <= n - nmin; i++) { const a = v.slice(0, i), b = v.slice(i), sd = Math.sqrt((pvar(a) * a.length + pvar(b) * b.length) / n) || 1e-9, tt = Math.abs(mean(b) - mean(a)) / (sd * Math.sqrt(1 / a.length + 1 / b.length)); if (!best || tt > best[0]) best = [tt, i, mean(a), mean(b)]; }
  const [tt, i, ma, mb] = best, nivel = mb - ma; if (tt < p["validacao.nre_z"] || Math.abs(nivel) / espMedio * 100 < p["validacao.nre_limite_pct"]) return null;
  return { inicio: res[i][0], dias_depois: n - i, nivel_dia: nivel, t: tt, nivel_pct: nivel / espMedio * 100, classe: "indefinida", classe_nome: CLASSES_NRE.indefinida, impacto: nivel * (n - i), ajuste_proposto: nivel * (n - i), situacao: "pendente" }; }
/* amostragem: fórmula estatística GENÉRICA (não é a da ANEEL) */
function tamanhoAmostra(N, cv, conf, prec) { const z = invNormal(0.5 + conf / 200), n0 = (z * cv / (prec / 100)) ** 2; return N ? Math.max(1, Math.min(N, Math.ceil(n0 / (1 + n0 / N)))) : 0; }
function precisaoAlcancada(N, n, media, desvio, conf) { if (!n || !media || !N) return null; return invNormal(0.5 + conf / 200) * (desvio / media) / Math.sqrt(n) * Math.sqrt(Math.max(0, 1 - n / N)) * 100; }
function resumoPee(pee, p) { pee = pee || {}; const cm = pee.custo_mv, ct = pee.custo_total, parte = cm != null && ct ? cm / ct * 100 : null, lim = p["validacao.pee.custo_mv_max_pct"] == null ? null : p["validacao.pee.custo_mv_max_pct"];
  const conf = pee.confianca_pct, prec = pee.precisao_pct, est = (pee.estratos || []).map(e => Object.assign({}, e, conf != null && prec != null ? { n_amostra: tamanhoAmostra(e.N, e.cv || 0.5, conf, prec), precisao_alcancada_pct: e.media ? precisaoAlcancada(e.N, e.n_medido || 0, e.media, e.desvio || 0, conf) : null } : {}));
  return Object.assign({}, pee, { custo_check: { parte_pct: parte, limite_pct: lim, situacao: parte == null ? "sem dado" : lim == null ? "aguardando Guia" : parte <= lim ? "dentro" : "fora do limite" },
    amostragem: { ok: conf != null && prec != null, estratos: est, populacao: est.reduce((s, e) => s + (e.N || 0), 0), amostra_total: est.reduce((s, e) => s + (e.n_amostra || 0), 0) },
    aguardando_guia: PREMISSAS_PEE.filter(k => p[k] == null) }); }

/* ════════ Utilidades da tela ════════ */
const E = s => typeof esc === "function" ? esc(s) : String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));
const N = (v, c) => typeof n2 === "function" ? n2(v, c) : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c });
const f = (v, c) => v == null || !isFinite(v) ? "—" : N(v, c == null ? 0 : c);
const fs = (v, c) => v == null || !isFinite(v) ? "—" : (v > 0 ? "+" : v < 0 ? "−" : "") + N(Math.abs(v), c == null ? 1 : c);
const num = s => { if (s == null || String(s).trim() === "") return null; const v = typeof numBr === "function" ? numBr(s) : parseFloat(String(s).replace(",", ".")); return v == null || !isFinite(v) ? null : v; };
const U = () => (typeof ui !== "undefined" && ui) ? ui : (window.__vaUi = window.__vaUi || {});
const pega = id => document.getElementById(id);
const redesenhar = () => { if (typeof desenhar === "function") desenhar(false); };
const emHub = () => U().modo === "hub";
const mesBr = m => m ? m.slice(5, 7) + "/" + m.slice(0, 4) : "—";
const casas = un => un === "tCO₂e" ? 2 : 0;
function centro() { try { if (typeof localDaInstalacao === "function") { const l = localDaInstalacao(); if (l && l.lat != null) return { lat: +l.lat, lon: +l.lon }; } } catch (e) {} return { lat: -22.5051, lon: -43.1784 }; }
function cacheLer() { try { return JSON.parse(localStorage.getItem(CHAVE) || "null") || {}; } catch (e) { return {}; } }
function cacheGravar(o) { try { localStorage.setItem(CHAVE, JSON.stringify(o)); } catch (e) {} }
const abaAtiva = id => { try { return typeof abasAtivas === "function" && abasAtivas().some(a => a[0] === id); } catch (e) { return false; } };
function ultimoMesCompleto() { const d = new Date(Date.now() - 3 * 3600 * 1000); let a = d.getUTCFullYear(), m = d.getUTCMonth(); if (m === 0) { a--; m = 12; } return a + "-" + String(m).padStart(2, "0"); }

/* ════════ Demonstração: Casa Physis SIMULADA (nunca vai para o Carbono, a Gestão nem um laudo) ════════ */
function rng(sem) { let h = 1779033703 ^ sem.length; for (let i = 0; i < sem.length; i++) { h = Math.imul(h ^ sem.charCodeAt(i), 3432918353); h = h << 13 | h >>> 19; }
  return () => { h = Math.imul(h ^ h >>> 16, 2246822507); h = Math.imul(h ^ h >>> 13, 3266489909); h ^= h >>> 16; return (h >>> 0) / 4294967296; }; }
/* valores SIMULADOS só desta demonstração (não são premissas nem dados de cliente) */
const SIM = { tarifa_kwh: 0.95, meta_kwh: 1500, kwp: 5.4, pr: 0.78, h_reserva: [5.6, 5.8, 5.0, 4.4, 3.7, 3.4, 3.6, 4.3, 4.6, 5.0, 5.3, 5.5], turbina_kwh_30d: 520,
  cdd: [205, 185, 170, 120, 75, 45, 40, 55, 80, 115, 150, 190], kwh_fixo: 780, kwh_por_gd: 2.4, efic: 0.88, pessoas: 5,
  caminhao: { esp: 28, km: 1800 }, trator: { esp: 9, h: 60 }, mes_clima: 4, mes_offline: 7, dias_offline: 9, mes_frota: 9, premissa_de: 8 };
function demoMundo() { const u = U(), fim = ultimoMesCompleto(); if (u.vaDemo && u.vaDemo.fim === fim) return u.vaDemo;
  const r = rng("validacao-casa-physis-" + fim), ruido = a => 1 + (r() * 2 - 1) * a, m24 = mesesAte(fim, 24), meses = m24.slice(12), c = centro(), anoTipico = mes => new Date(Date.UTC(2025, +mes, 0)).getUTCDate();
  let H = null; try { if (typeof solMensal === "function") H = solMensal(c.lat, 0.5); } catch (e) {} if (!Array.isArray(H) || H.length !== 12 || H.some(x => !(x > 0))) H = SIM.h_reserva;
  const MM = Array.from({ length: 12 }, (_, i) => String(i + 1).padStart(2, "0")), moy = mes => +mes.slice(5, 7) - 1;
  /* solar: geração planejada = kWp × H × dias × PR; irradiação medida pela estação (um mês nublado) */
  const plSol = Object.fromEntries(MM.map((k, i) => [k, SIM.kwp * H[i] * anoTipico(k) * SIM.pr])), climaSol = Object.fromEntries(MM.map((k, i) => [k, H[i]]));
  const medSol = {}, irr = {}; meses.forEach((m, k) => { const h = H[moy(m)] * (k === SIM.mes_clima ? 0.72 : ruido(0.04)); irr[m] = h; medSol[m] = { valor: planoDoMes(plSol, m) * (h / H[moy(m)]) * diasDoMes(m) / anoTipico(m.slice(5, 7)) * ruido(0.02), dias: diasDoMes(m), dias_mes: diasDoMes(m) }; });
  /* turbinas: energia planejada pelos dias do mês; um mês com o nó desligado (poucos dias com leitura) */
  const plTur = Object.fromEntries(MM.map(k => [k, SIM.turbina_kwh_30d * anoTipico(k) / 30])), medTur = {};
  meses.forEach((m, k) => { const dm = diasDoMes(m), d = k === SIM.mes_offline ? SIM.dias_offline : dm; medTur[m] = { valor: SIM.turbina_kwh_30d * dm / 30 * d / dm * ruido(0.04), dias: d, dias_mes: dm }; });
  /* energia e AVAC: linha de base y = fixo + k × graus-dia (24 meses); no relatório, a medida de eficiência; um mês de calor; ocupação acima da premissa nos últimos meses */
  const cdd = {}, kwh = {}, kwhMes = kwh; m24.forEach((m, i) => { const k = i - 12, g = SIM.cdd[moy(m)] * (k === 1 ? 1.4 : ruido(0.08)); cdd[m] = g;
    kwh[m] = (SIM.kwh_fixo + SIM.kwh_por_gd * g) * (k >= 0 ? SIM.efic : 1) * (k >= SIM.premissa_de ? 1.22 : 1) * ruido(0.03); });
  const plEne = Object.fromEntries(MM.map((k, i) => [k, (SIM.kwh_fixo + SIM.kwh_por_gd * SIM.cdd[i]) * SIM.efic])), climaEne = Object.fromEntries(MM.map((k, i) => [k, SIM.cdd[i]]));
  const medEne = Object.fromEntries(meses.map(m => [m, { valor: kwh[m], dias: diasDoMes(m), dias_mes: diasDoMes(m) }]));
  /* água: plano = premissa de consumo por pessoa × pessoas, igual todo mês; o medido segue a estação */
  const pc = premissa("agua.per_capita") || 130, plAgua = Object.fromEntries(MM.map(k => [k, pc * SIM.pessoas * 365 / 12 / 1000]));
  const medAgua = Object.fromEntries(meses.map(m => [m, { valor: planoDoMes(plAgua, m) * (1 + 0.2 * Math.cos(2 * Math.PI * moy(m) / 12)) * ruido(0.03), dias: diasDoMes(m), dias_mes: diasDoMes(m) }]));
  /* frota: consumo esperado do cadastro × km (ou horas); o caminhão gasta demais num mês */
  const fr = (id, nome, comb, esp, base, porH, salto) => { const plano = {}, medido = {}, extra = {};
    meses.forEach((m, k) => { const b = base * ruido(porH ? 0.2 : 0.15), l = esp * b / (porH ? 1 : 100) * (k === salto ? 1.38 : ruido(0.05)); plano[m] = esp * b / (porH ? 1 : 100);
      medido[m] = { valor: l, dias: null, dias_mes: diasDoMes(m) }; extra[m] = { base: b, unidade_base: porH ? "h" : "km", consumo_medido: porH ? l / b : l / b * 100, consumo_esperado: esp, combustivel: comb }; });
    return { item: id, nome, ativo: "", grandeza: "combustivel_l", fonte: "Frota e combustível · consumo esperado do cadastro (SIMULADO)", premissa: "", plano, medido, extra, combustivel: comb }; };
  const frota = [fr("veiculo-1", "Caminhão (SIMULADO)", "diesel_b", SIM.caminhao.esp, SIM.caminhao.km, false, SIM.mes_frota), fr("veiculo-2", "Trator (SIMULADO)", "diesel_b", SIM.trator.esp, SIM.trator.h, true, -1)];
  const itens = {
    solar: [{ item: "usina-telhado", nome: "Usina do telhado (SIMULADA)", ativo: "lugar01-no84", grandeza: "energia", fonte: "Energia solar · dimensionamento (SIMULADO)", premissa: "", plano: plSol, clima_esperado: climaSol, medido: medSol, clima: irr }],
    agua: [{ item: "hidrometro-geral", nome: "Hidrômetro geral (SIMULADO)", ativo: "lugar01-no85", grandeza: "vazao", fonte: "Premissa de consumo por pessoa × moradores (SIMULADO)", premissa: "agua.per_capita", plano: plAgua, medido: medAgua }],
    energia: [{ item: "quadro-geral", nome: "Quadro geral e AVAC (SIMULADO)", ativo: "lugar01-no84", grandeza: "energia", fonte: "Projeto de AVAC e linha de base (SIMULADO)", premissa: "ocupação de projeto (SIMULADA)", plano: plEne, clima_esperado: climaEne, medido: medEne, clima: cdd }],
    turbinas: [{ item: "turbina-descida", nome: "Turbina da descida de água (SIMULADA)", ativo: "lugar01-no86", grandeza: "energia", fonte: "Turbinas · energia planejada (SIMULADO)", premissa: "", plano: plTur, medido: medTur }],
    frota, carbono: [] };
  itens.carbono = itensCarbono(itens.energia, frota, meses);
  const base = ipmvpRegressao(m24.slice(0, 12).map(m => ({ mes: m, y: kwh[m], x: cdd[m] })), meses.map(m => ({ mes: m, y: kwh[m], x: cdd[m] })), P(), 0);
  u.vaDemo = { fim, meses, m24, itens, base, kwhMes, base_var: "graus_dia", base_item: "Quadro geral e AVAC (SIMULADO)", base_periodo: [m24[0], m24[11], meses[0], meses[11]] };
  return u.vaDemo; }
/* Carbono: kWh × fator da rede e litros × fatores de combustão do Carbono (espelho de Validacao.itens_carbono) */
function fatorRede() { try { const C = window.PhysisCarbono, F = C && C.base ? C.base() : null; return F && F.rede ? F.rede.anual[F.rede.padrao].valor : null; } catch (e) { return null; } }
function itensCarbono(energia, frota, meses) { const out = [], fr = fatorRede();
  if (fr != null) energia.filter(it => it.plano).forEach(it => { const plano = {}, med = {}; meses.forEach(m => { const v = planoDoMes(it.plano, m), x = ((it.medido || {})[m] || {});
      if (v != null) plano[m] = v * fr / 1000; med[m] = { valor: x.valor == null ? null : x.valor * fr / 1000, dias: x.dias == null ? null : x.dias, dias_mes: diasDoMes(m) }; });
    out.push({ item: "rede-" + it.item, nome: (it.nome || it.item) + " · rede elétrica", ativo: it.ativo || "", grandeza: "tco2e", fonte: "Energia × fator da rede do Carbono", premissa: "", plano, medido: med }); });
  frota.filter(it => it.plano).forEach(it => { let k = null; try { const r = window.FROTA && FROTA.co2e ? FROTA.co2e(it.combustivel || "diesel_b", 1) : null; k = r && r.t != null ? r.t : null; } catch (e) {} if (k == null) return;
    const plano = {}, med = {}; Object.keys(it.plano).forEach(m => plano[m] = it.plano[m] * k); Object.keys(it.medido || {}).forEach(m => med[m] = { valor: it.medido[m].valor == null ? null : it.medido[m].valor * k, dias: null, dias_mes: diasDoMes(m) });
    out.push({ item: "comb-" + it.item, nome: it.nome + " · combustível", ativo: it.ativo || "", grandeza: "tco2e", fonte: "Frota × fatores de combustão móvel do Carbono", premissa: "", plano, medido: med }); });
  return out; }

/* M&V da Casa Physis SIMULADA: plano, medidores, dados de 15 min com defeitos de propósito, dias para o modelo diário */
function demoMv(w, est) { if (w.mv) return w.mv; const r = rng("validacao-mv-" + w.fim), ruido = a => 1 + (r() * 2 - 1) * a, p = P();
  const pm = { escopo: "Casa Physis (SIMULADA): quadro geral com o AVAC, usina do telhado, turbina e hidrômetro.", fronteira: "Medidor geral de energia na entrada e hidrômetro geral (SIMULADOS).",
    opcao: "C", justificativa: "Medidas que se misturam no mesmo quadro: só a instalação inteira mostra o efeito (SIMULADO).", metodo: "Linha de base diária com ponto de mudança na temperatura do ar; economia pela equação geral.",
    fontes: ["lugar01-no84 (energia, 15 min)", "lugar01-no85 (água, mensal)", "lugar01-no81-ar (temperatura do ar)"], variaveis_independentes: ["Temperatura média do dia (graus-dia)"], fatores_estaticos: ["Área climatizada", "Ocupantes", "Horário de uso"],
    base_ini: w.m24[0], base_fim: w.m24[11], rel_ini: w.meses[0], rel_fim: w.meses[11], papeis: [{ papel: "coleta", pessoa: "Arthur", competencia: "" }, { papel: "analise", pessoa: "Erick Lopes", competencia: "" }, { papel: "arquivo", pessoa: "Rafael", competencia: "" }, { papel: "relatorio", pessoa: "Rafael", competencia: "" }],
    formato: "Relatório padrão ODT e PDF/A", periodicidade: "Mensal, com fechamento anual", politica_faltantes: "excluir", tarifa_kwh: SIM.tarifa_kwh, tarifa_fonte: "SIMULADA", meta_economia: SIM.meta_kwh, cmms_automatico: false, perfil: "pee",
    pee: { energia_economizada_mwh_ano: 1.6, reducao_demanda_ponta_kw: 0.9, rcb: null, rcb_entradas: {}, custo_mv: 1200, custo_total: 18000, erro_pct: null, precisao_pct: 10, confianca_pct: 90, fonte: "SIMULADO",
      estratos: [{ nome: "Lâmpadas (SIMULADO)", N: 120, cv: 0.5, n_medido: 30, media: 9.5, desvio: 2.1 }, { nome: "Geladeiras (SIMULADO)", N: 40, cv: 0.4, n_medido: 0 }] }, qa: ["Conferir a calibração dos medidores", "Conferir a perda de dados do mês", "Revisar os pontos marcados na limpeza"],
    revisao_anual: w.meses[11].slice(0, 4) + "-12-15", ecms: [{ id: "avac-eficiente", nome: "AVAC eficiente (SIMULADO)" }, { id: "led", nome: "Iluminação LED (SIMULADO)" }], area_m2: 220, ocupantes: 5, simulacao: null };
  const hoje = new Date().toISOString().slice(0, 10), tsOf = d => Date.UTC(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10), 12) / 1000;
  const meds = [{ ativo: "lugar01-no84", tipo: "Medidor de energia (SIMULADO)", modelo: "[CONFERIR]", exatidao_pct: 1.0, incerteza_pct: 1.0, comissionamento: w.m24[0] + "-05", cal_ultima: w.m24[0] + "-05", cal_proxima: w.m24[12] + "-05", certificado_nome: "certificado-simulado.pdf", certificado_sha256: "9f2b6c1e0d4a7e3b5c8f1a2d4e6b8c0a1f3e5d7c9b2a4c6e8f0a1b3c5d7e9f1a" },
    { ativo: "lugar01-no85", tipo: "Hidrômetro (SIMULADO)", modelo: "[CONFERIR]", exatidao_pct: null, incerteza_pct: null, comissionamento: w.m24[0] + "-05", cal_ultima: null, cal_proxima: null, certificado_nome: null, certificado_sha256: null },
    { ativo: "lugar01-no86", tipo: "Medidor da turbina (SIMULADO)", modelo: "[CONFERIR]", exatidao_pct: 2.0, incerteza_pct: 2.0, comissionamento: w.m24[0] + "-05", cal_ultima: w.m24[0] + "-05", cal_proxima: w.meses[3] + "-05", certificado_nome: "certificado-simulado-2.pdf", certificado_sha256: "1a3c5e7f9b2d4f6a8c0e1b3d5f7a9c2e4b6d8f0a2c4e6b8d0f1a3c5e7b9d2f4a" }].map(m => Object.assign(m, { alertas: alertasMedidor(m, hoje) }));
  /* 7 dias de leituras de 15 min com uma lacuna, um salto, um trecho travado, um carimbo repetido e uma leitura negativa no hidrômetro */
  const t0 = tsOf(w.meses[11] + "-01"), q15 = []; for (let k = 0; k < 672; k++) { if (k >= 300 && k < 324) continue; const h = (k % 96) / 4;
    q15.push({ id: 10000 + k, ts: t0 + k * 900, valor: +((2.4 + 3.2 * Math.max(0, Math.sin(Math.PI * (h - 7) / 12))) * ruido(0.08)).toFixed(3) }); }
  q15[100].valor = 48.0; for (let k = 400; k < 420; k++) q15[k].valor = 3.111; q15.push({ id: 20000, ts: q15[50].ts, valor: 2.5 });
  const lq = limparSerie(q15, p, "energia", [0, 500], Date.now() / 1000), mens = w.meses.map((m, i) => ({ id: 30000 + i, ts: tsOf(m + "-28"), valor: i === 5 ? -3 : 18 + 4 * r() }));
  const lm = limparSerie(mens, p, "vazao", [0, 100], Date.now() / 1000), resumoQ = (at, it, q) => ({ ativo: at, item: it, granularidade: q.granularidade, passo_s: q.passo_s, n: q.n, validos: q.validos, perda_pct: q.perda_pct, perda_ok: q.perda_ok, resumo: q.resumo, lacunas: q.lacunas.length, exemplos: q.pontos.filter(o => o.marcas.length).slice(0, 12) });
  /* dias: temperatura e consumo SIMULADOS; ano de base e ano de relatório (com a medida de eficiência e uma semana gastando demais) */
  const dias = []; let d = new Date(Date.UTC(+w.m24[0].slice(0, 4), +w.m24[0].slice(5, 7) - 1, 1)); const fimD = new Date(Date.UTC(+w.fim.slice(0, 4), +w.fim.slice(5, 7), 0));
  for (let i = 0; d <= fimD; i++, d = new Date(d.getTime() + 86400000)) { const dia = d.toISOString().slice(0, 10), doy = (d - new Date(Date.UTC(d.getUTCFullYear(), 0, 1))) / 86400000, T = 21 + 5 * Math.cos(2 * Math.PI * (doy - 15) / 365) + (r() * 2 - 1) * 2.5;
    const rel = dia.slice(0, 7) >= w.meses[0], y = ((22 + 2.6 * Math.max(0, T - 19.5)) * (rel ? 0.88 : 1) * (rel && i % 365 >= 200 && i % 365 < 205 ? 1.35 : 1) + (rel && i % 365 >= 240 ? 4.0 : 0)) * ruido(0.04); dias.push({ dia, x: T, y }); }
  const base = dias.filter(x => x.dia.slice(0, 7) <= pm.base_fim), relD = dias.filter(x => x.dia.slice(0, 7) >= pm.rel_ini), esc = escolherModelo(base.map(x => x.x), base.map(x => x.y), p), mod = esc.escolhido;
  if (mod) esc.aceite = aceite(mod, p, p["validacao.aceite_cvrmse_diario_max_pct"]);
  const serie = economiaAcumulada(mod, relD), espT = serie.reduce((s, x) => s + x.esperado, 0), econ = serie.length ? serie[serie.length - 1].acumulada : null, res = mod ? base.map(x => x.y - prever(mod, x.x)) : [];
  const inc = incertezaEconomia(mod && mod.metricas.cv_rmse_pct, base.length, serie.length, econ != null && espT ? econ / espT : null, p, mod ? mod.metricas.p : 2, autocorrelacao(res));
  /* núcleo M&V 2.0 da demonstração: modelo do relatório (retreinado), FDD contra o intervalo de previsão, Monte Carlo, CUSUM, NRE */
  const mrel = escolherModelo(relD.map(x => x.x), relD.map(x => x.y), p).escolhido, serieRel = economiaAcumulada(mrel, relD), tarifa = SIM.tarifa_kwh;
  const mcArgs = { esperado: espT, medido: espT - (econ || 0), m_dias: serie.length, erro_padrao: mod ? mod.metricas.erro_padrao : 0, rho: autocorrelacao(res), exatidao_pct: 1.0, imputados: 9 };
  const mc = mod ? monteCarlo(mcArgs, p, "demo-mc-" + w.fim) : null, sens = mod ? sensibilidade(mcArgs, p, "demo-mc-" + w.fim) : [];
  const resR = serie.map(s => s.medido - s.esperado), dMod = cusum(resR, p, resR.length >= 30 ? resR.slice(0, 30).reduce((s, x) => s + x, 0) / 30 : null, mod ? mod.metricas.erro_padrao : null);
  const nre = detectarNre(serie.map(s => [s.dia, s.medido - s.esperado]), espT / Math.max(1, serie.length), p); if (nre) { nre.classe = "equipamento_novo"; nre.classe_nome = CLASSES_NRE.equipamento_novo; nre.chave = "demo-nre"; nre.item = "quadro-geral"; }
  const proj = projecaoPersistencia(serie, serie.length, SIM.meta_kwh, tarifa), fat = w.meses.slice(-6).map((m, i) => { const iv = relD.filter(x => x.dia.slice(0, 7) === m).reduce((s, x) => s + x.y, 0), f2 = iv * (i === 4 ? 1.07 : 1 + (r() - 0.5) * 0.02); return { mes: m, fatura: f2, intervalo: iv, diferenca_pct: (iv - f2) / f2 * 100 }; });
  const alarmes = ordenarPorRisco(fddIntervalo(serieRel, mrel ? mrel.metricas.erro_padrao : 0, relD.length, p, tarifa).filter(x => x.lado === "acima").map(tr => { const cs = causas({ mes: tr.inicio, planejado: tr.esperado, medido: tr.medido, pct: tr.desvio_pct, abs: tr.medido - tr.esperado, cobertura_pct: null }, [], { sentido: "consumir", sinal: 1, clima: null }, p);
    return Object.assign({}, tr, { chave: "demo-" + tr.inicio, item: "quadro-geral", causa: cs[0].codigo, causa_nome: cs[0].nome, acao: ACOES[cs[0].codigo], tarefa: false }); }));
  const semDados = m => m ? Object.fromEntries(Object.entries(m).filter(([k]) => k !== "dados")) : null;
  const mv2 = [{ item: "quadro-geral", nome: "Quadro geral e AVAC (SIMULADO)", ativo: "lugar01-no84", modelo: semDados(mod), candidatos: esc.candidatos.map(semDados), aceite: esc.aceite, n_base: base.length, economia_acumulada: serie, economia: econ, esperado: espT, incerteza: inc, alarmes,
    aceite_minimo: { ok: !!mod && ((mod.metricas.r2 || 0) > p["validacao.aceite_r2_min"] || (mod.metricas.cv_rmse_pct || 99) < p["validacao.aceite_cvrmse_ou_max_pct"]) }, fonte_temperatura: "estação do lugar (SIMULADA)", granularidade: "15 min", politica_faltantes: "excluir", politica_nome: POLITICAS.excluir,
    imputados: 9, monte_carlo: mc, sensibilidade: sens, deriva_modelo: dMod, deriva_sensor: Object.assign(cusum(fat.map(f => (f.intervalo - f.fatura) / f.fatura), p, 0, 0.01), { referencia: "fatura" }), nres: nre ? [nre] : [], ajuste_nao_rotineiro: 0, economia_ajustada: econ,
    projecao: proj, fatura: fat, modelo_versao: mod ? { hash: "SIMULADO-" + w.fim, ciclo: w.fim } : null, unidade: "kWh", periodo: [relD[0].dia, relD[relD.length - 1].dia] }];
  const insp = [{ id: 1, ecm: "avac-eficiente", operando: true, obs: "SIMULADO", dia: w.meses[9] + "-10", por: "Arthur" }];
  const soma = (mod, a, b) => { const m = est.modulos.find(x => x.modulo === mod); const v = m ? m.linhas.filter(l => l.medido != null && l.mes >= a && l.mes <= b).reduce((s, l) => s + l.medido, 0) : 0; return v || null; };
  const kwhB = w.m24.slice(0, 12).reduce((s, m) => s + (w.kwhMes[m] || 0), 0), km = w.itens.frota.reduce((s, it) => s + w.meses.reduce((a, m) => a + (((it.extra || {})[m] || {}).unidade_base === "km" ? it.extra[m].base : 0), 0), 0);
  const en = enpis(pm, { energia_kwh: kwhB || null }, { energia_kwh: soma("energia", pm.rel_ini, pm.rel_fim), agua_m3: soma("agua", pm.rel_ini, pm.rel_fim), frota_l: w.itens.frota[0].medido ? w.meses.reduce((s, m) => s + (w.itens.frota[0].medido[m].valor || 0), 0) : null, frota_km: km || null });
  const tarefas = [{ tipo: "calibracao", situacao: "atrasada", ativo: "lugar01-no86", texto: "lugar01-no86: calibração vencida." }, { tipo: "calibracao", situacao: "pendente", ativo: "lugar01-no85", texto: "lugar01-no85: sem data da próxima calibração [CONFERIR]." },
    { tipo: "inspecao", situacao: "pendente", ecm: "led", texto: "Inspeção periódica da medida Iluminação LED (SIMULADO): confirmar que continua operando." }];
  w.mv = { plano_mv: { atual: pm, versao: 2, versoes: [{ versao: 1, motivo: "Plano inicial (SIMULADO)", por: "Rafael", quando: tsOf(w.m24[0] + "-02"), registro: "simulado-0001" }, { versao: 2, motivo: "Períodos de base e de relatório definidos (SIMULADO)", por: "Rafael", quando: tsOf(w.meses[0] + "-02"), registro: "simulado-0002" }] },
    opcoes_ipmvp: OPCOES_IPMVP, papeis: PAPEIS, medidores: meds, qualidade: [resumoQ("lugar01-no84", "quadro-geral", lq), resumoQ("lugar01-no85", "hidrometro-geral", lm)], enpis: en, mv2, inspecoes: insp,
    licoes: [{ id: 1, texto: "SIMULADO: o hidrômetro sem calibração deixa a água fora do relatório de economia até ter certificado.", quando: tsOf(w.meses[6] + "-03"), por: "Erick Lopes" }], tarefas,
    rastreio: { versao_codigo: VERSAO_CODIGO, plano_mv_versao: 2, fator_rede_tco2_mwh: fatorRede(), premissas: p, periodos: { base: [pm.base_ini, pm.base_fim], relatorio: [pm.rel_ini, pm.rel_fim] }, "leituras.simuladas": "dados SIMULADOS (sem leituras do hub)", ["modelo.quadro-geral"]: mod ? { tipo: mod.tipo, coef: mod.coef, pontos_de_mudanca: mod.cps, versao: VERSAO_CODIGO } : null },
    secoes_relatorio: SECOES_RELATORIO, versao_codigo: VERSAO_CODIGO, perfis: PERFIS, pee: resumoPee(pm.pee, p) };
  return w.mv; }
function estadoDemo() { const w = demoMundo(), p = P(), a = alfaFrota(), memo = w.fim + "|" + JSON.stringify(p) + "|" + (fatorRede() || "");
  if (w.memo === memo && w.est) return w.est;
  w.itens.carbono = itensCarbono(w.itens.energia, w.itens.frota, w.meses);
  w.est = { ok: true, demo: true, meses: w.meses, premissas: p, modulos: Object.keys(MODULOS).map(k => analisarModulo(k, w.itens[k], w.meses, p, a)),
    planos: Object.values(w.itens).flat().filter(it => it.plano && !/^(rede|comb)-/.test(it.item)).map(it => ({ id: 0, modulo: Object.keys(w.itens).find(k => w.itens[k].includes(it)), item: it.item, nome: it.nome, ativo: it.ativo, fonte: it.fonte, premissa: it.premissa })) };
  w.mv = null; Object.assign(w.est, demoMv(w, w.est));
  w.memo = memo; return w.est; }

/* ════════ Dados do hub ════════ */
let csrf = null;
async function api(metodo, url, corpo) { const op = { credentials:"same-origin", cache:"no-store" };
  if (metodo === "POST") { if (csrf == null) { try { const i = await fetch("/api/instancia", op).then(r => r.json()); csrf = i.csrf || ""; } catch (e) { csrf = ""; } }
    op.method = "POST"; op.headers = { "Content-Type": "application/json" }; if (csrf) op.headers["X-Physis-CSRF"] = csrf; op.body = JSON.stringify(corpo || {}); }
  let r, j = {}; try { r = await fetch(url, op); try { j = await r.json(); } catch (e) {} } catch (e) { return { ok: false, erro: "sem ligação com o computador central", rede: true }; }
  if (r && !r.ok && j.ok == null) j.ok = false; return j; }
function carregar(forcar) { const u = U(), c = u.vaEst || {}; if (!emHub()) return;
  if (!forcar && (c.carregando || (c.em && Date.now() - c.em < 60000))) return;
  u.vaEst = Object.assign({}, c, { carregando: true });
  api("GET", "api/validacao/estado?meses=12").then(j => { if (j && j.ok) { u.vaEst = { em: Date.now(), dados: j }; cacheGravar({ estado: j, em: Date.now() }); }
    else { const k = cacheLer(); u.vaEst = { em: Date.now(), dados: k.estado || null, offline: !!j.rede, erro: j.erro || "" }; } redesenhar(); }); }
/* O que a tela usa: { est, demo, semPlano, offline, carregando } */
function fonte() { const u = U();
  if (emHub()) { carregar(false); const c = u.vaEst || {}, d = c.dados;
    if (d && d.modulos && d.modulos.some(m => m.tem_plano)) return { est: d, demo: false, offline: !!c.offline };
    if (!d && c.carregando) return { est: null, carregando: true };
    return { est: estadoDemo(), demo: true, semPlano: true, hub: d }; }
  return { est: estadoDemo(), demo: true }; }

/* ════════ Desenho ════════ */
const tabela = (cap, cab, linhas) => `<div class="rolagem"><table><caption>${E(cap)}</caption><thead><tr>${cab.map(h => `<th scope="col">${E(h)}</th>`).join("")}</tr></thead><tbody>${linhas.join("")}</tbody></table></div>`;
const pares = (cap, ls) => `<table class="va-ev"><caption class="so-leitor">${E(cap)}</caption><tbody>${ls.filter(Boolean).map(([k, v]) => `<tr><th scope="row">${E(k)}</th><td>${v}</td></tr>`).join("")}</tbody></table>`;
function situacao(m, p) { if (!m.tem_plano) return ["Sem plano", "in"]; if (m.quando && m.quando.continua) return ["Fora do plano agora", "al"]; if (m.quando) return ["Saiu do plano no período", "at"]; return ["Dentro do plano", "ok"]; }
function aviso(F) { if (F.carregando) return ""; const u = U();
  if (F.demo) return `<div class="faixa at" role="note"><strong>Dados SIMULADOS da Casa Physis.</strong> <span>${F.semPlano ? "Nenhum plano gravado neste computador central: grave o planejado na parte Planejado para ver a sua instalação." : "Abra a plataforma instalada para ver o planejado e o medido da sua instalação."}</span> <span>Os números simulados nunca vão para o Carbono, a Gestão nem um relatório de verdade.</span></div>`;
  if (F.offline) return `<div class="faixa at" role="status"><span>Sem ligação com o computador central: mostrando a última cópia guardada neste aparelho.</span></div>`; return ""; }
function cartaoModulo(m, p) { const [st, cls] = situacao(m, p), t = m.total;
  return `<section class="cartao" aria-labelledby="h-va-r-${m.modulo}"><h3 id="h-va-r-${m.modulo}" class="t3">${E(m.nome)}</h3><p><span class="selo ${cls}">${E(st)}</span></p>
    ${m.tem_plano ? `<p><span class="numero">${fs(t.pct, 1)} %</span> <span class="t2">${E(m.unidade)}</span></p>${pares("Totais do período", [["Planejado", `${f(t.planejado, casas(m.unidade))} ${E(m.unidade)}`], ["Medido", `${f(t.medido, casas(m.unidade))} ${E(m.unidade)}`], ["Meses comparados", f(t.meses, 0)]])}
      ${m.quando ? `<p class="t2 pq"><span>Primeiro mês fora do limite:</span> <strong>${mesBr(m.quando.primeiro_mes)}</strong></p>` : ""}
      <div><button type="button" data-va-mod="${m.modulo}" id="va-ver-${m.modulo}">Ver o módulo</button></div>` : `<p class="t2">${E(m.sem_plano)}</p>`}</section>`; }
function grafico(m, p) { const ls = m.linhas, un = m.unidade, W = 640, H = 240, mg = { l: 56, r: 12, t: 14, b: 34 }, vals = ls.flatMap(l => [l.planejado, l.medido]).filter(v => v != null), y1 = (Math.max(...vals, 0) || 1) * 1.12;
  const bw = (W - mg.l - mg.r) / ls.length, sy = y => H - mg.b - y / y1 * (H - mg.t - mg.b), cx = i => mg.l + (i + 0.5) * bw;
  const barras = ls.map((l, i) => l.medido == null ? "" : `<rect x="${(cx(i) - bw * 0.32).toFixed(1)}" y="${sy(l.medido).toFixed(1)}" width="${(bw * 0.64).toFixed(1)}" height="${(H - mg.b - sy(l.medido)).toFixed(1)}" style="fill:var(--marca,#4A8A5A)${fora(l, p) ? ";stroke:var(--al-t,#7A2214);stroke-width:3" : ""}"><title>${E(mesBr(l.mes) + " · " + f(l.medido, casas(un)) + " " + un)}</title></rect>`).join("");
  const pts = ls.map((l, i) => l.planejado == null ? null : `${cx(i).toFixed(1)},${sy(l.planejado).toFixed(1)}`).filter(Boolean).join(" ");
  const marcas = ls.map((l, i) => fora(l, p) ? `<text x="${cx(i).toFixed(1)}" y="${(Math.min(sy(l.medido || 0), l.planejado != null ? sy(l.planejado) : H) - 6).toFixed(1)}" font-size="13" font-weight="700" text-anchor="middle" style="fill:var(--al-t,#7A2214)">!</text>` : "").join("");
  const rot = ls.map((l, i) => i % 2 ? "" : `<text x="${cx(i).toFixed(1)}" y="${H - 12}" font-size="11" text-anchor="middle" style="fill:var(--tinta2,#4A4F44)">${E(l.mes.slice(5, 7) + "/" + l.mes.slice(2, 4))}</text>`).join("");
  return `<figure style="margin:0"><svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px" role="img" aria-label="${E(m.nome)}" aria-describedby="va-tab-${m.modulo}">
    <line x1="${mg.l}" y1="${H - mg.b}" x2="${W - mg.r}" y2="${H - mg.b}" style="stroke:var(--linha,#D9D3C2)"/><text x="${mg.l - 6}" y="${mg.t + 8}" font-size="11" text-anchor="end" style="fill:var(--tinta2,#4A4F44)">${f(y1, casas(un))}</text><text x="${mg.l - 6}" y="${H - mg.b}" font-size="11" text-anchor="end" style="fill:var(--tinta2,#4A4F44)">0</text>
    ${barras}<polyline points="${pts}" fill="none" style="stroke:var(--agua,#546A7B)" stroke-width="2.5" stroke-dasharray="6 4"/>${ls.map((l, i) => l.planejado == null ? "" : `<circle cx="${cx(i).toFixed(1)}" cy="${sy(l.planejado).toFixed(1)}" r="3.5" style="fill:var(--agua,#546A7B)"/>`).join("")}${marcas}${rot}</svg>
    <figcaption class="t2 pq"><span>${E(un)}</span> <span>Barras: medido.</span> <span>Linha tracejada azul: planejado.</span> <span>Barra com borda e ponto de exclamação: mês fora do limite.</span></figcaption></figure>`; }
function textoCausa(c) { const ev = c.evidencia || {};
  if (c.codigo === "falha_dado") return pares("Evidência", [["Dias com leitura", `${f(ev.dias, 0)} / ${f(ev.dias_mes, 0)}`], ["Dias com leitura (%)", `${f(ev.cobertura_pct, 0)} %`], ["Mínimo para o mês valer", `${f(ev.cobertura_min_pct, 0)} %`]]);
  if (c.codigo === "clima") return pares("Evidência", [["Variável do clima", E(NOME_CLIMA[ev.variavel] || ev.variavel)], ["Medido", f(ev.medido, 2)], ["Esperado no plano", f(ev.esperado, 2)], ["Diferença", `${fs(ev.diferenca_pct, 0)} %`]]);
  if (c.codigo === "consumo_anormal") return pares("Evidência", [["Razão medido ÷ planejado no mês", f(ev.razao, 2)], ["Mediana da razão nos meses anteriores", f(ev.mediana, 2)], ["Meses no histórico", f(ev.n, 0)], ["z robusto", f(ev.z, 1)]]);
  if (c.codigo === "premissa") return pares("Evidência", [["Meses seguidos no mesmo sentido", f(ev.meses, 0)], ["Desvio médio nesses meses", `${fs(ev.media_pct, 1)} %`], ["Variação da razão medido ÷ planejado", `${f(ev.cv_pct, 0)} %`], ev.premissa ? ["Premissa do plano", E(ev.premissa)] : null]);
  if (c.codigo === "sazonal") return pares("Evidência", [["Planejado", E("igual todo mês")], ["Média medida no período", f(ev.media_medida, 1)], ["Medido no mês", f(ev.medido, 1)]]);
  return `<p class="t2">Nenhuma regra explica o desvio: confira em campo.</p>`; }
const NIV = { alta:["Confiança alta", "ok"], "média":["Confiança média", "at"], baixa:["Confiança baixa", "in"], "—":["Sem confiança", "in"] };
function cartaoPorque(m, x) { const c = x.como, top = x.causas[0];
  return `<section class="cartao" aria-labelledby="h-va-pq-${m.modulo}-${x.mes}"><h4 id="h-va-pq-${m.modulo}-${x.mes}" class="t3"><span>${mesBr(x.mes)}</span> · <span>${fs(x.pct, 1)} %</span></h4>
    <p><strong>Quanto:</strong> <span>${fs(x.abs, casas(m.unidade))} ${E(m.unidade)}</span></p>
    ${c ? `<p><strong>Como:</strong></p>${pares("Como", [["Equipamento", E(c.nome)], c.ativo ? ["Medidor", `<code>${E(c.ativo)}</code>`] : null, ["Variável", `<code>${E(c.variavel)}</code>`], ["Parte do desvio do mês", `${f(c.parte_pct, 0)} %`]])}` : ""}
    <p><strong>Por quê:</strong></p><ol class="va-causas">${x.causas.map(k => { const [rot, cls] = NIV[k.nivel] || NIV["—"]; return `<li><p><strong>${E(k.nome)}</strong> <span class="selo ${cls}">${E(rot)}</span> <span class="t2 pq">${k.confianca ? f(k.confianca, 2) : ""}</span></p>${textoCausa(k)}</li>`; }).join("")}</ol>
    ${top && top.codigo === "nao_identificada" ? `<p class="t2 pq">Causa não identificada é uma resposta válida: o sistema não inventa um motivo.</p>` : ""}</section>`; }
function parteModulo(F) { const u = U(), est = F.est, p = est.premissas || P(), ms = est.modulos, sel = ms.some(m => m.modulo === u.vaMod) ? u.vaMod : (ms.find(m => m.tem_plano) || ms[0]).modulo, m = ms.find(x => x.modulo === sel);
  const escolha = `<div class="precos"><div><label for="va-mod">Módulo</label><select id="va-mod" data-va-k="mod" style="width:100%">${ms.map(x => `<option value="${x.modulo}" ${x.modulo === sel ? "selected" : ""}>${E(x.nome)}</option>`).join("")}</select></div></div>`;
  if (!m.tem_plano) return `<section class="cartao" aria-labelledby="h-va-m"><h2 id="h-va-m">${E(m.nome)}</h2>${escolha}<div class="faixa in" role="status"><strong>Sem plano.</strong> <span>${E(m.sem_plano)}</span></div>${m.itens_sem_plano && m.itens_sem_plano.length ? `<p class="t2">Itens medidos sem planejado: <span>${E(m.itens_sem_plano.join(", "))}</span></p>` : ""}</section>`;
  const un = m.unidade, cs = casas(un), q = m.quando;
  const lin = m.linhas.map(l => `<tr><th scope="row">${mesBr(l.mes)}</th><td>${f(l.planejado, cs)}</td><td>${f(l.medido, cs)}</td><td>${fs(l.abs, cs)}</td><td>${l.pct == null ? "—" : fs(l.pct, 1) + " %"}</td><td>${l.cobertura_pct == null ? "—" : f(l.cobertura_pct, 0) + " %"}</td><td>${fora(l, p) ? `<span class="selo al">fora</span>` : `<span class="selo ok">dentro</span>`}</td></tr>`);
  const its = m.itens.map(it => `<li><strong>${E(it.nome)}</strong>${it.ativo ? ` <code>${E(it.ativo)}</code>` : ""}<br><span class="t2 pq"><span>Fonte do planejado:</span> <span>${E(it.fonte)}</span>${it.premissa ? ` · <span>Premissa:</span> <span>${E(it.premissa)}</span>` : ""}</span></li>`).join("");
  const quandoTxt = q ? pares("Quando", [["Primeiro mês fora do limite", `<strong>${mesBr(q.primeiro_mes)}</strong>`], ["Meses seguidos fora", f(q.duracao_meses, 0)], ["Continua fora no último mês", E(q.continua ? "sim" : "não")], ["Trechos fora do limite no período", f(q.trechos.length, 0)]])
    : `<div class="faixa ok" role="status"><span>Todos os meses dentro do limite de</span> <strong>${f(p["validacao.desvio_limite_pct"], 0)} %</strong><span>.</span></div>`;
  return `<section class="cartao" aria-labelledby="h-va-m"><h2 id="h-va-m">${E(m.nome)}</h2>${escolha}${grafico(m, p)}
    <h3 class="t3">Quanto: planejado × medido, mês a mês</h3>${tabela("Planejado, medido e desvio por mês", ["Mês", "Planejado (" + un + ")", "Medido (" + un + ")", "Desvio (" + un + ")", "Desvio (%)", "Dias com leitura", "Situação"], lin).replace("<div class=\"rolagem\"><table>", `<div class="rolagem"><table id="va-tab-${m.modulo}">`)}
    <p class="t2 pq">Desvio = medido − planejado; a porcentagem é sobre o planejado. Limite: <span>${f(p["validacao.desvio_limite_pct"], 0)} %</span> <span>(premissa a conferir).</span></p>
    <h3 class="t3">Quando</h3>${quandoTxt}
    <h3 class="t3">De onde vem cada número</h3><ul>${its}</ul></section>
    ${m.explicacoes.length ? `<section class="cartao" aria-labelledby="h-va-pq"><h2 id="h-va-pq">Como e por quê, em cada mês fora do limite</h2><p class="t2 apoio">Cada causa vem de uma regra com evidência. A confiança vai de 0 a 1; a causa de cima é a mais provável.</p><div class="grade">${m.explicacoes.map(x => cartaoPorque(m, x)).join("")}</div></section>` : ""}`; }
function parteResumo(F) { const est = F.est, p = est.premissas || P(), ms = est.modulos, fm = ms.filter(m => m.quando), sp = ms.filter(m => !m.tem_plano);
  return `<section class="cartao" aria-labelledby="h-va-res"><h2 id="h-va-res">Resumo dos últimos 12 meses</h2>
    <p class="t2"><span>De</span> <strong>${mesBr(est.meses[0])}</strong> <span>a</span> <strong>${mesBr(est.meses[est.meses.length - 1])}</strong><span>.</span> <span>Módulos fora do plano em algum mês:</span> <strong>${fm.length}</strong><span>.</span> <span>Módulos sem plano:</span> <strong>${sp.length}</strong><span>.</span></p>
    <div class="grade">${ms.map(m => cartaoModulo(m, p)).join("")}</div></section>
    <section class="cartao" aria-labelledby="h-va-rel"><h2 id="h-va-rel">Relatório de medição e verificação</h2><p class="t2 apoio">Planejado × medido de cada módulo, os meses fora do limite com o como e o por quê, e a linha de base no estilo do IPMVP. Formatos abertos: Documento (ODT) e PDF/A.</p>
      <div class="chips" role="group" aria-label="Baixar o relatório"><button type="button" id="va-b-odt" data-va-acao="odt">Baixar o relatório (ODT)</button><button type="button" id="va-b-pdf" data-va-acao="pdf">Baixar o relatório (PDF/A)</button></div>
      <p id="va-rel-msg" class="t2" role="status">${E(U().vaRelMsg || "")}</p>${F.demo ? `<p class="t2 pq">Na demonstração, o relatório sai marcado como SIMULADO.</p>` : ""}</section>
    <section class="cartao" aria-labelledby="h-va-lim"><h2 id="h-va-lim">Limites usados</h2>${tabela("Limites das regras (premissas, todas a conferir)", ["Limite", "Valor", "Situação"], [
      ["Desvio que conta como fora do plano (%)", f(p["validacao.desvio_limite_pct"], 0)], ["Dias com leitura para o mês valer (%)", f(p["validacao.cobertura_min_pct"], 0)], ["Diferença do clima que explica o desvio (%)", f(p["validacao.clima_min_pct"], 0)],
      ["Meses seguidos para apontar premissa", f(p["validacao.premissa_meses_min"], 0)], ["Variação máxima da razão nesses meses (%)", f(p["validacao.premissa_variacao_max_pct"], 0)], ["Plano igual todo mês: variação até (%)", f(p["validacao.plano_plano_max_pct"], 0)],
      ["Consumo fora do normal: z robusto maior que", f(p["validacao.anomalia_z"], 1)], ["Meses de histórico antes de dizer o normal", f(p["validacao.anomalia_amostra_min"], 0)], ["Base dos graus-dia (°C)", f(p["validacao.grau_dia_base_c"], 1)],
      ["Meses mínimos da linha de base", f(p["validacao.baseline_meses_min"], 0)], ["CV(RMSE) máximo da linha de base (%)", f(p["validacao.baseline_cvrmse_max_pct"], 0)]].map(([n, v]) => `<tr><th scope="row">${E(n)}</th><td>${v}</td><td><span class="selo at">conferir</span></td></tr>`))}</section>`; }
function resultadoBase(r, un) { if (!r) return ""; const m = r.modelo, e = r.economia, av = (m.avisos || (m.aviso ? [m.aviso] : []));
  if (m.a == null) return `<div class="faixa at" role="status"><span>Poucos meses com consumo e variável: a regressão precisa de pelo menos 3.</span></div>`;
  const avTxt = av.map(a => a === "curta" ? "Base mais curta que o recomendado (um ciclo inteiro de operação)." : a === "cv" ? "CV(RMSE) acima do limite: o modelo explica pouco o consumo." : a === "poucos" ? "Poucos meses." : a);
  return `${pares("Modelo da linha de base", [["Inclinação (a)", f(m.a, 3)], ["Intercepto (b)", f(m.b, 1)], ["r²", f(m.r2, 3)], ["CV(RMSE) (%)", f(m.cv_rmse_pct, 1)], ["Meses na base", f(m.n, 0)]])}
    ${avTxt.length ? `<div class="faixa at" role="note">${avTxt.map(t => `<span>${E(t)}</span>`).join(" ")}</div>` : `<div class="faixa ok" role="status"><span>Linha de base dentro dos critérios (premissas a conferir).</span></div>`}
    ${tabela("Economia pela equação geral do IPMVP", ["Grandeza", "Valor"], [["Linha de base (soma medida na base)", f(r.base, 0) + " " + un], ["Período de relatório (soma medida)", f(r.relatorio, 0) + " " + un], ["Esperado pela linha de base nas condições do relatório", f(r.esperado_relatorio, 0) + " " + un], ["Ajuste rotineiro", fs(r.ajuste_rotineiro, 0) + " " + un], ["Ajuste não rotineiro", fs(r.ajuste_nao_rotineiro, 0) + " " + un], ["Economia", `<strong>${f(e.econ, 0)} ${un}</strong>`], ["Economia (%)", f(e.pct, 1) + " %"]].map(([k, v]) => `<tr><th scope="row">${E(k)}</th><td>${v}</td></tr>`))}
    <p class="t2 pq">Economia = (linha de base − período de relatório) ± ajustes: a mesma equação da aba Certificações. O ajuste rotineiro leva a linha de base às condições do período de relatório.</p>`; }
function parteBase(F) { const u = U(), est = F.est, p = est.premissas || P();
  const cert = abaAtiva("certificacoes") ? `<div><button type="button" data-aba="certificacoes">Abrir Certificações · Medição e verificação (IPMVP)</button></div>` : "";
  const intro = `<p class="t2 apoio">O consumo esperado aprende com os dados do próprio lugar: uma regressão linear simples do consumo de cada mês do período de base contra a variável que o move (graus-dia, irradiação ou produção). No período de relatório, a linha de base diz quanto se gastaria sem a medida, nas mesmas condições.</p>`;
  if (F.demo) { const w = demoMundo(), [b0, b1, r0, r1] = w.base_periodo;
    return `<section class="cartao" aria-labelledby="h-va-b"><h2 id="h-va-b">Linha de base (IPMVP)</h2>${intro}${pares("Linha de base simulada", [["Equipamento", E(w.base_item)], ["Variável", E(VARIAVEIS_BASE[w.base_var])], ["Período de base", `${mesBr(b0)} → ${mesBr(b1)}`], ["Período de relatório", `${mesBr(r0)} → ${mesBr(r1)}`]])}${resultadoBase(w.base, "kWh")}${cert}</section>`; }
  const ps = (est.planos || []).filter(x => x.id), fm = u.vaB || {}, opc = ps.map(x => `<option value="${x.id}" ${String(fm.plano) === String(x.id) ? "selected" : ""}>${E((MODULOS[x.modulo] || {}).nome || x.modulo)} · ${E(x.nome || x.item)}</option>`).join("");
  const mesCampo = (k, rot) => `<div><label for="va-b-${k}">${rot}</label><input id="va-b-${k}" type="month" data-va-k="b-${k}" value="${E(fm[k] || "")}" style="width:100%"></div>`;
  return `<section class="cartao" aria-labelledby="h-va-b"><h2 id="h-va-b">Linha de base (IPMVP)</h2>${intro}
    ${ps.length ? `<div class="precos"><div><label for="va-b-plano">Equipamento com planejado</label><select id="va-b-plano" data-va-k="b-plano" style="width:100%">${opc}</select></div>
      <div><label for="va-b-var">Variável que move o consumo</label><select id="va-b-var" data-va-k="b-var" style="width:100%">${Object.entries(VARIAVEIS_BASE).map(([k, n]) => `<option value="${k}" ${fm.var === k ? "selected" : ""}>${E(n)}</option>`).join("")}</select></div>
      ${mesCampo("base_ini", "Período de base: primeiro mês")}${mesCampo("base_fim", "Período de base: último mês")}${mesCampo("rel_ini", "Período de relatório: primeiro mês")}${mesCampo("rel_fim", "Período de relatório: último mês")}</div>
      <div><button type="button" id="va-b-calc" data-va-acao="base">Calcular a linha de base</button></div><p class="t2" role="status">${E(u.vaBMsg || "")}</p>${u.vaBRes ? resultadoBase(u.vaBRes, "") : ""}`
      : `<p class="t2">Grave um planejado (parte Planejado) com o medidor do equipamento para calcular a linha de base.</p>`}${cert}</section>`; }
function parsear12(s) { const v = String(s || "").split(";").map(x => num(x)); return v.length === 12 && v.every(x => x != null && x >= 0) ? v : null; }
function partePlanejado(F) { const u = U(), est = F.est, fm = u.vaPl || {}, ps = est.planos || [], MOD = ["solar", "agua", "energia", "turbinas"];
  const lista = ps.length ? tabela("Planejados gravados: módulo, equipamento, medidor e fonte", ["Módulo", "Equipamento", "Medidor", "Fonte", "Ações"], ps.map(x => `<tr><th scope="row">${E((MODULOS[x.modulo] || {}).nome || x.modulo)}</th><td>${E(x.nome || x.item)}</td><td>${x.ativo ? `<code>${E(x.ativo)}</code>` : "—"}</td><td>${E(x.fonte)}</td><td>${x.id && !F.demo ? `<button type="button" id="va-pl-del-${x.id}" data-va-acao="pl-remover" data-va-id="${x.id}" aria-label="${E("Apagar o planejado de " + (x.nome || x.item))}">Apagar</button>` : "—"}</td></tr>`)) : `<p class="t2">Nenhum planejado gravado.</p>`;
  const campo = (k, rot, ph, ajuda) => `<div><label for="va-pl-${k}">${rot}</label><input id="va-pl-${k}" type="text" data-va-k="pl-${k}" value="${E(fm[k] == null ? "" : fm[k])}" placeholder="${E(ph || "")}" style="width:100%"${ajuda ? ` aria-describedby="va-pl-${k}-aj"` : ""}>${ajuda ? `<p id="va-pl-${k}-aj" class="t2 pq">${ajuda}</p>` : ""}</div>`;
  const trazer = (abaAtiva("solar") && window.SOLAR ? `<button type="button" id="va-pl-solar" data-va-acao="trazer-solar">Trazer da aba Energia solar</button>` : "") + (abaAtiva("turbinas") && window.TURBINAS ? `<button type="button" id="va-pl-tur" data-va-acao="trazer-turbinas">Trazer da aba Turbinas</button>` : "");
  return `<section class="cartao" aria-labelledby="h-va-pl"><h2 id="h-va-pl">Planejado</h2><p class="t2 apoio">O planejado sai do dimensionamento de cada módulo, do Planejador ou de uma premissa, sempre com a fonte. Frota e Carbono vêm sozinhos: o consumo esperado de cada veículo e os fatores do Carbono.</p>${lista}</section>
    <section class="cartao" aria-labelledby="h-va-pln"><h2 id="h-va-pln">Gravar um planejado</h2>
      ${trazer ? `<div class="chips" role="group" aria-label="Trazer o planejado de outra aba">${trazer}</div>` : ""}
      <div class="precos"><div><label for="va-pl-modulo">Módulo</label><select id="va-pl-modulo" data-va-k="pl-modulo" style="width:100%">${MOD.map(k => `<option value="${k}" ${fm.modulo === k ? "selected" : ""}>${E(MODULOS[k].nome)}</option>`).join("")}</select></div>
      ${campo("item", "Código do equipamento", "ex.: usina-telhado")}${campo("nome", "Nome do equipamento", "ex.: Usina do telhado")}${campo("ativo", "Medidor no hub (ativo)", "ex.: lugar01-no84", "O ativo das leituras: lugar, nó e sufixo, como na tabela de medições.")}</div>
      ${campo("meses", "Planejado de janeiro a dezembro (12 valores com ponto e vírgula)", "ex.: 610; 580; 560; …", "Na unidade do módulo: kWh, m³.")}${campo("clima", "Clima esperado no plano (12 valores, opcional)", "ex.: 5,6; 5,8; …", "Irradiação em kWh/m²·dia (solar), chuva em mm (água) ou graus-dia (energia).")}
      ${campo("fonte", "Fonte do planejado", "ex.: Energia solar · dimensionamento de 10/2026")}${campo("premissa", "Premissa usada (opcional)", "ex.: agua.per_capita")}
      <div><button type="button" id="va-b-pl" data-va-acao="pl-gravar">Gravar o planejado</button></div><p class="t2" role="status">${E(u.vaPlMsg || "")}</p></section>`; }

/* ════════ Plano de M&V, medidores e dados, modelos e incerteza, painel M&V 2.0 ════════ */
const lista = v => (v || []).length ? `<ul>${v.map(x => `<li>${E(x)}</li>`).join("")}</ul>` : "—";
const NOME_ALERTA = { sem_calibracao:"Sem data de calibração [CONFERIR]", calibracao_vencida:"Calibração vencida", exatidao_desconhecida:"Exatidão desconhecida [CONFERIR]", sem_certificado:"Sem certificado" };
const NOME_MARCA = { ts_invalido:"Carimbo de tempo inválido", ts_futuro:"Carimbo de tempo no futuro", ts_duplicado:"Carimbo de tempo repetido", ts_fora_de_ordem:"Fora de ordem (usado na ordem certa)", impossivel:"Valor impossível", negativo:"Valor negativo", atipico:"Valor atípico", travado:"Sensor travado" };
const real = v => v == null || !isFinite(v) ? "—" : (typeof brl === "function" ? brl(Math.round(v * 100) / 100) : "R$ " + N(v, 2));
const dataBr2 = s => s ? String(s).slice(0, 10).split("-").reverse().join("/") : "—", quandoBr = ts => ts ? new Date(ts * 1000).toISOString().slice(0, 10).split("-").reverse().join("/") : "—";
function partePlanoMv(F) { const u = U(), est = F.est, pmv = est.plano_mv || {}, pm = pmv.atual, tar = est.tarefas || [];
  const corpo = pm ? `${pares("Plano de M&V", [["Escopo", E(pm.escopo)], ["Fronteira de medição", E(pm.fronteira)], ["Opção IPMVP", `<strong>${E(pm.opcao)}</strong> · <span>${E(OPCOES_IPMVP[pm.opcao] || "")}</span>`], ["Justificativa da opção", E(pm.justificativa)], ["Método de cálculo", E(pm.metodo)],
      ["Fontes de dados (medidores e pontos)", lista(pm.fontes)], ["Variáveis independentes", lista(pm.variaveis_independentes)], ["Fatores estáticos", lista(pm.fatores_estaticos)], ["Período de base", `${mesBr(pm.base_ini)} → ${mesBr(pm.base_fim)}`], ["Período de relatório", `${mesBr(pm.rel_ini)} → ${mesBr(pm.rel_fim)}`],
      ["Formato do relatório", E(pm.formato || "—")], ["Periodicidade", E(pm.periodicidade || "—")], ["Etapas de QA", lista(pm.qa)], ["Revisão anual", dataBr2(pm.revisao_anual)], ["Área (m²)", f(pm.area_m2, 0)], ["Ocupantes", f(pm.ocupantes, 0)]])}
    ${pm.opcao === "D" && pm.simulacao ? `<h3 class="t3">Simulação (opção D)</h3>${pares("Simulação", [["Programa", E(pm.simulacao.software)], ["Versão", E(pm.simulacao.versao)]])}${tabela("Cópias dos arquivos de entrada e saída", ["Arquivo", "Papel", "SHA-256"], pm.simulacao.arquivos.map(a => `<tr><th scope="row">${E(a.nome)}</th><td>${E(a.papel)}</td><td><code>${E(a.sha256)}</code></td></tr>`))}` : ""}
    <h3 class="t3">Pessoas e papéis</h3>${tabela("Quem coleta, analisa, arquiva e relata", ["Papel", "Pessoa", "Competência (CMVP ou equivalente)"], (pm.papeis || []).map(x => `<tr><th scope="row">${E(PAPEIS[x.papel] || x.papel)}</th><td>${E(x.pessoa || "[A DEFINIR]")}</td><td>${x.competencia ? E(x.competencia) : `<span class="t2">não informada</span>`}</td></tr>`))}
    <p class="t2 pq">A competência é só um campo: o sistema nunca supõe que alguém tem certificação.</p>${partePee(F, pm)}`
    : `<div class="faixa at" role="status"><span>Sem plano de M&V gravado nesta instalação.</span></div>`;
  const vers = (pmv.versoes || []).slice().reverse().map(v => `<tr><th scope="row">${f(v.versao, 0)}</th><td>${quandoBr(v.quando)}</td><td>${E(v.por)}</td><td>${E(v.motivo)}</td><td><code>${E(v.registro)}</code></td></tr>`);
  const insp = ((pm || {}).ecms || []).map(e => { const ult = (est.inspecoes || []).find(i => i.ecm === e.id); return `<tr><th scope="row">${E(e.nome || e.id)}</th><td>${ult ? dataBr2(ult.dia) : "—"}</td><td>${ult ? `<span class="selo ${ult.operando ? "ok" : "al"}">${ult.operando ? "operando" : "não operando"}</span>` : "—"}</td><td>${F.demo ? "—" : `<button type="button" data-va-acao="inspecao" data-va-ecm="${E(e.id)}" data-va-op="1" id="va-insp-${E(e.id)}">Operando</button> <button type="button" data-va-acao="inspecao" data-va-ecm="${E(e.id)}" data-va-op="0">Não operando</button>`}</td></tr>`; });
  return `<section class="cartao" aria-labelledby="h-va-pmv"><h2 id="h-va-pmv">Plano de M&V</h2><p class="t2 apoio">Um plano por instalação, guardado e versionado no computador central. Cada mudança vai para o registro encadeado do hub: quem, quando e por quê.</p>
      <p class="t2"><span>Versão atual:</span> <strong>${f(pmv.versao || 0, 0)}</strong></p>${corpo}</section>
    <section class="cartao" aria-labelledby="h-va-tar"><h2 id="h-va-tar">Tarefas</h2>${tar.length ? `<ul>${tar.map(x => `<li><span class="selo ${x.situacao === "atrasada" ? "al" : "at"}">${E(x.situacao)}</span> <span>${E(x.texto)}</span></li>`).join("")}</ul>` : `<p class="t2">Nada pendente.</p>`}</section>
    <section class="cartao" aria-labelledby="h-va-insp"><h2 id="h-va-insp">Inspeção periódica das medidas</h2><p class="t2 apoio">Confirma que cada medida de eficiência continua funcionando. Sem inspeção no prazo, vira tarefa.</p>${insp.length ? tabela("Medidas de eficiência e a última inspeção", ["Medida", "Última inspeção", "Situação", "Registrar"], insp) : `<p class="t2">O plano não lista medidas de eficiência.</p>`}<p class="t2" role="status">${E(u.vaInspMsg || "")}</p></section>
    <section class="cartao" aria-labelledby="h-va-ver"><h2 id="h-va-ver">Versões do plano</h2>${vers.length ? tabela("Versões do plano de M&V e o registro encadeado", ["Versão", "Quando", "Quem", "Por quê", "Registro"], vers) : `<p class="t2">Nenhuma versão ainda.</p>`}</section>
    ${formPlanoMv(F, pm)}
    <section class="cartao" aria-labelledby="h-va-lic"><h2 id="h-va-lic">Diário de lições aprendidas</h2>${(est.licoes || []).length ? `<ul>${est.licoes.map(l => `<li><span class="t2 pq">${quandoBr(l.quando)} · ${E(l.por)}</span><br><span>${E(l.texto)}</span></li>`).join("")}</ul>` : `<p class="t2">Nenhuma lição registrada.</p>`}
      <div><label for="va-lic-texto">Nova lição</label><textarea id="va-lic-texto" rows="2" style="width:100%"></textarea></div><div><button type="button" id="va-b-lic" data-va-acao="licao">Registrar a lição</button></div><p class="t2" role="status">${E(u.vaLicMsg || "")}</p></section>`; }
function partePee(F, pm) { const z = F.est.pee; if (!pm || pm.perfil !== "pee" || !z) return `<p class="t2"><span>Perfil do programa:</span> <strong>${E(PERFIS[(pm || {}).perfil || "geral"])}</strong></p>`;
  const cc = z.custo_check || {}, am = z.amostragem || {};
  return `<h3 class="t3">Perfil PEE (ANEEL)</h3><div class="faixa at" role="note"><span>As exigências numéricas do PEE (confiança, precisão, amostra, duração, vida útil, RCB, taxa e prazos) aguardam a leitura do Guia de M&V da ANEEL:</span> <strong>[MARCADOR]</strong></div>
    ${pares("Perfil PEE", [["Energia economizada (MWh/ano)", f(z.energia_economizada_mwh_ano, 1)], ["Redução de demanda na ponta (kW)", f(z.reducao_demanda_ponta_kw, 1)], ["Relação custo-benefício (RCB)", z.rcb == null ? "[MARCADOR]" : f(z.rcb, 2)], ["Custo da M&V ÷ custo total", `${f(cc.parte_pct, 1)} % · <span class="selo ${cc.situacao === "fora do limite" ? "al" : cc.situacao === "dentro" ? "ok" : "at"}">${E(cc.situacao)}</span>`], ["Erro alcançado (%)", f(z.erro_pct, 1)], ["Precisão (%)", f(z.precisao_pct, 1)], ["Confiança (%)", f(z.confianca_pct, 0)]])}
    ${am.estratos && am.estratos.length ? tabela("Plano amostral por estrato (fórmula estatística genérica, não a da ANEEL)", ["Estrato", "População", "Amostra", "Medidos", "Precisão alcançada"], am.estratos.map(e => `<tr><th scope="row">${E(e.nome)}</th><td>${f(e.N, 0)}</td><td>${f(e.n_amostra, 0)}</td><td>${f(e.n_medido, 0)}</td><td>${e.precisao_alcancada_pct == null ? "—" : f(e.precisao_alcancada_pct, 1) + " %"}</td></tr>`)) : ""}
    <p class="t2 pq">n₀ = (z·CV ÷ e)²; n = n₀ ÷ (1 + n₀ ÷ N)</p>`; }
function formPlanoMv(F, pm) { const u = U(), x = u.vaPmv || pm || {}, linhas = v => (v || []).join("\n");
  const txt = (k, rot, val, area) => `<div><label for="va-pmv-${k}">${rot}</label>${area ? `<textarea id="va-pmv-${k}" rows="3" style="width:100%">${E(val || "")}</textarea>` : `<input id="va-pmv-${k}" type="text" value="${E(val == null ? "" : val)}" style="width:100%">`}</div>`;
  const pap = Object.keys(PAPEIS).map(k => { const r = (x.papeis || []).find(y => y.papel === k) || {}; return `<div class="precos">${txt("p-" + k, "Pessoa: " + PAPEIS[k].toLowerCase(), r.pessoa)}${txt("c-" + k, "Competência (opcional)", r.competencia)}</div>`; }).join("");
  const sim = x.simulacao || {};
  return `<section class="cartao" aria-labelledby="h-va-pmvf"><h2 id="h-va-pmvf">Mudar o plano de M&V</h2><p class="t2 apoio">Listas: um item por linha. Arquivos da simulação: nome; SHA-256; entrada ou saída. Medidas: código; nome.</p>
    <div class="precos">${txt("escopo", "Escopo", x.escopo)}${txt("fronteira", "Fronteira de medição", x.fronteira)}<div><label for="va-pmv-opcao">Opção IPMVP</label><select id="va-pmv-opcao" style="width:100%">${Object.entries(OPCOES_IPMVP).map(([k, n]) => `<option value="${k}" ${x.opcao === k ? "selected" : ""}>${k} · ${E(n)}</option>`).join("")}</select></div>${txt("justificativa", "Justificativa da opção", x.justificativa)}${txt("metodo", "Método de cálculo", x.metodo)}</div>
    <div class="precos">${txt("fontes", "Fontes de dados (medidores e pontos)", linhas(x.fontes), true)}${txt("variaveis_independentes", "Variáveis independentes", linhas(x.variaveis_independentes), true)}${txt("fatores_estaticos", "Fatores estáticos", linhas(x.fatores_estaticos), true)}${txt("qa", "Etapas de QA", linhas(x.qa), true)}</div>
    <div class="precos">${["base_ini", "base_fim", "rel_ini", "rel_fim"].map(k => `<div><label for="va-pmv-${k}">${{ base_ini:"Período de base: primeiro mês", base_fim:"Período de base: último mês", rel_ini:"Período de relatório: primeiro mês", rel_fim:"Período de relatório: último mês" }[k]}</label><input id="va-pmv-${k}" type="month" value="${E(x[k] || "")}" style="width:100%"></div>`).join("")}<div><label for="va-pmv-revisao_anual">Revisão anual</label><input id="va-pmv-revisao_anual" type="date" value="${E(x.revisao_anual || "")}" style="width:100%"></div></div>
    <div class="precos">${txt("formato", "Formato do relatório", x.formato)}${txt("periodicidade", "Periodicidade", x.periodicidade)}${txt("area_m2", "Área (m²)", x.area_m2)}${txt("ocupantes", "Ocupantes", x.ocupantes)}</div>
    ${txt("ecms", "Medidas de eficiência (ECM)", (x.ecms || []).map(e => e.id + "; " + e.nome).join("\n"), true)}
    <h3 class="t3">Pessoas e papéis</h3>${pap}
    <h3 class="t3">Opção D: simulação</h3><div class="precos">${txt("sw", "Programa de simulação", sim.software)}${txt("swv", "Versão do programa", sim.versao)}</div>${txt("arqs", "Arquivos de entrada e saída", (sim.arquivos || []).map(a => a.nome + "; " + a.sha256 + "; " + a.papel).join("\n"), true)}
    ${txt("motivo", "Por que mudou (vai para o registro)", u.vaPmvMotivo || "")}
    <div><button type="button" id="va-b-pmv" data-va-acao="pmv-gravar">Gravar nova versão do plano</button></div><p class="t2" role="status">${E(u.vaPmvMsg || "")}</p></section>`; }
function parteMedidores(F) { const u = U(), est = F.est, p = est.premissas || P(), ms = est.medidores || [], q = est.qualidade || [];
  const linM = ms.map(m => `<tr><th scope="row"><code>${E(m.ativo)}</code></th><td>${E(m.tipo || "—")}</td><td>${E(m.modelo || "—")}</td><td>${m.exatidao_pct == null ? "—" : f(m.exatidao_pct, 1) + " %"}</td><td>${m.incerteza_pct == null ? "—" : f(m.incerteza_pct, 1) + " %"}</td><td>${dataBr2(m.comissionamento)}</td><td>${dataBr2(m.cal_ultima)}</td><td>${dataBr2(m.cal_proxima)}</td><td>${m.certificado_sha256 ? `<code title="${E(m.certificado_sha256)}">${E(m.certificado_sha256.slice(0, 12))}…</code>` : "—"}</td><td>${(m.alertas || []).length ? m.alertas.map(a => `<span class="selo ${a.tipo === "calibracao_vencida" ? "al" : "at"}">${E(NOME_ALERTA[a.tipo] || a.tipo)}</span>`).join(" ") : `<span class="selo ok">em dia</span>`}</td></tr>`);
  const linQ = q.map(x => `<tr><th scope="row"><code>${E(x.ativo)}</code></th><td>${E(x.granularidade)}</td><td>${f(x.n, 0)}</td><td>${f(x.validos, 0)}</td><td>${f(x.perda_pct, 1)} %</td><td><span class="selo ${x.perda_ok ? "ok" : "al"}">${x.perda_ok ? "dentro" : "fora do limite"}</span></td><td>${Object.entries(x.resumo || {}).map(([k, n]) => `<span>${E(NOME_MARCA[k] || k)}</span>: <strong>${n}</strong>`).join("<br>") || "—"}</td></tr>`);
  const ex = q.flatMap(x => (x.exemplos || []).map(o => `<tr><th scope="row"><code>${E(x.ativo)}</code></th><td>${o.ts ? new Date(o.ts * 1000).toISOString().slice(0, 16).replace("T", " ") : "—"}</td><td>${o.original == null ? "—" : f(o.original, 3)}</td><td>${o.valor == null ? "não usado" : f(o.valor, 3)}</td><td>${o.marcas.map(m => E(NOME_MARCA[m] || m)).join(", ")}</td></tr>`));
  const campo = (k, rot, tipo) => `<div><label for="va-md-${k}">${rot}</label><input id="va-md-${k}" type="${tipo || "text"}" style="width:100%"></div>`;
  return `<section class="cartao" aria-labelledby="h-va-med"><h2 id="h-va-med">Medidores</h2><p class="t2 apoio">Tipo, modelo, exatidão e incerteza, data de comissionamento, última e próxima calibração e o certificado (arquivo resumido em SHA-256 neste aparelho).</p>${ms.length ? tabela("Cadastro de medidores e alertas de calibração", ["Medidor", "Tipo", "Modelo", "Exatidão", "Incerteza", "Comissionamento", "Última calibração", "Próxima calibração", "Certificado", "Alertas"], linM) : `<p class="t2">Nenhum medidor cadastrado.</p>`}
      <h3 class="t3">Cadastrar ou mudar um medidor</h3><div class="precos">${campo("ativo", "Medidor no hub (ativo)")}${campo("tipo", "Tipo")}${campo("modelo", "Modelo")}${campo("exatidao_pct", "Exatidão (%)")}${campo("incerteza_pct", "Incerteza (%)")}${campo("comissionamento", "Comissionamento", "date")}${campo("cal_ultima", "Última calibração", "date")}${campo("cal_proxima", "Próxima calibração", "date")}${campo("certificado", "Certificado de calibração (arquivo)", "file")}</div>
      <div><button type="button" id="va-b-md" data-va-acao="medidor">Gravar o medidor</button></div><p class="t2" role="status">${E(u.vaMdMsg || "")}</p></section>
    <section class="cartao" aria-labelledby="h-va-qd"><h2 id="h-va-qd">Qualidade dos dados</h2><p class="t2 apoio">A granularidade nativa fica como veio (15 min, hora ou só o mês). A limpeza marca lacunas, valores atípicos, carimbos de tempo, sensor travado e valores negativos ou impossíveis; o valor original fica sempre ao lado e nada é trocado em silêncio.</p>
      <p class="t2"><span>Plano de coleta: perda de dados máxima de</span> <strong>${f(p["validacao.perda_dados_max_pct"], 0)} %</strong> <span>(premissa a conferir).</span></p>
      ${linQ.length ? tabela("Qualidade por medidor: granularidade, perda e marcas", ["Medidor", "Granularidade nativa", "Leituras", "Válidas", "Perda de dados", "Situação", "Marcas"], linQ) : `<p class="t2">Sem leituras.</p>`}
      ${ex.length ? `<details><summary>Ver os pontos marcados (original e marca)</summary>${tabela("Pontos marcados na limpeza", ["Medidor", "Quando (UTC)", "Original", "Usado", "Marcas"], ex)}</details>` : ""}</section>`; }
function parteModelos(F) { const est = F.est, mv = est.mv2 || [], en = est.enpis || [];
  const MOT = { r2: "R² baixo", cv_rmse: "CV(RMSE) alto", nmbe: "NMBE alto", "sem modelo": "sem modelo" };
  const blocos = mv.map(x => { const esc = x.modelo, i = x.incerteza || {};
    const lin = (x.candidatos || []).map(m => `<tr><th scope="row">${E(m.tipo)}${m.forma && m.forma !== m.tipo ? ` <span class="t2">(${E(m.forma)})</span>` : ""}</th><td>${f(m.metricas.r2, 3)}</td><td>${f(m.metricas.cv_rmse_pct, 1)} %</td><td>${fs(m.metricas.nmbe_pct, 2)} %</td><td>${f(m.metricas.erro_padrao, 2)}</td><td>${(m.cps || []).map(c => f(c, 1)).join(" · ") || "—"}</td><td>${esc && esc.tipo === m.tipo ? `<span class="selo ok">escolhido</span>` : "—"}</td></tr>`);
    return `<section class="cartao" aria-labelledby="h-va-mo-${E(x.item)}"><h2 id="h-va-mo-${E(x.item)}">${E(x.nome)}</h2><p class="t2"><span>Dias no período de base:</span> <strong>${f(x.n_base, 0)}</strong></p>
      ${lin.length ? tabela("Modelos com ponto de mudança (2P a 5P) e o de vizinhos, pelo ajuste", ["Modelo", "R²", "CV(RMSE)", "NMBE", "Erro padrão", "Ponto(s) de mudança (°C)", "Escolha"], lin) : `<p class="t2">Poucos dias com consumo e temperatura no período de base.</p>`}
      <p>${x.aceite && x.aceite.ok ? `<span class="selo ok">Modelo aceito</span>` : `<span class="selo al">Modelo fora dos critérios</span> <span class="t2">${E(((x.aceite || {}).motivos || []).map(m => MOT[m] || m).join(", "))}</span>`}</p>
      <h3 class="t3">Incerteza da economia</h3>${i.incerteza_pct == null ? `<p class="t2">Sem economia no período de relatório para calcular a incerteza.</p>` : `<p><span class="numero">${f(i.incerteza_pct, 1)} %</span> <span class="selo ${i.veredito === "dentro" ? "ok" : "al"}">${E(i.veredito)}</span></p>
      ${pares("Incerteza", [["Nível de confiança", f(i.confianca_pct, 0) + " %"], ["Limite (parte da economia)", f(i.limite_pct, 0) + " %"], ["t de Student", f(i.t, 3)], ["Autocorrelação dos resíduos", f(i.rho, 2)], ["Dias efetivos na base", f(i.n_efetivo, 0)]])}`}</section>`; }).join("");
  const linE = en.map(e => `<tr><th scope="row">${E(e.enpi)}</th><td>${f(e.base, 2)}</td><td>${f(e.relatorio, 2)}</td><td>${e.variacao_pct == null ? "—" : fs(e.variacao_pct, 1) + " %"}</td><td>${E(e.fonte_normalizador)}</td></tr>`);
  return `${blocos || `<section class="cartao" aria-labelledby="h-va-mo"><h2 id="h-va-mo">Modelos e incerteza</h2><p class="t2">Defina os períodos de base e de relatório no plano de M&V e grave um planejado de energia ou água com o medidor.</p></section>`}
    <section class="cartao" aria-labelledby="h-va-enpi"><h2 id="h-va-enpi">Indicadores de desempenho (EnPI) e linha de base energética (EnB)</h2><p class="t2 apoio">No conceito da ISO 50006 (citada só pelo nome): consumo dividido pelo que o explica, no período de base e no de relatório.</p>${tabela("EnPI: base × relatório", ["EnPI", "Base", "Relatório", "Variação", "Normalizador"], linE)}</section>`; }
function graficoAcumulado(s) { if (!s.length) return ""; const W = 640, H = 200, mg = { l: 60, r: 10, t: 12, b: 26 }, ys = s.map(x => x.acumulada), y0 = Math.min(0, ...ys), y1 = Math.max(0, ...ys) || 1;
  const sx = i => mg.l + i / Math.max(1, s.length - 1) * (W - mg.l - mg.r), sy = y => H - mg.b - (y - y0) / (y1 - y0 || 1) * (H - mg.t - mg.b);
  return `<figure style="margin:0"><svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px" role="img" aria-label="Economia acumulada"><line x1="${mg.l}" x2="${W - mg.r}" y1="${sy(0).toFixed(1)}" y2="${sy(0).toFixed(1)}" style="stroke:var(--linha,#D9D3C2)"/>
    <polyline points="${s.map((x, i) => sx(i).toFixed(1) + "," + sy(x.acumulada).toFixed(1)).join(" ")}" fill="none" style="stroke:var(--marca,#4A8A5A)" stroke-width="2.5"/><text x="${mg.l - 6}" y="${mg.t + 8}" font-size="11" text-anchor="end" style="fill:var(--tinta2,#4A4F44)">${f(y1, 0)}</text><text x="${mg.l - 6}" y="${H - mg.b}" font-size="11" text-anchor="end" style="fill:var(--tinta2,#4A4F44)">${f(y0, 0)}</text>
    <text x="${mg.l}" y="${H - 8}" font-size="11" style="fill:var(--tinta2,#4A4F44)">${E(dataBr2(s[0].dia))}</text><text x="${W - mg.r}" y="${H - 8}" font-size="11" text-anchor="end" style="fill:var(--tinta2,#4A4F44)">${E(dataBr2(s[s.length - 1].dia))}</text></svg>
    <figcaption class="t2 pq"><span>Economia acumulada: esperado pela linha de base − medido, dia a dia.</span></figcaption></figure>`; }
function partePainel(F) { const u = U(), est = F.est, mv = est.mv2 || [], tar = (est.tarefas || []).filter(t => t.situacao === "atrasada"), al = ordenarPorRisco(mv.flatMap(x => (x.alarmes || []).map(a => Object.assign({ nome: x.nome }, a))));
  const card = (id, tit, n, un) => `<section class="cartao" aria-labelledby="h-va-k-${id}"><h3 id="h-va-k-${id}" class="t3">${tit}</h3><span class="numero">${n}</span> <span class="t2">${un}</span></section>`;
  const x = mv[0] || {}, i = x.incerteza || {}, mc = x.monte_carlo || {}, pj = x.projecao || {}, un = x.unidade || "kWh";
  if (!mv.length) return `<section class="cartao" aria-labelledby="h-va-pn"><h2 id="h-va-pn">Painel M&V 2.0</h2><p class="t2">Defina os períodos de base e de relatório no plano de M&V e grave um planejado de energia ou água com o medidor.</p></section>`;
  const sens = (x.sensibilidade || []).map(s => `<tr><th scope="row">${E(s.nome)}</th><td>${f(s.parte_pct, 1)} %</td></tr>`);
  const nres = (x.nres || []).map(n => `<tr><th scope="row">${dataBr2(n.inicio)}</th><td>${E(n.classe_nome)}</td><td>${fs(n.nivel_dia, 1)} ${E(un)}/dia</td><td>${fs(n.ajuste_proposto, 0)} ${E(un)}</td><td><span class="selo ${n.situacao === "aprovado" ? "ok" : n.situacao === "recusado" ? "al" : "at"}">${E(n.situacao)}</span></td><td>${n.situacao === "pendente" ? (F.demo ? "—" : `<button type="button" data-va-acao="nre" data-va-chave="${E(n.chave)}" data-va-op="1" id="va-nre-${E(n.chave)}">Aprovar</button> <button type="button" data-va-acao="nre" data-va-chave="${E(n.chave)}" data-va-op="0">Recusar</button>`) : E(n.motivo || "")}</td></tr>`);
  const der = (d, nome) => `<tr><th scope="row">${nome}</th><td>${d && d.alarme ? `<span class="selo al">deriva ${E(d.lado || "")}</span>` : `<span class="selo ok">sem deriva</span>`}</td><td>${E((d && d.referencia) || "resíduos do modelo")}</td></tr>`;
  const fat = (x.fatura || []).map(z => `<tr><th scope="row">${mesBr(z.mes)}</th><td>${f(z.fatura, 0)}</td><td>${f(z.intervalo, 0)}</td><td>${z.diferenca_pct == null ? "—" : fs(z.diferenca_pct, 1) + " %"}</td></tr>`);
  return `<section class="cartao" aria-labelledby="h-va-pn"><h2 id="h-va-pn">Painel M&V 2.0</h2><p class="t2 apoio">Economia acumulada quase em tempo real com as leituras do hub (V6, MQTT e importações), indicadores e alarmes de desvio com a causa provável e a ação sugerida.</p>
      ${pares("Dados e modelo", [["Granularidade nativa", E(x.granularidade || "—")], ["Política de faltantes", E(x.politica_nome || "—")], ["Temperatura", E(x.fonte_temperatura || "—")], ["Modelo escolhido (validação cruzada)", E(((x.modelo || {}).tipo) || "—")], ["Ajuste mínimo", x.aceite_minimo && x.aceite_minimo.ok ? `<span class="selo ok">atende</span>` : `<span class="selo al">não atende</span>`], ["Versão do modelo", `<code>${E(((x.modelo_versao || {}).hash || "—").slice(0, 16))}</code>`]])}
      <div class="grade">${card("ec", "Economia acumulada", f(x.economia, 0), un)}${card("ic", "Intervalo de confiança (Monte Carlo)", mc.ic_inf == null ? "—" : f(mc.ic_inf, 0) + " a " + f(mc.ic_sup, 0), un + " · " + f(mc.confianca_pct, 0) + " %")}${card("in", "Incerteza da economia", f(i.incerteza_pct, 1), "% · " + (i.veredito || "sem dado"))}${card("pj", "Projeção até o fim do período", f(pj.projetada, 0), un)}${card("al", "Alarmes de desvio", f(al.length, 0), "trechos")}${card("ta", "Tarefas atrasadas", f(tar.length, 0), "itens")}</div>
      ${pj.risco ? `<div class="faixa al" role="status"><strong>Risco de não atingir a meta.</strong> <span>Meta:</span> <strong>${f(pj.meta, 0)} ${E(un)}</strong><span>; projeção pela persistência:</span> <strong>${f(pj.projetada, 0)} ${E(un)}</strong>${pj.rs_em_risco != null ? `<span>; em risco:</span> <strong>${real(pj.rs_em_risco)}</strong>` : ""}</div>` : pj.risco === false ? `<div class="faixa ok" role="status"><span>A projeção atinge a meta.</span></div>` : ""}
      ${graficoAcumulado(x.economia_acumulada || [])}
      <div class="chips" role="group" aria-label="Pacote de auditoria e resultado verificado"><button type="button" id="va-b-aud" data-va-acao="auditoria" data-va-item="${E(x.item)}">Exportar pacote de auditoria</button>${F.demo ? "" : `<button type="button" id="va-b-ver" data-va-acao="verificar" data-va-item="${E(x.item)}">Registrar resultado verificado</button>`}</div><p class="t2" role="status">${E(u.vaAudMsg || "")}</p></section>
    <section class="cartao" aria-labelledby="h-va-fdd"><h2 id="h-va-fdd">Alarmes de desvio (FDD)</h2><p class="t2 apoio">Alarme só quando o medido sai do intervalo de previsão do modelo, por dias seguidos; ordenados pelo R$ em risco. O mesmo trecho não se repete.</p>
      ${al.length ? tabela("Alarmes: trecho, desvio, R$ em risco, causa provável e ação sugerida", ["Equipamento", "Início", "Fim", "Dias", "Desvio", "R$ em risco", "Causa provável", "Ação sugerida", "Gestão"], al.map(a => `<tr><th scope="row">${E(a.nome)}</th><td>${dataBr2(a.inicio)}</td><td>${dataBr2(a.fim)}</td><td>${f(a.dias, 0)}</td><td>${fs(a.desvio_pct, 1)} %</td><td>${a.rs_em_risco == null ? "—" : real(a.rs_em_risco)}</td><td>${E(a.causa_nome)}</td><td>${E(a.acao)}</td><td>${a.tarefa ? `<span class="selo ok">tarefa aberta</span>` : F.demo ? "—" : `<button type="button" data-va-acao="tarefa" data-va-chave="${E(a.chave)}">Criar tarefa na Gestão</button>`}</td></tr>`)) : `<div class="faixa ok" role="status"><span>Nenhum alarme de desvio.</span></div>`}
      <p class="t2 pq">Modo automático (abre a tarefa sozinho em falha de equipamento ou de operação): <strong>${(((est.plano_mv || {}).atual || {}).cmms_automatico) ? "ligado" : "desligado"}</strong><span>, no plano de M&V.</span></p><p class="t2" role="status">${E(u.vaTarMsg || "")}</p></section>
    <section class="cartao" aria-labelledby="h-va-inc2"><h2 id="h-va-inc2">De onde vem a incerteza</h2>${tabela("Fontes da incerteza, da maior para a menor (Monte Carlo)", ["Fonte", "Parte da variância"], sens)}${mc.exatidao_conhecida === false ? `<p class="t2 pq">Exatidão do medidor desconhecida [CONFERIR]: cadastre-a em Medidores e dados.</p>` : ""}</section>
    <section class="cartao" aria-labelledby="h-va-der"><h2 id="h-va-der">Deriva do modelo e do sensor (CUSUM)</h2>${tabela("Deriva por CUSUM", ["O quê", "Situação", "Referência"], [der(x.deriva_modelo, "Modelo"), der(x.deriva_sensor, "Sensor")])}</section>
    <section class="cartao" aria-labelledby="h-va-nre"><h2 id="h-va-nre">Eventos não rotineiros</h2><p class="t2 apoio">Mudança de nível que o modelo não explica. O ajuste não rotineiro só entra na conta depois da aprovação de uma pessoa, e a decisão vai para o registro.</p>
      ${nres.length ? tabela("Eventos não rotineiros prováveis e o ajuste proposto", ["Desde", "Classe provável", "Nível", "Ajuste proposto", "Situação", "Decisão"], nres) : `<p class="t2">Nenhum evento não rotineiro.</p>`}
      <div><label for="va-nre-motivo">Motivo da decisão</label><input id="va-nre-motivo" type="text" style="width:100%"></div><p class="t2" role="status">${E(u.vaNreMsg || "")}</p></section>
    <section class="cartao" aria-labelledby="h-va-fat"><h2 id="h-va-fat">Conferência com a fatura</h2><p class="t2 apoio">A fonte principal são os dados de intervalo; a fatura e o digitado servem só para conferir.</p>${fat.length ? tabela("Fatura × soma dos dados de intervalo", ["Mês", "Fatura", "Intervalo", "Diferença"], fat) : `<p class="t2">Sem faturas no plano de M&V.</p>`}</section>`; }
function telaValidacao() { const u = U(), SUBS = [["resumo", "Resumo"], ["painel", "Painel M&V 2.0"], ["modulo", "Por módulo"], ["base", "Linha de base (IPMVP)"], ["modelos", "Modelos e incerteza"], ["plano", "Plano de M&V"], ["medidores", "Medidores e dados"], ["planejado", "Planejado"]];
  const sub = SUBS.some(s => s[0] === u.vaSub) ? u.vaSub : "resumo", F = fonte();
  const chips = `<div class="chips" role="group" aria-label="Partes da validação">${SUBS.map(([k, n]) => `<button type="button" id="va-sub-${k}" data-va-sub="${k}" aria-pressed="${k === sub}">${n}</button>`).join("")}</div>`;
  const corpo = F.carregando ? `<p class="t2" role="status">Carregando o planejado e o medido…</p>`
    : aviso(F) + (sub === "modulo" ? parteModulo(F) : sub === "base" ? parteBase(F) : sub === "planejado" ? partePlanejado(F) : sub === "painel" ? partePainel(F)
      : sub === "modelos" ? parteModelos(F) : sub === "plano" ? partePlanoMv(F) : sub === "medidores" ? parteMedidores(F) : parteResumo(F));
  return `<h1>Validação · planejado × gerado (M&amp;V)</h1><p class="t2 apoio">O que foi planejado × o que está sendo realmente gerado e consumido, mês a mês: quanto, como, quando e por quê.</p>${chips}<div id="va-corpo">${corpo}</div>`; }

/* ════════ Relatório (ODT e PDF/A pelo PhysisODF, os formatos abertos da plataforma) ════════ */
function relatorio(F) { const est = F.est, p = est.premissas || P(), b = [], pm = (est.plano_mv || {}).atual || {}, S = SECOES_RELATORIO, op = pm.opcao;
  b.push({ h: 1, t: "Relatório de medição e verificação · planejado × medido" });
  if (F.demo) b.push({ t: "Dados SIMULADOS da Casa Physis: não usar como laudo." });
  b.push({ h: 2, t: S[0] });
  b.push({ t: `Escopo: ${pm.escopo || "[A DEFINIR]"}. Fronteira de medição: ${pm.fronteira || "[A DEFINIR]"}.` });
  b.push({ t: "Medidas de eficiência (ECM): " + ((pm.ecms || []).map(e => e.nome || e.id).join(", ") || "[A DEFINIR]") + "." });
  b.push({ h: 2, t: S[1] });
  b.push({ t: `Opção IPMVP: ${op ? op + " · " + OPCOES_IPMVP[op] : "[A DEFINIR]"}. Justificativa: ${pm.justificativa || "[A DEFINIR]"}. Método: ${pm.metodo || "[A DEFINIR]"}.` });
  if (op === "D" && pm.simulacao) { b.push({ t: `Simulação: ${pm.simulacao.software} versão ${pm.simulacao.versao}.` }); b.push({ tabela: { cab: ["Arquivo", "Papel", "SHA-256"], linhas: pm.simulacao.arquivos.map(x => [x.nome, x.papel, x.sha256]), legenda: "Cópias dos arquivos de entrada e saída da simulação" } }); }
  b.push({ t: ["Desvio = medido − planejado; % sobre o planejado.", "Medido: média do dia × 24 h das leituras do hub, somada no mês; dias sem leitura aparecem como falha de dado.", "Causas por regras com evidência; causa não identificada é aceita.", "IPMVP citado só pelo nome; regressão linear simples; premissas validacao.* a conferir.", "Validação preliminar: não substitui o projeto com responsável técnico."], lista: true });
  b.push({ h: 2, t: S[2] });
  b.push({ t: `Período: ${mesBr(est.meses[0])} a ${mesBr(est.meses[est.meses.length - 1])}. Limite de desvio: ${f(p["validacao.desvio_limite_pct"], 0)} % (premissa a conferir).` });
  est.modulos.filter(m => m.tem_plano).forEach(m => { const cs = casas(m.unidade);
    b.push({ tabela: { cab: ["Mês", "Planejado (" + m.unidade + ")", "Medido (" + m.unidade + ")", "Desvio (" + m.unidade + ")", "Desvio (%)", "Dias com leitura"], linhas: m.linhas.map(l => [mesBr(l.mes), f(l.planejado, cs), f(l.medido, cs), fs(l.abs, cs), l.pct == null ? "—" : fs(l.pct, 1) + " %", l.cobertura_pct == null ? "—" : f(l.cobertura_pct, 0) + " %"]), legenda: m.nome } }); });
  if ((est.qualidade || []).length) b.push({ tabela: { cab: ["Medidor", "Granularidade", "Perda de dados (%)", "Marcados"], linhas: est.qualidade.map(x => [x.ativo, x.granularidade, f(x.perda_pct, 1), String(Object.values(x.resumo || {}).reduce((s, n) => s + n, 0))]), legenda: "Qualidade dos dados" } });
  b.push({ h: 2, t: S[3] });
  b.push({ tabela: { cab: ["Módulo", "Planejado", "Medido", "Desvio (%)", "Primeiro mês fora"], linhas: est.modulos.map(m => [m.nome, m.total ? f(m.total.planejado, casas(m.unidade)) : "—", m.total ? f(m.total.medido, casas(m.unidade)) : "—", m.total ? fs(m.total.pct, 1) : "—", m.tem_plano ? (m.quando ? mesBr(m.quando.primeiro_mes) : "—") : m.sem_plano]), legenda: "Comparação com as metas do plano" } });
  if ((est.enpis || []).length) b.push({ tabela: { cab: ["EnPI", "Base", "Relatório", "Variação (%)"], linhas: est.enpis.map(e => [e.enpi, f(e.base, 2), f(e.relatorio, 2), e.variacao_pct == null ? "—" : fs(e.variacao_pct, 1)]), legenda: "Indicadores de desempenho (EnPI)" } });
  const r = F.demo ? demoMundo().base : U().vaBRes;
  if (r && r.modelo && r.modelo.a != null) b.push({ tabela: { cab: ["Grandeza", "Valor"], linhas: [["Linha de base", f(r.base, 0)], ["Período de relatório", f(r.relatorio, 0)], ["Ajuste rotineiro", fs(r.ajuste_rotineiro, 0)], ["Ajuste não rotineiro", fs(r.ajuste_nao_rotineiro, 0)], ["Economia", f(r.economia.econ, 0)], ["Economia (%)", f(r.economia.pct, 1)]], legenda: "Economia = (linha de base − período de relatório) ± ajustes" } });
  if (est.pee) { const z = est.pee; b.push({ tabela: { cab: ["Campo do PEE (ANEEL)", "Valor"], linhas: [["Energia economizada (MWh/ano)", f(z.energia_economizada_mwh_ano, 1)], ["Redução de demanda na ponta (kW)", f(z.reducao_demanda_ponta_kw, 1)], ["RCB", z.rcb == null ? "[MARCADOR]" : f(z.rcb, 2)], ["Custo da M&V / custo total (%)", f((z.custo_check || {}).parte_pct, 1) + " · " + (z.custo_check || {}).situacao], ["Erro / precisão / confiança alcançados (%)", [z.erro_pct, z.precisao_pct, z.confianca_pct].map(v => f(v, 1)).join(" / ")]], legenda: "Perfil PEE (ANEEL): números do projeto; exigências aguardando o Guia de M&V" } }); }
  b.push({ h: 2, t: S[4] });
  (est.mv2 || []).forEach(x => { const i = x.incerteza || {}; b.push({ t: `${x.nome}: modelo ${(x.modelo || {}).tipo || "—"}, R² ${f(((x.modelo || {}).metricas || {}).r2, 3)}, CV(RMSE) ${f(((x.modelo || {}).metricas || {}).cv_rmse_pct, 1)} %, NMBE ${f(((x.modelo || {}).metricas || {}).nmbe_pct, 2)} %; incerteza fracional ${f(i.incerteza_pct, 1)} % a ${f(i.confianca_pct, 0)} % de confiança, limite ${f(i.limite_pct, 0)} %: ${i.veredito || "sem dado"}.` }); });
  (est.mv2 || []).forEach(x => { const mc = x.monte_carlo; if (mc) b.push({ t: `Monte Carlo: economia ${f(mc.economia, 0)} com IC de ${f(mc.confianca_pct, 0)} % de ${f(mc.ic_inf, 0)} a ${f(mc.ic_sup, 0)}; fontes: ${(x.sensibilidade || []).map(s => s.nome + " " + f(s.parte_pct, 0) + " %").join(", ")}.` }); });
  if (!(est.mv2 || []).length) b.push({ t: "Sem modelo diário: defina os períodos de base e de relatório no plano de M&V." });
  b.push({ h: 2, t: S[5] });
  b.push({ t: est.modulos.flatMap(m => m.explicacoes.map(x => `${m.nome} · ${mesBr(x.mes)}: ${x.causas.map(k => k.nome + " (" + f(k.confianca, 2) + ")").join(", ")}`)).concat((est.inspecoes || []).map(i => `Inspeção ${i.ecm} em ${dataBr2(i.dia)}: ${i.operando ? "operando" : "NÃO operando"}`)), lista: true });
  b.push({ h: 2, t: S[6] });
  const ac = new Set(); est.modulos.forEach(m => m.explicacoes.forEach(x => ac.add(ACOES[x.causas[0].codigo]))); (est.mv2 || []).forEach(x => (x.alarmes || []).forEach(a => ac.add(a.acao))); (est.tarefas || []).forEach(t => ac.add(t.texto));
  b.push({ t: ac.size ? [...ac] : ["Manter o plano de coleta e a revisão anual."], lista: true });
  b.push({ h: 2, t: S[7] });
  b.push({ tabela: { cab: ["Número", "Fonte"], linhas: Object.keys(est.rastreio || {}).sort().map(k => [k, typeof est.rastreio[k] === "string" ? est.rastreio[k] : JSON.stringify(est.rastreio[k])]), legenda: "Rastreabilidade: leituras, fator da rede, premissas, ajustes e versão do modelo" } });
  return { blocos: b, secoes: S }; }
async function baixar(tipo) { const u = U(), F = fonte(); if (!F.est) return; const O = window.PhysisODF, titulo = "Validação M&V" + (F.demo ? " (SIMULADO)" : "");
  if (!O) { u.vaRelMsg = "O gerador de documentos não está nesta tela."; redesenhar(); return; }
  u.vaRelMsg = "Gerando…"; redesenhar();
  try { const mod = relatorio(F);
    if (tipo === "odt") { const u8 = await O.odt(mod, { titulo }); const n = O.nomeArquivo(titulo, "odt"); await O.baixar(n, u8, O.MIME.odt); u.vaRelMsg = "Baixado: " + n; }
    else { const r = emHub() ? await O.pdfa(mod, titulo).catch(() => ({ ok: false })) : { ok: false };   /* sem o computador central nem tenta */
      if (r && r.ok) { const n = O.nomeArquivo(titulo, "pdf"); await O.baixar(n, r.pdf, O.MIME.pdf); u.vaRelMsg = "Baixado: " + n; }
      else u.vaRelMsg = r && r.status === 401 ? "Entre com a sua conta para gerar o PDF/A." : "Sem o computador central, o PDF/A não sai: baixe o ODT e exporte para PDF/A no LibreOffice."; } }
  catch (e) { u.vaRelMsg = "Não foi possível gerar o relatório."; }
  redesenhar(); const b = pega(tipo === "odt" ? "va-b-odt" : "va-b-pdf"); if (b) b.focus(); }

/* ════════ Trazer o planejado das outras abas (no navegador; a equipe confere e grava) ════════ */
function doSolar() { try { const c = window.SOLAR && SOLAR.compat ? SOLAR.compat() : null; if (!c || c.semLocal || !(c.ger > 0) || !Array.isArray(c.H) || c.H.length !== 12) return null;
  const pesos = c.H.map((h, i) => h * new Date(Date.UTC(2025, i + 1, 0)).getUTCDate()), s = pesos.reduce((a, b) => a + b, 0); if (!s) return null;
  return { modulo: "solar", meses: pesos.map(w => +(c.ger * w / s).toFixed(1)), clima: c.H.map(h => +h.toFixed(2)), fonte: "Energia solar · dimensionamento (geração do ano repartida pela irradiação de cada mês)" }; } catch (e) { return null; } }
function doTurbinas() { try { const k = window.TURBINAS && TURBINAS.kwhAnoPlanejado ? TURBINAS.kwhAnoPlanejado() : null; if (!(k > 0)) return null;
  return { modulo: "turbinas", meses: Array.from({ length: 12 }, (_, i) => +(k * new Date(Date.UTC(2025, i + 1, 0)).getUTCDate() / 365).toFixed(1)), clima: null, fonte: "Turbinas · energia do ano planejada, repartida pelos dias de cada mês" }; } catch (e) { return null; } }
const valor = k => { const x = pega("va-" + k); return x ? x.value : ""; };
function lerForm() { const u = U(), fm = { modulo: valor("pl-modulo"), item: valor("pl-item").trim(), nome: valor("pl-nome").trim(), ativo: valor("pl-ativo").trim(), meses: valor("pl-meses"), clima: valor("pl-clima"), fonte: valor("pl-fonte").trim(), premissa: valor("pl-premissa").trim() }; u.vaPl = fm; return fm; }
async function acao(b) { const u = U(), a = b.dataset.vaAcao, F = fonte();
  if (a === "odt" || a === "pdf") return baixar(a);
  if (a === "auditoria") { const item = b.dataset.vaItem; if (F.demo && !emHub()) { const x = (F.est.mv2 || [])[0] || {}, pac = { formato: "physis-validacao-auditoria/1", simulado: true, modelo: x.modelo_versao, calculo: { economia: x.economia, esperado: x.esperado }, serie: x.economia_acumulada, premissas: F.est.premissas };
      const u8 = new TextEncoder().encode(JSON.stringify(pac, null, 1)); if (window.PhysisODF) await PhysisODF.baixar("validacao-auditoria-SIMULADO.json", u8, "application/json"); u.vaAudMsg = "Pacote SIMULADO baixado."; redesenhar(); refocar("va-b-aud"); return; }
    const a2 = document.createElement("a"); a2.href = "api/validacao/auditoria?item=" + encodeURIComponent(item); a2.download = ""; document.body.appendChild(a2); a2.click(); a2.remove(); u.vaAudMsg = "Pacote de auditoria pedido ao computador central."; redesenhar(); refocar("va-b-aud"); return; }
  if (a === "verificar") { const r = await api("POST", "api/validacao/verificar", { item: b.dataset.vaItem }); u.vaAudMsg = r.ok ? "Resultado verificado registrado (entra no lote diário de integridade)." : (r.erro || "Não foi possível registrar."); redesenhar(); refocar("va-b-ver"); return; }
  if (a === "tarefa") { const r = await api("POST", "api/validacao/tarefa", { chave: b.dataset.vaChave }); u.vaTarMsg = r.ok ? "Tarefa aberta na Gestão, com a evidência." : (r.erro || "Não foi possível abrir a tarefa."); if (r.ok) carregar(true); redesenhar(); refocar("va-sub-painel"); return; }
  if (a === "nre") { const motivo = valor("nre-motivo").trim(); if (!motivo) { u.vaNreMsg = "Diga o motivo da decisão."; redesenhar(); refocar("va-nre-motivo"); return; }
    const r = await api("POST", "api/validacao/nre", { chave: b.dataset.vaChave, aprovar: b.dataset.vaOp === "1", motivo }); u.vaNreMsg = r.ok ? "Decisão registrada." : (r.erro || "Não foi possível registrar."); if (r.ok) carregar(true); redesenhar(); refocar("va-nre-motivo"); return; }
  if (a === "pmv-gravar") { const v = k => valor("pmv-" + k), ls = k => v(k).split("\n").map(s => s.trim()).filter(Boolean);
    const d = { escopo: v("escopo"), fronteira: v("fronteira"), opcao: v("opcao"), justificativa: v("justificativa"), metodo: v("metodo"), fontes: ls("fontes"), variaveis_independentes: ls("variaveis_independentes"), fatores_estaticos: ls("fatores_estaticos"), qa: ls("qa"),
      base_ini: v("base_ini"), base_fim: v("base_fim"), rel_ini: v("rel_ini"), rel_fim: v("rel_fim"), revisao_anual: v("revisao_anual"), formato: v("formato"), periodicidade: v("periodicidade"), area_m2: num(v("area_m2")), ocupantes: num(v("ocupantes")),
      ecms: ls("ecms").map(s => { const [id, nome] = s.split(";").map(x => x.trim()); return { id, nome: nome || "" }; }), papeis: Object.keys(PAPEIS).map(k => ({ papel: k, pessoa: v("p-" + k), competencia: v("c-" + k) })) };
    if (d.opcao === "D") d.simulacao = { software: v("sw"), versao: v("swv"), arquivos: ls("arqs").map(s => { const [nome, sha, pap] = s.split(";").map(x => x.trim()); return { nome, sha256: (sha || "").toLowerCase(), papel: pap === "saida" || pap === "saída" ? "saida" : "entrada" }; }) };
    u.vaPmv = d; u.vaPmvMotivo = v("motivo"); const erro = validarPlanoMv(d);
    if (erro) { u.vaPmvMsg = erro; redesenhar(); refocar("va-pmv-escopo"); return; }
    if (!u.vaPmvMotivo.trim()) { u.vaPmvMsg = "Diga por que o plano mudou."; redesenhar(); refocar("va-pmv-motivo"); return; }
    if (F.demo && !emHub()) { u.vaPmvMsg = "Na demonstração, o plano é SIMULADO: gravar funciona na plataforma instalada."; redesenhar(); refocar("va-b-pmv"); return; }
    Object.keys(d).forEach(k => { if (d[k] == null || d[k] === "") delete d[k]; });
    const r = await api("POST", "api/validacao/plano-mv", { plano: d, motivo: u.vaPmvMotivo }); u.vaPmvMsg = r.ok ? "Nova versão gravada no registro." : (r.erro || "Não foi possível gravar.");
    if (r.ok) { u.vaPmv = null; u.vaPmvMotivo = ""; carregar(true); } redesenhar(); refocar("va-b-pmv"); return; }
  if (a === "licao") { const tx = valor("lic-texto").trim(); if (!tx) { u.vaLicMsg = "Escreva a lição."; redesenhar(); refocar("va-lic-texto"); return; }
    if (F.demo && !emHub()) { u.vaLicMsg = "Na demonstração, o diário é SIMULADO: registrar funciona na plataforma instalada."; redesenhar(); refocar("va-b-lic"); return; }
    const r = await api("POST", "api/validacao/licao", { texto: tx }); u.vaLicMsg = r.ok ? "Lição registrada." : (r.erro || "Não foi possível gravar."); if (r.ok) carregar(true); redesenhar(); refocar("va-b-lic"); return; }
  if (a === "inspecao") { if (F.demo && !emHub()) return; const r = await api("POST", "api/validacao/inspecao", { ecm: b.dataset.vaEcm, operando: b.dataset.vaOp === "1" });
    u.vaInspMsg = r.ok ? "Inspeção registrada." : (r.erro || "Não foi possível gravar."); if (r.ok) carregar(true); redesenhar(); refocar("va-sub-plano"); return; }
  if (a === "medidor") { const v = k => valor("md-" + k).trim(), d = { ativo: v("ativo"), tipo: v("tipo"), modelo: v("modelo"), exatidao_pct: num(v("exatidao_pct")), incerteza_pct: num(v("incerteza_pct")), comissionamento: v("comissionamento"), cal_ultima: v("cal_ultima"), cal_proxima: v("cal_proxima") };
    if (!d.ativo || !d.tipo) { u.vaMdMsg = "Informe o medidor (ativo) e o tipo."; redesenhar(); refocar("va-md-ativo"); return; }
    if (F.demo && !emHub()) { u.vaMdMsg = "Na demonstração, os medidores são SIMULADOS: gravar funciona na plataforma instalada."; redesenhar(); refocar("va-b-md"); return; }
    const inp = pega("va-md-certificado"), arq = inp && inp.files && inp.files[0];
    if (arq && window.crypto && crypto.subtle) { const h = await crypto.subtle.digest("SHA-256", await arq.arrayBuffer()); d.certificado_sha256 = [...new Uint8Array(h)].map(x => x.toString(16).padStart(2, "0")).join(""); d.certificado_nome = arq.name.slice(0, 160); }
    Object.keys(d).forEach(k => { if (d[k] == null || d[k] === "") delete d[k]; });
    const r = await api("POST", "api/validacao/medidor", d); u.vaMdMsg = r.ok ? "Medidor gravado no registro." : (r.erro || "Não foi possível gravar."); if (r.ok) carregar(true); redesenhar(); refocar("va-b-md"); return; }
  if (a === "trazer-solar" || a === "trazer-turbinas") { const fm = lerForm(), t = a === "trazer-solar" ? doSolar() : doTurbinas();
    if (!t) { u.vaPlMsg = a === "trazer-solar" ? "A aba Energia solar ainda não tem dimensionamento com local." : "A aba Turbinas ainda não tem energia planejada."; redesenhar(); refocar(b.id); return; }
    u.vaPl = Object.assign(fm, { modulo: t.modulo, meses: t.meses.map(v => N(v, 1)).join("; "), clima: t.clima ? t.clima.map(v => N(v, 2)).join("; ") : "", fonte: t.fonte, item: fm.item || (t.modulo === "solar" ? "usina" : "turbina") });
    u.vaPlMsg = "Planejado trazido: confira e grave."; redesenhar(); refocar("va-pl-meses"); return; }
  if (a === "pl-gravar") { const fm = lerForm(), meses = parsear12(fm.meses), clima = fm.clima.trim() ? parsear12(fm.clima) : null;
    if (!meses) { u.vaPlMsg = "Informe os 12 meses, separados por ponto e vírgula."; redesenhar(); refocar("va-pl-meses"); return; }
    if (fm.clima.trim() && !clima) { u.vaPlMsg = "O clima esperado precisa de 12 valores, ou fica vazio."; redesenhar(); refocar("va-pl-clima"); return; }
    if (!/^[A-Za-z0-9_.-]{1,60}$/.test(fm.item)) { u.vaPlMsg = "Código do equipamento: letras, números, ponto, hífen ou sublinhado."; redesenhar(); refocar("va-pl-item"); return; }
    if (!fm.fonte) { u.vaPlMsg = "Diga a fonte do planejado."; redesenhar(); refocar("va-pl-fonte"); return; }
    if (F.demo && !emHub()) { u.vaPlMsg = "Na demonstração, o planejado é SIMULADO: gravar funciona na plataforma instalada."; redesenhar(); refocar("va-b-pl"); return; }
    const MM = i => String(i + 1).padStart(2, "0"), d = { modulo: fm.modulo, item: fm.item, nome: fm.nome, ativo: fm.ativo, fonte: fm.fonte, meses: Object.fromEntries(meses.map((v, i) => [MM(i), v])) };
    if (clima) d.clima = Object.fromEntries(clima.map((v, i) => [MM(i), v])); if (fm.premissa) d.premissa = fm.premissa;
    const r = await api("POST", "api/validacao/plano", d); u.vaPlMsg = r.ok ? "Planejado gravado." : (r.erro || "Não foi possível gravar.");
    if (r.ok) { u.vaPl = {}; carregar(true); } redesenhar(); refocar("va-b-pl"); return; }
  if (a === "pl-remover") { const r = await api("POST", "api/validacao/plano/remover", { id: +b.dataset.vaId }); u.vaPlMsg = r.ok ? "Planejado apagado." : (r.erro || "Não foi possível apagar."); carregar(true); redesenhar(); refocar("va-b-pl"); return; }
  if (a === "base") { const fm = { plano: valor("b-plano"), var: valor("b-var"), base_ini: valor("b-base_ini"), base_fim: valor("b-base_fim"), rel_ini: valor("b-rel_ini"), rel_fim: valor("b-rel_fim") }; u.vaB = fm;
    if (![fm.base_ini, fm.base_fim, fm.rel_ini, fm.rel_fim].every(x => /^\d{4}-\d{2}$/.test(x)) || fm.base_ini > fm.base_fim || fm.rel_ini > fm.rel_fim) { u.vaBMsg = "Escolha os quatro meses, com o início antes do fim."; redesenhar(); refocar("va-b-base_ini"); return; }
    u.vaBMsg = "Calculando…"; redesenhar();
    const q = Object.entries(fm).map(([k, v]) => encodeURIComponent(k) + "=" + encodeURIComponent(v)).join("&"), r = await api("GET", "api/validacao/baseline?" + q);
    u.vaBRes = r.ok ? r : null; u.vaBMsg = r.ok ? "" : (r.erro || "Não foi possível calcular."); redesenhar(); refocar("va-b-calc"); } }
function refocar(id) { const x = pega(id); if (x && x.focus) x.focus(); }
if (typeof document !== "undefined" && !window.__vaEventos) { window.__vaEventos = true;
  document.addEventListener("change", ev => { const t = ev.target; if (!t || !t.dataset || !t.dataset.vaK) return; const u = U(), k = t.dataset.vaK;
    if (k === "mod") { u.vaMod = t.value; redesenhar(); refocar("va-mod"); return; }
    if (k.startsWith("pl-")) { u.vaPl = Object.assign({}, u.vaPl, { [k.slice(3)]: t.value }); return; }
    if (k.startsWith("b-")) { u.vaB = Object.assign({}, u.vaB, { [k.slice(2)]: t.value }); } });
  document.addEventListener("click", ev => { const tg = ev.target; if (!tg || !tg.closest) return; const b = tg.closest("button"); if (!b || !b.dataset) return; const u = U();
    if (b.dataset.vaSub) { u.vaSub = b.dataset.vaSub; redesenhar(); refocar("va-sub-" + b.dataset.vaSub); return; }
    if (b.dataset.vaMod) { u.vaMod = b.dataset.vaMod; u.vaSub = "modulo"; redesenhar(); refocar("va-mod"); return; }
    if (b.dataset.vaAcao) acao(b); }); }

window.VALIDACAO = { desvio, diasDoMes, mesesAte, planoDoMes, cvPct, planoPlano, comparar, fora, quando, nivel, causas, como, somarItens, analisarModulo,
  ipmvp, grausDia, reta, linhaDeBase, esperado, ipmvpRegressao, itensCarbono, fatorRede, estadoDemo, demoMundo, relatorio, premissa, MODULOS, SEM_PLANO, CAUSAS, VARIAVEIS_BASE,
  metricas, regressao, ajustarCP, ajustarML, escolherModelo, aceite, prever, invNormal, tStudent, autocorrelacao, incertezaEconomia, granularidade, limparSerie, economiaAcumulada, trechosFdd,
  alertasMedidor, validarPlanoMv, enpis, OPCOES_IPMVP, PAPEIS, SECOES_RELATORIO, ACOES, VERSAO_CODIGO,
  cusum, intervaloPrevisao, fddIntervalo, ordenarPorRisco, projecaoPersistencia, monteCarlo, sensibilidade, detectarNre, tamanhoAmostra, precisaoAlcancada, resumoPee,
  POLITICAS, CLASSES_NRE, FONTES_INCERTEZA, PERFIS, PREMISSAS_PEE };
window.telaValidacao = telaValidacao;   /* global: a plataforma chama telaValidacao() ao desenhar a aba */

/* ════════ Inglês (o integrador junta ao I18N da plataforma) ════════ */
window.VALIDACAO_I18N = {
  "Validação · planejado × gerado (M&V)": "Validation · planned × generated (M&V)",
  "O que foi planejado × o que está sendo realmente gerado e consumido, mês a mês: quanto, como, quando e por quê.": "What was planned × what is really being generated and consumed, month by month: how much, how, when and why.",
  "Partes da validação": "Validation sections",
  "Resumo": "Summary",
  "Por módulo": "By module",
  "Linha de base (IPMVP)": "Baseline (IPMVP)",
  "Planejado": "Planned",
  "Carregando o planejado e o medido…": "Loading planned and measured values…",
  "Dados SIMULADOS da Casa Physis.": "SIMULATED data from Casa Physis.",
  "Nenhum plano gravado neste computador central: grave o planejado na parte Planejado para ver a sua instalação.": "No plan saved on this central computer: save the planned values in the Planned section to see your installation.",
  "Abra a plataforma instalada para ver o planejado e o medido da sua instalação.": "Open the installed platform to see the planned and measured values of your installation.",
  "Os números simulados nunca vão para o Carbono, a Gestão nem um relatório de verdade.": "Simulated numbers never go to Carbon, Management or a real report.",
  "Sem ligação com o computador central: mostrando a última cópia guardada neste aparelho.": "No connection to the central computer: showing the last copy saved on this device.",
  "Energia solar (geração)": "Solar energy (generation)",
  "Água (consumo e reúso)": "Water (consumption and reuse)",
  "Energia e AVAC (consumo)": "Energy and HVAC (consumption)",
  "Turbinas (geração)": "Turbines (generation)",
  "Frota (combustível)": "Fleet (fuel)",
  "Carbono (emissões)": "Carbon (emissions)",
  "Sem plano: grave o planejado da usina (aba Energia solar · dimensionamento) para comparar.": "No plan: save the planned output of the plant (Solar energy tab · sizing) to compare.",
  "Sem plano: grave o consumo planejado (premissa de consumo por pessoa, projeto ou Planejador) para comparar.": "No plan: save the planned consumption (per-person consumption assumption, design or Planner) to compare.",
  "Sem plano: grave o consumo planejado (projeto, AVAC ou Planejador) para comparar.": "No plan: save the planned consumption (design, HVAC or Planner) to compare.",
  "Sem plano: grave a energia planejada (aba Turbinas) para comparar.": "No plan: save the planned energy (Turbines tab) to compare.",
  "Sem plano: nenhum veículo tem o consumo esperado no cadastro da Frota.": "No plan: no vehicle has the expected consumption in the Fleet register.",
  "Sem plano: o Carbono nasce dos planejados de Energia e da Frota, e nenhum dos dois tem plano.": "No plan: Carbon comes from the Energy and Fleet plans, and neither has a plan.",
  "Equipamento desligado ou falha de dado": "Equipment off or data gap",
  "Clima diferente do esperado": "Weather different from expected",
  "Consumo fora do normal aprendido": "Consumption outside the learned normal",
  "Premissa do projeto diverge do medido": "Design assumption differs from what was measured",
  "Efeito sazonal": "Seasonal effect",
  "Causa não identificada": "Cause not identified",
  "Graus-dia de resfriamento": "Cooling degree-days",
  "Irradiação (kWh/m²·dia)": "Irradiation (kWh/m²·day)",
  "Produção ou ocupação (Gestão)": "Production or occupancy (Management)",
  "Chuva do mês (mm)": "Rainfall in the month (mm)",
  "Sem plano": "No plan",
  "Fora do plano agora": "Off plan now",
  "Saiu do plano no período": "Went off plan in the period",
  "Dentro do plano": "Within plan",
  "Totais do período": "Period totals",
  "Medido": "Measured",
  "Meses comparados": "Months compared",
  "Primeiro mês fora do limite:": "First month over the limit:",
  "Primeiro mês fora do limite": "First month over the limit",
  "Ver o módulo": "See the module",
  "Barras: medido.": "Bars: measured.",
  "Linha tracejada azul: planejado.": "Dashed blue line: planned.",
  "Barra com borda e ponto de exclamação: mês fora do limite.": "Bar with an outline and an exclamation mark: month over the limit.",
  "Evidência": "Evidence",
  "Dias com leitura": "Days with readings",
  "Dias com leitura (%)": "Days with readings (%)",
  "Mínimo para o mês valer": "Minimum for the month to count",
  "Variável do clima": "Weather variable",
  "Esperado no plano": "Expected in the plan",
  "Diferença": "Difference",
  "Razão medido ÷ planejado no mês": "Measured ÷ planned ratio in the month",
  "Mediana da razão nos meses anteriores": "Median ratio in previous months",
  "Meses no histórico": "Months in the history",
  "z robusto": "robust z",
  "Meses seguidos no mesmo sentido": "Consecutive months in the same direction",
  "Desvio médio nesses meses": "Mean deviation in those months",
  "Variação da razão medido ÷ planejado": "Variation of the measured ÷ planned ratio",
  "Premissa do plano": "Plan assumption",
  "igual todo mês": "the same every month",
  "Média medida no período": "Mean measured in the period",
  "Medido no mês": "Measured in the month",
  "Nenhuma regra explica o desvio: confira em campo.": "No rule explains the deviation: check on site.",
  "Confiança alta": "High confidence",
  "Confiança média": "Medium confidence",
  "Confiança baixa": "Low confidence",
  "Sem confiança": "No confidence",
  "Quanto:": "How much:",
  "Como:": "How:",
  "Por quê:": "Why:",
  "Como": "How",
  "Equipamento": "Equipment",
  "Medidor": "Meter",
  "Variável": "Variable",
  "Parte do desvio do mês": "Share of the month's deviation",
  "Causa não identificada é uma resposta válida: o sistema não inventa um motivo.": "Cause not identified is a valid answer: the system does not invent a reason.",
  "Módulo": "Module",
  "Sem plano.": "No plan.",
  "Itens medidos sem planejado:": "Measured items without a plan:",
  "Todos os meses dentro do limite de": "All months within the limit of",
  "Quanto: planejado × medido, mês a mês": "How much: planned × measured, month by month",
  "Planejado, medido e desvio por mês": "Planned, measured and deviation per month",
  "Mês": "Month",
  "Desvio (%)": "Deviation (%)",
  "Situação": "Status",
  "fora": "over",
  "dentro": "within",
  "Desvio = medido − planejado; a porcentagem é sobre o planejado. Limite:": "Deviation = measured − planned; the percentage is over the planned value. Limit:",
  "(premissa a conferir).": "(assumption to be checked).",
  "Quando": "When",
  "Continua fora no último mês": "Still over in the last month",
  "Meses seguidos fora": "Consecutive months over",
  "Trechos fora do limite no período": "Stretches over the limit in the period",
  "sim": "yes",
  "não": "no",
  "De onde vem cada número": "Where each number comes from",
  "Fonte do planejado:": "Source of the planned value:",
  "Premissa:": "Assumption:",
  "Como e por quê, em cada mês fora do limite": "How and why, in each month over the limit",
  "Cada causa vem de uma regra com evidência. A confiança vai de 0 a 1; a causa de cima é a mais provável.": "Each cause comes from a rule with evidence. Confidence goes from 0 to 1; the cause on top is the most likely.",
  "Resumo dos últimos 12 meses": "Summary of the last 12 months",
  "De": "From",
  "a": "to",
  "Módulos fora do plano em algum mês:": "Modules off plan in some month:",
  "Módulos sem plano:": "Modules without a plan:",
  "Relatório de medição e verificação": "Measurement and verification report",
  "Planejado × medido de cada módulo, os meses fora do limite com o como e o por quê, e a linha de base no estilo do IPMVP. Formatos abertos: Documento (ODT) e PDF/A.": "Planned × measured for each module, the months over the limit with the how and the why, and the IPMVP-style baseline. Open formats: Document (ODT) and PDF/A.",
  "Baixar o relatório": "Download the report",
  "Baixar o relatório (ODT)": "Download the report (ODT)",
  "Baixar o relatório (PDF/A)": "Download the report (PDF/A)",
  "Na demonstração, o relatório sai marcado como SIMULADO.": "In the demo, the report is marked as SIMULATED.",
  "Limites usados": "Thresholds used",
  "Limites das regras (premissas, todas a conferir)": "Rule thresholds (assumptions, all to be checked)",
  "Limite": "Limit",
  "Valor": "Amount",
  "conferir": "to check",
  "Desvio que conta como fora do plano (%)": "Deviation that counts as off plan (%)",
  "Dias com leitura para o mês valer (%)": "Days with readings for the month to count (%)",
  "Diferença do clima que explica o desvio (%)": "Weather difference that explains the deviation (%)",
  "Meses seguidos para apontar premissa": "Consecutive months to point to an assumption",
  "Variação máxima da razão nesses meses (%)": "Maximum ratio variation in those months (%)",
  "Plano igual todo mês: variação até (%)": "Plan the same every month: variation up to (%)",
  "Consumo fora do normal: z robusto maior que": "Consumption outside the normal: robust z greater than",
  "Meses de histórico antes de dizer o normal": "Months of history before stating the normal",
  "Base dos graus-dia (°C)": "Degree-day base (°C)",
  "Meses mínimos da linha de base": "Minimum baseline months",
  "CV(RMSE) máximo da linha de base (%)": "Maximum baseline CV(RMSE) (%)",
  "Poucos meses com consumo e variável: a regressão precisa de pelo menos 3.": "Few months with consumption and variable: the regression needs at least 3.",
  "Base mais curta que o recomendado (um ciclo inteiro de operação).": "Baseline shorter than recommended (a full operating cycle).",
  "CV(RMSE) acima do limite: o modelo explica pouco o consumo.": "CV(RMSE) above the limit: the model explains little of the consumption.",
  "Poucos meses.": "Few months.",
  "Modelo da linha de base": "Baseline model",
  "Inclinação (a)": "Slope (a)",
  "Intercepto (b)": "Intercept (b)",
  "CV(RMSE) (%)": "CV(RMSE) (%)",
  "Meses na base": "Months in the baseline",
  "Linha de base dentro dos critérios (premissas a conferir).": "Baseline within the criteria (assumptions to be checked).",
  "Economia pela equação geral do IPMVP": "Savings by the IPMVP general equation",
  "Grandeza": "Quantity",
  "Linha de base (soma medida na base)": "Baseline (sum measured in the baseline)",
  "Período de relatório (soma medida)": "Reporting period (sum measured)",
  "Esperado pela linha de base nas condições do relatório": "Expected by the baseline under reporting conditions",
  "Ajuste rotineiro": "Routine adjustment",
  "Ajuste não rotineiro": "Non-routine adjustment",
  "Economia": "Savings",
  "Economia (%)": "Savings (%)",
  "Economia = (linha de base − período de relatório) ± ajustes: a mesma equação da aba Certificações. O ajuste rotineiro leva a linha de base às condições do período de relatório.": "Savings = (baseline − reporting period) ± adjustments: the same equation as the Certifications tab. The routine adjustment brings the baseline to the conditions of the reporting period.",
  "Abrir Certificações · Medição e verificação (IPMVP)": "Open Certifications · Measurement and verification (IPMVP)",
  "O consumo esperado aprende com os dados do próprio lugar: uma regressão linear simples do consumo de cada mês do período de base contra a variável que o move (graus-dia, irradiação ou produção). No período de relatório, a linha de base diz quanto se gastaria sem a medida, nas mesmas condições.": "Expected consumption is learned from the site's own data: a simple linear regression of each month's consumption in the baseline period against the variable that drives it (degree-days, irradiation or production). In the reporting period, the baseline says how much would be used without the measure, under the same conditions.",
  "Linha de base simulada": "Simulated baseline",
  "Período de base": "Baseline period",
  "Período de relatório": "Reporting period",
  "Equipamento com planejado": "Equipment with a plan",
  "Variável que move o consumo": "Variable that drives consumption",
  "Período de base: primeiro mês": "Baseline period: first month",
  "Período de base: último mês": "Baseline period: last month",
  "Período de relatório: primeiro mês": "Reporting period: first month",
  "Período de relatório: último mês": "Reporting period: last month",
  "Calcular a linha de base": "Calculate the baseline",
  "Grave um planejado (parte Planejado) com o medidor do equipamento para calcular a linha de base.": "Save a plan (Planned section) with the equipment's meter to calculate the baseline.",
  "Planejados gravados: módulo, equipamento, medidor e fonte": "Saved plans: module, equipment, meter and source",
  "Fonte": "Source",
  "Ações": "Actions",
  "Apagar": "Delete",
  "Nenhum planejado gravado.": "No plan saved.",
  "O planejado sai do dimensionamento de cada módulo, do Planejador ou de uma premissa, sempre com a fonte. Frota e Carbono vêm sozinhos: o consumo esperado de cada veículo e os fatores do Carbono.": "The planned value comes from each module's sizing, the Planner or an assumption, always with its source. Fleet and Carbon come by themselves: each vehicle's expected consumption and the Carbon factors.",
  "Gravar um planejado": "Save a plan",
  "Trazer o planejado de outra aba": "Bring the planned value from another tab",
  "Trazer da aba Energia solar": "Bring from the Solar energy tab",
  "Trazer da aba Turbinas": "Bring from the Turbines tab",
  "Código do equipamento": "Equipment code",
  "Nome do equipamento": "Equipment name",
  "Medidor no hub (ativo)": "Meter in the hub (asset)",
  "O ativo das leituras: lugar, nó e sufixo, como na tabela de medições.": "The asset of the readings: site, node and suffix, as in the measurements table.",
  "Planejado de janeiro a dezembro (12 valores com ponto e vírgula)": "Planned from January to December (12 values separated by semicolons)",
  "Na unidade do módulo: kWh, m³.": "In the module's unit: kWh, m³.",
  "Clima esperado no plano (12 valores, opcional)": "Weather expected in the plan (12 values, optional)",
  "Irradiação em kWh/m²·dia (solar), chuva em mm (água) ou graus-dia (energia).": "Irradiation in kWh/m²·day (solar), rainfall in mm (water) or degree-days (energy).",
  "Fonte do planejado": "Source of the planned value",
  "Premissa usada (opcional)": "Assumption used (optional)",
  "Gravar o planejado": "Save the plan",
  "ex.: usina-telhado": "e.g.: usina-telhado",
  "ex.: Usina do telhado": "e.g.: Roof plant",
  "ex.: lugar01-no84": "e.g.: lugar01-no84",
  "ex.: 610; 580; 560; …": "e.g.: 610; 580; 560; …",
  "ex.: 5,6; 5,8; …": "e.g.: 5.6; 5.8; …",
  "ex.: Energia solar · dimensionamento de 10/2026": "e.g.: Solar energy · sizing of 10/2026",
  "ex.: agua.per_capita": "e.g.: agua.per_capita",
  "A aba Energia solar ainda não tem dimensionamento com local.": "The Solar energy tab has no sizing with a location yet.",
  "A aba Turbinas ainda não tem energia planejada.": "The Turbines tab has no planned energy yet.",
  "Planejado trazido: confira e grave.": "Planned value brought in: check it and save.",
  "Informe os 12 meses, separados por ponto e vírgula.": "Enter the 12 months, separated by semicolons.",
  "O clima esperado precisa de 12 valores, ou fica vazio.": "The expected weather needs 12 values, or stays empty.",
  "Código do equipamento: letras, números, ponto, hífen ou sublinhado.": "Equipment code: letters, numbers, dot, hyphen or underscore.",
  "Diga a fonte do planejado.": "State the source of the planned value.",
  "Na demonstração, o planejado é SIMULADO: gravar funciona na plataforma instalada.": "In the demo, the plan is SIMULATED: saving works on the installed platform.",
  "Planejado gravado.": "Plan saved.",
  "Não foi possível gravar.": "Could not save.",
  "Planejado apagado.": "Plan deleted.",
  "Não foi possível apagar.": "Could not delete.",
  "Escolha os quatro meses, com o início antes do fim.": "Choose the four months, with the start before the end.",
  "Calculando…": "Calculating…",
  "Não foi possível calcular.": "Could not calculate.",
  "O gerador de documentos não está nesta tela.": "The document generator is not on this screen.",
  "Gerando…": "Generating…",
  "Entre com a sua conta para gerar o PDF/A.": "Sign in with your account to generate the PDF/A.",
  "Sem o computador central, o PDF/A não sai: baixe o ODT e exporte para PDF/A no LibreOffice.": "Without the central computer there is no PDF/A: download the ODT and export it to PDF/A in LibreOffice.",
  "Não foi possível gerar o relatório.": "Could not generate the report.",
  "sem ligação com o computador central": "no connection to the central computer",
  "Usina do telhado (SIMULADA)": "Roof plant (SIMULATED)",
  "Hidrômetro geral (SIMULADO)": "Main water meter (SIMULATED)",
  "Quadro geral e AVAC (SIMULADO)": "Main panel and HVAC (SIMULATED)",
  "Turbina da descida de água (SIMULADA)": "Water downpipe turbine (SIMULATED)",
  "Caminhão (SIMULADO)": "Truck (SIMULATED)",
  "Trator (SIMULADO)": "Tractor (SIMULATED)",
  "Energia solar · dimensionamento (SIMULADO)": "Solar energy · sizing (SIMULATED)",
  "Premissa de consumo por pessoa × moradores (SIMULADO)": "Per-person consumption assumption × residents (SIMULATED)",
  "Projeto de AVAC e linha de base (SIMULADO)": "HVAC design and baseline (SIMULATED)",
  "Turbinas · energia planejada (SIMULADO)": "Turbines · planned energy (SIMULATED)",
  "Frota e combustível · consumo esperado do cadastro (SIMULADO)": "Fleet and fuel · expected consumption from the register (SIMULATED)",
  "ocupação de projeto (SIMULADA)": "design occupancy (SIMULATED)",
  "Energia × fator da rede do Carbono": "Energy × Carbon grid factor",
  "Frota × fatores de combustão móvel do Carbono": "Fleet × Carbon mobile combustion factors",
  "combustível": "fuel",
  "rede elétrica": "power grid",
  "Quadro geral e AVAC (SIMULADO) · rede elétrica": "Main panel and HVAC (SIMULATED) · power grid",
  "Caminhão (SIMULADO) · combustível": "Truck (SIMULATED) · fuel",
  "Trator (SIMULADO) · combustível": "Tractor (SIMULATED) · fuel",
  "Energia solar · dimensionamento (geração do ano repartida pela irradiação de cada mês)": "Solar energy · sizing (yearly generation split by each month's irradiation)",
  "Turbinas · energia do ano planejada, repartida pelos dias de cada mês": "Turbines · planned yearly energy, split by the days of each month",
  "Validação M&V": "M&V validation",
  "Relatório de medição e verificação · planejado × medido": "Measurement and verification report · planned × measured",
  "Dados SIMULADOS da Casa Physis: não usar como laudo.": "SIMULATED data from Casa Physis: do not use as an expert report.",
  "Período:": "Period:",
  ". Limite de desvio:": ". Deviation limit:",
  "% (premissa a conferir).": "% (assumption to be checked).",
  "Quando: primeiro mês fora do limite": "When: first month over the limit",
  "mês(es) seguidos": "consecutive month(s)",
  "; continua fora no último mês": "; still over in the last month",
  "Quando: todos os meses dentro do limite.": "When: all months within the limit.",
  ", variável": ", variable",
  "% do desvio do mês.": "% of the month's deviation.",
  "(confiança": "(confidence",
  "Fontes do planejado:": "Sources of the planned values:",
  "Linha de base (estilo IPMVP)": "Baseline (IPMVP style)",
  "Modelo: consumo =": "Model: consumption =",
  "× variável +": "× variable +",
  "; CV(RMSE)": "; CV(RMSE)",
  "meses na base.": "months in the baseline.",
  "Economia = (linha de base − período de relatório) ± ajustes": "Savings = (baseline − reporting period) ± adjustments",
  "Linha de base não calculada: escolha o equipamento, a variável e os períodos na parte Linha de base.": "Baseline not calculated: choose the equipment, the variable and the periods in the Baseline section.",
  "Método e limites": "Method and limits",
  "Desvio = medido − planejado; % sobre o planejado.": "Deviation = measured − planned; % over the planned value.",
  "Medido: média do dia × 24 h das leituras do hub, somada no mês; dias sem leitura aparecem como falha de dado.": "Measured: daily mean × 24 h of the hub readings, summed over the month; days without readings show up as a data gap.",
  "Causas por regras com evidência; causa não identificada é aceita.": "Causes by rules with evidence; cause not identified is accepted.",
  "IPMVP citado só pelo nome; regressão linear simples; premissas validacao.* a conferir.": "IPMVP cited by name only; simple linear regression; validacao.* assumptions to be checked.",
  "Validação preliminar: não substitui o projeto com responsável técnico.": "Preliminary validation: does not replace the design signed by a qualified professional.",
  "Apagar o planejado de": "Delete the plan of",
  "média": "medium",
  "Uso interno": "Internal use",
  "Produto 3 do SustainKit: planejado × medido de cada módulo, mês a mês, com quanto, quando, como e por quê.": "SustainKit product 3: planned × measured for each module, month by month, with how much, when, how and why.",
  "Versão 0.1: as regras e os limites são premissas a conferir com 12 meses de dados reais da Casa Physis.": "Version 0.1: the rules and thresholds are assumptions to be checked against 12 months of real Casa Physis data.",
  "No nível 4, a medição contínua fica na aba Validação: planejado × medido de cada módulo, mês a mês, com a linha de base por regressão.": "At level 4, continuous measurement is in the Validation tab: planned × measured for each module, month by month, with the regression baseline.",
  "Abrir a Validação": "Open Validation",
  "Validação · planejado × gerado": "Validation · planned × generated",
  "Produto 3 do SustainKit: o que foi planejado aqui × o que está sendo realmente gerado e consumido, mês a mês, com quanto, quando, como e por quê.": "SustainKit product 3: what was planned here × what is really being generated and consumed, month by month, with how much, when, how and why.",
  "Produto 3 do SustainKit: o planejado de cada módulo (dimensionamento, Planejador, premissas) × o medido pelo hub, mês a mês, dizendo quanto desviou, quando começou, em qual equipamento e por quê (clima, equipamento desligado, consumo fora do normal, premissa ou estação), com a linha de base no estilo do IPMVP.": "SustainKit product 3: each module's planned value (sizing, Planner, assumptions) × what the hub measures, month by month, saying how much it deviated, when it started, in which equipment and why (weather, equipment off, consumption outside the normal, assumption or season), with an IPMVP-style baseline.",
  "Planejado de cada módulo, com a fonte": "Planned value of each module, with its source",
  "Leituras do hub (V6, MQTT, importações)": "Hub readings (V6, MQTT, imports)",
  "Clima medido (irradiação, chuva, temperatura)": "Measured weather (irradiation, rainfall, temperature)",
  "Consumo esperado da Frota e fatores do Carbono": "Fleet expected consumption and Carbon factors",
  "Tabela validacao_plano no banco do hub (validacao.py); medido da tabela medicao; premissas validacao.* (conferir).": "validacao_plano table in the hub database (validacao.py); measured values from the medicao table; validacao.* assumptions (to check).",
  "Não precisa (usa os medidores dos outros módulos).": "Not needed (uses the meters of the other modules).",
  "Em desenvolvimento: contas com espelho em validacao.py, regras de causa e relatório ODT e PDF/A prontos; limites a conferir com 12 meses de dados reais.": "In development: calculations mirrored in validacao.py, cause rules and ODT and PDF/A report ready; thresholds to be checked against 12 months of real data.",
  "Conferir": "Check",
  "% de confiança, limite": "% confidence, limit",
  ". Fronteira de medição:": ". Measurement boundary:",
  "Ajuste mínimo": "Minimum fit",
  "Alarmes de desvio": "Deviation alarms",
  "Alarmes: trecho, desvio, R$ em risco, causa provável e ação sugerida": "Alarms: stretch, deviation, R$ at risk, probable cause and suggested action",
  "Anexo de rastreabilidade": "Traceability annex",
  "Análise de incerteza": "Uncertainty analysis",
  "Arquivos de entrada e saída": "Input and output files",
  "Autocorrelação dos resíduos": "Residual autocorrelation",
  "Ação sugerida": "Suggested action",
  "Cadastro de medidores e alertas de calibração": "Meter register and calibration alerts",
  "Calibração vencida": "Calibration overdue",
  "Campo do PEE (ANEEL)": "PEE (ANEEL) field",
  "Carimbo de tempo inválido": "Invalid timestamp",
  "Carimbo de tempo no futuro": "Timestamp in the future",
  "Carimbo de tempo repetido": "Repeated timestamp",
  "Casa Physis (SIMULADA): quadro geral com o AVAC, usina do telhado, turbina e hidrômetro.": "Casa Physis (SIMULATED): main panel with HVAC, roof plant, turbine and water meter.",
  "Causa provável": "Probable cause",
  "Certificado de calibração (arquivo)": "Calibration certificate (file)",
  "Classe provável": "Probable class",
  "Coleta dos dados": "Data collection",
  "Comparação com as metas": "Comparison with targets",
  "Comparação com as metas do plano": "Comparison with the plan targets",
  "Competência (CMVP ou equivalente)": "Competence (CMVP or equivalent)",
  "Competência (opcional)": "Competence (optional)",
  "Conferir a alimentação e a comunicação do medidor e do nó; repor os dias perdidos se houver outra fonte.": "Check the power and communication of the meter and node; restore the lost days if there is another source.",
  "Conferir a calibração dos medidores": "Check the meter calibration",
  "Conferir a perda de dados do mês": "Check the month's data loss",
  "Confiança (%)": "Confidence (%)",
  "Custo da M&V / custo total (%)": "M&V cost / total cost (%)",
  "Custo da M&V ÷ custo total": "M&V cost ÷ total cost",
  "Cópias dos arquivos de entrada e saída": "Copies of the input and output files",
  "Cópias dos arquivos de entrada e saída da simulação": "Copies of the simulation input and output files",
  "Dados e modelo": "Data and model",
  "Decisão": "Decision",
  "Decisão registrada.": "Decision recorded.",
  "Deriva por CUSUM": "Drift by CUSUM",
  "Descrição do projeto": "Project description",
  "Dias efetivos na base": "Effective days in the baseline",
  "Diga o motivo da decisão.": "State the reason for the decision.",
  "Diga por que o plano mudou.": "State why the plan changed.",
  "EnPI: base × relatório": "EnPI: baseline × reporting",
  "Equipamento novo (subiu a carga de base, noite e dia)": "New equipment (base load rose, night and day)",
  "Erro / precisão / confiança alcançados (%)": "Achieved error / precision / confidence (%)",
  "Erro alcançado (%)": "Achieved error (%)",
  "Erro do modelo": "Model error",
  "Erro padrão": "Standard error",
  "Escolha a opção IPMVP (A, B, C ou D).": "Choose the IPMVP option (A, B, C or D).",
  "Escreva a lição.": "Write the lesson.",
  "Etapas de QA": "QA steps",
  "Eventos não rotineiros prováveis e o ajuste proposto": "Probable non-routine events and the proposed adjustment",
  "Exatidão (%)": "Accuracy (%)",
  "Exatidão desconhecida [CONFERIR]": "Unknown accuracy [CONFERIR]",
  "Exatidão do medidor": "Meter accuracy",
  "Excluir o período sem dado": "Exclude the period without data",
  "Fatores estáticos": "Static factors",
  "Fatura × soma dos dados de intervalo": "Bill × sum of interval data",
  "Fontes da incerteza, da maior para a menor (Monte Carlo)": "Uncertainty sources, largest first (Monte Carlo)",
  "Fontes de dados (medidores e pontos)": "Data sources (meters and points)",
  "Fora de ordem (usado na ordem certa)": "Out of order (used in the right order)",
  "Formato do relatório": "Report format",
  "Fronteira de medição": "Measurement boundary",
  "Hidrômetro (SIMULADO)": "Water meter (SIMULATED)",
  "Horário de uso": "Hours of use",
  "Iluminação LED (SIMULADO)": "LED lighting (SIMULATED)",
  "Indicadores de desempenho (EnPI)": "Performance indicators (EnPI)",
  "Informe o medidor (ativo) e o tipo.": "Enter the meter (asset) and the type.",
  "Inspecionar o equipamento e a operação (horário, ajuste, vazamento) e registrar a inspeção.": "Inspect the equipment and operation (schedule, setpoint, leak) and record the inspection.",
  "Inspeção": "Inspection",
  "Inspeção em campo; registrar o que foi achado no diário de lições.": "On-site inspection; record what was found in the lessons log.",
  "Inspeção registrada.": "Inspection recorded.",
  "Instalação inteira (fatura ou medidor geral)": "Whole facility (bill or main meter)",
  "Intervalo de confiança (Monte Carlo)": "Confidence interval (Monte Carlo)",
  "Justificativa da opção": "Option justification",
  "Limite (parte da economia)": "Limit (share of savings)",
  "Linha de base diária com ponto de mudança na temperatura do ar; economia pela equação geral.": "Daily change-point baseline on air temperature; savings by the general equation.",
  "Lição registrada.": "Lesson recorded.",
  "Lâmpadas (SIMULADO)": "Lamps (SIMULATED)",
  "Geladeiras (SIMULADO)": "Refrigerators (SIMULATED)",
  "Manter o plano de coleta e a revisão anual.": "Keep the collection plan and the annual review.",
  "Medidas de eficiência (ECM)": "Efficiency measures (ECM)",
  "Medidas de eficiência (ECM):": "Efficiency measures (ECM):",
  "Medidas de eficiência e a última inspeção": "Efficiency measures and the last inspection",
  "Medidas que se misturam no mesmo quadro: só a instalação inteira mostra o efeito (SIMULADO).": "Measures mixed in the same panel: only the whole facility shows the effect (SIMULATED).",
  "Medidor da turbina (SIMULADO)": "Turbine meter (SIMULATED)",
  "Medidor de energia (SIMULADO)": "Energy meter (SIMULATED)",
  "Medidor geral de energia na entrada e hidrômetro geral (SIMULADOS).": "Main energy meter at the service entrance and main water meter (SIMULATED).",
  "Medidor gravado no registro.": "Meter saved to the registry.",
  "Medidores e dados": "Meters and data",
  "Medição isolada de todos os parâmetros": "Retrofit isolation, all parameters",
  "Medição isolada do parâmetro-chave": "Retrofit isolation, key parameter",
  "Mensal, com fechamento anual": "Monthly, with yearly close",
  "Modelo escolhido (validação cruzada)": "Chosen model (cross-validation)",
  "Modelos com ponto de mudança (2P a 5P) e o de vizinhos, pelo ajuste": "Change-point models (2P to 5P) and the neighbours model, by fit",
  "Modelos e incerteza": "Models and uncertainty",
  "Mudança de horário (o consumo mudou de hora)": "Schedule change (consumption moved in time)",
  "Mudança de nível sem padrão claro": "Level change without a clear pattern",
  "Mudança de ocupação (subiu só nas horas ocupadas)": "Occupancy change (rose only in occupied hours)",
  "Método de cálculo": "Calculation method",
  "Método e opção IPMVP": "Method and IPMVP option",
  "Na demonstração, o diário é SIMULADO: registrar funciona na plataforma instalada.": "In the demo, the log is SIMULATED: recording works on the installed platform.",
  "Na demonstração, o plano é SIMULADO: gravar funciona na plataforma instalada.": "In the demo, the plan is SIMULATED: saving works on the installed platform.",
  "Na demonstração, os medidores são SIMULADOS: gravar funciona na plataforma instalada.": "In the demo, the meters are SIMULATED: saving works on the installed platform.",
  "Nada a corrigir no equipamento: registrar o clima do período e levar à linha de base.": "Nothing to fix in the equipment: record the weather of the period and take it to the baseline.",
  "Nova versão gravada no registro.": "New version saved to the registry.",
  "NÃO operando": "NOT operating",
  "Não foi possível abrir a tarefa.": "Could not open the task.",
  "Não foi possível registrar.": "Could not record.",
  "Nível de confiança": "Confidence level",
  "O quê": "What",
  "Opção D: guarde as cópias dos arquivos de entrada e saída (nome e SHA-256).": "Option D: keep the copies of the input and output files (name and SHA-256).",
  "Opção D: informe o programa de simulação e a versão.": "Option D: enter the simulation software and version.",
  "Opção IPMVP": "IPMVP option",
  "Opção IPMVP:": "IPMVP option:",
  "Pacote de auditoria pedido ao computador central.": "Audit package requested from the central computer.",
  "Parte da variância": "Share of variance",
  "Perda de dados": "Data loss",
  "Perda de dados (%)": "Data loss (%)",
  "Perfil PEE (ANEEL): números do projeto; exigências aguardando o Guia de M&V": "PEE (ANEEL) profile: project numbers; requirements awaiting the M&V Guide",
  "Períodos de base e de relatório definidos (SIMULADO)": "Baseline and reporting periods defined (SIMULATED)",
  "Plano amostral por estrato (fórmula estatística genérica, não a da ANEEL)": "Sampling plan by stratum (generic statistical formula, not ANEEL's)",
  "Plano de M&V": "M&V plan",
  "Política de faltantes": "Missing-data policy",
  "Ponto(s) de mudança (°C)": "Change point(s) (°C)",
  "Pontos marcados na limpeza": "Points flagged by cleaning",
  "Por que mudou (vai para o registro)": "Why it changed (goes to the registry)",
  "Precisão (%)": "Precision (%)",
  "Precisão alcançada": "Achieved precision",
  "Preencher pelo modelo da linha de base": "Fill with the baseline model",
  "Preencher por interpolação linear": "Fill by linear interpolation",
  "Programa de simulação": "Simulation software",
  "Projeção até o fim do período": "Projection to the end of the period",
  "Próxima calibração": "Next calibration",
  "Qualidade dos dados": "Data quality",
  "Qualidade por medidor: granularidade, perda e marcas": "Quality per meter: granularity, loss and flags",
  "Quem coleta, analisa, arquiva e relata": "Who collects, analyses, archives and reports",
  "R$ em risco": "R$ at risk",
  "Rastreabilidade: leituras, fator da rede, premissas, ajustes e versão do modelo": "Traceability: readings, grid factor, assumptions, adjustments and model version",
  "Recomendações": "Recommendations",
  "Redução de demanda na ponta (kW)": "Peak demand reduction (kW)",
  "Relatório padrão ODT e PDF/A": "Standard ODT and PDF/A report",
  "Relação custo-benefício (RCB)": "Cost-benefit ratio (RCB)",
  "Resultado verificado registrado (entra no lote diário de integridade).": "Verified result recorded (goes into the daily integrity lot).",
  "Revisar a premissa com a equipe e registrar a mudança no plano de M&V (com o motivo).": "Review the assumption with the team and record the change in the M&V plan (with the reason).",
  "Revisar os pontos marcados na limpeza": "Review the points flagged by cleaning",
  "Revisão anual": "Annual review",
  "SIMULADO: o hidrômetro sem calibração deixa a água fora do relatório de economia até ter certificado.": "SIMULATED: the uncalibrated water meter keeps water out of the savings report until it has a certificate.",
  "Sem data de calibração [CONFERIR]": "No calibration date [CONFERIR]",
  "Sem modelo diário: defina os períodos de base e de relatório no plano de M&V.": "No daily model: set the baseline and reporting periods in the M&V plan.",
  "Simulação calibrada": "Calibrated simulation",
  "Simulação:": "Simulation:",
  "Tarefa aberta na Gestão, com a evidência.": "Task opened in Management, with the evidence.",
  "Temperatura média do dia (graus-dia)": "Daily mean temperature (degree-days)",
  "Trocar o planejado igual todo mês por um planejado com estação.": "Replace the flat monthly plan with a seasonal plan.",
  "Valor atípico": "Outlier",
  "Valor impossível": "Impossible value",
  "Valor negativo": "Negative value",
  "Sensor travado": "Stuck sensor",
  "Variação (%)": "Change (%)",
  "Variáveis independentes": "Independent variables",
  "Versão do modelo": "Model version",
  "Versão do programa": "Software version",
  "Versões do plano de M&V e o registro encadeado": "M&V plan versions and the chained registry",
  "Válidas": "Valid",
  "a fronteira de medição": "the measurement boundary",
  "a justificativa da opção": "the option justification",
  "com IC de": "with a CI of",
  "dados SIMULADOS (sem leituras do hub)": "SIMULATED data (no hub readings)",
  "estação do lugar (SIMULADA)": "site weather station (SIMULATED)",
  "kWh por unidade produzida": "kWh per unit produced",
  "km medidos da frota": "measured fleet km",
  "lugar01-no81-ar (temperatura do ar)": "lugar01-no81-ar (air temperature)",
  "lugar01-no85 (água, mensal)": "lugar01-no85 (water, monthly)",
  "lugar01-no84 (energia, 15 min)": "lugar01-no84 (energy, 15 min)",
  "não operando": "not operating",
  "operando": "operating",
  "não usado": "not used",
  "o método de cálculo": "the calculation method",
  "ocupantes do plano de M&V": "occupants from the M&V plan",
  "produção da Gestão": "production from Management",
  "resíduos do modelo": "model residuals",
  "sem modelo": "no model",
  "t de Student": "Student's t",
  "Área climatizada": "Conditioned area",
  "Última calibração": "Last calibration",
  "Última inspeção": "Last inspection",
  "área do plano de M&V": "area from the M&V plan",
  "Painel M&V 2.0": "M&V 2.0 dashboard",
  "Economia acumulada": "Cumulative savings",
  "Economia acumulada quase em tempo real com as leituras do hub (V6, MQTT e importações), indicadores e alarmes de desvio com a causa provável e a ação sugerida.": "Near-real-time cumulative savings from the hub readings (V6, MQTT and imports), indicators and deviation alarms with the probable cause and suggested action.",
  "Granularidade nativa": "Native granularity",
  "Temperatura": "Temperature",
  "atende": "meets",
  "não atende": "does not meet",
  "Incerteza da economia": "Savings uncertainty",
  "Tarefas atrasadas": "Overdue tasks",
  "itens": "items",
  "trechos": "stretches",
  "% do esperado": "% of expected",
  "Risco de não atingir a meta.": "Risk of missing the target.",
  "Meta:": "Target:",
  "; projeção pela persistência:": "; persistence projection:",
  "; em risco:": "; at risk:",
  "A projeção atinge a meta.": "The projection meets the target.",
  "Economia acumulada: esperado pela linha de base − medido, dia a dia.": "Cumulative savings: baseline expected − measured, day by day.",
  "Pacote de auditoria e resultado verificado": "Audit package and verified result",
  "Exportar pacote de auditoria": "Export audit package",
  "Registrar resultado verificado": "Record verified result",
  "Alarmes de desvio (FDD)": "Deviation alarms (FDD)",
  "Alarme só quando o medido sai do intervalo de previsão do modelo, por dias seguidos; ordenados pelo R$ em risco. O mesmo trecho não se repete.": "Alarm only when the measured value leaves the model's prediction interval for consecutive days; sorted by R$ at risk. The same stretch is not repeated.",
  "Gestão": "Management",
  "tarefa aberta": "task open",
  "Criar tarefa na Gestão": "Create task in Management",
  "Nenhum alarme de desvio.": "No deviation alarms.",
  "Modo automático (abre a tarefa sozinho em falha de equipamento ou de operação):": "Automatic mode (opens the task by itself on equipment or operation faults):",
  "ligado": "on",
  "desligado": "off",
  ", no plano de M&V.": ", in the M&V plan.",
  "De onde vem a incerteza": "Where the uncertainty comes from",
  "Exatidão do medidor desconhecida [CONFERIR]: cadastre-a em Medidores e dados.": "Unknown meter accuracy [CONFERIR]: register it in Meters and data.",
  "Deriva do modelo e do sensor (CUSUM)": "Model and sensor drift (CUSUM)",
  "Modelo": "Model",
  "Sensor": "Sensor",
  "sem deriva": "no drift",
  "Referência": "Reference",
  "Eventos não rotineiros": "Non-routine events",
  "Mudança de nível que o modelo não explica. O ajuste não rotineiro só entra na conta depois da aprovação de uma pessoa, e a decisão vai para o registro.": "A level change the model does not explain. The non-routine adjustment only enters the calculation after a person approves it, and the decision goes to the registry.",
  "Desde": "Since",
  "Nível": "Level",
  "Ajuste proposto": "Proposed adjustment",
  "Aprovar": "Approve",
  "Recusar": "Reject",
  "Nenhum evento não rotineiro.": "No non-routine events.",
  "Motivo da decisão": "Reason for the decision",
  "Conferência com a fatura": "Cross-check with the bill",
  "A fonte principal são os dados de intervalo; a fatura e o digitado servem só para conferir.": "Interval data is the primary source; the bill and typed values are only used to cross-check.",
  "Fatura": "Bill",
  "Intervalo": "Interval",
  "Sem faturas no plano de M&V.": "No bills in the M&V plan.",
  "fatura": "bill",
  "carga de base do período de base (confirme com a fatura)": "base load of the baseline period (confirm with the bill)",
  "Perfil do programa:": "Program profile:",
  "Geral (IPMVP)": "General (IPMVP)",
  "PEE (ANEEL)": "PEE (ANEEL)",
  "Perfil PEE (ANEEL)": "PEE (ANEEL) profile",
  "As exigências numéricas do PEE (confiança, precisão, amostra, duração, vida útil, RCB, taxa e prazos) aguardam a leitura do Guia de M&V da ANEEL:": "The PEE numeric requirements (confidence, precision, sample, duration, lifetime, RCB, rate and deadlines) await the reading of ANEEL's M&V Guide:",
  "Perfil PEE": "PEE profile",
  "Energia economizada (MWh/ano)": "Energy saved (MWh/year)",
  "aguardando Guia": "awaiting the Guide",
  "sem dado": "no data",
  "Estrato": "Layer",
  "População": "Population",
  "Amostra": "Sample",
  "Medidos": "Measured units",
  "Exatidão": "Accuracy",
  "Incerteza": "Uncertainty",
  "Comissionamento": "Commissioning",
  "Certificado": "Certificate",
  "Alertas": "Alerts",
  "em dia": "up to date",
  "Sem certificado": "No certificate",
  "Nenhum medidor cadastrado.": "No meter registered.",
  "Medidores": "Meters",
  "Tipo, modelo, exatidão e incerteza, data de comissionamento, última e próxima calibração e o certificado (arquivo resumido em SHA-256 neste aparelho).": "Type, model, accuracy and uncertainty, commissioning date, last and next calibration and the certificate (file summarised as SHA-256 on this device).",
  "Cadastrar ou mudar um medidor": "Register or change a meter",
  "Tipo": "Type",
  "Incerteza (%)": "Uncertainty (%)",
  "Gravar o medidor": "Save the meter",
  "A granularidade nativa fica como veio (15 min, hora ou só o mês). A limpeza marca lacunas, valores atípicos, carimbos de tempo, sensor travado e valores negativos ou impossíveis; o valor original fica sempre ao lado e nada é trocado em silêncio.": "The native granularity is kept as it came (15 min, hour or month only). Cleaning flags gaps, outliers, timestamps, stuck sensors and negative or impossible values; the original value always stays alongside and nothing is changed silently.",
  "Plano de coleta: perda de dados máxima de": "Collection plan: maximum data loss of",
  "Leituras": "Readings",
  "Marcas": "Flags",
  "Sem leituras.": "No readings.",
  "Ver os pontos marcados (original e marca)": "See the flagged points (original and flag)",
  "Quando (UTC)": "When (UTC)",
  "Original": "Original",
  "Usado": "Used",
  "Um plano por instalação, guardado e versionado no computador central. Cada mudança vai para o registro encadeado do hub: quem, quando e por quê.": "One plan per installation, stored and versioned on the central computer. Every change goes to the hub's chained registry: who, when and why.",
  "Versão atual:": "Current version:",
  "Sem plano de M&V gravado nesta instalação.": "No M&V plan saved for this installation.",
  "Simulação": "Simulation",
  "Programa": "Software",
  "Pessoas e papéis": "People and roles",
  "Pessoa": "Person",
  "não informada": "not stated",
  "A competência é só um campo: o sistema nunca supõe que alguém tem certificação.": "Competence is only a field: the system never assumes anyone is certified.",
  "Tarefas": "Tasks",
  "Nada pendente.": "Nothing pending.",
  "Inspeção periódica das medidas": "Periodic inspection of the measures",
  "Confirma que cada medida de eficiência continua funcionando. Sem inspeção no prazo, vira tarefa.": "Confirms that each efficiency measure is still working. Without an inspection on time, it becomes a task.",
  "Medida": "Measure",
  "Registrar": "Record",
  "O plano não lista medidas de eficiência.": "The plan lists no efficiency measures.",
  "Versões do plano": "Plan versions",
  "Versão": "Version",
  "Quem": "Who",
  "Por quê": "Why",
  "Registro": "Log",
  "Nenhuma versão ainda.": "No version yet.",
  "Mudar o plano de M&V": "Change the M&V plan",
  "Listas: um item por linha. Arquivos da simulação: nome; SHA-256; entrada ou saída. Medidas: código; nome.": "Lists: one item per line. Simulation files: name; SHA-256; input or output. Measures: code; name.",
  "Escopo": "Scope",
  "Formato": "Format",
  "Periodicidade": "Periodicity",
  "Área (m²)": "Area (m²)",
  "Ocupantes": "Occupants",
  "Opção D: simulação": "Option D: simulation",
  "Gravar nova versão do plano": "Save a new plan version",
  "Diário de lições aprendidas": "Lessons-learned log",
  "Nenhuma lição registrada.": "No lesson recorded.",
  "Nova lição": "New lesson",
  "Registrar a lição": "Record the lesson",
  "Dias no período de base:": "Days in the baseline period:",
  "Escolha": "Choose",
  "escolhido": "chosen",
  "Modelo aceito": "Model accepted",
  "Modelo fora dos critérios": "Model outside the criteria",
  "R² baixo": "Low R²",
  "CV(RMSE) alto": "High CV(RMSE)",
  "NMBE alto": "High NMBE",
  "Sem economia no período de relatório para calcular a incerteza.": "No savings in the reporting period to calculate the uncertainty.",
  "Poucos dias com consumo e temperatura no período de base.": "Few days with consumption and temperature in the baseline period.",
  "Indicadores de desempenho (EnPI) e linha de base energética (EnB)": "Performance indicators (EnPI) and energy baseline (EnB)",
  "No conceito da ISO 50006 (citada só pelo nome): consumo dividido pelo que o explica, no período de base e no de relatório.": "Following the ISO 50006 concept (cited by name only): consumption divided by what explains it, in the baseline and reporting periods.",
  "Normalizador": "Normaliser",
  "Variação": "Change",
  "Coleta": "Collection",
  "Análise": "Analysis",
  "Arquivo": "File",
  "Relatório": "Report",
  "Defina os períodos de base e de relatório no plano de M&V e grave um planejado de energia ou água com o medidor.": "Set the baseline and reporting periods in the M&V plan and save an energy or water plan with its meter.",
  "Plano de M&V da instalação": "Installation M&V plan",
  "Revisar o plano": "Review the plan",
  "Escrever o plano de M&V da instalação.": "Write the installation's M&V plan.",
  "Marcar a data da revisão anual do plano de M&V.": "Set the date of the M&V plan's annual review.",
  "pendente": "pending",
  "atrasada": "overdue",
  "aprovado": "approved",
  "recusado": "rejected",
  "deriva": "drift",
  "Dados faltantes preenchidos": "Filled missing data",
  "deriva acima": "drift up",
  "deriva abaixo": "drift down",
  "Pessoa: coleta dos dados": "Person: data collection",
  "Pessoa: análise": "Person: analysis",
  "Pessoa: arquivo": "Person: archive",
  "Pessoa: relatório": "Person: report",
  "mês": "month",
  "hora": "hour",
  "dia": "day",
  "Inspeção periódica da medida Iluminação LED (SIMULADO): confirmar que continua operando.": "Periodic inspection of the measure LED lighting (SIMULATED): confirm it is still operating.",
  "lugar01-no86: calibração vencida.": "lugar01-no86: calibration overdue.",
  "lugar01-no85: sem data da próxima calibração [CONFERIR].": "lugar01-no85: no next calibration date [CONFERIR]."
};
window.VALIDACAO_I18N_RX = [
  [
    "^Planejado \\((.+)\\)$",
    "Planned ($1)"
  ],
  [
    "^Medido \\((.+)\\)$",
    "Measured ($1)"
  ],
  [
    "^Desvio \\((.+)\\)$",
    "Deviation ($1)"
  ],
  [
    "^Apagar o planejado de (.+)$",
    "Delete the plan of $1"
  ],
  [
    "^(.+): calibração vencida\\.$",
    "$1: calibration overdue."
  ],
  [
    "^(.+): sem data da próxima calibração \\[CONFERIR\\]\\.$",
    "$1: no next calibration date [CONFERIR]."
  ],
  [
    "^Inspeção periódica da medida (.+): confirmar que continua operando\\.$",
    "Periodic inspection of the measure $1: confirm it is still operating."
  ],
  [
    "^A medida (.+) não estava operando na última inspeção\\.$",
    "The measure $1 was not operating at the last inspection."
  ],
  [
    "^Revisão anual do plano de M&V em (.+)\\.$",
    "Annual review of the M&V plan on $1."
  ],
  [
    "^Revisão anual do plano de M&V atrasada desde (.+)\\.$",
    "Annual review of the M&V plan overdue since $1."
  ],
  [
    "^Pessoa: (.+)$",
    "Person: $1"
  ],
  [
    "^deriva (acima|abaixo)$",
    "drift $1"
  ]
];
})();
