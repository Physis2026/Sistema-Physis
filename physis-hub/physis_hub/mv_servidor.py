"""Servidor local do Physis M&V (VERSÃO DE TESTE): só em 127.0.0.1, porta 8710 (PHYSIS_MV_PORTA).
Tela em web/mv.html; API JSON em /api/mv/*; exportação ODS/ODT (e PDF/A quando houver LibreOffice).

Segurança desta fase (computador principal, D58): ouve só em 127.0.0.1, confere o cabeçalho Host e exige
X-Physis-MV: 1 em todo POST (um site de fora não consegue mandar esse cabeçalho). Na migração para o servidor físico
(dezembro, Eric) entra a conta da Gestão com papéis, como no hub.
"""
from __future__ import annotations

import base64
import hmac
import ipaddress
import json
import re
import os
import secrets
import socket
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import mv_integracoes  # noqa: E402
from . import documentos
from . import mv_bots
from . import mv_arquivos
from . import mv_comandos
from . import mv_editais
from .mv import ESTADOS, FRENTES, MV, NOMES_ESTADO, ErroMV

WEB = Path(__file__).resolve().parents[1] / "web"
VENDOR = Path(__file__).resolve().parents[2] / "vendor"
_IA = {}


def _ia():
    from .ia_physis import IAPhysis
    if "m" not in _IA:
        _IA["m"] = IAPhysis()
    return _IA["m"]


VENDOR_OK = {"three.min.js", "jszip.min.js"}       # bibliotecas abertas guardadas localmente (sem internet)
PORTA = int(os.environ.get("PHYSIS_MV_PORTA") or 8710)
CORPO_MAX = 256 * 1024
CORPO_UPLOAD = 56 * 1024 * 1024      # até 40 MB (modelos 3D) em base64
_TRAVA = threading.Lock()
NOME_FRENTE = {f[0]: f[1] for f in FRENTES}


def tabelas_exportacao(mv: MV, vista: str) -> tuple[str, list[dict]]:
    if vista == "editais":
        return "Physis M&V · propostas e editais", mv_editais.Editais(mv).planilha()
    if vista == "gantt" or vista == "tarefas":
        ts = mv.gantt()
        cab = ["Frente", "Projeto", "Tarefa", "Responsável", "Início (plano)", "Fim (plano)", "Prazo", "Folga (d)",
               "Crítica", "Atrasada", "Estado", "Data", "Versão", "Meta 2027–2031"]
        linhas = [[NOME_FRENTE[t["frente"]], t["projeto"], t["titulo"], t["responsavel"], t["plan_inicio"] or "", t["plan_fim"] or "",
                   t["fim"] or "", t["folga"] if t["folga"] is not None else "", "sim" if t["critico"] else "",
                   "sim" if t["atrasada"] else "", NOMES_ESTADO[t["estado"]], "[CONFERIR]" if t["data_estimada"] else "confirmada",
                   t["versao"], t["meta"] or ""] for t in ts]
        return "Physis M&V · cronograma", [{"nome": "Cronograma", "cab": cab, "linhas": linhas}]
    if vista == "alertas":
        cab = ["Gravidade", "Bot", "Frente", "Alerta", "Intervenção sugerida", "Desde"]
        linhas = [[a["gravidade"], a["bot"], NOME_FRENTE.get(a["frente"], ""), a["texto"], a["acao"],
                   datetime.fromtimestamp(a["criado"]).strftime("%Y-%m-%d")] for a in mv.alertas()]
        return "Physis M&V · alertas", [{"nome": "Alertas", "cab": cab, "linhas": linhas}]
    if vista == "documentos":
        cab = ["Situação", "Frente", "Tipo", "Documento", "Modificado", "Idade (d)", "Validade (d)", "Marcadores", "Falhas"]
        linhas = [[d["situacao"], NOME_FRENTE[d["frente"]], d["tipo"], d["caminho"], d["modificado"], d["idade_d"], d["validade_d"],
                   d["marcadores"], "; ".join(f'{f["texto"]} ({f["decisao"]})' for f in d["falhas"])] for d in mv.documentos()]
        return "Physis M&V · documentos", [{"nome": "Documentos", "cab": cab, "linhas": linhas}]
    if vista == "saude":
        s = mv.saude()
        cab = ["Frente", "Nota", "Confiança (% datas confirmadas)", "Total", "Feitas", "Atrasadas", "Bloqueadas", "Datas a conferir", "Progresso %"]
        linhas = [[f["nome"], f["nota"] if f["nota"] is not None else "sem dados", f["confianca_pct"], f["total"], f["feitas"], f["atrasadas"], f["bloqueadas"], f["datas_estimadas"],
                   f["progresso_pct"]] for f in s["frentes"].values()]
        fin = [[e, k, t, v] for e, d in s["financeiro"].items() for k in ("oficial", "a_conferir") for t, v in d[k].items()]
        r = mv.roadmap()
        metas = [[m["ano"], NOME_FRENTE[m["frente"]], m["titulo"], m["indicador"], m["alvo"], m["tarefas"], m["feitas"], m["fonte"]]
                 for m in r["metas"]]
        return "Physis M&V · saúde e metas", [
            {"nome": "Saúde", "cab": cab, "linhas": linhas},
            {"nome": "Metas 2027-2031", "cab": ["Ano", "Frente", "Meta", "Indicador", "Alvo", "Tarefas", "Feitas", "Fonte"], "linhas": metas},
            {"nome": "Financeiro", "cab": ["Entidade", "Situação", "Tipo", "Valor (R$)"], "linhas": fin}]
    raise ErroMV("vista inválida")


