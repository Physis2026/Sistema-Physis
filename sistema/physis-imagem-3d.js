/* physis-imagem-3d.js — da imagem (ou do SVG) para o CAD 2D e o modelo 3D, no navegador, sem internet e sem biblioteca de
   terceiros. Pedido da dona (20/11/2026, Modelagem 3D da InovaSTEM, subaba "Enviar arquivo").
   Contrato:
     window.PhysisImagem3D = {
       mascara(rgba, nx, ny, limiar, inverter)  → Uint8Array nx·ny (1 = material): escuro vira material; transparente = fundo
       contornos(M, nx, ny, celula_mm, tolerancia_celulas) → [[ [x,y], ... ], ...] laços fechados em mm (y para cima),
                                                  pelas bordas das células e simplificados (Douglas-Peucker)
       svg(lacos, largura_mm, altura_mm) / dxf(lacos) → texto do CAD 2D (SVG em mm; DXF R12 com POLYLINE fechadas)
       relevo(M, nx, ny, celula_mm, altura_mm, base_mm) → Float32Array no formato do Physis 3D (9 números por triângulo):
                                                  extrusão das células de material, com base opcional por baixo de tudo
       testes() → peças de teste de impressão geradas aqui (cubo de calibração, balanço, ponte, espessura de parede),
                  cada uma com { id, nome, medidas, observar, T }
       autoteste() → [{ nome, ok, info }]
     }
   Os arquivos STL e 3MF são escritos pelas funções do motor do Physis 3D (window.PHYSIS3D.escreverSTL / escrever3MF);
   este módulo não muda nenhuma função nem conta do motor. Medidas de conferência: PHYSIS3D.medir. */
(function () {
"use strict";

/* ════════ imagem → máscara ════════ */
function mascara(rgba, nx, ny, limiar, inverter) {
  const M = new Uint8Array(nx * ny), L = limiar == null ? 128 : +limiar;
  for (let k = 0; k < nx * ny; k++) {
    const r = rgba[4 * k], g = rgba[4 * k + 1], b = rgba[4 * k + 2], a = rgba[4 * k + 3] / 255;
    const lum = 255 - a * (255 - (0.2126 * r + 0.7152 * g + 0.0722 * b));       // transparente conta como branco
    const escuro = lum < L;
    M[k] = (inverter ? !escuro : escuro) ? 1 : 0;
  }
  return M;
}

/* ════════ máscara → contornos (bordas das células, encadeadas e simplificadas) ════════ */
function dp(pts, tol) {                     // Douglas-Peucker num trecho aberto
  if (pts.length < 3) return pts.slice();
  const a = pts[0], b = pts[pts.length - 1], dx = b[0] - a[0], dy = b[1] - a[1], n = Math.hypot(dx, dy) || 1;
  let im = 0, dm = -1;
  for (let i = 1; i < pts.length - 1; i++) {
    const d = Math.abs(dy * (pts[i][0] - a[0]) - dx * (pts[i][1] - a[1])) / n;
    if (d > dm) { dm = d; im = i; }
  }
  if (dm <= tol) return [a, b];
  const e = dp(pts.slice(0, im + 1), tol), f = dp(pts.slice(im), tol);
  return e.slice(0, -1).concat(f);
}
function simplificarLaco(l, tol) {
  if (l.length < 4 || !(tol > 0)) return l;
  let im = 0, dm = -1;                      // corta o laço no ponto mais longe do primeiro
  for (let i = 1; i < l.length; i++) { const d = Math.hypot(l[i][0] - l[0][0], l[i][1] - l[0][1]); if (d > dm) { dm = d; im = i; } }
  const s = dp(l.slice(0, im + 1), tol).slice(0, -1).concat(dp(l.slice(im).concat([l[0]]), tol).slice(0, -1));
  // o corte pode cair no meio de um lado: tira os pontos que ficaram alinhados com os vizinhos (laço fechado)
  let mudou = true;
  while (mudou && s.length > 3) {
    mudou = false;
    for (let i = 0; i < s.length && s.length > 3; i++) {
      const a = s[(i + s.length - 1) % s.length], b = s[i], c = s[(i + 1) % s.length], dx = c[0] - a[0], dy = c[1] - a[1];
      if (Math.abs(dy * (b[0] - a[0]) - dx * (b[1] - a[1])) / (Math.hypot(dx, dy) || 1) <= tol) { s.splice(i, 1); mudou = true; i--; }
    }
  }
  return s.length >= 3 ? s : l;
}
function contornos(M, nx, ny, cel, tol) {
  cel = cel || 1;
  const on = (i, j) => i >= 0 && j >= 0 && i < nx && j < ny && M[j * nx + i] === 1;
  const prox = new Map(), chave = (x, y) => x + "," + y;
  const add = (x0, y0, x1, y1) => { const k = chave(x0, y0); (prox.get(k) || prox.set(k, []).get(k)).push([x1, y1]); };
  // grade de vértices: x = i, y = ny − j (y para cima); arestas com o material à esquerda
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    if (!on(i, j)) continue;
    const xa = i, xb = i + 1, ya = ny - j - 1, yb = ny - j;
    if (!on(i, j + 1)) add(xa, ya, xb, ya);           // embaixo, para a direita
    if (!on(i + 1, j)) add(xb, ya, xb, yb);           // à direita, para cima
    if (!on(i, j - 1)) add(xb, yb, xa, yb);           // em cima, para a esquerda
    if (!on(i - 1, j)) add(xa, yb, xa, ya);           // à esquerda, para baixo
  }
  const lacos = [];
  for (const [k0] of prox) {
    while ((prox.get(k0) || []).length) {
      const l = []; let k = k0, guarda = 0;
      do {
        const lista = prox.get(k), p = lista.pop(); const xy = k.split(",").map(Number);
        l.push(xy); k = chave(p[0], p[1]);
        if (++guarda > 4 * nx * ny + 8) break;
      } while (k !== k0 && (prox.get(k) || []).length);
      if (l.length >= 3) lacos.push(simplificarLaco(l, tol == null ? 0.5 : tol).map(p => [p[0] * cel, p[1] * cel]));
    }
  }
  return lacos;
}

/* ════════ CAD 2D: SVG e DXF ════════ */
const n4 = v => (Math.round(v * 1e4) / 1e4).toString();
function svg(lacos, largura, altura) {
  const d = lacos.map(l => "M" + l.map(p => n4(p[0]) + " " + n4(altura - p[1])).join(" L") + " Z").join(" ");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${n4(largura)}mm" height="${n4(altura)}mm" viewBox="0 0 ${n4(largura)} ${n4(altura)}">`
    + `<path d="${d}" fill="#000000" fill-rule="evenodd"/></svg>\n`;
}
function dxf(lacos) {
  const L = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$INSUNITS", "70", "4", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"];
  lacos.forEach(l => {
    L.push("0", "POLYLINE", "8", "CONTORNO", "66", "1", "70", "1");
    l.forEach(p => L.push("0", "VERTEX", "8", "CONTORNO", "10", n4(p[0]), "20", n4(p[1]), "30", "0"));
    L.push("0", "SEQEND", "8", "CONTORNO");
  });
  L.push("0", "ENDSEC", "0", "EOF");
  return L.join("\r\n") + "\r\n";
}

/* ════════ 3D: faces com a normal pedida (a ordem dos vértices é acertada pela normal) ════════ */
function quad(out, p0, p1, p2, p3, n) {
  const ux = p1[0] - p0[0], uy = p1[1] - p0[1], uz = p1[2] - p0[2], vx = p2[0] - p0[0], vy = p2[1] - p0[1], vz = p2[2] - p0[2];
  const c = [uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx];
  const pts = c[0] * n[0] + c[1] * n[1] + c[2] * n[2] >= 0 ? [p0, p1, p2, p3] : [p3, p2, p1, p0];
  out.push(...pts[0], ...pts[1], ...pts[2], ...pts[0], ...pts[2], ...pts[3]);
}
/* campo de alturas (h por célula, 0 = vazio) → malha fechada */
function campoDeAlturas(H, nx, ny, cel) {
  const out = [], h = (i, j) => (i >= 0 && j >= 0 && i < nx && j < ny) ? H[j * nx + i] : 0;
  // as paredes são cortadas em todos os níveis que existem, para as arestas verticais coincidirem (malha fechada)
  const niveis = Array.from(new Set([0].concat(Array.from(H)))).sort((a, b) => a - b);
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    const z = h(i, j); if (!(z > 0)) continue;
    const x0 = i * cel, x1 = x0 + cel, y0 = (ny - j - 1) * cel, y1 = y0 + cel;
    quad(out, [x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z], [0, 0, 1]);
    quad(out, [x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0], [0, 0, -1]);
    const lado = (zv, a, b, n) => { for (let k = 0; k < niveis.length - 1; k++) { const za = niveis[k], zb = niveis[k + 1];
      if (za >= zv && zb <= z) quad(out, [a[0], a[1], za], [b[0], b[1], za], [b[0], b[1], zb], [a[0], a[1], zb], n); } };
    lado(h(i + 1, j), [x1, y0], [x1, y1], [1, 0, 0]);
    lado(h(i - 1, j), [x0, y1], [x0, y0], [-1, 0, 0]);
    lado(h(i, j - 1), [x1, y1], [x0, y1], [0, 1, 0]);       // célula de cima na imagem = +y
    lado(h(i, j + 1), [x0, y0], [x1, y0], [0, -1, 0]);
  }
  return new Float32Array(out);
}
function relevo(M, nx, ny, cel, altura, base) {
  altura = +altura || 0; base = +base || 0;
  if (!(cel > 0) || !(altura > 0 || base > 0)) throw new Error("altura e base não podem ser as duas zero");
  const H = new Float32Array(nx * ny);
  let algum = false;
  for (let k = 0; k < nx * ny; k++) { H[k] = (M[k] ? altura : 0) + base; if (H[k] > 0) algum = true; }
  if (!algum) throw new Error("nenhuma célula de material: ajuste o limiar ou inverta");
  return campoDeAlturas(H, nx, ny, cel);
}

/* ════════ foto: escala de cinza, suavização, limiar automático (Otsu), ruído e fundo ════════ */
function cinza(rgba, n) {
  const g = new Float32Array(n);
  for (let k = 0; k < n; k++) { const a = rgba[4 * k + 3] / 255; g[k] = 255 - a * (255 - (0.2126 * rgba[4 * k] + 0.7152 * rgba[4 * k + 1] + 0.0722 * rgba[4 * k + 2])); }
  return g;
}
/* média em caixa separável, aplicada 3 vezes (aproxima uma gaussiana); raio em células */
function suavizar(g, nx, ny, raio) {
  raio = Math.max(0, Math.round(raio || 0));
  if (!raio) return Float32Array.from(g);
  let a = Float32Array.from(g), b = new Float32Array(g.length);
  for (let it = 0; it < 3; it++) {
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      let s = 0, c = 0; for (let d = -raio; d <= raio; d++) { const x = i + d; if (x >= 0 && x < nx) { s += a[j * nx + x]; c++; } } b[j * nx + i] = s / c; }
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      let s = 0, c = 0; for (let d = -raio; d <= raio; d++) { const y = j + d; if (y >= 0 && y < ny) { s += b[y * nx + i]; c++; } } a[j * nx + i] = s / c; }
  }
  return a;
}
/* limiar de Otsu (1979): o que separa melhor os dois grupos do histograma de 256 tons */
function otsu(g) {
  const h = new Float64Array(256); for (let k = 0; k < g.length; k++) h[Math.max(0, Math.min(255, Math.round(g[k])))]++;
  const n = g.length; let soma = 0; for (let i = 0; i < 256; i++) soma += i * h[i];
  let sB = 0, wB = 0, melhor = 0, lim = 128;
  for (let t = 0; t < 256; t++) {
    wB += h[t]; if (!wB) continue; const wF = n - wB; if (!wF) break;
    sB += t * h[t]; const mB = sB / wB, mF = (soma - sB) / wF, v = wB * wF * (mB - mF) * (mB - mF);
    if (v > melhor) { melhor = v; lim = t + 0.5; }
  }
  return lim;
}
/* componentes ligadas (vizinhança de 4) do valor v; devolve rótulos, tamanhos e se tocam a borda */
function componentes(M, nx, ny, v) {
  const rot = new Int32Array(nx * ny).fill(-1), tam = [], borda = [], pilha = [];
  for (let k = 0; k < nx * ny; k++) {
    if (M[k] !== v || rot[k] >= 0) continue;
    const c = tam.length; tam.push(0); borda.push(false); rot[k] = c; pilha.push(k);
    while (pilha.length) {
      const q = pilha.pop(), i = q % nx, j = (q - i) / nx; tam[c]++;
      if (i === 0 || j === 0 || i === nx - 1 || j === ny - 1) borda[c] = true;
      const viz = [i > 0 ? q - 1 : -1, i < nx - 1 ? q + 1 : -1, j > 0 ? q - nx : -1, j < ny - 1 ? q + nx : -1];
      for (const w of viz) if (w >= 0 && M[w] === v && rot[w] < 0) { rot[w] = c; pilha.push(w); }
    }
  }
  return { rot, tam, borda };
}
/* ruído: tira as manchas de material menores que areaMin células e tapa os furinhos menores que areaMin;
   fundo: tira o material que toca a borda da foto (o fundo escuro em volta da peça); maior: fica só a maior peça */
