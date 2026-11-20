"""Bots do Physis M&V (VERSÃO DE TESTE; D50, D56, D58). Rodam sozinhos pela agenda do Windows (mv_cli agenda) e
nunca mandam nada para fora: produzem alertas, tarefas de correção e o resumo diário. Envio de e-mail e publicação
seguem precisando de aprovação humana (D49).

Bots desta versão (por regras, sem IA; a IA do Claude entra nos bots de editais/acervo, com teto de US$ 50/mês, D71):
- atrasos: tarefa vencida, bloqueada, dependência não concluída perto do início, ciclo de dependências, sem responsável,
  data estimada no caminho crítico; cada alerta traz a intervenção sugerida.
- documentos: varre as pastas de trabalho, mede idade × validade por tipo de documento e confere regras das decisões
  (horizonte 2031, sede no Brasil, grafia Rafaella, S2 Services não é ONG, bônus sobre vendas suspenso, marcadores).
  Cada documento com falha vira alerta + tarefa de correção.
- resumo: relatório diário (Markdown + ODT) na pasta de saída.
"""
from __future__ import annotations

import hashlib
import os
import re
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

from . import mv as mvmod
from .mv import MV

DOCS = Path(os.environ.get("PHYSIS_DOCS") or (Path.home() / "OneDrive - Physis Engineering" / "Documents"))
RAIZES = ("Casa Physis", "Sistema Physis", "Instituto Physis")
SAIDA = Path(os.environ.get("PHYSIS_MV_SAIDA") or (DOCS / "Sistema Physis" / "28_Physis_MV"))
# pastas geradas, de código ou cópias: o bot não varre (o código tem os próprios testes)
IGNORAR = re.compile(r"(\\|/)(sistema_physis_fase1|_backup[^\\/]*|_versoes_teste|node_modules|\.git|\.claude|Modulos em desenvolvimento|"
                     r"Projetos em desenvolvimento|sistema_physis_ep_final|06_Kits_revisao|28_Physis_MV)(\\|/)", re.I)
EXTS = {".docx", ".pptx", ".xlsx", ".odt", ".odp", ".ods", ".md", ".txt", ".pdf"}
# arquivos que CITAM as regras (decisões, revisões): não são conferidos por elas
SEM_REGRAS = re.compile(r"^(27_Decisoes|04_Respostas|Revis[aã]o_Estrutural|Trechos_retirados)", re.I)   # Trechos_retirados: registro do texto antigo

# validade por tipo (dias); premissas da versão de teste, a ajustar pela dona
VALIDADE = {"apresentacao": 90, "contrato": 365, "planilha": 180, "memo": 30, "plano": 180, "documento": 180}

REGRAS = [
    # id, padrão, condição extra (padrão que, se presente, anula), texto, decisão, gravidade
    ("horizonte", re.compile(r"2027\s*[–—-]\s*2032"), None, "Horizonte 2027–2032: o oficial é 2027–2031", "D40", "atencao"),
    ("nome", re.compile(r"\bRafaela\b"), None, "Grafia 'Rafaela': a oficial é Rafaella", "D61", "atencao"),
    ("sede", re.compile(r"\b(ICT|OSC|Instituto Physis)\b[^.\n]{0,120}Am[ée]rica Latina", re.I), re.compile(r"sede e foro no Brasil", re.I),
     "ICT descrita na América Latina sem 'sede e foro no Brasil'", "D42", "alerta"),
    ("ongs", re.compile(r"duas ONGs", re.I), None, "'Duas ONGs': a S2 Services SARL é empresa, não ONG", "D66", "alerta"),
    ("bonus", re.compile(r"b[oô]nus[^.\n]{0,80}vendas", re.I), None, "Bônus de bolsista sobre vendas (suspenso até o parecer)", "D34", "alerta"),
    # Divergências mapeadas em 18/11/2026 na leitura da pasta Casa Physis (sessão do Instituto Physis)
    ("pdi28", re.compile(r"\b28\s+(projetos|projects|fichas)\b", re.I), re.compile(r"vers[aã]o de 28 projetos|28-project version", re.I),
     "PDI com 28 projetos: o atual tem 22 (P1–P22, atualização de 18/11/2026)", "PDI P1–P22", "atencao"),
    ("p18", re.compile(r"P18\b[^\n]{0,30}Maker e e-?waste", re.I), None,
     "P18 se chama Economia circular (maker, filamento, reúso e e-waste são rotas dele)", "PDI P1–P22", "atencao"),
    ("gsa_cessao", re.compile(r"(technical secretariat|secretaria t[ée]cnica)[^.\n]{0,60}Physis Engineering", re.I),
     re.compile(r"cess[aã]o de posi[cç][aã]o|assignment|assign(?:ed)? to (?:the )?(?:Physis )?Institut", re.I),
     "Global South Alliance: a Physis assina agora e o Instituto assume depois; prever a cláusula de cessão", "D67", "atencao"),
]
MARCADORES = re.compile(r"\[(MARCADOR|A PREENCHER|CONFERIR)\]|\ba definir\b", re.I)


