# Mapeamento do ecossistema Physis: bots, parcerias, finanças, documentos, modelagem e melhoria contínua
Versão de 22/11/2026. Responde ao pedido de 22/11 (bots de mercado e parcerias com GIS, resíduos, dados abertos, abas por modalidade,
câmeras com IA e drones, aprendizado de máquina por pilar, assessoria contábil e jurídica, documentos por pilar para 26/11, revisão semanal,
marketing) e diz, para cada função, **o que já existia, o que foi ampliado, separado ou criado, e o que falta**. Regra 1 valendo:
nada de dado inventado; o que falta é [MARCADOR] ou pergunta na caixa (M&A → Aprovações → Perguntas).

## Versão enxuta aplicada (22/11/2026, depois da revisão)
| Mudança | Antes | Agora |
|---|---|---|
| documentos | lia tudo de hora em hora | confere a assinatura das pastas de hora em hora; lê só se mudou (e 1×/dia) |
| atrasos | de hora em hora | de 8 em 8 h |
| jurídico | bot próprio | **vencimentos**: jurídico + fiscal + contratos + ACTs + certidões + editais + documentos, calendário .ics |
| revisão semanal | rodava todos os bots de novo | só junta o que já foi produzido |
| kit 26/11 | diário | diário até 26/11, depois às segundas |
| mercado | semanal (todas as cidades) | **sob demanda** (/mercado cidade área), guardado 6 meses |
| cursos | diário | só quando a IA acha documento novo |
| melhoria | taxa de aprovação | + **uso real em 4 semanas** (sugere reduzir/desligar) e regra da inovação (menos de 5 % em 30 dias → semanal) |
| novo | — | **base de fatos** (fonte única + consistência + versões zero) |
Sobre a IA externa (Claude, US$ 50/mês só para redigir): contraria a regra 11 do CLAUDE.md; fica como pergunta na caixa. Nada foi ligado.

## 0. Pedido "api updates" e ciclo de 22/11
- O texto do pedido feito ao "api updates" **não foi encontrado** (repositório, branches, ZIP do ciclo). É preciso reenviá-lo para cruzar.
- A branch `ciclo/2026-11-22` (ZIP "arquivos-para-enviar") foi **incorporada**: avisos da eólica (`vento.py`, `physis-turbinas.js`, teste novo),
  ajuste do estresse e a versão deles do teste da simulação (com tolerância, igual à minha). As correções de `test_odf` e `test_carbono_espelho`
  eram idênticas às minhas.

## 1. Arquitetura: como dividir para ser barato, eficiente e com melhoria contínua
| Camada | O que faz | Quando roda | Custo |
|---|---|---|---|
| **Physis Hub** (servidor :8700) | Atende clientes e equipe na hora: loja, plataforma, Gestão, 6 robôs (suporte, preços, editais, marketing, projetos, pluviômetro), aprendizado (chuva, anomalias, consumo, irrigação), indicadores, fornecedores, parceiros, resíduos | Sempre ligado | Só o servidor |
| **Physis M&A** (:8710) | Gestão nível 2 e **25 bots agendados** (abaixo) | Hora em hora, 7h e semanal | Um computador |
| **IA Physis** | Motor comum: índice dos textos da Physis, resposta com fonte, temas | Índice 1×/dia | Zero (biblioteca padrão + SQLite) |
| **Modelo aberto local (opcional)** | Só reescreve, mantendo fontes | Sob demanda | GPU própria quando houver |

Princípios: (1) um bot por **decisão humana diferente** (quem aprova é quem define a fronteira); (2) bots da mesma família dividem
utilitários (rascunho de e-mail, caixa de perguntas, alertas idempotentes); (3) nada pago nem de terceiros (regra 11); (4) toda
sugestão passa pela fila e **a decisão humana treina o bot** (bot melhoria).

### Famílias de bots do M&A (25)
| Família | Bots | Decide |
|---|---|---|
| Gestão e prazos | atrasos, resumo, gestoes, documentos | Direção |
| Instituto, InovaSTEM e cursos | editais, acervo, cursos, inovacao | Instituto / InovaSTEM |
| Mercado e parcerias | **mercado** (novo) | Direção + equipe |
| Assessoria | **financeiro**, **juridico** (novos), **kit** (novo) | Contador, advogado, direção |
| Modelagem e campo | simulacao, dados_iot | Engenharia |
| Plataforma | paginas, links | Design/sistema |
| IA | ia | Engenharia |
| Governança | vigia, sentinela, auditoria, **melhoria** (novo), **semanal** (novo), backup, bancos, sala | Engenharia |

