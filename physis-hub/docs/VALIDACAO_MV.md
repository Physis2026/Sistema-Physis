# Validação · planejado × gerado (M&V)

**Em desenvolvimento** (versão 0.2, 18/11/2026; responsáveis: Erick Lopes, Arthur e Rafael). É o **produto 3 do SustainKit**: conferir o que foi planejado com o que
está sendo realmente gerado e consumido. Aparece só na Casa Physis (instalação de pesquisa), marcada "Em desenvolvimento",
e fica fora da loja pública, como a Frota.

> Não confundir com `physis_hub/mv*.py`: aquilo é a gestão interna de M&V das quatro entidades da Physis. Este módulo
> se chama `validacao`.

## Para que serve

Toda instalação nasce de um plano: a usina solar vai gerar tanto por mês, a casa vai gastar tanta água, a turbina vai
dar tanta energia, o caminhão vai fazer tantos litros a cada 100 km. Depois de instalado, o hub mede tudo. A Validação
põe os dois lado a lado, mês a mês, e responde quatro perguntas:

| Pergunta | O que a aba mostra |
|---|---|
| **Quanto?** | O desvio: medido − planejado, na unidade do módulo e em %. |
| **Quando?** | O primeiro mês em que o desvio passou do limite e quantos meses seguidos durou. |
| **Como?** | O equipamento e a variável que mais pesaram no desvio do mês. |
| **Por quê?** | A causa provável, com a evidência e uma confiança de 0 a 1. "Causa não identificada" é uma resposta aceita. |

## De onde vem cada número

**Planejado.** Nunca é inventado. Ou a equipe grava (parte *Planejado* da aba), sempre com a **fonte**, ou ele vem
sozinho de outro módulo:

| Módulo | Planejado | Medido |
|---|---|---|
| Energia solar | Dimensionamento da aba Energia solar (botão "Trazer da aba Energia solar": a geração do ano repartida pela irradiação de cada mês) | Medidor da usina no hub (`energia`, kW → kWh) |
| Água | Projeto, Planejador ou premissa de consumo por pessoa | Hidrômetro no hub (`vazao`, m³/h → m³) |
| Energia e AVAC | Projeto, AVAC ou Planejador | Medidor de energia no hub |
| Turbinas | Aba Turbinas (botão "Trazer da aba Turbinas": a energia do ano repartida pelos dias do mês) | Medidor da turbina no hub |
| Frota | Consumo esperado de cada veículo (cadastro da Frota) × km (ou horas) medidos | Abastecimentos do mês (ou a vazão) |
| Carbono | Planejado de Energia × fator da rede + planejado da Frota × fatores de combustão, os mesmos do Carbono | O mesmo, com o medido |

Módulo sem plano diz **"Sem plano"** e explica o que falta gravar.

**Medido.** As leituras que o hub já guarda (linha V6, MQTT, importações): a média de cada dia × 24 h, somada no mês. É
a mesma regra do aprendizado de consumo. Ao lado de cada mês aparece quantos dias tiveram leitura.

**Clima.** A estação da Resiliência e o pluviômetro: irradiância medida (kWh/m²·dia), chuva do mês (mm) e graus-dia de
resfriamento calculados das temperaturas do ar. O plano pode trazer o clima que ele supôs (por exemplo, a irradiação do
dimensionamento solar), e aí a aba compara um com o outro.

## As regras do "por quê"

Cada regra só aparece se a evidência existir. A de confiança mais alta fica em cima.

