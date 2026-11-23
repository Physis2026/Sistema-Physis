"""Vigia dos bots e sentinela dos serviços (M&A, versão de teste).

vigia: cada bot rodou dentro do intervalo esperado e sem erro (tabela mv_execucao).
sentinela: roda implantacao/verificar.sh (Linux) ou verificar.ps1 (Windows) e docker compose ps; [FALHA] vira alerta,
           [AVISO] vira atenção. Só observa: não reinicia nada (D49, aprovação humana).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from .mv import MV

RAIZ_REPO = Path(__file__).resolve().parents[2]

# Intervalo máximo (h) entre execuções sem erro. Agenda: bots_hora (atrasos, documentos) e resumo_7h (o resto).
LIMITE_H = {"atrasos": 9, "documentos": 2, "dados_iot": 2, "resumo": 26, "backup": 26, "paginas": 26, "inovacao": 26, "links": 26,
            "editais": 26, "simulacao": 26, "gestoes": 26, "bancos": 26, "acervo": 26, "ia": 26, "cursos": 26, "auditoria": 26,
            "financeiro": 26, "vencimentos": 26, "fatos": 26, "kit": 26, "repositorios": 26, "desenvolvimento": 26, "sincronizacao": 26, "melhoria": 26, "semanal": 7 * 24 + 6}
# sob demanda (sem rotina, versão enxuta): o vigia não cobra horário
SOB_DEMANDA = {"mercado"}


def bot_vigia(mv: MV, agora: float | None = None, limites: dict | None = None) -> dict:
    agora = agora or time.time()
    limites = limites or LIMITE_H
    inicio = mv.nova_rodada()
    out = {}
    instalado = mv.db.execute("SELECT MIN(inicio) FROM mv_execucao").fetchone()[0] or agora   # carência desde a 1ª rodada
    for bot, lim in limites.items():
        ok = mv.db.execute("SELECT MAX(fim) FROM mv_execucao WHERE bot=? AND erro=''", (bot,)).fetchone()[0]
        ult = mv.db.execute("SELECT fim, erro FROM mv_execucao WHERE bot=? ORDER BY fim DESC, id DESC LIMIT 1", (bot,)).fetchone()
        idade = round((agora - ok) / 3600, 1) if ok else None
        estado = "ok"
        if ult and ult[1]:
            estado = "erro"
            mv.alertar("vigia", "bot_com_erro", bot, "alerta", f"Última execução do bot {bot} terminou com erro: {ult[1][:200]}",
                       f"Ver mv_cli.log e rodar: python -m physis_hub.mv_cli bots {bot}")
        if ult is None and (agora - instalado) / 3600 <= lim:        # nunca rodou e ainda está dentro do prazo desde a instalação
            out[bot] = {"estado": "aguardando 1ª rodada", "idade_h": None, "limite_h": lim}
            continue
        if idade is None or idade > lim:
            estado = "parado" if estado == "ok" else estado
            quando = f"há {idade:.1f} h" if idade is not None else "nunca"
            mv.alertar("vigia", "bot_parado", bot, "alerta", f"Bot {bot} sem execução boa {quando} (limite {lim} h)",
                       "Conferir as tarefas PhysisMV\\bots_hora e resumo_7h (mv_cli agenda) e o computador do nó")
        out[bot] = {"estado": estado, "idade_h": idade, "limite_h": lim}
    mv.fechar_alertas_nao_vistos("vigia", inicio)
    mv.registrar_execucao("vigia", inicio, json.dumps(out))
    return out


def _linhas_verificar(texto: str) -> list[tuple[str, str]]:
    r = []
    for ln in texto.splitlines():
        s = ln.strip()
        for marca, nivel in (("[FALHA]", "alerta"), ("[AVISO]", "atencao")):
            if s.startswith(marca):
                r.append((nivel, s[len(marca):].strip()))
    return r


def _rodar(cmd: list[str], timeout: int = 120) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, repr(e)


def bot_sentinela(mv: MV, executar=_rodar, raiz: Path | None = None, which=shutil.which) -> dict:
    raiz = Path(raiz or RAIZ_REPO)
    inicio = mv.nova_rodada()
    out = {"verificar": None, "conteineres": None, "falhas": 0, "avisos": 0}
    impl = raiz / "implantacao"
    if os.name == "nt" and (impl / "verificar.ps1").exists():
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(impl / "verificar.ps1")]
    elif (impl / "verificar.sh").exists() and which("systemctl"):
        cmd = ["bash", str(impl / "verificar.sh")]
    else:
        cmd = None
    if cmd:
        cod, txt = executar(cmd)
        itens = _linhas_verificar(txt)
        for nivel, msg in itens:
            mv.alertar("sentinela", "servico", msg[:120], nivel, msg, "Ver a saída de verificar e o serviço indicado")
        out["verificar"] = {"codigo": cod, "itens": len(itens)}
        if cod == -1:
            mv.alertar("sentinela", "verificar_falhou", "verificar", "alerta", f"verificar não rodou: {txt[:200]}", "Rodar à mão")
    else:
        mv.alertar("sentinela", "sem_verificar", "verificar", "info",
                   "verificar.sh/ps1 não aplicável neste computador (sem systemd ou sem o script)", "Rodar no servidor físico")
        out["verificar"] = "não aplicável"
    comp = raiz / "servicos" / "docker-compose.yml"
    if comp.exists() and which("docker"):
        cod, txt = executar(["docker", "compose", "-f", str(comp), "ps", "-a", "--format", "json"])
        if cod == 0:
            linhas = []
            for x in txt.splitlines():
                x = x.strip()
                if x.startswith("["):
                    linhas += json.loads(x)
                elif x.startswith("{"):
                    linhas.append(json.loads(x))
            ruins = [c for c in linhas if c.get("State") != "running" or c.get("Health") == "unhealthy"]
            for c in ruins:
                nome = c.get("Service") or c.get("Name", "?")
                mv.alertar("sentinela", "conteiner", nome, "alerta",
                           f"Serviço {nome}: {c.get('State')} {c.get('Health') or ''}".strip(),
                           f"docker compose logs {nome}; reiniciar só com aprovação")
            out["conteineres"] = {"total": len(linhas), "com_problema": len(ruins)}
        else:
            mv.alertar("sentinela", "docker", "compose", "atencao", f"docker compose ps falhou: {txt[:200]}",
                       "Conferir se o Docker está rodando neste nó")
            out["conteineres"] = {"erro": txt[:200]}
    d = dict(mv.db.execute("SELECT gravidade, COUNT(*) FROM mv_alerta WHERE bot='sentinela' AND resolvido IS NULL "
                           "AND visto>=? GROUP BY gravidade", (inicio,)).fetchall())
    out["falhas"], out["avisos"] = d.get("alerta", 0), d.get("atencao", 0)
    mv.fechar_alertas_nao_vistos("sentinela", inicio)
    mv.registrar_execucao("sentinela", inicio, json.dumps(out))
    return out
