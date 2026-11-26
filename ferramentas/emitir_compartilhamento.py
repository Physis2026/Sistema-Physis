#!/usr/bin/env python3
r"""Emite o pacote de COMPARTILHAMENTO com a equipe só depois de todos os testes (26/11/2026).

    cd C:\physis\physis-ma-20261122-1bd599e
    py ferramentas\emitir_compartilhamento.py --saida C:\physis\compartilhar-2026-11-26
    py ferramentas\emitir_compartilhamento.py --saida ... --rapido     # pula a suíte completa (só para ensaio)

Ordem: (1) suíte completa de testes; (2) kits por módulo (gerar_kits_revisao); (3) testes de cada kit: zip íntegro,
manifesto SHA-256 igual, LEIA-ME e FICHA presentes, HTML que abre sem internet, nenhum segredo; (4) páginas HTML para
visualização (demos) com as mesmas conferências; (5) zips por pessoa (kits_por_pessoa) conferidos contra o mapa de
responsáveis; (6) relatório. Se qualquer teste FALHAR, nada é marcado como pronto: o relatório diz o que corrigir.
Saída: <saida>/por-pessoa/<Nome>.zip, <saida>/paginas.zip, <saida>/INDICE.md e <saida>/RELATORIO-TESTES.md.
Só a biblioteca padrão. Não muda o repositório.
"""
from __future__ import annotations
import argparse, hashlib, html.parser, json, re, subprocess, sys, time, zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PY = sys.executable
SEGREDO = re.compile(r"(?i)(senha|password|passwd|token|api[_-]?key|secret)\s*[:=]\s*['\"][^'\"\s]{6,}['\"]|-----BEGIN [A-Z ]*PRIVATE KEY-----|ghp_[A-Za-z0-9]{20,}")
PROIBIDOS = re.compile(r"(?i)(^|/)(secrets\.h|\.env|senha[^/]*\.txt|.*\.db|.*\.sqlite3?)$")
EXTERNO = re.compile(r"""<(script|link|img|iframe)[^>]+(src|href)\s*=\s*["']https?://""", re.I)
L: list[str] = []; F = [0]; A = [0]


def ok(t): L.append("- [ OK  ] " + t)
def av(t): L.append("- [AVISO] " + t); A[0] += 1
def fa(t): L.append("- [FALHA] " + t); F[0] += 1


class _P(html.parser.HTMLParser):
    def __init__(s): super().__init__(); s.h1 = 0; s.titulo = False
    def handle_starttag(s, tag, a):
        if tag == "h1": s.h1 += 1
        if tag == "title": s.titulo = True


def conferir_html(nome: str, texto: str, barra: bool = False) -> None:
    p = _P()
    try:
        p.feed(texto)
    except Exception as e:  # noqa: BLE001
        fa(f"{nome}: HTML não lê ({type(e).__name__})"); return
    if not p.titulo: av(f"{nome}: sem <title>")
    if EXTERNO.search(texto): fa(f"{nome}: carrega arquivo da internet (regra: telas sem internet)")
    if barra and "physis-preferencias" not in texto and "pxp-barra" not in texto and "PxPref" not in texto: av(f"{nome}: sem a barra de preferências")


def conferir_segredos(nome: str, dados: bytes) -> None:
    if len(dados) > 5_000_000: return
    try:
        t = dados.decode("utf-8")
    except UnicodeDecodeError:
        return
    if re.search(r"(^|/)tests?/|\.example\.|exemplo", nome):   # senhas falsas de teste e modelos de exemplo
        return
    m = SEGREDO.search(t)
    if m and re.fullmatch(r"['\"][A-Z0-9_]+['\"]", m.group(0).split("=")[-1].split(":")[-1].strip()):
        return                                                    # marcador em maiúsculas (SENHA_DA_REDE)
    if m and "[MARCADOR" not in t[max(0, m.start() - 80):m.end() + 80]:
        fa(f"{nome}: parece ter segredo ('{m.group(0)[:30]}…'): tire antes de compartilhar")


def conferir_zip(z: Path, manifesto: dict | None = None) -> int:
    try:
        with zipfile.ZipFile(z) as zz:
            ruim = zz.testzip()
            if ruim: fa(f"{z.name}: arquivo corrompido dentro ({ruim})"); return 0
            nomes = zz.namelist()
            for n in nomes:
                if PROIBIDOS.search(n): fa(f"{z.name}: arquivo que não pode sair: {n}")
                if n.endswith((".html", ".htm")): conferir_html(f"{z.name}:{n}", zz.read(n).decode("utf-8", "replace"))
                if n.endswith((".md", ".json", ".js", ".py", ".html", ".txt", ".csv", ".ini", ".yaml", ".yml")): conferir_segredos(f"{z.name}:{n}", zz.read(n))
            if manifesto:
                arqs = manifesto.get("arquivos") or {}
                itens = arqs.items() if isinstance(arqs, dict) else ((a.get("caminho") or a.get("arquivo"), a.get("sha256")) for a in arqs)
                for cam, sha in itens:
                    if not cam or not sha: continue
                    alvo = [n for n in nomes if n.endswith("/" + cam) or n == cam]
                    if not alvo: fa(f"{z.name}: falta {cam} do manifesto"); continue
                    if hashlib.sha256(zz.read(alvo[0])).hexdigest() != sha: fa(f"{z.name}: {cam} difere do manifesto")
                if not any(n.endswith("LEIA-ME.md") for n in nomes): fa(f"{z.name}: sem LEIA-ME.md")
                if not any(n.endswith("FICHA_REVISAO.md") for n in nomes): fa(f"{z.name}: sem FICHA_REVISAO.md")
            return len(nomes)
    except zipfile.BadZipFile:
        fa(f"{z.name}: não é zip válido"); return 0