function limpar(M, nx, ny, op) {
  op = op || {}; const R = Uint8Array.from(M), am = Math.max(0, Math.round(op.areaMin || 0));
  if (op.fundo) { const c = componentes(R, nx, ny, 1); for (let k = 0; k < R.length; k++) if (R[k] && c.borda[c.rot[k]]) R[k] = 0; }
  if (am > 0) {
    let c = componentes(R, nx, ny, 1); for (let k = 0; k < R.length; k++) if (R[k] && c.tam[c.rot[k]] < am) R[k] = 0;
    c = componentes(R, nx, ny, 0); for (let k = 0; k < R.length; k++) if (!R[k] && !c.borda[c.rot[k]] && c.tam[c.rot[k]] < am) R[k] = 1;
  }
  if (op.maior) { const c = componentes(R, nx, ny, 1); let mx = -1, im = -1; c.tam.forEach((t, i) => { if (t > mx) { mx = t; im = i; } });
    for (let k = 0; k < R.length; k++) if (R[k] && c.rot[k] !== im) R[k] = 0; }
  return R;
}
/* tudo junto: foto (RGBA) → máscara pronta; op = { limiar (null = Otsu), inverter, suavizar, areaMin, fundo, maior } */
function processarFoto(rgba, nx, ny, op) {
  op = op || {};
  const g = suavizar(cinza(rgba, nx * ny), nx, ny, op.suavizar || 0), auto = otsu(g);
  const L = op.limiar == null || op.limiar === "" ? auto : +op.limiar, M = new Uint8Array(nx * ny);
  for (let k = 0; k < nx * ny; k++) { const escuro = g[k] < L; M[k] = (op.inverter ? !escuro : escuro) ? 1 : 0; }
  return { M: limpar(M, nx, ny, op), limiar: L, otsu: auto, cinza: g };
}

/* ════════ polígonos: extrusão com furos (recorte de orelhas, com ponte para cada furo) ════════ */
const area2 = l => { let a = 0; for (let i = 0; i < l.length; i++) { const p = l[i], q = l[(i + 1) % l.length]; a += p[0] * q[1] - q[0] * p[1]; } return a / 2; };
function dentro(p, l) { let c = false; for (let i = 0, j = l.length - 1; i < l.length; j = i++) { const a = l[i], b = l[j];
  if ((a[1] > p[1]) !== (b[1] > p[1]) && p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]) c = !c; } return c; }
function cruza(a, b, c, d) {
  const o = (p, q, r) => (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
  const d1 = o(c, d, a), d2 = o(c, d, b), d3 = o(a, b, c), d4 = o(a, b, d);
  return ((d1 > 1e-12 && d2 < -1e-12) || (d1 < -1e-12 && d2 > 1e-12)) && ((d3 > 1e-12 && d4 < -1e-12) || (d3 < -1e-12 && d4 > 1e-12));
}
function limparLaco(l) { const o = []; l.forEach(p => { const u = o[o.length - 1]; if (!u || Math.hypot(u[0] - p[0], u[1] - p[1]) > 1e-9) o.push([+p[0], +p[1]]); });
  while (o.length > 2 && Math.hypot(o[0][0] - o[o.length - 1][0], o[0][1] - o[o.length - 1][1]) <= 1e-9) o.pop(); return o; }
/* agrupa laços em peças: cada contorno de fora (sentido anti-horário) com os furos dentro dele (horário) */
function agrupar(lacos) {
  const ls = lacos.map(limparLaco).filter(l => l.length >= 3 && Math.abs(area2(l)) > 1e-9);
  const prof = ls.map((l, i) => ls.reduce((n, m, j) => n + (j !== i && dentro(l[0], m) ? 1 : 0), 0));
  const fora = [];
  ls.forEach((l, i) => { if (prof[i] % 2 === 0) fora.push({ i, l: area2(l) < 0 ? l.slice().reverse() : l, furos: [] }); });
  ls.forEach((l, i) => { if (prof[i] % 2 === 1) {
    let dono = null; fora.forEach(f => { if (dentro(l[0], f.l) && prof[f.i] === prof[i] - 1 && (!dono || Math.abs(area2(f.l)) < Math.abs(area2(dono.l)))) dono = f; });
    if (dono) dono.furos.push(area2(l) > 0 ? l.slice().reverse() : l); } });
  return fora;
}
function costurar(fora, furos) {
  let pol = fora.slice();
  furos.slice().sort((a, b) => Math.max(...b.map(p => p[0])) - Math.max(...a.map(p => p[0]))).forEach(h => {
    let im = 0; h.forEach((p, i) => { if (p[0] > h[im][0]) im = i; });
    const M = h[im], todos = [pol].concat(furos);
    const cand = pol.map((p, i) => [Math.hypot(p[0] - M[0], p[1] - M[1]), i]).sort((a, b) => a[0] - b[0]);
    let iv = cand[0][1];
    for (const [, i] of cand) {
      const V = pol[i]; let livre = true;
      for (const l of todos) { for (let k = 0; k < l.length && livre; k++) { if (cruza(M, V, l[k], l[(k + 1) % l.length])) livre = false; } if (!livre) break; }
      if (livre) { iv = i; break; }
    }
    const volta = h.slice(im).concat(h.slice(0, im + 1));
    pol = pol.slice(0, iv + 1).concat(volta, [pol[iv]], pol.slice(iv + 1));
  });
  return pol;
}
function orelhas(pol) {
  const idx = pol.map((_, i) => i), tris = [], P = pol, conv = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) > 1e-12;
  const dentroTri = (p, a, b, c) => { const s = (x, y, z) => (y[0] - x[0]) * (z[1] - x[1]) - (y[1] - x[1]) * (z[0] - x[0]);
    return s(a, b, p) >= -1e-12 && s(b, c, p) >= -1e-12 && s(c, a, p) >= -1e-12; };
  let guarda = 0;
  while (idx.length > 3 && guarda++ < 100000) {
    let achou = false;
    for (let k = 0; k < idx.length; k++) {
      const ia = idx[(k + idx.length - 1) % idx.length], ib = idx[k], ic = idx[(k + 1) % idx.length], a = P[ia], b = P[ib], c = P[ic];
      if (!conv(a, b, c)) continue;
      let vazio = true;
      for (const j of idx) { if (j === ia || j === ib || j === ic) continue; const p = P[j];
        if ((p[0] === a[0] && p[1] === a[1]) || (p[0] === b[0] && p[1] === b[1]) || (p[0] === c[0] && p[1] === c[1])) continue;
        if (dentroTri(p, a, b, c)) { vazio = false; break; } }
      if (vazio) { tris.push([a, b, c]); idx.splice(k, 1); achou = true; break; }
    }
    if (!achou) { const ia = idx[0], ib = idx[1], ic = idx[2]; tris.push([P[ia], P[ib], P[ic]]); idx.splice(1, 1); }   // laço ruim: segue sem travar
  }
  if (idx.length === 3) tris.push([P[idx[0]], P[idx[1]], P[idx[2]]]);
  return tris;
}
/* laços fechados (mm; furos pela paridade) → sólido de altura h (z de 0 a h), no formato do Physis 3D */
function extrudar(lacos, h) {
  h = +h; if (!(h > 0)) throw new Error("a altura da extrusão precisa ser maior que zero");
  const out = [];
  agrupar(lacos).forEach(g => {
    orelhas(costurar(g.l, g.furos)).forEach(([a, b, c]) => { out.push(a[0], a[1], h, b[0], b[1], h, c[0], c[1], h, a[0], a[1], 0, c[0], c[1], 0, b[0], b[1], 0); });
    [g.l].concat(g.furos).forEach(l => l.forEach((p, i) => { const q = l[(i + 1) % l.length], n = [q[1] - p[1], -(q[0] - p[0]), 0];
      quad(out, [p[0], p[1], 0], [q[0], q[1], 0], [q[0], q[1], h], [p[0], p[1], h], n); }));
  });
  if (!out.length) throw new Error("nenhum contorno fechado para extrudar");
  return new Float32Array(out);
}
/* formas paramétricas (mm), centradas na origem */
const PRIM = {
  retangulo: (w, d) => [[[-w / 2, -d / 2], [w / 2, -d / 2], [w / 2, d / 2], [-w / 2, d / 2]]],
  circulo: (diam, n) => { n = Math.max(8, Math.round(n || 48)); const r = diam / 2, l = []; for (let i = 0; i < n; i++) { const a = 2 * Math.PI * i / n; l.push([r * Math.cos(a), r * Math.sin(a)]); } return [l]; },
  chapaComFuro: (w, d, furo) => { if (!(furo > 0 && furo < Math.min(w, d))) throw new Error("o furo precisa ser menor que a chapa"); return PRIM.retangulo(w, d).concat([PRIM.circulo(furo, 48)[0].reverse()]); },
  perfil: (tipo, a, b, e) => { if (!(e > 0 && e < Math.min(a, b))) throw new Error("a espessura precisa ser menor que as abas");
    if (tipo === "L") return [[[0, 0], [a, 0], [a, e], [e, e], [e, b], [0, b]]];
    if (tipo === "U") return [[[0, 0], [a, 0], [a, b], [a - e, b], [a - e, e], [e, e], [e, b], [0, b]]];
    if (tipo === "T") return [[[0, b - e], [(a - e) / 2, b - e], [(a - e) / 2, 0], [(a + e) / 2, 0], [(a + e) / 2, b - e], [a, b - e], [a, b], [0, b]]];
    throw new Error("perfil: L, U ou T"); }
};

/* ════════ DXF 2D: LINE, LWPOLYLINE, POLYLINE, CIRCLE e ARC → laços fechados e linhas abertas (mm) ════════ */
function lerDxf(texto) {
  const L = String(texto).replace(/\r/g, "").split("\n"), pares = [];
  for (let i = 0; i + 1 < L.length; i += 2) pares.push([parseInt(L[i], 10), L[i + 1].trim()]);
  const ents = []; let sec = "", e = null;
  pares.forEach(([c, v]) => {
    if (c === 0) { if (e) ents.push(e); e = null;
      if (v === "SECTION" || v === "ENDSEC" || v === "EOF") { sec = v === "SECTION" ? "?" : ""; return; }
      if (sec === "ENTITIES") e = { tipo: v, c: [] }; return; }
    if (c === 2 && sec === "?") { sec = v; return; }
    if (e) e.c.push([c, v]);
  });
  if (e) ents.push(e);
  const g = (en, cod) => { const x = en.c.find(p => p[0] === cod); return x ? parseFloat(x[1]) : 0; };
  const fechados = [], abertos = [], segs = [], avisos = new Set();
  let poli = null;
  ents.forEach(en => {
    if (en.tipo === "LINE") segs.push([[g(en, 10), g(en, 20)], [g(en, 11), g(en, 21)]]);
    else if (en.tipo === "LWPOLYLINE") { const pts = [], fl = g(en, 70); let x = null;
      en.c.forEach(([c, v]) => { if (c === 10) x = parseFloat(v); if (c === 20 && x != null) { pts.push([x, parseFloat(v)]); x = null; } if (c === 42 && parseFloat(v)) avisos.add("arcos dentro de polilinhas (bulge) viram retas"); });
      ((fl & 1) ? fechados : abertos).push(pts); }
    else if (en.tipo === "POLYLINE") poli = { pts: [], fechada: (g(en, 70) & 1) === 1 };
    else if (en.tipo === "VERTEX" && poli) poli.pts.push([g(en, 10), g(en, 20)]);
    else if (en.tipo === "SEQEND" && poli) { (poli.fechada ? fechados : abertos).push(poli.pts); poli = null; }
    else if (en.tipo === "CIRCLE") { const l = PRIM.circulo(2 * g(en, 40), 64)[0].map(p => [p[0] + g(en, 10), p[1] + g(en, 20)]); fechados.push(l); }
    else if (en.tipo === "ARC") { const r = g(en, 40), a0 = g(en, 50) * Math.PI / 180; let a1 = g(en, 51) * Math.PI / 180; if (a1 <= a0) a1 += 2 * Math.PI;
      const n = Math.max(4, Math.ceil((a1 - a0) / (Math.PI / 32))), pts = []; for (let i = 0; i <= n; i++) { const a = a0 + (a1 - a0) * i / n; pts.push([g(en, 10) + r * Math.cos(a), g(en, 20) + r * Math.sin(a)]); }
      segs.push(pts); }
    else if (["TEXT", "MTEXT", "DIMENSION", "HATCH", "INSERT", "SPLINE", "ELLIPSE", "POINT"].indexOf(en.tipo) >= 0) avisos.add(en.tipo + " ainda não é lido (fica de fora)");
  });
  // encadeia linhas e arcos soltos pelos pontos das pontas
  const k = p => Math.round(p[0] * 1e4) + "," + Math.round(p[1] * 1e4), usados = new Set();
  segs.forEach((s0, i0) => {
    if (usados.has(i0)) return; usados.add(i0); let cad = s0.slice(), mudou = true;
    while (mudou) { mudou = false;
      for (let i = 0; i < segs.length; i++) { if (usados.has(i)) continue; const s = segs[i], ini = k(cad[0]), fim = k(cad[cad.length - 1]);
        if (k(s[0]) === fim) cad = cad.concat(s.slice(1)); else if (k(s[s.length - 1]) === fim) cad = cad.concat(s.slice(0, -1).reverse());
        else if (k(s[s.length - 1]) === ini) cad = s.slice(0, -1).concat(cad); else if (k(s[0]) === ini) cad = s.slice(1).reverse().concat(cad); else continue;
        usados.add(i); mudou = true; } }
    if (cad.length > 3 && k(cad[0]) === k(cad[cad.length - 1])) fechados.push(cad.slice(0, -1)); else abertos.push(cad);
  });
  const unid = pares.findIndex(p => p[0] === 9 && p[1] === "$INSUNITS");
  return { lacos: fechados.filter(l => l.length >= 3), linhas: abertos.filter(l => l.length >= 2), avisos: Array.from(avisos),
    unidade: unid >= 0 && pares[unid + 1] ? ({ 1: "polegada", 4: "mm", 5: "cm", 6: "m" }[parseInt(pares[unid + 1][1], 10)] || "") : "" };
}

