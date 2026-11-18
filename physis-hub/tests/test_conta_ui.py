"""Conferências estáticas do módulo de conta (sistema/physis-conta.js) e da ligação na Gestão Physis.

- o módulo não carrega nada de fora, não usa eval e não fecha a tag de script;
- a cópia embutida na Gestão e no painel da plataforma (<script id="physis-conta">) é igual ao arquivo;
- todo texto fixo passado por t("...") tem tradução em I18N, e toda chave de I18N é usada;
- as rotas exigidas existem no módulo e no servidor;
- a Gestão chama os robôs e o aprendizado pelas rotas do servidor.
"""
import json
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MODULO = RAIZ / "sistema" / "physis-conta.js"
GESTAO = RAIZ / "sistema" / "gestao-interna-physis.html"
PAINEL = RAIZ / "physis-hub" / "web" / "painel.html"
SERVIDOR = RAIZ / "physis-hub" / "physis_hub" / "servidor.py"


def ler(p: Path) -> str:
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


class TestModuloConta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = ler(MODULO)
        cls.gestao = ler(GESTAO)

    def test_sem_internet_eval_nem_fim_de_script(self):
        self.assertNotIn("</script", self.js.lower())
        self.assertIsNone(re.search(r"https?://", self.js), "endereço de fora no módulo")
        self.assertIsNone(re.search(r"\beval\s*\(|new\s+Function\s*\(", self.js))
        self.assertNotIn("import(", self.js)

    def test_copia_igual_na_gestao(self):
        m = re.search(r'\n<script id="physis-conta">\n(.*?)</script>', self.gestao, re.S)
        self.assertIsNotNone(m, "bloco physis-conta ausente na Gestão")
        self.assertEqual(m.group(1), self.js if self.js.endswith("\n") else self.js + "\n")
        self.assertEqual(self.gestao.count('\n<script id="physis-conta">'), 1)   # o cabeçalho do módulo cita o bloco no meio da linha
        # o módulo vem antes do aplicativo e da casca, e o início logo depois dele
        self.assertLess(self.gestao.index('<script id="physis-conta">'), self.gestao.index('<script id="gp-casca">'))
        self.assertIn('<script id="gp-conta-iniciar">', self.gestao)

    def test_copia_igual_no_painel(self):
        painel = ler(PAINEL)
        m = re.search(r'\n<script id="physis-conta">\n(.*?)</script>', painel, re.S)
        self.assertIsNotNone(m, "bloco physis-conta ausente no painel")
        self.assertEqual(m.group(1), self.js if self.js.endswith("\n") else self.js + "\n")
        self.assertEqual(painel.count('\n<script id="physis-conta">'), 1)
        # o módulo vem antes do aplicativo (o primeiro <script> do <body>)
        app = painel.index('<script>\n"use strict";')
        self.assertLess(painel.index('\n<script id="physis-conta">'), app)
        # uma chamada a iniciar (depois de ler /api/instancia), Minha conta com as telas da direção, e a entrada com 2FA e termos
        fora = painel.replace(m.group(0), "")                   # o cabeçalho do módulo também cita iniciar()
        self.assertEqual(fora.count("PhysisConta.iniciar("), 1)
        for marca in ("C.telaMinhaConta()", "C.telaConvites() + C.telaChaves()", "PhysisConta.ligar(tela)", 'id="btn-conta"',
                      "j.precisa_2fa", "corpo.codigo", "corpo.consentimento = { versao: ui.inst.termos_versao, aceito: true }",
                      'href="/conta/esqueci"', 'autocomplete="one-time-code"'):
            self.assertIn(marca, painel, marca)

    def _i18n(self):
        bloco = self.js.split("/*I18N-INICIO*/", 1)[1].split("/*I18N-FIM*/", 1)[0]
        pares = re.findall(r'^\s*"((?:[^"\\]|\\.)*)":\s*"((?:[^"\\]|\\.)*)",?\s*$', bloco, re.M)
        return dict(pares)

    def test_i18n_cobre_os_textos(self):
        d = self._i18n()
        self.assertGreater(len(d), 100)
        usados = set(re.findall(r'\bt\("((?:[^"\\]|\\.)*)"\)', self.js))
        # textos em listas que passam por t(x)
        listas = re.findall(r'\[("a conta e as sessões.*?")\]\.map', self.js, re.S)
        for l in listas:
            usados |= set(re.findall(r'"((?:[^"\\]|\\.)*)"', l))
        faltam = sorted(u for u in usados if u not in d)
        self.assertEqual(faltam, [], "sem tradução: %s" % faltam)
        for k, v in d.items():
            self.assertTrue(v.strip(), "tradução vazia: " + k)
            if k not in ("E-mail",):
                self.assertNotEqual(k, v, "tradução igual ao português: " + k)
        # situações dos convites (t(c.estado)) também traduzidas
        for e in ("pendente", "aceito", "vencido", "revogado"):
            self.assertIn(e, d)
        sobras = sorted(k for k in d if k not in usados and k not in ("pendente", "aceito", "vencido", "revogado"))
        self.assertEqual(sobras, [], "chaves de I18N sem uso: %s" % sobras)

    def test_contrato_publico(self):
        for nome in ("iniciar", "telaMinhaConta", "telaConvites", "telaChaves", "ligar", "I18N", "t:"):
            self.assertIn(nome, self.js.split("g.PhysisConta = {", 1)[1])
        self.assertIn('"X-Physis-CSRF"', self.js)
        for chave in ("reautenticar", "confirmar_email", "consentimento", "j.csrf === true"):
            self.assertIn(chave, self.js)
        self.assertIn('role=\'dialog\' aria-modal=\'true\'', self.js)
        self.assertIn('"Escape"', self.js)

    def test_rotas_no_modulo_e_no_servidor(self):
        srv = ler(SERVIDOR)
        rotas = ["/api/conta/senha", "/api/conta/2fa/iniciar", "/api/conta/2fa/ativar", "/api/conta/2fa/desativar",
                 "/api/conta/meus-dados", "/api/conta/apagar", "/api/conta/consentimento", "/api/conta/reautenticar",
                 "/api/conta/confirmar/reenviar", "/api/convites", "/api/instancia", "/api/dispositivos/chaves"]
        for r in rotas:
            self.assertIn('"' + r, self.js, "rota ausente no módulo: " + r)
            self.assertIn('"' + r, srv, "rota ausente no servidor: " + r)
        self.assertIn('"/revogar"', self.js)

    def test_cores_da_paleta(self):
        paleta = set(h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}", ler(RAIZ / "physis-hub" / "docs" / "PALETA.md")))
        for h in set(re.findall(r"#[0-9A-Fa-f]{6}\b", self.js)):
            self.assertIn(h.upper(), paleta, "cor fora da paleta: " + h)
        self.assertIn("html[data-tema=escuro] .pc{", self.js)


