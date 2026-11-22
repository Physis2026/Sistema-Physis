/* physis-desenvolvimento.js v1 (22/11/2026): painel "Desenvolvimento" igual em todos os módulos, plataformas internas e Gestão.
   Fonte única: o Physis M&A. O bot "desenvolvimento" grava sistema/desenvolvimento-dados.js (window.PHYSIS_DESENV);
   esta página só LÊ. Uso: <div data-physis-desenvolvimento="planejador"></div> (ou "todos" na Gestão).
   Sem internet, sem rastreamento; segue idioma e tema das preferências Physis. */
(function (w) {
  "use strict";
  var d = w.document;
  var T = {
    pt: { tit: "Desenvolvimento", fonte: "Fonte: Physis M&A · atualizado em", semDados: "Ainda sem dados do M&A: rode o bot \"desenvolvimento\" (ou espere a próxima hora).",
      tarefas: "tarefas", feitas: "feitas", revisao: "em revisão", abertas: "abertas", atrasadas: "atrasadas", prox: "Próximos prazos",
      aprov: "Aprovações", reg: "Última regressão", nada: "nada pendente", estimada: "[CONFERIR]", arquivo: "Onde fica",
      est: { a_fazer: "a fazer", fazendo: "fazendo", bloqueada: "bloqueada", revisao: "em revisão", feita: "feita",
             pendente: "pendente", aprovado: "aprovado", ajustar: "ajustar", reprovado: "reprovado" } },
    en: { tit: "Development", fonte: "Source: Physis M&V · updated", semDados: "No M&V data yet: run the \"desenvolvimento\" bot (or wait for the next hour).",
      tarefas: "tasks", feitas: "done", revisao: "in review", abertas: "open", atrasadas: "late", prox: "Next deadlines",
      aprov: "Approvals", reg: "Last regression", nada: "nothing pending", estimada: "[TO CHECK]", arquivo: "Location",
      est: { a_fazer: "to do", fazendo: "doing", bloqueada: "blocked", revisao: "in review", feita: "done",
             pendente: "pending", aprovado: "approved", ajustar: "adjust", reprovado: "rejected" } }
  };
  function idioma() { try { return (localStorage.getItem("physis-pref-idioma") || d.documentElement.lang || "pt").slice(0, 2) === "en" ? "en" : "pt"; } catch (e) { return "pt"; } }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function estilo() {
    if (d.getElementById("pdv-estilo")) return;
    var s = d.createElement("style"); s.id = "pdv-estilo";
    s.textContent = ".pdv{border:1px solid var(--linha,#D9D3C2);border-left:5px solid var(--terracota,#BB6B4A);border-radius:12px;padding:.6rem .9rem;margin:1rem 0;background:var(--sup,#FFFFFF);color:var(--texto,#1B1F23);font-size:.92rem}" +
      ".pdv summary{cursor:pointer;font-weight:700}.pdv .pdv-m{margin:.6rem 0;padding-top:.5rem;border-top:1px dashed var(--linha,#D9D3C2)}" +
      ".pdv .pdv-barra{height:8px;border-radius:6px;background:var(--linha,#D9D3C2);overflow:hidden;margin:.35rem 0}.pdv .pdv-barra span{display:block;height:100%;background:var(--verde,#2F7D5B)}" +
      ".pdv .pdv-n{display:inline-block;margin:.1rem .5rem .1rem 0}.pdv .pdv-at{color:var(--rotulo,#C2410C);font-weight:700}.pdv ul{margin:.3rem 0;padding-left:1.1rem}.pdv small{opacity:.8}";
    d.head.appendChild(s);
  }
  function bloco(m, t) {
    var x = m.tarefas || {}, f = x.total ? Math.round(100 * x.feitas / x.total) : 0;
    var h = '<div class="pdv-m"><strong>' + esc(idioma() === "en" ? m.nome_en : m.nome) + "</strong><br><small>" + esc(m.descricao) + " · " + t.arquivo + ": " + esc(m.arquivo) + "</small>" +
      '<div class="pdv-barra" role="img" aria-label="' + f + '%"><span style="width:' + Math.max(2, f) + '%"></span></div>' +
      '<span class="pdv-n">' + x.total + " " + t.tarefas + '</span><span class="pdv-n">' + x.feitas + " " + t.feitas + '</span><span class="pdv-n">' + x.revisao + " " + t.revisao +
      '</span><span class="pdv-n">' + x.abertas + " " + t.abertas + '</span><span class="pdv-n' + (x.atrasadas ? " pdv-at" : "") + '">' + x.atrasadas + " " + t.atrasadas + "</span>";
    h += "<div><em>" + t.prox + ":</em>" + ((m.proximas || []).length ? "<ul>" + m.proximas.map(function (p) {
      return "<li>" + esc(p.fim) + " · " + esc(t.est[p.estado] || p.estado) + " · " + esc(p.titulo) + (p.estimada ? " " + t.estimada : "") + "</li>"; }).join("") + "</ul>" : " " + t.nada) + "</div>";
    h += "<div><em>" + t.aprov + ":</em>" + ((m.aprovacoes || []).length ? "<ul>" + m.aprovacoes.map(function (a) {
      return "<li>" + esc(a.prazo) + " · " + esc(t.est[a.estado] || a.estado) + " · " + esc(a.item) + "</li>"; }).join("") + "</ul>" : " " + t.nada) + "</div></div>";
    return h;
  }
  function render(el) {
    var t = T[idioma()], D = w.PHYSIS_DESENV, qual = el.getAttribute("data-physis-desenvolvimento") || "todos";
    // painel INTERNO: nunca aparece dentro da plataforma do cliente (tela em quadro) nem sem os dados do M&A
    var emQuadro = false; try { emQuadro = w.self !== w.top || d.documentElement.hasAttribute("data-em-quadro") || d.documentElement.hasAttribute("data-physis-demo"); } catch (e) { emQuadro = true; }
    if (emQuadro || !D || !D.modulos) { el.innerHTML = ""; el.hidden = true; return; }
    el.hidden = false;
    estilo();
    var h = '<details class="pdv"' + (qual === "todos" ? " open" : "") + "><summary>" + t.tit + "</summary>";
    var ks = qual === "todos" ? Object.keys(D.modulos) : qual.split(",");
    ks.forEach(function (k) { if (D.modulos[k]) h += bloco(D.modulos[k], t); });
    h += "<p><small>" + t.reg + ": " + esc(D.regressao && D.regressao.quando) + " · " + esc(D.regressao && D.regressao.resultado).slice(0, 160) + "<br>" + t.fonte + " " + esc(D.gerado) + "</small></p></details>";
    el.innerHTML = h;
  }
  function tudo() { Array.prototype.forEach.call(d.querySelectorAll("[data-physis-desenvolvimento]"), render); }
  w.PhysisDesenvolvimento = { render: render, atualizar: tudo };
  if (d.readyState === "loading") d.addEventListener("DOMContentLoaded", tudo); else tudo();
  w.addEventListener("storage", function (e) { if (e.key && e.key.indexOf("physis-pref") === 0) tudo(); });
})(typeof window !== "undefined" ? window : this);
