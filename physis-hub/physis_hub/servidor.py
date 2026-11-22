"""Servidor HTTP do hub (biblioteca padrao).

Rotas que o Receptor V6 ja usa (sem mudar o firmware):
  POST /api/gateway/webhook      text/plain, uma linha V6 por linha -> 200
Rotas para dispositivos Wi-Fi via ESP (Caixinha e afins):
  POST /api/v6/linha             mesmo corpo; a resposta traz os comandos pendentes do no
Rotas das telas:
  GET  /api/painel               estado completo para a interface
  GET  /api/serie?ativo=&grandeza=
  GET  /api/leituras?limite=&no=   historico das leituras (tela Registros e download)
  GET  /api/saude                contadores, descartes, cadeia do registro
  POST /api/comando              {"comando":"CMD:03:LIM1:35"} ou a linha crua
  GET  /api/clima                previsão de cada fonte guardada no hub, placar de acertos e previsão combinada
  POST /api/clima/local          {"lat","lon","municipio","uf","ibge"} — também grava no receptor (PHYSIS_RX_URL)
  POST /api/clima/atualizar      consulta todas as fontes agora
  GET  /                         web/painel.html
Páginas e rotas ligadas em 15/11/2026 (cada uma com o seu documento em docs/):
  /documento[/<id>], /api/documentos…, POST /api/documentos/pdfa   documento para comentários e PDF/A (EXPORTACAO.md)
  /municipio, /api/municipio…                                       painel municipal de resiliência (MUNICIPIO.md)
  /api/evidencias/dados, POST /api/evidencias/anexo[/remover]       certificação assistida (EVIDENCIAS.md)
  /api/parceiros…                                                   profissionais parceiros (PARCEIROS.md)
  /app/baixar, /app/android.apk[.sha256]                            download do app (APP_NATIVO.md)
  GET  /api/servidor/pegada                                         pegada do servidor (PEGADA_SERVIDOR.md)
  /demo/{sustainkit,scada,monitoramento,planejador,plataforma}/     demonstrações públicas (demos/)
  /termos, /privacidade, /acessibilidade                            textos de sistema/physis-juridico.js (minuta)

Variaveis de ambiente:
  PHYSIS_MQTT_BROKER/_PORTA/_USUARIO/_SENHA/_TLS/_NOS  ponte MQTT da Caixinha IoT (ver docs/MQTT.md)
  PHYSIS_PORTA (8700)  PHYSIS_BANCO (physis-hub.db)  PHYSIS_ORG  PHYSIS_LUGAR
  PHYSIS_RX_URL        ex.: http://192.168.4.1 — liga o envio de comandos e a consulta ao receptor
  PHYSIS_TOKEN         se definido, exigido em X-Physis-Token nas rotas das telas que alteram estado (comparação em
                       tempo constante); também vale como chave única antiga dos aparelhos. Prefira as chaves por dispositivo.
  Segurança na internet (docs/SEGURANCA.md, physis_hub/seguranca.py):
  PHYSIS_ENDERECO (0.0.0.0)  PHYSIS_PROXY_CONFIAVEL  PHYSIS_HTTPS  PHYSIS_EXPOSTO  PHYSIS_ACEITAR_SEM_CHAVE
  PHYSIS_PRIMEIRA_CONTA_EXTERNA  PHYSIS_LIMITE_{PUBLICO,ARQUIVO,ENTRAR,DISPOSITIVO}  PHYSIS_RETENCAO_DIAS_*
  PHYSIS_CSRF_ESTRITO  PHYSIS_ORIGENS  PHYSIS_SESSAO_OCIOSA_MIN  PHYSIS_SESSAO_DIAS  PHYSIS_REAUT_MIN
  PHYSIS_CONFIRMAR_EMAIL  PHYSIS_TERMOS_VERSAO  PHYSIS_CONSENTIMENTO_ESTRITO  PHYSIS_SEGURANCA_CONTATO
  PHYSIS_SIMULAR       ex.: "6,1,3,1" (solo,zona,coleira,comedouro) — gera dados sem hardware
  PHYSIS_APP_DOWNLOAD  pasta com baixar.html, android.apk (padrão: <pacote>/app-download)
  PHYSIS_PEGADA        configuração da pegada do servidor (JSON); "0" desliga
"""
from __future__ import annotations

import base64
import hashlib
import html as html_mod
import json
import os
import sys
import threading
import traceback
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import re

from . import clima as clima_mod
from . import saude as saude_mod
from . import mqtt as mqtt_mod
from . import gis as gis_mod
from . import zonas as zonas_mod
from . import vento as vento_mod
from . import residuos_gis as residuos_mod
from . import aprendizado as aprendizado_mod
from . import robos as robos_mod
from . import alertas_clima as alertas_mod
from . import app_pwa
from . import correio
from . import documentos as documentos_mod
from . import documentos_auto as documentos_auto_mod
from . import indicadores as indicadores_mod
from . import editais as editais_mod
from . import evidencias as evidencias_mod
from . import municipio as municipio_mod
from . import parceiros as parceiros_mod
from . import frota as frota_mod
from . import validacao as validacao_mod
from . import intercambio as intercambio_mod
from . import mapeamento as mapeamento_mod
from . import simulacao as simulacao_mod
from . import cep as cep_mod
from . import fornecedores as fornecedores_mod
from .simulacao import biogas as sim_biogas_mod
from . import pegada_servidor as pegada_mod
from . import seguranca as seg
from . import suporte_remoto as suporte_mod
from . import perfil_cliente
from .hub import Hub
from .protocolo import para_int, validar_telemetria
from .simulador import Simulador

CORPO_MAX = 64 * 1024
# Ao recusar um corpo grande, o servidor ainda le e descarta ate este tanto antes de fechar.
# Sem isso, o Windows (e as vezes o Linux) corta a conexao com RST e quem enviou nunca ve o 413.
# O teto e o tempo limite impedem que alguem prenda o servidor mandando um corpo sem fim.
DRENAR_MAX = 24 * 1024 * 1024
DRENAR_SEGUNDOS = 5
WEB = Path(__file__).resolve().parent.parent / "web"
DWG_MAX = 50 * 1024 * 1024


def converter_dwg(dados: bytes, programa: str | None = None, tempo: float = 120.0) -> dict:
    """DWG -> DXF com o LibreDWG (dwg2dxf, código aberto). Sem o programa no servidor, avisa e pede DXF."""
    import shutil
    import subprocess
    import tempfile
    exe = programa or os.environ.get("PHYSIS_DWG2DXF") or shutil.which("dwg2dxf")
    if not exe:
        return {"ok": False, "codigo": 501, "erro": "o conversor de DWG (LibreDWG, dwg2dxf) ainda não está instalado no servidor; exporte em DXF pelo programa de desenho"}
    if not dados.startswith(b"AC10"):
        return {"ok": False, "codigo": 400, "erro": "o arquivo não parece ser um DWG"}
    with tempfile.TemporaryDirectory() as d:
        ent, sai = Path(d) / "entrada.dwg", Path(d) / "saida.dxf"
        ent.write_bytes(dados)
        try:
            p = subprocess.run([exe, "-y", "-o", str(sai), str(ent)], capture_output=True, timeout=tempo)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "codigo": 500, "erro": f"a conversão não terminou: {exc}"}
        if not sai.is_file() or sai.stat().st_size == 0:
            msg = (p.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-1:] or ["sem detalhe"]
            return {"ok": False, "codigo": 422, "erro": "o conversor não conseguiu ler este DWG (" + msg[0][:160] + "); exporte em DXF"}
        return {"ok": True, "dxf": sai.read_bytes()}


# mapas de fundo das regiões dos clientes (PMTiles do OpenStreetMap); PHYSIS_MAPAS troca a pasta
def PASTA_MAPAS() -> Path:
    return Path(os.environ.get("PHYSIS_MAPAS") or (WEB.parent / "mapas"))


# bibliotecas grandes que o servidor entrega em /vendor/ (as pequenas vão embutidas nos programas)
VENDOR_TIPOS = {"maplibre-gl.js": "text/javascript; charset=utf-8", "maplibre-gl.css": "text/css; charset=utf-8",
                "pmtiles.js": "text/javascript; charset=utf-8", "web-ifc-api-iife.js": "text/javascript; charset=utf-8",
                "web-ifc.wasm": "application/wasm", "three.min.js": "text/javascript; charset=utf-8"}
# three.js 0.170 em módulos ES (vista 3D com oclusão de ambiente e leitor glTF; ferramentas/baixar_three.py, TESTE de 22/11/2026)
THREE_MODULOS = ("three/three.module.min.js",) + tuple("three/addons/" + a for a in (
    "postprocessing/EffectComposer.js", "postprocessing/Pass.js", "postprocessing/RenderPass.js", "postprocessing/ShaderPass.js",
    "postprocessing/MaskPass.js", "postprocessing/OutputPass.js", "postprocessing/GTAOPass.js", "shaders/CopyShader.js",
    "shaders/OutputShader.js", "shaders/GTAOShader.js", "shaders/PoissonDenoiseShader.js", "math/SimplexNoise.js",
    "loaders/GLTFLoader.js", "utils/BufferGeometryUtils.js"))
VENDOR_TIPOS.update({n: "text/javascript; charset=utf-8" for n in THREE_MODULOS})
INSTANCIA = Path(__file__).resolve().parent.parent / "instancia.json"
# catálogo inicial da loja (pacote do site Physis; ferramentas/gerar_loja_catalogo.py): publicado ao ligar se a loja está vazia
LOJA_CATALOGO_INICIAL = Path(__file__).resolve().parent.parent / "loja-catalogo-inicial.json"


def arquivo_instancia() -> Path:
    """instancia.json desta instalação. PHYSIS_INSTANCIA troca o arquivo (por exemplo, para rodar uma segunda instalação
    do mesmo código, cada uma com a sua configuração e o seu PHYSIS_BANCO)."""
    return Path(os.environ.get("PHYSIS_INSTANCIA") or INSTANCIA)


