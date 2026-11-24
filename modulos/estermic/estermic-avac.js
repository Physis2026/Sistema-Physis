/* estermic-avac.js — VERSÃO DE TESTE (20/11/2026). Módulo AVAC personalizado para a Estermic (contrato direto no Brasil, sem loja).
   Base: cópia personalizada do módulo AVAC da Physis (modulos/estermic/avac-estermic-copia.js = sistema/physis-avac.js) e da carga
   térmica (sistema/physis-cargatermica.js). As contas são as do módulo base, sem mudança (regra 2 do CLAUDE.md); este arquivo só
   organiza cliente, contratos por subprojeto, fases financeiras, equipamentos com peças, BIM/GIS e a emissão de documentos.
   Nada é inventado: o que falta aparece como [MARCADOR]; o que precisa de confirmação, como [CONFERIR].
   Melhorias feitas aqui voltam ao módulo padrão: cada uma fica registrada em modulos/estermic/aprendizados-modulo-padrao.json.

   Contrato: window.ESTERMIC = {
     padrao(), normalizar(estado), MARCADOR, CONFERIR,
     financeiro(sub), alertas(estado, hoje), pendencias(estado),
     rascunhoNota(estado, iSub, iFase) -> { para, assunto, corpo, eml }   (só RASCUNHO; nunca envia)
     equipamentosDoCalculo(sub, AVAC) -> itens com TAG; sugerirDaBase(base, item) -> { itens, fabricantes }
     ifcDados(estado, iSub) -> objeto para PhysisIFC.escrever; geojson(estado)
     memorial(estado, iSub, AVAC, CT), relatorio(...), estudoPreliminar(estado, iSub, AVAC, CT) ("EP" = Estudo Preliminar,
     resposta da dona de 21/11), tabelaEquipamentos(estado, iSub)   -> blocos/tabelas
     FASES_PADRAO (Estudo Preliminar, Projeto Básico, Projeto Executivo), PECAS_PADRAO (peças de reposição por sistema)
     odt(blocos, marca, meta) / ods(tabelas, marca, meta) -> Uint8Array (ODF 1.3, template do CLIENTE) }
   Só funções puras; sem internet; sem dependência de terceiros. */
(function (global) {
"use strict";

const MARCADOR = "[MARCADOR]", CONFERIR = "[CONFERIR]";
const vazio = v => v == null || (typeof v === "string" && v.trim() === "");
const mk = (v, rot) => vazio(v) ? (rot ? "[MARCADOR: " + rot + "]" : MARCADOR) : String(v);
const num = v => { if (v == null || v === "") return null; const n = typeof v === "number" ? v : Number(String(v).replace(/\./g, "").replace(",", ".")); return isFinite(n) ? n : null; };
const soma = (l, k) => l.reduce((s, x) => s + (num(x[k]) || 0), 0);
const copia = o => JSON.parse(JSON.stringify(o));

/* ════════ Estado inicial ════════ */
/* Decisão da dona (21/11/2026): fases de pagamento padrão por etapa do projeto, pré-preenchidas e editáveis; valores e prazos [MARCADOR] */
const FASES_PADRAO = ["Estudo Preliminar", "Projeto Básico", "Projeto Executivo"];
const faseVazia = nome => ({ nome:nome || "", descricao:"", valor:null, prazo:"", faturado:null, nf:"", vencimento:"", recebido:null });
/* Decisão da dona (21/11/2026): part number em TODAS as peças de reposição. Lista de peças típicas por sistema (rótulos genéricos,
   sem número; a lista em si é [CONFERIR] com o Ryan); o código de cada peça fica [MARCADOR] até haver dado real. */
const PECAS_PADRAO = {
  "Ar condicionado":["Filtro de ar da evaporadora", "Sensor de temperatura", "Placa eletrônica", "Motor do ventilador", "Capacitor do compressor"],
  "Ventilação":["Correia", "Rolamentos", "Filtro de ar", "Sensor de pressão diferencial", "Motor"],
  "Aquecimento solar":["Sensor de temperatura", "Válvula de segurança", "Resistência de apoio", "Bomba de circulação"],
  "Piscina":["Filtro", "Sensor de temperatura", "Bomba de circulação"],
  "_outro":["Filtro", "Sensor", "Correia ou acoplamento"] };
const pecasPadrao = sistema => (PECAS_PADRAO[sistema] || PECAS_PADRAO._outro).map(d => ({ descricao:d, codigo:"", qtd:null, padrao:true }));
function subprojeto(i) {
  return { id:"sp" + i, nome:"", escopo:"",
    contrato:{ numero:"", valor:null, assinatura:"", prazoFinal:"", condicoes:"", iss:"" },
    fases:FASES_PADRAO.map(faseVazia), local:{ endereco:"", municipio:"", uf:"", lat:null, lon:null, altitude:null },
    dados:{},                  /* estado das contas do módulo base: dados.avac = { e }, dados.cargatermica = { e } */
    dadosConfirmados:false,    /* enquanto falso, os documentos saem com a marca EXEMPLO (dados da planilha-exemplo) */
    equipamentos:[],
    ambientes:[],              /* [{ nome, area (m², null = sem fonte), ocupacao, fonte }] */
    premissas:[],              /* [{ t, fonte }] dados do projeto com a fonte de cada um */
    alternativas:[] };         /* [{ nome, descricao, fonte }] para o Estudo Preliminar */
}
function padrao() {
  return { versao:1, teste:true,
    cliente:{ id:"estermic", nome:"Estermic", cnpj:"", contato:"", email:"",
      explicacao:"" /* funcionamento core das atividades do cliente: [MARCADOR] até a dona informar */ },
    marcaCliente:{ nome:"Estermic", logoPng:null, fonteTitulo:"", fonteTexto:"", corPrincipal:"", corTexto:"", corLinha:"" },
    emissor:{ nome:"Physis Engineering", cnpj:"44.982.448/0001-23", cnpjSituacao:"provisório", regime:"Simples Nacional", municipio:"" },
    contador:{ nome:"Robson", email:"" },
    config:{ diasAviso:7 /* janela de aviso da tela (preferência de uso, não número técnico) */ },
    subprojetos:[1, 2, 3, 4].map(subprojeto),
    conjunto:null,             /* conjunto de dados carregado (ex.: { id:"casa-physis", rotulo, fontes, premissas }) */
    aprendizados:[] };
}
function normalizar(e) {
  const p = padrao(); if (!e || typeof e !== "object") return p;
  const out = Object.assign(p, e);
  ["cliente", "marcaCliente", "emissor", "contador", "config"].forEach(k => { out[k] = Object.assign(padrao()[k], e[k] || {}); });
  out.subprojetos = (Array.isArray(e.subprojetos) && e.subprojetos.length ? e.subprojetos : p.subprojetos).map((s, i) => {
    const b = subprojeto(i + 1), o = Object.assign(b, s || {});
    o.contrato = Object.assign(subprojeto(i + 1).contrato, (s || {}).contrato || {});
    o.local = Object.assign(subprojeto(i + 1).local, (s || {}).local || {});
    ["fases", "equipamentos", "ambientes", "premissas", "alternativas"].forEach(k => { o[k] = Array.isArray(o[k]) ? o[k] : []; });
    o.dados = o.dados && typeof o.dados === "object" ? o.dados : {}; return o; });
  out.aprendizados = Array.isArray(e.aprendizados) ? e.aprendizados : [];
  out.conjunto = e.conjunto && typeof e.conjunto === "object" ? e.conjunto : null;
  return out;
}
const nomeSub = (s, i) => vazio(s.nome) ? "Subprojeto " + (i + 1) + " " + MARCADOR : s.nome;

/* ════════ Financeiro por fase ════════ */
function situacaoFase(f) {
  const v = num(f.valor), fat = num(f.faturado) || 0, rec = num(f.recebido) || 0;
  if (v == null) return "sem valor";
  if (rec >= v && v > 0) return "recebida";
  if (rec > 0) return "recebida em parte";
  if (fat >= v && v > 0) return "faturada";
  if (fat > 0) return "faturada em parte";
  return "a faturar";
}
function financeiro(sub) {
  const fases = sub.fases || [], valorContrato = num(sub.contrato && sub.contrato.valor);
  const somaFases = soma(fases, "valor"), faturado = soma(fases, "faturado"), recebido = soma(fases, "recebido");
  const contratado = valorContrato != null ? valorContrato : (fases.length ? somaFases : null);
  return { contratado, valorContrato, somaFases, faturado, recebido,
    aFaturar: contratado == null ? null : Math.max(0, contratado - faturado),
    aReceber: Math.max(0, faturado - recebido),
    divergeFases: valorContrato != null && fases.length > 0 && Math.abs(valorContrato - somaFases) > 0.005,
    porFase: fases.map((f, i) => ({ i, nome:mk(f.nome, "nome da fase"), valor:num(f.valor), prazo:f.prazo || "", faturado:num(f.faturado) || 0,
      recebido:num(f.recebido) || 0, situacao:situacaoFase(f) })) };
}
const dia = s => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s || "")); return m ? Date.UTC(+m[1], +m[2] - 1, +m[3]) : null; };
const hojeUTC = h => { const d = h instanceof Date ? h : new Date(h || Date.now()); return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()); };
function alertas(estado, hoje) {
  const e = normalizar(estado), H = hojeUTC(hoje), jan = (num(e.config.diasAviso) || 0) * 864e5, out = [];
  const add = (nivel, sub, texto) => out.push({ nivel, sub, texto });
  e.subprojetos.forEach((s, i) => { const n = nomeSub(s, i), F = financeiro(s);
    if (vazio(s.contrato.numero)) add("pendente", i, n + ": número do contrato " + MARCADOR);
    if (F.valorContrato == null) add("pendente", i, n + ": valor do contrato " + MARCADOR);
    if (!s.fases.length) add("pendente", i, n + ": fases e prazos de pagamento " + MARCADOR);
    else if (s.fases.some(f => num(f.valor) == null)) add("pendente", i, n + ": valor de fase " + MARCADOR);
    if (F.divergeFases) add("atencao", i, n + ": soma das fases diferente do valor do contrato");
    const pf = dia(s.contrato.prazoFinal);
    if (pf != null && pf < H) add("alerta", i, n + ": prazo final do contrato vencido (" + s.contrato.prazoFinal + ")");
    else if (pf != null && pf - H <= jan) add("atencao", i, n + ": prazo final do contrato em " + Math.round((pf - H) / 864e5) + " dia(s)");
    s.fases.forEach((f, j) => { const fn = n + " · " + mk(f.nome, "fase " + (j + 1)), st = situacaoFase(f), p = dia(f.prazo), vc = dia(f.vencimento);
      if (p != null && (st === "a faturar" || st === "faturada em parte")) {
        if (p < H) add("alerta", i, fn + ": prazo de faturamento vencido (" + f.prazo + ")");
        else if (p - H <= jan) add("atencao", i, fn + ": faturar em " + Math.round((p - H) / 864e5) + " dia(s)"); }
      if (vc != null && vc < H && /^faturada/.test(st)) add("alerta", i, fn + ": pagamento vencido em " + f.vencimento + " e não recebido"); }); });
  const ordem = { alerta:0, atencao:1, pendente:2 }; return out.sort((a, b) => ordem[a.nivel] - ordem[b.nivel]);
}

