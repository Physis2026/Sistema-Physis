"""Auditoria cruzada, caixa de perguntas das pendências e plano de intervenção final (M&A, 22/11/2026).

1. Cruza todos os bots e módulos da mesma pasta (physis_hub/): bots do M&A × agenda × vigia × sala × mapa de integrações ×
   documentação × testes; robôs do Hub × mapa × documentação × testes; módulos sem uso ou sem teste; variáveis de ambiente sem
   documentação; cópias embutidas e demos desatualizadas.
2. Caixa de perguntas: cada pendência que depende de decisão humana vira UMA pergunta específica (mv_comandos.perguntar, aba
   Aprovações), com opções. Perguntas de limite respondidas com um número passam a valer nos bots (sem mexer em variável).
3. Plano de intervenção: quem faz, o quê, como e como saber que ficou pronto (Markdown e JSON em PHYSIS_MV_SAIDA/intervencao).
Nada é alterado sozinho: a auditoria só aponta, pergunta e planeja (D49).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

RAIZ_HUB = Path(__file__).resolve().parents[1]
RAIZ_REPO = RAIZ_HUB.parent
PACOTE = RAIZ_HUB / "physis_hub"
ENTRADAS = {"servidor", "mv_cli", "mv_servidor", "__init__", "__main__"}     # executados direto, não importados
SEMANAIS: set = set()
SOB_DEMANDA = {"mercado", "modelos"}     # versão enxuta: sem rotina (/mercado <cidade> [área])

LIMITES = {
    "PHYSIS_IOT_MUDO_H": ("dados_iot", "Quantas horas sem leitura de um sensor de campo o bot dados-iot deve considerar \"sensor mudo\"?",
                          ["2", "6", "12", "24"]),
    "PHYSIS_GESTOES_MAX_H": ("gestoes", "Qual a idade máxima, em horas, da exportação de cada Gestão interna antes de o bot gestões avisar?",
                             ["24", "48", "168"]),
    "PHYSIS_EDITAIS_AVISO_DIAS": ("editais", "Com quantos dias de antecedência o bot editais deve avisar que um edital vai fechar?",
                                  ["7", "15", "30"]),
    "PHYSIS_CERT_AVISO_DIAS": ("bancos", "Com quantos dias de antecedência avisar que o certificado HTTPS do Hub vai vencer?", ["14", "21", "30"]),
    "PHYSIS_VENC_AVISO_DIAS": ("vencimentos", "Com quantos dias de antecedência o bot vencimentos deve avisar prazos fiscais, de contratos, ACTs, certidões e licenças?",
                               ["7", "15", "30"]),
    "PHYSIS_FIN_CONFERIR_DIAS": ("financeiro", "Em quantos dias o contador deve conferir cada lançamento antes de o bot financeiro avisar?", ["7", "15", "30"]),
}


def origem_limite(var: str) -> str:
    return f"pendencia:limite:{var}"


def limite_respondido(mv, var: str):
    """Número respondido na caixa de perguntas para um limite (ou None)."""
    try:
        r = mv.db.execute("SELECT resposta FROM mv_pergunta WHERE origem=? AND resposta<>'' ORDER BY respondida DESC LIMIT 1",
                          (origem_limite(var),)).fetchone()
    except Exception:  # noqa: BLE001 — tabela ainda não criada
        return None
    if not r:
        return None
    m = re.search(r"-?\d+(?:[.,]\d+)?", r[0])
    return float(m.group(0).replace(",", ".")) if m else None


PERGUNTAS_FIXAS = [
    ("pendencia:trilhas", "Quais são as trilhas T1 e T2 do InovaSTEM (nome e palavras-chave de cada uma) para o bot acervo propor materiais a partir de 30/11/2026?",
     ["Enviar trilhas.json na pasta InovaSTEM", "Adiar as trilhas"], ["inovastem"], "2026-11-30"),
    ("pendencia:ia", "Nos robôs do Hub, a IA fica só local (IA Physis + modelo aberto, regra 11) ou o Claude continua como opção (D71, teto mensal)?",
     ["Só local (desligar o Claude)", "Claude como opção, com teto", "Decidir depois"], ["sistema-physis", "m&a"], ""),
    ("pendencia:paleta", "Tirar da PALETA.md o azul \"Informação\" (#1C3550 sobre #DBE7F1), já trocado nas telas pelo guia de 19/11?",
     ["Sim, tirar da PALETA.md", "Não, manter"], ["sistema-physis", "templates"], ""),
    ("pendencia:regra2", "As cores, fontes e rodapé foram aplicados direto no SustainKit, SCADA e Planejador (só aparência). Aprovar assim ou mover para a TEMPLATE_PROG?",
     ["Aprovar assim", "Mover para a TEMPLATE_PROG"], ["sistema-physis"], ""),
    ("pendencia:servidor", "Quem instala o servidor físico do Hub e em qual sistema?",
     ["Eric · Windows (instalar.ps1)", "Eric · Linux (instalar.sh)", "Outra pessoa"], ["sistema-physis", "m&a"], ""),
    ("pendencia:backup", "Qual destino e quem guarda a senha da cópia cifrada do Hub (backup.env)?",
     ["Disco externo", "Outro computador da Physis", "Nuvem da Physis"], ["sistema-physis"], ""),
    ("pendencia:cursos", "A plataforma de cursos integrada (Instituto, Physis Engineering, InovaSTEM) roda em qual lugar?",
     ["No Physis Hub", "Na plataforma do Instituto", "Plataforma própria da InovaSTEM"], ["instituto", "inovastem", "sistema-physis"], ""),
    ("pendencia:tipos_lanc", "Acrescentar tipos de lançamento para separar as portas do ecossistema (loja, rede, patrocínio, investimento, imposto)? Hoje só existem receita, despesa, doação, edital e rateio.",
     ["Sim, acrescentar os 5", "Não, usar o campo projeto", "Conversar com o contador"], ["m&a"], ""),
    ("pendencia:cidade_mf", "Em qual cidade fica a Fazenda MF (para o mapa de parcerias e fornecedores)?", ["[escrever a cidade e a UF]"], ["m&a"], ""),
    ("pendencia:cidades", "Quais cidades entram já no mapa de parcerias além de Petrópolis/RJ e Itirapuã/SP (e quando abrir para o Brasil)?",
     ["Só as atuais por enquanto", "Acrescentar cidades (escrever)", "Abrir para o Brasil"], ["m&a", "instituto", "inovastem"], ""),
    ("pendencia:semanal", "Qual dia e hora para a revisão semanal completa (hoje: segunda às 6h)?", ["Segunda 6h", "Sexta 18h", "Outro (escrever)"], ["m&a"], ""),
    ("pendencia:contador", "Quem recebe os rascunhos do bot financeiro (contador) e do bot jurídico (advogado)? O endereço fica na configuração, nunca no código.",
     ["Contador e advogado atuais", "Outra pessoa (escrever)"], ["m&a"], ""),
    ("pendencia:drones", "Em qual projeto começar câmeras com IA e imagens de drone: Casa Physis (Lote 168), Fazenda Santa Clara ou Fazenda MF?",
     ["Casa Physis (Lote 168)", "Fazenda Santa Clara", "Fazenda MF"], ["sistema-physis", "casa"], ""),
    ("pendencia:linux", "O servidor vai ser Linux? (o mv_cli agenda hoje só cria a agenda do Windows; no Linux falta o timer do systemd)",
     ["Sim, fazer o timer do systemd", "Não, Windows"], ["m&a"], ""),
]
ACOES_MARCO = ["Antecipar a tarefa", "Tirar da Fase 0", "Registrar exceção ao marco"]


def _caixa(mv) -> dict:
    """Cria (uma vez) as perguntas da caixa e devolve quantas existem/abertas."""
    from . import mv_comandos
    criadas = []
    for var, (bot, texto, ops) in LIMITES.items():
        criadas.append(mv_comandos.perguntar(mv, texto, ops, origem_limite(var), ["m&a"]))
    for origem, texto, ops, aplica, prazo in PERGUNTAS_FIXAS:
        criadas.append(mv_comandos.perguntar(mv, texto, ops, origem, aplica, prazo))
    for (ref, texto) in mv.db.execute("SELECT ref, texto FROM mv_alerta WHERE bot='atrasos' AND tipo='marco_estourado' AND resolvido IS NULL").fetchall():
        criadas.append(mv_comandos.perguntar(mv, texto.rstrip(".") + ". O que fazer?", ACOES_MARCO, f"pendencia:marco:{ref}", ["m&a"]))
    for (ref, texto) in mv.db.execute("SELECT ref, texto FROM mv_alerta WHERE bot='atrasos' AND tipo='estimada_critica' AND resolvido IS NULL").fetchall():
        criadas.append(mv_comandos.perguntar(mv, texto.split(": ", 1)[-1] + ": qual a data confirmada pelo responsável?",
                                             ["Manter a data estimada"], f"pendencia:data:{ref}", ["m&a"]))
    abertas = sum(1 for p in criadas if not p.get("resposta"))
    return {"perguntas": len(criadas), "abertas": abertas}


def _texto(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def cruzar(conferir_copias: bool = True) -> dict:
    from . import mv_bots, mv_cli, mv_integracoes, mv_vigia, robos
    agenda = mv_cli.texto_agenda()
    docs = " ".join(_texto(p) for p in (RAIZ_HUB / "docs").glob("*.md"))
    testes = " ".join(_texto(p) for p in (RAIZ_HUB / "tests").glob("*.py"))
    sala = _texto(PACOTE / "mv_sala.py")
    falhas, matriz = [], []
    for b in sorted(mv_bots.BOTS):
        linha = {"bot": b, "agenda": re.search(rf"\b{b}\b", agenda) is not None or b in SOB_DEMANDA,
                 "vigia": b in mv_vigia.LIMITE_H or b in ("vigia", "sentinela", "sala") or b in SOB_DEMANDA,
                 "sala": f'"{b}"' in sala, "mapa": b in mv_integracoes.BOT_DO_NO.values(),
                 "docs": re.search(rf"\b{b}\b", docs) is not None,
                 "testes": f'"{b}"' in testes or getattr(mv_bots.BOTS[b], "__name__", "-") + "(" in testes}
        matriz.append(linha)
        for k, ok in linha.items():
            if k != "bot" and not ok:
                falhas.append({"tipo": "bot", "ref": f"{b}:{k}", "texto": f"Bot {b} não aparece em: {k}"})
    robos_m = []
    rob_docs = _texto(RAIZ_HUB / "docs" / "ROBOS.md")
    nos = {n[0] for n in mv_integracoes.NOS}
    for r in sorted(robos.CLASSES):
        linha = {"robo": r, "mapa": f"r_{r}" in nos, "docs": f"\x60{r}\x60" in rob_docs,
                 "testes": r in _texto(RAIZ_HUB / "tests" / "test_robos.py") or robos.CLASSES[r].__name__ in testes}
        robos_m.append(linha)
        for k, ok in linha.items():
            if k != "robo" and not ok:
                falhas.append({"tipo": "robo", "ref": f"{r}:{k}", "texto": f"Robô {r} não aparece em: {k}"})
    mods = sorted(p.stem for p in PACOTE.glob("*.py"))
    fontes = {m: _texto(PACOTE / f"{m}.py") for m in mods}
    # fora do pacote também conta: telas (modo demonstração), conectores e contas-espelho testadas (regra 4)
    fora = testes + " ".join(_texto(p) for p in (RAIZ_HUB / "web").glob("*.html")) + " ".join(
        _texto(p) for p in (RAIZ_REPO / "servicos" / "hub-conectores").glob("*.py")) + " ".join(_texto(p) for p in RAIZ_HUB.glob("*.py"))
    sem_uso, sem_teste = [], []
    for m in mods:
        if m in ENTRADAS:
            continue
        pad = re.compile(rf"(from \. import [^\n]*\b{m}\b|from \.{m} import|physis_hub\.{m}\b|from physis_hub import [^\n]*\b{m}\b|import {m}\b)")
        if not any(pad.search(t) for o, t in fontes.items() if o != m) and not re.search(rf"\b{m}\b", fora):
            sem_uso.append(m)
        if not re.search(rf"\b{m}\b", testes):
            sem_teste.append(m)
    usadas = set()
    for t in fontes.values():
        usadas |= set(re.findall(r"""(?:environ(?:\.get)?\s*[\(\[]\s*|getenv\(\s*|_limite\(\s*|_pede_limite\([^)]*?)["'](PHYSIS_[A-Z0-9_]*[A-Z0-9])["']""", t))   # só leitura de ambiente (não nomes globais do JS)
    doc_env = docs + " ".join(_texto(p) for p in (RAIZ_REPO / "implantacao").glob("*") if p.is_file()) + " ".join(
        _texto(p) for p in (RAIZ_REPO / "servicos" / "env").glob("*")) + _texto(RAIZ_REPO / "servicos" / ".env.exemplo")
    sem_doc = sorted(v for v in usadas if v not in doc_env)
    copias = {}
    if conferir_copias:
        for nome, cmd in (("sincronizar", [sys.executable, str(RAIZ_REPO / "ferramentas" / "sincronizar.py"), "--conferir"]),
                          ("demos", [sys.executable, str(RAIZ_REPO / "demos" / "gerar_demos.py"), "--conferir"])):
            if Path(cmd[1]).is_file():
                try:
                    p = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(RAIZ_REPO))
                    copias[nome] = "ok" if p.returncode == 0 else (p.stdout + p.stderr).strip()[:300]
                except (OSError, subprocess.TimeoutExpired) as e:
                    copias[nome] = repr(e)
    return {"bots": matriz, "robos": robos_m, "falhas": falhas, "modulos_sem_uso": sem_uso, "modulos_sem_teste": sem_teste,
            "variaveis_sem_doc": sem_doc, "copias": copias}


QUEM = {"vencimentos": "Direção / contador / advogado", "fatos": "Direção", "kit": "Direção", "atrasos": "Direção", "documentos": "Equipe (dono do documento)", "editais": "Instituto Physis", "acervo": "Equipe InovaSTEM",
        "cursos": "Equipe InovaSTEM / Instituto", "gestoes": "Administrativo", "paginas": "Design / sistema", "inovacao": "Direção"}


def plano(mv, cr: dict) -> list[dict]:
    from . import mv_comandos
    itens = []
    for bot, tipo, ref, g, texto, acao in mv.db.execute(
            "SELECT bot, tipo, ref, gravidade, texto, acao FROM mv_alerta WHERE resolvido IS NULL AND bot<>'auditoria'").fetchall():
        itens.append({"prioridade": {"alerta": 1, "atencao": 2}.get(g, 3), "quem": QUEM.get(bot, "Engenharia (Eric)"), "origem": f"bot {bot}",
                      "o_que": texto, "como": acao or "Ver o alerta no M&A", "pronto_quando": "o alerta fecha sozinho na rodada seguinte"})
    for f in cr["falhas"]:
        itens.append({"prioridade": 1, "quem": "Engenharia (Eric)", "origem": "auditoria", "o_que": f["texto"],
                      "como": "Ligar o que falta (agenda, vigia, sala, mapa, docs ou teste)", "pronto_quando": "a auditoria não lista mais"})
    for v in cr["variaveis_sem_doc"]:
        itens.append({"prioridade": 3, "quem": "Engenharia (Eric)", "origem": "auditoria", "o_que": f"Variável {v} usada no código sem documentação",
                      "como": "Descrever em docs/ ou no .env.exemplo", "pronto_quando": "a auditoria não lista mais"})
    for nome, st in cr["copias"].items():
        if st != "ok":
            itens.append({"prioridade": 1, "quem": "Engenharia (Eric)", "origem": "auditoria", "o_que": f"{nome}: cópias desatualizadas",
                          "como": "python ferramentas/sincronizar.py e python demos/gerar_demos.py", "pronto_quando": "--conferir sem diferença"})
    for p in mv_comandos.perguntas(mv, abertas=True):
        if p["origem"].startswith("pendencia:"):
            itens.append({"prioridade": 2, "quem": "Direção", "origem": "caixa de perguntas", "o_que": p["pergunta"],
                          "como": "M&A → Aprovações → Perguntas: escolher uma opção ou escrever a resposta",
                          "pronto_quando": "a pergunta aparece como respondida"})
    return sorted(itens, key=lambda x: (x["prioridade"], x["quem"]))


def bot_auditoria(mv, saida: Path | None = None, conferir_copias: bool = True) -> dict:
    from . import mv_bots
    inicio = mv.nova_rodada()
    caixa = _caixa(mv)
    cr = cruzar(conferir_copias)
    for f in cr["falhas"]:
        mv.alertar("auditoria", f["tipo"], f["ref"], "atencao", f["texto"], "Ver o plano de intervenção")
    for nome, st in cr["copias"].items():
        if st != "ok":
            mv.alertar("auditoria", "copias", nome, "alerta", f"{nome}: cópias desatualizadas", "python ferramentas/sincronizar.py; python demos/gerar_demos.py")
    for v in cr["variaveis_sem_doc"]:
        mv.alertar("auditoria", "variavel", v, "info", f"Variável {v} sem documentação", "Descrever em docs/")
    itens = plano(mv, cr)
    pasta = Path(saida or (mv_bots.SAIDA / "intervencao"))
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "plano-de-intervencao.json").write_text(json.dumps({"cruzamento": cr, "caixa": caixa, "itens": itens}, ensure_ascii=False, indent=1),
                                                     encoding="utf-8")
    sim = lambda v: "✅" if v else "❌"  # noqa: E731
    md = ["# Plano de intervenção final", "", f"Gerado em {time.strftime('%d/%m/%Y %H:%M')} pela auditoria do M&A. Prioridade 1 = agora; 2 = decisão; 3 = depois.", "",
          f"Caixa de perguntas: **{caixa['abertas']} aberta(s)** de {caixa['perguntas']} (M&A → Aprovações → Perguntas).", "",
          "## Cruzamento dos bots do M&A", "", "| Bot | Agenda | Vigia | Sala | Mapa | Docs | Testes |", "|---|---|---|---|---|---|---|"]
    md += [f"| {l['bot']} | " + " | ".join(sim(l[k]) for k in ("agenda", "vigia", "sala", "mapa", "docs", "testes")) + " |" for l in cr["bots"]]
    md += ["", "## Robôs do Hub", "", "| Robô | Mapa | Docs | Testes |", "|---|---|---|---|"]
    md += [f"| {l['robo']} | " + " | ".join(sim(l[k]) for k in ("mapa", "docs", "testes")) + " |" for l in cr["robos"]]
    md += ["", f"Módulos sem uso por outro módulo: {', '.join(cr['modulos_sem_uso']) or 'nenhum'}.",
           f"Módulos sem teste que os cite: {', '.join(cr['modulos_sem_teste']) or 'nenhum'}.",
           f"Variáveis sem documentação: {', '.join(cr['variaveis_sem_doc']) or 'nenhuma'}.",
           "Cópias e demos: " + (", ".join(f"{k}: {v}" for k, v in cr["copias"].items()) or "não conferido") + ".", "",
           "## O que fazer (em ordem)", "", "| # | Prioridade | Quem | O quê | Como | Pronto quando |", "|---|---|---|---|---|---|"]
    md += [f"| {i} | {x['prioridade']} | {x['quem']} | {x['o_que'][:160]} | {x['como'][:120]} | {x['pronto_quando']} |" for i, x in enumerate(itens, 1)]
    (pasta / "plano-de-intervencao.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    r = {"perguntas_abertas": caixa["abertas"], "falhas_cruzamento": len(cr["falhas"]), "itens_plano": len(itens),
         "variaveis_sem_doc": len(cr["variaveis_sem_doc"]), "arquivo": str(pasta / "plano-de-intervencao.md")}
    mv.fechar_alertas_nao_vistos("auditoria", inicio)
    mv.registrar_execucao("auditoria", inicio, json.dumps(r, ensure_ascii=False))
    return r
