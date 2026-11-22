/* physis-explica.js v1 (22/11/2026): bot de explicação de cada tela, que funciona SEM servidor e sem internet.
   Busca nas perguntas e respostas da própria tela (window.PHYSIS_EXPLICA[contexto], vindas de sistema/explica-*.js) e
   mostra a melhor resposta + temas ligados. Quando a página tiver uma IA disponível (window.PhysisIA.perguntar), tenta
   primeiro por ela e cai nas respostas prontas se não houver. PT/EN pelas preferências. Sem rastreamento.
   Uso: <div data-physis-explica="planejador"></div>. Original único: sistema/physis-explica.js. */
(function (w) {
  "use strict";
  var d = w.document;
  function lingua() { try { return (localStorage.getItem("physis-pref-idioma") || localStorage.getItem("physis-idioma") || d.documentElement.lang || "pt").slice(0, 2) === "en" ? "en" : "pt"; } catch (e) { return "pt"; } }
  var TX = { pt: { tit: "Como funciona? Pergunte", dica: "Escreva sua dúvida ou escolha um tema.", perguntar: "Perguntar", nada: "Não encontrei uma resposta pronta para isso. Temas que posso explicar:", ver: "Ver também", ia: "Resposta da IA" },
             en: { tit: "How does it work? Ask", dica: "Type your question or pick a topic.", perguntar: "Ask", nada: "I have no ready answer for that. Topics I can explain:", ver: "See also", ia: "AI answer" } };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function norm(s) { return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  function palavras(s) { return norm(s).split(/[^a-z0-9]+/).filter(function (x) { return x.length > 2; }); }
  function campo(x, L) { return x && typeof x === "object" ? (x[L] || x.pt || "") : (x || ""); }
  function buscar(base, txt, L) {
    var q = palavras(txt); if (!q.length) return [];
    return base.map(function (e) {
      var alvo = palavras(campo(e.p, L) + " " + (e.k || []).join(" ")), s = 0;
      q.forEach(function (p) { alvo.forEach(function (a) { if (a === p) s += 3; else if (a.indexOf(p) === 0 || p.indexOf(a) === 0) s += 1; }); });
      return { e: e, s: s };
    }).filter(function (x) { return x.s >= 3; }).sort(function (a, b) { return b.s - a.s; }).map(function (x) { return x.e; });
  }
  function estilo() {
    if (d.getElementById("pex-estilo")) return;
    var s = d.createElement("style"); s.id = "pex-estilo";
    s.textContent = ".pex{border:1px solid var(--linha,#D9D3C2);border-left:5px solid var(--verde,#2F7D5B);border-radius:12px;margin:1rem 0;background:var(--sup,#FFFFFF);color:var(--texto,#1B1F23);max-width:100%;overflow-wrap:anywhere}" +
      ".pex summary{cursor:pointer;font-weight:700;padding:.6rem .9rem}.pex .pex-c{padding:0 .9rem .8rem}.pex input{flex:1 1 14rem;font:inherit;padding:.4rem;border:1px solid var(--linha,#D9D3C2);border-radius:8px;background:transparent;color:inherit}" +
      ".pex .pex-l{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center;margin:.4rem 0}.pex button{border:1px solid var(--linha,#D9D3C2);border-radius:999px;padding:.25rem .65rem;font:inherit;font-size:.88rem;cursor:pointer;background:var(--sup,#FFFFFF);color:inherit}" +
      ".pex .pex-p{background:var(--botao,#C2410C);border-color:var(--botao,#C2410C);color:#FFFFFF;border-radius:8px;font-size:1rem}.pex .pex-r{margin-top:.5rem}.pex .pex-r h3{margin:.3rem 0;font-size:1rem}";
    d.head.appendChild(s);
  }
  function montar(el) {
    if (el.getAttribute("data-pex-ok")) return; el.setAttribute("data-pex-ok", "1");
    try { if (d.documentElement.hasAttribute("data-physis-demo")) { el.hidden = true; return; } } catch (e) { /* segue */ }
    var L = lingua(), t = TX[L], ctx = el.getAttribute("data-physis-explica") || "", base = ((w.PHYSIS_EXPLICA || {})[ctx] || {}).itens || [];
    if (!base.length) { el.hidden = true; return; }
    estilo();
    var temas = base.filter(function (e) { return e.tema; });
    el.innerHTML = '<details class="pex"><summary>' + t.tit + '</summary><div class="pex-c"><small>' + t.dica + '</small><div class="pex-l"><input type="text" aria-label="' + t.tit + '"><button class="pex-p">' + t.perguntar +
      '</button></div><div class="pex-l">' + temas.map(function (e, i) { return '<button data-i="' + base.indexOf(e) + '">' + esc(campo(e.tema, L)) + "</button>"; }).join("") + '</div><div class="pex-r" role="status"></div></div></details>';
    var inp = el.querySelector("input"), out = el.querySelector(".pex-r");
    function mostrar(e, extra) {
      var rel = (e.ver || []).map(function (id) { return base.filter(function (x) { return x.id === id; })[0]; }).filter(Boolean);
      out.innerHTML = "<h3>" + esc(campo(e.p, L)) + "</h3><p>" + esc(campo(e.r, L)) + "</p>" + (rel.length ? "<p><small>" + t.ver + ": " + rel.map(function (x) { return '<button data-i="' + base.indexOf(x) + '">' + esc(campo(x.tema || x.p, L)) + "</button>"; }).join(" ") + "</small></p>" : "") + (extra || "");
      ligar(out);
    }
    function ligar(raiz) { Array.prototype.forEach.call(raiz.querySelectorAll("[data-i]"), function (b) { b.onclick = function () { mostrar(base[+b.getAttribute("data-i")]); }; }); }
    function perguntar() {
      var txt = inp.value.trim(); if (!txt) return;
      var achou = buscar(base, txt, L), pronta = function () {
        if (achou.length) mostrar(achou[0]); else { out.innerHTML = "<p>" + t.nada + "</p><div class='pex-l'>" + temas.map(function (e) { return '<button data-i="' + base.indexOf(e) + '">' + esc(campo(e.tema, L)) + "</button>"; }).join("") + "</div>"; ligar(out); }
      };
      if (w.PhysisIA && typeof w.PhysisIA.perguntar === "function") {
        Promise.resolve(w.PhysisIA.perguntar(txt, { contexto: ctx, idioma: L })).then(function (r) { if (r) out.innerHTML = "<h3>" + t.ia + "</h3><p>" + esc(r) + "</p>"; else pronta(); }, pronta);
      } else pronta();
    }
    el.querySelector(".pex-p").onclick = perguntar; inp.onkeydown = function (e) { if (e.key === "Enter") perguntar(); };
    ligar(el);
  }
  function tudo() { Array.prototype.forEach.call(d.querySelectorAll("[data-physis-explica]"), montar); }
  w.PhysisExplica = { montar: montar, buscar: buscar };
  if (d.readyState === "loading") d.addEventListener("DOMContentLoaded", tudo); else tudo();
  if (w.MutationObserver) new MutationObserver(function () { Array.prototype.forEach.call(d.querySelectorAll("[data-physis-explica]:not([data-pex-ok])"), montar); }).observe(d.documentElement, { childList: true, subtree: true });
})(typeof window !== "undefined" ? window : this);
