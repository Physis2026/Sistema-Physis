"""Módulo AVAC personalizado da Estermic (modulos/estermic/), VERSÃO DE TESTE de 20/11/2026.

Protege:
1. A cópia personalizada do AVAC é igual ao módulo base (sistema/physis-avac.js) enquanto nenhum aprendizado de cálculo
   estiver registrado em aprendizados-modulo-padrao.json; os casos de teste também.
2. Independência e regras da tela: nada de internet, eval ou envio de e-mail; um <h1> só; lang, viewport, main, nav e footer;
   tema escuro; só cores da PALETA.md; "VERSÃO DE TESTE" marcada; pedido de nota só como RASCUNHO.
3. Nada inventado: subprojetos, e-mail do contador, marca do cliente e códigos de peça começam vazios ([MARCADOR]).
4. No navegador sem tela (Edge ou Chrome, se houver): o arnês ferramentas/testes-navegador/teste-estermic.html passa
   inteiro; o ODT e o ODS gerados são ODF válidos no template do CLIENTE (sem a marca Physis além do "Elaborado por");
   o IFC tem um equipamento por item; a tela abre na seleção do cliente e nas abas.
"""
import base64
import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.dom import minidom

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "modulos" / "estermic"
NO_REPO = (PASTA / "estermic-avac.js").is_file()
NAVEGADORES = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
               r"C:\Program Files\Google\Chrome\Application\chrome.exe", "/usr/bin/chromium", "/usr/bin/google-chrome", "/usr/bin/microsoft-edge"]


def navegador():
    for c in NAVEGADORES:
        if os.path.isfile(c):
            return c
    return shutil.which("chromium") or shutil.which("google-chrome")


def dom(url, espera_ms=8000):
    with tempfile.TemporaryDirectory() as ud:
        r = subprocess.run([navegador(), "--headless=new", "--disable-gpu", "--no-first-run", "--user-data-dir=" + ud,
                            "--allow-file-access-from-files", f"--virtual-time-budget={espera_ms}", "--dump-dom", url],
                           capture_output=True, timeout=120)
    return r.stdout.decode("utf-8", "replace")


def pre(texto, ident):
    m = re.search(r'<pre id="%s">(.*?)</pre>' % ident, texto, re.S)
    return html.unescape(m.group(1)) if m else ""


@unittest.skipUnless(NO_REPO, "só no repositório")
class Estatico(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (PASTA / "estermic-avac.html").read_text(encoding="utf-8")
        cls.js = (PASTA / "estermic-avac.js").read_text(encoding="utf-8")
        cls.apr = json.loads((PASTA / "aprendizados-modulo-padrao.json").read_text(encoding="utf-8"))

    def test_copia_igual_a_base_ou_registrada(self):
        base, copia = (RAIZ / "sistema" / "physis-avac.js").read_bytes(), (PASTA / "avac-estermic-copia.js").read_bytes()
        muda = [a for a in self.apr["aprendizados"] if a.get("muda_calculo")]
        if base != copia:
            self.assertTrue(muda, "a cópia do AVAC mudou: registre o aprendizado com muda_calculo=true")
        else:
            self.assertEqual(hashlib.sha256(base).hexdigest(), self.apr["copia_base"]["sha256_base_quando_copiado"],
                             "a base mudou depois da cópia: copie de novo e atualize o sha256 em aprendizados-modulo-padrao.json")
        self.assertEqual((RAIZ / "sistema" / "physis-avac-casos.json").read_bytes(), (PASTA / "avac-estermic-casos.json").read_bytes())

    def test_aprendizados_bem_formados(self):
        ids = [a["id"] for a in self.apr["aprendizados"]]
        self.assertEqual(len(ids), len(set(ids)))
        for a in self.apr["aprendizados"]:
            for k in ("data", "area", "descricao", "onde", "levar_para", "estado"):
                self.assertTrue(a.get(k), f"{a['id']} sem {k}")

    def test_independencia(self):
        for nome, txt in (("html", self.html), ("js", self.js)):
            sem_coment = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)
            self.assertNotRegex(sem_coment, r'(src|href)\s*=\s*["\']?https?://', nome)
            self.assertNotRegex(sem_coment, r"\beval\s*\(|new Function", nome)
            self.assertNotRegex(sem_coment, r"(?i)mailto:|smtp|sendmail|/api/(email|enviar)", nome + ": nada de enviar e-mail")
        for src in re.findall(r'<script src="([^"]+)"', self.html):
            self.assertTrue((PASTA / src).resolve().is_file(), src)

    def test_estrutura_da_tela(self):
        h = self.html
        self.assertEqual(len(re.findall(r"<h1\b", re.sub(r"<script\b.*?</script>", "", h, flags=re.S))), 1)
        for p in ('<html lang="pt-BR"', 'name="viewport"', "<main", "<nav", "<footer", 'html[data-tema="escuro"]', "VERSÃO DE TESTE",
                  "PhysisPreferencias.iniciar", "44.982.448/0001-23", "Selecionar cliente", "Pedir nota ao contador", "Elaborado por"):
            self.assertIn(p, h + self.js, p)
        self.assertIn("min-height:44px", h)

    def test_so_cores_da_paleta(self):
        paleta = {c.upper() for c in re.findall(r"#[0-9A-Fa-f]{6}", (RAIZ / "physis-hub" / "docs" / "PALETA.md").read_text(encoding="utf-8"))}
        for c in set(re.findall(r"#[0-9A-Fa-f]{6}", self.html + self.js)):
            self.assertIn(c.upper(), paleta, c)

    def test_nada_inventado_no_padrao(self):
        self.assertRegex(self.js, r'contador:\{ nome:"Robson", email:"" \}')
        self.assertRegex(self.js, r'marcaCliente:\{ nome:"Estermic", logoPng:null, fonteTitulo:"", fonteTexto:"", corPrincipal:""')
        self.assertIn("[1, 2, 3, 4].map(subprojeto)", self.js)
        self.assertIn('nome:"", escopo:""', self.js)


