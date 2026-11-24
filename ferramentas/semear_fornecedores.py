#!/usr/bin/env python3
r"""Planilha de equipamentos da Gestão com os fabricantes de AVAC e instalações (24/11/2026: "incluir fornecedores sem contar com
base de dados externa; incluir modelos").

Fonte: a base interna sistema/physis-equipamentos.json (fabricantes por segmento, da planilha PHYSIS_AVAC-5, e as classes de
equipamento da Physis). Cada fabricante entra como marca na categoria do segmento; o modelo comercial fica vazio até a cotação
(o sistema não inventa modelo). Revendedores e distribuidores (CNPJ, regiões, contatos com consentimento) são cadastrados pelo Ryan.

    cd C:\physis\clientes\physis-physis-site      (a instalação com a Gestão)
    py C:\physis\physis-ma-20261122-1bd599e\ferramentas\semear_fornecedores.py --banco physis-hub.db
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "physis-hub"))


def semear(fornecedores, base: dict, quem: str = "semente-avac") -> dict:
    from physis_hub.fornecedores import SEGMENTO_CATEGORIA
    feitos, pulados = 0, []
    for seg, info in base.get("fabricantes_por_segmento", {}).items():
        if seg.startswith("_"):
            continue
        cat = SEGMENTO_CATEGORIA.get(seg)
        if not cat:
            pulados.append(seg); continue
        for marca in info.get("fabricantes", []):
            r = fornecedores.equipamento({"categoria": cat, "marca": marca, "modelo": "",
                                          "notas_internas": f"Segmento {seg} ({info.get('aplicacao', '')}). Modelo comercial: [MARCADOR] até a cotação."}, quem)
            if r.get("ok"):
                feitos += 1
            else:
                pulados.append(f"{seg}/{marca}: {r.get('erro')}")
    return {"marcas": feitos, "pulados": pulados}


def importar_modelos(fornecedores, csv_path: Path, quem: str = "bot-modelos") -> int:
    import csv as _csv
    from physis_hub.fornecedores import SEGMENTO_CATEGORIA
    n = 0
    for l in _csv.DictReader(csv_path.read_text(encoding="utf-8-sig").splitlines(), delimiter=";"):
        cat = SEGMENTO_CATEGORIA.get(l.get("segmento", ""))
        if cat and l.get("modelo"):
            r = fornecedores.equipamento({"categoria": cat, "marca": l["fabricante"], "modelo": l["modelo"], "notas_internas": f"Catálogo: {l.get('arquivo', '')}"}, quem)
            n += 1 if r.get("ok") else 0
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0]); ap.add_argument("--banco", required=True)
    ap.add_argument("--modelos", help="modelos_propostos.csv do bot de modelos (só os aprovados no M&A)")
    a = ap.parse_args(argv)
    from physis_hub.hub import Hub
    from physis_hub.fornecedores import Fornecedores
    h = Hub(caminho=a.banco, org="gestao")
    r = semear(Fornecedores(h), json.loads((RAIZ / "sistema" / "physis-equipamentos.json").read_text(encoding="utf-8")))
    if a.modelos:
        r["modelos"] = importar_modelos(Fornecedores(h), Path(a.modelos))
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
