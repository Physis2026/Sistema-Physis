"""Mapa de integrações do Sistema Physis (aba Monitoramento do M&A e mapa avulso). Fonte única dos dados.

Cada nó é um sistema (engrenagem no 3D); cada aresta é uma passagem de informação, com o arquivo do código onde ela
aparece. Aresta "opcional" = depende de configuração (IA externa ou modelo local). Atualizado em 22/11/2026: InovaSTEM e
Modelagem/Physis 3D como plataformas próprias (atendem várias frentes), plataforma de cursos integrada (Instituto,
Physis Engineering, InovaSTEM), robôs do Hub (suporte, preços, editais, marketing, projetos, pluviômetro), trilha
quântica (QUBO) e IA Physis.
"""
from __future__ import annotations

import time

GRUPOS = {"plat": ["Plataformas", "#0B3D2E"], "mod": ["Modelagem e Gêmeo Virtual", "#F97316"],
          "srv": ["Serviços e infraestrutura", "#23282D"], "iot": ["Campo (IoT)", "#BB6B4A"],
          "ma": ["M&A e frentes", "#7C3AED"], "bot": ["Bots do M&A", "#4A8A5A"], "robo": ["Robôs do Hub", "#2F7D5B"],
          "ia": ["IA Physis", "#C2410C"], "opc": ["Opcional", "#B9A97F"]}

