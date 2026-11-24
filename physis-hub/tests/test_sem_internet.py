"""Os programas da Physis rodam sem internet.

Protege:
1. Nenhum programa carrega script, estilo ou fonte de fora (CDN, Google Fonts...).
   Links para o usuário clicar (<a href>) podem existir; o que não pode é o programa depender deles para funcionar.
2. As bibliotecas guardadas em vendor/ são as mesmas que foram conferidas na origem (resumo SHA-256).
3. O Planejador está com a cópia atual de vendor/ embutida (rodar ferramentas/embutir_bibliotecas.py não muda nada).

Só roda dentro do repositório (no pacote do cliente, vendor/ e ferramentas/ não vão).
"""
import hashlib
import json
import importlib.util
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
NO_REPO = (RAIZ / "vendor").is_dir() and (RAIZ / "ferramentas" / "embutir_bibliotecas.py").is_file()

PROGRAMAS = ["sistema/*.html", "modulos/planejador/*.html", "physis-hub/web/*.html"]
EXTERNO = [
    re.compile(r'<script\b[^>]*\bsrc\s*=\s*["\']?(?:https?:)?//', re.I),
    re.compile(r'<link\b[^>]*\bhref\s*=\s*["\']?(?:https?:)?//[^>]*>', re.I),
    re.compile(r'@import\s+(?:url\()?["\']?(?:https?:)?//', re.I),
    re.compile(r'url\(\s*["\']?(?:https?:)?//', re.I),
]

# SHA-256 dos arquivos baixados em 14/11/2026 (o SHA-512 conferiu com o publicado pelo cdnjs)
VENDOR = {
    "jszip.min.js": "acc7e41455a80765b5fd9c7ee1b8078a6d160bbbca455aeae854de65c947d59e",
    "pdf.min.js": "5b5799e6f8c680663207ac5b42ee14eed2a406fa7af48f50c154f0c0b1566946",
    "pdf.worker.min.js": "feabdf309770ed24bba31a5467836cdc8cf639c705af27d52b585b041bb8527b",
    # mapa e BIM (jsDelivr, 14/11/2026)
    "maplibre-gl.js": "be9633c4d870e26fb37f1cfe5c5a77181667114003ea16207ac7850d8da8add1",
    "maplibre-gl.css": "576b085fdd9487a65a19215328c1e086c07ce5bf6da09b666b3806d3d008dae9",
    "pmtiles.js": "367c19f8936d1d6c1b1820b0dee053f793fc29277655c3e471f5ed4d37b5f045",
    "web-ifc-api-iife.js": "ce09568916e574e710225737563672b3933bfa7c49ce5544ac877bae13b0709a",
    "web-ifc.wasm": "3cebe59b646bf79b38c525a4ffe289881f5bb544952a75a89ec0c1d900240b3f",
    "three.min.js": "170c6789f43217c96b3170f4b42fafe135de7f7cd48497a4218f9757ee1d49fa",
}


@unittest.skipUnless(NO_REPO, "só no repositório")
class SemInternet(unittest.TestCase):
    def test_nenhum_programa_busca_coisas_fora(self):
        achados = []
        for padrao in PROGRAMAS:
            for arq in sorted(RAIZ.glob(padrao)):
                texto = arq.read_text(encoding="utf-8", errors="replace")
                for r in EXTERNO:
                    for m in r.finditer(texto):
                        trecho = texto[m.start():m.start() + 120]
                        if re.match(r"<link\b", trecho, re.I) and not re.search(r'rel\s*=\s*["\']?(stylesheet|preload|preconnect|modulepreload)', m.group(0), re.I):
                            continue        # <link rel="canonical"> etc. não carregam nada
                        achados.append(f"{arq.relative_to(RAIZ)}: {trecho[:90]}")
        self.assertEqual(achados, [], "programa dependendo da internet")

    def test_vendor_confere(self):
        # three.js em módulos (ferramentas/baixar_three.py conferiu com o SHA-256 publicado pelo jsDelivr em 22/11/2026)
        tres = RAIZ / "vendor" / "three" / "SHA256.json"
        extra = {"three/" + n: h for n, h in json.loads(tres.read_text(encoding="utf-8")).items()} if tres.is_file() else {}
        for nome, esperado in {**VENDOR, **extra}.items():
            atual = hashlib.sha256((RAIZ / "vendor" / nome).read_bytes()).hexdigest()
            self.assertEqual(atual, esperado, f"vendor/{nome} mudou: confira a origem e atualize vendor/LEIA-ME.md")

    def test_planejador_com_bibliotecas_atuais(self):
        spec = importlib.util.spec_from_file_location("embutir", RAIZ / "ferramentas" / "embutir_bibliotecas.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for alvo in mod.ALVOS:
            html = alvo.read_text(encoding="utf-8")
            self.assertEqual(mod.embutir(html), html, f"{alvo.name}: rode ferramentas/embutir_bibliotecas.py")


if __name__ == "__main__":
    unittest.main()
