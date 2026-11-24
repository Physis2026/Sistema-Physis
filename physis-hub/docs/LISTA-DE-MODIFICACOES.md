# Lista de modificações

## Rodada de 24/11/2026 (correção final) · cada item entra na lista de aprovações do M&A (grupo "Final 24/11")

| Nº | Pedido | O que mudou | Onde ver | Testado |
|---|---|---|---|---|
| F1 | Novo visual | Cores e fontes do guia de identidade (tipo A escuro, tipo B claro) nas telas atuais; só aparência | Gestão, SustainKit, SCADA, Planejador, consultoria | testes de paleta e contraste |
| F2 | Bots autônomos, sem Claude | Texto livre na caixa de comandos respondido na hora (comandos locais + IA Physis); fila antiga respondida pelo vigia | M&A › Bots e comandos | sim |
| F3 | IA Physis generativa própria | Modelo aberto local (Ollama, qwen2.5:7b); busca → diretrizes (regras, decisões, aprendizagens) → skill → geração → trava de números → rascunho; resposta por trechos na hora e texto do modelo em segundo plano | M&A; py -m physis_hub.mv_cli ia | sim (modelo real no PC da Physis) |
| F4 | Planejador completo na Casa | Edição completa, sem ativação de licença, na instalação da Casa Physis | Casa › Planejador | sim |
| F5 | Análises por objeto e perguntas | Bot de modelagem diz as análises (CFD, flambagem, térmica…) e pergunta o que falta; flambagem conferida no CalculiX | Modelagem 3D, InovaSTEM › Simulação | sim |
| F6 | InovaSTEM sem repetição | Uma aba Impressão 3D (peça, parâmetros, filamentos, fatiamento, testes e fila); Simulação por área com previsão da modelagem; sem conteúdo de construção | /laboratorio | sim |
| F7 | Programas abertos e camadas | Catálogo só aberto (sem ORCA): mecânica, física, química, biologia, BIM e instalações, IoT/quadros, BMS e solar; guia de instalação no Acer com links [CONFERIR] e as 12 camadas | implantacao/PROGRAMAS-E-CAMADAS-ACER.md | catálogo sim; links não conferidos |
| F8 | AVAC completo | Água gelada; piscina com filtragem e borda infinita; sauna; exaustão de churrasqueira (dutos e aquecimento solar já existiam) | AVAC | sim |
| F9 | Sprinklers no Planejador | Número de chuveiros, vazão e reserva a partir de parâmetros digitados da NBR 10897 | Planejador › Módulos | sim |
| F10 | Estermic à parte | Sistema próprio na porta 8704, estado no servidor com histórico, IFC de instalações (chiller, bombas, ventiladores, difusores, torre) | http://127.0.0.1:8704 | sim |
| F11 | Atualização final | Um comando confere, copia bancos, regenera, testa, verifica serviços, salva e faz backup em zip | ferramentas/atualizacao_final.py | sim (PC da Physis, 24/11 01:49) |
| F12 | Quadros elétricos | Todas as normas registradas (IEC 60617/61082/81346, NBR 5410, NBR IEC 61439, IEC 60204-1, NBR 5444, NR-10, NR-12) [CONFERIR vigência] | guia do Acer | documento |

## Rodadas anteriores

### Terceira e quarta rodadas

14/11/2026. Para aprovar antes da emissão dos documentos finais. Os pacotes finais ainda não foram refeitos.

## 1. Feito e testado nesta rodada