| Causa | Quando aparece | Evidência mostrada |
|---|---|---|
| Equipamento desligado ou falha de dado | Menos dias com leitura que o mínimo (`validacao.cobertura_min_pct`) | Dias com leitura / dias do mês |
| Clima diferente do esperado | O clima medido ficou longe do esperado (`validacao.clima_min_pct`) **no mesmo sentido** do desvio (menos sol, menos geração; mais calor, mais consumo) | Medido, esperado, diferença |
| Consumo fora do normal aprendido | A razão medido ÷ planejado do mês passou do normal dos meses anteriores: o mesmo z robusto da Frota (`validacao.anomalia_z`) | Razão, mediana, meses, z |
| Efeito sazonal | O plano é igual todo mês (ano ÷ 12) e o medido do mês está longe da média do período, no sentido do desvio | Média medida, medido do mês |
| Premissa do projeto diverge do medido | Vários meses seguidos (`validacao.premissa_meses_min`) no mesmo sentido, com pouca variação (`validacao.premissa_variacao_max_pct`), e o período todo puxado para esse lado | Meses, desvio médio, variação, premissa citada no plano |
| Causa não identificada | Nenhuma regra acima casou | Pede conferência em campo |

A confiança é uma escala própria (alta ≥ 0,7; média ≥ 0,45; baixa abaixo), **não** uma probabilidade calibrada.

## Linha de base (no estilo do IPMVP)

O consumo esperado aprende com os dados do próprio lugar: uma **regressão linear simples** (só biblioteca padrão do
Python, a mesma reta do aprendizado) do consumo de cada mês do **período de base** contra a variável que move o consumo:

- graus-dia de resfriamento (energia e AVAC; base em `validacao.grau_dia_base_c`);
- irradiação (solar);
- produção ou ocupação (lançada na Gestão do cliente).

A aba mostra a reta (y = a·x + b), o r², o CV(RMSE) e quantos meses entraram. Base curta (`validacao.baseline_meses_min`)
ou CV(RMSE) alto (`validacao.baseline_cvrmse_max_pct`) viram aviso.

No **período de relatório**, o **ajuste rotineiro** é o consumo que a linha de base daria nas condições do relatório
menos o consumo medido na base. A economia sai da **mesma equação** da aba Certificações (nível 4, Medição e
verificação): economia = (linha de base − período de relatório) ± ajustes. A conta existe uma vez só na tela
(`VALIDACAO.ipmvp`, que o `mvEconomia()` das Certificações chama) e tem espelho no servidor
(`validacao.ipmvp_economia`); o teste confere que as duas dão o mesmo resultado. O IPMVP é citado só pelo nome; nenhum
texto dele foi copiado.

## Limites (premissas, todas "conferir")

| Premissa | Padrão | O que faz |
|---|---|---|
| `validacao.desvio_limite_pct` | 10 % | Desvio que conta como fora do plano |
| `validacao.cobertura_min_pct` | 90 % | Dias com leitura para o mês valer |
| `validacao.clima_min_pct` | 10 % | Diferença do clima que explica o desvio |
| `validacao.premissa_meses_min` | 3 meses | Meses seguidos para apontar premissa |
| `validacao.premissa_variacao_max_pct` | 15 % | Variação máxima da razão nesses meses |
| `validacao.plano_plano_max_pct` | 2 % | Plano "igual todo mês" |
| `validacao.anomalia_z` | 3,5 | z robusto do consumo fora do normal |
| `validacao.anomalia_amostra_min` | 6 meses | Histórico antes de dizer o normal |
| `validacao.grau_dia_base_c` | 18,3 °C | Base dos graus-dia |
| `validacao.baseline_meses_min` | 12 meses | Tamanho recomendado da base |
| `validacao.baseline_cvrmse_max_pct` | 15 % | CV(RMSE) máximo da base |

Os valores vêm de `sistema/physis-premissas.json`; o que for proposta da Physis está marcado [CONFERIR] na fonte.

## Relatório

Na parte *Resumo*, "Baixar o relatório (ODT)" gera o documento aberto pelo `PhysisODF` (o mesmo gerador da
plataforma). "Baixar o relatório (PDF/A)" passa pelo computador central (LibreOffice); sem ele, a aba avisa e o ODT pode
ser exportado para PDF/A no LibreOffice. O relatório leva a tabela de cada módulo, os meses fora do limite com o como e o
por quê, a linha de base e o método. Na demonstração sai marcado SIMULADO.