/* ════════ transformação, caixas e colisão simples ════════ */
function caixaDe(T) { const mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < T.length; i += 3) for (let k = 0; k < 3; k++) { const v = T[i + k]; if (v < mn[k]) mn[k] = v; if (v > mx[k]) mx[k] = v; } return { min: mn, max: mx }; }
/* p' = R(rot em graus, z·y·x) · (p − pivô) · escala + pivô + posição */
function transformar(T, pos, rot, esc, pivo) {
  pos = pos || [0, 0, 0]; rot = rot || [0, 0, 0]; esc = esc == null ? 1 : +esc; pivo = pivo || [0, 0, 0];
  const r = rot.map(g => g * Math.PI / 180), [cx, cy, cz] = r.map(Math.cos), [sx, sy, sz] = r.map(Math.sin);
  const R = [[cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx], [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx], [-sy, cy * sx, cy * cx]];
  const o = new Float32Array(T.length), inv = esc < 0;
  for (let i = 0; i < T.length; i += 3) { const x = (T[i] - pivo[0]) * esc, y = (T[i + 1] - pivo[1]) * esc, z = (T[i + 2] - pivo[2]) * esc;
    for (let k = 0; k < 3; k++) o[i + k] = R[k][0] * x + R[k][1] * y + R[k][2] * z + pivo[k] + pos[k]; }
  if (inv) for (let i = 0; i < o.length; i += 9) for (let k = 0; k < 3; k++) { const t = o[i + 3 + k]; o[i + 3 + k] = o[i + 6 + k]; o[i + 6 + k] = t; }
  return o;
}
function juntar(lista) { let n = 0; lista.forEach(T => n += T.length); const o = new Float32Array(n); let k = 0; lista.forEach(T => { o.set(T, k); k += T.length; }); return o; }
/* pares de itens cujas caixas se cruzam (encostar não conta); itens = [{ nome, T }] */
function colisoes(itens, folga) {
  folga = folga == null ? 0.01 : folga; const cx = itens.map(it => caixaDe(it.T)), out = [];
  for (let a = 0; a < itens.length; a++) for (let b = a + 1; b < itens.length; b++) {
    const A = cx[a], B = cx[b]; let cruzam = true, vol = 1;
    for (let k = 0; k < 3; k++) { const s = Math.min(A.max[k], B.max[k]) - Math.max(A.min[k], B.min[k]); if (s <= folga) { cruzam = false; break; } vol *= s; }
    if (cruzam) out.push({ a, b, volume_mm3: vol });
  }
  return out;
}

/* ════════ 3MF de montagem (um objeto por peça, com cor) e IFC4 do modelo editado ════════ */
let TAB_CRC = null;
function crc32(b) { if (!TAB_CRC) { TAB_CRC = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; TAB_CRC[n] = c >>> 0; } }
  let c = 0xFFFFFFFF; for (let i = 0; i < b.length; i++) c = TAB_CRC[(c ^ b[i]) & 255] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
