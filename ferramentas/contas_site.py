#!/usr/bin/env python3
r"""Contas de cada site (Gestão 8703, Casa 8701, InovaSTEM 8702, Hub 8700) · 23/11/2026.

Cada site tem as PRÓPRIAS contas: a conta criada na Gestão não vale na Casa, e vice-versa.

    cd C:\physis\physis-ma-20261122-1bd599e
    py ferramentas\contas_site.py listar                       # só lê: usuários e papéis de cada site
    py ferramentas\contas_site.py senha casa rafaella          # define uma senha nova (pede a senha; não aparece na tela)

Sites: gestao (physis-physis-site), casa (physis-casa-physis-inicial), inovastem (physis-inovastem), hub (physis-hub do sistema).
A senha nova segue a mesma regra do site (mínimo de 12 caracteres, sem senha comum) e encerra as sessões abertas daquela conta.
"""
from __future__ import annotations

import getpass
import os
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE = RAIZ.parent
sys.path.insert(0, str(RAIZ / "physis-hub"))
from physis_hub import seguranca as seg  # noqa: E402
from physis_hub.hub import Hub  # noqa: E402

SITES = {"gestao": BASE / "clientes" / "physis-physis-site", "casa": BASE / "clientes" / "physis-casa-physis-inicial",
         "inovastem": BASE / "clientes" / "physis-inovastem", "hub": RAIZ / "physis-hub"}


def bancos(pasta: Path) -> list[Path]:
    out = []
    for b in sorted(pasta.glob("*.db")):
        try:
            con = sqlite3.connect(f"file:{b}?mode=ro", uri=True)
            if con.execute("SELECT 1 FROM sqlite_master WHERE name='conta'").fetchone():
                out.append(b)
            con.close()
        except sqlite3.Error:
            pass
    return out


def listar() -> None:
    for nome, pasta in SITES.items():
        bs = bancos(pasta) if pasta.is_dir() else []
        if not bs:
            print(f"{nome}: sem banco com contas ({pasta}) → na primeira abertura o site pede para criar a conta de administração")
            continue
        for b in bs:
            con = sqlite3.connect(f"file:{b}?mode=ro", uri=True)
            linhas = con.execute("SELECT usuario, nome, papel FROM conta ORDER BY id").fetchall()
            con.close()
            print(f"{nome} ({b.name}): " + (", ".join(f"{u} ({n}, {p})" for u, n, p in linhas) or "nenhuma conta ainda → a primeira abertura cria a de administração"))


def senha(site: str, usuario: str) -> int:
    pasta = SITES.get(site)
    bs = bancos(pasta) if pasta and pasta.is_dir() else []
    if not bs:
        print(f"Site '{site}' sem banco de contas.")
        return 1
    con = sqlite3.connect(bs[0], timeout=30)
    r = con.execute("SELECT id FROM conta WHERE usuario=?", (usuario,)).fetchone()
    if not r:
        print(f"Usuário '{usuario}' não existe em {site}. Rode 'listar' para ver os usuários.")
        return 1
    nova = getpass.getpass("Senha nova (mínimo 12 caracteres): ")
    if nova != getpass.getpass("Repita a senha nova: "):
        print("As duas senhas não são iguais. Nada foi mudado.")
        return 1
    erro = seg.senha_fraca(nova, usuario)
    if erro:
        print("Senha recusada:", erro)
        return 1
    sal = os.urandom(16)
    resumo = Hub._resumir(nova, sal)                    # o mesmo resumo do site (PBKDF2-SHA256)
    con.execute("UPDATE conta SET sal=?, resumo=? WHERE id=?", (sal, resumo, r[0]))
    con.execute("DELETE FROM sessao WHERE conta=?", (r[0],))
    con.commit()
    con.close()
    print(f"Senha de '{usuario}' em {site} trocada. Entre de novo no site.")
    return 0


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["listar"]:
        listar()
    elif len(a) == 3 and a[0] == "senha":
        sys.exit(senha(a[1], a[2]))
    else:
        print(__doc__)
