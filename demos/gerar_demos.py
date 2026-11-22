#!/usr/bin/env python3
"""Gera as demonstrações públicas (demos/*.html) a partir dos programas de verdade. Rode depois de mudar um original.

    python demos/gerar_demos.py             # gera
    python demos/gerar_demos.py --conferir  # só confere (testes): sai com erro se alguma demo estiver velha

Por que existe: as demos são o que o site mostra. Copiadas à mão, ficam velhas (era o caso até 15/11/2026).
Aqui cada demo é o arquivo original com poucos ajustes conferidos (se o original mudar e um ajuste não couber
mais, o script para com erro em vez de gerar uma demo quebrada).

Para que servem (decisão de 15/11/2026): as demos PROMOVEM as ferramentas e levam à compra da versão completa
na loja. Cada uma tem:
  - uma faixa no topo: "Demonstração · dados simulados", o benefício numa linha, um resultado na hora
    (R$/mês, próxima rega, alarme) tirado do próprio programa, uma linha "ao vivo" que muda a cada 10 s
    (aria-live polite, com botão Pausar) e o convite "Na versão completa você…";
  - uma faixa fixa no rodapé com "Comprar a versão completa", que leva ao item certo da loja (/loja/?item=<id>).
A plataforma de verdade (painel.html) nunca leva essas faixas: o produto não é rotulado como demonstração.

| Demo                             | Original                                   | Abre em                                  | Compra                |
|----------------------------------|--------------------------------------------|------------------------------------------|-----------------------|
| physis-demo-sustainkit.html      | sistema/SustainKit_Definitivo.html         | Modo Apresentação, "Dados de exemplo"     | /loja/?item=sk-pacote |
| physis-demo-scada.html           | sistema/physis-scada-demo.html             | fazenda simulada, relógio acelerado       | /loja/?item=scada     |
| physis-demo-monitoramento.html   | physis-hub/web/painel.html                 | aba Monitoramento verde, nós V6 simulados | /loja/?item=mon-sw    |
| physis-demo-planejador.html      | modulos/planejador/planejador-physis.html  | Planejador                               | /loja/?item=P13       |
| physis-demo-cliente.html         | physis-hub/web/painel.html                 | plataforma com os módulos vendáveis       | /loja/                |

Endereços no servidor (o servidor precisa servir cada arquivo na sua rota; as ligações entre as demos usam a rota
e, quando a página é aberta como arquivo .html, o nome do arquivo):
  /demo/sustainkit/  /demo/scada/  /demo/monitoramento/  /demo/planejador/  /demo/plataforma/

Animais e saúde (e turbinas, AVAC) não aparecem no site por enquanto: só os módulos vendáveis.
A Gestão interna da Physis (sistema/gestao-interna-physis.html) NÃO vira demo pública: tem dados internos da equipe.
Nomes de pessoas da equipe saem das demos (só nomes fictícios em público).
"""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DEMOS = RAIZ / "demos"
PAINEL = RAIZ / "physis-hub" / "web" / "painel.html"
SCADA = RAIZ / "sistema" / "physis-scada-demo.html"
PLANEJADOR = RAIZ / "modulos" / "planejador" / "planejador-physis.html"
SUSTAINKIT = RAIZ / "sistema" / "SustainKit_Definitivo.html"

# Módulos vendáveis no site (pedido de 15/11/2026): planejamento, solar, água, monitoramento (com a Caixinha IoT),
# SustainKit, SCADA, gestão e certificação. SbN, economia circular, carbono e resiliência entram como partes do
# planejamento/SustainKit. Fora: animais, saúde, turbinas, AVAC.
MODULOS_DEMO = ["planejador", "sustainkit", "solar", "agua", "monitoramento", "zonas", "supervisao", "gestao",
                "certificacoes", "sbn", "circular", "carbono", "resiliencia"]
MARCA = '<meta name="physis-demo-gerado" content="demos/gerar_demos.py">'

# Demos antigas que este script não gera mais (são apagadas ao gerar; o --conferir acusa se ainda existirem).
OBSOLETAS = ["physis-demo-gestao.html"]   # era a plataforma aberta na aba Gestão (sem ligação no site)

# arquivo, rota no servidor, rótulo pt, rótulo en
LIGACOES = [
    ("physis-demo-monitoramento.html", "/demo/monitoramento/", "Monitoramento verde", "Green monitoring"),
    ("physis-demo-sustainkit.html", "/demo/sustainkit/", "SustainKit", "SustainKit"),
    ("physis-demo-scada.html", "/demo/scada/", "SCADA", "SCADA"),
    ("physis-demo-planejador.html", "/demo/planejador/", "Planejador", "Planner"),
    ("physis-demo-cliente.html", "/demo/plataforma/", "Plataforma", "Platform"),
]

SELO = ("Demonstração · dados simulados", "Demo · simulated data")

# Demos por cliente (15/11/2026): a mesma plataforma, com os módulos da ficha de clientes/clientes.json (ficam em dia
# com ela), o lugar de exemplo da demonstração e os nós V6 simulados. arquivo → (org da ficha, dispositivos, rótulo en)
FICHAS = RAIZ / "clientes" / "clientes.json"
DEMOS_CLIENTES = {
    "physis-demo-casa-physis.html": ("casa-physis", "{ campo:6, zonas:1, col:3, com:1 }", "Casa Physis · Net Zero"),
    "physis-demo-santa-clara.html": ("fazenda-santa-clara", "{ campo:6, zonas:0, col:0, com:0 }", "Fazenda Santa Clara"),
    "physis-demo-santa-clara-v2.html": ("fazenda-santa-clara-v2", "{ campo:6, zonas:0, col:0, com:0 }", "Fazenda Santa Clara · version 2"),
    # 20/11/2026: Fazenda MF e a plataforma inicial da Casa Physis (logo própria, da ficha)
    "physis-demo-fazenda-mf.html": ("fazenda-mf", "{ campo:6, zonas:1, col:3, com:1 }", "Fazenda MF"),
    "physis-demo-casa-physis-inicial.html": ("casa-physis-inicial", "{ campo:6, zonas:1, col:3, com:1 }", "Casa Physis"),
}


