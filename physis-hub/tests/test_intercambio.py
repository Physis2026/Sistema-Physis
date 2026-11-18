"""Intercâmbio entre plataformas (docs/INTERCAMBIO.md), com dois hubs de verdade no mesmo processo.

A = Physis Engineering; B = outra plataforma Physis (ex.: o Instituto). Cada um com o seu banco e o seu arquivo de chaves.
Protege:
1. Troca assinada: B publica uma peça da biblioteca, A puxa; o que chega fica pendente, não aparece até a direção aprovar.
2. Empurrar: A envia resumos de projeto; o campo pessoal (cliente) só sai com consentimento.
3. Chave errada, momento fora da janela e nonce repetido são recusados; conjunto fora da lista do parceiro também.
4. Registro com dado pessoal sem consentimento ou com SHA-256 alterado é recusado na chegada.
5. Só a direção mexe; a chave fica só no arquivo do servidor (nunca no banco nem na resposta do estado).
6. Endereço do parceiro: HTTPS, ou HTTP só da rede local/VPN.
"""
import json
import os
import secrets
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from physis_hub import intercambio as ic
from physis_hub import seguranca as seg
from physis_hub import servidor
from physis_hub.hub import Hub

SENHA = "frase-longa-da-direcao-1"


class DoisHubs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.antes = {k: os.environ.get(k) for k in ("PHYSIS_EXPOSTO", "PHYSIS_INTERCAMBIO_CHAVES", "PHYSIS_INTERCAMBIO_ID", "PHYSIS_INTERCAMBIO_LIMITE")}
        for k in cls.antes:
            os.environ.pop(k, None)
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        cls.h, cls.srv, cls.porta, cls.s = {}, {}, {}, {}
        ids = {"A": "physis-engenharia", "B": "instituto-teste"}
        cursos = [{"nome": "Introdução ao monitoramento", "link": "https://cursos.example/intro", "gratuito": True, "carga": 4,
                   "instrutor": "Fulana de Tal"}]
        for k in ("A", "B"):
            h = Hub(org=ids[k])
            inst = {"login": True, "intercambio_id": ids[k], "intercambio_chaves": str(t / f"chaves-{k}.json"), "cursos": cursos}
            srv = servidor.iniciar(h, 0, endereco="127.0.0.1", instancia=inst)
            h.criar_conta("Direção", f"dir@{k.lower()}.example", SENHA)
            adm = h.sessao(h.entrar(f"dir@{k.lower()}.example", SENHA)["token"])
            h.criar_conta("Equipe", f"eq@{k.lower()}.example", SENHA, adm["id"], papel="operador")
            cls.h[k], cls.srv[k], cls.porta[k] = h, srv, srv.server_address[1]
            for quem in ("dir", "eq"):
                tk = h.entrar(f"{quem}@{k.lower()}.example", SENHA)["token"]
                cls.s[(k, quem)] = ("physis_sessao=" + tk, seg.csrf_de(h, tk))
        cls.ids = ids
        # A cadastra B; B cadastra A (cada lado diz o que manda e o que aceita)
        cls.admin("A", "POST", "/api/intercambio/parceiro", {"id": ids["B"], "nome": "Instituto (teste)", "url": f"http://127.0.0.1:{cls.porta['B']}",
                                                            "enviar": ["cursos_catalogo", "projetos_resumo"], "receber": ["pecas_biblioteca"]}, ok=True)
        cls.admin("B", "POST", "/api/intercambio/parceiro", {"id": ids["A"], "nome": "Physis (teste)", "url": f"http://127.0.0.1:{cls.porta['A']}",
                                                            "enviar": ["pecas_biblioteca"], "receber": ["projetos_resumo"]}, ok=True)
        st, j = cls.admin("A", "POST", "/api/intercambio/parceiro/chave", {"id": ids["B"]}, ok=True)
        cls.chave = j["chave"]
        cls.admin("B", "POST", "/api/intercambio/parceiro/chave", {"id": ids["A"], "chave": cls.chave}, ok=True)

    @classmethod
    def tearDownClass(cls):
        for s in cls.srv.values():
            s.shutdown()
            s.server_close()
        cls.tmp.cleanup()
        for k, v in cls.antes.items():
            if v is not None:
                os.environ[k] = v

    @classmethod
    def pedir(cls, k, metodo, rota, corpo=None, cab=None, cru=None):
        dados = cru if cru is not None else (json.dumps(corpo).encode() if corpo is not None else None)
        req = urllib.request.Request(f"http://127.0.0.1:{cls.porta[k]}{rota}", data=dados, method=metodo,
                                     headers=dict({"Content-Type": "application/json"}, **(cab or {})))
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read() or b"{}"), r.headers
        except urllib.error.HTTPError as e:
            b = e.read()
            return e.code, (json.loads(b) if b.strip().startswith(b"{") else {}), e.headers

    @classmethod
    def admin(cls, k, metodo, rota, corpo=None, quem="dir", ok=False):
        cab = {}
        if quem:
            ck, tk = cls.s[(k, quem)]
            cab = {"Cookie": ck, "X-Physis-CSRF": tk}
        st, j, _ = cls.pedir(k, metodo, rota, corpo, cab)
        if ok:
            assert st == 200 and j.get("ok"), (rota, st, j)
        return st, j

    def assinado(self, k, metodo, rota, corpo=b"", chave=None, origem=None, momento=None, nonce=None):
        m = str(int(momento if momento is not None else time.time()))
        n = nonce or secrets.token_urlsafe(18)
        cab = {"X-Physis-Origem": origem or self.ids["A"], "X-Physis-Momento": m, "X-Physis-Nonce": n,
               "X-Physis-Assinatura": ic.assinar(chave or self.chave, metodo, rota, m, n, corpo)}
        return self.pedir(k, metodo, rota, cab=cab, cru=corpo if metodo == "POST" else None)

    # 1. puxar, pendente, aprovar
    def test_1_troca_assinada_pendente_ate_aprovar(self):
        sha = "ab" * 32
        self.admin("B", "POST", "/api/intercambio/publicar", {"dataset": "pecas_biblioteca", "registros": [
            {"id": "suporte-placa-v1", "dados": {"nome": "Suporte de placa", "licenca": "CERN-OHL-S-2.0", "material": "rPETG",
                                                 "arquivo_nome": "suporte.stl", "arquivo_sha256": sha, "arquivo_bytes": 123456,
                                                 "autor_publico": "Maria"}}]}, ok=True)
        st, j = self.admin("A", "POST", "/api/intercambio/puxar", {"parceiro": self.ids["B"], "dataset": "pecas_biblioteca"})
        self.assertEqual(st, 200, j)
        self.assertEqual((j["recebidos"], j["novos_pendentes"]), (1, 1))
        # pendente: não aparece para a equipe
        st, r = self.admin("A", "GET", "/api/intercambio/recebidos?dataset=pecas_biblioteca", quem="eq")
        self.assertEqual((st, r["registros"]), (200, []))
        st, e = self.admin("A", "GET", "/api/intercambio/estado")
        pend = [p for p in e["pendentes"] if p["dataset"] == "pecas_biblioteca"]
        self.assertEqual(len(pend), 1)
        self.assertEqual(pend[0]["dados"]["arquivo_sha256"], sha)
        self.assertNotIn("autor_publico", pend[0]["dados"], "nome público sem consentimento não sai")
        self.assertEqual(pend[0]["sha256"], ic.resumo_registro("pecas_biblioteca", "suporte-placa-v1", self.ids["B"], pend[0]["dados"]))
        # puxar de novo, igual, não duplica
        st, j = self.admin("A", "POST", "/api/intercambio/puxar", {"parceiro": self.ids["B"], "dataset": "pecas_biblioteca"})
        self.assertEqual(j["novos_pendentes"], 0)
        # aprovar: agora aparece
        self.admin("A", "POST", "/api/intercambio/revisar", {"ids": [pend[0]["seq"]], "decisao": "aprovar"}, ok=True)
        st, r = self.admin("A", "GET", "/api/intercambio/recebidos?dataset=pecas_biblioteca", quem="eq")
        self.assertEqual([x["id"] for x in r["registros"]], ["suporte-placa-v1"])
        # auditoria no registro encadeado do hub
        ops = [x["operacao"] for x in self.admin("A", "GET", "/api/intercambio/estado")[1]["registro"]]
        self.assertIn("recebido (puxado daqui)", ops)
        self.assertIn("importacao aprovada", ops)
        self.assertTrue(self.h["A"].verificar_cadeia()[0])

    # 2. empurrar; LGPD
    def test_2_empurrar_sem_dado_pessoal_sem_consentimento(self):
        self.admin("A", "POST", "/api/intercambio/publicar", {"dataset": "projetos_resumo", "registros": [
            {"id": "p1", "dados": {"titulo": "Reúso de água", "resumo": "Cisterna e reúso", "uf": "RJ", "cliente": "Fazenda Exemplo"}},
            {"id": "p2", "dados": {"titulo": "Solar", "resumo": "Usina pequena", "uf": "DF", "cliente": "Escola Modelo"}, "consentimento": True}]}, ok=True)
        st, j = self.admin("A", "POST", "/api/intercambio/enviar", {"parceiro": self.ids["B"], "dataset": "projetos_resumo"})
        self.assertEqual(st, 200, j)
        self.assertEqual((j["enviados"], j["pessoais_retirados"]), (2, 1))
        pend = {p["id"]: p for p in self.admin("B", "GET", "/api/intercambio/estado")[1]["pendentes"] if p["dataset"] == "projetos_resumo"}
        self.assertNotIn("cliente", pend["p1"]["dados"])
        self.assertEqual((pend["p2"]["dados"]["cliente"], pend["p2"]["dados"]["consentimento"]), ("Escola Modelo", True))
        self.assertEqual(self.admin("B", "GET", "/api/intercambio/recebidos?dataset=projetos_resumo")[1]["registros"], [])
        # campo fora da lista e e-mail escondido num campo aberto: nada é publicado
        st, j = self.admin("A", "POST", "/api/intercambio/publicar", {"dataset": "projetos_resumo", "registros": [{"id": "p3", "dados": {"titulo": "x", "cpf": "1"}}]})
        self.assertEqual(st, 400)
        st, j = self.admin("A", "POST", "/api/intercambio/publicar", {"dataset": "projetos_resumo", "registros": [{"id": "p4", "dados": {"titulo": "contato fulano@exemplo.com"}}]})
        self.assertEqual(st, 400)

    # 3. assinatura, repetição, janela, conjunto não permitido
    def test_3_chave_errada_repeticao_e_conjunto_nao_permitido(self):
        rota = "/api/intercambio/v1/oferta"
        self.assertEqual(self.assinado("B", "GET", rota)[0], 200)
        self.assertEqual(self.assinado("B", "GET", rota, chave="x" * 40)[0], 401)
        self.assertEqual(self.assinado("B", "GET", rota, momento=time.time() - 3600)[0], 401)
        self.assertEqual(self.assinado("B", "GET", rota, origem="desconhecido")[0], 401)
        self.assertEqual(self.pedir("B", "GET", rota)[0], 401, "sem assinatura")
        n = secrets.token_urlsafe(18)
        self.assertEqual(self.assinado("B", "GET", rota, nonce=n)[0], 200)
        self.assertEqual(self.assinado("B", "GET", rota, nonce=n)[0], 409, "nonce repetido")
        # B não manda cursos para A (a lista de B só tem pecas_biblioteca)
        self.assertEqual(self.assinado("B", "GET", "/api/intercambio/v1/dados/cursos_catalogo")[0], 403)
        # A tenta empurrar cursos: A permite, B não aceita
        st, j = self.admin("A", "POST", "/api/intercambio/enviar", {"parceiro": self.ids["B"], "dataset": "cursos_catalogo"})
        self.assertEqual((st, j["status"]), (400, 403))
        # A não puxa o que não está na própria lista
        self.assertEqual(self.admin("A", "POST", "/api/intercambio/puxar", {"parceiro": self.ids["B"], "dataset": "lotes_integridade"})[0], 400)
        ops = [x.get("motivo") for x in self.admin("B", "GET", "/api/intercambio/estado")[1]["registro"]]
        self.assertIn("assinatura não confere", ops)
        self.assertIn("nonce repetido (repetição)", ops)

    # 4. o que chega com problema
    def test_4_registro_pessoal_sem_consentimento_ou_alterado_e_recusado(self):
        A = self.ids["A"]
        bom = ic.registro("projetos_resumo", "q1", A, {"titulo": "Bom"})
        pessoal = ic.registro("projetos_resumo", "q2", A, {"titulo": "Com cliente", "cliente": "Fulano"})
        alterado = dict(ic.registro("projetos_resumo", "q3", A, {"titulo": "Original"}), dados={"titulo": "Mudado"})
        pk = {"esquema": ic.ESQUEMA, "origem": A, "destino": self.ids["B"], "dataset": "projetos_resumo", "gerado_em": "x",
              "registros": [bom, pessoal, alterado]}
        st, j, h = self.assinado("B", "POST", "/api/intercambio/v1/receber/projetos_resumo", json.dumps(pk).encode())
        self.assertEqual(st, 200, j)
        self.assertEqual((j["recebidos"], len(j["recusados"])), (1, 2))
        self.assertTrue(h.get("X-Physis-Assinatura"), "resposta assinada")
        pk2 = dict(pk, esquema="outro/9")
        self.assertEqual(self.assinado("B", "POST", "/api/intercambio/v1/receber/projetos_resumo", json.dumps(pk2).encode())[0], 400)

    # 5. papéis e segredo
    def test_5_so_direcao_e_chave_fora_do_banco(self):
        self.assertEqual(self.admin("A", "GET", "/api/intercambio/estado", quem="eq")[0], 403)
        self.assertEqual(self.admin("A", "GET", "/api/intercambio/estado", quem=None)[0], 401)
        self.assertEqual(self.admin("A", "POST", "/api/intercambio/parceiro", {"id": "x-y", "nome": "X", "url": "http://203.0.113.5"}, quem="eq")[0], 403)
        st, e = self.admin("A", "GET", "/api/intercambio/estado")
        self.assertNotIn(self.chave, json.dumps(e))
        self.assertTrue([p for p in e["parceiros"] if p["id"] == self.ids["B"]][0]["tem_chave"])
        tudo = "\n".join(self.h["A"]._db.iterdump())
        self.assertNotIn(self.chave, tudo)
        self.assertIn(self.chave, (Path(self.tmp.name) / "chaves-A.json").read_text(encoding="utf-8"))

    def test_6_endereco_do_parceiro(self):
        self.assertIsNone(ic.endereco_permitido("https://instituto.example"))
        self.assertIsNone(ic.endereco_permitido("http://100.101.1.2:8700"))       # VPN
        self.assertIsNone(ic.endereco_permitido("http://192.168.0.10:8700"))
        self.assertIsNotNone(ic.endereco_permitido("http://203.0.113.5:8700"))
        self.assertIsNotNone(ic.endereco_permitido("http://instituto.example"))
        self.assertIsNotNone(ic.endereco_permitido("ftp://x"))
        st, j = self.admin("A", "POST", "/api/intercambio/parceiro", {"id": "fora-x", "nome": "Fora", "url": "http://203.0.113.5"})
        self.assertEqual(st, 400)


class Contrato(unittest.TestCase):
    def test_limpar_e_resumo(self):
        d, fora = ic.limpar("cursos_catalogo", {"nome": "Curso", "instrutor": "Fulana", "senha": "x"}, False)
        self.assertEqual((d, fora), ({"nome": "Curso"}, ["instrutor"]))
        d, fora = ic.limpar("cursos_catalogo", {"nome": "Curso", "instrutor": "Fulana"}, True)
        self.assertEqual(d, {"nome": "Curso", "instrutor": "Fulana", "consentimento": True})
        r = ic.registro("cursos_catalogo", "c1", "physis", {"nome": "Curso"})
        self.assertEqual(r["sha256"], ic.sha256(ic.canonico({"dataset": "cursos_catalogo", "id": "c1", "origem": "physis", "dados": {"nome": "Curso"}})))
        self.assertEqual(len(ic.assinar("k" * 32, "GET", "/x", "1", "n" * 16, b"")), 64)


if __name__ == "__main__":
    unittest.main()
