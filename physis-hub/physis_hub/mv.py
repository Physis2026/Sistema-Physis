"""Physis M&V: núcleo de gestão de nível 2 das quatro frentes (VERSÃO DE TESTE, 18/11/2026; decisões D45 e D51–D60
do documento 27 de Sistema Physis).

O que é: um painel e um banco próprios, separados da Gestão interna de cada plataforma (regra 9 do CLAUDE.md), que
juntam Casa Physis, Physis Engineering, Instituto Physis e InovaSTEM. Cada plataforma continua gerindo os seus
projetos; o M&V lê, mede, cruza prazos e dependências e avisa o que precisa de intervenção.

Tabelas (banco próprio, `physis-mv.db`, nunca o do hub nem o do Instituto):
  mv_frente, mv_meta (metas 2027–2031), mv_marco (roadmap), mv_tarefa, mv_documento, mv_alerta, mv_lanc (financeiro,
  sempre separado por entidade e "a conferir pelo contador" até ele validar), mv_execucao (registro dos bots).

Regras:
- Nada é inventado: data que veio de estimativa (horizonte micro/meso/macro da Gestão) fica com `data_estimada=1`
  e aparece como [CONFERIR]; valor financeiro sem conferência do contador nunca entra como oficial (D70).
- Toda tarefa tem `versao` 'teste' ou 'oficial' (D31): o M&V só exporta como oficial o que foi aprovado.
- Caminho crítico pelo método CPM (dias corridos): início mais cedo/tarde, folga total; folga 0 = crítico.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from datetime import date, datetime, timedelta
from pathlib import Path

VERSAO = "mv-teste-0.1"
HOJE = lambda: date.today()  # noqa: E731 — trocado nos testes

FRENTES = (
    ("casa", "Casa Physis", "CNPJ comercial: lofts, loja 24h, óleos, restaurante, venda 3D"),
    ("engineering", "Physis Engineering", "Consultoria, engenharia, software e Sistema Physis"),
    ("instituto", "Instituto Physis", "OSC/ICT: PDI, cursos, projetos sociais, Physis 3D (pesquisa)"),
    ("inovastem", "InovaSTEM", "Rede de treinamento, trilhas e InovaSTEM Delas"),
    ("transversal", "Transversal (M&V)", "Jurídico, contábil, lote, marca e o próprio M&V"),
)
ESTADOS = ("a_fazer", "fazendo", "bloqueada", "revisao", "feita")
NOMES_ESTADO = {"a_fazer": "A fazer", "fazendo": "Fazendo", "bloqueada": "Bloqueada", "revisao": "Em revisão", "feita": "Feita"}
GRAVIDADES = ("info", "atencao", "alerta")
# horizonte da Gestão Physis → duração estimada em dias corridos (marcada [CONFERIR])
HORIZONTE_DIAS = {"micro": 7, "meso": 30, "macro": 90}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS mv_frente (id TEXT PRIMARY KEY, nome TEXT NOT NULL, descricao TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS mv_meta (
  id TEXT PRIMARY KEY, frente TEXT NOT NULL, ano INTEGER NOT NULL, titulo TEXT NOT NULL, indicador TEXT NOT NULL DEFAULT '',
  alvo TEXT NOT NULL DEFAULT '', fonte TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS mv_marco (
  id TEXT PRIMARY KEY, frente TEXT NOT NULL, data TEXT NOT NULL, titulo TEXT NOT NULL, meta TEXT, fase TEXT NOT NULL DEFAULT '',
  feito INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS mv_tarefa (
  id TEXT PRIMARY KEY, frente TEXT NOT NULL, projeto TEXT NOT NULL DEFAULT '', titulo TEXT NOT NULL,
  responsavel TEXT NOT NULL DEFAULT '', inicio TEXT, fim TEXT, duracao_d INTEGER NOT NULL DEFAULT 1,
  estado TEXT NOT NULL DEFAULT 'a_fazer', prioridade INTEGER NOT NULL DEFAULT 3, depende_de TEXT NOT NULL DEFAULT '[]',
  meta TEXT, marco TEXT, fonte TEXT NOT NULL DEFAULT '', data_estimada INTEGER NOT NULL DEFAULT 0,
  versao TEXT NOT NULL DEFAULT 'teste', bloqueio TEXT NOT NULL DEFAULT '', origem TEXT NOT NULL DEFAULT 'manual',
  criado REAL NOT NULL, atualizado REAL NOT NULL, concluida_em TEXT);
CREATE TABLE IF NOT EXISTS mv_documento (
  caminho TEXT PRIMARY KEY, nome TEXT NOT NULL, frente TEXT NOT NULL, tipo TEXT NOT NULL, extensao TEXT NOT NULL,
  modificado TEXT NOT NULL, tamanho INTEGER NOT NULL, idade_d INTEGER NOT NULL, validade_d INTEGER NOT NULL,
  versao TEXT NOT NULL DEFAULT '', falhas TEXT NOT NULL DEFAULT '[]', marcadores INTEGER NOT NULL DEFAULT 0,
  situacao TEXT NOT NULL DEFAULT 'ok', visto REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mv_alerta (
  id TEXT PRIMARY KEY, bot TEXT NOT NULL, tipo TEXT NOT NULL, ref TEXT NOT NULL DEFAULT '', frente TEXT NOT NULL DEFAULT '',
  gravidade TEXT NOT NULL, texto TEXT NOT NULL, acao TEXT NOT NULL DEFAULT '', criado REAL NOT NULL, visto REAL NOT NULL,
  resolvido REAL);
CREATE TABLE IF NOT EXISTS mv_lanc (
  id INTEGER PRIMARY KEY AUTOINCREMENT, entidade TEXT NOT NULL, data TEXT NOT NULL, tipo TEXT NOT NULL,
  valor REAL NOT NULL, descricao TEXT NOT NULL DEFAULT '', projeto TEXT NOT NULL DEFAULT '', fonte TEXT NOT NULL DEFAULT '',
  conferido INTEGER NOT NULL DEFAULT 0, criado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mv_execucao (
  id INTEGER PRIMARY KEY AUTOINCREMENT, bot TEXT NOT NULL, inicio REAL NOT NULL, fim REAL, resumo TEXT NOT NULL DEFAULT '',
  erro TEXT NOT NULL DEFAULT '');
"""
ENTIDADES_FIN = ("casa", "engineering", "instituto", "pessoa_fisica")   # nunca somadas entre si (D70)
TIPOS_LANC = ("receita", "despesa", "doacao", "edital", "rateio")
_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def pasta_padrao() -> Path:
    """Banco fora do OneDrive (sincronização corrompe SQLite): PHYSIS_MV_DADOS ou C:/physis/dados."""
    p = Path(os.environ.get("PHYSIS_MV_DADOS") or (Path(__file__).resolve().parents[3] / "dados"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s[:10]) if s and _DATA.match(s[:10]) else None


class ErroMV(ValueError):
    pass


class MV:
    def __init__(self, caminho: str | Path | None = None):
        self.caminho = str(caminho or (pasta_padrao() / "physis-mv.db"))
        self.db = sqlite3.connect(self.caminho, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(ESQUEMA)
        for fid, nome, desc in FRENTES:
            self.db.execute("INSERT OR IGNORE INTO mv_frente VALUES (?,?,?)", (fid, nome, desc))
        self.db.commit()
        self._marca = 0.0

    def nova_rodada(self) -> float:
        """Marca de tempo estritamente crescente por rodada de bot (o relógio do Windows tem ~15 ms de resolução)."""
        self._marca = max(time.time(), self._marca + 0.001)
        return self._marca

    # ------------------------------------------------------------------ tarefas
    def salvar_tarefa(self, t: dict, origem: str = "manual") -> dict:
        tid = str(t.get("id") or "").strip()
        if not _ID.match(tid):
            raise ErroMV("id inválido")
        if t.get("frente") not in dict((f[0], 1) for f in FRENTES):
            raise ErroMV(f"frente inválida: {t.get('frente')}")
        titulo = str(t.get("titulo") or "").strip()
        if not titulo:
            raise ErroMV("título vazio")
        estado = t.get("estado") or "a_fazer"
        if estado not in ESTADOS:
            raise ErroMV("estado inválido")
        for k in ("inicio", "fim"):
            if t.get(k) and not _DATA.match(str(t[k])):
                raise ErroMV(f"{k} deve ser AAAA-MM-DD")
        dep = t.get("depende_de") or []
        if isinstance(dep, str):
            dep = [x for x in re.split(r"[,\s]+", dep) if x]
        ini, fim = _d(t.get("inicio")), _d(t.get("fim"))
        dur = int(t.get("duracao_d") or ((fim - ini).days + 1 if ini and fim else 1))
        if dur < 1:
            raise ErroMV("duração menor que 1 dia")
        agora = time.time()
        ant = self.db.execute("SELECT criado, concluida_em FROM mv_tarefa WHERE id=?", (tid,)).fetchone()
        concl = (ant["concluida_em"] if ant else None) or (HOJE().isoformat() if estado == "feita" else None)
        if estado != "feita":
            concl = None
        self.db.execute(
            """INSERT OR REPLACE INTO mv_tarefa (id,frente,projeto,titulo,responsavel,inicio,fim,duracao_d,estado,prioridade,
               depende_de,meta,marco,fonte,data_estimada,versao,bloqueio,origem,criado,atualizado,concluida_em)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (tid, t["frente"], str(t.get("projeto") or ""), titulo, str(t.get("responsavel") or ""), t.get("inicio"),
             t.get("fim"), dur, estado, int(3 if t.get("prioridade") in (None, "") else t["prioridade"]), json.dumps(dep), t.get("meta"), t.get("marco"),
             str(t.get("fonte") or ""), 1 if t.get("data_estimada") else 0, t.get("versao") or "teste",
             str(t.get("bloqueio") or ""), origem, ant["criado"] if ant else agora, agora, concl))
        self.db.commit()
        return self.tarefa(tid)

    def mudar_estado(self, tid: str, estado: str, bloqueio: str = "") -> dict:
        t = self.tarefa(tid)
        if not t:
            raise ErroMV("tarefa não encontrada")
        t["estado"], t["bloqueio"] = estado, bloqueio if estado == "bloqueada" else ""
        return self.salvar_tarefa(t, t["origem"])

    def tarefa(self, tid: str) -> dict | None:
        r = self.db.execute("SELECT * FROM mv_tarefa WHERE id=?", (tid,)).fetchone()
        return self._tar(r) if r else None

    def tarefas(self, frente: str | None = None) -> list[dict]:
        q, a = "SELECT * FROM mv_tarefa", ()
        if frente:
            q, a = q + " WHERE frente=?", (frente,)
        return [self._tar(r) for r in self.db.execute(q + " ORDER BY prioridade, fim, id", a)]

    @staticmethod
    def _tar(r) -> dict:
        d = dict(r)
        d["depende_de"] = json.loads(d["depende_de"] or "[]")
        return d

    # ------------------------------------------------------------ caminho crítico
    def cpm(self, frente: str | None = None) -> dict:
        """CPM em dias corridos. Âncora: início informado (ou hoje). Devolve por tarefa es/ef/ls/lf/folga e a lista
        de ids críticos. Ciclos de dependência viram erro listado (não quebram o painel)."""
        ts = {t["id"]: t for t in self.tarefas(frente)}
        hoje = HOJE()
        ordem, marca, ciclos = [], {}, []

        def visitar(i, pilha):
            if marca.get(i) == 2:
                return
            if marca.get(i) == 1:
                ciclos.append(" → ".join(pilha + [i]))
                return
            marca[i] = 1
            for d in ts[i]["depende_de"]:
                if d in ts:
                    visitar(d, pilha + [i])
            marca[i] = 2
            ordem.append(i)

        for i in ts:
            visitar(i, [])
        es, ef = {}, {}
        for i in ordem:
            t = ts[i]
            base = _d(t["inicio"]) or hoje
            pred = [ef[d] for d in t["depende_de"] if d in ef]
            ini = max([base] + pred)
            es[i], ef[i] = ini, ini + timedelta(days=t["duracao_d"])
        fim_proj = max(ef.values()) if ef else hoje
        # cadeias = componentes ligados por dependência; o caminho crítico é o mais longo de cada cadeia com 2+ tarefas
        # (tarefa solta não forma caminho). Folga medida contra o fim da própria cadeia.
        suc = {i: [] for i in ts}
        for i in ts:
            for d in ts[i]["depende_de"]:
                if d in suc:
                    suc[d].append(i)
        comp, cid = {}, 0
        for i in ts:
            if i in comp:
                continue
            cid += 1
            pilha = [i]
            while pilha:
                x = pilha.pop()
                if x in comp:
                    continue
                comp[x] = cid
                pilha += [d for d in ts[x]["depende_de"] if d in ts] + suc[x]
        fim_comp, tam_comp = {}, {}
        for i in ordem:
            c = comp[i]
            fim_comp[c] = max(fim_comp.get(c, ef[i]), ef[i])
            tam_comp[c] = tam_comp.get(c, 0) + 1
        ls, lf = {}, {}
        for i in reversed(ordem):
            s = [ls[x] for x in suc[i] if x in ls]
            lf[i] = min([fim_comp[comp[i]]] + s)
            ls[i] = lf[i] - timedelta(days=ts[i]["duracao_d"])
        res = {}
        for i in ordem:
            folga = (ls[i] - es[i]).days
            prazo = _d(ts[i]["fim"])
            fim_plan = ef[i] - timedelta(days=1)
            res[i] = {"es": es[i].isoformat(), "ef": fim_plan.isoformat(), "ls": ls[i].isoformat(),
                      "lf": (lf[i] - timedelta(days=1)).isoformat(), "folga": folga, "cadeia": comp[i],
                      "critico": folga <= 0 and tam_comp[comp[i]] > 1 and ts[i]["estado"] != "feita",
                      # as dependências empurram o fim planejado para depois do prazo informado
                      "prazo_em_risco": bool(prazo and fim_plan > prazo and ts[i]["estado"] != "feita"),
                      "estouro_d": (fim_plan - prazo).days if prazo and fim_plan > prazo else 0}
        return {"tarefas": res, "criticos": [i for i in ordem if res[i]["critico"]], "ciclos": ciclos,
                "em_risco": [i for i in ordem if res[i]["prazo_em_risco"]],
                "fim_previsto": (fim_proj - timedelta(days=1)).isoformat()}

    # --------------------------------------------------------------- visões
    def atrasada(self, t: dict, hoje: date | None = None) -> bool:
        f = _d(t["fim"])
        return bool(f and f < (hoje or HOJE()) and t["estado"] != "feita")

    def gantt(self, frente: str | None = None) -> list[dict]:
        c = self.cpm(frente)["tarefas"]
        out = []
        for t in self.tarefas(frente):
            k = c.get(t["id"], {})
            out.append({**t, "plan_inicio": k.get("es"), "plan_fim": k.get("ef"), "folga": k.get("folga"),
                        "critico": k.get("critico", False), "atrasada": self.atrasada(t),
                        "prazo_em_risco": k.get("prazo_em_risco", False), "estouro_d": k.get("estouro_d", 0)})
        return sorted(out, key=lambda x: (x["frente"], x["plan_inicio"] or "", x["id"]))

    def kanban(self, frente: str | None = None) -> dict:
        col = {e: [] for e in ESTADOS}
        for t in self.tarefas(frente):
            col[t["estado"]].append({**t, "atrasada": self.atrasada(t)})
        return col

    def matriz(self) -> dict:
        """Pendências por pessoa × frente: abertas / atrasadas / bloqueadas."""
        m: dict[str, dict[str, dict[str, int]]] = {}
        for t in self.tarefas():
            if t["estado"] == "feita":
                continue
            for p in [x.strip() for x in (t["responsavel"] or "(sem responsável)").split(",") if x.strip()][:1]:
                c = m.setdefault(p, {}).setdefault(t["frente"], {"abertas": 0, "atrasadas": 0, "bloqueadas": 0})
                c["abertas"] += 1
                c["atrasadas"] += self.atrasada(t)
                c["bloqueadas"] += t["estado"] == "bloqueada"
        return m

    def roadmap(self) -> dict:
        metas = [dict(r) for r in self.db.execute("SELECT * FROM mv_meta ORDER BY ano, frente")]
        marcos = [dict(r) for r in self.db.execute("SELECT * FROM mv_marco ORDER BY data")]
        # quantas tarefas abertas sustentam cada meta (correlação tarefa → meta de 5 anos)
        n = {}
        for t in self.tarefas():
            if t["meta"]:
                n.setdefault(t["meta"], [0, 0])
                n[t["meta"]][0] += 1
                n[t["meta"]][1] += t["estado"] == "feita"
        for m in metas:
            m["tarefas"], m["feitas"] = n.get(m["id"], [0, 0])
        sem_meta = sum(1 for t in self.tarefas() if not t["meta"] and t["estado"] != "feita")
        return {"metas": metas, "marcos": marcos, "tarefas_sem_meta": sem_meta, "horizonte": "2027–2031"}

    def saude(self) -> dict:
        hoje = HOJE()
        risco = set(self.cpm()["em_risco"])
        por = {}
        for fid, nome, _ in FRENTES:
            ts = self.tarefas(fid)
            tot = len(ts)
            feitas = sum(t["estado"] == "feita" for t in ts)
            atras = sum(self.atrasada(t, hoje) for t in ts)
            bloq = sum(t["estado"] == "bloqueada" for t in ts)
            est = sum(t["data_estimada"] for t in ts if t["estado"] != "feita")
            emr = sum(t["id"] in risco for t in ts)
            # nota 0–100: começa em 100 e perde, proporcionalmente às abertas, até 50 por atraso, 30 por bloqueio e
            # 20 por prazo em risco (regra simples, explicada na tela)
            abertas = max(1, tot - feitas)
            nota = 100 if tot == 0 else max(0, round(100 - 50 * atras / abertas - 30 * bloq / abertas - 20 * emr / abertas))
            por[fid] = {"nome": nome, "total": tot, "feitas": feitas, "atrasadas": atras, "bloqueadas": bloq, "em_risco": emr,
                        "datas_estimadas": est, "nota": nota,
                        "progresso_pct": round(100 * feitas / tot, 1) if tot else 0.0}
        docs = self.db.execute("SELECT situacao, COUNT(*) n FROM mv_documento GROUP BY situacao").fetchall()
        al = self.db.execute("SELECT gravidade, COUNT(*) n FROM mv_alerta WHERE resolvido IS NULL GROUP BY gravidade").fetchall()
        return {"hoje": hoje.isoformat(), "versao": VERSAO, "frentes": por,
                "documentos": {r["situacao"]: r["n"] for r in docs}, "alertas_abertos": {r["gravidade"]: r["n"] for r in al},
                "financeiro": self.financeiro(), "ultima_execucao": self.ultima_execucao()}

    # ------------------------------------------------------------ financeiro
    def lancar(self, l: dict) -> int:
        if l.get("entidade") not in ENTIDADES_FIN:
            raise ErroMV("entidade inválida")
        if l.get("tipo") not in TIPOS_LANC:
            raise ErroMV("tipo inválido")
        if not _DATA.match(str(l.get("data") or "")):
            raise ErroMV("data deve ser AAAA-MM-DD")
        v = float(l["valor"])
        cur = self.db.execute(
            "INSERT INTO mv_lanc (entidade,data,tipo,valor,descricao,projeto,fonte,conferido,criado) VALUES (?,?,?,?,?,?,?,?,?)",
            (l["entidade"], l["data"], l["tipo"], v, str(l.get("descricao") or ""), str(l.get("projeto") or ""),
             str(l.get("fonte") or ""), 1 if l.get("conferido") else 0, time.time()))
        self.db.commit()
        return cur.lastrowid

    def financeiro(self) -> dict:
        """Por entidade, nunca somado entre entidades. 'oficial' só com conferência do contador (D70)."""
        out = {}
        for e in ENTIDADES_FIN:
            rs = self.db.execute("SELECT tipo, conferido, SUM(valor) s, COUNT(*) n FROM mv_lanc WHERE entidade=? "
                                 "GROUP BY tipo, conferido", (e,)).fetchall()
            d = {"oficial": {}, "a_conferir": {}, "lancamentos": 0}
            for r in rs:
                d["oficial" if r["conferido"] else "a_conferir"][r["tipo"]] = round(r["s"], 2)
                d["lancamentos"] += r["n"]
            out[e] = d
        return out

    # ------------------------------------------------------------ alertas e bots
    def alertar(self, bot: str, tipo: str, ref: str, gravidade: str, texto: str, acao: str = "", frente: str = "") -> str:
        """Idempotente por (bot, tipo, ref): o mesmo problema não vira alerta repetido; reaparece se tinha sido resolvido."""
        if gravidade not in GRAVIDADES:
            raise ErroMV("gravidade inválida")
        aid = f"{bot}:{tipo}:{ref}"[:200]
        agora = max(time.time(), self._marca)
        ant = self.db.execute("SELECT id FROM mv_alerta WHERE id=?", (aid,)).fetchone()
        if ant:
            self.db.execute("UPDATE mv_alerta SET texto=?, acao=?, gravidade=?, visto=?, resolvido=NULL WHERE id=?",
                            (texto, acao, gravidade, agora, aid))
        else:
            self.db.execute("INSERT INTO mv_alerta VALUES (?,?,?,?,?,?,?,?,?,?,NULL)",
                            (aid, bot, tipo, ref, frente, gravidade, texto, acao, agora, agora))
        self.db.commit()
        return aid

    def fechar_alertas_nao_vistos(self, bot: str, desde: float) -> int:
        """Alertas do bot que não reapareceram nesta rodada foram resolvidos."""
        c = self.db.execute("UPDATE mv_alerta SET resolvido=? WHERE bot=? AND resolvido IS NULL AND visto<?",
                            (time.time(), bot, desde))
        self.db.commit()
        return c.rowcount

    def alertas(self, abertos: bool = True) -> list[dict]:
        q = "SELECT * FROM mv_alerta" + (" WHERE resolvido IS NULL" if abertos else "")
        ordem = "CASE gravidade WHEN 'alerta' THEN 0 WHEN 'atencao' THEN 1 ELSE 2 END"
        return [dict(r) for r in self.db.execute(q + f" ORDER BY {ordem}, criado DESC")]

    def registrar_execucao(self, bot: str, inicio: float, resumo: str = "", erro: str = "") -> None:
        self.db.execute("INSERT INTO mv_execucao (bot,inicio,fim,resumo,erro) VALUES (?,?,?,?,?)",
                        (bot, inicio, time.time(), resumo, erro))
        self.db.commit()

    def ultima_execucao(self) -> dict:
        out = {}
        for r in self.db.execute("SELECT bot, MAX(fim) f, resumo, erro FROM mv_execucao GROUP BY bot"):
            out[r["bot"]] = {"quando": datetime.fromtimestamp(r["f"]).isoformat(timespec="minutes") if r["f"] else None,
                             "resumo": r["resumo"], "erro": r["erro"]}
        return out

    def documentos(self) -> list[dict]:
        rs = self.db.execute("SELECT * FROM mv_documento ORDER BY CASE situacao WHEN 'falha' THEN 0 WHEN 'vencido' THEN 1 "
                             "ELSE 2 END, idade_d DESC")
        return [{**dict(r), "falhas": json.loads(r["falhas"])} for r in rs]

    # ------------------------------------------------------------ importação
    def importar_gestao(self, caminho: str | Path, inicio: date | None = None, frente: str = "engineering") -> int:
        """Importa a exportação physis/1 de uma Gestão (tabelas pessoa, projeto, tarefa) para a `frente` dada.
        A Gestão da Physis Engineering vai para "engineering"; as tarefas tiradas do sistema da Physis em 18/11/2026
        (gestao-tarefas-do-instituto.json) vão para "instituto" e saem da frente engineering. Sem datas na origem:
        o horizonte vira prazo estimado a partir de `inicio` e fica data_estimada=1 ([CONFERIR])."""
        if frente not in dict((f[0], 1) for f in FRENTES):
            raise ErroMV(f"frente inválida: {frente}")
        meta_padrao = {"engineering": "m-eng-sistema", "instituto": "m-inst-ict"}.get(frente)
        d = json.loads(Path(caminho).read_text(encoding="utf-8"))
        tb = d.get("tabelas") or {}
        pes = {p["pessoa_id"]: p.get("nome") or p["pessoa_id"] for p in tb.get("pessoa", [])}
        proj = {p["projeto_id"]: p.get("nome") or "" for p in tb.get("projeto", [])}
        ini = inicio or HOJE()
        n = 0
        for t in tb.get("tarefa", []):
            hz = t.get("horizonte") or "meso"
            dias = HORIZONTE_DIAS.get(hz, 30)
            pr = (t.get("extras") or {}).get("prioridade")
            tid = "gestao:" + str(t["tarefa_id"])
            ant = self.tarefa(tid)
            estado = "feita" if t.get("concluida") else (ant["estado"] if ant else "a_fazer")
            dep = ["gestao:" + str(t["depende_de"])] if t.get("depende_de") else []
            self.salvar_tarefa({
                "id": tid, "frente": frente, "projeto": proj.get(t.get("projeto_id"), ""),
                "titulo": t.get("titulo") or "(sem título)", "responsavel": pes.get(t.get("pessoa_id"), t.get("pessoa_id") or ""),
                "inicio": ini.isoformat(), "fim": (ini + timedelta(days=dias - 1)).isoformat(), "duracao_d": dias,
                "estado": estado, "prioridade": 0 if pr == 0 else (2 if hz == "micro" else 3 if hz == "meso" else 4),
                "depende_de": dep, "fonte": f"Gestão ({Path(caminho).name})",
                "data_estimada": True,
                "meta": ((ant or {}).get("meta") if (ant or {}).get("frente") == frente else None) or meta_padrao},
                origem="gestao")
            n += 1
        return n

    def ausentes_da_gestao(self, caminho: str | Path, frente: str = "engineering") -> list[str]:
        """Tarefas vindas da Gestão (origem "gestao") desta frente que não estão mais no arquivo: só lista, não apaga."""
        d = json.loads(Path(caminho).read_text(encoding="utf-8"))
        ids = {"gestao:" + str(t["tarefa_id"]) for t in (d.get("tabelas") or {}).get("tarefa", [])}
        rs = self.db.execute("SELECT id FROM mv_tarefa WHERE origem='gestao' AND frente=?", (frente,))
        return sorted(r["id"] for r in rs if r["id"] not in ids)