def ficha(org: str) -> dict:
    return next(f for f in json.loads(FICHAS.read_text(encoding="utf-8"))["clientes"] if f["org"] == org)


def marca_embutida(org: str) -> dict | None:
    """Marca própria da ficha com as logos SVG embutidas (a demo é um arquivo só, sem servidor para /marca/)."""
    m = ficha(org).get("marca")
    if not isinstance(m, dict):
        return None
    r = {k: m[k] for k in ("nome", "logo_texto") if m.get(k)}
    for tom in ("clara", "escura"):
        arq = RAIZ / str(m.get(f"logo_{tom}") or "")
        if arq.suffix.lower() == ".svg" and arq.is_file():
            # sempre com fim de linha LF: o Git grava o SVG em LF, e a demo tem de sair igual em qualquer cópia (Windows ou Linux)
            svg = arq.read_bytes().replace(b"\r\n", b"\n")
            r[f"logo_{tom}"] = "data:image/svg+xml;base64," + base64.b64encode(svg).decode("ascii")
    return {"instalacao": org, "marca": r}

# O que cada demo diz. Números só do próprio programa (dados simulados ou de exemplo); nada de preço nem limite novo.
TEXTOS = {
    "physis-demo-sustainkit.html": {
        "produto": ("Physis SustainKit", "Physis SustainKit"),
        "beneficio": ("Descubra em minutos quanto o seu projeto economiza em energia e água, e em quanto tempo cada medida se paga.",
                      "Find out in minutes how much your project saves on energy and water, and how soon each measure pays back."),
        "convite": ("Na versão completa você salva os projetos, exporta o relatório e usa os dados do seu terreno.",
                    "In the full version you save your projects, export the report and use your own site's data."),
        "compra": "/loja/?item=sk-pacote",
        "extra": None,
    },
    "physis-demo-scada.html": {
        "produto": ("Physis SCADA", "Physis SCADA"),
        "beneficio": ("A fazenda inteira numa tela: energia, água e alarmes no minuto em que acontecem.",
                      "The whole farm on one screen: energy, water and alarms the minute they happen."),
        "convite": ("Na versão completa você liga os seus equipamentos, guarda o histórico e exporta os relatórios.",
                    "In the full version you connect your own equipment, keep the history and export the reports."),
        "compra": "/loja/?item=scada",
        "extra": None,
    },
    "physis-demo-monitoramento.html": {
        "produto": ("Physis · Monitoramento verde", "Physis · Green monitoring"),
        "beneficio": ("Saiba quando regar antes de a planta sentir: a umidade do solo de cada canteiro, ao vivo.",
                      "Know when to water before the plant feels it: soil moisture in every bed, live."),
        "convite": ("Na versão completa você liga os seus sensores, guarda o histórico e exporta os dados.",
                    "In the full version you connect your own sensors, keep the history and export the data."),
        "compra": "/loja/?item=mon-sw",
        "extra": ("/loja/?item=campo", "Com o kit de sensores", "With the sensor kit"),
    },
    "physis-demo-planejador.html": {
        "produto": ("Planejador Physis", "Physis Planner"),
        "beneficio": ("Planeje o terreno inteiro antes da obra: implantação, normas, sol e fases.",
                      "Plan the whole site before building: layout, codes, sun and phases."),
        "convite": ("Na versão completa você salva os projetos e usa os dados do seu terreno.",
                    "In the full version you save your projects and use your own site's data."),
        "compra": "/loja/?item=P13",
        "extra": None,
    },
    "physis-demo-cliente.html": {
        "produto": ("Sistema Physis · Plataforma", "Physis System · Platform"),
        "beneficio": ("Os módulos da Physis numa plataforma só: monitoramento, água, energia, gestão e certificação.",
                      "Physis modules in a single platform: monitoring, water, energy, management and certification."),
        "convite": ("Na versão completa você salva, exporta, usa os seus dados e liga os seus sensores.",
                    "In the full version you save, export, use your own data and connect your own sensors."),
        "compra": "/loja/",
        "extra": None,
    },
}

for _arq, (_org, _q, _en) in DEMOS_CLIENTES.items():
    _f = ficha(_org)
    TEXTOS[_arq] = {"produto": ("Sistema Physis · " + _f["nome"], "Physis System · " + _en),
                    "beneficio": ("A plataforma com os módulos de " + _f["nome"] + ", com dados simulados.",
                                  "The platform with the " + _en + " modules, with simulated data."),
                    "convite": ("Na versão completa você salva, exporta, usa os seus dados e liga os seus sensores.",
                                "In the full version you save, export, use your own data and connect your own sensors."),
                    "compra": "/loja/", "extra": None}

# ── Resultado na hora e linha ao vivo: lidos do próprio programa (as contas não mudam) ─────────────────────────
# Cada provedor devolve resultado(en, F) -> [destaque, resto] e linha(en, F) -> {texto, alerta}; pausar(p) é opcional.

