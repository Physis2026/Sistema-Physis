"""Comandos aos bots, bots por tarefa e programáveis, aprovações, modelos 3D e modo rede local do Physis M&A (20/11/2026)."""
import base64
import json
import struct
import tempfile
import threading
import time
import unittest
import urllib.request
from datetime import date
from pathlib import Path

from physis_hub import mv as mvmod
from physis_hub import mv_arquivos, mv_comandos, mv_servidor
from physis_hub.mv import MV, ErroMV


def stl_binario(n=1) -> bytes:
    tri = struct.pack("<12fH", 0, 0, 1, 0, 0, 0, 10, 0, 0, 0, 10, 0, 0)
    return b"\x00" * 80 + struct.pack("<I", n) + tri * n


class TestComandos(unittest.TestCase):
    def setUp(self):
        mvmod.HOJE = lambda: date(2026, 11, 20)
        self.tmp = tempfile.TemporaryDirectory()
        self.mv = MV(":memory:")
        self.arq = mv_arquivos.Arquivos(self.mv, Path(self.tmp.name) / "arq")
        self.c = mv_comandos.Comandos(self.mv, self.arq)
        self.mv.salvar_tarefa({"id": "f0-advogado", "frente": "transversal", "titulo": "Escolher advogado e contrato de honorários",
                               "responsavel": "Rafaella", "fim": "2026-11-28", "data_estimada": True})

    def tearDown(self):
        self.tmp.cleanup()

    def test_modelo_de_contrato_vira_odt_de_teste_anexado(self):
        r = self.c.executar("/contrato f0-advogado")
        self.assertEqual((r["tipo"], r["estado"], r["tarefa"]), ("modelo", "rascunho", "f0-advogado"))
        dados, nome = self.arq.conteudo(r["arquivo"])
        self.assertEqual(dados[:2], b"PK")
        self.assertTrue(nome.endswith("_TESTE.odt"))
        self.assertEqual(self.arq.arquivo(r["arquivo"])["origem"], "bot")

    def test_email_e_rascunho_e_nada_sai(self):
        r = self.c.executar('/email f0-advogado "Pedido de proposta"')
        self.assertEqual(r["estado"], "rascunho")
        self.assertIn("Nada foi enviado", r["resultado"])
        self.assertIn("Pedido de proposta", r["resultado"])

    def test_checklist_reconhece_contrato(self):
        r = self.c.executar("/checklist f0-advogado")
        self.assertIn("Revisão jurídica", r["resultado"])

    def test_texto_livre_vai_para_fila_do_claude_com_tarefa(self):
        r = self.c.executar("Prepare perguntas ao advogado para #f0-advogado")
        self.assertEqual((r["tipo"], r["estado"], r["tarefa"]), ("claude", "na_fila", "f0-advogado"))
        self.assertEqual(len(self.c.fila("na_fila")), 1)
        p = self.c.decidir_pedido(r["id"], "aprovado")
        self.assertEqual(p["estado"], "aprovado")

    def test_erros_claros(self):
        for t in ["", "/naoexiste", "/contrato tarefa-que-nao-existe", "/modelo carta f0-advogado", "/programar ano /rodar resumo",
                  "/programar dia /programar dia /rodar resumo"]:
            with self.assertRaises(ErroMV, msg=t):
                self.c.executar(t)
        self.assertIn("/modelo", self.c.executar("/ajuda")["resultado"])

    def test_bot_programado_roda_na_frequencia(self):
        r = self.c.executar("/programar dia /checklist f0-advogado")
        self.assertEqual(r["tipo"], "programado")
        t0 = time.time()
        self.assertEqual(len(self.c.rodar_programados(t0)), 1)
        self.assertEqual(self.c.rodar_programados(t0 + 3600), [])           # ainda não passou um dia
        self.assertEqual(len(self.c.rodar_programados(t0 + 86400)), 1)
        self.c.alternar(r["id"], False)
        self.assertEqual(self.c.rodar_programados(t0 + 3 * 86400), [])
        self.assertEqual(len([p for p in self.c.fila() if p["origem"].startswith("programado:")]), 2)

    def test_imprimir_so_modelo_3d(self):
        m = self.arq.enviar("modelos3d", "peca.stl", base64.b64encode(stl_binario()).decode(), ref="CC BY 4.0")
        r = self.c.executar(f"/imprimir {m['id']} PETG")
        self.assertEqual((r["tipo"], r["estado"]), ("impressao3d", "rascunho"))
        self.assertIn("PETG", r["resultado"])
        d = self.arq.enviar("documentos", "a.txt", base64.b64encode(b"x").decode())
        with self.assertRaises(ErroMV):
            self.c.executar(f"/imprimir {d['id']}")
        with self.assertRaises(ErroMV):
            self.arq.enviar("modelos3d", "falso.stl", base64.b64encode(b"nao sou stl").decode())

    def test_revisar_anexo(self):
        d = self.arq.enviar("documentos", "nota.md", base64.b64encode("Horizonte 2032, assinado Rafaela.".encode()).decode())
        r = self.c.executar(f"/revisar {d['id']}")
        self.assertIn("falha", r["resultado"])

    def test_aprovacoes(self):
        self.assertEqual(self.c.semear_aprovacoes(mv_comandos.APROVACOES_23_11), len(mv_comandos.APROVACOES_23_11))
        self.assertEqual(self.c.semear_aprovacoes(mv_comandos.APROVACOES_23_11), 0)      # idempotente
        a = self.c.decidir("ap-mv-visual", "ajustar", "trocar a cor do botão")
        self.assertEqual((a["estado"], a["nota"]), ("ajustar", "trocar a cor do botão"))
        with self.assertRaises(ErroMV):
            self.c.decidir("ap-mv-visual", "talvez")
        mvmod.HOJE = lambda: date(2026, 11, 30)
        self.assertTrue(any(x["atrasada"] for x in self.c.aprovacoes()))


