"""Robôs da Physis: uma base comum e seis robôs que hoje funcionam por regras, sem internet.

Toda resposta de robô tem o mesmo formato:
  {"ok", "robo", "intencao", "resposta" (texto em português), "fontes" (de onde veio), "confianca" (0 a 1),
   "revisao_humana" (True quando uma pessoa precisa conferir antes de usar), "dados" (o resultado estruturado),
   "ia" ({"usada": bool, ...})}

IA local (opcional, desligada por padrão): a variável PHYSIS_IA_URL aponta para o servidor de IA da própria
Physis — compatível com OpenAI (/v1/chat/completions) ou Ollama (/api/generate). Sem ela, nada sai do hub.
Mesmo ligada:
  * só aceita endereço da rede local (localhost, IP privado, nome .local ou sem domínio); endereço de fora
    só com PHYSIS_IA_EXTERNO=1 escrito de propósito;
  * tira dados pessoais (e-mail, telefone, CPF, CNPJ, CEP, coordenadas, nomes informados) antes de mandar;
  * tem tempo máximo (PHYSIS_IA_TEMPO, 30 s) e, se falhar, a resposta por regras continua valendo;
  * o registro guarda só metadados (robô, tamanho, tempo, ok) — nunca o texto.

Ordem de quem melhora o texto (ia_do_ambiente): Claude com a conta da Physis, se configurado (ia_claude.py) →
IA local acima (Fase 2) → respostas prontas por regras. O texto da resposta não leva aviso visível (decisão de
15/11/2026); o protocolo fica: "ia" na resposta (provedor, modelo, quando) e uma entrada "ia" no registro encadeado
do hub (ia.protocolo = id do registro), e revisao_humana=True. Ver docs/IA_CLAUDE.md.

Robôs: suporte, precos, editais, marketing, projetos, pluviometro. Ver docs/ROBOS.md.
"""
from __future__ import annotations

import ast
import ipaddress
import json
import logging
import math
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from . import clima as clima_mod
from . import editais as editais_mod
from . import ia_claude as claude_mod

log = logging.getLogger("physis.robos")
RAIZ = Path(__file__).resolve().parent.parent
REGISTRO_IA: list[dict] = []           # últimas chamadas à IA, só metadados (a tela de estado pode mostrar)


# ══ Texto: normalização, palavras e TF-IDF ════════════════════════════════════════════════════════
PARADAS = set("""a o e é de da do das dos em no na nos nas um uma uns umas para por com sem que se ao aos à às
como mais menos muito pouco ou ser ter tem há foi são está estão isso isto esse essa este esta pelo pela pelos pelas
eu você voce ele ela nós nos eles elas meu minha seu sua qual quais quando onde porque porquê sobre entre até ate
também tambem já ja não nao sim lhe the and for with from this that are was not you your how what can""".split())


def normalizar(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c) != "Mn").lower()


def palavras(s: str) -> list[str]:
    """Palavras com 3+ letras, sem acento, sem palavras vazias; corte simples de plural e tamanho (radical)."""
    out = []
    for w in re.findall(r"[a-z0-9]+", normalizar(s)):
        if len(w) < 3 or w in PARADAS or w.isdigit():
            continue
        if len(w) > 4 and w.endswith("s"):
            w = w[:-1]
        out.append(w[:8])
    return out


