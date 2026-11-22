# Casa Physis · Lote 168 · propostas de projeto net zero (VERSÃO DE TESTE, 22/11/2026)

Pedido da dona (22/11/2026): melhorias de design aproveitando o desnível e o espaço; soluções inteligentes, inovadoras e de
ótimo custo-benefício; renováveis e soluções baseadas na natureza (SbN); **todos os itens da lista inicial rearranjados**;
**norte sempre indicado**; **sempre buscar net zero**.

Regra 1: nenhum número inventado. Cada número tem fonte (documento técnico da Casa Physis, a semente rev0 do gêmeo ou uma
conta mostrada aqui); o que falta é `[MARCADOR]` e o que diverge entre documentos é `[CONFERIR]`.

Arquivos: `versao_A_netzero.csv` e `versao_A2_netzero.csv` (variantes no formato do comparador do gêmeo), `planta_A_netzero.svg` e
`planta_A2_netzero.svg` (plantas com norte), `projeto_rev0.json` e `projeto_A2.json` (projetos do Planejador gerados pelo comparador).
**Variante adotada em teste: A2** (M&A pg:da5c700b814d).

## 0. Norte

- Documentos 01 §2 e 20: "Rua G = norte de projeto; norte verdadeiro a ≈ 17°" (nor-nordeste); a seta da prancha do topógrafo
  "a corrigir". **[CONFERIR] com o topógrafo.**
- Sentido (corrigido em 22/11/2026 com a sessão do gêmeo): na 20 › Perímetro o lado ao longo de +Y tem azimute 17° e a 03 ›
  Levantamento diz que "o eixo do lote aponta a cerca de 17° (nor-nordeste)". Logo o norte de projeto (+Y, Rua G) fica 17° a
  **leste** do norte verdadeiro, e o norte verdadeiro, em coordenadas locais, é **(−0,29; 0,96)**: 17° a oeste do +Y. O IFC do gêmeo
  já grava esse `TrueNorth` e a semente tem `lote.norte_verdadeiro_graus = 17` com `[CONFERIR]` (M&A pg:afe44bbf677a).
  Na aba Net zero do Planejador o campo "norte verdadeiro em relação ao de projeto (graus, horário)" fica **−17** para este lote.
  `[CONFERIR]` também o sentido do eixo x local: a 20 dá 287° para o lado P-01→P-02, o que pediria x para oeste; o topógrafo confirma.
- A encosta cai **para o norte** (Rua H ≈ 902–903 → Rua G ≈ 874–875): no hemisfério sul é a melhor face para sol e FV.
  Toda planta desta proposta traz NP (projeto) e NV (verdadeiro).

## 1. Lista inicial rearranjada (todos os itens)

Base: as 92 peças da semente rev0 (planilha 03 › Implantação + 20) por zona: Z1 18, Z2 40, Z3 34.
Na rev0, três itens estavam **sem lugar**: Loft 6 e Loft 7 ("não cabe seguindo as curvas de nível com varanda e recuos") e a
Loja 24 h ("sem lugar na nova Zona 3"). O documento 00b prevê 6 lofts e a 7ª unidade no mês 36.

**Variante A** (comparador do gêmeo, `gemeo_versoes.avaliar`, mesmo lote, mesma régua):

| | rev0 | Variante A |
|---|---|---|
| Peças da lista com lugar | 89 de 92 (LF6, LF7, loja sem área) | **92 de 92** |
| Lofts | 5 | **7** |
| Área de edificações | 310,5 m² | 353,3 m² |
| Ocupação (limite 40 %, 03) | 21,3 % | 24,3 % |
| Filtro (perímetro, sobreposição, ocupação) | passa | **passa** |

Mudanças (só estas cinco peças; as outras 87 ficam como na rev0):
- **LF6** (4 × 4, PCD) e **LF7** (4 × 5, mês 36) **geminados sobre o estacionamento da Rua G**, piso a 879,4 (3,1 m acima das
  vagas a 876,3, no nível do talude a montante). Usa o vão do estacionamento que já existe, sem corte novo; parede comum
  economiza estrutura e fachada. Alerta do comparador: desnível de 2,8 m sob a projeção → estrutura elevada, que é a proposta.
  **[CONFERIR] estrutura:** os pilares precisam deixar as 2 vagas (1 PCD) livres; o 21 já aponta viga W150 insuficiente nos lofts.
