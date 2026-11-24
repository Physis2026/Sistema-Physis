/* physis-3d.js v2 · vista 3D de modelos (IFC lido pelo web-ifc) com three.js · VERSÃO DE TESTE (22/11/2026)
   SPDX-License-Identifier: AGPL-3.0-only · Copyright (C) 2026 Physis Engineering

   O que faz: monta uma vista 3D num elemento, com luz de céu e sol, sombras suaves, materiais PBR, mapeamento de tons
   (ACES), arestas, vistas prontas, tela cheia, altura ajustável, captura em alta resolução (PNG) e exportação glTF
   binário (GLB) para um renderizador offline (Blender/Cycles), sempre como opção.
   Só aparência: não calcula áreas nem muda dados. Quem chama entrega as malhas e continua dono das contas.
   Sem internet: Physis3D.carregar("/vendor/") traz o three.js 0.170 em módulos (vendor/three/, com oclusão de ambiente e
   leitor glTF) ou, sem eles, o three.min.js 0.160; tudo servido pelo próprio servidor.
   Cores: o fundo e as arestas seguem as variáveis da tela (--bg/--fundo, --ink/--tinta), então acompanham o tema claro e
   escuro; as demais vêm de physis-hub/docs/PALETA.md.
   O sol é de apresentação (posição fixa), não é estudo solar. O norte do modelo (TrueNorth do IFC) é lido e mostrado numa
   rosa no canto, também na imagem salva e no GLB; sem norte no modelo aparece "N?" com [MARCADOR].

   Uso:
     var v = Physis3D.criar(div, { qualidade: "alta" | "atual", nome: "casa-physis", rotulo: "Modelo BIM em 3D" });
     v.adicionarMalha({ pos: Float32Array, nor: Float32Array, ix: Uint32Array, cor: [r, g, b, a] (sRGB 0–1), espaco: false, nome: "" });
     v.terminar();                 // enquadra e desenha
     v.capturar(2).then(blob)      // PNG com 2× os pixels da vista
     v.glb()                       // ArrayBuffer .glb
     v.destruir();
   Norte: Physis3D.criar(div, { norte: Physis3D.norteDoIFC(api, modelo, WebIFC) }) mostra a rosa (e na imagem salva).
   Ajudante para o web-ifc: Physis3D.malhasDoIFC(api, modelo, WebIFC, aoMalha) chama aoMalha({pos, nor, ix, cor, espaco, id}).
*/
(function (g) {
  "use strict";
  var ALTURAS = [["360", "Compacta"], ["540", "Média"], ["720", "Alta"]];
  var ESCALAS = [["1", "1× (tela)"], ["2", "2×"], ["4", "4× (apresentação)"]];
  var MAX_LADO = 8192;

  function corDaTela(el, nomes, padrao) {
    try {
      var s = g.getComputedStyle(el);
      for (var i = 0; i < nomes.length; i++) { var v = s.getPropertyValue(nomes[i]).trim(); if (v) return v; }
    } catch (e) {}
    return padrao;
  }
  function elem(tag, at, filhos) {
    var e = g.document.createElement(tag);
    for (var k in at || {}) { if (k === "texto") e.textContent = at[k]; else if (k.slice(0, 2) === "on") e[k] = at[k]; else e.setAttribute(k, at[k]); }
    (filhos || []).forEach(function (f) { if (f) e.appendChild(f); });
    return e;
  }
  function seletor(rotulo, opcoes, valor, aoMudar) {
    var s = elem("select", { "aria-label": rotulo, "class": "p3d-sel" });
    opcoes.forEach(function (o) { var op = elem("option", { value: o[0], texto: o[1] }); if (o[0] === valor) op.selected = true; s.appendChild(op); });
    s.onchange = function () { aoMudar(s.value); };
    return elem("label", { "class": "p3d-rot" }, [g.document.createTextNode(rotulo + " "), s]);
  }
  function botao(texto, acao, dica) { return elem("button", { type: "button", "class": "btn p3d-bt", title: dica || texto, onclick: acao, texto: texto }); }

  var CSS = ".p3d{position:relative}.p3d-quadro{position:relative}" +
    ".p3d-norte{position:absolute;top:8px;right:8px;width:48px;height:48px;pointer-events:none}" +
    ".p3d-norte circle{fill:var(--panel,var(--sup,#FFFFFF));stroke:var(--ink,var(--tinta,#1B1F23));stroke-width:1.5}" +
    ".p3d-norte path{fill:#BB6B4A}.p3d-norte text{fill:var(--ink,var(--tinta,#1B1F23));font:700 11px sans-serif}" +
    "html[data-tema=\"escuro\"] .p3d-norte path{fill:#D9A58C}.p3d-barra{display:flex;flex-wrap:wrap;gap:.4rem;align-items:center;margin:.4rem 0}" +
    ".p3d-bt,.p3d-sel{min-height:44px;min-width:44px}.p3d-rot{display:inline-flex;align-items:center;gap:.3rem;font-size:.88rem}" +
    ".p3d canvas{display:block;width:100%;border:1px solid var(--line,#D9D3C2);border-radius:10px;touch-action:none}" +
    ".p3d canvas:focus-visible{outline:3px solid var(--focus,#C2410C);outline-offset:2px}" +
    ".p3d:fullscreen{background:var(--bg,#F4F1EA);padding:.6rem;overflow:auto}.p3d:fullscreen canvas{height:calc(100vh - 9rem)!important}";

  function criar(area, op) {
    op = op || {};
    var THREE = g.THREE;
    if (!THREE) throw new Error("three.js não carregado");
    var alta = op.qualidade !== "atual";
    if (!g.document.getElementById("p3d-css")) g.document.head.appendChild(elem("style", { id: "p3d-css", texto: CSS }));
    var altura = +(op.altura || 360);
    var raiz = elem("div", { "class": "p3d", role: "group", "aria-label": op.rotulo || "Vista 3D" });
    var dica = elem("p", { "class": "hint", id: "p3d-dica-" + Math.random().toString(36).slice(2, 8),
      texto: "Arraste para girar (Shift ou botão direito: mover); roda ou pinça para aproximar. Teclado: setas giram, Shift+setas movem, + e − aproximam, 0 volta ao início." });
    var cv = elem("canvas", { tabindex: "0", role: "img", "aria-label": (op.rotulo || "Modelo em 3D") + ". Use as setas para girar.", "aria-describedby": dica.id });
    cv.style.height = altura + "px";
    var aviso = elem("p", { "class": "hint", role: "status", "aria-live": "polite" });

    var ren, A = alta && ADD ? ADD : null;
    try { ren = new THREE.WebGLRenderer({ canvas: cv, antialias: true, alpha: !!A, preserveDrawingBuffer: false }); }
    catch (e) { area.replaceChildren(elem("p", { "class": "hint", texto: "Este navegador não abriu o 3D (WebGL desligado ou sem placa de vídeo)." })); throw e; }
    var cena = new THREE.Scene(), malhas = [], caixa = new THREE.Box3(), arestas = new THREE.Group(), chao = null, sol = null;
    var dpr = Math.min(g.devicePixelRatio || 1, 2);
    if (alta) {
      ren.outputColorSpace = THREE.SRGBColorSpace;
      ren.toneMapping = THREE.ACESFilmicToneMapping; ren.toneMappingExposure = 1.05;
      ren.shadowMap.enabled = true; ren.shadowMap.type = THREE.PCFSoftShadowMap;
      ren.setPixelRatio(dpr);
      cena.add(new THREE.HemisphereLight(0xFFFFFF, 0xD9D3C2, 1.6));
      sol = new THREE.DirectionalLight(0xFFFFFF, 2.6); sol.castShadow = true;
      sol.shadow.mapSize.set(2048, 2048);
      cena.add(sol, sol.target, arestas);
    } else {
      /* igual à vista antiga do Planejador (até 22/11/2026), para comparar */
      cena.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 1.1));
      var s0 = new THREE.DirectionalLight(0xffffff, 0.8); s0.position.set(5, 10, 7); cena.add(s0);
    }
    /* oclusão de ambiente (GTAO): só com o three.js em módulos (Physis3D.carregar); sem ele a vista funciona igual, sem o efeito */
    var comp = null, gtao = null, ocl = !!A && op.oclusao !== false;
    /* com o pós-processamento, o tom ACES escureceria o fundo: o 3D sai transparente e o fundo é a cor da tela (CSS) */
    function corFundo() { return corDaTela(area, ["--bg", "--fundo"], "#F4F1EA"); }
    function fundo() {
      if (A) { cena.background = null; ren.setClearColor(0x000000, 0); cv.style.background = corFundo(); return; }
      cena.background = new THREE.Color(alta ? corFundo() : 0xF4F6F1);
    }
    fundo();

    /* norte: direção do TrueNorth do IFC no plano do modelo (x, y); o web-ifc entrega Y para cima, então o norte vira (x, 0, -y).
       Sem norte no modelo, a rosa mostra "N?" e o aviso pede o dado (regra: o norte sempre indicado em sistemas de construção). */
    var norte = op.norte && isFinite(op.norte.x) && isFinite(op.norte.y) && (op.norte.x || op.norte.y) ? new THREE.Vector3(op.norte.x, 0, -op.norte.y).normalize() : null;
    var rosa = g.document.createElementNS("http://www.w3.org/2000/svg", "svg");
    rosa.setAttribute("class", "p3d-norte"); rosa.setAttribute("viewBox", "-24 -24 48 48"); rosa.setAttribute("role", "img");
    rosa.setAttribute("aria-label", norte ? "Indicador do norte" : "Norte não informado no modelo [MARCADOR]");
    rosa.innerHTML = '<circle r="22"/><g class="p3d-seta"><path d="M0,-9 L6,13 L0,9 L-6,13 Z"/><text y="-11" x="0" text-anchor="middle">' + (norte ? "N" : "N?") + "</text></g>";
    var anguloNorte = 0;
    var cam = new THREE.PerspectiveCamera(45, 1, 0.01, 1000), alvo = new THREE.Vector3(), az = 0.8, el = 0.6, dist = 10, raio = 1, inicial = null;
    function tamanho() {
      var W = Math.max(280, cv.clientWidth || area.clientWidth || 640), H = cv.clientHeight || altura;
      ren.setSize(W, H, false); cam.aspect = W / H; cam.updateProjectionMatrix();
      if (comp) { comp.setPixelRatio(ren.getPixelRatio()); comp.setSize(W, H); }
    }
    function montarComposicao() {
      if (!A || comp) return;
      var rt = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: 4 });
      comp = new A.EffectComposer(ren, rt);
      comp.addPass(new A.RenderPass(cena, cam));
      gtao = new A.GTAOPass(cena, cam, 1, 1);
      gtao.updateGtaoMaterial({ radius: Math.max(0.4, raio * 0.025), distanceExponent: 1.5, thickness: Math.max(1, raio * 0.02), scale: 1.2, samples: 16 });
      gtao.blendIntensity = 0.9; gtao.enabled = ocl;
      comp.addPass(gtao); comp.addPass(new A.OutputPass());
    }
    function desenhar() {
      cam.position.set(alvo.x + dist * Math.cos(el) * Math.sin(az), alvo.y + dist * Math.sin(el), alvo.z + dist * Math.cos(el) * Math.cos(az));
      cam.lookAt(alvo); if (comp) comp.render(); else ren.render(cena, cam);
      if (norte) { cam.updateMatrixWorld(); var a0 = alvo.clone().project(cam), a1 = alvo.clone().addScaledVector(norte, raio * 0.2).project(cam);
        anguloNorte = Math.atan2(a1.x - a0.x, (a1.y - a0.y) / cam.aspect); }
      rosa.querySelector(".p3d-seta").setAttribute("transform", "rotate(" + (anguloNorte * 180 / Math.PI).toFixed(1) + ")");
    }
    function mover(dx, dy) {
      var dir = new THREE.Vector3(), dirx = new THREE.Vector3(), diry = new THREE.Vector3();
      cam.getWorldDirection(dir); dirx.crossVectors(dir, cam.up).normalize(); diry.crossVectors(dirx, dir).normalize();
      var k = dist * 0.0015; alvo.addScaledVector(dirx, -dx * k).addScaledVector(diry, dy * k); desenhar();
    }
    /* enquadra pelos vértices do modelo (amostra), não pela caixa: lote girado fica maior */
    var amostra = [];
    function enquadrar() {
      tamanho();
      var dir = new THREE.Vector3(-Math.cos(el) * Math.sin(az), -Math.sin(el), -Math.cos(el) * Math.cos(az)).normalize();
      var dx = new THREE.Vector3().crossVectors(dir, cam.up); if (dx.lengthSq() < 1e-6) dx.set(1, 0, 0); dx.normalize();
      var dy = new THREE.Vector3().crossVectors(dx, dir).normalize(), d = new THREE.Vector3();
      var u0 = Infinity, u1 = -Infinity, v0 = Infinity, v1 = -Infinity, w0 = 0;
      for (var i = 0; i < amostra.length; i += 3) { d.set(amostra[i] - alvo.x, amostra[i + 1] - alvo.y, amostra[i + 2] - alvo.z);
        var u = d.dot(dx), v = d.dot(dy), w = d.dot(dir); if (u < u0) u0 = u; if (u > u1) u1 = u; if (v < v0) v0 = v; if (v > v1) v1 = v; if (w < w0) w0 = w; }
      if (!isFinite(u0)) return;
      /* centro do desenho no centro da vista; distância para caber ~85%, somando a parte do modelo à frente do alvo */
      alvo.addScaledVector(dx, (u0 + u1) / 2).addScaledVector(dy, (v0 + v1) / 2);
      var t = Math.tan(cam.fov * Math.PI / 360);
      dist = Math.max(raio * 0.3, Math.max((u1 - u0) / 2 / (t * cam.aspect), (v1 - v0) / 2 / t) / 0.85 - w0);
      /* refino pela projeção em perspectiva, partindo dessa distância segura (sempre fora do modelo) */
      var minimo = dist * 0.35, p = new THREE.Vector3();
      for (var it = 0; it < 5; it++) {
        cam.position.copy(alvo).addScaledVector(dir, -dist); cam.lookAt(alvo); cam.updateMatrixWorld();
        var x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
        for (var k = 0; k < amostra.length; k += 3) { p.set(amostra[k], amostra[k + 1], amostra[k + 2]).project(cam); if (p.z > 1 || p.z < -1) continue;
          if (p.x < x0) x0 = p.x; if (p.x > x1) x1 = p.x; if (p.y < y0) y0 = p.y; if (p.y > y1) y1 = p.y; }
        var m = Math.max(x1 - x0, y1 - y0) / 2; if (!isFinite(m) || m <= 0) break;
        var mh = dist * t; alvo.addScaledVector(dx, (x0 + x1) / 2 * mh * cam.aspect).addScaledVector(dy, (y0 + y1) / 2 * mh);
        dist = Math.max(minimo, dist * Math.pow(m / 0.85, 0.8));
      }
    }
    function zoom(f) { dist = Math.max(raio * 0.15, Math.min(raio * 20, dist * f)); desenhar(); }
    function vista(nome) {
      if (!inicial) return;
      alvo.copy(inicial.alvo); dist = inicial.dist; mexeu = false;
      var V = { iso: [0.8, 0.6], planta: [0, 1.5], frente: [0, 0.3], lado: [Math.PI / 2, 0.3] }[nome] || [0.8, 0.6];
      az = V[0]; el = V[1]; if (alta) enquadrar(); desenhar(); aviso.textContent = "Vista: " + ({ iso: "isométrica", planta: "de cima", frente: "frente", lado: "lateral" }[nome] || nome) + ".";
    }

    /* mouse, toque e caneta */
    var pts = {}, arr = null, pinca = 0, mexeu = false;
    ["pointerdown", "wheel", "keydown"].forEach(function (t) { cv.addEventListener(t, function () { mexeu = true; }); });
    cv.addEventListener("contextmenu", function (e) { e.preventDefault(); });
    cv.addEventListener("pointerdown", function (e) { pts[e.pointerId] = [e.clientX, e.clientY]; arr = { x: e.clientX, y: e.clientY, mover: e.shiftKey || e.button === 2 }; try { cv.setPointerCapture(e.pointerId); } catch (x) {} });
    function solta(e) { delete pts[e.pointerId]; pinca = 0; if (!Object.keys(pts).length) arr = null; }
    cv.addEventListener("pointerup", solta); cv.addEventListener("pointercancel", solta);
    cv.addEventListener("pointermove", function (e) {
      if (!arr) return; pts[e.pointerId] = [e.clientX, e.clientY];
      var ks = Object.keys(pts);
      if (ks.length === 2) { var a = pts[ks[0]], b = pts[ks[1]], d = Math.hypot(a[0] - b[0], a[1] - b[1]); if (pinca) zoom(pinca / d); pinca = d; return; }
      var dx = e.clientX - arr.x, dy = e.clientY - arr.y; arr.x = e.clientX; arr.y = e.clientY;
      if (arr.mover) mover(dx, dy); else { az -= dx * 0.01; el = Math.max(-1.45, Math.min(1.5, el + dy * 0.01)); desenhar(); }
    });
    cv.addEventListener("wheel", function (e) { e.preventDefault(); zoom(e.deltaY > 0 ? 1.1 : 0.9); }, { passive: false });
    cv.addEventListener("keydown", function (e) {
      var k = e.key, f = true;
      if (k === "ArrowLeft") { if (e.shiftKey) mover(-30, 0); else { az += 0.1; desenhar(); } }
      else if (k === "ArrowRight") { if (e.shiftKey) mover(30, 0); else { az -= 0.1; desenhar(); } }
      else if (k === "ArrowUp") { if (e.shiftKey) mover(0, -30); else { el = Math.min(1.5, el + 0.08); desenhar(); } }
      else if (k === "ArrowDown") { if (e.shiftKey) mover(0, 30); else { el = Math.max(-1.45, el - 0.08); desenhar(); } }
      else if (k === "+" || k === "=") zoom(0.9);
      else if (k === "-" || k === "_") zoom(1.1);
      else if (k === "0" || k === "Home") vista("iso");
      else f = false;
      if (f) e.preventDefault();
    });

    var mats = {};
    function material(cor, espaco) {
      var r = cor[0], gg = cor[1], b = cor[2], a = espaco ? 0.25 : (cor[3] == null ? 1 : cor[3]);
      var chave = [r, gg, b, a, espaco ? 1 : 0].map(function (x) { return (+x).toFixed(4); }).join(",");
      if (mats[chave]) return mats[chave];
      var c = alta ? new THREE.Color().setRGB(r, gg, b, THREE.SRGBColorSpace) : new THREE.Color(r, gg, b);
      var m = alta ? new THREE.MeshStandardMaterial({ color: c, roughness: 0.82, metalness: 0, transparent: a < 1, opacity: a, side: THREE.DoubleSide, depthWrite: a >= 1 })
                   : new THREE.MeshLambertMaterial({ color: c, transparent: espaco || a < 1, opacity: a, side: THREE.DoubleSide });
      if (alta) { m.polygonOffset = true; m.polygonOffsetFactor = 1; m.polygonOffsetUnits = 1; }
      return (mats[chave] = m);
    }
    var api = {
      cena: cena, renderizador: ren, camera: cam, canvas: cv, qualidade: alta ? "alta" : "atual",
      adicionarMalha: function (m) {
        var geo = new THREE.BufferGeometry();
        geo.setAttribute("position", new THREE.BufferAttribute(m.pos, 3));
        if (m.nor) geo.setAttribute("normal", new THREE.BufferAttribute(m.nor, 3)); else geo.computeVertexNormals();
        if (m.ix) geo.setIndex(new THREE.BufferAttribute(m.ix, 1));
        var malha = new THREE.Mesh(geo, material(m.cor || [0.8, 0.8, 0.8, 1], !!m.espaco));
        malha.name = m.nome || ""; malha.userData.espaco = !!m.espaco;
        if (alta) { malha.castShadow = !m.espaco && malha.material.opacity >= 1; malha.receiveShadow = !m.espaco;
          if (!m.espaco) arestas.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo, 25), linhaMat)); }
        cena.add(malha); malhas.push(malha); geo.computeBoundingBox(); caixa.union(geo.boundingBox);
        if (!m.espaco) { var passo = Math.max(1, Math.floor(m.pos.length / 3 / 400)) * 3; for (var q = 0; q < m.pos.length; q += passo) amostra.push(m.pos[q], m.pos[q + 1], m.pos[q + 2]); }
        return malha;
      },
      terminar: function () {
        if (caixa.isEmpty()) { aviso.textContent = "O modelo não tem geometria para mostrar em 3D."; return api; }
        caixa.getCenter(alvo); raio = caixa.getSize(new THREE.Vector3()).length() / 2 || 1; dist = raio * (alta ? 2.2 : 2.6);
        cam.near = raio / 100; cam.far = raio * 100;
        if (alta) {
          sol.position.set(alvo.x + raio * 1.1, alvo.y + raio * 1.6, alvo.z + raio * 0.7); sol.target.position.copy(alvo);
          var sc = sol.shadow.camera; sc.left = sc.bottom = -raio * 1.2; sc.right = sc.top = raio * 1.2; sc.near = raio * 0.1; sc.far = raio * 5; sc.updateProjectionMatrix();
          sol.shadow.bias = -0.0015; sol.shadow.normalBias = raio * 0.004;
          /* chão que recebe sombra: útil para prédio solto; desligado quando o modelo já traz o terreno */
          chao = new THREE.Mesh(new THREE.PlaneGeometry(raio * 8, raio * 8), new THREE.ShadowMaterial({ opacity: 0.22 }));
          chao.rotation.x = -Math.PI / 2; chao.position.set(alvo.x, caixa.min.y - raio * 0.002, alvo.z); chao.receiveShadow = true; chao.visible = !!op.chao; cena.add(chao);
        }
        if (alta) enquadrar();
        montarComposicao();
        inicial = { alvo: alvo.clone(), dist: dist };
        tamanho(); desenhar(); return api;
      },
      redesenhar: function () { fundo(); linhaMat.color.set(corArestas()); tamanho(); desenhar(); },
      vista: vista,
      capturar: function (escala) {
        escala = Math.max(1, +escala || 2);
        var W = cv.clientWidth || 640, H = cv.clientHeight || altura, k = Math.min(escala, MAX_LADO / Math.max(W, H));
        var antes = ren.getPixelRatio();
        ren.setPixelRatio(k); ren.setSize(W, H, false); if (comp) { comp.setPixelRatio(k); comp.setSize(W, H); } desenhar();
        var url;
        if (A) { var c2 = g.document.createElement("canvas"); c2.width = cv.width; c2.height = cv.height; var x2 = c2.getContext("2d");
          x2.fillStyle = corFundo(); x2.fillRect(0, 0, c2.width, c2.height); x2.drawImage(cv, 0, 0); norteNaImagem(x2, c2.width, k); url = c2.toDataURL("image/png"); }
        else { var c3 = g.document.createElement("canvas"); c3.width = cv.width; c3.height = cv.height; var x3 = c3.getContext("2d");
          x3.drawImage(cv, 0, 0); norteNaImagem(x3, c3.width, k); url = c3.toDataURL("image/png"); }
        ren.setPixelRatio(alta ? dpr : antes); tamanho(); desenhar();
        return fetch(url).then(function (r) { return r.blob(); });
      },
      glb: function () { return paraGLB(malhas, op.nome || "modelo", op.norte || null); },
      oclusao: function () { return !!(gtao && gtao.enabled); },
      destruir: function () { try { ro && ro.disconnect(); mo && mo.disconnect(); if (comp) comp.dispose(); ren.dispose(); } catch (e) {} }
    };

    /* a imagem salva leva a rosa do norte no canto, como na tela */
    function norteNaImagem(x, largura, k) {
      var r = 22 * k, cx = largura - (8 + 24) * k, cy = (8 + 24) * k, est = g.getComputedStyle(rosa.querySelector("circle")), est2 = g.getComputedStyle(rosa.querySelector("path"));
      x.save(); x.translate(cx, cy); x.beginPath(); x.arc(0, 0, r, 0, 2 * Math.PI); x.fillStyle = est.fill || "#FFFFFF"; x.fill();
      x.lineWidth = 1.5 * k; x.strokeStyle = est.stroke || "#1B1F23"; x.stroke(); x.rotate(anguloNorte);
      x.beginPath(); x.moveTo(0, -9 * k); x.lineTo(6 * k, 13 * k); x.lineTo(0, 9 * k); x.lineTo(-6 * k, 13 * k); x.closePath(); x.fillStyle = est2.fill || "#BB6B4A"; x.fill();
      x.fillStyle = est.stroke || "#1B1F23"; x.font = "700 " + 11 * k + "px sans-serif"; x.textAlign = "center"; x.fillText(norte ? "N" : "N?", 0, -11 * k);
      x.restore();
    }
    function corArestas() { return corDaTela(area, ["--ink", "--tinta"], "#1B1F23"); }
    var linhaMat = new THREE.LineBasicMaterial({ color: new THREE.Color(corArestas()), transparent: true, opacity: 0.35 });

    function baixar(blob, nome) { var a = elem("a", { href: URL.createObjectURL(blob), download: nome }); g.document.body.appendChild(a); a.click(); setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 500); }
    var escala = "2";
    var barra = elem("div", { "class": "p3d-barra", role: "toolbar", "aria-label": "Ferramentas da vista 3D" }, [
      botao("Isométrica", function () { vista("iso"); }), botao("De cima", function () { vista("planta"); }),
      botao("Frente", function () { vista("frente"); }), botao("Lateral", function () { vista("lado"); }),
      alta ? (function () { var c = elem("input", { type: "checkbox", checked: "checked" }); c.onchange = function () { arestas.visible = c.checked; desenhar(); };
        return elem("label", { "class": "p3d-rot p3d-bt" }, [c, g.document.createTextNode(" Arestas")]); })() : null,
      A ? (function () { var c = elem("input", { type: "checkbox" }); if (ocl) c.checked = true; c.onchange = function () { ocl = c.checked; if (gtao) gtao.enabled = ocl; desenhar(); };
        return elem("label", { "class": "p3d-rot p3d-bt" }, [c, g.document.createTextNode(" Oclusão de ambiente")]); })() : null,
      alta ? (function () { var c = elem("input", { type: "checkbox" }); if (op.chao) c.checked = true; c.onchange = function () { if (chao) chao.visible = c.checked; desenhar(); };
        return elem("label", { "class": "p3d-rot p3d-bt" }, [c, g.document.createTextNode(" Sombra no chão")]); })() : null,
      seletor("Altura", ALTURAS, String(altura), function (v) { altura = +v; cv.style.height = altura + "px"; tamanho(); desenhar(); }),
      botao("Tela cheia", function () { if (g.document.fullscreenElement) g.document.exitFullscreen(); else if (raiz.requestFullscreen) raiz.requestFullscreen().then(function () { cv.focus(); }); }),
      seletor("Imagem", ESCALAS, escala, function (v) { escala = v; }),
      botao("Salvar imagem (PNG)", function () { api.capturar(+escala).then(function (b) { baixar(b, (op.nome || "vista-3d") + "-" + escala + "x.png"); aviso.textContent = "Imagem salva em " + escala + "× a resolução da vista."; }); }),
      alta ? botao("Baixar modelo (GLB)", function () { baixar(new Blob([api.glb()], { type: "model/gltf-binary" }), (op.nome || "modelo") + ".glb"); aviso.textContent = "Modelo em glTF binário salvo: abre no Blender (Cycles) para imagens de apresentação."; }, "glTF binário para renderizar fora do navegador") : null
    ]);
    raiz.append(barra, elem("div", { "class": "p3d-quadro" }, [cv, rosa]), aviso, dica);
    if (!norte) aviso.textContent = "O modelo não informa o norte (TrueNorth): [MARCADOR] conferir a orientação no projeto.";
    area.replaceChildren(raiz);

    var ro = g.ResizeObserver ? new g.ResizeObserver(function () { if (!inicial) return; if (alta && !mexeu) { alvo.copy(inicial.alvo); enquadrar(); } else tamanho(); desenhar(); }) : null; if (ro) ro.observe(cv);
    /* tema: a vista acompanha a troca de Claro/Escuro/Automático */
    var mo = g.MutationObserver ? new g.MutationObserver(function () { if (inicial) api.redesenhar(); }) : null;
    if (mo) mo.observe(g.document.documentElement, { attributes: true, attributeFilter: ["data-tema", "data-theme", "class"] });
    try { g.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () { if (inicial) api.redesenhar(); }); } catch (e) {}
    g.document.addEventListener("fullscreenchange", function () { if (inicial) { tamanho(); desenhar(); } });
    return api;
  }

  /* glTF 2.0 binário (GLB): uma malha por elemento, material PBR com a cor do modelo. Eixo Y para cima (igual ao web-ifc). */
  function paraGLB(malhas, nome, norte) {
    var partes = [], tam = 0, bviews = [], acess = [], materiais = [], chaves = {}, nos = [], meshes = [];
    function junta(arr, alvo) { var pad = (4 - (tam % 4)) % 4; if (pad) { partes.push(new Uint8Array(pad)); tam += pad; }
      var u = new Uint8Array(arr.buffer, arr.byteOffset, arr.byteLength).slice(); partes.push(u);
      bviews.push({ buffer: 0, byteOffset: tam, byteLength: u.byteLength, target: alvo }); tam += u.byteLength; return bviews.length - 1; }
    malhas.forEach(function (m, i) {
      var geo = m.geometry, p = geo.attributes.position, n = geo.attributes.normal;
      if (!p) return;
      var pos = new Float32Array(p.array), mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
      for (var k = 0; k < pos.length; k += 3) for (var j = 0; j < 3; j++) { if (pos[k + j] < mn[j]) mn[j] = pos[k + j]; if (pos[k + j] > mx[j]) mx[j] = pos[k + j]; }
      var at = { POSITION: acess.push({ bufferView: junta(pos, 34962), componentType: 5126, count: pos.length / 3, type: "VEC3", min: mn, max: mx }) - 1 };
      if (n) at.NORMAL = acess.push({ bufferView: junta(new Float32Array(n.array), 34962), componentType: 5126, count: n.count, type: "VEC3" }) - 1;
      var prim = { attributes: at };
      if (geo.index) { var ix = new Uint32Array(geo.index.array); prim.indices = acess.push({ bufferView: junta(ix, 34963), componentType: 5125, count: ix.length, type: "SCALAR" }) - 1; }
      var mt = m.material, c = mt.color, a = mt.opacity == null ? 1 : mt.opacity, ch = [c.r, c.g, c.b, a].map(function (x) { return x.toFixed(4); }).join(",");
      if (chaves[ch] == null) { chaves[ch] = materiais.length; materiais.push({ name: "cor-" + materiais.length, doubleSided: true, alphaMode: a < 1 ? "BLEND" : "OPAQUE",
        pbrMetallicRoughness: { baseColorFactor: [c.r, c.g, c.b, a], metallicFactor: 0, roughnessFactor: 0.82 } }); }
      prim.material = chaves[ch];
      meshes.push({ name: m.name || ("elemento-" + i), primitives: [prim] });
      nos.push({ name: m.name || ("elemento-" + i), mesh: meshes.length - 1 });
    });
    var bin = new Uint8Array((tam + 3) & ~3), o = 0;
    partes.forEach(function (u) { bin.set(u, o); o += u.byteLength; });
    var json = { asset: { version: "2.0", generator: "physis-3d.js v2 (Physis Engineering)" }, scene: 0,
      scenes: [{ name: nome, nodes: nos.map(function (_, i) { return i; }) }], nodes: nos, meshes: meshes, materials: materiais,
      accessors: acess, bufferViews: bviews, buffers: [{ byteLength: bin.byteLength }] };
    /* norte do IFC (plano x, y do modelo) para o renderizador offline desenhar a seta */
    if (norte && isFinite(norte.x) && isFinite(norte.y)) json.asset.extras = { physis_norte: { x: +norte.x, y: +norte.y } };
    var jt = new TextEncoder().encode(JSON.stringify(json)), jl = (jt.length + 3) & ~3;
    var total = 12 + 8 + jl + 8 + bin.byteLength, out = new ArrayBuffer(total), dv = new DataView(out), u8 = new Uint8Array(out);
    dv.setUint32(0, 0x46546C67, true); dv.setUint32(4, 2, true); dv.setUint32(8, total, true);
    dv.setUint32(12, jl, true); dv.setUint32(16, 0x4E4F534A, true); u8.fill(0x20, 20, 20 + jl); u8.set(jt, 20);
    dv.setUint32(20 + jl, bin.byteLength, true); dv.setUint32(24 + jl, 0x004E4942, true); u8.set(bin, 28 + jl);
    return out;
  }

  /* norte do IFC: TrueNorth do contexto de modelo (IfcGeometricRepresentationContext, não o subcontexto); null se não houver */
  function norteDoIFC(api, modelo, WebIFC) {
    try {
      var ids = api.GetLineIDsWithType(modelo, WebIFC.IFCGEOMETRICREPRESENTATIONCONTEXT);
      for (var i = 0; i < ids.size(); i++) {
        var c = api.GetLine(modelo, ids.get(i));
        if (!c || !c.TrueNorth) continue;
        var d = api.GetLine(modelo, c.TrueNorth.value != null ? c.TrueNorth.value : c.TrueNorth.expressID);
        var r = (d && d.DirectionRatios || []).map(function (v) { return +(v && v.value != null ? v.value : v); });
        if (r.length >= 2 && (r[0] || r[1])) return { x: r[0], y: r[1] };
      }
    } catch (e) {}
    return null;
  }

  /* web-ifc → malhas (posições já com a transformação de cada peça) */
  function malhasDoIFC(api, modelo, WebIFC, aoMalha) {
    var espacos = new Set(), ids = api.GetLineIDsWithType(modelo, WebIFC.IFCSPACE);
    for (var i = 0; i < ids.size(); i++) espacos.add(ids.get(i));
    var M = g.THREE ? new g.THREE.Matrix4() : null;
    function receber(malha) {
      var pgs = malha.geometries;
      for (var i = 0; i < pgs.size(); i++) {
        var pg = pgs.get(i), geo = api.GetGeometry(modelo, pg.geometryExpressID);
        var v = api.GetVertexArray(geo.GetVertexData(), geo.GetVertexDataSize()), ix = api.GetIndexArray(geo.GetIndexData(), geo.GetIndexDataSize());
        var n = v.length / 6, pos = new Float32Array(n * 3), nor = new Float32Array(n * 3), t = pg.flatTransformation;
        M.fromArray(t); var Mn = new g.THREE.Matrix3().getNormalMatrix(M), vv = new g.THREE.Vector3();
        for (var k = 0; k < n; k++) {
          vv.set(v[k * 6], v[k * 6 + 1], v[k * 6 + 2]).applyMatrix4(M); pos[k * 3] = vv.x; pos[k * 3 + 1] = vv.y; pos[k * 3 + 2] = vv.z;
          vv.set(v[k * 6 + 3], v[k * 6 + 4], v[k * 6 + 5]).applyMatrix3(Mn).normalize(); nor[k * 3] = vv.x; nor[k * 3 + 1] = vv.y; nor[k * 3 + 2] = vv.z;
        }
        var c = pg.color, nome = "";
        try { var L = api.GetLine(modelo, malha.expressID); nome = (L.Name && L.Name.value) || ""; } catch (e) {}
        aoMalha({ pos: pos, nor: nor, ix: new Uint32Array(ix), cor: [c.x, c.y, c.z, c.w], espaco: espacos.has(malha.expressID), id: malha.expressID, nome: nome });
        geo.delete();
      }
    }
    api.StreamAllMeshes(modelo, receber);
    if (api.StreamAllMeshesWithTypes) api.StreamAllMeshesWithTypes(modelo, [WebIFC.IFCSPACE], receber);
    return espacos;
  }

  /* Carrega o three.js do servidor (pasta /vendor/). Prefere a versão em módulos ES (vendor/three/, three.js 0.170: oclusão de
     ambiente e leitor glTF); se não houver, usa o arquivo único antigo (vendor/three.min.js, 0.160), sem esses dois recursos.
     O importmap só é posto se a página ainda não tiver um. Devolve { THREE, modulos: true|false }. */
  var ADD = null, CARREGANDO = null;
  function carregar(base) {
    base = base || "/vendor/";
    if (CARREGANDO) return CARREGANDO;
    var t = base + "three/three.module.min.js";
    CARREGANDO = (function () {
      if (!g.document.querySelector('script[type="importmap"]')) {
        var im = g.document.createElement("script"); im.type = "importmap";
        im.textContent = JSON.stringify({ imports: { "three": t, "three/addons/": base + "three/addons/" } });
        g.document.head.appendChild(im);
      }
      var imp = function (u) { return import(u); };
      return imp(t).then(function (T) {
        return Promise.all(["postprocessing/EffectComposer.js", "postprocessing/RenderPass.js", "postprocessing/GTAOPass.js",
          "postprocessing/OutputPass.js", "loaders/GLTFLoader.js"].map(function (a) { return imp("three/addons/" + a); }))
          .then(function (m) { ADD = Object.assign({}, m[0], m[1], m[2], m[3], m[4]); g.THREE = T; return { THREE: T, modulos: true }; });
      }).catch(function () {
        if (g.THREE) return { THREE: g.THREE, modulos: false };
        return new Promise(function (ok, er) { var s = g.document.createElement("script"); s.src = base + "three.min.js";
          s.onload = function () { ok({ THREE: g.THREE, modulos: false }); }; s.onerror = function () { CARREGANDO = null; er(new Error("a biblioteca three.js não está no servidor")); };
          g.document.head.appendChild(s); });
      });
    })();
    return CARREGANDO;
  }

  /* glTF/GLB → malhas (com a transformação de cada nó). Precisa do three.js em módulos. Cores devolvidas em sRGB. */
  function malhasDoGLTF(dados, aoMalha) {
    var THREE = g.THREE;
    if (!ADD || !ADD.GLTFLoader) return Promise.reject(new Error("o leitor glTF precisa do three.js em módulos no servidor"));
    return new Promise(function (ok, er) {
      new ADD.GLTFLoader().parse(dados, "", function (gl) {
        var n = 0; gl.scene.updateMatrixWorld(true);
        gl.scene.traverse(function (o) {
          if (!o.isMesh || !o.geometry || !o.geometry.attributes.position) return;
          var geo = o.geometry.clone(); geo.applyMatrix4(o.matrixWorld);
          var mt = Array.isArray(o.material) ? o.material[0] : o.material, c = { r: 0.8, g: 0.8, b: 0.8 };
          if (mt && mt.color) mt.color.getRGB(c, THREE.SRGBColorSpace);
          var ix = geo.index ? new Uint32Array(geo.index.array) : null;
          aoMalha({ pos: new Float32Array(geo.attributes.position.array), nor: geo.attributes.normal ? new Float32Array(geo.attributes.normal.array) : null,
            ix: ix, cor: [c.r, c.g, c.b, mt && mt.opacity != null ? mt.opacity : 1], espaco: false, nome: o.name || "" });
          n++;
        });
        ok(n);
      }, er);
    });
  }

  g.Physis3D = { versao: 2, carregar: carregar, criar: criar, malhasDoIFC: malhasDoIFC, norteDoIFC: norteDoIFC, malhasDoGLTF: malhasDoGLTF, paraGLB: paraGLB,
    modulos: function () { return !!ADD; } };
})(typeof window !== "undefined" ? window : this);