class IndiceTFIDF:
    """Busca por semelhança de palavras (TF-IDF e cosseno). Pequeno, explicável e sem dependências."""

    def __init__(self, textos: list[str]):
        self.docs = [Counter(palavras(t)) for t in textos]
        n = len(self.docs)
        df = Counter(w for d in self.docs for w in d)
        self.idf = {w: math.log((1 + n) / (1 + c)) + 1.0 for w, c in df.items()}
        self.vetores = [self._vetor(d) for d in self.docs]

    def _vetor(self, cont: Counter) -> dict[str, float]:
        v = {w: (1 + math.log(c)) * self.idf.get(w, 0.0) for w, c in cont.items() if w in self.idf}
        norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {w: x / norma for w, x in v.items()}

    def vetor(self, texto: str) -> dict[str, float]:
        return self._vetor(Counter(palavras(texto)))

    @staticmethod
    def cosseno(a: dict[str, float], b: dict[str, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(x * b.get(w, 0.0) for w, x in a.items())

    def buscar(self, consulta: str, k: int = 3) -> list[tuple[float, int]]:
        q = self.vetor(consulta)
        notas = [(self.cosseno(q, v), i) for i, v in enumerate(self.vetores)]
        notas.sort(key=lambda t: (-t[0], t[1]))
        return [(round(s, 4), i) for s, i in notas[:k] if s > 0]

    def termos_comuns(self, consulta: str, i: int, n: int = 5) -> list[str]:
        q = self.vetor(consulta)
        comuns = sorted(((q[w] * self.vetores[i][w], w) for w in q if w in self.vetores[i]), reverse=True)
        return [w for _, w in comuns[:n]]


# ══ Dados pessoais: tirar antes de qualquer envio ═════════════════════════════════════════════════
_PADROES_PESSOAIS = [
    (re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"), "[e-mail]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
    (re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"), "[CNPJ]"),
    (re.compile(r"(\+?55\s?)?\(?\b\d{2}\)?\s?9?\d{4}[-\s]?\d{4}\b"), "[telefone]"),
    (re.compile(r"\b\d{5}-\d{3}\b"), "[CEP]"),
    (re.compile(r"-?\b\d{1,2}\.\d{3,}\s*,\s*-?\d{1,3}\.\d{3,}\b"), "[coordenadas]"),
    (re.compile(r"https?://\S+"), "[link]"),
]


def anonimizar_relatorio(texto: str, nomes: tuple[str, ...] | list[str] = ()) -> tuple[str, dict]:
    """Texto sem dados pessoais e quantos de cada tipo saíram (ex.: {"e-mail": 1}) — a nota do que foi enviado."""
    t, cont = str(texto or ""), {}
    for rx, troca in _PADROES_PESSOAIS:
        t, n = rx.subn(troca, t)
        if n:
            cont[troca.strip("[]")] = cont.get(troca.strip("[]"), 0) + n
    for nome in sorted((n for n in nomes if n and len(n) >= 3), key=len, reverse=True):
        t, n = re.subn(re.escape(nome), "[pessoa]", t, flags=re.I)
        if n:
            cont["pessoa"] = cont.get("pessoa", 0) + n
    return t, cont


def anonimizar(texto: str, nomes: tuple[str, ...] | list[str] = ()) -> str:
    return anonimizar_relatorio(texto, nomes)[0]


# ══ Gancho para a IA local ═══════════════════════════════════════════════════════════════════════
def _post_json(url: str, corpo: dict, tempo: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(corpo).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "PhysisHub/1.0"})
    chave = os.environ.get("PHYSIS_IA_CHAVE")
    if chave:
        req.add_header("Authorization", f"Bearer {chave}")
    with urllib.request.urlopen(req, timeout=tempo) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def destino_local(url: str) -> bool:
    """Só a rede da Physis/cliente: localhost, IP privado, nome .local/.lan/.internal ou sem domínio."""
    try:
        u = urllib.parse.urlparse(url)
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    if u.scheme not in ("http", "https") or not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_private or ip.is_loopback or ip.is_link_local
    except ValueError:
        return host == "localhost" or "." not in host or host.endswith((".local", ".lan", ".internal", ".localhost"))


class IALocal:
    def __init__(self, url: str | None = None, modelo: str | None = None, tempo: float | None = None, enviar=None):
        self.url = (url if url is not None else os.environ.get("PHYSIS_IA_URL") or "").strip()
        self.modelo = modelo or os.environ.get("PHYSIS_IA_MODELO") or "physis"
        self.tempo = float(tempo or os.environ.get("PHYSIS_IA_TEMPO") or 30)
        self.enviar = enviar or _post_json
        self.erro = ""
        self.ultimo: dict = {}
        if self.url and not destino_local(self.url) and os.environ.get("PHYSIS_IA_EXTERNO") != "1":
            self.erro = "PHYSIS_IA_URL fora da rede local: desligada (use PHYSIS_IA_EXTERNO=1 só se for mesmo o servidor da Physis)"
            self.url = ""

    @property
    def ativa(self) -> bool:
        return bool(self.url)

    @property
    def tipo(self) -> str:
        return "ollama" if "/api/generate" in self.url or os.environ.get("PHYSIS_IA_TIPO") == "ollama" else "openai"

    def gerar(self, sistema: str, pedido: str, robo: str = "", nomes=()) -> str | None:
        """Texto da IA ou None (desligada, fora do ar, tempo esgotado). O pedido vai sem dados pessoais."""
        if not self.ativa:
            return None
        pedido = anonimizar(pedido, nomes)
        inicio = time.monotonic()
        ok, texto = False, None
        try:
            if self.tipo == "ollama":
                url = self.url if self.url.endswith("/api/generate") else self.url.rstrip("/") + "/api/generate"
                r = self.enviar(url, {"model": self.modelo, "system": sistema, "prompt": pedido, "stream": False,
                                      "options": {"temperature": 0.2}}, self.tempo)
                texto = r.get("response")
            else:
                url = self.url if self.url.endswith("/chat/completions") else self.url.rstrip("/") + "/v1/chat/completions"
                r = self.enviar(url, {"model": self.modelo, "temperature": 0.2,
                                      "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": pedido}]}, self.tempo)
                texto = ((r.get("choices") or [{}])[0].get("message") or {}).get("content")
            ok = bool(texto)
        except (urllib.error.URLError, OSError, ValueError, TypeError, AttributeError, IndexError) as exc:
            self.erro = type(exc).__name__
        ms = int((time.monotonic() - inicio) * 1000)
        meta = {"robo": robo, "tipo": self.tipo, "bytes_enviados": len(pedido.encode()) + len(sistema.encode()), "ms": ms, "ok": ok,
                "quando": time.time()}
        REGISTRO_IA.append(meta)
        del REGISTRO_IA[:-100]
        log.info("ia robo=%s tipo=%s bytes=%d ms=%d ok=%s", robo, self.tipo, meta["bytes_enviados"], ms, ok)
        self.ultimo = {"tipo": self.tipo, "modelo": self.modelo} if ok else {}
        return texto.strip() if ok else None


AVISO_IA = claude_mod.AVISO_IA


class CadeiaIA:
    """Tenta cada IA na ordem (Claude → local); se nenhuma responder, o robô usa a resposta por regras."""

    def __init__(self, provedores: list):
        self.provedores = [p for p in provedores if p is not None]
        self.erro = ""
        self.ultimo: dict = {}
        self.tentativas: list[str] = []

    @property
    def ativa(self) -> bool:
        return any(p.ativa for p in self.provedores)

    @property
    def tipo(self) -> str:
        return " → ".join([p.tipo for p in self.provedores if p.ativa] + ["regras"])

    def gerar(self, sistema: str, pedido: str, robo: str = "", nomes=()) -> str | None:
        self.ultimo, self.tentativas, self.erro = {}, [], ""
        for p in self.provedores:
            if not p.ativa:
                continue
            texto = p.gerar(sistema, pedido, robo=robo, nomes=nomes)
            if texto:
                self.ultimo = dict(getattr(p, "ultimo", None) or {"tipo": p.tipo})
                return texto
            self.tentativas.append(f"{p.tipo}: {p.erro or 'sem resposta'}")
        self.erro = "; ".join(self.tentativas)
        return None


def ia_do_ambiente(avisar=None) -> CadeiaIA:
    """Claude (se houver chave) → IA local (PHYSIS_IA_URL, Fase 2) → regras. avisar(assunto, corpo): aviso de teto."""
    return CadeiaIA([claude_mod.IAClaude(avisar=avisar), IALocal()])


def claude_da_cadeia(ia) -> "claude_mod.IAClaude | None":
    for p in getattr(ia, "provedores", None) or ([ia] if ia is not None else []):
        if isinstance(p, claude_mod.IAClaude):
            return p
    return None


def registrar_uso_ia(hub, robo: str, info: dict, extra: dict | None = None) -> str | None:
    """Protocolo interno: quem gerou (robô/documento), provedor, modelo e quando, no registro encadeado. Sem texto."""
    if hub is None or not hasattr(hub, "registrar"):
        return None
    try:
        conteudo = {"o_que": "texto gerado por IA", "robo": robo, "provedor": info.get("tipo"), "modelo": info.get("modelo"),
                    "quando": info.get("quando"), "revisao_humana": True}
        if info.get("dados_pessoais_removidos"):
            conteudo["dados_pessoais_removidos"] = info["dados_pessoais_removidos"]
        conteudo.update(extra or {})
        with hub._trava:
            ident = hub.registrar("ia", f"robo:{robo}", conteudo)
            hub._db.commit()
        return ident
    except Exception as exc:                      # o protocolo não derruba a resposta; fica no log
        log.warning("protocolo de IA não gravado (%s)", type(exc).__name__)
        return None


# ══ Base dos robôs ══════════════════════════════════════════════════════════════════════════════
def resposta(robo: str, texto: str, *, fontes=None, confianca: float = 1.0, revisao_humana: bool = False,
             dados=None, intencao: str | None = None, ia=None) -> dict:
    return {"ok": True, "robo": robo, "intencao": intencao, "resposta": texto, "fontes": fontes or [],
            "confianca": round(max(0.0, min(1.0, confianca)), 3), "revisao_humana": bool(revisao_humana),
            "dados": dados if dados is not None else {}, "ia": ia or {"usada": False}}


class Robo:
    nome = "robo"
    titulo = "Robô"
    descricao = ""
    intencoes: tuple[tuple[str, str], ...] = ()       # (nome, expressão regular sobre o texto sem acento)
    sistema_ia = "Você é um assistente da Physis. Responda em português do Brasil, curto e claro, só com base no material dado."

    def __init__(self, contexto: dict | None = None, ia=None):
        self.ctx = contexto or {}
        self.ia = ia if ia is not None else ia_do_ambiente()

    def agora(self) -> float:
        h = self.ctx.get("hub")
        return (self.ctx.get("relogio") or (h.relogio if h else time.time))()

    def intencao(self, texto: str) -> str | None:
        t = normalizar(texto)
        return next((nome for nome, rx in self.intencoes if re.search(rx, t)), None)

    def responder(self, pedido: dict) -> dict:
        pedido = pedido if isinstance(pedido, dict) else {}
        inicio = time.monotonic()
        try:
            r = self._responder(pedido)
        except (ValueError, TypeError, KeyError) as exc:
            r = {"ok": False, "robo": self.nome, "erro": f"pedido inválido: {exc}", "revisao_humana": True}
        if r.get("intencao") is None:
            r["intencao"] = self.intencao(str(pedido.get("pergunta") or ""))
        if (r.get("ia") or {}).get("usada"):         # passou por IA: protocolo no registro e revisão humana
            r["revisao_humana"] = True
            r["ia"]["protocolo"] = registrar_uso_ia(self.ctx.get("hub"), self.nome, r["ia"])
        log.info("robo=%s intencao=%s tamanho=%d ok=%s ms=%d", self.nome, r.get("intencao"), len(json.dumps(pedido, ensure_ascii=False)),
                 r.get("ok"), int((time.monotonic() - inicio) * 1000))
        return r

    def _responder(self, pedido: dict) -> dict:        # pragma: no cover — cada robô implementa
        raise NotImplementedError

    def melhorar(self, rascunho: str, material: str, instrucao: str) -> tuple[str, dict]:
        """Passa o rascunho pela IA local, se houver. Sem IA (ou com falha), devolve o rascunho por regras."""
        if not self.ia.ativa:
            return rascunho, {"usada": False}
        texto = self.ia.gerar(self.sistema_ia, f"{instrucao}\n\nMaterial:\n{material}\n\nRascunho:\n{rascunho}", robo=self.nome,
                              nomes=self.ctx.get("nomes_pessoais") or ())
        if not texto:
            return rascunho, {"usada": False, "erro": self.ia.erro or "sem resposta"}
        info = dict(getattr(self.ia, "ultimo", None) or {"tipo": self.ia.tipo})
        info.update(usada=True, revisao_humana=True)
        info.setdefault("quando", datetime.fromtimestamp(self.agora()).isoformat(timespec="seconds"))
        if getattr(self.ia, "tentativas", None):
            info["tentativas"] = list(self.ia.tentativas)     # ex.: Claude no teto, quem respondeu foi a IA local
        return texto, info


# ── 1. Suporte ──────────────────────────────────────────────────────────────────────────────────
def _paragrafos_md(caminho: Path, rotulo: str) -> list[dict]:
    out, secao, buf, em_codigo = [], "", [], False
    def fechar():
        texto = " ".join(x.strip() for x in buf).strip()
        if len(texto) >= 40:
            out.append({"texto": texto, "fonte": rotulo, "secao": secao})
        buf.clear()
    for linha in caminho.read_text(encoding="utf-8", errors="replace").splitlines():
        if linha.strip().startswith("```"):
            em_codigo = not em_codigo
            continue
        if em_codigo:
            continue
        m = re.match(r"^#{1,6}\s+(.*)", linha)
        if m:
            fechar()
            secao = m.group(1).strip()
        elif not linha.strip():
            fechar()
        else:
            buf.append(re.sub(r"[*`|]", " ", linha))
    fechar()
    return out


def _curso_do_painel(caminho: Path) -> list[dict]:
    """As telas do curso de introdução embutido no painel (CURSOS_EMBUTIDOS), uma por parágrafo."""
    try:
        txt = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    ini, fim = txt.find("const CURSOS_EMBUTIDOS"), txt.find("const ETAPAS_CURSO")
    if ini < 0 or fim < ini:
        return []
    bloco, out = txt[ini:fim], []
    cod = (re.search(r'cod:"([^"]+)"', bloco) or [None, "curso"])[1]
    for m in re.finditer(r'\{\s*t:"([^"]+)"[^\n]*?itens:\[(.*?)\]\s*,\s*dica:"((?:[^"\\]|\\.)*)"', bloco):
        itens = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(2))
        out.append({"texto": " ".join(itens + [m.group(3)]), "fonte": f"Curso {cod}", "secao": m.group(1)})
    return out


