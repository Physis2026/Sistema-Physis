"""Preferências de leitura e acessibilidade iguais em todas as telas (sistema/physis-preferencias.js).

Protege:
1. O módulo funciona sem internet e com a Content-Security-Policy: nada de fora, nada de eval/new Function.
2. Cada tela leva uma cópia IGUAL ao original (bloco <script id="physis-preferencias">) e chama PhysisPreferencias.iniciar.
3. A barra tem os 4 controles combinados (Idioma, Tema, Modo de conforto, Acessibilidade (PcD)) e os itens de cada painel,
   em português e em inglês; comandos de voz e Libras (VLibras) começam desligados e nada é carregado de fora.
4. Os dicionários de inglês são válidos e cobrem todo texto fixo da página de consultoria e do SustainKit.
5. Sem id repetido e um título (h1) só nas telas.

Só roda dentro do repositório (as telas de sistema/ e modulos/ não vão no pacote do cliente).
"""
import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MODULO = RAIZ / "sistema" / "physis-preferencias.js"
NO_REPO = MODULO.is_file() and (RAIZ / "modulos" / "planejador").is_dir()

CONSULTORIA = RAIZ / "physis-hub" / "web" / "consultoria.html"
SUSTAINKIT = RAIZ / "sistema" / "SustainKit_Definitivo.html"
PLANEJADOR = RAIZ / "modulos" / "planejador" / "planejador-physis.html"
DEMOS = sorted((RAIZ / "demos").glob("physis-demo-*.html"))
# demos/ é gerada por demos/gerar_demos.py a partir dos originais; só a do Planejador leva este módulo
# (as outras vêm da plataforma e do SCADA, que têm a barra de preferências própria, com os mesmos controles).
PAGINAS = [CONSULTORIA, SUSTAINKIT, PLANEJADOR, RAIZ / "demos" / "physis-demo-planejador.html", RAIZ / "demos" / "physis-demo-sustainkit.html"]

ROTULOS_PT = ["Idioma", "Tema", "Claro", "Escuro (verde)", "Automático", "Modo de conforto", "Acessibilidade (PcD)",
              "Texto maior", "Mais espaçamento", "Menos estímulo", "Foco reforçado", "Fonte para dislexia",
              "Régua de leitura", "Modo leitura simplificada", "Lembrar onde parei",
              "Cegueira e baixa visão", "Ouvir esta tela", "Alto contraste", "Atalhos de teclado", "Surdez", "Libras (VLibras)",
              "Fala", "Comunicação alternativa (CAA)", "Preciso de ajuda", "Não entendi", "Quero falar com uma pessoa", "Sim", "Não",
              "Pode repetir de outro jeito?", "Mobilidade", "Comandos de voz", "Relatar barreira", "Declaração de acessibilidade",
              "Pular para o conteúdo", "Lei 13.146/2015", "eMAG", "WCAG 2.2", "ABNT NBR 17225"]
ROTULOS_EN = ["Language", "Theme", "Light", "Dark (green)", "Automatic", "Comfort mode", "Accessibility (disability)",
              "Listen to this screen", "Report a barrier", "Accessibility statement", "Voice commands", "Skip to content"]

IGNORAR = {"script", "style", "textarea", "noscript", "template", "code", "pre"}
ATRIBUTOS = {"aria-label", "title", "placeholder", "alt", "label"}
VAZIOS = {"br", "img", "input", "meta", "link", "hr", "source", "wbr", "area", "col"}


