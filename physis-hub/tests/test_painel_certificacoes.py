"""Plataforma (painel.html): saída da Tela do cliente, Conformidade legal e IPMVP em Certificações, programas sem o hub,
instalação de pesquisa com todas as telas e "Experimente agora" na loja (15/11/2026)."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PAINEL = RAIZ / "physis-hub" / "web" / "painel.html"


def ler(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class TelaDoClienteSaiu(unittest.TestCase):
    def test_programa_e_aba_removidos(self):
        p = ler(PAINEL)
        linha = next(l for l in p.split("\n") if l.startswith("const PROGRAMAS = {"))
        self.assertNotIn("painel:", linha)
        for velho in ("quadroTela", "SECAO_TELA", "telaPainel", "ocultasNoPainel", 'painel:"Tela do cliente"', 'data-prog="painel"'):
            self.assertNotIn(velho, p, velho)

    def test_mesmas_contas(self):
        p = ler(PAINEL)
        self.assertIn('if (s === "conforme") ok++; else if (s === "parcial") ok += 0.5;', p)        # calcConformidade
        self.assertIn('veredito: razao >= 3 ? "confortavel" : (razao >= 1 ? "apertado" : "nao_comprova")', p)   # comprovavel
        self.assertIn('dias < 0 ? "vencida" : (dias <= 60 ? "vence_em_breve" : "valida")', p)       # statusCal
        # equação geral do IPMVP: uma conta só, VALIDACAO.ipmvp (sistema/physis-validacao.js), também usada pela aba Validação
        self.assertIn("const ip = VALIDACAO.ipmvp(b ? b.v : null, p ? p.v : null, aj), econ = ip.econ;", p)
        self.assertIn("const econ = base - rel + a, baseAj = base + a;", p)

    def test_migracao_do_rascunho(self):
        p = ler(PAINEL)
        self.assertIn('CMV_CHAVE = "physis-conformidade-mv", CMV_RASCUNHO = "physis-cliente:rascunho:"', p)
        for campo in ("d.requisito", "medida_eficiencia", "d.instrumento", "d.verificacao_campo", "c.migrado ="):
            self.assertIn(campo, p)

    def test_subabas_em_certificacoes(self):
        p = ler(PAINEL)
        self.assertIn('data-ce-aba="conformidade"', p)
        self.assertIn('data-ce-aba="ipmvp"', p)


class SemHubEPesquisa(unittest.TestCase):
    def test_planejador_sem_hub_abre_o_arquivo_da_pasta(self):
        p = ler(PAINEL)
        self.assertIn('const ARQ_LOCAL = { planejador:"planejador.html" };', p)
        self.assertIn('fetch(a, { method:"HEAD", cache:"no-store" })', p)
        self.assertIn("if (!doServidor && !PROGRAMAS[id]) return", p)

    def test_planejador_embutido_como_o_sustainkit(self):
        """Desde 15/11/2026 o Planejador vai embutido (base64) em PROGRAMAS, como o SustainKit e o SCADA: abre sem o computador central."""
        import base64
        p = ler(PAINEL)
        linha = next(l for l in p.split("\n") if l.startswith("const PROGRAMAS = {"))
        m = re.search(r'planejador:"([A-Za-z0-9+/=]+)"', linha)
        self.assertIsNotNone(m)
        html = base64.b64decode(m.group(1)).decode("utf-8")
        self.assertIn("Planejador Physis", html)
        self.assertIn('<script id="physis-calc-comum">', html)

    def test_pesquisa_mostra_todas_as_abas(self):
        p = ler(PAINEL)
        self.assertIn("pesquisa: emPesquisa(), resumo: temHardware(), registro: emPesquisa(), teste: emPesquisa() }", p)
        for rota in ("/gestao/", "/loja/", "/consultoria/", "/municipio", "/documento", "/app/baixar"):
            self.assertIn(f'"{rota}"', p)

    def test_casa_physis_com_tudo(self):
        f = next(x for x in json.loads(ler(RAIZ / "clientes" / "clientes.json"))["clientes"] if x["org"] == "casa-physis")
        self.assertTrue(f["pesquisa"] and f["gestao_interna"])
        self.assertNotIn("painel", f["modulos"])


class Experimente(unittest.TestCase):
    def test_tres_cartoes_com_demo_e_compra(self):
        p = ler(PAINEL)
        for demo, arq in (("sustainkit", "physis-demo-sustainkit.html"), ("scada", "physis-demo-scada.html"), ("monitoramento", "physis-demo-monitoramento.html")):
            self.assertIn(f'demo:"{demo}", arq:"{arq}"', p)
        self.assertIn('"/demo/" + x.demo + "/"', p)
        self.assertIn("${blocoExperimente()}", p)
        self.assertIn('data-exp-comprar="${x.id}"', p)

    def test_animacao_respeita_preferencias(self):
        p = ler(PAINEL)
        self.assertIn("@media (prefers-reduced-motion:reduce){.exp-svg *{animation:none!important}}", p)
        self.assertIn("html.a11y-calma .exp-svg *", p)


if __name__ == "__main__":
    unittest.main()