# id, nome, grupo, descrição
NOS = [
    ("hub", "Physis Hub (servidor :8700)", "srv", "Servidor central em Python: contas, APIs, registro encadeado, saúde."),
    ("loja", "Loja (site)", "plat", "Seleção de módulos e catálogo (/api/loja/catalogo)."),
    ("plataforma", "Plataforma do cliente", "plat", "painel.html: abas do cliente; abre SustainKit, SCADA e Planejador."),
    ("gestao", "Gestão Physis interna", "plat", "gestao-interna-physis.html em /gestao/ (direção e administrativo)."),
    ("central", "Central de clientes", "plat", "Só desenho (desenhos/); as rotas /api/central/* já existem no Hub."),
    ("instituto_plat", "Plataforma do Instituto (repo próprio)", "plat", "Repositório do Instituto; liga-se ao Hub pelo Intercâmbio."),
    ("inovastem_plat", "Plataforma InovaSTEM", "plat", "Plataforma própria da InovaSTEM, que atende várias frentes (Instituto, Physis Engineering, Casa)."),
    ("physis3d", "Modelagem / Physis 3D", "plat", "Plataforma de modelagem 3D (aba Modelagem 3D do M&A, galeria, impressão, escaneamento); atende várias frentes."),
    ("cursos_plat", "Plataforma de cursos (integrada)", "plat", "Uma plataforma de cursos para Instituto Physis, Physis Engineering e InovaSTEM (em preparação; trilhas a partir de 30/11/2026)."),
    ("mv", "Physis M&A (núcleo :8710)", "ma", "Gestão nível 2: CPM, alertas, saúde por frente, abas Monitoramento e Modelagem 3D."),
    ("casa", "Casa Physis", "ma", "Frente com Gestão interna própria."),
    ("eng", "Physis Engineering", "ma", "Frente com Gestão interna própria."),
    ("inst", "Instituto Physis", "ma", "Frente do Instituto (ICT, NIT, editais)."),
    ("inovastem", "InovaSTEM (frente)", "ma", "Frente InovaSTEM no M&A (piloto T1/T2, hackathon, InovaSTEM Delas)."),
    ("pastas", "Pastas de documentos", "ma", "OneDrive: Sistema Physis, Casa Physis, Instituto Physis, Global South Alliance, Estermic (e Marketing Physis como repositório)."),
    ("sustainkit", "SustainKit", "mod", "Programa de sustentabilidade (Agro, Água, Energia, Materiais, Certificação)."),
    ("scada", "SCADA / Monitoramento", "mod", "physis-scada-demo.html: supervisão das leituras."),
    ("planejador", "Planejador", "mod", "Lote e implantação; entrega o lote ao Mapeamento."),
    ("mapeamento", "Mapeamento (contexto do lugar)", "mod", "Camadas abertas, sol em cada superfície, planta solar."),
    ("simulacao", "Simulação (Gêmeo Virtual)", "mod", "Térmica, estrutura, fluidos, terreno, biogás, incerteza."),
    ("bim", "BIM IFC4", "mod", "ifc.py + web-ifc: modelo com o que os módulos dimensionaram."),
    ("quantica", "Trilha quântica (QUBO · Qiskit)", "mod", "QUBO resolvido no clássico; Qiskit só em contêiner (P&D, nunca em relatório)."),
    ("calc", "Serviço calc", "srv", "PV, eólica, térmica, drenagem, rede de água."),
    ("documentos_srv", "Serviço documentos (ODF/PDF-A)", "srv", "Gera documentos ODF e PDF/A."),
    ("mqtt", "Mosquitto (MQTT)", "srv", "Broker das leituras de campo."),
    ("timescale", "TimescaleDB (séries)", "srv", "Séries temporais das leituras."),
    ("postgis", "PostGIS", "srv", "Dados geográficos."),
    ("geoserver", "GeoServer", "srv", "Publica camadas geográficas."),
    ("superset", "Superset (painéis)", "srv", "Painéis de dados."),
    ("firmware", "Receptor/Transmissor V6", "iot", "Firmware de campo (protocolo V6)."),
    ("caixinha", "Caixinha, pluviômetro, secador, animais", "iot", "ESPHome, SmartColar, AutoFeeder."),
    ("r_suporte", "Robô suporte", "robo", "Responde com a documentação, citando a fonte; senão, chamado."),
    ("r_precos", "Robô preços", "robo", "Aponta itens de proposta fora da faixa de preço."),
    ("r_editais", "Robô editais", "robo", "Ordena editais pela semelhança com a Physis."),
    ("r_marketing", "Robô marketing", "robo", "Aprende quais temas engajam (Beta-Binomial) e junta com a nota da Gestão."),
    ("r_projetos", "Robô projetos", "robo", "Esqueleto de projeto a partir de um edital."),
    ("r_pluviometro", "Robô pluviômetro", "robo", "YAML ESPHome e cadastro de pluviômetro."),
    ("ia_physis", "IA Physis (própria)", "ia", "Índice próprio dos textos da Physis; respostas com fonte, sem terceiros."),
    ("vllm", "Modelo aberto local (vLLM)", "opc", "Opcional (PHYSIS_IA_URL): só reescreve, mantendo as fontes."),
    ("claude", "Claude (externo)", "opc", "Opcional nos robôs do Hub (ia_claude.py); regra 11: nunca único caminho."),
    ("b_atrasos", "bot atrasos", "bot", "Prazos, dependências e marcos."), ("b_documentos", "bot documentos", "bot", "Validade e regras dos documentos."),
    ("b_resumo", "bot resumo", "bot", "Resumo diário MD + ODT."), ("b_backup", "bot backup", "bot", "Cópia diária do banco do M&A."),
    ("b_paginas", "bot páginas", "bot", "Checklist base das telas."), ("b_links", "bot links", "bot", "Links externos das telas."),
    ("b_inovacao", "bot inovação", "bot", "Feeds abertos → pedidos para aprovação."), ("b_vigia", "bot vigia", "bot", "Cada bot rodou no prazo e sem erro."),
    ("b_sentinela", "bot sentinela", "bot", "verificar.sh/ps1 + docker compose ps."), ("b_sala", "bot sala", "bot", "Sala visual dos bots."),
    ("b_editais", "bot editais", "bot", "Prazos e necessidades das propostas."), ("b_acervo", "bot acervo → trilhas", "bot", "Materiais para as trilhas aprovadas."),
    ("b_iot", "bot dados-iot", "bot", "Idade da última leitura por nó."), ("b_simul", "bot simulação", "bot", "Casos do Gêmeo Virtual em dia."),
    ("b_gestoes", "bot gestões", "bot", "Exportações das Gestões importadas."), ("b_bancos", "bot bancos/certificados", "bot", "Integridade, HTTPS e segredos."),
    ("b_cursos", "bot cursos (mapa)", "bot", "Mapeia temas de cursos nos documentos; rechecagem automática."),
    ("b_ia", "bot índice IA", "bot", "Atualiza o índice da IA Physis."),
    ("b_auditoria", "bot auditoria", "bot", "Cruza bots, robôs e módulos; caixa de perguntas; plano de intervenção."),
    ("b_mercado", "bot mercado e parcerias (sob demanda)", "bot", "Fabricantes, fornecedores, testes, estágio, laboratórios, hubs, investidores, supermercados, collabs e resíduos por cidade; mapa GIS."),
    ("b_camadas", "bot camadas de mapa", "bot", "Baixa e converte as camadas (OpenStreetMap, NASA POWER e os endereços oficiais de fontes-camadas.txt) na janela das cidades da Physis."),
    ("b_modelos", "bot modelos dos fabricantes (diário)", "bot", "Lê os catálogos guardados pela equipe e propõe os modelos de cada fabricante da lista para aprovar."),
    ("b_financeiro", "bot financeiro (contábil)", "bot", "Comprovantes, duplicidades, conferência, saldo, fluxo por projeto e porta, NF-e; rascunho ao contador."),
    ("b_vencimentos", "bot vencimentos", "bot", "Calendário único: jurídico, fiscal, contratos, ACTs, certidões, editais e documentos (.ics); rascunhos ao advogado e ao contador."),
    ("b_desenv", "bot desenvolvimento", "bot", "Painel Desenvolvimento de cada módulo (sistema/desenvolvimento-dados.js) a partir das tarefas do M&A."),
    ("b_sincro", "bot sincronização", "bot", "Leva as melhorias dos módulos compartilhados entre Sistema, Instituto e InovaSTEM; testa antes; commit só local."),
    ("modelagem3d_mod", "Módulo Modelagem 3D", "mod", "modulos/modelagem3d: visualizador STL/OBJ, galeria, impressão, escaneados (saiu do M&A em 22/11)."),
    ("b_repos", "bot repositórios", "bot", "Acompanha os repositórios fora do sistema (marketing-physis): commits, alterações não salvas, cópia, inventário."),
    ("marketing_repo", "Marketing Physis (repositório)", "plat", "OneDrive › Documents › Marketing Physis: plano, planilhas, validação de dezembro, integrações e logos (Fase 2)."),
    ("b_fatos", "bot base de fatos", "bot", "Fonte única dos fatos, checagem de consistência e preenchimento das versões zero."),
    ("b_kit", "bot kit 26/11", "bot", "Documentos exigidos por pilar; versão zero com dados do M&A."),
    ("b_melhoria", "bot melhoria contínua", "bot", "Aprende com aprovações e descartes; aponta o bot a calibrar."),
    ("b_semanal", "bot revisão semanal", "bot", "Regressão completa uma vez por semana."),
    ("fornecedores_hub", "Fornecedores (Hub)", "srv", "fornecedores.py: cadastro oficial com curadoria (solar; outras áreas na fase 2)."),
    ("parceiros_hub", "Profissionais parceiros (Hub)", "srv", "parceiros.py: instaladores e projetistas com curadoria."),
    ("residuos_hub", "Resíduos e economia circular (Hub)", "srv", "residuos_gis.py: destinos pelo OpenStreetMap."),
    ("aprendizado_hub", "Aprendizado e indicadores (Hub)", "srv", "aprendizado.py (chuva, anomalias, consumo, irrigação) e indicadores.py."),
    ("dados_abertos", "Bases de dados abertas", "opc", "OSM, IBGE, CNPJ, ANEEL, INMETRO, e-MEC, CNPq, SINIR, CVM, NASA POWER…"),
]
BOT_DO_NO = {"b_atrasos": "atrasos", "b_documentos": "documentos", "b_resumo": "resumo", "b_backup": "backup", "b_paginas": "paginas",
             "b_links": "links", "b_inovacao": "inovacao", "b_vigia": "vigia", "b_sentinela": "sentinela", "b_sala": "sala",
             "b_editais": "editais", "b_acervo": "acervo", "b_iot": "dados_iot", "b_simul": "simulacao", "b_gestoes": "gestoes",
             "b_bancos": "bancos", "b_cursos": "cursos", "b_ia": "ia", "b_auditoria": "auditoria", "b_mercado": "mercado", "b_modelos": "modelos", "b_camadas": "camadas", "b_financeiro": "financeiro", "b_vencimentos": "vencimentos", "b_fatos": "fatos", "b_repos": "repositorios", "b_desenv": "desenvolvimento", "b_sincro": "sincronizacao", "b_kit": "kit", "b_melhoria": "melhoria", "b_semanal": "semanal"}

