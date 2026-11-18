#!/usr/bin/env python3
"""Coloca dentro da plataforma (painel.html) as bases de dados que ela usa sem servidor.

Por quê: a plataforma também funciona aberta como arquivo e na demonstração, sem servidor.
Então a base de certificações (sistema/physis-certificacoes.json) viaja dentro do HTML, num
bloco <script type="application/json" id="base-...">. Rodar de novo troca o bloco; não duplica.

    python ferramentas/embutir_bases.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PAINEL = RAIZ / "physis-hub" / "web" / "painel.html"
S = RAIZ / "sistema"
BASES = {"base-certificacoes": S / "physis-certificacoes.json", "base-plantas": S / "physis-plantas.json",
         "base-equipamentos": S / "physis-equipamentos.json",        # solar (módulos e inversores) e carga térmica
         "base-fatores-emissao": S / "physis-fatores-emissao.json",  # carbono (GHG Protocol)
         "base-evidencias": S / "physis-evidencias.json",            # certificação assistida
         "base-materiais": S / "physis-materiais.json",              # materiais e composições (SustainKit na plataforma, Certificações)
         "base-servidor-catalogo": S / "physis-servidor-catalogo.json",  # catálogo de módulos do Servidor verde
         "base-i18n-modulos": S / "physis-i18n-modulos.json"}        # inglês das telas dos módulos
# módulos de cálculo em arquivo próprio (testados à parte), embutidos como <script> no <head>
MODULOS = {"mod-avac": S / "physis-avac.js", "mod-saude": S / "physis-saude.js", "mod-juridico": S / "physis-juridico.js",
           "mod-turbinas": S / "physis-turbinas.js", "mod-solar": S / "physis-solar.js",
           "mod-ifc": S / "physis-ifc.js",                        # IFC no navegador (Mapeamento sem servidor)
           "mod-mapeamento": S / "physis-mapeamento.js",          # Mapeamento (camadas, BIM, planta solar); depois da solar
           "mod-circular-mapa": S / "physis-circular-mapa.js", "mod-cargatermica": S / "physis-cargatermica.js",
           "mod-metodologia": S / "physis-metodologia.js", "mod-sbn": S / "physis-sbn.js",
           "mod-carbono": S / "physis-carbono.js", "mod-relatorio-esg": S / "physis-relatorio-esg.js",
           "mod-evidencias": S / "physis-evidencias.js", "mod-parceiros": S / "physis-parceiros.js",
           "mod-ble": S / "physis-ble.js",
           "mod-mapa-local": S / "physis-mapa-local.js",          # mapa do local (como no receptor V6)
           "mod-aprendizado-ui": S / "physis-aprendizado-ui.js",  # o que o hub aprendeu + avisos de clima
           "mod-odf": S / "physis-odf.js",                        # ODT, ODS e PDF/A ao lado do "Baixar esta tela"
           "mod-secador": S / "physis-secador.js",                # aba Secador solar (em desenvolvimento)
           "mod-frota": S / "physis-frota.js",                    # aba Frota e combustível (em desenvolvimento)
           "mod-servidor-verde": S / "physis-servidor-verde.js",  # aba Servidor verde (em desenvolvimento)
           "mod-suporte-remoto": S / "physis-suporte-remoto.js",  # "Permitir suporte" (Minha conta da direção)
           "mod-intercambio": S / "physis-intercambio.js",        # intercâmbio com plataformas parceiras (Minha conta da direção)
           "mod-simulacao-casos": S / "simulacao-exemplos" / "casos.js",   # exemplos da Simulação (dados fictícios)
           "mod-simulacao": S / "physis-simulacao.js",
           "mod-fornecedores": S / "physis-fornecedores.js"}      # Fornecedores na sua região (aba Solar)            # aba Simulação + cartões nas outras abas


def bloco(ident: str, arq: Path) -> str:
    dados = json.loads(arq.read_text(encoding="utf-8"))            # confere que é JSON válido
    texto = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" id="{ident}">{texto}</script>'


def embutir(html: str) -> str:
    for ident, arq in BASES.items():
        if not arq.is_file():
            continue
        novo = bloco(ident, arq)
        # só o bloco que começa a linha: o texto do bloco citado num comentário de outro módulo não pode casar (15/11/2026)
        padrao = re.compile(rf'^<script type="application/json" id="{ident}">.*?</script>\n?', re.S | re.M)
        # sempre no <head>: o código da página lê a base assim que carrega, então ela tem de vir antes
        html = padrao.sub("", html)
        html = html.replace("</head>", novo + "\n</head>", 1)
    for ident, arq in MODULOS.items():
        if not arq.is_file():
            continue
        codigo = arq.read_text(encoding="utf-8")
        if re.search(r"(?i)</script", codigo):
            raise SystemExit(f"{arq.name} contém '</script' e não pode ir embutido")
        novo = f'<script id="{ident}">{codigo}</script>'
        padrao = re.compile(rf'^<script id="{ident}">.*?</script>\n?', re.S | re.M)
        html = padrao.sub("", html)
        html = html.replace("</head>", novo + "\n</head>", 1)
    return html


def main() -> None:
    antes = PAINEL.read_text(encoding="utf-8")
    depois = embutir(antes)
    if depois != antes:
        PAINEL.write_text(depois, encoding="utf-8", newline="")
    print("bases embutidas:", ", ".join(k for k, v in BASES.items() if v.is_file()) or "nenhuma")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
