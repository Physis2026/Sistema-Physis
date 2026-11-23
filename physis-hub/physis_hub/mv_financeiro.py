"""Assessoria contábil/financeira e jurídica do M&A (bots "financeiro" e "juridico", 22/11/2026).

Conferem, alertam e PREPARAM e-mails como rascunho para o contador e o advogado (fila de pedidos, aba Bots e comandos):
nada é enviado sem aprovação (D49). Entidades nunca somadas entre si (D70). Nada de cálculo de imposto inventado (regra 1):
o bot aponta o que falta para o contador calcular.

financeiro: lançamento sem comprovante (fonte), sem projeto, duplicado, não conferido há mais que o limite (caixa de
perguntas), saldo do mês negativo por entidade, fluxo por projeto e por "porta" (loja, rede, patrocínio, investimento,
imposto: hoje só pela palavra no projeto/descrição, até a direção decidir os tipos novos), NF-e (XML) sem lançamento e
lançamento sem NF-e quando a pasta de notas existe.
vencimentos (substitui o bot jurídico e o calendário fiscal, versão enxuta de 22/11/2026): ver bot_vencimentos.
"""
from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date
from pathlib import Path

PORTAS = {"loja": r"\bloja\b", "rede": r"\brede\b", "patrocinio": r"patroc", "investimento": r"invest", "imposto": r"impost|tribut|das\b|iss\b|icms",
          "edital": r"edital", "doacao": r"doa[cç]", "projeto_cliente": r"cliente|proposta"}
NFE = "{http://www.portalfiscal.inf.br/nfe}"


def _porta(texto: str) -> str:
    t = texto.lower()
    return next((p for p, rx in PORTAS.items() if re.search(rx, t)), "geral")


def ler_nfe(xml: bytes) -> dict | None:
    """Chave, data, CNPJ do emitente e destinatário e valor total de uma NF-e (nfeProc ou NFe)."""
    try:
        r = ET.fromstring(xml)
    except ET.ParseError:
        return None
    inf = r.find(f".//{NFE}infNFe")
    if inf is None:
        return None
    g = lambda caminho: (inf.findtext(caminho) or "").strip()  # noqa: E731
    return {"chave": (inf.get("Id") or "").replace("NFe", ""), "data": (g(f"{NFE}ide/{NFE}dhEmi") or g(f"{NFE}ide/{NFE}dEmi"))[:10],
            "emitente": g(f"{NFE}emit/{NFE}CNPJ"), "destinatario": g(f"{NFE}dest/{NFE}CNPJ") or g(f"{NFE}dest/{NFE}CPF"),
            "valor": float(g(f"{NFE}total/{NFE}ICMSTot/{NFE}vNF") or 0)}


def _email(mv, para: str, assunto: str, itens: list[str], origem: str) -> None:
    from . import mv_comandos
    if not itens:
        return
    cmd = mv_comandos.Comandos(mv)
    ref = f"email:{origem}:{time.strftime('%Y-%m-%d')}"
    if mv.db.execute("SELECT 1 FROM mv_pedido_bot WHERE comando=?", (ref,)).fetchone():
        return
    corpo = (f"Para: {para}\nAssunto: {assunto}\n\nOlá,\n\nO acompanhamento do Physis M&A encontrou os pontos abaixo. Pode nos ajudar a "
             "esclarecer?\n\n- " + "\n- ".join(itens[:40]) + ("\n- (… mais itens no M&A)" if len(itens) > 40 else "") +
             "\n\nObrigado,\nPhysis Engineering Ltda.\n\n[rascunho gerado pelo M&A: revisar antes de enviar]")
    cmd._pedido("email", ref, "", "rascunho", corpo, origem=origem)


