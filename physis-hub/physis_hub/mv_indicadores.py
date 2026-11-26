"""Indicadores de TODAS as plataformas numa tela do M&A (26/11/2026, pedido da dona: "uma tela no M&A unificada, que
compute o trabalho de todas as plataformas, site e etc").

Lê, só para leitura, a tabela indicador_hora (indicadores.py) de cada banco: o hub, cada instalação em <base>/clientes
(Casa, site/Gestão, InovaSTEM, GSA, Estermic...) e soma por plataforma e no total. Só números (nunca dado pessoal).
Base: PHYSIS_BASE ou a pasta acima da do banco do M&A (C:\\physis). Bancos extras: PHYSIS_MV_BANCOS (separados por ;).
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

SOMA = ["req.total", "login.ok", "login.senha_errada", "login.bloqueado", "med.leituras", "med.alarmes", "alerta.enviados",
        "ia.chamadas", "ia.falhas", "loja.compras", "loja.instalacoes", "doc.emitido", "suporte.acessos_novos", "csrf.recusado", "req.limite_429"]
MEDIA = ["req.taxa_5xx", "req.taxa_4xx", "req.p95_ms"]
ULTIMO = ["backup.idade_h", "testes.falhas", "disp.nos_ativos", "doc.em_revisao", "ia.gasto_mes_usd"]


def bancos(mv) -> list[tuple[str, Path]]:
    base = Path(os.environ.get("PHYSIS_BASE") or Path(getattr(mv, "caminho", ".")).resolve().parent.parent)
    out = []
    for b in [x for x in (os.environ.get("PHYSIS_MV_BANCOS") or "").split(";") if x.strip()]:
        out.append((Path(b).stem, Path(b)))
    for repo in sorted(base.glob("physis-ma-*/physis-hub/physis-hub.db")):
        out.append(("Hub (8700)", repo))
    for inst in sorted((base / "clientes").glob("physis-*")):
        if not inst.is_dir() or ".antiga-" in inst.name or ".falhou-" in inst.name:
            continue
        nome = inst.name.replace("physis-", "")
        try:
            j = json.loads((inst / "instancia.json").read_text(encoding="utf-8"))
            nome = j.get("nome") or j.get("org") or nome
        except (OSError, ValueError):
            pass
        for db in sorted(inst.glob("*.db")):
            out.append((str(nome), db))
    vistos, uni = set(), []
    for n, p in out:
        k = str(p.resolve()) if p.exists() else str(p)
        if k not in vistos and p.exists():
            vistos.add(k); uni.append((n, p))
    return uni


def _ler(db: Path, desde_h: int) -> list[tuple[int, str, float]]:
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        try:
            return con.execute("SELECT hora, chave, valor FROM indicador_hora WHERE hora>=?", (desde_h,)).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return []


def resumo(linhas, agora_h: int, horas: int) -> dict:
    sel = [(h, k, v) for h, k, v in linhas if h > agora_h - horas]
    r = {}
    for k in SOMA:
        r[k] = round(sum(v for h, kk, v in sel if kk == k), 2)
    for k in MEDIA:
        xs = [v for h, kk, v in sel if kk == k]
        r[k] = round(sum(xs) / len(xs), 4) if xs else None
    for k in ULTIMO:
        xs = sorted((h, v) for h, kk, v in sel if kk == k)
        r[k] = xs[-1][1] if xs else None
    r["horas_com_dado"] = len({h for h, _, _ in sel})
    return r


def painel(mv, agora: float | None = None) -> dict:
    agora_h = int((agora or time.time()) // 3600)
    plats, total7 = [], {k: 0.0 for k in SOMA}
    for nome, db in bancos(mv):
        linhas = _ler(db, agora_h - 24 * 30)
        if not linhas:
            plats.append({"nome": nome, "banco": db.name, "sem_dado": True}); continue
        d1, d7, d30 = resumo(linhas, agora_h, 24), resumo(linhas, agora_h, 24 * 7), resumo(linhas, agora_h, 24 * 30)
        dias = []
        for i in range(13, -1, -1):
            ini = agora_h - 24 * (i + 1)
            dias.append(round(sum(v for h, k, v in linhas if k == "req.total" and ini < h <= ini + 24), 1))
        plats.append({"nome": nome, "banco": db.name, "dia": d1, "semana": d7, "mes": d30, "pedidos_14d": dias})
        for k in SOMA:
            total7[k] += d7[k] or 0
    alertas = []
    for p in plats:
        if p.get("sem_dado"):
            alertas.append(f"{p['nome']}: sem indicadores (a plataforma não coletou ainda ou está desligada)"); continue
        s = p["semana"]
        if (s.get("req.taxa_5xx") or 0) > 0.01: alertas.append(f"{p['nome']}: erros 5xx acima de 1% na semana")
        if (p["dia"].get("backup.idade_h") or 0) > 36: alertas.append(f"{p['nome']}: cópia de segurança com mais de 36 h")
        if (s.get("login.bloqueado") or 0) > 0: alertas.append(f"{p['nome']}: {int(s['login.bloqueado'])} entrada(s) bloqueada(s) na semana")
        if (p["dia"].get("testes.falhas") or 0) > 0: alertas.append(f"{p['nome']}: testes com falha na última implantação")
    return {"ok": True, "gerado": time.time(), "plataformas": plats, "total_semana": {k: round(v, 2) for k, v in total7.items()}, "alertas": alertas}
