"""Logica do hub: recebe linhas V6, guarda, adapta, acompanha comandos.

Sem dependencia fora da biblioteca padrao. O banco e SQLite; um arquivo por
lugar. O registro do lugar e uma cadeia: cada entrada guarda o resumo da
anterior, entao alterar uma linha antiga quebra a verificacao.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from collections import Counter, deque
from datetime import datetime, timedelta
from pathlib import Path

from . import adaptador, protocolo
from . import clima as clima_mod
from . import integridade
from . import perfil_cliente
from . import secador as secador_mod
from . import seguranca as seg

OFFLINE_S_PADRAO = 160          # 3 ciclos do TDMA com 99 nos (~53 s cada)
LINHAS_PARA_CONFIRMAR = 3       # leituras do no ate declarar "nao confirmado"
BAT_BAIXA_V = 3.5
NIVEL_RACAO_BAIXO = 15.0
INSTANCIA_PADRAO = Path(__file__).resolve().parent.parent / "instancia.json"
LOCAL_NAO_INFORMADO = "local não informado"


def terreno_do_planejador(texto: str | None) -> dict:
    """Lote mapeado no Planejador (cliente_estado "physis.terreno.v1", schema physis.terreno/1.0) → {lat, lon, municipio,
    uf, poligono [[lon, lat], …], area_m2}. O Planejador guarda o polígono em metros locais (x leste, y norte) a partir de
    terreno.lat0/lon0; a conversão para graus é a mesma de sistema/physis-sbn.js (mapa GIS): 110.540 m por grau de
    latitude e 111.320 × cos(lat0) m por grau de longitude. lat/lon = lat0/lon0 (o ponto de referência do lote)."""
    try:
        s = json.loads(texto) if texto else None
    except ValueError:
        s = None
    if not isinstance(s, dict):
        return {}
    t, m, i = (s.get(k) if isinstance(s.get(k), dict) else {} for k in ("terreno", "meta", "inicio"))
    lat0 = t.get("lat0") if t.get("lat0") is not None else i.get("lat")
    lon0 = t.get("lon0") if t.get("lon0") is not None else i.get("lon")
    out = {"lat": lat0, "lon": lon0, "municipio": m.get("municipio") or "", "uf": m.get("uf") or ""}
    poly = t.get("poly")
    try:
        la0, lo0 = float(lat0), float(lon0)
        pts = [(float(p[0]), float(p[1])) for p in poly] if isinstance(poly, list) else []
    except (TypeError, ValueError, IndexError):
        pts = []
    if len(pts) > 2:
        a = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:] + pts[:1])) / 2
        kx = 111320 * math.cos(math.radians(la0))
        out["poligono"] = [[round(lo0 + x / kx, 7), round(la0 + y / 110540, 7)] for x, y in pts]
        out["area_m2"] = round(abs(a), 1)
    return out


def ler_instancia() -> dict:
    """instancia.json desta instalação (PHYSIS_INSTANCIA troca o arquivo), com as mesmas regras de servidor.ler_instancia."""
    try:
        return json.loads(Path(os.environ.get("PHYSIS_INSTANCIA") or INSTANCIA_PADRAO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS leitura (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, no INTEGER NOT NULL, ts INTEGER NOT NULL,
  recebido REAL NOT NULL, origem TEXT NOT NULL, linha TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS leitura_unica ON leitura(no, ts) WHERE ts > 0;
CREATE TABLE IF NOT EXISTS medicao (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, leitura INTEGER NOT NULL, topico TEXT NOT NULL,
  grandeza TEXT NOT NULL, ativo TEXT NOT NULL, valor REAL NOT NULL, ts INTEGER NOT NULL,
  alarme TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS medicao_ativo ON medicao(ativo, grandeza, seq);
CREATE TABLE IF NOT EXISTS registro (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL, tipo TEXT NOT NULL,
  quando REAL NOT NULL, origem TEXT NOT NULL, conteudo TEXT NOT NULL,
  anterior TEXT NOT NULL, resumo TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS comando (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, linha TEXT NOT NULL, destino INTEGER NOT NULL,
  estado TEXT NOT NULL, criado REAL NOT NULL, atualizado REAL NOT NULL,
  restam INTEGER NOT NULL, detalhe TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS conta (
  id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, usuario TEXT NOT NULL UNIQUE,
  papel TEXT NOT NULL, sal BLOB NOT NULL, resumo BLOB NOT NULL, criado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessao (
  resumo TEXT PRIMARY KEY, conta INTEGER NOT NULL, expira REAL NOT NULL, criado REAL NOT NULL DEFAULT 0,
  ip TEXT NOT NULL DEFAULT '', agente TEXT NOT NULL DEFAULT '', visto REAL NOT NULL DEFAULT 0, reauth REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS central (
  tipo TEXT NOT NULL, numero TEXT NOT NULL, dados TEXT NOT NULL, estado TEXT NOT NULL,
  criado REAL NOT NULL, atualizado REAL NOT NULL, PRIMARY KEY (tipo, numero));
CREATE TABLE IF NOT EXISTS central_arquivo (
  id TEXT PRIMARY KEY, pedido TEXT NOT NULL, nome TEXT NOT NULL, tamanho INTEGER NOT NULL,
  dados BLOB NOT NULL, criado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS gestao_estado (
  chave TEXT PRIMARY KEY, valor TEXT NOT NULL, versao INTEGER NOT NULL, atualizado REAL NOT NULL, por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS gestao_arquivo (
  id TEXT PRIMARY KEY, nome TEXT NOT NULL, tipo TEXT NOT NULL, dados BLOB NOT NULL, tamanho INTEGER NOT NULL,
  criado REAL NOT NULL, por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS instalacao (
  numero TEXT PRIMARY KEY, compra TEXT NOT NULL UNIQUE, org TEXT NOT NULL, nome TEXT NOT NULL,
  email TEXT NOT NULL, modulos TEXT NOT NULL, sal BLOB NOT NULL, resumo BLOB NOT NULL, pacote TEXT,
  criado REAL NOT NULL, ativado REAL, erros INTEGER NOT NULL DEFAULT 0, bloqueado_ate REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS email_saida (
  id INTEGER PRIMARY KEY AUTOINCREMENT, para TEXT NOT NULL, assunto TEXT NOT NULL, corpo TEXT NOT NULL,
  estado TEXT NOT NULL, ref TEXT NOT NULL, criado REAL NOT NULL, enviado REAL, erro TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS loja_item (
  id TEXT PRIMARY KEY, dados TEXT NOT NULL, revisado TEXT, publicado TEXT, atualizado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS envio (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, registro INTEGER NOT NULL, enviado INTEGER NOT NULL DEFAULT 0);
"""


def _resumo(anterior: str, tipo: str, quando: float, origem: str, conteudo: str) -> str:
    base = "|".join((anterior, tipo, f"{quando:.6f}", origem, conteudo))
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