def tipo_de(nome: str, ext: str) -> str:
    n = nome.lower()
    if ext in (".pptx", ".odp") or re.search(r"apresenta|deck|profile|concept|folder", n):
        return "apresentacao"
    if re.search(r"contrato|minuta|termo|acordo|estatuto|memorando|governan", n):
        return "contrato"
    if ext in (".xlsx", ".ods"):
        return "planilha"
    if re.search(r"memo|checklist|leia-me|pendenc|regress", n):
        return "memo"
    if re.search(r"plano|roteiro|cronograma|estrat", n):
        return "plano"
    return "documento"


def frente_de(caminho: str) -> str:
    c = caminho.lower()
    if "inovastem" in c:
        return "inovastem"
    if "instituto" in c:
        return "instituto"
    if "1_tecnico_casa" in c or "lote" in c:
        return "casa"
    if "estrat" in c:
        return "transversal"
    return "engineering"


def texto_de(p: Path, limite: int = 2_000_000) -> str:
    """Texto simples de docx/pptx/xlsx/odt/odp/ods/md/txt (sem dependências). PDF: vazio (só idade)."""
    ext = p.suffix.lower()
    try:
        if ext in (".md", ".txt"):
            return p.read_text(encoding="utf-8", errors="replace")[:limite]
        if ext == ".pdf":
            return ""
        with zipfile.ZipFile(p) as z:
            nomes = z.namelist()
            if ext == ".docx":
                alvo = [n for n in nomes if re.match(r"word/(document|header\d*|footer\d*)\.xml$", n)]
            elif ext == ".pptx":
                alvo = sorted(n for n in nomes if re.match(r"ppt/slides/slide\d+\.xml$", n))
            elif ext == ".xlsx":
                alvo = [n for n in nomes if n == "xl/sharedStrings.xml"]
            else:
                alvo = ["content.xml"] if "content.xml" in nomes else []
            partes, tam = [], 0
            for n in alvo:
                x = z.read(n).decode("utf-8", errors="replace")
                x = re.sub(r"</(w:p|a:p|text:p|text:h|si)>", "\n", x)
                t = re.sub(r"<[^>]+>", "", x)
                partes.append(t)
                tam += len(t)
                if tam > limite:
                    break
            return "\n".join(partes)[:limite]
    except (zipfile.BadZipFile, OSError, KeyError):
        return ""


GERADOR = re.compile(r"generated (?:by|using) python-(?:docx|pptx)|openpyxl|Steve Canny", re.I)


