import json, sys
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]          # pasta do sistema, onde quer que esteja
JS = str(RAIZ / "sistema" / "physis-avac.js")
CASOS = str(RAIZ / "sistema" / "physis-avac-casos.json")
OUT = sys.argv[1]
casos = open(CASOS, encoding="utf-8").read()
json.loads(casos)
html = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Teste AVAC</title>
<script>
/* stubs dos globais da plataforma (mesmas definições do painel.html) */
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));
const numBr = v => { const s = String(v == null ? "" : v).trim(); if (!s) return null; const n = Number(s.replace(/\./g, "").replace(",", ".")); return isNaN(n) ? (isNaN(Number(s)) ? null : Number(s)) : n; };
const n2 = (v, c) => Number(v).toLocaleString("pt-BR", { minimumFractionDigits: c, maximumFractionDigits: c });
const brl = v => "R$ " + Number(v).toLocaleString("pt-BR");
const el = id => document.getElementById(id);
const ui = {}; const MEM = {};
const calcLer = k => MEM[k] ? JSON.parse(JSON.stringify(MEM[k])) : {};
const calcGravar = (k, v) => { MEM[k] = JSON.parse(JSON.stringify(v)); };
function desenhar(){ const t = el("tela"); if (t) t.innerHTML = telaAvac() + telaQuadroEletrico(); }
</script>
<script src="__URL_AVAC__"></script>
</head><body><h2>Teste de window.AVAC.calcular</h2><pre id="saida">rodando…</pre><div id="tela" hidden></div>
<script>
const CASOS = __CASOS__;
const linhas = []; let ok = 0, falha = 0;
function pega(o, p){ return p.split(".").reduce((a, k) => a == null ? undefined : a[k], o); }
try {
  CASOS.casos.forEach(c => { const r = window.AVAC.calcular(c.entradas), tol = c.tolerancia || { rel:1e-9, abs:1e-9 }; let fc = 0;
    Object.keys(c.esperado).forEach(p => { const esp = c.esperado[p], v = pega(r, p);
      const bom = typeof esp === "number" ? (typeof v === "number" && Math.abs(v - esp) <= tol.abs + tol.rel * Math.abs(esp)) : v === esp;
      if (bom) ok++; else { falha++; fc++; linhas.push("  FALHA " + p + ": esperado " + JSON.stringify(esp) + ", calculado " + JSON.stringify(v)); } });
    linhas.unshift((fc ? "FALHOU " : "PASSOU ") + c.nome + " (" + Object.keys(c.esperado).length + " valores, " + fc + " falhas)"); });
  /* desenho de todas as subabas e do quadro (não pode lançar erro) */
  ["visao","tip","carga","ac","vent","press","solar","piscina","dutos","resumo","memoria"].forEach(s => { ui.avacSub = s; const h = telaAvac();
    if ((h.match(/<h1/g) || []).length !== 1) { falha++; linhas.push("FALHA desenho " + s + ": h1"); } else ok++; });
  const q = telaQuadroEletrico(); if (/<h1/.test(q) || !/<h2/.test(q)) { falha++; linhas.push("FALHA quadro: cabeçalhos"); } else ok++;
  /* migração da tela antiga */
  MEM.avac = { amb:[{ n:"Sala", area:"30", uso:"residencial" }] }; ui.avacSub = "ac"; const hm = telaAvac();
  if (!/Unidade \(migrada/.test(telaAvac.toString()) && hm.indexOf("24.000") < 0) { falha++; linhas.push("FALHA migração"); } else ok++;
  /* carga térmica levada ao ar-condicionado (botão da subaba Carga térmica) e desfazer */
  { const e0 = window.AVAC.padrao(); e0.ac.amb = [{ n:"Sala", area:20, dorm:0, override:12000, equip:"Split hi-wall", matriz:true, q:[], comum:1 }];
    const R0 = window.AVAC.calcular(e0), antes = R0.ac.amb[0].btu, cg = [{ nome:"Sala", btuh:15000, area:20 }, { nome:"Quarto novo", btuh:7000, area:9 }];
    const plano = window.AVAC.planoCargas(e0, R0, cg);
    if (plano[0].manual && plano[0].antes === 12000 && plano[1].novo) ok++; else { falha++; linhas.push("FALHA plano da carga térmica: " + JSON.stringify(plano)); }
    const R1 = window.AVAC.calcular(window.AVAC.aplicarCargas(e0, cg)), s = R1.ac.amb.find(a => a.nome === "Sala");
    if (s.btuCalc >= 15000 && s.btu === s.btuCalc && s.fonte === "Carga térmica (NBR 16401-1)" && R1.ac.amb.some(a => a.nome === "Quarto novo")) ok++; else { falha++; linhas.push("FALHA carga térmica levada: " + JSON.stringify(s)); }
    const R2 = window.AVAC.calcular(e0); /* desfazer = voltar o estado anterior */
    if (R2.ac.amb[0].btu === antes && R2.ac.amb[0].fonte === "triagem por m²/TR" && R2.ac.amb.length === 1) ok++; else { falha++; linhas.push("FALHA desfazer"); } }
  /* inputs sem rótulo */
  delete MEM.avac; const doc = new DOMParser().parseFromString("<div>" + ["visao","tip","ac","vent","press","solar","piscina","dutos"].map(s => { ui.avacSub = s; return telaAvac(); }).join("") + telaQuadroEletrico() + "</div>", "text/html");
  const sem = [...doc.querySelectorAll("input,select")].filter(i => !doc.querySelector('label[for="' + i.id + '"]'));
  const ids = [...doc.querySelectorAll("[id]")].map(x => x.id), dup = ids.filter((x, i) => ids.indexOf(x) !== i);
  if (sem.length) { falha++; linhas.push("FALHA " + sem.length + " campos sem label: " + sem.slice(0, 5).map(i => i.id).join(", ")); } else ok++;
  linhas.push("ids repetidos entre subabas (esperado: só os comuns): " + [...new Set(dup)].slice(0, 8).join(", "));
} catch (err) { falha++; linhas.push("ERRO " + err.message + "\n" + err.stack); }
linhas.push("\nTOTAL: " + ok + " ok, " + falha + " falhas");
document.getElementById("saida").textContent = linhas.join("\n");
document.title = falha ? "FALHOU" : "PASSOU";
</script></body></html>"""
open(OUT, "w", encoding="utf-8").write(html.replace("__CASOS__", casos).replace("__URL_AVAC__", Path(JS).as_uri()))
print("ok", OUT)
