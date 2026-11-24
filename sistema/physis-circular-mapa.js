/* physis-circular-mapa.js — parte "Mapa e indicadores" da aba Economia circular.
   Contrato com a plataforma: define telaCircularMapa(dados) (uma section com h2, sem título h1: entra dentro de telaCircular).
   dados = resposta de GET api/gis/residuos?lat=&lon=&raio= (destinos de resíduos guardados no servidor). Sem "dados", o
   módulo busca sozinho no servidor (ui.rcm) para o lugar de gisLugar(). Sem servidor, mostra só os indicadores do plano.
   O plano vem de rcLer() da plataforma (localStorage "physis-residuos-plano": lista de { tipo, qtd, un, rota }, com
   RC_ROTAS[rota].destino, RC_UN e RC_DESVIADO) — com cópia mínima das tabelas se o módulo rodar sozinho.
   Mapa: SVG desenhado aqui, sem fundo de terceiros (projeção local em volta do lugar, anéis de distância, legenda,
   pontos focáveis pelo teclado) e a mesma informação em tabelas. Se o servidor tiver o MapLibre (/vendor/) e o
   mapa da região (/mapas/regiao.pmtiles), um botão abre o mapa com fundo, opcional.
   CO₂ do transporte: espelho de residuos_gis.co2_transporte (fator por t·km, ou viagens de caminhão a diesel).
   Globais usadas na hora de desenhar: esc, n2, numBr, el, ui, desenhar; se existirem: gisLugar, rcLer, rcKgMes,
   RC_ROTAS, RC_POR_ID, RC_DESVIADO, calcLer, calcGravar. Estado: calcLer("rc-mapa"); seleção e filtros em ui.rcm*. */
