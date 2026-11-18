"""Robôs da Physis (sem rede: a IA local é uma função de mentira).

Protege:
1. A IA local fica desligada sem PHYSIS_IA_URL, recusa endereço de fora da rede, tira dados pessoais antes de
   enviar, entende OpenAI e Ollama, e uma falha não derruba a resposta por regras. O registro não guarda texto.
2. Suporte: responde citando a fonte (docs e curso de introdução); sem confiança, sugere ou abre chamado.
3. Preços: item fora da faixa do histórico/catálogo é apontado; sem referência, pede revisão.
4. Editais: o alinhado à Physis e parecido com um aprovado vem primeiro; prazo vencido vai para o fim.
5. Marketing: o tema que engaja mais sobe (Beta-Binomial) e a nota da regra é a mesma da Gestão.
6. Projetos: esqueleto completo, com cronograma e orçamento, sempre com revisão humana.
7. Pluviômetro: YAML do ESPHome com o pino certo; pino proibido e lugar fora do Brasil são recusados.
"""
import json
import os
import unittest
from datetime import datetime
from unittest import mock

from physis_hub import robos
from physis_hub.hub import Hub

AGORA = datetime(2026, 11, 15, 10, 0).timestamp()

BASE = [
    {"texto": "Para baixar qualquer tela, use o botão Baixar esta tela: ele gera Word, PDF ou Excel com a identidade da Physis.",
     "fonte": "docs/APPS.md", "secao": "Exportar"},
    {"texto": "A bateria do nó de solo deve ficar acima de 3,5 V; abaixo disso o painel mostra alerta de bateria baixa.",
     "fonte": "docs/PROTOCOLO.md", "secao": "Bateria"},
    {"texto": "A previsão do tempo junta Open-Meteo, INMET e CEMADEN, e aprende qual fonte acerta mais no lugar.",
     "fonte": "docs/CLIMA.md", "secao": "Previsão"},
]


class FalsaIA:
    def __init__(self, resposta=None, erro=None):
        self.pedidos, self.resposta, self.erro = [], resposta, erro

    def __call__(self, url, corpo, tempo):
        self.pedidos.append((url, corpo, tempo))
        if self.erro:
            raise self.erro
        return self.resposta


class TestTexto(unittest.TestCase):
    def test_palavras_e_busca(self):
        self.assertEqual(robos.palavras("As Baterias do NÓ"), ["bateria"])
        idx = robos.IndiceTFIDF([d["texto"] for d in BASE])
        (s, i), *_ = idx.buscar("como exportar a tela para PDF?")
        self.assertEqual(i, 0)
        self.assertGreater(s, 0.1)
        self.assertIn("pdf", idx.termos_comuns("tela em pdf", 0))

    def test_anonimizar(self):
        t = robos.anonimizar("Sou Maria Souza, maria@x.com.br, CPF 123.456.789-09, tel (24) 99876-5432, CEP 25600-000, "
                             "ponto -22.50500, -43.18300", nomes=["Maria Souza"])
        for s in ("maria@", "123.456", "99876", "25600", "-22.505", "Maria"):
            self.assertNotIn(s, t)
        self.assertIn("[pessoa]", t)


