#!/usr/bin/env python3
"""Padroniza as telas pelo checklist base (doc 43) sem mudar função nem conta (regras 1, 2 e 6 do CLAUDE.md).

    python ferramentas/padronizar_paginas.py              # aplica (idempotente)
    python ferramentas/padronizar_paginas.py --conferir   # só mostra o que mudaria
    python ferramentas/padronizar_paginas.py --raiz C:\physis\instituto-physis --razao "Instituto Physis" --lista instituto
        (outro repositório: usa o verificador deste M&A e as ferramentas de cópia do repositório indicado)

O que faz em cada tela de mv_paginas.PAGINAS:
1. Fontes do guia (Lora no corpo; Josefin Sans para logotipos) embutidas em base64 (sem internet; OFL em vendor/fontes).
   A fonte para dislexia da barra de preferências continua valendo (usa !important).
2. Rodapé só com a razão social "Physis Engineering Ltda." (decisão de 22/11/2026) e um link "Voltar ao início".
   O rodapé tem <nav> próprio; telas sem <main> ganham um <main style="display:contents"> (não muda o layout).
3. Cores: azul ou fora da PALETA.md vira a cor permitida mais próxima com a mesma claridade (contraste mantido).
   Cores dentro dos módulos comuns (<script id="...">) são trocadas no original em sistema/*.js; depois rode sincronizar.py.
4. Link interno quebrado conhecido: gestao-physis.html → gestao-interna-physis.html (a Gestão interna aponta para si mesma).
"""
from __future__ import annotations

import base64
import json
import colorsys
import re
import sys
from pathlib import Path

def _arg(nome: str, padrao: str | None = None) -> str | None:
    a = sys.argv[1:]
    return a[a.index(nome) + 1] if nome in a and a.index(nome) + 1 < len(a) else padrao


FERR = Path(__file__).resolve().parent.parent                 # repositório desta ferramenta (verificador e fontes)
RAIZ = Path(_arg("--raiz") or FERR).resolve()                 # repositório onde aplicar (padrão: este)
LISTA = _arg("--lista", "physis")                             # physis | instituto
sys.path.insert(0, str(FERR / "physis-hub"))
sys.path.insert(0, str(RAIZ / "ferramentas"))                 # sincronizar/embutir_bases DO repositório onde aplicar
from physis_hub import mv_paginas  # noqa: E402
import embutir_bases  # noqa: E402
import sincronizar  # noqa: E402

# blocos que são CÓPIA de um original (sincronizar.py / embutir_bases.py): a cor muda no original, nunca na cópia
COPIAS = set(sincronizar.BLOCOS) | set(sincronizar.ANTIGOS) | set(embutir_bases.MODULOS) | set(embutir_bases.BASES)
ORIGINAIS = sorted({*sincronizar.BLOCOS.values(), *embutir_bases.MODULOS.values(), *embutir_bases.BASES.values(),
                    sincronizar.ORIGEM, sincronizar.NUCLEO})

FONTES = FERR / "vendor" / "fontes"
ARQ_FONTES = [("Lora", 400, "lora-latin-400-normal.woff2"), ("Lora", 700, "lora-latin-700-normal.woff2"),
              ("Josefin Sans", 700, "josefin-sans-latin-700-normal.woff2")]
MARCA = "physis-guia"
RODAPE_ID = "physis-rodape"
TROCAS_LINK = {'href="gestao-physis.html"': 'href="gestao-interna-physis.html"'}
# Texto do rodapé: só o que é fato; o resto é [MARCADOR] (regra 1). "Physis Engineering" é o nome usado nas próprias telas.
# Decisão da dona (22/11/2026): o rodapé leva só a razão social, sem CNPJ, cidade ou outros dados.
RAZAO = _arg("--razao", "Physis Engineering Ltda.")          # Instituto: "Instituto Physis" (sem CNPJ ainda: não inventar razão social)
LEGAL = (f'<nav class="physis-rodape-nav" aria-label="Rodapé"><p><span>{RAZAO}</span> <a href="#">Voltar ao início</a></p></nav>')
# textos que versões anteriores desta ferramenta puseram nos dicionários e que saem agora
INGLES_ANTIGO = ["Informações legais", "Physis Engineering · CNPJ [MARCADOR]", "Privacidade e LGPD: [MARCADOR]",
                 "Termos de uso: [MARCADOR]", "Contato: [MARCADOR]"]


