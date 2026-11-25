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
        if not exe:                        # Windows sem Poppler: pypdf (py -m pip install pypdf), páginas separadas por \f
            try:
                from pypdf import PdfReader
                return "\f".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages)
            except Exception:  # noqa: BLE001 — sem pypdf ou PDF ilegível: sem texto (OCR antes)
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
    try:                       # 25/11/2026: catálogo técnico automático (baixa, lê, confere e grava; sem passo manual)
        tec = catalogo_automatico(pasta, fabs)
    except Exception as e:  # noqa: BLE001 — um defeito aqui não derruba a lista de modelos
        tec = {"erro": repr(e)}
    if tec.get("lacunas"):
        ref = "catalogo:lacunas:" + ",".join(tec["lacunas"])[:200]
        if not mv.db.execute("SELECT 1 FROM mv_pedido_bot WHERE comando=?", (ref,)).fetchone():
            cmd._pedido("modelos", ref, "", "rascunho", "Catálogo técnico sem condensadora multi-split válida de: " + ", ".join(tec["lacunas"])
                        + ". O bot baixa sozinho os catálogos listados em fontes.txt (Fabricante;endereço do PDF) na pasta de catálogos.", str(pasta), origem="modelos")
    return {"pasta": str(pasta), "arquivos_lidos": lidos, "sem_texto": sem_texto, "fabricantes_com_modelos": len(todos), "rascunhos_novos": novos,
            "catalogo_tecnico": tec}


# ── 25/11/2026: linhas TÉCNICAS para o catálogo (tudo automático: o bot baixa, lê, confere e grava) ─────────────────────────
BTU = re.compile(r"(\d{1,3}(?:[.\s]\d{3})+|\d{4,6})\s*(?:btu\s*/?\s*h|btus?)\b", re.I)
KW = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*kw\b", re.I)
SAIDAS = re.compile(r"\b([2-9])\s*[xX×]\s*1\b|\b(\d{1,2})\s*(?:saídas|saidas|unidades internas|evaporadoras|conexões|conexoes)\b", re.I)
PREFIXO = {"bi": 2, "tri": 3, "quadri": 4, "penta": 5}
COMB = re.compile(r"(\d{2,3})\s*%?\s*(?:a|até|-|–|~)\s*(\d{2,3})\s*%", re.I)
MCA = re.compile(r"(?:MCA|corrente m[aá]xima)\D{0,20}(\d+(?:[.,]\d+)?)\s*A\b", re.I)
MOP = re.compile(r"(?:MOP|disjuntor(?: m[aá]ximo)?)\D{0,20}(\d{1,3})\s*A\b", re.I)
TENSAO = re.compile(r"\b(127|220|380)\s*V\b")
DATA = (re.compile(r"\b(0[1-9]|1[0-2])\s*[/.-]\s*(20\d{2})\b"), re.compile(r"(?:©|rev\.?|revis[aã]o|edi[cç][aã]o|vers[aã]o)\s*:?\s*(20\d{2})\b", re.I))


def data_do_catalogo(txt: str) -> str:
    """Data escrita no próprio catálogo (mês/ano, revisão ou ©). Sem data no texto: vazio (a importação recusa; não se inventa)."""
    m = DATA[0].search(txt)
    if m:
        return f"{m.group(2)}-{m.group(1)}"
    m = DATA[1].search(txt)
    return m.group(1) if m else ""


def propor_tecnicos(txt: str, arquivo: str, fabs: dict[str, str], fonte: str = "") -> list[dict]:
    """Uma linha do catálogo técnico por modelo achado na MESMA linha do texto que a capacidade. Tipo pelo que a linha diz
    (evaporadora/condensadora) e pelo contexto multi-split da página. Linha ambígua não vira proposta."""
    data = data_do_catalogo(txt)
    nome_fab = next((f for f in fabs if re.search(r"\b" + re.escape(f) + r"\b", arquivo, re.I)), "")
    out, vistos = [], set()
    for pg, pagina in enumerate(txt.split("\f"), start=1):
        multi = bool(re.search(r"multi\s*-?\s*split|\b(bi|tri|quadri|penta)\s*-?\s*split|\b[2-9]\s*[xX×]\s*1\b", pagina, re.I))
        fab = nome_fab
        for linha in pagina.splitlines():
            for f in fabs:
                if re.search(r"\b" + re.escape(f) + r"\b", linha, re.I):
                    fab = f
            cap_b, cap_k = BTU.search(linha), KW.search(linha)
            if not fab or not (cap_b or cap_k):
                continue
            cods = [c for c in MODELO.findall(linha) if not EVITAR.match(c) and c.upper() != fab.upper() and not c.isdigit()]
            if not cods:
                continue
            l = linha.lower()
            sd = SAIDAS.search(linha)
            saidas = (int(sd.group(1) or sd.group(2)) if sd else
                      next((n for p, n in PREFIXO.items() if re.search(r"\b" + p + r"\s*-?\s*split", l)), None))
            if re.search(r"evaporadora|unidade interna|\binterna\b|hi-?wall|cassete|console|piso-?teto|dutad", l):
                tipo = "evaporadora_multi" if multi else "split"
            elif re.search(r"condensadora|unidade externa|\bexterna\b", l) or saidas:
                tipo = "condensadora_multi" if (multi or saidas) else "split"
            else:
                continue
            chave = (tipo, fab, cods[0])
            if chave in vistos:
                continue
            vistos.add(chave)
            r = {k: "" for k in ("tipo", "fabricante", "linha", "modelo", "cap_resf_btuh", "cap_resf_kw", "saidas_max", "comb_min_pct",
                                 "comb_max_pct", "tensao_v", "fases", "corrente_max_a", "disjuntor_max_a", "fonte", "fonte_ref", "data_fonte")}
            r.update(tipo=tipo, fabricante=fab, modelo=cods[0], fonte=fonte or arquivo, fonte_ref=f"p. {pg}", data_fonte=data)
            if cap_b:
                r["cap_resf_btuh"] = re.sub(r"[.\s]", "", cap_b.group(1))
            else:
                r["cap_resf_kw"] = cap_k.group(1)
            if tipo == "condensadora_multi" and saidas:
                r["saidas_max"] = str(saidas)
            cb = COMB.search(linha)
            if cb and int(cb.group(1)) < int(cb.group(2)):
                r["comb_min_pct"], r["comb_max_pct"] = cb.group(1), cb.group(2)
            for k, rx in (("corrente_max_a", MCA), ("disjuntor_max_a", MOP), ("tensao_v", TENSAO)):
                m = rx.search(linha)
                if m:
                    r[k] = m.group(1)
            if re.search(r"monof", l):
                r["fases"] = "1"
            elif re.search(r"trif", l):
                r["fases"] = "3"
            out.append(r)
    return out