/* ════════ Pendências (tudo o que ainda é [MARCADOR]) ════════ */
function pendencias(estado) {
  const e = normalizar(estado), p = [], ver = (v, t) => { if (vazio(v)) p.push(t); };
  ver(e.cliente.explicacao, "Cliente: explicação do funcionamento core das atividades da Estermic");
  ver(e.cliente.cnpj, "Cliente: CNPJ da Estermic"); ver(e.cliente.contato, "Cliente: contato");
  ver(e.contador.email, "Contador (Robson): e-mail");
  ver(e.marcaCliente.logoPng, "Marca do cliente: logo"); ver(e.marcaCliente.fonteTitulo, "Marca do cliente: fonte de título");
  ver(e.marcaCliente.fonteTexto, "Marca do cliente: fonte de texto"); ver(e.marcaCliente.corPrincipal, "Marca do cliente: cor principal");
  if (e.emissor.cnpjSituacao === "provisório") p.push("Emissor: CNPJ marcado como provisório " + CONFERIR);
  p.push("ISS (município e alíquota): o contador define — perguntar ao Robson");
  e.subprojetos.forEach((s, i) => { const n = "Subprojeto " + (i + 1);
    ver(s.nome, n + ": nome"); ver(s.escopo, n + ": escopo"); ver(s.contrato.numero, n + ": número do contrato");
    if (num(s.contrato.valor) == null) p.push(n + ": valor do contrato"); ver(s.contrato.condicoes, n + ": condições de pagamento");
    if (!s.fases.length) p.push(n + ": fases e prazos"); s.fases.forEach(f => { if (num(f.valor) == null || vazio(f.prazo)) p.push(n + ": valor e prazo da fase " + mk(f.nome)); }); if (s.local.lat == null || s.local.lon == null) p.push(n + ": localização (latitude e longitude)");
    if (!s.dadosConfirmados) p.push(n + ": dados de cálculo confirmados (hoje: " + (e.conjunto ? e.conjunto.rotulo : "exemplo da planilha") + ")");
    s.ambientes.forEach(a => { if (a.area == null) p.push(n + ": área de \"" + mk(a.nome) + "\" sem fonte"); });
    s.equipamentos.forEach((q, j) => { if (vazio(q.fabricante) || vazio(q.modelo)) p.push(n + ": " + (q.tag || "item " + (j + 1)) + " sem fabricante/modelo");
      (q.pecas || []).forEach(pc => { if (vazio(pc.codigo)) p.push(n + ": " + (q.tag || "item") + " · peça \"" + mk(pc.descricao) + "\" sem código (part number)"); }); }); });
  return p;
}

