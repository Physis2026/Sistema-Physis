"""Guarda sempre uma versão do Sistema Physis também na pasta Casa Physis e atualiza o Physis M&V (decisão de 18/11/2026).

    python ferramentas/documentos/salvar_casa_physis.py [arquivo.zip ...]

Faz duas coisas:
1. Atualiza o Physis M&V:
   - importa as tarefas da Gestão da Physis (documento 18, frente engineering);
   - importa as tarefas que foram para o Instituto (frente instituto), se o arquivo existir;
   - roda os bots (atrasos, documentos, resumo);
   - guarda uma cópia do banco do M&V. O banco vivo fica fora do OneDrive, porque a sincronização corrompe SQLite.
2. Copia os ZIPs dados (versão de envio, backup) para
   Casa Physis\\2_Desenvolvimento_Physis_Engineering\\Sistema_Physis_versoes.
   Guarda as 3 últimas de cada tipo e escreve um LEIA-ME com o SHA-256 de cada uma.

É chamado no fim de `emitir_entrega.py` e de `backup_arquivos.py`. Falhar aqui nunca desfaz a emissão: só avisa.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DOCS_PHYSIS = Path(os.environ.get("PHYSIS_DOCS", str(Path.home() / "OneDrive - Physis Engineering" / "Documents" / 'Sistema Physis')))
CASA = Path(os.environ.get("PHYSIS_CASA", str(Path.home() / "OneDrive - Physis Engineering" / "Documents" / 'Casa Physis')))
DESTINO = Path(os.environ.get("PHYSIS_CASA_VERSOES", str(CASA / "2_Desenvolvimento_Physis_Engineering" / "Sistema_Physis_versoes")))
TAREFAS_PHYSIS = DOCS_PHYSIS / "18_Checklist_para_importar_na_Gestao.json"
TAREFAS_INSTITUTO = CASA / "3_Instituto_Physis" / "Separado_do_Sistema_Physis_2026-11-18" / "codigo_extraido" / "gestao-tarefas-do-instituto.json"
MANTER = 3
# o banco vivo do M&V: fixo, para a emissão (que roda numa cópia limpa em outra pasta) achar o mesmo banco
os.environ.setdefault("PHYSIS_MV_DADOS", r"C:\physis\dados")


def _mv(*args: str) -> str:
    r = subprocess.run([sys.executable, "-m", "physis_hub.mv_cli", *args], cwd=RAIZ / "physis-hub",
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    if r.returncode:
        raise RuntimeError(f"mv_cli {' '.join(args)}: {(r.stderr or r.stdout).strip()[-400:]}")
    return r.stdout.strip()


def atualizar_mv() -> dict:
    out = {}
    if TAREFAS_PHYSIS.is_file():
        out["engineering"] = json.loads(_mv("importar", str(TAREFAS_PHYSIS), "--frente", "engineering"))
    if TAREFAS_INSTITUTO.is_file():
        out["instituto"] = json.loads(_mv("importar", str(TAREFAS_INSTITUTO), "--frente", "instituto"))
    _mv("bots", "atrasos", "documentos", "resumo")
    out["bots"] = "ok"
    banco = Path(os.environ["PHYSIS_MV_DADOS"]) / "physis-mv.db"
    if banco.is_file():
        (DESTINO / "mv").mkdir(parents=True, exist_ok=True)
        copia = DESTINO / "mv" / f"physis-mv_{datetime.datetime.now():%Y-%m-%d_%H%M}.db"
        with sqlite3.connect(banco) as src, sqlite3.connect(copia) as dst:
            src.backup(dst)   # cópia consistente, mesmo com o banco aberto
        _podar(DESTINO / "mv", "physis-mv_")
        out["banco_mv"] = str(copia)
    return out


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _tipo(nome: str) -> str:
    return "envio" if "_ENVIO_" in nome else "backup" if nome.startswith("sistema-physis-arquivos-") else re.sub(r"[\d_-]+\.zip$", "", nome)


def _podar(pasta: Path, prefixo: str) -> None:
    for velho in sorted((p for p in pasta.iterdir() if p.name.startswith(prefixo)), key=lambda p: p.stat().st_mtime)[:-MANTER]:
        velho.unlink()


def copiar(arquivos: list[Path]) -> list[Path]:
    DESTINO.mkdir(parents=True, exist_ok=True)
    feitos = []
    for a in arquivos:
        if not a.is_file():
            continue
        alvo = DESTINO / a.name
        shutil.copy2(a, alvo)
        feitos.append(alvo)
        t = _tipo(a.name)
        mesmos = [p for p in DESTINO.glob("*.zip") if _tipo(p.name) == t]
        for velho in sorted(mesmos, key=lambda p: p.stat().st_mtime)[:-MANTER]:
            velho.unlink()
    return feitos


def leia_me(mv: dict | None) -> None:
    linhas = ["# Sistema Physis · versões guardadas na Casa Physis", "",
              f"Atualizado em {datetime.datetime.now():%d/%m/%Y %H:%M}. Guardadas as {MANTER} últimas de cada tipo. "
              "O original fica em `Documents\\Sistema Physis\\_backup_arquivos`; o código, no GitHub.", "",
              "| Arquivo | Tamanho | SHA-256 |", "|---|---|---|"]
    for p in sorted(DESTINO.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
        linhas.append(f"| {p.name} | {p.stat().st_size / 2**20:.1f} MB | `{_sha(p)}` |")
    if mv:
        linhas += ["", "## Physis M&V", "",
                   "Tarefas da Gestão da Physis (frente engineering) e do Instituto (frente instituto) importadas; bots rodados.",
                   "Cópia do banco do M&V em `mv\\` (abrir só a cópia; o banco vivo fica em `C:\\physis\\dados`).", "",
                   "```", json.dumps(mv, ensure_ascii=False, indent=1)[:4000], "```"]
    (DESTINO / "LEIA-ME.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def salvar(arquivos: list[Path] | None = None) -> None:
    """Uso pelos outros scripts: nunca levanta erro, só avisa."""
    mv = None
    try:
        mv = atualizar_mv()
        print("M&V atualizado:", {k: (v.get("importadas") if isinstance(v, dict) else v) for k, v in mv.items()})
    except Exception as e:  # noqa: BLE001
        print(f"AVISO: M&V não foi atualizado ({e})")
    try:
        feitos = copiar(list(arquivos or []))
        leia_me(mv)
        for f in feitos:
            print(f"cópia na Casa Physis: {f}")
    except Exception as e:  # noqa: BLE001
        print(f"AVISO: cópia na Casa Physis falhou ({e})")


if __name__ == "__main__":
    salvar([Path(x) for x in sys.argv[1:]])