def data_do_conteudo(p: Path):
    """Data de criação/modificação gravada DENTRO do arquivo (docProps/core.xml ou meta.xml). Arquivo copiado ganha
    data de sistema nova; a de dentro mostra a idade real do conteúdo (apresentações com mais de 5 anos, D54)."""
    if p.suffix.lower() not in (".docx", ".pptx", ".xlsx", ".odt", ".odp", ".ods"):
        return None
    try:
        with zipfile.ZipFile(p) as z:
            n = "docProps/core.xml" if "docProps/core.xml" in z.namelist() else ("meta.xml" if "meta.xml" in z.namelist() else None)
            if not n:
                return None
            x = z.read(n).decode("utf-8", errors="replace")
    except (zipfile.BadZipFile, OSError, KeyError):
        return None
    g = GERADOR.search(x)
    if g:                                   # data e autor vêm do modelo da biblioteca, não do documento
        return ("gerador", g.group(0))
    m = re.search(r"<(?:dcterms:modified|dc:date)[^>]*>(\d{4}-\d{2}-\d{2})", x)
    try:
        return date.fromisoformat(m.group(1)) if m else None
    except ValueError:
        return None


def conferir_texto(texto: str) -> tuple[list[dict], int]:
    falhas = []
    for rid, pad, anula, txt, dec, grav in REGRAS:
        m = pad.search(texto)
        if m and not (anula and anula.search(texto)):
            ini = max(0, m.start() - 40)
            falhas.append({"regra": rid, "texto": txt, "decisao": dec, "gravidade": grav,
                           "trecho": re.sub(r"\s+", " ", texto[ini:m.end() + 40]).strip()})
    return falhas, len(MARCADORES.findall(texto))


