"""Editais no Physis M&V (VERSÃO DE TESTE, 18/11/2026; D47, D81, D85–D87; doc 31).

Cada edital do banco (Sistema Physis/31_Editais/banco_editais.csv) vira uma ficha com:
- dados do edital (prazo, financiador, frente, aderência, via parceria, link, fonte verificada);
- etapa da proposta: triagem → decidir → preparar → revisão → enviada → resultado (aprovada/reprovada) ou arquivada;
- **necessidades**: checklist gerado a partir dos documentos exigidos, das exigências formais, do parceiro necessário e dos
  documentos-padrão (doc 31), com estado de cada item e responsável;
- decisão, responsável, notas e perguntas pendentes à dona.
Nada é enviado para fora: a etapa "enviada" só é marcada por uma pessoa.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path

from . import mv as mvmod
from .mv import MV, ErroMV

ETAPAS = ("triagem", "decidir", "preparar", "revisao", "enviada", "aprovada", "reprovada", "arquivada")
NOMES_ETAPA = {"triagem": "Triagem", "decidir": "Decidir", "preparar": "Preparar", "revisao": "Em revisão", "enviada": "Enviada",
               "aprovada": "Aprovada", "reprovada": "Reprovada", "arquivada": "Arquivada"}
ESQUEMA = """
CREATE TABLE IF NOT EXISTS mv_edital (
  id TEXT PRIMARY KEY, titulo TEXT NOT NULL, financiador TEXT NOT NULL DEFAULT '', link TEXT NOT NULL DEFAULT '',
  tipo TEXT NOT NULL DEFAULT '', prazo TEXT NOT NULL DEFAULT '', valor TEXT NOT NULL DEFAULT '', moeda TEXT NOT NULL DEFAULT '',
  quem_pode TEXT NOT NULL DEFAULT '', territorio TEXT NOT NULL DEFAULT '', temas TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT '', frente TEXT NOT NULL DEFAULT '', aderencia TEXT NOT NULL DEFAULT '', motivo TEXT NOT NULL DEFAULT '',
  proxima_acao TEXT NOT NULL DEFAULT '', verificado INTEGER NOT NULL DEFAULT 0, via_parceria INTEGER NOT NULL DEFAULT 0,
  perfil_parceiro TEXT NOT NULL DEFAULT '', recorrencia TEXT NOT NULL DEFAULT '', proxima_edicao TEXT NOT NULL DEFAULT '',
  criterios TEXT NOT NULL DEFAULT '', licao TEXT NOT NULL DEFAULT '', origem TEXT NOT NULL DEFAULT '',
  etapa TEXT NOT NULL DEFAULT 'triagem', decisao TEXT NOT NULL DEFAULT '', responsavel TEXT NOT NULL DEFAULT '',
  notas TEXT NOT NULL DEFAULT '', perguntas TEXT NOT NULL DEFAULT '[]', necessidades TEXT NOT NULL DEFAULT '[]',
  criado REAL NOT NULL, atualizado REAL NOT NULL);