/* ════════ Rascunho de e-mail ao contador (NUNCA envia) ════════ */
const brl = v => v == null ? MARCADOR : "R$ " + Number(v).toFixed(2).replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
function rascunhoNota(estado, iSub, iFase) {
  const e = normalizar(estado), s = e.subprojetos[iSub]; if (!s) throw new Error("subprojeto inexistente");
  const f = s.fases[iFase]; if (!f) throw new Error("fase inexistente");
  const para = vazio(e.contador.email) ? "[MARCADOR: e-mail do Robson]" : e.contador.email;
  const assunto = "Pedido de nota fiscal de serviço — " + e.cliente.nome + " — contrato " + mk(s.contrato.numero) + " — " + mk(f.nome, "fase");
  const corpo = ["Olá, " + e.contador.nome + ",", "",
    "Por favor, emitir a nota fiscal de serviço (NFS-e) abaixo. RASCUNHO gerado pelo sistema; conferir antes de enviar.", "",
    "Prestador: " + e.emissor.nome + " — CNPJ " + e.emissor.cnpj + (e.emissor.cnpjSituacao === "provisório" ? " (provisório " + CONFERIR + ")" : "") + " — " + e.emissor.regime,
    "Tomador: " + e.cliente.nome + " — CNPJ " + mk(e.cliente.cnpj, "CNPJ da Estermic"),
    "Contrato: " + mk(s.contrato.numero) + " — " + nomeSub(s, iSub),
    "Fase: " + mk(f.nome, "nome da fase") + (f.prazo ? " — prazo " + f.prazo : ""),
    "Valor da fase: " + brl(num(f.valor)),
    "Descrição do serviço: " + mk(f.descricao || s.escopo, "descrição do serviço"),
    "ISS: município e alíquota " + (vazio(s.contrato.iss) ? "a definir por você (contador)" : s.contrato.iss + " " + CONFERIR),
    "Condições de pagamento: " + mk(s.contrato.condicoes), "",
    "Obrigado.", e.emissor.nome].join("\n");
  const enc = t => "=?UTF-8?B?" + b64(utf8(t)) + "?=";
  const eml = ["X-Unsent: 1", "To: " + para, "Subject: " + enc(assunto), "MIME-Version: 1.0", "Content-Type: text/plain; charset=UTF-8",
    "Content-Transfer-Encoding: base64", "", b64(utf8(corpo)).replace(/(.{76})/g, "$1\r\n")].join("\r\n");
  /* texto curto para colar no WhatsApp (só copiar; nenhum link de envio) */
  const whatsapp = ["Olá, " + e.contador.nome + "! Pedido de *nota fiscal de serviço* (rascunho do sistema, conferir):",
    "• Tomador: " + e.cliente.nome + " (CNPJ " + mk(e.cliente.cnpj, "CNPJ da Estermic") + ")",
    "• Contrato " + mk(s.contrato.numero) + " — " + nomeSub(s, iSub),
    "• Fase: " + mk(f.nome, "nome da fase") + " — *" + brl(num(f.valor)) + "*",
    "• Serviço: " + mk(f.descricao || s.escopo, "descrição do serviço"),
    "• ISS: " + (vazio(s.contrato.iss) ? "você define" : s.contrato.iss),
    "Obrigado! " + e.emissor.nome].join("\n");
  return { para, assunto, corpo, eml, whatsapp, enviado:false };
}

/* ════════ Equipamentos: do cálculo, com TAG e peças ════════ */
const PREFIXO = { "Ar condicionado":"AC", "Ventilação":"VE", "Aquecimento solar":"AS", "Piscina":"AP" };
/* Seleção de modelos e fabricantes por categoria (24/11/2026): [categoria da base de equipamentos, segmento de fabricantes].
   Sem item na base, aparecem só os fabricantes do segmento; o modelo fica [MARCADOR] até a cotação. */
const SELECAO = { "Chiller":[null, "Chillers"], "Torre de arrefecimento":[null, "Torres de resfriamento"], "Tanque de termoacumulação":[null, null],
  "Skid (conjunto montado)":[null, null], "Bomba":["bombas", "Bombas hidráulicas"], "Tanque de expansão":[null, null], "Filtro de ar":["filtros de ar", "Filtragem de ar"],
  "Filtro de piscina":[null, "Equipamentos de piscina"], "Ventilador ou exaustor":["ventiladores e exaustores", "Ventiladores industriais"],
  "Grelha":["distribuição de ar", "Difusores, grelhas e dampers"], "Difusor":["distribuição de ar", "Difusores, grelhas e dampers"],
  "Tomada de ar exterior":["distribuição de ar", "Difusores, grelhas e dampers"], "Registro ou válvula":[null, "Válvulas e atuadores"], "Tubo":[null, null],
  "Duto flexível":[null, "Dutos flexíveis"], "Isolamento térmico":[null, "Isolamento térmico"], "Placa fotovoltaica":["módulos fotovoltaicos", null],
  "Inversor (fotovoltaico)":["inversores", null], "Inversor de frequência":[null, "Inversores de frequência"], "Aquecedor de passagem":[null, "Aquecedores a gás"],
  "Aquecedor a gás (acumulação)":[null, "Aquecedores a gás"], "Coletor solar":["aquecimento solar de água", "Aquecimento solar"],
  "Bomba de calor de piscina":[null, "Bombas de calor para piscina"], "Fancoil ou UTA":["ar-condicionado", "Fancoils e UTAs"], "Split ou VRF":["ar-condicionado", "VRF / fluxo variável"],
  "Automação (BMS)":["automação", "Automação predial"] };
const CATEG_BASE = { "Ar condicionado":"ar-condicionado", "Ventilação":"ventiladores e exaustores", "Aquecimento solar":"aquecimento solar de água", "Piscina":"aquecimento solar de água" };
const SEGMENTO = { "Ar condicionado":"Split e multi-split", "Ventilação":"Ventiladores industriais" };
function entradasAvac(sub) { return sub && sub.dados && sub.dados.avac && sub.dados.avac.e ? sub.dados.avac.e : {}; }
function equipamentosDoCalculo(sub, AVAC) {
  const R = AVAC.calcular(entradasAvac(sub)), cont = {};
  return (R.lista || []).map(x => { const pre = PREFIXO[x.sistema] || "EQ"; cont[pre] = (cont[pre] || 0) + 1;
    return { tag:pre + "-" + String(cont[pre]).padStart(2, "0"), origem:"calculo", sistema:x.sistema, descricao:x.descricao, qtd:x.qtd, cap:x.cap, un:x.un,
      categoria:x.categoria, fabricante:"", modelo:"", baseId:"", pecas:pecasPadrao(x.sistema) }; });
}
function capKw(item) { const c = num(item.cap); if (c == null) return null;
  if (item.un === "BTU/h") return c * 0.00029307107;   /* conversão de unidade: 1 BTU/h = 0,29307107 W */
  if (item.un === "kW") return c; return null; }
function sugerirDaBase(base, item) {
  if (!base || !Array.isArray(base.itens)) return { itens:[], fabricantes:[] };
  const selc = SELECAO[item.selecao], cat = selc ? selc[0] : CATEG_BASE[item.sistema], kw = capKw(item);
  let l = cat ? base.itens.filter(b => b.categoria === cat) : [];
  if (kw != null) { const perto = l.filter(b => b.faixa_capacidade && kw >= num(b.faixa_capacidade.min) * 0.9 && kw <= num(b.faixa_capacidade.max) * 1.1); if (perto.length) l = perto; }
  const seg = base.fabricantes_por_segmento && base.fabricantes_por_segmento[selc ? selc[1] : SEGMENTO[item.sistema]];
  return { itens:l.slice(0, 12).map(b => ({ id:b.id, descricao:b.descricao, eficiencia:b.eficiencia || null })), fabricantes:seg && seg.fabricantes ? seg.fabricantes.slice() : [] };
}
function tabelaEquipamentos(estado, iSub) {
  const s = normalizar(estado).subprojetos[iSub], linhas = [];
  s.equipamentos.forEach((q, j) => {
    linhas.push([j + 1, q.tag || "", q.sistema || "", q.descricao || "", q.qtd == null ? "" : q.qtd, q.cap == null ? "" : q.cap, q.un || "",
      mk(q.fabricante), mk(q.modelo), q.baseId || "", "", "", ""]);
    (q.pecas || []).forEach((p, k) => linhas.push([(j + 1) + "." + (k + 1), q.tag || "", "", "", p.qtd == null ? "" : p.qtd, "", "", "", "", "", mk(p.descricao), mk(p.codigo, "part number"), p.obs || ""]));
  });
  return { nome:"Equipamentos " + (s.nome || "subprojeto " + (iSub + 1)).slice(0, 20),
    cab:["Item", "TAG", "Sistema", "Descrição", "Qtd.", "Capacidade", "Unidade", "Fabricante", "Modelo", "Ref. base Physis", "Peça", "Código (part number)", "Obs."], linhas };
}

