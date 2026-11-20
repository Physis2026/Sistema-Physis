/* physis-avac.js — AVAC e térmico: porta das contas da planilha PHYSIS_AVAC-5_quadro_eletrico
   (abas 0 Controle, 1 Tipologias, 2 Ar condicionado, 3 Ventilação, 4 Pressurização, 5 Aq. solar,
   6 Piscina, 7 Dutos e ventiladores, 8 Quadro elétrico, 9 Resumo, 10 Lista de equipamentos,
   11 Memória de cálculo). Mesmas fórmulas e tabelas de referência da planilha; normas citadas só
   pelo código e pelos parâmetros numéricos que a planilha usa.
   Contrato com a plataforma: define telaAvac() (HTML da aba inteira, sem o quadro elétrico),
   telaQuadroEletrico() (seção com <h2> para a aba Caixinha Physis IoT, mesmo estado e mesmas contas)
   e window.AVAC.calcular(entradas) (função pura, testável). Globais usadas só na hora de desenhar: esc, n2, numBr, el, desenhar, ui,
   calcLer, calcGravar. Estado salvo em calcLer("avac").e; linhas antigas em .amb são migradas. */
(function () {
"use strict";

/* ════════ Tabelas de referência (as mesmas da planilha) ════════ */
const DEG_BTU = [120000, 96000, 84000, 72000, 60000, 48000, 36000, 30000, 24000, 22000, 18000, 12000, 9000, 7000]; // aba 2, R5:R23
const RESERV = [10000, 8000, 6000, 5000, 4000, 3000, 2500, 2000, 1500, 1000, 750, 600, 500];                       // aba 5, N5:N17
const MOTOR_KW = [0.18, 0.25, 0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3, 3.7, 4.5, 5.5, 7.5, 9.2, 11, 15, 18.5, 22, 30, 37, 45, 55, 75]; // aba 7, AD
const MOTOR_CV = [0.25, 0.33, 0.5, 0.75, 1, 1.5, 2, 3, 4, 5, 6, 7.5, 10, 12.5, 15, 20, 25, 30, 40, 50, 60, 75, 100];          // aba 7, AE
const LARG = []; for (let w = 100; w <= 3000; w += 50) LARG.push(w);                                                 // aba 7, AG (passo 50 mm)
/* premissas da base (sistema/physis-premissas.json, pelas contas comuns PhysisCalc). A cópia ao lado é a mesma da base e
   só vale quando o módulo roda sem ela (teste do navegador em ferramentas/testes-navegador). */
const PREM_AVAC = (id, pad) => { try { const v = typeof PhysisCalc !== "undefined" ? PhysisCalc.premissa(id) : null; return v && typeof v === "object" ? v : pad; } catch (e) { return pad; } };
const VEL_DUTO = PREM_AVAC("avac.velocidade_dutos", { "Prumada residencial (shaft)":8, "Ramal em forro — residencial":5, "Exaustão técnica (lixo, bombas)":8, "Garagem":12, "Pressurização e fumaça":12, "Duto principal — comercial":10 });
const TIPOS_DUTO = Object.entries(VEL_DUTO);                                                                         // aba 7, AA:AB
const EXA = PREM_AVAC("avac.exaustao", { vazao_banheiro_m3h:90, trocas_banheiro_h:15, trocas_lixo_h:20, trocas_garagem_h:6, garagem_ls_por_m2:7.5, garagem_m3h_por_vaga:300 });
/* NBR 5410: seções, capacidade de condução (cobre, PVC 70 °C, método B1), FCT, neutro reduzido; disjuntores comerciais */
const SEC = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300];
const IZ2 = [17.5, 24, 32, 41, 57, 76, 101, 125, 151, 192, 232, 269, 309, 353, 415, 477];
const IZ3 = [15.5, 21, 28, 36, 50, 68, 89, 110, 134, 171, 207, 239, 275, 314, 370, 426];
const DISJ = [10, 16, 20, 25, 32, 40, 50, 63, 70, 80, 100, 125, 150, 175, 200, 225, 250, 300, 350, 400, 500, 630];
const FCT_T = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60], FCT_V = [1.22, 1.17, 1.12, 1.06, 1, 0.94, 0.87, 0.79, 0.71, 0.61, 0.5];
const NEU_F = [35, 50, 70, 95, 120, 150, 185, 240, 300], NEU_N = [25, 25, 35, 50, 70, 70, 95, 120, 150];
const FASES_AC = ["RST", "RS", "ST", "RT", "RS", "ST", "RT", "RS"];
const S3 = Math.sqrt(3);
const TIPOS_EMP = ["Residencial multifamiliar", "Loja / varejo", "Edifício comercial", "Shopping center", "Hospital / EAS", "Indústria", "Hotel", "Data center", "Escola"];
const MODULOS = [["ac", "Ar condicionado"], ["vent", "Ventilação e exaustão"], ["press", "Pressurização de escada"], ["solar", "Aquecimento solar"],
  ["piscina", "Aquecimento de piscina"], ["dutos", "Dutos e ventiladores"], ["lista", "Lista de equipamentos"], ["quadro", "Quadro elétrico"]];
const FALTA = { ac:"faltam tipologias, m²/TR ou COP", vent:"faltam tipologias", press:"faltam ΔP, nº de portas ou dimensões", solar:"faltam população ou dados do coletor",
  piscina:"falta a área do espelho d'água", dutos:"depende de ventilação ou pressurização ativas", lista:"nenhum módulo de cálculo ativo", quadro:"nenhum módulo de cálculo ativo" };

/* ════════ Exemplo da planilha (valores-padrão) ════════ */
function padrao() {
  const amb = (n, area, dorm, equip, matriz, q, comum) => ({ n, area, dorm, override:null, equip, matriz, q:q || [], comum:comum || 0 });
  return {
    controle: { nome:"", local:"", tipo:"Residencial multifamiliar", resp:"", data:"", lat:null, lon:null, raio:300,
      ativo: { ac:true, vent:true, press:true, solar:true, piscina:true, dutos:true, lista:true, quadro:true } },
    tipologias: { pessoasDorm:2, lista: [
      { n:"Tipo A  (rosa)", q:206, area:29.73, dorm:1, banh:1, vagas:0 }, { n:"Tipo B (roxo)", q:28, area:52.6, dorm:2, banh:2, vagas:0 },
      { n:"Tipo C (laranja)", q:10, area:53.8, dorm:2, banh:3, vagas:0 }, { n:"Tipo D (azul)", q:64, area:44.6, dorm:2, banh:2, vagas:0 }] },
    ac: { m2TR:15, cop:3.2, btuTR:12000, degraus:DEG_BTU.slice(), amb: [
      amb("Estar / preparo — compacto", 12.92, 0, "Split hi-wall", true, [1]), amb("Estar / preparo ", 15.9, 0, "", false),
      amb("Estar / preparo", 15.25, 0, "", false), amb("Estar / preparo — padrão", 18.25, 0, "Split hi-wall", true, [0, 1, 1, 1]),
      amb("Quarto compacto", 7.11, 1, "Split hi-wall", true, [0, 1, 0, 1]), amb("Quarto 1", 6.1, 1, "", false),
      amb("Quarto 2", 9.03, 1, "Split hi-wall", true, [1]), amb("Suíte", 11.11, 1, "Split hi-wall", true, [0, 1, 2, 1]),
      amb("Suíte 2", 9.62, 1, "", true), amb("Suíte 3", 10.56, 1, "", false), amb("Suíte 4", 8.9, 0, "", false),
      amb("Salão de festas", 80, 0, "Cassete", true, [], 1), amb("Academia", 45, 0, "Cassete", true, [], 1),
      amb("Coworking", 30, 0, "Split hi-wall", true, [], 1), amb("Salão de jogos", 35, 0, "Split hi-wall", true),
      amb("Brinquedoteca", 25, 0, "Split hi-wall", true), amb("Portaria / recepção", 12, 0, "Split hi-wall", true)] },
    vent: { metodo:"Vazão fixa", vazBanh:EXA.vazao_banheiro_m3h, areaBanh:4, peBanh:2.6, trocasBanh:EXA.trocas_banheiro_h, lixoArea:12, lixoPe:2.6, lixoTrocas:EXA.trocas_lixo_h,
      garArea:1800, garPe:2.6, garVagas:0, garTrocas:EXA.trocas_garagem_h, garLsm2:EXA.garagem_ls_por_m2, garVaga:EXA.garagem_m3h_por_vaga,
      outros: [{ n:"Casa de bombas", area:15, pe:2.6, trocas:10 }, { n:"Sala de medidores", area:8, pe:2.6, trocas:6 }] },
    press: { dp:50, v:1, portas:0, abertas:2, w:0.9, h:2.1, fresta:0.02, outras:0, fator:1.25, fechador:50, limite:110 },
    solar: { consumo:50, tq:40, tf:22, fracao:0.7, eta:null, prod:null, incl:null, azim:0, lat:null, H:null, areaCol:2, volM2:75, horas:4, reserv:RESERV.slice() },
    piscina: { area:60, prof:1.4, tw:28, ta:22, ur:70, v:0.5, descoberta:1, capa:1, hCapa:12, redCapa:0.7, paredes:3, ti:22, tAq:24 },
    dutos: { rug:0.00009, fs:1.15, rend:0.6, alt:0, temp:20, rendTransm:0.95, rendMotor:0.88, margem1:0.3, margem2:0.2, sistemas: [
      { nome:"Exaustão de banheiros", fonte:"banheiros", vazao:0, vel:8, reto:40, equiv:30, local:150, altura:600, tipo:"Prumada residencial (shaft)" },
      { nome:"Depósito de lixo", fonte:"lixo", vazao:0, vel:8, reto:15, equiv:10, local:100, altura:200, tipo:"Exaustão técnica (lixo, bombas)" },
      { nome:"Garagem", fonte:"garagem", vazao:0, vel:10, reto:60, equiv:45, local:200, altura:600, tipo:"Garagem" },
      { nome:"Pressurização de escada", fonte:"press", vazao:0, vel:10, reto:45, equiv:35, local:250, altura:600, tipo:"Pressurização e fumaça" }] },
    quadro: { vff:380, vfn:220, tamb:30, fcaC:0.8, fcaA:1, rho70:0.0206, rho20:0.0178, smin:2.5, dvTot:0.04, dvAlim:0.015, dvPart:0.1,
      compAlim:40, deseq:0.1, copPisc:5, icc:10, x:0.08, icnMod:10, icuCM:25, i2t:80000, tCM:0.1, magCM:10, icuAlim:25, tAlim:0.1, magAlim:10,
      k:115, harm:"não", f4:0.86, circ:{}, extras:[], splits:{} }
  };
}

/* ════════ Utilitários puros ════════ */
const MESES_AQ = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const N = v => { if (v === true) return 1; if (v === false || v == null || v === "") return 0; const n = +v; return isFinite(n) ? n : 0; };   // como N() do Excel
const ehObj = o => o && typeof o === "object" && !Array.isArray(o);
function mesclar(base, over) { Object.keys(over || {}).forEach(k => { const v = over[k];
  if (ehObj(v) && ehObj(base[k])) mesclar(base[k], v); else base[k] = v == null ? v : JSON.parse(JSON.stringify(v)); }); return base; }
/* primeiro valor >= x numa lista crescente — o INDEX(lista; CONT.SE(lista;"<"&x)+1) da planilha; null = "acima da tabela" */
function acima(asc, x) { if (!isFinite(x)) return null; let c = 0; for (let i = 0; i < asc.length; i++) if (asc[i] < x) c++; return c < asc.length ? asc[c] : null; }
function secPor(tab, x) { if (!isFinite(x)) return 0; let c = 0; for (let i = 0; i < tab.length; i++) if (tab[i] < x) c++; return c < SEC.length ? SEC[c] : 0; }
const secAcima = x => secPor(SEC, x);
const izDe = (s, tres) => { const i = SEC.indexOf(s); return i < 0 ? null : (tres ? IZ3 : IZ2)[i]; };
const deRet = (a, b) => 1.3 * Math.pow(a * b, 0.625) / Math.pow(a + b, 0.25);   // Huebscher
const maxN = l => { const v = l.filter(x => typeof x === "number" && isFinite(x)); return v.length ? Math.max.apply(null, v) : 0; };
/* FIXED() do Excel em pt-BR: milhar com ponto, decimal com vírgula */
function fx(v, c, semMilhar) { v = Number(v); if (!isFinite(v)) return "—"; const s = Math.abs(v).toFixed(c), p = s.split(".");
  const i = semMilhar ? p[0] : p[0].replace(/\B(?=(\d{3})+(?!\d))/g, "."); return (v < 0 && Number(s) !== 0 ? "-" : "") + i + (p[1] ? "," + p[1] : ""); }
const iaCurva = (inn, curva, mag) => inn > 63 ? mag : (curva === "B" ? 5 : curva === "D" ? 20 : 10);

