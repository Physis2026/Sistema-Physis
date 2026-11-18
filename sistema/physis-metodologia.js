/* physis-metodologia.js — camada "Metodologia e normas" da plataforma.
   Os dados abaixo são cópia de sistema/physis-metodologia.json (a fonte). Para mudar, edite o JSON e copie de novo
   para o bloco entre DADOS-INICIO e DADOS-FIM (comando em physis-hub/docs/METODOLOGIA.md); o teste
   physis-hub/tests/test_metodologia.py reprova se os dois forem diferentes.
   Contrato: window.PHYSIS_METODOLOGIA (os dados) e window.metodologiaHtml(modulo, opcoes) → HTML de uma <section>
   com título "Metodologia e normas" e um <details> fechado. opcoes.nivel = nível do título (2 a 5, padrão 2);
   cada cálculo usa o nível seguinte. Módulo desconhecido → "" (a tela não quebra).
   Sem internet e sem dependência: usa esc() da plataforma se existir. Redação própria; normas só por número e item. */
(function () {
"use strict";
/*DADOS-INICIO*/
const DADOS = {
  "versao": 1,
  "atualizado": "2026-11-15",
  "regra": "Cada cálculo da plataforma que tem norma ligada diz qual norma, qual item, como ela é usada e a situação. Redação própria; nenhum trecho de norma é copiado.",
  "aviso": "Validação preliminar: não substitui o projeto com ART (ou RRT) de um profissional habilitado. As normas são citadas só pelo número e pelo item, com redação própria da Physis; consulte sempre a versão oficial vigente.",
  "status": {
    "conforme": {
      "selo": "ok"
    },
    "simplificado": {
      "selo": "at"
    },
    "só citado": {
      "selo": "in"
    },
    "falta implementar": {
      "selo": "al"
    }
  },
  "modulos": {
    "modulos": {
      "nome": "Loja Physis",
      "resumo": "Orçamento dos módulos escolhidos. Não há conta de engenharia.",
      "calculos": [
        {
          "id": "loja.orcamento",
          "nome": "Orçamento da loja",
          "o_que_calcula": "Soma o preço de cada módulo escolhido, o valor anual e a quantidade.",
          "formula": {
            "texto": "total = Σ (quantidade × preço unitário); anual = Σ valores anuais",
            "variaveis": [
              {
                "simbolo": "quantidade",
                "significado": "quantidade de cada item",
                "unidade": "un."
              },
              {
                "simbolo": "preço unitário",
                "significado": "preço da tabela da Physis",
                "unidade": "R$"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Conta de soma; os preços vêm da tabela da Physis, nunca inventados (marcador quando falta)."
            },
            {
              "codigo": "Lei 8.078/1990",
              "edicao": "1990",
              "item": "art. 31",
              "como_e_usada": "O preço e as condições aparecem claros antes do pagamento."
            },
            {
              "codigo": "Decreto 7.962/2013",
              "edicao": "2013",
              "item": "art. 2º",
              "como_e_usada": "A página de pagamento mostra o preço total, as despesas e as condições."
            }
          ],
          "limites_de_validade": "Vale para a tabela de preços em vigor.",
          "fonte_de_dados": "Tabela de preços da Physis no servidor.",
          "status": "conforme",
          "o_que_falta": "",
          "onde": "physis-hub/web/painel.html · calcular(m) da loja"
        }
      ]
    },
    "inicio": {
      "nome": "Início",
      "resumo": "Perfil do lugar e histórico das contas de luz e água, que alimentam Carbono, Solar e Certificações.",
      "calculos": [
        {
          "id": "inicio.media_contas",
          "nome": "Média anual das contas",
          "o_que_calcula": "Leva as últimas contas de luz (até 12) para um ano, para servir de consumo de referência.",
          "formula": {
            "texto": "E_ano = (Σ kWh das últimas n contas) × 12 ÷ n",
            "variaveis": [
              {
                "simbolo": "E_ano",
                "significado": "consumo de um ano",
                "unidade": "kWh/ano"
              },
              {
                "simbolo": "n",
                "significado": "número de contas (1 a 12)",
                "unidade": "meses"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ISO 50006",
              "edicao": "2023",
              "item": "seções de linha de base",
              "como_e_usada": "Ideia de linha de base energética: um período de referência que represente o uso normal."
            },
            {
              "codigo": "ISO 50001",
              "edicao": "2018 (Amd 1:2024)",
              "item": "6.5",
              "como_e_usada": "A média das contas é o começo da linha de base que a norma pede."
            }
          ],
          "limites_de_validade": "Com menos de 12 contas a sazonalidade some; o sistema avisa quantas contas usou.",
          "fonte_de_dados": "Contas informadas pela pessoa no Início.",
          "status": "simplificado",
          "o_que_falta": "Com 12 meses ou mais, normalizar pela variável que explica o consumo (graus-dia, produção, ocupação), como pede a ISO 50006. O modelo de consumo do aprendizado.py já faz parte disso.",
          "onde": "painel.html · carbKwhDoInicio()"
        }
      ]
    },
    "mapeamento": {
      "nome": "Mapeamento",
      "resumo": "Camadas abertas do lugar numa tela só: zonas do IBGE, Köppen, solo, relevo, clima, rio e destinos de resíduos. As contas de solo, relevo, clima e rio são as mesmas das outras abas.",
      "calculos": [
        {
          "id": "map.koppen",
          "nome": "Clima de Köppen do lugar",
          "o_que_calcula": "A classe de Köppen pelas médias mensais de temperatura e chuva, com a temperatura corrigida pela altitude real do lugar.",
          "formula": {
            "texto": "T_lugar = T_base − 0,0065 × (altitude do lugar − altitude da célula da base), quando a diferença passa de 50 m; depois, as regras de Köppen-Geiger (grupos A, B, C pelas temperaturas e pela chuva do mês mais seco)",
            "variaveis": [
              {
                "simbolo": "T_base",
                "significado": "temperatura média do mês na célula da base aberta",
                "unidade": "°C"
              },
              {
                "simbolo": "T_lugar",
                "significado": "temperatura média do mês corrigida para o lugar",
                "unidade": "°C"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "",
              "item": "",
              "como_e_usada": "Método de referência: classificação climática de Köppen-Geiger; gradiente de 6,5 °C por km da atmosfera padrão."
            }
          ],
          "limites_de_validade": "A base de clima tem células de cerca de 50 km; a correção de altitude não vê encosta, vale nem vento local.",
          "fonte_de_dados": "NASA POWER (médias de longo prazo), guardada no servidor; altitude do lugar pela base de relevo.",
          "status": "simplificado",
          "o_que_falta": "Comparar com estação meteorológica próxima (INMET) quando houver 30 anos de dados e mostrar a diferença na tela. Só software.",
          "onde": "physis_hub/zonas.py · koppen(); painel.html · telaMapeamento()"
        }
      ]
    },
    "planejador": {
      "nome": "Planejador",
      "resumo": "Terreno, implantação e cálculos por norma do estudo preliminar (programa modulos/planejador/planejador-physis.html).",
      "calculos": [
        {
          "id": "plan.declividade_app",
          "nome": "Declividade e APP de encosta",
          "o_que_calcula": "Mede a inclinação do terreno em cada célula e marca a área acima de 45° como APP e acima de 30% como área que pede estudo.",
          "formula": {
            "texto": "i = Δz ÷ Δx (m/m); APP se i ≥ 1 (45° = 100%); atenção se i ≥ 0,30; topo de morro: se altura ≥ mínima e inclinação média > a da base, APP acima de base + 2/3 da altura",
            "variaveis": [
              {
                "simbolo": "i",
                "significado": "declividade",
                "unidade": "m/m ou %"
              },
              {
                "simbolo": "Δz",
                "significado": "diferença de altura entre vizinhos",
                "unidade": "m"
              },
              {
                "simbolo": "Δx",
                "significado": "distância horizontal",
                "unidade": "m"
              }
            ]
          },
          "premissas": [
            "app.declividade",
            "app.faixa_rio",
            "app.raio_nascente",
            "app.topo_morro"
          ],
          "normas": [
            {
              "codigo": "Lei 12.651/2012",
              "edicao": "2012",
              "item": "art. 4º, I, IV, V e IX",
              "como_e_usada": "Encosta acima de 45° (= 100%), faixa de rios pela largura (I), raio de nascentes (IV) e topo de morro (IX, triagem pelo relevo); larguras e parâmetros da base a conferir."
            },
            {
              "codigo": "Lei 6.766/1979",
              "edicao": "1979",
              "item": "art. 3º, parágrafo único",
              "como_e_usada": "Terreno com 30% ou mais só pode ser parcelado com exigências do órgão; o sistema mostra o alerta."
            },
            {
              "codigo": "ABNT NBR 11682",
              "edicao": "2009",
              "item": "requisitos de estudo",
              "como_e_usada": "Acima de 30% o sistema pede estudo de estabilidade."
            }
          ],
          "limites_de_validade": "A resolução é a do levantamento ou do modelo de elevação (30 m no SRTM). Modelo de 30 m não vê taludes pequenos.",
          "fonte_de_dados": "Topografia enviada pela pessoa ou modelo de elevação aberto; hidrografia instalada no servidor (base da ANA convertida por ferramentas/hidrografia_servidor.py) ou rio digitado.",
          "status": "conforme",
          "o_que_falta": "Feito em 15/11/2026: APP de rios (I) e nascentes (IV) com a camada de hidrografia do servidor (GET /api/gis/hidrografia, quando instalada) ou rio digitado ou importado, sempre com a largura digitada; topo de morro (IX) em triagem pelo relevo do terreno. Falta: o engenheiro conferir as larguras e os parâmetros (premissas 'conferir') e confirmar a base do morro com o modelo de elevação da região.",
          "onde": "planejador-physis.html (declividade, aptidão) · physis_hub/gis.py relevo()"
        },
        {
          "id": "plan.estabilidade",
          "nome": "Triagem de estabilidade da encosta",
          "o_que_calcula": "Estima o fator de segurança (FS) da encosta seca e saturada, para dizer onde não cortar nem infiltrar.",
          "formula": {
            "texto": "Talude infinito: FS = [c' + (γ·z − m·γw·z)·cos²β·tan φ'] ÷ (γ·z·sen β·cos β)",
            "variaveis": [
              {
                "simbolo": "FS",
                "significado": "fator de segurança",
                "unidade": "—"
              },
              {
                "simbolo": "c'",
                "significado": "coesão efetiva",
                "unidade": "kPa"
              },
              {
                "simbolo": "φ'",
                "significado": "ângulo de atrito",
                "unidade": "°"
              },
              {
                "simbolo": "γ",
                "significado": "peso específico do solo",
                "unidade": "kN/m³"
              },
              {
                "simbolo": "z",
                "significado": "espessura da camada",
                "unidade": "m"
              },
              {
                "simbolo": "m",
                "significado": "fração saturada (0 a 1)",
                "unidade": "—"
              },
              {
                "simbolo": "β",
                "significado": "inclinação",
                "unidade": "°"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 11682",
              "edicao": "2009",
              "item": "fatores de segurança mínimos",
              "como_e_usada": "O FS mínimo de referência (1,5) é comparado ao calculado; a norma pede estudo com sondagem."
            },
            {
              "codigo": "ABNT NBR 6484",
              "edicao": "2020",
              "item": "ensaio SPT",
              "como_e_usada": "Os parâmetros são típicos até a sondagem SPT."
            }
          ],
          "limites_de_validade": "Só triagem: talude infinito, parâmetros estimados. Não vale para ruptura circular, rocha ou aterro.",
          "fonte_de_dados": "Parâmetros típicos por tipo de solo; sondagem quando houver.",
          "status": "simplificado",
          "o_que_falta": "Engenheiro geotécnico confere o FS mínimo pelo nível de segurança da NBR 11682 (vidas e bens em risco) e troca por análise com sondagem.",
          "onde": "planejador-physis.html · triagem geotécnica"
        },
        {
          "id": "plan.drenagem",
          "nome": "Drenagem: vazão e detenção da chuva",
          "o_que_calcula": "Calcula a vazão de chuva antes e depois da obra e o volume para não aumentar o pico.",
          "formula": {
            "texto": "Q = C·i·A ÷ 3,6 (método racional); calhas (NBR 10844): Q = i·A ÷ 60 (L/min) com i da IDF no tempo de retorno e na duração da base e área (a + h/2)·b no telhado inclinado; calha retangular por Manning; SCS-CN como segundo método",
            "variaveis": [
              {
                "simbolo": "Q",
                "significado": "vazão de pico",
                "unidade": "m³/s"
              },
              {
                "simbolo": "C",
                "significado": "coeficiente de escoamento",
                "unidade": "—"
              },
              {
                "simbolo": "i",
                "significado": "intensidade da chuva",
                "unidade": "mm/h"
              },
              {
                "simbolo": "A",
                "significado": "área de contribuição",
                "unidade": "km²"
              },
              {
                "simbolo": "T",
                "significado": "tempo de retorno",
                "unidade": "anos"
              },
              {
                "simbolo": "t",
                "significado": "duração",
                "unidade": "min"
              }
            ]
          },
          "premissas": [
            "drenagem.calha_tr",
            "drenagem.calha_duracao",
            "drenagem.calha_manning_n",
            "drenagem.calha_declividade",
            "drenagem.condutor_diam_min"
          ],
          "normas": [
            {
              "codigo": "ABNT NBR 10844",
              "edicao": "1989",
              "item": "calhas e condutores",
              "como_e_usada": "Citada para calhas e condutores; o dimensionamento das calhas ainda não é feito."
            },
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Método racional e SCS-CN (TR-55) são métodos de hidrologia; a lei municipal costuma exigir a detenção."
            }
          ],
          "limites_de_validade": "Racional vale para bacias pequenas (até cerca de 2 a 3 km²). A IDF tem de ser a do município.",
          "fonte_de_dados": "IDF informada pela pessoa (SGB/CPRM ou estudo local).",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: vazão de cada água de telhado e calha sugerida pela NBR 10844. Falta: diâmetro do condutor pelo ábaco da norma e engenheiro conferir os valores marcados [CONFERIR NA NORMA].",
          "onde": "planejador-physis.html · bloco Drenagem e Calhas; sistema/physis-calc-comum.js · calhas()"
        },
        {
          "id": "plan.agua_fria",
          "nome": "Consumo e reservação de água",
          "o_que_calcula": "Estima o consumo diário pelas pessoas e usos, a reservação e se a pressão pede válvula redutora.",
          "formula": {
            "texto": "Consumo = Σ (pessoas × L/pessoa·dia); reserva = consumo × dias; redutora se desnível > 40 m",
            "variaveis": [
              {
                "simbolo": "L/pessoa·dia",
                "significado": "consumo por pessoa",
                "unidade": "L"
              },
              {
                "simbolo": "dias",
                "significado": "dias de reserva (padrão 2)",
                "unidade": "dias"
              },
              {
                "simbolo": "desnível",
                "significado": "diferença de altura até o ponto mais baixo",
                "unidade": "m"
              }
            ]
          },
          "premissas": [
            "agua.per_capita",
            "agua.reserva_dias"
          ],
          "normas": [
            {
              "codigo": "ABNT NBR 5626",
              "edicao": "2020",
              "item": "pressões máximas e reservação",
              "como_e_usada": "Pressão estática acima de 400 kPa (≈ 40 m) pede redutora; a reserva é definida pelo projetista."
            },
            {
              "codigo": "ABNT NBR 7229",
              "edicao": "1993",
              "item": "tabela de contribuição",
              "como_e_usada": "Os valores por pessoa saem da tabela de esgoto, usada como estimativa de consumo."
            }
          ],
          "limites_de_validade": "Estimativa de estudo preliminar; não é o dimensionamento de tubos.",
          "fonte_de_dados": "Ocupação informada; catálogo do Planejador.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: dias de reserva na base de premissas. Falta: dimensionamento de tubos (pesos e vazões) fica para o projeto.",
          "onde": "planejador-physis.html · bloco Água"
        },
        {
          "id": "plan.chuva_cisterna",
          "nome": "Aproveitamento de água de chuva",
          "o_que_calcula": "Simula a cisterna dia a dia com a chuva mensal do projeto e mostra cobertura e dias com água da rede para vários volumes.",
          "formula": {
            "texto": "Captado no mês = A × max(0, P × C − descarte × dias de chuva) ÷ 1000; balanço mês a mês S(m) = min(V, S(m−1) + captado − demanda) (núcleo) e dia a dia (módulo)",
            "variaveis": [
              {
                "simbolo": "P",
                "significado": "chuva do dia",
                "unidade": "mm"
              },
              {
                "simbolo": "A",
                "significado": "área de telhado",
                "unidade": "m²"
              },
              {
                "simbolo": "C",
                "significado": "coeficiente de escoamento",
                "unidade": "—"
              },
              {
                "simbolo": "V",
                "significado": "volume da cisterna",
                "unidade": "m³"
              }
            ]
          },
          "premissas": [
            "chuva.coef_escoamento",
            "chuva.descarte_inicial",
            "agua.fracao_nao_potavel"
          ],
          "normas": [
            {
              "codigo": "ABNT NBR 15527",
              "edicao": "2019",
              "item": "dimensionamento do reservatório",
              "como_e_usada": "A norma deixa escolher o método se ele for justificado; o balanço diário é um dos aceitos."
            },
            {
              "codigo": "ABNT NBR 16783",
              "edicao": "2019",
              "item": "usos não potáveis",
              "como_e_usada": "A água de chuva vai só para usos não potáveis."
            }
          ],
          "limites_de_validade": "Chuva diária simulada a partir da mensal; vale como estudo.",
          "fonte_de_dados": "Chuva mensal do projeto (INMET ou base GIS).",
          "status": "conforme",
          "o_que_falta": "Feito em 15/11/2026: descarte da primeira chuva descontado (mês a mês e na simulação diária). Falta: engenheiro conferir o valor do descarte na NBR 15527.",
          "onde": "planejador-physis.html · run() (PhysisCalc.cisterna) e Água de chuva por simulação diária"
        },
        {
          "id": "plan.esgoto",
          "nome": "Tanque séptico, filtro e infiltração",
          "o_que_calcula": "Dimensiona o tanque séptico, o filtro anaeróbio e a área de infiltração para casas sem rede pública.",
          "formula": {
            "texto": "V_tanque = 1.000 + N·(C·T + K·Lf); V_filtro = 1,6·N·C·T; área de infiltração = N·C ÷ coeficiente de infiltração",
            "variaveis": [
              {
                "simbolo": "N",
                "significado": "pessoas ou unidades",
                "unidade": "—"
              },
              {
                "simbolo": "C",
                "significado": "contribuição de esgoto",
                "unidade": "L/pessoa·dia"
              },
              {
                "simbolo": "T",
                "significado": "tempo de detenção",
                "unidade": "dia"
              },
              {
                "simbolo": "K",
                "significado": "taxa de acumulação de lodo",
                "unidade": "dia"
              },
              {
                "simbolo": "Lf",
                "significado": "lodo fresco",
                "unidade": "L/pessoa·dia"
              }
            ]
          },
          "premissas": [
            "agua.per_capita"
          ],
          "normas": [
            {
              "codigo": "ABNT NBR 7229",
              "edicao": "1993",
              "item": "fórmula do volume útil e tabelas de C, T, K e Lf",
              "como_e_usada": "Mesma forma de cálculo da norma; distâncias mínimas de 1,5 m conferidas no mapa."
            },
            {
              "codigo": "ABNT NBR 13969",
              "edicao": "1997",
              "item": "filtro anaeróbio, sumidouro e ensaio de percolação (anexo A)",
              "como_e_usada": "Filtro e área de infiltração; a disposição final depende do ensaio."
            },
            {
              "codigo": "ABNT NBR 17076",
              "edicao": "2024",
              "item": "toda a norma",
              "como_e_usada": "Pode ter substituído as duas acima: conferir antes de usar em projeto."
            }
          ],
          "limites_de_validade": "Até cerca de 50 pessoas (sistema de pequeno porte).",
          "fonte_de_dados": "Ocupação informada; solo estimado até o ensaio de percolação.",
          "status": "conforme",
          "o_que_falta": "Engenheiro confere se a NBR 17076:2024 substituiu a 7229 e a 13969; se sim, rever fórmulas e tabelas.",
          "onde": "planejador-physis.html · bloco Esgoto"
        },
        {
          "id": "plan.energia",
          "nome": "Consumo de energia e placas solares",
          "o_que_calcula": "Estima o consumo por área e uso e a potência solar para cobrir 100%.",
          "formula": {
            "texto": "kWp = consumo mensal ÷ produção por kWp (kWh/kWp·mês); placas = kWp ÷ 0,55",
            "variaveis": [
              {
                "simbolo": "produção",
                "significado": "energia de cada kWp",
                "unidade": "kWh/kWp·mês"
              }
            ]
          },
          "premissas": [
            "pv.pr"
          ],
          "normas": [
            {
              "codigo": "ABNT NBR 16690",
              "edicao": "2019",
              "item": "requisitos de projeto do arranjo",
              "como_e_usada": "Citada para o projeto do arranjo; não calculada aqui."
            },
            {
              "codigo": "REN ANEEL 1.059/2023",
              "edicao": "2023",
              "item": "acesso à rede",
              "como_e_usada": "Citada para a conexão."
            },
            {
              "codigo": "ABNT NBR 5410",
              "edicao": "2004 (versão corrigida 2008)",
              "item": "geral",
              "como_e_usada": "Citada para a instalação."
            }
          ],
          "limites_de_validade": "Estudo preliminar.",
          "fonte_de_dados": "Catálogo de consumo por área (editável); PVGIS ou base GIS.",
          "status": "só citado",
          "o_que_falta": "As normas são só citadas: o projeto elétrico do arranjo (strings, cabos, proteções) fica para o projetista. Ver também o módulo Energia solar.",
          "onde": "planejador-physis.html · bloco Energia"
        },
        {
          "id": "plan.estrutura",
          "nome": "Pré-dimensionamento de estrutura",
          "o_que_calcula": "Dá a ordem de grandeza de pilares, vigas, lajes e sapatas por área de influência.",
          "formula": {
            "texto": "Carga por pilar = área de influência × (peso próprio + sobrecarga); sapata = carga ÷ tensão admissível",
            "variaveis": [
              {
                "simbolo": "sobrecarga",
                "significado": "carga de uso",
                "unidade": "kN/m²"
              },
              {
                "simbolo": "tensão admissível",
                "significado": "do solo",
                "unidade": "kPa"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 6120",
              "edicao": "2019",
              "item": "cargas de uso",
              "como_e_usada": "Sobrecarga por tipo de uso."
            },
            {
              "codigo": "ABNT NBR 6118",
              "edicao": "2023",
              "item": "concreto",
              "como_e_usada": "C25 e CA-50 como hipótese."
            },
            {
              "codigo": "ABNT NBR 6122",
              "edicao": "2022",
              "item": "fundações",
              "como_e_usada": "Fundação só depois da sondagem."
            }
          ],
          "limites_de_validade": "Só ordem de grandeza, malha de cerca de 5 m.",
          "fonte_de_dados": "Hipóteses do Planejador.",
          "status": "simplificado",
          "o_que_falta": "O cálculo estrutural é do projetista com ART.",
          "onde": "planejador-physis.html · bloco Estrutura"
        },
        {
          "id": "plan.acessibilidade",
          "nome": "Rota acessível",
          "o_que_calcula": "Mede o desnível do acesso até cada construção e escolhe calçada, rampa ou plataforma.",
          "formula": {
            "texto": "inclinação = desnível ÷ distância; ≤ 5% calçada; ≤ 8,33% rampa com patamares; acima, plataforma",
            "variaveis": [
              {
                "simbolo": "inclinação",
                "significado": "da rota",
                "unidade": "%"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 9050",
              "edicao": "2020",
              "item": "rampas e rotas acessíveis",
              "como_e_usada": "Limites de inclinação de calçada e rampa."
            }
          ],
          "limites_de_validade": "Rota pelo terreno, sem detalhar degraus, larguras e patamares.",
          "fonte_de_dados": "Terreno e acesso desenhados.",
          "status": "simplificado",
          "o_que_falta": "A NBR 9050 limita também a altura de cada trecho de rampa conforme a inclinação; incluir essa tabela e a largura mínima.",
          "onde": "planejador-physis.html · bloco Acessibilidade"
        },
        {
          "id": "plan.incendio",
          "nome": "Medidas básicas contra incêndio",
          "o_que_calcula": "Indica extintores, iluminação, sinalização e saídas pelo uso e área.",
          "formula": {
            "texto": "extintores ≥ área ÷ área por extintor (pela classe de risco)",
            "variaveis": [
              {
                "simbolo": "área",
                "significado": "área construída",
                "unidade": "m²"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 12693",
              "edicao": "a conferir",
              "item": "distribuição de extintores",
              "como_e_usada": "Quantidade mínima indicativa."
            }
          ],
          "limites_de_validade": "Indicativo; a exigência final é do Corpo de Bombeiros.",
          "fonte_de_dados": "Uso e área das construções.",
          "status": "simplificado",
          "o_que_falta": "Ligar à Instrução Técnica do estado escolhido.",
          "onde": "planejador-physis.html · bloco Incêndio"
        },
        {
          "id": "plan.insolacao",
          "nome": "Sol, orientação e zona bioclimática",
          "o_que_calcula": "Calcula a exposição ao sol de telhados e encostas e indica a zona bioclimática.",
          "formula": {
            "texto": "Posição do sol por latitude, dia e hora (declinação e ângulo horário); sombra pelo modelo do terreno",
            "variaveis": [
              {
                "simbolo": "δ",
                "significado": "declinação solar",
                "unidade": "°"
              },
              {
                "simbolo": "ω",
                "significado": "ângulo horário",
                "unidade": "°"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 15220",
              "edicao": "a conferir",
              "item": "parte 3 (zoneamento)",
              "como_e_usada": "Zona bioclimática e diretrizes; só citada."
            },
            {
              "codigo": "ABNT NBR 15575",
              "edicao": "2021",
              "item": "desempenho térmico",
              "como_e_usada": "Só citada."
            },
            {
              "codigo": "Duffie & Beckman",
              "edicao": "4ª ed., 2013",
              "item": "geometria solar",
              "como_e_usada": "Fórmulas da posição do sol."
            }
          ],
          "limites_de_validade": "Geometria solar sem nuvens.",
          "fonte_de_dados": "Latitude e modelo do terreno.",
          "status": "só citado",
          "o_que_falta": "Graus-dia e verificação da envoltória pela NBR 15575 (transmitância e absortância) estão listados como próximo módulo; um engenheiro confere a revisão vigente da NBR 15220.",
          "onde": "planejador-physis.html · exposição ao sol"
        }
      ]
    },
    "sustainkit": {
      "nome": "SustainKit",
      "resumo": "Modelagem rápida de energia, água, carbono e custos (sistema/SustainKit_Definitivo.html, objeto SK).",
      "calculos": [
        {
          "id": "sk.agua",
          "nome": "Captação de chuva e consumo",
          "o_que_calcula": "Estima a água de chuva captada por dia e o consumo das pessoas.",
          "formula": {
            "texto": "captação (L/dia) = chuva anual × área × C ÷ 365 (indicador); cisterna = a mesma conta do Planejador: balanço mês a mês com descarte inicial e demanda não potável = pessoas × L/pessoa·dia × parte não potável",
            "variaveis": [
              {
                "simbolo": "C",
                "significado": "coeficiente de escoamento",
                "unidade": "—"
              },
              {
                "simbolo": "área",
                "significado": "área de telhado",
                "unidade": "m²"
              }
            ]
          },
          "premissas": [
            "chuva.coef_escoamento",
            "agua.per_capita",
            "chuva.descarte_inicial",
            "agua.fracao_nao_potavel"
          ],
          "normas": [
            {
              "codigo": "ABNT NBR 15527",
              "edicao": "2019",
              "item": "dimensionamento",
              "como_e_usada": "Média anual serve só de estimativa; a norma pede olhar a chuva mês a mês."
            },
            {
              "codigo": "ABNT NBR 7229",
              "edicao": "1993",
              "item": "tabela de contribuição",
              "como_e_usada": "Origem dos valores por pessoa (estimativa)."
            }
          ],
          "limites_de_validade": "Sem a chuva mês a mês (digitada ou do Planejador) a cisterna não é dimensionada.",
          "fonte_de_dados": "Cidade escolhida (chuva anual) e Cadastro.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: cisterna pelo balanço mês a mês do Planejador (mesma função) com o pior mês. Falta: trazer a chuva mensal da base GIS do servidor pela cidade.",
          "onde": "SustainKit_Definitivo.html · SK.cisterna, calcAgua()"
        },
        {
          "id": "sk.fluxo_agua",
          "nome": "Fluxo da água e reúso",
          "o_que_calcula": "Divide a água do dia em chuva, reúso, rede, esgoto e o que não volta.",
          "formula": {
            "texto": "esgoto = 0,80 × demanda; reúso = min(esgoto × %reúso, demanda − chuva); rede = demanda − chuva − reúso",
            "variaveis": [
              {
                "simbolo": "0,80",
                "significado": "coeficiente de retorno água → esgoto",
                "unidade": "—"
              }
            ]
          },
          "premissas": [
            "esgoto.coef_retorno"
          ],
          "normas": [
            {
              "codigo": "ABNT NBR 9649",
              "edicao": "1986",
              "item": "coeficiente de retorno",
              "como_e_usada": "Origem do valor de 0,80."
            },
            {
              "codigo": "ABNT NBR 13969",
              "edicao": "1997",
              "item": "reúso (classes)",
              "como_e_usada": "O reúso segue as classes de uso."
            },
            {
              "codigo": "ABNT NBR 16783",
              "edicao": "2019",
              "item": "fontes alternativas",
              "como_e_usada": "Qualidade mínima por uso."
            }
          ],
          "limites_de_validade": "Balanço diário médio.",
          "fonte_de_dados": "Entradas do bloco Água.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: coeficiente de retorno lido da base. Falta: conferir o valor na NBR 9649.",
          "onde": "SustainKit_Definitivo.html · SK.fluxoAgua"
        },
        {
          "id": "sk.solar",
          "nome": "Solar por horas de sol pleno",
          "o_que_calcula": "Potência mínima e geração anual pelas horas de sol pleno da cidade.",
          "formula": {
            "texto": "HSP no plano = HSP da cidade × fator do plano (modelo isotrópico, PhysisCalc.fatorPlano); P_min = consumo diário ÷ (HSP × PR); geração = P × HSP × 365 × PR",
            "variaveis": [
              {
                "simbolo": "HSP",
                "significado": "horas de sol pleno (média ou pior mês)",
                "unidade": "h/dia"
              },
              {
                "simbolo": "PR",
                "significado": "rendimento global",
                "unidade": "—"
              }
            ]
          },
          "premissas": [
            "pv.pr"
          ],
          "normas": [
            {
              "codigo": "IEC 61724-1",
              "edicao": "2021",
              "item": "definição do PR",
              "como_e_usada": "O PR segue a definição da norma de monitoramento."
            },
            {
              "codigo": "ABNT NBR 16690",
              "edicao": "2019",
              "item": "projeto do arranjo",
              "como_e_usada": "Só citada."
            }
          ],
          "limites_de_validade": "Tabela de 11 cidades; plano horizontal.",
          "fonte_de_dados": "Tabela CIDADES do SustainKit.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: inclinação e orientação (digitadas ou do telhado do Planejador) pelo mesmo modelo da aba Energia solar; sol mês a mês da plataforma quando o SustainKit está dentro dela, senão pela latitude escalada ao HSP da cidade. Falta: tabela de cidades com a base do servidor fora da plataforma.",
          "onde": "SustainKit_Definitivo.html · SK.solar"
        },
        {
          "id": "sk.bateria",
          "nome": "Banco de baterias",
          "o_que_calcula": "Energia do banco para as horas de autonomia.",
          "formula": {
            "texto": "E = consumo diário × horas ÷ 24 ÷ DoD ÷ rendimento de ida e volta (regra única: plataforma, SustainKit e agro)",
            "variaveis": [
              {
                "simbolo": "DoD",
                "significado": "profundidade de descarga",
                "unidade": "—"
              },
              {
                "simbolo": "1,2",
                "significado": "margem",
                "unidade": "—"
              }
            ]
          },
          "premissas": [
            "bateria.dod",
            "bateria.rendimento"
          ],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Não há NBR de dimensionamento de banco de baterias; segurança pela IEC 62619 (lítio)."
            },
            {
              "codigo": "IEC 62619",
              "edicao": "2022",
              "item": "segurança",
              "como_e_usada": "Só citada."
            }
          ],
          "limites_de_validade": "Sem perdas do inversor separadas.",
          "fonte_de_dados": "Consumo e autonomia informados.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: uma regra só (÷ rendimento 0,95 da base) na plataforma e no SustainKit; a margem de 1,2 saiu. Falta: perfil por hora quando houver medição; conferir o rendimento na folha de dados.",
          "onde": "SustainKit_Definitivo.html · SK.bateria"
        },
        {
          "id": "sk.carbono",
          "nome": "Carbono do SustainKit",
          "o_que_calcula": "Emissões da rede e do diesel, evitado pela solar e pelo biogás, carbono dos materiais.",
          "formula": {
            "texto": "inventário = rede (kWh ÷ 1000 × fator SIN) + diesel (L × 2,671 kgCO₂e/L); evitadas à parte: solar (kWh × fator SIN) e biogás no lugar do GLP (m³ × 6 kWh/m³ ÷ 12,8 kWh/kg × fator do GLP)",
            "variaveis": [
              {
                "simbolo": "fator SIN",
                "significado": "fator da rede",
                "unidade": "tCO₂/MWh"
              }
            ]
          },
          "premissas": [
            "rede.fator_emissao",
            "combustivel.diesel",
            "combustivel.glp",
            "biogas.pci",
            "glp.pci"
          ],
          "normas": [
            {
              "codigo": "GHG Protocol",
              "edicao": "2004 / 2015",
              "item": "escopos 1 e 2",
              "como_e_usada": "Divisão em escopos."
            },
            {
              "codigo": "ISO 14064-1",
              "edicao": "2018",
              "item": "quantificação",
              "como_e_usada": "Base do inventário."
            }
          ],
          "limites_de_validade": "Mesmos fatores e a mesma regra do biogás da aba Carbono; o SustainKit não tem remoções nem créditos, então o saldo net zero é o próprio inventário.",
          "fonte_de_dados": "Entradas do bloco Carbono.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: diesel por litro e biogás pela regra da aba Carbono, da base de premissas; a solar não abate mais o inventário. Falta: fatores com ano e fonte (adequação 23).",
          "onde": "SustainKit_Definitivo.html · SK.carbono"
        },
        {
          "id": "sk.orientacao",
          "nome": "Orientação e duração do dia",
          "o_que_calcula": "Declinação, duração do dia e altura do sol ao meio-dia por latitude e mês.",
          "formula": {
            "texto": "δ = 23,45·sen(360·(284 + n) ÷ 365); duração = 2·ω_s ÷ 15",
            "variaveis": [
              {
                "simbolo": "n",
                "significado": "dia do ano",
                "unidade": "—"
              },
              {
                "simbolo": "ω_s",
                "significado": "ângulo do pôr do sol",
                "unidade": "°"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "Duffie & Beckman",
              "edicao": "4ª ed., 2013",
              "item": "geometria solar",
              "como_e_usada": "Fórmulas astronômicas."
            },
            {
              "codigo": "ABNT NBR 15220",
              "edicao": "a conferir",
              "item": "parte 3",
              "como_e_usada": "Zona bioclimática da cidade (tabela própria do SustainKit)."
            }
          ],
          "limites_de_validade": "Astronomia exata o bastante para estudo.",
          "fonte_de_dados": "Latitude da cidade.",
          "status": "conforme",
          "o_que_falta": "Conferir as zonas da tabela CIDADES com a revisão vigente da NBR 15220.",
          "onde": "SustainKit_Definitivo.html · SK.ori"
        },
        {
          "id": "sk.agro",
          "nome": "Agro solar",
          "o_que_calcula": "Energia diária das cargas do campo, potência solar e bateria.",
          "formula": {
            "texto": "kWh = Σ P·h ÷ 1000; P_min = kWh ÷ (HSP × PR); bateria = regra única com horas = dias de autonomia × 24 e o DoD da base",
            "variaveis": [
              {
                "simbolo": "0,75",
                "significado": "rendimento adotado",
                "unidade": "—"
              },
              {
                "simbolo": "2",
                "significado": "dias de autonomia",
                "unidade": "dias"
              }
            ]
          },
          "premissas": [
            "pv.pr",
            "bateria.dod",
            "bateria.rendimento",
            "agro.autonomia_dias"
          ],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Premissas próprias do módulo agro."
            }
          ],
          "limites_de_validade": "Cargas típicas, não medidas.",
          "fonte_de_dados": "Lista de cargas do SustainKit.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: PR, DoD, rendimento e dias de autonomia vêm da base (antes 0,75, 0,80 e × 1,2 fixos). Falta: cargas medidas no lugar.",
          "onde": "SustainKit_Definitivo.html · SK.agro"
        },
        {
          "id": "sk.residuos",
          "nome": "Resíduos do SustainKit",
          "o_que_calcula": "Total e parte desviada do aterro.",
          "formula": {
            "texto": "desvio = Σ kg em rotas fora do aterro ÷ Σ kg",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "Lei 12.305/2010",
              "edicao": "2010",
              "item": "art. 9º",
              "como_e_usada": "Ordem de prioridade: não gerar, reduzir, reutilizar, reciclar, tratar e só então dispor."
            }
          ],
          "limites_de_validade": "Mesmas unidades da Economia circular.",
          "fonte_de_dados": "Lista de resíduos.",
          "status": "conforme",
          "o_que_falta": "",
          "onde": "SustainKit_Definitivo.html · SK.residuos"
        },
        {
          "id": "sk.materiais",
          "nome": "Materiais por zona e custo de acabamento",
          "o_que_calcula": "Sugere materiais por zona bioclimática e soma o custo dos acabamentos.",
          "formula": {
            "texto": "custo = (material + base) × área + ferramentas + mão de obra × área",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 15220",
              "edicao": "a conferir",
              "item": "parte 3",
              "como_e_usada": "Zona bioclimática."
            },
            {
              "codigo": "ABNT NBR 15575",
              "edicao": "2021",
              "item": "partes 4 e 5",
              "como_e_usada": "Desempenho de paredes e coberturas; só citada."
            }
          ],
          "limites_de_validade": "Custos de referência sem data nem fonte de preço.",
          "fonte_de_dados": "Tabelas MAT_ZONA e ACABAMENTOS.",
          "status": "só citado",
          "o_que_falta": "Engenheiro confere se as sugestões por zona atendem aos limites de transmitância e absortância da NBR 15575; custos precisam de fonte e data.",
          "onde": "SustainKit_Definitivo.html · SK.acab, MAT_ZONA"
        }
      ]
    },
    "solar": {
      "nome": "Energia solar",
      "resumo": "Potencial do lugar, tamanho do sistema, bateria e economia (painel.html, solarCalc).",
      "calculos": [
        {
          "id": "solar.irradiacao",
          "nome": "Sol do lugar",
          "o_que_calcula": "Irradiação média de cada mês: medida por satélite (NASA POWER, no servidor) ou estimada pela latitude.",
          "formula": {
            "texto": "H = H0 × KT; H0 = (24 ÷ π)·Gsc·E·[cos φ·cos δ·sen ωs + ωs·sen φ·sen δ]",
            "variaveis": [
              {
                "simbolo": "H",
                "significado": "irradiação diária no plano horizontal",
                "unidade": "kWh/m²·dia"
              },
              {
                "simbolo": "H0",
                "significado": "irradiação fora da atmosfera",
                "unidade": "kWh/m²·dia"
              },
              {
                "simbolo": "KT",
                "significado": "índice de claridade",
                "unidade": "—"
              },
              {
                "simbolo": "Gsc",
                "significado": "constante solar (1,367)",
                "unidade": "kW/m²"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "Duffie & Beckman",
              "edicao": "4ª ed., 2013",
              "item": "radiação extraterrestre média do mês",
              "como_e_usada": "Fórmula usada quando a base de satélite não responde."
            },
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "A irradiação vem de base pública; não há NBR que a defina."
            }
          ],
          "limites_de_validade": "Plano horizontal. KT de 0,5 é só um exemplo.",
          "fonte_de_dados": "NASA POWER (média de longo prazo) guardada no servidor (gis.py).",
          "status": "conforme",
          "o_que_falta": "",
          "onde": "painel.html · solMensal(), carregarGisSolar()"
        },
        {
          "id": "solar.dimensionamento",
          "nome": "Potência, placas e área",
          "o_que_calcula": "Potência para cobrir a parte desejada do consumo, número de placas e área de telhado.",
          "formula": {
            "texto": "kWp = consumo × cobertura ÷ Σ(H_mês × fator do plano_mês × dias × PR); fator do plano pelo modelo isotrópico (Liu e Jordan; difusa pela correlação de Erbs); placas = ⌈kWp × 1000 ÷ W_placa⌉",
            "variaveis": [
              {
                "simbolo": "PR",
                "significado": "rendimento global",
                "unidade": "—"
              },
              {
                "simbolo": "W_placa",
                "significado": "potência de cada placa",
                "unidade": "W"
              }
            ]
          },
          "premissas": [
            "pv.pr",
            "solar.albedo"
          ],
          "normas": [
            {
              "codigo": "IEC 61724-1",
              "edicao": "2021",
              "item": "definição do PR",
              "como_e_usada": "O PR inclui temperatura, sujeira, cabos e inversor."
            },
            {
              "codigo": "ABNT NBR 16690",
              "edicao": "2019",
              "item": "requisitos de projeto do arranjo",
              "como_e_usada": "Citada na tela; a parte elétrica (strings, cabos, proteções) não é calculada."
            },
            {
              "codigo": "ABNT NBR 16149",
              "edicao": "2013",
              "item": "interface com a rede",
              "como_e_usada": "Citada; vale para o inversor escolhido."
            }
          ],
          "limites_de_validade": "Plano das placas pelo modelo isotrópico com a inclinação e a orientação digitadas ou do telhado do Planejador; plano deitado dá o mesmo que antes.",
          "fonte_de_dados": "Consumo do Carbono ou do Início; irradiação do servidor.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: irradiação levada ao plano das placas (modelo isotrópico) com o telhado do Planejador. Falta (engenheiro): projeto elétrico pela NBR 16690 — strings na menor temperatura, cabos CC e proteções (adequação 20).",
          "onde": "sistema/physis-solar.js · calcular(), entradas(); sistema/physis-calc-comum.js · fatorPlano()"
        },
        {
          "id": "solar.economia",
          "nome": "Economia em R$",
          "o_que_calcula": "Quanto a energia gerada economiza por ano.",
          "formula": {
            "texto": "mês a mês: autoconsumo = min(geração × parte usada na hora, consumo); injetada = geração − autoconsumo; créditos abatem o consumo da rede; a energia compensada paga pct(ano) × Fio B (Lei 14.300, art. 27); conta com solar ≥ custo de disponibilidade; economia = conta sem solar − conta com solar",
            "variaveis": [
              {
                "simbolo": "tarifa",
                "significado": "preço da energia",
                "unidade": "R$/kWh"
              }
            ]
          },
          "premissas": [
            "solar.fio_b_escala",
            "tarifa.custo_disponibilidade"
          ],
          "normas": [
            {
              "codigo": "Lei 14.300/2022",
              "edicao": "2022",
              "item": "arts. 17 e 27",
              "como_e_usada": "A compensação da energia injetada paga parte do uso da rede (Fio B) numa escala que sobe ano a ano; a conta atual ignora isso."
            },
            {
              "codigo": "REN ANEEL 1.059/2023",
              "edicao": "2023",
              "item": "faturamento da micro e minigeração",
              "como_e_usada": "Regras de compensação."
            },
            {
              "codigo": "REN ANEEL 1.000/2021",
              "edicao": "2021",
              "item": "custo de disponibilidade",
              "como_e_usada": "A conta mínima continua sendo cobrada."
            }
          ],
          "limites_de_validade": "Com 100% de autoconsumo dá a conta antiga (geração × tarifa). Créditos que sobram não viram dinheiro; tarifa branca e geração remota não são tratadas; o retorno usa a economia do 1º ano.",
          "fonte_de_dados": "Tarifa, parte autoconsumida, Fio B, tipo de ligação e ano informados pela pessoa; escala do Fio B e custo de disponibilidade da base de premissas.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: autoconsumo e energia injetada separados, Fio B pela escala do art. 27 e custo de disponibilidade. Falta: engenheiro conferir os percentuais na lei e a regra da ANEEL depois de 2028 (premissas marcadas 'conferir').",
          "onde": "sistema/physis-solar.js · calcular(); sistema/physis-calc-comum.js · economiaSolar()"
        },
        {
          "id": "solar.bateria",
          "nome": "Bateria",
          "o_que_calcula": "Energia da bateria para as horas de autonomia.",
          "formula": {
            "texto": "E = consumo diário × horas ÷ 24 ÷ DoD ÷ rendimento de ida e volta (regra única: plataforma, SustainKit e agro)",
            "variaveis": [
              {
                "simbolo": "DoD",
                "significado": "profundidade de descarga (lítio 0,9; AGM 0,5)",
                "unidade": "—"
              },
              {
                "simbolo": "0,95",
                "significado": "rendimento do inversor e da bateria",
                "unidade": "—"
              }
            ]
          },
          "premissas": [
            "bateria.dod",
            "bateria.rendimento"
          ],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Não há NBR de dimensionamento de banco de baterias."
            },
            {
              "codigo": "IEC 62619",
              "edicao": "2022",
              "item": "segurança de baterias de lítio",
              "como_e_usada": "Citada no Planejador para abrigo e segurança."
            }
          ],
          "limites_de_validade": "Carga média, sem pico nem perfil por hora.",
          "fonte_de_dados": "Consumo anual.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: uma regra só (÷ rendimento 0,95 da base) na plataforma e no SustainKit; a margem de 1,2 saiu. Falta: perfil por hora quando houver medição; conferir o rendimento na folha de dados.",
          "onde": "painel.html · solarCalc() bat"
        }
      ]
    },
    "avac": {
      "nome": "AVAC e térmico",
      "resumo": "Porta da planilha PHYSIS_AVAC-5 (sistema/physis-avac.js) e carga térmica por ambiente (sistema/physis-cargatermica.js).",
      "calculos": [
        {
          "id": "avac.carga_termica",
          "nome": "Carga térmica por ambiente",
          "o_que_calcula": "Carga de resfriamento sensível e latente hora a hora (8 h às 18 h) e pico por ambiente e do conjunto.",
          "formula": {
            "texto": "Q = Σ U·A·ΔT_sol-ar (paredes e coberturas, com atraso) + vidros (A·FS·I + U·A·ΔT) + pessoas + iluminação + equipamentos + infiltração + ar externo (1,23·V·ΔT e 3010·V·Δw)",
            "variaveis": [
              {
                "simbolo": "U",
                "significado": "transmitância",
                "unidade": "W/m²K"
              },
              {
                "simbolo": "FS",
                "significado": "fator solar do vidro",
                "unidade": "—"
              },
              {
                "simbolo": "V",
                "significado": "vazão de ar",
                "unidade": "L/s"
              },
              {
                "simbolo": "Δw",
                "significado": "diferença de umidade",
                "unidade": "kg/kg"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 16401-1",
              "edicao": "2008",
              "item": "cálculo da carga térmica; condições externas (anexo)",
              "como_e_usada": "Caminho de cálculo seguido; as tabelas foram lembradas e estão marcadas 'verificar'."
            },
            {
              "codigo": "ABNT NBR 16401-2",
              "edicao": "2008",
              "item": "parâmetros de conforto",
              "como_e_usada": "Interior 24 °C e 50% de umidade."
            },
            {
              "codigo": "ABNT NBR 16401-3",
              "edicao": "2008",
              "item": "vazão eficaz de ar externo",
              "como_e_usada": "Vazão = Rp × pessoas + Ra × área."
            },
            {
              "codigo": "ABNT NBR 15220",
              "edicao": "a conferir",
              "item": "absortância e propriedades térmicas",
              "como_e_usada": "Ordem de grandeza das propriedades dos materiais."
            },
            {
              "codigo": "ASHRAE Handbook Fundamentals",
              "edicao": "a conferir",
              "item": "carga térmica e céu claro",
              "como_e_usada": "Método de referência das fórmulas."
            }
          ],
          "limites_de_validade": "Verão, dia 21 do mês; céu claro; perfil das 8 às 18 h.",
          "fonte_de_dados": "Tabelas do próprio módulo (DADOS) e equipamentos de physis-equipamentos.json.",
          "status": "simplificado",
          "o_que_falta": "Engenheiro confere as tabelas lembradas (condições externas por cidade, calor de pessoas, Rp e Ra) contra a norma vigente e tira o 'verificar'.",
          "onde": "sistema/physis-cargatermica.js · CARGA_TERMICA.calcular()"
        },
        {
          "id": "avac.ar_condicionado",
          "nome": "Ar-condicionado por área",
          "o_que_calcula": "Capacidade de cada ambiente por m² por TR, padronizada na lista comercial de BTU/h, e carga elétrica.",
          "formula": {
            "texto": "Com carga térmica levada da subaba Carga térmica: BTU/h = carga de projeto (NBR 16401-1) → próximo valor comercial; sem ela, triagem: BTU/h = área ÷ (m²/TR) × 12.000; kWt = TR × 3,517; kWe = kWt ÷ COP",
            "variaveis": [
              {
                "simbolo": "m²/TR",
                "significado": "área atendida por TR",
                "unidade": "m²"
              },
              {
                "simbolo": "COP",
                "significado": "coeficiente de desempenho",
                "unidade": "—"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 16401-1",
              "edicao": "2008",
              "item": "carga térmica",
              "como_e_usada": "A norma pede cálculo de carga térmica; a regra de m²/TR é só triagem."
            }
          ],
          "limites_de_validade": "Triagem da planilha; não substitui a carga térmica.",
          "fonte_de_dados": "Tipologias e ambientes informados.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: o botão 'Levar para o dimensionamento do ar-condicionado' passa a carga de cada ambiente (com confirmação e desfazer) e a tabela mostra a fonte 'Carga térmica (NBR 16401-1)'; m²/TR fica como triagem. Falta: carga térmica de todos os ambientes.",
          "onde": "sistema/physis-avac.js · calcular(), telaLevarCargas(), aplicarCargas()"
        },
        {
          "id": "avac.ventilacao",
          "nome": "Ventilação e exaustão",
          "o_que_calcula": "Vazões de banheiros, depósito de lixo, garagem e outros ambientes.",
          "formula": {
            "texto": "banheiro = vazão fixa ou área × pé-direito × trocas/h; garagem = maior entre trocas/h, L/s·m² e m³/h por vaga",
            "variaveis": [
              {
                "simbolo": "trocas/h",
                "significado": "renovações por hora",
                "unidade": "1/h"
              }
            ]
          },
          "premissas": [
            "avac.exaustao"
          ],
          "normas": [
            {
              "codigo": "ABNT NBR 16401-3",
              "edicao": "2008",
              "item": "vazões de ar externo",
              "como_e_usada": "Vale para ambientes ocupados; banheiro, lixo e garagem seguem o código de obras."
            },
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Exaustão de banheiro, lixo e garagem não tem NBR de vazão; valores da planilha (premissa Physis) e do código de obras do município."
            }
          ],
          "limites_de_validade": "Valores típicos da planilha.",
          "fonte_de_dados": "Planilha PHYSIS_AVAC-5.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: vazões e trocas de partida lidas da base de premissas. Falta: conferir com o código de obras do município.",
          "onde": "sistema/physis-avac.js · calcular()"
        },
        {
          "id": "avac.pressurizacao",
          "nome": "Pressurização de escada",
          "o_que_calcula": "Vazão de ar para manter a escada pressurizada e força para abrir a porta.",
          "formula": {
            "texto": "Q_vaz = 0,827·A·ΔP^0,5; Q_ab = v·A_porta·n; Q = (Q_vaz + Q_ab) × fator; F = F_fechador + W·A·ΔP ÷ (2·(W − 0,075))",
            "variaveis": [
              {
                "simbolo": "ΔP",
                "significado": "diferença de pressão",
                "unidade": "Pa"
              },
              {
                "simbolo": "A",
                "significado": "área de frestas",
                "unidade": "m²"
              },
              {
                "simbolo": "v",
                "significado": "velocidade na porta aberta",
                "unidade": "m/s"
              },
              {
                "simbolo": "W",
                "significado": "largura da porta",
                "unidade": "m"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 14880",
              "edicao": "a conferir",
              "item": "vazão de projeto e força na porta",
              "como_e_usada": "Mesma forma de cálculo; o limite de 110 N e os valores de ΔP e portas abertas são da planilha."
            }
          ],
          "limites_de_validade": "Uma escada; sem efeito chaminé nem vento.",
          "fonte_de_dados": "Planilha PHYSIS_AVAC-5.",
          "status": "simplificado",
          "o_que_falta": "Engenheiro confere na NBR 14880 e na Instrução Técnica do Corpo de Bombeiros do estado: faixa de ΔP, número de portas abertas, velocidade e força máxima. Depois pôr os valores na base de premissas.",
          "onde": "sistema/physis-avac.js · calcular()"
        },
        {
          "id": "avac.aquecimento_solar",
          "nome": "Aquecimento solar de água",
          "o_que_calcula": "Consumo de água quente, energia, área de coletores, reservatório e apoio.",
          "formula": {
            "texto": "E = V·4,186·ΔT ÷ 3600; parcela solar = E × fração; produção do mês = eficiência do coletor (ENCE Inmetro) × irradiação do lugar no plano do coletor; área = parcela ÷ produção do pior mês",
            "variaveis": [
              {
                "simbolo": "V",
                "significado": "consumo de água quente",
                "unidade": "L/dia"
              },
              {
                "simbolo": "ΔT",
                "significado": "temperatura de consumo − água fria",
                "unidade": "K"
              },
              {
                "simbolo": "produção",
                "significado": "energia do coletor",
                "unidade": "kWh/m²·dia"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 15569",
              "edicao": "2020",
              "item": "dimensionamento (método simplificado)",
              "como_e_usada": "Segue o roteiro de demanda, fração solar e volume; com produção fixa do coletor."
            }
          ],
          "limites_de_validade": "Sol do lugar mês a mês (base do servidor, a mesma da aba Energia solar); sem a eficiência, vale a produção informada (sem valor fixo).",
          "fonte_de_dados": "Eficiência da etiqueta Inmetro informada; irradiação mensal do servidor (NASA POWER) ou estimativa pela latitude.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: produção fixa de 1,8 kWh/m²·dia trocada pela eficiência da ENCE × sol do lugar mês a mês, mostrando o pior mês. Falta: perdas do reservatório e da tubulação e a fração solar anual (NBR 15569), com conferência do engenheiro.",
          "onde": "sistema/physis-avac.js · calcular()"
        },
        {
          "id": "avac.piscina",
          "nome": "Aquecimento de piscina",
          "o_que_calcula": "Perdas por evaporação, convecção, radiação e paredes; potência de manutenção e de aquecimento inicial.",
          "formula": {
            "texto": "m_evap = (25 + 19·v)·A·(w_s − w_a); q_evap = m·2257 ÷ 3600; q_conv = (5,7 + 3,8·v)·A·ΔT; q_rad = ε·σ·A·(T_w⁴ − T_céu⁴)",
            "variaveis": [
              {
                "simbolo": "v",
                "significado": "velocidade do vento",
                "unidade": "m/s"
              },
              {
                "simbolo": "w",
                "significado": "umidade absoluta",
                "unidade": "kg/kg"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ASHRAE Handbook Fundamentals",
              "edicao": "a conferir",
              "item": "evaporação de superfícies livres",
              "como_e_usada": "Fórmula de evaporação."
            },
            {
              "codigo": "ABNT NBR 10339",
              "edicao": "2018",
              "item": "projeto de piscinas",
              "como_e_usada": "Não traz carga térmica; só citada."
            },
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Não há NBR de carga térmica de piscina."
            }
          ],
          "limites_de_validade": "Regime permanente com médias; sem sol sobre a água.",
          "fonte_de_dados": "Planilha PHYSIS_AVAC-5.",
          "status": "conforme",
          "o_que_falta": "Considerar o ganho solar na piscina descoberta (reduz a potência).",
          "onde": "sistema/physis-avac.js · calcular()"
        },
        {
          "id": "avac.dutos",
          "nome": "Dutos e ventiladores",
          "o_que_calcula": "Diâmetro, perda de carga do trecho crítico, duto retangular equivalente e motor.",
          "formula": {
            "texto": "D = √(4Q ÷ πv); f por Swamee-Jain; Δp = f·L÷D·ρv²÷2; De = 1,3·(ab)^0,625 ÷ (a+b)^0,25; P = Q·Δp ÷ η",
            "variaveis": [
              {
                "simbolo": "v",
                "significado": "velocidade",
                "unidade": "m/s"
              },
              {
                "simbolo": "f",
                "significado": "fator de atrito",
                "unidade": "—"
              },
              {
                "simbolo": "η",
                "significado": "rendimento do ventilador",
                "unidade": "—"
              }
            ]
          },
          "premissas": [
            "avac.velocidade_dutos"
          ],
          "normas": [
            {
              "codigo": "ABNT NBR 16401-1",
              "edicao": "2008",
              "item": "dutos",
              "como_e_usada": "Velocidades e ruído; os limites por tipo de duto vêm da planilha."
            },
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Darcy-Weisbach, Swamee-Jain e Huebscher são métodos de mecânica dos fluidos."
            }
          ],
          "limites_de_validade": "Ar padrão corrigido pela altitude e temperatura.",
          "fonte_de_dados": "Planilha PHYSIS_AVAC-5.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: limites de velocidade por tipo de duto lidos da base. Falta: conferir na NBR 16401-1 (marcado [CONFERIR NA NORMA]).",
          "onde": "sistema/physis-avac.js · calcular()"
        },
        {
          "id": "avac.quadro",
          "nome": "Quadro elétrico do AVAC",
          "o_que_calcula": "Corrente, disjuntor, seção por capacidade, queda de tensão, curto-circuito e seccionamento de cada circuito e do alimentador.",
          "formula": {
            "texto": "Ib = kVA·1000 ÷ (√3·V); S ≥ maior entre capacidade (Iz·FCT·FCA ≥ In), queda (ΔV ≤ limite), curto (S ≥ √(I²t) ÷ k) e seccionamento (L ≤ Lmax); PE pela regra de seções",
            "variaveis": [
              {
                "simbolo": "Iz",
                "significado": "capacidade de condução",
                "unidade": "A"
              },
              {
                "simbolo": "FCT",
                "significado": "fator de temperatura",
                "unidade": "—"
              },
              {
                "simbolo": "k",
                "significado": "constante do condutor (115 cobre/PVC)",
                "unidade": "—"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 5410",
              "edicao": "2004 (versão corrigida 2008)",
              "item": "6.2.5 (capacidade), 6.2.7 (queda), 5.3.5 e 6.3 (curto), 5.1.2.2 (seccionamento), 6.4.3 (PE)",
              "como_e_usada": "Tabelas de cobre PVC 70 °C, método B1, fatores de temperatura, neutro reduzido e PE."
            }
          ],
          "limites_de_validade": "Só cobre com isolação PVC, método B1; FCA informado à mão.",
          "fonte_de_dados": "Planilha PHYSIS_AVAC-5.",
          "status": "simplificado",
          "o_que_falta": "Engenheiro confere tabelas e limites com a edição vigente; acrescentar outros métodos de instalação (B2, C, D), isolação EPR/XLPE e o cálculo do FCA por agrupamento.",
          "onde": "sistema/physis-avac.js · calcular()"
        }
      ]
    },
    "turbinas": {
      "nome": "Turbinas",
      "resumo": "Microturbinas de água e turbinas eólicas pequenas (sistema/physis-turbinas.js).",
      "calculos": [
        {
          "id": "turb.hidraulica",
          "nome": "Potência da água",
          "o_que_calcula": "Potência e energia por ano de cada microturbina, descontando a perda na tubulação.",
          "formula": {
            "texto": "P = ρ·g·Q·H_líq·η; H_líq = H_bruta − h_f; h_f por Darcy-Weisbach (Swamee-Jain) ou Hazen-Williams",
            "variaveis": [
              {
                "simbolo": "ρ",
                "significado": "densidade da água (1000)",
                "unidade": "kg/m³"
              },
              {
                "simbolo": "Q",
                "significado": "vazão",
                "unidade": "m³/s"
              },
              {
                "simbolo": "H",
                "significado": "queda",
                "unidade": "m"
              },
              {
                "simbolo": "η",
                "significado": "eficiência do conjunto",
                "unidade": "—"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Fórmula da física; não há NBR para microturbina."
            },
            {
              "codigo": "IEC 61116",
              "edicao": "1992",
              "item": "equipamentos de pequenas centrais",
              "como_e_usada": "Referência para escolher e ensaiar o equipamento."
            },
            {
              "codigo": "Lei 9.433/1997",
              "edicao": "1997",
              "item": "outorga",
              "como_e_usada": "Usar água de rio ou nascente pode pedir outorga."
            },
            {
              "codigo": "REN ANEEL 1.059/2023",
              "edicao": "2023",
              "item": "conexão",
              "como_e_usada": "Para injetar na rede."
            }
          ],
          "limites_de_validade": "Faixas de tipo de turbina são de literatura (verificar com o fabricante).",
          "fonte_de_dados": "Vazão e queda informadas; vazão mensal quando houver.",
          "status": "conforme",
          "o_que_falta": "Feito em 15/11/2026: aviso de outorga (Lei 9.433/1997) e vazão ecológica, que sai da vazão disponível quando informada. Falta: buscar a vazão ecológica do órgão gestor.",
          "onde": "sistema/physis-turbinas.js · hidraulica(), eolica() (espelho physis_hub/vento.py)"
        },
        {
          "id": "turb.eolica",
          "nome": "Energia do vento",
          "o_que_calcula": "Energia anual de uma turbina pequena com o vento do lugar (distribuição de Weibull) e a curva de potência.",
          "formula": {
            "texto": "v_cubo = v_ref·(h ÷ h_ref)^α; P(v) = ½·ρ·A·v³·Cp (até a nominal); E = horas × ∫P(v)·f(v)dv",
            "variaveis": [
              {
                "simbolo": "α",
                "significado": "expoente do terreno",
                "unidade": "—"
              },
              {
                "simbolo": "Cp",
                "significado": "coeficiente de potência (≤ 0,593)",
                "unidade": "—"
              },
              {
                "simbolo": "k, c",
                "significado": "parâmetros de Weibull",
                "unidade": "—, m/s"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "IEC 61400-2",
              "edicao": "2013",
              "item": "turbinas pequenas",
              "como_e_usada": "Classe e segurança da turbina."
            },
            {
              "codigo": "IEC 61400-12-1",
              "edicao": "2022",
              "item": "curva de potência",
              "como_e_usada": "A curva usada é genérica; a certificada vem deste ensaio."
            },
            {
              "codigo": "ABNT NBR 10151",
              "edicao": "2019",
              "item": "ruído em áreas habitadas",
              "como_e_usada": "Conferir o ruído na distância dos vizinhos."
            }
          ],
          "limites_de_validade": "Vento médio de base pública; k = 2 se não houver medição.",
          "fonte_de_dados": "Base GIS de vento (servidor) ou medição.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: a curva de potência do fabricante (IEC 61400-12-1), quando digitada, substitui o modelo por Cp. Falta: correção da curva pela densidade do ar do lugar.",
          "onde": "sistema/physis-turbinas.js · hidraulica(), eolica() (espelho physis_hub/vento.py)"
        }
      ]
    },
    "agua": {
      "nome": "Qualidade da água",
      "resumo": "Eletrodo de pH, diferença de pH, vazamento, filtro e bomba. Nenhum limite vem de fábrica.",
      "calculos": [
        {
          "id": "agua.ph_eletrodo",
          "nome": "Saúde do eletrodo de pH",
          "o_que_calcula": "Inclinação (slope) e desvio da calibração, vida útil e tempo de resposta.",
          "formula": {
            "texto": "slope (%) = (ΔmV medido ÷ ΔmV teórico) × 100; aprovado se |slope − 100| ≤ 5",
            "variaveis": [
              {
                "simbolo": "slope",
                "significado": "sensibilidade do eletrodo",
                "unidade": "%"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Boa prática de calibração de eletrodo de pH; não há NBR para a gestão do eletrodo."
            }
          ],
          "limites_de_validade": "Faixas do arquivo original da Physis.",
          "fonte_de_dados": "Calibrações registradas.",
          "status": "conforme",
          "o_que_falta": "",
          "onde": "physis_hub/ph_eletrodo.py e painel.html"
        },
        {
          "id": "agua.limites",
          "nome": "Limites de pH e alertas",
          "o_que_calcula": "Compara as leituras com os limites que quem opera informa.",
          "formula": {
            "texto": "alerta se leitura fora de [mínimo, máximo] do lugar",
            "variaveis": []
          },
          "premissas": [
            "agua.referencias_por_uso"
          ],
          "normas": [
            {
              "codigo": "Portaria GM/MS 888/2021",
              "edicao": "2021",
              "item": "padrão de potabilidade",
              "como_e_usada": "Referência para água de beber; o sistema não aplica sozinho."
            },
            {
              "codigo": "Resolução CONAMA 357/2005",
              "edicao": "2005",
              "item": "classes de água",
              "como_e_usada": "Referência para rio e lago."
            },
            {
              "codigo": "Resolução CONAMA 430/2011",
              "edicao": "2011",
              "item": "lançamento de efluentes",
              "como_e_usada": "Referência para efluente."
            },
            {
              "codigo": "ABNT NBR 13969",
              "edicao": "1997",
              "item": "reúso",
              "como_e_usada": "Referência para água de reúso."
            }
          ],
          "limites_de_validade": "Limite provisório não gera alerta (regra do sistema).",
          "fonte_de_dados": "Limites informados pela pessoa.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: faixa de referência por uso ao lado de cada limite; modo de teste (desligado por padrão, marcado 'teste — valores a conferir') que preenche os limites vazios pela referência e libera os alertas. Desligado, vale a regra 3. Falta: o engenheiro conferir as faixas e outros parâmetros (coliformes, DBO).",
          "onde": "painel.html · telaAgua(); physis_hub/agua.py"
        },
        {
          "id": "agua.vazamento",
          "nome": "Vazamento e bomba",
          "o_que_calcula": "Vazamento pela vazão da madrugada, sinais de filtro sujo e proteção da bomba pela corrente e tensão.",
          "formula": {
            "texto": "vazamento se vazão noturna > limite; atraso de mistura = volume do trecho ÷ vazão",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Regras de operação; limites informados por quem opera."
            }
          ],
          "limites_de_validade": "Depende dos limites do lugar.",
          "fonte_de_dados": "Leituras dos sensores.",
          "status": "conforme",
          "o_que_falta": "",
          "onde": "physis_hub/agua.py; painel.html anVazamento(), anBomba()"
        }
      ]
    },
    "sbn": {
      "nome": "SbN e viveiro",
      "resumo": "Seletor de plantas, espaços e agrofloresta, plano de plantio, viveiro e calendário.",
      "calculos": [
        {
          "id": "sbn.seletor",
          "nome": "Seletor de plantas",
          "o_que_calcula": "Filtra plantas por função, luz, bioma, solo, estrato, nativa, restauração de APP e exclui invasoras.",
          "formula": {
            "texto": "planta entra se atende a todos os filtros; ordem pelo número de funções",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "Lei 12.651/2012",
              "edicao": "2012",
              "item": "recomposição de APP",
              "como_e_usada": "Filtro 'restauração de APP' para escolher espécies."
            },
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Seleção por base de plantas da Physis; não é cálculo normativo."
            }
          ],
          "limites_de_validade": "Base de 234 plantas; bioma e solo vêm da localização.",
          "fonte_de_dados": "sistema/physis-plantas.json.",
          "status": "conforme",
          "o_que_falta": "Conferir a lista de espécies permitidas na recomposição com a norma estadual de restauração.",
          "onde": "painel.html · telaSbn()"
        },
        {
          "id": "sbn.plano",
          "nome": "Plano de plantio e quantidades",
          "o_que_calcula": "Soma as plantas por espaço e desenha o mapa do plano.",
          "formula": {
            "texto": "quantidade por espaço = Σ plantas escolhidas",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Contagem; o espaçamento vem das combinações da base."
            }
          ],
          "limites_de_validade": "Desenho esquemático, não é planta de projeto.",
          "fonte_de_dados": "Base de espaços (combinações A, B, C).",
          "status": "conforme",
          "o_que_falta": "",
          "onde": "painel.html · sbnMapa()"
        },
        {
          "id": "sbn.viveiro",
          "nome": "Viveiro e venda de mudas",
          "o_que_calcula": "Plano de produção e calendário do viveiro.",
          "formula": {
            "texto": "lotes por mês conforme o plano de produção",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "Lei 10.711/2003",
              "edicao": "2003",
              "item": "registro RENASEM",
              "como_e_usada": "Quem produz ou vende mudas precisa de registro; o sistema deve lembrar."
            }
          ],
          "limites_de_validade": "Plano de produção da base.",
          "fonte_de_dados": "physis-plantas.json (viveiro).",
          "status": "conforme",
          "o_que_falta": "",
          "onde": "painel.html · telaSbn() viveiro"
        },
        {
          "id": "sbn.jardim_chuva",
          "nome": "Jardim de chuva e wetland",
          "o_que_calcula": "Tamanho de jardim de chuva e de wetland para tratar ou infiltrar água.",
          "formula": {
            "texto": "a fazer",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 13969",
              "edicao": "1997",
              "item": "tratamento complementar",
              "como_e_usada": "Referência para wetland de efluente."
            },
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Jardim de chuva não tem NBR; usar o volume da drenagem do Planejador e o ensaio de infiltração."
            }
          ],
          "limites_de_validade": "—",
          "fonte_de_dados": "—",
          "status": "falta implementar",
          "o_que_falta": "Dimensionar pelo volume de chuva a reter (Planejador) e pela taxa de infiltração medida; wetland pela carga de esgoto e tempo de detenção. Precisa de engenheiro para fixar as taxas.",
          "onde": "módulo novo (physis-sbn.js, em construção)"
        }
      ]
    },
    "circular": {
      "nome": "Economia circular",
      "resumo": "Resíduos, rotas, classe, MTR, desvio do aterro e o que montar no lugar; mapa de destinos.",
      "calculos": [
        {
          "id": "rc.classe",
          "nome": "Classe do resíduo e rota permitida",
          "o_que_calcula": "Mostra a classe de cada resíduo e bloqueia rota proibida para perigoso.",
          "formula": {
            "texto": "classe I não pode ir para coleta pública, aterro comum nem compostagem",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 10004",
              "edicao": "2024",
              "item": "classificação (partes 1 e 2)",
              "como_e_usada": "Classes I, IIA e IIB da tela."
            },
            {
              "codigo": "ABNT NBR 10007",
              "edicao": "2004",
              "item": "amostragem",
              "como_e_usada": "Quando a classe depende de ensaio."
            },
            {
              "codigo": "Resolução CONAMA 307/2002",
              "edicao": "2002",
              "item": "classes A a D",
              "como_e_usada": "Entulho classe A."
            }
          ],
          "limites_de_validade": "Classe típica por tipo de resíduo; casos duvidosos pedem ensaio.",
          "fonte_de_dados": "Tabela RC_TIPOS da tela.",
          "status": "simplificado",
          "o_que_falta": "Engenheiro confere se as classes I, IIA e IIB continuam na NBR 10004:2024 e ajusta o rótulo.",
          "onde": "painel.html · RC_TIPOS, rcAlertas()"
        },
        {
          "id": "rc.desvio",
          "nome": "Desvio do aterro",
          "o_que_calcula": "Parte do resíduo que não vai para o aterro.",
          "formula": {
            "texto": "desvio = Σ kg em reúso, reciclagem, compostagem e logística reversa ÷ Σ kg",
            "variaveis": [
              {
                "simbolo": "kg",
                "significado": "massa por mês",
                "unidade": "kg/mês"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "Lei 12.305/2010",
              "edicao": "2010",
              "item": "art. 9º",
              "como_e_usada": "Ordem de prioridade."
            },
            {
              "codigo": "TRUE Zero Waste",
              "edicao": "a conferir",
              "item": "meta de desvio",
              "como_e_usada": "Meta de 90%."
            },
            {
              "codigo": "LEED v5",
              "edicao": "v5",
              "item": "resíduos",
              "como_e_usada": "Critério de desvio."
            }
          ],
          "limites_de_validade": "Massa informada, não pesada.",
          "fonte_de_dados": "Plano de resíduos.",
          "status": "conforme",
          "o_que_falta": "",
          "onde": "painel.html · rcResumo()"
        },
        {
          "id": "rc.mtr",
          "nome": "MTR",
          "o_que_calcula": "Quais resíduos precisam de Manifesto de Transporte a cada saída.",
          "formula": {
            "texto": "MTR se o destino é reciclagem, compostagem externa, incineração, aterro ou logística reversa",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "Portaria MMA 280/2020",
              "edicao": "2020",
              "item": "MTR nacional",
              "como_e_usada": "Emissão no SINIR."
            },
            {
              "codigo": "Lei 12.305/2010",
              "edicao": "2010",
              "item": "plano de gerenciamento",
              "como_e_usada": ""
            }
          ],
          "limites_de_validade": "Regra geral; o estado pode ter sistema próprio.",
          "fonte_de_dados": "Rotas do plano.",
          "status": "conforme",
          "o_que_falta": "Conferir se o estado usa sistema de MTR próprio.",
          "onde": "painel.html · RC_EXIGE_MTR"
        },
        {
          "id": "rc.produtos",
          "nome": "Produtos e equipamentos no lugar",
          "o_que_calcula": "Composto, biogás, biodiesel, filamento, agregado e o tamanho do que montar.",
          "formula": {
            "texto": "produto = kg × rendimento; biogás = kg × m³/kg; biodigestor ≈ kg/dia × 2 × 30 dias",
            "variaveis": [
              {
                "simbolo": "rendimento",
                "significado": "parte que vira produto",
                "unidade": "—"
              }
            ]
          },
          "premissas": [
            "residuos.rendimentos",
            "residuos.biogas_por_kg"
          ],
          "normas": [
            {
              "codigo": "Resolução CONAMA 481/2017",
              "edicao": "2017",
              "item": "compostagem",
              "como_e_usada": "Controle do processo de compostagem."
            },
            {
              "codigo": "ABNT NBR 15116",
              "edicao": "2021",
              "item": "agregado reciclado",
              "como_e_usada": "Agregado para uso não estrutural."
            },
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Rendimentos de literatura marcados como estimativa."
            }
          ],
          "limites_de_validade": "Estimativas para planejamento.",
          "fonte_de_dados": "Tabela RC_ROTAS.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: rendimentos e biogás por kg lidos da base de premissas. Falta: conferir as estimativas e os tamanhos de pátio e equipamentos.",
          "onde": "painel.html · RC_ROTAS, rcProduto()"
        },
        {
          "id": "rc.transporte",
          "nome": "Distância e CO₂ do transporte",
          "o_que_calcula": "Distância até cada destino e CO₂ do caminhão.",
          "formula": {
            "texto": "distância por haversine; CO₂ = t·km × fator ou viagens × L × 2,671 kgCO₂e/L",
            "variaveis": []
          },
          "premissas": [
            "combustivel.diesel"
          ],
          "normas": [
            {
              "codigo": "GHG Protocol",
              "edicao": "2004 / 2015",
              "item": "escopo 3, transporte",
              "como_e_usada": "Emissão do transporte de resíduos fica no escopo 3."
            }
          ],
          "limites_de_validade": "Linha reta, não pelo caminho.",
          "fonte_de_dados": "OpenStreetMap (servidor) e importação manual.",
          "status": "simplificado",
          "o_que_falta": "Aplicar fator de rota (linha reta → estrada) e conferir licença do destino.",
          "onde": "sistema/physis-circular-mapa.js; physis_hub/residuos_gis.py"
        },
        {
          "id": "rc.esgoto_biogas",
          "nome": "Esgoto e biogás",
          "o_que_calcula": "Volume do tanque séptico, filtro, área de infiltração, biodigestor, biogás, energia, reúso e lodo.",
          "formula": {
            "texto": "C = Σ N × C_uso; Lf = Σ N × Lf_uso; tanque séptico V = 1.000 + C × T + K × Lf (L); filtro anaeróbio = 1,6 × C × T (L); infiltração = C ÷ coeficiente do solo; biodigestor = (Nb × águas negras + resíduo) × 35 dias × 1,25; biogás = Nb × 0,04 + resíduo de cozinha × 0,1 (outros substratos: [MARCADOR]); energia = biogás × 6 kWh/m³; fogão = biogás ÷ 0,35 m³/h; reúso = efluente tratado",
            "variaveis": [
              {
                "simbolo": "N",
                "significado": "pessoas por tipo de uso",
                "unidade": "pessoas"
              },
              {
                "simbolo": "C",
                "significado": "contribuição de esgoto",
                "unidade": "L/dia"
              },
              {
                "simbolo": "Lf",
                "significado": "lodo fresco",
                "unidade": "L/dia"
              },
              {
                "simbolo": "T",
                "significado": "tempo de detenção",
                "unidade": "dia"
              },
              {
                "simbolo": "K",
                "significado": "taxa de acumulação de lodo",
                "unidade": "dia"
              },
              {
                "simbolo": "Nb",
                "significado": "pessoas-equivalentes no biodigestor",
                "unidade": "pessoas"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 7229",
              "edicao": "1993",
              "item": "tanque séptico: contribuição, detenção e acumulação de lodo",
              "como_e_usada": "Volume útil do tanque séptico; mesmos valores por tipo de uso do Planejador."
            },
            {
              "codigo": "ABNT NBR 13969",
              "edicao": "1997",
              "item": "filtro anaeróbio, infiltração e reúso",
              "como_e_usada": "Filtro, área de infiltração pelo coeficiente do solo e classes de reúso."
            },
            {
              "codigo": "ABNT NBR 17076",
              "edicao": "2024",
              "item": "sistemas de menor porte",
              "como_e_usada": "Pode ter substituído as duas acima; um engenheiro confere antes de usar os números em projeto."
            }
          ],
          "limites_de_validade": "Planejamento; prefere os números do Planejador, depois os do SustainKit; a estimativa usa a ocupação do Início e os resíduos do plano com a rota Biodigestor.",
          "fonte_de_dados": "localStorage physis-calc-esgoto e physis-calc-biogas (Planejador ou SustainKit) ou ocupação do Início, plano de resíduos e base de equipamentos (metano do biogás, áreas por pessoa).",
          "status": "simplificado",
          "o_que_falta": "Conferir a NBR 17076:2024; fator de biofertilizante [MARCADOR]; fator de metano do tratamento no Carbono [MARCADOR].",
          "onde": "painel.html · physisSaneamento() e physisBiogas() (cópia do bloco physis-calc-planejador do Planejador), ebAtual(), telaEsgotoBiogas()"
        }
      ]
    },
    "carbono": {
      "nome": "Carbono",
      "resumo": "Inventário dos escopos 1 e 2, emissões evitadas e caminho net zero (painel.html, carbCalc).",
      "calculos": [
        {
          "id": "carb.escopo1",
          "nome": "Escopo 1 (combustíveis)",
          "o_que_calcula": "Emissões de diesel, GLP e gás natural queimados no lugar.",
          "formula": {
            "texto": "E1 = Σ consumo × fator ÷ 1000",
            "variaveis": [
              {
                "simbolo": "fator",
                "significado": "diesel 2,671 kgCO₂e/L; GLP 2,939 kgCO₂e/kg; GN 1,999 kgCO₂e/m³",
                "unidade": "kgCO₂e por unidade"
              }
            ]
          },
          "premissas": [
            "combustivel.diesel",
            "combustivel.glp",
            "combustivel.gn"
          ],
          "normas": [
            {
              "codigo": "GHG Protocol",
              "edicao": "2004 / 2015",
              "item": "escopo 1",
              "como_e_usada": "Queima própria."
            },
            {
              "codigo": "ISO 14064-1",
              "edicao": "2018",
              "item": "emissões diretas",
              "como_e_usada": ""
            }
          ],
          "limites_de_validade": "Só CO₂e pelos fatores da base; sem fonte e ano dos fatores.",
          "fonte_de_dados": "Consumo informado.",
          "status": "simplificado",
          "o_que_falta": "Conferir a fonte e o ano dos fatores; separar a parte de biodiesel do diesel (CO₂ biogênico é informado à parte) e incluir CH₄ e N₂O com o GWP usado pelo Programa Brasileiro GHG Protocol.",
          "onde": "painel.html · carbCalc()"
        },
        {
          "id": "carb.escopo2",
          "nome": "Escopo 2 (eletricidade)",
          "o_que_calcula": "Emissões da energia comprada da rede.",
          "formula": {
            "texto": "E2 = kWh ÷ 1000 × fator SIN",
            "variaveis": [
              {
                "simbolo": "fator SIN",
                "significado": "fator médio da rede",
                "unidade": "tCO₂/MWh"
              }
            ]
          },
          "premissas": [
            "rede.fator_emissao"
          ],
          "normas": [
            {
              "codigo": "GHG Protocol",
              "edicao": "2004 / 2015",
              "item": "guia do escopo 2, abordagem por localização",
              "como_e_usada": "Fator médio da rede."
            },
            {
              "codigo": "Fator médio do SIN (MCTI)",
              "edicao": "por ano",
              "item": "fator anual",
              "como_e_usada": "Conferir o ano."
            }
          ],
          "limites_de_validade": "Fator de um ano só.",
          "fonte_de_dados": "Contas do Início ou valor informado.",
          "status": "simplificado",
          "o_que_falta": "Escolher o fator do ano do inventário (tabela por ano na base de premissas).",
          "onde": "painel.html · carbCalc()"
        },
        {
          "id": "carb.evitado_saldo",
          "nome": "Evitado e saldo net zero",
          "o_que_calcula": "Emissões evitadas pela solar e pelo biogás e o saldo até o net zero.",
          "formula": {
            "texto": "saldo = E1 + E2 − evitado(solar + biogás) − medidas",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "GHG Protocol",
              "edicao": "2004 / 2015",
              "item": "emissões evitadas",
              "como_e_usada": "Evitado é informado à parte, não é descontado do inventário."
            },
            {
              "codigo": "ISO 14068-1",
              "edicao": "2023",
              "item": "neutralidade",
              "como_e_usada": "Saldo zero só com redução real e remoções ou créditos."
            }
          ],
          "limites_de_validade": "Pode contar a solar duas vezes: se o kWh da rede já vem das contas (que já estão menores por causa da solar), descontar a solar de novo dá saldo menor que o real.",
          "fonte_de_dados": "Entradas da aba.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: inventário dos escopos 1 e 2 sem descontos; evitadas (solar, biogás, reciclagem) num quadro à parte; o saldo net zero só abate remoções e créditos (aba Carbono e SustainKit). Falta: fatores com ano e fonte (adequação 23).",
          "onde": "painel.html · carbCalc() saldo"
        },
        {
          "id": "carb.sbce",
          "nome": "Enquadramento no SBCE",
          "o_que_calcula": "Diz se a organização passa das faixas de relato e de metas.",
          "formula": {
            "texto": "relatar se ≥ 10 mil tCO₂e/ano; metas se ≥ 25 mil",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "Lei 15.042/2024",
              "edicao": "2024",
              "item": "faixas de enquadramento",
              "como_e_usada": "Texto informativo."
            }
          ],
          "limites_de_validade": "Informativo.",
          "fonte_de_dados": "Inventário da aba.",
          "status": "só citado",
          "o_que_falta": "Conferir a regulamentação do SBCE antes de mostrar como regra.",
          "onde": "painel.html · telaCarbono()"
        },
        {
          "id": "carb.esgoto",
          "nome": "Tratamento de esgoto no lugar (escopo 1)",
          "o_que_calcula": "Metano do tratamento de esgoto feito no próprio lugar.",
          "formula": {
            "texto": "CH₄ (kg/ano) = pessoas × DBO por pessoa × 365 × capacidade máxima de metano × fator de correção do tratamento; só entra com os fatores na base",
            "variaveis": [
              {
                "simbolo": "pessoas",
                "significado": "pessoas atendidas",
                "unidade": "pessoas"
              },
              {
                "simbolo": "DBO",
                "significado": "carga orgânica por pessoa",
                "unidade": "kg/dia"
              },
              {
                "simbolo": "fator de correção",
                "significado": "fração do metano possível que o tratamento gera",
                "unidade": "0 a 1"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "IPCC 2006",
              "edicao": "2006",
              "item": "vol. 5, cap. 6 (efluentes domésticos)",
              "como_e_usada": "Método do metano do tratamento de efluentes."
            },
            {
              "codigo": "GHG Protocol",
              "edicao": "2004 / 2015",
              "item": "escopo 1",
              "como_e_usada": "Fonte própria da organização."
            }
          ],
          "limites_de_validade": "Só com os fatores na base de fatores (efluentes); sem eles a linha fica [MARCADOR].",
          "fonte_de_dados": "Economia circular · Esgoto e biogás (pessoas e rota).",
          "status": "simplificado",
          "o_que_falta": "Incluir na base de fatores, com fonte, a DBO por pessoa, a capacidade máxima de metano e o fator de correção de cada rota [MARCADOR].",
          "onde": "sistema/physis-carbono.js · calcular() (esgoto_no_lugar); espelho physis_hub/carbono.py"
        },
        {
          "id": "carb.materiais_obra",
          "nome": "Materiais da obra (escopo 3, categoria 1)",
          "o_que_calcula": "Carbono incorporado das paredes e coberturas escolhidas.",
          "formula": {
            "texto": "tCO₂e = Σ área × carbono incorporado por m² ÷ 1000",
            "variaveis": [
              {
                "simbolo": "área",
                "significado": "área da composição",
                "unidade": "m²"
              },
              {
                "simbolo": "carbono por m²",
                "significado": "carbono incorporado, berço ao portão",
                "unidade": "kgCO₂e/m²"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "GHG Protocol",
              "edicao": "2004 / 2015",
              "item": "escopo 3, categoria 1",
              "como_e_usada": "Bens comprados; o carbono da obra entra no ano da compra."
            }
          ],
          "limites_de_validade": "Berço ao portão; composição sem valor por m² fica [MARCADOR].",
          "fonte_de_dados": "localStorage physis-calc-materiais (SustainKit ou Planejador).",
          "status": "simplificado",
          "o_que_falta": "Valor por m² de cada composição na base de materiais.",
          "onde": "sistema/physis-carbono.js · calcular() (materiais_obra); espelho physis_hub/carbono.py"
        }
      ]
    },
    "resiliencia": {
      "nome": "Resiliência climática",
      "resumo": "Previsão, chuva medida (CEMADEN), alertas do negócio e matriz de riscos.",
      "calculos": [
        {
          "id": "res.matriz",
          "nome": "Matriz de riscos",
          "o_que_calcula": "Nota de cada risco do lugar pela chance e pelo impacto.",
          "formula": {
            "texto": "nota = chance × impacto (1 a 5); alto ≥ 16; médio 9 a 15",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR ISO 31000",
              "edicao": "2018",
              "item": "avaliação de riscos",
              "como_e_usada": "Ideia de chance × consequência."
            },
            {
              "codigo": "ISO 14091",
              "edicao": "2021",
              "item": "riscos climáticos",
              "como_e_usada": "Lista de perigos do clima."
            }
          ],
          "limites_de_validade": "As escalas de 1 a 5 não têm descrição escrita.",
          "fonte_de_dados": "Escolha da pessoa.",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: cada nível de chance e impacto (1 a 5) tem o sentido escrito na tela. Falta: riscos com dados medidos do lugar.",
          "onde": "painel.html · telaResiliencia()"
        },
        {
          "id": "res.encosta",
          "nome": "Alerta de encosta pela chuva medida",
          "o_que_calcula": "Nível de atenção pela chuva acumulada em 24 h e 72 h no pluviômetro do CEMADEN.",
          "formula": {
            "texto": "atenção se 24 h ≥ 40 mm ou 72 h ≥ 60 mm; alerta se 24 h ≥ 80 mm ou 72 h ≥ 120 mm",
            "variaveis": [
              {
                "simbolo": "mm",
                "significado": "chuva acumulada",
                "unidade": "mm"
              }
            ]
          },
          "premissas": [
            "resiliencia.encosta_limiares"
          ],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Referência de planejamento da Physis; a Defesa Civil usa limiares próprios por bairro."
            },
            {
              "codigo": "ABNT NBR 11682",
              "edicao": "2009",
              "item": "encostas",
              "como_e_usada": "O estudo da encosta é feito no Planejador."
            }
          ],
          "limites_de_validade": "Limiar genérico; pode não valer para o bairro.",
          "fonte_de_dados": "CEMADEN (servidor).",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: limiares de 24 h e 72 h na base de premissas e trocáveis na tela pelos da Defesa Civil do município (os digitados valem no alerta). Falta: limiar por bairro e sensor de umidade do solo.",
          "onde": "painel.html · telaResiliencia() nivelEnc"
        },
        {
          "id": "res.alertas",
          "nome": "Alertas para o negócio",
          "o_que_calcula": "Cruza a atividade do Início com a previsão (geada no café, calor no gado, chuva na colheita).",
          "formula": {
            "texto": "alerta se a previsão passa do limiar da atividade (ex.: mínima < 3 °C para café)",
            "variaveis": []
          },
          "premissas": [
            "res.alertas_limiares"
          ],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Limiares agronômicos de literatura; não há norma."
            }
          ],
          "limites_de_validade": "Previsão de poucos dias.",
          "fonte_de_dados": "Open-Meteo, INMET (servidor).",
          "status": "simplificado",
          "o_que_falta": "Feito em 15/11/2026: limiares de cada atividade lidos da base de premissas. Falta: conferir com o técnico de cada atividade.",
          "onde": "painel.html · alertasAprendidos()"
        }
      ]
    },
    "zonas": {
      "nome": "Caixinha Physis IoT",
      "resumo": "Zonas de irrigação pela Caixinha e quadro elétrico do AVAC.",
      "calculos": [
        {
          "id": "zonas.rega",
          "nome": "Rega automática",
          "o_que_calcula": "Abre a válvula abaixo do limite de umidade do solo e fecha no limite + 5 pontos ou no tempo máximo.",
          "formula": {
            "texto": "abre se umidade < LIM; fecha se umidade ≥ LIM + 5 ou tempo ≥ TMAX",
            "variaveis": [
              {
                "simbolo": "LIM",
                "significado": "limite de umidade",
                "unidade": "%"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Regra de controle; limites informados por quem opera."
            },
            {
              "codigo": "FAO-56",
              "edicao": "1998",
              "item": "necessidade de água das culturas",
              "como_e_usada": "Referência para escolher o limite."
            }
          ],
          "limites_de_validade": "A segurança final fica no nó (ESPHome fecha sozinho).",
          "fonte_de_dados": "Sensores de umidade do solo.",
          "status": "conforme",
          "o_que_falta": "",
          "onde": "physis_hub/mqtt.py"
        },
        {
          "id": "zonas.quadro",
          "nome": "Quadro elétrico (do AVAC)",
          "o_que_calcula": "Mesmas contas do quadro do módulo AVAC.",
          "formula": {
            "texto": "ver AVAC: quadro elétrico",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ABNT NBR 5410",
              "edicao": "2004 (versão corrigida 2008)",
              "item": "dimensionamento de circuitos",
              "como_e_usada": "Ver o cálculo avac.quadro."
            }
          ],
          "limites_de_validade": "Ver AVAC.",
          "fonte_de_dados": "Ver AVAC.",
          "status": "simplificado",
          "o_que_falta": "Ver AVAC.",
          "onde": "sistema/physis-avac.js · telaQuadroEletrico()"
        }
      ]
    },
    "campo": {
      "nome": "Monitoramento verde",
      "resumo": "Umidade do solo, clima e irrigação do receptor V6.",
      "calculos": [
        {
          "id": "campo.irrigacao",
          "nome": "Quando irrigar",
          "o_que_calcula": "Velocidade com que o solo seca e chance de chuva decidem quando regar.",
          "formula": {
            "texto": "regressão da umidade por hora desde a última rega + chance de chuva do modelo",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "FAO-56",
              "edicao": "1998",
              "item": "balanço de água no solo",
              "como_e_usada": "Referência de método."
            },
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Modelo estatístico próprio, explicado na tela."
            }
          ],
          "limites_de_validade": "Precisa de dias de histórico.",
          "fonte_de_dados": "Sensores e previsão (servidor).",
          "status": "conforme",
          "o_que_falta": "Mostrar a evapotranspiração de referência da previsão como informação.",
          "onde": "physis_hub/aprendizado.py"
        }
      ]
    },
    "animais": {
      "nome": "Animais",
      "resumo": "Coleiras e comedouros: leitura e situação.",
      "calculos": [
        {
          "id": "animais.atividade",
          "nome": "Atividade e alimentação",
          "o_que_calcula": "Mostra a atividade das coleiras e o consumo dos comedouros.",
          "formula": {
            "texto": "leitura direta dos sensores",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Monitoramento; não há cálculo normativo."
            }
          ],
          "limites_de_validade": "—",
          "fonte_de_dados": "Coleiras e comedouros.",
          "status": "conforme",
          "o_que_falta": "Fase 2: índice de temperatura e umidade (estresse térmico do rebanho) com fonte de literatura.",
          "onde": "painel.html · telaAnimais()"
        }
      ]
    },
    "saude": {
      "nome": "Saúde",
      "resumo": "Caixinha de remédios e pulseira de alerta.",
      "calculos": [
        {
          "id": "saude.dose",
          "nome": "Situação da dose",
          "o_que_calcula": "Marca a dose como tomada, atrasada ou esquecida pelo horário.",
          "formula": {
            "texto": "atrasado se tomado depois da tolerância; esquecido se não tomado",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Regra de horário; não é cálculo de engenharia."
            },
            {
              "codigo": "Lei 13.709/2018",
              "edicao": "2018",
              "item": "art. 11",
              "como_e_usada": "Dado de saúde é sensível: consentimento e acesso só autorizado."
            }
          ],
          "limites_de_validade": "—",
          "fonte_de_dados": "Caixinha e pulseira.",
          "status": "conforme",
          "o_que_falta": "",
          "onde": "physis_hub/saude.py; sistema/physis-saude.js"
        }
      ]
    },
    "supervisao": {
      "nome": "SCADA",
      "resumo": "Supervisão de medições (sistema/physis-scada-demo.html).",
      "calculos": [
        {
          "id": "scada.linha_base",
          "nome": "Linha de base e economia medida",
          "o_que_calcula": "Compara o consumo medido com a linha de base para provar economia.",
          "formula": {
            "texto": "economia = linha de base ajustada − consumo medido",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ISO 50001",
              "edicao": "2018 (Amd 1:2024)",
              "item": "6.4 e 6.5",
              "como_e_usada": "Indicadores e linha de base."
            },
            {
              "codigo": "ISO 50006",
              "edicao": "2023",
              "item": "EnB e EnPI",
              "como_e_usada": "Ajuste da linha de base."
            },
            {
              "codigo": "ISO 50015",
              "edicao": "2014",
              "item": "M&V",
              "como_e_usada": "Plano de medição e verificação."
            },
            {
              "codigo": "IPMVP",
              "edicao": "a conferir",
              "item": "opções A a D",
              "como_e_usada": ""
            }
          ],
          "limites_de_validade": "Demonstração.",
          "fonte_de_dados": "Medidores (núcleo physis/1).",
          "status": "só citado",
          "o_que_falta": "Implementar o ajuste da linha de base por variável (graus-dia, produção) e o plano de M&V.",
          "onde": "sistema/physis-scada-demo.html"
        }
      ]
    },
    "resumo": {
      "nome": "Resumo",
      "resumo": "Junta os números dos outros módulos.",
      "sem_calculo": "Não faz conta própria: repete os resultados dos módulos, cada um com a sua metodologia.",
      "calculos": []
    },
    "certificacoes": {
      "nome": "Certificações",
      "resumo": "Gap analysis com redação própria (sistema/physis-certificacoes.json).",
      "calculos": [
        {
          "id": "cert.nota",
          "nome": "Nota de atendimento e maturidade",
          "o_que_calcula": "Percentual atendido, pontos e maturidade de 1 a 5.",
          "formula": {
            "texto": "nota = Σ valor ÷ critérios avaliados (atende 1; parcial 0,5; não 0); maturidade = 1 + round(nota × 4); LEED: nível pelos pontos",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ISO 14001",
              "edicao": "2015 (Amd 1:2024)",
              "item": "cláusulas 4 a 10",
              "como_e_usada": "Critérios por cláusula."
            },
            {
              "codigo": "ISO 50001",
              "edicao": "2018 (Amd 1:2024)",
              "item": "cláusulas 4 a 10",
              "como_e_usada": ""
            },
            {
              "codigo": "ISO 45001",
              "edicao": "2018",
              "item": "cláusulas 4 a 10",
              "como_e_usada": ""
            },
            {
              "codigo": "LEED v5",
              "edicao": "v5",
              "item": "créditos e pré-requisitos",
              "como_e_usada": "Pontos e níveis."
            },
            {
              "codigo": "EDGE",
              "edicao": "a conferir",
              "item": "20% abaixo da referência",
              "como_e_usada": ""
            },
            {
              "codigo": "Portaria Inmetro nº 309/2022",
              "edicao": "2022",
              "item": "INI-C e INI-R",
              "como_e_usada": ""
            },
            {
              "codigo": "Selo Casa Azul",
              "edicao": "a conferir",
              "item": "critérios",
              "como_e_usada": ""
            }
          ],
          "limites_de_validade": "Validação preliminar; a decisão é da certificadora.",
          "fonte_de_dados": "Base de certificações da Physis.",
          "status": "simplificado",
          "o_que_falta": "Pontos de cada crédito LEED v5 conferidos com o guia oficial; evidências automáticas ligadas às metodologias deste documento.",
          "onde": "painel.html · certAvalia()"
        },
        {
          "id": "cert.conformidade",
          "nome": "Conformidade legal",
          "o_que_calcula": "Quanto dos requisitos legais que se aplicam já está atendido.",
          "formula": {
            "texto": "atendimento = (conformes + 0,5 × parciais) ÷ itens que se aplicam × 100 (itens “não se aplica” e sem resposta ficam fora)",
            "variaveis": [
              {
                "simbolo": "conformes",
                "significado": "conformes",
                "unidade": "itens"
              },
              {
                "simbolo": "parciais",
                "significado": "parciais",
                "unidade": "itens"
              },
              {
                "simbolo": "itens que se aplicam",
                "significado": "itens que se aplicam",
                "unidade": "itens"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "Lei 12.305/2010",
              "edicao": "2010",
              "item": "plano de gerenciamento de resíduos e MTR",
              "como_e_usada": "Itens do tema Resíduos."
            },
            {
              "codigo": "Lei 9.433/1997",
              "edicao": "1997",
              "item": "outorga de uso da água",
              "como_e_usada": "Itens do tema Água e outorga."
            },
            {
              "codigo": "Lei 12.651/2012",
              "edicao": "2012",
              "item": "APP",
              "como_e_usada": "Tema APP e Código Florestal; o requisito ainda está como [MARCADOR]."
            }
          ],
          "limites_de_validade": "Levantamento assistido, não certificação; não substitui ART de profissional habilitado.",
          "fonte_de_dados": "Respostas da pessoa, por item: situação, evidência, prazo e responsável.",
          "status": "simplificado",
          "o_que_falta": "Redigir o requisito de APP e Código Florestal; conferir a vigência de cada NR e norma citada antes de emitir relatório.",
          "onde": "painel.html · confCalc() (mesma conta da antiga Tela do cliente, calcConformidade)"
        },
        {
          "id": "cert.ipmvp",
          "nome": "Economia medida (IPMVP)",
          "o_que_calcula": "Economia de energia e de água de uma medida, em kWh, m³, % e R$, e se a medição consegue comprová-la.",
          "formula": {
            "texto": "economia = (linha de base − período de relatório) ± ajustes rotineiros ± ajustes não rotineiros; % = economia ÷ (linha de base + ajustes); R$ = economia × tarifa; comprovável quando economia pretendida ÷ incerteza ≥ 3 (apertado entre 1 e 3); evitadas = kWh economizados ÷ 1000 × fator da rede do Carbono",
            "variaveis": [
              {
                "simbolo": "linha de base",
                "significado": "linha de base",
                "unidade": "kWh ou m³ (soma dos meses escolhidos)"
              },
              {
                "simbolo": "período de relatório",
                "significado": "período de relatório",
                "unidade": "kWh ou m³"
              },
              {
                "simbolo": "ajustes",
                "significado": "ajustes",
                "unidade": "kWh ou m³"
              },
              {
                "simbolo": "tarifa",
                "significado": "tarifa",
                "unidade": "R$/kWh ou R$/m³"
              },
              {
                "simbolo": "incerteza",
                "significado": "incerteza",
                "unidade": "%"
              },
              {
                "simbolo": "fator da rede",
                "significado": "fator da rede",
                "unidade": "tCO₂/MWh"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "IPMVP",
              "edicao": "a conferir",
              "item": "equação geral de economia e ajustes",
              "como_e_usada": "Economia como diferença entre linha de base e período de relatório, com ajustes rotineiros e não rotineiros."
            },
            {
              "codigo": "ISO 50015",
              "edicao": "2014",
              "item": "medição e verificação do desempenho energético",
              "como_e_usada": "Referência para o plano de medição, a incerteza e a verificação dos instrumentos."
            },
            {
              "codigo": "ISO 50006",
              "edicao": "2023",
              "item": "linha de base energética",
              "como_e_usada": "Escolha do período da linha de base."
            }
          ],
          "limites_de_validade": "Opção pela fatura (medição da instalação inteira); o ajuste sugerido pela produção supõe consumo proporcional à produção.",
          "fonte_de_dados": "Contas mensais de luz e água (Início), produção mensal (Gestão), ajustes, tarifas e instrumentos informados.",
          "status": "simplificado",
          "o_que_falta": "Ajuste rotineiro por regressão (clima e produção) em vez da proporção simples; incerteza calculada a partir dos instrumentos.",
          "onde": "painel.html · mvEconomia(), mvComprovavel(), mvStatusCal(), mvPlano()"
        }
      ]
    },
    "gestao": {
      "nome": "Gestão",
      "resumo": "Atividades, compras e investimentos, indicadores e custos.",
      "calculos": [
        {
          "id": "gestao.investimento",
          "nome": "Retorno do investimento",
          "o_que_calcula": "Retorno simples e descontado, VPL e TIR de cada medida.",
          "formula": {
            "texto": "fluxo mensal = ganho × (1 + f)^t; VPL = Σ fluxo ÷ (1 + i)^(t+1) − investimento; TIR por bisseção",
            "variaveis": [
              {
                "simbolo": "f",
                "significado": "reajuste mensal",
                "unidade": "—"
              },
              {
                "simbolo": "i",
                "significado": "taxa de desconto mensal",
                "unidade": "—"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Engenharia econômica padrão; a mesma conta no servidor (investimento.py) com teste."
            }
          ],
          "limites_de_validade": "Sem imposto, financiamento nem valor residual.",
          "fonte_de_dados": "Medidas informadas e a solar.",
          "status": "conforme",
          "o_que_falta": "",
          "onde": "painel.html · analiseInvest(); physis_hub/investimento.py"
        }
      ]
    },
    "cursos": {
      "nome": "Cursos",
      "resumo": "",
      "sem_calculo": "Não faz cálculo de engenharia.",
      "calculos": []
    },
    "pesquisa": {
      "nome": "Em desenvolvimento",
      "resumo": "",
      "sem_calculo": "Não faz cálculo de engenharia.",
      "calculos": []
    },
    "registro": {
      "nome": "Registro",
      "resumo": "",
      "sem_calculo": "Não faz cálculo de engenharia.",
      "calculos": []
    },
    "teste": {
      "nome": "Teste e diagnóstico",
      "resumo": "",
      "sem_calculo": "Não faz cálculo de engenharia.",
      "calculos": []
    },
    "geral": {
      "nome": "Toda a plataforma",
      "resumo": "Regras que valem para todas as telas.",
      "calculos": [
        {
          "id": "geral.acessibilidade",
          "nome": "Acessibilidade digital",
          "o_que_calcula": "Teclado, foco visível, nome em cada controle, contraste AA e alvos de 44 px.",
          "formula": {
            "texto": "contraste ≥ 4,5:1 (texto) e ≥ 3:1 (texto grande e componentes)",
            "variaveis": []
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "Lei 13.146/2015",
              "edicao": "2015",
              "item": "art. 63",
              "como_e_usada": "Sites devem ser acessíveis."
            },
            {
              "codigo": "ABNT NBR 17225",
              "edicao": "2025",
              "item": "requisitos",
              "como_e_usada": "Requisitos de acessibilidade web."
            },
            {
              "codigo": "WCAG 2.2",
              "edicao": "2023",
              "item": "nível AA",
              "como_e_usada": ""
            }
          ],
          "limites_de_validade": "—",
          "fonte_de_dados": "Testes de acessibilidade do repositório.",
          "status": "conforme",
          "o_que_falta": "",
          "onde": "physis-hub/web/painel.html; physis-preferencias.js"
        }
      ]
    },
    "secador": {
      "nome": "Secador solar",
      "resumo": "Secagem com o sol: balanço de massa, curva de secagem, tamanho do coletor e CO₂ evitado (versão 0.1, a homologar).",
      "calculos": [
        {
          "id": "sec.massa",
          "nome": "Balanço de massa do lote",
          "o_que_calcula": "Quanta água sai do produto, o peso na umidade desejada e o rendimento.",
          "formula": {
            "texto": "água a tirar = W₀ × (u₀ − u) ÷ (100 − u); peso na meta = matéria seca ÷ (1 − u/100); rendimento = W_fim ÷ W₀",
            "variaveis": [
              {
                "simbolo": "W₀",
                "significado": "peso no começo",
                "unidade": "kg"
              },
              {
                "simbolo": "u₀",
                "significado": "umidade no começo, base úmida",
                "unidade": "%"
              },
              {
                "simbolo": "u",
                "significado": "umidade desejada, base úmida",
                "unidade": "%"
              },
              {
                "simbolo": "W_fim",
                "significado": "peso no fim",
                "unidade": "kg"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "Embrapa Café",
              "edicao": "a conferir",
              "item": "umidade de armazenamento e temperatura da massa",
              "como_e_usada": "Referência da meta de umidade e da temperatura máxima do café (premissas marcadas verificar)."
            },
            {
              "codigo": "IN MAPA 8/2003",
              "edicao": "2003",
              "item": "classificação do café cru",
              "como_e_usada": "Referência para a umidade do café beneficiado; o limite exato é conferido no regulamento."
            }
          ],
          "limites_de_validade": "Umidades em base úmida; premissas por produto são de literatura geral, marcadas verificar.",
          "fonte_de_dados": "Lote informado (peso e umidade) e pesagens à mão ou célula de carga (PESO).",
          "status": "simplificado",
          "o_que_falta": "Medir a umidade real de cada produto no começo e no fim para trocar as premissas.",
          "onde": "sistema/physis-secador.js · aguaARemover(), pesoNaUmidade(), rendimento() (espelho: physis_hub/secador.py)"
        },
        {
          "id": "sec.curva",
          "nome": "Curva de secagem (modelo de Lewis)",
          "o_que_calcula": "Velocidade de secagem e hora prevista para chegar à umidade desejada.",
          "formula": {
            "texto": "W(t) = We + (W₀ − We) × e^(−k·t); com 3 ou mais pesos, ajuste por mínimos quadrados (We numa grade de 100 passos, refinado por seção áurea); fim previsto = −ln((W_meta − We) ÷ (W₀ − We)) ÷ k",
            "variaveis": [
              {
                "simbolo": "W(t)",
                "significado": "peso no tempo t",
                "unidade": "kg"
              },
              {
                "simbolo": "We",
                "significado": "peso de equilíbrio",
                "unidade": "kg"
              },
              {
                "simbolo": "k",
                "significado": "constante de secagem",
                "unidade": "1/h"
              },
              {
                "simbolo": "t",
                "significado": "tempo desde o começo",
                "unidade": "h"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Modelo exponencial de camada fina da literatura de secagem; sem pesos, k e umidade de equilíbrio típicos do produto."
            }
          ],
          "limites_de_validade": "Camada fina e condições do ar parecidas ao longo do lote; sem resposta quando o equilíbrio fica acima da meta.",
          "fonte_de_dados": "Pesos do lote (PESO ou pesagens à mão).",
          "status": "simplificado",
          "o_que_falta": "Medir o k de cada produto no secador da Physis.",
          "onde": "sistema/physis-secador.js · ajustar(), previsaoLote() (espelho: physis_hub/secador.py)"
        },
        {
          "id": "sec.coletor",
          "nome": "Tamanho do coletor e vazão de ar",
          "o_que_calcula": "Área de coletor solar e vazão do ventilador para secar um lote no prazo.",
          "formula": {
            "texto": "calor = água × 2,45 MJ/kg ÷ aproveitamento do ar; área = calor ÷ (H × 3,6 × η × dias); Δw = 1,006 × ΔT × aproveitamento ÷ 2.450; vazão = (água ÷ Δw) ÷ 1,15 ÷ (dias × horas)",
            "variaveis": [
              {
                "simbolo": "H",
                "significado": "irradiação no coletor",
                "unidade": "kWh/m² por dia"
              },
              {
                "simbolo": "η",
                "significado": "eficiência do coletor",
                "unidade": "0 a 1"
              },
              {
                "simbolo": "ΔT",
                "significado": "aquecimento do ar no coletor",
                "unidade": "°C"
              },
              {
                "simbolo": "Δw",
                "significado": "água levada por kg de ar",
                "unidade": "kg/kg"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "ASHRAE 93",
              "edicao": "a conferir",
              "item": "eficiência do coletor",
              "como_e_usada": "A eficiência usada é premissa; o método de ensaio indica como medi-la no coletor construído."
            },
            {
              "codigo": "ASHRAE Handbook Fundamentals",
              "edicao": "a conferir",
              "item": "psicrometria",
              "como_e_usada": "Calor específico do ar, calor latente da água e densidade do ar nas contas do ar de secagem."
            }
          ],
          "limites_de_validade": "Mês de projeto escolhido (o mais fraco por padrão); irradiação da NASA POWER quando o lugar tem localização.",
          "fonte_de_dados": "Produto por lote, dias de sol, horas de ventilador, irradiação do lugar.",
          "status": "simplificado",
          "o_que_falta": "Medir a eficiência real do coletor (ensaio) e trocar a premissa.",
          "onde": "sistema/physis-secador.js · dimensionar() (espelho: physis_hub/secador.py)"
        },
        {
          "id": "sec.evitado",
          "nome": "CO₂ evitado pelo secador solar",
          "o_que_calcula": "Emissão que um secador elétrico ou a lenha teria para tirar a mesma água.",
          "formula": {
            "texto": "elétrico = calor da água ÷ η ÷ 3,6 (kWh) × fator da rede; lenha = calor ÷ (13 MJ/kg × η) kg, com CH₄ e N₂O da queima e o CO₂ só se a lenha for sem reposição",
            "variaveis": [
              {
                "simbolo": "η",
                "significado": "eficiência do secador comparado",
                "unidade": "0 a 1"
              },
              {
                "simbolo": "fator da rede",
                "significado": "emissão da eletricidade",
                "unidade": "tCO₂/MWh"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "GHG Protocol",
              "edicao": "2004 / 2015",
              "item": "emissões evitadas",
              "como_e_usada": "Informadas à parte, nunca descontadas do inventário."
            },
            {
              "codigo": "Fator médio do SIN (MCTI)",
              "edicao": "por ano",
              "item": "fator da rede",
              "como_e_usada": "Fator da base do Carbono."
            }
          ],
          "limites_de_validade": "Comparação com um secador hipotético de mesma carga.",
          "fonte_de_dados": "Água tirada nos lotes, base de fatores de emissão.",
          "status": "simplificado",
          "o_que_falta": "Confirmar a eficiência dos secadores de comparação usados na região.",
          "onde": "sistema/physis-secador.js · dimensionar() (evitado)"
        }
      ]
    },
    "servidor-verde": {
      "nome": "Servidor verde",
      "resumo": "Dimensionamento de servidores com pouca pegada, por projeto (em desenvolvimento).",
      "calculos": [
        {
          "premissas": [],
          "status": "simplificado",
          "onde": "sistema/physis-servidor-verde.js (espelho: physis_hub/servidor_verde.py)",
          "id": "sv.computacao",
          "nome": "Computação e memória de vídeo",
          "o_que_calcula": "Núcleos, memória e memória de vídeo para as cargas de trabalho e o modelo de IA.",
          "formula": {
            "texto": "memória de vídeo = parâmetros × bytes por parâmetro × 1,2; memória = soma dos programas (+ o modelo, quando a placa não comporta); placas = memória de vídeo ÷ memória por placa",
            "variaveis": [
              {
                "simbolo": "parâmetros",
                "significado": "tamanho do modelo",
                "unidade": "bilhões"
              },
              {
                "simbolo": "bytes por parâmetro",
                "significado": "precisão do modelo",
                "unidade": "B"
              }
            ]
          },
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Regra de dimensionamento da Physis; faixas por classe genérica marcadas verificar."
            }
          ],
          "limites_de_validade": "Classes genéricas de máquina; o desempenho real depende do modelo e do programa.",
          "fonte_de_dados": "Seleção de módulos e cargas de trabalho do projeto; catálogo de módulos.",
          "o_que_falta": "Curadoria das faixas de potência e desempenho por classe; tokens por segundo medidos."
        },
        {
          "premissas": [],
          "status": "simplificado",
          "onde": "sistema/physis-servidor-verde.js (espelho: physis_hub/servidor_verde.py)",
          "id": "sv.armazenamento",
          "nome": "Armazenamento e cópias",
          "o_que_calcula": "Crescimento do banco de dados e dos arquivos e o espaço das cópias.",
          "formula": {
            "texto": "dados = sensores × leituras por dia × bytes × dias de retenção; cópia 3-2-1 com uma cópia fora do lugar",
            "variaveis": [
              {
                "simbolo": "bytes",
                "significado": "tamanho de cada leitura",
                "unidade": "B"
              },
              {
                "simbolo": "retenção",
                "significado": "tempo guardado",
                "unidade": "anos"
              }
            ]
          },
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Boa prática de cópia de segurança (3 cópias, 2 meios, 1 fora do lugar)."
            }
          ],
          "limites_de_validade": "Sem compressão do banco; RAID e fotos do disco somados à parte.",
          "fonte_de_dados": "Cargas de trabalho do projeto.",
          "o_que_falta": "Medir o crescimento real do banco na Casa Physis."
        },
        {
          "premissas": [],
          "status": "simplificado",
          "onde": "sistema/physis-servidor-verde.js (espelho: physis_hub/servidor_verde.py)",
          "id": "sv.energia",
          "nome": "Energia, nobreak e solar",
          "o_que_calcula": "Consumo do servidor, tamanho do nobreak e da geração solar com bateria.",
          "formula": {
            "texto": "kWh/dia = W médio × 24 ÷ eficiência da fonte (curva 80 PLUS pela carga); nobreak VA = pico ÷ fator de potência; Wh = W médio × autonomia ÷ profundidade de descarga; kWp = kWh/dia ÷ (horas de sol × PR)",
            "variaveis": [
              {
                "simbolo": "W médio",
                "significado": "potência média do servidor",
                "unidade": "W"
              },
              {
                "simbolo": "autonomia",
                "significado": "tempo no nobreak",
                "unidade": "h"
              },
              {
                "simbolo": "PR",
                "significado": "rendimento global do sistema solar",
                "unidade": "0 a 1"
              }
            ]
          },
          "normas": [
            {
              "codigo": "IEC 62040-3",
              "edicao": "a conferir",
              "item": "desempenho do nobreak",
              "como_e_usada": "Referência para a escolha e o ensaio do nobreak."
            },
            {
              "codigo": "ABNT NBR 16690",
              "edicao": "2019",
              "item": "instalação fotovoltaica",
              "como_e_usada": "Instalação do sistema solar que alimenta o servidor."
            }
          ],
          "limites_de_validade": "Potências por classe genérica (verificar); sol do lugar pela NASA POWER ou digitado.",
          "fonte_de_dados": "Seleção de módulos, lugar do projeto e catálogo (curvas 80 PLUS).",
          "o_que_falta": "Calibrar com a medição real da pegada do servidor."
        },
        {
          "premissas": [],
          "status": "simplificado",
          "onde": "sistema/physis-servidor-verde.js (espelho: physis_hub/servidor_verde.py)",
          "id": "sv.termico",
          "nome": "Calor da sala e PUE",
          "o_que_calcula": "Calor do servidor, ar-condicionado ou ventilação e a eficiência da sala.",
          "formula": {
            "texto": "BTU/h = W × 3,412; TR = BTU/h ÷ 12.000; PUE = (TI + ar + perdas + luz) ÷ TI",
            "variaveis": [
              {
                "simbolo": "TI",
                "significado": "energia dos equipamentos de TI",
                "unidade": "kW"
              },
              {
                "simbolo": "PUE",
                "significado": "eficiência no uso da energia",
                "unidade": "—"
              }
            ]
          },
          "normas": [
            {
              "codigo": "ISO/IEC 30134-2",
              "edicao": "a conferir",
              "item": "PUE",
              "como_e_usada": "Definição do indicador de eficiência da sala."
            },
            {
              "codigo": "ASHRAE TC 9.9",
              "edicao": "a conferir",
              "item": "classe A1",
              "como_e_usada": "Faixa de temperatura e umidade da sala."
            }
          ],
          "limites_de_validade": "Sala pequena; perdas e iluminação informadas.",
          "fonte_de_dados": "Energia calculada e dados da sala.",
          "o_que_falta": "Medir temperatura e consumo do ar na sala da Casa Physis."
        },
        {
          "premissas": [],
          "status": "simplificado",
          "onde": "sistema/physis-servidor-verde.js (espelho: physis_hub/servidor_verde.py)",
          "id": "sv.carbono",
          "nome": "Carbono e custos do servidor",
          "o_que_calcula": "Emissão da operação e da fabricação, custo da energia e retorno do investimento solar.",
          "formula": {
            "texto": "operação = kWh/ano ÷ 1000 × fator da rede do lugar; fabricação = carbono da classe ÷ anos de uso (escopo 3, cat. 2); custo = kWh × tarifa",
            "variaveis": [
              {
                "simbolo": "fator da rede",
                "significado": "emissão da eletricidade do lugar",
                "unidade": "tCO₂/MWh"
              },
              {
                "simbolo": "anos de uso",
                "significado": "vida útil considerada",
                "unidade": "anos"
              }
            ]
          },
          "normas": [
            {
              "codigo": "GHG Protocol",
              "edicao": "2004 / 2015",
              "item": "orientação setorial de TIC",
              "como_e_usada": "Energia no escopo 2 ou 3 e fabricação no escopo 3."
            },
            {
              "codigo": "ITU-T L.1450",
              "edicao": "a conferir",
              "item": "pegada do setor de TIC",
              "como_e_usada": "Métodos para a pegada das máquinas."
            }
          ],
          "limites_de_validade": "Carbono de fabricação por classe é ordem de grandeza (verificar); custos sem orçamento ficam [MARCADOR].",
          "fonte_de_dados": "Energia calculada, fator da rede do Carbono e catálogo.",
          "o_que_falta": "Orçamentos reais e carbono de fabricação por modelo de máquina."
        }
      ]
    },
    "simulacao": {
      "nome": "Simulação (Fase 1)",
      "resumo": "Simulações leves de pré-dimensionamento (calor, estrutura, ventilação, terreno e água, incerteza, QUBO e biogás), iguais no servidor e no navegador (em desenvolvimento).",
      "calculos": [
        {
          "premissas": [],
          "status": "simplificado",
          "onde": "sistema/physis-simulacao.js (espelho: physis_hub/simulacao/)",
          "id": "sim.termica",
          "nome": "Calor em paredes e coberturas",
          "o_que_calcula": "U das camadas, transiente 1D (atraso e amortecimento) e corte 2D (ponte térmica).",
          "formula": {
            "texto": "U = 1 ÷ (Rsi + Σ e/λ + Rse); transiente por diferenças finitas (implícito, explícito ou Crank-Nicolson)",
            "variaveis": [
              {
                "simbolo": "e/λ",
                "significado": "resistência de cada camada",
                "unidade": "m²K/W"
              }
            ]
          },
          "normas": [
            {
              "codigo": "ABNT NBR 15220",
              "edicao": "a conferir",
              "item": "parte 2, método de cálculo da transmitância",
              "como_e_usada": "Mesma soma de resistências; Rsi e Rse de premissa."
            }
          ],
          "limites_de_validade": "Fluxo unidimensional por camada; propriedades da base de materiais.",
          "fonte_de_dados": "physis-materiais.json; premissas sim.termica.*",
          "o_que_falta": "Ensaios de materiais de terra e fibras."
        },
        {
          "premissas": [],
          "status": "simplificado",
          "onde": "sistema/physis-simulacao.js (espelho: physis_hub/simulacao/)",
          "id": "sim.estrutura",
          "nome": "Estrutura linear (treliça, pórtico, chapa)",
          "o_que_calcula": "Deslocamentos, esforços e tensões; flambagem de Euler; verificação simplificada.",
          "formula": {
            "texto": "K·u = F (barra e viga de Euler-Bernoulli; triângulos CST); Pcr = π²EI/(KL)²",
            "variaveis": [
              {
                "simbolo": "E, I",
                "significado": "módulo de elasticidade e inércia",
                "unidade": "Pa, m⁴"
              }
            ]
          },
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Cálculo linear clássico; vento pelo método da pressão dinâmica da ABNT NBR 6123, com V0, S1, S2, S3 e Cf digitados [CONFERIR NA NORMA]."
            }
          ],
          "limites_de_validade": "Linear, pequenas deformações; não substitui o cálculo estrutural assinado.",
          "fonte_de_dados": "Material da premissa sim.estrutura.materiais ou do ensaio.",
          "o_que_falta": "E e fy de bambu, madeira e filamentos medidos."
        },
        {
          "premissas": [],
          "status": "simplificado",
          "onde": "sistema/physis-simulacao.js (espelho: physis_hub/simulacao/)",
          "id": "sim.terreno",
          "nome": "Terreno e água (D8, SCS-CN, USLE)",
          "o_que_calcula": "Caminho da água, enxurrada de um evento e perda de solo na grade do lote.",
          "formula": {
            "texto": "Q = (P − 0,2S)² ÷ (P + 0,8S), S = 25400/CN − 254; A = R·K·LS·C·P",
            "variaveis": [
              {
                "simbolo": "CN",
                "significado": "número da curva por uso do solo",
                "unidade": "—"
              }
            ]
          },
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Métodos clássicos (SCS-CN, USLE); CN por uso de premissa [CONFERIR]."
            }
          ],
          "limites_de_validade": "Grade do lote; um evento de chuva; sem rede de drenagem.",
          "fonte_de_dados": "Geometria do lugar (Mapeamento).",
          "o_que_falta": "Modelo de elevação do lote em campo."
        },
        {
          "premissas": [],
          "status": "simplificado",
          "onde": "sistema/physis-simulacao.js (espelho: physis_hub/simulacao/)",
          "id": "sim.biogas",
          "nome": "Biodigestor: produção de biogás",
          "o_que_calcula": "Biogás e metano por dia e por mês, volume, carga orgânica, energia e CO₂e evitado.",
          "formula": {
            "texto": "produção = Σ massa × ST × SV × BMP × fração(k(T), TRH); k(T) = k_ref·θ^(T − T_ref)",
            "variaveis": [
              {
                "simbolo": "BMP",
                "significado": "potencial de metano do substrato",
                "unidade": "m³/kg SV"
              }
            ]
          },
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Cinética de 1ª ordem e BMP de tabela (premissas sim.biogas.*, conferir)."
            }
          ],
          "limites_de_validade": "Mistura completa ou fluxo pistonado; temperatura do local quando sem aquecimento.",
          "fonte_de_dados": "Plano de resíduos (rota biodigestor) e local da instalação.",
          "o_que_falta": "BMP medido dos substratos do cliente."
        },
        {
          "premissas": [],
          "status": "simplificado",
          "onde": "sistema/physis-simulacao.js (espelho: physis_hub/simulacao/)",
          "id": "sim.incerteza",
          "nome": "Faixa de incerteza (Monte Carlo)",
          "o_que_calcula": "Média e percentis da geração, do inventário de carbono e do retorno.",
          "formula": {
            "texto": "N sorteios das entradas (normal, uniforme, triangular, lognormal) pelo gerador mulberry32",
            "variaveis": [
              {
                "simbolo": "P5, P95",
                "significado": "percentis",
                "unidade": "—"
              }
            ]
          },
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "—",
              "como_e_usada": "Método estatístico; semente fixa nos testes."
            }
          ],
          "limites_de_validade": "Entradas independentes.",
          "fonte_de_dados": "Desvios digitados ou da incerteza do inventário.",
          "o_que_falta": "Correlação entre entradas."
        }
      ]
    },
    "frota": {
      "nome": "Frota e combustível",
      "resumo": "Distância, consumo, marcha lenta, alertas e CO₂e da frota (versão 0.1, em desenvolvimento).",
      "calculos": [
        {
          "id": "frota.distancia",
          "nome": "Distância percorrida",
          "o_que_calcula": "Quilômetros rodados pelos pontos de GPS ou pelo odômetro.",
          "formula": {
            "texto": "d = 2R · asen(√(sen²(Δφ/2) + cos φ₁ · cos φ₂ · sen²(Δλ/2))); trecho com velocidade implícita acima de v_salto sai da soma; com odômetro no começo e no fim, vale ODO_fim − ODO_começo",
            "variaveis": [
              {
                "simbolo": "R",
                "significado": "raio médio da Terra",
                "unidade": "km"
              },
              {
                "simbolo": "φ, λ",
                "significado": "latitude e longitude",
                "unidade": "rad"
              },
              {
                "simbolo": "v_salto",
                "significado": "velocidade implícita que marca salto de GPS",
                "unidade": "km/h"
              }
            ]
          },
          "premissas": [
            "frota.gps_salto_kmh"
          ],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "",
              "como_e_usada": "Fórmula de haversine (geometria esférica)."
            }
          ],
          "limites_de_validade": "Esfera de raio médio (erro abaixo de 0,5 %); pontos espaçados cortam curvas.",
          "fonte_de_dados": "Linha V6 TIPO:VEI (LAT, LON, ODO) ou CSV do rastreador.",
          "status": "simplificado",
          "o_que_falta": "Conferir com o odômetro de um veículo da Casa Physis.",
          "onde": "physis_hub/frota.py (espelho: sistema/physis-frota.js) · distancia(), haversine_km()"
        },
        {
          "id": "frota.consumo",
          "nome": "Consumo por km e por hora",
          "o_que_calcula": "Litros pela vazão, horas de motor e o consumo em L/100 km ou L/h; sem vazão, pelo método do tanque cheio.",
          "formula": {
            "texto": "L = Σ (FLXᵢ + FLXᵢ₊₁)/2 · Δt só nos trechos com vazão nas duas pontas (buraco > 15 min não entra); km e horas de motor dos mesmos trechos; L/100 km = L ÷ km × 100; L/h = L ÷ horas; amostra = dia completo; tanque cheio: litros do abastecimento ÷ (ODO − ODO anterior) × 100",
            "variaveis": [
              {
                "simbolo": "FLX",
                "significado": "vazão de combustível",
                "unidade": "L/h"
              },
              {
                "simbolo": "Δt",
                "significado": "intervalo entre leituras",
                "unidade": "h"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "",
              "como_e_usada": "Método de referência descrito na fórmula."
            }
          ],
          "limites_de_validade": "Diesel com retorno precisa de medição diferencial; tanque cheio supõe tanque cheio nos dois abastecimentos.",
          "fonte_de_dados": "FLX e HOR da linha VEI; abastecimentos digitados ou do cartão.",
          "status": "simplificado",
          "o_que_falta": "Conferir o fluxômetro escolhido e a forma de medir com retorno.",
          "onde": "physis_hub/frota.py (espelho: sistema/physis-frota.js) · trechos_com_vazao(), litros_do_fluxo(), horas_motor(), consumo(), consumo_entre_abastecimentos()"
        },
        {
          "id": "frota.anomalia",
          "nome": "Consumo acima do normal do veículo",
          "o_que_calcula": "Se a amostra nova de consumo está acima do normal aprendido do próprio veículo.",
          "formula": {
            "texto": "z = 0,6745 · (x − mediana) ÷ MAD; alerta se z > z_lim e x ≥ mediana · (1 + d_min/100), com n ≥ n_min amostras; EWMA = α·x + (1 − α)·EWMA anterior",
            "variaveis": [
              {
                "simbolo": "MAD",
                "significado": "desvio absoluto mediano das amostras anteriores",
                "unidade": "L/100 km ou L/h"
              },
              {
                "simbolo": "z_lim, d_min, n_min, α",
                "significado": "premissas do alerta",
                "unidade": "—"
              }
            ]
          },
          "premissas": [
            "frota.anomalia_z",
            "frota.anomalia_desvio_min_pct",
            "frota.anomalia_amostra_min",
            "frota.ewma_alfa"
          ],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "",
              "como_e_usada": "z modificado de Iglewicz e Hoaglin (1993)."
            }
          ],
          "limites_de_validade": "Mudança de serviço (outra carga, outro terreno) muda o normal; o alerta pede conferência, não conclui.",
          "fonte_de_dados": "Amostras diárias pela vazão ou trechos entre abastecimentos.",
          "status": "simplificado",
          "o_que_falta": "Conferir os limites com 2 a 3 meses de dados reais da frota.",
          "onde": "physis_hub/frota.py (espelho: sistema/physis-frota.js) · anomalia_consumo(), normal_aprendido()"
        },
        {
          "id": "frota.alertas",
          "nome": "Nível caindo parado, marcha lenta e cerca",
          "o_que_calcula": "Queda de nível com o veículo parado (vazamento ou furto possível), marcha lenta longa e saída da cerca.",
          "formula": {
            "texto": "queda = NIV_começo − NIV_agora − (litros pela vazão ÷ tanque × 100) ≥ q_lim com deslocamento ≤ d_parado; marcha lenta: motor ligado e VEL < v_lim por ≥ t_lim; cerca: ponto dentro → fora (método do raio)",
            "variaveis": [
              {
                "simbolo": "q_lim",
                "significado": "queda mínima",
                "unidade": "% do tanque"
              },
              {
                "simbolo": "d_parado",
                "significado": "deslocamento máximo para contar como parado",
                "unidade": "km"
              },
              {
                "simbolo": "v_lim, t_lim",
                "significado": "velocidade e tempo da marcha lenta",
                "unidade": "km/h; min"
              }
            ]
          },
          "premissas": [
            "frota.queda_nivel_pct",
            "frota.parado_distancia_km",
            "frota.marcha_lenta_vel_kmh",
            "frota.marcha_lenta_min"
          ],
          "normas": [
            {
              "codigo": "sem norma aplicável",
              "edicao": "—",
              "item": "",
              "como_e_usada": "Método de referência descrito na fórmula."
            },
            {
              "codigo": "Lei 13.709/2018",
              "edicao": "2018",
              "item": "art. 6º e 15 (finalidade e término)",
              "como_e_usada": "Posição do veículo é dado pessoal de quem dirige: aviso, código no lugar do nome e retenção."
            }
          ],
          "limites_de_validade": "Sensor de nível com resolução pior que q_lim não vê vazamento pequeno.",
          "fonte_de_dados": "NIV, VEL, FLX, IGN da linha VEI; cercas desenhadas na aba.",
          "status": "simplificado",
          "o_que_falta": "Testar com sensor de nível e rastreador reais.",
          "onde": "physis_hub/frota.py (espelho: sistema/physis-frota.js) · quedas_sem_andar(), marcha_lenta(), saidas_da_cerca(), ponto_no_poligono()"
        },
        {
          "id": "frota.co2e",
          "nome": "Emissões da frota",
          "o_que_calcula": "CO₂e dos litros abastecidos (ou medidos pela vazão), pelo mesmo caminho do Carbono.",
          "formula": {
            "texto": "igual a carb.escopo1 (combustão móvel): energia do combustível × fator por gás × GWP; mistura do diesel B e da gasolina C pela base de fatores",
            "variaveis": [
              {
                "simbolo": "L",
                "significado": "litros (m³ de GNV)",
                "unidade": "L"
              }
            ]
          },
          "premissas": [],
          "normas": [
            {
              "codigo": "GHG Protocol",
              "edicao": "2004 / 2015",
              "item": "escopo 1, combustão móvel",
              "como_e_usada": "Frota própria no escopo 1; CO₂ da parte bio à parte."
            },
            {
              "codigo": "IPCC 2006",
              "edicao": "2006",
              "item": "vol. 2, cap. 3 (transporte)",
              "como_e_usada": "Fatores de CH₄ e N₂O de veículos, já na base do Carbono."
            }
          ],
          "limites_de_validade": "Teor de mistura conforme a base de fatores do período.",
          "fonte_de_dados": "Abastecimentos do ano; vazão para veículo sem abastecimento.",
          "status": "conforme",
          "o_que_falta": "",
          "onde": "physis_hub/frota.py (espelho: sistema/physis-frota.js) · co2e(), para_carbono() → carbono.calcular (ctx.frota_movel)"
        }
      ]
    }
  },
  "adequacoes": [
    {
      "prioridade": 1,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "carb.evitado_saldo",
        "sk.carbono"
      ],
      "titulo": "Carbono: tirar a dupla contagem da solar",
      "o_que_fazer": "Mostrar o inventário dos escopos 1 e 2 sem descontos; mostrar 'emissões evitadas' num quadro separado; o saldo net zero só desconta remoções e créditos.",
      "criterio_de_aceite": "Com kWh da rede vindo das contas e geração solar informada, o total do inventário não muda quando a geração muda.",
      "situacao": "feito (15/11/2026)"
    },
    {
      "prioridade": 2,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "solar.economia"
      ],
      "titulo": "Solar: economia pela Lei 14.300",
      "o_que_fazer": "Separar autoconsumo e energia injetada; aplicar à injetada o desconto do Fio B pela escala do art. 27 (percentuais na base de premissas, conferidos na lei); manter o custo de disponibilidade.",
      "criterio_de_aceite": "Com 100% de autoconsumo a economia é a mesma de hoje; com 100% injetado ela fica menor e cai a cada ano da escala.",
      "situacao": "feito (15/11/2026)"
    },
    {
      "prioridade": 3,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "avac.ar_condicionado",
        "avac.carga_termica"
      ],
      "titulo": "AVAC: usar a carga térmica no lugar de m²/TR",
      "o_que_fazer": "Quando o ambiente tiver carga térmica calculada (physis-cargatermica.js), o ar-condicionado e o quadro elétrico usam esse valor; m²/TR fica só como triagem e aparece marcado assim.",
      "criterio_de_aceite": "Ambiente com carga calculada mostra a capacidade da carga térmica e a fonte 'NBR 16401-1'.",
      "situacao": "feito (15/11/2026)"
    },
    {
      "prioridade": 4,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "solar.dimensionamento",
        "sk.solar"
      ],
      "titulo": "Solar: irradiação no plano das placas",
      "o_que_fazer": "Levar a irradiação horizontal para o plano inclinado (modelo isotrópico) com a inclinação e a orientação do telhado do Planejador; o SustainKit usa a mesma base do servidor.",
      "criterio_de_aceite": "Telhado plano dá o mesmo resultado de hoje; telhado inclinado para o norte aumenta a geração de inverno.",
      "situacao": "feito (15/11/2026)"
    },
    {
      "prioridade": 5,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "avac.aquecimento_solar"
      ],
      "titulo": "Aquecimento solar: irradiação do lugar mês a mês",
      "o_que_fazer": "Trocar a produção fixa de 1,8 kWh/m²·dia pela produção do coletor (etiqueta Inmetro) corrigida pela irradiação mensal do lugar; mostrar o pior mês.",
      "criterio_de_aceite": "Duas cidades com sol diferente dão áreas de coletor diferentes.",
      "situacao": "feito (15/11/2026)"
    },
    {
      "prioridade": 6,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "sk.bateria",
        "solar.bateria",
        "sk.agro"
      ],
      "titulo": "Baterias e PR: uma regra só",
      "o_que_fazer": "Unificar a margem da bateria (÷ 0,95 na plataforma, × 1,2 no SustainKit, 2 dias e 0,80 no agro) e o PR do agro (0,75) numa premissa da base, com fonte.",
      "criterio_de_aceite": "Mesma entrada dá o mesmo banco de baterias na plataforma e no SustainKit.",
      "situacao": "feito (15/11/2026)"
    },
    {
      "prioridade": 7,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "sk.carbono",
        "carb.escopo1"
      ],
      "titulo": "Fatores de emissão: uma fonte só",
      "o_que_fazer": "SustainKit passa a usar o diesel por litro (2,671 kgCO₂e/L) e a regra de biogás da base de premissas, igual à aba Carbono.",
      "criterio_de_aceite": "Teste de premissas compara os fatores dos dois programas.",
      "situacao": "feito (15/11/2026)"
    },
    {
      "prioridade": 8,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "plan.drenagem"
      ],
      "titulo": "Planejador: calhas e condutores pela NBR 10844",
      "o_que_fazer": "Calcular a vazão de cada água de telhado (intensidade × área de contribuição ÷ 60) com a IDF do lugar e o tempo de retorno da norma, e escolher calha e condutor.",
      "criterio_de_aceite": "Cada cobertura do projeto mostra a vazão e a seção sugerida.",
      "situacao": "feito (15/11/2026)"
    },
    {
      "prioridade": 9,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "sk.agua",
        "plan.chuva_cisterna"
      ],
      "titulo": "Água de chuva: mês a mês e descarte inicial",
      "o_que_fazer": "SustainKit usa o balanço mensal ou diário do Planejador em vez da média anual; descontar o volume de descarte inicial recomendado pela NBR 15527.",
      "criterio_de_aceite": "A cisterna do SustainKit e a do Planejador dão o mesmo volume para o mesmo projeto.",
      "situacao": "feito (15/11/2026)"
    },
    {
      "prioridade": 10,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "agua.limites"
      ],
      "titulo": "Qualidade da água: referência por uso, sem alerta automático",
      "o_que_fazer": "Mostrar ao lado de cada limite a faixa de referência do uso escolhido (beber, rio, efluente, reúso) como informação; nada é preenchido nem alerta sozinho.",
      "criterio_de_aceite": "Sem limite informado pela pessoa, nenhum alerta aparece (regra 3).",
      "situacao": "feito (15/11/2026), com modo de teste opcional"
    },
    {
      "prioridade": 11,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "res.matriz",
        "res.encosta"
      ],
      "titulo": "Resiliência: escalas escritas e limiares trocáveis",
      "o_que_fazer": "Descrever cada nível de chance e impacto (ISO 31000) e permitir trocar os limiares de chuva pelos da Defesa Civil do município.",
      "criterio_de_aceite": "A tela mostra o significado de cada nível; limiar trocado vale para o alerta.",
      "situacao": "feito (15/11/2026)"
    },
    {
      "prioridade": 12,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "plan.declividade_app"
      ],
      "titulo": "Planejador: outras APP e Lei 6.766",
      "o_que_fazer": "Marcar faixas de APP de rios e nascentes (art. 4º, I e IV) quando houver hidrografia no servidor; citar a Lei 6.766 no alerta de 30%.",
      "criterio_de_aceite": "Com um rio no mapa aparece a faixa de APP na largura que o engenheiro aprovou.",
      "situacao": "feito (15/11/2026): rios e nascentes com a hidrografia do servidor ou digitada; topo de morro em triagem"
    },
    {
      "prioridade": 13,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "turb.eolica",
        "turb.hidraulica"
      ],
      "titulo": "Turbinas: curva certificada e outorga",
      "o_que_fazer": "Permitir carregar a curva de potência do fabricante (IEC 61400-12-1) e avisar sobre outorga e vazão ecológica na hidráulica.",
      "criterio_de_aceite": "Curva carregada substitui o modelo por Cp no cálculo da energia.",
      "situacao": "feito (15/11/2026)"
    },
    {
      "prioridade": 14,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "sbn.viveiro"
      ],
      "titulo": "Viveiro: aviso de RENASEM",
      "o_que_fazer": "Mostrar o aviso de registro antes de vender mudas.",
      "criterio_de_aceite": "O aviso aparece na parte Viveiro.",
      "situacao": "feito (15/11/2026)"
    },
    {
      "prioridade": 15,
      "quem": "software",
      "quando": "agora",
      "calculos": [
        "avac.ventilacao",
        "avac.dutos",
        "rc.produtos",
        "res.alertas",
        "plan.agua_fria",
        "sk.fluxo_agua"
      ],
      "titulo": "Premissas soltas para a base",
      "o_que_fazer": "Levar para sistema/physis-premissas.json os valores hoje fixos no código: vazões de exaustão, limites de velocidade de dutos, rendimentos dos resíduos, limiares das atividades, 2 dias de reserva de água e coeficiente de retorno 0,80.",
      "criterio_de_aceite": "Cada valor tem id, unidade e fonte na base, e o código lê da base.",
      "situacao": "feito (15/11/2026)"
    },
    {
      "prioridade": 16,
      "quem": "engenharia",
      "quando": "fase 2",
      "calculos": [
        "plan.esgoto"
      ],
      "titulo": "Esgoto: NBR 17076:2024",
      "o_que_fazer": "Conferir se a NBR 17076:2024 substituiu as NBR 7229 e 13969; se sim, rever fórmula, tabelas e distâncias.",
      "criterio_de_aceite": "Base de premissas com a edição conferida, data e responsável."
    },
    {
      "prioridade": 17,
      "quem": "engenharia",
      "quando": "fase 2",
      "calculos": [
        "avac.pressurizacao"
      ],
      "titulo": "Pressurização: valores da NBR 14880 e da IT do estado",
      "o_que_fazer": "Conferir faixa de ΔP, portas abertas, velocidade, fator e força máxima.",
      "criterio_de_aceite": "Valores com fonte na base de premissas."
    },
    {
      "prioridade": 18,
      "quem": "engenharia",
      "quando": "fase 2",
      "calculos": [
        "avac.carga_termica"
      ],
      "titulo": "Carga térmica: tabelas lembradas",
      "o_que_fazer": "Conferir condições externas por cidade, calor de pessoas e Rp/Ra com a NBR 16401 vigente.",
      "criterio_de_aceite": "Nenhum valor marcado 'verificar' sem fonte."
    },
    {
      "prioridade": 19,
      "quem": "engenharia",
      "quando": "fase 2",
      "calculos": [
        "avac.quadro"
      ],
      "titulo": "Quadro elétrico: NBR 5410 completa",
      "o_que_fazer": "Validar tabelas Iz, FCT e limites de queda; acrescentar métodos de instalação, EPR/XLPE e FCA por agrupamento.",
      "criterio_de_aceite": "Casos de teste conferidos à mão por engenheiro eletricista."
    },
    {
      "prioridade": 20,
      "quem": "engenharia",
      "quando": "fase 2",
      "calculos": [
        "solar.dimensionamento"
      ],
      "titulo": "Solar: projeto elétrico pela NBR 16690 e comissionamento pela NBR 16274",
      "o_que_fazer": "Strings (tensão na menor temperatura, corrente), cabos CC, proteções e roteiro de comissionamento.",
      "criterio_de_aceite": "Cálculo de strings com dados da placa e do inversor escolhidos."
    },
    {
      "prioridade": 21,
      "quem": "engenharia",
      "quando": "fase 2",
      "calculos": [
        "plan.estabilidade"
      ],
      "titulo": "Encostas: FS mínimo pela NBR 11682",
      "o_que_fazer": "Fixar o FS mínimo pelo nível de segurança; a triagem segue só como triagem.",
      "criterio_de_aceite": "FS mínimo vem da base, com a tabela conferida."
    },
    {
      "prioridade": 22,
      "quem": "engenharia",
      "quando": "fase 2",
      "calculos": [
        "rc.classe"
      ],
      "titulo": "Resíduos: NBR 10004:2024",
      "o_que_fazer": "Conferir as classes da tela na edição de 2024 e pôr o ano no rótulo.",
      "criterio_de_aceite": "Rótulo com edição conferida."
    },
    {
      "prioridade": 23,
      "quem": "engenharia",
      "quando": "fase 2",
      "calculos": [
        "carb.escopo1",
        "carb.escopo2"
      ],
      "titulo": "Carbono: fatores com ano e fonte",
      "o_que_fazer": "Conferir o fator do SIN por ano, a mistura de biodiesel e os fatores de GLP e gás natural.",
      "criterio_de_aceite": "Base de premissas com fonte e ano de cada fator."
    },
    {
      "prioridade": 24,
      "quem": "engenharia",
      "quando": "fase 2",
      "calculos": [
        "sk.materiais",
        "plan.insolacao"
      ],
      "titulo": "Envoltória: NBR 15575 e NBR 15220",
      "o_que_fazer": "Conferir revisão vigente da NBR 15220 e os limites de transmitância e absortância das sugestões por zona.",
      "criterio_de_aceite": "Tabela MAT_ZONA com a verificação marcada."
    },
    {
      "prioridade": 25,
      "quem": "engenharia",
      "quando": "fase 2",
      "calculos": [
        "sbn.jardim_chuva"
      ],
      "titulo": "Jardim de chuva e wetland",
      "o_que_fazer": "Fixar taxas de infiltração e de carga e o método de dimensionamento.",
      "criterio_de_aceite": "Módulo com fórmula e fonte aprovadas."
    },
    {
      "prioridade": 26,
      "quem": "engenharia",
      "quando": "fase 2",
      "calculos": [
        "plan.incendio"
      ],
      "titulo": "Incêndio: Instrução Técnica do estado",
      "o_que_fazer": "Ligar as medidas à IT do Corpo de Bombeiros do estado do projeto.",
      "criterio_de_aceite": "Exigências por estado na base."
    }
  ],
  "normas": {
    "ABNT NBR 15527": {
      "tipo": "ABNT",
      "assunto": "aproveitamento de água de chuva de coberturas para usos não potáveis",
      "edicao": "2019",
      "situacao": "vigente",
      "nota": "a edição de 2007 foi substituída; não citar 2007"
    },
    "ABNT NBR 5626": {
      "tipo": "ABNT",
      "assunto": "sistemas prediais de água fria e água quente",
      "edicao": "2020",
      "situacao": "conferir",
      "nota": "a edição de 2020 juntou água fria e quente; conferir no catálogo ABNT"
    },
    "ABNT NBR 8160": {
      "tipo": "ABNT",
      "assunto": "sistemas prediais de esgoto sanitário",
      "edicao": "1999",
      "situacao": "conferir",
      "nota": "conferir se há revisão publicada"
    },
    "ABNT NBR 7229": {
      "tipo": "ABNT",
      "assunto": "tanques sépticos (projeto, construção e operação)",
      "edicao": "1993",
      "situacao": "conferir",
      "nota": "conferir se foi substituída pela ABNT NBR 17076:2024; até a conferência, as contas seguem a 7229"
    },
    "ABNT NBR 13969": {
      "tipo": "ABNT",
      "assunto": "tratamento complementar e disposição final do efluente de tanque séptico; reúso",
      "edicao": "1997",
      "situacao": "conferir",
      "nota": "conferir se foi substituída pela ABNT NBR 17076:2024"
    },
    "ABNT NBR 17076": {
      "tipo": "ABNT",
      "assunto": "sistemas de tratamento de esgoto de menor porte",
      "edicao": "2024",
      "situacao": "conferir",
      "nota": "pode ter substituído as NBR 7229 e 13969; um engenheiro confere antes de trocar as contas"
    },
    "ABNT NBR 16783": {
      "tipo": "ABNT",
      "assunto": "uso de fontes alternativas de água não potável em edificações",
      "edicao": "2019",
      "situacao": "conferir",
      "nota": "classes de uso e qualidade mínima da água de reúso e de chuva"
    },
    "ABNT NBR 9649": {
      "tipo": "ABNT",
      "assunto": "projeto de redes coletoras de esgoto sanitário",
      "edicao": "1986",
      "situacao": "conferir",
      "nota": "origem do coeficiente de retorno água → esgoto"
    },
    "ABNT NBR 10844": {
      "tipo": "ABNT",
      "assunto": "instalações prediais de águas pluviais (calhas e condutores)",
      "edicao": "1989",
      "situacao": "conferir",
      "nota": "conferir se há revisão publicada"
    },
    "ABNT NBR 12211": {
      "tipo": "ABNT",
      "assunto": "estudos de concepção de sistemas públicos de abastecimento de água",
      "edicao": "1992",
      "situacao": "conferir",
      "nota": "só quando o projeto inclui rede pública (loteamento, condomínio)"
    },
    "ABNT NBR 12218": {
      "tipo": "ABNT",
      "assunto": "projeto de rede de distribuição de água para abastecimento público",
      "edicao": "2017",
      "situacao": "conferir",
      "nota": "só quando o projeto inclui rede pública (loteamento, condomínio)"
    },
    "Portaria GM/MS 888/2021": {
      "tipo": "regulamento",
      "assunto": "padrão de potabilidade da água para consumo humano",
      "edicao": "2021",
      "situacao": "conferir",
      "nota": "texto consolidado na Portaria de Consolidação 5/2017 do Ministério da Saúde; conferir a redação vigente"
    },
    "Resolução CONAMA 357/2005": {
      "tipo": "regulamento",
      "assunto": "classes de corpos d'água e padrões de qualidade",
      "edicao": "2005",
      "situacao": "conferir",
      "nota": "conferir alterações posteriores"
    },
    "Resolução CONAMA 430/2011": {
      "tipo": "regulamento",
      "assunto": "condições e padrões de lançamento de efluentes",
      "edicao": "2011",
      "situacao": "conferir",
      "nota": ""
    },
    "Lei 9.433/1997": {
      "tipo": "lei",
      "assunto": "Política Nacional de Recursos Hídricos (outorga do uso da água)",
      "edicao": "1997",
      "situacao": "vigente",
      "nota": "uso de água em turbina e captação pode exigir outorga ou dispensa no órgão gestor"
    },
    "ABNT NBR 16401-1": {
      "tipo": "ABNT",
      "assunto": "ar-condicionado central e unitário: projeto das instalações e carga térmica",
      "edicao": "2008",
      "situacao": "conferir",
      "nota": "conferir se há revisão publicada"
    },
    "ABNT NBR 16401-2": {
      "tipo": "ABNT",
      "assunto": "ar-condicionado: parâmetros de conforto térmico",
      "edicao": "2008",
      "situacao": "conferir",
      "nota": ""
    },
    "ABNT NBR 16401-3": {
      "tipo": "ABNT",
      "assunto": "ar-condicionado: qualidade do ar interior e vazões de ar externo",
      "edicao": "2008",
      "situacao": "conferir",
      "nota": ""
    },
    "ABNT NBR 14880": {
      "tipo": "ABNT",
      "assunto": "saídas de emergência: escada de segurança com controle de fumaça por pressurização",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": "nenhum arquivo nosso cita a edição; conferir também a Instrução Técnica do Corpo de Bombeiros do estado"
    },
    "ABNT NBR 15569": {
      "tipo": "ABNT",
      "assunto": "aquecimento solar de água em circuito direto: projeto e instalação",
      "edicao": "2020",
      "situacao": "conferir",
      "nota": "conferir a edição vigente"
    },
    "ABNT NBR 10339": {
      "tipo": "ABNT",
      "assunto": "piscinas: projeto, execução e manutenção",
      "edicao": "2018",
      "situacao": "conferir",
      "nota": "não traz método de carga térmica de aquecimento"
    },
    "ABNT NBR 15220": {
      "tipo": "ABNT",
      "assunto": "desempenho térmico de edificações e zoneamento bioclimático (partes 1 a 5)",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": "conferir a revisão vigente antes de usar o zoneamento em projeto"
    },
    "ABNT NBR 15575": {
      "tipo": "ABNT",
      "assunto": "edificações habitacionais: desempenho (partes 1 a 6)",
      "edicao": "2021",
      "situacao": "conferir",
      "nota": "edição de 2013 com emendas; conferir a versão vigente"
    },
    "ABNT NBR 5410": {
      "tipo": "ABNT",
      "assunto": "instalações elétricas de baixa tensão",
      "edicao": "2004 (versão corrigida 2008)",
      "situacao": "conferir",
      "nota": "conferir se há revisão publicada"
    },
    "ABNT NBR 5419": {
      "tipo": "ABNT",
      "assunto": "proteção contra descargas atmosféricas (SPDA), partes 1 a 4",
      "edicao": "2015",
      "situacao": "conferir",
      "nota": "propostas citam 2026; confirmar se há edição nova"
    },
    "ABNT NBR 16690": {
      "tipo": "ABNT",
      "assunto": "instalações elétricas de arranjos fotovoltaicos: requisitos de projeto",
      "edicao": "2019",
      "situacao": "conferir",
      "nota": ""
    },
    "ABNT NBR 16149": {
      "tipo": "ABNT",
      "assunto": "sistemas fotovoltaicos: características da interface de conexão com a rede",
      "edicao": "2013",
      "situacao": "conferir",
      "nota": ""
    },
    "ABNT NBR 16150": {
      "tipo": "ABNT",
      "assunto": "sistemas fotovoltaicos: ensaio de conformidade da interface com a rede",
      "edicao": "2013",
      "situacao": "conferir",
      "nota": "vale para o inversor (certificação Inmetro), não para o cálculo"
    },
    "ABNT NBR 16274": {
      "tipo": "ABNT",
      "assunto": "sistemas fotovoltaicos conectados à rede: documentação, comissionamento, inspeção e avaliação de desempenho",
      "edicao": "2014",
      "situacao": "conferir",
      "nota": ""
    },
    "IEC 61724-1": {
      "tipo": "ISO/IEC",
      "assunto": "monitoramento de desempenho de sistemas fotovoltaicos (definição do rendimento global PR)",
      "edicao": "2021",
      "situacao": "conferir",
      "nota": ""
    },
    "IEC 62619": {
      "tipo": "ISO/IEC",
      "assunto": "segurança de baterias de lítio para uso estacionário",
      "edicao": "2022",
      "situacao": "conferir",
      "nota": ""
    },
    "Lei 14.300/2022": {
      "tipo": "lei",
      "assunto": "marco legal da micro e minigeração distribuída (compensação de energia)",
      "edicao": "2022",
      "situacao": "vigente",
      "nota": "regra de transição do pagamento do uso da rede (Fio B) no art. 27"
    },
    "REN ANEEL 1.059/2023": {
      "tipo": "regulamento",
      "assunto": "regras de conexão e faturamento da micro e minigeração distribuída",
      "edicao": "2023",
      "situacao": "vigente",
      "nota": ""
    },
    "REN ANEEL 1.000/2021": {
      "tipo": "regulamento",
      "assunto": "regras de prestação do serviço de distribuição (inclui custo de disponibilidade)",
      "edicao": "2021",
      "situacao": "conferir",
      "nota": "conferir os valores mínimos de faturamento por tipo de ligação"
    },
    "IEC 61400-2": {
      "tipo": "ISO/IEC",
      "assunto": "turbinas eólicas pequenas: requisitos de projeto e segurança",
      "edicao": "2013",
      "situacao": "conferir",
      "nota": ""
    },
    "IEC 61400-12-1": {
      "tipo": "ISO/IEC",
      "assunto": "turbinas eólicas: medição da curva de potência",
      "edicao": "2022",
      "situacao": "conferir",
      "nota": "a curva de potência certificada sai deste ensaio"
    },
    "ABNT NBR 10151": {
      "tipo": "ABNT",
      "assunto": "acústica: medição e avaliação de ruído em áreas habitadas",
      "edicao": "2019",
      "situacao": "conferir",
      "nota": "edição de 2019 com emenda de 2020"
    },
    "IEC 61116": {
      "tipo": "ISO/IEC",
      "assunto": "guia de equipamentos eletromecânicos para pequenas centrais hidrelétricas",
      "edicao": "1992",
      "situacao": "conferir",
      "nota": ""
    },
    "ABNT NBR 11682": {
      "tipo": "ABNT",
      "assunto": "estabilidade de encostas",
      "edicao": "2009",
      "situacao": "conferir",
      "nota": ""
    },
    "ABNT NBR 6118": {
      "tipo": "ABNT",
      "assunto": "projeto de estruturas de concreto",
      "edicao": "2023",
      "situacao": "conferir",
      "nota": ""
    },
    "ABNT NBR 6120": {
      "tipo": "ABNT",
      "assunto": "ações para o cálculo de estruturas de edificações",
      "edicao": "2019",
      "situacao": "conferir",
      "nota": ""
    },
    "ABNT NBR 6122": {
      "tipo": "ABNT",
      "assunto": "projeto e execução de fundações",
      "edicao": "2022",
      "situacao": "conferir",
      "nota": ""
    },
    "ABNT NBR 6484": {
      "tipo": "ABNT",
      "assunto": "sondagem de simples reconhecimento com SPT",
      "edicao": "2020",
      "situacao": "conferir",
      "nota": ""
    },
    "ABNT NBR 9050": {
      "tipo": "ABNT",
      "assunto": "acessibilidade a edificações, mobiliário, espaços e equipamentos urbanos",
      "edicao": "2020",
      "situacao": "conferir",
      "nota": "edição de 2020 com emenda de 2021"
    },
    "ABNT NBR 12693": {
      "tipo": "ABNT",
      "assunto": "sistemas de proteção por extintores de incêndio",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": "a exigência final é da Instrução Técnica do Corpo de Bombeiros do estado"
    },
    "ABNT NBR 15526": {
      "tipo": "ABNT",
      "assunto": "redes de distribuição interna para gases combustíveis",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": "usada por analogia na linha de biogás"
    },
    "Lei 12.651/2012": {
      "tipo": "lei",
      "assunto": "Código Florestal (Áreas de Preservação Permanente, APP)",
      "edicao": "2012",
      "situacao": "vigente",
      "nota": "encosta acima de 45° = 100% de declividade (art. 4º, V)"
    },
    "Lei 6.766/1979": {
      "tipo": "lei",
      "assunto": "parcelamento do solo urbano",
      "edicao": "1979",
      "situacao": "vigente",
      "nota": "restrição de parcelar terreno com declividade de 30% ou mais (art. 3º, parágrafo único)"
    },
    "ABNT NBR 10004": {
      "tipo": "ABNT",
      "assunto": "classificação de resíduos sólidos (partes 1 e 2)",
      "edicao": "2024",
      "situacao": "vigente (revisada)",
      "nota": "conferir se as classes I, IIA e IIB usadas na tela continuam valendo na edição de 2024"
    },
    "ABNT NBR 10007": {
      "tipo": "ABNT",
      "assunto": "amostragem de resíduos sólidos",
      "edicao": "2004",
      "situacao": "conferir",
      "nota": "só quando a classe depende de ensaio de laboratório"
    },
    "ABNT NBR 15116": {
      "tipo": "ABNT",
      "assunto": "agregados reciclados para argamassas e concretos",
      "edicao": "2021",
      "situacao": "conferir",
      "nota": ""
    },
    "Resolução CONAMA 307/2002": {
      "tipo": "regulamento",
      "assunto": "gestão dos resíduos da construção civil (classes A a D)",
      "edicao": "2002",
      "situacao": "conferir",
      "nota": "conferir alterações posteriores"
    },
    "Resolução CONAMA 481/2017": {
      "tipo": "regulamento",
      "assunto": "compostagem de resíduos orgânicos",
      "edicao": "2017",
      "situacao": "conferir",
      "nota": ""
    },
    "Portaria MMA 280/2020": {
      "tipo": "regulamento",
      "assunto": "Manifesto de Transporte de Resíduos (MTR) nacional no SINIR",
      "edicao": "2020",
      "situacao": "conferir",
      "nota": ""
    },
    "Lei 12.305/2010": {
      "tipo": "lei",
      "assunto": "Política Nacional de Resíduos Sólidos (ordem de prioridade e logística reversa)",
      "edicao": "2010",
      "situacao": "vigente",
      "nota": ""
    },
    "GHG Protocol": {
      "tipo": "referência técnica",
      "assunto": "padrão corporativo de inventário de emissões e guia do escopo 2",
      "edicao": "2004 / 2015",
      "situacao": "vigente",
      "nota": "no Brasil, ferramenta do Programa Brasileiro GHG Protocol"
    },
    "ISO 14064-1": {
      "tipo": "ISO/IEC",
      "assunto": "inventário de gases de efeito estufa de organizações",
      "edicao": "2018",
      "situacao": "vigente",
      "nota": ""
    },
    "ISO 14068-1": {
      "tipo": "ISO/IEC",
      "assunto": "neutralidade de carbono",
      "edicao": "2023",
      "situacao": "vigente",
      "nota": ""
    },
    "Fator médio do SIN (MCTI)": {
      "tipo": "referência técnica",
      "assunto": "fator de emissão da energia elétrica da rede brasileira",
      "edicao": "por ano",
      "situacao": "conferir",
      "nota": "o fator muda todo ano; conferir o ano usado"
    },
    "Lei 15.042/2024": {
      "tipo": "lei",
      "assunto": "Sistema Brasileiro de Comércio de Emissões (SBCE)",
      "edicao": "2024",
      "situacao": "conferir",
      "nota": "faixas de 10 mil e 25 mil tCO₂e por ano para relatar e para cumprir metas; conferir a regulamentação"
    },
    "ISO 50001": {
      "tipo": "ISO/IEC",
      "assunto": "sistema de gestão de energia",
      "edicao": "2018 (Amd 1:2024)",
      "situacao": "vigente",
      "nota": ""
    },
    "ISO 50006": {
      "tipo": "ISO/IEC",
      "assunto": "linha de base e indicadores de desempenho energético (EnB e EnPI)",
      "edicao": "2023",
      "situacao": "conferir",
      "nota": ""
    },
    "ISO 50015": {
      "tipo": "ISO/IEC",
      "assunto": "medição e verificação do desempenho energético",
      "edicao": "2014",
      "situacao": "conferir",
      "nota": ""
    },
    "IPMVP": {
      "tipo": "referência técnica",
      "assunto": "protocolo internacional de medição e verificação de economia (EVO)",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": ""
    },
    "ISO 14001": {
      "tipo": "ISO/IEC",
      "assunto": "sistema de gestão ambiental",
      "edicao": "2015 (Amd 1:2024)",
      "situacao": "vigente",
      "nota": "revisão prevista; conferir se já foi publicada"
    },
    "ISO 45001": {
      "tipo": "ISO/IEC",
      "assunto": "sistema de gestão de saúde e segurança do trabalho",
      "edicao": "2018",
      "situacao": "vigente",
      "nota": ""
    },
    "ABNT NBR ISO 31000": {
      "tipo": "ABNT",
      "assunto": "gestão de riscos: diretrizes",
      "edicao": "2018",
      "situacao": "vigente",
      "nota": ""
    },
    "ISO 14091": {
      "tipo": "ISO/IEC",
      "assunto": "adaptação à mudança do clima: vulnerabilidade, impactos e riscos",
      "edicao": "2021",
      "situacao": "conferir",
      "nota": ""
    },
    "LEED v5": {
      "tipo": "certificação",
      "assunto": "certificação de edificações (USGBC/GBCI)",
      "edicao": "v5",
      "situacao": "vigente",
      "nota": "v4.1 só como legado (projetos já registrados)"
    },
    "EDGE": {
      "tipo": "certificação",
      "assunto": "certificação de eficiência em recursos (IFC)",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": ""
    },
    "Portaria Inmetro nº 309/2022": {
      "tipo": "regulamento",
      "assunto": "INI-C e INI-R (PBE Edifica)",
      "edicao": "2022",
      "situacao": "vigente",
      "nota": "o RTQ-R e o RTQ-C são as regras antigas"
    },
    "Selo Casa Azul": {
      "tipo": "certificação",
      "assunto": "selo de sustentabilidade da CAIXA",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": ""
    },
    "TRUE Zero Waste": {
      "tipo": "certificação",
      "assunto": "certificação de lixo zero (GBCI)",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": "meta de 90% de desvio do aterro"
    },
    "Lei 10.711/2003": {
      "tipo": "lei",
      "assunto": "Sistema Nacional de Sementes e Mudas (registro RENASEM de quem produz ou vende mudas)",
      "edicao": "2003",
      "situacao": "conferir",
      "nota": "conferir o decreto regulamentador vigente"
    },
    "Lei 13.709/2018": {
      "tipo": "lei",
      "assunto": "Lei Geral de Proteção de Dados (LGPD); dado de saúde é sensível (art. 11)",
      "edicao": "2018",
      "situacao": "vigente",
      "nota": ""
    },
    "Lei 13.146/2015": {
      "tipo": "lei",
      "assunto": "Lei Brasileira de Inclusão (LBI)",
      "edicao": "2015",
      "situacao": "vigente",
      "nota": "acessibilidade digital no art. 63"
    },
    "ABNT NBR 17225": {
      "tipo": "ABNT",
      "assunto": "acessibilidade em conteúdo e aplicações web: requisitos",
      "edicao": "2025",
      "situacao": "conferir",
      "nota": ""
    },
    "WCAG 2.2": {
      "tipo": "referência técnica",
      "assunto": "diretrizes de acessibilidade para conteúdo web (W3C), nível AA",
      "edicao": "2023",
      "situacao": "vigente",
      "nota": ""
    },
    "Lei 8.078/1990": {
      "tipo": "lei",
      "assunto": "Código de Defesa do Consumidor (informação clara de preço)",
      "edicao": "1990",
      "situacao": "vigente",
      "nota": ""
    },
    "Decreto 7.962/2013": {
      "tipo": "regulamento",
      "assunto": "comércio eletrônico (informações obrigatórias na venda pela internet)",
      "edicao": "2013",
      "situacao": "vigente",
      "nota": ""
    },
    "ASHRAE Handbook Fundamentals": {
      "tipo": "referência técnica",
      "assunto": "métodos de carga térmica, psicrometria e perdas de piscina",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": "livro técnico, não é norma brasileira"
    },
    "Duffie & Beckman": {
      "tipo": "referência técnica",
      "assunto": "engenharia solar: radiação extraterrestre e geometria solar",
      "edicao": "4ª ed., 2013",
      "situacao": "vigente",
      "nota": "livro técnico"
    },
    "FAO-56": {
      "tipo": "referência técnica",
      "assunto": "evapotranspiração de culturas (boletim de irrigação e drenagem nº 56)",
      "edicao": "1998",
      "situacao": "vigente",
      "nota": "boletim técnico, não é norma"
    },
    "sem norma aplicável": {
      "tipo": "—",
      "assunto": "não há norma técnica que fixe este cálculo; vale o método de referência descrito",
      "edicao": "—",
      "situacao": "—",
      "nota": ""
    },
    "Embrapa Café": {
      "tipo": "referência técnica",
      "assunto": "pós-colheita, secagem e armazenamento do café (Embrapa Café e Consórcio Pesquisa Café)",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": "publicações técnicas; conferir a mais recente"
    },
    "IN MAPA 8/2003": {
      "tipo": "regulamento",
      "assunto": "regulamento técnico de identidade e qualidade para a classificação do café beneficiado grão cru",
      "edicao": "2003",
      "situacao": "conferir",
      "nota": "conferir se houve atualização do regulamento"
    },
    "ASHRAE 93": {
      "tipo": "referência técnica",
      "assunto": "métodos de ensaio do desempenho térmico de coletores solares",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": "norma americana; base para medir a eficiência do coletor"
    },
    "IPCC 2006": {
      "tipo": "referência técnica",
      "assunto": "diretrizes para inventários nacionais de gases de efeito estufa (vol. 5: resíduos e efluentes)",
      "edicao": "2006",
      "situacao": "conferir",
      "nota": "com o Refinamento de 2019"
    },
    "ISO/IEC 30134-2": {
      "tipo": "ISO",
      "assunto": "indicadores de datacenter: eficiência no uso da energia (PUE)",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": ""
    },
    "ASHRAE TC 9.9": {
      "tipo": "referência técnica",
      "assunto": "faixas de temperatura e umidade para salas de equipamentos de TI",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": "orientação técnica, não é norma brasileira"
    },
    "ITU-T L.1450": {
      "tipo": "referência técnica",
      "assunto": "métodos para a pegada ambiental do setor de tecnologia da informação e comunicação",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": ""
    },
    "IEC 62040-3": {
      "tipo": "IEC",
      "assunto": "sistemas de alimentação ininterrupta (nobreak): desempenho e ensaios",
      "edicao": "a conferir",
      "situacao": "conferir",
      "nota": ""
    }
  }
};
/*DADOS-FIM*/
const SELO = { "conforme":"ok", "simplificado":"at", "falta implementar":"al", "só citado":"in" };
const ROTULO = { "conforme":"Conforme", "simplificado":"Simplificado", "falta implementar":"Falta implementar", "só citado":"Só citado" };
const e = s => (typeof esc === "function") ? esc(s == null ? "" : String(s))
  : String(s == null ? "" : s).replace(/[&<>"']/g, ch => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[ch]));
const idSeguro = s => String(s).replace(/[^\w-]/g, "_");
const selo = st => `<span class="selo ${SELO[st] || "in"}">${e(ROTULO[st] || st)}</span>`;

function tabelaVariaveis(cx) { const l = (cx.formula && cx.formula.variaveis) || []; if (!l.length) return "";
  return `<div class="rolagem"><table><caption class="t2 pq">Variáveis de ${e(cx.nome)}</caption><thead><tr><th scope="col">Símbolo</th><th scope="col">O que é</th><th scope="col">Unidade</th></tr></thead><tbody>`
    + l.map(x => `<tr><th scope="row">${e(x.simbolo)}</th><td>${e(x.significado)}</td><td>${e(x.unidade)}</td></tr>`).join("") + `</tbody></table></div>`; }

function tabelaNormas(cx) { const l = cx.normas || []; if (!l.length) return "";
  return `<div class="rolagem"><table><caption class="t2 pq">Normas e referências de ${e(cx.nome)}</caption><thead><tr><th scope="col">Norma</th><th scope="col">Edição</th><th scope="col">Item</th><th scope="col">Como é usada</th></tr></thead><tbody>`
    + l.map(x => { const cat = DADOS.normas[x.codigo] || {}, conferir = /conferir/.test(cat.situacao || "");
      return `<tr><th scope="row">${e(x.codigo)}</th><td>${e(x.edicao || "—")}${conferir ? ` <span class="selo at">conferir</span>` : ""}</td><td>${e(x.item || "—")}</td><td>${e(x.como_e_usada || "")}</td></tr>`; }).join("")
    + `</tbody></table></div>`; }

function calculoHtml(cx, h) { const id = "met-c-" + idSeguro(cx.id), pr = cx.premissas || [];
  const linha = (rot, txt) => txt ? `<li><strong>${rot}:</strong> ${e(txt)}</li>` : "";
  return `<section class="met-calculo" aria-labelledby="${id}"><h${h} id="${id}" class="t3">${e(cx.nome)} ${selo(cx.status)}</h${h}>`
    + `<p>${e(cx.o_que_calcula)}</p><p><strong>Conta:</strong> <code style="white-space:normal">${e(cx.formula && cx.formula.texto)}</code></p>`
    + tabelaVariaveis(cx) + tabelaNormas(cx)
    + `<ul class="t2">${linha("Premissas da base", pr.join(", "))}${linha("Vale para", cx.limites_de_validade)}${linha("Dados de", cx.fonte_de_dados)}${linha("O que falta", cx.o_que_falta)}${linha("No código", cx.onde)}</ul></section>`; }

function metodologiaHtml(modulo, opcoes) { const m = DADOS.modulos[modulo]; if (!m) return "";
  const o = opcoes || {}, nivel = Math.min(Math.max(Math.round(+o.nivel) || 2, 2), 5), id = "met-" + idSeguro(modulo), calcs = m.calculos || [];
  const cont = {}; calcs.forEach(x => { cont[x.status] = (cont[x.status] || 0) + 1; });
  const sit = Object.keys(ROTULO).filter(k => cont[k]).map(k => `${selo(k)} ${cont[k]}`).join(" ");
  const corpo = calcs.length ? calcs.map(cx => calculoHtml(cx, Math.min(nivel + 1, 6))).join("") : `<p class="t2">${e(m.sem_calculo || "Sem cálculo próprio.")}</p>`;
  return `<section class="cartao metodologia" aria-labelledby="${id}-h"><h${nivel} id="${id}-h"${nivel > 2 ? ' class="t3"' : ""}>Metodologia e normas</h${nivel}>`
    + `<details data-metodologia="${e(modulo)}"><summary>Ver como cada conta é feita e quais normas segue (${calcs.length} ${calcs.length === 1 ? "cálculo" : "cálculos"})</summary>`
    + `<p class="t2 pq" role="note">${e(DADOS.aviso)}</p>${m.resumo ? `<p class="t2">${e(m.resumo)}</p>` : ""}${sit ? `<p class="t2 pq">Situação: ${sit}</p>` : ""}${corpo}`
    + `<p class="t2 pq">Conforme: segue a norma ou o método de referência. Simplificado: segue o caminho da norma com hipóteses mais simples. Só citado: a norma aparece, mas a conta não a aplica. Falta implementar: a conta ainda não segue o que a norma ou a lei pede.</p></details></section>`; }

window.PHYSIS_METODOLOGIA = DADOS;
window.metodologiaHtml = metodologiaHtml;
})();
