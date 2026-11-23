#!/usr/bin/env python3
"""Instalador do Physis M&A sem .bat: duplo clique neste arquivo (abre com o Python, que é assinado pela Python Software
Foundation). Use quando o Windows bloquear o INSTALAR-PHYSIS.bat. Faz exatamente o mesmo (ferramentas/instalar_tudo.py)."""
import runpy
import sys
from pathlib import Path

aqui = Path(__file__).resolve().parent
sys.argv = [str(aqui / "ferramentas" / "instalar_tudo.py"), *sys.argv[1:]]
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
except SystemExit:
    pass
input("\nAperte Enter para fechar...")
