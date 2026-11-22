#!/usr/bin/env python3
"""Mantém as cópias embutidas iguais ao original. Rode depois de mudar um original.

    python ferramentas/sincronizar.py            # aplica
    python ferramentas/sincronizar.py --conferir # só confere (para testes e CI); sai com erro se houver diferença

Por que existe: os programas da Physis são arquivos HTML únicos, que funcionam sem internet.
Por isso o exportador de documentos (sistema/physis-exportar.js) vai copiado dentro de cada um,
e alguns programas vão embutidos em base64 dentro da plataforma (physis-hub/web/painel.html).
Copiar à mão gera versões diferentes; este script faz a cópia sempre igual ao original.

O que faz:
1. Troca o bloco do exportador em cada HTML pelo conteúdo de sistema/physis-exportar.js.
   Também os módulos compartilhados em blocos <script id="..."> (BLOCOS): preferências, conta, ODF, parceiros, pontes.
2. Corrige textos pedidos pela Physis nos programas (ex.: o SCADA não se chama mais
   "fazenda net zero").
3. Refaz as cópias em base64 (PROGRAMAS) dentro da plataforma com o mesmo tratamento.
"""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ORIGEM = RAIZ / "sistema" / "physis-exportar.js"
INICIO = "/* physis-exportar.js v"
FIM = '})(typeof window !== "undefined" ? window : this);'
ALVOS = [
    RAIZ / "physis-hub" / "docs" / "physis-exportar.js",
    RAIZ / "sistema" / "gestao-interna-physis.html",
    RAIZ / "sistema" / "physis-scada-demo.html",
    RAIZ / "physis-hub" / "web" / "consultoria.html",
    RAIZ / "sistema" / "SustainKit_Definitivo.html",
    RAIZ / "modulos" / "planejador" / "planejador-physis.html",
    RAIZ / "physis-hub" / "web" / "painel.html",
    # barra única de preferências também nestas (15/11/2026)
    RAIZ / "physis-hub" / "web" / "documento.html",
    RAIZ / "physis-hub" / "web" / "municipio.html",
    RAIZ / "app-nativo" / "site" / "baixar.html",
    RAIZ / "physis-hub" / "web" / "mv.html",          # Physis M&A (20/11/2026): mesma barra de preferências e acessibilidade
    RAIZ / "modulos" / "modelagem3d" / "modelagem-3d.html",  # módulo de modelagem 3D (22/11/2026): ferramentas que saíram do M&A
    RAIZ / "modulos" / "estermic" / "estermic-avac.html",    # painel Desenvolvimento (22/11/2026)
]
# A "Tela do cliente" (sistema/physis-tela-cliente.html) saiu em 15/11/2026: tudo o que ela fazia está nas abas da plataforma.
PLATAFORMA = RAIZ / "physis-hub" / "web" / "painel.html"
# Textos que a Physis pediu para mudar (14/11/2026): o SCADA é da organização do cliente, não de uma "fazenda net zero".
TROCAS = [
    ("Physis · SCADA · fazenda net zero", "Physis · SCADA"),
    ("SCADA · fazenda net zero", "SCADA"),
    ("SCADA · net zero farm", "SCADA"),
    ("Fazenda simulada · o dado não é real", "Simulação · o dado não é real"),
    ("Simulated farm · the data is not real", "Simulation · the data is not real"),
]


def trocar_exportar(texto: str, novo: str) -> str:
    i = texto.find(INICIO)
    if i < 0:
        return texto
    j = texto.find(FIM, i)
    if j < 0:
        raise SystemExit("bloco do exportador sem fim reconhecível")
    return texto[:i] + novo + texto[j + len(FIM):]


# Outros originais embutidos como bloco <script id="..."> (o conteúdo do bloco é o arquivo, igual).
# Só troca o bloco que já existe na página (ninguém ganha um módulo que não usa).
BLOCOS = {
    "gp-ponte": RAIZ / "sistema" / "gestao-ponte.js",
    # Preferências (idioma, tema, conforto, acessibilidade): UM módulo para todas as telas desde 15/11/2026.
    "physis-preferencias": RAIZ / "sistema" / "physis-preferencias.js",
    "physis-conta": RAIZ / "sistema" / "physis-conta.js",          # conta e segurança (CSRF, 2FA, convites, chaves)
    "physis-odf": RAIZ / "sistema" / "physis-odf.js",              # ODT, ODS, PDF/A e "compartilhar para comentários"
    "physis-parceiros": RAIZ / "sistema" / "physis-parceiros.js",  # profissionais parceiros
    "physis-fornecedores": RAIZ / "sistema" / "physis-fornecedores.js",  # fornecedores e equipamentos (Gestão)
    "pc-ponte": RAIZ / "sistema" / "physis-ponte-cliente.js",      # ponte da plataforma com o servidor (dados do cliente)
    # contas comuns (Lei 14.300, plano inclinado, baterias, cisterna, calhas, aquecimento solar) com a base de premissas
    "physis-calc-comum": RAIZ / "sistema" / "physis-calc-comum.js",
    # painel "Desenvolvimento" (22/11/2026): igual em todos os módulos, plataformas internas e Gestão; fonte única = M&A
    "physis-desenvolvimento": RAIZ / "sistema" / "physis-desenvolvimento.js",
}
# Nome antigo do bloco de preferências (px-preferencias v1, a segunda implementação que existia até 15/11/2026):
# vira o bloco do módulo único na primeira rodada.
ANTIGOS = {"px-preferencias": "physis-preferencias"}


