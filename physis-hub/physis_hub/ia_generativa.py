"""IA Physis generativa (v1, 24/11/2026): modelo aberto rodando NO PRÓPRIO COMPUTADOR (Ollama), sem serviço de terceiros (regra 11).

Fluxo de cada pedido (sempre o mesmo, nesta ordem):
  1. BUSCA   – a IA Physis extrativa (ia_physis) escolhe os trechos dos documentos da Physis;
  2. DIRETRIZES – entram as regras que não se quebram (CLAUDE.md), as decisões da dona (perguntas respondidas no M&A)
     e as aprendizagens (rascunhos aprovados e ajustes pedidos);
  3. SKILL   – instruções diretas do tipo de pedido (resposta, e-mail, checklist, resumo, ata, proposta, post, nota ao contador);
  4. GERAÇÃO – o modelo local escreve SÓ com o que veio em 1–2, com [n] das fontes; o que falta vira [MARCADOR];
  5. TRAVA   – todo número da resposta tem de existir nas fontes/diretrizes/pedido; número sem origem vira [MARCADOR] e o
     rascunho é marcado para revisão; resposta sem nenhuma citação também;
  6. RASCUNHO – nada sai sozinho: volta para aprovação. Sem o modelo (desligado, computador fraco), cai no modo extrativo.

Configuração (variáveis de ambiente, fora do código):
  PHYSIS_IA_URL     (padrão http://127.0.0.1:11434 · Ollama)
  PHYSIS_IA_MODELO  (padrão qwen2.5:7b · 32 GB de RAM sobra; com 8 GB use qwen2.5:3b)
  PHYSIS_IA_MODO    generativa (padrão: tenta o modelo e cai no extrativo) | extrativa (nunca chama o modelo)
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[2]
TEMPO_LIMITE = 900       # CPU sem placa de vídeo: 1ª resposta carrega o modelo (minutos); PHYSIS_IA_TEMPO muda

SKILLS = {
    "resposta": "Responda à pergunta em até 6 frases, em português do Brasil, direto ao ponto. Cada frase com fato leva [n].",
    "email": "Escreva um RASCUNHO de e-mail: linha 'Assunto:', saudação, 3 a 8 frases objetivas, despedida com '[MARCADOR] assinatura'. "
             "Destinatário, datas e valores só se estiverem nas fontes; senão [MARCADOR].",
    "checklist": "Escreva um checklist numerado de passos concretos e verificáveis (verbo no infinitivo), na ordem de execução, "
                 "com responsável e prazo quando estiverem nas fontes; senão [MARCADOR].",
    "resumo": "Faça um resumo em tópicos curtos: situação, o que está pronto, o que falta, riscos. Só fatos das fontes, com [n].",
    "ata": "Escreva uma ata: data [MARCADOR se não houver], participantes, pauta, decisões, encaminhamentos (quem, o quê, quando).",
    "proposta": "Escreva a estrutura de uma proposta: objetivo, escopo, entregas, etapas, premissas. Preço, prazo e limites técnicos "
                "SEMPRE [MARCADOR] se não estiverem nas fontes.",
    "post": "Escreva um post para redes da Physis (até 120 palavras), tom claro e profissional, sem promessa nem número que não "
            "esteja nas fontes; termine com 2 a 4 hashtags. É rascunho para aprovação (Rafaella no M&A ou Marzia na Gestão).",
    "contador": "Escreva uma nota ao contador: período, lançamentos/documentos citados nas fontes, dúvidas numeradas. Valores e CNPJ "
                "só das fontes; senão [MARCADOR]. Não dê parecer fiscal.",
}
GATILHOS = [   # texto sem acento → skill
    (r"\b(e-?mail|mensagem para|escreva para|responder a)\b", "email"),
    (r"\b(checklist|passo a passo|passos)\b", "checklist"),
    (r"\b(resum|situacao|status)", "resumo"),
    (r"\bata\b", "ata"),
    (r"\bproposta\b", "proposta"),
    (r"\b(post|instagram|linkedin|publicacao|legenda)\b", "post"),
    (r"\b(contador|contabil|nota fiscal|imposto)", "contador"),
]

BASE = """Você é a IA Physis, assistente interna da Physis Engineering. Regras absolutas:
1. Use SOMENTE as FONTES e as DIRETRIZES abaixo. Não use conhecimento externo.
2. Nunca invente preço, prazo, número, nome de pessoa/cliente, texto legal ou limite técnico. O que faltar escreva [MARCADOR].
3. Cite cada fato com [n] da fonte. Se as fontes não respondem, diga: "Não está nos documentos da Physis." e liste o que falta.
4. Português do Brasil, frases curtas, sem floreio. Não diga que enviou nada: tudo é rascunho para aprovação.
5. Siga as decisões da dona e as aprendizagens; se conflitarem com uma fonte, a decisão mais recente da dona vale e você avisa."""


def _sem_acento(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def skill_para(texto: str) -> str:
    n = _sem_acento(texto)
    for p, s in GATILHOS:
        if re.search(p, n):
            return s
    return "resposta"


def regras_fixas() -> str:
    try:
        t = (RAIZ_REPO / "CLAUDE.md").read_text(encoding="utf-8")
        m = re.search(r"## Regras que não se quebram\n(.*?)\n## ", t, re.S)
        return m.group(1).strip() if m else ""
    except OSError:
        return ""


def diretrizes(mv=None, limite: int = 12) -> dict:
    """Decisões da dona (perguntas respondidas) e aprendizagens (rascunhos aprovados / ajustes) do banco do M&A."""
    dec, apr = [], []
    if mv is not None:
        try:
            for r in mv.db.execute("SELECT pergunta, resposta, nota FROM mv_pergunta WHERE resposta IS NOT NULL AND resposta!='' "
                                   "ORDER BY respondida DESC LIMIT ?", (limite,)):
                dec.append(f"- {r[0]} → {r[1]}" + (f" ({r[2]})" if r[2] else ""))
        except Exception:  # noqa: BLE001 — banco sem a tabela
            pass
        try:
            for r in mv.db.execute("SELECT comando, estado, resultado FROM mv_pedido_bot WHERE estado IN ('aprovado','ajustar') "
                                   "ORDER BY atualizado DESC LIMIT ?", (limite,)):
                apr.append(f"- [{r[1]}] pedido: {r[0][:160]}" + (f" · nota: {r[2][:200]}" if r[1] == "ajustar" and r[2] else ""))
        except Exception:  # noqa: BLE001
            pass
    return {"regras": regras_fixas(), "decisoes": "\n".join(dec), "aprendizagens": "\n".join(apr)}


def montar_prompt(pedido: str, trechos: list[dict], dire: dict, skill: str, contexto: str = "") -> list[dict]:
    fontes = "\n\n".join(f"[{i + 1}] ({t.get('caminho', '')}{' · ' + t['secao'] if t.get('secao') else ''})\n{t.get('texto', '')[:900]}"
                         for i, t in enumerate(trechos)) or "(nenhuma fonte encontrada)"
    sistema = (BASE + "\n\nREGRAS DA PHYSIS:\n" + (dire.get("regras") or "(sem)") +
               "\n\nDECISÕES DA DONA (mais recentes primeiro):\n" + (dire.get("decisoes") or "(nenhuma registrada)") +
               "\n\nAPRENDIZAGENS (o que foi aprovado ou pedido para ajustar):\n" + (dire.get("aprendizagens") or "(nenhuma ainda)") +
               "\n\nTAREFA (" + skill + "): " + SKILLS[skill])
    usuario = (f"CONTEXTO: {contexto}\n\n" if contexto else "") + f"FONTES:\n{fontes}\n\nPEDIDO: {pedido}"
    return [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]


def chamar_modelo(mensagens: list[dict], url: str | None = None, modelo: str | None = None, abrir=urllib.request.urlopen) -> str:
    url = (url or os.environ.get("PHYSIS_IA_URL") or "http://127.0.0.1:11434").rstrip("/")
    modelo = modelo or os.environ.get("PHYSIS_IA_MODELO") or "qwen2.5:7b"
    corpo = json.dumps({"model": modelo, "messages": mensagens, "stream": False, "keep_alive": "60m",
                        "options": {"temperature": 0.1, "num_ctx": 4096, "num_predict": 600}}).encode()
    req = urllib.request.Request(url + "/api/chat", corpo, {"Content-Type": "application/json"})
    with abrir(req, timeout=float(os.environ.get("PHYSIS_IA_TEMPO") or TEMPO_LIMITE)) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["content"].strip()


NUM = re.compile(r"\d+(?:[.,]\d+)*")


def travar(resposta: str, base: str, n_fontes: int) -> tuple[str, list[str]]:
    """Número sem origem vira [MARCADOR]; [n] inexistente sai; sem citação nenhuma → aviso."""
    avisos = []
    permitidos = set(NUM.findall(base))
    def troca(m):
        s = m.group(0)
        ini = m.start()
        if ini > 0 and resposta[ini - 1] == "[" and resposta[m.end():m.end() + 1] == "]":
            return s if 1 <= int(re.sub(r"\D", "", s) or 0) <= n_fontes else ""     # citação [n]
        if s in permitidos or len(re.sub(r"\D", "", s)) <= 1 and s in base:
            return s
        avisos.append(s)
        return "[MARCADOR]"
    saida = NUM.sub(troca, resposta).replace("[]", "")
    if avisos:
        avisos = [f"números sem origem nas fontes trocados por [MARCADOR]: {', '.join(dict.fromkeys(avisos))}"]
    if n_fontes and not re.search(r"\[\d+\]", saida):
        avisos.append("resposta sem citação de fonte: conferir tudo")
    return saida, avisos


def gerar(pedido: str, mv=None, ia=None, contexto: str = "", skill: str | None = None, chamar=None, modo: str | None = None) -> dict:
    """Responde um pedido com o fluxo completo. Sempre devolve {modo, skill, resposta, fontes, avisos, revisao_humana}."""
    from .ia_physis import IAPhysis
    ia = ia or IAPhysis()
    skill = skill or skill_para(pedido)
    limpo = re.sub(r"#\S+", " ", pedido)
    extr = ia.perguntar(limpo)
    if (modo or os.environ.get("PHYSIS_IA_MODO") or "generativa").lower() == "extrativa":
        return {"modo": "extrativa", "skill": skill, **extr, "avisos": []}
    try:
        trechos = ia.buscar(limpo, 5)
    except Exception:  # noqa: BLE001
        trechos = []
    dire = diretrizes(mv)
    msgs = montar_prompt(pedido, trechos, dire, skill, contexto)
    try:
        texto = (chamar or chamar_modelo)(msgs)
    except Exception as e:  # noqa: BLE001 — modelo desligado/ausente: o sistema continua (modo extrativo)
        return {"modo": "extrativa", "skill": skill, **extr,
                "avisos": [f"modelo local indisponível ({type(e).__name__}); resposta extrativa. Ver: ollama serve / PHYSIS_IA_MODELO"]}
    base = pedido + "\n" + contexto + "\n" + "\n".join(t.get("texto", "") for t in trechos) + "\n" + "\n".join(dire.values())
    texto, avisos = travar(texto, base, len(trechos))
    fontes = [{"n": i + 1, "fonte": _rel(t.get("caminho", "")), "secao": t.get("secao", "")} for i, t in enumerate(trechos)]
    return {"modo": "generativa", "skill": skill, "ok": True, "resposta": texto, "fontes": fontes, "avisos": avisos,
            "confianca": extr.get("confianca", 0.0), "revisao_humana": True}


def _rel(c: str) -> str:
    try:
        return str(Path(c).relative_to(RAIZ_REPO))
    except ValueError:
        return Path(c).name if len(c) > 120 else c


def estado() -> dict:
    """Diagnóstico: o modelo responde? (para o teste_zero e o painel)"""
    url = (os.environ.get("PHYSIS_IA_URL") or "http://127.0.0.1:11434").rstrip("/")
    modelo = os.environ.get("PHYSIS_IA_MODELO") or "qwen2.5:7b"
    try:
        with urllib.request.urlopen(url + "/api/tags", timeout=5) as r:
            nomes = [m.get("name", "") for m in json.loads(r.read().decode()).get("models", [])]
        return {"servidor": True, "modelo": modelo, "instalado": any(n.startswith(modelo) for n in nomes), "modelos": nomes}
    except Exception as e:  # noqa: BLE001
        return {"servidor": False, "modelo": modelo, "instalado": False, "erro": type(e).__name__}
