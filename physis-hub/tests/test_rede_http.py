"""Porta exclusiva e fila de conexões (physis_hub/rede_http.py)."""
import os
import socket
import unittest

from physis_hub.rede_http import ServidorHTTP
from http.server import BaseHTTPRequestHandler


class PortaExclusiva(unittest.TestCase):
    def test_segundo_processo_na_mesma_porta_falha(self):
        a = ServidorHTTP(("127.0.0.1", 0), BaseHTTPRequestHandler)
        try:
            porta = a.server_address[1]
            with self.assertRaises(OSError):
                ServidorHTTP(("127.0.0.1", porta), BaseHTTPRequestHandler).server_close()
        finally:
            a.server_close()

    def test_fila_e_reuso(self):
        self.assertGreaterEqual(ServidorHTTP.request_queue_size, 128 if not os.environ.get("PHYSIS_FILA_CONEXOES") else 5)
        self.assertEqual(ServidorHTTP.allow_reuse_address, os.name != "nt")
        if os.name == "nt":
            self.assertTrue(hasattr(socket, "SO_EXCLUSIVEADDRUSE"))


if __name__ == "__main__":
    unittest.main()
