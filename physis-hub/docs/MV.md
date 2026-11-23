# Physis M&V (versão de teste)

Gestão de **nível 2** que junta as quatro frentes: Casa Physis, Physis Engineering, Instituto Physis e InovaSTEM, mais a frente
Transversal (jurídico, contábil, lote, marca e o próprio M&V). Cada plataforma continua com a sua Gestão interna. O M&V mede, cruza
prazos e dependências e avisa onde é preciso intervir. Decisões: documento 27 de `Sistema Physis` (D31 a D75).

## Onde está

| Parte | Arquivo |
|---|---|
| Núcleo (banco, CPM, visões, financeiro, alertas) | `physis_hub/mv.py` |
| Bots (atrasos, documentos, resumo) | `physis_hub/mv_bots.py` |
| Semente (metas 2027–2031, marcos, Fase 0 até 31/01/2027) | `physis_hub/mv_semente.py` |
| Servidor local + exportação | `physis_hub/mv_servidor.py` |
| Linha de comando e agenda do Windows | `physis_hub/mv_cli.py` |
| Tela | `web/mv.html` |
| Testes | `tests/test_mv.py` |

O banco é **próprio** (`physis-mv.db`) e fica **fora do OneDrive**, em `C:\physis\dados` ou em `PHYSIS_MV_DADOS`, porque a sincronização
corrompe SQLite. Os resumos diários vão para `Sistema Physis\28_Physis_MV\resumos` (`PHYSIS_MV_SAIDA`).

## Comandos

    cd physis-hub
    python -m physis_hub.mv_cli semear
    python -m physis_hub.mv_cli importar "<...>\Sistema Physis\18_Checklist_para_importar_na_Gestao.json"
    python -m physis_hub.mv_cli bots                # documentos, atrasos e resumo
    python -m physis_hub.mv_cli servir              # http://127.0.0.1:8710/
    python -m physis_hub.mv_cli agenda --criar      # tarefas agendadas do Windows (D58)
    python -m unittest tests.test_mv

## Visões
- **Saúde**: nota de 0 a 100 por frente. Perde, em proporção às tarefas abertas, até 50 pontos por atraso, 30 por bloqueio e 20 por prazo em risco. Mostra também alertas abertos, documentos e a última execução de cada bot.
- **Gantt e caminho crítico** (CPM em dias corridos): o caminho crítico é a sequência mais longa de cada cadeia de dependências com 2 ou mais tarefas. Uma tarefa fica com **prazo em risco** quando as dependências empurram o fim para depois do prazo. Data estimada aparece tracejada, com [CONFERIR].
- **Kanban** com troca de estado. Ao bloquear uma tarefa, a tela pede o motivo e de quem ela depende.
- **Matriz de pendências**: tarefas abertas, atrasadas e bloqueadas por pessoa e por frente.
- **Roadmap 2027–2031**: metas, marcos e quantas tarefas sustentam cada meta. Também mostra quantas tarefas ainda não estão ligadas a nenhuma meta.
- **Alertas e intervenções**, **Documentos** e **Financeiro**. No financeiro, cada entidade aparece separada e nunca somada às outras. O que não foi conferido pelo contador fica "a conferir" (D70).
- **Download** de cada visão em ODS, ODT ou PDF/A. O PDF precisa do LibreOffice (`soffice`); sem ele, o servidor avisa e oferece ODT ou ODS.

## Bots (rodam sozinhos, D56 e D58)
- **atrasos** (de hora em hora), que detecta:
  - tarefa vencida, com a intervenção sugerida (replanejar, resolver o bloqueio, dividir em entregas menores ou reatribuir);
  - tarefa bloqueada;
  - dependência ainda aberta a até 3 dias do início;
  - prazo em risco;
  - ciclo de dependências;
  - tarefa sem responsável;
  - data estimada no caminho crítico;
  - **tarefa que passa do marco da fase** (18/11/2026): toda tarefa aberta cujo projeto começa com "Fase 0" precisa
    terminar até o marco "Fase 0 fechada" (`MARCOS_DE_FASE` em `mv_bots.py`), e toda tarefa com o campo `marco`
    preenchido, até aquele marco. Vale o mais tarde entre o prazo informado e o fim calculado pelas dependências. Pega o
    caso em que a tarefa está dentro do próprio prazo, mas o prazo dela já passa do marco (ex.: CNPJ do Instituto em
    fev/2027 com a Fase 0 fechando em 31/01/2027).
