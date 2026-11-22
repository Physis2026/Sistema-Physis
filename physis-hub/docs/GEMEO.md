# Gêmeo digital da Casa Physis · G0–G1 (versão de TESTE)

Desenho aprovado pela dona em 21/11/2026: `Documents\Sistema Physis\47_Gemeo_Digital_Casa_Physis_TESTE.md`
(seções 3, 6 e 7). Tarefa no M&A: `casa-gemeo-g0-g1`. Ramo: `teste/casa-gemeo-g0-g1` (sem merge no main sem aprovação).

## O que existe

| Peça | Onde | O que faz |
|---|---|---|
| Núcleo | `physis_hub/gemeo.py` | Zonas e entidades, estados de vida, valor com procedência, leitura da semente, totais por zona, validação. Pontos (`gemeo_ponto`) e cenários (`gemeo_cenario`) só em `ESQUEMA_SQL`: o hub ainda não cria as tabelas |
| Importador | `physis_hub/gemeo_importar.py` | Planilhas 20 e 03 (e 18 só para citar D5) → projeto `physis.terreno/1.0` com o campo `gemeo`. Lê .xlsx sem dependências; para com erro se faltar um rótulo |
| Semente rev0 | `modulos/planejador/gemeo/casa-physis-rev0.json` | Abre no Planejador por "Abrir projeto" (nada no Planejador foi mudado) |
| Testes | `tests/test_gemeo.py` | 19 testes; os 2 da classe `Acervo` só rodam onde as planilhas existem |

Refazer a semente quando a planilha 20 ou a 03 mudar (o teste `Acervo` acusa semente desatualizada):

    cd physis-hub
    python -m physis_hub.gemeo_importar --saida ../modulos/planejador/gemeo/casa-physis-rev0.json
    # pasta das planilhas: --editaveis PASTA ou PHYSIS_CASA_EDITAVEIS

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
- G3 IFC4 por `ifc.py`; G4 camada simulada; G5 aba na plataforma `casa-physis-inicial`; G6–G7 dependem de obra.
- Georreferência (L-01): sem lat/long oficial, tudo em x/y local.