/* ════════ Cálculo (função pura) ════════ */
function calcular(entradas) {
  const e = mesclar(padrao(), entradas || {}), r = { entradas:e };
  const on = (e.controle && e.controle.ativo) || {};
  const st = (k, ok) => on[k] === false ? "não aplicável" : (ok ? "ativo" : "bloqueado");
  const status = {}; r.status = status;

  /* 1. Tipologias */
  const T = e.tipologias, tl = T.lista || [];
  const tip = { unidades:0, area:0, dorm:0, banh:0, vagas:0 };
  tl.forEach(t => { const q = N(t.q); tip.unidades += q; tip.area += q * N(t.area); tip.dorm += q * N(t.dorm); tip.banh += q * N(t.banh); tip.vagas += q * N(t.vagas); });
  tip.areaMedia = tip.unidades ? tip.area / tip.unidades : 0; tip.pop = tip.dorm * N(T.pessoasDorm); r.tip = tip;
  const unM = tl.map(t => String(t.n == null ? "" : t.n) === "" ? 0 : N(t.q));   // unidades de cada tipologia na matriz

  /* 2. Ar condicionado — padronização por tipo de ambiente */
  const A = e.ac, m2 = N(A.m2TR), btuTR = N(A.btuTR), cop = N(A.cop);
  const deg = (A.degraus || []).map(N).filter(x => x > 0).sort((a, b) => a - b);
  const ambIn = A.amb || [];
  /* carga térmica levada da subaba Carga térmica (physis-cargatermica.js, NBR 16401-1), em BTU/h de projeto por unidade
     (x.carga, gravada pelo botão "Levar para o dimensionamento do ar-condicionado"): quando existe, ela dimensiona o
     ar-condicionado; a regra de m²/TR fica só como triagem */
  const amb = ambIn.map((x, i) => { const area = N(x.area), nome = String(x.n == null ? "" : x.n), ct = N(x.carga) > 0 ? N(x.carga) : null, xb = ct != null ? ct : area / m2 * btuTR;
    let bc = 0; if (area !== 0 && isFinite(xb)) { const a1 = acima(deg, xb); bc = a1 != null ? a1 : (btuTR ? Math.ceil(xb / btuTR) * btuTR : 0); }
    const ov = x.override, btu = (ov === null || ov === undefined || ov === "") ? bc : N(ov), naM = !!x.matriz && nome !== "";
    let M = 0; if (naM) { const q = x.q || []; unM.forEach((u, t) => { M += N(q[t]) * u; }); M += N(x.comum); }
    return { i, nome, area, tr:ct != null ? (btuTR ? ct / btuTR : 0) : (m2 ? area / m2 : 0), btuCalc:bc, btu, cargaBtu:ct, fonte:ct != null ? "Carga térmica (NBR 16401-1)" : "triagem por m²/TR",
      equip:x.equip || "", matriz:naM, qtd:M, btuTotal:M * btu, dorm:N(x.dorm),
      comum:naM ? N(x.comum) : 0, foraMatriz:nome !== "" && !x.matriz }; });
  const dormChk = []; tl.forEach((t, ti) => { const nome = String(t.n == null ? "" : t.n); if (!nome) return;
    const mat = amb.reduce((s, a, ai) => s + (a.matriz ? a.dorm * N((ambIn[ai].q || [])[ti]) : 0), 0);
    dormChk.push({ tipologia:nome, cadastro:N(t.dorm), matriz:mat, situacao:N(t.dorm) === mat ? "confere" : "DIVERGE" }); });
  const porCap = deg.map(cap => ({ cap, tr:btuTR ? cap / btuTR : 0, qtd:amb.reduce((s, a) => s + (a.matriz && a.btu === cap ? a.qtd : 0), 0),
    tipos:amb.filter(a => a.matriz && a.btu === cap && a.qtd > 0).length }));
  const ac = { amb, dormChk, porCap, totalBTU:amb.reduce((s, a) => s + a.btuTotal, 0), equip:porCap.reduce((s, c) => s + c.qtd, 0),
    matrizTotal:amb.reduce((s, a) => s + a.qtd, 0), foraMatriz:amb.filter(a => a.foraMatriz).length };
  ac.TR = btuTR ? ac.totalBTU / btuTR : 0; ac.kWt = ac.TR * 3.517; ac.kWe = cop ? ac.kWt / cop : 0;
  ac.situacao = ac.equip === ac.matrizTotal ? "confere" : "DIVERGE — há capacidade fora da lista comercial"; r.ac = ac;
  status.ac = st("ac", tip.unidades > 0 && m2 > 0 && cop > 0);

  /* 3. Ventilação e exaustão */
  const V = e.vent, vent = {};
  vent.porBanh = V.metodo === "Trocas por hora" ? N(V.areaBanh) * N(V.peBanh) * N(V.trocasBanh) : N(V.vazBanh);
  vent.banheiros = tip.banh * vent.porBanh; vent.lixo = N(V.lixoArea) * N(V.lixoPe) * N(V.lixoTrocas);
  vent.vagas = N(V.garVagas) === 0 ? tip.vagas : N(V.garVagas);
  vent.garTrocas = N(V.garArea) * N(V.garPe) * N(V.garTrocas); vent.garArea = N(V.garArea) * N(V.garLsm2) * 3.6; vent.garVaga = vent.vagas * N(V.garVaga);
  vent.garagem = Math.max(vent.garTrocas, vent.garArea, vent.garVaga);
  vent.outrosLista = (V.outros || []).map(o => ({ n:o.n || "", vazao:N(o.area) * N(o.pe) * N(o.trocas) }));
  vent.outros = vent.outrosLista.reduce((s, o) => s + o.vazao, 0);
  vent.total = vent.banheiros + vent.lixo + vent.garagem + vent.outros; vent.totalLs = vent.total / 3.6; r.vent = vent;
  status.vent = st("vent", tip.unidades > 0);

  /* 4. Pressurização de escada (NBR 14880) */
  const P = e.press, press = {};
  press.areaPorta = N(P.w) * N(P.h); press.fechadas = Math.max(N(P.portas) - N(P.abertas), 0);
  press.areaVaz = press.fechadas * N(P.fresta) + N(P.outras); press.qVaz = 0.827 * press.areaVaz * Math.sqrt(N(P.dp));
  press.qAb = N(P.v) * press.areaPorta * N(P.abertas); press.q = (press.qVaz + press.qAb) * N(P.fator);
  press.qh = press.q * 3600; press.qls = press.q * 1000; press.qPorta = N(P.portas) === 0 ? 0 : press.qh / N(P.portas);
  press.fPress = N(P.w) <= 0.075 ? 0 : N(P.w) * press.areaPorta * N(P.dp) / (2 * (N(P.w) - 0.075));
  press.fTotal = N(P.fechador) + press.fPress;
  press.situacao = press.fTotal <= N(P.limite) ? "ok" : "acima de 110 N — reduzir ΔP ou prever alívio"; r.press = press;
  status.press = st("press", N(P.dp) > 0 && N(P.portas) > 0 && N(P.w) > 0 && N(P.h) > 0);

  /* 5. Aquecimento solar (NBR 15569, método simplificado), com a produção do coletor mês a mês */
  const SO = e.solar, solar = { pop:tip.pop };
  solar.consumo = solar.pop * N(SO.consumo); solar.dT = N(SO.tq) - N(SO.tf); solar.demanda = solar.consumo * 4.186 * solar.dT / 3600;
  solar.parcela = solar.demanda * N(SO.fracao);
  /* produção do coletor mês a mês: eficiência média da etiqueta Inmetro × irradiação do lugar no plano do coletor
     (base GIS do servidor, a mesma da aba Energia solar); a área sai do PIOR mês. Sem a irradiação ou sem a eficiência,
     vale a produção específica informada (sem número fixo: a produção de 1,8 kWh/m²·dia em qualquer lugar saiu em 15/11/2026). */
  const etaC = N(SO.eta) > 1 ? N(SO.eta) / 100 : N(SO.eta), Hs = Array.isArray(SO.H) && SO.H.length === 12 && SO.H.every(x => N(x) > 0) ? SO.H.map(N) : null;
  const PCv = typeof PhysisCalc !== "undefined" ? PhysisCalc : null;
  const Ht = Hs && PCv && N(SO.incl) > 0 && SO.lat != null && SO.lat !== "" ? PCv.fatorPlano(Hs, N(SO.lat), N(SO.incl), N(SO.azim)).Ht : Hs;
  if (Ht && etaC > 0) { solar.prodMes = Ht.map(h => h * etaC); solar.piorMes = solar.prodMes.indexOf(Math.min.apply(null, solar.prodMes));
    solar.prodUsada = solar.prodMes[solar.piorMes]; solar.modo = "mensal"; solar.eta = etaC; }
  else { solar.prodMes = null; solar.piorMes = null; solar.prodUsada = N(SO.prod); solar.modo = solar.prodUsada > 0 ? "informada" : "falta"; }
  solar.areaNec = solar.prodUsada ? solar.parcela / solar.prodUsada : 0;
  solar.coletores = N(SO.areaCol) ? Math.ceil(solar.areaNec / N(SO.areaCol)) : 0; solar.areaInst = solar.coletores * N(SO.areaCol);
  solar.volCol = solar.areaInst * N(SO.volM2); solar.volReq = Math.max(solar.consumo, solar.volCol);
  const resAsc = (SO.reserv || []).map(N).filter(x => x > 0).sort((a, b) => a - b), rc = acima(resAsc, solar.volReq);
  solar.reservatorio = rc != null ? rc : Math.ceil(solar.volReq / 1000) * 1000;
  solar.apoio = N(SO.horas) ? (solar.demanda - solar.parcela) / N(SO.horas) : 0; r.solar = solar;
  status.solar = st("solar", tip.pop > 0 && solar.prodUsada > 0 && N(SO.areaCol) > 0);

  /* 6. Aquecimento de piscina */
  const PI = e.piscina, pis = {}, tw = N(PI.tw), ta = N(PI.ta), v = N(PI.v), Ap = N(PI.area);
  pis.pvs = 0.61094 * Math.exp(17.625 * tw / (tw + 243.04)); pis.pva = 0.61094 * Math.exp(17.625 * ta / (ta + 243.04)) * N(PI.ur) / 100;
  pis.ws = 0.622 * pis.pvs / (101.325 - pis.pvs); pis.wa = 0.622 * pis.pva / (101.325 - pis.pva);
  pis.evap = Math.max((25 + 19 * v) * Ap * (pis.ws - pis.wa), 0); pis.qEvap = pis.evap * 2257 / 3600;
  pis.h = 5.7 + 3.8 * v; pis.qConv = pis.h * Ap * (tw - ta) / 1000; pis.tCeu = N(PI.descoberta) === 1 ? ta - 6 : ta;
  pis.qRad = 0.95 * 0.0000000567 * Ap * (Math.pow(tw + 273.15, 4) - Math.pow(pis.tCeu + 273.15, 4)) / 1000;
  pis.qParedes = (pis.qEvap + pis.qConv + pis.qRad) * N(PI.paredes) / 100; pis.subtotal = pis.qEvap + pis.qConv + pis.qRad + pis.qParedes;
  pis.capa = N(PI.capa) === 1 ? pis.subtotal * N(PI.hCapa) / 24 * N(PI.redCapa) : 0; pis.manut = pis.subtotal - pis.capa;
  pis.volume = Ap * N(PI.prof); pis.inicial = N(PI.tAq) ? pis.volume * 1000 * 4.186 * (tw - N(PI.ti)) / (N(PI.tAq) * 3600) : 0;
  pis.total = pis.manut + pis.inicial; pis.btu = pis.total * 3412; r.piscina = pis;
  status.piscina = st("piscina", Ap > 0);

  /* 7. Dutos, trecho crítico e ventiladores (Darcy-Weisbach + Swamee-Jain) */
  const D = e.dutos, Tk = N(D.temp) + 273.15, dut = {};
  dut.patm = 101.325 * Math.pow(1 - 0.0000225577 * N(D.alt), 5.25588); dut.rho = dut.patm * 1000 / (287.05 * Tk);
  dut.nu = 0.000001458 * Math.pow(Tk, 1.5) / (Tk + 110.4) / dut.rho;
  const rug = N(D.rug), rendC = N(D.rend), fonte = { banheiros:status.vent === "ativo" ? vent.banheiros : 0, lixo:status.vent === "ativo" ? vent.lixo : 0,
    garagem:status.vent === "ativo" ? vent.garagem : 0, press:status.press === "ativo" ? press.qh : 0 };
  dut.sis = (D.sistemas || []).map((s, i) => { const B = s.fonte ? N(fonte[s.fonte]) : N(s.vazao), C = N(s.vel), o = { i, nome:s.nome || "", fonte:s.fonte || "", vazao:B, vel:C };
    o.area = (B === 0 || C === 0) ? 0 : B / 3600 / C; o.diam = o.area === 0 ? 0 : Math.sqrt(4 * o.area / Math.PI) * 1000;
    o.reynolds = o.diam === 0 ? 0 : C * o.diam / 1000 / dut.nu;
    o.atrito = o.reynolds === 0 ? 0 : 0.25 / Math.pow(Math.log10(rug / (3.7 * o.diam / 1000) + 5.74 / Math.pow(o.reynolds, 0.9)), 2);
    o.perdaUnit = o.diam === 0 ? 0 : o.atrito / (o.diam / 1000) * dut.rho * C * C / 2; o.perdaTrecho = o.perdaUnit * (N(s.reto) + N(s.equiv));
    o.pressao = (o.perdaTrecho + N(s.local)) * N(D.fs); o.potAbs = (B === 0 || !rendC) ? 0 : B / 3600 * o.pressao / rendC / 1000;
    const H = N(s.altura); o.largura = null; o.deRet = o.aspecto = o.velRet = o.potEixo = o.potMargem = o.potEletrica = o.motorKw = o.motorCv = null;
    if (B !== 0 && H !== 0) { let c = 0; LARG.forEach(w => { if (deRet(H, w) < o.diam) c++; }); o.largura = c < LARG.length ? LARG[c] : "acima da tabela"; }
    if (typeof o.largura === "number") { o.deRet = deRet(H, o.largura); o.aspecto = Math.max(H, o.largura) / Math.min(H, o.largura); o.velRet = B / 3600 / (H * o.largura / 1e6); }
    /* Revisão de 15/11/2026 (docs/REVISAO_AVAC.md, item 1): o rendimento entre o ventilador e a rede só aumenta a potência
       pedida. Eixo do motor = absorvida ÷ rendimento da transmissão (correia 0,95; acoplamento direto 1); elétrica = eixo ÷
       rendimento do motor. Antes multiplicava pelo rendimento do motor e escolhia motor menor. */
    if (B !== 0) { const rT = (D.rendTransm == null || D.rendTransm === "") ? 0.95 : (N(D.rendTransm) || 1);
      o.potEixo = o.potAbs / rT; o.potEletrica = o.potEixo / (N(D.rendMotor) || 1); o.potMargem = o.potEixo * (1 + (o.potEixo <= 1.5 ? N(D.margem1) : N(D.margem2)));
      const m = acima(MOTOR_KW, o.potMargem); o.motorKw = m != null ? m : "acima da tabela"; if (m != null) o.motorCv = MOTOR_CV[MOTOR_KW.indexOf(m)]; }
    o.situacao = B === 0 ? "" : H === 0 ? "informe a altura" : o.largura === "acima da tabela" ? "dividir em mais dutos ou prumadas"
      : o.aspecto > 4 ? "relação > 4:1 — rever altura" : o.motorKw === "acima da tabela" ? "motor acima da tabela" : "ok";
    const tp = TIPOS_DUTO.find(t => t[0] === s.tipo); o.tipo = s.tipo || ""; o.limite = tp ? tp[1] : 0;
    o.situacaoVel = (o.nome === "" || C === 0) ? "" : o.limite === 0 ? "defina o tipo" : C <= o.limite ? "ok" : "acima do limite";
    return o; });
  dut.potAbs = dut.sis.reduce((s, o) => s + o.potAbs, 0); dut.potEixo = dut.sis.reduce((s, o) => s + N(o.potEixo), 0); dut.potEletrica = dut.sis.reduce((s, o) => s + N(o.potEletrica), 0);
  dut.motores = dut.sis.reduce((s, o) => s + N(o.motorKw), 0); dut.ventiladores = dut.sis.filter(o => o.vazao > 0).length; r.dutos = dut;
  status.dutos = st("dutos", status.vent === "ativo" || status.press === "ativo");
  const algum = ["ac", "vent", "press", "solar", "piscina", "dutos"].some(k => status[k] === "ativo");
  status.lista = st("lista", algum); status.quadro = st("quadro", algum);

  /* 8. Quadro elétrico QF-AVAC (NBR 5410 simplificada) */
  const Q = e.quadro, vff = N(Q.vff), U0 = N(Q.vfn), rho = N(Q.rho70), L = N(Q.compAlim), kc = N(Q.k);
  const fct = FCT_V[Math.min(FCT_T.filter(t => t < N(Q.tamb)).length, 10)], fcaC = N(Q.fcaC), fcaA = N(Q.fcaA), dvTerm = N(Q.dvTot) - N(Q.dvAlim);
  const fh = Q.harm === "sim" ? N(Q.f4) : 1, ov = Q.circ || {};
  const cq = [];
  dut.sis.forEach((s, i) => cq.push({ id:"v" + i, nome:s.nome ? "Ventilador — " + s.nome : "", kwUnit:N(s.motorKw), qtd:1,
    pad:{ fases:"RST", fp:0.85, rend:N(D.rendMotor), fd:1, fs:1.15, ipin:7, curva:"D", dr:"não", comp:30, iplaca:null } }));
  let kac = 0; amb.forEach(a => { if (!a.matriz || a.comum <= 0) return;
    cq.push({ id:"ac" + encodeURIComponent(a.nome).replace(/\./g, "%2E"), nome:"Ar condicionado — " + a.nome, kwUnit:status.ac !== "ativo" ? 0 : (cop ? a.btu / 3412 / cop : 0), qtd:a.comum, ehAC:true,
      pad:{ fases:FASES_AC[kac++ % FASES_AC.length], fp:0.95, rend:1, fd:1, fs:1, ipin:0, curva:"C", dr:"não", comp:35, iplaca:null } }); });
  cq.push({ id:"solar", nome:"Apoio elétrico do aquecimento solar", kwUnit:status.solar !== "ativo" ? 0 : solar.apoio, qtd:1,
    pad:{ fases:"RST", fp:1, rend:1, fd:1, fs:1, ipin:0, curva:"C", dr:"não", comp:40, iplaca:null } });
  cq.push({ id:"piscina", nome:"Aquecedor de piscina", kwUnit:status.piscina !== "ativo" ? 0 : (N(Q.copPisc) <= 1 ? pis.total : pis.total / N(Q.copPisc)), qtd:1,
    pad:{ fases:"RST", fp:0.9, rend:1, fd:1, fs:1, ipin:0, curva:"C", dr:"não", comp:40, iplaca:null } });
  (Q.extras || []).forEach((x, i) => cq.push({ id:"x" + i, extra:i, nome:x.nome || "", kwUnit:N(x.kw), qtd:x.qtd == null ? 1 : N(x.qtd),
    pad:{ fases:"RST", fp:0.92, rend:1, fd:1, fs:1, ipin:0, curva:"C", dr:"não", comp:30, iplaca:null } }));
  const circ = cq.map(c => { const p = Object.assign({}, c.pad, c.extra != null ? pick((Q.extras || [])[c.extra]) : (ov[c.id] || {}));
    const fases = String(p.fases || ""), o = { id:c.id, nome:c.nome, ehAC:!!c.ehAC, extra:c.extra, kwUnit:c.kwUnit, qtd:c.qtd, p };
    o.kw = N(c.kwUnit) * N(c.qtd); o.kva = o.kw === 0 ? 0 : o.kw / ((N(p.fp) || 1) * (N(p.rend) || 1));
    o.tensao = fases === "" ? null : fases.length === 1 ? U0 : vff;
    o.icalc = (o.kva === 0 || fases === "") ? 0 : fases.length === 3 ? o.kva * 1000 / (S3 * vff) : o.kva * 1000 / o.tensao;
    o.base = N(p.iplaca) > 0 ? N(p.iplaca) : o.icalc; o.ib = o.base * (N(p.fs) || 1);
    o.iR = /R/i.test(fases) ? o.ib * N(p.fd) : 0; o.iS = /S/i.test(fases) ? o.ib * N(p.fd) : 0; o.iT = /T/i.test(fases) ? o.ib * N(p.fd) : 0;
    return o; });
  const al = {}; al.ativos = circ.filter(c => c.kw > 0).length;
  al.reserva = al.ativos === 0 ? 0 : al.ativos <= 6 ? 2 : al.ativos <= 12 ? 3 : al.ativos <= 30 ? 4 : Math.ceil(0.15 * al.ativos);
  al.kw = circ.reduce((s, c) => s + c.kw, 0); al.kva = circ.reduce((s, c) => s + c.kva, 0); al.dem = circ.reduce((s, c) => s + c.kva * N(c.p.fd), 0);
  al.iR = circ.reduce((s, c) => s + c.iR, 0); al.iS = circ.reduce((s, c) => s + c.iS, 0); al.iT = circ.reduce((s, c) => s + c.iT, 0);
  al.ib = Math.max(al.iR, al.iS, al.iT); al.deseq = al.ib === 0 ? 0 : (al.ib - Math.min(al.iR, al.iS, al.iT)) / al.ib;
  al.in = al.ib === 0 ? 0 : (acima(DISJ, al.ib) || 0);
  al.sCap = al.ib === 0 ? 0 : secPor(IZ3, al.in / (fct * fcaA * fh));
  al.sQueda = al.ib === 0 ? 0 : secAcima(S3 * rho * L * al.ib / (N(Q.dvAlim) * vff));
  al.sCurto = al.ib === 0 ? 0 : secAcima(Math.max(N(Q.icc) * 1000 * Math.sqrt(N(Q.tAlim)) / kc, 3 * rho * L * N(Q.magAlim) * al.in / (0.8 * U0)));
  al.s = al.ib === 0 ? 0 : secAcima(Math.max(al.sCap, al.sQueda, al.sCurto, N(Q.smin)));
  al.sN = al.s === 0 ? 0 : (Q.harm === "sim" || al.s <= 25) ? al.s : (NEU_F.indexOf(al.s) >= 0 ? NEU_N[NEU_F.indexOf(al.s)] : al.s);
  al.sPE = al.s === 0 ? 0 : al.s <= 16 ? al.s : al.s <= 35 ? 16 : secAcima(al.s / 2);
  al.iz = al.s === 0 ? 0 : izDe(al.s, true) * fct * fcaA * fh; al.dv = al.s === 0 ? 0 : S3 * rho * L * al.ib / (al.s * vff);
  al.icc = N(Q.icc);
  al.iccQF = al.s === 0 ? al.icc : U0 / Math.sqrt(Math.pow(N(Q.rho20) * L / al.s, 2) + Math.pow(U0 / (al.icc * 1000) + N(Q.x) / 1000 * L, 2)) / 1000;
  al.lmax = (al.s === 0 || !al.in) ? 0 : 0.8 * U0 * al.s / (rho * (1 + al.s / al.sPE) * N(Q.magAlim) * al.in);
  al.fct = fct;
  circ.forEach(o => { const p = o.p, fases = String(p.fases || ""), tres = fases.length === 3, kq = tres ? S3 : 2, F = o.tensao, S = N(p.comp), K = N(p.ipin);
    o.in = o.sCap = o.sQueda = o.sProt = o.s = o.sPE = o.iz = o.dv = o.dvPartida = o.lmax = null;
    if (o.ib !== 0 && F) {
      o.in = acima(DISJ, o.ib) || 0; const ia = iaCurva(o.in, p.curva, N(Q.magCM));
      o.sCap = secPor(tres ? IZ3 : IZ2, o.in / (fct * fcaC)); o.sQueda = secAcima(kq * rho * S * o.ib / (dvTerm * F));
      const a1 = Math.sqrt(o.in <= 63 ? N(Q.i2t) : Math.pow(al.iccQF * 1000, 2) * N(Q.tCM)) / kc, a2 = p.dr === "sim" ? 0 : 2 * rho * S * o.in * ia / (0.8 * U0);
      const a3 = K === 0 ? 0 : kq * rho * S * K * o.base / (F * Math.max(N(Q.dvPart) - (al.ib === 0 ? 0 : al.dv * (al.ib - o.ib + K * o.base) / al.ib), 0.001));
      o.sProt = secAcima(Math.max(a1, a2, a3)); o.s = secAcima(Math.max(o.sCap, o.sQueda, o.sProt, N(Q.smin)));
      if (o.s) { o.sPE = o.s <= 16 ? o.s : o.s <= 35 ? 16 : secAcima(o.s / 2); o.iz = izDe(o.s, tres) * fct * fcaC; o.dv = kq * rho * S * o.ib / (o.s * F);
        if (K) o.dvPartida = kq * rho * S * K * o.base / (o.s * F) + (al.ib === 0 ? 0 : al.dv * (al.ib - o.ib + K * o.base) / al.ib);
        o.lmax = o.in ? 0.8 * U0 * o.s / (rho * (1 + o.s / o.sPE) * o.in * ia) : null; }
    } else if (o.ib !== 0) { o.in = acima(DISJ, o.ib) || 0; o.s = 0; }
    o.situacao = o.kw === 0 ? "" : fases === "" ? "defina as fases" : S === 0 ? "informe o comprimento" : (!o.in || !o.s) ? "acima da tabela — dividir circuito"
      : al.iccQF > (o.in <= 63 ? N(Q.icnMod) : N(Q.icuCM)) ? "Icc acima da capacidade de interrupção" : N(o.dv) > dvTerm ? "queda de tensão"
      : N(o.iz) < o.in ? "Iz < In" : (p.dr !== "sim" && S > N(o.lmax)) ? "seccionamento — usar DR ou aumentar seção"
      : (K > 0 && N(o.dvPartida) > N(Q.dvPart)) ? "queda na partida acima do limite" : "ok"; });
  al.dvTot = al.dv + maxN(circ.map(c => c.dv));
  al.situacao = al.ib === 0 ? "sem carga" : (al.in === 0 || al.s === 0) ? "acima da tabela — barramento ou condutores em paralelo"
    : al.icc > N(Q.icuAlim) ? "Icc na origem acima da capacidade do disjuntor do alimentador" : L > al.lmax ? "alimentador longo para o seccionamento — aumentar seção ou usar DR"
    : al.deseq > N(Q.deseq) ? "rebalancear fases" : al.dvTot > N(Q.dvTot) ? "queda total acima do admitido"
    : circ.filter(c => c.situacao === "ok").length < al.ativos ? "há circuitos a verificar" : "ok";
  /* circuito típico de split por capacidade (unidades autônomas) */
  const spl = deg.map(cap => { const p = Object.assign({ fases:"R", fp:0.95, iplaca:null, comp:15, curva:"C", dr:"não" }, (Q.splits || {})[cap] || {});
    const fases = String(p.fases || ""), tres = fases.length === 3, kq = tres ? S3 : 2, J = N(p.comp), o = { cap, p };
    o.qtd = status.ac !== "ativo" ? 0 : amb.reduce((s, a) => s + (a.matriz && a.btu === cap ? a.qtd - a.comum : 0), 0);
    o.kw = cop ? cap / 3412 / cop : 0; o.tensao = fases === "" ? null : fases.length === 1 ? U0 : vff;
    o.icalc = (o.kw === 0 || fases === "") ? 0 : o.kw / (N(p.fp) || 1) * 1000 / (tres ? S3 * vff : o.tensao); o.ib = N(p.iplaca) > 0 ? N(p.iplaca) : o.icalc;
    o.in = o.s = o.sPE = o.iz = o.dv = o.lmax = null;
    if (o.ib !== 0 && o.tensao) { o.in = acima(DISJ, o.ib) || 0; const ia = iaCurva(0, p.curva, 0), cIz = (tres ? IZ3 : IZ2).filter(z => z < o.in / (fct * fcaC)).length;
      o.s = cIz >= SEC.length ? 0 : secAcima(Math.max(N(Q.smin), SEC[cIz], kq * rho * J * o.ib / (dvTerm * o.tensao), p.dr === "sim" ? 0 : 2 * rho * J * o.in * ia / (0.8 * U0)));
      if (o.s) { o.sPE = o.s <= 16 ? o.s : o.s <= 35 ? 16 : secAcima(o.s / 2); o.iz = izDe(o.s, tres) * fct * fcaC; o.dv = kq * rho * J * o.ib / (o.s * o.tensao);
        o.lmax = o.in ? 0.8 * U0 * o.s / (rho * (1 + o.s / o.sPE) * o.in * ia) : null; } }
    o.situacao = (o.qtd === 0 || o.ib === 0) ? "" : (!o.in || !o.s) ? "acima da tabela" : N(o.dv) > dvTerm ? "queda de tensão" : N(o.iz) < o.in ? "Iz < In"
      : (p.dr !== "sim" && J > N(o.lmax)) ? "seccionamento — usar DR" : "ok";
    return o; });
  const quadro = { circ, alim:al, splits:spl, splitsQtd:spl.reduce((s, o) => s + o.qtd, 0), splitsKw:spl.reduce((s, o) => s + o.qtd * o.kw, 0), dvTerm };
  quadro.conf = status.ac !== "ativo" ? status.ac : (Math.abs(quadro.splitsKw + circ.filter(c => c.ehAC).reduce((s, c) => s + c.kw, 0) - ac.kWe) < 0.5 ? "confere" : "DIVERGE");
  r.quadro = quadro;

  /* 0. Verificações automáticas de consistência (aba Controle) */
  const C0 = e.controle;
  r.checks = [
    ["Lista de AC × ambientes da matriz", ac.situacao, "Ar-condicionado, lista por capacidade"],
    ["Dormitórios do cadastro × matriz", dormChk.some(d => d.situacao === "DIVERGE") ? "DIVERGE" : "confere", "Tipologias e ambientes"],
    ["Tipos de ambiente fora da matriz", ac.foraMatriz > 0 ? ac.foraMatriz + " tipo(s) sem quantidade" : "confere", "Tipologias e ambientes, coluna Na matriz"],
    ["Velocidade nos dutos", dut.sis.some(o => o.situacaoVel === "acima do limite") ? "acima do limite" : "ok", "Dutos e ventiladores"],
    ["Força na porta da escada", status.press !== "ativo" ? status.press : press.situacao, "Pressurização"],
    ["Quadro elétrico — alimentador", status.quadro !== "ativo" ? status.quadro : al.situacao, "Quadro elétrico (aba Caixinha Physis IoT)"],
    ["Splits × carga elétrica do ar-condicionado", quadro.conf, "Quadro elétrico (aba Caixinha Physis IoT)"],
    ["Coordenadas da obra", (C0.lat == null || C0.lat === "" || C0.lon == null || C0.lon === "") ? "sem coordenada — distâncias não calculadas" : "ok", "Visão geral"]
  ].map(x => ({ verificacao:x[0], resultado:x[1], onde:x[2] }));

  /* 9. Resumo */
  const g = (k, v) => status[k] !== "ativo" ? status[k] : v;
  r.resumo = [
    ["Edifício", "Unidades", tip.unidades, "cadastro de tipologias"], ["Edifício", "População estimada (pessoas)", tip.pop, "pessoas por dormitório adotadas"],
    ["Edifício", "Área privativa total (m²)", tip.area, ""],
    ["Ar condicionado", "Capacidade total (TR)", g("ac", ac.TR), "estimativa por área específica"], ["Ar condicionado", "Capacidade total (BTU/h)", g("ac", ac.totalBTU), ""],
    ["Ar condicionado", "Equipamentos (un.)", g("ac", ac.equip), "padronizados por tipo de ambiente"], ["Ar condicionado", "Carga elétrica estimada (kW)", g("ac", ac.kWe), "COP de referência"],
    ["Ventilação", "Banheiros (m³/h)", g("vent", vent.banheiros), "vazão por peça"], ["Ventilação", "Depósito de lixo (m³/h)", g("vent", vent.lixo), "trocas por hora"],
    ["Ventilação", "Garagem (m³/h)", g("vent", vent.garagem), "maior dos três critérios"], ["Ventilação", "Total do edifício (m³/h)", g("vent", vent.total), ""],
    ["Ventilação", "Ventiladores / potência total (kW)", g("dutos", dut.potAbs), "trecho crítico por sistema"],
    ["Pressurização", "Vazão de projeto (m³/h)", g("press", press.qh), "NBR 14880"], ["Pressurização", "Força na porta (N)", g("press", press.fTotal), "limite 110 N"],
    ["Pressurização", "Situação", g("press", press.situacao), ""],
    ["Aquecimento solar", "Coletores", g("solar", solar.coletores), "fração solar adotada"], ["Aquecimento solar", "Área coletora (m²)", g("solar", solar.areaInst), ""],
    ["Aquecimento solar", "Reservatório (L)", g("solar", solar.reservatorio), ""], ["Aquecimento solar", "Potência do apoio (kW)", g("solar", solar.apoio), ""],
    ["Piscina", "Manutenção (kW)", g("piscina", pis.manut), ""], ["Piscina", "Potência de seleção (kW)", g("piscina", pis.total), "manutenção + recuperação"]
  ].map(x => ({ sistema:x[0], grandeza:x[1], valor:x[2], base:x[3] }));

  /* 10. Lista de equipamentos (categorias genéricas no lugar de fabricantes) */
  const lista = [], okL = status.lista === "ativo";
  if (okL && status.ac === "ativo") porCap.forEach(c => { if (c.qtd > 0) lista.push({ sistema:"Ar condicionado", descricao:"Unidade de " + fx(c.cap, 0) + " BTU/h — tipo a definir",
    qtd:c.qtd, cap:c.cap, un:"BTU/h", categoria:"Split / condicionador (fabricante a definir)" }); });
  if (okL && status.dutos === "ativo") dut.sis.forEach(o => { if (o.vazao > 0) lista.push({ sistema:"Ventilação",
    descricao:"Ventilador — " + o.nome + "  (" + fx(o.pressao, 0) + " Pa · motor " + fx(N(o.motorKw), 2) + " kW / " + fx(N(o.motorCv), 2) + " cv)", qtd:1, cap:o.vazao, un:"m³/h",
    categoria:o.vazao > 5000 ? "Ventilador industrial" : "Exaustor residencial" }); });
  if (okL && status.solar === "ativo") { lista.push({ sistema:"Aquecimento solar", descricao:"Coletor solar — " + fx(solar.areaInst, 1) + " m² de área total", qtd:solar.coletores, cap:N(SO.areaCol), un:"m²/coletor", categoria:"Coletor solar" });
    lista.push({ sistema:"Aquecimento solar", descricao:"Reservatório térmico", qtd:1, cap:solar.reservatorio, un:"L", categoria:"Reservatório térmico" });
    lista.push({ sistema:"Aquecimento solar", descricao:"Sistema de apoio ao aquecimento", qtd:1, cap:solar.apoio, un:"kW", categoria:"Apoio (elétrico, gás ou bomba de calor)" }); }
  if (okL && status.piscina === "ativo") lista.push({ sistema:"Piscina", descricao:"Aquecedor de piscina — manutenção " + fx(pis.manut, 1) + " kW", qtd:1, cap:pis.total, un:"kW", categoria:"Bomba de calor / aquecedor de piscina" });
  lista.forEach((x, i) => { x.item = i + 1; }); r.lista = lista;

  /* 11. Memória de cálculo (texto gerado como na planilha) */
  const mem = [], sec = (t, k, linhas) => mem.push({ titulo:t, situacao:status[k], linhas:status[k] === "ativo" ? linhas.filter(Boolean) : [] });
  sec("1. Ar condicionado — estimativa por área específica", "ac", ["Critério adotado: 1 TR para cada " + fx(m2, 1) + " m²   ·   1 TR = " + fx(btuTR, 0) + " BTU/h = 3,517 kW"]
    .concat(amb.filter(a => a.matriz).map(a => a.nome + " — " + fx(a.area, 1) + " m² / " + fx(m2, 1) + " = " + fx(a.tr, 2) + " TR = " + fx(a.btuCalc, 0) + " BTU/h  →  padronizado " + fx(a.btu, 0) + " BTU/h  ×  " + fx(a.qtd, 0) + " un.  =  " + fx(a.btuTotal, 0) + " BTU/h"))
    .concat(["Total: " + fx(ac.totalBTU, 0) + " BTU/h = " + fx(ac.TR, 1) + " TR = " + fx(ac.kWt, 1) + " kW térmicos   ·   carga elétrica " + fx(ac.kWe, 1) + " kW (COP " + fx(cop, 2) + ")",
      "Equipamentos padronizados: " + fx(ac.equip, 0) + " unidades"]));
  sec("2. Ventilação e exaustão", "vent", ["Banheiros: " + fx(tip.banh, 0) + " peças × " + fx(vent.porBanh, 0) + " m³/h = " + fx(vent.banheiros, 0) + " m³/h",
    "Depósito de lixo: " + fx(V.lixoArea, 1) + " m² × " + fx(V.lixoPe, 2) + " m × " + fx(V.lixoTrocas, 0) + " tr/h = " + fx(vent.lixo, 0) + " m³/h",
    "Garagem — a) trocas/hora: " + fx(vent.garTrocas, 0) + "   b) por área: " + fx(vent.garArea, 0) + "   c) por vaga: " + fx(vent.garVaga, 0) + "   →  adotado " + fx(vent.garagem, 0) + " m³/h",
    "Outros ambientes: " + fx(vent.outros, 0) + " m³/h", "Total do edifício: " + fx(vent.total, 0) + " m³/h = " + fx(vent.totalLs, 0) + " L/s"]);
  sec("3. Pressurização de escada — NBR 14880", "press", ["Área da porta: A = " + fx(P.w, 2) + " × " + fx(P.h, 2) + " = " + fx(press.areaPorta, 2) + " m²",
    "Frestas: " + fx(press.fechadas, 0) + " portas fechadas × " + fx(P.fresta, 3, true) + " m² + " + fx(P.outras, 3, true) + " m² = " + fx(press.areaVaz, 3, true) + " m²",
    "Vazamento: Q = 0,827 · A · ΔP^0,5 = 0,827 × " + fx(press.areaVaz, 3, true) + " × " + fx(P.dp, 0) + "^0,5 = " + fx(press.qVaz, 3, true) + " m³/s",
    "Portas abertas: Q = v · A · n = " + fx(P.v, 2) + " × " + fx(press.areaPorta, 2) + " × " + fx(P.abertas, 0) + " = " + fx(press.qAb, 3, true) + " m³/s",
    "Vazão de projeto: (" + fx(press.qVaz, 3, true) + " + " + fx(press.qAb, 3, true) + ") × " + fx(P.fator, 2) + " = " + fx(press.q, 3, true) + " m³/s = " + fx(press.qh, 0) + " m³/h",
    "Força na porta: F = " + fx(P.fechador, 0) + " + (W·A·ΔP)/(2·(W−0,075)) = " + fx(press.fTotal, 0) + " N   →  limite 110 N: " + press.situacao]);
  sec("4. Aquecimento solar — NBR 15569 (método simplificado)", "solar", ["População: " + fx(tip.dorm, 0) + " dormitórios × " + fx(T.pessoasDorm, 1) + " = " + fx(solar.pop, 0) + " pessoas",
    "Consumo: " + fx(solar.pop, 0) + " × " + fx(SO.consumo, 0) + " L/dia = " + fx(solar.consumo, 0) + " L/dia a " + fx(SO.tq, 0) + " °C",
    "Demanda: E = V · c · ΔT / 3600 = " + fx(solar.consumo, 0) + " × 4,186 × " + fx(solar.dT, 0) + " / 3600 = " + fx(solar.demanda, 1) + " kWh/dia",
    "Parcela solar: " + fx(solar.demanda, 1) + " × " + fx(N(SO.fracao) * 100, 0) + "% = " + fx(solar.parcela, 1) + " kWh/dia",
    "Área coletora: Ac = " + fx(solar.parcela, 1) + " / " + fx(solar.prodUsada, 2) + " kWh/m²·dia" + (solar.modo === "mensal" ? " (pior mês: " + MESES_AQ[solar.piorMes] + ", eficiência " + fx(solar.eta * 100, 0) + "% × sol do lugar)" : " (produção informada)") + " = " + fx(solar.areaNec, 1) + " m²  →  " + fx(solar.coletores, 0) + " coletores (" + fx(solar.areaInst, 1) + " m²)",
    "Reservatório: maior entre consumo diário e mínimo por m² = " + fx(solar.volReq, 0) + " L  →  comercial " + fx(solar.reservatorio, 0) + " L",
    "Apoio: (" + fx(solar.demanda, 1) + " − " + fx(solar.parcela, 1) + ") / " + fx(SO.horas, 0) + " h = " + fx(solar.apoio, 1) + " kW"]);
  sec("5. Aquecimento de piscina", "piscina", ["Espelho " + fx(Ap, 0) + " m² · volume " + fx(pis.volume, 0) + " m³ · água " + fx(tw, 1) + " °C · ar " + fx(ta, 1) + " °C · UR " + fx(PI.ur, 0) + "% · vento " + fx(v, 2) + " m/s",
    "Pressões de vapor: água " + fx(pis.pvs, 3) + " kPa · ar " + fx(pis.pva, 3) + " kPa   →  w_s = " + fx(pis.ws * 1000, 2) + " g/kg · w_a = " + fx(pis.wa * 1000, 2) + " g/kg",
    "Evaporação: m = (25 + 19·v) · A · (w_s − w_a) = " + fx(pis.evap, 1) + " kg/h  →  q = m · 2257 / 3600 = " + fx(pis.qEvap, 1) + " kW",
    "Convecção: h = 5,7 + 3,8·v = " + fx(pis.h, 2) + " W/m²K  →  q = " + fx(pis.qConv, 1) + " kW",
    "Radiação (T céu " + fx(pis.tCeu, 1) + " °C): " + fx(pis.qRad, 1) + " kW   ·   paredes e fundo: " + fx(pis.qParedes, 1) + " kW",
    "Subtotal " + fx(pis.subtotal, 1) + " kW − capa térmica " + fx(pis.capa, 1) + " kW  =  manutenção " + fx(pis.manut, 1) + " kW",
    "Aquecimento inicial em " + fx(PI.tAq, 0) + " h: " + fx(pis.inicial, 1) + " kW   →   potência de seleção " + fx(pis.total, 1) + " kW"]);
  sec("6. Dutos, trecho crítico e ventiladores", "dutos", ["Ar a " + fx(dut.rho, 3) + " kg/m³ · rugosidade " + fx(rug, 5, true) + " m · fator de segurança " + fx(D.fs, 2) + " · rendimento " + fx(rendC, 2) + " · altitude " + fx(D.alt, 0) + " m, ar a " + fx(D.temp, 1) + " °C"]
    .concat(dut.sis.filter(o => o.vazao !== 0).map(o => o.nome + ": " + fx(o.vazao, 0) + " m³/h a " + fx(o.vel, 1) + " m/s → D = " + fx(o.diam, 0) + " mm · " + fx(o.perdaUnit, 2) + " Pa/m × "
      + fx(N(D.sistemas[o.i].reto) + N(D.sistemas[o.i].equiv), 1) + " m + " + fx(D.sistemas[o.i].local, 0) + " Pa localizadas × " + fx(D.fs, 2) + " = " + fx(o.pressao, 0) + " Pa · " + fx(o.potAbs, 2) + " kW absorvidos · motor " + fx(N(o.motorKw), 2) + " kW"))
    .concat(["Potência total de ventilação: " + fx(dut.potAbs, 2) + " kW em " + fx(dut.ventiladores, 0) + " ventiladores · motores instalados " + fx(dut.motores, 2) + " kW"]));
  sec("7. Quadro elétrico QF-AVAC — NBR 5410 (simplificado)", "quadro", circ.filter(c => c.kw > 0).map(c => c.nome + ": " + fx(c.kw, 2) + " kW · Ib " + fx(c.ib, 1) + " A · disjuntor " + fx(N(c.in), 0) + " A curva " + (c.p.curva || "") + " · fase " + fx(N(c.s), 1) + " mm² · PE " + fx(N(c.sPE), 1) + " mm² · queda " + fx(N(c.dv) * 100, 2) + "% · " + c.situacao)
    .concat(["Alimentador: Ib " + fx(al.ib, 1) + " A (fase mais carregada) · disjuntor " + fx(al.in, 0) + " A · fase " + fx(al.s, 0) + " mm² · neutro " + fx(al.sN, 0) + " mm² · PE " + fx(al.sPE, 0) + " mm² · queda " + fx(al.dv * 100, 2) + "% (total " + fx(al.dvTot * 100, 2) + "%) · Icc no quadro " + fx(al.iccQF, 2) + " kA · " + al.situacao]));
  r.memoria = mem;
  return r;
}
const pick = x => { const o = {}; ["fases", "fp", "rend", "fd", "fs", "ipin", "curva", "dr", "comp", "iplaca"].forEach(k => { if (x && x[k] !== undefined) o[k] = x[k]; }); return o; };

