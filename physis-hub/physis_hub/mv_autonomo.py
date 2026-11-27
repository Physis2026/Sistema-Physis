"""Bot autônomo do M&A (pedido da dona de 24/11/2026: "o sistema não deve estar conectado ao Claude; os bots devem ser
autônomos e responder às demandas pedidas").

Texto livre na caixa de comandos é respondido NA HORA, no próprio computador, sem serviço externo (regra 11):
1. reconhece pedidos comuns e roda o comando local equivalente (e-mail, checklist, contrato/ofício/termo/ata/proposta,
   resumo, atrasadas, rodar bots);
2. o resto é respondido pela IA Physis: busca nos documentos + modelo aberto local (ia_generativa), com as fontes; o que não está nos documentos
   vira [MARCADOR] e não é inventado;
3. a resposta volta como RASCUNHO para aprovar (nada sai para fora sozinho).
"""
from __future__ import annotations

import os
import re
import threading
import time
import unicodedata

INTENCOES = [   # (padrão no texto sem acento, comando com {t} = id da tarefa)
    (r"\b(e-?mail|mensagem|escrever para|responder)\b", "/email {t}"),
    (r"\b(checklist|lista de verificacao|passos)\b", "/checklist {t}"),
    (r"\bcontrato\b", "/modelo contrato {t}"),
    (r"\boficio\b", "/modelo oficio {t}"),
    (r"\btermo\b", "/modelo termo {t}"),
    (r"\bata\b", "/modelo ata {t}"),
    (r"\bproposta\b", "/modelo proposta {t}"),
]


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def _ia():
    from .ia_physis import IAPhysis
    return IAPhysis()


def _resumo_tarefas(mv, so_atrasadas: bool) -> str:
    from datetime import date
    hoje = date.today().isoformat()
    # 27/11/2026: a coluna é "fim" (não "prazo") e o estado final é "feita": antes, "atrasadas" sempre falhava
    q = ("SELECT id, titulo, responsavel, fim FROM mv_tarefa WHERE estado NOT IN ('feita','descartada') "
         + ("AND fim IS NOT NULL AND fim!='' AND fim<? " if so_atrasadas else "") + "ORDER BY fim LIMIT 30")
    try:
        rs = mv.db.execute(q, (hoje,) if so_atrasadas else ()).fetchall()
    except Exception:  # noqa: BLE001 — banco antigo sem alguma coluna
        return "Não consegui ler as tarefas deste banco."
    if not rs:
        return "Nenhuma tarefa atrasada." if so_atrasadas else "Nenhuma tarefa em aberto."
    return "\n".join(f"- #{r[0]} · {r[1]} · {r[2] or '[MARCADOR] responsável'} · prazo {r[3] or '[MARCADOR]'}" for r in rs)


# ── AÇÕES DO SISTEMA (27/11/2026): pedidos de uso do sistema que não estão nos documentos ("crie uma tarefa...",
# "rode o resumo todo dia"). A IA não responde com texto: entende a ação, mostra o que vai fazer e espera a aprovação;
# aprovada, o sistema executa. Ação que ele ainda não sabe fazer vira "ação não reconhecida" (lista de melhorias), nunca
# resposta inventada.
VERBO_ACAO = r"\b(cri(a|e|ar)|inclu(a|i|ir)|adicion(a|e|ar)|cadastr(a|e|ar)|registr(a|e|ar)|abr(a|e|ir)|agend(a|e|ar)|program(a|e|ar)|rod(e|ar)|" \
             r"alter(a|e|ar)|mud(a|e|ar)|apag(a|ue|ar)|exclu(a|i|ir)|remov(a|e|er)|marqu(e)|marcar|conclu(a|i|ir)|nova|novo)\b"
FRENTE_PALAVRA = (("inovastem", "inovastem"), ("instituto", "instituto"), ("engineering", "engineering"), ("engenharia", "engineering"),
                  ("casa physis", "casa"), ("loja", "casa"))
BOTS_RODAR = ("atrasos", "documentos", "resumo", "backup", "paginas", "inovacao")
ACOES_CONHECIDAS = ["criar tarefa: \"crie uma tarefa: <título> para <responsável> até <dd/mm/aaaa>\"",
                    "programar bot: \"rode o resumo todo dia\" (atrasos, documentos, resumo, backup, paginas, inovacao; hora, dia ou semana)",
                    "concluir tarefa: \"conclua a tarefa #<id>\""]