class TestIALocal(unittest.TestCase):
    def test_desligada_sem_variavel(self):
        with mock.patch.dict(os.environ, {"PHYSIS_IA_URL": ""}):
            ia = robos.IALocal()
        self.assertFalse(ia.ativa)
        self.assertIsNone(ia.gerar("s", "p"))

    def test_recusa_endereco_de_fora(self):
        self.assertTrue(robos.destino_local("http://192.168.0.20:8000"))
        self.assertTrue(robos.destino_local("http://ia-physis:11434"))
        self.assertTrue(robos.destino_local("http://localhost:8000"))
        self.assertFalse(robos.destino_local("https://api.openai.com/v1"))
        with mock.patch.dict(os.environ, {"PHYSIS_IA_EXTERNO": ""}):
            ia = robos.IALocal("https://api.exemplo.com", enviar=FalsaIA({}))
        self.assertFalse(ia.ativa)
        self.assertIn("fora da rede local", ia.erro)

    def test_openai_sem_dados_pessoais_e_registro_so_metadados(self):
        falsa = FalsaIA({"choices": [{"message": {"content": "ok, resposta"}}]})
        ia = robos.IALocal("http://10.0.0.5:8000", enviar=falsa, tempo=5)
        self.assertEqual(ia.gerar("sistema", "meu email é ana@ex.com e cpf 111.222.333-44", robo="t"), "ok, resposta")
        url, corpo, tempo = falsa.pedidos[0]
        self.assertTrue(url.endswith("/v1/chat/completions"))
        self.assertEqual(tempo, 5)
        enviado = json.dumps(corpo)
        self.assertNotIn("ana@ex.com", enviado)
        self.assertNotIn("111.222", enviado)
        meta = robos.REGISTRO_IA[-1]
        self.assertEqual(set(meta), {"robo", "tipo", "bytes_enviados", "ms", "ok", "quando"})

    def test_ollama_e_falha(self):
        falsa = FalsaIA({"response": "texto do ollama"})
        ia = robos.IALocal("http://127.0.0.1:11434/api/generate", enviar=falsa)
        self.assertEqual(ia.tipo, "ollama")
        self.assertEqual(ia.gerar("s", "p"), "texto do ollama")
        self.assertFalse(falsa.pedidos[0][1]["stream"])
        ruim = robos.IALocal("http://127.0.0.1:8000", enviar=FalsaIA(erro=OSError("timeout")))
        self.assertIsNone(ruim.gerar("s", "p"))


class TestSuporte(unittest.TestCase):
    def robo(self, **ctx):
        ia = robos.IALocal("", enviar=FalsaIA())
        return robos.Suporte({"base_suporte": BASE, **ctx}, ia)

    def test_responde_com_citacao(self):
        r = self.robo().responder({"pergunta": "Como baixo a tela em PDF ou Word?", "_publico": "equipe"})
        self.assertTrue(r["ok"])
        self.assertEqual(r["fontes"][0]["fonte"], "docs/APPS.md")
        self.assertIn("[1]", r["resposta"])
        self.assertGreaterEqual(r["confianca"], robos.Suporte.LIMIAR)
        self.assertEqual(r["intencao"], "exportar")

    def test_sem_confianca_escala_e_abre_chamado(self):
        r = self.robo().responder({"pergunta": "Qual é a cor favorita do gato do vizinho?"})
        self.assertTrue(r["revisao_humana"])
        self.assertIn("escalar", r["dados"])
        h = Hub(":memory:", relogio=lambda: AGORA)
        r = self.robo(hub=h, suporte_email="suporte@physis.example", quem="teste").responder(
            {"pergunta": "Qual é a cor favorita do gato do vizinho?", "abrir_chamado": True})
        self.assertTrue(r["dados"]["chamado"]["ok"])
        self.assertEqual(len(h.suporte_listar()), 1)

    def test_ia_melhora_o_texto(self):
        falsa = FalsaIA({"choices": [{"message": {"content": "Use Baixar esta tela [1]."}}]})
        r = robos.Suporte({"base_suporte": BASE}, robos.IALocal("http://localhost:8000", enviar=falsa)).responder(
            {"pergunta": "exportar tela para PDF", "_publico": "equipe"})
        self.assertTrue(r["ia"]["usada"])
        self.assertEqual(r["resposta"], "Use Baixar esta tela [1].")      # sem aviso visível no texto (15/11/2026)
        self.assertNotIn(robos.AVISO_IA, r["resposta"])
        self.assertTrue(r["revisao_humana"])                               # a revisão humana continua
        self.assertEqual(r["ia"]["tipo"], "openai")

    def test_protocolo_de_ia_no_registro(self):
        h = Hub(":memory:", relogio=lambda: AGORA)
        falsa = FalsaIA({"choices": [{"message": {"content": "Use Baixar esta tela [1]."}}]})
        r = robos.Suporte({"base_suporte": BASE, "hub": h}, robos.IALocal("http://localhost:8000", enviar=falsa)).responder(
            {"pergunta": "exportar tela para PDF", "_publico": "equipe"})
        reg = h._db.execute("SELECT id, origem, conteudo FROM registro WHERE tipo='ia'").fetchall()
        self.assertEqual(len(reg), 1)
        self.assertEqual(r["ia"]["protocolo"], reg[0][0])
        c = json.loads(reg[0][2])
        self.assertEqual((reg[0][1], c["robo"], c["provedor"], c["modelo"]), ("robo:suporte", "suporte", "openai", "physis"))
        self.assertTrue(c["quando"])
        self.assertNotIn("Baixar", reg[0][2])                              # o texto não vai para o registro
        self.assertTrue(h.verificar_cadeia()[0])

    def test_base_real_tem_docs_e_curso(self):
        base = robos.carregar_base()
        fontes = {b["fonte"] for b in base}
        self.assertTrue(any(f.startswith("docs/") for f in fontes))
        self.assertIn("Curso PHY-INTRO", fontes)
        r = robos.Suporte({"base_suporte": base}, robos.IALocal("")).responder(
            {"pergunta": "Como abrir um chamado no Suporte Physis pelo WhatsApp?", "_publico": "equipe"})
        self.assertTrue(r["fontes"])


