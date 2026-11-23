"""ODF (OpenDocument) gerado pela Physis: estrutura do pacote, XML válido, estilos da identidade e células tipadas.

O gerador do servidor (physis_hub/documentos.py) e o do navegador (sistema/physis-odf.js) seguem o mesmo
modelo. Aqui se confere o do servidor; o do navegador é conferido (1) pelos nomes de estilo e de arquivo
que os dois precisam ter iguais e (2) rodando o JS no Node, quando o Node existe na máquina.
"""
import base64
import datetime as dt
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest import mock

from physis_hub import documentos as D

RAIZ = Path(__file__).resolve().parents[2]
JS = RAIZ / "sistema" / "physis-odf.js"
N = {k: "{" + v + "}" for k, v in D.NS.items()}
QUANDO = dt.datetime(2026, 11, 15, 10, 30, 0)
PNG_1x1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")

BLOCOS = [
    {"h": 1, "t": "Resumo & <metas>"},
    {"t": "Primeiro parágrafo  com   espaços\te tabulação\nnova linha"},
    {"t": "item um", "lista": True}, {"t": "item dois", "lista": True},
    {"t": "passo 1", "lista": "ol"},
    {"h": 2, "t": "Tabela"},
    {"tabela": {"cab": ["Item", "Valor"], "linhas": [["Água", "1.234,56"], ["Energia"]], "legenda": "Fonte: medição"}},
    {"imagem": {"png": PNG_1x1, "alt": "Gráfico de consumo", "largura_px": 800, "altura_px": 400}},
]


def abrir(dados: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(dados))


class EstruturaPacote:
    """Conferências comuns a .odt e .ods (o pacote ODF)."""
    mime = ""

    def conferir_pacote(self, dados: bytes):
        # 1) mimetype é o primeiro arquivo, sem compressão, sem campo extra: os bytes 30.. do arquivo são "mimetype"+tipo
        self.assertEqual(dados[:4], b"PK\x03\x04")
        self.assertEqual(dados[26:28], (8).to_bytes(2, "little"))           # tamanho do nome
        self.assertEqual(dados[28:30], b"\x00\x00")                          # campo extra vazio
        self.assertEqual(dados[30:38], b"mimetype")
        self.assertEqual(dados[38:38 + len(self.mime)], self.mime.encode())
        z = abrir(dados)
        self.assertIsNone(z.testzip())
        primeiro = z.infolist()[0]
        self.assertEqual(primeiro.filename, "mimetype")
        self.assertEqual(primeiro.compress_type, zipfile.ZIP_STORED)
        self.assertEqual(z.read("mimetype").decode(), self.mime)
        # 2) manifesto lista todo arquivo (menos mimetype e o próprio manifesto), com tipo
        man = ET.fromstring(z.read("META-INF/manifest.xml"))
        ent = {e.get(N["manifest"] + "full-path"): e.get(N["manifest"] + "media-type") for e in man}
        self.assertEqual(ent["/"], self.mime)
        nomes = set(z.namelist()) - {"mimetype", "META-INF/manifest.xml"}
        self.assertEqual(set(ent) - {"/"}, nomes)
        for n in nomes:
            self.assertTrue(ent[n], n)
        # 3) todo XML é bem formado; versão 1.3
        for n in ("content.xml", "styles.xml", "meta.xml"):
            raiz = ET.fromstring(z.read(n))
            self.assertEqual(raiz.get(N["office"] + "version"), "1.3", n)
        # 4) meta.xml: título, autor Physis Engineering, gerador e data
        meta = ET.fromstring(z.read("meta.xml")).find(N["office"] + "meta")
        self.assertEqual(meta.findtext(N["meta"] + "initial-creator"), "Physis Engineering")
        self.assertEqual(meta.findtext(N["dc"] + "creator"), "Physis Engineering")
        self.assertIn("Sistema Physis", meta.findtext(N["meta"] + "generator"))
        self.assertEqual(meta.findtext(N["meta"] + "creation-date"), "2026-11-15T10:30:00")
        return z


