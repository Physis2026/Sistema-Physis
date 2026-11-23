"""Checklist base de toda página (site, plataforma, loja, app, telas internas) conferido pelo Physis M&A (20/11/2026; pedido da dona:
"fazer um checklist de todas as informações base pra toda e qualquer página do site, plataforma, loja ou app"; doc 43).

O bot lê cada HTML do Sistema Physis (e outras raízes informadas) e confere o que dá para conferir no código. O que exige olho
humano (texto jurídico, fotos reais, conteúdo) fica na lista manual do doc 43. Resultado no M&A: aba Documentos → "Páginas e telas".
"""
from __future__ import annotations

import colorsys
import json
import os
import re
import time
from pathlib import Path

from .mv import MV

RAIZ = Path(os.environ.get("PHYSIS_RAIZ_SISTEMA") or Path(__file__).resolve().parents[2])
PALETA = Path(__file__).resolve().parents[1] / "docs" / "PALETA.md"
ESQUEMA = """
CREATE TABLE IF NOT EXISTS mv_pagina (
  caminho TEXT PRIMARY KEY, nome TEXT NOT NULL, tipo TEXT NOT NULL DEFAULT '', ok INTEGER NOT NULL DEFAULT 0,
  total INTEGER NOT NULL DEFAULT 0, falhas TEXT NOT NULL DEFAULT '[]', visto REAL NOT NULL);
"""
PAGINAS = [  # (caminho relativo, tipo)
    ("physis-hub/web/painel.html", "site e loja + plataforma do cliente"),
    ("physis-hub/web/consultoria.html", "site · consultoria"),
    ("physis-hub/web/municipio.html", "site · municípios"),
    ("physis-hub/web/documento.html", "documento"),
    ("physis-hub/web/mv.html", "interna · Physis M&A"),
    ("sistema/gestao-interna-physis.html", "interna · Gestão"),
    ("sistema/SustainKit_Definitivo.html", "programa · SustainKit"),
    ("sistema/physis-scada-demo.html", "programa · SCADA"),
    ("modulos/planejador/planejador-physis.html", "programa · Planejador"),
    ("app-nativo/site/baixar.html", "app · download"),
]
INOVASTEM = re.compile(r"inovastem", re.I)
# sistema do Instituto (outro repositório): as mesmas regras, e a barra tem de ser IDÊNTICA à original da Physis (dona, 20/11/2026)
INSTITUTO = Path(os.environ.get("PHYSIS_RAIZ_INSTITUTO") or (Path(__file__).resolve().parents[3] / "instituto-physis"))   # ao lado do sistema
PAGINAS_INSTITUTO = [
    ("physis-hub/web/site.html", "Instituto · site"), ("physis-hub/web/painel.html", "Instituto · plataforma"),
    ("physis-hub/web/documento.html", "Instituto · documento"), ("physis-hub/web/municipio.html", "Instituto · municípios"),
    ("sistema/gestao-interna-physis.html", "Instituto · Gestão"), ("sistema/SustainKit_Definitivo.html", "Instituto · SustainKit"),
    ("sistema/physis-scada-demo.html", "Instituto · SCADA"),
]


def paleta() -> set[str]:
    try:
        return {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}", PALETA.read_text(encoding="utf-8"))}
    except OSError:
        return set()


def azul(h: str) -> bool:
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    return ss > 0.25 and 0.5 < hh < 0.72 and 0.12 < ll < 0.92     # matiz entre ciano e azul, com saturação


HREF = re.compile(r'<a\b[^>]*\bhref="([^"]+)"', re.I)


def links_internos(html: str, pasta: Path) -> list[str]:
    """Âncoras (#id) que não existem na página e arquivos relativos que não existem na pasta (links quebrados internos)."""
    sem_js = re.sub(r"(?is)<script\b[^>]*>.*?</script>", "", html)
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    ruins = []
    for h in sorted(set(HREF.findall(sem_js))):
        if "${" in h or h.startswith(("http://", "https://", "mailto:", "tel:", "javascript:", "data:", "blob:", "/api/", "?")):
            continue
        if h.startswith("#"):
            if len(h) > 1 and h[1:] not in ids:
                ruins.append(h)
        elif not h.startswith("/"):
            alvo = (pasta / h.split("#")[0].split("?")[0]).resolve()
            if h.split("#")[0] and not alvo.exists():
                ruins.append(h)
    return ruins


IGNORAR_URL = re.compile(r"purl\.org|^http://x/|react\.dev/errors|^https://wa\.me/$|w3\.org|xmlns|schemas\.|example\.(com|org)|localhost|127\.0\.0\.1|\{|\$|\\", re.I)


