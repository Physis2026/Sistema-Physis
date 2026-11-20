"""Pesquisa diária de inovações tecnológicas abertas (diretriz da dona, 20/11/2026: "pesquisas de inovações tecnológicas abertas
para os sistemas em desenvolvimento ou sistemas que podem ser adicionados e integrados deve ser feita todos os dias para todas as
plataformas, sites, apps; após a aprovação de descobertas, o sistema inclui como atividade em seguida").

Roda SEM o Claude (dois nós locais: este PC e o Acer): lê feeds públicos (Atom/RSS) de lançamentos de projetos abertos que o Sistema
Physis usa ou pode integrar e de artigos científicos (arXiv) nos temas da Physis. Cada novidade vira um PEDIDO "inovacao" na fila de
bots (rascunho); aprovado, vira tarefa no M&A (frente transversal) para avaliar e integrar. Uma vez por dia; sem internet, registra e
tenta no dia seguinte.
"""
from __future__ import annotations

import time
import urllib.request
from xml.etree import ElementTree as ET

from .mv import MV

ESQUEMA = """
CREATE TABLE IF NOT EXISTS mv_inovacao (
  link TEXT PRIMARY KEY, titulo TEXT NOT NULL, fonte TEXT NOT NULL, tema TEXT NOT NULL DEFAULT '', visto REAL NOT NULL);
"""
FONTES = [  # (nome, url do feed, tema / onde usar)
    ("three.js", "https://github.com/mrdoob/three.js/releases.atom", "visualizador 3D (M&A, InovaSTEM, Physis 3D)"),
    ("web-ifc", "https://github.com/ThatOpen/engine_web-ifc/releases.atom", "BIM/IFC (Planejador, Estermic)"),
    ("IfcOpenShell", "https://github.com/IfcOpenShell/IfcOpenShell/releases.atom", "BIM/IFC no servidor"),
    ("MapLibre GL", "https://github.com/maplibre/maplibre-gl-js/releases.atom", "GIS (mapeamento, mapa local)"),
    ("PMTiles", "https://github.com/protomaps/PMTiles/releases.atom", "mapas sem internet"),
    ("EnergyPlus", "https://github.com/NREL/EnergyPlus/releases.atom", "simulação energética / AVAC"),
    ("pvlib", "https://github.com/pvlib/pvlib-python/releases.atom", "solar"),
    ("PrusaSlicer", "https://github.com/prusa3d/PrusaSlicer/releases.atom", "fatiamento 3D aberto (Physis 3D)"),
    ("arXiv · gêmeo digital de edificações", "http://export.arxiv.org/api/query?search_query=all:%22digital%20twin%22%20AND%20all:building&sortBy=submittedDate&max_results=5", "gêmeos digitais"),
    ("arXiv · AVAC e aprendizado de máquina", "http://export.arxiv.org/api/query?search_query=all:HVAC%20AND%20all:%22machine%20learning%22&sortBy=submittedDate&max_results=5", "AVAC / Estermic"),
    ("arXiv · medição e verificação de energia", "http://export.arxiv.org/api/query?search_query=all:%22measurement%20and%20verification%22%20AND%20all:energy&sortBy=submittedDate&max_results=5", "M&V (IPMVP)"),
]
NS = {"a": "http://www.w3.org/2005/Atom"}


def baixar(url: str, timeout: float = 15) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Physis-MA-inovacao/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(8_000_000)


def itens_do_feed(xml: bytes, limite: int = 3) -> list[tuple[str, str]]:
    raiz = ET.fromstring(xml)
    out = []
    for e in raiz.findall("a:entry", NS)[:limite]:
        t = (e.findtext("a:title", default="", namespaces=NS) or "").strip()
        ln = e.find("a:link", NS)
        link = (ln.get("href") if ln is not None else "") or (e.findtext("a:id", default="", namespaces=NS) or "")
        if t and link:
            out.append((" ".join(t.split())[:200], link.strip()))
    for e in raiz.iter("item"):                      # RSS 2.0
        if len(out) >= limite:
            break
        t, link = (e.findtext("title") or "").strip(), (e.findtext("link") or "").strip()
        if t and link:
            out.append((" ".join(t.split())[:200], link))
    return out


def rodar(mv: MV, buscar=baixar, fontes=None, agora: float | None = None) -> dict:
    from . import mv_comandos
    mv.db.executescript(ESQUEMA)
    agora = agora or time.time()
    ult = mv.db.execute("SELECT MAX(fim) FROM mv_execucao WHERE bot='inovacao' AND erro=''").fetchone()[0]
    if ult and agora - ult < 20 * 3600:
        return {"pulado": "já rodou hoje"}
    cmd = mv_comandos.Comandos(mv)
    novos, erros = 0, []
    for nome, url, tema in (fontes or FONTES):
        try:
            itens = itens_do_feed(buscar(url))
        except Exception as e:  # noqa: BLE001 — sem internet ou feed fora do ar: segue para a próxima fonte
            erros.append(f"{nome}: {type(e).__name__}")
            continue
        for titulo, link in itens:
            if mv.db.execute("SELECT 1 FROM mv_inovacao WHERE link=?", (link,)).fetchone():
                continue
            mv.db.execute("INSERT INTO mv_inovacao VALUES (?,?,?,?,?)", (link, titulo, nome, tema, agora))
            cmd._pedido("inovacao", f"{nome}: {titulo}", "", "rascunho",
                        f"Fonte aberta: {nome}\nTítulo: {titulo}\nLink: {link}\nOnde pode entrar: {tema}\n\n"
                        "Aprovar = vira tarefa no M&A para avaliar e integrar (versão de teste primeiro).", origem="inovacao")
            novos += 1
    mv.db.commit()
    return {"novos": novos, "fontes": len(fontes or FONTES), "erros": erros}
