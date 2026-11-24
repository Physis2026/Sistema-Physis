"""Bot de modelos dos fabricantes (24/11/2026: "buscar modelos no bot de pesquisa de mercado para os fabricantes na lista").

Sem base externa e sem inventar: lê os catálogos que a equipe guarda em Sistema Physis/Fornecedores/Catalogos (PDF com texto, HTML de
páginas salvas, XLSX/CSV/TXT/ODT/DOCX), procura os fabricantes da lista (sistema/physis-equipamentos.json) e, perto de cada nome, os
códigos de modelo (ex.: "38TVCA12", "WQ-1500", "VRF 8HP"). Cada fabricante com modelos achados vira um RASCUNHO no M&A para aprovar;
aprovado, os modelos entram na planilha de equipamentos da Gestão (ferramentas/semear_fornecedores.py --modelos <csv>).
Também grava modelos_propostos.csv com a fonte (arquivo e trecho). PDF escaneado: rode o OCR antes (Tesseract).
"""
from __future__ import annotations

import csv
import io
import json
import re
import subprocess
import shutil
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MODELO = re.compile(r"\b(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9][A-Z0-9-]{3,19}\b")
TIPOS = {".pdf", ".html", ".htm", ".txt", ".csv", ".xlsx", ".odt", ".docx", ".md"}
EVITAR = re.compile(r"^(NBR|ISO|IEC|ABNT|CNPJ|CEP|ART|RRT|R\d{2,3}A?|\d+[A-Z]?)$")


def fabricantes() -> dict[str, str]:
    base = json.loads((RAIZ / "sistema" / "physis-equipamentos.json").read_text(encoding="utf-8"))
    out = {}
    for seg, info in base.get("fabricantes_por_segmento", {}).items():
        if not seg.startswith("_"):
            for f in info.get("fabricantes", []):
                out.setdefault(f, seg)
    return out


def texto(p: Path) -> str:
    if p.suffix.lower() == ".pdf":
        exe = shutil.which("pdftotext")
        if not exe:
            return ""
        r = subprocess.run([exe, "-layout", str(p), "-"], capture_output=True, timeout=120)
        return r.stdout.decode("utf-8", "replace")
    from .ia_physis import _ler
    return _ler(p) if p.suffix.lower() != ".csv" else p.read_text(encoding="utf-8", errors="replace")


def achar_modelos(txt: str, fabs: dict[str, str], janela: int = 160) -> dict[str, list[tuple[str, str]]]:
    achados: dict[str, list[tuple[str, str]]] = {}
    marcas = sorted((m.start(), m.end(), f) for f in fabs for m in re.finditer(r"\b" + re.escape(f) + r"\b", txt, re.I))
    for k, (ini, fim, f) in enumerate(marcas):
        prox = next((a for a, _, g in marcas[k + 1:] if a >= fim and g != f), len(txt))      # para no próximo fabricante
        trecho = txt[fim: min(fim + janela, prox)]
        if trecho:
            for cod in MODELO.findall(trecho):
                if EVITAR.match(cod) or cod.upper() == f.upper():
                    continue
                lst = achados.setdefault(f, [])
                if cod not in [c for c, _ in lst]:
                    lst.append((cod, " ".join((txt[ini: fim + 60]).split())))
    return achados


def bot_modelos(mv, pasta: Path | None = None, saida: Path | None = None) -> dict:
    from . import mv_bots, mv_comandos
    pasta = Path(pasta or (mv_bots.DOCS / "Sistema Physis" / "Fornecedores" / "Catalogos"))
    if not pasta.is_dir():
        return {"pasta": str(pasta), "aviso": "pasta de catálogos ainda não existe: crie e guarde os catálogos dos fabricantes nela"}
    fabs, todos = fabricantes(), {}
    lidos, sem_texto = 0, []
    for p in sorted(x for x in pasta.rglob("*") if x.is_file() and x.suffix.lower() in TIPOS):
        t = texto(p)
        if not t.strip():
            sem_texto.append(p.name); continue
        lidos += 1
        for f, lst in achar_modelos(t, fabs).items():
            for cod, tr in lst:
                todos.setdefault(f, []).append({"modelo": cod, "arquivo": p.name, "trecho": tr})
    linhas = [["fabricante", "segmento", "modelo", "arquivo", "trecho"]] + [[f, fabs[f], x["modelo"], x["arquivo"], x["trecho"]] for f, l in todos.items() for x in l]
    destino = Path(saida or (mv_bots.SAIDA / "fornecedores"))
    destino.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO(); csv.writer(buf, delimiter=";").writerows(linhas)
    (destino / "modelos_propostos.csv").write_text("\ufeff" + buf.getvalue(), encoding="utf-8")
    cmd = mv_comandos.Comandos(mv); novos = 0
    for f, l in todos.items():
        ref = f"modelos:{f}"
        if mv.db.execute("SELECT 1 FROM mv_pedido_bot WHERE comando=?", (ref,)).fetchone():
            continue
        cmd._pedido("modelos", ref, "", "rascunho", f"{f} ({fabs[f]}): " + ", ".join(sorted({x['modelo'] for x in l}))[:1500]
                    + ". Conferir no catálogo antes de aprovar.", str(destino / "modelos_propostos.csv"), origem="modelos")
        novos += 1
    return {"pasta": str(pasta), "arquivos_lidos": lidos, "sem_texto": sem_texto, "fabricantes_com_modelos": len(todos), "rascunhos_novos": novos}
