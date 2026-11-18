#!/usr/bin/env python3
"""Gera "24_Fase2_por_Pessoa_e_Modulo" (.md e .ods) a partir das tarefas da Gestão e do mapa de kits.

    python ferramentas/documentos/fase2_por_modulo.py --docs "<pasta Documents/Sistema Physis>"

Por módulo: cada tarefa (a cópia do responsável principal, sem repetir as cópias "(com …)") vai para os módulos cujo
nome ou palavra-chave aparece no título; o que não cita módulo fica em "Geral (bloco da Fase 2)".
Por pessoa: total, principal e co-responsável, e a lista das tarefas principais por horizonte.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
HORIZ = {"micro": "Esta semana", "media": "Próximas semanas", "longa": "Próximos meses (Fase 2)"}
EXTRA = {  # palavras que também apontam para o módulo (além do nome do kit)
    "planejador": ["planejador", "gis", "bim", "ifc", "terreno", "mapeamento"],
    "solar": ["solar", "fotovolt", "inversor", "fio b", "lei 14.300"],
    "agua": ["água", "agua", "ph", "turbidez", "cisterna"],
    "avac": ["avac", "ar-condicionado", "carga térmica"],
    "carbono": ["carbono", "esg", "emissõ", "inventário"],
    "circular": ["circular", "resíduo", "biogás", "biogas", "biodigestor"],
    "certificacoes": ["certifica", "leed", "edge", "iso 14001"],
    "monitoramento": ["monitoramento", "sensor", "caixinha"],
    "servidor": ["servidor", "vpn", "contêiner", "conteiner", "docker", "backup"],
    "mapeamento": ["mapeamento", "camada", "hidrografia", "planta solar"],
}


def carregar(docs: Path):
    tarefas = json.loads((docs / "18_Checklist_para_importar_na_Gestao.json").read_text(encoding="utf-8"))["tabelas"]
    kits = json.loads((RAIZ / "ferramentas" / "kits" / "modulos.json").read_text(encoding="utf-8"))["modulos"]
    return tarefas, kits


def modulos_da_tarefa(titulo: str, kits: list) -> list[str]:
    t = titulo.lower()
    achou = []
    for k in kits:
        chaves = [k["nome"].lower().split(" (")[0]] + EXTRA.get(k["id"], [])
        if any(c and c in t for c in chaves):
            achou.append(k["nome"])
    return achou


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", type=Path, required=True)
    a = ap.parse_args()
    tab, kits = carregar(a.docs)
    pessoas = {p["pessoa_id"]: p["nome"] for p in tab["pessoa"]}
    T = tab["tarefa"]
    principais = [t for t in T if "(com " not in t["titulo"]]
    por_mod = collections.defaultdict(list)
    for t in principais:
        mods = modulos_da_tarefa(t["titulo"], kits) or ["Geral (bloco: " + t["extras"].get("projeto_nome", "") + ")"]
        for m in mods:
            por_mod[m].append(t)
    por_pes = collections.defaultdict(lambda: {"total": 0, "principal": 0, "co": 0, "lista": []})
    for t in T:
        p = por_pes[t["pessoa_id"]]
        p["total"] += 1
        if "(com " in t["titulo"]:
            p["co"] += 1
        else:
            p["principal"] += 1
            p["lista"].append(t)
    cel = lambda s: str(s).replace("|", "/").replace("\n", " ")
    L = ["# 24 · Fase 2 por pessoa e por módulo", "",
         f"Gerado a partir das {len(T)} tarefas da Gestão (uma cópia por pessoa) e dos {len(kits)} kits. "
         "Por módulo, cada tarefa aparece uma vez, com o responsável principal; os co-responsáveis estão no texto \"(com …)\".", "",
         "## Por pessoa", "", "| Pessoa | Total | Principal | Co-responsável | Esta semana |", "|---|---|---|---|---|"]
    for pid, p in sorted(por_pes.items(), key=lambda x: -x[1]["total"]):
        semana = [t for t in p["lista"] if t["horizonte"] == "micro"] or [t for t in T if t["pessoa_id"] == pid and t["horizonte"] == "micro"]
        L.append(f"| {cel(pessoas.get(pid, pid))} | {p['total']} | {p['principal']} | {p['co']} | "
                 + cel(" · ".join(t["titulo"].split(". Feito quando")[0][:90] for t in semana[:4])) + " |")
    L += ["", "## Por módulo", ""]
    resp = {k["nome"]: ", ".join(k.get("responsaveis") or []) for k in kits}
    for m in sorted(por_mod, key=lambda x: (x.startswith("Geral"), x)):
        L += [f"### {m}", "", f"Responsáveis do kit: {resp.get(m, '—')}", "", "| Tarefa | Responsável principal | Horizonte |", "|---|---|---|"]
        for t in por_mod[m]:
            L.append(f"| {cel(t['titulo'].split(' (responsável principal')[0][:220])} | {cel(pessoas.get(t['pessoa_id'], t['pessoa_id']))} | {HORIZ.get(t['horizonte'], t['horizonte'])} |")
        L.append("")
    saida = a.docs / "24_Fase2_por_Pessoa_e_Modulo.md"
    saida.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    try:  # a mesma informação em planilha aberta
        sys.path.insert(0, str(RAIZ / "physis-hub"))
        from physis_hub import documentos
        fp = [{"nome": "Por pessoa", "cab": ["Pessoa", "Total", "Principal", "Co"],
               "linhas": [[pessoas.get(k, k), v["total"], v["principal"], v["co"]] for k, v in por_pes.items()]},
              {"nome": "Por módulo", "cab": ["Módulo", "Tarefa", "Responsável principal", "Horizonte"],
               "linhas": [[m, t["titulo"][:250], pessoas.get(t["pessoa_id"], t["pessoa_id"]), HORIZ.get(t["horizonte"], "")]
                          for m in sorted(por_mod) for t in por_mod[m]]}]
        (a.docs / "24_Fase2_por_Pessoa_e_Modulo.ods").write_bytes(documentos.ods("Fase 2 por pessoa e por módulo", fp))
    except Exception as exc:  # noqa: BLE001
        print("planilha não gerada:", exc)
    print(f"{saida.name}: {len(por_pes)} pessoas, {len(por_mod)} módulos/grupos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
