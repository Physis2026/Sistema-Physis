#!/usr/bin/env python3
r"""Regressão no NAVEGADOR (26/11/2026): abre as telas num Chromium automático, como uma pessoa, e confere o que os testes de
código não veem. Roda toda noite pelo physis_noite.ps1 (ou à mão):

    cd C:\physis\physis-ma-20261122-1bd599e
    py ferramentas\testes-navegador\regressao_navegador.py --saida C:\physis\noturno\navegador.md

Sem conta e sem mexer em dados: usa as DEMONSTRAÇÕES (demos/*.html, dados fictícios, todas as abas), o laboratório da
InovaSTEM (arquivo) e o M&A local (http://127.0.0.1:8710, só leitura). Em cada aba, em 1280 px e em 360 px (celular):
  erro de script · número de títulos h1 (tem de ser 1) · rolagem lateral · controles sem nome · tela longa sem partes.
Saída: relatório .md e código 1 se houver FALHA (erro de script, mais de um h1, rolagem lateral).
Precisa de: py -m pip install playwright && py -m playwright install chromium
"""
from __future__ import annotations
import argparse, asyncio, json, sys, time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
VER = """()=>{const vis=e=>!!(e.offsetWidth||e.offsetHeight||e.getClientRects().length);const m=document.querySelector('main')||document.body;
 const semNome=[...m.querySelectorAll('input,select,textarea,button')].filter(vis).filter(e=>!(e.labels&&e.labels.length)&&!e.getAttribute('aria-label')&&!e.getAttribute('aria-labelledby')&&!(e.tagName==='BUTTON'&&e.textContent.trim())&&!['hidden','file'].includes(e.type)).length;
 return {h1:[...document.querySelectorAll('h1')].filter(vis).length, larg:document.documentElement.scrollWidth, telas:Math.round(document.documentElement.scrollHeight/innerHeight), semNome}}"""


async def varrer(b, url, abas_js, largura, nome, L, falhas):
    pg = await b.new_page(viewport={"width": largura, "height": 800}); erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)[:160]))
    try:
        await pg.goto(url, wait_until="load", timeout=60000); await pg.wait_for_timeout(1500)
        ids = await pg.evaluate(abas_js) if abas_js else [None]
        for a in ids or [None]:
            erros.clear()
            if a is not None:
                await pg.evaluate("a=>{const b=document.querySelector('[data-aba=\"'+a+'\"],[data-v=\"'+a+'\"]'); if(b) b.click(); else if(window.irPara) irPara(a);}", a)
                await pg.wait_for_timeout(700)
            r = await pg.evaluate(VER)
            ruim = []
            if erros: ruim.append("erro de script: " + erros[0])
            if r["h1"] != 1: ruim.append(f"{r['h1']} títulos h1")
            if r["larg"] > largura + 2: ruim.append(f"rolagem lateral ({r['larg']} px)")
            aviso = []
            if r["semNome"]: aviso.append(f"{r['semNome']} controle(s) sem nome")
            if largura < 500 and r["telas"] > 12: aviso.append(f"tela longa ({r['telas']} telas)")
            rot = f"{nome} · {a or 'página'} · {largura}px"
            if ruim: falhas.append(rot); L.append(f"- [FALHA] {rot}: " + "; ".join(ruim + aviso))
            elif aviso: L.append(f"- [AVISO] {rot}: " + "; ".join(aviso))
    except Exception as e:  # noqa: BLE001
        L.append(f"- [AVISO] {nome} · {largura}px: não abriu ({type(e).__name__}: {str(e)[:120]})")
    finally:
        await pg.close()


async def main(saida: Path, mv: str) -> int:
    from playwright.async_api import async_playwright
    L = [f"# Regressão no navegador · {time.strftime('%d/%m/%Y %H:%M')}", ""]; falhas = []
    alvos = [(p.as_uri(), "[...new Set([...document.querySelectorAll('nav [data-aba]')].map(b=>b.dataset.aba))]", p.stem) for p in sorted((RAIZ / "demos").glob("physis-demo-*.html"))]
    lab = next(iter(sorted(RAIZ.parent.glob("juncao-instituto/physis-hub/web/inovastem-lab.html"))), None)
    if lab: alvos.append((lab.as_uri(), None, "inovastem-laboratorio"))
    alvos.append((mv, "[...document.querySelectorAll('[role=tab][data-v]')].map(b=>b.dataset.v)", "M&A"))
    async with async_playwright() as p:
        b = await p.chromium.launch(**({"executable_path": __import__("os").environ["PHYSIS_CHROMIUM"]} if __import__("os").environ.get("PHYSIS_CHROMIUM") else {}))
        for url, js, nome in alvos:
            for w in (1280, 360):
                await varrer(b, url, js, w, nome, L, falhas)
        await b.close()
    L.insert(2, f"**Resultado: {len(falhas)} falha(s)** em {len(alvos)} telas (cada aba em 1280 e 360 px)." + ("" if falhas else " Nenhuma falha."))
    saida.parent.mkdir(parents=True, exist_ok=True); saida.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:40])); return 1 if falhas else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--saida", default=str(RAIZ.parent / "noturno" / "navegador.md")); ap.add_argument("--mv", default="http://127.0.0.1:8710/")
    a = ap.parse_args()
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("Playwright não instalado: py -m pip install playwright && py -m playwright install chromium"); sys.exit(2)
    sys.exit(asyncio.run(main(Path(a.saida), a.mv)))
