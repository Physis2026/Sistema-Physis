#!/usr/bin/env python3
"""Banco da modelagem: copia um IFC para SQLite (uma tabela por tipo de elemento) e registra a revisão.

    python ferramentas/ifc_para_sqlite.py modelo.ifc [modelo.sqlite] [--sem-geometria]

Decisão da dona de 22/11/2026 (M&A pg:36f2ad6f5402): o IFC continua sendo a fonte; cada revisão vira um SQLite que o
servidor da Physis, o Planejador, o gêmeo e o M&A podem consultar sem programa extra (o sqlite3 já vem no Python).
A conversão usa o IfcOpenShell (LGPL, aberto; receita Ifc2Sql do ifcpatch). Ele é opcional e só precisa estar onde a
conversão roda: `python -m pip install --user ifcopenshell ifcpatch`. O servidor continua sem dependências.

Tabelas: as do Ifc2Sql (uma por classe IFC, mais propriedades e geometria) e `physis_revisao`, com o nome do arquivo,
o SHA-256 do IFC, o esquema, a data da conversão e a contagem por classe. Converter de novo o mesmo arquivo não duplica
(o SHA-256 é a chave); um IFC novo gera um SQLite novo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from collections import Counter
from contextlib import closing
from pathlib import Path


def converter(ifc: Path, saida: Path, geometria: bool = True) -> dict:
    try:
        import ifcopenshell
        from ifcpatch.recipes import Ifc2Sql
    except ImportError as e:
        raise SystemExit(2) from e
    sha = hashlib.sha256(ifc.read_bytes()).hexdigest()
    if saida.exists():
        with closing(sqlite3.connect(saida)) as db:
            try:
                r = db.execute("SELECT sha256 FROM physis_revisao").fetchone()
            except sqlite3.OperationalError:
                r = None
        if r and r[0] == sha:
            return {"sqlite": str(saida), "sha256": sha, "ja_existia": True}
        saida.unlink()
    f = ifcopenshell.open(str(ifc))
    t = time.time()
    p = Ifc2Sql.Patcher(f, sql_type="SQLite", database=str(saida), should_get_geometry=geometria, should_skip_geometry_data=not geometria)
    p.patch()
    for x in (getattr(p, "c", None), getattr(p, "db", None)):   # sem geometria o Ifc2Sql não fecha a conexão (trava no Windows)
        try:
            x.close()
        except Exception:  # noqa: BLE001 (já fechada)
            pass
    criado = Path(p.get_output()) if hasattr(p, "get_output") and isinstance(p.get_output(), str) else saida
    if criado != saida and criado.exists():
        criado.replace(saida)
    contagem = dict(Counter(e.is_a() for e in f.by_type("IfcProduct")).most_common())
    with closing(sqlite3.connect(saida)) as db, db:
        db.execute("CREATE TABLE IF NOT EXISTS physis_revisao (arquivo TEXT, sha256 TEXT PRIMARY KEY, esquema TEXT, convertido TEXT, contagem TEXT)")
        db.execute("INSERT OR REPLACE INTO physis_revisao VALUES (?,?,?,?,?)",
                   (ifc.name, sha, f.schema, time.strftime("%Y-%m-%dT%H:%M:%S"), json.dumps(contagem, ensure_ascii=False)))
    return {"sqlite": str(saida), "sha256": sha, "esquema": f.schema, "pecas": sum(contagem.values()),
            "segundos": round(time.time() - t, 1), "ja_existia": False}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ifc")
    ap.add_argument("sqlite", nargs="?")
    ap.add_argument("--sem-geometria", action="store_true", help="só dados (classes, atributos, propriedades); arquivo menor")
    a = ap.parse_args(argv)
    ifc = Path(a.ifc)
    if not ifc.is_file():
        ap.error("IFC não encontrado: " + a.ifc)
    saida = Path(a.sqlite) if a.sqlite else ifc.with_suffix(".sqlite")
    try:
        r = converter(ifc, saida, geometria=not a.sem_geometria)
    except SystemExit:
        print("IfcOpenShell não instalado: python -m pip install --user ifcopenshell ifcpatch", file=sys.stderr)
        return 2
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