def baixar_fontes(pasta: Path, abrir=None) -> dict:
    """fontes.txt na pasta dos catálogos (uma por linha: Fabricante;https://...pdf). O bot baixa o que ainda não tem para
    pasta/baixados e guarda endereço, data e SHA-256 em fontes-baixadas.json. Sem internet: segue com o que já tem."""
    import hashlib
    import time
    import urllib.request
    lista, reg_arq = pasta / "fontes.txt", pasta / "fontes-baixadas.json"
    reg = json.loads(reg_arq.read_text(encoding="utf-8")) if reg_arq.is_file() else {}
    if not lista.is_file():
        return {"fontes": 0, "baixados": 0, "falhas": [], "registro": reg}
    dest = pasta / "baixados"
    dest.mkdir(exist_ok=True)
    abrir = abrir or (lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Physis-bot-modelos"}), timeout=60).read())
    n, falhas, total = 0, [], 0
    for l in lista.read_text(encoding="utf-8-sig").splitlines():
        if not l.strip() or l.lstrip().startswith("#") or ";" not in l:
            continue
        fab, url = [x.strip() for x in l.split(";", 1)]
        if not re.match(r"https?://", url):
            continue
        total += 1
        nome = re.sub(r"[^A-Za-z0-9._-]+", "-", fab + "-" + url.rsplit("/", 1)[-1])[:120]
        if not nome.lower().endswith((".pdf", ".csv", ".xlsx", ".html", ".htm", ".txt")):
            nome += ".pdf"
        if nome in reg and (dest / nome).is_file():
            continue
        try:
            dados = abrir(url)
            if len(dados) > 60 * 1024 * 1024:
                raise ValueError("arquivo maior que 60 MB")
            (dest / nome).write_bytes(dados)
            reg[nome] = {"fabricante": fab, "url": url, "baixado": time.strftime("%Y-%m-%d"), "sha256": hashlib.sha256(dados).hexdigest()}
            n += 1
        except Exception as e:  # noqa: BLE001 — sem internet ou endereço fora do ar: registra e segue
            falhas.append(f"{fab}: {type(e).__name__}")
    reg_arq.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"fontes": total, "baixados": n, "falhas": falhas, "registro": reg}


def catalogo_automatico(pasta: Path, fabs: dict[str, str], textos: dict[str, str] | None = None, catalogo=None, abrir=None) -> dict:
    """Baixa (fontes.txt), lê, propõe e GRAVA no catálogo técnico (PHYSIS_CATALOGO). Linha completa e sem aviso: conferido_bot."""
    from . import catalogo_modelos as cm
    b = baixar_fontes(pasta, abrir)
    urls = {k: v["url"] for k, v in b["registro"].items()}
    linhas = []
    if textos is None:
        textos = {}
        for p in sorted(x for x in pasta.rglob("*") if x.is_file() and x.suffix.lower() in TIPOS):
            textos[p.name] = texto(p)
    for nome, t in textos.items():
        if t.strip():
            linhas += propor_tecnicos(t, nome, fabs, urls.get(nome, ""))
    cat = catalogo or cm.Catalogo(cm.caminho_padrao())
    r = cat.importar_linhas(linhas, "bot-modelos", origem="bot", nome_arquivo="catálogos da pasta") if linhas else {"gravadas": 0, "recusadas": []}
    est = {}
    for m in cat.modelos():
        est[m["estado"]] = est.get(m["estado"], 0) + 1
    lac = cat.lacunas()
    return {"download": {k: b[k] for k in ("fontes", "baixados", "falhas")}, "propostas": len(linhas), "gravadas": r.get("gravadas", 0),
            "iguais": r.get("iguais", 0), "recusadas": len(r.get("recusadas", [])), "motivos_recusa": sorted({x["erro"] for x in r.get("recusadas", [])})[:10],
            "por_estado": est, "lacunas": [f["fabricante"] for s in lac["segmentos"] for f in s["fabricantes"] if f["lacuna"] and "multi" in s["segmento"].lower()]}
