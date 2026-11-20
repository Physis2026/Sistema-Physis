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
import time
import traceback
from datetime import datetime
from pathlib import Path

from . import mv_bots, mv_semente
from .mv import MV, pasta_padrao

RAIZ_HUB = Path(__file__).resolve().parents[1]


def comandos_agenda() -> list[list[str]]:
    py = sys.executable.replace("python.exe", "pythonw.exe") if sys.executable.endswith("python.exe") else sys.executable
    base = f'cmd /c cd /d "{RAIZ_HUB}" && "{py}" -m physis_hub.mv_cli'
    return [
        ["schtasks", "/Create", "/F", "/SC", "HOURLY", "/TN", "PhysisMV\\bots_hora", "/TR", f"{base} bots atrasos documentos"],
        ["schtasks", "/Create", "/F", "/SC", "DAILY", "/ST", "07:00", "/TN", "PhysisMV\\resumo_7h", "/TR", f"{base} bots atrasos documentos resumo backup paginas inovacao"],
        ["schtasks", "/Create", "/F", "/SC", "ONLOGON", "/TN", "PhysisMV\\painel", "/TR", f"{base} servir"],
        # R-02 (auditoria 39): rodar depois se o computador estava desligado às 7h, e também na bateria
        ["powershell", "-NoProfile", "-Command",
         "$s=New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries "
         "-ExecutionTimeLimit (New-TimeSpan -Hours 2); "
         "foreach($n in 'bots_hora','resumo_7h'){Set-ScheduledTask -TaskPath '\\PhysisMV\\' -TaskName $n -Settings $s | Out-Null}; 'ok'"],
    ]


def registrar_falha(argv, erro: BaseException) -> Path:
    """Falha fora de rodar() (abrir o banco, importar, argumentos) fica no mv_cli.log e, se der, vira alerta (R-02)."""
    log = pasta_padrao() / "mv_cli.log"
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] argv={argv!r}\n")
        f.write("".join(traceback.format_exception(erro)))
    try:
        mv = MV()
        try:
            mv.registrar_execucao("cli", time.time(), "", repr(erro)[:500])
            mv.alertar("mv", "cli_falhou", " ".join(map(str, argv or []))[:80] or "cli", "alerta",
                       f"A linha de comando do M&A falhou: {erro!r}"[:300], f"Ver {log}")
        finally:
            mv.db.close()
    except Exception:  # noqa: BLE001 — o registro em arquivo já foi feito
        pass
    return log


def main(argv=None) -> int:
    try:
        return _main(argv)
    except SystemExit:
        raise
    except BaseException as e:  # noqa: BLE001
        log = registrar_falha(argv if argv is not None else sys.argv[1:], e)
        print(f"falhou: {e!r} (detalhes em {log})", file=sys.stderr)
        return 1


def _main(argv=None) -> int:
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
    s.add_argument("--rede", action="store_true", help="teste na rede local com senha (sem internet pública)")
    pg = sub.add_parser("pergunta", help="registra uma pergunta à dona no M&A (ou devolve a resposta já dada)")
    pg.add_argument("texto")
    pg.add_argument("--opcoes", default="", help="opções separadas por |")
    pg.add_argument("--origem", default="sessao")
    pg.add_argument("--aplica", default="", help="sistemas separados por vírgula: " + ",".join(("sistema-physis", "instituto", "inovastem", "casa", "m&a", "templates", "documentos")))
    pg.add_argument("--prazo", default="")
    pl = sub.add_parser("perguntas", help="lista perguntas e respostas centralizadas no M&A")
    pl.add_argument("--abertas", action="store_true")
    pl.add_argument("--sistema", default="")
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
    try:
        if a.cmd == "semear":
            print(json.dumps(mv_semente.semear(mv), ensure_ascii=False))
        elif a.cmd == "importar":
            n = mv.importar_gestao(a.arquivo, frente=a.frente)
            print(json.dumps({"frente": a.frente, "importadas": n,
                              "ausentes_do_arquivo": mv.ausentes_da_gestao(a.arquivo, a.frente)}, ensure_ascii=False))
        elif a.cmd == "pergunta":
            from . import mv_comandos
            print(json.dumps(mv_comandos.perguntar(mv, a.texto, [o for o in a.opcoes.split("|") if o], a.origem,
                                                   [s for s in a.aplica.split(",") if s], a.prazo), ensure_ascii=False, indent=1))
        elif a.cmd == "perguntas":
            from . import mv_comandos
            print(json.dumps(mv_comandos.perguntas(mv, True if a.abertas else None, a.sistema or None), ensure_ascii=False, indent=1))
        elif a.cmd == "importar-editais":
            from . import mv_editais
            print(json.dumps(mv_editais.Editais(mv).importar_csv(a.arquivo), ensure_ascii=False))
        elif a.cmd == "bots":
            print(json.dumps(mv_bots.rodar(mv, a.quais or None), ensure_ascii=False, indent=1))
        elif a.cmd == "servir":
            from . import mv_servidor
            srv = mv_servidor.servir(mv, a.porta or mv_servidor.PORTA, rede_local=a.rede)
            print(f"Physis M&A (teste) em http://127.0.0.1:{srv.server_address[1]}/")
            for ip in getattr(srv, "ips", []):
                print(f"  rede local: http://{ip}:{srv.server_address[1]}/  (usuário teste; senha em "
                      f"{Path(mv.caminho).parent / 'senha-teste-rede.txt'})")
            try:
                srv.serve_forever()
            except KeyboardInterrupt:
                pass
    finally:
        mv.db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