(function () {
"use strict";
/* rótulo que vai cortado no desenho: em inglês, traduz pela tradução da plataforma (trad) antes de cortar */
const traduzRotulo = s => { try { if (/^en/i.test(document.documentElement.lang || "") && typeof trad === "function") { const v = trad(s); if (v != null) return String(v).trim(); } } catch (e) {} return String(s == null ? "" : s); };

/* categoria -> [rótulo, cor (PALETA.md), forma] */
const CAT = {
  aterro:["Aterro (sanitário ou não informado)", "#7A2214", "quad"], aterro_controlado:["Aterro controlado", "#A85432", "quad"],
  lixao:["Lixão (vazadouro a céu aberto)", "#2A1215", "cruz"], transbordo:["Estação de transbordo", "#8A6410", "quad"],
  cooperativa:["Cooperativa ou associação de catadores", "#1F4A1C", "circ"], reciclagem:["Centro de reciclagem ou triagem", "#4A8A5A", "circ"],
  ecoponto:["Ecoponto", "#546A7B", "diam"], pev:["Ponto de entrega voluntária (PEV)", "#2F5E4E", "circ"], sucata:["Ferro-velho ou sucata", "#546A7B", "diam"],
  compostagem:["Compostagem", "#8A6A1F", "tri"], rcc:["Resíduos da construção (RCC, ATT)", "#5F6659", "diam"], ete:["Estação de tratamento de esgoto", "#3D2A5C", "tri"] };
/* destino do plano -> categorias que recebem (espelho de residuos_gis.CATEGORIAS_POR_DESTINO) */
const POR_DESTINO = { reciclagem:["cooperativa", "reciclagem", "ecoponto", "sucata", "pev"], reversa:["ecoponto", "pev", "reciclagem"],
  compostagem:["compostagem"], aterro2:["aterro", "aterro_controlado", "transbordo"] };
/* cópia mínima das tabelas do painel, só se o módulo rodar sem elas */
const ROTAS_MIN = { compostagem:["Compostagem no lugar", "compostagem", 1], vermi:["Minhocário", "compostagem", 1], larvas:["Larvas", "reuso", 1], biodigestor:["Biodigestor", "reuso", 1],
  biodiesel:["Biodiesel", "reuso", 1], filamento:["Filamento 3D", "reuso", 1], maker:["Oficina maker", "reuso", 1], agregado:["Agregado reciclado na obra", "reuso", 1],
  biomassa:["Biomassa para energia", "reuso", 1], biochar:["Biocarvão", "reuso", 1], reuso:["Reúso ou doação", "reuso", 1], reciclagem:["Reciclagem", "reciclagem", 0],
  reversa:["Logística reversa", "reversa", 0], aterro:["Aterro sanitário (rejeito)", "aterro2", 0], aterro1:["Aterro de resíduos perigosos", "aterro1", 0], incineracao:["Incineração", "incineracao", 0] };
const UN_MIN = { kg_mes:1, kg_sem:52 / 12, kg_dia:30, t_mes:1000, l_mes:0.92 };
const DESVIADO_MIN = ["reuso", "reciclagem", "compostagem", "reversa"];
const DIESEL_KG_L = (typeof PhysisCalc !== "undefined" && PhysisCalc.premissa("combustivel.diesel")) || 2.671;   /* premissa combustivel.diesel da base (contas comuns); 2,671 só se o bloco faltar */
const RAIOS = [5, 10, 20, 30, 50], MAX_FOCO = 60;
const RUMOS = ["norte", "nordeste", "leste", "sudeste", "sul", "sudoeste", "oeste", "noroeste"];

/* ════════ Contas ════════ */
function haversineKm(la1, lo1, la2, lo2) { const r = Math.PI / 180, dp = (la2 - la1) * r, dl = (lo2 - lo1) * r;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(la1 * r) * Math.cos(la2 * r) * Math.sin(dl / 2) ** 2; return 2 * 6371.0088 * Math.asin(Math.sqrt(a)); }
/* espelho de residuos_gis.co2_transporte */
function co2Transporte(kgMes, distKm, o) { o = o || {}; const t = Math.max(0, kgMes || 0) / 1000, r = { t_mes:t, t_km:t * distKm, viagens:null, litros:null, kg_co2_mes:null, metodo:null };
  if (o.fator > 0) { r.kg_co2_mes = r.t_km * o.fator; r.metodo = "fator por t·km"; }
  else if (o.consumo > 0 && o.carga > 0) { const v = t > 0 ? Math.ceil(t / o.carga) : 0, l = v * distKm * (o.ida === false ? 1 : 2) / o.consumo;
    Object.assign(r, { viagens:v, litros:l, kg_co2_mes:l * (o.diesel || DIESEL_KG_L), metodo:"viagens de caminhão a diesel" }); }
  return r; }
const rotaInfo = id => { if (typeof RC_ROTAS === "object" && RC_ROTAS[id]) { const x = RC_ROTAS[id]; return { nome:x.nome, destino:x.destino, interno:!!x.interno }; }
  const m = ROTAS_MIN[id]; return m ? { nome:m[0], destino:m[1], interno:!!m[2] } : { nome:id || "—", destino:"", interno:false }; };
const nomeTipo = id => (typeof RC_POR_ID === "object" && RC_POR_ID[id]) ? RC_POR_ID[id].nome : id;
const kgMes = r => typeof rcKgMes === "function" ? rcKgMes(r) : ((typeof numBr === "function" ? numBr(r.qtd) : parseFloat(r.qtd)) || 0) * (UN_MIN[r.un] || 1);
/* plano de resíduos + linhas extras da parte Esgoto e biogás (rcExtrasFluxo da plataforma: lodo do tratamento ou esgoto que
   vai ao biodigestor, marcadas extra:true): entram no fluxo, mas não no total nem no desvio do aterro (que são de resíduos sólidos) */
function planoLer() { let l = [];
  if (typeof rcLer === "function") l = rcLer();
  else { try { const x = JSON.parse(localStorage.getItem("physis-residuos-plano") || "[]"); l = Array.isArray(x) ? x : []; } catch (e) { l = []; } }
  try { if (typeof rcExtrasFluxo === "function") l = l.concat(rcExtrasFluxo()); } catch (e) {}
  return l; }
const desviados = () => (typeof RC_DESVIADO !== "undefined" && Array.isArray(RC_DESVIADO)) ? RC_DESVIADO : DESVIADO_MIN;
function categoriasDoItem(r, info) { if (info.interno) return []; if (r.tipo === "rcc") return ["rcc"].concat(POR_DESTINO.reciclagem); return POR_DESTINO[info.destino] || []; }
function maisProximo(pontos, cats) { let m = null; (pontos || []).forEach(p => { if (cats.includes(p.categoria) && (!m || p.dist_km < m.dist_km)) m = p; }); return m; }

/* Indicadores do plano: kg/mês por destino, % de desvio do aterro e CO₂ do transporte até o destino mais próximo */
function indicadores(plano, pontos, cfg) { const linhas = [], porRota = {}; let tot = 0, desv = 0;
  plano.forEach(r => { const kg = kgMes(r), info = rotaInfo(r.rota); if (!r.extra) { tot += kg; if (desviados().includes(info.destino)) desv += kg;
    porRota[info.nome] = (porRota[info.nome] || 0) + kg; }
    const cats = categoriasDoItem(r, info), alvo = cats.length ? maisProximo(pontos, cats) : null;
    const dist = alvo ? alvo.dist_km * (cfg.tort > 0 ? cfg.tort : 1) : null;
    const tp = (typeof RC_POR_ID === "object" && RC_POR_ID[r.tipo]) || null;
    /* nomes sempre preenchidos: linhas extras (lodo do esgoto, águas negras) podem não ter grupo ou nome na tabela; sem isso o fluxo mostrava "undefined" */
    linhas.push({ grupo:(tp && tp.grupo) || "Outros", classe:(tp && tp.classe) || "?", tipo:nomeTipo(r.tipo) || "Tipo não informado", rota:info.nome || r.rota || "Rota não informada", interno:info.interno, kg, alvo, dist, co2:dist != null ? co2Transporte(kg, dist, cfg) : null, semCategoria:!info.interno && !cats.length }); });
  return { linhas, tot, desv, pct:tot ? desv / tot : null, porRota, co2:linhas.reduce((s, l) => s + ((l.co2 && l.co2.kg_co2_mes) || 0), 0),
    temCo2:linhas.some(l => l.co2 && l.co2.kg_co2_mes != null) }; }

/* ════════ Fluxo dos resíduos: geração por tipo → separação → rota → destino (distância e CO₂) ════════ */
const COR_GRUPO = { "Orgânicos":"#8A6A1F", "Recicláveis":"#4A8A5A", "Obra e madeira":"#5F6659", "Perigosos e logística reversa":"#7A2214", "Rejeito":"#4A4F44", "Outros":"#4A4F44" };
function destinoDe(l) { return l.interno ? "No próprio lugar" : l.alvo ? (l.alvo.nome || (CAT[l.alvo.categoria] || [l.alvo.categoria])[0]) : l.semCategoria ? "Empresa licenciada (a contratar)" : "Destino a definir (nenhum no raio)"; }
function fluxo(I) { const L = I.linhas.filter(l => l.kg > 0); if (!L.length) return null;
  const col = [{}, {}, {}, {}], lig = [{}, {}, {}], soma = (o, k, v, extra) => { o[k] = o[k] || Object.assign({ v:0 }, extra || {}); o[k].v += v; };
  L.forEach(l => { const ks = [l.tipo, l.grupo, l.rota, destinoDe(l)], cor = COR_GRUPO[l.grupo] || "#4A4F44";
    soma(col[0], ks[0], l.kg, { cor }); soma(col[1], ks[1], l.kg, { cor }); soma(col[2], ks[2], l.kg, { cor:"#1A4D2E" });
    soma(col[3], ks[3], l.kg, { cor:l.interno ? "#1F4A1C" : "#8A6410", dist:l.dist, co2:0 }); if (l.co2 && l.co2.kg_co2_mes) col[3][ks[3]].co2 += l.co2.kg_co2_mes;
    for (let i = 0; i < 3; i++) soma(lig[i], ks[i] + "→" + ks[i + 1], l.kg, { a:ks[i], b:ks[i + 1], cor }); });
  return { col, lig, tot:L.reduce((s, l) => s + l.kg, 0), L }; }
function sankeySvg(F) { const W = 900, H = 300, nw = 12, pad = 10, xs = [8, 200, 392, 584], maxN = Math.max(...F.col.map(c => Object.keys(c).length));
  const k = (H - 20 - pad * (maxN - 1)) / F.tot, pos = F.col.map(c => { let y = 10; const o = {}; Object.entries(c).sort((a, b) => b[1].v - a[1].v).forEach(([n, x]) => { o[n] = { y, h:Math.max(1, x.v * k), sa:0, ea:0, x }; y += x.v * k + pad; }); return o; });
  /* o rótulo cortado não tem par em inglês: traduz (trad() do painel) antes de cortar */
  const corta = (s, n) => { s = traduzRotulo(s); return s.length > n ? s.slice(0, n - 1) + "…" : s; };
  let fitas = "";
  F.lig.forEach((ls, i) => Object.values(ls).sort((a, b) => b.v - a.v).forEach(l => { const A = pos[i][l.a], B = pos[i + 1][l.b], t = l.v * k, x0 = xs[i] + nw, x1 = xs[i + 1], y0 = A.y + A.sa, y1 = B.y + B.ea, xm = (x0 + x1) / 2; A.sa += t; B.ea += t;
    fitas += `<path d="M${x0} ${y0.toFixed(1)}C${xm} ${y0.toFixed(1)} ${xm} ${y1.toFixed(1)} ${x1} ${y1.toFixed(1)}L${x1} ${(y1 + t).toFixed(1)}C${xm} ${(y1 + t).toFixed(1)} ${xm} ${(y0 + t).toFixed(1)} ${x0} ${(y0 + t).toFixed(1)}Z" fill="${l.cor}" fill-opacity="0.35"><title>${esc(l.a)} → ${esc(l.b)}: ${f1(l.v, 0)} kg/mês</title></path>`; }));
  const nos = pos.map((c, i) => Object.entries(c).map(([n, p]) => { const ult = i === 3, tx = xs[i] + nw + 4, extra = ult && p.x.dist != null ? ` · ${f1(p.x.dist, 1)} km${p.x.co2 ? " · " + f1(p.x.co2, 1) + " kg CO₂e" : ""}` : "";
    return `<rect x="${xs[i]}" y="${p.y.toFixed(1)}" width="${nw}" height="${p.h.toFixed(1)}" fill="${p.x.cor}"><title>${esc(n)}: ${f1(p.x.v, 0)} kg/mês${esc(extra)}</title></rect><text x="${tx}" y="${(p.y + p.h / 2 + 4).toFixed(1)}" font-size="11" fill="#1B1F23" text-anchor="start">${esc(corta(n, ult ? 30 : 24))} (${f1(p.x.v, 0)})${esc(extra)}</text>`; }).join("")).join("");
  const cab = ["Geração", "Separação", "Rota", "Destino"].map((t, i) => `<text x="${xs[i]}" y="8" font-size="10" font-weight="700" fill="#4A4F44">${t}</text>`).join("");
  return `<svg viewBox="0 -6 ${W} ${H + 6}" width="100%" style="max-width:${W}px" role="img" aria-label="Fluxo dos resíduos em kg por mês: geração por tipo, separação, rota e destino; os números estão na tabela">${cab}${fitas}${nos}</svg>`; }
function secaoFluxo(I) { const F = fluxo(I); if (!F) return "";
  return `<section class="cartao" aria-labelledby="h-rcm-fluxo"><h3 id="h-rcm-fluxo" class="t3">Fluxo dos resíduos</h3><p class="t2 pq">Da geração ao destino, em kg por mês: largura de cada faixa = quantidade. Distância em linha reta até o destino mais próximo do tipo certo.</p>
    <div class="rolagem">${sankeySvg(F)}</div>
    <div class="rolagem"><table><caption>Fluxo de cada resíduo: geração, separação, rota, destino, distância e CO₂ do transporte</caption><thead><tr><th scope="col">Resíduo</th><th scope="col">Classe</th><th scope="col">Separação</th><th scope="col">kg/mês</th><th scope="col">Rota</th><th scope="col">Destino</th><th scope="col">Distância (km)</th><th scope="col">kg CO₂e/mês</th></tr></thead><tbody>
    ${F.L.map(l => `<tr><th scope="row">${esc(l.tipo)}</th><td>${esc(l.classe)}</td><td>${esc(l.grupo)}</td><td>${f1(l.kg, 0)}</td><td>${esc(l.rota)}</td><td>${esc(destinoDe(l))}</td><td>${l.interno ? "0" : f1(l.dist, 1)}</td><td>${l.interno ? "0" : l.co2 && l.co2.kg_co2_mes != null ? f1(l.co2.kg_co2_mes, 1) : "—"}</td></tr>`).join("")}</tbody></table></div></section>`; }
function metodoCircular() { return `<details class="cartao"><summary><h3 class="t3" style="display:inline">Metodologia e normas</h3></summary><ul>
  <li><strong>Classificação:</strong> ABNT NBR 10004 (conferir a edição vigente) separa os resíduos em classe I (perigosos) e classe II (não perigosos: II A não inertes e II B inertes), pela origem, pelas listagens e, quando preciso, pelos ensaios de lixiviação (NBR 10005) e de solubilização (NBR 10006). A classe de cada tipo no plano é a usual; resíduo de processo próprio precisa de laudo.</li>
  <li><strong>Amostragem:</strong> ABNT NBR 10007 — como coletar, guardar e preservar a amostra que vai ao laboratório para a classificação.</li>
  <li><strong>Ordem de prioridade:</strong> Lei 12.305/2010 (Política Nacional de Resíduos Sólidos, regulamentada pelo Decreto 10.936/2022): não gerar, reduzir, reutilizar, reciclar, tratar e só então dispor os rejeitos de forma ambientalmente adequada. Logística reversa obrigatória para pilhas e baterias, pneus, óleos lubrificantes, lâmpadas, eletroeletrônicos e embalagens de agrotóxicos, entre outros. Grandes geradores fazem o Plano de Gerenciamento de Resíduos Sólidos (PGRS).</li>
  <li><strong>Transporte e rastreio:</strong> Manifesto de Transporte de Resíduos (MTR) emitido no SINIR a cada saída para destino externo, com o Certificado de Destinação Final (CDF) de volta e a declaração periódica (DMR), conforme a Portaria MMA 280/2020; estados podem ter sistema próprio integrado.</li>
  <li><strong>Construção civil e saúde:</strong> CONAMA 307/2002 (classes A a D de RCC e áreas de transbordo e triagem); resíduos de serviços de saúde pela CONAMA 358/2005 e pela RDC ANVISA 222/2018.</li>
  <li><strong>Desvio do aterro:</strong> reúso, reciclagem, compostagem e logística reversa contam como desvio; a meta de 90% segue o critério TRUE / LEED Zero Waste, o mesmo da tela de resíduos.</li>
  <li><strong>Destinos no mapa:</strong> OpenStreetMap (categoria deduzida das etiquetas e do nome) e bases importadas (SINIR, MUNIC, órgãos estaduais). Antes de contratar, conferir licença de operação, cadastro no SINIR e a classe que o destino pode receber.</li>
  <li><strong>CO₂ do transporte:</strong> t·km × fator do projeto, ou viagens de caminhão × distância × 2 ÷ consumo × fator do diesel (premissa da Physis). Distância em linha reta (multiplicador estrada/linha reta editável). Estimativa de planejamento.</li></ul></details>`; }

/* ════════ Estado e dados ════════ */
function cfgLer() { let o = {}; if (typeof calcLer === "function") o = calcLer("rc-mapa") || {}; else { try { o = JSON.parse(localStorage.getItem("physis-calc-rc-mapa") || "{}") || {}; } catch (e) {} } return o; }
function cfgGravar(o) { if (typeof calcGravar === "function") return calcGravar("rc-mapa", o); try { localStorage.setItem("physis-calc-rc-mapa", JSON.stringify(o)); } catch (e) {} }
const num = s => { if (s == null || String(s).trim() === "") return null; const v = typeof numBr === "function" ? numBr(s) : parseFloat(String(s).replace(",", ".")); return v == null || !isFinite(v) ? null : v; };
function carregar(raio) { const L = typeof gisLugar === "function" ? gisLugar() : null; if (!L) return { semLugar:true };
  if (ui.modo !== "hub") return { semServidor:true };
  const k = L.lat.toFixed(3) + "," + L.lon.toFixed(3) + ":" + raio; if (ui.rcm && ui.rcm.k === k) return ui.rcm; ui.rcm = { k, carregando:true };
  fetch(`api/gis/residuos?lat=${L.lat}&lon=${L.lon}&raio=${raio}`, { cache:"no-store" }).then(r => r.json()).then(j => { ui.rcm = Object.assign(j, { k }); desenhar(false); })
    .catch(() => { ui.rcm = { k, ok:false, avisos:["servidor sem resposta"] }; desenhar(false); });
  return ui.rcm; }

/* ════════ Desenho ════════ */
const f1 = (v, c) => v == null || !isFinite(v) ? "—" : n2(v, c == null ? 1 : c);
const rumoTxt = g => RUMOS[Math.round(((g % 360) + 360) % 360 / 45) % 8];
function forma(f, x, y, s, cor) { const a = s, b = s * 1.15;
  if (f === "quad") return `<rect class="rcm-f" x="${(x - a).toFixed(1)}" y="${(y - a).toFixed(1)}" width="${(2 * a).toFixed(1)}" height="${(2 * a).toFixed(1)}" fill="${cor}" stroke="#FFFFFF" stroke-width="1.5"/>`;
  if (f === "tri") return `<polygon class="rcm-f" points="${x.toFixed(1)},${(y - b).toFixed(1)} ${(x + b).toFixed(1)},${(y + a).toFixed(1)} ${(x - b).toFixed(1)},${(y + a).toFixed(1)}" fill="${cor}" stroke="#FFFFFF" stroke-width="1.5"/>`;
  if (f === "diam") return `<polygon class="rcm-f" points="${x.toFixed(1)},${(y - b).toFixed(1)} ${(x + b).toFixed(1)},${y.toFixed(1)} ${x.toFixed(1)},${(y + b).toFixed(1)} ${(x - b).toFixed(1)},${y.toFixed(1)}" fill="${cor}" stroke="#FFFFFF" stroke-width="1.5"/>`;
  if (f === "cruz") return `<g class="rcm-f"><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${b.toFixed(1)}" fill="#FFFFFF" stroke="${cor}" stroke-width="2"/><path d="M${(x - a * 0.7).toFixed(1)} ${(y - a * 0.7).toFixed(1)}L${(x + a * 0.7).toFixed(1)} ${(y + a * 0.7).toFixed(1)}M${(x + a * 0.7).toFixed(1)} ${(y - a * 0.7).toFixed(1)}L${(x - a * 0.7).toFixed(1)} ${(y + a * 0.7).toFixed(1)}" stroke="${cor}" stroke-width="2.5"/></g>`;
  return `<circle class="rcm-f" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${a.toFixed(1)}" fill="${cor}" stroke="#FFFFFF" stroke-width="1.5"/>`; }
const descr = p => `${p.nome || "Sem nome"}, ${(CAT[p.categoria] || [p.categoria])[0]}, ${f1(p.dist_km, 1)} km a ${rumoTxt(p.rumo || 0)}`;

function mapaSvg(d, pontos, raio, sel) { const S = 360, c = S / 2, Rp = 160, lat0 = d.lat, lon0 = d.lon, kx = 111.32 * Math.cos(lat0 * Math.PI / 180), ky = 110.574;
  const pos = p => [c + (p.lon - lon0) * kx / raio * Rp, c - (p.lat - lat0) * ky / raio * Rp];
  const aneis = [0.25, 0.5, 0.75, 1].map(f => `<circle cx="${c}" cy="${c}" r="${(Rp * f).toFixed(1)}" fill="none" stroke="#D9D3C2" stroke-dasharray="${f === 1 ? "0" : "3 3"}"/><text x="${(c + 3).toFixed(1)}" y="${(c - Rp * f - 3).toFixed(1)}" font-size="10" fill="#4A4F44">${f1(raio * f, raio * f < 10 && raio * f % 1 ? 1 : 0)} km</text>`).join("");
  const ord = pontos.slice().sort((a, b) => b.dist_km - a.dist_km);   /* os mais perto por cima */
  const foco = new Set(pontos.slice(0, MAX_FOCO).map(p => p.id));
  const pts = ord.map(p => { const [x, y] = pos(p), [nome, cor, f] = CAT[p.categoria] || [p.categoria, "#4A4F44", "circ"], i = pontos.indexOf(p), s = p.id === sel ? 8 : 5.5;
    return foco.has(p.id) ? `<g class="rcm-p" tabindex="0" role="button" aria-pressed="${p.id === sel}" aria-label="${esc(descr(p))}" data-rcm-p="${i}"><title>${esc(descr(p))}</title>${forma(f, x, y, s, cor)}</g>`
      : `<g aria-hidden="true">${forma(f, x, y, 4, cor)}</g>`; }).join("");
  return `<svg viewBox="0 0 ${S} ${S}" width="100%" style="max-width:${S}px;background:#FAF9F5;border:1px solid #D9D3C2;border-radius:10px" role="group" aria-label="Mapa dos destinos em volta do lugar, raio de ${raio} km, ${pontos.length} pontos; a lista completa está na tabela abaixo">
    ${aneis}<text x="${S - 14}" y="22" font-size="13" font-weight="700" text-anchor="middle" fill="#1B1F23">N</text><path d="M${S - 14} 26 l-5 12 h10 z" fill="#1B1F23"/>
    ${pts}<circle cx="${c}" cy="${c}" r="9" fill="none" stroke="#1A4D2E" stroke-width="3"/><circle cx="${c}" cy="${c}" r="3.5" fill="#1A4D2E"/><text x="${c}" y="${c + 24}" font-size="11" text-anchor="middle" fill="#1A4D2E" font-weight="700" stroke="#FAF9F5" stroke-width="3" paint-order="stroke">o lugar</text></svg>`; }

function legenda(grupos) { const ks = Object.keys(CAT).filter(k => grupos[k]);
  return ks.length ? `<ul class="rcm-leg" aria-label="Legenda do mapa">${ks.map(k => `<li><svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">${forma(CAT[k][2], 9, 9, 5.5, CAT[k][1])}</svg> ${esc(CAT[k][0])} (${grupos[k].n})</li>`).join("")}</ul>` : ""; }

/* barras horizontais, com a tabela como alternativa */
function hbarras(titulo, itens, un, casas, meta) { if (!itens.length) return ""; const W = 360, lh = 26, H = itens.length * lh + 10, L = 130, mx = Math.max(1e-9, ...itens.map(x => x.v), meta || 0);
  const b = itens.map((x, i) => { const w = (W - L - 60) * x.v / mx, y = 5 + i * lh;
    return `<text x="${L - 6}" y="${y + 15}" font-size="11" text-anchor="end" fill="#1B1F23">${esc(traduzRotulo(x.rot).length > 22 ? traduzRotulo(x.rot).slice(0, 21) + "…" : traduzRotulo(x.rot))}</text><rect x="${L}" y="${y + 3}" width="${Math.max(0, w).toFixed(1)}" height="16" fill="${x.cor || "#4A8A5A"}"><title>${esc(x.rot)}: ${f1(x.v, casas)} ${esc(un)}</title></rect><text x="${(L + w + 4).toFixed(1)}" y="${y + 15}" font-size="11" fill="#4A4F44">${f1(x.v, casas)}</text>`; }).join("");
  const m = meta ? `<line x1="${(L + (W - L - 60) * meta / mx).toFixed(1)}" y1="2" x2="${(L + (W - L - 60) * meta / mx).toFixed(1)}" y2="${H - 2}" stroke="#1B1F23" stroke-dasharray="4 3"/>` : "";
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px" role="img" aria-label="${esc(titulo)}; os números estão na tabela">${b}${m}</svg>`; }

function campo(o, k, rot, ph, ajuda) { return `<div><label for="rcm-${k}">${rot}</label><input id="rcm-${k}" type="text" inputmode="decimal" data-rcm-k="${k}" value="${esc(o[k] == null ? "" : o[k])}" placeholder="${esc(ph)}" style="width:100%"${ajuda ? ` aria-describedby="rcm-${k}-a"` : ""}>${ajuda ? `<span id="rcm-${k}-a" class="t2 pq">${ajuda}</span>` : ""}</div>`; }

function telaCircularMapa(dados) { const o = cfgLer(), raio = RAIOS.includes(+o.raio) ? +o.raio : 20, d = dados || carregar(raio);
  ui.rcmDados = d;
  const ok = d && d.ok && Array.isArray(d.pontos), filtro = ui.rcmCat || "", todos = ok ? d.pontos : [], pontos = filtro ? todos.filter(p => p.categoria === filtro) : todos;
  const grupos = ok ? d.grupos || {} : {}, selId = ui.rcmSel && todos.some(p => p.id === ui.rcmSel) ? ui.rcmSel : null, sel = selId ? todos.find(p => p.id === selId) : null;
  const estado = !d ? "" : d.semLugar ? "Local não informado — preencha na página Início (endereço, município, UF e coordenadas) para ver os destinos em volta."
    : d.semServidor ? "O mapa dos destinos usa a base guardada no servidor da plataforma. Sem servidor, só os indicadores do plano aparecem."
    : d.carregando ? "Procurando aterros, cooperativas, ecopontos e outros destinos em volta…" : !ok ? "Base de destinos indisponível agora; o servidor tenta de novo mais tarde." : "";
  const ctrl = `<div class="precos"><div><label for="rcm-raio">Raio da busca</label><select id="rcm-raio" data-rcm-k="raio" style="width:100%">${RAIOS.map(r => `<option value="${r}" ${r === raio ? "selected" : ""}>${r} km</option>`).join("")}</select></div>
      <div><label for="rcm-cat">Mostrar</label><select id="rcm-cat" data-rcm-cat="1" style="width:100%"><option value="">Todos os tipos</option>${Object.keys(CAT).filter(k => grupos[k]).map(k => `<option value="${k}" ${filtro === k ? "selected" : ""}>${esc(CAT[k][0])}</option>`).join("")}</select></div></div>`;
  let mapa = "";
  if (ok) {
    const info = sel ? `<p class="faixa in" role="status" aria-live="polite"><strong>${esc(sel.nome || "Sem nome")}</strong> · ${esc((CAT[sel.categoria] || [sel.categoria])[0])} · ${f1(sel.dist_km, 1)} km em linha reta a ${rumoTxt(sel.rumo || 0)}${sel.materiais && sel.materiais.length ? " · recebe " + esc(sel.materiais.join(", ")) : ""}${sel.operador ? " · " + esc(sel.operador) : ""}${sel.horario ? " · horário " + esc(sel.horario) : ""} · fonte: ${esc(sel.fonte || "")}</p>`
      : `<p class="t2 pq" role="status" aria-live="polite">Escolha um ponto no mapa (Tab e Enter) para ver os detalhes.</p>`;
    const fundo = (typeof window !== "undefined") ? `<div><button type="button" data-rcm-fundo="1" aria-pressed="${!!ui.rcmFundo}">${ui.rcmFundo ? "Fechar o mapa com fundo" : "Abrir o mapa com fundo da região"}</button></div>${ui.rcmFundo ? `<div id="rcm-ml" role="region" aria-label="Mapa com fundo da região (visual; a mesma informação está nas tabelas)" style="height:360px;border:1px solid #D9D3C2;border-radius:10px;margin-top:8px"></div><p id="rcm-ml-aviso" class="t2 pq" role="status"></p>` : ""}` : "";
    const maisProx = Object.keys(CAT).filter(k => grupos[k]).map(k => { const p = grupos[k].mais_proximo;
      return `<tr><th scope="row">${esc(CAT[k][0])}</th><td>${grupos[k].n}</td><td>${esc(p.nome || "Sem nome")}</td><td>${f1(p.dist_km, 1)} km a ${rumoTxt(p.rumo || 0)}</td></tr>`; }).join("");
    const lista = pontos.map(p => `<tr><th scope="row">${esc(p.nome || "Sem nome")}</th><td>${esc((CAT[p.categoria] || [p.categoria])[0])}</td><td>${f1(p.dist_km, 1)}</td><td>${rumoTxt(p.rumo || 0)}</td><td>${esc((p.materiais || []).join(", ") || "—")}</td><td>${esc(p.fonte || "")}</td></tr>`).join("");
    mapa = `<div class="grade"><div>${mapaSvg(d, pontos, d.raio_km || raio, selId)}${pontos.length > MAX_FOCO ? `<p class="t2 pq">Pelo teclado, o mapa percorre os ${MAX_FOCO} pontos mais perto; todos estão na tabela.</p>` : ""}</div><div>${legenda(grupos)}${info}</div></div>${fundo}
      <div class="rolagem"><table><caption>Destino mais próximo de cada tipo (distância em linha reta)</caption><thead><tr><th scope="col">Tipo</th><th scope="col">Quantos no raio</th><th scope="col">Mais próximo</th><th scope="col">Distância</th></tr></thead><tbody>${maisProx || `<tr><td colspan="4">Nenhum destino encontrado no raio.</td></tr>`}</tbody></table></div>
      <details><summary>Todos os ${pontos.length} pontos${filtro ? " deste tipo" : ""}</summary><div class="rolagem"><table><caption>Destinos em volta do lugar, do mais perto ao mais longe</caption><thead><tr><th scope="col">Nome</th><th scope="col">Tipo</th><th scope="col">Distância (km)</th><th scope="col">Direção</th><th scope="col">Materiais</th><th scope="col">Fonte</th></tr></thead><tbody>${lista}</tbody></table></div></details>
      <p class="t2 pq">${esc(d.fonte || "")}${d.atribuicao ? " · " + esc(d.atribuicao) : ""}. ${(d.avisos || []).map(esc).join(" · ")}</p>`;
  }
  /* indicadores do plano */
  const plano = planoLer(), cfg = { fator:num(o.fator), consumo:num(o.consumo), carga:num(o.carga), tort:num(o.tort), ida:o.ida !== "0" }, I = indicadores(plano, ok ? todos : [], cfg);
  const porRota = Object.entries(I.porRota).sort((a, b) => b[1] - a[1]).map(([rot, v]) => ({ rot, v }));
  const desvio = I.pct == null ? [] : [{ rot:"Desviado do aterro", v:I.pct * 100, cor:"#1F4A1C" }, { rot:"Aterro e outros", v:(1 - I.pct) * 100, cor:"#7A2214" }];
  const co2 = I.linhas.filter(l => l.co2 && l.co2.kg_co2_mes != null).map(l => ({ rot:l.tipo, v:l.co2.kg_co2_mes, cor:"#8A6410" }));
  const tabTrans = I.linhas.filter(l => !l.interno).map(l => `<tr><th scope="row">${esc(l.tipo)}</th><td>${esc(l.rota)}</td><td>${f1(l.kg, 0)}</td><td>${l.alvo ? esc(l.alvo.nome || (CAT[l.alvo.categoria] || [""])[0]) : l.semCategoria ? "sem destino no mapa (empresa licenciada)" : "nenhum no raio"}</td><td>${f1(l.dist, 1)}</td><td>${l.co2 ? f1(l.co2.t_km, 1) : "—"}</td><td>${l.co2 && l.co2.kg_co2_mes != null ? f1(l.co2.kg_co2_mes, 1) : "—"}</td></tr>`).join("");
  const painel = `<section class="cartao" aria-labelledby="h-rcm-ind"><h3 id="h-rcm-ind" class="t3">Painel de indicadores</h3>${plano.length ? `
      <div class="grade"><div><h4>Quilos por mês por destino</h4>${hbarras("Quilos por mês por destino", porRota, "kg/mês", 0)}
        <div class="rolagem"><table><caption class="so-leitor">Quilos por mês por destino</caption><thead><tr><th scope="col">Destino</th><th scope="col">kg/mês</th></tr></thead><tbody>${porRota.map(x => `<tr><th scope="row">${esc(x.rot)}</th><td>${f1(x.v, 0)}</td></tr>`).join("")}</tbody></table></div></div>
      <div><h4>Desvio do aterro</h4>${hbarras("Desvio do aterro, meta de 90%", desvio, "%", 0, 90)}
        <p class="t2"><strong>${I.pct == null ? "—" : f1(I.pct * 100, 0) + "%"}</strong> desviado (meta de 90%, linha tracejada). Total ${f1(I.tot, 0)} kg/mês.</p></div>
      <div><h4>CO₂ do transporte</h4>${I.temCo2 ? hbarras("CO₂ do transporte por resíduo", co2, "kg CO₂e/mês", 1) + `<p class="t2"><strong>${f1(I.co2, 1)}</strong> kg CO₂e por mês · ${f1(I.co2 * 12 / 1000, 2)} t por ano</p>`
        : `<p class="t2">Informe o fator por t·km, ou o consumo e a carga do caminhão, para estimar o CO₂.</p>`}</div></div>
      <div class="precos">${campo(o, "fator", "Fator do transporte (kg CO₂e por t·km)", "do projeto", "Opcional. Se vazio, conta por viagens de caminhão a diesel.")}${campo(o, "consumo", "Consumo do caminhão (km/L)", "ex.: 4")}${campo(o, "carga", "Carga por viagem (t)", "ex.: 3")}
        ${campo(o, "tort", "Multiplicador estrada/linha reta", "1", "A distância por estrada é maior que a reta; use a medida do projeto.")}
        <div><label for="rcm-ida">Viagem</label><select id="rcm-ida" data-rcm-k="ida" style="width:100%"><option value="1" ${o.ida !== "0" ? "selected" : ""}>ida e volta</option><option value="0" ${o.ida === "0" ? "selected" : ""}>só ida</option></select></div></div>
      <div class="rolagem"><table><caption>Transporte de cada resíduo até o destino mais próximo do tipo certo</caption><thead><tr><th scope="col">Resíduo</th><th scope="col">Rota</th><th scope="col">kg/mês</th><th scope="col">Destino mais próximo</th><th scope="col">Distância (km)</th><th scope="col">t·km/mês</th><th scope="col">kg CO₂e/mês</th></tr></thead><tbody>${tabTrans || `<tr><td colspan="7">Todas as rotas são no lugar: sem transporte.</td></tr>`}</tbody></table></div>
      <p class="t2 pq">CO₂ = t·km × fator; ou viagens (⌈t ÷ carga⌉) × distância × 2 ÷ consumo × ${n2(DIESEL_KG_L, 3)} kg CO₂e/L de diesel (premissa da Physis). Estimativa de planejamento; o destino precisa ter licença e o MTR (SINIR) segue valendo.</p>`
      : `<p class="t2">Acrescente os resíduos do lugar acima para ver os indicadores.</p>`}</section>`;
  const estilo = `<style>.rcm-p{cursor:pointer;outline:none}.rcm-p:focus .rcm-f,.rcm-p:hover .rcm-f{stroke:#1B1F23;stroke-width:3}.rcm-p:focus-visible .rcm-f{stroke:#1B1F23;stroke-width:3.5}.rcm-leg{list-style:none;padding:0;margin:0 0 8px}.rcm-leg li{display:flex;align-items:center;gap:6px;margin:2px 0}</style>`;
  if (ui.rcmFundo && ok) setTimeout(() => montarFundo(d, pontos), 0);
  return `<section aria-labelledby="h-rcm">${estilo}<h2 id="h-rcm">Mapa e indicadores</h2><p class="t2 apoio">Aterros, cooperativas, ecopontos, compostagem e áreas de entulho em volta do lugar, e os números do plano de resíduos.</p>
    <section class="cartao" aria-labelledby="h-rcm-mapa"><h3 id="h-rcm-mapa" class="t3">Destinos em volta</h3>${ctrl}${estado ? `<p class="t2" role="status">${esc(estado)}</p>` : ""}${mapa}</section>${secaoFluxo(I)}${painel}${metodoCircular()}</section>`; }

/* ════════ Mapa com fundo (opcional): MapLibre e PMTiles servidos pelo próprio servidor ════════ */
function carregarJs(n) { return new Promise((ok, er) => { const s = document.createElement("script"); s.src = "/vendor/" + n; s.onload = () => ok(); s.onerror = () => er(new Error("a biblioteca " + n + " não está no servidor")); document.head.append(s); }); }
async function montarFundo(d, pontos) { const div = el("rcm-ml"), aviso = el("rcm-ml-aviso"); if (!div || div.dataset.montado) return; div.dataset.montado = "1";
  try { if (!window.maplibregl) { if (!document.querySelector('link[href="/vendor/maplibre-gl.css"]')) { const l = document.createElement("link"); l.rel = "stylesheet"; l.href = "/vendor/maplibre-gl.css"; document.head.append(l); } await carregarJs("maplibre-gl.js"); }
    if (!window.pmtiles) { try { await carregarJs("pmtiles.js"); } catch (e) {} }
    if (!window.__pmtilesOk && window.pmtiles) { const p = new pmtiles.Protocol(); maplibregl.addProtocol("pmtiles", p.tile); window.__pmtilesOk = true; }
    let fundo = false; try { const r = await fetch("/mapas/regiao.pmtiles", { method:"HEAD" }); fundo = r.ok; } catch (e) {}
    const gj = { type:"FeatureCollection", features:pontos.map(p => ({ type:"Feature", properties:{ nome:p.nome || "", cor:(CAT[p.categoria] || [0, "#4A4F44"])[1] }, geometry:{ type:"Point", coordinates:[p.lon, p.lat] } })) };
    const fontes = { pts:{ type:"geojson", data:gj }, lugar:{ type:"geojson", data:{ type:"Feature", properties:{}, geometry:{ type:"Point", coordinates:[d.lon, d.lat] } } } };
    const camadas = [{ id:"fundo", type:"background", paint:{ "background-color":"#F4F1EA" } }];
    if (fundo) { fontes.osm = { type:"vector", url:"pmtiles:///mapas/regiao.pmtiles" }; camadas.push({ id:"agua", type:"fill", source:"osm", "source-layer":"water", paint:{ "fill-color":"#C3D0BD" } }, { id:"vias", type:"line", source:"osm", "source-layer":"roads", paint:{ "line-color":"#C9B98F", "line-width":1 } }); }
    camadas.push({ id:"pts", type:"circle", source:"pts", paint:{ "circle-radius":6, "circle-color":["get", "cor"], "circle-stroke-color":"#FFFFFF", "circle-stroke-width":1.5 } },
      { id:"lugar", type:"circle", source:"lugar", paint:{ "circle-radius":8, "circle-color":"#FFFFFF", "circle-stroke-color":"#1A4D2E", "circle-stroke-width":3 } });
    const kx = (d.raio_km || 20) / (111.32 * Math.cos(d.lat * Math.PI / 180)), ky = (d.raio_km || 20) / 110.574;
    const m = new maplibregl.Map({ container:div, style:{ version:8, sources:fontes, layers:camadas }, attributionControl:false });
    m.addControl(new maplibregl.NavigationControl({ showCompass:true })); m.addControl(new maplibregl.ScaleControl({ unit:"metric" }));
    if (fundo) m.addControl(new maplibregl.AttributionControl({ customAttribution:"© colaboradores do OpenStreetMap" }));
    m.fitBounds([[d.lon - kx, d.lat - ky], [d.lon + kx, d.lat + ky]], { padding:20, duration:0 });
    if (aviso) aviso.textContent = fundo ? "Mapa com o fundo da região guardado no servidor." : "Sem o arquivo do mapa da região no servidor: só os pontos aparecem. Veja docs/MAPAS_E_DWG.md.";
  } catch (e) { if (aviso) aviso.textContent = "Não foi possível abrir o mapa com fundo (" + e.message + "). O mapa simples acima tem a mesma informação."; } }

/* ════════ Eventos (atributos data-rcm-…) ════════ */
function refocar(sel) { const x = typeof sel === "string" ? el(sel) : null; if (x) x.focus(); }
function escolher(i) { const d = ui.rcmDados, todos = d && d.pontos ? d.pontos : [], filtro = ui.rcmCat || "", pts = filtro ? todos.filter(p => p.categoria === filtro) : todos, p = pts[+i];
  if (!p) return; ui.rcmSel = ui.rcmSel === p.id ? null : p.id; desenhar(false);
  const g = document.querySelector(`[data-rcm-p="${i}"]`); if (g) g.focus(); }
if (typeof document !== "undefined" && !window.__rcmEventos) { window.__rcmEventos = true;
  document.addEventListener("change", ev => { const t = ev.target; if (!t || !t.dataset) return;
    if (t.dataset.rcmCat) { ui.rcmCat = t.value; ui.rcmSel = null; desenhar(false); refocar("rcm-cat"); return; }
    if (!t.dataset.rcmK) return; const o = Object.assign({}, cfgLer()); o[t.dataset.rcmK] = t.value; cfgGravar(o); desenhar(false); refocar(t.id); });
  document.addEventListener("click", ev => { const g = ev.target.closest ? ev.target.closest("[data-rcm-p]") : null; if (g) { escolher(g.dataset.rcmP); return; }
    const b = ev.target.closest ? ev.target.closest("button[data-rcm-fundo]") : null; if (b) { ui.rcmFundo = !ui.rcmFundo; desenhar(false); const x = document.querySelector("button[data-rcm-fundo]"); if (x) x.focus(); } });
  document.addEventListener("keydown", ev => { const g = ev.target && ev.target.closest ? ev.target.closest("[data-rcm-p]") : null; if (!g || (ev.key !== "Enter" && ev.key !== " ")) return; ev.preventDefault(); escolher(g.dataset.rcmP); }); }

window.CIRCULAR_MAPA = { haversineKm, co2Transporte, indicadores, POR_DESTINO, CAT };
window.telaCircularMapa = telaCircularMapa;   /* global: a aba Economia circular chama telaCircularMapa() ao desenhar */
})();
