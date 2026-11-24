# Gêmeo digital da Casa Physis · G0–G3 (versão de TESTE)

Desenho aprovado pela dona em 21/11/2026: `Documents\Sistema Physis\47_Gemeo_Digital_Casa_Physis_TESTE.md`
(seções 3, 6 e 7). Tarefa no M&A: `casa-gemeo-g0-g1`. Ramo: `teste/casa-gemeo-g0-g1` (sem merge no main sem aprovação).

## O que existe

| Peça | Onde | O que faz |
|---|---|---|
| Núcleo | `physis_hub/gemeo.py` | Zonas e entidades, estados de vida, valor com procedência, leitura da semente, totais por zona, validação. Pontos (`gemeo_ponto`) e cenários (`gemeo_cenario`) só em `ESQUEMA_SQL`: o hub ainda não cria as tabelas |
| Importador | `physis_hub/gemeo_importar.py` | Planilhas 20 e 03 (e 18 só para citar D5) → projeto `physis.terreno/1.0` com o campo `gemeo`. Lê .xlsx sem dependências; para com erro se faltar um rótulo |
| Semente rev0 | `modulos/planejador/gemeo/casa-physis-rev0.json` | Abre no Planejador por "Abrir projeto" (nada no Planejador foi mudado) |
| IFC 3D (G3) | `physis_hub/gemeo_ifc.py` → `modulos/planejador/gemeo/casa-physis-rev0.ifc` | IFC4 do lote: 92 elementos (72 com sólido), terreno pelas curvas de nível, 3 zonas, cor da entidade, marcado estudo preliminar, sem lat/long |
| Comparador de versões | `physis_hub/gemeo_versoes.py`, modelos em `modulos/planejador/gemeo/versoes/` | Várias plantas do mesmo lote: filtro de normas e segurança, ranking por custo-benefício, projeto e IFC por versão |
| Testes | `tests/test_gemeo.py` | 32 testes; os 2 da classe `Acervo` só rodam onde as planilhas existem |

Refazer a semente quando a planilha 20 ou a 03 mudar (o teste `Acervo` acusa semente desatualizada):

    cd physis-hub
    python -m physis_hub.gemeo_importar --saida ../modulos/planejador/gemeo/casa-physis-rev0.json
    # pasta das planilhas: --editaveis PASTA ou PHYSIS_CASA_EDITAVEIS

Ver em 3D: abrir o Planejador pela plataforma (o 3D usa `/vendor/`), anexar `casa-physis-rev0.ifc` no Início e
clicar em "Ver em 3D e áreas" (arrastar gira, roda do mouse aproxima). Refazer o IFC depois de refazer a semente:

    python -m physis_hub.gemeo_ifc

Alturas no 3D (decisão pg:16228b14d400): edificações do 20 › Quadro de áreas com 2,90 m (LAB/MEC de cima − de baixo
na 03); o resto é placa de 0,20 m só de desenho; tudo [CONFERIR] até o executivo. Sem cota na 03 → cota do terreno
interpolada. O terreno é aproximado pelas curvas (não é levantamento 3D).

## Comparar versões de planta

Critério da dona (M&A pg:97b6e5a48dcf): normas e segurança eliminam; entre as que passam, melhor custo-benefício.

    python -m physis_hub.gemeo_versoes versao_B.csv versao_C.xlsx --masterplan --precos precos.csv         --saida comparacao.json --ifc versoes_ifc

- Versão = CSV no formato de `versoes/MODELO_versao.csv` (é a rev0; copiar e alterar) ou .xlsx com a aba Implantação
  no leiaute da 03. `--masterplan` junta as 6 combinações da 03 › Estudos de masterplan (avaliação parcial, sem planta).
- Filtro: edificação fora do perímetro, edificações sobrepostas no mesmo nível, ocupação acima de 40 % (03).
  Sinaliza sem eliminar o desnível > 1,5 m sob a projeção, com a mesma conta e o mesmo limiar do Planejador
  (`TerrenoPlanejador` espelha `T.build`/`T.z`; valores conferidos no navegador e fixados no teste).
- Ranking: custo por m² de edificação só com preço com fonte (`versoes/MODELO_precos.csv`, vem vazio); sem preço,
  [MARCADOR] e ranking por módulos presentes, lofts e terra movida.
- `--ifc` grava o projeto do Planejador e o IFC de cada versão (os números da planilha 20 ficam só na rev0).
- Não confere: recuos (a 03 não tem os parâmetros municipais), estrutura, incêndio, acessibilidade detalhada.
  O Planejador confere mais coisas ao abrir o projeto de cada versão; é triagem, não substitui o responsável técnico.

## Espelho, norte e coordenada (22/11/2026)

- A planta local da 03 é um espelho leste–oeste da realidade: a grade UTM da imagem do levantamento dá +y (P-01→P-05)
  a 16,9° e +x (P-01→P-02) a 286,7°, como a 20 › Perímetro (17° e 287°). O gêmeo vira o x (x = −x_03; giros com sinal
  trocado); a 03 fica como está (pg:0fc4161d708b). D10 resolvida.
- Norte verdadeiro: +y a 17° (TrueNorth = (−sen 17°, cos 17°)) [CONFERIR com o topógrafo, pg:afe44bbf677a].
- Coordenada do P-01 lida na grade UTM 23S SAD-69: E 691.161,7 / N 7.518.862,0 → lat −22,4257, lon −43,1427,
  estimada (pg:63cd2ce2f829). No Planejador: terreno.lat0/lon0; no IFC: IfcSite RefLatitude/RefLongitude.

## Regras da semente

