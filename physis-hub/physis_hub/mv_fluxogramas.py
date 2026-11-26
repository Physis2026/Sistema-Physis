"""Fluxogramas editáveis do M&A (Flowy, MIT; 26/11/2026): a direção desenha os fluxos aba > módulo > plataforma > M&A
e guarda aqui. Só o desenho (JSON do Flowy); até 200 fluxogramas de até 500 kB."""
from __future__ import annotations

import json
import re
import time

NOME = re.compile(r"^[\w .()-]{1,80}$")


def _tabela(mv):
    mv.db.execute("CREATE TABLE IF NOT EXISTS mv_fluxograma (nome TEXT PRIMARY KEY, dados TEXT NOT NULL, atualizado REAL NOT NULL)")


def listar(mv) -> dict:
    _tabela(mv)
    return {"ok": True, "itens": [{"nome": n, "atualizado": a} for n, a in mv.db.execute("SELECT nome, atualizado FROM mv_fluxograma ORDER BY atualizado DESC")]}


def ler(mv, nome: str) -> dict:
    _tabela(mv)
    r = mv.db.execute("SELECT dados, atualizado FROM mv_fluxograma WHERE nome=?", (nome,)).fetchone()
    return {"ok": bool(r), "nome": nome, "dados": json.loads(r[0]) if r else None, "atualizado": r[1] if r else None}


def gravar(mv, nome: str, dados) -> dict:
    nome = str(nome or "").strip()
    if not NOME.match(nome):
        return {"ok": False, "erro": "nome inválido (letras, números, espaço, ponto, hífen; até 80)"}
    txt = json.dumps(dados, ensure_ascii=False)
    if len(txt) > 500_000:
        return {"ok": False, "erro": "fluxograma grande demais"}
    _tabela(mv)
    if mv.db.execute("SELECT COUNT(*) FROM mv_fluxograma").fetchone()[0] >= 200 and not mv.db.execute("SELECT 1 FROM mv_fluxograma WHERE nome=?", (nome,)).fetchone():
        return {"ok": False, "erro": "limite de 200 fluxogramas"}
    mv.db.execute("INSERT OR REPLACE INTO mv_fluxograma(nome, dados, atualizado) VALUES(?,?,?)", (nome, txt, time.time()))
    mv.db.commit()
    return {"ok": True, "nome": nome}