/* ════════ BIM (IFC) e GIS (GeoJSON) ════════ */
/* classe IFC pela descrição/sistema do equipamento (24/11/2026); o resto continua equipamento de climatização */
function tipoIfc(q) { const t = ((q.sistema || "") + " " + (q.descricao || "")).toLowerCase();
  const sel = String(q.selecao || "");
  const porSel = { "Chiller":"chiller", "Torre de arrefecimento":"torre", "Tanque de termoacumulação":"tanque", "Tanque de expansão":"tanque", "Skid (conjunto montado)":"skid",
    "Bomba":"bomba", "Ventilador ou exaustor":"ventilador", "Grelha":"difusor", "Difusor":"difusor", "Tomada de ar exterior":"difusor", "Registro ou válvula":"valvula",
    "Filtro de ar":"filtro", "Filtro de piscina":"filtro", "Aquecedor de passagem":"aquecedor", "Aquecedor a gás (acumulação)":"aquecedor" }[sel];
  if (porSel) return porSel;
  return /chiller|resfriador de l[ií]quido/.test(t) ? "chiller" : /torre de resfriamento/.test(t) ? "torre" : /\bbomba/.test(t) ? "bomba"
    : /ventilador|exaustor/.test(t) ? "ventilador" : /difusor|grelha|veneziana/.test(t) ? "difusor" : /\bquadro/.test(t) ? "quadro" : "avac"; }

/* IFC da arquitetura → áreas e preenchimento inicial dos cálculos (24/11/2026: "ao incluir IFC, o cálculo de áreas deve ser
   automático, assim como o preenchimento inicial"). Classifica os espaços pelo nome; o que não reconhece vira ambiente
   climatizado. Tudo pode ser corrigido depois; a origem fica registrada (e.origemIfc). */
const CLASSES_ESPACO = [[/garag|estacion/, "garagem"], [/banh|wc|sanit|lavabo|vesti/, "banheiro"], [/lixo|res[ií]duo/, "lixo"], [/piscina/, "piscina"],
  [/sauna/, "sauna"], [/churras|gourmet/, "churrasqueira"], [/circula|corredor|hall|escada|elevador|shaft|duto|varanda|sacada|terra[cç]o|acesso/, "nao_climatizado"],
  [/m[aá]quinas|bombas|medidores|t[eé]cnic|casa de/, "tecnico"]];
function classeEspaco(nome) { const t = String(nome || "").toLowerCase(); const c = CLASSES_ESPACO.find(([rx]) => rx.test(t)); return c ? c[1] : "climatizado"; }
function classeDe(s) {   /* nome primeiro; o tipo do elemento só quando o nome não diz nada (lago não é piscina) */
  const c = classeEspaco((s.nome_longo || "") + " " + (s.nome || "")); if (c !== "climatizado" || !s.tipo) return c;
  const t = classeEspaco(s.tipo === "técnico" ? "casa de máquinas" : s.tipo); return t === "piscina" ? "nao_climatizado" : t; }
function preencherDoIfc(ePadrao, espacos, arquivo) {
  const e = copia(ePadrao), lista = (espacos || []).map(s => ({ nome:(s.nome_longo || s.nome || "Espaço").trim(), area:num(s.area_m2) > 0 ? num(s.area_m2) : null, alt:num(s.altura_m), classe:classeDe(s), fonte:s.fonte }));
  const soma = c => lista.filter(s => s.classe === c).reduce((t, s) => t + (s.area || 0), 0), area = lista.reduce((t, s) => t + (s.area || 0), 0);
  e.tipologias = { pessoasDorm:e.tipologias ? e.tipologias.pessoasDorm : 2, lista:[{ n:"Edificação (do IFC)", q:1, area, dorm:0, banh:lista.filter(s => s.classe === "banheiro").length, vagas:0 }] };
  e.ac.amb = lista.filter(s => s.classe === "climatizado" && s.area > 0).map(s => ({ n:s.nome, area:s.area, dorm:0, override:null, equip:"", matriz:true, q:[], comum:1 }));
  e.vent.garArea = soma("garagem"); e.vent.lixoArea = soma("lixo");
  const alt = lista.filter(s => s.alt > 0); if (alt.length) { const pe = alt.reduce((t, s) => t + s.alt, 0) / alt.length; e.vent.garPe = pe; e.vent.lixoPe = pe; e.vent.peBanh = pe; }
  e.vent.outros = lista.filter(s => s.classe === "tecnico" && s.area > 0).map((s, i) => ({ id:"ifc" + i, n:s.nome, area:s.area, pe:s.alt || "", trocas:"" }));
  if (soma("piscina") > 0) e.piscina.area = soma("piscina");
  const sau = lista.find(s => s.classe === "sauna" && s.area > 0); if (sau) { e.ext = e.ext || {}; e.ext.saunaVol = sau.alt ? Math.round(sau.area * sau.alt * 100) / 100 : ""; }
  e.vent.churr = lista.filter(s => s.classe === "churrasqueira").map((s, i) => ({ id:"ifcch" + i, n:s.nome, coifaM:"", vazM:"" }));
  e.origemIfc = { arquivo:String(arquivo || ""), espacos:lista.length, area_total_m2:Math.round(area * 100) / 100, sem_area:lista.filter(s => !(s.area > 0)).map(s => s.nome), classes:lista.map(s => ({ nome:s.nome, area:s.area, classe:s.classe, fonte:s.fonte })) };
  return e;
}

/* PDF de planta → espaços (24/11/2026): lê os rótulos de área escritos na planta ("Sala 24,50 m²", "A = 12,3 m2") e o nome mais
   próximo acima ou ao lado. Só PDF com texto (vetorial); PDF escaneado ou imagem precisa de OCR (Tesseract no servidor, próxima
   etapa). Área que não aparece escrita não é calculada por aproximação. */