# notas internas de desenvolvimento: não entram nas respostas a clientes (podem citar pessoas e decisões internas)
DOCS_INTERNOS = ("MEMO-CLAUDE-CODE.md", "LISTA-DE-MODIFICACOES.md", "CHECKLIST.md", "IA_CLAUDE.md")


PUBLICOS = ("cliente", "equipe")
# Texto de desenvolvedor: nome de arquivo, pasta do código, rota, identificador de código. Nunca vai para o cliente.
_DEV = re.compile(r"`|\b[\w-]+\.(?:md|js|py|html|json|yaml|yml|db|odt|ods|sh|ps1|ino|h)\b|\bdocs/|physis_hub|/api/|\b[a-z]+_[a-z0-9_]+\b"
                  r"|\b[a-z]+[A-Z][A-Za-z]+\b|\bPHYSIS_[A-Z_]+|\[MARCADOR|\{\{")


def eh_texto_de_cliente(texto: str) -> bool:
    """True quando o trecho pode ir a um cliente: sem nome de arquivo, pasta, rota, variável ou identificador de código,
    sem [MARCADOR] e sem {{campo}} (trecho de modelo ainda incompleto)."""
    return not _DEV.search(str(texto or ""))


def _manual_cliente(pasta_modelos: Path | None = None) -> list[dict]:
    """As seções do manual (comum e de cada módulo): a base do suporte para o cliente, junto com o curso de introdução."""
    from . import documentos_auto
    pastas = [Path(pasta_modelos)] if pasta_modelos else documentos_auto.pastas_modelos()
    nomes = documentos_auto.nomes_modulos()
    out, vistos = [], set()
    for pasta in pastas:
        arqs = [(pasta / "manual" / "comum.md", "Manual da plataforma")] + [
            (a, "Manual · " + nomes.get(a.stem, a.stem.capitalize())) for a in sorted((pasta / "manual" / "modulos").glob("*.md"))]
        for arq, rotulo in arqs:
            if arq.is_file() and arq.name + rotulo not in vistos:
                vistos.add(arq.name + rotulo)
                out += _paragrafos_md(arq, rotulo)
    return out


def carregar_base(pasta_docs: Path | None = None, painel: Path | None = None, internos: bool = False,
                  publico: str = "equipe", pasta_modelos: Path | None = None) -> list[dict]:
    """Base do suporte por público (15/11/2026). Cliente: só o manual por módulo e o curso de introdução, e só trechos
    sem nome de arquivo ou código. Equipe: isso mais a documentação técnica (docs/*.md) e as explicações do código."""
    base = []
    if publico == "equipe":
        pasta = Path(pasta_docs or RAIZ / "docs")
        for arq in sorted(pasta.glob("*.md")):
            if internos or arq.name not in DOCS_INTERNOS:
                base += _paragrafos_md(arq, f"docs/{arq.name}")
        base += _docstrings(RAIZ / "physis_hub")
    cliente = _manual_cliente(pasta_modelos) + _curso_do_painel(Path(painel or RAIZ / "web" / "painel.html"))
    base += [b for b in cliente if publico == "equipe" or eh_texto_de_cliente(b["texto"] + " " + b["secao"])]
    return base


def so_para_cliente(base: list[dict]) -> list[dict]:
    """Filtro de segurança da base injetada: fora o que é de desenvolvedor (fonte ou texto)."""
    return [b for b in base if not str(b.get("fonte", "")).startswith(("docs/", "physis_hub/")) and eh_texto_de_cliente(
        f"{b.get('fonte', '')} {b.get('secao', '')} {b.get('texto', '')}")]


def _docstrings(pasta: Path) -> list[dict]:
    """A explicação no topo de cada módulo do hub (ex.: clima.py conta de onde vem a previsão)."""
    out = []
    for arq in sorted(pasta.glob("*.py")):
        try:
            doc = ast.get_docstring(ast.parse(arq.read_text(encoding="utf-8", errors="replace")))
        except (SyntaxError, ValueError, OSError):
            continue
        titulo = (doc or "").strip().splitlines()[0] if doc else ""
        for par in re.split(r"\n\s*\n", doc or ""):
            texto = " ".join(par.split())
            if len(texto) >= 40:
                out.append({"texto": texto, "fonte": f"physis_hub/{arq.name}", "secao": titulo[:80]})
    return out


