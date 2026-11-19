"""Inglês do Servidor verde, do Secador solar, dos Parceiros e da base de plantas (sem navegador).

Protege:
1. sistema/physis-i18n-modulos.json: todo par tem inglês não vazio; toda regra (I18N_RX) compila e tem inglês;
   as duas regras genéricas (" · ") ficam no fim, para não passarem na frente das específicas.
2. Servidor verde e Secador: o dicionário do módulo (SERVIDOR_VERDE_I18N, SECADOR_I18N) está no JSON ou no I18N do
   painel, com o mesmo inglês que a tela mostra, e as regras com números (..._I18N_RX) estão no JSON (o painel só lê
   regras de lá); todo texto fixo da tela tem par ou é pedaço fixo de uma regra. O catálogo do Servidor verde também.
3. Parceiros: a tela se traduz sozinha (PARCEIROS.I18N e I18N_RX, como PhysisConta); todo texto fixo tem par ou regra.
4. Plantas: cada planta tem nome_en (nome comum inglês bem estabelecido ou, sem ele, o nome científico) e o par
   nome → nome_en está no JSON, para a tela de SbN mostrar o nome em inglês.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_preferencias import _literais_js, _visivel      # a mesma leitura de literais da barra de preferências

RAIZ = Path(__file__).resolve().parents[2]
S = RAIZ / "sistema"
JSON_I18N = S / "physis-i18n-modulos.json"
PAINEL = RAIZ / "physis-hub" / "web" / "painel.html"
NO_REPO = JSON_I18N.is_file() and (S / "physis-servidor-verde.js").is_file()
GENERICAS = ["^· (.+)$", "^([^·]+) · (.+)$"]
PT = re.compile(r"[ãõçáéíóúâêôÃÕÇÁÉÍÓÚÂÊÔ]|\b(de|do|da|dos|das|para|com|por|sem|não|uma|um|ao|na|no|em|até|ou|e)\b")

# Literais que não aparecem como texto da tela (chaves, nomes de arquivo, mensagens só de console ou de alert do navegador)
NAO_E_TELA = {
    # sufixo do nome do projeto duplicado (dado da pessoa) e nomes de partida dos componentes,
    # que viram o valor de um campo editável (o valor de um campo não é traduzido)
    "servidor-verde": {"(cópia)",
                       "Raspberry Pi 5 com SSD", "Mini PC (processador, memória, SSD)", "Servidor de IA: placa-mãe, processador e memória",
                       "Placa de vídeo 8 GB", "Placa de vídeo 16 GB", "Servidor x86 (2 processadores, memória)", "Switch de rede"},
    # origem das premissas de cada produto (PRODUTOS[].fonte): documentação do código, não vai para a tela
    "secador": {"Embrapa Café / Consórcio Pesquisa Café: massa até 40 °C para qualidade, 45 °C no máximo; sementes até 35 °C; armazenar com 11 a 12 % b.u. — verificar",
                "literatura de plantas medicinais (óleos essenciais se perdem acima de 35 a 40 °C) — verificar",
                "literatura de secagem de cogumelos: 40 a 55 °C; umidade final perto de 10 % b.u. — verificar",
                "manuais de frutas desidratadas: 55 a 65 °C; umidade final de 15 a 20 % b.u. — verificar",
                "valores genéricos — trocar pelos do produto"},
    "parceiros": set(),
    "frota": set(),
    "validacao": set(),
}


def texto_rx(p):
    """O texto fixo de uma regra: tira âncoras, grupos e escapes, para conferir se um pedaço da tela está nela."""
    p = p.strip("^$").replace("\\(", "\x01").replace("\\)", "\x02")
    antes = None
    while antes != p:                                         # grupos (também os de dentro de outros)
        antes, p = p, re.sub(r"\((?:\?:)?[^()]*\)", "\0", p)
    return re.sub(r"\\(.)", r"\1", p).replace("\x01", "(").replace("\x02", ")")


def objeto(js, inicio):
    """Lê o literal (objeto ou lista, em JSON) que começa logo depois de `inicio`."""
    i = js.index(inicio) + len(inicio)
    abre = js[i]
    fecha = "}" if abre == "{" else "]"
    prof, j = 0, i
    while j < len(js):
        c = js[j]
        if c == '"':
            j += 1
            while js[j] != '"':
                j += 2 if js[j] == "\\" else 1
        elif c == abre:
            prof += 1
        elif c == fecha:
            prof -= 1
            if not prof:
                return json.loads(js[i:j + 1])
        j += 1
    raise ValueError(inicio)


def i18n_do_painel():
    try:
        h = PAINEL.read_text(encoding="utf-8")
        return json.loads(re.search(r"\nconst I18N = (\{.*?\});\n", h, re.S).group(1))
    except (OSError, AttributeError, ValueError):
        return {}


def faltando(js, chaves, regras, ignorar):
    """Textos fixos com cara de português que não têm par nem fazem parte de uma regra."""
    rx = [texto_rx(a) for a, _ in regras]
    out = []
    for lit in _literais_js(js):
        k = _visivel(lit)
        if not k or k in ignorar or not PT.search(k):
            continue
        partes = [p.strip() for p in k.split("·") if PT.search(p)] or [k]       # frase com " · ": cada parte tem o seu par
        if all(p in chaves or any(p in c for c in chaves) or any(p in r for r in rx) for p in partes):
            continue
        out.append(k)
    return sorted(set(out))


@unittest.skipUnless(NO_REPO, "só no repositório")
class JsonDoIngles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads(JSON_I18N.read_text(encoding="utf-8"))

    def test_pares_e_regras_com_ingles(self):
        vazios = [k for k, v in self.d["I18N"].items() if not isinstance(v, str) or not v.strip()]
        self.assertEqual(vazios, [])
        for a, b in self.d["I18N_RX"]:
            re.compile(a)
            self.assertTrue(b.strip(), a)

    def test_genericas_no_fim(self):
        self.assertEqual([a for a, _ in self.d["I18N_RX"][-2:]], GENERICAS)


class _Modulo:
    ARQ = NOME = DIC = RX = None

    @classmethod
    def setUpClass(cls):
        cls.js = (S / cls.ARQ).read_text(encoding="utf-8")
        cls.d = json.loads(JSON_I18N.read_text(encoding="utf-8"))
        cls.dic = objeto(cls.js, cls.DIC)
        cls.rx = objeto(cls.js, cls.RX)

    def codigo_de_tela(self):
        """O código sem os blocos do inglês."""
        js = self.js
        for ini in (self.DIC, self.RX):
            i = js.index(ini)
            j = js.index("\n};" if ini == self.DIC else "\n];", i)
            js = js[:i] + js[j + 3:]
        return js

    def test_dicionario_com_ingles(self):
        self.assertGreater(len(self.dic), 30)
        self.assertEqual([k for k, v in self.dic.items() if not isinstance(v, str) or not v.strip()], [])
        for a, b in self.rx:
            re.compile(a)
            self.assertTrue(b.strip(), a)

    def test_tudo_tambem_no_json(self):
        I = dict(self.d["I18N"], **i18n_do_painel())          # o que a tela mostra: o I18N do painel vem antes do JSON
        self.assertEqual([k for k in self.dic if k not in I], [], "par do módulo que o painel não vê")
        self.assertEqual({k: (v, I[k]) for k, v in self.dic.items() if I[k] != v}, {}, "inglês diferente no módulo e no painel/JSON")
        pads = {a for a, _ in self.d["I18N_RX"]}
        self.assertEqual([a for a, _ in self.rx if a not in pads], [])

    def test_todo_texto_da_tela_tem_ingles(self):
        chaves = set(self.dic) | set(self.d["I18N"]) | set(i18n_do_painel())
        f = faltando(self.codigo_de_tela(), chaves, self.rx + self.d["I18N_RX"], NAO_E_TELA[self.NOME])
        self.assertEqual(f, [], "texto da tela sem inglês")


@unittest.skipUnless(NO_REPO, "só no repositório")
class ServidorVerde(_Modulo, unittest.TestCase):
    ARQ, NOME, DIC, RX = "physis-servidor-verde.js", "servidor-verde", "window.SERVIDOR_VERDE_I18N = ", "window.SERVIDOR_VERDE_I18N_RX = "

    def test_catalogo_com_ingles(self):
        C = json.loads((S / "physis-servidor-catalogo.json").read_text(encoding="utf-8"))
        I = self.d["I18N"]
        textos = [x["nome"] for x in C["hardware"] + C["software"]] + [x.get("nota") for x in C["hardware"] + C["software"]]
        textos += [x.get("licenca") for x in C["software"]] + [C["modelos"]["nota"]]
        faltam = sorted({t for t in textos if t and PT.search(t) and t not in I})
        self.assertEqual(faltam, [], "nome, nota ou licença do catálogo sem inglês")


@unittest.skipUnless(NO_REPO, "só no repositório")
class Secador(_Modulo, unittest.TestCase):
    ARQ, NOME, DIC, RX = "physis-secador.js", "secador", "window.SECADOR_I18N = ", "window.SECADOR_I18N_RX = "


@unittest.skipUnless(NO_REPO, "só no repositório")
class Frota(_Modulo, unittest.TestCase):
    ARQ, NOME, DIC, RX = "physis-frota.js", "frota", "window.FROTA_I18N = ", "window.FROTA_I18N_RX = "


@unittest.skipUnless(NO_REPO, "só no repositório")
class Validacao(_Modulo, unittest.TestCase):
    ARQ, NOME, DIC, RX = "physis-validacao.js", "validacao", "window.VALIDACAO_I18N = ", "window.VALIDACAO_I18N_RX = "


@unittest.skipUnless(NO_REPO, "só no repositório")
class Parceiros(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = (S / "physis-parceiros.js").read_text(encoding="utf-8")
        cls.dic = objeto(cls.js, "const PAR_I18N = /*I18N*/")
        cls.rx = objeto(cls.js, "const PAR_I18N_RX = /*I18N_RX*/")

    def test_contrato(self):
        for x in ("I18N: PAR_I18N, I18N_RX: PAR_I18N_RX, t", "attributeFilter:[\"lang\"]", "op.idioma"):
            self.assertIn(x, self.js)
        self.assertNotIn("avaliaçãoões", self.js)
        self.assertNotRegex(self.js, r"https?://")

    def test_dicionario_com_ingles(self):
        self.assertEqual([k for k, v in self.dic.items() if not isinstance(v, str) or not v.strip()], [])
        for a, b in self.rx:
            re.compile(a)
            self.assertTrue(b.strip(), a)

    def test_todo_texto_da_tela_tem_ingles(self):
        js = self.js
        i, j = js.index("const PAR_I18N = "), js.index("\n];", js.index("const PAR_I18N_RX = ")) + 3
        f = faltando(js[:i] + js[j:], set(self.dic), self.rx, NAO_E_TELA["parceiros"])
        self.assertEqual(f, [], "texto da tela sem inglês")

    def test_mensagens_do_servidor(self):
        """Os erros e pendências que parceiros.py manda (e a tela mostra) têm inglês no módulo."""
        py = (RAIZ / "physis-hub" / "physis_hub" / "parceiros.py").read_text(encoding="utf-8")
        msgs = set(re.findall(r'"erro": "([^"]+)"', py)) | set(re.findall(r'return None, "([^"]+)"', py))
        msgs |= set(re.findall(r'out\.append\("([^"]+)"\)', py)) | set(re.findall(r'pend\.insert\(0, "([^"]+)"\)', py))
        msgs = {m for m in msgs if not m.endswith(": ")}
        rx = [re.compile(a) for a, _ in self.rx]
        faltam = sorted(m for m in msgs if m not in self.dic and not any(r.search(m) for r in rx))
        self.assertEqual(faltam, [])


@unittest.skipUnless(NO_REPO, "só no repositório")
class Plantas(unittest.TestCase):
    def test_nome_em_ingles(self):
        base = json.loads((S / "physis-plantas.json").read_text(encoding="utf-8"))
        I = json.loads(JSON_I18N.read_text(encoding="utf-8"))["I18N"]
        sem = [p["n"] for p in base["plantas"] if not str(p.get("nome_en") or "").strip()]
        self.assertEqual(sem, [], "planta sem nome_en")
        fora = [p["nome"] for p in base["plantas"] if I.get(p["nome"]) != p["nome_en"]]
        self.assertEqual(fora, [], "o par nome → nome_en precisa estar no JSON do inglês")
        # espécie sem nome comum fica com o nome científico (nunca nome inventado em português)
        for p in base["plantas"]:
            if p.get("especie") and p["nome_en"] == p["nome"] and p["nome"] != p["cientifico"]:
                self.assertRegex(p["nome"], r"^[A-Z][a-z]+( |$)", p["n"])

    def test_vocabulario(self):
        base = json.loads((S / "physis-plantas.json").read_text(encoding="utf-8"))
        I = json.loads(JSON_I18N.read_text(encoding="utf-8"))["I18N"]
        textos = [f["nome"] for f in base["funcoes"]] + [e["nome"] for e in base["estratos"]] + [c["nome"] for c in base["ciclos"]]
        textos += sorted({p["tipo"] for p in base["plantas"]}) + sorted({p["luz"] for p in base["plantas"]})
        self.assertEqual([t for t in textos if t not in I], [])


if __name__ == "__main__":
    unittest.main()