# ---------------------------------------------------------------------------------------------- bot de documentos
def bot_documentos(mv: MV, raizes: list[Path] | None = None, hoje: date | None = None) -> dict:
    inicio = mv.nova_rodada()
    hoje = hoje or mvmod.HOJE()
    raizes = raizes or [DOCS / r for r in RAIZES]
    vistos, falhas_n, vencidos, modelos = 0, 0, {}, {}
    for raiz in raizes:
        if not raiz.is_dir():
            mv.alertar("documentos", "pasta", str(raiz), "info", f"Pasta não encontrada: {raiz}", "Conferir o caminho em PHYSIS_DOCS")
            continue
        for dirpath, dirs, arquivos in os.walk(raiz):
            if IGNORAR.search(dirpath + os.sep):
                dirs[:] = []
                continue
            for a in arquivos:
                p = Path(dirpath) / a
                ext = p.suffix.lower()
                if ext not in EXTS or a.startswith(("~$", ".")):
                    continue
                try:
                    st = p.stat()
                except OSError:
                    continue
                vistos += 1
                mod = date.fromtimestamp(st.st_mtime)
                interna = data_do_conteudo(p)
                gerador = isinstance(interna, tuple)
                if not gerador and interna and interna < mod:   # cópia recente de conteúdo antigo: vale a data de dentro
                    mod = interna
                idade = max(0, (hoje - mod).days)
                tipo = tipo_de(a, ext)
                fr = frente_de(str(p))
                falhas, marc = ([], 0) if SEM_REGRAS.match(a) else conferir_texto(texto_de(p))
                if gerador:
                    modelos.setdefault(fr, []).append(a)
                validade = VALIDADE[tipo]
                situ = "falha" if falhas else ("vencido" if idade > validade else "ok")
                rel = str(p.relative_to(DOCS)) if str(p).startswith(str(DOCS)) else str(p)
                mv.db.execute("INSERT OR REPLACE INTO mv_documento VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                              (rel, a, fr, tipo, ext, mod.isoformat(), st.st_size, idade, validade,
                               "teste" if "teste" in rel.lower() else ("oficial" if "oficia" in rel.lower() else ""),
                               mvmod.json.dumps(falhas, ensure_ascii=False), marc, situ, inicio))
                h = hashlib.sha1(rel.encode()).hexdigest()[:10]
                if falhas:
                    falhas_n += 1
                    grav = "alerta" if any(f["gravidade"] == "alerta" for f in falhas) else "atencao"
                    resumo = "; ".join(f'{f["texto"]} ({f["decisao"]})' for f in falhas)
                    mv.alertar("documentos", "falha", rel, grav, f"{a}: {resumo}",
                               "Corrigir no editável, gerar versão de teste, conferir e só então substituir a oficial", fr)
                    tid = f"doc:{h}"
                    ant = mv.tarefa(tid)
                    if not ant or ant["estado"] != "feita":
                        mv.salvar_tarefa({"id": tid, "frente": fr, "projeto": "Correções de documentos (bot)",
                                          "titulo": f"Corrigir {a}: {resumo}"[:300], "responsavel": "Rafaella",
                                          "inicio": hoje.isoformat(), "fim": (hoje + timedelta(days=7)).isoformat(),
                                          "estado": ant["estado"] if ant else "a_fazer", "prioridade": 1 if grav == "alerta" else 2,
                                          "meta": "m-transv-fase0", "fonte": rel, "data_estimada": True}, origem="bot-documentos")
                elif situ == "vencido":
                    vencidos.setdefault((fr, tipo), []).append((idade, a))
    for (fr, tipo), lst in vencidos.items():
        lst.sort(reverse=True)
        anos5 = sum(1 for i, _ in lst if i > 5 * 365)
        exemplos = ", ".join(f"{n} ({i} d)" for i, n in lst[:5])
        mv.alertar("documentos", "vencido", f"{fr}:{tipo}", "atencao" if tipo == "apresentacao" else "info",
                   f"{len(lst)} {tipo}(s) de {dict((f[0], f[1]) for f in mvmod.FRENTES)[fr]} além da validade "
                   f"({VALIDADE[tipo]} dias){f'; {anos5} com mais de 5 anos' if anos5 else ''}. Mais antigos: {exemplos}",
                   "Revisar dados e visual; apresentações de captação têm prioridade", fr)
    for fr, lst in modelos.items():
        mv.alertar("documentos", "template", fr, "atencao",
                   f"{len(lst)} arquivo(s) com metadados do gerador (autor e data falsos, ex.: 'Steve Canny', 2013): "
                   + ", ".join(lst[:6]), "Corrigir o template: autor 'Physis Engineering' (ou Instituto/Casa) e data real", fr)
    mv.db.commit()
    fechados = mv.fechar_alertas_nao_vistos("documentos", inicio)
    r = {"vistos": vistos, "com_falha": falhas_n, "grupos_vencidos": len(vencidos),
         "template_gerador": sum(len(v) for v in modelos.values()), "alertas_resolvidos": fechados}
    mv.registrar_execucao("documentos", inicio, mvmod.json.dumps(r))
    return r


# ------------------------------------------------------------------------------------------------ bot de atrasos
# Marcos que fecham uma fase: toda tarefa aberta cujo projeto começa com o nome da fase precisa terminar até o marco.
# Pedido de 18/11/2026: o CNPJ do Instituto (J2, fev/2027) e as cessões (J5/J6, mar/2027) passam do marco "Fase 0 fechada"
# (31/01/2027, mantido pela dona), e o M&V só comparava cada tarefa com o próprio prazo. Tarefa com o campo "marco"
# preenchido também é conferida contra esse marco.
MARCOS_DE_FASE = {"k-fase0": "Fase 0"}


def marcos_estourados_por(t: dict, k: dict, marcos: dict) -> list[tuple[str, str, str, str]]:
    """[(id do marco, título, data do marco, fim planejado)] dos marcos abertos que a tarefa ultrapassa.
    Fim planejado = o mais tarde entre o prazo informado e o fim calculado pelo CPM (dependências)."""
    if t["estado"] == "feita":
        return []
    fins = [x for x in (mvmod._d(k.get("ef")), mvmod._d(t["fim"])) if x]
    if not fins:
        return []
    fim_plan, out = max(fins), []
    for mid, m in marcos.items():
        liga = t.get("marco") == mid or (mid in MARCOS_DE_FASE and (t.get("projeto") or "").startswith(MARCOS_DE_FASE[mid]))
        data = mvmod._d(m["data"])
        if liga and data and fim_plan > data:
            out.append((mid, m["titulo"], data.isoformat(), fim_plan.isoformat()))
    return out