/* ════════ Estado salvo (calcLer/calcGravar "avac") e migração da tela antiga ════════ */
function migrar(o) { const e = padrao(), velhos = (o && Array.isArray(o.amb)) ? o.amb.filter(a => a && String(a.n || "").trim()) : [];
  if (!velhos.length) return e;
  const num = v => typeof v === "number" ? v : (typeof numBr === "function" ? numBr(v) : Number(String(v).replace(/\./g, "").replace(",", "."))) || 0;
  e.tipologias.lista = [{ n:"Unidade (migrada da tela anterior)", q:1, area:velhos.reduce((s, a) => s + num(a.area), 0), dorm:0, banh:0, vagas:0 }];
  e.ac.amb = velhos.map(a => ({ n:String(a.n).trim(), area:num(a.area), dorm:0, override:null, equip:"Split hi-wall", matriz:true, q:[1], comum:0 }));
  e.migrado = true; return e; }
function ler() { const o = calcLer("avac") || {}; return o.e && typeof o.e === "object" ? o.e : migrar(o); }
function gravar(e) { const o = calcLer("avac") || {}; o.e = e; calcGravar("avac", o); }
function setPath(obj, path, v) { const ps = String(path).split("."); let c = obj;
  for (let i = 0; i < ps.length - 1; i++) { const k = ps[i]; if (c[k] == null || typeof c[k] !== "object") c[k] = /^\d+$/.test(ps[i + 1]) ? [] : {}; c = c[k]; }
  c[ps[ps.length - 1]] = v; }

