/* physis-modelador.js v1 (22/11/2026): bot de modelagem na página inicial de todo projeto com modelagem 3D.
   Pedido em texto (PT/EN) ou imagem/arquivo → modelo gerado LOCALMENTE (sem internet, sempre o mesmo resultado)
   + cálculos preliminares + exportação no formato certo (STL, OBJ, IFC, GeoJSON, CSV).
   Geradores v1: turbina eólica para impressão 3D (Savonius), dutos de ar-condicionado (IFC), chuva no terreno
   (KML/KMZ do Google Earth, GeoJSON, GPX ou área digitada) e relevo a partir de imagem. Pedido que nenhum gerador
   entende vira texto para a caixa de comandos do M&A (fila do Claude); quando a IA da Physis estiver no servidor,
   ela usa estes mesmos geradores. Premissas e números de regra prática vêm marcados [CONFERIR]: é estimativa
   preliminar, não projeto. Uso: <div data-physis-modelador="modelagem3d"></div>. Original único: sistema/physis-modelador.js. */
(function (w) {
  "use strict";
  var d = w.document;
  function lingua() { try { return (localStorage.getItem("physis-pref-idioma") || d.documentElement.lang || "pt").slice(0, 2) === "en" ? "en" : "pt"; } catch (e) { return "pt"; } }
  var TX = {
    pt: { tit: "Bot de modelagem", sub: "Escreva o pedido ou envie uma imagem ou arquivo (KML/KMZ do Google Earth, GeoJSON, GPX). Exemplos:",
      ex: ["gere uma turbina para impressão 3D de 40 cm", "inclua a previsão de passagem de ar-condicionado numa sala de 60 m²", "mapeie a incidência de chuva no terreno com 1.500 mm/ano", "relevo da imagem com 12 cm"],
      gerar: "Gerar", arquivo: "Imagem ou arquivo", calc: "Cálculos preliminares", baixar: "Baixar", naoEntendi: "Nenhum gerador local entende este pedido ainda. Copie o texto para a caixa de comandos do M&A: ele vai para a fila do Claude e volta como rascunho.",
      copiar: "Copiar pedido", copiado: "Copiado.", aviso: "Estimativa preliminar para conversar e decidir; não substitui projeto assinado. Itens [CONFERIR] são premissas a confirmar.",
      semTerreno: "Para a chuva, envie o contorno do terreno (KML/KMZ do Google Earth, GeoJSON ou GPX) ou escreva a área (ex.: 2.000 m²).",
      lido: "Arquivo lido", pontos: "pontos", sugestoes: "Sugestões" },
    en: { tit: "Modelling bot", sub: "Write the request or upload an image or file (Google Earth KML/KMZ, GeoJSON, GPX). Examples:",
      ex: ["generate a 40 cm wind turbine for 3D printing", "add the air-conditioning duct route for a 60 m² room", "map rainfall on the site with 1,500 mm/year", "relief from the image, 12 cm"],
      gerar: "Generate", arquivo: "Image or file", calc: "Preliminary calculations", baixar: "Download", naoEntendi: "No local generator understands this request yet. Copy it to the M&V command box: it goes to Claude's queue and comes back as a draft.",
      copiar: "Copy request", copiado: "Copied.", aviso: "Preliminary estimate to discuss and decide; it does not replace a signed design. [TO CHECK] items are assumptions to confirm.",
      semTerreno: "For rainfall, upload the site outline (Google Earth KML/KMZ, GeoJSON or GPX) or type the area (e.g., 2,000 m²).",
      lido: "File read", pontos: "points", sugestoes: "Suggestions" }
  };
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
  Malha.prototype.cilindro = function (cx, cy, r, z0, z1, n) {  // disco/cilindro fechado
    for (var i = 0; i < n; i++) {
      var a = 2 * Math.PI * i / n, b = 2 * Math.PI * (i + 1) / n, p0 = [cx + r * Math.cos(a), cy + r * Math.sin(a)], p1 = [cx + r * Math.cos(b), cy + r * Math.sin(b)];
      this.quad([p0[0], p0[1], z0], [p1[0], p1[1], z0], [p1[0], p1[1], z1], [p0[0], p0[1], z1]);
      this.tri([cx, cy, z1], [p0[0], p0[1], z1], [p1[0], p1[1], z1]); this.tri([cx, cy, z0], [p1[0], p1[1], z0], [p0[0], p0[1], z0]);
    }
  };
  Malha.prototype.arco = function (cx, cy, r, e, a0, a1, z0, z1, n) {  // pá: casca de meio cilindro com espessura e
    for (var i = 0; i < n; i++) {
      var a = a0 + (a1 - a0) * i / n, b = a0 + (a1 - a0) * (i + 1) / n, ri = r - e;
      var o0 = [cx + r * Math.cos(a), cy + r * Math.sin(a)], o1 = [cx + r * Math.cos(b), cy + r * Math.sin(b)], i0 = [cx + ri * Math.cos(a), cy + ri * Math.sin(a)], i1 = [cx + ri * Math.cos(b), cy + ri * Math.sin(b)];
      this.quad([o0[0], o0[1], z0], [o1[0], o1[1], z0], [o1[0], o1[1], z1], [o0[0], o0[1], z1]);
      this.quad([i1[0], i1[1], z0], [i0[0], i0[1], z0], [i0[0], i0[1], z1], [i1[0], i1[1], z1]);
      this.quad([o0[0], o0[1], z1], [o1[0], o1[1], z1], [i1[0], i1[1], z1], [i0[0], i0[1], z1]);
      this.quad([i0[0], i0[1], z0], [i1[0], i1[1], z0], [o1[0], o1[1], z0], [o0[0], o0[1], z0]);
    }
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
    var m = txt.match(/(\d+[.,]?\d*)\s*(cm|mm|m)\b/i), alt = m ? num(m[1]) * ({ cm: 10, mm: 1, m: 1000 })[m[2].toLowerCase()] : 400;
    var vel = (txt.match(/(\d+[.,]?\d*)\s*m\/s/i) || [])[1], v = vel ? num(vel) : 5;
    var D = alt * 0.5, r = D / 4, e = Math.max(1.6, D / 100), ch = Math.max(2.4, alt / 80), eixoR = Math.max(4, D / 30), M = new Malha();
    M.cilindro(0, 0, D / 2 + 4, 0, ch, 64); M.cilindro(0, 0, D / 2 + 4, alt - ch, alt, 64);                 // tampas
    M.arco(-r + e, 0, r, e, 0, Math.PI, ch, alt - ch, 48); M.arco(r - e, 0, r, e, Math.PI, 2 * Math.PI, ch, alt - ch, 48);  // duas pás em S
    M.cilindro(0, 0, eixoR, -alt * 0.15, alt + alt * 0.05, 32);                                             // furo/eixo de referência
    var Am = (D / 1000) * (alt / 1000), cp = 0.15, P = 0.5 * 1.225 * Am * Math.pow(v, 3) * cp, vol = volume(M) / 1000, cx = caixaDe(M), mesa = 220;
    var calc = [
      [L === "en" ? "Type" : "Tipo", "Savonius (S)"], [L === "en" ? "Height × diameter" : "Altura × diâmetro", fmt(alt / 10, 1) + " × " + fmt(D / 10, 1) + " cm"],
      [L === "en" ? "Swept area" : "Área varrida", fmt(Am, 3) + " m²"],
      [L === "en" ? "Power at " : "Potência a ", fmt(v, 1) + " m/s, Cp " + cp + " " + CONF[L] + ": " + fmt(P, 2) + " W"],
      [L === "en" ? "Printed volume (approx.)" : "Volume impresso (aprox.)", fmt(vol, 0) + " cm³ · PLA ≈ " + fmt(vol * 1.24 * 0.6, 0) + " g " + CONF[L] + " (60% " + (L === "en" ? "infill/shell" : "preenchimento/casca") + ")"],
      [L === "en" ? "Fits a " : "Cabe numa mesa de ", mesa + " mm? " + (Math.max(cx[0], cx[1]) <= mesa && cx[2] <= 250 ? (L === "en" ? "yes" : "sim") : (L === "en" ? "no: print in parts (blades and end plates separately)" : "não: imprimir em partes (pás e tampas separadas)"))]];
    return { nome: "turbina_savonius_" + Math.round(alt / 10) + "cm", malha: M, calc: calc, formatos: ["stl", "obj"],
      sugestoes: L === "en" ? ["Add a bearing seat for a 608 bearing and a shaft of the printer's diameter.", "For outdoor use, PETG or ASA instead of PLA.", "Measure wind speed on site before sizing a generator."]
        : ["Prever alojamento para rolamento 608 e eixo no diâmetro da impressora.", "Para uso externo, PETG ou ASA em vez de PLA.", "Medir o vento no local antes de dimensionar o gerador."] };
  }
  function gDutos(txt, L) {
    var a = (txt.match(/(\d+[.,]?\d*)\s*m²|(\d+[.,]?\d*)\s*m2/i) || []), area = a[1] ? num(a[1]) : a[2] ? num(a[2]) : 40;
    var pe = (txt.match(/p[eé][- ]?direito\s*(?:de\s*)?(\d+[.,]?\d*)/i) || [])[1], h = pe ? num(pe) : 2.8;
    var lado = Math.sqrt(area), btu = area * 600, tr = btu / 12000, q = tr * 400 * 1.699, vAr = 4, secao = q / 3600 / vAr, w = Math.sqrt(secao * 2), hd = secao / w;
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
      sugestoes: L === "en" ? ["Replace the rule of thumb with the HVAC module's load calculation (NBR 16401) before sizing.", "Import the building IFC in the Planner to route the duct through the real rooms."]
        : ["Trocar a regra prática pelo cálculo de carga do módulo AVAC (NBR 16401) antes de dimensionar.", "Importar o IFC da edificação no Planejador para passar o duto pelos ambientes reais."] };
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
      sugestoes: L === "en" ? ["Photo → full 3D object (several photos around it): use Physis 3D on the InovaSTEM platform or CrealityScan."] : ["Foto → objeto 3D completo (várias fotos ao redor): usar a Physis 3D da plataforma InovaSTEM ou o CrealityScan."] };
  }
  function entender(txt, temImg) {
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
    s.textContent = ".pmd{border:1px solid var(--linha,#D9D3C2);border-left:5px solid var(--botao,#C2410C);border-radius:12px;padding:.8rem 1rem;margin:1rem 0;background:var(--sup,#FFFFFF);color:var(--texto,#1B1F23)}" +
      ".pmd h2{margin:.1rem 0 .3rem;font-size:1.15rem}.pmd textarea{width:100%;min-height:3.2rem;font:inherit;padding:.4rem;border:1px solid var(--linha,#D9D3C2);border-radius:8px;background:var(--fundo,#F4F1EA);color:inherit}" +
      ".pmd .pmd-l{display:flex;flex-wrap:wrap;gap:.5rem;align-items:center;margin:.5rem 0}.pmd button,.pmd .pmd-b{border:1px solid var(--linha,#D9D3C2);border-radius:8px;padding:.35rem .7rem;font:inherit;cursor:pointer;background:var(--sup,#FFFFFF);color:inherit}" +
      ".pmd .pmd-p{background:var(--botao,#C2410C);border-color:var(--botao,#C2410C);color:#FFFFFF}.pmd .pmd-ex{font-size:.88rem;opacity:.85;cursor:pointer;text-decoration:underline dotted}" +
      ".pmd table{border-collapse:collapse;width:100%;font-size:.92rem}.pmd td{border-bottom:1px solid var(--linha,#D9D3C2);padding:.25rem .3rem;vertical-align:top}.pmd .pmd-v{min-height:0;margin:.5rem 0}.pmd small{opacity:.8}.pmd canvas{max-width:100%;height:auto}.pmd{overflow-wrap:anywhere;max-width:100%}";
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
  function montar(el) {
    var L = lingua(), t = TX[L], ctx = el.getAttribute("data-physis-modelador") || "";
    var emQuadro = false; try { emQuadro = d.documentElement.hasAttribute("data-physis-demo"); } catch (e) { emQuadro = false; }
    if (emQuadro) { el.hidden = true; return; }
    estilo();
    el.innerHTML = '<section class="pmd" aria-label="' + t.tit + '"><h2>' + t.tit + "</h2><small>" + t.sub + " " + t.ex.map(function (x) { return '<span class="pmd-ex" tabindex="0">' + esc(x) + "</span>"; }).join(" · ") + "</small>" +
      '<div class="pmd-l"><textarea class="pmd-t" aria-label="' + t.tit + '"></textarea></div><div class="pmd-l"><label class="pmd-b">' + t.arquivo +
      ' <input type="file" class="pmd-f" accept="image/*,.kml,.kmz,.geojson,.json,.gpx" hidden></label><span class="pmd-fn"></span><button class="pmd-p pmd-g">' + t.gerar + '</button></div><div class="pmd-o" role="status"></div><div class="pmd-v"></div></section>';
    var ta = el.querySelector(".pmd-t"), out = el.querySelector(".pmd-o"), vbox = el.querySelector(".pmd-v"), img = null, geo = null;
    Array.prototype.forEach.call(el.querySelectorAll(".pmd-ex"), function (x) { var f = function () { ta.value = x.textContent; ta.focus(); }; x.onclick = f; x.onkeydown = function (e) { if (e.key === "Enter") f(); }; });
    el.querySelector(".pmd-f").onchange = function (e) {
      var f = e.target.files[0]; if (!f) return; img = null; geo = null; var nm = f.name.toLowerCase(), fn = el.querySelector(".pmd-fn"); fn.textContent = f.name;
      if (/^image\//.test(f.type)) { var im = new Image(); im.onload = function () { img = im; }; im.src = URL.createObjectURL(f); return; }
      var ok = function (pts) { geo = { nome: f.name, pts: pts }; fn.textContent = t.lido + ": " + f.name + " (" + pts.length + " " + t.pontos + ")"; };
      if (/\.kmz$/.test(nm)) {
        if (!w.JSZip) { fn.textContent = "KMZ: " + (L === "en" ? "unzip it and upload the .kml" : "descompacte e envie o .kml"); return; }
        w.JSZip.loadAsync(f).then(function (z) { var k = Object.keys(z.files).filter(function (n) { return /\.kml$/i.test(n); })[0]; return k ? z.files[k].async("string") : ""; }).then(function (s) { ok(lerKML(s)); });
      } else f.text().then(function (s) { ok(/\.kml$/.test(nm) ? lerKML(s) : /\.gpx$/.test(nm) ? lerGPX(s) : lerGeoJSON(JSON.parse(s))); });
    };
    el.querySelector(".pmd-g").onclick = function () {
      var txt = ta.value.trim(), qual = entender(txt, !!img) || (geo ? "chuva" : ""), r;
      if (!qual) {
        out.innerHTML = "<p>" + t.naoEntendi + "</p><button class='pmd-c'>" + t.copiar + "</button>"; vbox.innerHTML = "";
        out.querySelector(".pmd-c").onclick = function () { var b = this; (navigator.clipboard ? navigator.clipboard.writeText("Modelagem (" + ctx + "): " + txt) : Promise.reject()).then(function () { b.textContent = t.copiado; }, function () { ta.select(); }); };
        return;
      }
      r = qual === "turbina" ? gTurbina(txt, L) : qual === "dutos" ? gDutos(txt, L) : qual === "chuva" ? gChuva(txt, L, geo) : img ? gRelevo(txt, L, img) : { erro: L === "en" ? "Upload an image for the relief." : "Envie uma imagem para o relevo." };
      if (r.erro) { out.innerHTML = "<p>" + esc(r.erro) + "</p>"; vbox.innerHTML = ""; return; }
      var bt = r.formatos.map(function (f) { return '<button data-f="' + f + '">' + t.baixar + " ." + f + "</button>"; }).join(" ");
      out.innerHTML = "<p><strong>" + esc(r.nome) + "</strong></p><h3 style='margin:.4rem 0;font-size:1rem'>" + t.calc + "</h3><table>" + r.calc.map(function (c) { return "<tr><td>" + esc(c[0]) + "</td><td>" + esc(c[1]) + "</td></tr>"; }).join("") +
        "</table><p><small>" + t.aviso + "</small></p><div class='pmd-l'>" + bt + "</div><p><strong>" + t.sugestoes + ":</strong></p><ul>" + r.sugestoes.map(function (s) { return "<li>" + esc(s) + "</li>"; }).join("") + "</ul>";
      Array.prototype.forEach.call(out.querySelectorAll("[data-f]"), function (b) {
        b.onclick = function () {
          var f = b.getAttribute("data-f");
          if (f === "stl") baixar(stl(r.malha), r.nome + ".stl"); else if (f === "obj") baixar(obj(r.malha), r.nome + ".obj");
          else if (f === "ifc") baixar(ifc(r.nome, r.ifc || []), r.nome + ".ifc");
          else if (f === "geojson") baixar(new Blob([JSON.stringify(r.geojson, null, 1)], { type: "application/geo+json" }), r.nome + ".geojson");
          else if (f === "csv") baixar(new Blob(["﻿item;valor\n" + r.calc.map(function (c) { return '"' + c[0] + '";"' + String(c[1]).replace(/"/g, "'") + '"'; }).join("\n")], { type: "text/csv" }), r.nome + ".csv");
        };
      });
      w.PhysisModelador.ultimo = r; ver(vbox, r.malha);
    };
  }
  w.PhysisModelador = { montar: montar, entender: entender, gerar: { turbina: gTurbina, dutos: gDutos, chuva: gChuva }, exportar: { stl: stl, obj: obj, ifc: ifc }, lerKML: lerKML, areaM2: areaM2, ultimo: null };
  function tudo() { Array.prototype.forEach.call(d.querySelectorAll("[data-physis-modelador]"), montar); }
  if (d.readyState === "loading") d.addEventListener("DOMContentLoaded", tudo); else tudo();
})(typeof window !== "undefined" ? window : this);
