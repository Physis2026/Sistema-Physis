"""Versão DEMO (mock) do Physis M&V: a mesma tela (web/mv.html) com dados FICTÍCIOS embutidos, funcionando sem servidor.

Para mostrar a parceiros, financiadores e editais sem expor dados reais. Nenhum dado do banco verdadeiro é lido: tudo é
gerado aqui, num banco em memória, com nomes genéricos e marcados como fictícios. As contas (caminho crítico, saúde,
alertas, editais) são as do sistema de verdade, rodadas sobre esses dados.

    python -m physis_hub.mv_mock --saida <arquivo.html>
"""
from __future__ import annotations

import argparse
import base64
import json
from datetime import date, timedelta
from pathlib import Path

from . import mv as mvmod
from . import mv_bots
from .mv import MV
from .mv_editais import Editais, necessidades_de

WEB = Path(__file__).resolve().parents[1] / "web"
HOJE = date(2026, 11, 20)

# id, frente, título, responsável, início (dias a partir de hoje), duração, depende_de, prioridade, meta, estado
TAREFAS = [
    ("d1", "transversal", "Constituir a entidade sem fins lucrativos (exemplo)", "Coordenação [fictício]", -10, 40, [], 0, "dm-base", "fazendo"),
    ("d2", "transversal", "Contratos de uso do espaço entre as entidades (exemplo)", "Jurídico [fictício]", 30, 20, ["d1"], 1, "dm-base", "a_fazer"),
    ("d3", "engineering", "Publicar 8 módulos na loja de demonstração", "Produto [fictício]", -20, 25, [], 1, "dm-produto", "fazendo"),
    ("d4", "engineering", "Piloto de M&V planejado × medido num cliente-exemplo", "Engenharia [fictício]", 5, 60, ["d3"], 1, "dm-produto", "a_fazer"),
    ("d5", "engineering", "Validar a linha de base com casos de teste oficiais", "Engenharia [fictício]", 66, 30, ["d4"], 2, "dm-produto", "a_fazer"),
    ("d6", "instituto", "Teoria da Mudança do programa de formação (exemplo)", "Pesquisa [fictício]", -5, 15, [], 1, "dm-impacto", "revisao"),
    ("d7", "instituto", "Indicadores SMART com linha de base e metas", "Pesquisa [fictício]", 11, 20, ["d6"], 2, "dm-impacto", "a_fazer"),
    ("d8", "inovastem", "Lançar a plataforma de formação online", "Comunidade [fictício]", -3, 7, [], 0, "dm-rede", "fazendo"),
    ("d9", "inovastem", "Hackathon de cibersegurança (ambiente isolado)", "Comunidade [fictício]", 90, 3, ["d8"], 2, "dm-rede", "a_fazer"),
    ("d10", "casa", "Licenças de operação do living lab (exemplo)", "Operações [fictício]", -40, 30, [], 1, "dm-lab", "bloqueada"),
    ("d11", "casa", "Abrir as reservas da hospedagem-piloto", "Operações [fictício]", 120, 30, ["d10"], 3, "dm-lab", "a_fazer"),
    ("d12", "transversal", "Revisão trimestral do portfólio", "Coordenação [fictício]", -30, 5, [], 2, "dm-base", "feita"),
]
METAS = [
    ("dm-base", "transversal", 2027, "Estrutura jurídica e contratos prontos [fictício]", "Contratos assinados", "100 %"),
    ("dm-produto", "engineering", 2027, "M&V verificado em clientes-piloto [fictício]", "Projetos com relatório IPMVP", "[exemplo]"),
    ("dm-impacto", "instituto", 2028, "Programa com cadeia de resultados e indicadores SMART [fictício]", "Indicadores com linha de base", "[exemplo]"),
    ("dm-rede", "inovastem", 2027, "Rede de formação ativa [fictício]", "Participantes e conclusão", "[exemplo]"),
    ("dm-lab", "casa", 2029, "Living lab em operação [fictício]", "Operação licenciada", "[exemplo]"),
]
EDITAIS = [
    {"chave": "demo1", "titulo": "Chamada Exemplo de Inovação em Energia 2027 [fictício]", "financiador": "Agência Exemplo", "tipo": "edital",
     "prazo": (HOJE + timedelta(days=9)).isoformat(), "status": "aberto", "frente_mais_aderente": "engineering", "aderencia": "alta",
     "fonte_verificada": "sim", "via_parceria": "nao", "documentos_exigidos": "Plano de trabalho|Orçamento|Currículos",
     "exigencias_formais": "Cadastro na plataforma|Contrapartida 10 %", "criterios_avaliacao_pesos": "Mérito 30|Equipe 20|Impacto 30|Orçamento 20"},
    {"chave": "demo2", "titulo": "Prêmio Exemplo de Mulheres em STEM [fictício]", "financiador": "Fundação Exemplo", "tipo": "premio",
     "prazo": (HOJE + timedelta(days=25)).isoformat(), "status": "aberto", "frente_mais_aderente": "inovastem", "aderencia": "media",
     "fonte_verificada": "nao", "via_parceria": "sim", "perfil_parceiro": "OSC com 2+ anos [exemplo]",
     "documentos_exigidos": "Vídeo de 3 min|Carta de apoio", "exigencias_formais": "Organização sem fins lucrativos"},
    {"chave": "demo3", "titulo": "Fundo Exemplo de Soluções Baseadas na Natureza [fictício]", "financiador": "Fundo Exemplo", "tipo": "edital",
     "prazo": (HOJE + timedelta(days=60)).isoformat(), "status": "aberto", "frente_mais_aderente": "instituto", "aderencia": "alta",
     "fonte_verificada": "sim", "via_parceria": "sim", "perfil_parceiro": "Prefeitura parceira [exemplo]",
     "documentos_exigidos": "Teoria da Mudança|Indicadores", "exigencias_formais": "Estatuto|Certidões"},
]