/* ════════ Desenho (usa os globais da plataforma) ════════ */
const SUBS = [["visao", "Visão geral e controle"], ["tip", "Tipologias e ambientes"], ["carga", "Carga térmica"], ["ac", "Ar-condicionado"], ["vent", "Ventilação"], ["press", "Pressurização"],
  ["solar", "Aquecimento solar"], ["piscina", "Piscina"], ["dutos", "Dutos e ventiladores"], ["resumo", "Resumo e lista de equipamentos"], ["memoria", "Memória de cálculo"]];
const f = (v, c) => (v == null || v === "" || (typeof v === "number" && !isFinite(v))) ? "—" : typeof v === "number" ? n2(v, c == null ? 2 : c) : esc(v);
const fmtIn = v => v == null || v === "" ? "" : typeof v === "number" ? String(+v.toPrecision(12)).replace(".", ",") : String(v);
const idDe = p => "avac-" + String(p).replace(/[^A-Za-z0-9_-]/g, "_");
function ctl(p, v, t, opt) { opt = opt || {}; const id = idDe(p), k = `id="${id}" data-avac-k="${esc(p)}"`;
  if (t === "b") return `<input type="checkbox" ${k} data-avac-t="b" ${v ? "checked" : ""}>`;
  if (t === "sel") return `<select ${k} data-avac-t="${opt.tipo || "s"}">${opt.ops.map(o => { const a = Array.isArray(o) ? o : [o, o];
    return `<option value="${esc(a[0])}" ${String(a[0]) === String(v == null ? "" : v) ? "selected" : ""}>${esc(a[1])}</option>`; }).join("")}</select>`;
  const val = t === "l" ? (v || []).map(fmtIn).join("; ") : fmtIn(v);
  return `<input type="text" ${k} data-avac-t="${t}" ${t === "s" ? "" : 'inputmode="decimal"'} value="${esc(val)}" style="width:${opt.w || "100%"}">`; }
