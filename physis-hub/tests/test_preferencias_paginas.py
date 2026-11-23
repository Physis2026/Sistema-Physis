"""Preferências nas telas com tradução própria: plataforma (painel.html), Gestão Physis e SCADA.

Pedido (15/11/2026): "absolutamente todas as páginas devem ter opções de acessibilidade e modo de conforto, opção inglês
e tela clara e escura" e um só modelo em todas as janelas. Desde então há UM módulo (sistema/physis-preferencias.js),
copiado igual em cada tela (bloco <script id="physis-preferencias">) por ferramentas/sincronizar.py, com quatro controles:
Idioma · Tema (Claro, Escuro, Automático) · Modo de conforto ▾ · Acessibilidade (PcD) ▾.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PAINEL = RAIZ / "physis-hub" / "web" / "painel.html"
SISTEMA = {
    "gestao": RAIZ / "sistema" / "gestao-interna-physis.html",
    "scada": RAIZ / "sistema" / "physis-scada-demo.html",
}
TODAS = dict(SISTEMA, painel=PAINEL)


def ler(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def bloco(texto: str, ident: str) -> str:
    m = re.search(r'<script id="%s">\n(.*?)\n</script>' % re.escape(ident), texto, re.S)
    return m.group(1) if m else ""


def estilo_tema(nome: str, texto: str) -> str:
    if nome == "painel":
        i = texto.index("/* Tema escuro (Tema: Claro / Escuro / Automático")
        return texto[i:texto.index("</style>", i)]
    m = re.search(r'<style id="pxp-tema">(.*?)</style>', texto, re.S)
    return m.group(1) if m else ""


def paleta() -> set[str]:
    doc = ler(RAIZ / "physis-hub" / "docs" / "PALETA.md")
    return {h.upper() for h in re.findall(r"`#([0-9A-Fa-f]{6})`", doc)}


def luminancia(h: str) -> float:
    def canal(c: int) -> float:
        v = c / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def contraste(a: str, b: str) -> float:
    la, lb = luminancia(a.lstrip("#")), luminancia(b.lstrip("#"))
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def variaveis(css: str) -> dict[str, str]:
    return {k: v.upper() for k, v in re.findall(r"(--[\w-]+):(#[0-9A-Fa-f]{6})\b", css)}


MODULO = RAIZ / "sistema" / "physis-preferencias.js"


class Barra(unittest.TestCase):
    """Desde 15/11/2026 há UM módulo de preferências (sistema/physis-preferencias.js). A plataforma, a Gestão e o SCADA
    entram pela porta PxPref (traduzem a si mesmos); consultoria, SustainKit e Planejador por PhysisPreferencias."""

    def test_mesma_barra_em_todas(self):
        original = ler(MODULO).replace("\r\n", "\n")
        for n, p in TODAS.items():
            t = ler(p)
            m = re.search(r'<script id="physis-preferencias">\n(.*?)</script>', t, re.S)
            self.assertIsNotNone(m, n)
            self.assertEqual(m.group(1), original, f"{n}: cópia diferente de sistema/physis-preferencias.js (rode ferramentas/sincronizar.py)")
            self.assertNotIn('<script id="px-preferencias">', t, f"{n}: a segunda implementação antiga voltou")

    def test_quatro_controles_e_rotulos(self):
        mod = ler(MODULO)
        for rot in ['idioma: "Idioma"', 'tema: "Tema"', 'claro: "Claro"', 'escuro: "Escuro (verde)"', 'auto: "Automático"',
                    'conforto: "Modo de conforto"', 'a11y: "Acessibilidade (PcD)"', 'tema: "Theme"', 'conforto: "Comfort mode"']:
            self.assertIn(rot, mod)
        for ident in ["pp-idioma", "pp-tema", "pp-conforto", "pp-a11y", "pp-painel-conforto", "pp-painel-a11y", "pxp-barra"]:
            self.assertIn('"' + ident + '"', mod)
        self.assertIn('"aria-expanded": "false"', mod)
        self.assertIn("global.PxPref = PX", mod)
        self.assertIn("global.PhysisPreferencias = API", mod)

    def test_chaves_compartilhadas(self):
        mod = ler(MODULO)
        self.assertIn('gravar("physis-pref-tema", e.tema)', mod)
        self.assertIn('P.op.chave = P.op.chave || "physis-pref"', mod)
        for cedo in [ler(p) for p in TODAS.values()]:
            self.assertIn('<script id="pxp-cedo">', cedo)
            self.assertIn('localStorage.getItem("physis-pref-tema")', cedo)
            self.assertIn("prefers-color-scheme: dark", cedo)

    def test_modo_de_conforto(self):
        mod = ler(MODULO)
        for k in ["espaco", "calma", "foco", "dislexia", "regua", "simples", "lembrar", "contraste"]:
            self.assertIn('caixa("%s"' % k, mod)
        self.assertIn('name: "pp-texto"', mod)   # texto: normal, maior, muito maior
        # 20/11/2026: "fundo verde" e tema escuro são uma opção só; o tema fica só dentro do modo de conforto
        self.assertNotIn('caixa("verde"', mod)
        self.assertIn('name: "pp-tema"', mod)
        self.assertIn("u.temaRot.hidden = true;", mod)
        self.assertIn('patch = { conforto: t.checked, tema: t.checked ? "escuro" : "auto", calma: t.checked, espaco: t.checked }', mod)
        self.assertIn('if (e.verde) { e.tema = "escuro"; e.verde = false; }', mod)
        # os botões de tema não têm data-pp: o tema é tratado antes do "if (!k) return;" (senão o clique não faz nada)
        self.assertLess(mod.index('if (t.name === "pp-tema") return mudar('), mod.index("if (!k) return;"))

    def test_acessibilidade_pcd(self):
        mod = ler(MODULO)
        for x in ["Cegueira e baixa visão", "Surdez", "Fala", "Mobilidade", "NVDA, JAWS, VoiceOver, TalkBack", "speechSynthesis",
                  "Alt+1", "Alt+2", "Alt+3", "Alt+0", "Libras (VLibras)", "Comunicação alternativa (CAA)",
                  "Preciso de ajuda", "Não entendi", "Quero falar com uma pessoa", "Pode repetir de outro jeito?",
                  "webkitSpeechRecognition", "LGPD", "Relatar barreira", "Copiar relato", "Declaração de acessibilidade",
                  "Lei 13.146/2015", "eMAG", "WCAG 2.2", "NBR 17225"]:
            self.assertIn(x, mod)
        self.assertIn("libras: false, voz: false", mod)
        self.assertNotRegex(mod, r"https?://")

    def test_em_quadro_segue_a_plataforma(self):
        mod = ler(MODULO)
        self.assertIn('hasAttribute("data-em-quadro")', mod)        # sem segunda barra dentro da plataforma
        self.assertIn('global.addEventListener("storage"', mod)      # segue a escolha feita na plataforma
        self.assertIn("esconderEmQuadro: op.esconderEmQuadro !== false", mod)

    def test_controles_antigos_saem(self):
        p = ler(PAINEL)
        for antigo in ['id="px-fundo"', 'id="btn-pass"', 'id="painel-pass"', 'id="px-idioma"', 'el("px-idioma").addEventListener']:
            self.assertNotIn(antigo, p)
        self.assertIn('<div id="pxp-lugar"></div>', p)
        for n, arq in SISTEMA.items():
            t = ler(arq)
            self.assertNotIn('id="px-conforto" aria-pressed', t, n)
            self.assertIn('<div id="pxp-lugar"></div>', t, n)
            self.assertIn("PxPref.iniciar(", bloco(t, "pxp-iniciar"), n)


class TemaEscuro(unittest.TestCase):
    def test_cada_tela_tem_o_escuro(self):
        for n, arq in TODAS.items():
            css = estilo_tema(n, ler(arq))
            self.assertIn('html[data-tema="escuro"]{', css, n)
            self.assertIn("@media screen{", css, n)   # na impressão vale o claro

    def test_so_cores_da_paleta(self):
        ok = paleta()
        for n, arq in TODAS.items():
            css = estilo_tema(n, ler(arq))
            css = re.sub(r"base64,[A-Za-z0-9+/=]+", "", css)
            css = re.sub(r"\[[^\]]*\]", "", css)   # cores dentro de seletores (o que é trocado) não contam
            css = re.sub(r"var\(--(?:tx|bg|bd)-[0-9A-F]+,#[0-9A-Fa-f]+\)", "", css)
            usadas = {h.upper()[:6] for h in re.findall(r"#([0-9A-Fa-f]{6,8})\b", css)}
            fora = sorted(usadas - ok)
            self.assertEqual(fora, [], f"{n}: cores fora da paleta {fora}")

    def test_contraste_aa_no_escuro(self):
        p = estilo_tema("painel", ler(PAINEL))
        v = variaveis(p[p.index('html[data-tema="escuro"]{'):])
        pares = [("--tinta", "--fundo"), ("--tinta", "--sup"), ("--tinta2", "--sup"), ("--tinta2", "--det-f"), ("--acao", "--sup"),
                 ("--marca", "--sup"), ("--ok-t", "--ok-f"), ("--at-t", "--at-f"), ("--al-t", "--al-f"), ("--in-t", "--in-f"),
                 ("--det-t", "--det-f"), ("--sup", "--acao"), ("--al-t", "--sup"), ("--tinta", "--tinte")]
        for a, b in pares:
            self.assertGreaterEqual(contraste(v[a], v[b]), 4.5, f"painel {a} sobre {b}")
        comum = {"--px-tinta": "#EEF2EA", "--px-fraca": "#D9D3C2", "--px-acao": "#B9CDB3", "--px-alerta": "#FF8A80", "--px-atencao": "#C9A227", "--px-info": "#8FB183"}  # guia de 19/11/2026: sem azul (era #7FA9C4)
        for arq in SISTEMA.values():
            vs = variaveis(estilo_tema("x", ler(arq)))
            for k, cor in comum.items():
                self.assertEqual(vs.get(k), cor)
                self.assertGreaterEqual(contraste(cor, vs["--px-sup"]), 4.5, k)
                self.assertGreaterEqual(contraste(cor, vs["--px-fundo"]), 4.5, k)
            # cores fixas da tela que viram texto no escuro
            for k, cor in vs.items():
                if k.startswith("--tx-") and cor not in ("#14180F",):
                    self.assertGreaterEqual(contraste(cor, "#1C2B21"), 4.5, f"{arq.name} {k}")

    def test_programas_embutidos_seguem_o_tema(self):
        p = ler(PAINEL)
        self.assertIn('r.setAttribute("data-tema", h.getAttribute("data-tema") || "claro")', p)
        # os programas cuidam do próprio fundo no tema escuro; a plataforma só avisa que eles estão em quadro (15/11/2026)
        self.assertIn('<html$1 data-em-quadro="">', p)


class Ingles(unittest.TestCase):
    def objeto_i18n(self):
        p = ler(PAINEL)
        i = p.index("const I18N = ") + len("const I18N = ")
        fim = p.index("};\n", i) + 1
        pares = json.loads(p[i:fim], object_pairs_hook=lambda kv: kv)
        return pares

    def test_dicionario_sem_par_repetido_com_valor_diferente(self):
        vistos, conflitos = {}, []
        for k, v in self.objeto_i18n():
            if k in vistos and vistos[k] != v:
                conflitos.append(k)
            vistos[k] = v
        self.assertEqual(conflitos, [])
        self.assertGreater(len(vistos), 1600)

    def test_partes_novas_traduzidas(self):
        d = dict(self.objeto_i18n())
        for pt in ["Visão geral e controle", "Quadro elétrico de AVAC (QF-AVAC)", "Caixinha de remédios e pulseira de alerta. Funcionam juntas ou separadas.",
                   "Suporte Physis", "Falar com a Physis", "Começar o curso", "Marcar como concluído", "Termos de uso", "Política de privacidade (LGPD)",
                   "Os textos jurídicos estão em português.", "Fechar"]:
            self.assertIn(pt, d)
        self.assertIn("No topo da tela ficam quatro controles: idioma (Português ou English), tema (claro, escuro ou automático), modo de conforto e acessibilidade (PcD).", ler(PAINEL))

    def test_padroes_validos(self):
        p = ler(PAINEL)
        i = p.index("const I18N_RX = ") + len("const I18N_RX = ")
        fim = p.index(".map(([a, b]) => [new RegExp(a), b]);", i)
        lista = json.loads(p[i:fim])
        for a, b in lista:
            re.compile(a.replace("(?<", "(?P<") if "(?<" in a and "(?<=" not in a and "(?<!" not in a else a)
            self.assertIsInstance(b, str)

    def test_gestao_segue_o_idioma_escolhido(self):
        g = ler(SISTEMA["gestao"])
        self.assertNotIn('var EN = /^en/i.test(navigator.language || "pt");', g)
        self.assertEqual(g.count('var EN = (function () { try { var p = JSON.parse(localStorage.getItem("physis-pref")'), 2)


if __name__ == "__main__":
    unittest.main()