PROVEDOR_SUSTAINKIT = r"""
window.PhysisDemoProvedor = (function(){
  var i = 0;
  function lista(){ try { return medidas().filter(function(m){ return !m.falta && m.eco > 0; }); } catch (e) { return null; } }
  function nome(m, en){ return /^Sistema solar/.test(m.n) ? (en ? "Solar power" : "Energia solar") : /^Água de chuva/.test(m.n) ? (en ? "Rainwater" : "Água de chuva") : m.n; }
  return {
    escuta: true,
    resultado: function(en, F){ var l = lista(); if (!l || !l.length) return null; var eco = 0; l.forEach(function(m){ eco += m.eco; });
      return [F.brl(eco / 12) + (en ? "/month" : "/mês"), en ? " less on the energy and water bills, with the example data (a chalet in Petrópolis). Change the city or the tariff and it recalculates on the spot."
        : " a menos nas contas de luz e água, com os dados de exemplo (um chalé em Petrópolis). Mude a cidade ou a tarifa e a conta refaz na hora."]; },
    linha: function(en, F){ var l = lista(); if (!l || !l.length) return null; var m = l[i++ % l.length], pb = m.r && m.r.simples;
      return { texto: nome(m, en) + ": " + F.brl(m.eco / 12) + (en ? "/month saved · pays back in " : "/mês de economia · paga-se em ") +
        (pb == null ? (en ? "more than its service life" : "mais que a vida útil") : F.num(pb / 12, 1) + (en ? " years" : " anos")) }; }
  };
})();
"""

PROVEDOR_SCADA = r"""
window.PhysisDemoProvedor = (function(){
  var visto = null, TARIFA = 0.95;   /* tarifa de exemplo, a mesma da demo do SustainKit; está escrita na tela */
  function S(){ return window.PhysisScadaDemo && window.PhysisScadaDemo.balanco ? window.PhysisScadaDemo : null; }
  function hh(min){ min = Math.round(min) % 1440; return String(Math.floor(min / 60)).padStart(2, "0") + ":" + String(min % 60).padStart(2, "0"); }
  return {
    resultado: function(en, F){ var s = S(); if (!s) return null; var kwh = s.balanco().autoconsumo;
      return [F.brl(kwh * TARIFA), en ? " less on the power bill in this simulation: " + F.num(kwh, 0) + " kWh of solar used on the farm (example tariff R$ 0.95/kWh)."
        : " a menos na conta de luz nesta simulação: " + F.num(kwh, 0) + " kWh do sol usados na fazenda (tarifa de exemplo R$ 0,95/kWh)."]; },
    linha: function(en, F){ var s = S(); if (!s) return null; var al = s.alarmes(), A = {}; s.ATIVOS.forEach(function(a){ A[a.id] = a; });
      var novo = al[0] && al[0] !== visto ? al[0] : null; visto = al[0] || visto;
      if (novo){ var fx = novo.ativo.fx || s.faixa(novo.g) || [];
        return { alerta: true, texto: (en ? "Alarm at " : "Alarme às ") + hh(novo.min) + ": " + (en ? novo.ativo.en : novo.ativo.pt) + " " +
          (novo.est === "alto" ? (en ? "above" : "acima da") : (en ? "below" : "abaixo da")) + (en ? " the range (" : " faixa (") + F.num(novo.v, 1) + (fx[2] && fx[2] !== "-" ? " " + fx[2] : "") + ")." }; }
      var ativos = s.ATIVOS.filter(function(a){ return a.estado !== "ok"; }).length;
      return { texto: hh(s.minuto()) + (en ? " on the simulated farm · solar " : " na fazenda simulada · sol ") + F.num(A["solar-usina"].ultimo || 0, 0) + " kW · " +
        (en ? "reservoir " : "reservatório ") + F.num(A["reservatorio-01"].ultimo || 0, 0) + " % · " + ativos + (en ? (ativos === 1 ? " alarm on" : " alarms on") : (ativos === 1 ? " alarme ativo" : " alarmes ativos")) + "." }; },
    pausar: function(p){ var s = S(), b = document.getElementById("btPausa"); if (s && b && s.rodando() === p) b.click(); }
  };
})();
"""