- **Varandas 6 e 7** na frente norte (1,0 m), vista para a Rua G e sol de inverno.
- **Loja 24 h** na cota do acesso (876,3), ao lado dos resíduos, fora das vagas: venda para quem passa na Rua G sem entrar no lote.

## 2. Água por gravidade e águas cinzas (propostas 3 e 4)

O desnível trabalha a favor: cotas da semente rev0 — C1 900,77; piscina 895,05; tanque de peixes 890,26; lago/wetland 890,59;
C2 885,48; C3 873,46 (sob o estacionamento da Rua G).

- **Cascata C1 → C3:** cada platô capta a própria chuva e entrega o excedente ao de baixo; a distribuição desce por gravidade.
  Carga estática de C1: 24,5 m até a loja (876,3) e 23,3 m até o LF5 (877,5); de C2 até a loja, 9,2 m. **[CONFERIR] limite de
  pressão estática da NBR 5626** e, onde precisar, válvula redutora ou caixa de quebra-pressão por platô — resolve a falha
  "pressão excessiva nos pontos baixos" do 21 sem bomba.
- **Bombeamento só para subir**, de dia, com o excedente FV (água como bateria). A Casa 1 está a 901,22 na rev0, acima de C1
  (900,77): precisa de pressurização. **[CONFERIR]** o 10 põe a Casa 1 no platô a 889–891, o que resolveria por gravidade.
- **Águas cinzas → floresta filtrante/wetland → irrigação** de hortas e pomar: resolve a divergência 01 (reúso) × 08 (fossa) e
  reduz a demanda não potável (1,9 m³/dia, 08 §1) atendida hoje com 220 m³ de cisternas (20). Volume de cinzas por dia:
  `[MARCADOR]` (separar no 18). Se o reúso cobrir parte da irrigação, as cisternas da fase 3 (C8–C10, 60 m³) podem diminuir.
- **Água potável (3,1 m³/dia):** net zero de água exige tratar a chuva para consumo (filtro lento + UV): `[CONFERIR]` potabilidade
  (Portaria de potabilidade) e licença; até lá, rede ou poço.

## 3. Mais FV e o saldo net zero (propostas 2 e 8)

- **Hoje:** 30,8 kWp (56 placas de 550 W) × 1.302 kWh/kWp·ano (PVGIS, 18) = 3.341,8 kWh/mês contra 3.341 kWh/mês de consumo
  de projeto (07): **saldo de 100,02 %**, sem margem.
- **7º loft:** a hospedagem consome 875 kWh/mês (03) ou 546,9 (18) para 6 lofts → **+91 a +146 kWh/mês por loft** → **+0,84 a
  +1,34 kWp** (2 a 3 placas de 550 W) só para empatar. Proposta: **meta de 110 %** (margem para degradação e sujeira) com
  FV nos telhados dos lofts 6–7 (36 m²) e uma **pérgola FV sobre as 4 vagas da Rua H** (40 m², 10 × 4). Potência por m²:
  `[MARCADOR]` (ficha da placa). Divergência a resolver: a 03 › Solar fala em 70 placas / 38,5 kWp para 7 lofts.
- **Orientação:** telhados e FV voltados ao **norte verdadeiro** (17° a oeste do norte de projeto, [CONFERIR]); inclinação 14° (03) × 15–20°
  (07/01) `[CONFERIR]`.
- **Beirais:** latitude de Petrópolis ≈ −22,5° (o lote ainda não tem lat/long oficial) → sol ao meio-dia a ≈ 89° no verão e ≈ 44°
  no inverno. Um beiral de **0,76 m** sobre janela norte de 2,10 m barra o sol acima de 70° (verão) e deixa entrar o de inverno.