/* ZIP sem compressão (método 0), como o 3MF aceita */
function zipGuardado(arquivos) {
  const enc = new TextEncoder(), partes = [], central = []; let pos = 0;
  arquivos.forEach(([nome, dados]) => {
    const n = enc.encode(nome), d = typeof dados === "string" ? enc.encode(dados) : dados, crc = crc32(d);
    const h = new DataView(new ArrayBuffer(30)); h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint32(14, crc, true);
    h.setUint32(18, d.length, true); h.setUint32(22, d.length, true); h.setUint16(26, n.length, true);
    const c = new DataView(new ArrayBuffer(46)); c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint32(16, crc, true);
    c.setUint32(20, d.length, true); c.setUint32(24, d.length, true); c.setUint16(28, n.length, true); c.setUint32(42, pos, true);
    partes.push(new Uint8Array(h.buffer), n, d); central.push(new Uint8Array(c.buffer), n); pos += 30 + n.length + d.length;
  });
  const tc = central.reduce((s, x) => s + x.length, 0), f = new DataView(new ArrayBuffer(22));
  f.setUint32(0, 0x06054b50, true); f.setUint16(8, arquivos.length, true); f.setUint16(10, arquivos.length, true); f.setUint32(12, tc, true); f.setUint32(16, pos, true);
  const tudo = partes.concat(central, [new Uint8Array(f.buffer)]), out = new Uint8Array(tudo.reduce((s, x) => s + x.length, 0)); let k = 0;
  tudo.forEach(x => { out.set(x, k); k += x.length; }); return out;
}
const xmlEsc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;" }[c]));
const NS3MF = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02";
function escrever3MFMontagem(itens) {
  const cores = itens.map(it => /^#[0-9A-Fa-f]{6}$/.test(it.cor || "") ? it.cor.toUpperCase() : "#D9D3C2");
  let objs = "", build = "";
  itens.forEach((it, o) => {
    const vs = [], idx = new Map(), ts = [], T = it.T, ch = i => T[i].toFixed(4) + "," + T[i + 1].toFixed(4) + "," + T[i + 2].toFixed(4);
    for (let i = 0; i < T.length; i += 9) { const t = [];
      for (let k = 0; k < 3; k++) { const c = ch(i + 3 * k); let j = idx.get(c); if (j == null) { j = vs.length; idx.set(c, j); vs.push(`<vertex x="${T[i + 3 * k]}" y="${T[i + 3 * k + 1]}" z="${T[i + 3 * k + 2]}"/>`); } t.push(j); }
      if (t[0] !== t[1] && t[1] !== t[2] && t[0] !== t[2]) ts.push(`<triangle v1="${t[0]}" v2="${t[1]}" v3="${t[2]}"/>`); }
    objs += `<object id="${o + 2}" type="model" name="${xmlEsc(it.nome)}" pid="1" pindex="${o}"><mesh><vertices>${vs.join("")}</vertices><triangles>${ts.join("")}</triangles></mesh></object>`;
    build += `<item objectid="${o + 2}"/>`;
  });
  const mats = itens.map((it, o) => `<base name="${xmlEsc(it.material || it.nome)}" displaycolor="${cores[o]}"/>`).join("");
  const modelo = `<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" xml:lang="pt-BR" xmlns="${NS3MF}"><metadata name="Application">Physis 3D · montagem</metadata><resources><basematerials id="1">${mats}</basematerials>${objs}</resources><build>${build}</build></model>`;
  return zipGuardado([["[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>'],
    ["_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'],
    ["3D/3dmodel.model", modelo]]);
}
/* IFC4 (texto STEP) do modelo editado: um IfcBuildingElementProxy por objeto, com a malha em IfcTriangulatedFaceSet (mm).
   As propriedades e a estrutura do IFC original não vão junto: é a geometria do que foi modelado aqui. */
function guidIfc() { const A = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"; let s = A[Math.floor(Math.random() * 4)];
  for (let i = 0; i < 21; i++) s += A[Math.floor(Math.random() * 64)]; return s; }
function escreverIfc(objetos, nomeProjeto) {
  const L = [], add = t => { L.push(t); return "#" + L.length; }, q = s => "'" + String(s == null ? "" : s).replace(/[^\x20-\x7E]/g, "_").replace(/'/g, "''") + "'";
  const pessoa = add("IFCPERSON($,$,'',$,$,$,$,$)"), org = add("IFCORGANIZATION($,'InovaSTEM',$,$,$)"), po = add(`IFCPERSONANDORGANIZATION(${pessoa},${org},$)`);
  const app = add(`IFCAPPLICATION(${org},'0.1','Physis 3D - Modelagem 3D','physis3d')`), dono = add(`IFCOWNERHISTORY(${po},${app},$,.ADDED.,$,$,$,0)`);
  const mm = add("IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.)"), un = add(`IFCUNITASSIGNMENT((${mm}))`);
  const o0 = add("IFCCARTESIANPOINT((0.,0.,0.))"), ax = add(`IFCAXIS2PLACEMENT3D(${o0},$,$)`);
  const ctx = add(`IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,${ax},$)`), sub = add(`IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,${ctx},$,.MODEL_VIEW.,$)`);
  const prj = add(`IFCPROJECT('${guidIfc()}',${dono},${q(nomeProjeto || "Modelagem 3D")},$,$,$,$,(${ctx}),${un})`);
  const lp = add(`IFCLOCALPLACEMENT($,${ax})`);
  const site = add(`IFCSITE('${guidIfc()}',${dono},'Terreno',$,$,${lp},$,$,.ELEMENT.,$,$,$,$,$)`);
  const pred = add(`IFCBUILDING('${guidIfc()}',${dono},'Edificacao',$,$,${lp},$,$,.ELEMENT.,$,$,$)`);
  const pav = add(`IFCBUILDINGSTOREY('${guidIfc()}',${dono},'Pavimento',$,$,${lp},$,$,.ELEMENT.,0.)`);
  add(`IFCRELAGGREGATES('${guidIfc()}',${dono},$,$,${prj},(${site}))`); add(`IFCRELAGGREGATES('${guidIfc()}',${dono},$,$,${site},(${pred}))`);
  add(`IFCRELAGGREGATES('${guidIfc()}',${dono},$,$,${pred},(${pav}))`);
  const els = [];
  objetos.forEach(ob => {
    const T = ob.T, vs = [], idx = new Map(), fs = [], ch = i => T[i].toFixed(3) + "," + T[i + 1].toFixed(3) + "," + T[i + 2].toFixed(3);
    for (let i = 0; i < T.length; i += 9) { const t = []; for (let k = 0; k < 3; k++) { const c = ch(i + 3 * k); let j = idx.get(c); if (j == null) { j = vs.length + 1; idx.set(c, j); vs.push("(" + [T[i + 3 * k], T[i + 3 * k + 1], T[i + 3 * k + 2]].map(v => (+v).toFixed(3)).join(",") + ")"); } t.push(j); }
      if (t[0] !== t[1] && t[1] !== t[2] && t[0] !== t[2]) fs.push("(" + t.join(",") + ")"); }
    if (!fs.length) return;
    const pts = add(`IFCCARTESIANPOINTLIST3D((${vs.join(",")}))`), fset = add(`IFCTRIANGULATEDFACESET(${pts},$,.T.,(${fs.join(",")}),$)`);
    const rep = add(`IFCSHAPEREPRESENTATION(${sub},'Body','Tessellation',(${fset}))`), pds = add(`IFCPRODUCTDEFINITIONSHAPE($,$,(${rep}))`);
    const lpe = add(`IFCLOCALPLACEMENT(${lp},${ax})`);
    els.push(add(`IFCBUILDINGELEMENTPROXY('${guidIfc()}',${dono},${q(ob.nome)},${q(ob.descricao || "")},$,${lpe},${pds},$,$)`));
  });
  if (els.length) add(`IFCRELCONTAINEDINSPATIALSTRUCTURE('${guidIfc()}',${dono},$,$,(${els.join(",")}),${pav})`);
  const hoje = new Date().toISOString().slice(0, 19);
  return "ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('ViewDefinition [ReferenceView]'),'2;1');\nFILE_NAME(" + q((nomeProjeto || "modelo") + ".ifc") + ",'" + hoje + "',(''),(''),'Physis 3D','Physis 3D','');\nFILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\n"
    + L.map((t, i) => "#" + (i + 1) + "=" + t + ";").join("\n") + "\nENDSEC;\nEND-ISO-10303-21;\n";
}

/* cores do guia para peças e montagens (nada de azul) */
const CORES_PECA = [["verde", "Verde profundo", "Deep green", "#0B3D2E"], ["laranja", "Laranja", "Orange", "#F97316"], ["terracota", "Terracota", "Terracotta", "#BB6B4A"],
  ["creme", "Creme", "Cream", "#F4F1EA"], ["areia", "Areia", "Sand", "#D9D3C2"], ["carvao", "Carvão", "Charcoal", "#1B1F23"], ["oliva", "Verde-oliva", "Olive green", "#4A5A47"]];

/* ════════ modo "desenho técnico": ler traços (não manchas), regiões, revolução e padrão circular (dona, 21/11/2026) ════════
   Coordenadas da grade: x para a direita, y para baixo (como a imagem). Em mm: X = x·cel, Y = (ny − y)·cel (y para cima). */
/* componentes ligadas da tinta (vizinhança de 8), com caixa e área */
function rotular8(M, nx, ny) {
  const rot = new Int32Array(nx * ny).fill(-1), comps = [], pilha = [];
  for (let k = 0; k < nx * ny; k++) {
    if (!M[k] || rot[k] >= 0) continue;
    const c = { id: comps.length, area: 0, x0: nx, y0: ny, x1: -1, y1: -1 }; comps.push(c); rot[k] = c.id; pilha.push(k);
    while (pilha.length) {
      const q = pilha.pop(), i = q % nx, j = (q - i) / nx; c.area++;
      if (i < c.x0) c.x0 = i; if (i > c.x1) c.x1 = i; if (j < c.y0) c.y0 = j; if (j > c.y1) c.y1 = j;
      for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) {
        const a = i + di, b = j + dj; if (a < 0 || b < 0 || a >= nx || b >= ny) continue; const w = b * nx + a;
        if (M[w] && rot[w] < 0) { rot[w] = c.id; pilha.push(w); } }
    }
  }
  return { rot, comps };
}
/* largura típica do traço: mediana dos trechos de tinta na horizontal e na vertical */
function larguraTraco(M, nx, ny) {
  const corridas = [];
  for (let j = 0; j < ny; j++) { let n = 0; for (let i = 0; i <= nx; i++) { if (i < nx && M[j * nx + i]) n++; else if (n) { corridas.push(n); n = 0; } } }
  for (let i = 0; i < nx; i++) { let n = 0; for (let j = 0; j <= ny; j++) { if (j < ny && M[j * nx + i]) n++; else if (n) { corridas.push(n); n = 0; } } }
  if (!corridas.length) return 1;
  corridas.sort((a, b) => a - b); return Math.max(1, corridas[Math.floor(corridas.length / 2)]);
}
/* erosão e dilatação por um quadrado de lado 2r+1 (separáveis) */
function morfo(M, nx, ny, r, dilatar) {
  if (!(r > 0)) return Uint8Array.from(M);
  const A = new Uint8Array(nx * ny), B = new Uint8Array(nx * ny);
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    let v = dilatar ? 0 : 1;
    for (let d = -r; d <= r; d++) { const x = i + d, m = x >= 0 && x < nx ? M[j * nx + x] : 0; if (dilatar ? m : !m) { v = dilatar ? 1 : 0; break; } }
    A[j * nx + i] = v; }
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
    let v = dilatar ? 0 : 1;
    for (let d = -r; d <= r; d++) { const y = j + d, m = y >= 0 && y < ny ? A[y * nx + i] : 0; if (dilatar ? m : !m) { v = dilatar ? 1 : 0; break; } }
    B[j * nx + i] = v; }
  return B;
}
/* afinamento de Zhang e Suen (1984): o traço vira uma linha de 1 célula, o "esqueleto" */
function afinar(M, nx, ny) {
  const S = Uint8Array.from(M), p = (i, j) => (i >= 0 && j >= 0 && i < nx && j < ny) ? S[j * nx + i] : 0;
  let mudou = true, guarda = 0;
  while (mudou && guarda++ < 200) {
    mudou = false;
    for (let passo = 0; passo < 2; passo++) {
      const tirar = [];
      for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
        if (!S[j * nx + i]) continue;
        const v = [p(i, j - 1), p(i + 1, j - 1), p(i + 1, j), p(i + 1, j + 1), p(i, j + 1), p(i - 1, j + 1), p(i - 1, j), p(i - 1, j - 1)];
        const B = v.reduce((s, x) => s + x, 0); if (B < 2 || B > 6) continue;
        let A = 0; for (let k = 0; k < 8; k++) if (!v[k] && v[(k + 1) % 8]) A++; if (A !== 1) continue;
        if (passo === 0 ? (v[0] * v[2] * v[4] || v[2] * v[4] * v[6]) : (v[0] * v[2] * v[6] || v[0] * v[4] * v[6])) continue;
        tirar.push(j * nx + i);
      }
      if (tirar.length) { mudou = true; tirar.forEach(k => { S[k] = 0; }); }
    }
  }
  return S;
}
/* esqueleto → linhas (de ponta ou cruzamento até ponta ou cruzamento; laços fechados soltos também) */
function tracarEsqueleto(S, nx, ny) {
  const viz = k => { const i = k % nx, j = (k - i) / nx, o = []; for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) {
    if (!di && !dj) continue; const a = i + di, b = j + dj; if (a >= 0 && b >= 0 && a < nx && b < ny && S[b * nx + a]) o.push(b * nx + a); } return o; };
  const grau = new Uint8Array(nx * ny); for (let k = 0; k < nx * ny; k++) if (S[k]) grau[k] = viz(k).length;
  const usada = new Set(), chave = (a, b) => a < b ? a + "," + b : b + "," + a, linhas = [], pt = k => [k % nx + 0.5, Math.floor(k / nx) + 0.5];
  const seguir = (ini, prox) => { const l = [ini]; let ant = ini, at = prox; usada.add(chave(ini, prox));
    while (true) { l.push(at); if (grau[at] !== 2) break; const n = viz(at).filter(w => w !== ant && !usada.has(chave(at, w))); if (!n.length) break;
      usada.add(chave(at, n[0])); ant = at; at = n[0]; if (at === ini) { l.push(at); break; } }
    return l; };
  for (let k = 0; k < nx * ny; k++) if (S[k] && grau[k] !== 2) viz(k).forEach(w => { if (!usada.has(chave(k, w))) linhas.push(seguir(k, w)); });
  for (let k = 0; k < nx * ny; k++) if (S[k] && grau[k] === 2) viz(k).forEach(w => { if (!usada.has(chave(k, w))) linhas.push(seguir(k, w)); });
  return linhas.filter(l => l.length >= 2).map(l => l.map(pt));
}
/* círculo por mínimos quadrados (Kåsa): centro, raio e resíduo médio */
function ajustarCirculo(pts) {
  const n = pts.length; if (n < 3) return null;
  let sx = 0, sy = 0; pts.forEach(p => { sx += p[0]; sy += p[1]; }); const mx = sx / n, my = sy / n;
  let suu = 0, svv = 0, suv = 0, suuu = 0, svvv = 0, suvv = 0, svuu = 0;
  pts.forEach(p => { const u = p[0] - mx, v = p[1] - my; suu += u * u; svv += v * v; suv += u * v; suuu += u * u * u; svvv += v * v * v; suvv += u * v * v; svuu += v * u * u; });
  const det = suu * svv - suv * suv; if (Math.abs(det) < 1e-12) return null;
  const b1 = (suuu + suvv) / 2, b2 = (svvv + svuu) / 2, uc = (b1 * svv - b2 * suv) / det, vc = (suu * b2 - suv * b1) / det;
  const r = Math.sqrt(uc * uc + vc * vc + (suu + svv) / n), cx = uc + mx, cy = vc + my;
  let rms = 0; pts.forEach(p => { const d = Math.hypot(p[0] - cx, p[1] - cy) - r; rms += d * d; });
  return { cx, cy, r, rms: Math.sqrt(rms / n) };
}
/* um laço vira primitivas exatas: círculo inteiro (se couber) ou trechos retos e arcos (Douglas-Peucker + ajuste de arco) */
function primitivas(l, tol) {
  tol = tol || 1;
  const c = l.length >= 8 ? ajustarCirculo(l) : null;
  if (c && c.r > 3 * tol && c.rms < Math.max(0.35 * tol, 0.02 * c.r)) {
    const n = Math.max(24, Math.min(128, Math.round(2 * Math.PI * c.r / tol))), pts = [];
    for (let i = 0; i < n; i++) { const a = 2 * Math.PI * i / n; pts.push([c.cx + c.r * Math.cos(a), c.cy + c.r * Math.sin(a)]); }
    return { pts, prims: [{ tipo: "circulo", cx: c.cx, cy: c.cy, r: c.r }] };
  }
  const s = simplificarLaco(l, tol), prims = [], out = [];
  let ext = 0; s.forEach(p => s.forEach(q => { ext = Math.max(ext, Math.hypot(p[0] - q[0], p[1] - q[1])); }));
  const varredura = (ca, tr) => { let tot = 0, a = Math.atan2(tr[0][1] - ca.cy, tr[0][0] - ca.cx);
    for (let k = 1; k < tr.length; k++) { const b = Math.atan2(tr[k][1] - ca.cy, tr[k][0] - ca.cx); let d = b - a; while (d > Math.PI) d -= 2 * Math.PI; while (d < -Math.PI) d += 2 * Math.PI; tot += d; a = b; }
    return tot; };
  // trechos com 5 ou mais vértices seguidos que cabem num arco (raio menor que a peça, 30° ou mais) viram um arco exato
  let i = 0;
  while (i < s.length) {
    let j = i + 4, melhor = null;
    while (j < s.length) { const tr = s.slice(i, j + 1), ca = ajustarCirculo(tr);
      if (ca && ca.rms < 0.35 * tol && ca.r < ext && Math.abs(varredura(ca, tr)) >= Math.PI / 6) { melhor = { j, ca, tr }; j++; } else break; }
    if (melhor) {
      const { ca, tr } = melhor, a0 = Math.atan2(tr[0][1] - ca.cy, tr[0][0] - ca.cx), da = varredura(ca, tr), n = Math.max(4, Math.ceil(Math.abs(da) * ca.r / tol));
      for (let k = 0; k < n; k++) { const a = a0 + da * k / n; out.push([ca.cx + ca.r * Math.cos(a), ca.cy + ca.r * Math.sin(a)]); }
      prims.push({ tipo: "arco", cx: ca.cx, cy: ca.cy, r: ca.r }); i = melhor.j;
    } else { out.push(s[i]); prims.push({ tipo: "reta" }); i++; }
  }
  return { pts: out.length >= 3 ? out : s, prims };
}
/* recorte de um laço por um semiplano (Sutherland–Hodgman): fica o lado com f(p) ≥ 0 */
function recortarLaco(l, f) {
  const out = [];
  for (let i = 0; i < l.length; i++) {
    const a = l[i], b = l[(i + 1) % l.length], fa = f(a), fb = f(b);
    if (fa >= 0) out.push(a);
    if ((fa >= 0) !== (fb >= 0)) { const t = fa / (fa - fb); out.push([a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]); }
  }
  return out.length >= 3 ? out : null;
}
/* lê uma vista de desenho técnico: traços, texto, cotas e hachuras; devolve as regiões (perfil, furo, ignorado) em células */
function lerDesenho(rgba, nx, ny, op) {
  op = op || {};
  const g = suavizar(cinza(rgba, nx * ny), nx, ny, op.suavizar || 0), auto = otsu(g), L = op.limiar == null || op.limiar === "" ? auto : +op.limiar;
  const M = new Uint8Array(nx * ny); for (let k = 0; k < nx * ny; k++) { const escuro = g[k] < L; M[k] = (op.inverter ? !escuro : escuro) ? 1 : 0; }
  const s = larguraTraco(M, nx, ny), lado = Math.min(nx, ny), textoMax = op.textoMax || Math.max(6 * s, Math.round(0.045 * lado));
  const ign = [];                                       // o que foi ignorado (para mostrar e poder reincluir)
  // 1. texto, setas soltas e traços curtos (componentes pequenos e isolados)
  const R = rotular8(M, nx, ny), M2 = Uint8Array.from(M), pequeno = [];
  R.comps.forEach(c => { const w = c.x1 - c.x0 + 1, h = c.y1 - c.y0 + 1;
    if (Math.max(w, h) <= textoMax) { const alongado = Math.max(w, h) >= 3 * Math.min(w, h) && Math.min(w, h) <= 2 * s;
      c.tipo = alongado ? "traco_curto" : "texto"; pequeno.push(c); } });
  if (!op.manterTexto) { const marca = new Uint8Array(R.comps.length); pequeno.forEach(c => { marca[c.id] = 1; ign.push({ tipo: c.tipo, x0: c.x0, y0: c.y0, x1: c.x1, y1: c.y1 }); });
    for (let k = 0; k < nx * ny; k++) if (M2[k] && marca[R.rot[k]]) M2[k] = 0; }
  // 2. hachuras: no esqueleto, trechos retos curtos e paralelos, em diagonal
  const esq = afinar(M2, nx, ny), linhas = tracarEsqueleto(esq, nx, ny), cand = [];
  linhas.forEach(l => { const a = l[0], b = l[l.length - 1], comp = Math.hypot(b[0] - a[0], b[1] - a[1]);
    if (comp < 3 * s || comp > 0.5 * lado) return;
    let desvio = 0; l.forEach(p => { desvio = Math.max(desvio, Math.abs((b[1] - a[1]) * (p[0] - a[0]) - (b[0] - a[0]) * (p[1] - a[1])) / comp); });
    if (desvio > Math.max(1.5, 0.6 * s)) return;
    let ang = Math.atan2(-(b[1] - a[1]), b[0] - a[0]) * 180 / Math.PI; ang = ((ang % 180) + 180) % 180;
    if ((ang >= 20 && ang <= 70) || (ang >= 110 && ang <= 160)) cand.push({ l, ang, meio: l[Math.floor(l.length / 2)] }); });
  const hach = op.manterHachura ? [] : cand.filter(c => cand.filter(o => Math.abs(o.ang - c.ang) <= 8).length >= 4);
  const M3 = Uint8Array.from(M2), rH = Math.ceil(s / 2) + 1, ponta = 1.5 * s + 2;
  hach.forEach(c => { const a = c.l[0], b = c.l[c.l.length - 1]; let x0 = nx, y0 = ny, x1 = 0, y1 = 0;
    c.l.forEach(p => { if (Math.hypot(p[0] - a[0], p[1] - a[1]) < ponta || Math.hypot(p[0] - b[0], p[1] - b[1]) < ponta) return;
      const i = Math.floor(p[0]), j = Math.floor(p[1]); x0 = Math.min(x0, i); y0 = Math.min(y0, j); x1 = Math.max(x1, i); y1 = Math.max(y1, j);
      for (let dj = -rH; dj <= rH; dj++) for (let di = -rH; di <= rH; di++) { const u = i + di, v = j + dj; if (u >= 0 && v >= 0 && u < nx && v < ny) M3[v * nx + u] = 0; } });
    if (x1 >= x0) ign.push({ tipo: "hachura", x0, y0, x1, y1 }); });
  // 3. regiões fechadas (fundo cercado de tinta), com a profundidade de cada uma (dentro de quantos contornos está)
  const fundo = componentes(M3, nx, ny, 0), nR = fundo.tam.length, prof = new Int32Array(nR).fill(-1), hachDentro = new Int32Array(nR);
  hach.forEach(c => { const i = Math.floor(c.meio[0]), j = Math.floor(c.meio[1]), r = fundo.rot[j * nx + i]; if (r >= 0) hachDentro[r]++; });
  // por região: primeiro pixel, área, borda (perímetro) e momentos, numa passada só
  const prim = new Int32Array(nR).fill(-1), area = new Float64Array(nR), per = new Float64Array(nR), sx = new Float64Array(nR), sy = new Float64Array(nR),
    sxx = new Float64Array(nR), syy = new Float64Array(nR), sxy = new Float64Array(nR);
  for (let k = 0; k < nx * ny; k++) { const r = fundo.rot[k]; if (r < 0) continue; if (prim[r] < 0) prim[r] = k; const i = k % nx, j = (k - i) / nx;
    area[r]++; sx[r] += i; sy[r] += j; sxx[r] += i * i; syy[r] += j * j; sxy[r] += i * j;
    if (i === 0 || j === 0 || i === nx - 1 || j === ny - 1 || M3[k - 1] || M3[k + 1] || M3[k - nx] || M3[k + nx]) per[r]++; }
  const pai = r => { const k = prim[r];
    let i = k % nx; const j = (k - i) / nx; while (i > 0 && fundo.rot[j * nx + i] === r) i--; while (i > 0 && M3[j * nx + i]) i--; return i >= 0 ? fundo.rot[j * nx + i] : -1; };
  const profDe = (r, n) => { if (prof[r] >= 0) return prof[r]; if (fundo.borda[r] || n > 40) return (prof[r] = 0); const p = pai(r); return (prof[r] = p < 0 || p === r ? 1 : profDe(p, n + 1) + 1); };
  const material = new Uint8Array(nR);
  // fresta entre duas linhas de hachura: fina (espessura ≈ 2·área/perímetro) e em diagonal — é material, não furo
  // espaçamento típico da hachura: distância entre linhas vizinhas, medida na normal (mediana)
  let passoH = 3 * s;
  if (hach.length >= 4) { const th = hach[0].ang * Math.PI / 180, nxh = Math.sin(th), nyh = Math.cos(th);
    const pr = hach.filter(c => Math.abs(c.ang - hach[0].ang) <= 8).map(c => c.meio[0] * nxh + c.meio[1] * nyh).sort((u, v) => u - v), ds = [];
    for (let i = 1; i < pr.length; i++) if (pr[i] - pr[i - 1] > 1) ds.push(pr[i] - pr[i - 1]);
    if (ds.length) { ds.sort((u, v) => u - v); passoH = Math.max(passoH, 1.5 * ds[Math.floor(ds.length / 2)]); } }
  const fresta = r => { const n = area[r]; if (n < 2 || hach.length < 4) return false; const esp = 2 * n / Math.max(1, per[r]);
    const mx = sx[r] / n, my = sy[r] / n, a_ = sxx[r] / n - mx * mx, b_ = syy[r] / n - my * my, c_ = sxy[r] / n - mx * my;
    const l1 = (a_ + b_) / 2 + Math.sqrt(((a_ - b_) / 2) ** 2 + c_ * c_), l2 = (a_ + b_) / 2 - Math.sqrt(((a_ - b_) / 2) ** 2 + c_ * c_);
    let ang = Math.atan2(-(l1 - a_), c_ || 1e-12) * 180 / Math.PI; ang = ((ang % 180) + 180) % 180;
    const diag = (ang >= 20 && ang <= 70) || (ang >= 110 && ang <= 160);
    return esp <= passoH && l1 > 4 * Math.max(l2, 0.25) && diag; };
  for (let r = 0; r < nR; r++) { if (fundo.borda[r]) continue; const d = profDe(r, 0); material[r] = hachDentro[r] >= 2 || fresta(r) || (d % 2 === 1) ? 1 : 0; }
  // seção hachurada manda: dentro dela, o que não é hachura continua furo só se for grande
  const F = new Uint8Array(nx * ny);
  for (let k = 0; k < nx * ny; k++) { if (M3[k]) F[k] = 1; else { const r = fundo.rot[k]; if (r >= 0 && !fundo.borda[r] && material[r]) F[k] = 1; } }
  // 4. linhas soltas (cotas, linhas de chamada, de centro) somem na abertura; volta meia espessura de traço para o meio da linha
  const rA = Math.ceil(s) + (op.abertura || 0), aberto = morfo(morfo(F, nx, ny, rA, false), nx, ny, rA, true), meio = Math.floor(s / 2);
  const Fin = meio > 0 ? morfo(aberto, nx, ny, meio, false) : aberto;
  // 5. regiões finais: cada componente vira um corpo, com os seus furos; o pequeno demais e o quadro de notas são ignorados
  const reg = componentes(Fin, nx, ny, 1), areaMin = op.areaMin || Math.max(4 * s * s * 4, Math.round(0.002 * nx * ny)), regioes = [];
  reg.tam.forEach((area, id) => {
    let x0 = nx, y0 = ny, x1 = 0, y1 = 0; for (let k = 0; k < nx * ny; k++) if (reg.rot[k] === id) { const i = k % nx, j = (k - i) / nx; if (i < x0) x0 = i; if (i > x1) x1 = i; if (j < y0) y0 = j; if (j > y1) y1 = j; }
    const textos = pequeno.filter(c => c.tipo === "texto" && c.x0 >= x0 && c.x1 <= x1 && c.y0 >= y0 && c.y1 <= y1).length;
    let tipo = "corpo", motivo = "";
    if (area < areaMin) { tipo = "ignorado"; motivo = "cota"; }
    else if (textos >= 3 && !hach.some(c => c.meio[0] >= x0 && c.meio[0] <= x1 + 1 && c.meio[1] >= y0 && c.meio[1] <= y1 + 1)) { tipo = "ignorado"; motivo = "texto"; }
    regioes.push({ id, area, x0, y0, x1, y1, tipo, motivo, hachurada: hach.some(c => reg.rot[Math.floor(c.meio[1]) * nx + Math.floor(c.meio[0])] === id || (c.meio[0] >= x0 && c.meio[0] <= x1 + 1 && c.meio[1] >= y0 && c.meio[1] <= y1 + 1)) });
  });
  // 6. linha de centro: traços curtos alinhados (traço e ponto) na vertical ou na horizontal
  let eixo = null; const tr = pequeno.filter(c => c.tipo === "traco_curto" || (c.x1 - c.x0 <= 2 * s || c.y1 - c.y0 <= 2 * s));
  const grupos = {}; tr.forEach(c => { const v = c.y1 - c.y0 > c.x1 - c.x0, k = (v ? "v" : "h") + Math.round(((v ? c.x0 + c.x1 : c.y0 + c.y1) / 2) / Math.max(2, s)); (grupos[k] = grupos[k] || []).push(c); });
  Object.keys(grupos).forEach(k => { const gs = grupos[k]; if (gs.length < 3) return; const v = k[0] === "v";
    const ini = Math.min(...gs.map(c => v ? c.y0 : c.x0)), fim = Math.max(...gs.map(c => v ? c.y1 : c.x1)); if (fim - ini < 0.3 * (v ? ny : nx)) return;
    const pos = gs.reduce((a, c) => a + (v ? (c.x0 + c.x1 + 1) / 2 : (c.y0 + c.y1 + 1) / 2), 0) / gs.length;
    if (!eixo || gs.length > eixo.n) eixo = { n: gs.length, p: v ? [pos, ini] : [ini, pos], q: v ? [pos, fim + 1] : [fim + 1, pos] }; });
  return { M: Fin, rot: reg.rot, regioes, ignorados: ign, tracos: linhas, hachuras: hach.length, textos: pequeno.filter(c => c.tipo === "texto").length,
    traco: s, limiar: L, otsu: auto, eixo: eixo ? { p: eixo.p, q: eixo.q } : null };
}
/* laços (em células) de uma região, já em mm, com primitivas ajustadas; outer = perfil, inner = furo */
function lacosDaRegiao(D, id, nx, ny, cel, tol) {
  const Mr = new Uint8Array(nx * ny); for (let k = 0; k < nx * ny; k++) if (D.rot[k] === id) Mr[k] = 1;
  return contornos(Mr, nx, ny, 1, 0.5).map(l => { const p = primitivas(l, tol || 1);
    return { tipo: area2(p.pts) >= 0 ? "perfil" : "furo", prims: p.prims, laco: p.pts.map(q => [q[0] * cel, q[1] * cel]) }; });
}
/* revolução: laços no plano do desenho (mm, y para cima) giram em volta do eixo p–q; n segmentos. O lado: +1 = à direita do eixo
   (ou abaixo, se o eixo for horizontal), −1 = o outro
   (o outro lado é cortado, como numa meia-seção). Z da peça = ao longo do eixo. */
