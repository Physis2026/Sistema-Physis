# Regressão de pedidos · situação em 24/11/2026

Legenda: **feito e testado** (teste automático ou no navegador) · **feito, sem teste no PC da Physis** · **parcial** · **falta** ·
**depende da dona / provedor**. Testes do Sistema neste ambiente: 1.504 OK (13 pulados, sem Edge). Nada aqui foi conferido no
computador da Physis depois do pacote sistema-24-11i, a não ser quando dito.

## Infra, IA e bots

| Pedido | Situação | Onde |
|---|---|---|
| Sistema sem Claude; bots autônomos respondem | feito e testado | M&A › Bots e comandos (mv_autonomo) |
| IA Physis generativa própria (modelo aberto local) | feito e testado (no PC da Physis: modo generativa OK) | ia_generativa, Ollama qwen2.5:7b |
| Respostas sem travar o M&A | feito e testado | trechos na hora + modelo em segundo plano |
| M&A ou site caído volta sozinho | feito e testado (sentinela de hora em hora religa pela agenda) | mv_vigia.religar_servicos |
| Atualização final com backup em zip | feito e testado (PC da Physis, sem --backup ainda) | ferramentas/atualizacao_final.py |
| Teste zero sem estourar o tempo | feito, sem teste no PC da Physis | --sem-testes |
| Marketing sem APIs | feito e testado (PC da Physis) | publicar_aprovados.csv, métricas da Gestão |
| E-mail real dos sistemas | depende da dona (senha de app do Microsoft 365) | setx PHYSIS_SMTP_* |
| Rede pública | depende do provedor (IP fixo) ou de uma VPS | Caddyfile, DNS |
| Caddy e Marketing Lembretes falhando na agenda | falta decisão (desativar Caddy até a rede pública?) | agenda do Windows |
| Regressão antiga (\PhysisRegressao) testa qual pasta | falta confirmar | tarefa regressao_hora |

## Visual, páginas e documentos

| Pedido | Situação | Onde |
|---|---|---|
| Novo visual (guia de identidade) | feito e testado | telas do Sistema |
| Edição manual de textos e ordem dos blocos | feito e testado (navegador) | botão "Editar página" (direção grava) |
| Lista de modificações e aprovações no M&A | feito | LISTA-DE-MODIFICACOES.md, grupo "Final 24/11" |
| CHECKLIST e ROADMAP atualizados | parcial (esta regressão substitui a parte de 24/11) | docs/ |
| Missão e visão oficiais | depende da dona (a IA citou um documento TESTE) | doc 37/41/48 |
| Documentos do kit (11 faltam, 7 a revisar), 58 com falha, 11 rascunhos, 15 "Executar" | depende da equipe | teste zero |

## InovaSTEM

| Pedido | Situação | Onde |
|---|---|---|
| Uma aba de Impressão 3D (filamentos, fatiamento, fila) | feito e testado | /laboratorio |
| Simulação por área com previsão da modelagem | feito e testado | /laboratorio#simulacao |
| Sem base de construção na InovaSTEM | feito e testado | bot público sem net zero/AVAC/dutos; sem "Terreno e água" |
| Sem abas e títulos repetidos | feito e testado (inclui Delas) | instituto-delas-24-11.patch |

## Modelagem, BIM e simulação

| Pedido | Situação | Onde |
|---|---|---|
| Análises por objeto (calha → CFD, peça longa → flambagem) e perguntas | feito e testado (flambagem conferida no CalculiX) | physis-modelador |
| Catálogo só de programas abertos (sem ORCA), com links | feito; links [CONFERIR] | ferramentas_simulacao, guia do Acer |
| BIM e instalações, BMS, solar, quadros (todas as normas) | feito (catálogo e guia) | guia do Acer |
| IFC/PDF da arquitetura → áreas e cálculo automáticos | feito e testado (IFC da Casa Physis: 31 edificações) | Estermic › BIM e GIS |
| Rascunho torto à mão/foto → planta reta, DXF, IFC e cálculo | feito e testado (IFC aberto no IfcOpenShell) | Estermic › BIM e GIS |
| Nomes dos ambientes lidos na imagem (OCR) | feito e testado com Tesseract; no PC da Physis falta instalar o Tesseract | /api/estermic/ocr |
| DWG | não (formato fechado): sai DXF | — |
| Modelagens térmica, solar, mecânica e fluidos no AVAC/Estermic | parcial: aba "Modelagens e simulações" com o pacote de dados para EnergyPlus, SAM/pvlib, OpenFOAM, EPANET e CalculiX; a simulação roda nesses programas (Acer) | AVAC › Modelagens |
| Renderizador da Casa Physis a partir da planta | falta (o IFC gerado já abre no fluxo do 3D; render automático é a próxima etapa) | — |
| Rede de água urbana (OSM, TOPODATA, IBGE, SNIS → EPANET) | feito e testado (simulação EPANET rodada) | ferramentas/rede_agua.py |
| Camadas com serviço público (IBGE, OSM) | feito; testado só com respostas simuladas | ferramentas/baixar_camadas.py |
| Demais camadas (relevo, hidrografia, MapBiomas…) | depende de download manual (guia) | guia do Acer, seção 8 |

## AVAC, Estermic e Planejador

| Pedido | Situação | Onde |
|---|---|---|
| Estermic como sistema à parte (porta 8704), aprovado no M&A | feito e testado; aprovação esperando a dona | physis_hub/estermic_servidor.py |
| BIM antes do cálculo na Estermic | feito | abas |
| Água gelada, termoacumulação, torre | feito e testado | AVAC › Água gelada |
| Pressão do circuito e NPSH (água gelada e solar) | feito e testado (propriedades da água conferidas) | AVAC › Água gelada / Aquecimento solar |
| Dutos por exaustão e ar exterior; churrasqueira na exaustão | feito e testado | AVAC › Ventilação, Dutos |
| Sauna separada; piscina privada/coletiva/borda infinita | feito e testado | AVAC |
| Tubulações fria/quente/gelada e fiação no quadro | feito e testado | AVAC › Tubulações, Quadro |
| Garagem com vazão mínima e máxima | feito | AVAC › Ventilação |
| Aquecedor de passagem e a gás | feito | AVAC › Aquecimento solar |
| Seleção de modelos e fabricantes; blocos IFC | feito (base genérica e fabricantes por segmento; modelo exato [MARCADOR] até a cotação) | Estermic › Equipamentos |
| Fornecedores além de solar (AVAC, elétrica, hidráulica…) | falta decisão da dona (perguntas de 24/11) | Gestão › Fornecedores |
| Dados antigos da Estermic (versão arquivo) | falta saber se existem | — |
| Sprinklers no Planejador | feito e testado | Planejador › Módulos |
| Planejador completo na Casa, sem licença | feito e testado | Casa › Planejador |
| Gêmeo digital (zonas, elementos, camadas) | feito e testado (estático) | Planejador › Gêmeo digital |
| Gêmeo: camada simulada (G4) | feito e testado (versão inicial: água de chuva dos telhados e geração solar mês a mês) | Planejador › Gêmeo digital |
| Gêmeo: camada medida (G6) | falta (depende de sensores) | doc 47 |

## Acer (Linux)

| Pedido | Situação |
|---|---|
| Guia de programas e camadas | feito (links [CONFERIR]) |
| Instalação no Acer | depende do Acer (após 1 mês no Windows) |