class TestODT(EstruturaPacote, unittest.TestCase):
    mime = D.MIME_ODT

    def setUp(self):
        self.dados = D.odt("Relatório de água", BLOCOS, sistema="Gestão Physis", logo_png=PNG_1x1, quando=QUANDO)
        self.z = self.conferir_pacote(self.dados)
        self.conteudo = ET.fromstring(self.z.read("content.xml"))
        self.estilos = ET.fromstring(self.z.read("styles.xml"))

    def test_titulo_e_meta(self):
        meta = ET.fromstring(self.z.read("meta.xml")).find(N["office"] + "meta")
        self.assertEqual(meta.findtext(N["dc"] + "title"), "Relatório de água")
        self.assertEqual(meta.findtext(N["dc"] + "language"), "pt-BR")

    def test_titulos_paragrafos_listas(self):
        texto = self.conteudo.find(N["office"] + "body").find(N["office"] + "text")
        hs = texto.findall(N["text"] + "h")
        self.assertEqual([h.get(N["text"] + "outline-level") for h in hs], ["1", "2"])
        self.assertEqual("".join(hs[0].itertext()), "Resumo & <metas>")
        self.assertEqual(hs[0].get(N["text"] + "style-name"), "Heading_20_1")
        listas = texto.findall(N["text"] + "list")
        self.assertEqual(len(listas), 2)                       # marcadores e numerada separadas
        self.assertEqual(listas[0].get(N["text"] + "style-name"), "Lista_20_Physis")
        self.assertEqual(len(listas[0].findall(N["text"] + "list-item")), 2)
        self.assertEqual(listas[1].get(N["text"] + "style-name"), "Lista_20_Numerada")
        # espaços repetidos, tabulação e quebra de linha viram elementos do ODF
        p = [p for p in texto.findall(N["text"] + "p") if "Primeiro" in "".join(p.itertext())][0]
        self.assertIsNotNone(p.find(N["text"] + "s"))
        self.assertIsNotNone(p.find(N["text"] + "tab"))
        self.assertIsNotNone(p.find(N["text"] + "line-break"))

    def test_tabela_com_cabecalho_verde(self):
        tab = self.conteudo.find(f".//{N['table']}table")
        self.assertIsNotNone(tab.find(N["table"] + "table-header-rows"))
        cab = tab.find(f"{N['table']}table-header-rows/{N['table']}table-row")
        self.assertEqual([("".join(c.itertext())) for c in cab], ["Item", "Valor"])
        linhas = tab.findall(N["table"] + "table-row")
        self.assertEqual(len(linhas), 2)
        self.assertEqual(len(linhas[1]), 2)                    # linha curta completada
        estilo = [s for s in self.conteudo.iter(N["style"] + "style") if s.get(N["style"] + "name") == "TabCab"][0]
        self.assertEqual(estilo.find(N["style"] + "table-cell-properties").get(N["fo"] + "background-color"), "#33512f")

    def test_imagem_embutida_com_texto_alternativo(self):
        fr = [f for f in self.conteudo.iter(N["draw"] + "frame")][0]
        img = fr.find(N["draw"] + "image")
        self.assertEqual(img.get(N["xlink"] + "href"), "Pictures/imagem1.png")
        self.assertEqual(self.z.read("Pictures/imagem1.png"), PNG_1x1)
        self.assertEqual(fr.findtext(N["svg"] + "title"), "Gráfico de consumo")
        self.assertEqual(fr.get(N["svg"] + "width"), "17.00cm")       # 800 px a 96 ppp passa de 17 cm: cabe na largura
        self.assertEqual(fr.get(N["svg"] + "height"), "8.50cm")

    def test_estilos_da_identidade(self):
        nomes = {s.get(N["style"] + "name") for s in self.estilos.iter(N["style"] + "style")}
        for n in ("Standard", "Text_20_body", "Title", "Subtitle", "Heading_20_1", "Heading_20_2", "Heading_20_3",
                  "Tabela_20_texto", "Tabela_20_cabecalho", "Header", "Footer", "Marca_20_dagua", "grMarca", "grLogo"):
            self.assertIn(n, nomes)
        h1 = [s for s in self.estilos.iter(N["style"] + "style") if s.get(N["style"] + "name") == "Heading_20_1"][0]
        self.assertEqual(h1.find(N["style"] + "text-properties").get(N["fo"] + "color"), "#33512f")
        self.assertEqual(h1.get(N["style"] + "default-outline-level"), "1")
        fontes = {f.get(N["style"] + "name") for f in self.estilos.iter(N["style"] + "font-face")}
        self.assertTrue({"Fraunces", "Inter"} <= fontes)

    def test_cabecalho_rodape_e_marca_dagua(self):
        mestre = self.estilos.find(f".//{N['style']}master-page")
        cab, rod = mestre.find(N["style"] + "header"), mestre.find(N["style"] + "footer")
        self.assertIn("Gestão Physis", "".join(cab.itertext()))
        logo = [f for f in cab.iter(N["draw"] + "frame") if f.get(N["draw"] + "name") == "LogoPhysis"][0]
        self.assertEqual(logo.find(N["draw"] + "image").get(N["xlink"] + "href"), "Pictures/logo-physis.png")
        self.assertIn("Pictures/logo-physis.png", self.z.namelist())
        marca = cab.find(f".//{N['draw']}custom-shape")
        self.assertEqual(marca.get(N["draw"] + "name"), "MarcaDaguaPhysis")
        self.assertIn("rotate (0.785398", marca.get(N["draw"] + "transform"))
        self.assertEqual("".join(marca.find(N["text"] + "p").itertext()), "PHYSIS")
        self.assertIn("Documento gerado pelo Sistema Physis", "".join(rod.itertext()))
        self.assertIsNotNone(rod.find(f".//{N['text']}page-number"))
        self.assertIsNotNone(rod.find(f".//{N['text']}page-count"))

    def test_sem_logo_e_sem_marca(self):
        z = abrir(D.odt("X", [], logo_png=False, marca_dagua=False, quando=QUANDO))
        self.assertNotIn("Pictures/logo-physis.png", z.namelist())
        self.assertNotIn(b"MarcaDaguaPhysis", z.read("styles.xml"))

    def test_ingles(self):
        z = abrir(D.odt("Report", [{"t": "x"}], idioma="en-GB", logo_png=False, quando=QUANDO))
        self.assertIn("Document generated by Sistema Physis", z.read("styles.xml").decode())

    def test_svg_com_reserva_png(self):
        z = abrir(D.odt("X", [{"imagem": {"png": PNG_1x1, "svg": b"<svg xmlns='http://www.w3.org/2000/svg'/>"}}], logo_png=False, quando=QUANDO))
        c = ET.fromstring(z.read("content.xml"))
        imgs = list(c.iter(N["draw"] + "image"))
        self.assertEqual([i.get(N["draw"] + "mime-type") for i in imgs], ["image/svg+xml", "image/png"])
        man = z.read("META-INF/manifest.xml").decode()
        self.assertIn('manifest:full-path="Pictures/imagem1.svg" manifest:media-type="image/svg+xml"', man)

    def test_caracteres_de_controle_nao_quebram_o_xml(self):
        z = abrir(D.odt("a\x01b", [{"t": "c\x0bd\x00"}], logo_png=False, quando=QUANDO))
        ET.fromstring(z.read("content.xml"))
        ET.fromstring(z.read("meta.xml"))