const campo = (p, v, rot, t, aj, opt) => `<div><label for="${idDe(p)}">${esc(rot)}</label>${ctl(p, v, t || "n", opt)}${aj ? `<span class="t2 pq">${esc(aj)}</span>` : ""}</div>`;
const cel = (p, v, rot, t, opt) => `<td><label class="so-leitor" for="${idDe(p)}">${esc(rot)}</label>${ctl(p, v, t || "n", Object.assign({ w:"6.5em" }, opt || {}))}</td>`;
const SIMNAO = { ops:[["sim", "sim"], ["não", "não"]] }, UM0 = { tipo:"n", ops:[["1", "sim"], ["0", "não"]] };
const FASES_OPS = { ops:["R", "S", "T", "RS", "ST", "RT", "RST"] }, CURVA_OPS = { ops:["B", "C", "D"] };
function selo(s) { if (s == null || s === "") return ""; const t = String(s);
  const c = t === "ativo" || t === "ok" || t === "confere" ? "ok" : t === "não aplicável" ? "in" : t === "bloqueado" || /^sem /.test(t) ? "at" : "al";
  return `<span class="selo ${c}">${esc(t)}</span>`; }
const sec = (id, tit, corpo, nivel) => `<section class="cartao" aria-labelledby="h-avac-${id}"><${nivel || "h2"} id="h-avac-${id}"${nivel === "h3" ? ' class="t3"' : ""}>${esc(tit)}</${nivel || "h2"}>${corpo}</section>`;
const secH3 = (id, tit, corpo) => sec(id, tit, corpo, "h3");   /* subseções do quadro elétrico (sob o <h2> da aba Caixinha) */
const card = (id, tit, num, un) => `<section class="cartao" aria-labelledby="h-avac-c-${id}"><h3 id="h-avac-c-${id}" class="t3">${esc(tit)}</h3><span class="numero">${num}</span><span class="t2"> ${esc(un || "")}</span></section>`;
const tabela = (cap, cab, linhas) => `<div class="rolagem"><table><caption>${esc(cap)}</caption><thead><tr>${cab.map(h => `<th scope="col">${h}</th>`).join("")}</tr></thead><tbody>${linhas.join("")}</tbody></table></div>`;
const linhaKV = (rot, val) => `<tr><th scope="row">${esc(rot)}</th><td>${val}</td></tr>`;
const kv = (cap, pares) => tabela(cap, ["Grandeza", "Valor"], pares.map(p => linhaKV(p[0], p[1])));
function avisoStatus(R, k) { const s = R.status[k]; if (s === "ativo") return "";
  return `<p class="faixa ${s === "bloqueado" ? "at" : "in"}">Módulo ${esc(s)}${s === "bloqueado" ? ": " + esc(FALTA[k]) : " (desligado na Visão geral)"}. Os números abaixo não entram no resumo nem no quadro.</p>`; }
const btn = (attr, txt, rot) => `<button type="button" id="avac-b-${attr.replace(/[^A-Za-z0-9]/g, "_")}" data-avac-${attr.split("=")[0]}="${esc(attr.split("=")[1])}"${rot ? ` aria-label="${esc(rot)}"` : ""}>${esc(txt)}</button>`;

function telaVisao(e, R) { const c = e.controle;
  const dados = sec("dados", "Empreendimento", `<div class="precos">${campo("controle.nome", c.nome, "Nome do empreendimento", "s")}${campo("controle.local", c.local, "Local (cidade / UF)", "s")}
    ${campo("controle.tipo", c.tipo, "Tipo de empreendimento", "sel", "", { ops:TIPOS_EMP })}${campo("controle.resp", c.resp, "Responsável técnico", "s")}${campo("controle.data", c.data, "Data de emissão", "s")}
    ${campo("controle.lat", c.lat, "Latitude da obra (graus decimais)", "nn", "Negativa no hemisfério sul. Ex.: -15,7939")}${campo("controle.lon", c.lon, "Longitude da obra (graus decimais)", "nn", "Negativa a oeste de Greenwich. Ex.: -47,8828")}
    ${campo("controle.raio", c.raio, "Raio de atendimento de fornecedores (km)", "n")}</div>`);
  const mods = sec("mods", "Módulos", tabela("Cada módulo só calcula com situação ativo: não aplicável quando desligado, bloqueado quando faltam dados.", ["Módulo", "Aplica-se?", "Dados mínimos", "Situação"],
    MODULOS.map(([k, n]) => `<tr><th scope="row">${esc(n)}</th>${cel("controle.ativo." + k, c.ativo[k] !== false, "Aplica-se: " + n, "b")}<td>${R.status[k] === "bloqueado" ? esc(FALTA[k]) : "ok"}</td><td>${selo(R.status[k])}</td></tr>`)));
  const chk = sec("chk", "Verificações automáticas de consistência", tabela("Verificações cruzadas entre as partes", ["Verificação", "Resultado", "Onde corrigir"],
    R.checks.map(x => `<tr><th scope="row">${esc(x.verificacao)}</th><td>${selo(x.resultado)}</td><td>${esc(x.onde)}</td></tr>`)));
  const cards = `<div class="grade">${card("tr", "Ar-condicionado", R.status.ac === "ativo" ? f(R.ac.TR, 1) : esc(R.status.ac), R.status.ac === "ativo" ? "TR · " + n2(R.ac.equip, 0) + " equipamentos" : "")}
    ${card("vz", "Ventilação", R.status.vent === "ativo" ? f(R.vent.total, 0) : esc(R.status.vent), R.status.vent === "ativo" ? "m³/h no edifício" : "")}
    ${card("kw", "Quadro QF-AVAC", R.status.quadro === "ativo" ? f(R.quadro.alim.kw, 1) : esc(R.status.quadro), R.status.quadro === "ativo" ? "kW instalados · alimentador " + n2(R.quadro.alim.s, 0) + " mm²" : "")}</div>`;
  const reset = `<p>${btn("reset=1", "Voltar ao exemplo da planilha")} <span class="t2 pq">Substitui todos os dados desta aba pelo exemplo (308 unidades).</span></p>`;
  return (e.migrado ? `<p class="faixa in">Os ambientes da tela anterior foram trazidos como uma tipologia única; o fator de uso antigo não existe na planilha e foi descartado.</p>` : "") + cards + dados + mods + chk + reset; }

function telaTip(e, R) { const tl = e.tipologias.lista, amb = e.ac.amb;
  const t1 = sec("tipo", "Tipologias de unidade", `<div class="precos">${campo("tipologias.pessoasDorm", e.tipologias.pessoasDorm, "Pessoas por dormitório", "n", "Critério de população do memorial.")}</div>`
    + tabela("Uma linha por tipologia; linhas sem nome não entram na matriz de ambientes.", ["Tipologia", "Quantidade", "Área privativa (m²)", "Dormitórios", "Banheiros", "Vagas", "<span class=\"so-leitor\">Ações</span>"],
      tl.map((t, i) => `<tr>${cel("tipologias.lista." + i + ".n", t.n, "Nome da tipologia " + (i + 1), "s", { w:"12em" })}${cel("tipologias.lista." + i + ".q", t.q, "Quantidade de " + t.n)}${cel("tipologias.lista." + i + ".area", t.area, "Área privativa de " + t.n)}
        ${cel("tipologias.lista." + i + ".dorm", t.dorm, "Dormitórios de " + t.n)}${cel("tipologias.lista." + i + ".banh", t.banh, "Banheiros de " + t.n)}${cel("tipologias.lista." + i + ".vagas", t.vagas, "Vagas de " + t.n)}
        <td>${btn("del=tip:" + i, "Remover", "Remover tipologia " + t.n)}</td></tr>`)) + `<p>${btn("add=tip", "Acrescentar tipologia")}</p>`
    + kv("Consolidado do edifício", [["Unidades", f(R.tip.unidades, 0)], ["Área privativa total (m²)", f(R.tip.area, 2)], ["Área privativa média (m²)", f(R.tip.areaMedia, 2)],
      ["Dormitórios", f(R.tip.dorm, 0)], ["População estimada (pessoas)", f(R.tip.pop, 0)], ["Banheiros a exaurir", f(R.tip.banh, 0)], ["Vagas de garagem", f(R.tip.vagas, 0)]]));
  const nomes = tl.map((t, i) => t.n || "(tipologia " + (i + 1) + ")");
  const t2 = sec("amb", "Banco de ambientes e matriz de quantidades", `<p class="t2 pq">Ambientes do mesmo tipo recebem o mesmo equipamento em todo o edifício. Uma área de referência por tipo; se um ambiente for maior, crie outro tipo. Quantidade por unidade em cada tipologia; a coluna de áreas comuns é contagem absoluta.</p>`
    + tabela("Banco de ambientes: área de referência, capacidade padronizada e quantidades", ["Tipo de ambiente", "Área de referência (m²)", "Conta como dormitório", "BTU/h adotado (override)", "Tipo de equipamento", "Na matriz"]
      .concat(nomes.map(n => esc(n) + " (qtd/un.)"), ["Áreas comuns (qtd)", "BTU/h calculado", "BTU/h padronizado", "Qtd no edifício", "BTU/h total", "<span class=\"so-leitor\">Ações</span>"]),
      amb.map((a, i) => { const x = R.ac.amb[i], p = "ac.amb." + i;
        return `<tr>${cel(p + ".n", a.n, "Tipo de ambiente " + (i + 1), "s", { w:"13em" })}${cel(p + ".area", a.area, "Área de referência de " + a.n)}${cel(p + ".dorm", N(a.dorm) === 1, "Conta como dormitório: " + a.n, "b")}
          ${cel(p + ".override", a.override, "BTU/h adotado para " + a.n + " (vazio = calculado)", "nn")}${cel(p + ".equip", a.equip, "Tipo de equipamento de " + a.n, "s", { w:"9em" })}${cel(p + ".matriz", !!a.matriz, "Na matriz: " + a.n, "b")}
          ${nomes.map((n, t) => cel(p + ".q." + t, (a.q || [])[t] == null ? "" : a.q[t], "Quantidade de " + a.n + " por unidade " + n, "n", { w:"4em" })).join("")}${cel(p + ".comum", a.comum, "Quantidade de " + a.n + " nas áreas comuns", "n", { w:"4em" })}
          <td>${f(x.btuCalc, 0)}</td><td>${f(x.btu, 0)}</td><td>${x.foraMatriz ? selo("fora da matriz") : f(x.qtd, 0)}</td><td>${f(x.btuTotal, 0)}</td><td>${btn("del=amb:" + i, "Remover", "Remover ambiente " + a.n)}</td></tr>`; }))
    + `<p>${btn("add=amb", "Acrescentar tipo de ambiente")}</p>`
    + tabela("Verificação — dormitórios do cadastro contra a matriz", ["Tipologia", "Dormitórios no cadastro", "Quartos e suítes na matriz", "Situação"],
      R.ac.dormChk.map(d => `<tr><th scope="row">${esc(d.tipologia)}</th><td>${f(d.cadastro, 0)}</td><td>${f(d.matriz, 0)}</td><td>${selo(d.situacao)}</td></tr>`)));
  return t1 + t2; }

function telaAC(e, R) { const a = e.ac, x = R.ac;
  const ent = sec("acp", "Critério adotado", `<div class="precos">${campo("ac.m2TR", a.m2TR, "Área por TR (m²/TR)")}${campo("ac.cop", a.cop, "COP de referência", "n", "Serve só para estimar a carga elétrica.")}
    ${campo("ac.btuTR", a.btuTR, "1 TR (BTU/h)")}${campo("ac.degraus", a.degraus, "Capacidades comerciais (BTU/h)", "l", "Separe por ponto e vírgula. Arredonda para a capacidade imediatamente superior.")}</div>`);
  const tipos = sec("act", "Capacidade por tipo de ambiente", tabela("Carga térmica calculada (NBR 16401-1) quando o ambiente tem; senão área ÷ m²/TR (triagem); arredondada à capacidade comercial", ["Tipo de ambiente", "Área (m²)", "TR calculado", "BTU/h calculado", "BTU/h padronizado", "Fonte", "Equipamento", "Qtd", "BTU/h total"],
    x.amb.filter(y => y.nome).map(y => `<tr><th scope="row">${esc(y.nome)}</th><td>${f(y.area, 2)}</td><td>${f(y.tr, 2)}</td><td>${f(y.btuCalc, 0)}</td><td>${f(y.btu, 0)}</td><td>${y.cargaBtu != null ? selo("Carga térmica (NBR 16401-1)") : selo("triagem") + " m²/TR"}</td><td>${esc(y.equip || "—")}</td><td>${y.foraMatriz ? selo("fora da matriz") : f(y.qtd, 0)}</td><td>${f(y.btuTotal, 0)}</td></tr>`))
    + `<p class="t2 pq">Os tipos e as quantidades são editados em Tipologias e ambientes. Ambientes levados da subaba Carga térmica (botão \"Levar para o dimensionamento do ar-condicionado\") usam a carga calculada (BTU/h de projeto, com o fator de segurança); os demais seguem a triagem por m²/TR.</p>`);
  const lst = sec("acl", "Lista de equipamentos para o projetista", tabela("Equipamentos por capacidade comercial", ["Capacidade (BTU/h)", "Capacidade (TR)", "Quantidade", "Tipos de ambiente atendidos"],
    x.porCap.map(c => `<tr><th scope="row">${f(c.cap, 0)}</th><td>${f(c.tr, 2)}</td><td>${f(c.qtd, 0)}</td><td>${f(c.tipos, 0)}</td></tr>`))
    + kv("Conferência", [["Total de equipamentos", f(x.equip, 0)], ["Ambientes na matriz", f(x.matrizTotal, 0)], ["Situação", selo(x.situacao)]])
    + `<p class="t2 pq">Acima de 60.000 BTU/h a solução deixa de ser split unitário: divida o ambiente em mais de uma máquina ou mude de sistema.</p>`);
  const res = `<div class="grade">${card("acb", "Capacidade total", f(x.totalBTU, 0), "BTU/h")}${card("actr", "Capacidade total", f(x.TR, 2), "TR · " + n2(x.kWt, 1) + " kW térmicos")}
    ${card("ace", "Carga elétrica estimada", f(x.kWe, 1), "kW (COP " + n2(N(a.cop), 2) + ")")}${card("acq", "Equipamentos", f(x.equip, 0), "unidades")}</div>
    <p class="faixa at">Fachada oeste, cobertura exposta, vidro sem controle solar ou ocupação densa afastam esta estimativa da carga real em até 30%. Antes do executivo, calcule a carga térmica hora a hora (NBR 16401-1) e registre o percentil das condições externas adotado.</p>`;
  return avisoStatus(R, "ac") + res + ent + tipos + lst; }

