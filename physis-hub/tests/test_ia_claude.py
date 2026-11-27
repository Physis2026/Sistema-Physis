"""IA Claude para os robôs (sem internet: um servidor HTTP falso no próprio computador faz o papel da Anthropic).

Protege:
1. Sem chave, o Claude fica desligado e nada sai do hub; a chave nunca aparece no repr, no log nem no contador.
2. Resposta normal: cabeçalhos certos (x-api-key, anthropic-version), modelo padrão, sem temperature, custo contado.
3. Erro da API, recusa ou rede fora: devolve None e o robô responde por regras.
4. Teto do mês: acima dele nada é enviado e o robô responde por regras; mês novo zera o contador.
5. Dados pessoais (e-mail, CPF, CNPJ, telefone) saem antes do envio, e o contador anota quantos saíram.
6. Ordem: Claude → IA local → regras; toda resposta de IA vem marcada e com revisão humana.
"""
import json
import os
import tempfile
import threading
import unittest
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

from physis_hub import ia_claude, robos

CHAVE = "sk-ant-teste-NAO-E-REAL-123"
BASE = [{"texto": "Para baixar qualquer tela, use o botão Baixar esta tela: ele gera Word, PDF ou Excel com a identidade da Physis.",
         "fonte": "docs/APPS.md", "secao": "Exportar"}]
OK = {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5", "stop_reason": "end_turn",
      "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": "Use o botão Baixar esta tela [1]."}],
      "usage": {"input_tokens": 1000, "output_tokens": 500}}


class Falso(BaseHTTPRequestHandler):
    respostas: list = []          # (status, corpo) por chamada
    recebidos: list = []

    def do_POST(self):
        corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8"))
        Falso.recebidos.append({"cabecalhos": dict(self.headers), "corpo": corpo, "caminho": self.path})
        status, saida = Falso.respostas.pop(0) if Falso.respostas else (200, OK)
        dados = json.dumps(saida).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def log_message(self, *a):
        pass


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Falso)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}/v1/messages"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        Falso.respostas, Falso.recebidos = [], []
        self.tmp = tempfile.TemporaryDirectory()
        self.consumo = Path(self.tmp.name) / "consumo.json"
        self.agora = datetime(2026, 11, 15, 10, 0).timestamp()

    def tearDown(self):
        self.tmp.cleanup()

    def claude(self, **kw):
        kw.setdefault("chave", CHAVE)
        kw.setdefault("url", self.url)
        kw.setdefault("consumo", self.consumo)
        kw.setdefault("teto_usd", 25)
        kw.setdefault("tempo", 5)
        return ia_claude.IAClaude(relogio=lambda: self.agora, **kw)