function revolver(lacos, eixo, n, lado) {
  n = Math.max(6, Math.min(512, Math.round(n || 64))); lado = lado < 0 ? -1 : 1;
  const [px, py] = eixo.p, [qx, qy] = eixo.q, L = Math.hypot(qx - px, qy - py); if (!(L > 0)) throw new Error("eixo sem comprimento");
  let ux = (qx - px) / L, uy = (qy - py) / L; if (uy < -1e-9 || (Math.abs(uy) <= 1e-9 && ux < 0)) { ux = -ux; uy = -uy; }
  const rz = p => [lado * ((p[0] - px) * uy - (p[1] - py) * ux), (p[0] - px) * ux + (p[1] - py) * uy];
  const out = [];
  lacos.forEach(l => {
    const rl = recortarLaco(l.map(rz), p => p[0]); if (!rl) return;
    const lim = rl.map(p => [Math.max(0, p[0]), p[1]]);
    for (let i = 0; i < lim.length; i++) { const a = lim[i], b = lim[(i + 1) % lim.length]; if (a[0] < 1e-9 && b[0] < 1e-9) continue;
      for (let k = 0; k < n; k++) { const t0 = 2 * Math.PI * k / n, t1 = 2 * Math.PI * (k + 1) / n, P = (p, t) => [p[0] * Math.cos(t), p[0] * Math.sin(t), p[1]];
        const A0 = P(a, t0), B0 = P(b, t0), B1 = P(b, t1), A1 = P(a, t1);
        if (a[0] > 1e-9) out.push(...A0, ...B0, ...A1); if (b[0] > 1e-9) out.push(...B0, ...B1, ...A1); } }
  });
  if (!out.length) throw new Error("o perfil não tem nada do lado escolhido do eixo");
  const T = new Float32Array(out); let v = 0;
  for (let i = 0; i < T.length; i += 9) v += T[i] * (T[i + 4] * T[i + 8] - T[i + 5] * T[i + 7]) - T[i + 1] * (T[i + 3] * T[i + 8] - T[i + 5] * T[i + 6]) + T[i + 2] * (T[i + 3] * T[i + 7] - T[i + 4] * T[i + 6]);
  if (v < 0) for (let i = 0; i < T.length; i += 9) for (let k = 0; k < 3; k++) { const x = T[i + 3 + k]; T[i + 3 + k] = T[i + 6 + k]; T[i + 6 + k] = x; }
  const zmin = caixaDe(T).min[2]; for (let i = 2; i < T.length; i += 3) T[i] -= zmin;
  return T;
}
/* padrão circular: n cópias de T em volta do eixo vertical que passa por centro (mm); devolve a lista dos n corpos */
function padraoCircular(T, n, centro) {
  n = Math.max(1, Math.min(360, Math.round(n || 1))); const c = centro || [0, 0], lista = [];
  for (let k = 0; k < n; k++) lista.push(transformar(T, [0, 0, 0], [0, 0, 360 * k / n], 1, [c[0], c[1], 0]));
  return lista;
}
/* quantos corpos separados há numa malha (vértices ligados por triângulos) */
function corpos(T) {
  const id = new Map(), pai = [], ch = i => T[i].toFixed(4) + "," + T[i + 1].toFixed(4) + "," + T[i + 2].toFixed(4);
  const raiz = a => { while (pai[a] !== a) a = pai[a] = pai[pai[a]]; return a; };
  const no = i => { const c = ch(i); let v = id.get(c); if (v == null) { v = pai.length; pai.push(v); id.set(c, v); } return v; };
  for (let i = 0; i < T.length; i += 9) { const a = raiz(no(i)), b = raiz(no(i + 3)), c = raiz(no(i + 6)); pai[b] = a; pai[raiz(c)] = a; }
  return new Set(pai.map((_, i) => raiz(i))).size;
}
/* ════════ impressão em qualquer impressora (dona, 22/11/2026): apoiar na mesa e dividir com encaixe ════════
   "somente garantir que todas as impressoras consigam imprimir os documentos gerados": STL binário em mm, malha fechada,
   peça apoiada em z = 0 e, acima do limite da mesa (200 mm por padrão), dividida em planos com encaixe de pino e furo.
   Só geometria: nada de marca de impressora nem de fatiador. */
