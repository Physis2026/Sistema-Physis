/* physis-paginas.js v1 (26/11/2026) · Páginas de 20 em vez de rolagem longa. Pedido da dona: "a partir de 20 itens, criar
   páginas 1 (1 a 20), 2 (21 a 40), 3 (41 a 60)...; as atuais sempre na página 1".
   Toda tabela (tbody) e lista (ul/ol) dentro do conteúdo principal com mais de 20 linhas ganha uma barra de páginas logo abaixo.
   A ordem é a da tela (as telas já listam o mais novo primeiro); a página 1 é sempre a inicial e volta a ser a 1 quando a lista muda.
   Fora: menus, abas, a barra de preferências e o que tiver data-sem-paginas. Só esconde (classe), não apaga nem muda função
   (regra 2). Funciona com o desenho ao vivo das telas (observa o conteúdo). Sem internet, sem dependências.
   ORIGINAL ÚNICO: sistema/physis-paginas.js; ferramentas/sincronizar.py copia para as telas (bloco script id="physis-paginas"). */
(function (w) {
  "use strict";
  var d = w.document; if (!d || w.PhysisPaginas) return;
  var N = 20, FORA = "nav,[role=tablist],[role=menu],.pp-barra,#pxp-barra,[data-pp-manter],[data-sem-paginas],.ped-barra,header,footer,select,datalist";
  var st = d.createElement("style"); st.id = "pg-estilo";
  st.textContent = ".pg-fora{display:none!important}.pg-nav{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:8px 0}" +
    ".pg-nav button{min-height:36px;min-width:44px;padding:4px 10px;border-radius:8px;border:1px solid currentColor;background:transparent;color:inherit;font:inherit;cursor:pointer}" +
    ".pg-nav button[aria-current=page]{font-weight:700;outline:2px solid currentColor;outline-offset:1px}.pg-nav span{opacity:.85}";
  (d.head || d.documentElement).appendChild(st);
  function rot(i, n) { var a = i * N + 1, b = Math.min(n, (i + 1) * N); return a + "–" + b; }
  function itens(c) { return Array.prototype.filter.call(c.children, function (e) { return e.tagName === "TR" || e.tagName === "LI"; }); }
  function navDe(c) { var alvo = c.tagName === "TBODY" ? c.closest("table") : c, cx = alvo && alvo.parentNode && alvo.parentNode.classList && /rolagem|tabwrap/.test(alvo.parentNode.className) ? alvo.parentNode : alvo;
    var n = cx.nextElementSibling; return { cx: cx, nav: n && n.getAttribute && n.getAttribute("data-pg-nav") != null ? n : null }; }
  function um(c) {
    var it = itens(c), x = navDe(c), total = it.length, assin = total + ":" + (it[0] ? (it[0].textContent || "").slice(0, 40) : "");
    if (total <= N) { it.forEach(function (e) { e.classList.remove("pg-fora"); }); if (x.nav) x.nav.remove(); return; }
    if (c.getAttribute("data-pg-assin") !== assin) { c.setAttribute("data-pg-assin", assin); c.setAttribute("data-pg", "0"); }   // lista mudou: volta à página 1
    var pg = Math.min(+c.getAttribute("data-pg") || 0, Math.ceil(total / N) - 1);
    it.forEach(function (e, i) { var f = i < pg * N || i >= (pg + 1) * N; if (e.classList.contains("pg-fora") !== f) e.classList.toggle("pg-fora", f); });
    var k = Math.ceil(total / N), html = "<span>" + (lingua() === "en" ? "Page " : "Página ") + (pg + 1) + (lingua() === "en" ? " of " : " de ") + k + " · " + rot(pg, total) + (lingua() === "en" ? " of " : " de ") + total + "</span>";
    for (var i = 0; i < k; i++) html += '<button type="button" data-pg-ir="' + i + '"' + (i === pg ? ' aria-current="page"' : "") + ' aria-label="' + (lingua() === "en" ? "Page " : "Página ") + (i + 1) + " (" + rot(i, total) + ')">' + (i + 1) + "</button>";
    if (!x.nav) { x.nav = d.createElement("div"); x.nav.className = "pg-nav"; x.nav.setAttribute("data-pg-nav", ""); x.nav.setAttribute("role", "group");
      x.nav.setAttribute("aria-label", lingua() === "en" ? "Pages" : "Páginas"); x.cx.parentNode.insertBefore(x.nav, x.cx.nextSibling); }
    if (x.nav.innerHTML !== html) x.nav.innerHTML = html;
    x.nav.__alvo = c;
  }
  function lingua() { return (d.documentElement.lang || "pt").slice(0, 2) === "en" ? "en" : "pt"; }
  var ocupado = false;
  function tudo() { if (ocupado) return; ocupado = true;
    try { var raiz = d.querySelector("main") || d.body; if (!raiz) return;
      Array.prototype.forEach.call(raiz.querySelectorAll("tbody, ul, ol"), function (c) { if (c.closest(FORA)) return; um(c); }); }
    finally { setTimeout(function () { ocupado = false; }, 0); } }
  d.addEventListener("click", function (ev) { var b = ev.target && ev.target.closest && ev.target.closest("[data-pg-ir]"); if (!b) return;
    var nav = b.closest("[data-pg-nav]"), c = nav && nav.__alvo; if (!c) return; c.setAttribute("data-pg", b.getAttribute("data-pg-ir")); um(c);
    var nb = nav.querySelector('[data-pg-ir="' + b.getAttribute("data-pg-ir") + '"]'); if (nb) nb.focus(); });
  function iniciar() { tudo(); if (w.MutationObserver) { var t = null; new MutationObserver(function (ms) {
      if (ms.every(function (m) { return m.target && m.target.closest && m.target.closest("[data-pg-nav]"); })) return; clearTimeout(t); t = setTimeout(tudo, 120); })
      .observe(d.body, { childList: true, subtree: true }); } }
  if (d.readyState === "loading") d.addEventListener("DOMContentLoaded", iniciar); else iniciar();
  w.PhysisPaginas = { POR_PAGINA: N, atualizar: tudo };
})(typeof window !== "undefined" ? window : this);
