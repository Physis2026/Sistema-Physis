# Mapeamento: o contexto do lugar

Situação: **em desenvolvimento** (fora da loja pública; aparece com o selo na Casa Physis). Pedido de 15/11/2026.

## Para que serve

O Mapeamento é o lugar de onde todos os outros módulos leem o terreno. Ele **depende do Início** (dados obrigatórios do
cliente, com a localização) e do **lote do Planejador**. Ele junta mapas abertos, arquivos do cliente e o sol, e entrega:

- o **contexto do lugar** (um documento JSON por instalação, cada campo com a fonte);
- o **sol em cada superfície** (telhados, fachadas, células do terreno);
- a **planta solar** (onde vão as placas, quantas, a curva do dia, a energia, strings e fator de potência);
- o **modelo BIM aberto** (IFC4) com o que os módulos dimensionaram.

Quem lê: Planejador, AVAC, Solar, SbN, Água, Resiliência e Carbono. Os módulos mandam de volta o que
dimensionaram, e isso aparece no BIM.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `physis-hub/physis_hub/mapeamento.py` | Catálogo de camadas, recorte, arquivos do cliente, contexto, sol, planta solar, rotas |
| `physis-hub/physis_hub/ifc.py` | Escreve e lê IFC4 (só biblioteca padrão) |
| `sistema/physis-mapeamento.js` | A tela (pt/en, acessível, claro e escuro); espelho das contas do sol |
| `modulos/mapeamento/exemplos/` | Pacote de **exemplo com dados fictícios** e o gerador `gerar_exemplos.py` |
| `ferramentas/testes-navegador/conferir-modelos.html` | Abre o exemplo nos visualizadores e mostra a lista de conferência |
| `physis-hub/tests/test_mapeamento.py`, `test_ifc.py` | Testes |

## Fase 1 (feito)

1. **Catálogo de camadas** (12): limites IBGE, relevo e declividade (Copernicus DEM, SRTM ou TOPODATA), hidrografia
   ANA BHO (a rota `/api/gis/hidrografia` continua), uso do solo MapBiomas, solos Embrapa, CAR/SICAR, clima INMET em EPW,
   risco SGB/CEMADEN, irradiação do Atlas Solarimétrico (LABREN), vento do Atlas eólico (CRESESB), rede ANEEL SIGEL,
   edificações e vias do OpenStreetMap. Cada uma tem nome pt/en, para quê, quem usa, fonte, licença, formato e o lugar no
   servidor. **Nenhum dado vem copiado**; fonte, produto e licença estão marcados [CONFERIR].
2. **O servidor lê as camadas instaladas** na pasta `PHYSIS_CAMADAS` e entrega cada uma recortada na janela do lote:
   vetor em GeoJSON (pontos, linhas e polígonos recortados de verdade); raster como resumo (mínimo, média, máximo,
   declividade, parcela de cada classe de uso do solo). O raster fica em grade ESRI ASCII (`.asc`), gerada uma vez pelo
   GDAL num contêiner Linux (passo abaixo). Dentro do servidor, só biblioteca padrão.
3. **Arquivos do cliente**: GeoJSON, KML/KMZ e Shapefile em `.zip` (`.shp`, `.dbf`, `.prj`). O leitor de Shapefile é
   nosso e aceita pontos, linhas e polígonos (com Z e M ignorados); MultiPatch e outros tipos são recusados com aviso
   claro. Coordenadas aceitas: **EPSG:4326 (WGS 84)** e **EPSG:4674 (SIRGAS 2000 geográfico)**, tratado como WGS 84
   (diferença abaixo de 1 m; a nota fica no índice). Projetado (UTM) é recusado com a instrução de reprojetar. Limite:
   20 MB, 20.000 feições, 500.000 vértices. Original e GeoJSON padronizado ficam em disco (`PHYSIS_MAPEAMENTO_PASTA`) e o
   índice no SQLite (`mapeamento_upload`) com os dois SHA-256; arquivo adulterado não é entregue.
