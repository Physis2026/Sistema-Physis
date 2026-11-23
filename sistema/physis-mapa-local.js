/* Physis · Mapa do local (window.PhysisMapaLocal)
   Escolher onde fica a lavoura, como na página de configuração do Receptor V6 (firmware/receptor-v6/src/webpages.cpp,
   cartão "Localização (previsão de chuva)"): clique no mapa ou arraste o marcador; os campos de latitude e longitude
   ficam e andam juntos com o marcador; "Salvar localização" chama quem usa o módulo (a plataforma grava em
   POST /api/clima/local, que também atualiza o receptor).
   Diferença do original: nada vem da internet. Se o servidor tiver o MapLibre (/vendor/) e o mapa da região
   (/mapas/regiao.pmtiles, docs/MAPAS_E_DWG.md), o mapa usa esse fundo. Sem eles (ou aberto como arquivo), aparece um
   localizador desenhado aqui mesmo: grade de latitude e longitude, norte, escala e o marcador, que também anda pelas
   setas do teclado (0,001°; com Shift, 0,01°).
   API: html({lat, lon, id, rotulo, ajuda, botaoSalvar}) → texto HTML; ligar(container, {lat, lon, aoMudar, aoSalvar});
   estado(id); I18N; I18N_RX. Eventos por atributos data-pml-…, ligados uma vez no document. */
