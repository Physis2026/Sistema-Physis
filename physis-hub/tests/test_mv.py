"""Physis M&V (versão de teste; physis_hub/mv.py, mv_bots.py, mv_servidor.py, mv_semente.py; docs/MV.md).

Protege:
1. CPM: caminho crítico só em cadeias com 2+ tarefas, folga correta, prazo em risco quando a dependência empurra o fim,
   ciclo listado sem quebrar.
2. Estados, validações e data de conclusão; importação da Gestão (physis/1) com datas estimadas [CONFERIR].
3. Financeiro sempre separado por entidade; "oficial" só com conferência do contador (D70).
4. Bots: atraso com intervenção sugerida; alertas idempotentes e fechados quando o problema some; regras dos documentos
   (2031, sede, Rafaella, S2 SARL, bônus) e metadados de gerador (autor/data falsos) viram alerta de template.
5. Semente: toda tarefa ligada a uma meta 2027–2031 e o plano da Fase 0 sem prazo em risco.
6. Servidor: só localhost, POST exige X-Physis-MV, exportação ODS/ODT válida.
7. Tela: só cores da PALETA.md, tema claro e escuro, sem recurso de internet.
"""
import io
import json
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

from physis_hub import mv as mvmod
from physis_hub import mv_bots, mv_semente, mv_servidor
from physis_hub.mv import MV, ErroMV

RAIZ = Path(__file__).resolve().parents[1]
HOJE = date(2026, 11, 18)


def novo():
    mvmod.HOJE = lambda: HOJE
    return MV(":memory:")


def t(mv, i, ini, fim, dep=(), **kw):
    return mv.salvar_tarefa({"id": i, "frente": kw.pop("frente", "transversal"), "titulo": kw.pop("titulo", i), "inicio": ini,
                             "fim": fim, "depende_de": list(dep), "responsavel": kw.pop("responsavel", "Rafaella"), **kw})


class TestCPM(unittest.TestCase):
    def test_cadeia_critica_e_folga(self):
        mv = novo()
        t(mv, "a", "2026-11-19", "2026-11-21")          # 3 d
        t(mv, "b", "2026-11-19", "2026-11-28", ["a"])   # 10 d, empurrada para 22/11 → fim 01/12
        t(mv, "c", "2026-11-19", "2026-11-20", ["a"])   # 2 d, folga
        t(mv, "solta", "2026-11-19", "2026-11-30")      # sozinha: não é caminho
        r = mv.cpm()
        self.assertEqual(r["tarefas"]["b"]["es"], "2026-11-22")
        self.assertEqual(r["tarefas"]["b"]["ef"], "2026-12-01")
        self.assertEqual(set(r["criticos"]), {"a", "b"})
        self.assertGreater(r["tarefas"]["c"]["folga"], 0)
        self.assertFalse(r["tarefas"]["solta"]["critico"])
        self.assertTrue(r["tarefas"]["b"]["prazo_em_risco"])
        self.assertEqual(r["tarefas"]["b"]["estouro_d"], 3)

    def test_ciclo_listado(self):
        mv = novo()
        t(mv, "x", "2026-11-19", "2026-11-20", ["y"])
        t(mv, "y", "2026-11-19", "2026-11-20", ["x"])
        self.assertTrue(mv.cpm()["ciclos"])


