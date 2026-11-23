"""Base de fatos do ecossistema Physis (bot "fatos", 22/11/2026): fonte única dos fatos + checagem de consistência nos
documentos + preenchimento das versões zero do kit.

- Cada fato é escrito UMA vez em fatos.json (pasta PHYSIS_MV_SAIDA/fatos; a equipe edita): chave, valor, pilar, fonte,
  e as formas ERRADAS que não podem aparecer nos documentos (regex). Valor vazio ou [MARCADOR] vira pergunta na caixa.
- A checagem lê os documentos das pastas (mesmo leitor do bot documentos) e aponta onde uma forma errada aparece.
- As regras das decisões (D40, D42, D61, D66, D34, PDI P1–P22, D67) continuam no bot documentos: aqui não se repetem.
- O kit usa os fatos na versão zero (razão social, nomes dos pilares, visão, missão…).
Regra 1: nenhum fato é inventado. O que vem semeado tem a fonte (decisão ou arquivo do sistema).
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

SEMENTE = [
    {"chave": "razao_social", "valor": "Physis Engineering Ltda.", "pilar": "engineering",
     "fonte": "decisão da dona, 22/11/2026 (rodapé só com a razão social)", "errado": []},
    {"chave": "pilares", "valor": "Physis Engineering, Casa Physis, Instituto Physis, InovaSTEM, Global South Alliance", "pilar": "ecossistema",
     "fonte": "MV.md (frentes do M&A) e pedido de 22/11/2026", "errado": []},
    {"chave": "horizonte", "valor": "2027–2031", "pilar": "ecossistema", "fonte": "D40 (o bot documentos confere)", "errado": []},
    {"chave": "fase0_marco", "valor": "31/01/2027", "pilar": "ecossistema", "fonte": "mv_semente.py (marco Fase 0 fechada)", "errado": []},
    {"chave": "pdi_projetos", "valor": "22 projetos (P1–P22)", "pilar": "instituto", "fonte": "atualização de 18/11/2026 (o bot documentos confere)", "errado": []},
    {"chave": "visao", "valor": "[MARCADOR]", "pilar": "ecossistema", "fonte": "", "errado": []},
    {"chave": "missao", "valor": "[MARCADOR]", "pilar": "ecossistema", "fonte": "", "errado": []},
    {"chave": "visao_instituto", "valor": "[MARCADOR]", "pilar": "instituto", "fonte": "", "errado": []},
    {"chave": "missao_instituto", "valor": "[MARCADOR]", "pilar": "instituto", "fonte": "", "errado": []},
    {"chave": "proposta_inovastem", "valor": "[MARCADOR]", "pilar": "inovastem", "fonte": "", "errado": []},
    {"chave": "proposta_casa", "valor": "[MARCADOR]", "pilar": "casa", "fonte": "", "errado": []},
    {"chave": "proposta_gsa", "valor": "[MARCADOR]", "pilar": "gsa", "fonte": "", "errado": []},
]
VAZIO = re.compile(r"^\s*$|\[MARCADOR\]|\[A PREENCHER\]", re.I)


def pasta(saida: Path | None = None) -> Path:
    from . import mv_bots
    return Path(saida or (mv_bots.SAIDA / "fatos"))


def carregar(saida: Path | None = None) -> list[dict]:
    """fatos.json; na primeira vez grava a semente (a equipe completa e corrige ali)."""
    f = pasta(saida) / "fatos.json"
    if not f.is_file():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(SEMENTE, ensure_ascii=False, indent=1), encoding="utf-8")
        return [dict(x) for x in SEMENTE]
    return json.loads(f.read_text(encoding="utf-8"))


def valor(fatos: list[dict], chave: str) -> str | None:
    """Valor do fato, ou None se ainda não foi preenchido."""
    v = next((x.get("valor", "") for x in fatos if x.get("chave") == chave), "")
    return None if VAZIO.search(v or "") else v


def checar(fatos: list[dict], raizes: list[Path], ler=None) -> list[dict]:
    """Onde uma forma errada de algum fato aparece nos documentos."""
    from .mv_bots import EXTS, IGNORAR, texto_de
    ler = ler or texto_de
    regras = [(x["chave"], re.compile(p, re.I)) for x in fatos for p in x.get("errado") or []]
    if not regras:
        return []
    achados = []
    for raiz in raizes:
        if not raiz.is_dir():
            continue
        for dirpath, dirs, arquivos in os.walk(raiz):
            if IGNORAR.search(dirpath + os.sep):
                dirs[:] = []
                continue
            for a in arquivos:
                p = Path(dirpath) / a
                if p.suffix.lower() not in EXTS:
                    continue
                t = ler(p)
                for chave, rx in regras:
                    m = rx.search(t or "")
                    if m:
                        achados.append({"arquivo": str(p), "nome": a, "fato": chave, "trecho": t[max(0, m.start() - 40):m.end() + 40]})
    return achados


def bot_fatos(mv, saida: Path | None = None, raizes: list[Path] | None = None, ler=None) -> dict:
    from . import mv_bots, mv_comandos
    inicio = mv.nova_rodada()
    fatos = carregar(saida)
    for x in fatos:                                   # fato vazio vira pergunta (uma vez)
        if valor(fatos, x["chave"]) is None:
            mv_comandos.perguntar(mv, f"Base de fatos: qual é o texto oficial de \"{x['chave']}\" ({x.get('pilar', '')})? "
                                      "Ele entra em todas as apresentações e versões zero.", [], f"pendencia:fato:{x['chave']}",
                                  ["m&a", "documentos"], "2026-11-26")
    # resposta dada na caixa → grava no fatos.json (fonte única)
    mudou = False
    for x in fatos:
        if valor(fatos, x["chave"]) is None:
            r = mv.db.execute("SELECT resposta FROM mv_pergunta WHERE origem=? AND resposta<>''", (f"pendencia:fato:{x['chave']}",)).fetchone()
            if r:
                x["valor"], x["fonte"] = r[0], f"caixa de perguntas do M&A, {time.strftime('%d/%m/%Y')}"
                mudou = True
    if mudou:
        (pasta(saida) / "fatos.json").write_text(json.dumps(fatos, ensure_ascii=False, indent=1), encoding="utf-8")
    raizes = raizes if raizes is not None else mv_bots.pastas_documentos()
    achados = checar(fatos, raizes, ler)
    for a in achados:
        mv.alertar("fatos", "inconsistente", f"{a['fato']}:{a['nome']}"[:150], "atencao",
                   f"{a['nome']}: forma diferente da base de fatos ({a['fato']}): …{a['trecho']}…", "Corrigir pelo valor oficial em fatos.json")
    vazios = [x["chave"] for x in fatos if valor(fatos, x["chave"]) is None]
    r = {"fatos": len(fatos), "preenchidos": len(fatos) - len(vazios), "vazios": vazios, "inconsistencias": len(achados)}
    mv.fechar_alertas_nao_vistos("fatos", inicio)
    mv.registrar_execucao("fatos", inicio, json.dumps(r, ensure_ascii=False))
    return r
