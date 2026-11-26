"""Arquivos do projeto enviados no Início da plataforma (26/11/2026, "pode guardar arquivos no servidor").

Antes ficavam só no navegador (IndexedDB): outro computador via a lista mas não o arquivo. Agora cada arquivo também fica
numa pasta da instalação (projeto-arquivos, ao lado do banco), que entra no backup diário junto com a pasta clientes.
Só tipos de projeto (IFC, mapas, imagens, PDF, textos, desenhos, planilhas); até 50 MB cada; nome limpo; id aleatório.
"""
from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path

MAX = 50 * 1024 * 1024
TIPOS = re.compile(r"\.(ifc|kml|kmz|geojson|json|zip|png|jpe?g|webp|heic|tiff?|pdf|docx?|odt|rtf|txt|md|dwg|dxf|skp|obj|stl|3dm|step|stp|xlsx?|ods|csv)$", re.I)
ID = re.compile(r"^[0-9a-f]{20}$")


class ProjetoArquivos:
    def __init__(self, pasta: str | Path):
        self.p = Path(pasta)
        self.p.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _nome(n: str) -> str:
        n = Path(str(n or "").replace("\\", "/")).name
        return re.sub(r"[^\w.\- ()]+", "_", n)[:120].strip() or "arquivo"

    def salvar(self, nome: str, dados: bytes, usuario: str = "") -> dict:
        nome = self._nome(nome)
        if not TIPOS.search(nome):
            return {"ok": False, "erro": "tipo de arquivo não aceito", "codigo": 400}
        if not dados or len(dados) > MAX:
            return {"ok": False, "erro": "arquivo vazio ou maior que 50 MB", "codigo": 413 if dados else 400}
        i = secrets.token_hex(10)
        (self.p / (i + ".bin")).write_bytes(dados)
        meta = {"id": i, "nome": nome, "tamanho": len(dados), "enviado": time.time(), "por": str(usuario)[:120]}
        (self.p / (i + ".json")).write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        return {"ok": True, **meta}

    def listar(self) -> list[dict]:
        out = []
        for m in sorted(self.p.glob("*.json")):
            try:
                out.append(json.loads(m.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return sorted(out, key=lambda x: x.get("enviado", 0))

    def ler(self, i: str) -> tuple[str, bytes] | None:
        if not ID.match(str(i)) or not (self.p / (i + ".bin")).is_file():
            return None
        meta = json.loads((self.p / (i + ".json")).read_text(encoding="utf-8"))
        return meta["nome"], (self.p / (i + ".bin")).read_bytes()

    def apagar(self, i: str) -> bool:
        if not ID.match(str(i)):
            return False
        ok = False
        for ext in (".bin", ".json"):
            f = self.p / (i + ext)
            if f.is_file():
                f.unlink(); ok = True
        return ok