def css_guia() -> str:
    pal = permitidas()
    k = {c: mais_proxima(c, pal) for c in ("#1B1F23", "#F4F1EA", "#C9D2C4", "#23282D", "#4A4F44")}   # cores do rodapé NA paleta do repositório
    faces = "".join(
        f'@font-face{{font-family:"{fam}";font-style:normal;font-weight:{peso};font-display:swap;'
        f'src:url(data:font/woff2;base64,{base64.b64encode((FONTES / arq).read_bytes()).decode()}) format("woff2")}}'
        for fam, peso, arq in ARQ_FONTES)
    return (f'<style id="{MARCA}">{faces}'
            'body{font-family:"Lora",Georgia,serif}'
            '.physis-logo,.physis-marca{font-family:"Josefin Sans","Lora",Georgia,serif}'
            f'#{RODAPE_ID}{{font:13px/1.5 "Lora",Georgia,serif;color:{k["#1B1F23"]};background:{k["#F4F1EA"]};border-top:1px solid {k["#C9D2C4"]};'
            'padding:12px 16px;margin-top:16px}'
            f'#{RODAPE_ID} p{{margin:2px 0}}'
            f'html[data-tema="escuro"] #{RODAPE_ID}{{color:{k["#F4F1EA"]};background:{k["#23282D"]};border-color:{k["#4A4F44"]}}}'
            f'html[data-em-quadro] #{RODAPE_ID}{{display:none}}'
            '</style>')


# ---- cores ---------------------------------------------------------------------------------------------------------
def _lab(h: str):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in (r, g, b)]
    x = (0.4124 * lin[0] + 0.3576 * lin[1] + 0.1805 * lin[2]) / 0.95047
    y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    z = (0.0193 * lin[0] + 0.1192 * lin[1] + 0.9505 * lin[2]) / 1.08883
    f = [t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116 for t in (x, y, z)]
    return 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])


def permitidas() -> list[str]:
    """Cores da PALETA.md DO repositório onde se aplica (o Instituto tem a dele), sem azul."""
    arq = RAIZ / "physis-hub" / "docs" / "PALETA.md"
    pal = {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}", arq.read_text(encoding="utf-8"))} if arq.is_file() else mv_paginas.paleta()
    return sorted(c for c in pal if not mv_paginas.azul(c))


def mais_proxima(h: str, pal: list[str]) -> str:
    L, a, b = _lab(h)
    def custo(c):
        L2, a2, b2 = _lab(c)
        return 3 * abs(L - L2) + ((a - a2) ** 2 + (b - b2) ** 2) ** 0.5   # claridade pesa 3x: mantém o contraste
    return min(pal, key=custo)


def ruins(cores: set[str], pal_ok: set[str]) -> set[str]:
    return {c for c in cores if mv_paginas.azul(c) or c not in pal_ok}


HEX = re.compile(r"#[0-9A-Fa-f]{6}\b")
BLOCO = re.compile(r'(?is)(<script id="[^"]+">)(.*?)(</script>)')
SCRIPT = re.compile(r"(?is)<script\b[^>]*>.*?</script>")
BLOCO_COPIA = re.compile(r'(?is)<script\b[^>]*\bid="([^"]+)"[^>]*>.*?</script>')


def trechos_copia(html: str) -> list[tuple[int, int]]:
    """Faixas que são cópia de original: blocos de COPIAS, o exportador e o núcleo embutido."""
    r = [(m.start(), m.end()) for m in BLOCO_COPIA.finditer(html) if m.group(1) in COPIAS]
    for ini, fim in ((sincronizar.INICIO, sincronizar.FIM), (sincronizar.NUCLEO_MARCA, "</script>")):
        i = html.find(ini)
        if i >= 0:
            j = html.find(fim, i)
            r.append((i, j + len(fim) if j >= 0 else len(html)))
    return sorted(r)


