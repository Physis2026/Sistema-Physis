"""Kit de documentos por pilar (prazo 26/11/2026), revisão semanal completa e melhoria contínua dos bots (22/11/2026).

kit: para cada pilar e tipo de documento exigido, procura nas pastas (tabela mv_documento, alimentada pelo bot documentos)
e diz se existe, se está velho, com [MARCADOR] ou falha. O que falta ganha uma VERSÃO ZERO em ODT montada com os dados reais
do M&A (metas, marcos, tarefas, editais) e [MARCADOR] onde só a equipe pode escrever (regra 1) + pedido para revisão.
semanal: uma vez por semana roda todos os bots, a auditoria e o kit e escreve o relatório semanal (regressão completa).
melhoria: aprende com as decisões humanas (pedidos aprovados × descartados, Beta-Binomial) e aponta o bot a calibrar.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path

PRAZO_KIT = date(2026, 11, 26)
PILARES = {   # pilar: (nome, frente do M&A, palavras no caminho/nome, modelo visual)
    "ecossistema": ("Ecossistema Physis (M&A)", "transversal", r"ecossistema|m&a|m&v|physis[ _-]?geral", "Template ecossistema Physis"),
    "engineering": ("Physis Engineering", "engineering", r"engineering|physis[ _-]?eng", "Template Physis Engineering"),
    "instituto": ("Instituto Physis", "instituto", r"instituto", "Template Instituto Physis"),
    "inovastem": ("InovaSTEM", "inovastem", r"inovastem", "Template InovaSTEM"),
    "casa": ("Casa Physis", "casa", r"casa[ _-]?physis|\bcasa\b", "Template Casa Physis"),
    "gsa": ("Global South Alliance", "transversal", r"global[ _-]?sou[rt]h|\bgsa\b", "Template Global South Alliance"),
}
TIPOS_DOC = {   # tipo: (nome, palavras no nome do arquivo, seções da versão zero)
    "visao_missao": ("Visão, missão, cronogramas e interligação do ecossistema", r"vis[aã]o|miss[aã]o|estrat",
                     ["Visão", "Missão", "Como os pilares se interligam", "Metas 2027–2031", "Cronograma e marcos", "Atividades por frente"]),
    "apresentacao": ("Apresentação geral", r"apresenta|deck|slides", ["Quem somos", "Problema", "Solução", "Resultados até aqui", "Metas", "Contato"]),
    "pitch": ("Pitch para parceiros e investidores", r"pitch", ["Problema", "Solução", "Mercado", "Tração", "Modelo de receita", "Equipe", "Pedido"]),
    "concept_note": ("Concept note", r"concept|nota[ _-]?conceit", ["Contexto", "Objetivo", "Atividades", "Resultados esperados", "Orçamento", "Parceiros"]),
    "proposta_edital": ("Proposta de edital (versão zero)", r"proposta.*edital|edital.*proposta|submiss", ["Edital alvo", "Aderência", "Objetivos", "Metodologia", "Cronograma", "Orçamento", "Documentos exigidos"]),
    "proposta_parceria": ("Proposta de parceria", r"parceri", ["Quem é o parceiro", "O que cada lado oferece", "Modalidade (teste, compra e venda, estágio, bancada…)", "Prazo", "Próximos passos"]),
    "contrato": ("Modelo de contrato", r"contrat", ["Partes", "Objeto", "Obrigações", "Prazo e rescisão", "Propriedade intelectual", "Foro"]),
    "act": ("Acordo de Cooperação Técnica (ACT)", r"\bact\b|coopera[cç][aã]o t[eé]cnica|acordo de coopera", ["Partes", "Objeto", "Plano de trabalho", "Responsabilidades", "Vigência", "Propriedade intelectual"]),
    "investidor": ("Documento para investidores", r"investid|one[ _-]?pager|data[ _-]?room", ["Tese", "Mercado", "Tração", "Uso dos recursos", "Riscos", "Governança"]),
    "planilha": ("Planilha financeira", r"planilha|financ|fluxo de caixa|or[cç]amento", ["Receitas por porta", "Despesas", "Fluxo por projeto", "Impostos (contador)"]),
    "artigo": ("Artigos", r"artigo", ["Título", "Resumo", "Texto", "Referências"]),
}
EXIGIDOS = {
    "ecossistema": ["visao_missao", "apresentacao", "planilha"],
    "engineering": ["apresentacao", "pitch", "proposta_parceria", "contrato", "investidor", "planilha"],
    "instituto": ["apresentacao", "concept_note", "proposta_edital", "act", "contrato", "planilha"],
    "inovastem": ["pitch", "apresentacao", "proposta_parceria", "concept_note"],
    "casa": ["apresentacao", "artigo"],
    "gsa": ["concept_note", "apresentacao", "act"],
}


def _conta_para(pil: str, caminho: str, frente_doc: str) -> bool:
    """O documento conta para o pilar se o caminho tem o nome do pilar; pela frente só conta para o primeiro pilar daquela
    frente (a "transversal" é do ecossistema e da GSA) e nunca se o caminho é de outro pilar (Marketing/GSA não viram GSA/ecossistema à toa)."""
    _, frente, rx_pil, _ = PILARES[pil]
    if re.search(rx_pil, caminho, re.I):
        return True
    dono = next(p for p, v in PILARES.items() if v[1] == frente)
    return frente_doc == frente and pil == dono and not any(re.search(v[2], caminho, re.I) for p, v in PILARES.items() if p != pil)


def situacao_kit(mv) -> list[dict]:
    docs = mv.db.execute("SELECT caminho, nome, frente, idade_d, validade_d, marcadores, falhas, situacao FROM mv_documento").fetchall()
    out = []
    for pil, tipos in EXIGIDOS.items():
        pnome, frente, rx_pil, _ = PILARES[pil]
        for t in tipos:
            tnome, rx_tipo, _ = TIPOS_DOC[t]
            achados = [d for d in docs if re.search(rx_tipo, d[1], re.I) and _conta_para(pil, d[0], d[2])]
            if not achados:
                est = "falta"
            else:
                d = min(achados, key=lambda x: x[3])            # o mais novo
                est = "ok" if not d[5] and d[3] <= d[4] and d[7] == "ok" else ("com_marcador" if d[5] else "revisar")
            out.append({"pilar": pil, "pilar_nome": pnome, "tipo": t, "tipo_nome": tnome, "estado": est,
                        "arquivo": min(achados, key=lambda x: x[3])[1] if achados else ""})
    return out


def _dados_m_a(mv, frente: str) -> dict:
    metas = mv.db.execute("SELECT id, ano, titulo FROM mv_meta WHERE frente=? ORDER BY ano", (frente,)).fetchall() if frente else []
    marcos = mv.db.execute("SELECT data, titulo FROM mv_marco WHERE frente IN (?, 'transversal') ORDER BY data", (frente,)).fetchall()
    tarefas = mv.db.execute("SELECT titulo, fim, responsavel FROM mv_tarefa WHERE frente=? AND estado<>'feita' ORDER BY fim LIMIT 12", (frente,)).fetchall()
    editais = []
    try:
        editais = mv.db.execute("SELECT titulo, prazo, financiador FROM mv_edital WHERE frente LIKE ? AND etapa NOT IN ('arquivada','reprovada') "
                                "ORDER BY prazo LIMIT 8", (f"%{frente}%",)).fetchall()
    except Exception:  # noqa: BLE001
        pass
    return {"metas": metas, "marcos": marcos, "tarefas": tarefas, "editais": editais}


def versao_zero(mv, pil: str, tipo: str) -> bytes:
    from .documentos import odt
    from . import mv_fatos
    pnome, frente, _, modelo = PILARES[pil]
    tnome, _, secoes = TIPOS_DOC[tipo]
    d = _dados_m_a(mv, frente)
    fatos = mv_fatos.carregar()
    sufixo = "" if pil == "ecossistema" else f"_{pil}"
    do_fato = {"Visão": mv_fatos.valor(fatos, "visao" + sufixo) or mv_fatos.valor(fatos, "visao"),
               "Missão": mv_fatos.valor(fatos, "missao" + sufixo) or mv_fatos.valor(fatos, "missao"),
               "Quem somos": mv_fatos.valor(fatos, "proposta" + sufixo) if pil != "ecossistema" else mv_fatos.valor(fatos, "pilares")}
    b = [{"h": 1, "t": f"{tnome} · {pnome}"},
         {"t": f"Versão zero gerada pelo Physis M&A em {time.strftime('%d/%m/%Y')} ({modelo}). Prazo do kit: 26/11/2026. "
               "Tudo que está fora de [MARCADOR] veio do banco do M&A; o resto é a equipe que escreve. Revisar antes de enviar."}]
    for s in secoes:
        b.append({"h": 2, "t": s})
        if re.search(r"Metas", s) and d["metas"]:
            b.append({"tabela": {"cab": ["Meta", "Ano", "Descrição"], "linhas": [[m[0], str(m[1]), m[2]] for m in d["metas"]]}})
        elif re.search(r"Cronograma|Prazo|Vigência", s) and (d["marcos"] or d["tarefas"]):
            b.append({"tabela": {"cab": ["Data", "Marco ou tarefa", "Responsável"],
                                 "linhas": [[m[0], m[1], ""] for m in d["marcos"]] + [[t[1] or "", t[0], t[2] or ""] for t in d["tarefas"]]}})
        elif re.search(r"Edital alvo", s) and d["editais"]:
            b.append({"tabela": {"cab": ["Edital", "Prazo", "Financiador"], "linhas": [list(e) for e in d["editais"]]}})
        elif do_fato.get(s):
            b.append({"t": do_fato[s] + "  (base de fatos)"})
        else:
            b.append({"t": f"[MARCADOR] {s.lower()} de {pnome}."})
    return odt(f"{tnome} · {pnome} (versão zero)", b, sistema="Physis M&A", logo_png=False)


def bot_kit(mv, saida: Path | None = None, hoje: date | None = None) -> dict:
    from . import mv as mvmod, mv_bots, mv_comandos
    hoje = hoje or mvmod.HOJE()
    if hoje > PRAZO_KIT and hoje.weekday() != 0:          # depois de 26/11: só às segundas (versão enxuta)
        return {"pulado": "depois de 26/11 o kit roda às segundas"}
    inicio = mv.nova_rodada()
    pasta = Path(saida or (mv_bots.SAIDA / "kit-26-11"))
    sit = situacao_kit(mv)
    cmd = mv_comandos.Comandos(mv)
    dias = (PRAZO_KIT - hoje).days
    geradas = 0
    for s in sit:
        if s["estado"] == "ok":
            continue
        grav = "alerta" if s["estado"] == "falta" and 0 <= dias <= 7 else "atencao"
        mv.alertar("kit", s["estado"], f"{s['pilar']}:{s['tipo']}", grav,
                   f"{s['pilar_nome']} · {s['tipo_nome']}: {'falta' if s['estado'] == 'falta' else s['estado'].replace('_', ' ')}"
                   + (f" ({s['arquivo']})" if s["arquivo"] else "") + (f" · faltam {dias} d para 26/11" if dias >= 0 else ""),
                   "Revisar a versão zero gerada pelo M&A" if s["estado"] == "falta" else "Atualizar com a nova estrutura e estratégia")
        ref = f"kit:{s['pilar']}:{s['tipo']}"
        dec = mv.db.execute("SELECT estado FROM mv_pedido_bot WHERE comando=? ORDER BY id DESC LIMIT 1", (ref,)).fetchone()
        if s["estado"] == "falta" and not (dec and dec[0] in mv_comandos.DECIDIDOS):    # decidida: não refaz nem reabre
            arq = pasta / "versao-zero" / s["pilar"] / f"{s['tipo']}.odt"
            arq.parent.mkdir(parents=True, exist_ok=True)
            arq.write_bytes(versao_zero(mv, s["pilar"], s["tipo"]))
            geradas += 1
            ref = f"kit:{s['pilar']}:{s['tipo']}"
            if not mv.db.execute("SELECT 1 FROM mv_pedido_bot WHERE comando=?", (ref,)).fetchone():
                cmd._pedido("kit", ref, "", "rascunho", f"Versão zero de \"{s['tipo_nome']}\" · {s['pilar_nome']} pronta para revisão.",
                            str(arq), origem="kit")
    md = ["# Kit de documentos · prazo 26/11/2026", "", f"Situação em {hoje.strftime('%d/%m/%Y')} ({dias} d para o prazo).", "",
          "| Pilar | Documento | Situação | Arquivo |", "|---|---|---|---|"]
    md += [f"| {s['pilar_nome']} | {s['tipo_nome']} | {s['estado']} | {s['arquivo'] or 'versão zero em kit-26-11/versao-zero/' + s['pilar']} |" for s in sit]
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "situacao-do-kit.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    r = {"exigidos": len(sit), "ok": sum(s["estado"] == "ok" for s in sit), "faltam": sum(s["estado"] == "falta" for s in sit),
         "versoes_zero": geradas, "dias_para_26_11": dias}
    mv.fechar_alertas_nao_vistos("kit", inicio)
    mv.registrar_execucao("kit", inicio, json.dumps(r, ensure_ascii=False))
    return r


# ---- melhoria contínua -------------------------------------------------------------------------------------------------
MIN_DECISOES = 5          # só calibra com 5+ decisões humanas (parâmetro do método, não limite técnico)


def bot_melhoria(mv) -> dict:
    """Taxa de aprovação de cada bot (Beta(1+aprovados, 1+descartados)) e alertas que mais se repetem."""
    from . import mv_comandos
    inicio = mv.nova_rodada()
    mv_comandos.Comandos(mv)
    out = {}
    for origem, est, n in mv.db.execute("SELECT origem, estado, COUNT(*) FROM mv_pedido_bot GROUP BY origem, estado"):
        o = out.setdefault(origem, {"aprovados": 0, "descartados": 0, "abertos": 0})
        if est in ("aprovado", "pronto"):
            o["aprovados"] += n
        elif est == "descartado":
            o["descartados"] += n
        else:
            o["abertos"] += n
    for origem, o in out.items():
        a, d = o["aprovados"], o["descartados"]
        o["taxa"] = round((1 + a) / (2 + a + d), 2)
        if a + d >= MIN_DECISOES and o["taxa"] < 0.4:
            mv.alertar("melhoria", "baixa_aprovacao", origem, "atencao", f"Bot {origem}: só {o['taxa']:.0%} das sugestões são aprovadas ({a} de {a + d})",
                       "Revisar as regras desse bot (o que a equipe descarta ensina o que cortar)")
        if o["abertos"] >= 20:
            mv.alertar("melhoria", "fila_parada", origem, "info", f"Bot {origem}: {o['abertos']} sugestões esperando decisão", "Aprovar ou descartar na aba Bots e comandos")
    resolvidos = mv.db.execute("SELECT bot, COUNT(*), AVG(resolvido - criado) FROM mv_alerta WHERE resolvido IS NOT NULL GROUP BY bot").fetchall()
    # USO (versão enxuta): em 4 semanas, quantos alertas viraram ação (resolvidos) e quantas sugestões foram decididas.
    agora = time.time()
    janela = agora - 28 * 86400
    uso = {}
    for (bot, primeira) in mv.db.execute("SELECT bot, MIN(inicio) FROM mv_execucao GROUP BY bot").fetchall():
        prod = mv.db.execute("SELECT COUNT(*) FROM mv_alerta WHERE bot=? AND criado>=?", (bot, janela)).fetchone()[0] + \
            mv.db.execute("SELECT COUNT(*) FROM mv_pedido_bot WHERE origem=? AND criado>=?", (bot, janela)).fetchone()[0]
        acoes = mv.db.execute("SELECT COUNT(*) FROM mv_alerta WHERE bot=? AND resolvido>=?", (bot, janela)).fetchone()[0] + \
            mv.db.execute("SELECT COUNT(*) FROM mv_pedido_bot WHERE origem=? AND atualizado>=? AND estado IN ('aprovado','descartado','pronto')",
                          (bot, janela)).fetchone()[0]
        uso[bot] = {"produziu": prod, "acoes": acoes}
        if prod and not acoes and agora - primeira >= 28 * 86400 and bot not in ("vigia", "sentinela", "sala", "backup", "melhoria"):
            mv.alertar("melhoria", "sem_uso", bot, "atencao", f"Bot {bot}: 4 semanas sem nenhuma ação sobre o que ele produziu ({prod} itens)",
                       "Aprovar a redução da frequência ou desligar (pergunta na caixa)")
    ino = out.get("inovacao")
    pri = mv.db.execute("SELECT MIN(inicio) FROM mv_execucao WHERE bot='inovacao'").fetchone()[0]
    if ino and pri and agora - pri >= 30 * 86400:
        total = ino["aprovados"] + ino["descartados"] + ino["abertos"]
        if total and ino["aprovados"] / total < 0.05:
            mv.alertar("melhoria", "inovacao_semanal", "inovacao", "atencao",
                       f"Inovação: {ino['aprovados']} de {total} novidades aprovadas em 30+ dias (menos de 5 %)", "Passar o bot inovação para semanal")
    r = {"por_bot": out, "uso_4_semanas": uso, "resolucao_media_h": {b: round((m or 0) / 3600, 1) for b, n, m in resolvidos}}
    mv.fechar_alertas_nao_vistos("melhoria", inicio)
    mv.registrar_execucao("melhoria", inicio, json.dumps(r, ensure_ascii=False))
    return r


# ---- revisão semanal ---------------------------------------------------------------------------------------------------
def bot_semanal(mv, saida: Path | None = None) -> dict:
    """Versão enxuta: JUNTA o que os outros bots já produziram (não recalcula). Últimas execuções, erros, alertas, caixa e kit."""
    from . import mv_bots, mv_comandos
    inicio = mv.nova_rodada()
    semana = time.time() - 7 * 86400
    rodou = [b for (b,) in mv.db.execute("SELECT DISTINCT bot FROM mv_execucao WHERE fim>=? AND erro=''", (semana,))]
    erros = [f"{b}: {e[:150]}" for b, e in mv.db.execute("SELECT bot, erro FROM mv_execucao WHERE fim>=? AND erro<>'' GROUP BY bot", (semana,))]
    s = mv.saude()
    abertos = mv.db.execute("SELECT bot, gravidade, COUNT(*) FROM mv_alerta WHERE resolvido IS NULL GROUP BY bot, gravidade ORDER BY bot").fetchall()
    perg = mv_comandos.perguntas(mv, abertas=True)
    kit = situacao_kit(mv)
    pasta = Path(saida or (mv_bots.SAIDA / "semanal"))
    pasta.mkdir(parents=True, exist_ok=True)
    md = [f"# Revisão semanal do ecossistema · {time.strftime('%d/%m/%Y')}", "",
          f"Bots que rodaram na semana: {len(rodou)}. Com erro: {len(erros)}{' (' + '; '.join(erros) + ')' if erros else ''}.", "",
          "## Saúde por frente", ""] + [f"- {f['nome']}: nota {f['nota'] if f['nota'] is not None else 'sem dados'}, {f['atrasadas']} atrasada(s), "
                                         f"{f['bloqueadas']} bloqueada(s)" for f in (s.get("frentes") or {}).values()] + [
          "", "## Alertas abertos por bot", ""] + [f"- {b} · {g}: {n}" for b, g, n in abertos] + [
          "", f"## Caixa de perguntas: {len(perg)} aberta(s)", ""] + [f"- {p['pergunta'][:160]}" for p in perg[:30]] + [
          "", "## Kit 26/11", ""] + [f"- {k['pilar_nome']} · {k['tipo_nome']}: {k['estado']}" for k in kit] + [
          "", "Detalhes: plano-de-intervencao.md (auditoria), mapa-ecossistema.md (mercado), situacao-do-kit.md (kit)."]
    arq = pasta / f"revisao-{time.strftime('%Y-%m-%d')}.md"
    arq.write_text("\n".join(md) + "\n", encoding="utf-8")
    if erros:
        mv.alertar("semanal", "erros", "semana", "alerta", f"Na semana, {len(erros)} bot(s) terminaram com erro", "; ".join(erros)[:300])
    r = {"bots": len(rodou), "erros": len(erros), "arquivo": str(arq)}
    mv.fechar_alertas_nao_vistos("semanal", inicio)
    mv.registrar_execucao("semanal", inicio, json.dumps(r, ensure_ascii=False))
    return r


# ── 24/11/2026: kit aprovado no M&A → documento oficial; e as tarefas "Executar" que os bots conseguem fazer sozinhos ──
def gerar_aprovados(mv, destino: Path | None = None) -> dict:
    """Copia cada versão do kit APROVADA no M&A para a pasta oficial do pilar (Sistema Physis/Kit_26-11_aprovado/<pilar>), onde o bot
    de documentos lê e o kit passa a contar como feito. Não apaga nada; não sobrescreve um arquivo que já exista com o mesmo nome."""
    import shutil
    from . import mv_bots
    base = Path(destino or (mv_bots.DOCS / "Sistema Physis" / "Kit_26-11_aprovado"))
    feitos, faltam = [], []
    for pid, cmdtxt, arq in mv.db.execute("SELECT id, comando, arquivo FROM mv_pedido_bot WHERE tipo='kit' AND estado='aprovado'").fetchall():
        _, pil, tipo = (cmdtxt.split(":") + ["", ""])[:3]
        if pil not in PILARES or tipo not in TIPOS_DOC:
            continue
        orig = Path(arq or "")
        if not orig.is_file():
            faltam.append({"pedido": pid, "documento": f"{pil}:{tipo}", "motivo": f"versão aprovada não encontrada: {arq}"})
            continue
        pasta = base / PILARES[pil][0]
        pasta.mkdir(parents=True, exist_ok=True)
        alvo = pasta / f"{TIPOS_DOC[tipo][0].split(' (')[0]} - {PILARES[pil][0]} (aprovado no M&A){orig.suffix}"
        if not alvo.exists():
            shutil.copy2(orig, alvo)
        feitos.append({"pedido": pid, "documento": f"{pil}:{tipo}", "arquivo": str(alvo)})
    return {"gerados": feitos, "faltam": faltam, "pasta": str(base)}


def executar_tarefas(mv, destino: Path | None = None) -> dict:
    """Tarefas 'Executar: …' dos bots: o que o sistema faz sozinho (kit aprovado → documento oficial) é feito e marcado como feito;
    o resto volta numa lista para a equipe (nada é marcado como feito sem ter sido feito)."""
    g = gerar_aprovados(mv, destino)
    feitos_ped = {x["pedido"] for x in g["gerados"]}
    feitas, restantes = [], []
    for tid, titulo in mv.db.execute("SELECT id, titulo FROM mv_tarefa WHERE id LIKE 'exec-%' AND estado<>'feita'").fetchall():
        ref = tid[5:]
        if ref.startswith("ped") and ref[3:].isdigit() and int(ref[3:]) in feitos_ped:
            mv.db.execute("UPDATE mv_tarefa SET estado='feita' WHERE id=?", (tid,))
            feitas.append({"id": tid, "titulo": titulo})
        else:
            restantes.append({"id": tid, "titulo": titulo})
    mv.db.commit()
    return {"feitas": feitas, "restantes": restantes, "kit": g}