PROVEDOR_MONITORAMENTO = r"""
window.PhysisDemoProvedor = (function(){
  var i = 0;
  function nos(){ try { return ui && ui.dados && ui.dados.nos ? ui.dados.nos.filter(function(n){ return n.tipo === "SOLO"; }) : null; } catch (e) { return null; } }
  function dois(n){ return String(n).padStart(2, "0"); }
  function tempo(min, en, F){ return min < 60 ? F.num(min, 0) + " min" : F.num(min / 60, 1) + " h"; }
  return {
    resultado: function(en, F){ var l = nos(); if (!l || !l.length) return null;
      var c = l.filter(function(n){ return n.online && typeof n.p1 === "number" && n.p1 > 0; }).sort(function(a, b){ return a.p1 - b.p1; })[0];
      if (c){ var t = new Date(Date.now() + c.p1 * 60000); t.setMinutes(Math.ceil(t.getMinutes() / 5) * 5, 0, 0);
        var amanha = t.toDateString() !== new Date().toDateString(), h = t.toLocaleTimeString(en ? "en-GB" : "pt-BR", { hour: "2-digit", minute: "2-digit" });
        return [(en ? "Next watering: node " : "Próxima rega: nó ") + dois(c.id) + (amanha ? (en ? " tomorrow at " : " amanhã às ") : (en ? " today at " : " hoje às ")) + h,
          en ? " (it reaches its " + F.num(c.lim1, 0) + " % limit in " + tempo(c.p1, en, F) + ", a forecast learned by the node itself)."
             : " (a umidade chega ao limite de " + F.num(c.lim1, 0) + " % em " + tempo(c.p1, en, F) + ", previsão aprendida no próprio nó)."]; }
      var irr = l.filter(function(n){ return n.ir1; }).length;
      return irr ? [irr + (en ? (irr === 1 ? " bed watering now" : " beds watering now") : (irr === 1 ? " canteiro irrigando agora" : " canteiros irrigando agora")), en ? ": the soil reached its limit and the node switched the valve on." : ": o solo chegou ao limite e o nó abriu a válvula."]
        : [en ? "No watering needed" : "Nenhuma rega necessária", en ? ": every bed is above its limit." : ": todos os canteiros acima do limite."]; },
    linha: function(en, F){ var l = nos(); if (!l || !l.length) return null;
      var off = l.filter(function(n){ return !n.online; }), fraca = l.filter(function(n){ return n.online && n.bat != null && n.bat < 3.5; });
      var seco = l.filter(function(n){ return n.media != null; }).sort(function(a, b){ return a.media - b.media; })[0];
      var op = [function(){ var on = l.length - off.length, irr = l.filter(function(n){ return n.ir1; }).length;
          return { texto: on + (en ? " of " : " de ") + l.length + (en ? " nodes online · " : " nós online · ") + irr + (en ? " watering now." : " irrigando agora.") }; },
        function(){ return seco ? { texto: (en ? "Driest bed: node " : "Canteiro mais seco: nó ") + dois(seco.id) + (en ? " at " : " com ") + F.num(seco.media, 1) + " %" + (en ? " (limit " : " (limite ") + F.num(seco.lim1, 0) + " %)." } : null; }];
      if (off.length) op.push(function(){ return { alerta: true, texto: (en ? "Alert: node " : "Alerta: nó ") + dois(off[0].id) + (en ? " has stopped reporting." : " parou de responder.") }; });
      if (fraca.length) op.push(function(){ return { alerta: true, texto: (en ? "Alert: low battery on node " : "Alerta: bateria fraca no nó ") + dois(fraca[0].id) + " (" + F.num(fraca[0].bat, 2) + " V)." }; });
      return op[i++ % op.length]() || op[0](); },
    pausar: function(p){ var b = document.getElementById("btn-pausa"); if (b && (b.getAttribute("aria-pressed") === "true") !== p) b.click(); }
  };
})();
"""

PROVEDORES = {"physis-demo-sustainkit.html": PROVEDOR_SUSTAINKIT, "physis-demo-scada.html": PROVEDOR_SCADA,
              "physis-demo-monitoramento.html": PROVEDOR_MONITORAMENTO}