def exportar(mv: MV, vista: str, formato: str) -> tuple[bytes, str, str]:
    titulo, tabs = tabelas_exportacao(mv, vista)
    nome = f"physis-mv-{vista}-{datetime.now():%Y-%m-%d}"
    if formato == "ods":
        return documentos.ods(titulo, tabs, sistema="Physis M&V (teste)"), "application/vnd.oasis.opendocument.spreadsheet", nome + ".ods"
    blocos = []
    for tb in tabs:
        blocos += [{"h": 2, "t": tb["nome"]}, {"tabela": {"cab": tb["cab"], "linhas": [[str(c) for c in l] for l in tb["linhas"]]}}]
    odt = documentos.odt(titulo, blocos, sistema="Physis M&V (teste)")
    if formato == "odt":
        return odt, "application/vnd.oasis.opendocument.text", nome + ".odt"
    if formato == "pdf":
        r = documentos.converter_pdfa(odt)
        if r.get("ok") and r.get("pdf"):
            return r["pdf"], "application/pdf", nome + ".pdf"
        raise ErroMV("PDF indisponível: instale o LibreOffice (soffice) ou use ODT/ODS")
    raise ErroMV("formato inválido (ods, odt ou pdf)")


def fabricar(mv: MV):
    ed = mv_editais.Editais(mv)
    arq = mv_arquivos.Arquivos(mv)
    cmd = mv_comandos.Comandos(mv, arq)
    cmd.semear_aprovacoes(mv_comandos.APROVACOES_23_11)
    from . import mv_clientes
    cli = mv_clientes.Clientes(mv)
    cli.semear()
    rede = getattr(mv, "_rede", None)        # modo rede local (teste): {"senha": ..., "hosts": {...}}
    class H(BaseHTTPRequestHandler):
        server_version = "PhysisMV/teste"

        def log_message(self, *a):  # silencioso; o registro dos bots fica no banco
            pass

        def _host_ok(self) -> bool:
            h = (self.headers.get("Host") or "").split(":")[0]
            if h in ("127.0.0.1", "localhost"):
                return True
            return bool(rede) and h in rede["hosts"]

        def _autorizado(self) -> bool:
            """Modo rede local: quem não está neste computador entra com usuário 'teste' e a senha de teste (HTTP Basic)."""
            if not rede or self.client_address[0] in ("127.0.0.1", "::1"):
                return True
            a = self.headers.get("Authorization") or ""
            if a.startswith("Basic "):
                try:
                    u, _, s = base64.b64decode(a[6:]).decode("utf-8").partition(":")
                except (ValueError, UnicodeDecodeError):
                    return False
                return u == "teste" and hmac.compare_digest(s, rede["senha"])
            return False

        def _pedir_senha(self) -> None:
            b = "Physis M&A (teste): entre com o usuário teste e a senha de teste.".encode()
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Physis M&A teste", charset="UTF-8"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def _seguranca(self) -> None:
            # R-04 (auditoria 39): o painel não abre dentro de páginas de terceiros nem vaza o endereço
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")

        def _de_outro_site(self) -> bool:
            """GET que custa (exportar, baixar): o navegador informa Sec-Fetch-Site; só aceita o próprio painel ou digitação."""
            s = self.headers.get("Sec-Fetch-Site")
            return s is not None and s not in ("same-origin", "none")

        def _json(self, cod: int, obj) -> None:
            b = json.dumps(obj, ensure_ascii=False, default=str).encode()
            self.send_response(cod)
            self._seguranca()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def _bytes(self, b: bytes, tipo: str, nome: str | None = None) -> None:
            self.send_response(200)
            self._seguranca()
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(b)))
            if nome:
                self.send_header("Content-Disposition", f'attachment; filename="{nome}"')
            else:
                self.send_header("Cache-Control", "no-cache")      # tela atualizada aparece sem Ctrl+F5 (23/11/2026)
                self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                 "script-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):  # noqa: N802
            if not self._host_ok():
                return self._json(403, {"erro": "host"})
            if not self._autorizado():
                return self._pedir_senha()
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            p, fr = u.path, q.get("frente") or None
            if p in ("/api/mv/exportar", "/api/mv/arquivo/baixar") and self._de_outro_site():
                return self._json(403, {"erro": "pedido de outro site recusado"})
            try:
                if p == "/api/mv/exportar" and q.get("formato") == "pdf":
                    # R-04: o ODT é montado com a trava; a conversão em PDF (até 2 min) roda fora dela, sem travar a tela
                    with _TRAVA:
                        odt, _, nome = exportar(mv, q.get("vista", "tarefas"), "odt")
                    r = documentos.converter_pdfa(odt)
                    if r.get("ok") and r.get("pdf"):
                        return self._bytes(r["pdf"], "application/pdf", nome[:-4] + ".pdf")
                    raise ErroMV("PDF indisponível: instale o LibreOffice (soffice) ou use ODT/ODS")
                with _TRAVA:
                    if p in ("/", "/mv", "/mv/"):
                        return self._bytes((WEB / "mv.html").read_bytes(), "text/html; charset=utf-8")
                    if p == "/logo.png" and (WEB / "logo-physis.png").is_file():   # logo atualizado (árvore, 19/11/2026)
                        return self._bytes((WEB / "logo-physis.png").read_bytes(), "image/png")
                    m_logo = re.match(r"^/logos/([a-z-]+_(?:clara|escura)\.(svg|png))$", p)
                    if m_logo and (WEB / "logos" / m_logo.group(1)).is_file():   # logos vazadas aprovadas (20/11/2026)
                        return self._bytes((WEB / "logos" / m_logo.group(1)).read_bytes(),
                                           "image/svg+xml" if m_logo.group(2) == "svg" else "image/png")
                    if p.startswith("/vendor/") and p[8:] in VENDOR_OK and (VENDOR / p[8:]).is_file():
                        return self._bytes((VENDOR / p[8:]).read_bytes(), "text/javascript; charset=utf-8")
                    if p == "/icone.png" and (WEB / "app" / "icone-192.png").is_file():   # logo Physis no cabeçalho
                        return self._bytes((WEB / "app" / "icone-192.png").read_bytes(), "image/png")
                    rotas = {"/api/mv/saude": lambda: mv.saude(), "/api/mv/gantt": lambda: mv.gantt(fr),
                             "/api/mv/kanban": lambda: mv.kanban(fr), "/api/mv/matriz": lambda: mv.matriz(),
                             "/api/mv/roadmap": lambda: mv.roadmap(), "/api/mv/alertas": lambda: mv.alertas(),
                             "/api/mv/documentos": lambda: mv.documentos(), "/api/mv/cpm": lambda: mv.cpm(fr),
                             "/api/mv/meta": lambda: {"frentes": [{"id": a, "nome": b, "descricao": c} for a, b, c in FRENTES],
                                                      "estados": [{"id": e, "nome": NOMES_ESTADO[e]} for e in ESTADOS],
                                                      "etapas": [{"id": e, "nome": mv_editais.NOMES_ETAPA[e]} for e in mv_editais.ETAPAS]},
                             "/api/mv/editais": lambda: ed.listar(),
                             "/api/mv/ia": lambda: _ia().perguntar(q.get("q", "")),            # IA Physis (só documentos da Physis)
                             "/api/mv/integracoes": lambda: mv_integracoes.estado(mv),         # mapa da aba Monitoramento
                             "/api/mv/arquivos": lambda: arq.listar(q.get("destino") or None, q.get("ref") or None),
                             "/api/mv/arquivo/previa": lambda: arq.previa(q.get("id", "")),
                             "/api/mv/fila": lambda: cmd.fila(q.get("estado") or None),
                             "/api/mv/programados": lambda: cmd.programados(),
                             "/api/mv/aprovacoes": lambda: cmd.aprovacoes(antigos=q.get("antigos") == "1"),
                             "/api/mv/marketing": lambda: __import__("physis_hub.mv_bots_extra", fromlist=["x"]).marketing_conteudos(),
                             "/api/mv/desenvolvimento": lambda: __import__("physis_hub.mv_desenvolvimento", fromlist=["dados"]).dados(mv),
                             "/api/mv/perguntas": lambda: mv_comandos.perguntas(mv, None if q.get("abertas") is None else q.get("abertas") == "1",
                                                                                 q.get("sistema") or None),
                             "/api/mv/comandos/ajuda": lambda: mv_comandos.AJUDA,
                             "/api/mv/contas": lambda: cli.contas(), "/api/mv/cnpjs": lambda: cli.cnpjs(),
                             "/api/mv/conta": lambda: cli.conta(q.get("id", "")),
                             "/api/mv/fin": lambda: cli.financeiro(q.get("nivel", "conta"), q.get("filtro") or None),
                             "/api/mv/lancs": lambda: cli.lancamentos(q.get("conta") or None),
                             "/api/mv/anteriores/sugestoes": lambda: cli.sugerir_anteriores(),
                             "/api/mv/paginas": lambda: __import__("physis_hub.mv_paginas", fromlist=["x"]).listar(mv)}
                    if p in rotas:
                        return self._json(200, rotas[p]())
                    if p == "/api/mv/arquivo/baixar":
                        b, nome = arq.conteudo(q.get("id", ""))
                        return self._bytes(b, "application/octet-stream", mv_arquivos.nome_seguro(nome))
                    if p == "/api/mv/arquivo/modelo-financas.csv":
                        return self._bytes(mv_arquivos.MODELO_FINANCAS.encode("utf-8-sig"), "text/csv; charset=utf-8", "modelo-financas.csv")
                    if p == "/api/mv/exportar":
                        b, tipo, nome = exportar(mv, q.get("vista", "tarefas"), q.get("formato", "ods"))
                        return self._bytes(b, tipo, nome)
            except ErroMV as e:
                return self._json(400, {"erro": str(e)})
            except Exception as e:  # noqa: BLE001 — R-03: erro interno vira JSON 500, sem derrubar a conexão
                return self._json(500, {"erro": f"erro interno: {type(e).__name__}"})
            return self._json(404, {"erro": "não encontrado"})

        def do_POST(self):  # noqa: N802
            if not self._host_ok() or self.headers.get("X-Physis-MV") != "1":
                return self._json(403, {"erro": "pedido recusado"})
            if not self._autorizado():
                return self._pedir_senha()
            p = urlparse(self.path).path
            n = int(self.headers.get("Content-Length") or 0)
            if n > (CORPO_UPLOAD if p == "/api/mv/arquivo/enviar" else CORPO_MAX):
                return self._json(413, {"erro": "corpo grande demais"})
            try:
                corpo = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._json(400, {"erro": "JSON inválido"})
            if not isinstance(corpo, dict):
                return self._json(400, {"erro": "corpo deve ser um objeto JSON"})
            try:
                with _TRAVA:
                    if p == "/api/mv/estado":
                        return self._json(200, mv.mudar_estado(str(corpo.get("id")), str(corpo.get("estado")), str(corpo.get("bloqueio") or "")))
                    if p == "/api/mv/tarefa":
                        if not isinstance(corpo, dict):
                            raise ErroMV("corpo deve ser um objeto JSON")
                        return self._json(200, mv.salvar_tarefa(corpo, conferir_deps=True))
                    if p == "/api/mv/edital":
                        return self._json(200, ed.atualizar(str(corpo.get("id")), corpo))
                    if p == "/api/mv/lanc":
                        return self._json(200, {"id": cli.lancar(corpo)})
                    if p == "/api/mv/conta":
                        return self._json(200, cli.salvar(corpo))
                    if p == "/api/mv/anterior":
                        return self._json(200, cli.criar_anterior(corpo))
                    if p == "/api/mv/conta/confirmar":
                        return self._json(200, cli.confirmar(str(corpo.get("id")), str(corpo.get("campo")), bool(corpo.get("aceitar", True))))
                    if p == "/api/mv/conta/analisar":
                        return self._json(200, cli.analisar(str(corpo.get("id"))))
                    if p == "/api/mv/nota":
                        return self._json(200, cli.pedir_nota(int(corpo.get("id"))))
                    if p == "/api/mv/alerta/resolver":
                        return self._json(200, mv.resolver_alerta(str(corpo.get("id"))))
                    if p == "/api/mv/arquivo/enviar":
                        return self._json(200, arq.enviar(str(corpo.get("destino")), str(corpo.get("nome") or ""),
                                                          str(corpo.get("conteudo") or ""), str(corpo.get("ref") or "")))
                    if p == "/api/mv/arquivo/aplicar":
                        return self._json(200, arq.aplicar(str(corpo.get("id"))))
                    if p == "/api/mv/arquivo/descartar":
                        return self._json(200, arq.descartar(str(corpo.get("id"))))
                    if p == "/api/mv/comando":
                        return self._json(200, cmd.executar(str(corpo.get("texto") or ""), "caixa"))
                    if p == "/api/mv/pedido":
                        return self._json(200, cmd.decidir_pedido(int(corpo.get("id")), str(corpo.get("estado")),
                                                                  corpo.get("resultado")))
                    if p == "/api/mv/programado":
                        if corpo.get("id"):
                            return self._json(200, cmd.alternar(int(corpo["id"]), bool(corpo.get("ativo"))))
                        return self._json(200, cmd.programar(str(corpo.get("comando") or ""), str(corpo.get("frequencia") or ""),
                                                             str(corpo.get("nome") or "")))
                    if p == "/api/mv/pergunta":
                        return self._json(200, mv_comandos.perguntar(mv, str(corpo.get("pergunta") or ""), corpo.get("opcoes") or [],
                                                                     str(corpo.get("origem") or "tela"), corpo.get("aplica_em") or [],
                                                                     str(corpo.get("prazo") or "")))
                    if p == "/api/mv/pergunta/responder":
                        return self._json(200, mv_comandos.responder(mv, str(corpo.get("id")), str(corpo.get("resposta") or ""),
                                                                     str(corpo.get("nota") or "")))
                    if p == "/api/mv/marketing/decidir":
                        from . import mv_bots_extra
                        try:
                            return self._json(200, mv_bots_extra.marketing_decidir(str(corpo.get("id")), str(corpo.get("acao")), str(corpo.get("nota") or "")))
                        except ValueError as e:
                            return self._json(400, {"erro": str(e)})
                    if p == "/api/mv/tarefa/encaminhar":
                        t = mv.tarefa(str(corpo.get("id")))
                        if not t:
                            raise ErroMV("tarefa não encontrada")
                        nome = str(corpo.get("responsavel") or "").strip()[:120]
                        if not nome:
                            raise ErroMV("diga para quem encaminhar")
                        mv.db.execute("UPDATE mv_tarefa SET responsavel=? WHERE id=?", (nome, t["id"]))
                        mv.db.commit()
                        return self._json(200, mv.tarefa(t["id"]))
                    if p == "/api/mv/aprovacao":
                        return self._json(200, cmd.decidir(str(corpo.get("id")), str(corpo.get("estado")), str(corpo.get("nota") or "")))
                if p == "/api/mv/bots/rodar":
                    # R-04: bots (até ~1,5 min) rodam numa conexão própria, fora da trava; com banco em memória (testes), na trava
                    quais = [x for x in ((corpo.get("quais") if isinstance(corpo, dict) else None) or []) if x in mv_bots.BOTS] or None
                    if mv.caminho == ":memory:":
                        with _TRAVA:
                            return self._json(200, mv_bots.rodar(mv, quais))
                    outro = MV(mv.caminho)
                    try:
                        return self._json(200, mv_bots.rodar(outro, quais))
                    finally:
                        outro.db.close()
            except (ErroMV, KeyError, TypeError, ValueError) as e:
                return self._json(400, {"erro": str(e)})
            except Exception as e:  # noqa: BLE001
                return self._json(500, {"erro": f"erro interno: {type(e).__name__}"})
            return self._json(404, {"erro": "não encontrado"})

    return H


