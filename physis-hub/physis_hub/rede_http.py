"""Servidor HTTP com porta exclusiva (todas as plataformas) e fila de conexões maior.

Por quê (verificação no servidor Windows, 24/11/2026): o http.server liga SO_REUSEADDR. No Windows essa opção deixa
um SEGUNDO processo ocupar a MESMA porta sem erro; os dois passam a disputar as conexões (dois "mv_cli servir"
alternando na 8710). Aqui, no Windows, a porta é exclusiva (SO_EXCLUSIVEADDRUSE): o segundo processo falha logo
ao subir, com "porta em uso", em vez de rodar escondido. No Linux, SO_REUSEADDR continua (só libera a porta
em TIME_WAIT; lá não permite duas escutas).
"""
from __future__ import annotations

import os
import socket
from http.server import ThreadingHTTPServer


class ServidorHTTP(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"
    # Fila de conexões à espera de aceite: o padrão (5) causava p99 de ~1 s acima de 10 acessos simultâneos.
    request_queue_size = max(5, int(os.environ.get("PHYSIS_FILA_CONEXOES") or 128))
    daemon_threads = True

    def server_bind(self):
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()
