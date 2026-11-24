/* physis-edicao.js v1 (24/11/2026): edição manual de textos e da ordem dos blocos das páginas servidas pelo hub (site da Physis,
   Casa Physis, Hub, InovaSTEM). Pedido da dona: "editar textos e layout das páginas manualmente".
   - Só aparece para quem entrou com conta (/api/instancia → autenticado); gravar exige a direção (o servidor confere).
   - Texto: títulos, parágrafos e itens de lista dentro de <main> viram editáveis (texto puro). A chave é um resumo do texto
     ORIGINAL ("t.<hash>"): se o texto original do sistema mudar, a troca antiga deixa de valer (nada some sem aviso: a lista
     de trocas fica no servidor).
   - Layout: blocos de <main> (section/.cartao de primeiro nível) sobem, descem ou ficam ocultos ("layout.ordem", "layout.ocultos").
     Cores e fontes não mudam (regra 6: só a paleta).
   - Grava em /api/site/textos/<página> (o mesmo armazenamento da consultoria). Páginas com edição própria (data-edicao-propria)
     ficam de fora. Sem internet; sem dependências. */
(function (w) {
  "use strict";
  var d = w.document;
  if (!d || w.__physisEdicao) return; w.__physisEdicao = true;
  function hash(s) { var h = 5381; for (var i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) >>> 0; return h.toString(36); }
  function pagina() { var p = (d.documentElement.getAttribute("data-pagina") || location.pathname).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    return ("ed-" + (p || "inicio")).slice(0, 40); }
  var PAG = pagina(), salvos = {}, originais = new WeakMap(), editando = false, aplicando = false;
  function principal() { return d.querySelector("main") || d.body; }
  function textos() { var m = principal(); return Array.prototype.filter.call(m.querySelectorAll("h1,h2,h3,h4,p,li"), function (e) {
    return !e.closest("nav,form,button,script,style,[data-pp-manter],[data-edicao-fora],.ped-barra") && !e.querySelector("input,select,textarea,button,canvas,svg,img") && e.textContent.trim().length > 1; }); }
  function blocos() { var m = principal(); return Array.prototype.filter.call(m.children, function (e) { return /^(SECTION|ARTICLE)$/.test(e.tagName) || e.classList.contains("cartao"); }); }
  function chaveTexto(e) { if (!originais.has(e)) originais.set(e, e.textContent.trim()); return "t." + hash(originais.get(e)); }
  function chaveBloco(b) { var t = b.querySelector("h1,h2,h3"); return "b." + hash((t ? t.textContent : b.textContent.slice(0, 80)).trim()); }
  function aplicar() {
    if (aplicando || editando) return; aplicando = true;
    try {
      textos().forEach(function (e) { var k = chaveTexto(e); if (salvos[k] && e.textContent.trim() !== salvos[k]) e.textContent = salvos[k]; });
      var ordem = (salvos["layout.ordem"] || "").split(",").filter(Boolean), ocultos = (salvos["layout.ocultos"] || "").split(",").filter(Boolean), bs = blocos();
      if (ordem.length && bs.length) { var pai = bs[0].parentNode, por = {}; bs.forEach(function (b) { por[chaveBloco(b)] = b; });
        ordem.forEach(function (k) { if (por[k]) pai.appendChild(por[k]); }); }
      blocos().forEach(function (b) { if (ocultos.indexOf(chaveBloco(b)) >= 0) b.hidden = true; });
    } finally { aplicando = false; }
  }
  function carregar() { return fetch("/api/site/textos/" + PAG, { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; })
    .then(function (j) { if (j && j.ok) { salvos = j.textos || {}; aplicar(); } }).catch(function () {}); }
  // ---- barra de edição
  var barra, msg;
  function botao(t, f, rot) { var b = d.createElement("button"); b.type = "button"; b.textContent = t; if (rot) b.setAttribute("aria-label", rot); b.onclick = f;
    b.style.cssText = "min-height:36px;padding:.3rem .7rem;border:1px solid #D9D3C2;border-radius:8px;background:#FFFFFF;color:#1B1F23;font:inherit;cursor:pointer"; return b; }
  function montarBarra() {
    barra = d.createElement("div"); barra.className = "ped-barra"; barra.setAttribute("role", "region"); barra.setAttribute("aria-label", "Edição da página");
    barra.style.cssText = "position:fixed;right:1rem;bottom:1rem;z-index:9999;display:flex;gap:.4rem;flex-wrap:wrap;align-items:center;background:#FFFFFF;color:#1B1F23;border:1px solid #D9D3C2;border-left:5px solid #C2410C;border-radius:12px;padding:.5rem .7rem;max-width:calc(100vw - 2rem)";
    msg = d.createElement("span"); msg.setAttribute("role", "status");
    var bEd = botao("Editar página", function () { ligar(!editando); bEd.textContent = editando ? "Parar de editar" : "Editar página"; bEd.setAttribute("aria-pressed", String(editando)); });
    bEd.setAttribute("aria-pressed", "false");
    barra.appendChild(bEd); barra.appendChild(botao("Salvar", salvar)); barra.appendChild(botao("Desfazer tudo", desfazer, "Voltar aos textos e à ordem originais")); barra.appendChild(msg);
    d.body.appendChild(barra);
  }
  function controles(b) {
    var c = d.createElement("div"); c.className = "ped-ctl"; c.setAttribute("data-edicao-fora", "");
    c.style.cssText = "display:flex;gap:.3rem;margin:.3rem 0;flex-wrap:wrap";
    var nome = (b.querySelector("h1,h2,h3") || {}).textContent || "bloco";
    c.appendChild(botao("↑", function () { var p = b.previousElementSibling; while (p && !blocos().includes(p)) p = p.previousElementSibling; if (p) b.parentNode.insertBefore(b, p); }, "Subir o bloco " + nome));
    c.appendChild(botao("↓", function () { var n = b.nextElementSibling; while (n && !blocos().includes(n)) n = n.nextElementSibling; if (n) b.parentNode.insertBefore(n, b); }, "Descer o bloco " + nome));
    c.appendChild(botao(b.getAttribute("data-ped-oculto") ? "Mostrar" : "Ocultar", function (ev) { var o = !b.getAttribute("data-ped-oculto");
      if (o) b.setAttribute("data-ped-oculto", "1"); else b.removeAttribute("data-ped-oculto"); b.style.opacity = o ? ".45" : ""; ev.target.textContent = o ? "Mostrar" : "Ocultar"; }, "Ocultar ou mostrar o bloco " + nome));
    b.insertBefore(c, b.firstChild);
  }
  function ligar(sim) {
    editando = sim;
    textos().forEach(function (e) { chaveTexto(e); if (sim) { try { e.contentEditable = "plaintext-only"; } catch (x) { e.contentEditable = "true"; } if (e.contentEditable !== "plaintext-only") e.contentEditable = "true";
      e.style.outline = "1px dashed #C2410C"; } else { e.removeAttribute("contenteditable"); e.style.outline = ""; } });
    blocos().forEach(function (b) { if (sim) { if (b.hidden) { b.hidden = false; b.setAttribute("data-ped-oculto", "1"); b.style.opacity = ".45"; } controles(b); }
      else { var c = b.querySelector(".ped-ctl"); if (c) c.remove(); if (b.getAttribute("data-ped-oculto")) b.hidden = true; b.style.opacity = ""; } });
    msg.textContent = sim ? "Clique nos textos para editar; use ↑ ↓ e Ocultar nos blocos." : "";
  }
  function salvar() {
    var envio = {};
    textos().forEach(function (e) { var k = chaveTexto(e), t = e.textContent.trim(); if (t !== originais.get(e)) envio[k] = t; else if (salvos[k]) envio[k] = ""; });
    envio["layout.ordem"] = blocos().map(chaveBloco).join(",");
    envio["layout.ocultos"] = blocos().filter(function (b) { return b.getAttribute("data-ped-oculto") || b.hidden; }).map(chaveBloco).join(",");
    msg.textContent = "Salvando…";
    fetch("/api/site/textos/" + PAG, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ textos: envio }) })
      .then(function (r) { return r.json().then(function (j) { return { r: r, j: j }; }); })
      .then(function (x) { if (x.r.ok && x.j.ok) { Object.keys(envio).forEach(function (k) { if (envio[k]) salvos[k] = envio[k]; else delete salvos[k]; }); msg.textContent = "Salvo."; }
        else msg.textContent = x.r.status === 401 || x.r.status === 403 ? "Só a direção pode gravar (entre com a conta da direção)." : "Não salvou: " + (x.j.erro || x.r.status); })
      .catch(function () { msg.textContent = "Sem ligação com o servidor."; });
  }
  function desfazer() {
    var envio = {}; Object.keys(salvos).forEach(function (k) { envio[k] = ""; }); if (!Object.keys(envio).length) { msg.textContent = "Nada para desfazer."; return; }
    fetch("/api/site/textos/" + PAG, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ textos: envio }) })
      .then(function (r) { if (r.ok) { msg.textContent = "Voltou ao original. Recarregando…"; setTimeout(function () { location.reload(); }, 600); } else msg.textContent = "Não desfez (" + r.status + ")."; });
  }
  function iniciar() {
    if (d.documentElement.hasAttribute("data-edicao-propria") || location.protocol.indexOf("http") !== 0) return;
    carregar();
    if (w.MutationObserver) { var t = null; new MutationObserver(function () { if (aplicando || editando) return; clearTimeout(t); t = setTimeout(aplicar, 150); })
      .observe(principal(), { childList: true, subtree: true }); }
    fetch("/api/instancia", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) { if (j && j.autenticado) montarBarra(); }).catch(function () {});
  }
  if (d.readyState === "loading") d.addEventListener("DOMContentLoaded", iniciar); else iniciar();
  w.PhysisEdicao = { hash: hash, pagina: pagina };
})(typeof window !== "undefined" ? window : this);