function espacosDoTexto(itens) {
  const rx = /(\d{1,4}(?:[.,]\d{1,2})?)\s*m\s*(?:²|2)(?![0-9A-Za-z])/i, out = [], usados = new Set();
  const txt = (itens || []).filter(i => i && String(i.s || "").trim()).map((i, k) => ({ k, s:String(i.s).trim(), x:+i.x || 0, y:+i.y || 0, p:i.p || 1 }));
  txt.forEach(t => { const m = rx.exec(t.s); if (!m) return; const area = num(m[1]); if (!(area > 0)) return;
    let nome = t.s.replace(rx, "").replace(/\b(a|área|area)\s*[=:]?\s*$/i, "").replace(/[=:–-]\s*$/, "").trim();
    if (!/[A-Za-zÀ-ú]{3,}/.test(nome)) { let melhor = null, dist = Infinity;
      txt.forEach(o => { if (o.p !== t.p || o.k === t.k || rx.test(o.s) || !/[A-Za-zÀ-ú]{3,}/.test(o.s) || usados.has(o.k)) return;
        const dy = o.y - t.y, dx = Math.abs(o.x - t.x); if (dy < -2 || dy > 40 || dx > 80) return; const d = dy + dx * 0.5; if (d < dist) { dist = d; melhor = o; } });
      if (melhor) { usados.add(melhor.k); nome = melhor.s; } }
    out.push({ nome:nome || "Espaço " + (out.length + 1), nome_longo:nome || "", area_m2:area, altura_m:null, fonte:"rótulo do PDF (página " + t.p + ")" }); });
  return out;
}
function ifcDados(estado, iSub) {
  const e = normalizar(estado), s = e.subprojetos[iSub];
  if (s.local.lat == null || s.local.lon == null) throw new Error("informe latitude e longitude do subprojeto " + (iSub + 1) + " (aba BIM e GIS)");
  const elementos = s.equipamentos.map((q, j) => { const props = { quantidade:num(q.qtd), tag:q.tag || "", fabricante:mk(q.fabricante), modelo:mk(q.modelo) };
    if (q.un === "BTU/h") props.btu_h = num(q.cap); else if (q.un === "m³/h") props.vazao_m3_h = num(q.cap); else if (q.un === "kW") props.potencia_kw = num(q.cap);
    (q.pecas || []).forEach((p, k) => { props["peca_" + (k + 1)] = mk(p.descricao) + " · " + mk(p.codigo, "part number"); });
    return { id:(q.tag || "eq" + (j + 1)), tipo:tipoIfc(q), nome:(q.tag ? q.tag + " — " : "") + (q.descricao || "Equipamento"), object_type:q.sistema || "AVAC",
      origem:"Estermic AVAC (teste)", posicao:{ x:j * 2, y:0, z:0 }, propriedades:Object.assign(props, q.selecao ? { categoria:q.selecao } : {}),
      caixa:(num(q.lx) > 0 && num(q.ly) > 0 && num(q.lz) > 0) ? { dx:num(q.lx), dy:num(q.ly), dz:num(q.lz) } : undefined }; });   /* bloco IFC: caixa com as medidas do catálogo do fabricante */
  return { projeto:{ id:"estermic-" + s.id, nome:e.cliente.nome + " — " + nomeSub(s, iSub) },
    site:{ nome:mk(s.local.endereco, "endereço"), lat:num(s.local.lat), lon:num(s.local.lon), altitude_m:num(s.local.altitude) },
    edificacoes:[{ id:"ed1", nome:nomeSub(s, iSub), pavimentos:[{ id:"terreo", nome:"Térreo", elevacao_m:0 }] }], elementos };
}
function geojson(estado) {
  const e = normalizar(estado);
  return { type:"FeatureCollection", features:e.subprojetos.filter(s => s.local.lat != null && s.local.lon != null).map(s => {
    const i = e.subprojetos.indexOf(s);
    return { type:"Feature", geometry:{ type:"Point", coordinates:[num(s.local.lon), num(s.local.lat)] },
      properties:{ cliente:e.cliente.nome, subprojeto:nomeSub(s, i), contrato:mk(s.contrato.numero), endereco:mk(s.local.endereco), municipio:mk(s.local.municipio), uf:mk(s.local.uf) } }; }) };
}

/* ════════ Documentos (blocos: {h,t} {t} {lista:[...]} {tabela:{cab,linhas,legenda}}) ════════ */
function cabecalhoDoc(e, s, i, tipo) {
  const b = [{ h:1, t:tipo + " — " + nomeSub(s, i) },
    { tabela:{ cab:["Campo", "Valor"], linhas:[["Cliente", e.cliente.nome], ["Subprojeto", nomeSub(s, i)], ["Contrato", mk(s.contrato.numero)],
      ["Local", mk(s.local.endereco) + (vazio(s.local.municipio) ? "" : " — " + s.local.municipio + "/" + (s.local.uf || ""))],
      ["Elaborado por", e.emissor.nome]], legenda:"Identificação" } }];
  if (!s.dadosConfirmados) b.splice(1, 0, e.conjunto
    ? { t:e.conjunto.rotulo + " — dados tirados dos documentos técnicos listados em \"Fontes\"; o que não tem fonte fica [MARCADOR]. Não entregar ao cliente.", destaque:true }
    : { t:"EXEMPLO — os números deste documento vêm do exemplo da planilha PHYSIS_AVAC-5, não de dados da " + e.cliente.nome + ". Não entregar ao cliente.", destaque:true });
  if (e.teste) b.splice(1, 0, { t:"VERSÃO DE TESTE — revisão interna antes da emissão.", destaque:true });
  return b;
}
function dadosDoProjeto(e, s) {
  const b = [];
  if (s.ambientes.length) b.push({ h:2, t:"Ambientes e áreas (com fonte)" }, { tabela:{ cab:["Ambiente", "Área (m²)", "Ocupação", "Fonte"],
    linhas:s.ambientes.map(a => [mk(a.nome), a.area == null ? "sem fonte" : a.area, mk(a.ocupacao), mk(a.fonte)]) } });
  const pr = ((e.conjunto && e.conjunto.premissas) || []).concat(s.premissas);
  if (pr.length) b.push({ h:2, t:"Premissas do projeto (com fonte)" }, { tabela:{ cab:["Premissa", "Fonte"], linhas:pr.map(x => [x.t, mk(x.fonte)]) } });
  return b; }
function fontes(e) { const f = (e.conjunto && e.conjunto.fontes) || []; return f.length ? [{ h:2, t:"Fontes" }, { lista:f.slice() }] : []; }
function memorial(estado, iSub, AVAC, CT) {
  const e = normalizar(estado), s = e.subprojetos[iSub], R = AVAC.calcular(entradasAvac(s)), b = cabecalhoDoc(e, s, iSub, "Memorial de cálculo");
  b.push({ h:2, t:"Método e normas" }, { t:"Contas do módulo AVAC da Physis (planilha PHYSIS_AVAC-5), sem alteração. Normas citadas como estão no código do módulo: "
    + "ABNT NBR 16401-1:2008 (carga térmica), NBR 16401-2 e 16401-3 (conforto e ar externo), NBR 14880 (pressurização de escada), NBR 15569 (aquecimento solar, método simplificado), NBR 5410 (quadro elétrico, simplificado). Conferir o texto vigente de cada norma antes da emissão." });
  if (CT && s.dados.cargatermica && s.dados.cargatermica.e) { const c = s.dados.cargatermica.e, r = CT.calcular(c.ambientes, c.clima, c.opcoes);
    b.push({ h:2, t:"Carga térmica por ambiente (NBR 16401-1)" }, { tabela:{ cab:["Ambiente", "Hora do pico", "Total no pico (W)", "Projeto (W)", "Projeto (BTU/h)", "Projeto (TR)"],
      linhas:r.ambientes.map(a => [a.nome || "—", a.pico.h, Math.round(a.pico.total), Math.round(a.projeto.W), Math.round(a.projeto.btuh), +a.projeto.tr.toFixed(2)]), legenda:"Carga de resfriamento com fator de segurança " + r.opcoes.fs } });
    if (r.avisos && r.avisos.length) b.push({ lista:r.avisos.slice() }); }
  dadosDoProjeto(e, s).forEach(x => b.push(x));
  R.memoria.forEach(m => { b.push({ h:2, t:m.titulo + " — " + m.situacao });
    b.push(m.linhas.length ? { lista:m.linhas.slice() } : { t:"Sistema " + m.situacao + ": não calculado nesta emissão." }); });
  b.push({ t:"Documento de anteprojeto gerado pelo sistema; não substitui o projeto assinado pelo responsável técnico (ART " + MARCADOR + ")." });
  return b.concat(fontes(e));
}
function relatorio(estado, iSub, AVAC) {
  const e = normalizar(estado), s = e.subprojetos[iSub], R = AVAC.calcular(entradasAvac(s)), b = cabecalhoDoc(e, s, iSub, "Relatório descritivo");
  b.push({ h:2, t:"Objeto e escopo" }, { t:mk(s.escopo, "escopo do subprojeto") },
    { h:2, t:"Sistemas e resultados principais" },
    { tabela:{ cab:["Sistema", "Grandeza", "Valor", "Base"], linhas:R.resumo.map(x => [x.sistema, x.grandeza, typeof x.valor === "number" ? +x.valor.toFixed(2) : String(x.valor), x.base || ""]), legenda:"Resumo do módulo AVAC" } },
    { h:2, t:"Equipamentos" }, { t:s.equipamentos.length + " item(ns) na lista de equipamentos (arquivo ODS anexo)." },
    { h:2, t:"Pendências desta emissão" }, { lista:pendencias(e).filter(p => p.indexOf("Subprojeto " + (iSub + 1)) === 0 || !/^Subprojeto/.test(p)) });
  return b.concat(dadosDoProjeto(e, s), fontes(e));
}
/* "EP" = ESTUDO PRELIMINAR (resposta da dona de 21/11/2026): concepção, alternativas, pré-dimensionamento e estimativa de
   ordem de grandeza. Custos e prazos nunca são inventados: sem fonte, ficam [MARCADOR]. */
