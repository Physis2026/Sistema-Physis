"""Bots mercado (parcerias e GIS), financeiro, jurídico, kit 26/11, melhoria contínua e revisão semanal (22/11/2026). Sem internet."""
import json
import os
import tempfile
import time
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest import mock

from physis_hub import mv_bots, mv_comandos, mv_ecossistema as E, mv_financeiro as F, mv_kit as K
from physis_hub.mv import MV

OVERPASS = {"elements": [
    {"type": "node", "id": 1, "lat": -22.51, "lon": -43.18, "tags": {"name": "Universidade X", "amenity": "university"}},
    {"type": "way", "id": 2, "center": {"lat": -22.50, "lon": -43.17}, "tags": {"name": "Supermercado Y", "shop": "supermarket"}},
    {"type": "node", "id": 3, "lat": -22.52, "lon": -43.19, "tags": {"amenity": "recycling"}}]}       # sem nome: ignorado


def falso_overpass(q):
    return OVERPASS if ("university" in q or "supermarket" in q) else {"elements": []}


class Mercado(unittest.TestCase):
    def test_descoberta_planilha_mapa_e_lacunas(self):
        mv = MV(":memory:")
        d = Path(tempfile.mkdtemp())
        (d / "parcerias.csv").write_text("nome;tipo;areas;cidade;uf;lat;lon;site;contato;modalidade;estado\n"
                                         "Fabricante Z;fabricante;solar,iot_hardware;Petrópolis;RJ;-22.5;-43.2;https://z.example;;teste;conferido\n", encoding="utf-8")
        r = E.bot_mercado(mv, d, buscar=falso_overpass, abrir=lambda u: 200, online=True)
        tipos = dict(mv.db.execute("SELECT tipo, COUNT(*) FROM mv_parceria GROUP BY tipo").fetchall())
        self.assertEqual(tipos.get("fabricante"), 1)
        self.assertGreaterEqual(tipos.get("estagio", 0), 1)
        estados = {e for (e,) in mv.db.execute("SELECT estado FROM mv_parceria WHERE fonte LIKE 'OpenStreetMap%'")}
        self.assertEqual(estados, {"a_conferir"})                       # nada de fora vira parceiro sozinho
        g = json.loads((d / "parcerias.geojson").read_text(encoding="utf-8"))
        self.assertTrue(all(f["geometry"]["type"] == "Point" for f in g["features"]))
        self.assertTrue((d / "mapa-ecossistema.md").is_file())
        self.assertEqual(r["dados_abertos"]["ok"], len(E.DADOS_ABERTOS))
        pedidos = mv.db.execute("SELECT COUNT(*) FROM mv_pedido_bot WHERE origem='mercado'").fetchone()[0]
        E.bot_mercado(mv, d, buscar=falso_overpass, abrir=lambda u: 200, online=True)
        self.assertEqual(mv.db.execute("SELECT COUNT(*) FROM mv_pedido_bot WHERE origem='mercado'").fetchone()[0], pedidos)   # sem repetir

    def test_sem_internet_segue(self):
        mv = MV(":memory:")
        def cai(q):
            raise OSError("sem rede")
        r = E.bot_mercado(mv, Path(tempfile.mkdtemp()), buscar=cai, abrir=lambda u: (_ for _ in ()).throw(OSError()), online=True)
        self.assertIn("erro", r["descoberta"]["petropolis-rj"])


NFE_XML = b"""<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe35123"><ide><dhEmi>2026-11-10T10:00:00-03:00</dhEmi></ide>
<emit><CNPJ>11222333000181</CNPJ></emit><dest><CNPJ>44555666000199</CNPJ></dest><total><ICMSTot><vNF>150.00</vNF></ICMSTot></total></infNFe></NFe></nfeProc>"""


class Financeiro(unittest.TestCase):
    def test_regras_e_nfe(self):
        mv = MV(":memory:")
        for v, fonte, desc in ((100, "", "compra loja"), (100, "", "compra loja"), (500, "rec.pdf", "patrocinio evento")):
            mv.lancar({"entidade": "engineering", "tipo": "despesa", "data": "2026-11-10", "valor": v, "descricao": desc, "fonte": fonte})
        d = Path(tempfile.mkdtemp())
        (d / "n1.xml").write_bytes(NFE_XML)
        self.assertEqual(F.ler_nfe(NFE_XML)["valor"], 150.0)
        r = F.bot_financeiro(mv, d, date(2026, 11, 22))
        tipos = {t for (t,) in mv.db.execute("SELECT tipo FROM mv_alerta WHERE bot='financeiro' AND resolvido IS NULL")}
        self.assertTrue({"sem_comprovante", "duplicado", "saldo_negativo", "nota_sem_lancamento"} <= tipos, tipos)
        self.assertIn("patrocinio", json.dumps(r["fluxo"]))
        email = mv.db.execute("SELECT estado, resultado FROM mv_pedido_bot WHERE origem='financeiro'").fetchone()
        self.assertEqual(email[0], "rascunho")                           # nunca enviado sozinho
        self.assertIn("[contador]", email[1])


