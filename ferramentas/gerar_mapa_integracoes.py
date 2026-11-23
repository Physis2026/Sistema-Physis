#!/usr/bin/env python3
"""Gera o mapa de integrações avulso (um HTML, sem internet) com o MESMO desenho da aba Monitoramento do M&A.

    python ferramentas/gerar_mapa_integracoes.py [saida.html] [--banco physis-mv.db]

O desenho vem do bloco /*MAPA-INICIO*/…/*MAPA-FIM*/ de physis-hub/web/mv.html; os dados, de physis_hub/mv_integracoes.py;
o three.js, de vendor/. Com --banco, os anéis mostram o estado dos bots nesse banco; sem ele, só as ligações.
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "physis-hub"))
from physis_hub import mv_integracoes  # noqa: E402
from physis_hub.mv import MV  # noqa: E402


def gerar(saida: Path, banco: str | None = None) -> Path:
    mv_html = (RAIZ / "physis-hub" / "web" / "mv.html").read_text(encoding="utf-8")
    i, j = mv_html.index("/*MAPA-INICIO*/"), mv_html.index("/*MAPA-FIM*/")
    desenho = mv_html[i:j + len("/*MAPA-FIM*/")]
    k = mv_html.index(".mon3d{")
    css = mv_html[k:mv_html.index(".mon-tab{", k)]
    dados = mv_integracoes.estado(MV(banco) if banco else MV(":memory:"))
    if not banco:
        dados["estado"] = {}
    three = (RAIZ / "vendor" / "three.min.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
    pagina = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mapa de integrações · Sistema Physis</title><style>
:root{{--fundo:#F4F1EA;--sup:#FFFFFF;--texto:#1B1F23;--linha:#D9D3C2;--semente:#F97316;--verde:#33512F}}
html[data-tema="escuro"]{{--fundo:#1B1F23;--sup:#23282D;--texto:#F4F1EA;--linha:#4A4F44;--verde:#DCEBD8}}
body{{margin:0;padding:12px 18px;font:15px/1.4 Lora,Georgia,serif;background:var(--fundo);color:var(--texto)}}
h1{{font-family:Fraunces,Georgia,serif;color:var(--verde);font-size:1.5rem;margin:0 0 8px}}
button{{min-height:44px;padding:0 14px;border-radius:8px;border:1px solid var(--linha);background:var(--sup);color:var(--texto);font:inherit;cursor:pointer}}
table{{border-collapse:collapse;width:100%;font-size:.85rem}}td,th{{border-bottom:1px solid var(--linha);padding:4px 6px;text-align:left}}
{css}</style></head><body>
<h1>🌳 Mapa de integrações · Sistema Physis</h1>
<p>Cada engrenagem é um sistema; as bolinhas andam no sentido da informação. Clique num sistema para ver as ligações. Tracejado = opcional.</p>
<p><button id="monGirar" type="button" aria-pressed="true">Pausar giro</button> <button id="tema" type="button">Tema escuro</button></p>
<div id="mon3d" class="mon3d" role="img" aria-label="Mapa 3D das integrações; a mesma informação está na tabela abaixo"></div>
<ul id="monLegenda" class="mon-leg"></ul>
<details><summary>Tabela das integrações</summary><div id="monTabela"></div></details>
<script>{three}</script>
<script>
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}})[c]);const tx=s=>s;
{desenho}
const D={json.dumps(dados, ensure_ascii=False)};
const M=desenharMapa(document.getElementById("mon3d"),D,THREE,{{dist:92}});
document.getElementById("monLegenda").innerHTML=legendaMapa(D);document.getElementById("monTabela").innerHTML=tabelaMapa(D);
const b=document.getElementById("monGirar");b.onclick=()=>{{const g=M.alternar();b.textContent=g?"Pausar giro":"Girar";b.setAttribute("aria-pressed",String(g))}};
const t=document.getElementById("tema"),h=document.documentElement;t.onclick=()=>{{h.dataset.tema=h.dataset.tema==="escuro"?"":"escuro";t.textContent=h.dataset.tema?"Tema claro":"Tema escuro"}};
</script></body></html>"""
    saida.write_text(pagina, encoding="utf-8")
    return saida


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    banco = sys.argv[sys.argv.index("--banco") + 1] if "--banco" in sys.argv else None
    if banco in args:
        args.remove(banco)
    print(gerar(Path(args[0] if args else "mapa-integracoes.html"), banco))
