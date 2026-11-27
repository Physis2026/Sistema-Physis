#!/usr/bin/env python3
r"""Teste dos bots, da IA e do M&A no servidor (usa o banco de verdade do M&A, como a rodada diária):

    py ferramentas\testar_bots.py            (todos os bots, um por um, com tempo máximo)
    py ferramentas\testar_bots.py --rapido   (sem os bots demorados: ia, camadas, mercado, semanal, backup)

Para cada bot: roda pelo mesmo comando da agenda (python -m physis_hub.mv_cli bots <nome>) e lê o registro de execução.
Depois: M&A no ar e aceitando entrada (caixa de comandos /ajuda), IA local (Ollama) respondendo, IA Physis com fonte,
marketing (tarefas e conteúdos), sincronização. Grava C:\physis\teste-bots-AAAAMMDD-HHMM.md.
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent / "physis-hub"
sys.path.insert(0, str(HUB))
DEMORADOS = {"ia", "camadas", "mercado", "semanal", "backup", "documentos", "auditoria"}


def get(url, corpo=None, tempo=30):
    req = urllib.request.Request(url, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"Content-Type": "application/json"} if corpo is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=tempo) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:          # 401/403/404: responde com o código (403 sem login é proteção correta)
        return e.code, {}


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--rapido", action="store_true"); a = ap.parse_args()
    from physis_hub import mv as mvmod, mv_bots
    dados = os.environ.get("PHYSIS_MV_DADOS") or (r"C:\physis\dados" if os.name == "nt" else str(mvmod.pasta_padrao()))
    banco = Path(dados) / "physis-mv.db"
    L, F, A = [], 0, 0
    def ok(t): L.append("  [ OK  ] " + t)
    def av(t):
        nonlocal A; A += 1; L.append("  [AVISO] " + t)
    def fa(t):
        nonlocal F; F += 1; L.append("  [FALHA] " + t)
    L.append("# Teste dos bots, IA e M&A · " + time.strftime("%d/%m/%Y %H:%M")); L.append(""); L.append("## 1. Bots (um por um)")
    env = dict(os.environ, PHYSIS_MV_DADOS=dados, PYTHONUTF8="1")
    for nome in sorted(mv_bots.BOTS):
        if a.rapido and nome in DEMORADOS:
            L.append(f"  [  -  ] {nome}: pulado (--rapido)"); continue
        t0 = time.time()
        try:
            x = subprocess.run([sys.executable, "-m", "physis_hub.mv_cli", "bots", nome], cwd=str(HUB), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        except subprocess.TimeoutExpired:
            fa(f"{nome}: passou de 15 min"); continue
        dur = time.time() - t0
        erro = ""
        try:
            con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
            r = con.execute("SELECT erro FROM mv_execucao WHERE bot=? ORDER BY id DESC LIMIT 1", (nome,)).fetchone(); con.close()
            erro = (r[0] if r else "") or ""
        except sqlite3.Error as e:
            erro = f"sem registro ({e})"
        if x.returncode != 0 or erro:
            fa(f"{nome}: {(erro or x.stderr or x.stdout)[-250:].strip()}")
        else:
            ok(f"{nome} ({dur:.0f} s)")
        print(L[-1])
    L.append(""); L.append("## 2. M&A no ar e aceitando entrada")
    try:
        st, j = get("http://127.0.0.1:8710/api/mv/saude"); ok("M&A responde (saúde)") if st == 200 else fa(f"saúde {st}")
        st, j = get("http://127.0.0.1:8710/api/mv/comando", {"texto": "/ajuda"}); ok("caixa de comandos aceitou /ajuda") if st == 200 else (ok("caixa de comandos protegida: sem login responde 403 (correto); a entrada pela tela exige conta") if st in (401, 403) else fa(f"comando {st}"))
        st, j = get("http://127.0.0.1:8710/api/mv/marketing"); n = len(j) if isinstance(j, list) else len(j.get("itens", [])) if isinstance(j, dict) else 0
        ok(f"marketing: {n} conteúdo(s) na fila") if n else av("marketing: nenhum conteúdo na fila (a Gestão ainda não tem conteúdos?)")
        st, j = get("http://127.0.0.1:8710/api/mv/fila"); ok(f"fila de pedidos dos bots: {len(j) if isinstance(j, list) else '?'}")
    except Exception as e:  # noqa: BLE001
        fa(f"M&A não respondeu: {e}")
    L.append(""); L.append("## 3. IA")
    try:
        st, j = get("http://127.0.0.1:11434/api/generate", {"model": "qwen2.5:7b", "prompt": "Responda só: ok", "stream": False}, tempo=240)
        ok("IA local (qwen2.5) respondeu: " + str(j.get("response", ""))[:40].replace("\n", " ")) if j.get("response") else fa("IA local sem resposta")
    except Exception as e:  # noqa: BLE001
        fa(f"IA local (Ollama) não respondeu em 4 min: {e}")
    try:
        st, j = get("http://127.0.0.1:8710/api/mv/ia?q=" + urllib.request.quote("O que é a Casa Physis?"), tempo=240)
        (ok(f"IA Physis respondeu com {len(j.get('fontes') or [])} fonte(s)") if j.get("fontes") else av("IA Physis sem fonte (índice vazio? rode o bot ia)"))
    except Exception as e:  # noqa: BLE001
        av(f"IA Physis: {e}")
    L.append(""); L.append("## 4. Marketing e sincronização")
    if os.name == "nt":
        x = subprocess.run(["schtasks", "/Query", "/FO", "CSV", "/V", "/TN", r"\Physis\Marketing KPIs"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        for tn in ("Marketing Aprovacoes", "Marketing KPIs", "Marketing Lembretes"):
            y = subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-ScheduledTask -TaskPath '\\Physis\\' -TaskName '{tn}' | Get-ScheduledTaskInfo).LastTaskResult"], capture_output=True, text=True, encoding="utf-8", errors="replace")
            r = (y.stdout or "").strip()
            ok(f"tarefa {tn}: última execução sem erro") if r == "0" else av(f"tarefa {tn}: resultado {r or 'desconhecido'}")
    try:
        con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
        r = con.execute("SELECT fim, erro FROM mv_execucao WHERE bot='sincronizacao' ORDER BY id DESC LIMIT 1").fetchone(); con.close()
        if r and not r[1]:
            ok("sincronização: última rodada " + time.strftime("%d/%m %H:%M", time.localtime(r[0] or 0)) + " sem erro")
        else:
            av("sincronização: sem rodada recente sem erro")
    except sqlite3.Error:
        av("sincronização: banco do M&A não lido")
    L.append(""); L.append(f"**Resultado: {F} falha(s), {A} aviso(s).**")
    rel = Path(r"C:\physis" if os.name == "nt" else "/tmp") / ("teste-bots-" + time.strftime("%Y%m%d-%H%M") + ".md")
    rel.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[-14:])); print("Relatório:", rel)
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
