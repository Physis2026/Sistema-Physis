#!/usr/bin/env python3
"""Instalador de um clique do Physis M&A (bots, IA Physis, agenda e tela). Feito para qualquer pessoa usar.

    INSTALAR-PHYSIS.bat            (Windows: duplo clique)
    python ferramentas/instalar_tudo.py [--completo] [--sem-agenda] [--sem-abrir]

Passos (cada um mostra OK ou o que fazer): 1 Python · 2 Git e pasta · 3 patch (se houver e ainda não aplicado) · 4 demos ·
5 testes · 6 banco do M&A (só cria se não existir) · 7 primeira rodada de todos os bots · 8 índice da IA Physis ·
9 agenda do Windows · 10 abre o M&A no navegador. Pode rodar de novo quantas vezes quiser: o que já está feito é pulado.
Nada é apagado. Um registro fica em instalar-physis.log, na pasta do sistema.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
RAIZ = _AQUI if (_AQUI / "physis-hub").is_dir() else _AQUI.parent      # solto na pasta principal ou em ferramentas/
HUB = RAIZ / "physis-hub"
LOG = RAIZ / "instalar-physis.log"
TESTES_RAPIDOS = ["tests.test_mv", "tests.test_mv_vigia", "tests.test_mv_bots_extra", "tests.test_ia_physis", "tests.test_mv_auditoria_cruzada", "tests.test_mv_ecossistema"]
try:
    sys.stdout.reconfigure(errors="replace")      # console antigo do Windows não quebra com acento
except (AttributeError, ValueError):
    pass


def diz(t: str) -> None:
    print(t, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + t + "\n")


def roda(cmd: list[str], cwd: Path = RAIZ, tempo: int = 1800) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=tempo)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"$ {' '.join(cmd)}\n{p.stdout[-4000:]}{p.stderr[-4000:]}\n")
    return p


def pare(t: str) -> None:
    diz("")
    diz("  PAROU AQUI: " + t)
    diz(f"  Mostre a um adulto ou mande o arquivo {LOG} para a equipe.")
    sys.exit(1)


ANTIGAS = ("bots_8h", "sinal_hora", "semanal")        # tarefas de versões anteriores (chamam bots que não existem mais)


def pergunta(t: str) -> bool:
    try:
        return input(f"  {t} (S/N): ").strip().lower().startswith("s")
    except EOFError:
        return False


def limpar_agenda_antiga() -> None:
    achadas = [n for n in ANTIGAS if roda(["schtasks", "/Query", "/TN", f"PhysisMV\\{n}"]).returncode == 0]
    if not achadas:
        return
    diz(f"       Tarefas antigas na agenda: {', '.join(achadas)} (dão erro, ex.: KeyError('sinal'))")
    if pergunta("Posso APAGAR essas tarefas antigas? Nada mais é apagado"):
        for n in achadas:
            roda(["schtasks", "/Delete", "/F", "/TN", f"PhysisMV\\{n}"])
        diz("       Tarefas antigas apagadas")
    else:
        diz("       Tarefas antigas mantidas (continuarão dando erro)")


def servidor_antigo() -> None:
    """Se já há um M&A na porta 8710 sem a aba Monitoramento, é a versão antiga: o novo não consegue abrir."""
    import urllib.error
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:8710/api/mv/integracoes", timeout=5)
        return                                   # já é o novo
    except urllib.error.HTTPError:
        pass                                     # responde, mas sem a rota: antigo
    except Exception:  # noqa: BLE001
        return                                   # nada rodando
    diz("       Há um M&A ANTIGO aberto na porta 8710.")
    if os.name == "nt" and pergunta("Posso FECHAR o M&A antigo para abrir o novo?"):
        p = roda(["powershell", "-NoProfile", "-Command",
                  "(Get-NetTCPConnection -LocalPort 8710 -State Listen).OwningProcess | Sort-Object -Unique"])
        for pid in p.stdout.split():
            if pid.isdigit():
                roda(["taskkill", "/PID", pid, "/F"])
        time.sleep(2)
        diz("       M&A antigo fechado")
    else:
        diz("       Feche o M&A antigo (ou reinicie o computador) e rode o instalador de novo.")


def main(argv: list[str]) -> int:
    diz("=" * 60)
    diz("  Instalador do Physis M&A")
    diz("=" * 60)
    # 1
    if sys.version_info < (3, 10):
        pare(f"o Python é {sys.version.split()[0]}; precisa ser 3.10 ou mais novo (guia, passo 1).")
    diz(f"[1/10] Python {sys.version.split()[0]} ........................ OK")
    # 2
    if not (HUB / "physis_hub" / "mv_cli.py").is_file():
        pare("esta não é a pasta do Sistema Physis (falta physis-hub). Coloque o instalador na pasta do sistema (ex.: C:\\physis\\physis-ma-20261122-1bd599e).")
    tem_git = (RAIZ / ".git").exists() and roda(["git", "--version"]).returncode == 0
    diz(f"[2/10] Pasta do sistema {RAIZ} ... OK" + ("" if tem_git else " (sem Git: o patch não será aplicado)"))
    # 3
    nomes = ("atualizacao-physis-2026-11-22.patch", "implementacao-final.patch")
    patch = next((p for n in nomes for p in (RAIZ / n, Path.home() / "Downloads" / n) if p.is_file()), None)
    # arquivos que você já copiou para a pasta (o .bat que está rodando, o LEIA-PRIMEIRO) não entram pelo patch
    sem = ["--exclude=INSTALAR-PHYSIS.bat", "--exclude=LEIA-PRIMEIRO.txt"]
    if patch and tem_git:
        if roda(["git", "apply", *sem, "--reverse", "--check", str(patch)]).returncode == 0:
            diz("[3/10] Atualização (patch) .................... já estava aplicada")
        elif roda(["git", "apply", *sem, "--check", str(patch)]).returncode == 0:
            if roda(["git", "apply", *sem, str(patch)]).returncode != 0:
                pare("o patch não entrou. Rode 'git status' e mostre o resultado.")
            diz("[3/10] Atualização (patch) .................... aplicada agora")
        else:
            pare("o patch não encaixa nesta cópia (alguém mudou arquivos). Rode 'git status' e mostre o resultado.")
    else:
        diz("[3/10] Atualização (patch) .................... nenhum patch encontrado (seguindo)")
    # 4 · telas, cópias embutidas e demos são GERADAS: o pacote pequeno não as traz, o instalador refaz (idempotente)
    for gerador in ("ferramentas/padronizar_paginas.py", "ferramentas/sincronizar.py", "ferramentas/embutir_bases.py", "demos/gerar_demos.py"):
        if (RAIZ / gerador).is_file():
            p = roda([sys.executable, gerador])
            if p.returncode != 0:
                pare(f"o gerador {gerador} deu erro (veja o registro).")
    diz("[4/10] Telas, cópias e demonstrações .......... OK")
    # 5
    alvo = ["discover", "-s", "tests"] if "--completo" in argv else TESTES_RAPIDOS
    diz("[5/10] Testes (pode levar alguns minutos) ...")
    p = roda([sys.executable, "-m", "unittest", *alvo], cwd=HUB, tempo=3600)
    linhas = [l for l in p.stderr.splitlines() if l.startswith(("OK", "FAILED", "Ran "))]
    fim = " · ".join(linhas[-2:]) or "?"
    if p.returncode != 0:
        pare(f"algum teste falhou ({fim}).")
    diz(f"       Testes ................................. {fim}")
    sys.path.insert(0, str(HUB))
    # pastas do OneDrive que os bots leem (só avisa; não para a instalação)
    from physis_hub import mv_bots, mv_repositorios
    diz(f"       Documentos do OneDrive: {mv_bots.DOCS}" + ("" if mv_bots.DOCS.is_dir() else "  (NÃO ENCONTRADA: guia, PHYSIS_DOCS)"))
    for p in mv_bots.pastas_documentos():
        diz(f"         {'OK   ' if p.is_dir() else 'FALTA'} {p.name}")
    mk = mv_repositorios.caminhos_existentes()
    diz(f"         {'OK   ' if mk else 'FALTA'} Marketing Physis" + (f" ({mk[0]})" if mk else ""))
    # 6
    from physis_hub.mv import pasta_padrao
    banco = pasta_padrao() / "physis-mv.db"
    if banco.is_file():
        diz(f"[6/10] Banco do M&A ........................... já existe ({banco})")
    else:
        roda([sys.executable, "-m", "physis_hub.mv_cli", "semear"], cwd=HUB)
        diz(f"[6/10] Banco do M&A ........................... criado ({banco})")
    # 7
    diz("[7/10] Primeira rodada de todos os bots ...")
    from physis_hub import mv_cli
    bots = list(getattr(mv_cli, "RODADA_DIARIA", None) or
                next(c for c in mv_cli.comandos_agenda() if "resumo_7h" in " ".join(c))[-1].split(" bots ", 1)[1].split())
    p = roda([sys.executable, "-m", "physis_hub.mv_cli", "bots", *bots], cwd=HUB, tempo=3600)
    if p.returncode != 0:
        pare("a rodada dos bots deu erro (veja o registro).")
    diz(f"       {len(bots)} bots rodaram ......................... OK")
    # 8
    roda([sys.executable, "-m", "physis_hub.mv_cli", "ia", "--indexar"], cwd=HUB)
    diz("[8/10] Índice da IA Physis .................... OK")
    # 9
    if "--sem-agenda" in argv:
        diz("[9/10] Agenda ................................. pulada (--sem-agenda)")
    elif os.name == "nt":
        limpar_agenda_antiga()
        p = roda([sys.executable, "-m", "physis_hub.mv_cli", "agenda", "--criar"], cwd=HUB)
        if p.returncode != 0:
            pare("a agenda não foi criada. Feche, clique com o BOTÃO DIREITO no INSTALAR-PHYSIS.bat e escolha 'Executar como administrador'.")
        diz("[9/10] Agenda do Windows (PhysisMV) ........... OK")
    else:
        diz("[9/10] Agenda ................................. só no Windows (no Linux: guia, Parte 7B)")
    # 10
    if "--sem-abrir" in argv:
        diz("[10/10] Tela do M&A ........................... não aberta (--sem-abrir)")
    else:
        servidor_antigo()
        py = sys.executable.replace("python.exe", "pythonw.exe") if os.name == "nt" else sys.executable
        bandeiras = 0x00000008 if os.name == "nt" else 0          # DETACHED_PROCESS no Windows
        subprocess.Popen([py, "-m", "physis_hub.mv_cli", "servir"], cwd=str(HUB), creationflags=bandeiras,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        webbrowser.open("http://127.0.0.1:8710/")
        diz("[10/10] Tela do M&A ........................... aberta em http://127.0.0.1:8710/")
    diz("")
    diz("  PRONTO! Agora, no M&A:")
    diz("   - aba Monitoramento: o mapa com as engrenagens;")
    diz("   - aba Aprovações > Perguntas: responda as perguntas das pendências;")
    diz("   - aba Bots e comandos: os pedidos dos bots para aprovar.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
