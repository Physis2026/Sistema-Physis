"""Vista 3D melhorada, versão de TESTE (sistema/physis-3d.js e modulos/planejador/visualizador-3d-teste.html, 22/11/2026).

Protege:
1. Sem internet (regra 11): nenhum endereço de fora; three.js e web-ifc vêm de /vendor/.
2. Só cores da paleta (regra 6), em tema claro e escuro; a única exceção é a cópia da vista atual do Planejador,
   mantida para comparar (modo "atual").
3. Acessibilidade (regra 5): vista focável com nome e instruções de teclado, alvos de 44 px, barra de ferramentas com nome.
4. A página de teste leva cópias iguais dos módulos (sincronizar.py) e caixa de envio de arquivo IFC.
5. O Planejador não mudou: o 3D dele é função (regra 2) e adotar a vista nova é decisão da dona.
6. O GLB segue o formato glTF 2.0 binário (cabeçalho, blocos JSON e BIN alinhados em 4 bytes).
"""
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MODULO = RAIZ / "sistema" / "physis-3d.js"
PAGINA = RAIZ / "modulos" / "planejador" / "visualizador-3d-teste.html"
PLANEJADOR = RAIZ / "modulos" / "planejador" / "planejador-physis.html"
PALETA = RAIZ / "physis-hub" / "docs" / "PALETA.md"
NO_REPO = MODULO.is_file() and PAGINA.is_file()
# cores da vista ATUAL do Planejador, copiadas só para a comparação lado a lado
COPIA_ATUAL = {"#8899AA"}


def ler(p):
    return p.read_text(encoding="utf-8")


def cores(texto):
    achadas = {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}\b", texto)}
    achadas |= {"#" + c.upper() for c in re.findall(r"0x([0-9A-Fa-f]{6})\b", texto)}
    return achadas


@unittest.skipUnless(NO_REPO, "só no repositório")
class Render3D(unittest.TestCase):
    def test_sem_internet(self):
        for p in (MODULO, PAGINA):
            self.assertNotRegex(ler(p), r"https?://", p.name)
        self.assertIn('"/vendor/"', ler(PAGINA))

    def test_so_cores_da_paleta(self):
        paleta = cores(ler(PALETA))
        for p in (MODULO, PAGINA):
            fora = cores(ler(p)) - paleta - COPIA_ATUAL
            self.assertFalse(fora, f"{p.name}: cores fora da paleta {sorted(fora)}")

    def test_tema_claro_e_escuro(self):
        pag = ler(PAGINA)
        self.assertIn('[data-tema="escuro"]', pag)
        self.assertIn("prefers-color-scheme:dark", pag)
        mod = ler(MODULO)
        # o fundo e as arestas seguem as variáveis da tela e a vista redesenha ao trocar o tema
        self.assertIn('"--bg", "--fundo"', mod)
        self.assertIn('attributeFilter: ["data-tema"', mod)

    def test_acessibilidade(self):
        mod = ler(MODULO)
        self.assertIn('tabindex: "0"', mod)
        self.assertIn('"aria-describedby"', mod)
        self.assertIn('role: "toolbar"', mod)
        self.assertIn("min-height:44px", mod)
        for tecla in ("ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", '"+"', '"-"', '"0"'):
            self.assertIn(tecla, mod)
        self.assertIn("aria-live", mod)

    def test_recursos_de_renderizacao(self):
        mod = ler(MODULO)
        for item in ("ACESFilmicToneMapping", "SRGBColorSpace", "PCFSoftShadowMap", "MeshStandardMaterial", "EdgesGeometry",
                     "requestFullscreen", "toDataURL", "setPixelRatio"):
            self.assertIn(item, mod)

    def test_copias_iguais_e_caixa_de_upload(self):
        pag = ler(PAGINA)
        for ident, fonte in (("physis-3d", MODULO), ("physis-preferencias", RAIZ / "sistema" / "physis-preferencias.js")):
            abre = f'<script id="{ident}">\n'
            i = pag.index(abre) + len(abre)
            j = pag.index("</script>", i)
            self.assertEqual(pag[i:j], ler(fonte).replace("\r\n", "\n"), ident)
        self.assertIn('type="file" accept=".ifc"', pag)
        self.assertIn("drop", pag)
        self.assertEqual(len(re.findall(r"<h1\b", pag)), 1)

    def test_ifc_so_do_mesmo_servidor(self):
        pag = ler(PAGINA)
        self.assertIn(r"/^\/[\w\/.\-]+\.ifc$/i", pag)

    def test_planejador_sem_mudanca(self):
        plan = ler(PLANEJADOR)
        self.assertNotIn("Physis3D", plan)
        self.assertIn("MeshLambertMaterial", plan)


def glb_valido(b: bytes):
    """Confere um .glb: devolve o JSON (para testes e para conferir o arquivo baixado da vista)."""
    import json
    import struct
    magia, versao, total = struct.unpack("<III", b[:12])
    assert magia == 0x46546C67 and versao == 2 and total == len(b)
    jl, jt = struct.unpack("<II", b[12:20])
    assert jt == 0x4E4F534A and jl % 4 == 0
    j = json.loads(b[20:20 + jl])
    bl, bt = struct.unpack("<II", b[20 + jl:28 + jl])
    assert bt == 0x004E4942 and bl % 4 == 0 and bl == j["buffers"][0]["byteLength"]
    for v in j["bufferViews"]:
        assert v["byteOffset"] % 4 == 0 and v["byteOffset"] + v["byteLength"] <= bl
    for a in j["accessors"]:
        assert a["bufferView"] < len(j["bufferViews"])
    return j


@unittest.skipUnless(NO_REPO, "só no repositório")
class GLB(unittest.TestCase):
    def test_validador_reconhece_glb_minimo(self):
        import json
        import struct
        pos = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
        js = json.dumps({"asset": {"version": "2.0"}, "buffers": [{"byteLength": 36}],
                         "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36}],
                         "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3"}]}).encode()
        js += b" " * ((4 - len(js) % 4) % 4)
        total = 12 + 8 + len(js) + 8 + len(pos)
        b = struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(pos), 0x004E4942) + pos
        self.assertEqual(glb_valido(b)["asset"]["version"], "2.0")

    def test_escritor_usa_o_mesmo_formato(self):
        mod = ler(MODULO)
        for marca in ("0x46546C67", "0x4E4F534A", "0x004E4942", 'version: "2.0"', "baseColorFactor", "34962", "34963"):
            self.assertIn(marca, mod)


if __name__ == "__main__":
    unittest.main()