class TestIAClaude(Base):
    def test_sem_chave_desligado(self):
        sem = {"PHYSIS_CLAUDE_CHAVE": "", "ANTHROPIC_API_KEY": "", "PHYSIS_CLAUDE_CHAVE_ARQUIVO": ""}
        with mock.patch.dict(os.environ, sem):
            ia = ia_claude.IAClaude(url=self.url, consumo=self.consumo)
        self.assertFalse(ia.ativa)
        self.assertIsNone(ia.gerar("s", "p"))
        self.assertEqual(Falso.recebidos, [])
        self.assertFalse(ia.estado()["configurada"])

    def test_chave_de_arquivo_e_endereco_externo_recusado(self):
        arq = Path(self.tmp.name) / "chave.txt"
        arq.write_text(CHAVE + "\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"PHYSIS_CLAUDE_CHAVE_ARQUIVO": str(arq)}):
            self.assertEqual(ia_claude.ler_chave(), CHAVE)
        ruim = self.claude(url="https://outro-servidor.example.com/v1/messages")
        self.assertFalse(ruim.ativa)
        self.assertIn("api.anthropic.com", ruim.erro)

    def test_resposta_normal(self):
        ia = self.claude()
        with self.assertLogs("physis.ia_claude", "INFO") as logs:
            self.assertEqual(ia.gerar("sistema", "como exportar?", robo="suporte"), "Use o botão Baixar esta tela [1].")
        req = Falso.recebidos[0]
        cab = {k.lower(): v for k, v in req["cabecalhos"].items()}
        self.assertEqual(cab["x-api-key"], CHAVE)
        self.assertEqual(cab["anthropic-version"], ia_claude.VERSAO_API)
        self.assertEqual(cab["anthropic-beta"], ia_claude.BETA_RESERVA)
        corpo = req["corpo"]
        self.assertEqual(corpo["model"], "claude-opus-5-5")
        self.assertEqual(corpo["fallbacks"], "default")
        self.assertEqual(corpo["output_config"], {"effort": "low"})
        self.assertNotIn("temperature", corpo)
        # custo: 1000 × 4 + 500 × 20 por milhão = 0,014 US$
        est = ia.estado()
        self.assertAlmostEqual(est["gasto_usd"], 0.014, places=6)
        self.assertEqual(est["chamadas"], 1)
        self.assertEqual(ia.ultimo["modelo"], "claude-opus-5-5")
        # a chave e o texto não aparecem no log, no repr nem no contador
        guardado = self.consumo.read_text(encoding="utf-8")
        for onde in ("\n".join(logs.output), repr(ia), guardado, json.dumps(est)):
            self.assertNotIn(CHAVE, onde)
        self.assertNotIn("como exportar", guardado)

    def test_erro_da_api_e_recusa(self):
        Falso.respostas = [(529, {"type": "error", "error": {"type": "overloaded_error", "message": "x"}}),
                           (200, dict(OK, stop_reason="refusal", content=[]))]
        ia = self.claude()
        self.assertIsNone(ia.gerar("s", "p"))
        self.assertIn("529", ia.erro)
        self.assertIn("overloaded_error", ia.erro)
        self.assertIsNone(ia.gerar("s", "p"))
        self.assertIn("recusou", ia.erro)
        self.assertEqual(ia.estado()["falhas"], 2)

    def test_rede_fora(self):
        ia = self.claude(url="http://127.0.0.1:9/v1/messages", tempo=1)
        self.assertIsNone(ia.gerar("s", "p"))
        self.assertIn("rede", ia.erro)

    def test_teto_atingido_e_mes_novo(self):
        self.consumo.write_text(json.dumps({"mes": "2026-11", "gasto_usd": 24.95}), encoding="utf-8")
        ia = self.claude(teto_usd=25)
        self.assertIsNone(ia.gerar("s", "p"))
        self.assertIn("teto", ia.erro)
        self.assertEqual(Falso.recebidos, [])
        self.assertEqual(ia.estado()["bloqueadas_teto"], 1)
        self.agora = datetime(2026, 12, 1, 8, 0).timestamp()        # mês novo: contador zera
        self.assertIsNotNone(ia.gerar("s", "p"))
        self.assertEqual(ia.estado()["mes"], "2026-12")
        self.assertFalse(self.claude(teto_usd=0).ativa)               # teto 0 = Claude desligado

    def test_dados_pessoais_saem_e_ficam_anotados(self):
        ia = self.claude()
        ia.gerar("sistema", "Sou Ana Lima, ana.lima@exemplo.com.br, CPF 123.456.789-09, CNPJ 12.345.678/0001-90, "
                            "tel (24) 99876-5432. Quero exportar.", robo="suporte", nomes=["Ana Lima"])
        enviado = json.dumps(Falso.recebidos[0]["corpo"], ensure_ascii=False)
        for s in ("ana.lima@", "123.456.789", "12.345.678/0001", "99876", "Ana Lima"):
            self.assertNotIn(s, enviado)
        for marca in ("[e-mail]", "[CPF]", "[CNPJ]", "[telefone]", "[pessoa]"):
            self.assertIn(marca, enviado)
        nota = json.loads(self.consumo.read_text(encoding="utf-8"))["envios"][-1]
        self.assertEqual(nota["dados_pessoais_removidos"], {"e-mail": 1, "CPF": 1, "CNPJ": 1, "telefone": 1, "pessoa": 1})
        self.assertNotIn("exportar", json.dumps(nota))


class TestTetosEAvisos(Base):
    def test_teto_por_robo_so_aquele_robo_volta_as_regras(self):
        ia = self.claude(max_tokens=100, tetos_robo={"suporte": 0.01, "editais": 5})
        self.assertIsNotNone(ia.gerar("s", "p", robo="suporte"))          # 0,014 gasto pelo suporte
        self.assertIsNone(ia.gerar("s", "p", robo="suporte"))              # passou do teto do suporte
        self.assertIn("teto do robô suporte", ia.erro)
        self.assertIsNotNone(ia.gerar("s", "p", robo="editais"))           # os outros seguem
        est = ia.estado()
        pr = {x["robo"]: x for x in est["por_robo"]}
        self.assertEqual((pr["suporte"]["chamadas"], pr["suporte"]["bloqueadas_teto"], pr["suporte"]["no_teto"]), (1, 1, True))
        self.assertEqual(pr["editais"]["chamadas"], 1)
        self.assertFalse(pr["editais"]["no_teto"])
        self.assertEqual(len(Falso.recebidos), 2)

    def test_aviso_por_email_80_e_100_uma_vez_por_mes(self):
        from physis_hub import correio
        from physis_hub.hub import Hub
        h = Hub(":memory:", relogio=lambda: self.agora)
        enviados = []
        with mock.patch.dict(os.environ, {"PHYSIS_SMTP_HOST": "smtp.teste"}), \
                mock.patch.object(correio, "enviar", lambda para, assunto, corpo: (enviados.append((para, assunto, corpo)), (True, ""))[1]):
            ia = self.claude(max_tokens=100, teto_usd=0.02, tetos_robo={"suporte": 1},
                             avisar=ia_claude.aviso_por_email(h, "direcao@physis.example"))
            ia.gerar("s", "p", robo="suporte")            # 0,014 = 70%: sem aviso
            self.assertEqual(enviados, [])
            ia.gerar("s", "p", robo="suporte")            # 0,028: passa de 80% e de 100%
            self.assertEqual([a for _, a, _ in enviados], ["Physis · IA Claude: 80% do teto do mês (2026-11)",
                                                           "Physis · IA Claude: 100% do teto do mês (2026-11)"])
            self.assertIsNone(ia.gerar("s", "p", robo="suporte"))     # teto total: robô por regras
            self.assertEqual(len(enviados), 2)                         # uma vez por mês por limite
        self.assertEqual(enviados[0][0], "direcao@physis.example")
        self.assertNotIn(CHAVE, json.dumps(enviados))
        self.assertEqual({e["estado"] for e in h.emails()}, {"enviado"})
        self.assertEqual(ia.estado()["avisos_enviados"], ["80", "100"])

    def test_historico_por_mes(self):
        ia = self.claude()
        ia.gerar("s", "p", robo="suporte")
        self.agora = datetime(2026, 12, 2, 9, 0).timestamp()
        ia.gerar("s", "p", robo="precos")
        est = ia.estado()
        self.assertEqual(est["mes"], "2026-12")
        self.assertEqual(est["historico"][0]["mes"], "2026-11")
        self.assertAlmostEqual(est["historico"][0]["gasto_usd"], 0.014, places=6)
        self.assertEqual(list(est["historico"][0]["por_robo"]), ["suporte"])
        self.assertEqual(est["avisos_enviados"], [])


class TestOrdemNosRobos(Base):
    def test_claude_primeiro_sem_aviso_no_texto(self):
        cadeia = robos.CadeiaIA([self.claude(), robos.IALocal("")])
        r = robos.Suporte({"base_suporte": BASE}, cadeia).responder({"pergunta": "exportar tela para PDF", "_publico": "equipe"})
        self.assertTrue(r["ia"]["usada"])
        self.assertEqual((r["ia"]["tipo"], r["ia"]["modelo"]), ("claude", "claude-opus-5-5"))
        self.assertTrue(r["ia"]["quando"])
        self.assertTrue(r["revisao_humana"])
        self.assertEqual(r["resposta"], "Use o botão Baixar esta tela [1].")
        self.assertNotIn("gerado_por_ia", r)

    def test_claude_falha_vai_para_local_depois_regras(self):
        Falso.respostas = [(500, {}), (500, {})]
        local = robos.IALocal("http://localhost:8000", enviar=lambda u, c, t: {"choices": [{"message": {"content": "da IA local"}}]})
        r = robos.Suporte({"base_suporte": BASE}, robos.CadeiaIA([self.claude(), local])).responder(
            {"pergunta": "exportar tela para PDF", "_publico": "equipe"})
        self.assertEqual(r["ia"]["tipo"], "openai")
        self.assertTrue(r["resposta"].startswith("da IA local"))
        self.assertTrue(any("claude" in t for t in r["ia"]["tentativas"]))
        r = robos.Suporte({"base_suporte": BASE}, robos.CadeiaIA([self.claude(), robos.IALocal("")])).responder(
            {"pergunta": "exportar tela para PDF", "_publico": "equipe"})
        self.assertFalse(r["ia"]["usada"])
        self.assertIn("Baixar esta tela", r["resposta"])          # resposta pronta

    def test_teto_robo_responde_por_regras(self):
        self.consumo.write_text(json.dumps({"mes": "2026-11", "gasto_usd": 30.0}), encoding="utf-8")
        r = robos.Suporte({"base_suporte": BASE}, robos.CadeiaIA([self.claude(), robos.IALocal("")])).responder(
            {"pergunta": "exportar tela para PDF", "_publico": "equipe"})
        self.assertTrue(r["ok"])
        self.assertFalse(r["ia"]["usada"])
        self.assertIn("teto", r["ia"]["erro"])
        self.assertEqual(Falso.recebidos, [])

    def test_precos_e_editais_viram_sugestao(self):
        cadeia = robos.CadeiaIA([self.claude()])
        r = robos.Precos({}, cadeia).responder({"itens": [{"descricao": "Módulo fotovoltaico 550 W", "preco": 960}],
                                                "historico": [{"descricao": "Módulo fotovoltaico 550 W", "preco": p} for p in (900, 1000)]})
        self.assertTrue(r["revisao_humana"])
        self.assertTrue(r["dados"]["sugestao"])
        self.assertTrue(r["ia"]["usada"])
        r = robos.Editais({}, cadeia).responder({"editais": [{"id": "b", "titulo": "Chamada energia solar no campo",
                                                             "resumo": "fotovoltaica", "prazo": "2026-12-20"}], "hoje": "2026-11-15"})
        self.assertTrue(r["dados"]["sugestao"])
        self.assertTrue(r["revisao_humana"] and r["ia"]["usada"])
        self.assertIn("Perfil:", Falso.recebidos[-1]["corpo"]["messages"][0]["content"])

    def test_ordem_padrao_do_ambiente(self):
        with mock.patch.dict(os.environ, {"PHYSIS_CLAUDE_CHAVE": CHAVE, "PHYSIS_IA_URL": "http://localhost:8000",
                                          "PHYSIS_CLAUDE_CONSUMO": str(self.consumo), "PHYSIS_CLAUDE_PERMITIDO": "1"}):
            c = robos.ia_do_ambiente()
        self.assertEqual(c.tipo, "claude → openai → regras")
        self.assertNotIn(CHAVE, repr(c.provedores[0]))

    def test_sem_permissao_a_chave_e_ignorada(self):
        """Decisão da dona (27/11/2026): o sistema não usa o Claude, mesmo com chave no ambiente."""
        with mock.patch.dict(os.environ, {"PHYSIS_CLAUDE_CHAVE": CHAVE, "PHYSIS_IA_URL": "http://localhost:8000",
                                          "PHYSIS_CLAUDE_CONSUMO": str(self.consumo)}):
            os.environ.pop("PHYSIS_CLAUDE_PERMITIDO", None)
            c = robos.ia_do_ambiente()
        self.assertEqual(c.tipo, "openai → regras")
        self.assertFalse(any(isinstance(x, robos.claude_mod.IAClaude) for x in c.provedores))


if __name__ == "__main__":
    unittest.main()
