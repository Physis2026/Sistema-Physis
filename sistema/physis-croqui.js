/* physis-croqui.js v1 (24/11/2026): rascunho à mão (foto ou escaneamento, mesmo torto) → planta retificada com ambientes e áreas,
   DXF para CAD e preenchimento dos cálculos. Pedido da dona: "um rascunho torto à mão deve virar projeto após processamento de imagem".
   Usa o processamento de imagem do Physis (physis-imagem-3d.js: cinza, suavização, Otsu, limpeza e contornos) e acrescenta:
   1) paredes = traços escuros; ambientes = áreas claras fechadas por paredes (furos do traço);
   2) retificação: ângulo dominante, giro para os eixos, lados quase horizontais/verticais alinhados (ortogonalização);
   3) escala pela largura real do desenho informada pela pessoa (sem ela, nenhuma área é dada).
   DWG é formato fechado: sai DXF (abre no AutoCAD, LibreCAD, FreeCAD e QGIS). Sem internet; sem dependências.
   Contrato: window.PhysisCroqui = { retificar(laco), deImagem(rgba, nx, ny, op) -> { ambientes, paredes, dxf, svg, escala_m_por_px } } */
(function (w) {
  "use strict";
  const area = l => { let a = 0; for (let i = 0; i < l.length; i++) { const p = l[i], q = l[(i + 1) % l.length]; a += p[0] * q[1] - q[0] * p[1]; } return a / 2; };
  function anguloDominante(lacos) { let sx = 0, sy = 0;                // média dos ângulos (mod 90°) pesada pelo comprimento
    lacos.forEach(l => l.forEach((p, i) => { const q = l[(i + 1) % l.length], dx = q[0] - p[0], dy = q[1] - p[1], c = Math.hypot(dx, dy); if (!c) return;
      const t = Math.atan2(dy, dx) * 4; sx += c * Math.cos(t); sy += c * Math.sin(t); }));
    return Math.atan2(sy, sx) / 4; }
  const girar = (l, a) => { const c = Math.cos(a), s = Math.sin(a); return l.map(p => [p[0] * c - p[1] * s, p[0] * s + p[1] * c]); };
  function simplificar(l, tol) {             // Douglas-Peucker num laço fechado (corta nos dois pontos mais distantes)
    if (l.length < 4) return l.slice();
    let a = 0, b = 0, dm = -1; l.forEach((p, i) => { const d = Math.hypot(p[0] - l[0][0], p[1] - l[0][1]); if (d > dm) { dm = d; b = i; } });
    const dpa = pts => { if (pts.length < 3) return pts.slice(); const p0 = pts[0], p1 = pts[pts.length - 1], dx = p1[0] - p0[0], dy = p1[1] - p0[1], n = Math.hypot(dx, dy) || 1;
      let im = 0, d2 = -1; for (let i = 1; i < pts.length - 1; i++) { const d = Math.abs(dy * (pts[i][0] - p0[0]) - dx * (pts[i][1] - p0[1])) / n; if (d > d2) { d2 = d; im = i; } }
      if (d2 <= tol) return [p0, p1]; const e = dpa(pts.slice(0, im + 1)), f = dpa(pts.slice(im)); return e.slice(0, -1).concat(f); };
    const um = dpa(l.slice(a, b + 1)), dois = dpa(l.slice(b).concat([l[0]]));
    return um.slice(0, -1).concat(dois.slice(0, -1)); }
  function retificar(laco, tolGraus, tolDist) {  // laço já girado para os eixos: junta lados H/V seguidos e refaz os cantos
    const xs = laco.map(p => p[0]), ys = laco.map(p => p[1]), diag = Math.hypot(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
    const l = simplificar(laco, tolDist == null ? Math.max(3, diag * 0.02) : tolDist), sinT = Math.sin((tolGraus == null ? 25 : tolGraus) * Math.PI / 180);
    const lados = l.map((p, i) => { const q = l[(i + 1) % l.length], dx = q[0] - p[0], dy = q[1] - p[1], c = Math.hypot(dx, dy) || 1e-9;
      return { p, q, c, t: Math.abs(dy / c) < sinT ? "H" : Math.abs(dx / c) < sinT ? "V" : "D" }; });
    const runs = []; lados.forEach(d => { const u = runs[runs.length - 1]; if (u && u.t === d.t && d.t !== "D") { u.ls.push(d); } else runs.push({ t: d.t, ls: [d] }); });
    if (runs.length > 1 && runs[0].t === runs[runs.length - 1].t && runs[0].t !== "D") { runs[0].ls = runs.pop().ls.concat(runs[0].ls); }
    if (runs.some(r => r.t === "D") || runs.length < 4 || runs.length % 2) return l;     // não ortogonal: fica só simplificado
    const coord = r => { const k = r.t === "H" ? 1 : 0; let s = 0, c = 0; r.ls.forEach(d => { s += (d.p[k] + d.q[k]) / 2 * d.c; c += d.c; }); return s / c; };
    const v = runs.map(coord);
    return runs.map((r, i) => { const n = runs[(i + 1) % runs.length]; return r.t === "H" ? [v[(i + 1) % runs.length], v[i]] : [v[i], v[(i + 1) % runs.length]]; })
      .map((p, i, arr) => p); }
  function deImagem(rgba, nx, ny, op) {
    op = op || {}; const I = w.PhysisImagem3D; if (!I) throw new Error("processamento de imagem (physis-imagem-3d.js) não carregado");
    const pf = I.processarFoto(rgba, nx, ny, { suavizar: op.suavizar == null ? 1 : op.suavizar, areaMin: op.areaMin == null ? Math.round(nx * ny * 0.0005) : op.areaMin });
    const lacos = I.contornos(pf.M, nx, ny, 1, op.tolerancia == null ? 2 : op.tolerancia);      // em "px" (célula = 1), y para cima
    if (!lacos.length) throw new Error("nenhum traço encontrado na imagem");
    const ang = anguloDominante(lacos), retos = lacos.map(l => retificar(girar(l, -ang)));
    // fora (anti-horário) = massa das paredes; furos (horário) dentro dela = ambientes
    const fora = retos.filter(l => area(l) > 0), furos = retos.filter(l => area(l) < 0);
    const maior = fora.reduce((m, l) => (!m || area(l) > area(m) ? l : m), null);
    const xs = maior.map(p => p[0]), largPx = Math.max(...xs) - Math.min(...xs);
    const esc = op.larguraReal_m > 0 && largPx > 0 ? op.larguraReal_m / largPx : null;
    const minPx = (op.ambienteMin_px == null ? nx * ny * 0.002 : op.ambienteMin_px);
    const amb = furos.filter(l => -area(l) >= minPx).sort((a, b) => area(a) - area(b)).map((l, i) => ({ nome: "Ambiente " + (i + 1),
      area_m2: esc ? Math.round(-area(l) * esc * esc * 100) / 100 : null, laco_m: esc ? l.map(p => [p[0] * esc, p[1] * esc]) : null, laco_px: l }));
    const emM = l => l.map(p => [p[0] * (esc || 1) * 1000, p[1] * (esc || 1) * 1000]);   // DXF e SVG em mm
    const todos = [maior].concat(amb.map(a => a.laco_px)).map(emM);
    const W = (Math.max(...xs) - Math.min(...xs)) * (esc || 1) * 1000, ys = maior.map(p => p[1]), H = (Math.max(...ys) - Math.min(...ys)) * (esc || 1) * 1000;
    const naImagem = l => { const pts = girar(l, ang).map(p => [p[0], ny - p[1]]), xs2 = pts.map(p => p[0]), ys2 = pts.map(p => p[1]);   // caixa na imagem (y para baixo)
      const x0 = Math.min(...xs2), x1 = Math.max(...xs2), y0 = Math.min(...ys2), y1 = Math.max(...ys2), mx = (x1 - x0) * 0.08, my = (y1 - y0) * 0.08;
      return [Math.max(0, Math.round(x0 + mx)), Math.max(0, Math.round(y0 + my)), Math.min(nx, Math.round(x1 - mx)), Math.min(ny, Math.round(y1 - my))]; };
    return { ambientes: amb.map(a => ({ nome: a.nome, area_m2: a.area_m2, laco_m: a.laco_m, caixa_img: naImagem(a.laco_px) })), angulo_graus: Math.round(ang * 1800 / Math.PI) / 10,
      escala_m_por_px: esc, paredes_m: esc ? maior.map(p => [p[0] * esc, p[1] * esc]) : null, limiar: pf.limiar, dxf: I.dxf(todos), svg: I.svg(todos, W, H) };
  }

  /* planta retificada → IFC4 (24/11/2026): paredes (perfil da massa de paredes com os ambientes como vazios, extrudado no pé-direito)
     e um IfcSpace por ambiente (perfil poligonal + IfcQuantityArea NetFloorArea). Unidade: metro. */
  function ifc(r, pe, nome) {
    if (!r || !r.escala_m_por_px) throw new Error("sem escala: informe a largura real do desenho");
    if (!(pe > 0)) throw new Error("informe o pé-direito (m) para o IFC");
    const L = [], id = { n: 0 }, e = s => { id.n++; L.push("#" + id.n + "=" + s + ";"); return "#" + id.n; };
    let g = 0; const guid = () => { const c = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"; g++; let s = "", x = g * 2654435761 % 4294967296;
      for (let i = 0; i < 22; i++) { s += c[(x + i * 7 + g) % 64]; x = Math.floor(x / 3) + 17; } return "'" + s + "'"; };
    const f = v => (Math.round(v * 1e4) / 1e4).toFixed(4), txt = s => "'" + String(s).replace(/'/g, "").replace(/[^\x20-\x7E]/g, "_") + "'";
    const org = e("IFCORGANIZATION($,'Physis Engineering',$,$,$)"), pes = e("IFCPERSON($,'Physis',$,$,$,$,$,$)"), po = e("IFCPERSONANDORGANIZATION(" + pes + "," + org + ",$)");
    const app = e("IFCAPPLICATION(" + org + ",'1','Physis croqui','physis-croqui')"), oh = e("IFCOWNERHISTORY(" + po + "," + app + ",$,.ADDED.,$,$,$,0)");
    const o3 = e("IFCCARTESIANPOINT((0.,0.,0.))"), ax = e("IFCAXIS2PLACEMENT3D(" + o3 + ",$,$)"), ctx = e("IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05," + ax + ",$)");
    const un = e("IFCUNITASSIGNMENT((" + e("IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.)") + "," + e("IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.)") + "))");
    const proj = e("IFCPROJECT(" + guid() + "," + oh + "," + txt(nome || "Planta do rascunho") + ",$,$,$,$,(" + ctx + ")," + un + ")");
    const lp = e("IFCLOCALPLACEMENT($," + ax + ")"), site = e("IFCSITE(" + guid() + "," + oh + ",'Terreno',$,$," + lp + ",$,$,.ELEMENT.,$,$,$,$,$)");
    const bld = e("IFCBUILDING(" + guid() + "," + oh + ",'Edificacao',$,$," + lp + ",$,$,.ELEMENT.,$,$,$)"), sto = e("IFCBUILDINGSTOREY(" + guid() + "," + oh + ",'Terreo',$,$," + lp + ",$,$,.ELEMENT.,0.)");
    e("IFCRELAGGREGATES(" + guid() + "," + oh + ",$,$," + proj + ",(" + site + "))"); e("IFCRELAGGREGATES(" + guid() + "," + oh + ",$,$," + site + ",(" + bld + "))");
    e("IFCRELAGGREGATES(" + guid() + "," + oh + ",$,$," + bld + ",(" + sto + "))");
    const poli = l => e("IFCPOLYLINE((" + l.concat([l[0]]).map(p => e("IFCCARTESIANPOINT((" + f(p[0]) + "," + f(p[1]) + "))")).join(",") + "))");
    const forma = (perfil, alt) => { const sol = e("IFCEXTRUDEDAREASOLID(" + perfil + "," + ax + "," + e("IFCDIRECTION((0.,0.,1.))") + "," + f(alt) + ")");
      return e("IFCPRODUCTDEFINITIONSHAPE($,$,(" + e("IFCSHAPEREPRESENTATION(" + ctx + ",'Body','SweptSolid',(" + sol + "))") + "))"); };
    const espacos = [], ambs = r.ambientes.filter(a => a.laco_m);
    ambs.forEach(a => { const pf = e("IFCARBITRARYCLOSEDPROFILEDEF(.AREA.," + txt(a.nome) + "," + poli(a.laco_m) + ")");
      const sp = e("IFCSPACE(" + guid() + "," + oh + "," + txt(a.nome) + ",$,$," + lp + "," + forma(pf, pe) + "," + txt(a.nome) + ",.ELEMENT.,.INTERNAL.,$)");
      const q = e("IFCQUANTITYAREA('NetFloorArea',$,$," + f(a.area_m2) + ",$)"), eq = e("IFCELEMENTQUANTITY(" + guid() + "," + oh + ",'Qto_SpaceBaseQuantities',$,$,(" + q + "))");
      e("IFCRELDEFINESBYPROPERTIES(" + guid() + "," + oh + ",$,$,(" + sp + ")," + eq + ")"); espacos.push(sp); });
    if (espacos.length) e("IFCRELAGGREGATES(" + guid() + "," + oh + ",$,$," + sto + ",(" + espacos.join(",") + "))");
    let parede = null;
    if (r.paredes_m) { const pf = e("IFCARBITRARYPROFILEDEFWITHVOIDS(.AREA.,'Paredes'," + poli(r.paredes_m) + ",(" + ambs.map(a => poli(a.laco_m)).join(",") + "))");
      parede = e("IFCWALL(" + guid() + "," + oh + ",'Paredes do rascunho',$,$," + lp + "," + forma(pf, pe) + ",$,.NOTDEFINED.)");
      e("IFCRELCONTAINEDINSPATIALSTRUCTURE(" + guid() + "," + oh + ",$,$,(" + parede + ")," + sto + ")"); }
    const cab = "ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('ViewDefinition [DesignTransferView]'),'2;1');\nFILE_NAME(" + txt((nome || "croqui") + ".ifc") + ",'2026-11-24T00:00:00',('Physis'),('Physis Engineering'),'physis-croqui','Physis','');\nFILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\n";
    return cab + L.join("\n") + "\nENDSEC;\nEND-ISO-10303-21;\n";
  }

  /* planta retificada → modelo 3D glTF binário (.glb) para a vista 3D e o render do Blender (24/11/2026). Piso de cada ambiente
     (polígono por recorte de orelhas) e paredes como caixas ao longo dos lados de cada ambiente e do contorno; espessura de
     parede e pé-direito digitados. Eixos do glTF: y para cima. Cores da paleta (piso #EFE8D6, paredes #F4F1EA). */
  function orelhas(l) {                       // triangulação de polígono simples (sem furos), anti-horário
    const p = area(l) < 0 ? l.slice().reverse() : l.slice(), idx = p.map((_, i) => i), tri = [];
    const conv = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) > 1e-12;
    const dentro = (q, a, b, c) => { const s = (u, v, w) => (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0]); return s(a, b, q) >= 0 && s(b, c, q) >= 0 && s(c, a, q) >= 0; };
    let guarda = 0;
    while (idx.length > 3 && guarda++ < 10000) { let achou = false;
      for (let k = 0; k < idx.length; k++) { const i0 = idx[(k + idx.length - 1) % idx.length], i1 = idx[k], i2 = idx[(k + 1) % idx.length], a = p[i0], b = p[i1], c = p[i2];
        if (!conv(a, b, c) || idx.some(j => j !== i0 && j !== i1 && j !== i2 && dentro(p[j], a, b, c))) continue;
        tri.push([a, b, c]); idx.splice(k, 1); achou = true; break; }
      if (!achou) break; }
    if (idx.length === 3) tri.push(idx.map(i => p[i]));
    return tri; }
  function glb(r, pe, esp) {
    if (!r || !r.escala_m_por_px) throw new Error("sem escala: informe a largura real do desenho");
    if (!(pe > 0)) throw new Error("informe o pé-direito (m)");
    if (!(esp > 0)) throw new Error("informe a espessura das paredes (m)");
    const malhas = { piso: [], parede: [] };
    const tri3 = (m, a, b, c) => m.push(a, b, c);
    (r.ambientes || []).filter(a => a.laco_m).forEach(a => orelhas(a.laco_m).forEach(t => tri3(malhas.piso, [t[0][0], 0, -t[0][1]], [t[1][0], 0, -t[1][1]], [t[2][0], 0, -t[2][1]])));
    const caixa = (p, q) => { const dx = q[0] - p[0], dy = q[1] - p[1], L = Math.hypot(dx, dy); if (L < 1e-6) return;
      const nx = -dy / L * esp / 2, ny = dx / L * esp / 2, c = [[p[0] + nx, p[1] + ny], [q[0] + nx, q[1] + ny], [q[0] - nx, q[1] - ny], [p[0] - nx, p[1] - ny]];
      const v = (k, z) => [c[k][0], z, -c[k][1]], m = malhas.parede, quad = (a, b, cc, d) => { tri3(m, a, b, cc); tri3(m, a, cc, d); };
      quad(v(0, 0), v(1, 0), v(1, pe), v(0, pe)); quad(v(2, 0), v(3, 0), v(3, pe), v(2, pe)); quad(v(1, 0), v(2, 0), v(2, pe), v(1, pe)); quad(v(3, 0), v(0, 0), v(0, pe), v(3, pe));
      quad(v(0, pe), v(1, pe), v(2, pe), v(3, pe)); quad(v(3, 0), v(2, 0), v(1, 0), v(0, 0)); };
    [r.paredes_m].concat((r.ambientes || []).map(a => a.laco_m)).filter(Boolean).forEach(l => l.forEach((p, i) => caixa(p, l[(i + 1) % l.length])));
    // glTF 2.0 binário: um buffer, duas primitivas (piso e paredes) com normais planas
    const partes = [], vistas = [], acess = [], prims = []; let off = 0;
    Object.entries(malhas).forEach(([nome, pts], k) => { if (!pts.length) return;
      const pos = new Float32Array(pts.length * 3), nor = new Float32Array(pts.length * 3), mn = [1e9, 1e9, 1e9], mx = [-1e9, -1e9, -1e9];
      for (let t = 0; t < pts.length; t += 3) { const a = pts[t], b = pts[t + 1], c = pts[t + 2], u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], w = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
        let n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]; const l = Math.hypot(...n) || 1; n = n.map(x => x / l);
        if (nome === "piso" && n[1] < 0) n = n.map(x => -x);
        [a, b, c].forEach((q, j) => { for (let e = 0; e < 3; e++) { pos[(t + j) * 3 + e] = q[e]; nor[(t + j) * 3 + e] = n[e]; mn[e] = Math.min(mn[e], q[e]); mx[e] = Math.max(mx[e], q[e]); } }); }
      [pos, nor].forEach((arr, j) => { const b = new Uint8Array(arr.buffer); partes.push(b); vistas.push({ buffer: 0, byteOffset: off, byteLength: b.length, target: 34962 }); off += b.length;
        acess.push(Object.assign({ bufferView: vistas.length - 1, componentType: 5126, count: pts.length, type: "VEC3" }, j === 0 ? { min: mn, max: mx } : {})); });
      prims.push({ attributes: { POSITION: acess.length - 2, NORMAL: acess.length - 1 }, material: k, mode: 4 }); });
    const cor = h => [parseInt(h.slice(1, 3), 16) / 255, parseInt(h.slice(3, 5), 16) / 255, parseInt(h.slice(5, 7), 16) / 255, 1];
    const json = { asset: { version: "2.0", generator: "Physis croqui" }, scene: 0, scenes: [{ nodes: [0] }], nodes: [{ mesh: 0, name: "planta" }],
      meshes: [{ name: "planta", primitives: prims }], materials: [{ name: "piso", pbrMetallicRoughness: { baseColorFactor: cor("#EFE8D6"), metallicFactor: 0, roughnessFactor: 0.9 }, doubleSided: true },
        { name: "paredes", pbrMetallicRoughness: { baseColorFactor: cor("#F4F1EA"), metallicFactor: 0, roughnessFactor: 0.8 } }],
      accessors: acess, bufferViews: vistas, buffers: [{ byteLength: off }] };
    let js = new TextEncoder().encode(JSON.stringify(json)); const pj = (4 - js.length % 4) % 4; if (pj) { const t = new Uint8Array(js.length + pj); t.set(js); t.fill(32, js.length); js = t; }
    const total = 12 + 8 + js.length + 8 + off, out = new Uint8Array(total), dv = new DataView(out.buffer);
    dv.setUint32(0, 0x46546C67, true); dv.setUint32(4, 2, true); dv.setUint32(8, total, true);
    dv.setUint32(12, js.length, true); dv.setUint32(16, 0x4E4F534A, true); out.set(js, 20);
    let o = 20 + js.length; dv.setUint32(o, off, true); dv.setUint32(o + 4, 0x004E4942, true); o += 8; partes.forEach(b => { out.set(b, o); o += b.length; });
    return out; }
  w.PhysisCroqui = { retificar, simplificar, deImagem, anguloDominante, ifc, glb, orelhas };
})(typeof window !== "undefined" ? window : this);