def links_externos(html: str) -> list[str]:
    """Links externos da página: href do HTML e endereços escritos nos scripts DA PRÓPRIA PÁGINA (os módulos comuns embutidos,
    <script id="...">, ficam de fora: são conferidos na página de origem)."""
    proprio = re.sub(r'(?is)<script id="[^"]+">.*?</script>', "", html)
    achados = set(HREF.findall(proprio)) | set(re.findall(r"""https?://[^\s"'<>`)\]]+""", proprio))
    return sorted({h.rstrip(".,;") for h in achados if h.startswith(("http://", "https://")) and not IGNORAR_URL.search(h)})


def barra_original(raiz: Path) -> str:
    try:
        return (raiz / "sistema" / "physis-preferencias.js").read_text(encoding="utf-8").replace("\r\n", "\n")
    except OSError:
        return ""


def conferir(html: str, nome: str, pal: set[str], original: str = "", pasta: Path | None = None) -> list[dict]:
    """Devolve a lista de itens do checklist com ok True/False e o motivo."""
    sem_scripts = re.sub(r"(?is)<script\b[^>]*>.*?</script>", "", html)
    # telas montadas por script (plataforma, Gestão): o texto da própria tela conta; os módulos comuns embutidos não contam
    proprio = re.sub(r'(?is)<script id="[^"]+">.*?</script>', "", html)
    itens = []

    def item(cod, desc, ok, nota=""):
        itens.append({"cod": cod, "item": desc, "ok": bool(ok), "nota": nota})
    item("lang", "Idioma da página declarado (<html lang>)", re.search(r"<html[^>]*\blang=", html, re.I))
    item("titulo", "Título da página (<title>)", re.search(r"<title>[^<]{3,}</title>", html, re.I))
    item("viewport", "Ajuste para celular (meta viewport)", re.search(r'name="viewport"', html, re.I))
    item("main", "Conteúdo principal marcado (<main>)", re.search(r"<main\b", html, re.I))
    item("nav", "Navegação marcada (<nav> ou abas)", re.search(r"<nav\b|role=\"tablist\"", html, re.I))
    item("rodape", "Rodapé (<footer>)", re.search(r"<footer\b", html, re.I))
    item("preferencias", "Barra única de idioma, tema, conforto e acessibilidade (PcD)",
         re.search(r'<script id="physis-preferencias">\s*/\*\s*physis-preferencias\.js', html))
    if original:
        m = re.search(r'<script id="physis-preferencias">\n(.*?)</script>', html.replace("\r\n", "\n"), re.S)
        item("barra-igual", "Idioma, Modo de conforto e Acessibilidade iguais em todas as páginas (barra idêntica à original)",
             bool(m) and m.group(1) == original, "" if m else "sem a barra")
    if pasta is not None:
        quebrados = links_internos(html, pasta)
        item("links", "Links internos funcionando (âncoras e arquivos)", not quebrados, " ".join(quebrados[:6]))
    item("pular", "\"Pular para o conteúdo\" (teclado e leitor de tela)", re.search(r"Pular para o conte[uú]do|#conteudo", html, re.I))
    item("escuro", "Tema escuro (tipo A)", re.search(r'data-tema="?escuro|data-tema=escuro|prefers-color-scheme:\s*dark', html, re.I))
    item("fontes", "Fontes do guia (Josefin Sans nos títulos, Lora no corpo)", re.search(r"Josefin", html) and re.search(r"Lora", html))
    rod = " ".join(re.findall(r"(?is)<footer\b.*?</footer>", proprio)) or ""
    # Decisões da dona (22/11/2026): o rodapé leva só a razão social; NÃO mostra CNPJ nem cidade.
    item("cnpj", "Rodapé sem CNPJ e sem cidade", not re.search(r"CNPJ|Petr[oó]polis|Belo Horizonte", rod, re.I))
    item("razao", "Rodapé com a razão social (Physis Engineering Ltda. ou a do Instituto)",
         re.search(r"Physis Engineering Ltda\.|Instituto Physis", rod))
    # privacidade, termos e contato saem do checklist base (decisão: rodapé só com a razão social); ficam nas telas que já
    # os têm (loja, consultoria, /termos, /privacidade).
    externos = re.findall(r'<(?:script|link|img|iframe)\b[^>]*(?:src|href)="(https?://[^"]+)"', html, re.I)
    item("offline", "Funciona sem internet (sem scripts, fontes ou imagens de fora)", not externos, ", ".join(externos[:3]))
    imgs = re.findall(r"<img\b[^>]*>", sem_scripts, re.I)
    sem_alt = [i for i in imgs if not re.search(r"\balt=", i, re.I)]
    item("alt", "Imagens com texto alternativo", not sem_alt, f"{len(sem_alt)} sem alt" if sem_alt else "")
    cores = {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}\b", html)}
    azuis = sorted(c for c in cores if azul(c))
    item("sem-azul", "Nenhum azul (paletas do guia sem azul)", not azuis, " ".join(azuis[:8]))
    fora = sorted(cores - pal) if pal else []
    item("paleta", "Só cores da PALETA.md", not fora, " ".join(fora[:8]) + (f" (+{len(fora) - 8})" if len(fora) > 8 else ""))
    item("botao", "Botão principal laranja #C2410C com texto branco", "#C2410C" in cores)
    item("familia", "Sem \"família Physis\" (D99)", not re.search(r"fam[ií]lia physis", sem_scripts, re.I))
    endosso = re.search(r"uma iniciativa physis", sem_scripts, re.I)
    item("endosso", "\"uma iniciativa PHYSIS\" só na InovaSTEM (D102)", not endosso or INOVASTEM.search(nome))
    return itens


