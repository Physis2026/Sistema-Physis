#!/usr/bin/env python3
r"""Ensaio da junção dos ramos de teste (23/11/2026) · roda no próprio computador, SEM mexer no que está no ar.

    cd C:\physis\physis-ma-20261122-1bd599e
    py ferramentas\ensaio_juncao.py

Cria duas cópias de trabalho novas (git worktree), cada uma num ramo novo "juncao-2026-11-23":
  C:\physis\juncao-sistema    = versão que roda (main) + teste/identidade-guia + teste/renderizacao-3d + teste/casa-gemeo-g0-g1
  C:\physis\juncao-instituto  = Instituto (main) + inovastem
Em cada uma: junta os ramos um a um; conflito só em arquivo GERADO (telas montadas, demos) usa a versão atual e
regenera no fim; conflito em arquivo de verdade é registrado (com o trecho) e aquele ramo fica de fora do ensaio.
Depois roda os geradores e TODOS os testes. Nada do que está no ar muda: nem pastas, nem banco, nem agenda.
O relatório fica em C:\physis\ensaio-juncao-AAAAMMDD-HHMM.md.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent          # instalação que roda
BASE = RAIZ.parent                                      # C:\physis
RAMO = "juncao-2026-11-23"
CERCA = "\x60\x60\x60"
GERADOS = ("physis-hub/web/painel.html", "demos/", "app-nativo/site/", "physis-hub/web/consultoria.html",
           "physis-hub/web/documento.html", "physis-hub/web/municipio.html", "physis-hub/physis-hub.db")
rel: list[str] = []
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass


def diz(t: str = "") -> None:
    print(t, flush=True)
    rel.append(t)


def run(cmd: list[str], cwd: Path, tempo: int = 3600, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=tempo, env={**os.environ, **(env or {})})


def git(cwd: Path, *a: str) -> subprocess.CompletedProcess:
    return run(["git", *a], cwd, 600)


def gerado(f: str) -> bool:
    return any(f == g or (g.endswith("/") and f.startswith(g)) for g in GERADOS)


def juntar(repo: Path, wt: Path, base: str, ramos: list[str], origem: Path | None) -> list[str]:
    if origem:                                        # traz os ramos de teste da outra pasta (só referências)
        for r in ramos:
            f = git(repo, "fetch", "-q", str(origem), f"+{r}:{r}")
            if f.returncode:
                diz(f"- ❌ não consegui trazer {r} de {origem}: {f.stderr.strip()[:200]}")
    if wt.exists():
        diz(f"- a pasta {wt} já existe: apague-a (ou renomeie) e rode de novo")
        return []
    w = git(repo, "worktree", "add", "-q", "-B", RAMO, str(wt), base)
    if w.returncode:
        diz(f"- ❌ não criei a cópia de trabalho: {w.stderr.strip()[:300]}")
        return []
    git(wt, "config", "user.name", "Ensaio de juncao")
    git(wt, "config", "user.email", "ensaio@localhost")
    ok = []
    for r in ramos:
        m = git(wt, "merge", "--no-ff", "--no-edit", "-m", f"Juncao (ensaio 23/11): {r}", r)
        if m.returncode == 0:
            diz(f"- ✅ {r}: juntou sem conflito")
            ok.append(r)
            continue
        conf = [l for l in git(wt, "diff", "--name-only", "--diff-filter=U").stdout.splitlines() if l]
        reais = [c for c in conf if not gerado(c)]
        if not conf:
            diz(f"- ❌ {r}: falhou sem conflito listado: {(m.stdout + m.stderr).strip()[:300]}")
            git(wt, "merge", "--abort")
            continue
        if not reais:
            for c in conf:
                git(wt, "checkout", "--ours", "--", c)
                git(wt, "add", "--", c)
            git(wt, "commit", "-q", "--no-edit")
            diz(f"- ✅ {r}: juntou; {len(conf)} arquivo(s) gerado(s) em conflito ficaram com a versão atual e serão regenerados")
            ok.append(r)
            continue
        diz(f"- ⚠️ {r}: CONFLITO em {len(reais)} arquivo(s) de verdade (ramo fica de fora do ensaio):")
        for c in reais[:15]:
            d = git(wt, "diff", "--", c).stdout
            diz(f"  - {c} ({d.count('<<<<<<<')} trecho(s) em conflito)")
            for bloco in d.split("<<<<<<<")[1:3]:
                diz("    " + CERCA)
                for ln in ("<<<<<<<" + bloco).splitlines()[:14]:
                    diz("    " + ln[:160])
                diz("    " + CERCA)
        git(wt, "merge", "--abort")
    return ok


def testes(wt: Path, rotulo: str) -> None:
    diz(f"\n### Geradores e testes · {rotulo}")
    for g in ("ferramentas/padronizar_paginas.py", "ferramentas/sincronizar.py", "ferramentas/embutir_bases.py", "demos/gerar_demos.py"):
        if (wt / g).is_file():
            p = run([sys.executable, g], wt, 1800)
            diz(f"- {g}: {'ok' if p.returncode == 0 else 'ERRO: ' + (p.stderr or p.stdout).strip()[-300:]}")
    hub = wt / "physis-hub"
    tmp = BASE / f"ensaio-dados-{rotulo}"
    tmp.mkdir(exist_ok=True)
    p = run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], hub, 3600,
            {"PHYSIS_MV_DADOS": str(tmp), "PHYSIS_DOCS": str(tmp / "docs"), "PYTHONIOENCODING": "utf-8"})
    linhas = (p.stderr or "").splitlines()
    fim = [l for l in linhas if l.startswith(("Ran ", "OK", "FAILED"))]
    diz(f"- testes: {' · '.join(fim[-2:]) or '?'}")
    for l in [l for l in linhas if l.startswith(("FAIL:", "ERROR:"))][:25]:
        diz(f"  - {l}")


def main() -> int:
    diz(f"# Ensaio da junção · {time.strftime('%d/%m/%Y %H:%M')}")
    diz("Nada do que está no ar foi mudado. Cópias de trabalho: C:\\physis\\juncao-sistema e C:\\physis\\juncao-instituto.")
    diz("\n## Sistema Physis (versão que roda + ramos de teste)")
    juntar(RAIZ, BASE / "juncao-sistema", "main", ["teste/identidade-guia", "teste/renderizacao-3d", "teste/casa-gemeo-g0-g1"],
           BASE / "physis-sistema")
    if (BASE / "juncao-sistema").exists():
        testes(BASE / "juncao-sistema", "sistema")
    diz("\n## Instituto Physis (main + inovastem)")
    juntar(BASE / "instituto-physis", BASE / "juncao-instituto", "main", ["inovastem"], None)
    if (BASE / "juncao-instituto").exists():
        testes(BASE / "juncao-instituto", "instituto")
    arq = BASE / f"ensaio-juncao-{time.strftime('%Y%m%d-%H%M')}.md"
    arq.write_text("\n".join(rel) + "\n", encoding="utf-8")
    print(f"\nRelatório: {arq}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