function apoiarNaMesa(T) {
  if (!T || !T.length) return T;
  let zmin = Infinity; for (let i = 2; i < T.length; i += 3) if (T[i] < zmin) zmin = T[i];
  if (!isFinite(zmin) || Math.abs(zmin) < 1e-9) return T;
  const U = Float32Array.from(T); for (let i = 2; i < U.length; i += 3) U[i] -= zmin; return U;
}
/* arestas: cada aresta em exatamente 2 triângulos, em sentidos opostos (o que todo fatiador espera) */
/* vértices numa grade de 0,001 mm: fecha costuras de quase-duplicados (revolução, escala em float) antes de cortar e conferir */
function soldar(T) { const U = new Float32Array(T.length); for (let i = 0; i < T.length; i++) U[i] = Math.round(T[i] * 1000) / 1000; return U; }
function arestas(T) {
  const r = x => Math.round(x * 1000), k = i => r(T[i]) + "," + r(T[i + 1]) + "," + r(T[i + 2]), m = new Map();
  for (let i = 0; i < T.length; i += 9) { const v = [k(i), k(i + 3), k(i + 6)];
    for (let j = 0; j < 3; j++) { const a = v[j], b = v[(j + 1) % 3]; if (a === b) continue; const s = a < b ? a + "|" + b : b + "|" + a;
      const e = m.get(s) || [0, 0]; e[a < b ? 0 : 1]++; m.set(s, e); } }
  let abertas = 0, ruins = 0; m.forEach(([p, q]) => { if (p + q === 1) abertas++; else if (p !== 1 || q !== 1) ruins++; });
  return { total: m.size, abertas, ruins, fechada: abertas === 0 && ruins === 0 };
}
/* conferência para imprimir: malha fechada, apoiada, tamanho e quanto da área fica em balanço acima de 45° */
function conferirImpressao(T, limite) {
  limite = limite || 200;
  const c = caixaDe(T), tam = [c.max[0] - c.min[0], c.max[1] - c.min[1], c.max[2] - c.min[2]], a = arestas(T);
  let area = 0, bal = 0; const cos45 = Math.cos(Math.PI / 4);
  for (let i = 0; i < T.length; i += 9) {
    const ux = T[i + 3] - T[i], uy = T[i + 4] - T[i + 1], uz = T[i + 5] - T[i + 2], vx = T[i + 6] - T[i], vy = T[i + 7] - T[i + 1], vz = T[i + 8] - T[i + 2];
    const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx, s = Math.hypot(nx, ny, nz); if (!(s > 0)) continue;
    area += s / 2; const zb = Math.min(T[i + 2], T[i + 5], T[i + 8]) - c.min[2];
    if (nz / s < -cos45 - 1e-9 && zb > 0.05) bal += s / 2;          // virada para baixo, mais deitada que 45°, fora da mesa
  }
  return { fechada: a.fechada, abertas: a.abertas, ruins: a.ruins, tamanho: tam, apoiada: Math.abs(c.min[2]) < 1e-6,
           balanco: area > 0 ? bal / area : 0, grande: Math.max(tam[0], tam[1], tam[2]) > limite + 1e-6, limite };
}
/* corta a malha no plano eixo = c: a parte de baixo, a de cima e os segmentos do corte (em 2D, nos outros dois eixos, em ordem cíclica) */
const EIXOS_2D = [[1, 2], [2, 0], [0, 1]];
function cortarPlano(T, ax, c) {
  const baixo = [], cima = [], segs = [], [u, v] = EIXOS_2D[ax];
  const ponto = (P, Q) => { const a = P[ax] - c, b = Q[ax] - c; const [A, B, ta, tb] = (P[0] < Q[0] || (P[0] === Q[0] && (P[1] < Q[1] || (P[1] === Q[1] && P[2] <= Q[2])))) ? [P, Q, a, b] : [Q, P, b, a];
    const t = ta / (ta - tb); const r = [A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t]; r[ax] = c; return r; };
  const pol = (out, L) => { for (let k = 1; k + 1 < L.length; k++) out.push(...L[0], ...L[k], ...L[k + 1]); };
  for (let i = 0; i < T.length; i += 9) {
    const V = [[T[i], T[i + 1], T[i + 2]], [T[i + 3], T[i + 4], T[i + 5]], [T[i + 6], T[i + 7], T[i + 8]]], d = V.map(p => p[ax] - c);
    if (d[0] <= 0 && d[1] <= 0 && d[2] <= 0) { baixo.push(...V[0], ...V[1], ...V[2]); continue; }
    if (d[0] >= 0 && d[1] >= 0 && d[2] >= 0) { cima.push(...V[0], ...V[1], ...V[2]); continue; }
    const B = [], C = [], X = [];
    for (let j = 0; j < 3; j++) { const P = V[j], Q = V[(j + 1) % 3], dp = d[j], dq = d[(j + 1) % 3];
      if (dp <= 0) B.push(P); if (dp >= 0) C.push(P);
      if ((dp < 0 && dq > 0) || (dp > 0 && dq < 0)) { const r = ponto(P, Q); B.push(r); C.push(r); X.push(r); } }
    pol(baixo, B); pol(cima, C);
    if (X.length === 2) segs.push([[X[0][u], X[0][v]], [X[1][u], X[1][v]]]);
  }
  return { baixo, cima, segs };
}
/* segmentos do corte → laços fechados (2D) */
function lacosDosSegmentos(segs) {
  const ch = p => p[0].toFixed(5) + "," + p[1].toFixed(5), viz = new Map(), pt = new Map();
  segs.forEach(([a, b]) => { const ka = ch(a), kb = ch(b); if (ka === kb) return; pt.set(ka, a); pt.set(kb, b);
    (viz.get(ka) || viz.set(ka, []).get(ka)).push(kb); (viz.get(kb) || viz.set(kb, []).get(kb)).push(ka); });
  const usado = new Set(), lacos = [], ar = (a, b) => (a < b ? a + "|" + b : b + "|" + a);
  viz.forEach((_, ini) => {
    const l = [ini]; let ant = null, atual = ini;
    for (let guarda = 0; guarda < 1e6; guarda++) {
      const prox = (viz.get(atual) || []).find(n => n !== ant && !usado.has(ar(atual, n)));
      if (!prox) break; usado.add(ar(atual, prox)); if (prox === ini) { lacos.push(l.map(k => pt.get(k))); break; }
      l.push(prox); ant = atual; atual = prox;
    }
  });
  return lacos.filter(l => l.length >= 3);
}
/* tampa (laços com furos) no plano eixo = c; normal para +eixo (sentido 1) ou -eixo (-1) */
function tampa(out, grupos, ax, c, sentido) {
  const [u, v] = EIXOS_2D[ax], P3 = p => { const r = [0, 0, 0]; r[u] = p[0]; r[v] = p[1]; r[ax] = c; return r; };
  grupos.forEach(g => orelhas(costurar(g.l, g.furos)).forEach(([a, b, d]) => {
    const A = P3(a), B = P3(b), D = P3(d); if (sentido > 0) out.push(...A, ...B, ...D); else out.push(...A, ...D, ...B); }));
}
/* ponto dentro da malha fechada (raio inclinado, conta cruzamentos) */
function dentroMalha(T, p) {
  const d = [0.5773, 0.6131, 0.5397]; let n = 0;
  for (let i = 0; i < T.length; i += 9) {
    const ax = T[i], ay = T[i + 1], az = T[i + 2], e1 = [T[i + 3] - ax, T[i + 4] - ay, T[i + 5] - az], e2 = [T[i + 6] - ax, T[i + 7] - ay, T[i + 8] - az];
    const h = [d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0]], det = e1[0] * h[0] + e1[1] * h[1] + e1[2] * h[2];
    if (Math.abs(det) < 1e-12) continue; const f = 1 / det, s = [p[0] - ax, p[1] - ay, p[2] - az], uu = f * (s[0] * h[0] + s[1] * h[1] + s[2] * h[2]);
    if (uu < 0 || uu > 1) continue; const q = [s[1] * e1[2] - s[2] * e1[1], s[2] * e1[0] - s[0] * e1[2], s[0] * e1[1] - s[1] * e1[0]], vv = f * (d[0] * q[0] + d[1] * q[1] + d[2] * q[2]);
    if (vv < 0 || uu + vv > 1) continue; if (f * (e2[0] * q[0] + e2[1] * q[1] + e2[2] * q[2]) > 1e-9) n++;
  }
  return n % 2 === 1;
}
/* círculo (2D) com n lados; sentido horário = furo na tampa */
const circ2 = (cx, cy, r, n, horario) => { const l = []; for (let k = 0; k < n; k++) { const a = 2 * Math.PI * k / n * (horario ? -1 : 1); l.push([cx + r * Math.cos(a), cy + r * Math.sin(a)]); } return l; };
/* parede de cilindro entre z0 e z1 no eixo ax; fora = normal para fora do eixo do cilindro (pino) ou para dentro (furo) */
function paredeCil(out, ax, l, z0, z1, fora) {
  const [u, v] = EIXOS_2D[ax], P3 = (p, z) => { const r = [0, 0, 0]; r[u] = p[0]; r[v] = p[1]; r[ax] = z; return r; };
  for (let k = 0; k < l.length; k++) { const p = l[k], q = l[(k + 1) % l.length], a = P3(p, z0), b = P3(q, z0), c = P3(q, z1), d = P3(p, z1);
    if (fora) out.push(...a, ...b, ...c, ...a, ...c, ...d); else out.push(...a, ...c, ...b, ...a, ...d, ...c); }
}
/* lugares para o pino: dentro do maior contorno, longe das bordas e dos furos; o furo correspondente cabe inteiro na parte de cima */
function lugaresDoPino(grupos, r, cima, ax, c, prof) {
  if (!grupos.length) return [];
  const g = grupos.slice().sort((a, b) => Math.abs(area2(b.l)) - Math.abs(area2(a.l)))[0], todos = [g.l].concat(g.furos);
  const distBorda = p => { let m = Infinity; todos.forEach(l => l.forEach((a, i) => { const b = l[(i + 1) % l.length], dx = b[0] - a[0], dy = b[1] - a[1], L = dx * dx + dy * dy;
    const t = L > 0 ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L)) : 0; m = Math.min(m, Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)); })); return m; };
  const [u, v] = EIXOS_2D[ax], noMaterial = (p, z) => { const q = [0, 0, 0]; q[u] = p[0]; q[v] = p[1]; q[ax] = z; return dentroMalha(cima, q); };
  const xs = g.l.map(p => p[0]), ys = g.l.map(p => p[1]), x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), cand = [];
  for (let i = 1; i < 12; i++) for (let j = 1; j < 12; j++) { const p = [x0 + (x1 - x0) * i / 12, y0 + (y1 - y0) * j / 12];
    if (!dentro(p, g.l) || g.furos.some(f => dentro(p, f))) continue; const db = distBorda(p); if (db < r + 2) continue;
    // o furo (com folga) tem de ficar inteiro dentro do material da parte de cima, até o fundo
    const ok = [0.4, prof * 0.5, prof + 0.4].every(z => [[0, 0], [r + 1, 0], [-(r + 1), 0], [0, r + 1], [0, -(r + 1)]].every(([a, b]) => noMaterial([p[0] + a, p[1] + b], c + z)));
    if (ok) cand.push({ p, db }); }
  if (!cand.length) return [];
  cand.sort((a, b) => b.db - a.db);
  const um = cand[0].p; let dois = null, melhor = 0;
  cand.forEach(q => { const d = Math.hypot(q.p[0] - um[0], q.p[1] - um[1]); if (d > melhor && d > 4 * r) { melhor = d; dois = q.p; } });
  return dois ? [um, dois] : [um];
}
/* corta a parte em c e põe o encaixe: pino na de baixo (sai pela tampa) e furo com folga na de cima */
function cortarComEncaixe(T, ax, c, op) {
  const folga = op.folga, n = 32;
  const { baixo, cima, segs } = cortarPlano(T, ax, c), grupos = agrupar(lacosDosSegmentos(segs));
  // pino de 6 mm; em parede fina, 4 mm e depois 3 mm (Ø × altura); sem lugar seguro, o corte fica sem encaixe (colar)
  let r = op.raio, h = op.altura, pinos = [];
  if (op.encaixe !== false) for (const [rr, hh] of [[op.raio, op.altura], [2, 5], [1.5, 4]]) {
    if (rr > op.raio) continue; pinos = lugaresDoPino(grupos, rr + folga, Float32Array.from(cima), ax, c, hh + 0.5); if (pinos.length) { r = rr; h = hh; break; } }
  const gB = grupos.map(g => ({ l: g.l, furos: g.furos.slice() })), gC = grupos.map(g => ({ l: g.l, furos: g.furos.slice() }));
  pinos.forEach(p => {
    const dono = (gs) => gs.find(g => dentro(p, g.l)) || gs[0];
    const lb = circ2(p[0], p[1], r, n, true), lc = circ2(p[0], p[1], r + folga, n, true);
    dono(gB).furos.push(lb); dono(gC).furos.push(lc);
    paredeCil(baixo, ax, lb.slice().reverse(), c, c + h, true);           // pino: parede para fora e topo
    tampa(baixo, [{ l: lb.slice().reverse(), furos: [] }], ax, c + h, 1);
    paredeCil(cima, ax, lc.slice().reverse(), c, c + h + 0.5, false);     // furo: parede para dentro e fundo virado para o furo
    tampa(cima, [{ l: lc.slice().reverse(), furos: [] }], ax, c + h + 0.5, -1);
  });
  tampa(baixo, gB, ax, c, 1); tampa(cima, gC, ax, c, -1);
  return { baixo: new Float32Array(baixo), cima: new Float32Array(cima), pinos: pinos.length, raio: pinos.length ? r : 0, laços: grupos.length };
}
/* solda feita: tira os triângulos com vértice repetido (lascas de corte perto de outro corte); os vizinhos fecham a malha */
function semDegenerados(T) {
  const o = [], igual = (i, j) => T[i] === T[j] && T[i + 1] === T[j + 1] && T[i + 2] === T[j + 2];
  for (let i = 0; i < T.length; i += 9) { if (igual(i, i + 3) || igual(i + 3, i + 6) || igual(i, i + 6)) continue; for (let k = 0; k < 9; k++) o.push(T[i + k]); }
  return new Float32Array(o);
}
/* divide em planos até cada parte caber no limite (mm), com encaixe em cada corte; as partes vão para a mesa (z = 0), lado a lado */
function dividirParaMesa(T, op) {
  op = Object.assign({ limite: 200, raio: 3, altura: 6, folga: 0.2, encaixe: true, vao: 10, afastar: 0.3 }, op || {});
  let partes = [{ T: soldar(T), nome: "parte" }], cortes = 0, pinos = 0, semEncaixe = 0;
  for (let ax = 0; ax < 3; ax++) {
    const novas = [];
    partes.forEach(pt => {
      const cx = caixaDe(pt.T), L = cx.max[ax] - cx.min[ax]; if (L <= op.limite + 1e-6) { novas.push(pt); return; }
      // o pino sai pela tampa: cada parte precisa caber com ele (limite menos a altura do pino e 1 mm de sobra)
      // o plano anda no máximo ±janela em volta do ideal (para longe dos vértices): também entra na conta do limite
      const janela = 5, util = (op.encaixe === false ? op.limite : op.limite - op.altura - 1) - 2 * janela, k = Math.ceil(L / Math.max(util, op.limite / 2));
      let resto = pt.T;
      for (let i = 1; i < k; i++) {
        // no meio do maior vão entre vértices perto do ideal: longe deles, o corte não vira fatia fina (tangente a furo, costura)
        const ideal = cx.min[ax] + L * i / k, zs = [ideal - janela, ideal + janela];
        for (let j = ax; j < resto.length; j += 3) { const z = resto[j]; if (z > ideal - janela && z < ideal + janela) zs.push(z); }
        zs.sort((x, y) => x - y); let c = ideal, vao = -1;
        for (let j = 1; j < zs.length; j++) { const g = zs[j] - zs[j - 1], m = (zs[j] + zs[j - 1]) / 2; if (g - Math.abs(m - ideal) * 0.02 > vao) { vao = g - Math.abs(m - ideal) * 0.02; c = m; } }
        const r = cortarComEncaixe(resto, ax, c, op); cortes++; pinos += r.pinos; if (!r.pinos) semEncaixe++;
        novas.push({ T: r.baixo, nome: "parte" }); resto = r.cima;
      }
      novas.push({ T: resto, nome: "parte" });
    });
    partes = novas;
  }
  // cada parte na mesa (z = 0), lado a lado no eixo x com um vão entre elas
  partes = partes.filter(pt => pt.T.length >= 9 * 4);   // fatia sem peça (canto vazio da caixa) não vira parte
  let x = 0; partes = partes.map((pt, i) => { const cx = caixaDe(pt.T), U = semDegenerados(soldar(pt.T));
    for (let j = 0; j < U.length; j += 3) { U[j] += x - cx.min[0]; U[j + 2] -= cx.min[2]; } x += cx.max[0] - cx.min[0] + op.vao;
    return { T: U, nome: "parte-" + (i + 1), conf: conferirImpressao(U, op.limite) }; });
  return { partes, cortes, pinos, semEncaixe, limite: op.limite };
}
/* folha sintética de desenho técnico para os testes: meia-seção de uma bucha com flange (cotas conhecidas, hachura a 45°,
   linha de centro de traço e ponto, linhas de cota com setas e textos) e um quadro de notas. pxmm = pixels por mm. */