function telaVent(e, R) { const v = e.vent, x = R.vent;
  const ent = sec("vb", "Dados de entrada", `<h3 class="t3">Banheiros das unidades</h3><div class="precos">${campo("vent.metodo", v.metodo, "Método", "sel", "", { ops:["Vazão fixa", "Trocas por hora"] })}
    ${campo("vent.vazBanh", v.vazBanh, "Vazão fixa por banheiro (m³/h)")}${campo("vent.areaBanh", v.areaBanh, "Área média do banheiro (m²)")}${campo("vent.peBanh", v.peBanh, "Pé-direito do banheiro (m)")}${campo("vent.trocasBanh", v.trocasBanh, "Trocas por hora do banheiro")}</div>
    <h3 class="t3">Depósito de lixo</h3><div class="precos">${campo("vent.lixoArea", v.lixoArea, "Área do depósito (m²)")}${campo("vent.lixoPe", v.lixoPe, "Pé-direito do depósito (m)")}${campo("vent.lixoTrocas", v.lixoTrocas, "Trocas por hora do depósito")}</div>
    <h3 class="t3">Garagem</h3><div class="precos">${campo("vent.garArea", v.garArea, "Área da garagem (m²)")}${campo("vent.garPe", v.garPe, "Pé-direito da garagem (m)")}${campo("vent.garVagas", v.garVagas, "Vagas (0 = usar cadastro)")}
    ${campo("vent.garTrocas", v.garTrocas, "Trocas por hora da garagem")}${campo("vent.garLsm2", v.garLsm2, "Vazão por área (L/s·m²)")}${campo("vent.garVaga", v.garVaga, "Vazão por vaga (m³/h)")}</div>`);
  const out = sec("vo", "Outros ambientes", tabela("Ambientes ventilados por trocas por hora", ["Ambiente", "Área (m²)", "Pé-direito (m)", "Trocas/h", "Vazão (m³/h)", "<span class=\"so-leitor\">Ações</span>"],
    (v.outros || []).map((o, i) => `<tr>${cel("vent.outros." + i + ".n", o.n, "Nome do ambiente " + (i + 1), "s", { w:"12em" })}${cel("vent.outros." + i + ".area", o.area, "Área de " + o.n)}${cel("vent.outros." + i + ".pe", o.pe, "Pé-direito de " + o.n)}
      ${cel("vent.outros." + i + ".trocas", o.trocas, "Trocas por hora de " + o.n)}<td>${f(x.outrosLista[i].vazao, 1)}</td><td>${btn("del=outro:" + i, "Remover", "Remover " + o.n)}</td></tr>`)) + `<p>${btn("add=outro", "Acrescentar ambiente")}</p>`);
  const L = (n, q, cr) => `<tr><th scope="row">${esc(n)}</th><td>${f(q, 1)}</td><td>${f(q / 3.6, 1)}</td><td>${esc(cr)}</td></tr>`;
  const res = sec("vr", "Vazões de projeto", tabela("Vazões por ambiente e total do edifício", ["Ambiente", "Vazão (m³/h)", "Vazão (L/s)", "Critério"], [L("Banheiros das unidades", x.banheiros, "nº de banheiros do cadastro × vazão adotada por peça (" + n2(x.porBanh, 1) + " m³/h)"),
    L("Depósito de lixo", x.lixo, "volume × trocas por hora"), L("Garagem — por trocas/hora", x.garTrocas, "critério a"), L("Garagem — por área", x.garArea, "critério b — L/s·m² convertido"),
    L("Garagem — por vaga", x.garVaga, "critério c (" + n2(x.vagas, 0) + " vagas)"), L("Garagem — adotado", x.garagem, "maior entre a, b e c"), L("Outros ambientes", x.outros, "conforme tabela"), L("TOTAL DO EDIFÍCIO", x.total, "")])
    + `<p class="t2 pq">O total do edifício não é o ponto de operação de um único ventilador: some por prumada e calcule o trecho crítico (Dutos e ventiladores). Garagem tem interface com o controle de fumaça. Confirme os critérios na NBR 16401-3, no código de obras e na IT do Corpo de Bombeiros.</p>`);
  return avisoStatus(R, "vent") + res + ent + out; }

function telaPress(e, R) { const p = e.press, x = R.press;
  const ent = sec("pe", "Dados de entrada", `<div class="precos">${campo("press.dp", p.dp, "Pressão diferencial com portas fechadas (Pa)", "n", "Confirme o valor da classe na NBR 14880 e na IT do CBM.")}
    ${campo("press.v", p.v, "Velocidade nas portas abertas (m/s)")}${campo("press.portas", p.portas, "Número de portas da escada (pavimentos)", "n", "Do projeto de arquitetura — obrigatório.")}
    ${campo("press.abertas", p.abertas, "Portas abertas simultaneamente")}${campo("press.w", p.w, "Largura da porta (m)")}${campo("press.h", p.h, "Altura da porta (m)")}
    ${campo("press.fresta", p.fresta, "Área de fresta por porta fechada (m²)")}${campo("press.outras", p.outras, "Outras áreas de vazamento (m²)", "n", "Paredes, descarga, tampas de duto, elevadores.")}
    ${campo("press.fator", p.fator, "Fator de majoração do sistema")}${campo("press.fechador", p.fechador, "Força do fechador da porta (N)")}${campo("press.limite", p.limite, "Limite de força (N)")}</div>`);
  const res = sec("pr", "Cálculo", kv("Vazão de pressurização e força na porta", [["Área da porta (m²) — A = W · H", f(x.areaPorta, 3)], ["Portas fechadas", f(x.fechadas, 0)], ["Área total de vazamento (m²)", f(x.areaVaz, 4)],
    ["Vazão de vazamento (m³/s) — Q = 0,827 · A · ΔP^0,5", f(x.qVaz, 4)], ["Vazão nas portas abertas (m³/s) — Q = v · A · n", f(x.qAb, 4)], ["Vazão de projeto (m³/s)", f(x.q, 4)],
    ["Vazão de projeto (m³/h)", f(x.qh, 0)], ["Vazão de projeto (L/s)", f(x.qls, 0)], ["Vazão média por porta (m³/h)", f(x.qPorta, 0)],
    ["Força devida à pressão (N) — (W·A·ΔP)/(2·(W − 0,075))", f(x.fPress, 1)], ["Força total de abertura (N)", f(x.fTotal, 1)], ["Situação", selo(x.situacao)]])
    + `<p class="t2 pq">A vazão vai para Dutos e ventiladores. O sistema exige alimentação de segurança, tomada de ar livre de fumaça e acionamento pelo alarme.</p>`);
  return avisoStatus(R, "press") + res + ent; }

function telaSolar(e, R) { const s = e.solar, x = R.solar;
  const ent = sec("se", "Demanda e coletor", `<div class="precos"><div><span class="t2">População (do cadastro)</span><br><strong>${f(x.pop, 0)} pessoas</strong></div>
    ${campo("solar.consumo", s.consumo, "Consumo por pessoa (L/dia)", "n", "Na temperatura de consumo.")}${campo("solar.tq", s.tq, "Temperatura de consumo (°C)")}${campo("solar.tf", s.tf, "Temperatura da água fria (°C)", "n", "Média da rede no local.")}
    ${campo("solar.fracao", s.fracao, "Fração solar desejada (0 a 1)")}${campo("solar.eta", s.eta, "Eficiência média do coletor (%)", "n", "Da etiqueta Inmetro (ENCE) do modelo escolhido.")}
    ${campo("solar.incl", s.incl, "Inclinação do coletor (°)", "n", "Vazio ou 0 = deitado.")}${campo("solar.azim", s.azim, "Para onde o coletor aponta (°)", "n", "0 norte, 90 leste, 180 sul, 270 oeste.")}
    ${campo("solar.prod", s.prod, "Produção específica informada (kWh/m²·dia)", "n", "Só sem a eficiência ou sem o sol do lugar.")}
    ${campo("solar.areaCol", s.areaCol, "Área útil por coletor (m²)")}${campo("solar.volM2", s.volM2, "Volume mínimo por m² de coletor (L)")}${campo("solar.horas", s.horas, "Horas de operação do apoio (h)")}
    ${campo("solar.reserv", s.reserv, "Reservatórios comerciais (L)", "l", "Separe por ponto e vírgula.")}</div>`);
  const res = sec("sr", "Cálculo", kv("Aquecimento solar pelo método simplificado", [["Consumo diário (L/dia)", f(x.consumo, 0)], ["Diferencial de temperatura (°C)", f(x.dT, 1)],
    ["Demanda de energia (kWh/dia) — E = V · c · ΔT / 3600", f(x.demanda, 2)], ["Parcela solar (kWh/dia)", f(x.parcela, 2)], ["Área coletora necessária (m²)", f(x.areaNec, 2)],
    ["Número de coletores", f(x.coletores, 0)], ["Área coletora instalada (m²)", f(x.areaInst, 1)], ["Volume mínimo pelos coletores (L)", f(x.volCol, 0)], ["Volume requerido (L)", f(x.volReq, 0)],
    ["Reservatório comercial (L)", f(x.reservatorio, 0)], ["Potência do apoio (kW)", f(x.apoio, 2)]])
    + `<p class="t2 pq">Confirme área livre de cobertura, sombreamento ao longo do ano e acesso para manutenção. Procedimento completo na NBR 15569.</p>`);
  const mes = x.modo === "mensal" ? sec("sm", "Produção do coletor mês a mês", `<div class="rolagem"><table><caption>Eficiência ${f(x.eta * 100, 0)}% × sol do lugar (${esc(s.solFonte || "base do servidor")}); a área sai do pior mês, ${MESES_AQ[x.piorMes]}</caption><thead><tr><th scope="col">Mês</th><th scope="col">Produção (kWh/m²·dia)</th><th scope="col">Área para a parcela solar (m²)</th></tr></thead><tbody>
    ${x.prodMes.map((p, i) => `<tr><th scope="row">${MESES_AQ[i]}${i === x.piorMes ? " (pior)" : ""}</th><td>${f(p, 2)}</td><td>${f(p ? x.parcela / p : 0, 1)}</td></tr>`).join("")}</tbody></table></div>`)
    : `<p class="t2 pq">${x.modo === "informada" ? "Produção informada à mão: informe a eficiência da etiqueta Inmetro para usar o sol do lugar mês a mês." : "Falta a eficiência do coletor (etiqueta Inmetro) ou a produção específica: sem ela o aquecimento solar não é dimensionado."}</p>`;
  return avisoStatus(R, "solar") + res + mes + ent; }

function telaPiscina(e, R) { const p = e.piscina, x = R.piscina;
  const ent = sec("ie", "Dados de entrada", `<div class="precos">${campo("piscina.area", p.area, "Área do espelho d'água (m²)")}${campo("piscina.prof", p.prof, "Profundidade média (m)")}
    ${campo("piscina.tw", p.tw, "Temperatura da água (°C)")}${campo("piscina.ta", p.ta, "Temperatura do ar (°C)", "n", "Mínima de projeto, não a média.")}${campo("piscina.ur", p.ur, "Umidade relativa (%)")}
    ${campo("piscina.v", p.v, "Velocidade do ar na lâmina (m/s)", "n", "0,1 coberta · 0,5 a 1,0 descoberta.")}${campo("piscina.descoberta", String(N(p.descoberta)), "Piscina descoberta?", "sel", "", UM0)}
    ${campo("piscina.capa", String(N(p.capa)), "Usa capa térmica?", "sel", "Só se o uso for garantido em operação.", UM0)}${campo("piscina.hCapa", p.hCapa, "Horas com capa (h/dia)")}${campo("piscina.redCapa", p.redCapa, "Redução de perda com capa (0 a 1)")}
    ${campo("piscina.paredes", p.paredes, "Perda por paredes e fundo (% das demais)")}${campo("piscina.ti", p.ti, "Temperatura inicial da água (°C)")}${campo("piscina.tAq", p.tAq, "Tempo de aquecimento inicial (h)")}</div>`);
  const res = sec("ir", "Perdas e potência", kv("Psicrometria, perdas térmicas e potência de seleção", [["Pressão de vapor saturado na água (kPa)", f(x.pvs, 3)], ["Pressão de vapor no ar (kPa)", f(x.pva, 3)],
    ["Umidade absoluta na superfície (g/kg)", f(x.ws * 1000, 2)], ["Umidade absoluta do ar (g/kg)", f(x.wa * 1000, 2)], ["Evaporação de água (kg/h) — (25 + 19·v) · A · (w_s − w_a)", f(x.evap, 2)],
    ["Perda por evaporação (kW)", f(x.qEvap, 2)], ["Coeficiente de convecção (W/m²·K) — 5,7 + 3,8·v", f(x.h, 2)], ["Perda por convecção (kW)", f(x.qConv, 2)], ["Temperatura do céu (°C)", f(x.tCeu, 1)],
    ["Perda por radiação (kW) — ε = 0,95", f(x.qRad, 2)], ["Perda por paredes e fundo (kW)", f(x.qParedes, 2)], ["Subtotal de perdas (kW)", f(x.subtotal, 2)], ["Redução pela capa térmica (kW)", f(x.capa, 2)],
    ["Manutenção de temperatura (kW)", f(x.manut, 2)], ["Volume da piscina (m³)", f(x.volume, 1)], ["Aquecimento inicial (kW)", f(x.inicial, 2)], ["Potência total de seleção (kW)", f(x.total, 2)], ["Potência total (BTU/h)", f(x.btu, 0)]])
    + `<p class="t2 pq">A evaporação domina e é sensível ao vento. Bomba de calor perde capacidade no frio: verifique na condição de inverno.</p>`);
  return avisoStatus(R, "piscina") + res + ent; }