"""
# documentos-padrão mais pedidos (doc 31): entram em toda proposta que vai ser preparada
PADRAO = ["Cartão CNPJ e contrato social/estatuto", "Certidões (federal, estadual, municipal, FGTS, trabalhista) válidas",
          "CVs/Lattes da equipe no formato pedido", "Atestados de capacidade técnica e portfólio do tema",
          "Proposta técnica e orçamento (PT/EN conforme o edital)", "Revisão final e autorização da dona antes do envio"]
_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")


def _sim(v: str) -> int:
    return 1 if str(v).strip().lower() in ("sim", "s", "yes", "true", "1") else 0


def necessidades_de(r: dict) -> list[dict]:
    itens, vistos = [], set()

    def add(txt, origem):
        t = re.sub(r"\s+", " ", txt).strip(" ;.-")
        k = t.lower()[:60]
        if t and t.lower() not in ("nao_informado", "nao informado") and k not in vistos:
            vistos.add(k)
            itens.append({"id": hashlib.sha1(k.encode()).hexdigest()[:8], "item": t[:240], "origem": origem, "feito": False,
                          "responsavel": ""})
    for p in re.split(r"[|;]", r.get("documentos_exigidos", "")):
        add(p, "documento exigido")
    for p in re.split(r"[|;]", r.get("exigencias_formais", "")):
        add(p, "exigência formal")
    if _sim(r.get("via_parceria", "")):
        add(f"Parceiro: {r.get('perfil_parceiro') or 'definir perfil'} (carta de interesse/acordo)", "parceria")
    for p in PADRAO:
        add(p, "documento-padrão")
    return itens


class Editais:
    def __init__(self, mv: MV):
        self.mv = mv
        mv.db.executescript(ESQUEMA)
        mv.db.commit()

    def importar_csv(self, caminho: str | Path) -> dict:
        """Importa o banco consolidado. Mantém etapa, decisão, notas e necessidades já trabalhadas."""
        n_novo = n_atual = 0
        agora = time.time()
        for r in csv.DictReader(open(caminho, encoding="utf-8-sig"), delimiter=";"):
            eid = "ed:" + hashlib.sha1((r.get("chave") or r.get("titulo", "")).encode()).hexdigest()[:10]
            ant = self.mv.db.execute("SELECT * FROM mv_edital WHERE id=?", (eid,)).fetchone()
            campos = dict(titulo=r.get("titulo", "")[:300] or "(sem título)", financiador=r.get("financiador", ""), link=r.get("link", ""),
                          tipo=r.get("tipo", ""), prazo=r.get("prazo", ""), valor=r.get("valor", ""), moeda=r.get("moeda", ""),
                          quem_pode=r.get("quem_pode_propor", ""), territorio=r.get("restricao_territorial", ""), temas=r.get("temas", ""),
                          status=r.get("status", ""), frente=r.get("frente_mais_aderente", ""), aderencia=r.get("aderencia", ""),
                          motivo=r.get("motivo", ""), proxima_acao=r.get("proxima_acao", ""), verificado=_sim(r.get("fonte_verificada", "")),
                          via_parceria=_sim(r.get("via_parceria", "")), perfil_parceiro=r.get("perfil_parceiro", ""),
                          recorrencia=r.get("recorrencia", ""), proxima_edicao=r.get("proxima_edicao_prevista", ""),
                          criterios=r.get("criterios_avaliacao_pesos", ""), licao=r.get("licao_para_physis", ""),
                          origem=r.get("origem_busca", ""))
            if ant:
                sets = ", ".join(f"{k}=?" for k in campos)
                self.mv.db.execute(f"UPDATE mv_edital SET {sets}, atualizado=? WHERE id=?", (*campos.values(), agora, eid))
                if ant["necessidades"] == "[]":
                    self.mv.db.execute("UPDATE mv_edital SET necessidades=? WHERE id=?", (json.dumps(necessidades_de(r), ensure_ascii=False), eid))
                n_atual += 1
            else:
                etapa = "decidir" if campos["status"] == "aberto" and campos["aderencia"] in ("alta", "media") else \
                        ("arquivada" if campos["aderencia"] == "inelegivel" else "triagem")
                cols = list(campos) + ["etapa", "necessidades", "criado", "atualizado", "id"]
                self.mv.db.execute(f"INSERT INTO mv_edital ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                                   (*campos.values(), etapa, json.dumps(necessidades_de(r), ensure_ascii=False), agora, agora, eid))
                n_novo += 1
        self.mv.db.commit()
        return {"novos": n_novo, "atualizados": n_atual}

    def listar(self) -> list[dict]:
        hoje = mvmod.HOJE()
        out = []
        for r in self.mv.db.execute("SELECT * FROM mv_edital"):
            d = dict(r)
            d["necessidades"] = json.loads(d["necessidades"])
            d["perguntas"] = json.loads(d["perguntas"])
            m = re.match(r"(\d{4}-\d{2}-\d{2})", d["prazo"])
            d["dias"] = (date.fromisoformat(m.group(1)) - hoje).days if m else None
            tot = len(d["necessidades"])
            d["pronto_pct"] = round(100 * sum(1 for x in d["necessidades"] if x["feito"]) / tot) if tot else 0
            out.append(d)
        ordem = {"alta": 0, "media": 1, "baixa": 2, "inelegivel": 3}
        return sorted(out, key=lambda d: (d["etapa"] in ("arquivada", "reprovada"), d["dias"] is None or d["dias"] < 0,
                                         d["dias"] if d["dias"] is not None else 9999, ordem.get(d["aderencia"], 4)))

    def atualizar(self, eid: str, dados: dict) -> dict:
        if not _ID.match(eid or ""):
            raise ErroMV("id inválido")
        r = self.mv.db.execute("SELECT * FROM mv_edital WHERE id=?", (eid,)).fetchone()
        if not r:
            raise ErroMV("edital não encontrado")
        upd = {}
        if "etapa" in dados:
            if dados["etapa"] not in ETAPAS:
                raise ErroMV("etapa inválida")
            upd["etapa"] = dados["etapa"]
        for k in ("decisao", "responsavel", "notas"):
            if k in dados:
                upd[k] = str(dados[k])[:4000]
        if "necessidade" in dados:                     # {"id", "feito"?, "responsavel"?} ou {"novo": "texto"}
            nec = json.loads(r["necessidades"])
            x = dados["necessidade"]
            if x.get("novo"):
                t = str(x["novo"]).strip()[:240]
                nec.append({"id": hashlib.sha1((t + str(time.time())).encode()).hexdigest()[:8], "item": t, "origem": "manual",
                            "feito": False, "responsavel": str(x.get("responsavel", ""))})
            else:
                for it in nec:
                    if it["id"] == x.get("id"):
                        if "feito" in x:
                            it["feito"] = bool(x["feito"])
                        if "responsavel" in x:
                            it["responsavel"] = str(x["responsavel"])[:80]
            upd["necessidades"] = json.dumps(nec, ensure_ascii=False)
        if "pergunta" in dados:
            pq = json.loads(r["perguntas"])
            pq.append({"texto": str(dados["pergunta"])[:1000], "resposta": "", "quando": date.today().isoformat()})
            upd["perguntas"] = json.dumps(pq, ensure_ascii=False)
        if not upd:
            raise ErroMV("nada para atualizar")
        sets = ", ".join(f"{k}=?" for k in upd)
        self.mv.db.execute(f"UPDATE mv_edital SET {sets}, atualizado=? WHERE id=?", (*upd.values(), time.time(), eid))
        self.mv.db.commit()
        return next(d for d in self.listar() if d["id"] == eid)

    def planilha(self) -> list[dict]:
        """Tabelas para o ODS: propostas em andamento, necessidades item a item, e o banco inteiro."""
        eds = self.listar()
        ativos = [d for d in eds if d["etapa"] in ("decidir", "preparar", "revisao", "enviada")]
        cab = ["Prazo", "Dias", "Etapa", "Título", "Financiador", "Frente", "Aderência", "Valor", "Via parceria", "Perfil do parceiro",
               "Pronto %", "Responsável", "Decisão", "Próxima ação", "Critérios e pesos", "Link", "Verificado"]
        lin = lambda d: [d["prazo"], "" if d["dias"] is None else d["dias"], NOMES_ETAPA[d["etapa"]], d["titulo"], d["financiador"],
                         d["frente"], d["aderencia"], f'{d["valor"]} {d["moeda"]}'.strip(), "sim" if d["via_parceria"] else "não",
                         d["perfil_parceiro"], f'{d["pronto_pct"]}%', d["responsavel"], d["decisao"], d["proxima_acao"], d["criterios"],
                         d["link"], "sim" if d["verificado"] else "não"]
        nec = [[d["prazo"], d["titulo"], it["item"], it["origem"], "feito" if it["feito"] else "pendente", it["responsavel"]]
               for d in ativos for it in d["necessidades"]]
        return [{"nome": "Propostas em andamento", "cab": cab, "linhas": [lin(d) for d in ativos]},
                {"nome": "Necessidades por proposta", "cab": ["Prazo", "Edital", "Necessidade", "Origem", "Situação", "Responsável"], "linhas": nec},
                {"nome": "Banco completo", "cab": cab, "linhas": [lin(d) for d in eds]}]
