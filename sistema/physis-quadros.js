/* physis-quadros.js — aba Quadros elétricos (25/11/2026): um quadro por função/módulo, integrados.
   - QF-AVAC: o quadro do AVAC (mesmo estado e mesmas contas de physis-avac.js; antes ficava na aba Caixinha Physis IoT).
   - Automação, Rural, Solar e Geral: listas de circuitos. Cada circuito tem a SETA DE SELEÇÃO do tipo de carga; quando o
     tipo é Ar-condicionado ou Piscina, a potência vem do AVAC (não se digita). Os outros tipos são digitados.
   - As contas de cada quadro são as MESMAS do QF-AVAC (NBR 5410 simplificada): AVAC.calcular com só estes circuitos.
     Nenhuma conta nova: nada a espelhar no servidor.
   - QGBT: soma dos alimentadores de todos os quadros.
   - Multi-split pelo catálogo do servidor (/api/avac/multisplit): só modelos conferidos; leva a condensadora ao QF-AVAC
     com a corrente máxima do fabricante.
   Globais: esc, el, desenhar, ui, calcLer, calcGravar, window.AVAC, window.telaQuadroEletrico. Estado em calcLer("quadros"). */
(function () {
"use strict";
const QUADROS = [["automacao", "Automação e Caixinha Physis IoT"], ["rural", "Rural (bombas, irrigação, motores)"], ["solar", "Solar (saída CA do inversor)"], ["geral", "Geral"]];
const TIPOS = [["ar_condicionado", "Ar-condicionado (vem do AVAC)"], ["piscina", "Piscina (vem do AVAC)"], ["bomba", "Bomba"], ["motor", "Motor"],
  ["iluminacao", "Iluminação"], ["tomadas", "Tomadas"], ["automacao", "Automação (fonte, CLP, gateway)"], ["inversor_solar", "Inversor solar"], ["outro", "Outra carga"]];
const DO_AVAC = { ar_condicionado:1, piscina:1 };
const PAD = { bomba:{ fp:0.85, fs:1.15, ipin:7, curva:"D", fases:"RST" }, motor:{ fp:0.85, fs:1.15, ipin:7, curva:"D", fases:"RST" },
  iluminacao:{ fp:0.92, fases:"R" }, tomadas:{ fp:0.92, fases:"R" }, automacao:{ fp:0.9, fases:"R" }, inversor_solar:{ fp:1, fases:"RST" },
  outro:{ fp:0.92, fases:"R" }, ar_condicionado:{ fp:0.95, fases:"RST" }, piscina:{ fp:0.9, fases:"RST" } };
const N = v => { const n = +String(v == null ? "" : v).replace(",", "."); return isFinite(n) ? n : 0; };
const f = (v, c) => { v = Number(v); return isFinite(v) ? v.toFixed(c).replace(".", ",") : "—"; };
const ler = () => { const o = calcLer("quadros") || {}; o.q = o.q || {}; QUADROS.forEach(([k]) => { o.q[k] = o.q[k] || { circ:[] }; }); o.ms = o.ms || { amb:[], fab:"", sim:1 }; return o; };
const gravar = o => calcGravar("quadros", o);
const avacE = () => { const o = calcLer("avac") || {}; return o.e && typeof o.e === "object" ? o.e : null; };

function doAvac(tipo) {
  const e = avacE(); if (!e || !window.AVAC) return { kw:0, nota:"AVAC ainda não preenchido" };
  const R = window.AVAC.calcular(e);
  if (tipo === "ar_condicionado") return R.status.ac === "ativo" ? { kw:R.ac.kWe, nota:"AVAC: " + f(R.ac.TR, 1) + " TR ÷ COP" } : { kw:0, nota:"AVAC: ar-condicionado " + R.status.ac };
  const c = R.quadro.circ.filter(x => x.id === "piscina" || x.id === "bpisc"); const kw = c.reduce((s, x) => s + x.kw, 0);
  return kw > 0 ? { kw, nota:"AVAC: aquecedor e bombas da piscina" } : { kw:0, nota:"AVAC: piscina " + R.status.piscina };
}

function calcQuadro(lista) {
  const extras = lista.map(c => { const p = Object.assign({}, PAD[c.tipo] || PAD.outro, c);
    const kw = DO_AVAC[c.tipo] ? doAvac(c.tipo).kw : N(c.kw);
    const x = { nome:c.nome || "", kw, qtd:DO_AVAC[c.tipo] ? 1 : (c.qtd == null || c.qtd === "" ? 1 : N(c.qtd)) };
    ["fases", "fp", "fs", "ipin", "curva", "dr", "comp", "iplaca"].forEach(k => { if (p[k] !== undefined && p[k] !== "" && p[k] !== null) x[k] = k === "fases" || k === "curva" || k === "dr" ? p[k] : N(p[k]); });
    return x; });
  const base = avacE(), Q = Object.assign({}, window.AVAC.padrao().quadro, base ? base.quadro : {}, { extras, circ:{}, splits:{} });
  const e = { controle:{ ativo:{ ac:false, vent:false, press:false, solar:false, piscina:false, dutos:false, lista:false, quadro:true } },
    ac:{ amb:[] }, dutos:{ sistemas:[] }, vent:{ outros:[] }, tipologias:{ lista:[] }, quadro:Q };
  const R = window.AVAC.calcular(e);
  return { circ:R.quadro.circ.filter(c => c.extra != null), al:R.quadro.alim };
}
window.QUADROS = { calcQuadro, doAvac, TIPOS, QUADROS };

const sel = (id, k, v, ops, rot) => `<label class="sr-only" for="${id}">${esc(rot)}</label><select id="${id}" data-qd-k="${esc(k)}">${ops.map(([a, b]) => `<option value="${esc(a)}"${a === v ? " selected" : ""}>${esc(b)}</option>`).join("")}</select>`;
const inp = (id, k, v, rot, w, semRot) => (semRot ? "" : `<label class="sr-only" for="${id}">${esc(rot)}</label>`) + `<input id="${id}" type="text" data-qd-k="${esc(k)}" value="${esc(v == null ? "" : String(v))}" style="width:${w || "6em"}"${/nome|fab$/.test(k) ? "" : ' inputmode="decimal"'}>`;

function telaUmQuadro(k, nome, o) {
  const lista = o.q[k].circ, r = lista.length ? calcQuadro(lista) : null;
  const linhas = lista.map((c, i) => { const id = "qd-" + k + "-" + i, x = r ? r.circ[i] : null, av = DO_AVAC[c.tipo] ? doAvac(c.tipo) : null, n = i + 1;
    return `<tr><td>${inp(id + "-n", k + "." + i + ".nome", c.nome, "Nome do circuito " + n, "12em")}</td>
      <td>${sel(id + "-t", k + "." + i + ".tipo", c.tipo || "outro", TIPOS, "Tipo de carga do circuito " + n)}</td>
      <td>${av ? f(av.kw, 2) + ` <span class="t2">${esc(av.nota)}</span>` : inp(id + "-kw", k + "." + i + ".kw", c.kw, "Potência (kW) do circuito " + n)}</td>
      <td>${av ? "1" : inp(id + "-q", k + "." + i + ".qtd", c.qtd, "Quantidade do circuito " + n, "4em")}</td>
      <td>${sel(id + "-f", k + "." + i + ".fases", c.fases || (PAD[c.tipo] || PAD.outro).fases, [["R", "1F (R)"], ["RS", "2F (RS)"], ["RST", "3F"]], "Fases do circuito " + n)}</td>
      <td>${inp(id + "-c", k + "." + i + ".comp", c.comp == null ? 30 : c.comp, "Comprimento (m) do circuito " + n, "4em")}</td>
      <td>${x ? f(x.ib, 1) : "—"}</td><td>${x && x.in ? x.in : "—"}</td><td>${x && x.s ? f(x.s, 1) : "—"}</td><td>${x && x.dv != null ? f(x.dv * 100, 2) : "—"}</td>
      <td>${esc(x ? x.situacao : "")}</td>
      <td><button type="button" id="${id}-del" data-qd-del="${k}:${i}" aria-label="Remover o circuito ${n} de ${esc(nome)}">Remover</button></td></tr>`; }).join("");
  const al = r ? r.al : null;
  return `<section aria-labelledby="h-qd-${k}"><h3 id="h-qd-${k}">${esc(nome)}</h3>
    ${lista.length ? `<div style="overflow-x:auto"><table><caption class="sr-only">Circuitos de ${esc(nome)}</caption><thead><tr><th scope="col">Circuito</th><th scope="col">Tipo de carga</th><th scope="col">kW</th><th scope="col">Qtd</th><th scope="col">Fases</th><th scope="col">m</th><th scope="col">Ib (A)</th><th scope="col">In (A)</th><th scope="col">Seção (mm²)</th><th scope="col">ΔV %</th><th scope="col">Situação</th><th scope="col"><span class="sr-only">Ações</span></th></tr></thead><tbody>${linhas}</tbody></table></div>
    <p class="t2">Alimentador: ${f(al.kw, 2)} kW · Ib ${f(al.ib, 1)} A · In ${al.in || "—"} A · ${al.s ? f(al.s, 1) + " mm²" : "—"} · ${esc(al.situacao)}</p>` : `<p class="t2">Nenhum circuito.</p>`}
    <p><button type="button" id="qd-add-${k}" data-qd-add="${k}">Acrescentar circuito</button></p></section>`;
}

function telaMultisplit(o) {
  const ms = o.ms, res = ui.qdMs;
  const amb = ms.amb.map((a, i) => `<tr><td>${inp("qd-ms-n" + i, "ms." + i + ".nome", a.nome, "Ambiente " + (i + 1), "12em")}</td><td>${inp("qd-ms-b" + i, "ms." + i + ".btuh", a.btuh, "Carga (BTU/h) do ambiente " + (i + 1), "7em")}</td><td><button type="button" id="qd-ms-del${i}" data-qd-del="ms:${i}" aria-label="Remover o ambiente ${i + 1}">Remover</button></td></tr>`).join("");
  let out = "";
  if (res && res.erro) out = `<p role="alert">${esc(res.erro)}</p>`;
  else if (res) { out = (res.aviso ? `<p>${esc(res.aviso)}</p>` : "") + (res.faltam || []).map(x => `<p class="t2">Faltam dados: ${esc(x)}</p>`).join("") + (res.opcoes || []).map((op, j) => `<div class="cartao"><p><strong>${esc(op.fabricante)} ${esc(op.linha)} · ${esc(op.modelo)}</strong> — ${op.cap_btuh} BTU/h, ${op.saidas} saídas, combinação ${f(op.combinacao_pct, 1)} % (faixa ${op.faixa_pct.join("–")} %), sobra ${f(op.sobra_pct, 1)} %${op.a_conferir ? " · <strong>a conferir</strong>" : ""}</p>
      <ul>${op.evaporadoras.map(e => `<li>${esc(e.ambiente)}: ${esc(e.modelo)} (${e.cap_btuh} BTU/h para ${e.carga_btuh})</li>`).join("")}</ul>
      <p class="t2">Elétrica: ${op.eletrica.corrente_max_a != null ? "MCA " + f(op.eletrica.corrente_max_a, 1) + " A" : "MCA não informada"}${op.eletrica.disjuntor_max_a != null ? " · MOP " + op.eletrica.disjuntor_max_a + " A" : ""} · Fonte: ${esc(op.fontes.join("; "))}</p>
      <button type="button" id="qd-ms-levar${j}" data-qd-levar="${j}">Levar ao QF-AVAC</button></div>`).join("")
      + ((res.descartadas || []).length ? `<details><summary>Por que as outras ficaram de fora (${res.descartadas.length})</summary><ul>${res.descartadas.map(d => `<li>${esc(d.fabricante)} ${esc(d.modelo)}: ${esc(d.motivo)}</li>`).join("")}</ul></details>` : ""); }
  return `<section aria-labelledby="h-qd-ms"><h2 id="h-qd-ms">Multi-split pelo catálogo</h2>
    <p class="t2">Só modelos conferidos pela direção (Gestão → Fornecedores → Catálogo técnico). Simultaneidade 1,0 = todos os ambientes no pico ao mesmo tempo.</p>
    ${amb ? `<table><caption class="sr-only">Ambientes da condensadora</caption><thead><tr><th scope="col">Ambiente</th><th scope="col">Carga (BTU/h)</th><th scope="col"><span class="sr-only">Ações</span></th></tr></thead><tbody>${amb}</tbody></table>` : ""}
    <p><button type="button" id="qd-ms-add" data-qd-add="ms">Acrescentar ambiente</button> <button type="button" id="qd-ms-puxar" data-qd-puxar="1">Puxar ambientes do AVAC</button></p>
    <p><label for="qd-ms-fab">Fabricante (vazio = todos)</label> ${inp("qd-ms-fab", "ms.fab", ms.fab, "", "10em", true)}
       <label for="qd-ms-sim">Simultaneidade</label> ${inp("qd-ms-sim", "ms.sim", ms.sim, "", "4em", true)}
       <button type="button" id="qd-ms-ir" data-qd-ms="1">Selecionar</button></p>
    <div role="status" aria-live="polite">${out}</div></section>`;
}

function telaQuadros() {
  const o = ler();
  const rs = QUADROS.map(([k, n]) => [n, o.q[k].circ.length ? calcQuadro(o.q[k].circ).al : null]);
  const e = avacE(); let alA = null; try { if (e) alA = window.AVAC.calcular(e).quadro.alim; } catch (x) { alA = null; }
  const todos = [["QF-AVAC", alA]].concat(rs).filter(x => x[1]);
  const kw = todos.reduce((s, x) => s + x[1].kw, 0), ib = todos.reduce((s, x) => s + x[1].ib, 0);
  const qgbt = `<section aria-labelledby="h-qd-qgbt"><h2 id="h-qd-qgbt">QGBT — resumo de todos os quadros</h2>
    ${todos.length ? `<table><caption class="sr-only">Alimentadores</caption><thead><tr><th scope="col">Quadro</th><th scope="col">kW</th><th scope="col">Ib (A)</th><th scope="col">In (A)</th><th scope="col">Situação</th></tr></thead><tbody>
    ${todos.map(([n, a]) => `<tr><th scope="row">${esc(n)}</th><td>${f(a.kw, 2)}</td><td>${f(a.ib, 1)}</td><td>${a.in || "—"}</td><td>${esc(a.situacao)}</td></tr>`).join("")}
    <tr><th scope="row">Total (soma simples, sem fator de demanda)</th><td>${f(kw, 2)}</td><td>${f(ib, 1)}</td><td>—</td><td></td></tr></tbody></table>` : `<p class="t2">Nenhum quadro com carga ainda.</p>`}</section>`;
  return `<h1>Quadros elétricos</h1>
    <p class="t2 pq">Um quadro por função. Na seta de seleção, Ar-condicionado e Piscina puxam a potência do AVAC; os demais tipos são digitados. Critérios da NBR 5410 em forma simplificada (as mesmas contas do QF-AVAC); não substitui o projeto elétrico.</p>
    ${qgbt}${typeof telaQuadroEletrico === "function" ? telaQuadroEletrico() : ""}
    <section aria-labelledby="h-qd-outros"><h2 id="h-qd-outros">Quadros por módulo</h2>${QUADROS.map(([k, n]) => telaUmQuadro(k, n, o)).join("")}</section>
    ${telaMultisplit(o)}`;
}

function setar(o, k, v) { const p = k.split("."); if (p[0] === "ms") { if (p.length === 2) o.ms[p[1]] = v; else o.ms.amb[+p[1]][p[2]] = v; return; }
  const c = o.q[p[0]].circ[+p[1]]; c[p[2]] = v; if (p[2] === "tipo") c.fases = (PAD[v] || PAD.outro).fases; }
if (typeof document !== "undefined") {
  document.addEventListener("change", ev => { const t = ev.target; if (!t || !t.dataset || t.dataset.qdK == null) return;
    const o = ler(); setar(o, t.dataset.qdK, t.value); gravar(o); desenhar(false); const x = el(t.id); if (x) x.focus(); });
  document.addEventListener("click", async ev => { const b = ev.target.closest ? ev.target.closest("button") : null; if (!b || !b.dataset) return;
    const d = b.dataset; if (d.qdAdd == null && d.qdDel == null && d.qdPuxar == null && d.qdMs == null && d.qdLevar == null) return;
    const o = ler();
    if (d.qdAdd === "ms") o.ms.amb.push({ nome:"Ambiente " + (o.ms.amb.length + 1), btuh:"" });
    else if (d.qdAdd) o.q[d.qdAdd].circ.push({ nome:"Novo circuito", tipo:"outro", kw:"", qtd:1, fases:"R", comp:30 });
    if (d.qdDel) { const [k, i] = d.qdDel.split(":"); if (k === "ms") o.ms.amb.splice(+i, 1); else o.q[k].circ.splice(+i, 1); }
    if (d.qdPuxar) { const e = avacE(); if (e && window.AVAC) { const R = window.AVAC.calcular(e), btuTR = N(e.ac && e.ac.btuTR) || 12000;
      o.ms.amb = R.ac.amb.filter(a => a.matriz && a.tr > 0).slice(0, 16).map(a => ({ nome:a.nome, btuh:Math.round(a.tr * btuTR) })); } }
    if (d.qdMs) { try { const r = await fetch("/api/avac/multisplit", { method:"POST", credentials:"same-origin", headers:{ "Content-Type":"application/json" },
        body:JSON.stringify({ ambientes:o.ms.amb.map(a => ({ nome:a.nome, btuh:N(a.btuh) })), fabricante:o.ms.fab || "", simultaneidade:N(o.ms.sim) || 1 }) });
      ui.qdMs = await r.json(); } catch (x) { ui.qdMs = { erro:"A seleção precisa do servidor da Physis (catálogo no banco)." }; } }
    if (d.qdLevar != null && ui.qdMs && ui.qdMs.opcoes) { const op = ui.qdMs.opcoes[+d.qdLevar], oa = calcLer("avac") || {}, e = oa.e;
      if (e && op) { e.quadro = e.quadro || {}; (e.quadro.extras = e.quadro.extras || []).push({ nome:"Condensadora " + op.fabricante + " " + op.modelo, kw:N(op.eletrica.pot_eletrica_kw), qtd:1,
          iplaca:op.eletrica.corrente_max_a != null ? op.eletrica.corrente_max_a : null, fases:N(op.eletrica.fases) === 3 ? "RST" : "R" });
        calcGravar("avac", oa);
        ui.qdMs.aviso = "Levada ao QF-AVAC. Se ela substitui splits da matriz do AVAC, tire-os de lá para não contar duas vezes."; } }
    gravar(o); desenhar(false); const x = el(b.id); if (x) x.focus(); });
}
window.telaQuadros = telaQuadros;
})();
