/* Physis · O que o hub aprendeu, na tela (window.PhysisAprendizadoUI)
   Mostra na aba Resiliência climática as quatro análises do aprendizado do hub (physis_hub/aprendizado.py,
   docs/APRENDIZADO.md §3) e o cartão "Receber estes avisos" (physis_hub/alertas_clima.py, docs/ALERTAS_CLIMA.md §2 e §5):
     chance de chuva aprendida · sensores estranhos · consumo esperado × real · quando irrigar · assinatura dos avisos.
   Regras de tela: a explicação vai sempre junto do número; com poucos dados aparece "aprendendo (poucos dados)";
   o modelo é mais uma opinião e nunca esconde a previsão das fontes. Sem o computador central (arquivo aberto
   direto, demonstração, 401/404), nada é inventado: o cartão diz que precisa do servidor.
   API: iniciar({aoMudar, perfil, fetch, ligado, nomeAtivo}); carregar(forcar); cartaoChuva(n); cartaoAnomalias(n);
   cartaoConsumo(n); cartaoIrrigacao(n); cartaoAvisos(n); resumoAnomalias(); listaAnomalias(); secaoResiliencia(n);
   estado(); I18N; I18N_RX. Eventos por atributos data-pau-…, ligados uma vez no document. */
(function (global) {
  "use strict";
  var doc = global.document;
  var ROTAS = { chuva: "api/aprendizado/previsao-chuva", anomalias: "api/aprendizado/anomalias", consumo: "api/aprendizado/consumo",
    irrigacao: "api/aprendizado/irrigacao", modelos: "api/aprendizado/estado", assinaturas: "api/alertas/assinaturas", historico: "api/alertas/historico" };
  var INTERVALO = 60000;
  var ATIVIDADES = { cafe: "Café", graos: "Grãos", gado: "Gado", gado_leite: "Gado de leite", irrigacao: "Irrigação", hortifruti: "Hortifrúti", hospedagem: "Hospedagem" };
  var GRANDEZAS = { umidade_solo: "Umidade do solo", temperatura: "Temperatura", umidade: "Umidade do ar", bateria: "Bateria", rssi: "Sinal do rádio (RSSI)",
    snr: "Sinal do rádio (SNR)", nivel: "Nível", energia: "Energia", tensao: "Tensão", corrente: "Corrente", vazao: "Vazão", pressao: "Pressão", fp: "Fator de potência" };
  var TIPOS = { fora_do_normal: "Fora do normal", salto_impossivel: "Salto impossível", travado: "Sensor travado", bateria_acabando: "Bateria acabando" };
  var ACOES = { irrigar_agora: ["al", "Irrigar agora"], agendar: ["in", "Programar a rega"], aguardar_chuva: ["in", "Aguardar a chuva"],
    nao_precisa: ["ok", "Não precisa irrigar"], sem_dado: ["in", "Sem dados suficientes"] };
  var ESTADOS_ENVIO = { enfileirado: "Na fila do e-mail", enviado: "Enviado", falhou: "Não saiu" };

  var cfg = { aoMudar: null, perfil: null, fetch: null, ligado: null, nomeAtivo: null };
  var R = {};            // por recurso: {estado: "vazio"|"carregando"|"ok"|"erro"|"sem_servidor"|"sem_sessao", dados, erro}
  Object.keys(ROTAS).forEach(function (k) { R[k] = { estado: "vazio", dados: null, erro: "" }; });
  var ultimo = 0, emCurso = null, assinaturaDados = "";
  var F = null;          // formulário de avisos (fica guardado entre um redesenho e outro)
  var av = { msg: "", tipo: "", sair: null, ocupado: false };
  var ligados = false;

  /* ── utilidades ── */
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function nf(v, casas) { if (v == null || !isFinite(v)) return "—"; var c = casas == null ? 1 : casas; try { return Number(v).toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c }); } catch (e) { return Number(v).toFixed(c).replace(".", ","); } }
  function pct(p) { return p == null || !isFinite(p) ? "—" : Math.round(100 * p) + "%"; }
  function dois(n) { return (n < 10 ? "0" : "") + n; }
  function diaMes(iso) { var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || "")); return m ? m[3] + "/" + m[2] : String(iso || ""); }
  function dataHora(ts) { if (!ts) return "—"; var d = new Date(ts * 1000); return dois(d.getDate()) + "/" + dois(d.getMonth() + 1) + " " + dois(d.getHours()) + ":" + dois(d.getMinutes()); }
  function titulo(n, id, texto) { n = n === 3 ? 3 : n === 4 ? 4 : 2; return "<h" + n + ' id="' + id + '"' + (n >= 3 ? ' class="t3"' : "") + ">" + texto + "</h" + n + ">"; }
  function sub(n) { return Math.min(4, (n === 3 ? 3 : 2) + 1); }
  function anunciar(t) { try { if (typeof global.anunciar === "function") global.anunciar(t); } catch (e) {} }
  function nomeAtivo(a) {
    if (typeof cfg.nomeAtivo === "function") { try { var x = cfg.nomeAtivo(a); if (x) return String(x); } catch (e) {} }
    var m = /-no(\d+)(?:-(a|b))?(?:-ar)?$/i.exec(String(a || ""));
    if (!m) return String(a || "");
    return "Nó " + parseInt(m[1], 10) + (m[2] ? " · zona " + m[2].toUpperCase() : "");
  }
  function aprendendo() { return ' <span class="selo at">aprendendo (poucos dados)</span>'; }
  function servidorPossivel() {
    try { var p = global.location.protocol; if (p !== "http:" && p !== "https:") return false; } catch (e) { return false; }
    if (typeof cfg.ligado === "function") { try { return !!cfg.ligado(); } catch (e) { return false; } }
    return true;
  }
  function f() { return cfg.fetch || (typeof global.fetch === "function" ? global.fetch.bind(global) : null); }

  /* ── carregar (uma vez por minuto; nunca lança erro) ── */
  function buscar(nome) {
    var fx = f(); if (!fx) { R[nome] = { estado: "sem_servidor", dados: null, erro: "" }; return Promise.resolve(); }
    if (R[nome].estado !== "ok") R[nome].estado = "carregando";
    return Promise.resolve().then(function () { return fx(ROTAS[nome], { cache: "no-store", credentials: "same-origin", headers: { Accept: "application/json" } }); })
      .then(function (r) {
        if (r.status === 401 || r.status === 403) { R[nome] = { estado: "sem_sessao", dados: null, erro: "" }; return; }
        if (r.status === 404 || r.status === 501) { R[nome] = { estado: "sem_servidor", dados: null, erro: "" }; return; }
        return r.json().then(function (j) {
          if (!r.ok || !j || j.ok === false) R[nome] = { estado: "erro", dados: null, erro: (j && j.erro) || ("HTTP " + r.status) };
          else R[nome] = { estado: "ok", dados: j, erro: "" };
        });
      })
      .catch(function () { R[nome] = { estado: "sem_servidor", dados: null, erro: "" }; });
  }
  function avisarHost() {
    var marca = JSON.stringify(Object.keys(R).map(function (k) { return [R[k].estado, R[k].dados]; }));
    if (marca === assinaturaDados) return; assinaturaDados = marca;
    if (typeof cfg.aoMudar === "function") { try { cfg.aoMudar(); } catch (e) {} }
  }
  function carregar(forcar) {
    try {
      if (!servidorPossivel()) { Object.keys(R).forEach(function (k) { R[k] = { estado: "sem_servidor", dados: null, erro: "" }; }); return Promise.resolve().then(function () { avisarHost(); return estado(); }); }   // depois: carregar() pode ser chamado de dentro do desenho da tela
      var agora = Date.now();
      if (emCurso) return emCurso;
      if (!forcar && ultimo && agora - ultimo < INTERVALO) return Promise.resolve(estado());
      ultimo = agora;
      emCurso = Promise.all(Object.keys(ROTAS).map(buscar)).catch(function () {}).then(function () { emCurso = null; preencherForm(false); avisarHost(); return estado(); });
      return emCurso;
    } catch (e) { emCurso = null; return Promise.resolve(estado()); }
  }
  function estado() {
    var o = {}; Object.keys(R).forEach(function (k) { o[k] = R[k].estado; });
    var ks = Object.keys(R), todos = function (e) { return ks.every(function (k) { return R[k].estado === e; }); };
    o.geral = todos("sem_servidor") ? "sem_servidor" : ks.some(function (k) { return R[k].estado === "ok"; }) ? "ok" : ks.some(function (k) { return R[k].estado === "carregando" || R[k].estado === "vazio"; }) ? "carregando" : "erro";
    o.ultimo = ultimo; return o;
  }
  function iniciar(o) {
    o = o || {}; ["aoMudar", "perfil", "fetch", "ligado", "nomeAtivo"].forEach(function (k) { if (o[k] !== undefined) cfg[k] = o[k]; });
    ligarEventos(); estilo(); return api;
  }

  /* ── pedaços comuns ── */
  function semDados(nome) {
    var r = R[nome];
    if (r.estado === "vazio" || r.estado === "carregando") return '<p class="t2">Carregando…</p>';
    if (r.estado === "sem_servidor") return '<p class="t2">Precisa do computador central (hub) deste lugar, que aprende com os dados guardados nele. Sem ele, este cartão fica vazio: nenhum número é inventado.</p>';
    if (r.estado === "sem_sessao") return '<p class="t2">Entre com usuário e senha para ver.</p>';
    if (r.estado === "erro") return '<p class="t2"><span>O computador central não entregou estes dados agora.</span> <span>Tenta de novo em 1 minuto.</span></p>';
    return "";
  }
  function cartao(n, id, tit, corpo, extra) { return '<section class="cartao pau-cartao' + (extra ? " " + extra : "") + '" aria-labelledby="' + id + '">' + titulo(n, id, tit) + corpo + "</section>"; }
  function modoModelo(nome) {
    var m = R.modelos.estado === "ok" ? (R.modelos.dados.modelos || []).filter(function (x) { return x.nome === nome; })[0] : null;
    return m && m.metricas ? m.metricas.modo : null;
  }

  /* ── 1. Chance de chuva aprendida ── */
  function cartaoChuva(n) {
    var id = "pau-h-chuva", tit = "Previsão deste lugar (aprendida)";
    var opiniao = '<p class="t2 pq">O modelo é mais uma opinião: confira sempre a previsão das fontes (INMET, CEMADEN e Open-Meteo) nos próximos dias.</p>';
    if (R.chuva.estado !== "ok") return cartao(n, id, tit, semDados("chuva") + opiniao);
    var d = R.chuva.dados, met = d.metricas || {}, modo = d.modo || met.modo || (d.modelo && d.modelo.modo);
    if (d.prob == null) return cartao(n, id, tit, '<p class="t2">' + esc(d.texto || "Nenhuma fonte de previsão guardada para amanhã.") + "</p>" + opiniao);
    var poucos = modo === "placar" || modo === "media";
    var topo = '<p class="pau-grande"><span class="numero">' + pct(d.prob) + '</span> <span>de chance de chover 1 mm ou mais em</span> <strong>' + esc(diaMes(d.dia)) + "</strong>" + (poucos ? aprendendo() : "") + "</p>";
    var expl = d.explicacao ? '<p class="t2">' + esc(d.explicacao) + "</p>" : "";
    var vistas = {}, contrib = (d.contribuicoes || []).filter(function (c) { if (vistas[c.texto]) return false; vistas[c.texto] = 1; return true; }).slice(0, 3);
    var lista = contrib.length ? '<p class="pau-sub">O que mais pesou nesta previsão:</p><ul class="pau-lista">' + contrib.map(function (c) {
      return '<li><span>' + esc(c.texto) + '</span> <span class="t2">' + (c.efeito >= 0 ? "(aumentou a chance)" : "(diminuiu a chance)") + "</span></li>"; }).join("") + "</ul>" : "";
    var bm = met.brier_modelo, bp = met.brier_placar, selo;
    if (bm != null && bp != null) {
      selo = '<p><span class="selo ' + (bm < bp ? "ok" : "at") + '">Modelo × placar</span> <span class="pau-num">' + nf(bm, 3) + " × " + nf(bp, 3) + '</span> <span class="t2 pq">(Brier: quanto menor, melhor)</span></p>'
        + '<p class="t2 pq">' + (bm < bp ? "Nos dias de teste, o modelo errou menos que o placar das fontes." : "Nos dias de teste, o modelo ainda não superou o placar das fontes; por isso os dois aparecem.") + "</p>";
    } else if (bp != null) {
      selo = '<p><span class="selo in">Placar das fontes</span> <span class="pau-num">' + nf(bp, 3) + '</span> <span class="t2 pq">(Brier: quanto menor, melhor)</span></p>';
    } else selo = "";
    var placar = d.placar_prob != null ? '<p class="t2 pq"><span>Só o placar das fontes daria:</span> <strong>' + pct(d.placar_prob) + "</strong></p>" : "";
    var ver = d.modelo && d.modelo.treinado_em ? '<p class="t2 pq"><span>Treinado em</span> <span>' + dataHora(d.modelo.treinado_em) + "</span></p>" : "";
    return cartao(n, id, tit, topo + expl + lista + selo + placar + opiniao + ver);
  }

  /* ── 2. Sensores estranhos (anomalias) ── */
  function listaAnomalias() {
    if (R.anomalias.estado !== "ok") return [];
    return (R.anomalias.dados.anomalias || []).slice().sort(function (a, b) { return (a.nivel === "alarme" ? 0 : 1) - (b.nivel === "alarme" ? 0 : 1); })
      .map(function (a) { return { nivel: a.nivel === "alarme" ? "alarme" : "atencao", ativo: a.ativo, grandeza: a.grandeza, tipo: a.tipo,
        titulo: nomeAtivo(a.ativo) + " · " + (GRANDEZAS[a.grandeza] || a.grandeza), rotulo: TIPOS[a.tipo] || a.tipo, texto: a.texto || "", dias_ate_baixa: a.dias_ate_baixa }; });
  }
  function itemAnomalia(a) {
    return '<li><span class="selo ' + (a.nivel === "alarme" ? "al" : "at") + '">' + (a.nivel === "alarme" ? "Alarme" : "Atenção") + '</span> <strong><span>' + esc(nomeAtivo(a.ativo)) + "</span> · <span>" + esc(GRANDEZAS[a.grandeza] || a.grandeza) + "</span></strong> "
      + '<span class="t2">(<span>' + esc(a.rotulo) + '</span>)</span> <span class="pau-txt">' + esc(a.texto) + "</span></li>";
  }
  function cartaoAnomalias(n) {
    var id = "pau-h-anom", tit = "Sensores com leitura estranha";
    if (R.anomalias.estado !== "ok") return cartao(n, id, tit, semDados("anomalias"));
    var d = R.anomalias.dados, l = listaAnomalias();
    var corpo = '<p class="t2 pq"><span>Sensores acompanhados:</span> <strong>' + (d.sensores || 0) + "</strong></p>";
    corpo += l.length ? '<ul class="pau-lista pau-anom">' + l.map(itemAnomalia).join("") + "</ul>" : '<p class="faixa ok">Nenhum sensor estranho agora.</p>';
    var m = R.modelos.estado === "ok" ? (R.modelos.dados.modelos || []).filter(function (x) { return x.nome === "anomalias"; })[0] : null;
    if (m && m.explicacao) corpo += '<p class="t2 pq">' + esc(m.explicacao) + "</p>";
    else corpo += '<p class="t2 pq">Compara cada leitura com o normal recente do mesmo sensor: valor longe do normal, o mesmo número repetido muitas vezes (travado), mudança mais rápida do que a física permite e bateria caindo.</p>';
    return cartao(n, id, tit, corpo);
  }
  function resumoAnomalias() {
    var l = listaAnomalias(); if (!l.length) return "";
    return '<ul class="pau-lista pau-anom pau-resumo" aria-label="Sensores com leitura estranha">' + l.map(itemAnomalia).join("") + "</ul>";
  }

  /* ── 3. Consumo esperado × real ── */
  function grafico(m) {
    var dias = m.dias || [], Wd = 340, Hd = 170, topo = 18, baixo = 26, esq = 6, larg = (Wd - esq * 2) / Math.max(1, dias.length);
    var max = 0; dias.forEach(function (d) { max = Math.max(max, d.real || 0, (d.faixa || [])[1] || 0, d.esperado || 0); }); max = max * 1.1 || 1;
    var y = function (v) { return topo + (Hd - topo - baixo) * (1 - v / max); };
    var desp = dias.filter(function (d) { return d.desperdicio; }).map(function (d) { return diaMes(d.dia); });
    var rot = "Consumo real e faixa esperada, últimos " + dias.length + " dias. " + (desp.length ? "Possível desperdício em: " + desp.join(", ") + "." : "Nenhum dia acima do normal.");
    var g = dias.map(function (d, i) {
      var x0 = esq + i * larg, fx = d.faixa || [d.esperado, d.esperado], bw = larg * 0.42, bx = x0 + (larg - bw) / 2, r = d.real || 0;
      return '<rect class="pau-fx" x="' + (x0 + larg * 0.12).toFixed(1) + '" y="' + y(fx[1]).toFixed(1) + '" width="' + (larg * 0.76).toFixed(1) + '" height="' + Math.max(1, y(fx[0]) - y(fx[1])).toFixed(1) + '"/>'
        + '<rect class="' + (d.desperdicio ? "pau-desp" : "pau-real") + '" x="' + bx.toFixed(1) + '" y="' + y(r).toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + Math.max(0, y(0) - y(r)).toFixed(1) + '"/>'
        + '<line class="pau-esp" x1="' + (x0 + larg * 0.12).toFixed(1) + '" x2="' + (x0 + larg * 0.88).toFixed(1) + '" y1="' + y(d.esperado || 0).toFixed(1) + '" y2="' + y(d.esperado || 0).toFixed(1) + '"/>'
        + (d.desperdicio ? '<text class="pau-alerta" x="' + (x0 + larg / 2).toFixed(1) + '" y="' + Math.max(12, y(Math.max(r, fx[1])) - 4).toFixed(1) + '" text-anchor="middle">!</text>' : "")
        + '<text class="pau-eixo" x="' + (x0 + larg / 2).toFixed(1) + '" y="' + (Hd - 8) + '" text-anchor="middle">' + esc(diaMes(d.dia)) + "</text>";
    }).join("");
    return '<svg class="pau-graf" viewBox="0 0 ' + Wd + " " + Hd + '" role="img" aria-label="' + esc(rot) + '"><line class="pau-base" x1="0" x2="' + Wd + '" y1="' + y(0).toFixed(1) + '" y2="' + y(0).toFixed(1) + '"/>' + g + "</svg>"
      + '<ul class="pau-leg" aria-hidden="true"><li><i class="pau-real"></i><span>Real</span></li><li><i class="pau-fx"></i><span>Faixa esperada</span></li><li><i class="pau-esp"></i><span>Esperado</span></li><li><i class="pau-desp"></i><span>! Possível desperdício</span></li></ul>';
  }
  function tabela(m, idc) {
    var un = m.unidade || "", ene = m.grandeza === "energia";   /* energia: P, Q, S e FP do dia (regra: FP sempre na energia) */
    var linhas = (m.dias || []).map(function (d) {
      var fx = d.faixa || [], sit = d.desperdicio ? '<span class="selo al">! Possível desperdício</span>' : d.real != null && fx.length && d.real < fx[0] ? '<span class="selo in">Abaixo do normal</span>' : '<span class="selo ok">Dentro do normal</span>';
      return "<tr" + (d.desperdicio ? ' class="pau-linha-desp"' : "") + '><th scope="row">' + esc(diaMes(d.dia)) + "</th><td>" + nf(d.real, 1) + "</td><td>" + nf(d.esperado, 1) + "</td><td>" + nf(fx[0], 1) + " – " + nf(fx[1], 1) + "</td>"
        + (ene ? (function (p) { p = p || {}; return "<td>" + nf(p.q_kvarh, 1) + "</td><td>" + nf(p.s_kvah, 1) + "</td><td>" + nf(p.fp, 2) + "</td><td>" + esc(p.fp_fonte || "—") + "</td>"; })(d.potencias) : "")
        + "<td>" + sit + "</td></tr>";
    }).join("");
    return '<div class="rolagem"><table class="pau-tab"><caption id="' + idc + '">Consumo de cada dia, real e esperado <span>(' + esc(un) + ")</span></caption><thead><tr>"
      + '<th scope="col">Dia</th><th scope="col">Real</th><th scope="col">Esperado</th><th scope="col">Faixa normal</th>' + (ene ? '<th scope="col">Q (kvarh)</th><th scope="col">S (kVAh)</th><th scope="col">FP</th><th scope="col">De onde vem o FP</th>' : "") + '<th scope="col">Situação</th></tr></thead><tbody>' + linhas + "</tbody></table></div>";
  }
  function cartaoConsumo(n) {
    var id = "pau-h-cons", tit = "Consumo esperado × real";
    if (R.consumo.estado !== "ok") return cartao(n, id, tit, semDados("consumo"), "pau-largo");
    var ms = R.consumo.dados.medidores || [];
    if (!ms.length) return cartao(n, id, tit, '<p class="t2">Nenhum medidor de energia ou de água com leituras datadas ainda.</p>', "pau-largo");
    var corpo = ms.map(function (m, i) {
      var modo = modoModelo("consumo:" + m.ativo + "|" + m.grandeza), poucos = modo ? (modo === "media" || modo === "placar") : /média simples/.test(m.explicacao || "");
      var tipo = m.grandeza === "energia" ? "Energia" : m.grandeza === "vazao" ? "Água" : (GRANDEZAS[m.grandeza] || m.grandeza);
      var desp = (m.desperdicio || []).length;
      return '<div class="pau-med">' + titulo(sub(n), id + "-" + i, "<span>" + esc(tipo) + "</span> · <span>" + esc(nomeAtivo(m.ativo)) + "</span>" + (poucos ? aprendendo() : ""))
        + (m.explicacao ? '<p class="t2 pq">' + esc(m.explicacao) + "</p>" : "")
        + (desp ? '<p class="faixa al"><strong>!</strong> <span>Dias com possível desperdício:</span> <strong>' + (m.desperdicio || []).map(diaMes).join(", ") + "</strong></p>" : '<p class="faixa ok">Nenhum dia acima do normal nos últimos 7 dias.</p>')
        + grafico(m) + tabela(m, id + "-t" + i) + "</div>";
    }).join("");
    return cartao(n, id, tit, '<p class="t2 pq">Cada dia, o consumo real comparado ao que seria normal para aquele dia. Acima da faixa normal é marcado como possível desperdício: vale conferir vazamento, equipamento ligado à toa ou mudança de rotina.</p>' + corpo, "pau-largo");
  }

  /* ── 4. Quando irrigar ── */
  function cartaoIrrigacao(n) {
    var id = "pau-h-irr", tit = "Quando irrigar";
    if (R.irrigacao.estado !== "ok") return cartao(n, id, tit, semDados("irrigacao"));
    var d = R.irrigacao.dados, recs = d.recomendacoes || [];
    var topo = d.prob_chuva != null ? '<p class="t2 pq"><span>Chance de chuva amanhã usada na conta:</span> <strong>' + pct(d.prob_chuva) + "</strong></p>" : '<p class="t2 pq">Sem chance de chuva para amanhã: a conta usa só a secagem do solo.</p>';
    if (!recs.length) return cartao(n, id, tit, topo + '<p class="t2">Nenhum sensor de umidade do solo com leituras nas últimas 72 horas.</p>');
    var lista = '<ul class="pau-lista pau-irr">' + recs.map(function (r) {
      var a = ACOES[r.acao] || ["in", r.acao];
      return '<li><p><strong>' + esc(nomeAtivo(r.ativo)) + '</strong> <span class="selo ' + a[0] + '">' + esc(a[1]) + "</span></p>"
        + '<p class="pau-txt">' + esc(r.texto || "") + "</p>"
        + (r.quando ? '<p class="t2 pq"><span>Chega ao limite por volta de</span> <strong>' + dataHora(r.quando) + "</strong></p>" : "")
        + (r.limite != null ? '<p class="t2 pq"><span>Limite da válvula:</span> <span>' + nf(r.limite, 0) + "%</span></p>" : "")
        + (r.explicacao ? '<p class="t2 pq">' + esc(r.explicacao) + "</p>" : "") + "</li>";
    }).join("") + "</ul>";
    return cartao(n, id, tit, topo + lista + '<p class="t2 pq">É uma sugestão: se as folhas murcharem, irrigue.</p>');
  }

  /* ── 5. Receber estes avisos (assinatura; LGPD) ── */
  function preencherForm(forcar) {
    if (F && !forcar) return;
    var atv = [];
    try { var p = typeof cfg.perfil === "function" ? cfg.perfil() : null; atv = ((p && p.atividades) || []).filter(function (a) { return ATIVIDADES[a]; }); } catch (e) {}
    var regras = R.assinaturas.estado === "ok" ? Object.keys(R.assinaturas.dados.regras || {}) : [];
    if (R.assinaturas.estado !== "ok") return;        // espera as regras e a finalidade do servidor
    // o servidor também conhece as atividades aprendidas do perfil (GET /api/alertas/assinaturas → atividades_perfil):
    // já vêm marcadas, junto com as do perfil deste navegador
    (R.assinaturas.dados.atividades_perfil || []).forEach(function (a) { if (ATIVIDADES[a] && atv.indexOf(a) < 0) atv.push(a); });
    F = { id: null, nome: "", email: "", whatsapp: "", whatsapp_chave: "", canais: ["email"], alertas: regras, atividades: atv,
      nivel_min: "atencao", silencio_ini: "22:00", silencio_fim: "06:00", alerta_fura_silencio: true, consentimento: false };
  }
  function chk(lista, valor, rot, campo, idb) {
    var marcado = (F[campo] || []).indexOf(valor) >= 0;
    return '<label class="opc" for="' + idb + '"><input type="checkbox" id="' + idb + '" data-pau-lista="' + campo + '" value="' + esc(valor) + '"' + (marcado ? " checked" : "") + "><span>" + esc(rot) + "</span></label>";
  }
  function cartaoAvisos(n) {
    var id = "pau-h-av", tit = "Receber estes avisos";
    var r = R.assinaturas;
    if (r.estado === "sem_sessao") return cartao(n, id, tit, '<p class="t2">Entre com usuário e senha para assinar os avisos de clima por e-mail ou WhatsApp.</p>', "pau-largo");
    if (r.estado !== "ok") return cartao(n, id, tit, semDados("assinaturas"), "pau-largo");
    preencherForm(false);
    var d = r.dados, regras = d.regras || {}, ativs = (d.atividades || Object.keys(ATIVIDADES)), s = n === 3 ? 4 : 3;
    var msg = '<div id="pau-av-msg" role="status" tabindex="-1">' + (av.msg ? '<p class="faixa ' + (av.tipo === "erro" ? "al" : "ok") + '">' + esc(av.msg) + "</p>" : "") + "</div>";
    var intro = '<p class="t2">Os mesmos alertas desta tela, avisados por e-mail e, se você quiser, por WhatsApp. O computador central confere a previsão guardada a cada 15 minutos e manda o mesmo aviso no máximo uma vez por dia.</p>';
    var semWhats = d.whatsapp ? "" : '<p class="t2 pq">O envio por WhatsApp ainda não está ligado neste servidor: os avisos por WhatsApp ficam registrados como “não saiu” até a equipe Physis ligar. O e-mail funciona.</p>';
    var form = '<form class="pau-form" data-pau-form="avisos" novalidate>'
      + '<fieldset><legend>Como receber</legend>'
      + '<label class="opc" for="pau-c-email"><input type="checkbox" id="pau-c-email" data-pau-lista="canais" value="email"' + (F.canais.indexOf("email") >= 0 ? " checked" : "") + "><span>Receber por e-mail</span></label>"
      + '<div class="pau-campo"><label for="pau-email">E-mail</label><input type="email" id="pau-email" data-pau-campo="email" autocomplete="email" value="' + esc(F.email) + '"></div>'
      + '<label class="opc" for="pau-c-whats"><input type="checkbox" id="pau-c-whats" data-pau-lista="canais" value="whatsapp"' + (F.canais.indexOf("whatsapp") >= 0 ? " checked" : "") + "><span>Receber por WhatsApp (opcional)</span></label>"
      + '<div class="pau-duas"><div class="pau-campo"><label for="pau-whats">Número do WhatsApp, com DDD</label><input type="tel" id="pau-whats" data-pau-campo="whatsapp" autocomplete="tel" inputmode="tel" placeholder="(24) 99999-0000" value="' + esc(F.whatsapp) + '"></div>'
      + '<div class="pau-campo"><label for="pau-chave">Apikey do CallMeBot</label><input type="text" id="pau-chave" data-pau-campo="whatsapp_chave" autocomplete="off" spellcheck="false" value="' + esc(F.whatsapp_chave) + '" aria-describedby="pau-chave-dica"></div></div>'
      + '<p class="t2 pq" id="pau-chave-dica">' + (F.id ? "Deixe vazio para manter a apikey já guardada." : "Só para o WhatsApp.") + "</p>"
      + '<details><summary>Como ativar o WhatsApp (CallMeBot)</summary><div class="pau-det">'
      + '<p class="t2">O CallMeBot é um serviço de fora, de terceiros, e é opcional: o texto do aviso passa por ele (sem outros dados seus além do número). O e-mail funciona sem ele.</p>'
      + '<ol><li>No celular que vai receber, salve nos contatos o número do CallMeBot indicado na página do serviço <span class="t2">[MARCADOR: número e mensagem de ativação a confirmar pela equipe Physis]</span>.</li>'
      + "<li>Mande para esse contato, pelo WhatsApp, a mensagem de autorização que a página do serviço indica.</li>"
      + "<li>O CallMeBot responde com a sua apikey. Copie e cole no campo acima.</li>"
      + "<li>Para parar, use “Parar de receber” aqui embaixo: o número e a apikey são apagados.</li></ol></div></details>"
      + semWhats + "</fieldset>"
      + "<fieldset><legend>Para quais atividades</legend><p class=\"t2 pq\">Já vêm marcadas as atividades descritas no Início.</p><div class=\"pau-grade-opc\">"
      + ativs.map(function (a) { return chk("atividades", a, ATIVIDADES[a] || a, "atividades", "pau-a-" + a); }).join("") + "</div></fieldset>"
      + "<fieldset><legend>Quais alertas</legend><div class=\"pau-grade-opc\">"
      + Object.keys(regras).map(function (k) { return chk("alertas", k, regras[k], "alertas", "pau-r-" + k); }).join("") + "</div></fieldset>"
      + "<fieldset><legend>Nível e horário</legend>"
      + '<div role="radiogroup" aria-labelledby="pau-niv-rot"><p id="pau-niv-rot" class="pau-sub">Nível mínimo</p>'
      + '<label class="opc" for="pau-n-at"><input type="radio" name="pau-nivel" id="pau-n-at" data-pau-campo="nivel_min" value="atencao"' + (F.nivel_min !== "alerta" ? " checked" : "") + "><span>Atenção e alerta</span></label>"
      + '<label class="opc" for="pau-n-al"><input type="radio" name="pau-nivel" id="pau-n-al" data-pau-campo="nivel_min" value="alerta"' + (F.nivel_min === "alerta" ? " checked" : "") + "><span>Só alerta (os mais fortes)</span></label></div>"
      + '<div class="pau-duas"><div class="pau-campo"><label for="pau-s-ini">Silêncio a partir de</label><input type="time" id="pau-s-ini" data-pau-campo="silencio_ini" value="' + esc(F.silencio_ini) + '"></div>'
      + '<div class="pau-campo"><label for="pau-s-fim">Silêncio até</label><input type="time" id="pau-s-fim" data-pau-campo="silencio_fim" value="' + esc(F.silencio_fim) + '"></div></div>'
      + '<label class="opc" for="pau-fura"><input type="checkbox" id="pau-fura" data-pau-campo="alerta_fura_silencio"' + (F.alerta_fura_silencio ? " checked" : "") + "><span>Alerta forte chega mesmo no horário de silêncio</span></label>"
      + '<div class="pau-campo"><label for="pau-nome">Nome (opcional)</label><input type="text" id="pau-nome" data-pau-campo="nome" autocomplete="name" value="' + esc(F.nome) + '"></div></fieldset>'
      + '<div class="pau-final"><p class="pau-sub">Para que servem estes dados</p><p>' + esc(d.finalidade || "") + "</p>"
      + '<label class="opc" for="pau-consent"><input type="checkbox" id="pau-consent" data-pau-campo="consentimento" required aria-required="true"' + (F.consentimento ? " checked" : "") + "><span>Li a finalidade acima e aceito receber estes avisos. Posso sair quando quiser. (obrigatório)</span></label>"
      + '<div class="chips"><button type="submit" class="principal"' + (av.ocupado ? " disabled" : "") + ">" + (F.id ? "Salvar as mudanças" : "Assinar os avisos") + "</button>"
      + (F.id ? '<button type="button" data-pau-acao="novo">Cancelar a mudança</button>' : "") + "</div></div>"
      + "</form>";
    return cartao(n, id, tit, intro + msg + form + minhas(s) + historico(s), "pau-largo");
  }
  function minhas(s) {
    var l = R.assinaturas.dados.assinaturas || [];
    var corpo = l.length ? '<ul class="limpa pau-assin">' + l.map(function (a) {
      var canais = (a.canais || []).map(function (c) { return "<span>" + (c === "whatsapp" ? "WhatsApp" : "E-mail") + "</span>"; }).join(" + ");
      var conf = av.sair === a.id;
      return '<li><div class="pau-a-info"><strong>' + canais + "</strong> <span class=\"t2\">" + esc([a.email, a.whatsapp ? "+" + a.whatsapp : ""].filter(Boolean).join(" · ")) + "</span>"
        + ' <span class="t2 pq"><span>Alertas escolhidos:</span> <span>' + (a.alertas || []).length + "</span></span></div>"
        + (conf ? '<p class="faixa at" id="pau-sair-' + a.id + '" tabindex="-1">Parar de receber apaga seu e-mail, telefone e apikey deste aviso. O histórico fica 90 dias, sem telefone.</p><div class="chips"><button type="button" class="perigo" data-pau-acao="sair-sim" data-pau-id="' + a.id + '">Sim, parar de receber</button><button type="button" data-pau-acao="sair-nao">Cancelar</button></div>'
          : '<div class="chips"><button type="button" data-pau-acao="editar" data-pau-id="' + a.id + '">Alterar</button><button type="button" class="perigo" data-pau-acao="sair" data-pau-id="' + a.id + '">Parar de receber</button></div>')
        + "</li>"; }).join("") + "</ul>" : '<p class="t2">Você ainda não assinou os avisos.</p>';
    return '<div class="pau-bloco">' + titulo(s, "pau-h-minhas", "Suas assinaturas") + corpo + "</div>";
  }
  function historico(s) {
    var h = R.historico;
    var corpo;
    if (h.estado !== "ok") corpo = semDados("historico");
    else {
      var l = (h.dados.historico || []).slice(0, 20);
      corpo = l.length ? '<div class="rolagem"><table class="pau-tab"><caption>Últimos avisos enviados (guardados por 90 dias)</caption><thead><tr><th scope="col">Quando</th><th scope="col">Canal</th><th scope="col">Nível</th><th scope="col">Situação</th><th scope="col">Aviso</th></tr></thead><tbody>'
        + l.map(function (e) { return '<tr><th scope="row">' + dataHora(e.criado) + "</th><td>" + (e.canal === "whatsapp" ? "WhatsApp" : "E-mail") + '</td><td><span class="selo ' + (e.nivel === "alerta" ? "al" : "at") + '">' + (e.nivel === "alerta" ? "Alerta" : "Atenção") + "</span></td><td>"
          + esc(ESTADOS_ENVIO[e.estado] || e.estado) + "</td><td>" + esc(e.texto || "") + "</td></tr>"; }).join("") + "</tbody></table></div>"
        : '<p class="t2">Nenhum aviso enviado ainda.</p>';
    }
    return '<div class="pau-bloco">' + titulo(s, "pau-h-hist", "Avisos enviados") + corpo + "</div>";
  }

  function enviar() {
    if (!F || av.ocupado) return;
    var erro = "", campo = "";
    if (!F.consentimento) { erro = "Marque a caixa de consentimento para assinar."; campo = "pau-consent"; }
    else if (!F.canais.length) { erro = "Escolha e-mail, WhatsApp ou os dois."; campo = "pau-c-email"; }
    else if (F.canais.indexOf("email") >= 0 && !String(F.email).trim()) { erro = "Informe o e-mail."; campo = "pau-email"; }
    else if (F.canais.indexOf("whatsapp") >= 0 && !String(F.whatsapp).trim()) { erro = "Informe o número do WhatsApp."; campo = "pau-whats"; }
    if (erro) { av.msg = erro; av.tipo = "erro"; redesenhar(campo); anunciar(erro); return; }
    var corpo = { consentimento: true, nome: F.nome, email: String(F.email).trim(), whatsapp: F.whatsapp, whatsapp_chave: F.whatsapp_chave, canais: F.canais.slice(),
      alertas: F.alertas.slice(), atividades: F.atividades.slice(), nivel_min: F.nivel_min, silencio_ini: F.silencio_ini, silencio_fim: F.silencio_fim,
      alerta_fura_silencio: !!F.alerta_fura_silencio };
    if (F.id) corpo.id = F.id;
    postar(corpo, F.id ? "Pronto: assinatura alterada." : "Pronto: assinatura feita. Os avisos chegam pelos canais escolhidos.", true);
  }
  function postar(corpo, ok, limpar) {
    var fx = f(); if (!fx) return;
    av.ocupado = true; av.msg = "Enviando…"; av.tipo = ""; redesenhar();
    Promise.resolve().then(function () { return fx(ROTAS.assinaturas, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "same-origin", body: JSON.stringify(corpo) }); })
      .then(function (r) { return r.json().catch(function () { return { ok: false, erro: "HTTP " + r.status }; }); })
      .then(function (j) {
        av.ocupado = false;
        if (j && j.ok) { av.msg = ok; av.tipo = "ok"; av.sair = null; if (limpar) { F = null; } }
        else { av.msg = "Não salvou: " + ((j && j.erro) || "erro"); av.tipo = "erro"; }
      }, function () { av.ocupado = false; av.msg = "O computador central não respondeu."; av.tipo = "erro"; })
      .then(function () { anunciar(av.msg); return carregar(true); })
      .then(function () { if (!F) preencherForm(false); redesenhar("pau-av-msg"); });
  }
  function redesenhar(foco) {
    assinaturaDados = "";
    if (typeof cfg.aoMudar === "function") { try { cfg.aoMudar(); } catch (e) {} }
    if (foco && doc) { var x = doc.getElementById(foco); if (x) try { x.focus(); } catch (e) {} }
  }

  /* ── eventos (uma vez, no document) ── */
  function ligarEventos() {
    if (ligados || !doc) return; ligados = true;
    var guardar = function (ev) {
      var t = ev.target; if (!t || !t.getAttribute || !F) return;
      var lista = t.getAttribute("data-pau-lista"), campo = t.getAttribute("data-pau-campo");
      if (lista && Array.isArray(F[lista])) { var i = F[lista].indexOf(t.value); if (t.checked && i < 0) F[lista].push(t.value); if (!t.checked && i >= 0) F[lista].splice(i, 1); return; }
      if (!campo) return;
      if (t.type === "checkbox") F[campo] = !!t.checked; else if (t.type === "radio") { if (t.checked) F[campo] = t.value; } else F[campo] = t.value;
    };
    doc.addEventListener("input", guardar); doc.addEventListener("change", guardar);
    doc.addEventListener("submit", function (ev) { var fm = ev.target; if (!fm || !fm.getAttribute || fm.getAttribute("data-pau-form") !== "avisos") return; ev.preventDefault(); enviar(); });
    doc.addEventListener("click", function (ev) {
      var b = ev.target.closest && ev.target.closest("[data-pau-acao]"); if (!b) return;
      var acao = b.getAttribute("data-pau-acao"), ident = +b.getAttribute("data-pau-id") || null;
      if (acao === "sair") { av.sair = ident; av.msg = ""; redesenhar("pau-sair-" + ident); return; }
      if (acao === "sair-nao") { var antes = av.sair; av.sair = null; redesenhar(null); var bt = doc.querySelector('[data-pau-acao="sair"][data-pau-id="' + antes + '"]'); if (bt) bt.focus(); return; }
      if (acao === "sair-sim") { postar({ acao: "sair", id: ident }, "Pronto: você não recebe mais estes avisos. E-mail, telefone e apikey foram apagados.", false); return; }
      if (acao === "editar") {
        var a = ((R.assinaturas.dados || {}).assinaturas || []).filter(function (x) { return x.id === ident; })[0]; if (!a) return;
        F = { id: a.id, nome: a.nome || "", email: a.email || "", whatsapp: a.whatsapp || "", whatsapp_chave: "", canais: (a.canais || []).slice(), alertas: (a.alertas || []).slice(),
          atividades: (a.atividades || []).slice(), nivel_min: a.nivel_min || "atencao", silencio_ini: a.silencio_ini || "22:00", silencio_fim: a.silencio_fim || "06:00",
          alerta_fura_silencio: a.alerta_fura_silencio !== 0 && a.alerta_fura_silencio !== false, consentimento: false };
        av.msg = "Alterando a assinatura. Confira, marque o consentimento e salve."; av.tipo = "ok"; redesenhar("pau-email"); return;
      }
      if (acao === "novo") { F = null; preencherForm(false); av.msg = ""; redesenhar("pau-email"); }
    });
  }

  /* ── tudo junto, para Resiliência climática ── */
  function secaoResiliencia(n) {
    n = n === 3 ? 3 : 2; var c = n + 1;
    var aviso = estado().geral === "sem_servidor" ? '<p class="faixa in">Estas análises precisam do computador central (hub) deste lugar, que aprende com os dados guardados nele. Aberta sem ele (arquivo direto ou demonstração), esta parte fica vazia: nenhum número é inventado.</p>' : "";
    return '<section class="pau-secao" aria-labelledby="pau-h-sec">' + titulo(n, "pau-h-sec", "O que o hub aprendeu com este lugar")
      + '<p class="t2 apoio">O computador central aprende com os dados guardados aqui, sem internet, e treina de novo todo dia às 3 h. Cada número vem com a explicação de como foi calculado. É mais uma opinião: confira sempre a previsão das fontes e o que você vê no campo.</p>'
      + aviso + '<div class="grade pau-grade">' + cartaoChuva(c) + cartaoAnomalias(c) + cartaoIrrigacao(c) + "</div>" + cartaoConsumo(c) + cartaoAvisos(c) + "</section>";
  }

  var CSS = ".pau-secao{display:flex;flex-direction:column;gap:14px;min-width:0}.pau-cartao{min-width:0}.pau-cartao>*{max-width:100%}"
    + ".pau-grande .numero{margin-right:6px}.pau-sub{font-weight:600;margin:4px 0 0}"
    + ".pau-lista{margin:0;padding-left:1.2em;display:flex;flex-direction:column;gap:8px}.pau-lista li{overflow-wrap:anywhere}"
    + ".pau-anom,.pau-irr{list-style:none;padding-left:0}.pau-anom li,.pau-irr li{border-top:1px solid var(--trilho,#EFE8D6);padding-top:8px;display:flex;flex-wrap:wrap;gap:4px 8px;align-items:baseline}"
    + ".pau-irr li{flex-direction:column;flex-wrap:nowrap;align-items:stretch}.pau-cartao p,.pau-cartao li{overflow-wrap:anywhere}.pau-txt{flex-basis:100%}"
    + ".pau-num{font-family:var(--numero,inherit);font-weight:600}"
    + ".pau-med{display:flex;flex-direction:column;gap:8px;padding-top:10px;border-top:1px solid var(--trilho,#EFE8D6)}"
    + ".pau-graf{display:block;width:100%;max-width:560px;height:auto}"
    + ".pau-graf .pau-fx{fill:var(--trilho,#EFE8D6)}.pau-graf .pau-real{fill:var(--acao,#1A4D2E)}.pau-graf .pau-desp{fill:var(--al-t,#7A2214)}"
    + ".pau-graf .pau-esp{stroke:var(--tinta,#1B1F23);stroke-width:2;stroke-dasharray:4 3}.pau-graf .pau-base{stroke:var(--linha,#D9D3C2)}"
    + ".pau-graf text{font-size:12px;fill:var(--tinta2,#4A4F44);font-family:var(--fonte,system-ui,sans-serif)}.pau-graf .pau-alerta{font-size:15px;font-weight:700;fill:var(--al-t,#7A2214)}"
    + ".pau-leg{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:6px 14px;font-size:.9em}.pau-leg li{display:flex;align-items:center;gap:6px}"
    + ".pau-leg i{display:inline-block;width:14px;height:14px;border-radius:3px}.pau-leg i.pau-real{background:var(--acao,#1A4D2E)}.pau-leg i.pau-fx{background:var(--trilho,#EFE8D6);border:1px solid var(--linha,#D9D3C2)}"
    + ".pau-leg i.pau-esp{height:0;border-top:2px dashed var(--tinta,#1B1F23);border-radius:0}.pau-leg i.pau-desp{background:var(--al-t,#7A2214)}"
    + "table.pau-tab{min-width:0;width:100%}.pau-tab caption{text-align:left;font-weight:600;padding-bottom:6px}.pau-tab td,.pau-tab th{overflow-wrap:anywhere}"
    + "tr.pau-linha-desp{background:var(--al-f,#F5E2D7)}tr.pau-linha-desp th,tr.pau-linha-desp td{color:var(--al-t,#7A2214);font-weight:600}"
    + ".pau-form{display:flex;flex-direction:column;gap:12px}.pau-form fieldset{gap:8px}.pau-form legend{font-size:1.05em}"
    + ".pau-campo{display:flex;flex-direction:column;gap:4px;min-width:0}.pau-campo input{width:100%}"
    + ".pau-form input[type=email],.pau-form input[type=tel]{font:inherit;min-height:44px;padding:8px 12px;border:1px solid #8A8270;border-radius:8px;background:var(--sup,#FFFFFF);color:var(--tinta,#1B1F23);max-width:100%}"
    + ".pau-duas{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(220px,100%),1fr));gap:10px}"
    + ".pau-grade-opc{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(220px,100%),1fr));gap:0 14px}"
    + ".pau-det{display:flex;flex-direction:column;gap:8px;padding:4px 0 8px}.pau-det ol{margin:0;padding-left:1.3em;display:flex;flex-direction:column;gap:6px}"
    + ".pau-final{display:flex;flex-direction:column;gap:8px;border:2px solid var(--acao,#1A4D2E);border-radius:12px;padding:14px}"
    + ".pau-bloco{display:flex;flex-direction:column;gap:8px;margin-top:8px}.pau-assin li{flex-direction:column;align-items:stretch}.pau-a-info{display:flex;flex-wrap:wrap;gap:4px 10px;overflow-wrap:anywhere}"
    + "#pau-av-msg:focus{outline:3px solid var(--acao,#1A4D2E);outline-offset:2px}";
  function estilo() { if (!doc || !doc.head || doc.getElementById("pau-estilo")) return; var e = doc.createElement("style"); e.id = "pau-estilo"; e.textContent = CSS; doc.head.appendChild(e); }

  var I18N = {
    "Previsão deste lugar (aprendida)": "This place's forecast (learned)",
    "O modelo é mais uma opinião: confira sempre a previsão das fontes (INMET, CEMADEN e Open-Meteo) nos próximos dias.": "The model is one more opinion: always check the sources' forecast (INMET, CEMADEN and Open-Meteo) for the next days.",
    "Nenhuma fonte de previsão guardada para amanhã.": "No forecast source stored for tomorrow.",
    "de chance de chover 1 mm ou mais em": "chance of 1 mm of rain or more on",
    "aprendendo (poucos dados)": "learning (little data)",
    "O que mais pesou nesta previsão:": "What weighed most in this forecast:",
    "(aumentou a chance)": "(raised the chance)",
    "(diminuiu a chance)": "(lowered the chance)",
    "Modelo × placar": "Model × scoreboard",
    "(Brier: quanto menor, melhor)": "(Brier: lower is better)",
    "Nos dias de teste, o modelo errou menos que o placar das fontes.": "On the test days, the model erred less than the sources' scoreboard.",
    "Nos dias de teste, o modelo ainda não superou o placar das fontes; por isso os dois aparecem.": "On the test days, the model has not yet beaten the sources' scoreboard; that is why both are shown.",
    "Placar das fontes": "Sources' scoreboard",
    "Só o placar das fontes daria:": "The sources' scoreboard alone would give:",
    "Treinado em": "Trained on",
    "o que o Open-Meteo previu": "what Open-Meteo forecast",
    "o que o INMET previu": "what INMET forecast",
    "o que o receptor previu": "what the receiver forecast",
    "os milímetros previstos pelo Open-Meteo": "the millimetres forecast by Open-Meteo",
    "a época do ano": "the time of year",
    "a chuva medida no dia anterior à previsão": "the rain measured the day before the forecast",
    "a chuva medida nos 3 dias anteriores": "the rain measured in the previous 3 days",
    "Carregando…": "Loading…",
    "Precisa do computador central (hub) deste lugar, que aprende com os dados guardados nele. Sem ele, este cartão fica vazio: nenhum número é inventado.": "Needs this place's central computer (hub), which learns from the data stored in it. Without it, this card stays empty: no number is made up.",
    "Entre com usuário e senha para ver.": "Sign in with user and password to see it.",
    "O computador central não entregou estes dados agora.": "The central computer did not deliver this data now.",
    "Tenta de novo em 1 minuto.": "It tries again in 1 minute.",
    "Sensores com leitura estranha": "Sensors with odd readings",
    "Sensores acompanhados:": "Sensors monitored:",
    "Nenhum sensor estranho agora.": "No odd sensor right now.",
    "Compara cada leitura com o normal recente do mesmo sensor: valor longe do normal, o mesmo número repetido muitas vezes (travado), mudança mais rápida do que a física permite e bateria caindo.": "Compares each reading with the same sensor's recent normal: value far from normal, the same number repeated many times (stuck), change faster than physics allows and a falling battery.",
    "Alarme": "Alarm",
    "Atenção": "Attention",
    "Alerta": "Alert",
    "Fora do normal": "Out of the normal",
    "Salto impossível": "Impossible jump",
    "Sensor travado": "Stuck sensor",
    "Bateria acabando": "Battery running out",
    "Umidade do solo": "Soil moisture",
    "Temperatura": "Temperature",
    "Umidade do ar": "Air humidity",
    "Bateria": "Battery",
    "Sinal do rádio (RSSI)": "Radio signal (RSSI)",
    "Sinal do rádio (SNR)": "Radio signal (SNR)",
    "Nível": "Level",
    "Energia": "Energy",
    "Tensão": "Voltage",
    "Corrente": "Current",
    "Vazão": "Flow",
    "Pressão": "Pressure",
    "Fator de potência": "Power factor",
    "Água": "Water",
    "Consumo esperado × real": "Expected × actual consumption",
    "Nenhum medidor de energia ou de água com leituras datadas ainda.": "No energy or water meter with dated readings yet.",
    "Dias com possível desperdício:": "Days with possible waste:",
    "Nenhum dia acima do normal nos últimos 7 dias.": "No day above normal in the last 7 days.",
    "Cada dia, o consumo real comparado ao que seria normal para aquele dia. Acima da faixa normal é marcado como possível desperdício: vale conferir vazamento, equipamento ligado à toa ou mudança de rotina.": "Each day, actual consumption compared with what would be normal for that day. Above the normal range is marked as possible waste: check for leaks, equipment left on or a change of routine.",
    "Real": "Actual",
    "Faixa esperada": "Expected range",
    "Esperado": "Expected",
    "! Possível desperdício": "! Possible waste",
    "Abaixo do normal": "Below normal",
    "Dentro do normal": "Within normal",
    "Consumo de cada dia, real e esperado": "Consumption of each day, actual and expected",
    "(kWh/dia)": "(kWh/day)",
    "(m³/dia)": "(m³/day)",
    "Dia": "Day",
    "Faixa normal": "Normal range",
    "Situação": "Status",
    "Quando irrigar": "When to irrigate",
    "Chance de chuva amanhã usada na conta:": "Chance of rain tomorrow used in the calculation:",
    "Sem chance de chuva para amanhã: a conta usa só a secagem do solo.": "No chance of rain for tomorrow: the calculation uses only how the soil dries.",
    "Nenhum sensor de umidade do solo com leituras nas últimas 72 horas.": "No soil moisture sensor with readings in the last 72 hours.",
    "Irrigar agora": "Irrigate now",
    "Programar a rega": "Schedule irrigation",
    "Aguardar a chuva": "Wait for the rain",
    "Não precisa irrigar": "No need to irrigate",
    "Sem dados suficientes": "Not enough data",
    "Chega ao limite por volta de": "Reaches the limit around",
    "Limite da válvula:": "Valve limit:",
    "É uma sugestão: se as folhas murcharem, irrigue.": "It is a suggestion: if the leaves wilt, irrigate.",
    "Receber estes avisos": "Receive these alerts",
    "Entre com usuário e senha para assinar os avisos de clima por e-mail ou WhatsApp.": "Sign in with user and password to subscribe to the weather alerts by e-mail or WhatsApp.",
    "Os mesmos alertas desta tela, avisados por e-mail e, se você quiser, por WhatsApp. O computador central confere a previsão guardada a cada 15 minutos e manda o mesmo aviso no máximo uma vez por dia.": "The same alerts as on this screen, sent by e-mail and, if you wish, by WhatsApp. The central computer checks the stored forecast every 15 minutes and sends the same alert at most once a day.",
    "O envio por WhatsApp ainda não está ligado neste servidor: os avisos por WhatsApp ficam registrados como “não saiu” até a equipe Physis ligar. O e-mail funciona.": "Sending by WhatsApp is not yet turned on in this server: WhatsApp alerts are logged as “not sent” until the Physis team turns it on. E-mail works.",
    "Como receber": "How to receive",
    "E-mail": "E-mail",
    "Receber por e-mail": "Receive by e-mail",
    "Receber por WhatsApp (opcional)": "Receive by WhatsApp (optional)",
    "WhatsApp": "WhatsApp",
    "Número do WhatsApp, com DDD": "WhatsApp number, with area code",
    "Apikey do CallMeBot": "CallMeBot apikey",
    "Deixe vazio para manter a apikey já guardada.": "Leave empty to keep the apikey already stored.",
    "Só para o WhatsApp.": "Only for WhatsApp.",
    "Como ativar o WhatsApp (CallMeBot)": "How to turn on WhatsApp (CallMeBot)",
    "O CallMeBot é um serviço de fora, de terceiros, e é opcional: o texto do aviso passa por ele (sem outros dados seus além do número). O e-mail funciona sem ele.": "CallMeBot is an outside, third-party service, and it is optional: the alert text goes through it (with no other data of yours besides the number). E-mail works without it.",
    "No celular que vai receber, salve nos contatos o número do CallMeBot indicado na página do serviço": "On the phone that will receive, save in your contacts the CallMeBot number shown on the service's page",
    "[MARCADOR: número e mensagem de ativação a confirmar pela equipe Physis]": "[PLACEHOLDER: activation number and message to be confirmed by the Physis team]",
    "Mande para esse contato, pelo WhatsApp, a mensagem de autorização que a página do serviço indica.": "Send that contact, by WhatsApp, the authorization message the service's page indicates.",
    "O CallMeBot responde com a sua apikey. Copie e cole no campo acima.": "CallMeBot answers with your apikey. Copy and paste it in the field above.",
    "Para parar, use “Parar de receber” aqui embaixo: o número e a apikey são apagados.": "To stop, use “Stop receiving” below: the number and the apikey are erased.",
    "Para quais atividades": "For which activities",
    "Já vêm marcadas as atividades descritas no Início.": "The activities described on the Home tab come already checked.",
    "Quais alertas": "Which alerts",
    "Nível e horário": "Level and time",
    "Nível mínimo": "Minimum level",
    "Atenção e alerta": "Attention and alert",
    "Só alerta (os mais fortes)": "Alert only (the strongest)",
    "Silêncio a partir de": "Quiet from",
    "Silêncio até": "Quiet until",
    "Alerta forte chega mesmo no horário de silêncio": "A strong alert arrives even during quiet hours",
    "Nome (opcional)": "Name (optional)",
    "Para que servem estes dados": "What this data is for",
    "Li a finalidade acima e aceito receber estes avisos. Posso sair quando quiser. (obrigatório)": "I read the purpose above and agree to receive these alerts. I can leave whenever I want. (required)",
    "Salvar as mudanças": "Save the changes",
    "Assinar os avisos": "Subscribe to the alerts",
    "Cancelar a mudança": "Cancel the change",
    "Suas assinaturas": "Your subscriptions",
    "Alertas escolhidos:": "Alerts chosen:",
    "Parar de receber apaga seu e-mail, telefone e apikey deste aviso. O histórico fica 90 dias, sem telefone.": "Stopping erases your e-mail, phone and apikey from this alert. The history stays for 90 days, without the phone.",
    "Sim, parar de receber": "Yes, stop receiving",
    "Cancelar": "Cancel",
    "Alterar": "Change",
    "Parar de receber": "Stop receiving",
    "Você ainda não assinou os avisos.": "You have not subscribed to the alerts yet.",
    "Últimos avisos enviados (guardados por 90 dias)": "Latest alerts sent (kept for 90 days)",
    "Quando": "When",
    "Canal": "Channel",
    "Aviso": "Alert",
    "Na fila do e-mail": "In the e-mail queue",
    "Enviado": "Sent",
    "Não saiu": "Not sent",
    "Nenhum aviso enviado ainda.": "No alert sent yet.",
    "Avisos enviados": "Alerts sent",
    "Marque a caixa de consentimento para assinar.": "Check the consent box to subscribe.",
    "Escolha e-mail, WhatsApp ou os dois.": "Choose e-mail, WhatsApp or both.",
    "Informe o e-mail.": "Enter the e-mail.",
    "Informe o número do WhatsApp.": "Enter the WhatsApp number.",
    "Pronto: assinatura alterada.": "Done: subscription changed.",
    "Pronto: assinatura feita. Os avisos chegam pelos canais escolhidos.": "Done: subscribed. The alerts arrive through the chosen channels.",
    "Pronto: você não recebe mais estes avisos. E-mail, telefone e apikey foram apagados.": "Done: you no longer receive these alerts. E-mail, phone and apikey were erased.",
    "Enviando…": "Sending…",
    "O computador central não respondeu.": "The central computer did not answer.",
    "Alterando a assinatura. Confira, marque o consentimento e salve.": "Changing the subscription. Check it, tick the consent and save.",
    "O que o hub aprendeu com este lugar": "What the hub learned about this place",
    "O computador central aprende com os dados guardados aqui, sem internet, e treina de novo todo dia às 3 h. Cada número vem com a explicação de como foi calculado. É mais uma opinião: confira sempre a previsão das fontes e o que você vê no campo.": "The central computer learns from the data stored here, without internet, and retrains every day at 3 a.m. Each number comes with the explanation of how it was calculated. It is one more opinion: always check the sources' forecast and what you see in the field.",
    "Estas análises precisam do computador central (hub) deste lugar, que aprende com os dados guardados nele. Aberta sem ele (arquivo direto ou demonstração), esta parte fica vazia: nenhum número é inventado.": "These analyses need this place's central computer (hub), which learns from the data stored in it. Opened without it (file or demo), this part stays empty: no number is made up.",
    // textos que vêm prontos do servidor (alertas_clima.py: REGRAS, FINALIDADE e erros da assinatura)
    "Geada no café": "Frost on coffee",
    "Chuva na colheita": "Rain at harvest",
    "Calor no rebanho": "Heat on the herd",
    "Chuva prevista: adiar a rega": "Rain forecast: postpone irrigation",
    "Chuva provável amanhã (modelo do lugar)": "Rain likely tomorrow (local model)",
    "Horta e viveiro": "Vegetable garden and nursery",
    "Chuva forte para hóspedes": "Heavy rain for guests",
    "Chuva acumulada e encostas": "Accumulated rain and slopes",
    "Café": "Coffee",
    "Grãos": "Grains",
    "Gado": "Cattle",
    "Gado de leite": "Dairy cattle",
    "Irrigação": "Irrigation",
    "Hortifrúti": "Fruit and vegetables",
    "Hospedagem": "Lodging",
    "Enviar avisos de clima (geada, chuva forte, calor, deslizamento) para o lugar monitorado pela plataforma Physis, pelos canais escolhidos. Você pode sair quando quiser.": "Send weather alerts (frost, heavy rain, heat, landslide) for the place monitored by the Physis platform, through the chosen channels. You can leave whenever you want.",
    "é preciso aceitar receber os avisos (consentimento)": "you need to agree to receive the alerts (consent)",
    "e-mail inválido": "invalid e-mail",
    "escolha e-mail e/ou WhatsApp": "choose e-mail and/or WhatsApp",
    "informe o e-mail": "enter the e-mail",
    "informe o WhatsApp": "enter the WhatsApp number",
    "WhatsApp com DDD, ex.: (24) 99999-0000": "WhatsApp with area code, e.g. (24) 99999-0000",
    "nível mínimo: atencao ou alerta": "minimum level: atencao or alerta",
    "horário de silêncio no formato HH:MM": "quiet hours in the HH:MM format",
    "assinatura não encontrada": "subscription not found",
    "só quem assinou (ou a direção) pode mudar": "only the subscriber (or management) can change it",
    "só quem assinou (ou a direção) pode cancelar": "only the subscriber (or management) can cancel it",
    "Sem leituras suficientes desde a última rega para medir a velocidade de secagem do solo.": "Not enough readings since the last irrigation to measure how fast the soil dries.",
    "desconhecida": "unknown",
    "e a temperatura do dia": " and the day's temperature",
    "e a produção/ocupação da Gestão": " and the production/occupancy from Management",
    "e a temperatura do dia e a produção/ocupação da Gestão": " and the day's temperature and the production/occupancy from Management"
  };
  var I18N_RX = [
    ["^Nó (\\d+)$", "Node $1"],
    ["^Nó (\\d+) · zona ([AB])$", "Node $1 · zone $2"],
    ["^Não salvou: (.+)$", "Not saved: $1"],
    ["^Consumo real e faixa esperada, últimos (\\d+) dias\\. Possível desperdício em: (.+)\\.$", "Actual consumption and expected range, last $1 days. Possible waste on: $2."],
    ["^Consumo real e faixa esperada, últimos (\\d+) dias\\. Nenhum dia acima do normal\\.$", "Actual consumption and expected range, last $1 days. No day above normal."],
    // textos prontos do servidor (aprendizado.py), traduzidos pela forma
    ["^valor (\\S+) longe do normal recente \\(mediana (\\S+); z robusto (\\S+)\\)$", "value $1 far from the recent normal (median $2; robust z $3)"],
    ["^pulou de (\\S+) para (\\S+) em (\\d+) min \\(limite físico (\\S+) por minuto\\)$", "jumped from $1 to $2 in $3 min (physical limit $4 per minute)"],
    ["^o mesmo valor \\((\\S+)\\) nas últimas (\\d+) leituras: sensor travado ou desligado$", "the same value ($1) in the last $2 readings: sensor stuck or off"],
    ["^a bateria cai (\\S+) V por dia: chega a (\\S+) V em cerca de (\\d+) dia\\(s\\)$", "the battery drops $1 V per day: it reaches $2 V in about $3 day(s)"],
    ["^Irrigue agora: a umidade está em (\\d+)%, no limite de (\\d+)% ou abaixo, e a chance de chuva amanhã é (\\S+)\\.$", "Irrigate now: moisture is at $1%, at or below the $2% limit, and the chance of rain tomorrow is $3."],
    ["^O solo chegou ao limite \\((\\d+)% ≤ (\\d+)%\\), mas a chance de chover amanhã é (\\S+)\\. Se a planta aguenta algumas horas, vale esperar a chuva; se as folhas murcharem, irrigue\\.$", "The soil reached the limit ($1% ≤ $2%), but the chance of rain tomorrow is $3. If the plant can wait a few hours, wait for the rain; if the leaves wilt, irrigate."],
    ["^O solo está em (\\d+)% e quase não está secando agora\\. Não precisa irrigar por enquanto\\.$", "The soil is at $1% and is barely drying now. No need to irrigate for now."],
    ["^Ainda não há leituras suficientes de umidade do solo \\(precisa de pelo menos 1 hora de secagem\\)\\.$", "There are not enough soil moisture readings yet (at least 1 hour of drying is needed)."],
    ["^O solo perde cerca de (\\S+) ponto\\(s\\) de umidade por hora e está em (\\d+)%\\. Chega ao limite de (\\d+)% por volta de (\\d\\d/\\d\\d) às (\\d\\d:\\d\\d)\\. Programe a próxima rega para perto desse horário \\(chance de chuva amanhã: (\\S+)\\)\\.$", "The soil loses about $1 moisture point(s) per hour and is at $2%. It reaches the $3% limit around $4 at $5. Schedule the next irrigation close to that time (chance of rain tomorrow: $6)."],
    ["^O solo perde cerca de (\\S+) ponto\\(s\\) de umidade por hora e está em (\\d+)%\\. Chega ao limite de (\\d+)% por volta de (\\d\\d/\\d\\d) às (\\d\\d:\\d\\d)\\. Como a chance de chuva amanhã é (\\S+), a sugestão é não irrigar antes e conferir de novo depois da chuva\\.$", "The soil loses about $1 moisture point(s) per hour and is at $2%. It reaches the $3% limit around $4 at $5. As the chance of rain tomorrow is $6, the suggestion is not to irrigate before and to check again after the rain."],
    // explicações prontas do servidor (aprendizado.py: explicar_*)
    ["^Ainda há poucos dias com chuva medida \\((\\d+)\\)\\. Por enquanto a chance de chuva é a média do que cada fonte disse, com mais peso para a fonte que mais acertou aqui\\. O modelo próprio começa com (\\d+) dias\\.$", "There are still few days with measured rain ($1). For now the chance of rain is the average of what each source said, with more weight for the source that was right most often here. The model itself starts with $2 days."],
    ["^Aprendeu com (\\d+) dias deste lugar em que a chuva foi medida\\. O que mais pesa: ([^,]+), ([^,]+), ([^,]+)\\. Nos dias de teste ele errou menos que o placar das fontes \\(Brier (\\S+) × (\\S+); quanto menor, melhor\\)\\. Acertou (\\d+)% dos dias de teste\\.$", "Learned from $1 days of this place with measured rain. What weighs most: $2, $3, $4. On the test days it erred less than the sources' scoreboard (Brier $5 × $6; lower is better). It was right on $7% of the test days."],
    ["^Aprendeu com (\\d+) dias deste lugar em que a chuva foi medida\\. O que mais pesa: ([^,]+), ([^,]+), ([^,]+)\\. Nos dias de teste ele ainda não superou o placar das fontes; a tela mostra os dois \\(Brier (\\S+) × (\\S+); quanto menor, melhor\\)\\. Acertou (\\d+)% dos dias de teste\\.$", "Learned from $1 days of this place with measured rain. What weighs most: $2, $3, $4. On the test days it has not yet beaten the sources' scoreboard; the screen shows both (Brier $5 × $6; lower is better). It was right on $7% of the test days."],
    ["^Aprendeu com (\\d+) dias deste lugar em que a chuva foi medida\\. O que mais pesa: ([^,]+), ([^,]+), ([^,]+)\\. Acertou (\\d+)% dos dias de teste\\.$", "Learned from $1 days of this place with measured rain. What weighs most: $2, $3, $4. It was right on $5% of the test days."],
    ["^Acompanha (\\d+) sensores\\. Para cada um, guarda o valor típico \\(mediana\\) e a variação típica \\(MAD\\) das últimas leituras\\. Estranha um valor quando ele fica a mais de (\\S+) 'réguas' do típico, quando o sensor repete o mesmo número (\\d+) vezes seguidas \\(travado\\) ou quando muda mais rápido do que a física permite\\. Nas baterias, uma reta da tensão pelo tempo estima em quantos dias ela fica baixa \\((\\d+) de (\\d+) em aviso\\)\\.$", "Monitors $1 sensors. For each one, it keeps the typical value (median) and the typical spread (MAD) of the latest readings. It flags a value when it is more than $2 'rulers' from typical, when the sensor repeats the same number $3 times in a row (stuck) or when it changes faster than physics allows. For batteries, a line of voltage over time estimates in how many days it gets low ($4 of $5 under warning)."],
    ["^Desde a última rega ou chuva, o solo perde (\\S+) ponto\\(s\\) de umidade por hora \\(reta ajustada a (\\d+) leituras, r² (\\S+)\\)\\. Com isso e a chance de chuva, o sistema calcula quando a umidade chega ao limite da válvula\\.$", "Since the last irrigation or rain, the soil loses $1 moisture point(s) per hour (line fitted to $2 readings, r² $3). With that and the chance of rain, the system calculates when moisture reaches the valve limit."],
    ["^Com (\\d+) dias, o esperado é a média simples\\. A regressão começa com (\\d+) dias\\.$", "With $1 days, the expected value is the simple average. The regression starts with $2 days."],
    ["^Aprendeu com (\\d+) dias o consumo normal levando em conta o mês, o fim de semana(.*?)\\. Explica (\\d+)% da variação; o erro típico é (\\S+)\\. Um dia acima do esperado \\+ 2 erros típicos é marcado como possível desperdício\\.$", "Learned from $1 days the normal consumption taking into account the month, the weekend$2. It explains $3% of the variation; the typical error is $4. A day above expected + 2 typical errors is marked as possible waste."],
    // avisos prontos do servidor (alertas_clima.py: avaliar), no histórico de avisos enviados
    ["^Café: risco de geada em (\\d\\d/\\d\\d) \\(mínima de (\\S+ °C)\\)\\. Proteja as mudas e as plantas novas\\.$", "Coffee: frost risk on $1 (minimum of $2). Protect seedlings and young plants."],
    ["^Colheita: chuva de (\\S+ mm) prevista em (\\d\\d/\\d\\d)\\. Planeje a colheita e a secagem\\.$", "Harvest: $1 of rain forecast on $2. Plan the harvest and the drying."],
    ["^Rebanho: calor de (\\S+ °C) em (\\d\\d/\\d\\d); confira sombra e água\\.$", "Herd: heat of $1 on $2; check shade and water."],
    ["^Horta e viveiro: chuva forte \\((\\S+ mm)\\) em (\\d\\d/\\d\\d); proteja canteiros e mudas\\.$", "Garden and nursery: heavy rain ($1) on $2; protect beds and seedlings."],
    ["^Horta e viveiro: frio de (\\S+ °C) em (\\d\\d/\\d\\d); proteja canteiros e mudas\\.$", "Garden and nursery: cold of $1 on $2; protect beds and seedlings."],
    ["^Horta e viveiro: calor de (\\S+ °C) em (\\d\\d/\\d\\d); proteja canteiros e mudas\\.$", "Garden and nursery: heat of $1 on $2; protect beds and seedlings."],
    ["^Hospedagem: chuva forte \\((\\S+ mm)\\) em (\\d\\d/\\d\\d); avise os hóspedes sobre estradas e trilhas\\.$", "Lodging: heavy rain ($1) on $2; warn guests about roads and trails."],
    ["^Irrigação: (\\S+ mm) de chuva prevista em (\\d\\d/\\d\\d); avalie adiar a rega\\.$", "Irrigation: $1 of rain forecast on $2; consider postponing irrigation."],
    ["^O modelo do lugar dá (\\d+)% de chance de chover em (\\d\\d/\\d\\d); avalie adiar a rega\\.$", "The local model gives a $1% chance of rain on $2; consider postponing irrigation."],
    ["^Chuva acumulada alta: risco de deslizamento em encostas\\. Medido \\((.+)\\): (\\S+ mm) em 24 h, (\\S+ mm) em 72 h\\. Siga sempre a Defesa Civil\\.$", "High accumulated rain: landslide risk on slopes. Measured ($1): $2 in 24 h, $3 in 72 h. Always follow Civil Defense."],
    ["^Solo encharcando: observe trincas, árvores inclinadas e água barrenta\\. Medido \\((.+)\\): (\\S+ mm) em 24 h, (\\S+ mm) em 72 h\\. Siga sempre a Defesa Civil\\.$", "Soil getting soaked: watch for cracks, leaning trees and muddy water. Measured ($1): $2 in 24 h, $3 in 72 h. Always follow Civil Defense."]
  ];

  var api = { iniciar: iniciar, carregar: carregar, estado: estado, cartaoChuva: cartaoChuva, cartaoAnomalias: cartaoAnomalias, cartaoConsumo: cartaoConsumo,
    cartaoIrrigacao: cartaoIrrigacao, cartaoAvisos: cartaoAvisos, resumoAnomalias: resumoAnomalias, listaAnomalias: listaAnomalias,
    secaoResiliencia: secaoResiliencia, I18N: I18N, I18N_RX: I18N_RX };
  global.PhysisAprendizadoUI = api;
})(typeof window !== "undefined" ? window : this);
