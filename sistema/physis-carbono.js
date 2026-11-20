/* physis-carbono.js — Carbono: inventário de emissões pelo GHG Protocol (abordagem do Programa Brasileiro
   GHG Protocol), remoções e emissões evitadas à parte, metas net zero, preparação para o SBCE (Lei 15.042/2024)
   e potencial de créditos. Espelho das contas em physis_hub/carbono.py (testes de mesa).
   Contrato com a plataforma: define telaCarbono() (HTML da aba inteira, com um único título h1) e
   window.PhysisCarbono = { tela, calcular, migrar, ler, gravar, contexto, resumo, kwhAno, base }.
   Fatores: sistema/physis-fatores-emissao.json, embutido no painel como <script type="application/json"
   id="base-fatores-emissao"> (ferramentas/embutir_bases.py). Estado em localStorage "physis-carbono"
   (o formato antigo {kwh, diesel, glp, gn, solar_kwh, medidas} é lido e migrado).
   Globais usadas só na hora de desenhar: esc, n2, el, ui, desenhar; e, se existirem, os leitores dos outros
   módulos (perfilLer, rcLer, gLer, sbnLer, calcLer, solarCalc, RC_POR_ID, RC_BIOGAS, SBN, window.AVAC, ebAtual).
   Esgoto e biogás (Economia circular): ebAtual() da plataforma ou as chaves "physis-calc-esgoto" e "physis-calc-biogas"
   (Planejador ou SustainKit). Materiais da obra: chave "physis-calc-materiais" { composicoes:[{ id, nome, area_m2,
   kgco2e_m2, fonte }], zona, atualizado }. Fatores que ainda não estão na base ficam [MARCADOR] e não entram na soma:
   F.efluentes = { dbo_kg_pessoa_dia, bo_kg_ch4_kg_dbo, mcf:{ fossa_filtro, wetland, biodigestor, ete } } (IPCC 2006,
   vol. 5, cap. 6) e F.agua_fornecida = { kg_m3 } (água tratada da concessionária, para o reúso evitado).
   Normas citadas pelo nome; nenhum texto de norma copiado. */
(function () {
"use strict";
const CHAVE = "physis-carbono";
const SUBS = [["inventario","Inventário"],["e1","Escopo 1"],["e2","Escopo 2"],["e3","Escopo 3"],["remocoes","Remoções e evitadas"],["metas","Metas e net zero"],["sbce","SBCE e créditos"]];
const QUAL = [["medido","Medido (conta, nota, medidor)"],["estimado","Estimado"]];
const CAT3 = { 1:"Bens e serviços comprados", 2:"Bens de capital", 3:"Combustíveis e energia (fora dos escopos 1 e 2)", 4:"Transporte e distribuição a montante", 5:"Resíduos gerados na operação", 6:"Viagens a negócios", 7:"Deslocamento casa–trabalho", 8:"Ativos arrendados a montante", 9:"Transporte e distribuição a jusante", 10:"Processamento de produtos vendidos", 11:"Uso de produtos vendidos", 12:"Fim de vida dos produtos vendidos", 13:"Ativos arrendados a jusante", 14:"Franquias", 15:"Investimentos" };
const BIOMAS = [["amazonia","Amazônia"],["mata_atlantica","Mata Atlântica"],["cerrado","Cerrado"],["caatinga","Caatinga"],["pantanal","Pantanal"],["pampa","Pampa"],["saf","Sistema agroflorestal (SAF)"]];
const DESTINOS = [["aterro","Aterro sanitário"],["compostagem","Compostagem"],["biodigestor","Biodigestor"],["reciclagem","Reciclagem"],["incineracao","Incineração"],["nenhum","Reúso (sem emissão)"]];
const TIPOS_RES = [["rejeito","Rejeito misturado"],["alimentos","Restos de alimentos"],["poda","Poda e jardinagem"],["papel","Papel e papelão"],["madeira","Madeira"],["tecidos","Tecidos"],["pet","Plástico PET"],["pp_pead","Plástico PP/PEAD"],["vidro","Vidro"],["sucata","Metais"],["rcc","Entulho"]];
const NOMES_RC = { esterco_bov:"Esterco bovino", esterco_sui:"Dejetos suínos", cama_aviario:"Cama de aviário", colheita:"Resíduos de colheita", oleo_cozinha:"Óleo de cozinha usado", longa_vida:"Embalagem longa vida", filme:"Plástico filme", eps:"Isopor (EPS)", aluminio:"Alumínio", saude:"Resíduos de saúde", pneus:"Pneus" };
const ROTA_DESTINO = { aterro:["aterro",false], aterro1:["aterro",false], reciclagem:["reciclagem",false], reversa:["reciclagem",false], incineracao:["incineracao",false], compostagem:["compostagem",true], vermi:["compostagem",true], biodigestor:["biodigestor",true], biomassa:["queima",true] };
const RC_UN_F = { kg_mes:1, kg_sem:52 / 12, kg_dia:30, t_mes:1000, l_mes:0.92 };
const BIOG_PAD = { alimentos:0.10, esterco_bov:0.04, esterco_sui:0.06, cama_aviario:0.07, colheita:0.05 };
/* energia do biogás e do GLP: premissas biogas.pci e glp.pci da base (contas comuns, a mesma regra do SustainKit);
   fora da plataforma (sem o bloco), os mesmos valores da base: 6 kWh/m³ e 12,8 kWh/kg (espelho physis_hub/carbono.py) */
const PREM = (id, pad) => { try { const v = typeof PhysisCalc !== "undefined" ? PhysisCalc.premissa(id) : null; return typeof v === "number" ? v : pad; } catch (e) { return pad; } };
const PCI_BIOGAS = () => PREM("biogas.pci", 6), PCI_GLP = () => PREM("glp.pci", 12.8);
const BIO = ["biodiesel","etanol_anidro","etanol_hidratado","lenha","carvao_vegetal"], BOVINOS = ["gado_corte","gado_leite","bufalo"];

/* ════════ utilitários ════════ */
const E = s => typeof esc === "function" ? esc(s) : String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));
const N = (v, c) => typeof n2 === "function" ? n2(v, c) : Number(v).toLocaleString("pt-BR", { minimumFractionDigits:c, maximumFractionDigits:c });
const T = v => v == null || !isFinite(v) ? "—" : N(v, Math.abs(v) < 100 ? 2 : 1);
const P = v => v == null || !isFinite(v) ? "—" : Math.round(v * 100) + "%";
const UI = () => typeof ui !== "undefined" && ui ? ui : (window.__carbUi = window.__carbUi || { mem:{} });
const pegar = id => typeof el === "function" ? el(id) : document.getElementById(id);
/* número digitado: "1.234,5", "0.0385" e "1.000" (= mil) */
function num(v){ if (v == null) return null; if (typeof v === "number") return isFinite(v) ? v : null; let s = String(v).trim().replace(/\s/g, ""); if (!s) return null;
  if (s.indexOf(",") >= 0) s = s.replace(/\./g, "").replace(",", "."); else if (/^-?\d{1,3}(\.\d{3})+$/.test(s)) s = s.replace(/\./g, "");
  const x = Number(s); return isFinite(x) ? x : null; }
const n0 = v => { const x = num(v); return x == null ? 0 : x; };
const clone = o => JSON.parse(JSON.stringify(o));
const lerLS = (k, pad) => { const u = UI(); if (u.vazia) return pad; try { const v = JSON.parse(localStorage.getItem(k) || "null"); return v == null ? pad : v; } catch (e){ return pad; } };

function base(){ if (base.c) return base.c; let b = null;
  try { const s = typeof document !== "undefined" && document.getElementById("base-fatores-emissao"); if (s) b = JSON.parse(s.textContent); } catch (e){}
  if (!b && typeof window !== "undefined" && window.PHYSIS_FATORES_EMISSAO) b = window.PHYSIS_FATORES_EMISSAO;
  if (b) base.c = b; return b; }

/* ════════ contas (mesmas de physis_hub/carbono.py) ════════ */
const gwpDe = (F, v) => F.gwp[v] || F.gwp[F.gwp.padrao];
const tco2e = (gases, gw) => Object.keys(gases).reduce((s, g) => s + gases[g] * (gw[g] || 0), 0) / 1000;
function combustao(F, comb, qtd, uso, teorBio, naoRenov){ const C = F.combustiveis, M = F.misturas, partes = [];
  if (M[comb] && typeof M[comb] === "object" && M[comb].fossil){ const m = M[comb], t = teorBio == null ? m.teor_bio : teorBio; partes.push([m.fossil, qtd * (1 - t)]); if (m.bio) partes.push([m.bio, qtd * t]); }
  else partes.push([comb, qtd]);
  const g = {}; let bio = 0; const ad = (k, v) => { g[k] = (g[k] || 0) + v; };
  partes.forEach(([cid, q]) => { const c = C[cid]; if (!c) return; const tj = q * c.mj / 1e6, e = c[uso] || c.estacionaria, ehBio = BIO.indexOf(cid) >= 0; let cb = tj * (c.co2_bio || 0);
    if (naoRenov && ehBio){ ad("CO2", cb); cb = 0; } ad("CO2", tj * (c.co2 || 0)); ad(ehBio ? "CH4_bio" : "CH4_fossil", tj * e.ch4); ad("N2O", tj * e.n2o); bio += cb; });
  return [g, bio]; }
function refrigerante(F, gas, kg){ const r = F.refrigerantes[gas]; if (!r) return [{}, true]; const g = {}; Object.keys(r.gases).forEach(k => { g[k] = kg * r.gases[k]; }); return [g, !!r.quioto]; }
function rebanho(F, tipo, cab){ const A = F.agro, r = A.rebanho[tipo], p = A.pastagem; if (!r) return {};
  const ef3 = BOVINOS.indexOf(tipo) >= 0 ? p.ef3_prp_bovinos : p.ef3_prp_outros, nex = r.nex_kg_n_1000kg_dia * r.peso_kg / 1000 * 365 * cab;
  return { CH4_bio: cab * (r.enterica_ch4 + r.dejetos_ch4), N2O: nex * (ef3 + p.frac_gasm * p.ef4 + p.frac_leach * p.ef5) * 44 / 28 }; }
function fertilizante(F, kgN, ureia, calc, dolo){ const A = F.agro, f = A.fertilizante, nt = kgN + ureia * A.teor_n_ureia;
  return { CO2: (ureia * A.ureia_tc_por_t + calc * A.calcario_tc_por_t + dolo * A.dolomita_tc_por_t) * 44 / 12, N2O: nt * (f.ef1 + f.frac_gasf * f.ef4 + f.frac_leach * f.ef5) * 44 / 28 }; }
const usoSolo = (F, ha, bioma) => ({ CO2: ha * (F.uso_solo.estoque_tco2_ha[bioma] || 0) / F.uso_solo.anos_amortizacao * 1000 });
function residuo(F, tipo, t, destino){ const R = F.residuos;
  if (destino === "aterro"){ const a = R.aterro, doc = R.doc[tipo] != null ? R.doc[tipo] : R.doc._padrao; return { CH4_bio: t * doc * a.docf * a.mcf * a.f * 16 / 12 * (1 - a.r) * (1 - a.ox) * 1000 }; }
  if (destino === "compostagem" || destino === "biodigestor"){ const x = R[destino]; return { CH4_bio: t * x.ch4 * 1000, N2O: t * x.n2o * 1000 }; }
  if (destino === "reciclagem") return { CO2: t * R.reciclagem_tco2e_t * 1000 };
  if (destino === "incineracao"){ const i = R.incineracao_tco2_t; return { CO2: t * (i[tipo] != null ? i[tipo] : i._padrao) * 1000 }; }
  if (destino === "queima") return combustao(F, "lenha", t * 1000, "estacionaria")[0];
  return {}; }
function fatorRede(F, escolha, manual){ const m = num(manual); if (m != null && m >= 0) return m; const A = F.rede.anual; return (A[escolha] || A[F.rede.padrao]).valor; }
function redeMercado(kwh, fRes, irec, contratos){ const mwh = kwh / 1000; let t = 0, cob = Math.min(irec || 0, mwh);
  (contratos || []).forEach(([cm, cf]) => { const x = Math.min(cm, Math.max(0, mwh - cob)); t += x * cf; cob += x; }); return t + Math.max(0, mwh - cob) * fRes; }
function remocoes(F, ha, bioma, idade){ const R = F.remocoes; let tx = R.tco2_ha_ano[bioma] || 0; if (idade > R.anos_crescimento_rapido) tx *= R.fator_depois; return ha * tx; }
function fatorDesloc(F, modo, gw){ const d = F.escopo3.deslocamento[modo]; if (!d) return 0; if (d.km_por_l) return tco2e(combustao(F, d.combustivel, 1, "movel")[0], gw) * 1000 / d.km_por_l; return d.kg; }
const sbceSit = (F, e1) => e1 > F.sbce.limite_obrigacao_t ? "obrigacao" : e1 > F.sbce.limite_relato_t ? "relato" : "voluntario";
function incerteza(l){ const tot = l.reduce((s, x) => s + x[0], 0); return tot > 0 ? Math.sqrt(l.reduce((s, x) => s + Math.pow(x[0] * x[1], 2), 0)) / tot : null; }
/* pegada do servidor (sistema digital): mesma regra de carbono.servidor_contagem e servidor_inventario */
const svContagem = (eq, escolha) => escolha === "ja_contado" || escolha === "somar" ? escolha : (eq.local === "fora" ? "somar" : "ja_contado");
function servidorInventario(eqs, fLoc, escolha, cats){ const tem = k => !cats || cats.indexOf(k) >= 0, out = { linhas:[], e2_t:0, e3_cat1_t:0, cat2_t:0, ja_contado_t:0 };
  (eqs || []).forEach(eq => { const t = n0(eq.kwh_ano) / 1000 * fLoc, q = eq.qualidade === "medido" ? "medido" : "estimado", nome = String(eq.nome || "Servidor");
    if (svContagem(eq, escolha) === "ja_contado") out.ja_contado_t += t;
    else if (eq.controle === "servico"){ if (tem(1)){ out.e3_cat1_t += t; out.linhas.push({ escopo:3, cat:1, fonte:nome + " (hospedagem comprada)", t, q }); } }
    else { out.e2_t += t; out.linhas.push({ escopo:2, cat:null, fonte:nome + " (energia do servidor)", t, q }); }
    const fab = n0(eq.t_ano_fabricacao); if (fab && tem(2)){ out.cat2_t += fab; out.linhas.push({ escopo:3, cat:2, fonte:nome + " (fabricação, amortizada)", t:fab, q:"estimado" }); } });
  return out; }
