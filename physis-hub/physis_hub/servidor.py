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
from . import gemeo_painel as gemeo_painel_mod
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
from . import catalogo_modelos as catalogo_mod
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


def arquivo_do_hub(h) -> str:
    """Arquivo do banco aberto pelo hub (":memory:" nos testes)."""
    try:
        return h._db.execute("PRAGMA database_list").fetchone()[2] or ":memory:"
    except Exception:  # noqa: BLE001
        return ":memory:"


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
_PX_LOGO = "data:image/png;base64,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"

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
<p>Physis Engineering Ltda.</p>
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
for _k, _v in catalogo_mod.ESQUEMAS.items():              # catálogo técnico de modelos (docs/CATALOGO.md)
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
    # PHYSIS_EXIGIR_LOGIN=1: pede senha também na rede local (equipe acessando pela rede, 25/11/2026)
    exige_login = bool(instancia.get("login")) or os.environ.get("PHYSIS_EXIGIR_LOGIN") == "1"
    # cadastro aberto: qualquer pessoa cria a própria conta (papel cliente), ex.: InovaSTEM; PHYSIS_CADASTRO_ABERTO=1
    cadastro_aberto = bool(instancia.get("cadastro_aberto")) or os.environ.get("PHYSIS_CADASTRO_ABERTO") == "1"
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
                                       # catálogo técnico (multi-split etc.): PHYSIS_CATALOGO = um banco para todas as instalações
                                       "catalogo": lambda: catalogo_mod.Catalogo(catalogo_mod.caminho_padrao(arquivo_do_hub(hub)), hub=hub),
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
            # Gêmeo digital (gemeo_painel.py): resumo, semente e IFC, só com sessão; sem semente nesta instalação, 404
            if p == "/api/gemeo" or p.startswith("/api/gemeo/"):
                if self._exigir(seg.CLIENTE):
                    r = gemeo_painel_mod.rota(p, arquivo_instancia().parent)
                    if isinstance(r[0], str):
                        self._enviar_bytes(r[3], r[2], {"Content-Disposition": "attachment; filename*=UTF-8''" + quote(r[1]),
                                                        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
                    else:
                        self._json(*r)
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
            # Catálogo técnico de modelos (catalogo_modelos.py; docs/CATALOGO.md): cliente vê só o conferido; o resto equipe
            if p.startswith("/api/catalogo/"):
                qc = self._exigir(seg.CLIENTE)
                if qc:
                    cod, r = modulo("catalogo").rota("GET", p, qc, None, q)
                    if isinstance(r, tuple):                       # ("bytes", nome, tipo, dados): planilha-modelo e exportação
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
            # Catálogo técnico: planilha até 1 MB (equipe; o estado da planilha só vale para a direção); conferir só a direção;
            # seleção multi-split do AVAC para quem tem sessão (só lê o catálogo)
            if p.startswith("/api/catalogo/") or p == "/api/avac/multisplit":
                qc = self._exigir(seg.CLIENTE if p == "/api/avac/multisplit" else seg.EQUIPE)
                if not qc or (p == "/api/catalogo/importar" and self._limitado("arquivo")):
                    return True
                corpo = self._corpo_grande(catalogo_mod.CSV_MAX + 64 * 1024)
                if corpo is None and (self.headers.get("Content-Length") or "0").strip() == "0":
                    corpo = b"{}"
                if corpo is None:
                    self._recusar_corpo("planilha grande demais (máximo 1 MB)")
                    return True
                self._json(*modulo("catalogo").rota("POST", p, qc, corpo, parse_qs(u.query)))
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
                    "gemeo": gemeo_painel_mod.pasta_gemeo(arquivo_instancia().parent) is not None,
                    "cadastro_aberto": cadastro_aberto,
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
                    r = hub.criar_conta(str(d.get("nome", "")), str(d.get("usuario", "")), str(d.get("senha", "")), q["id"] if q else None,
                                        aberto=cadastro_aberto and not q)
                    if not r["ok"]:
                        return self._json(400, r)
                    aceito, versao = seg._consentimento_do_corpo(d)
                    if aceito and r.get("id"):
                        seg.consentimento_registrar(hub, r["id"], str(d.get("usuario", "")).strip().lower(), versao, True, self._ip())
                    if not r.get("primeira"):
                        self._mandar(seg.confirmar_enviar(hub, r["id"], url_publica))
                        if not (cadastro_aberto and not q):
                            return self._json(200, r)
                        # cadastro aberto: a pessoa já entra (a conta vale como cliente até confirmar o e-mail)
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


from .rede_http import ServidorHTTP as _ServidorHTTP   # porta exclusiva no Windows + fila de 128 (rede_http.py)


def iniciar(hub: Hub, porta: int = 8700, token: str | None = None, endereco: str = "0.0.0.0", instancia: dict | None = None,
            clima=None, irradiacao=None):
    semear_loja(hub)
    srv = _ServidorHTTP((endereco, porta), criar_manipulador(hub, token, instancia, clima, irradiacao))
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
    # 0.0.0.0 é "todas as placas de rede": serve para ligar, não para abrir no navegador (23/11/2026)
    print(f"Physis Hub: abra http://127.0.0.1:{porta}/ neste computador" + (f" (escutando em {endereco})" if endereco not in ("127.0.0.1", "localhost") else ""))
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