## 2. Função pedida × o que existe × decisão
| Pedido | Já existia | Decisão | Feito agora | Falta |
|---|---|---|---|---|
| Pesquisa de mercado, fabricantes, parceiros, investidores (peças, IoT, hardware, teste, compra e venda, estágio, bancadas…) | `fornecedores.py` (só solar, com curadoria), `parceiros.py` (instaladores) | **Novo bot mercado** + ampliar fornecedores na fase 2 | 12 tipos de parceria × 9 áreas; candidatos do OpenStreetMap sempre "a conferir"; planilha `parcerias.csv` para o que só pesquisa humana acha (fabricantes, investidores, collabs, testes); pedidos por cidade × tipo; estados a_conferir → conferido → contatado → parceiro | Levar os conferidos para o cadastro oficial do Hub (`fornecedores.py`) nas áreas além do solar; telas de pipeline na Gestão |
| Mapa GIS por cidade (depois Brasil e exterior) | Mapa de fornecedores (solar) e de resíduos no Hub | **Ampliar** | `parcerias.geojson` (lê no Mapeamento/QGIS); cidades atuais: Petrópolis/RJ e Itirapuã/SP; `cidades.json` para acrescentar | Camada no Mapeamento do Hub; cidade da Fazenda MF (caixa) |
| Troca de resíduos, pontos de coleta, lixeiras Physis | `residuos_gis.py` (destinos pelo OSM) | **Ampliar** | Tipo "residuos" e "supermercado" no mapa (lugares de grande circulação para lixeiras) | Regra de sugestão de lixeira depende de raio definido pela equipe (caixa) |
| Bases de dados abertas | Fontes soltas em cada módulo | **Novo catálogo** | 18 bases (OSM, IBGE, CNPJ, ANEEL, INMETRO, CEC, e-MEC, CNPq DGP, Lattes, SINIR, CVM, dados.gov.br, NASA POWER, INMET, CEMADEN, ANA, MapBiomas, FINEP) com teste semanal de acesso | Importadores específicos (CNPJ por CNAE, ANEEL por município, e-MEC por cidade) |
| Abas por modalidade (solar: equipamentos e fornecedores; AVAC: fabricantes e mapa; supermercados, laboratórios, hubs, estágio) | Base de equipamentos (203 classes, importadores INMETRO/CEC), vista "fornecedores na sua região" (solar) | **Ampliar** | Matriz área → tipos de parceria (`AREAS` em mv_ecossistema.py) que define o que cada aba deve mostrar | Vista "fornecedores/parceiros na sua região" nas abas AVAC, IoT, água, turbinas, SbN, circular (fase 2 do fornecedores.py) |
| Assessoria contábil e modelagem financeira | Financeiro por entidade, conferência do contador (D70) | **Novo bot financeiro** | Comprovante, projeto, duplicidade, conferência (limite na caixa), saldo do mês, fluxo por projeto e por porta, NF-e (XML) × lançamentos, rascunho ao contador | Tipos de lançamento para loja/rede/patrocínio/investimento/imposto (caixa); impostos calculados pelo contador, não pelo bot |
| Assessoria jurídica | Tarefas J1–J8 no M&A | **Novo bot juridico** | Tarefas vencidas, documentos de contrato/ACT/termo com marcador, decisões abertas; rascunho ao advogado | Prazos de vigência de contratos assinados (precisa do cadastro de contratos) |
| E-mails para esclarecer | Fila de e-mails da Gestão (rascunho) | **Reaproveitar** | Rascunhos na fila do M&A, nunca enviados sozinhos | Envio real pelo SMTP do Hub depois de aprovado |
| Documentos por pilar, templates, versão zero para 26/11 | Documentos automáticos (modelos, aprovação), bot documentos (validade, regras) | **Novo bot kit** | 6 pilares × tipos exigidos (visão/missão/cronograma, apresentação, pitch, concept note, proposta de edital e de parceria, contrato, ACT, investidores, planilha, artigos); versão zero ODT com metas, marcos, tarefas e editais reais | O conteúdo de cada documento (equipe); templates visuais por pilar (arquivos de modelo da identidade) |
| Revisão semanal rigorosa | Bots diários | **Novo bot semanal** | Roda tudo + auditoria + kit + mercado e escreve o relatório da semana | — |
| Marketing (trends, impacto, impulsionamento, foco, orgânico, collabs) | Robô Marketing (aprende engajamento por tema), abas Marketing da Gestão | **Ampliar** (Hub) | Tipo "collab" no mapa de parcerias | Importar métricas das redes (exportação CSV; API das redes só como opção); ranking de temas por objetivo; calendário a partir dos marcos do M&A |
| Câmeras com IA e drones | — | **Roadmap** (seção 4) | Pergunta na caixa: em qual projeto começar | Tudo da seção 4 |
| ML e melhoria contínua por pilar | Aprendizado do Hub, indicadores, robô marketing, IA Physis | **Novo bot melhoria** + matriz (seção 3) | Taxa de aprovação por bot, filas paradas, tempo de resolução | Modelos por pilar da seção 3 |

