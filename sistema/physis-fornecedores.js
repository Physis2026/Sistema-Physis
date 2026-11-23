/* physis-fornecedores.js — Fornecedores e equipamentos: "Fornecedores na sua região" na aba Energia solar (cliente) e
   planilha + fila por região + importar/exportar + mapa na Gestão interna (só equipe, nunca ao cliente).
   Servidor: physis-hub/physis_hub/fornecedores.py (rotas /api/fornecedores*). Sem internet: só o próprio hub.
   Contrato:
     FORNECEDORES.htmlSolar()               devolve o lugar da vista (<div data-forn-solar>); o módulo monta sozinho quando
                                            o lugar aparece na página (a aba Solar desenha por texto)
     FORNECEDORES.montarSolar(el, op)       "Fornecedores na sua região": local de localDaInstalacao() (município → UF →
                                            Brasil, com o rótulo dizendo qual valeu); itens do projeto da aba Solar (módulo e
                                            inversor de calcLer("solar") ou da Planta solar, estrutura, proteção, cabos,
                                            bateria se houver autonomia e instalação = link para os parceiros). Sem local:
                                            "local não informado — preencha no Início". O cliente recebe do servidor só o público.
     FORNECEDORES.montarGestao(el, op)      Gestão interna (equipe): planilha de fornecedores e de equipamentos (ordenar,
                                            filtrar, editar na célula, incluir e remover linha, CSV e ODS pelo PhysisODF),
                                            catálogos/folhas de dados (upload), fila por região do Ryan com "Pedir atualização",
                                            importar/exportar CSV por região, histórico e mapa
     FORNECEDORES.montarMapa(el, op)        só o mapa (SVG próprio, sem fundo de terceiros; mesma informação em tabela)
       op (opcional) = { idioma: function () { return "pt" | "en"; } }; sem ele, vale o lang do <html>.
     FORNECEDORES.itensDoProjeto(), FORNECEDORES.cnpjValido(v), FORNECEDORES.I18N, FORNECEDORES.t(s)
   Não usa h1. Cores só da PALETA.md, com variante para html[data-tema="escuro"]. */
(function (global) {
"use strict";

const CATEGORIAS = { modulos:"Módulos fotovoltaicos", inversores:"Inversores", estruturas:"Estruturas de fixação", baterias:"Baterias", protecao:"String box e proteção", cabos:"Cabos e conectores", kits:"Kits completos", instalacao:"Instalação e integração (profissionais parceiros)" };
const ABRANGENCIAS = { nacional:"Nacional", regional:"Regional", estadual:"Estadual", local:"Local" };
const STATUS = { em_analise:"Em análise", aprovado:"Aprovado", suspenso:"Suspenso" };
const FONTES_PRECO = { cotacao:"Cotação", catalogo:"Catálogo" };
const DIAS_PADRAO = 90;   /* espelho de fornecedores.DIAS_PADRAO; o valor que vale vem do servidor (premissa, status conferir) */
const UFS = "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split(" ");
/* ponto de referência de cada UF no mapa = a capital (coordenadas aproximadas; o mapa não tem os polígonos das UFs) */
const CAPITAIS = { AC:[-9.97,-67.81], AL:[-9.67,-35.74], AM:[-3.12,-60.02], AP:[0.03,-51.07], BA:[-12.97,-38.5], CE:[-3.73,-38.53], DF:[-15.79,-47.88], ES:[-20.32,-40.34], GO:[-16.69,-49.26], MA:[-2.53,-44.3], MG:[-19.92,-43.94], MS:[-20.47,-54.62], MT:[-15.6,-56.1], PA:[-1.46,-48.5], PB:[-7.12,-34.86], PE:[-8.05,-34.88], PI:[-5.09,-42.8], PR:[-25.43,-49.27], RJ:[-22.91,-43.17], RN:[-5.79,-35.21], RO:[-8.76,-63.9], RR:[2.82,-60.67], RS:[-30.03,-51.23], SC:[-27.6,-48.55], SE:[-10.91,-37.07], SP:[-23.55,-46.63], TO:[-10.18,-48.33] };

/* ══ Inglês ══ */
const FORN_I18N = /*I18N*/{
  "Módulos fotovoltaicos":"PV modules", "Inversores":"Inverters", "Estruturas de fixação":"Mounting structures", "Baterias":"Batteries",
  "String box e proteção":"String box and protection", "Cabos e conectores":"Cables and connectors", "Kits completos":"Complete kits",
  "Instalação e integração (profissionais parceiros)":"Installation and integration (partner professionals)",
  "Nacional":"National", "Regional":"Regional", "Estadual":"State", "Local":"Local", "Em análise":"Under review", "Aprovado":"Approved", "Suspenso":"Suspended",
  "Cotação":"Quote", "Catálogo":"Catalogue", "Fornecedores na sua região":"Suppliers in your region",
  "local não informado — preencha no Início":"location not provided — fill it in on the Home page", "Ir para o Início":"Go to Home",
  "Disponível com o servidor da Physis.":"Available with the Physis server.", "Carregando…":"Loading…",
  "Não foi possível carregar os fornecedores agora.":"Could not load the suppliers right now.",
  "Nenhum fornecedor para este item na sua região ainda.":"No supplier for this item in your region yet.",
  "Fornecedores cadastrados e conferidos pela Physis. Preço só aparece com a data e a fonte; confirme com o fornecedor antes de comprar.":"Suppliers registered and checked by Physis. A price only appears with its date and source; confirm with the supplier before buying.",
  "desatualizado — conferir":"out of date — check", "em dia":"up to date", "Site":"Website", "Produtos":"Products", "Catálogos":"Catalogues",
  "Prazo de entrega":"Delivery time", "Pedido mínimo":"Minimum order", "dias":"days", "Ver profissionais parceiros":"See partner professionals",
  "Fornecedores e equipamentos":"Suppliers and equipment", "Planilha de fornecedores":"Supplier sheet", "Equipamentos":"Equipment",
  "Fila por região":"Queue by region", "Importar e exportar CSV":"CSV import and export", "Mapa":"Map", "Histórico":"History",
  "Uso interno da equipe: nada desta tela aparece para o cliente.":"Team use only: nothing on this screen is shown to clients.",
  "Entre com uma conta da equipe.":"Sign in with a team account.", "Filtrar":"Filter", "Todas":"All", "Todos":"All",
  "Abrangência":"Scope", "Categoria":"Category", "Situação":"Status", "desatualizado":"out of date", "Fornecedor":"Supplier",
  "CNPJ":"CNPJ", "Nome público":"Public name", "Regiões":"Regions", "Última atualização":"Last update", "Ativo":"Active", "Notas internas":"Internal notes",
  "Ações":"Actions", "Detalhes":"Details", "Remover":"Remove", "Incluir fornecedor":"Add supplier", "Razão social":"Company name",
  "Incluir":"Add", "Gravar":"Save", "Baixar CSV":"Download CSV", "Baixar ODS":"Download ODS", "Gravado.":"Saved.", "Removido.":"Removed.",
  "UF":"State", "Município":"Municipality", "Código IBGE":"IBGE code", "Prazo (dias)":"Lead time (days)", "Pedido mínimo (R$)":"Minimum order (R$)",
  "Incluir região":"Add region", "Dados conferidos hoje":"Data checked today", "Contatos (LGPD)":"Contacts (LGPD)", "Nome":"Name", "Cargo":"Role",
  "E-mail":"E-mail", "Telefone com DDD":"Phone with area code", "A pessoa autorizou o uso destes dados pela Physis para contato comercial (LGPD).":"The person authorized Physis to use this data for business contact (LGPD).",
  "Incluir contato":"Add contact", "Apagar (pedido de exclusão)":"Delete (deletion request)", "Equipamentos oferecidos":"Equipment offered",
  "Ligar equipamento":"Link equipment", "Preço (só com data, região e fonte)":"Price (only with date, region and source)", "Valor":"Value",
  "Unidade":"Unit", "Data":"Date", "Fonte":"Source", "Referência da fonte":"Source reference", "Incluir preço":"Add price",
  "Arquivos (catálogos e folhas de dados)":"Files (catalogues and datasheets)", "Enviar arquivo (PDF ou imagem, até 20 MB)":"Upload file (PDF or image, up to 20 MB)",
  "público":"public", "interno":"internal", "Tornar público":"Make public", "Tornar interno":"Make internal", "Local da sede":"Head office location",
  "Latitude":"Latitude", "Longitude":"Longitude", "Raio de atendimento (km)":"Service radius (km)", "Endereço":"Address",
  "Parceiros de instalação (ids)":"Installation partners (ids)", "Curadoria":"Curation", "Motivo":"Reason", "Gravar curadoria":"Save curation",
  "Só a direção muda a curadoria.":"Only management can change the curation.", "Apagar fornecedor":"Delete supplier",
  "Apagar este fornecedor, contatos, regiões, preços e arquivos? Não dá para desfazer.":"Delete this supplier, its contacts, regions, prices and files? This cannot be undone.",
  "Marca":"Brand", "Modelo":"Model", "Id da base de equipamentos":"Equipment base id", "Folha de dados (link)":"Datasheet (link)", "Fornecedores":"Suppliers",
  "Incluir equipamento":"Add equipment", "nenhum":"none", "Região":"Region", "Desatualizados":"Out of date", "Mais antiga":"Oldest",
  "Tarefa":"Task", "Pedir atualização":"Request update", "em dia":"up to date", "desatualizada":"out of date", "sem fornecedores":"no suppliers",
  "Arquivo CSV":"CSV file", "Conferir o arquivo":"Check the file", "Gravar importação":"Save import", "Exportar a região":"Export the region",
  "Colunas aceitas":"Accepted columns", "Instalações dos clientes":"Client installations", "Fornecedores (sede)":"Suppliers (head office)",
  "Atende todo o Brasil":"Serves the whole country", "Tabela do mapa":"Map table", "Cliente":"Client", "no município":"in the municipality",
  "no estado":"in the state", "no Brasil":"nationwide", "com fornecedor perto":"with a nearby supplier", "sem fornecedor perto":"no nearby supplier",
  "Pontos das UFs = capitais (aproximado). Endereço → coordenadas: digitar lat/lon; busca automática só com Nominatim hospedado pela Physis (Fase 2).":"State points = capitals (approximate). Address → coordinates: type lat/lon; automatic lookup only with a Physis-hosted Nominatim (Phase 2).",
  "o seu papel não permite esta ação":"your role does not allow this action", "CNPJ inválido":"Invalid CNPJ",
  "contato só com o consentimento da pessoa (LGPD)":"contact only with the person's consent (LGPD)"
};
const FORN_I18N_RX = /*I18N_RX*/[
  ["^Fornecedores que atendem (.+)$", "Suppliers serving $1"],
  ["^Nenhum fornecedor cadastrado só para (.+): mostrando os que atendem todo o estado \\((..)\\)$", "No supplier registered for $1 only: showing those serving the whole state ($2)"],
  ["^Fornecedores que atendem todo o estado \\((..)\\)$", "Suppliers serving the whole state ($1)"],
  ["^Nenhum fornecedor cadastrado para (.+) nem para o estado \\((..)\\): mostrando os que atendem todo o Brasil$", "No supplier registered for $1 or the state ($2): showing those serving the whole country"],
  ["^Nenhum fornecedor cadastrado para a sua região ainda$", "No supplier registered for your region yet"],
  ["^atualizado em (.+)$", "updated on $1"], ["^(.+) \\(estado todo\\)$", "$1 (whole state)"], ["^Erro: (.+)$", "Error: $1"],
  ["^em (\\d{4}-\\d{2}-\\d{2}) \\((.+)\\)$", "on $1 ($2)"], ["^Atualizar fornecedores de (.+)$", "Update suppliers of $1"],
  ["^Tarefa (\\S+) criada para o Ryan na Gestão\\.$", "Task $1 created for Ryan in Management."],
  ["^(\\d+) linhas, (\\d+) fornecedores, (\\d+) preços · resumo SHA-256 (\\w+)$", "$1 rows, $2 suppliers, $3 prices · SHA-256 digest $4"],
  ["^limite: (\\d+) dias \\(premissa a conferir\\)$", "limit: $1 days (assumption to be checked)"]
];
let opIdioma = null;
function en(){ try { if (opIdioma) return opIdioma() === "en"; return /^en/i.test((global.document && global.document.documentElement.lang) || ""); } catch (e){ return false; } }
function t(s){ const k = String(s == null ? "" : s).replace(/\s+/g, " ").trim(); if (!k || !en()) return s;
  let v = Object.prototype.hasOwnProperty.call(FORN_I18N, k) ? FORN_I18N[k] : null;
  if (v == null) for (const [a, r] of FORN_I18N_RX){ const m = k.match(new RegExp(a)); if (m){ v = r.replace(/\$(\d)/g, (_, i) => { const g = m[+i]; return g == null ? "" : g.length < k.length ? t(g) : g; }); break; } }
  return v == null ? s : v; }
const vivos = new Set();
function aoMudarIdioma(el, fn){ vivos.add([el, fn]);
  if (aoMudarIdioma.obs || typeof MutationObserver === "undefined" || !global.document) return;
  let ultimo = global.document.documentElement.lang;
  aoMudarIdioma.obs = new MutationObserver(() => { const l = global.document.documentElement.lang; if (l === ultimo) return; ultimo = l;
    vivos.forEach(x => { if (!x[0].isConnected){ vivos.delete(x); return; } try { x[1](); } catch (e){} }); });
  aoMudarIdioma.obs.observe(global.document.documentElement, { attributes:true, attributeFilter:["lang"] }); }

const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));
const et = s => esc(t(s));
const dig = v => String(v == null ? "" : v).replace(/\D/g, "");
function cnpjValido(v){ const d = dig(v); if (d.length !== 14 || /^(\d)\1+$/.test(d)) return false;
  const P = [[12, [5,4,3,2,9,8,7,6,5,4,3,2]], [13, [6,5,4,3,2,9,8,7,6,5,4,3,2]]];
  for (const [n, p] of P){ let s = 0; for (let i = 0; i < n; i++) s += +d[i] * p[i]; const r = s % 11; if ((r < 2 ? 0 : 11 - r) !== +d[n]) return false; } return true; }
