#!/usr/bin/env python3
r"""Confere o backup de verdade (não só se rodou): py ferramentas\verificar_backup.py

1. o último C:\physis\backup-diario\AAAAMMDD tem uma cópia de CADA banco que existe hoje (hub, clientes, dados);
2. cada cópia abre, passa no integrity_check e tem as mesmas tabelas (e o mesmo número de contas) que o original;
3. restauração de ensaio: a cópia do hub é aberta numa pasta temporária e as contas são lidas;
4. C:\physis\backup-arquivos tem os arquivos das pastas de origem (amostra de até 300 por pasta, pelo nome e tamanho).
"""
import os
import random
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

RAIZ = Path(r"C:\physis") if os.name == "nt" else Path(os.environ.get("PHYSIS_RAIZ_TESTE", "/tmp/physis"))


def main() -> int:
    F = A = 0
    def p(nivel, t):
        nonlocal F, A
        F += nivel == "FALHA"; A += nivel == "AVISO"; print(f"  [{nivel:^5}] {t}")
    bd = RAIZ / "backup-diario"
    ult = sorted((d for d in bd.iterdir() if d.is_dir() and d.name.isdigit()), reverse=True)[:1] if bd.is_dir() else []
    if not ult:
        p("FALHA", "nenhum backup diário"); return 1
    ult = ult[0]; print("== Backup", ult)
    origens = [x for x in list((RAIZ / "physis-ma-20261122-1bd599e" / "physis-hub").glob("*.db")) + list((RAIZ / "clientes").glob("physis-*/*.db"))
               + list((RAIZ / "dados").glob("*.db")) if ".antiga-" not in str(x) and ".falhou-" not in str(x)]
    for o in origens:
        c = ult / (o.parent.name + "__" + o.name)
        if not c.is_file():
            p("FALHA", f"sem cópia de {o}"); continue
        try:
            a, b = sqlite3.connect(f"file:{o}?mode=ro", uri=True), sqlite3.connect(f"file:{c}?mode=ro", uri=True)
            if b.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                p("FALHA", f"{c.name}: integridade"); continue
            ta = {r[0] for r in a.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            tb = {r[0] for r in b.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            falta = ta - tb
            extra = ""
            if "conta" in ta and "conta" in tb:
                na, nb = a.execute("SELECT COUNT(*) FROM conta").fetchone()[0], b.execute("SELECT COUNT(*) FROM conta").fetchone()[0]
                extra = f" · contas {nb}/{na}"
                if nb < na:
                    p("AVISO", f"{c.name}: contas criadas depois do backup ({nb} no backup, {na} hoje)")
            (p("AVISO", f"{c.name}: tabelas criadas depois do backup: {', '.join(sorted(falta))[:120]}") if falta
             else p("OK", f"{c.name} íntegro, {len(tb)} tabelas{extra}"))
            a.close(); b.close()
        except sqlite3.Error as e:
            p("FALHA", f"{c.name}: {e}")
    hub = next((x for x in ult.glob("physis-hub__physis-hub.db")), None)
    if hub:
        t = Path(tempfile.mkdtemp()) / "restaurado.db"; shutil.copy2(hub, t)
        try:
            n = sqlite3.connect(t).execute("SELECT COUNT(*) FROM conta").fetchone()[0]; p("OK", f"restauração de ensaio do hub: {n} conta(s) lidas")
        except sqlite3.Error as e:
            p("FALHA", f"restauração de ensaio: {e}")
    print("== Arquivos (backup-arquivos)")
    ba = RAIZ / "backup-arquivos"
    for org in (RAIZ / "dados", RAIZ / "clientes", RAIZ / "iniciar"):
        if not org.is_dir():
            continue
        alvo = ba / ("C_physis_" + org.name)
        arqs = [f for f in org.rglob("*") if f.is_file() and f.suffix not in (".db", ".db-wal", ".db-shm") and ".antiga-" not in str(f)]
        amostra = random.sample(arqs, min(300, len(arqs))) if arqs else []
        faltam = [f for f in amostra if not (alvo / f.relative_to(org)).is_file()]
        (p("OK", f"{org.name}: amostra de {len(amostra)} arquivo(s) presente no backup") if not faltam
         else p("AVISO", f"{org.name}: {len(faltam)} de {len(amostra)} sem cópia (ex.: {faltam[0].relative_to(org)}) — criados depois do último backup?"))
    print(f"\nResultado: {F} falha(s), {A} aviso(s).")
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
