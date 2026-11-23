"""Controle do desenvolvimento por módulo (pedido da dona, 22/11/2026).

O M&A continua sendo a FONTE ÚNICA: tarefas, aprovações e testes. Este módulo:
- monta o painel "Desenvolvimento" de cada módulo (`dados`), servido ao M&A em /api/mv/desenvolvimento;
- grava `sistema/desenvolvimento-dados.js` (bot "desenvolvimento"), que os módulos, as plataformas internas e a Gestão
  carregam com <script src>. Assim o mesmo painel aparece dentro de cada módulo, mesmo aberto do disco, sem internet
  e sem responder nada duas vezes.
Nada aqui altera tarefas: só lê.
"""
import json
import re
import time
from datetime import date
from pathlib import Path

from .mv import MV

# módulo → onde fica, o que conta como dele (tarefas e aprovações)
MODULOS = {
    "modelagem3d": {"nome": "Modelagem 3D", "nome_en": "3D modelling",
                    "arquivo": "modulos/modelagem3d/modelagem-3d.html",
                    "descricao": "Visualizador STL/OBJ, galeria com licença, pedidos de impressão (qualquer impressora de filamento ou resina) e escaneados",
                    "regex": r"\b3D\b|STL|\bOBJ\b|impress[aã]o 3D|escane|modelagem 3D",
                    "aprovacoes": ["ap-mv-3d", "ap-checklist-f23"]},
    "planejador": {"nome": "Planejador (BIM, GIS, solar)", "nome_en": "Planner (BIM, GIS, solar)",
                   "arquivo": "modulos/planejador/planejador-physis.html",
                   "descricao": "Projeto da instalação: BIM/IFC, GIS, planta solar e carga térmica",
                   "regex": r"Planejador|\bBIM\b|\bIFC\b|\bGIS\b|georref|planta solar|carga t[eé]rmica",
                   "aprovacoes": ["ap-checklist-f23"]},
    "estermic": {"nome": "Estermic · AVAC personalizado", "nome_en": "Estermic · custom HVAC",
                 "arquivo": "modulos/estermic/estermic-avac.html",
                 "descricao": "Cópia personalizada do módulo AVAC para a Estermic (4 subprojetos)",
                 "projetos": ["Estermic"], "regex": r"Estermic|\bAVAC\b",
                 "aprovacoes": ["ap-p0-estermic-ryan", "ap-p0-estermic-teste"]},
    "gemeo-casa": {"nome": "Gêmeo digital da Casa Physis", "nome_en": "Casa Physis digital twin",
                   "arquivo": "physis-hub/web/painel.html",
                   "descricao": "Gêmeo digital de projeto (G0–G5) e artigos da evolução",
                   "regex": r"G[eê]meo|Casa Physis · plataforma inicial", "aprovacoes": []},
    "inovastem-3d": {"nome": "InovaSTEM · Physis 3D (site e plataforma)", "nome_en": "InovaSTEM · Physis 3D (site and platform)",
                     "arquivo": "instituto-physis (ramo inovastem): plataforma InovaSTEM",
                     "descricao": "Foto→3D, ferramentas tipo SketchUp, BIM, montagens e desenho técnico para a comunidade",
                     "regex": r"InovaSTEM.*(3D|site|plataforma)|Physis 3D|Site do Instituto",
                     "aprovacoes": ["ap-site-inovastem"]},
}


def _tarefas_do(mv: MV, cfg: dict) -> list[dict]:
    rx = re.compile(cfg.get("regex") or r"$^", re.I)
    pj = set(cfg.get("projetos") or [])
    out = []
    for t in mv.gantt():
        if t.get("projeto") in pj or rx.search(f"{t.get('projeto', '')} {t.get('titulo', '')}"):
            out.append(t)
    return out


def _regressao(mv: MV) -> dict:
    r = mv.db.execute("SELECT inicio, resumo, erro FROM mv_execucao WHERE bot='regressao' ORDER BY inicio DESC, id DESC LIMIT 1").fetchone()
    if not r:
        return {"quando": "", "resultado": "sem registro"}
    txt = str(r["erro"] or r["resumo"] or "")
    return {"quando": time.strftime("%Y-%m-%d %H:%M", time.localtime(r["inicio"])), "resultado": txt[:300]}


def dados(mv: MV) -> dict:
    hoje = date.today().isoformat()
    from . import mv_comandos
    mv_comandos._garantir(mv)          # banco novo: cria as tabelas de aprovação antes de ler (22/11/2026)
    aprov = {a["id"]: a for a in mv.db.execute("SELECT id, item, estado, prazo FROM mv_aprovacao").fetchall()}
    reg = _regressao(mv)
    mods = {}
    for k, cfg in MODULOS.items():
        ts = _tarefas_do(mv, cfg)
        ab = [t for t in ts if t["estado"] != "feita"]
        prox = sorted([t for t in ab if (t.get("fim") or t.get("plan_fim"))], key=lambda t: t.get("fim") or t.get("plan_fim"))[:4]
        aps = [dict(aprov[i]) for i in cfg["aprovacoes"] if i in aprov]
        mods[k] = {"nome": cfg["nome"], "nome_en": cfg["nome_en"], "arquivo": cfg["arquivo"], "descricao": cfg["descricao"],
                   "tarefas": {"total": len(ts), "feitas": len(ts) - len(ab), "revisao": sum(t["estado"] == "revisao" for t in ts),
                               "abertas": len(ab), "atrasadas": sum(bool(t.get("atrasada")) for t in ts)},
                   "proximas": [{"titulo": t["titulo"][:140], "fim": t.get("fim") or t.get("plan_fim"), "estado": t["estado"],
                                 "estimada": bool(t.get("data_estimada"))} for t in prox],
                   "aprovacoes": [{"item": a["item"][:140], "estado": a["estado"], "prazo": a["prazo"]} for a in aps]}
    return {"gerado": time.strftime("%Y-%m-%d %H:%M"), "hoje": hoje, "fonte": "Physis M&A (fonte única)", "regressao": reg, "modulos": mods}


def gravar(mv: MV, raiz: Path | None = None) -> dict:
    """Grava sistema/desenvolvimento-dados.js no repositório do Sistema Physis (pasta-irmã de physis-hub)."""
    raiz = raiz or Path(__file__).resolve().parents[2]
    d = dados(mv)
    alvo = raiz / "sistema" / "desenvolvimento-dados.js"
    alvo.write_text("/* Gerado pelo bot \"desenvolvimento\" do Physis M&A. Não editar: a fonte é o M&A. */\n"
                    f"window.PHYSIS_DESENV = {json.dumps(d, ensure_ascii=False, indent=1)};\n", encoding="utf-8")
    return {"arquivo": str(alvo), "modulos": len(d["modulos"])}
