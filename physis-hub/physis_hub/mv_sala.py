"""Sala visual dos bots (HTML único, sem internet), gerada do banco do M&A a cada rodada (bot "sala").
Também roda sozinho: python -m physis_hub.mv_sala [physis-mv.db] [saida.html]
"""
import html, json, sqlite3, sys, time
from datetime import datetime
from pathlib import Path


def gerar(db, OUT, DB="physis-mv.db"):
    d = db
    LIM = {"atrasos": 2, "documentos": 2, "resumo": 26, "backup": 26, "paginas": 26, "inovacao": 26, "links": 26,
           "vigia": 2, "sentinela": 2, "dados_iot": 2,
           "editais": 26, "simulacao": 26, "gestoes": 26, "bancos": 26, "acervo": 26, "ia": 26, "cursos": 26, "auditoria": 26, "financeiro": 26, "vencimentos": 26, "fatos": 26, "kit": 26, "repositorios": 26, "desenvolvimento": 26, "sincronizacao": 26, "melhoria": 26, "mercado": 24 * 400, "semanal": 174}
    FUNCAO = {"atrasos": "Prazos e caminho crítico", "documentos": "Validade e regras dos documentos",
              "resumo": "Resumo diário 7h", "backup": "Cópia do banco", "paginas": "Checklist das telas",
              "inovacao": "Pesquisa de inovações", "links": "Links externos", "vigia": "Vigia dos bots",
              "sentinela": "Serviços e contêineres", "dados_iot": "Sensores de campo",
              "editais": "Editais (Instituto)", "simulacao": "Gêmeo Virtual", "gestoes": "Exportações das Gestões",
              "bancos": "Bancos, HTTPS e segredos", "acervo": "Acervo → trilhas InovaSTEM", "ia": "Índice da IA Physis", "cursos": "Mapa de potenciais cursos", "modelos": "Modelos dos fabricantes (catálogos)", "auditoria": "Auditoria, perguntas e intervenção", "financeiro": "Assessor contábil e financeiro", "vencimentos": "Vencimentos (jurídico, fiscal, contratos)", "fatos": "Base de fatos", "repositorios": "Repositórios (marketing-physis…)", "desenvolvimento": "Painel Desenvolvimento dos módulos", "sincronizacao": "Sincronização dos módulos compartilhados", "kit": "Kit de documentos 26/11", "melhoria": "Melhoria contínua dos bots", "mercado": "Mercado e parcerias (sob demanda)", "semanal": "Revisão semanal completa"}
    ICONE = {"atrasos": "⏰", "documentos": "📄", "resumo": "📰", "backup": "💾", "paginas": "💻", "inovacao": "💡",
             "links": "🔗", "vigia": "🔭", "sentinela": "🚨", "dados_iot": "📡", "editais": "📑", "simulacao": "⚙️",
             "gestoes": "📥", "bancos": "🗄️", "acervo": "🎓", "ia": "🧠", "cursos": "🗺️", "modelos": "🏷️", "auditoria": "🧭", "financeiro": "💰", "vencimentos": "⏳", "fatos": "📚", "repositorios": "🗂️", "desenvolvimento": "🛠️", "sincronizacao": "🔄", "kit": "📦", "melhoria": "📈", "mercado": "🌍", "semanal": "🔁"}
    SALAS = [("Gestão e prazos", ["atrasos", "resumo", "documentos", "gestoes"]),
             ("Instituto, InovaSTEM e cursos", ["editais", "acervo", "cursos", "inovacao"]),
             ("IA Physis", ["ia"]),
             ("Modelagem e campo", ["simulacao", "dados_iot"]),
             ("Plataforma e conteúdo", ["paginas", "links"]),
             ("Assessoria e documentos", ["financeiro", "vencimentos", "fatos", "kit", "repositorios"]),
             ("Mercado e parcerias", ["mercado"]),
             ("Infraestrutura", ["backup", "bancos", "vigia", "sentinela", "auditoria", "melhoria", "semanal", "desenvolvimento", "sincronizacao"])]

    agora = time.time()
    cards = {}
    for b in LIM:
        ult = d.execute("SELECT inicio, fim, resumo, erro FROM mv_execucao WHERE bot=? ORDER BY fim DESC, id DESC LIMIT 1", (b,)).fetchone()
        al = d.execute("SELECT gravidade, texto FROM mv_alerta WHERE bot=? AND resolvido IS NULL ORDER BY "
                       "CASE gravidade WHEN 'alerta' THEN 0 WHEN 'atencao' THEN 1 ELSE 2 END", (b,)).fetchall()
        if not ult and b == "mercado":
            est, txt = "ok", "sob demanda: ainda não pedido (/mercado cidade área)"
        elif not ult:
            est, txt = "parado", "nunca rodou"
        elif ult[3]:
            est, txt = "erro", ult[3][:120]
        elif (agora - ult[1]) / 3600 > LIM[b]:
            est, txt = "parado", f"sem rodar há {(agora - ult[1]) / 3600:.1f} h"
        elif any(g == "alerta" for g, _ in al):
            est, txt = "alerta", f"{len(al)} alerta(s) abertos"
        elif any(g == "atencao" for g, _ in al):
            est, txt = "atencao", f"{sum(1 for g, _ in al if g == 'atencao')} ponto(s) de atenção"
        elif al:
            est, txt = "ok", f"{len(al)} configuração(ões) pendente(s)"
        else:
            est, txt = "ok", "tudo certo"
        quando = datetime.fromtimestamp(ult[1]).strftime("%d/%m %H:%M") if ult else "—"
        dur = f"{ult[1] - ult[0]:.2f} s" if ult else "—"
        res = ""
        if ult and ult[2]:
            try:
                j = json.loads(ult[2])
                res = ", ".join(f"{k}: {v}" for k, v in j.items() if not isinstance(v, (dict, list)))[:160]
            except ValueError:
                res = ult[2][:160]
        cards[b] = dict(est=est, txt=txt, quando=quando, dur=dur, res=res, al=al[:4], n=len(al))

    ROT = {"ok": "Trabalhando", "atencao": "Atenção", "alerta": "Com alertas", "erro": "Erro", "parado": "Parado"}
    def card(b):
        c = cards[b]
        li = "".join(f'<li class="g-{g}">{html.escape(t[:110])}</li>' for g, t in c["al"])
        mais = f'<li class="mais">+ {c["n"] - 4} outros</li>' if c["n"] > 4 else ""
        return f'''<article class="mesa e-{c["est"]}" tabindex="0" aria-label="Bot {b}: {ROT[c["est"]]}">
     <div class="monitor"><span class="ic" aria-hidden="true">{ICONE[b]}</span><span class="luz" aria-hidden="true"></span></div>
     <h3>{b}</h3><p class="fn">{FUNCAO[b]}</p>
     <p class="st"><strong>{ROT[c["est"]]}</strong> · {html.escape(c["txt"])}</p>
     <p class="meta">Última: {c["quando"]} · {c["dur"]}</p>
     {f'<p class="res">{html.escape(c["res"])}</p>' if c["res"] else ""}
     {f'<ul>{li}{mais}</ul>' if li else ""}
    </article>'''

    cont = {k: sum(1 for c in cards.values() if c["est"] == k) for k in ROT}
    salas = "".join(f'<section class="sala"><h2>{n}</h2><div class="mesas">{"".join(card(b) for b in bs)}</div></section>' for n, bs in SALAS)
    fr = d.execute("SELECT f.nome, COUNT(t.id), SUM(t.estado='feita') FROM mv_frente f LEFT JOIN mv_tarefa t ON t.frente=f.id GROUP BY f.id").fetchall()
    # InovaSTEM separada: plataforma própria que atende várias frentes (dona, 22/11/2026)
    fd = {n: (t, int(f or 0)) for n, t, f in fr}
    frentes = "".join(f"<li><b>{html.escape(n)}</b> {f}/{t} feitas</li>" for n, (t, f) in fd.items())

    page = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Sala dos bots · Physis M&amp;A</title><style>
    :root{{--fundo:#F4F1EA;--piso:#EFE8D6;--texto:#1B1F23;--verde:#33512F;--mesa:#FFFFFF;--borda:#C9D2C4}}
    html[data-tema=escuro]{{--fundo:#1B1F23;--piso:#1C2B21;--texto:#F4F1EA;--verde:#DCEBD8;--mesa:#23282D;--borda:#4A4F44}}
    *{{box-sizing:border-box}}body{{margin:0;font:15px/1.4 system-ui,sans-serif;background:var(--fundo);color:var(--texto)}}
    header{{display:flex;flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;padding:16px 20px}}
    h1{{font-family:Fraunces,Georgia,serif;color:var(--verde);margin:0;font-size:1.6rem}}
    .placar{{display:flex;gap:8px;flex-wrap:wrap}}.placar span::first-letter{{color:var(--c)}}.placar span{{padding:4px 10px;border-radius:99px;background:var(--mesa);border:1px solid var(--borda)}}
    button{{min-height:44px;padding:0 14px;border-radius:8px;border:1px solid var(--borda);background:var(--mesa);color:var(--texto);cursor:pointer}}
    button:focus-visible,.mesa:focus-visible{{outline:3px solid var(--verde);outline-offset:2px}}
    main{{padding:0 20px 20px;display:grid;gap:18px}}
    .sala{{background:var(--piso);border:2px solid var(--borda);border-radius:14px;padding:14px;
     background-image:linear-gradient(var(--borda) 1px,transparent 1px),linear-gradient(90deg,var(--borda) 1px,transparent 1px);background-size:40px 40px;background-blend-mode:soft-light}}
    .sala h2{{margin:0 0 10px;font-size:1.05rem;color:var(--verde)}}
    .mesas{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}}
    .mesa{{background:var(--mesa);border:1px solid var(--borda);border-left:8px solid var(--c);border-radius:10px;padding:12px;box-shadow:0 3px 0 var(--borda)}}
    .monitor{{position:relative;width:64px;height:44px;border-radius:6px;background:#1B1F23;display:grid;place-items:center;font-size:22px;margin-bottom:6px}}
    .luz{{position:absolute;right:-6px;top:-6px;width:14px;height:14px;border-radius:50%;background:var(--c);box-shadow:0 0 8px var(--c)}}
    .e-ok .luz{{animation:pisca 1.6s infinite}}@keyframes pisca{{50%{{opacity:.35}}}}
    @media (prefers-reduced-motion:reduce){{.luz{{animation:none!important}}}}
    .e-ok{{--c:#4A8A5A}}.e-atencao{{--c:#8A6410}}.e-alerta{{--c:#7A2214}}.e-erro{{--c:#7A2214}}.e-parado{{--c:#4A4F44}}
    h3{{margin:0;font-size:1.1rem}}.fn,.meta,.res{{margin:2px 0;font-size:.85rem;opacity:.85}}.st{{margin:6px 0}}
    ul{{margin:6px 0 0;padding-left:18px;font-size:.82rem}}li.g-alerta::marker{{color:#7A2214}}li.g-atencao::marker{{color:#8A6410}}
    .frentes{{display:flex;flex-wrap:wrap;gap:6px 18px;list-style:none;padding:0;margin:0 20px 10px}}
    footer{{padding:10px 20px 24px;font-size:.8rem;opacity:.8}}
    </style></head><body>
    <header><h1>🌳 Sala dos bots · Physis M&amp;A</h1>
    <div class="placar" role="status">{"".join(f'<span class="e-{k}">● {v} {ROT[k].lower()}</span>' for k, v in cont.items() if v)}</div>
    <button id="tema" type="button" aria-pressed="false">Tema escuro</button></header>
    <ul class="frentes" aria-label="Frentes">{frentes}</ul>
    <main>{salas}</main>
    <footer>Gerado em {datetime.now():%d/%m/%Y %H:%M} a partir de {html.escape(DB)}. Bots só observam e alertam; ações passam por aprovação (D49).</footer>
    <script>const b=document.getElementById('tema'),h=document.documentElement;
    try{{if(localStorage.getItem('physis-pref')==='escuro')h.dataset.tema='escuro'}}catch(e){{}}
    const s=()=>{{const e=h.dataset.tema==='escuro';b.textContent=e?'Tema claro':'Tema escuro';b.setAttribute('aria-pressed',e)}};s();
    b.onclick=()=>{{h.dataset.tema=h.dataset.tema==='escuro'?'':'escuro';try{{localStorage.setItem('physis-pref',h.dataset.tema||'claro')}}catch(e){{}}s()}};</script>
    </body></html>'''
    Path(OUT).parent.mkdir(parents=True, exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(page)
    return {"arquivo": str(OUT), **{k: v for k, v in cont.items() if v}}


def bot_sala(mv, saida=None):
    from . import mv_bots
    inicio = mv.nova_rodada()
    alvo = Path(saida or (mv_bots.SAIDA / "sala-dos-bots.html"))
    r = gerar(mv.db, alvo, "banco do M&A")
    mv.registrar_execucao("sala", inicio, json.dumps(r))
    return r


if __name__ == "__main__":
    print(gerar(sqlite3.connect(sys.argv[1] if len(sys.argv) > 1 else "physis-mv.db"),
                sys.argv[2] if len(sys.argv) > 2 else "sala-dos-bots.html", sys.argv[1] if len(sys.argv) > 1 else "physis-mv.db"))