class Hub:
    def __init__(self, caminho: str = ":memory:", org: str = "org-teste", lugar: str = "lugar01",
                 offline_s: int = OFFLINE_S_PADRAO, guardar_medicoes: bool = True,
                 enviar_comando=None, relogio=time.time):
        self.org, self.lugar = org, lugar
        self.offline_s = offline_s
        self.guardar_medicoes = guardar_medicoes
        self.enviar_comando = enviar_comando      # funcao(linha) -> (ok, detalhe) ou None
        self.saude_receptor = None                # funcao(linha, origem) -> dict de saude.registrar_evento (o servidor liga)
        self.frota_receptor = None                # funcao(est, ts, linha) do frota.py para cada linha VEI aceita (o servidor liga)
        self.secador_produtos: dict[int, str] = {}  # no SEC -> produto do lote (secador.PRODUTOS); vazio = limite generico
        self.relogio = relogio
        self.instancia: dict | None = None        # instancia.json (lido na primeira vez que for preciso; testes podem pôr o dict)
        self.SESSAO_S = seg.sessao_vida_s(Hub.SESSAO_S)      # PHYSIS_SESSAO_DIAS (vida máxima da sessão)
        self._trava = threading.RLock()
        self._db = sqlite3.connect(caminho, check_same_thread=False)
        self._db.executescript(ESQUEMA)
        # migração: contas ganham a pessoa da equipe a que pertencem e podem ser desativadas
        cols = {r[1] for r in self._db.execute("PRAGMA table_info(conta)")}
        if "pessoa" not in cols:
            self._db.execute("ALTER TABLE conta ADD COLUMN pessoa TEXT NOT NULL DEFAULT ''")
        if "ativa" not in cols:
            self._db.execute("ALTER TABLE conta ADD COLUMN ativa INTEGER NOT NULL DEFAULT 1")
        # segurança: a sessão passa a ser guardada só como resumo SHA-256 do token. As sessões antigas
        # (token em texto) são descartadas: quem estava dentro entra de novo uma vez.
        if "token" in {r[1] for r in self._db.execute("PRAGMA table_info(sessao)")}:
            self._db.execute("DROP TABLE sessao")
            self._db.executescript(ESQUEMA)
        self._db.executescript(perfil_cliente.ESQUEMA)     # dados da plataforma do cliente (antes só no navegador)
        integridade.preparar(self._db)  # lotes de dados conferidos (fonte da verdade; blockchain é só adicional)
        seg.preparar(self._db)          # chaves dos dispositivos e registro de acessos
        self._db.commit()
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self.nos: dict[int, dict] = {}
        self.descartes: Counter = Counter()
        self.contagem: Counter = Counter()
        self.ultimas_descartadas: deque = deque(maxlen=20)
        linha = self._db.execute("SELECT resumo FROM registro ORDER BY seq DESC LIMIT 1").fetchone()
        self._ultimo_resumo = linha[0] if linha else "0" * 64

    # ── Registro do lugar ────────────────────────────────────────────────────
    def registrar(self, tipo: str, origem: str, conteudo: dict) -> str:
        with self._trava:
            quando = self.relogio()
            texto = json.dumps(conteudo, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            resumo = _resumo(self._ultimo_resumo, tipo, quando, origem, texto)
            ident = resumo[:16]
            cur = self._db.execute(
                "INSERT INTO registro(id,tipo,quando,origem,conteudo,anterior,resumo) VALUES(?,?,?,?,?,?,?)",
                (ident, tipo, quando, origem, texto, self._ultimo_resumo, resumo))
            self._db.execute("INSERT INTO envio(registro) VALUES(?)", (cur.lastrowid,))
            self._ultimo_resumo = resumo
            return ident

    def verificar_cadeia(self) -> tuple[bool, int]:
        """(integra, quantidade). Recalcula todos os resumos na ordem."""
        with self._trava:
            anterior, n = "0" * 64, 0
            for tipo, quando, origem, conteudo, ant, resumo in self._db.execute(
                    "SELECT tipo,quando,origem,conteudo,anterior,resumo FROM registro ORDER BY seq"):
                if ant != anterior or _resumo(anterior, tipo, quando, origem, conteudo) != resumo:
                    return False, n
                anterior, n = resumo, n + 1
            return True, n

    # ── Entrada de telemetria ────────────────────────────────────────────────
    def receber_lote(self, corpo: str, origem: str = "receptor") -> dict:
        """Corpo text/plain com uma linha V6 por linha, como o receptor envia."""
        aceitas = duplicadas = descartadas = 0
        with self._trava:
            for bruta in corpo.split("\n"):
                if not bruta.strip():
                    continue
                r = self._receber_linha(bruta, origem)
                if r == "aceita":
                    aceitas += 1
                elif r == "duplicada":
                    duplicadas += 1
                else:
                    descartadas += 1
            self._db.commit()
        return {"ok": True, "aceitas": aceitas, "duplicadas": duplicadas, "descartadas": descartadas}

    def _receber_linha(self, bruta: str, origem: str) -> str:
        self.contagem["recebidas"] += 1
        ok, motivo, campos = protocolo.validar_telemetria(bruta)
        if not ok:
            self.descartes[motivo] += 1
            self.ultimas_descartadas.append({"motivo": motivo, "linha": bruta[:160]})
            return "descartada"
        if campos.get("TIPO", "").strip().upper() in protocolo.TIPOS_SAUDE:
            return self._receber_saude(bruta, origem)     # dado de saúde: antes do adaptador, nunca em `medicao`
        if campos.pop("_FORA", None):
            self.descartes["campo_fora_da_faixa"] += 1   # so o campo foi descartado; a leitura segue
        linha = protocolo.limpar_linha(bruta)
        est = adaptador.interpretar(campos)
        no, ts, agora = est["id"], est["ts"], self.relogio()
        if not (protocolo.EPOCH_MIN_VALIDO <= ts <= protocolo.EPOCH_MAX_VALIDO):
            ts = 0                      # no sem relogio: nao ha como deduplicar
        intervalo = None                # pluviometro: segundos desde a linha anterior do mesmo no (intensidade em mm/h)
        antes = self.nos.get(no)
        if est["tipo"] == "PLUV" and antes and antes.get("tipo") == "PLUV":
            ts_antes = antes.get("ts") or 0
            if ts and protocolo.EPOCH_MIN_VALIDO <= ts_antes <= protocolo.EPOCH_MAX_VALIDO:
                intervalo = ts - ts_antes
            elif not ts:
                intervalo = agora - antes["visto"]
        try:
            cur = self._db.execute(
                "INSERT INTO leitura(no,ts,recebido,origem,linha) VALUES(?,?,?,?,?)",
                (no, ts, agora, origem, linha))
        except sqlite3.IntegrityError:
            self.contagem["duplicadas"] += 1
            return "duplicada"
        self.contagem["aceitas"] += 1
        if self.guardar_medicoes:
            campos_ts = dict(campos)
            campos_ts["TS"] = str(ts)
            self._db.executemany(
                "INSERT INTO medicao(leitura,topico,grandeza,ativo,valor,ts,alarme) VALUES(?,?,?,?,?,?,?)",
                [(cur.lastrowid, m["topico"], m["grandeza"], m["ativo"], m["valor"], m["ts"], m["alarme"])
                 for m in adaptador.adaptar(campos_ts, self.org, self.lugar, intervalo)])
            if est["tipo"] == "PLUV" and est.get("chi") is not None:
                self._chuva_do_dia(ts or agora)
        if est["tipo"] == "VEI" and self.frota_receptor is not None:
            try:                        # frota (docs/FROTA.md): ponto de GPS e sensores do veículo ligado ao nó
                self.frota_receptor(est, ts or agora, linha)
            except Exception:           # noqa: BLE001 — um defeito na frota não derruba a telemetria
                self.descartes["frota_erro"] += 1
        self._atualizar_no(est, agora, linha)
        return "aceita"

    def _chuva_do_dia(self, quando: float) -> None:
        """Soma do CHI do dia (fuso de Brasília) -> clima_observado origem "physis": o placar das fontes de
        previsão e o modelo de chuva (aprendizado.py) passam a usar a chuva medida no próprio lugar."""
        d = datetime.fromtimestamp(quando, clima_mod.FUSO)
        ini = datetime(d.year, d.month, d.day, tzinfo=clima_mod.FUSO).timestamp()
        mm, _ = clima_mod.chuva_do_periodo(self._db, ini, ini + 86400)
        if mm is not None:
            clima_mod.observar_no_banco(self._db, d.strftime("%Y-%m-%d"), "physis", mm, self.relogio())

    def _receber_saude(self, bruta: str, origem: str) -> str:
        """MED/PUL (docs/SAUDE.md): vão para a Saúde (consentimento, autorização, avisos). Sem o módulo ligado
        neste servidor (saude_receptor), a linha é descartada. A linha crua não vai para o painel (dado sensível)."""
        motivo = "saude_sem_modulo"
        if self.saude_receptor is not None:
            try:
                r = self.saude_receptor(protocolo.limpar_linha(bruta), origem) or {}
            except Exception:          # noqa: BLE001 — um defeito na Saúde não derruba a telemetria
                r = {"ok": False, "motivo": "erro"}
            if r.get("ok"):
                self.contagem["saude"] += 1
                return "duplicada" if r.get("duplicada") else "aceita"
            motivo = "saude_" + str(r.get("motivo") or "recusada")
        self.descartes[motivo] += 1
        self.ultimas_descartadas.append({"motivo": motivo, "linha": "[linha de saúde: não mostrada]"})
        return "descartada"

    def _atualizar_no(self, est: dict, agora: float, linha: str) -> None:
        no = est["id"]
        antes = self.nos.get(no)
        novo = dict(est)
        novo.update({"visto": agora, "linha": linha,
                     "pacotes": (antes["pacotes"] + 1) if antes else 1})
        for chave in ("rssi", "snr"):          # nao medido nesta linha: preserva
            if novo.get(chave) is None and antes:
                novo[chave] = antes.get(chave)
        self.nos[no] = novo
        if antes is None:
            self.registrar("no_descoberto", f"no{no:02d}", {"no": no, "tipo": est["tipo"]})
        else:
            for chave, nome in (("ir1", "valvula1"), ("ir2", "valvula2"), ("bomba", "bomba"), ("imp", "impacto"),
                                ("vent", "ventilador")):
                if chave in est and bool(antes.get(chave)) != bool(est.get(chave)):
                    self.registrar("evento", f"no{no:02d}", {"no": no, "o_que": nome, "valor": bool(est.get(chave))})
        self._conferir_comandos(no, est)

    # ── Comandos ─────────────────────────────────────────────────────────────
    def comandar(self, linha: str, autor: str = "painel") -> dict:
        ok, destino, normal = protocolo.comando_valido(linha)
        if not ok:
            self.contagem["comandos_recusados"] += 1
            return {"ok": False, "erro": "comando fora do contrato"}
        with self._trava:
            agora = self.relogio()
            estado, detalhe = "pendente", ""
            if self.enviar_comando is not None:
                try:
                    enviado, detalhe = self.enviar_comando(normal)
                except Exception as exc:        # receptor fora do ar nao derruba o hub
                    enviado, detalhe = False, f"falha ao enviar: {exc}"
                estado = "enviado" if enviado else "falhou"
            cur = self._db.execute(
                "INSERT INTO comando(linha,destino,estado,criado,atualizado,restam,detalhe) VALUES(?,?,?,?,?,?,?)",
                (normal, destino, estado, agora, agora, LINHAS_PARA_CONFIRMAR, detalhe))
            self.registrar("comando", autor, {"linha": normal, "estado": estado})
            self._db.commit()
            return {"ok": estado != "falhou", "id": cur.lastrowid, "comando": normal, "estado": estado,
                    "detalhe": detalhe}

    def comandos_pendentes(self, no: int | None = None, marcar_enviado: bool = True) -> list[str]:
        """Para quem entrega o comando sem o receptor (no Wi-Fi ou simulador)."""
        with self._trava:
            sql = "SELECT seq, linha FROM comando WHERE estado='pendente'"
            args: tuple = ()
            if no is not None:
                sql += " AND destino IN (?, 0)"
                args = (no,)
            linhas = self._db.execute(sql + " ORDER BY seq", args).fetchall()
            if marcar_enviado and linhas:
                self._db.executemany("UPDATE comando SET estado='enviado', atualizado=? WHERE seq=?",
                                     [(self.relogio(), s) for s, _ in linhas])
                self._db.commit()
            return [l for _, l in linhas]

    def _conferir_comandos(self, no: int, est: dict) -> None:
        abertos = self._db.execute(
            "SELECT seq, linha, restam FROM comando WHERE estado='enviado' AND destino=?", (no,)).fetchall()
        for seq, linha, restam in abertos:
            _, acao, arg = protocolo.separar_comando(linha)
            alvo = {"LIM1": "lim1", "LIM2": "lim2", "IRR1": "ir1", "IRR2": "ir2", "VENT": "vent"}.get(acao)
            if alvo is None:                    # SYNC, MODO, PING: a linha do no nao confirma
                self._db.execute("UPDATE comando SET estado='sem_confirmacao', atualizado=? WHERE seq=?",
                                 (self.relogio(), seq))
                continue
            atual = est.get(alvo)
            if acao.startswith("LIM"):
                bateu = atual is not None and abs(atual - float(arg)) < 0.051
            else:
                bateu = atual is not None and bool(atual) == (arg == "1")
            if bateu:
                novo = "confirmado"
            elif restam <= 1:
                novo = "nao_confirmado"
            else:
                self._db.execute("UPDATE comando SET restam=? WHERE seq=?", (restam - 1, seq))
                continue
            self._db.execute("UPDATE comando SET estado=?, atualizado=? WHERE seq=?", (novo, self.relogio(), seq))
            self.registrar("comando", f"no{no:02d}", {"linha": linha, "estado": novo})

    # ── Leitura para as telas ────────────────────────────────────────────────
    def alertas(self) -> list[dict]:
        agora, out, chuva = self.relogio(), [], False
        for no, n in sorted(self.nos.items()):
            nome = f"No {no:02d}"
            if agora - n["visto"] > self.offline_s:
                out.append({"nivel": "alarme", "no": no, "texto": f"{nome} sem falar ha {int(agora - n['visto'])} s"})
                continue
            if n.get("bat") is not None and n["bat"] < BAT_BAIXA_V:
                out.append({"nivel": "atencao", "no": no, "texto": f"{nome} com bateria baixa ({n['bat']:.2f} V)"})
            if n["tipo"] == "SOLO" and n.get("media") is None:
                out.append({"nivel": "alarme", "no": no, "texto": f"{nome} sem leitura de solo"})
            if n["tipo"] == "ZONA" and n.get("bomba") and not (n.get("ir1") or n.get("ir2")):
                out.append({"nivel": "alarme", "no": no, "texto": f"{nome}: bomba ligada sem valvula aberta"})
            if n["tipo"] == "COL" and n.get("imp"):
                out.append({"nivel": "alarme", "no": no, "texto": f"{nome}: impacto detectado na coleira"})
            if n["tipo"] == "COM" and n.get("niv") is not None and n["niv"] < NIVEL_RACAO_BAIXO:
                out.append({"nivel": "atencao", "no": no, "texto": f"{nome}: racao em {n['niv']:.0f} %"})
            if n["tipo"] == "SEC":       # secador solar (docs/SECADOR.md): produto do lote, se a instalacao disser
                if chuva is False:
                    with self._trava:
                        chuva = secador_mod.chuva_prevista(self._db, agora)
                prod = self.secador_produtos.get(no)
                out += [{"nivel": nv, "no": no, "texto": f"{nome}: {tx}"} for nv, tx in secador_mod.alertas(n, prod, chuva)]
        return out

    def painel(self) -> dict:
        with self._trava:
            agora = self.relogio()
            nos = []
            for no, n in sorted(self.nos.items()):
                d = {k: v for k, v in n.items() if k != "linha"}
                d["online"] = agora - n["visto"] <= self.offline_s
                d["ha_s"] = int(agora - n["visto"])
                d["linha"] = n["linha"]
                nos.append(d)
            comandos = [dict(zip(("id", "linha", "destino", "estado", "detalhe"), r)) for r in self._db.execute(
                "SELECT seq,linha,destino,estado,detalhe FROM comando ORDER BY seq DESC LIMIT 20")]
            registro = [dict(zip(("id", "tipo", "quando", "origem", "conteudo"), r)) for r in self._db.execute(
                "SELECT id,tipo,quando,origem,conteudo FROM registro ORDER BY seq DESC LIMIT 40")]
            pend = self._db.execute("SELECT COUNT(*) FROM envio WHERE enviado=0").fetchone()[0]
            return {
                "org": self.org, "lugar": self.lugar, "agora": agora, "nos": nos,
                "alertas": self.alertas(), "comandos": comandos, "registro": registro,
                "saude": {"contagem": dict(self.contagem), "descartes": dict(self.descartes),
                          "ultimas_descartadas": list(self.ultimas_descartadas),
                          "fila_envio": pend},
            }

    def serie(self, ativo: str, grandeza: str, limite: int = 200) -> list[dict]:
        with self._trava:
            linhas = self._db.execute(
                "SELECT ts, valor, alarme FROM medicao WHERE ativo=? AND grandeza=? ORDER BY seq DESC LIMIT ?",
                (ativo, grandeza, limite)).fetchall()
        return [{"ts": t, "valor": v, "alarme": a} for t, v, a in reversed(linhas)]

    def leituras(self, limite: int = 1000, no: int | None = None) -> list[dict]:
        """Historico das leituras aceitas, da mais nova para a mais antiga (tela Registros e download)."""
        limite = max(1, min(int(limite), 20000))
        with self._trava:
            if no is None:
                linhas = self._db.execute("SELECT no, ts, recebido, linha FROM leitura ORDER BY seq DESC LIMIT ?", (limite,)).fetchall()
            else:
                linhas = self._db.execute("SELECT no, ts, recebido, linha FROM leitura WHERE no=? ORDER BY seq DESC LIMIT ?", (int(no), limite)).fetchall()
        return [{"no": n, "ts": t, "recebido": r, "linha": l} for n, t, r, l in linhas]

    def fila_envio(self, limite: int = 500) -> list[dict]:
        """Registros ainda nao confirmados pelo servidor (store-and-forward)."""
        with self._trava:
            return [dict(zip(("seq", "id", "tipo", "quando", "origem", "conteudo", "resumo"), r))
                    for r in self._db.execute(
                        "SELECT e.seq, r.id, r.tipo, r.quando, r.origem, r.conteudo, r.resumo "
                        "FROM envio e JOIN registro r ON r.seq = e.registro WHERE e.enviado=0 "
                        "ORDER BY e.seq LIMIT ?", (limite,))]

    def marcar_enviados(self, ate_seq: int) -> None:
        with self._trava:
            self._db.execute("UPDATE envio SET enviado=1 WHERE seq<=?", (ate_seq,))
            self._db.commit()

    # ── Contas e sessoes (acesso local da instalacao) ───────────────────────
    # Senha nunca e guardada: so o resumo PBKDF2-SHA256 com sal por conta.
    ITERACOES = 240_000
    SENHA_MIN = seg.SENHA_MIN          # 12; política completa em seguranca.senha_fraca (lista de senhas comuns)
    SESSAO_S = 30 * 24 * 3600

    @staticmethod
    def _resumir(senha: str, sal: bytes) -> bytes:
        return hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, Hub.ITERACOES)

    def tem_conta(self) -> bool:
        with self._trava:
            return self._db.execute("SELECT COUNT(*) FROM conta").fetchone()[0] > 0

    def _eh_admin(self, autor: int | None) -> bool:
        r = self._db.execute("SELECT papel, ativa FROM conta WHERE id=?", (autor or -1,)).fetchone()
        return bool(r) and r[0] == "administrador" and bool(r[1])

    def criar_conta(self, nome: str, usuario: str, senha: str, autor: int | None = None,
                    pessoa: str = "", papel: str = "operador") -> dict:
        """A primeira conta e criada por quem abre a instalacao e vira administradora; as demais, por um administrador.

        Com PHYSIS_DOMINIO_EMAIL definido (ex.: physisengineering.com), as contas novas precisam ser e-mails desse dominio."""
        nome, usuario = (nome or "").strip(), (usuario or "").strip().lower()
        if not nome or not usuario:
            return {"ok": False, "erro": "Informe o nome e o usuario."}
        erro = seg.senha_fraca(senha, usuario)
        if erro:
            return {"ok": False, "erro": erro}
        dominio = (os.environ.get("PHYSIS_DOMINIO_EMAIL") or "").strip().lower().lstrip("@")
        if dominio and not usuario.endswith("@" + dominio):
            return {"ok": False, "erro": f"Use um e-mail @{dominio}."}
        papel = seg.normalizar_papel(papel)          # aceita também "direção", "equipe" e "cliente"
        if not papel:
            return {"ok": False, "erro": "Papel invalido."}
        with self._trava:
            primeira = not self.tem_conta()
            if not primeira and not self._eh_admin(autor):
                return {"ok": False, "erro": "So um administrador cria novas contas."}
            papel = "administrador" if primeira else papel
            sal = os.urandom(16)
            try:
                # a primeira conta (dona da instalação, criada da rede local) nasce confirmada; as criadas pela
                # direção confirmam o e-mail pelo link (seguranca.confirmar_enviar), quando a confirmação é exigida
                cur = self._db.execute("INSERT INTO conta(nome,usuario,papel,sal,resumo,criado,pessoa,confirmado) VALUES(?,?,?,?,?,?,?,?)",
                                       (nome, usuario, papel, sal, self._resumir(senha, sal), self.relogio(), (pessoa or "")[:40],
                                        self.relogio() if primeira else None))
            except sqlite3.IntegrityError:
                return {"ok": False, "erro": "Ja existe uma conta com esse usuario."}
            self._db.commit()
            self.registrar("conta", usuario, {"o_que": "conta criada", "papel": papel, "pessoa": pessoa or ""})
            self._db.commit()
            return {"ok": True, "primeira": primeira, "id": cur.lastrowid}

    def contas(self) -> list[dict]:
        with self._trava:
            linhas = self._db.execute("SELECT nome, usuario, papel, pessoa, ativa, criado, confirmado, totp_ativo FROM conta ORDER BY nome").fetchall()
        return [{"nome": n, "usuario": u, "papel": p, "pessoa": pe, "ativa": bool(a), "criado": c, "email_confirmado": cf is not None,
                 "dois_fatores": bool(t)} for n, u, p, pe, a, c, cf, t in linhas]

    def alterar_conta(self, autor: int | None, usuario: str, *, senha: str | None = None, ativa: bool | None = None,
                      papel: str | None = None, pessoa: str | None = None) -> dict:
        """Só administrador. Desativar ou trocar a senha encerra as sessões abertas da conta."""
        usuario = (usuario or "").strip().lower()
        with self._trava:
            if not self._eh_admin(autor):
                return {"ok": False, "erro": "So um administrador altera contas."}
            alvo = self._db.execute("SELECT id, papel FROM conta WHERE usuario=?", (usuario,)).fetchone()
            if not alvo:
                return {"ok": False, "erro": "Conta nao encontrada."}
            if papel is not None and not seg.normalizar_papel(papel):
                return {"ok": False, "erro": "Papel invalido."}
            papel = seg.normalizar_papel(papel) if papel is not None else None
            if alvo[0] == autor and (ativa is False or (papel is not None and papel != seg.DIRECAO)):
                return {"ok": False, "erro": "Voce nao pode desativar nem rebaixar a propria conta."}
            if senha is not None:
                erro = seg.senha_fraca(senha, usuario)
                if erro:
                    return {"ok": False, "erro": erro}
                sal = os.urandom(16)
                self._db.execute("UPDATE conta SET sal=?, resumo=? WHERE id=?", (sal, self._resumir(senha, sal), alvo[0]))
            if ativa is not None:
                self._db.execute("UPDATE conta SET ativa=? WHERE id=?", (1 if ativa else 0, alvo[0]))
            if papel is not None:
                self._db.execute("UPDATE conta SET papel=? WHERE id=?", (papel, alvo[0]))
            if pessoa is not None:
                self._db.execute("UPDATE conta SET pessoa=? WHERE id=?", (pessoa[:40], alvo[0]))
            if senha is not None or ativa is False:
                self._db.execute("DELETE FROM sessao WHERE conta=?", (alvo[0],))
            self.registrar("conta", usuario, {"o_que": "conta alterada", "senha": senha is not None, "ativa": ativa, "papel": papel, "pessoa": pessoa})
            self._db.commit()
            return {"ok": True}

    def trocar_senha(self, conta_id: int, atual: str, nova: str) -> dict:
        with self._trava:
            r = self._db.execute("SELECT usuario, sal, resumo FROM conta WHERE id=?", (conta_id,)).fetchone()
            if not r or not hmac.compare_digest(self._resumir(atual or "", r[1]), r[2]):
                return {"ok": False, "erro": "A senha atual nao confere."}
            erro = seg.senha_fraca(nova, r[0])
            if erro:
                return {"ok": False, "erro": erro}
            sal = os.urandom(16)
            self._db.execute("UPDATE conta SET sal=?, resumo=? WHERE id=?", (sal, self._resumir(nova, sal), conta_id))
            self.registrar("conta", r[0], {"o_que": "senha trocada pela propria pessoa"})
            self._db.commit()
            return {"ok": True}

    # ── Dados da Gestão Physis no servidor ────────────────────────────────────
    # Cada parte da Gestão (atividades, painel administrativo, reuniões, documentos...) é guardada como
    # um texto JSON por chave, com número de versão. Quem grava informa a versão em que se baseou; se outra
    # pessoa gravou antes, o servidor recusa (conflito) e devolve a versão atual, e a tela junta as duas.
    GESTAO_CHAVE = re.compile(r"^gestao-physis:[A-Za-z0-9_.:-]{1,80}$")
    GESTAO_VALOR_MAX = 8 * 1024 * 1024
    GESTAO_ARQ_MAX = 20 * 1024 * 1024

    def gestao_ler(self, desde: float = 0.0) -> dict:
        with self._trava:
            linhas = self._db.execute("SELECT chave, valor, versao, atualizado, por FROM gestao_estado WHERE atualizado > ?", (desde,)).fetchall()
        return {c: {"valor": v, "versao": n, "atualizado": a, "por": p} for c, v, n, a, p in linhas}

    def gestao_gravar(self, chave: str, valor: str, versao_base: int, por: str) -> dict:
        if not self.GESTAO_CHAVE.match(chave or ""):
            return {"ok": False, "erro": "chave invalida"}
        if not isinstance(valor, str) or len(valor.encode("utf-8")) > self.GESTAO_VALOR_MAX:
            return {"ok": False, "erro": "valor invalido ou grande demais"}
        with self._trava:
            r = self._db.execute("SELECT valor, versao, por, atualizado FROM gestao_estado WHERE chave=?", (chave,)).fetchone()
            atual = r[1] if r else 0
            if int(versao_base or 0) != atual:
                return {"ok": False, "conflito": True, "valor": r[0] if r else None, "versao": atual, "por": r[2] if r else ""}
            if r and r[0] == valor:
                return {"ok": True, "versao": atual, "igual": True}
            agora = max(self.relogio(), (r[3] if r else 0) + 1e-6)
            self._db.execute("INSERT INTO gestao_estado(chave,valor,versao,atualizado,por) VALUES(?,?,?,?,?) "
                             "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor, versao=excluded.versao, atualizado=excluded.atualizado, por=excluded.por",
                             (chave, valor, atual + 1, agora, por))
            self.registrar("gestao", por, {"o_que": "gravou", "chave": chave, "versao": atual + 1, "bytes": len(valor)})
            self._db.commit()
            return {"ok": True, "versao": atual + 1, "atualizado": agora}

    def gestao_arquivo_por(self, ident: str, nome: str, tipo: str, dados: bytes, por: str) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_-]{4,80}", ident or ""):
            return {"ok": False, "erro": "identificador invalido"}
        if not dados or len(dados) > self.GESTAO_ARQ_MAX:
            return {"ok": False, "erro": "arquivo vazio ou maior que 20 MB"}
        nome = (nome or "arquivo").replace("\\", "/").rsplit("/", 1)[-1][:120]
        if seg.eh_executavel(dados):
            return {"ok": False, "erro": "arquivo executável não é aceito"}
        tipo = seg.tipo_seguro(tipo, nome)
        with self._trava:
            self._db.execute("INSERT OR REPLACE INTO gestao_arquivo(id,nome,tipo,dados,tamanho,criado,por) VALUES(?,?,?,?,?,?,?)",
                             (ident, nome, tipo, dados, len(dados), self.relogio(), por))
            self.registrar("gestao", por, {"o_que": "arquivo guardado", "id": ident, "nome": nome, "bytes": len(dados)})
            self._db.commit()
            return {"ok": True}

    def gestao_arquivo(self, ident: str) -> tuple[str, str, bytes] | None:
        with self._trava:
            r = self._db.execute("SELECT nome, tipo, dados FROM gestao_arquivo WHERE id=?", (ident,)).fetchone()
        return (r[0], r[1], bytes(r[2])) if r else None

    def gestao_arquivo_apagar(self, ident: str, por: str) -> bool:
        with self._trava:
            cur = self._db.execute("DELETE FROM gestao_arquivo WHERE id=?", (ident,))
            if cur.rowcount:
                self.registrar("gestao", por, {"o_que": "arquivo apagado", "id": ident})
            self._db.commit()
            return cur.rowcount > 0

    # ── Dados da plataforma do cliente no servidor (perfil_cliente.py; ponte sistema/physis-ponte-cliente.js) ──
    def cliente_ler(self, org: str | None = None, desde: float = 0.0, chave: str | None = None) -> dict:
        """{chave: {valor, versao, atualizado, por}} da organização (padrão: a desta instalação)."""
        org = org or self.org
        with self._trava:
            if chave is not None:
                linhas = self._db.execute("SELECT chave, valor, versao, atualizado, por FROM cliente_estado WHERE org=? AND chave=?",
                                          (org, chave)).fetchall()
            else:
                linhas = self._db.execute("SELECT chave, valor, versao, atualizado, por FROM cliente_estado WHERE org=? AND atualizado > ?",
                                          (org, desde)).fetchall()
        return {c: {"valor": v, "versao": n, "atualizado": a, "por": p} for c, v, n, a, p in linhas}

    def cliente_gravar(self, chave: str, valor, versao_base: int, por: str, org: str | None = None) -> dict:
        """Grava com controle de versão. Versão base diferente da atual = conflito (devolve a atual)."""
        org = org or self.org
        if not perfil_cliente.chave_valida(chave):
            return {"ok": False, "erro": "chave nao permitida"}
        if not isinstance(valor, str):
            return {"ok": False, "erro": "valor precisa ser texto"}
        tam = len(valor.encode("utf-8"))
        if tam > perfil_cliente.VALOR_MAX:
            return {"ok": False, "erro": "valor grande demais", "grande": True}
        with self._trava:
            r = self._db.execute("SELECT valor, versao, por, atualizado FROM cliente_estado WHERE org=? AND chave=?", (org, chave)).fetchone()
            atual = r[1] if r else 0
            if int(versao_base or 0) != atual:
                return {"ok": False, "conflito": True, "valor": r[0] if r else None, "versao": atual, "por": r[2] if r else "",
                        "atualizado": r[3] if r else None}
            if r and r[0] == valor:
                return {"ok": True, "versao": atual, "igual": True, "atualizado": r[3]}
            soma, n = self._db.execute("SELECT COALESCE(SUM(LENGTH(CAST(valor AS BLOB))),0), COUNT(*) FROM cliente_estado "
                                       "WHERE org=? AND chave<>?", (org, chave)).fetchone()
            if soma + tam > perfil_cliente.TOTAL_MAX or (not r and n >= perfil_cliente.CHAVES_MAX):
                return {"ok": False, "erro": "espaço da organização no servidor esgotado", "grande": True}
            agora = max(self.relogio(), (r[3] if r else 0) + 1e-6)
            self._db.execute("INSERT INTO cliente_estado(org,chave,valor,versao,atualizado,por) VALUES(?,?,?,?,?,?) "
                             "ON CONFLICT(org,chave) DO UPDATE SET valor=excluded.valor, versao=excluded.versao, "
                             "atualizado=excluded.atualizado, por=excluded.por", (org, chave, valor, atual + 1, agora, por))
            # o registro guarda só metadados (o conteúdo é da organização)
            self.registrar("cliente", por, {"o_que": "gravou", "chave": chave, "versao": atual + 1, "bytes": tam})
            self._db.commit()
            return {"ok": True, "versao": atual + 1, "atualizado": agora}

    def cliente_aprendido(self, org: str | None = None) -> dict:
        """Atividades do negócio aprendidas da descrição (physis-perfil guardado no servidor)."""
        v = self.cliente_ler(org, chave="physis-perfil").get("physis-perfil")
        r = perfil_cliente.aprendido_do_perfil(v["valor"] if v else None)
        r["atualizado"] = v["atualizado"] if v else None
        return r

    # ── Local da instalação (lacuna 2 do mapa de variáveis, 15/11/2026) ─────────────────────────
    def _inst(self) -> dict:
        if self.instancia is None:
            self.instancia = ler_instancia()
        return self.instancia

    def local_da_instalacao(self) -> dict:
        """O local do cliente, numa função só, para previsão/CEMADEN, Resiliência, Solar, Secador, AVAC (clima e cidade),
        SbN (bioma e região), Economia circular e Carbono. Fonte da verdade (pedido de 15/11/2026):

        geometria (lat, lon, polígono, área): 1. o lote mapeado no Planejador (physis.terreno.v1: lat0/lon0 + polígono, mais
           rico); 2. o cadastro obrigatório do Início (physis-perfil.c.lat/lon); 3. o local gravado no Monitoramento
           (/api/clima/local, tabela clima_local, por compatibilidade); 4. o instancia.json ("local", só padrão do instalador).
        município e UF: Início > Planejador > Monitoramento > instancia.json. Estação do CEMADEN e IBGE: Monitoramento >
           instancia.json > Início.
        Sem coordenadas: fonte "nao_informado", lat e lon None, e quem usa diz "local não informado" (nunca um ponto padrão).
        CEP (obrigatório no Início desde 15/11/2026) e fonte_coordenadas: "cep" (aproximado, do CEP), "mapa" (marcado no
        mapa), "digitado", ou a fonte da geometria (planejador, monitoramento, instalacao). Ponto do mapa ou digitado vale
        sobre o do CEP (a tela grava assim).
        Devolve {lat, lon, municipio, uf, ibge, cep, cemaden_estacao, poligono, area_m2, fonte, fonte_coordenadas, fontes}."""
        with self._trava:
            try:
                r = self._db.execute("SELECT dados FROM clima_local WHERE id=1").fetchone()
            except sqlite3.Error:
                r = None
            est = dict(self._db.execute("SELECT chave, valor FROM cliente_estado WHERE org=? AND chave IN "
                                        "('physis-perfil','physis.terreno.v1')", (self.org,)).fetchall())

        def ler(txt):
            try:
                v = json.loads(txt) if txt else None
                return v if isinstance(v, dict) else {}
            except ValueError:
                return {}
        mon = ler(r[0]) if r else {}
        c = ler(est.get("physis-perfil")).get("c") or {}
        c = c if isinstance(c, dict) else {}
        ter = terreno_do_planejador(est.get("physis.terreno.v1"))
        inst = self._inst().get("local")
        inst = inst if isinstance(inst, dict) else {}
        perfil = {"lat": c.get("lat", c.get("latitude")), "lon": c.get("lon", c.get("longitude")),
                  "municipio": c.get("municipio"), "uf": c.get("uf"), "ibge": c.get("ibge")}
        geo = [("planejador", ter), ("inicio", perfil), ("monitoramento", mon), ("instalacao", inst)]
        out = {"lat": None, "lon": None, "municipio": "", "uf": "", "ibge": "", "cep": "", "cemaden_estacao": "", "poligono": None,
               "area_m2": None, "fonte": "nao_informado", "fonte_coordenadas": None, "fontes": {}}
        _cep = re.sub(r"\D", "", str(c.get("cep") or ""))
        if len(_cep) == 8:
            out["cep"] = _cep[:5] + "-" + _cep[5:]
        for fonte, d in geo:
            if d.get("lat") in (None, "") or d.get("lon") in (None, ""):
                continue
            ponto = lambda v: v.strip().replace(",", ".") if isinstance(v, str) else v   # o Início grava "-22,505"
            loc, _ = clima_mod.validar_local({"lat": ponto(d.get("lat")), "lon": ponto(d.get("lon"))})
            if loc:
                out.update(lat=loc["lat"], lon=loc["lon"], fonte=fonte)
                break
        if ter.get("poligono"):
            out["poligono"], out["area_m2"], out["fontes"]["area"] = ter["poligono"], ter["area_m2"], "planejador"
        elif isinstance(c.get("area_total_ha"), (int, float, str)) and str(c.get("area_total_ha")).strip():
            try:
                out["area_m2"], out["fontes"]["area"] = float(str(c["area_total_ha"]).replace(",", ".")) * 10000, "inicio"
            except ValueError:
                pass
        for campo, ordem in (("municipio", [("inicio", perfil), ("planejador", ter), ("monitoramento", mon), ("instalacao", inst)]),
                             ("uf", [("inicio", perfil), ("planejador", ter), ("monitoramento", mon), ("instalacao", inst)]),
                             ("ibge", [("monitoramento", mon), ("instalacao", inst), ("inicio", perfil)]),
                             ("cemaden_estacao", [("monitoramento", mon), ("instalacao", inst)])):
            for fonte, d in ordem:
                v = str(d.get(campo) or "").strip()
                if v:
                    out[campo] = v.upper()[:2] if campo == "uf" else v[:80]
                    out["fontes"][campo] = fonte
                    break
        if out["fonte"] != "nao_informado":
            out["fontes"]["coordenadas"] = out["fonte"]
            fc = str(c.get("fonte_coordenadas") or "").strip()
            out["fonte_coordenadas"] = (fc if fc in ("cep", "mapa", "digitado") else "digitado") if out["fonte"] == "inicio" else out["fonte"]
        return out

    # ── Lote diário de integridade (ruptura R6; docs/INTEGRIDADE_DADOS.md) ─────────────────────────
    LOTE_HORA = 3          # fecha o dia anterior a partir das 3 h (mesma janela do treino diário)

    def lote_diario_ligado(self) -> bool:
        """PHYSIS_LOTE_DIARIO=0 desliga; instancia.json {"integridade": {"lote_diario": false}} também."""
        if os.environ.get("PHYSIS_LOTE_DIARIO", "1").strip() == "0":
            return False
        cfg = self._inst().get("integridade")
        return not (isinstance(cfg, dict) and cfg.get("lote_diario") is False)

    def fechar_lote_diario(self, hora: int | None = None) -> dict:
        """Fecha (uma vez) o lote do dia anterior com os registros validados. Chamado pelo laço diário do hub
        (aprendizado.rodar → passo_diario); repetir não duplica. Fuso de Brasília, como o resto do hub."""
        if not self.lote_diario_ligado():
            return {"ok": True, "desligado": True}
        agora = self.relogio()
        d = datetime.fromtimestamp(agora, clima_mod.FUSO)
        if d.hour < (self.LOTE_HORA if hora is None else hora):
            return {"ok": True, "cedo": True}
        ontem = (d - timedelta(days=1)).date()
        if getattr(self, "_lote_dia", None) == ontem:
            return {"ok": True, "repetido": True, "dia": ontem.isoformat()}
        self._lote_dia = ontem
        with self._trava:
            r = integridade.lote_diario(self._db, ontem.isoformat(), org=self.org, lugar=self.lugar, fuso=clima_mod.FUSO,
                                        fechado_em=datetime.fromtimestamp(agora, clima_mod.FUSO).isoformat(timespec="seconds"))
            if not r.get("repetido"):
                self.registrar("integridade", "hub", {k: v for k, v in r.items() if k != "ok"})
                self._db.commit()
        return r

    def entrar(self, usuario: str, senha: str, ip: str = "", agente: str = "", codigo: str | None = None) -> dict:
        usuario = (usuario or "").strip().lower()
        with self._trava:
            agora = self.relogio()
            falhas = getattr(self, "_falhas", {})
            self._falhas = falhas
            n, ate = falhas.get(usuario, (0, 0.0))
            if agora < ate:
                return {"ok": False, "erro": f"Muitas tentativas. Tente de novo em {int(ate - agora) + 1} s.", "espera": True}
            linha = self._db.execute("SELECT id, nome, papel, sal, resumo FROM conta WHERE usuario=? AND ativa=1", (usuario,)).fetchone()
            certo = bool(linha) and hmac.compare_digest(self._resumir(senha or "", linha[3]), linha[4])
            if certo and seg.totp_ligado(self, linha[0]):
                # verificação em duas etapas: sem código, pede o código (a senha certa não abre a sessão sozinha)
                if not codigo:
                    return {"ok": False, "precisa_2fa": True, "erro": "Digite o código do aplicativo autenticador."}
                certo = seg.segundo_fator(self, linha[0], codigo, usuario)
            if not certo:
                n += 1
                falhas[usuario] = (n, agora + 30 if n >= 5 else 0.0)
                return {"ok": False, "erro": "Usuario ou senha nao conferem." if not codigo else "Usuario, senha ou codigo nao conferem."}
            falhas.pop(usuario, None)
            token = secrets.token_urlsafe(32)          # vai só no cookie; o banco guarda o resumo SHA-256
            self._db.execute("DELETE FROM sessao WHERE expira < ?", (agora,))
            # entrar conta como autenticação recente (reauth): ações sensíveis valem por PHYSIS_REAUT_MIN depois do login
            self._db.execute("INSERT INTO sessao(resumo,conta,expira,criado,ip,agente,visto,reauth) VALUES(?,?,?,?,?,?,?,?)",
                             (seg.resumo(token), linha[0], agora + self.SESSAO_S, agora, (ip or "")[:64], (agente or "")[:200], agora, agora))
            self._db.commit()
            return {"ok": True, "token": token, "nome": linha[1], "papel": linha[2]}

    def sessao(self, token: str | None) -> dict | None:
        if not token:
            return None
        r_ = seg.resumo(token)
        with self._trava:
            agora = self.relogio()
            r = self._db.execute("SELECT c.id, c.nome, c.usuario, c.papel, c.pessoa, s.resumo, s.visto, s.reauth, c.confirmado, "
                                 "c.consentimento_versao, c.totp_ativo FROM sessao s JOIN conta c ON c.id = s.conta "
                                 "WHERE s.resumo=? AND s.expira > ? AND c.ativa=1", (r_, agora)).fetchone()
            if not r or not seg.iguais(r[5], r_):
                return None
            ociosa = seg.sessao_ociosa_s()
            if ociosa and r[6] and agora - r[6] > ociosa:          # parada tempo demais: cai
                self._db.execute("DELETE FROM sessao WHERE resumo=?", (r_,))
                self._db.commit()
                return None
            if agora - (r[6] or 0) > 60:                           # marca o uso sem gravar a cada pedido
                self._db.execute("UPDATE sessao SET visto=? WHERE resumo=?", (agora, r_))
                self._db.commit()
        q = dict(zip(("id", "nome", "usuario", "papel", "pessoa"), r[:5]))
        q.update(reauth=r[7] or 0.0, confirmado=(r[8] is not None) or not seg.confirmacao_exigida(),
                 consentimento=r[9] or "", dois_fatores=bool(r[10]))
        return q

    def sair(self, token: str | None) -> None:
        with self._trava:
            self._db.execute("DELETE FROM sessao WHERE resumo=?", (seg.resumo(token or ""),))
            self._db.commit()

    # ── Caixa central: o que a loja entrega e a gestao recebe, sem copiar e colar ──
    TIPOS_CENTRAL = ("compra", "pedido", "alocacao", "suporte")

    # ── Suporte ao cliente: cada mensagem vira um chamado, com e-mail para a Physis na fila de saída ──
    def suporte_abrir(self, dados: dict, quem: str, para: str, usuario: str = "") -> dict:
        assunto = str(dados.get("assunto") or "").strip()[:140]
        mensagem = str(dados.get("mensagem") or "").strip()[:4000]
        if not assunto or not mensagem:
            return {"ok": False, "erro": "assunto e mensagem são obrigatórios"}
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", para or ""):
            return {"ok": False, "erro": "e-mail de suporte da Physis não configurado"}
        contato = str(dados.get("contato") or "").strip()[:160]
        canal = "whatsapp" if dados.get("canal") == "whatsapp" else "email"
        with self._trava:
            seq = self._db.execute("SELECT COUNT(*) FROM central WHERE tipo='suporte'").fetchone()[0] + 1
        numero = "SP-%04d" % seq
        reg = {"assunto": assunto, "mensagem": mensagem, "contato": contato, "canal": canal, "quem": quem,
               "org": self.org, "lugar": self.lugar, "quando": self.relogio()}
        if usuario:
            reg["usuario"] = usuario
        r = self.central_por("suporte", numero, reg)
        if not r.get("ok"):
            return r
        corpo = "\n".join([f"Chamado {numero} · {self.org} ({self.lugar})", f"Quem: {quem or '—'} · contato: {contato or '—'} · canal preferido: {canal}",
                           f"Assunto: {assunto}", "", mensagem, "", "Responda pelo canal indicado. Mensagem enviada pela plataforma Physis."])
        with self._trava:
            self._db.execute("INSERT INTO email_saida(para,assunto,corpo,estado,ref,criado) VALUES(?,?,?,?,?,?)",
                             (para, f"Suporte {numero} · {assunto}", corpo, "pendente", numero, self.relogio()))
            self._db.commit()
        return {"ok": True, "numero": numero}

    def suporte_listar(self, usuario: str | None = None) -> list[dict]:
        """Todos os chamados; com usuario, só os que essa conta abriu (papel cliente).
        O cliente vê a situação e as respostas que a Physis mandou; as notas internas e o responsável, nunca."""
        out = []
        for x in self.central_listar():
            if x["tipo"] != "suporte" or not (usuario is None or x["dados"].get("usuario") == usuario):
                continue
            d = x["dados"]
            c = {"numero": x["numero"], "estado": x["estado"], "criado": x["criado"], "atualizado": x["atualizado"],
                 **{k: d.get(k) for k in ("assunto", "mensagem", "canal", "contato")},
                 "respostas": [{"quando": r.get("quando"), "texto": r.get("texto")} for r in d.get("respostas") or []]}
            if usuario is None:          # equipe
                c.update(responsavel=d.get("responsavel") or "", notas=len(d.get("notas") or []), usuario=d.get("usuario") or "",
                         quem=d.get("quem") or "", org=d.get("org") or "")
            out.append(c)
        return out

    # ── Caixa de chamados (equipe): situação, responsável, notas internas e resposta por e-mail ──
    SUPORTE_ESTADOS = {"novo": "novo", "em atendimento": "em_atendimento", "em_atendimento": "em_atendimento",
                       "atendimento": "em_atendimento", "resolvido": "resolvido"}
    SUPORTE_ESTADO_TEXTO = {"novo": "novo", "em_atendimento": "em atendimento", "resolvido": "resolvido"}
    _EMAIL_RE = re.compile(r"[^@\s,;<>()]+@[^@\s,;<>()]+\.[^@\s,;<>()]+")

    def suporte_detalhe(self, numero: str) -> dict | None:
        with self._trava:
            r = self._db.execute("SELECT dados, estado, criado, atualizado FROM central WHERE tipo='suporte' AND numero=?",
                                 (numero,)).fetchone()
        if not r:
            return None
        d = json.loads(r[0])
        return {"numero": numero, "estado": r[1], "estado_texto": self.SUPORTE_ESTADO_TEXTO.get(r[1], r[1]), "criado": r[2],
                "atualizado": r[3], **{k: d.get(k) for k in ("assunto", "mensagem", "contato", "canal", "quem", "usuario", "org", "lugar")},
                "responsavel": d.get("responsavel") or "", "notas": d.get("notas") or [], "respostas": d.get("respostas") or [],
                "historico": d.get("historico") or [], "email_cliente": self._email_do_chamado(d)}

    def _email_do_chamado(self, d: dict) -> str:
        for v in (d.get("usuario"), d.get("contato")):
            m = self._EMAIL_RE.search(str(v or ""))
            if m:
                return m.group(0)
        return ""

    def suporte_atualizar(self, numero: str, d: dict, quem: str) -> dict:
        """d: {estado?, responsavel?, nota?, resposta?: {texto, assunto?}}. A resposta vai para a fila email_saida
        (ref "<numero>-R<n>"); o servidor manda pelo correio.py. Devolve {ok, chamado, ref}."""
        if not isinstance(d, dict):
            return {"ok": False, "erro": "json invalido"}
        estado = d.get("estado")
        if estado is not None:
            estado = self.SUPORTE_ESTADOS.get(str(estado).strip().lower())
            if not estado:
                return {"ok": False, "erro": "situação: novo, em atendimento ou resolvido"}
        resp = d.get("resposta")
        if resp is not None and (not isinstance(resp, dict) or not str(resp.get("texto") or "").strip()):
            return {"ok": False, "erro": "a resposta precisa de texto"}
        with self._trava:
            r = self._db.execute("SELECT dados, estado FROM central WHERE tipo='suporte' AND numero=?", (numero,)).fetchone()
            if not r:
                return {"ok": False, "erro": "chamado desconhecido", "codigo": 404}
            dados, atual = json.loads(r[0]), r[1]
            agora, mudou, ref = self.relogio(), [], None
            if estado and estado != atual:
                dados.setdefault("historico", []).append({"quando": agora, "por": quem, "de": atual, "para": estado})
                atual = estado
                mudou.append("estado")
            if isinstance(d.get("responsavel"), str) and d["responsavel"].strip()[:120] != (dados.get("responsavel") or ""):
                dados["responsavel"] = d["responsavel"].strip()[:120]
                mudou.append("responsavel")
            if isinstance(d.get("nota"), str) and d["nota"].strip():
                dados.setdefault("notas", []).append({"quando": agora, "por": quem, "texto": d["nota"].strip()[:4000]})
                mudou.append("nota")
            if resp is not None:
                para = self._email_do_chamado(dados)
                if not para:
                    return {"ok": False, "erro": "o chamado não tem e-mail do cliente; responda pelo canal indicado (WhatsApp)"}
                texto = str(resp["texto"]).strip()[:8000]
                assunto = (str(resp.get("assunto") or "").strip()[:140] or f"Re: {dados.get('assunto') or 'seu chamado'}")
                n = len(dados.get("respostas") or []) + 1
                ref = f"{numero}-R{n}"
                corpo = "\n".join([f"Olá{', ' + dados['quem'] if dados.get('quem') else ''}.", "", texto, "",
                                   f"Chamado {numero} · situação: {self.SUPORTE_ESTADO_TEXTO.get(atual, atual)}.",
                                   "Você acompanha este chamado na sua plataforma Physis, em Suporte.", "", "Physis Engineering"])
                eid = self._db.execute("INSERT INTO email_saida(para,assunto,corpo,estado,ref,criado) VALUES(?,?,?,?,?,?)",
                                       (para, f"Suporte {numero} · {assunto}", corpo, "pendente", ref, agora)).lastrowid
                dados.setdefault("respostas", []).append({"quando": agora, "por": quem, "texto": texto, "email": eid})
                mudou.append("resposta")
            if not mudou:
                return {"ok": True, "igual": True, "chamado": self.suporte_detalhe(numero), "ref": None}
            self._db.execute("UPDATE central SET dados=?, estado=?, atualizado=? WHERE tipo='suporte' AND numero=?",
                             (json.dumps(dados, ensure_ascii=False), atual, agora, numero))
            self.registrar("central", numero, {"o_que": "chamado atualizado", "campos": mudou, "estado": atual, "quem": quem})
            self._db.commit()
        return {"ok": True, "chamado": self.suporte_detalhe(numero), "ref": ref}

    # ── Central de clientes (equipe): organizações a partir de compras, instalações e pedidos ──
    def central_clientes(self) -> list[dict]:
        """Uma ficha por organização: contato (dado pessoal: só equipe), módulos, instalação, compras, pedidos
        e chamados de suporte (quantos e em que situação). Junta pelo e-mail de contato."""
        itens = self.central_listar()
        fichas: dict[str, dict] = {}

        def ficha(chave: str, nome: str = "") -> dict:
            f = fichas.get(chave)
            if f is None:
                f = fichas[chave] = {"chave": chave, "org": "", "nome": nome, "contato": {"nome": "", "email": "", "telefone": "", "doc": ""},
                                     "modulos": [], "instalacoes": [], "compras": [], "pedidos": [],
                                     "chamados": {"total": 0, "abertos": 0, "novo": 0, "em_atendimento": 0, "resolvido": 0, "lista": []},
                                     "criado": None, "atualizado": None}
            return f

        def tocar(f: dict, criado, atualizado) -> None:
            if criado is not None:
                f["criado"] = criado if f["criado"] is None else min(f["criado"], criado)
            if atualizado is not None:
                f["atualizado"] = atualizado if f["atualizado"] is None else max(f["atualizado"], atualizado)

        def contato(f: dict, nome="", email="", telefone="", doc="") -> None:
            email = str(email or "").strip().lower()
            for k, v in (("nome", nome), ("email", email), ("telefone", telefone), ("doc", doc)):
                if v and not f["contato"][k]:
                    f["contato"][k] = str(v)[:160]

        def mods(f: dict, lista) -> None:
            for m in lista or []:
                if isinstance(m, str) and m not in f["modulos"]:
                    f["modulos"].append(m)

        por_email: dict[str, str] = {}
        por_compra: dict[str, str] = {}
        for i in self.instalacoes():
            chave = "org:" + i["org"]
            f = ficha(chave, i["nome"])
            f["org"] = i["org"]
            contato(f, i["nome"], i["email"])
            mods(f, i["modulos"])
            f["instalacoes"].append({"numero": i["numero"], "compra": i["compra"], "ativada": bool(i["ativado"]), "criado": i["criado"]})
            tocar(f, i["criado"], i["ativado"] or i["criado"])
            por_compra[i["compra"]] = chave
            if i["email"]:
                por_email.setdefault(i["email"].lower(), chave)
        for x in itens:
            if x["tipo"] != "compra":
                continue
            d, pag = x["dados"], (x["dados"].get("pagador") or {})
            email = str(pag.get("email") or "").strip().lower()
            chave = por_compra.get(x["numero"]) or por_email.get(email) or ("email:" + email if email else "compra:" + x["numero"])
            f = ficha(chave, str(pag.get("nome") or ""))
            contato(f, pag.get("nome"), email, pag.get("telefone"), pag.get("doc"))
            mods(f, self.modulos_do_contrato(d))
            f["compras"].append({"numero": x["numero"], "estado": x["estado"], "fatura": d.get("fatura"), "total": d.get("total"),
                                 "criado": x["criado"]})
            tocar(f, x["criado"], x["atualizado"])
            if email:
                por_email.setdefault(email, chave)
        for x in itens:
            if x["tipo"] != "pedido":
                continue
            d = x["dados"]
            email = str(d.get("email") or "").strip().lower()
            chave = por_email.get(email) or ("email:" + email if email else "pedido:" + x["numero"])
            f = ficha(chave, str(d.get("org") or d.get("nome") or ""))
            contato(f, d.get("nome"), email, d.get("telefone"), d.get("doc"))
            f["pedidos"].append({"numero": x["numero"], "estado": x["estado"], "origem": d.get("origem") or "loja", "criado": x["criado"]})
            tocar(f, x["criado"], x["atualizado"])
            if email:
                por_email.setdefault(email, chave)
        orgs = {f["org"]: k for k, f in fichas.items() if f["org"]}
        for x in itens:
            if x["tipo"] != "suporte":
                continue
            d = x["dados"]
            email = self._email_do_chamado(d).lower()
            chave = por_email.get(email) or (orgs.get(d.get("org")) if d.get("org") != self.org else None) \
                or ("email:" + email if email else "suporte:" + x["numero"])
            f = ficha(chave, str(d.get("quem") or ""))
            contato(f, d.get("quem"), email)
            ch = f["chamados"]
            ch["total"] += 1
            ch[x["estado"]] = ch.get(x["estado"], 0) + 1
            ch["abertos"] += x["estado"] != "resolvido"
            ch["lista"].append({"numero": x["numero"], "estado": x["estado"], "assunto": d.get("assunto"), "criado": x["criado"],
                                "atualizado": x["atualizado"], "responsavel": d.get("responsavel") or ""})
            tocar(f, x["criado"], x["atualizado"])
        out = list(fichas.values())
        for f in out:
            if not f["nome"]:
                f["nome"] = f["contato"]["nome"] or f["contato"]["email"] or f["chave"]
        out.sort(key=lambda f: (-(f["chamados"]["abertos"]), -(f["atualizado"] or 0)))
        return out

    def central_por(self, tipo: str, numero: str, dados: dict) -> dict:
        """Guarda uma compra paga ou um pedido de proposta. Repetir o mesmo numero nao duplica."""
        if tipo not in self.TIPOS_CENTRAL or not numero or len(numero) > 40:
            return {"ok": False, "erro": "registro invalido"}
        with self._trava:
            ja = self._db.execute("SELECT estado, dados FROM central WHERE tipo=? AND numero=?", (tipo, numero)).fetchone()
            if ja:
                return {"ok": True, "repetido": True, "estado": ja[0], "fatura": (json.loads(ja[1]) or {}).get("fatura")}
            agora = self.relogio()
            if tipo == "compra":      # as faturas sao numeradas em sequencia, a partir de 0000
                dados = dict(dados, fatura="%04d" % self._db.execute("SELECT COUNT(*) FROM central WHERE tipo='compra'").fetchone()[0])
            self._db.execute("INSERT INTO central(tipo,numero,dados,estado,criado,atualizado) VALUES(?,?,?,?,?,?)",
                             (tipo, numero, json.dumps(dados, ensure_ascii=False), "aguardando" if tipo == "compra" else "novo", agora, agora))
            self.registrar("central", numero, {"o_que": f"{tipo} recebida"})
            self._db.commit()
            return {"ok": True, "repetido": False, "estado": "aguardando" if tipo == "compra" else "novo", "fatura": dados.get("fatura")}

    def central_gravar(self, tipo: str, numero: str, dados: dict, estado: str = "ativo") -> dict:
        """Cria ou atualiza um registro que muda com o tempo (a equipe de consultores de um projeto)."""
        if tipo not in self.TIPOS_CENTRAL or not numero or len(numero) > 60:
            return {"ok": False, "erro": "registro invalido"}
        with self._trava:
            agora = self.relogio()
            self._db.execute("INSERT INTO central(tipo,numero,dados,estado,criado,atualizado) VALUES(?,?,?,?,?,?) "
                             "ON CONFLICT(tipo,numero) DO UPDATE SET dados=excluded.dados, estado=excluded.estado, atualizado=excluded.atualizado",
                             (tipo, numero, json.dumps(dados, ensure_ascii=False), estado, agora, agora))
            self.registrar("central", numero, {"o_que": f"{tipo} gravada"})
            self._db.commit()
            return {"ok": True}

    EXT_ARQUIVO = (".xlsx", ".xls", ".xlsm", ".csv", ".pdf", ".docx", ".doc")
    ARQUIVO_MAX = 20 * 1024 * 1024
    ARQUIVOS_POR_PEDIDO = 10

    def arquivo_por(self, pedido: str, nome: str, dados: bytes) -> dict:
        """Guarda um arquivo de apoio enviado pela loja junto com um pedido de proposta ja recebido."""
        nome = (nome or "").replace("\\", "/").rsplit("/", 1)[-1].strip()[:120]
        if not nome or not nome.lower().endswith(self.EXT_ARQUIVO):
            return {"ok": False, "erro": "so sao aceitos arquivos Excel, PDF e Word"}
        if not dados or len(dados) > self.ARQUIVO_MAX:
            return {"ok": False, "erro": "arquivo vazio ou maior que 20 MB"}
        erro = seg.arquivo_confere(nome, dados)          # conteúdo confere com a extensão; nada executável
        if erro:
            return {"ok": False, "erro": erro}
        with self._trava:
            if not self._db.execute("SELECT 1 FROM central WHERE tipo='pedido' AND numero=?", (pedido,)).fetchone():
                return {"ok": False, "erro": "pedido desconhecido"}
            if self._db.execute("SELECT COUNT(*) FROM central_arquivo WHERE pedido=?", (pedido,)).fetchone()[0] >= self.ARQUIVOS_POR_PEDIDO:
                return {"ok": False, "erro": "limite de arquivos por pedido atingido"}
            aid = secrets.token_urlsafe(12)
            self._db.execute("INSERT INTO central_arquivo(id,pedido,nome,tamanho,dados,criado) VALUES(?,?,?,?,?,?)",
                             (aid, pedido, nome, len(dados), dados, self.relogio()))
            self.registrar("central", pedido, {"o_que": "arquivo recebido", "nome": nome, "bytes": len(dados)})
            self._db.commit()
            return {"ok": True, "id": aid, "nome": nome, "tamanho": len(dados)}

    def arquivos_de(self, pedido: str) -> list[dict]:
        with self._trava:
            linhas = self._db.execute("SELECT id, nome, tamanho, criado FROM central_arquivo WHERE pedido=? ORDER BY criado", (pedido,)).fetchall()
        return [{"id": i, "nome": n, "tamanho": t, "criado": c} for i, n, t, c in linhas]

    def arquivo(self, aid: str) -> tuple[str, bytes] | None:
        with self._trava:
            r = self._db.execute("SELECT nome, dados FROM central_arquivo WHERE id=?", (aid,)).fetchone()
        return (r[0], bytes(r[1])) if r else None

    def central_estado(self, tipo: str, numero: str) -> str | None:
        with self._trava:
            r = self._db.execute("SELECT estado FROM central WHERE tipo=? AND numero=?", (tipo, numero)).fetchone()
        return r[0] if r else None

    def central_listar(self) -> list[dict]:
        with self._trava:
            linhas = self._db.execute("SELECT tipo, numero, dados, estado, criado, atualizado FROM central ORDER BY criado").fetchall()
        return [{"tipo": t, "numero": n, "dados": json.loads(d), "estado": e, "criado": c, "atualizado": a} for t, n, d, e, c, a in linhas]

    def central_marcar(self, tipo: str, numero: str, estado: str, quem: str = "") -> bool:
        with self._trava:
            cur = self._db.execute("UPDATE central SET estado=?, atualizado=? WHERE tipo=? AND numero=?", (estado, self.relogio(), tipo, numero))
            if cur.rowcount:
                self.registrar("central", numero, {"o_que": f"{tipo} {estado}", "quem": quem})
            self._db.commit()
            return cur.rowcount > 0

    # ── Montagem automática depois da compra aprovada ─────────────────────────
    # Aprovar o uso de uma compra cria, sozinho: o número da instalação, a plataforma só com os
    # módulos comprados, um código de ativação secreto (guardado só como resumo com sal) e o
    # e-mail de acesso na fila de saída. O código nunca aparece na loja: só no e-mail.
    MODULOS_PLATAFORMA = ("monitoramento", "agua", "zonas", "animais", "coleiras", "comedouros", "sustainkit", "supervisao",
                          "gestao", "painel", "planejador", "certificacoes", "solar", "avac", "turbinas", "sbn", "circular",
                          "carbono", "resiliencia", "medicamentos", "pulseira", "secador", "frota", "validacao")
    ATIVAR_ERROS = 5
    ATIVAR_ESPERA_S = 15 * 60

    @staticmethod
    def _codigo_ativacao() -> str:
        abc = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"          # sem 0/O e 1/I, que se confundem
        s = "".join(secrets.choice(abc) for _ in range(12))
        return "-".join((s[0:4], s[4:8], s[8:12]))

    @staticmethod
    def _resumo_codigo(sal: bytes, codigo: str) -> bytes:
        limpo = re.sub(r"[^A-Z0-9]", "", (codigo or "").upper())
        return hashlib.pbkdf2_hmac("sha256", limpo.encode(), sal, 100_000)

    # ids das certificações da loja (um item "cert-<id>" por certificação): os mesmos de sistema/physis-certificacoes.json
    CERTIFICACOES_LOJA = ("iso9001", "iso14001", "iso45001", "iso22000", "iso50001", "netzero", "leed", "leed_zero", "edge", "true_zw",
                          "aqua_hqe", "casa_azul", "greenkey", "pbe", "pbqph", "obra", "rainforest", "organico", "cafe_4c")
    # Do contrato à plataforma: cada item vendido (da loja ou de uma proposta personalizada) liga os módulos
    # que ele traz. Assim a plataforma nasce já com as abas certas, sem ninguém escolher à mão.
    # "base" (computador central e receptor LoRa, parte do Kit Monitoramento) liga o Monitoramento; "consultoria-pers"
    # é serviço da equipe e não liga módulo (entrada vazia de propósito: o mapa de variáveis confere que todo item da loja
    # está aqui). Ids conferidos em web/painel.html, LOJA_VENDA (15/11/2026).
    ITEM_MODULOS = {"base": ("monitoramento",), "consultoria-pers": (),
                    "mon-sw": ("monitoramento",), "campo": ("monitoramento",), "zonas": ("zonas",), "col": ("coleiras",),
                    "com": ("comedouros",), "P6": ("agua",), "scada": ("supervisao",), "gestao": ("gestao",),
                    "sk-e": ("sustainkit", "solar"), "sk-w": ("sustainkit",), "sk-m": ("sustainkit",),
                    "sk-c": ("sustainkit", "certificacoes"), "sk-pacote": ("sustainkit", "certificacoes", "carbono"),
                    "P5": ("turbinas",), "P9": ("pulseira",), "P10": ("medicamentos",), "P12": ("carbono",),
                    "P13": ("planejador",), "P15": ("resiliencia",), "P14": ("avac",), "P26": ("avac",),
                    "solar": ("solar",),   # módulo à parte do SustainKit (15/11/2026)
                    **dict.fromkeys(("cert-iso9001", "cert-iso14001", "cert-iso45001", "cert-iso22000", "cert-iso50001", "cert-netzero", "cert-leed", "cert-leed_zero", "cert-edge", "cert-true_zw", "cert-aqua_hqe", "cert-casa_azul", "cert-greenkey", "cert-pbe", "cert-pbqph", "cert-obra", "cert-rainforest", "cert-organico", "cert-cafe_4c"), ("certificacoes",)),   # um módulo por certificação (mesmos ids de CERTIFICACOES_LOJA)
                    "P17": ("sbn",), "P18": ("agua",),   # reúso e chuva vai com a Qualidade da água (à venda)
                    "P19": ("sbn",), "P11": ("circular",), "P16": ("circular",),
                    "P20": ("circular",), "P22": ("circular",), "P27": ("circular",), "P23": ("secador",),
                    "frota": ("frota",),   # Frota e combustível (em desenvolvimento, só na loja interna; 18/11/2026)
                    "validacao": ("validacao",),   # Validação planejado × gerado, M&V (produto 3 do SustainKit; em desenvolvimento, só na loja interna)
                    # D17 (15/11/2026): níveis 2 a 4 de cada certificação (regra em sistema/physis-certificacoes.json,
                    # niveis_loja; conferida por tests/test_cert_niveis.py). N3 = N2 (consultoria é serviço); N4 = N3 + M&V + SustainKit (D20).
                    'cert-iso9001-n2': ('certificacoes', 'gestao', 'monitoramento'),
                    'cert-iso9001-n3': ('certificacoes', 'gestao', 'monitoramento'),
                    'cert-iso9001-n4': ('certificacoes', 'gestao', 'monitoramento', 'sustainkit'),
                    'cert-iso14001-n2': ('certificacoes', 'circular', 'gestao', 'monitoramento'),
                    'cert-iso14001-n3': ('certificacoes', 'circular', 'gestao', 'monitoramento'),
                    'cert-iso14001-n4': ('certificacoes', 'circular', 'gestao', 'monitoramento', 'sustainkit'),
                    'cert-iso45001-n2': ('certificacoes', 'gestao', 'monitoramento'),
                    'cert-iso45001-n3': ('certificacoes', 'gestao', 'monitoramento'),
                    'cert-iso45001-n4': ('certificacoes', 'gestao', 'monitoramento', 'sustainkit'),
                    'cert-iso22000-n2': ('certificacoes', 'gestao', 'monitoramento'),
                    'cert-iso22000-n3': ('certificacoes', 'gestao', 'monitoramento'),
                    'cert-iso22000-n4': ('certificacoes', 'gestao', 'monitoramento', 'sustainkit'),
                    'cert-iso50001-n2': ('certificacoes', 'solar', 'gestao', 'monitoramento'),
                    'cert-iso50001-n3': ('certificacoes', 'solar', 'gestao', 'monitoramento'),
                    'cert-iso50001-n4': ('certificacoes', 'solar', 'gestao', 'monitoramento', 'sustainkit'),
                    'cert-netzero-n2': ('certificacoes', 'solar', 'circular', 'carbono', 'gestao'),
                    'cert-netzero-n3': ('certificacoes', 'solar', 'circular', 'carbono', 'gestao'),
                    'cert-netzero-n4': ('certificacoes', 'solar', 'circular', 'carbono', 'gestao', 'monitoramento', 'sustainkit'),
                    'cert-leed-n2': ('certificacoes', 'solar', 'avac', 'agua', 'circular', 'carbono', 'gestao', 'monitoramento'),
                    'cert-leed-n3': ('certificacoes', 'solar', 'avac', 'agua', 'circular', 'carbono', 'gestao', 'monitoramento'),
                    'cert-leed-n4': ('certificacoes', 'solar', 'avac', 'agua', 'circular', 'carbono', 'gestao', 'monitoramento', 'sustainkit'),
                    'cert-leed_zero-n2': ('certificacoes', 'solar', 'avac', 'agua', 'circular', 'carbono', 'monitoramento'),
                    'cert-leed_zero-n3': ('certificacoes', 'solar', 'avac', 'agua', 'circular', 'carbono', 'monitoramento'),
                    'cert-leed_zero-n4': ('certificacoes', 'solar', 'avac', 'agua', 'circular', 'carbono', 'monitoramento', 'sustainkit'),
                    'cert-edge-n2': ('certificacoes', 'solar', 'avac', 'agua', 'carbono', 'monitoramento'),
                    'cert-edge-n3': ('certificacoes', 'solar', 'avac', 'agua', 'carbono', 'monitoramento'),
                    'cert-edge-n4': ('certificacoes', 'solar', 'avac', 'agua', 'carbono', 'monitoramento', 'sustainkit'),
                    'cert-true_zw-n2': ('certificacoes', 'circular'),
                    'cert-true_zw-n3': ('certificacoes', 'circular'),
                    'cert-true_zw-n4': ('certificacoes', 'circular', 'monitoramento', 'sustainkit'),
                    'cert-aqua_hqe-n2': ('certificacoes', 'solar', 'avac', 'agua', 'circular'),
                    'cert-aqua_hqe-n3': ('certificacoes', 'solar', 'avac', 'agua', 'circular'),
                    'cert-aqua_hqe-n4': ('certificacoes', 'solar', 'avac', 'agua', 'circular', 'monitoramento', 'sustainkit'),
                    'cert-casa_azul-n2': ('certificacoes', 'solar', 'agua', 'circular', 'gestao'),
                    'cert-casa_azul-n3': ('certificacoes', 'solar', 'agua', 'circular', 'gestao'),
                    'cert-casa_azul-n4': ('certificacoes', 'solar', 'agua', 'circular', 'gestao', 'monitoramento', 'sustainkit'),
                    'cert-greenkey-n2': ('certificacoes', 'solar', 'agua', 'circular', 'monitoramento'),
                    'cert-greenkey-n3': ('certificacoes', 'solar', 'agua', 'circular', 'monitoramento'),
                    'cert-greenkey-n4': ('certificacoes', 'solar', 'agua', 'circular', 'monitoramento', 'sustainkit'),
                    'cert-pbe-n2': ('certificacoes', 'solar', 'avac', 'agua'),
                    'cert-pbe-n3': ('certificacoes', 'solar', 'avac', 'agua'),
                    'cert-pbe-n4': ('certificacoes', 'solar', 'avac', 'agua', 'monitoramento', 'sustainkit'),
                    'cert-pbqph-n2': ('certificacoes',),
                    'cert-pbqph-n3': ('certificacoes',),
                    'cert-pbqph-n4': ('certificacoes', 'monitoramento', 'sustainkit'),
                    'cert-obra-n2': ('certificacoes', 'solar', 'agua', 'circular', 'gestao', 'monitoramento'),
                    'cert-obra-n3': ('certificacoes', 'solar', 'agua', 'circular', 'gestao', 'monitoramento'),
                    'cert-obra-n4': ('certificacoes', 'solar', 'agua', 'circular', 'gestao', 'monitoramento', 'sustainkit'),
                    'cert-rainforest-n2': ('certificacoes', 'agua', 'circular', 'carbono'),
                    'cert-rainforest-n3': ('certificacoes', 'agua', 'circular', 'carbono'),
                    'cert-rainforest-n4': ('certificacoes', 'agua', 'circular', 'carbono', 'monitoramento', 'sustainkit'),
                    'cert-organico-n2': ('certificacoes', 'agua', 'circular'),
                    'cert-organico-n3': ('certificacoes', 'agua', 'circular'),
                    'cert-organico-n4': ('certificacoes', 'agua', 'circular', 'monitoramento', 'sustainkit'),
                    'cert-cafe_4c-n2': ('certificacoes', 'agua', 'circular', 'carbono', 'gestao'),
                    'cert-cafe_4c-n3': ('certificacoes', 'agua', 'circular', 'carbono', 'gestao'),
                    'cert-cafe_4c-n4': ('certificacoes', 'agua', 'circular', 'carbono', 'gestao', 'monitoramento', 'sustainkit')}
    # propostas personalizadas descrevem os itens em texto: palavras que identificam cada módulo
    PALAVRAS_MODULOS = (("solar", "solar"), ("fotovolt", "solar"), ("usina", "solar"), ("sensor", "monitoramento"),
                        ("umidade do solo", "monitoramento"), ("estação meteorol", "resiliencia"), ("ph", "agua"),
                        ("qualidade da água", "agua"), ("scada", "supervisao"), ("supervis", "supervisao"),
                        ("gestão", "gestao"), ("certifica", "certificacoes"), ("avac", "avac"), ("ar-condicionado", "avac"),
                        ("turbina", "turbinas"), ("coleira", "coleiras"), ("comedouro", "comedouros"), ("caixinha", "zonas"),
                        ("irrigação por zona", "zonas"), ("viveiro", "sbn"), ("sbn", "sbn"), ("resíduo", "circular"),
                        ("carbono", "carbono"), ("planejador", "planejador"))

    def modulos_do_contrato(self, dados: dict) -> list[str]:
        """Módulos da plataforma a partir do contrato: a lista explícita, os itens da loja e o texto dos itens."""
        achados: list[str] = []
        def por(m):
            if m in self.MODULOS_PLATAFORMA and m not in achados:
                achados.append(m)
        for m in dados.get("modulos") or []:
            if m == "animais":
                por("coleiras"); por("comedouros")
            else:
                por(m)
        for item in dados.get("itens") or []:
            if not isinstance(item, dict):
                continue
            for m in self.ITEM_MODULOS.get(str(item.get("id") or item.get("cod") or ""), ()):
                por(m)
            texto = " " + re.sub(r"\s+", " ", f"{item.get('nome', '')} {item.get('descricao', '')}".lower()) + " "
            for palavra, m in self.PALAVRAS_MODULOS:
                if (f" {palavra} " in texto) if len(palavra) <= 3 else (palavra in texto):
                    por(m)
        return achados

    def instalar_compra(self, numero_compra: str, link_base: str, fabricar=None, quem: str = "") -> dict:
        """Monta a instalação de uma compra aprovada. Repetir não cria outra nem troca o código."""
        with self._trava:
            ja = self._db.execute("SELECT numero FROM instalacao WHERE compra=?", (numero_compra,)).fetchone()
            if ja:
                return {"ok": True, "repetido": True, "numero": ja[0]}
            r = self._db.execute("SELECT dados FROM central WHERE tipo='compra' AND numero=?", (numero_compra,)).fetchone()
            if not r:
                return {"ok": False, "erro": "compra desconhecida"}
            dados = json.loads(r[0])
            pag = dados.get("pagador") or {}
            email, nome = str(pag.get("email") or "").strip(), str(pag.get("nome") or "Cliente").strip()[:120]
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                return {"ok": False, "erro": "compra sem e-mail valido"}
            modulos = self.modulos_do_contrato(dados)
            cursos = [c for c in (dados.get("cursos") or []) if isinstance(c, dict) and str(c.get("link", "")).startswith("https://")]
            seq = self._db.execute("SELECT COUNT(*) FROM instalacao").fetchone()[0] + 1
            numero = "PH-%04d" % seq
            base = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFD", nome.lower()).encode("ascii", "ignore").decode()).strip("-")[:40] or "cliente"
            org = f"{base}-{seq:04d}"
            codigo, sal = self._codigo_ativacao(), secrets.token_bytes(16)
            pacote = None
            if modulos and fabricar is not None:
                try:
                    pacote = str(fabricar(org, modulos, nome, cursos))
                except Exception as e:          # a instalação existe mesmo sem pacote; a equipe vê o motivo
                    self.registrar("instalacao", numero, {"o_que": "pacote nao montado", "erro": str(e)[:200]})
            self._db.execute("INSERT INTO instalacao(numero,compra,org,nome,email,modulos,sal,resumo,pacote,criado) VALUES(?,?,?,?,?,?,?,?,?,?)",
                             (numero, numero_compra, org, nome, email, json.dumps(modulos), sal, self._resumo_codigo(sal, codigo), pacote, self.relogio()))
            link = link_base.rstrip("/") + "/ativar/" + numero
            linhas = [f"Olá, {nome}.", "",
                      "O seu pedido " + numero_compra + " foi aprovado pela Physis Engineering.", ""]
            if modulos:
                linhas += ["Sua plataforma Physis está pronta:", "",
                           f"  Número da instalação: {numero}",
                           f"  Link de acesso: {link}",
                           f"  Código de ativação: {codigo}", "",
                           "Abra o link, digite o código e baixe a sua plataforma, já com os módulos comprados:",
                           "  " + ", ".join(modulos) + ".",
                           "No primeiro acesso, a plataforma pede o seu nome, um usuário e uma senha. A senha fica só com você.", ""]
            if cursos:
                linhas += ["Seus cursos:"] + [f"  {c.get('nome', 'Curso')}: {c['link']}" for c in cursos] + [""]
            linhas += ["Guarde o código: ele é pessoal e vale só para esta instalação.",
                       "Dúvidas: responda a este e-mail.", "", "Physis Engineering"]
            assunto = f"Physis · seu acesso ({numero})" if modulos else f"Physis · seu pedido {numero_compra} foi aprovado"
            self._db.execute("INSERT INTO email_saida(para,assunto,corpo,estado,ref,criado) VALUES(?,?,?,?,?,?)",
                             (email, assunto, "\n".join(linhas), "pendente", numero, self.relogio()))
            self.registrar("instalacao", quem or "gestao", {"o_que": "instalacao criada", "numero": numero, "compra": numero_compra,
                                                           "modulos": modulos, "pacote": bool(pacote)})
            self._db.commit()
            return {"ok": True, "repetido": False, "numero": numero, "org": org, "link": link, "modulos": modulos,
                    "pacote": bool(pacote), "email": "pendente"}

    def ativar(self, numero: str, codigo: str) -> dict:
        """Confere o código. Cinco erros seguidos bloqueiam por 15 minutos."""
        with self._trava:
            r = self._db.execute("SELECT sal, resumo, pacote, erros, bloqueado_ate, nome, modulos FROM instalacao WHERE numero=?", (numero,)).fetchone()
            if not r:
                return {"ok": False, "erro": "instalacao ou codigo nao conferem"}
            sal, resumo, pacote, erros, ate, nome, modulos = r
            agora = self.relogio()
            if ate > agora:
                return {"ok": False, "erro": "muitas tentativas; espere alguns minutos", "espera": int(ate - agora)}
            if not hmac.compare_digest(bytes(resumo), self._resumo_codigo(bytes(sal), codigo)):
                erros += 1
                self._db.execute("UPDATE instalacao SET erros=?, bloqueado_ate=? WHERE numero=?",
                                 (0 if erros >= self.ATIVAR_ERROS else erros, agora + self.ATIVAR_ESPERA_S if erros >= self.ATIVAR_ERROS else 0, numero))
                self._db.commit()
                return {"ok": False, "erro": "instalacao ou codigo nao conferem"}
            self._db.execute("UPDATE instalacao SET erros=0, ativado=COALESCE(ativado, ?) WHERE numero=?", (agora, numero))
            self.registrar("instalacao", numero, {"o_que": "ativacao conferida"})
            self._db.commit()
            return {"ok": True, "numero": numero, "nome": nome, "modulos": json.loads(modulos), "pacote": pacote}

    def instalacoes(self) -> list[dict]:
        with self._trava:
            linhas = self._db.execute("SELECT numero, compra, org, nome, email, modulos, pacote, criado, ativado FROM instalacao ORDER BY criado").fetchall()
        return [{"numero": n, "compra": c, "org": o, "nome": nm, "email": e, "modulos": json.loads(m), "pacote": bool(p),
                 "criado": cr, "ativado": a} for n, c, o, nm, e, m, p, cr, a in linhas]

    def emails(self, estado: str | None = None) -> list[dict]:
        with self._trava:
            q = "SELECT id, para, assunto, corpo, estado, ref, criado, enviado, erro FROM email_saida"
            linhas = self._db.execute(q + (" WHERE estado=?" if estado else "") + " ORDER BY id", ((estado,) if estado else ())).fetchall()
        return [{"id": i, "para": p, "assunto": a, "corpo": c, "estado": e, "ref": r, "criado": cr, "enviado": en, "erro": er}
                for i, p, a, c, e, r, cr, en, er in linhas]

    def email_marcar(self, ident: int, estado: str, erro: str = "") -> bool:
        if estado not in ("pendente", "enviado", "falhou", "enviado_a_mao"):
            return False
        with self._trava:
            cur = self._db.execute("UPDATE email_saida SET estado=?, erro=?, enviado=? WHERE id=?",
                                   (estado, erro[:300], self.relogio() if estado.startswith("enviado") else None, ident))
            if cur.rowcount and estado.startswith("enviado") and str(
                    (self._db.execute("SELECT ref FROM email_saida WHERE id=?", (ident,)).fetchone() or [""])[0]).startswith(seg.REF_CONTA):
                self._db.execute("UPDATE email_saida SET corpo='[e-mail de conta com link de uso único: texto apagado depois do envio]' WHERE id=?",
                                 (ident,))
            elif cur.rowcount and estado.startswith("enviado"):
                # depois de enviado, o código de ativação não fica guardado em texto no servidor
                self._db.execute("UPDATE email_saida SET corpo=? WHERE id=?",
                                 (re.sub(r"(Código de ativação: )[A-Z0-9-]+", r"\1(enviado ao cliente)",
                                         self._db.execute("SELECT corpo FROM email_saida WHERE id=?", (ident,)).fetchone()[0]), ident))
            if cur.rowcount:
                self.registrar("email", str(ident), {"o_que": estado})
            self._db.commit()
            return cur.rowcount > 0

    # ── Catálogo da loja: o servidor é quem diz o que o cliente vê ────────────
    # Regra: tudo nasce interno. Primeiro alguém da Physis revisa (fixa situação e preço);
    # só depois um item em funcionamento pode ir ao público. Mudar conteúdo, preço ou
    # situação depois disso desfaz a revisão e tira do público: precisa revisar de novo.
    LOJA_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
    LOJA_PUBLICAVEL = ("func",)                      # "Em funcionamento"; desenvolvimento, simulação e parcerias não
    LOJA_SITUACOES = ("func", "sim", "dev", "par")
    LOJA_CATEGORIAS = ("", "campo", "agua", "energia", "cert", "cuidado", "mat", "cursos")
    LOJA_TEXTOS = {"nome": 120, "cod": 20, "sub": 400, "carga": 40, "modalidade": 60, "link": 300, "resumo": 2000}

    def _loja_ler(self, ident: str) -> dict | None:
        r = self._db.execute("SELECT dados, revisado, publicado FROM loja_item WHERE id=?", (ident,)).fetchone()
        if not r:
            return None
        d = json.loads(r[0])
        d["revisado"] = json.loads(r[1]) if r[1] else None
        d["publicado"] = json.loads(r[2]) if r[2] else None
        return d

    def loja_gravar(self, ident: str, campos: dict, quem: str) -> dict:
        """Cria ou altera um item. Campos aceitos: st, preco (número ou null = sob consulta), categ, e,
        para produto novo ou curso, nome, cod, sub, carga, modalidade, link, resumo."""
        if not self.LOJA_ID.match(ident or ""):
            return {"ok": False, "erro": "identificador invalido"}
        novo_d: dict = {}
        if "st" in campos:
            if campos["st"] not in self.LOJA_SITUACOES:
                return {"ok": False, "erro": "situacao invalida"}
            novo_d["st"] = campos["st"]
        if "preco" in campos:
            p = campos["preco"]
            if p is not None and (isinstance(p, bool) or not isinstance(p, (int, float)) or p < 0 or p > 10_000_000):
                return {"ok": False, "erro": "preco invalido"}
            novo_d["preco"] = p
        if "categ" in campos:
            if campos["categ"] not in self.LOJA_CATEGORIAS:
                return {"ok": False, "erro": "assunto invalido"}
            novo_d["categ"] = campos["categ"]
        if "novo" in campos:
            novo_d["novo"] = bool(campos["novo"])
        for k, lim in self.LOJA_TEXTOS.items():
            if k in campos:
                v = campos[k]
                if v is not None and (not isinstance(v, str) or len(v) > lim):
                    return {"ok": False, "erro": f"{k} invalido"}
                if k == "link" and v and not v.startswith("https://"):
                    return {"ok": False, "erro": "o link precisa comecar com https://"}
                novo_d[k] = (v or "").strip()
        with self._trava:
            atual = self._loja_ler(ident)
            d = {k: v for k, v in (atual or {}).items() if k not in ("revisado", "publicado")}
            if novo_d.get("novo") and not (d.get("nome") or novo_d.get("nome")):
                return {"ok": False, "erro": "produto novo precisa de nome"}
            mudou = any(d.get(k) != v for k, v in novo_d.items())
            d.update(novo_d)
            revisado = None if mudou else (atual or {}).get("revisado")
            publicado = None if mudou else (atual or {}).get("publicado")
            self._db.execute("INSERT INTO loja_item(id,dados,revisado,publicado,atualizado) VALUES(?,?,?,?,?) "
                             "ON CONFLICT(id) DO UPDATE SET dados=excluded.dados, revisado=excluded.revisado, "
                             "publicado=excluded.publicado, atualizado=excluded.atualizado",
                             (ident, json.dumps(d, ensure_ascii=False), json.dumps(revisado) if revisado else None,
                              json.dumps(publicado) if publicado else None, self.relogio()))
            if mudou:
                self.registrar("loja", quem, {"o_que": "item alterado", "id": ident, "campos": sorted(novo_d)})
            self._db.commit()
            return {"ok": True, "item": self._loja_ler(ident), "revisao_desfeita": mudou and bool((atual or {}).get("revisado"))}

    def loja_revisar(self, ident: str, quem: str, revisado: bool = True) -> dict:
        """Primeira revisão: a pessoa confirma a situação e o preço como estão gravados."""
        with self._trava:
            atual = self._loja_ler(ident)
            if not atual or "st" not in atual:
                return {"ok": False, "erro": "grave a situacao do item antes de revisar"}
            rev = {"por": quem, "em": self.relogio()} if revisado else None
            pub = atual.get("publicado") if revisado else None      # desfazer a revisão tira do público
            self._db.execute("UPDATE loja_item SET revisado=?, publicado=?, atualizado=? WHERE id=?",
                             (json.dumps(rev) if rev else None, json.dumps(pub) if pub else None, self.relogio(), ident))
            self.registrar("loja", quem, {"o_que": "revisado" if revisado else "revisao desfeita", "id": ident})
            self._db.commit()
            return {"ok": True, "item": self._loja_ler(ident)}

    def loja_publicar(self, ident: str, quem: str, publico: bool = True) -> dict:
        with self._trava:
            atual = self._loja_ler(ident)
            if not atual:
                return {"ok": False, "erro": "item desconhecido"}
            if publico:
                if not atual.get("revisado"):
                    return {"ok": False, "erro": "o item precisa da primeira revisao antes de ir ao publico"}
                if atual.get("st") not in self.LOJA_PUBLICAVEL:
                    return {"ok": False, "erro": "so item em funcionamento vai ao publico; em desenvolvimento fica interno"}
            pub = {"por": quem, "em": self.relogio()} if publico else None
            self._db.execute("UPDATE loja_item SET publicado=?, atualizado=? WHERE id=?",
                             (json.dumps(pub) if pub else None, self.relogio(), ident))
            self.registrar("loja", quem, {"o_que": "publicado" if publico else "retirado do publico", "id": ident})
            self._db.commit()
            return {"ok": True, "item": self._loja_ler(ident)}

    QUEM_CATALOGO_INICIAL = "catálogo inicial da instalação"

    def loja_semear_inicial(self, catalogo: dict) -> dict:
        """Site novo: se NADA foi publicado ainda, grava, revisa e publica o catálogo inicial (sistema/loja-catalogo-inicial.json),
        registrado como "catálogo inicial da instalação". Nunca mexe num catálogo que a equipe já publicou; item que a equipe já
        gravou (mesmo sem publicar) fica como está. Só entra item em funcionamento; o resto é recusado."""
        with self._trava:
            publicados = self._db.execute("SELECT COUNT(*) FROM loja_item WHERE publicado IS NOT NULL").fetchone()[0]
            existentes = {r[0] for r in self._db.execute("SELECT id FROM loja_item")}
        if publicados:
            return {"ok": True, "semeado": 0, "motivo": "a loja já tem catálogo publicado"}
        quem, feitos, recusados = self.QUEM_CATALOGO_INICIAL, [], {}
        for ident, campos in sorted((catalogo or {}).get("itens", {}).items()):
            if ident in existentes:
                continue
            if campos.get("st") not in self.LOJA_PUBLICAVEL:
                recusados[ident] = "não está em funcionamento"
                continue
            r = self.loja_gravar(ident, {k: v for k, v in campos.items() if k in ("st", "preco", "categ", *self.LOJA_TEXTOS)}, quem)
            if r.get("ok"):
                r = self.loja_revisar(ident, quem)
            if r.get("ok"):
                r = self.loja_publicar(ident, quem)
            if r.get("ok"):
                feitos.append(ident)
            else:
                recusados[ident] = r.get("erro", "erro")
        if feitos:
            with self._trava:
                self.registrar("loja", quem, {"o_que": quem, "itens": len(feitos)})
                self._db.commit()
        return {"ok": True, "semeado": len(feitos), "recusados": recusados}

    def loja_catalogo(self, interno: bool = False) -> dict:
        """Público: só itens revisados, em funcionamento e publicados, sem dados de revisão.
        Interno: tudo, com quem revisou e publicou."""
        with self._trava:
            ids = [r[0] for r in self._db.execute("SELECT id FROM loja_item ORDER BY id")]
            itens = {i: self._loja_ler(i) for i in ids}
        if interno:
            return {"ok": True, "itens": itens}
        visiveis = {}
        for i, d in itens.items():
            if d.get("publicado") and d.get("revisado") and d.get("st") in self.LOJA_PUBLICAVEL:
                visiveis[i] = {k: v for k, v in d.items() if k not in ("revisado", "publicado")}
        return {"ok": True, "itens": visiveis}

    # ── Consultoria ── textos editáveis das páginas públicas do site (ex.: /consultoria)
    # Só texto puro: qualquer marcação HTML é retirada antes de gravar. Texto vazio apaga a
    # troca e a página volta ao texto original.
    SITE_PAGINA = re.compile(r"^[a-z0-9-]{1,40}$")
    SITE_CHAVE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,59}$")
    SITE_TEXTO_MAX = 4000
    SITE_BLOCOS_MAX = 200

    def _site_tabela(self) -> None:
        if not getattr(self, "_site_pronto", False):
            self._db.execute("CREATE TABLE IF NOT EXISTS site_texto (pagina TEXT NOT NULL, chave TEXT NOT NULL, texto TEXT NOT NULL, "
                             "atualizado REAL NOT NULL, por TEXT NOT NULL, PRIMARY KEY (pagina, chave))")
            self._db.commit()
            self._site_pronto = True

    @staticmethod
    def _site_limpar(texto: str) -> str:
        t = re.sub(r"<[^>]*>", "", texto)                       # tira tags
        t = t.replace("<", "").replace(">", "")                 # e o que sobrar de tag aberta
        t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", t).replace("\r\n", "\n").replace("\r", "\n")
        return t.strip()

    def site_textos(self, pagina: str) -> dict:
        if not self.SITE_PAGINA.match(pagina or ""):
            return {"ok": False, "erro": "pagina invalida"}
        with self._trava:
            self._site_tabela()
            linhas = self._db.execute("SELECT chave, texto, atualizado FROM site_texto WHERE pagina=? ORDER BY chave", (pagina,)).fetchall()
        return {"ok": True, "pagina": pagina, "textos": {c: t for c, t, _ in linhas},
                "atualizado": max((a for _, _, a in linhas), default=None)}

    def site_gravar(self, pagina: str, textos, por: str) -> dict:
        """Grava {chave: texto}. Texto vazio apaga a troca daquela chave."""
        if not self.SITE_PAGINA.match(pagina or ""):
            return {"ok": False, "erro": "pagina invalida"}
        if not isinstance(textos, dict) or not textos:
            return {"ok": False, "erro": "envie {chave: texto}"}
        if len(textos) > self.SITE_BLOCOS_MAX:
            return {"ok": False, "erro": f"no maximo {self.SITE_BLOCOS_MAX} blocos"}
        limpos: dict[str, str] = {}
        for k, v in textos.items():
            if not isinstance(k, str) or not self.SITE_CHAVE.match(k):
                return {"ok": False, "erro": "chave invalida"}
            if not isinstance(v, str):
                return {"ok": False, "erro": f"texto invalido em {k}"}
            t = self._site_limpar(v)
            if len(t) > self.SITE_TEXTO_MAX:
                return {"ok": False, "erro": f"texto maior que {self.SITE_TEXTO_MAX} caracteres em {k}"}
            limpos[k] = t
        with self._trava:
            self._site_tabela()
            ja = {r[0] for r in self._db.execute("SELECT chave FROM site_texto WHERE pagina=?", (pagina,))}
            depois = (ja | {k for k, t in limpos.items() if t}) - {k for k, t in limpos.items() if not t}
            if len(depois) > self.SITE_BLOCOS_MAX:
                return {"ok": False, "erro": f"no maximo {self.SITE_BLOCOS_MAX} blocos por pagina"}
            agora = self.relogio()
            for k, t in limpos.items():
                if t:
                    self._db.execute("INSERT INTO site_texto(pagina,chave,texto,atualizado,por) VALUES(?,?,?,?,?) "
                                     "ON CONFLICT(pagina,chave) DO UPDATE SET texto=excluded.texto, atualizado=excluded.atualizado, por=excluded.por",
                                     (pagina, k, t, agora, por))
                else:
                    self._db.execute("DELETE FROM site_texto WHERE pagina=? AND chave=?", (pagina, k))
            self.registrar("site", por, {"o_que": "textos alterados", "pagina": pagina, "chaves": sorted(limpos)[:50]})
            self._db.commit()
        return dict(self.site_textos(pagina), gravados=len(limpos))
    # ── fim Consultoria ──

    def fechar(self) -> None:
        with self._trava:
            self._db.commit()
            self._db.close()
