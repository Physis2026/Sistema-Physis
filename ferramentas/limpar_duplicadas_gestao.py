#!/usr/bin/env python3
r"""Tarefas repetidas que a Gestão ao vivo trouxe para o M&A (23/11/2026).

    cd C:\physis\physis-ma-20261122-1bd599e
    py ferramentas\limpar_duplicadas_gestao.py            # SÓ MOSTRA (não muda nada)
    py ferramentas\limpar_duplicadas_gestao.py --aplicar  # faz cópia do banco e tira as repetidas

Repetida = tarefa vinda da Gestão (id gestao:...) com o mesmo título E o mesmo responsável de outra tarefa.
Fica uma: a que não veio da Gestão; senão a já começada ou feita; senão a mais antiga. Se alguma estava feita, a que fica vira feita.
Quem dependia da repetida passa a depender da que fica. Antes de mudar, copia o banco para
dados\backup-antes-limpeza-AAAAMMDD-HHMM.db (para voltar, é só copiar de volta com o M&A fechado).
"""
from __future__ import annotations

import json
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
    banco = pasta_padrao() / "physis-mv.db"
    db = sqlite3.connect(banco, timeout=30)
    # grupos de mesmo título; fica: a tarefa que não veio da Gestão; senão a da Gestão já começada/feita; senão a mais antiga.
    # Só tarefas da Gestão (id gestao:...) são tiradas; as de outros robôs e as manuais nunca.
    grupos = {}
    # mesma tarefa = mesmo título E mesmo responsável (a Gestão é individual: a mesma tarefa de duas pessoas não é repetida)
    for tid, tit, est, quando, criado, resp in db.execute("SELECT id, titulo, estado, concluida_em, criado, responsavel FROM mv_tarefa"):
        grupos.setdefault((titulo_norm(tit), titulo_norm(resp)), []).append((tid, tit, est, quando, criado))
    pares = []
    for g in grupos.values():
        if len(g) < 2 or not any(x[0].startswith("gestao:") for x in g):
            continue
        g.sort(key=lambda x: (x[0].startswith("gestao:"), x[2] == "a_fazer", x[4]))
        fica = g[0][0]
        for tid, tit, est, quando, _ in g[1:]:
            if tid.startswith("gestao:"):
                pares.append((tid, fica, tit, est, quando))
    total = db.execute("SELECT COUNT(*) FROM mv_tarefa").fetchone()[0]
    print(f"Banco: {banco}")
    print(f"Tarefas: {total} · repetidas vindas da Gestão: {len(pares)} · ficariam: {total - len(pares)}")
    for tid, alvo, tit, est, _ in pares[:10]:
        print(f"  - {tit[:80]}  ({tid} -> fica {alvo}{', feita' if est == 'feita' else ''})")
    if "--aplicar" not in argv:
        print("\nNada foi mudado. Para aplicar: py ferramentas\\limpar_duplicadas_gestao.py --aplicar")
        return 0
    copia = banco.with_name(f"backup-antes-limpeza-{time.strftime('%Y%m%d-%H%M')}.db")
    dest = sqlite3.connect(copia)
    db.backup(dest)
    dest.close()
    print(f"\nCópia do banco: {copia}")
    troca = {tid: alvo for tid, alvo, *_ in pares}
    for tid, alvo, _, est, quando in pares:
        if est == "feita":
            db.execute("UPDATE mv_tarefa SET estado='feita', concluida_em=COALESCE(concluida_em, ?) WHERE id=? AND estado<>'feita'",
                       (quando, alvo))
    for tid, dep in db.execute("SELECT id, depende_de FROM mv_tarefa").fetchall():
        lst = json.loads(dep or "[]")
        novo = list(dict.fromkeys(troca.get(d, d) for d in lst if troca.get(d, d) != tid))
        if novo != lst:
            db.execute("UPDATE mv_tarefa SET depende_de=? WHERE id=?", (json.dumps(novo), tid))
    db.executemany("DELETE FROM mv_tarefa WHERE id=?", [(t,) for t in troca])
    db.commit()
    ok = db.execute("PRAGMA integrity_check").fetchone()[0]
    print(f"Tiradas: {len(troca)} · tarefas agora: {db.execute('SELECT COUNT(*) FROM mv_tarefa').fetchone()[0]} · integridade: {ok}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
