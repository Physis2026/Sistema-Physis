"""Tarefas reais dos clientes, projetos e parceiros no M&A (pedido da dona, 21/11/2026).

Antes, cada conta tinha só "esclarecer a ficha". Aqui entram as entregas já combinadas, com o prazo que a dona deu
(data confirmada) ou com a data marcada [CONFERIR] (data_estimada) quando ainda não foi confirmada. Só cria ou atualiza
tarefas com id "real-…"; não toca nas outras. Rodar de novo não duplica nada.
Uso: python ferramentas_mv_tarefas_reais.py   (banco em PHYSIS_MV_DADOS; sem a variável, o oficial)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from physis_hub.mv import MV  # noqa: E402

# (id, frente, projeto, título, responsável, início, fim, prioridade, data confirmada?)
T = [
    # Estermic · P0 até 24/11 (doc 44); versão interna ao Ryan em 23/11 às 13h59
    ("real-est-dados", "engineering", "Estermic", "Preencher os dados com a Casa Physis caso os da Estermic não cheguem", "Rafaella", "2026-11-21", "2026-11-22", 1, True),
    ("real-est-ep", "engineering", "Estermic", "EP (Estudo Preliminar): relatório e memorial de cálculo no template neutro", "Ryan", "2026-11-21", "2026-11-23", 1, True),
    ("real-est-pecas", "engineering", "Estermic", "Lista de equipamentos e peças com part number em todas as peças de reposição", "Ryan", "2026-11-21", "2026-11-23", 1, True),
    ("real-est-interna", "engineering", "Estermic", "Versão interna do módulo AVAC personalizado ao Ryan (23/11 às 13h59)", "Rafaella", "2026-11-21", "2026-11-23", 0, True),
    ("real-est-fim-p0", "engineering", "Estermic", "Fim da prioridade 0: revisão final da entrega (24/11)", "Rafaella", "2026-11-23", "2026-11-24", 0, True),
    ("real-est-nf", "engineering", "Estermic", "Nota fiscal por e-mail e WhatsApp; fases de pagamento por etapa do projeto; ISS definido pelo contador", "Rafaella", "2026-11-24", "2026-11-28", 2, False),
    # Rede Taças e Turbinas · evento 21/11 (revisão interna 14h, envio externo 18h)
    ("real-tt-mapa", "inovastem", "Rede Taças e Turbinas", "Revisar o mapa de conteúdo e design da aula e da apresentação", "Rafaella", "2026-11-21", "2026-11-21", 0, True),
    ("real-tt-aula", "inovastem", "Rede Taças e Turbinas", "Aula de PDI de 40 min (versão para revisão)", "Rafaella", "2026-11-20", "2026-11-21", 0, True),
    ("real-tt-apresentacao", "inovastem", "Rede Taças e Turbinas", "Apresentação: lançamento 0 da InovaSTEM, parcerias e investimento, previsões 2027, grupos de WhatsApp", "Rafaella", "2026-11-20", "2026-11-21", 0, True),
    ("real-tt-revisao", "inovastem", "Rede Taças e Turbinas", "Revisão interna dos dois materiais às 14h", "Rafaella", "2026-11-21", "2026-11-21", 0, True),
    ("real-tt-qr", "inovastem", "Rede Taças e Turbinas", "QR codes dos grupos de WhatsApp (entram por último, nos espaços reservados)", "Rafaella", "2026-11-21", "2026-11-21", 1, True),
    ("real-tt-envio", "inovastem", "Rede Taças e Turbinas", "Envio externo às 18h, só com autorização da dona", "Rafaella", "2026-11-21", "2026-11-21", 0, True),
    # WhatsApp Business · estratégia até 22/11, testes a partir de 23/11
    ("real-wa-estrategia", "transversal", "WhatsApp", "Estratégia do WhatsApp Business (grupos por frente, respostas, catálogo)", "Rafaella", "2026-11-21", "2026-11-22", 0, True),
    ("real-wa-automacoes", "transversal", "WhatsApp", "Automações prontas para teste (a partir de 23/11)", "Rafaella", "2026-11-22", "2026-11-23", 1, True),
    # Global South Alliance · reunião de alinhamento em 25/11
    ("real-gsa-reuniao", "transversal", "Global South Alliance", "Reunião de alinhamento da Global South Alliance", "Rafaella", "2026-11-25", "2026-11-25", 1, True),
    ("real-gsa-docs", "transversal", "Global South Alliance", "Alimentar os documentos da aliança depois da reunião", "Rafaella", "2026-11-25", "2026-11-28", 2, False),
    # GIZ PtX · contrato direto
    ("real-giz-escopo", "engineering", "GIZ PtX", "Confirmar escopo, fases e invoice com a GIZ", "Rafaella", "2026-11-24", "2026-11-28", 2, False),
    ("real-giz-tributos", "engineering", "GIZ PtX", "Exportação de serviço: conferir a tributação com o contador", "Rafaella", "2026-11-24", "2026-11-28", 2, False),
    # Clientes da plataforma (dentro do Sistema Physis)
    ("real-mf-modulos", "engineering", "Fazenda MF", "Confirmar os módulos contratados", "Rafaella", "2026-11-24", "2026-11-28", 2, False),
    ("real-mf-dados", "engineering", "Fazenda MF", "Carregar os dados reais na plataforma do cliente", "Rafael", "2026-11-28", "2026-12-05", 3, False),
    ("real-sc-modulos", "engineering", "Fazenda Santa Clara", "Confirmar os módulos e os dados reais", "Rafaella", "2026-11-24", "2026-11-28", 2, False),
    ("real-sc-versao", "engineering", "Fazenda Santa Clara", "Escolher a versão da plataforma (v1 ou v2)", "Rafaella", "2026-11-24", "2026-11-28", 2, False),
    # Captação municipal 2027 (doc 46)
    ("real-mun-serrana", "engineering", "Captação municipal 2027", "Lista de secretarias e e-mails da Região Serrana (46b)", "Rafaella", "2026-11-21", "2026-11-30", 2, False),
    ("real-mun-modelos", "engineering", "Captação municipal 2027", "Modelos municipais para aprovação (apresentação, uma página por secretaria, proposta de piloto)", "Rafaella", "2026-11-24", "2026-12-05", 2, False),
    ("real-mun-munic", "engineering", "Captação municipal 2027", "Recorte nacional pela pesquisa MUNIC (46c)", "Rafaella", "2026-12-01", "2026-12-15", 3, False),
    ("real-mun-envios", "engineering", "Captação municipal 2027", "Primeiros envios (rascunhos aprovados pela dona)", "Rafaella", "2027-01-05", "2027-01-15", 3, False),
]


def main():
    mv = MV()
    for tid, fr, pj, tit, resp, ini, fim, prio, conf in T:
        ant = mv.tarefa(tid) or {}
        mv.salvar_tarefa({"id": tid, "frente": fr, "projeto": pj, "titulo": tit, "responsavel": ant.get("responsavel") or resp,
                          "estado": ant.get("estado") or "a_fazer", "inicio": ant.get("inicio") or ini, "fim": ant.get("fim") or fim,
                          "prioridade": prio, "data_estimada": (not conf) if not ant else bool(ant.get("data_estimada")),
                          "fonte": "Pedidos da dona (chat 19–21/11/2026)"}, origem="conta")
    print(len(T), "tarefas reais gravadas em", mv.caminho if hasattr(mv, "caminho") else "banco do M&A")


if __name__ == "__main__":
    main()
