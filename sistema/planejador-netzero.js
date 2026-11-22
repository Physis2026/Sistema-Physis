/* planejador-netzero.js v1 · aba "Net zero" do Planejador Physis · VERSÃO DE TESTE (22/11/2026)
   SPDX-License-Identifier: AGPL-3.0-only · Copyright (C) 2026 Physis Engineering

   Decisão da dona (M&A pg:b880e775e565): construir em teste a aba Net zero, dividida pelos planos do Planejador.
   Desenho: desenhos/planejador-aba-netzero.html. Copiado igual para dentro do Planejador por ferramentas/sincronizar.py
   (bloco <script id="planejador-netzero">), depois do núcleo: usa MOD, LIC, PLANOS, STEPS, R_, run, T, GEO, ED, h, card…
   Não muda conta do núcleo: lê o que o núcleo calcula (R.en, R.yield, R.pv, R.corte, R.aterro, R.chuva, Aptidão) e
   acrescenta verificações e sugestões. Sem dado, mostra [MARCADOR]. Contas só na tela (nada no servidor, regra 4).

   Planos (cada um inclui o anterior):
   - Livre: norte de projeto e verdadeiro; itens sem lugar; saldo de energia e de água; bloco no Documento EP.
   - Profissional: terra (corte × aterro); desnível sob a projeção; pressão por gravidade; bomba; beirais; FV onde cabe.
   - Especialista: aptidão cruzada com realocação; circuitos de água separados.
   - Empresa: variantes guardadas e comparadas; meta de certificação; planejado × medido (gêmeo).
*/
(function () {
  "use strict";
  if (typeof MOD === "undefined" || typeof STEPS === "undefined" || typeof R_ === "undefined") return;
  var RADN = Math.PI / 180;
  var nfmt = function (v, d) { return v == null || !isFinite(v) ? "[MARCADOR]" : NF(v, d); };
  var dentroLote = function (it) { var p = S.terreno.poly; return p.length >= 3 && corners(it).every(function (c) { return GEO.inside(c, p); }); };
  var cota = function (it) { return it.cota != null ? it.cota : T.z(it.x, it.y); };
  var LIMITE_PRESSAO_M = 40;   // a mesma regra do núcleo (R.pressao, NBR 5626)

  /* rosa com norte de projeto (para cima na planta) e norte verdadeiro (giro em graus, horário); sem giro: "NV?" */
  function rosa(giro) {
    var svg = '<svg viewBox="-60 -34 120 68" width="120" height="68" role="img" aria-label="' +
      (giro == null ? "Norte de projeto para cima; norte verdadeiro não informado" : "Norte de projeto para cima; norte verdadeiro a " + NF(giro, 1) + " graus") + '">' +
      '<g transform="translate(-28,4)"><path d="M0,-22 L6,6 L0,2 L-6,6 Z" fill="currentColor"/><text y="22" text-anchor="middle" font-size="10" font-weight="700" fill="currentColor">NP</text></g>' +
      '<g transform="translate(28,4) rotate(' + (giro || 0) + ')"><path d="M0,-22 L6,6 L0,2 L-6,6 Z" fill="#BB6B4A"/></g>' +
      '<text x="28" y="26" text-anchor="middle" font-size="10" font-weight="700" fill="currentColor">' + (giro == null ? "NV?" : "NV") + '</text></svg>';
    var d = h("div", { class: "nz-rosa" }); d.innerHTML = svg; return d;
  }

  /* ---------------------------------------------------------------- Livre */
  MOD.registrar({
    id: "nz_livre", aba: "netzero", nome: "Net zero · essencial", plano: "livre", estado: "disponível",
    resumo: "norte, itens sem lugar e saldo de energia e água",
    padrao: { metaEnergia: 110, kwpInstalado: null, norteVerdadeiro: null },
    calcular: function (R, p) {
      /* edificação sem área ou fora do lote = item da lista sem lugar; anotações sem área (viveiro em terraço, caminho) não contam */
      var semLugar = S.itens.filter(function (i) { var t = TIPOS[i.tipo]; if (!t || t.cat === "ponto" || i.tipo === "acesso") return false;
          return t.cat === "ed" ? (areaItem(i) < 0.05 || !dentroLote(i)) : (areaItem(i) >= 0.05 && !dentroLote(i)); })
        .map(function (i) { return i.nome + (areaItem(i) < 0.05 ? " (sem área)" : " (fora do lote)"); });
      var kwh = R.en ? R.en.kwh : null, prod = R.yield || null;
      var kwp = p.kwpInstalado != null ? p.kwpInstalado : (R.pv ? R.pv.kwp : null);
      var ger = kwp != null && prod ? kwp * prod / 12 : null;
      var saldo = ger != null && kwh ? ger / kwh * 100 : null;
      var falta = kwh && prod ? Math.max(0, (p.metaEnergia || 100) / 100 * kwh * 12 / prod - (kwp || 0)) : null;
      var ch = R.chuva || null;
      return { semLugar: semLugar, kwh: kwh, prod: prod, kwp: kwp, ger: ger, saldo: saldo, falta: falta, meta: p.metaEnergia || 100,
        aguaCob: ch && ch.cob != null ? ch.cob * 100 : null, cisterna: ch ? ch.V : null, norte: p.norteVerdadeiro, kwpDoNucleo: p.kwpInstalado == null };
    },
    tela: function (r) {
      return h("div", {},
        h("div", { class: "row", style: "align-items:center;gap:1rem;flex-wrap:wrap" }, rosa(r.norte),
          h("p", { class: "hint", style: "margin:0;max-width:60ch" }, r.norte == null
            ? "Norte verdadeiro não informado: [MARCADOR]. Informe o giro em relação ao norte de projeto (o topógrafo confirma). Todo desenho de construção mostra os dois."
            : "Norte de projeto para cima na planta; norte verdadeiro a " + NF(r.norte, 1) + "° (sentido horário). Orientar telhados e placas pelo verdadeiro.")),
        h("div", { class: "grid" }, mfld("nz_livre", "norteVerdadeiro", "Norte verdadeiro em relação ao de projeto", { unit: "graus, horário" }),
          mfld("nz_livre", "metaEnergia", "Meta de energia", { unit: "% do consumo", min: 100 }),
          mfld("nz_livre", "kwpInstalado", "Placas instaladas", { unit: "kWp", min: 0, dica: "vazio: o tamanho calculado pelo núcleo (100 %)" })),
        kpis([[nfmt(r.saldo, 1) + " %", "energia: geração ÷ consumo"], [nfmt(r.falta, 2) + " kWp", "faltam para a meta de " + NF(r.meta, 0) + " %"],
          [nfmt(r.aguaCob, 0) + " %", "água de chuva: demanda atendida"], [String(r.semLugar.length), "itens sem lugar"]]),
        r.semLugar.length ? tbl(["Item sem lugar"], r.semLugar.map(function (n) { return [n]; })) : h("p", { class: "hint" }, "Todos os itens do programa têm lugar dentro do lote."));
    },
    verificar: function (r, C) {
      if (r.norte == null) C("warn", "Net zero: norte verdadeiro não informado ([MARCADOR]); o estudo solar usa o norte de projeto", "netzero");
      r.semLugar.forEach(function (n) { C("warn", "Net zero: " + n + " — todo item da lista precisa de lugar", "netzero"); });
      if (r.saldo != null && r.saldo < r.meta) C("info", "Net zero: energia em " + NF(r.saldo, 1) + " %, abaixo da meta de " + NF(r.meta, 0) + " % (faltam " + NF(r.falta, 2) + " kWp)", "netzero");
    },
    blocos: function (r, ad) {
      ad.P("Energia: geração " + nfmt(r.ger, 0) + " kWh/mês para consumo de " + nfmt(r.kwh, 0) + " kWh/mês (" + nfmt(r.saldo, 1) + " %); meta de " + NF(r.meta, 0) + " % pede mais " + nfmt(r.falta, 2) + " kWp.");
      ad.P("Água de chuva: " + nfmt(r.aguaCob, 0) + " % da demanda com cisterna de " + nfmt(r.cisterna, 1) + " m³. Norte verdadeiro: " + (r.norte == null ? "[MARCADOR]" : NF(r.norte, 1) + "° do norte de projeto") + ".");
      if (r.semLugar.length) ad.P("Itens sem lugar: " + r.semLugar.join("; ") + ".");
    }
  });

  /* ---------------------------------------------------------------- Profissional */
  MOD.registrar({
    id: "nz_prof", aba: "netzero", nome: "Net zero · terreno e água", plano: "profissional", estado: "disponível",
    resumo: "terra, desnível, pressão por gravidade, bomba, beirais e onde cabe FV",
    padrao: { janela: 2.1, solBarrado: 70, vazao: null, altura: null, horas: null, rendimento: null },
    calcular: function (R, p) {
      var corte = R.corte || 0, aterro = R.aterro || 0;
      var desn = ED().map(function (i) { var zs = corners(i).map(function (c) { return T.z(c[0], c[1]); }); return { nome: i.nome, dz: Math.max.apply(null, zs) - Math.min.apply(null, zs) }; })
        .filter(function (d) { return d.dz > 1.5; }).sort(function (a, b) { return b.dz - a.dz; });
      var cist = S.itens.filter(function (i) { return i.tipo === "cisterna"; }).map(function (i) { return { nome: i.nome, z: cota(i) }; }).sort(function (a, b) { return b.z - a.z; });
      var topo = cist[0] || null, pressao = [];
      if (topo) ED().forEach(function (i) { var hm = topo.z - cota(i); if (hm < 0 || hm > LIMITE_PRESSAO_M) pressao.push({ nome: i.nome, h: hm }); });
      var lat = S.terreno.lat0 != null ? S.terreno.lat0 : (S.inicio && S.inicio.lat != null ? +S.inicio.lat : null);
      var inverno = lat != null ? 90 - Math.abs(lat) - 23.44 : null, verao = lat != null ? 90 - Math.abs(Math.abs(lat) - 23.44) : null;
      var beiral = p.janela && p.solBarrado ? p.janela / Math.tan(p.solBarrado * RADN) : null;
      var bomba = p.vazao && p.altura && p.horas && p.rendimento ? 1000 * 9.81 * (p.vazao / 3600) * p.altura / p.rendimento * p.horas * 30 / 1000 : null;
      var pv = R.pv || null, estac = S.itens.filter(function (i) { return i.tipo === "estacionamento"; }).reduce(function (a, i) { return a + areaItem(i); }, 0);
      return { corte: corte, aterro: aterro, sobra: corte - aterro, desn: desn, topo: topo, pressao: pressao, lat: lat, inverno: inverno, verao: verao,
        beiral: beiral, bomba: bomba, pv: pv, estac: estac, falta_m2: pv ? Math.max(0, pv.areaNec - pv.roofU) : null };
    },
    tela: function (r) {
      return h("div", {},
        kpis([[nfmt(r.sobra, 0) + " m³", "terra sobrando (corte − aterro): solo-cimento e platôs"], [String(r.desn.length), "construções com desnível > 1,5 m sob a projeção"],
          [String(r.pressao.length), "pontos fora da faixa de pressão por gravidade"], [nfmt(r.beiral, 2) + " m", "beiral para barrar o sol acima de " + NF(MOD.p("nz_prof").solBarrado, 0) + "°"]]),
        r.desn.length ? tbl(["Construção", "Desnível sob a projeção", "Leitura"], r.desn.map(function (d) { return [d.nome, NF(d.dz, 1) + " m", "estrutura elevada ou semi-enterrada (parede de montante como contenção)"]; })) : null,
        r.topo ? h("p", { class: "hint" }, "Reservatório mais alto: " + r.topo.nome + " a " + NF(r.topo.z, 2) + " m. Acima dele precisa de bomba; mais de " + LIMITE_PRESSAO_M + " m abaixo, válvula redutora (NBR 5626).") : h("p", { class: "hint" }, "Sem cisterna desenhada: a água por gravidade não pode ser avaliada."),
        r.pressao.length ? tbl(["Ponto", "Altura abaixo do reservatório", "Leitura"], r.pressao.map(function (q) { return [q.nome, NF(q.h, 1) + " m", q.h < 0 ? "acima do reservatório: bomba ou reservatório mais alto" : "pressão alta: redutora ou caixa de quebra-pressão"]; })) : null,
        h("p", { class: "hint" }, r.lat == null ? "Sol do lugar: [MARCADOR] latitude do terreno." : "Sol ao meio-dia: " + NF(r.verao, 0) + "° no verão e " + NF(r.inverno, 0) + "° no inverno (latitude " + NF(r.lat, 2) + "°)."),
        r.pv ? h("p", { class: "hint" }, "FV: " + NF(r.pv.areaNec, 0) + " m² de placas para 100 % e " + NF(r.pv.roofU, 0) + " m² de telhado útil" + (r.falta_m2 > 0 ? "; faltam " + NF(r.falta_m2, 0) + " m²: pérgolas sobre os " + NF(r.estac, 0) + " m² de estacionamento" : "") + ".") : null,
        h("div", { class: "grid" }, mfld("nz_prof", "janela", "Altura da janela", { unit: "m" }), mfld("nz_prof", "solBarrado", "Barrar o sol acima de", { unit: "graus" }),
          mfld("nz_prof", "vazao", "Bomba: vazão", { unit: "m³/h" }), mfld("nz_prof", "altura", "Bomba: altura", { unit: "m", dica: "diferença de nível + perdas" }),
          mfld("nz_prof", "horas", "Bomba: horas por dia", { unit: "h" }), mfld("nz_prof", "rendimento", "Bomba: rendimento", { unit: "0 a 1" })),
        h("p", { class: "hint" }, "Energia da bomba: " + nfmt(r.bomba, 1) + " kWh/mês (ρ·g·Q·H ÷ η). Subir água que poderia descer gasta energia à toa: compare alturas antes de escolher onde fica cada tanque."));
    },
    verificar: function (r, C) {
      if (r.sobra > 0) C("info", "Net zero: sobram " + NF(r.sobra, 0) + " m³ de terra; reusar em solo-cimento ou platôs evita bota-fora", "netzero");
      r.pressao.forEach(function (q) { C("warn", "Net zero: " + q.nome + (q.h < 0 ? " fica acima do reservatório mais alto" : " a " + NF(q.h, 1) + " m abaixo do reservatório (limite " + LIMITE_PRESSAO_M + " m)"), "netzero"); });
    },
    blocos: function (r, ad) {
      ad.P("Terra: corte " + NF(r.corte, 1) + " m³ e aterro " + NF(r.aterro, 1) + " m³ (sobra " + NF(r.sobra, 1) + " m³). Beiral sugerido: " + nfmt(r.beiral, 2) + " m.");
      if (r.desn.length) ad.TB(["Construção", "Desnível (m)"], r.desn.map(function (d) { return [d.nome, NF(d.dz, 1)]; }));
    }
  });

  /* ---------------------------------------------------------------- Especialista */
  var CIRC = [["efluente", /fossa|filtro|tratamento|biodigest|floresta filtrante|esgoto/i], ["produção", /peixe|aquapon|wetland|^lago/i],
    ["reserva", /cisterna|reserva|mini-lago|^c\d/i], ["drenagem", /chuva|infiltra|vala|deten/i], ["banho", /piscina|regenera/i]];
  function circuito(i) { var c = CIRC.find(function (q) { return q[1].test(i.nome); }) || CIRC.find(function (q) { return q[1].test(i.tipo); }); return c ? c[0] : "a classificar"; }
  MOD.registrar({
    id: "nz_esp", aba: "netzero", nome: "Net zero · aptidão e circuitos", plano: "especialista", estado: "disponível",
    resumo: "aptidão cruzada com realocação e circuitos de água separados",
    padrao: { notaMinima: 0.4, folga: 1.5, passo: 0.5 },
    calcular: function (R, p) {
      var apt = MOD.porId.apt && LIC.liberado("apt") ? MOD.res("apt") : null, g = T.build(), sugest = [];
      if (apt && !apt.erro && g) {
        /* média da nota num retângulo em tempo constante: tabelas de somas acumuladas da nota e das células dentro do lote */
        var W1 = g.nx + 1, SA = new Float64Array(W1 * (g.ny + 1)), SC = new Float64Array(W1 * (g.ny + 1));
        for (var jj = 0; jj < g.ny; jj++) for (var ii = 0; ii < g.nx; ii++) { var kk = jj * g.nx + ii, o = (jj + 1) * W1 + ii + 1, dentro = g.ins[kk] ? 1 : 0;
          SA[o] = (dentro ? apt.A[kk] : 0) + SA[o - 1] + SA[o - W1] - SA[o - W1 - 1]; SC[o] = dentro + SC[o - 1] + SC[o - W1] - SC[o - W1 - 1]; }
        var soma = function (T_, i0, j0, i1, j1) { return T_[(j1 + 1) * W1 + i1 + 1] - T_[j0 * W1 + i1 + 1] - T_[(j1 + 1) * W1 + i0] + T_[j0 * W1 + i0]; };
        var media = function (x0, y0, x1, y1) {
          var i0 = Math.max(0, Math.ceil((x0 - g.x0) / g.cs)), i1 = Math.min(g.nx - 1, Math.floor((x1 - g.x0) / g.cs)),
              j0 = Math.max(0, Math.ceil((y0 - g.y0) / g.cs)), j1 = Math.min(g.ny - 1, Math.floor((y1 - g.y0) / g.cs));
          if (i1 < i0 || j1 < j0) return null; var c = soma(SC, i0, j0, i1, j1); return c ? soma(SA, i0, j0, i1, j1) / c : null; };
        var eds = ED(), caixa = function (i) { var cs = corners(i), xs = cs.map(function (c) { return c[0]; }), ys = cs.map(function (c) { return c[1]; }); return [Math.min.apply(null, xs), Math.min.apply(null, ys), Math.max.apply(null, xs), Math.max.apply(null, ys)]; };
        var rec = S.regras && S.regras.recLat != null ? +S.regras.recLat : 0, poly = S.terreno.poly, ocupadas = [];
        var dSeg = function (P, A, B) { var vx = B[0] - A[0], vy = B[1] - A[1], t = Math.max(0, Math.min(1, ((P[0] - A[0]) * vx + (P[1] - A[1]) * vy) / (vx * vx + vy * vy || 1))); return Math.hypot(P[0] - A[0] - t * vx, P[1] - A[1] - t * vy); };
        var longeDoLimite = function (c) { for (var q = 0; q < poly.length; q++) if (dSeg(c, poly[q], poly[(q + 1) % poly.length]) < rec) return false; return true; };
        eds.forEach(function (it) {
          var b = caixa(it), nota = media(b[0], b[1], b[2], b[3]);
          if (nota == null || nota > p.notaMinima) return;
          var w = b[2] - b[0], d = b[3] - b[1], outros = eds.filter(function (o) { return o !== it; }).map(caixa).concat(ocupadas), melhor = null, xs = S.terreno.poly.map(function (q) { return q[0]; }), ys = S.terreno.poly.map(function (q) { return q[1]; });
          for (var x = Math.min.apply(null, xs); x + w <= Math.max.apply(null, xs); x += p.passo) for (var y = Math.min.apply(null, ys); y + d <= Math.max.apply(null, ys); y += p.passo) {
            var c4 = [[x, y], [x + w, y], [x + w, y + d], [x, y + d]];
            if (!c4.every(function (c) { return GEO.inside(c, poly) && longeDoLimite(c); })) continue;
            if (outros.some(function (o) { return x < o[2] + p.folga && x + w > o[0] - p.folga && y < o[3] + p.folga && y + d > o[1] - p.folga; })) continue;
            var v = media(x, y, x + w, y + d);
            if (v != null && (!melhor || v > melhor.v)) melhor = { x: x + w / 2, y: y + d / 2, v: v };
          }
          if (melhor) ocupadas.push([melhor.x - w / 2, melhor.y - d / 2, melhor.x + w / 2, melhor.y + d / 2]);
          sugest.push({ id: it.id, nome: it.nome, nota: nota, nova: melhor });
        });
      }
      var agua = S.itens.filter(function (i) { return TIPOS[i.tipo] && (TIPOS[i.tipo].cat === "agua" || TIPOS[i.tipo].cat === "inf" || /peixe|lago|wetland/i.test(i.nome)); })
        .map(function (i) { return { nome: i.nome, circ: circuito(i), z: cota(i) }; });
      var efl = agua.filter(function (a) { return a.circ === "efluente"; }), limpo = agua.filter(function (a) { return a.circ === "banho" || a.circ === "produção"; });
      var risco = efl.filter(function (e) { return limpo.some(function (l) { return e.z > l.z; }); }).map(function (e) { return e.nome; });
      return { semApt: !apt || !!(apt && apt.erro), sugest: sugest, agua: agua, risco: risco };
    },
    tela: function (r) {
      return h("div", {},
        h("p", { class: "hint" }, "A nota olha o terreno (declividade, sol, acesso, caminhos da água). Antes de aplicar, confira o uso e a vizinhança: blocos que trabalham juntos devem mudar juntos. Recuo das regras usado: " + (S.regras && S.regras.recLat != null ? NF(+S.regras.recLat, 1) + " m" : "[MARCADOR] (sem recuo lateral nas regras)") + "."),
        r.semApt ? h("p", { class: "hint" }, "Ative o módulo Aptidão (plano Especialista) para cruzar as notas.") :
          r.sugest.length ? tbl(["Construção", "Nota agora", "Melhor posição", "Nota nova", ""], r.sugest.map(function (s) {
            return [s.nome, NF(s.nota, 2), s.nova ? "x " + NF(s.nova.x, 1) + " · y " + NF(s.nova.y, 1) : "sem lugar livre", s.nova ? NF(s.nova.v, 2) : "—",
              s.nova && s.nova.v > s.nota + 0.05 ? h("button", { class: "btn", type: "button", onclick: function () { mutate(function () { var it = S.itens.find(function (i) { return i.id === s.id; }); if (it) { it.x = +s.nova.x.toFixed(2); it.y = +s.nova.y.toFixed(2); } }, "realocado pela aptidão: " + s.nome); } }, "Aplicar") : ""];
          })) : h("p", { class: "hint" }, "Nenhuma construção com nota de aptidão abaixo do mínimo."),
        tbl(["Item de água", "Circuito", "Cota (m)"], r.agua.map(function (a) { return [a.nome, a.circ, NF(a.z, 2)]; })),
        h("p", { class: "hint" }, "Circuitos que não se misturam: banho (piscina e regeneração), produção (peixes, lago, wetland → hortas), reserva (cisternas, mini-lago), drenagem (jardins de chuva) e efluente (fossa, filtro, floresta filtrante). Águas cinzas vão para a floresta filtrante e voltam como irrigação."),
        h("div", { class: "grid" }, mfld("nz_esp", "notaMinima", "Nota mínima de aptidão", { min: 0, max: 1 }), mfld("nz_esp", "folga", "Folga entre edificações", { unit: "m" })));
    },
    verificar: function (r, C) {
      r.sugest.forEach(function (s) { if (s.nova && s.nova.v > s.nota + 0.05) C("info", "Net zero: " + s.nome + " tem aptidão " + NF(s.nota, 2) + "; há lugar com " + NF(s.nova.v, 2), "netzero"); });
      r.risco.forEach(function (n) { C("warn", "Net zero: " + n + " (efluente) está acima de água de banho ou produção: conferir o caminho da água", "netzero"); });
    },
    blocos: function (r, ad) {
      if (r.sugest.length) ad.TB(["Construção", "Nota", "Nota na posição sugerida"], r.sugest.map(function (s) { return [s.nome, NF(s.nota, 2), s.nova ? NF(s.nova.v, 2) : "—"]; }));
    }
  });

  /* ---------------------------------------------------------------- Empresa */
  MOD.registrar({
    id: "nz_emp", aba: "netzero", nome: "Net zero · variantes e certificação", plano: "empresa", estado: "disponível",
    resumo: "variantes guardadas e comparadas, meta de certificação e planejado × medido",
    padrao: { variantes: [], economiaMeta: 20 },
    calcular: function (R, p) {
      var l = MOD.res("nz_livre"), pr = LIC.liberado("nz_prof") ? MOD.res("nz_prof") : null;
      var atual = { nome: "atual", saldo: l && l.saldo, semLugar: l ? l.semLugar.length : null, sobra: pr && pr.sobra, ocup: R.to != null ? R.to * 100 : null };
      return { atual: atual, variantes: p.variantes || [], meta: p.economiaMeta };
    },
    tela: function (r) {
      var linhas = r.variantes.concat([r.atual]).map(function (v) { return [v.nome, nfmt(v.saldo, 1) + " %", v.semLugar == null ? "—" : String(v.semLugar), nfmt(v.sobra, 0) + " m³", nfmt(v.ocup, 1) + " %"]; });
      return h("div", {},
        tbl(["Variante", "Energia", "Itens sem lugar", "Terra sobrando", "Ocupação"], linhas),
        h("div", { class: "row" }, h("button", { class: "btn", type: "button", onclick: function () {
          var nome = "variante " + (r.variantes.length + 1); mutate(function () { MOD.p("nz_emp").variantes = (MOD.p("nz_emp").variantes || []).concat([Object.assign({}, r.atual, { nome: nome })]); }, "variante guardada: " + nome);
        } }, "Guardar a planta atual como variante")),
        h("p", { class: "hint" }, "Meta de certificação: economia mínima de " + NF(r.meta, 0) + " % em energia, água e energia incorporada (EDGE, doc. 05). Planejado × medido: [MARCADOR] até ligar o gêmeo e a validação (M&V)."),
        h("div", { class: "grid" }, mfld("nz_emp", "economiaMeta", "Meta de economia (certificação)", { unit: "%" })));
    },
    blocos: function (r, ad) { if (r.variantes.length) ad.TB(["Variante", "Energia (%)"], r.variantes.map(function (v) { return [v.nome, nfmt(v.saldo, 1)]; })); }
  });

  /* ---------------------------------------------------------------- a aba */
  var k = STEPS.findIndex(function (s) { return s[0] === "documento"; });
  if (!STEPS.some(function (s) { return s[0] === "netzero"; })) STEPS.splice(k < 0 ? STEPS.length : k, 0, ["netzero", "Net zero"]);
  R_.netzero = function (el) {
    el.append(h("h2", {}, "Net zero"),
      h("p", { class: "lead" }, "Energia, água e terra do lugar, com o norte sempre indicado. Cada plano acrescenta uma parte; sem dado, a aba mostra [MARCADOR]. Versão de teste."));
    if (!T.build()) { el.append(card(null, "Importe o terreno no passo 1 para usar a aba Net zero.")); return; }
    MOD.lista.filter(function (m) { return m.aba === "netzero"; }).forEach(function (m) {
      var cab = PLANOS[m.plano].nome + " · " + m.resumo;
      if (!LIC.liberado(m.id)) { el.append(card(m.nome, cab, h("p", { class: "hint" }, "Parte do plano " + PLANOS[m.plano].nome + ". Ative uma licença que a inclua ou use a avaliação na aba Módulos."))); return; }
      MOD.p(m.id);   // com parâmetros guardados, a parte entra nas verificações e no Documento EP
      var r = MOD.res(m.id);
      el.append(card(m.nome, cab, r && r.erro ? h("p", { class: "hint" }, "Não foi possível calcular: " + r.erro) : m.tela(r, MOD.p(m.id))));
    });
  };
  if (!document.getElementById("nz-css")) { var st = document.createElement("style"); st.id = "nz-css"; st.textContent = ".nz-rosa{color:var(--ink)}"; document.head.appendChild(st); }
  if (typeof S !== "undefined" && S && typeof route === "function") route();
})();