class TestTarefas(unittest.TestCase):
    def test_validacoes(self):
        mv = novo()
        for ruim in ({"id": "a b"}, {"id": "a", "frente": "nada", "titulo": "x"}, {"id": "a", "frente": "casa", "titulo": ""},
                     {"id": "a", "frente": "casa", "titulo": "x", "estado": "talvez"},
                     {"id": "a", "frente": "casa", "titulo": "x", "inicio": "18/11/2026"}):
            with self.assertRaises(ErroMV):
                mv.salvar_tarefa(ruim)

    def test_estado_e_conclusao(self):
        mv = novo()
        t(mv, "a", "2026-11-10", "2026-11-12")
        self.assertTrue(mv.atrasada(mv.tarefa("a")))
        x = mv.mudar_estado("a", "feita")
        self.assertEqual(x["concluida_em"], "2026-11-18")
        self.assertFalse(mv.atrasada(x))
        y = mv.mudar_estado("a", "bloqueada", "esperando o contador")
        self.assertIsNone(y["concluida_em"])
        self.assertEqual(y["bloqueio"], "esperando o contador")

    def test_importar_gestao(self):
        mv = novo()
        d = {"_formato": "physis/1", "tabelas": {"pessoa": [{"pessoa_id": "eric", "nome": "Eric Oliveira"}],
             "projeto": [{"projeto_id": "p1", "nome": "Fase 2 · 1. Servidor"}],
             "tarefa": [{"tarefa_id": "t1", "titulo": "Chave", "pessoa_id": "eric", "projeto_id": "p1", "horizonte": "micro",
                         "concluida": False, "depende_de": None, "extras": {"prioridade": 0}},
                        {"tarefa_id": "t2", "titulo": "VPN", "pessoa_id": "eric", "projeto_id": "p1", "horizonte": "macro",
                         "concluida": True, "depende_de": "t1", "extras": {}}]}}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "g.json"
            p.write_text(json.dumps(d), encoding="utf-8")
            self.assertEqual(mv.importar_gestao(p), 2)
        a, b = mv.tarefa("gestao:t1"), mv.tarefa("gestao:t2")
        self.assertEqual((a["fim"], a["prioridade"], a["responsavel"], a["data_estimada"]), ("2026-11-24", 0, "Eric Oliveira", 1))
        self.assertEqual((b["estado"], b["depende_de"]), ("feita", ["gestao:t1"]))

    def test_importar_por_frente_move_tarefas_do_instituto(self):
        """18/11/2026: tarefas que saíram da Gestão da Physis entram na frente instituto; as que somem só são listadas."""
        mv = novo()
        tar = lambda i: {"tarefa_id": i, "titulo": i, "pessoa_id": "x", "horizonte": "meso", "extras": {}}  # noqa: E731
        with tempfile.TemporaryDirectory() as tmp:
            antes, physis, inst = (Path(tmp) / n for n in ("a.json", "p.json", "i.json"))
            antes.write_text(json.dumps({"tabelas": {"tarefa": [tar("t1"), tar("t3d")]}}), encoding="utf-8")
            physis.write_text(json.dumps({"tabelas": {"tarefa": [tar("t1")]}}), encoding="utf-8")
            inst.write_text(json.dumps({"tabelas": {"tarefa": [tar("t3d")]}}), encoding="utf-8")
            mv.importar_gestao(antes)
            self.assertEqual(mv.ausentes_da_gestao(physis), ["gestao:t3d"])
            mv.importar_gestao(physis)
            mv.importar_gestao(inst, frente="instituto")
            self.assertEqual(mv.ausentes_da_gestao(physis), [])
            self.assertEqual((mv.tarefa("gestao:t3d")["frente"], mv.tarefa("gestao:t3d")["meta"]), ("instituto", "m-inst-ict"))
            self.assertEqual(mv.tarefa("gestao:t1")["meta"], "m-eng-sistema")
            with self.assertRaises(ErroMV):
                mv.importar_gestao(physis, frente="nada")


class TestFinanceiro(unittest.TestCase):
    def test_separado_e_conferencia(self):
        mv = novo()
        mv.lancar({"entidade": "instituto", "tipo": "doacao", "data": "2026-11-18", "valor": 1000})
        mv.lancar({"entidade": "instituto", "tipo": "doacao", "data": "2026-11-18", "valor": 500, "conferido": True})
        mv.lancar({"entidade": "casa", "tipo": "receita", "data": "2026-11-18", "valor": 70})
        f = mv.financeiro()
        self.assertEqual(f["instituto"]["oficial"], {"doacao": 500.0})
        self.assertEqual(f["instituto"]["a_conferir"], {"doacao": 1000.0})
        self.assertEqual(f["casa"]["a_conferir"], {"receita": 70.0})
        self.assertEqual(f["engineering"]["lancamentos"], 0)
        with self.assertRaises(ErroMV):
            mv.lancar({"entidade": "todas", "tipo": "receita", "data": "2026-11-18", "valor": 1})


