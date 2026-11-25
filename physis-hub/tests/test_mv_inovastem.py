"""Bot InovaSTEM do M&A (mv_inovastem.py): o que chega no site vira alerta, sem dado pessoal."""
import sqlite3, tempfile, time, unittest
from pathlib import Path
from physis_hub.mv import MV
from physis_hub import mv_inovastem

class Bot(unittest.TestCase):
    def test_alerta_o_que_chegou(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "i.db"; c = sqlite3.connect(db)
            c.executescript("CREATE TABLE ino_proposta(tipo,titulo,email,estado,criado); CREATE TABLE com_mensagem(texto,criado);")
            c.execute("INSERT INTO ino_proposta VALUES('projeto','Horta','eva@x.example','publicado',?)", (time.time(),))
            c.execute("INSERT INTO com_mensagem VALUES('Olá, equipe',?)", (time.time(),)); c.commit(); c.close()
            mv = MV(":memory:")
            r = mv_inovastem.bot_inovastem(mv, db)
            self.assertEqual(r["novos"], 2)
            txt = " ".join(x[0] for x in mv.db.execute("SELECT texto FROM mv_alerta WHERE bot='inovastem'"))
            self.assertIn("Novo projeto: Horta", txt); self.assertNotIn("eva@x.example", txt)
            self.assertEqual(mv_inovastem.bot_inovastem(mv, db)["novos"], 0)      # segunda rodada: nada novo
            self.assertIn("aviso", mv_inovastem.bot_inovastem(mv, Path(d) / "nao.db"))

if __name__ == "__main__":
    unittest.main()