def interpretar_acao(texto: str) -> dict | None:
    from datetime import date
    n = _sem_acento(texto).strip()
    if not re.search(VERBO_ACAO, n) or n.endswith("?") or re.match(r"(como|onde|qual|quais|o que|por que|porque|quando|quem|da pra|e possivel)\b", n):
        return None          # pergunta (como criar...?) vai para a IA com os documentos; ação é pedido no imperativo
    m = re.search(r"\bconclu\w*\s+(?:a\s+)?tarefa\s+#?([A-Za-z0-9_.:-]{1,80})", n)
    if m:
        return {"acao": "concluir_tarefa", "id": m.group(1)}
    freq = next((f for rx, f in ((r"\b(todo dia|todos os dias|diariamente)\b", "dia"), (r"\b(toda semana|semanalmente)\b", "semana"),
                                 (r"\b(toda hora|de hora em hora)\b", "hora")) if re.search(rx, n)), None)
    bot = next((b for b in BOTS_RODAR if re.search(r"\b" + b + r"\b", n)), None)
    if freq and bot:
        return {"acao": "programar", "comando": "/rodar " + bot, "frequencia": freq}
    m = re.search(r"\b(tarefa|atividade|pend[eê]ncia)\b\s*[:\-–]?\s*(.+)", texto, re.I | re.S)
    if m and len(m.group(2).strip()) >= 3:
        resto = m.group(2).strip()
        a = {"acao": "criar_tarefa", "frente": "transversal"}
        pz = re.search(r"\b(?:at[eé]|prazo:?|para o dia|no dia)\s+(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", resto, re.I)
        if pz:
            d, mm, y = int(pz.group(1)), int(pz.group(2)), pz.group(3)
            y = int(y) + (2000 if y and len(y) == 2 else 0) if y else date.today().year
            try:
                a["fim"] = date(y, mm, d).isoformat()
            except ValueError:
                a["fim_invalido"] = pz.group(0)
            resto = (resto[:pz.start()] + resto[pz.end():]).strip()
        rp = re.search(r"\b(?:para|respons[aá]vel:?)\s+(?:a\s+|o\s+)?([A-ZÀ-Ú][\wÀ-ú]+(?:\s+[A-ZÀ-Ú][\wÀ-ú]+)?)\s*[,.;]?\s*$", resto)
        if rp:
            a["responsavel"] = rp.group(1)
            resto = resto[:rp.start()].strip()
        a["titulo"] = resto.strip(" .,;:-–")[:300]
        nn = _sem_acento(texto)
        a["frente"] = next((f for k, f in FRENTE_PALAVRA if k in nn), "transversal")
        return a if a["titulo"] else None
    return {"acao": "nao_reconhecida"}


def descrever_acao(a: dict) -> str:
    if a["acao"] == "criar_tarefa":
        return ("Vou CRIAR a tarefa: \"" + a["titulo"] + "\" · responsável " + (a.get("responsavel") or "[MARCADOR]") + " · prazo "
                + (a.get("fim") or ("[CONFERIR] data inválida: " + a["fim_invalido"] if a.get("fim_invalido") else "[MARCADOR]"))
                + " · frente " + a["frente"] + ". Aprove para criar (fica em Tarefas › A fazer).")
    if a["acao"] == "programar":
        return f"Vou PROGRAMAR o bot: {a['comando']} a cada {a['frequencia']}. Aprove para ligar (aba Bots e comandos › programados)."
    if a["acao"] == "concluir_tarefa":
        return f"Vou marcar a tarefa #{a['id']} como CONCLUÍDA. Aprove para confirmar."
    return ("Entendi que é um pedido de AÇÃO no sistema, mas ainda não sei fazer esta ação sozinho. Nada foi mudado. "
            "Ações que sei fazer: " + " · ".join(ACOES_CONHECIDAS) + ". Este pedido fica na lista de melhorias do M&A "
            "(tipo \"ação não reconhecida\") para virar ação automática numa próxima versão; até lá, faça pela aba correspondente.")


def executar_acao(cmd, pid: int, a: dict) -> str:
    """Só depois da aprovação (mv_comandos.decidir_pedido). Devolve o que foi feito."""
    if a.get("acao") == "criar_tarefa":
        t = {"id": f"acao-{int(pid)}", "frente": a.get("frente") or "transversal", "projeto": "Pedidos pela caixa de comandos",
             "titulo": a["titulo"], "responsavel": a.get("responsavel") or "", "fonte": f"pedido #{int(pid)} (aprovado)"}
        if a.get("fim"):
            t["fim"] = a["fim"]
        cmd.mv.salvar_tarefa(t, origem="bot:autonomo")
        return f"Tarefa criada: #{t['id']}."
    if a.get("acao") == "programar":
        r = cmd.programar(a["comando"], a["frequencia"])
        return "Bot programado: " + str(r.get("resultado") or r)[:200]
    if a.get("acao") == "concluir_tarefa":
        t = cmd.mv.tarefa(a["id"])
        if not t:
            return f"Tarefa #{a['id']} não encontrada: nada foi mudado."
        cmd.mv.mudar_estado(a["id"], "feita")
        return f"Tarefa #{a['id']} concluída."
    return "Nada executado (ação não reconhecida)."