## Demonstração e simulador

Sem o computador central (ou sem nenhum plano gravado), a aba mostra a **Casa Physis SIMULADA**, com 24 meses: um mês
nublado na solar (causa: clima), um mês com a turbina desligada (causa: falha de dado), um mês de calor e uma ocupação
acima da premissa na energia (clima, consumo fora do normal e premissa), a água com estação (efeito sazonal) e o caminhão
gastando demais num mês (consumo fora do normal). Os números simulados nunca vão para o Carbono, a Gestão nem um relatório
de verdade.

No hub de teste, `ferramentas/simulador_dispositivos.py --usuario …` grava dois planejados SIMULADOS (medidores 84 e 85),
tirados do próprio modelo do simulador sem as anomalias: as anomalias e os dias sem leitura aparecem como desvio.
`--limpar` apaga esses planejados.

## Onde está

| O quê | Arquivo |
|---|---|
| Contas, regras, banco e rotas | `physis-hub/physis_hub/validacao.py` |
| Aba (tela, demonstração, relatório, inglês) | `sistema/physis-validacao.js` (embutido no painel por `ferramentas/embutir_bases.py`) |
| Testes | `physis-hub/tests/test_validacao.py` |
| Metodologia | `sistema/physis-metodologia.json`, módulo `validacao` |
| Mapa de variáveis | `sistema/physis-variaveis.json` (`validacao.*`) |

Rotas:

    GET  /api/validacao/estado?meses=12&ultimo=AAAA-MM        cliente ou mais
    GET  /api/validacao/baseline?plano=&var=graus_dia|irradiancia|producao&base_ini=&base_fim=&rel_ini=&rel_fim=
    POST /api/validacao/plano            {modulo, item, nome, ativo, grandeza, fonte, meses, clima?, premissa?}   equipe
    POST /api/validacao/plano/remover    {id}                                                                    equipe

## Responsáveis

Erick Lopes, Arthur e Rafael (decisão de 18/11/2026). Kit de revisão `validacao` em `ferramentas/kits/modulos.json` e quatro
tarefas na Gestão (premissas e limites; medidores e calibração; plano de M&V da Casa Physis; teste de campo com dados de
intervalo reais).

## M&V 2.0: o núcleo

Desde 18/11/2026 o M&V contínuo é o centro do módulo. Métodos citados só pelo nome (IPMVP, ISO 50015, ISO 50006, ASHRAE
Guideline 14, CalTRACK, NMEC Rulebook); nenhum texto deles foi copiado. Tudo é biblioteca padrão do Python e funciona sem
internet. Código: `physis_hub/validacao_nucleo.py` (núcleo), `physis_hub/validacao_modelos.py` (modelos, métricas, limpeza).

