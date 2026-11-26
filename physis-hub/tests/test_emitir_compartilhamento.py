"""Pacote de compartilhamento com a equipe (26/11/2026): os testes que barram a emissão."""
import importlib.util, io, json, tempfile, unittest, zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("emitir_comp", RAIZ / "ferramentas" / "emitir_compartilhamento.py")
ec = importlib.util.module_from_spec(spec); spec.loader.exec_module(ec)


class Comp(unittest.TestCase):
    def setUp(self):
        ec.L.clear(); ec.F[0] = 0; ec.A[0] = 0; self.d = Path(tempfile.mkdtemp())

    def zip(self, arqs):
        z = self.d / "k.zip"
        with zipfile.ZipFile(z, "w") as zz:
            for n, t in arqs.items(): zz.writestr(n, t)
        return z

    def test_barra_segredo_e_arquivo_proibido(self):
        ec.conferir_zip(self.zip({"k/a.py": 'token = "abcdef123456"', "k/secrets.h": "x", "k/dados.db": "x"}))
        self.assertEqual(ec.F[0], 3)

    def test_html_com_internet_falha(self):
        ec.conferir_zip(self.zip({"k/p.html": '<html><title>x</title><script src="https://cdn.x/y.js"></script></html>'}))
        self.assertEqual(ec.F[0], 1)

    def test_teste_e_exemplo_nao_sao_segredo(self):
        ec.conferir_zip(self.zip({"k/tests/test_a.py": 'SENHA = "senha-bem-longa"', "k/s.example.yaml": 'password: "SENHA_DA_REDE"'}))
        self.assertEqual(ec.F[0], 0)

    def test_manifesto_confere(self):
        z = self.zip({"k/LEIA-ME.md": "a", "k/FICHA_REVISAO.md": "b", "k/x.txt": "conteudo"})
        ec.conferir_zip(z, {"arquivos": {"x.txt": "0" * 64}})
        self.assertEqual(ec.F[0], 1)


if __name__ == "__main__":
    unittest.main()