| Nº | Pedido | O que mudou | Onde ver |
|---|---|---|---|
| 1 | “+” para adicionar produtos na loja | Botão “Adicionar produto” no modo de edição, com caixa: nome, código, resumo, assunto, situação, preço e “Mostrar ao cliente”. Dá para remover o que foi acrescentado. | Loja › Editar catálogo e preços |
| 2 | Diferença de pH com atraso de mistura | Compara o “depois” com o “antes” de alguns segundos atrás. O atraso é o volume do cano dividido pela vazão; sem vazão, vale um atraso fixo. | Qualidade da água |
| 3 | Condutividade | Leitura por ponto; sólidos dissolvidos só quando você informa o fator do laudo. | Qualidade da água |
| 4 | Indicador de limpeza do filtro | Três sinais: pressão no filtro, turbidez e dias desde a última limpeza. Pede limpeza com dois sinais juntos. Botão “Registrar limpeza hoje”. | Qualidade da água |
| 5 | Vazamento pela vazão noturna | Vazão do meio das leituras na janela sem irrigação, contra o limite que você define. | Qualidade da água |
| 6 | Proteção de bomba pela corrente | Avisos de corrente alta, corrente baixa, tensão baixa e bomba ligada sem fluxo. A plataforma avisa; não desliga a bomba. | Qualidade da água |
| 7 | Modos de operação | Normal, obra, seca e chuva, cada um com o seu limite de turbidez. | Qualidade da água |
| 8 | Registro de laudo | Data, laboratório, análise, resultado, validade e responsável, com aviso de laudo vencido. | Qualidade da água |
| 9 | Tipo desconhecido, faixas e poda | Dispositivo de tipo desconhecido é recusado, na tela e no servidor. Bateria e sinal absurdos são descartados e a leitura segue. A lista de leituras já vistas tem limite de 5.000. | Servidor e Diagnóstico |
| 10 | Acessibilidade dentro dos programas | Texto maior, espaçamento, contraste, modo calma e modo de conforto agora valem dentro do SCADA e do SustainKit. | Qualquer programa embutido |
| 11 | Modos que escondiam informação | O modo calma não esconde mais o mapa nem os gráficos; o modo foco não esconde mais o “ao vivo”. | Resumo |
| 12 | Segurança | O servidor envia política de conteúdo em toda resposta. A atualização para com a aba em segundo plano. | Servidor |
| 13 | Pessoa física ou jurídica em lista | Era um par de botões; agora é uma lista, e as caixas de baixo seguem a escolha. | Início |
| 14 | Transformadores | Número de transformadores; as caixas abrem conforme o número. | Início › Lugar e equipamentos |
| 15 | Plano de ação | “Atividades” virou “Plano de ação”, com detalhamento, responsável e prazo. Os próximos prazos aparecem no Início. | Gestão e Início |
| 16 | Sistemas de gestão como módulo | Saiu da Gestão e entrou na loja como próximo módulo, sob consulta. | Loja |
| 17 | Compras com análise de investimento | Tipo “Investimento”, com ganho por mês, vida útil e taxa de juros. A tela calcula o tempo de retorno e o valor presente líquido. | Gestão › Compras e investimentos |
| 18 | Indicadores de desempenho | Grupos de produção, energia, ambiental, qualidade e financeiro, e uma linha para acrescentar os seus (por exemplo, toneladas por kWh). | Gestão › Indicadores |
| 19 | Financeiro por projeto e por consultor | Duas tabelas automáticas nos totais, com impostos e custos das parcerias. | Gestão interna › Totais |
| 20 | Nome, e-mail e telefone obrigatórios só no pedido personalizado e no pagamento | No pagamento, os três passaram a ser obrigatórios. No Início e no primeiro acesso, deixaram de ser. | Loja › Pagamento; Início |
| 21 | Data no registro de fatores internos e externos | Campo Data, opcional, como primeira coluna. | Gestão › Fatores internos e externos |
| 22 | CPF obrigatório na compra e no pedido personalizado; CEP obrigatório; nome do lugar não | CPF ou CNPJ obrigatório no pagamento e no pedido. No Início, o CEP passou a ser obrigatório e o nome do lugar, opcional. | Loja; Início |
| 23 | Limite provisório ou confirmado | Cada grupo de limites da água tem a caixa “Limites confirmados”. Provisório mostra o diagnóstico na tela e não gera alerta. | Qualidade da água, nos ajustes de cada quadro |
| 24 | Origem de cada leitura | Digitada, de planilha, de exemplo ou do sensor; aparece na contagem e no arquivo baixado. | Qualidade da água › Leituras |
| 25 | Nível da represa e modo automático | Nível e chuva de 24 horas como medidas. No automático, entra em seca ou chuva sozinho; “obra” só por escolha. | Qualidade da água › Modo de operação |
| 26 | Documento de premissas | Tabela com 26 premissas e limites e a situação de cada um, para baixar. | Qualidade da água › Premissas e limites |
| 27 | Queda de energia nos dois cenários | Compara bomba desligando com bomba ligada: horas de irrigação perdidas contra energia das baterias. | Qualidade da água |
| 28 | Prazos do plano de ação no Resumo | Saíram do Início. Ação vencida e ação que vence em até 7 dias viram alerta no Resumo, sozinhas. | Resumo |
| 29 | Investimento no padrão de auditoria de grau de investimento | Campo de inflação; a tela calcula retorno simples, retorno descontado, valor presente líquido e taxa interna de retorno. | Gestão › Compras e investimentos |
| 30 | Indicadores do último mês e histórico de um ano | Duas colunas (último mês e 12 meses) e três gráficos. | Gestão › Indicadores |
| 31 | Tela de clientes separada da gestão financeira | Desenho refeito como “Plataforma Physis · Central de clientes”, só técnica. | Quadro de revisão (rascunho) |
| 32 | Compra de teste antiga não decide o que a plataforma mostra | Na demonstração, a loja abre sempre no catálogo. Era a causa de a plataforma aparecer só com o SustainKit. | Loja |
| 33 | Arquivos de download com nomes claros | Site e plataforma, gestão interna e servidor da Physis em arquivos separados. | Entrega |
| 34 | Gestão Physis com o menu do desenho e as Atividades da versão zero | Menu lateral com Atividades, Tarefas e projetos, Propostas, Contratos, Financeiro, Fornecedores, Alertas, Cursos e Meus contratos. As 39 tarefas, 9 pessoas e 15 projetos da versão zero estão mantidos. | Gestão Physis |
| 35 | Sem SCADA na gestão; telas do sistema original no menu | Saíram do cabeçalho os atalhos para o Painel do cliente e o SCADA. Entraram no menu “Mapa da equipe” e “Direção”, as outras duas telas do aplicativo original. | Gestão Physis |
| 36 | Todas as telas em inglês também | Botão “English” no Modelo 1, com 976 textos e 103 padrões traduzidos, em todas as telas da loja e da plataforma; o idioma é lembrado e segue para o SCADA. Menu, Reuniões e Documentos da Gestão Physis em inglês junto com o aplicativo. Ficam em português o SustainKit e, até recarregar, o painel administrativo da gestão. | Modelo 1 e Gestão Physis |
| 37 | Reuniões, transcrições de chamadas e documentos internos | Duas partes novas na Gestão Physis. Reuniões: data, assunto, participantes, notas, transcrição (colada ou lida de arquivo), encaminhamentos, busca. Documentos: envio de qualquer arquivo até 20 MB, com categoria, projeto, filtro, busca e download. A caixa “Dados da Physis” deixou de flutuar por cima da tela. | Gestão Physis |

