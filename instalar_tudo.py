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
TESTES_RAPIDOS = ["tests.test_mv", "tests.test_mv_vigia", "tests.test_mv_bots_extra", "tests.test_ia_physis", "tests.test_mv_auditoria_cruzada"]
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
        pare("esta não é a pasta do Sistema Physis (falta physis-hub). Coloque o instalador na pasta physis-sistema.")
    tem_git = (RAIZ / ".git").exists() and roda(["git", "--version"]).returncode == 0
    diz(f"[2/10] Pasta do sistema {RAIZ} ... OK" + ("" if tem_git else " (sem Git: o patch não será aplicado)"))
    # 3
    patch = next((p for p in (RAIZ / "implementacao-final.patch", Path.home() / "Downloads" / "implementacao-final.patch") if p.is_file()), None)
    if patch and tem_git:
        if roda(["git", "apply", "--reverse", "--check", str(patch)]).returncode == 0:
            diz("[3/10] Atualização (patch) .................... já estava aplicada")
        elif roda(["git", "apply", "--check", str(patch)]).returncode == 0:
            if roda(["git", "apply", str(patch)]).returncode != 0:
                pare("o patch não entrou. Rode 'git status' e mostre o resultado.")
            diz("[3/10] Atualização (patch) .................... aplicada agora")
        else:
            pare("o patch não encaixa nesta cópia (alguém mudou arquivos). Rode 'git status' e mostre o resultado.")
    else:
        diz("[3/10] Atualização (patch) .................... nenhum patch encontrado (seguindo)")
    # 4
    if (RAIZ / "demos" / "gerar_demos.py").is_file():
        roda([sys.executable, "demos/gerar_demos.py"])
    diz("[4/10] Demonstrações do site .................. OK")
    # 5
    alvo = ["discover", "-s", "tests"] if "--completo" in argv else TESTES_RAPIDOS
    diz("[5/10] Testes (pode levar alguns minutos) ...")
    p = roda([sys.executable, "-m", "unittest", *alvo], cwd=HUB, tempo=3600)
    linhas = [l for l in p.stderr.splitlines() if l.startswith(("OK", "FAILED", "Ran "))]
    fim = " · ".join(linhas[-2:]) or "?"
    if p.returncode != 0:
        pare(f"algum teste falhou ({fim}).")
    diz(f"       Testes ................................. {fim}")
    # 6
    sys.path.insert(0, str(HUB))
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
    bots = next(c for c in mv_cli.comandos_agenda() if "resumo_7h" in " ".join(c))[-1].split(" bots ", 1)[1].split()
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