class TestPublicoDoSuporte(unittest.TestCase):
    """Pergunta de cliente nunca cita documento de desenvolvedor nem mostra nome de arquivo ou de código."""
    PERGUNTAS = ("Como baixo a tela em PDF ou Word?", "O que é o physis-odf.js e como exportar?", "Como funciona a exportação ODT?",
                 "Como calcular a carga térmica do ar-condicionado AVAC?", "O nó do sensor está sem sinal, o que faço?",
                 "Como calibrar o pH da água?", "Qual é a senha do primeiro acesso?", "Como o SCADA manda comandos?",
                 "Onde vejo a revisão do AVAC e a exportação?", "Como abrir um chamado no Suporte Physis pelo WhatsApp?")

    @classmethod
    def setUpClass(cls):
        cls.cliente = robos.carregar_base(publico="cliente")
        cls.equipe = robos.carregar_base(publico="equipe")

    def test_base_do_cliente_so_manual_e_curso(self):
        fontes = {b["fonte"] for b in self.cliente}
        self.assertTrue(fontes)
        self.assertTrue(all(f == "Curso PHY-INTRO" or f.startswith("Manual") for f in fontes), fontes)
        self.assertTrue(any(f.startswith("Manual · ") for f in fontes))
        for b in self.cliente:
            self.assertTrue(robos.eh_texto_de_cliente(b["texto"]), b)
        self.assertTrue(any(b["fonte"].startswith("docs/") for b in self.equipe))     # a equipe continua vendo a doc técnica

    def test_pergunta_de_cliente_nunca_cita_doc_de_desenvolvedor(self):
        s = robos.Suporte({}, robos.IALocal(""))
        for p in self.PERGUNTAS:
            r = s.responder({"pergunta": p})                                   # sem _publico: vale cliente
            tudo = json.dumps({k: r.get(k) for k in ("resposta", "fontes", "dados")}, ensure_ascii=False)
            self.assertNotIn("docs/", tudo, p)
            self.assertNotIn("physis_hub", tudo, p)
            for f in r.get("fontes") or []:
                self.assertTrue(f["fonte"] == "Curso PHY-INTRO" or f["fonte"].startswith("Manual"), (p, f["fonte"]))
            self.assertTrue(robos.eh_texto_de_cliente(r["resposta"]), (p, r["resposta"]))
            self.assertNotRegex(r["resposta"], r"\.(md|js|py|html|json)\b")

    def test_base_injetada_tambem_e_filtrada_para_cliente(self):
        base = BASE + [{"texto": "Use o physis-odf.js para gerar o ODT; ver docs/EXPORTACAO.md e a função odt().",
                        "fonte": "Manual · Teste", "secao": "Exportar"}]
        r = robos.Suporte({"base_suporte": base}, robos.IALocal("")).responder({"pergunta": "Como exportar o ODT em PDF?"})
        self.assertNotIn("docs/", json.dumps(r, ensure_ascii=False))
        self.assertNotIn("physis-odf.js", json.dumps(r, ensure_ascii=False))

    def test_ia_que_cita_arquivo_e_descartada_para_cliente(self):
        falsa = FalsaIA({"choices": [{"message": {"content": "Veja docs/EXPORTACAO.md e o physis-odf.js [1]."}}]})
        r = robos.Suporte({}, robos.IALocal("http://localhost:8000", enviar=falsa)).responder({"pergunta": "Como calibrar o pH da água?"})
        if r["fontes"]:
            self.assertFalse(r["ia"]["usada"])
            self.assertNotIn("physis-odf", r["resposta"])
            self.assertTrue(robos.eh_texto_de_cliente(r["resposta"]))