- Fontes (R1-1): números de sistemas da planilha 20; geometria da 03 (Implantação + Levantamento). Cada valor de
  `gemeo.fonte_por_valor` tem `fonte` (planilha › aba, linha, coluna), `procedencia` (hoje tudo `estimado`, estudo
  preliminar rev 0), `zona` e `entidade` (Z1 Physis Engineering, Z2 Instituto Physis, Z3 Casa Physis; `lote` para
  totais e sistemas que servem a mais de uma zona).
- Divergências D1–D6 ficam no próprio valor como `conferir: {divergencia, alternativas: [{valor, fonte}]}`.
- D5 (consumo mensal) fica vazio com `[MARCADOR]`: a 20 não traz o número (decisão da dona, M&A pg:310a1c0db09d).
- x/y da 03 › Implantação = canto do retângulo (confirmado, M&A pg:8d264ca11dc1); o item do Planejador guarda o centro.
- O arco P-04→P-05 do levantamento (R 19,464 m) é desenhado com a flecha para dentro: assim a área do polígono
  (1.456,2 m²) bate com a do levantamento (1.455,95 m²). Pela corda daria ≈ 1.494 m².
- Camada medida vazia, "aguardando sensores" (R1-2). Estado de vida de todos os elementos: `projetado`.
- Só dados de projeto (R2-3): pode ir para os artigos.

## Números de conferência (rev0)

92 elementos (Z1 18, Z2 40, Z3 34); corte 489,3 m³ e aterro 24,8 m³ (linha Total da 03); lote 1.455,95 m²; área
construída 435,5 m² e projeção 343,2 m² (20, somam as linhas do quadro); reservação 220 m³ (soma das cisternas).

## Não feito (próximas etapas do doc 47)

- G2 vista no Planejador (planta por zona, ficha por elemento); `tipo_planejador` é só classificação de desenho.
- G4 camada simulada; G5 aba na plataforma `casa-physis-inicial`; G6–G7 dependem de obra.
- Georreferência (L-01): sem lat/long oficial, tudo em x/y local.

## Conferente automático com aprendizado (22/11/2026)

`physis_hub/gemeo_conferente.py`: o raciocínio de conferência vira rotina.

    python -m physis_hub.gemeo_conferente ciclo        # só quando a dona pede (pg:ba8cbff56e13)
    python -m physis_hub.gemeo_conferente relatorio
    python -m physis_hub.gemeo_conferente corrigir ID OPCAO --nota "..."

- Acha sozinho: divergência entre fontes, peça fora do nível do terreno que nenhuma fonte explica, elemento sem área,
  soma das partes × total. Opções sempre fechadas (nunca número novo).
- Cada achado vira pergunta única no M&A, com a sugestão do sistema em primeiro e a confiança.
- Respostas e correções viram exemplos; regressão logística leve (`aprendizado.py`) por tipo de achado, versionada
  (`gemeo_modelo`), acerto deixa-um-de-fora, explicação em português. Exemplos iniciais: 10 decisões reais do M&A.
- Aplica sozinho só com ≥ 10 decisões humanas e acerto ≥ 90% no tipo (pg:068bf675d5b9); registra no M&A para
  revisão; o que ele aplicou não entra no treino.

## Estrutura até o terreno (22/11/2026)

Terreno do IFC = grade do Planejador (antes, a malha só das curvas laterais punha peças "voando"). Pilares tubulares
100 × 100 × 4,75 e blocos 0,70/0,60 aflorando 30 cm (02b), nas quantidades da 20 › Fundações; aterro da 03 desenhado
até o terreno; LAB/MEC de cima reconhecidos sobre os de baixo. Posição de cada apoio: regra escrita, [CONFERIR].

## Roteiro de camadas (decisão pg:ee988f1fe957; tarefas no M&A)

| Tarefa | Camada | Fonte que já existe | Falta |
|---|---|---|---|
| `casa-gemeo-estrutura` (feita em teste, 22/11) | 36 vigas W (LAB/MEC, lofts borda e central, grelha radial e anel do restaurante, V3 da Casa 1), contraventos em X, LAB/MEC P1–P8 da 02b, muro drenado da Rua G (5,2 m no modelo × até ≈ 4,7 m na 02b [CONFERIR]), taludes 1:1 com gabião e vetiver | 20 › Vigas e Fundações, 02b | projeto estrutural; perfis e espessuras do catálogo; V1/V2 do balanço (andar de cima da Casa 1 não modelado) |
| `casa-gemeo-hidraulica` (feita em teste, 22/11) | 11 tubos de esgoto com as cotas de fundo da 20, 7 caixas de inspeção e a de gordura (posição pela proporção dos comprimentos [CONFERIR]), biodigestor, fossa e filtro (não cabem nos 4,1 m da 03: achado do conferente), cisternas C1–C3 nas peças da 03 e C4–C10 sem posição, cota e pressão da água por ponto (D9: Loft 2, Loft 4 e platô da Rua G × 03), drenagem sem geometria | 20 › Esgoto trechos, Tratamento, Cisternas, Água vertical, Drenagem | traçado em DWG; água fria e quente; drenagem em planta |
| `casa-gemeo-eletrica` | quadros, circuitos, strings, inversores, baterias, placas uma a uma | 20 › Quadro de cargas, Strings FV; 02b | posição do QGBT |
| `casa-gemeo-interiores` | mobiliário, esquadrias, Casa 1 em L, mezaninos, vegetação | 09b, 20 › Esquadrias e Espécies, doc 10 | layout fino |
| `casa-gemeo-avac-sbn` | ar-condicionado, aquecimento, SBN, demais itens | 03 › Aquecimento, Bioconstrução, Piscina natural; 18 | — |

Texturas e materiais visuais: com a sessão de renderização (biblioteca aberta hospedada pela Physis); o acervo não
traz código de cor, então cor de material só entra com fonte.