class TestBots(unittest.TestCase):
    def test_atraso_intervencao_e_fechamento(self):
        mv = novo()
        t(mv, "a", "2026-11-01", "2026-11-10", prioridade=1)
        t(mv, "b", "2026-11-11", "2026-11-30", ["a"])
        r = mv_bots.bot_atrasos(mv, HOJE)
        self.assertEqual(r["atrasadas"], 1)
        al = [x for x in mv.alertas() if x["tipo"] == "atrasada"]
        self.assertEqual(len(al), 1)
        self.assertEqual(al[0]["gravidade"], "alerta")
        self.assertIn("segura 1", al[0]["acao"])
        mv_bots.bot_atrasos(mv, HOJE)                       # idempotente
        self.assertEqual(len([x for x in mv.alertas() if x["tipo"] == "atrasada"]), 1)
        mv.mudar_estado("a", "feita")
        mv_bots.bot_atrasos(mv, HOJE)
        self.assertFalse([x for x in mv.alertas() if x["tipo"] == "atrasada"])

    def test_regras_dos_documentos(self):
        f, n = mv_bots.conferir_texto("Arquitetura 2027–2032. Preparado por Rafaela. A ICT na América Latina com duas ONGs. "
                                      "Bônus de participação sobre metade das vendas. [MARCADOR] [CONFERIR]")
        self.assertEqual({x["regra"] for x in f}, {"horizonte", "nome", "sede", "ongs", "bonus"})
        self.assertEqual(n, 2)
        f, _ = mv_bots.conferir_texto("Rafaella. Instituto (ICT) com sede e foro no Brasil, atuação na América Latina. 2027–2031. "
                                      "Distrito de inovação da América Latina.")
        self.assertEqual(f, [])

    def test_bot_documentos_varre_e_cria_tarefa(self):
        mv = novo()
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp) / "Instituto Physis"
            raiz.mkdir()
            (raiz / "memo.md").write_text("Instituto Physis, ICT na América Latina.", encoding="utf-8")
            (raiz / "ok.md").write_text("Tudo certo, 2027–2031.", encoding="utf-8")
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as z:
                z.writestr("docProps/core.xml", "<dc:description>generated by python-docx</dc:description>"
                           "<dcterms:modified>2013-12-23T23:15:00Z</dcterms:modified>")
                z.writestr("word/document.xml", "<w:p>Texto 2027–2031</w:p>")
            (raiz / "gerado.docx").write_bytes(buf.getvalue())
            ign = raiz / "_backup_x"
            ign.mkdir()
            (ign / "velho.md").write_text("2027–2032", encoding="utf-8")
            r = mv_bots.bot_documentos(mv, [raiz], HOJE)
        self.assertEqual(r["vistos"], 3)
        self.assertEqual(r["com_falha"], 1)
        self.assertEqual(r["template_gerador"], 1)
        docs = {d["nome"]: d for d in mv.documentos()}
        self.assertEqual(docs["memo.md"]["situacao"], "falha")
        self.assertEqual(docs["gerado.docx"]["idade_d"], 0)          # data do gerador ignorada
        self.assertTrue(any(x["origem"] == "bot-documentos" for x in mv.tarefas()))
        self.assertTrue(any(a["tipo"] == "template" for a in mv.alertas()))

    def test_bot_com_defeito_nao_para_os_outros(self):
        mv = novo()
        orig = mv_bots.BOTS["atrasos"]
        mv_bots.BOTS["atrasos"] = lambda m: 1 / 0
        try:
            r = mv_bots.rodar(mv, ["atrasos"])
        finally:
            mv_bots.BOTS["atrasos"] = orig
        self.assertIn("erro", r["atrasos"])
        self.assertTrue(any(a["tipo"] == "bot_falhou" for a in mv.alertas()))


class TestSemente(unittest.TestCase):
    def test_metas_e_plano_sem_risco(self):
        mv = novo()
        mv_semente.semear(mv)
        metas = {m["id"] for m in mv.roadmap()["metas"]}
        for x in mv.tarefas():
            self.assertIn(x["meta"], metas, x["id"])
            self.assertTrue(x["responsavel"])
        self.assertEqual(mv.cpm()["em_risco"], [])
        self.assertEqual(mv.cpm()["ciclos"], [])
        self.assertTrue(all(2027 <= m["ano"] <= 2031 for m in mv.roadmap()["metas"]))


class TestServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mv = novo()
        mv_semente.semear(cls.mv)
        cls.srv = mv_servidor.servir(cls.mv, 0)
        cls.url = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def req(self, p, corpo=None, cab=None):
        r = urllib.request.Request(self.url + p, data=json.dumps(corpo).encode() if corpo is not None else None, headers=cab or {})
        try:
            with urllib.request.urlopen(r) as x:
                return x.status, x.read(), x.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def test_leitura_e_post_protegido(self):
        c, b, _ = self.req("/api/mv/saude")
        self.assertEqual(c, 200)
        self.assertIn("transversal", json.loads(b)["frentes"])
        c, _, _ = self.req("/api/mv/estado", {"id": "mv-nucleo", "estado": "revisao"})
        self.assertEqual(c, 403)
        c, b, _ = self.req("/api/mv/estado", {"id": "mv-nucleo", "estado": "revisao"}, {"X-Physis-MV": "1"})
        self.assertEqual((c, json.loads(b)["estado"]), (200, "revisao"))
        c, _, _ = self.req("/api/mv/saude", cab={"Host": "evil.example"})
        self.assertEqual(c, 403)

    def test_exportacao_odf(self):
        for vista in ("tarefas", "alertas", "documentos", "saude"):
            for fmt, mime in (("ods", "spreadsheet"), ("odt", "text")):
                c, b, h = self.req(f"/api/mv/exportar?vista={vista}&formato={fmt}")
                self.assertEqual(c, 200, (vista, fmt))
                z = zipfile.ZipFile(io.BytesIO(b))
                self.assertIn(mime, z.read("mimetype").decode())
                self.assertIn("attachment", h["Content-Disposition"])


class TestTela(unittest.TestCase):
    def test_paleta_tema_sem_internet(self):
        html = (RAIZ / "web" / "mv.html").read_text(encoding="utf-8")
        paleta = set(re.findall(r"#[0-9A-Fa-f]{6}", (RAIZ / "docs" / "PALETA.md").read_text(encoding="utf-8")))
        usadas = set(re.findall(r"#[0-9A-Fa-f]{6}\b", html))
        self.assertTrue(usadas, "nenhuma cor encontrada")
        self.assertEqual({c.upper() for c in usadas} - {c.upper() for c in paleta}, set())
        self.assertIn('html[data-tema="escuro"]', html)
        self.assertNotRegex(html, r"(src|href)=\"https?://")
        self.assertEqual(html.count("<h1"), 1)


if __name__ == "__main__":
    unittest.main()