ESTILO = """<style id="physis-demo-estilo">
#physis-demo-faixa{padding:10px 16px;background:#F6EAD0;color:#5C3F00;border-bottom:1px solid #B9A97F;font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;box-sizing:border-box;max-width:100%;overflow-wrap:anywhere}
#physis-demo-faixa *{box-sizing:border-box}
#physis-demo-faixa p{margin:4px 0}
#physis-demo-faixa .pdf-topo{display:flex;flex-wrap:wrap;gap:4px 14px;align-items:center}
#physis-demo-faixa .pdf-selo{font-weight:700;letter-spacing:.01em}
#physis-demo-faixa nav{display:flex;flex-wrap:wrap;gap:4px;margin-left:auto}
#physis-demo-faixa nav a{color:#5C3F00;font-weight:600;padding:6px 10px;border-radius:6px;min-height:36px;display:inline-flex;align-items:center}
#physis-demo-faixa nav a[aria-current=page]{background:#5C3F00;color:#FFFFFF;text-decoration:none}
#physis-demo-faixa .pdf-beneficio{font-size:1.08em;font-weight:700;color:#1C2B21}
#physis-demo-faixa .pdf-vivo{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;background:#FFFFFF;border:1px solid #B9A97F;border-radius:10px;padding:8px 12px;margin:6px 0}
#physis-demo-faixa .pdf-textos{flex:1 1 280px;min-width:0}
#physis-demo-faixa .pdf-resultado{color:#1C2B21}
#physis-demo-faixa .pdf-resultado strong{color:#1F4A1C;font-size:1.25em}
#physis-demo-faixa .pdf-linha{color:#4A4F44;font-variant-numeric:tabular-nums;border-radius:6px;padding:2px 6px;margin:2px -6px}
#physis-demo-faixa .pdf-linha.pdf-alerta{color:#7A2214;background:#F5E2D7;font-weight:600}
#physis-demo-faixa button{font:inherit;font-weight:600;min-height:44px;min-width:44px;padding:6px 14px;border-radius:8px;border:1px solid #5C3F00;background:#FFFFFF;color:#5C3F00;cursor:pointer}
#physis-demo-faixa .pdf-convite{color:#5C3F00}
#physis-demo-faixa a:focus-visible,#physis-demo-faixa button:focus-visible,#physis-demo-compra a:focus-visible{outline:3px solid #1C3550;outline-offset:2px}
#physis-demo-compra{position:fixed;left:0;right:0;bottom:0;z-index:2147482000;display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;justify-content:center;padding:8px 16px calc(8px + env(safe-area-inset-bottom));background:#FFFFFF;color:#1C2B21;border-top:2px solid #B9A97F;font:15px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif;box-sizing:border-box}
#physis-demo-compra .pdf-selo{font-weight:700;color:#5C3F00}
#physis-demo-compra a{display:inline-flex;align-items:center;min-height:44px;padding:8px 18px;border-radius:8px;font-weight:700;text-decoration:none}
#physis-demo-compra .pdf-comprar{background:#33512F;color:#FFFFFF}
#physis-demo-compra .pdf-outra{color:#33512F;text-decoration:underline}
#physis-demo-espaco{height:72px}
@media (max-width:480px){#physis-demo-compra{gap:2px 10px}#physis-demo-compra .pdf-selo{font-size:.9em}#physis-demo-compra .pdf-comprar{order:3;flex-basis:100%;justify-content:center}#physis-demo-compra .pdf-outra{padding:8px 6px;font-size:.9em}#physis-demo-espaco{height:120px}}
@media (prefers-reduced-motion:no-preference){html:not(.a11y-calma) #physis-demo-faixa .pdf-linha.pdf-nova{animation:pdf-luz 1.6s ease-out}}
@keyframes pdf-luz{from{background:#ECE0BD}to{background:transparent}}
html[data-tema=escuro] #physis-demo-faixa{background:#33372E;color:#E5D5AE;border-color:#4A5A47}
html[data-tema=escuro] #physis-demo-faixa nav a,html[data-tema=escuro] #physis-demo-faixa .pdf-convite{color:#E5D5AE}
html[data-tema=escuro] #physis-demo-faixa nav a[aria-current=page]{background:#E5D5AE;color:#14180F}
html[data-tema=escuro] #physis-demo-faixa .pdf-beneficio,html[data-tema=escuro] #physis-demo-faixa .pdf-resultado{color:#EEF2EA}
html[data-tema=escuro] #physis-demo-faixa .pdf-vivo{background:#2A3829;border-color:#4A5A47}
html[data-tema=escuro] #physis-demo-faixa .pdf-resultado strong{color:#B9CDB3}
html[data-tema=escuro] #physis-demo-faixa .pdf-linha{color:#D6DBCF}
html[data-tema=escuro] #physis-demo-faixa .pdf-linha.pdf-alerta{color:#FF8A80;background:#2A1215}
html[data-tema=escuro] #physis-demo-faixa button{background:#2A3829;color:#E5D5AE;border-color:#E5D5AE}
html[data-tema=escuro] #physis-demo-compra{background:#2A3829;color:#EEF2EA;border-color:#4A5A47}
html[data-tema=escuro] #physis-demo-compra .pdf-selo{color:#E5D5AE}
html[data-tema=escuro] #physis-demo-compra .pdf-comprar{background:#B9CDB3;color:#14180F}
html[data-tema=escuro] #physis-demo-compra .pdf-outra{color:#B9CDB3}
html[data-tema=escuro] #physis-demo-faixa a:focus-visible,html[data-tema=escuro] #physis-demo-faixa button:focus-visible,html[data-tema=escuro] #physis-demo-compra a:focus-visible{outline-color:#B8D0E0}
@media print{#physis-demo-compra,#physis-demo-espaco{display:none}}
</style>"""

# Idioma (segue o lang da página, que cada programa muda com o próprio dicionário), ligações (rota ou arquivo),
# título da aba e a linha ao vivo (no máximo a cada 10 s, com Pausar; parada de saída com "Menos estímulo").
SCRIPT = r"""<script id="physis-demo-script">
(function(){
  var r = document.documentElement, f = document.getElementById("physis-demo-faixa"), c = document.getElementById("physis-demo-compra");
  var emQuadro = false; try { emQuadro = window.self !== window.top; } catch (e) { emQuadro = true; }
  if (emQuadro) { [f, c, document.getElementById("physis-demo-espaco")].forEach(function (x) { if (x) x.style.display = "none"; }); }
  var TIT = %%TITULOS%%, comoArquivo = location.protocol === "file:" || /\.html$/.test(location.pathname);
  function en(){ return /^en/i.test(r.getAttribute("lang") || ""); }
  var F = {
    num: function(v, d){ return Number(v).toLocaleString(en() ? "en-US" : "pt-BR", { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 }); },
    brl: function(v){ return "R$ " + Math.round(v).toLocaleString(en() ? "en-US" : "pt-BR"); }
  };
  [f, c].forEach(function(raiz){ raiz.querySelectorAll("a[data-arquivo]").forEach(function(a){ if (comoArquivo) a.setAttribute("href", a.getAttribute("data-arquivo")); }); });
  var P = window.PhysisDemoProvedor || null, res = document.getElementById("pdf-resultado"), lin = document.getElementById("pdf-linha"),
      bt = document.getElementById("pdf-pausa"), pausado = false, prontos = false;
  function escrever(no, partes){ no.textContent = ""; var s = document.createElement("strong"); s.textContent = partes[0]; no.appendChild(s); no.appendChild(document.createTextNode(partes[1])); }
  function resultado(){ if (!P || !res) return false; var x = null; try { x = P.resultado(en(), F); } catch (e) { x = null; } if (x) escrever(res, x); return !!x; }
  function linha(nova){ if (!P || !lin) return; var x = null; try { x = P.linha(en(), F); } catch (e) { x = null; } if (!x) return;
    lin.textContent = x.texto; lin.classList.toggle("pdf-alerta", !!x.alerta);
    if (nova){ lin.classList.remove("pdf-nova"); void lin.offsetWidth; lin.classList.add("pdf-nova"); } }
  function rotuloPausa(){ if (!bt) return; var e = en(); bt.textContent = pausado ? (e ? "Resume" : "Continuar") : (e ? "Pause" : "Pausar");
    bt.setAttribute("aria-pressed", String(pausado)); }
  /* com PhysisPreferencias, o título vai pelo dicionário da página; sem ela, a demo segura o título (os programas o reescrevem) */
  function titulo(){ if (window.PhysisPreferencias) return; var q = en() ? TIT[1] : TIT[0]; if (document.title !== q) document.title = q; }
  function idioma(){ var e = en();
    [f, c].forEach(function(raiz){
      raiz.querySelectorAll("[data-pt]").forEach(function(x){ x.textContent = x.getAttribute(e ? "data-en" : "data-pt"); });
      [raiz].concat([].slice.call(raiz.querySelectorAll("[data-pt-rot]"))).forEach(function(x){ if (x.hasAttribute("data-pt-rot")) x.setAttribute("aria-label", x.getAttribute(e ? "data-en-rot" : "data-pt-rot")); });
    });
    titulo(); rotuloPausa(); if (prontos){ resultado(); linha(false); } }
  idioma();
  if (window.MutationObserver){ new MutationObserver(idioma).observe(r, { attributes: true, attributeFilter: ["lang"] });
    var te = document.querySelector("title"); if (te) new MutationObserver(titulo).observe(te, { childList: true, characterData: true, subtree: true }); }
  if (!P) return;
  if (r.classList.contains("a11y-calma")) pausado = true;     /* "Menos estímulo": a linha começa parada */
  rotuloPausa();
  if (bt) bt.addEventListener("click", function(){ pausado = !pausado; rotuloPausa(); if (P.pausar) try { P.pausar(pausado); } catch (e) {} if (!pausado) linha(true); });
  var tentativas = 0;
  (function comecar(){ if (resultado()){ prontos = true; linha(false); return; } if (++tentativas < 40) setTimeout(comecar, 500); })();
  setInterval(function(){ if (!prontos || pausado || document.hidden) return; resultado(); linha(true); }, 10000);
  if (P.escuta){ var t = null; document.addEventListener("input", function(ev){ if (f.contains(ev.target)) return; clearTimeout(t); t = setTimeout(resultado, 400); }, true);
    document.addEventListener("change", function(ev){ if (f.contains(ev.target)) return; clearTimeout(t); t = setTimeout(resultado, 400); }, true); }
})();
</script>"""