/* dados do hub (GET /api/servidor/pegada); sem servidor = exemplo da demonstração, que nunca entra no inventário */
const SV = { dados:null, quando:0, pedido:false, erro:null };
const temServidorWeb = () => { try { return /^https?:$/.test(location.protocol); } catch (e){ return false; } };
function svCarregar(){ if (!temServidorWeb() || SV.pedido || typeof fetch !== "function") return; if (SV.dados && Date.now() - SV.quando < 300000) return; if (SV.erro && Date.now() - SV.quando < 300000) return;
  SV.pedido = true; fetch("/api/servidor/pegada", { credentials:"same-origin", cache:"no-store" }).then(r => r.json().then(j => [r.status, j], () => [r.status, {}]))
    .then(([st, j]) => { SV.pedido = false; SV.quando = Date.now(); if (j && j.ok && j.modo === "hub"){ SV.dados = j; SV.erro = null; } else SV.erro = st; redesenhar(); })
    .catch(() => { SV.pedido = false; SV.quando = Date.now(); SV.erro = "rede"; }); }
const SV_DEMO = { ok:true, modo:"demo", fator_rede:null, equipamentos:[
  { nome:"Hub (Raspberry Pi 5)", classe_nome:"Raspberry Pi 5 (com fonte, ventoinha e SSD)", local:"no_lugar", controle:"proprio", metodo:"nominal", qualidade:"estimado", w_agora:6, kwh_mes:4.4, kwh_ano:52.6, kg_fabricacao:20, vida_anos:5, t_ano_fabricacao:0.004 },
  { nome:"Servidor de IA (2 placas de vídeo)", classe_nome:"Servidor com GPU para IA", local:"no_lugar", controle:"proprio", metodo:"nominal+gpu", qualidade:"parcial", w_agora:180, kwh_mes:131, kwh_ano:1577, kg_fabricacao:1600, vida_anos:4, t_ano_fabricacao:0.4 }],
  dicas:[] };
const anoNetZero = (anoBase, pct, resid) => pct > 0 ? anoBase + Math.ceil((1 - resid) / (pct / 100) - 1e-9) : null;

/* ════════ estado salvo ════════ */
function padrao(){ return { v:2, ano:String(new Date().getFullYear() - 1), gwp:"", area_m2:"", kwh:"", solar_kwh:"",
  rede:{ fator:"", fator_manual:"", usar_mensal:false, mensal:["","","","","","","","","","","",""], irec_mwh:"", contratos:[], q:"medido" },
  estac:[], movel:[], movel_auto:true, refrig:[], proc:[], rebanho:[], fert:{ n_kg:"", ureia_kg:"", calcario_kg:"", dolomita_kg:"", q:"estimado" }, solo:{ ativo:false, ha:"", bioma:"mata_atlantica" },
  e3:{ cats:[1,4,5,6,7], gastos:[], materiais:[], mat_auto:true, capital:"", transp:[], res_auto:true, residuos:[], viagens:[], desloc:[], fim:[], outras:[] },
  remo:{ bioma:"mata_atlantica", ha:"", idade:"", usar_sbn:true },
  metas:{ ano_base:"", base_t:"", alvo:"2050", pct:"", incluir_e3:false, medidas:[] },
  sbce:{ inventario:false, responsavel:false, plano:false, dados:false, relato:false, verif:false, registro:false },
  servidor:{ incluir:true, contagem:"auto" } }; }
function mesclar(a, b){ Object.keys(b || {}).forEach(k => { const v = b[k]; if (v && typeof v === "object" && !Array.isArray(v) && a[k] && typeof a[k] === "object" && !Array.isArray(a[k])) mesclar(a[k], v); else a[k] = v; }); return a; }
/* formato antigo (até 11/2026): { kwh, diesel, glp, gn, solar_kwh, medidas:[{n,t}] } */
function migrar(c){ c = c && typeof c === "object" ? c : {}; if (c.v === 2) return mesclar(padrao(), clone(c));
  const p = padrao(); p.kwh = c.kwh || ""; p.solar_kwh = c.solar_kwh || "";
  [["diesel","diesel_b"],["glp","glp"],["gn","gas_natural"]].forEach(([k, comb]) => { if (num(c[k])) p.estac.push({ comb, qtd:String(c[k]), q:"estimado" }); });
  p.metas.medidas = Array.isArray(c.medidas) ? c.medidas.slice() : []; return p; }
function ler(){ const u = UI(); let c = null; if (u.vazia) c = (u.mem || {}).carb || null; else { try { c = JSON.parse(localStorage.getItem(CHAVE) || "null"); } catch (e){} } return migrar(c); }
function gravar(c){ const u = UI(); c.v = 2; if (u.vazia){ u.mem = u.mem || {}; u.mem.carb = c; return; } try { localStorage.setItem(CHAVE, JSON.stringify(c)); } catch (e){} }

/* ════════ dados dos outros módulos ════════ */
function contexto(c){ c = c || ler(); const ctx = {}, ano = String(c.ano || "");
  const perfil = typeof perfilLer === "function" ? perfilLer() : Object.assign({ c:{}, historico:[] }, lerLS("physis-perfil", {}));
  const hist = (perfil.historico || []).filter(x => x.mes && num(x.kwh) != null).sort((a, b) => a.mes.localeCompare(b.mes));
  const doAno = hist.filter(x => x.mes.slice(0, 4) === ano);
  if (doAno.length === 12){ ctx.kwh_ano = doAno.reduce((s, x) => s + num(x.kwh), 0); ctx.kwh_mes = doAno.map(x => num(x.kwh)); ctx.kwh_fonte = "12 contas de " + ano + " no Início"; }
  else { const u = hist.slice(-12); if (u.length){ ctx.kwh_ano = u.reduce((s, x) => s + num(x.kwh), 0) * 12 / u.length; ctx.kwh_fonte = "média das " + u.length + " últimas contas do Início, levada a 12 meses"; } }
  const pc = perfil.c || {}; ctx.area_m2 = num(pc.area_construida); ctx.colaboradores = num(pc.colaboradores); ctx.nome = pc.razao_social || pc.nome_fantasia || pc.unidade_nome || pc.nome || "";
  ctx.rc = typeof rcLer === "function" ? rcLer() : lerLS("physis-residuos-plano", []); if (!Array.isArray(ctx.rc)) ctx.rc = [];
  const reg = k => { const r = lerLS(k, null); return r && typeof r === "object" && !Array.isArray(r) && (r.fonte || num(r.pessoas) != null || num(r.biogas_m3_dia) != null) ? r : null; };
  try { const eb = typeof ebAtual === "function" ? ebAtual() : null; ctx.esgoto = eb ? eb.esgoto : reg("physis-calc-esgoto"); ctx.biogas = eb ? eb.biogas : reg("physis-calc-biogas"); } catch (e){}
  const mt = lerLS("physis-calc-materiais", null); if (mt && typeof mt === "object" && Array.isArray(mt.composicoes)) ctx.materiais = mt;
  const g = typeof gLer === "function" ? gLer() : Object.assign({ producao:[], compras:[] }, lerLS("physis-gestao-cliente", {}));
  const prod = (g.producao || []).filter(x => x.mes && num(x.prod)).sort((a, b) => a.mes.localeCompare(b.mes)).slice(-12);
  if (prod.length){ ctx.producao = prod.reduce((s, x) => s + num(x.prod), 0) * 12 / prod.length; ctx.producao_un = (prod.find(x => x.un) || {}).un || "unidade"; }
  const comb = (g.producao || []).filter(x => x.mes && num(x.comb)).sort((a, b) => a.mes.localeCompare(b.mes)).slice(-12); if (comb.length) ctx.comb_l = comb.reduce((s, x) => s + num(x.comb), 0) * 12 / comb.length;
  const hoje = new Date(), lim = new Date(hoje.getFullYear() - 1, hoje.getMonth(), hoje.getDate()).toISOString().slice(0, 10), pagas = (g.compras || []).filter(x => (x.sit === "Comprado" || x.sit === "Pago") && String(x.data || "") >= lim);
  ctx.compras_rs = pagas.filter(x => x.cat !== "Investimento").reduce((s, x) => s + n0(x.valor), 0); ctx.capital_rs = pagas.filter(x => x.cat === "Investimento").reduce((s, x) => s + n0(x.valor), 0);
  const sbn = typeof sbnLer === "function" ? sbnLer() : Object.assign({ plano:[] }, lerLS("physis-sbn", {}));
  const plantas = typeof SBN !== "undefined" && SBN && SBN.plantas ? SBN.plantas : [];
  ctx.mudas_sbn = (sbn.plano || []).reduce((s, x) => { const p = plantas.find(y => String(y.n) === String(x.n)); return s + (!plantas.length || (p && ["medio","alto","emergente"].indexOf(p.estrato) >= 0) ? n0(x.qtd) : 0); }, 0);
  try { if (window.AVAC && typeof calcLer === "function"){ const o = calcLer("avac"), e = o && o.e ? o.e : null; if (e){ const R = window.AVAC.calcular(e); if (R && R.ac && R.ac.kWt > 0) ctx.avac_kwt = R.ac.kWt; } } } catch (e){}
  /* Solar, Secador e Turbinas entram sozinhos nas evitadas (R4, 15/11/2026), só quando o módulo tem projeto salvo (nada de usina hipotética) */
  try { const so = typeof calcLer === "function" ? calcLer("solar") : null; if (so && (num(so.consumo) > 0 || num(so.kwp) > 0) && typeof solarCalc === "function"){ const s = solarCalc(); if (s && s.ger > 0) ctx.solar_kwh = s.ger; } } catch (e){}
  try { const se = typeof calcLer === "function" ? calcLer("secador") : null, d = se && se.dim; if (d && num(d.massa) > 0 && window.SECADOR && SECADOR.dimensionar){ const r = SECADOR.dimensionar(Object.assign({}, d, { lenha_nao_renovavel: !!d.lenha_nr })); if (r && r.co2_eletrico_kg_ano > 0) ctx.secador_co2_kg = r.co2_eletrico_kg_ano; } } catch (e){}
  /* Frota e combustível (18/11/2026): litros MEDIDOS (abastecimentos do ano, ou a vazão) por combustível; a frota simulada nunca vem */
  try { if (window.FROTA && FROTA.paraCarbono){ const fm = FROTA.paraCarbono(ano); if (Array.isArray(fm) && fm.length) ctx.frota_movel = fm; } } catch (e){}
  try { if (window.TURBINAS && TURBINAS.kwhAnoPlanejado){ const k = TURBINAS.kwhAnoPlanejado(); if (k > 0) ctx.turbinas_kwh = k; } } catch (e){}
  if (SV.dados && SV.dados.modo === "hub" && Array.isArray(SV.dados.equipamentos)) ctx.servidor = SV.dados.equipamentos;
  return ctx; }
/* kWh do ano sem chamar solarCalc (que pode chamar de volta o Carbono): campo do Carbono ou contas do Início */
const kwhAno = c => { c = migrar(c || ler()); const k = num(c.kwh); if (k != null) return k; const ano = String(c.ano || "");
  const perfil = typeof perfilLer === "function" ? perfilLer() : Object.assign({ historico:[] }, lerLS("physis-perfil", {})), h = (perfil.historico || []).filter(x => x.mes && num(x.kwh) != null).sort((a, b) => a.mes.localeCompare(b.mes));
  const doAno = h.filter(x => x.mes.slice(0, 4) === ano), u = doAno.length === 12 ? doAno : h.slice(-12); return u.length ? u.reduce((s, x) => s + num(x.kwh), 0) * (doAno.length === 12 ? 1 : 12 / u.length) : null; };
const nomeRes = t => typeof RC_POR_ID !== "undefined" && RC_POR_ID[t] ? RC_POR_ID[t].nome : (NOMES_RC[t] || (TIPOS_RES.find(x => x[0] === t) || [t, t])[1]);
const nomeComb = (F, k) => (F.misturas[k] && F.misturas[k].nome) || (F.combustiveis[k] && F.combustiveis[k].nome) || k;
const unComb = (F, k) => (F.misturas[k] && F.misturas[k].unidade) || (F.combustiveis[k] && F.combustiveis[k].unidade) || "";

