"""Servidor local do Physis M&V (VERSÃO DE TESTE): só em 127.0.0.1, porta 8710 (PHYSIS_MV_PORTA).
Tela em web/mv.html; API JSON em /api/mv/*; exportação ODS/ODT (e PDF/A quando houver LibreOffice).

Segurança desta fase (computador principal, D58): ouve só em 127.0.0.1, confere o cabeçalho Host e exige
X-Physis-MV: 1 em todo POST (um site de fora não consegue mandar esse cabeçalho). Na migração para o servidor físico
(dezembro, Eric) entra a conta da Gestão com papéis, como no hub.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import documentos
from . import mv_bots
from . import mv_editais
from .mv import ESTADOS, FRENTES, MV, NOMES_ESTADO, ErroMV

WEB = Path(__file__).resolve().parents[1] / "web"
PORTA = int(os.environ.get("PHYSIS_MV_PORTA") or 8710)
CORPO_MAX = 256 * 1024
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
        cab = ["Frente", "Nota", "Total", "Feitas", "Atrasadas", "Bloqueadas", "Datas a conferir", "Progresso %"]
        linhas = [[f["nome"], f["nota"], f["total"], f["feitas"], f["atrasadas"], f["bloqueadas"], f["datas_estimadas"],
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
    class H(BaseHTTPRequestHandler):
        server_version = "PhysisMV/teste"

        def log_message(self, *a):  # silencioso; o registro dos bots fica no banco
            pass

        def _host_ok(self) -> bool:
            h = (self.headers.get("Host") or "").split(":")[0]
            return h in ("127.0.0.1", "localhost")

        def _json(self, cod: int, obj) -> None:
            b = json.dumps(obj, ensure_ascii=False, default=str).encode()
            self.send_response(cod)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def _bytes(self, b: bytes, tipo: str, nome: str | None = None) -> None:
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(b)))
            self.send_header("X-Content-Type-Options", "nosniff")
            if nome:
                self.send_header("Content-Disposition", f'attachment; filename="{nome}"')
            else:
                self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                 "script-src 'self' 'unsafe-inline'; img-src 'self' data:")
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):  # noqa: N802
            if not self._host_ok():
                return self._json(403, {"erro": "host"})
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            p, fr = u.path, q.get("frente") or None
            try:
                with _TRAVA:
                    if p in ("/", "/mv", "/mv/"):
                        return self._bytes((WEB / "mv.html").read_bytes(), "text/html; charset=utf-8")
                    if p == "/logo.png" and (WEB / "logo-physis.png").is_file():   # logo atualizado (árvore, 19/11/2026)
                        return self._bytes((WEB / "logo-physis.png").read_bytes(), "image/png")
                    if p == "/icone.png" and (WEB / "app" / "icone-192.png").is_file():   # logo Physis no cabeçalho
                        return self._bytes((WEB / "app" / "icone-192.png").read_bytes(), "image/png")
                    rotas = {"/api/mv/saude": lambda: mv.saude(), "/api/mv/gantt": lambda: mv.gantt(fr),
                             "/api/mv/kanban": lambda: mv.kanban(fr), "/api/mv/matriz": lambda: mv.matriz(),
                             "/api/mv/roadmap": lambda: mv.roadmap(), "/api/mv/alertas": lambda: mv.alertas(),
                             "/api/mv/documentos": lambda: mv.documentos(), "/api/mv/cpm": lambda: mv.cpm(fr),
                             "/api/mv/meta": lambda: {"frentes": [{"id": a, "nome": b, "descricao": c} for a, b, c in FRENTES],
                                                      "estados": [{"id": e, "nome": NOMES_ESTADO[e]} for e in ESTADOS],
                                                      "etapas": [{"id": e, "nome": mv_editais.NOMES_ETAPA[e]} for e in mv_editais.ETAPAS]},
                             "/api/mv/editais": lambda: ed.listar()}
                    if p in rotas:
                        return self._json(200, rotas[p]())
                    if p == "/api/mv/exportar":
                        b, tipo, nome = exportar(mv, q.get("vista", "tarefas"), q.get("formato", "ods"))
                        return self._bytes(b, tipo, nome)
            except ErroMV as e:
                return self._json(400, {"erro": str(e)})
            return self._json(404, {"erro": "não encontrado"})

        def do_POST(self):  # noqa: N802
            if not self._host_ok() or self.headers.get("X-Physis-MV") != "1":
                return self._json(403, {"erro": "pedido recusado"})
            n = int(self.headers.get("Content-Length") or 0)
            if n > CORPO_MAX:
                return self._json(413, {"erro": "corpo grande demais"})
            try:
                corpo = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._json(400, {"erro": "JSON inválido"})
            p = urlparse(self.path).path
            try:
                with _TRAVA:
                    if p == "/api/mv/estado":
                        return self._json(200, mv.mudar_estado(str(corpo.get("id")), str(corpo.get("estado")), str(corpo.get("bloqueio") or "")))
                    if p == "/api/mv/tarefa":
                        return self._json(200, mv.salvar_tarefa(corpo))
                    if p == "/api/mv/edital":
                        return self._json(200, ed.atualizar(str(corpo.get("id")), corpo))
                    if p == "/api/mv/lanc":
                        return self._json(200, {"id": mv.lancar(corpo)})
                    if p == "/api/mv/alerta/resolver":
                        mv.db.execute("UPDATE mv_alerta SET resolvido=strftime('%s','now') WHERE id=?", (str(corpo.get("id")),))
                        mv.db.commit()
                        return self._json(200, {"ok": True})
                    if p == "/api/mv/bots/rodar":
                        quais = [x for x in (corpo.get("quais") or []) if x in mv_bots.BOTS] or None
                        return self._json(200, mv_bots.rodar(mv, quais))
            except (ErroMV, KeyError, TypeError, ValueError) as e:
                return self._json(400, {"erro": str(e)})
            return self._json(404, {"erro": "não encontrado"})

    return H


def servir(mv: MV | None = None, porta: int = PORTA) -> ThreadingHTTPServer:
    mv = mv or MV()
    srv = ThreadingHTTPServer(("127.0.0.1", porta), fabricar(mv))
    return srv
