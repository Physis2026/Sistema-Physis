#!/usr/bin/env python3
"""Imagem de apresentação a partir do GLB da vista 3D, com o Blender (Cycles) instalado no servidor da Physis.

    python ferramentas/renderizar_glb.py modelo.glb imagem.png [--largura 2400] [--altura 1500] [--amostras 128]
                                         [--vista iso|planta|frente|lado] [--fundo "#F4F1EA"]

Opção, nunca o único caminho (regra 11; decisão da dona de 22/11/2026, M&A pg:b88441eec95b): a vista 3D continua salvando o PNG
em até 4× direto do navegador. O Blender é software aberto (GPL; Cycles sob Apache-2.0) e roda sem tela (`blender -b`).
Onde procurar o Blender: variável PHYSIS_BLENDER, o PATH, ou as pastas de instalação comuns. Sem Blender, avisa e sai com 2.
O sol é de apresentação (mesma direção da vista 3D), não é estudo solar.
"""
from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

CENA = Path(__file__).resolve().parent / "blender_cena.py"
PALETA_FUNDOS = {"#F4F1EA", "#F6F3EE", "#FFFFFF", "#0B3D2E", "#1B1F23"}   # docs/PALETA.md: fundos claros e escuros


def norte_do_glb(glb: Path):
    """Norte gravado pela vista 3D (asset.extras.physis_norte, plano x, y do IFC) ou None."""
    import json
    import struct
    try:
        b = glb.read_bytes()
        jl = struct.unpack("<I", b[12:16])[0]
        n = json.loads(b[20:20 + jl]).get("asset", {}).get("extras", {}).get("physis_norte")
        return (float(n["x"]), float(n["y"])) if n and (n["x"] or n["y"]) else None
    except (OSError, ValueError, KeyError, TypeError, struct.error):
        return None


def achar_blender() -> str | None:
    if os.environ.get("PHYSIS_BLENDER") and Path(os.environ["PHYSIS_BLENDER"]).is_file():
        return os.environ["PHYSIS_BLENDER"]
    achado = shutil.which("blender")
    if achado:
        return achado
    for padrao in (r"C:\Program Files\Blender Foundation\Blender*\blender.exe", "/usr/bin/blender", "/snap/bin/blender",
                   "/Applications/Blender.app/Contents/MacOS/Blender"):
        acha = sorted(glob.glob(padrao))
        if acha:
            return acha[-1]
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("glb"); ap.add_argument("png")
    ap.add_argument("--largura", type=int, default=2400); ap.add_argument("--altura", type=int, default=1500)
    ap.add_argument("--amostras", type=int, default=128)
    ap.add_argument("--vista", choices=("iso", "planta", "frente", "lado"), default="iso")
    ap.add_argument("--fundo", default="#F4F1EA")
    a = ap.parse_args(argv)
    if a.fundo.upper() not in PALETA_FUNDOS:
        ap.error("fundo fora da paleta (docs/PALETA.md): use " + ", ".join(sorted(PALETA_FUNDOS)))
    if not Path(a.glb).is_file():
        ap.error("GLB não encontrado: " + a.glb)
    blender = achar_blender()
    if not blender:
        print("Blender não encontrado. Instale o Blender (blender.org, aberto) no servidor ou indique PHYSIS_BLENDER. "
              "Enquanto isso, use 'Salvar imagem (PNG)' na vista 3D.", file=sys.stderr)
        return 2
    norte = norte_do_glb(Path(a.glb))
    if not norte:
        print("Aviso: o GLB não informa o norte; a imagem leva 'N?' ([MARCADOR] conferir a orientação).", file=sys.stderr)
    cmd = [blender, "-b", "--factory-startup", "--python", str(CENA), "--",
           str(Path(a.glb).resolve()), str(Path(a.png).resolve()), str(a.largura), str(a.altura), str(a.amostras), a.vista, a.fundo,
           f"{norte[0]},{norte[1]}" if norte else "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not Path(a.png).is_file():
        print((r.stdout or "")[-2000:] + (r.stderr or "")[-2000:], file=sys.stderr)
        return 1
    print("imagem salva:", a.png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