- **Custos com fonte (15, payback):** placas + inversores R$ 84.266; baterias 30 kWh R$ 23.000; coletores R$ 27.140.
  R$/kWp: `[MARCADOR]` (a linha não diz quantos kWp cobre).

## 4. Desnível e contenções (propostas 5, 6 e 7)

- **Terra movida da rev0: corte 489,3 m³ × aterro 24,8 m³** (semente, fonte 03) → ≈ 464 m³ sobrando. Proposta: **solo-cimento
  com o solo do corte** (blocos e pisos; já citado no 09) e aterro dos platôs de horta, em vez de bota-fora (custo do bota-fora:
  `[MARCADOR]`). Terraplenagem da opção M2: R$ 40 mil contra R$ 53–55 mil das outras (04 §3).
- **LAB/MEC semi-enterrado:** o comparador mede 3,4–3,5 m de desnível sob o superbloco; a parede de montante vira contenção e
  massa térmica, e o teto vira terraço-viveiro (já previsto). **[CONFERIR]** cálculo de contenção (21: taludes sem cálculo).
- **Platôs com gabião + vetiver** (já previstos, 01): padronizar as cotas dos platôs nas cotas dos módulos para equilibrar
  corte e aterro.
- **Reter antes de infiltrar:** o 21 marca "infiltrar água em zona instável" como falha de impacto muito alto. Jardins de chuva
  **impermeabilizados com dreno** e a detenção de 6 m³ junto à Rua G (06) primeiro; valas de infiltração só depois do ensaio.
  Excedente de projeto: ≈ 26 m³ numa chuva de 2 h, T25 (06).

## 5. Conforto e operação (propostas 9 a 12)

- **Biogás com estufa:** 1,37 m³/dia contra 1,15 sem (03) → cobre ≈ 21 % da cocção do restaurante (19,18 kWh/dia, 03); o resto
  por indução com FV `[CONFERIR]` se a cocção já está no consumo de projeto.
- **Chaminé solar no restaurante circular** (bioconstrução): ventilação por tiragem térmica, sem motor.
- **Plano inclinado de carga** (trilho) ao lado da escada principal: insumos, colheita e resíduos entre Rua H e Rua G
  (≈ 28 m de desnível em ≈ 72 m) sem veículo e sem esforço. Custo: `[MARCADOR]`.
- **Monitoramento net zero:** medidores por zona no gêmeo/SCADA, que são a prova exigida pelo EDGE (≥ 20 % de economia) e,
  depois de 12 meses de dados, pelo LEED/AQUA (05).

## 6. Custo-benefício (ordem sugerida)

| Faixa | Propostas | Por quê |
|---|---|---|
| Custo baixo, efeito alto | beirais 0,76 m; água por gravidade com quebra-pressão; águas cinzas; reter antes de infiltrar; vetiver | usam o desnível e o sol; evitam bombas e riscos |
| Custo médio | lofts 6–7 geminados sobre o estacionamento; pérgola FV; solo-cimento do corte | aumentam a receita (lofts) e a geração; evitam bota-fora |
| Custo alto ou incerto | plano inclinado; potabilização da chuva | `[MARCADOR]` preço; dependem de licença |

Preços em R$/m² por item: `[MARCADOR]` até haver tabela com fonte (critério da dona, M&A pg:97b6e5a48dcf).

## 7. Pendências

- Norte verdadeiro e lat/long do lote (topógrafo).
- Estrutura dos lofts 6–7 sobre o estacionamento; contenção do LAB/MEC; sondagem SPT (21).
- Volume de águas cinzas; ficha da placa FV; R$/kWp; custo de bota-fora.
- Posição da Casa 1 (rev0 901,22 × doc. 10 889–891).

## 8. Piscina, lago, peixes e wetland (variante A2, adotada em teste)