class TestODS(EstruturaPacote, unittest.TestCase):
    mime = D.MIME_ODS

    def setUp(self):
        self.tabelas = [
            {"nome": "Consumo", "cab": ["Mês", "kWh", "Custo", "Variação", "Data", "CEP", "Obs"],
             "linhas": [["Jan", "1.234,5", "R$ 1.050,00", "-12,5%", "15/11/2026", "01234-567", "ok"],
                        ["Fev", 980, "R$ 10", "3%", dt.date(2026, 2, 1), "01234", None]]},
            {"nome": "Consumo", "cab": ["a"], "linhas": [["1.5"]]},              # nome repetido
            {"nome": "x/y:z?*[]", "linhas": [["sem cabeçalho"]]},
        ]
        self.z = self.conferir_pacote(D.ods("Consumo 2026", self.tabelas, quando=QUANDO))
        self.c = ET.fromstring(self.z.read("content.xml"))

    def folhas(self):
        return self.c.findall(f"{N['office']}body/{N['office']}spreadsheet/{N['table']}table")

    def test_uma_folha_por_tabela_nomes_unicos(self):
        nomes = [t.get(N["table"] + "name") for t in self.folhas()]
        self.assertEqual(len(nomes), 3)
        self.assertEqual(len({n.lower() for n in nomes}), 3)
        self.assertFalse(any(ch in nomes[2] for ch in "[]*?:/\\"))

    def test_cabecalho_com_estilo(self):
        t = self.folhas()[0]
        cab = t.find(f"{N['table']}table-header-rows/{N['table']}table-row")
        celulas = cab.findall(N["table"] + "table-cell")
        self.assertEqual(["".join(c.itertext()) for c in celulas][:3], ["Mês", "kWh", "Custo"])
        self.assertTrue(all(c.get(N["table"] + "style-name") == "ceCab" for c in celulas))
        est = [s for s in self.c.iter(N["style"] + "style") if s.get(N["style"] + "name") == "ceCab"][0]
        self.assertEqual(est.find(N["style"] + "text-properties").get(N["fo"] + "font-weight"), "bold")
        self.assertEqual(est.find(N["style"] + "table-cell-properties").get(N["fo"] + "background-color"), "#4b7547")

    def test_numeros_tipados(self):
        t = self.folhas()[0]
        linhas = t.findall(N["table"] + "table-row")[-2:]
        a = linhas[0].findall(N["table"] + "table-cell")
        tipos = [(c.get(N["office"] + "value-type"), c.get(N["office"] + "value") or c.get(N["office"] + "date-value")) for c in a]
        self.assertEqual(tipos[0], ("string", None))
        self.assertEqual(tipos[1], ("float", "1234.5"))
        self.assertEqual(tipos[2], ("currency", "1050"))
        self.assertEqual(a[2].get(N["office"] + "currency"), "BRL")
        self.assertEqual(tipos[3], ("percentage", "-0.125"))
        self.assertEqual(tipos[4], ("date", "2026-11-15"))
        self.assertEqual(tipos[5][0], "string")                # CEP fica texto
        self.assertEqual("".join(a[1].itertext()), "1.234,5")   # exibe como foi escrito
        b = linhas[1].findall(N["table"] + "table-cell")
        self.assertEqual((b[1].get(N["office"] + "value-type"), b[1].get(N["office"] + "value")), ("float", "980"))
        self.assertEqual(b[4].get(N["office"] + "date-value"), "2026-02-01")
        self.assertEqual("".join(b[4].itertext()), "01/02/2026")
        self.assertEqual(b[5].get(N["office"] + "value-type"), "string")
        self.assertIsNone(b[6].get(N["office"] + "value-type"))    # vazio
        # "1.5" é ambíguo em pt-BR: fica texto
        c2 = self.folhas()[1].findall(N["table"] + "table-row")[-1].findall(N["table"] + "table-cell")[0]
        self.assertEqual(c2.get(N["office"] + "value-type"), "string")

    def test_formatos_de_numero(self):
        nomes = {e.get(N["style"] + "name") for e in self.c.iter() if e.get(N["style"] + "name")}
        self.assertTrue({"N_num", "N_brl", "N_pct", "N_data", "ceNum", "ceMoeda", "cePct", "ceData"} <= nomes)
        moeda = [s for s in self.c.iter(N["style"] + "style") if s.get(N["style"] + "name") == "ceMoeda"][0]
        self.assertEqual(moeda.get(N["style"] + "data-style-name"), "N_brl")

    def test_faixa_e_impressao(self):
        t = self.folhas()[0]
        primeira = t.find(N["table"] + "table-row").find(N["table"] + "table-cell")
        self.assertEqual(primeira.get(N["table"] + "style-name"), "ceFaixa")
        self.assertEqual(primeira.get(N["table"] + "number-columns-spanned"), "7")
        estilos = self.z.read("styles.xml").decode()
        self.assertIn("PHYSIS ENGINEERING", estilos)
        self.assertIn("Documento gerado pelo Sistema Physis", estilos)
        self.assertIn("<text:page-number>", estilos)
        sem = abrir(D.ods("X", [{"cab": ["a"], "linhas": [["1"]]}], faixa=False, quando=QUANDO))
        t2 = ET.fromstring(sem.read("content.xml")).find(f".//{N['table']}table")
        self.assertIsNotNone(t2.find(N["table"] + "table-header-rows"))
        self.assertIsNone(t2.find(N["table"] + "table-row/" + N["table"] + "table-cell[@" + N["table"] + "style-name='ceFaixa']"))

    def test_sem_tabelas(self):
        z = self.conferir_pacote(D.ods("Vazio", [], quando=QUANDO))
        self.assertEqual(len(ET.fromstring(z.read("content.xml")).findall(f".//{N['table']}table")), 1)