def montar() -> dict:
    mvmod.HOJE = lambda: HOJE
    mv = MV(":memory:")
    for m in METAS:
        mv.db.execute("INSERT INTO mv_meta VALUES (?,?,?,?,?,?,?)", (*m, "Demonstração (dados fictícios)"))
    mv.db.execute("INSERT INTO mv_marco (id,frente,data,titulo,meta,fase) VALUES (?,?,?,?,?,?)",
                  ("dk1", "transversal", (HOJE + timedelta(days=70)).isoformat(), "Marco exemplo: estrutura pronta [fictício]", "dm-base", "Fase 0"))
    for tid, fr, tit, resp, ini, dur, dep, pri, meta, est in TAREFAS:
        i = HOJE + timedelta(days=ini)
        mv.salvar_tarefa({"id": tid, "frente": fr, "titulo": tit, "responsavel": resp, "inicio": i.isoformat(),
                          "fim": (i + timedelta(days=dur - 1)).isoformat(), "depende_de": dep, "prioridade": pri, "meta": meta,
                          "estado": est, "bloqueio": "Aguardando órgão licenciador [fictício]" if est == "bloqueada" else "",
                          "data_estimada": ini > 30, "fonte": "demonstração"}, origem="semente")
    for e, d, t, v in (("engineering", -15, "receita", 12000), ("instituto", -10, "doacao", 5000), ("casa", -5, "despesa", 3000)):
        mv.lancar({"entidade": e, "tipo": t, "data": (HOJE + timedelta(days=d)).isoformat(), "valor": v,
                   "descricao": "Lançamento fictício", "conferido": e == "engineering"})
    mv.db.execute("INSERT INTO mv_documento VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  ("Exemplo/apresentacao_antiga.pptx", "apresentacao_antiga.pptx", "engineering", "apresentacao", ".pptx",
                   "2021-03-01", 2048, (HOJE - date(2021, 3, 1)).days, 90, "", json.dumps([{"regra": "horizonte",
                   "texto": "Horizonte desatualizado (exemplo)", "decisao": "demo", "gravidade": "atencao", "trecho": "…"}]), 2, "falha", 0))
    mv.db.commit()
    ed = Editais(mv)
    for r in EDITAIS:
        eid = "ed:" + r["chave"]
        mv.db.execute("INSERT INTO mv_edital (id,titulo,financiador,tipo,prazo,status,frente,aderencia,verificado,via_parceria,"
                      "perfil_parceiro,criterios,etapa,necessidades,criado,atualizado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,0)",
                      (eid, r["titulo"], r["financiador"], r["tipo"], r["prazo"], r["status"], r["frente_mais_aderente"], r["aderencia"],
                       1 if r["fonte_verificada"] == "sim" else 0, 1 if r["via_parceria"] == "sim" else 0, r.get("perfil_parceiro", ""),
                       r.get("criterios_avaliacao_pesos", ""), "preparar" if r["chave"] == "demo1" else "decidir",
                       json.dumps(necessidades_de(r), ensure_ascii=False)))
    mv.db.commit()
    mv_bots.bot_atrasos(mv, HOJE)
    from .mv_servidor import FRENTES, NOMES_ESTADO, ESTADOS  # noqa: F401 (mesmas listas da tela)
    from . import mv_editais
    return {
        "/api/mv/meta": {"frentes": [{"id": a, "nome": b, "descricao": c} for a, b, c in mvmod.FRENTES],
                         "estados": [{"id": e, "nome": mvmod.NOMES_ESTADO[e]} for e in mvmod.ESTADOS],
                         "etapas": [{"id": e, "nome": mv_editais.NOMES_ETAPA[e]} for e in mv_editais.ETAPAS]},
        "/api/mv/saude": mv.saude(), "/api/mv/gantt": mv.gantt(), "/api/mv/kanban": mv.kanban(), "/api/mv/matriz": mv.matriz(),
        "/api/mv/roadmap": mv.roadmap(), "/api/mv/alertas": mv.alertas(), "/api/mv/documentos": mv.documentos(),
        "/api/mv/editais": ed.listar(),
    }


