#!/usr/bin/env python3
r"""Atualização final (24/11/2026): confere, regenera, testa e salva TUDO com um comando, e escreve o relatório.

    cd C:\physis\physis-ma-20261122-1bd599e
    py ferramentas\atualizacao_final.py                 # confere + regenera + testes rápidos + relatório (não salva)
    py ferramentas\atualizacao_final.py --completo      # + todos os testes do Sistema e do Instituto (demora)
    py ferramentas\atualizacao_final.py --completo --salvar --backup   # + git commit nos dois e backup completo em zip

Só ESCREVE: cópia dos bancos antes de mexer (dados/antes-da-atualizacao-AAAAMMDD-HHMM), arquivos gerados (painel, demos,
laboratório), a Gestão e o Planejador da Casa nas instalações (cópia), commits (com --salvar) e o backup (com --backup).
Nunca apaga nada. Relatório: RELATORIO-ATUALIZACAO-FINAL.md na pasta do sistema.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE = RAIZ.parent
INST = BASE / "instituto-physis"
CLIENTES = BASE / "clientes"
PY = sys.executable
CERCA_MD = chr(96) * 3
PORTAS = {8710: "Physis M&A", 8700: "Hub", 8701: "Casa Physis", 8702: "InovaSTEM", 8703: "site Physis + Gestão", 8704: "Estermic"}
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

rel: list[str] = []
pend: list[str] = []


def diz(t: str = "") -> None:
    print(t, flush=True)
    rel.append(t)


def bloco(titulo: str, txt: str) -> None:
    diz(f"{titulo}\n{CERCA_MD}\n{txt}\n{CERCA_MD}")


def rodar(cmd: list[str], cwd: Path, limite: int = 7200) -> tuple[int, str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=limite, env=env)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def resumo_testes(saida: str) -> str:
    linhas = [l for l in saida.splitlines() if l.startswith(("Ran ", "OK", "FAILED", "FAIL:", "ERROR:"))]
    return "\n".join(linhas[-12:]) or saida[-400:]


def git_estado(rep: Path, nome: str) -> None:
    if not (rep / ".git").exists():
        diz(f"- {nome}: pasta {rep} não encontrada")
        pend.append(f"{nome}: repositório não encontrado em {rep}")
        return
    _, ramo = rodar(["git", "branch", "--show-current"], rep)
    _, ult = rodar(["git", "log", "--oneline", "-1"], rep)
    _, ns = rodar(["git", "status", "--porcelain"], rep)
    n = len([l for l in ns.splitlines() if l.strip()])
    diz(f"- {nome}: ramo {ramo.strip()} · último salvamento {ult.strip()} · {n} arquivo(s) não salvo(s)")


def copiar_bancos() -> None:
    dest = BASE / "dados" / f"antes-da-atualizacao-{time.strftime('%Y%m%d-%H%M')}"
    vistos, bancos = set(), []
    for p in list((BASE / "dados").glob("*.db")) + list(CLIENTES.glob("*/dados/*.db")) + list(CLIENTES.glob("*/*.db")):
        if p.is_file() and p.resolve() not in vistos:
            vistos.add(p.resolve())
            bancos.append(p)
    if not bancos:
        diz("- nenhum banco encontrado (instalação nova?)")
        return
    dest.mkdir(parents=True, exist_ok=True)
    for i, b in enumerate(bancos):
        dono = b.parent.parent.name if b.parent.name == "dados" else b.parent.name
        alvo = dest / f"{dono}__{b.name}"
        try:
            o, d = sqlite3.connect(str(b)), sqlite3.connect(str(alvo))
            o.backup(d)                      # cópia consistente mesmo com o servidor ligado
            o.close()
            ok = d.execute("PRAGMA quick_check").fetchone()[0]
            d.close()
            diz(f"- {b} → {alvo.name} ({ok})")
            if ok != "ok":
                pend.append(f"banco {b.name}: integridade {ok}")
        except sqlite3.Error as e:
            pend.append(f"banco {b}: não copiado ({e})")
            diz(f"- {b}: ERRO {e}")


def regenerar() -> None:
    for cmd in ([PY, "ferramentas/sincronizar.py"], [PY, "ferramentas/embutir_bases.py"], [PY, "demos/gerar_demos.py"]):
        c, s = rodar(cmd, RAIZ, 900)
        diz(f"- {cmd[1]}: {'ok' if c == 0 else 'ERRO'}")
        if c:
            pend.append(f"{cmd[1]} falhou: {s[-300:]}")
    lab = INST / "ferramentas" / "montar_lab_inovastem.py"
    if lab.is_file():
        c, s = rodar([PY, str(lab)], INST, 900)
        diz(f"- laboratório InovaSTEM: {'ok' if c == 0 else 'ERRO'} {s.strip()[-120:]}")
        if c:
            pend.append("montar_lab_inovastem falhou")
    site = CLIENTES / "physis-physis-site" / "web"
    if site.is_dir():
        shutil.copy2(RAIZ / "sistema" / "gestao-interna-physis.html", site / "gestao.html")
        diz("- Gestão copiada para o site (8703 /gestao/)")
    casa = CLIENTES / "physis-casa-physis-inicial" / "web"
    if casa.is_dir():
        alvo = casa / "planejador.html"
        shutil.copy2(RAIZ / "modulos" / "planejador" / "planejador-physis.html", alvo)
        sys.path.insert(0, str(RAIZ / "physis-hub"))
        import montar  # noqa: E402
        montar.edicao_completa(alvo)
        diz("- Planejador da Casa Physis: edição completa, sem licença")


def testes(completo: bool) -> None:
    hub = RAIZ / "physis-hub"
    if completo:
        c, s = rodar([PY, "-m", "unittest", "discover", "-s", "tests"], hub)
    else:
        rap = ["tests.test_ia_generativa", "tests.test_mv_comandos", "tests.test_modelagem_analises", "tests.test_preferencias",
               "tests.test_sincronia", "tests.test_bases", "tests.test_planejador_edicao", "tests.test_fila_e_edital", "tests.test_mv_auditoria_cruzada"]
        c, s = rodar([PY, "-m", "unittest", *rap], hub, 1800)
    bloco(f"### Sistema ({'todos' if completo else 'rápidos'})", resumo_testes(s))
    if c:
        pend.append("testes do Sistema com falha (ver acima)")
    ih = INST / "physis-hub"
    if ih.is_dir():
        args = ["discover", "-s", "tests"] if completo else ["tests.test_inovastem"]
        c, s = rodar([PY, "-m", "unittest", *args], ih)
        bloco(f"### Instituto ({'todos' if completo else 'InovaSTEM'})", resumo_testes(s))
        if c:
            pend.append("testes do Instituto com falha (ver acima)")


def servicos() -> None:
    for porta, nome in PORTAS.items():
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{porta}/", timeout=5) as r:
                diz(f"- {porta} {nome}: responde ({r.status})")
        except Exception as e:  # noqa: BLE001
            diz(f"- {porta} {nome}: NÃO responde ({type(e).__name__})")
            pend.append(f"porta {porta} ({nome}) não responde: religar pela agenda ou remontar")
    sys.path.insert(0, str(RAIZ / "physis-hub"))
    try:
        from physis_hub import ia_generativa
        e = ia_generativa.estado()
        diz(f"- IA Physis: servidor {'ligado' if e.get('servidor') else 'desligado'} · modelo {e.get('modelo')} {'instalado' if e.get('instalado') else 'NÃO instalado'}")
        if not e.get("instalado"):
            pend.append("IA generativa: ligar o Ollama e baixar o modelo (ollama pull qwen2.5:7b)")
    except Exception as ex:  # noqa: BLE001
        diz(f"- IA Physis: erro {ex}")
    if os.name == "nt":
        c, s = rodar(["schtasks", "/query", "/fo", "csv", "/nh"], RAIZ, 120)
        ts = sorted({l.split(",")[0].strip('"') for l in s.splitlines() if "Physis" in l})
        diz(f"- agenda do Windows: {len(ts)} tarefa(s) Physis: " + ", ".join(ts[:25]))


def salvar() -> None:
    for rep, nome in ((RAIZ, "Sistema"), (INST, "Instituto")):
        if not (rep / ".git").exists():
            continue
        rodar(["git", "add", "-A"], rep)
        c, s = rodar(["git", "commit", "-m", f"Atualização final {time.strftime('%d/%m/%Y %H:%M')} (ferramentas/atualizacao_final.py)"], rep)
        diz(f"- {nome}: {'salvo' if c == 0 else 'nada novo para salvar' if 'nothing' in s else 'ERRO ' + s[-200:]}")


def backup() -> None:
    c, s = rodar([PY, "ferramentas/backup_completo.py"], RAIZ, 4 * 3600)
    pasta = next((l.split("Pasta:", 1)[1].strip() for l in s.splitlines() if "Pasta:" in l), "")
    diz(f"- backup completo: {'ok' if c == 0 else 'com pendências'} · {pasta}")
    if pasta and Path(pasta).is_dir():
        z = shutil.make_archive(pasta, "zip", pasta)
        diz(f"- zip: {z} ({Path(z).stat().st_size / 1048576:.0f} MB) · guarde uma cópia FORA deste computador (HD externo)")
    if c:
        pend.append("backup completo com pendências (ver MANIFESTO.md no backup)")


# o que só a dona, o provedor ou o Acer resolvem (não dá para fazer por código) · atualizar a cada rodada
FORA_DO_CODIGO = [
    "Rede pública: prevista para 26/11/2026 (IP fixo do provedor ou VPS + WireGuard); depois o Caddyfile e o DNS no Microsoft 365",
    "E-mail real: senha de app do Microsoft 365 para rafaella.dourado@physisengineering.com (setx PHYSIS_SMTP_SENHA) e teste de envio",
    "Contas: redefinir senha da Casa (contas_site.py), criar contas do Hub e da InovaSTEM",
    "Missão/visão oficiais: atualização na Fase 2 (decisão de 24/11/2026)",
    "Quadros elétricos: carimbo da Casa Physis (logos em physis-hub/web/logos/casa-physis_*) no modelo do QElectroTech",
    "Tarefas Executar que o bot não faz sozinho: ver py -m physis_hub.mv_cli executar",
    "Acer (Linux): instalar seguindo implantacao/PROGRAMAS-E-CAMADAS-ACER.md e o RESTAURAR-NO-ACER.md do backup",
]


def main(argv: list[str]) -> int:
    completo, sal, bk = "--completo" in argv, "--salvar" in argv, "--backup" in argv
    diz(f"# Atualização final · {time.strftime('%d/%m/%Y %H:%M')}")
    diz("\n## 1. Onde está cada sistema")
    git_estado(RAIZ, "Sistema")
    git_estado(INST, "Instituto")
    diz("\n## 2. Cópia dos bancos antes de mexer")
    copiar_bancos()
    diz("\n## 3. Arquivos gerados e instalações")
    regenerar()
    diz("\n## 4. Testes")
    testes(completo)
    diz("\n## 5. Serviços")
    servicos()
    tz = RAIZ / "ferramentas" / "teste_zero.py"
    if tz.is_file():
        c, s = rodar([PY, str(tz), "--sem-testes"], RAIZ, 3600)
        bloco("\n## 6. Teste zero (bots, arquivos, pendências)", "\n".join(s.splitlines()[-25:]))
    if sal:
        diz("\n## 7. Salvamento (git)")
        salvar()
    if bk:
        diz("\n## 8. Backup completo")
        backup()
    diz("\n## Pendências encontradas agora")
    for p in pend or ["nenhuma ✅"]:
        diz(f"- [ ] {p}" if pend else f"- {p}")
    diz("\n## Fora do código (dona, provedor, Acer)")
    for p in FORA_DO_CODIGO:
        diz(f"- [ ] {p}")
    (RAIZ / "RELATORIO-ATUALIZACAO-FINAL.md").write_text("\n".join(rel) + "\n", encoding="utf-8")
    print(f"\nRelatório: {RAIZ / 'RELATORIO-ATUALIZACAO-FINAL.md'}")
    return 0 if not pend else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