def _a(texto: str) -> str:
    return texto.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def _t(tag: str, pt_en: tuple[str, str], extra: str = "") -> str:
    pt, en = pt_en
    return f'<{tag}{extra} data-pt="{_a(pt)}" data-en="{_a(en)}">{_a(pt)}</{tag}>'


def titulo(atual: str) -> list[str]:
    pt, en = TEXTOS[atual]["produto"]
    return [f"{pt} · {SELO[0]}", f"{en} · {SELO[1]}"]


def faixa(atual: str) -> tuple[str, str]:
    """Faixa do topo (não fixa) + faixa de compra fixa no rodapé. Texto em pt e en; segue o lang da página."""
    tx = TEXTOS[atual]
    atual_attr = ' aria-current="page"'
    links = "".join(
        f'<a href="{rota}" data-arquivo="{arq}"{atual_attr if arq == atual else ""} data-pt="{_a(pt)}" data-en="{_a(en)}">{_a(pt)}</a>'
        for arq, rota, pt, en in LIGACOES)
    selo_forte, beneficio = _t("strong", SELO, ' class="pdf-selo"'), _t("p", tx["beneficio"], ' class="pdf-beneficio"')
    convite, selo_rodape = _t("p", tx["convite"], ' class="pdf-convite"'), _t("span", SELO, ' class="pdf-selo"')
    vivo = ""
    if atual in PROVEDORES:
        vivo = ('<div class="pdf-vivo"><div class="pdf-textos"><p class="pdf-resultado" id="pdf-resultado"></p>'
                '<p class="pdf-linha" id="pdf-linha" aria-live="polite"></p></div>'
                '<button type="button" id="pdf-pausa" aria-pressed="false" aria-controls="pdf-linha">Pausar</button></div>')
    topo = (f'<section id="physis-demo-faixa" data-pp-manter translate="no" aria-label="{_a(SELO[0])}" data-pt-rot="{_a(SELO[0])}" data-en-rot="{_a(SELO[1])}">'
            f'<div class="pdf-topo">{selo_forte}'
            f'<nav aria-label="Outras demonstrações" data-pt-rot="Outras demonstrações" data-en-rot="Other demos">{links}</nav></div>'
            f'{beneficio}{vivo}{convite}</section>')
    outra = ""
    if tx["extra"]:
        href, pt, en = tx["extra"]
        outra = f'<a class="pdf-outra" href="{href}" data-pt="{_a(pt)}" data-en="{_a(en)}">{_a(pt)}</a>'
    compra = (f'<div id="physis-demo-espaco" aria-hidden="true"></div>'
              f'<div id="physis-demo-compra" role="region" data-pp-manter translate="no" aria-label="Comprar" data-pt-rot="Comprar" data-en-rot="Buy">'
              f'{selo_rodape}'
              f'<a class="pdf-comprar" href="{tx["compra"]}" data-pt="Comprar a versão completa" data-en="Buy the full version">Comprar a versão completa</a>{outra}</div>')
    titulos = json.dumps(titulo(atual), ensure_ascii=False)
    prov = f'<script id="physis-demo-provedor">{PROVEDORES[atual]}</script>\n' if atual in PROVEDORES else ""
    return topo, compra + "\n" + ESTILO + "\n" + prov + SCRIPT.replace("%%TITULOS%%", titulos)


