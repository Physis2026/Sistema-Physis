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
    q = ("SELECT id, titulo, responsavel, prazo FROM mv_tarefa WHERE estado NOT IN ('concluida','descartada') "
         + ("AND prazo!='' AND prazo<? " if so_atrasadas else "") + "ORDER BY prazo LIMIT 30")
    try:
        rs = mv.db.execute(q, (hoje,) if so_atrasadas else ()).fetchall()
    except Exception:  # noqa: BLE001 — banco antigo sem alguma coluna
        return "Não consegui ler as tarefas deste banco."
    if not rs:
        return "Nenhuma tarefa atrasada." if so_atrasadas else "Nenhuma tarefa em aberto."
    return "\n".join(f"- #{r[0]} · {r[1]} · {r[2] or '[MARCADOR] responsável'} · prazo {r[3] or '[MARCADOR]'}" for r in rs)


def responder(cmd, texto: str, tid: str = "", origem: str = "caixa", ia=None) -> dict:
    """Responde um texto livre sem Claude. cmd = mv_comandos.Comandos. Devolve o pedido gravado."""
    n = _sem_acento(texto)
    if tid:
        for padrao, modelo in INTENCOES:
            if re.search(padrao, n):
                r = cmd.executar(modelo.format(t=tid), origem=origem)
                return r
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
