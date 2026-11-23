#!/usr/bin/env python3
r"""Desfaz a parte errada da limpeza de 23/11 (18h28): ela juntou tarefas de mesmo título de PESSOAS DIFERENTES.

    cd C:\physis\physis-ma-20261122-1bd599e
    py ferramentas\restaurar_por_pessoa.py            # SÓ MOSTRA
    py ferramentas\restaurar_por_pessoa.py --aplicar  # copia o banco e devolve as tarefas

Compara a cópia feita antes da limpeza (dados\backup-antes-limpeza-*.db, a mais antiga) com o banco de agora:
- tarefa da Gestão que sumiu e cuja "irmã" que ficou é de OUTRA pessoa → volta, como estava na cópia;
- tarefa que sumiu e tem irmã da MESMA pessoa → era repetida de verdade, continua fora;
- tarefa que ficou e virou "feita" só porque a de outra pessoa estava feita → volta ao estado da cópia.
O resto do banco (o que os robôs e você fizeram depois das 18h28) fica como está. Depois, a Gestão ao vivo
é lida de novo na próxima rodada (py -m physis_hub.mv_cli bots gestoes), já com a regra por pessoa.
"""
from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "physis-hub"))
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass
from physis_hub.mv import pasta_padrao  # noqa: E402
from physis_hub.mv_bots_extra import titulo_norm  # noqa: E402


def main(argv: list[str]) -> int:
    pasta = pasta_padrao()
    banco = pasta / "physis-mv.db"
    copias = sorted(pasta.glob("backup-antes-limpeza-*.db"))
    if not copias:
        print("Não há cópia de antes da limpeza: nada a desfazer.")
        return 0
    copia = copias[0]
    db = sqlite3.connect(banco, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("ATTACH DATABASE ? AS antes", (str(copia),))
    cols = [r[1] for r in db.execute("PRAGMA main.table_info(mv_tarefa)")]
    cols_antes = {r[1] for r in db.execute("PRAGMA antes.table_info(mv_tarefa)")}
    comuns = [c for c in cols if c in cols_antes]
    agora = {(titulo_norm(r["titulo"]), titulo_norm(r["responsavel"])): r["id"] for r in db.execute("SELECT id, titulo, responsavel FROM main.mv_tarefa")}
    por_titulo = {}
    for r in db.execute("SELECT id, titulo, responsavel, estado FROM main.mv_tarefa"):
        por_titulo.setdefault(titulo_norm(r["titulo"]), []).append(r)
    sumidas = db.execute("SELECT a.* FROM antes.mv_tarefa a WHERE a.id LIKE 'gestao:%' AND a.id NOT IN (SELECT id FROM main.mv_tarefa)").fetchall()
    voltam = []
    for r in sorted(sumidas, key=lambda x: (x["estado"] == "a_fazer", x["criado"])):     # 1 por pessoa: a começada/feita, senão a mais antiga
        k = (titulo_norm(r["titulo"]), titulo_norm(r["responsavel"]))
        if k not in agora:
            agora[k] = r["id"]
            voltam.append(r)
    # quem ficou "feita" só porque a tarefa de outra pessoa estava feita
    desfazer = []
    for r in sumidas:
        if r["estado"] != "feita":
            continue
        for q in por_titulo.get(titulo_norm(r["titulo"]), []):
            if titulo_norm(q["responsavel"]) == titulo_norm(r["responsavel"]) or q["estado"] != "feita":
                continue
            antes = db.execute("SELECT estado, concluida_em FROM antes.mv_tarefa WHERE id=?", (q["id"],)).fetchone()
            if antes and antes["estado"] != "feita":
                desfazer.append((q["id"], antes["estado"], antes["concluida_em"], q["titulo"], q["responsavel"]))
    desfazer = list({d[0]: d for d in desfazer}.values())
    print(f"Banco: {banco}\nCópia de antes da limpeza: {copia.name}")
    print(f"Tiradas pela limpeza (da Gestão): {len(sumidas)} · eram de outra pessoa e VOLTAM: {len(voltam)} · "
          f"repetidas de verdade (mesma pessoa), continuam fora: {len(sumidas) - len(voltam)}")
    print(f"Tarefas que viraram 'feita' por causa de outra pessoa e voltam ao estado anterior: {len(desfazer)}")
    for r in voltam[:8]:
        print(f"  volta: {r['titulo'][:70]}  ({r['responsavel'] or 'sem responsável'})")
    for d in desfazer[:5]:
        print(f"  estado volta a '{d[1]}': {d[3][:60]} ({d[4]})")
    if "--aplicar" not in argv:
        print("\nNada foi mudado. Para aplicar: py ferramentas\\restaurar_por_pessoa.py --aplicar")
        return 0
    seg = banco.with_name(f"backup-antes-restaurar-{time.strftime('%Y%m%d-%H%M')}.db")
    destino = sqlite3.connect(seg)
    db.execute("DETACH DATABASE antes")
    db.backup(destino)
    destino.close()
    db.execute("ATTACH DATABASE ? AS antes", (str(copia),))
    print(f"\nCópia do banco de agora: {seg}")
    lista = ",".join(comuns)
    for r in voltam:
        db.execute(f"INSERT OR IGNORE INTO main.mv_tarefa ({lista}) SELECT {lista} FROM antes.mv_tarefa WHERE id=?", (r["id"],))
    for tid, est, quando, _, _ in desfazer:
        db.execute("UPDATE main.mv_tarefa SET estado=?, concluida_em=? WHERE id=?", (est, quando, tid))
    db.execute("DELETE FROM main.mv_assinatura WHERE bot LIKE 'gestao:%'") if db.execute(
        "SELECT 1 FROM main.sqlite_master WHERE name='mv_assinatura'").fetchone() else None
    db.commit()
    db.execute("DETACH DATABASE antes")
    print(f"Voltaram: {len(voltam)} · estados corrigidos: {len(desfazer)} · tarefas agora: "
          f"{db.execute('SELECT COUNT(*) FROM mv_tarefa').fetchone()[0]} · integridade: {db.execute('PRAGMA integrity_check').fetchone()[0]}")
    print("Agora rode: py -m physis_hub.mv_cli bots gestoes   (dentro de physis-hub) para ler a Gestão de novo, por pessoa.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