def troca(texto: str, de: str, para: str, nome: str, n: int = 1) -> str:
    achou = texto.count(de)
    if achou != n:
        raise SystemExit(f"{nome}: o ajuste não cabe mais no original (esperava {n}, achou {achou}): {de[:90]!r}")
    return texto.replace(de, para)


def confere(texto: str, trecho: str, nome: str) -> None:
    """O provedor lê isto do programa: se sumir, para com erro em vez de gerar uma demo sem resultado."""
    if trecho not in texto:
        raise SystemExit(f"{nome}: o original não tem mais {trecho[:90]!r} (o resultado da demo depende disso)")


def marcar(texto: str, nome: str, atual: str, demo_id: str) -> str:
    # <html ...> ganha data-physis-demo (os programas escondem/mostram o que é só da demo por ele)
    m = re.compile(r"<html\b([^>]*)>").search(texto, 0, 400)
    if not m:
        raise SystemExit(f"{nome}: sem <html> no começo")
    if "data-physis-demo" not in m.group(1):
        texto = texto[:m.start()] + f'<html{m.group(1)} data-physis-demo="{demo_id}">' + texto[m.end():]
    # título da aba: "Produto · Demonstração · dados simulados"
    m = re.compile(r"<title>[^<]*</title>").search(texto)
    if not m:
        raise SystemExit(f"{nome}: sem <title>")
    texto = texto[:m.start()] + f'<title>{_a(titulo(atual)[0])}</title>' + texto[m.end():]
    i, h = texto.find("<head>"), texto.find("</head>")
    if i < 0 or h < 0 or i > h:
        raise SystemExit(f"{nome}: sem <head>…</head>")
    texto = texto[:i + 6] + "\n" + MARCA + texto[i + 6:]
    m = re.compile(r"<body[^>]*>").search(texto, texto.find("</head>"))   # o <body> de verdade, depois do </head>
    if not m:
        raise SystemExit(f"{nome}: sem <body>")
    topo, rodape = faixa(atual)
    pos = m.end()
    pular = re.compile(r"\s*<a class=\"[^\"]*px-pular[^\"]*\"[^>]*>[^<]*</a>").match(texto, pos)   # "Ir para o conteúdo" continua primeiro
    if pular:
        pos = pular.end()
    texto = texto[:pos] + "\n" + topo + texto[pos:]
    fim = texto.rfind("</body>")
    if fim < 0:
        raise SystemExit(f"{nome}: sem </body>")
    return texto[:fim] + rodape + "\n" + texto[fim:]


def plataforma(atual: str, aba_inicial: str, modulos: list[str], q: str, demo_id: str, pesquisa: bool = False,
               marca: dict | None = None) -> str:
    t = PAINEL.read_text(encoding="utf-8")
    nome = atual
    # 1. modo demonstração ligado em qualquer endereço (o original só liga em /demo/)
    t = troca(t, "demo: /^\\/demo\\/?$/.test(location.pathname)", "demo: true", nome)
    # 2. sem service worker (a demo é arquivo solto no site)
    t = troca(t, '!location.pathname.startsWith("/demo")', "false", nome)
    # 3. módulos da demo, com dados simulados (nós V6 do campo e Caixinha IoT)
    t = troca(t, 'abrirPlataformaCliente(["monitoramento","agua","zonas","solar"], { campo:6, zonas:1, col:0, com:0 }, false);',
              "abrirPlataformaCliente(" + json.dumps(modulos).replace(" ", "") + ", " + q + ", false);"
              + (" ui.inst.pesquisa = true; aplicarInstancia(ui.inst);" if pesquisa else "")   # pesquisa: todas as abas, as em desenvolvimento com selo
              + (" aplicarMarca(" + json.dumps(marca, ensure_ascii=True) + ");" if marca else ""), nome)   # marca própria (logo da ficha)
    # 4. aba inicial (o endereço #aba continua valendo)
    t = troca(t, 'ui.inst.demo = true; } ui.aba = "resumo"; desenhar(false);',
              'ui.inst.demo = true; } ui.aba = TELAS[location.hash.slice(1)] ? location.hash.slice(1) : "' + aba_inicial + '"; desenhar(false);', nome)
    # 5. a ponte com o servidor não roda na demo (no servidor ela já para em /demo/...; aqui também como arquivo .html)
    t = troca(t, '  if (!/^https?:$/.test(location.protocol)) { P.erro = "sem servidor"; return; }\n  if (/^\\/(demo|',
              '  P.erro = "demonstração"; return;   /* demo pública: nada é lido do servidor */\n  if (/^\\/(demo|', nome)
    # 6. o Planejador abre a demo dele (no servidor, abriria /planejador/)
    t = troca(t, 'const ARQ_LOCAL = { planejador:"planejador.html" };',
              'const ARQ_LOCAL = { planejador: /\\.html$/.test(location.pathname) ? "physis-demo-planejador.html" : "/demo/planejador/" };', nome)
    t = troca(t, '${doServidor ? `src="${rota}"` : ""}',
              '${doServidor ? `src="${rota}"` : id === "planejador" ? `src="${/\\.html$/.test(location.pathname) ? "physis-demo-planejador.html" : "/demo/planejador/"}"` : ""}', nome)
    if atual == "physis-demo-monitoramento.html":
        for trecho in ("ui.dados = hubLocal.painel()", 'id="btn-pausa" aria-pressed="false"', 'n.tipo === "SOLO"', "n.p1", "n.lim1", "n.ir1", "n.online"):
            confere(t, trecho, nome)
    return marcar(t, nome, atual, demo_id)


