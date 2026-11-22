"""Vista 3D melhorada, versão de TESTE (sistema/physis-3d.js e modulos/planejador/visualizador-3d-teste.html, 22/11/2026).

Protege:
1. Sem internet (regra 11): nenhum endereço de fora; three.js e web-ifc vêm de /vendor/.
2. Só cores da paleta (regra 6), em tema claro e escuro; a única exceção é a cópia da vista atual do Planejador,
   mantida para comparar (modo "atual").
3. Acessibilidade (regra 5): vista focável com nome e instruções de teclado, alvos de 44 px, barra de ferramentas com nome.
4. A página de teste leva cópias iguais dos módulos (sincronizar.py) e caixa de envio de arquivo IFC.
5. O Planejador usa a vista comum (decisão da dona, 22/11/2026) e a conta das áreas é a mesma de antes (regra 2).
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
            # o único endereço permitido é o nome do espaço do SVG (não busca nada na rede)
            self.assertNotRegex(ler(p).replace("http://www.w3.org/2000/svg", ""), r"https?://", p.name)
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
        self.assertIn('type="file" accept=".ifc,.glb,.gltf"', pag)
        self.assertIn("drop", pag)
        self.assertEqual(len(re.findall(r"<h1\b", pag)), 1)

    def test_ifc_so_do_mesmo_servidor(self):
        pag = ler(PAGINA)
        self.assertIn(r"/^\/[\w\/.\-]+\.(ifc|glb)$/i", pag)

    def test_planejador_usa_a_vista_comum(self):
        """Decisão da dona (M&A pg:cf499965b745, 22/11/2026): o "Ver em 3D e áreas" desenha pela physis-3d.js.
        A conta das áreas (piso de cada IfcSpace) continua a mesma (regra 2)."""
        plan = ler(PLANEJADOR)
        abre = '<script id="physis-3d">\n'
        i = plan.index(abre) + len(abre)
        self.assertEqual(plan[i:plan.index("</script>", i)], ler(MODULO).replace("\r\n", "\n"))
        self.assertIn("Physis3D.carregar(VENDOR.base)", plan)
        self.assertIn("Physis3D.malhasDoIFC(IFC_API,m,WebIFC", plan)
        self.assertIn("if(ar>0&&n.y/(2*ar)<-0.9)a+=ar", plan)
        self.assertIn("{areas:lista,areaTotal:total}", plan)
        self.assertNotIn("new THREE.MeshLambertMaterial({color:new THREE.Color(c.x,c.y,c.z)", plan)   # a vista antiga saiu
        self.assertNotIn("VENDOR.js('three.min.js')", plan)

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


@unittest.skipUnless(NO_REPO, "só no repositório")
class Offline(unittest.TestCase):
    """Imagem de apresentação pelo Blender (opção; decisão da dona M&A pg:b88441eec95b)."""
    def carregar(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("renderizar_glb", RAIZ / "ferramentas" / "renderizar_glb.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_sem_blender_avisa_e_nao_quebra(self):
        import tempfile
        mod = self.carregar()
        mod.achar_blender = lambda: None
        with tempfile.TemporaryDirectory() as d:
            glb = Path(d) / "m.glb"
            glb.write_bytes(b"glTF")
            self.assertEqual(mod.main([str(glb), str(Path(d) / "x.png")]), 2)

    def test_fundo_so_da_paleta(self):
        mod = self.carregar()
        paleta = cores(ler(PALETA))
        self.assertTrue(mod.PALETA_FUNDOS <= paleta)
        with self.assertRaises(SystemExit):
            mod.main(["m.glb", "x.png", "--fundo", "#123456"])

    def test_blender_de_verdade(self):
        """Só onde o Blender está instalado: GLB mínimo → PNG com o tamanho pedido e o canto na cor de fundo da paleta."""
        import json, struct, tempfile, zlib
        mod = self.carregar()
        if not mod.achar_blender():
            self.skipTest("Blender não instalado nesta máquina")
        pos = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
        js = json.dumps({"asset": {"version": "2.0"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
                         "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}], "buffers": [{"byteLength": 36}],
                         "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36}],
                         "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3",
                                        "min": [0, 0, 0], "max": [1, 1, 0]}]}).encode()
        js += b" " * ((4 - len(js) % 4) % 4)
        total = 12 + 8 + len(js) + 8 + len(pos)
        glb = struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(pos), 0x004E4942) + pos
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "m.glb").write_bytes(glb)
            png = Path(d) / "m.png"
            self.assertEqual(mod.main([str(Path(d) / "m.glb"), str(png), "--largura", "160", "--altura", "100", "--amostras", "4",
                                       "--fundo", "#0B3D2E"]), 0)
            b = png.read_bytes()
        self.assertEqual(b[:8], bytes.fromhex("89504e470d0a1a0a"))
        w, h, prof, tipo = struct.unpack(">IIBB", b[16:26])
        self.assertEqual((w, h), (160, 100))
        dados, i = b"", 8
        while i < len(b):
            n, t = struct.unpack(">I4s", b[i:i + 8]); dados += b[i + 8:i + 8 + n] if t == b"IDAT" else b""; i += 12 + n
        cru = zlib.decompress(dados)
        canais = {6: 4, 2: 3}[tipo] * (prof // 8)
        filtro, linha = cru[0], bytearray(cru[1:1 + w * canais])
        if filtro in (1, 4):                       # Sub e Paeth na 1ª linha: soma o pixel da esquerda
            for k in range(canais, len(linha)):
                linha[k] = (linha[k] + linha[k - canais]) & 0xFF
        elif filtro == 3:                          # Average na 1ª linha
            for k in range(canais, len(linha)):
                linha[k] = (linha[k] + linha[k - canais] // 2) & 0xFF
        self.assertEqual(tuple(linha[:3]) if prof == 8 else None, (0x0B, 0x3D, 0x2E))

    def test_cena_sem_internet(self):
        self.assertNotRegex(ler(RAIZ / "ferramentas" / "blender_cena.py"), r"https?://")


IFC_DOIS_AMBIENTES = """ISO-10303-21;
HEADER;FILE_DESCRIPTION(('ViewDefinition [ReferenceView]'),'2;1');FILE_NAME('t.ifc','2026-11-22T00:00:00',(''),(''),'t','t','');FILE_SCHEMA(('IFC4'));ENDSEC;
DATA;
#1=IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.);#3=IFCUNITASSIGNMENT((#1));
#4=IFCCARTESIANPOINT((0.,0.,0.));#5=IFCDIRECTION((0.,0.,1.));#6=IFCDIRECTION((1.,0.,0.));#7=IFCAXIS2PLACEMENT3D(#4,#5,#6);
#60=IFCDIRECTION((0.,1.));#8=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#7,#60);
#9=IFCPROJECT('0YvctVUKr0kugbFTf53O9L',$,'Teste',$,$,$,$,(#8),#3);#10=IFCLOCALPLACEMENT($,#7);
#11=IFCSITE('1YvctVUKr0kugbFTf53O9L',$,'Lote',$,$,#10,$,$,.ELEMENT.,$,$,$,$,$);#14=IFCRELAGGREGATES('4YvctVUKr0kugbFTf53O9L',$,$,$,#9,(#11));
#20=IFCRECTANGLEPROFILEDEF(.AREA.,$,#21,4.,5.);#21=IFCAXIS2PLACEMENT2D(#22,$);#22=IFCCARTESIANPOINT((2.,2.5));
#23=IFCEXTRUDEDAREASOLID(#20,#7,#5,2.8);#24=IFCSHAPEREPRESENTATION(#8,'Body','SweptSolid',(#23));#25=IFCPRODUCTDEFINITIONSHAPE($,$,(#24));
#26=IFCSPACE('7YvctVUKr0kugbFTf53O9L',$,'S1','Sala',$,#10,#25,$,.ELEMENT.,.INTERNAL.,$);
#36=IFCSPACE('8YvctVUKr0kugbFTf53O9L',$,'S2','Quarto',$,#10,#25,$,.ELEMENT.,.INTERNAL.,$);
#40=IFCRELAGGREGATES('9YvctVUKr0kugbFTf53O9L',$,$,$,#11,(#26,#36));
ENDSEC;
END-ISO-10303-21;
"""


@unittest.skipUnless(NO_REPO, "só no repositório")
class Norte(unittest.TestCase):
    """Regra da dona (22/11/2026): o norte sempre indicado em sistemas de construção."""
    def test_vista_le_e_mostra_o_norte(self):
        mod = ler(MODULO)
        for item in ("function norteDoIFC", "IFCGEOMETRICREPRESENTATIONCONTEXT", "TrueNorth", "p3d-norte",
                     "Norte não informado no modelo [MARCADOR]", "norteNaImagem", "physis_norte"):
            self.assertIn(item, mod)

    def test_planejador_e_pagina_passam_o_norte(self):
        self.assertIn("norte=Physis3D.norteDoIFC(IFC_API,m,WebIFC)", ler(PLANEJADOR))
        self.assertIn("{norte,nome:", ler(PLANEJADOR))
        self.assertIn("Physis3D.norteDoIFC(api, m0, WebIFC)", ler(PAGINA))

    def test_blender_le_o_norte_do_glb(self):
        import importlib.util, json, struct, tempfile
        spec = importlib.util.spec_from_file_location("renderizar_glb", RAIZ / "ferramentas" / "renderizar_glb.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        def glb(extras):
            js = json.dumps({"asset": {"version": "2.0", **({"extras": extras} if extras else {})}}).encode()
            js += b" " * ((4 - len(js) % 4) % 4)
            return struct.pack("<III", 0x46546C67, 2, 20 + len(js)) + struct.pack("<II", len(js), 0x4E4F534A) + js
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.glb", Path(d) / "b.glb"
            a.write_bytes(glb({"physis_norte": {"x": 0, "y": 1}}))
            b.write_bytes(glb(None))
            self.assertEqual(mod.norte_do_glb(a), (0.0, 1.0))
            self.assertIsNone(mod.norte_do_glb(b))
        self.assertIn('"N?"', ler(RAIZ / "ferramentas" / "blender_cena.py"))


def _tem_ifcopenshell():
    try:
        import ifcopenshell, ifcpatch  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(NO_REPO, "só no repositório")
class BancoDaModelagem(unittest.TestCase):
    """IFC + SQLite (decisão da dona M&A pg:36f2ad6f5402): o IFC é a fonte; cada revisão vira um SQLite consultável."""
    def carregar(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("ifc_para_sqlite", RAIZ / "ferramentas" / "ifc_para_sqlite.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_sem_ifcopenshell_avisa(self):
        self.assertIn("pip install --user ifcopenshell ifcpatch", ler(RAIZ / "ferramentas" / "ifc_para_sqlite.py"))

    @unittest.skipUnless(_tem_ifcopenshell(), "IfcOpenShell não instalado nesta máquina")
    def test_converte_e_registra_a_revisao(self):
        import json, sqlite3, tempfile
        mod = self.carregar()
        with tempfile.TemporaryDirectory() as d:
            ifc, db = Path(d) / "dois.ifc", Path(d) / "dois.sqlite"
            ifc.write_text(IFC_DOIS_AMBIENTES, encoding="utf-8")
            r = mod.converter(ifc, db, geometria=False)
            self.assertFalse(r["ja_existia"])
            self.assertTrue(mod.converter(ifc, db, geometria=False)["ja_existia"])     # a mesma revisão não duplica
            from contextlib import closing
            with closing(sqlite3.connect(db)) as c:
                self.assertEqual(c.execute("SELECT count(*) FROM IfcSpace").fetchone()[0], 2)
                arq, sha, esquema, _, cont = c.execute("SELECT * FROM physis_revisao").fetchone()
            self.assertEqual((arq, esquema, len(sha)), ("dois.ifc", "IFC4", 64))
            self.assertEqual(json.loads(cont)["IfcSpace"], 2)


if __name__ == "__main__":
    unittest.main()
