/* physis-cargatermica.js — Carga térmica de verão por ambiente (sensível + latente), no caminho da ABNT NBR 16401-1:2008
   (cálculo da carga de resfriamento a partir das condições externas de projeto, da envoltória, da insolação, das cargas internas
   e do ar externo). Redação própria; nenhuma frase das normas é reproduzida.
   Método (resumo; detalhes em physis-hub/docs/CARGA_TERMICA.md):
   · temperatura externa horária = TBS de projeto − amplitude diária × fração horária (perfil da ASHRAE);
   · sol pelo modelo de céu claro (A, B, C por mês) com latitude, declinação e hora solar;
   · paredes e coberturas: temperatura sol-ar e U·A, com atraso térmico e amortecimento do material (massa térmica);
   · vidros: área × fator solar × sombreamento × irradiância + condução U·A·ΔT;
   · pessoas (sensível/latente por atividade), iluminação e equipamentos em W/m², infiltração (trocas/h)
     e ar externo (L/s por pessoa + L/s por m², lógica da NBR 16401-3);
   · perfil das 8 às 18 h, pico por ambiente e pico simultâneo do conjunto, fator de segurança;
   · sugestão de sistema (split × VRF × chiller) com equipamento da base sistema/physis-equipamentos.json e energia anual.
   Espelho em Python: physis-hub/physis_hub/cargatermica.py (mesmas fórmulas; testes em physis-hub/tests/test_cargatermica.py).
   Contrato: window.CARGA_TERMICA = { calcular(ambientes, clima, opcoes), padrao(), DADOS } e window.telaCargaTermica(estado).
   Globais usadas só na hora de desenhar: esc, n2, numBr, brl, el, ui, desenhar (e calcLer/calcGravar, se existirem). */