class Suporte(Robo):
    nome, titulo = "suporte", "Suporte Physis"
    descricao = "Responde dúvidas com a documentação e o curso de introdução, citando de onde tirou; se não souber, sugere abrir chamado."
    intencoes = (("acesso", r"senha|login|entrar|conta"), ("exportar", r"baixar|export|word|pdf|excel"),
                 ("sensor", r"sensor|no |receptor|lora|bateria|umidade"), ("clima", r"chuva|previs|clima|tempo"),
                 ("chamado", r"chamado|suporte|ajuda|whatsapp"))
    LIMIAR = 0.15            # abaixo disso não responde: sugere chamado
    SEGURO = 0.35            # acima disso dispensa revisão humana

    def __init__(self, contexto=None, ia=None):
        super().__init__(contexto, ia)
        self._indices: dict = {}

    def indice(self, publico: str = "equipe") -> tuple[list[dict], IndiceTFIDF]:
        """Um índice por público. Cliente: manual por módulo + curso de introdução (nunca docs de desenvolvedor)."""
        publico = publico if publico in PUBLICOS else "cliente"
        if publico not in self._indices:
            dada = self.ctx.get("base_suporte")
            if dada is not None:
                base = list(dada) if publico == "equipe" else so_para_cliente(dada)
            else:
                base = carregar_base(self.ctx.get("pasta_docs"), self.ctx.get("painel_html"), bool(self.ctx.get("docs_internos")),
                                     publico=publico, pasta_modelos=self.ctx.get("pasta_modelos"))
            self._indices[publico] = (base, IndiceTFIDF([f"{d['secao']} {d['texto']}" for d in base]))
        return self._indices[publico]

    def _responder(self, pedido: dict) -> dict:
        pergunta = str(pedido.get("pergunta") or "").strip()[:1000]
        if not pergunta:
            raise ValueError("falta a pergunta")
        # quem pergunta: o servidor põe _publico pela sessão (equipe ou cliente); sem isso, vale o mais restrito
        publico = "equipe" if pedido.get("_publico") == "equipe" else "cliente"
        base, idx = self.indice(publico)
        achados = idx.buscar(pergunta, k=3) if base else []
        fontes = [{"n": k + 1, "fonte": base[i]["fonte"], "secao": base[i]["secao"], "trecho": base[i]["texto"][:300],
                   "semelhanca": s, "termos": idx.termos_comuns(pergunta, i)} for k, (s, i) in enumerate(achados)]
        # uma palavra só em comum (ex.: "receita") não basta: a confiança cai pela metade
        conf = (achados[0][0] * (1.0 if len(fontes[0]["termos"]) >= 2 else 0.5)) if achados else 0.0
        if conf < self.LIMIAR:
            dados = {"escalar": {"assunto": pergunta[:140], "mensagem": pergunta + ("\n\nTalvez relacionado: " +
                                 "; ".join(f"{f['fonte']} § {f['secao']}" for f in fontes) if fontes else "")}}
            texto = ("Não encontrei isso com segurança na documentação. Sugiro abrir um chamado no Suporte Physis: "
                     "uma pessoa da equipe responde.")
            h, para = self.ctx.get("hub"), self.ctx.get("suporte_email")
            if pedido.get("abrir_chamado") and h and para:
                r = h.suporte_abrir({"assunto": pergunta[:140], "mensagem": dados["escalar"]["mensagem"],
                                     "contato": str(pedido.get("contato") or "")}, str(pedido.get("_quem") or self.ctx.get("quem", "")), para)
                dados["chamado"] = r
                if r.get("ok"):
                    texto = f"Abri o chamado {r['numero']} no Suporte Physis. A equipe responde pelo canal indicado."
            return resposta(self.nome, texto, fontes=fontes, confianca=conf, revisao_humana=True, dados=dados)
        top = base[achados[0][1]]
        trecho = top["texto"] if len(top["texto"]) <= 700 else top["texto"][:700].rsplit(" ", 1)[0] + "…"
        rascunho = f"{trecho} [1]"
        if len(fontes) > 1:
            rascunho += "\n\nVeja também: " + "; ".join(f"[{f['n']}] {f['fonte']} § {f['secao']}" for f in fontes[1:])
        material = "\n".join(f"[{f['n']}] ({f['fonte']} § {f['secao']}) {base[i]['texto'][:900]}" for f, (_, i) in zip(fontes, achados))
        instr = f"Pergunta: {pergunta}\nResponda só com o material, citando [n]."
        if publico == "cliente":
            instr += " Quem pergunta é cliente: não cite nome de arquivo, pasta, rota nem nome de código."
        texto, ia = self.melhorar(rascunho, material, instr)
        if publico == "cliente" and not eh_texto_de_cliente(texto):          # a IA escorregou: fica o texto do manual
            texto, ia = rascunho, dict(ia, usada=False, erro="resposta da IA citava arquivo ou código; ficou o texto do manual")
        return resposta(self.nome, texto, fontes=fontes, confianca=conf, revisao_humana=conf < self.SEGURO, ia=ia,
                        dados={"melhor": {"fonte": top["fonte"], "secao": top["secao"]}, "publico": publico})


# ── 2. Preços de propostas ──────────────────────────────────────────────────────────────────────
def _quartis(xs: list[float]) -> tuple[float, float, float]:
    s = sorted(xs)
    def q(p):
        k = (len(s) - 1) * p
        f, c = math.floor(k), math.ceil(k)
        return s[f] + (s[c] - s[f]) * (k - f)
    return q(0.25), q(0.5), q(0.75)


def faixa_de_precos(precos: list[float]) -> tuple[float, float, float] | None:
    """(mínimo aceitável, mediana, máximo aceitável): regra de Tukey com 4+ preços; com menos, -30%/+40% da mediana."""
    precos = [float(p) for p in precos if isinstance(p, (int, float)) and p > 0]
    if not precos:
        return None
    if len(precos) >= 4:
        q1, med, q3 = _quartis(precos)
        iqr = q3 - q1
        return max(0.0, q1 - 1.5 * iqr), med, q3 + 1.5 * iqr
    s = sorted(precos)
    med = s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2
    return med * 0.7, med, med * 1.4