def bot_financeiro(mv, pasta_notas: Path | None = None, hoje: date | None = None) -> dict:
    from . import mv as mvmod
    from .mv_auditoria import limite_respondido
    from . import mv_bots
    inicio = mv.nova_rodada()
    hoje = hoje or mvmod.HOJE()
    lancs = [dict(zip(("id", "entidade", "data", "tipo", "valor", "descricao", "projeto", "fonte", "conferido"), r)) for r in
             mv.db.execute("SELECT id,entidade,data,tipo,valor,descricao,projeto,fonte,conferido FROM mv_lanc")]
    itens = []
    lim = limite_respondido(mv, "PHYSIS_FIN_CONFERIR_DIAS")
    vistos = defaultdict(list)
    saldo = defaultdict(float)
    fluxo = defaultdict(lambda: defaultdict(float))
    for l in lancs:
        rot = f"#{l['id']} {l['entidade']} {l['data']} {l['tipo']} R$ {l['valor']:.2f} {l['descricao'][:50]}"
        if not l["fonte"].strip():
            mv.alertar("financeiro", "sem_comprovante", str(l["id"]), "atencao", f"Lançamento sem comprovante: {rot}",
                       "Anexar o comprovante/nota (campo fonte) ou pedir ao contador", l["entidade"])
            itens.append(f"Sem comprovante: {rot}")
        if l["tipo"] in ("receita", "edital", "doacao", "rateio") and not l["projeto"].strip():
            mv.alertar("financeiro", "sem_projeto", str(l["id"]), "atencao", f"Lançamento sem projeto: {rot}",
                       "Ligar ao projeto (fluxo por projeto)", l["entidade"])
        if not l["conferido"] and lim is not None:
            idade = (hoje - date.fromisoformat(l["data"][:10])).days
            if idade > lim:
                mv.alertar("financeiro", "nao_conferido", str(l["id"]), "atencao", f"Não conferido pelo contador há {idade} d: {rot}",
                           "Conferência do contador (D70)", l["entidade"])
                itens.append(f"Conferir: {rot}")
        chave = (l["entidade"], l["data"], round(l["valor"], 2), l["tipo"], l["descricao"].strip().lower())
        vistos[chave].append(l["id"])
        sinal = -1 if l["tipo"] in ("despesa", "rateio") else 1
        saldo[(l["entidade"], l["data"][:7])] += sinal * abs(l["valor"])
        fluxo[(l["entidade"], l["projeto"] or "(sem projeto)")][_porta(l["projeto"] + " " + l["descricao"])] += sinal * abs(l["valor"])
    for ch, ids in vistos.items():
        if len(ids) > 1:
            mv.alertar("financeiro", "duplicado", ",".join(map(str, ids)), "alerta", f"Lançamentos repetidos {ids}: {ch[0]} {ch[1]} R$ {ch[2]:.2f}",
                       "Conferir se é o mesmo pagamento", ch[0])
            itens.append(f"Possível duplicidade: lançamentos {ids}")
    for (ent, mes), s in saldo.items():
        if s < 0:
            mv.alertar("financeiro", "saldo_negativo", f"{ent}:{mes}", "atencao", f"{ent} fecha {mes} com saldo negativo (R$ {s:.2f}) nos lançamentos",
                       "Conferir lançamentos faltando ou planejar o caixa", ent)
    # NF-e
    pasta = Path(pasta_notas or os.environ.get("PHYSIS_NOTAS") or (mv_bots.DOCS / "Sistema Physis" / "notas"))
    notas = []
    if pasta.is_dir():
        for f in sorted(pasta.rglob("*.xml")):
            n = ler_nfe(f.read_bytes())
            if n:
                notas.append(n | {"arquivo": f.name})
        usados = set()
        for n in notas:
            par = next((l for l in lancs if l["id"] not in usados and abs(abs(l["valor"]) - n["valor"]) < 0.01 and l["data"][:10] == n["data"]), None)
            if par:
                usados.add(par["id"])
            else:
                mv.alertar("financeiro", "nota_sem_lancamento", n["chave"] or n["arquivo"], "alerta",
                           f"NF-e {n['arquivo']} ({n['data']}, R$ {n['valor']:.2f}, emitente {n['emitente']}) sem lançamento igual", "Lançar ou conferir")
                itens.append(f"NF-e sem lançamento: {n['arquivo']} R$ {n['valor']:.2f} em {n['data']}")
    else:
        mv.alertar("financeiro", "sem_pasta_notas", str(pasta), "info", f"Pasta das NF-e (XML) não encontrada: {pasta}",
                   "Salvar os XML das notas nessa pasta ou definir PHYSIS_NOTAS")
    _email(mv, "[contador]", "Pontos para conferir no financeiro da Physis", itens, "financeiro")
    r = {"lancamentos": len(lancs), "notas": len(notas), "itens_para_contador": len(itens),
         "fluxo": {f"{e} · {p}": {k: round(v, 2) for k, v in d.items()} for (e, p), d in fluxo.items()},
         "saldo_mes": {f"{e} {m}": round(s, 2) for (e, m), s in saldo.items()}}
    mv.fechar_alertas_nao_vistos("financeiro", inicio)
    mv.registrar_execucao("financeiro", inicio, json.dumps(r, ensure_ascii=False))
    return r