function estudoPreliminar(estado, iSub, AVAC, CT) {
  const e = normalizar(estado), s = e.subprojetos[iSub], b = cabecalhoDoc(e, s, iSub, "EP — Estudo Preliminar");
  const R = AVAC ? AVAC.calcular(entradasAvac(s)) : null;
  b.push({ h:2, t:"1. Concepção" }, { t:"Objeto e escopo: " + mk(s.escopo, "escopo do subprojeto") });
  dadosDoProjeto(e, s).forEach(x => b.push(x.h ? { h:3, t:x.t } : x));
  b.push({ h:2, t:"2. Alternativas" });
  if (s.alternativas.length) b.push({ tabela:{ cab:["Alternativa", "Descrição", "Fonte"], linhas:s.alternativas.map(a => [mk(a.nome), mk(a.descricao), mk(a.fonte)]) } });
  const temCT = !!(CT && s.dados.cargatermica && s.dados.cargatermica.e);
  if (temCT) { const c = s.dados.cargatermica.e, r = CT.calcular(c.ambientes, c.clima, c.opcoes);
    if (r.sistema && r.sistema.opcoes) b.push({ tabela:{ cab:["Sistema (módulo de carga térmica)", "Viável?", "Motivo", "Energia (kWh/ano)"],
      linhas:r.sistema.opcoes.map(o => [o.nome, o.viavel ? "sim" : "não", o.motivo || "", o.kwh_ano == null ? "—" : Math.round(o.kwh_ano)]), legenda:"Comparação de sistemas da carga térmica (NBR 16401-1)" } }); }
  if (!s.alternativas.length && !temCT) b.push({ t:"Alternativas " + MARCADOR + " (comparar ao menos duas soluções de climatização e ventilação)." });
  b.push({ h:2, t:"3. Pré-dimensionamento" });
  if (R) { const lin = R.resumo.filter(x => R.status[{ "Ar condicionado":"ac", "Ventilação":"vent", "Pressurização":"press", "Aquecimento solar":"solar", "Piscina":"piscina" }[x.sistema]] === "ativo");
    b.push(lin.length ? { tabela:{ cab:["Sistema", "Grandeza", "Valor", "Base"], linhas:lin.map(x => [x.sistema, x.grandeza, typeof x.valor === "number" ? +x.valor.toFixed(2) : String(x.valor), x.base || ""]), legenda:"Resumo do módulo AVAC (contas do módulo base)" } }
      : { t:"Nenhum sistema calculado no módulo AVAC para este subprojeto " + MARCADOR + "." }); }
  b.push({ tabela:{ cab:["TAG", "Equipamento", "Qtd.", "Capacidade", "Fabricante/modelo"],
    linhas:s.equipamentos.length ? s.equipamentos.map(q => [q.tag || "", q.descricao || "", q.qtd == null ? MARCADOR : q.qtd, q.cap == null ? "sem fonte" : q.cap + " " + (q.un || ""), mk(q.fabricante) + " / " + mk(q.modelo)]) : [[MARCADOR, "", "", "", ""]],
    legenda:"Equipamentos pré-dimensionados" } });
  b.push({ h:2, t:"4. Estimativa de ordem de grandeza" },
    { tabela:{ cab:["Item", "Ordem de grandeza", "Base"], linhas:[["Investimento em AVAC", MARCADOR, MARCADOR], ["Consumo de energia (kWh/ano)", MARCADOR, MARCADOR], ["Prazo de implantação", MARCADOR, MARCADOR]] } },
    { t:"Estimativa a preencher com cotações ou base de custos com fonte; o sistema não estima preço." });
  return b.concat(fontes(e));
}

/* ════════ ODF com a marca do CLIENTE (sem a marca Physis além do "elaborado por") ════════ */
function utf8(s) { return typeof TextEncoder !== "undefined" ? new TextEncoder().encode(String(s)) : Uint8Array.from(unescape(encodeURIComponent(String(s))), c => c.charCodeAt(0)); }
function b64(u8) { let s = ""; for (let i = 0; i < u8.length; i++) s += String.fromCharCode(u8[i]);
  if (typeof btoa === "function") return btoa(s);
  const A = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"; let o = "";
  for (let i = 0; i < s.length; i += 3) { const n = (s.charCodeAt(i) << 16) | ((s.charCodeAt(i + 1) || 0) << 8) | (s.charCodeAt(i + 2) || 0);
    o += A[n >> 18 & 63] + A[n >> 12 & 63] + (i + 1 < s.length ? A[n >> 6 & 63] : "=") + (i + 2 < s.length ? A[n & 63] : "="); } return o; }