class Precos(Robo):
    nome, titulo = "precos", "Preços de propostas"
    descricao = "Compara os itens de uma proposta com o catálogo e o histórico de preços e aponta o que está fora da faixa."
    intencoes = (("conferir", r"preco|valor|orcamento|proposta|caro|barato"),)
    SEMELHANCA_MIN = 0.35

    def _referencias(self, pedido: dict) -> list[dict]:
        refs = []
        for r in pedido.get("referencias") or []:
            if isinstance(r, dict) and r.get("descricao"):
                refs.append({"descricao": str(r["descricao"]), "min": r.get("min"), "max": r.get("max"), "preco": r.get("preco"),
                             "origem": r.get("origem") or "referência informada"})
        for r in pedido.get("historico") or []:
            if isinstance(r, dict) and r.get("descricao") and isinstance(r.get("preco"), (int, float)):
                refs.append({"descricao": str(r["descricao"]), "preco": float(r["preco"]), "origem": r.get("origem") or "proposta anterior"})
        h = self.ctx.get("hub")
        if h is not None and pedido.get("usar_catalogo", True):
            for ident, d in (h.loja_catalogo(interno=True).get("itens") or {}).items():
                if isinstance(d.get("preco"), (int, float)) and (d.get("nome") or d.get("sub")):
                    refs.append({"descricao": f"{d.get('nome', '')} {d.get('sub', '')}".strip(), "preco": float(d["preco"]),
                                 "origem": f"catálogo da loja ({ident})"})
        return refs

    def _responder(self, pedido: dict) -> dict:
        itens = [i for i in (pedido.get("itens") or []) if isinstance(i, dict) and i.get("descricao")]
        if not itens:
            raise ValueError("falta a lista de itens (descricao e preco)")
        refs = self._referencias(pedido)
        idx = IndiceTFIDF([r["descricao"] for r in refs]) if refs else None
        out, fora = [], 0
        for it in itens:
            preco = it.get("preco")
            preco = float(preco) if isinstance(preco, (int, float)) and not isinstance(preco, bool) else None
            achados = [(s, i) for s, i in (idx.buscar(it["descricao"], k=20) if idx else []) if s >= self.SEMELHANCA_MIN]
            r = {"descricao": it["descricao"], "preco": preco, "situacao": "sem_referencia", "faixa": None, "referencias": []}
            if achados and preco is not None:
                melhor = refs[achados[0][1]]
                if melhor.get("min") is not None and melhor.get("max") is not None:
                    lo, hi = float(melhor["min"]), float(melhor["max"])
                    med = (lo + hi) / 2
                else:
                    faixa = faixa_de_precos([refs[i]["preco"] for _, i in achados if refs[i].get("preco") is not None])
                    lo, med, hi = faixa if faixa else (None, None, None)
                if lo is not None:
                    r["faixa"] = [round(lo, 2), round(hi, 2)]
                    r["mediana"] = round(med, 2)
                    r["desvio_pct"] = round(100 * (preco - med) / med, 1) if med else None
                    r["situacao"] = "acima" if preco > hi else "abaixo" if preco < lo else "ok"
                r["referencias"] = [{"descricao": refs[i]["descricao"], "origem": refs[i]["origem"], "semelhanca": s,
                                     "preco": refs[i].get("preco")} for s, i in achados[:5]]
            fora += r["situacao"] in ("acima", "abaixo")
            out.append(r)
        sem = sum(1 for r in out if r["situacao"] == "sem_referencia")
        linhas = [f"{len(out)} itens conferidos: {fora} fora da faixa, {sem} sem referência."]
        for r in out:
            if r["situacao"] in ("acima", "abaixo"):
                linhas.append(f"• {r['descricao']}: R$ {r['preco']:.2f} está {'acima' if r['situacao'] == 'acima' else 'abaixo'} "
                              f"da faixa R$ {r['faixa'][0]:.2f}–{r['faixa'][1]:.2f} ({r['desvio_pct']:+.0f}% da mediana).")
        fontes = sorted({ref["origem"] for r in out for ref in r["referencias"]})
        conf = 1 - sem / len(out)
        material = "\n".join(f"- {r['descricao']}: preço {r['preco']}, situação {r['situacao']}, faixa {r['faixa']}, "
                             f"mediana {r.get('mediana')}, referências: " + "; ".join(f"{x['descricao']} ({x['origem']}, {x['preco']})"
                                                                                   for x in r["referencias"][:3])
                             for r in out)[:6000]
        texto, ia = self.melhorar("\n".join(linhas), material,
                                  "Explique em português simples, item por item, o que está fora da faixa e o que conferir. "
                                  "Use só os números do material; não proponha preço novo. É uma sugestão para a equipe.")
        return resposta(self.nome, texto, fontes=[{"fonte": f} for f in fontes], confianca=conf,
                        revisao_humana=fora > 0 or sem > 0, ia=ia, dados={"itens": out, "sugestao": True})


# ── 3. Editais ──────────────────────────────────────────────────────────────────────────────────
PERFIL_PHYSIS = ("Physis Engenharia: sustentabilidade, eficiência energética, energia solar fotovoltaica, água, irrigação, "
                 "saneamento, reúso, clima, carbono, descarbonização, adaptação e resiliência climática, agro, agrofloresta, "
                 "soluções baseadas na natureza, IoT, sensores, monitoramento, automação, inovação tecnológica, economia "
                 "circular, resíduos, ESG, certificações, climatização, construção sustentável, capacitação e cursos.")


class Editais(Robo):
    nome, titulo = "editais", "Editais"
    descricao = "Ordena os editais pela semelhança com as áreas da Physis e com os editais em que a Physis já foi aprovada."
    intencoes = (("ranquear", r"edital|editai|chamada|fomento|grant"),)

    def _responder(self, pedido: dict) -> dict:
        lista = pedido.get("editais")
        if lista is None and self.ctx.get("editais") is not None:
            lista = self.ctx["editais"].ler_cache().get("itens", [])
        lista = [e for e in (lista or []) if isinstance(e, dict) and (e.get("titulo") or e.get("resumo"))]
        if not lista:
            raise ValueError("nenhum edital para ordenar")
        aceitos = [a for a in (pedido.get("aceitos") or []) if isinstance(a, dict)]
        hoje = str(pedido.get("hoje") or datetime.fromtimestamp(self.agora(), clima_mod.FUSO).strftime("%Y-%m-%d"))
        textos_aceitos = [f"{a.get('titulo', '')} {a.get('resumo', '')}" for a in aceitos]
        textos = [f"{e.get('titulo', '')} {e.get('resumo', '')}" for e in lista]
        idx = IndiceTFIDF([PERFIL_PHYSIS] + textos_aceitos + textos)     # IDF com tudo junto
        perfil = idx.vetores[0]
        vac = idx.vetores[1:1 + len(aceitos)]
        out = []
        for e, t in zip(lista, textos):
            v = idx.vetor(t)
            s_perfil = idx.cosseno(v, perfil)
            sims = [idx.cosseno(v, a) for a in vac]
            s_aceito = max(sims) if sims else None
            item = dict(e)
            item.setdefault("areas", editais_mod.areas_de(t))
            item.setdefault("prazo", editais_mod.prazo_de(editais_mod.extrair_datas(t)))
            regra = editais_mod.relevancia(item, hoje)
            sim = 0.5 * s_perfil + 0.5 * s_aceito if s_aceito is not None else s_perfil
            nota = round(100 * (0.6 * min(1.0, sim * 2) + 0.4 * min(1.0, regra / 35)))
            vencido = bool(item.get("prazo")) and item["prazo"] < hoje
            if vencido:
                nota = 0
            motivos = []
            if item["areas"]:
                motivos.append("áreas da Physis: " + ", ".join(item["areas"]))
            if s_aceito is not None and sims:
                k = max(range(len(sims)), key=lambda i: sims[i])
                if sims[k] >= 0.15:
                    motivos.append(f"parecido com \"{aceitos[k].get('titulo', '')[:80]}\" (aprovado antes)")
            if vencido:
                motivos.append(f"prazo já passou ({item['prazo']})")
            elif item.get("prazo"):
                motivos.append(f"prazo {item['prazo']}")
            out.append({"id": e.get("id"), "titulo": e.get("titulo"), "link": e.get("link"), "nota": nota,
                        "semelhanca_perfil": round(s_perfil, 3), "semelhanca_aceitos": _r3(s_aceito), "regra": regra,
                        "prazo": item.get("prazo"), "areas": item["areas"], "motivos": motivos})
        out.sort(key=lambda x: (-x["nota"], x["prazo"] or "9999"))
        top = [f"{i + 1}. {x['titulo']} — nota {x['nota']} ({'; '.join(x['motivos']) or 'pouca relação com a Physis'})" for i, x in enumerate(out[:5])]
        texto = "Editais mais alinhados à Physis:\n" + "\n".join(top)
        resumos = {(e.get("id"), e.get("titulo")): str(e.get("resumo") or "") for e in lista}
        material = "\n".join(f"[{i + 1}] {x['titulo']} — nota {x['nota']}; prazo {x['prazo'] or '?'}; "
                             f"resumo: {resumos.get((x['id'], x['titulo']), '')[:800]}" for i, x in enumerate(out[:5]))
        texto, ia = self.melhorar(texto, f"Perfil: {PERFIL_PHYSIS}\n\n{material}",
                                  "Para cada edital, faça um resumo de 2 linhas e diga o encaixe com o perfil da Physis "
                                  "(forte, médio ou fraco, e por quê). Mantenha a ordem e as notas. É sugestão, não decisão.")
        return resposta(self.nome, texto, fontes=[{"fonte": "perfil Physis (áreas de editais.py)"}] +
                        ([{"fonte": f"{len(aceitos)} editais aprovados antes"}] if aceitos else []),
                        confianca=0.8 if aceitos else 0.6, revisao_humana=True, ia=ia, dados={"ranking": out, "sugestao": True})