4. **Contexto do lugar**: área, declividade, rios e nascentes, uso do solo, solo, CAR, clima, irradiação, vento, risco,
   rede elétrica e prédios, cada um com a fonte. Camada que falta aparece como **"camada não instalada"**; nunca um valor
   inventado. Sem localização, o documento pede o Início.
5. **Sol nas superfícies**: a mesma conta da aba Solar (`PhysisCalc.fatorPlano`: Liu e Jordan, fração difusa de Erbs)
   mais a **sombra do horizonte**: marcha de raio no terreno do Planejador e nas caixas dos prédios, em 36 direções.
   Mapa de calor do terreno e tabelas de telhados e fachadas. Vai para a Solar e o AVAC em `physis-calc-incidencia`.
6. **Planta solar (BIM)** (prioridade 0). **Mora na aba Energia solar** (pedido de 15/11/2026: "planta solar deve estar na
   mesma aba de energia solar"): a sub-aba "Planta solar (BIM)" da Solar chama `PhysisMapeamento.telaPlantaSolar()` deste
   módulo (as mesmas funções, sem cópia) e leva o selo **Em desenvolvimento** até a revisão. No Mapeamento fica só um
   aviso com o link para a Solar; o **Sol nas superfícies** continua aqui (é contexto que a Solar e o AVAC leem).
   Um número só de geração: ao enviar a planta (`physis-calc-planta-solar`), o dimensionamento da Solar passa a usar o
   kWp, o módulo e o fator do plano da planta (escolha "Sistema usado nas contas"), e os cartões dizem a fonte.
   - escolha onde vai a planta: águas de telhado do Planejador ou área no solo (lote inteiro ou retângulo desenhado),
     cada uma com a irradiação que recebe;
   - arranjo: módulo da base de equipamentos (medidas tiradas da descrição da base, ou digitadas), retrato ou paisagem,
     módulos por mesa, inclinação e azimute (no solo), passo entre fileiras, afastamento das bordas e folga entre
     módulos; edificações no solo viram obstáculos;
   - **sombra entre fileiras** no solstício de inverno, nas horas críticas: sombra = altura da mesa × cos(Δazimute) ÷
     tan(altura do sol); passo vazio = o mínimo sem sombra;
   - **carta solar** do lugar com nascer e pôr do sol e o **perfil do horizonte** (terreno e vizinhos);
   - **o dia desde o nascer do sol**: irradiância no plano das placas e potência CA estimada, para o dia médio de cada
     mês e para solstícios e equinócios. A irradiação do dia é distribuída hora a hora (Collares-Pereira e Rabl para a
     global, Liu e Jordan para a difusa) e **reescalada para fechar com o total do mês da aba Solar**;
   - energia do mês e do ano: **a conta da própria aba Solar** (`SOLAR.calcular`), com o fator do plano daqui (já com a
     sombra do horizonte); temperatura da célula e perdas também da aba Solar (`tCelula`, `fTemp`, `PERDAS_PADRAO`);
   - elétrica: inversor da base, strings pela função da aba Solar (`SOLAR.strings`), e sempre o fator de potência com
     P, Q e S (`PhysisCalc.potencias`, premissa `eletrica.fator_potencia_padrao`);
   - saída: `physis-calc-planta-solar` para a aba Solar e elementos para o BIM.
7. **BIM aberto (IFC4)**: IfcProject, IfcSite com latitude e longitude, IfcBuilding, IfcBuildingStorey e os sistemas:
   arranjo FV (IfcSolarDevice, com os módulos agregados), inversor (IfcTransformer .INVERTER.), cisterna (IfcTank),
   calhas e condutores (IfcPipeSegment), AVAC (IfcUnitaryEquipment), quadro (IfcElectricDistributionBoard), turbinas
   (IfcElectricGenerator), biodigestor, canteiros e suportes (IfcBuildingElementProxy). Propriedades com
   unidade; materiais da base com quantidade e carbono; **todo equipamento elétrico leva fator de potência, P, Q e S**.
   Leitor básico (sem núcleo de geometria): esquema, terreno, edificações, pavimentos, contagem por tipo e tamanho.
8. **Contrato com o motor de simulação** (outro agente, `physis_hub/simulacao`), esquema `physis-geometria-lugar/1`
   (`mapeamento.geometria_para_simulacao`; na tela, `physis-geometria-lugar`): terreno em grade (x leste, y norte, Z),
   caixas das edificações, superfícies com orientação e irradiação, e os materiais de cada elemento BIM com densidade,
   condutividade, calor específico e carbono. Só dados: o Mapeamento não faz essas simulações.

### Formato que os módulos mandam para o BIM

Cada módulo grava, com `MAPEAMENTO.enviarParaBim(modulo, elementos)`, uma lista no formato do `ifc.escrever`:
`{id, tipo, nome, pavimento, posicao:{x,y,z}, caixa:{dx,dy,dz}, propriedades:{chave: valor ou {valor, unidade}}, materiais:[{id, quantidade, unidade}], memorial}`.
Tipos: `pv, inversor, cisterna, calha, condutor, avac, quadro, turbina, biodigestor, canteiro, rack`.

### Rotas

| Rota | O que faz | Acesso |
|---|---|---|
| `GET /api/mapeamento/camadas` | Catálogo com o estado de cada camada | aberto (como as outras de GIS) |
| `GET /api/mapeamento/camada?id=&bbox=` | Camada recortada | aberto |
| `GET` / `POST /api/mapeamento/contexto` | Contexto do lugar (POST leva o lote do Planejador e a irradiação da aba Solar) | cliente |
| `GET /api/mapeamento/uploads`, `POST /api/mapeamento/upload` (corpo cru, cabeçalho `X-Physis-Nome`), `GET/DELETE /api/mapeamento/upload?id=` | Arquivos do cliente | cliente |
| `POST /api/mapeamento/incidencia` | Sol nas superfícies no servidor | cliente |
| `POST /api/mapeamento/planta-solar` | Arranjo e carta solar no servidor | cliente |
| `POST /api/mapeamento/ifc` | Gera o IFC (devolve o arquivo) | cliente |
| `POST /api/mapeamento/ifc/ler` | Resumo de um IFC enviado | cliente |

### Passo GDAL (raster), fora do servidor

O GDAL (licença MIT/X [CONFERIR]) roda num contêiner Linux, uma vez por região, para recortar e converter o GeoTIFF
oficial em grade `.asc` (graus, EPSG:4326):

    docker run --rm -v /dados/camadas:/d ghcr.io/osgeo/gdal:ubuntu-small-latest \
      gdal_translate -of AAIGrid -projwin <lon_min> <lat_max> <lon_max> <lat_min> /d/original.tif /d/relevo.asc

(a imagem e a etiqueta [CONFERIR]; se o original não estiver em EPSG:4326, `gdalwarp -t_srs EPSG:4326` antes). Vetores
grandes: `ogr2ogr -f GeoJSON -clipsrc <lon_min> <lat_min> <lon_max> <lat_max> saida.geojson original.shp`.

### Premissas usadas e a criar

- `eletrica.fator_potencia_padrao` (já existe na base, 0,92, status conferir).
- **A criar em `sistema/physis-premissas.json`** (até lá, a tela pede o valor): `solar.arranjo_afastamento_borda` (m),
  `solar.arranjo_folga_modulos` (m), `solar.arranjo_hora_critica_inicio` e `solar.arranjo_hora_critica_fim` (hora
  solar no solstício de inverno). Todas [CONFERIR] com a norma e o fabricante do suporte.

## CEP do Início (15/11/2026)

Regra do dono: **CEP obrigatório; latitude e longitude opcionais e preenchidas com o CEP**.
- O navegador nunca chama o provedor: pede ao servidor `GET /api/local/cep/<cep>` (sessão, limite por IP `PHYSIS_LIMITE_CEP`,
  cache de 30 dias na tabela `cep_cache`). Vai para o provedor **só o CEP**, com User-Agent genérico (LGPD); a tela avisa.
- `PHYSIS_CEP_PROVEDOR` (ordem, vírgula): `brasilapi` (BrasilAPI CEP v2, pode trazer coordenadas), `viacep` (endereço,
  município e código IBGE), `nominatim` (instância própria em `PHYSIS_NOMINATIM_URL`; a pública só dentro da política de
  uso: 1 pedido por segundo, User-Agent descritivo) ou `desligado`. Padrão `brasilapi,viacep`. **[CONFERIR]** os termos de
  uso de cada um na página oficial antes de ligar em produção.
- Sem coordenadas do provedor: **não há centróide do município embutido** (falta uma base do IBGE com licença conferida);
  a tela diz "coordenadas não encontradas — marque no mapa". Nunca um ponto inventado.
- Fonte das coordenadas (`fonte_coordenadas` em `localDaInstalacao()` e `hub.local_da_instalacao()`): "cep" (aproximado),
  "mapa" ou "digitado"; mapa e digitado valem sobre o CEP. Solar, planta solar e previsão mostram "Local aproximado pelo
  CEP" quando a fonte é o CEP.
- Sem internet ou provedor desligado: o CEP continua obrigatório, o endereço é digitado e as coordenadas são opcionais.
- Testes: `tests/test_cep.py`.

**Tarefa do Eric (Fase 2):** subir um Nominatim próprio (contêiner Linux, extrato do Brasil do OpenStreetMap) e uma base
de CEP/municípios do IBGE com licença conferida (centróides), para a consulta não depender de serviços de fora; depois
trocar `PHYSIS_CEP_PROVEDOR` para `nominatim` e preencher `PHYSIS_NOMINATIM_URL`.

## Fase 2 (ainda não feito)

- Instalar as bases nacionais no servidor (com o Eric): baixar, conferir licença, recortar e manter atualizado.
- Luz natural com Ladybug Tools e Radiance (anual e por ambiente).
- EnergyPlus multizona a partir do BIM (zonas e materiais do IFC).
- Escoamento de ar com OpenFOAM (vento em volta dos prédios, ventilação natural).
- Visualizador IFC completo (geometria): web-ifc com three.js, já guardados em `vendor/` (web-ifc: MPL-2.0; three.js:
  MIT [CONFERIR]) ou That Open Engine (MIT [CONFERIR]); IfcOpenShell (LGPL-3.0 [CONFERIR]) no servidor.
- Fator de visão do céu anisotrópico (Perez) e sombra por módulo na curva do dia.

## Licenças

| O quê | Licença |
|---|---|
| Código do Mapeamento | da Physis (código aberto do Sistema Physis) |
| IFC4 / ISO 16739-1 (buildingSMART) | padrão aberto [CONFERIR os termos de uso do esquema] |
| IBGE, ANA, Embrapa, SICAR, INMET, SGB, CEMADEN, INPE/LABREN, CEPEL/CRESESB, ANEEL | dados públicos; uso com citação [CONFERIR cada uma] |
| Copernicus DEM | licença própria, livre com atribuição [CONFERIR] |
| SRTM | domínio público [CONFERIR] |
| MapBiomas | CC BY 4.0 [CONFERIR] |
| OpenStreetMap | ODbL 1.0, com atribuição e compartilhamento pela mesma licença do banco derivado [CONFERIR] |
| GDAL | MIT/X [CONFERIR] |
| web-ifc / three.js / That Open Engine / IfcOpenShell | MPL-2.0 / MIT / MIT / LGPL-3.0 [CONFERIR] |
| Ladybug Tools, Radiance, EnergyPlus, OpenFOAM (Fase 2) | GPL-3.0 / licença Radiance (BSD) / BSD-3 / GPL-3.0 [CONFERIR] |

## Como conferir

    cd physis-hub
    python -W ignore -m unittest tests.test_mapeamento tests.test_ifc
    python ../modulos/mapeamento/exemplos/gerar_exemplos.py
    # na raiz do repositório: python -m http.server 8850 --bind 127.0.0.1
    # abrir /ferramentas/testes-navegador/conferir-modelos.html (lista de conferência: 23 itens)