const conforto = () => { try { const c = global.document.documentElement.classList; return c.contains("physis-conforto") || c.contains("a11y-simples"); } catch (e){ return false; } };
const comServidor = () => { try { return /^https?:$/.test(global.location.protocol); } catch (e){ return false; } };
const brl = v => "R$ " + Number(v).toLocaleString(en() ? "en-GB" : "pt-BR", { minimumFractionDigits:2, maximumFractionDigits:4 });
/* link externo digitado pela equipe: só http(s), sempre abre fora e sem mandar a página de origem */
const link = (url, txt) => /^https?:\/\//i.test(url || "") ? `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(txt || url)}</a>` : "";

let csrf = null;
async function token(){ if (csrf == null){ try { csrf = (await fetch("/api/instancia", { credentials:"same-origin" }).then(r => r.json())).csrf || ""; } catch (e){ csrf = ""; } } return csrf; }
async function api(url, corpo, bruto){
  const op = { credentials:"same-origin" };
  if (corpo !== undefined){ const tk = await token(); op.method = "POST"; op.headers = {};
    if (bruto){ op.body = corpo; op.headers["Content-Type"] = "application/octet-stream"; } else { op.body = JSON.stringify(corpo); op.headers["Content-Type"] = "application/json"; }
    if (tk) op.headers["X-Physis-CSRF"] = tk; }
  const r = await fetch(url, op); let j = {}; try { j = await r.json(); } catch (e){}
  if (!r.ok || j.ok === false){ const e = new Error(j.erro || ("HTTP " + r.status)); e.dados = j; e.codigo = r.status; throw e; }
  return j; }
function baixarBlob(nome, blob){ const u = URL.createObjectURL(blob), a = global.document.createElement("a"); a.href = u; a.download = nome; global.document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(u), 4000); }
const opcoes = (obj, sel, vazio) => (vazio ? `<option value="">${et(vazio)}</option>` : "") + Object.keys(obj).map(k => `<option value="${esc(k)}"${k === sel ? " selected" : ""}>${et(obj[k])}</option>`).join("");
const opUF = (sel, vazio, br) => (vazio ? `<option value="">${et(vazio)}</option>` : "") + (br ? `<option value="BR"${sel === "BR" ? " selected" : ""}>BR</option>` : "") + UFS.map(u => `<option${u === sel ? " selected" : ""}>${u}</option>`).join("");
const campo = (id, rot, attrs) => `<div><label for="${id}">${et(rot)}</label><input id="${id}" ${attrs || 'type="text"'} style="width:100%"></div>`;
const seloAtual = desat => desat ? `<span class="selo at">${et("desatualizado — conferir")}</span>` : `<span class="selo ok">${et("em dia")}</span>`;
let seq = 0;