class Textos(HTMLParser):
    """Textos fixos de uma página (nós de texto e atributos lidos por leitor de tela), como o módulo os vê."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pilha, self.textos, self.ids, self.h1 = [], [], [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a and tag not in ("script", "style"):
            self.ids.append(a["id"])
        if tag == "h1":
            self.h1 += 1
        manter = "data-pp-manter" in a or a.get("translate") == "no"
        if tag not in VAZIOS:
            self.pilha.append((tag, manter))
        if any(t in IGNORAR or m for t, m in self.pilha) or manter:
            return
        for k, v in attrs:
            if k in ATRIBUTOS and v and re.search(r"[A-Za-zÀ-ÿ]", v):
                self.textos.append(re.sub(r"\s+", " ", v).strip())
        if tag == "input" and a.get("type") in ("button", "submit", "reset") and a.get("value"):
            self.textos.append(a["value"].strip())

    def handle_endtag(self, tag):
        for i in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[i][0] == tag:
                del self.pilha[i:]
                break

    def handle_data(self, d):
        if any(t in IGNORAR or m for t, m in self.pilha):
            return
        k = re.sub(r"\s+", " ", d).strip()
        if k and re.search(r"[A-Za-zÀ-ÿ]", k):
            self.textos.append(k)


def ler_textos(html):
    p = Textos()
    p.feed(html.split("<body", 1)[1])
    return p


def objeto_js(html, nome):
    """Lê o objeto literal `nome: { ... }` (chaves e valores entre aspas duplas) como JSON.
    Usa o último da página: o primeiro é o exemplo no comentário do módulo embutido."""
    i = html.rindex(nome + (" {" if nome.endswith("=") else ": {"))
    j = html.index("{", i)
    prof, k = 0, j
    em_texto = False
    while True:
        c = html[k]
        if em_texto:
            if c == "\\":
                k += 1
            elif c == '"':
                em_texto = False
        elif c == '"':
            em_texto = True
        elif c == "{":
            prof += 1
        elif c == "}":
            prof -= 1
            if prof == 0:
                break
        k += 1
    bruto = html[j:k + 1]
    bruto = re.sub(r"/\*.*?\*/", "", bruto, flags=re.S)
    bruto = re.sub(r",\s*}", "}", bruto)
    return json.loads(bruto)


def lista_js(html, nome):
    i = html.rindex(nome + (" [" if nome.endswith("=") else ": ["))
    j = html.index("]", i)
    return json.loads(html[html.index("[", i):j + 1])


# ---------- Planejador: textos que o código escreve na tela ----------
# Exceções documentadas: o que o extrator acha mas NÃO é texto de tela (pedaços de SVG/HTML montados no código,
# classes CSS, seletores, media query, nomes de tipo GeoJSON, a diretiva "use strict") e códigos de norma (iguais em inglês).
NAO_E_TELA_PLANEJADOR = re.compile(
    r'^(" .*|"\] polygon|\(prefers-contrast: more\)|btn primary|bubble b-a|logo dk|logo lt|proximo p-|tbody tr|thead th|use strict|Title'
    r'|Point coordinates, LineString coordinates|NBR [\d\-]+)$')
# Instrução enviada ao assistente de IA (não aparece na tela; o assistente responde em português).
TEXTO_PARA_IA_PLANEJADOR = re.compile(r"^Você é o assistente técnico do Planejador Physis")


def _literais_js(src):
    """Varre o JS e devolve cada literal de texto; de um template `...${x}...` saem os pedaços fixos."""
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c == "/" and src[i + 1:i + 2] == "/":
            j = src.find("\n", i); i = n if j < 0 else j; continue
        if c == "/" and src[i + 1:i + 2] == "*":
            j = src.find("*/", i + 2); i = n if j < 0 else j + 2; continue
        if c in "'\"":
            j, buf = i + 1, []
            while j < n and src[j] != c and src[j] != "\n":
                if src[j] == "\\":
                    buf.append(src[j:j + 2]); j += 2; continue
                buf.append(src[j]); j += 1
            out.append("".join(buf)); i = j + 1; continue
        if c == "`":
            j, buf = i + 1, []
            while j < n and src[j] != "`":
                if src[j] == "\\":
                    buf.append(src[j:j + 2]); j += 2; continue
                if src[j] == "$" and src[j + 1:j + 2] == "{":
                    out.append("".join(buf)); buf = []; k, d = j + 2, 1
                    while k < n and d:
                        if src[k] == "{": d += 1
                        elif src[k] == "}": d -= 1
                        elif src[k] in "'\"`":
                            q = src[k]; k += 1
                            while k < n and src[k] != q:
                                k += 2 if src[k] == "\\" else 1
                        k += 1
                    out.extend(_literais_js(src[j + 2:k - 1])); j = k; continue
                buf.append(src[j]); j += 1
            out.append("".join(buf)); i = j + 1; continue
        if c == "/":                                   # expressão regular: pula
            k = i - 1
            while k >= 0 and src[k] in " \t": k -= 1
            if k < 0 or src[k] in "(,=:[!&|?{};+-*%<>~^\n":
                j, cls = i + 1, False
                while j < n and src[j] != "\n":
                    if src[j] == "\\": j += 2; continue
                    if src[j] == "[": cls = True
                    elif src[j] == "]": cls = False
                    elif src[j] == "/" and not cls: break
                    j += 1
                i = j + 1; continue
        i += 1
    return out


def _visivel(s):
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), s.replace("\\n", "\n").replace("\\'", "'").replace('\\"', '"'))
    k = re.sub(r"\s+", " ", s).strip()
    if len(k) < 2 or not re.search(r"[A-Za-zÀ-ÿ]{2}", k): return None
    if re.search(r"[{}<>]|=>|https?:|^data:|^[#.\[][\w-]|^[a-z-]+:\S|;\S", k): return None   # código, CSS, seletor, HTML
    if re.fullmatch(r"[a-z0-9_.\-/]+", k) or re.fullmatch(r"[A-Z0-9_.\-/]+", k): return None  # chaves, ids, siglas
    if " " not in k and not re.search(r"[áéíóúâêôãõçÁÉÍÓÚ]", k) and not re.fullmatch(r"[A-ZÀ-Ý][a-zà-ÿ]+", k): return None
    return k


def literais_planejador(html):
    """Textos do aplicativo do Planejador (o bloco <script> sem id depois do pp-planejador; bibliotecas ficam de fora)."""
    i = html.index('<script id="pp-planejador">')
    i = html.index("<script>", i) + len("<script>")
    src = html[i:html.index("</script>", i)]
    return sorted({k for k in map(_visivel, _literais_js(src)) if k})


@unittest.skipUnless(NO_REPO, "só no repositório")
class Modulo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = MODULO.read_text(encoding="utf-8")

    def test_sem_internet_nem_eval(self):
        self.assertNotRegex(self.js, r"https?://", "o módulo não pode buscar nada fora")
        self.assertNotRegex(self.js, r"\beval\s*\(")
        self.assertNotIn("new Function", self.js)
        self.assertNotIn("document.write", self.js)
        self.assertNotRegex(self.js, r"(?i)</script")       # vai embutido dentro de <script>
        self.assertNotIn("vlibras.gov.br", self.js)         # VLibras: a instalar no servidor, nunca de fora
        self.assertNotRegex(self.js, r"\bimportScripts|\bimport\s*\(")

    def test_rotulos_nas_duas_linguas(self):
        for r in ROTULOS_PT + ROTULOS_EN:
            self.assertIn(r, self.js, r)
        pt = self.js[self.js.index("pt: {"):self.js.index("en: {")]
        en = self.js[self.js.index("en: {"):self.js.index("var CSS")]
        chaves = lambda s: set(re.findall(r"(?:^|[{,])\s*(\w+): \"", s, re.M))
        self.assertEqual(chaves(pt), chaves(en), "todo texto da barra precisa existir em português e em inglês")

    def test_voz_e_libras_comecam_desligados(self):
        padrao = re.search(r"var PADRAO = \{(.*?)\};", self.js, re.S).group(1)
        for k in ("voz", "libras", "conforto", "verde", "contraste", "regua"):
            self.assertRegex(padrao, rf"\b{k}: false", k)
        self.assertIn('tema: "auto"', padrao)
        self.assertIn("try { global.localStorage", self.js)          # guarda sempre protegido

    def test_atalhos(self):
        for a in ("Alt+1", "Alt+2", "Alt+3", "Alt+0"):
            self.assertIn(a, self.js)


@unittest.skipUnless(NO_REPO, "só no repositório")
class Paginas(unittest.TestCase):
    def test_copias_iguais_ao_original(self):
        original = MODULO.read_text(encoding="utf-8").replace("\r\n", "\n")
        for pag in PAGINAS:
            with self.subTest(pag.name):
                html = pag.read_text(encoding="utf-8")
                m = re.search(r'<script id="physis-preferencias">\n(.*?)</script>', html, re.S)
                self.assertIsNotNone(m, "falta o bloco do módulo")
                self.assertEqual(m.group(1), original, "cópia diferente de sistema/physis-preferencias.js")
                self.assertEqual(html.count('<script id="physis-preferencias">'), 1)
                self.assertIn("PhysisPreferencias.iniciar(", html)
                self.assertIn("data-physis-preferencias", html)
                self.assertIn('chave: "physis-pref"', html)

    def test_sem_id_repetido_e_um_titulo(self):
        for pag in (CONSULTORIA, SUSTAINKIT):
            with self.subTest(pag.name):
                p = ler_textos(pag.read_text(encoding="utf-8"))
                repetidos = sorted({i for i in p.ids if p.ids.count(i) > 1})
                self.assertEqual(repetidos, [])
                self.assertEqual(p.h1, 1)
                # a barra cria ids pp-*: a página não pode usar os mesmos
                self.assertEqual([i for i in p.ids if i.startswith("pp-") and i != "pp-lugar"], [])
        html = PLANEJADOR.read_text(encoding="utf-8")
        self.assertIn("h('h1',{class:'appname'},'Planejador Physis'", html)
        self.assertNotIn("id:'btn-conforto'", html)     # o modo de conforto é o da barra compartilhada

    def test_dicionarios_validos(self):
        for pag in (CONSULTORIA, SUSTAINKIT, PLANEJADOR):
            with self.subTest(pag.name):
                d = objeto_js(pag.read_text(encoding="utf-8"), "var T =" if pag == PLANEJADOR else "dicionario")
                self.assertGreater(len(d), 40)
                for k, v in d.items():
                    self.assertIsInstance(v, str)
                    self.assertTrue(k.strip() and v.strip(), k)
                    self.assertEqual(k, re.sub(r"\s+", " ", k).strip(), f"chave com espaço sobrando: {k!r}")
                    self.assertNotRegex(v, r"NBR 15527:2007|LEED v4\.1|Portaria 309/2019", "edição antiga no inglês")

    def test_consultoria_toda_traduzida(self):
        html = CONSULTORIA.read_text(encoding="utf-8")
        d, exc = objeto_js(html, "dicionario"), set(lista_js(html, "excecoes"))
        faltam = [t for t in ler_textos(html).textos if t not in d and t not in exc]
        self.assertEqual(faltam, [], "textos da consultoria sem inglês")
        # o serviço novo e o consentimento LGPD estão no dicionário
        self.assertIn("Consultoria personalizada com equipe multidisciplinar", d)
        self.assertTrue(any("LGPD" in v for v in d.values()))
        # a edição de textos pausa a tradução (grava sempre o português)
        self.assertIn("PhysisPreferencias.pausar(", html)

    def test_sustainkit_todo_traduzido(self):
        html = SUSTAINKIT.read_text(encoding="utf-8")
        d, exc = objeto_js(html, "dicionario"), set(lista_js(html, "excecoes"))
        por_padrao = {"HPS: — · PR: 0,78 · PVGIS ERA5"}        # coberto por padrão (texto com número)
        faltam = [t for t in ler_textos(html).textos if t not in d and t not in exc and t not in por_padrao]
        self.assertEqual(faltam, [], "textos fixos do SustainKit sem inglês")

    def test_sustainkit_apresentacao_so_na_demo(self):
        """Modo Apresentação é da demo do site: escondido no original (plataforma, /sustainkit/, pacotes)."""
        html = SUSTAINKIT.read_text(encoding="utf-8")
        self.assertRegex(html, r'<button[^>]*id="btn-apresentacao"[^>]*\bhidden>')
        self.assertRegex(html, r'id="sk-exemplo"[^>]*hidden>Dados de exemplo<')
        self.assertIn("quadro=window.self!==window.top", html)          # dentro da plataforma, nunca
        self.assertNotIn('data-physis-demo="sustainkit"', html.split("<head>")[0] + html[:300])
        demo = (RAIZ / "demos" / "physis-demo-sustainkit.html").read_text(encoding="utf-8")
        self.assertIn('<html lang="pt-BR" data-physis-demo="sustainkit">', demo)

    def test_planejador_todo_traduzido(self):
        """Todo texto do código do Planejador que aparece na tela tem inglês (o dicionário T serve inteiro e em pedaços)."""
        html = PLANEJADOR.read_text(encoding="utf-8")
        d, exc = objeto_js(html, "var T ="), set(lista_js(html, "var EXC ="))
        lits = literais_planejador(html)
        self.assertGreater(len(lits), 1000)
        faltam = [k for k in lits if k not in d and k not in exc and not NAO_E_TELA_PLANEJADOR.search(k)
                  and not TEXTO_PARA_IA_PLANEJADOR.search(k)]
        self.assertEqual(faltam, [], "textos do Planejador sem inglês")
        self.assertIn("fragmentos: T", html)


@unittest.skipUnless(NO_REPO and (RAIZ / "demos" / "gerar_demos.py").is_file(), "só no repositório")
class Demos(unittest.TestCase):
    """As demos do site são geradas dos programas de verdade (demos/gerar_demos.py), nunca copiadas à mão."""

    def test_demos_atualizadas(self):
        import subprocess, sys
        r = subprocess.run([sys.executable, str(RAIZ / "demos" / "gerar_demos.py"), "--conferir"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, "rode python demos/gerar_demos.py\n" + r.stdout + r.stderr)

    def test_cada_demo(self):
        nomes = {p.name for p in DEMOS}
        clientes = {"physis-demo-casa-physis.html": "casa-physis", "physis-demo-santa-clara.html": "fazenda-santa-clara",
                    "physis-demo-santa-clara-v2.html": "fazenda-santa-clara-v2"}         # demos por cliente (15/11/2026)
        self.assertEqual(nomes, {"physis-demo-cliente.html", "physis-demo-scada.html", "physis-demo-planejador.html",
                                 "physis-demo-sustainkit.html", "physis-demo-monitoramento.html"} | set(clientes))
        # os módulos de cada demo de cliente são os da ficha (clientes/clientes.json)
        fichas = {f["org"]: f for f in json.loads((RAIZ / "clientes" / "clientes.json").read_text(encoding="utf-8"))["clientes"]}
        for arq, org in clientes.items():
            html = (RAIZ / "demos" / arq).read_text(encoding="utf-8")
            self.assertIn("abrirPlataformaCliente(" + json.dumps(fichas[org]["modulos"]).replace(" ", "") + ", ", html, arq)
            self.assertIn(fichas[org]["nome"].split(" · ")[0], html, arq)
            self.assertEqual(" ui.inst.pesquisa = true;" in html, bool(fichas[org].get("pesquisa")), arq)
        # cada demo promove a compra do item certo da loja
        compra = {"physis-demo-sustainkit.html": "/loja/?item=sk-pacote", "physis-demo-scada.html": "/loja/?item=scada",
                  "physis-demo-monitoramento.html": "/loja/?item=mon-sw", "physis-demo-planejador.html": "/loja/?item=P13",
                  "physis-demo-cliente.html": "/loja/", **{arq: "/loja/" for arq in clientes}}
        for pag in DEMOS:
            with self.subTest(pag.name):
                html = pag.read_text(encoding="utf-8")
                self.assertIn('<meta name="physis-demo-gerado"', html)
                self.assertIn('id="physis-demo-faixa"', html)
                self.assertIn('id="physis-demo-compra"', html)
                self.assertIn("Demonstração · dados simulados</title>", html)
                self.assertIn(f'class="pdf-comprar" href="{compra[pag.name]}"', html)
                self.assertIn("Na versão completa você", html)
                self.assertTrue("data-physis-preferencias" in html or 'id="pxp-lugar"' in html, "falta a barra de preferências")
                for nome in ("rafaella", "oliveira"):
                    self.assertNotIn(nome, html.lower(), "nome da equipe numa demo pública")
                self.assertNotIn('href="physis-tela-cliente.html"', html, "a Tela do cliente saiu")
        for nome in ("physis-demo-sustainkit.html", "physis-demo-scada.html", "physis-demo-monitoramento.html"):
            html = (RAIZ / "demos" / nome).read_text(encoding="utf-8")
            self.assertIn('id="pdf-linha" aria-live="polite"', html, nome)      # dado ao vivo, educado com leitor de tela
            self.assertIn('id="pdf-pausa"', html, nome)                           # e com Pausar
        mon = (RAIZ / "demos" / "physis-demo-monitoramento.html").read_text(encoding="utf-8")
        self.assertIn('abrirPlataformaCliente(["monitoramento"], { campo:6', mon)
        self.assertIn(': "campo"; desenhar(false);', mon)
        self.assertFalse((RAIZ / "demos" / "physis-demo-gestao.html").exists(), "demo obsoleta")
        cliente = (RAIZ / "demos" / "physis-demo-cliente.html").read_text(encoding="utf-8")
        m = re.search(r"abrirPlataformaCliente\((\[[^\]]*\]), \{ campo:6", cliente)
        self.assertIsNotNone(m)
        mods = json.loads(m.group(1))
        for vendavel in ("planejador", "solar", "agua", "monitoramento", "sustainkit", "supervisao", "gestao", "certificacoes"):
            self.assertIn(vendavel, mods)
        for fora in ("animais", "coleiras", "comedouros", "saude", "medicamentos", "pulseira", "turbinas", "avac"):
            self.assertNotIn(fora, mods)


if __name__ == "__main__":
    unittest.main()