# de, para, o que passa, fonte no código, opcional
ARESTAS = [
    ("hub", "plataforma", "estado do cliente, leituras, alertas", "physis-ponte-cliente.js"), ("plataforma", "hub", "ações do cliente", "/api/cliente/estado"),
    ("hub", "loja", "catálogo de módulos", "/api/loja/catalogo"), ("loja", "hub", "pedido / compra", "/api/central/compra"),
    ("hub", "gestao", "estado da gestão", "gestao-ponte.js"), ("gestao", "hub", "alterações da gestão", "/api/gestao/estado"),
    ("hub", "central", "clientes, instalações, pedidos", "/api/central/*"),
    ("hub", "instituto_plat", "dados aprovados", "INTERCAMBIO.md"), ("instituto_plat", "hub", "dados aprovados", "INTERCAMBIO.md"),
    ("plataforma", "sustainkit", "abre em quadro", "painel.html"), ("plataforma", "scada", "abre em quadro", "painel.html"),
    ("plataforma", "planejador", "abre em quadro", "painel.html"),
    ("planejador", "mapeamento", "lote", "MAPEAMENTO.md"), ("mapeamento", "planejador", "contexto do lugar", "MAPEAMENTO.md"),
    ("mapeamento", "sustainkit", "contexto, sol, planta solar", "MAPEAMENTO.md"), ("mapeamento", "bim", "modelo IFC4", "/api/mapeamento/ifc"),
    ("mapeamento", "simulacao", "terreno e sol", "SIMULACAO.md"), ("simulacao", "plataforma", "cartões de resultado", "SIMULACAO.painel()"),
    ("simulacao", "quantica", "problema physis-qubo/1", "simulacao/qubo.py exportar()"), ("quantica", "simulacao", "resultado comparado ao clássico", "conteiner/qubo_qiskit.py"),
    ("bim", "physis3d", "modelo BIM", "ifc.py / web-ifc"), ("physis3d", "mv", "galeria, pedidos de impressão", "mv.html · Modelagem 3D"),
    ("physis3d", "instituto_plat", "Physis 3D (licença J7)", "INTERCAMBIO.md"), ("simulacao", "physis3d", "resultados no modelo", "SIMULACAO.md"),
    ("physis3d", "casa", "modelos da Casa", "Modelagem 3D"), ("physis3d", "eng", "modelos dos projetos", "Modelagem 3D"),
    ("hub", "calc", "pedidos de cálculo", "calc_cliente.py"), ("calc", "hub", "resultados", "calc_cliente.py"),
    ("hub", "documentos_srv", "conteúdo", "documentos_cliente.py"), ("documentos_srv", "hub", "ODF / PDF-A", "/api/documentos/pdfa"),
    ("firmware", "mqtt", "linhas V6", "PROTOCOLO.md"), ("caixinha", "mqtt", "leituras", "ESPHome"), ("mqtt", "hub", "leituras", "mqtt.py"),
    ("hub", "scada", "leituras", "/api/leituras"), ("mqtt", "timescale", "séries", "servicos/"), ("timescale", "superset", "séries", "servicos/"),
    ("postgis", "geoserver", "camadas", "servicos/"), ("geoserver", "mapeamento", "camadas publicadas", "servicos/"),
    # robôs do Hub
    ("hub", "r_suporte", "pergunta", "/api/robos/suporte"), ("r_suporte", "plataforma", "resposta com fonte", "robos.Suporte"),
    ("loja", "r_precos", "itens da proposta", "/api/robos/precos"), ("r_precos", "central", "itens fora da faixa", "robos.Precos"),
    ("hub", "r_editais", "editais coletados", "editais.py"), ("r_editais", "r_projetos", "edital escolhido", "robos.Projetos"),
    ("r_projetos", "gestao", "esqueleto de projeto", "robos.Projetos"),
    ("gestao", "r_marketing", "temas e métricas (Instagram, LinkedIn, site)", "Gestão → Marketing → Temas"),
    ("r_marketing", "gestao", "engajamento esperado por tema", "robos.Marketing"),
    ("hub", "r_pluviometro", "lugar e pino", "/api/robos/pluviometro"), ("r_pluviometro", "caixinha", "YAML ESPHome", "robos.Pluviometro"),
    ("claude", "r_suporte", "texto melhorado", "ia_claude.py", 1), ("claude", "r_projetos", "texto melhorado", "ia_claude.py", 1),
    # IA Physis
    ("pastas", "ia_physis", "documentos compartilhados", "ia_physis.indexar"), ("hub", "ia_physis", "documentação e código", "ia_physis.fontes_padrao"),
    ("ia_physis", "mv", "respostas com fonte (/api/mv/ia)", "mv_servidor.py"), ("ia_physis", "b_cursos", "temas por plataforma", "ia_physis.temas"),
    ("vllm", "ia_physis", "reescrita mantendo fontes", "PHYSIS_IA_URL", 1), ("b_ia", "ia_physis", "índice atualizado", "ia_physis.bot_ia"),
    # cursos
    ("b_cursos", "cursos_plat", "mapa-de-cursos.json", "mv_cursos.py"), ("cursos_plat", "instituto_plat", "cursos do Instituto", "mv_cursos.plataformas"),
    ("cursos_plat", "inovastem_plat", "trilhas InovaSTEM", "mv_cursos.plataformas"), ("cursos_plat", "plataforma", "cursos da Physis Engineering", "mv_cursos.plataformas"),
    ("b_cursos", "mv", "potenciais de curso para aprovação", "mv_pedido_bot"), ("b_acervo", "cursos_plat", "materiais por trilha", "mv_bots_extra.bot_acervo"),
    ("inovastem_plat", "inst", "atende", "InovaSTEM"), ("inovastem_plat", "eng", "atende", "InovaSTEM"), ("inovastem_plat", "casa", "atende", "InovaSTEM"),
    # M&A e frentes
    ("casa", "mv", "exportação physis/1", "mv_cli importar"), ("eng", "mv", "exportação physis/1", "mv_cli importar"),
    ("inst", "mv", "exportação physis/1", "mv_cli importar"), ("inovastem", "mv", "tarefas e metas", "mv_semente"), ("gestao", "mv", "tarefas da Gestão ao vivo (de hora em hora)", "mv_bots_extra.gestao_ao_vivo"),
    # bots do M&A
    ("mv", "b_atrasos", "tarefas e marcos", "mv_bots.bot_atrasos"), ("b_atrasos", "mv", "alertas de prazo", "mv_alerta"),
    ("pastas", "b_documentos", "arquivos", "mv_bots.bot_documentos"), ("b_documentos", "mv", "alertas e tarefas", "mv_alerta"),
    ("mv", "b_resumo", "saúde e alertas", "mv_bots.resumo"), ("b_resumo", "pastas", "resumo MD + ODT", "PHYSIS_MV_SAIDA"),
    ("mv", "b_backup", "banco", "mv_bots.backup"), ("b_backup", "pastas", "cópia diária", "PHYSIS_MV_BACKUP"),
    ("loja", "b_paginas", "HTML", "mv_paginas"), ("gestao", "b_paginas", "HTML", "mv_paginas"), ("plataforma", "b_paginas", "HTML", "mv_paginas"),
    ("b_paginas", "mv", "checklist", "mv_alerta"), ("planejador", "b_links", "links externos", "mv_paginas"), ("b_links", "mv", "links quebrados", "mv_alerta"),
    ("b_inovacao", "mv", "pedidos para aprovação", "mv_inovacao"), ("b_inovacao", "quantica", "tema: computação quântica", "mv_inovacao.FONTES"),
    ("b_inovacao", "physis3d", "tema: three.js, gêmeo digital", "mv_inovacao.FONTES"),
    ("mv", "b_vigia", "execuções", "mv_vigia"), ("b_vigia", "mv", "bot parado / com erro", "mv_alerta"),
    ("hub", "b_sentinela", "saúde", "mv_vigia.bot_sentinela"), ("b_sentinela", "mv", "falhas de serviço", "mv_alerta"),
    ("mv", "b_sala", "estado dos bots", "mv_sala"),
    ("pastas", "b_editais", "banco_editais.csv", "mv_bots_extra.bot_editais"), ("b_editais", "inst", "prazos para o ICT", "mv_alerta"),
    ("pastas", "b_acervo", "acervo", "mv_bots_extra.bot_acervo"), ("timescale", "b_iot", "leituras", "mv_bots_extra.bot_dados_iot"),
    ("hub", "b_iot", "tabela leitura", "mv_bots_extra.bot_dados_iot"), ("b_iot", "mv", "sensor mudo", "mv_alerta"),
    ("simulacao", "b_simul", "casos e premissas", "mv_bots_extra.bot_simulacao"), ("b_simul", "mv", "conta divergente", "mv_alerta"),
    ("gestao", "b_gestoes", "exportações", "mv_bots_extra.bot_gestoes"), ("b_gestoes", "mv", "gestão sem importar", "mv_alerta"),
    ("hub", "b_bancos", "bancos, HTTPS, Git", "mv_bots_extra.bot_bancos"), ("b_bancos", "mv", "alertas", "mv_alerta"),
    ("pastas", "b_cursos", "documentos compartilhados", "mv_cursos.plataformas"),
    ("mv", "b_auditoria", "bots, alertas, perguntas", "mv_auditoria.cruzar"), ("hub", "b_auditoria", "módulos, robôs, variáveis", "mv_auditoria.cruzar"),
    ("b_auditoria", "mv", "caixa de perguntas e plano de intervenção", "mv_auditoria.bot_auditoria"),
    ("dados_abertos", "b_mercado", "pontos e cadastros abertos", "mv_ecossistema.DADOS_ABERTOS"), ("pastas", "b_mercado", "parcerias.csv da equipe", "mv_ecossistema"),
    ("b_mercado", "mapeamento", "parcerias.geojson (mapa GIS)", "mv_ecossistema.geojson"), ("b_mercado", "mv", "candidatos a conferir e lacunas", "mv_pedido_bot"),
    ("b_mercado", "fornecedores_hub", "candidatos para o cadastro oficial", "FORNECEDORES.md"), ("pastas", "b_modelos", "catálogos dos fabricantes", "mv_modelos"), ("b_camadas", "mapeamento", "camadas em PHYSIS_CAMADAS", "camadas_bot.py"), ("b_modelos", "fornecedores_hub", "modelos aprovados", "semear_fornecedores.py"), ("fornecedores_hub", "plataforma", "fornecedores na sua região", "physis-fornecedores.js"),
    ("parceiros_hub", "loja", "profissionais aprovados", "parceiros.py"), ("residuos_hub", "b_mercado", "pontos de coleta (Overpass)", "residuos_gis.buscar_overpass"),
    ("mv", "b_financeiro", "lançamentos (mv_lanc)", "mv_financeiro"), ("pastas", "b_financeiro", "NF-e (XML)", "PHYSIS_NOTAS"), ("b_financeiro", "mv", "alertas e rascunho ao contador", "mv_pedido_bot"),
    ("mv", "b_vencimentos", "tarefas, editais, documentos", "mv_financeiro.bot_vencimentos"), ("pastas", "b_vencimentos", "vencimentos.csv (fiscal, contratos, ACTs)", "mv_financeiro"),
    ("b_vencimentos", "mv", "alertas, .ics e rascunhos ao advogado/contador", "mv_pedido_bot"),
    ("pastas", "b_fatos", "documentos e fatos.json", "mv_fatos.checar"), ("b_fatos", "b_kit", "valores oficiais para as versões zero", "mv_fatos.valor"),
    ("b_fatos", "mv", "inconsistências e perguntas", "mv_alerta"),
    ("mv", "b_desenv", "tarefas e aprovações por módulo", "mv_desenvolvimento.dados"), ("b_desenv", "modelagem3d_mod", "painel Desenvolvimento", "desenvolvimento-dados.js"),
    ("b_desenv", "planejador", "painel Desenvolvimento", "desenvolvimento-dados.js"), ("b_desenv", "gestao", "painel Desenvolvimento", "desenvolvimento-dados.js"),
    ("b_sincro", "instituto_plat", "módulos compartilhados (testados)", "mv_sincronizacao.rodar"), ("b_sincro", "plataforma", "módulos compartilhados (testados)", "mv_sincronizacao.rodar"),
    ("b_sincro", "mv", "alertas e aprovações de clientes", "mv_sincronizacao"), ("modelagem3d_mod", "physis3d", "modelos e impressão", "modulos/modelagem3d"),
    ("marketing_repo", "b_repos", "estado do Git e inventário", "mv_repositorios.estado"), ("b_repos", "mv", "alertas (sem commit, sem cópia)", "mv_alerta"),
    ("marketing_repo", "b_documentos", "plano e documentos", "mv_bots._repos"), ("marketing_repo", "ia_physis", "textos do marketing", "ia_physis.fontes_padrao"),
    ("marketing_repo", "r_marketing", "temas, métricas e plano", "Fase 2 do marketing"), ("marketing_repo", "gestao", "logos e materiais", "Gestão → Marketing"),
    ("mv", "b_kit", "documentos, metas, marcos, editais", "mv_kit.situacao_kit"), ("b_kit", "pastas", "versões zero (ODT)", "mv_kit.versao_zero"),
    ("mv", "b_melhoria", "aprovações e descartes", "mv_kit.bot_melhoria"), ("b_melhoria", "mv", "bot a calibrar", "mv_alerta"),
    ("b_semanal", "mv", "relatório semanal (junta, não recalcula)", "mv_kit.bot_semanal"), ("mv", "b_semanal", "execuções e alertas da semana", "mv_execucao"),
    ("mqtt", "aprendizado_hub", "leituras", "aprendizado.py"), ("aprendizado_hub", "plataforma", "previsões e anomalias", "aprendizado.py"),
    ("r_marketing", "b_melhoria", "engajamento aprendido", "robos.Marketing"),
]


