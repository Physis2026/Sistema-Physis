"""Editais no Physis M&V (physis_hub/mv_editais.py; doc 31): importação idempotente que preserva o trabalho feito, necessidades
geradas (documentos exigidos, exigências formais, parceiro, documentos-padrão), etapas válidas e planilha ODS."""
import io
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path

from physis_hub import mv as mvmod
from physis_hub import mv_editais, mv_servidor
from physis_hub.mv import MV, ErroMV

CSV = ("chave;titulo;financiador;link;tipo;prazo;status;frente_mais_aderente;aderencia;fonte_verificada;via_parceria;perfil_parceiro;"
       "documentos_exigidos;exigencias_formais;criterios_avaliacao_pesos\n"
       "bndes;BNDES Garagem;BNDES;https://x;aceleracao;2026-11-30;aberto;engineering;alta;sim;nao;;Pitch|Vídeo 4 min;Cadastro;\n"
       "iki;IKI Small Grants;IKI;https://y;edital;2027-01-08;aberto;instituto;media;nao;sim;OSC com 3+ anos;;3 anos de operação;\n"
       "sic;Sicoob;Sicoob;https://z;edital;2026-12-31;aberto;nenhuma;inelegivel;sim;nao;;;;\n")


class TestEditais(unittest.TestCase):
    def setUp(self):
        mvmod.HOJE = lambda: date(2026, 11, 18)
        self.mv = MV(":memory:")
        self.ed = mv_editais.Editais(self.mv)
        self.tmp = tempfile.TemporaryDirectory()
        self.arq = Path(self.tmp.name) / "b.csv"
        self.arq.write_text(CSV, encoding="utf-8-sig")

    def tearDown(self):
        self.tmp.cleanup()

    def test_importa_e_gera_necessidades(self):
        self.assertEqual(self.ed.importar_csv(self.arq), {"novos": 3, "atualizados": 0})
        ls = {d["titulo"]: d for d in self.ed.listar()}
        b, i, s = ls["BNDES Garagem"], ls["IKI Small Grants"], ls["Sicoob"]
        self.assertEqual((b["etapa"], b["dias"]), ("decidir", 12))
        self.assertEqual(s["etapa"], "arquivada")
        itens = [x["item"] for x in b["necessidades"]]
        self.assertIn("Pitch", itens)
        self.assertIn("Revisão final e autorização da dona antes do envio", itens)
        self.assertTrue(any(x["origem"] == "parceria" and "OSC com 3+ anos" in x["item"] for x in i["necessidades"]))

    def test_reimportar_preserva_trabalho(self):
        self.ed.importar_csv(self.arq)
        d = next(x for x in self.ed.listar() if x["titulo"] == "BNDES Garagem")
        nid = d["necessidades"][0]["id"]
        self.ed.atualizar(d["id"], {"etapa": "preparar", "responsavel": "Marzia", "necessidade": {"id": nid, "feito": True}})
        self.ed.atualizar(d["id"], {"pergunta": "Faixa Tração ou Criação?"})
        self.assertEqual(self.ed.importar_csv(self.arq), {"novos": 0, "atualizados": 3})
        d2 = next(x for x in self.ed.listar() if x["id"] == d["id"])
        self.assertEqual((d2["etapa"], d2["responsavel"]), ("preparar", "Marzia"))
        self.assertTrue(d2["necessidades"][0]["feito"])
        self.assertGreater(d2["pronto_pct"], 0)
        self.assertEqual(len(d2["perguntas"]), 1)
        with self.assertRaises(ErroMV):
            self.ed.atualizar(d["id"], {"etapa": "talvez"})

    def test_planilha_ods(self):
        self.ed.importar_csv(self.arq)
        d = self.ed.listar()[0]
        self.ed.atualizar(d["id"], {"etapa": "preparar"})
        b, tipo, nome = mv_servidor.exportar(self.mv, "editais", "ods")
        self.assertIn("spreadsheet", tipo)
        self.assertTrue(nome.endswith(".ods"))
        self.assertIn(b"Necessidades por proposta", zipfile.ZipFile(io.BytesIO(b)).read("content.xml"))


if __name__ == "__main__":
    unittest.main()