class TestGestaoRobos(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.g = ler(GESTAO)

    def test_rotas_dos_robos_e_aprendizado(self):
        for r in ("/api/robos/suporte", "/api/robos/precos", "/api/robos/editais", "/api/robos/projetos", "/api/robos/marketing",
                  "/api/aprendizado/estado", "/api/aprendizado/consumo", "/api/aprendizado/anomalias", "/api/aprendizado/treinar",
                  "/api/alertas/assinaturas", "/api/alertas/historico"):
            self.assertIn('"' + r + '"', self.g, r)

    def test_partes_ligadas(self):
        for marca in ('<script id="gp-robos">', "data-pr-precos", "gx-ed-nota", "data-ed-esbocar", "gx-mk-robo",
                      "PC.telaConvites()", "PC.telaMinhaConta()", "PC.telaChaves()", '"suporte", "Suporte Physis"'):
            self.assertIn(marca, self.g, marca)

    def test_bloco_robos_sem_internet_e_com_ingles(self):
        b = self.g.split('<script id="gp-robos">', 1)[1].split("</script>", 1)[0]
        self.assertIsNone(re.search(r"https?://", b))
        self.assertNotIn("eval(", b)
        # todo texto visível do bloco passa por L("pt", "en")
        self.assertGreater(b.count('L("'), 60)

    def test_cores_novas_da_paleta(self):
        paleta = set(h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}", ler(RAIZ / "physis-hub" / "docs" / "PALETA.md")))
        estilo = self.g.split('<style id="gr-estilo">', 1)[1].split("</style>", 1)[0]
        for h in set(re.findall(r"#[0-9A-Fa-f]{6}\b", estilo)):
            self.assertIn(h.upper(), paleta, "cor fora da paleta: " + h)
        self.assertIn('[data-tema="escuro"]', estilo)

    def test_um_h1_por_parte_nova(self):
        b = self.g.split('<script id="gp-robos">', 1)[1].split("</script>", 1)[0]
        self.assertEqual(b.count("<h1"), 5)       # Suporte, Clientes, Chamados, Parceiros e Fornecedores (uma tela cada); Direção usa h2


class TestGestaoNovas(unittest.TestCase):
    """15/11/2026: Clientes, Chamados, Parceiros, ODF, nome "Eric Oliveira" e semente da Fase 2."""
    @classmethod
    def setUpClass(cls):
        cls.g = ler(GESTAO)

    def test_copias_iguais_odf_e_parceiros(self):
        for bloco, arq in (("physis-odf", "physis-odf.js"), ("physis-parceiros", "physis-parceiros.js")):
            js = ler(RAIZ / "sistema" / arq)
            self.assertNotIn("</script", js.lower())
            m = re.search(r'\n<script id="' + bloco + r'">\n(.*?)</script>', self.g, re.S)
            self.assertIsNotNone(m, bloco)
            self.assertEqual(m.group(1), js if js.endswith("\n") else js + "\n", bloco)
        self.assertEqual(self.g.count("window.PhysisODF.acoplar("), 2)   # barra do painel administrativo e barra geral

    def test_rotas_clientes_chamados(self):
        srv = ler(SERVIDOR)
        for r in ("/api/central/clientes", "/api/suporte/chamados"):
            self.assertIn('"' + r, self.g, r)
            self.assertIn('"' + r, srv, r)
        for marca in ('["clientes", "Clientes", null]', '["chamados", "Chamados", null]', '["parceiros", "Parceiros", null]', "PARCEIROS.montarCuradoria("):
            self.assertIn(marca, self.g, marca)

    def test_nome_eric_oliveira(self):
        self.assertNotIn("Erick Oliveira", self.g)
        self.assertIn('{id:"erickoliveira",nome:"Eric Oliveira"', self.g)
        self.assertIn("Erick Lopes", self.g)

    def test_semente_fase2(self):
        pk = json.loads(ler(RAIZ / "sistema" / "gestao-fase2-tarefas.json"))
        m = re.search(r"\$y=(\[\{\"id\".*?\}\]),Fn=\[", self.g, re.S)
        self.assertIsNotNone(m, "semente de tarefas não achada")
        tarefas = json.loads(m.group(1))
        self.assertEqual(len(tarefas), len(pk["tabelas"]["tarefa"]))
        self.assertGreater(len(tarefas), 0)          # o total vem do arquivo da Fase 2 (muda quando ele é refeito)
        self.assertEqual({t["id"] for t in tarefas}, {t["tarefa_id"] for t in pk["tabelas"]["tarefa"]})
        projetos = {t["projeto"] for t in tarefas}
        self.assertEqual(len(projetos), 10)
        self.assertTrue(all(p.startswith("Fase 2 · ") for p in projetos))
        self.assertTrue(all(t["pessoa"] != "adefinir" for t in tarefas))
        self.assertNotIn('{id:"adefinir",nome:"A definir"', self.g)
        self.assertIn("window.PHYSIS_MELHORIAS=[];", self.g)
        self.assertNotIn("PHYSIS_MELHORIAS||[]", self.g)


if __name__ == "__main__":
    unittest.main()
