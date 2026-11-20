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


def paleta() -> set[str]:
    try:
        return {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}", PALETA.read_text(encoding="utf-8"))}
    except OSError:
        return set()


def azul(h: str) -> bool:
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    return ss > 0.25 and 0.5 < hh < 0.72 and 0.12 < ll < 0.92     # matiz entre ciano e azul, com saturação


def conferir(html: str, nome: str, pal: set[str]) -> list[dict]:
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
    item("pular", "\"Pular para o conteúdo\" (teclado e leitor de tela)", re.search(r"Pular para o conte[uú]do|#conteudo", html, re.I))
    item("escuro", "Tema escuro (tipo A)", re.search(r'data-tema="?escuro|data-tema=escuro|prefers-color-scheme:\s*dark', html, re.I))
    item("fontes", "Fontes do guia (Josefin Sans nos títulos, Lora no corpo)", re.search(r"Josefin", html) and re.search(r"Lora", html))
    rod = " ".join(re.findall(r"(?is)<footer\b.*?</footer>", proprio)) or ""
    item("cnpj", "Rodapé com razão social e CNPJ (ou [MARCADOR])", re.search(r"CNPJ", rod, re.I))
    item("privacidade", "Privacidade/LGPD indicada", re.search(r"privacidade|LGPD", proprio, re.I))
    item("termos", "Termos de uso indicados", re.search(r"termos de uso", proprio, re.I))
    item("contato", "Contato indicado", re.search(r"contato|e-mail|fale com", proprio, re.I))
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


def rodar(mv: MV, raiz: Path | None = None, extras: list[tuple[str, str]] | None = None) -> dict:
    mv.db.executescript(ESQUEMA)
    raiz = Path(raiz or RAIZ)
    pal = paleta()
    inicio = mv.nova_rodada()
    out = []
    for rel, tipo in PAGINAS + list(extras or []):
        p = raiz / rel
        if not p.is_file():
            continue
        itens = conferir(p.read_text(encoding="utf-8", errors="replace"), rel, pal)
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


def listar(mv: MV) -> list[dict]:
    mv.db.executescript(ESQUEMA)
    return [{**dict(r), "falhas": json.loads(r["falhas"])} for r in mv.db.execute("SELECT * FROM mv_pagina ORDER BY ok * 1.0 / total, caminho")]