def responder(cmd, texto: str, tid: str = "", origem: str = "caixa", ia=None) -> dict:
    """Responde um texto livre sem Claude. cmd = mv_comandos.Comandos. Devolve o pedido gravado."""
    n = _sem_acento(texto)
    if tid:
        for padrao, modelo in INTENCOES:
            if re.search(padrao, n):
                r = cmd.executar(modelo.format(t=tid), origem=origem)
                return r
    ac = interpretar_acao(texto)
    if ac:
        import json as _json
        tipo = "acao" if ac["acao"] != "nao_reconhecida" else "acao_nao_reconhecida"
        return cmd._pedido(tipo, texto, tid, "rascunho", descrever_acao(ac) + ("\n\nACAO " + _json.dumps(ac, ensure_ascii=False) if tipo == "acao" else ""),
                           origem=origem)
    if re.search(r"\b(atrasad|vencid)", n):
        return cmd._pedido("autonomo", texto, tid, "pronto", _resumo_tarefas(cmd.mv, True), origem=origem)
    if re.search(r"\b(tarefas|pendencias|o que falta)\b", n) and len(n.split()) <= 8:
        return cmd._pedido("autonomo", texto, tid, "pronto", _resumo_tarefas(cmd.mv, False), origem=origem)
    contexto = ""
    if tid:
        t = cmd.mv.tarefa(tid) or {}
        contexto = f"Tarefa #{tid}: {t.get('titulo', '')} · responsável {t.get('responsavel') or '[MARCADOR]'} · prazo {t.get('prazo') or '[MARCADOR]'}"
    from . import ia_generativa
    try:      # 1º: resposta na hora pelos trechos (segundos); a tela não espera o modelo
        r = ia_generativa.gerar(texto, cmd.mv, ia=ia, contexto=contexto, modo="extrativa")
    except Exception as e:  # noqa: BLE001 — índice ausente/corrompido: diz o que fazer, não trava
        r = {"resposta": f"IA Physis indisponível ({e}). Rode: py -m physis_hub.mv_cli ia --refazer", "fontes": [], "avisos": []}
    gerativa = (os.environ.get("PHYSIS_IA_MODO") or "generativa").lower() != "extrativa"
    p = cmd._pedido("autonomo", texto, tid, "rascunho", _texto(contexto, r, gerativa), origem=origem)
    if gerativa:   # 2º: o modelo local escreve em segundo plano e substitui o rascunho quando terminar
        threading.Thread(target=_gerar_depois, args=(cmd.mv, p["id"], texto, contexto, ia), daemon=True).start()
    return p


def _texto(contexto: str, r: dict, aguardando: bool = False) -> str:
    partes = [contexto, r.get("resposta", "")]
    if r.get("fontes"):
        partes.append("Fontes: " + "; ".join(f"[{f['n']}] {f['fonte']}" for f in r["fontes"]))
    else:
        partes.append("[MARCADOR] Sem base nos documentos: completar à mão ou acrescentar o documento na pasta da IA.")
    partes += [f"Aviso: {x}" for x in r.get("avisos", []) if not x.startswith("modelo local") or not aguardando]
    partes.append(f"(IA Physis · modo {r.get('modo', 'extrativa')} · {r.get('skill', 'resposta')} · rascunho para aprovar"
                  + (" · o texto escrito pela IA substitui este em alguns minutos)" if aguardando else ")"))
    return "\n".join(x for x in partes if x)


_TRAVA = threading.Lock()      # um pedido por vez no modelo: CPU sem placa de vídeo não aguenta vários


def _gerar_depois(mv, pid: int, texto: str, contexto: str, ia=None) -> None:
    from . import ia_generativa
    with _TRAVA:
        try:
            r = ia_generativa.gerar(texto, mv, ia=ia, contexto=contexto)
            if r.get("modo") != "generativa":
                return
            mv.db.execute("UPDATE mv_pedido_bot SET resultado=?, atualizado=? WHERE id=? AND estado='rascunho'",
                          (_texto(contexto, r)[:20000], time.time(), int(pid)))
            mv.db.commit()
        except Exception:  # noqa: BLE001 — fica a resposta por trechos
            pass


def processar_fila(mv, limite: int = 50) -> dict:
    """Responde os pedidos antigos que ficaram 'na_fila' (de quando iam para o Claude)."""
    from . import mv_comandos
    cmd = mv_comandos.Comandos(mv)
    try:
        fila = mv.db.execute("SELECT id, comando, tarefa, origem FROM mv_pedido_bot WHERE estado='na_fila' ORDER BY criado LIMIT ?",
                             (int(limite),)).fetchall()
    except Exception:  # noqa: BLE001
        return {"respondidos": 0}
    ia, feitos = None, 0
    for pid, comando, tarefa, origem in fila:
        try:
            from . import ia_generativa
            ia = ia or _ia()
            r = ia_generativa.gerar(comando, mv, ia=ia, modo="extrativa")   # vigia: rápido, não ocupa o modelo
            txt = r.get("resposta", "") + ("\nFontes: " + "; ".join(f"[{f['n']}] {f['fonte']}" for f in r["fontes"]) if r.get("fontes")
                                           else "\n[MARCADOR] Sem base nos documentos: completar à mão.")
        except Exception as e:  # noqa: BLE001
            txt = f"IA Physis indisponível ({e})."
        mv.db.execute("UPDATE mv_pedido_bot SET estado='rascunho', resultado=?, tipo='autonomo', atualizado=strftime('%s','now') WHERE id=?",
                      (txt[:20000], pid))
        feitos += 1
    mv.db.commit()
    return {"respondidos": feitos}