- **documentos** (de hora em hora): varre `Casa Physis`, `Sistema Physis` e `Instituto Physis` (sem as pastas de código, backup e kits) e confere:
  - **idade × validade** por tipo: apresentação 90 dias, contrato 365, planilha 180, memo 30, plano 180, documento 180. A idade vem da data gravada dentro do arquivo, então uma cópia recente de conteúdo antigo continua velha;
  - **regras das decisões**: horizonte 2031 (D40), sede no Brasil (D42), grafia Rafaella (D61), S2 Services é SARL (D66), bônus sobre vendas (D34);
    desde 18/11/2026 também: PDI com "28 projetos" (o atual tem 22, P1–P22), P18 ainda chamado "Maker e e-waste" (agora
    Economia circular) e a secretaria da Global South Alliance na Physis Engineering sem a cláusula de cessão ao Instituto (D67).
    Arquivos que só registram texto antigo (`Trechos_retirados…`) ficam fora das regras;
  - **marcadores** ([MARCADOR], [A PREENCHER], [CONFERIR], "a definir");
  - **falha de template**: autor e data falsos deixados pelo gerador (python-docx ou python-pptx, "Steve Canny", 2013).
  Cada documento com falha vira alerta e uma tarefa "Corrigir…".
- **resumo** (diário, às 7h): Markdown e ODT com a saúde, os alertas que pedem intervenção, o caminho crítico dos próximos 14 dias e os documentos com falha.

Os alertas são idempotentes: o mesmo problema não se repete e é fechado sozinho quando some. Nada sai para fora: e-mails e documentos
continuam passando por aprovação humana (D49).

## Segurança (fase de teste)
Ouve só em `127.0.0.1` e confere o cabeçalho Host. Todo POST exige o cabeçalho `X-Physis-MV: 1`, que uma página de outro site não consegue enviar.
Na migração para o servidor físico (dezembro, Eric), entram as contas e os papéis da Gestão e o HTTPS pelo proxy.

## Versão enxuta (22/11/2026)
Três regras: (1) só roda se alguém usa o resultado (o bot melhoria mede as ações em 4 semanas e sugere reduzir ou desligar);
(2) a frequência acompanha a velocidade da mudança; (3) aprendizado de máquina só onde há dados (começa por regras e guarda cada decisão).

| Frequência | Bots |
|---|---|
| De hora em hora | sinal de vida, documentos (só lê se algum arquivo mudou; leitura completa 1×/dia), dados-iot, vigia, sentinela |
| De 8 em 8 h | atrasos |
| Diário (7h) | resumo, backup, páginas, links, inovação (1 mês, depois decide), editais, simulação, gestões, bancos, acervo, índice da IA, cursos (só com documento novo), financeiro, vencimentos, base de fatos, kit (diário até 26/11, depois às segundas), melhoria, auditoria |
| Semanal (segunda 6h) | revisão semanal: junta o que os outros produziram, não recalcula |
| Sob demanda | mercado/radar por cidade e área (`/mercado`), análise de marketing mensal |
| Adiado até haver dado | visão (câmeras e drones), mapa internacional, trends, verba de impulsionamento, classificador de extrato |

## Bots compartilhados (22/11/2026)
Todos entram na agenda (`mv_cli agenda`): de hora em hora `atrasos documentos dados_iot vigia sentinela sala`; às 7h, todos.
Nenhum limite técnico vem de fábrica (regra 1): sem a variável, o bot mostra a medida e abre um único aviso "info".

