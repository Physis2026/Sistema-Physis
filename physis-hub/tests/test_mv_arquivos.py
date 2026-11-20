"""Caixas de upload do Physis M&A (physis_hub/mv_arquivos.py): tipo conferido pelo conteúdo, limite, sem duplicar, prévia antes
de gravar, aplicação única (editais e finanças 'a conferir'), descarte sem apagar e servidor com cabeçalho anti-CSRF."""
import base64
import io
import json
import tempfile
import threading
import unittest
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

from physis_hub import mv as mvmod
from physis_hub import mv_arquivos, mv_editais, mv_servidor
from physis_hub.mv import MV, ErroMV

CSV_ED = ("chave;titulo;financiador;prazo;status;frente_mais_aderente;aderencia\n"
          "bndes;BNDES Garagem;BNDES;2026-11-30;aberto;engineering;alta\n"
          "iki;IKI Small Grants;IKI;2027-01-08;aberto;instituto;media\n")
CSV_FIN = ("entidade;data;tipo;valor;descricao;projeto;fonte\n"
           "Casa Physis;19/11/2026;despesa;1.234,56;Material;Casa;NF 1\n"
           "instituto;2026-11-20;receita;500;Doação X;;\n"
           "marte;2026-11-20;receita;10;x;;\n"
           "casa;2026-13-40;despesa;10;x;;\n")


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def ods(linhas: list[list[str]]) -> bytes:
    cel = lambda v: f'<table:table-cell office:value-type="string"><text:p>{v}</text:p></table:table-cell>'
    rows = "".join("<table:table-row>" + "".join(cel(v) for v in l) + "</table:table-row>" for l in linhas)
    xml = ('<?xml version="1.0" encoding="UTF-8"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
           'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
           f'<office:body><office:spreadsheet><table:table table:name="A">{rows}</table:table></office:spreadsheet></office:body></office:document-content>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/vnd.oasis.opendocument.spreadsheet")
        z.writestr("content.xml", xml)
    return buf.getvalue()


class TestArquivos(unittest.TestCase):
    def setUp(self):
        mvmod.HOJE = lambda: date(2026, 11, 19)
        self.tmp = tempfile.TemporaryDirectory()
        self.mv = MV(":memory:")
        self.a = mv_arquivos.Arquivos(self.mv, Path(self.tmp.name) / "arquivos")

    def tearDown(self):
        self.tmp.cleanup()

    def test_tipo_conferido_pelo_conteudo(self):
        with self.assertRaises(ErroMV):
            self.a.enviar("documentos", "falso.pdf", b64(b"nao sou pdf"))
        with self.assertRaises(ErroMV):
            self.a.enviar("financas", "x.exe", b64(b"MZ"))
        with self.assertRaises(ErroMV):
            self.a.enviar("outro", "a.pdf", b64(b"%PDF-1.4"))
        r = self.a.enviar("documentos", "ata reunião.pdf", b64(b"%PDF-1.4 ok"), ref="k-mv-teste")
        self.assertEqual((r["estado"], r["ref"], r["importavel"]), ("guardado", "k-mv-teste", False))
        self.assertNotIn("caminho", r)

    def test_nome_seguro_e_pasta(self):
        self.assertEqual(mv_arquivos.nome_seguro("../../Ata Reunião?.pdf"), "ata_reuniao.pdf")
        r = self.a.enviar("documentos", "..\\..\\x.txt", b64(b"ola"))
        dados, nome = self.a.conteudo(r["id"])
        self.assertEqual(dados, b"ola")
        arquivos = list((Path(self.tmp.name) / "arquivos").rglob("*"))
        self.assertTrue(any(p.name.endswith("_x.txt") for p in arquivos))

    def test_limite_e_duplicado(self):
        grande = b"%PDF-" + b"0" * (mv_arquivos.TAMANHO_MAX + 1)
        with self.assertRaises(ErroMV):
            self.a.enviar("documentos", "g.pdf", b64(grande))
        r1 = self.a.enviar("documentos", "a.txt", b64(b"mesmo"))
        r2 = self.a.enviar("documentos", "b.txt", b64(b"mesmo"))
        self.assertEqual(r1["id"], r2["id"])
        self.assertTrue(r2["duplicado"])
        self.assertEqual(len(self.a.listar("documentos")), 1)

    def test_editais_previa_e_aplicacao_unica(self):
        r = self.a.enviar("editais", "banco.csv", b64(CSV_ED.encode("utf-8-sig")))
        self.assertEqual(r["estado"], "recebido")
        p = self.a.previa(r["id"])
        self.assertEqual((p["novos"], p["atualizados"]), (2, 0))
        self.assertEqual(self.mv.db.execute("SELECT COUNT(*) FROM mv_edital").fetchone()[0], 0)   # prévia não grava
        ap = self.a.aplicar(r["id"])
        self.assertIn("2 novo", ap["resultado"])
        self.assertEqual(len(mv_editais.Editais(self.mv).listar()), 2)
        with self.assertRaises(ErroMV):
            self.a.aplicar(r["id"])
        with self.assertRaises(ErroMV):
            self.a.descartar(r["id"])

    def test_editais_csv_sem_titulo(self):
        r = self.a.enviar("editais", "x.csv", b64(b"a;b\n1;2\n"))
        with self.assertRaises(ErroMV):
            self.a.previa(r["id"])

    def test_financas_csv_cp1252_a_conferir(self):
        r = self.a.enviar("financas", "extrato.csv", b64(CSV_FIN.encode("cp1252")))
        p = self.a.previa(r["id"])
        self.assertEqual((p["validas"], len(p["invalidas"])), (2, 2))
        casa = p["itens"][0]
        self.assertEqual((casa["entidade"], casa["data"], casa["valor"]), ("casa", "2026-11-19", 1234.56))
        self.a.aplicar(r["id"])
        fin = self.mv.financeiro()
        self.assertEqual(fin["casa"]["a_conferir"]["despesa"], 1234.56)
        self.assertEqual(fin["casa"]["oficial"], {})
        self.assertEqual(fin["instituto"]["a_conferir"]["receita"], 500.0)
        # o mesmo conteúdo em outro arquivo: linhas já lançadas são reconhecidas e não duplicam
        r2 = self.a.enviar("financas", "extrato2.csv", b64((CSV_FIN + "\n").encode("cp1252")))
        self.assertEqual(self.a.previa(r2["id"])["ja_lancados"], 2)
        self.assertIn("0 lançamento", self.a.aplicar(r2["id"])["resultado"])

    def test_financas_ods(self):
        b = ods([["entidade", "data", "tipo", "valor", "descricao"], ["engineering", "2026-11-19", "receita", "1500.5", "Consultoria"]])
        r = self.a.enviar("financas", "lanc.ods", b64(b))
        p = self.a.previa(r["id"])
        self.assertEqual((p["validas"], p["itens"][0]["valor"]), (1, 1500.5))

    def test_extrato_pdf_so_guardado(self):
        r = self.a.enviar("financas", "extrato.pdf", b64(b"%PDF-1.7"), ref="casa")
        self.assertEqual(r["estado"], "guardado")
        self.assertFalse(self.a.previa(r["id"])["importavel"])
        with self.assertRaises(ErroMV):
            self.a.aplicar(r["id"])

    def test_descartar_mantem_arquivo(self):
        r = self.a.enviar("documentos", "a.txt", b64(b"x"))
        self.assertEqual(self.a.descartar(r["id"])["estado"], "descartado")
        self.assertEqual(self.a.conteudo(r["id"])[0], b"x")
        with self.assertRaises(ErroMV):
            self.a.arquivo("../etc")


class TestServidorUpload(unittest.TestCase):
    def setUp(self):
        self.mv = MV(":memory:")
        self.srv = mv_servidor.servir(self.mv, 0)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def _post(self, p, corpo, cab=True):
        h = {"Content-Type": "application/json"}
        if cab:
            h["X-Physis-MV"] = "1"
        req = urllib.request.Request(self.url + p, data=json.dumps(corpo).encode(), headers=h, method="POST")
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_fluxo_http(self):
        st, _ = self._post("/api/mv/arquivo/enviar", {"destino": "editais", "nome": "b.csv", "conteudo": b64(CSV_ED.encode())}, cab=False)
        self.assertEqual(st, 403)
        st, r = self._post("/api/mv/arquivo/enviar", {"destino": "editais", "nome": "b.csv", "conteudo": b64(CSV_ED.encode())})
        self.assertEqual(st, 200)
        with urllib.request.urlopen(self.url + "/api/mv/arquivo/previa?id=" + r["id"]) as x:
            self.assertEqual(json.loads(x.read())["novos"], 2)
        st, ap = self._post("/api/mv/arquivo/aplicar", {"id": r["id"]})
        self.assertEqual((st, ap["estado"]), (200, "aplicado"))
        with urllib.request.urlopen(self.url + "/api/mv/arquivos?destino=editais") as x:
            self.assertEqual(len(json.loads(x.read())), 1)
        with urllib.request.urlopen(self.url + "/api/mv/arquivo/baixar?id=" + r["id"]) as x:
            self.assertIn("attachment", x.headers["Content-Disposition"])
            self.assertEqual(x.read(), CSV_ED.encode())
        st, e = self._post("/api/mv/arquivo/enviar", {"destino": "documentos", "nome": "a.pdf", "conteudo": b64(b"oi")})
        self.assertEqual(st, 400)


if __name__ == "__main__":
    unittest.main()
