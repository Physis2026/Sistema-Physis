#!/usr/bin/env python3
r"""Tira de "projetos municipais" e põe em Editais (pedido da dona de 24/11/2026, ped59: "troca de pesquisa municipal").

    cd C:\physis\physis-ma-20261122-1bd599e\physis-hub
    py ..\ferramentas\municipais_para_editais.py             # só mostra o que seria movido (não muda nada)
    py ..\ferramentas\municipais_para_editais.py --aplicar   # move (copia o banco antes)

Contas (Clientes e projetos) com "municipal", "município", "prefeitura" ou "pesquisa municipal" no nome viram edital na aba Editais
(etapa triagem), levando anexos e pedidos; a conta é ARQUIVADA, não apagada. Projetos de tarefas com esses nomes, sem conta, ganham
um edital com o mesmo nome; as tarefas ficam onde estão e passam a citar o edital no projeto.
"""
from __future__ import annotations

import re
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "physis-hub"))
from physis_hub import mv_clientes, mv_editais  # noqa: E402
from physis_hub.mv import MV  # noqa: E402

RX = re.compile(r"munic[ií]p|prefeitura|pesquisa municipal", re.I)


def planejar(mv: MV) -> dict:
    cl = mv_clientes.Clientes(mv)
    contas = [c for c in cl.contas() if RX.search(c["nome"] or "") and c.get("estado") != "arquivada"]
    nomes_contas = {c["nome"] for c in cl.contas()}          # tarefas de conta seguem a conta (que vira edital)
    projetos = {}
    for tid, proj in mv.db.execute("SELECT id, projeto FROM mv_tarefa WHERE projeto<>'' AND estado<>'feita'").fetchall():
        if RX.search(proj or "") and proj not in nomes_contas and not proj.startswith("Edital · "):
            projetos.setdefault(proj, []).append(tid)
    return {"contas": [{"id": c["id"], "nome": c["nome"]} for c in contas], "projetos": {k: len(v) for k, v in projetos.items()}, "_tarefas": projetos}


def aplicar(mv: MV, plano: dict) -> dict:
    cl = mv_clientes.Clientes(mv); mv_editais.Editais(mv)
    feitos = [cl.para_edital(c["id"]) for c in plano["contas"]]
    cols = {r[1] for r in mv.db.execute("PRAGMA table_info(mv_edital)")}
    agora = time.time()
    for proj, tids in plano["_tarefas"].items():
        eid = "ed-" + re.sub(r"[^a-z0-9]+", "-", proj.lower()).strip("-")[:70]
        if not mv.db.execute("SELECT 1 FROM mv_edital WHERE id=?", (eid,)).fetchone():
            d = {"id": eid, "titulo": proj, "etapa": "triagem", "origem": f"projeto:{proj}", "motivo": "Movido de projetos municipais para Editais (24/11/2026)",
                 "proxima_acao": "Conferir financiador, prazo, valor e critérios ([MARCADOR] no que faltar)", "criado": agora, "atualizado": agora}
            d = {k: v for k, v in d.items() if k in cols}
            mv.db.execute(f"INSERT INTO mv_edital ({','.join(d)}) VALUES ({','.join('?' * len(d))})", list(d.values()))
        mv.db.executemany("UPDATE mv_tarefa SET projeto=? WHERE id=?", [(f"Edital · {proj}", t) for t in tids])
        feitos.append({"edital": eid, "tarefas": len(tids)})
    mv.db.commit()
    return {"movidos": feitos}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    mv = MV()
    try:
        p = planejar(mv)
        print("Contas que viram edital:", [c["nome"] for c in p["contas"]] or "nenhuma")
        print("Projetos de tarefas que ganham edital:", p["projetos"] or "nenhum")
        if "--aplicar" not in argv:
            print("Nada foi mudado. Para mover: --aplicar")
            return 0
        if mv.caminho != ":memory:":
            shutil.copy2(mv.caminho, mv.caminho.replace(".db", f"-antes-editais-{time.strftime('%Y%m%d-%H%M')}.db"))
        print(aplicar(mv, p))
    finally:
        mv.db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