## 3. Aprendizado de máquina e melhoria contínua por pilar
| Pilar | Tem hoje | Melhoria contínua | Falta (próximo) |
|---|---|---|---|
| Plataforma / monitoramento | chuva, anomalias, consumo, irrigação (`aprendizado.py`), indicadores com retorno da equipe | Retreino diário; "aviso real ou falso" ensina | Anomalia por imagem (câmeras) |
| Gêmeo virtual / modelagem | Simulação física (determinística), paridade JS×Python | Bot simulação | Calibração com medição (erro modelo × sensor) |
| Instituto / editais | Robô editais (semelhança), bot editais (prazos) | Aprovado/reprovado alimenta a semelhança | Ligar o resultado das propostas ao ranking |
| InovaSTEM / cursos | Bot cursos (temas), acervo (trilhas) | Aprovação dos temas | Conclusão de alunos por trilha |
| Marketing | Robô Marketing (Beta-Binomial) | Métricas por tema | Métricas reais das redes |
| Financeiro | Regras do bot financeiro | Decisões do contador | Previsão de caixa por projeto (depois de 3+ meses de lançamentos) |
| Mercado e parcerias | Bot mercado | Aprovação por tipo (bot melhoria) | Priorizar tipos com mais aprovação |
| Gestão (M&A) | CPM, saúde, alertas | Bot melhoria, auditoria | Prever atraso por histórico de tarefas |

## 4. Câmeras com IA e imagens de drone: roadmap
| Fase | O que | Ferramentas abertas | Onde entra no sistema |
|---|---|---|---|
| 0 · Base | Escolher o projeto piloto (caixa), inventário de câmeras e drone, LGPD (aviso, finalidade, retenção) | — | Documentos (jurídico), M&A |
| 1 · Drone | Voo do lote → ortomosaico e modelo de elevação | OpenDroneMap/WebODM, QGIS | Mapeamento (camada), Simulação/terreno (relevo), BIM |
| 2 · Análise | Índices de vegetação (SbN, agro), termografia (painéis solares, AVAC) | QGIS, OpenCV | SbN, Solar, AVAC |
| 3 · Câmeras | Câmeras IP (RTSP/ONVIF) com detecção local de eventos | Frigate (NVR aberto), OpenCV; modelos com licença compatível | SCADA, alertas, monitoramento integrado |
| 4 · Aprender | Equipe confirma eventos → retreino; comparação imagem × sensor | Rotulagem local | aprendizado.py, bot melhoria |
Ponto de partida sugerido: o projeto que já tem lote, mapa e BIM (Casa Physis, Lote 168), mas a escolha está na caixa de perguntas.
Atenção à licença dos modelos de detecção (algumas são AGPL): conferir antes de embutir.

## 5. Kit de 26/11
O bot kit confere, por pilar, os documentos exigidos e gera a versão zero do que falta (`kit-26-11/versao-zero/<pilar>/<tipo>.odt`).
**Limite honesto:** a versão zero traz estrutura + dados reais do M&A; o texto (proposta de valor, números de mercado, valores de
contrato) é da equipe. Nada é enviado sem revisão e aprovação.

## 6. O que ainda falta para o modelo ser totalmente integrado
1. **Hub ↔ M&A por API local:** editais coletados pelo Hub, métricas de marketing da Gestão e fornecedores curados entrando no M&A sem exportação manual.
2. **Envio real dos e-mails aprovados** pelo SMTP do Hub (hoje: rascunho).
3. **Servidor físico** com Hub + M&A + backup (pergunta na caixa: quem instala, Windows ou Linux).
4. **Cadastro de contratos** com vigência e partes (para o jurídico alertar vencimentos).
5. **Pipeline de parceiros e investidores** na Gestão (estados já existem no mercado).
6. **Estoque de peças IoT e bancadas** (o que tem, onde, quem testa).
7. **Painéis de indicadores (Superset)** dos KPIs por pilar.
8. **Registro LGPD por bot** (que dado lê, para quê, por quanto tempo).
9. **Tradução EN dos documentos** do kit (InovaSTEM e GSA).
10. **Login único** entre Hub e M&A quando o M&A sair do modo teste.
