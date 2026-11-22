/* physis-modelador.js v1 (22/11/2026): bot de modelagem na página inicial de todo projeto com modelagem 3D.
   Pedido em texto (PT/EN) ou imagem/arquivo → modelo gerado LOCALMENTE (sem internet, sempre o mesmo resultado)
   + cálculos preliminares + exportação no formato certo (STL, OBJ, IFC, GeoJSON, CSV).
   Geradores v1: turbina eólica para impressão 3D (Savonius), dutos de ar-condicionado (IFC), chuva no terreno
   (KML/KMZ do Google Earth, GeoJSON, GPX ou área digitada) e relevo a partir de imagem. Pedido que nenhum gerador
   entende vira texto para a caixa de comandos da equipe (fila de pedidos); quando a IA da Physis estiver no servidor,
   ela usa estes mesmos geradores. Premissas e números de regra prática vêm marcados [CONFERIR]: é estimativa
   preliminar, não projeto. Uso: <div data-physis-modelador="modelagem3d"></div>. Original único: sistema/physis-modelador.js. */
(function (w) {
  "use strict";
  var d = w.document;
  function lingua() { try { return (localStorage.getItem("physis-pref-idioma") || localStorage.getItem("physis-idioma") || d.documentElement.lang || "pt").slice(0, 2) === "en" ? "en" : "pt"; } catch (e) { return "pt"; } }
  var TX = {
    pt: { tit: "Bot de modelagem", sub: "Escreva o pedido ou envie uma imagem ou arquivo (KML/KMZ do Google Earth, GeoJSON, GPX; terreno em grade .asc ou XYZ). Exemplos:",
      ex: ["gere uma turbina para impressão 3D de 40 cm", "inclua a previsão de passagem de ar-condicionado numa sala de 60 m²", "mapeie a incidência de chuva no terreno com 1.500 mm/ano", "balanço net zero de uma casa com 450 kWh por mês", "carga térmica NBR 16401 de uma sala de 40 m² com 8 pessoas", "calha e cisterna para telhado de 120 m²", "estufa de 3 x 6 m", "caixa para sensores 10 x 8 x 5 cm", "relevo da imagem com 12 cm"],
      gerar: "Gerar", arquivo: "Imagem ou arquivo", calc: "Cálculos preliminares", baixar: "Baixar", naoEntendi: "Nenhum gerador local entende este pedido ainda. Copie o texto para a caixa de comandos da equipe: ele entra na fila de pedidos e volta como rascunho.",
      copiar: "Copiar pedido", copiado: "Copiado.", aviso: "Estimativa preliminar para conversar e decidir; não substitui projeto assinado. Itens [CONFERIR] são premissas a confirmar.",
      semTerreno: "Para a chuva, envie o contorno do terreno (KML/KMZ do Google Earth, GeoJSON ou GPX) ou escreva a área (ex.: 2.000 m²).",
      lido: "Arquivo lido", pontos: "pontos", sugestoes: "Sugestões" },
    en: { tit: "Modelling bot", sub: "Write the request or upload an image or file (Google Earth KML/KMZ, GeoJSON, GPX; terrain as .asc or XYZ grid). Examples:",
      ex: ["generate a 40 cm wind turbine for 3D printing", "add the air-conditioning duct route for a 60 m² room", "map rainfall on the site with 1,500 mm/year", "net zero balance for a house using 450 kWh per month", "cooling load NBR 16401 for a 40 m² room with 8 people", "gutter and cistern for a 120 m² roof", "greenhouse 3 x 6 m", "sensor case 10 x 8 x 5 cm", "relief from the image, 12 cm"],
      gerar: "Generate", arquivo: "Image or file", calc: "Preliminary calculations", baixar: "Download", naoEntendi: "No local generator understands this request yet. Copy it to the team's command box: it joins the request queue and comes back as a draft.",
      copiar: "Copy request", copiado: "Copied.", aviso: "Preliminary estimate to discuss and decide; it does not replace a signed design. [TO CHECK] items are assumptions to confirm.",
      semTerreno: "For rainfall, upload the site outline (Google Earth KML/KMZ, GeoJSON or GPX) or type the area (e.g., 2,000 m²).",
      lido: "File read", pontos: "points", sugestoes: "Suggestions" }
  };
  // site público (InovaSTEM): sem citar ferramentas internas nem enviar coordenadas a terceiros
  var PUB = {
    pt: { naoEntendi: "Nenhum gerador entende este pedido ainda. Sugira a ideia em Desafios e projetos ou no Fórum: a comunidade e a equipe ajudam a modelar.",
      mais: "Para seguir: use as subabas Modelos BIM (CAD e IFC), Lugar (GIS) e Simulação do laboratório." },
    en: { naoEntendi: "No generator understands this request yet. Suggest the idea in Challenges and projects or in the Forum: the community and the team help model it.",
      mais: "Next: use the lab sub-tabs BIM models (CAD and IFC), Place (GIS) and Simulation." } };
  var CONF = { pt: "[CONFERIR]", en: "[TO CHECK]" };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function num(s) { return parseFloat(String(s).replace(/\.(?=\d{3}\b)/g, "").replace(",", ".")); }
  function fmt(n, k) { return (Math.round(n * Math.pow(10, k || 0)) / Math.pow(10, k || 0)).toLocaleString(lingua() === "en" ? "en-GB" : "pt-BR"); }

  // ------------------------------------------------------------------ geometria básica (triângulos em mm)
  function Malha() { this.t = []; }
  Malha.prototype.tri = function (a, b, c) { this.t.push([a, b, c]); };
  Malha.prototype.quad = function (a, b, c, e) { this.tri(a, b, c); this.tri(a, c, e); };
  Malha.prototype.caixa = function (x0, y0, z0, x1, y1, z1) {
    var p = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], m = this;
    [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]].forEach(function (f) { m.quad(p[f[0]], p[f[1]], p[f[2]], p[f[3]]); });
  };
  Malha.prototype.hexa = function (p) {  // sólido de 8 vértices (0–3 base, 4–7 topo), como a caixa
    var m = this; [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]].forEach(function (f) { m.quad(p[f[0]], p[f[1]], p[f[2]], p[f[3]]); });
  };
  Malha.prototype.cilindro = function (cx, cy, r, z0, z1, n) {  // disco/cilindro fechado
    for (var i = 0; i < n; i++) {
      var a = 2 * Math.PI * i / n, b = i + 1 === n ? 0 : 2 * Math.PI * (i + 1) / n, p0 = [cx + r * Math.cos(a), cy + r * Math.sin(a)], p1 = [cx + r * Math.cos(b), cy + r * Math.sin(b)];
      this.quad([p0[0], p0[1], z0], [p1[0], p1[1], z0], [p1[0], p1[1], z1], [p0[0], p0[1], z1]);
      this.tri([cx, cy, z1], [p0[0], p0[1], z1], [p1[0], p1[1], z1]); this.tri([cx, cy, z0], [p1[0], p1[1], z0], [p0[0], p0[1], z0]);
    }
  };
  Malha.prototype.arco = function (cx, cy, r, e, a0, a1, z0, z1, n) {  // casca de cilindro (pá, tubo, anel) com espessura e: SEMPRE fechada
    var cheio = Math.abs(a1 - a0) >= 2 * Math.PI - 1e-9, rI = r - e, M = this;
    if (!cheio) [a0, a1].forEach(function (a, k) {   // tampas das pontas: sem elas a malha fica com arestas abertas (erro no fatiador)
      var o = [cx + r * Math.cos(a), cy + r * Math.sin(a)], q = [cx + rI * Math.cos(a), cy + rI * Math.sin(a)];
      if (k === 0) M.quad([q[0], q[1], z0], [o[0], o[1], z0], [o[0], o[1], z1], [q[0], q[1], z1]);
      else M.quad([o[0], o[1], z0], [q[0], q[1], z0], [q[0], q[1], z1], [o[0], o[1], z1]);
    });
    for (var i = 0; i < n; i++) {
      var a = a0 + (a1 - a0) * i / n, b = cheio && i + 1 === n ? a0 : a0 + (a1 - a0) * (i + 1) / n, ri = r - e;
      var o0 = [cx + r * Math.cos(a), cy + r * Math.sin(a)], o1 = [cx + r * Math.cos(b), cy + r * Math.sin(b)], i0 = [cx + ri * Math.cos(a), cy + ri * Math.sin(a)], i1 = [cx + ri * Math.cos(b), cy + ri * Math.sin(b)];
      this.quad([o0[0], o0[1], z0], [o1[0], o1[1], z0], [o1[0], o1[1], z1], [o0[0], o0[1], z1]);
      this.quad([i1[0], i1[1], z0], [i0[0], i0[1], z0], [i0[0], i0[1], z1], [i1[0], i1[1], z1]);
      this.quad([o0[0], o0[1], z1], [o1[0], o1[1], z1], [i1[0], i1[1], z1], [i0[0], i0[1], z1]);
      this.quad([i0[0], i0[1], z0], [i1[0], i1[1], z0], [o1[0], o1[1], z0], [o0[0], o0[1], z0]);
    }
  };
  Malha.prototype.anelRet = function (x0, y0, x1, y1, e, z0, z1) {  // moldura retangular fechada (sólido único)
    var o = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], i = [[x0 + e, y0 + e], [x1 - e, y0 + e], [x1 - e, y1 - e], [x0 + e, y1 - e]], M = this;
    for (var k = 0; k < 4; k++) { var q = (k + 1) % 4;
      M.quad([o[k][0], o[k][1], z0], [o[q][0], o[q][1], z0], [o[q][0], o[q][1], z1], [o[k][0], o[k][1], z1]);
      M.quad([i[q][0], i[q][1], z0], [i[k][0], i[k][1], z0], [i[k][0], i[k][1], z1], [i[q][0], i[q][1], z1]);
      M.quad([o[k][0], o[k][1], z1], [o[q][0], o[q][1], z1], [i[q][0], i[q][1], z1], [i[k][0], i[k][1], z1]);
      M.quad([i[k][0], i[k][1], z0], [i[q][0], i[q][1], z0], [o[q][0], o[q][1], z0], [o[k][0], o[k][1], z0]); }
  };
  Malha.prototype.caixaOca = function (X, Y, Z, e) {  // caixa aberta em cima: fundo + paredes num sólido único, sem arestas compartilhadas
    var o = [[0, 0], [X, 0], [X, Y], [0, Y]], i = [[e, e], [X - e, e], [X - e, Y - e], [e, Y - e]], M = this;
    M.quad([0, 0, 0], [0, Y, 0], [X, Y, 0], [X, 0, 0]);                       // fundo por fora
    M.quad([e, e, e], [X - e, e, e], [X - e, Y - e, e], [e, Y - e, e]);         // fundo por dentro
    for (var k = 0; k < 4; k++) { var q = (k + 1) % 4;
      M.quad([o[k][0], o[k][1], 0], [o[q][0], o[q][1], 0], [o[q][0], o[q][1], Z], [o[k][0], o[k][1], Z]);
      M.quad([i[q][0], i[q][1], e], [i[k][0], i[k][1], e], [i[k][0], i[k][1], Z], [i[q][0], i[q][1], Z]);
      M.quad([o[k][0], o[k][1], Z], [o[q][0], o[q][1], Z], [i[q][0], i[q][1], Z], [i[k][0], i[k][1], Z]); }
  };
  function stl(m, nome) {  // STL binário
    var n = m.t.length, buf = new ArrayBuffer(84 + 50 * n), dv = new DataView(buf), o = 84;
    dv.setUint32(80, n, true);
    m.t.forEach(function (t) {
      var u = [t[1][0] - t[0][0], t[1][1] - t[0][1], t[1][2] - t[0][2]], v = [t[2][0] - t[0][0], t[2][1] - t[0][1], t[2][2] - t[0][2]];
      var nx = u[1] * v[2] - u[2] * v[1], ny = u[2] * v[0] - u[0] * v[2], nz = u[0] * v[1] - u[1] * v[0], l = Math.hypot(nx, ny, nz) || 1;
      [nx / l, ny / l, nz / l].concat(t[0], t[1], t[2]).forEach(function (x, k) { dv.setFloat32(o + 4 * k, x, true); });
      o += 50;
    });
    return new Blob([buf], { type: "model/stl" });
  }
  function obj(m) {
    var s = "# Physis · modelador\n", k = 1;
    m.t.forEach(function (t) { t.forEach(function (p) { s += "v " + p[0].toFixed(3) + " " + p[1].toFixed(3) + " " + p[2].toFixed(3) + "\n"; }); s += "f " + k + " " + (k + 1) + " " + (k + 2) + "\n"; k += 3; });
    return new Blob([s], { type: "text/plain" });
  }
  function checar(m) {  // malha fechada: cada aresta usada por exatamente 2 triângulos (o que os fatiadores acusam como problema de "arestas")
    var f = function (v) { return (Math.round(v * 1000) / 1000 + 0).toFixed(3); }, k = function (p) { return f(p[0]) + "," + f(p[1]) + "," + f(p[2]); }, E = {};
    m.t.forEach(function (t) { for (var i = 0; i < 3; i++) { var a = k(t[i]), b = k(t[(i + 1) % 3]), e = a < b ? a + "|" + b : b + "|" + a; E[e] = (E[e] || 0) + 1; } });
    var abertas = 0, mais = 0; Object.keys(E).forEach(function (e) { if (E[e] === 1) abertas++; else if (E[e] > 2) mais++; });
    return { abertas: abertas, nao_manifold: mais, ok: abertas === 0 && mais === 0 };
  }
  function bico(x, min) { return Math.max(min || 1.2, Math.ceil(x / 0.4 - 1e-9) * 0.4); }  // espessura em múltiplos do bico de 0,4 mm
  function volume(m) { var v = 0; m.t.forEach(function (t) { var a = t[0], b = t[1], c = t[2]; v += (a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6; }); return Math.abs(v); }
  function caixaDe(m) { var lo = [1e9, 1e9, 1e9], hi = [-1e9, -1e9, -1e9]; m.t.forEach(function (t) { t.forEach(function (p) { for (var i = 0; i < 3; i++) { lo[i] = Math.min(lo[i], p[i]); hi[i] = Math.max(hi[i], p[i]); } }); }); return [hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]]; }

  // ------------------------------------------------------------------ IFC4 mínimo (STEP), com elementos extrudados
  function ifc(nome, elementos) {
    var L = [], id = 0, ag = Date.now().toString(36).toUpperCase();
    function e(s) { id += 1; L.push("#" + id + "=" + s + ";"); return "#" + id; }
    function g() { var c = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$", s = ""; for (var i = 0; i < 22; i++) s += c[Math.floor(Math.random() * 64)]; return "'" + s + "'"; }
    var pessoa = e("IFCPERSON($,'Physis',$,$,$,$,$,$)"), org = e("IFCORGANIZATION($,'Physis Engineering',$,$,$)"), po = e("IFCPERSONANDORGANIZATION(" + pessoa + "," + org + ",$)");
    var app = e("IFCAPPLICATION(" + org + ",'1','Physis modelador','physis-modelador')"), dono = e("IFCOWNERHISTORY(" + po + "," + app + ",$,.ADDED.,$,$,$," + Math.floor(Date.now() / 1000) + ")");
    var orig = e("IFCCARTESIANPOINT((0.,0.,0.))"), eixo = e("IFCAXIS2PLACEMENT3D(" + orig + ",$,$)"), ctx = e("IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05," + eixo + ",$)");
    var um = e("IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.)"), un = e("IFCUNITASSIGNMENT((" + um + "))");
    var proj = e("IFCPROJECT(" + g() + "," + dono + ",'" + nome.replace(/'/g, "") + "',$,$,$,$,(" + ctx + ")," + un + ")");
    var lp = e("IFCLOCALPLACEMENT($," + eixo + ")"), site = e("IFCSITE(" + g() + "," + dono + ",'Terreno',$,$," + lp + ",$,$,.ELEMENT.,$,$,$,$,$)");
    var bld = e("IFCBUILDING(" + g() + "," + dono + ",'Edificação',$,$," + lp + ",$,$,.ELEMENT.,$,$,$)"), sto = e("IFCBUILDINGSTOREY(" + g() + "," + dono + ",'Pavimento',$,$," + lp + ",$,$,.ELEMENT.,0.)");
    e("IFCRELAGGREGATES(" + g() + "," + dono + ",$,$," + proj + ",(" + site + "))"); e("IFCRELAGGREGATES(" + g() + "," + dono + ",$,$," + site + ",(" + bld + "))"); e("IFCRELAGGREGATES(" + g() + "," + dono + ",$,$," + bld + ",(" + sto + "))");
    var filhos = [];
    elementos.forEach(function (el) {  // el: {tipo:'IFCDUCTSEGMENT'|..., nome, x,y,z (mm), dx,dy (perfil), comp (mm), dir:[x,y,z]}
      var p = e("IFCCARTESIANPOINT((" + el.x.toFixed(1) + "," + el.y.toFixed(1) + "," + el.z.toFixed(1) + "))"), dz = e("IFCDIRECTION((" + el.dir.join(",") + "))");
      var ref = e("IFCDIRECTION((" + (Math.abs(el.dir[2]) > 0.9 ? "1.,0.,0." : "0.,0.,1.") + "))");
      var pl = e("IFCLOCALPLACEMENT(" + lp + "," + e("IFCAXIS2PLACEMENT3D(" + p + "," + dz + "," + ref + ")") + ")");
      var perfil = e("IFCRECTANGLEPROFILEDEF(.AREA.,$," + e("IFCAXIS2PLACEMENT2D(" + e("IFCCARTESIANPOINT((0.,0.))") + ",$)") + "," + el.dx.toFixed(1) + "," + el.dy.toFixed(1) + ")");
      var solido = e("IFCEXTRUDEDAREASOLID(" + perfil + "," + eixo + "," + e("IFCDIRECTION((0.,0.,1.))") + "," + el.comp.toFixed(1) + ")");
      var forma = e("IFCPRODUCTDEFINITIONSHAPE($,$,(" + e("IFCSHAPEREPRESENTATION(" + ctx + ",'Body','SweptSolid',(" + solido + "))") + "))");
      filhos.push(e(el.tipo + "(" + g() + "," + dono + ",'" + el.nome.replace(/'/g, "") + "',$,$," + pl + "," + forma + ",$,$)"));
    });
    if (filhos.length) e("IFCRELCONTAINEDINSPATIALSTRUCTURE(" + g() + "," + dono + ",$,$,(" + filhos.join(",") + ")," + sto + ")");
    var cab = "ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('ViewDefinition [ReferenceView]'),'2;1');\nFILE_NAME('" + nome.replace(/'/g, "") + ".ifc','" + new Date().toISOString().slice(0, 19) + "',('Physis'),('Physis Engineering'),'physis-modelador','Physis','');\nFILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\n";
    return new Blob([cab + L.join("\n") + "\nENDSEC;\nEND-ISO-10303-21;\n"], { type: "application/x-step" });
  }

  // ------------------------------------------------------------------ leitura de arquivos geográficos (Google Earth e similares)
  function lerKML(txt) {
    var xml = new DOMParser().parseFromString(txt, "application/xml"), cs = xml.getElementsByTagName("coordinates"), pts = [];
    for (var i = 0; i < cs.length; i++) cs[i].textContent.trim().split(/\s+/).forEach(function (c) { var p = c.split(",").map(Number); if (p.length >= 2 && isFinite(p[0])) pts.push([p[0], p[1]]); });
    return pts;
  }
  function lerGPX(txt) {
    var xml = new DOMParser().parseFromString(txt, "application/xml"), pts = [];
    ["trkpt", "rtept", "wpt"].forEach(function (t) { var n = xml.getElementsByTagName(t); for (var i = 0; i < n.length; i++) pts.push([+n[i].getAttribute("lon"), +n[i].getAttribute("lat")]); });
    return pts;
  }
  function lerGeoJSON(o) {
    var pts = [];
    (function andar(c) { if (typeof c[0] === "number") pts.push([c[0], c[1]]); else c.forEach(andar); })(
      (o.features ? o.features : [o]).map(function (f) { return (f.geometry || f).coordinates; }));
    return pts;
  }
  function areaM2(pts) {  // polígono lon/lat → m² (projeção local equiretangular; erro pequeno em terrenos)
    if (pts.length < 3) return 0;
    var lat0 = pts.reduce(function (s, p) { return s + p[1]; }, 0) / pts.length, kx = 111320 * Math.cos(lat0 * Math.PI / 180), ky = 110574, a = 0;
    for (var i = 0; i < pts.length; i++) { var p = pts[i], q = pts[(i + 1) % pts.length]; a += (p[0] * kx) * (q[1] * ky) - (q[0] * kx) * (p[1] * ky); }
    return Math.abs(a) / 2;
  }

  // ------------------------------------------------------------------ geradores
  function gTurbina(txt, L) {
    // Feita para imprimir SEM SUPORTE e com pouco filamento: cada seção (até 200 mm) é um disco apoiado na mesa com as pás e o
    // cubo subindo na vertical; a tampa de cima é um disco à parte. Tudo monta num eixo roscado M8 com porcas (encaixe e aperto).
    var m = txt.match(/(\d+[.,]?\d*)\s*(cm|mm|m)\b/i), alt = m ? num(m[1]) * ({ cm: 10, mm: 1, m: 1000 })[m[2].toLowerCase()] : 400;
    var vel = (txt.match(/(\d+[.,]?\d*)\s*m\/s/i) || [])[1], v = vel ? num(vel) : 5, MAX = 200;
    var D = Math.min(alt * 0.5, MAX - 12), r = D / 4, e = bico(D / 110, 1.6), ch = bico(alt / 120, 2.4), R = D / 2 + 4, furo = 4.3, cubo = bico(4.3 + 2.4, 6.8);
    var nSec = Math.max(1, Math.ceil(alt / MAX)), hs = alt / nSec, partes = [], M = new Malha();
    function secao(z0) {  // disco-base (anel com furo do eixo) + 2 pás em S + cubo; nada fica no ar
      var p = new Malha();
      p.arco(0, 0, R, R - furo, 0, 2 * Math.PI, z0, z0 + ch, 72);
      p.arco(-r + 1.5 * e, 0, r, e, 0, Math.PI, z0 + ch, z0 + hs, 48); p.arco(r - 1.5 * e, 0, r, e, Math.PI, 2 * Math.PI, z0 + ch, z0 + hs, 48);  // pontas afastadas: nenhuma aresta dividida por 4 faces
      p.arco(0, 0, cubo, cubo - furo, 0, 2 * Math.PI, z0 + ch, z0 + hs, 32);
      return p;
    }
    for (var k = 0; k < nSec; k++) { var p = secao(0); partes.push({ nome: "secao_" + (k + 1), malha: p }); secao(k * (hs + 8)).t.forEach(function (t) { M.t.push(t); }); }
    var tampa = new Malha(); tampa.arco(0, 0, R, R - furo, 0, 2 * Math.PI, 0, ch, 72); partes.push({ nome: "tampa", malha: tampa });
    tampa.t.forEach(function (t) { M.t.push(t.map(function (q) { return [q[0], q[1], q[2] + nSec * (hs + 8)]; })); });
    var Am = (D / 1000) * (alt / 1000), cp = 0.15, P = 0.5 * 1.225 * Am * Math.pow(v, 3) * cp, vol = 0, ok = true, ab = 0;
    partes.forEach(function (q) { vol += volume(q.malha) / 1000; var c = checar(q.malha); ok = ok && c.ok; ab += c.abertas; });
    var calc = [
      [L === "en" ? "Type" : "Tipo", "Savonius (S) · " + nSec + (L === "en" ? " section(s) of " : " seção(ões) de ") + fmt(hs, 0) + " mm + " + (L === "en" ? "top disc" : "tampa")],
      [L === "en" ? "Height × diameter" : "Altura × diâmetro", fmt(alt / 10, 1) + " × " + fmt(D / 10, 1) + " cm" + (D < alt * 0.5 ? " (" + (L === "en" ? "diameter limited to the 200 mm bed" : "diâmetro limitado à mesa de 200 mm") + ")" : "")],
      [L === "en" ? "Swept area" : "Área varrida", fmt(Am, 3) + " m²"],
      [L === "en" ? "Power at " : "Potência a ", fmt(v, 1) + " m/s, Cp " + cp + " " + CONF[L] + ": " + fmt(P, 2) + " W"],
      [L === "en" ? "Print without supports" : "Impressão sem suporte", (L === "en" ? "yes: each part lies flat on its disc, walls vertical, nothing floating" : "sim: cada peça apoia no próprio disco, paredes verticais, nada no ar")],
      [L === "en" ? "Closed mesh (no open edges)" : "Malha fechada (sem arestas abertas)", ok ? (L === "en" ? "yes" : "sim") : (L === "en" ? "no: " : "não: ") + ab],
      [L === "en" ? "Walls / discs" : "Paredes / discos", fmt(e, 1) + " / " + fmt(ch, 1) + " mm (" + (L === "en" ? "multiples of the 0.4 mm nozzle" : "múltiplos do bico de 0,4 mm") + ")"],
      [L === "en" ? "Filament (approx.)" : "Filamento (aprox.)", fmt(vol, 0) + " cm³ " + (L === "en" ? "of walls" : "de paredes") + " · PLA ≈ " + fmt(vol * 1.24, 0) + " g " + CONF[L] + " · " + (L === "en" ? "3 perimeters, 15% gyroid" : "3 perímetros, giroide 15%")],
      [L === "en" ? "Assembly" : "Montagem", (L === "en" ? "M8 threaded rod " : "barra roscada M8 de ") + fmt(alt + 40, 0) + " mm + " + (2 * nSec + 2) + (L === "en" ? " M8 nuts/washers; hole Ø " : " porcas/arruelas M8; furo Ø ") + fmt(furo * 2, 1) + " mm (+0,6 mm " + (L === "en" ? "clearance" : "de folga") + ")"]];
    return { nome: "turbina_savonius_" + Math.round(alt / 10) + "cm", malha: M, partes: partes, calc: calc, formatos: ["stl", "obj"],
      sugestoes: L === "en" ? ["Align the sections by the blades before tightening; a drop of glue (CA) between discs adds stiffness.", "Outdoors: PETG or ASA; add a 608 bearing at the base.", "Measure wind on site before choosing the generator."]
        : ["Alinhar as seções pelas pás antes de apertar; uma gota de cola (cianoacrilato) entre discos dá mais rigidez.", "Uso externo: PETG ou ASA; rolamento 608 na base.", "Medir o vento no local antes de escolher o gerador."] };
  }
  function gDutos(txt, L, trCalc) {
    var a = (txt.match(/(\d+[.,]?\d*)\s*m²|(\d+[.,]?\d*)\s*m2/i) || []), area = a[1] ? num(a[1]) : a[2] ? num(a[2]) : 40;
    var pe = (txt.match(/p[eé][- ]?direito\s*(?:de\s*)?(\d+[.,]?\d*)/i) || [])[1], h = pe ? num(pe) : 2.8;
    var lado = Math.sqrt(area), btu = area * 600, tr = trCalc || btu / 12000, q = tr * 400 * 1.699, vAr = 4, secao = q / 3600 / vAr, w = Math.sqrt(secao * 2), hd = secao / w;
    var L1 = lado * 1000, z = (h - 0.25) * 1000, els = [{ tipo: "IFCDUCTSEGMENT", nome: "Duto tronco " + Math.round(w * 1000) + "x" + Math.round(hd * 1000), x: 0, y: L1 / 2, z: z, dx: w * 1000, dy: hd * 1000, comp: L1, dir: [1, 0, 0] }];
    var nBocas = Math.max(2, Math.round(area / 15));
    for (var i = 0; i < nBocas; i++) els.push({ tipo: "IFCAIRTERMINAL", nome: "Difusor " + (i + 1), x: L1 * (i + 0.5) / nBocas, y: L1 / 2, z: z - 150, dx: 300, dy: 300, comp: 150, dir: [0, 0, 1] });
    var M = new Malha(); M.caixa(0, L1 / 2 - w * 500, z - hd * 1000, L1, L1 / 2 + w * 500, z);
    els.slice(1).forEach(function (el) { M.caixa(el.x - 150, el.y - 150, el.z - 150, el.x + 150, el.y + 150, el.z); });
    var calc = [
      [L === "en" ? "Room" : "Ambiente", fmt(area, 1) + " m² · " + (L === "en" ? "ceiling " : "pé-direito ") + fmt(h, 2) + " m"],
      [L === "en" ? "Cooling load (rule of thumb)" : "Carga térmica (regra prática)", fmt(btu, 0) + " BTU/h ≈ " + fmt(tr, 2) + " TR (600 BTU/h·m²) " + CONF[L]],
      [L === "en" ? "Air flow" : "Vazão de ar", fmt(q, 0) + " m³/h (400 cfm/TR) " + CONF[L]],
      [L === "en" ? "Trunk duct at 4 m/s" : "Duto tronco a 4 m/s", fmt(w * 1000, 0) + " × " + fmt(hd * 1000, 0) + " mm (" + fmt(secao, 3) + " m²)"],
      [L === "en" ? "Diffusers" : "Difusores", nBocas + " × 300 × 300 mm"]];
    return { nome: "dutos_ac_" + Math.round(area) + "m2", malha: M, ifc: els, calc: calc, formatos: ["ifc", "stl"],
      sugestoes: L === "en" ? ["Replace the rule of thumb with the HVAC module's load calculation (NBR 16401) before sizing.", "Import the building IFC in the BIM design module to route the duct through the real rooms."]
        : ["Trocar a regra prática pelo cálculo de carga do módulo AVAC (NBR 16401) antes de dimensionar.", "Importar o IFC da edificação no módulo de projeto BIM para passar o duto pelos ambientes reais."] };
  }
  function gChuva(txt, L, geo) {
    var mm = (txt.match(/(\d[\d.,]*)\s*mm/i) || [])[1], P = mm ? num(mm) : NaN, a = (txt.match(/(\d[\d.,]*)\s*m²|(\d[\d.,]*)\s*m2/i) || []);
    var area = geo && geo.pts.length >= 3 ? areaM2(geo.pts) : a[1] ? num(a[1]) : a[2] ? num(a[2]) : 0;
    if (!area) return { erro: TX[L].semTerreno };
    var c = /telhado|cobertura|roof/i.test(txt) ? 0.8 : /grama|gramado|vegeta|lawn|grass/i.test(txt) ? 0.3 : 0.5, chuvaMM = isFinite(P) ? P : 1500;
    var vol = area * chuvaMM / 1000 * c, M = new Malha(), lado = Math.sqrt(area) * 1000; M.caixa(0, 0, 0, lado, lado, 200);
    var calc = [[L === "en" ? "Site area" : "Área do terreno", fmt(area, 0) + " m²" + (geo ? " (" + esc(geo.nome) + ", " + geo.pts.length + " " + TX[L].pontos + ")" : "")],
      [L === "en" ? "Annual rainfall" : "Chuva anual", fmt(chuvaMM, 0) + " mm" + (isFinite(P) ? "" : " " + CONF[L] + (L === "en" ? " (use INMET/CHIRPS for the site)" : " (usar INMET/CHIRPS do local)"))],
      [L === "en" ? "Runoff coefficient" : "Coeficiente de escoamento", c + " " + CONF[L]],
      [L === "en" ? "Water falling and running off per year" : "Água que cai e escoa por ano", fmt(area * chuvaMM / 1000, 0) + " m³ · " + fmt(vol, 0) + " m³ " + (L === "en" ? "runoff" : "escoados")],
      [L === "en" ? "Cistern for 30 days of rain (approx.)" : "Cisterna para 30 dias de chuva (aprox.)", fmt(vol / 12, 1) + " m³ " + CONF[L]]];
    var gj = { type: "FeatureCollection", features: [{ type: "Feature", properties: { area_m2: Math.round(area), chuva_mm_ano: chuvaMM, coef_escoamento: c, escoamento_m3_ano: Math.round(vol), fonte: "Physis modelador (estimativa preliminar)" },
      geometry: geo && geo.pts.length >= 3 ? { type: "Polygon", coordinates: [geo.pts.concat([geo.pts[0]])] } : null }] };
    return { nome: "chuva_terreno", malha: M, geojson: gj, calc: calc, formatos: ["geojson", "csv", "stl"],
      sugestoes: L === "en" ? ["With a terrain model (DEM/GeoTIFF or contour lines) the bot will map slope and flow direction.", "Cross with the planned roofs to size gutters (NBR 10844)."]
        : ["Com o modelo do terreno (MDT/GeoTIFF ou curvas de nível), o bot passa a mapear declividade e direção do escoamento.", "Cruzar com os telhados previstos para dimensionar calhas (NBR 10844)."] };
  }
  function gRelevo(txt, L, img) {
    var m = txt.match(/(\d+[.,]?\d*)\s*(cm|mm)\b/i), larg = m ? num(m[1]) * (m[2].toLowerCase() === "cm" ? 10 : 1) : 100, n = 120;
    var cv = d.createElement("canvas"), r = img.height / img.width, nx = n, ny = Math.max(2, Math.round(n * r)); cv.width = nx; cv.height = ny;
    var c = cv.getContext("2d"); c.drawImage(img, 0, 0, nx, ny); var px = c.getImageData(0, 0, nx, ny).data, H = [], hmax = 4, base = 1.2, s = larg / (nx - 1);
    for (var j = 0; j < ny; j++) { H.push([]); for (var i = 0; i < nx; i++) { var k = 4 * (j * nx + i); H[j].push(base + hmax * (1 - (0.3 * px[k] + 0.59 * px[k + 1] + 0.11 * px[k + 2]) / 255)); } }
    var M = new Malha();
    for (j = 0; j < ny - 1; j++) for (i = 0; i < nx - 1; i++) {
      var p = function (a, b, z) { return [a * s, b * s, z]; };
      M.quad(p(i, j, H[j][i]), p(i + 1, j, H[j][i + 1]), p(i + 1, j + 1, H[j + 1][i + 1]), p(i, j + 1, H[j + 1][i]));
      M.quad(p(i, j, 0), p(i, j + 1, 0), p(i + 1, j + 1, 0), p(i + 1, j, 0));
    }
    for (i = 0; i < nx - 1; i++) { M.quad([i * s, 0, 0], [(i + 1) * s, 0, 0], [(i + 1) * s, 0, H[0][i + 1]], [i * s, 0, H[0][i]]); M.quad([(i + 1) * s, (ny - 1) * s, 0], [i * s, (ny - 1) * s, 0], [i * s, (ny - 1) * s, H[ny - 1][i]], [(i + 1) * s, (ny - 1) * s, H[ny - 1][i + 1]]); }
    for (j = 0; j < ny - 1; j++) { M.quad([0, (j + 1) * s, 0], [0, j * s, 0], [0, j * s, H[j][0]], [0, (j + 1) * s, H[j + 1][0]]); M.quad([(nx - 1) * s, j * s, 0], [(nx - 1) * s, (j + 1) * s, 0], [(nx - 1) * s, (j + 1) * s, H[j + 1][nx - 1]], [(nx - 1) * s, j * s, H[j][nx - 1]]); }
    var calc = [[L === "en" ? "Size" : "Tamanho", fmt(larg / 10, 1) + " × " + fmt(larg * r / 10, 1) + " cm, " + (L === "en" ? "relief up to " : "relevo até ") + (base + hmax) + " mm"],
      [L === "en" ? "Volume (approx.)" : "Volume (aprox.)", fmt(volume(M) / 1000, 1) + " cm³"]];
    return { nome: "relevo_imagem", malha: M, calc: calc, formatos: ["stl", "obj"],
      sugestoes: L === "en" ? ["Photo → full 3D object (several photos around it): use Physis 3D on the InovaSTEM platform or a 3D scanning app."] : ["Foto → objeto 3D completo (várias fotos ao redor): usar a Physis 3D da plataforma InovaSTEM ou um aplicativo de escaneamento 3D."] };
  }
  // ------------------------------------------------------------------ v2 (22/11/2026): net zero, água, estufa, caixa, terreno real, AVAC NBR 16401
  function pr(id, d) { try { var v = w.PhysisCalc && w.PhysisCalc.premissa(id); return typeof v === "number" ? v : d; } catch (e) { return d; } }
  function centro(geo) { if (!geo || !geo.pts.length) return null; var x = 0, y = 0; geo.pts.forEach(function (p) { x += p[0]; y += p[1]; }); return [x / geo.pts.length, y / geo.pts.length]; }
  function achar(txt, rx, d) { var m = txt.match(rx); return m ? num(m[1]) : d; }
  function placas(M, n, lat, x0, y0) {  // fileiras de módulos 1,13 × 2,28 m inclinados na latitude (mm)
    var inc = Math.min(35, Math.max(10, Math.abs(lat))) * Math.PI / 180, a = 1134, b = 2279, porF = Math.ceil(Math.sqrt(n * 2)), k = 0;
    for (var i = 0; k < n; i++) for (var j = 0; j < porF && k < n; j++, k++) {
      var x = x0 + j * (a + 20), y = y0 + i * (b * Math.cos(inc) + 900), h = b * Math.sin(inc);
      var yb = y + b * Math.cos(inc); M.hexa([[x, y, 265], [x + a, y, 265], [x + a, yb, 265 + h], [x, yb, 265 + h], [x, y, 300], [x + a, y, 300], [x + a, yb, 300 + h], [x, yb, 300 + h]]);  // módulo com 35 mm de espessura
      M.caixa(x + 40, y + b * Math.cos(inc) - 60, 0, x + 100, y + b * Math.cos(inc), 300 + h); M.caixa(x + a - 100, y + b * Math.cos(inc) - 60, 0, x + a - 40, y + b * Math.cos(inc), 300 + h);
    }
  }
  function gNetZero(txt, L, geo) {
    var c = centro(geo), lat = c ? c[1] : -22.5, kwh = achar(txt, /(\d[\d.,]*)\s*kwh/i, NaN), area = achar(txt, /(\d[\d.,]*)\s*m(?:²|2)/i, geo && geo.pts.length >= 3 ? areaM2(geo.pts) : 150);
    var cons = isFinite(kwh) ? kwh : area * 30 / 12, hsp = achar(txt, /(\d[\d.,]*)\s*(?:hsp|kwh\/m²·dia|h de sol)/i, 4.5), PR = pr("pv.pr", 0.78), fe = pr("rede.fator_emissao", 0.0289);
    var kwp = cons * 12 / (hsp * 365 * PR), wp = 550, n = Math.max(1, Math.ceil(kwp * 1000 / wp)), ger = n * wp / 1000 * hsp * 365 * PR, co2 = ger / 1000 * fe;
    var chuva = achar(txt, /(\d[\d.,]*)\s*mm/i, 1500), telh = achar(txt, /telhado\s*(?:de\s*)?(\d[\d.,]*)/i, area), agua = telh * chuva / 1000 * pr("chuva.coef_escoamento", 0.8);
    var M = new Malha(); placas(M, Math.min(n, 60), lat, 0, 0);
    var calc = [
      [L === "en" ? "Consumption" : "Consumo", fmt(cons, 0) + " kWh/" + (L === "en" ? "month" : "mês") + (isFinite(kwh) ? "" : " (" + fmt(area, 0) + " m² × 30 kWh/m²·" + (L === "en" ? "year" : "ano") + " " + CONF[L] + ")")],
      [L === "en" ? "Solar for net zero energy" : "Solar para energia net zero", fmt(kwp, 2) + " kWp · " + n + " × " + wp + " Wp " + CONF[L] + " · HSP " + fmt(hsp, 1) + (L === "en" ? " h " : " h ") + CONF[L] + " · PR " + PR],
      [L === "en" ? "Generation / roof area" : "Geração / área de telhado", fmt(ger, 0) + " kWh/" + (L === "en" ? "year" : "ano") + " · ≈ " + fmt(n * 2.6, 0) + " m² " + (L === "en" ? "of modules" : "de módulos")],
      [L === "en" ? "Avoided emissions" : "Emissões evitadas", fmt(co2, 2) + " tCO₂/" + (L === "en" ? "year" : "ano") + " (" + fe + " tCO₂/MWh, " + (L === "en" ? "grid factor" : "fator da rede") + " " + CONF[L] + ")"],
      [L === "en" ? "Rainwater from the roof" : "Água de chuva do telhado", fmt(agua, 0) + " m³/" + (L === "en" ? "year" : "ano") + " (" + fmt(telh, 0) + " m², " + fmt(chuva, 0) + " mm)"],
      [L === "en" ? "Tilt / latitude" : "Inclinação / latitude", fmt(Math.min(35, Math.max(10, Math.abs(lat))), 0) + "° · " + fmt(lat, 3) + (c ? "" : " " + CONF[L])]];
    return { nome: "net_zero_" + Math.round(cons) + "kwh", malha: M, calc: calc, formatos: ["stl", "obj", "csv"],
      sugestoes: L === "en" ? ["Confirm HSP with a solar map (pvlib) for the exact site and shading.", "Add batteries or biogas only if the goal includes resilience (off-grid hours).", "Enter the 12 bills to replace the estimated consumption."]
        : ["Confirmar a HSP com um mapa solar (pvlib) para o local e o sombreamento exatos.", "Somar baterias ou biogás só se a meta incluir resiliência (horas sem rede).", "Informar as 12 contas de luz para trocar o consumo estimado."] };
  }
  function gAgua(txt, L) {
    var A = achar(txt, /(\d[\d.,]*)\s*m(?:²|2)/i, 120), I = achar(txt, /(\d[\d.,]*)\s*mm\/h/i, 150), chuva = achar(txt, /(\d[\d.,]*)\s*mm(?!\/)/i, 1500), C = pr("chuva.coef_escoamento", 0.8);
    // NBR 10844, calha semicircular, n 0,011, declividade 0,5%: capacidade por diâmetro (L/min)
    var TAB = [[100, 130], [125, 236], [150, 384], [200, 829]], Q = I * A / 60, nq = 1, larg;
    while (Q / nq > TAB[TAB.length - 1][1]) nq++;
    larg = (TAB.filter(function (t) { return t[1] >= Q / nq; })[0] || TAB[TAB.length - 1])[0];
    var cist = A * chuva / 1000 * C / 12 * 1.5;
    var M = new Malha(), Lm = Math.sqrt(A) * 1000; M.caixa(0, 0, 0, Lm, larg, larg * 0.6); M.cilindro(Lm + 1500, 0, Math.sqrt(cist / Math.PI / 2) * 1000, 0, 2000, 48);
    var calc = [[L === "en" ? "Roof" : "Telhado", fmt(A, 0) + " m²"],
      [L === "en" ? "Design flow (NBR 10844)" : "Vazão de projeto (NBR 10844)", fmt(Q, 1) + " L/min · I = " + fmt(I, 0) + " mm/h " + CONF[L]],
      [L === "en" ? "Gutters / downpipes" : "Calhas / condutores", nq + " × " + (L === "en" ? "semicircular gutter Ø " : "calha semicircular Ø ") + larg + " mm (0,5%) · " + (L === "en" ? "downpipe Ø min. " : "condutor Ø mín. ") + pr("drenagem.condutor_diam_min", 70) + " mm " + CONF[L]],
      [L === "en" ? "Cistern (1.5 month of runoff)" : "Cisterna (1,5 mês de escoamento)", fmt(cist, 1) + " m³ " + CONF[L] + " · " + (L === "en" ? "first flush " : "descarte inicial ") + pr("chuva.descarte_inicial", 2) + " mm"]];
    return { nome: "calha_cisterna_" + Math.round(A) + "m2", malha: M, calc: calc, formatos: ["stl", "csv"],
      sugestoes: L === "en" ? ["Size month by month with the platform's cistern calculation (NBR 15527) and real demand."] : ["Dimensionar mês a mês com a conta de cisterna da plataforma (NBR 15527) e a demanda real."] };
  }
  function gEstufa(txt, L) {
    var m = txt.match(/(\d+[.,]?\d*)\s*[x×]\s*(\d+[.,]?\d*)\s*m/i), a = m ? num(m[1]) : 3, b = m ? num(m[2]) : 6, h = achar(txt, /altura\s*(?:de\s*)?(\d+[.,]?\d*)/i, 2.4), M = new Malha();
    var arcos = Math.max(2, Math.round(b / 1.2) + 1);
    for (var k = 0; k < arcos; k++) { var y = b * 1000 * k / (arcos - 1); M.arco(a * 500, y, a * 500, 30, 0, Math.PI, 0, 30, 24); }
    M.caixa(0, 0, 0, a * 1000, 40, 300); M.caixa(0, b * 1000 - 40, 0, a * 1000, b * 1000, 300);
    var vent = a * b * 0.2, calc = [[L === "en" ? "Floor / growing area" : "Piso / área de cultivo", fmt(a * b, 1) + " m² · " + fmt(a * b * 0.7, 1) + " m² " + (L === "en" ? "beds" : "de canteiros") + " " + CONF[L]],
      [L === "en" ? "Hoops" : "Arcos", arcos + " × " + (L === "en" ? "every " : "a cada ") + fmt(b / (arcos - 1), 2) + " m"],
      [L === "en" ? "Natural ventilation" : "Ventilação natural", "≥ " + fmt(vent, 1) + " m² (20% " + (L === "en" ? "of floor" : "do piso") + ") " + CONF[L]],
      [L === "en" ? "Rainwater from the cover" : "Água de chuva da cobertura", fmt(a * b * 1.5 * 0.8, 1) + " m³/" + (L === "en" ? "year" : "ano") + " (1.500 mm) " + CONF[L]]];
    return { nome: "estufa_" + a + "x" + b + "m", malha: M, calc: calc, formatos: ["stl", "obj", "csv"],
      sugestoes: L === "en" ? ["Add SustainKit sensors (temperature, humidity, soil) and drip irrigation fed by the cistern."] : ["Incluir sensores do SustainKit (temperatura, umidade, solo) e gotejamento alimentado pela cisterna."] };
  }
  function gCaixa(txt, L) {
    var m = txt.match(/(\d+[.,]?\d*)\s*[x×]\s*(\d+[.,]?\d*)\s*[x×]\s*(\d+[.,]?\d*)\s*(cm|mm)/i), f = m && m[4].toLowerCase() === "cm" ? 10 : 1;
    var X = m ? num(m[1]) * f : 100, Y = m ? num(m[2]) * f : 80, Z = m ? num(m[3]) * f : 50, e = 2, M = new Malha();
    var tampa = new Malha(), corpo = new Malha();
    corpo.caixaOca(X, Y, Z, e);                                                   // corpo: um sólido só
    tampa.caixa(0, 0, 0, X, Y, e); tampa.anelRet(e + 0.3, e + 0.3, X - e - 0.3, Y - e - 0.3, 1.6, e, e + 4);  // tampa + aba de encaixe (folga 0,3 mm)
    corpo.t.forEach(function (t) { M.t.push(t); }); tampa.t.forEach(function (t) { M.t.push(t.map(function (q) { return [q[0] + X + 10, q[1], q[2]]; })); });
    var calc = [[L === "en" ? "Inside" : "Interno", fmt(X - 2 * e, 0) + " × " + fmt(Y - 2 * e, 0) + " × " + fmt(Z - e, 0) + " mm"], [L === "en" ? "Material" : "Material", fmt(volume(M) / 1000, 1) + " cm³ · PETG/ASA " + (L === "en" ? "outdoors" : "para área externa")]];
    return { nome: "caixa_sensores_" + Math.round(X) + "x" + Math.round(Y) + "x" + Math.round(Z), malha: M, partes: [{ nome: "corpo", malha: corpo }, { nome: "tampa", malha: tampa }], calc: calc, formatos: ["stl", "obj"],
      sugestoes: L === "en" ? ["Add a cable gland hole (PG7) and a rubber gasket for IP54."] : ["Prever furo para prensa-cabo (PG7) e vedação de borracha para IP54."] };
  }
  function gAvac(txt, L) {  // NBR 16401-1 (método simplificado de componentes) e 16401-3 (ar externo)
    var A = achar(txt, /(\d[\d.,]*)\s*m(?:²|2)/i, 40), h = achar(txt, /p[eé][- ]?direito\s*(?:de\s*)?(\d+[.,]?\d*)/i, 2.8), pes = achar(txt, /(\d+)\s*pessoas|(\d+)\s*people/i, Math.max(1, Math.round(A / 6)));
    var jan = achar(txt, /(\d[\d.,]*)\s*m(?:²|2)\s*de\s*janela|janelas?\s*(?:de\s*)?(\d[\d.,]*)/i, A * 0.15), dT = achar(txt, /Δ?T\s*(?:de\s*)?(\d+)/i, 8);
    var qEnv = (A * 0.6 * 2.5 + A * 1.0) * dT, qJan = jan * 200 * 0.6, qPes = pes * (75 + 55), qIlu = A * 10, qEq = A * 15, qAr = (pes * 2.5 + A * 0.3) * 1.2 * (dT * 1.0 + 15);
    var Q = qEnv + qJan + qPes + qIlu + qEq + qAr, btu = Q * 3.412, tr = btu / 12000, r = gDutos("sala de " + A + " m² pé-direito " + h, L, tr);
    var calc = [[L === "en" ? "Room" : "Ambiente", fmt(A, 1) + " m² · " + pes + (L === "en" ? " people" : " pessoas") + " · " + (L === "en" ? "windows " : "janelas ") + fmt(jan, 1) + " m² · ΔT " + dT + " K " + CONF[L]],
      [L === "en" ? "Envelope + windows" : "Envoltória + janelas", fmt(qEnv + qJan, 0) + " W (U 2,5 W/m²K; FS 0,6; 200 W/m² " + CONF[L] + ")"],
      [L === "en" ? "People, lighting, equipment" : "Pessoas, iluminação, equipamentos", fmt(qPes + qIlu + qEq, 0) + " W (75+55 W/" + (L === "en" ? "person" : "pessoa") + "; 10 e 15 W/m²)"],
      [L === "en" ? "Outdoor air (NBR 16401-3)" : "Ar externo (NBR 16401-3)", fmt(pes * 2.5 + A * 0.3, 0) + " L/s · " + fmt(qAr, 0) + " W " + CONF[L]],
      [L === "en" ? "Total cooling load" : "Carga térmica total", fmt(Q / 1000, 2) + " kW · " + fmt(btu, 0) + " BTU/h · " + fmt(tr, 2) + " TR"],
      [L === "en" ? "Rule of thumb (check)" : "Regra prática (conferência)", fmt(A * 600, 0) + " BTU/h"]];
    r.calc = calc.concat(r.calc.slice(2)); r.nome = "avac_nbr16401_" + Math.round(A) + "m2"; return r;
  }
  function lerGrade(txt) {  // ESRI ASCII (.asc) ou XYZ (x y z por linha) → {nx, ny, cel, z[]}
    var ls = txt.trim().split(/\r?\n/), cab = {}, i = 0;
    while (i < ls.length && /^[a-z_]+\s/i.test(ls[i])) { var p = ls[i].trim().split(/\s+/); cab[p[0].toLowerCase()] = +p[1]; i++; }
    if (cab.ncols) { var z = []; ls.slice(i).forEach(function (l) { l.trim().split(/\s+/).forEach(function (v) { z.push(+v); }); }); return { nx: cab.ncols, ny: cab.nrows, cel: cab.cellsize || 1, sem: cab.nodata_value, z: z }; }
    var pts = ls.map(function (l) { return l.trim().split(/[\s,;]+/).map(Number); }).filter(function (p) { return p.length >= 3 && isFinite(p[2]); });
    var xs = Array.from(new Set(pts.map(function (p) { return p[0]; }))).sort(function (a, b) { return a - b; }), ys = Array.from(new Set(pts.map(function (p) { return p[1]; }))).sort(function (a, b) { return b - a; });
    var mz = {}, zz = []; pts.forEach(function (p) { mz[p[0] + "," + p[1]] = p[2]; });
    ys.forEach(function (y) { xs.forEach(function (x) { zz.push(mz[x + "," + y]); }); });
    return { nx: xs.length, ny: ys.length, cel: xs.length > 1 ? xs[1] - xs[0] : 1, z: zz };
  }
  function gTerreno(txt, L, grade) {
    var g = grade, nx = g.nx, ny = g.ny, passo = Math.max(1, Math.ceil(Math.max(nx, ny) / 150)), Z = function (i, j) { var v = g.z[j * nx + i]; return v == null || v === g.sem || !isFinite(v) ? NaN : v; };
    var zmin = Infinity, zmax = -Infinity, imin = 0, jmin = 0, decl = [];
    for (var j = 0; j < ny; j++) for (var i = 0; i < nx; i++) { var v = Z(i, j); if (isFinite(v)) { if (v < zmin) { zmin = v; imin = i; jmin = j; } zmax = Math.max(zmax, v); }
      if (i > 0 && j > 0 && isFinite(v)) { var dx = (v - Z(i - 1, j)) / g.cel, dy = (v - Z(i, j - 1)) / g.cel; if (isFinite(dx) && isFinite(dy)) decl.push(Math.atan(Math.hypot(dx, dy)) * 180 / Math.PI); } }
    decl.sort(function (a, b) { return a - b; });
    var M = new Malha(), esc = 1000 * g.cel;
    for (j = 0; j + passo < ny; j += passo) for (i = 0; i + passo < nx; i += passo) {
      var a = Z(i, j), b = Z(i + passo, j), c = Z(i + passo, j + passo), e = Z(i, j + passo); if (![a, b, c, e].every(isFinite)) continue;
      M.quad([i * esc, -j * esc, (a - zmin) * 1000], [(i + passo) * esc, -j * esc, (b - zmin) * 1000], [(i + passo) * esc, -(j + passo) * esc, (c - zmin) * 1000], [i * esc, -(j + passo) * esc, (e - zmin) * 1000]);
    }
    var acima = decl.filter(function (x) { return x > pr("app.declividade", 45); }).length, area = (nx - 1) * (ny - 1) * g.cel * g.cel;
    var calc = [[L === "en" ? "Grid" : "Grade", nx + " × " + ny + " · " + (L === "en" ? "cell " : "célula ") + g.cel + " m · " + fmt(area, 0) + " m²"],
      [L === "en" ? "Elevation range" : "Desnível", fmt(zmin, 1) + " → " + fmt(zmax, 1) + " m (" + fmt(zmax - zmin, 1) + " m)"],
      [L === "en" ? "Slope (median / max)" : "Declividade (mediana / máx.)", fmt(decl[Math.floor(decl.length / 2)] || 0, 1) + "° / " + fmt(decl[decl.length - 1] || 0, 1) + "°"],
      [L === "en" ? "Above 45° (APP, Forest Code)" : "Acima de 45° (APP, Código Florestal)", fmt(100 * acima / Math.max(1, decl.length), 1) + "% " + (L === "en" ? "of cells" : "das células")],
      [L === "en" ? "Water runs to" : "A água escoa para", (L === "en" ? "lowest point at cell " : "o ponto mais baixo, célula ") + imin + ", " + jmin + " (" + fmt(zmin, 1) + " m)"]];
    return { nome: "terreno", malha: M, calc: calc, formatos: ["stl", "obj", "csv"],
      sugestoes: L === "en" ? ["GeoTIFF (Copernicus/ALOS/SRTM): export as ASCII grid (.asc) in QGIS until the GeoTIFF reader is added.", "Cross with rainfall to size drainage and with the APP map."]
        : ["GeoTIFF (Copernicus/ALOS/SRTM): exportar como grade ASCII (.asc) no QGIS até entrar a leitura de GeoTIFF.", "Cruzar com a chuva para dimensionar a drenagem e com o mapa de APP."] };
  }
  function chuvaOnline(geo) {  // média anual 2015–2024 (Open-Meteo/ERA5) quando há internet; sem internet fica [CONFERIR]
    var c = centro(geo); if (!c || !w.fetch) return Promise.resolve(null);
    var u = "https://archive-api.open-meteo.com/v1/archive?latitude=" + c[1].toFixed(4) + "&longitude=" + c[0].toFixed(4) + "&start_date=2015-01-01&end_date=2024-12-31&daily=precipitation_sum&timezone=UTC";
    return w.fetch(u).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
      if (!j || !j.daily) return null; var s = 0, n = 0; j.daily.precipitation_sum.forEach(function (v) { if (v != null) { s += v; n++; } }); return n > 3000 ? { mm: s / (n / 365.25), fonte: "Open-Meteo/ERA5 2015–2024" } : null;
    }).catch(function () { return null; });
  }
  function entender(txt, temImg) {
    if (/net ?zero|carbono zero|zerar (a )?(energia|conta|emiss)|balan[cç]o energ|energia solar|fotovolt|solar panel/i.test(txt)) return "netzero";
    if (/calha|cisterna|[aá]gua de chuva|capta[cç][aã]o de chuva|gutter|cistern/i.test(txt)) return "agua";
    if (/estufa|greenhouse/i.test(txt)) return "estufa";
    if (/caixa|case|gabinete/i.test(txt) && /sensor|eletr[oô]nic|placa|esp32|arduino/i.test(txt)) return "caixa";
    if (/carga t[eé]rmica|NBR ?16401|cooling load/i.test(txt)) return "avac";
    if (/turbina|aerogerador|rotor e[oó]lic|wind turbine|turbine/i.test(txt)) return "turbina";
    if (/ar[- ]condicionado|\bduto|\bAVAC\b|\bHVAC\b|climatiza|air[- ]condition|\bduct/i.test(txt)) return "dutos";
    if (/chuva|pluvi|precipita|rain/i.test(txt)) return "chuva";
    if (temImg || /relevo|litofan|heightmap|relief/i.test(txt)) return "relevo";
    return "";
  }

  // ------------------------------------------------------------------ interface
  function estilo() {
    if (d.getElementById("pmd-estilo")) return;
    var s = d.createElement("style"); s.id = "pmd-estilo";
    s.textContent = ".pmd{border:1px solid #D9D3C2;border-left:5px solid #C2410C;border-radius:12px;padding:.8rem 1rem;margin:1rem 0;background:#FFFFFF;color:#1B1F23}" +
      ".pmd h2{margin:.1rem 0 .3rem;font-size:1.15rem}.pmd textarea{width:100%;min-height:3.2rem;font:inherit;padding:.4rem;border:1px solid #D9D3C2;border-radius:8px;background:transparent;color:inherit}" +
      ".pmd .pmd-l{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin:.5rem 0}.pmd button,.pmd .pmd-b{border:1px solid #D9D3C2;border-radius:8px;padding:.35rem .7rem;font:inherit;cursor:pointer;background:#FFFFFF;color:inherit}" +
      ".pmd .pmd-p{background:#C2410C;border-color:#C2410C;color:#FFFFFF}.pmd .pmd-ex{font-size:.88rem;opacity:.85;cursor:pointer;text-decoration:underline dotted}" +
      ".pmd table{border-collapse:collapse;width:100%;font-size:.92rem}.pmd td{border-bottom:1px solid #D9D3C2;padding:.25rem .3rem;vertical-align:top}.pmd .pmd-v{min-height:0;margin:.5rem 0}.pmd small{opacity:.8}.pmd canvas{max-width:100%;height:auto}.pmd{overflow-wrap:anywhere;max-width:100%}" + "html[data-tema='escuro'] .pmd{background:#0F4535;color:#F4F1EA;border-color:#2F5E4E}html[data-tema='escuro'] .pmd button:not([class*=\"-p\"]){background:#0F4535;color:#F4F1EA;border-color:#2F5E4E}html[data-tema='escuro'] .pmd td,html[data-tema='escuro'] .pmd .pdv-m{border-color:#2F5E4E}";
    d.head.appendChild(s);
  }
  function baixar(blob, nome) { var u = URL.createObjectURL(blob), a = d.createElement("a"); a.href = u; a.download = nome; d.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(u); }, 3000); }
  function ver(box, m) {
    var THREE = w.THREE; box.innerHTML = ""; if (!THREE || !m.t.length) return;
    var W = Math.min(box.clientWidth || 560, 720), H = Math.round(W * 0.55), ren = new THREE.WebGLRenderer({ antialias: true }); ren.setSize(W, H); box.appendChild(ren.domElement);
    var pos = []; m.t.forEach(function (t) { t.forEach(function (p) { pos.push(p[0], p[1], p[2]); }); });
    var g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3)); g.computeVertexNormals(); g.computeBoundingBox();
    var c = new THREE.Vector3(), tam = new THREE.Vector3(); g.boundingBox.getCenter(c); g.boundingBox.getSize(tam); g.translate(-c.x, -c.y, -c.z); g.rotateX(-Math.PI / 2);
    var cena = new THREE.Scene(), cs = getComputedStyle(d.documentElement); cena.background = new THREE.Color((cs.getPropertyValue("--sup") || "#FFFFFF").trim() || "#FFFFFF");
    cena.add(new THREE.Mesh(g, new THREE.MeshStandardMaterial({ color: new THREE.Color("#B07A12"), roughness: .6, side: THREE.DoubleSide })));
    cena.add(new THREE.HemisphereLight(0xffffff, 0x444444, 1.1)); var l = new THREE.DirectionalLight(0xffffff, .8); l.position.set(1, 2, 3); cena.add(l);
    var r = Math.max(tam.x, tam.y, tam.z) || 1, cam = new THREE.PerspectiveCamera(40, W / H, r / 100, r * 100), ang = 0.6, vivo = true;
    (function laco() { if (!vivo || !box.contains(ren.domElement)) return; ang += 0.01; cam.position.set(Math.sin(ang) * r * 2, r * 0.9, Math.cos(ang) * r * 2); cam.lookAt(0, 0, 0); ren.render(cena, cam); requestAnimationFrame(laco); })();
    ren.domElement.setAttribute("role", "img"); ren.domElement.setAttribute("aria-label", "Prévia 3D do modelo gerado");
  }
  function sugPub(lista, t) { return lista.concat([t.mais]); }
  function montar(el) {
    if (el.getAttribute("data-pmd-ok")) return; el.setAttribute("data-pmd-ok", "1");
    var L = lingua(), ctx = el.getAttribute("data-physis-modelador") || "", publico = /^inovastem/.test(ctx), t = publico ? Object.assign({}, TX[L], PUB[L]) : TX[L];
    var emQuadro = false; try { emQuadro = d.documentElement.hasAttribute("data-physis-demo"); } catch (e) { emQuadro = false; }
    if (emQuadro) { el.hidden = true; return; }
    estilo();
    el.innerHTML = '<section class="pmd" aria-label="' + t.tit + '"><h2>' + t.tit + "</h2><small>" + t.sub + " " + t.ex.map(function (x) { return '<span class="pmd-ex" tabindex="0">' + esc(x) + "</span>"; }).join(" · ") + "</small>" +
      '<div class="pmd-l"><textarea class="pmd-t" aria-label="' + t.tit + '"></textarea></div><div class="pmd-l"><label class="pmd-b">' + t.arquivo +
      ' <input type="file" class="pmd-f" accept="image/*,.kml,.kmz,.geojson,.json,.gpx,.asc,.xyz,.txt,.csv" hidden></label><span class="pmd-fn"></span><button class="pmd-p pmd-g">' + t.gerar + '</button></div><div class="pmd-o" role="status"></div><div class="pmd-v"></div></section>';
    var ta = el.querySelector(".pmd-t"), out = el.querySelector(".pmd-o"), vbox = el.querySelector(".pmd-v"), img = null, geo = null, grade = null;
    Array.prototype.forEach.call(el.querySelectorAll(".pmd-ex"), function (x) { var f = function () { ta.value = x.textContent; ta.focus(); }; x.onclick = f; x.onkeydown = function (e) { if (e.key === "Enter") f(); }; });
    el.querySelector(".pmd-f").onchange = function (e) {
      var f = e.target.files[0]; if (!f) return; img = null; geo = null; grade = null; var nm = f.name.toLowerCase(), fn = el.querySelector(".pmd-fn"); fn.textContent = f.name;
      if (/^image\//.test(f.type)) { var im = new Image(); im.onload = function () { img = im; }; im.src = URL.createObjectURL(f); return; }
      var ok = function (pts) { geo = { nome: f.name, pts: pts }; fn.textContent = t.lido + ": " + f.name + " (" + pts.length + " " + t.pontos + ")"; };
      if (/\.kmz$/.test(nm)) {
        if (!w.JSZip) { fn.textContent = "KMZ: " + (L === "en" ? "unzip it and upload the .kml" : "descompacte e envie o .kml"); return; }
        w.JSZip.loadAsync(f).then(function (z) { var k = Object.keys(z.files).filter(function (n) { return /\.kml$/i.test(n); })[0]; return k ? z.files[k].async("string") : ""; }).then(function (s) { ok(lerKML(s)); });
      } else if (/\.(asc|xyz|txt|csv)$/.test(nm)) f.text().then(function (s) { grade = lerGrade(s); fn.textContent = t.lido + ": " + f.name + " (" + grade.nx + " × " + grade.ny + ")"; });
      else f.text().then(function (s) { ok(/\.kml$/.test(nm) ? lerKML(s) : /\.gpx$/.test(nm) ? lerGPX(s) : lerGeoJSON(JSON.parse(s))); });
    };
    var sug = function (lista) { return publico ? sugPub(lista, t) : lista; };
    el.querySelector(".pmd-g").onclick = function () {
      var txt = ta.value.trim(), qual = grade ? "terreno" : (entender(txt, !!img) || (geo ? "chuva" : "")), r;
      if (!qual) {
        out.innerHTML = "<p>" + t.naoEntendi + "</p>" + (publico ? "" : "<button class='pmd-c'>" + t.copiar + "</button>"); vbox.innerHTML = ""; if (publico) return;
        out.querySelector(".pmd-c").onclick = function () { var b = this; (navigator.clipboard ? navigator.clipboard.writeText("Modelagem (" + ctx + "): " + txt) : Promise.reject()).then(function () { b.textContent = t.copiado; }, function () { ta.select(); }); };
        return;
      }
      if (qual === "chuva" && geo && !publico && !/\d\s*mm/i.test(txt)) { out.innerHTML = "<p>" + (L === "en" ? "Looking up the site's rainfall…" : "Buscando a chuva do local…") + "</p>";
        chuvaOnline(geo).then(function (c) { if (c) { ta.value = txt + " " + Math.round(c.mm) + " mm"; fonteChuva = c.fonte; } gerarAgora(); }); return; }
      gerarAgora();
    };
    var fonteChuva = "";
    function gerarAgora() {
      var txt = ta.value.trim(), qual = grade ? "terreno" : (entender(txt, !!img) || (geo ? "chuva" : "")), r;
      r = qual === "turbina" ? gTurbina(txt, L) : qual === "dutos" ? gDutos(txt, L) : qual === "avac" ? gAvac(txt, L) : qual === "chuva" ? gChuva(txt, L, geo) : qual === "netzero" ? gNetZero(txt, L, geo)
        : qual === "agua" ? gAgua(txt, L) : qual === "estufa" ? gEstufa(txt, L) : qual === "caixa" ? gCaixa(txt, L) : qual === "terreno" ? gTerreno(txt, L, grade) : img ? gRelevo(txt, L, img) : { erro: L === "en" ? "Upload an image for the relief." : "Envie uma imagem para o relevo." };
      if (fonteChuva && r.calc) { r.calc.push([L === "en" ? "Rainfall source" : "Fonte da chuva", fonteChuva]); fonteChuva = ""; }
      if (r.erro) { out.innerHTML = "<p>" + esc(r.erro) + "</p>"; vbox.innerHTML = ""; return; }
      var bt = r.formatos.map(function (f) { return '<button data-f="' + f + '">' + t.baixar + " ." + f + "</button>"; }).join(" ");
      out.innerHTML = "<p><strong>" + esc(r.nome) + "</strong></p><h3 style='margin:.4rem 0;font-size:1rem'>" + t.calc + "</h3><table>" + r.calc.map(function (c) { return "<tr><td>" + esc(c[0]) + "</td><td>" + esc(c[1]) + "</td></tr>"; }).join("") +
        "</table><p><small>" + t.aviso + "</small></p><div class='pmd-l'>" + bt + "</div><p><strong>" + t.sugestoes + ":</strong></p><ul>" + sug(r.sugestoes).map(function (s) { return "<li>" + esc(s) + "</li>"; }).join("") + "</ul>";
      Array.prototype.forEach.call(out.querySelectorAll("[data-f]"), function (b) {
        b.onclick = function () {
          var f = b.getAttribute("data-f");
          if (f === "stl" && r.partes) r.partes.forEach(function (q, i) { setTimeout(function () { baixar(stl(q.malha), r.nome + "_" + q.nome + ".stl"); }, 400 * i); });
          else if (f === "stl") baixar(stl(r.malha), r.nome + ".stl"); else if (f === "obj") baixar(obj(r.malha), r.nome + ".obj");
          else if (f === "ifc") baixar(ifc(r.nome, r.ifc || []), r.nome + ".ifc");
          else if (f === "geojson") baixar(new Blob([JSON.stringify(r.geojson, null, 1)], { type: "application/geo+json" }), r.nome + ".geojson");
          else if (f === "csv") baixar(new Blob(["﻿item;valor\n" + r.calc.map(function (c) { return '"' + c[0] + '";"' + String(c[1]).replace(/"/g, "'") + '"'; }).join("\n")], { type: "text/csv" }), r.nome + ".csv");
        };
      });
      w.PhysisModelador.ultimo = r; ver(vbox, r.malha);
    };
  }
  w.PhysisModelador = { checar: checar, montar: montar, entender: entender, gerar: { turbina: gTurbina, dutos: gDutos, chuva: gChuva, netzero: gNetZero, agua: gAgua, estufa: gEstufa, caixa: gCaixa, avac: gAvac, terreno: gTerreno }, lerGrade: lerGrade, chuvaOnline: chuvaOnline, exportar: { stl: stl, obj: obj, ifc: ifc }, lerKML: lerKML, areaM2: areaM2, ultimo: null };
  function tudo() { Array.prototype.forEach.call(d.querySelectorAll("[data-physis-modelador]"), montar); }
  if (d.readyState === "loading") d.addEventListener("DOMContentLoaded", tudo); else tudo();
  if (w.MutationObserver) new MutationObserver(function () { Array.prototype.forEach.call(d.querySelectorAll("[data-physis-modelador]:not([data-pmd-ok])"), montar); }).observe(d.documentElement, { childList: true, subtree: true });
})(typeof window !== "undefined" ? window : this);
