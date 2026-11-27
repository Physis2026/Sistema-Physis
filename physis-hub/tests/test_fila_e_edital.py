"""Fila do Claude em arquivo e conta que vira edital (decisões de 23/11/2026)."""
import tempfile
import time
import unittest
from pathlib import Path

from physis_hub import mv_clientes, mv_comandos, mv_vigia
from physis_hub.mv import MV


class Fila(unittest.TestCase):
    def test_arquivo_e_alerta_depois_de_24h(self):
        mv = MV(":memory:")
        c = mv_comandos.Comandos(mv)
        p = c._pedido("claude", "Ler os anexos e propor a ficha")         # pedido antigo, de antes do bot autônomo
        mv.db.execute("UPDATE mv_pedido_bot SET criado=? WHERE id=?", (time.time() - 30 * 3600, p["id"]))
        d = Path(tempfile.mkdtemp())
        r = mv_vigia.exportar_fila(mv, d)
        self.assertEqual(r["fila"], 1)
        self.assertIn("Ler os anexos", (d / "fila-pedidos.md").read_text(encoding="utf-8"))
        self.assertTrue(any(a["tipo"] == "fila_parada" for a in mv.alertas()))
        from physis_hub import mv_autonomo
        self.assertEqual(mv_autonomo.processar_fila(mv)["respondidos"], 1)     # o bot responde sozinho, sem Claude
        self.assertEqual(c.pedido(p["id"])["estado"], "rascunho")
        self.assertEqual(mv_vigia.exportar_fila(mv, d)["fila"], 0)


class ContaParaEdital(unittest.TestCase):
    def test_move_sem_apagar(self):
        mv = MV(":memory:")
        cl = mv_clientes.Clientes(mv)
        cl.salvar({"id": "captacao-municipal-2027", "nome": "Captação municipal 2027", "tipo": "futuro"})
        cl.analisar("captacao-municipal-2027")
        r = cl.para_edital("captacao-municipal-2027")
        self.assertEqual(r["edital"], "ed-captacao-municipal-2027")
        e = mv.db.execute("SELECT titulo, etapa FROM mv_edital WHERE id=?", (r["edital"],)).fetchone()
        self.assertEqual(tuple(e), ("Captação municipal 2027", "triagem"))
        self.assertEqual(cl.conta("captacao-municipal-2027")["estado"], "arquivada")
        ped = mv.db.execute("SELECT origem, comando FROM mv_pedido_bot WHERE estado IN ('na_fila','rascunho')").fetchone()
        self.assertEqual(ped[0], "edital:ed-captacao-municipal-2027")
        self.assertIn("ficha do edital", ped[1])
