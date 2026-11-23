#!/usr/bin/env python3
"""Gera physis-hub/docs/VARIAVEIS.md: toda variável PHYSIS_* lida no código do servidor, com onde é lida e a linha do código.

    python ferramentas/listar_variaveis.py

Rodar de novo depois de criar variável nova (a auditoria do M&A avisa quando falta).
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PACOTE = RAIZ / "physis-hub" / "physis_hub"
SAIDA = RAIZ / "physis-hub" / "docs" / "VARIAVEIS.md"
LEITURA = re.compile(r"""(?:environ(?:\.get)?\s*[\(\[]\s*|getenv\(\s*|_limite\(\s*|_pede_limite\([^)]*?)["'](PHYSIS_[A-Z0-9_]*[A-Z0-9])["']""")
C = "\x60"


def main() -> None:
    onde = defaultdict(list)
    for p in sorted(PACOTE.glob("*.py")):
        for n, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for m in LEITURA.finditer(linha):
                onde[m.group(1)].append((p.name, n, linha.strip()[:150]))
    md = ["# Variáveis de ambiente do servidor (índice gerado do código)", "",
          f"Gerado por {C}ferramentas/listar_variaveis.py{C}. Cada variável aparece com o arquivo, a linha e o trecho onde é lida (o padrão,",
          "quando existe, está no trecho). Segredos (senhas, chaves) nunca vão no código: só no arquivo de ambiente (regra 12).", "",
          "| Variável | Onde é lida | Trecho do código |", "|---|---|---|"]
    for v in sorted(onde):
        arq, n, trecho = onde[v][0]
        mais = f" (+{len(onde[v]) - 1})" if len(onde[v]) > 1 else ""
        md.append(f"| {C}{v}{C} | {arq}:{n}{mais} | {C}{trecho.replace('|', '¦').replace(C, '')}{C} |")
    SAIDA.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(SAIDA, len(onde), "variáveis")


if __name__ == "__main__":
    main()