/* ══ Itens do projeto solar (o que a aba Solar escolheu) ══ */
function itensDoProjeto(){
  let o = {}; try { o = (typeof calcLer === "function" ? calcLer("solar") : JSON.parse(global.localStorage.getItem("physis-calc-solar") || "{}")) || {}; } catch (e){}
  let pl = null; try { pl = JSON.parse(global.localStorage.getItem("physis-calc-planta-solar") || "null"); } catch (e){}
  const S = global.SOLAR || {}, M = S.MODULOS || [], I = S.INVERSORES || [];
  const mod = o.mod || (pl && pl.modulo && pl.modulo.id) || (M[0] && M[0].id) || "", inv = o.inv || (I[0] && I[0].id) || "";
  const itens = [mod, inv, "estruturas", "protecao", "cabos"].filter(Boolean);
  if (Number(String(o.autonomia || "0").replace(",", ".")) > 0) itens.push("baterias");
  itens.push("instalacao"); return itens; }

/* ══ Aba Energia solar: "Fornecedores na sua região" ══ */
function montarSolar(el, op){
  if (op && typeof op.idioma === "function") opIdioma = op.idioma;
  if (el.dataset.fornMontado) return; el.dataset.fornMontado = "1";
  const id = "fs" + (++seq), st = { dados:null, erro:"", sem:false };
  const L = () => (typeof global.localDaInstalacao === "function" ? global.localDaInstalacao() : { uf:"" }) || { uf:"" };
  async function carregar(){
    const l = L(); if (!l.uf){ st.sem = true; return desenhar(); }
    if (!comServidor()){ st.erro = "Disponível com o servidor da Physis."; return desenhar(); }
    const q = new URLSearchParams({ uf:l.uf, ibge:l.ibge || "", municipio:l.municipio || "", itens:itensDoProjeto().join(",") });
    try { st.dados = await api("/api/fornecedores/regiao?" + q.toString()); st.erro = ""; } catch (e){ st.erro = "Não foi possível carregar os fornecedores agora."; }
    desenhar(); }
  function cartao(f, item){
    const prods = f.produtos ? f.produtos.filter(p => !item || item.categoria === "instalacao" || p.categoria === item.categoria) : (f.ofertas || []).filter(p => !item || p.categoria === item.categoria);
    const linhasProd = prods.map(p => { const pr = (p.precos || []).filter(x => x.data && x.fonte)[0];   /* sem data ou fonte, não mostra */
      return `<li>${esc([p.marca, p.modelo].filter(Boolean).join(" ") || t(CATEGORIAS[p.categoria]))}${pr ? ` · ${esc(brl(pr.valor))} ${esc(pr.unidade)} <span class="t2">${et("em " + pr.data + " (" + (pr.fonte_nome || pr.fonte) + ")")}</span>` : ""}</li>`; }).join("");
    const det = `${linhasProd ? `<p class="pq"><strong>${et("Produtos")}</strong></p><ul class="pq">${linhasProd}</ul>` : ""}
      ${f.prazo_entrega_dias != null ? `<p class="pq">${et("Prazo de entrega")}: ${esc(f.prazo_entrega_dias)} ${et("dias")}</p>` : ""}
      ${f.pedido_minimo_brl != null ? `<p class="pq">${et("Pedido mínimo")}: ${esc(brl(f.pedido_minimo_brl))}</p>` : ""}
      ${(f.catalogos || []).length ? `<p class="pq">${et("Catálogos")}: ${f.catalogos.map(c => `<a href="/api/fornecedores/arquivo/${c.id}" download>${esc(c.nome)}</a>`).join(", ")}</p>` : ""}
      ${f.notas_internas ? `<p class="pq t2">${et("Notas internas")}: ${esc(f.notas_internas)}</p>` : ""}`;
    return `<li class="cartao"><h4 class="t3">${esc(f.nome_publico || f.nome)}${f.status && f.status !== "aprovado" ? ` <span class="selo at">${et(STATUS[f.status])}</span>` : ""}</h4>
      <p class="pq">${esc(t(f.regiao || ""))} · ${et("atualizado em " + (f.ultima_atualizacao || "—"))} ${seloAtual(f.desatualizado)}</p>
      ${f.site ? `<p class="pq">${et("Site")}: ${link(f.site, f.site.replace(/^https?:\/\//i, ""))}</p>` : ""}
      ${conforto() ? `<details><summary>${et("Detalhes")}</summary>${det}</details>` : det}</li>`; }
  function desenhar(){
    const d = st.dados;
    let corpo;
    if (st.sem || (d && d.nivel === "sem_local")) corpo = `<div class="faixa at" role="status"><strong>${et("local não informado — preencha no Início")}</strong> <button type="button" data-aba="inicio">${et("Ir para o Início")}</button></div>`;
    else if (st.erro) corpo = `<p class="faixa in" role="status">${et(st.erro)}</p>`;
    else if (!d) corpo = `<p class="t2">${et("Carregando…")}</p>`;
    else corpo = `<p class="faixa ${d.nivel === "municipio" ? "ok" : "at"}" role="status">${et(d.rotulo)}</p>
      ${d.itens.map((it, k) => `<section aria-labelledby="${id}-i${k}"><h3 id="${id}-i${k}" class="t3">${et(it.id ? it.nome : CATEGORIAS[it.categoria])}</h3>
        ${it.fornecedores.length ? `<p class="t2 pq">${et(it.rotulo)}</p><ul style="list-style:none;padding:0;display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(260px,1fr))">${it.fornecedores.map(f => cartao(f, it)).join("")}</ul>` : `<p class="t2">${et("Nenhum fornecedor para este item na sua região ainda.")}</p>`}
        ${it.categoria === "instalacao" ? `<p><button type="button" data-aba="loja" data-loja-vista="parceiros">${et("Ver profissionais parceiros")}</button></p>` : ""}</section>`).join("")}
      <p class="t2 pq">${et("limite: " + (d.dias_desatualizado || DIAS_PADRAO) + " dias (premissa a conferir)")}</p>`;
    el.innerHTML = `<section class="cartao" aria-labelledby="${id}-h"><h2 id="${id}-h">${et("Fornecedores na sua região")}</h2>
      <p class="t2">${et("Fornecedores cadastrados e conferidos pela Physis. Preço só aparece com a data e a fonte; confirme com o fornecedor antes de comprar.")}</p>${corpo}</section>`; }
  aoMudarIdioma(el, desenhar); desenhar(); carregar(); }
function htmlSolar(){ return '<div data-forn-solar=""></div>'; }
if (typeof MutationObserver !== "undefined" && global.document && !global.__fornObs){ global.__fornObs = true;
  const ver = () => global.document.querySelectorAll("[data-forn-solar]:not([data-forn-montado])").forEach(x => montarSolar(x));
  new MutationObserver(ver).observe(global.document.documentElement, { childList:true, subtree:true }); }

/* ══ Mapa (SVG próprio; só equipe) ══ */
const W = 640, H = 610, LON0 = -75, LON1 = -33, LAT0 = 6, LAT1 = -34;
const px = (lat, lon) => ({ x: (lon - LON0) / (LON1 - LON0) * W, y: (lat - LAT0) / (LAT1 - LAT0) * H });
const kmPx = km => km / 111.32 * W / (LON1 - LON0);
const ESTILO_MAPA = `<style>.pf-mapa{max-width:100%;height:auto;background:#F7F9F4;border:1px solid #C9D2C4}.pf-mapa .gr{stroke:#C9D2C4;stroke-width:1}
.pf-mapa .uf{fill:#FFFFFF;stroke:#4A4F44}.pf-mapa .uf-sel{fill:#DCEBD8;stroke:#1F4A1C;stroke-width:2}.pf-mapa .tx{fill:#1C2B21;font:11px sans-serif}
.pf-mapa .f{fill:#33512F;stroke:#FFFFFF}.pf-mapa .f-velho{fill:#8A6410;stroke:#FFFFFF}.pf-mapa .raio{fill:#7FA874;fill-opacity:.25;stroke:#33512F}
.pf-mapa .c-perto{fill:#2F5E4E;stroke:#FFFFFF}.pf-mapa .c-longe{fill:#7A2214;stroke:#FFFFFF}.pf-mapa .nac{fill:#E3E8DE;fill-opacity:.35}
.pf-mapa [tabindex]:focus{outline:3px solid #1C2B21}
html[data-tema="escuro"] .pf-mapa{background:#14180F;border-color:#3A4A38}html[data-tema="escuro"] .pf-mapa .gr{stroke:#33372E}
html[data-tema="escuro"] .pf-mapa .uf{fill:#2A3829;stroke:#A8BFA0}html[data-tema="escuro"] .pf-mapa .uf-sel{fill:#4A5A47;stroke:#8FB183}
html[data-tema="escuro"] .pf-mapa .tx{fill:#EEF2EA}html[data-tema="escuro"] .pf-mapa .f{fill:#8FB183;stroke:#14180F}html[data-tema="escuro"] .pf-mapa .f-velho{fill:#C9A227;stroke:#14180F}
html[data-tema="escuro"] .pf-mapa .raio{fill:#7FA874;stroke:#A8BFA0}html[data-tema="escuro"] .pf-mapa .c-perto{fill:#8FB183;stroke:#14180F}
html[data-tema="escuro"] .pf-mapa .c-longe{fill:#FF8A80;stroke:#14180F}html[data-tema="escuro"] .pf-mapa .nac{fill:#3D2A5C}html[data-tema="escuro"] .pf-mapa [tabindex]:focus{outline-color:#EEF2EA}</style>`;
function svgMapa(d){
  const selUF = new Set(); d.fornecedores.forEach(f => f.regioes.forEach(r => { if (r.uf !== "BR") selUF.add(r.uf); }));
  const nac = d.fornecedores.filter(f => f.abrangencia === "nacional").length;
  let g = "";
  for (let lon = -70; lon <= -35; lon += 5){ const a = px(LAT0, lon), b = px(LAT1, lon); g += `<line class="gr" x1="${a.x}" y1="0" x2="${b.x}" y2="${H}"/>`; }
  for (let lat = 5; lat >= -30; lat -= 5){ const a = px(lat, LON0); g += `<line class="gr" x1="0" y1="${a.y}" x2="${W}" y2="${a.y}"/>`; }
  if (nac) g += `<rect class="nac" x="0" y="0" width="${W}" height="${H}"><title>${esc(t("Atende todo o Brasil"))}: ${nac}</title></rect>`;
  Object.keys(CAPITAIS).forEach(u => { const p = px(...CAPITAIS[u]); g += `<g><circle class="${selUF.has(u) ? "uf-sel" : "uf"}" cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="13"/><text class="tx" x="${p.x.toFixed(1)}" y="${(p.y + 4).toFixed(1)}" text-anchor="middle">${u}</text></g>`; });
  d.fornecedores.forEach(f => { if (f.lat == null) return; const p = px(f.lat, f.lon);
    if (f.raio_km) g += `<circle class="raio" cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${Math.max(3, kmPx(f.raio_km)).toFixed(1)}"/>`;
    g += `<rect class="${f.desatualizado ? "f-velho" : "f"}" tabindex="0" role="img" aria-label="${esc(f.nome + " · " + t(ABRANGENCIAS[f.abrangencia]))}" x="${(p.x - 6).toFixed(1)}" y="${(p.y - 6).toFixed(1)}" width="12" height="12"><title>${esc(f.nome)}</title></rect>`; });
  d.clientes.forEach(c => { if (c.lat == null) return; const p = px(c.lat, c.lon);
    g += `<path class="${c.perto ? "c-perto" : "c-longe"}" tabindex="0" role="img" aria-label="${esc(c.org + " · " + t(c.perto ? "com fornecedor perto" : "sem fornecedor perto"))}" d="M${p.x.toFixed(1)},${(p.y - 8).toFixed(1)} l7,13 h-14 z"><title>${esc(c.org)}</title></path>`; });
  return `<svg class="pf-mapa" viewBox="0 0 ${W} ${H}" role="group" aria-label="${et("Mapa")}" xmlns="http://www.w3.org/2000/svg">${g}</svg>`; }
function montarMapa(el, op){
  if (op && typeof op.idioma === "function") opIdioma = op.idioma;
  const id = "fm" + (++seq), st = { f:{ abrangencia:"", categoria:"", situacao:"" }, d:null, erro:"" };
  async function carregar(){ try { st.d = await api("/api/fornecedores/mapa?" + new URLSearchParams(st.f).toString()); st.erro = ""; } catch (e){ st.erro = e.codigo === 401 || e.codigo === 403 ? "Entre com uma conta da equipe." : "Erro: " + e.message; } desenhar(); }
  function desenhar(){ const d = st.d, f = st.f;
    el.innerHTML = `${ESTILO_MAPA}<section aria-labelledby="${id}-h"><h3 id="${id}-h">${et("Mapa")}</h3>
      <form data-fm="filtro" style="display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));align-items:end">
        <div><label for="${id}-a">${et("Abrangência")}</label><select id="${id}-a" name="abrangencia" style="width:100%">${opcoes(ABRANGENCIAS, f.abrangencia, "Todas")}</select></div>
        <div><label for="${id}-c">${et("Categoria")}</label><select id="${id}-c" name="categoria" style="width:100%">${opcoes(CATEGORIAS, f.categoria, "Todas")}</select></div>
        <div><label for="${id}-s">${et("Situação")}</label><select id="${id}-s" name="situacao" style="width:100%">${opcoes({ em_dia:"em dia", desatualizado:"desatualizado" }, f.situacao, "Todas")}</select></div>
        <div><button type="submit">${et("Filtrar")}</button></div></form>
      <div role="status" aria-live="polite">${st.erro ? `<p>${et(st.erro)}</p>` : ""}</div>
      ${d ? `${svgMapa(d)}<p class="t2 pq">${et("Pontos das UFs = capitais (aproximado). Endereço → coordenadas: digitar lat/lon; busca automática só com Nominatim hospedado pela Physis (Fase 2).")}</p>
      <div class="rolagem"><table><caption>${et("Fornecedores (sede)")}</caption><thead><tr><th scope="col">${et("Fornecedor")}</th><th scope="col">${et("Abrangência")}</th><th scope="col">${et("Regiões")}</th><th scope="col">${et("Última atualização")}</th></tr></thead><tbody>
        ${d.fornecedores.map(x => `<tr><th scope="row">${esc(x.nome)}</th><td>${et(ABRANGENCIAS[x.abrangencia])}${x.raio_km ? " · " + esc(x.raio_km) + " km" : ""}</td><td>${esc(x.regioes.map(r => r.municipio ? r.municipio + "/" + r.uf : r.uf).join(", "))}</td><td>${esc(x.ultima_atualizacao || "—")} ${seloAtual(x.desatualizado)}</td></tr>`).join("")}</tbody></table></div>
      <div class="rolagem"><table><caption>${et("Instalações dos clientes")}</caption><thead><tr><th scope="col">${et("Cliente")}</th><th scope="col">${et("Município")}</th><th scope="col">${et("no município")}</th><th scope="col">${et("no estado")}</th><th scope="col">${et("no Brasil")}</th></tr></thead><tbody>
        ${d.clientes.map(c => `<tr><th scope="row">${esc(c.org)}</th><td>${esc((c.municipio || "—") + "/" + (c.uf || "—"))}</td><td>${c.fornecedores.municipio}</td><td>${c.fornecedores.uf}</td><td>${c.fornecedores.nacional}</td></tr>`).join("")}</tbody></table></div>` : `<p class="t2">${et("Carregando…")}</p>`}</section>`; }
  el.addEventListener("submit", ev => { const fm = ev.target; if (!fm.dataset || fm.dataset.fm !== "filtro") return; ev.preventDefault();
    st.f = { abrangencia:fm.elements.abrangencia.value, categoria:fm.elements.categoria.value, situacao:fm.elements.situacao.value }; carregar(); });
  aoMudarIdioma(el, desenhar); desenhar(); carregar(); }

/* ══ Gestão interna: planilha, fila, importação e mapa ══ */
function montarGestao(el, op){
  if (op && typeof op.idioma === "function") opIdioma = op.idioma;
  const id = "fg" + (++seq), st = { aba:"fornecedores", d:null, fila:null, papel:null, msg:"", filtro:{ texto:"", abrangencia:"", situacao:"" }, ordem:["nome_publico", 1], aberto:{}, imp:null, hist:null };
  const direcao = () => st.papel === "administrador";
  async function carregar(){
    try { const i = await fetch("/api/instancia", { credentials:"same-origin" }).then(r => r.json()).catch(() => ({})); st.papel = i.papel || null; csrf = i.csrf || csrf;
      st.d = await api("/api/fornecedores/interno"); st.fila = await api("/api/fornecedores/fila"); }
    catch (e){ st.msg = e.codigo === 401 || e.codigo === 403 ? "Entre com uma conta da equipe." : "Erro: " + e.message; }
    desenhar(); }
  async function agir(fn, ok){ try { const r = await fn(); st.msg = typeof ok === "function" ? ok(r) : ok; } catch (e){ st.msg = "Erro: " + e.message; } await carregar(); }
  const nomeF = i => { const f = st.d && st.d.fornecedores.find(x => x.id === i); return f ? f.nome_publico : "#" + i; };
  function linhasFiltradas(){
    const f = st.filtro, [k, s] = st.ordem, txt = f.texto.toLowerCase();
    return st.d.fornecedores.filter(x => (!txt || (x.nome + " " + x.nome_publico + " " + x.cnpj + " " + x.notas_internas).toLowerCase().includes(txt))
      && (!f.abrangencia || x.abrangencia === f.abrangencia) && (!f.situacao || (f.situacao === "desatualizado") === x.desatualizado))
      .sort((a, b) => String(a[k] == null ? "" : a[k]).localeCompare(String(b[k] == null ? "" : b[k]), "pt-BR", { numeric:true }) * s); }
  const COLS = [["nome_publico", "Nome público"], ["cnpj", "CNPJ"], ["site", "Site"], ["abrangencia", "Abrangência"], ["regioes", "Regiões"], ["status", "Situação"], ["ultima_atualizacao", "Última atualização"], ["notas_internas", "Notas internas"]];
  const cab = c => { const [k, s] = st.ordem, ord = k === c[0] ? (s > 0 ? "ascending" : "descending") : "none";
    return `<th scope="col" aria-sort="${ord}"><button type="button" data-fg-ordem="${c[0]}">${et(c[1])}${ord === "none" ? "" : ord === "ascending" ? " ▲" : " ▼"}</button></th>`; };
  const cel = (f, k, w) => `<input type="text" aria-label="${esc(t(k === "site" ? "Site" : k === "notas_internas" ? "Notas internas" : "Nome público") + " · " + f.nome_publico)}" data-fg-cel="${k}" data-fg-id="${f.id}" value="${esc(f[k] || "")}" style="width:${w}">`;
  function planilha(){
    const ls = linhasFiltradas(), f = st.filtro;
    return `<form data-fg="filtro" style="display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));align-items:end">
        ${campo(id + "-ft", "Filtrar", `type="search" name="texto" value="${esc(f.texto)}"`)}
        <div><label for="${id}-fa">${et("Abrangência")}</label><select id="${id}-fa" name="abrangencia" style="width:100%">${opcoes(ABRANGENCIAS, f.abrangencia, "Todas")}</select></div>
        <div><label for="${id}-fs">${et("Situação")}</label><select id="${id}-fs" name="situacao" style="width:100%">${opcoes({ em_dia:"em dia", desatualizado:"desatualizado" }, f.situacao, "Todas")}</select></div>
        <div><button type="submit">${et("Filtrar")}</button></div></form>
      <p style="display:flex;gap:8px;flex-wrap:wrap"><button type="button" data-fg-baixar="csv">${et("Baixar CSV")}</button><button type="button" data-fg-baixar="ods">${et("Baixar ODS")}</button></p>
      <div class="rolagem"><table data-fg-tabela="fornecedores"><caption>${et("Planilha de fornecedores")}</caption><thead><tr>${COLS.map(cab).join("")}<th scope="col"><span class="so-leitor">${et("Ações")}</span></th></tr></thead><tbody>
      ${ls.map(x => `<tr><th scope="row">${cel(x, "nome_publico", "14em")}<br><span class="t2 pq">${esc(x.nome)}</span></th><td>${esc(x.cnpj)}</td><td>${cel(x, "site", "14em")}</td>
        <td><select aria-label="${esc(t("Abrangência") + " · " + x.nome_publico)}" data-fg-cel="abrangencia" data-fg-id="${x.id}">${opcoes(ABRANGENCIAS, x.abrangencia)}</select></td>
        <td>${esc(x.regioes.map(r => t(r.rotulo)).join(", ") || "—")}</td><td><span class="selo ${x.status === "aprovado" ? "ok" : x.status === "suspenso" ? "al" : "at"}">${et(STATUS[x.status])}</span>${x.ativo ? "" : ` <span class="selo al">${et("interno")}</span>`}</td>
        <td>${esc(x.ultima_atualizacao || "—")} ${seloAtual(x.desatualizado)}</td><td>${cel(x, "notas_internas", "16em")}</td>
        <td><button type="button" data-fg-abrir="${x.id}" aria-expanded="${!!st.aberto[x.id]}" aria-label="${esc(t("Detalhes") + " · " + x.nome_publico)}">${et("Detalhes")}</button></td></tr>
        ${st.aberto[x.id] ? `<tr><td colspan="${COLS.length + 1}">${detalhe(x)}</td></tr>` : ""}`).join("")}</tbody></table></div>
      <form data-fg="novo" class="cartao" style="display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));align-items:end">
        <h3 class="t3" style="grid-column:1/-1">${et("Incluir fornecedor")}</h3>
        ${campo(id + "-nc", "CNPJ", 'type="text" name="cnpj" required inputmode="numeric"')}${campo(id + "-nn", "Razão social", 'type="text" name="nome" required maxlength="160"')}
        ${campo(id + "-np", "Nome público", 'type="text" name="nome_publico" maxlength="120"')}${campo(id + "-ns", "Site", 'type="url" name="site" maxlength="300"')}
        <div><label for="${id}-na">${et("Abrangência")}</label><select id="${id}-na" name="abrangencia" style="width:100%">${opcoes(ABRANGENCIAS, "local")}</select></div>
        <div><label for="${id}-nu">${et("UF")}</label><select id="${id}-nu" name="uf" style="width:100%">${opUF("", "—")}</select></div>
        ${campo(id + "-nm", "Município", 'type="text" name="municipio" maxlength="80"')}${campo(id + "-ni", "Código IBGE", 'type="text" name="ibge" inputmode="numeric" maxlength="7"')}
        <div><button type="submit">${et("Incluir")}</button></div></form>`; }
  function detalhe(f){
    const pid = f.id, ofs = f.ofertas;
    const regs = `<h4>${et("Regiões")}</h4><ul>${f.regioes.map(r => `<li>${esc(t(r.rotulo))} · ${et("atualizado em " + r.data)} ${seloAtual(r.desatualizado)}${r.prazo_entrega_dias != null ? " · " + esc(r.prazo_entrega_dias) + " " + et("dias") : ""}${r.pedido_minimo_brl != null ? " · " + esc(brl(r.pedido_minimo_brl)) : ""}
        <button type="button" data-fg-acao="regiao/conferida" data-fg-id="${pid}" data-fg-x="${r.id}">${et("Dados conferidos hoje")}</button> <button type="button" data-fg-acao="regiao/remover" data-fg-id="${pid}" data-fg-x="${r.id}" aria-label="${esc(t("Remover") + " " + r.rotulo)}">${et("Remover")}</button></li>`).join("")}</ul>
      <form data-fg="regiao" data-fg-id="${pid}" style="display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));align-items:end">
        <div><label for="${id}-ru${pid}">${et("UF")}</label><select id="${id}-ru${pid}" name="uf" required style="width:100%">${opUF("", "—", true)}</select></div>
        ${campo(id + "-rm" + pid, "Município", 'type="text" name="municipio"')}${campo(id + "-ri" + pid, "Código IBGE", 'type="text" name="ibge" inputmode="numeric" maxlength="7"')}
        ${campo(id + "-rp" + pid, "Prazo (dias)", 'type="number" name="prazo_entrega_dias" min="0" max="365"')}${campo(id + "-rq" + pid, "Pedido mínimo (R$)", 'type="number" name="pedido_minimo_brl" min="0" step="0.01"')}
        <div><button type="submit">${et("Incluir região")}</button></div></form>`;
    const cont = `<h4>${et("Contatos (LGPD)")}</h4><ul>${f.contatos.map(c => `<li>${esc(c.nome)}${c.cargo ? " · " + esc(c.cargo) : ""} · ${esc(c.email || "—")} · ${esc(c.telefone || "—")} <button type="button" data-fg-acao="contato/remover" data-fg-id="${pid}" data-fg-x="${c.id}">${et("Apagar (pedido de exclusão)")}</button></li>`).join("")}</ul>
      <form data-fg="contato" data-fg-id="${pid}" style="display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));align-items:end">
        ${campo(id + "-cn" + pid, "Nome", 'type="text" name="nome" required maxlength="120"')}${campo(id + "-cc" + pid, "Cargo", 'type="text" name="cargo" maxlength="80"')}
        ${campo(id + "-ce" + pid, "E-mail", 'type="email" name="email"')}${campo(id + "-ct" + pid, "Telefone com DDD", 'type="tel" name="telefone"')}
        <label style="grid-column:1/-1;font-weight:400;display:flex;gap:8px"><input type="checkbox" name="consentimento" required> ${et("A pessoa autorizou o uso destes dados pela Physis para contato comercial (LGPD).")}</label>
        <div><button type="submit">${et("Incluir contato")}</button></div></form>`;
    const eqs = (st.d.equipamentos || []).map(e => [e.id, [CATEGORIAS[e.categoria], e.marca, e.modelo].filter(Boolean).join(" · ")]);
    const ofe = `<h4>${et("Equipamentos oferecidos")}</h4><ul>${ofs.map(o => `<li>${et(CATEGORIAS[o.categoria])} · ${esc([o.marca, o.modelo].filter(Boolean).join(" "))}${o.equipamento_id ? " (" + esc(o.equipamento_id) + ")" : ""}
        ${o.precos.map(p => ` · ${esc(brl(p.valor))} ${esc(p.unidade)} ${et("em " + p.data + " (" + p.fonte_nome + ")")} ${esc(p.uf + (p.ibge ? "/" + p.ibge : ""))}`).join("")}
        <button type="button" data-fg-acao="oferta/remover" data-fg-id="${pid}" data-fg-x="${o.oferta}">${et("Remover")}</button></li>`).join("")}</ul>
      <form data-fg="oferta" data-fg-id="${pid}" style="display:flex;gap:8px;flex-wrap:wrap;align-items:end"><div><label for="${id}-oe${pid}">${et("Equipamentos")}</label><select id="${id}-oe${pid}" name="equipamento">${eqs.map(([v, n]) => `<option value="${v}">${esc(t(n))}</option>`).join("")}</select></div><button type="submit"${eqs.length ? "" : " disabled"}>${et("Ligar equipamento")}</button></form>
      <form data-fg="preco" data-fg-id="${pid}" style="display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));align-items:end"><h5 style="grid-column:1/-1">${et("Preço (só com data, região e fonte)")}</h5>
        <div><label for="${id}-po${pid}">${et("Equipamentos")}</label><select id="${id}-po${pid}" name="oferta" style="width:100%">${ofs.map(o => `<option value="${o.oferta}">${esc([o.marca, o.modelo].filter(Boolean).join(" ") || t(CATEGORIAS[o.categoria]))}</option>`).join("")}</select></div>
        ${campo(id + "-pv" + pid, "Valor", 'type="number" name="valor" required min="0" step="0.0001"')}${campo(id + "-pn" + pid, "Unidade", 'type="text" name="unidade" required placeholder="R$/Wp" maxlength="20"')}
        ${campo(id + "-pd" + pid, "Data", 'type="date" name="data" required')}<div><label for="${id}-pf${pid}">${et("Fonte")}</label><select id="${id}-pf${pid}" name="fonte" required style="width:100%">${opcoes(FONTES_PRECO, "cotacao")}</select></div>
        ${campo(id + "-pr" + pid, "Referência da fonte", 'type="text" name="fonte_ref" maxlength="200"')}<div><label for="${id}-pu${pid}">${et("UF")}</label><select id="${id}-pu${pid}" name="uf" required style="width:100%">${opUF("", "—", true)}</select></div>
        ${campo(id + "-pi" + pid, "Código IBGE", 'type="text" name="ibge" inputmode="numeric" maxlength="7"')}<div><button type="submit"${ofs.length ? "" : " disabled"}>${et("Incluir preço")}</button></div></form>`;
    const arqs = `<h4>${et("Arquivos (catálogos e folhas de dados)")}</h4><ul>${f.arquivos.map(a => `<li><a href="/api/fornecedores/arquivo/${a.id}" download>${esc(a.nome)}</a> · ${Math.ceil(a.tamanho / 1024)} KB · <span class="selo ${a.publico ? "in" : "at"}">${et(a.publico ? "público" : "interno")}</span> <code title="SHA-256">${esc(a.sha256.slice(0, 12))}…</code>
        ${direcao() ? `<button type="button" data-fg-pub="${a.id}" data-fg-v="${a.publico ? "" : "1"}">${et(a.publico ? "Tornar interno" : "Tornar público")}</button>` : ""} <button type="button" data-fg-rmarq="${a.id}">${et("Remover")}</button></li>`).join("")}</ul>
      <div><label for="${id}-up${pid}">${et("Enviar arquivo (PDF ou imagem, até 20 MB)")}</label> <input id="${id}-up${pid}" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" data-fg-up="fornecedor" data-fg-id="${pid}"></div>`;
    const loc = `<h4>${et("Local da sede")}</h4><form data-fg="local" data-fg-id="${pid}" style="display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));align-items:end">
        ${campo(id + "-le" + pid, "Endereço", `type="text" name="endereco" maxlength="300" value="${esc(f.endereco)}"`)}${campo(id + "-la" + pid, "Latitude", `type="number" step="any" name="lat" value="${f.lat == null ? "" : f.lat}"`)}
        ${campo(id + "-lo" + pid, "Longitude", `type="number" step="any" name="lon" value="${f.lon == null ? "" : f.lon}"`)}${campo(id + "-lr" + pid, "Raio de atendimento (km)", `type="number" min="0" name="raio_km" value="${f.raio_km == null ? "" : f.raio_km}"`)}
        ${campo(id + "-lp" + pid, "Parceiros de instalação (ids)", `type="text" name="parceiros" value="${esc(f.parceiros.join(", "))}"`)}<div><button type="submit">${et("Gravar")}</button></div></form>`;
    const cur = `<h4>${et("Curadoria")}</h4><form data-fg="curadoria" data-fg-id="${pid}" style="display:flex;gap:8px;flex-wrap:wrap;align-items:end">
        <div><label for="${id}-cs${pid}">${et("Situação")}</label><select id="${id}-cs${pid}" name="status"${direcao() ? "" : " disabled"}>${opcoes(STATUS, f.status)}</select></div>
        <div><label for="${id}-cm${pid}">${et("Motivo")}</label><input id="${id}-cm${pid}" name="motivo" type="text" maxlength="300"${direcao() ? "" : " disabled"}></div>
        <button type="submit"${direcao() ? "" : " disabled"}>${et("Gravar curadoria")}</button></form>${direcao() ? `<p><button type="button" data-fg-apagar="${pid}">${et("Apagar fornecedor")}</button></p>` : `<p class="t2 pq">${et("Só a direção muda a curadoria.")}</p>`}
      <p><button type="button" data-fg-hist="${pid}">${et("Histórico")}</button></p>${st.hist && st.hist.id === pid ? `<ol class="pq">${st.hist.itens.map(h => `<li>${esc(h.data)} · ${esc(h.quem)} · ${esc(h.o_que)}</li>`).join("")}</ol>` : ""}`;
    return `<div style="display:grid;gap:10px">${regs}${cont}${ofe}${arqs}${loc}${cur}</div>`; }
  function equipamentos(){
    const es = st.d.equipamentos, base = st.d.base || {};
    const ce = (e, k, w) => `<input type="text" aria-label="${esc(t(k === "marca" ? "Marca" : k === "modelo" ? "Modelo" : "Folha de dados (link)") + " · " + (e.marca || "") + " " + (e.modelo || ""))}" data-fg-eq="${k}" data-fg-id="${e.id}" value="${esc(e[k] || "")}" style="width:${w}">`;
    return `<p style="display:flex;gap:8px;flex-wrap:wrap"><button type="button" data-fg-baixar="csv">${et("Baixar CSV")}</button><button type="button" data-fg-baixar="ods">${et("Baixar ODS")}</button></p>
      <div class="rolagem"><table data-fg-tabela="equipamentos"><caption>${et("Equipamentos")}</caption><thead><tr><th scope="col">${et("Categoria")}</th><th scope="col">${et("Marca")}</th><th scope="col">${et("Modelo")}</th><th scope="col">${et("Id da base de equipamentos")}</th><th scope="col">${et("Folha de dados (link)")}</th><th scope="col">${et("Fornecedores")}</th><th scope="col">${et("Arquivos (catálogos e folhas de dados)")}</th><th scope="col"><span class="so-leitor">${et("Ações")}</span></th></tr></thead><tbody>
      ${es.map(e => `<tr><th scope="row">${et(CATEGORIAS[e.categoria])}</th><td>${ce(e, "marca", "9em")}</td><td>${ce(e, "modelo", "10em")}</td>
        <td><select aria-label="${esc(t("Id da base de equipamentos") + " · " + e.modelo)}" data-fg-eq="equipamento_id" data-fg-id="${e.id}"><option value="">—</option>${Object.keys(base).filter(k => base[k].categoria === e.categoria).map(k => `<option value="${esc(k)}"${k === e.equipamento_id ? " selected" : ""}>${esc(k)}</option>`).join("")}</select></td>
        <td>${ce(e, "ficha_url", "12em")} ${link(e.ficha_url, "↗")}</td><td>${esc(e.fornecedores.map(nomeF).join(", ") || t("nenhum"))}</td>
        <td>${e.arquivos.map(a => `<a href="/api/fornecedores/arquivo/${a.id}" download>${esc(a.nome)}</a>`).join(", ")} <label class="so-leitor" for="${id}-eu${e.id}">${et("Enviar arquivo (PDF ou imagem, até 20 MB)")}</label><input id="${id}-eu${e.id}" type="file" accept=".pdf,.png,.jpg,.jpeg,.webp" data-fg-up="equipamento" data-fg-id="${e.id}"></td>
        <td><button type="button" data-fg-rmeq="${e.id}">${et("Remover")}</button></td></tr>`).join("")}</tbody></table></div>
      <form data-fg="equip" class="cartao" style="display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));align-items:end"><h3 class="t3" style="grid-column:1/-1">${et("Incluir equipamento")}</h3>
        <div><label for="${id}-ec">${et("Categoria")}</label><select id="${id}-ec" name="categoria" style="width:100%">${opcoes(Object.fromEntries(Object.entries(CATEGORIAS).filter(([k]) => k !== "instalacao")), "modulos")}</select></div>
        ${campo(id + "-em", "Marca", 'type="text" name="marca" maxlength="80"')}${campo(id + "-eo", "Modelo", 'type="text" name="modelo" maxlength="120"')}
        ${campo(id + "-ei", "Id da base de equipamentos", 'type="text" name="equipamento_id" maxlength="60" list="' + id + '-base"')}<datalist id="${id}-base">${Object.keys(base).map(k => `<option value="${esc(k)}">`).join("")}</datalist>
        ${campo(id + "-ef", "Folha de dados (link)", 'type="url" name="ficha_url" maxlength="300"')}<div><button type="submit">${et("Incluir")}</button></div></form>`; }
  function fila(){
    const f = st.fila; if (!f) return "";
    return `<p class="t2">${esc(f.responsavel.nome)} · ${et("limite: " + f.dias_desatualizado + " dias (premissa a conferir)")}</p>
      <div class="rolagem"><table><caption>${et("Fila por região")}</caption><thead><tr><th scope="col">${et("Região")}</th><th scope="col">${et("Situação")}</th><th scope="col">${et("Fornecedores")}</th><th scope="col">${et("Desatualizados")}</th><th scope="col">${et("Mais antiga")}</th><th scope="col">${et("Tarefa")}</th></tr></thead><tbody>
      ${f.regioes.map(r => `<tr><th scope="row">${et(r.rotulo)}</th><td><span class="selo ${r.situacao === "em dia" ? "ok" : "at"}">${et(r.situacao)}</span></td><td>${r.fornecedores}</td><td>${r.desatualizados}</td><td>${esc(r.mais_antiga_data || "—")}</td>
        <td>${r.tarefa ? esc(r.tarefa) : `<button type="button" data-fg-pedir="${esc(JSON.stringify({ uf:r.uf, ibge:r.ibge || "", municipio:r.municipio || "" }))}">${et("Pedir atualização")}</button>`}</td></tr>`).join("")}</tbody></table></div>`; }
  function importar(){
    const i = st.imp || {};
    return `<form data-fg="importar" style="display:grid;gap:8px;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));align-items:end">
        <div><label for="${id}-iu">${et("UF")}</label><select id="${id}-iu" name="uf" required style="width:100%">${opUF(i.uf || "", "—", true)}</select></div>
        ${campo(id + "-im", "Município", `type="text" name="municipio" value="${esc(i.municipio || "")}"`)}${campo(id + "-ii", "Código IBGE", `type="text" name="ibge" inputmode="numeric" maxlength="7" value="${esc(i.ibge || "")}"`)}
        <div><label for="${id}-if">${et("Arquivo CSV")}</label><input id="${id}-if" type="file" name="arquivo" accept=".csv,text/csv"></div>
        <div style="display:flex;gap:8px;flex-wrap:wrap"><button type="submit" name="acao" value="simular">${et("Conferir o arquivo")}</button><button type="submit" name="acao" value="gravar"${i.simulado ? "" : " disabled"}>${et("Gravar importação")}</button><button type="button" data-fg-exportar="1">${et("Exportar a região")}</button></div></form>
      ${i.erros ? `<ul class="pq">${i.erros.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
      <p class="t2 pq">${et("Colunas aceitas")}: cnpj; categoria; marca; modelo; equipamento_id; prazo_entrega_dias; pedido_minimo_brl; preco; preco_unidade; preco_data; preco_fonte; preco_fonte_ref</p>`; }
  function desenhar(){
    const abas = [["fornecedores", "Planilha de fornecedores"], ["equipamentos", "Equipamentos"], ["fila", "Fila por região"], ["csv", "Importar e exportar CSV"], ["mapa", "Mapa"]];
    el.innerHTML = `<section aria-labelledby="${id}-h"><h2 id="${id}-h">${et("Fornecedores e equipamentos")}</h2><p class="t2">${et("Uso interno da equipe: nada desta tela aparece para o cliente.")}</p>
      <div class="chips" role="group" aria-label="${et("Fornecedores e equipamentos")}">${abas.map(([k, n]) => `<button type="button" data-fg-aba="${k}" aria-pressed="${k === st.aba}">${et(n)}</button>`).join("")}</div>
      <div role="status" aria-live="polite">${st.msg ? `<p class="pq"><strong>${et(st.msg)}</strong></p>` : ""}</div>
      ${!st.d ? "" : st.aba === "fornecedores" ? planilha() : st.aba === "equipamentos" ? equipamentos() : st.aba === "fila" ? fila() : st.aba === "csv" ? importar() : `<div data-fg-mapa></div>`}</section>`;
    const m = el.querySelector("[data-fg-mapa]"); if (m) montarMapa(m, op); }
  function tabelaDaTela(){ const tb = el.querySelector("table[data-fg-tabela]"); if (!tb) return null;
    const val = c => { const i = c.querySelector("input,select"); return (i ? (i.tagName === "SELECT" ? i.options[i.selectedIndex] && i.options[i.selectedIndex].text : i.value) : c.textContent).replace(/\s+/g, " ").trim(); };
    const cab = Array.from(tb.querySelectorAll("thead th")).slice(0, -1).map(c => c.textContent.replace(/[▲▼]/g, "").trim());
    const linhas = Array.from(tb.querySelectorAll("tbody tr")).filter(r => r.children.length > 2).map(r => Array.from(r.children).slice(0, -1).map(val));
    return { nome: tb.dataset.fgTabela, cab, linhas }; }
  async function baixar(tipo){ const tb = tabelaDaTela(); if (!tb) return;
    if (tipo === "csv"){ const q = v => /[";\n]/.test(v) || /^[=+\-@]/.test(v) ? '"' + ("" + (/^[=+\-@]/.test(v) ? "'" : "") + v).replace(/"/g, '""') + '"' : v;
      return baixarBlob("physis-" + tb.nome + ".csv", new Blob(["﻿" + [tb.cab].concat(tb.linhas).map(l => l.map(q).join(";")).join("\n")], { type:"text/csv" })); }
    if (global.PhysisODF){ const u8 = await global.PhysisODF.ods([{ nome:t(tb.nome === "equipamentos" ? "Equipamentos" : "Fornecedores"), cab:tb.cab, linhas:tb.linhas }], { titulo:t("Fornecedores e equipamentos") });
      return global.PhysisODF.baixar("physis-" + tb.nome + ".ods", u8, global.PhysisODF.MIME.ods); } }
  el.addEventListener("click", async ev => { const b = ev.target.closest("button"); if (!b || !el.contains(b)) return; const ds = b.dataset;
    if (ds.fgAba){ st.aba = ds.fgAba; st.msg = ""; desenhar(); const x = el.querySelector(`[data-fg-aba="${ds.fgAba}"]`); if (x) x.focus(); }
    else if (ds.fgOrdem){ st.ordem = [ds.fgOrdem, st.ordem[0] === ds.fgOrdem ? -st.ordem[1] : 1]; desenhar(); const x = el.querySelector(`[data-fg-ordem="${ds.fgOrdem}"]`); if (x) x.focus(); }
    else if (ds.fgAbrir){ st.aberto[ds.fgAbrir] = !st.aberto[ds.fgAbrir]; desenhar(); const x = el.querySelector(`[data-fg-abrir="${ds.fgAbrir}"]`); if (x) x.focus(); }
    else if (ds.fgBaixar) await baixar(ds.fgBaixar);
    else if (ds.fgAcao) await agir(() => api(`/api/fornecedores/${ds.fgId}/${ds.fgAcao}`, { id:Number(ds.fgX) }), ds.fgAcao.endsWith("remover") ? "Removido." : "Gravado.");
    else if (ds.fgPub) await agir(() => api("/api/fornecedores/arquivo/publico", { id:Number(ds.fgPub), publico:!!ds.fgV }), "Gravado.");
    else if (ds.fgRmarq) await agir(() => api("/api/fornecedores/arquivo/remover", { id:Number(ds.fgRmarq) }), "Removido.");
    else if (ds.fgRmeq) await agir(() => api("/api/fornecedores/equipamento/remover", { id:Number(ds.fgRmeq) }), "Removido.");
    else if (ds.fgApagar && global.confirm(t("Apagar este fornecedor, contatos, regiões, preços e arquivos? Não dá para desfazer.")))
      await agir(() => api(`/api/fornecedores/${ds.fgApagar}/apagar`, {}), "Removido.");
    else if (ds.fgHist){ try { const h = await api("/api/fornecedores/historico?fornecedor=" + ds.fgHist); st.hist = { id:Number(ds.fgHist), itens:h.itens }; } catch (e){ st.msg = "Erro: " + e.message; } desenhar(); }
    else if (ds.fgPedir) await agir(() => api("/api/fornecedores/pedir-atualizacao", JSON.parse(ds.fgPedir)), r => "Tarefa " + r.id + " criada para o Ryan na Gestão.");
    else if (ds.fgExportar){ const fm = b.form, q = new URLSearchParams({ uf:fm.elements.uf.value, municipio:fm.elements.municipio.value, ibge:fm.elements.ibge.value });
      try { const r = await fetch("/api/fornecedores/exportar?" + q.toString(), { credentials:"same-origin" }); if (!r.ok) throw new Error((await r.json()).erro || r.status);
        baixarBlob("fornecedores-" + q.get("uf") + ".csv", await r.blob()); } catch (e){ st.msg = "Erro: " + e.message; desenhar(); } } });
  el.addEventListener("change", async ev => { const x = ev.target, ds = x.dataset || {};
    if (ds.fgCel) await agir(() => api(`/api/fornecedores/${ds.fgId}/editar`, { [ds.fgCel]: x.value.trim() }), "Gravado.");
    else if (ds.fgEq) await agir(() => api("/api/fornecedores/equipamento", { id:Number(ds.fgId), [ds.fgEq]: x.value.trim() }), "Gravado.");
    else if (ds.fgUp && x.files && x.files[0]){ const a = x.files[0], q = new URLSearchParams({ [ds.fgUp]: ds.fgId, nome:a.name, tipo:ds.fgUp === "equipamento" ? "ficha" : "catalogo" });
      await agir(async () => api("/api/fornecedores/arquivo?" + q.toString(), await a.arrayBuffer(), true), r => "Gravado. SHA-256 " + r.sha256.slice(0, 12) + "…"); } });
  el.addEventListener("submit", async ev => { const fm = ev.target; if (!fm.dataset || !fm.dataset.fg) return; ev.preventDefault();
    const v = n => (fm.elements[n] && fm.elements[n].value || "").trim(), num = n => v(n) === "" ? undefined : Number(v(n)), pid = fm.dataset.fgId, tipo = fm.dataset.fg;
    const limpo = o => { Object.keys(o).forEach(k => { if (o[k] === undefined || o[k] === "") delete o[k]; }); return o; };
    if (tipo === "filtro"){ st.filtro = { texto:v("texto"), abrangencia:v("abrangencia"), situacao:v("situacao") }; return desenhar(); }
    if (tipo === "novo"){ if (!cnpjValido(v("cnpj"))){ st.msg = "CNPJ inválido"; return desenhar(); }
      return agir(() => api("/api/fornecedores/cadastro", limpo({ cnpj:v("cnpj"), nome:v("nome"), nome_publico:v("nome_publico"), site:v("site"), abrangencia:v("abrangencia"), uf:v("uf"), municipio:v("municipio"), ibge:v("ibge") })), "Gravado."); }
    if (tipo === "regiao") return agir(() => api(`/api/fornecedores/${pid}/regiao`, limpo({ uf:v("uf"), municipio:v("municipio"), ibge:v("ibge"), prazo_entrega_dias:num("prazo_entrega_dias"), pedido_minimo_brl:num("pedido_minimo_brl") })), "Gravado.");
    if (tipo === "contato") return agir(() => api(`/api/fornecedores/${pid}/contato`, limpo({ nome:v("nome"), cargo:v("cargo"), email:v("email"), telefone:v("telefone"), consentimento:fm.elements.consentimento.checked })), "Gravado.");
    if (tipo === "oferta") return agir(() => api(`/api/fornecedores/${pid}/oferta`, { equipamento:Number(v("equipamento")) }), "Gravado.");
    if (tipo === "preco") return agir(() => api(`/api/fornecedores/${pid}/preco`, limpo({ oferta:Number(v("oferta")), valor:num("valor"), unidade:v("unidade"), data:v("data"), fonte:v("fonte"), fonte_ref:v("fonte_ref"), uf:v("uf"), ibge:v("ibge") })), "Gravado.");
    if (tipo === "local") return agir(() => api(`/api/fornecedores/${pid}/editar`, { endereco:v("endereco"), lat:num("lat") == null ? null : num("lat"), lon:num("lon") == null ? null : num("lon"), raio_km:num("raio_km") == null ? null : num("raio_km"),
      parceiros:v("parceiros").split(/[,\s]+/).filter(Boolean).map(Number).filter(n => Number.isInteger(n)) }), "Gravado.");
    if (tipo === "curadoria") return agir(() => api(`/api/fornecedores/${pid}/curadoria`, limpo({ status:v("status"), motivo:v("motivo") })), "Gravado.");
    if (tipo === "equip") return agir(() => api("/api/fornecedores/equipamento", limpo({ categoria:v("categoria"), marca:v("marca"), modelo:v("modelo"), equipamento_id:v("equipamento_id"), ficha_url:v("ficha_url") })), "Gravado.");
    if (tipo === "importar"){ const acao = ev.submitter && ev.submitter.value || "simular", a = fm.elements.arquivo.files[0];
      const regiao = { uf:v("uf"), municipio:v("municipio"), ibge:v("ibge") };
      if (acao === "simular"){ if (!a) return; st.imp = Object.assign({}, regiao, { csv:await a.text(), nome:a.name }); }
      try { const r = await api("/api/fornecedores/importar", limpo(Object.assign({}, regiao, { csv:st.imp.csv, nome:st.imp.nome, simular:acao === "simular" })));
        st.msg = r.linhas + " linhas, " + r.fornecedores + " fornecedores, " + r.precos + " preços · resumo SHA-256 " + r.resumo.slice(0, 16);
        st.imp = acao === "simular" ? Object.assign(st.imp, { simulado:true, erros:null }) : null; if (acao !== "simular") return carregar(); }
      catch (e){ st.msg = "Erro: " + e.message; st.imp = Object.assign(st.imp || {}, { simulado:false, erros:(e.dados && e.dados.erros) || null }); }
      return desenhar(); } });
  aoMudarIdioma(el, desenhar); desenhar(); carregar(); }

global.FORNECEDORES = { CATEGORIAS, ABRANGENCIAS, STATUS, FONTES_PRECO, DIAS_PADRAO, cnpjValido, itensDoProjeto, htmlSolar, montarSolar, montarGestao, montarMapa, I18N: FORN_I18N, I18N_RX: FORN_I18N_RX, t };
})(typeof window !== "undefined" ? window : globalThis);