| Bot | O que faz | Arquivo | Variáveis |
|---|---|---|---|
| paginas | Checklist base das telas (doc 43): rodapé com a razão social, fontes, paleta, sem azul, barra igual | `mv_paginas.py` | `PHYSIS_RAIZ_INSTITUTO` |
| links | Links externos das telas, 1x por dia | `mv_paginas.py` | — |
| auditoria | Cruza bots, robôs e módulos; caixa de perguntas das pendências; plano de intervenção | `mv_auditoria.py` | — |
| mercado | **Sob demanda** (`/mercado <cidade> [área]`; consulta guardada 6 meses). Ecossistema de parcerias por cidade e área (fabricantes, fornecedores, teste, compra e venda, estágio, laboratórios, hubs, investidores, supermercados, collabs, resíduos); mapa GIS (parcerias.geojson); catálogo de dados abertos. Semanal | `mv_ecossistema.py` | `PHYSIS_MERCADO_ONLINE` |
| financeiro | Assessor contábil: comprovante, projeto, duplicidade, conferência, saldo, fluxo por projeto e porta, NF-e; rascunho ao contador | `mv_financeiro.py` | `PHYSIS_NOTAS` |
| vencimentos | Calendário único (substitui o jurídico e o calendário fiscal): tarefas jurídicas, `vencimentos.csv` (fiscal, contratos, ACTs, certidões, licenças), editais e documentos; `.ics`; rascunhos ao advogado e ao contador | `mv_financeiro.py` | — |
| repositorios | Repositórios fora do sistema (padrão: `Documents\Marketing Physis` no OneDrive, pela mesma raiz `PHYSIS_DOCS`; senão `C:\physis\marketing-physis`): último commit, alterações sem commit, cópia fora do computador, inventário (planos, planilhas, logos); os documentos entram no bot documentos e na IA Physis | `mv_repositorios.py` | `PHYSIS_REPOSITORIOS` |
| fatos | Base de fatos: fonte única (`fatos.json`), checagem de consistência nos documentos, valores nas versões zero; fato vazio vira pergunta | `mv_fatos.py` | — |
| kit | Documentos exigidos por pilar para 26/11; versão zero (ODT) com dados do M&A | `mv_kit.py` | — |
| melhoria | Melhoria contínua: taxa de aprovação de cada bot (Beta-Binomial), filas paradas, tempo de resolução | `mv_kit.py` | — |
| semanal | Revisão semanal completa (todos os bots + relatório), segunda às 6h | `mv_kit.py` | — |
| desenvolvimento | Painel "Desenvolvimento" de cada módulo, gerado das tarefas e aprovações do M&A (`sistema/desenvolvimento-dados.js`) | `mv_desenvolvimento.py` | — |
| sincronizacao | Leva as melhorias dos módulos compartilhados entre Sistema, Instituto e InovaSTEM, com teste antes; commit só local, nunca push; clientes só com dupla aprovação | `mv_sincronizacao.py` | — |
| vigia | Cada bot rodou dentro do prazo e sem erro | `mv_vigia.py` | (prazos da agenda em `LIMITE_H`) |
| sentinela | `verificar.sh/ps1` + `docker compose ps` → alertas | `mv_vigia.py` | — |
| sala | Gera `sala-dos-bots.html` em `PHYSIS_MV_SAIDA` | `mv_sala.py` | — |
| editais | Importa `banco_editais.csv`; prazo perto, vencido, sem responsável | `mv_bots_extra.py` | `PHYSIS_EDITAIS_CSV`, `PHYSIS_EDITAIS_AVISO_DIAS` |
| dados_iot | Idade da última leitura por nó (tabela `leitura` do Hub) | `mv_bots_extra.py` | `PHYSIS_BANCO`, `PHYSIS_IOT_MUDO_H` |
| simulacao | Casos do Gêmeo Virtual em dia; premissas iguais no JS (regra 4) | `mv_bots_extra.py` | — |
| gestoes | Exportações physis/1 das Gestões: idade e se já foram importadas | `mv_bots_extra.py` | `PHYSIS_MV_GESTOES`, `PHYSIS_GESTOES_MAX_H` |
| bancos | integrity_check, pg_isready, validade do HTTPS, segredos no Git (regra 12) | `mv_bots_extra.py` | `PHYSIS_PG_HOST`, `PHYSIS_DOMINIO`, `PHYSIS_CERT_AVISO_DIAS` |
| acervo | Acervo → trilhas do InovaSTEM pelas palavras de `trilhas.json`; vira pedido para aprovação | `mv_bots_extra.py` | `PHYSIS_ACERVO`, `PHYSIS_TRILHAS` |

| ia | Atualiza o índice da IA Physis (só o que mudou) | `ia_physis.py` | `PHYSIS_IA_PASTAS` |
| cursos | Mapa de potenciais cursos por plataforma (Instituto, Physis Engineering, InovaSTEM); rechecagem automática; trilhas a partir de 30/11/2026 | `mv_cursos.py` | `PHYSIS_CURSOS_PASTAS` |

**IA Physis** (`ia_physis.py`, 22/11/2026): IA própria, feita do zero, só para o servidor, o sistema, as plataformas e os apps. Índice
SQLite FTS5 (BM25) dos textos da Physis; resposta **extrativa com fonte**; sem evidência, "Não encontrei isso nos documentos da Physis".
Uso: `mv_cli ia "pergunta"`, `mv_cli ia --indexar` e `GET /api/mv/ia?q=`.

**Aba Monitoramento** (`mv.html`): mapa 3D das integrações (`mv_integracoes.py`, rota `/api/mv/integracoes`), com o anel de estado de cada
bot. O mapa avulso sai do mesmo desenho: `python ferramentas/gerar_mapa_integracoes.py saida.html --banco physis-mv.db`.

IA local opcional (regra 11): `PHYSIS_IA_URL` (vLLM, API compatível com OpenAI) e `PHYSIS_IA_MODELO`. Sem elas, os bots seguem só
por regras. O bot `inovacao` agora também alerta quando uma fonte não responde.

## Ainda não feito (próximas entregas)
- Bots por frente, parceiros e fornecedores com a fila de e-mails. (Editais e acervo → trilhas: feitos em 22/11, ver acima.)
- Leitura direta das Gestões internas em vez da exportação JSON.
- Decidir a IA dos bots de editais e acervo: o código usa só o modelo local opcional (regra 11). A decisão antiga (Claude, teto de US$ 50/mês, D71) não foi implementada, porque contraria a regra 11.