function telaDutos(e, R) { const d = e.dutos, x = R.dutos;
  const ent = sec("de", "Parâmetros do ar, do duto e do motor", `<div class="precos">${campo("dutos.alt", d.alt, "Altitude do local (m)")}${campo("dutos.temp", d.temp, "Temperatura do ar no duto (°C)")}
    ${campo("dutos.rug", d.rug, "Rugosidade absoluta (m)", "n", "Chapa galvanizada: 0,00009 m.")}${campo("dutos.fs", d.fs, "Fator de segurança sobre a pressão")}${campo("dutos.rend", d.rend, "Rendimento do conjunto motoventilador")}
    ${campo("dutos.rendTransm", d.rendTransm == null ? 0.95 : d.rendTransm, "Rendimento da transmissão", "n", "Correia: 0,95. Acoplamento direto: 1.")}${campo("dutos.rendMotor", d.rendMotor, "Rendimento do motor")}${campo("dutos.margem1", d.margem1, "Margem do motor até 1,5 kW")}${campo("dutos.margem2", d.margem2, "Margem do motor acima de 1,5 kW")}</div>`
    + kv("Propriedades do ar", [["Pressão atmosférica (kPa)", f(x.patm, 3)], ["Densidade do ar (kg/m³)", f(x.rho, 4)], ["Viscosidade cinemática (m²/s, Sutherland)", x.nu.toExponential(4).replace(".", ",")]]));
  const FONTES = [["", "vazão manual"], ["banheiros", "Ventilação — banheiros"], ["lixo", "Ventilação — lixo"], ["garagem", "Ventilação — garagem"], ["press", "Pressurização"]];
  const sis = sec("ds", "Trecho crítico por sistema", tabela("Dados de cada sistema (a vazão vem das outras partes ou é digitada)", ["Sistema", "Origem da vazão", "Vazão manual (m³/h)", "Velocidade (m/s)", "Trecho reto (m)", "Comp. equiv. acessórios (m)", "Perdas localizadas (Pa)", "Altura disponível (mm)", "Tipo de sistema", "<span class=\"so-leitor\">Ações</span>"],
    (d.sistemas || []).map((s, i) => { const p = "dutos.sistemas." + i;
      return `<tr>${cel(p + ".nome", s.nome, "Nome do sistema " + (i + 1), "s", { w:"12em" })}${cel(p + ".fonte", s.fonte || "", "Origem da vazão de " + s.nome, "sel", { ops:FONTES, w:"" })}${cel(p + ".vazao", s.vazao, "Vazão manual de " + s.nome)}
        ${cel(p + ".vel", s.vel, "Velocidade de " + s.nome)}${cel(p + ".reto", s.reto, "Trecho reto de " + s.nome)}${cel(p + ".equiv", s.equiv, "Comprimento equivalente de acessórios de " + s.nome)}${cel(p + ".local", s.local, "Perdas localizadas de " + s.nome)}
        ${cel(p + ".altura", s.altura, "Altura disponível de " + s.nome)}${cel(p + ".tipo", s.tipo || "", "Tipo de sistema de " + s.nome, "sel", { ops:[["", "—"]].concat(TIPOS_DUTO.map(t => [t[0], t[0] + " (" + t[1] + " m/s)"])) })}<td>${btn("del=sis:" + i, "Remover", "Remover " + s.nome)}</td></tr>`; }))
    + `<p>${btn("add=sis", "Acrescentar sistema")}</p>`
    + tabela("Resultados: perda de carga (Darcy-Weisbach com Swamee-Jain), duto retangular e motor", ["Sistema", "Vazão (m³/h)", "Diâm. equiv. (mm)", "Reynolds", "Fator de atrito", "Perda unitária (Pa/m)", "Perda no trecho (Pa)", "Pressão total (Pa)", "Potência absorvida (kW)", "Largura (mm)", "De retangular (mm)", "Relação de aspecto", "Velocidade no retangular (m/s)", "Potência no eixo (kW)", "Com margem (kW)", "Potência elétrica (kW)", "Motor (kW)", "Motor (cv)", "Situação"],
      x.sis.map(o => `<tr><th scope="row">${esc(o.nome)}</th><td>${f(o.vazao, 0)}</td><td>${f(o.diam, 0)}</td><td>${f(o.reynolds, 0)}</td><td>${f(o.atrito, 4)}</td><td>${f(o.perdaUnit, 3)}</td><td>${f(o.perdaTrecho, 1)}</td><td>${f(o.pressao, 1)}</td><td>${f(o.potAbs, 3)}</td>
        <td>${f(o.largura, 0)}</td><td>${f(o.deRet, 0)}</td><td>${f(o.aspecto, 2)}</td><td>${f(o.velRet, 2)}</td><td>${f(o.potEixo, 3)}</td><td>${f(o.potMargem, 3)}</td><td>${f(o.potEletrica, 3)}</td><td>${f(o.motorKw, 2)}</td><td>${f(o.motorCv, 2)}</td><td>${selo(o.situacao)}</td></tr>`))
    + kv("Totais", [["Potência absorvida total (kW)", f(x.potAbs, 3)], ["Potência no eixo total (kW)", f(x.potEixo, 3)], ["Potência elétrica total (kW)", f(x.potEletrica, 3)], ["Motores instalados (kW)", f(x.motores, 2)], ["Ventiladores especificados", f(x.ventiladores, 0)]])
    + `<p class="t2 pq">Perdas localizadas reúnem veneziana, grelhas, atenuador, damper e filtro sujo. A seção retangular tem diâmetro equivalente (De = 1,30·(a·b)^0,625/(a+b)^0,25) igual ou maior que o circular. Potência no eixo do motor = potência absorvida ÷ rendimento da transmissão; potência elétrica = potência no eixo ÷ rendimento do motor. A planilha multiplicava pelo rendimento do motor, o que escolhia motor menor (revisão de 15/11/2026).</p>`);
  const vel = sec("dv", "Verificação de velocidade", tabela("Velocidade adotada contra o limite do tipo de sistema", ["Sistema", "Velocidade adotada (m/s)", "Limite (m/s)", "Situação"],
    x.sis.filter(o => o.nome).map(o => `<tr><th scope="row">${esc(o.nome)}</th><td>${f(o.vel, 1)}</td><td>${f(o.limite, 0)}</td><td>${selo(o.situacaoVel)}</td></tr>`))
    + `<p class="t2 pq">Em shaft residencial quem manda é o ruído: 6 a 8 m/s em prumada, até 12 m/s em garagem e pressurização.</p>`);
  return avisoStatus(R, "dutos") + sis + vel + ent; }

function potenciasQuadro(al) { const PCq = typeof PhysisCalc !== "undefined" ? PhysisCalc : null, fp = al.kva > 0 ? al.kw / al.kva : null, lim = PCq ? PCq.premissa("eletrica.fator_potencia_minimo") : null;
  const o = { p:al.kw, s:al.kva, q:Math.sqrt(Math.max(0, al.kva * al.kva - al.kw * al.kw)), fp, fonte:"circuitos", baixo:lim != null && fp != null && fp < lim, limite:lim };
  return PCq ? PCq.potenciasHtml([["Alimentador (soma dos circuitos)", o]], /^en/i.test(document.documentElement.lang), "Potências do quadro (FP de cada circuito, com o rendimento)") : ""; }
function telaQuadro(e, R) { const sec = secH3, q = e.quadro, x = R.quadro, al = x.alim;
  const P = (k, rot, t, aj, opt) => campo("quadro." + k, q[k], rot, t, aj, opt);
  const ent = sec("qe", "Parâmetros elétricos", `<div class="precos">${P("vff", "Tensão fase-fase (V)", "n", "380/220 V ou 220/127 V: confirme com a concessionária.")}${P("vfn", "Tensão fase-neutro U0 (V)")}
    ${P("tamb", "Temperatura ambiente do trajeto (°C)", "n", "FCT = " + n2(al.fct, 2) + " (NBR 5410, Tabela 40, linha seguinte).")}${P("fcaC", "Fator de agrupamento — circuitos")}${P("fcaA", "Fator de agrupamento — alimentador")}
    ${P("rho70", "Resistividade do cobre a 70 °C (Ω·mm²/m)")}${P("rho20", "Resistividade do cobre a 20 °C (Ω·mm²/m)")}${P("smin", "Seção mínima — força (mm²)")}
    ${P("dvTot", "Queda de tensão total admitida (fração)", "n", "0,04 = 4%. Terminais: " + n2(x.dvTerm * 100, 2) + "%.")}${P("dvAlim", "Parcela do alimentador (fração)")}${P("dvPart", "Queda máxima na partida de motor (fração)")}
    ${P("compAlim", "Comprimento do alimentador (m)")}${P("deseq", "Desequilíbrio máximo entre fases (fração)")}${P("copPisc", "COP do aquecedor da piscina", "n", "1 = resistência; acima de 1 = bomba de calor.")}
    ${P("icc", "Icc trifásica na origem do alimentador (kA)", "n", "Obrigatório confirmar.")}${P("x", "Reatância dos cabos (mΩ/m)")}${P("icnMod", "Capacidade de interrupção — modulares (kA)")}${P("icuCM", "Capacidade de interrupção — caixa moldada (kA)")}
    ${P("i2t", "Energia passante máx. do modular (A²s)")}${P("tCM", "Tempo de eliminação — caixa moldada (s)")}${P("magCM", "Disparo magnético — caixa moldada (× In)")}${P("icuAlim", "Capacidade de interrupção — disjuntor do alimentador (kA)")}
    ${P("tAlim", "Tempo de eliminação — alimentador (s)")}${P("magAlim", "Disparo magnético — alimentador (× In)")}${P("k", "Constante k do condutor (cobre/PVC)")}
    ${P("harm", "3ª harmônica acima de 15% no alimentador?", "sel", "sim: neutro pleno e 4 condutores carregados.", SIMNAO)}${P("f4", "Fator para 4 condutores carregados")}</div>`);
  const cp = c => c.extra != null ? "quadro.extras." + c.extra : "quadro.circ." + c.id;
  const circ = sec("qc", "Circuitos do quadro — cargas de AVAC", tabela("Parâmetros de cada circuito (ventiladores, ar-condicionado de áreas comuns, apoio solar, piscina e cargas extras)",
    ["Carga", "Potência unitária (kW)", "Qtd", "Fases", "Fator de potência", "Rendimento", "Fator de demanda", "Fator de serviço", "Ip/In partida", "Curva", "DR 30 mA", "Comprimento (m)", "Corrente de placa (A)", "<span class=\"so-leitor\">Ações</span>"],
    x.circ.map(c => { const p = cp(c), n = c.nome || "carga";
      return `<tr>${c.extra != null ? cel(p + ".nome", c.nome, "Descrição da carga extra " + (c.extra + 1), "s", { w:"12em" }) + cel(p + ".kw", c.kwUnit, "Potência unitária de " + n) + cel(p + ".qtd", c.qtd, "Quantidade de " + n)
          : `<th scope="row">${esc(c.nome || "(sistema sem nome)")}</th><td>${f(c.kwUnit, 2)}</td><td>${f(c.qtd, 0)}</td>`}
        ${cel(p + ".fases", c.p.fases, "Fases de " + n, "sel", FASES_OPS)}${cel(p + ".fp", c.p.fp, "Fator de potência de " + n, "n", { w:"4.5em" })}${cel(p + ".rend", c.p.rend, "Rendimento de " + n, "n", { w:"4.5em" })}
        ${cel(p + ".fd", c.p.fd, "Fator de demanda de " + n, "n", { w:"4.5em" })}${cel(p + ".fs", c.p.fs, "Fator de serviço de " + n, "n", { w:"4.5em" })}${cel(p + ".ipin", c.p.ipin, "Ip/In de partida de " + n, "n", { w:"4em" })}
        ${cel(p + ".curva", c.p.curva, "Curva do disjuntor de " + n, "sel", CURVA_OPS)}${cel(p + ".dr", c.p.dr, "DR de 30 mA em " + n, "sel", SIMNAO)}${cel(p + ".comp", c.p.comp, "Comprimento de " + n, "n", { w:"4.5em" })}
        ${cel(p + ".iplaca", c.p.iplaca, "Corrente de placa de " + n + " (vazio = calculada)", "nn", { w:"4.5em" })}<td>${c.extra != null ? btn("del=extra:" + c.extra, "Remover", "Remover " + n) : ""}</td></tr>`; }))
    + `<p>${btn("add=extra", "Acrescentar carga")}</p>`
    + tabela("Resultados por circuito: corrente, proteção e seção (capacidade, queda, curto, seccionamento e partida)", ["Carga", "Potência instalada (kW)", "Aparente (kVA)", "Corrente calculada (A)", "Ib (A)", "Disjuntor In (A)", "Seção por capacidade", "Por queda", "Por proteção e partida", "Fase adotada (mm²)", "PE (mm²)", "Iz corrigida (A)", "Queda em regime", "Queda na partida", "Comp. máx. seccionamento (m)", "Fase R (A)", "Fase S (A)", "Fase T (A)", "Situação"],
      x.circ.filter(c => c.kw > 0 || c.extra != null).map(c => `<tr><th scope="row">${esc(c.nome || "—")}</th><td>${f(c.kw, 2)}</td><td>${f(c.kva, 2)}</td><td>${f(c.icalc, 2)}</td><td>${f(c.ib, 2)}</td><td>${f(c.in, 0)}</td><td>${f(c.sCap, 1)}</td><td>${f(c.sQueda, 1)}</td><td>${f(c.sProt, 1)}</td>
        <td>${f(c.s, 1)}</td><td>${f(c.sPE, 1)}</td><td>${f(c.iz, 1)}</td><td>${c.dv == null ? "—" : n2(c.dv * 100, 2) + "%"}</td><td>${c.dvPartida == null ? "—" : n2(c.dvPartida * 100, 2) + "%"}</td><td>${f(c.lmax, 1)}</td><td>${f(c.iR, 1)}</td><td>${f(c.iS, 1)}</td><td>${f(c.iT, 1)}</td><td>${selo(c.situacao)}</td></tr>`)));
  const ali = sec("qa", "Quadro — totais, curto-circuito e alimentador", kv("Totais do QF-AVAC e dimensionamento do alimentador", [["Circuitos ativos", f(al.ativos, 0)], ["Circuitos de reserva recomendados", f(al.reserva, 0)],
    ["Potência instalada (kW)", f(al.kw, 2)], ["Potência aparente instalada (kVA)", f(al.kva, 2)], ["Demanda (kVA)", f(al.dem, 2)], ["Corrente — fase R (A)", f(al.iR, 1)], ["Corrente — fase S (A)", f(al.iS, 1)], ["Corrente — fase T (A)", f(al.iT, 1)],
    ["Corrente de projeto do alimentador (A)", f(al.ib, 1)], ["Desequilíbrio entre fases", n2(al.deseq * 100, 1) + "%"], ["Disjuntor do alimentador In (A)", f(al.in, 0)], ["Seção por capacidade (mm²)", f(al.sCap, 0)],
    ["Seção por queda de tensão (mm²)", f(al.sQueda, 0)], ["Seção por curto e seccionamento (mm²)", f(al.sCurto, 0)], ["Seção fase adotada (mm²)", f(al.s, 0)], ["Seção do neutro (mm²)", f(al.sN, 0)], ["Seção do PE (mm²)", f(al.sPE, 0)],
    ["Iz corrigida do alimentador (A)", f(al.iz, 1)], ["Queda de tensão no alimentador", n2(al.dv * 100, 2) + "%"], ["Pior queda total em regime", n2(al.dvTot * 100, 2) + "%"], ["Corrente de curto na origem (kA)", f(al.icc, 2)],
    ["Corrente de curto no QF-AVAC (kA)", f(al.iccQF, 2)], ["Comprimento máx. do alimentador por seccionamento (m)", f(al.lmax, 1)], ["Situação", selo(al.situacao)]])
    + `<p class="t2 pq">Queda sem reatância (cos φ = 1); curto com fonte reativa e cabo a 20 °C; seccionamento com Zs ≈ 1,25 × resistência do laço a 70 °C e 80% de U0. Seletividade, DPS e coordenação ficam para o projeto elétrico. Pressurização e exaustão de fumaça exigem alimentação de segurança independente.</p>`);
  const spl = sec("qs", "Circuito típico de split por capacidade — unidades autônomas", tabela("Circuito-padrão de cada capacidade (sai do quadro de cada apartamento)",
    ["Capacidade (BTU/h)", "Qtd no edifício", "Potência (kW)", "Fases", "Fator de potência", "Corrente de placa (A)", "Comprimento (m)", "Curva", "DR 30 mA", "Ib (A)", "Disjuntor (A)", "Fase (mm²)", "PE (mm²)", "Iz (A)", "Queda", "Comp. máx. (m)", "Situação"],
    x.splits.map(s => { const p = "quadro.splits." + s.cap, n = n2(s.cap, 0) + " BTU/h";
      return `<tr><th scope="row">${f(s.cap, 0)}</th><td>${f(s.qtd, 0)}</td><td>${f(s.kw, 3)}</td>${cel(p + ".fases", s.p.fases, "Fases do split de " + n, "sel", FASES_OPS)}${cel(p + ".fp", s.p.fp, "Fator de potência do split de " + n, "n", { w:"4.5em" })}
        ${cel(p + ".iplaca", s.p.iplaca, "Corrente de placa do split de " + n, "nn", { w:"4.5em" })}${cel(p + ".comp", s.p.comp, "Comprimento do circuito do split de " + n, "n", { w:"4.5em" })}${cel(p + ".curva", s.p.curva, "Curva do split de " + n, "sel", CURVA_OPS)}
        ${cel(p + ".dr", s.p.dr, "DR do split de " + n, "sel", SIMNAO)}<td>${f(s.ib, 2)}</td><td>${f(s.in, 0)}</td><td>${f(s.s, 1)}</td><td>${f(s.sPE, 1)}</td><td>${f(s.iz, 1)}</td><td>${s.dv == null ? "—" : n2(s.dv * 100, 2) + "%"}</td><td>${f(s.lmax, 1)}</td><td>${selo(s.situacao)}</td></tr>`; }))
    + kv("Splits no edifício", [["Circuitos de split no edifício", f(x.splitsQtd, 0)], ["Carga instalada de splits (kW)", f(x.splitsKw, 2)], ["Conferência com o ar-condicionado (splits + áreas comuns)", selo(x.conf)]]));
  return avisoStatus(R, "quadro") + ali + potenciasQuadro(al) + circ + spl + ent; }

