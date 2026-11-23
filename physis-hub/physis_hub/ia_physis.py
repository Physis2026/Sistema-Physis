"""IA Physis (v0, 22/11/2026): IA própria da Physis, feita do zero, só para o servidor, o Sistema Physis, as plataformas e os apps.

O que é, sem exagero:
- **Índice próprio** dos textos da Physis (documentação, explicação do código, pastas de documentos compartilhadas e acervo),
  guardado num SQLite local (FTS5 com BM25), atualizado só no que mudou.
- **Resposta extrativa com fonte:** a IA devolve frases que existem nos documentos, cada uma com [n] e o arquivo de origem.
  Não escreve fato novo, não inventa número (regra 1). Sem evidência suficiente, responde que não encontrou.
- **Temas:** os termos e pares de termos que mais aparecem em cada conjunto de documentos (TF-IDF), para mapear cursos.
- **Sem terceiros (regra 11):** nada sai do computador. Um modelo aberto local (PHYSIS_IA_URL, vLLM) pode, no futuro, só
  reescrever a resposta mantendo as fontes; sem ele, tudo funciona.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import time
from collections import Counter, defaultdict
from pathlib import Path

from . import mv as mvmod
from .robos import PARADAS, normalizar

RAIZ_REPO = Path(__file__).resolve().parents[2]
TIPOS = {".md", ".txt", ".odt", ".docx", ".odp", ".pptx", ".ods", ".xlsx", ".html"}
MIN_PALAVRAS, MAX_PALAVRAS = 6, 220      # 6: linhas curtas de plano ("Validação de dezembro: …") não podem se perder
ESQUEMA = """
CREATE TABLE IF NOT EXISTS ia_arquivo (caminho TEXT PRIMARY KEY, grupo TEXT NOT NULL, assinatura TEXT NOT NULL, visto REAL NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS ia_trecho USING fts5(texto, caminho UNINDEXED, grupo UNINDEXED, secao,
    tokenize='unicode61 remove_diacritics 2');
"""


# verbos e palavras de pergunta, e palavras de código, que não dizem o assunto
VAZIAS = set("""faco fazer faz fazem posso pode podem preciso precisa quero queria existe existem funciona funcionam
onde qual quais quanto quantos quanta como devo deve serve servem tenho temos sobre algum alguma dizer explica explique
self true false none return json html http https string lista dict""".split())


def termos(texto: str) -> list[str]:
    """Palavras com 4+ letras, sem acento e sem palavras vazias (forma legível, sem cortar o radical)."""
    return [w for w in re.findall(r"[a-z0-9]+", normalizar(texto)) if len(w) >= 4 and w not in PARADAS and w not in VAZIAS and not w.isdigit()]


def _ler(p: Path) -> str:
    if p.suffix.lower() in (".md", ".txt"):
        return p.read_text(encoding="utf-8", errors="replace")
    if p.suffix.lower() == ".html":
        t = p.read_text(encoding="utf-8", errors="replace")
        t = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", t)
        return re.sub(r"<[^>]+>", " ", t)
    from .mv_bots import texto_de
    return texto_de(p) or ""


def trechos(texto: str) -> list[tuple[str, str]]:
    """(seção, trecho): parágrafos de 12 a 220 palavras; o título Markdown mais recente vira a seção."""
    out, secao = [], ""
    for par in re.split(r"\n\s*\n", texto):
        # linha de tabela Markdown vira frase ("a — b — c."); separadores e cercas de código saem
        linhas = []
        for l in par.strip().splitlines():
            s = l.strip()
            if not s or s.startswith(("```", "---")) or re.fullmatch(r"\|[\s:|-]+\|?", s):
                continue
            if re.search(r"\b[0-9a-fA-F]{32,}\b", s):     # lista de SHA256/hashes não é texto (resposta da missão vinha com hashes, 23/11)
                continue
            if s.startswith("|"):
                cel = [c.strip() for c in s.strip("|").split("|") if c.strip()]
                s = " — ".join(cel).rstrip(".") + "."
            linhas.append(s)
        if not linhas:
            continue
        if linhas[0].lstrip().startswith("#"):
            secao = linhas[0].strip("# ").strip()[:120]
            linhas = linhas[1:]
        t = " ".join(" ".join(linhas).split())
        pal = t.split()
        for i in range(0, len(pal), MAX_PALAVRAS):
            pedaco = pal[i:i + MAX_PALAVRAS]
            if len(pedaco) >= MIN_PALAVRAS:
                out.append((secao, " ".join(pedaco)))
    return out


def fontes_padrao() -> dict[str, list[Path]]:
    """Grupos de fontes. PHYSIS_IA_PASTAS acrescenta pastas (separadas por ; ou :) no grupo 'documentos'."""
    from . import mv_bots
    g = {"sistema": [RAIZ_REPO / "CLAUDE.md", RAIZ_REPO / "physis-hub" / "docs"],
         "documentos": mv_bots.pastas_documentos()}
    from . import mv_repositorios
    g["repositorios"] = mv_repositorios.caminhos_existentes()      # marketing-physis e outros
    extra = os.environ.get("PHYSIS_IA_PASTAS", "")
    g["documentos"] += [Path(x) for x in re.split(r"[;" + os.pathsep + "]", extra) if x.strip()]
    return g


class IAPhysis:
    def __init__(self, caminho: str | Path | None = None):
        self.caminho = str(caminho or (mvmod.pasta_padrao() / "ia-physis.db"))
        self.db = sqlite3.connect(self.caminho, check_same_thread=False)   # o servidor do M&A atende em várias threads
        self.db.executescript(ESQUEMA)

    # ---- índice ------------------------------------------------------------------------------------------------
    def indexar(self, grupos: dict[str, list[Path]] | None = None) -> dict:
        grupos = grupos or fontes_padrao()
        vistos, novos, removidos, faltam = set(), 0, 0, []
        for grupo, raizes in grupos.items():
            for raiz in raizes:
                raiz = Path(raiz)
                if not raiz.exists():
                    faltam.append(str(raiz))
                    continue
                arqs = [raiz] if raiz.is_file() else [p for p in raiz.rglob("*") if p.is_file() and p.suffix.lower() in TIPOS
                                                       and not any(x in p.parts for x in (".git", "node_modules", "backup", "kits", "28_Physis_MV"))]
                for p in arqs:
                    c = str(p)
                    vistos.add(c)
                    st = p.stat()
                    ass = f"{st.st_size}:{int(st.st_mtime)}"
                    ant = self.db.execute("SELECT assinatura FROM ia_arquivo WHERE caminho=?", (c,)).fetchone()
                    if ant and ant[0] == ass:
                        continue
                    try:
                        partes = trechos(_ler(p))
                    except Exception:  # noqa: BLE001 — arquivo ilegível não para o índice
                        partes = []
                    self.db.execute("DELETE FROM ia_trecho WHERE caminho=?", (c,))
                    self.db.executemany("INSERT INTO ia_trecho (texto, caminho, grupo, secao) VALUES (?,?,?,?)",
                                        [(t, c, grupo, s) for s, t in partes])
                    self.db.execute("INSERT OR REPLACE INTO ia_arquivo VALUES (?,?,?,?)", (c, grupo, ass, time.time()))
                    novos += 1
        for (c,) in self.db.execute("SELECT caminho FROM ia_arquivo").fetchall():
            if c not in vistos:
                self.db.execute("DELETE FROM ia_trecho WHERE caminho=?", (c,))
                self.db.execute("DELETE FROM ia_arquivo WHERE caminho=?", (c,))
                removidos += 1
        self.db.commit()
        n = self.db.execute("SELECT COUNT(*) FROM ia_arquivo").fetchone()[0]
        t = self.db.execute("SELECT COUNT(*) FROM ia_trecho").fetchone()[0]
        return {"arquivos": n, "trechos": t, "atualizados": novos, "removidos": removidos, "pastas_ausentes": faltam}

    # ---- perguntas -----------------------------------------------------------------------------------------------
    def buscar(self, pergunta: str, k: int = 6, grupo: str | None = None) -> list[dict]:
        ts = sorted(set(termos(pergunta)))
        if not ts:
            return []
        q = " OR ".join(f'"{t}"' for t in ts)
        sql = "SELECT texto, caminho, grupo, secao, bm25(ia_trecho) FROM ia_trecho WHERE ia_trecho MATCH ?"
        args = [q]
        if grupo:
            sql += " AND grupo=?"
            args.append(grupo)
        rs = self.db.execute(sql + " ORDER BY bm25(ia_trecho) LIMIT ?", (*args, k)).fetchall()
        return [{"texto": a, "caminho": b, "grupo": c, "secao": d, "nota": round(-e, 3)} for a, b, c, d, e in rs]

    def _df(self, termo: str) -> int:
        return self.db.execute("SELECT COUNT(*) FROM ia_trecho WHERE ia_trecho MATCH ?", (f'"{termo}"',)).fetchone()[0]   # texto ou seção

    def perguntar(self, pergunta: str, k: int = 6, grupo: str | None = None) -> dict:
        ts = set(termos(pergunta))
        n = self.db.execute("SELECT COUNT(*) FROM ia_trecho").fetchone()[0] or 1
        df = {t: self._df(t) for t in ts}
        ausentes = sorted(t for t, d in df.items() if d == 0)
        nao_sei = {"ok": True, "fontes": [], "confianca": 0.0, "revisao_humana": True,
                   "resposta": "Não encontrei isso nos documentos da Physis." + (f" Termos sem nenhum registro: {', '.join(ausentes)}." if ausentes else "")}
        if not ts or ausentes:            # pergunta com termo que a Physis nunca escreveu: não responde por aproximação
            return nao_sei
        peso = {t: math.log(1 + n / d) for t, d in df.items()}
        achados = self.buscar(pergunta, k, grupo)
        frases = []
        for i, a in enumerate(achados):
            da_secao = ts & set(termos(a["secao"]))
            bonus = sum(peso[t] for t in da_secao) * 0.5
            for f in re.split(r"(?<=[.!?;])\s+", a["texto"]):
                f = re.sub(r"[*`#>]+", "", f).strip(" -")
                proprios = ts & set(termos(f))
                cobre = proprios | da_secao
                if proprios and len(f.split()) >= 5:
                    frases.append((sum(peso[t] for t in cobre) + bonus, -i, f, i, len(cobre)))
        frases.sort(reverse=True)
        melhor = max((x[4] for x in frases), default=0)
        confianca = round(melhor / len(ts), 2)
        if not frases or (len(ts) > 1 and melhor < 2):
            return nao_sei
        usadas, linhas = [], []
        for _, _, f, i, _ in frases[:3]:
            if i not in usadas:
                usadas.append(i)
            linhas.append(f"{f} [{usadas.index(i) + 1}]")
        fontes = [{"n": n + 1, "fonte": _rel(achados[i]["caminho"]), "secao": achados[i]["secao"]} for n, i in enumerate(usadas)]
        return {"ok": True, "resposta": " ".join(linhas), "fontes": fontes, "confianca": confianca, "revisao_humana": True}

    # ---- temas (para os cursos) ----------------------------------------------------------------------------------
    def temas(self, prefixos: list[str], n: int = 15, min_docs: int = 2) -> list[dict]:
        """Termos e pares de termos presentes em pelo menos min_docs arquivos das pastas dadas, ordenados por TF-IDF."""
        docs = defaultdict(list)
        for texto, cam in self.db.execute("SELECT texto, caminho FROM ia_trecho"):
            if any(cam.startswith(str(p)) for p in prefixos):
                docs[cam].append(texto)
        if not docs:
            return []
        df, tf, onde = Counter(), Counter(), defaultdict(set)
        for cam, ts in docs.items():
            pal = termos(" ".join(ts))
            gramas = pal + [f"{a} {b}" for a, b in zip(pal, pal[1:]) if a != b]
            c = Counter(gramas)
            for g in c:
                df[g] += 1
                onde[g].add(cam)
            tf.update(c)
        total = len(docs)
        notas = []
        for g, d in df.items():
            if d < min_docs or (total > 3 and d > total / 2):     # termo em metade dos arquivos não distingue tema
                continue
            notas.append((tf[g] * math.log(1 + total / d) * (1.5 if " " in g else 1.0), g))
        notas.sort(reverse=True)
        out, cobertos = [], set()
        for nota, g in notas:
            if any(g in c or c in g for c in cobertos):
                continue
            cobertos.add(g)
            out.append({"tema": g, "arquivos": sorted(_rel(x) for x in onde[g]), "n_arquivos": len(onde[g]), "nota": round(nota, 1)})
            if len(out) >= n:
                break
        return out


def _rel(caminho: str) -> str:
    try:
        return str(Path(caminho).relative_to(RAIZ_REPO))
    except ValueError:
        return Path(caminho).name if len(caminho) > 120 else caminho


def bot_ia(mv) -> dict:
    """Atualiza o índice da IA Physis (só o que mudou)."""
    inicio = mv.nova_rodada()
    r = IAPhysis().indexar()
    for p in r["pastas_ausentes"]:
        mv.alertar("ia", "pasta", p, "info", f"Pasta de documentos não encontrada para a IA Physis: {p}",
                   "Definir PHYSIS_DOCS / PHYSIS_IA_PASTAS no servidor")
    mv.fechar_alertas_nao_vistos("ia", inicio)
    mv.registrar_execucao("ia", inicio, json.dumps(r, ensure_ascii=False))
    return r