def bot_atrasos(mv: MV, hoje: date | None = None) -> dict:
    inicio = mv.nova_rodada()
    hoje = hoje or mvmod.HOJE()
    cpm = mv.cpm()
    crit = set(cpm["criticos"])
    ts = {t["id"]: t for t in mv.tarefas()}
    marcos = {r["id"]: dict(r) for r in mv.db.execute("SELECT * FROM mv_marco WHERE feito=0")}
    n = {"atrasadas": 0, "bloqueadas": 0, "dependencias": 0, "sem_responsavel": 0, "estimadas_criticas": 0}
    for c in cpm["ciclos"]:
        mv.alertar("atrasos", "ciclo", c, "alerta", f"Ciclo de dependências: {c}", "Remover uma das dependências")
    for tid, t in ts.items():
        if t["estado"] == "feita":
            continue
        fim = mvmod._d(t["fim"])
        if fim and fim < hoje:
            n["atrasadas"] += 1
            dias = (hoje - fim).days
            suc = [x for x, y in ts.items() if tid in y["depende_de"] and y["estado"] != "feita"]
            grav = "alerta" if (tid in crit or t["prioridade"] <= 1 or suc) else "atencao"
            if t["estado"] == "bloqueada":
                acao = f"Resolver o bloqueio ({t['bloqueio'] or 'motivo não informado'}) com quem ele depende"
            elif suc:
                acao = f"Replanejar ou reforçar: segura {len(suc)} tarefa(s) seguinte(s)"
            elif t["duracao_d"] > 30:
                acao = "Dividir em entregas menores com responsável e data"
            else:
                acao = "Confirmar nova data com o responsável ou reatribuir"
            mv.alertar("atrasos", "atrasada", tid, grav, f"Atrasada há {dias} dia(s): {t['titulo']} ({t['responsavel'] or 'sem responsável'})",
                       acao, t["frente"])
        if t["estado"] == "bloqueada":
            n["bloqueadas"] += 1
            mv.alertar("atrasos", "bloqueada", tid, "alerta" if tid in crit else "atencao",
                       f"Bloqueada: {t['titulo']} — {t['bloqueio'] or 'motivo não informado'}", "Registrar de quem depende e cobrar", t["frente"])
        ini = cpm["tarefas"].get(tid, {}).get("es")
        pend = [d for d in t["depende_de"] if d in ts and ts[d]["estado"] != "feita"]
        if ini and pend and mvmod._d(ini) <= hoje + timedelta(days=3):
            n["dependencias"] += 1
            mv.alertar("atrasos", "dependencia", tid, "atencao",
                       f"Começa em até 3 dias, mas depende de: {', '.join(ts[d]['titulo'][:60] for d in pend)}",
                       "Antecipar a dependência ou mover o início", t["frente"])
        k = cpm["tarefas"].get(tid, {})
        if k.get("prazo_em_risco"):
            n["prazo_em_risco"] = n.get("prazo_em_risco", 0) + 1
            mv.alertar("atrasos", "prazo_em_risco", tid, "alerta" if t["prioridade"] <= 1 else "atencao",
                       f"Prazo em risco ({k['estouro_d']} d além de {t['fim']}): {t['titulo']} — as dependências terminam depois",
                       "Antecipar a dependência, rodar em paralelo ou renegociar o prazo", t["frente"])
        for mid, mtit, mdata, fim_plan in marcos_estourados_por(t, k, marcos):
            n["marco_estourado"] = n.get("marco_estourado", 0) + 1
            dias = (date.fromisoformat(fim_plan) - date.fromisoformat(mdata)).days
            mv.alertar("atrasos", "marco_estourado", f"{mid}:{tid}", "alerta" if t["prioridade"] <= 1 else "atencao",
                       f"Passa do marco '{mtit}' ({mdata}): {t['titulo']} termina em {fim_plan} (+{dias} d)",
                       "Antecipar a tarefa, tirar dela o que não é desta fase, ou a direção registrar a exceção ao marco", t["frente"])
        if not t["responsavel"].strip():
            n["sem_responsavel"] += 1
            mv.alertar("atrasos", "sem_responsavel", tid, "info", f"Sem responsável: {t['titulo']}", "Atribuir", t["frente"])
        if tid in crit and t["data_estimada"]:
            n["estimadas_criticas"] += 1
            mv.alertar("atrasos", "estimada_critica", tid, "info", f"Caminho crítico com data estimada [CONFERIR]: {t['titulo']}",
                       "Confirmar a data com o responsável", t["frente"])
    fechados = mv.fechar_alertas_nao_vistos("atrasos", inicio)
    r = {**n, "criticos": len(crit), "fim_previsto": cpm["fim_previsto"], "alertas_resolvidos": fechados}
    mv.registrar_execucao("atrasos", inicio, mvmod.json.dumps(r))
    return r