def _r3(v):
    return None if v is None else round(v, 3)


# ── 4. Marketing ────────────────────────────────────────────────────────────────────────────────
def nota_regra_tema(t: dict, hoje: str) -> float:
    """A mesma conta de nota() da Gestão → Marketing (tendência, interesse, votos; -3 se usado há menos de 14 dias)."""
    usado = False
    if t.get("usadoEm"):
        try:
            dias = (datetime.strptime(str(t["usadoEm"])[:10], "%Y-%m-%d") - datetime.strptime(hoje, "%Y-%m-%d")).days
            usado = dias > -14
        except ValueError:
            usado = False
    n = 0.4 * float(t.get("tendencia") or 0) + 0.3 * float(t.get("interesse") or 0) + 0.3 * min(10.0, float(t.get("votos") or 0) * 2) - (3 if usado else 0)
    return round(n, 1)


class Marketing(Robo):
    nome, titulo = "marketing", "Marketing"
    descricao = "Aprende quais temas engajam mais (atualização bayesiana Beta-Binomial) e junta com a nota da Gestão."
    intencoes = (("temas", r"tema|post|marketing|engaj|public"),)
    FORCA_PRIORI = 100.0          # quantas "impressões imaginárias" a média geral vale no começo
    PESO_AREA = 0.3               # métricas de outro tema da mesma área contam 30%

    def _responder(self, pedido: dict) -> dict:
        temas = [t for t in (pedido.get("temas") or []) if isinstance(t, dict) and t.get("tema")]
        if not temas:
            raise ValueError("falta a lista de temas")
        hoje = str(pedido.get("hoje") or datetime.fromtimestamp(self.agora(), clima_mod.FUSO).strftime("%Y-%m-%d"))
        met = [m for m in (pedido.get("metricas") or []) if isinstance(m, dict)]
        def imp(m):
            return float(m.get("impressoes") or m.get("alcance") or 0)
        def eng(m):
            if m.get("engajamentos") is not None:
                return float(m["engajamentos"])
            return float(sum(m.get(k) or 0 for k in ("curtidas", "comentarios", "compartilhamentos", "salvos", "cliques")))
        ti, te = sum(imp(m) for m in met), sum(eng(m) for m in met)
        taxa = te / ti if ti else 0.03
        a0, b0 = 1 + taxa * self.FORCA_PRIORI, 1 + (1 - taxa) * self.FORCA_PRIORI
        por_id = {str(t.get("id") or t["tema"]): t for t in temas}
        nome_id = {normalizar(t["tema"]): k for k, t in por_id.items()}
        acum = {k: [0.0, 0.0] for k in por_id}        # engajamentos, impressões do próprio tema
        area = Counter(), Counter()
        for m in met:
            k = str(m.get("tema_id") or "") or nome_id.get(normalizar(m.get("tema") or ""), "")
            if k in acum:
                acum[k][0] += eng(m)
                acum[k][1] += imp(m)
                ar = por_id[k].get("area")
            else:
                ar = m.get("area")
            if ar:
                area[0][ar] += eng(m)
                area[1][ar] += imp(m)
        out = []
        for k, t in por_id.items():
            e, i = acum[k]
            ar = t.get("area")
            ea, ia = area[0][ar] - e, area[1][ar] - i
            a = a0 + e + self.PESO_AREA * ea
            b = b0 + (i - e) + self.PESO_AREA * max(0.0, ia - ea)
            media = a / (a + b)
            dp = math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))
            out.append({"id": k, "tema": t["tema"], "area": ar, "taxa_esperada": round(media, 4),
                        "intervalo_90": [round(max(0, media - 1.645 * dp), 4), round(media + 1.645 * dp, 4)],
                        "impressoes": i, "engajamentos": e, "nota_regra": nota_regra_tema(t, hoje), "pouco_testado": i < 500})
        maior = max(x["taxa_esperada"] for x in out) or 1.0
        for x in out:
            x["nota_aprendida"] = round(10 * x["taxa_esperada"] / maior, 1)
            x["nota_final"] = round(0.5 * x["nota_regra"] + 0.5 * x["nota_aprendida"], 1)
        out.sort(key=lambda x: (-x["nota_final"], x["tema"]))
        linhas = [f"Taxa média de engajamento: {100 * taxa:.1f}% ({int(ti)} impressões)."] + [
            f"{n + 1}. {x['tema']} — nota {x['nota_final']} (regra {x['nota_regra']}, aprendida {x['nota_aprendida']}; "
            f"engaja ~{100 * x['taxa_esperada']:.1f}%{', pouco testado: vale experimentar' if x['pouco_testado'] else ''})"
            for n, x in enumerate(out[:5])]
        return resposta(self.nome, "\n".join(linhas), fontes=[{"fonte": "métricas de engajamento informadas"}, {"fonte": "nota() da Gestão → Marketing"}],
                        confianca=min(1.0, ti / 5000) if ti else 0.2, revisao_humana=False, dados={"ranking": out, "taxa_geral": round(taxa, 4)})


# ── 5. Esboço de projeto ────────────────────────────────────────────────────────────────────────
MODELOS_AREA = {
    "energia": {"obj": "reduzir o consumo e o custo de energia com eficiência e geração solar",
                "ativ": ["diagnóstico energético com as contas dos últimos 12 meses", "dimensionamento solar (SustainKit)", "monitoramento do consumo"],
                "ind": ["kWh economizados por ano", "kWp instalados", "tCO2e evitadas"]},
    "agua": {"obj": "garantir água em quantidade e qualidade, com reúso e captação de chuva",
             "ativ": ["balanço hídrico do lugar", "projeto de captação e reúso", "medição de vazão e qualidade (pH)"],
             "ind": ["m³ de água economizados", "% de reúso", "parâmetros de qualidade dentro da norma"]},
    "clima": {"obj": "medir e reduzir emissões e aumentar a resiliência climática",
              "ativ": ["inventário de emissões", "mapa de riscos climáticos do lugar", "plano de adaptação"],
              "ind": ["tCO2e inventariadas e reduzidas", "riscos com plano de resposta"]},
    "agro": {"obj": "aumentar a produtividade com menos água e insumos",
             "ativ": ["sensores de umidade do solo e irrigação automática", "previsão local de chuva", "boas práticas e agrofloresta"],
             "ind": ["litros de água por hectare", "produtividade por hectare", "produtores atendidos"]},
    "inovacao": {"obj": "levar tecnologia de monitoramento (IoT) a quem ainda não tem",
                 "ativ": ["instalação da rede de sensores LoRa", "plataforma Physis com dados offline", "validação em campo (TRL)"],
                 "ind": ["dispositivos instalados", "disponibilidade da rede (%)", "TRL alcançado"]},
    "sustentabilidade": {"obj": "estruturar a gestão ambiental e a economia circular",
                         "ativ": ["análise de lacunas para certificação", "plano de resíduos", "relatório de indicadores"],
                         "ind": ["toneladas de resíduo desviadas do aterro", "requisitos atendidos"]},
    "construcao": {"obj": "melhorar o desempenho de edificações (energia, conforto e água)",
                   "ativ": ["avaliação de climatização (AVAC)", "modelo BIM e simulação", "recomendações de retrofit"],
                   "ind": ["kWh/m² por ano", "horas de conforto térmico"]},
    "capacitacao": {"obj": "formar pessoas para usar e manter as soluções",
                    "ativ": ["cursos curtos na plataforma Physis", "oficinas práticas em campo", "material didático aberto"],
                    "ind": ["pessoas capacitadas", "% de aprovação nas avaliações"]},
}
FASES = (("Mapear", 0.2, "levantamento do lugar, dados e linha de base"), ("Modelar", 0.3, "cálculos, projeto e plano"),
         ("Checar", 0.35, "implantação, medição e ajustes"), ("Documentar", 0.15, "relatório, indicadores e divulgação"))
