#!/usr/bin/env python3
r"""Diagnóstico do Physis M&A que está instalado (SÓ LEITURA: não muda banco, agenda nem arquivos).

    py diagnostico_ma.py                                   (procura sozinho em C:\physis)
    py diagnostico_ma.py "C:\physis\physis-ma-20261122-1bd599e"

Gera diagnostico-ma-AAAAMMDD-HHMM.md na pasta onde for rodado: versão, bots, agenda, banco, servidor e a lista
"o que precisa ser atualizado" comparada com a versão final de 22/11/2026. Mande esse arquivo para a equipe.
"""
from __future__ import annotations

import json
import os
import platform
import re
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

# ---- o que a versão final (22/11/2026, 23h55) tem ---------------------------------------------------------------------
FINAL_BOTS = {"atrasos", "documentos", "resumo", "backup", "paginas", "inovacao", "links", "editais", "dados_iot", "simulacao", "gestoes",
              "bancos", "acervo", "ia", "cursos", "financeiro", "vencimentos", "fatos", "kit", "repositorios", "desenvolvimento",
              "sincronizacao", "melhoria", "auditoria", "vigia", "sentinela", "sala", "mercado", "semanal"}
FINAL_MODULOS = {"mv_vigia": "vigia e sentinela", "mv_sala": "sala dos bots", "mv_bots_extra": "editais, dados-iot, simulação, gestões, bancos, acervo",
                 "ia_physis": "IA Physis", "mv_cursos": "mapa de cursos", "mv_integracoes": "aba Monitoramento", "mv_auditoria": "auditoria e caixa de perguntas",
                 "mv_ecossistema": "mercado e parcerias (GIS)", "mv_financeiro": "financeiro e vencimentos", "mv_kit": "kit 26/11, melhoria, semanal",
                 "mv_fatos": "base de fatos", "mv_repositorios": "repositórios (Marketing Physis)", "mv_desenvolvimento": "painel Desenvolvimento",
                 "mv_sincronizacao": "sincronização dos módulos"}
FINAL_TAREFAS = {"bots_hora", "atrasos_8h", "resumo_7h", "revisao_semanal", "painel", "hub"}
FINAL_ROTAS = {"/api/mv/saude": "núcleo", "/api/mv/integracoes": "aba Monitoramento", "/api/mv/ia?q=agua": "IA Physis"}

AGENDA_TXT = [""]   # ações das tarefas lidas (erro antigo de bot só conta se a agenda ainda o chama)


def achar_instalacao(arg: str | None) -> Path | None:
    cands = [Path(arg)] if arg else []
    if not arg:
        base = Path("C:/physis") if os.name == "nt" else Path.home()
        if base.is_dir():
            achados = [p for p in base.glob("*/physis-hub/physis_hub/mv_cli.py")] + [p for p in base.glob("*/*/physis-hub/physis_hub/mv_cli.py")]
            achados.sort(key=lambda p: ((p.parents[2] / ".git").exists(), p.parents[2].name.startswith("physis-ma-"), p.stat().st_mtime), reverse=True)  # com Git (clone) primeiro
            if len(achados) > 1:
                print("Instalações encontradas (uso a primeira): " + " | ".join(str(p.parents[2]) for p in achados))   # a versão mais nova primeiro
            cands += [p.parents[1] for p in achados][:10]
    for c in cands:
        for raiz in (c, c / "physis-hub"):
            if (raiz / "physis_hub" / "mv_cli.py").is_file():
                return raiz
    return None