(function (global) {
  "use strict";
  var doc = global.document;
  var W = 400, H = 260;
  var VAOS = [24, 8, 2, 0.5, 0.12, 0.03, 0.008];     // graus de longitude que cabem na largura, do mais longe ao mais perto
  var ZOOM_PADRAO = 4;
  var PASSOS = [10, 5, 2, 1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001];
  var BR = { latMin: -35, latMax: 6, lonMin: -75, lonMax: -28 };   // o mesmo limite do receptor e de clima.validar_local
  var st = {};          // por id: {lat, lon, cx, cy, zoom, texto:{lat,lon}, msg, tipo, alterado}
  var opc = {};         // por id: opções de ligar()
  var ml = {};          // por id: {div, mapa, marcador}
  var base = { estado: "nao_testado", aviso: "" };   // nao_testado | testando | sim | nao
  var ligados = false, arrasto = null;
  var MEMO_BASE = "physis-mapa-base";
  var AVISO_SEM_MAPA ="Sem o mapa da região no servidor: a grade mostra só as coordenadas. Para achar o lugar, use a localização do aparelho ou digite a latitude e a longitude.";

  /* ── utilidades ── */
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function num(v, casas) { if (v == null || !isFinite(v)) return ""; return Number(v).toFixed(casas).replace(".", ","); }
  function lerNum(t) { var s = String(t == null ? "" : t).trim().replace(/\s+/g, "").replace(",", "."); if (!/^[-+]?(\d+\.?\d*|\.\d+)$/.test(s)) return NaN; return parseFloat(s); }
  function limitar(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function porId(id) { return doc.querySelector('[data-pml="' + id + '"]'); }
  function idDe(n) { var c = n && n.closest ? n.closest("[data-pml]") : null; return c ? c.getAttribute("data-pml") : null; }
  function anunciar(t) { try { if (typeof global.anunciar === "function") global.anunciar(t); } catch (e) {} }
  function noBrasil(lat, lon) { return lat >= BR.latMin && lat <= BR.latMax && lon >= BR.lonMin && lon <= BR.lonMax; }
  function servidor() { try { var p = global.location.protocol; return p === "http:" || p === "https:"; } catch (e) { return false; } }

  /* Confere o que foi digitado: erro bloqueia o movimento; fora do Brasil só avisa (o servidor recusa, mas a pessoa decide). */
  function validar(tLat, tLon) {
    var lat = lerNum(tLat), lon = lerNum(tLon);
    if (isNaN(lat) || isNaN(lon)) return { ok: false, campo: isNaN(lat) ? "lat" : "lon", msg: "Digite números, com vírgula ou ponto. Ex.: -22,5050 e -43,1830." };
    if (lat < -90 || lat > 90) return { ok: false, campo: "lat", msg: "A latitude vai de -90 a 90." };
    if (lon < -180 || lon > 180) return { ok: false, campo: "lon", msg: "A longitude vai de -180 a 180." };
    if (!noBrasil(lat, lon)) return { ok: true, lat: lat, lon: lon, aviso: "Este ponto parece estar fora do Brasil. O servidor só aceita pontos no Brasil (latitude de -35 a 6, longitude de -75 a -28)." };
    return { ok: true, lat: lat, lon: lon };
  }

  function estadoDe(id, lat, lon) {
    var s = st[id];
    var la = typeof lat === "string" ? lerNum(lat) : lat, lo = typeof lon === "string" ? lerNum(lon) : lon;
    var tem = la != null && lo != null && isFinite(la) && isFinite(lo);
    if (!s) {
      s = st[id] = { lat: tem ? la : null, lon: tem ? lo : null, zoom: ZOOM_PADRAO, msg: "", tipo: "", alterado: false };
      s.cx = tem ? la : -15.8; s.cy = tem ? lo : -47.9;       // sem ponto ainda: centro do Brasil, só para a grade
      s.texto = { lat: tem ? num(la, 5) : "", lon: tem ? num(lo, 5) : "" };
      if (!tem) s.zoom = 1;
    } else if (tem && !s.alterado && (s.lat !== la || s.lon !== lo)) {       // quem usa o módulo mudou o ponto (ex.: GPS)
      s.lat = la; s.lon = lo; s.texto = { lat: num(la, 5), lon: num(lo, 5) }; s.cx = la; s.cy = lo; if (s.zoom < 2) s.zoom = ZOOM_PADRAO;
    }
    return s;
  }

  /* ── localizador desenhado (sem mapa de fundo) ── */
  function escala(s) {          // px por grau
    var kx = W / VAOS[s.zoom], ky = kx / Math.max(0.2, Math.cos(s.cx * Math.PI / 180));
    return { kx: kx, ky: ky };
  }
  function proj(s, lat, lon) { var k = escala(s); return { x: W / 2 + (lon - s.cy) * k.kx, y: H / 2 - (lat - s.cx) * k.ky }; }
  function desproj(s, x, y) { var k = escala(s); return { lat: s.cx - (y - H / 2) / k.ky, lon: s.cy + (x - W / 2) / k.kx }; }
  function passoGrade(vao) { for (var i = 0; i < PASSOS.length; i++) if (vao / PASSOS[i] >= 3) return PASSOS[i]; return PASSOS[PASSOS.length - 1]; }
  function casasDe(p) { return p >= 1 ? 0 : p >= 0.1 ? 1 : p >= 0.01 ? 2 : 3; }
  function rotuloSvg(s) {
    return s.lat == null ? "Mapa de localização, sem ponto escolhido. Clique no mapa ou digite a latitude e a longitude."
      : "Mapa de localização. Marcador em latitude " + num(s.lat, 4) + ", longitude " + num(s.lon, 4) + ". Use as setas para mover; com Shift, o passo é maior.";
  }
  function vista(s) { return s.cx + "|" + s.cy + "|" + s.zoom; }
  function svg(id, s) {
    var vaoLon = VAOS[s.zoom], k = escala(s), vaoLat = H / k.ky;
    var pLon = passoGrade(vaoLon), pLat = passoGrade(vaoLat), c1 = casasDe(pLon), c2 = casasDe(pLat), g = "";
    var lon0 = Math.ceil((s.cy - vaoLon / 2) / pLon) * pLon, lat0 = Math.ceil((s.cx - vaoLat / 2) / pLat) * pLat;
    for (var lo = lon0; lo <= s.cy + vaoLon / 2 + 1e-9; lo += pLon) { var x = proj(s, s.cx, lo).x;
      g += '<line class="pml-g" x1="' + x.toFixed(1) + '" y1="0" x2="' + x.toFixed(1) + '" y2="' + H + '"/><text class="pml-r" x="' + (x + 3).toFixed(1) + '" y="' + (H - 6) + '">' + num(lo, c1) + "°</text>"; }
    for (var la = lat0; la <= s.cx + vaoLat / 2 + 1e-9; la += pLat) { var y = proj(s, la, s.cy).y;
      g += '<line class="pml-g" x1="0" y1="' + y.toFixed(1) + '" x2="' + W + '" y2="' + y.toFixed(1) + '"/><text class="pml-r" x="4" y="' + (y - 4).toFixed(1) + '">' + num(la, c2) + "°</text>"; }
    // escala: um valor redondo perto de 1/4 da largura
    var kmPx = vaoLon * 111.32 * Math.cos(s.cx * Math.PI / 180) / W, alvo = kmPx * W / 4, ops = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000], km = ops[0];
    for (var i = 0; i < ops.length; i++) if (ops[i] <= alvo) km = ops[i];
    var lw = km / kmPx, esc0 = W - 20 - lw;
    var barra = '<g aria-hidden="true"><rect class="pml-cx" x="' + (esc0 - 6).toFixed(1) + '" y="' + (H - 40) + '" width="' + (lw + 14).toFixed(1) + '" height="24" rx="4"/><line class="pml-esc" x1="' + esc0.toFixed(1) + '" y1="' + (H - 22) + '" x2="' + (esc0 + lw).toFixed(1) + '" y2="' + (H - 22) + '"/>'
      + '<text class="pml-r" x="' + esc0.toFixed(1) + '" y="' + (H - 27) + '">' + (km < 1 ? num(km * 1000, 0) + " m" : num(km, 0) + " km") + "</text></g>";
    var norte = '<g aria-hidden="true" transform="translate(' + (W - 26) + ',14)"><rect class="pml-cx" x="-14" y="-4" width="28" height="44" rx="4"/><path class="pml-n" d="M0 0 L8 22 L0 17 L-8 22 Z"/><text class="pml-r pml-nt" x="0" y="36" text-anchor="middle">N</text></g>';
    var marca = "";
    if (s.lat != null) { var p = proj(s, s.lat, s.lon);
      marca = '<g class="pml-m" transform="translate(' + p.x.toFixed(1) + "," + p.y.toFixed(1) + ')"><line x1="-16" y1="0" x2="-6" y2="0"/><line x1="6" y1="0" x2="16" y2="0"/><line x1="0" y1="-16" x2="0" y2="-6"/><line x1="0" y1="6" x2="0" y2="16"/><circle r="9"/><circle class="pml-mc" r="3"/></g>'; }
    return '<svg class="pml-svg" data-pml-svg="' + esc(id) + '" data-pml-v="' + vista(s) + '" id="' + esc(id) + '-svg" viewBox="0 0 ' + W + " " + H + '" tabindex="0" role="application" aria-label="' + esc(rotuloSvg(s)) + '" aria-describedby="' + esc(id) + '-ajuda">'
      + '<rect class="pml-f" x="0" y="0" width="' + W + '" height="' + H + '"/>' + g + barra + norte + marca + "</svg>";
  }

  function mensagem(s) { return s.msg ? '<p class="pml-msg ' + (s.tipo === "erro" ? "pml-erro" : s.tipo === "aviso" ? "pml-aviso" : "t2") + '">' + esc(s.msg) + "</p>" : ""; }

  /* ── HTML ── */
  function html(o) {
    o = o || {};
    var id = String(o.id || "pml").replace(/[^\w-]/g, ""), s = estadoDe(id, o.lat, o.lon);
    if (o.aoSalvar || o.aoMudar) opc[id] = Object.assign(opc[id] || {}, o);
    var comFundo = base.estado === "sim" && o.mapaBase !== false;
    var erro = s.tipo === "erro" ? s.campo : "";
    var campo = function (k, rot) {
      return '<div><label for="' + id + "-" + k + '">' + rot + '</label><input type="text" id="' + id + "-" + k + '" data-pml-campo="' + k + '" inputmode="decimal" autocomplete="off" spellcheck="false" value="' + esc(s.texto[k]) + '" aria-describedby="' + id + '-dica"' + (erro === k ? ' aria-invalid="true"' : "") + "></div>";
    };
    return '<div class="pml" data-pml="' + id + '">'
      + (o.rotulo ? '<p class="pml-rot"><strong>' + esc(o.rotulo) + "</strong></p>" : "")
      + '<p class="t2 pq" id="' + id + '-ajuda">' + esc(o.ajuda || "Clique no mapa ou arraste o marcador para escolher onde fica a lavoura. Também dá para digitar a latitude e a longitude, ou mover o marcador com as setas do teclado.") + "</p>"
      + '<div class="pml-ml" data-pml-ml="' + id + '"' + (comFundo ? "" : " hidden") + "></div>"
      + (comFundo ? "" : '<div class="pml-sv">' + svg(id, s) + "</div>"
        + '<div class="pml-bt" role="group" aria-label="Aproximação do mapa"><button type="button" data-pml-zoom="1" aria-label="Aproximar o mapa">+</button><button type="button" data-pml-zoom="-1" aria-label="Afastar o mapa">−</button><button type="button" data-pml-centro="1">Centralizar no marcador</button></div>'
        + (base.aviso ? '<p class="t2 pq pml-aviso-base">' + esc(base.aviso) + "</p>" : ""))
      + '<div class="pml-campos">' + campo("lat", "Latitude") + campo("lon", "Longitude") + "</div>"
      + '<p class="t2 pq" id="' + id + '-dica">Graus decimais, com vírgula ou ponto. No Brasil, a latitude e a longitude são negativas.</p>'
      + '<div id="' + id + '-msg" role="status" tabindex="-1">' + mensagem(s) + "</div>"
      + (o.botaoSalvar === false ? "" : '<div><button type="button" class="principal" data-pml-salvar="1">Salvar localização</button></div>')
      + "</div>";
  }

  /* ── atualizar sem redesenhar a tela toda ── */
  function atualizar(id, mudouVista) {
    var c = porId(id), s = st[id]; if (!c || !s) return;
    var sv = c.querySelector("[data-pml-svg]");
    var marca = sv && sv.querySelector(".pml-m");
    if (sv && marca && sv.getAttribute("data-pml-v") === vista(s) && s.lat != null) {      // mesma vista: só o marcador anda (o arrasto não perde o ponteiro)
      var p = proj(s, s.lat, s.lon); marca.setAttribute("transform", "translate(" + p.x.toFixed(1) + "," + p.y.toFixed(1) + ")"); sv.setAttribute("aria-label", rotuloSvg(s));
    } else if (sv) { var tinhaFoco = doc.activeElement === sv, novo = doc.createElement("div"); novo.innerHTML = svg(id, s); var n = novo.firstChild; sv.parentNode.replaceChild(n, sv); if (tinhaFoco) n.focus(); }
    ["lat", "lon"].forEach(function (k) { var i = c.querySelector('[data-pml-campo="' + k + '"]'); if (!i) return;
      if (doc.activeElement !== i || mudouVista) i.value = s.texto[k];
      if (s.tipo === "erro" && s.campo === k) i.setAttribute("aria-invalid", "true"); else i.removeAttribute("aria-invalid"); });
    var m = c.querySelector("#" + id + "-msg"); if (m) m.innerHTML = mensagem(s);
    var x = ml[id]; if (x && x.marcador && s.lat != null) x.marcador.setLngLat([s.lon, s.lat]);
  }

  function mover(id, lat, lon, origem) {
    var s = st[id]; if (!s) return;
    lat = limitar(lat, -90, 90); lon = limitar(lon, -180, 180);
    s.lat = Math.round(lat * 1e5) / 1e5; s.lon = Math.round(lon * 1e5) / 1e5; s.alterado = true;
    s.texto = { lat: num(s.lat, 5), lon: num(s.lon, 5) };
    var v = validar(s.texto.lat, s.texto.lon); s.msg = v.aviso || ""; s.tipo = v.aviso ? "aviso" : ""; s.campo = "";
    var p = proj(s, s.lat, s.lon);
    if (origem !== "arrasto" && (p.x < 12 || p.x > W - 12 || p.y < 12 || p.y > H - 12)) { s.cx = s.lat; s.cy = s.lon; }
    atualizar(id, origem !== "campo");
  }
  function avisarMudanca(id) {
    var s = st[id], o = opc[id] || {}; if (!s || s.lat == null) return;
    anunciar("Latitude " + num(s.lat, 4) + ", longitude " + num(s.lon, 4));
    if (typeof o.aoMudar === "function") { try { o.aoMudar(s.lat, s.lon); } catch (e) {} }
  }

  /* ── eventos (uma vez, no document; sobrevivem ao redesenho da tela) ── */
  function pontoSvg(sv, ev) {          // pela matriz do próprio SVG: certo mesmo com o desenho centralizado na caixa
    try { var m = sv.getScreenCTM(); if (m) { var pt = sv.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY; var q = pt.matrixTransform(m.inverse()); return { x: q.x, y: q.y }; } } catch (e) {}
    var r = sv.getBoundingClientRect(); return { x: (ev.clientX - r.left) * W / r.width, y: (ev.clientY - r.top) * H / r.height }; }
  function ligarEventos() {
    if (ligados || !doc) return; ligados = true;
    doc.addEventListener("pointerdown", function (ev) {
      var sv = ev.target.closest && ev.target.closest("[data-pml-svg]"); if (!sv || ev.button > 0) return;
      var id = sv.getAttribute("data-pml-svg"), s = st[id]; if (!s) return;
      ev.preventDefault(); sv.focus();
      var p = pontoSvg(sv, ev), q = desproj(s, p.x, p.y); arrasto = { id: id, ponteiro: ev.pointerId };
      mover(id, q.lat, q.lon, "arrasto");
    });
    doc.addEventListener("pointermove", function (ev) {
      if (!arrasto || ev.pointerId !== arrasto.ponteiro) return;
      var c = porId(arrasto.id), sv = c && c.querySelector("[data-pml-svg]"), s = st[arrasto.id]; if (!sv || !s) return;
      var p = pontoSvg(sv, ev); p.x = limitar(p.x, 0, W); p.y = limitar(p.y, 0, H);
      var q = desproj(s, p.x, p.y); mover(arrasto.id, q.lat, q.lon, "arrasto");
    });
    var soltar = function (ev) { if (!arrasto || (ev.pointerId != null && ev.pointerId !== arrasto.ponteiro)) return; var id = arrasto.id; arrasto = null; avisarMudanca(id); };
    doc.addEventListener("pointerup", soltar); doc.addEventListener("pointercancel", soltar);
    doc.addEventListener("keydown", function (ev) {
      var alvo = ev.target, sv = alvo && alvo.getAttribute && alvo.getAttribute("data-pml-svg") != null ? alvo : null;
      if (sv) {
        var id = sv.getAttribute("data-pml-svg"), s = st[id]; if (!s) return;
        var passo = ev.shiftKey ? 0.01 : 0.001, d = { ArrowUp: [passo, 0], ArrowDown: [-passo, 0], ArrowLeft: [0, -passo], ArrowRight: [0, passo] }[ev.key];
        if (d) { ev.preventDefault(); if (s.lat == null) { s.lat = s.cx; s.lon = s.cy; } mover(id, s.lat + d[0], s.lon + d[1], "teclado"); avisarMudanca(id); return; }
        if (ev.key === "+" || ev.key === "=") { ev.preventDefault(); zoom(id, 1); return; }
        if (ev.key === "-") { ev.preventDefault(); zoom(id, -1); return; }
        return;
      }
      if (ev.key === "Enter" && alvo && alvo.getAttribute && alvo.getAttribute("data-pml-campo")) { ev.preventDefault(); daCampos(idDe(alvo)); }
    });
    doc.addEventListener("input", function (ev) {
      var k = ev.target && ev.target.getAttribute && ev.target.getAttribute("data-pml-campo"); if (!k) return;
      var id = idDe(ev.target), s = st[id]; if (!s) return; s.texto[k] = ev.target.value; s.alterado = true;
    });
    doc.addEventListener("change", function (ev) {
      var k = ev.target && ev.target.getAttribute && ev.target.getAttribute("data-pml-campo"); if (k) daCampos(idDe(ev.target));
    });
    doc.addEventListener("click", function (ev) {
      var b = ev.target.closest && ev.target.closest("[data-pml-zoom],[data-pml-centro],[data-pml-salvar]"); if (!b) return;
      var id = idDe(b), s = st[id]; if (!s) return;
      if (b.hasAttribute("data-pml-zoom")) return zoom(id, +b.getAttribute("data-pml-zoom"));
      if (b.hasAttribute("data-pml-centro")) { if (s.lat != null) { s.cx = s.lat; s.cy = s.lon; } atualizar(id, true); return; }
      salvar(id);
    });
  }
  function zoom(id, d) {
    var s = st[id]; if (!s) return; s.zoom = limitar(s.zoom + d, 0, VAOS.length - 1);
    if (s.lat != null) { var p = proj(s, s.lat, s.lon); if (d > 0 || p.x < 0 || p.x > W || p.y < 0 || p.y > H) { s.cx = s.lat; s.cy = s.lon; } }
    atualizar(id, true);
  }
  function daCampos(id) {
    var s = st[id]; if (!s) return null;
    var v = validar(s.texto.lat, s.texto.lon);
    if (!v.ok) { s.msg = v.msg; s.tipo = "erro"; s.campo = v.campo; atualizar(id, false); return null; }
    if (v.lat !== s.lat || v.lon !== s.lon) { mover(id, v.lat, v.lon, "campo"); avisarMudanca(id); }
    else { s.msg = v.aviso || ""; s.tipo = v.aviso ? "aviso" : ""; s.campo = ""; atualizar(id, false); }
    return v;
  }
  function salvar(id) {
    var s = st[id], o = opc[id] || {}, v = daCampos(id);
    if (!v) { var c = porId(id), i = c && c.querySelector('[data-pml-campo="' + (s.campo || "lat") + '"]'); if (i) i.focus(); return; }
    if (typeof o.aoSalvar !== "function") return;
    s.msg = "Salvando…"; s.tipo = ""; atualizar(id, false);
    var fim = function (r) {
      var t = st[id]; if (!t) return;
      if (r && r.ok === false) { t.msg = r.erro ? "Não salvou: " + r.erro : "Não salvou."; t.tipo = "erro"; t.campo = ""; }
      else { t.alterado = false; t.msg = r && r.mensagem ? r.mensagem : (r && r.ok ? "Localização salva." : ""); t.tipo = ""; }
      atualizar(id, false); if (t.msg) anunciar(t.msg);
    };
    try { var r = o.aoSalvar(s.lat, s.lon); if (r && typeof r.then === "function") r.then(fim, function () { fim({ ok: false, erro: "o computador central não respondeu" }); }); else fim(r); }
    catch (e) { fim({ ok: false }); }
  }

  /* ── mapa com fundo (opcional): MapLibre e mapa da região servidos pelo próprio servidor ── */
  function existe(url, metodo) {
    if (typeof global.fetch !== "function") return Promise.resolve(false);
    return global.fetch(url, { method: metodo || "HEAD", cache: metodo === "GET" ? "force-cache" : "no-store", credentials: "same-origin" })
      .then(function (r) { return !!r.ok; }, function () { return false; });
  }
  function script(url) { return new Promise(function (ok, er) { var s = doc.createElement("script"); s.src = url; s.onload = function () { ok(); }; s.onerror = function () { er(new Error(url)); }; doc.head.appendChild(s); }); }
  function testarBase() {
    if (base.estado !== "nao_testado") return;
    if (!servidor()) { base.estado = "nao"; base.aviso = AVISO_SEM_MAPA; return; }
    // sem o mapa, o servidor responde 404 e o navegador anota isso no console; por isso a resposta "não tem" vale 12 h neste aparelho
    var memo = null; try { memo = JSON.parse(global.localStorage.getItem(MEMO_BASE) || "null"); } catch (e) {}
    if (memo && memo.r === "nao" && Date.now() - memo.t < 12 * 3600 * 1000) { base.estado = "nao"; base.aviso = AVISO_SEM_MAPA; return; }
    base.estado = "testando";
    existe("/mapas/regiao.pmtiles", "HEAD").then(function (temMapa) {
      if (!temMapa) throw new Error("sem-mapa");
      if (global.maplibregl) return true;
      return existe("/vendor/maplibre-gl.js", "GET").then(function (temLib) {
        if (!temLib) throw new Error("sem-biblioteca");
        if (!doc.querySelector('link[href="/vendor/maplibre-gl.css"]')) { var l = doc.createElement("link"); l.rel = "stylesheet"; l.href = "/vendor/maplibre-gl.css"; doc.head.appendChild(l); }
        return script("/vendor/maplibre-gl.js");
      });
    }).then(function () {
      if (global.pmtiles) return;
      return existe("/vendor/pmtiles.js", "GET").then(function (t) { if (!t) throw new Error("sem-pmtiles"); return script("/vendor/pmtiles.js"); });
    }).then(function () {
      if (!global.maplibregl || !global.pmtiles) throw new Error("incompleto");
      if (!global.__pmtilesOk) { var p = new global.pmtiles.Protocol(); global.maplibregl.addProtocol("pmtiles", p.tile); global.__pmtilesOk = true; }
      base.estado = "sim"; base.aviso = "";
      Object.keys(st).forEach(trocarParaFundo);
    }).catch(function () {
      base.estado = "nao";
      try { global.localStorage.setItem(MEMO_BASE, JSON.stringify({ r: "nao", t: Date.now() })); } catch (e) {}
      base.aviso = AVISO_SEM_MAPA;
      Object.keys(st).forEach(function (id) { var c = porId(id), b = c && c.querySelector(".pml-bt"); if (b && !c.querySelector(".pml-aviso-base")) { var p = doc.createElement("p"); p.className = "t2 pq pml-aviso-base"; p.textContent = base.aviso; b.parentNode.insertBefore(p, b.nextSibling); } });
    });
  }
  function trocarParaFundo(id) {
    var c = porId(id); if (!c || (opc[id] && opc[id].mapaBase === false)) return;
    var sv = c.querySelector(".pml-sv"), bt = c.querySelector(".pml-bt"), lugar = c.querySelector("[data-pml-ml]");
    if (sv) sv.remove(); if (bt) bt.remove(); if (lugar) lugar.hidden = false;
    montar(id);
  }
  function montar(id) {
    var c = porId(id), lugar = c && c.querySelector("[data-pml-ml]"), s = st[id]; if (!lugar || !s || base.estado !== "sim") return;
    var x = ml[id];
    if (x && x.div) { if (x.div.parentNode !== lugar) { lugar.appendChild(x.div); try { x.mapa.resize(); } catch (e) {} } if (s.lat != null) x.marcador.setLngLat([s.lon, s.lat]); return; }
    var M = global.maplibregl, div = doc.createElement("div"); div.className = "pml-ml-in"; lugar.appendChild(div);
    var escuro = doc.documentElement.getAttribute("data-tema") === "escuro";
    var mapa = new M.Map({ container: div, attributionControl: false, center: [s.lon != null ? s.lon : s.cy, s.lat != null ? s.lat : s.cx], zoom: s.lat != null ? 12 : 4,
      locale: { "NavigationControl.ZoomIn": "Aproximar o mapa", "NavigationControl.ZoomOut": "Afastar o mapa", "NavigationControl.ResetBearing": "Voltar o norte para cima", "Marker.Title": "Marcador da lavoura: arraste, ou use as setas para mover", "ScaleControl.Meters": "m", "ScaleControl.Kilometers": "km" },
      style: { version: 8, sources: { osm: { type: "vector", url: "pmtiles:///mapas/regiao.pmtiles" } }, layers: [
        { id: "fundo", type: "background", paint: { "background-color": escuro ? "#2A3829" : "#EEF2EA" } },
        { id: "agua", type: "fill", source: "osm", "source-layer": "water", paint: { "fill-color": escuro ? "#546A7B" : "#C3D0BD" } },
        { id: "vias", type: "line", source: "osm", "source-layer": "roads", paint: { "line-color": "#C9B98F", "line-width": 1 } }] } });
    mapa.addControl(new M.NavigationControl({ showCompass: true })); mapa.addControl(new M.ScaleControl({ unit: "metric" }));
    mapa.addControl(new M.AttributionControl({ customAttribution: "© colaboradores do OpenStreetMap" }));
    var pino = doc.createElement("div"); pino.className = "pml-pino"; pino.id = id + "-pino"; pino.tabIndex = 0;     // com id: a tela devolve o foco a ele depois de redesenhar pino.setAttribute("role", "button");
    pino.setAttribute("aria-label", "Marcador da lavoura: arraste, ou use as setas para mover");
    var marcador = new M.Marker({ element: pino, draggable: true, anchor: "bottom" }).setLngLat([s.lon != null ? s.lon : s.cy, s.lat != null ? s.lat : s.cx]).addTo(mapa);
    pino.setAttribute("aria-label", "Marcador da lavoura: arraste, ou use as setas para mover");      // o MapLibre troca pelo texto dele
    marcador.on("dragend", function () { var p = marcador.getLngLat(); mover(id, p.lat, p.lng, "arrasto"); avisarMudanca(id); });
    mapa.on("click", function (e) { mover(id, e.lngLat.lat, e.lngLat.lng, "arrasto"); avisarMudanca(id); });
    pino.addEventListener("keydown", function (ev) { var t = st[id], passo = ev.shiftKey ? 0.01 : 0.001, d = { ArrowUp: [passo, 0], ArrowDown: [-passo, 0], ArrowLeft: [0, -passo], ArrowRight: [0, passo] }[ev.key];
      if (!d || !t) return; ev.preventDefault(); ev.stopPropagation(); if (t.lat == null) { t.lat = t.cx; t.lon = t.cy; } mover(id, t.lat + d[0], t.lon + d[1], "teclado"); mapa.panTo([t.lon, t.lat]); avisarMudanca(id); });
    ml[id] = { div: div, mapa: mapa, marcador: marcador };
  }

  /* ── API ── */
  function ligar(container, o) {
    o = o || {}; ligarEventos(); estilo();
    var raiz = container || doc, lista = [];
    if (raiz.getAttribute && raiz.getAttribute("data-pml")) lista.push(raiz);
    if (raiz.querySelectorAll) Array.prototype.push.apply(lista, raiz.querySelectorAll("[data-pml]"));
    lista.forEach(function (c) {
      var id = c.getAttribute("data-pml");
      opc[id] = Object.assign(opc[id] || {}, o);
      var s = estadoDe(id, o.lat, o.lon);
      if (o.lat != null && !s.alterado) atualizar(id, true);
      if (o.mapaBase !== false) { testarBase(); if (base.estado === "sim") { if (c.querySelector(".pml-sv")) trocarParaFundo(id); else montar(id); } }
    });
    return lista.length;
  }
  function estado(id) {
    var s = st[id || "pml"]; if (!s) return null;
    var v = validar(s.texto.lat, s.texto.lon);
    return { lat: s.lat, lon: s.lon, texto: { lat: s.texto.lat, lon: s.texto.lon }, valido: v.ok, noBrasil: s.lat != null && noBrasil(s.lat, s.lon), alterado: s.alterado, zoom: s.zoom, base: base.estado === "sim" ? "mapa" : "grade" };
  }

  var CSS = ".pml{display:flex;flex-direction:column;gap:10px;min-width:0}"
    + ".pml-sv{min-width:0}.pml-svg{display:block;width:100%;height:auto;max-height:360px;border:1px solid var(--linha,#C9D2C4);border-radius:10px;background:var(--tinte,#EEF4EA);touch-action:none;cursor:crosshair;user-select:none;-webkit-user-select:none}"
    + ".pml-svg:focus-visible{outline:3px solid var(--acao,#33512F);outline-offset:2px}"
    + ".pml-svg .pml-f{fill:var(--tinte,#EEF4EA)}.pml-svg .pml-g{stroke:var(--linha,#C9D2C4);stroke-width:1}"
    + ".pml-svg .pml-r{fill:var(--tinta2,#4A4F44);font-size:13px;font-family:var(--fonte,system-ui,sans-serif)}.pml-svg .pml-nt{font-weight:700;fill:var(--tinta,#1C2B21)}"
    + ".pml-svg .pml-cx{fill:var(--sup,#FFFFFF);opacity:.85}.pml-svg .pml-n{fill:var(--tinta,#1C2B21)}.pml-svg .pml-esc{stroke:var(--tinta,#1C2B21);stroke-width:3}"
    + ".pml-svg .pml-m line{stroke:var(--acao,#33512F);stroke-width:2.5}.pml-svg .pml-m circle{fill:none;stroke:var(--acao,#33512F);stroke-width:3}.pml-svg .pml-m .pml-mc{fill:var(--acao,#33512F);stroke:none}"
    + ".pml-bt{display:flex;flex-wrap:wrap;gap:6px}.pml-bt button[data-pml-zoom]{min-width:44px;padding:0;font-size:1.2em}"
    + ".pml-ml{height:320px;border:1px solid var(--linha,#C9D2C4);border-radius:10px;overflow:hidden}.pml-ml-in{width:100%;height:100%}"
    + ".pml-campos{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(160px,100%),1fr));gap:10px}.pml-campos input{width:100%}"
    + ".pml-erro{color:var(--al-t,#7A2214);font-weight:600}.pml-aviso{color:var(--at-t,#5C3F00);font-weight:600}"
    + ".pml-pino{width:30px;height:30px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:#33512F;border:3px solid #FFFFFF;box-shadow:0 0 0 1px #1C2B21;cursor:grab}"
    + ".pml-pino:focus-visible{outline:3px solid var(--acao,#33512F);outline-offset:3px;box-shadow:0 0 0 2px #FFFFFF}";
  function estilo() { if (!doc || !doc.head || doc.getElementById("pml-estilo")) return; var e = doc.createElement("style"); e.id = "pml-estilo"; e.textContent = CSS; doc.head.appendChild(e); }

  var I18N = {
    "Clique no mapa ou arraste o marcador para escolher onde fica a lavoura. Também dá para digitar a latitude e a longitude, ou mover o marcador com as setas do teclado.": "Click the map or drag the marker to choose where the field is. You can also type the latitude and longitude, or move the marker with the arrow keys.",
    "Aproximação do mapa": "Map zoom",
    "Aproximar o mapa": "Zoom in",
    "Afastar o mapa": "Zoom out",
    "Voltar o norte para cima": "Reset north",
    "Centralizar no marcador": "Center on the marker",
    "Latitude": "Latitude",
    "Longitude": "Longitude",
    "Graus decimais, com vírgula ou ponto. No Brasil, a latitude e a longitude são negativas.": "Decimal degrees, with comma or dot. In Brazil, latitude and longitude are negative.",
    "Salvar localização": "Save location",
    "Salvando…": "Saving…",
    "Localização salva.": "Location saved.",
    "Não salvou.": "Not saved.",
    "Digite números, com vírgula ou ponto. Ex.: -22,5050 e -43,1830.": "Type numbers, with comma or dot. E.g. -22.5050 and -43.1830.",
    "A latitude vai de -90 a 90.": "Latitude goes from -90 to 90.",
    "A longitude vai de -180 a 180.": "Longitude goes from -180 to 180.",
    "Este ponto parece estar fora do Brasil. O servidor só aceita pontos no Brasil (latitude de -35 a 6, longitude de -75 a -28).": "This point seems to be outside Brazil. The server only accepts points in Brazil (latitude -35 to 6, longitude -75 to -28).",
    "Sem o mapa da região no servidor: a grade mostra só as coordenadas. Para achar o lugar, use a localização do aparelho ou digite a latitude e a longitude.": "No regional map on the server: the grid shows only the coordinates. To find the place, use this device's location or type the latitude and longitude.",
    "Mapa de localização, sem ponto escolhido. Clique no mapa ou digite a latitude e a longitude.": "Location map, no point chosen. Click the map or type the latitude and longitude.",
    "Marcador da lavoura: arraste, ou use as setas para mover": "Field marker: drag it, or use the arrow keys to move it",
    "© colaboradores do OpenStreetMap": "© OpenStreetMap contributors",
    "o computador central não respondeu": "the central computer did not answer"
  };
  var I18N_RX = [
    ["^Mapa de localização\\. Marcador em latitude (-?[\\d,]+), longitude (-?[\\d,]+)\\. Use as setas para mover; com Shift, o passo é maior\\.$", "Location map. Marker at latitude $1, longitude $2. Use the arrow keys to move it; with Shift, the step is larger."],
    ["^Latitude (-?[\\d,]+), longitude (-?[\\d,]+)$", "Latitude $1, longitude $2"],
    ["^Não salvou: (.+)$", "Not saved: $1"],
    ["^([\\d,]+) (k?m)$", "$1 $2"]
  ];

  global.PhysisMapaLocal = { html: html, ligar: ligar, estado: estado, validar: validar, I18N: I18N, I18N_RX: I18N_RX };
})(typeof window !== "undefined" ? window : this);