def scada() -> str:
    t = SCADA.read_text(encoding="utf-8")
    nome = "physis-demo-scada.html"
    # a faixa do programa ligava a programas internos (Tela do cliente, que saiu, e Gestão); na demo, a faixa da demo liga as demos
    t = troca(t, '<a class="px-l" href="physis-scada-demo.html" aria-current="page">SCADA</a>', "", nome)
    # sem nomes da equipe em público
    t = troca(t, "2. Dar ao Eric Oliveira o modelo de dado que ele pediu na reunião de 01/09,", "2. Dar à equipe técnica o modelo de dado pedido na reunião de 01/09,", nome)
    t = troca(t, "arquivo que o Eric Oliveira pediu para montar o protótipo em Docker.", "arquivo pedido para montar o protótipo em Docker.", nome)
    # leitura (sem mudar conta) para o resultado da demo: energia do sol usada, relógio da fazenda, pausa
    t = troca(t, "  parar:function(){ rodando = false; }\n};",
              "  parar:function(){ rodando = false; },\n  balanco:function(){ return balanco; }, minuto:function(){ return minutoPlanta; },\n"
              "  rodando:function(){ return rodando; }, faixa:function(g){ return FAIXAS[g]; }\n};", nome)
    # a demo pública não lê nada do servidor (a ponte Hub -> supervisão traria medições reais de quem estiver logado)
    t = troca(t, "  if(!/^https?:$/.test(location.protocol)) return;\n  var org = null, faixa",
              "  return;   /* demo pública: só a planta simulada, nada é lido do servidor */\n  var org = null, faixa", nome)
    # a fazenda simulada começa com o sol já alto (no original, às 05:00): o resultado aparece logo ao abrir
    t = troca(t, "var minutoPlanta = 5*60;   // começa às 05:00", "var minutoPlanta = 9*60;   // demo: começa às 09:00", nome)
    # o título da aba diz que é demonstração, nas duas línguas (o programa reescreve o título ao trocar de língua)
    t = troca(t, 'document.title = "Physis · " + d.titulo;',
              'document.title = EN ? ' + json.dumps(titulo(nome)[1], ensure_ascii=False) + " : " + json.dumps(titulo(nome)[0], ensure_ascii=False) + ";", nome)
    confere(t, 'id="btPausa"', nome)
    return marcar(t, nome, nome, "scada")


def planejador() -> str:
    t = PLANEJADOR.read_text(encoding="utf-8")
    nome = "physis-demo-planejador.html"
    pt, en = titulo(nome)
    t = troca(t, 'var T = {\n    "Planejador Physis": "Physis Planner",', 'var T = {\n    ' + json.dumps(pt, ensure_ascii=False) + ": " + json.dumps(en, ensure_ascii=False) +
              ', "Planejador Physis": "Physis Planner",', nome)   # o título da aba, no dicionário da página
    return marcar(t, nome, nome, "planejador")


def sustainkit() -> str:
    """O SustainKit da demo abre no Modo Apresentação, com dados de exemplo marcados (o modo só existe na demo)."""
    t = SUSTAINKIT.read_text(encoding="utf-8")
    nome = "physis-demo-sustainkit.html"
    troca(t, "function iniciarDemo(){", "function iniciarDemo(){", nome)        # confere que o original ainda tem a demo
    for trecho in ("function medidas(){", "falta:falta(", "eco:", "m.r=SK.analiseInvest(", "'Sistema solar FV (", "'Água de chuva (cisterna)'"):
        confere(t, trecho, nome)
    pt, en = titulo(nome)
    t = troca(t, '    dicionario: {\n      "Physis SustainKit": "Physis SustainKit",', '    dicionario: {\n      ' + json.dumps(pt, ensure_ascii=False) + ": " +
              json.dumps(en, ensure_ascii=False) + ',\n      "Physis SustainKit": "Physis SustainKit",', nome)   # o título da aba, no dicionário da página
    return marcar(t, nome, nome, "sustainkit")


def gerar() -> dict[str, str]:
    return {
        "physis-demo-sustainkit.html": sustainkit(),
        "physis-demo-scada.html": scada(),
        "physis-demo-monitoramento.html": plataforma("physis-demo-monitoramento.html", "campo", ["monitoramento"],
                                                     "{ campo:6, zonas:0, col:0, com:0 }", "monitoramento"),
        "physis-demo-cliente.html": plataforma("physis-demo-cliente.html", "resumo", MODULOS_DEMO,
                                               "{ campo:6, zonas:1, col:0, com:0 }", "plataforma"),
        "physis-demo-planejador.html": planejador(),
        **{arq: plataforma(arq, "resumo", ficha(org)["modulos"], q, org, bool(ficha(org).get("pesquisa")), marca_embutida(org))
           for arq, (org, q, _en) in DEMOS_CLIENTES.items()},
    }


def main() -> int:
    conferir = "--conferir" in sys.argv
    velhas = []
    for nome, novo in gerar().items():
        arq = DEMOS / nome
        antes = arq.read_text(encoding="utf-8") if arq.exists() else None
        if antes != novo:
            velhas.append(nome)
            if not conferir:
                arq.write_bytes(novo.encode("utf-8"))
    for nome in OBSOLETAS:
        arq = DEMOS / nome
        if arq.exists():
            velhas.append(nome + " (obsoleta)")
            if not conferir:
                arq.unlink()
    for v in velhas:
        print(("velha: " if conferir else "gerada: ") + v)
    if not velhas:
        print("demos iguais aos originais")
    return 1 if (conferir and velhas) else 0


if __name__ == "__main__":
    raise SystemExit(main())