Regressão: 54 testes do servidor, 10 cenários de estresse, 49 verificações da regressão da Physis e 370 estados de tela sem violação.

## 2. Desenhos para aprovar (ainda não construídos)

1. **Central de clientes**, separada da gestão financeira e administrativa. Um cartão por cliente, com versão, módulos, acesso, dispositivos, alertas e última comunicação. *Aprovada na quarta rodada, com a correção de ser uma interface à parte.*
2. **Cursos na loja.** Cursos como mais um assunto, com a mesma conta. *Aprovado.*
3. **Cursos na plataforma.** Aba com progresso, próxima aula e certificado. *Aprovado.*
4. **Cursos na gestão interna.** Cursos e turmas, com inscritos e receita. *Aprovado.*

Os quatro estão no quadro de revisão. Nomes de curso, cargas e preços são marcadores.

## 3. Login e acesso remoto para clientes com servidor próprio

**Pergunta:** quem tem servidor próprio e só usa o sistema precisa de login?

**Resposta: sim, mas só local.** É o que o sistema já faz:

- A conta é criada no próprio servidor do cliente. A senha fica lá, protegida, e nunca vai à Physis.
- Sem login, qualquer pessoa na mesma rede abriria a plataforma e poderia mandar irrigar. O login também diz quem fez o quê.
- Não é preciso conta na internet nem servidor da Physis para o dia a dia.

**Acesso remoto para reparo, sem guardar dados online.** Proposta:

1. O cliente liga um botão “Permitir suporte”, com prazo (por exemplo, 2 horas ou 1 dia).
2. O servidor dele abre uma ligação de saída até a Physis. Nada precisa ser aberto no roteador do cliente.
3. A equipe Physis vê as telas por essa ligação. Os dados passam, mas não ficam guardados no servidor da Physis.
4. O prazo acaba ou o cliente desliga: a ligação cai. Cada acesso fica registrado no servidor do cliente.

Isto ainda não está construído. Depende de escolher onde a ponte fica hospedada.

**O que falta em segurança:** endereço com HTTPS, limite de tentativas nas rotas públicas e isolamento completo dos programas embutidos (hoje eles precisam do mesmo espaço da página para receber o desenho e as preferências).

## 4. Como seria a unificação das partes comuns