| Parte | Como funciona |
|---|---|
| Dados de intervalo | A fonte principal são as leituras do hub (15 min quando o aparelho dá; hora ou dia senão). A fatura e o digitado só conferem ("Conferência com a fatura"). |
| Limpeza | Marca carimbo de tempo inválido, repetido, no futuro ou fora de ordem, salto isolado, sensor travado e valor negativo ou impossível. O original fica ao lado com a marca; a tabela `medicao` nunca muda. |
| Faltantes | Política do plano: excluir o período, preencher por interpolação linear ou pelo modelo. A aba mostra a política e a taxa de faltantes de cada mês. |
| Clima | Temperatura do ar da estação da Resiliência; sem estação, a previsão/observação da fonte aberta que o hub já guarda (Open-Meteo, em `clima_fonte`, com cache no servidor). Nenhuma chamada externa nova. |
| Modelos | Ponto de mudança 2P, 3P, 4P e 5P no dia, modelo horário (hora do dia + temperatura) e k-NN com dados bastantes. Escolha por validação cruzada em blocos seguidos. Ajuste mínimo: R² acima de `validacao.aceite_r2_min` OU CV(RMSE) abaixo de `validacao.aceite_cvrmse_ou_max_pct`. Valores-p e análise dos resíduos (Durbin-Watson, autocorrelação, assimetria, curtose). |
| Versões | Cada modelo guarda parâmetros e hash (tabela `validacao_modelo`); refaz a cada ciclo e só cria versão nova quando dados ou parâmetros mudam. |
| Pacote de auditoria | "Exportar pacote de auditoria": dados brutos, marcas da limpeza, política, temperaturas, modelo e parâmetros, conta e hashes. `validacao_nucleo.conferir_pacote` refaz a conta e chega ao mesmo número. |
| Deriva | CUSUM nos resíduos (deriva do modelo) e por medidor (deriva do sensor: contra a fatura, quando há; senão contra a carga de base do período de base). |
| Incerteza | Monte Carlo com semente fixa (exatidão do medidor, erro do modelo, dias preenchidos): economia com IC de `validacao.mc_confianca_pct` e a parte de cada fonte. A incerteza fracional continua ao lado. |
| Eventos não rotineiros | Degrau sustentado que o modelo não explica; classe provável (equipamento novo, ocupação, horário) pelo perfil horário dos resíduos; impacto e ajuste proposto. O ajuste só entra depois da aprovação de uma pessoa, e a decisão vai para o registro encadeado. |
| FDD | Alarme só quando o medido sai do intervalo de previsão (por `validacao.fdd_dias_min` dias), com causa provável e ação sugerida, ordenado pelo R$ em risco (tarifa digitada no plano, com a fonte: a base ainda não tem tarifa R$/kWh). Projeção por persistência e "risco de não atingir a meta". |
| Ciclo fechado | "Criar tarefa na Gestão" (chave `gestao-physis:validacao-tarefas`, com a evidência). Modo automático no plano, desligado de fábrica. |
| Resultado verificável | "Registrar resultado verificado": período, economia, IC, hash do modelo e dos dados viram um registro SHA-256 que entra no lote diário de integridade. Terceiros conferem sem ver os dados brutos. A Physis garante dados e hashes; blockchain, tokens e custódia são do parceiro. Prova de conhecimento zero e pagamento por contrato inteligente: Fase 2 com o parceiro; a interface é o resumo do resultado no lote (`integridade.registros_do_dia`, grandeza `economia_verificada`). |
| Opção D | Contrafactual "e se" com o motor de simulação da plataforma (`simulacao.termica.perda_envoltoria`), com programa, versão e hash dos arquivos de entrada e saída. Calibração contínua do gêmeo digital: Fase 2. |
| Protocolos | MQTT e V6 já existem; Modbus entra pelo ESP do medidor `ENE` (EXTENSAO_V6). BACnet e OPC UA não existem no hub: Fase 2 pelo Node-RED dos serviços abertos (`SERVICOS_ABERTOS.md`). |

Rotas novas: `GET /api/validacao/auditoria?item=`, `POST /api/validacao/plano-mv | medidor | licao | inspecao | nre | tarefa | verificar`.

## PEE/ANEEL

O plano de M&V tem um perfil de programa: **Geral (IPMVP)** ou **PEE (ANEEL)**. No Programa de Eficiência Energética da
ANEEL, a M&V segue o PIMVP (nome do IPMVP em português); o PIMVP não cobre tudo do PEE (por exemplo, projetos em
comunidades de baixo poder aquisitivo pedem estratégia diferente, em geral por amostragem); e a metodologia pesa o erro da
medição, o custo da medição, o custo total do projeto e a energia economizada.

Com o perfil PEE, o plano e o relatório levam: energia economizada (MWh/ano), redução de demanda na ponta (kW), RCB com as
entradas, custo da M&V ÷ custo total (com aviso quando passa do limite) e erro, precisão e confiança alcançados. Para
muitas unidades parecidas (lâmpadas, geladeiras, aparelhos de ar), o plano amostral calcula a amostra por estrato com a
fórmula estatística **genérica** n₀ = (z·CV ÷ e)², n = n₀ ÷ (1 + n₀ ÷ N) — não é a fórmula da ANEEL.