def rodar(mv: MV, raiz: Path | None = None, extras: list[tuple[str, str]] | None = None, instituto: Path | None = None) -> dict:
    mv.db.executescript(ESQUEMA)
    raiz = Path(raiz or RAIZ)
    pal = paleta()
    original = barra_original(raiz)
    inicio = mv.nova_rodada()
    out = []
    inst = Path(instituto or INSTITUTO)
    alvos = [(raiz / rel, rel, tipo) for rel, tipo in PAGINAS + list(extras or [])]
    if inst.is_dir():
        alvos += [(inst / rel, "instituto:" + rel, tipo) for rel, tipo in PAGINAS_INSTITUTO]
    for p, rel, tipo in alvos:
        if not p.is_file():
            continue
        itens = conferir(p.read_text(encoding="utf-8", errors="replace"), rel, pal, original, p.parent)
        ok = sum(i["ok"] for i in itens)
        falhas = [i for i in itens if not i["ok"]]
        mv.db.execute("INSERT OR REPLACE INTO mv_pagina VALUES (?,?,?,?,?,?,?)",
                      (rel, p.name, tipo, ok, len(itens), json.dumps(falhas, ensure_ascii=False), time.time()))
        out.append({"pagina": rel, "ok": ok, "total": len(itens)})
        if falhas:
            mv.alertar("paginas", "checklist_base", rel, "atencao" if len(falhas) <= 3 else "alerta",
                       f"{p.name}: {len(falhas)} item(ns) do checklist base faltando ({', '.join(f['cod'] for f in falhas[:6])})",
                       "Ver aba Documentos → Páginas e telas; checklist no doc 43")
    mv.fechar_alertas_nao_vistos("paginas", inicio)
    mv.db.commit()
    return {"paginas": len(out), "completas": sum(1 for o in out if o["ok"] == o["total"])}


def verificar_externos(mv: MV, raiz: Path | None = None, instituto: Path | None = None, buscar=None) -> dict:
    """Bot "links" (1x por dia): testa cada link externo das páginas (HEAD, e GET se o site recusar HEAD). Sem internet: registra
    e tenta no dia seguinte. Link que responde 4xx/5xx ou não responde vira alerta no M&A."""
    import urllib.request
    raiz = Path(raiz or RAIZ)
    inst = Path(instituto or INSTITUTO)
    mv.db.executescript("CREATE TABLE IF NOT EXISTS mv_link (url TEXT PRIMARY KEY, paginas TEXT NOT NULL, status TEXT NOT NULL, visto REAL NOT NULL);")

    def padrao(url):
        for metodo in ("HEAD", "GET"):
            try:
                req = urllib.request.Request(url, method=metodo, headers={"User-Agent": "Physis-MA-links/1.0"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    return str(r.status)
            except urllib.error.HTTPError as e:
                if metodo == "HEAD" and e.code in (403, 405, 501):
                    continue
                return str(e.code)
            except Exception as e:  # noqa: BLE001
                if metodo == "GET":
                    return type(e).__name__
        return "erro"
    buscar = buscar or padrao
    urls: dict[str, set] = {}
    alvos = [(raiz / rel, rel) for rel, _ in PAGINAS] + ([(inst / rel, "instituto:" + rel) for rel, _ in PAGINAS_INSTITUTO] if inst.is_dir() else [])
    for p, rel in alvos:
        if p.is_file():
            for u in links_externos(p.read_text(encoding="utf-8", errors="replace")):
                urls.setdefault(u, set()).add(rel)
    inicio = mv.nova_rodada()
    ruins = []
    for u, pags in sorted(urls.items()):
        st = buscar(u)
        mv.db.execute("INSERT OR REPLACE INTO mv_link VALUES (?,?,?,?)", (u, json.dumps(sorted(pags)), st, time.time()))
        if not st.isdigit() or int(st) >= 400:
            ruins.append(u)
            mv.alertar("links", "link_quebrado", u[:200], "atencao", f"Link externo sem resposta ({st}): {u[:120]}",
                       f"Corrigir em: {', '.join(sorted(pags))[:200]}")
    mv.fechar_alertas_nao_vistos("links", inicio)
    mv.db.commit()
    return {"links": len(urls), "quebrados": len(ruins)}


def listar(mv: MV) -> list[dict]:
    mv.db.executescript(ESQUEMA)
    return [{**dict(r), "falhas": json.loads(r["falhas"])} for r in mv.db.execute("SELECT * FROM mv_pagina ORDER BY ok * 1.0 / total, caminho")]