RUBRICAS = (("Equipe técnica", 0.45), ("Equipamentos e materiais", 0.25), ("Serviços de terceiros", 0.10),
            ("Capacitação e divulgação", 0.10), ("Viagens", 0.05), ("Despesas administrativas", 0.05))


class Projetos(Robo):
    nome, titulo = "projetos", "Esboço de projeto"
    descricao = "Monta o esqueleto de um projeto a partir de um edital e dos modelos da Physis"
    intencoes = (("projeto", r"projeto|proposta|edital|esboco|roteiro"),)
    sistema_ia = ("Você ajuda a Physis Engineering a escrever projetos para editais. Português do Brasil, técnico e claro. "
                  "Não invente números, parceiros nem resultados: deixe [A PREENCHER] onde faltar dado.")

    def _responder(self, pedido: dict) -> dict:
        e = pedido.get("edital") if isinstance(pedido.get("edital"), dict) else {}
        titulo = str(e.get("titulo") or pedido.get("pergunta") or "").strip()
        if not titulo:
            raise ValueError("falta o edital (titulo e resumo)")
        texto_ed = f"{titulo} {e.get('resumo', '')}"
        areas = [a for a in (e.get("areas") or editais_mod.areas_de(texto_ed)) if a in MODELOS_AREA] or ["sustentabilidade"]
        meses = int(e.get("duracao_meses") or 12)
        valor = e.get("valor_max")
        prazo = e.get("prazo") or editais_mod.prazo_de(editais_mod.extrair_datas(texto_ed))
        secoes = [
            {"titulo": "1. Título", "itens": [f"[A PREENCHER] — proposta para \"{titulo[:120]}\""]},
            {"titulo": "2. Contexto e justificativa", "itens": ["Problema do território e público atendido [A PREENCHER]",
                                                                 "Por que a Physis: experiência em " + ", ".join(areas)]},
            {"titulo": "3. Objetivo geral", "itens": ["Contribuir para " + "; ".join(MODELOS_AREA[a]["obj"] for a in areas)]},
            {"titulo": "4. Objetivos específicos", "itens": [a for ar in areas for a in MODELOS_AREA[ar]["ativ"]]},
            {"titulo": "5. Metodologia (caminho Physis)", "itens": [f"{n}: {d}" for n, _, d in FASES]},
            {"titulo": "6. Metas e indicadores", "itens": [i for ar in areas for i in MODELOS_AREA[ar]["ind"]]},
            {"titulo": f"7. Cronograma ({meses} meses)", "itens": _cronograma(meses)},
            {"titulo": "8. Orçamento", "itens": [f"{r}: {int(p * 100)}%" + (f" ≈ R$ {valor * p:,.2f}" if isinstance(valor, (int, float)) else "")
                                                 for r, p in RUBRICAS]},
            {"titulo": "9. Equipe e parceiros", "itens": ["Coordenação técnica [A PREENCHER]", "Parceiros locais [A PREENCHER]"]},
            {"titulo": "10. Riscos e como lidar", "itens": ["Atraso de equipamentos: compra no 1º trimestre", "Clima: cronograma de campo fora da época de chuva",
                                                             "Adesão do público: capacitação desde o início"]},
            {"titulo": "11. Continuidade", "itens": ["Dados ficam no computador central do lugar (funciona sem internet)", "Equipe local capacitada"]},
        ]
        pendencias = ["Conferir critérios de elegibilidade e pontuação do edital", "Contrapartida exigida", "Documentos da instituição",
                      "Valores reais do orçamento"] + ([] if prazo else ["Prazo de envio (não encontrado no texto)"])
        rascunho = "\n".join(f"{s['titulo']}\n" + "\n".join(f"  - {i}" for i in s["itens"]) for s in secoes)
        texto, ia = self.melhorar(rascunho, texto_ed[:3000], "Melhore a redação do roteiro mantendo a estrutura e os [A PREENCHER].")
        return resposta(self.nome, texto, fontes=[{"fonte": "edital informado"}, {"fonte": "modelos de área da Physis"}],
                        confianca=0.5, revisao_humana=True, ia=ia,
                        dados={"secoes": secoes, "areas": areas, "prazo": prazo, "pendencias": pendencias})


def _cronograma(meses: int) -> list[str]:
    out, ini = [], 1
    for i, (n, p, _) in enumerate(FASES):
        dur = max(1, round(meses * p)) if i < len(FASES) - 1 else max(1, meses - ini + 1)
        fim = min(meses, ini + dur - 1)
        out.append(f"{n}: meses {ini} a {fim}" if fim > ini else f"{n}: mês {ini}")
        ini = min(meses, fim + 1)
    return out


# ── 6. Pluviômetro ──────────────────────────────────────────────────────────────────────────────
PINOS = {
    # placa: (bons para interrupção com pull-up interno, só entrada sem pull-up, proibidos com motivo)
    "esp32": ({4, 13, 14, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33}, {34, 35, 36, 39},
              {0: "pino de boot", 1: "serial (TX)", 2: "pino de boot e LED", 3: "serial (RX)", 5: "pino de boot",
               6: "memória flash", 7: "memória flash", 8: "memória flash", 9: "memória flash", 10: "memória flash",
               11: "memória flash", 12: "pino de boot (tensão da flash)", 15: "pino de boot"}),
    "esp8266": ({4, 5, 12, 13, 14}, set(), {0: "pino de boot", 1: "serial (TX)", 2: "pino de boot", 3: "serial (RX)",
                                           15: "pino de boot", 16: "não tem interrupção"}),
}
MM_POR_PULSO = 0.2794           # báscula comum de 0,011 polegada; calibrar com água medida


def _gpio(v) -> int:
    m = re.fullmatch(r"(?:gpio)?\s*(\d{1,2})", str(v).strip().lower())
    if not m:
        raise ValueError("pino deve ser um número de GPIO (ex.: 27 ou GPIO27)")
    return int(m.group(1))


def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", normalizar(s)).strip("-")
    return (s or "pluviometro")[:24]