**Nenhum número do PEE foi conferido.** Todas as exigências (confiança, precisão, amostra mínima, duração da medição, vida
útil, fórmula e limite da RCB, taxa de desconto, prazos, limite do custo da M&V) são premissas `validacao.pee.*` com
`[MARCADOR: conferir no Guia de M&V da ANEEL]`. Os números entram depois que os PDFs forem lidos. Fontes oficiais para a
leitura (pela direção):

- página de M&V do PEE: https://www.gov.br/aneel/pt-br/assuntos/programa-de-eficiencia-energetica/mv
- Guia de M&V, módulos 1.1 a 1.4 e 2.1 a 2.3: https://www.gov.br/aneel/pt-br/centrais-de-conteudos/manuais-modelos-e-instrucoes/pesquisa-e-desenvolvimento-e-eficiencia-energetica

## Mapa dos pedidos

Situação: **feito** (no código, com teste), **parcial** (existe, falta algo dito ao lado) ou **Fase 2**.

### Checklist de excelência (1º pedido)

| Item | Onde está | Situação |
|---|---|---|
| Plano de M&V versionado (escopo, fronteira, opção A/B/C/D com justificativa, método, fontes, variáveis, fatores estáticos, períodos, papéis, formato, periodicidade, QA, revisão anual) | `validacao.validar_plano_mv`, tabela `validacao_plano_mv`, aba · Plano de M&V | feito |
| Cada mudança no registro encadeado | `Validacao.gravar_plano_mv` → `hub.registrar` | feito |
| EnPI e EnB (ISO 50006) | `validacao.enpis`, aba · Modelos e incerteza | parcial (kWh/m², m³/pessoa, L/100 km; kWh por unidade produzida espera a produção da Gestão) |
| Cadastro de medidores com calibração e certificado (arquivo resumido em SHA-256) | tabela `validacao_medidor`, `alertas_medidor` | feito |
| Calibração em campo | — | Fase 2 |
| Granularidade nativa, plano de coleta e perda máxima | `limpar_serie`, `validacao.perda_dados_max_pct` | feito |
| Limpeza com o original e a marca | `limpar_serie` | feito |
| Modelos 2P a 5P, tipo ML só com dados bastantes, R², CV(RMSE), NMBE, erro padrão, aceite | `validacao_modelos`, `validacao_nucleo.escolher_por_cv` | feito |
| Incerteza fracional e veredito "dentro / fora do limite" | `incerteza_economia` | feito |
| M&V 2.0: economia acumulada, painel, alarmes FDD idempotentes com causa e ação | `Validacao.mv2`, aba · Painel M&V 2.0 | feito |
| Rastreabilidade de cada número (leituras, fator da rede, premissas, ajustes, versão do modelo) | `estado()["rastreio"]`, anexo do relatório | feito |
| Inspeção periódica das ECM | tabela `validacao_inspecao`, tarefas | feito |
| Relatório padrão com as seções fixas; opção D com programa, versão e hashes | `relatorio_blocos`, `SECOES_RELATORIO` | feito |
| Papéis com campo de competência (nunca presumida), revisão anual e diário de lições | plano, tabela `validacao_licao`, tarefas | feito |
| Equipe com CMVP real | — | Fase 2 |

### M&V 2.0 como núcleo (2º pedido)