# ------------------------------------------------------------------------------------------------- resumo diário
def resumo(mv: MV, saida: Path | None = None, hoje: date | None = None) -> dict:
    inicio = mv.nova_rodada()
    hoje = hoje or mvmod.HOJE()
    saida = Path(saida or SAIDA) / "resumos"
    saida.mkdir(parents=True, exist_ok=True)
    s = mv.saude()
    al = mv.alertas()
    cpm = mv.cpm()
    prox = [t for t in mv.gantt() if t["critico"] and t["plan_inicio"] and mvmod._d(t["plan_inicio"]) <= hoje + timedelta(days=14)]
    linhas = [f"# Physis M&V · resumo de {hoje.strftime('%d/%m/%Y')} (versão de teste)", "",
              "## Saúde por frente", "", "| Frente | Nota | Feitas | Atrasadas | Bloqueadas | Datas a conferir |", "|---|---|---|---|---|---|"]
    for f in s["frentes"].values():
        linhas.append(f"| {f['nome']} | {f['nota']} | {f['feitas']}/{f['total']} | {f['atrasadas']} | {f['bloqueadas']} | {f['datas_estimadas']} |")
    linhas += ["", f"Fim previsto do plano atual: {cpm['fim_previsto']}", "", "## Alertas que pedem intervenção", ""]
    for a in [x for x in al if x["gravidade"] == "alerta"][:25]:
        linhas.append(f"- **{a['texto']}** → {a['acao']}")
    linhas += ["", "## Caminho crítico nos próximos 14 dias", ""]
    for t in prox[:25]:
        linhas.append(f"- {t['plan_inicio']} → {t['plan_fim']} · {t['titulo']} ({t['responsavel']})")
    docs = [d for d in mv.documentos() if d["situacao"] == "falha"]
    linhas += ["", f"## Documentos com falha ({len(docs)})", ""]
    for d in docs[:30]:
        linhas.append(f"- {d['caminho']}: " + "; ".join(f["texto"] for f in d["falhas"]))
    linhas += ["", "_Gerado automaticamente pelo Physis M&V. Nada foi enviado para fora; e-mails e documentos seguem para aprovação._"]
    md = "\n".join(linhas)
    arq = saida / f"{hoje.isoformat()}.md"
    arq.write_text(md, encoding="utf-8")
    odt_ok = False
    try:
        from . import documentos
        blocos = []
        for l in linhas[2:]:
            if l.startswith("## "):
                blocos.append({"h": 2, "t": l[3:]})
            elif l.startswith("- "):
                blocos.append({"t": l[2:].replace("**", ""), "lista": True})
            elif l and not l.startswith("|---"):
                blocos.append({"t": l.replace("**", "").replace("_", "")})
        (saida / f"{hoje.isoformat()}.odt").write_bytes(
            documentos.odt(f"Physis M&V · resumo de {hoje.strftime('%d/%m/%Y')}", blocos, sistema="Physis M&V (teste)"))
        odt_ok = True
    except Exception as e:  # noqa: BLE001 — o resumo em Markdown basta se o ODT falhar
        mv.alertar("resumo", "odt", "odt", "info", f"Resumo ODT não gerado: {e}", "Ver documentos.py")
    r = {"arquivo": str(arq), "odt": odt_ok, "alertas": len(al)}
    mv.registrar_execucao("resumo", inicio, mvmod.json.dumps(r))
    return r


