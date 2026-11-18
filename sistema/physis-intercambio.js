/* physis-intercambio.js — "Intercâmbio com outras plataformas" (18/11/2026): troca de dados combinados com uma plataforma
   parceira (outra instalação compatível com a Physis), sem dividir banco. Só para a direção da instalação.
   Conversa com o servidor (physis-hub/physis_hub/intercambio.py; docs/INTERCAMBIO.md):
     GET  /api/intercambio/estado              → { origem, esquema, datasets, parceiros, pendentes, registro }
     POST /api/intercambio/parceiro            { id, nome, url, ativo, enviar: [...], receber: [...] }
     POST /api/intercambio/parceiro/chave      { id, chave? }  (sem chave: o servidor gera e mostra uma vez)
     POST /api/intercambio/parceiro/remover    { id }
     POST /api/intercambio/testar | puxar | enviar   { parceiro, dataset? }
     POST /api/intercambio/revisar             { ids: [...], decisao: "aprovar"|"recusar", motivo }
   A chave nunca volta do servidor depois de gerada; o que chega fica pendente até a direção aprovar.
   Contrato: window.PhysisIntercambio = { tela(opcoes) → HTML, ligar(raiz, opcoes), textos }. opcoes.idioma() → "pt"|"en";
   opcoes.csrf() → token da sessão (X-Physis-CSRF); opcoes.pedir(rota, corpo) → Promise<json> substitui o fetch.
   Acessível (rótulos, legendas, aria-live, foco devolvido), português e inglês, tema claro e escuro pelas classes da
   plataforma (cartao, selo, faixa, t2, t3, rolagem): o módulo não define cores próprias. Sem endereço de internet. */