def fora_de_script(html: str, alvo: str, ultimo: bool = False) -> int:
    """Posição de 'alvo' (sem diferenciar maiúsculas) fora de qualquer <script>: o primeiro, ou o último."""
    faixas = [(m.start(), m.end()) for m in SCRIPT.finditer(html)]
    achados = [m.start() for m in re.finditer(re.escape(alvo), html, re.I)
               if not any(a <= m.start() < b for a, b in faixas)]
    if not achados:
        raise SystemExit(f"não achei {alvo} fora de script")
    return achados[-1] if ultimo else achados[0]


def trocar_cores(txt: str, mapa: dict[str, str]) -> str:
    return HEX.sub(lambda m: mapa.get(m.group(0).upper(), m.group(0)), txt)


# ---- página --------------------------------------------------------------------------------------------------------
INGLES = {"Rodapé": "Footer", RAZAO: RAZAO, "Voltar ao início": "Back to top"}


def traduzir(html: str) -> str:
    """Põe o inglês do rodapé no dicionário da tela (consultoria, SustainKit), se ela tiver um; tira o das versões antigas."""
    for k in INGLES_ANTIGO:
        html = re.sub(r'\r?\n[ \t]*' + re.escape(json.dumps(k, ensure_ascii=False)) + r': "[^"\n]*",', "", html)
    # telas com dicionário EN["..."]="..."; (Physis M&A)
    ens = list(re.finditer(r'(?m)^EN\["[^"\n]*"\]="[^"\n]*";[ \t]*\r?$', html))
    if ens:
        faltam = [(k, v) for k, v in INGLES.items() if f'EN[{json.dumps(k, ensure_ascii=False)}]=' not in html]
        if faltam:
            fim = ens[-1].end()
            cr = "\r" if html[ens[-1].start():fim].endswith("\r") else ""
            novos = "".join(f'\nEN[{json.dumps(k, ensure_ascii=False)}]={json.dumps(v, ensure_ascii=False)};{cr}' for k, v in faltam)
            html = html[:fim] + novos + html[fim:]
        return html
    copias = trechos_copia(html)   # o exemplo no comentário do módulo de preferências não conta
    ms = [m for m in re.finditer(r"\bdicionario: \{", html) if not any(a <= m.start() < b for a, b in copias)]
    if not ms:
        return html
    m = ms[-1]
    faltam = [(k, v) for k, v in INGLES.items() if json.dumps(k, ensure_ascii=False) + ":" not in html]
    if not faltam:
        return html
    # depois da 1ª entrada, mantendo o recuo dela (gerar_demos.py ancora no início do dicionário)
    fim1 = html.index("\n", html.index("\n", m.end()) + 1)
    linha1 = html[html.index("\n", m.end()) + 1:fim1]
    recuo = linha1[:len(linha1) - len(linha1.lstrip())]
    cr = "\r" if linha1.endswith("\r") else ""
    novos = "".join(f"\n{recuo}{json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)},{cr}" for k, v in faltam)
    return html[:fim1] + novos + html[fim1:]