/* ════════ inventário completo ════════ */
function calcular(estado, ctx, F){ F = F || base(); if (!F) return null; ctx = ctx || {};
  const c = migrar(estado), gwv = c.gwp || F.gwp.padrao, gw = gwpDe(F, gwv), U = F.incerteza, linhas = [];
  const add = (escopo, grupo, fonte, gases, q, tf, bio, cat, fora, ref) => { const qq = q === "medido" ? "medido" : "estimado";
    linhas.push({ escopo, grupo, fonte, gases, t: tco2e(gases, gw), bio_t:(bio || 0) / 1000, q:qq, u: Math.hypot(U.dado[qq], U.fator[tf] != null ? U.fator[tf] : 0.5), cat: cat || null, fora: !!fora, ref: ref || null }); };
  c.estac.forEach((x, i) => { const tp = num(x.teor_pct), [g, b] = combustao(F, x.comb, n0(x.qtd), "estacionaria", tp == null ? null : tp / 100, !!x.nr); add(1, "estacionaria", nomeComb(F, x.comb), g, x.q, "combustivel", b, null, false, "estac." + i); });
  /* combustão móvel: o medido na aba Frota e combustível vale sobre o digitado (o digitado fica de reserva); espelho de carbono.py */
  const medFrota = Array.isArray(ctx.frota_movel) && ctx.frota_movel.length && c.movel_auto !== false;
  (medFrota ? ctx.frota_movel : c.movel).forEach((x, i) => { const tp = num(x.teor_pct), [g, b] = combustao(F, x.comb, n0(x.qtd), "movel", tp == null ? null : tp / 100, false); add(1, "movel", nomeComb(F, x.comb) + (medFrota ? " · " + (x.fonte || "Frota e combustível") : ""), g, medFrota ? "medido" : x.q, "combustivel", b, null, false, (medFrota ? "frota." : "movel.") + i); });
  c.refrig.forEach((x, i) => { const vz = F.vazamento[x.equip] || F.vazamento.split, tx = num(x.taxa_pct) != null ? num(x.taxa_pct) / 100 : vz.taxa, kg = x.modo === "carga" ? n0(x.carga) * tx : n0(x.kg);
    const [g, quioto] = refrigerante(F, x.gas, kg); add(1, "fugitivas", (F.refrigerantes[x.gas] || {}).nome || x.gas, g, x.q, "refrigerante", 0, null, !quioto, "refrig." + i); });
  c.proc.forEach((x, i) => { const g = {}; g[x.gas || "CO2"] = n0(x.kg); add(1, "processos", x.nome || "Processo", g, x.q, "processo", 0, null, false, "proc." + i); });
  c.rebanho.forEach((x, i) => add(1, "agropecuaria", (F.agro.rebanho[x.tipo] || {}).nome || x.tipo, rebanho(F, x.tipo, n0(x.cab)), x.q, "agro", 0, null, false, "rebanho." + i));
  const fe = c.fert; if (["n_kg","ureia_kg","calcario_kg","dolomita_kg"].some(k => n0(fe[k]))) add(1, "agropecuaria", "Adubo nitrogenado, ureia e calcário", fertilizante(F, n0(fe.n_kg), n0(fe.ureia_kg), n0(fe.calcario_kg), n0(fe.dolomita_kg)), fe.q, "agro", 0, null, false, "fert");
  if (c.solo.ativo && n0(c.solo.ha)) add(1, "uso_solo", "Mudança de uso do solo (" + ((BIOMAS.find(b => b[0] === c.solo.bioma) || ["", c.solo.bioma])[1]) + ")", usoSolo(F, n0(c.solo.ha), c.solo.bioma), "estimado", "solo", 0, null, false, "solo");
  const e3 = c.e3, cats = (e3.cats || []).map(Number), tem = k => cats.indexOf(k) >= 0;
  if (e3.res_auto !== false) (ctx.rc || []).forEach((r, i) => { const rd = ROTA_DESTINO[r.rota] || ["nenhum", true], tAno = n0(r.qtd) * (RC_UN_F[r.un] || 1) * 12 / 1000, g = residuo(F, r.tipo, tAno, rd[0]);
    if (!Object.keys(g).length) return; if (rd[1]) add(1, "residuos_no_lugar", nomeRes(r.tipo) + " · " + DESTINOS.concat([["queima","Queima para energia"]]).find(d => d[0] === rd[0])[1].toLowerCase() + " no lugar", g, "estimado", "residuos", 0, null, false, "rc." + i);
    else if (tem(5)) add(3, "residuos", nomeRes(r.tipo) + " · " + DESTINOS.find(d => d[0] === rd[0])[1].toLowerCase(), g, "estimado", "residuos", 0, 5, false, "rc." + i); });
  /* tratamento de esgoto no lugar (Economia circular · Esgoto e biogás): escopo 1, só com o fator na base */
  const es = ctx.esgoto, pesEsg = es ? n0(es.pessoas) : 0, EF = F.efluentes; let esgoto = null;
  if (pesEsg > 0){ const trat = es.tratamento || "", mcf = EF && EF.mcf ? num(EF.mcf[trat]) : null, dbo = EF ? num(EF.dbo_kg_pessoa_dia) : null, bo = EF ? num(EF.bo_kg_ch4_kg_dbo) : null;
    if (mcf != null && dbo != null && bo != null){ const kg = pesEsg * dbo * 365 * bo * mcf; add(1, "esgoto_no_lugar", "Tratamento de esgoto no lugar", { CH4_bio: kg }, "estimado", "residuos", 0, null, false, "esgoto"); esgoto = { marcador:false, pessoas:pesEsg, tratamento:trat, kg_ch4:kg, fonte:es.fonte || "" }; }
    else esgoto = { marcador:true, pessoas:pesEsg, tratamento:trat, fonte:es.fonte || "" }; }
  if (tem(5)) e3.residuos.forEach((x, i) => add(3, "residuos", nomeRes(x.tipo) + " · " + ((DESTINOS.find(d => d[0] === x.destino) || ["", x.destino])[1]).toLowerCase(), residuo(F, x.tipo, n0(x.t), x.destino), x.q, "residuos", 0, 5, false, "e3.residuos." + i));
  /* escopo 2 */
  const kwh = num(c.kwh) != null ? num(c.kwh) : (ctx.kwh_ano != null ? ctx.kwh_ano : null), fLoc = fatorRede(F, c.rede.fator, c.rede.fator_manual);
  const mens = (c.rede.mensal || []).map(num), usaMes = !!c.rede.usar_mensal && mens.length === 12 && mens.every(v => v != null) && num(c.kwh) == null && ctx.kwh_mes && ctx.kwh_mes.length === 12;
  let e2loc = usaMes ? ctx.kwh_mes.reduce((s, k, i) => s + k / 1000 * mens[i], 0) : (kwh || 0) / 1000 * fLoc;
  let e2mkt = redeMercado(kwh || 0, fLoc, n0(c.rede.irec_mwh), (c.rede.contratos || []).map(k => [n0(k.mwh), n0(k.fator)]));
  if (kwh) add(2, "rede", "Eletricidade da rede (localização" + (usaMes ? ", fatores mensais" : "") + ")", { CO2: e2loc * 1000 }, c.rede.q || "medido", "rede", 0, null, false, "rede");
  /* pegada do servidor: só com dado do hub (nunca com o exemplo da demonstração) */
  const svc = c.servidor || {}; let sv = null;
  if (ctx.servidor && svc.incluir !== false){ sv = servidorInventario(ctx.servidor, fLoc, svc.contagem || "auto", cats);
    sv.linhas.forEach((x, i) => add(x.escopo, x.escopo === 2 ? "servidor" : x.cat === 2 ? "servidor_fabricacao" : "servidor_hospedagem", x.fonte, { CO2: x.t * 1000 }, x.q, x.escopo === 2 ? "rede" : "escopo3", 0, x.cat, false, "servidor." + i));
    e2loc += sv.e2_t; e2mkt += sv.e2_t; }
  /* escopo 3 */
  const G3 = F.escopo3;
  if (tem(1)){ e3.gastos.forEach((x, i) => add(3, "compras", (G3.gasto_kg_por_real[x.cat] || { nome:"Compras" }).nome + " (por gasto)", { CO2: n0(x.valor) * ((G3.gasto_kg_por_real[x.cat] || {}).kg || 0) }, "estimado", "gasto", 0, 1, false, "e3.gastos." + i));
    e3.materiais.forEach((x, i) => add(3, "compras", (G3.materiais_kg_por_kg[x.mat] || { nome:"Material" }).nome, { CO2: n0(x.kg) * ((G3.materiais_kg_por_kg[x.mat] || {}).kg || 0) }, x.q, "escopo3", 0, 1, false, "e3.materiais." + i)); }
  /* carbono incorporado das composições escolhidas no SustainKit ou no Planejador (área × kgCO₂e/m²); sem o valor por m², [MARCADOR] */
  const matFalta = [], comps = ctx.materiais ? ctx.materiais.composicoes : [];
  if (tem(1) && e3.mat_auto !== false) (comps || []).forEach((m, i) => { if (!m || typeof m !== "object") return; const a = num(m.area_m2), k = num(m.kgco2e_m2), nome = String(m.nome || m.id || "Composição");
    if (!(a > 0)) return; if (k == null){ matFalta.push(nome); return; } add(3, "materiais_obra", nome, { CO2: a * k }, "estimado", "escopo3", 0, 1, false, "mat." + i); });
  if (tem(2) && n0(e3.capital)) add(3, "bens_capital", "Bens de capital (por gasto)", { CO2: n0(e3.capital) * G3.gasto_kg_por_real.manufaturados.kg }, "estimado", "gasto", 0, 2, false, "e3.capital");
  e3.transp.forEach((x, i) => { const k = Number(x.cat) || 4; if (tem(k)) add(3, "transporte", (G3.transporte_tkm[x.modo] || { nome:"Transporte" }).nome, { CO2: n0(x.tkm) * ((G3.transporte_tkm[x.modo] || {}).kg || 0) }, x.q, "escopo3", 0, k, false, "e3.transp." + i); });
  if (tem(6)) e3.viagens.forEach((x, i) => add(3, "viagens", (G3.viagens_pkm[x.modo] || { nome:"Viagem" }).nome, { CO2: n0(x.pkm) * ((G3.viagens_pkm[x.modo] || {}).kg || 0) }, x.q, "escopo3", 0, 6, false, "e3.viagens." + i));
  if (tem(7)) e3.desloc.forEach((x, i) => add(3, "deslocamento", (G3.deslocamento[x.modo] || { nome:"Deslocamento" }).nome, { CO2: n0(x.pessoas) * n0(x.km) * n0(x.dias) * fatorDesloc(F, x.modo, gw) }, "estimado", "escopo3", 0, 7, false, "e3.desloc." + i));
  if (tem(12)) e3.fim.forEach((x, i) => add(3, "fim_de_vida", nomeRes(x.tipo) + " vendido · " + ((DESTINOS.find(d => d[0] === x.destino) || ["", x.destino])[1]).toLowerCase(), residuo(F, x.tipo, n0(x.t), x.destino), "estimado", "residuos", 0, 12, false, "e3.fim." + i));
  e3.outras.forEach((x, i) => { const k = Number(x.cat); if (tem(k)) add(3, "outras", x.nome || CAT3[k], { CO2: n0(x.t) * 1000 }, x.q, "escopo3", 0, k, false, "e3.outras." + i); });
  /* totais */
  const soma = esc => linhas.filter(l => l.escopo === esc && !l.fora).reduce((s, l) => s + l.t, 0), e1 = soma(1), e3t = soma(3), total = e1 + e2loc + e3t;
  const porGas = { CO2:0, CH4:0, N2O:0, HFC:0, SF6:0 }; linhas.filter(l => !l.fora).forEach(l => Object.keys(l.gases).forEach(g => { const k = g.indexOf("CH4") === 0 ? "CH4" : g.indexOf("HFC") === 0 ? "HFC" : g; porGas[k] = (porGas[k] || 0) + l.gases[g] * (gw[g] || 0) / 1000; }));
  const porGrupo = {}; linhas.filter(l => !l.fora).forEach(l => { porGrupo[l.grupo] = (porGrupo[l.grupo] || 0) + l.t; });
  const porCat = {}; linhas.filter(l => l.escopo === 3 && !l.fora).forEach(l => { porCat[l.cat] = (porCat[l.cat] || 0) + l.t; });
  const tMed = linhas.filter(l => !l.fora && l.q === "medido").reduce((s, l) => s + l.t, 0);
  /* remoções e evitadas: sempre à parte */
  const haSbn = c.remo.usar_sbn !== false ? n0(ctx.mudas_sbn) / F.remocoes.mudas_por_ha : 0, ha = n0(c.remo.ha) + haSbn, rem = ha ? remocoes(F, ha, c.remo.bioma, n0(c.remo.idade)) : 0;
  /* biogás: o registro da parte Esgoto e biogás (Planejador, SustainKit ou estimativa, que já soma os resíduos do plano com a
     rota Biodigestor) substitui a soma do plano, para não contar duas vezes */
  const bioR = ctx.biogas && num(ctx.biogas.biogas_m3_dia) != null ? ctx.biogas : null;
  const glpKg = tco2e(combustao(F, "glp", 1, "estacionaria")[0], gw), biogM3 = bioR ? num(bioR.biogas_m3_dia) * 365 : (ctx.rc || []).filter(r => r.rota === "biodigestor").reduce((s, r) => s + n0(r.qtd) * (RC_UN_F[r.un] || 1) * 12 * ((typeof RC_BIOGAS !== "undefined" ? RC_BIOGAS : BIOG_PAD)[r.tipo] || 0.05), 0);
  const reusoM3 = ctx.esgoto ? n0(ctx.esgoto.reuso_m3_dia) * 365 : 0, fAgua = F.agua_fornecida ? num(F.agua_fornecida.kg_m3) : null;
  const recic = (ctx.rc || []).filter(r => (ROTA_DESTINO[r.rota] || [])[0] === "reciclagem").reduce((s, r) => { const t = n0(r.qtd) * (RC_UN_F[r.un] || 1) * 12 / 1000; return s + Math.max(0, tco2e(residuo(F, r.tipo, t, "aterro"), gw) - tco2e(residuo(F, r.tipo, t, "reciclagem"), gw)); }, 0);
  const evit = { solar: (num(c.solar_kwh) != null ? n0(c.solar_kwh) : (c.solar_auto !== false ? n0(ctx.solar_kwh) : 0)) / 1000 * fLoc, secador: n0(ctx.secador_co2_kg) / 1000, turbinas: n0(ctx.turbinas_kwh) / 1000 * fLoc, biogas: biogM3 * PCI_BIOGAS() / PCI_GLP() * glpKg, reciclagem: recic, reuso: fAgua != null ? reusoM3 * fAgua / 1000 : 0 };
  /* intensidade, metas, SBCE */
  const area = num(c.area_m2) != null ? num(c.area_m2) : ctx.area_m2, opera = e1 + e2loc;
  const M = c.metas, anoBase = num(M.ano_base) || num(c.ano) || new Date().getFullYear() - 1, baseT = num(M.base_t) != null ? num(M.base_t) : (M.incluir_e3 ? total : opera);
  const pct = num(M.pct) != null ? num(M.pct) : F.metas.reducao_ano_pct_referencia, alvo = num(M.alvo) || 2050, trajet = [];
  for (let a = anoBase; a <= Math.max(anoBase, alvo); a++) trajet.push([a, baseT * Math.max(0, 1 - pct / 100 * (a - anoBase))]);
  const medT = (M.medidas || []).reduce((s, m) => s + n0(m.t), 0);
  return { c, gwp:gwv, linhas, e1, e2_loc:e2loc, e2_mkt:e2mkt, e3:e3t, total, opera, porGas, porGrupo, porCat, kwh, kwh_fonte: num(c.kwh) != null ? "informado no Carbono" : ctx.kwh_fonte || "", fator_rede:fLoc, usa_mensal:usaMes,
    bio_t: linhas.reduce((s, l) => s + l.bio_t, 0), fora_t: linhas.filter(l => l.fora).reduce((s, l) => s + l.t, 0), medido: total ? tMed / total : null,
    incerteza: incerteza(linhas.filter(l => !l.fora).map(l => [l.t, l.u])), remocoes_t: rem, remocoes_ha: ha, ha_sbn: haSbn, evitadas: evit, evitadas_t: evit.solar + evit.secador + evit.turbinas + evit.biogas + evit.reciclagem + evit.reuso, biogas_m3: biogM3, biogas_fonte: bioR ? String(bioR.fonte || "") : "", reuso_m3: reusoM3, reuso_marcador: reusoM3 > 0 && fAgua == null, esgoto, mat_falta: matFalta,
    area, int_m2: area ? opera / area * 1000 : null, producao: ctx.producao || null, producao_un: ctx.producao_un || "", int_prod: ctx.producao ? opera / ctx.producao * 1000 : null,
    metas:{ ano_base:anoBase, base_t:baseT, pct, alvo, trajet, net_zero: anoNetZero(anoBase, pct, F.metas.residual_max), medidas_t:medT, apos_medidas: Math.max(0, (M.incluir_e3 ? total : opera) - medT) },
    sbce: sbceSit(F, e1), servidor: sv }; }

