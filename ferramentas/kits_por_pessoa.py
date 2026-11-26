#!/usr/bin/env python3
"""Junta os kits de revisão por PESSOA: um zip por responsável com os kits dos módulos dela (ferramentas/kits/modulos.json).

    python ferramentas/gerar_kits_revisao.py --saida C:\\physis\\kits-2026-11-26
    python ferramentas/kits_por_pessoa.py --saida C:\\physis\\kits-2026-11-26

Gera <saida>/por-pessoa/<Nome>.zip e <saida>/por-pessoa/INDICE.md (quem recebe o quê). Módulo sem responsável vai para
"_sem-responsavel" (a direção decide). Não inventa responsável.
"""
from __future__ import annotations
import argparse, json, re, zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--saida", required=True); a = ap.parse_args()
    s = Path(a.saida); mods = json.loads((RAIZ / "ferramentas" / "kits" / "modulos.json").read_text(encoding="utf-8"))["modulos"]
    destino = s / "por-pessoa"; destino.mkdir(parents=True, exist_ok=True)
    pessoas: dict[str, list[tuple[str, Path]]] = {}
    for m in mods:
        zs = sorted(z for z in s.glob(f"kit-{m['id']}-*.zip") if re.fullmatch(re.escape(f"kit-{m['id']}-") + r"\d{4}-\d{2}-\d{2}\.zip", z.name))
        if not zs:
            continue
        for p in (m.get("responsaveis") or ["_sem-responsavel"]):
            pessoas.setdefault(p, []).append((m.get("nome", m["id"]), zs[-1]))
    linhas = ["# Kits de revisão por pessoa", "", "| Pessoa | Kits (módulos) |", "|---|---|"]
    for p, kits in sorted(pessoas.items()):
        nome = re.sub(r"[^\w.-]+", "-", p, flags=re.UNICODE).strip("-") or "pessoa"
        with zipfile.ZipFile(destino / f"{nome}.zip", "w", zipfile.ZIP_STORED) as z:
            for _, k in kits:
                z.write(k, k.name)
        linhas.append(f"| {p} | " + ", ".join(n for n, _ in kits) + " |")
        print(f"{nome}.zip: {len(kits)} kit(s)")
    (destino / "INDICE.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
