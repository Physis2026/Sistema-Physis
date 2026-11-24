#!/usr/bin/env python3
"""Baixa o three.js em módulos ES para vendor/three/ e confere cada arquivo com o SHA-256 publicado pelo jsDelivr.

    python ferramentas/baixar_three.py            # baixa e confere
    python ferramentas/baixar_three.py --conferir # só confere os arquivos já guardados (sem internet não conferir nada)

Só os arquivos que a vista 3D usa (sistema/physis-3d.js): o núcleo, o pós-processamento com oclusão de ambiente (GTAO) e o
leitor glTF. Os arquivos não são alterados: as páginas resolvem `three` e `three/addons/` por um importmap.
Decisão da dona de 22/11/2026 (M&A pg:ea1020f44c18): "Agora, em teste".
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

VERSAO = "0.170.0"
RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "vendor" / "three"
ARQUIVOS = {
    "build/three.module.min.js": "three.module.min.js",
    "LICENSE": "LICENSE",
}
for a in ("postprocessing/EffectComposer.js", "postprocessing/Pass.js", "postprocessing/RenderPass.js", "postprocessing/ShaderPass.js",
          "postprocessing/MaskPass.js", "postprocessing/OutputPass.js", "postprocessing/GTAOPass.js",
          "shaders/CopyShader.js", "shaders/OutputShader.js", "shaders/GTAOShader.js", "shaders/PoissonDenoiseShader.js",
          "math/SimplexNoise.js", "loaders/GLTFLoader.js", "utils/BufferGeometryUtils.js"):
    ARQUIVOS["examples/jsm/" + a] = "addons/" + a
CDN = f"https://cdn.jsdelivr.net/npm/three@{VERSAO}/"
DADOS = f"https://data.jsdelivr.com/v1/packages/npm/three@{VERSAO}?structure=flat"


def baixar(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "physis-vendor/1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main() -> int:
    conferir = "--conferir" in sys.argv
    manifesto = DESTINO / "SHA256.json"
    if conferir:
        esperado = json.loads(manifesto.read_text(encoding="utf-8"))
        ruins = [n for n, h in esperado.items() if hashlib.sha256((DESTINO / n).read_bytes()).hexdigest() != h]
        print("tudo conferido" if not ruins else "diferente: " + ", ".join(ruins))
        return 1 if ruins else 0
    publicados = {f["name"].lstrip("/"): f["hash"] for f in json.loads(baixar(DADOS))["files"]}
    saida = {}
    for origem, local in ARQUIVOS.items():
        b = baixar(CDN + origem)
        h = base64.b64encode(hashlib.sha256(b).digest()).decode()
        if publicados.get(origem) != h:
            print(f"SHA diferente do publicado: {origem}")
            return 1
        p = DESTINO / local
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b)
        saida[local] = hashlib.sha256(b).hexdigest()
        print(f"ok {len(b):>8} B  {local}")
    manifesto.write_text(json.dumps(saida, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