function telaResumo(e, R) {
  const res = sec("rr", "Resumo de instalações — anteprojeto", tabela("Resumo por sistema", ["Sistema", "Grandeza", "Valor", "Base do cálculo"],
    R.resumo.map(x => `<tr><th scope="row">${esc(x.sistema)}</th><td>${esc(x.grandeza)}</td><td>${typeof x.valor === "number" ? f(x.valor, Number.isInteger(x.valor) ? 0 : 2) : selo(x.valor)}</td><td>${esc(x.base)}</td></tr>`))
    + `<p class="t2 pq">Anteprojeto: a estimativa por área específica não substitui o cálculo de carga térmica; vazões de exaustão e pressurização devem ser confirmadas no texto vigente das normas ABNT e na IT do Corpo de Bombeiros.</p>`);
  const lst = sec("rl", "Lista de equipamentos", R.status.lista !== "ativo" ? avisoStatus(R, "lista") : tabela("Consolidada de todos os sistemas (categoria genérica no lugar do fabricante)", ["Item", "Sistema", "Descrição", "Quantidade", "Capacidade", "Unidade", "Categoria de referência"],
    R.lista.map(x => `<tr><th scope="row">${x.item}</th><td>${esc(x.sistema)}</td><td>${esc(x.descricao)}</td><td>${f(x.qtd, 0)}</td><td>${f(x.cap, Number.isInteger(x.cap) ? 0 : 2)}</td><td>${esc(x.un)}</td><td>${esc(x.categoria)}</td></tr>`))
    + `<p class="t2 pq">Especifique por desempenho e cite dois ou três fabricantes por item no orçamento.</p>`);
  return res + lst + `<p class="t2">Quadro elétrico: ver aba Caixinha Physis IoT (cargas vindas desta lista de equipamentos).</p>`; }

function telaMemoria(e, R) {
  return R.memoria.map((m, i) => sec("m" + i, m.titulo, `<p>${selo(m.situacao)}</p>` + (m.linhas.length ? `<ul>${m.linhas.map(l => `<li>${esc(l)}</li>`).join("")}</ul>` : `<p class="t2">Módulo ${esc(m.situacao)}: não calculado nesta emissão.</p>`))).join("")
    + `<p class="t2 pq">Documento de anteprojeto. Módulos não aplicáveis ou bloqueados não foram calculados nesta emissão.</p>`; }

/* sol do lugar para o aquecimento solar: o mesmo da aba Energia solar (base GIS do servidor ou estimativa pela latitude) */
function comSol(e) { try { const S = typeof window !== "undefined" && window.SOLAR && window.SOLAR.compat ? window.SOLAR.compat() : null;
  if (S && Array.isArray(S.H) && S.H.length === 12 && !(e.solar && Array.isArray(e.solar.H))) { e = JSON.parse(JSON.stringify(e)); e.solar = e.solar || {};
    e.solar.H = S.H; e.solar.lat = S.lat; e.solar.solFonte = S.medido ? "medida por satélite (NASA POWER, no servidor)" : "estimada pela latitude"; } } catch (x) {} return e; }
/* ── Levar a carga térmica para o dimensionamento do ar-condicionado (botão na subaba Carga térmica) ──
   cargasCalculadas(): [{ nome, btuh (projeto, com fator de segurança), area }] da subaba Carga térmica.
   planoCargas(e, R, cargas): o que muda em cada ambiente (antes → depois, feito à mão, novo).
   aplicarCargas(e, cargas): novo estado com x.carga em cada ambiente de mesmo nome (cria o que falta, 1 unidade);
   o valor feito à mão (override) só é trocado depois da confirmação, e o desfazer volta o estado anterior. */
function cargasCalculadas() { try { const CT = typeof window !== "undefined" ? window.CARGA_TERMICA : null, o = CT && typeof calcLer === "function" ? calcLer("cargatermica") : null;
  if (!(CT && o && o.e && Array.isArray(o.e.ambientes) && o.e.ambientes.length)) return [];
  const r = CT.calcular(o.e.ambientes, o.e.clima, o.e.opcoes);
  return (r.ambientes || []).filter(a => a.nome && a.projeto && a.projeto.btuh > 0).map(a => ({ nome:a.nome, btuh:a.projeto.btuh, area:a.area })); } catch (x) { return []; } }
function planoCargas(e, R, cargas) { const deg = (e.ac.degraus || []).map(N).filter(x => x > 0).sort((a, b) => a - b), btuTR = N(e.ac.btuTR);
  return (cargas || []).map(c => { const i = (e.ac.amb || []).findIndex(a => String(a.n) === c.nome), a = i >= 0 ? e.ac.amb[i] : null, r = i >= 0 ? R.ac.amb[i] : null;
    const pad = acima(deg, c.btuh), depois = pad != null ? pad : (btuTR ? Math.ceil(c.btuh / btuTR) * btuTR : c.btuh);
    return { i, nome:c.nome, btuh:c.btuh, antes:r ? r.btu : null, depois, manual:!!(a && a.override !== null && a.override !== undefined && a.override !== ""), novo:i < 0 }; }); }
function aplicarCargas(e, cargas) { e = JSON.parse(JSON.stringify(e));
  (cargas || []).forEach(c => { let a = e.ac.amb.find(x => String(x.n) === c.nome);
    if (!a) { a = { n:c.nome, area:+(c.area || 0).toFixed(2), dorm:0, override:null, equip:"Split hi-wall", matriz:true, q:[], comum:1 }; e.ac.amb.push(a); }
    a.carga = c.btuh; a.override = null; });
  return e; }
function telaLevarCargas(e, R) { const cargas = cargasCalculadas(), plano = planoCargas(e, R, cargas), f = x => x == null ? "—" : n2(x, 0);
  const conf = ui.avacPush && plano.length ? `<div role="alertdialog" aria-modal="false" aria-labelledby="h-avac-push-c" aria-describedby="avac-push-d" class="faixa at">
    <h3 id="h-avac-push-c" class="t3">Confirme o que vai mudar</h3><p id="avac-push-d" class="t2">A capacidade destes ambientes passa a vir da carga térmica (NBR 16401-1).${plano.some(p => p.manual) ? " Atenção: há valor digitado à mão que será trocado." : ""}</p>
    <div class="rolagem"><table><caption>Ambiente, capacidade antes e depois (BTU/h padronizado)</caption><thead><tr><th scope="col">Ambiente</th><th scope="col">Antes</th><th scope="col">Depois</th><th scope="col">Observação</th></tr></thead><tbody>
    ${plano.map(p => `<tr><th scope="row">${esc(p.nome)}</th><td>${f(p.antes)}</td><td>${f(p.depois)}</td><td>${p.novo ? "ambiente novo (1 unidade; ajuste a quantidade em Tipologias e ambientes)" : p.manual ? "valor feito à mão será trocado" : "—"}</td></tr>`).join("")}</tbody></table></div>
    <div class="chips"><button type="button" id="avac-push-ok" data-avac-push="ok">Confirmar</button><button type="button" id="avac-push-cancelar" data-avac-push="cancelar">Cancelar</button></div></div>` : "";
  const desf = ui.avacDesfazer ? `<p class="t2" role="status">Carga térmica levada para ${ui.avacDesfazerN || 0} ambiente(s) do ar-condicionado. <button type="button" id="avac-push-desfazer" data-avac-push="desfazer">Desfazer</button></p>` : "";
  return `<section class="cartao" aria-labelledby="h-avac-push"><h2 id="h-avac-push">Levar para o ar-condicionado</h2>
    <p class="t2 pq">Cada ambiente com carga calculada acima passa a dimensionar o ambiente de mesmo nome no Ar-condicionado (se não existir, é criado). A capacidade aparece com a fonte "Carga térmica (NBR 16401-1)" no lugar da triagem por m²/TR. Antes de mudar, o sistema mostra o que muda; depois, dá para desfazer.</p>
    <button type="button" id="avac-push-ver" data-avac-push="ver"${plano.length ? "" : " disabled aria-describedby=\"avac-push-sem\""}>Levar para o dimensionamento do ar-condicionado</button>${plano.length ? "" : `<p id="avac-push-sem" class="t2 pq">Calcule a carga de pelo menos um ambiente acima.</p>`}
    ${conf}${desf}</section>`; }
function telaAvac() { const e = comSol(ler()), R = calcular(e), sub = SUBS.some(s => s[0] === ui.avacSub) ? ui.avacSub : "visao";
  const chips = `<div class="chips" role="group" aria-label="Partes do AVAC">${SUBS.map(([k, n]) => `<button type="button" id="avac-sub-${k}" data-avac-sub="${k}" aria-pressed="${k === sub}">${esc(n)}</button>`).join("")}</div>`;
  const corpo = { visao:telaVisao, tip:telaTip, carga: () => (typeof telaCargaTermica === "function" ? telaCargaTermica() : "<p class=\"t2\">Módulo de carga térmica não carregado.</p>") + telaLevarCargas(e, R), ac:telaAC, vent:telaVent, press:telaPress, solar:telaSolar, piscina:telaPiscina, dutos:telaDutos, resumo:telaResumo, memoria:telaMemoria }[sub](e, R);
  return `<h1>AVAC e térmico</h1><p class="t2 apoio">Ar-condicionado, ventilação, pressurização de escada, aquecimento solar, piscina, dutos e quadro elétrico — as contas da planilha PHYSIS_AVAC-5. Altere os dados: tudo é recalculado.</p>${chips}<div id="avac-corpo">${corpo}</div>`; }

/* ════════ Eventos (atributos data-avac-…) ════════ */
function refocar(id) { const x = el(id); if (x) x.focus(); }
if (typeof document !== "undefined" && !window.__avacEventos) { window.__avacEventos = true;
  document.addEventListener("change", ev => { const t = ev.target; if (!t || !t.dataset || t.dataset.avacK == null) return;
    const tp = t.dataset.avacT || "n"; let v;
    if (tp === "b") v = !!t.checked; else if (tp === "s") v = t.value;
    else if (tp === "l") v = String(t.value).split(/[;\s]+/).map(s => numBr(s)).filter(x => x != null && isFinite(x) && x > 0);
    else { const s = String(t.value).trim(); v = s === "" ? (tp === "nn" ? null : 0) : numBr(s); if (v == null || !isFinite(v)) v = tp === "nn" ? null : 0; }
    const e = ler(), k = t.dataset.avacK; setPath(e, k, k.indexOf("ac.amb.") === 0 && /\.dorm$/.test(k) ? (v ? 1 : 0) : v); gravar(e); const id = t.id; desenhar(false); refocar(id); });
  document.addEventListener("click", ev => { const b = ev.target.closest ? ev.target.closest("button") : null; if (!b || !b.dataset) return;
    if (b.dataset.avacSub) { ui.avacSub = b.dataset.avacSub; desenhar(false); refocar("avac-sub-" + b.dataset.avacSub); return; }
    if (b.dataset.avacPush) { const a = b.dataset.avacPush;
      if (a === "ver") { ui.avacPush = true; desenhar(false); refocar("avac-push-ok"); return; }
      if (a === "cancelar") { ui.avacPush = false; desenhar(false); refocar("avac-push-ver"); return; }
      if (a === "ok") { const e0 = ler(), c = cargasCalculadas(); ui.avacDesfazer = JSON.stringify(e0.ac.amb); ui.avacDesfazerN = c.length; ui.avacPush = false;
        gravar(aplicarCargas(e0, c)); desenhar(false); refocar("avac-push-desfazer"); return; }
      if (a === "desfazer" && ui.avacDesfazer) { const e0 = ler(); e0.ac.amb = JSON.parse(ui.avacDesfazer); ui.avacDesfazer = null; gravar(e0); desenhar(false); refocar("avac-push-ver"); return; }
      return; }
    const add = b.dataset.avacAdd, del = b.dataset.avacDel; if (!add && !del && !b.dataset.avacReset) return;
    let e = ler(); const id = b.id;
    if (b.dataset.avacReset) { if (typeof confirm === "function" && !confirm("Substituir todos os dados do AVAC pelo exemplo da planilha?")) return; e = padrao(); }
    if (add === "tip") e.tipologias.lista.push({ n:"Nova tipologia", q:0, area:0, dorm:0, banh:0, vagas:0 });
    if (add === "amb") e.ac.amb.push({ n:"Novo ambiente", area:0, dorm:0, override:null, equip:"Split hi-wall", matriz:true, q:[], comum:0 });
    if (add === "outro") e.vent.outros.push({ n:"Novo ambiente", area:0, pe:2.6, trocas:6 });
    if (add === "sis") e.dutos.sistemas.push({ nome:"Novo sistema", fonte:"", vazao:0, vel:8, reto:20, equiv:10, local:100, altura:300, tipo:"Duto principal — comercial" });
    if (add === "extra") (e.quadro.extras = e.quadro.extras || []).push({ nome:"Nova carga", kw:0, qtd:1 });
    if (del) { const [k, i] = del.split(":"), n = +i;
      if (k === "tip") { e.tipologias.lista.splice(n, 1); e.ac.amb.forEach(a => { if (Array.isArray(a.q)) a.q.splice(n, 1); }); }
      if (k === "amb") e.ac.amb.splice(n, 1); if (k === "outro") e.vent.outros.splice(n, 1); if (k === "sis") e.dutos.sistemas.splice(n, 1); if (k === "extra") e.quadro.extras.splice(n, 1); }
    gravar(e); desenhar(false); refocar(el(id) ? id : (del && del.indexOf("extra") === 0) ? "avac-b-add_extra" : "avac-sub-" + (ui.avacSub || "visao")); }); }

/* Quadro elétrico de AVAC — mostrado na aba Caixinha Physis IoT (fora do telaAvac). Mesmo estado e mesmas contas
   do AVAC: as cargas vêm da lista de equipamentos (ventiladores, splits de áreas comuns, apoio solar, piscina). */
function telaQuadroEletrico() { const e = comSol(ler()), R = calcular(e);
  return `<section aria-labelledby="h-avac-qf"><h2 id="h-avac-qf">Quadro elétrico de AVAC (QF-AVAC)</h2>
    <p class="t2 pq">Corrente de projeto, proteção, seção (capacidade, queda, curto-circuito, seccionamento e partida de motor), neutro, PE e alimentador — critérios da NBR 5410 em forma simplificada; não substitui o projeto elétrico. As cargas vêm da aba AVAC e térmico.</p>
    ${telaQuadro(e, R)}</section>`; }

window.AVAC = { calcular, padrao, migrar, planoCargas, aplicarCargas, versao:"PHYSIS_AVAC-5" };
window.telaAvac = telaAvac;   /* global: chamada pelo nome telaAvac() na hora de desenhar */
window.telaQuadroEletrico = telaQuadroEletrico;
})();