def trocar_blocos(texto: str) -> str:
    for velho, novo in ANTIGOS.items():
        texto = re.sub(r'<script id="%s">\n.*?</script>' % re.escape(velho), '<script id="%s">\n</script>' % novo, texto, count=1, flags=re.S)
    for ident, fonte in BLOCOS.items():
        abre = f'<script id="{ident}">\n'
        i = texto.find(abre)
        if i < 0:
            continue
        j = texto.find("</script>", i)
        texto = texto[:i + len(abre)] + fonte.read_text(encoding="utf-8").replace("\r\n", "\n") + texto[j:]
    return texto


NUCLEO = RAIZ / "sistema" / "physis-nucleo.js"
NUCLEO_MARCA = "/* physis-nucleo.js v1 — embutido, verbatim */\n"


def trocar_nucleo(texto: str) -> str:
    """Cópia do contrato de dados (physis-nucleo.js) embutida na Gestão: sempre igual ao original."""
    i = texto.find(NUCLEO_MARCA)
    if i < 0:
        return texto
    j = texto.find("</script>", i)
    # "</script" dentro do código (num comentário de exemplo) fecharia a tag antes da hora: vai escapado.
    novo = NUCLEO.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n").replace("</script", "<\\/script") + "\n\n"
    return texto[:i + len(NUCLEO_MARCA)] + novo + texto[j:]


def tratar(texto: str, novo: str) -> str:
    texto = trocar_nucleo(trocar_blocos(trocar_exportar(texto, novo)))
    for a, b in TROCAS:
        texto = texto.replace(a, b)
    return texto


# Programas embutidos que são cópia exata de um arquivo: a cópia é refeita a partir do arquivo.
# (Desde 14/11/2026 a "Tela do cliente" também: os ajustes que só existiam na cópia foram levados ao original.)
FONTES = {
    "sustainkit": RAIZ / "sistema" / "SustainKit_Definitivo.html",
    "supervisao": RAIZ / "sistema" / "physis-scada-demo.html",
    # Planejador embutido desde 15/11/2026: abre sem o computador central, como o SustainKit e o SCADA
    "planejador": RAIZ / "modulos" / "planejador" / "planejador-physis.html",
}


def tratar_programas(html: str, novo: str) -> str:
    m = re.search(r"const PROGRAMAS = \{(.*?)\};\n", html, re.S)
    if not m:
        return html
    def um(mm: re.Match) -> str:
        fonte = FONTES.get(mm.group(1))
        bruto = fonte.read_text(encoding="utf-8") if fonte else base64.b64decode(mm.group(2)).decode("utf-8")
        return f'{mm.group(1)}:"' + base64.b64encode(tratar(bruto, novo).encode("utf-8")).decode("ascii") + '"'
    corpo = re.sub(r'(\w+):"([A-Za-z0-9+/=]+)"', um, m.group(1))
    return html[:m.start(1)] + corpo + html[m.end(1):]


CALC_COMUM = RAIZ / "sistema" / "physis-calc-comum.js"
PREMISSAS = RAIZ / "sistema" / "physis-premissas.json"


def premissas_no_calc_comum(conferir: bool) -> bool:
    """Copia sistema/physis-premissas.json para o bloco PREMISSAS de physis-calc-comum.js. Devolve True se mudou."""
    if not (CALC_COMUM.is_file() and PREMISSAS.is_file()):
        return False
    import json
    base = json.loads(PREMISSAS.read_text(encoding="utf-8"))
    # só as premissas (o catálogo de normas fica no JSON: tem notas sobre edições substituídas que os programas não citam)
    dados = {k: base[k] for k in ("versao", "atualizado", "premissas") if k in base}
    texto = CALC_COMUM.read_text(encoding="utf-8")
    novo = re.sub(r"(/\*PREMISSAS-INICIO\*/\nvar PREMISSAS = ).*?(;\n/\*PREMISSAS-FIM\*/)",
                  lambda m: m.group(1) + json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + m.group(2),
                  texto, count=1, flags=re.S)
    if novo != texto and not conferir:
        CALC_COMUM.write_text(novo, encoding="utf-8", newline="\n")
    return novo != texto


def _materiais():
    arq = RAIZ / "ferramentas" / "embutir_materiais.py"
    if not arq.is_file():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("embutir_materiais", arq)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> int:
    conferir = "--conferir" in sys.argv
    novo = ORIGEM.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
    if not novo.startswith(INICIO) or not novo.endswith(FIM):
        raise SystemExit("o original do exportador precisa começar e terminar com as marcas conhecidas")
    diferentes = []
    # 0º a base de premissas dentro das contas comuns (o bloco vai para o painel, o SustainKit e o Planejador)
    if premissas_no_calc_comum(conferir):
        diferentes.append(CALC_COMUM.relative_to(RAIZ))
    # 1º a base de materiais dentro do SustainKit e do Planejador (a cópia do SustainKit vai embutida na plataforma)
    em = _materiais()
    if em:
        for a in em.ALVOS:
            h = a.read_text(encoding="utf-8")
            n = em.embutir(h)
            if n != h:
                diferentes.append(a.relative_to(RAIZ))
                if not conferir:
                    a.write_text(n, encoding="utf-8", newline="")
    for arq in ALVOS:
        antes = arq.read_text(encoding="utf-8")
        depois = tratar(antes, novo) if arq.suffix == ".html" else novo + "\n"
        if arq == PLATAFORMA:
            depois = tratar_programas(depois, novo)
        if depois != antes:
            diferentes.append(arq.relative_to(RAIZ))
            if not conferir:
                arq.write_text(depois, encoding="utf-8", newline="\n")
    for d in diferentes:
        print(("diferente: " if conferir else "atualizado: ") + str(d))
    if not diferentes:
        print("tudo igual ao original")
    return 1 if (conferir and diferentes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