def padronizar(html: str, mapa: dict[str, str]) -> str:
    nl = "\r\n" if "\r\n" in html else "\n"
    # cores fora das cópias (as cópias mudam no original)
    partes, pos = [], 0
    for a, b in trechos_copia(html):
        if a < pos:
            continue
        partes.append(trocar_cores(html[pos:a], mapa))
        partes.append(html[a:b])
        pos = b
    partes.append(trocar_cores(html[pos:], mapa))
    html = "".join(partes)
    for a, b in TROCAS_LINK.items():
        html = html.replace(a, b)
    # tira o que esta ferramenta pôs antes (idempotente)
    html = re.sub(rf'<style id="{MARCA}">.*?</style>(\r?\n)?', "", html, flags=re.S)
    html = re.sub(rf'(?s)<footer id="{RODAPE_ID}"[^>]*>.*?</footer>(\r?\n)?', "", html)
    html = re.sub(rf'(?s)<div id="{RODAPE_ID}-legal">.*?</nav></div>', "", html)
    html = html.replace('<main id="physis-main" style="display:contents">', "").replace("</main><!--physis-main-->", "")
    # fontes + estilo do rodapé
    i = fora_de_script(html, "</head>")
    # antes das bases e módulos embutidos (embutir_bases.py sempre os põe logo antes do </head>)
    emb = re.search(r'(?m)^<script (?:type="application/json" )?id="(?:base|mod)-[\w-]+">', html[:i])
    i = emb.start() if emb else i
    html = html[:i] + css_guia() + nl + html[i:]
    html = traduzir(html)
    # rodapé
    sem_copias = BLOCO.sub("", html)
    rod = " ".join(re.findall(r"(?is)<footer\b.*?</footer>", sem_copias))
    if not re.search(r"<footer\b", sem_copias, re.I):
        j = fora_de_script(html, "</body>", ultimo=True)
        html = html[:j] + f'<footer id="{RODAPE_ID}" class="physis-rodape">{LEGAL}</footer>{nl}' + html[j:]
    elif RAZAO not in rod or not re.search(r"<nav\b", sem_copias, re.I):
        faixas = [(m.start(), m.end()) for m in SCRIPT.finditer(html)]
        m = next(m for m in re.finditer(r"(?is)<footer\b[^>]*>", html) if not any(a <= m.start() < b for a, b in faixas))
        html = html[:m.end()] + f'<div id="{RODAPE_ID}-legal">{LEGAL}</div>' + html[m.end():]
    # <main> que não muda o layout
    if not re.search(r"<main\b", BLOCO.sub("", html), re.I):
        b = fora_de_script(html, "<body")
        b = html.index(">", b) + 1
        html = html[:b] + '<main id="physis-main" style="display:contents">' + html[b:]
        j = html.find(f'<footer id="{RODAPE_ID}"')
        j = j if j >= 0 else fora_de_script(html, "</body>", ultimo=True)
        html = html[:j] + "</main><!--physis-main-->" + html[j:]
    return html


def main(argv) -> int:
    so_conferir = "--conferir" in argv
    pal = permitidas()
    pal_set = set(pal)
    if LISTA == "instituto":
        # a InovaSTEM é marca própria (sem "Instituto Physis" na página; lilás da Delas): fica de fora (testes do Instituto)
        paginas = [RAIZ / c for c, _ in mv_paginas.PAGINAS_INSTITUTO]
    else:
        paginas = [RAIZ / c for c, _ in mv_paginas.PAGINAS]
    paginas = [p for p in paginas if p.is_file()]
    # cores ruins em todas as telas e nos módulos comuns originais
    modulos = [p for p in ORIGINAIS if p.exists()]
    todas = set()
    for p in paginas:
        t = p.read_text(encoding="utf-8")
        todas |= ruins({c.upper() for c in HEX.findall(t)}, pal_set)
    for p in modulos:
        todas |= ruins({c.upper() for c in HEX.findall(p.read_text(encoding="utf-8"))}, pal_set)
    mapa = {c: mais_proxima(c, pal) for c in sorted(todas)}
    for c, d in mapa.items():
        print(f"  cor {c} -> {d}")
    for p in modulos:
        t = p.read_text(encoding="utf-8")
        n = trocar_cores(t, mapa)
        if n != t:
            print(f"  módulo comum: {p.relative_to(RAIZ)}")
            if not so_conferir:
                p.write_text(n, encoding="utf-8", newline="")
    for p in paginas:
        t = p.read_text(encoding="utf-8")
        n = padronizar(t, mapa)
        if n != t:
            print(f"  tela: {p.relative_to(RAIZ)}")
            if not so_conferir:
                p.write_text(n, encoding="utf-8", newline="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
