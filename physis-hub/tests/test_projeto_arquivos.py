"""Arquivos do projeto do Início guardados no servidor (26/11/2026)."""
import tempfile, unittest
from pathlib import Path
from physis_hub.projeto_arquivos import ProjetoArquivos


class Arquivos(unittest.TestCase):
    def setUp(self):
        self.pa = ProjetoArquivos(Path(tempfile.mkdtemp()) / "pa")

    def test_salva_lista_le_apaga(self):
        r = self.pa.salvar("planta.png", b"\x89PNG...", "ana")
        self.assertTrue(r["ok"]); self.assertEqual(self.pa.ler(r["id"]), ("planta.png", b"\x89PNG..."))
        self.assertEqual([x["nome"] for x in self.pa.listar()], ["planta.png"])
        self.assertTrue(self.pa.apagar(r["id"])); self.assertEqual(self.pa.listar(), [])

    def test_recusa(self):
        self.assertFalse(self.pa.salvar("virus.exe", b"x")["ok"])
        self.assertFalse(self.pa.salvar("a.pdf", b"")["ok"])
        self.assertEqual(self.pa.salvar("../../etc/passwd.txt", b"x")["nome"], "passwd.txt")
        self.assertIsNone(self.pa.ler("../x")); self.assertFalse(self.pa.apagar("../x"))


if __name__ == "__main__":
    unittest.main()