(function () {
"use strict";

/*DADOS-INICIO*/
const DADOS = {
 "versao": 1,
 "constantes": {
  "h_ext": 17,
  "delta_r_horizontal": 3.9,
  "refletancia_solo": 0.2,
  "c_sensivel": 1.23,
  "c_latente": 3010,
  "btu_por_w": 3.412142,
  "w_por_tr": 3516.853,
  "_fonte": "ASHRAE Handbook Fundamentals (cap. 18): h_ext ≈ 17 W/m²K e correção de onda longa de 3,9 K em superfície horizontal; 1,23 W/(L/s·K) e 3010 W/(L/s) por kg/kg para ar a 1,2 kg/m³"
 },
 "padroes": {
  "pe_direito": 2.8,
  "iluminacao_wm2": 10,
  "equipamentos_wm2": 10,
  "infiltracao_ach": 0.5,
  "tint": 24,
  "urint": 50,
  "fs": 1.1,
  "horas": [
   8,
   9,
   10,
   11,
   12,
   13,
   14,
   15,
   16,
   17,
   18
  ],
  "ini": 8,
  "fim": 18,
  "horas_ano": 2600,
  "fator_carga": 0.5,
  "fator_adjacente": 0.5,
  "_fonte": "Interior 24 °C / 50 % UR: faixa de conforto de verão da ABNT NBR 16401-2:2008 (seção de parâmetros de conforto). Iluminação, equipamentos, infiltração, 2600 h/ano (10 h × 260 dias) e fator de carga 0,5: premissa Physis — verificar por projeto"
 },
 "fracao_amplitude": [
  0.82,
  0.88,
  0.92,
  0.95,
  0.98,
  1.0,
  0.98,
  0.91,
  0.74,
  0.55,
  0.38,
  0.23,
  0.13,
  0.05,
  0.0,
  0.0,
  0.06,
  0.14,
  0.24,
  0.39,
  0.5,
  0.59,
  0.68,
  0.75
 ],
 "_fracao_amplitude_fonte": "ASHRAE Handbook Fundamentals (cap. 14), fração da amplitude diária por hora solar; índice 0 = meia-noite. T(h) = TBS_projeto − amplitude × fração(h)",
 "ceu_claro": [
  [
   1230,
   0.142,
   0.058
  ],
  [
   1215,
   0.144,
   0.06
  ],
  [
   1186,
   0.156,
   0.071
  ],
  [
   1136,
   0.18,
   0.097
  ],
  [
   1104,
   0.196,
   0.121
  ],
  [
   1088,
   0.205,
   0.134
  ],
  [
   1085,
   0.207,
   0.136
  ],
  [
   1107,
   0.201,
   0.122
  ],
  [
   1151,
   0.177,
   0.092
  ],
  [
   1192,
   0.16,
   0.073
  ],
  [
   1221,
   0.149,
   0.063
  ],
  [
   1233,
   0.142,
   0.057
  ]
 ],
 "_ceu_claro_fonte": "Modelo de céu claro da ASHRAE (edições 1985–2005 do Fundamentals): A (W/m²), B e C por mês, dia 21. I_DN = A·exp(−B/sen β). Verificar: as edições novas usam o modelo tau.",
 "dia_21": [
  21,
  52,
  80,
  111,
  141,
  172,
  202,
  233,
  264,
  294,
  325,
  355
 ],
 "orientacoes": {
  "N": 0,
  "NE": 45,
  "L": 90,
  "SE": 135,
  "S": 180,
  "SO": 225,
  "O": 270,
  "NO": 315,
  "H": -1
 },
 "cores": {
  "branca": 0.2,
  "clara": 0.3,
  "media": 0.6,
  "escura": 0.8,
  "preta": 0.95,
  "_fonte": "absortância solar típica por cor de superfície (faixas como as da ABNT NBR 15220-2, anexo de absortâncias) — verificar com o material real"
 },
 "atividades": {
  "repouso": {
   "nome": "Sentado em repouso (sala de espera, cinema)",
   "sens": 65,
   "lat": 30
  },
  "escritorio": {
   "nome": "Escritório, trabalho leve sentado",
   "sens": 75,
   "lat": 55
  },
  "residencial": {
   "nome": "Residência, atividade leve em pé ou sentado",
   "sens": 75,
   "lat": 55
  },
  "restaurante": {
   "nome": "Restaurante (refeição)",
   "sens": 80,
   "lat": 80
  },
  "comercio": {
   "nome": "Loja, em pé, andando devagar",
   "sens": 80,
   "lat": 80
  },
  "sala_aula": {
   "nome": "Sala de aula",
   "sens": 70,
   "lat": 45
  },
  "trabalho_leve": {
   "nome": "Bancada, trabalho leve em pé",
   "sens": 80,
   "lat": 140
  },
  "danca": {
   "nome": "Dança moderada",
   "sens": 90,
   "lat": 160
  },
  "academia": {
   "nome": "Academia, exercício",
   "sens": 210,
   "lat": 315
  },
  "_fonte": "ASHRAE Handbook Fundamentals (cap. 18, tabela de calor liberado por pessoa, valores ajustados); tabela equivalente no anexo de cargas internas da ABNT NBR 16401-1:2008 — verificar"
 },
 "ar_externo": {
  "escritorio": {
   "nome": "Escritório",
   "rp": 2.5,
   "ra": 0.3
  },
  "residencial": {
   "nome": "Residência (sala, quarto)",
   "rp": 2.5,
   "ra": 0.3
  },
  "sala_aula": {
   "nome": "Sala de aula",
   "rp": 5.0,
   "ra": 0.6
  },
  "comercio": {
   "nome": "Loja",
   "rp": 3.8,
   "ra": 0.6
  },
  "restaurante": {
   "nome": "Restaurante, salão",
   "rp": 3.8,
   "ra": 0.9
  },
  "academia": {
   "nome": "Academia",
   "rp": 10.0,
   "ra": 0.3
  },
  "reuniao": {
   "nome": "Sala de reunião, auditório",
   "rp": 2.5,
   "ra": 0.3
  },
  "_fonte": "Lógica da ABNT NBR 16401-3:2008 (vazão eficaz = Rp × pessoas + Ra × área; tabela de vazões por tipo de local, nível 1). Valores lembrados da tabela, alinhados à ASHRAE 62.1 — verificar na norma antes de emitir"
 },
 "materiais": {
  "tijolo_6f_14": {
   "nome": "Tijolo cerâmico 6 furos rebocado (14 cm)",
   "tipo": "parede",
   "u": 2.48,
   "atraso": 3.3,
   "amortecimento": 0.421,
   "composicao": "tijolo_6f_14"
  },
  "tijolo_macico_25": {
   "nome": "Tijolo maciço rebocado (≈ 25 cm)",
   "tipo": "parede",
   "u": 2.04,
   "atraso": 7.8,
   "amortecimento": 0.13,
   "composicao": "tijolo_macico_25"
  },
  "bloco_concreto_14": {
   "nome": "Bloco de concreto rebocado (14 cm)",
   "tipo": "parede",
   "u": 2.78,
   "atraso": 3.6,
   "amortecimento": 0.39,
   "composicao": "bloco_concreto_14"
  },
  "concreto_10": {
   "nome": "Parede de concreto maciço (10 cm)",
   "tipo": "parede",
   "u": 4.4,
   "atraso": 2.6,
   "amortecimento": 0.506,
   "composicao": "concreto_10"
  },
  "drywall_la": {
   "nome": "Drywall ou steel frame com lã mineral",
   "tipo": "parede",
   "u": 0.67,
   "atraso": 2.6,
   "amortecimento": 0.506,
   "composicao": "drywall_la"
  },
  "madeira_tabua": {
   "nome": "Tábua de madeira (2,5 cm)",
   "tipo": "parede",
   "u": 2.97,
   "atraso": 1.2,
   "amortecimento": 0.73,
   "composicao": "madeira_tabua"
  },
  "taipa_30": {
   "nome": "Taipa de pilão (30 cm)",
   "tipo": "parede",
   "u": 2.26,
   "atraso": 8.6,
   "amortecimento": 0.105,
   "composicao": "taipa_30"
  },
  "adobe_25": {
   "nome": "Adobe rebocado com terra (25 cm)",
   "tipo": "parede",
   "u": 1.73,
   "atraso": 8.3,
   "amortecimento": 0.114,
   "composicao": "adobe_25"
  },
  "btc_15": {
   "nome": "Tijolo de solo-cimento (BTC) rebocado (15 cm)",
   "tipo": "parede",
   "u": 2.75,
   "atraso": 5.0,
   "amortecimento": 0.27,
   "composicao": "btc_15"
  },
  "cob_40": {
   "nome": "Cob (terra, palha e areia moldada, 40 cm)",
   "tipo": "parede",
   "u": 1.35,
   "atraso": 13.6,
   "amortecimento": 0.028,
   "composicao": "cob_40"
  },
  "pau_a_pique_15": {
   "nome": "Pau a pique (taipa de mão, 15 cm)",
   "tipo": "parede",
   "u": 2.8,
   "atraso": 4.6,
   "amortecimento": 0.3,
   "composicao": "pau_a_pique_15"
  },
  "superadobe_35": {
   "nome": "Superadobe (sacos de terra, 35 cm)",
   "tipo": "parede",
   "u": 1.68,
   "atraso": 10.6,
   "amortecimento": 0.062,
   "composicao": "superadobe_35"
  },
  "fardo_palha_45": {
   "nome": "Fardo de palha rebocado com terra (45 cm)",
   "tipo": "parede",
   "u": 0.13,
   "atraso": 21.1,
   "amortecimento": 0.004,
   "composicao": "fardo_palha_45"
  },
  "canhamo_cal_30": {
   "nome": "Cânhamo e cal (30 cm)",
   "tipo": "parede",
   "u": 0.22,
   "atraso": 19.2,
   "amortecimento": 0.007,
   "composicao": "canhamo_cal_30"
  },
  "telha_ceramica_forro_madeira": {
   "nome": "Telha cerâmica com forro de madeira",
   "tipo": "cobertura",
   "u": 2.0,
   "atraso": 1.3,
   "amortecimento": 0.712,
   "composicao": "telha_ceramica_forro_madeira"
  },
  "telha_ceramica_laje": {
   "nome": "Telha cerâmica com laje mista (12 cm)",
   "tipo": "cobertura",
   "u": 2.06,
   "atraso": 5.2,
   "amortecimento": 0.256,
   "composicao": "telha_ceramica_laje"
  },
  "fibrocimento_sem_forro": {
   "nome": "Telha de fibrocimento sem forro",
   "tipo": "cobertura",
   "u": 4.56,
   "atraso": 0.2,
   "amortecimento": 0.949,
   "composicao": "fibrocimento_sem_forro"
  },
  "fibrocimento_laje": {
   "nome": "Telha de fibrocimento com laje (10 cm)",
   "tipo": "cobertura",
   "u": 2.06,
   "atraso": 5.2,
   "amortecimento": 0.256,
   "composicao": "fibrocimento_laje"
  },
  "metalica_sem_forro": {
   "nome": "Telha metálica sem forro",
   "tipo": "cobertura",
   "u": 4.76,
   "atraso": 0.0,
   "amortecimento": 1.0,
   "composicao": "metalica_sem_forro"
  },
  "sanduiche_pu_30": {
   "nome": "Telha sanduíche metálica com PU (30 mm)",
   "tipo": "cobertura",
   "u": 0.83,
   "atraso": 1.2,
   "amortecimento": 0.73,
   "composicao": "sanduiche_pu_30"
  },
  "laje_exposta_10": {
   "nome": "Laje de concreto exposta (10 cm)",
   "tipo": "cobertura",
   "u": 3.74,
   "atraso": 2.6,
   "amortecimento": 0.506,
   "composicao": "laje_exposta_10"
  },
  "telhado_verde_extensivo": {
   "nome": "Telhado verde extensivo (laje + 10 cm de substrato)",
   "tipo": "cobertura",
   "u": 2.11,
   "atraso": 6.5,
   "amortecimento": 0.182,
   "absortancia": 0.3,
   "composicao": "telhado_verde_extensivo"
  },
  "telhado_verde_intensivo": {
   "nome": "Telhado verde intensivo (laje + 30 cm de substrato)",
   "tipo": "cobertura",
   "u": 1.15,
   "atraso": 13.9,
   "amortecimento": 0.026,
   "absortancia": 0.25,
   "composicao": "telhado_verde_intensivo"
  },
  "palha_sape": {
   "nome": "Cobertura de palha ou sapê (≈ 20 cm)",
   "tipo": "cobertura",
   "u": 0.33,
   "atraso": 8.3,
   "amortecimento": 0.114,
   "composicao": "palha_sape"
  },
  "vidro_simples": {
   "nome": "Vidro simples incolor 6 mm",
   "tipo": "vidro",
   "u": 5.7,
   "fs": 0.82
  },
  "vidro_controle_solar": {
   "nome": "Vidro de controle solar (refletivo/serigrafado)",
   "tipo": "vidro",
   "u": 5.5,
   "fs": 0.45
  },
  "vidro_duplo": {
   "nome": "Vidro duplo incolor",
   "tipo": "vidro",
   "u": 2.8,
   "fs": 0.7
  },
  "vidro_duplo_lowe": {
   "nome": "Vidro duplo com baixo emissivo",
   "tipo": "vidro",
   "u": 1.8,
   "fs": 0.4
  },
  "policarbonato_alveolar": {
   "nome": "Policarbonato alveolar 10 mm",
   "tipo": "vidro",
   "u": 3.0,
   "fs": 0.75
  },
  "laje_entre_pisos": {
   "nome": "Laje de concreto com piso (12 cm)",
   "tipo": "piso",
   "u": 3.94,
   "atraso": 3.2,
   "amortecimento": 0.433,
   "composicao": "laje_entre_pisos"
  },
  "_fonte": "U e atraso de cada parede/cobertura vêm das composições de sistema/physis-materiais.json (método da ABNT NBR 15220-2 ou valor tabelado da NBR 15220-3); amortecimento = exp(−2π·atraso/24) (premissa Physis). Vidros: faixas de catálogo público.",
  "_verificar": true,
  "terra_palha_25": {
   "nome": "Terra-palha (25 cm) com reboco de terra",
   "tipo": "parede",
   "u": 0.82,
   "atraso": 10.7,
   "amortecimento": 0.061,
   "composicao": "terra_palha_25"
  }
 },
 "cidades": [
  {
   "nome": "São Paulo",
   "uf": "SP",
   "lat": -23.6,
   "alt": 800,
   "tbs": 31.6,
   "tbu": 21.4,
   "dr": 9.0
  },
  {
   "nome": "Rio de Janeiro",
   "uf": "RJ",
   "lat": -22.9,
   "alt": 5,
   "tbs": 35.2,
   "tbu": 25.0,
   "dr": 7.0
  },
  {
   "nome": "Brasília",
   "uf": "DF",
   "lat": -15.8,
   "alt": 1060,
   "tbs": 31.6,
   "tbu": 18.8,
   "dr": 11.5
  },
  {
   "nome": "Belo Horizonte",
   "uf": "MG",
   "lat": -19.9,
   "alt": 790,
   "tbs": 32.0,
   "tbu": 20.6,
   "dr": 10.0
  },
  {
   "nome": "Salvador",
   "uf": "BA",
   "lat": -12.9,
   "alt": 10,
   "tbs": 32.0,
   "tbu": 25.0,
   "dr": 6.0
  },
  {
   "nome": "Recife",
   "uf": "PE",
   "lat": -8.1,
   "alt": 10,
   "tbs": 32.6,
   "tbu": 25.0,
   "dr": 7.0
  },
  {
   "nome": "Fortaleza",
   "uf": "CE",
   "lat": -3.8,
   "alt": 25,
   "tbs": 33.0,
   "tbu": 25.0,
   "dr": 7.0
  },
  {
   "nome": "Natal",
   "uf": "RN",
   "lat": -5.8,
   "alt": 50,
   "tbs": 31.8,
   "tbu": 25.2,
   "dr": 6.0
  },
  {
   "nome": "São Luís",
   "uf": "MA",
   "lat": -2.5,
   "alt": 50,
   "tbs": 33.0,
   "tbu": 25.8,
   "dr": 7.5
  },
  {
   "nome": "Teresina",
   "uf": "PI",
   "lat": -5.1,
   "alt": 70,
   "tbs": 38.2,
   "tbu": 23.5,
   "dr": 13.0
  },
  {
   "nome": "Belém",
   "uf": "PA",
   "lat": -1.4,
   "alt": 15,
   "tbs": 33.8,
   "tbu": 26.0,
   "dr": 8.0
  },
  {
   "nome": "Manaus",
   "uf": "AM",
   "lat": -3.1,
   "alt": 70,
   "tbs": 35.0,
   "tbu": 25.8,
   "dr": 9.0
  },
  {
   "nome": "Cuiabá",
   "uf": "MT",
   "lat": -15.6,
   "alt": 180,
   "tbs": 37.6,
   "tbu": 23.4,
   "dr": 11.0
  },
  {
   "nome": "Campo Grande",
   "uf": "MS",
   "lat": -20.5,
   "alt": 560,
   "tbs": 34.4,
   "tbu": 22.4,
   "dr": 11.0
  },
  {
   "nome": "Goiânia",
   "uf": "GO",
   "lat": -16.7,
   "alt": 750,
   "tbs": 34.5,
   "tbu": 20.5,
   "dr": 12.0
  },
  {
   "nome": "Vitória",
   "uf": "ES",
   "lat": -20.3,
   "alt": 5,
   "tbs": 34.0,
   "tbu": 25.5,
   "dr": 7.0
  },
  {
   "nome": "Curitiba",
   "uf": "PR",
   "lat": -25.4,
   "alt": 910,
   "tbs": 30.5,
   "tbu": 20.5,
   "dr": 10.0
  },
  {
   "nome": "Florianópolis",
   "uf": "SC",
   "lat": -27.6,
   "alt": 5,
   "tbs": 32.4,
   "tbu": 25.0,
   "dr": 7.0
  },
  {
   "nome": "Porto Alegre",
   "uf": "RS",
   "lat": -30.0,
   "alt": 5,
   "tbs": 35.5,
   "tbu": 24.0,
   "dr": 10.0
  }
 ],
 "_cidades_fonte": "Condições externas de verão (TBS de projeto com frequência 0,4 %, TBU coincidente médio e amplitude diária) lembradas dos dados climáticos de projeto da ASHRAE, mesma origem da tabela de cidades do anexo da ABNT NBR 16401-1:2008. Todos os valores: verificar na tabela vigente antes de emitir.",
 "_cidades_verificar": true,
 "regras_sistema": {
  "split_max_ambiente_kw": 17.6,
  "split_max_total_tr": 20,
  "vrf_min_tr": 3,
  "vrf_max_tr": 150,
  "vrf_min_ambientes": 3,
  "vrf_ideal_tr": 6,
  "vrf_ideal_ambientes": 4,
  "chiller_min_tr": 40,
  "chiller_ideal_tr": 100,
  "chiller_agua_min_tr": 150,
  "_fonte": "premissa Physis (prática de mercado) — revisar por projeto"
 },
 "sistemas_padrao": {
  "split": {
   "sazonal": 6.0,
   "aux": 1.0
  },
  "vrf": {
   "sazonal": 6.0,
   "aux": 1.0
  },
  "chiller": {
   "sazonal": 4.6,
   "aux": 1.15
  },
  "_fonte": "usado só quando a base physis-equipamentos.json não está disponível"
 }
};
/*DADOS-FIM*/

const RAD = Math.PI / 180, K = DADOS.constantes, P = DADOS.padroes;
const N = v => { const n = +v; return (v === null || v === undefined || v === "" || !isFinite(n)) ? 0 : n; };
const tem = v => v !== null && v !== undefined && v !== "" && isFinite(+v);
const ou = (v, d) => tem(v) ? +v : d;

/* ════════ Psicrometria ════════ */
const pressao = alt => 101.325 * Math.pow(1 - 2.25577e-5 * alt, 5.2559);                  // kPa
const pws = t => 0.61094 * Math.exp(17.625 * t / (t + 243.04));                             // kPa (Magnus, igual ao physis-avac.js)
const wsat = (t, p) => { const s = pws(t); return 0.621945 * s / (p - s); };                // kg/kg
const wBulbos = (tbs, tbu, p) => ((2501 - 2.326 * tbu) * wsat(tbu, p) - 1.006 * (tbs - tbu)) / (2501 + 1.86 * tbs - 4.186 * tbu);
const wUR = (t, ur, p) => { const pv = ur / 100 * pws(t); return 0.621945 * pv / (p - pv); };

/* ════════ Clima de projeto ════════ */
/* cidade de projeto a partir do local único da plataforma (localDaInstalacao: Planejador > Início > Monitoramento):
   o município, se estiver na tabela; senão a cidade da tabela na mesma UF. Sem local: "" (nada de cidade padrão). */
function localPlataforma() { try { return typeof localDaInstalacao === "function" ? localDaInstalacao() : null; } catch (e) { return null; } }
function cidadeDoLocal() { const L = localPlataforma(); if (!L) return "";
  const m = cidadePorNome(L.municipio); if (m) return m.nome;
  const u = String(L.uf || "").toUpperCase(), x = u ? DADOS.cidades.find(c => String(c.uf).toUpperCase() === u) : null; return x ? x.nome : ""; }
function cidadePorNome(nome) { const s = String(nome || "").trim().toLowerCase(); return DADOS.cidades.find(c => c.nome.toLowerCase() === s) || null; }
function resolverClima(clima, opcoes) {
  const c = clima || {}, op = opcoes || {}, cid = cidadePorNome(c.cidade), avisos = [];
  const pega = (k, d) => tem(c[k]) ? +c[k] : (cid && tem(cid[k]) ? +cid[k] : d);
  if (!cid && !tem(c.tbs)) avisos.push("Sem cidade nem TBS externa: usado 32 °C / TBU 24 °C só como exemplo.");
  const r = { cidade:cid ? cid.nome : (c.cidade || ""), lat:pega("lat", -15.8), alt:pega("alt", 0), tbs:pega("tbs", 32), tbu:pega("tbu", 24), dr:pega("dr", 10),
    tint:ou(c.tint, P.tint), urint:ou(c.urint, P.urint) };
  r.p = pressao(r.alt);
  r.w_ext = tem(c.w) ? +c.w / 1000 : tem(c.ur) ? wUR(r.tbs, +c.ur, r.p) : wBulbos(r.tbs, r.tbu, r.p);
  r.w_int = wUR(r.tint, r.urint, r.p);
  r.mes = tem(op.mes) ? Math.min(12, Math.max(1, Math.round(+op.mes))) : (r.lat <= 0 ? 1 : 7);
  r.decl = tem(op.declinacao) ? +op.declinacao : 23.45 * Math.sin(360 * (284 + DADOS.dia_21[r.mes - 1]) / 365 * RAD);
  r.text = DADOS.fracao_amplitude.map(f => r.tbs - r.dr * f);                                // °C, índice = hora solar 0..23
  r.avisos = avisos; return r; }

/* ════════ Sol (hora solar) e irradiância em superfície ════════ */
function sol(cl, h) { const L = cl.lat * RAD, d = cl.decl * RAD, H = 15 * (h - 12) * RAD;
  const sb = Math.cos(L) * Math.cos(d) * Math.cos(H) + Math.sin(L) * Math.sin(d);
  if (sb <= 0) return { sb:0, cb:1, az:0, idn:0, C:0 };
  const cb = Math.sqrt(Math.max(0, 1 - sb * sb)), abc = DADOS.ceu_claro[cl.mes - 1];
  const sAz = -Math.cos(d) * Math.sin(H) / cb, cAz = (Math.sin(d) - sb * Math.sin(L)) / (cb * Math.cos(L));
  return { sb, cb, az:cb < 1e-9 ? 0 : Math.atan2(sAz, cAz) / RAD, idn:abc[0] * Math.exp(-abc[1] / sb), C:abc[2] }; }   /* sol a pino: azimute indefinido e cos β = 0 */
/* orientação: graus a partir do norte, sentido horário (N 0, L 90, S 180, O 270); -1 = horizontal */
function irradiancia(cl, h, orient) { const s = sol(cl, h); if (s.idn <= 0) return 0;
  if (orient < 0) return s.idn * s.sb + s.C * s.idn;                                         // horizontal: direta + difusa
  const cosT = s.cb * Math.cos((s.az - orient) * RAD);
  return s.idn * Math.max(cosT, 0) + s.C * s.idn * 0.5 + K.refletancia_solo * s.idn * (s.C + s.sb) * 0.5; }
const orientGraus = o => { if (tem(o)) return +o; const g = DADOS.orientacoes[String(o || "").toUpperCase()]; return g === undefined ? 0 : g; };

/* ════════ Superfícies ════════ */
function propriedades(s) { const m = DADOS.materiais[s.material] || {};
  return { u:ou(s.u, N(m.u)), atraso:ou(s.atraso, N(m.atraso)), amort:ou(s.amortecimento, tem(m.amortecimento) ? +m.amortecimento : 1),
    alfa:ou(s.absortancia, tem(m.absortancia) ? +m.absortancia : (tem(DADOS.cores[s.cor]) ? DADOS.cores[s.cor] : DADOS.cores.media)),
    fs:ou(s.fs, tem(m.fs) ? +m.fs : 0.82), sombra:ou(s.sombra, 1), nome:m.nome || "" }; }
const interp = (arr, x) => { const y = ((x % 24) + 24) % 24, i = Math.floor(y), f = y - i; return arr[i] * (1 - f) + arr[(i + 1) % 24] * f; };
/* devolve função hora -> {opaca, vsol, vcond} em W */
function superficie(s, cl) { const tipo = s.tipo || "parede", A = N(s.area), pr = propriedades(s), Ti = cl.tint;
  if (tipo === "vidro") { const og = orientGraus(s.orient);
    return h => ({ opaca:0, vsol:A * pr.fs * pr.sombra * irradiancia(cl, h, og), vcond:pr.u * A * (cl.text[h] - Ti) }); }
  if (tipo === "piso_solo") return () => ({ opaca:0, vsol:0, vcond:0 });
  if (tipo === "adjacente") { const fa = ou(s.fator, P.fator_adjacente); return h => ({ opaca:pr.u * A * fa * (cl.text[h] - Ti), vsol:0, vcond:0 }); }
  if (tipo === "piso_exterior") return h => ({ opaca:pr.u * A * (cl.text[h] - Ti), vsol:0, vcond:0 });
  const horiz = tipo === "cobertura", og = horiz ? -1 : orientGraus(s.orient), comSol = s.sol !== false;
  const tsa = []; for (let h = 0; h < 24; h++) tsa.push(cl.text[h] + (comSol ? pr.alfa * irradiancia(cl, h, og) / K.h_ext - (horiz ? K.delta_r_horizontal : 0) : 0));
  const tm = tsa.reduce((a, b) => a + b, 0) / 24;
  return h => ({ opaca:pr.u * A * ((tm - Ti) + pr.amort * (interp(tsa, h - pr.atraso) - tm)), vsol:0, vcond:0 }); }

/* ════════ Ambiente ════════ */
const COMP = ["envoltoria", "vidro_solar", "vidro_conducao", "pessoas_s", "pessoas_l", "iluminacao", "equipamentos", "infiltracao_s", "infiltracao_l", "ar_externo_s", "ar_externo_l"];
const LATENTES = ["pessoas_l", "infiltracao_l", "ar_externo_l"];
function ambiente(a, cl, op) { const area = N(a.area), pe = ou(a.pe_direito, P.pe_direito), vol = area * pe;
  const pes = N(a.pessoas), at = DADOS.atividades[a.atividade] || DADOS.atividades.escritorio, uso = DADOS.ar_externo[a.uso] || DADOS.ar_externo.escritorio;
  const ilum = ou(a.iluminacao_wm2, P.iluminacao_wm2) * area, equip = ou(a.equipamentos_wm2, P.equipamentos_wm2) * area + N(a.equipamentos_w);
  const qInf = ou(a.infiltracao_ach, P.infiltracao_ach) * vol / 3.6;                                          // L/s
  const qAe = op.ar_externo === false ? 0 : tem(a.ar_externo_ls) ? +a.ar_externo_ls : ou(a.ar_externo_lpp, uso.rp) * pes + ou(a.ar_externo_lpm2, uso.ra) * area;
  const ini = ou(a.ini, P.ini), fim = ou(a.fim, P.fim), dw = Math.max(cl.w_ext - cl.w_int, 0);
  const sups = (a.superficies || []).map(s => superficie(s, cl));
  const horas = op.horas.map(h => { const ocup = h >= ini && h <= fim ? 1 : 0, dT = cl.text[h] - cl.tint, c = {};
    c.envoltoria = 0; c.vidro_solar = 0; c.vidro_conducao = 0;
    sups.forEach(f => { const q = f(h); c.envoltoria += q.opaca; c.vidro_solar += q.vsol; c.vidro_conducao += q.vcond; });
    c.pessoas_s = ocup * pes * at.sens; c.pessoas_l = ocup * pes * at.lat; c.iluminacao = ocup * ilum; c.equipamentos = ocup * equip;
    c.infiltracao_s = K.c_sensivel * qInf * dT; c.infiltracao_l = K.c_latente * qInf * dw;
    c.ar_externo_s = ocup * K.c_sensivel * qAe * dT; c.ar_externo_l = ocup * K.c_latente * qAe * dw;
    const lat = LATENTES.reduce((s, k) => s + c[k], 0), tot = COMP.reduce((s, k) => s + c[k], 0);
    return { h, comp:c, sens:tot - lat, lat, total:tot }; });
  let pico = horas[0]; horas.forEach(x => { if (x.total > pico.total) pico = x; });
  const fs = op.fs, W = pico.total * fs;
  return { nome:String(a.nome || ""), area, volume:vol, pessoas:pes, vazao_infiltracao_ls:qInf, vazao_ar_externo_ls:qAe, horas, pico,
    projeto:{ sens:pico.sens * fs, lat:pico.lat * fs, W, btuh:W * K.btu_por_w, tr:W / K.w_por_tr, shr:pico.total > 0 ? pico.sens / pico.total : 1,
      wm2:area > 0 ? W / area : 0 } }; }

/* ════════ Sugestão de sistema e energia anual ════════ */
function baseEquip(op) { if (op.equipamentos) return op.equipamentos;
  try { if (typeof document !== "undefined") { const t = document.getElementById("base-equipamentos"); if (t) return JSON.parse(t.textContent); } } catch (e) { /* sem base */ }
  return null; }
const sazonal = it => it && it.eficiencia ? ou(it.eficiencia.sazonal, N(it.eficiencia.tipico)) : 0;
function escolherSplit(itens, btuh) {
  const ok = itens.filter(i => i.sistema === "split" && tem(i.capacidade_nominal_btuh) && !/conv|janela/.test(i.id));
  const ordem = i => /hiwall/.test(i.id) ? 0 : /cassete/.test(i.id) ? 1 : /pisoteto/.test(i.id) ? 2 : 3;
  const cand = ok.filter(i => i.capacidade_nominal_btuh >= btuh)
    .sort((x, y) => x.capacidade_nominal_btuh - y.capacidade_nominal_btuh || ordem(x) - ordem(y) || sazonal(y) - sazonal(x));
  if (cand.length) return { item:cand[0], qtd:1 };
  const maior = ok.sort((x, y) => y.capacidade_nominal_btuh - x.capacidade_nominal_btuh)[0];
  return maior ? { item:maior, qtd:Math.ceil(btuh / maior.capacidade_nominal_btuh) } : null; }
function escolherFaixa(itens, sistema, kw, filtro) {
  const ok = itens.filter(i => i.sistema === sistema && (!filtro || filtro(i)));
  const dentro = ok.filter(i => kw >= N(i.faixa_capacidade.min) && kw <= N(i.faixa_capacidade.max)).sort((x, y) => sazonal(y) - sazonal(x));
  if (dentro.length) return { item:dentro[0], qtd:1 };
  const maior = ok.sort((x, y) => N(y.faixa_capacidade.max) - N(x.faixa_capacidade.max))[0];
  if (maior && kw > N(maior.faixa_capacidade.max)) return { item:maior, qtd:Math.ceil(kw / N(maior.faixa_capacidade.max)) };
  const menor = ok.sort((x, y) => N(x.faixa_capacidade.min) - N(y.faixa_capacidade.min))[0];
  return menor ? { item:menor, qtd:1 } : null; }
function sugerir(res, op) {
  const R = DADOS.regras_sistema, base = baseEquip(op), itens = base && Array.isArray(base.itens) ? base.itens.filter(i => i.categoria === "ar-condicionado") : [];
  const tr = res.total.projeto.tr, kwP = res.total.projeto.W / 1000, kwBloco = res.total.bloco.total / 1000;
  const amb = res.ambientes.filter(a => a.pico.total > 0), n = amb.length, maxAmb = amb.reduce((m, a) => Math.max(m, a.projeto.W / 1000), 0);
  const energia = (saz, aux) => saz > 0 ? kwBloco * op.horas_ano * op.fator_carga / saz * aux : 0;
  const ops = [];
  /* split: um equipamento por ambiente */
  { const esc_ = itens.length ? amb.map(a => Object.assign({ ambiente:a.nome, btuh:a.projeto.btuh, kw:a.projeto.W / 1000 }, escolherSplit(itens, a.projeto.btuh) || {})) : [];
    const sq = esc_.reduce((s, x) => s + x.kw, 0), sd = esc_.reduce((s, x) => s + (x.item && sazonal(x.item) > 0 ? x.kw / sazonal(x.item) : 0), 0);
    const saz = itens.length && sd > 0 ? sq / sd : DADOS.sistemas_padrao.split.sazonal, aux = DADOS.sistemas_padrao.split.aux;
    const viavel = maxAmb <= R.split_max_ambiente_kw * 1.0001 && tr <= R.split_max_total_tr;
    ops.push({ tipo:"split", nome:"Split por ambiente (hi-wall, cassete ou piso-teto inverter)", viavel,
      motivo:viavel ? "cada ambiente cabe em um equipamento e o total é pequeno" : maxAmb > R.split_max_ambiente_kw ? "há ambiente acima de 60.000 BTU/h" : "total acima de " + R.split_max_total_tr + " TR: muitas condensadoras",
      equipamentos:esc_.map(x => ({ ambiente:x.ambiente, id:x.item ? x.item.id : "", descricao:x.item ? x.item.descricao : "base indisponível", qtd:x.qtd || 1, sazonal:x.item ? sazonal(x.item) : null })),
      sazonal:saz, indicador:"IDRS", aux, kwh_ano:energia(saz, aux) }); }
  /* VRF */
  { const e = itens.length ? escolherFaixa(itens, "vrf", kwP, i => !/recupera/i.test(i.descricao)) : null;
    const saz = e ? sazonal(e.item) : DADOS.sistemas_padrao.vrf.sazonal, aux = e ? ou(e.item.auxiliares_fator, 1) : DADOS.sistemas_padrao.vrf.aux;
    const viavel = tr >= R.vrf_min_tr && tr <= R.vrf_max_tr && n >= R.vrf_min_ambientes;
    ops.push({ tipo:"vrf", nome:"VRF (uma condensadora para vários ambientes)", viavel,
      motivo:viavel ? "vários ambientes com controle individual e carga média" : n < R.vrf_min_ambientes ? "poucos ambientes para justificar o VRF" : tr < R.vrf_min_tr ? "carga pequena demais" : "carga acima da faixa usual de VRF",
      equipamentos:e ? [{ ambiente:"conjunto", id:e.item.id, descricao:e.item.descricao, qtd:e.qtd, sazonal:saz }] : [], sazonal:saz, indicador:"IEER (W/W)", aux, kwh_ano:energia(saz, aux) }); }
  /* chiller */
  { const agua = tr >= R.chiller_agua_min_tr;
    const e = itens.length ? escolherFaixa(itens, "chiller", kwP, i => agua ? /agua/.test(i.id) : /chiller-ar/.test(i.id)) : null;
    const saz = e ? sazonal(e.item) : DADOS.sistemas_padrao.chiller.sazonal, aux = e ? ou(e.item.auxiliares_fator, 1) : DADOS.sistemas_padrao.chiller.aux;
    const viavel = tr >= R.chiller_min_tr;
    ops.push({ tipo:"chiller", nome:"Água gelada (chiller " + (agua ? "a água com torre" : "a ar") + " + fancoils)", viavel,
      motivo:viavel ? "carga grande: central de água gelada compensa" : "carga abaixo de " + R.chiller_min_tr + " TR: central de água gelada não compensa",
      equipamentos:e ? [{ ambiente:"central", id:e.item.id, descricao:e.item.descricao, qtd:e.qtd, sazonal:saz }] : [], sazonal:saz, indicador:"IPLV (COP)", aux, kwh_ano:energia(saz, aux) }); }
  const tarifa = N(op.tarifa); ops.forEach(o => { o.custo_ano = tarifa > 0 ? o.kwh_ano * tarifa : null; });
  let rec = tr >= R.chiller_ideal_tr ? "chiller" : (n >= R.vrf_ideal_ambientes && tr >= R.vrf_ideal_tr) ? "vrf" : "split";
  if (!ops.find(o => o.tipo === rec).viavel) { const v = ops.find(o => o.viavel); rec = v ? v.tipo : "split"; }
  const viaveis = ops.filter(o => o.viavel && o.kwh_ano > 0), menor = viaveis.length ? viaveis.reduce((m, o) => o.kwh_ano < m.kwh_ano ? o : m) : null;
  return { opcoes:ops, recomendado:rec, menor_consumo:menor ? menor.tipo : null, base:!!itens.length }; }

/* ════════ Cálculo principal (função pura) ════════ */
function calcular(ambientes, clima, opcoes) {
  const o = opcoes || {}, op = { horas:Array.isArray(o.horas) && o.horas.length ? o.horas.map(h => Math.round(N(h)) % 24) : P.horas.slice(), fs:ou(o.fs, P.fs),
    horas_ano:ou(o.horas_ano, P.horas_ano), fator_carga:ou(o.fator_carga, P.fator_carga), tarifa:o.tarifa, ar_externo:o.ar_externo, equipamentos:o.equipamentos };
  const cl = resolverClima(clima, Object.assign({}, o)), avisos = cl.avisos.slice();
  const amb = (ambientes || []).map(a => ambiente(a || {}, cl, op));
  const porHora = op.horas.map((h, i) => { const c = {}; COMP.forEach(k => { c[k] = amb.reduce((s, a) => s + a.horas[i].comp[k], 0); });
    const lat = LATENTES.reduce((s, k) => s + c[k], 0), tot = COMP.reduce((s, k) => s + c[k], 0); return { h, comp:c, sens:tot - lat, lat, total:tot }; });
  let bloco = porHora[0] || { h:op.horas[0], comp:{}, sens:0, lat:0, total:0 }; porHora.forEach(x => { if (x.total > bloco.total) bloco = x; });
  const somaPicos = amb.reduce((s, a) => s + a.pico.total, 0), W = bloco.total * op.fs;
  const total = { porHora, bloco, soma_picos:somaPicos, diversidade:somaPicos > 0 ? bloco.total / somaPicos : 1,
    projeto:{ W, btuh:W * K.btu_por_w, tr:W / K.w_por_tr, sens:bloco.sens * op.fs, lat:bloco.lat * op.fs },
    soma_picos_projeto:{ W:somaPicos * op.fs, btuh:somaPicos * op.fs * K.btu_por_w, tr:somaPicos * op.fs / K.w_por_tr },
    grupos:agrupar(bloco.comp) };
  if (amb.some(a => (a.area || 0) <= 0)) avisos.push("Há ambiente sem área.");
  if (cl.lat <= 0 && cl.mes === 1) avisos.push("Sol calculado para 21 de janeiro. Fachadas norte recebem mais sol no inverno: confira também os meses de abril a agosto.");
  const r = { clima:cl, opcoes:op, ambientes:amb, total, avisos };
  r.sistema = sugerir(r, op);
  return r; }
function agrupar(c) { c = c || {}; const g = k => N(c[k]);
  return [["Envoltória (paredes, coberturas, pisos)", g("envoltoria")], ["Vidros — sol", g("vidro_solar")], ["Vidros — condução", g("vidro_conducao")],
    ["Pessoas", g("pessoas_s") + g("pessoas_l")], ["Iluminação", g("iluminacao")], ["Equipamentos", g("equipamentos")],
    ["Infiltração", g("infiltracao_s") + g("infiltracao_l")], ["Ar externo", g("ar_externo_s") + g("ar_externo_l")]].map(x => ({ nome:x[0], W:x[1] })); }

/* ════════ Exemplo ════════ */
function padrao() {
  return { clima:{ cidade:cidadeDoLocal() }, opcoes:{ mes:1, fs:1.1, horas_ano:2600, fator_carga:0.5, tarifa:null },
    ambientes:[
      { nome:"Escritório", area:30, pe_direito:2.8, pessoas:4, atividade:"escritorio", uso:"escritorio", iluminacao_wm2:10, equipamentos_wm2:15, infiltracao_ach:0.5,
        superficies:[{ tipo:"parede", orient:"N", area:12, material:"tijolo_6f_14", cor:"clara" }, { tipo:"vidro", orient:"N", area:4, material:"vidro_simples", sombra:0.7 },
          { tipo:"parede", orient:"O", area:14, material:"tijolo_6f_14", cor:"clara" }, { tipo:"cobertura", area:30, material:"telha_ceramica_laje", cor:"media" }] },
      { nome:"Sala de reunião", area:18, pe_direito:2.8, pessoas:8, atividade:"escritorio", uso:"reuniao", iluminacao_wm2:10, equipamentos_wm2:5, infiltracao_ach:0.5,
        superficies:[{ tipo:"parede", orient:"L", area:10, material:"taipa_30", cor:"media" }, { tipo:"vidro", orient:"L", area:3, material:"vidro_duplo" },
          { tipo:"cobertura", area:18, material:"telhado_verde_extensivo" }] }] }; }

/* ════════ Desenho (globais da plataforma) ════════ */
const fmt = (v, c) => (v == null || !isFinite(v)) ? "—" : (typeof n2 === "function" ? n2(v, c == null ? 0 : c) : Number(v).toFixed(c == null ? 0 : c));
const idDe = p => "ct-" + String(p).replace(/[^A-Za-z0-9_-]/g, "_");
const valIn = v => v == null || v === "" ? "" : typeof v === "number" ? String(+v.toPrecision(12)).replace(".", ",") : String(v);
function ctl(p, v, t, opt) { opt = opt || {}; const id = idDe(p), k = `id="${id}" data-ct-k="${esc(p)}" data-ct-t="${t}"`;
  if (opt.ops) return `<select ${k}>${opt.ops.map(o => `<option value="${esc(o[0])}" ${String(o[0]) === String(v == null ? "" : v) ? "selected" : ""}>${esc(o[1])}</option>`).join("")}</select>`;
  return `<input type="text" ${k} ${t === "s" ? "" : 'inputmode="decimal"'} value="${esc(valIn(v))}"${opt.ph != null ? ` placeholder="${esc(valIn(opt.ph))}"` : ""} style="width:${opt.w || "100%"}">`; }
const campo = (p, v, rot, t, opt, ajuda) => `<div><label for="${idDe(p)}">${esc(rot)}</label>${ctl(p, v, t, opt)}${ajuda ? `<span class="t2 pq">${esc(ajuda)}</span>` : ""}</div>`;
const celula = (p, v, rot, t, opt) => `<td><label class="so-leitor" for="${idDe(p)}">${esc(rot)}</label>${ctl(p, v, t, Object.assign({ w:"6.5em" }, opt || {}))}</td>`;
const tabela = (cap, cab, linhas) => `<div class="rolagem"><table><caption>${esc(cap)}</caption><thead><tr>${cab.map(h => `<th scope="col">${h}</th>`).join("")}</tr></thead><tbody>${linhas.join("")}</tbody></table></div>`;
const secao = (id, tit, corpo) => `<section class="cartao" aria-labelledby="h-ct-${id}"><h3 id="h-ct-${id}" class="t3">${esc(tit)}</h3>${corpo}</section>`;
const botao = (acao, txt, rot) => `<button type="button" id="ct-b-${acao.replace(/[^A-Za-z0-9]/g, "_")}" data-ct-acao="${esc(acao)}"${rot ? ` aria-label="${esc(rot)}"` : ""}>${esc(txt)}</button>`;
const OPS = obj => Object.keys(obj).filter(k => k[0] !== "_").map(k => [k, obj[k].nome || k]);
const MATS = tipo => Object.keys(DADOS.materiais).filter(k => k[0] !== "_" && DADOS.materiais[k].tipo === tipo).map(k => [k, DADOS.materiais[k].nome]);
const TIPOS_SUP = [["parede", "Parede externa"], ["cobertura", "Cobertura"], ["vidro", "Vidro / janela"], ["adjacente", "Divisa com ambiente sem ar"], ["piso_exterior", "Piso sobre área aberta"], ["piso_solo", "Piso sobre o solo"]];
const ORI = [["N", "Norte"], ["NE", "Nordeste"], ["L", "Leste"], ["SE", "Sudeste"], ["S", "Sul"], ["SO", "Sudoeste"], ["O", "Oeste"], ["NO", "Noroeste"], ["H", "Horizontal (claraboia)"]];
const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const CORES_SVG = ["#33512F", "#7FA874", "#B9CDB3", "#B07A10", "#546A7B", "#8FB183", "#A85432", "#8A8270"];

function grafico(grupos) { const tot = grupos.reduce((s, g) => s + Math.max(g.W, 0), 0); if (!(tot > 0)) return "";
  const larg = 640, alt = 28 * grupos.length + 16, maxW = Math.max.apply(null, grupos.map(g => Math.max(g.W, 0))) || 1, x0 = 250;
  const barras = grupos.map((g, i) => { const w = Math.max(g.W, 0) / maxW * (larg - x0 - 90), y = 8 + i * 28;
    return `<text x="${x0 - 8}" y="${y + 15}" text-anchor="end" font-size="13" fill="#1C2B21">${esc(g.nome)}</text>`
      + `<rect x="${x0}" y="${y + 2}" width="${w.toFixed(1)}" height="18" fill="${CORES_SVG[i % CORES_SVG.length]}"></rect>`
      + `<text x="${(x0 + w + 6).toFixed(1)}" y="${y + 15}" font-size="13" fill="#4A4F44">${esc(fmt(g.W / tot * 100, 0))} %</text>`; }).join("");
  return `<figure><svg viewBox="0 0 ${larg} ${alt}" width="100%" role="img" aria-labelledby="ct-graf-t"><title id="ct-graf-t">Parcela de cada componente na carga do pico simultâneo</title>${barras}</svg>`
    + `<figcaption class="t2 pq">Os mesmos números estão na tabela abaixo.</figcaption></figure>`; }

function ler(estado) { if (estado && typeof estado === "object" && Array.isArray(estado.ambientes)) return estado;
  try { if (typeof calcLer === "function") { const o = calcLer("cargatermica") || {}; if (o.e && Array.isArray(o.e.ambientes)) return o.e; } } catch (e) { /* sem estado salvo */ }
  return padrao(); }
function gravar(e) { if (typeof calcGravar === "function") { const o = (typeof calcLer === "function" && calcLer("cargatermica")) || {}; o.e = e; calcGravar("cargatermica", o); } }

const TITULO_CT = `<h2 id="h-ct">Carga térmica</h2>`;   /* um só título (com ou sem o clima) */
function telaCargaTermica(estado) { const e = ler(estado), c0 = e.clima || {}, o = e.opcoes || {};
  /* cidade vazia e TBS vazia: vem do local da plataforma; sem local, a carga (que depende do clima) não é calculada */
  const Lp = localPlataforma(), auto = !cidadePorNome(c0.cidade) && !tem(c0.tbs) ? cidadeDoLocal() : "";
  const c = auto ? Object.assign({}, c0, { cidade:auto }, !tem(c0.lat) && Lp && Lp.lat != null ? { lat:Lp.lat } : {}) : c0;
  const semClima = !cidadePorNome(c.cidade) && !tem(c.tbs);
  const R = semClima ? null : calcular(e.ambientes, c, o), cl = R ? R.clima : null, cid = cidadePorNome(c.cidade) || {};
  const ph = k => tem(cid[k]) ? cid[k] : null;
  const clima = secao("clima", "Clima de projeto e premissas", `<div class="precos">`
    + campo("clima.cidade", c.cidade || "", "Cidade (condições de verão)", "s", { ops:[["", "Outra — informar abaixo"]].concat(DADOS.cidades.map(x => [x.nome, x.nome + " / " + x.uf])) })
    + campo("clima.lat", c.lat, "Latitude (graus, negativa no sul)", "nn", { ph:ph("lat") })
    + campo("clima.alt", c.alt, "Altitude (m)", "nn", { ph:ph("alt") })
    + campo("clima.tbs", c.tbs, "TBS externa de projeto (°C)", "nn", { ph:ph("tbs") })
    + campo("clima.tbu", c.tbu, "TBU coincidente (°C)", "nn", { ph:ph("tbu") })
    + campo("clima.dr", c.dr, "Amplitude diária (°C)", "nn", { ph:ph("dr") })
    + campo("clima.tint", c.tint, "Temperatura interna (°C)", "nn", { ph:P.tint })
    + campo("clima.urint", c.urint, "Umidade interna (%)", "nn", { ph:P.urint })
    + campo("opcoes.mes", o.mes, "Mês do cálculo solar", "n", { ops:MESES.map((m, i) => [String(i + 1), m]) })
    + campo("opcoes.fs", o.fs, "Fator de segurança", "nn", { ph:P.fs })
    + campo("opcoes.horas_ano", o.horas_ano, "Horas de uso por ano", "nn", { ph:P.horas_ano })
    + campo("opcoes.fator_carga", o.fator_carga, "Fator de carga médio (0 a 1)", "nn", { ph:P.fator_carga }, "Fração média do pico ao longo do ano — premissa Physis.")
    + campo("opcoes.tarifa", o.tarifa, "Tarifa de energia (R$/kWh)", "nn", {}, "Sem tarifa, o custo fica em branco.")
    + `</div>${auto ? `<p class="t2" role="status">Cidade de projeto tirada do local da plataforma: <strong>${esc(auto)}</strong>. Escolha outra acima para trocar.</p>` : ""}<p class="t2 pq">Campos vazios usam o valor da cidade (mostrado em cinza). Valores de cidade, materiais e ar externo vêm de tabelas públicas lembradas e estão marcados para conferência na base.</p>`);
  const ambs = (e.ambientes || []).map((a, i) => { const pre = "ambientes." + i + ".";
    const sups = (a.superficies || []).map((s, j) => { const sp = pre + "superficies." + j + ".", t = s.tipo || "parede";
      const mats = t === "vidro" ? MATS("vidro") : t === "cobertura" ? MATS("cobertura") : t === "parede" ? MATS("parede") : MATS("parede").concat(MATS("piso"));
      return `<tr><th scope="row">${j + 1}</th>${celula(sp + "tipo", t, "Tipo da superfície " + (j + 1), "s", { ops:TIPOS_SUP, w:"11em" })}`
        + celula(sp + "orient", s.orient || "N", "Orientação da superfície " + (j + 1), "s", { ops:ORI, w:"8em" })
        + celula(sp + "area", s.area, "Área da superfície " + (j + 1) + " (m²)", "n")
        + celula(sp + "material", s.material || "", "Material da superfície " + (j + 1), "s", { ops:[["", "— informar U —"]].concat(mats), w:"14em" })
        + celula(sp + "u", s.u, "U da superfície " + (j + 1) + " (W/m²K), vazio = do material", "nn", { ph:propriedades(s).u })
        + celula(sp + "cor", s.cor || "media", "Cor da superfície " + (j + 1), "s", { ops:Object.keys(DADOS.cores).filter(k => k[0] !== "_").map(k => [k, k]), w:"7em" })
        + celula(sp + "sombra", s.sombra, "Sombreamento da superfície " + (j + 1) + " (1 = sem sombra)", "nn", { ph:1 })
        + `<td>${botao("del-sup:" + i + ":" + j, "Remover", "Remover superfície " + (j + 1) + " de " + (a.nome || "ambiente"))}</td></tr>`; });
    return secao("a" + i, "Ambiente " + (i + 1) + (a.nome ? " — " + a.nome : ""), `<div class="precos">`
      + campo(pre + "nome", a.nome, "Nome", "s") + campo(pre + "area", a.area, "Área (m²)", "n") + campo(pre + "pe_direito", a.pe_direito, "Pé-direito (m)", "nn", { ph:P.pe_direito })
      + campo(pre + "pessoas", a.pessoas, "Pessoas", "n") + campo(pre + "atividade", a.atividade || "escritorio", "Atividade", "s", { ops:OPS(DADOS.atividades) })
      + campo(pre + "uso", a.uso || "escritorio", "Uso (ar externo)", "s", { ops:OPS(DADOS.ar_externo) })
      + campo(pre + "iluminacao_wm2", a.iluminacao_wm2, "Iluminação (W/m²)", "nn", { ph:P.iluminacao_wm2 })
      + campo(pre + "equipamentos_wm2", a.equipamentos_wm2, "Equipamentos (W/m²)", "nn", { ph:P.equipamentos_wm2 })
      + campo(pre + "infiltracao_ach", a.infiltracao_ach, "Infiltração (trocas por hora)", "nn", { ph:P.infiltracao_ach })
      + campo(pre + "ini", a.ini, "Ocupação: início (h)", "nn", { ph:P.ini }) + campo(pre + "fim", a.fim, "Ocupação: fim (h)", "nn", { ph:P.fim })
      + `</div>` + tabela("Superfícies de " + (a.nome || "ambiente " + (i + 1)), ["Nº", "Tipo", "Orientação", "Área (m²)", "Material", "U (W/m²K)", "Cor", "Sombra", "Ação"], sups)
      + `<p>${botao("add-sup:" + i, "Acrescentar superfície")} ${botao("del-amb:" + i, "Remover ambiente", "Remover o ambiente " + (a.nome || i + 1))}</p>`); }).join("");
  if (semClima) return `<section aria-labelledby="h-ct">${TITULO_CT}`
    + (typeof avisoSemLocal === "function" ? avisoSemLocal() : `<p class="faixa at" role="status">Local não informado — preencha na página Início.</p>`)
    + `<p class="t2">Sem o local, a carga térmica não usa clima de exemplo: escolha a cidade de projeto ou digite a TBS externa abaixo.</p>` + clima + ambs
    + `<p>${botao("add-amb", "Acrescentar ambiente")} ${botao("reset", "Voltar ao exemplo")}</p></section>`;
  const T = R.total;
  const linhas = R.ambientes.map(a => `<tr><th scope="row">${esc(a.nome || "—")}</th><td>${fmt(a.pico.h, 0)} h</td><td>${fmt(a.pico.sens)}</td><td>${fmt(a.pico.lat)}</td><td>${fmt(a.pico.total)}</td>`
    + `<td>${fmt(a.projeto.W)}</td><td>${fmt(a.projeto.btuh)}</td><td>${fmt(a.projeto.tr, 2)}</td><td>${fmt(a.projeto.wm2)}</td></tr>`)
    .concat([`<tr><th scope="row">Soma dos picos</th><td>—</td><td>—</td><td>—</td><td>${fmt(T.soma_picos)}</td><td>${fmt(T.soma_picos_projeto.W)}</td><td>${fmt(T.soma_picos_projeto.btuh)}</td><td>${fmt(T.soma_picos_projeto.tr, 2)}</td><td>—</td></tr>`,
      `<tr><th scope="row">Pico simultâneo</th><td>${fmt(T.bloco.h, 0)} h</td><td>${fmt(T.bloco.sens)}</td><td>${fmt(T.bloco.lat)}</td><td>${fmt(T.bloco.total)}</td><td>${fmt(T.projeto.W)}</td><td>${fmt(T.projeto.btuh)}</td><td>${fmt(T.projeto.tr, 2)}</td><td>—</td></tr>`]);
  const res = secao("res", "Resultado por ambiente", tabela("Carga de pico (W) e capacidade de projeto com fator de segurança " + fmt(R.opcoes.fs, 2), ["Ambiente", "Hora do pico", "Sensível (W)", "Latente (W)", "Total (W)", "Projeto (W)", "Projeto (BTU/h)", "Projeto (TR)", "W/m²"], linhas)
    + `<p class="t2 pq">Split por ambiente usa o pico de cada ambiente; sistema central (VRF, chiller) usa o pico simultâneo (diversidade ${fmt(T.diversidade * 100, 0)} %).</p>`);
  const tg = T.grupos.reduce((s, g) => s + g.W, 0);
  const comp = secao("comp", "De onde vem o calor (pico simultâneo, " + fmt(T.bloco.h, 0) + " h)", grafico(T.grupos)
    + tabela("Componentes da carga no pico simultâneo", ["Componente", "W", "%"], T.grupos.map(g => `<tr><th scope="row">${esc(g.nome)}</th><td>${fmt(g.W)}</td><td>${tg ? fmt(g.W / tg * 100, 1) : "—"}</td></tr>`)));
  const perfil = secao("perfil", "Perfil horário do conjunto", tabela("Carga total do conjunto por hora solar (sem fator de segurança)", ["Hora", "Temperatura externa (°C)", "Sensível (W)", "Latente (W)", "Total (W)"],
    T.porHora.map(x => `<tr><th scope="row">${fmt(x.h, 0)} h</th><td>${fmt(cl.text[x.h], 1)}</td><td>${fmt(x.sens)}</td><td>${fmt(x.lat)}</td><td>${fmt(x.total)}</td></tr>`)));
  const S = R.sistema, nomeRec = (S.opcoes.find(x => x.tipo === S.recomendado) || {}).nome || "";
  const sis = secao("sis", "Sistema sugerido e energia anual", `<p><strong>Sugestão: ${esc(nomeRec)}.</strong>${S.menor_consumo && S.menor_consumo !== S.recomendado ? " Menor consumo entre os viáveis: " + esc((S.opcoes.find(x => x.tipo === S.menor_consumo) || {}).nome || "") + "." : ""}</p>`
    + tabela("Comparação de sistemas (energia = pico simultâneo × horas por ano × fator de carga ÷ eficiência sazonal × auxiliares)", ["Sistema", "Viável?", "Motivo", "Equipamento", "Eficiência sazonal", "Energia (kWh/ano)", "Custo (R$/ano)"],
      S.opcoes.map(x => `<tr><th scope="row">${esc(x.nome)}</th><td>${x.viavel ? "sim" : "não"}</td><td>${esc(x.motivo)}</td><td>${x.equipamentos.length ? x.equipamentos.map(q => esc((q.qtd > 1 ? q.qtd + " × " : "") + q.descricao + (q.ambiente && q.ambiente !== "conjunto" && q.ambiente !== "central" ? " (" + q.ambiente + ")" : ""))).join("<br>") : "—"}</td>`
        + `<td>${fmt(x.sazonal, 1)} ${esc(x.indicador)}</td><td>${fmt(x.kwh_ano)}</td><td>${x.custo_ano == null ? "informe a tarifa" : (typeof brl === "function" ? brl(Math.round(x.custo_ano)) : fmt(x.custo_ano))}</td></tr>`))
    + (S.base ? "" : `<p class="t2 pq">Base de equipamentos não carregada: eficiências-padrão usadas.</p>`)
    + `<p class="t2 pq">Equipamentos por classe genérica (sem marca). Confira a eficiência na tabela do Inmetro vigente e cote com três fornecedores.</p>`);
  const av = R.avisos.length ? `<ul class="t2">${R.avisos.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : "";
  return `<section aria-labelledby="h-ct">${TITULO_CT}`
    + `<p class="t2 apoio">Carga de resfriamento por ambiente (sensível e latente), hora a hora das 8 às 18 h, no caminho da NBR 16401-1: envoltória com sol e massa térmica, vidros, pessoas, iluminação, equipamentos, infiltração e ar externo. Resultado em W, BTU/h e TR, com sugestão de sistema.</p>`
    + av + clima + ambs + `<p>${botao("add-amb", "Acrescentar ambiente")} ${botao("reset", "Voltar ao exemplo")}</p>` + res + comp + perfil + sis
    + `<p class="t2 pq">Estudo preliminar: não substitui o projeto de AVAC assinado. Método simplificado (sem fator de armazenamento de carga radiante); revisar com software de simulação no projeto executivo.</p></section>`; }

/* ════════ Eventos (atributos data-ct-…) ════════ */
function setPath(obj, path, v) { const ps = String(path).split("."); let c = obj;
  for (let i = 0; i < ps.length - 1; i++) { const k = ps[i]; if (c[k] == null || typeof c[k] !== "object") c[k] = /^\d+$/.test(ps[i + 1]) ? [] : {}; c = c[k]; }
  c[ps[ps.length - 1]] = v; }
const redesenhar = id => { if (typeof desenhar === "function") desenhar(false); const x = typeof el === "function" ? el(id) : null; if (x) x.focus(); };
if (typeof document !== "undefined" && typeof window !== "undefined" && !window.__ctEventos) { window.__ctEventos = true;
  document.addEventListener("change", ev => { const t = ev.target; if (!t || !t.dataset || t.dataset.ctK == null) return;
    const tp = t.dataset.ctT || "n", s = String(t.value).trim(); let v;
    if (tp === "s") v = t.value; else { v = s === "" ? null : (typeof numBr === "function" ? numBr(s) : Number(s.replace(",", "."))); if (v == null || !isFinite(v)) v = tp === "nn" ? null : 0; }
    const e = ler(); setPath(e, t.dataset.ctK, v); gravar(e); redesenhar(t.id); });
  document.addEventListener("click", ev => { const b = ev.target && ev.target.closest ? ev.target.closest("button[data-ct-acao]") : null; if (!b) return;
    const [ac, i, j] = String(b.dataset.ctAcao).split(":"); let e = ler(); const id = b.id;
    if (ac === "reset") { if (typeof confirm === "function" && !confirm("Substituir os dados da carga térmica pelo exemplo?")) return; e = padrao(); }
    if (ac === "add-amb") e.ambientes.push({ nome:"Novo ambiente", area:0, pessoas:0, atividade:"escritorio", uso:"escritorio", superficies:[] });
    if (ac === "del-amb") e.ambientes.splice(+i, 1);
    if (ac === "add-sup") (e.ambientes[+i].superficies = e.ambientes[+i].superficies || []).push({ tipo:"parede", orient:"N", area:0, material:"tijolo_6f_14", cor:"media" });
    if (ac === "del-sup") e.ambientes[+i].superficies.splice(+j, 1);
    gravar(e); redesenhar(typeof el === "function" && el(id) ? id : "ct-b-add_amb"); }); }

const API = { calcular, padrao, resolverClima, irradiancia, sol, DADOS, versao:"CT-1" };
if (typeof window !== "undefined") { window.CARGA_TERMICA = API; window.telaCargaTermica = telaCargaTermica; }
if (typeof module !== "undefined" && module.exports) module.exports = API;
})();