class TestPerguntasCentrais(unittest.TestCase):
    def test_mesma_pergunta_uma_vez_e_resposta_reaproveitada(self):
        mv = MV(":memory:")
        mv_comandos.Comandos(mv)
        p1 = mv_comandos.perguntar(mv, "Data do hackathon: janeiro ou março?", ["Janeiro", "Março"], "sessao-instituto", ["instituto"])
        self.assertFalse(p1["ja_existia"])
        p2 = mv_comandos.perguntar(mv, "data do Hackathon - janeiro ou marco", [], "sessao-inovastem", ["inovastem"])
        self.assertTrue(p2["ja_existia"])
        self.assertEqual((p2["id"], p2["pedidos"], p2["aplica_em"]), (p1["id"], 2, ["inovastem", "instituto"]))
        mv_comandos.responder(mv, p1["id"], "Março")
        p3 = mv_comandos.perguntar(mv, "Data do hackathon: janeiro ou março?", origem="site")
        self.assertEqual((p3["aberta"], p3["resposta"]), (False, "Março"))
        self.assertEqual(len(mv_comandos.perguntas(mv, abertas=True)), 0)
        self.assertEqual(len(mv_comandos.perguntas(mv, sistema="inovastem")), 1)


class TestPerguntasSemComandos(unittest.TestCase):
    def test_banco_novo_sem_tabela(self):
        mv = MV(":memory:")
        self.assertEqual(mv_comandos.perguntas(mv, sistema="instituto"), [])
        self.assertFalse(mv_comandos.perguntar(mv, "Teste?", ["Sim"], "cli", ["instituto"])["ja_existia"])


class TestRedeLocal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mv = MV(Path(self.tmp.name) / "mv.db")

    def tearDown(self):
        self.mv.db.close()
        self.tmp.cleanup()

    def test_padrao_so_local_e_rede_com_senha(self):
        srv = mv_servidor.servir(self.mv, 0)
        self.assertEqual(srv.server_address[0], "127.0.0.1")
        srv.server_close()
        ips = mv_servidor.ips_locais()
        if not ips:
            self.skipTest("sem rede local nesta máquina")
        srv = mv_servidor.servir(self.mv, 0, rede_local=True)
        porta = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            ip = sorted(ips)[0]
            senha = (Path(self.tmp.name) / "senha-teste-rede.txt").read_text(encoding="utf-8").strip()
            self.assertGreaterEqual(len(senha), 10)
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(f"http://{ip}:{porta}/api/mv/saude")
            self.assertEqual(e.exception.code, 401)
            cab = {"Authorization": "Basic " + base64.b64encode(f"teste:{senha}".encode()).decode()}
            with urllib.request.urlopen(urllib.request.Request(f"http://{ip}:{porta}/api/mv/saude", headers=cab)) as r:
                self.assertIn("frentes", json.loads(r.read()))
            ruim = {"Authorization": "Basic " + base64.b64encode(b"teste:errada").decode()}
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(urllib.request.Request(f"http://{ip}:{porta}/api/mv/saude", headers=ruim))
            with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/mv/aprovacoes") as r:     # neste PC: sem senha
                self.assertTrue(len(json.loads(r.read())) >= 10)
            with urllib.request.urlopen(f"http://127.0.0.1:{porta}/vendor/three.min.js") as r:
                self.assertEqual(r.status, 200)
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(f"http://127.0.0.1:{porta}/vendor/../physis_hub/mv.py")
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
