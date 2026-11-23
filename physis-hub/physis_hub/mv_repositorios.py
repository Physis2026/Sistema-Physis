"""Repositórios da Physis fora do Sistema Physis (bot "repositorios", 22/11/2026). Primeiro: marketing-physis.

O M&A acompanha cada repositório Git listado (padrão: Documents\Marketing Physis no OneDrive; senão C:\physis\marketing-physis):
- estado do Git: ramo, último commit (data e mensagem), alterações não salvas, se há cópia fora do computador (remote);
- inventário por tipo: planos e documentos, planilhas, logos e imagens, dados (CSV/JSON);
- os documentos entram no bot documentos (validade, [MARCADOR], regras das decisões) e no índice da IA Physis.
Só lê: nunca faz commit, push ou apaga nada (D49). Comandos Git só locais (sem rede).
Lista: PHYSIS_REPOSITORIOS (JSON [{"id","nome","caminho","area"}]) ou repositorios.json em PHYSIS_MV_SAIDA/repositorios.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[2]
def padrao() -> list[dict]:
    """Marketing Physis na pasta Documents do OneDrive (decisão de 22/11/2026: …\\OneDrive - Physis Engineering\\Documents\\Marketing Physis),
    pela mesma raiz que o M&A já usa (PHYSIS_DOCS), sem nome de usuário no código. Segunda opção: a pasta irmã do sistema."""
    from . import mv_bots
    candidatos = [mv_bots.DOCS / "Marketing Physis", RAIZ_REPO.parent / "marketing-physis"]
    escolhido = next((c for c in candidatos if c.is_dir()), candidatos[0])
    return [{"id": "marketing-physis", "nome": "Marketing Physis", "caminho": str(escolhido), "area": "marketing"}]
TIPOS = {"documentos": {".md", ".txt", ".odt", ".docx", ".pdf", ".odp", ".pptx"}, "planilhas": {".ods", ".xlsx", ".xls", ".csv"},
         "logos_imagens": {".svg", ".png", ".jpg", ".jpeg", ".webp", ".ai", ".eps"}, "dados": {".json", ".yaml", ".yml"}}


def lista(saida: Path | None = None) -> list[dict]:
    env = os.environ.get("PHYSIS_REPOSITORIOS", "").strip()
    if env:
        return json.loads(env)
    from . import mv_bots
    f = Path(saida or (mv_bots.SAIDA / "repositorios")) / "repositorios.json"
    if f.is_file():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return padrao()


def caminhos_existentes() -> list[Path]:
    """Pastas dos repositórios que existem neste computador (para o bot documentos e a IA Physis)."""
    try:
        return [Path(r["caminho"]) for r in lista() if Path(r["caminho"]).is_dir()]
    except Exception:  # noqa: BLE001
        return []


def _git(pasta: Path, *args: str) -> str | None:
    if not shutil.which("git"):
        return None
    try:
        p = subprocess.run(["git", "-C", str(pasta), *args], capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace",          # Windows: sem isto os acentos do Git viravam "Ã§" (teste de 23/11)
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        return p.stdout.strip() if p.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def estado(r: dict) -> dict:
    p = Path(r["caminho"])
    out = {"id": r["id"], "nome": r.get("nome", r["id"]), "caminho": str(p), "existe": p.is_dir()}
    if not out["existe"]:
        return out
    out["git"] = (p / ".git").exists()
    if out["git"]:
        out["ramo"] = _git(p, "rev-parse", "--abbrev-ref", "HEAD")
        log = _git(p, "log", "-1", "--format=%h%x1f%cI%x1f%s")
        if log:
            h, data, msg = log.split("\x1f", 2)
            out["ultimo_commit"] = {"hash": h, "data": data, "mensagem": msg}
        st = _git(p, "status", "--porcelain")
        out["nao_salvos"] = len([l for l in (st or "").splitlines() if l.strip()]) if st is not None else None
        out["remotos"] = (_git(p, "remote") or "").split()
    inv = {k: 0 for k in TIPOS}
    for f in p.rglob("*"):
        if ".git" in f.parts or not f.is_file():
            continue
        for k, exts in TIPOS.items():
            if f.suffix.lower() in exts:
                inv[k] += 1
    out["inventario"] = inv
    return out


def bot_repositorios(mv, agora: float | None = None) -> dict:
    inicio = mv.nova_rodada()
    agora = agora or time.time()
    res = []
    for r in lista():
        e = estado(r)
        res.append(e)
        ref = e["id"]
        if not e["existe"]:
            mv.alertar("repositorios", "ausente", ref, "info", f"Repositório {e['nome']} não encontrado em {e['caminho']}",
                       "Conferir o caminho (PHYSIS_REPOSITORIOS) ou rodar no computador onde ele está")
            continue
        if not e.get("git"):
            mv.alertar("repositorios", "sem_git", ref, "atencao", f"{e['nome']}: a pasta não é um repositório Git", "git init -b main; git add -A; git commit")
            continue
        if not e.get("ultimo_commit"):
            mv.alertar("repositorios", "sem_commit", ref, "atencao", f"{e['nome']}: repositório sem nenhum commit", "git add -A; git commit -m \"...\"")
        if e.get("nao_salvos"):
            mv.alertar("repositorios", "nao_salvos", ref, "atencao", f"{e['nome']}: {e['nao_salvos']} arquivo(s) alterado(s) sem commit",
                       f"cd {e['caminho']}; git add -A; git commit -m \"...\"")
        if not e.get("remotos"):
            mv.alertar("repositorios", "sem_copia", ref, "atencao", f"{e['nome']}: sem cópia fora deste computador (nenhum remote)",
                       "Criar a cópia no servidor da Physis (ou espelho no GitHub) e fazer git push; o backup do servidor também cobre")
    mv.fechar_alertas_nao_vistos("repositorios", inicio)
    r = {"repositorios": res}
    mv.registrar_execucao("repositorios", inicio, json.dumps(r, ensure_ascii=False))
    return r