class TestPrecos(unittest.TestCase):
    def test_faixa_e_situacoes(self):
        hist = [{"descricao": "Módulo fotovoltaico 550 W", "preco": p} for p in (900, 950, 1000, 980, 1020)]
        refs = [{"descricao": "Sensor de umidade do solo capacitivo", "min": 80, "max": 150}]
        r = robos.Precos({}, robos.IALocal("")).responder({"itens": [
            {"descricao": "Modulo fotovoltaico 550W", "preco": 2000},
            {"descricao": "Módulo fotovoltaico de 550 W", "preco": 960},
            {"descricao": "Sensor capacitivo de umidade do solo", "preco": 60},
            {"descricao": "Cabo flexível 6 mm²", "preco": 12}], "historico": hist, "referencias": refs})
        sit = [i["situacao"] for i in r["dados"]["itens"]]
        self.assertEqual(sit, ["acima", "ok", "abaixo", "sem_referencia"])
        self.assertTrue(r["revisao_humana"])
        self.assertIn("acima", r["resposta"])

    def test_usa_catalogo_do_hub(self):
        h = Hub(":memory:", relogio=lambda: AGORA)
        h.loja_gravar("kit-solo", {"nome": "Kit sensor de solo LoRa", "preco": 1200.0, "st": "func"}, "teste")
        r = robos.Precos({"hub": h}, robos.IALocal("")).responder({"itens": [{"descricao": "Kit sensor de solo LoRa", "preco": 1250}]})
        it = r["dados"]["itens"][0]
        self.assertEqual(it["situacao"], "ok")
        self.assertIn("catálogo", it["referencias"][0]["origem"])

    def test_sem_itens(self):
        r = robos.Precos({}, robos.IALocal("")).responder({})
        self.assertFalse(r["ok"])


class TestEditais(unittest.TestCase):
    def test_ranking(self):
        editais = [
            {"id": "a", "titulo": "Festival de dança contemporânea", "resumo": "apoio a grupos de dança", "prazo": "2026-12-20"},
            {"id": "b", "titulo": "Chamada pública energia solar e eficiência energética no campo",
             "resumo": "sistemas fotovoltaicos para produtores rurais e irrigação", "prazo": "2026-12-20"},
            {"id": "c", "titulo": "Edital de energia solar para escolas", "resumo": "fotovoltaica", "prazo": "2026-10-01"},
        ]
        aceitos = [{"titulo": "Energia solar para irrigação de pequenos produtores rurais", "resumo": "fotovoltaica no campo"}]
        r = robos.Editais({}, robos.IALocal("")).responder({"editais": editais, "aceitos": aceitos, "hoje": "2026-11-15"})
        ids = [x["id"] for x in r["dados"]["ranking"]]
        self.assertEqual(ids[0], "b")
        self.assertEqual(r["dados"]["ranking"][-1]["nota"], 0)
        self.assertTrue(any("aprovado antes" in m for m in r["dados"]["ranking"][0]["motivos"]))


class TestMarketing(unittest.TestCase):
    def test_aprende_com_engajamento(self):
        temas = [{"id": "1", "tema": "Energia solar no campo", "area": "energia", "tendencia": 5, "interesse": 5, "votos": 0},
                 {"id": "2", "tema": "Qualidade da água e pH", "area": "agua", "tendencia": 5, "interesse": 5, "votos": 0},
                 {"id": "3", "tema": "ESG para pequenas empresas", "area": "sustentabilidade", "tendencia": 5, "interesse": 5, "votos": 0}]
        met = [{"tema_id": "1", "impressoes": 4000, "engajamentos": 80},
               {"tema_id": "2", "impressoes": 4000, "engajamentos": 320},
               {"tema": "ESG para pequenas empresas", "impressoes": 100, "curtidas": 2}]
        r = robos.Marketing({}, robos.IALocal("")).responder({"temas": temas, "metricas": met, "hoje": "2026-11-15"})
        rk = r["dados"]["ranking"]
        self.assertEqual(rk[0]["id"], "2")
        self.assertTrue(next(x for x in rk if x["id"] == "3")["pouco_testado"])
        a, b = rk[0]["intervalo_90"]
        self.assertLess(a, rk[0]["taxa_esperada"])
        self.assertGreater(b, rk[0]["taxa_esperada"])

    def test_nota_regra_igual_a_gestao(self):
        # 0.4*8 + 0.3*6 + 0.3*min(10, 3*2) - 3 (usado há 5 dias) = 3.8
        self.assertEqual(robos.nota_regra_tema({"tendencia": 8, "interesse": 6, "votos": 3, "usadoEm": "2026-11-10"}, "2026-11-15"), 3.8)
        self.assertEqual(robos.nota_regra_tema({"tendencia": 8, "interesse": 6, "votos": 3, "usadoEm": "2026-10-01"}, "2026-11-15"), 6.8)