let TAB_CRC = null;
function crc32(u8) { if (!TAB_CRC) { TAB_CRC = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; TAB_CRC[n] = c >>> 0; } }
  let c = 0xFFFFFFFF; for (let i = 0; i < u8.length; i++) c = TAB_CRC[(c ^ u8[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
/* zip sem compressão (armazenado): simples, aberto e suficiente para ODF; o mimetype vai primeiro */
function zip(arqs) {
  const u16 = v => [v & 255, v >>> 8 & 255], u32 = v => [v & 255, v >>> 8 & 255, v >>> 16 & 255, v >>> 24 & 255];
  const partes = [], central = []; let pos = 0;
  arqs.forEach(a => { const nome = utf8(a.nome), d = typeof a.dados === "string" ? utf8(a.dados) : a.dados, crc = crc32(d), fl = /[^\x20-\x7e]/.test(a.nome) ? 0x0800 : 0;
    const cab = Uint8Array.from([0x50, 0x4B, 3, 4].concat(u16(20), u16(fl), u16(0), u16(0), u16(0x21), u32(crc), u32(d.length), u32(d.length), u16(nome.length), u16(0)));
    partes.push(cab, nome, d);
    central.push(Uint8Array.from([0x50, 0x4B, 1, 2].concat(u16(20), u16(20), u16(fl), u16(0), u16(0), u16(0x21), u32(crc), u32(d.length), u32(d.length), u16(nome.length), u16(0), u16(0), u16(0), u16(0), u32(0), u32(pos))), nome);
    pos += cab.length + nome.length + d.length; });
  const tamC = central.reduce((s, p) => s + p.length, 0);
  const todas = partes.concat(central, [Uint8Array.from([0x50, 0x4B, 5, 6].concat(u16(0), u16(0), u16(arqs.length), u16(arqs.length), u32(tamC), u32(pos), u16(0)))]);
  const out = new Uint8Array(todas.reduce((s, p) => s + p.length, 0)); let o = 0; todas.forEach(p => { out.set(p, o); o += p.length; }); return out;
}
const x = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;" }[c])).replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g, "");
const NS = 'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:meta="urn:oasis:names:tc:opendocument:xmlns:meta:1.0" xmlns:svg="urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"';
const CAB = '<?xml version="1.0" encoding="UTF-8"?>\n';
/* Marca do cliente: valores reais quando a Estermic enviar; até lá, NEUTROS (cinzas e fontes genéricas), nunca a marca Physis */
const NEUTRO = { corPrincipal:"#1B1F23", corTexto:"#1B1F23", corLinha:"#D9D3C2", fonteTitulo:"serif", fonteTexto:"sans-serif" };
const corOk = c => /^#[0-9A-Fa-f]{6}$/.test(String(c || ""));
function marcaEfetiva(m) { m = m || {};
  return { nome:m.nome || "Cliente", logoPng:m.logoPng || null,
    corPrincipal:corOk(m.corPrincipal) ? m.corPrincipal : NEUTRO.corPrincipal, corTexto:corOk(m.corTexto) ? m.corTexto : NEUTRO.corTexto,
    corLinha:corOk(m.corLinha) ? m.corLinha : NEUTRO.corLinha,
    fonteTitulo:vazio(m.fonteTitulo) ? NEUTRO.fonteTitulo : m.fonteTitulo, fonteTexto:vazio(m.fonteTexto) ? NEUTRO.fonteTexto : m.fonteTexto,
    neutra:!(corOk(m.corPrincipal) && !vazio(m.fonteTitulo) && m.logoPng) }; }
const fontesXml = M => '<office:font-face-decls><style:font-face style:name="FT" svg:font-family="' + x(M.fonteTitulo) + '"/><style:font-face style:name="FX" svg:font-family="' + x(M.fonteTexto) + '"/></office:font-face-decls>';
function metaXml(meta) { return CAB + '<office:document-meta ' + NS + ' office:version="1.3"><office:meta><meta:generator>Sistema Physis/estermic-avac teste</meta:generator><dc:title>' + x(meta.titulo) + "</dc:title><dc:creator>" + x(meta.autor || "Physis Engineering") + "</dc:creator><dc:language>pt-BR</dc:language></office:meta></office:document-meta>"; }
function manifesto(tipo, extras) { return CAB + '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3"><manifest:file-entry manifest:full-path="/" manifest:media-type="' + tipo + '" manifest:version="1.3"/>'
  + ["content.xml", "styles.xml", "meta.xml"].map(f => '<manifest:file-entry manifest:full-path="' + f + '" manifest:media-type="text/xml"/>').join("")
  + (extras || []).map(f => '<manifest:file-entry manifest:full-path="' + f + '" manifest:media-type="image/png"/>').join("") + "</manifest:manifest>"; }
function decodB64(s) { const bin = typeof atob === "function" ? atob(s) : null; if (bin == null) return null; const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }
function odt(blocos, marca, meta) {
  const M = marcaEfetiva(marca); meta = meta || {}; let tn = 0;
  const corpo = (blocos || []).map(b => {
    if (b.h) return '<text:h text:style-name="H' + Math.min(3, b.h) + '" text:outline-level="' + Math.min(3, b.h) + '">' + x(b.t) + "</text:h>";
    if (b.lista) return '<text:list text:style-name="L1">' + b.lista.map(l => '<text:list-item><text:p text:style-name="P">' + x(l) + "</text:p></text:list-item>").join("") + "</text:list>";
    if (b.tabela) { const T = b.tabela, nc = T.cab.length; tn++;
      return (T.legenda ? '<text:p text:style-name="Leg">' + x(T.legenda) + "</text:p>" : "") + '<table:table table:name="Tabela' + tn + '" table:style-name="Tab"><table:table-column table:number-columns-repeated="' + nc + '"/>'
        + '<table:table-header-rows><table:table-row>' + T.cab.map(c => '<table:table-cell table:style-name="CC" office:value-type="string"><text:p text:style-name="PC">' + x(c) + "</text:p></table:table-cell>").join("") + "</table:table-row></table:table-header-rows>"
        + T.linhas.map(l => "<table:table-row>" + T.cab.map((_, k) => '<table:table-cell table:style-name="CD" office:value-type="string"><text:p text:style-name="P">' + x(l[k]) + "</text:p></table:table-cell>").join("") + "</table:table-row>").join("") + "</table:table>"; }
    return '<text:p text:style-name="' + (b.destaque ? "Dest" : "P") + '">' + x(b.t) + "</text:p>"; }).join("");
  const logo = M.logoPng ? decodB64(M.logoPng) : null;
  const logoXml = logo ? '<draw:frame draw:name="logo" text:anchor-type="as-char" svg:width="3cm" svg:height="1.2cm"><draw:image xlink:href="Pictures/logo.png" xlink:type="simple" xlink:show="embed" xlink:actuate="onLoad"/></draw:frame> ' : "";
  const conteudo = CAB + '<office:document-content ' + NS + ' office:version="1.3">' + fontesXml(M)
    + '<office:automatic-styles><style:style style:name="Tab" style:family="table"><style:table-properties style:width="17cm" table:align="margins"/></style:style>'
    + '<style:style style:name="CC" style:family="table-cell"><style:table-cell-properties fo:background-color="' + M.corPrincipal + '" fo:padding="0.08cm" fo:border="0.5pt solid ' + M.corLinha + '"/></style:style>'
    + '<style:style style:name="CD" style:family="table-cell"><style:table-cell-properties fo:padding="0.08cm" fo:border="0.5pt solid ' + M.corLinha + '"/></style:style></office:automatic-styles>'
    + "<office:body><office:text>" + corpo + "</office:text></office:body></office:document-content>";
  const pstyle = (n, fam, extra, texto) => '<style:style style:name="' + n + '" style:family="paragraph"' + (extra || "") + ">" + (texto || "") + "</style:style>";
  const estilos = CAB + '<office:document-styles ' + NS + ' office:version="1.3">' + fontesXml(M) + "<office:styles>"
    + '<style:default-style style:family="paragraph"><style:text-properties style:font-name="FX" fo:font-size="10.5pt" fo:color="' + M.corTexto + '" fo:language="pt" fo:country="BR"/></style:default-style>'
    + pstyle("P", 0, "", '<style:paragraph-properties fo:margin-bottom="0.18cm"/>')
    + pstyle("H1", 0, ' style:default-outline-level="1"', '<style:paragraph-properties fo:margin-top="0.3cm" fo:margin-bottom="0.25cm"/><style:text-properties style:font-name="FT" fo:font-size="18pt" fo:font-weight="bold" fo:color="' + M.corPrincipal + '"/>')
    + pstyle("H2", 0, ' style:default-outline-level="2"', '<style:paragraph-properties fo:margin-top="0.35cm" fo:margin-bottom="0.15cm" fo:border-bottom="0.5pt solid ' + M.corLinha + '"/><style:text-properties style:font-name="FT" fo:font-size="13pt" fo:font-weight="bold" fo:color="' + M.corPrincipal + '"/>')
    + pstyle("H3", 0, ' style:default-outline-level="3"', '<style:text-properties style:font-name="FT" fo:font-size="11.5pt" fo:font-weight="bold"/>')
    + pstyle("PC", 0, "", '<style:text-properties fo:color="#FFFFFF" fo:font-weight="bold" fo:font-size="9.5pt"/>')
    + pstyle("Leg", 0, "", '<style:text-properties fo:font-style="italic" fo:font-size="9pt"/>')
    + pstyle("Dest", 0, "", '<style:paragraph-properties fo:padding="0.15cm" fo:border="1pt solid ' + M.corPrincipal + '"/><style:text-properties fo:font-weight="bold"/>')
    + pstyle("Cab", 0, "", '<style:text-properties fo:font-size="9pt"/>') + pstyle("Rod", 0, "", '<style:paragraph-properties fo:text-align="center"/><style:text-properties fo:font-size="8pt"/>')
    + '<text:list-style style:name="L1"><text:list-level-style-bullet text:level="1" text:bullet-char="•"><style:list-level-properties text:list-level-position-and-space-mode="label-alignment"><style:list-level-label-alignment text:label-followed-by="listtab" fo:text-indent="-0.4cm" fo:margin-left="0.6cm"/></style:list-level-properties></text:list-level-style-bullet></text:list-style>'
    + "</office:styles>"
    + '<office:automatic-styles><style:page-layout style:name="pm1"><style:page-layout-properties fo:page-width="21cm" fo:page-height="29.7cm" fo:margin-top="1.5cm" fo:margin-bottom="1.5cm" fo:margin-left="2cm" fo:margin-right="2cm"/></style:page-layout></office:automatic-styles>'
    + '<office:master-styles><style:master-page style:name="Standard" style:page-layout-name="pm1"><style:header><text:p text:style-name="Cab">' + logoXml + x(M.nome) + " · " + x(meta.titulo) + (meta.teste ? " · VERSÃO DE TESTE" : "") + "</text:p></style:header>"
    + '<style:footer><text:p text:style-name="Rod">Elaborado por ' + x(meta.elaboradoPor || "Physis Engineering") + ' · página <text:page-number text:select-page="current">1</text:page-number> de <text:page-count>1</text:page-count></text:p></style:footer></style:master-page></office:master-styles></office:document-styles>';
  const tipo = "application/vnd.oasis.opendocument.text", arqs = [{ nome:"mimetype", dados:tipo }, { nome:"META-INF/manifest.xml", dados:manifesto(tipo, logo ? ["Pictures/logo.png"] : []) },
    { nome:"content.xml", dados:conteudo }, { nome:"styles.xml", dados:estilos }, { nome:"meta.xml", dados:metaXml(meta) }];
  if (logo) arqs.push({ nome:"Pictures/logo.png", dados:logo });
  return zip(arqs);
}
function ods(tabelas, marca, meta) {
  const M = marcaEfetiva(marca); meta = meta || {};
  const cel = (v, st) => typeof v === "number" && isFinite(v) ? '<table:table-cell table:style-name="' + st + '" office:value-type="float" office:value="' + v + '"><text:p>' + x(String(v).replace(".", ",")) + "</text:p></table:table-cell>"
    : '<table:table-cell table:style-name="' + st + '" office:value-type="string"><text:p>' + x(v) + "</text:p></table:table-cell>";
  const folhas = (tabelas || []).map((T, i) => '<table:table table:name="' + x(String(T.nome || "Folha " + (i + 1)).replace(/[\[\]*?:\/\\']/g, " ").slice(0, 31)) + '"><table:table-column table:number-columns-repeated="' + T.cab.length + '"/>'
    + "<table:table-row>" + cel(M.nome + " · " + (meta.titulo || "") + (meta.teste ? " · VERSÃO DE TESTE" : ""), "Ti") + "</table:table-row>"
    + "<table:table-row>" + T.cab.map(c => cel(c, "Cab")).join("") + "</table:table-row>"
    + T.linhas.map(l => "<table:table-row>" + T.cab.map((_, k) => cel(l[k] == null ? "" : l[k], "Ce")).join("") + "</table:table-row>").join("")
    + "<table:table-row>" + cel("Elaborado por " + (meta.elaboradoPor || "Physis Engineering"), "Ce") + "</table:table-row></table:table>").join("");
  const conteudo = CAB + '<office:document-content ' + NS + ' office:version="1.3">' + fontesXml(M) + "<office:automatic-styles>"
    + '<style:style style:name="Ti" style:family="table-cell"><style:text-properties style:font-name="FT" fo:font-size="13pt" fo:font-weight="bold" fo:color="' + M.corPrincipal + '"/></style:style>'
    + '<style:style style:name="Cab" style:family="table-cell"><style:table-cell-properties fo:background-color="' + M.corPrincipal + '" fo:border="0.5pt solid ' + M.corLinha + '"/><style:text-properties fo:color="#FFFFFF" fo:font-weight="bold"/></style:style>'
    + '<style:style style:name="Ce" style:family="table-cell"><style:table-cell-properties fo:border="0.5pt solid ' + M.corLinha + '"/></style:style>'
    + "</office:automatic-styles><office:body><office:spreadsheet>" + folhas + "</office:spreadsheet></office:body></office:document-content>";
  const estilos = CAB + '<office:document-styles ' + NS + ' office:version="1.3">' + fontesXml(M) + '<office:styles><style:default-style style:family="table-cell"><style:text-properties style:font-name="FX" fo:font-size="10pt" fo:color="' + M.corTexto + '"/></style:default-style></office:styles></office:document-styles>';
  const tipo = "application/vnd.oasis.opendocument.spreadsheet";
  return zip([{ nome:"mimetype", dados:tipo }, { nome:"META-INF/manifest.xml", dados:manifesto(tipo) }, { nome:"content.xml", dados:conteudo }, { nome:"styles.xml", dados:estilos }, { nome:"meta.xml", dados:metaXml(meta) }]);
}
function tabelaFinanceiro(estado) {
  const e = normalizar(estado), linhas = [];
  e.subprojetos.forEach((s, i) => { const F = financeiro(s);
    F.porFase.forEach(f => linhas.push([nomeSub(s, i), mk(s.contrato.numero), f.nome, f.valor == null ? MARCADOR : f.valor, f.prazo || MARCADOR, f.faturado, f.recebido, f.situacao]));
    linhas.push([nomeSub(s, i), mk(s.contrato.numero), "TOTAL", F.contratado == null ? MARCADOR : F.contratado, mk(s.contrato.prazoFinal), F.faturado, F.recebido, F.aFaturar == null ? MARCADOR : "a faturar " + F.aFaturar.toFixed(2)]); });
  return { nome:"Financeiro por fase", cab:["Subprojeto", "Contrato", "Fase", "Valor (R$)", "Prazo", "Faturado (R$)", "Recebido (R$)", "Situação"], linhas };
}

const API = { versao:"ESTERMIC-AVAC-teste-1", MARCADOR, CONFERIR, SELECAO, preencherDoIfc, classeEspaco, espacosDoTexto, padrao, normalizar, nomeSub, financeiro, situacaoFase, alertas, pendencias, rascunhoNota,
  equipamentosDoCalculo, sugerirDaBase, tabelaEquipamentos, tabelaFinanceiro, ifcDados, geojson, memorial, relatorio, estudoPreliminar, FASES_PADRAO, PECAS_PADRAO, pecasPadrao, faseVazia, odt, ods, zip, crc32, marcaEfetiva, b64, utf8 };
global.ESTERMIC = API;
if (typeof module !== "undefined" && module.exports) module.exports = API;
})(typeof window !== "undefined" ? window : this);
