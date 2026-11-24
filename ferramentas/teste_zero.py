#!/usr/bin/env python3
r"""Teste zero (23/11/2026): a conferência completa ANTES do backup e da emissão. Só lê e testa; não muda nada.

    cd C:\physis\physis-ma-20261122-1bd599e
    py ferramentas\teste_zero.py

1 testes do Sistema · 2 testes do Instituto · 3 links no ar (M&A, Hub, Casa, InovaSTEM, Laboratório, Gestão)
4 diagnóstico · 5 arquivos (leitura, revisão, salvamento) · 6 auditoria dos bots · 7 tarefas repetidas · 8 fila dos bots
Relatório em C:\physis\teste-zero-AAAAMMDD-HHMM.md. "TUDO OK" = pode fazer o backup completo (backup_completo.py).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BASE = RAIZ.parent
PY = sys.executable
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}
rel, falhas = [], []
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass


def diz(t=""):
    print(t, flush=True)
    rel.append(t)


def item(nome, ok, det=""):
    diz(f"- {'✅' if ok else '❌'} {nome}" + (f": {det}" if det else ""))
    if not ok:
        falhas.append(f"{nome}: {det}")


def run(cmd, cwd, tempo=3600):
    try:
        return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=tempo, env=ENV)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "tempo esgotado")


def unittest(rotulo, hub):
    if not hub.is_dir():
        item(f"testes {rotulo}", False, f"pasta não encontrada: {hub}")
        return
    p = run([PY, "-m", "unittest", "discover", "-s", "tests"], hub)
    fim = [l for l in p.stderr.splitlines() if l.startswith(("Ran ", "OK", "FAILED"))]
    item(f"testes {rotulo}", p.returncode == 0, " · ".join(fim[-2:]))
    for l in [l for l in p.stderr.splitlines() if l.startswith(("FAIL:", "ERROR:"))][:15]:
        diz(f"  - {l}")


def marketing():
    """Marketing (bot próprio na pasta Marketing Physis, tarefas \\Physis\\Marketing* e app na porta 5000)."""
    diz("\n## 9. Marketing")
    sys.path.insert(0, str(RAIZ / "physis-hub"))
    from physis_hub import mv_bots  # noqa: E402
    pasta = mv_bots.DOCS / "Marketing Physis"
    bot = pasta / "instalador" / "bot" / "physis_marketing_bot.py"
    item("pasta Marketing Physis", pasta.is_dir(), str(pasta))
    item("bot do Marketing", bot.is_file(), str(bot))
    if os.name == "nt":
        q = run(["schtasks", "/Query", "/FO", "CSV", "/V", "/NH"], RAIZ, 120).stdout
        tarefas = [l for l in q.splitlines() if "\\Physis\\" in l and "Marketing" in l]
        item("tarefas do Marketing na agenda", bool(tarefas), f"{len(tarefas)} tarefa(s)")
        for l in tarefas:
            c = [x.strip('"') for x in l.split('","')]
            # colunas do schtasks /V em CSV: 1 nome, 2 próxima execução, 3 status, 5 última execução, 6 último resultado
            res = c[6] if len(c) > 6 else "?"
            item(f"  {c[1] if len(c) > 1 else l[:60]}", res in ("0", "267009", "267011"), f"última: {c[5] if len(c) > 5 else '?'} · resultado {res}")
    try:
        with urllib.request.urlopen("http://127.0.0.1:5000/", timeout=10) as r:
            item("app do Marketing (porta 5000)", r.status < 500, str(r.status))
    except Exception as e:  # noqa: BLE001
        item("app do Marketing (porta 5000)", False, str(e)[:100])


def pronto_para_versao_final():
    """O que ainda depende de decisão humana antes da versão final (não é falha técnica: é a lista do que falta)."""
    diz("\n## 10. Pronto para a versão final? (pendências de conteúdo e decisão)")
    import sqlite3
    sys.path.insert(0, str(RAIZ / "physis-hub"))
    from physis_hub.mv import pasta_padrao  # noqa: E402
    db = sqlite3.connect(f"file:{pasta_padrao() / 'physis-mv.db'}?mode=ro", uri=True)
    q = lambda s: (db.execute(s).fetchone() or [0])[0]  # noqa: E731
    linhas = [
        ("aprovações esperando decisão", q("SELECT COUNT(*) FROM mv_aprovacao WHERE estado NOT IN ('aprovado','ajustar','reprovado')")),
        ("rascunhos dos bots esperando aprovação", q("SELECT COUNT(*) FROM mv_pedido_bot WHERE estado IN ('rascunho','pronto')")),
        ("pedidos parados na fila dos bots", q("SELECT COUNT(*) FROM mv_pedido_bot WHERE estado='na_fila'")),
        ("perguntas abertas", q("SELECT COUNT(*) FROM mv_pergunta WHERE resposta=''")),
        ("tarefas 'Executar' (aprovadas, ainda não feitas)", q("SELECT COUNT(*) FROM mv_tarefa WHERE id LIKE 'exec-%' AND estado<>'feita'")),
        ("ajustes da Rafaella em aberto", q("SELECT COUNT(*) FROM mv_tarefa WHERE id LIKE 'ajuste-%' AND estado<>'feita'")),
        ("documentos com falha pelas regras", q("SELECT COUNT(*) FROM mv_documento WHERE situacao='falha'")),
        ("alertas que pedem intervenção", q("SELECT COUNT(*) FROM mv_alerta WHERE resolvido IS NULL AND gravidade='alerta'")),
    ]
    try:
        from physis_hub import mv_kit
        from physis_hub.mv import MV
        kit = mv_kit.situacao_kit(MV(str(pasta_padrao() / "physis-mv.db")))
        linhas.append(("documentos do kit que faltam", sum(1 for k in kit if k["estado"] == "falta")))
        linhas.append(("documentos do kit a revisar ou com [MARCADOR]", sum(1 for k in kit if k["estado"] in ("revisar", "com_marcador"))))
    except Exception as e:  # noqa: BLE001
        linhas.append((f"kit (não li: {e.__class__.__name__})", "?"))
    for nome, n in linhas:
        diz(f"- {'✅' if n == 0 else '⏳'} {nome}: {n}")
    diz("Tudo em ⏳ precisa de decisão ou conteúdo da equipe antes da versão final (o sistema não inventa: regra 1).")


def main():
    diz(f"# Teste zero · {time.strftime('%d/%m/%Y %H:%M')}")
    diz("\n## 1-2. Testes")
    if "--sem-testes" in sys.argv:          # a atualização final já roda os testes (24/11/2026: no PC da Physis levam ~30 min)
        diz("- testes pulados (--sem-testes): rodados pela atualização final")
    else:
        unittest("do Sistema", RAIZ / "physis-hub")
        unittest("do Instituto", BASE / "instituto-physis" / "physis-hub")
    diz("\n## 3. Links no ar")
    for nome, u in [("M&A", "http://127.0.0.1:8710/"), ("Monitoramento", "http://127.0.0.1:8710/api/mv/integracoes"), ("Hub", "http://127.0.0.1:8700/"),
                    ("Casa", "http://127.0.0.1:8701/"), ("InovaSTEM", "http://127.0.0.1:8702/"), ("Laboratório", "http://127.0.0.1:8702/laboratorio"),
                    ("Site da Physis", "http://127.0.0.1:8703/"), ("Gestão", "http://127.0.0.1:8703/gestao/")]:
        try:
            with urllib.request.urlopen(u, timeout=60) as r:
                item(f"{nome} ({u})", r.status == 200, str(r.status))
        except Exception as e:  # noqa: BLE001
            item(f"{nome} ({u})", False, str(e)[:120])
    diz("\n## 4. Diagnóstico")
    d = run([PY, str(RAIZ / "diagnostico_ma.py" if (RAIZ / "diagnostico_ma.py").is_file() else BASE / "diagnostico_ma.py")], RAIZ / "physis-hub", 600)
    nada = "Nada: esta instalação já está na versão final" in d.stdout
    item("diagnóstico (parte 8)", nada, "Nada a atualizar" if nada else d.stdout.split("## 8.")[-1].strip()[:400])
    diz("\n## 5. Arquivos (leitura, revisão, salvamento)")
    a = run([PY, "ferramentas/testar_arquivos.py"], RAIZ, 1800)
    sal = a.stdout.split("## C.")[-1].split("## Resultado")[0]
    item("salvamento", "FALHA" not in sal, "todos os itens OK" if "FALHA" not in sal else sal.strip()[:300])
    leit = [l for l in a.stdout.splitlines() if "FALHA" in l and "## C" not in l and "sem texto" not in l and "encontrados: 0" not in l]
    item("leitura", not leit, "; ".join(leit)[:300])
    diz("\n## 6. Auditoria dos bots")
    au = run([PY, "-m", "physis_hub.mv_cli", "bots", "auditoria"], RAIZ / "physis-hub", 900)
    try:
        cr = json.loads(au.stdout)["auditoria"]
        item("cruzamento dos bots", cr.get("falhas_cruzamento") == 0, f"falhas {cr.get('falhas_cruzamento')} · perguntas abertas {cr.get('perguntas_abertas')}")
    except Exception:  # noqa: BLE001
        item("cruzamento dos bots", False, (au.stdout + au.stderr)[-300:])
    diz("\n## 7. Tarefas repetidas")
    l = run([PY, "ferramentas/limpar_duplicadas_gestao.py"], RAIZ, 300)
    item("repetidas da Gestão", "repetidas vindas da Gestão: 0" in l.stdout, [x for x in l.stdout.splitlines() if "repetidas" in x][:1])
    diz("\n## 8. Fila dos bots (autônomos)")
    sys.path.insert(0, str(RAIZ / "physis-hub"))
    from physis_hub import mv_bots  # noqa: E402
    fila = mv_bots.SAIDA / "fila-claude.md"
    item("arquivo da fila", fila.is_file(), str(fila))
    marketing()
    pronto_para_versao_final()
    diz("\n## Resultado técnico: " + ("TUDO OK ✅ · pode fazer o backup completo" if not falhas else f"{len(falhas)} pendência(s)"))
    arq = BASE / f"teste-zero-{time.strftime('%Y%m%d-%H%M')}.md"
    arq.write_text("\n".join(rel) + "\n", encoding="utf-8")
    print(f"\nRelatório: {arq}")
    return 0 if not falhas else 1


if __name__ == "__main__":
    sys.exit(main())