class Vencimentos(unittest.TestCase):
    def test_calendario_unico(self):
        mv = MV(":memory:")
        mv.salvar_tarefa({"id": "j1-estatuto", "frente": "instituto", "titulo": "J1 Estatuto", "inicio": "2026-11-01", "fim": "2026-11-15"})
        d = Path(tempfile.mkdtemp())
        (d / "vencimentos.csv").write_text("item;tipo;data;responsavel;fonte\nDCTFWeb novembro;fiscal;2026-11-28;Contador;contador\n"
                                           "ACT com universidade;act;2027-03-01;Rafaella;\n", encoding="utf-8")
        r = F.bot_vencimentos(mv, date(2026, 11, 22), d)
        self.assertEqual(r["eventos"], 3)
        alertas = {t for (t,) in mv.db.execute("SELECT tipo FROM mv_alerta WHERE bot='vencimentos' AND resolvido IS NULL")}
        self.assertIn("juridico", alertas)                   # vencida
        self.assertNotIn("fiscal", alertas)                  # sem antecedência definida: só avisa o vencido
        ics = (d / "calendario-de-vencimentos.ics").read_text(encoding="utf-8")
        self.assertIn("BEGIN:VCALENDAR", ics)
        self.assertIn("DTSTART;VALUE=DATE:20261128", ics)
        from physis_hub import mv_auditoria as A
        A._caixa(mv)
        pid = next(p["id"] for p in mv_comandos.perguntas(mv) if p["origem"] == A.origem_limite("PHYSIS_VENC_AVISO_DIAS"))
        mv_comandos.responder(mv, pid, "15")
        F.bot_vencimentos(mv, date(2026, 11, 22), d)
        alertas = {t for (t,) in mv.db.execute("SELECT tipo FROM mv_alerta WHERE bot='vencimentos' AND resolvido IS NULL")}
        self.assertIn("fiscal", alertas)                     # agora avisa 15 d antes
        self.assertEqual(mv.db.execute("SELECT estado FROM mv_pedido_bot WHERE origem='vencimentos-fiscal'").fetchone()[0], "rascunho")


class Kit(unittest.TestCase):
    def test_versao_zero(self):
        mv = MV(":memory:")
        d = Path(tempfile.mkdtemp())
        r = K.bot_kit(mv, d, date(2026, 11, 22))
        self.assertEqual(r["faltam"], r["exigidos"])
        self.assertEqual(r["dias_para_26_11"], 4)
        odt = d / "versao-zero" / "instituto" / "act.odt"
        self.assertTrue(zipfile.is_zipfile(odt))
        self.assertIn(b"[MARCADOR]", zipfile.ZipFile(odt).read("content.xml"))
        self.assertTrue((d / "situacao-do-kit.md").is_file())


class Melhoria(unittest.TestCase):
    def test_taxa_de_aprovacao(self):
        mv = MV(":memory:")
        cmd = mv_comandos.Comandos(mv)
        for est in ["descartado"] * 6 + ["aprovado"]:
            p = cmd._pedido("mercado", f"x{time.time()}", "", "rascunho", "", origem="mercado")
            mv.db.execute("UPDATE mv_pedido_bot SET estado=? WHERE id=?", (est, p["id"]))
        r = K.bot_melhoria(mv)
        self.assertLess(r["por_bot"]["mercado"]["taxa"], 0.4)
        self.assertTrue(mv.db.execute("SELECT 1 FROM mv_alerta WHERE bot='melhoria' AND tipo='baixa_aprovacao'").fetchone())


class Semanal(unittest.TestCase):
    def test_so_junta(self):
        mv = MV(":memory:")
        mv.registrar_execucao("atrasos", time.time(), "{}")
        mv.registrar_execucao("editais", time.time(), "", "ValueError()")
        d = Path(tempfile.mkdtemp())
        n_antes = mv.db.execute("SELECT COUNT(*) FROM mv_execucao").fetchone()[0]
        r = K.bot_semanal(mv, d)
        self.assertEqual(mv.db.execute("SELECT COUNT(*) FROM mv_execucao").fetchone()[0], n_antes + 1)   # não rodou outros bots
        self.assertEqual(r["erros"], 1)
        self.assertTrue(Path(r["arquivo"]).is_file())