@unittest.skipUnless(NO_REPO and navegador(), "precisa do repositório e de Edge/Chrome")
class NoNavegador(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = dom((RAIZ / "ferramentas" / "testes-navegador" / "teste-estermic.html").as_uri())

    def test_arnes_inteiro(self):
        s = pre(self.d, "saida")
        m = re.search(r"RESULTADO (\d+)/(\d+)", s)
        self.assertTrue(m, s[:500])
        self.assertEqual(m.group(1), m.group(2), s)

    def _zip(self, ident, mime):
        z = zipfile.ZipFile(io.BytesIO(base64.b64decode(pre(self.d, ident))))
        info = z.infolist()
        self.assertEqual(info[0].filename, "mimetype")
        self.assertEqual(info[0].compress_type, zipfile.ZIP_STORED)
        self.assertEqual(z.read("mimetype").decode(), mime)
        self.assertIsNone(z.testzip())
        for n in z.namelist():
            if n.endswith(".xml"):
                minidom.parseString(z.read(n))
        return z

    def test_odt_no_template_do_cliente(self):
        z = self._zip("odt", "application/vnd.oasis.opendocument.text")
        est, cont = z.read("styles.xml").decode(), z.read("content.xml").decode()
        self.assertIn("Estermic · Memorial de cálculo · VERSÃO DE TESTE", est)
        self.assertIn("Elaborado por Physis Engineering", est)
        self.assertNotIn("PHYSIS ENGINEERING", est + cont)
        self.assertNotIn("#33512F".lower(), (est + cont).lower())
        self.assertIn("EXEMPLO", cont)
        self.assertIn("NBR 16401-1", cont)

    def test_ods_lista_e_financeiro(self):
        z = self._zip("ods", "application/vnd.oasis.opendocument.spreadsheet")
        cont = z.read("content.xml").decode()
        self.assertEqual(cont.count("<table:table "), 2)
        self.assertIn("[MARCADOR: part number]", cont)
        self.assertIn("AC-01", cont)

    def test_ifc(self):
        t = pre(self.d, "ifc")
        self.assertTrue(t.startswith("ISO-10303-21;"))
        self.assertIn("IFCSITE(", t)
        self.assertGreater(t.count("IFCUNITARYEQUIPMENT("), 0)

    def test_rascunho_eml(self):
        t = pre(self.d, "eml")
        self.assertTrue(t.startswith("X-Unsent: 1"))
        self.assertIn("To: [MARCADOR: e-mail do Robson]", t)

    def test_tela_abre_no_cliente_e_nas_abas(self):
        url = (PASTA / "estermic-avac.html").as_uri()
        d0 = dom(url)
        self.assertIn("Selecionar cliente", d0)
        self.assertIn("Abrir inclusão de projeto", d0)
        for aba, texto in (("projeto", "Fases e prazos"), ("fin", "Alertas e prazos"), ("equip", "Trazer do cálculo AVAC"),
                           ("bimgis", "Baixar IFC do subprojeto"), ("emissao", "Memorial de cálculo (ODT)"), ("pend", "Pendências"),
                           ("calculo", "módulo base, cópia Estermic")):
            d = dom(url + "?cliente=estermic&aba=" + aba)
            m = re.search(r"<main\s.*?</main>", d, re.S)
            self.assertTrue(m, aba)
            self.assertIn(texto, m.group(0), aba)
            self.assertNotIn("Não foi possível", m.group(0), aba)
            self.assertNotIn("Carregando", m.group(0), aba)


if __name__ == "__main__":
    unittest.main()