def git(pasta: Path, *a) -> str | None:
    try:
        p = subprocess.run(["git", "-C", str(pasta), *a], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        return p.stdout.strip() if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def main(argv: list[str]) -> int:
    linhas, falta = [], []
    diz = lambda t="": (print(t), linhas.append(t))  # noqa: E731
    hub = achar_instalacao(argv[0] if argv else None)
    diz(f"# Diagnóstico do Physis M&A · {time.strftime('%d/%m/%Y %H:%M')}")
    diz(f"Computador: {platform.node()} · Windows/SO: {platform.platform()} · Python: {sys.version.split()[0]}")
    if not hub:
        diz("\n**Não achei a instalação do M&A.** Rode de novo dizendo a pasta: py diagnostico_ma.py \"C:\\caminho\\da\\pasta\"")
        return _gravar(linhas)
    raiz = hub.parent if hub.name == "physis-hub" else hub
    diz(f"Instalação: {hub}")
    # versão
    diz("\n## 1. Versão")
    h = git(raiz, "log", "-1", "--format=%h · %ci · %s")
    diz(f"- Git: {h or 'pasta sem Git (cópia solta)'}")
    st = git(raiz, "status", "--porcelain") if h else ""
    if st:
        diz("- **Há arquivos alterados sem commit nesta instalação** (guardar antes de atualizar):")
        for l in st.splitlines()[:40]:
            diz(f"  - {l}")
    if h:
        tem = git(raiz, "merge-base", "--is-ancestor", "6643e5b", "HEAD")
        diz(f"- Tem o trabalho do GitHub de 22/11 20h37 (6643e5b)? {'sim' if tem is not None else 'não ou desconhecido'}")
    # código
    diz("\n## 2. Bots e módulos")
    sys.path.insert(0, str(hub))
    bots = set()
    try:
        from physis_hub import mv_bots  # noqa: E402
        bots = set(mv_bots.BOTS)
        diz(f"- Bots instalados ({len(bots)}): {', '.join(sorted(bots))}")
    except Exception as e:  # noqa: BLE001
        diz(f"- **Não consegui carregar os bots:** {e!r}"[:300])
    faltam_bots = sorted(FINAL_BOTS - bots)
    if faltam_bots:
        falta.append(f"Bots que faltam ({len(faltam_bots)}): {', '.join(faltam_bots)}")
    if "juridico" in bots:
        falta.append("Bot 'juridico' ainda existe: na versão final virou 'vencimentos'")
    for m, oque in FINAL_MODULOS.items():
        if not (hub / "physis_hub" / f"{m}.py").is_file():
            falta.append(f"Módulo {m}.py ({oque})")
    mv_html = hub / "web" / "mv.html"
    if mv_html.is_file() and 'data-v="monitoramento"' not in mv_html.read_text(encoding="utf-8", errors="replace"):
        falta.append("Aba Monitoramento no mv.html")
    # agenda
    diz("\n## 3. Agenda do Windows (PhysisMV)")
    if os.name == "nt":
        try:
            p = subprocess.run(["schtasks", "/Query", "/FO", "CSV", "/V"], capture_output=True, text=True, timeout=60, errors="replace")
            tarefas = {}
            for l in p.stdout.splitlines():
                m = re.search(r'"\\PhysisMV\\([^"]+)"', l)
                if m:
                    campos = [c.strip('"') for c in l.split('","')]
                    tarefas[m.group(1)] = campos
            for n, c in sorted(tarefas.items()):
                acao = next((x for x in c if "physis_hub." in x), "")   # mv_cli e, na tarefa hub, servidor
                AGENDA_TXT[0] += " " + acao
                diz(f"- {n}: {acao[-140:]}")
                if str(raiz) not in acao and str(hub) not in acao:
                    falta.append(f"Tarefa PhysisMV\\{n} aponta para outra pasta (não esta instalação)")
            for n in sorted(set(tarefas) - FINAL_TAREFAS):
                falta.append(f"Tarefa antiga PhysisMV\\{n} (não existe na versão final; o instalador novo pergunta se pode apagar)")
            for n in sorted(FINAL_TAREFAS - set(tarefas)):
                falta.append(f"Tarefa PhysisMV\\{n} não existe (agenda da versão final)")
        except Exception as e:  # noqa: BLE001
            diz(f"- não consegui ler a agenda: {e!r}"[:200])
    else:
        diz("- (só no Windows)")
    # banco
    diz("\n## 4. Banco do M&A")
    banco = None
    try:
        from physis_hub.mv import pasta_padrao  # noqa: E402
        banco = pasta_padrao() / "physis-mv.db"
    except Exception as e:  # noqa: BLE001
        diz(f"- não consegui achar a pasta do banco: {e!r}"[:200])
    diz(f"- PHYSIS_MV_DADOS = {os.environ.get('PHYSIS_MV_DADOS') or '(não definida)'}")
    if banco and banco.is_file():
        diz(f"- Banco: {banco} · {banco.stat().st_size // 1024} KB · alterado em {time.strftime('%d/%m/%Y %H:%M', time.localtime(banco.stat().st_mtime))}")
        db = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
        q = lambda s, *a: db.execute(s, a).fetchall()  # noqa: E731
        try:
            diz(f"- Tarefas: {q('SELECT COUNT(*) FROM mv_tarefa')[0][0]} · metas: {q('SELECT COUNT(*) FROM mv_meta')[0][0]} · "
                f"alertas abertos: {q('SELECT COUNT(*) FROM mv_alerta WHERE resolvido IS NULL')[0][0]}")
            esperado = {}
            try:
                from physis_hub import mv as _mvmod  # noqa: E402
                m = sqlite3.connect(":memory:"); m.executescript(_mvmod.ESQUEMA) if hasattr(_mvmod, "ESQUEMA") else None
                esperado = {t: [c[1] for c in m.execute(f"PRAGMA table_info({t})")] for (t,) in m.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            except Exception:  # noqa: BLE001
                pass
            for (t,) in q("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'mv_%'"):
                cols = [c[1] for c in q(f"PRAGMA table_info({t})")]
                if t in esperado and cols != esperado[t]:
                    diz(f"- Tabela {t} diferente do código: banco {cols} × código {esperado[t]}")
            diz("- Última execução de cada bot:")
            agora = time.time()
            for bot, fim, erro in q("SELECT bot, MAX(fim), erro FROM mv_execucao GROUP BY bot ORDER BY bot"):
                diz(f"  - {bot}: há {(agora - (fim or 0)) / 3600:.1f} h{' · ERRO: ' + erro[:120] if erro else ''}")
                if erro and "KeyError" in erro and re.search(rf"\b{re.escape(bot)}\b", AGENDA_TXT[0]):
                    falta.append(f"Bot '{bot}' chamado pela agenda não existe nesta versão ({erro[:60]}): agenda antiga")
            parados = [b for b, fim in q("SELECT bot, MAX(fim) FROM mv_execucao GROUP BY bot") if agora - (fim or 0) > 26 * 3600]
            if parados:
                falta.append(f"Bots sem rodar há mais de 26 h: {', '.join(parados)} (agenda parada ou computador desligado)")
            try:
                ab = q("SELECT COUNT(*) FROM mv_pergunta WHERE resposta=''")[0][0]
                diz(f"- Perguntas abertas na caixa: {ab}")
            except sqlite3.Error:
                diz("- Caixa de perguntas: ainda não existe nesta versão")
        except sqlite3.Error as e:
            diz(f"- erro lendo o banco: {e}")
    else:
        diz(f"- **Banco não encontrado** em {banco}")
        falta.append("Banco do M&A não encontrado no lugar que esta versão procura (definir PHYSIS_MV_DADOS)")
    # servidor
    diz("\n## 5. Servidor do M&A (http://127.0.0.1:8710)")
    for rota, oque in FINAL_ROTAS.items():
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:8710{rota}", timeout=8) as r:
                diz(f"- {rota}: responde ({r.status})")
        except urllib.error.HTTPError as e:
            diz(f"- {rota}: HTTP {e.code}")
            if e.code == 404:
                falta.append(f"Rota {rota} ({oque}) não existe no servidor que está rodando (servidor ANTIGO aberto na porta 8710: fechar e abrir o novo)")
        except Exception as e:  # noqa: BLE001
            diz(f"- {rota}: sem resposta ({type(e).__name__})")
            if rota == "/api/mv/saude":
                falta.append("O servidor do M&A não está rodando (tarefa 'painel' ou 'py -m physis_hub.mv_cli servir')")
                break
    # marketing
    padrao = Path.home() / "OneDrive - Physis Engineering" / "Documents"
    cands = [Path(os.environ[v]) / "Documents" for v in ("OneDriveCommercial", "OneDrive") if os.environ.get(v)] + [padrao]
    docs = Path(os.environ["PHYSIS_DOCS"]) if os.environ.get("PHYSIS_DOCS") else next((c for c in cands if (c / "Sistema Physis").is_dir()), padrao)
    diz("\n## 6. Pastas do OneDrive lidas pelos bots")
    diz(f"- Documents: {docs}" + ("" if docs.is_dir() else "  (NÃO encontrada)"))
    for grupo in (("Sistema Physis",), ("Casa Physis",), ("Instituto Physis",), ("Global Sourh Alliance", "Global South Alliance"), ("Estermic",)):
        achada = next((docs / n for n in grupo if (docs / n).is_dir()), None)
        diz(f"- {grupo[0]}: {'OK (' + achada.name + ')' if achada else 'NÃO encontrada'}")
        if not achada:
            falta.append(f"Pasta {docs / grupo[0]} não encontrada (OneDrive: 'Sempre manter neste dispositivo')")
    mk = docs / "Marketing Physis"
    diz(f"- {mk}: {'existe' if mk.is_dir() else 'NÃO encontrado'}{' · Git: ' + (git(mk, 'log', '-1', '--format=%h %s') or 'sem commit') if mk.is_dir() else ''}")
    # integração
    diz("\n## 7. Integração (Instituto Physis e sincronização)")
    inst = raiz.parent / "instituto-physis"
    if inst.is_dir():
        diz(f"- Instituto Physis em {inst}: {git(inst, 'log', '-1', '--format=%h %ci %s') or 'sem Git'}")
        if git(inst, "status", "--porcelain"):
            falta.append("Instituto Physis com alterações sem commit (a sincronização automática fica parada até salvar)")
        if banco and banco.is_file():
            try:
                r = sqlite3.connect(f"file:{banco}?mode=ro", uri=True).execute(
                    "SELECT resumo, fim FROM mv_execucao WHERE bot='sincronizacao' ORDER BY fim DESC LIMIT 1").fetchone()
                diz(f"- Última sincronização: {time.strftime('%d/%m %H:%M', time.localtime(r[1])) if r else 'nunca'} · {(r[0] if r else '')[:300]}")
            except sqlite3.Error:
                pass
    else:
        diz(f"- Instituto Physis NÃO encontrado em {inst} (a sincronização e o bot páginas procuram ali)")
        falta.append(f"Repositório do Instituto ao lado do sistema: git clone https://github.com/Physis2026/instituto-physis \"{inst}\"")
    # resumo
    diz("\n## 8. O que precisa ser atualizado")
    if falta:
        for f in falta:
            diz(f"- [ ] {f}")
        diz("\nPara atualizar: PASSO-A-PASSO-ATUALIZADO.md (área de arquivos). Mande este relatório para a equipe.")
    else:
        diz("- Nada: esta instalação já está na versão final.")
    return _gravar(linhas)


def _gravar(linhas: list[str]) -> int:
    f = Path(__file__).resolve().parent / f"diagnostico-ma-{time.strftime('%Y%m%d-%H%M')}.md"
    f.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"\nRelatório salvo em: {f}")
    if os.name == "nt" and sys.stdin and sys.stdin.isatty():
        input("Aperte Enter para fechar...")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
