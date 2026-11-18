"""Intercâmbio de dados entre plataformas Physis (docs/INTERCAMBIO.md).

Duas instalações (a da Physis Engineering e a do Instituto Physis, ou qualquer instalação compatível) trocam
conjuntos de dados combinados SEM dividir banco: cada lado guarda o que é seu e só recebe o que a direção dele aceitar.

Contrato aberto "physis-intercambio/1":
  pacote   = {"esquema", "origem", "destino", "dataset", "gerado_em", "registros": [registro, ...]}
  registro = {"dataset", "id", "origem", "dados": {...}, "sha256"}
  sha256   = SHA-256 do JSON canônico (chaves em ordem, sem espaços, UTF-8) de {dataset, id, origem, dados}.

Conjuntos (lista de permissão, campo a campo; o que não está na lista não sai):
  cursos_catalogo, projetos_resumo, pecas_biblioteca (dados da peça + SHA-256 do arquivo, para a biblioteca 3D do
  Instituto) e lotes_integridade. Campos pessoais (ex.: "cliente", "autor_publico") só saem e só entram com
  "consentimento": true no registro (LGPD); sem ele, o campo é retirado no envio e o registro é recusado na chegada.

Segurança:
  * Parceiros: só a direção cadastra (nome, endereço, conjuntos permitidos em cada sentido). A chave combinada fica só
    no arquivo de chaves do servidor (PHYSIS_INTERCAMBIO_CHAVES; padrão: intercambio-chaves.json ao lado do banco),
    nunca no código, nunca no banco, nunca no registro.
  * Cada pedido é assinado: HMAC-SHA256(chave, esquema \\n método \\n caminho \\n momento \\n nonce \\n SHA-256 do corpo),
    nos cabeçalhos X-Physis-Origem, X-Physis-Momento, X-Physis-Nonce e X-Physis-Assinatura. Momento fora de ±5 min ou
    nonce repetido = recusado (sem repetição). A resposta volta assinada com o nonce do pedido.
  * Limite de pedidos por parceiro e de falhas por endereço; corpo e quantidade de registros limitados.
  * Só por HTTPS ou pela rede local/VPN (endereço privado). Tudo fica no registro encadeado do hub (tipo "intercambio"),
    sem o conteúdo dos registros.
  * Importar não publica: o que chega fica "pendente" até a direção aprovar; só então aparece (recebidos()).
Puxar (GET do parceiro) e empurrar (POST para o parceiro) funcionam nos dois sentidos.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import seguranca as seg

ESQUEMA = "physis-intercambio/1"
JANELA_S = 300                      # ± 5 min entre os relógios
MAX_REGISTROS = 2000                # por pacote
CORPO_MAX = 4 * 1024 * 1024         # pacote de até 4 MB
DADOS_MAX = 16 * 1024               # um registro (JSON) de até 16 kB
TEXTO_MAX = 4000
FALHAS_MAX, FALHAS_JANELA = 20, 600  # falhas de assinatura por endereço
PREFIXO = "/api/intercambio/"
ID_RX = re.compile(r"[a-z0-9][a-z0-9._-]{1,63}")
REG_ID_RX = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
NONCE_RX = re.compile(r"[A-Za-z0-9_-]{16,128}")
SHA_RX = re.compile(r"[0-9a-f]{64}")
# dado pessoal escondido num campo aberto: e-mail, CPF ou CNPJ
# redes de "rede local ou VPN" (o Python acha que 203.0.113.0/24, de documentação, é privada: aqui a lista é explícita)
REDES_LOCAIS_VPN = tuple(ipaddress.ip_network(r) for r in ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
                                                            "100.64.0.0/10", "::1/128", "fc00::/7"))
PESSOAL_RX = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b|\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")

DATASETS = {
    "cursos_catalogo": {
        "nome": {"pt": "Catálogo público de cursos", "en": "Public course catalogue"},
        "campos": ("nome", "descricao", "link", "gratuito", "carga_horas", "idioma", "area", "nivel"),
        "pessoais": ("instrutor",)},
    "projetos_resumo": {
        "nome": {"pt": "Resumo de projetos", "en": "Project summaries"},
        "campos": ("titulo", "resumo", "area", "municipio", "uf", "situacao", "ano", "indicadores"),
        "pessoais": ("cliente", "responsavel")},
    "pecas_biblioteca": {
        "nome": {"pt": "Biblioteca aberta de peças (dados e resumo do arquivo)", "en": "Open part library (metadata and file hash)"},
        "campos": ("nome", "descricao", "licenca", "material", "arquivo_nome", "arquivo_sha256", "arquivo_bytes", "url", "versao"),
        "pessoais": ("autor_publico",)},
    "lotes_integridade": {
        "nome": {"pt": "Lotes de integridade (resumo de cada lote)", "en": "Integrity lots (hash of each lot)"},
        "campos": ("lote", "periodo_ini", "periodo_fim", "quantidade", "fechado_em", "resumo_lote"),
        "pessoais": ("responsavel",)},
}

ESQUEMA_SQL = """
CREATE TABLE IF NOT EXISTS intercambio_parceiro (
  id TEXT PRIMARY KEY, nome TEXT NOT NULL, url TEXT NOT NULL, ativo INTEGER NOT NULL DEFAULT 1,
  enviar TEXT NOT NULL DEFAULT '[]', receber TEXT NOT NULL DEFAULT '[]', criado REAL NOT NULL, atualizado REAL NOT NULL, por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS intercambio_publicado (
  dataset TEXT NOT NULL, id TEXT NOT NULL, dados TEXT NOT NULL, consentimento INTEGER NOT NULL DEFAULT 0,
  atualizado REAL NOT NULL, por TEXT NOT NULL, PRIMARY KEY (dataset, id));
CREATE TABLE IF NOT EXISTS intercambio_recebido (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, parceiro TEXT NOT NULL, dataset TEXT NOT NULL, id TEXT NOT NULL,
  origem TEXT NOT NULL, dados TEXT NOT NULL, sha256 TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'pendente',
  recebido REAL NOT NULL, via TEXT NOT NULL, revisado REAL, revisor TEXT, motivo TEXT);
CREATE INDEX IF NOT EXISTS intercambio_recebido_ds ON intercambio_recebido (dataset, estado);
CREATE TABLE IF NOT EXISTS intercambio_nonce (
  parceiro TEXT NOT NULL, nonce TEXT NOT NULL, quando REAL NOT NULL, PRIMARY KEY (parceiro, nonce));
"""


# ═══════════════ Contrato: registro, pacote e assinatura (iguais nos dois lados) ═══════════════
def canonico(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def resumo_registro(dataset: str, rid: str, origem: str, dados: dict) -> str:
    return sha256(canonico({"dataset": dataset, "id": rid, "origem": origem, "dados": dados}))


def registro(dataset: str, rid: str, origem: str, dados: dict) -> dict:
    return {"dataset": dataset, "id": rid, "origem": origem, "dados": dados, "sha256": resumo_registro(dataset, rid, origem, dados)}


def limpar(dataset: str, dados: dict, consentimento: bool) -> tuple[dict, list[str]]:
    """Só os campos da lista do conjunto. Campo pessoal só com consentimento. Devolve (dados, campos pessoais retirados)."""
    d = DATASETS[dataset]
    out = {k: dados[k] for k in d["campos"] if k in dados and dados[k] is not None}
    tirados = [k for k in d["pessoais"] if dados.get(k) not in (None, "")]
    if consentimento and tirados:
        out.update({k: dados[k] for k in tirados})
        out["consentimento"] = True
        tirados = []
    return out, tirados


def assinar(chave: str, metodo: str, caminho: str, momento: str, nonce: str, corpo: bytes) -> str:
    msg = "\n".join((ESQUEMA, metodo.upper(), caminho, str(momento), nonce, sha256(corpo or b"")))
    return hmac.new(chave.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def _valor_ok(v, prof: int = 0) -> bool:
    if v is None or isinstance(v, bool) or isinstance(v, (int, float)):
        return not (isinstance(v, float) and v != v)
    if isinstance(v, str):
        return len(v) <= TEXTO_MAX
    if prof < 2 and isinstance(v, list):
        return len(v) <= 100 and all(_valor_ok(x, prof + 1) for x in v)
    if prof < 2 and isinstance(v, dict):
        return len(v) <= 100 and all(isinstance(k, str) and len(k) <= 80 and _valor_ok(x, prof + 1) for k, x in v.items())
    return False


def conferir_dados(dataset: str, dados: dict) -> str | None:
    """Erro (texto) ou None. Vale para publicar aqui e para o que chega do parceiro."""
    if not isinstance(dados, dict) or not dados:
        return "dados vazios"
    d = DATASETS[dataset]
    fora = sorted(set(dados) - set(d["campos"]) - set(d["pessoais"]) - {"consentimento"})
    if fora:
        return "campos fora da lista do conjunto: " + ", ".join(fora[:5])
    if any(k in dados for k in d["pessoais"]) and dados.get("consentimento") is not True:
        return "dado pessoal sem consentimento (LGPD)"
    if not all(_valor_ok(v) for v in dados.values()) or len(canonico(dados)) > DADOS_MAX:
        return "valor grande demais ou de tipo não aceito"
    for k, v in dados.items():
        if k in d["pessoais"] or k == "consentimento" or k.endswith(("sha256", "resumo_lote")):
            continue
        if isinstance(v, str) and PESSOAL_RX.search(v):
            return f"o campo {k} parece ter dado pessoal (e-mail, CPF ou CNPJ)"
    for k in ("link", "url"):
        if dados.get(k) and not str(dados[k]).startswith("https://"):
            return f"{k}: só endereço https://"
    if "arquivo_sha256" in dados and not SHA_RX.fullmatch(str(dados["arquivo_sha256"])):
        return "arquivo_sha256: 64 caracteres hexadecimais"
    return None


def endereco_permitido(url: str) -> str | None:
    """HTTPS sempre; HTTP só para rede local ou VPN (loopback, privada, 100.64.0.0/10, fc00::/7). Erro ou None."""
    try:
        u = urlparse(url)
    except ValueError:
        return "endereço inválido"
    if u.scheme not in ("https", "http") or not u.hostname or u.username or u.password or u.query or u.fragment:
        return "endereço: use https://servidor[:porta][/caminho]"
    if u.scheme == "https":
        return None
    try:
        ip = ipaddress.ip_address(u.hostname)
    except ValueError:
        return "sem HTTPS, só um endereço IP da rede local ou da VPN"
    if any(ip.version == r.version and ip in r for r in REDES_LOCAIS_VPN):
        return None
    return "sem HTTPS, só um endereço IP da rede local ou da VPN"


# ═══════════════ O módulo ═══════════════
class Intercambio:
    def __init__(self, hub, origem: str, arquivo_chaves: str | Path, relogio=None, cursos=None, timeout: float = 15.0):
        self.hub = hub
        self.origem = origem if ID_RX.fullmatch(str(origem or "")) else "physis"
        self.arquivo_chaves = Path(arquivo_chaves)
        self.relogio = relogio or hub.relogio
        self._cursos = cursos or (lambda: [])
        self.timeout = timeout
        lim = seg.ler_limite(os.environ.get("PHYSIS_INTERCAMBIO_LIMITE"), "120/600")
        self._lim = seg.Limitador(lim[0], lim[1]) if lim else None
        self._falhas: dict[str, list[float]] = {}
        self._trava_chaves = threading.Lock()
        with hub._trava:
            hub._db.executescript(ESQUEMA_SQL)
            hub._db.commit()

    @property
    def _db(self):
        return self.hub._db

    # ── chaves: só no arquivo do servidor ──
    def _chaves(self) -> dict:
        try:
            d = json.loads(self.arquivo_chaves.read_text(encoding="utf-8"))
            return {k: v for k, v in d.items() if isinstance(v, str)} if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def _gravar_chaves(self, d: dict) -> None:
        self.arquivo_chaves.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.arquivo_chaves.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, self.arquivo_chaves)

    def definir_chave(self, pid: str, chave: str | None, quem: str) -> dict:
        if not self._parceiro(pid):
            return {"ok": False, "codigo": 404, "erro": "parceiro desconhecido"}
        gerada = not chave
        chave = chave or ("phx_" + secrets.token_urlsafe(32))
        if len(chave) < 32 or len(chave) > 200 or not re.fullmatch(r"[\x21-\x7e]+", chave):
            return {"ok": False, "erro": "chave: de 32 a 200 caracteres visíveis, sem espaço"}
        with self._trava_chaves:
            d = self._chaves()
            d[pid] = chave
            self._gravar_chaves(d)
        self._auditar(pid, "chave definida", por=quem, gerada=gerada)
        r = {"ok": True, "gerada": gerada}
        if gerada:
            r["chave"] = chave          # aparece só agora: a direção passa ao parceiro por um canal seguro
        return r

    # ── parceiros ──
    def _parceiro(self, pid: str) -> dict | None:
        l = self._db.execute("SELECT id,nome,url,ativo,enviar,receber,criado,atualizado,por FROM intercambio_parceiro WHERE id=?",
                             (str(pid or ""),)).fetchone()
        if not l:
            return None
        return {"id": l[0], "nome": l[1], "url": l[2], "ativo": bool(l[3]), "enviar": json.loads(l[4]), "receber": json.loads(l[5]),
                "criado": l[6], "atualizado": l[7], "por": l[8]}

    def parceiros(self) -> list[dict]:
        ch = self._chaves()
        ids = [l[0] for l in self._db.execute("SELECT id FROM intercambio_parceiro ORDER BY nome")]
        return [dict(self._parceiro(i), tem_chave=i in ch) for i in ids]

    def salvar_parceiro(self, d: dict, quem: str) -> dict:
        pid, nome, url = str(d.get("id") or "").strip(), str(d.get("nome") or "").strip()[:120], str(d.get("url") or "").strip().rstrip("/")
        if not ID_RX.fullmatch(pid):
            return {"ok": False, "erro": "id: o identificador da outra instalação (2 a 64 letras minúsculas, números, ponto, hífen)"}
        if pid == self.origem:
            return {"ok": False, "erro": "id: é o identificador desta instalação"}
        if not nome:
            return {"ok": False, "erro": "nome obrigatório"}
        erro = endereco_permitido(url)
        if erro:
            return {"ok": False, "erro": erro}
        listas = {}
        for k in ("enviar", "receber"):
            v = d.get(k) or []
            if not isinstance(v, list) or any(x not in DATASETS for x in v):
                return {"ok": False, "erro": f"{k}: conjuntos aceitos: " + ", ".join(DATASETS)}
            listas[k] = sorted(set(v))
        agora = self.relogio()
        with self.hub._trava:
            antes = self._parceiro(pid)
            self._db.execute("INSERT INTO intercambio_parceiro(id,nome,url,ativo,enviar,receber,criado,atualizado,por) VALUES(?,?,?,?,?,?,?,?,?) "
                             "ON CONFLICT(id) DO UPDATE SET nome=excluded.nome, url=excluded.url, ativo=excluded.ativo, "
                             "enviar=excluded.enviar, receber=excluded.receber, atualizado=excluded.atualizado, por=excluded.por",
                             (pid, nome, url, 0 if d.get("ativo") is False else 1, json.dumps(listas["enviar"]), json.dumps(listas["receber"]),
                              agora, agora, quem))
            self._db.commit()
        self._auditar(pid, "parceiro alterado" if antes else "parceiro criado", por=quem, url=url, enviar=listas["enviar"],
                      receber=listas["receber"], ativo=d.get("ativo") is not False)
        return {"ok": True, "parceiro": self._parceiro(pid)}

    def remover_parceiro(self, pid: str, quem: str) -> dict:
        if not self._parceiro(pid):
            return {"ok": False, "codigo": 404, "erro": "parceiro desconhecido"}
        with self.hub._trava:
            self._db.execute("DELETE FROM intercambio_parceiro WHERE id=?", (pid,))
            self._db.commit()
        with self._trava_chaves:
            d = self._chaves()
            if d.pop(pid, None) is not None:
                self._gravar_chaves(d)
        self._auditar(pid, "parceiro removido", por=quem)
        return {"ok": True}

    # ── o que esta instalação oferece ──
    def publicar(self, dataset: str, registros: list, quem: str) -> dict:
        if dataset not in DATASETS:
            return {"ok": False, "erro": "conjunto desconhecido"}
        if dataset in ("cursos_catalogo", "lotes_integridade"):
            return {"ok": False, "erro": "este conjunto vem do próprio sistema (cursos da instalação, lotes de integridade)"}
        if not isinstance(registros, list) or not registros or len(registros) > MAX_REGISTROS:
            return {"ok": False, "erro": f"registros: de 1 a {MAX_REGISTROS}"}
        prontos, erros = [], []
        for n, r in enumerate(registros):
            rid = str((r or {}).get("id") or "") if isinstance(r, dict) else ""
            dados = (r or {}).get("dados") if isinstance(r, dict) else None
            consent = isinstance(r, dict) and r.get("consentimento") is True
            if not REG_ID_RX.fullmatch(rid):
                erros.append({"n": n, "erro": "id inválido"})
                continue
            if not isinstance(dados, dict):
                erros.append({"n": n, "id": rid, "erro": "dados vazios"})
                continue
            dados = {k: v for k, v in dados.items() if k != "consentimento"}
            # a forma é conferida como se houvesse consentimento; sem ele, os campos pessoais ficam aqui e não saem (limpar)
            pess = any(k in dados for k in DATASETS[dataset]["pessoais"])
            e = conferir_dados(dataset, dict(dados, consentimento=True) if pess else dados)
            if e:
                erros.append({"n": n, "id": rid, "erro": e})
                continue
            prontos.append((rid, dados, consent))
        if erros:
            return {"ok": False, "erro": "registros recusados; nada foi publicado", "recusados": erros[:50]}
        agora = self.relogio()
        with self.hub._trava:
            for rid, dados, consent in prontos:
                self._db.execute("INSERT OR REPLACE INTO intercambio_publicado(dataset,id,dados,consentimento,atualizado,por) VALUES(?,?,?,?,?,?)",
                                 (dataset, rid, json.dumps(dados, ensure_ascii=False), int(consent), agora, quem))
            self._db.commit()
        self._auditar("-", "publicado", por=quem, dataset=dataset, registros=len(prontos))
        return {"ok": True, "publicados": len(prontos)}

    def despublicar(self, dataset: str, rid: str, quem: str) -> dict:
        with self.hub._trava:
            n = self._db.execute("DELETE FROM intercambio_publicado WHERE dataset=? AND id=?", (dataset, str(rid))).rowcount
            self._db.commit()
        if n:
            self._auditar("-", "despublicado", por=quem, dataset=dataset, id=str(rid)[:128])
        return {"ok": bool(n), **({} if n else {"codigo": 404, "erro": "registro não publicado"})}

    def publicados(self, dataset: str | None = None) -> list[dict]:
        q, a = "SELECT dataset,id,dados,consentimento,atualizado,por FROM intercambio_publicado", ()
        if dataset:
            q, a = q + " WHERE dataset=?", (dataset,)
        return [{"dataset": l[0], "id": l[1], "dados": json.loads(l[2]), "consentimento": bool(l[3]), "atualizado": l[4], "por": l[5]}
                for l in self._db.execute(q + " ORDER BY dataset, id LIMIT 5000", a)]

    def _fonte(self, dataset: str) -> list[tuple[str, dict, bool, float]]:
        """(id, dados brutos, consentimento, atualizado) do que esta instalação tem para o conjunto."""
        if dataset == "cursos_catalogo":
            out = []
            for c in (self._cursos() or []):
                if isinstance(c, dict) and c.get("nome"):
                    rid = re.sub(r"[^A-Za-z0-9._:-]+", "-", str(c.get("id") or c["nome"]))[:120].strip("-") or "curso"
                    carga = c.get("carga_horas", c.get("carga"))
                    d = {"nome": c.get("nome"), "descricao": c.get("descricao"), "link": c.get("link"), "gratuito": c.get("gratuito"),
                         "carga_horas": carga if isinstance(carga, (int, float)) else None, "idioma": c.get("idioma"),
                         "area": c.get("area"), "nivel": c.get("nivel"), "instrutor": c.get("instrutor")}
                    out.append((rid, d, c.get("consentimento") is True, 0.0))
            return out
        if dataset == "lotes_integridade":
            try:
                linhas = self._db.execute("SELECT lote,periodo_ini,periodo_fim,quantidade,fechado_em,resumo_lote,responsavel FROM integridade_lote "
                                          "ORDER BY fechado_em, lote").fetchall()
            except Exception:    # noqa: BLE001 — sem a tabela de integridade nesta instalação
                return []
            return [(l[0], dict(zip(("lote", "periodo_ini", "periodo_fim", "quantidade", "fechado_em", "resumo_lote", "responsavel"), l)),
                     False, 0.0) for l in linhas]
        return [(p["id"], p["dados"], p["consentimento"], p["atualizado"]) for p in self.publicados(dataset)]

    def pacote(self, dataset: str, destino: str, desde: float | None = None) -> tuple[dict, int]:
        """Pacote do conjunto para um parceiro e quantos campos pessoais ficaram de fora (sem consentimento)."""
        regs, tirados = [], 0
        for rid, dados, consent, quando in self._fonte(dataset):
            if desde and quando and quando <= desde:
                continue
            if not REG_ID_RX.fullmatch(str(rid)):
                continue
            limpo, fora = limpar(dataset, dados, consent)
            tirados += len(fora)
            if conferir_dados(dataset, limpo) is None:
                regs.append(registro(dataset, str(rid), self.origem, limpo))
            if len(regs) >= MAX_REGISTROS:
                break
        return ({"esquema": ESQUEMA, "origem": self.origem, "destino": destino, "dataset": dataset,
                 "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.relogio())), "registros": regs}, tirados)

    # ── o que chega ──
    def conferir_pacote(self, pid: str, dataset: str, p) -> tuple[list[dict], list[dict], str | None]:
        """(válidos, recusados, erro do pacote)."""
        if not isinstance(p, dict) or p.get("esquema") != ESQUEMA:
            return [], [], f"esquema: esperado {ESQUEMA}"
        if p.get("origem") != pid or p.get("dataset") != dataset or p.get("destino") not in (None, self.origem):
            return [], [], "pacote de outra origem, outro conjunto ou outro destino"
        regs = p.get("registros")
        if not isinstance(regs, list) or len(regs) > MAX_REGISTROS:
            return [], [], f"registros: lista de até {MAX_REGISTROS}"
        ok, ruins = [], []
        for n, r in enumerate(regs):
            if not isinstance(r, dict) or set(r) != {"dataset", "id", "origem", "dados", "sha256"}:
                ruins.append({"n": n, "erro": "registro fora do contrato"})
                continue
            if r["dataset"] != dataset or r["origem"] != pid or not REG_ID_RX.fullmatch(str(r["id"])):
                ruins.append({"n": n, "erro": "dataset, origem ou id inválido"})
                continue
            e = conferir_dados(dataset, r["dados"])
            if e:
                ruins.append({"n": n, "id": r["id"], "erro": e})
                continue
            if not isinstance(r["sha256"], str) or not hmac.compare_digest(r["sha256"], resumo_registro(dataset, r["id"], pid, r["dados"])):
                ruins.append({"n": n, "id": r["id"], "erro": "SHA-256 não confere (registro alterado)"})
                continue
            ok.append(r)
        return ok, ruins, None

    def guardar_recebidos(self, pid: str, dataset: str, regs: list[dict], via: str) -> int:
        """Cada registro novo (ou mudado) fica PENDENTE até a direção aprovar. Repetido igual não entra de novo."""
        agora, n = self.relogio(), 0
        with self.hub._trava:
            for r in regs:
                igual = self._db.execute("SELECT 1 FROM intercambio_recebido WHERE parceiro=? AND dataset=? AND id=? AND sha256=? "
                                         "AND estado IN ('pendente','aprovado')", (pid, dataset, r["id"], r["sha256"])).fetchone()
                if igual:
                    continue
                self._db.execute("INSERT INTO intercambio_recebido(parceiro,dataset,id,origem,dados,sha256,estado,recebido,via) "
                                 "VALUES(?,?,?,?,?,?,'pendente',?,?)",
                                 (pid, dataset, r["id"], r["origem"], json.dumps(r["dados"], ensure_ascii=False), r["sha256"], agora, via))
                n += 1
            self._db.commit()
        return n

    def pendentes(self, limite: int = 500) -> list[dict]:
        return self._lista("estado='pendente'", (), limite)

    def recebidos(self, dataset: str | None = None, limite: int = 2000) -> list[dict]:
        """Só o que a direção aprovou."""
        if dataset:
            return self._lista("estado='aprovado' AND dataset=?", (dataset,), limite)
        return self._lista("estado='aprovado'", (), limite)

    def _lista(self, onde: str, args: tuple, limite: int) -> list[dict]:
        cols = ("seq", "parceiro", "dataset", "id", "origem", "dados", "sha256", "estado", "recebido", "via", "revisado", "revisor", "motivo")
        out = []
        for l in self._db.execute(f"SELECT {','.join(cols)} FROM intercambio_recebido WHERE {onde} ORDER BY seq DESC LIMIT ?", args + (int(limite),)):
            x = dict(zip(cols, l))
            x["dados"] = json.loads(x["dados"])
            out.append(x)
        return out

    def revisar(self, ids: list, decisao: str, quem: str, motivo: str = "") -> dict:
        if decisao not in ("aprovar", "recusar") or not isinstance(ids, list) or not ids or len(ids) > 2000 \
                or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
            return {"ok": False, "erro": "use {ids: [números], decisao: aprovar|recusar, motivo}"}
        agora, n = self.relogio(), 0
        with self.hub._trava:
            for i in ids:
                l = self._db.execute("SELECT parceiro,dataset,id FROM intercambio_recebido WHERE seq=? AND estado='pendente'", (i,)).fetchone()
                if not l:
                    continue
                if decisao == "aprovar":       # a versão aprovada antes do mesmo registro sai de cena
                    self._db.execute("UPDATE intercambio_recebido SET estado='substituido' WHERE parceiro=? AND dataset=? AND id=? AND estado='aprovado'", l)
                self._db.execute("UPDATE intercambio_recebido SET estado=?, revisado=?, revisor=?, motivo=? WHERE seq=?",
                                 ("aprovado" if decisao == "aprovar" else "recusado", agora, quem, str(motivo or "")[:300], i))
                n += 1
            self._db.commit()
        self._auditar("-", "importacao " + ("aprovada" if decisao == "aprovar" else "recusada"), por=quem, registros=n)
        return {"ok": True, "revisados": n}

    # ── registro (auditoria) no registro encadeado do hub ──
    def _auditar(self, parceiro: str, operacao: str, **extra) -> None:
        try:
            self.hub.registrar("intercambio", str(parceiro or "-")[:64], dict(extra, operacao=operacao))
        except Exception:    # noqa: BLE001 — a auditoria não derruba a troca
            pass

    def registro_eventos(self, limite: int = 200) -> list[dict]:
        out = []
        for quando, origem, conteudo in self._db.execute("SELECT quando, origem, conteudo FROM registro WHERE tipo='intercambio' "
                                                         "ORDER BY seq DESC LIMIT ?", (int(limite),)):
            try:
                c = json.loads(conteudo)
            except ValueError:
                c = {}
            out.append({"quando": quando, "parceiro": origem, **c})
        return out

    # ── assinatura dos pedidos que chegam ──
    def _falhou(self, ip: str) -> None:
        agora = time.monotonic()
        l = [t for t in self._falhas.get(ip, []) if agora - t < FALHAS_JANELA]
        l.append(agora)
        self._falhas[ip] = l[-FALHAS_MAX:]
        if len(self._falhas) > 10_000:
            self._falhas.clear()

    def _bloqueado(self, ip: str) -> bool:
        agora = time.monotonic()
        return len([t for t in self._falhas.get(ip, []) if agora - t < FALHAS_JANELA]) >= FALHAS_MAX

    def verificar(self, metodo: str, caminho: str, cab, corpo: bytes, ip: str) -> tuple[dict | None, int, str]:
        """(parceiro, 0, "") se o pedido vale; senão (None, código HTTP, motivo)."""
        if self._bloqueado(ip):
            return None, 429, "muitas falhas deste endereço; tente mais tarde"
        pid, momento = (cab.get("X-Physis-Origem") or "").strip(), (cab.get("X-Physis-Momento") or "").strip()
        nonce, ass = (cab.get("X-Physis-Nonce") or "").strip(), (cab.get("X-Physis-Assinatura") or "").strip().lower()
        par = self._parceiro(pid) if ID_RX.fullmatch(pid) else None
        chave = self._chaves().get(pid) if par else None
        motivo = None
        if not par or not par["ativo"] or not chave:
            motivo = "parceiro desconhecido, inativo ou sem chave"
        elif not re.fullmatch(r"\d{9,12}", momento) or abs(self.relogio() - int(momento)) > JANELA_S:
            motivo = "momento fora da janela (relógio?)"
        elif not NONCE_RX.fullmatch(nonce) or not SHA_RX.fullmatch(ass):
            motivo = "cabeçalhos de assinatura ausentes"
        elif not hmac.compare_digest(ass, assinar(chave, metodo, caminho, momento, nonce, corpo)):
            motivo = "assinatura não confere"
        if motivo:
            self._falhou(ip)
            self._auditar(pid if par else "-", "pedido recusado", motivo=motivo, caminho=caminho[:120], ip=ip)
            return None, 401, motivo
        agora = self.relogio()
        with self.hub._trava:
            self._db.execute("DELETE FROM intercambio_nonce WHERE quando < ?", (agora - 2 * JANELA_S,))
            try:
                self._db.execute("INSERT INTO intercambio_nonce(parceiro,nonce,quando) VALUES(?,?,?)", (pid, nonce, agora))
                self._db.commit()
            except Exception:    # noqa: BLE001 — PRIMARY KEY: nonce já usado
                self._db.commit()
                self._auditar(pid, "pedido recusado", motivo="nonce repetido (repetição)", caminho=caminho[:120], ip=ip)
                return None, 409, "nonce repetido: pedido recusado (repetição)"
        if self._lim and self._lim.tentar(pid) > 0:
            self._auditar(pid, "pedido recusado", motivo="limite de pedidos", caminho=caminho[:120])
            return None, 429, "limite de pedidos do parceiro"
        return par, 0, ""

    def rota_parceiro(self, metodo: str, caminho_completo: str, cab, corpo: bytes, ip: str, transporte_ok: bool) -> tuple[int, bytes, dict]:
        """Rotas /api/intercambio/v1/* (sem sessão: valem a assinatura e a lista do parceiro). Resposta assinada."""
        def resp(codigo: int, obj: dict, par: dict | None = None, nonce: str = "") -> tuple[int, bytes, dict]:
            b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            h = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
            chave = self._chaves().get(par["id"]) if par else None
            if chave and nonce:
                m = str(int(self.relogio()))
                h.update({"X-Physis-Origem": self.origem, "X-Physis-Momento": m, "X-Physis-Assinatura": assinar(chave, "RESPOSTA", caminho_completo, m, nonce, b)})
            return codigo, b, h
        if not transporte_ok:
            return resp(403, {"ok": False, "erro": "intercâmbio só por HTTPS ou pela rede local/VPN"})
        par, cod, motivo = self.verificar(metodo, caminho_completo, cab, corpo or b"", ip)
        if not par:
            return resp(cod, {"ok": False, "erro": motivo})
        nonce = (cab.get("X-Physis-Nonce") or "").strip()
        u = urlparse(caminho_completo)
        p = u.path[len(PREFIXO + "v1/"):]
        if metodo == "GET" and p == "oferta":
            self._auditar(par["id"], "oferta consultada", ip=ip)
            return resp(200, {"ok": True, "esquema": ESQUEMA, "origem": self.origem, "envio": par["enviar"], "recebe": par["receber"],
                              "datasets": {k: {"campos": list(v["campos"]), "pessoais": list(v["pessoais"])} for k, v in DATASETS.items()}}, par, nonce)
        m = re.fullmatch(r"(dados|receber)/([a-z_]+)", p)
        if not m or m.group(2) not in DATASETS:
            return resp(404, {"ok": False, "erro": "rota ou conjunto desconhecido"}, par, nonce)
        ds = m.group(2)
        if metodo == "GET" and m.group(1) == "dados":
            if ds not in par["enviar"]:
                self._auditar(par["id"], "envio recusado", dataset=ds, motivo="conjunto não permitido")
                return resp(403, {"ok": False, "erro": "conjunto não permitido para este parceiro"}, par, nonce)
            try:
                desde = float((parse_qs(u.query).get("desde") or ["0"])[0])
            except ValueError:
                desde = 0.0
            pk, tirados = self.pacote(ds, par["id"], desde or None)
            self._auditar(par["id"], "enviado (puxado pelo parceiro)", dataset=ds, registros=len(pk["registros"]), pessoais_retirados=tirados,
                          resumo=sha256(canonico(pk["registros"])))
            return resp(200, dict(pk, ok=True), par, nonce)
        if metodo == "POST" and m.group(1) == "receber":
            if ds not in par["receber"]:
                self._auditar(par["id"], "recebimento recusado", dataset=ds, motivo="conjunto não permitido")
                return resp(403, {"ok": False, "erro": "conjunto não permitido para este parceiro"}, par, nonce)
            try:
                pk = json.loads((corpo or b"").decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return resp(400, {"ok": False, "erro": "json inválido"}, par, nonce)
            ok, ruins, erro = self.conferir_pacote(par["id"], ds, pk)
            if erro:
                self._auditar(par["id"], "recebimento recusado", dataset=ds, motivo=erro)
                return resp(400, {"ok": False, "erro": erro}, par, nonce)
            n = self.guardar_recebidos(par["id"], ds, ok, "recebido do parceiro")
            self._auditar(par["id"], "recebido (enviado pelo parceiro)", dataset=ds, registros=len(ok), novos=n, recusados=len(ruins),
                          resumo=sha256(canonico(ok)))
            return resp(200, {"ok": True, "recebidos": len(ok), "novos_pendentes": n, "recusados": ruins[:50],
                              "aviso": "Os registros ficam pendentes até a direção do destino aprovar."}, par, nonce)
        return resp(405, {"ok": False, "erro": "método não aceito"}, par, nonce)

    # ── cliente: esta instalação chama o parceiro ──
    def _chamar(self, par: dict, metodo: str, rota: str, corpo_obj=None) -> tuple[int, dict]:
        chave = self._chaves().get(par["id"])
        if not chave:
            return 0, {"ok": False, "erro": "sem chave para este parceiro (defina a chave)"}
        erro = endereco_permitido(par["url"])
        if erro:
            return 0, {"ok": False, "erro": erro}
        base = urlparse(par["url"])
        caminho = (base.path.rstrip("/") + rota) if base.path not in ("", "/") else rota
        corpo = json.dumps(corpo_obj, ensure_ascii=False).encode("utf-8") if corpo_obj is not None else b""
        momento, nonce = str(int(self.relogio())), secrets.token_urlsafe(24)
        cab = {"X-Physis-Origem": self.origem, "X-Physis-Momento": momento, "X-Physis-Nonce": nonce,
               "X-Physis-Assinatura": assinar(chave, metodo, rota, momento, nonce, corpo), "Accept": "application/json"}
        if corpo_obj is not None:
            cab["Content-Type"] = "application/json; charset=utf-8"
        url = f"{base.scheme}://{base.netloc}{caminho}"
        req = urllib.request.Request(url, data=corpo if metodo == "POST" else None, method=metodo, headers=cab)
        abrir = urllib.request.build_opener(urllib.request.ProxyHandler({}))      # sem proxy de sistema: direto (VPN ou HTTPS)
        try:
            with abrir.open(req, timeout=self.timeout) as r:
                status, b, h = r.status, r.read(CORPO_MAX + 1), r.headers
        except urllib.error.HTTPError as e:
            status, b, h = e.code, e.read(CORPO_MAX + 1), e.headers
        except (urllib.error.URLError, OSError, ValueError) as e:
            return 0, {"ok": False, "erro": f"sem ligação com o parceiro: {str(getattr(e, 'reason', e))[:120]}"}
        if len(b) > CORPO_MAX:
            return 0, {"ok": False, "erro": "resposta grande demais"}
        try:
            obj = json.loads(b.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            return status, {"ok": False, "erro": "resposta que não é JSON"}
        ass, m = (h.get("X-Physis-Assinatura") or "").lower(), h.get("X-Physis-Momento") or ""
        assinada = (h.get("X-Physis-Origem") == par["id"] and re.fullmatch(r"\d{9,12}", m) and abs(self.relogio() - int(m)) <= JANELA_S
                    and SHA_RX.fullmatch(ass) and hmac.compare_digest(ass, assinar(chave, "RESPOSTA", rota, m, nonce, b)))
        if not assinada:
            erro = obj.get("erro") if isinstance(obj, dict) else None
            return status or 0, {"ok": False, "erro": "resposta sem assinatura válida" + (f" ({erro})" if erro else ""), "status": status}
        return status, obj if isinstance(obj, dict) else {"ok": False, "erro": "resposta inesperada"}

    def _par_ativo(self, pid: str) -> tuple[dict | None, dict | None]:
        par = self._parceiro(pid)
        if not par:
            return None, {"ok": False, "codigo": 404, "erro": "parceiro desconhecido"}
        if not par["ativo"]:
            return None, {"ok": False, "erro": "parceiro inativo"}
        return par, None

    def testar(self, pid: str, quem: str) -> dict:
        par, erro = self._par_ativo(pid)
        if erro:
            return erro
        st, j = self._chamar(par, "GET", PREFIXO + "v1/oferta")
        self._auditar(pid, "ligacao testada", por=quem, ok=st == 200 and bool(j.get("ok")), status=st)
        if st != 200 or not j.get("ok"):
            return {"ok": False, "erro": j.get("erro") or f"o parceiro respondeu {st}", "status": st}
        return {"ok": True, "parceiro_envia": j.get("envio", []), "parceiro_recebe": j.get("recebe", []), "esquema": j.get("esquema")}

    def puxar(self, pid: str, dataset: str, quem: str) -> dict:
        par, erro = self._par_ativo(pid)
        if erro:
            return erro
        if dataset not in par["receber"]:
            return {"ok": False, "erro": "este conjunto não está na lista do que se recebe deste parceiro"}
        st, j = self._chamar(par, "GET", PREFIXO + "v1/dados/" + dataset)
        if st != 200 or not j.get("ok"):
            self._auditar(pid, "puxar falhou", por=quem, dataset=dataset, status=st, motivo=str(j.get("erro"))[:200])
            return {"ok": False, "erro": j.get("erro") or f"o parceiro respondeu {st}", "status": st}
        pk = {k: v for k, v in j.items() if k != "ok"}
        ok, ruins, erro_p = self.conferir_pacote(pid, dataset, pk)
        if erro_p:
            self._auditar(pid, "puxar recusado", por=quem, dataset=dataset, motivo=erro_p)
            return {"ok": False, "erro": erro_p}
        n = self.guardar_recebidos(pid, dataset, ok, "puxado")
        self._auditar(pid, "recebido (puxado daqui)", por=quem, dataset=dataset, registros=len(ok), novos=n, recusados=len(ruins),
                      resumo=sha256(canonico(ok)))
        return {"ok": True, "recebidos": len(ok), "novos_pendentes": n, "recusados": ruins[:50],
                "aviso": "Os registros ficam pendentes até a direção aprovar."}

    def enviar(self, pid: str, dataset: str, quem: str) -> dict:
        par, erro = self._par_ativo(pid)
        if erro:
            return erro
        if dataset not in par["enviar"]:
            return {"ok": False, "erro": "este conjunto não está na lista do que se envia a este parceiro"}
        pk, tirados = self.pacote(dataset, pid)
        st, j = self._chamar(par, "POST", PREFIXO + "v1/receber/" + dataset, pk)
        ok = st == 200 and bool(j.get("ok"))
        self._auditar(pid, "enviado (empurrado daqui)" if ok else "enviar falhou", por=quem, dataset=dataset, registros=len(pk["registros"]),
                      pessoais_retirados=tirados, status=st, resumo=sha256(canonico(pk["registros"])))
        if not ok:
            return {"ok": False, "erro": j.get("erro") or f"o parceiro respondeu {st}", "status": st}
        return {"ok": True, "enviados": len(pk["registros"]), "pessoais_retirados": tirados, "parceiro": {k: j.get(k) for k in ("recebidos", "novos_pendentes", "recusados")}}

    # ── estado para a tela da direção ──
    def estado(self) -> dict:
        cont = {k: 0 for k in DATASETS}
        for ds, n in self._db.execute("SELECT dataset, COUNT(*) FROM intercambio_publicado GROUP BY dataset"):
            cont[ds] = n
        cont["cursos_catalogo"] = len([c for c in (self._cursos() or []) if isinstance(c, dict) and c.get("nome")])
        cont["lotes_integridade"] = len(self._fonte("lotes_integridade"))
        aprovados = dict(self._db.execute("SELECT dataset, COUNT(*) FROM intercambio_recebido WHERE estado='aprovado' GROUP BY dataset").fetchall())
        return {"ok": True, "esquema": ESQUEMA, "origem": self.origem,
                "datasets": [{"id": k, "nome": v["nome"], "campos": list(v["campos"]), "pessoais": list(v["pessoais"]),
                              "oferecidos": cont.get(k, 0), "aprovados": aprovados.get(k, 0)} for k, v in DATASETS.items()],
                "parceiros": self.parceiros(), "pendentes": self.pendentes(200), "registro": self.registro_eventos(100)}

    # ── rotas da direção (com sessão; o servidor já conferiu o papel) ──
    def rota_admin(self, metodo: str, p: str, conta: dict, d: dict | None, q: dict) -> tuple[int, dict]:
        quem = str(conta.get("usuario") or conta.get("nome") or "direção")[:120]
        d = d or {}
        if metodo == "GET":
            if p == PREFIXO + "estado":
                return 200, self.estado()
            if p == PREFIXO + "recebidos":
                ds = (q.get("dataset") or [""])[0]
                if ds and ds not in DATASETS:
                    return 400, {"ok": False, "erro": "conjunto desconhecido"}
                return 200, {"ok": True, "registros": self.recebidos(ds or None)}
            if p == PREFIXO + "publicados":
                ds = (q.get("dataset") or [""])[0]
                return 200, {"ok": True, "registros": self.publicados(ds or None)}
            return 404, {"ok": False, "erro": "rota desconhecida"}
        acoes = {
            "parceiro": lambda: self.salvar_parceiro(d, quem),
            "parceiro/chave": lambda: self.definir_chave(str(d.get("id") or ""), d.get("chave") or None, quem),
            "parceiro/remover": lambda: self.remover_parceiro(str(d.get("id") or ""), quem),
            "publicar": lambda: self.publicar(str(d.get("dataset") or ""), d.get("registros"), quem),
            "publicado/remover": lambda: self.despublicar(str(d.get("dataset") or ""), str(d.get("id") or ""), quem),
            "testar": lambda: self.testar(str(d.get("parceiro") or ""), quem),
            "puxar": lambda: self.puxar(str(d.get("parceiro") or ""), str(d.get("dataset") or ""), quem),
            "enviar": lambda: self.enviar(str(d.get("parceiro") or ""), str(d.get("dataset") or ""), quem),
            "revisar": lambda: self.revisar(d.get("ids"), str(d.get("decisao") or ""), quem, str(d.get("motivo") or "")),
        }
        f = acoes.get(p[len(PREFIXO):])
        if not f:
            return 404, {"ok": False, "erro": "rota desconhecida"}
        if p.endswith(("/puxar", "/enviar")) and str(d.get("dataset") or "") not in DATASETS:
            return 400, {"ok": False, "erro": "conjunto desconhecido"}
        r = f()
        return r.pop("codigo", 200 if r.get("ok") else 400), r