class Pluviometro(Robo):
    nome, titulo = "pluviometro", "Pluviômetro"
    descricao = "Gera o YAML do ESPHome e o cadastro no hub para um pluviômetro de báscula, a partir do lugar e do pino."
    intencoes = (("gerar", r"pluvi|bascula|chuva medida|esphome"),)

    def _responder(self, pedido: dict) -> dict:
        d = pedido.get("dados") if isinstance(pedido.get("dados"), dict) else pedido
        placa = str(d.get("placa") or "esp32").lower()
        if placa not in PINOS:
            raise ValueError("placa deve ser esp32 ou esp8266")
        no = int(d.get("no") or 0)
        if not 1 <= no <= 99:
            raise ValueError("número do nó (ID) de 1 a 99, único no lugar")
        loc, erro = clima_mod.validar_local(d)
        if not loc:
            raise ValueError(erro)
        pino = _gpio(d.get("pino", 27))
        bons, so_entrada, proibidos = PINOS[placa]
        avisos = []
        if pino in proibidos:
            raise ValueError(f"GPIO{pino} não serve: {proibidos[pino]}")
        if pino in so_entrada:
            avisos.append(f"GPIO{pino} não tem pull-up interno: ponha um resistor de 10 kΩ do pino ao 3,3 V")
        elif pino not in bons:
            raise ValueError(f"GPIO{pino} não existe ou não é recomendado na {placa}")
        mm = float(d.get("mm_por_pulso") or MM_POR_PULSO)
        if not 0.05 <= mm <= 2.0:
            raise ValueError("mm por pulso fora do normal (0,05 a 2 mm)")
        intervalo = int(d.get("intervalo_s") or 300)
        intervalo = max(60, min(3600, intervalo))
        hub_url = str(d.get("hub_url") or "http://physis-hub.local:8700").rstrip("/")
        if not re.fullmatch(r"https?://[A-Za-z0-9.-]+(:\d{1,5})?", hub_url):
            raise ValueError("endereço do hub inválido (ex.: http://192.168.0.10:8700)")
        nome = _slug(d.get("nome") or f"pluviometro-{no:02d}")
        yaml = yaml_pluviometro(nome, placa, pino, pino in so_entrada, mm, intervalo, hub_url, no, loc)
        linha = f"ID:{no:02d},TIPO:PLUV,CHI:0.00,PUL:0,BAT:-,TS:1794600000"
        texto = (f"Pluviômetro \"{nome}\" (nó {no:02d}) na {placa.upper()}, báscula no GPIO{pino}, {mm} mm por pulso, "
                 f"mandando a chuva ao hub a cada {intervalo // 60} min. "
                 + (" ".join(avisos) + ". " if avisos else "")
                 + "Atenção: o hub ainda não aceita TIPO:PLUV — ver a proposta em docs/ROBOS.md antes de instalar.")
        return resposta(self.nome, texto, fontes=[{"fonte": "docs/EXTENSAO_V6.md"}, {"fonte": "docs/ROBOS.md § TIPO:PLUV"}],
                        confianca=0.9, revisao_humana=True,
                        dados={"arquivo": f"{nome}.yaml", "yaml": yaml, "secrets": SECRETS_EXEMPLO, "avisos": avisos,
                               "registro_hub": {"local": loc, "no": no, "tipo": "PLUV", "linha_exemplo": linha,
                                                "observacao_diaria": "soma de CHI do dia → clima.observar(dia, 'physis', mm)"}})


SECRETS_EXEMPLO = "wifi_ssid: \"[rede]\"\nwifi_senha: \"[senha]\"\nota_senha: \"[senha]\"\n"


def yaml_pluviometro(nome, placa, pino, pull_externo, mm, intervalo, hub_url, no, loc) -> str:
    placa_yaml = "esp32:\n  board: esp32dev\n  framework:\n    type: arduino" if placa == "esp32" else "esp8266:\n  board: d1_mini"
    pull = "" if pull_externo else "\n      pullup: true"
    fator = round(mm * intervalo / 60.0, 6)          # pulse_counter dá pulsos/minuto; isto vira mm no intervalo
    return f"""# Pluviômetro de báscula Physis — gerado pelo robô Pluviômetro (revisar antes de gravar)
# Lugar: {loc.get('municipio') or '-'} {loc.get('uf') or ''} ({loc['lat']}, {loc['lon']}) · nó {no:02d}
# Ligação: um fio da báscula no GPIO{pino}, o outro no GND.{' Resistor de 10 kΩ do GPIO ao 3,3 V.' if pull_externo else ''}
esphome:
  name: {nome}
  comment: "Pluviometro Physis no {no:02d}"

{placa_yaml}

logger:
ota:
  - platform: esphome
    password: !secret ota_senha

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_senha

time:
  - platform: sntp
    id: relogio

http_request:
  timeout: 10s

sensor:
  - platform: pulse_counter
    id: chuva_intervalo
    name: "Chuva no intervalo"
    pin:
      number: GPIO{pino}
      inverted: true
      mode:
        input: true{pull}
    use_pcnt: false
    internal_filter: 50ms          # a báscula "quica" ao virar
    count_mode:
      rising_edge: INCREMENT
      falling_edge: DISABLE
    update_interval: {intervalo}s
    unit_of_measurement: mm
    accuracy_decimals: 2
    filters:
      - multiply: {fator}           # {mm} mm por pulso
    total:
      id: pulsos_total
      name: "Pulsos desde que ligou"

interval:
  - interval: {intervalo}s
    then:
      - http_request.post:
          url: {hub_url}/api/v6/linha
          request_headers:
            Content-Type: text/plain
          body: !lambda |-
            char b[120];
            auto t = id(relogio).now();
            float chi = isnan(id(chuva_intervalo).state) ? 0.0f : id(chuva_intervalo).state;
            snprintf(b, sizeof(b), "ID:{no:02d},TIPO:PLUV,CHI:%.2f,PUL:%u,BAT:-,TS:%lu", chi,
                     (unsigned) id(pulsos_total).state, (unsigned long) (t.is_valid() ? t.timestamp : 0));
            return std::string(b);
"""


# ══ Registro dos robôs e roteamento ═════════════════════════════════════════════════════════════
CLASSES = {c.nome: c for c in (Suporte, Precos, Editais, Marketing, Projetos, Pluviometro)}


def criar_robos(contexto: dict | None = None, ia=None) -> dict[str, Robo]:
    if ia is None:
        ctx = contexto or {}
        para = os.environ.get("PHYSIS_CLAUDE_AVISO_EMAIL") or ctx.get("suporte_email") or ""
        ia = ia_do_ambiente(avisar=claude_mod.aviso_por_email(ctx["hub"], para) if ctx.get("hub") is not None else None)
    return {n: c(contexto, ia) for n, c in CLASSES.items()}


def listar(robos: dict[str, Robo]) -> list[dict]:
    return [{"nome": r.nome, "titulo": r.titulo, "descricao": r.descricao, "ia_local": r.ia.ativa, "ia": r.ia.tipo}
            for r in robos.values()]


def rotear(texto: str, robos: dict[str, Robo]) -> str:
    """Qual robô atende um texto livre (regras de intenção); sem acerto, o suporte."""
    for nome in ("pluviometro", "precos", "editais", "marketing", "projetos"):
        if nome in robos and robos[nome].intencao(texto):
            return nome
    return "suporte"


def atender(nome: str, pedido: dict, robos: dict[str, Robo]) -> tuple[int, dict]:
    """Para a rota POST /api/robos/<nome>: (código HTTP, resposta)."""
    if nome == "auto":
        nome = rotear(str((pedido or {}).get("pergunta") or ""), robos)
    r = robos.get(nome)
    if r is None:
        return 404, {"ok": False, "erro": "robô desconhecido", "robos": sorted(robos)}
    out = r.responder(pedido or {})
    return (200 if out.get("ok") else 400), out