Números da planilha 03 (aba Piscina natural): piscina 4 × 6 = 24 m², 1,4 m, 33,6 m³; zona de regeneração mínima 30 % (7,2 m²) e
máxima recomendada 50 % (12 m², FLL); lago + wetland adotado 15 m²; renovação 1 volume/dia; **altura manométrica 9,1 m
("NA piscina − NA lago + perdas")**; 8 h de bomba; 4,2 m³/h; 231 W; **55,5 kWh/mês**. Perdas: evaporação de piscina, lago e
mini-lago 125 L/dia; reposição dos peixes 134 L/dia (03, aba Água). Tanque de peixes: ≈ 180 kg/ano e água rica para as hortas
(15, payback 1,55 ano). Piscina natural de pedras: R$ 17.250 (15).

**Problema:** o lago que regenera a piscina está a 890,59 e a piscina a 895,05; a bomba sobe 9,1 m todo dia.

**Proposta (A2):** quatro circuitos que não se misturam, cada um aproveitando o desnível:
- **Banho:** zona de regeneração de **12 m² (50 % FLL)** colada no lado de cima da piscina, lâmina a 895,35 (0,30 m acima), no lugar
  do antigo apoio técnico (removido). A água volta por gravidade; a bomba só vence ≈ 0,8 m (diferença + perdas). Com a mesma
  vazão e o rendimento implícito da 03 (104 W hidráulicos ÷ 231 W = 0,45): **≈ 20 W e ≈ 4,9 kWh/mês, economia de ≈ 50,7 kWh/mês**
  (≈ 1,5 % do consumo de projeto). Reposição da piscina por gravidade a partir da C1 (900,77).
- **Produção:** tanque de peixes (890,26) ↔ lago + wetland (890,59), na mesma cota: o lago vira o biofiltro dos peixes
  (aquaponia) e a água com nutrientes desce **por gravidade** para as hortas B (890,19), C (888,20) e D (886,23).
- **Reserva:** excedente do lago → C2 (885,48) → mini-lago (878,83), ao lado do fogo de chão: água à mão para combate a fogo.
- **Efluente:** cinzas e negras → fossa, filtro e floresta filtrante; nunca chegam à piscina nem ao lago (o 03 já pede "qualidade
  da água e peixes separados").

`[CONFERIR]`: qualidade da água da piscina natural (NBR 10339/10818, já citadas no 05); vazão real de recirculação com a regeneração
colada; impermeabilização da regeneração na encosta.

## 9. Cruzamento com a Aptidão do Planejador

O módulo "Aptidão do terreno para construir" (Especialista: declividade 0,45, sol 0,25, acesso 0,20, caminhos da água 0,10)
rodou no próprio Planejador sobre a rev0 e as variantes (projetos gerados pelo comparador do gêmeo):
- Variante A: **Loft 6 com nota 0,31** ("rever posição"): 63 % da projeção sobre um caminho da água (lado oeste do
  estacionamento, para onde a enxurrada corre até o canto baixo da Rua G). Loft 7: 0,45.
- Variante A2: o par geminado "em pé" (4 × 9 m) em x = 7,75: **Loft 6 0,51 e Loft 7 0,51**, 2–8 % sobre caminho da água, 1,6 m do Loft 4.
  Loja 24 h 0,57; zona de regeneração 0,62.
- Já na rev0, nota baixa: Coelhos 0,26, LAB 0,34–0,35, 2 lavabos 0,37 → a aba Net zero (plano Especialista) sugere posições.
- O projeto não tem item "acesso" desenhado: o critério de acesso foi ignorado. `[CONFERIR]` desenhar os acessos da Rua H e da Rua G.

## 10. Aba Net zero no Planejador (construída em teste)

Decisão da dona (M&A pg:b880e775e565). Código: `sistema/planejador-netzero.js` (bloco copiado no Planejador por `sincronizar.py`).
Desenho: `desenhos/planejador-aba-netzero.html`. Livre: norte NP/NV, itens sem lugar, saldo de energia e água. Profissional: terra,
desnível, pressão por gravidade (limite de 40 m do núcleo, NBR 5626), bomba, beirais, FV onde cabe. Especialista: aptidão com
realocação (respeita lote, recuo lateral e folga de 1,5 m) e circuitos de água. Empresa: variantes e meta de certificação.
