#!/usr/bin/env python3
"""Monta a plataforma de cada cliente a partir de clientes/clientes.json.

    python montar_clientes.py --saida <pasta>

Cada pacote leva o rascunho do manual do cliente (manual/MANUAL-RASCUNHO.md e .odt), montado só com os módulos
da ficha (montar.escrever_manual). A versão final do manual passa pela revisão e aprovação na fila de emissão.

O código é um só (este repositório). Cada cliente é só uma ficha: organização, módulos e,
para a Casa Physis, o modo de pesquisa. Os programas da Physis (SustainKit, SCADA e
Planejador) vêm das pastas do repositório.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from montar import LICENCA_PADRAO, montar

RAIZ = Path(__file__).resolve().parent.parent
FICHAS = RAIZ / "clientes" / "clientes.json"
PROGRAMAS = {
    "sustainkit": RAIZ / "sistema" / "SustainKit_Definitivo.html",
    "supervisao": RAIZ / "sistema" / "physis-scada-demo.html",
    "planejador": RAIZ / "modulos" / "planejador" / "planejador-physis.html",
}
# Pegada do servidor (docs/PEGADA_SERVIDOR.md): obrigatória na Casa Physis. É a configuração do documento, sem as
# partes de exemplo (medidor "lugar01/no7", servidor de IA e clientes hospedados): essas entram quando existirem de fato.
# Uma ficha de clientes.json com "pegada_servidor" vale no lugar desta.
PEGADA_PADRAO = {
    "casa-physis": {"classe": "notebook", "nome": "Hub da Casa Physis (notebook, 16 GB de RAM: 2 × 8 GB)", "local": "no_lugar", "controle": "proprio",
                    "intervalo_min": 5, "contagem": "auto", "fator_rede": None},
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--so", default="", help="montar só esta organização")
    a = ap.parse_args()
    a.saida.mkdir(parents=True, exist_ok=True)
    base = json.loads(FICHAS.read_text(encoding="utf-8"))
    # "suporte" de uma ficha substitui o da Physis só para ela; "_leia" não é campo de configuração
    for f in base["clientes"]:
        if isinstance(f.get("suporte"), dict):
            f["suporte"] = {k: v for k, v in f["suporte"].items() if not k.startswith("_")}
    fichas, suporte = base["clientes"], base.get("suporte")
    for f in fichas:
        if a.so and f["org"] != a.so:
            continue
        gestao = RAIZ / "sistema" / "gestao-interna-physis.html" if f.get("gestao_interna") else None
        pacote = montar(f["org"], f.get("lugar", "lugar01"), f["modulos"], a.saida, PROGRAMAS["sustainkit"],
                        LICENCA_PADRAO, PROGRAMAS["supervisao"], gestao, PROGRAMAS["planejador"],
                        bool(f.get("pesquisa")), f.get("nome", ""), f.get("cursos"), f.get("suporte") or suporte,
                        pegada=f.get("pegada_servidor") or PEGADA_PADRAO.get(f["org"]))
        print(f"{f['nome']}: {pacote.name} ({pacote.stat().st_size // 1024} kB) · módulos: {', '.join(f['modulos'])} · manual (rascunho)"
              + (" · pesquisa" if f.get("pesquisa") else ""))


if __name__ == "__main__":
    main()