class TestPluviometro(unittest.TestCase):
    BASE = {"no": 31, "lat": -22.505, "lon": -43.183, "municipio": "Petrópolis", "uf": "RJ", "pino": "GPIO27",
            "hub_url": "http://192.168.0.10:8700", "nome": "Pluviômetro Horta"}

    def test_yaml(self):
        r = robos.Pluviometro({}, robos.IALocal("")).responder({"dados": dict(self.BASE)})
        self.assertTrue(r["ok"], r)
        y = r["dados"]["yaml"]
        for s in ("number: GPIO27", "pullup: true", "ID:31,TIPO:PLUV", "http://192.168.0.10:8700/api/v6/linha", "name: pluviometro-horta",
                  "!secret wifi_senha", "multiply: 1.397"):
            self.assertIn(s, y)
        self.assertEqual(r["dados"]["registro_hub"]["tipo"], "PLUV")
        self.assertTrue(r["revisao_humana"])

    def test_pinos_e_lugar(self):
        p = robos.Pluviometro({}, robos.IALocal(""))
        r = p.responder({"dados": dict(self.BASE, pino=34)})
        self.assertTrue(r["ok"])
        self.assertTrue(r["dados"]["avisos"])
        self.assertNotIn("pullup: true", r["dados"]["yaml"])
        self.assertFalse(p.responder({"dados": dict(self.BASE, pino=6)})["ok"])
        self.assertFalse(p.responder({"dados": dict(self.BASE, lat=40.7, lon=-74.0)})["ok"])
        self.assertFalse(p.responder({"dados": dict(self.BASE, no=120)})["ok"])


class TestProjetos(unittest.TestCase):
    def test_esqueleto(self):
        r = robos.Projetos({}, robos.IALocal("")).responder({"edital": {
            "titulo": "Chamada para reúso de água e saneamento rural", "resumo": "Inscrições até 10/02/2027",
            "valor_max": 200000, "duracao_meses": 12}})
        d = r["dados"]
        self.assertIn("agua", d["areas"])
        self.assertEqual(len(d["secoes"]), 11)
        self.assertEqual(d["prazo"], "2027-02-10")
        crono = next(s for s in d["secoes"] if s["titulo"].startswith("7."))["itens"]
        self.assertTrue(crono[0].startswith("Mapear: meses 1"))
        self.assertTrue(crono[-1].endswith("12"))
        orc = next(s for s in d["secoes"] if s["titulo"].startswith("8."))["itens"]
        self.assertIn("90,000.00", orc[0])
        self.assertTrue(r["revisao_humana"])
        self.assertNotIn("GIZ", r["resposta"])


class TestRoteamento(unittest.TestCase):
    def test_atender(self):
        rs = robos.criar_robos({"base_suporte": BASE}, robos.IALocal(""))
        self.assertEqual(len(robos.listar(rs)), 6)
        self.assertEqual(robos.rotear("o preço da proposta está caro?", rs), "precos")
        self.assertEqual(robos.rotear("gerar esphome do pluviômetro", rs), "pluviometro")
        self.assertEqual(robos.rotear("esqueci minha senha", rs), "suporte")
        cod, r = robos.atender("nao-existe", {}, rs)
        self.assertEqual(cod, 404)
        cod, r = robos.atender("auto", {"pergunta": "como exportar a tela em pdf"}, rs)
        self.assertEqual((cod, r["robo"]), (200, "suporte"))
        for chave in ("resposta", "fontes", "confianca", "revisao_humana", "dados", "ia"):
            self.assertIn(chave, r)


if __name__ == "__main__":
    unittest.main()