JURIDICO = re.compile(r"jur[ií]dic|contrat|\bACT\b|acordo|termo|estatuto|ata\b|cess[aã]o|licen[cç]", re.I)
TIPOS_VENC = ("fiscal", "contrato", "act", "certidao", "licenca", "documento", "juridico", "edital", "outro")


def _ics(eventos: list[dict]) -> str:
    """Calendário aberto (iCalendar, RFC 5545): abre no Thunderbird, Outlook, Google Agenda, celular."""
    linhas = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Physis//M&A vencimentos//PT-BR", "CALSCALE:GREGORIAN"]
    agora = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    for e in eventos:
        d = e["data"].replace("-", "")
        uid = re.sub(r"[^A-Za-z0-9]+", "-", f"{e['tipo']}-{e['item']}-{d}")[:80] + "@physis-ma"
        resumo = f"[{e['tipo']}] {e['item']}".replace("\n", " ").replace(",", "\\,").replace(";", "\\;")
        linhas += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{agora}", f"DTSTART;VALUE=DATE:{d}", f"SUMMARY:{resumo[:200]}",
                   f"DESCRIPTION:{(e.get('responsavel') or '')} {(e.get('fonte') or '')}".replace(",", "\\,")[:300], "END:VEVENT"]
    return "\r\n".join(linhas + ["END:VCALENDAR"]) + "\r\n"


