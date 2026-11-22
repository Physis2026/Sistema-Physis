"""Bibliotecas de mapa e BIM entregues pelo próprio servidor (/vendor/), sem internet.

Protege:
1. Só os arquivos da lista saem por /vendor/ (nunca um caminho qualquer do servidor).
2. O tipo certo vai junto (o navegador recusa WebAssembly com tipo errado).
3. A política de segurança deixa rodar o WebAssembly e o worker do mapa, e mais nada de fora.
"""
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from physis_hub.hub import Hub
from physis_hub.servidor import THREE_MODULOS, VENDOR_TIPOS, iniciar

RAIZ = Path(__file__).resolve().parents[2]
TEM = (RAIZ / "vendor" / "web-ifc.wasm").is_file() or (Path(__file__).resolve().parents[1] / "web" / "vendor" / "web-ifc.wasm").is_file()


@unittest.skipUnless(TEM, "bibliotecas de mapa e BIM ausentes nesta instalação")
class Vendor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = iniciar(Hub(), 0, endereco="127.0.0.1", instancia={"login": True})
        cls.porta = cls.srv.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def get(self, rota):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.porta}{rota}", timeout=10) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def test_entrega_as_da_lista_com_tipo(self):
        st, hd, corpo = self.get("/vendor/web-ifc.wasm")
        self.assertEqual((st, hd.get("Content-Type")), (200, "application/wasm"))
        self.assertEqual(corpo[:4], b"\x00asm")
        st, hd, _ = self.get("/vendor/maplibre-gl.js")
        self.assertEqual(st, 200); self.assertTrue(hd.get("Content-Type").startswith("text/javascript"))
        self.assertIn("'wasm-unsafe-eval'", hd.get("Content-Security-Policy"))
        self.assertIn("worker-src 'self' blob:", hd.get("Content-Security-Policy"))

    def test_eval_so_no_planejador(self):
        """O leitor BIM precisa de 'unsafe-eval'; a liberação vale só para a página do Planejador."""
        _, hd, _ = self.get("/planejador/")          # 401 ou 404 nesta instalação de teste, mas o cabeçalho já mostra a política
        self.assertIn("'unsafe-eval'", hd.get("Content-Security-Policy"))
        for rota in ("/", "/api/instancia", "/vendor/maplibre-gl.js", "/gestao/"):
            self.assertNotIn(" 'unsafe-eval'", self.get(rota)[1].get("Content-Security-Policy"), rota)

    def test_nada_fora_da_lista(self):
        for rota in ("/vendor/../physis_hub/servidor.py", "/vendor/%2e%2e/physis_hub/hub.py", "/vendor/LEIA-ME.md",
                     "/vendor/", "/vendor/jszip.min.js"):
            self.assertEqual(self.get(rota)[0], 404, rota)
        self.assertEqual(set(VENDOR_TIPOS), {"maplibre-gl.js", "maplibre-gl.css", "pmtiles.js", "web-ifc-api-iife.js",
                                             "web-ifc.wasm", "three.min.js"} | set(THREE_MODULOS))
        for rota in ("/vendor/three/LICENSE", "/vendor/three/SHA256.json", "/vendor/three/addons/../three.module.min.js",
                     "/vendor/three/addons/exporters/GLTFExporter.js"):
            self.assertEqual(self.get(rota)[0], 404, rota)

    def test_three_em_modulos(self):
        """Vista 3D (sistema/physis-3d.js): three.js em módulos com tipo de script, para o import() do navegador."""
        if not (RAIZ / "vendor" / "three" / "three.module.min.js").is_file():
            self.skipTest("three.js em módulos ausente")
        for n in THREE_MODULOS:
            st, hd, _ = self.get("/vendor/" + n)
            self.assertEqual((st, hd.get("Content-Type")), (200, "text/javascript; charset=utf-8"), n)


if __name__ == "__main__":
    unittest.main()
