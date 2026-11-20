"""Clientes, projetos e parceiros no Physis M&A (VERSÃO DE TESTE, 20/11/2026; pedido da dona: "abas de projetos/clientes/parceiros
com plataformas individuais e um sistema de inserção para projetos futuros, com aba para upload de documentos e bots para análises
e preenchimento de informações, a serem confirmadas para estabelecer o projeto"; mapeamento financeiro "por CNPJ, por clientes, por
projetos, por sistemas vendidos, por lojas online e por membros da equipe", e-mails ao contador como rascunho).

Regras:
- toda conta (cliente, parceiro, projeto interno ou futuro) tem uma ficha com o que precisa ser esclarecido no início (CNPJ emissor,
  regime, base contratual, moeda, impostos, template) e um RESUMO A CONFERIR; o que o bot preenche entra como "proposto" e só vale
  depois de confirmado por uma pessoa;
- template: cliente = só logo, fontes e paleta do cliente; parceria = logos juntas e cores intermediárias; interno = Physis;
- valores nunca inventados: [MARCADOR]; impostos com [CONFERIR] até o contador (Robson) confirmar;
- e-mail ao contador = RASCUNHO na fila de bots; nada é enviado.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import time
from datetime import date

from . import mv_comandos
from .mv import MV, ErroMV

ESQUEMA = """
CREATE TABLE IF NOT EXISTS mv_cnpj (
  id TEXT PRIMARY KEY, nome TEXT NOT NULL, cnpj TEXT NOT NULL DEFAULT '[MARCADOR]', regime TEXT NOT NULL DEFAULT '[CONFERIR]',
  municipio TEXT NOT NULL DEFAULT '', impostos TEXT NOT NULL DEFAULT '', situacao TEXT NOT NULL DEFAULT 'provisorio', nota TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS mv_conta (
  id TEXT PRIMARY KEY, nome TEXT NOT NULL, tipo TEXT NOT NULL, frente TEXT NOT NULL DEFAULT 'engineering',
  cnpj_emissor TEXT NOT NULL DEFAULT 'physis-eng', contrato TEXT NOT NULL DEFAULT '', moeda TEXT NOT NULL DEFAULT 'BRL',
  impostos TEXT NOT NULL DEFAULT '', template TEXT NOT NULL DEFAULT 'physis', cores TEXT NOT NULL DEFAULT '[]',
  core TEXT NOT NULL DEFAULT '', responsavel TEXT NOT NULL DEFAULT '', contato TEXT NOT NULL DEFAULT '[MARCADOR]',
  estado TEXT NOT NULL DEFAULT 'ativo', proximos TEXT NOT NULL DEFAULT '', propostas TEXT NOT NULL DEFAULT '{}',
  criado REAL NOT NULL, atualizado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mv_subprojeto (
  id TEXT PRIMARY KEY, conta TEXT NOT NULL, nome TEXT NOT NULL, escopo TEXT NOT NULL DEFAULT '[MARCADOR]',
  contrato TEXT NOT NULL DEFAULT '[MARCADOR]', valor TEXT NOT NULL DEFAULT '[MARCADOR]', fases TEXT NOT NULL DEFAULT '[]',
  prazo TEXT NOT NULL DEFAULT '', estado TEXT NOT NULL DEFAULT 'a_definir', criado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mv_palavra (palavra TEXT NOT NULL, conta TEXT NOT NULL, PRIMARY KEY (palavra, conta));
"""
PARADAS = set("para com sem pela pelo pelos pelas uma umas uns como mais menos entre sobre ainda depois antes cada todo toda todos "
              "todas outro outra projeto projetos cliente clientes contrato direto modulo modulos módulo módulos marcador conferir "
              "plataforma sistema physis fase fases versao versão final interna loja".split())
TIPOS = {"cliente_direto": "Cliente · contrato direto", "cliente_loja": "Cliente da plataforma (loja)", "parceiro": "Parceria",
         "interno": "Projeto interno", "futuro": "Projeto futuro (em cadastro)", "anterior": "Projeto anterior (concluído)"}
DOCS_RAIZ = Path.home() / "OneDrive - Physis Engineering" / "Documents"
# grupos de palavras que identificam projetos anteriores nos nomes de arquivos/pastas (o bot PROPÕE; a dona confirma)
GRUPOS_ANTERIORES = [
    ("GIZ ADVANCE · Egito (eficiência de recursos)", ["giz advance", "egypt", "sharky", "lion tex", "energya", "marcyrl"], "GIZ", "Egito"),
    ("WWF · MecfinUC (proposta técnica e comercial)", ["wwf", "mecfinuc"], "WWF", "Brasil"),
    ("PHES · Jordânia (proposta técnica)", ["phes", "jordan"], "[CONFERIR]", "Jordânia"),
    ("Palestina (relatórios de empresas)", ["palestine", "al hana", "al-taj", "alhana", "alnkhubah", "ahmadakram", "gbs_stones"], "[CONFERIR]", "Palestina"),
    ("Botuporã-BA", ["botupor"], "[CONFERIR]", "Brasil"),
    ("EMS · treinamento WP2", ["ems", "wp2-ems"], "[CONFERIR]", "[CONFERIR]"),
    ("OLACDE · curso H2V", ["olacde", "h2v"], "OLACDE", "[CONFERIR]"),
    ("EPC · ToR 81319865", ["81319865", "tor for epc"], "[CONFERIR]", "[CONFERIR]"),
    ("FAETEC · apresentação DIC", ["faetec"], "FAETEC", "Brasil"),
]
TEMPLATES = {"cliente": "Só logo, fontes e paleta do cliente", "parceria": "Logos juntas e cores intermediárias (inclui Physis)",
             "physis": "Identidade Physis (tipo B/A)"}
FASES_PADRAO = ["Fase 0 · diagnóstico", "Fase 1 · projeto", "Fase 2 · entrega", "Fase 3 · acompanhamento"]
_ID = re.compile(r"^[a-z0-9-]{2,60}$")

CNPJS = [
    {"id": "physis-eng", "nome": "Physis Engineering", "cnpj": "44.982.448/0001-23", "regime": "Simples Nacional",
     "municipio": "Petrópolis/RJ", "impostos": "DAS do Simples (anexo e fator R: [CONFERIR] com o Robson); ISS no DAS; exportação de serviço: [CONFERIR]",
     "situacao": "provisorio", "nota": "CNPJ e razão social 'Physis Engineering Ltda.' a confirmar nos documentos (dona, 20/11: Simples Nacional)"},
    {"id": "casa", "nome": "Casa Physis", "situacao": "a_abrir", "nota": "CNPJ a abrir (D60); sócios D33"},
    {"id": "instituto", "nome": "Instituto Physis", "situacao": "a_abrir", "nota": "OSC/ICT em fundação; CNPJ previsto fev/2027 (Kit 17) [CONFERIR]"},
    {"id": "pessoa-fisica", "nome": "Pessoa física (Lote 168)", "cnpj": "não se aplica", "regime": "IRPF", "situacao": "ativo",
     "nota": "Lote 168 até a escritura (D68)"},
]
CONTAS = [
    {"id": "giz-ptx", "nome": "GIZ PtX", "tipo": "cliente_direto", "contrato": "Contratada direto pela GIZ (invoice; exportação de serviço)",
     "moeda": "EUR", "impostos": "Exportação de serviço no Simples: [CONFERIR] com o Robson", "template": "cliente",
     "core": "Power-to-X (PtX): [MARCADOR] escopo do contrato com a GIZ", "proximos": "Confirmar escopo, fases e invoice"},
    {"id": "estermic", "nome": "Estermic", "tipo": "cliente_direto", "contrato": "Contrato direto no Brasil (PJ → PJ, NF de serviço, ISS)",
     "moeda": "BRL", "impostos": "NF de serviço pelo Simples (ISS no DAS) [CONFERIR]", "template": "cliente", "responsavel": "Ryan (equipe Physis, cocriação)",
     "core": "Projetos AVAC personalizados (cópia do módulo AVAC): BIM, GIS, fabricantes, IFC, lista de equipamentos, relatório e memorial de cálculo",
     "proximos": "Versão final interna ao Ryan 23/11 13h59; prioridade 0 até 24/11 (doc 44)"},
    {"id": "gsa", "nome": "Global South Alliance", "tipo": "parceiro", "frente": "transversal", "contrato": "Parceria (documentos na pasta de projetos)", "template": "parceria",
     "core": "Aliança Sul Global (concept note GS Alliance × AWPI, 19/10/2026)", "proximos": "Alimentar após a reunião de alinhamento de 25/11"},
    {"id": "rede-tacas-turbinas", "nome": "Rede Taças e Turbinas", "tipo": "parceiro", "frente": "inovastem", "contrato": "Parceria com contrato/patrocínio [MARCADOR] valores",
     "template": "parceria", "core": "Eventos: aula de empreendedorismo com estruturas de PDI e apresentação da Physis / lançamento 0 da InovaSTEM",
     "responsavel": "Rafaella (aprova)", "proximos": "21/11: revisão interna 14h, envio externo 18h"},
    {"id": "fazenda-mf", "nome": "Fazenda MF", "tipo": "cliente_loja", "contrato": "Cliente da plataforma (módulos da loja)", "template": "cliente",
     "core": "Módulos da plataforma (ex.: SustainKit, SCADA, monitoramento): [MARCADOR] quais", "proximos": "Confirmar módulos contratados"},
    {"id": "fazenda-santa-clara", "nome": "Fazenda Santa Clara", "tipo": "cliente_loja", "contrato": "Cliente da plataforma (módulos da loja)",
     "template": "cliente", "core": "Plataforma do cliente com demos existentes (physis-demo-santa-clara, v2)", "proximos": "Confirmar módulos e dados reais"},
]


class Clientes:
    def __init__(self, mv: MV):
        self.mv = mv
        mv.db.executescript(ESQUEMA)
        cols = {r[1] for r in mv.db.execute("PRAGMA table_info(mv_lanc)")}
        for c in ("conta", "subprojeto", "sistema", "loja", "membro", "cnpj_emissor", "contrato", "nf"):
            if c not in cols:                       # migração simples: níveis do mapeamento financeiro (20/11/2026)
                mv.db.execute(f"ALTER TABLE mv_lanc ADD COLUMN {c} TEXT NOT NULL DEFAULT ''")
        mv.db.commit()

    # ------------------------------------------------------------ semente
    # ------------------------------------------------------------ integração automática (dona, 20/11/2026)
    def integrar(self, cid: str) -> dict:
        """Todo projeto/cliente/parceiro adicionado entra sozinho no monitoramento: tarefa de ficha (Visão geral, Cronograma,
        Projetos, Tarefas, Pendências), tarefas dos subprojetos, alerta do que falta esclarecer e palavras-chave nos editais."""
        import unicodedata
        c = self.conta(cid)
        pend = [r["item"] for r in c["resumo"] if r["pendente"]]
        if c["tipo"] == "anterior":           # projeto concluído: só palavras-chave (editais) e portfólio; sem tarefas nem alertas
            pend = []
        fr = c["frente"] if c["frente"] in ("casa", "engineering", "instituto", "inovastem", "transversal") else "engineering"
        tid = f"conta-{cid}-ficha"
        ant = self.mv.tarefa(tid)
        if c["tipo"] != "anterior":
          self.mv.salvar_tarefa({"id": tid, "frente": fr, "projeto": c["nome"],
                               "titulo": f"{c['nome']}: esclarecer a ficha ({len(pend)} item(ns): {', '.join(pend) or 'nenhum'})",
                               "responsavel": c["responsavel"] or "Rafaella", "estado": "feita" if not pend else (ant["estado"] if ant and ant["estado"] != "feita" else "a_fazer"),
                               "inicio": (ant or {}).get("inicio") or date.today().isoformat(), "fim": (ant or {}).get("fim"),
                               "duracao_d": (ant or {}).get("duracao_d") or 7, "data_estimada": True, "fonte": "Clientes e projetos (M&A)"},
                              origem="conta")
        for s in c["subprojetos"]:
            sid = f"conta-{s['id']}"
            a2 = self.mv.tarefa(sid)
            self.mv.salvar_tarefa({"id": sid, "frente": fr, "projeto": c["nome"], "titulo": f"{s['nome']}: definir escopo, contrato e fases",
                                   "responsavel": c["responsavel"] or "Rafaella", "estado": (a2 or {}).get("estado") or "a_fazer",
                                   "inicio": (a2 or {}).get("inicio") or date.today().isoformat(), "fim": (a2 or {}).get("fim"),
                                   "duracao_d": (a2 or {}).get("duracao_d") or 14, "data_estimada": True, "depende_de": [tid],
                                   "fonte": "Clientes e projetos (M&A)"}, origem="conta")
        if pend:
            self.mv.alertar("contas", "ficha_pendente", cid, "atencao", f"{c['nome']}: {len(pend)} item(ns) a esclarecer ({', '.join(pend)})",
                            "Abrir Clientes e projetos → resumo a conferir; anexar documentos e usar o bot de análise")
        else:
            self.mv.db.execute("UPDATE mv_alerta SET resolvido=? WHERE bot='contas' AND ref=? AND resolvido IS NULL", (time.time(), cid))
        txt = "".join(ch for ch in unicodedata.normalize("NFKD", f"{c['nome']} {c['core']}") if not unicodedata.combining(ch)).lower()
        palavras = {w for w in re.findall(r"[a-z0-9]{4,}", txt) if w not in PARADAS and not w.isdigit()}
        self.mv.db.execute("DELETE FROM mv_palavra WHERE conta=?", (cid,))
        self.mv.db.executemany("INSERT OR IGNORE INTO mv_palavra VALUES (?,?)", [(w, cid) for w in sorted(palavras)])
        self.mv.db.commit()
        return {"conta": cid, "tarefas": 1 + len(c["subprojetos"]), "pendentes": len(pend), "palavras": sorted(palavras)}

    def semear(self) -> dict:
        n = m = s = 0
        agora = time.time()
        for c in CNPJS:
            if not self.mv.db.execute("SELECT 1 FROM mv_cnpj WHERE id=?", (c["id"],)).fetchone():
                cols = list(c)
                self.mv.db.execute(f"INSERT INTO mv_cnpj ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", list(c.values()))
                n += 1
        for c in CONTAS:
            if not self.mv.db.execute("SELECT 1 FROM mv_conta WHERE id=?", (c["id"],)).fetchone():
                d = {**c, "criado": agora, "atualizado": agora}
                self.mv.db.execute(f"INSERT INTO mv_conta ({','.join(d)}) VALUES ({','.join('?' * len(d))})", list(d.values()))
                m += 1
        for i in range(1, 5):
            sid = f"estermic-sp{i}"
            if not self.mv.db.execute("SELECT 1 FROM mv_subprojeto WHERE id=?", (sid,)).fetchone():
                self.mv.db.execute("INSERT INTO mv_subprojeto (id,conta,nome,fases,criado) VALUES (?,?,?,?,?)",
                                   (sid, "estermic", f"Subprojeto {i} [MARCADOR]",
                                    json.dumps([{"fase": f, "valor": "[MARCADOR]", "prazo": "", "faturado": False, "recebido": False}
                                                for f in FASES_PADRAO], ensure_ascii=False), agora))
                s += 1
        self.mv.db.commit()
        for c in self.contas():
            self.integrar(c["id"])
        return {"cnpjs": n, "contas": m, "subprojetos": s}

    # ------------------------------------------------------------ leitura
    def cnpjs(self) -> list[dict]:
        return [dict(r) for r in self.mv.db.execute("SELECT * FROM mv_cnpj ORDER BY rowid")]

    def contas(self) -> list[dict]:
        return [self._conta(r) for r in self.mv.db.execute("SELECT * FROM mv_conta ORDER BY estado='futuro', nome")]

    def _conta(self, r) -> dict:
        d = dict(r)
        d["cores"] = json.loads(d["cores"])
        d["propostas"] = json.loads(d["propostas"])
        d["tipo_nome"] = TIPOS.get(d["tipo"], d["tipo"])
        d["template_nome"] = TEMPLATES.get(d["template"], d["template"])
        return d

    def conta(self, cid: str) -> dict:
        r = self.mv.db.execute("SELECT * FROM mv_conta WHERE id=?", (cid,)).fetchone()
        if not r:
            raise ErroMV("conta não encontrada")
        d = self._conta(r)
        d["subprojetos"] = [{**dict(x), "fases": json.loads(x["fases"])} for x in
                            self.mv.db.execute("SELECT * FROM mv_subprojeto WHERE conta=? ORDER BY id", (cid,))]
        d["financeiro"] = self.financeiro("conta", cid)
        d["perguntas"] = [p for p in mv_comandos.perguntas(self.mv) if cid in p["pergunta"].lower() or d["nome"].lower() in p["pergunta"].lower()]
        d["resumo"] = self.resumo(d)
        return d

    def resumo(self, d: dict) -> list[dict]:
        """Resumo a conferir: o que precisa estar esclarecido no início, com a situação de cada item."""
        cn = next((c for c in self.cnpjs() if c["id"] == d["cnpj_emissor"]), {})
        itens = [("CNPJ emissor", f"{cn.get('nome', '?')} · {cn.get('cnpj', '[MARCADOR]')}"), ("Regime", cn.get("regime", "[CONFERIR]")),
                 ("Base contratual", d["contrato"] or "[MARCADOR]"), ("Moeda", d["moeda"]), ("Impostos", d["impostos"] or "[CONFERIR]"),
                 ("Template", d["template_nome"]), ("Responsável", d["responsavel"] or "[MARCADOR]"), ("Contato", d["contato"]),
                 ("Atividade core", d["core"] or "[MARCADOR]"), ("Próximos passos", d["proximos"] or "[MARCADOR]")]
        return [{"item": k, "valor": v, "pendente": bool(re.search(r"\[(MARCADOR|CONFERIR)\]|^\?", str(v)))} for k, v in itens]

    # ------------------------------------------------------------ inclusão de projetos (futuros) e confirmação
    def salvar(self, d: dict) -> dict:
        import unicodedata
        base = "".join(ch for ch in unicodedata.normalize("NFKD", str(d.get("nome", ""))) if not unicodedata.combining(ch))
        cid = str(d.get("id") or re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-"))[:60]
        if not _ID.match(cid):
            raise ErroMV("nome/id inválido")
        if not str(d.get("nome") or "").strip():
            raise ErroMV("nome vazio")
        tipo = d.get("tipo") or "futuro"
        if tipo not in TIPOS:
            raise ErroMV("tipo inválido")
        tpl = d.get("template") or ("cliente" if tipo.startswith("cliente") else "parceria" if tipo == "parceiro" else "physis")
        if tipo == "anterior":
            tpl = "physis"
        if tpl not in TEMPLATES:
            raise ErroMV("template inválido")
        if d.get("cnpj_emissor") and not self.mv.db.execute("SELECT 1 FROM mv_cnpj WHERE id=?", (d["cnpj_emissor"],)).fetchone():
            raise ErroMV("CNPJ emissor desconhecido")
        agora = time.time()
        ant = self.mv.db.execute("SELECT * FROM mv_conta WHERE id=?", (cid,)).fetchone()
        campos = {k: str(d.get(k) if d.get(k) is not None else (ant[k] if ant else ""))[:2000]
                  for k in ("nome", "frente", "cnpj_emissor", "contrato", "moeda", "impostos", "core", "responsavel", "contato", "proximos")}
        campos["frente"] = campos["frente"] or "engineering"
        campos["cnpj_emissor"] = campos["cnpj_emissor"] or "physis-eng"
        campos["moeda"] = campos["moeda"] or "BRL"
        campos["contato"] = campos["contato"] or "[MARCADOR]"
        estado = d.get("estado") or (ant["estado"] if ant else ("futuro" if tipo == "futuro" else "ativo"))
        if ant:
            self.mv.db.execute("UPDATE mv_conta SET nome=?,tipo=?,frente=?,cnpj_emissor=?,contrato=?,moeda=?,impostos=?,template=?,core=?,"
                               "responsavel=?,contato=?,proximos=?,estado=?,atualizado=? WHERE id=?",
                               (campos["nome"], tipo, campos["frente"], campos["cnpj_emissor"], campos["contrato"], campos["moeda"],
                                campos["impostos"], tpl, campos["core"], campos["responsavel"], campos["contato"], campos["proximos"], estado, agora, cid))
        else:
            self.mv.db.execute("INSERT INTO mv_conta (id,nome,tipo,frente,cnpj_emissor,contrato,moeda,impostos,template,core,responsavel,contato,"
                               "proximos,estado,criado,atualizado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (cid, campos["nome"], tipo, campos["frente"], campos["cnpj_emissor"], campos["contrato"], campos["moeda"],
                                campos["impostos"], tpl, campos["core"], campos["responsavel"], campos["contato"], campos["proximos"], estado, agora, agora))
        self.mv.db.commit()
        self.integrar(cid)
        return self.conta(cid)

    def propor(self, cid: str, campos: dict, origem: str = "bot") -> dict:
        """O bot PROPÕE valores (lidos de documentos); só valem depois de confirmar()."""
        c = self.conta(cid)
        prop = c["propostas"]
        for k, v in campos.items():
            if k in ("contrato", "moeda", "impostos", "core", "responsavel", "contato", "proximos"):
                prop[k] = {"valor": str(v)[:2000], "origem": origem, "quando": date.today().isoformat()}
        self.mv.db.execute("UPDATE mv_conta SET propostas=? WHERE id=?", (json.dumps(prop, ensure_ascii=False), cid))
        self.mv.db.commit()
        return self.conta(cid)

    def confirmar(self, cid: str, campo: str, aceitar: bool = True) -> dict:
        c = self.conta(cid)
        p = c["propostas"].pop(campo, None)
        if p is None:
            raise ErroMV("não há proposta para esse campo")
        if aceitar:
            self.mv.db.execute(f"UPDATE mv_conta SET {campo}=? WHERE id=?", (p["valor"], cid)) if campo in (
                "contrato", "moeda", "impostos", "core", "responsavel", "contato", "proximos") else None
        self.mv.db.execute("UPDATE mv_conta SET propostas=?, atualizado=? WHERE id=?", (json.dumps(c["propostas"], ensure_ascii=False), time.time(), cid))
        self.mv.db.commit()
        self.integrar(cid)
        return self.conta(cid)

    # ------------------------------------------------------------ financeiro em níveis
    NIVEIS = {"cnpj": "cnpj_emissor", "entidade": "entidade", "conta": "conta", "subprojeto": "subprojeto", "sistema": "sistema",
              "loja": "loja", "membro": "membro"}

    def financeiro(self, nivel: str = "conta", filtro: str | None = None) -> list[dict]:
        col = self.NIVEIS.get(nivel)
        if not col:
            raise ErroMV("nível inválido (cnpj, entidade, conta, subprojeto, sistema, loja, membro)")
        q = f"SELECT {col} chave, tipo, conferido, SUM(valor) s, COUNT(*) n FROM mv_lanc"
        a = []
        if filtro:
            q, a = q + f" WHERE {col}=?", [filtro]
        out = {}
        for r in self.mv.db.execute(q + f" GROUP BY {col}, tipo, conferido", a):
            k = r["chave"] or "(sem)"
            d = out.setdefault(k, {"chave": k, "oficial": {}, "a_conferir": {}, "lancamentos": 0})
            d["oficial" if r["conferido"] else "a_conferir"][r["tipo"]] = round(r["s"], 2)
            d["lancamentos"] += r["n"]
        return sorted(out.values(), key=lambda x: x["chave"])

    def sugerir_anteriores(self, raiz: Path | None = None) -> list[dict]:
        """Lê os nomes de arquivos e pastas dos Documentos e PROPÕE projetos anteriores com caixas pré-preenchidas
        (nome, cliente/financiador, país, ano, documentos de origem). Nada é gravado: a dona revisa e confirma."""
        raiz = Path(raiz or DOCS_RAIZ)
        if not raiz.is_dir():
            return []
        itens = []
        for p in list(raiz.iterdir()) + [q for d in raiz.iterdir() if d.is_dir() for q in d.iterdir()][:2000]:
            itens.append(p)
        ja = {c["nome"] for c in self.contas()}
        out = []
        for nome, chaves, cliente, pais in GRUPOS_ANTERIORES:
            arqs = sorted({str(p.relative_to(raiz)) for p in itens if any(k in p.name.lower() for k in chaves)})
            if not arqs or nome in ja:
                continue
            anos = sorted({m for a in arqs for m in re.findall(r"(?<!\d)(20[12]\d)(?!\d)", a)} |
                          {"20" + m[:2] for a in arqs for m in re.findall(r"(?<!\d)(2[0-6][01]\d[0-3]\d)(?!\d)", a)})
            out.append({"nome": nome, "cliente": cliente, "pais": pais, "ano": ", ".join(anos[-3:]) or "[CONFERIR]",
                        "escopo": "[CONFERIR] (resumo a partir dos documentos)", "arquivos": arqs[:40], "total_arquivos": len(arqs)})
        return out

    def criar_anterior(self, d: dict) -> dict:
        """Confirma um projeto anterior revisado pela dona (estado concluído; documentos de origem registrados)."""
        arqs = [str(a)[:300] for a in (d.get("arquivos") or [])][:60]
        core = f"Cliente/financiador: {d.get('cliente') or '[CONFERIR]'} · país: {d.get('pais') or '[CONFERIR]'} · ano: {d.get('ano') or '[CONFERIR]'} · escopo: {d.get('escopo') or '[CONFERIR]'}"
        r = self.salvar({"nome": d.get("nome"), "tipo": "anterior", "estado": "concluido", "template": "physis", "core": core,
                         "contrato": d.get("contrato") or "[CONFERIR]", "proximos": "Documentos de origem: " + ("; ".join(arqs) or "nenhum")})
        return r

    def lancar(self, l: dict) -> int:
        """Lançamento com os níveis do mapeamento (conta, subprojeto, sistema, loja, membro, CNPJ emissor, contrato)."""
        lid = self.mv.lancar(l)
        extras = {k: str(l.get(k) or "")[:200] for k in ("conta", "subprojeto", "sistema", "loja", "membro", "cnpj_emissor", "contrato")}
        if extras["conta"] and not self.mv.db.execute("SELECT 1 FROM mv_conta WHERE id=?", (extras["conta"],)).fetchone():
            raise ErroMV("conta desconhecida")
        self.mv.db.execute(f"UPDATE mv_lanc SET {', '.join(k + '=?' for k in extras)} WHERE id=?", (*extras.values(), lid))
        self.mv.db.commit()
        return lid

    def lancamentos(self, conta: str | None = None) -> list[dict]:
        q, a = "SELECT * FROM mv_lanc", []
        if conta:
            q, a = q + " WHERE conta=?", [conta]
        return [dict(r) for r in self.mv.db.execute(q + " ORDER BY data DESC, id DESC LIMIT 500", a)]

    def analisar(self, cid: str) -> dict:
        """Bot de análise: revisa cada anexo da conta e pede ao Claude (fila) uma PROPOSTA de ficha a partir deles."""
        c = self.conta(cid)
        anexos = [dict(r) for r in self.mv.db.execute("SELECT id, nome FROM mv_arquivo WHERE ref=? AND estado!='descartado'", (cid,))] \
            if self.mv.db.execute("SELECT name FROM sqlite_master WHERE name='mv_arquivo'").fetchone() else []
        cmd = mv_comandos.Comandos(self.mv)
        texto = (f"Ler os anexos da conta '{c['nome']}' ({cid}) e PROPOR a ficha (contrato, moeda, impostos, atividade core, responsável, "
                 f"contato, próximos passos, subprojetos e fases) para confirmação da dona. Anexos: "
                 + (", ".join(f"{a['nome']} ({a['id']})" for a in anexos) or "nenhum ainda") + ". Não inventar: [MARCADOR].")
        return cmd._pedido("claude", texto, "", "na_fila", "Na fila do Claude; a proposta volta para confirmação campo a campo.", origem=f"conta:{cid}")

    def pedir_nota(self, lid: int) -> dict:
        """Rascunho de e-mail ao contador (Robson) pedindo a NF de um lançamento de receita. Nunca envia."""
        r = self.mv.db.execute("SELECT * FROM mv_lanc WHERE id=?", (int(lid),)).fetchone()
        if not r:
            raise ErroMV("lançamento não encontrado")
        if r["tipo"] not in ("receita", "edital"):
            raise ErroMV("nota fiscal só para receita")
        conta = self.mv.db.execute("SELECT * FROM mv_conta WHERE id=?", (r["conta"],)).fetchone() if r["conta"] else None
        cn = self.mv.db.execute("SELECT * FROM mv_cnpj WHERE id=?", (r["cnpj_emissor"] or "physis-eng",)).fetchone()
        corpo = (f"Para: Robson (contador) <[MARCADOR] e-mail>\nAssunto: Pedido de nota fiscal · {conta['nome'] if conta else '[cliente]'} · {r['data']}\n\n"
                 f"Olá, Robson,\n\nPode emitir a nota fiscal abaixo?\n\n- Emissor: {cn['nome'] if cn else '[MARCADOR]'} · CNPJ {cn['cnpj'] if cn else '[MARCADOR]'} · {cn['regime'] if cn else ''}\n"
                 f"- Tomador: {conta['nome'] if conta else '[MARCADOR]'} · CNPJ/ID [MARCADOR]\n- Contrato: {r['contrato'] or (conta['contrato'] if conta else '[MARCADOR]')}\n"
                 f"- Subprojeto/fase: {r['subprojeto'] or '—'}\n- Descrição: {r['descricao']}\n- Valor: {r['valor']:.2f} {conta['moeda'] if conta else 'BRL'}\n"
                 f"- Impostos: {conta['impostos'] if conta else '[CONFERIR]'}\n\nObrigada,\nRafaella\nPhysis Engineering\n\n"
                 "— RASCUNHO do Physis M&A: revisar e enviar manualmente. Nada foi enviado.")
        p = mv_comandos.Comandos(self.mv)._pedido("email_contador", f"/nota {lid}", "", "rascunho", corpo, origem="financeiro")
        self.mv.db.execute("UPDATE mv_lanc SET nf=? WHERE id=?", (f"rascunho:{p['id']}", int(lid)))
        self.mv.db.commit()
        return p