/* ════════ peças de tela ════════ */
const idDe = p => "cb-" + String(p).replace(/[^a-zA-Z0-9]+/g, "-");
function pegarCaminho(o, p){ return String(p).split(".").reduce((a, k) => a == null ? a : a[k], o); }
function porCaminho(o, p, v){ const ks = String(p).split("."); let a = o; ks.slice(0, -1).forEach((k, i) => { if (a[k] == null || typeof a[k] !== "object") a[k] = /^\d+$/.test(ks[i + 1]) ? [] : {}; a = a[k]; }); a[ks[ks.length - 1]] = v; }
function inp(c, p, rot, ph, aj, so){ const v = pegarCaminho(c, p), id = idDe(p);
  return `<div><label for="${id}"${so ? ' class="so-leitor"' : ""}>${rot}</label><input id="${id}" type="text" inputmode="decimal" data-carb-campo="${E(p)}" value="${E(v == null ? "" : v)}" placeholder="${E(ph || "")}" style="width:100%">${aj ? `<span class="t2 pq">${aj}</span>` : ""}</div>`; }
function txt(c, p, rot, ph, so){ const v = pegarCaminho(c, p), id = idDe(p); return `<div><label for="${id}"${so ? ' class="so-leitor"' : ""}>${rot}</label><input id="${id}" type="text" data-carb-campo="${E(p)}" value="${E(v == null ? "" : v)}" placeholder="${E(ph || "")}" style="width:100%"></div>`; }
function sel(c, p, rot, ops, so){ const v = String(pegarCaminho(c, p) == null ? "" : pegarCaminho(c, p)), id = idDe(p);
  return `<div><label for="${id}"${so ? ' class="so-leitor"' : ""}>${rot}</label><select id="${id}" data-carb-campo="${E(p)}" style="width:100%">${ops.map(([k, n]) => `<option value="${E(k)}" ${v === String(k) ? "selected" : ""}>${E(n)}</option>`).join("")}</select></div>`; }
function chk(c, p, rot){ const id = idDe(p); return `<div><label for="${id}" style="display:flex;gap:8px;align-items:center"><input id="${id}" type="checkbox" data-carb-campo="${E(p)}" ${pegarCaminho(c, p) ? "checked" : ""}> ${rot}</label></div>`; }
const cartao = (id, tit, numero, un, extra) => `<section class="cartao" aria-labelledby="h-${id}"><h3 id="h-${id}" class="t3">${tit}</h3><span class="numero">${numero}</span><span class="t2">${un}</span>${extra || ""}</section>`;
const tabela = (cap, cab, linhas) => `<div class="rolagem"><table><caption class="so-leitor">${E(cap)}</caption><thead><tr>${cab.map(h => `<th scope="col">${h}</th>`).join("")}</tr></thead><tbody>${linhas.join("")}</tbody></table></div>`;
const aviso = t => `<span class="selo at">verificar</span> <span class="t2 pq">${t}</span>`;

/* listas editáveis: [campo, rótulo, tipo (sel|num|txt|chk), opções ou dica] */
function LISTAS(F){ const opsComb = ks => ks.map(k => [k, nomeComb(F, k) + " (" + unComb(F, k) + ")"]), ent = o => Object.keys(o).filter(k => k[0] !== "_" && typeof o[k] === "object").map(k => [k, o[k].nome || k]);
  return {
    estac:{ tit:"Combustão estacionária", aj:"Geradores, caldeiras, fornos, fogões e secadores. Quantidade de um ano, pela nota fiscal ou pelo medidor.", campos:[["comb","Combustível","sel",opsComb(["diesel_b","diesel","glp","gas_natural","lenha","carvao_vegetal","biodiesel","etanol_hidratado"])],["qtd","Quantidade por ano","num"],["nr","Lenha ou carvão de origem não renovável","chk"],["q","Dado","sel",QUAL]], novo:{ comb:"diesel_b", qtd:"", q:"medido" } },
    movel:{ tit:"Combustão móvel (frota própria)", aj:"Carros, caminhões, tratores e máquinas da empresa. Diesel B e gasolina C já levam a mistura obrigatória de biocombustível; o CO₂ da parte bio é informado à parte.", campos:[["comb","Combustível","sel",opsComb(["diesel_b","gasolina_c","etanol_hidratado","gnv","biodiesel","diesel"])],["qtd","Litros (ou m³ de GNV) por ano","num"],["teor_pct","Teor bio (%), vazio = padrão","num"],["q","Dado","sel",QUAL]], novo:{ comb:"diesel_b", qtd:"", teor_pct:"", q:"medido" } },
    refrig:{ tit:"Fugitivas: gases de refrigeração", aj:"Melhor caminho: a massa recarregada na manutenção do ano (nota do técnico). Sem ela, carga do equipamento × taxa de vazamento típica.", campos:[["gas","Gás","sel",ent(F.refrigerantes)],["modo","Como medir","sel",[["recarga","Massa recarregada (kg)"],["carga","Carga × taxa de vazamento"]]],["kg","Recarregado no ano (kg)","num"],["carga","Carga do equipamento (kg)","num"],["equip","Equipamento","sel",ent(F.vazamento).filter(x => x[0] !== "carga_kg_por_kw")],["taxa_pct","Vazamento ao ano (%), vazio = típico","num"],["q","Dado","sel",QUAL]], novo:{ gas:"R-410A", modo:"recarga", kg:"", carga:"", equip:"split", taxa_pct:"", q:"medido" } },
    proc:{ tit:"Emissões de processo", aj:"Gases que saem de reações químicas do processo (ex.: CO₂ de calcinação, uso de CO₂ engarrafado, SF₆ de disjuntores).", campos:[["nome","Processo","txt"],["gas","Gás","sel",[["CO2","CO₂"],["CH4_fossil","CH₄ (fóssil)"],["N2O","N₂O"],["SF6","SF₆"]]],["kg","kg do gás por ano","num"],["q","Dado","sel",QUAL]], novo:{ nome:"", gas:"CO2", kg:"", q:"estimado" } },
    rebanho:{ tit:"Rebanho", aj:"Fermentação entérica, manejo de dejetos e N₂O dos dejetos deixados no pasto (fatores IPCC, nível 1, América Latina).", campos:[["tipo","Animal","sel",ent(F.agro.rebanho)],["cab","Cabeças (média do ano)","num"],["q","Dado","sel",QUAL]], novo:{ tipo:"gado_corte", cab:"", q:"medido" } },
    "rede.contratos":{ tit:"Contratos de energia com atributo de origem", aj:"Mercado livre com garantia de origem: MWh do contrato e fator do contrato (0 para renovável certificada).", campos:[["mwh","MWh por ano","num"],["fator","Fator do contrato (tCO₂/MWh)","num"]], novo:{ mwh:"", fator:"0" } },
    "e3.gastos":{ tit:"Compras por gasto (categoria 1)", aj:"Triagem por valor gasto em reais. Fator provisório de ordem de grandeza: troque pelo fator do fornecedor quando tiver.", campos:[["cat","Tipo de compra","sel",ent(F.escopo3.gasto_kg_por_real)],["valor","R$ por ano","num"]], novo:{ cat:"manufaturados", valor:"" } },
    "e3.materiais":{ tit:"Materiais comprados (categoria 1)", aj:"Quando a quantidade é conhecida: kg de material × carbono incorporado (berço ao portão).", campos:[["mat","Material","sel",ent(F.escopo3.materiais_kg_por_kg)],["kg","kg por ano","num"],["q","Dado","sel",QUAL]], novo:{ mat:"concreto", kg:"", q:"estimado" } },
    "e3.transp":{ tit:"Transporte de cargas (categorias 4 e 9)", aj:"Tonelada transportada × distância (t·km). Categoria 4 = o que chega (pago pela empresa); 9 = o que sai até o cliente.", campos:[["cat","Categoria","sel",[["4","4 · chegada (a montante)"],["9","9 · saída (a jusante)"]]],["modo","Modo","sel",ent(F.escopo3.transporte_tkm)],["tkm","t·km por ano","num"],["q","Dado","sel",QUAL]], novo:{ cat:"4", modo:"caminhao", tkm:"", q:"estimado" } },
    "e3.residuos":{ tit:"Outros resíduos enviados (categoria 5)", aj:"Resíduos que não estão na Economia circular.", campos:[["tipo","Resíduo","sel",TIPOS_RES],["t","Toneladas por ano","num"],["destino","Destino","sel",DESTINOS],["q","Dado","sel",QUAL]], novo:{ tipo:"rejeito", t:"", destino:"aterro", q:"estimado" } },
    "e3.viagens":{ tit:"Viagens a negócios (categoria 6)", aj:"Passageiro·km: soma das distâncias de cada pessoa em cada viagem.", campos:[["modo","Modo","sel",ent(F.escopo3.viagens_pkm)],["pkm","Passageiro·km por ano","num"],["q","Dado","sel",QUAL]], novo:{ modo:"aviao_nacional", pkm:"", q:"estimado" } },
    "e3.desloc":{ tit:"Deslocamento casa–trabalho (categoria 7)", aj:"Por meio de transporte: pessoas, km por dia (ida e volta) e dias de trabalho no ano.", campos:[["modo","Meio","sel",ent(F.escopo3.deslocamento)],["pessoas","Pessoas","num"],["km","km por dia (ida e volta)","num"],["dias","Dias no ano","num"]], novo:{ modo:"carro", pessoas:"", km:"", dias:"220" } },
    "e3.fim":{ tit:"Fim de vida dos produtos vendidos (categoria 12)", aj:"Toneladas de produto e embalagem vendidas e o destino provável depois do uso.", campos:[["tipo","Material","sel",TIPOS_RES],["t","Toneladas por ano","num"],["destino","Destino","sel",DESTINOS]], novo:{ tipo:"rejeito", t:"", destino:"aterro" } },
    "e3.outras":{ tit:"Outras categorias (valor calculado fora)", aj:"Para as categorias sem calculadora aqui: informe o resultado e guarde a memória de cálculo.", campos:[["cat","Categoria","sel",Object.keys(CAT3).map(k => [k, k + " · " + CAT3[k]])],["nome","Descrição","txt"],["t","tCO₂e por ano","num"],["q","Dado","sel",QUAL]], novo:{ cat:"3", nome:"", t:"", q:"estimado" } },
    "metas.medidas":{ tit:"Medidas de redução", aj:"Cada medida com a redução esperada por ano (dos estudos de Energia solar, AVAC, Custos ou do diagnóstico).", campos:[["n","Medida","txt"],["t","Redução (tCO₂e por ano)","num"]], novo:{ n:"", t:"" } } }; }
function lista(c, p, F, R){ const L = LISTAS(F)[p], arr = pegarCaminho(c, p) || [], porRef = {}; (R ? R.linhas : []).forEach(l => { if (l.ref) porRef[l.ref] = (porRef[l.ref] || 0) + l.t; });
  const temT = !!R && p !== "rede.contratos" && p !== "metas.medidas", hid = idDe(p) + "-h";
  const linhas = arr.map((x, i) => { const pi = p + "." + i, cel = L.campos.map(([k, r, tp, op]) => { const pp = pi + "." + k, id = idDe(pp), rot = r + " (linha " + (i + 1) + ")";
      if (tp === "sel") return `<td><label class="so-leitor" for="${id}">${E(rot)}</label><select id="${id}" data-carb-campo="${E(pp)}">${op.map(([v, n]) => `<option value="${E(v)}" ${String(x[k]) === String(v) ? "selected" : ""}>${E(n)}</option>`).join("")}</select></td>`;
      if (tp === "chk") return `<td><label class="so-leitor" for="${id}">${E(rot)}</label><input id="${id}" type="checkbox" data-carb-campo="${E(pp)}" ${x[k] ? "checked" : ""}></td>`;
      return `<td><label class="so-leitor" for="${id}">${E(rot)}</label><input id="${id}" type="text" ${tp === "num" ? 'inputmode="decimal"' : ""} data-carb-campo="${E(pp)}" value="${E(x[k] == null ? "" : x[k])}" style="width:100%;min-width:${tp === "txt" ? 160 : 80}px"></td>`; }).join("");
    const t = porRef[pi];
    return `<tr>${cel}${temT ? `<td>${T(t)}</td>` : ""}<td><button type="button" id="${idDe(pi)}-x" data-carb-del="${E(p)}:${i}" aria-label="Remover a linha ${i + 1} de ${E(L.tit)}">Remover</button></td></tr>`; });
  return `<section class="cartao" aria-labelledby="${hid}"><h3 id="${hid}" class="t3">${E(L.tit)}</h3><p class="t2 pq">${L.aj}</p>
    ${arr.length ? tabela(L.tit, L.campos.map(x => E(x[1])).concat(temT ? ["tCO₂e por ano"] : []).concat(['<span class="so-leitor">Ações</span>']), linhas) : `<p class="t2">Nenhuma linha ainda.</p>`}
    <div><button type="button" id="${idDe(p)}-add" data-carb-add="${E(p)}">Acrescentar linha</button></div></section>`; }