# ------------------------------------------------------------------------------------------- cópia de segurança
BACKUP_DIR = Path(os.environ.get("PHYSIS_MV_BACKUP") or (DOCS / "Sistema Physis" / "28_Physis_MV" / "backup"))
BACKUP_DIAS = 30


def backup(mv: MV, destino: Path | None = None, hoje: date | None = None) -> dict:
    """Cópia diária consistente do banco (VACUUM INTO) numa pasta do OneDrive, mantendo 30 dias (doc 32, item 6.6, decisão de
    18/11/2026). Confere a cópia com integrity_check; aos domingos (e na 1ª cópia) testa a restauração comparando as contagens
    das tabelas. O banco ativo continua fora do OneDrive (a sincronização corrompe SQLite em uso)."""
    import sqlite3
    inicio = mv.nova_rodada()
    hoje = hoje or mvmod.HOJE()
    pasta = Path(destino or BACKUP_DIR)
    pasta.mkdir(parents=True, exist_ok=True)
    primeira = not any(pasta.glob("physis-mv-*.db"))
    alvo = pasta / f"physis-mv-{hoje.isoformat()}.db"
    tmp = pasta / f"physis-mv-{hoje.isoformat()}.tmp"
    tmp.unlink(missing_ok=True)
    mv.db.execute("VACUUM INTO ?", (str(tmp),))
    c = sqlite3.connect(tmp)
    ok = c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    restauro = None
    if hoje.weekday() == 6 or primeira:
        tabelas = [r[0] for r in mv.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'mv_%'")]
        restauro = all(mv.db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] ==
                       c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tabelas)
    c.close()
    if not ok or restauro is False:
        tmp.unlink(missing_ok=True)
        mv.alertar("backup", "falha", hoje.isoformat(), "alerta", f"Cópia de segurança de {hoje} falhou na conferência",
                   "Ver o disco e o OneDrive; rodar de novo")
        r = {"ok": False}
    else:
        tmp.replace(alvo)
        antigas = sorted(pasta.glob("physis-mv-*.db"))[:-BACKUP_DIAS]
        for a in antigas:
            a.unlink(missing_ok=True)
        mv.fechar_alertas_nao_vistos("backup", inicio)
        r = {"ok": True, "arquivo": str(alvo), "mb": round(alvo.stat().st_size / 1e6, 2), "restauracao_testada": restauro,
             "removidas": len(antigas)}
    mv.registrar_execucao("backup", inicio, mvmod.json.dumps(r))
    return r


BOTS = {"atrasos": bot_atrasos, "documentos": bot_documentos, "resumo": resumo, "backup": backup}


def rodar(mv: MV, quais: list[str] | None = None) -> dict:
    out = {}
    for nome in quais or ["documentos", "atrasos", "resumo"]:
        t0 = time.time()
        try:
            out[nome] = BOTS[nome](mv)
        except Exception as e:  # noqa: BLE001 — um bot com defeito não para os outros; fica registrado e vira alerta
            mv.registrar_execucao(nome, t0, "", repr(e))
            mv.alertar("mv", "bot_falhou", nome, "alerta", f"O bot {nome} falhou: {e!r}", "Ver o registro e corrigir")
            out[nome] = {"erro": repr(e)}
    return out