def ips_locais() -> set[str]:
    """IPs privados desta máquina (rede local). Só endereços privados entram; nunca um IP público."""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return {i for i in ips if ipaddress.ip_address(i).is_private and not ipaddress.ip_address(i).is_loopback}


def senha_teste(pasta: Path) -> str:
    """Senha de teste da rede local, criada uma vez e guardada fora do OneDrive (dados/senha-teste-rede.txt)."""
    arq = pasta / "senha-teste-rede.txt"
    if not arq.is_file():
        arq.write_text(secrets.token_urlsafe(9), encoding="utf-8")
    return arq.read_text(encoding="utf-8").strip()


def servir(mv: MV | None = None, porta: int = PORTA, rede_local: bool = False) -> ThreadingHTTPServer:
    """Padrão: só 127.0.0.1. rede_local=True (teste, 20/11/2026): ouve nos IPs privados desta máquina, com senha de teste
    para quem vem de outro aparelho. Não abre para a internet: nada de redirecionamento no roteador; o Windows pode perguntar
    se libera o Python no firewall para redes PRIVADAS (a dona decide; nunca liberar em rede pública)."""
    mv = mv or MV()
    if rede_local:
        ips = ips_locais()
        if not ips:
            raise ErroMV("nenhum IP de rede local encontrado (Wi-Fi/cabo desligado?)")
        mv._rede = {"senha": senha_teste(Path(mv.caminho).parent), "hosts": ips | {socket.gethostname().lower()}}
        srv = ThreadingHTTPServer(("0.0.0.0", porta), fabricar(mv))
        srv.ips = sorted(ips)
        return srv
    srv = ThreadingHTTPServer(("127.0.0.1", porta), fabricar(mv))
    return srv