class TestCelula(unittest.TestCase):
    def test_interpretar(self):
        f = D.interpretar_celula
        self.assertEqual(f("1.234.567,89"), ("float", 1234567.89))
        self.assertEqual(f("42"), ("float", 42.0))
        self.assertEqual(f("−3,5"), ("float", -3.5))
        self.assertEqual(f("R$ 2.000"), ("currency", 2000.0))
        self.assertEqual(f("50%"), ("percentage", 0.5))
        self.assertEqual(f("29/02/2024"), ("date", "2024-02-29"))
        self.assertEqual(f("31/02/2024")[0], "string")
        self.assertEqual(f("2026-11-15"), ("date", "2026-11-15"))
        self.assertEqual(f("0800")[0], "string")
        self.assertEqual(f("0,5"), ("float", 0.5))
        self.assertEqual(f("12 kWh")[0], "string")
        self.assertEqual(f("1.5")[0], "string")
        self.assertEqual(f(""), ("vazio", ""))
        self.assertEqual(f(True), ("boolean", True))
        self.assertEqual(f(float("nan"))[0], "string")


class TestPDFA(unittest.TestCase):
    def test_sem_libreoffice_501(self):
        with mock.patch.dict(os.environ, {"PHYSIS_SOFFICE": ""}), mock.patch("shutil.which", return_value=None):
            r = D.converter_pdfa(D.odt("x", [], logo_png=False))
        self.assertFalse(r["ok"])
        self.assertEqual(r["codigo"], 501)

    def test_recusa_o_que_nao_e_odf(self):
        r = D.converter_pdfa(b"%PDF-1.4", programa="soffice")
        self.assertEqual(r["codigo"], 400)

    def test_comando_pdfa2(self):
        visto = {}

        def falso(cmd, capture_output, timeout):
            visto["cmd"] = cmd
            pasta = Path(cmd[cmd.index("--outdir") + 1])
            (pasta / "documento.pdf").write_bytes(b"%PDF-1.7\n<pdfaid:part>2</pdfaid:part>\n%%EOF")
            return subprocess.CompletedProcess(cmd, 0, b"", b"")

        with mock.patch("subprocess.run", side_effect=falso):
            r = D.converter_pdfa(D.odt("x", [], logo_png=False), programa="soffice")
        self.assertTrue(r["ok"])
        self.assertTrue(r["pdfa"])
        self.assertIn("--headless", visto["cmd"])
        filtro = visto["cmd"][visto["cmd"].index("--convert-to") + 1]
        self.assertTrue(filtro.startswith("pdf:writer_pdf_Export:"))
        self.assertEqual(json.loads(filtro.split(":", 2)[2])["SelectPdfVersion"]["value"], "2")