/* gráficos SVG acessíveis (o texto alternativo repete a tabela ao lado) */
function barras(id, titulo, dados){ const d = dados.filter(x => x[1] > 0); if (!d.length) return ""; const max = Math.max.apply(null, d.map(x => x[1])), h = 30 * d.length + 10, W = 640, x0 = 190;
  return `<figure style="margin:8px 0"><svg role="img" aria-labelledby="${id}-t ${id}-d" viewBox="0 0 ${W} ${h}" style="width:100%;max-width:${W}px;height:auto"><title id="${id}-t">${E(titulo)}</title><desc id="${id}-d">${E(d.map(x => x[0] + ": " + T(x[1]) + " tCO₂e").join("; "))}</desc>
    ${d.map((x, i) => { const w = Math.max(2, (W - x0 - 90) * x[1] / max), y = 6 + i * 30; return `<text x="${x0 - 8}" y="${y + 15}" text-anchor="end" font-size="13" fill="currentColor">${E(x[0])}</text><rect x="${x0}" y="${y}" width="${w.toFixed(1)}" height="20" rx="3" fill="${x[2] || "var(--marca, #1A4D2E)"}"></rect><text x="${(x0 + w + 6).toFixed(1)}" y="${y + 15}" font-size="13" fill="currentColor">${E(T(x[1]))}</text>`; }).join("")}</svg><figcaption class="t2 pq">${E(titulo)} (tCO₂e por ano)</figcaption></figure>`; }
function linhaMeta(R){ const tr = R.metas.trajet; if (tr.length < 2 || !(R.metas.base_t > 0)) return ""; const W = 640, H = 220, x0 = 56, y0 = 16, w = W - x0 - 16, h = H - y0 - 36, max = R.metas.base_t * 1.05, a0 = tr[0][0], a1 = tr[tr.length - 1][0];
  const X = a => x0 + (a - a0) / Math.max(1, a1 - a0) * w, Y = v => y0 + h - v / max * h, pts = tr.map(([a, v]) => X(a).toFixed(1) + "," + Y(v).toFixed(1)).join(" "), ap = R.metas.apos_medidas;
  const marcas = [a0, Math.round((a0 + a1) / 2), a1].map(a => `<text x="${X(a).toFixed(1)}" y="${H - 14}" font-size="12" text-anchor="middle" fill="currentColor">${a}</text>`).join("");
  return `<figure style="margin:8px 0"><svg role="img" aria-labelledby="cb-traj-t cb-traj-d" viewBox="0 0 ${W} ${H}" style="width:100%;max-width:${W}px;height:auto"><title id="cb-traj-t">Caminho de redução até ${a1}</title><desc id="cb-traj-d">Linha da meta: de ${E(T(R.metas.base_t))} tCO₂e em ${a0} caindo ${E(N(R.metas.pct, 1))}% da base por ano. Linha tracejada: emissões depois das medidas cadastradas, ${E(T(ap))} tCO₂e.</desc>
    <line x1="${x0}" y1="${y0 + h}" x2="${x0 + w}" y2="${y0 + h}" stroke="currentColor" stroke-opacity=".4"></line><line x1="${x0}" y1="${y0}" x2="${x0}" y2="${y0 + h}" stroke="currentColor" stroke-opacity=".4"></line>
    <text x="${x0 - 6}" y="${y0 + 10}" font-size="12" text-anchor="end" fill="currentColor">${E(T(max))}</text><text x="${x0 - 6}" y="${y0 + h}" font-size="12" text-anchor="end" fill="currentColor">0</text>${marcas}
    <polyline points="${pts}" fill="none" stroke="var(--marca, #1A4D2E)" stroke-width="3"></polyline>
    ${R.metas.medidas_t > 0 ? `<line x1="${x0}" y1="${Y(ap).toFixed(1)}" x2="${x0 + w}" y2="${Y(ap).toFixed(1)}" stroke="var(--acao, #2F7D5B)" stroke-width="2" stroke-dasharray="6 4"></line>` : ""}</svg>
    <figcaption class="t2 pq">Linha cheia: meta (tCO₂e por ano). ${R.metas.medidas_t > 0 ? "Tracejada: depois das medidas cadastradas." : ""}</figcaption></figure>`; }

/* ════════ subabas ════════ */
const GRUPOS = { estacionaria:"Combustão estacionária", movel:"Combustão móvel", fugitivas:"Fugitivas (refrigeração)", processos:"Processos", agropecuaria:"Agropecuária", residuos_no_lugar:"Resíduos tratados no lugar", esgoto_no_lugar:"Tratamento de esgoto no lugar", materiais_obra:"Materiais da obra", uso_solo:"Mudança de uso do solo", rede:"Eletricidade da rede", compras:"Compras", bens_capital:"Bens de capital", transporte:"Transporte de cargas", residuos:"Resíduos enviados", viagens:"Viagens a negócios", deslocamento:"Deslocamento casa–trabalho", fim_de_vida:"Fim de vida dos produtos", outras:"Outras categorias", servidor:"Servidor do sistema digital", servidor_hospedagem:"Hospedagem do sistema digital", servidor_fabricacao:"Fabricação do servidor" };
function tabLinhas(R, filtro, cap){ const l = R.linhas.filter(filtro); if (!l.length) return `<p class="t2">Nada lançado ainda.</p>`;
  return tabela(cap, ["Fonte", "Grupo", "tCO₂e por ano", "CO₂ biogênico (t)", "Dado", "Incerteza"], l.map(x => `<tr><th scope="row" style="font-weight:500">${E(x.fonte)}${x.fora ? ' <span class="selo in">fora de Quioto, à parte</span>' : ""}</th><td>${E(GRUPOS[x.grupo] || x.grupo)}${x.cat ? " · cat. " + x.cat : ""}</td><td>${T(x.t)}</td><td>${x.bio_t ? T(x.bio_t) : "—"}</td><td>${x.q === "medido" ? "Medido" : "Estimado"}</td><td>±${Math.round(x.u * 100)}%</td></tr>`)); }

/* ════════ pegada do servidor (sistema digital) ════════ */
const SV_METODO = { medidor:"medido (medidor na tomada)", rapl:"parcial (contador do processador + resto estimado)", "rapl+gpu":"parcial (processador e placas de vídeo medidos)", "nominal+gpu":"parcial (placas de vídeo medidas, resto estimado)", nominal:"estimado (potência da classe × uso)", fixo:"estimado (potência informada)", misto:"misto (mudou de método no período)", sem_historico:"estimado (sem histórico ainda)" };
const SV_LOCAL = { no_lugar:"no lugar do inventário", fora:"fora (datacenter ou outro lugar)" };
function secaoServidor(c, R, F, foco){ svCarregar();
  const hub = !!(SV.dados && SV.dados.modo === "hub"), D = hub ? SV.dados : SV_DEMO, eqs = D.equipamentos || [], fLoc = R.fator_rede, svc = c.servidor || {}, escolha = svc.contagem || "auto";
  const inv = servidorInventario(eqs, fLoc, escolha, null), kwhMes = eqs.reduce((s, e) => s + n0(e.kwh_mes), 0), tEn = eqs.reduce((s, e) => s + n0(e.kwh_ano), 0) / 1000 * fLoc, tFab = eqs.reduce((s, e) => s + n0(e.t_ano_fabricacao), 0), wAgora = eqs.reduce((s, e) => s + n0(e.w_agora), 0);
  const quals = eqs.map(e => e.qualidade), qual = quals.length && quals.every(q => q === "medido") ? "medido" : quals.some(q => q === "medido" || q === "parcial") ? "parcialmente medido" : "estimado";
  const faixa = hub ? `<p class="t2 pq">Dados deste servidor, atualizados a cada ${N(n0(D.intervalo_min) || 5, 0)} minutos. ${D.total && D.total.medido_pct != null ? "Parte medida: " + P(D.total.medido_pct) + "." : ""}</p>`
    : `<p class="faixa at" role="note"><strong>Exemplo (modo demonstração).</strong> Números ilustrativos de um hub Raspberry Pi 5 e um servidor de IA com 2 placas de vídeo. Eles não entram no inventário. ${SV.erro === 401 || SV.erro === 403 ? "Entre com a sua conta para ver os dados do servidor." : temServidorWeb() ? "O servidor ainda não mandou a pegada." : "Abra a plataforma pelo servidor Physis para ver os dados reais."}</p>`;
  const cards = `<div class="grade">${cartao("cb-sv-w", "Potência agora", N(wAgora, 0), "W")}${cartao("cb-sv-k", "Energia", N(kwhMes, 1), "kWh por mês", `<span class="t2 pq">${qual}${hub ? "" : " · exemplo"}</span>`)}${cartao("cb-sv-t", "Operação (energia)", T(tEn), "tCO₂e por ano", `<span class="t2 pq">${N(kwhMes * 12, 0)} kWh × ${N(fLoc, 4)} tCO₂/MWh (o mesmo fator do escopo 2)</span>`)}${cartao("cb-sv-f", "Fabricação (escopo 3, cat. 2)", T(tFab), "tCO₂e por ano", `<span class="t2 pq">dividida pelos anos de uso</span>`)}</div>`;
  const linhas = eqs.map(e => { const k = svContagem(e, escolha), t = n0(e.kwh_ano) / 1000 * fLoc;
    return `<tr><th scope="row" style="font-weight:500">${E(e.nome)}<br><span class="t2 pq">${E(e.classe_nome || "")}</span></th><td>${E(SV_LOCAL[e.local] || e.local || "")}${n0(e.pue) > 1 ? " · PUE " + N(e.pue, 2) : ""}</td><td>${E(SV_METODO[e.metodo] || e.metodo || "")}</td><td>${N(n0(e.kwh_mes), 1)}</td><td>${T(t)}</td><td>${T(n0(e.t_ano_fabricacao))}<br><span class="t2 pq">${N(n0(e.kg_fabricacao), 0)} kg ÷ ${N(n0(e.vida_anos), 0)} anos</span></td><td>${k === "ja_contado" ? '<span class="selo in">parte do escopo 2 já contado</span>' : e.controle === "servico" ? '<span class="selo at">soma no escopo 3, cat. 1</span>' : '<span class="selo at">soma no escopo 2</span>'}</td></tr>`; });
  const tab = eqs.length ? tabela("Equipamentos do sistema digital", ["Equipamento", "Onde fica", "Método", "kWh por mês", "Energia (tCO₂e por ano)", "Fabricação (tCO₂e por ano)", "No inventário"], linhas) : `<p class="t2">Nenhum equipamento informado.</p>`;
  const conf = `<div class="precos">${chk(c, "servidor.incluir", "Incluir a pegada do servidor no inventário")}${sel(c, "servidor.contagem", "Como contar a energia do servidor", [["auto", "Automático: pelo lugar de cada máquina (recomendado)"], ["ja_contado", "Já está nas contas de luz do inventário (só informar)"], ["somar", "Somar como fonte própria"]])}</div>
    <p class="t2 pq">Por que isso importa: se o servidor fica no mesmo lugar cujas contas de luz já estão no escopo 2 (como a Casa Physis), a energia dele já foi contada; ela aparece aqui só como informação (${T(inv.ja_contado_t)} tCO₂e por ano), para não contar duas vezes. Se fica em outro lugar (datacenter, servidor da Physis que hospeda clientes), ninguém contou: entra como fonte própria, no escopo 2 quando a máquina é sua, ou no escopo 3, categoria 1, quando a hospedagem é comprada de outra empresa. Somado agora: escopo 2 ${T(inv.e2_t)}, escopo 3 cat. 1 ${T(inv.e3_cat1_t)} tCO₂e por ano.</p>`;
  const dicas = (D.dicas && D.dicas.length ? D.dicas : ["Desligue ou suspenda a placa de vídeo quando nenhum modelo de IA estiver rodando.", "Agende treinos de IA para as horas de sol, quando a energia solar própria cobre o pico.", "Prefira máquinas pequenas e eficientes e junte serviços em contêineres.", "Use a máquina até o fim da vida útil: a fabricação pesa mais que a luz nas máquinas pequenas."]).map(d => `<li>${E(d)}</li>`).join("");
  const e3nota = `<p class="t2 pq">Fabricação: o carbono de fazer as máquinas (escopo 3, categoria 2, bens de capital) é dividido pelos anos de uso, para acompanhar a pegada ano a ano. O GHG Protocol pede, no relato oficial, o total no ano da compra: use a soma das máquinas compradas no ano. Se a compra do servidor já está em “Bens de capital (por gasto)”, não marque as duas coisas. A linha entra no total só com a categoria 2 marcada.</p>`;
  const resumo = `<p class="t2 pq">${hub ? "" : "Exemplo: "}${N(kwhMes, 1)} kWh por mês · ${T(tEn)} tCO₂e por ano de energia (${qual}) + ${T(tFab)} de fabricação.</p>`;
  if (foco === "resumo") return `<section class="cartao" aria-labelledby="h-cb-sv-r"><h2 id="h-cb-sv-r">Pegada do servidor (sistema digital)</h2>${hub ? "" : faixa}${resumo}<p class="t2 pq">Detalhes e escolha da contagem nas subabas Escopo 2 e Escopo 3.</p></section>`;
  return `<section class="cartao" aria-labelledby="h-cb-sv-${foco}"><h2 id="h-cb-sv-${foco}">Pegada do servidor (sistema digital)</h2><p class="t2 pq">As máquinas que rodam este sistema também gastam energia e foram fabricadas. Aqui está a pegada delas.</p>${faixa}${cards}${tab}${foco === "e2" ? conf : e3nota}
    <details><summary>Como reduzir</summary><ul>${dicas}</ul></details><p class="t2 pq">${aviso("potência por classe e carbono de fabricação são ordem de grandeza (" + E((F.servidor || {})._fonte || "") + ")")}</p></section>`; }

function abaInventario(c, R, F, ctx){ const tot = R.total, ops = [["", "Padrão (" + F.gwp.padrao + ")"], ["AR5", "AR5 (IPCC 2013)"], ["AR6", "AR6 (IPCC 2021)"]];
  const conf = `<section class="cartao" aria-labelledby="h-cb-conf"><h2 id="h-cb-conf">Ano e método</h2><div class="precos">${inp(c, "ano", "Ano do inventário", "ex.: 2025")}${sel(c, "gwp", "Potencial de aquecimento (GWP)", ops)}${inp(c, "area_m2", "Área construída (m²)", ctx.area_m2 != null ? N(ctx.area_m2, 0) + " (do Início)" : "ex.: 1200", "Para o indicador por m².")}</div>
    <p class="t2 pq">${aviso(E(F.gwp.nota_padrao))}</p></section>`;
  const cards = `<div class="grade">${cartao("cb-t1", "Escopo 1 · diretas", T(R.e1), "tCO₂e por ano")}${cartao("cb-t2", "Escopo 2 · energia comprada", T(R.e2_loc), "tCO₂e por ano (localização)", `<span class="t2 pq">Escolha de compra: ${T(R.e2_mkt)}</span>`)}${cartao("cb-t3", "Escopo 3 · cadeia de valor", T(R.e3), "tCO₂e por ano", `<span class="t2 pq">${(c.e3.cats || []).length} categorias escolhidas</span>`)}${cartao("cb-tt", "Total", T(tot), "tCO₂e por ano", tot ? `<span class="t2 pq">Dado medido: ${P(R.medido)} · incerteza ±${R.incerteza != null ? Math.round(R.incerteza * 100) : "—"}%</span>` : `<span class="t2 pq">Comece pelo Escopo 1 e pelo Escopo 2.</span>`)}</div>`;
  const grafico = barras("cb-g-esc", "Emissões por escopo", [["Escopo 1", R.e1, "var(--marca, #1A4D2E)"], ["Escopo 2", R.e2_loc, "var(--acao, #2F7D5B)"], ["Escopo 3", R.e3, "var(--agua, #B07A12)"]]) + barras("cb-g-fonte", "Emissões por grupo de fontes", Object.keys(R.porGrupo).map(k => [GRUPOS[k] || k, R.porGrupo[k]]).sort((a, b) => b[1] - a[1]));
  const gases = tabela("Emissões por gás", ["Gás", "tCO₂e por ano", "Parte"], [["CO₂", "CO2"], ["CH₄", "CH4"], ["N₂O", "N2O"], ["HFCs", "HFC"], ["SF₆", "SF6"]].map(([n, k]) => `<tr><th scope="row">${n}</th><td>${T(R.porGas[k] || 0)}</td><td>${tot ? P((R.porGas[k] || 0) / tot) : "—"}</td></tr>`));
  const ind = tabela("Indicadores de intensidade", ["Indicador", "Valor"], [`<tr><th scope="row">Escopos 1 e 2 por m² construído</th><td>${R.int_m2 != null ? N(R.int_m2, 1) + " kgCO₂e/m²·ano" : "falta a área"}</td></tr>`, `<tr><th scope="row">Escopos 1 e 2 por unidade produzida</th><td>${R.int_prod != null ? N(R.int_prod, 3) + " kgCO₂e por " + E(R.producao_un) : "falta a produção (Gestão → Produção e insumos)"}</td></tr>`, `<tr><th scope="row">CO₂ biogênico (à parte)</th><td>${T(R.bio_t)} t</td></tr>`, `<tr><th scope="row">Gases fora de Quioto (HCFC-22, à parte)</th><td>${T(R.fora_t)} tCO₂e</td></tr>`, `<tr><th scope="row">Remoções (à parte, não abatem)</th><td>${T(R.remocoes_t)} tCO₂ por ano</td></tr>`, `<tr><th scope="row">Emissões evitadas (à parte, não abatem)</th><td>${T(R.evitadas_t)} tCO₂e por ano</td></tr>`]);
  return `${conf}${cards}<section class="cartao" aria-labelledby="h-cb-inv"><h2 id="h-cb-inv">Inventário ${E(c.ano || "")} por fonte</h2>${grafico}${tabLinhas(R, () => true, "Todas as fontes do inventário")}
    <p class="t2 pq">Incerteza: soma quadrática do dado (medido ±5%, estimado ±30%) e do fator de cada linha; valor de ordem de grandeza para orientar onde medir melhor, não um intervalo estatístico formal.</p></section>
    <div class="grade"><section class="cartao" aria-labelledby="h-cb-gas"><h2 id="h-cb-gas">Por gás</h2>${gases}</section><section class="cartao" aria-labelledby="h-cb-ind"><h2 id="h-cb-ind">Intensidade e itens à parte</h2>${ind}</section></div>${secaoServidor(c, R, F, "resumo")}`; }

const NOME_TRAT = { fossa_filtro:"Tanque séptico + filtro anaeróbio", wetland:"Tanque séptico + wetland construído", biodigestor:"Biodigestor (esgoto e orgânicos)", ete:"ETE compacta" };
function secaoEsgoto(R){ const s = R.esgoto; if (!s) return "";
  return `<section class="cartao" aria-labelledby="h-cb-esg"><h3 id="h-cb-esg" class="t3">Tratamento de esgoto no lugar (da Economia circular)</h3><p class="t2"><span>Pessoas atendidas:</span> <strong>${N(s.pessoas, 0)}</strong> · <span>Tratamento:</span> <strong>${E(NOME_TRAT[s.tratamento] || s.tratamento || "a definir")}</strong>${s.fonte ? ` · <span>Fonte:</span> <strong>${E(s.fonte)}</strong>` : ""}</p>
    ${s.marcador ? `<p class="faixa at" role="note">[MARCADOR: fator de metano do tratamento de esgoto (IPCC 2006, vol. 5, cap. 6) ainda não está na base de fatores. A linha entra no escopo 1 quando ele for incluído e conferido.]</p>` : tabLinhas(R, l => l.grupo === "esgoto_no_lugar", "Tratamento de esgoto no lugar")}</section>`; }
/* Frota e combustível: litros medidos substituem o digitado da combustão móvel (com a fonte); a caixa volta ao digitado */
function frotaNota(c, R, ctx){ if (!Array.isArray(ctx.frota_movel) || !ctx.frota_movel.length) return "";
  const usa = c.movel_auto !== false, t = R.linhas.filter(l => l.grupo === "movel").reduce((s, l) => s + l.t, 0);
  return `<section class="cartao" aria-labelledby="h-cb-frota"><h3 id="h-cb-frota" class="t3">Combustão móvel medida na aba Frota e combustível</h3>
    <ul>${ctx.frota_movel.map(x => `<li><span>${E(nomeComb(base(), x.comb))}</span> <strong>${N(n0(x.qtd), 0)}</strong> <span>${E(unComb(base(), x.comb))}</span> <span class="t2 pq">(${E(x.fonte || "")})</span></li>`).join("")}</ul>
    <div class="precos">${chk(c, "movel_auto", "Usar o medido na frota (o digitado abaixo fica de reserva)")}</div>
    <p class="t2 pq">${usa ? "O inventário usa o medido: " + N(t, 2) + " tCO₂e. As linhas digitadas abaixo não entram enquanto a caixa estiver marcada." : "A caixa está desmarcada: o inventário usa as linhas digitadas abaixo."}</p></section>`; }
function abaE1(c, R, F, ctx){ const L = p => lista(c, p, F, R);
  const avac = ctx.avac_kwt ? `<p class="t2 pq">A aba AVAC e térmico tem ${N(ctx.avac_kwt, 0)} kW de frio: carga estimada de ${N(ctx.avac_kwt * F.vazamento.carga_kg_por_kw.valor, 0)} kg de fluido. <button type="button" id="cb-sug-avac" data-carb-sug="avac">Acrescentar como linha estimada</button></p>` : "";
  const comb = ctx.comb_l ? `<p class="t2 pq">A Gestão registra ${N(ctx.comb_l, 0)} litros de combustível por ano em Produção e insumos: lance aqui separando gerador (estacionária) e frota (móvel).</p>` : "";
  const rc = R.linhas.filter(l => l.grupo === "residuos_no_lugar");
  const solo = `<section class="cartao" aria-labelledby="h-cb-solo"><h3 id="h-cb-solo" class="t3">Mudança de uso do solo (opcional)</h3><p class="t2 pq">Vegetação nativa convertida nos últimos 20 anos: a perda de carbono é dividida em 20 anos.</p><div class="precos">${chk(c, "solo.ativo", "Incluir mudança de uso do solo")}${inp(c, "solo.ha", "Hectares convertidos", "ex.: 3")}${sel(c, "solo.bioma", "Bioma da vegetação original", BIOMAS.filter(b => b[0] !== "saf"))}</div><p class="t2 pq">${aviso("estoques de carbono por bioma são ordem de grandeza (" + E(F.uso_solo._fonte) + ")")}</p></section>`;
  return `<p class="t2 apoio">Emissões que saem de fontes da própria organização: queima de combustíveis, vazamento de gases de refrigeração, processos, animais e solo, e resíduos tratados no lugar.</p>
    ${L("estac")}${comb}${frotaNota(c, R, ctx)}${L("movel")}${L("refrig")}${avac}${L("proc")}${L("rebanho")}
    <section class="cartao" aria-labelledby="h-cb-fert"><h3 id="h-cb-fert" class="t3">Adubo e correção do solo</h3><div class="precos">${inp(c, "fert.n_kg", "Nitrogênio de outros adubos (kg de N por ano)", "ex.: 300", "kg de N, não de adubo")}${inp(c, "fert.ureia_kg", "Ureia (kg por ano)", "ex.: 500", "O N da ureia (46%) já entra na conta.")}${inp(c, "fert.calcario_kg", "Calcário calcítico (kg por ano)", "ex.: 2000")}${inp(c, "fert.dolomita_kg", "Calcário dolomítico (kg por ano)", "ex.: 0")}${sel(c, "fert.q", "Dado", QUAL)}</div></section>
    <section class="cartao" aria-labelledby="h-cb-rcl"><h3 id="h-cb-rcl" class="t3">Resíduos tratados no lugar (da Economia circular)</h3>${rc.length ? tabLinhas(R, l => l.grupo === "residuos_no_lugar", "Resíduos tratados no lugar") : `<p class="t2">Nenhum resíduo com rota no lugar (compostagem, minhocário, biodigestor, queima) na Economia circular.</p>`}</section>${secaoEsgoto(R)}
    ${solo}<section class="cartao" aria-labelledby="h-cb-s1"><h2 id="h-cb-s1">Escopo 1: ${T(R.e1)} tCO₂e por ano</h2>${tabLinhas(R, l => l.escopo === 1, "Fontes do escopo 1")}</section>`; }

function abaE2(c, R, F, ctx){ const A = F.rede.anual, ops = [["", A[F.rede.padrao].rotulo + " · " + N(A[F.rede.padrao].valor, 4)]].concat(Object.keys(A).filter(k => k !== F.rede.padrao).sort().reverse().map(k => [k, A[k].rotulo + " · " + N(A[k].valor, 4)]));
  const M = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"];
  const mens = `<details ${c.rede.usar_mensal ? "open" : ""}><summary>Fatores mensais do MCTI (mais exato)</summary><p class="t2 pq">${E(F.rede.mensal.nota)} ${ctx.kwh_mes ? "As 12 contas de " + E(c.ano) + " estão no Início." : "Precisa das 12 contas do ano " + E(c.ano) + " no Início e do campo de consumo vazio."}</p>${chk(c, "rede.usar_mensal", "Usar os fatores mensais")}<div class="precos">${M.map((m, i) => inp(c, "rede.mensal." + i, "Fator de " + m + " (tCO₂/MWh)", "ex.: 0,0385")).join("")}</div></details>`;
  const solarPh = ctx.solar_kwh ? N(ctx.solar_kwh, 0) + " (da Energia solar)" : "ex.: 9000";
  return `<p class="t2 apoio">Emissões da geração da eletricidade comprada da rede. O GHG Protocol pede os dois números: por localização (fator médio do sistema) e por escolha de compra (certificados e contratos).</p>
    <section class="cartao" aria-labelledby="h-cb-loc"><h2 id="h-cb-loc">Por localização</h2><div class="precos">${inp(c, "kwh", "Eletricidade da rede (kWh por ano)", ctx.kwh_ano != null ? N(ctx.kwh_ano, 0) : "ex.: 24000", ctx.kwh_fonte ? "Vazio = " + E(ctx.kwh_fonte) + "." : "Sem contas no Início: informe aqui.")}${sel(c, "rede.fator", "Fator do SIN", ops)}${inp(c, "rede.fator_manual", "Ou outro fator (tCO₂/MWh)", "ex.: 0,0385", "Ex.: sistema isolado ou ano que não está na lista.")}${sel(c, "rede.q", "Dado", QUAL)}</div>
      <p class="t2 pq">${aviso(E((A[c.rede.fator] || A[F.rede.padrao]).fonte))}</p>${mens}
      <div class="grade">${cartao("cb-e2l", "Localização", T(R.e2_loc), "tCO₂e por ano", `<span class="t2 pq">${R.kwh != null ? N(R.kwh, 0) + " kWh × " + (R.usa_mensal ? "fatores mensais" : N(R.fator_rede, 4) + " tCO₂/MWh") : "falta o consumo"}</span>`)}${cartao("cb-e2m", "Escolha de compra", T(R.e2_mkt), "tCO₂e por ano")}</div></section>
    <section class="cartao" aria-labelledby="h-cb-mkt"><h2 id="h-cb-mkt">Por escolha de compra</h2><p class="t2 pq">${E(F.rede.mercado.nota)}</p><div class="precos">${inp(c, "rede.irec_mwh", "Energia com I-REC (MWh por ano)", "ex.: 10")}</div>${lista(c, "rede.contratos", F, R)}</section>
    <section class="cartao" aria-labelledby="h-cb-sol"><h2 id="h-cb-sol">Geração solar no lugar (mostrada à parte)</h2><div class="precos">${inp(c, "solar_kwh", "Geração solar consumida no lugar (kWh por ano)", solarPh)}</div>
      <p class="t2 pq">A energia solar própria tem emissão zero e já reduz o que vem da rede (a conta de luz mede só o que entra). Por isso ela não é descontada outra vez do escopo 2: aparece aqui e em “Remoções e evitadas” só como informação (${T(R.evitadas.solar)} tCO₂e por ano que a rede teria emitido).</p></section>${secaoServidor(c, R, F, "e2")}`; }

function abaE3(c, R, F, ctx){ const cats = (c.e3.cats || []).map(Number), tem = k => cats.indexOf(k) >= 0, L = p => lista(c, p, F, R);
  const escolha = `<section class="cartao" aria-labelledby="h-cb-cats"><h2 id="h-cb-cats">Categorias que entram</h2><p class="t2 pq">O escopo 3 é opcional no Programa Brasileiro GHG Protocol, mas bancos e investidores pedem as categorias relevantes. Marque as que se aplicam e explique as que ficaram de fora.</p>
    <fieldset><legend class="so-leitor">Categorias do escopo 3</legend><div class="precos">${Object.keys(CAT3).map(k => `<div><label for="cb-cat-${k}" style="display:flex;gap:8px;align-items:center"><input id="cb-cat-${k}" type="checkbox" data-carb-cat="${k}" ${tem(+k) ? "checked" : ""}> ${k} · ${E(CAT3[k])}</label></div>`).join("")}</div></fieldset></section>`;
  const sugC = ctx.compras_rs ? `<p class="t2 pq">Gestão → Compras: R$ ${N(ctx.compras_rs, 2)} pagos nos últimos 12 meses (sem investimentos). <button type="button" id="cb-sug-compras" data-carb-sug="compras">Usar como bens manufaturados</button></p>` : "";
  const rcL = R.linhas.filter(l => l.escopo === 3 && l.ref && l.ref.indexOf("rc.") === 0);
  let corpo = "";
  const matL = R.linhas.filter(l => l.grupo === "materiais_obra");
  if (tem(1)) corpo += L("e3.gastos") + sugC + L("e3.materiais") + `<section class="cartao" aria-labelledby="h-cb-mob"><h3 id="h-cb-mob" class="t3">Materiais da obra (carbono incorporado, categoria 1)</h3>${chk(c, "e3.mat_auto", "Ler as composições escolhidas no SustainKit ou no Planejador")}
    ${matL.length ? tabLinhas(R, l => l.grupo === "materiais_obra", "Materiais da obra") : `<p class="t2">Nenhuma composição com área e carbono por m² ainda. Escolha as paredes e coberturas no SustainKit (Materiais) ou no Planejador.</p>`}
    ${R.mat_falta.length ? `<p class="t2 pq">[MARCADOR] carbono por m² ainda não informado: ${E(R.mat_falta.join(", "))}.</p>` : ""}<p class="t2 pq">Área × carbono incorporado por m² (berço ao portão). É o carbono da obra inteira: pelo GHG Protocol entra no ano da compra dos materiais; nos outros anos, desmarque a leitura.</p></section>`;
  if (tem(2)) corpo += `<section class="cartao" aria-labelledby="h-cb-cap"><h3 id="h-cb-cap" class="t3">Bens de capital (categoria 2)</h3><div class="precos">${inp(c, "e3.capital", "Investimentos em máquinas e obras (R$ no ano)", ctx.capital_rs ? N(ctx.capital_rs, 2) + " (da Gestão)" : "ex.: 150000")}</div>${ctx.capital_rs && !n0(c.e3.capital) ? `<button type="button" id="cb-sug-capital" data-carb-sug="capital">Usar o valor da Gestão</button>` : ""}</section>`;
  if (tem(4) || tem(9)) corpo += L("e3.transp");
  if (tem(5)) corpo += `<section class="cartao" aria-labelledby="h-cb-rc3"><h3 id="h-cb-rc3" class="t3">Resíduos da Economia circular enviados para fora (categoria 5)</h3>${chk(c, "e3.res_auto", "Ler os resíduos da Economia circular")}${rcL.length ? tabLinhas(R, l => l.escopo === 3 && l.ref && l.ref.indexOf("rc.") === 0, "Resíduos enviados para fora") : `<p class="t2">Nenhum resíduo com destino externo emissor (aterro, reciclagem, incineração).</p>`}<p class="t2 pq">Aterro: metano que o resíduo vai gerar ao longo dos anos, lançado no ano do envio. ${aviso("fatores IPCC de nível 1; aterros com queima de biogás emitem menos")}</p></section>` + L("e3.residuos");
  if (tem(6)) corpo += L("e3.viagens");
  if (tem(7)) corpo += L("e3.desloc") + (ctx.colaboradores ? `<p class="t2 pq">O Início registra ${N(ctx.colaboradores, 0)} colaboradores.</p>` : "");
  if (tem(12)) corpo += L("e3.fim");
  if ([3, 8, 10, 11, 13, 14, 15].some(tem)) corpo += L("e3.outras");
  const porCat = Object.keys(R.porCat).sort((a, b) => a - b);
  return `<p class="t2 apoio">Emissões que acontecem fora da organização, por causa dela: compras, transporte, resíduos, viagens, deslocamento das pessoas e o fim de vida do que é vendido.</p>${escolha}${corpo}
    <section class="cartao" aria-labelledby="h-cb-s3"><h2 id="h-cb-s3">Escopo 3: ${T(R.e3)} tCO₂e por ano</h2>${porCat.length ? tabela("Escopo 3 por categoria", ["Categoria", "tCO₂e por ano"], porCat.map(k => `<tr><th scope="row">${k} · ${E(CAT3[k] || "")}</th><td>${T(R.porCat[k])}</td></tr>`)) : `<p class="t2">Nada lançado ainda.</p>`}<p class="t2 pq">${aviso("fatores de transporte, viagens e gasto vêm de base internacional ou são provisórios; substituir por dados de fornecedores")}</p></section>${secaoServidor(c, R, F, "e3")}`; }

function abaRemocoes(c, R, F, ctx){ return `<p class="t2 apoio">Pelo GHG Protocol, remoções (carbono que as plantas tiram do ar) e emissões evitadas (o que se deixa de emitir em outro lugar) são informadas à parte. Elas nunca são descontadas do inventário.</p>
    <section class="cartao" aria-labelledby="h-cb-rem"><h2 id="h-cb-rem">Remoções por restauração e reflorestamento</h2><div class="precos">${sel(c, "remo.bioma", "Bioma ou sistema", BIOMAS)}${inp(c, "remo.ha", "Área plantada ou em restauração (ha)", "ex.: 2")}${inp(c, "remo.idade", "Idade do plantio (anos)", "ex.: 3")}${chk(c, "remo.usar_sbn", "Somar as árvores do plano SbN" + (ctx.mudas_sbn ? " (" + N(ctx.mudas_sbn, 0) + " mudas = " + N(ctx.mudas_sbn / F.remocoes.mudas_por_ha, 2) + " ha)" : ""))}</div>
      <div class="grade">${cartao("cb-rm", "Remoção estimada", T(R.remocoes_t), "tCO₂ por ano", `<span class="t2 pq">${N(R.remocoes_ha, 2)} ha × ${N(F.remocoes.tco2_ha_ano[c.remo.bioma] || 0, 1)} tCO₂/ha·ano${n0(c.remo.idade) > F.remocoes.anos_crescimento_rapido ? " × " + N(F.remocoes.fator_depois, 1) + " (plantio adulto)" : ""}</span>`)}</div>
      <p class="t2 pq">${aviso(E(F.remocoes._fonte))}</p></section>
    <section class="cartao" aria-labelledby="h-cb-ev"><h2 id="h-cb-ev">Emissões evitadas</h2>${tabela("Emissões evitadas", ["Origem", "tCO₂e por ano", "Como"], [`<tr><th scope="row">Energia solar própria</th><td>${T(R.evitadas.solar)}</td><td>kWh solares × fator da rede</td></tr>`, `<tr><th scope="row">Secador solar</th><td>${T(R.evitadas.secador)}</td><td>do Secador: CO₂ do secador elétrico que o sol substitui</td></tr>`, `<tr><th scope="row">Turbinas (água e vento)</th><td>${T(R.evitadas.turbinas)}</td><td>kWh das turbinas planejadas × fator da rede</td></tr>`, `<tr><th scope="row">Biogás no lugar do GLP</th><td>${T(R.evitadas.biogas)}</td><td>${N(R.biogas_m3, 0)} m³ de biogás por ano (Economia circular): 6 kWh/m³ ÷ 12,8 kWh/kg de GLP${R.biogas_fonte ? `<br><span class="t2 pq">Fonte: ${E(R.biogas_fonte)} (substitui a soma do plano de resíduos, sem contar duas vezes)</span>` : ""}</td></tr>`, `<tr><th scope="row">Reúso de água tratada</th><td>${R.reuso_marcador ? "[MARCADOR]" : T(R.evitadas.reuso)}</td><td>${N(R.reuso_m3, 0)} m³ de efluente reusado por ano (Esgoto e biogás)${R.reuso_marcador ? `<br><span class="t2 pq">[MARCADOR: fator de emissão da água fornecida pela concessionária ainda não está na base.]</span>` : ""}</td></tr>`, `<tr><th scope="row">Reciclagem no lugar do aterro</th><td>${T(R.evitadas.reciclagem)}</td><td>metano de aterro que não acontece, menos o transporte da reciclagem</td></tr>`])}
      <p class="t2 pq">Total evitado: ${T(R.evitadas_t)} tCO₂e por ano. Serve para comunicar benefício e para avaliar projetos de crédito; não entra no saldo do inventário.</p></section>`; }

function abaMetas(c, R, F){ const M = R.metas, marcos = M.trajet.filter(([a], i) => i === 0 || (a - M.ano_base) % 5 === 0 || i === M.trajet.length - 1);
  return `<p class="t2 apoio">Ano-base, meta de redução por ano e o caminho até o net zero: cortar pelo menos 90% e neutralizar o resto com remoções.</p>
    <section class="cartao" aria-labelledby="h-cb-meta"><h2 id="h-cb-meta">Meta</h2><div class="precos">${inp(c, "metas.ano_base", "Ano-base", String(M.ano_base))}${inp(c, "metas.base_t", "Emissões do ano-base (tCO₂e)", T(M.base_t) + " (inventário atual)")}${inp(c, "metas.pct", "Redução por ano (% da base)", N(F.metas.reducao_ano_pct_referencia, 1))}${inp(c, "metas.alvo", "Ano do net zero", "2050")}${chk(c, "metas.incluir_e3", "Incluir o escopo 3 na meta")}</div>
      <p class="t2 pq">${aviso(E(F.metas.fonte))}</p>
      <div class="grade">${cartao("cb-nz", "Net zero na meta", M.net_zero ? String(M.net_zero) : "—", M.net_zero && M.net_zero > M.alvo ? "depois do ano escolhido: aumente a redução por ano" : "ano em que o corte chega a 90%")}${cartao("cb-md", "Depois das medidas", T(M.apos_medidas), "tCO₂e por ano", `<span class="t2 pq">medidas cadastradas: ${T(M.medidas_t)} tCO₂e por ano</span>`)}</div>
      ${linhaMeta(R)}${tabela("Caminho da meta", ["Ano", "Meta (tCO₂e)"], marcos.map(([a, v]) => `<tr><th scope="row">${a}</th><td>${T(v)}</td></tr>`))}
      <p class="t2 pq">${E(F.metas.nota_residual)}</p></section>${lista(c, "metas.medidas", F, null)}`; }

function abaSbce(c, R, F){ const sit = R.sbce, S = F.sbce, ck = c.sbce;
  const itens = [["inventario","Inventário anual pelo GHG Protocol ou ISO 14064-1, com ano-base", R.total > 0],["responsavel","Responsável nomeado e rotina de coleta de dados",false],["plano","Plano de monitoramento escrito (fontes, medidores, fórmulas, frequência)",false],["dados","Dados medidos nas fontes maiores (notas, medidores calibrados)", R.medido != null && R.medido >= 0.8],["relato","Relato anual pronto no formato pedido pelo órgão gestor",false],["verif","Verificação por terceira parte (organismo acreditado)",false],["registro","Cadastro no registro central do SBCE (quando aberto)",false]];
  const feitos = itens.filter(([k]) => ck[k]).length, pronto = feitos === itens.length ? ["ok", "Pronto para o SBCE"] : feitos ? ["at", "Em preparação (" + feitos + " de " + itens.length + ")"] : ["al", "Não iniciado"];
  const quadro = { voluntario:["in", "Abaixo de " + N(S.limite_relato_t, 0) + " tCO₂e: sem obrigação; relato voluntário é boa prática e prepara para clientes e bancos."], relato:["at", "Entre " + N(S.limite_relato_t, 0) + " e " + N(S.limite_obrigacao_t, 0) + " tCO₂e: obrigado a ter plano de monitoramento e relatar as emissões todo ano."], obrigacao:["al", "Acima de " + N(S.limite_obrigacao_t, 0) + " tCO₂e: além de relatar, precisa entregar cotas ou certificados que cubram as emissões (conciliação periódica)."] }[sit];
  const gwB = gwpDe(F, R.gwp).CH4_bio, ch4Biog = R.biogas_m3 * 0.6 * 0.716 * gwB / 1000, buffer = 0.2;
  const proj = [["Restauração e reflorestamento (SbN)", R.remocoes_t * (1 - buffer), "Verra VCS VM0047 (florestamento, reflorestamento e revegetação); MDL AR-ACM0003; Gold Standard (florestamento e reflorestamento)", "Só gera crédito o que não aconteceria sem o projeto (adicionalidade). A floresta precisa durar (permanência): parte dos créditos fica numa reserva de risco, aqui 20%."],
    ["Biogás de dejetos e restos orgânicos", ch4Biog + R.evitadas.biogas, "MDL AMS-III.D (recuperação de metano de dejetos), AMS-I.C (energia térmica renovável); Verra e Gold Standard aceitam essas famílias", "O número é um teto: metano captado e queimado mais o GLP trocado. O crédito real depende da linha de base (o dejeto iria para lagoa aberta?) e da medição do biogás."],
    ["Eficiência energética e troca de combustível", R.metas.medidas_t, "MDL AMS-II (eficiência), AMS-III (troca de combustível)", "Eficiência elétrica no Brasil gera pouco crédito, porque a rede já é pouco emissora; troca de diesel ou GLP rende mais."]];
  return `<p class="t2 apoio">Enquadramento no Sistema Brasileiro de Comércio de Emissões (Lei 15.042/2024) e o potencial de gerar créditos de carbono.</p>
    <section class="cartao" aria-labelledby="h-cb-sbce"><h2 id="h-cb-sbce">Enquadramento no SBCE</h2><div class="grade">${cartao("cb-sb1", "Emissões diretas (escopo 1)", T(R.e1), "tCO₂e por ano", `<span class="selo ${quadro[0]}">${sit === "voluntario" ? "Abaixo do limite" : sit === "relato" ? "Deve monitorar e relatar" : "Deve relatar e conciliar"}</span>`)}${cartao("cb-sb2", "Pronto para o SBCE?", `<span class="selo ${pronto[0]}">${pronto[1]}</span>`, "")}</div>
      <p>${E(quadro[1])}</p><p class="t2 pq">Os limites valem por instalação ou fonte e olham as emissões diretas; a lei deixou de fora das obrigações a produção agropecuária primária. Os ativos do sistema são a Cota Brasileira de Emissões (CBE) e o Certificado de Redução ou Remoção Verificada de Emissões (CRVE). ${aviso("regulamentação em publicação pelo órgão gestor: conferir regras, prazos e formato do relato antes de decidir")}</p>
      <h3 class="t3">Lista de preparação</h3><div>${itens.map(([k, r, auto]) => `<div><label for="cb-sb-${k}" style="display:flex;gap:8px;align-items:center"><input id="cb-sb-${k}" type="checkbox" data-carb-campo="sbce.${k}" ${ck[k] ? "checked" : ""}> ${E(r)}${auto && !ck[k] ? ' <span class="selo in">sugestão: os dados indicam que já está feito</span>' : ""}</label></div>`).join("")}</div></section>
    <section class="cartao" aria-labelledby="h-cb-cred"><h2 id="h-cb-cred">Potencial de créditos</h2>${tabela("Projetos com potencial de crédito", ["Projeto", "Potencial (tCO₂e por ano)", "Famílias de metodologia", "Adicionalidade e permanência"], proj.map(([n, t, m, a]) => `<tr><th scope="row">${E(n)}</th><td>${T(t)}</td><td>${E(m)}</td><td>${E(a)}</td></tr>`))}
      <p class="t2 pq">${aviso("nomes das metodologias citados para orientar; confirmar a versão vigente no registro escolhido (Verra, Gold Standard, mecanismo do Acordo de Paris ou CRVE do SBCE)")}</p>
      <p class="t2 pq">Biocombustível: o CBIO (RenovaBio, Lei 13.576/2017) só é emitido por produtor ou importador certificado de biocombustível. Quem produz biodiesel do óleo de cozinha ou biometano para venda pode avaliar a certificação; para uso próprio, o ganho aparece como emissão evitada.</p></section>`; }

function metodologia(F){ return `<details><summary class="t2">Metodologia e normas</summary><ul>
    <li><strong>GHG Protocol</strong> (WRI e WBCSD): padrão corporativo (escopos 1, 2 e 3, ano-base, controle operacional), orientação do escopo 2 (relato duplo: localização e escolha de compra) e padrão do escopo 3 (15 categorias).</li>
    <li><strong>Programa Brasileiro GHG Protocol</strong>: adaptação brasileira, com a ferramenta de cálculo e as especificações do programa (fatores do SIN do MCTI, mistura de biocombustíveis, CO₂ biogênico informado à parte).</li>
    <li><strong>ISO 14064-1:2018</strong>: inventário organizacional; as categorias 1 (diretas), 2 (energia importada) e 3 a 6 (indiretas) correspondem aos escopos 1, 2 e 3.</li>
    <li><strong>Lei 15.042/2024</strong>: cria o SBCE, com limites de 10 mil e 25 mil tCO₂e por ano para relato e para obrigações.</li>
    <li><strong>Pegada do servidor</strong>: GHG Protocol (energia no escopo 2, ou no escopo 3, categoria 1, quando a hospedagem é comprada; fabricação no escopo 3, categoria 2), Orientação Setorial de TIC do GHG Protocol e Recomendação ITU-T L.1450 (métodos para a pegada de organizações do setor de tecnologia). Medição por medidor, contador do processador (RAPL) ou potência da classe; PUE para datacenter.</li>
    <li><strong>IPCC 2006</strong> e Refinamento 2019: fatores de combustão, agropecuária, solo e resíduos (nível 1). <strong>IPCC AR5 e AR6</strong>: GWP de 100 anos.</li>
    <li>Fatores com fonte e ano em sistema/physis-fatores-emissao.json; os marcados “verificar” são conferidos antes de qualquer relato oficial. Base de dados por projeto: quem troca um fator registra o motivo.</li></ul>
    <p class="t2 pq">Os textos acima resumem as normas com palavras próprias da Physis; não substituem a leitura dos documentos nem a verificação por terceira parte.</p></details>`; }

/* ════════ tela inteira ════════ */
function tela(){ const F = base(), h1 = "<h1>Carbono</h1>";
  if (!F) return h1 + `<p class="faixa al" role="alert">A base de fatores de emissão não foi carregada. Rode ferramentas/embutir_bases.py para embutir sistema/physis-fatores-emissao.json no painel.</p>`;
  const c = ler(), ctx = contexto(c), R = calcular(c, ctx, F), u = UI(), sub = SUBS.some(s => s[0] === u.carbAba) ? u.carbAba : "inventario";
  const chips = `<div class="chips" role="group" aria-label="Partes do Carbono">${SUBS.map(([k, n]) => `<button type="button" id="cb-aba-${k}" data-carb-aba="${k}" aria-pressed="${k === sub}">${E(n)}</button>`).join("")}</div>`;
  const corpo = { inventario:abaInventario, e1:abaE1, e2:abaE2, e3:abaE3, remocoes:abaRemocoes, metas:abaMetas, sbce:abaSbce }[sub](c, R, F, ctx);
  return `${h1}<p class="t2 apoio">Inventário de emissões pelo GHG Protocol: escopo 1 (fontes próprias), escopo 2 (energia comprada) e escopo 3 (cadeia de valor), com remoções e emissões evitadas à parte, metas até o net zero e a preparação para o SBCE.</p>${chips}${corpo}${metodologia(F)}`; }

/* resumo para o Relatório ESG e outros módulos */
function resumo(){ const F = base(); if (!F) return null; const c = ler(), R = calcular(c, contexto(c), F);
  return { ano:c.ano, gwp:R.gwp, e1:R.e1, e2_loc:R.e2_loc, e2_mkt:R.e2_mkt, e3:R.e3, total:R.total, por_gas:R.porGas, por_grupo:R.porGrupo, por_cat:R.porCat, bio_t:R.bio_t, fora_t:R.fora_t, remocoes_t:R.remocoes_t, evitadas:R.evitadas, evitadas_t:R.evitadas_t, solar_kwh:num(c.solar_kwh),
    medido:R.medido, incerteza:R.incerteza, int_m2:R.int_m2, int_prod:R.int_prod, producao_un:R.producao_un, kwh:R.kwh, fator_rede:R.fator_rede, metas:{ ano_base:R.metas.ano_base, base_t:R.metas.base_t, pct:R.metas.pct, alvo:R.metas.alvo, net_zero:R.metas.net_zero, medidas_t:R.metas.medidas_t },
    sbce:R.sbce, sbce_check:c.sbce, cats3:c.e3.cats, linhas:R.linhas.length }; }

/* ════════ eventos: um ouvinte guardado por tipo ════════ */
function refocar(id){ const x = pegar(id); if (x && x.focus) x.focus(); }
const redesenhar = () => { if (typeof desenhar === "function") desenhar(false); };
if (typeof document !== "undefined" && !window.__carbEventos){ window.__carbEventos = true;
  document.addEventListener("change", ev => { const t = ev.target; if (!t || !t.dataset) return;
    if (t.dataset.carbCampo != null){ const c = ler(); porCaminho(c, t.dataset.carbCampo, t.type === "checkbox" ? t.checked : t.value.trim());
      if (/^refrig\.\d+\.equip$/.test(t.dataset.carbCampo)) { /* novo equipamento: volta à taxa típica */ porCaminho(c, t.dataset.carbCampo.replace(/equip$/, "taxa_pct"), ""); }
      gravar(c); redesenhar(); refocar(t.id); return; }
    if (t.dataset.carbCat != null){ const c = ler(), k = Number(t.dataset.carbCat); c.e3.cats = (c.e3.cats || []).map(Number).filter(x => x !== k); if (t.checked) c.e3.cats.push(k); c.e3.cats.sort((a, b) => a - b); gravar(c); redesenhar(); refocar(t.id); } });
  document.addEventListener("click", ev => { const b = ev.target && ev.target.closest ? ev.target.closest("button") : null; if (!b || !b.dataset) return; const F = base();
    if (b.dataset.carbAba){ UI().carbAba = b.dataset.carbAba; redesenhar(); refocar("cb-aba-" + b.dataset.carbAba); return; }
    if (!F) return;
    if (b.dataset.carbAdd){ const c = ler(), p = b.dataset.carbAdd, L = LISTAS(F)[p]; if (!L) return; const arr = pegarCaminho(c, p) || []; arr.push(clone(L.novo)); porCaminho(c, p, arr); gravar(c); redesenhar();
      const campo = L.campos.find(x => x[2] !== "sel") || L.campos[0]; refocar(idDe(p + "." + (arr.length - 1) + "." + campo[0])); return; }
    if (b.dataset.carbDel){ const [p, i] = b.dataset.carbDel.split(":"), c = ler(), arr = pegarCaminho(c, p) || []; arr.splice(+i, 1); porCaminho(c, p, arr); gravar(c); redesenhar(); refocar(idDe(p) + "-add"); return; }
    if (b.dataset.carbSug){ const c = ler(), ctx = contexto(c), k = b.dataset.carbSug;
      if (k === "avac" && ctx.avac_kwt) c.refrig.push({ gas:"R-410A", modo:"carga", kg:"", carga: String(Math.round(ctx.avac_kwt * F.vazamento.carga_kg_por_kw.valor)), equip:"split", taxa_pct:"", q:"estimado" });
      if (k === "compras" && ctx.compras_rs) c.e3.gastos.push({ cat:"manufaturados", valor: String(Math.round(ctx.compras_rs)) });
      if (k === "capital" && ctx.capital_rs) c.e3.capital = String(Math.round(ctx.capital_rs));
      gravar(c); redesenhar(); refocar("cb-aba-" + (UI().carbAba || "inventario")); } }); }

const I18N_SERVIDOR = { "Pegada do servidor (sistema digital)":"Server footprint (digital system)", "Potência agora":"Power now", "Energia":"Energy", "kWh por mês":"kWh per month", "Operação (energia)":"Operation (energy)", "Fabricação (escopo 3, cat. 2)":"Manufacturing (scope 3, cat. 2)", "dividida pelos anos de uso":"spread over the years of use",
  "Equipamento":"Equipment", "Onde fica":"Location", "Método":"Method", "Energia (tCO₂e por ano)":"Energy (tCO₂e per year)", "Fabricação (tCO₂e por ano)":"Manufacturing (tCO₂e per year)", "No inventário":"In the inventory", "parte do escopo 2 já contado":"part of scope 2 already counted", "soma no escopo 2":"added to scope 2", "soma no escopo 3, cat. 1":"added to scope 3, cat. 1",
  "Incluir a pegada do servidor no inventário":"Include the server footprint in the inventory", "Como contar a energia do servidor":"How to count the server energy", "Automático: pelo lugar de cada máquina (recomendado)":"Automatic: by where each machine is (recommended)", "Já está nas contas de luz do inventário (só informar)":"Already in the inventory electricity bills (report only)", "Somar como fonte própria":"Add as its own source",
  "Como reduzir":"How to reduce", "Exemplo (modo demonstração).":"Example (demo mode).", "Servidor do sistema digital":"Digital system server", "Hospedagem do sistema digital":"Digital system hosting", "Fabricação do servidor":"Server manufacturing", "no lugar do inventário":"at the inventory site", "fora (datacenter ou outro lugar)":"elsewhere (datacenter or other site)" };
window.PhysisCarbono = { tela, calcular, migrar, ler, gravar, contexto, resumo, kwhAno, base, num, servidorInventario, i18nServidor: I18N_SERVIDOR, versao:"carbono-ghg-3" };
window.telaCarbono = tela;   /* global: chamada pelo nome telaCarbono() na hora de desenhar (TELAS.carbono) */
})();