function folhaSintetica(doc, pxmm) {
  pxmm = pxmm || 6; const W = 900, H = 600, cv = doc.createElement("canvas"); cv.width = W; cv.height = H; const c = cv.getContext("2d");
  c.fillStyle = "#FFFFFF"; c.fillRect(0, 0, W, H); c.strokeStyle = "#000000"; c.fillStyle = "#000000"; c.lineWidth = 2;
  // bucha: furo Ø20 (r 10), cubo Ø36 (r 18) com 30 de altura, flange Ø60 (r 30) com 8 de espessura (z de 0 a 38)
  const B = { ri: 10, ro: 18, rf: 30, hf: 8, hh: 30 }, ex = 260, base = 480, X = r => ex + r * pxmm, Y = z => base - z * pxmm;
  const perfil = [[B.ri, 0], [B.rf, 0], [B.rf, B.hf], [B.ro, B.hf], [B.ro, B.hf + B.hh], [B.ri, B.hf + B.hh]];
  c.beginPath(); perfil.forEach((p, i) => (i ? c.lineTo : c.moveTo).call(c, X(p[0]), Y(p[1]))); c.closePath(); c.stroke();
  c.save(); c.beginPath(); perfil.forEach((p, i) => (i ? c.lineTo : c.moveTo).call(c, X(p[0]), Y(p[1]))); c.closePath(); c.clip(); c.lineWidth = 1.5;
  for (let d = -400; d < 400; d += 12) { c.beginPath(); c.moveTo(ex + d, base + 50); c.lineTo(ex + d + 400, base - 350); c.stroke(); }
  c.restore(); c.lineWidth = 2;
  // outra metade em vista (sem hachura) e a linha de centro (traço e ponto)
  c.beginPath(); perfil.forEach((p, i) => (i ? c.lineTo : c.moveTo).call(c, ex - p[0] * pxmm, Y(p[1]))); c.closePath(); c.stroke();
  c.lineWidth = 1.5; for (let y = Y(B.hf + B.hh) - 30; y < base + 30; y += 22) { c.beginPath(); c.moveTo(ex, y); c.lineTo(ex, y + 12); c.stroke(); c.beginPath(); c.moveTo(ex, y + 16); c.lineTo(ex, y + 18); c.stroke(); }
  // cotas: linhas com setas e números
  const cota = (x0, y0, x1, y1, txt) => { c.lineWidth = 1; c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1, y1); c.stroke();
    [[x0, y0, 1], [x1, y1, -1]].forEach(([x, y, s]) => { const a = Math.atan2(y1 - y0, x1 - x0); c.beginPath(); c.moveTo(x, y);
      c.lineTo(x + s * 10 * Math.cos(a) - 4 * Math.sin(a), y + s * 10 * Math.sin(a) + 4 * Math.cos(a)); c.lineTo(x + s * 10 * Math.cos(a) + 4 * Math.sin(a), y + s * 10 * Math.sin(a) - 4 * Math.cos(a)); c.closePath(); c.fill(); });
    c.font = "16px sans-serif"; c.fillText(txt, (x0 + x1) / 2 - 14, (y0 + y1) / 2 - 6); };
  cota(X(-B.rf), base + 40, X(B.rf), base + 40, "Ø60"); cota(X(B.rf) + 40, Y(0), X(B.rf) + 40, Y(B.hf + B.hh), "38"); cota(X(-B.ro), Y(B.hf + B.hh) - 40, X(B.ro), Y(B.hf + B.hh) - 40, "Ø36");
  // quadro de notas
  c.lineWidth = 2; c.strokeRect(620, 60, 250, 140); c.font = "15px sans-serif";
  ["NOTAS:", "1. MATERIAL: PLA RECICLADO", "2. COTAS EM mm", "3. TOLERANCIA GERAL 0,2"].forEach((s, i) => c.fillText(s, 632, 88 + 26 * i));
  c.font = "18px sans-serif"; c.fillText("PECA 1 - BUCHA COM FLANGE", 40, 40);
  return { cv, W, H, pxmm, bucha: B, eixoPx: { p: [ex, Y(B.hf + B.hh) - 30], q: [ex, base + 30] }, recorte: { x: 40, y: 100, w: 560, h: 480 },
    volume: Math.PI * (B.rf * B.rf - B.ri * B.ri) * B.hf + Math.PI * (B.ro * B.ro - B.ri * B.ri) * B.hh };
}
/* roda a leitura da folha sintética (no navegador) e confere a revolução */
function testeFolha(doc) {
  const F = folhaSintetica(doc, 6), r = F.recorte, cx = F.cv.getContext("2d"), im = cx.getImageData(r.x, r.y, r.w, r.h);
  const D = lerDesenho(im.data, r.w, r.h, {}), cel = 1 / F.pxmm, corposR = D.regioes.filter(g => g.tipo === "corpo");
  const ex = F.eixoPx.p[0] - r.x, eixo = { p: [ex * cel, (r.h - (F.eixoPx.p[1] - r.y)) * cel], q: [ex * cel, (r.h - (F.eixoPx.q[1] - r.y)) * cel] };
  const lacos = []; corposR.forEach(g => lacosDaRegiao(D, g.id, r.w, r.h, cel, 1).forEach(l => lacos.push(l.laco)));
  const T = revolver(lacos, eixo, 128, 1);
  return { D, corpos: corposR.length, T, volumeEsperado: F.volume, eixoDetectado: D.eixo, F };
}