def bot_vencimentos(mv, hoje: date | None = None, saida: Path | None = None) -> dict:
    """Vencimentos (substitui o bot jurídico e o calendário fiscal): tarefas jurídicas, vencimentos.csv (fiscal, contratos,
    ACTs, certidões, licenças: quem informa é o contador/advogado/equipe), prazos de editais e documentos vencidos.
    Alerta só o que é dele (jurídico e planilha); editais e documentos aparecem no calendário sem alerta repetido."""
    import csv
    import io
    from . import mv as mvmod, mv_bots
    from .mv_auditoria import limite_respondido
    inicio = mv.nova_rodada()
    hoje = hoje or mvmod.HOJE()
    aviso = limite_respondido(mv, "PHYSIS_VENC_AVISO_DIAS")
    pasta = Path(saida or (mv_bots.SAIDA / "vencimentos"))
    pasta.mkdir(parents=True, exist_ok=True)
    plan = pasta / "vencimentos.csv"
    if not plan.is_file():
        plan.write_text("item;tipo;data;responsavel;fonte\n", encoding="utf-8")
    ev = []
    for r in csv.DictReader(io.StringIO(plan.read_text(encoding="utf-8-sig")), delimiter=";"):
        if (r.get("item") or "").strip() and re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("data") or "").strip()):
            ev.append({"item": r["item"].strip(), "tipo": (r.get("tipo") or "outro").strip().lower(), "data": r["data"].strip(),
                       "responsavel": r.get("responsavel", ""), "fonte": r.get("fonte", "") or "vencimentos.csv", "alerta": True})
    for tid, tit, proj, fim, est, resp in mv.db.execute(
            "SELECT id, titulo, projeto, fim, estado, responsavel FROM mv_tarefa WHERE estado<>'feita' AND fim IS NOT NULL").fetchall():
        if re.match(r"^j\d", tid or "", re.I) or JURIDICO.search(f"{tit} {proj}"):
            ev.append({"item": tit, "tipo": "juridico", "data": fim[:10], "responsavel": resp, "fonte": f"tarefa {tid}", "alerta": True})
    try:
        for tit, prazo in mv.db.execute("SELECT titulo, prazo FROM mv_edital WHERE etapa IN ('triagem','decidir','preparar','revisao')"):
            m = re.match(r"(\d{4}-\d{2}-\d{2})", prazo or "")
            if m:
                ev.append({"item": tit, "tipo": "edital", "data": m.group(1), "responsavel": "", "fonte": "bot editais", "alerta": False})
    except Exception:  # noqa: BLE001 — tabela de editais ainda não criada
        pass
    for nome, idade, validade in mv.db.execute("SELECT nome, idade_d, validade_d FROM mv_documento WHERE validade_d > 0"):
        venc = date.fromordinal(hoje.toordinal() - idade + validade)
        ev.append({"item": f"revisar {nome}", "tipo": "documento", "data": venc.isoformat(), "responsavel": "", "fonte": "bot documentos", "alerta": False})
    ev.sort(key=lambda e: e["data"])
    juridicos, fiscais = [], []
    for e in ev:
        if not e["alerta"]:
            continue
        dias = (date.fromisoformat(e["data"]) - hoje).days
        if dias < 0 or (aviso is not None and dias <= aviso):
            g = "alerta" if dias < 0 else "atencao"
            mv.alertar("vencimentos", e["tipo"], f"{e['tipo']}:{e['item']}"[:150], g,
                       f"{'Vencido' if dias < 0 else 'Vence em ' + str(dias) + ' d'} ({e['data']}): [{e['tipo']}] {e['item']}",
                       f"Responsável: {e['responsavel'] or '[definir]'}")
            (fiscais if e["tipo"] == "fiscal" else juridicos).append(f"{e['data']} · {e['item']}")
    if aviso is None:
        mv.alertar("vencimentos", "sem_limite", "PHYSIS_VENC_AVISO_DIAS", "info", "Antecedência de aviso dos vencimentos não definida: só avisa o que já venceu",
                   "Responder na caixa de perguntas")
    _email(mv, "[advogado]", "Prazos jurídicos da Physis", juridicos, "vencimentos-juridico")
    _email(mv, "[contador]", "Prazos fiscais da Physis", fiscais, "vencimentos-fiscal")
    (pasta / "calendario-de-vencimentos.ics").write_text(_ics(ev), encoding="utf-8", newline="")
    md = ["# Calendário de vencimentos", "", f"Gerado em {hoje.strftime('%d/%m/%Y')}. Importe o .ics na agenda. Fiscal, contratos e ACTs: vencimentos.csv.", "",
          "| Data | Tipo | Item | Responsável | Fonte |", "|---|---|---|---|---|"]
    md += [f"| {e['data']} | {e['tipo']} | {e['item'][:90]} | {e['responsavel'] or ''} | {e['fonte']} |" for e in ev if e["data"] >= hoje.isoformat()][:200]
    (pasta / "calendario-de-vencimentos.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    r = {"eventos": len(ev), "proximos_ou_vencidos": len(juridicos) + len(fiscais), "arquivo": str(pasta / "calendario-de-vencimentos.ics")}
    mv.fechar_alertas_nao_vistos("vencimentos", inicio)
    mv.registrar_execucao("vencimentos", inicio, json.dumps(r, ensure_ascii=False))
    return r