class TestJSEspelho(unittest.TestCase):
    """sistema/physis-odf.js precisa sair com a mesma estrutura do gerador do servidor."""

    def setUp(self):
        if not JS.is_file():
            self.skipTest("sistema/physis-odf.js ausente")
        self.js = JS.read_text(encoding="utf-8")

    def test_mesmos_nomes(self):
        for nome in ("mimetype", "META-INF/manifest.xml", "content.xml", "styles.xml", "meta.xml", "Pictures/logo-physis.png",
                     "Heading_20_", "Text_20_body", "Lista_20_Physis", "Lista_20_Numerada", "Tabela_20_cabecalho", "Tabela_20_texto",
                     "TabCab", "TabCel", "MarcaDaguaPhysis", "Marca_20_dagua", "grMarca", "grLogo", "LogoPhysis", "TSistema",
                     "ceCab", "ceNum", "ceMoeda", "cePct", "ceData", "ceFaixa", "N_num", "N_brl", "N_pct", "N_data",
                     "Physis Engineering", "Documento gerado pelo Sistema Physis", 'office:version="1.3"',
                     "application/vnd.oasis.opendocument.text", "application/vnd.oasis.opendocument.spreadsheet",
                     "rotate (0.785398163397448)", "CompressionStream", "deflate-raw"):
            self.assertIn(nome, self.js, nome)

    @unittest.skipUnless(shutil.which("node"), "Node ausente: o JS é conferido em ferramentas/conferir-odf.html")
    def test_js_gera_pacote_valido(self):
        roteiro = (
            "globalThis.window = globalThis; require(" + json.dumps(str(JS)) + ");"
            "const b = " + json.dumps([{"h": 1, "t": "Título"}, {"t": "a", "lista": True}, {"tabela": {"cab": ["A"], "linhas": [["1,5"]]}}]) + ";"
            "Promise.all([PhysisODF.odt({titulo: 'T', blocos: b}, {logo: false, data: new Date(2026,10,15,10,30,0)}),"
            " PhysisODF.ods([{nome: 'F', cab: ['A','B'], linhas: [['1.234,5', '15/11/2026']]}], {titulo: 'T', data: new Date(2026,10,15,10,30,0)})])"
            ".then(r => process.stdout.write(JSON.stringify(r.map(u => Buffer.from(u).toString('base64')))));")
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "roda.js"
            arq.write_text(roteiro, encoding="utf-8")
            p = subprocess.run(["node", str(arq)], capture_output=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace"))
        odt_b, ods_b = [base64.b64decode(x) for x in json.loads(p.stdout)]
        for dados, mime in ((odt_b, D.MIME_ODT), (ods_b, D.MIME_ODS)):
            t = EstruturaPacote()
            t.mime = mime
            for nome in ("assertEqual", "assertIsNone", "assertTrue", "assertIn"):
                setattr(t, nome, getattr(self, nome))
            t.conferir_pacote(dados)
        c = ET.fromstring(abrir(ods_b).read("content.xml"))
        valores = [e.get(N["office"] + "value") for e in c.iter(N["table"] + "table-cell") if e.get(N["office"] + "value-type") == "float"]
        self.assertIn("1234.5", valores)


if __name__ == "__main__":
    unittest.main()