class Enxuta(unittest.TestCase):
    def test_documentos_so_quando_muda(self):
        mv = MV(":memory:")
        d = Path(tempfile.mkdtemp())
        (d / "a.md").write_text("texto", encoding="utf-8")
        r1 = mv_bots.BOTS["documentos"](mv, [d])
        r2 = mv_bots.BOTS["documentos"](mv, [d])
        self.assertNotIn("pulado", r1)
        self.assertIn("pulado", r2)
        (d / "b.md").write_text("novo", encoding="utf-8")
        self.assertNotIn("pulado", mv_bots.BOTS["documentos"](mv, [d]))
        r4 = mv_bots.BOTS["documentos"](mv, [d], agora=time.time() + 25 * 3600)
        self.assertNotIn("pulado", r4)                       # 1 vez por dia lê tudo

    def test_mercado_sob_demanda_e_renovacao(self):
        mv = MV(":memory:")
        d = Path(tempfile.mkdtemp())
        chamadas = []
        def buscar(q):
            chamadas.append(q)
            return OVERPASS if "university" in q else {"elements": []}
        E.bot_mercado(mv, d, buscar=buscar, abrir=lambda u: 200, online=True, cidade="Petropolis", area="cursos_inovastem")
        n = len(chamadas)
        self.assertGreater(n, 0)
        self.assertTrue(all("-22.505" in q for q in chamadas))          # só a cidade pedida
        E.bot_mercado(mv, d, buscar=buscar, abrir=lambda u: 200, online=True, cidade="Petrópolis", area="cursos_inovastem")
        self.assertEqual(len(chamadas), n)                               # guardado por 6 meses
        with self.assertRaises(ValueError):
            E.bot_mercado(mv, d, buscar=buscar, online=True, cidade="Lisboa")
        self.assertNotIn("mercado", __import__("physis_hub.mv_vigia", fromlist=["x"]).LIMITE_H)

    def test_comando_mercado(self):
        mv = MV(":memory:")
        cmd = mv_comandos.Comandos(mv)
        with mock.patch.object(E, "bot_mercado", lambda mv, **k: {"ok": k}):
            r = cmd.executar("/mercado Itirapuã avac")
        self.assertIn("avac", r["resultado"])
        self.assertIn("Itirapu", r["resultado"])

    def test_kit_depois_do_prazo_so_segunda(self):
        mv = MV(":memory:")
        self.assertIn("pulado", K.bot_kit(mv, Path(tempfile.mkdtemp()), date(2026, 12, 2)))     # quarta
        self.assertNotIn("pulado", K.bot_kit(mv, Path(tempfile.mkdtemp()), date(2026, 11, 30)))  # segunda

    def test_melhoria_mede_uso(self):
        mv = MV(":memory:")
        antigo = time.time() - 40 * 86400
        mv.db.execute("INSERT INTO mv_execucao (bot,inicio,fim,resumo,erro) VALUES ('links',?,?,'','')", (antigo, antigo))
        mv.alertar("links", "link_quebrado", "x", "atencao", "link sem resposta")
        r = K.bot_melhoria(mv)
        self.assertEqual(r["uso_4_semanas"]["links"]["acoes"], 0)
        self.assertTrue(mv.db.execute("SELECT 1 FROM mv_alerta WHERE bot='melhoria' AND tipo='sem_uso' AND ref='links'").fetchone())


class Fatos(unittest.TestCase):
    def test_base_de_fatos(self):
        from physis_hub import mv_fatos
        mv = MV(":memory:")
        d = Path(tempfile.mkdtemp())
        docs = d / "docs"
        docs.mkdir()
        (docs / "apresentacao.md").write_text("Physis Engenharia LTDA, empresa de Petrópolis", encoding="utf-8")
        r = mv_fatos.bot_fatos(mv, d, [docs])
        self.assertIn("visao", r["vazios"])
        self.assertEqual(r["inconsistencias"], 0)            # sem forma errada cadastrada: nada inventado
        fatos = json.loads((d / "fatos.json").read_text(encoding="utf-8"))
        next(x for x in fatos if x["chave"] == "razao_social")["errado"] = [r"Physis Engenharia"]
        (d / "fatos.json").write_text(json.dumps(fatos), encoding="utf-8")
        r = mv_fatos.bot_fatos(mv, d, [docs])
        self.assertEqual(r["inconsistencias"], 1)
        pid = next(p["id"] for p in mv_comandos.perguntas(mv) if p["origem"] == "pendencia:fato:visao")
        mv_comandos.responder(mv, pid, "Ecossistemas que se pagam com a natureza")
        mv_fatos.bot_fatos(mv, d, [docs])
        self.assertEqual(mv_fatos.valor(mv_fatos.carregar(d), "visao"), "Ecossistemas que se pagam com a natureza")
        with mock.patch.object(mv_fatos, "carregar", lambda saida=None: mv_fatos.carregar.__wrapped__(d) if hasattr(mv_fatos.carregar, "__wrapped__") else json.loads((d / "fatos.json").read_text(encoding="utf-8"))):
            odt = K.versao_zero(mv, "ecossistema", "visao_missao")
        self.assertIn(b"Ecossistemas que se pagam", zipfile.ZipFile(__import__("io").BytesIO(odt)).read("content.xml"))


if __name__ == "__main__":
    unittest.main()