| Parte comum | Onde está repetida hoje | Como unificar | Risco |
|---|---|---|---|
| Preferências de acessibilidade | Página principal; SCADA e Tela do cliente têm o seu próprio “conforto” | Um arquivo só (`physis-acessibilidade.js`), carregado por todos | Baixo. Primeiro passo já feito: a página repassa as preferências |
| Exportação (Word, PDF, Excel) | Página principal, SCADA, Tela do cliente e Gestão interna | `physis-exportar.js` servido uma vez pelo servidor | Baixo: é a mesma biblioteca |
| Leitor do protocolo | `protocolo.py`, página principal e Tela do cliente | Um arquivo de casos de teste comum; depois, um só leitor em JavaScript | Médio: precisa dos mesmos testes dos dois lados |
| Cores e fontes | Página principal e cada programa | Uma folha de estilo (`physis-padrao.css`) | Médio no SustainKit, que tem cores dentro das contas |
| Logo | Em cada arquivo | Um arquivo de imagem | Baixo |
| Dados (medições) | O campo guarda leituras; a auditoria guarda medições digitadas | Cada leitura vira medição, com a origem marcada | Alto: é a ponte entre os dois modelos |
| Programas embutidos como texto | Três programas dentro da página | Arquivos separados, com versão e hash, servidos pelo servidor | Baixo no servidor; a versão de arquivo único continua para demonstração |

**Ordem proposta:** exportação e logo; acessibilidade; programas como arquivos separados; folha de estilo; leitor do protocolo; por último, a ponte de dados. Em cada passo, comparar os resultados antes e depois.

## 5. O que preciso de você

1. **Aprovar ou corrigir os quatro desenhos.**
2. **“IGA”**, no seu pedido sobre compras: não entendi a sigla.
3. **SCADA:** “verificar interface dentro de sistema IoT e SustainKit”. Quer que o SCADA mostre dados do monitoramento e do SustainKit, ou que tenha o mesmo desenho?
4. **Financeiro (comprovantes):** você pediu mais praticidade em todo o mapeamento financeiro. Diga por onde começar.
5. **Relatório da Fazenda Santa Clara,** para a leitura do controlador de irrigação, o valor em reais da diferença de pH e os limites de cada modo.
6. **Faixas de bateria e de sinal** de cada equipamento. Usei limites largos, só para barrar valores absurdos.
7. **Regra do filtro** (dois sinais juntos) e **preço da Gestão** na loja.

## 6. O que ainda não foi feito

- Entrada da gestão interna com clientes e cursos: só o desenho.
- Produtos acrescentados na loja, Início, Gestão e água ficam guardados no aparelho, não no servidor.
- Modelagem financeira completa (índices bancários) e fechamento da parceria com os custos reais.
- Isolamento dos programas embutidos e HTTPS.
- Pacotes finais das duas versões: refaço depois da sua aprovação.

## 7. Três sistemas separados e a segurança dos dados

**Sim, são coisas diferentes, e é o normal mantê-las separadas.**

| Sistema | Para quem | O que tem | Onde ficam os dados |
|---|---|---|---|
| Plataforma do cliente | O cliente | Acesso técnico e supervisório: Início, monitoramento, água, SustainKit, SCADA, Gestão dele e Resumo | No servidor do próprio cliente |
| Central de clientes (rascunho) | Equipe técnica da Physis | Estado técnico de cada plataforma e suporte | Nada guardado; vê pela ligação de suporte |
| Gestão Physis | Direção e administrativo da Physis | Propostas, contratos, financeiro, consultores e fornecedores | Servidor da Physis |

O que liga os três é pouco e de propósito: a compra e o pedido de proposta saem da loja para a Gestão Physis; a liberação de uso volta para o cliente.

**Segurança hoje**

- Plataforma do cliente: login local, senha protegida que nunca sai do servidor do cliente, registro encadeado do que foi feito, política de conteúdo em toda resposta.
- Cada cliente tem o seu servidor e o seu banco: um cliente não enxerga o outro.

**O que falta antes de pôr dados reais**

- **Gestão Physis:** hoje guarda tudo no navegador e não tem senha por pessoa. Não é lugar para dado financeiro real ainda. Precisa de servidor, login por pessoa e cópia de segurança.
- **HTTPS** em tudo o que ficar na internet.
- **Gestão e Início do cliente** ainda guardam no aparelho, não no servidor dele.
- **Textos de privacidade**, prazo de guarda e “apagar meus dados”.