def documentos_gerados(saida: Path, base: Path) -> tuple[Path, int]:
    """Primeira versão dos documentos gerados pelo sistema (tabela docauto de cada banco: hub e instalações em <base>/clientes).
    Versão 1 vai como está; documento já revisado (versão > 1) vai na versão atual com o aviso no índice (a primeira não fica
    guardada no banco). Arquivo gerado (ODT/PDF) quando existe; senão o texto."""
    import sqlite3
    dbs = sorted(base.glob("physis-ma-*/physis-hub/*.db")) + sorted(p for p in (base / "clientes").glob("physis-*/*.db") if ".antiga-" not in str(p) and ".falhou-" not in str(p))
    z = saida / "documentos.zip"; n = 0; idx = ["# Documentos gerados pelo sistema (primeira versão)", "", "| Plataforma | Documento | Tipo | Versão | Situação |", "|---|---|---|---|---|"]
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zz:
        for db in dbs:
            plat = db.parent.name.replace("physis-", "") if db.parent.name != "physis-hub" else "hub"
            try:
                con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
                try:   # a 1ª versão guardada antes da edição (docauto_v1), quando existe
                    linhas = con.execute("SELECT d.id, d.tipo, COALESCE(v.titulo, d.titulo), d.estado, COALESCE(v.texto, d.texto), "
                                         "CASE WHEN v.doc_id IS NULL THEN d.arquivo ELSE v.arquivo END, CASE WHEN v.doc_id IS NULL THEN d.versao ELSE 1 END "
                                         "FROM docauto d LEFT JOIN docauto_v1 v ON v.doc_id=d.id ORDER BY d.criado_em").fetchall()
                except sqlite3.Error:
                    linhas = con.execute("SELECT id, tipo, titulo, estado, texto, arquivo, versao FROM docauto ORDER BY criado_em").fetchall()
                con.close()
            except sqlite3.Error:
                continue
            for i, tipo, tit, est, texto, arq, ver in linhas:
                nome = re.sub(r"[^\w.-]+", "_", f"{tit}")[:80] or i
                if arq:
                    ext = ".pdf" if bytes(arq[:4]) == b"%PDF" else ".odt" if bytes(arq[:2]) == b"PK" else ".bin"
                    zz.writestr(f"documentos/{plat}/{nome}_v{ver}{ext}", bytes(arq))
                zz.writestr(f"documentos/{plat}/{nome}_v{ver}.txt", texto or "")
                idx.append(f"| {plat} | {tit} | {tipo} | {ver}{'' if ver == 1 else ' (a 1ª não fica guardada: esta é a atual)'} | {est} |"); n += 1
        zz.writestr("documentos/INDICE.md", "\n".join(idx) + "\n")
    return z, n


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--saida", required=True); ap.add_argument("--rapido", action="store_true"); ap.add_argument("--base", default="")
    a = ap.parse_args(); s = Path(a.saida); s.mkdir(parents=True, exist_ok=True); dia = time.strftime("%Y-%m-%d")
    L.append(f"# Testes antes de compartilhar · {time.strftime('%d/%m/%Y %H:%M')}"); L.append("")
    L.append("## 1. Suíte de testes")
    if a.rapido:
        av("suíte pulada (--rapido): NÃO compartilhe este resultado")
    else:
        r = subprocess.run([PY, "-W", "ignore", "-m", "unittest", "discover", "-s", "tests"], cwd=RAIZ / "physis-hub", capture_output=True, text=True, encoding="utf-8", errors="replace")
        fim = [l for l in (r.stderr + r.stdout).splitlines() if l.startswith(("Ran ", "OK", "FAILED"))]
        (ok if r.returncode == 0 else fa)("suíte: " + " · ".join(fim[-2:]))
        if r.returncode: (s / "testes-suite.log").write_text(r.stderr + r.stdout, encoding="utf-8")
    L.append(""); L.append("## 2. Kits por módulo")
    kits = s / "kits"
    r = subprocess.run([PY, str(RAIZ / "ferramentas" / "gerar_kits_revisao.py"), "--saida", str(kits), "--data", dia], capture_output=True, text=True, encoding="utf-8", errors="replace")
    (ok if r.returncode == 0 else fa)("kits gerados" if r.returncode == 0 else "gerar_kits_revisao falhou: " + (r.stderr or r.stdout)[-300:])
    mods = json.loads((RAIZ / "ferramentas" / "kits" / "modulos.json").read_text(encoding="utf-8"))["modulos"]
    L.append(""); L.append("## 3. Testes de cada kit")
    for m in mods:
        z = kits / f"kit-{m['id']}-{dia}.zip"
        if not z.is_file(): fa(f"kit {m['id']}: zip não gerado"); continue
        man = kits / "_manifestos" / f"kit-{m['id']}-{dia}.json"
        manifesto = json.loads(man.read_text(encoding="utf-8")) if man.is_file() else None
        if manifesto is None: av(f"kit {m['id']}: sem manifesto guardado")
        if not m.get("responsaveis"): av(f"kit {m['id']}: sem responsável (vai para _sem-responsavel)")
        n = conferir_zip(z, manifesto)
        if n: ok(f"kit {m['id']} · {n} arquivos · {z.stat().st_size // 1024} kB · {', '.join(m.get('responsaveis') or ['—'])}")
    L.append(""); L.append("## 4. Páginas para visualização (HTML)")
    pags = sorted((RAIZ / "demos").glob("*.html"))
    with zipfile.ZipFile(s / "paginas.zip", "w", zipfile.ZIP_DEFLATED) as zz:
        idx = ["<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Páginas Physis para visualização</title></head><body><main><h1>Páginas Physis para visualização</h1><p>Abra no navegador, sem internet. Versão de demonstração: dados fictícios.</p><ul>"]
        for pg in pags:
            t = pg.read_text(encoding="utf-8"); conferir_html(pg.name, t, barra=True); conferir_segredos(pg.name, t.encode("utf-8"))
            zz.write(pg, "paginas/" + pg.name); idx.append(f"<li><a href='{pg.name}'>{pg.stem.replace('physis-demo-', '').replace('-', ' ')}</a></li>")
        idx.append("</ul></main></body></html>"); zz.writestr("paginas/index.html", "".join(idx))
    n = conferir_zip(s / "paginas.zip"); ok(f"paginas.zip · {len(pags)} páginas + índice · {(s / 'paginas.zip').stat().st_size // 1024} kB") if n else None
    L.append(""); L.append("## 4b. Documentos gerados pelo sistema (primeira versão)")
    zdoc, ndoc = documentos_gerados(s, Path(a.base) if a.base else RAIZ.parent)
    if conferir_zip(zdoc) or ndoc == 0:
        (ok if ndoc else av)(f"documentos.zip · {ndoc} documento(s)" if ndoc else "nenhum documento gerado pelo sistema ainda (documentos.zip só com o índice)")
    L.append(""); L.append("## 5. Zips por pessoa")
    r = subprocess.run([PY, str(RAIZ / "ferramentas" / "kits_por_pessoa.py"), "--saida", str(kits)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode: fa("kits_por_pessoa falhou: " + r.stderr[-300:])
    pp = kits / "por-pessoa"; esperado = {}
    for m in mods:
        for p in (m.get("responsaveis") or ["_sem-responsavel"]): esperado.setdefault(p, set()).add(f"kit-{m['id']}-{dia}.zip")
    for p, kz in sorted(esperado.items()):
        nome = re.sub(r"[^\w.-]+", "-", p).strip("-")
        z = pp / f"{nome}.zip"
        if not z.is_file(): fa(f"{p}: zip da pessoa não gerado"); continue
        with zipfile.ZipFile(z) as zz:
            tem = set(zz.namelist())
        falta, sobra = kz - tem, tem - kz
        if falta: fa(f"{p}: faltam {sorted(falta)}")
        if sobra: fa(f"{p}: kits de outra pessoa {sorted(sobra)}")
        if not falta and not sobra and conferir_zip(z): ok(f"{p}: {len(kz)} kit(s) · {z.stat().st_size // 1048576} MB")
    L.append(""); L.append(f"**Resultado: {F[0]} falha(s), {A[0]} aviso(s).** " + ("NÃO compartilhe: corrija as falhas e rode de novo." if F[0] else "Ensaio (--rapido): rode sem --rapido antes de compartilhar." if a.rapido else "Pode compartilhar: por-pessoa/<Nome>.zip para cada pessoa, paginas.zip e documentos.zip para todos."))
    (s / "RELATORIO-TESTES.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    if (pp / "INDICE.md").is_file(): (s / "INDICE.md").write_text((pp / "INDICE.md").read_text(encoding="utf-8"), encoding="utf-8")
    print("\n".join(L)); print("Relatório:", s / "RELATORIO-TESTES.md")
    return 1 if F[0] else (2 if a.rapido else 0)


if __name__ == "__main__":
    raise SystemExit(main())