def montar_real(caminho: str | Path | None = None) -> dict:
    """Cópia de LEITURA do banco verdadeiro (sem dados fictícios), para abrir o M&V fora do servidor. Mesmas visões da tela."""
    from datetime import datetime
    from . import mv_editais
    mv = MV(caminho)
    ed = Editais(mv)
    return {"modo": "real", "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "/api/mv/meta": {"frentes": [{"id": a, "nome": b, "descricao": c} for a, b, c in mvmod.FRENTES],
                             "estados": [{"id": e, "nome": mvmod.NOMES_ESTADO[e]} for e in mvmod.ESTADOS],
                             "etapas": [{"id": e, "nome": mv_editais.NOMES_ETAPA[e]} for e in mv_editais.ETAPAS]},
            "/api/mv/saude": mv.saude(), "/api/mv/gantt": mv.gantt(), "/api/mv/kanban": mv.kanban(), "/api/mv/matriz": mv.matriz(),
            "/api/mv/roadmap": mv.roadmap(), "/api/mv/alertas": mv.alertas(), "/api/mv/documentos": mv.documentos(),
            "/api/mv/editais": ed.listar()}


def gerar(saida: str | Path, real: bool = False) -> Path:
    dados = montar_real() if real else montar()
    icone = WEB / "logo-physis.png"
    if not icone.is_file():
        icone = WEB / "app" / "icone-192.png"
    if icone.is_file():
        dados["logo"] = "data:image/png;base64," + base64.b64encode(icone.read_bytes()).decode()
    html = (WEB / "mv.html").read_text(encoding="utf-8")
    bloco = "<script>window.MV_MOCK=" + json.dumps(dados, ensure_ascii=False, default=str).replace("</", "<\\/") + ";</script>\n"
    html = html.replace("<script>\n\"use strict\";", bloco + "<script>\n\"use strict\";", 1)
    html = html.replace("<title>Physis M&amp;V · versão de teste</title>",
                        "<title>Physis M&amp;V · cópia de leitura</title>" if real else "<title>Physis M&amp;V · demonstração</title>", 1)
    saida = Path(saida)
    saida.write_text(html, encoding="utf-8")
    return saida


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="physis-mv-mock")
    ap.add_argument("--saida", required=True)
    ap.add_argument("--real", action="store_true", help="cópia de leitura do banco verdadeiro, sem dados fictícios")
    a = ap.parse_args()
    print(gerar(a.saida, real=a.real))