| Item | Onde está | Situação |
|---|---|---|
| Dados de intervalo como fonte principal; fatura só para conferir | `agregar`, "Conferência com a fatura" | feito |
| Modelos diário e horário, 2P a 5P, escolha por validação cruzada | `escolher_por_cv`, `ajustar_horario` | feito |
| Ajuste mínimo (R² ou CV(RMSE)), valores-p e resíduos | `aceite_minimo`, `diagnostico` | feito |
| Retreino a cada ciclo e versão do modelo com hash | tabela `validacao_modelo` | feito |
| Deriva do modelo e do sensor (CUSUM) | `cusum` | parcial (sem fatura, a referência do sensor é fraca) |
| Pacote de auditoria reproduzível | `montar_pacote`, `conferir_pacote`, rota `auditoria` | feito |
| Monte Carlo com semente, IC e sensibilidade | `monte_carlo`, `sensibilidade` | feito |
| Política de faltantes e taxa por período | `agregar` | feito |
| Clima como variável principal (estação ou fonte aberta guardada) | `temperaturas_dia` | feito |
| NRE: detectar, classificar, quantificar, propor ajuste só com aprovação, registro | `detectar_nre`, `decidir_nre`, tabela `validacao_nre` | feito |
| FDD contra o intervalo de previsão, projeção por persistência, R$ em risco | `fdd_intervalo`, `projecao_persistencia`, `ordenar_por_risco` | parcial (tarifa digitada no plano; a base não tem tarifa R$/kWh [CONFERIR]) |
| Ciclo fechado com a Gestão (botão e modo automático desligado) | `criar_tarefa` | feito |
| Resultado verificável no lote de integridade | `verificar_resultado`, `integridade.registros_do_dia` | feito |
| Prova de conhecimento zero e contrato inteligente (parceiro) | interface: resumo no lote | Fase 2 |
| Opção D com o motor de simulação (programa, versão, hashes) | `contrafactual_d` | parcial (só condução da envoltória) |
| Calibração contínua do gêmeo digital | — | Fase 2 |
| Modbus | ESP do `ENE` (EXTENSAO_V6) | feito (pelo V6) |
| BACnet e OPC UA | Node-RED dos serviços abertos | Fase 2 |

### PEE/ANEEL (3º pedido)

| Item | Onde está | Situação |
|---|---|---|
| Perfil "PEE (ANEEL)" ao lado de "Geral (IPMVP)" | `validar_plano_mv` (`perfil`, `pee`) | feito |
| Campos do PEE no plano e no relatório | `resumo_pee`, `relatorio_blocos` | parcial — aguardando Guia |
| Exigências numéricas como premissas `validacao.pee.*` | `sistema/physis-premissas.json` | parcial — aguardando Guia |
| Plano amostral por estrato e precisão alcançada (fórmula genérica) | `tamanho_amostra`, `plano_amostral` | parcial — aguardando Guia |
| Teste do custo da M&V | `resumo_pee`["custo_check"] | parcial — aguardando Guia |
| Exportar o XML do relatório final da ANEEL ("XML_FINAL_RELATORIOPEE v3.0") | — | Fase 2 |

## Fase 2 em três horizontes

| Horizonte | O quê |
|---|---|
| Próximos meses | Ler o Guia de M&V da ANEEL e preencher `validacao.pee.*`; exportar o XML do relatório final do PEE; calibração dos medidores em campo; teste de campo com dados de intervalo reais. |
| Próximo ano | Gradient boosting, floresta aleatória e LSTM no servidor com bibliotecas abertas; calibração contínua do gêmeo digital; validação na borda, no firmware V6; BACnet e OPC UA pelo Node-RED; revisão por pares dos modelos; equipe com formação CMVP e NMEC. |
| Depois | Prova de conhecimento zero e contrato inteligente com o parceiro; otimização de ajustes por aprendizado por reforço (PPO), verificada pelo M&V. |

## O que falta

- Conferir todos os limites com 12 meses de dados reais da Casa Physis [CONFERIR].
- Ler o Guia de M&V da ANEEL e preencher as premissas `validacao.pee.*` [MARCADOR].
- Tarifa R$/kWh na base de premissas (hoje vem digitada no plano, com a fonte) [CONFERIR].
- Regressão com mais de uma variável; incerteza dos parâmetros do modelo.
- Trazer o planejado do Planejador sozinho (hoje a equipe digita, com a fonte).