def _estado_bot(mv, bot: str, agora: float) -> dict:
    from . import mv_vigia
    lim = mv_vigia.LIMITE_H.get(bot, 26)
    ult = mv.db.execute("SELECT fim, erro FROM mv_execucao WHERE bot=? ORDER BY fim DESC, id DESC LIMIT 1", (bot,)).fetchone()
    al = [g for (g,) in mv.db.execute("SELECT gravidade FROM mv_alerta WHERE bot=? AND resolvido IS NULL", (bot,))]
    if not ult:
        return {"estado": "parado", "texto": "nunca rodou", "quando": None, "alertas": len(al)}
    if ult[1]:
        e, t = "erro", ult[1][:120]
    elif (agora - ult[0]) / 3600 > lim:
        e, t = "parado", f"sem rodar há {(agora - ult[0]) / 3600:.1f} h"
    elif "alerta" in al:
        e, t = "alerta", f"{al.count('alerta')} alerta(s)"
    elif "atencao" in al:
        e, t = "atencao", f"{al.count('atencao')} ponto(s) de atenção"
    else:
        e, t = "ok", "tudo certo" if not al else f"{len(al)} configuração(ões) pendente(s)"
    return {"estado": e, "texto": t, "quando": ult[0], "alertas": len(al)}


def estado(mv, agora: float | None = None) -> dict:
    agora = agora or time.time()
    return {"grupos": GRUPOS,
            "nos": [{"id": i, "nome": n, "grupo": g, "descricao": d} for i, n, g, d in NOS],
            "arestas": [{"de": a[0], "para": a[1], "oque": a[2], "fonte": a[3], "opcional": bool(a[4]) if len(a) > 4 else False}
                        for a in ARESTAS],
            "estado": {no: _estado_bot(mv, bot, agora) for no, bot in BOT_DO_NO.items()}}