def ler_instancia() -> dict:
    """Configuracao da instalacao montada na compra: modulos, se exige login, licenca."""
    try:
        return json.loads(arquivo_instancia().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


MAPEAMENTO_CORPO_MAX = 20 * 1024 * 1024        # arquivo do cliente ou IFC da aba Mapeamento
SIMULACAO_CORPO_MAX = 8 * 1024 * 1024          # entrada de uma simulação (grade do terreno até 250.000 células)


def banco_da_instancia(inst: dict) -> str:
    """Arquivo do banco: PHYSIS_BANCO; senão physis-hub.db."""
    return os.environ.get("PHYSIS_BANCO") or "physis-hub.db"


def cliente_receptor(base: str, timeout: float = 4.0):
    """Funcao que entrega um comando ao receptor (`POST /api/comando`)."""
    def enviar(linha: str):
        dados = json.dumps({"comando": linha}).encode()
        req = urllib.request.Request(base.rstrip("/") + "/api/comando", data=dados,
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                corpo = json.loads(r.read().decode() or "{}")
                return bool(corpo.get("ok")), f"fila do receptor: {corpo.get('fila', '?')}"
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return False, f"receptor inacessivel: {exc}"
    return enviar


def consultar_receptor(hub: Hub, base: str, parar: threading.Event, intervalo: float = 3.0):
    """Consulta `GET /api/leituras?desde=<cursor>` — segundo caminho, alem do envio."""
    cursor = 0
    while not parar.is_set():
        try:
            with urllib.request.urlopen(f"{base.rstrip('/')}/api/leituras?desde={cursor}", timeout=4) as r:
                dados = json.loads(r.read().decode())
            linhas = dados.get("leituras", [])
            if linhas:
                hub.receber_lote("\n".join(linhas), origem="receptor-consulta")
            cursor = int(dados.get("cursor", cursor))
        except (urllib.error.URLError, OSError, ValueError):
            pass
        parar.wait(intervalo)


def simular(hub: Hub, sim: Simulador, parar: threading.Event, intervalo: float = 2.0):
    while not parar.is_set():
        linhas = sim.passo(hub.comandos_pendentes())
        hub.receber_lote("\n".join(linhas), origem="simulador")
        parar.wait(intervalo)


def origem_chamadas(valor: str | None) -> str | None:
    """Origem do servidor de chamadas (Jitsi) da Physis, ou None se ausente ou invalida.

    So aceita https://host[:porta], sem caminho, consulta nem caractere que quebre a politica
    de seguranca. Qualquer outra coisa e recusada: a politica continua fechada."""
    if not valor:
        return None
    v = valor.strip().rstrip("/")
    if any(c in v for c in " ;,'\"\t\r\n"):
        return None
    u = urlparse(v)
    if u.scheme != "https" or not u.hostname or u.path or u.query or u.fragment or u.username or u.password:
        return None
    return f"https://{u.netloc}"


def politica(chamadas: str | None = None) -> str:
    """Content-Security-Policy. Sem servidor de chamadas, nada de fora do proprio servidor e carregado.
    Com ele, so aquela origem entra: script da API, quadro da chamada e a ligacao (https e wss)."""
    o = origem_chamadas(chamadas)
    s = f" {o}" if o else ""
    w = f" {o} wss://{o[len('https://'):]}" if o else ""
    # 'wasm-unsafe-eval': deixa rodar o leitor BIM (web-ifc, WebAssembly) servido pelo próprio servidor;
    # worker-src blob:: o mapa (MapLibre) desenha num worker criado na própria página. Nada de fora entra.
    return ("default-src 'self'; script-src 'self' 'unsafe-inline'" + s + " 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; "
            "worker-src 'self' blob:; "
            "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' blob:" + w + "; frame-src 'self' blob: data:" + s + "; "
            "media-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'")


def fabricante(instancia: dict):
    """Função que monta o pacote de um cliente, ou None se este servidor não tem o montador.

    Procura montar.py ao lado de physis_hub/ e os programas da Physis em programas/ (pacote do
    servidor) ou nas pastas do repositório. Os pacotes vão para PHYSIS_ENTREGAS (padrão: entregas/)."""
    raiz = WEB.parent
    if not (raiz / "montar.py").exists():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("physis_montar", raiz / "montar.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    def achar(*nomes):
        for n in nomes:
            for p in (raiz / "programas" / n, raiz.parent / "sistema" / n, raiz.parent / "modulos" / "planejador" / n):
                if p.exists():
                    return p
        return None
    sk, sup = achar("SustainKit_Definitivo.html"), achar("physis-scada-demo.html")
    saida = Path(os.environ.get("PHYSIS_ENTREGAS") or (raiz / "entregas"))
    def fabricar(org: str, modulos: list[str], nome: str, cursos: list | None = None) -> Path:
        saida.mkdir(parents=True, exist_ok=True)
        return mod.montar(org, "lugar01", modulos, saida, sk, instancia.get("licenca") or mod.LICENCA_PADRAO, sup, None, None, False, nome, cursos)
    return fabricar


# ── Páginas que o próprio servidor monta (ativar, entrada da Gestão, fluxos de conta) ──
# Mesmo modelo da plataforma (painel.html): faixa com a árvore e o título serifado verde (o único h1 da tela),
# cartão, campos e botões do painel, rodapé com a navegação do site. Tudo dentro da página: a política de
# segurança (politica()) já aceita estilo e script embutidos e imagem data:, e nada vem de fora.
# Idioma e tema seguem a escolha guardada no navegador ("physis-pref" e "physis-pref-tema", as mesmas chaves
# das outras telas). Cada página traz o seu dicionário português → inglês em window.PX_EN.
_PX_LOGO = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAPwAAABYCAMAAADm+GqtAAAAwFBMVEUAAABOekpShE5MeUg+fj5OekxNeUl/f39MeEhUVVRNeUhMeUlQgUxNeUlRgkxQgkwA/wBQgUxVqVVRg0xQgUxTh04AfwA0ZjRIbEhOkk1Vej1mmGZ/fwBmmTP///9mZjMzmTNakFVmZmZ/fz9olUr//wA7Ozs4WzhObDsAVQAAf39/v39//38A//8zZmY/vz9VVQBVVSpiiU5mzGZ//wCqqlX/AP8AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAU3IIqAAAAQHRSTlMA+PktBBCwAm0DTs+PkVBwAa8DL88TAgULCQsFAgUBBQX/BQQJAQQHDgMCBAIBBQQDBg0FAgMBAAAAAAAAAAAAehiI7gAAE51JREFUeNrlXIdi48iRbaADUgc0EoPSzGbbd/YF+/7/0+5VNUCCIKXReUcnSwt7NUgE8DpUeFXVQnxjG3WBP0H07Sj+EJua/5WiqOKIPyJEL4wfRUuni+7TIm+XnU44L2qne6FFbITNg24/fa9PY/iN9ipRD72Rh+EodOOsHak9sGlZ6k8JvRLeiz7HeOcDl1shwiD7PPaCLtHA0Hl2EL8IpT8bdDEdYn/Iap72qi3zsW0f8mFAGwgf+4BZXwlj6GbruYU+z6arthyiGJzoqvtiJ6xBKzw2eS53MuQ2eE0tFK0Ye91o8ZlEQO9rJ3TMvTdC8/SniV4dsjzLhhhkGueFgOSXURrxp08k5AsdhuZnDO8cbeCtD0LEEG3d5zbLMOXFseiD6NoJ819bW/LUKIpPIeRpDPu8L/bCN+bhycc8/jL0EHU2l6bBuIhSYEjs0Ov3j09NRkJx/AxCT2uJPhW9KK3ovgiTAZQu86GRos5z6PhMyKEWBP4gypAUP2yf2Mv6o8/89hDQvUKFWA8jBkGd9+IBRu2Qw7YNed35rBx6cSdYGBiPvWh1VwgTnWxb8dHx+wHo6W8QY6UBvgJMiX8PDXR9n2GUq66oTdtqo0XRRr4li5/EpoX5roUeGggzn3uSZu0+q9s6J/TQ/Fp8YQ1fk/r7MaO/ciDNh99+bJ8HpgsmuQ11mdcQe+h/dm4yK5rcyzzmZXXYYTrQiRqjHkagEsemHo/sANmPbu+Q3e5tlsN4gT0zg489xB0M2tzhqITs0w6SDlIBfS4HmD0a1oFw/YcGrx8m0dsQbIQ551UeCc2jMHmW2/4LOtppb2Mfnct123YwANBCuEQNFrQhw/jjbkZWqpW+1+JOxtxk2djSdDboa9hzqkWTRKi6hsZFIdoxgxlgISExCHwI9cfFrvSojJv9VVJa9YDeh3iDHgfmqDEFXE4enf0aCTtN/hzSHtYejuRgdnAKPiZ2WLU2YvpqUXXLzMWQlvBt0rAXHcBnkHJlbtVhRCNpvv3QcWONJCKDevzAnd/bIQgWW7qXUrt8ADp0uGl8QeAh9kDlyF/sqAi7X355L/oB/g8swqJN/106yWrZqhsiUanNyXulpovravsDte06fsSkrpm16upeej6P0E4t3+m9L9mnowFetO0Y86yB3BtgvIevJQzeHfU8TnvYdSVLecx2CMDAOsJb69J8+ZbEV99dJUz8RF3MZMQr+AohntTq7j5EUutP6FpIs0r82fv+b+1PltBD542wa4/o9Qyju7A5mX0DERuD9cntJcugA/CeuJ7+wtJtRX3e5O7yA0EJlWWNoXPuRSHLUi5t+EhH5eXX48SaRcCdsjQNNgeZW11abXW5Ydva091m/ZQ+4iV3P4jQ6HngFqzVZfjqcFGLzpLdM4qQQesNHkcx2FDxjZgud0AvI6aOHdtL0wFC47Q1Tq4/sEIz5kZ0a88S7yxP3HGrQSSsftKxk6WLdWNBL+W04en1BfoKmimT68E4CeVOd2dlQt9j2FsSYOhgTG0l9mOLgwO9ypBx08OTsfhMzKHaYL5n0HrUpmNBk1wOYzUpsRtKa/oru8mcsRMlUq4+EOCzzG3A0y3qDDaDFV2csTZZVp9/MNEDcIdzjl9TXjatyS7AT2LfcA+kuwGsYiOll3q0MZCB3lhR6dB5Nl/6gboGBr+xBhMe0t9HaH6+USQRsxPOgQEgGQh7QHQ3wNeaNilreueqe74JHj5zQwC6220xYWTghOQDuXn4NfhC4WFNuls7Rn9+tQ4xgKHBsCNq0g/EVBcxbyq6BzJwJEITKnAg/d7Nrswdhi72Rj8QuyumWz0vT4f4eBzdvxr8JVzu+ItZ4Oj3QMVKAwfN8fmeV/Qs3DCR4hH0Iv4waPcCug5dA2SlAfoeXG1N01oLEuwI0Bxg4Rds6wD7U1u13iOWAYVxGErNIgAeL55Z3N8AP6lpmu4LdUevdCds3wa/DPRq1RLVSl4CgG7Tie5eNySS1XPgp3T8kA4ecMTuCr66CFBX1tF0gLkzlIP0oa5dHExDAgiGDH1lBXsGdp2iwW6j6ztuIryzcb7vf7jB53UXXzBV+NymeP2wJzF66vptx1fpWnf+bdOU56ddDXu1fnc31dAQsys+nm8a+wD86SEjLPjhrgVXh2bSAqq+BHA8UTcYFUR9gOHzszM//ihI3T0+C55ECvpqUTKvAJ8gsIzbdjzFk/Dz6cKQKZ4d9jxOmo19RF5soOl6wP+PRNgK6X2TQ7097Cs2dEuMlRF/q58MiXx6sG4GeDOwcfsDP1npTgRPZlLfts+DL9Lh/f8F/NL196nji+0l9aw9cwP8tBVKO5rqto7ko4kAbSVDiZmP+YOvuVN/bRC0gXKvxd7k0Gp42oOwmOggd1OXqw7m784FP5CB/MKwxxdwz0+vBz/rC8gl7ue1Lktzfv8c+qthnxpvwzb3wUtMcRJaJZCbMJs9rLqE7iS6u/B52aFB+nuV+D64vdQ6B7bpWClmgK63TOYl+Lag1v9yOeeLu+K06eIKfDF3fZHardjCM/Cvb1rN19Iez272QqgbZvDoA9k+cfiaWc+KHwPCH5i/KTH4m4adWPGXTvdk56Q2Gq1txz5ZfLsrNb+ArxJRtqf3n0XU3POX5usWfFJotUgd313CIxsnae6u+hZ4EK+k5+sd67elj1rVod+xQcn1techn2xSbgwvwehhHGQw9Udvh/l8Ho2BasC3Rj4O8tfqFjPGX7DIQJmt5XWatPJic1fg79skqajj23YjsGq2mktJj1TTy8MeYyhZeBx1O/uYuqdj9s2IrLIlvBDeajtQQ3Bb5I5bpTHL1swtlJW400NTBn0bfNu17bTT0p2MylXPXW0b8Knrpby+wE8w/HXwa/TGrbue8/diz7Y9IFzdvdOFDzEmX201HaD4ZtMcvNWWotYY8yD+AomHu7G7Cb5JGz/DbW37b4NnK9bAQfqtbW+4qNI1CZHTG8dmC572dcmeED5EnsQT/3uwNkkvBWqjJwe16vWfBXl0jB22Xd9jhqkRfMau78eVaeDHW1xFAp/PGyDUawM4Dfv6YnM3OphF1a2OX8KkskzuU/2iYzPz80LXrkn9sL6m2DKG2Y7IdIQMcKOA0QqG0vLUgmdjcBb6DSSGxg0IWBWPU3FmRZ4B79JW1lJspPVrBB6NVxZVz+QDFXy3rpts6zNegyfGZ+K7Dc/Ai4td1aamDqTkXQCni67Skam8TJT0pRgcCFQ6Guf+1Pf31Qvg9WXLb8B3q+3Q3QSvbrfJCn8lFleleBk84e+62ceqb39yCBrBCIDmD48t8TiNcDOtAvCxf2UchL5AaSbxuuJKXH3byHkR/EoIAL9be003wK/uru6S1r0NHo1y5J7XRz1GOHMAX2iWhi2B72Oo1WvBP8Pt/X7wF68q5IW3X730amI3s/WYXL8M3jzIjRYRaGvg2zGDB1/nP0kPIpgVyPvHDap9V/AKHMmltdu8IPAu7hY/J4vx9rBHwhGeB0u/E1Xq+eRRgfJIyQlk3QXRvR/4zdlWHF8CX4nLgdG+AL5OStRQC6gFPKAf7kXknhd7TZJQvCd4omZOZ9V06eRtwE+J+lgYh4ndjO6Znm/Z/zAjcZ4JfITKY48HzmvrSNAH26o25WUU7zHsNWs3TSpqUmfP//awZ88IApGmalvNpNLNOT9nWomGfl1Fbbnn+2gx03vS8zXt2jRsxnea8x1crpW+cpe2wBY8+8RZuaYT9e0sjX6mW1LmXc/gm5ZZbvh5IchRhxD6H7UeR5h6et/rd+j5SlFUwNV7fUzU8CXXYbYnHBuZ0F96SyQndfFcAJvAazUTtgFeYAgg+9kZxFEo7e3shLdWdb+6FA1Jf+ULNBafKbPV7eWFtO52s7VwtgcKmk0YAHkybw9PqkNigi+B1sL5DTVyNsF61SGMz/V8/iL4FyM23zidhm9yHsix228dm/zKsWF2P7kZZ9easd6l1FpybKplI5Kk8+zfU+guRTh3+gekYq76egyxr3Y3J9BVwOxCYsF1XnM/LZ25zuh95vTiqOEViPDpqziprGt95QSmu7cubXGnFWyYMxl77dKC4hn/7cqnJZfWcsR6fIcCjLMz2b0iF7Corn83chZpXMiMUC/ESl02+RJpzF1zIjPcwmY0NIiIzCiDC0GLVwXJV9NiK2Xa7iaGZ07PjopKQZgrpF11K+uM717TWDbRWODu6kRj5TONlZnANBZJvEHDvEPoMznn0eB/iGa5yMflqJX4sNtILCQ4y/g1B6fRa00EJsuxM4FJk/6//4LAXJbPBCYIkI4IzCxxvdUHTLJn6prCVBJR9nDH0gKhGo8JvlMLdX0AiSmnKlHXdWT5h3Ge5Fmirm+kpfyrp+NgWDfWG3bRS6iAOWhRAqfa7YpT0AJVCBy0mO4E+ELPOUkpaIF5rTloUX+0nqdwlWIjdY/caxjzoy+ZsFN7NQ/6Ow5XFT/FpJbbYhwGCHnAl3eJSoFdCRLTb8NV//qT/cA1FOeRQMptSJFuij5n430hDjDF9pSBUKdApWRxgN4fTFhMWyTjEsn1wVLSYNN4DlGXJWLUDYWo6xoh6jIOkO6Ow/DkEKEY4RSidojtVSkbl2lz2T+tleeH2YoKYorzRoZzcsKRkxMkJydMf0dyglmSEzSgI7ztJTfDOJSjR6CfkhOKN4HPUby3nksos4B7sicdZql6irNyTN6odVqKT2kpqnpMdiAS01BgSGYgycv7j1dwISkuqUNCi4SkTltUF9EB5HtKSGqQh1RzQpI5JSTtVEpIMrY4cGLijYSk77BpNjVv+gePoDO+xWsuTk5zlS+0OAA+mJzyjzRS0SrUEBxI9nMqGqY89BwiLZyKBkLAjCkVjVBqzjeVua7ud0hFg7zov3/NV8nhLiSEdCSb1GyU0h7CFRpf1q0uUIbNHLBe9oqqhSZGyAERQ2Qfra5Oc7uBiYZXB089X5yniyREVNNYiseP+BROQsSIQNmd3Sd6CFQSJyEefQzjdwffiP/ZWvPi5frvdWT2piN4kZ1A6af7B4JLXq5GphWUWyAbrszdcaB8BuJy4B07JJ6h6ARu7jn9NHBBDqaEvEo//T7gK1au7gh3qlTM02LPHesSYVfYZA7RR+PY9FS0x078Dnsw2JAcX2rnBKWxOtA9jUk+NN8nHSUecxwKMxxlZST4KfGYNF6/JB5/ocRjxOhrEWmIyGTaelu2nHgcTZn6o3iDUseyWRg44+oyM4pyNZqyBv5G7MBFSYRw4X02GowskmoR60Q4dN4jyMBScmEUpdyC+0AGsTYZrjZIo5+LClPKOVPzMPZTyrmaU87VKeW8V9uU8wKmzuSsSgxu1X5/8CTw7iCAqIX3RFg2JlGQkMUMni78if6a+YI+7WHsMsWZwDPP2VCD/JpSJbjYAKQsWern7BYuNlCrYgOLijPKwX4cqegQBUeY8Id2XWzw89sUuSaBpwEEfvheoCJEZvpnXWlqgwRedzQ0DVomKYWmbOe0T4gjgP1xz+BJMyDFCDlMtFfRo7nbR01MhlrkAeXcBvG01NiMPAQ4cPs10h0PpAho6KtUZhIVChHfqMK3bPZ7rSlCwQX9QFEzRlW4BTxlGRF4OedBZKVe9hzAF1AL3POl4Dlz3DO3V011tiowIp2q2ZuFyXp3LjCipM6GS6n+wQVGE5LB88BjhVJTfXBvVmC0nvN8aAgjZZ1/ETfAp7x+kBGnPZEq4dbgdZfVAKuKGTzGrl6Xlmlo9UdOGuTSMhRO524Mc2nZOImltCzMpWVRdG8IvroET4gxI9tsC17PEQwnq2bZuwVeIPGU2DyTXRYV9pbLpkqa6DxpDNdVQMK5JAmaLsalqBBuzlxUaN6qqHDp+XYFHnOVlI25Ar9cYAkB9HuDS+UN8Cwjj8hO2ZSTeioa6W+Vk3YoJ/VzOekTKovhweqm5sycFuWkbzbnZwvvDH5H6gunNsO+ET/wzZk5cnyCqkn2YtXz2Qk8HgZd7k5zfqJFUcJSSBzyFPI7Zn5dSPxwLiR+OBUSF29bSEy1XtjEfi4q0DPhr6mvdzjUnIWHf+hT9hQJYLG9q1MOkJbLz9JPFdEO4je6egK/LiHXakymHpeQj+TS9xnV1XcF6uenMf6E/DDDt7xDCXkhyjShjbuRmCdmHrHaJKJsIikiZT+l4ydePGDnB9+QYvO5ZsYm5uOyeIBtaKEkXjwgUhl1dCitaZG68daLByz+fBIq06TS1GYLhsPtxZzYm+CfGIV5L52fzvZnQWGymiPcc8z2bpQ0yzEULMXsInnvu3oY0BTLshE1KfbrZSP68v+7gLrAnEfYJPunX1ywrWxW8flDWjAkk0is9pk5dJRTvqcFQwaXS0Cl2rFlwRDIkJhmxnssGEIFd66U4v6ffQDSNEDYXYQJRXHAUjFUeTcAIy0VU9BSMSg7oqViNFcueoSU24qXinHzUjHvwN4UQvy+CEl15dy2FNd0yDPKa5+SWzpeJOhhpNhVBE27Xy8ShHv+470WCqGCqvvf84BWqess/VG3IS0PVUHM8PJQqBRNy0NZWh5qz8tDoeBG7s3nWxis0Fbq08JgNa2T8O9/kIXBrpeEK1dLwgU/+7AZ+frjJ1wWUtNigHrOGxmkkeOgeTFAJLQngx/FZ59zMcD1MpCK1kLyTpNla3gZyP/67MtAsixcuE1aAFTzAqDDH2MB0M0wkMvSr6L/dOj+F6f//NkjrGFyAAAAAElFTkSuQmCC"

_PX_CEDO = r"""<script>(function(){var r=document.documentElement,p=null,t=null,i=null;try{p=JSON.parse(localStorage.getItem("physis-pref")||"null");}catch(e){}
try{t=(p&&p.tema)||localStorage.getItem("physis-pref-tema");i=(p&&p.idioma)||localStorage.getItem("physis-idioma");}catch(e){}
if(t!=="claro"&&t!=="escuro")t="auto";r.setAttribute("data-tema-escolha",t);var e=t;if(t==="auto"){try{e=matchMedia("(prefers-color-scheme: dark)").matches?"escuro":"claro";}catch(x){e="claro";}}
r.setAttribute("data-tema",(p&&p.verde)?"escuro":e);if(i==="en")r.setAttribute("lang","en");})();</script>"""

_PX_CSS = r"""<style>
:root{color-scheme:light;--fundo:#F4F6F1;--sup:#FFFFFF;--tinta:#1C2B21;--tinta2:#4A4F44;--acao:#33512F;--sobre:#FFFFFF;--linha:#C9D2C4;--campo:#FFFFFF;--borda-campo:#8A9284;--ok:#1F4A1C;--al:#7A2214;
--fonte:Lexend,"Atkinson Hyperlegible",system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;--titulo:Fraunces,Georgia,"Times New Roman",serif}
html[data-tema="escuro"]{color-scheme:dark;--fundo:#14180F;--sup:#1C2B21;--tinta:#EEF2EA;--tinta2:#D9D3C2;--acao:#B9CDB3;--sobre:#14180F;--linha:#4A5A47;--campo:#14180F;--borda-campo:#8A9182;--ok:#DCEBD8;--al:#FF8A80}
*{box-sizing:border-box}[hidden]{display:none!important}
body{margin:0;min-height:100vh;display:flex;flex-direction:column;background:var(--fundo);color:var(--tinta);font:1rem/1.55 var(--fonte)}
a{color:var(--acao)}:focus-visible{outline:3px solid var(--acao);outline-offset:2px}
.pular{position:absolute;left:-9999px;top:8px;background:var(--acao);color:var(--sobre);padding:10px 14px;border-radius:8px;z-index:10}.pular:focus{left:8px}
.px-faixa{background:var(--fundo);border-bottom:1px solid var(--linha)}
.px-in{max-width:1240px;margin:0 auto;padding:10px 20px;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px 16px}
.px-id{display:flex;align-items:center;gap:14px;min-width:0}
.px-id img{height:42px;width:42px;object-fit:cover;object-position:0 50%;display:block;flex:none;border-radius:6px}
html[data-tema="escuro"] .px-id img{filter:brightness(0) invert(1)}
.px-tit{font:500 24px/1.15 var(--titulo);letter-spacing:-.012em;color:var(--acao);margin:0;overflow-wrap:anywhere}
.px-nav{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center}
.px-nav div{display:flex;align-items:center;gap:6px}
.px-nav label{font-size:.85em;font-weight:600;color:var(--tinta2)}
.px-nav select{font:inherit;font-size:.88em;font-weight:600;min-height:44px;padding:0 8px;border:1px solid var(--linha);border-radius:8px;background:var(--sup);color:var(--tinta)}
main{flex:1 0 auto;width:100%;max-width:520px;margin:0 auto;padding:24px 16px 40px}
main:focus{outline:none}
.t2{color:var(--tinta2);margin:0}
.cartao{background:var(--sup);border:1px solid var(--linha);border-radius:14px;padding:18px;margin-top:14px;display:grid;gap:12px}
label{font-weight:600}
input{font:inherit;width:100%;min-height:46px;padding:6px 12px;border:1px solid var(--borda-campo);border-radius:8px;background:var(--campo);color:var(--tinta)}
input[type=checkbox]{width:20px;height:20px;min-height:0;padding:0;margin:3px 0 0;accent-color:var(--acao);flex:none}
.linha{display:flex;gap:10px;align-items:flex-start;font-weight:400}
.principal{font:inherit;font-weight:600;min-height:46px;padding:0 20px;border-radius:8px;border:1px solid var(--acao);background:var(--acao);color:var(--sobre);cursor:pointer}
.principal[disabled]{opacity:.6;cursor:wait}
#msg{min-height:1.5em;font-weight:600;margin:0}#msg.erro{color:var(--al)}#msg.ok{color:var(--ok)}
.depois{margin-top:14px}.depois a{display:inline-flex;align-items:center;min-height:44px;font-weight:600}
code{font-size:.92em;background:var(--fundo);border:1px solid var(--linha);border-radius:4px;padding:0 4px;overflow-wrap:anywhere}
footer{border-top:1px solid var(--linha);background:var(--sup);color:var(--tinta2);font-size:.92rem}
footer .px-in{display:block;padding:12px 20px 24px}
footer ul{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:0 20px}
footer a{display:inline-flex;align-items:center;min-height:44px;font-weight:600}
footer p{margin:4px 0}
@media (max-width:480px){.px-in{padding:10px 16px}.px-tit{font-size:21px}footer .px-in{padding:10px 16px 22px}}
"""

_PX_FAIXA = r"""<a class="pular" href="#conteudo" data-pt="">Ir para o conteúdo</a>
<header class="px-faixa"><div class="px-in">
<div class="px-id"><img alt="Physis Engineering" width="42" height="42" src="__LOGO__"><h1 class="px-tit" id="tit">__TITULO__</h1></div>
<div class="px-nav" role="group" aria-label="Preferências de leitura" data-pt-aria="Preferências de leitura">
<div><label for="px-idioma" data-pt="">Idioma</label><select id="px-idioma"><option value="pt" lang="pt-BR">Português</option><option value="en" lang="en">English</option></select></div>
<div><label for="px-tema" data-pt="">Tema</label><select id="px-tema"><option value="claro" data-pt="">Claro</option><option value="escuro" data-pt="">Escuro</option><option value="auto" data-pt="">Automático</option></select></div>
</div></div></header>
"""

_PX_RODAPE = r"""<footer><div class="px-in">
<nav aria-label="Site da Physis" data-pt-aria="Site da Physis"><ul>
<li><a href="/loja/" data-pt="">Loja</a></li><li><a href="/consultoria/" data-pt="">Consultoria</a></li><li><a href="/demo/" data-pt="">Demonstração</a></li></ul></nav>
<nav aria-label="Documentos da Physis" data-pt-aria="Documentos da Physis"><ul>
<li><a href="/termos" data-pt="">Termos de uso</a></li><li><a href="/privacidade" data-pt="">Política de privacidade</a></li><li><a href="/acessibilidade" data-pt="">Acessibilidade</a></li></ul></nav>
<p>Physis Engineering · Petrópolis/RJ</p>
</div></footer>
"""

_PX_JS = r"""<script>
var PX=(function(){var r=document.documentElement,est={titulo:null,suf:" · Physis"},tem=Object.prototype.hasOwnProperty;
var COMUM={"Ir para o conteúdo":"Skip to content","Preferências de leitura":"Reading preferences","Idioma":"Language","Tema":"Theme","Claro":"Light","Escuro":"Dark","Automático":"Automatic",
"Site da Physis":"Physis website","Loja":"Store","Consultoria":"Consulting","Demonstração":"Demo",
"Documentos da Physis":"Physis documents","Termos de uso":"Terms of use","Política de privacidade":"Privacy policy","Acessibilidade":"Accessibility",
"Conferindo…":"Checking…","Sem resposta do servidor.":"No response from the server.","Sem resposta do servidor. Tente de novo.":"No response from the server. Try again.",
"Seu nome":"Your name","E-mail":"E-mail","Esqueci a senha":"I forgot my password",
"Li e aceito os Termos de uso e a Política de privacidade da Physis (versão {0}).":"I have read and accept the Physis Terms of use and Privacy policy (version {0}).",
"Para criar a conta, marque que leu e aceita os termos.":"To create the account, tick that you have read and accept the terms."};
function en(){return r.getAttribute("lang")==="en";}
function L(s,v){var d=window.PX_EN||{},t=s;if(en()){if(tem.call(d,s))t=d[s];else if(tem.call(COMUM,s))t=COMUM[s];}
if(v)t=t.replace(/\{(\d)\}/g,function(_,n){return v[n]==null?"":L(String(v[n]));});return t;}
function por(el,s,v){if(!el)return;el.setAttribute("data-pt",s||"");if(v)el.setAttribute("data-v",JSON.stringify(v));else el.removeAttribute("data-v");el.textContent=L(s||"",v);}
function traduzir(){var a=document.querySelectorAll("[data-pt]"),i,v;for(i=0;i<a.length;i++){v=null;try{v=JSON.parse(a[i].getAttribute("data-v")||"null");}catch(e){}a[i].textContent=L(a[i].getAttribute("data-pt"),v);}
a=document.querySelectorAll("[data-pt-aria]");for(i=0;i<a.length;i++)a[i].setAttribute("aria-label",L(a[i].getAttribute("data-pt-aria")));
if(est.titulo)document.title=L(est.titulo)+est.suf;}
function lerPref(){var p=null;try{p=JSON.parse(localStorage.getItem("physis-pref")||"null");}catch(e){}return p&&typeof p==="object"?p:{};}
function gravarPref(k,v){var p=lerPref();if(!p.v)p.v=2;p[k]=v;try{localStorage.setItem("physis-pref",JSON.stringify(p));if(k==="tema")localStorage.setItem("physis-pref-tema",v);if(k==="idioma")localStorage.setItem("physis-idioma",v);}catch(e){}}
function escuroSis(){try{return matchMedia("(prefers-color-scheme: dark)").matches;}catch(e){return false;}}
function tema(t){if(t!=="claro"&&t!=="escuro")t="auto";r.setAttribute("data-tema-escolha",t);r.setAttribute("data-tema",t==="auto"?(escuroSis()?"escuro":"claro"):t);if(st)st.value=t;}
function idioma(i){r.setAttribute("lang",i==="en"?"en":"pt-BR");if(si)si.value=i==="en"?"en":"pt";traduzir();}
var a=document.querySelectorAll("[data-pt]");for(var i=0;i<a.length;i++)if(!a[i].getAttribute("data-pt"))a[i].setAttribute("data-pt",a[i].textContent.replace(/\s+/g," ").trim());
var si=document.getElementById("px-idioma"),st=document.getElementById("px-tema");
if(si){si.value=en()?"en":"pt";si.addEventListener("change",function(){gravarPref("idioma",si.value);idioma(si.value);});}
if(st){st.value=r.getAttribute("data-tema-escolha")||"auto";st.addEventListener("change",function(){gravarPref("tema",st.value);tema(st.value);});}
try{matchMedia("(prefers-color-scheme: dark)").addEventListener("change",function(){if((r.getAttribute("data-tema-escolha")||"auto")==="auto")tema("auto");});}catch(e){}
window.addEventListener("storage",function(e){if(e.key!=="physis-pref"&&e.key!=="physis-pref-tema")return;var p=lerPref();var t=p.tema;try{t=t||localStorage.getItem("physis-pref-tema");}catch(x){}tema(t);idioma(p.idioma==="en"?"en":"pt");});
traduzir();
return {L:L,por:por,titulo:function(s,suf){est.titulo=s;if(suf)est.suf=suf;document.title=L(s)+est.suf;}};})();
</script>"""


PAGINA_ATIVAR = (r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ativar a plataforma · Physis</title>""" + _PX_CEDO + _PX_CSS + r"""#codigo{font-size:1.15em;letter-spacing:.08em;min-height:48px;text-transform:uppercase}
</style></head><body>""" + _PX_FAIXA.replace("__TITULO__", '<span data-pt="">Ativar a sua plataforma</span>') + r"""<main id="conteudo" tabindex="-1">
<p class="t2"><span data-pt="">Instalação</span> <strong>__NUMERO__</strong>. <span data-pt="">Digite o código de ativação que chegou no seu e-mail.</span></p>
<div class="cartao"><label for="codigo" data-pt="">Código de ativação</label><input id="codigo" autocomplete="one-time-code" placeholder="XXXX-XXXX-XXXX" aria-describedby="msg">
<button type="button" id="ok" class="principal" data-pt="">Ativar e baixar a plataforma</button><p id="msg" role="status" aria-live="polite"></p></div>
<p class="t2 depois"><span data-pt="">Depois de baixar: descompacte, rode</span> <code>python3 -m physis_hub.servidor</code> <span data-pt="">e abra o endereço indicado no arquivo LEIA-ME. No primeiro acesso, crie o seu usuário e senha.</span></p>
</main>""" + _PX_RODAPE + r"""<script>window.PX_EN={"Ativar a sua plataforma":"Activate your platform","Ativar a plataforma":"Activate the platform","Instalação":"Installation",
"Digite o código de ativação que chegou no seu e-mail.":"Type the activation code that arrived in your e-mail.","Código de ativação":"Activation code",
"Ativar e baixar a plataforma":"Activate and download the platform","Depois de baixar: descompacte, rode":"After downloading: unzip it, run",
"e abra o endereço indicado no arquivo LEIA-ME. No primeiro acesso, crie o seu usuário e senha.":"and open the address given in the LEIA-ME (read me) file. On first access, create your user and password.",
"Digite o código.":"Type the code.","Código conferido. O download da sua plataforma começou.":"Code confirmed. Your platform download has started.",
"Código conferido. A equipe Physis envia a plataforma montada para você em breve.":"Code confirmed. The Physis team will send you the assembled platform soon.",
"Muitas tentativas. Espere alguns minutos e tente de novo.":"Too many attempts. Wait a few minutes and try again.",
"Instalação ou código não conferem. Confira o e-mail.":"Installation or code do not match. Check the e-mail."};</script>""" + _PX_JS + r"""<script>
PX.titulo("Ativar a plataforma");
var n="__NUMERO__",b=document.getElementById("ok"),m=document.getElementById("msg"),c=document.getElementById("codigo");
function dizer(t,e){PX.por(m,t);m.className=e?"erro":"ok";}
c.addEventListener("keydown",function(e){if(e.key==="Enter")b.click();});
b.onclick=function(){var v=c.value.trim();if(!v){dizer("Digite o código.",true);c.focus();return;}b.disabled=true;dizer("Conferindo…",false);
fetch("/api/ativar/"+encodeURIComponent(n),{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({codigo:v})}).then(function(r){
var t=r.headers.get("Content-Type")||"";if(r.ok&&t.indexOf("zip")>=0)return r.blob().then(function(z){var u=URL.createObjectURL(z),a=document.createElement("a");a.href=u;a.download="physis-"+n+".zip";document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(u);},4000);dizer("Código conferido. O download da sua plataforma começou.",false);});
return r.json().then(function(j){dizer(j.ok?"Código conferido. A equipe Physis envia a plataforma montada para você em breve.":(j.erro==="muitas tentativas; espere alguns minutos"?"Muitas tentativas. Espere alguns minutos e tente de novo.":"Instalação ou código não conferem. Confira o e-mail."),!j.ok);});
}).catch(function(){dizer("Sem resposta do servidor. Tente de novo.",true);}).then(function(){b.disabled=false;});};
</script></body></html>""").replace("__LOGO__", _PX_LOGO)


PAGINA_ENTRAR = (r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Entrar · Gestão Physis</title>""" + _PX_CEDO + _PX_CSS + r"""</style></head><body>""" + _PX_FAIXA.replace("__TITULO__", "Gestão Physis") + r"""<main id="conteudo" tabindex="-1">
<p class="t2" id="sub" data-pt="">Entre com o seu e-mail da Physis e a sua senha.</p>
<div class="cartao"><div id="caixa-nome" hidden><label for="nome" data-pt="">Seu nome</label><input id="nome" autocomplete="name"></div>
<div><label for="usuario" data-pt="">E-mail</label><input id="usuario" type="email" autocomplete="username" inputmode="email"></div>
<div><label for="senha" data-pt="">Senha</label><input id="senha" type="password" autocomplete="current-password"></div>
<div id="caixa-codigo" hidden><label for="codigo" data-pt="">Código do aplicativo autenticador</label><input id="codigo" autocomplete="one-time-code" inputmode="numeric" aria-describedby="dica-codigo">
<p class="t2" id="dica-codigo" data-pt="">6 números do aplicativo, ou um dos códigos de recuperação.</p></div>
<div id="caixa-termos" hidden><label class="linha"><input type="checkbox" id="termos"> <span id="termos-txt"></span></label></div>
<button type="button" id="ok" class="principal" data-pt="">Entrar</button><p id="msg" role="status" aria-live="polite"></p></div>
<p class="t2 depois"><a href="/conta/esqueci" data-pt="">Esqueci a senha</a></p></main>""" + _PX_RODAPE + r"""<script>window.PX_EN={"Entrar":"Sign in",
"Entre com o seu e-mail da Physis e a sua senha.":"Sign in with your Physis e-mail and your password.","Senha":"Password",
"Código do aplicativo autenticador":"Authenticator app code","6 números do aplicativo, ou um dos códigos de recuperação.":"The 6 digits from the app, or one of your recovery codes.",
"Primeira entrada neste servidor: quem criar esta conta passa a ser da direção (administradora). Use uma senha de pelo menos 12 caracteres.":"First sign-in on this server: whoever creates this account becomes management (administrator). Use a password of at least 12 characters.",
"Criar conta e entrar":"Create account and sign in","Informe o e-mail e a senha.":"Enter your e-mail and password.","Digite o código do aplicativo.":"Type the app code.",
"Entrando…":"Signing in…","Esta conta usa verificação em duas etapas. Digite o código do aplicativo.":"This account uses two-step verification. Type the app code.",
"E-mail ou senha não conferem.":"E-mail or password do not match."};</script>""" + _PX_JS + r"""<script>
PX.titulo("Entrar"," · Gestão Physis");
var criar=false,versao=null,b=document.getElementById("ok"),m=document.getElementById("msg");
function dizer(t,e){PX.por(m,t);m.className=e?"erro":"ok";}
fetch("/api/instancia",{cache:"no-store"}).then(function(r){return r.json();}).then(function(j){versao=(j&&j.termos_versao)||null;if(j&&j.tem_conta===false){criar=true;document.getElementById("caixa-nome").hidden=false;
PX.por(document.getElementById("sub"),"Primeira entrada neste servidor: quem criar esta conta passa a ser da direção (administradora). Use uma senha de pelo menos 12 caracteres.");document.getElementById("senha").autocomplete="new-password";PX.por(b,"Criar conta e entrar");
if(versao){PX.por(document.getElementById("termos-txt"),"Li e aceito os Termos de uso e a Política de privacidade da Physis (versão {0}).",[versao]);document.getElementById("caixa-termos").hidden=false;}}});
["usuario","senha","nome","codigo"].forEach(function(i){document.getElementById(i).addEventListener("keydown",function(e){if(e.key==="Enter")b.click();});});
b.onclick=function(){var u=document.getElementById("usuario").value.trim(),s=document.getElementById("senha").value,n=document.getElementById("nome").value.trim(),cx=document.getElementById("caixa-codigo");
if(!u||!s){dizer("Informe o e-mail e a senha.",true);return;}var corpo={nome:n||u,usuario:u,senha:s};
if(!cx.hidden){corpo.codigo=document.getElementById("codigo").value.trim();if(!corpo.codigo){dizer("Digite o código do aplicativo.",true);document.getElementById("codigo").focus();return;}}
if(criar&&versao){if(!document.getElementById("termos").checked){dizer("Para criar a conta, marque que leu e aceita os termos.",true);document.getElementById("termos").focus();return;}corpo.consentimento={versao:versao,aceito:true};}
b.disabled=true;dizer("Conferindo…",false);
fetch(criar?"/api/conta/criar":"/api/conta/entrar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(corpo)})
.then(function(r){return r.json();}).then(function(j){if(j.ok){dizer("Entrando…",false);location.reload();}
else if(j.precisa_2fa&&cx.hidden){cx.hidden=false;document.getElementById("codigo").focus();dizer("Esta conta usa verificação em duas etapas. Digite o código do aplicativo.",false);b.disabled=false;}
else{dizer(j.erro||"E-mail ou senha não conferem.",true);b.disabled=false;}})
.catch(function(){dizer("Sem resposta do servidor.",true);b.disabled=false;});};
</script></body></html>""").replace("__LOGO__", _PX_LOGO)


# Páginas dos fluxos de conta, servidas pelo próprio servidor (as telas só precisam pôr os links):
#   /conta/esqueci  /conta/nova-senha#t=…  /conta/confirmar#t=…  /conta/convite#t=…
# O código vem depois de "#": o navegador não o envia ao servidor nem a proxies; a página o tira da barra de endereço.
PAGINA_CONTA = (r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conta · Physis</title>""" + _PX_CEDO + _PX_CSS + r"""</style></head><body>""" + _PX_FAIXA.replace("__TITULO__", "Conta Physis") + r"""<main id="conteudo" tabindex="-1">
<p class="t2" id="sub"></p>
<form class="cartao" id="f" novalidate>
<div id="c-email" hidden><label for="email" data-pt="">E-mail</label><input id="email" type="email" autocomplete="username" inputmode="email"></div>
<div id="c-token" hidden><label for="token" data-pt="">Código que chegou no e-mail</label><input id="token" autocomplete="one-time-code"></div>
<div id="c-nome" hidden><label for="nome" data-pt="">Seu nome</label><input id="nome" autocomplete="name"></div>
<div id="c-senha" hidden><label for="senha" data-pt="">Senha nova</label><input id="senha" type="password" autocomplete="new-password" aria-describedby="dica">
<p class="t2" id="dica" data-pt="">Pelo menos 12 caracteres. Uma frase com palavras suas é o melhor; não precisa de símbolos.</p></div>
<div id="c-senha2" hidden><label for="senha2" data-pt="">Repita a senha nova</label><input id="senha2" type="password" autocomplete="new-password"></div>
<div id="c-termos" hidden><label class="linha"><input type="checkbox" id="termos"> <span id="termos-txt"></span></label></div>
<button type="submit" id="ok" class="principal" data-pt="">Continuar</button><p id="msg" role="status" aria-live="polite"></p></form>
<p class="t2 depois"><a href="/gestao" data-pt="">Ir para a entrada</a></p></main>""" + _PX_RODAPE + r"""<script>window.PX_EN={"Conta Physis":"Physis account","Código que chegou no e-mail":"Code from the e-mail",
"Senha nova":"New password","Pelo menos 12 caracteres. Uma frase com palavras suas é o melhor; não precisa de símbolos.":"At least 12 characters. A phrase in your own words works best; no symbols needed.",
"Repita a senha nova":"Repeat the new password","Continuar":"Continue","Ir para a entrada":"Go to sign-in","Cole o código do e-mail.":"Paste the code from the e-mail.",
"Convite para {0} ({1}) em {2}. Escolha o seu nome e a sua senha.":"Invitation for {0} ({1}) at {2}. Choose your name and your password.",
"direção":"management","equipe":"team","cliente":"client","Criar a minha conta":"Create my account","Digite o e-mail.":"Type your e-mail.",
"E-mail confirmado. Já pode entrar na plataforma.":"E-mail confirmed. You can now sign in to the platform.",
"A senha precisa de pelo menos 12 caracteres.":"The password needs at least 12 characters.","As duas senhas não são iguais.":"The two passwords are not the same.",
"Senha nova gravada. Indo para a entrada…":"New password saved. Going to sign-in…","Digite o seu nome.":"Type your name.","Conta criada. Entrando…":"Account created. Signing in…",
"Digite o e-mail da sua conta. Se ele tiver conta, chega um link para criar uma senha nova.":"Type your account e-mail. If it has an account, a link to create a new password will arrive.",
"Escolha a senha nova. Ao gravar, todas as sessões abertas da conta são encerradas.":"Choose the new password. When you save it, every open session of the account is closed.",
"Confirmar o e-mail":"Confirm your e-mail","Confirme que este e-mail é seu.":"Confirm that this e-mail is yours.","Aceitar o convite":"Accept the invitation",
"Conferindo o convite…":"Checking the invitation…","Gravar a senha nova":"Save the new password","Conferir o convite":"Check the invitation",
"Cole o código que chegou no e-mail do convite.":"Paste the code from the invitation e-mail.",
"Se este e-mail tiver conta, enviamos um link para criar uma senha nova. Ele vale 30 minutos.":"If this e-mail has an account, we sent a link to create a new password. It is valid for 30 minutes."};</script>""" + _PX_JS + r"""<script>
var modo=location.pathname.replace(/\/+$/,"").split("/").pop(),versao=null;
var tk=(location.hash.match(/[#&]t=([A-Za-z0-9_-]+)/)||[])[1]||"";
if(tk&&history.replaceState)history.replaceState(null,"",location.pathname);
function $(i){return document.getElementById(i);}
function mostrar(){for(var i=0;i<arguments.length;i++)$("c-"+arguments[i]).hidden=false;}
function dizer(t,e){PX.por($("msg"),t||"");$("msg").className=e?"erro":"ok";}
function falha(){dizer("Sem resposta do servidor. Tente de novo.",true);$("ok").disabled=false;}
function post(rota,corpo){return fetch(rota,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(corpo)}).then(function(r){return r.json();});}
function codigo(){return tk||$("token").value.trim();}
function ver(){if(!codigo()){dizer("Cole o código do e-mail.",true);$("token").focus();return;}
post("/api/conta/convite/ver",{token:codigo()}).then(function(j){if(!j.ok){dizer(j.erro,true);return;}tk=codigo();$("c-token").hidden=true;
PX.por($("sub"),"Convite para {0} ({1}) em {2}. Escolha o seu nome e a sua senha.",[j.email,({administrador:"direção",operador:"equipe",cliente:"cliente"}[j.papel]||j.papel),j.org]);
$("nome").value=j.nome||"";mostrar("nome","senha","senha2");versao=j.termos_versao||null;
if(versao){PX.por($("termos-txt"),"Li e aceito os Termos de uso e a Política de privacidade da Physis (versão {0}).",[versao]);mostrar("termos");}
PX.por($("ok"),"Criar a minha conta");modo="convite2";dizer("",false);$("nome").focus();}).catch(falha);}
function enviar(){var b=$("ok");
if(modo==="esqueci"){var em=$("email").value.trim();if(!em){dizer("Digite o e-mail.",true);$("email").focus();return;}b.disabled=true;
post("/api/conta/esqueci",{usuario:em}).then(function(j){dizer(j.mensagem||j.erro,!j.ok);b.disabled=false;}).catch(falha);return;}
if(modo==="confirmar"){if(!codigo()){dizer("Cole o código do e-mail.",true);$("token").focus();return;}
post("/api/conta/confirmar",{token:codigo()}).then(function(j){dizer(j.ok?"E-mail confirmado. Já pode entrar na plataforma.":j.erro,!j.ok);}).catch(falha);return;}
if(modo==="convite"){ver();return;}
var s=$("senha").value;if(s.length<12){dizer("A senha precisa de pelo menos 12 caracteres.",true);$("senha").focus();return;}
if(s!==$("senha2").value){dizer("As duas senhas não são iguais.",true);$("senha2").focus();return;}
if(modo==="nova-senha"){if(!codigo()){dizer("Cole o código do e-mail.",true);$("token").focus();return;}b.disabled=true;
post("/api/conta/nova-senha",{token:codigo(),senha:s}).then(function(j){if(j.ok){dizer("Senha nova gravada. Indo para a entrada…",false);setTimeout(function(){location.href="/gestao";},1500);}else{dizer(j.erro,true);b.disabled=false;}}).catch(falha);return;}
if(modo==="convite2"){var n=$("nome").value.trim();if(!n){dizer("Digite o seu nome.",true);$("nome").focus();return;}
if(versao&&!$("termos").checked){dizer("Para criar a conta, marque que leu e aceita os termos.",true);$("termos").focus();return;}
var corpo={token:tk,nome:n,senha:s};if(versao)corpo.consentimento={versao:versao,aceito:true};b.disabled=true;
post("/api/conta/convite/aceitar",corpo).then(function(j){if(j.ok){dizer("Conta criada. Entrando…",false);setTimeout(function(){location.href=j.papel==="cliente"?"/":"/gestao";},800);}else{dizer(j.erro,true);b.disabled=false;}}).catch(falha);}}
var T={esqueci:["Esqueci a senha","Digite o e-mail da sua conta. Se ele tiver conta, chega um link para criar uma senha nova."],
"nova-senha":["Senha nova","Escolha a senha nova. Ao gravar, todas as sessões abertas da conta são encerradas."],
confirmar:["Confirmar o e-mail","Confirme que este e-mail é seu."],convite:["Aceitar o convite","Conferindo o convite…"]};
var t=T[modo]||T.esqueci;if(!T[modo])modo="esqueci";PX.por($("tit"),t[0]);PX.por($("sub"),t[1]);PX.titulo(t[0]);
$("f").addEventListener("submit",function(e){e.preventDefault();enviar();});
if(modo==="esqueci")mostrar("email");
else if(modo==="nova-senha"){if(!tk)mostrar("token");mostrar("senha","senha2");PX.por($("ok"),"Gravar a senha nova");}
else if(modo==="confirmar"){if(!tk)mostrar("token");else enviar();}
else if(modo==="convite"){if(!tk){mostrar("token");PX.por($("ok"),"Conferir o convite");PX.por($("sub"),"Cole o código que chegou no e-mail do convite.");}else ver();}
</script></body></html>""").replace("__LOGO__", _PX_LOGO)


# ── Esquemas dos corpos JSON das rotas ligadas em 15/11/2026 (entram em seg.ESQUEMAS; validação estrita) ──
_S, _NUM = str, (int, float)
ESQUEMAS_ROTAS = {
    # documento para comentários (documentos.py; docs/EXPORTACAO.md)
    "doc_publicar": {"titulo": (_S, 300, True), "html": (_S, documentos_mod.HTML_MAX, True), "origem": (_S, 2000, False),
                     "nota": (_S, 1000, False)},
    "doc_versao": {"html": (_S, documentos_mod.HTML_MAX, True), "nota": (_S, 1000, False)},
    "doc_comentar": {"texto": (_S, documentos_mod.TEXTO_MAX, False), "sugestao": (_S, documentos_mod.TEXTO_MAX, False),
                     "paragrafo": (_S, 40, False), "versao": (int, 10**6, False), "pai": (int, 10**12, False)},
    "doc_texto": {"texto": (_S, documentos_mod.TEXTO_MAX, True)},
    "doc_resolver": {"resolvido": (bool, None, False)},
    "doc_sugestao": {"aceitar": (bool, None, True)},
    "doc_convite": {"nome": (_S, 80, True), "email": (_S, 160, False), "dias": (_NUM, documentos_mod.DIAS_MAX, False),
                    "pode_comentar": (bool, None, False)},
    "doc_arquivar": {"arquivado": (bool, None, False)},
    # painel municipal (municipio.py; docs/MUNICIPIO.md)
    "mun_config": {"ibge": (_S, 7, True), "uf": (_S, 2, True), "municipio": (_S, 80, False), "lat": (_NUM, 90, False),
                   "lon": (_NUM, 180, False), "orgao": (_S, 120, False), "telefone_emergencia": (_S, 20, False),
                   "limiares": (dict, 8, False), "rios": (list, municipio_mod.MAX_RIOS, False),
                   "pluviometros": (list, municipio_mod.MAX_PLUV, False)},
    "mun_bairro": {"id": (_S, 80, True), "nome": (_S, 80, False), "risco": ((_S, int), 20, False), "estacoes": (list, 20, False),
                   "rio": (_S, 40, False), "apagar": (bool, None, False)},
    # certificação assistida (evidencias.py; docs/EVIDENCIAS.md)
    "evid_anexo": {"cert": (_S, 60, True), "criterio": (_S, 80, True), "nome": (_S, 160, True), "data": (_S, 10, True),
                   "validade": (_S, 10, False), "responsavel": (_S, 200, False), "obs": (_S, 2000, False), "arquivo": (_S, 40, False)},
    "evid_remover": {"id": (int, 10**12, True)},
    # profissionais parceiros (parceiros.py; docs/PARCEIROS.md). Conteúdo (CPF, UF, especialidade...) o módulo confere.
    "parc_cadastro": {"tipo": (_S, 2, False), "documento": (_S, 20, False), "nome": (_S, 160, False), "nome_publico": (_S, 120, False),
                      "conselho": (_S, 10, False), "registro": (_S, 40, False), "registro_uf": (_S, 2, False),
                      "email": (_S, 160, False), "telefone": (_S, 20, False), "especialidades": (list, 10, False),
                      "regioes": (list, 60, False), "descricao": (_S, 1000, False), "consentimento": (bool, None, False)},
    "parc_orcamento": {"parceiro": ((int, _S), 10**9, True), "servico": (_S, 40, False), "municipio": (_S, 80, False), "uf": (_S, 2, False),
                       "ibge": (_S, 7, False), "nome": (_S, 120, False), "email": (_S, 160, False), "telefone": (_S, 20, False),
                       "descricao": (_S, 2000, False), "consentimento": (bool, None, False)},
    "parc_documento": {"tipo": (_S, 20, True), "validade": (_S, 10, False), "descricao": (_S, 400, False), "arquivo": (_S, 40, False)},
    "parc_doc_remover": {"id": (int, 10**12, True)},
    "parc_curadoria": {"status": (_S, 20, True), "motivo": (_S, 600, False)},
    "parc_avaliacao": {"nota": (int, 5, True), "pedido": (_S, 40, True), "comentario": (_S, 1000, False)},
    # Mapeamento (mapeamento.py, ifc.py; docs/MAPEAMENTO.md): corpos JSON; arquivos (upload, IFC para ler) vão em bytes
    "map_contexto": {"lote": (dict, 5000, False), "irradiacao_solar": (dict, 10, False), "local": (dict, 20, False)},
    "map_incidencia": {"H": (list, 12, False), "lat": ((int, float), 90, True), "superficies": (list, 2000, True),
                       "grade": ((dict, list), 1_000_000, False), "caixas": (list, 5000, False), "albedo": ((int, float), 1, False),
                       "fonte_irradiacao": (_S, 300, False)},
    "map_planta_solar": {"poligono": (list, 5000, True), "modulo": (dict, 60, True), "arranjo": (dict, 60, True),
                         "lat": ((int, float), 90, False), "obstaculos": (list, 5000, False)},
    "map_ifc": {"projeto": (dict, 20, False), "site": (dict, 20, True), "elementos": (list, 5000, False), "premissas": (dict, 60, False)},
    # Simulação (physis_hub/simulacao; docs/SIMULACAO.md): cada parte tem a sua entrada; o motor confere os campos e o tamanho
    # (simulacao.LIMITES). Aqui só: objeto JSON e campos de primeiro nível conhecidos (lido sem modo estrito).
    "sim_corpo": {},
}
ESQUEMAS_ROTAS["parc_editar"] = {k: v for k, v in ESQUEMAS_ROTAS["parc_cadastro"].items() if k != "consentimento"}
for _k, _v in ESQUEMAS_ROTAS.items():
    seg.ESQUEMAS.setdefault(_k, _v)
for _k, _v in fornecedores_mod.ESQUEMAS.items():          # fornecedores e equipamentos (docs/FORNECEDORES.md)
    seg.ESQUEMAS.setdefault(_k, _v)
for _k, _v in frota_mod.ESQUEMAS.items():                 # frota e combustível (docs/FROTA.md, em desenvolvimento)
    seg.ESQUEMAS.setdefault(_k, _v)
for _k, _v in validacao_mod.ESQUEMAS.items():             # validação planejado × gerado (docs/VALIDACAO_MV.md, em desenvolvimento)
    seg.ESQUEMAS.setdefault(_k, _v)


def esquema_documento(caminho: str) -> str | None:
    """Esquema do corpo de um POST /api/documentos…; None = rota que o módulo não conhece (ele responde 404)."""
    p = [x for x in caminho.split("/") if x][2:]
    if not p:
        return "doc_publicar"
    r = p[1:]
    if r == ["versoes"]:
        return "doc_versao"
    if r == ["comentarios"]:
        return "doc_comentar"
    if len(r) == 3 and r[0] == "comentarios":
        return {"editar": "doc_texto", "apagar": "vazio", "resolver": "doc_resolver", "sugestao": "doc_sugestao"}.get(r[2])
    if r == ["convites"]:
        return "doc_convite"
    if len(r) == 3 and r[0] == "convites" and r[2] == "revogar":
        return "vazio"
    return {"arquivar": "doc_arquivar", "apagar": "vazio"}.get(r[0]) if len(r) == 1 else None


# ── Demonstrações públicas (demos/, geradas por demos/gerar_demos.py): só leitura, lista fechada ──
DEMOS = {"sustainkit": "physis-demo-sustainkit.html", "scada": "physis-demo-scada.html",
         "monitoramento": "physis-demo-monitoramento.html", "planejador": "physis-demo-planejador.html",
         "plataforma": "physis-demo-cliente.html"}


def arquivo_demo(caminho: str) -> Path | None:
    """/demo/<nome>[/] -> arquivo da demo: no pacote, web/demos/; no repositório, demos/ na raiz."""
    m = re.fullmatch(r"/demo/([a-z]+)/?", caminho)
    nome = DEMOS.get(m.group(1)) if m else None
    if not nome:
        return None
    return next((p for p in (WEB / "demos" / nome, WEB.parent.parent / "demos" / nome) if p.is_file()), None)


# ── Download do app nativo (docs/APP_NATIVO.md, seção 12). Lista fechada: nada do pedido vira caminho ──
APK_MIME = "application/vnd.android.package-archive"
APP_DOWNLOAD = {"/app/baixar": "baixar.html", "/app/baixar/": "baixar.html", "/app/android.apk": "android.apk",
                "/app/android.apk.sha256": "android.apk"}
_SHA_CACHE: dict = {}


def arquivo_app(nome: str) -> Path | None:
    """PHYSIS_APP_DOWNLOAD (só ela, se definida); senão <pacote>/app-download e, no repositório, o que o
    app-nativo/scripts/publicar_baixar.py deixou em app-nativo/site/publicar (a página modelo, sem APK, também vale)."""
    env = (os.environ.get("PHYSIS_APP_DOWNLOAD") or "").strip()
    pastas = [Path(env)] if env else [WEB.parent / "app-download", WEB.parent.parent / "app-nativo" / "site" / "publicar"]
    for p in pastas:
        if (p / nome).is_file():
            return p / nome
    if nome == "baixar.html" and not env:
        modelo = WEB.parent.parent / "app-nativo" / "site" / "baixar.html"
        if modelo.is_file():
            return modelo
    return None


def sha256_arquivo(p: Path) -> str:
    """SHA-256 calculado do próprio arquivo servido (guardado enquanto tamanho e data não mudam)."""
    st = p.stat()
    chave = (str(p), st.st_size, st.st_mtime_ns)
    if chave not in _SHA_CACHE:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for bloco in iter(lambda: f.read(1 << 20), b""):
                h.update(bloco)
        _SHA_CACHE.clear()
        _SHA_CACHE[chave] = h.hexdigest()
    return _SHA_CACHE[chave]


# ── Termos de uso, política de privacidade e acessibilidade: texto de sistema/physis-juridico.js (minuta) ──
JURIDICO_ROTAS = {"/termos": "termos", "/privacidade": "privacidade", "/acessibilidade": "acessibilidade"}
_JURIDICO_CACHE: dict = {}


def ler_juridico() -> dict | None:
    """Os textos gerados por ferramentas/gerar_juridico.py. No pacote: web/physis-juridico.js (montar.py copia)."""
    arq = next((p for p in (WEB / "physis-juridico.js", WEB.parent / "programas" / "physis-juridico.js",
                            WEB.parent.parent / "sistema" / "physis-juridico.js") if p.is_file()), None)
    if not arq:
        return None
    chave = (str(arq), arq.stat().st_mtime_ns)
    if _JURIDICO_CACHE.get("chave") == chave:
        return _JURIDICO_CACHE["dados"]
    try:
        dados = json.loads(arq.read_text(encoding="utf-8").split("window.PHYSIS_JURIDICO = ", 1)[1].rstrip().rstrip(";"))
    except (OSError, IndexError, ValueError):
        return None
    if not isinstance(dados, dict):
        return None
    _JURIDICO_CACHE.update(chave=chave, dados=dados)
    return dados


def _md_linha(s: str) -> str:
    """Escapa tudo e só depois devolve o negrito do markdown (nada do arquivo vira etiqueta HTML)."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_mod.escape(str(s), quote=False))


def md_para_html(paragrafos: list) -> str:
    """Markdown simples das minutas: parágrafo, lista (- ou 1.), tabela (| a | b |) e **negrito**."""
    out, atual, buf = [], None, []

    def despejar():
        if atual in ("ul", "ol") and buf:
            out.append(f"<{atual}>" + "".join(f"<li>{i}</li>" for i in buf) + f"</{atual}>")
        elif atual == "tabela" and buf:
            cab, corpo = buf[0], buf[1:]
            out.append('<div class="rolar" role="region" tabindex="0" aria-label="Tabela" data-pt-aria="Tabela"><table><thead><tr>'
                       + "".join(f'<th scope="col">{_md_linha(c)}</th>' for c in cab) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_md_linha(c)}</td>" for c in r) + "</tr>" for r in corpo)
                       + "</tbody></table></div>")
        buf.clear()

    for p in paragrafos or []:
        s = str(p).strip()
        if not s:
            continue
        if s.startswith("|") and s.endswith("|"):
            novo = "tabela"
        elif re.match(r"^[-*] ", s):
            novo = "ul"
        elif re.match(r"^\d+[.)] ", s):
            novo = "ol"
        else:
            novo = "p"
        if novo != atual:
            despejar()
            atual = novo
        if novo == "tabela":
            celulas = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in celulas if c):
                continue                                   # linha |---|---| do markdown
            buf.append(celulas)
        elif novo in ("ul", "ol"):
            buf.append(_md_linha(re.sub(r"^([-*]|\d+[.)]) ", "", s, count=1)))
        else:
            out.append(f"<p>{_md_linha(s)}</p>")
    despejar()
    return "\n".join(out)


_PX_CSS_JURIDICO = r"""main{max-width:860px}.juridico{overflow-wrap:anywhere}
.juridico h2{font:500 1.3rem/1.3 var(--titulo);color:var(--acao);margin:28px 0 8px}.juridico p,.juridico li{margin:6px 0}
.juridico ol,.juridico ul{padding-left:1.4em}
.rolar{overflow-x:auto;max-width:100%;border:1px solid var(--linha);border-radius:8px;margin:10px 0;background:var(--sup)}
.rolar table{border-collapse:collapse;width:100%;min-width:480px}.rolar th,.rolar td{border-bottom:1px solid var(--linha);padding:8px 10px;text-align:left;vertical-align:top}
.rolar th{background:var(--fundo)}
.aviso{background:var(--sup);border:1px solid var(--linha);border-left:4px solid var(--acao);border-radius:8px;padding:10px 14px;margin:0 0 12px}
.so-en{display:none}html[lang=en] .so-en{display:block}
.px-docs{list-style:none;margin:0 0 8px;padding:0;display:flex;flex-wrap:wrap;gap:0 20px}.px-docs a{display:inline-flex;align-items:center;min-height:44px;font-weight:600}
.px-docs a[aria-current]{color:var(--tinta);text-decoration:none}
"""


def pagina_juridico(chave: str) -> str | None:
    """Página Physis (PT/EN, claro/escuro) com um dos textos jurídicos. O texto é a minuta em português;
    em inglês, a página avisa que a tradução sai depois da revisão jurídica (não inventamos texto legal)."""
    dados = ler_juridico()
    bloco = (dados or {}).get(chave)
    if not isinstance(bloco, dict) or not bloco.get("blocos"):
        return None
    titulo = html_mod.escape(str(bloco.get("titulo") or ""))
    corpo = []
    for b in bloco["blocos"]:
        if b.get("t"):
            corpo.append(f"<h2>{_md_linha(b['t'])}</h2>")
        corpo.append(md_para_html(b.get("p") or []))
    atual = ' aria-current="page"'
    docs = "".join(f'<li><a href="{r}"{atual if k == chave else ""} data-pt="">{n}</a></li>'
                   for r, k, n in (("/termos", "termos", "Termos de uso"), ("/privacidade", "privacidade", "Política de privacidade"),
                                   ("/acessibilidade", "acessibilidade", "Acessibilidade")))
    situacao = html_mod.escape(str(dados.get("situacao") or ""))
    versao = html_mod.escape(str(dados.get("versao") or ""))
    return ((r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITULO__ · Physis</title>""" + _PX_CEDO + _PX_CSS + _PX_CSS_JURIDICO + r"""</style></head><body>"""
             + _PX_FAIXA.replace("__TITULO__", '<span data-pt="">__TITULO__</span>') + r"""<main id="conteudo" tabindex="-1">
<p class="aviso"><strong data-pt="">__SITUACAO__</strong> · <span data-pt="">versão de</span> __VERSAO__. <span data-pt="">Dados entre colchetes ainda serão definidos.</span></p>
<p class="aviso so-en" lang="en">This text is a draft available in Portuguese only. The English version will be published after the legal review.</p>
<nav aria-label="Documentos" data-pt-aria="Documentos"><ul class="px-docs">__DOCS__</ul></nav>
<article class="juridico" lang="pt-BR">__CORPO__</article>
</main>""" + _PX_RODAPE + r"""<script>window.PX_EN={"Termos de uso":"Terms of use","Política de privacidade (LGPD)":"Privacy policy (LGPD)",
"Política de privacidade":"Privacy policy","Encontrou alguma barreira? Conte para nós":"Found a barrier? Tell us","Documentos":"Documents",
"Minuta em revisão jurídica":"Draft under legal review","versão de":"version of","Tabela":"Table",
"Dados entre colchetes ainda serão definidos.":"Data in square brackets is still to be defined."};</script>""" + _PX_JS
             + r"""<script>PX.titulo(document.querySelector("#tit [data-pt]").getAttribute("data-pt"));</script></body></html>""")
            .replace("__LOGO__", _PX_LOGO).replace("__TITULO__", titulo).replace("__SITUACAO__", situacao)
            .replace("__VERSAO__", versao).replace("__DOCS__", docs).replace("__CORPO__", "\n".join(corpo)))


def rodar_diario(fn, parar: threading.Event, passo: float = 86400.0, inicio: float = 300.0) -> None:
    """Roda fn() 5 min depois de ligar e depois uma vez por dia (retenção LGPD dos documentos)."""
    espera = inicio
    while not parar.wait(espera):
        try:
            fn()
        except Exception as exc:      # noqa: BLE001 — um erro não derruba o servidor
            print("tarefa diária:", type(exc).__name__, exc)
        espera = passo


def criar_manipulador(hub: Hub, token: str | None, instancia: dict | None = None, clima=None, irradiacao=None):
    instancia = instancia if instancia is not None else ler_instancia()
    if irradiacao is None:
        irradiacao = gis_mod.Irradiacao(hub)
    saude = saude_mod.Saude(hub)
    # MED/PUL pelo receptor, pelo /api/v6/linha e pelo MQTT: o hub entrega à Saúde antes do adaptador genérico
    # (protocolo.TIPOS_SAUDE; PHYSIS_SAUDE_V6=0 desliga). Avisos novos (dose esquecida, crise) saem pela fila de e-mail.
    def receptor_saude(linha: str, origem: str) -> dict:
        r = saude.registrar_evento(linha, origem=origem)
        for aid in r.get("alertas", []):
            threading.Thread(target=correio.enviar_fila, args=(hub, f"saude-{aid}"), daemon=True).start()
        return r
    if getattr(hub, "saude_receptor", None) is None:
        hub.saude_receptor = receptor_saude
    if clima is None:
        rx = os.environ.get("PHYSIS_RX_URL")
        clima = clima_mod.Clima(hub, receptor_url=rx, enviar_local=clima_mod.receptor_local(rx) if rx else None)
    exige_login = bool(instancia.get("login"))
    csp = politica(os.environ.get("PHYSIS_CHAMADAS") or instancia.get("chamadas"))
    csp_planejador = csp.replace("'wasm-unsafe-eval'", "'wasm-unsafe-eval' 'unsafe-eval'", 1)
    fabricar = fabricante(instancia)
    url_publica = (os.environ.get("PHYSIS_URL_PUBLICA") or instancia.get("url_publica") or "").rstrip("/")
    # Editais e eventos (editais.py): listas públicas buscadas pelo servidor, com cache em arquivo
    pasta_editais = Path(os.environ.get("PHYSIS_EDITAIS_PASTA") or (Path(banco_da_instancia(instancia)).resolve().parent / "editais"))
    editais_col = editais_mod.Coletor(pasta_editais, tipo="edital")
    # "Permitir suporte": acesso da equipe Physis com prazo, só pela VPN (PHYSIS_SUPORTE_REDES); docs/SUPORTE_REMOTO.md
    suporte = suporte_mod.SuporteRemoto(hub)
    cep_srv = cep_mod.ServicoCEP(hub)                       # CEP → endereço e coordenadas (só o CEP sai do servidor)
    uploads_map = mapeamento_mod.Uploads(hub._db)          # arquivos do cliente da aba Mapeamento (GeoJSON, KML, SHP em zip…)
    eventos_col = editais_mod.Coletor(pasta_editais, tipo="evento")
    # Aprendizado local (sem internet), robôs com regras (+ IA local opcional) e alertas de clima por e-mail/WhatsApp
    aprendizado = aprendizado_mod.Aprendizado(hub)
    robos = robos_mod.criar_robos({"hub": hub, "editais": editais_col,
                                   "suporte_email": os.environ.get("PHYSIS_SUPORTE_EMAIL") or instancia.get("suporte_email") or ""})
    # emissão de documentos (modelos → rascunho → revisão → aprovação → emissão) e biblioteca; a IA é a mesma dos robôs
    docauto = documentos_auto_mod.DocumentosAuto(hub, ia=robos["suporte"].ia)
    # indicadores da plataforma (D18): só metadados; coleta de 5 em 5 min no laço do hub (ver o fim de iniciar)
    indicadores = indicadores_mod.Indicadores(hub, robos=robos)
    hub.indicadores = indicadores                 # o laço de coleta (main) usa a mesma instância
    alertas = alertas_mod.AlertasClima(hub, aprendizado=aprendizado)
    # Documento para comentários, painel municipal e parceiros: criados no primeiro uso (cada um cria as suas tabelas)
    modulos_vivos: dict = {}
    modulos_trava = threading.Lock()

    def modulo(nome: str):
        with modulos_trava:
            if nome not in modulos_vivos:
                modulos_vivos[nome] = {"docs": lambda: documentos_mod.Documentos(hub),
                                       "municipio": lambda: municipio_mod.Municipio(hub, clima=clima, aprendizado=aprendizado),
                                       "parceiros": lambda: parceiros_mod.Parceiros(hub),
                                       "fornecedores": lambda: fornecedores_mod.Fornecedores(
                                           hub, pasta=fornecedores_mod.pasta_padrao(banco_da_instancia(instancia))),
                                       # intercâmbio com plataformas parceiras (docs/INTERCAMBIO.md): chave só no arquivo do servidor
                                       "intercambio": lambda: intercambio_mod.Intercambio(
                                           hub, instancia.get("intercambio_id") or os.environ.get("PHYSIS_INTERCAMBIO_ID") or hub.org,
                                           os.environ.get("PHYSIS_INTERCAMBIO_CHAVES") or instancia.get("intercambio_chaves")
                                           or (Path(banco_da_instancia(instancia)).resolve().parent / "intercambio-chaves.json"),
                                           cursos=lambda: instancia.get("cursos") or [])}[nome]()
            return modulos_vivos[nome]
    # Frota e combustível (docs/FROTA.md): criada já na partida, porque o hub entrega a ela cada linha VEI (com a trava do hub)
    frota = frota_mod.Frota(hub, pasta=frota_mod.pasta_padrao(banco_da_instancia(instancia)))
    modulos_vivos["frota"] = frota
    hub.frota_receptor = frota.receber_v6
    # Validação · planejado × gerado (docs/VALIDACAO_MV.md): lê o medido do hub e a frota; planos na tabela validacao_plano
    modulos_vivos["validacao"] = validacao_mod.Validacao(hub, frota=frota)
    cfg_pegada = pegada_mod.config_de(instancia)          # None = desligada (PHYSIS_PEGADA=0)
    # ── Segurança (seguranca.py; docs/SEGURANCA.md) ──
    proxies = seg.proxies_confiaveis()                  # PHYSIS_PROXY_CONFIAVEL: só deles vale X-Forwarded-*
    limites = seg.Limites()                             # PHYSIS_LIMITE_*: balde de fichas por IP
    chamadas_origem = origem_chamadas(os.environ.get("PHYSIS_CHAMADAS") or instancia.get("chamadas"))
    sem_chave = os.environ.get("PHYSIS_ACEITAR_SEM_CHAVE", "").strip()   # "1" aceita, "0" recusa, vazio: só rede local
    SEM_PAPEL = {"ok": False, "erro": "o seu papel não permite esta ação"}
    termos = seg.termos_versao()                        # versão dos Termos/Política (sistema/physis-juridico.js)
    # rotas da própria conta que funcionam sem token CSRF (ainda não há sessão) e mesmo com o consentimento pendente
    SEM_CSRF = ("/api/conta/entrar", "/api/conta/criar", "/api/conta/esqueci", "/api/conta/nova-senha", "/api/conta/confirmar",
                "/api/conta/convite/ver", "/api/conta/convite/aceitar")
    class Manipulador(BaseHTTPRequestHandler):
        # Cabecalhos de seguranca em toda resposta. As telas usam script e estilo dentro da pagina,
        # por isso 'unsafe-inline'; de fora do proprio servidor, so o servidor de chamadas da Physis, se configurado.
        def end_headers(self):
            # O Planejador (e só ele) precisa de 'unsafe-eval': o leitor BIM web-ifc monta funções ao rodar.
            # A liberação vale só para essa página; o resto da plataforma continua sem eval.
            eh_planejador = urlparse(getattr(self, "path", "") or "").path in ("/planejador", "/planejador/",
                                                                              "/demo/planejador", "/demo/planejador/")
            self.send_header("Content-Security-Policy", csp_planejador if eh_planejador else csp)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            # Permissions-Policy, COOP, CORP, X-Frame-Options e, só por HTTPS, HSTS (seguranca.cabecalhos_extra)
            for k, v in seg.cabecalhos_extra(self._https(), chamadas_origem):
                self.send_header(k, v)
            super().end_headers()

        server_version = "PhysisHub/0.1"
        sys_version = ""                     # não anuncia a versão do Python no cabeçalho Server

        def log_message(self, *a):          # silencioso; a saude fica em /api/saude
            pass

        def handle_one_request(self):
            self._corpo_lido = False          # cada pedido começa sem corpo lido
            self._respondeu = False
            self._status, inicio = 0, time.monotonic()
            try:
                super().handle_one_request()
                if self._status:              # indicadores da plataforma: só método, rota normalizada, código e tempo
                    indicadores.requisicao(getattr(self, "command", ""), getattr(self, "path", ""), self._status,
                                           (time.monotonic() - inicio) * 1000)
            except (ConnectionError, TimeoutError):
                self.close_connection = True          # quem chamou foi embora
            except Exception:
                # o rastro do erro vai só para o console do servidor; quem chamou recebe "erro interno", nunca o rastro
                traceback.print_exc(file=sys.stderr)
                self.close_connection = True
                if not self._respondeu:
                    try:
                        self._json(500, {"ok": False, "erro": "erro interno"})
                    except Exception:
                        pass

        def send_response(self, *a, **k):
            self._respondeu = True
            self._status = a[0] if a and isinstance(a[0], int) else int(k.get("code", 0) or 0)
            super().send_response(*a, **k)

        # ── Segurança: IP de verdade, HTTPS, rede local, papéis, limites e chaves dos aparelhos ──
        def _ip(self) -> str:
            return seg.ip_do_cliente(self.client_address[0], getattr(self, "headers", None) or {}, proxies)

        def _https(self) -> bool:
            return seg.eh_https(self.client_address[0], getattr(self, "headers", None) or {}, proxies)

        def _local(self) -> bool:
            return seg.eh_rede_local(self._ip())

        def _precisa_sessao(self) -> bool:
            """Com login na instalação, sempre; sem login, só quem chama de fora da rede local."""
            return exige_login or not self._local()

        def _cookie(self, valor: str, idade: int) -> str:
            return (f"physis_sessao={valor}; Path=/; Max-Age={idade}; HttpOnly; SameSite=Strict"
                    + ("; Secure" if self._https() else ""))

        def _exigir(self, minimo: str) -> dict | None:
            """Conta da sessão com pelo menos o papel pedido; senão responde 401 (sem sessão) ou 403 e devolve None.
            Com PHYSIS_CONSENTIMENTO_ESTRITO=1, sem o aceite da versão atual dos termos também 403 ({"consentimento": true})."""
            q = self._quem()
            if not q:
                self._json(401, {"ok": False, "erro": "entre com usuario e senha", "login": True})
                return None
            if seg.consentimento_estrito() and seg.consentimento_pendente(q):
                self._json(403, {"ok": False, "consentimento": True, "versao": termos,
                                 "erro": "Leia e aceite a versão atual dos Termos de uso e da Política de privacidade."})
                return None
            if not seg.pode(q, minimo):
                self._json(403, dict(SEM_PAPEL, confirmar_email=True) if q.get("confirmado") is False else SEM_PAPEL)
                return None
            return q

        def _sensivel(self, q: dict) -> bool:
            """Ações sensíveis pedem a senha de novo se o último login/reautenticação passou de PHYSIS_REAUT_MIN."""
            if seg.reauth_recente(hub, q):
                return True
            self._json(403, {"ok": False, "reautenticar": True, "erro": "Confirme a sua senha para continuar."})
            return False

        # ── Rotas ligadas em 15/11/2026 (docs: EXPORTACAO, MUNICIPIO, EVIDENCIAS, PARCEIROS, APP_NATIVO, PEGADA_SERVIDOR) ──
        def _conta_doc(self) -> dict | None:
            """Conta da sessão para as rotas de documento; sem o aceite dos termos atuais (modo estrito), não vale (o convite vale)."""
            q = self._quem()
            if q and seg.consentimento_estrito() and seg.consentimento_pendente(q):
                return None
            return q

        def _doc_resposta(self, r) -> None:
            codigo, obj = r
            if codigo == 429:
                return self._recusar(429, obj, {"Retry-After": str(obj.get("espera", 60))})
            return self._json(codigo, obj)

        def _intercambio(self, metodo: str, u, corpo: bytes, q: dict) -> None:
            """/api/intercambio/v1/* = a outra plataforma (assinatura HMAC, sem sessão, só HTTPS ou rede local/VPN);
            /api/intercambio/* = a direção desta instalação (recebidos: equipe). Ver docs/INTERCAMBIO.md."""
            ic = modulo("intercambio")
            if u.path.startswith(intercambio_mod.PREFIXO + "v1/"):
                cod, dados, cab = ic.rota_parceiro(metodo, u.path + ("?" + u.query if u.query else ""), self.headers, corpo,
                                                   self._ip(), self._https() or self._local())
                self.send_response(cod)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(dados)))
                for k, v in cab.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(dados)
                return
            conta = self._exigir(seg.EQUIPE if (metodo == "GET" and u.path == intercambio_mod.PREFIXO + "recebidos") else seg.DIRECAO)
            if not conta:
                return
            d = None
            if metodo == "POST":
                try:
                    d = json.loads(corpo.decode("utf-8")) if corpo else {}
                except (ValueError, UnicodeDecodeError):
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                if not isinstance(d, dict):
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                if u.path.endswith(("/parceiro/chave", "/parceiro/remover")) and not self._sensivel(conta):
                    return
            self._json(*ic.rota_admin(metodo, u.path, conta, d, q))

        def _enviar_bytes(self, dados: bytes, tipo: str, cabecalhos: dict | None = None) -> None:
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(dados)))
            for k, v in (cabecalhos or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(dados)

        def _app_download(self, caminho: str) -> None:
            """/app/baixar (página), /app/android.apk (com Digest SHA-256) e /app/android.apk.sha256 (calculado do APK)."""
            arq = arquivo_app(APP_DOWNLOAD[caminho])
            if not arq:
                return self._json(404, {"ok": False, "erro": "app ainda não publicado neste servidor" if "apk" in caminho
                                        else "página de download ausente"})
            if caminho.startswith("/app/baixar"):
                return self._enviar_bytes(arq.read_bytes(), "text/html; charset=utf-8", {"Cache-Control": "no-cache"})
            soma = sha256_arquivo(arq)
            if caminho.endswith(".sha256"):
                return self._enviar_bytes(f"{soma}  android.apk\n".encode("ascii"), "text/plain; charset=utf-8", {"Cache-Control": "no-cache"})
            total = arq.stat().st_size
            self.send_response(200)
            self.send_header("Content-Type", APK_MIME)
            self.send_header("Content-Length", str(total))
            self.send_header("Content-Disposition", 'attachment; filename="physis.apk"')
            self.send_header("Digest", "sha-256=" + base64.b64encode(bytes.fromhex(soma)).decode("ascii"))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            with open(arq, "rb") as f:                      # em blocos: o APK tem dezenas de MB
                for bloco in iter(lambda: f.read(1 << 20), b""):
                    self.wfile.write(bloco)

        def _rotas_novas_get(self, u, q: dict) -> bool:
            """GET das rotas novas. True = respondeu. Fica antes de qualquer _barrado: há páginas públicas e o revisor
            externo do documento não tem sessão; cada rota decide o seu acesso."""
            p = u.path
            # documento para comentários: a página não tem dado; a API decide (equipe com sessão ou convite)
            if p == "/documento/fontes.css":
                self._enviar_bytes(documentos_mod.fontes_css().encode("utf-8"), "text/css; charset=utf-8", {"Cache-Control": "max-age=86400"})
                return True
            if p in ("/documento", "/documento/") or re.fullmatch(r"/documento/[A-Za-z0-9_-]{16,64}/?", p):
                if not (WEB / "documento.html").is_file():
                    self._json(404, {"ok": False, "erro": "documento.html ausente"})
                else:
                    self._arquivo(WEB / "documento.html", "text/html; charset=utf-8")
                return True
            if p.startswith("/api/indicadores"):          # indicadores da plataforma (D18): só equipe e direção
                qi = self._exigir(seg.EQUIPE)
                if qi:
                    self._json(*indicadores.rota("GET", p, qi, None, consulta=q))
                return True
            if p.startswith("/api/emissao") or p == "/api/ia/consumo":
                qe = self._exigir(seg.EQUIPE)
                if not qe:
                    return True
                if p == "/api/ia/consumo":           # tela de consumo da IA: nunca leva a chave nem texto enviado
                    cl = robos_mod.claude_da_cadeia(robos["suporte"].ia)
                    self._json(200, {"ok": True, "consumo": cl.estado() if cl else None})
                    return True
                r = docauto.rota("GET", p, qe, None, consulta=q)
                if r and "_bytes" in r[1]:
                    nome = r[1]["_nome"]
                    self._enviar_bytes(r[1]["_bytes"], r[1]["_tipo"], {"Content-Disposition": f'attachment; filename="{nome}"',
                                                                      "Cache-Control": "no-store"})
                    return True
                if r:
                    self._json(*r)
                    return True
                return False
            if p.startswith("/api/documentos"):
                r = modulo("docs").rota("GET", p, self._conta_doc(), None, convite=self.headers.get("X-Physis-Convite"),
                                        ip=self._ip(), base=url_publica, consulta=q)
                if r:
                    self._doc_resposta(r)
                    return True
                return False
            # painel municipal: página e modo público sem conta; operador = equipe
            if p in ("/municipio", "/municipio/"):
                if not (WEB / "municipio.html").is_file():
                    self._json(404, {"ok": False, "erro": "municipio.html ausente"})
                else:
                    self._arquivo(WEB / "municipio.html", "text/html; charset=utf-8")
                return True
            if p == "/api/municipio/publico":
                self._json(200, modulo("municipio").estado(operador=False))
                return True
            if p == "/api/municipio":
                if self._exigir(seg.EQUIPE):
                    self._json(200, modulo("municipio").estado(operador=True))
                return True
            if p == "/api/municipio/exportar":
                qm = self._quem()
                oper = bool(qm and seg.pode(qm, seg.EQUIPE))
                tipo = q.get("tipo", ["alertas"])[0]
                if tipo not in ("alertas", "chuva", "bairros"):
                    self._json(400, {"ok": False, "erro": "tipo: alertas, chuva ou bairros"})
                    return True
                self._enviar_bytes(modulo("municipio").exportar_csv(tipo, operador=oper).encode("utf-8"), "text/csv; charset=utf-8",
                                   {"Content-Disposition": f'attachment; filename="municipio-{tipo}.csv"', "Cache-Control": "no-store"})
                return True
            # certificação assistida: nomes de arquivos da Gestão só para a equipe
            if p == "/api/evidencias/dados":
                qe = self._exigir(seg.CLIENTE)
                if qe:
                    self._json(200, {"ok": True, "dados": evidencias_mod.dados_servidor(hub, incluir_arquivos=seg.pode(qe, seg.EQUIPE))})
                return True
            # CEP do Início (cep.py): com sessão e limite por IP; vai para o provedor só o CEP (LGPD); cache no SQLite
            if p.startswith("/api/local/cep/"):
                if self._exigir(seg.CLIENTE) and not self._limitado("cep"):
                    self._json(*cep_srv.consultar(unquote(p.rsplit("/", 1)[-1])[:12]))
                return True
            # Mapeamento: catálogo e camadas abertas sem login; contexto e arquivos do cliente com sessão
            if p.startswith("/api/mapeamento/"):
                aberto = p.rstrip("/") in ("/api/mapeamento/camadas", "/api/mapeamento/camada")
                qm = None if aberto else self._exigir(seg.CLIENTE)
                if aberto or qm:
                    self._rota_mapeamento("GET", u, q, None, qm)
                return True
            # Fornecedores e equipamentos (fornecedores.py; docs/FORNECEDORES.md): cliente só /regiao e arquivo público; o resto equipe
            if p.startswith("/api/fornecedores"):
                qf = self._exigir(seg.CLIENTE)
                if qf:
                    cod, r = modulo("fornecedores").rota("GET", p, qf, None, q)
                    if isinstance(r, tuple):                       # ("bytes", nome, tipo, dados): CSV ou catálogo
                        self._enviar_bytes(r[3], r[2], {"Content-Disposition": "attachment; filename*=UTF-8''" + quote(r[1]),
                                                        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
                    else:
                        self._json(cod, r)
                return True
            # Intercâmbio (intercambio.py; docs/INTERCAMBIO.md): /v1/ = outra plataforma, com assinatura; o resto = direção
            if p.startswith("/api/intercambio/"):
                self._intercambio("GET", u, b"", q)
                return True
            # Validação · planejado × gerado (validacao.py; docs/VALIDACAO_MV.md): cliente vê
            if p.startswith("/api/validacao/"):
                qv = self._exigir(seg.CLIENTE)
                if qv:
                    cod, r = modulo("validacao").rota("GET", p, qv, None, q)
                    if isinstance(r, tuple):                       # ("bytes", nome, tipo, dados): pacote de auditoria
                        self._enviar_bytes(r[3], r[2], {"Content-Disposition": "attachment; filename*=UTF-8''" + quote(r[1]),
                                                        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
                    else:
                        self._json(cod, r)
                return True
            # Frota e combustível (frota.py; docs/FROTA.md): cliente vê; comprovante e exportação só a equipe
            if p.startswith("/api/frota/"):
                qv = self._exigir(seg.CLIENTE)
                if qv:
                    cod, r = modulo("frota").rota("GET", p, qv, None, q)
                    if isinstance(r, tuple):                       # ("bytes", nome, tipo, dados): CSV ou comprovante
                        self._enviar_bytes(r[3], r[2], {"Content-Disposition": "attachment; filename*=UTF-8''" + quote(r[1]),
                                                        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
                    else:
                        self._json(cod, r)
                return True
            # parceiros: vitrine pública (sem dado pessoal); lista interna para a equipe; CPF/CNPJ completo só a direção
            if p == "/api/parceiros":
                g = lambda k: q.get(k, [""])[0][:80]
                self._json(200, modulo("parceiros").vitrine(g("servico"), g("uf"), g("municipio"), g("ibge")))
                return True
            if p == "/api/parceiros/interno":
                qp = self._exigir(seg.EQUIPE)
                if not qp:
                    return True
                completo = q.get("completo", [""])[0] == "1" and seg.pode(qp, seg.DIRECAO)
                if completo and not self._sensivel(qp):
                    return True
                self._json(200, modulo("parceiros").interno(completo=completo))
                return True
            # app nativo: sem login (o celular baixa antes de entrar)
            if p in APP_DOWNLOAD:
                self._app_download(p)
                return True
            # pegada do servidor: cliente vê os totais; equipe e direção, o detalhe (fontes e clientes hospedados)
            if p == "/api/servidor/pegada":
                qg = self._exigir(seg.CLIENTE)
                if not qg:
                    return True
                if cfg_pegada is None:
                    self._json(200, {"ok": False, "desligada": True, "erro": "pegada do servidor desligada nesta instalação (PHYSIS_PEGADA=0)"})
                    return True
                self._json(200, pegada_mod.para(hub, cfg_pegada).relatorio(detalhado=seg.pode(qg, seg.EQUIPE)))
                return True
            # demonstrações públicas: só leitura; os mesmos cabeçalhos de segurança das outras páginas (end_headers)
            if p.startswith("/demo/") and p != "/demo/":          # /demo/ continua sendo a demonstração do painel
                arq = arquivo_demo(p)
                if not arq:
                    self._json(404, {"ok": False, "erro": "demonstração desconhecida"})
                else:
                    self._enviar_bytes(arq.read_bytes(), "text/html; charset=utf-8", {"Cache-Control": "public, max-age=3600"})
                return True
            if p.rstrip("/") in JURIDICO_ROTAS:
                pagina = pagina_juridico(JURIDICO_ROTAS[p.rstrip("/")])
                if pagina is None:
                    self._json(404, {"ok": False, "erro": "texto jurídico ausente nesta instalação"})
                else:
                    self._pagina(pagina)
                return True
            return False

        def _rota_mapeamento(self, metodo: str, u, q: dict, corpo: bytes | None, quem: dict | None) -> None:
            r = mapeamento_mod.rota(metodo, u.path, q, corpo, hub=hub, uploads=uploads_map,
                                    nome_arquivo=unquote(self.headers.get("X-Physis-Nome", ""))[:200],
                                    quem=(quem or {}).get("usuario", ""))
            if r is None:
                self._json(404, {"ok": False, "erro": "rota desconhecida"})
            elif len(r) == 3:                               # (código, bytes, tipo): o arquivo IFC
                self._enviar_bytes(r[1], r[2], {"Content-Disposition": 'attachment; filename="physis-modelo.ifc"',
                                                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
            else:
                self._json(*r)

        def _rotas_novas_post_grandes(self, u) -> bool:
            """POST com corpo que pode passar de 64 KB (PDF/A, documento publicado, importação de bairros). True = respondeu."""
            p = u.path
            # emissão de documentos (documentos_auto.py): equipe gera/edita/envia/emite; a direção aprova e devolve
            if p.startswith("/api/emissao"):
                q = self._exigir(seg.EQUIPE)
                if not q:
                    return True
                corpo = self._corpo_grande(documentos_auto_mod.TEXTO_MAX + 64 * 1024)
                if corpo is None and (self.headers.get("Content-Length") or "0").strip() == "0":
                    corpo = b"{}"                   # ação sem corpo (enviar, aprovar, emitir)
                if corpo is None:
                    self._recusar_corpo("documento grande demais")
                    return True
                r = docauto.rota("POST", p, q, corpo)
                if r:
                    self._json(*r)
                    return True
                return False
            # Fornecedores: só a equipe grava (CSV até 1 MB e arquivo até 20 MB); apagar pede senha recente
            if p.startswith("/api/fornecedores"):
                qf = self._exigir(seg.EQUIPE)
                if not qf or (p in ("/api/fornecedores/importar", "/api/fornecedores/arquivo") and self._limitado("arquivo")):
                    return True
                corpo = self._corpo_grande(fornecedores_mod.ARQ_MAX + 64 * 1024)
                if corpo is None and (self.headers.get("Content-Length") or "0").strip() == "0":
                    corpo = b"{}"
                if corpo is None:
                    self._recusar_corpo("arquivo grande demais (máximo 20 MB)")
                    return True
                if p.endswith("/apagar") and not self._sensivel(qf):
                    return True
                self._json(*modulo("fornecedores").rota("POST", p, qf, corpo, parse_qs(u.query)))
                return True
            # Simulação (Fase 1): POST /api/simulacao/<parte>; 422 = dado faltando ([MARCADOR]); 400 = entrada inválida ou grande
            if p.startswith("/api/simulacao/"):
                qs = self._exigir(seg.CLIENTE)
                if not qs or self._limitado("arquivo"):
                    return True
                corpo = self._corpo_grande(SIMULACAO_CORPO_MAX)
                if corpo is None:
                    self._recusar_corpo("caso grande demais para a Fase 1")
                    return True
                d = self._ler(corpo, "sim_corpo", estrito=False)
                if d is None:
                    return True
                ctx = None
                if p.rstrip("/") == "/api/simulacao/biogas" and d.get("regime") == "ambiente" and not d.get("temperatura_mensal"):
                    ctx = sim_biogas_mod.clima_do_local(hub, irradiacao)      # temperatura do local da instalação (nunca um padrão)
                self._json(*simulacao_mod.rota(p.rstrip("/"), d, ctx))
                return True
            # Mapeamento: arquivo do cliente e IFC até 20 MB; corpos JSON conferidos pelos ESQUEMAS map_*
            if p.startswith("/api/mapeamento/"):
                qm = self._exigir(seg.CLIENTE)
                if not qm or (re.search(r"/(upload|ifc/ler)$", p) and self._limitado("arquivo")):
                    return True
                corpo = self._corpo_grande(MAPEAMENTO_CORPO_MAX)
                if corpo is None and (self.headers.get("Content-Length") or "0").strip() == "0":
                    corpo = b"{}"
                if corpo is None:
                    self._recusar_corpo("arquivo grande demais (máximo 20 MB)")
                    return True
                esq = {"/api/mapeamento/contexto": "map_contexto", "/api/mapeamento/incidencia": "map_incidencia",
                       "/api/mapeamento/planta-solar": "map_planta_solar", "/api/mapeamento/ifc": "map_ifc"}.get(p.rstrip("/"))
                if esq and self._ler(corpo, esq) is None:
                    return True
                self._rota_mapeamento("POST", u, parse_qs(u.query), corpo, qm)
                return True
            # Intercâmbio: pacote de até 4 MB (intercambio.CORPO_MAX)
            if p.startswith("/api/intercambio/"):
                if (self.headers.get("Content-Length") or "0").strip() in ("", "0"):
                    corpo = b""
                else:
                    corpo = self._corpo_grande(intercambio_mod.CORPO_MAX)
                    if corpo is None:
                        self._recusar_corpo("pacote grande demais (máximo 4 MB)")
                        return True
                self._intercambio("POST", u, corpo, parse_qs(u.query))
                return True
            # Validação: só a equipe grava o planejado (com a fonte)
            if p.startswith("/api/validacao/"):
                qv = self._exigir(seg.EQUIPE)
                if not qv:
                    return True
                corpo = self._corpo_grande(64 * 1024)
                if corpo is None:
                    self._recusar_corpo("corpo grande demais (máximo 64 kB)")
                    return True
                self._json(*modulo("validacao").rota("POST", p, qv, corpo, parse_qs(u.query)))
                return True
            # Frota: só a equipe grava (CSV até 4 MB, comprovante até 10 MB); apagar veículo e retenção só a direção
            if p.startswith("/api/frota/"):
                qv = self._exigir(seg.EQUIPE)
                if not qv or (p in ("/api/frota/importar", "/api/frota/comprovante") and self._limitado("arquivo")):
                    return True
                corpo = self._corpo_grande(max(frota_mod.ARQ_MAX, frota_mod.CSV_MAX) + 64 * 1024)
                if corpo is None and (self.headers.get("Content-Length") or "0").strip() == "0":
                    corpo = b"{}"
                if corpo is None:
                    self._recusar_corpo("arquivo grande demais (máximo 10 MB)")
                    return True
                if p == "/api/frota/veiculo/remover" and not self._sensivel(qv):
                    return True
                self._json(*modulo("frota").rota("POST", p, qv, corpo, parse_qs(u.query)))
                return True
            if p == "/api/documentos/pdfa":
                if not self._exigir(seg.CLIENTE) or self._limitado("arquivo"):      # LibreOffice é pesado: 10 por 10 min por IP
                    return True
                odf = self._corpo_grande(documentos_mod.CORPO_MAX)
                if odf is None:
                    self._recusar_corpo("documento vazio ou grande demais")
                    return True
                ext = "ods" if "spreadsheet" in (self.headers.get("Content-Type") or "") else "odt"
                r = documentos_mod.converter_pdfa(odf, extensao=ext)       # sem soffice: serviço de documentos ou 501
                if not r["ok"]:
                    self._json(r.pop("codigo", 500), r)
                    return True
                self._enviar_bytes(r["pdf"], "application/pdf", {"Content-Disposition": 'attachment; filename="physis-documento.pdf"',
                                                                 "Cache-Control": "no-store", "X-Physis-PDFA": str(r.get("pdfa"))})
                return True
            if p.startswith("/api/documentos"):
                conta, convite = self._conta_doc(), self.headers.get("X-Physis-Convite")
                if not conta and not convite:          # sem sessão nem convite: nem lê o corpo grande
                    self._json(401, {"ok": False, "erro": "entre com usuario e senha", "login": True})
                    return True
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    n = -1
                corpo = self._corpo_grande(documentos_mod.CORPO_MAX) if n > 0 else b"{}"
                if corpo is None:
                    self._recusar_corpo("documento grande demais (máx. 16 MB)")
                    return True
                esq = esquema_documento(p)
                if esq and self._ler(corpo, esq) is None:
                    return True
                r = modulo("docs").rota("POST", p, conta, corpo, convite=convite, ip=self._ip(), base=url_publica)
                if r:
                    self._doc_resposta(r)
                    return True
                return False
            if p == "/api/municipio/bairros/importar":
                qm = self._exigir(seg.EQUIPE)
                if not qm:
                    return True
                dados = self._corpo_grande(municipio_mod.IMPORTAR_MAX_BYTES)
                if dados is None:
                    self._recusar_corpo("arquivo vazio ou maior que 5 MB")
                    return True
                try:
                    lista = municipio_mod.ler_importacao(dados, self.headers.get("Content-Type") or "")
                except ValueError as exc:
                    self._json(400, {"ok": False, "erro": str(exc)})
                    return True
                r = modulo("municipio").importar(lista, qm["usuario"], substituir=parse_qs(u.query).get("substituir", [""])[0] == "1")
                self._json(200 if r["ok"] else 400, r)
                return True
            return False

        def _rotas_novas_post(self, u, corpo: str) -> bool:
            """POST JSON (até 64 KB) das rotas novas. Todo corpo passa por seg.ESQUEMAS (estrito). True = respondeu."""
            p = u.path
            if p.startswith("/api/indicadores"):          # retorno real/falso, incidentes, melhoria → tarefa, coletar
                qi = self._exigir(seg.EQUIPE)
                if qi:
                    self._json(*indicadores.rota("POST", p, qi, corpo))
                return True
            if p in ("/api/municipio/config", "/api/municipio/bairro", "/api/municipio/atualizar"):
                qm = self._exigir(seg.EQUIPE)
                if not qm:
                    return True
                d = self._ler(corpo, {"/api/municipio/config": "mun_config", "/api/municipio/bairro": "mun_bairro"}.get(p, "vazio"))
                if d is None:
                    return True
                mun = modulo("municipio")
                if p.endswith("/atualizar"):
                    if not self._limitado("publico"):          # cada clique chama CEMADEN, INMET e GloFAS
                        self._json(200, mun.consultar())
                    return True
                r = mun.definir_config(d, qm["usuario"]) if p.endswith("/config") else mun.editar_bairro(d, qm["usuario"])
                self._json(200 if r["ok"] else 400, r)
                return True
            if p in ("/api/evidencias/anexo", "/api/evidencias/anexo/remover"):
                qe = self._exigir(seg.CLIENTE)
                if not qe:
                    return True
                d = self._ler(corpo, "evid_remover" if p.endswith("/remover") else "evid_anexo")
                if d is None:
                    return True
                r = (evidencias_mod.remover(hub, d["id"], qe["usuario"]) if p.endswith("/remover")
                     else evidencias_mod.anexar(hub, d, qe["usuario"]))
                self._json(200 if r["ok"] else 400, r)
                return True
            if not p.startswith("/api/parceiros"):
                return False
            par = modulo("parceiros")
            if p in ("/api/parceiros/cadastro", "/api/parceiros/orcamento"):
                # públicas (loja), com limite por IP; dado pessoal só com o consentimento marcado (o módulo confere)
                if self._limitado("publico"):
                    return True
                d = self._ler(corpo, "parc_cadastro" if p.endswith("cadastro") else "parc_orcamento")
                if d is None:
                    return True
                qp = self._quem()
                r = par.cadastrar(d, "site") if p.endswith("cadastro") else par.pedir_orcamento(d, usuario=qp["usuario"] if qp else "")
                self._json(200 if r["ok"] else 400, r)
                return True
            m = re.fullmatch(r"/api/parceiros/(\d{1,12})/(editar|documento|documento/remover|conferir|curadoria|avaliacao|apagar)", p)
            if not m:
                self._json(404, {"ok": False, "erro": "rota desconhecida"})
                return True
            pid, acao = int(m.group(1)), m.group(2)
            qp = self._exigir(seg.CLIENTE if acao == "avaliacao" else seg.DIRECAO if acao in ("curadoria", "apagar") else seg.EQUIPE)
            if not qp:
                return True
            d = self._ler(corpo, {"editar": "parc_editar", "documento": "parc_documento", "documento/remover": "parc_doc_remover",
                                  "curadoria": "parc_curadoria", "avaliacao": "parc_avaliacao"}.get(acao, "vazio"))
            if d is None:
                return True
            if acao == "apagar" and not self._sensivel(qp):          # LGPD: apaga cadastro, documentos e avaliações
                return True
            us = qp["usuario"]
            r = {"editar": lambda: par.editar(pid, d, us),
                 "documento": lambda: par.documento(pid, d, us),
                 "documento/remover": lambda: par.remover_documento(pid, d["id"], us),
                 "conferir": lambda: par.conferir_registro(pid, us),
                 "curadoria": lambda: par.curar(pid, d.get("status"), d.get("motivo"), us, seg.pode(qp, seg.DIRECAO)),
                 "avaliacao": lambda: par.avaliar(pid, d, us, eh_equipe=seg.pode(qp, seg.EQUIPE)),
                 "apagar": lambda: par.apagar(pid, us)}[acao]()
            self._json(r.pop("codigo", 200 if r["ok"] else 400), r)
            return True

        def _csrf_barrado(self) -> bool:
            """POST/PUT/DELETE: (1) Origin/Referer de outro site com sessão (ou nas rotas de conta) = 403;
            (2) com sessão, X-Physis-CSRF errado = 403; ausente = 403 só com PHYSIS_CSRF_ESTRITO=1."""
            caminho = urlparse(self.path).path
            tk = self._token_sessao() or self._token_suporte()
            if seg.origem_confere(self.headers, url_publica) is False and (tk or caminho.startswith("/api/conta/")):
                return self._negar_csrf("origem de outro site")
            if tk and caminho not in SEM_CSRF:
                h = self.headers.get("X-Physis-CSRF")
                if (h is not None or seg.csrf_estrito()) and not seg.iguais(h, seg.csrf_de(hub, tk)):
                    return self._negar_csrf("token CSRF ausente ou errado")
            return False

        def _negar_csrf(self, motivo: str) -> bool:
            seg.acesso_registrar(hub, "", self._ip(), "csrf recusado", cadeia=False)
            self._json(403, {"ok": False, "csrf": True, "erro": "pedido recusado: " + motivo + "; recarregue a página"})
            return True

        def _ler(self, corpo, esquema: str, estrito: bool = True) -> dict | None:
            """JSON do corpo validado (seguranca.carregar_json + ESQUEMAS). None = já respondeu 400."""
            try:
                d = seg.carregar_json(corpo or "{}")
            except ValueError:
                self._json(400, {"ok": False, "erro": "json invalido"})
                return None
            erro = seg.validar(d, seg.ESQUEMAS[esquema], estrito)
            if erro:
                self._json(400, {"ok": False, "erro": erro})
                return None
            return d

        def _mandar(self, ref: str | None) -> None:
            if ref:
                threading.Thread(target=correio.enviar_fila, args=(hub, ref), daemon=True).start()

        def _pagina(self, html: str) -> None:
            pagina = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(pagina)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(pagina)

        def _limitado(self, categoria: str) -> bool:
            """True (e já respondeu 429 com Retry-After, depois de ler o corpo) quando este IP passou do limite."""
            espera = limites.tentar(categoria, self._ip())
            if espera <= 0:
                return False
            n = max(1, int(espera + 0.999))
            self._recusar(429, {"ok": False, "erro": f"muitos pedidos; tente de novo em {n} s", "espera": n}, {"Retry-After": str(n)})
            return True

        def _dispositivo(self, saude_linha: bool = False) -> tuple[bool, int | None]:
            """Quem entrega linhas de aparelho. (True, nó ou None) se pode; (False, None) e já respondeu 401.
            Aceita: a chave do dispositivo (Authorization: Bearer / X-Physis-Chave); o PHYSIS_TOKEN antigo
            (X-Physis-Token); sem chave, conforme PHYSIS_ACEITAR_SEM_CHAVE (vazio = só da rede local)."""
            ch = seg.chave_do_pedido(self.headers)
            if ch:
                c = seg.chave_conferir(hub, ch)
                if c:
                    return True, c["no"]
                self._json(401, {"ok": False, "erro": "chave do dispositivo inválida ou revogada"})
                return False, None
            if token is not None and seg.iguais(self.headers.get("X-Physis-Token"), token):
                return True, None
            if saude_linha and token is not None:          # como antes: com PHYSIS_TOKEN definido, a Saúde exige token ou chave
                self._json(401, {"ok": False, "erro": "token ausente ou invalido"})
                return False, None
            if sem_chave == "1" or (sem_chave != "0" and self._local()):
                return True, None
            self._json(401, {"ok": False, "erro": "chave do dispositivo ausente"})
            return False, None

        def _drenar_pendente(self) -> None:
            """Lê o corpo que ninguém leu antes de responder com erro. Sem isso, um 401/403/404 a um POST
            com corpo fecha a conexão com bytes não lidos e o Windows corta com RST: quem enviou não vê a resposta."""
            if getattr(self, "_corpo_lido", True):
                return
            self._corpo_lido = True
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return
            if 0 < n <= CORPO_MAX:
                try:
                    self.rfile.read(n)
                except OSError:
                    pass

        def _json(self, codigo: int, obj, cabecalhos: dict | None = None) -> None:
            if codigo >= 400:
                # corpo grande ainda não lido (ex.: 403 a um anexo de 20 MB): responde e drena com tempo limite
                try:
                    grande = not getattr(self, "_corpo_lido", True) and int(self.headers.get("Content-Length") or 0) > CORPO_MAX
                except ValueError:
                    grande = False
                if grande:
                    return self._recusar(codigo, obj, cabecalhos)
                self._drenar_pendente()
            corpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (cabecalhos or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(corpo)

        def _json_cookie(self, codigo: int, obj, cookie: str) -> None:
            corpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Set-Cookie", cookie)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        def _recusar_corpo(self, erro: str) -> None:
            """Responde 413 e fecha sem cortar a conexao na cara de quem enviou."""
            self._recusar(413, {"ok": False, "erro": erro})

        def _recusar(self, codigo: int, obj: dict, cabecalhos: dict | None = None) -> None:
            """Responde um erro (413, 429) a um pedido cujo corpo ainda não foi lido: responde, depois lê e
            descarta o corpo (até DRENAR_MAX, com tempo limite) e fecha, sem RST no Windows."""
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = 0
            if getattr(self, "_corpo_lido", False):
                n = 0
            self._corpo_lido = True
            self.close_connection = True
            corpo = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (cabecalhos or {}).items():
                self.send_header(k, v)
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(corpo)
            try:
                self.wfile.flush()
                self.connection.settimeout(DRENAR_SEGUNDOS)
                restam = min(max(n, 0), DRENAR_MAX)
                while restam > 0:
                    pedaco = self.rfile.read(min(65536, restam))
                    if not pedaco:
                        break
                    restam -= len(pedaco)
            except OSError:
                pass

        def _corpo(self) -> str | None:
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return None
            if n < 0 or n > CORPO_MAX:
                return None
            self._corpo_lido = True
            return self.rfile.read(n).decode("utf-8", errors="replace")

        def _corpo_grande(self, limite: int) -> bytes | None:
            """Corpo maior que o normal (dados e arquivos da Gestão). None = ausente ou acima do limite."""
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return None
            if n <= 0 or n > limite:
                return None
            self._corpo_lido = True
            return self.rfile.read(n)

        def _sessao_ou_401(self) -> dict | None:
            q = self._quem()
            if not q:
                self._json(401, {"ok": False, "erro": "entre com usuario e senha", "login": True})
            return q

        def _autorizado(self) -> bool:
            return token is None or seg.iguais(self.headers.get("X-Physis-Token"), token)

        def _token_sessao(self) -> str | None:
            for parte in (self.headers.get("Cookie") or "").split(";"):
                k, _, v = parte.strip().partition("=")
                if k == "physis_sessao":
                    return v
            return None

        def _token_suporte(self) -> str | None:
            for parte in (self.headers.get("Cookie") or "").split(";"):
                k, _, v = parte.strip().partition("=")
                if k == "physis_suporte":
                    return v
            return None

        def _quem(self) -> dict | None:
            q = hub.sessao(self._token_sessao())
            if not q and self._token_suporte():
                q = suporte.sessao(self._token_suporte(), self._ip())    # sessão de suporte (papel equipe, só pela VPN)
            return q

        def _suporte_barrado(self, u, metodo: str) -> bool:
            """Sessão de suporte: registra cada rota da API (sem conteúdo) e, no modo "só ver", recusa escrita."""
            if hub.sessao(self._token_sessao()) or not self._token_suporte():
                return False
            q = suporte.sessao(self._token_suporte(), self._ip())
            if not q or u.path == "/api/suporte-remoto/sair":
                return False
            if not suporte.pode_metodo(q, metodo):
                suporte.uso(q, metodo, u.path, self._ip(), recusado=True)
                self._json(403, {"ok": False, "so_ver": True, "erro": "Acesso de suporte só para ver: nada pode ser mudado."})
                return True
            if u.path.startswith("/api/"):
                suporte.uso(q, metodo, u.path, self._ip())
            return False

        def _barrado(self) -> bool:
            """True (e ja respondeu 401) quando a instalacao exige login (ou quem chama esta fora da rede local) e nao ha sessao."""
            if not self._precisa_sessao() or self._quem():
                return False
            self._json(401, {"ok": False, "erro": "entre com usuario e senha", "login": True})
            return True

        def _estado_instancia(self) -> dict:
            q = self._quem()
            return {"org": hub.org, "lugar": hub.lugar, "modulos": instancia.get("modulos"),
                    "exige_login": exige_login, "tem_conta": hub.tem_conta(), "autenticado": bool(q),
                    "nome": q["nome"] if q else None, "papel": q["papel"] if q else None,
                    "licenca": instancia.get("licenca"), "sustainkit": (WEB / "sustainkit.html").exists(),
                    "supervisao": (WEB / "supervisao.html").exists(), "gestao": (WEB / "gestao.html").exists(),
                    "planejador": (WEB / "planejador.html").exists(), "pesquisa": bool(instancia.get("pesquisa")),
                    "nome_cliente": instancia.get("nome"),
                    # marca própria da instalação (ex.: Casa Physis): nome, título e logos em /marca/ (montar.py)
                    "instalacao": instancia.get("instalacao") or "physis",
                    "marca": instancia.get("marca") if isinstance(instancia.get("marca"), dict) else None,
                    "cursos": [c for c in (instancia.get("cursos") or []) if isinstance(c, dict)] if q else [],
                    "senha_min": hub.SENHA_MIN,
                    # segurança: token CSRF da sessão (mandar em X-Physis-CSRF), termos, e-mail, 2FA
                    "csrf": seg.csrf_de(hub, self._token_sessao() or self._token_suporte()) if q else None,
                    "suporte_remoto": {"so_ver": q.get("so_ver")} if q and q.get("suporte") else None,
                    "termos_versao": termos, "consentimento_pendente": seg.consentimento_pendente(q) if q else False,
                    "email_confirmado": q.get("confirmado") if q else None, "dois_fatores": q.get("dois_fatores") if q else None,
                    "recuperar_senha": True, "reautenticar_min": int(seg.reauth_janela_s() // 60)}

        def _rotas_conta(self, caminho: str):
            """Fluxos de conta. Devolve False se a rota não é daqui (o do_POST segue procurando)."""
            ip = self._ip()
            publicas = {"/api/conta/esqueci": "esqueci", "/api/conta/nova-senha": "nova_senha", "/api/conta/confirmar": "token",
                        "/api/conta/convite/ver": "token", "/api/conta/convite/aceitar": "convite_aceitar"}
            if caminho in publicas:
                if self._limitado("entrar"):
                    return None
                d = self._ler(self._corpo(), publicas[caminho])
                if d is None:
                    return None
                if caminho == "/api/conta/esqueci":
                    r, ref = seg.senha_esqueci(hub, d["usuario"], url_publica, ip)
                    self._mandar(ref)
                    return self._json(200, r)
                if caminho == "/api/conta/nova-senha":
                    r = seg.senha_redefinir(hub, d["token"], d["senha"], ip)
                    return self._json(200 if r["ok"] else 400, r)
                if caminho == "/api/conta/confirmar":
                    r = seg.confirmar(hub, d["token"])
                    return self._json(200 if r["ok"] else 400, r)
                if caminho == "/api/conta/convite/ver":
                    r = seg.convite_ver(hub, d["token"])
                    return self._json(200 if r["ok"] else 404, r)
                r = seg.convite_aceitar(hub, d["token"], d.get("nome") or "", d["senha"], d, ip)
                if not r["ok"]:
                    return self._json(400, r)
                e = hub.entrar(r["usuario"], d["senha"], ip, self.headers.get("User-Agent") or "")
                seg.acesso_registrar(hub, r["usuario"], ip, "entrou")
                tk = e.pop("token")
                e["csrf"] = seg.csrf_de(hub, tk)
                return self._json_cookie(200, e, self._cookie(tk, hub.SESSAO_S))
            privadas = {"/api/conta/confirmar/reenviar": "vazio", "/api/conta/consentimento": "consentimento",
                        "/api/conta/reautenticar": "reautenticar", "/api/conta/2fa/iniciar": "vazio",
                        "/api/conta/2fa/ativar": "codigo", "/api/conta/2fa/desativar": "codigo", "/api/convites": "convite"}
            revogar = caminho.startswith("/api/convites/") and caminho.endswith("/revogar")
            if caminho not in privadas and not revogar:
                return False
            if caminho == "/api/conta/reautenticar" and self._limitado("entrar"):
                return None
            q = self._quem()
            if not q:
                return self._json(401, {"ok": False, "erro": "entre com usuario e senha", "login": True})
            if caminho.startswith("/api/convites"):
                if not seg.pode(q, seg.DIRECAO):
                    return self._json(403, SEM_PAPEL)
                if revogar:
                    ok = seg.convite_revogar(hub, caminho.split("/")[-2], q["usuario"])
                    return self._json(200 if ok else 404, {"ok": ok})
            d = self._ler(self._corpo(), privadas[caminho])
            if d is None:
                return None
            if caminho == "/api/convites":
                if seg.normalizar_papel(d.get("papel")) == seg.DIRECAO and not self._sensivel(q):
                    return None
                r = seg.convite_criar(hub, d["email"], d.get("papel") or seg.EQUIPE, d.get("pessoa") or "", d.get("nome") or "",
                                      q["usuario"], url_publica)
                if r["ok"]:
                    self._mandar(r.pop("ref"))
                    r["email_enviado"] = correio.configurado()
                return self._json(200 if r["ok"] else 400, r)
            if caminho == "/api/conta/confirmar/reenviar":
                ref = seg.confirmar_enviar(hub, q["id"], url_publica)
                self._mandar(ref)
                return self._json(200, {"ok": True, "enviado": bool(ref)})
            if caminho == "/api/conta/consentimento":
                if d["aceito"] and not d.get("versao"):
                    return self._json(400, {"ok": False, "erro": "falta o campo versao"})
                r = seg.consentimento_registrar(hub, q["id"], q["usuario"], d.get("versao") or q.get("consentimento") or "", d["aceito"], ip)
                return self._json(200 if r["ok"] else 409, r)
            if caminho == "/api/conta/reautenticar":
                r = seg.reautenticar(hub, self._token_sessao(), q, d["senha"], d.get("codigo") or "")
                return self._json(200 if r["ok"] else r.pop("codigo", 403), r)
            if caminho == "/api/conta/2fa/iniciar":
                if not self._sensivel(q):
                    return None
                r = seg.totp_iniciar(hub, q["id"], q["usuario"])
                return self._json(200 if r["ok"] else 400, r)
            if caminho == "/api/conta/2fa/ativar":
                r = seg.totp_ativar(hub, q["id"], q["usuario"], d["codigo"])
                return self._json(200 if r["ok"] else 400, r)
            if not self._sensivel(q):           # /api/conta/2fa/desativar
                return None
            r = seg.totp_desativar(hub, q["id"], q["usuario"], d["codigo"])
            return self._json(200 if r["ok"] else 400, r)

        def do_HEAD(self):
            # só o mapa da região responde a HEAD (o Planejador pergunta se o arquivo existe antes de usar)
            u = urlparse(self.path)
            if u.path.startswith("/mapas/"):
                return self._mapa(u.path, so_cabecalho=True)
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _mapa(self, caminho: str, so_cabecalho: bool = False) -> None:
            """Mapa de fundo da região (PMTiles do OpenStreetMap) guardado no servidor, entregue por partes
            (Range), como o leitor de PMTiles pede. Nome restrito: só [a-z0-9-].pmtiles dentro da pasta de mapas."""
            if self._barrado():
                return
            nome = caminho[len("/mapas/"):]
            arq = PASTA_MAPAS() / nome
            if not re.fullmatch(r"[a-z0-9-]{1,40}\.pmtiles", nome) or not arq.is_file():
                if so_cabecalho:
                    self.send_response(404)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                return self._json(404, {"ok": False, "erro": "mapa da região não instalado"})
            total = arq.stat().st_size
            ini, fim, parcial = 0, total - 1, False
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", (self.headers.get("Range") or "").strip())
            if m and (m.group(1) or m.group(2)):
                if m.group(1):
                    ini = int(m.group(1)); fim = min(int(m.group(2)) if m.group(2) else total - 1, total - 1)
                else:
                    ini = max(0, total - int(m.group(2)))
                if ini > fim or ini >= total:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{total}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                parcial = True
            n = fim - ini + 1
            self.send_response(206 if parcial else 200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(n))
            if parcial:
                self.send_header("Content-Range", f"bytes {ini}-{fim}/{total}")
            self.send_header("Cache-Control", "private, max-age=86400")
            self.end_headers()
            if so_cabecalho:
                return
            with open(arq, "rb") as f:
                f.seek(ini)
                restam = n
                while restam > 0:
                    pedaco = f.read(min(1 << 20, restam))
                    if not pedaco:
                        break
                    self.wfile.write(pedaco)
                    restam -= len(pedaco)

        def _arquivo(self, arq: Path, tipo: str) -> None:
            dados = arq.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            if self._suporte_barrado(u, "GET"):
                return
            if u.path == "/api/suporte-remoto":
                r = suporte.listar(self._quem())
                return self._json(r.pop("codigo", 200), r)
            if u.path == "/api/instancia":
                return self._json(200, self._estado_instancia())
            if u.path in ("/conta/esqueci", "/conta/nova-senha", "/conta/confirmar", "/conta/convite"):
                return self._pagina(PAGINA_CONTA)
            # documento, município, evidências, parceiros, app, pegada, demos e textos jurídicos (antes de qualquer _barrado)
            if self._rotas_novas_get(u, q):
                return
            if u.path in ("/.well-known/security.txt", "/security.txt"):
                txt = seg.security_txt(os.environ.get("PHYSIS_SEGURANCA_CONTATO") or os.environ.get("PHYSIS_SUPORTE_EMAIL")
                                       or instancia.get("suporte_email") or "", url_publica, time.time()).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(txt)))
                self.end_headers()
                self.wfile.write(txt)
                return
            if u.path == "/api/convites":
                if not self._exigir(seg.DIRECAO):
                    return
                return self._json(200, {"ok": True, "convites": seg.convite_listar(hub)})
            # ── Editais (só quem tem acesso) e eventos (equipe com sessão): editais.rota decide ──
            if u.path.startswith(("/api/editais", "/api/eventos")):
                q = self._quem()
                if q and not seg.pode(q, seg.EQUIPE):          # conta de cliente não vê a área interna
                    return self._json(403, SEM_PAPEL)
                r = editais_mod.rota("GET", u.path, q, None, editais_col, eventos_col, hub, correio)
                if r:
                    return self._json(*r)
            if u.path.startswith("/api/central/compra/"):
                # publico de proposito: a loja so pergunta se a propria compra ja foi aprovada
                est = hub.central_estado("compra", u.path.rsplit("/", 1)[-1])
                return self._json(200 if est else 404, {"ok": bool(est), "estado": est})
            if u.path == "/api/loja/catalogo":
                # publico: so o que foi revisado e posto no ar pela equipe
                return self._json(200, hub.loja_catalogo(interno=False))
            if u.path == "/api/loja/catalogo/interno":
                if not self._exigir(seg.EQUIPE):
                    return
                return self._json(200, hub.loja_catalogo(interno=True))
            # ── Consultoria ── página pública e textos editáveis do site (leitura pública, como a loja)
            if u.path in ("/consultoria", "/consultoria/"):
                if not (WEB / "consultoria.html").exists():
                    return self._json(404, {"ok": False, "erro": "consultoria.html ausente"})
                return self._arquivo(WEB / "consultoria.html", "text/html; charset=utf-8")
            if u.path.startswith("/api/site/textos/"):
                r = hub.site_textos(u.path[len("/api/site/textos/"):])
                return self._json(200 if r["ok"] else 404, r)
            # ── fim Consultoria ──
            if u.path.startswith("/ativar/"):
                numero = u.path.rstrip("/").rsplit("/", 1)[-1]
                if not re.fullmatch(r"PH-\d{4,6}", numero):
                    return self._json(404, {"ok": False, "erro": "rota desconhecida"})
                pagina = PAGINA_ATIVAR.replace("__NUMERO__", numero).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(pagina)))
                self.end_headers()
                self.wfile.write(pagina)
                return
            # ── LGPD art. 18: o que o servidor guarda sobre quem está na sessão (seguranca.meus_dados) ──
            if u.path == "/api/conta/meus-dados":
                q = self._sessao_ou_401()
                if not q:
                    return
                return self._json(200, seg.meus_dados(hub, q))
            # ── Chaves dos dispositivos: só a direção lista (a chave em si nunca volta, só o resumo fica guardado) ──
            if u.path == "/api/dispositivos/chaves":
                if not self._exigir(seg.DIRECAO):
                    return
                return self._json(200, {"ok": True, "chaves": seg.chave_listar(hub)})
            if u.path == "/api/gestao/estado":
                q = self._exigir(seg.EQUIPE)
                if not q:
                    return
                try:
                    desde = float((q2 := parse_qs(u.query)).get("desde", ["0"])[0])
                except ValueError:
                    desde = 0.0
                return self._json(200, {"ok": True, "agora": time.time(), "conta": {k: q[k] for k in ("nome", "usuario", "papel", "pessoa")},
                                        "itens": hub.gestao_ler(desde)})
            # ── Plataforma do cliente: dados que antes ficavam só no navegador (perfil_cliente.py) ──
            if u.path == "/api/cliente/estado" or u.path.startswith("/api/cliente/estado/") or u.path == "/api/cliente/perfil":
                qc = self._exigir(seg.CLIENTE)          # sempre com sessão, mesmo em instalação sem login
                if not qc:
                    return
                if u.path == "/api/cliente/perfil":
                    return self._json(200, {"ok": True, "org": hub.org, "aprendido": hub.cliente_aprendido()})
                if u.path == "/api/cliente/estado":
                    try:
                        desde = float(q.get("desde", ["0"])[0])
                    except ValueError:
                        desde = 0.0
                    return self._json(200, {"ok": True, "agora": time.time(), "org": hub.org,
                                            "conta": {k: qc[k] for k in ("nome", "usuario", "papel")},
                                            "chaves": list(perfil_cliente.CHAVES), "prefixos": list(perfil_cliente.PREFIXOS),
                                            "itens": hub.cliente_ler(desde=desde)})
                chave = unquote(u.path[len("/api/cliente/estado/"):])
                if not perfil_cliente.chave_valida(chave):
                    return self._json(400, {"ok": False, "erro": "chave nao permitida"})
                it = hub.cliente_ler(chave=chave).get(chave)
                if not it:
                    return self._json(404, {"ok": False, "chave": chave, "versao": 0, "valor": None}, {"ETag": '"v0"'})
                etag = f'"v{it["versao"]}"'
                if (self.headers.get("If-None-Match") or "").strip() == etag:
                    self.send_response(304)
                    self.send_header("ETag", etag)
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    return
                return self._json(200, {"ok": True, "chave": chave, **it}, {"ETag": etag})
            # ── Central de clientes e caixa de chamados (Gestão interna; dado pessoal: só equipe) ──
            if u.path == "/api/central/clientes":
                if not self._exigir(seg.EQUIPE):
                    return
                return self._json(200, {"ok": True, "clientes": hub.central_clientes()})
            if u.path.startswith("/api/suporte/chamados/"):
                if not self._exigir(seg.EQUIPE):
                    return
                ch = hub.suporte_detalhe(unquote(u.path[len("/api/suporte/chamados/"):]))
                return self._json(200 if ch else 404, {"ok": bool(ch), "chamado": ch})
            if u.path == "/api/suporte/chamados":
                if not self._exigir(seg.EQUIPE):
                    return
                return self._json(200, {"ok": True, "chamados": hub.suporte_listar(None)})
            if u.path.startswith("/api/gestao/arquivo/"):
                if not self._exigir(seg.EQUIPE):
                    return
                arq = hub.gestao_arquivo(u.path.rsplit("/", 1)[-1])
                if not arq:
                    return self._json(404, {"ok": False})
                self.send_response(200)
                self.send_header("Content-Type", arq[1])
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(arq[0]))
                self.send_header("Content-Length", str(len(arq[2])))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(arq[2])
                return
            if u.path == "/api/contas":
                q = self._sessao_ou_401()
                if not q:
                    return
                if q["papel"] != "administrador":
                    return self._json(403, {"ok": False, "erro": "so a direcao ve as contas"})
                return self._json(200, {"ok": True, "contas": hub.contas()})
            # ── Saúde (caixinha de remédios e pulseira): dado sensível, sempre com sessão e só de quem foi autorizado ──
            if u.path == "/api/saude/estado":
                q = self._sessao_ou_401()
                if not q:
                    return
                return self._json(200, saude.estado(q["usuario"]))
            if u.path in ("/api/central/emails", "/api/central/instalacoes"):
                if not self._exigir(seg.EQUIPE):
                    return
                if u.path.endswith("emails"):
                    # avisos de saúde (dado sensível, LGPD) vão só para os cuidadores: a fila mostra só quantos são
                    todos = hub.emails()
                    # e-mails de conta (senha nova, confirmação, convite) levam link de uso único: também ficam fora da fila
                    oculto = lambda e: str(e.get("ref") or "").startswith(("saude-", seg.REF_CONTA))
                    saude_n = sum(1 for e in todos if str(e.get("ref") or "").startswith("saude-"))
                    return self._json(200, {"ok": True, "configurado": correio.configurado(), "saude_ocultos": saude_n,
                                            "conta_ocultos": sum(1 for e in todos if str(e.get("ref") or "").startswith(seg.REF_CONTA)),
                                            "emails": [e for e in todos if not oculto(e)]})
                return self._json(200, {"ok": True, "instalacoes": hub.instalacoes()})
            if u.path in ("/demo", "/demo/"):
                # demonstração gratuita: roda inteira no navegador, com dados simulados; não lê nada do servidor
                return self._arquivo(WEB / "painel.html", "text/html; charset=utf-8")
            if u.path in ("/loja/interna", "/loja/interna/"):
                # a pagina em si nao tem dado; os dados internos so vem com sessao
                return self._arquivo(WEB / "painel.html", "text/html; charset=utf-8")
            if u.path.startswith("/api/") and self._barrado():
                return
            if u.path in ("/sustainkit", "/sustainkit/") and (WEB / "sustainkit.html").exists():
                if self._barrado():
                    return
                return self._arquivo(WEB / "sustainkit.html", "text/html; charset=utf-8")
            if u.path in ("/loja", "/loja/"):
                # a loja e publica: quem compra nao tem, nem deve ter, conta na gestao
                return self._arquivo(WEB / "painel.html", "text/html; charset=utf-8")
            if u.path == "/api/central/arquivos":
                # dado pessoal (anexos de quem pediu proposta): sempre com sessão da equipe, com ou sem login na instalação
                if not self._exigir(seg.EQUIPE):
                    return
                return self._json(200, {"ok": True, "arquivos": hub.arquivos_de((parse_qs(u.query).get("pedido") or [""])[0])})
            if u.path.startswith("/api/central/arquivo/"):
                if not self._exigir(seg.EQUIPE):
                    return
                arq = hub.arquivo(u.path.rsplit("/", 1)[-1])
                if not arq:
                    return self._json(404, {"ok": False})
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8\'\'" + quote(arq[0]))
                self.send_header("Content-Length", str(len(arq[1])))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(arq[1])
                return
            if u.path == "/api/central/caixa":
                # compras e pedidos trazem nome, e-mail e CPF de quem pagou: sempre com sessão da equipe
                if not self._exigir(seg.EQUIPE):
                    return
                return self._json(200, {"ok": True, "itens": hub.central_listar()})
            if u.path in ("/gestao", "/gestao/") and (WEB / "gestao.html").exists():
                # sem sessão, a página de entrada; a Gestão (e o que ela traz embutido) só depois do login
                if not self._quem():
                    pagina = PAGINA_ENTRAR.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(pagina)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(pagina)
                    return
                return self._arquivo(WEB / "gestao.html", "text/html; charset=utf-8")
            if u.path.startswith("/app/"):
                # app instalável (PWA): manifestos, ícones e service worker. Só os da lista e sem login:
                # o celular precisa deles para instalar antes de qualquer entrada.
                r = app_pwa.resposta(unquote(u.path[len("/app/"):]), WEB)
                if not r:
                    return self._json(404, {"ok": False, "erro": "arquivo desconhecido"})
                corpo, cabecalhos = r
                self.send_response(200)
                for k, v in cabecalhos.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(corpo)
                return
            if u.path in ("/marca/logo-clara.svg", "/marca/logo-escura.svg"):
                # logo da marca própria da instalação (montar.py, web/marca/): só estes dois nomes, sem login (cabeçalho)
                arq = WEB / "marca" / u.path[len("/marca/"):]
                if not arq.is_file():
                    return self._json(404, {"ok": False, "erro": "sem marca própria"})
                return self._arquivo(arq, "image/svg+xml")
            if u.path.startswith("/vendor/"):
                # bibliotecas abertas guardadas no próprio sistema (mapa e BIM); só as da lista, nunca um caminho qualquer
                nome = u.path[len("/vendor/"):]
                tipo = VENDOR_TIPOS.get(nome)
                arq = next((p for p in (WEB / "vendor" / nome, WEB.parent.parent / "vendor" / nome) if tipo and p.is_file()), None)
                if not arq:
                    return self._json(404, {"ok": False, "erro": "biblioteca desconhecida"})
                dados = arq.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(dados)))
                self.send_header("Cache-Control", "public, max-age=604800, immutable")
                self.end_headers()
                self.wfile.write(dados)
                return
            if u.path.startswith("/mapas/"):
                return self._mapa(u.path)
            if u.path in ("/planejador", "/planejador/") and (WEB / "planejador.html").exists():
                if self._barrado():
                    return
                return self._arquivo(WEB / "planejador.html", "text/html; charset=utf-8")
            if u.path in ("/supervisao", "/supervisao/") and (WEB / "supervisao.html").exists():
                if self._barrado():
                    return
                return self._arquivo(WEB / "supervisao.html", "text/html; charset=utf-8")
            if u.path == "/api/painel":
                return self._json(200, hub.painel())
            if u.path == "/api/clima":
                # previsão das fontes guardadas no hub (a tela nunca chama a internet)
                return self._json(200, clima.estado())
            if u.path == "/api/suporte":
                # os contatos da Physis são públicos; os chamados (com contato de quem abriu) só com sessão:
                # a equipe vê todos, o cliente só os que ele abriu
                q = self._quem()
                contatos = {"whatsapp": re.sub(r"\D", "", os.environ.get("PHYSIS_SUPORTE_WHATSAPP") or instancia.get("suporte_whatsapp") or ""),
                            "email": os.environ.get("PHYSIS_SUPORTE_EMAIL") or instancia.get("suporte_email") or ""}
                if not q:
                    return self._json(200, {"ok": True, "chamados": [], "login": True, **contatos})
                return self._json(200, {"ok": True, "chamados": hub.suporte_listar(None if seg.pode(q, seg.EQUIPE) else q["usuario"]), **contatos})
            if u.path in ("/api/gis/relevo", "/api/gis/solo", "/api/gis/rio"):
                # relevo (curvas de nível e declividade), solo e rio (enchente) do lugar, guardados no hub
                try:
                    lat, lon = float(q.get("lat", [""])[0]), float(q.get("lon", [""])[0])
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "lat e lon são obrigatórios"})
                if not (-35.0 <= lat <= 6.0 and -75.0 <= lon <= -28.0):
                    return self._json(400, {"ok": False, "erro": "coordenadas fora do Brasil"})
                extra = gis_mod.GisExtra(irradiacao)
                return self._json(200, getattr(extra, u.path.rsplit("/", 1)[-1])(lat, lon))
            if u.path == "/api/gis/hidrografia":
                # rios e nascentes da camada instalada no servidor (PHYSIS_HIDROGRAFIA), recortados na janela pedida
                r = gis_mod.hidrografia(q.get("bbox", [""])[0].split(","))
                return self._json(200 if r.get("ok") or r.get("sem_camada") else 400, r)
            if u.path in ("/api/gis/irradiacao", "/api/gis/clima"):
                # base GIS de clima do lugar (ponto + grade da região), buscada uma vez e guardada no hub
                try:
                    lat, lon = float(q.get("lat", [""])[0]), float(q.get("lon", [""])[0])
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "lat e lon são obrigatórios"})
                r = irradiacao.consultar(lat, lon, q.get("camada", ["irradiacao"])[0] if u.path.endswith("clima") else "irradiacao")
                return self._json(200 if r["ok"] or not r.get("erro") else 400, r)
            if u.path in ("/api/gis/zonas", "/api/gis/solo-grade", "/api/gis/vento", "/api/gis/residuos"):
                # zonas do lugar (IBGE + Köppen), mapa de solo da região, vento em altura e destinos de resíduos:
                # buscados uma vez e guardados no hub
                try:
                    lat, lon = float(q.get("lat", [""])[0]), float(q.get("lon", [""])[0])
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "lat e lon são obrigatórios"})
                if not (-35.0 <= lat <= 6.0 and -75.0 <= lon <= -28.0):
                    return self._json(400, {"ok": False, "erro": "coordenadas fora do Brasil"})
                if u.path.endswith("zonas"):
                    r = zonas_mod.Zonas(irradiacao).consultar(lat, lon)
                elif u.path.endswith("solo-grade"):
                    r = gis_mod.GisExtra(irradiacao).solo_grade(lat, lon, q.get("prop", ["phh2o"])[0], q.get("prof", ["0-5cm"])[0])
                elif u.path.endswith("vento"):
                    r = vento_mod.Vento(irradiacao).consultar(lat, lon)
                else:
                    try:
                        raio = float(q.get("raio", [str(residuos_mod.RAIO_PADRAO)])[0])
                    except ValueError:
                        return self._json(400, {"ok": False, "erro": "raio precisa ser número"})
                    r = residuos_mod.ResiduosGis(irradiacao).consultar(lat, lon, raio)
                return self._json(200 if r.get("ok") or not r.get("erro") else 400, r)
            # ── Aprendizado (modelos do próprio hub, sem internet) ──
            if u.path.startswith("/api/aprendizado/"):
                if self._barrado():
                    return
                qual = u.path.rsplit("/", 1)[-1]
                fn = {"estado": aprendizado.estado, "anomalias": aprendizado.anomalias, "previsao-chuva": aprendizado.previsao_chuva,
                      "consumo": aprendizado.consumo, "irrigacao": aprendizado.irrigacao}.get(qual)
                if fn:
                    return self._json(200, fn())
            if u.path == "/api/robos":
                if not self._exigir(seg.CLIENTE):
                    return
                return self._json(200, {"ok": True, "robos": robos_mod.listar(robos)})
            if u.path in ("/api/alertas/assinaturas", "/api/alertas/historico"):
                qs = self._sessao_ou_401()
                if not qs:
                    return
                quem = None if seg.pode(qs, seg.DIRECAO) else qs["usuario"]          # a direção vê todas
                if u.path.endswith("/historico"):
                    return self._json(200, {"ok": True, "historico": alertas.historico(quem=quem)})
                return self._json(200, {"ok": True, "assinaturas": alertas.assinaturas(quem),
                                        "regras": {k: v[0] for k, v in alertas_mod.REGRAS.items()},
                                        "atividades": list(alertas_mod.ATIVIDADES), "finalidade": alertas_mod.FINALIDADE,
                                        # aprendidas da descrição do negócio: valem quando a assinatura não escolhe nenhuma
                                        "atividades_perfil": alertas.atividades_do_perfil(),
                                        "whatsapp": bool(alertas.whatsapp), "agora": alertas.alertas_agora()})
            if u.path == "/api/saude":
                integra, n = hub.verificar_cadeia()
                p = hub.painel()["saude"]
                p["registro"] = {"integro": integra, "entradas": n}
                return self._json(200, p)
            if u.path == "/api/leituras":
                try:
                    lim = int(q.get("limite", ["1000"])[0]); no = q.get("no", [""])[0]
                    return self._json(200, hub.leituras(lim, int(no) if no else None))
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "limite ou no invalido"})
            if u.path == "/api/serie":
                return self._json(200, hub.serie(q.get("ativo", [""])[0], q.get("grandeza", [""])[0]))
            if u.path in ("/", "/painel.html"):
                arq = WEB / "painel.html"
                if not arq.exists():
                    return self._json(404, {"ok": False, "erro": "painel.html ausente"})
                dados = arq.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)
                return
            self._json(404, {"ok": False, "erro": "rota desconhecida"})

        def do_PUT(self):
            u = urlparse(self.path)
            if self._csrf_barrado() or self._suporte_barrado(u, "PUT"):
                return
            if u.path.startswith("/api/gestao/arquivo/"):
                q = self._exigir(seg.EQUIPE)
                if not q:
                    return
                dados = self._corpo_grande(hub.GESTAO_ARQ_MAX)
                if dados is None:
                    return self._recusar_corpo("arquivo vazio ou maior que 20 MB")
                nome = unquote(self.headers.get("X-Nome") or "arquivo")
                r = hub.gestao_arquivo_por(u.path.rsplit("/", 1)[-1], nome, self.headers.get("Content-Type") or "", dados, q["usuario"])
                return self._json(200 if r["ok"] else 400, r)
            if u.path.startswith("/api/cliente/estado/"):
                return self._gravar_cliente(unquote(u.path[len("/api/cliente/estado/"):]))
            self._json(404, {"ok": False, "erro": "rota desconhecida"})

        def _gravar_cliente(self, chave: str) -> None:
            """PUT /api/cliente/estado/<chave> {"valor": texto, "versao": n} (ou cabeçalho If-Match: "v<n>").
            200 + ETag; 409 (conflito) com o valor, a versão e quem gravou; 413 grande demais; 400 chave fora da lista."""
            bruto = self._corpo_grande(perfil_cliente.VALOR_MAX + 4096)
            if bruto is None:
                return self._recusar_corpo("dados ausentes ou maiores que 2 MB")
            q = self._exigir(seg.CLIENTE)
            if not q:
                return
            if not perfil_cliente.chave_valida(chave):
                return self._json(400, {"ok": False, "erro": "chave nao permitida"})
            try:
                d = seg.carregar_json(bruto)
            except (ValueError, UnicodeDecodeError):
                return self._json(400, {"ok": False, "erro": "json invalido"})
            if not isinstance(d, dict) or not isinstance(d.get("valor"), str) or set(d) - {"valor", "versao"}:
                return self._json(400, {"ok": False, "erro": "envie {valor: texto, versao: número}"})
            versao = d.get("versao")
            if versao is None:
                m = re.fullmatch(r'(?:W/)?"?v(\d{1,12})"?', (self.headers.get("If-Match") or "").strip())
                versao = int(m.group(1)) if m else 0
            if not isinstance(versao, int) or isinstance(versao, bool) or versao < 0:
                return self._json(400, {"ok": False, "erro": "versao invalida"})
            r = hub.cliente_gravar(chave, d["valor"], versao, q["usuario"])
            if r.get("conflito"):
                return self._json(409, r, {"ETag": f'"v{r["versao"]}"'})
            if not r["ok"]:
                return self._json(413 if r.get("grande") else 400, r)
            return self._json(200, r, {"ETag": f'"v{r["versao"]}"'})

        def do_DELETE(self):
            u = urlparse(self.path)
            if self._csrf_barrado() or self._suporte_barrado(u, "DELETE"):
                return
            if u.path.startswith("/api/gestao/arquivo/"):
                q = self._exigir(seg.EQUIPE)
                if not q:
                    return
                return self._json(200, {"ok": hub.gestao_arquivo_apagar(u.path.rsplit("/", 1)[-1], q["usuario"])})
            if u.path.startswith("/api/mapeamento/"):           # apagar um arquivo do cliente (Mapeamento)
                qm = self._exigir(seg.CLIENTE)
                if qm:
                    self._rota_mapeamento("DELETE", u, parse_qs(u.query), None, qm)
                return
            self._json(404, {"ok": False, "erro": "rota desconhecida"})

        def do_POST(self):
            u = urlparse(self.path)
            if self._csrf_barrado() or self._suporte_barrado(u, "POST"):
                return
            # ── "Permitir suporte" (suporte_remoto.py): a direção libera e revoga; a equipe Physis entra pela VPN ──
            if u.path in ("/api/suporte-remoto/conceder", "/api/suporte-remoto/revogar"):
                qd = self._exigir(seg.DIRECAO)
                if not qd:
                    return
                if u.path.endswith("conceder"):
                    d = self._ler(self._corpo(), "suporte_conceder")
                    if d is None:
                        return
                    r = suporte.conceder(qd, d.get("duracao", ""), d.get("nota") or "", bool(d.get("so_ver")), self._ip())
                else:
                    d = self._ler(self._corpo(), "suporte_revogar")
                    if d is None:
                        return
                    r = suporte.revogar(qd, d.get("id", ""), self._ip())
                return self._json(r.pop("codigo", 200), r)
            if u.path == "/api/suporte-remoto/entrar":
                d = self._ler(self._corpo(), "suporte_entrar")
                if d is None:
                    return
                r = suporte.entrar(d.get("codigo", ""), d.get("equipe", ""), self._ip(), self.headers.get("User-Agent", ""))
                if not r.get("ok"):
                    return self._json(r.pop("codigo", 403), r)
                idade = max(1, int(r["expira"] - hub.relogio()))
                cookie = (f"physis_suporte={r.pop('token')}; Path=/; Max-Age={idade}; HttpOnly; SameSite=Strict" + ("; Secure" if self._https() else ""))
                return self._json_cookie(200, r, cookie)
            if u.path == "/api/suporte-remoto/sair":
                suporte.sair(self._token_suporte(), self._quem(), self._ip())
                return self._json_cookie(200, {"ok": True}, "physis_suporte=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict")
            # PDF/A, documento para comentários e importação de bairros: corpo maior que o normal
            if self._rotas_novas_post_grandes(u):
                return
            # ── Editais, eventos e e-mail escrito na Gestão (vai para a fila email_saida que já existe) ──
            if u.path.startswith(("/api/editais", "/api/eventos")) or u.path == "/api/gestao/correio":
                q = self._quem()
                if q and not seg.pode(q, seg.EQUIPE):
                    return self._json(403, SEM_PAPEL)
                if q and u.path.endswith("/fontes") and not seg.pode(q, seg.DIRECAO):   # configurar as fontes: só a direção
                    return self._json(403, SEM_PAPEL)
                r = editais_mod.rota("POST", u.path, q, self._corpo(), editais_col, eventos_col, hub, correio)
                if r:
                    return self._json(*r)
            # ── Suporte ao cliente: chamado + e-mail para a Physis (e-mail e WhatsApp vêm da configuração) ──
            if u.path == "/api/suporte":
                q = self._quem()
                if self._precisa_sessao() and not q:
                    return self._json(401, {"ok": False, "erro": "entre com usuario e senha", "login": True})
                if not q and self._limitado("publico"):
                    return
                d = self._ler(self._corpo(), "suporte", estrito=False)
                if d is None:
                    return
                para = os.environ.get("PHYSIS_SUPORTE_EMAIL") or instancia.get("suporte_email") or ""
                r = hub.suporte_abrir(d if isinstance(d, dict) else {}, (q or {}).get("nome", ""), para, (q or {}).get("usuario", ""))
                if r.get("ok"):
                    threading.Thread(target=correio.enviar_fila, args=(hub, r["numero"]), daemon=True).start()
                return self._json(200 if r["ok"] else 400, r)
            # ── Caixa de chamados (equipe): situação, responsável, nota interna e resposta por e-mail ao cliente ──
            if u.path.startswith("/api/suporte/chamados/"):
                q = self._exigir(seg.EQUIPE)
                if not q:
                    return
                d = self._ler(self._corpo(), "chamado")
                if d is None:
                    return
                r = hub.suporte_atualizar(unquote(u.path[len("/api/suporte/chamados/"):]), d, q["usuario"])
                if r.get("ref"):
                    self._mandar(r["ref"])
                    r["email"] = "enviando" if correio.configurado() else "pendente"
                return self._json(200 if r["ok"] else r.pop("codigo", 400), r)
            # ── DWG para DXF (Planejador): conversor aberto LibreDWG (dwg2dxf) instalado no servidor ──
            if u.path == "/api/converter/dwg":
                q = self._quem()
                if self._precisa_sessao() and not q:
                    return self._json(401, {"ok": False, "erro": "entre com usuario e senha", "login": True})
                if not exige_login and not self._autorizado():
                    return self._json(401, {"ok": False, "erro": "token ausente ou invalido"})
                dados = self._corpo_grande(DWG_MAX)
                if dados is None:
                    return self._recusar_corpo("arquivo DWG vazio ou maior que 50 MB")
                r = converter_dwg(dados)
                if not r["ok"]:
                    return self._json(r["codigo"], {"ok": False, "erro": r["erro"]})
                self.send_response(200)
                self.send_header("Content-Type", "application/dxf")
                self.send_header("Content-Length", str(len(r["dxf"])))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(r["dxf"])
                return
            # ── Localização do lugar e previsão do tempo ──
            if u.path in ("/api/clima/local", "/api/clima/atualizar"):
                q = self._quem()
                if self._precisa_sessao() and not q:
                    return self._json(401, {"ok": False, "erro": "entre com usuario e senha", "login": True})
                if not exige_login and not self._autorizado():
                    return self._json(401, {"ok": False, "erro": "token ausente ou invalido"})
                if u.path.endswith("/atualizar"):
                    return self._json(200, {"ok": True, "consultas": clima.consultar_tudo(), "estado": clima.estado()})
                try:
                    d = seg.carregar_json(self._corpo() or "{}")
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                r = clima.definir_local(d if isinstance(d, dict) else {}, (q or {}).get("usuario", ""))
                return self._json(200 if r["ok"] else 400, r)
            # ── Saúde: linhas dos aparelhos (MED/PUL, a homologar) e ações da tela ──
            if u.path == "/api/saude/linha":
                corpo = self._corpo()
                if corpo is None:
                    return self._recusar_corpo("corpo invalido ou grande demais")
                if self._limitado("dispositivo"):
                    return
                ok, no = self._dispositivo(saude_linha=True)
                if not ok:
                    return
                corpo, _ = seg.filtrar_do_no(corpo, no)
                res = [saude.registrar_evento(l, origem="aparelho") for l in corpo.split("\n") if l.strip()]
                for aid in {a for r in res for a in r.get("alertas", [])}:
                    threading.Thread(target=correio.enviar_fila, args=(hub, f"saude-{aid}"), daemon=True).start()
                return self._json(200, {"ok": True, "aceitas": sum(1 for r in res if r.get("ok") and not r.get("duplicada")),
                                        "linhas": [{"ok": r.get("ok"), "motivo": r.get("motivo", "")} for r in res]})
            if u.path.startswith("/api/saude/"):
                q = self._sessao_ou_401()
                if not q:
                    return
                try:
                    d = seg.carregar_json(self._corpo() or "{}")
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                r = saude.executar(u.path[len("/api/saude/"):], d if isinstance(d, dict) else {}, q["usuario"])
                return self._json(200 if r.get("ok") else r.pop("codigo", 400), r)
            # ── Gestão no servidor: dados, contas e senha (sempre com sessão) ──
            if u.path.startswith("/api/gestao/estado/"):
                q = self._exigir(seg.EQUIPE)
                if not q:
                    return
                bruto = self._corpo_grande(hub.GESTAO_VALOR_MAX + 4096)
                if bruto is None:
                    return self._recusar_corpo("dados ausentes ou grandes demais")
                try:
                    d = seg.carregar_json(bruto)
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                if not isinstance(d, dict) or not isinstance(d.get("versao") or 0, int) or isinstance(d.get("versao"), bool):
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                r = hub.gestao_gravar(unquote(u.path[len("/api/gestao/estado/"):]), d.get("valor"), d.get("versao") or 0, q["usuario"])
                return self._json(409 if r.get("conflito") else (200 if r["ok"] else 400), r)
            if u.path in ("/api/contas", "/api/conta/senha") or (u.path.startswith("/api/contas/") and u.path.count("/") == 3):
                q = self._sessao_ou_401()
                if not q:
                    return
                esq = "senha" if u.path == "/api/conta/senha" else ("contas" if u.path == "/api/contas" else "conta_alterar")
                d = self._ler(self._corpo(), esq, estrito=False)
                if d is None:
                    return
                if u.path != "/api/conta/senha" and not seg.pode(q, seg.DIRECAO):
                    return self._json(403, SEM_PAPEL)
                # dar papel de direção, mudar papel, desativar ou trocar a senha de outra pessoa: pede a senha de novo
                if u.path != "/api/conta/senha" and (seg.normalizar_papel(d.get("papel")) == seg.DIRECAO or
                                                     (u.path != "/api/contas" and (d.get("papel") is not None or d.get("ativa") is False
                                                                                   or d.get("senha") is not None))):
                    if not self._sensivel(q):
                        return
                if u.path == "/api/conta/senha":
                    r = hub.trocar_senha(q["id"], str(d.get("atual", "")), str(d.get("nova", "")))
                    if r["ok"]:
                        seg.evento_seguranca(hub, "senha trocada", q["usuario"], ip=self._ip())
                elif u.path == "/api/contas":
                    r = hub.criar_conta(str(d.get("nome", "")), str(d.get("usuario", "")), str(d.get("senha", "")), q["id"],
                                        str(d.get("pessoa") or ""), str(d.get("papel") or "operador"))
                    if r["ok"] and r.get("id"):
                        self._mandar(seg.confirmar_enviar(hub, r["id"], url_publica))
                else:
                    alvo = unquote(u.path.rsplit("/", 1)[-1])
                    r = hub.alterar_conta(q["id"], alvo, senha=d.get("senha") if isinstance(d.get("senha"), str) else None,
                                          ativa=d.get("ativa") if isinstance(d.get("ativa"), bool) else None,
                                          papel=d.get("papel") if isinstance(d.get("papel"), str) else None,
                                          pessoa=d.get("pessoa") if isinstance(d.get("pessoa"), str) else None)
                return self._json(200 if r["ok"] else 400, r)
            # ── Fluxos de conta (seguranca.py): esqueci a senha, confirmar e-mail, convite, consentimento, 2FA ──
            if u.path.startswith("/api/conta/") or u.path.startswith("/api/convites"):
                r = self._rotas_conta(u.path)
                if r is not False:
                    return
            # ── Consultoria ── gravar textos do site: sempre com sessão, mesmo em instalação sem login
            if u.path.startswith("/api/site/textos/"):
                # lê o corpo antes de responder, mesmo sem sessão: no Windows, fechar com bytes
                # não lidos corta a conexão (RST) e quem enviou não vê o 401
                bruto = self._corpo_grande(1024 * 1024)
                if bruto is None:
                    return self._recusar_corpo("textos ausentes ou maiores que 1 MB")
                q = self._exigir(seg.DIRECAO)          # textos do site público: só a direção
                if not q:
                    return
                try:
                    d = seg.carregar_json(bruto)
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                if isinstance(d, dict) and isinstance(d.get("textos"), dict) and len(d) == 1:
                    d = d["textos"]          # aceita {"textos": {...}} ou {chave: texto}
                r = hub.site_gravar(u.path[len("/api/site/textos/"):], d, q["usuario"])
                return self._json(200 if r["ok"] else 400, r)
            # ── fim Consultoria ──
            if u.path == "/api/central/arquivo":
                # arquivo de apoio do pedido: corpo binario, ate 20 MB; publico como o proprio pedido (com limite por IP)
                if self._limitado("arquivo"):
                    return
                q = parse_qs(u.query)
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    n = -1
                if n <= 0 or n > hub.ARQUIVO_MAX:
                    return self._recusar_corpo("arquivo vazio ou maior que 20 MB")
                self._corpo_lido = True
                r = hub.arquivo_por((q.get("pedido") or [""])[0], (q.get("nome") or [""])[0], self.rfile.read(n))
                return self._json(200 if r["ok"] else 400, r)
            corpo = self._corpo()
            if corpo is None:
                return self._recusar_corpo("corpo invalido ou grande demais")
            # ── Município (operador), evidências e parceiros ──
            if self._rotas_novas_post(u, corpo):
                return
            # ── Aprendizado, robôs e alertas de clima ──
            if u.path == "/api/aprendizado/treinar":
                if not self._exigir(seg.DIRECAO):
                    return
                return self._json(200, aprendizado.treinar())
            if u.path.startswith("/api/robos/"):
                qs = self._sessao_ou_401()
                if not qs:
                    return
                try:
                    d = seg.carregar_json(corpo or "{}")
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                d = d if isinstance(d, dict) else {}
                d["_quem"] = qs["usuario"]                  # quem abre o chamado do suporte (vem da sessão, nunca do corpo)
                # público da resposta (vem da sessão, nunca do corpo): cliente só vê manual e curso; equipe vê também a doc técnica
                d["_publico"] = "equipe" if seg.pode(qs, seg.EQUIPE) else "cliente"
                cod, r = robos_mod.atender(u.path.rsplit("/", 1)[-1], d, robos)
                return self._json(cod, r)
            if u.path == "/api/alertas/assinaturas":
                qs = self._sessao_ou_401()
                if not qs:
                    return
                try:
                    d = seg.carregar_json(corpo or "{}")
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                if not isinstance(d, dict):
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                admin = seg.pode(qs, seg.DIRECAO)
                if d.get("acao") == "sair":
                    r = alertas.sair(int(d.get("id") or 0), qs["usuario"], admin=admin)
                else:
                    d.pop("_admin", None)
                    if admin:
                        d["_admin"] = True
                    r = alertas.assinar(d, qs["usuario"])
                return self._json(r.pop("codigo", 200 if r["ok"] else 400), r)
            if u.path == "/api/gis/residuos/importar":
                if not self._exigir(seg.EQUIPE):
                    return
                try:
                    pts = (residuos_mod.importar_geojson(seg.carregar_json(corpo)) if corpo.lstrip().startswith("{")
                           else residuos_mod.importar_csv(corpo))
                except ValueError as exc:
                    return self._json(400, {"ok": False, "erro": str(exc)})
                return self._json(200, residuos_mod.ResiduosGis(irradiacao).importar(pts))
            # Entrega dos aparelhos: chave por dispositivo (Authorization: Bearer / X-Physis-Chave). Sem chave,
            # só da rede local (o receptor V6 atual ainda não manda chave) ou com PHYSIS_ACEITAR_SEM_CHAVE=1.
            recusadas = 0
            if u.path in ("/api/gateway/webhook", "/api/hardware/gateway", "/api/v6/linha"):
                if self._limitado("dispositivo"):
                    return
                ok, no = self._dispositivo()
                if not ok:
                    return
                corpo, recusadas = seg.filtrar_do_no(corpo, no)
            if u.path in ("/api/gateway/webhook", "/api/hardware/gateway"):
                r = hub.receber_lote(corpo, origem="receptor")
                if recusadas:
                    r["recusadas_outro_no"] = recusadas
                return self._json(200, r)
            if u.path == "/api/v6/linha":
                r = hub.receber_lote(corpo, origem="esp-wifi")
                if recusadas:
                    r["recusadas_outro_no"] = recusadas
                # comandos pendentes do(s) no(s) que acabaram de falar
                pend: list[str] = []
                for bruta in corpo.split("\n"):
                    ok, _, campos = validar_telemetria(bruta)
                    if ok:
                        pend += hub.comandos_pendentes(para_int(campos["ID"], -1))
                r["comandos"] = pend
                return self._json(200, r)
            if u.path in ("/api/central/compra", "/api/central/pedido"):
                # a loja entrega aqui; nao exige login porque quem compra nao tem conta na gestao (limite por IP)
                if self._limitado("publico"):
                    return
                tipo = u.path.rsplit("/", 1)[-1]
                try:
                    d = seg.carregar_json(corpo or "{}")
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                if len(corpo or "") > 64_000 or d.get("_formato") != f"physis-{tipo}/1" or not isinstance(d.get("numero"), str):
                    return self._json(400, {"ok": False, "erro": "registro invalido"})
                r = hub.central_por(tipo, d["numero"], d)
                return self._json(200 if r["ok"] else 400, r)
            if u.path == "/api/central/alocacao":
                # interno: a direcao define os consultores e cada consultor aceita a sua parte
                if not self._exigir(seg.EQUIPE):
                    return
                try:
                    d = seg.carregar_json(corpo or "{}")
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                if len(corpo or "") > 64_000 or d.get("_formato") != "physis-alocacao/1" or not isinstance(d.get("id"), str):
                    return self._json(400, {"ok": False, "erro": "registro invalido"})
                r = hub.central_gravar("alocacao", d["id"], d)
                return self._json(200 if r["ok"] else 400, r)
            if u.path.startswith("/api/central/compra/") and u.path.endswith("/aprovar"):
                q = self._exigir(seg.DIRECAO)          # aprovar dispara a montagem e o código: só a direção
                if not q or not self._sensivel(q):     # e com a senha confirmada há pouco
                    return
                numero = u.path.split("/")[-2]
                ok = hub.central_marcar("compra", numero, "aprovado", q["usuario"] if q else "")
                if not ok:
                    return self._json(404, {"ok": False})
                # montagem automática: número, plataforma, código e e-mail de acesso
                base = url_publica or (("https" if self._https() else "http") + "://" + (self.headers.get("Host") or "localhost"))
                inst = hub.instalar_compra(numero, base, fabricar, q["usuario"] if q else "")
                if inst.get("ok") and not inst.get("repetido"):
                    # manual (só os módulos comprados), contrato e dados da NF: rascunhos na fila de emissão (revisão e aprovação)
                    try:
                        docs = docauto.documentos_da_compra(numero, inst.get("modulos") or [], q["usuario"] if q else "sistema")
                        inst["manual"], inst["documentos"] = docs.get("manual"), docs
                    except Exception as e:          # o manual não derruba a aprovação; a equipe vê no registro
                        hub.registrar("documento_auto", numero, {"o_que": "manual não gerado", "erro": type(e).__name__})
                if inst.get("ok") and not inst.get("repetido") and correio.configurado():
                    threading.Thread(target=correio.enviar_fila, args=(hub, inst["numero"]), daemon=True).start()
                    inst["email"] = "enviando"
                return self._json(200, {"ok": True, "instalacao": inst})
            if u.path.startswith("/api/ativar/"):
                # o cliente digita o código do e-mail; certo -> baixa a plataforma montada para ele
                if self._limitado("entrar"):
                    return
                try:
                    d = seg.carregar_json(corpo or "{}")
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                r = hub.ativar(u.path.rsplit("/", 1)[-1], str(d.get("codigo", "")) if isinstance(d, dict) else "")
                if not r["ok"]:
                    return self._json(429 if r.get("espera") else 403, r)
                pac = Path(r["pacote"]) if r.get("pacote") else None
                if pac and pac.is_file():
                    dados = pac.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                    self.send_header("Content-Disposition", "attachment; filename=\"physis-" + r["numero"] + ".zip\"")
                    self.send_header("Content-Length", str(len(dados)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(dados)
                    return
                return self._json(200, {"ok": True, "pacote": False, "numero": r["numero"]})
            if u.path.startswith("/api/central/emails/"):
                # a equipe marca como enviado à mão, ou manda tentar de novo pelo servidor de e-mail
                if not self._exigir(seg.EQUIPE):
                    return
                partes = u.path.split("/")
                if len(partes) != 6 or not partes[4].isdigit() or partes[5] not in ("enviado", "enviar"):
                    return self._json(404, {"ok": False, "erro": "rota desconhecida"})
                if partes[5] == "enviado":
                    return self._json(200, {"ok": hub.email_marcar(int(partes[4]), "enviado_a_mao")})
                e = [x for x in hub.emails() if x["id"] == int(partes[4])]
                if not e:
                    return self._json(404, {"ok": False})
                ok, erro = correio.enviar(e[0]["para"], e[0]["assunto"], e[0]["corpo"])
                hub.email_marcar(e[0]["id"], "enviado" if ok else "falhou", erro)
                return self._json(200 if ok else 502, {"ok": ok, "erro": erro})
            if u.path in ("/api/conta/criar", "/api/conta/entrar", "/api/conta/sair"):
                if u.path != "/api/conta/sair" and self._limitado("entrar"):     # por IP, além do limite por usuário do hub
                    return
                if u.path == "/api/conta/sair":
                    d = {}
                else:
                    d = self._ler(corpo, "criar" if u.path.endswith("criar") else "entrar", estrito=False)
                    if d is None:
                        return
                if u.path == "/api/conta/sair":
                    q = self._quem()
                    hub.sair(self._token_sessao())
                    if q:
                        seg.acesso_registrar(hub, q["usuario"], self._ip(), "saiu")
                    return self._json_cookie(200, {"ok": True}, self._cookie("", 0))
                if u.path == "/api/conta/criar":
                    q = self._quem()
                    # a primeira conta vira a direção: de fora da rede local, só com PHYSIS_PRIMEIRA_CONTA_EXTERNA=1
                    if not hub.tem_conta() and not self._local() and os.environ.get("PHYSIS_PRIMEIRA_CONTA_EXTERNA") != "1":
                        return self._json(403, {"ok": False, "erro": "a primeira conta só pode ser criada da rede local do servidor"})
                    r = hub.criar_conta(str(d.get("nome", "")), str(d.get("usuario", "")), str(d.get("senha", "")), q["id"] if q else None)
                    if not r["ok"]:
                        return self._json(400, r)
                    aceito, versao = seg._consentimento_do_corpo(d)
                    if aceito and r.get("id"):
                        seg.consentimento_registrar(hub, r["id"], str(d.get("usuario", "")).strip().lower(), versao, True, self._ip())
                    if not r.get("primeira"):
                        self._mandar(seg.confirmar_enviar(hub, r["id"], url_publica))
                        return self._json(200, r)
                r = hub.entrar(str(d.get("usuario", "")), str(d.get("senha", "")), self._ip(), self.headers.get("User-Agent") or "",
                               d.get("codigo") if isinstance(d.get("codigo"), str) else None)
                if not r.get("precisa_2fa"):
                    seg.acesso_registrar(hub, str(d.get("usuario", "")).strip().lower(), self._ip(),
                                         "entrou" if r["ok"] else ("bloqueado" if r.get("espera") else "senha errada"))
                if not r["ok"]:
                    return self._json(429 if r.get("espera") else 401, r)
                tk = r.pop("token")
                r["csrf"] = seg.csrf_de(hub, tk)
                return self._json_cookie(200, r, self._cookie(tk, hub.SESSAO_S))
            # ── LGPD art. 18, VI: a pessoa apaga a própria conta (confirma com a senha); ver seguranca.apagar_titular ──
            if u.path == "/api/conta/apagar":
                if self._limitado("entrar"):
                    return
                q = self._sessao_ou_401()
                if not q:
                    return
                d = self._ler(corpo, "apagar")
                if d is None:
                    return
                if q.get("dois_fatores") and not seg.segundo_fator(hub, q["id"], str(d.get("codigo") or ""), q["usuario"]):
                    return self._json(403, {"ok": False, "precisa_2fa": True, "erro": "Digite o código do aplicativo autenticador."})
                r = seg.apagar_titular(hub, q, str(d.get("senha", "")))
                if not r["ok"]:
                    return self._json(r.pop("codigo", 400), r)
                return self._json_cookie(200, r, self._cookie("", 0))
            # ── Chaves dos dispositivos (só a direção): criar devolve a chave UMA vez; revogar vale na hora ──
            if u.path == "/api/dispositivos/chaves" or (u.path.startswith("/api/dispositivos/chaves/") and u.path.endswith("/revogar")):
                q = self._exigir(seg.DIRECAO)
                if not q:
                    return
                if u.path.endswith("/revogar"):
                    ok = seg.chave_revogar(hub, u.path.split("/")[-2], q["usuario"])
                    return self._json(200 if ok else 404, {"ok": ok})
                d = self._ler(corpo, "chave")
                if d is None or not self._sensivel(q):
                    return
                r = seg.chave_criar(hub, d.get("no"), str(d.get("rotulo", "")), q["usuario"])
                return self._json(200 if r["ok"] else 400, r)
            if u.path.startswith("/api/loja/item/"):
                # catálogo da loja: sempre exige sessão da equipe, mesmo em instalação sem login; publicar, só a direção
                q = self._exigir(seg.EQUIPE)
                if not q:
                    return
                partes = u.path.split("/")          # ['', 'api', 'loja', 'item', <id>, (acao)]
                if len(partes) not in (5, 6):
                    return self._json(404, {"ok": False, "erro": "rota desconhecida"})
                try:
                    d = seg.carregar_json(corpo or "{}")
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                if not isinstance(d, dict):
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                ident, acao = partes[4], (partes[5] if len(partes) == 6 else "")
                if acao == "":
                    r = hub.loja_gravar(ident, d, q["usuario"])
                elif acao == "revisar":
                    r = hub.loja_revisar(ident, q["usuario"], bool(d.get("revisado", True)))
                elif acao == "publicar":
                    if not seg.pode(q, seg.DIRECAO):
                        return self._json(403, SEM_PAPEL)
                    r = hub.loja_publicar(ident, q["usuario"], bool(d.get("publico", True)))
                else:
                    return self._json(404, {"ok": False, "erro": "rota desconhecida"})
                return self._json(200 if r["ok"] else 400, r)
            if u.path == "/api/comando":
                if self._barrado():
                    return
                if not self._autorizado():
                    return self._json(401, {"ok": False, "erro": "token ausente ou invalido"})
                linha = corpo.strip()
                if linha.startswith("{"):
                    try:
                        c = seg.carregar_json(linha)
                        linha = str(c.get("comando", "")) if isinstance(c, dict) else ""
                        if len(linha) > 200:
                            return self._json(400, {"ok": False, "erro": "comando longo demais"})
                    except ValueError:
                        return self._json(400, {"ok": False, "erro": "json invalido"})
                r = hub.comandar(linha)
                return self._json(200 if r["ok"] else 400, r)
            self._json(404, {"ok": False, "erro": "rota desconhecida"})

    return Manipulador


def semear_loja(hub: Hub, caminho: Path | str | None = None) -> dict | None:
    """Site novo: publica o catálogo inicial (loja-catalogo-inicial.json ao lado do instancia.json, ou PHYSIS_LOJA_CATALOGO)
    quando nada foi publicado ainda. Sem o arquivo (instalação de cliente), não faz nada."""
    arq = Path(caminho or os.environ.get("PHYSIS_LOJA_CATALOGO") or LOJA_CATALOGO_INICIAL)
    if not arq.is_file():
        return None
    try:
        cat = json.loads(arq.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return hub.loja_semear_inicial(cat)


def iniciar(hub: Hub, porta: int = 8700, token: str | None = None, endereco: str = "0.0.0.0", instancia: dict | None = None,
            clima=None, irradiacao=None):
    semear_loja(hub)
    srv = ThreadingHTTPServer((endereco, porta), criar_manipulador(hub, token, instancia, clima, irradiacao))
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main() -> None:
    porta = int(os.environ.get("PHYSIS_PORTA", "8700"))
    rx = os.environ.get("PHYSIS_RX_URL")
    inst = ler_instancia()
    hub = Hub(banco_da_instancia(inst),
              org=os.environ.get("PHYSIS_ORG", inst.get("org", "org-teste")),
              lugar=os.environ.get("PHYSIS_LUGAR", inst.get("lugar", "lugar01")),
              enviar_comando=cliente_receptor(rx) if rx else None)
    parar = threading.Event()
    if rx:
        threading.Thread(target=consultar_receptor, args=(hub, rx, parar), daemon=True).start()
    sim = os.environ.get("PHYSIS_SIMULAR")
    if sim:
        a, b, c, d = (int(x) for x in sim.split(","))
        threading.Thread(target=simular, args=(hub, Simulador(a, b, c, d), parar), daemon=True).start()
    clima = clima_mod.Clima(hub, receptor_url=rx, enviar_local=clima_mod.receptor_local(rx) if rx else None)
    if os.environ.get("PHYSIS_CLIMA", "1") != "0":     # PHYSIS_CLIMA=0 desliga as consultas (sem internet de propósito)
        threading.Thread(target=clima_mod.rodar, args=(clima, parar), daemon=True).start()
    cfg_mqtt = mqtt_mod.config_de(ler_instancia())       # Caixinha Physis IoT (ESPHome) pelo broker MQTT
    if cfg_mqtt:
        threading.Thread(target=mqtt_mod.rodar, args=(hub, cfg_mqtt, parar), daemon=True).start()
    apr_fundo = aprendizado_mod.Aprendizado(hub)         # treina ao ligar (se o último tem mais de 1 dia) e às 3 h
    threading.Thread(target=aprendizado_mod.rodar, args=(apr_fundo, parar), daemon=True).start()
    alertas_fundo = alertas_mod.AlertasClima(hub, aprendizado=apr_fundo)   # alertas de clima a cada 15 min
    threading.Thread(target=alertas_mod.rodar, args=(alertas_fundo, parar),
                     kwargs={"enviar": lambda: alertas_mod.enviar_emails(hub, correio.enviar_fila)}, daemon=True).start()
    saude_fundo = saude_mod.Saude(hub)          # doses esquecidas e avisos aos cuidadores, mesmo sem a tela aberta
    threading.Thread(target=saude_mod.rodar, args=(saude_fundo, parar),
                     kwargs={"enviar": lambda: saude_mod.enviar_avisos(hub, correio.enviar_fila)}, daemon=True).start()
    # retenção (LGPD/Marco Civil): sessões vencidas, acessos com mais de 6 meses, e-mails não enviados... (PHYSIS_RETENCAO_DIAS_*)
    threading.Thread(target=seg.rodar_retencao, args=(hub, parar), daemon=True).start()
    # LGPD dos documentos para comentários: nome e e-mail do revisor externo saem depois do prazo (docs/EXPORTACAO.md)
    threading.Thread(target=rodar_diario, args=(documentos_mod.Documentos(hub).retencao, parar), daemon=True).start()
    # painel municipal: CEMADEN, INMET e rios a cada 15 min, como o clima (PHYSIS_CLIMA=0 desliga; docs/MUNICIPIO.md)
    if os.environ.get("PHYSIS_CLIMA", "1") != "0":
        mun_fundo = municipio_mod.Municipio(hub, clima=clima, aprendizado=apr_fundo)
        threading.Thread(target=municipio_mod.rodar, args=(mun_fundo, parar), daemon=True).start()
    # pegada do servidor: uma amostra a cada 5 min (PHYSIS_PEGADA=0 desliga; docs/PEGADA_SERVIDOR.md). A rota usa a mesma.
    cfg_pegada = pegada_mod.config_de(inst)
    if cfg_pegada is not None:
        threading.Thread(target=pegada_mod.rodar, args=(pegada_mod.para(hub, cfg_pegada), parar), daemon=True).start()
    endereco = os.environ.get("PHYSIS_ENDERECO") or "0.0.0.0"
    srv = iniciar(hub, porta, os.environ.get("PHYSIS_TOKEN"), endereco=endereco, clima=clima)
    # indicadores da plataforma (D18): coleta a cada 5 min no próprio laço do hub (sem cron, sem Agendador do Windows)
    if getattr(hub, "indicadores", None) is not None:
        threading.Thread(target=rodar_diario, args=(hub.indicadores.tarefa_periodica, parar, 300.0, 60.0), daemon=True).start()
    print(f"Physis Hub em http://{endereco}:{porta}  receptor={rx or 'nao configurado'}  simulador={sim or 'desligado'}")
    if not inst.get("login"):
        print("Aviso: instalação sem login. Telemetria aberta só para a rede local; de fora, tudo pede sessão (docs/SEGURANCA.md).")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        parar.set()
        srv.shutdown()
        hub.fechar()


if __name__ == "__main__":
    main()