(function (g) {
  "use strict";
  var T = {
    pt: { tit: "Intercâmbio com outras plataformas", intro: "Troca de dados combinados com uma plataforma parceira (outra instalação compatível com a Physis), sem dividir banco: cada lado guarda o que é seu. Os pedidos vão assinados com uma chave combinada, só por HTTPS ou pela VPN.",
      lgpd: "LGPD: só saem os campos da lista de cada conjunto. Campos pessoais (nome de cliente, autor, instrutor) só saem com consentimento marcado no registro. O que chega fica pendente até a direção aprovar.",
      esta: "Esta instalação", idOrigem: "Identificador", esquema: "Contrato", parceiros: "Plataformas parceiras", nenhum: "Nenhuma plataforma parceira cadastrada.",
      colNome: "Nome", colUrl: "Endereço", colEnvia: "Esta envia", colRecebe: "Esta recebe", colChave: "Chave", colAcoes: "Ações", sim: "sim", nao: "não", inativo: "inativo",
      testar: "Testar ligação", editar: "Editar", remover: "Remover", novo: "Cadastrar ou editar parceiro", fId: "Identificador da outra plataforma", fNome: "Nome", fUrl: "Endereço (https://… ou IP da VPN)",
      fEnviar: "O que esta instalação envia", fReceber: "O que esta instalação aceita receber", fAtivo: "Ativo", salvar: "Salvar parceiro",
      chaveTit: "Chave combinada", chaveIntro: "A chave fica só no arquivo de chaves deste servidor. Gere aqui e passe à outra plataforma por um canal seguro, ou cole a chave que ela gerou.",
      chavePar: "Parceiro", gerar: "Gerar chave nova", colar: "Chave recebida do parceiro (32 caracteres ou mais)", gravarChave: "Gravar a chave colada",
      chaveNova: "Chave gerada (aparece só agora; copie e passe ao parceiro por um canal seguro):",
      trocaTit: "Trocar agora", trocaPar: "Parceiro", trocaDs: "Conjunto de dados", puxar: "Puxar do parceiro", enviar: "Enviar ao parceiro",
      pendTit: "Chegou e espera aprovação", pendNada: "Nada pendente.", colSel: "Escolher", colDe: "De", colDs: "Conjunto", colReg: "Registro", colResumo: "Conteúdo", colSha: "SHA-256",
      aprovar: "Aprovar os escolhidos", recusar: "Recusar os escolhidos", motivo: "Motivo da recusa (opcional)",
      dsTit: "Conjuntos de dados (contrato aberto)", colCampos: "Campos que podem sair", colPessoais: "Campos pessoais (só com consentimento)", colOferta: "Oferecidos aqui", colAprov: "Recebidos e aprovados",
      regTit: "Registro do intercâmbio", regNada: "Nada registrado ainda.", colQuando: "Quando", colOp: "Operação", colDet: "Detalhe",
      ok: "Feito.", erro: "Não foi possível: ", carregando: "Carregando…", reaut: "Confirme a sua senha (Minha conta) e tente de novo.",
      confirmaRemover: "Remover este parceiro e a chave dele?", semServidor: "O intercâmbio usa o servidor desta instalação." },
    en: { tit: "Data exchange with other platforms", intro: "Exchange of agreed datasets with a partner platform (another Physis-compatible installation), without sharing databases: each side keeps its own. Requests are signed with a shared key, over HTTPS or the VPN only.",
      lgpd: "LGPD: only the fields on each dataset's list leave. Personal fields (client, author, instructor names) leave only with consent marked on the record. Whatever arrives stays pending until the management approves it.",
      esta: "This installation", idOrigem: "Identifier", esquema: "Contract", parceiros: "Partner platforms", nenhum: "No partner platform registered.",
      colNome: "Name", colUrl: "Address", colEnvia: "This one sends", colRecebe: "This one receives", colChave: "Key", colAcoes: "Actions", sim: "yes", nao: "no", inativo: "inactive",
      testar: "Test connection", editar: "Edit", remover: "Remove", novo: "Register or edit a partner", fId: "Identifier of the other platform", fNome: "Name", fUrl: "Address (https://… or VPN IP)",
      fEnviar: "What this installation sends", fReceber: "What this installation accepts", fAtivo: "Active", salvar: "Save partner",
      chaveTit: "Shared key", chaveIntro: "The key is kept only in this server's key file. Generate it here and give it to the other platform over a safe channel, or paste the key it generated.",
      chavePar: "Partner", gerar: "Generate a new key", colar: "Key received from the partner (32 characters or more)", gravarChave: "Save the pasted key",
      chaveNova: "Key generated (shown only now; copy it and give it to the partner over a safe channel):",
      trocaTit: "Exchange now", trocaPar: "Partner", trocaDs: "Dataset", puxar: "Pull from partner", enviar: "Send to partner",
      pendTit: "Arrived and awaiting approval", pendNada: "Nothing pending.", colSel: "Select", colDe: "From", colDs: "Dataset", colReg: "Record", colResumo: "Content", colSha: "SHA-256",
      aprovar: "Approve selected", recusar: "Refuse selected", motivo: "Reason for refusal (optional)",
      dsTit: "Datasets (open contract)", colCampos: "Fields that may leave", colPessoais: "Personal fields (consent only)", colOferta: "Offered here", colAprov: "Received and approved",
      regTit: "Exchange log", regNada: "Nothing logged yet.", colQuando: "When", colOp: "Operation", colDet: "Detail",
      ok: "Done.", erro: "Could not: ", carregando: "Loading…", reaut: "Confirm your password (My account) and try again.",
      confirmaRemover: "Remove this partner and its key?", semServidor: "The data exchange uses this installation's server." }
  };
  var OPS_EN = { "parceiro criado": "partner created", "parceiro alterado": "partner changed", "parceiro removido": "partner removed", "chave definida": "key set",
    "publicado": "published", "despublicado": "unpublished", "pedido recusado": "request refused", "oferta consultada": "offer read", "ligacao testada": "connection tested",
    "enviado (puxado pelo parceiro)": "sent (pulled by partner)", "recebido (enviado pelo parceiro)": "received (pushed by partner)", "recebido (puxado daqui)": "received (pulled from here)",
    "enviado (empurrado daqui)": "sent (pushed from here)", "enviar falhou": "send failed", "puxar falhou": "pull failed", "puxar recusado": "pull refused",
    "envio recusado": "sending refused", "recebimento recusado": "receiving refused", "importacao aprovada": "import approved", "importacao recusada": "import refused" };
  var est = { dados: null, msg: "", erro: false, chave: "", form: null };
  var E = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  function en(op) { var i = op && op.idioma ? op.idioma() : (g.document.documentElement.lang || "pt"); return /^en/i.test(i); }
  function L(op) { return en(op) ? T.en : T.pt; }
  function quando(ts, op) { try { return new Date(ts * 1000).toLocaleString(en(op) ? "en-GB" : "pt-BR", { dateStyle: "short", timeStyle: "short" }); } catch (e) { return ""; } }
  function nomeDs(d, op) { return d && d.nome ? (en(op) ? d.nome.en : d.nome.pt) : ""; }
  function pedir(op, rota, corpo) {
    if (op && typeof op.pedir === "function") return op.pedir(rota, corpo);
    var h = { "Content-Type": "application/json" }, tk = op && op.csrf ? op.csrf() : null; if (tk) h["X-Physis-CSRF"] = tk;
    return g.fetch(rota, corpo ? { method: "POST", headers: h, body: JSON.stringify(corpo), credentials: "same-origin" } : { credentials: "same-origin", cache: "no-store", headers: h })
      .then(function (r) { return r.json(); });
  }
  function opcoesDs(ds, op, sel) { return ds.map(function (d) { return "<option value='" + E(d.id) + "'" + (d.id === sel ? " selected" : "") + ">" + E(nomeDs(d, op)) + "</option>"; }).join(""); }
  function caixas(nome, ds, marcados, op) {
    return ds.map(function (d) { var id = "ic-" + nome + "-" + d.id;
      return "<div><label class='opc' for='" + id + "'><input type='checkbox' id='" + id + "' data-ic-" + nome + "='" + E(d.id) + "'" + (marcados.indexOf(d.id) >= 0 ? " checked" : "") + "> <span>" + E(nomeDs(d, op)) + "</span></label></div>"; }).join("");
  }
  function tela(op) {
    var t = L(op), d = est.dados;
    if (!d) return "<section class='cartao' aria-labelledby='ic-h'><h2 id='ic-h'>" + E(t.tit) + "</h2><p class='t2' role='status' id='ic-msg'>" + E(est.msg || t.carregando) + "</p></section>";
    var ds = d.datasets || [], ps = d.parceiros || [], f = est.form || { id: "", nome: "", url: "", ativo: true, enviar: [], receber: [] };
    var nomeDe = {}; ds.forEach(function (x) { nomeDe[x.id] = nomeDs(x, op); });
    var lista = function (l) { return (l || []).map(function (x) { return nomeDe[x] || x; }).join("; ") || "—"; };
    var linhasP = ps.map(function (p) {
      return "<tr><th scope='row'>" + E(p.nome) + "<br><span class='t2'>" + E(p.id) + "</span>" + (p.ativo ? "" : " <span class='selo in'>" + E(t.inativo) + "</span>") + "</th><td>" + E(p.url) + "</td><td>" + E(lista(p.enviar)) + "</td><td>" + E(lista(p.receber)) + "</td>"
        + "<td><span class='selo " + (p.tem_chave ? "ok" : "al") + "'>" + E(p.tem_chave ? t.sim : t.nao) + "</span></td><td>"
        + "<button type='button' data-ic-testar='" + E(p.id) + "' aria-label='" + E(t.testar + ": " + p.nome) + "'>" + E(t.testar) + "</button> "
        + "<button type='button' data-ic-editar='" + E(p.id) + "' aria-label='" + E(t.editar + ": " + p.nome) + "'>" + E(t.editar) + "</button> "
        + "<button type='button' data-ic-remover='" + E(p.id) + "' aria-label='" + E(t.remover + ": " + p.nome) + "'>" + E(t.remover) + "</button></td></tr>"; }).join("");
    var optP = ps.map(function (p) { return "<option value='" + E(p.id) + "'>" + E(p.nome) + "</option>"; }).join("");
    var pend = (d.pendentes || []).map(function (x) {
      var cont = Object.keys(x.dados || {}).slice(0, 4).map(function (k) { return k + ": " + (typeof x.dados[k] === "object" ? JSON.stringify(x.dados[k]) : x.dados[k]); }).join(" · ");
      return "<tr><td><input type='checkbox' id='ic-p-" + x.seq + "' data-ic-pend='" + x.seq + "' aria-label='" + E(t.colSel + ": " + x.id) + "'></td><td>" + E(x.parceiro) + "</td><td>" + E(nomeDe[x.dataset] || x.dataset) + "</td><th scope='row'>" + E(x.id) + "</th><td>" + E(cont.slice(0, 240)) + "</td><td><code>" + E(String(x.sha256).slice(0, 12)) + "…</code></td></tr>"; }).join("");
    var linhasD = ds.map(function (x) { return "<tr><th scope='row'>" + E(nomeDs(x, op)) + "<br><span class='t2'>" + E(x.id) + "</span></th><td>" + E(x.campos.join(", ")) + "</td><td>" + E(x.pessoais.join(", ")) + "</td><td>" + E(x.oferecidos) + "</td><td>" + E(x.aprovados) + "</td></tr>"; }).join("");
    var linhasR = (d.registro || []).slice(0, 100).map(function (x) {
      var det = ["dataset", "registros", "novos", "recusados", "pessoais_retirados", "motivo", "status", "por"].filter(function (k) { return x[k] != null && x[k] !== ""; }).map(function (k) { return k + ": " + x[k]; }).join(" · ");
      return "<tr><th scope='row'>" + E(quando(x.quando, op)) + "</th><td>" + E(x.parceiro) + "</td><td>" + E(en(op) ? (OPS_EN[x.operacao] || x.operacao) : x.operacao) + "</td><td>" + E(det) + "</td></tr>"; }).join("");
    return "<section class='cartao' aria-labelledby='ic-h'><h2 id='ic-h'>" + E(t.tit) + "</h2><p class='t2'>" + E(t.intro) + "</p>"
      + "<p class='faixa at' role='note'>" + E(t.lgpd) + "</p>"
      + "<p><strong>" + E(t.esta) + ":</strong> " + E(t.idOrigem) + " <code>" + E(d.origem) + "</code> · " + E(t.esquema) + " <code>" + E(d.esquema) + "</code></p>"
      + "<p id='ic-msg' tabindex='-1' role='status' aria-live='polite' class='" + (est.erro ? "faixa al" : "t2") + "'>" + E(est.msg) + "</p>"
      + (est.chave ? "<p class='faixa ok' role='alert'>" + E(t.chaveNova) + " <strong id='ic-chave-nova' tabindex='-1' style='font-family:ui-monospace,Consolas,monospace;word-break:break-all'>" + E(est.chave) + "</strong></p>" : "")
      + "<h3 class='t3' id='ic-hp'>" + E(t.parceiros) + "</h3>"
      + (linhasP ? "<div class='rolagem'><table aria-labelledby='ic-hp'><thead><tr><th scope='col'>" + E(t.colNome) + "</th><th scope='col'>" + E(t.colUrl) + "</th><th scope='col'>" + E(t.colEnvia) + "</th><th scope='col'>" + E(t.colRecebe) + "</th><th scope='col'>" + E(t.colChave) + "</th><th scope='col'>" + E(t.colAcoes) + "</th></tr></thead><tbody>" + linhasP + "</tbody></table></div>" : "<p class='t2'>" + E(t.nenhum) + "</p>")
      + "<h3 class='t3'>" + E(t.novo) + "</h3><div class='precos'>"
      + "<div><label for='ic-f-id'>" + E(t.fId) + "</label><input id='ic-f-id' type='text' maxlength='64' autocomplete='off' spellcheck='false' value='" + E(f.id) + "' style='width:100%'></div>"
      + "<div><label for='ic-f-nome'>" + E(t.fNome) + "</label><input id='ic-f-nome' type='text' maxlength='120' value='" + E(f.nome) + "' style='width:100%'></div>"
      + "<div><label for='ic-f-url'>" + E(t.fUrl) + "</label><input id='ic-f-url' type='url' maxlength='300' inputmode='url' value='" + E(f.url) + "' style='width:100%'></div>"
      + "<div><label class='opc' for='ic-f-ativo'><input type='checkbox' id='ic-f-ativo'" + (f.ativo !== false ? " checked" : "") + "> <span>" + E(t.fAtivo) + "</span></label></div></div>"
      + "<fieldset><legend>" + E(t.fEnviar) + "</legend>" + caixas("env", ds, f.enviar || [], op) + "</fieldset>"
      + "<fieldset><legend>" + E(t.fReceber) + "</legend>" + caixas("rec", ds, f.receber || [], op) + "</fieldset>"
      + "<p><button type='button' id='ic-salvar' class='principal'>" + E(t.salvar) + "</button></p>"
      + (ps.length ? "<h3 class='t3'>" + E(t.chaveTit) + "</h3><p class='t2'>" + E(t.chaveIntro) + "</p><div class='precos'>"
        + "<div><label for='ic-k-par'>" + E(t.chavePar) + "</label><select id='ic-k-par' style='width:100%'>" + optP + "</select></div>"
        + "<div style='align-self:end'><button type='button' id='ic-gerar'>" + E(t.gerar) + "</button></div>"
        + "<div><label for='ic-k-colar'>" + E(t.colar) + "</label><input id='ic-k-colar' type='password' autocomplete='off' maxlength='200' style='width:100%'></div>"
        + "<div style='align-self:end'><button type='button' id='ic-gravar-chave'>" + E(t.gravarChave) + "</button></div></div>"
        + "<h3 class='t3'>" + E(t.trocaTit) + "</h3><div class='precos'>"
        + "<div><label for='ic-t-par'>" + E(t.trocaPar) + "</label><select id='ic-t-par' style='width:100%'>" + optP + "</select></div>"
        + "<div><label for='ic-t-ds'>" + E(t.trocaDs) + "</label><select id='ic-t-ds' style='width:100%'>" + opcoesDs(ds, op) + "</select></div>"
        + "<div style='align-self:end'><button type='button' id='ic-puxar'>" + E(t.puxar) + "</button> <button type='button' id='ic-enviar'>" + E(t.enviar) + "</button></div></div>" : "")
      + "<h3 class='t3' id='ic-hpend'>" + E(t.pendTit) + "</h3>"
      + (pend ? "<div class='rolagem'><table aria-labelledby='ic-hpend'><thead><tr><th scope='col'>" + E(t.colSel) + "</th><th scope='col'>" + E(t.colDe) + "</th><th scope='col'>" + E(t.colDs) + "</th><th scope='col'>" + E(t.colReg) + "</th><th scope='col'>" + E(t.colResumo) + "</th><th scope='col'>" + E(t.colSha) + "</th></tr></thead><tbody>" + pend + "</tbody></table></div>"
        + "<div class='precos'><div><label for='ic-motivo'>" + E(t.motivo) + "</label><input id='ic-motivo' type='text' maxlength='300' style='width:100%'></div>"
        + "<div style='align-self:end'><button type='button' id='ic-aprovar' class='principal'>" + E(t.aprovar) + "</button> <button type='button' id='ic-recusar'>" + E(t.recusar) + "</button></div></div>" : "<p class='t2'>" + E(t.pendNada) + "</p>")
      + "<h3 class='t3' id='ic-hds'>" + E(t.dsTit) + "</h3><div class='rolagem'><table aria-labelledby='ic-hds'><thead><tr><th scope='col'>" + E(t.colDs) + "</th><th scope='col'>" + E(t.colCampos) + "</th><th scope='col'>" + E(t.colPessoais) + "</th><th scope='col'>" + E(t.colOferta) + "</th><th scope='col'>" + E(t.colAprov) + "</th></tr></thead><tbody>" + linhasD + "</tbody></table></div>"
      + "<h3 class='t3' id='ic-hreg'>" + E(t.regTit) + "</h3>"
      + (linhasR ? "<div class='rolagem'><table aria-labelledby='ic-hreg'><thead><tr><th scope='col'>" + E(t.colQuando) + "</th><th scope='col'>" + E(t.colDe) + "</th><th scope='col'>" + E(t.colOp) + "</th><th scope='col'>" + E(t.colDet) + "</th></tr></thead><tbody>" + linhasR + "</tbody></table></div>" : "<p class='t2'>" + E(t.regNada) + "</p>")
      + "</section>";
  }
  function ligar(raiz, op) {
    if (!raiz || raiz.__icLigado) return; raiz.__icLigado = true;
    var $ = function (id) { return g.document.getElementById(id); };
    var pintar = function (foco) { raiz.innerHTML = tela(op); var f = foco && $(foco); if (f) f.focus(); };
    var carregar = function (foco) { pedir(op, "/api/intercambio/estado").then(function (j) { if (j && j.ok) est.dados = j; else { est.erro = true; est.msg = L(op).erro + ((j && j.erro) || ""); } pintar(foco); })
      .catch(function () { est.erro = true; est.msg = L(op).semServidor; pintar(foco); }); };
    var resposta = function (j, foco) { var t = L(op); est.erro = !(j && j.ok); est.msg = j && j.ok ? (j.aviso || t.ok) : (j && j.reautenticar ? t.reaut : t.erro + ((j && j.erro) || "")); carregar(foco || "ic-msg"); };
    var marcados = function (nome) { return Array.prototype.slice.call(raiz.querySelectorAll("[data-ic-" + nome + "]")).filter(function (c) { return c.checked; }).map(function (c) { return c.getAttribute("data-ic-" + nome); }); };
    raiz.addEventListener("click", function (ev) {
      var b = ev.target.closest ? ev.target.closest("button") : null; if (!b) return; var t = L(op), id;
      if (b.id === "ic-salvar") {
        est.form = { id: $("ic-f-id").value.trim(), nome: $("ic-f-nome").value.trim(), url: $("ic-f-url").value.trim(), ativo: $("ic-f-ativo").checked, enviar: marcados("env"), receber: marcados("rec") };
        est.chave = ""; pedir(op, "/api/intercambio/parceiro", est.form).then(function (j) { if (j && j.ok) est.form = null; resposta(j); });
      } else if (b.id === "ic-gerar") {
        pedir(op, "/api/intercambio/parceiro/chave", { id: $("ic-k-par").value }).then(function (j) { est.chave = j && j.ok ? j.chave || "" : ""; resposta(j, est.chave ? "ic-chave-nova" : "ic-msg"); });
      } else if (b.id === "ic-gravar-chave") {
        var c = $("ic-k-colar").value.trim(); est.chave = "";
        pedir(op, "/api/intercambio/parceiro/chave", { id: $("ic-k-par").value, chave: c }).then(function (j) { resposta(j); });
      } else if (b.id === "ic-puxar" || b.id === "ic-enviar") {
        b.disabled = true; est.chave = "";
        pedir(op, "/api/intercambio/" + (b.id === "ic-puxar" ? "puxar" : "enviar"), { parceiro: $("ic-t-par").value, dataset: $("ic-t-ds").value }).then(function (j) { resposta(j); });
      } else if (b.id === "ic-aprovar" || b.id === "ic-recusar") {
        var ids = marcados("pend").map(Number); if (!ids.length) return;
        pedir(op, "/api/intercambio/revisar", { ids: ids, decisao: b.id === "ic-aprovar" ? "aprovar" : "recusar", motivo: ($("ic-motivo") || {}).value || "" }).then(function (j) { resposta(j); });
      } else if ((id = b.getAttribute("data-ic-testar"))) {
        pedir(op, "/api/intercambio/testar", { parceiro: id }).then(function (j) { resposta(j); });
      } else if ((id = b.getAttribute("data-ic-editar"))) {
        var p = ((est.dados || {}).parceiros || []).filter(function (x) { return x.id === id; })[0]; if (!p) return;
        est.form = { id: p.id, nome: p.nome, url: p.url, ativo: p.ativo, enviar: p.enviar, receber: p.receber }; est.chave = ""; pintar("ic-f-nome");
      } else if ((id = b.getAttribute("data-ic-remover"))) {
        if (g.confirm && !g.confirm(t.confirmaRemover)) return;
        est.chave = ""; pedir(op, "/api/intercambio/parceiro/remover", { id: id }).then(function (j) { resposta(j); });
      }
    });
    pintar(); carregar();
  }
  g.PhysisIntercambio = { tela: tela, ligar: ligar, textos: T };
})(typeof window !== "undefined" ? window : this);