/* ════════ peças de teste de impressão (geradas aqui; nada copiado de terceiros) ════════ */
function caixa(out, x0, y0, z0, dx, dy, dz) {
  const x1 = x0 + dx, y1 = y0 + dy, z1 = z0 + dz;
  quad(out, [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1], [0, 0, 1]);
  quad(out, [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [0, 0, -1]);
  quad(out, [x1, y0, z0], [x1, y1, z0], [x1, y1, z1], [x1, y0, z1], [1, 0, 0]);
  quad(out, [x0, y0, z0], [x0, y1, z0], [x0, y1, z1], [x0, y0, z1], [-1, 0, 0]);
  quad(out, [x0, y1, z0], [x1, y1, z0], [x1, y1, z1], [x0, y1, z1], [0, 1, 0]);
  quad(out, [x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1], [0, -1, 0]);
}
/* prisma de perfil convexo no plano XZ (pontos no sentido anti-horário visto de −Y), estendido de y0 a y1 */
function prismaXZ(out, perfil, y0, y1) {
  const n = perfil.length, cx = perfil.reduce((s, p) => s + p[0], 0) / n, cz = perfil.reduce((s, p) => s + p[1], 0) / n;
  for (let k = 1; k < n - 1; k++) {
    const a = perfil[0], b = perfil[k], c = perfil[k + 1];
    for (const [y, s] of [[y0, -1], [y1, 1]]) {
      const tri = [[a[0], y, a[1]], [b[0], y, b[1]], [c[0], y, c[1]]];
      const u = [tri[1][0] - tri[0][0], 0, tri[1][2] - tri[0][2]], v = [tri[2][0] - tri[0][0], 0, tri[2][2] - tri[0][2]];
      const ny_ = u[2] * v[0] - u[0] * v[2];
      (ny_ * s >= 0 ? tri : tri.reverse()).forEach(p => out.push(...p));
    }
  }
  for (let k = 0; k < n; k++) {
    const a = perfil[k], b = perfil[(k + 1) % n], mx = (a[0] + b[0]) / 2 - cx, mz = (a[1] + b[1]) / 2 - cz;
    const ex = b[0] - a[0], ez = b[1] - a[1];
    let nx_ = ez, nz_ = -ex; if (nx_ * mx + nz_ * mz < 0) { nx_ = -nx_; nz_ = -nz_; }
    quad(out, [a[0], y0, a[1]], [b[0], y0, b[1]], [b[0], y1, b[1]], [a[0], y1, a[1]], [nx_, 0, nz_]);
  }
}
const BLOCOS = "Feita de blocos fechados encostados uns nos outros (o fatiador junta os blocos). ";
function testes() {
  const P = window.PHYSIS3D, lista = [];
  lista.push({ id: "cubo-calibracao-20mm", nome: "Cubo de calibração de 20 mm", en: { nome: "20 mm calibration cube", medidas: "Solid 20 × 20 × 20 mm cube.", observar: "Measure X, Y and Z with calipers: 20.0 mm is expected. The difference shows material shrinkage or extrusion flow; also look at the first layer and the corners." },
    medidas: "Cubo maciço de 20 × 20 × 20 mm.",
    observar: "Meça X, Y e Z com paquímetro: o esperado é 20,0 mm. A diferença mostra contração do material ou fluxo de extrusão; olhe também a primeira camada e os cantos.",
    T: P && P.cubo ? P.cubo(20) : (() => { const o = []; caixa(o, 0, 0, 0, 20, 20, 20); return new Float32Array(o); })() });
  { const o = []; caixa(o, 0, 0, 0, 60, 20, 2);
    [30, 45, 60].forEach((ang, k) => { const x = 4 + 19 * k, h = 15, w = 5, t = Math.tan(ang * Math.PI / 180);
      prismaXZ(o, [[x, 2], [x + w, 2], [x + w + h * t * 0.5, 2 + h * 0.5], [x, 2 + h * 0.5]], 5, 15); });
    lista.push({ id: "teste-balanco-30-45-60", nome: "Teste de balanço (30°, 45° e 60°)", en: { nome: "Overhang test (30°, 45° and 60°)", medidas: "Made of closed blocks touching each other (the slicer joins them). 60 × 20 × 2 mm base with three 7.5 mm tall, 10 mm deep ramps whose underside leans 30°, 45° and 60° from vertical.", observar: "See from which angle the underside gets rough, stringy or drooping. Physis 3D shows overhangs above 45° in red (view option)." },
      medidas: BLOCOS + "Base de 60 × 20 × 2 mm com três rampas de 7,5 mm de altura, 10 mm de profundidade e a face de baixo inclinada a 30°, 45° e 60° da vertical.",
      observar: "Veja a partir de qual ângulo a face de baixo fica áspera, com fios soltos ou caída. O Physis 3D marca em vermelho o balanço acima de 45° (opção da vista).",
      T: new Float32Array(o) }); }
  { const o = []; caixa(o, 0, 0, 0, 90, 10, 2); let x = 0;
    const vaos = [10, 20, 30]; caixa(o, x, 0, 2, 5, 10, 10);
    vaos.forEach(v => { x += 5 + v; caixa(o, x, 0, 2, 5, 10, 10); });
    caixa(o, 0, 0, 12, x + 5, 10, 1.5);
    lista.push({ id: "teste-ponte-10-20-30mm", nome: "Teste de ponte (vãos de 10, 20 e 30 mm)", en: { nome: "Bridging test (10, 20 and 30 mm spans)", medidas: "Made of closed blocks touching each other (the slicer joins them). 90 × 10 × 2 mm base, four 5 × 10 × 10 mm pillars and a 1.5 mm slab on top, with clear spans of 10, 20 and 30 mm.", observar: "See how much the underside of the slab sags in the middle of each span and whether the strands are taut or loose." },
      medidas: BLOCOS + "Base de 90 × 10 × 2 mm, quatro pilares de 5 × 10 × 10 mm e uma laje de 1,5 mm por cima, com vãos livres de 10, 20 e 30 mm.",
      observar: "Veja quanto a face de baixo da laje cede no meio de cada vão e se os fios ficam esticados ou soltos.",
      T: new Float32Array(o) }); }
  { const o = []; caixa(o, 0, 0, 0, 50, 20, 1.5);
    [0.4, 0.8, 1.2, 1.6, 2.0].forEach((e, k) => caixa(o, 4 + 9.5 * k, 2.5, 1.5, e, 15, 10));
    lista.push({ id: "teste-espessura-parede", nome: "Teste de espessura de parede (0,4 a 2,0 mm)", en: { nome: "Wall thickness test (0.4 to 2.0 mm)", medidas: "Made of closed blocks touching each other (the slicer joins them). 50 × 20 × 1.5 mm base with five 15 × 10 mm walls, 0.4, 0.8, 1.2, 1.6 and 2.0 mm thick.", observar: "See which walls come out whole and measure each one. A wall thinner than the nozzle (0.4 mm in the Physis 3D default setup) may disappear in the slicer." },
      medidas: BLOCOS + "Base de 50 × 20 × 1,5 mm com cinco paredes de 15 × 10 mm e espessuras de 0,4, 0,8, 1,2, 1,6 e 2,0 mm.",
      observar: "Veja quais paredes saem inteiras e meça cada uma. Parede mais fina que o bico (0,4 mm na configuração padrão do Physis 3D) pode sumir no fatiador.",
      T: new Float32Array(o) }); }
  return lista;
}

/* ════════ autoteste (no navegador) ════════ */
function autoteste() {
  const r = [], ok = (nome, c, info) => r.push({ nome, ok: !!c, info: info == null ? "" : String(info) }), P = window.PHYSIS3D;
  // quadrado 4 × 4 de material numa imagem 6 × 6
  const nx = 6, ny = 6, rgba = new Uint8ClampedArray(nx * ny * 4).fill(255);
  for (let j = 1; j < 5; j++) for (let i = 1; i < 5; i++) { const k = 4 * (j * nx + i); rgba[k] = rgba[k + 1] = rgba[k + 2] = 0; }
  const M = mascara(rgba, nx, ny, 128, false);
  ok("máscara: 16 células de material", M.reduce((s, v) => s + v, 0) === 16);
  ok("inverter troca material e fundo", mascara(rgba, nx, ny, 128, true).reduce((s, v) => s + v, 0) === 20);
  const L = contornos(M, nx, ny, 2, 0.5);
  ok("contorno do quadrado: 1 laço de 4 cantos", L.length === 1 && L[0].length === 4, JSON.stringify(L));
  ok("contorno em mm (célula de 2 mm: lado 8 mm)", L.length && Math.max(...L[0].map(p => p[0])) - Math.min(...L[0].map(p => p[0])) === 8);
  const furo = M.slice(); furo[2 * nx + 2] = 0;
  ok("furo vira um segundo laço", contornos(furo, nx, ny, 1, 0.5).length === 2);
  ok("DXF com POLYLINE fechada", /POLYLINE[\s\S]*70\r\n1[\s\S]*SEQEND[\s\S]*EOF/.test(dxf(L)));
  ok("SVG com o caminho", svg(L, 12, 12).indexOf('fill-rule="evenodd"') > 0);
  const T = relevo(M, nx, ny, 2, 3, 0);
  if (P && P.medir) {
    const m = P.medir(T);
    ok("relevo: volume 8 × 8 × 3 = 192 mm³", Math.abs(m.volume_mm3 - 192) < 1e-6, m.volume_mm3);
    ok("relevo: malha fechada e orientada", m.arestas && m.arestas.fechada && m.volume_sinal === 1, JSON.stringify(m.arestas));
    const Tb = relevo(M, nx, ny, 2, 3, 1), mb = P.medir(Tb);
    ok("com base de 1 mm: 12 × 12 × 1 + 192 = 336 mm³", Math.abs(mb.volume_mm3 - 336) < 1e-6, mb.volume_mm3);
    ok("com base: malha fechada", mb.arestas && mb.arestas.fechada, JSON.stringify(mb.arestas));
    const deg = M.slice(); deg[1 * nx + 1] = 0; deg[3 * nx + 3] = 0;     // alturas diferentes nas bordas
    const md = P.medir(relevo(deg, nx, ny, 1, 2, 0.5));
    ok("bordas com alturas diferentes: sem aresta aberta", md.arestas.abertas === 0 && md.arestas.orientacao_trocada === 0, JSON.stringify(md.arestas));
    const ts = testes();
    ok("quatro peças de teste", ts.length === 4);
    const vol = { "cubo-calibracao-20mm": 8000, "teste-ponte-10-20-30mm": 90 * 10 * 2 + 4 * 5 * 10 * 10 + 80 * 10 * 1.5,
      "teste-espessura-parede": 50 * 20 * 1.5 + (0.4 + 0.8 + 1.2 + 1.6 + 2.0) * 15 * 10 };
    ts.forEach(t => { const mt = P.medir(t.T);
      ok(t.nome + ": volume positivo" + (vol[t.id] ? " e igual ao desenho" : ""), mt.volume_mm3 > 0 && (vol[t.id] == null || Math.abs(mt.volume_mm3 - vol[t.id]) < 1e-3), mt.volume_mm3);
      ok(t.nome + ": STL escrito pelo motor", P.escreverSTL(t.T, t.id).byteLength === 84 + 50 * t.T.length / 9); });
  } else ok("motor do Physis 3D presente", false);
  // foto: Otsu num histograma de dois tons, ruído e fundo
  const fx = 20, fy = 20, foto = new Uint8ClampedArray(fx * fy * 4).fill(255);
  for (let j = 0; j < fy; j++) for (let i = 0; i < fx; i++) { const k = 4 * (j * fx + i), dentroQ = i >= 5 && i < 15 && j >= 5 && j < 15, borda = i < 2;
    const v = dentroQ || borda ? 40 : 220; foto[k] = foto[k + 1] = foto[k + 2] = v; }
  foto[4 * (1 * fx + 18)] = foto[4 * (1 * fx + 18) + 1] = foto[4 * (1 * fx + 18) + 2] = 30;              // um ponto de ruído
  const pf = processarFoto(foto, fx, fy, { suavizar: 0, areaMin: 3, fundo: true });
  ok("Otsu entre os dois tons", pf.otsu > 40 && pf.otsu < 220, pf.otsu);
  ok("foto: fica só a peça (ruído e fundo da borda tirados)", pf.M.reduce((s, v) => s + v, 0) === 100, pf.M.reduce((s, v) => s + v, 0));
  ok("foto: um contorno da peça", contornos(pf.M, fx, fy, 1, 0.5).length === 1);
  // extrusão com furo: chapa 40 × 30 com furo de 10 mm
  const Tch = extrudar(PRIM.chapaComFuro(40, 30, 10), 5), vch = 40 * 30 * 5 - 5 * 48 / 2 * 25 * Math.sin(2 * Math.PI / 48);
  if (P && P.medir) { const mc = P.medir(Tch);
    ok("chapa com furo: volume da chapa menos o furo", Math.abs(mc.volume_mm3 - vch) < 1e-2, mc.volume_mm3);
    ok("chapa com furo: malha fechada", mc.arestas.fechada && mc.volume_sinal === 1, JSON.stringify(mc.arestas));
    const ml = P.medir(extrudar(PRIM.perfil("L", 30, 20, 3), 50));
    ok("perfil L: volume (30 + 20 − 3) × 3 × 50", Math.abs(ml.volume_mm3 - 47 * 3 * 50) < 1e-2 && ml.arestas.fechada, ml.volume_mm3); }
  const dx = "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n0\n0\nLINE\n8\n0\n10\n10\n20\n0\n11\n10\n21\n10\n0\nLINE\n8\n0\n10\n10\n20\n10\n11\n0\n21\n10\n0\nLINE\n8\n0\n10\n0\n20\n10\n11\n0\n21\n0\n0\nCIRCLE\n8\n0\n10\n50\n20\n0\n40\n5\n0\nENDSEC\n0\nEOF\n";
  const ld = lerDxf(dx);
  ok("DXF: quatro linhas viram um laço e o círculo outro", ld.lacos.length === 2 && ld.linhas.length === 0, JSON.stringify(ld.lacos.map(l => l.length)));
  ok("DXF de volta: lido pelo próprio leitor", lerDxf(dxf([[[0, 0], [10, 0], [10, 10]]])).lacos.length === 1);
  const c1 = { nome: "a", T: transformar(extrudar(PRIM.retangulo(10, 10), 10), [0, 0, 0]) }, c2 = { nome: "b", T: transformar(c1.T, [5, 0, 0]) }, c3 = { nome: "c", T: transformar(c1.T, [10, 0, 0]) };
  const co = colisoes([c1, c2, c3]);
  ok("colisão por caixas: a×b e b×c se cruzam; a e c só encostam", co.length === 2 && co[0].a === 0 && co[0].b === 1 && co[1].a === 1 && co[1].b === 2, JSON.stringify(co));
  const z3 = escrever3MFMontagem([{ nome: "a", T: c1.T, cor: "#0B3D2E" }, { nome: "b", T: c3.T, cor: "#F97316" }]);
  ok("3MF da montagem é ZIP com duas peças", z3[0] === 0x50 && z3[1] === 0x4B && new TextDecoder().decode(z3).split("<object ").length === 3);
  const ifc = escreverIfc([{ nome: "Caixa", T: c1.T }], "teste");
  // desenho técnico: folha sintética com a meia-seção de uma bucha de cotas conhecidas (só no navegador, com canvas)
  if (typeof document !== "undefined" && document.createElement && P && P.medir) {
    try { const tf = testeFolha(document), mf = P.medir(tf.T), erro = Math.abs(mf.volume_mm3 - tf.volumeEsperado) / tf.volumeEsperado;
      ok("desenho técnico: texto, cotas e quadro de notas não viram corpo", tf.D.regioes.filter(g => g.tipo === "corpo").length === 2, JSON.stringify(tf.D.regioes.map(g => g.tipo + ":" + g.motivo + ":" + g.area)));
      ok("desenho técnico: a hachura é lida como hachura", tf.D.hachuras >= 4, tf.D.hachuras);
      ok("desenho técnico: linha de centro achada", !!tf.eixoDetectado && Math.abs(tf.eixoDetectado.p[0] - (tf.F.eixoPx.p[0] - tf.F.recorte.x)) <= 3, JSON.stringify(tf.eixoDetectado));
      ok("revolução da meia-seção: malha fechada", mf.arestas.fechada && mf.volume_sinal === 1, JSON.stringify(mf.arestas));
      ok("revolução da meia-seção: volume a ±2 % do analítico", erro <= 0.02, mf.volume_mm3.toFixed(1) + " × " + tf.volumeEsperado.toFixed(1) + " (" + (100 * erro).toFixed(2) + " %)");
      // a folha inteira: o quadro de notas e o título são texto; as setas e as cotas, pequenas demais; ficam só as duas metades da bucha
      const F2 = tf.F, D2 = lerDesenho(F2.cv.getContext("2d").getImageData(0, 0, F2.W, F2.H).data, F2.W, F2.H, {});
      ok("desenho técnico: na folha inteira, notas e cotas ficam de fora", D2.regioes.filter(g => g.tipo === "corpo").length === 2 && D2.regioes.some(g => g.motivo === "texto"),
        JSON.stringify(D2.regioes.map(g => g.tipo + ":" + g.motivo)));
      ok("desenho técnico: os textos são reconhecidos e ignorados", D2.textos >= 20, D2.textos);
    } catch (e) { ok("desenho técnico: a folha sintética roda", false, e && e.message); }
  }
  const pa = extrudar(PRIM.retangulo(4, 20).map(l => l.map(p => [p[0], p[1] + 20])), 5), pad = padraoCircular(pa, 6, [0, 0]);
  ok("padrão circular de 6: 6 corpos", pad.length === 6 && corpos(juntar(pad)) === 6, corpos(juntar(pad)));
  if (P && P.medir) ok("padrão circular: volume 6 vezes o de uma pá", Math.abs(P.medir(juntar(pad)).volume_mm3 - 6 * 4 * 20 * 5) < 1e-2);
  const rv = revolver([[[10, 0], [20, 0], [20, 10], [10, 10]]], { p: [0, 0], q: [0, 10] }, 256, 1);
  if (P && P.medir) ok("revolução de um retângulo: tubo π(20² − 10²)·10 a 0,1 %", Math.abs(P.medir(rv).volume_mm3 - Math.PI * 300 * 10) / (Math.PI * 3000) < 0.001, P.medir(rv).volume_mm3);
  const cf = ajustarCirculo(PRIM.circulo(30, 40)[0].map(p => [p[0] + 5, p[1] - 3]));
  ok("círculo por mínimos quadrados: centro e raio", Math.abs(cf.cx - 5) < 1e-6 && Math.abs(cf.cy + 3) < 1e-6 && Math.abs(cf.r - 15) < 1e-6);
  ok("IFC4 com IfcTriangulatedFaceSet", /FILE_SCHEMA\(\('IFC4'\)\)/.test(ifc) && ifc.indexOf("IFCTRIANGULATEDFACESET") > 0 && ifc.indexOf("IFCBUILDINGELEMENTPROXY") > 0);
  // qualquer impressora (dona, 22/11/2026): apoiar na mesa, conferir a malha e dividir acima de 200 mm com encaixe
  { const fl = transformar(extrudar(PRIM.retangulo(30, 20), 10), [0, 0, 25], [0, 0, 0], 1, [0, 0, 0]), ap = apoiarNaMesa(fl);
    ok("peça flutuando vai para a mesa (z mínimo = 0)", Math.abs(caixaDe(ap).min[2]) < 1e-9 && !conferirImpressao(fl).apoiada && conferirImpressao(ap).apoiada); }
  { const cx = extrudar(PRIM.retangulo(20, 20), 20), furado = cx.slice(9), c1 = conferirImpressao(cx), c2 = conferirImpressao(furado);
    ok("conferência acusa malha aberta (sem um triângulo)", c1.fechada && !c2.fechada && c2.abertas === 3); }
  { const barra = extrudar(PRIM.retangulo(300, 40), 40), d = dividirParaMesa(barra), v = d.partes.reduce((n, q) => n + (P ? P.medir(q.T).volume_mm3 : 0), 0);
    ok("barra de 300 mm: 2 partes até 200 mm, fechadas, apoiadas, com pinos", d.partes.length === 2 && d.pinos >= 1 && d.partes.every(q => q.conf.fechada && q.conf.apoiada && !q.conf.grande));
    ok("divisão conserva o volume (±0,1 %)", !P || Math.abs(v - 300 * 40 * 40) / (300 * 40 * 40) < 0.001, v); }
  { const tf = testeFolha(document), grande = transformar(tf.T, [0, 0, 0], [0, 0, 0], 6, [0, 0, 0]), d = dividirParaMesa(grande, { limite: 100 });
    ok("bucha revolucionada de 360 mm em partes de até 100 mm: todas fechadas, dentro do limite; encaixe em pelo menos 90 % dos cortes", d.partes.length >= 30 && d.partes.every(q => q.conf.fechada && !q.conf.grande && q.T.length > 0) && d.semEncaixe <= 0.1 * d.cortes, d.partes.length + " partes, " + d.semEncaixe + " cortes sem encaixe (canto fino)"); }
  { const tubo = extrudar(PRIM.circulo(80, 48).concat([PRIM.circulo(60, 48)[0].reverse()]), 450), d = dividirParaMesa(tubo);
    ok("tubo de parede de 10 mm: pino menor no encaixe", d.pinos >= 2 && d.semEncaixe === 0 && d.partes.every(q => q.conf.fechada)); }
  return r;
}

window.PhysisImagem3D = { mascara, contornos, svg, dxf, relevo, campoDeAlturas, testes, autoteste, cinza, suavizar, otsu, limpar, processarFoto,
  extrudar, PRIM, lerDxf, caixaDe, transformar, juntar, colisoes, escrever3MFMontagem, escreverIfc, CORES_PECA,
  rotular8, larguraTraco, morfo, afinar, tracarEsqueleto, ajustarCirculo, primitivas, recortarLaco, lerDesenho, lacosDaRegiao, revolver,
  padraoCircular, corpos, folhaSintetica, testeFolha, apoiarNaMesa, soldar, arestas, conferirImpressao, cortarPlano, dentroMalha, dividirParaMesa,
  versao: "physis-imagem-3d-0.4" };
})();
