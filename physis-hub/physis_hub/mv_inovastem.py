"""Bot InovaSTEM no M&A (25/11/2026: "mensagens enviadas não estão sendo alertadas em local nenhum").

Lê SÓ PARA LEITURA o banco da InovaSTEM (PHYSIS_INOVASTEM_BANCO; padrão C:\physis\clientes\physis-inovastem\physis-inovastem.db) e
vira alerta no M&A tudo o que chegou desde a última rodada: projetos e desafios, cadastros de interesse, pedidos de impressão,
tópicos e mensagens do fórum. Nada de e-mail ou nome de quem mandou: só o tipo e o título. O site da InovaSTEM também mostra
os avisos para a equipe (Avisos novos, no alto de qualquer aba).
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[2]
CONSULTAS = (("proposta", "SELECT tipo, titulo, criado FROM ino_proposta WHERE criado>? AND estado<>'removido'"),
             ("interesse", "SELECT '', '', criado FROM ino_interesse WHERE criado>?"),
             ("impressao", "SELECT '', arquivo_nome, criado FROM ino_impressao WHERE criado>?"),
             ("forum", "SELECT '', titulo, criado FROM com_topico WHERE criado>?"),
             ("mensagem", "SELECT '', substr(texto,1,80), criado FROM com_mensagem WHERE criado>?"))
ROTULO = {"interesse": "Novo cadastro de interesse", "impressao": "Novo pedido de impressão", "forum": "Novo tópico no fórum",
          "mensagem": "Nova mensagem no fórum"}


def banco() -> Path:
    return Path(os.environ.get("PHYSIS_INOVASTEM_BANCO") or (RAIZ_REPO.parent / "clientes" / "physis-inovastem" / "physis-inovastem.db"))


def bot_inovastem(mv, arquivo: Path | None = None) -> dict:
    inicio = mv.nova_rodada()
    arq = Path(arquivo or banco())
    mv.db.execute("CREATE TABLE IF NOT EXISTS mv_assinatura (bot TEXT PRIMARY KEY, valor TEXT NOT NULL, quando REAL NOT NULL)")
    if not arq.is_file():
        r = {"aviso": f"banco da InovaSTEM não encontrado: {arq}"}
        mv.registrar_execucao("inovastem", inicio, json.dumps(r, ensure_ascii=False))
        return r
    ant = mv.db.execute("SELECT valor FROM mv_assinatura WHERE bot='inovastem'").fetchone()
    desde = float(ant[0]) if ant else time.time() - 7 * 86400          # primeira rodada: a última semana
    con = sqlite3.connect(f"file:{arq}?mode=ro", uri=True)
    novos, maior = [], desde
    try:
        for tipo, q in CONSULTAS:
            try:
                for a, b, c in con.execute(q, (desde,)):
                    rot = {"desafio": "Novo desafio", "projeto": "Novo projeto"}.get(a, "Nova proposta") if tipo == "proposta" else ROTULO[tipo]
                    novos.append((tipo, rot + (": " + str(b) if b else ""), c))
                    maior = max(maior, c)
            except sqlite3.Error:
                pass
    finally:
        con.close()
    for tipo, texto, quando in novos:
        mv.alertar("inovastem", tipo, f"{tipo}:{quando}", "atencao", "InovaSTEM · " + texto[:200],
                   "Ver no site da InovaSTEM (Participar, com a conta da equipe): apagar ou responder", "instituto")
    mv.db.execute("INSERT OR REPLACE INTO mv_assinatura VALUES ('inovastem', ?, ?)", (repr(maior), time.time()))
    mv.db.commit()
    r = {"novos": len(novos), "banco": str(arq)}
    mv.registrar_execucao("inovastem", inicio, json.dumps(r, ensure_ascii=False))
    return r
