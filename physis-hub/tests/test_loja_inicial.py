"""Loja de um site Physis novo (15/11/2026: "para as lojas as opções de compra não estão aparecendo").

Um hub novo com o catálogo inicial (sistema/loja-catalogo-inicial.json, gerado por ferramentas/gerar_loja_catalogo.py)
publica sozinho os itens à venda ao ligar; o catálogo público traz os preços decididos e nunca item em desenvolvimento;
um catálogo que a equipe já publicou não é sobrescrito; o pacote do site leva o arquivo.
"""
import json
import re
import shutil
import tempfile
import unittest
import urllib.request
from pathlib import Path

from physis_hub import servidor
from physis_hub.hub import Hub

RAIZ = Path(__file__).resolve().parents[2]
CAT = RAIZ / "sistema" / "loja-catalogo-inicial.json"
PAINEL = RAIZ / "physis-hub" / "web" / "painel.html"
NO_REPO = CAT.is_file() and PAINEL.is_file()


def novo_hub():
    h = Hub(":memory:")
    h.instancia = {}
    return h


@unittest.skipUnless(NO_REPO, "só no repositório")
class CatalogoInicial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = json.loads(CAT.read_text(encoding="utf-8"))
        cls.painel = PAINEL.read_text(encoding="utf-8")

    def test_arquivo_em_dia_com_o_painel(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("g", RAIZ / "ferramentas" / "gerar_loja_catalogo.py")
        g = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(g)
        self.assertEqual(g.gerar(), self.cat, "rode python ferramentas/gerar_loja_catalogo.py")

    def test_precos_decididos_e_so_itens_prontos(self):
        it = self.cat["itens"]
        self.assertEqual(it["solar"]["preco"], 300)
        self.assertEqual(it["consultoria-pers"]["preco"], 5000)
        certs = [k for k in it if k.startswith("cert-")]
        self.assertEqual(len(certs), len(Hub.CERTIFICACOES_LOJA))
        self.assertTrue(all(it[k]["preco"] == 750 for k in certs))
        self.assertEqual([(n["n"], n["preco"], n["a_partir_de"]) for n in self.cat["precos_niveis_certificacao"]],
                         [(1, 750, True), (2, 5000, False), (3, 30000, True), (4, 50000, True)])
        self.assertTrue(all(v["st"] == "func" for v in it.values()))
        self.assertIn("scada", self.cat["fora"])                               # supervisão está em simulação
        for dev in ("P23", "servidor-verde", "simulacao", "mapeamento", "P5", "P15"):
            self.assertNotIn(dev, it)
        sob = [k for k, v in it.items() if v["preco"] is None]
        self.assertTrue(sob and all(not k.startswith("cert-") and k not in ("solar", "consultoria-pers") for k in sob))

    def test_hub_novo_publica_e_nao_sobrescreve(self):
        h = novo_hub()
        r = h.loja_semear_inicial(self.cat)
        self.assertEqual(r["semeado"], len(self.cat["itens"]))
        pub = h.loja_catalogo()["itens"]
        self.assertEqual(set(pub), set(self.cat["itens"]))
        # a equipe muda o preço da solar e publica; ligar de novo não mexe
        h.loja_gravar("solar", {"preco": 350}, "equipe")
        h.loja_revisar("solar", "equipe")
        h.loja_publicar("solar", "equipe")
        self.assertEqual(h.loja_semear_inicial(self.cat)["semeado"], 0)
        self.assertEqual(h.loja_catalogo()["itens"]["solar"]["preco"], 350)
        # item em desenvolvimento no arquivo: recusado
        h2 = novo_hub()
        r2 = h2.loja_semear_inicial({"itens": {"P23": {"st": "dev", "nome": "Secador"}, "solar": {"st": "func", "preco": 300}}})
        self.assertIn("P23", r2["recusados"])
        self.assertEqual(set(h2.loja_catalogo()["itens"]), {"solar"})

    @staticmethod
    def _tem_registro(h):
        try:
            h._db.execute("SELECT 1 FROM registro LIMIT 1")
            return True
        except Exception:
            return False

    def test_pacote_do_site_leva_o_arquivo_e_o_servidor_publica(self):
        self.assertIn('if org == "physis-site":', (RAIZ / "physis-hub" / "montar.py").read_text(encoding="utf-8"))
        tmp = Path(tempfile.mkdtemp(prefix="loja-"))
        try:
            arq = tmp / "loja-catalogo-inicial.json"
            shutil.copy2(CAT, arq)
            h = novo_hub()
            self.assertEqual(servidor.semear_loja(h, arq)["semeado"], len(self.cat["itens"]))
            srv = servidor.iniciar(h, 0, endereco="127.0.0.1", instancia={"login": True, "modulos": ["gestao"]})
            try:
                porta = srv.server_address[1]
                j = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/loja/catalogo", timeout=5).read())
                itens = j["itens"]
                self.assertEqual(itens["solar"]["preco"], 300)
                self.assertEqual(itens["cert-leed"]["preco"], 750)
                self.assertIn("consultoria-pers", itens)
                for dev in ("P23", "servidor-verde", "scada"):
                    self.assertNotIn(dev, itens)
            finally:
                srv.shutdown()
                srv.server_close()
            self.assertIsNone(servidor.semear_loja(novo_hub(), tmp / "nao-existe.json"))     # instalação de cliente: nada
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
