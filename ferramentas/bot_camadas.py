#!/usr/bin/env python3
r"""Bot de camadas à mão (o mesmo do M&A, physis_hub/camadas_bot.py):

    py ferramentas\bot_camadas.py                       (pasta PHYSIS_CAMADAS, cidades da Physis)
    py ferramentas\bot_camadas.py --forcar --so hidrografia,vento
"""
import argparse, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "physis-hub"))
from physis_hub import camadas_bot, mv_ecossistema  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--pasta", default=os.environ.get("PHYSIS_CAMADAS") or r"C:\physis\camadas")
ap.add_argument("--so", default="")
ap.add_argument("--forcar", action="store_true")
a = ap.parse_args()
r = camadas_bot.rodar_bot(Path(a.pasta), mv_ecossistema.cidades(), [x for x in a.so.split(",") if x] or None, a.forcar)
for c, x in r["camadas"].items():
    print(f"{c:14} {x['situacao']:40} {x.get('motivo') or x.get('arquivo') or ''}")
print("\nFaltam:", ", ".join(r["faltam"]) or "nenhuma", "· Provisórias:", ", ".join(r["provisorias"]) or "nenhuma")
