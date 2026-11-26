#!/usr/bin/env python3
"""Mapa de fluxo de informação MEDIDO no navegador (26/11/2026): abre cada aba da plataforma (8799), da Gestão (8798) e do
M&A (8797) e registra o que a aba lê, grava e pede ao servidor. Saída: /tmp/fluxos.json (compare com a versão anterior).
Precisa de Playwright + Chromium (opcional; só para auditoria). Suba antes as três instalações de teste nessas portas.
"""

import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright
SPY = """(()=>{window.__f={le:new Set(),grava:new Set(),api:new Set()};
 const gi=Storage.prototype.getItem, si=Storage.prototype.setItem;
 Storage.prototype.getItem=function(k){try{__f.le.add('ls:'+k)}catch(e){} return gi.call(this,k)};
 Storage.prototype.setItem=function(k,v){try{__f.grava.add('ls:'+k)}catch(e){} return si.call(this,k,v)};
 const of=window.fetch; window.fetch=function(u,o){try{const s=String(u&&u.url||u).replace(location.origin,'').split('?')[0].replace(/\\/[0-9a-f-]{6,}/g,'/:id');__f.api.add(((o&&o.method)||'GET')+' '+s)}catch(e){} return of.apply(this,arguments)};
 const t=setInterval(()=>{ if(window.calcLer&&!window.calcLer.__s){const cl=window.calcLer, cg=window.calcGravar; window.calcLer=function(k){__f.le.add('calc:'+k);return cl.apply(this,arguments)}; window.calcLer.__s=1; if(cg) window.calcGravar=function(k){__f.grava.add('calc:'+k);return cg.apply(this,arguments)}; clearInterval(t)}},20);})()"""
async def varrer(pg, js):
    n=await pg.evaluate(f"()=>({js}).length"); out=[]
    for i in range(n):
        await pg.evaluate("()=>{__f.le.clear();__f.grava.clear();__f.api.clear()}")
        rot=await pg.evaluate(f"i=>{{const b=({js})[i]; const t=b.textContent.trim().replace(/\\s*Em desenvolvimento\\s*/,'').replace(/\\s+/g,' ').slice(0,40); b.click(); return t}}",i)
        await pg.wait_for_timeout(1500)
        d=await pg.evaluate("()=>({le:[...__f.le].sort(),grava:[...__f.grava].sort(),api:[...__f.api].sort()})"); d['aba']=rot; out.append(d)
    return out
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(); R={}
    c=await b.new_context(viewport={"width":1280,"height":900}, storage_state="/tmp/estado.json" if Path("/tmp/estado.json").exists() else None); await c.add_init_script(SPY); pg=await c.new_page()
    await pg.goto("http://127.0.0.1:8799/",wait_until="networkidle"); await pg.wait_for_timeout(1200)
    R['casa']=await varrer(pg,"[...new Map([...document.querySelectorAll('nav [data-aba]')].map(b=>[b.dataset.aba,b])).values()]")
    c2=await b.new_context(viewport={"width":1280,"height":900}); await c2.add_init_script(SPY); pg=await c2.new_page()
    await pg.goto("http://127.0.0.1:8798/",wait_until="networkidle")
    await pg.evaluate("""async()=>{const j=await (await fetch('/api/instancia')).json(); await fetch('/api/conta/entrar',{method:'POST',headers:{'Content-Type':'application/json','X-Physis-CSRF':j.csrf||''},body:JSON.stringify({usuario:'teste@physisengineering.com',senha:'senha-bem-longa-123'})})}""")
    await pg.goto("http://127.0.0.1:8798/gestao/",wait_until="networkidle"); await pg.wait_for_timeout(1500)
    R['gestao']=await varrer(pg,"[...document.querySelectorAll('nav button')].filter(b=>!b.dataset.ppAcao && b.textContent.trim() && !/^(EN|PT|Sair)$/.test(b.textContent.trim()) && !b.closest('#pxp-barra,.pp-barra'))")
    await pg.goto("http://127.0.0.1:8797/",wait_until="networkidle"); await pg.wait_for_timeout(1500)
    R['mv']=await varrer(pg,"[...document.querySelectorAll('[role=tab][data-v]')]")
    json.dump(R,open('/tmp/fluxos.json','w'),ensure_ascii=False,indent=1)
    for k,v in R.items(): print(k,len(v), sum(len(x['api']) for x in v), sum(len(x['le'])+len(x['grava']) for x in v))
    await b.close()
asyncio.run(main())
