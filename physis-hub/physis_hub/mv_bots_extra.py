"""Bots compartilhados do M&A (22/11/2026): editais, dados-iot, simulação, gestões, bancos/certificados, acervo → trilhas.

Regras (CLAUDE.md): nenhum limite técnico inventado (regra 1). Limite que o sistema ainda não tem vem de variável de ambiente;
sem ela, o bot mostra a medida e abre UM aviso "info" pedindo o limite, sem alarme falso. Só observam e propõem: nada é
enviado, apagado ou reiniciado sem aprovação humana (D49). IA só local e opcional (regra 11, ver ia_local).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import sqlite3
import ssl
import subprocess
import time
from datetime import date, datetime
from pathlib import Path

from . import mv as mvmod
from .mv import MV

RAIZ_REPO = Path(__file__).resolve().parents[2]


_MV_ATUAL: list = []     # banco da rodada atual: a resposta da caixa de perguntas vale como limite


def _limite(nome: str):
    """Limite: variável de ambiente; senão, a resposta numérica dada na caixa de perguntas do M&A; senão, None."""
    v = os.environ.get(nome, "").strip().replace(",", ".")
    try:
        if v:
            return float(v)
    except ValueError:
        pass
    if _MV_ATUAL:
        from .mv_auditoria import limite_respondido
        return limite_respondido(_MV_ATUAL[-1], nome)
    return None


def _pede_limite(mv: MV, bot: str, var: str, oque: str) -> None:
    mv.alertar(bot, "sem_limite", var, "info", f"Limite de {oque} não definido: o bot só mostra a medida",
               f"Responder na caixa de perguntas (M&A → Aprovações) ou definir a variável {var}; o sistema não traz valor de fábrica")


def _fim(mv: MV, bot: str, inicio: float, r: dict) -> dict:
    mv.fechar_alertas_nao_vistos(bot, inicio)
    mv.registrar_execucao(bot, inicio, json.dumps(r, ensure_ascii=False, default=str))
    return r


# ---- IA local (opcional) ------------------------------------------------------------------------------------------
def ia_local(pergunta: str, contexto: str = "", tempo: int = 60) -> str | None:
    """Pergunta ao modelo aberto do próprio servidor (vLLM, API compatível com OpenAI em PHYSIS_IA_URL). Sem a variável,
    ou se o servidor não responde, devolve None e o bot segue só por regras. Nunca chama serviço de terceiros."""
    url = os.environ.get("PHYSIS_IA_URL", "").rstrip("/")
    if not url:
        return None
    import urllib.request
    corpo = json.dumps({"model": os.environ.get("PHYSIS_IA_MODELO", "local"), "temperature": 0,
                        "messages": [{"role": "system", "content": "Responda em português do Brasil, curto e factual. "
                                      "Se não souber, diga que não sabe; não invente números."},
                                     {"role": "user", "content": (contexto[:6000] + "\n\n" + pergunta).strip()}]}).encode()
    try:
        req = urllib.request.Request(url + "/v1/chat/completions", corpo, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=tempo) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()
    except Exception:  # noqa: BLE001 — IA é opcional
        return None


# ---- editais --------------------------------------------------------------------------------------------------------
ABERTAS = ("triagem", "decidir", "preparar", "revisao")


def bot_editais(mv: MV, csv: Path | None = None) -> dict:
    """Importa o banco de editais (se houver) e acompanha prazos e necessidades das propostas abertas."""
    from . import mv_bots, mv_editais
    inicio = mv.nova_rodada()
    ed = mv_editais.Editais(mv)
    arq = Path(csv or os.environ.get("PHYSIS_EDITAIS_CSV") or (mv_bots.DOCS / "Sistema Physis" / "31_Editais" / "banco_editais.csv"))
    r = {"importados": None, "abertos": 0, "vencidos": 0, "proximos": 0}
    if arq.is_file():
        r["importados"] = ed.importar_csv(arq)
    else:
        mv.alertar("editais", "sem_banco", str(arq), "info", f"Banco de editais não encontrado: {arq}",
                   "Definir PHYSIS_EDITAIS_CSV ou colocar o banco_editais.csv no lugar")
    aviso = _limite("PHYSIS_EDITAIS_AVISO_DIAS")
    if aviso is None:
        _pede_limite(mv, "editais", "PHYSIS_EDITAIS_AVISO_DIAS", "antecedência de aviso de prazo (dias)")
    for d in ed.listar():
        if d["etapa"] not in ABERTAS:
            continue
        r["abertos"] += 1
        dias, tit = d["dias"], d["titulo"][:90]
        if dias is not None and dias < 0:
            r["vencidos"] += 1
            mv.alertar("editais", "vencido", d["id"], "atencao", f"Edital com prazo vencido e ainda em '{d['etapa']}': {tit}",
                       "Arquivar ou registrar a próxima edição", d.get("frente", ""))
        elif dias is not None and aviso is not None and dias <= aviso:
            r["proximos"] += 1
            falta = sum(1 for x in d["necessidades"] if not x["feito"])
            mv.alertar("editais", "prazo", d["id"], "alerta" if falta else "atencao",
                       f"Edital fecha em {dias} d ({d['prazo']}), {d['pronto_pct']} % pronto, {falta} item(ns) pendente(s): {tit}",
                       "Decidir se entra; distribuir os itens pendentes", d.get("frente", ""))
        if d["etapa"] in ("preparar", "revisao") and not d.get("responsavel"):
            mv.alertar("editais", "sem_responsavel", d["id"], "atencao", f"Proposta sem responsável: {tit}", "Definir o responsável")
    return _fim(mv, "editais", inicio, r)


# ---- dados de campo (IoT) -------------------------------------------------------------------------------------------
def bot_dados_iot(mv: MV, banco: Path | None = None, agora: float | None = None) -> dict:
    """Idade da última leitura de cada nó no banco do Hub (tabela leitura)."""
    inicio = mv.nova_rodada()
    agora = agora or time.time()
    arq = Path(banco or os.environ.get("PHYSIS_BANCO") or "physis-hub.db")
    if not arq.is_file():
        mv.alertar("dados_iot", "sem_banco", str(arq), "info", f"Banco do Hub não encontrado: {arq}",
                   "Rodar no servidor do Hub ou definir PHYSIS_BANCO")
        return _fim(mv, "dados_iot", inicio, {"nos": 0, "banco": str(arq)})
    lim = _limite("PHYSIS_IOT_MUDO_H")
    if lim is None:
        _pede_limite(mv, "dados_iot", "PHYSIS_IOT_MUDO_H", "horas sem leitura de um sensor")
    con = sqlite3.connect(f"file:{arq}?mode=ro", uri=True)
    try:
        linhas = con.execute("SELECT no, MAX(recebido) FROM leitura GROUP BY no").fetchall()
    finally:
        con.close()
    nos = {}
    for no, ult in linhas:
        h = round((agora - ult) / 3600, 1)
        nos[str(no)] = h
        if lim is not None and h > lim:
            mv.alertar("dados_iot", "no_mudo", str(no), "alerta", f"Nó {no} sem leitura há {h:.1f} h (limite {lim:g} h)",
                       "Conferir energia, rádio e o receptor V6 desse nó")
    return _fim(mv, "dados_iot", inicio, {"nos": len(nos), "idade_h": nos})


# ---- simulação (Gêmeo Virtual) --------------------------------------------------------------------------------------
def _quase(a, b, rel=1e-9, ab=1e-9) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= max(ab, rel * max(abs(a), abs(b)))
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_quase(x, y, rel, ab) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_quase(a[k], b[k], rel, ab) for k in a)
    return a == b


def bot_simulacao(mv: MV) -> dict:
    """Casos de referência do Gêmeo Virtual em dia (mesma conta hoje × gravado) e premissas copiadas no JS."""
    from .simulacao import casos
    inicio = mv.nova_rodada()
    j, _js, bloco = casos.textos()
    novo = json.loads(j)
    r = {"casos": len(novo.get("casos", novo)) if isinstance(novo, dict) else None, "em_dia": True, "premissas_js": True}
    arq = casos.PASTA / "casos.json"
    if not arq.is_file() or not _quase(json.loads(arq.read_text(encoding="utf-8")), novo):
        r["em_dia"] = False
        mv.alertar("simulacao", "casos", "casos.json", "alerta", "Casos de referência da Simulação desatualizados (a conta mudou)",
                   "Conferir a mudança e rodar: python -m physis_hub.simulacao.casos --gravar")
    js = RAIZ_REPO / "sistema" / "physis-simulacao.js"
    if js.is_file() and bloco not in js.read_text(encoding="utf-8"):
        r["premissas_js"] = False
        mv.alertar("simulacao", "premissas", "physis-simulacao.js", "alerta", "Premissas da Simulação diferentes entre servidor e navegador",
                   "Rodar: python -m physis_hub.simulacao.casos --gravar (regra 4: conta espelho)")
    return _fim(mv, "simulacao", inicio, r)


# ---- gestões internas -----------------------------------------------------------------------------------------------
def bot_gestoes(mv: MV, pasta: Path | None = None, agora: float | None = None) -> dict:
    """Exportações physis/1 das Gestões internas: idade de cada arquivo e se já entrou no M&A."""
    from . import mv_bots
    inicio = mv.nova_rodada()
    agora = agora or time.time()
    p = Path(pasta or os.environ.get("PHYSIS_MV_GESTOES") or (mv_bots.DOCS / "Sistema Physis" / "28_Physis_MV" / "gestoes"))
    if not p.is_dir():
        mv.alertar("gestoes", "sem_pasta", str(p), "info", f"Pasta das exportações das Gestões não encontrada: {p}",
                   "Definir PHYSIS_MV_GESTOES (uma exportação physis/1 por Gestão)")
        return _fim(mv, "gestoes", inicio, {"arquivos": 0})
    lim = _limite("PHYSIS_GESTOES_MAX_H")
    if lim is None:
        _pede_limite(mv, "gestoes", "PHYSIS_GESTOES_MAX_H", "idade máxima da exportação de uma Gestão (h)")
    ult_imp = mv.db.execute("SELECT MAX(atualizado) FROM mv_tarefa WHERE origem='gestao'").fetchone()[0] or 0
    out = {}
    for f in sorted(p.glob("*.json")):
        h = round((agora - f.stat().st_mtime) / 3600, 1)
        out[f.name] = h
        if lim is not None and h > lim:
            mv.alertar("gestoes", "velha", f.name, "atencao", f"Exportação {f.name} tem {h:.0f} h (limite {lim:g} h)",
                       "Exportar de novo na Gestão interna dessa frente")
        if f.stat().st_mtime > ult_imp + 60:
            mv.alertar("gestoes", "nao_importada", f.name, "atencao", f"Exportação {f.name} é mais nova que a última importação",
                       f'Rodar: python -m physis_hub.mv_cli importar "{f}"')
    return _fim(mv, "gestoes", inicio, {"arquivos": len(out), "idade_h": out})


# ---- bancos, certificados e segredos --------------------------------------------------------------------------------
SEGREDOS = re.compile(r"(^|/)(secrets\.h|\.env|[^/]*\.env|[^/]*chaves?[^/]*\.json|[^/]*\.pem|[^/]*\.key)$", re.I)


def _validade_cert(host: str, porta: int = 443, tempo: int = 10) -> float:
    ctx = ssl.create_default_context()
    with socket.create_connection((host, porta), timeout=tempo) as s, ctx.wrap_socket(s, server_hostname=host) as t:
        fim = t.getpeercert()["notAfter"]
    return (ssl.cert_time_to_seconds(fim) - time.time()) / 86400


def bot_bancos(mv: MV, bancos: list[Path] | None = None, raiz: Path | None = None, validade=_validade_cert) -> dict:
    """integrity_check dos bancos SQLite, PostgreSQL (pg_isready), validade do HTTPS e segredos fora do Git (regra 12)."""
    inicio = mv.nova_rodada()
    r = {"bancos": {}, "postgres": None, "https": None, "segredos_no_git": []}
    lista = bancos if bancos is not None else [Path(os.environ.get("PHYSIS_BANCO") or "physis-hub.db"), mvmod.pasta_padrao() / "physis-mv.db"]
    for b in lista:
        if not Path(b).is_file():
            continue
        try:
            con = sqlite3.connect(f"file:{b}?mode=ro", uri=True)
            res = con.execute("PRAGMA integrity_check").fetchone()[0]
            con.close()
        except sqlite3.Error as e:
            res = repr(e)
        r["bancos"][Path(b).name] = res
        if res != "ok":
            mv.alertar("bancos", "integridade", str(b), "alerta", f"Banco {Path(b).name} com problema: {res[:150]}",
                       "Parar a escrita, restaurar a última cópia boa (restaurar.sh) e investigar")
    if shutil.which("pg_isready") and os.environ.get("PHYSIS_PG_HOST"):
        p = subprocess.run(["pg_isready", "-h", os.environ["PHYSIS_PG_HOST"]], capture_output=True, text=True, timeout=20)
        r["postgres"] = p.returncode == 0
        if p.returncode:
            mv.alertar("bancos", "postgres", os.environ["PHYSIS_PG_HOST"], "alerta", f"PostgreSQL não responde: {p.stdout.strip()}",
                       "docker compose ps postgis timescaledb")
    dom = os.environ.get("PHYSIS_DOMINIO")
    if dom:
        try:
            dias = round(validade(dom), 1)
            r["https"] = dias
            aviso = _limite("PHYSIS_CERT_AVISO_DIAS")
            if aviso is None:
                _pede_limite(mv, "bancos", "PHYSIS_CERT_AVISO_DIAS", "antecedência de aviso do certificado HTTPS (dias)")
            elif dias <= aviso:
                mv.alertar("bancos", "certificado", dom, "alerta" if dias <= 0 else "atencao",
                           f"Certificado HTTPS de {dom} vence em {dias:.0f} d", "Conferir a renovação automática do Caddy")
        except Exception as e:  # noqa: BLE001
            r["https"] = repr(e)
            mv.alertar("bancos", "https", dom, "alerta", f"HTTPS de {dom} não respondeu: {e!r}"[:200], "Conferir o Caddy e o DNS")
    raiz = Path(raiz or RAIZ_REPO)
    if (raiz / ".git").exists() and shutil.which("git"):
        p = subprocess.run(["git", "-C", str(raiz), "ls-files"], capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        achados = [f for f in p.stdout.splitlines() if SEGREDOS.search(f) and ".exemplo" not in f and "exemplo" not in f]
        r["segredos_no_git"] = achados
        for f in achados:
            mv.alertar("bancos", "segredo_no_git", f, "alerta", f"Arquivo de segredo no Git: {f}",
                       "Tirar do Git (git rm --cached), trocar a senha/chave e pôr no .gitignore (regra 12)")
    return _fim(mv, "bancos", inicio, r)


# ---- acervo → trilhas (InovaSTEM) -----------------------------------------------------------------------------------
TIPOS_ACERVO = {".pdf", ".odt", ".docx", ".odp", ".pptx", ".ods", ".xlsx", ".md", ".txt", ".mp4", ".html"}


def bot_acervo(mv: MV, pasta: Path | None = None, trilhas: Path | None = None) -> dict:
    """Liga o acervo às trilhas do InovaSTEM. As trilhas (T1, T2…) e suas palavras-chave vêm de trilhas.json, escrito pela
    equipe; o bot não inventa conteúdo de curso. Cada material novo que casa com uma trilha vira pedido para aprovação."""
    from . import mv_bots, mv_comandos
    inicio = mv.nova_rodada()
    base = mv_bots.DOCS / "Instituto Physis" / "InovaSTEM"
    p = Path(pasta or os.environ.get("PHYSIS_ACERVO") or (base / "acervo"))
    t = Path(trilhas or os.environ.get("PHYSIS_TRILHAS") or (base / "trilhas.json"))
    if not p.is_dir():
        mv.alertar("acervo", "sem_pasta", str(p), "info", f"Pasta do acervo não encontrada: {p}", "Definir PHYSIS_ACERVO")
        return _fim(mv, "acervo", inicio, {"materiais": 0})
    if not t.is_file():
        mv.alertar("acervo", "sem_trilhas", str(t), "atencao", "Trilhas do InovaSTEM ainda não definidas (trilhas.json)",
                   'Criar o arquivo: {"T1": {"nome": "[MARCADOR]", "palavras": ["..."]}, "T2": {...}}')
        return _fim(mv, "acervo", inicio, {"materiais": 0})
    defs = json.loads(t.read_text(encoding="utf-8"))
    mv.db.execute("CREATE TABLE IF NOT EXISTS mv_acervo (caminho TEXT PRIMARY KEY, trilha TEXT NOT NULL, visto REAL NOT NULL)")
    cmd = mv_comandos.Comandos(mv)
    novos, sem_trilha, total = 0, 0, 0
    for f in sorted(x for x in p.rglob("*") if x.is_file() and x.suffix.lower() in TIPOS_ACERVO):
        total += 1
        nome = re.sub(r"[_\-.]+", " ", f.stem).lower()
        casou = [k for k, d in defs.items() if any(w.lower() in nome for w in d.get("palavras", []))]
        if not casou:
            sem_trilha += 1
            continue
        rel = str(f.relative_to(p))
        for k in casou:
            if mv.db.execute("SELECT 1 FROM mv_acervo WHERE caminho=? AND trilha=?", (rel, k)).fetchone():
                continue
            mv.db.execute("INSERT OR REPLACE INTO mv_acervo VALUES (?,?,?)", (rel, k, time.time()))
            resumo = ia_local(f"Em duas frases: para que serve este material na trilha {k} ({defs[k].get('nome', '')})?",
                              f"Arquivo: {rel}") or ""
            cmd._pedido("acervo", f"{k}: {f.name}", "", "rascunho",
                        f"Material do acervo: {rel}\nTrilha sugerida: {k} · {defs[k].get('nome', '[MARCADOR]')}\n"
                        f"Motivo: o nome casa com as palavras-chave da trilha.\n{resumo}\n\n"
                        "Aprovar = entra na trilha (a equipe revisa o conteúdo antes de publicar).", origem="acervo")
            novos += 1
    mv.db.commit()
    if sem_trilha:
        mv.alertar("acervo", "sem_trilha", "acervo", "info", f"{sem_trilha} material(is) do acervo sem trilha",
                   "Acrescentar palavras-chave em trilhas.json ou classificar à mão")
    return _fim(mv, "acervo", inicio, {"materiais": total, "propostas_novas": novos, "sem_trilha": sem_trilha})


def _com_caixa(f):
    """Durante a rodada do bot, _limite também lê as respostas da caixa de perguntas deste banco."""
    def rodar(mv, *a, **k):
        _MV_ATUAL.append(mv)
        try:
            return f(mv, *a, **k)
        finally:
            _MV_ATUAL.pop()
    rodar.__name__, rodar.__doc__ = f.__name__, f.__doc__
    return rodar


BOTS_EXTRA = {"editais": _com_caixa(bot_editais), "dados_iot": _com_caixa(bot_dados_iot), "simulacao": bot_simulacao,
              "gestoes": _com_caixa(bot_gestoes), "bancos": _com_caixa(bot_bancos), "acervo": bot_acervo}
