"""Linha de comando do Physis M&V (versão de teste).

    python -m physis_hub.mv_cli semear                 # metas 2027–2031, marcos e Fase 0 (doc 27)
    python -m physis_hub.mv_cli importar <arquivo.json> [--frente engineering|instituto|...]  # exportação physis/1
    python -m physis_hub.mv_cli bots [atrasos documentos resumo]
    python -m physis_hub.mv_cli servir [--porta 8710]
    python -m physis_hub.mv_cli agenda                 # mostra os comandos schtasks (D58); --criar cria as tarefas
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import mv_bots, mv_semente
from .mv import MV

RAIZ_HUB = Path(__file__).resolve().parents[1]


def comandos_agenda() -> list[list[str]]:
    py = sys.executable.replace("python.exe", "pythonw.exe") if sys.executable.endswith("python.exe") else sys.executable
    base = f'cmd /c cd /d "{RAIZ_HUB}" && "{py}" -m physis_hub.mv_cli'
    return [
        ["schtasks", "/Create", "/F", "/SC", "HOURLY", "/TN", "PhysisMV\\bots_hora", "/TR", f"{base} bots atrasos documentos"],
        ["schtasks", "/Create", "/F", "/SC", "DAILY", "/ST", "07:00", "/TN", "PhysisMV\\resumo_7h", "/TR", f"{base} bots atrasos documentos resumo backup"],
        ["schtasks", "/Create", "/F", "/SC", "ONLOGON", "/TN", "PhysisMV\\painel", "/TR", f"{base} servir"],
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="physis-mv")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("semear")
    i = sub.add_parser("importar")
    i.add_argument("arquivo")
    i.add_argument("--frente", default="engineering")
    ie = sub.add_parser("importar-editais")
    ie.add_argument("arquivo")
    b = sub.add_parser("bots")
    b.add_argument("quais", nargs="*")
    s = sub.add_parser("servir")
    s.add_argument("--porta", type=int, default=None)
    g = sub.add_parser("agenda")
    g.add_argument("--criar", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "agenda":
        for c in comandos_agenda():
            print(" ".join(f'"{x}"' if " " in x else x for x in c))
            if a.criar:
                r = subprocess.run(c, capture_output=True, text=True)
                print("  →", (r.stdout or r.stderr).strip())
        return 0
    mv = MV()
    if a.cmd == "semear":
        print(json.dumps(mv_semente.semear(mv), ensure_ascii=False))
    elif a.cmd == "importar":
        n = mv.importar_gestao(a.arquivo, frente=a.frente)
        print(json.dumps({"frente": a.frente, "importadas": n,
                          "ausentes_do_arquivo": mv.ausentes_da_gestao(a.arquivo, a.frente)}, ensure_ascii=False))
    elif a.cmd == "importar-editais":
        from . import mv_editais
        print(json.dumps(mv_editais.Editais(mv).importar_csv(a.arquivo), ensure_ascii=False))
    elif a.cmd == "bots":
        print(json.dumps(mv_bots.rodar(mv, a.quais or None), ensure_ascii=False, indent=1))
    elif a.cmd == "servir":
        from . import mv_servidor
        srv = mv_servidor.servir(mv, a.porta or mv_servidor.PORTA)
        print(f"Physis M&V (teste) em http://127.0.0.1:{srv.server_address[1]}/")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
