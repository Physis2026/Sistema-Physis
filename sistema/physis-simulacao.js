/* physis-simulacao.js — simulações leves da Fase 1 no navegador, sem internet (pedido de 15/11/2026).
   Espelho de physis-hub/physis_hub/simulacao/ (mesmas contas, mesma ordem de operações; paridade conferida nos casos
   comuns de sistema/simulacao-exemplos/ por physis-hub/tests/test_simulacao_paridade.py e pela página
   ferramentas/testes-navegador/conferir-simulacao.html).
   Contrato com a plataforma:
     window.SIMULACAO = { termica, estrutura, fluidos, terreno, incerteza, qubo, biogas, comum, painel, autoteste, ... }
       (funções puras; cada resultado traz metodo, hipoteses, premissas_usadas, malha, limites_validade e aviso);
     telaSimulacao() = HTML da aba "Simulação" (um só h1), com os exemplos desenhados (deformada, campo de
       temperatura, acumulação de fluxo, campo do LBM, curvas do biogás) e a entrada em JSON para rodar de novo;
     SIMULACAO.painel(tipo, entrada) = cartão (h2) para pôr dentro de outra aba (AVAC, Economia circular,
       Mapeamento, Turbinas, Secador, SbN, Solar, Carbono);
     window.SIMULACAO_I18N (português → inglês).
   Bases lidas se existirem: <script id="base-materiais">, <script id="base-fatores-emissao">, window.PhysisCalc
   (premissas gerais), window.TURBINAS (contas do vento), window.SIMULACAO_CASOS (exemplos). Premissas próprias
   copiadas abaixo entre SIM-PREMISSAS-INICIO e SIM-PREMISSAS-FIM por `python -m physis_hub.simulacao.casos --gravar`.
   Globais usadas só para desenhar, se existirem: esc, ui, desenhar. Nada aprova projeto: pré-dimensionamento. */
(function (global) {
"use strict";
if (global.SIMULACAO) return;
/*SIM-PREMISSAS-INICIO*/
var PREM = {"premissas":[{"id":"sim.termica.resistencias_superficiais","grandeza":"Resistências superficiais interna e externa (Rsi, Rse)","valor_padrao":{"parede":{"rsi":0.13,"rse":0.04},"cobertura_verao":{"rsi":0.17,"rse":0.04}},"unidade":"m²·K/W","opcoes":[],"fonte":"ABNT NBR 15220-2 (tabela de resistências superficiais), mesmos valores de sistema/physis-materiais.json (resistencias_superficiais) [CONFERIR NA NORMA]","status":"conferir","nota":"Teste confere que é igual à base de materiais. Cobertura no verão = fluxo descendente."},{"id":"sim.termica.h_conv_vento","grandeza":"Coeficiente de convecção externa em função do vento (h = a + b·v)","valor_padrao":{"a":5.7,"b":3.8},"unidade":"W/(m²·K), v em m/s","opcoes":[],"fonte":"correlação de McAdams para superfície ao vento (literatura de transferência de calor) [CONFERIR]","status":"conferir","nota":"Só para quem precisa separar convecção de radiação (câmara do Secador). Paredes usam Rse."},{"id":"sim.termica.emissividade","grandeza":"Emissividade de superfícies comuns de construção (onda longa)","valor_padrao":0.9,"unidade":"adimensional (0 a 1)","opcoes":[],"fonte":"ordem de grandeza de literatura para alvenaria, terra, madeira e tinta não metálica [CONFERIR]","status":"conferir","nota":"Metal polido e manta aluminizada têm emissividade muito menor: digite o valor do fabricante."},{"id":"sim.estrutura.materiais","grandeza":"Propriedades estruturais por material (E, G, fy, ν, densidade)","valor_padrao":{"aco_estrutural":{"nome":"Aço estrutural de perfil","E_Pa":200000000000,"G_Pa":77000000000,"fy_Pa":250000000,"nu":0.3,"densidade":7800},"aluminio":{"nome":"Alumínio de perfil (liga a definir)","E_Pa":70000000000,"G_Pa":26000000000,"fy_Pa":null,"nu":0.33,"densidade":2700},"madeira_eucalipto":{"nome":"Eucalipto tratado","E_Pa":null,"G_Pa":null,"fy_Pa":null,"nu":null,"densidade":750},"bambu":{"nome":"Bambu (colmo)","E_Pa":null,"G_Pa":null,"fy_Pa":null,"nu":null,"densidade":700}},"unidade":"Pa; kg/m³","opcoes":[],"fonte":"aço: valores usuais de aço estrutural (fy do aço ASTM A36 / MR250) [CONFERIR NA NORMA ABNT NBR 8800]; alumínio: E usual, fy depende da liga e da têmpera [MARCADOR]; madeira: classe de resistência da ABNT NBR 7190 ou ensaio [MARCADOR]; bambu: ensaio (ISO 22156 / ABNT NBR 16828) [MARCADOR]. Densidades de sistema/physis-materiais.json.","status":"conferir","nota":"null = a conta pede o valor ([MARCADOR]). Bambu e madeira variam muito de peça para peça."},{"id":"sim.estrutura.k_flambagem","grandeza":"Coeficiente de comprimento de flambagem K por condição de apoio","valor_padrao":{"biapoiada":1.0,"engaste_livre":2.0,"engaste_engaste":0.5,"engaste_apoio":0.7},"unidade":"adimensional","opcoes":[],"fonte":"valores teóricos da flambagem de Euler (livros de resistência dos materiais); as normas recomendam valores um pouco maiores para projeto [CONFERIR NA NORMA]","status":"conferir","nota":"Engaste real nunca é perfeito: usar o K de projeto da norma do material."},{"id":"sim.estrutura.fs_tensao","grandeza":"Fator de segurança global na tensão (σ ≤ fy/FS)","valor_padrao":1.5,"unidade":"adimensional","opcoes":[],"fonte":"premissa Physis provisória para triagem por tensões admissíveis; o dimensionamento segue os coeficientes da norma do material [CONFERIR NA NORMA]","status":"conferir","nota":"Triagem, não dimensionamento."},{"id":"sim.estrutura.fs_flambagem","grandeza":"Fator de segurança na flambagem (|N| ≤ Pcr/FS)","valor_padrao":2.0,"unidade":"adimensional","opcoes":[],"fonte":"premissa Physis provisória [CONFERIR NA NORMA]","status":"conferir","nota":"Imperfeições e excentricidade reduzem a carga real; a norma tem curvas próprias."},{"id":"sim.vento.pressao_dinamica","grandeza":"Pressão dinâmica do vento: q = coef·Vk², Vk = V0·S1·S2·S3, F = Cf·q·A","valor_padrao":{"coef_q":0.613,"v0":null,"s1":null,"s2":null,"s3":null,"cf":null},"unidade":"coef em N·s²/m⁴; V0 em m/s; S e Cf adimensionais","opcoes":[],"fonte":"método da ABNT NBR 6123 (só o nome do método; V0 do mapa de isopletas, S1, S2, S3 e Cf das tabelas da norma) [CONFERIR NA NORMA]","status":"conferir","nota":"coef_q = ½·ρ do ar padrão. Os fatores do lugar e da peça são digitados pelo engenheiro; null vira [MARCADOR]."},{"id":"sim.turbinas.ct_empuxo","grandeza":"Coeficiente de empuxo do rotor (C_T) para a força no topo da torre","valor_padrao":0.89,"unidade":"adimensional","opcoes":[],"fonte":"teoria do disco atuador no ponto de Betz (C_T = 8/9) [CONFERIR com o fabricante]","status":"conferir","nota":"Na velocidade de sobrevivência a carga vem do rotor parado e do arrasto: dado do fabricante."},{"id":"sim.ventilacao.cd","grandeza":"Coeficiente de descarga de aberturas (ventilação natural)","valor_padrao":0.6,"unidade":"adimensional","opcoes":[],"fonte":"valor usual de orifício de borda viva na literatura de ventilação natural [CONFERIR]","status":"conferir","nota":"Venezianas e telas reduzem: usar o dado do fabricante."},{"id":"sim.ventilacao.cp_vento","grandeza":"Coeficientes de pressão do vento na fachada (barlavento e sotavento)","valor_padrao":{"barlavento":0.5,"sotavento":-0.3},"unidade":"adimensional","opcoes":[],"fonte":"ordem de grandeza de literatura para prédio baixo isolado [CONFERIR]; túnel de vento ou norma valem mais","status":"conferir","nota":"ΔCp = barlavento − sotavento entra em Q = Cd·A·v·√ΔCp."},{"id":"sim.hidro.cn_por_uso","grandeza":"Número de curva (CN) por uso do solo e grupo hidrológico (A a D)","valor_padrao":{"mata":{"A":30,"B":55,"C":70,"D":77},"pasto_bom":{"A":39,"B":61,"C":74,"D":80},"pasto_degradado":{"A":68,"B":79,"C":86,"D":89},"lavoura":{"A":67,"B":78,"C":85,"D":89},"solo_exposto":{"A":77,"B":86,"C":91,"D":94},"estrada_terra":{"A":72,"B":82,"C":87,"D":89},"urbano_denso":{"A":77,"B":85,"C":90,"D":92},"impermeavel":{"A":98,"B":98,"C":98,"D":98},"agrofloresta":{"A":null,"B":null,"C":null,"D":null}},"unidade":"adimensional (0 a 100)","opcoes":[],"fonte":"USDA NRCS, TR-55 (1986), tabelas de número de curva para condição de umidade média [CONFERIR]","status":"conferir","nota":"Agrofloresta não está na tabela: [MARCADOR] até haver valor de estudo. Solo do lugar define o grupo A–D."},{"id":"sim.hidro.ia_razao","grandeza":"Abstração inicial do SCS-CN (Ia = razão·S)","valor_padrao":0.2,"unidade":"adimensional","opcoes":[],"fonte":"USDA NRCS, método do número de curva [CONFERIR]","status":"conferir","nota":"Alguns estudos recentes usam 0,05."},{"id":"sim.erosao.ls","grandeza":"Fator topográfico LS da USLE: (λ/λ_ref)^m·(a·sen²θ + b·senθ + c)","valor_padrao":{"lambda_ref":22.13,"a":65.41,"b":4.56,"c":0.065},"unidade":"λ em m","opcoes":[],"fonte":"Wischmeier & Smith (1978), USDA Agriculture Handbook 537 [CONFERIR]","status":"conferir","nota":"Expoente m pela declividade (0,5 ≥ 5 %; 0,4; 0,3; 0,2 < 1 %). R, K, C e P são digitados do estudo do lugar."},{"id":"sim.mc.amostras","grandeza":"Número de amostras do Monte Carlo","valor_padrao":2000,"unidade":"amostras","opcoes":[],"fonte":"premissa Physis","status":"conferir","nota":"Mais amostras = percentis mais estáveis."},{"id":"sim.mc.semente","grandeza":"Semente do gerador pseudoaleatório (mulberry32)","valor_padrao":42,"unidade":"inteiro","opcoes":[],"fonte":"premissa Physis (reprodutível: mesma semente, mesmo resultado no servidor e no navegador)","status":"conferir","nota":"Fixa nos testes."},{"id":"sim.qubo.penalidade_fator","grandeza":"Fator da penalidade das restrições no QUBO","valor_padrao":1.5,"unidade":"adimensional (× maior ganho)","opcoes":[],"fonte":"premissa Physis","status":"conferir","nota":"Penalidade pequena deixa violar restrição; grande demais atrapalha o recozimento."},{"id":"sim.qubo.limite_exato","grandeza":"Até quantas variáveis o QUBO é resolvido por enumeração exata","valor_padrao":20,"unidade":"variáveis","opcoes":[],"fonte":"premissa Physis","status":"conferir","nota":"Acima disso, recozimento simulado."},{"id":"sim.qubo.varreduras","grandeza":"Varreduras do recozimento simulado","valor_padrao":400,"unidade":"varreduras","opcoes":[],"fonte":"premissa Physis","status":"conferir","nota":""},{"id":"sim.qubo.suavidade","grandeza":"Peso da suavidade na topologia grossa (β)","valor_padrao":0.2,"unidade":"adimensional","opcoes":[],"fonte":"premissa Physis","status":"conferir","nota":"Maior β = peça com menos furos isolados."},{"id":"sim.biogas.substratos","grandeza":"Substratos do biodigestor: ST, SV, BMP, fração de CH₄ e N-P-K do digestato","valor_padrao":{"esterco_bovino":{"nome":"Esterco bovino (fresco, com urina)","st":0.1,"sv":0.8,"bmp":0.38,"ch4":0.55,"esterco":true,"rebanho":"gado_leite","npk":{"N":3.5,"P2O5":1.5,"K2O":4.0}},"esterco_suino":{"nome":"Dejeto suíno (chorume)","st":0.06,"sv":0.8,"bmp":0.42,"ch4":0.6,"esterco":true,"rebanho":"suino","npk":{"N":4.5,"P2O5":2.5,"K2O":2.5}},"cama_aviario":{"nome":"Cama de aviário / esterco de aves","st":0.25,"sv":0.75,"bmp":0.4,"ch4":0.6,"esterco":true,"rebanho":null,"npk":{"N":20.0,"P2O5":15.0,"K2O":15.0}},"restos_alimentos":{"nome":"Restos de alimentos","st":0.2,"sv":0.9,"bmp":0.65,"ch4":0.6,"esterco":false,"npk":null},"residuos_colheita":{"nome":"Resíduos de colheita (palha seca)","st":0.85,"sv":0.9,"bmp":0.35,"ch4":0.52,"esterco":false,"npk":null},"lodo_esgoto":{"nome":"Lodo de esgoto","st":0.04,"sv":0.7,"bmp":0.4,"ch4":0.62,"esterco":false,"npk":null},"outro":{"nome":"Outro substrato","st":null,"sv":null,"bmp":null,"ch4":null,"esterco":false,"npk":null}},"unidade":"st: fração da massa fresca; sv: fração dos ST; bmp: m³ de biogás por kg SV; ch4: fração do biogás; npk: kg por tonelada fresca","opcoes":[],"fonte":"faixas típicas de tabelas de substratos para biogás (FNR, Leitfaden Biogas; KTBL) e literatura de digestão anaeróbia [CONFERIR]; N-P-K de tabelas de adubação com dejetos [CONFERIR]","status":"conferir","nota":"Ensaio de BMP e análise de ST/SV do substrato real valem mais. 'outro' sem valores: [MARCADOR]. Conferência cruzada: ST × SV × BMP perto de residuos.biogas_por_kg (m³ por kg fresco)."},{"id":"sim.biogas.cinetica","grandeza":"Cinética de 1ª ordem: k(T) = k_ref·θ^(T − T_ref)","valor_padrao":{"k_ref_dia":0.15,"theta":1.06,"t_ref_c":35},"unidade":"k em 1/dia; T em °C","opcoes":[],"fonte":"ordem de grandeza de literatura de digestão anaeróbia de dejetos (correção de temperatura na forma θ, tipo Arrhenius) [CONFERIR]","status":"conferir","nota":"Cada substrato pode ter k_ref próprio (campo k_ref do substrato)."},{"id":"sim.biogas.cov_max","grandeza":"Carga orgânica volumétrica máxima por regime","valor_padrao":{"psicrofilico":1.0,"mesofilico":3.0,"termofilico":5.0,"ambiente":1.0},"unidade":"kg SV/(m³·dia)","opcoes":[],"fonte":"faixas usuais de literatura para digestores rurais e de mistura completa [CONFERIR]","status":"conferir","nota":"Acima: aviso de sobrecarga (acidificação)."},{"id":"sim.biogas.trh_min_dias","grandeza":"Tempo de retenção hidráulica mínimo por regime (e TRH alvo padrão do dimensionamento)","valor_padrao":{"psicrofilico":40,"mesofilico":20,"termofilico":12,"ambiente":40},"unidade":"dias","opcoes":[],"fonte":"faixas usuais de literatura [CONFERIR]","status":"conferir","nota":"Abaixo: aviso de TRH curto (lavagem das bactérias)."},{"id":"sim.biogas.temperaturas","grandeza":"Temperatura de operação por regime aquecido","valor_padrao":{"psicrofilico":20,"mesofilico":37,"termofilico":55},"unidade":"°C","opcoes":[],"fonte":"faixas clássicas de digestão anaeróbia [CONFERIR]","status":"conferir","nota":"Sem aquecimento ('ambiente'): temperatura média mensal do local da instalação, nunca um padrão."},{"id":"sim.biogas.t_min_c","grandeza":"Temperatura abaixo da qual a produção cai muito (aviso)","valor_padrao":15,"unidade":"°C","opcoes":[],"fonte":"literatura de digestores rurais [CONFERIR]","status":"conferir","nota":""},{"id":"sim.biogas.ganho_enterrado_c","grandeza":"Ganho de temperatura do digestor enterrado ou em estufa sobre a média do ar","valor_padrao":2.0,"unidade":"°C","opcoes":[],"fonte":"premissa Physis [CONFERIR com medição]","status":"conferir","nota":"Medir a temperatura do digestor (sensor) troca esta premissa."},{"id":"sim.biogas.tipos_digestor","grandeza":"Tipos de digestor e modelo de reator usado na cinética","valor_padrao":{"tubular":{"nome":"Tubular (manga plástica)","modelo":"pistonado"},"lagoa_coberta":{"nome":"Lagoa coberta","modelo":"mistura"},"indiano":{"nome":"Indiano (gasômetro flutuante)","modelo":"mistura"},"chines":{"nome":"Chinês (cúpula fixa)","modelo":"mistura"},"mistura_completa":{"nome":"Mistura completa (CSTR)","modelo":"mistura"}},"unidade":"","opcoes":[],"fonte":"classificação usual de biodigestores rurais [CONFERIR]","status":"conferir","nota":""},{"id":"sim.biogas.folga_volume","grandeza":"Folga do volume total sobre o volume útil (gás e borda)","valor_padrao":1.25,"unidade":"adimensional","opcoes":[],"fonte":"premissa Physis (mesma folga do biodigestor da Economia circular: × 1,25)","status":"conferir","nota":""},{"id":"sim.biogas.eta_eletrica","grandeza":"Rendimento elétrico do gerador a biogás","valor_padrao":0.3,"unidade":"adimensional (0 a 1)","opcoes":[],"fonte":"ordem de grandeza de motogeradores pequenos [CONFERIR com o fabricante]","status":"conferir","nota":""},{"id":"sim.biogas.eta_termica","grandeza":"Rendimento do queimador/caldeira para calor útil (Secador, AVAC, água quente)","valor_padrao":0.75,"unidade":"adimensional (0 a 1)","opcoes":[],"fonte":"ordem de grandeza [CONFERIR com o fabricante]","status":"conferir","nota":""},{"id":"sim.biogas.queimador_m3_h","grandeza":"Consumo de um queimador de fogão doméstico a biogás","valor_padrao":0.35,"unidade":"m³/h","opcoes":[],"fonte":"ordem de grandeza de literatura de biodigestores domésticos [CONFERIR]","status":"conferir","nota":"Dá as horas de cozinha por dia."},{"id":"sim.biogas.horas_gerador","grandeza":"Horas de funcionamento do gerador por dia","valor_padrao":24,"unidade":"h/dia","opcoes":[],"fonte":"premissa Physis","status":"conferir","nota":"Gerador que só roda no horário de ponta tem potência maior para a mesma energia."},{"id":"sim.biogas.vazamento","grandeza":"Fração do metano perdida em vazamentos do sistema","valor_padrao":0.05,"unidade":"adimensional (0 a 1)","opcoes":[],"fonte":"ordem de grandeza de literatura e de metodologias de crédito [CONFERIR]","status":"conferir","nota":"Desconta das emissões evitadas."},{"id":"sim.biogas.densidade_biogas","grandeza":"Densidade do biogás","valor_padrao":1.15,"unidade":"kg/m³","opcoes":[],"fonte":"ordem de grandeza para 55–65 % de CH₄ [CONFERIR]","status":"conferir","nota":"Usada no volume do digestato."},{"id":"sim.biogas.incerteza","grandeza":"Coeficientes de variação das entradas do biogás (faixa de Monte Carlo)","valor_padrao":{"kg_cv":0.1,"st_cv":0.1,"sv_cv":0.05,"bmp_cv":0.2,"ch4_cv":0.05},"unidade":"adimensional","opcoes":[],"fonte":"premissa Physis [CONFERIR]","status":"conferir","nota":"Distribuição normal em cada entrada."},{"id":"biogas.pci","grandeza":"Energia do biogás","valor_padrao":6,"unidade":"kWh/m³","opcoes":[],"fonte":"premissa Physis (mesmo valor do Planejador, physisBiogas, e da aba Carbono); conferir com o teor de metano medido","status":"conferir","nota":"Usado para dizer quanto GLP o biogás substitui (emissões evitadas)."},{"id":"glp.pci","grandeza":"Energia do GLP","valor_padrao":12.8,"unidade":"kWh/kg","opcoes":[],"fonte":"premissa Physis (valor da aba Carbono); conferir com a ficha do combustível","status":"conferir","nota":"Biogás evitado = m³ × biogas.pci ÷ glp.pci × fator do GLP (combustivel.glp). Regra única: aba Carbono e SustainKit."},{"id":"eletrica.fator_potencia_padrao","grandeza":"Fator de potência adotado quando não há medição","valor_padrao":0.92,"unidade":"adimensional (0 a 1)","opcoes":[],"fonte":"premissa Physis para estimativa, igual à referência regulatória abaixo [CONFERIR]; vale a medição (V6, medidor) quando houver","status":"conferir","nota":"Usado para dar Q (kvar) e S (kVA) a partir de P (kW) em todos os módulos de energia."},{"id":"eletrica.fator_potencia_minimo","grandeza":"Fator de potência de referência (abaixo dele, aviso de FP baixo)","valor_padrao":0.92,"unidade":"adimensional (0 a 1)","opcoes":[],"fonte":"REN ANEEL 1.000/2021 (fator de potência de referência para cobrança de reativo) [CONFERIR NA NORMA]","status":"conferir","nota":"Só aviso: FP abaixo do valor de referência costuma gerar cobrança de energia reativa."}]};
/*SIM-PREMISSAS-FIM*/
var AVISO = "Pré-dimensionamento para revisão do engenheiro responsável. Não aprova projeto, não substitui norma nem ensaio. Premissas marcadas 'conferir' precisam ser conferidas antes de uso em proposta.";
var MARCADOR = "[MARCADOR]";
var POR_ID = {};
(PREM.premissas || []).forEach(function (p) { POR_ID[p.id] = p; });
var CFG = { materiais: null, fatores: null };

function FaltaDado(msg) { var e = new Error(msg); e.faltaDado = true; return e; }
function info(id) {
  if (POR_ID[id]) return POR_ID[id];
  var PC = global.PhysisCalc; return PC && PC.info ? PC.info(id) : null;
}
function premissa(id, padrao) {
  var PC = global.PhysisCalc;
  if (!POR_ID[id] && PC && PC.premissa) { var v = PC.premissa(id); return v == null ? (padrao === undefined ? null : padrao) : v; }
  var p = POR_ID[id]; if (!p) return padrao === undefined ? null : padrao;
  return p.valor_padrao;
}
function usada(id, valor) {
  var p = info(id) || {};
  return { id: id, valor: valor === undefined ? (p.valor_padrao === undefined ? null : p.valor_padrao) : valor, status: p.status || (info(id) ? "conferir" : "ausente"), fonte: p.fonte || MARCADOR };
}
function lerJsonScript(id) { try { var s = typeof document !== "undefined" ? document.getElementById(id) : null; return s ? JSON.parse(s.textContent) : null; } catch (e) { return null; } }
function baseMateriais() {
  if (CFG.materiais) return CFG.materiais;
  var b = lerJsonScript("base-materiais") || (global.SIMULACAO_CASOS && global.SIMULACAO_CASOS.materiais) || null;
  CFG.materiais = b || { materiais: [], composicoes: [] }; return CFG.materiais;
}
function material(mid) {
  var ms = baseMateriais().materiais || [];
  for (var i = 0; i < ms.length; i++) if (ms[i].id === mid) return ms[i];
  throw FaltaDado(MARCADOR + " material '" + mid + "' não está na base sistema/physis-materiais.json");
}
function composicao(cid) {
  var cs = baseMateriais().composicoes || [];
  for (var i = 0; i < cs.length; i++) if (cs[i].id === cid) return cs[i];
  throw FaltaDado(MARCADOR + " composição '" + cid + "' não está na base");
}
function resultado(metodo, hipoteses, premissas, malha, limites, dados, avisos) {
  var r = { metodo: metodo, hipoteses: hipoteses.slice(), premissas_usadas: premissas.slice(), malha: malha === undefined ? null : malha,
    limites_validade: limites, aviso: AVISO, fase: 1, avisos: (avisos || []).slice() };
  for (var k in dados) if (Object.prototype.hasOwnProperty.call(dados, k)) r[k] = dados[k];
  return r;
}
function num(x, d) { return typeof x === "number" && isFinite(x) ? x : d; }
function nn(x) { return x !== undefined && x !== null; }

/* mulberry32: mesma sequência que comum.Rng no Python */
function Rng(semente) {
  var a = (semente == null ? 42 : semente) | 0;
  var f = function () {
    a = (a + 0x6D2B79F5) | 0;
    var t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  f.normal = function () { var u1 = f(), u2 = f(); if (u1 <= 0) u1 = 1e-300; return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2); };
  return f;
}
function tridiagonal(a, b, c, d) {
  var n = d.length, cp = new Array(n), dp = new Array(n), x = new Array(n), i;
  cp[0] = n > 1 ? c[0] / b[0] : 0; dp[0] = d[0] / b[0];
  for (i = 1; i < n; i++) { var m = b[i] - a[i] * cp[i - 1]; cp[i] = i < n - 1 ? c[i] / m : 0; dp[i] = (d[i] - a[i] * dp[i - 1]) / m; }
  x[n - 1] = dp[n - 1];
  for (i = n - 2; i >= 0; i--) x[i] = dp[i] - cp[i] * x[i + 1];
  return x;
}
function percentil(o, p) {
  var n = o.length; if (!n) return NaN;
  var h = (n - 1) * p / 100, i = Math.floor(h);
  if (i >= n - 1) return o[n - 1];
  return o[i] + (h - i) * (o[i + 1] - o[i]);
}
function zeros(n) { var a = new Array(n); for (var i = 0; i < n; i++) a[i] = 0; return a; }
function matriz(n, m) { var a = new Array(n); for (var i = 0; i < n; i++) a[i] = zeros(m); return a; }
function soma(a) { var s = 0; for (var i = 0; i < a.length; i++) s += a[i]; return s; }

/* ══════════════ 1. CALOR ══════════════ */
var SIGMA = 5.670374419e-8;
function resistencias(tipo) {
  var rs = premissa("sim.termica.resistencias_superficiais") || {}, v = rs[tipo || "parede"] || rs.parede;
  if (!v) throw FaltaDado(MARCADOR + " resistências superficiais (premissa sim.termica.resistencias_superficiais)");
  return [v.rsi, v.rse];
}
function camada(c) {
  if (nn(c.resistencia)) return { nome: c.nome || "câmara de ar", espessura: num(c.espessura, 0), R: c.resistencia, k: null, rho: null, cp: null, carbono: null, ar: true };
  var e = c.espessura, k, rho, cp, ci, nome;
  if (c.material) { var m = material(c.material); k = m.condutividade; rho = m.densidade; cp = m.calor_especifico; ci = (m.carbono_incorporado || {}).valor; nome = m.nome || c.material; }
  else { k = c.condutividade; rho = c.densidade; cp = c.calor_especifico; ci = c.carbono; nome = c.nome || "camada"; }
  if (!nn(k)) throw FaltaDado(MARCADOR + " condutividade de '" + nome + "' (a base não tem; digite do ensaio ou da folha de dados)");
  return { nome: nome, espessura: e, R: e / k, k: k, rho: nn(rho) ? rho : null, cp: nn(cp) ? cp : null, carbono: nn(ci) ? ci : null, ar: false, material: c.material || null };
}
function uValor(camadas, tipo, rsi, rse, ti, te) {
  tipo = tipo || "parede"; var rs = resistencias(tipo); rsi = nn(rsi) ? rsi : rs[0]; rse = nn(rse) ? rse : rs[1];
  var cs = camadas.map(camada), rt = rsi, i;
  for (i = 0; i < cs.length; i++) rt += cs[i].R;
  rt += rse;
  var u = 1 / rt, ct = 0, massa = 0, semCt = [], carbOk = true, carb = 0;
  cs.forEach(function (c) { if (!c.ar && c.rho && c.cp) ct += c.espessura * c.rho * c.cp / 1000; });
  cs.forEach(function (c) { if (!c.ar && !(c.rho && c.cp)) semCt.push(c.nome); });
  cs.forEach(function (c) { if (!c.ar && c.rho) massa += c.espessura * c.rho; });
  cs.forEach(function (c) { if (!(c.ar || (c.carbono != null && c.rho))) carbOk = false; });
  if (carbOk) cs.forEach(function (c) { if (!c.ar) carb += c.espessura * c.rho * c.carbono; }); else carb = null;
  var temps = null;
  if (nn(ti) && nn(te)) {
    var q = u * (ti - te), t = ti - q * rsi; temps = [t];
    for (i = cs.length - 1; i >= 0; i--) { t -= q * cs[i].R; temps.push(t); }
    temps.reverse();
  }
  var av = semCt.length ? [MARCADOR + " densidade ou calor específico de: " + semCt.join(", ") + " (capacidade térmica incompleta)"] : [];
  if (carb == null) av.push(MARCADOR + " carbono incorporado de alguma camada: total por m² não calculado");
  return resultado("Condução 1D em regime permanente, camadas homogêneas em série (método da ABNT NBR 15220-2, redação própria)",
    ["fluxo perpendicular à parede", "camadas homogêneas, sem pontes térmicas", "propriedades da base de materiais"],
    [usada("sim.termica.resistencias_superficiais", { rsi: rsi, rse: rse })], { camadas: cs.length },
    "Válido para camadas contínuas; pontes térmicas (montantes, pilares, juntas) pedem a placa_2d. Umidade muda a condutividade da terra e das fibras.",
    { u: u, r_total: rt, ct_kj_m2k: ct, massa_kg_m2: massa, carbono_kgco2e_m2: carb, temperaturas_interfaces: temps,
      camadas: cs.map(function (c) { return { nome: c.nome, espessura: c.espessura, R: c.R, k: c.k }; }) }, av);
}
function uComposicao(cid) {
  var c = composicao(cid), tipo = c.tipo === "parede" ? "parede" : "cobertura_verao";
  if (!c.camadas || !c.camadas.length) { var tab = c.tabelado || {};
    return resultado("Valor tabelado da base (composição sem camadas)", ["valor de tabela"], [], null, "Tabelado: não recalculado.", { u: tab.u, ct_kj_m2k: tab.ct, id: cid, fonte_tabela: tab.fonte }); }
  var r = uValor(c.camadas, tipo); r.id = cid; r.u_base = (c.calculo || {}).u; return r;
}
function perdaEnvoltoria(itens, ti, te) {
  var linhas = [], tot = 0;
  itens.forEach(function (it) {
    var u = nn(it.u) ? it.u : it.composicao ? uComposicao(it.composicao).u : uValor(it.camadas, it.tipo || "parede").u;
    var w = u * it.area * (ti - te); tot += w; linhas.push({ nome: it.nome || "", u: u, area: it.area, w: w });
  });
  return resultado("Σ U·A·ΔT (condução em regime permanente)", ["ΔT constante", "sem radiação solar (use sol-ar)"], [usada("sim.termica.resistencias_superficiais")],
    { itens: itens.length }, "Carga de pico simplificada; a carga térmica completa é a da aba AVAC (NBR 16401-1).", { itens: linhas, w_total: tot });
}
function hConveccaoVento(v) { var c = premissa("sim.termica.h_conv_vento") || {}; if (!nn(c.a) || !nn(c.b)) throw FaltaDado(MARCADOR + " premissa sim.termica.h_conv_vento"); return c.a + c.b * v; }
function hRadiacao(eps, t1, t2) { eps = nn(eps) ? eps : premissa("sim.termica.emissividade"); var a = t1 + 273.15, b = t2 + 273.15; return eps * SIGMA * (a * a + b * b) * (a + b); }
function solAr(te, alfa, I, he) { return te + alfa * I / he; }
function func(spec, padrao) {
  if (!nn(spec)) return function () { return padrao || 0; };
  if (typeof spec === "number") return function () { return spec; };
  if (nn(spec.constante)) return function () { return spec.constante; };
  if (spec.senoide) { var s = spec.senoide, m = s.media, a = s.amplitude, per = (nn(s.periodo_h) ? s.periodo_h : 24) * 3600, f = (s.fase_h || 0) * 3600;
    return function (t) { return m + a * Math.sin(2 * Math.PI * (t - f) / per); }; }
  if (spec.serie) { var ser = spec.serie, ps = spec.passo_s; return function (t) { return ser[Math.min(ser.length - 1, Math.floor(t / ps + 1e-9))]; }; }
  throw new Error("temperatura: use número, {constante}, {senoide} ou {serie, passo_s}");
}
function celulas1d(camadas, dxMax) {
  var cel = [];
  camadas.forEach(function (c) {
    var cc = camada(c);
    if (cc.ar) throw FaltaDado("câmara de ar no transiente: troque por camada equivalente (k = e/R, ρ do ar) [MARCADOR]");
    if (!(cc.rho && cc.cp)) throw FaltaDado(MARCADOR + " densidade e calor específico de '" + cc.nome + "' (transiente precisa)");
    var n = Math.max(1, Math.ceil(cc.espessura / dxMax - 1e-9));
    for (var i = 0; i < n; i++) cel.push([cc.espessura / n, cc.k, cc.rho * cc.cp]);
  });
  return cel;
}
function transiente1d(p) {
  var tipo = p.tipo || "parede", rs = resistencias(tipo), rsi = rs[0], rse = rs[1];
  var cel = celulas1d(p.camadas, num(p.dx_max, 0.01)), n = cel.length, i, j;
  var dt = num(p.dt, 300), theta = num(p.theta, 1), dur = num(p.duracao_h, 72) * 3600;
  var teF = func(p.te, 0), tiF = func(p.ti, 0);
  var ce = p.contorno_ext || { tipo: "conveccao", h: 1 / rse }, ci = p.contorno_int || { tipo: "conveccao", h: 1 / rsi };
  var gb = function (c, dxk) { return c.tipo === "temperatura" ? 1 / dxk : 1 / (dxk + 1 / c.h); };
  var g = []; for (i = 0; i < n - 1; i++) g.push(1 / (cel[i][0] / (2 * cel[i][1]) + cel[i + 1][0] / (2 * cel[i + 1][1])));
  var ge = gb(ce, cel[0][0] / (2 * cel[0][1])), gi = gb(ci, cel[n - 1][0] / (2 * cel[n - 1][1]));
  var cap = cel.map(function (c) { return c[0] * c[2]; }), gl = [ge].concat(g), gr = g.concat([gi]), avisos = [], nsub = 1;
  if (theta < 0.5) {
    var dtc = Infinity; for (i = 0; i < n; i++) dtc = Math.min(dtc, cap[i] / ((1 - theta) * (gl[i] + gr[i])));
    if (dt > 0.9 * dtc) { nsub = Math.ceil(dt / (0.9 * dtc)); avisos.push("passo explícito instável: cada passo foi dividido em " + nsub + " (limite " + dtc.toFixed(1) + " s)"); }
  }
  var h = dt / nsub, t0 = nn(p.t0) ? p.t0 : teF(0), T = Array.isArray(t0) ? t0.slice() : zeros(n).map(function () { return t0; });
  if (T.length !== n) throw new Error("t0 com " + T.length + " valores; a malha tem " + n + " células");
  var passos = Math.round(dur / dt), cada = Math.max(1, Math.round(num(p.saida_s, 3600) / dt));
  var sInv = 1 / ge; for (i = 0; i < g.length; i++) sInv += 1 / g[i]; sInv += 1 / gi; var U = 1 / sInv;
  var qInt = function (T, t) { return gi * (T[n - 1] - tiF(t)); };
  var a = zeros(n), b = zeros(n), c = zeros(n), d = zeros(n), t = 0, serie = [], todos = [];
  serie.push({ t_h: 0, te: teF(0), ti: tiF(0), q_int: qInt(T, 0), t_meio: T[Math.floor(n / 2)] });
  for (var k = 1; k <= passos; k++) {
    for (var s = 0; s < nsub; s++) {
      var t1 = t + h, e0 = teF(t), e1 = teF(t1), i0 = tiF(t), i1 = tiF(t1);
      for (j = 0; j < n; j++) {
        var left0 = j === 0 ? e0 : T[j - 1], right0 = j === n - 1 ? i0 : T[j + 1];
        var expl = gl[j] * (left0 - T[j]) + gr[j] * (right0 - T[j]);
        a[j] = j > 0 ? -theta * gl[j] : 0; c[j] = j < n - 1 ? -theta * gr[j] : 0;
        b[j] = cap[j] / h + theta * (gl[j] + gr[j]);
        d[j] = cap[j] / h * T[j] + (1 - theta) * expl;
        if (j === 0) d[j] += theta * gl[j] * e1;
        if (j === n - 1) d[j] += theta * gr[j] * i1;
      }
      if (theta > 0) T = tridiagonal(a, b, c, d); else { var Tn = []; for (j = 0; j < n; j++) Tn.push(d[j] / b[j]); T = Tn; }
      t = t1;
    }
    todos.push([t, teF(t), qInt(T, t)]);
    if (k % cada === 0) serie.push({ t_h: t / 3600, te: teF(t), ti: tiF(t), q_int: qInt(T, t), t_meio: T[Math.floor(n / 2)] });
  }
  var atraso = null, amort = null, sen = p.te && typeof p.te === "object" ? p.te.senoide : null;
  if (sen) {
    var per = num(sen.periodo_h, 24) * 3600, ult = todos.filter(function (x) { return x[0] > dur - per + 1e-9; });
    if (dur >= 2 * per && ult.length) {
      var tq = ult[0], tt = ult[0], qmx = -Infinity, qmn = Infinity;
      ult.forEach(function (x) { if (x[2] > tq[2]) tq = x; if (x[1] > tt[1]) tt = x; if (x[2] > qmx) qmx = x[2]; if (x[2] < qmn) qmn = x[2]; });
      atraso = (((tq[0] - tt[0]) % per) + per) % per / 3600;
      amort = sen.amplitude ? (qmx - qmn) / 2 / (U * sen.amplitude) : null;
    } else avisos.push("duração menor que 2 períodos: atraso e amortecimento não calculados");
  }
  var xc = [], x = 0; cel.forEach(function (cc) { xc.push(x + cc[0] / 2); x += cc[0]; });
  var nomeT = theta === 1 ? "implícito" : theta === 0 ? "explícito" : theta === 0.5 ? "Crank-Nicolson" : "θ";
  return resultado("Diferenças finitas 1D (volumes finitos), método θ = " + theta + " (" + nomeT + ")",
    ["propriedades constantes", "sem umidade nem mudança de fase", "contato perfeito entre camadas"],
    [usada("sim.termica.resistencias_superficiais", { rsi: rsi, rse: rse })], { celulas: n, dt_s: dt, subpassos: nsub, passos: passos },
    "Atraso e amortecimento valem para regime periódico (vários dias simulados). Terra crua e fibras mudam com a umidade.",
    { serie: serie, perfil_final: T, x_celulas: xc, u: U, atraso_h: atraso, amortecimento: amort }, avisos);
}
var LADOS = [[-1, 0, "topo"], [1, 0, "base"], [0, -1, "esquerda"], [0, 1, "direita"]];
function placa2d(p) {
  var nx = p.nx, ny = p.ny, dx = p.dx, dy = p.dy, N = nx * ny, s, i, j;
  var K = typeof p.k === "number" ? zeros(N).map(function () { return p.k; }) : p.k.slice();
  var M = p.mascara || zeros(N).map(function () { return 1; }), cont = p.contornos || {}, vazio = p.vazio, fixos = {};
  (p.fixos || []).forEach(function (f) { fixos[f[0]] = f[1]; });
  var viz = [], bnd = [];
  for (s = 0; s < N; s++) { viz.push([]); bnd.push([]); }
  var gb = function (c, meia) { return c.tipo === "temperatura" ? 1 / meia : 1 / (meia + 1 / c.h); };
  for (i = 0; i < ny; i++) for (j = 0; j < nx; j++) {
    s = i * nx + j; if (!M[s]) continue;
    for (var l = 0; l < 4; l++) {
      var di = LADOS[l][0], dj = LADOS[l][1], lado = LADOS[l][2], horiz = dj !== 0;
      var meia = (horiz ? dx : dy) / (2 * K[s]), area = horiz ? dy : dx, ii = i + di, jj = j + dj;
      if (ii >= 0 && ii < ny && jj >= 0 && jj < nx) {
        var o = ii * nx + jj;
        if (M[o]) viz[s].push([o, area / (meia + (horiz ? dx : dy) / (2 * K[o]))]);
        else if (vazio) bnd[s].push([area * gb(vazio, meia), vazio.T, "vazio"]);
      } else { var c = cont[lado]; if (c) bnd[s].push([area * gb(c, meia), c.T, lado]); }
    }
  }
  var tr = p.transiente, T = zeros(N), avisos = [], iters = 0, metodo, malha, v, q;
  if (tr) {
    var RC = typeof tr.rho_cp === "number" ? zeros(N).map(function () { return tr.rho_cp; }) : tr.rho_cp.slice();
    var t0 = nn(tr.t0) ? tr.t0 : 0; T = typeof t0 === "number" ? zeros(N).map(function () { return t0; }) : t0.slice();
    var cap = RC.map(function (r) { return r * dx * dy; }), lim = Infinity, achou = false;
    for (s = 0; s < N; s++) if (M[s] && (viz[s].length || bnd[s].length)) { var sg = 0; for (q = 0; q < viz[s].length; q++) sg += viz[s][q][1]; for (q = 0; q < bnd[s].length; q++) sg += bnd[s][q][0]; lim = Math.min(lim, cap[s] / sg); achou = true; }
    if (!achou) lim = 1;
    var dt = tr.dt || 0.9 * lim;
    if (dt > 0.9 * lim) { avisos.push("dt reduzido para " + (0.9 * lim).toPrecision(3) + " s (estabilidade explícita)"); dt = 0.9 * lim; }
    var passos = Math.ceil(tr.duracao_s / dt);
    for (v in fixos) T[+v] = fixos[v];
    for (var k = 0; k < passos; k++) {
      var Tn = T.slice();
      for (s = 0; s < N; s++) {
        if (!M[s] || nn(fixos[s])) continue;
        var fl = 0; for (q = 0; q < viz[s].length; q++) fl += viz[s][q][1] * (T[viz[s][q][0]] - T[s]);
        for (q = 0; q < bnd[s].length; q++) fl += bnd[s][q][0] * (bnd[s][q][1] - T[s]);
        Tn[s] = T[s] + dt * fl / cap[s];
      }
      T = Tn;
    }
    iters = passos; metodo = "Diferenças finitas 2D, transiente explícito (Euler para frente)";
    malha = { nx: nx, ny: ny, dx: dx, dy: dy, dt_s: dt, passos: passos };
  } else {
    var om = num(p.omega, 1.6), tol = num(p.tol, 1e-6), mx = num(p.max_iter, 20000), tb = [];
    Object.keys(cont).forEach(function (kk) { if (cont[kk]) tb.push(cont[kk].T); });
    var ini = tb.length ? soma(tb) / tb.length : 0; T = zeros(N).map(function () { return ini; });
    for (v in fixos) T[+v] = fixos[v];
    var conv = false;
    for (var it = 1; it <= mx; it++) {
      var dmax = 0;
      for (s = 0; s < N; s++) {
        if (!M[s] || nn(fixos[s])) continue;
        var nu = 0, de = 0;
        for (q = 0; q < viz[s].length; q++) { nu += viz[s][q][1] * T[viz[s][q][0]]; de += viz[s][q][1]; }
        for (q = 0; q < bnd[s].length; q++) { nu += bnd[s][q][0] * bnd[s][q][1]; de += bnd[s][q][0]; }
        if (de === 0) continue;
        var novo = (1 - om) * T[s] + om * nu / de, dv = Math.abs(novo - T[s]);
        if (dv > dmax) dmax = dv;
        T[s] = novo;
      }
      iters = it;
      if (dmax < tol) { conv = true; break; }
    }
    if (!conv) avisos.push("SOR não convergiu no máximo de iterações");
    metodo = "Diferenças finitas 2D (volumes finitos), regime permanente por SOR";
    malha = { nx: nx, ny: ny, dx: dx, dy: dy, iteracoes: iters, omega: om, tol: tol };
  }
  var fluxos = {}, vals = [];
  for (s = 0; s < N; s++) if (M[s]) { vals.push(T[s]); bnd[s].forEach(function (b) { fluxos[b[2]] = (fluxos[b[2]] || 0) + b[0] * (T[s] - b[1]); }); }
  return resultado(metodo, ["condução 2D, propriedades constantes por célula", "profundidade unitária (1 m)", "contato perfeito entre células"], [], malha,
    "Malha grossa erra perto de cantos e de materiais muito diferentes: refine (dx menor) e compare. Peça impressa: preenchimento (infill) entra como k equivalente da célula [CONFERIR com ensaio].",
    { T: T, t_min: vals.length ? Math.min.apply(null, vals) : null, t_max: vals.length ? Math.max.apply(null, vals) : null, fluxos_w_por_m: fluxos }, avisos);
}
function placaAnalitica(x, y, a, b, tTopo, termos) {
  termos = termos || 201; var s = 0;
  for (var n = 1; n <= termos; n += 2) s += 4 * tTopo / (n * Math.PI) * Math.sin(n * Math.PI * x / a) * Math.sinh(n * Math.PI * y / a) / Math.sinh(n * Math.PI * b / a);
  return s;
}
function mascaraDeSegmentos(seg, x0, y0, nx, ny, dx, dy) {
  var M = zeros(nx * ny);
  for (var i = 0; i < ny; i++) {
    var yc = y0 + (ny - i - 0.5) * dy, xs = [];
    seg.forEach(function (sg) { var A = sg[0], B = sg[1]; if ((A[1] > yc) !== (B[1] > yc)) xs.push(A[0] + (yc - A[1]) * (B[0] - A[0]) / (B[1] - A[1])); });
    for (var j = 0; j < nx; j++) { var xc = x0 + (j + 0.5) * dx, cnt = 0; for (var q = 0; q < xs.length; q++) if (xs[q] > xc) cnt++; M[i * nx + j] = cnt % 2; }
  }
  return M;
}
function poligonosParaSegmentos(pols) { var s = []; pols.forEach(function (p) { for (var k = 0; k < p.length; k++) s.push([p[k], p[(k + 1) % p.length]]); }); return s; }

/* ══════════════ 2. ESTRUTURA ══════════════ */
var G_PADRAO = 9.81;
function secao(s) {
  var t = s.tipo, i;
  if (t === "retangulo") { var b = s.b, h = s.h, a = Math.max(b, h), c = Math.min(b, h), j = a * Math.pow(c, 3) * (1 / 3 - 0.21 * (c / a) * (1 - Math.pow(c, 4) / (12 * Math.pow(a, 4))));
    return { A: b * h, Iz: b * Math.pow(h, 3) / 12, Iy: h * Math.pow(b, 3) / 12, J: j, cy: h / 2, cz: b / 2 }; }
  if (t === "circular") { var d = s.d; i = Math.PI * Math.pow(d, 4) / 64; return { A: Math.PI * d * d / 4, Iz: i, Iy: i, J: 2 * i, cy: d / 2, cz: d / 2 }; }
  if (t === "tubo") { var D = s.d, e = s.t, di = D - 2 * e; i = Math.PI * (Math.pow(D, 4) - Math.pow(di, 4)) / 64; return { A: Math.PI * (D * D - di * di) / 4, Iz: i, Iy: i, J: 2 * i, cy: D / 2, cz: D / 2 }; }
  var o = { A: s.A, Iz: nn(s.Iz) ? s.Iz : nn(s.I) ? s.I : 0 }; o.Iy = nn(s.Iy) ? s.Iy : o.Iz; o.J = nn(s.J) ? s.J : o.Iz + o.Iy;
  o.cy = nn(s.cy) ? s.cy : nn(s.c) ? s.c : 0; o.cz = nn(s.cz) ? s.cz : o.cy; return o;
}
function materialEstrutural(mid) { var tab = premissa("sim.estrutura.materiais") || {}; return mid && tab[mid] ? JSON.parse(JSON.stringify(tab[mid])) : {}; }
function resolverBanda(A, b) {
  var n = b.length, bw = 0, i, j, k, c;
  for (i = 0; i < n; i++) { var row = A[i]; for (j = n - 1; j > i; j--) if (row[j] !== 0) { if (j - i > bw) bw = j - i; break; } }
  for (c = 0; c < n; c++) {
    var piv = A[c][c];
    if (!(Math.abs(piv) >= 1e-300)) throw FaltaDado("estrutura instável: faltam apoios ou ligações (pivô nulo)");
    var fim = Math.min(n, c + bw + 1), Ac = A[c];
    for (var r = c + 1; r < fim; r++) { var Ar = A[r], f = Ar[c] / piv; if (f !== 0) { for (k = c; k < fim; k++) Ar[k] -= f * Ac[k]; b[r] -= f * b[c]; } }
  }
  var x = zeros(n);
  for (i = n - 1; i >= 0; i--) { var s = b[i], Ai = A[i], lim = Math.min(n, i + bw + 1); for (k = i + 1; k < lim; k++) s -= Ai[k] * x[k]; x[i] = s / Ai[i]; }
  return x;
}
function rot(dim, xi, xj, ref) {
  var d = [], k; for (k = 0; k < dim; k++) d.push(xj[k] - xi[k]);
  var L = 0; for (k = 0; k < dim; k++) L += d[k] * d[k]; L = Math.sqrt(L);
  if (!(L > 0)) throw FaltaDado("elemento de comprimento zero");
  if (dim === 2) { var c = d[0] / L, s = d[1] / L; return [L, [[c, s, 0], [-s, c, 0], [0, 0, 1]]]; }
  var ex = d.map(function (v) { return v / L; }), v = ref ? ref.slice() : [0, 0, 1];
  var proj = function (v) { var dot = 0; for (var q = 0; q < 3; q++) dot += v[q] * ex[q]; return [v[0] - dot * ex[0], v[1] - dot * ex[1], v[2] - dot * ex[2]]; };
  var yv = proj(v), ny = Math.sqrt(yv[0] * yv[0] + yv[1] * yv[1] + yv[2] * yv[2]);
  if (ny < 1e-9) { yv = proj([0, 1, 0]); ny = Math.sqrt(yv[0] * yv[0] + yv[1] * yv[1] + yv[2] * yv[2]); }
  var ey = yv.map(function (a) { return a / ny; });
  var ez = [ex[1] * ey[2] - ex[2] * ey[1], ex[2] * ey[0] - ex[0] * ey[2], ex[0] * ey[1] - ex[1] * ey[0]];
  return [L, [ex, ey, ez]];
}
function kLocal(dim, tipo, E, G, sc, L) {
  var n = dim === 2 ? 6 : 12, k = matriz(n, n), nd = n / 2;
  var put = function (i, j, v) { k[i][j] += v; if (i !== j) k[j][i] += v; };
  var ea = E * sc.A / L; put(0, 0, ea); put(0, nd, -ea); put(nd, nd, ea);
  if (tipo === "barra") return k;
  var L2 = Math.pow(L, 2), L3 = Math.pow(L, 3);
  if (dim === 2) { var ei = E * sc.Iz;
    put(1, 1, 12 * ei / L3); put(1, 2, 6 * ei / L2); put(1, 4, -12 * ei / L3); put(1, 5, 6 * ei / L2);
    put(2, 2, 4 * ei / L); put(2, 4, -6 * ei / L2); put(2, 5, 2 * ei / L);
    put(4, 4, 12 * ei / L3); put(4, 5, -6 * ei / L2); put(5, 5, 4 * ei / L); return k; }
  var gj = G * sc.J / L; put(3, 3, gj); put(3, 9, -gj); put(9, 9, gj);
  var ez = E * sc.Iz;
  put(1, 1, 12 * ez / L3); put(1, 5, 6 * ez / L2); put(1, 7, -12 * ez / L3); put(1, 11, 6 * ez / L2);
  put(5, 5, 4 * ez / L); put(5, 7, -6 * ez / L2); put(5, 11, 2 * ez / L);
  put(7, 7, 12 * ez / L3); put(7, 11, -6 * ez / L2); put(11, 11, 4 * ez / L);
  var ey = E * sc.Iy;
  put(2, 2, 12 * ey / L3); put(2, 4, -6 * ey / L2); put(2, 8, -12 * ey / L3); put(2, 10, -6 * ey / L2);
  put(4, 4, 4 * ey / L); put(4, 8, 6 * ey / L2); put(4, 10, 2 * ey / L);
  put(8, 8, 12 * ey / L3); put(8, 10, 6 * ey / L2); put(10, 10, 4 * ey / L);
  return k;
}
function fFixo(dim, tipo, q, L) {
  var qx = q[0], qy = q[1], qz = dim === 3 ? q[2] : 0;
  if (dim === 2) return tipo === "barra" ? [qx * L / 2, qy * L / 2, 0, qx * L / 2, qy * L / 2, 0] : [qx * L / 2, qy * L / 2, qy * L * L / 12, qx * L / 2, qy * L / 2, -qy * L * L / 12];
  if (tipo === "barra") return [qx * L / 2, qy * L / 2, qz * L / 2, 0, 0, 0, qx * L / 2, qy * L / 2, qz * L / 2, 0, 0, 0];
  return [qx * L / 2, qy * L / 2, qz * L / 2, 0, -qz * L * L / 12, qy * L * L / 12, qx * L / 2, qy * L / 2, qz * L / 2, 0, qz * L * L / 12, -qy * L * L / 12];
}
function matT(R, nd) { var n = nd * 2, T = matriz(n, n); for (var b = 0; b < n / 3; b++) for (var i = 0; i < 3; i++) for (var j = 0; j < 3; j++) T[3 * b + i][3 * b + j] = R[i][j]; return T; }
function portico(p) {
  var dim = p.dim || 2, nd = dim === 2 ? 3 : 6, nos = p.nos, nnos = nos.length, ng = nnos * nd, K = matriz(ng, ng), F = zeros(ng), i, j, m, d;
  (p.cargas || []).forEach(function (c) { c.F.forEach(function (v, k) { F[c.no * nd + k] += v; }); });
  var els = [], pp = p.peso_proprio;
  p.elementos.forEach(function (e) {
    var mat = materialEstrutural(e.material), E = nn(e.E) ? e.E : mat.E_Pa;
    if (!nn(E)) throw FaltaDado(MARCADOR + " módulo de elasticidade E do elemento " + e.i + "-" + e.j + " (material '" + e.material + "')");
    var G = nn(e.G) ? e.G : (mat.G_Pa || E / 2.6), sc = secao(e.secao), tipo = e.tipo || "viga";
    var rr = rot(dim, nos[e.i], nos[e.j], e.ref), L = rr[0], R = rr[1], kl = kLocal(dim, tipo, E, G, sc, L);
    var q = (e.q || zeros(dim === 3 ? 3 : 2)).slice(); while (q.length < (dim === 3 ? 3 : 2)) q.push(0);
    if (pp) {
      var rho = nn(pp.rho) ? pp.rho : mat.densidade;
      if (!nn(rho)) throw FaltaDado(MARCADOR + " densidade para o peso próprio");
      var w = rho * num(pp.g, G_PADRAO) * sc.A, gv = dim === 2 ? [0, -w] : [0, 0, -w];
      for (var a = 0; a < q.length; a++) { var sa = 0; for (var bb = 0; bb < dim; bb++) sa += R[a][bb] * gv[bb]; q[a] += sa; }
    }
    var ff = fFixo(dim, tipo, q, L), T = matT(R, nd), dofs = [], n = 2 * nd;
    for (j = 0; j < nd; j++) dofs.push(e.i * nd + j); for (j = 0; j < nd; j++) dofs.push(e.j * nd + j);
    var kT = matriz(n, n);
    for (i = 0; i < n; i++) for (j = 0; j < n; j++) { var s1 = 0; for (m = 0; m < n; m++) s1 += kl[i][m] * T[m][j]; kT[i][j] = s1; }
    for (i = 0; i < n; i++) {
      var Fi = 0; for (m = 0; m < n; m++) Fi += T[m][i] * ff[m]; F[dofs[i]] += Fi;
      for (j = 0; j < n; j++) { var s2 = 0; for (m = 0; m < n; m++) s2 += T[m][i] * kT[m][j]; K[dofs[i]][dofs[j]] += s2; }
    }
    els.push({ e: e, L: L, R: R, T: T, k: kl, ff: ff, q: q, sc: sc, E: E, tipo: tipo, dofs: dofs, mat: mat });
  });
  var restr = zeros(ng).map(function () { return false; });
  (p.apoios || []).forEach(function (a) { a.restr.forEach(function (v, k) { if (v) restr[a.no * nd + k] = true; }); });
  var auto = []; for (d = 0; d < ng; d++) if (!restr[d] && K[d][d] === 0) { restr[d] = true; auto.push(d); }
  var livres = []; for (d = 0; d < ng; d++) if (!restr[d]) livres.push(d);
  var Kr = livres.map(function (a) { return livres.map(function (b) { return K[a][b]; }); }), Fr = livres.map(function (a) { return F[a]; });
  var ur = livres.length ? resolverBanda(Kr, Fr) : [], u = zeros(ng);
  livres.forEach(function (dd, k) { u[dd] = ur[k]; });
  var reac = [];
  for (d = 0; d < ng; d++) if (restr[d] && auto.indexOf(d) < 0) { var sr = 0; for (m = 0; m < ng; m++) sr += K[d][m] * u[m]; reac.push({ no: Math.floor(d / nd), gl: d % nd, valor: sr - F[d] }); }
  var resEl = els.map(function (el) {
    var n = 2 * nd, ug = el.dofs.map(function (dd) { return u[dd]; }), ul = [], f = [], ii, mm;
    for (ii = 0; ii < n; ii++) { var su = 0; for (mm = 0; mm < n; mm++) su += el.T[ii][mm] * ug[mm]; ul.push(su); }
    for (ii = 0; ii < n; ii++) { var sf = 0; for (mm = 0; mm < n; mm++) sf += el.k[ii][mm] * ul[mm]; f.push(sf - el.ff[ii]); }
    var L = el.L, q = el.q, sc = el.sc, pts = [], sig = 0, mmax = 0;
    for (var s = 0; s <= 10; s++) {
      var x = L * s / 10, N = -f[0] - q[0] * x;
      if (dim === 2) { var Mz = el.tipo !== "barra" ? -f[2] + f[1] * x + q[1] * x * x / 2 : 0; pts.push({ x: x, N: N, V: f[1] + q[1] * x, M: Mz }); }
      else { var Mz3 = 0, My3 = 0; if (el.tipo !== "barra") { Mz3 = -f[5] + f[1] * x + q[1] * x * x / 2; My3 = -f[4] - f[2] * x - q[2] * x * x / 2; }
        pts.push({ x: x, N: N, Vy: f[1] + q[1] * x, Vz: f[2] + q[2] * x, T: -f[3], My: My3, Mz: Mz3 }); }
    }
    pts.forEach(function (t, k) {
      var sv = dim === 2 ? Math.abs(t.N) / sc.A + (sc.Iz ? Math.abs(t.M) * sc.cy / sc.Iz : 0)
        : Math.abs(t.N) / sc.A + (sc.Iz ? Math.abs(t.Mz) * sc.cy / sc.Iz : 0) + (sc.Iy ? Math.abs(t.My) * sc.cz / sc.Iy : 0);
      var mv = dim === 2 ? Math.abs(t.M) : Math.sqrt(t.My * t.My + t.Mz * t.Mz);
      if (k === 0 || sv > sig) sig = sv; if (k === 0 || mv > mmax) mmax = mv;
    });
    return { i: el.e.i, j: el.e.j, tipo: el.tipo, L: L, N: -f[0], N_j: f[nd], M_max: mmax, sigma_max: sig, f_local: f, diagrama: pts,
      material: el.e.material || null, E: el.E, I_min: dim === 3 ? Math.min(sc.Iz, sc.Iy) : sc.Iz, A: sc.A };
  });
  var avisos = auto.length ? [auto.length + " giros sem rigidez (nós só de barras) foram travados automaticamente"] : [];
  var desl = []; for (i = 0; i < nnos; i++) desl.push(u.slice(i * nd, (i + 1) * nd));
  var dmax = 0; desl.forEach(function (dd) { var s = 0; for (var k = 0; k < dim; k++) s += dd[k] * dd[k]; s = Math.sqrt(s); if (s > dmax) dmax = s; });
  var temViga = els.some(function (e) { return e.tipo !== "barra"; });
  return resultado("Elementos finitos lineares, " + (temViga ? "pórtico" : "treliça") + " " + dim + "D (barra axial + viga de Euler-Bernoulli)",
    ["material elástico linear", "pequenos deslocamentos (1ª ordem)", "seções planas permanecem planas", "ligações ideais (rótula ou engaste)", "sem cisalhamento na flexão (Euler-Bernoulli)"],
    els.some(function (e) { return Object.keys(e.mat).length; }) ? [usada("sim.estrutura.materiais")] : [],
    { nos: nnos, elementos: els.length, graus_de_liberdade: ng, livres: livres.length },
    "Primeira ordem: não pega efeito P-Δ, flambagem local, ligações semirrígidas nem fadiga. Bambu e madeira variam muito por peça: use valores de ensaio. Confira a combinação de ações na norma do material.",
    { deslocamentos: desl, desl_max: dmax, reacoes: reac, elementos: resEl }, avisos);
}
function euler(E, I, L, apoio, K) {
  apoio = apoio || "biapoiada"; var kt = premissa("sim.estrutura.k_flambagem") || {};
  if (!nn(K)) K = kt[apoio]; if (!nn(K)) throw FaltaDado(MARCADOR + " coeficiente K de flambagem para '" + apoio + "'");
  return resultado("Flambagem elástica de Euler: Pcr = π²·E·I/(K·L)²", ["barra reta ideal, carga centrada", "regime elástico"], [usada("sim.estrutura.k_flambagem", K)], null,
    "Só barras esbeltas (flambagem elástica); barras curtas falham por esmagamento antes. Imperfeições reduzem a carga real: a norma do material dá a curva de projeto.",
    { pcr: Math.pow(Math.PI, 2) * E * I / Math.pow(K * L, 2), K: K, apoio: apoio });
}
function verificar(res, apoio) {
  var fs = premissa("sim.estrutura.fs_tensao"), fsb = premissa("sim.estrutura.fs_flambagem");
  var linhas = res.elementos.map(function (e) {
    var mat = materialEstrutural(e.material), fy = mat.fy_Pa, lin = { i: e.i, j: e.j, material: e.material, sigma_max: e.sigma_max };
    if (!nn(fy) || !nn(fs)) { lin.tensao = MARCADOR + " tensão admissível (fy do material ou FS)"; lin.util_tensao = null; }
    else lin.util_tensao = e.sigma_max / (fy / fs);
    var N = Math.min(e.N, e.N_j);
    if (N < 0 && e.I_min > 0 && nn(fsb)) { var pcr = euler(e.E, e.I_min, e.L, apoio || "biapoiada").pcr; lin.pcr = pcr; lin.util_flambagem = -N / (pcr / fsb); }
    var u2 = nn(lin.util_flambagem) ? lin.util_flambagem : 0; lin.ok = nn(lin.util_tensao) && lin.util_tensao <= 1 && u2 <= 1;
    return lin;
  });
  return resultado("Verificação por tensões admissíveis (σ ≤ fy/FS) e flambagem de Euler (|N| ≤ Pcr/FS)", ["cargas características (sem majorar)", "comprimento de flambagem = comprimento do elemento × K"],
    [usada("sim.estrutura.fs_tensao"), usada("sim.estrutura.fs_flambagem"), usada("sim.estrutura.materiais")], null,
    "Triagem. O dimensionamento final segue a norma do material (aço, madeira, bambu, alumínio).", { linhas: linhas, todos_ok: linhas.every(function (l) { return l.ok; }) });
}
function cargaVento(area, cf, v0, s1, s2, s3) {
  var pv = premissa("sim.vento.pressao_dinamica") || {}, pick = function (a, b) { return nn(a) ? a : nn(b) ? b : null; };
  var v = { v0: pick(v0, pv.v0), s1: pick(s1, pv.s1), s2: pick(s2, pv.s2), s3: pick(s3, pv.s3), cf: pick(cf, pv.cf), coef: pick(null, pv.coef_q) };
  var falt = Object.keys(v).filter(function (k) { return v[k] == null; });
  if (falt.length) throw FaltaDado(MARCADOR + " " + falt.join(", ") + " (pressão de vento: digite da norma, [CONFERIR NA NORMA])");
  var vk = v.v0 * v.s1 * v.s2 * v.s3, q = v.coef * vk * vk;
  return resultado("Pressão dinâmica do vento (método da ABNT NBR 6123, nomeado; valores digitados [CONFERIR NA NORMA])", ["vento estático equivalente", "coeficiente de força único para a peça"],
    [usada("sim.vento.pressao_dinamica", v)], null, "Sem efeitos dinâmicos (vórtices, ressonância). Fatores S1, S2, S3 e Cf vêm da norma.", { vk: vk, q_pa: q, forca_n: v.cf * q * area });
}
function empuxoRotor(D, v, rho, ct) {
  rho = nn(rho) ? rho : 1.225; ct = nn(ct) ? ct : premissa("sim.turbinas.ct_empuxo");
  if (!nn(ct)) throw FaltaDado(MARCADOR + " coeficiente de empuxo C_T");
  var a = Math.PI * D * D / 4;
  return resultado("Teoria do disco atuador: F = ½·ρ·A·v²·C_T", ["rotor como disco", "vento uniforme"], [usada("sim.turbinas.ct_empuxo", ct)], null,
    "Para a velocidade de sobrevivência use a força com o rotor parado e o arrasto da torre (fabricante).", { forca_n: 0.5 * rho * a * v * v * ct, area: a });
}
function malhaDeMascara(M, nx, ny, dx, dy, x0, y0) {
  x0 = x0 || 0; y0 = y0 || 0; var ids = {}, nos = [], tris = [], chaves = [];
  var no = function (i, j) { var k = i + "," + j; if (!(k in ids)) { ids[k] = nos.length; nos.push([x0 + j * dx, y0 + (ny - i) * dy]); chaves.push(k); } return ids[k]; };
  for (var i = 0; i < ny; i++) for (var j = 0; j < nx; j++) if (M[i * nx + j]) {
    var a = no(i + 1, j), b = no(i + 1, j + 1), c = no(i, j + 1), d = no(i, j); tris.push([a, b, c]); tris.push([a, c, d]); }
  return { nos: nos, tris: tris, id_canto: ids };
}
function cst(p) {
  var mat = materialEstrutural(p.material), E = nn(p.E) ? p.E : mat.E_Pa, nu = nn(p.nu) ? p.nu : mat.nu;
  if (!nn(E) || !nn(nu)) throw FaltaDado(MARCADOR + " E e ν do material da peça (ensaio da oficina)");
  var t = p.t, nos = p.nos, tris = p.tris, ng = 2 * nos.length, K = matriz(ng, ng), F = zeros(ng), c0 = E / (1 - nu * nu);
  var D = [[c0, c0 * nu, 0], [c0 * nu, c0, 0], [0, 0, c0 * (1 - nu) / 2]], Bs = [], i, j, m;
  tris.forEach(function (tr) {
    var x1 = nos[tr[0]][0], y1 = nos[tr[0]][1], x2 = nos[tr[1]][0], y2 = nos[tr[1]][1], x3 = nos[tr[2]][0], y3 = nos[tr[2]][1];
    var A2 = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1);
    if (!(A2 > 0)) throw FaltaDado("triângulo com área nula ou no sentido horário");
    var B = [[(y2 - y3) / A2, 0, (y3 - y1) / A2, 0, (y1 - y2) / A2, 0], [0, (x3 - x2) / A2, 0, (x1 - x3) / A2, 0, (x2 - x1) / A2],
      [(x3 - x2) / A2, (y2 - y3) / A2, (x1 - x3) / A2, (y3 - y1) / A2, (x2 - x1) / A2, (y1 - y2) / A2]];
    var DB = matriz(3, 6); for (i = 0; i < 3; i++) for (j = 0; j < 6; j++) { var s = 0; for (m = 0; m < 3; m++) s += D[i][m] * B[m][j]; DB[i][j] = s; }
    var dofs = [2 * tr[0], 2 * tr[0] + 1, 2 * tr[1], 2 * tr[1] + 1, 2 * tr[2], 2 * tr[2] + 1], f = t * A2 / 2;
    for (i = 0; i < 6; i++) for (j = 0; j < 6; j++) K[dofs[i]][dofs[j]] += f * (B[0][i] * DB[0][j] + B[1][i] * DB[1][j] + B[2][i] * DB[2][j]);
    Bs.push([B, dofs, A2 / 2]);
  });
  (p.cargas || []).forEach(function (c) { F[2 * c.no] += c.F[0]; F[2 * c.no + 1] += c.F[1]; });
  var restr = zeros(ng).map(function () { return false; });
  (p.apoios || []).forEach(function (a) { a.restr.forEach(function (v, k) { if (v) restr[2 * a.no + k] = true; }); });
  var livres = []; for (i = 0; i < ng; i++) if (!restr[i]) livres.push(i);
  var ur = resolverBanda(livres.map(function (a) { return livres.map(function (b) { return K[a][b]; }); }), livres.map(function (a) { return F[a]; })), u = zeros(ng);
  livres.forEach(function (d, k) { u[d] = ur[k]; });
  var tens = Bs.map(function (x) {
    var B = x[0], ue = x[1].map(function (d) { return u[d]; }), eps = [0, 0, 0], s = [0, 0, 0], ii, jj;
    for (ii = 0; ii < 3; ii++) { var se = 0; for (jj = 0; jj < 6; jj++) se += B[ii][jj] * ue[jj]; eps[ii] = se; }
    for (ii = 0; ii < 3; ii++) { var ss = 0; for (jj = 0; jj < 3; jj++) ss += D[ii][jj] * eps[jj]; s[ii] = ss; }
    var vm = Math.sqrt(s[0] * s[0] - s[0] * s[1] + s[1] * s[1] + 3 * s[2] * s[2]), en = 0.5 * t * x[2] * (s[0] * eps[0] + s[1] * eps[1] + s[2] * eps[2]);
    return { sx: s[0], sy: s[1], txy: s[2], von_mises: vm, energia: en, area: x[2] };
  });
  var reac = []; for (i = 0; i < ng; i++) if (restr[i]) { var sr = 0; for (m = 0; m < ng; m++) sr += K[i][m] * u[m]; reac.push({ no: Math.floor(i / 2), gl: i % 2, valor: sr - F[i] }); }
  var desl = nos.map(function (_, k) { return [u[2 * k], u[2 * k + 1]]; });
  var vmx = 0; tens.forEach(function (x) { if (x.von_mises > vmx) vmx = x.von_mises; });
  var dmx = 0; desl.forEach(function (d) { var h = Math.sqrt(d[0] * d[0] + d[1] * d[1]); if (h > dmx) dmx = h; });
  return resultado("Elementos finitos 2D, estado plano de tensões, triângulo de deformação constante (CST)", ["material elástico linear e isótropo", "pequenas deformações", "espessura constante t"],
    Object.keys(mat).length ? [usada("sim.estrutura.materiais")] : [], { nos: nos.length, triangulos: tris.length, graus_de_liberdade: ng },
    "CST é rígido demais em flexão com poucos elementos na altura: refine e compare. Peça impressa é anisotrópica (camadas): E e resistência entre camadas são menores [CONFERIR com ensaio].",
    { deslocamentos: desl, tensoes: tens, reacoes: reac, von_mises_max: vmx, desl_max: dmx });
}

/* ══════════════ 3. FLUIDOS (redes de tubos e dutos: as que já existem — vento.py/TURBINAS, AVAC, PhysisCalc.calhas) ══════════════ */
function ventilacaoNatural(p) {
  var cd = nn(p.cd) ? p.cd : premissa("sim.ventilacao.cd"), cps = premissa("sim.ventilacao.cp_vento") || {}, dcp = p.dcp;
  if (!nn(dcp) && nn(cps.barlavento) && nn(cps.sotavento)) dcp = cps.barlavento - cps.sotavento;
  if (!nn(cd) || !nn(dcp)) throw FaltaDado(MARCADOR + " coeficiente de descarga Cd ou ΔCp (premissas sim.ventilacao)");
  var a1 = p.a1, a2 = p.a2, ae = 1 / Math.sqrt(1 / Math.pow(a1, 2) + 1 / Math.pow(a2, 2)), ti = num(p.ti, 25), te = num(p.te, 25), tm = (ti + te) / 2 + 273.15;
  var qc = cd * ae * Math.sqrt(2 * 9.81 * num(p.h, 0) * Math.abs(ti - te) / tm), qv = cd * ae * num(p.v, 0) * Math.sqrt(Math.max(0, dcp)), q = Math.sqrt(qc * qc + qv * qv);
  return resultado("Ventilação natural: efeito chaminé e vento por orifício (coeficientes de premissa)", ["escoamento por orifício, ar incompressível", "temperatura uniforme dentro", "chaminé e vento somados em quadratura (aproximação)"],
    [usada("sim.ventilacao.cd", cd), usada("sim.ventilacao.cp_vento", { dcp: dcp })], null,
    "Ordem de grandeza para pré-dimensionar aberturas. Vento real varia com a direção e o entorno: ΔCp de túnel de vento ou de norma vale mais. Para o Secador, a vazão do coletor depende da insolação.",
    { area_efetiva: ae, q_chamine_m3s: qc, q_vento_m3s: qv, q_m3s: q, trocas_h: p.volume ? q * 3600 / p.volume : null, dcp: dcp, cd: cd });
}
var EX = [0, 1, 0, -1, 0, 1, -1, -1, 1], EY = [0, 0, 1, 0, -1, 1, 1, -1, -1], W = [4 / 9, 1 / 9, 1 / 9, 1 / 9, 1 / 9, 1 / 36, 1 / 36, 1 / 36, 1 / 36], OP = [0, 3, 4, 1, 2, 7, 8, 5, 6], ESP = [0, 1, 4, 3, 2, 8, 7, 6, 5];
function feq(k, rho, ux, uy) { var eu = EX[k] * ux + EY[k] * uy; return W[k] * rho * (1.0 + 3.0 * eu + 4.5 * eu * eu - 1.5 * (ux * ux + uy * uy)); }
function lbm(p) {
  var nx = p.nx, ny = p.ny, N = nx * ny, obs = p.obstaculo || zeros(N), u0 = num(p.u_entrada, 0.05), tau = num(p.tau, 0.6);
  if (!(tau > 0.5)) throw new Error("tau precisa ser maior que 0,5 (estabilidade)");
  var om = 1.0 / tau, modo = p.modo || "canal", passos = num(p.passos, 200), ini = p.u0_campo, f = [], k, s, x, y;
  for (k = 0; k < 9; k++) f.push(zeros(N));
  for (s = 0; s < N; s++) { var ux0 = obs[s] ? 0 : (ini ? ini[0][s] : (modo === "canal" ? u0 : 0)), uy0 = obs[s] ? 0 : (ini ? ini[1][s] : 0);
    for (k = 0; k < 9; k++) f[k][s] = feq(k, 1.0, ux0, uy0); }
  var massa0 = 0; for (k = 0; k < 9; k++) for (s = 0; s < N; s++) if (!obs[s]) massa0 += f[k][s];
  var rho = zeros(N).map(function () { return 1; }), UX = zeros(N), UY = zeros(N);
  for (var it = 0; it < passos; it++) {
    for (s = 0; s < N; s++) {
      if (obs[s]) continue;
      var r = 0, mx = 0, my = 0;
      for (k = 0; k < 9; k++) { var fk = f[k][s]; r += fk; mx += fk * EX[k]; my += fk * EY[k]; }
      var ux = mx / r, uy = my / r; rho[s] = r; UX[s] = ux; UY[s] = uy;
      for (k = 0; k < 9; k++) f[k][s] += om * (feq(k, r, ux, uy) - f[k][s]);
    }
    var g = []; for (k = 0; k < 9; k++) g.push(zeros(N));
    for (s = 0; s < N; s++) {
      if (obs[s]) continue;
      y = Math.floor(s / nx); x = s - y * nx;
      for (k = 0; k < 9; k++) {
        var xx = x + EX[k], yy = y + EY[k];
        if (modo === "periodico") { xx = ((xx % nx) + nx) % nx; yy = ((yy % ny) + ny) % ny; }
        else { if (yy < 0 || yy >= ny) { g[ESP[k]][s] += f[k][s]; continue; } if (xx < 0 || xx >= nx) continue; }
        var d = yy * nx + xx;
        if (obs[d]) g[OP[k]][s] += f[k][s]; else g[k][d] += f[k][s];
      }
    }
    f = g;
    if (modo === "canal") for (y = 0; y < ny; y++) {
      s = y * nx; if (!obs[s]) for (k = 0; k < 9; k++) f[k][s] = feq(k, 1.0, u0, 0.0);
      var s2 = y * nx + nx - 1, s1 = y * nx + nx - 2; if (!obs[s2]) for (k = 0; k < 9; k++) f[k][s2] = f[k][s1];
    }
  }
  var vel = [];
  for (s = 0; s < N; s++) {
    if (obs[s]) { rho[s] = 0; UX[s] = 0; UY[s] = 0; vel.push(0); continue; }
    var rr = 0, sx = 0, sy = 0; for (k = 0; k < 9; k++) rr += f[k][s]; for (k = 0; k < 9; k++) sx += f[k][s] * EX[k]; for (k = 0; k < 9; k++) sy += f[k][s] * EY[k];
    var vx = sx / rr, vy = sy / rr; rho[s] = rr; UX[s] = vx; UY[s] = vy; vel.push(Math.sqrt(vx * vx + vy * vy));
  }
  var massa = 0; for (s = 0; s < N; s++) if (!obs[s]) massa += rho[s];
  var nuv = (tau - 0.5) / 3, larg = 0, alt = 0, c;
  for (y = 0; y < ny; y++) { c = 0; for (x = 0; x < nx; x++) if (obs[y * nx + x]) c++; if (c > larg) larg = c; }
  for (x = 0; x < nx; x++) { c = 0; for (y = 0; y < ny; y++) if (obs[y * nx + x]) c++; if (c > alt) alt = c; }
  var avisos = [];
  if (u0 * Math.sqrt(3) > 0.15) avisos.push("Mach de rede acima de 0,15: erro de compressibilidade; reduza u_entrada");
  if (vel.some(function (v) { return v !== v; })) avisos.push("instável (NaN): aumente tau ou reduza u_entrada");
  return resultado("Lattice-Boltzmann D2Q9, colisão BGK — QUALITATIVO, Fase 1", ["2D, escoamento quase incompressível (Mach baixo)", "unidades de rede (sem escala física direta)", "paredes por volta simples (bounce-back)", "sem turbulência modelada"],
    [], { nx: nx, ny: ny, passos: passos, tau: tau },
    "Qualitativo, Fase 1: mostra onde o ar acelera, separa e forma esteira. Não usar para pressão de projeto, conforto ou dimensionamento. Projeto: OpenFOAM na Fase 2.",
    { ux: UX, uy: UY, rho: rho, vel: vel, massa_inicial: massa0, massa_final: massa, reynolds_rede: u0 * (alt || ny) / nuv, viscosidade_rede: nuv, qualitativo: true }, avisos);
}
function turb() { var T = global.TURBINAS; if (!T) throw FaltaDado("módulo Turbinas (sistema/physis-turbinas.js) ausente: as contas do vento vêm de lá"); return T; }
function weibullMomentos(serie) {
  var v = serie.filter(function (x) { return nn(x) && x >= 0; });
  if (v.length < 2) throw FaltaDado("série de vento curta demais");
  var m = soma(v) / v.length, sd = 0; v.forEach(function (x) { sd += (x - m) * (x - m); }); sd = Math.sqrt(sd / (v.length - 1));
  if (m <= 0 || sd <= 0) throw FaltaDado("série de vento constante ou nula");
  var k = Math.pow(sd / m, -1.086); return [k, m / turb().gama(1 + 1 / k)];
}
var ALFA_PAD = { agua: 0.10, aberto: 0.15, rural: 0.20, floresta: 0.25, cidade_pequena: 0.30, urbano: 0.40 };
function eolicaSerie(p) {
  var T = turb(), tb = p.turbina || {}, rho = T.densidadeAr(num(p.altitude, 0), num(p.temperatura, 25));
  var alfa = nn(p.alfa) ? p.alfa : (ALFA_PAD[p.terreno || "aberto"] || ALFA_PAD.aberto);
  var t = T.turbinaEolica(tb.diametro || 0, nn(tb.cp) ? tb.cp : 0.30, tb.v_in || 0, tb.v_nom, tb.v_out, tb.p_nom, rho);
  var cf = T.curvaFabricante ? T.curvaFabricante(tb.curva) : null; if (cf) { t.curva = cf; t.p_nom = Math.max.apply(null, cf.map(function (x) { return x[1]; })); }
  var hRef = num(p.h_ref, 10), h = num(p.altura_cubo, 12), passo = num(p.passo_h, 1), perdas = Math.max(0, Math.min(num(p.perdas, 0), 100)) / 100;
  var vc = p.serie.map(function (v) { return T.cisalhamento(v, hRef, h, alfa); }), e = 0;
  vc.forEach(function (v) { e += T.potenciaVento(v, t); });
  var eDir = e * passo * (1 - perdas), horas = vc.length * passo, kc = weibullMomentos(vc), eWb = T.energiaWeibull(t, kc[0], kc[1], horas) * (1 - perdas);
  return resultado("Energia da série (Σ P(v)·Δt) e pela Weibull ajustada (método de Justus), contas de vento.py", ["lei de potência para a altura do cubo", "curva de potência ideal ou do fabricante", "série representativa do período"],
    [], { amostras: vc.length, passo_h: passo }, "Série curta (menos de 1 ano) não representa o ano. Meça no local, na altura do cubo.",
    { kwh_serie: eDir, kwh_weibull: eWb, k: kc[0], c: kc[1], v_media_cubo: soma(vc) / vc.length, horas: horas, rho: rho, alfa: alfa, p_nom: t.p_nom });
}

/* ══════════════ 4. TERRENO E HIDROLOGIA ══════════════ */
var VIZ = [[0, 1], [1, 1], [1, 0], [1, -1], [0, -1], [-1, -1], [-1, 0], [-1, 1]];
function gradeDoMapeamento(j) { var lat = j.lat0 - j.ny * j.cs / 2; return { nx: j.nx, ny: j.ny, dx: j.cs * 111320 * Math.cos(lat * Math.PI / 180), dy: j.cs * 110540, z: j.valores.slice() }; }
/* terreno do contrato physis-geometria-lugar/1 (Mapeamento): Z[j·nx + i], j do sul para o norte → linha 0 = norte */
function gradeDaGeometria(geo) {
  var t = geo && geo.terreno; if (!t) throw FaltaDado("geometria do lugar sem terreno (desenhe ou importe o relevo no Mapeamento)");
  var z = []; for (var i = 0; i < t.ny; i++) for (var j = 0; j < t.nx; j++) z.push(t.Z[(t.ny - 1 - i) * t.nx + j]);
  return { nx: t.nx, ny: t.ny, dx: t.cs, dy: t.cs, z: z };
}
function zg(g, i, j) { if (i >= 0 && i < g.ny && j >= 0 && j < g.nx) { var v = g.z[i * g.nx + j]; return v == null ? null : v; } return null; }
function declividadeAspecto(g) {
  var nx = g.nx, ny = g.ny, dx = g.dx, dy = g.dy, dec = zeros(nx * ny).map(function () { return null; }), asp = dec.slice();
  for (var i = 0; i < ny; i++) for (var j = 0; j < nx; j++) {
    var z0 = zg(g, i, j); if (z0 == null) continue;
    var w = [-1, 0, 1].map(function (a) { return [-1, 0, 1].map(function (b) { var v = zg(g, i + a, j + b); return v == null ? z0 : v; }); });
    var dzdx = ((w[0][2] + 2 * w[1][2] + w[2][2]) - (w[0][0] + 2 * w[1][0] + w[2][0])) / (8 * dx);
    var dzdy = ((w[0][0] + 2 * w[0][1] + w[0][2]) - (w[2][0] + 2 * w[2][1] + w[2][2])) / (8 * dy);
    var s = Math.sqrt(dzdx * dzdx + dzdy * dzdy);
    dec[i * nx + j] = Math.atan(s) * 180 / Math.PI;
    asp[i * nx + j] = s === 0 ? null : ((Math.atan2(-dzdx, -dzdy) * 180 / Math.PI + 360) % 360);
  }
  var val = dec.filter(function (d) { return d != null; });
  return resultado("Declividade e aspecto pelo método de Horn (janela 3×3)", ["grade regular", "borda: repete a célula central"], [], { nx: nx, ny: ny, dx: dx, dy: dy },
    "Resolução da grade limita: modelo de 30 m não vê taludes de casa. Declividade em graus (45° = 100 %).",
    { declividade_graus: dec, aspecto_graus: asp, declividade_media: val.length ? soma(val) / val.length : null });
}
function d8(g) {
  var nx = g.nx, ny = g.ny, dirs = zeros(nx * ny).map(function () { return -1; });
  for (var i = 0; i < ny; i++) for (var j = 0; j < nx; j++) {
    var z0 = zg(g, i, j); if (z0 == null) continue;
    var best = 0, bk = -1;
    for (var k = 0; k < 8; k++) { var a = VIZ[k][0], b = VIZ[k][1], z1 = zg(g, i + a, j + b); if (z1 == null) continue;
      var dist = Math.sqrt(Math.pow(a * g.dy, 2) + Math.pow(b * g.dx, 2)), q = (z0 - z1) / dist; if (q > best) { best = q; bk = k; } }
    dirs[i * nx + j] = bk;
  }
  return dirs;
}
function acumulacao(g, dirs, peso) {
  var nx = g.nx, N = nx * g.ny; dirs = dirs || d8(g);
  var acc = []; for (var s = 0; s < N; s++) acc.push(g.z[s] == null ? 0 : (peso ? (peso[s] || 0) : 1));
  var ordem = []; for (s = 0; s < N; s++) if (g.z[s] != null) ordem.push(s);
  ordem.sort(function (a, b) { return g.z[b] - g.z[a] || a - b; });
  ordem.forEach(function (s) { var k = dirs[s]; if (k >= 0) { var i = Math.floor(s / nx), j = s - i * nx; acc[(i + VIZ[k][0]) * nx + j + VIZ[k][1]] += acc[s]; } });
  return acc;
}
function escoamento(g) {
  var dirs = d8(g), acc = acumulacao(g, dirs), area = g.dx * g.dy, sumid = 0;
  dirs.forEach(function (d, s) { if (d < 0 && g.z[s] != null) sumid++; });
  return resultado("Direção de escoamento D8 (maior queda) e acumulação de fluxo", ["água segue o vizinho mais baixo (um só caminho)", "depressões não são preenchidas"], [], { nx: g.nx, ny: g.ny },
    "D8 concentra o fluxo em linhas; em encosta lisa ele exagera canais. Depressões (−1) param o fluxo: confira no campo se são reais (lagoa, bacia) ou erro do modelo de elevação.",
    { direcoes: dirs, acumulacao: acc, area_contribuicao_m2: acc.map(function (a) { return a * area; }), sumidouros: sumid });
}
function scsCn(P, cn, ia) {
  ia = nn(ia) ? ia : premissa("sim.hidro.ia_razao", 0.2);
  if (!(cn > 0 && cn <= 100)) throw new Error("CN entre 0 e 100");
  var S = 25400 / cn - 254, Ia = ia * S; return P <= Ia ? 0 : Math.pow(P - Ia, 2) / (P - Ia + S);
}
function cnDe(uso, grupo) { var tab = premissa("sim.hidro.cn_por_uso") || {}, v = (tab[uso] || {})[grupo]; if (!nn(v)) throw FaltaDado(MARCADOR + " CN do uso '" + uso + "' no grupo hidrológico '" + grupo + "'"); return v; }
function escoamentoScs(g, chuva, usos, grupo) {
  var N = g.nx * g.ny, area = g.dx * g.dy, cn = [], q = [];
  for (var s = 0; s < N; s++) { cn.push(g.z[s] == null ? null : cnDe(typeof usos === "string" ? usos : usos[s], typeof grupo === "string" ? grupo : grupo[s])); }
  cn.forEach(function (c) { q.push(c == null ? 0 : scsCn(chuva, c)); });
  var vol = acumulacao(g, null, q.map(function (x) { return x * area / 1000; })), tot = 0; q.forEach(function (x) { tot += x * area / 1000; });
  return resultado("Escoamento superficial pelo número de curva (SCS-CN, USDA NRCS) e soma a montante pelo D8", ["chuva uniforme no evento", "condição de umidade antecedente média (II)", "sem infiltração ao longo do caminho"],
    [usada("sim.hidro.cn_por_uso"), usada("sim.hidro.ia_razao")], { nx: g.nx, ny: g.ny },
    "Evento isolado, bacias pequenas. Não dá vazão de pico nem hidrograma; para drenagem urbana use o método da norma/prefeitura.",
    { cn: cn, lamina_mm: q, volume_acumulado_m3: vol, volume_total_m3: tot, chuva_mm: chuva });
}
function usle(g, R, K, C, P, comp) {
  var falt = [["R", R], ["K", K], ["C", C], ["P", P]].filter(function (x) { return !nn(x[1]); }).map(function (x) { return x[0]; });
  if (falt.length) throw FaltaDado(MARCADOR + " fatores " + falt.join(", ") + " da USLE (digite do estudo do lugar)");
  var ls = premissa("sim.erosao.ls") || {}, N = g.nx * g.ny, dec = declividadeAspecto(g).declividade_graus, acc = acumulacao(g), lado = Math.sqrt(g.dx * g.dy);
  var out = zeros(N).map(function () { return null; }), lsv = out.slice(), val = function (x, s) { return Array.isArray(x) ? x[s] : x; };
  for (var s = 0; s < N; s++) {
    if (dec[s] == null) continue;
    var th = dec[s] * Math.PI / 180, pct = Math.tan(th) * 100, m = pct >= 5 ? 0.5 : pct >= 3.5 ? 0.4 : pct >= 1 ? 0.3 : 0.2;
    var lam = comp ? comp : lado * Math.sqrt(acc[s]), L = Math.pow(lam / ls.lambda_ref, m), S = ls.a * Math.pow(Math.sin(th), 2) + ls.b * Math.sin(th) + ls.c;
    lsv[s] = L * S; out[s] = val(R, s) * val(K, s) * lsv[s] * val(C, s) * val(P, s);
  }
  var v = out.filter(function (x) { return x != null; }), g2 = function (x) { return Array.isArray(x) ? "grade" : x; };
  return resultado("USLE: A = R·K·LS·C·P (Wischmeier & Smith), LS pela declividade e comprimento de rampa", ["perda média anual", "erosão laminar e em sulcos (não voçoroca)"],
    [usada("sim.erosao.ls"), { id: "usle.fatores", valor: { R: g2(R), K: g2(K), C: g2(C), P: g2(P) }, status: "digitado", fonte: "estudo do lugar" }], { nx: g.nx, ny: g.ny },
    "Ordem de grandeza para comparar cenários (com e sem cobertura, curva de nível). Não prevê deslizamento: risco de encosta é a aba Resiliência e a Defesa Civil.",
    { perda_t_ha_ano: out, ls: lsv, media: v.length ? soma(v) / v.length : null, maxima: v.length ? Math.max.apply(null, v) : null });
}
function visada(g, oi, oj, hObs, hAlvo) {
  hObs = nn(hObs) ? hObs : 1.6; hAlvo = hAlvo || 0;
  var nx = g.nx, ny = g.ny, z0 = zg(g, oi, oj); if (z0 == null) throw FaltaDado("observador fora da grade ou sem cota");
  var h0 = z0 + hObs, vis = zeros(nx * ny), tot = 0;
  for (var i = 0; i < ny; i++) for (var j = 0; j < nx; j++) {
    var zt = zg(g, i, j); if (zt == null) continue;
    if (i === oi && j === oj) { vis[i * nx + j] = 1; continue; }
    var di = i - oi, dj = j - oj, dist = Math.sqrt(Math.pow(di * g.dy, 2) + Math.pow(dj * g.dx, 2)), alvo = (zt + hAlvo - h0) / dist;
    var n = Math.ceil(2 * Math.max(Math.abs(di), Math.abs(dj))), ok = true;
    for (var k = 1; k < n; k++) { var f = k / n, ii = Math.floor(oi + f * di + 0.5), jj = Math.floor(oj + f * dj + 0.5);
      if ((ii === i && jj === j) || (ii === oi && jj === oj)) continue;
      var zc = zg(g, ii, jj); if (zc == null) continue; if ((zc - h0) / (f * dist) > alvo) { ok = false; break; } }
    vis[i * nx + j] = ok ? 1 : 0;
  }
  g.z.forEach(function (z) { if (z != null) tot++; });
  return resultado("Visada simples (linha de visada sobre a grade, sem curvatura da Terra)", ["terreno nu (sem árvores nem prédios)", "vizinho mais próximo ao longo do raio"], [], { nx: nx, ny: ny },
    "Só relevo; vegetação e construções mudam tudo. Distâncias de poucos km.", { visivel: vis, fracao_visivel: soma(vis) / Math.max(1, tot) });
}

/* ══════════════ 5. MONTE CARLO ══════════════ */
function sortear(d, rng) {
  if (typeof d === "number") return d;
  var t = d.tipo;
  if (t === "normal") return d.media + d.dp * rng.normal();
  if (t === "uniforme") return d.min + (d.max - d.min) * rng();
  if (t === "triangular") { var a = d.min, c = d.moda, b = d.max, u = rng(), fc = (c - a) / (b - a);
    return u < fc ? a + Math.sqrt(u * (b - a) * (c - a)) : b - Math.sqrt((1 - u) * (b - a) * (b - c)); }
  if (t === "lognormal") { var m = d.media, s = d.dp, s2 = Math.log(1 + Math.pow(s / m, 2)); return Math.exp(Math.log(m) - s2 / 2 + Math.sqrt(s2) * rng.normal()); }
  throw new Error("distribuição desconhecida: " + t);
}
var MODELOS = {
  carbono: function (x) { var s = 0, i = 0; while (("a" + i) in x) { s += x["a" + i] * x["f" + i]; i++; } return s; },
  solar: function (x) { return x.kwp * x.h * x.pr * 365; },
  payback: function (x) { return x.economia > 0 ? x.custo / x.economia : Infinity; },
  biogas: function (x) { var s = 0, i = 0; while (("kg" + i) in x) { s += x["kg" + i] * x["st" + i] * x["sv" + i] * x["bmp" + i] * x["ch4" + i] * (("fr" + i) in x ? x["fr" + i] : 1); i++; } return s; }
};
function monteCarlo(entradas, modelo, n, semente, percs) {
  n = n || premissa("sim.mc.amostras", 2000); semente = nn(semente) ? semente : premissa("sim.mc.semente", 42); percs = percs || [5, 25, 50, 75, 95];
  var f = typeof modelo === "string" ? MODELOS[modelo] : modelo, rng = Rng(semente), nomes = Object.keys(entradas).sort(), ys = [];
  for (var i = 0; i < n; i++) { var x = {}; nomes.forEach(function (k) { x[k] = sortear(entradas[k], rng); }); ys.push(f(x)); }
  var ok = ys.filter(function (y) { return isFinite(y); }).sort(function (a, b) { return a - b; }), m = ok.length ? soma(ok) / ok.length : NaN, sd = 0;
  if (ok.length > 1) { ok.forEach(function (y) { sd += (y - m) * (y - m); }); sd = Math.sqrt(sd / (ok.length - 1)); }
  var pc = {}; percs.forEach(function (p) { pc[String(p)] = percentil(ok, p); });
  return resultado("Monte Carlo (amostragem aleatória simples, gerador mulberry32 com semente fixa)", ["entradas independentes (sem correlação)", "distribuições escolhidas pela pessoa ou premissa"],
    [usada("sim.mc.amostras", n), usada("sim.mc.semente", semente)], { amostras: n, semente: semente, ordem_entradas: nomes },
    "A faixa só é tão boa quanto as distribuições de entrada. Entradas correlacionadas (ex.: tarifa e inflação) ficam mais largas ou estreitas do que o real.",
    { media: m, dp: sd, percentis: pc, n_validos: ok.length, modelo: typeof modelo === "string" ? modelo : "função" });
}

/* ══════════════ 6. QUBO ══════════════ */
var AVISO_QUANTICO = "Trilha de pesquisa: solução quântica (QAOA/QUBO) é P&D, cabe ~20–30 variáveis em simulador e precisa reproduzir o ótimo clássico. Nunca usar em relatório nem certificação.";
var LIMITE_EXATO = 24;
function qNovo(n, nomes) { var no = nomes; if (!no) { no = []; for (var i = 0; i < n; i++) no.push("x" + i); } return { n: n, nomes: no, linear: zeros(n), quad: {}, offset: 0 }; }
function qSoma(Q, i, j, w) { if (i === j) { Q.linear[i] += w; return; } var a = Math.min(i, j), b = Math.max(i, j), k = a + "," + b; Q.quad[k] = (Q.quad[k] || 0) + w; }
function qLista(Q) { return Object.keys(Q.quad).map(function (k) { var p = k.split(","); return [+p[0], +p[1], Q.quad[k]]; }).sort(function (x, y) { return x[0] - y[0] || x[1] - y[1]; }); }
function qEnergia(Q, x) { var e = Q.offset, i; for (i = 0; i < Q.n; i++) if (x[i]) e += Q.linear[i]; qLista(Q).forEach(function (t) { if (x[t[0]] && x[t[1]]) e += t[2]; }); return e; }
function qViz(Q) { var nb = []; for (var i = 0; i < Q.n; i++) nb.push([]); qLista(Q).forEach(function (t) { nb[t[0]].push([t[1], t[2]]); nb[t[1]].push([t[0], t[2]]); }); return nb; }
function qExato(Q) {
  var n = Q.n; if (n > LIMITE_EXATO) throw FaltaDado(n + " variáveis: acima de " + LIMITE_EXATO + " use o recozimento");
  var nb = qViz(Q), h = Q.linear, x = zeros(n), e = Q.offset, best = e, bx = x.slice(), tot = Math.pow(2, n);
  for (var g = 1; g < tot; g++) {
    var i = 0, gg = g; while ((gg & 1) === 0) { gg >>>= 1; i++; }
    var d = h[i]; for (var q = 0; q < nb[i].length; q++) if (x[nb[i][q][0]]) d += nb[i][q][1];
    if (x[i]) { e -= d; x[i] = 0; } else { e += d; x[i] = 1; }
    if (e < best - 1e-9) { best = e; bx = x.slice(); }
  }
  return { x: bx, energia: qEnergia(Q, bx), metodo: "exato (enumeração em código de Gray)", avaliados: tot };
}
function qRecozimento(Q, semente, varr, t0, t1) {
  var n = Q.n; semente = nn(semente) ? semente : premissa("sim.mc.semente", 42); varr = varr || premissa("sim.qubo.varreduras", 400);
  var nb = qViz(Q), h = Q.linear, esc = 1e-9, i;
  h.forEach(function (v) { if (Math.abs(v) > esc) esc = Math.abs(v); }); qLista(Q).forEach(function (t) { if (Math.abs(t[2]) > esc) esc = Math.abs(t[2]); });
  t0 = nn(t0) ? t0 : 2 * esc; t1 = nn(t1) ? t1 : 1e-3 * esc;
  var rng = Rng(semente), x = []; for (i = 0; i < n; i++) x.push(rng() < 0.5 ? 1 : 0);
  var e = qEnergia(Q, x), best = e, bx = x.slice();
  for (var s = 0; s < varr; s++) {
    var T = t0 * Math.pow(t1 / t0, s / Math.max(1, varr - 1));
    for (i = 0; i < n; i++) {
      var d = h[i]; for (var q = 0; q < nb[i].length; q++) if (x[nb[i][q][0]]) d += nb[i][q][1];
      var dE = x[i] ? -d : d;
      if (dE <= 0 || rng() < Math.exp(-dE / T)) { x[i] = x[i] ? 0 : 1; e += dE; if (e < best - 1e-9) { best = e; bx = x.slice(); } }
    }
  }
  return { x: bx, energia: qEnergia(Q, bx), metodo: "recozimento simulado (" + varr + " varreduras, semente " + semente + ")" };
}
function qResolver(Q, semente) { return Q.n <= Math.min(LIMITE_EXATO, premissa("sim.qubo.limite_exato", 20)) ? qExato(Q) : qRecozimento(Q, semente); }
function qPen(base) { return premissa("sim.qubo.penalidade_fator", 1.5) * base; }
function qRes(metodo, Q, sol, P, dados, limites) {
  var d = { qubo: { n: Q.n, variaveis: Q.nomes }, Q: Q, solucao: sol, penalidade: P, aviso_quantico: AVISO_QUANTICO };
  for (var k in dados) d[k] = dados[k];
  return resultado(metodo + " — resolvido no clássico", ["restrições como penalidade quadrática", "penalidade grande o bastante para não violar"],
    [usada("sim.qubo.penalidade_fator"), usada("sim.qubo.limite_exato")], { variaveis: Q.n, termos_quadraticos: Object.keys(Q.quad).length }, limites, d);
}
function qPaineis(p) {
  var g = p.ganho.slice(), n = g.length, k = p.k, som = p.sombra || [], i, j, sm = 0;
  som.forEach(function (s) { sm += Math.abs(s[2]); });
  var P = p.penalidade || qPen(Math.max.apply(null, g) + sm), Q = qNovo(n, g.map(function (_, i) { return "posicao_" + i; }));
  for (i = 0; i < n; i++) qSoma(Q, i, i, -g[i] + P - 2 * P * k);
  for (i = 0; i < n; i++) for (j = i + 1; j < n; j++) qSoma(Q, i, j, 2 * P);
  som.forEach(function (s) { qSoma(Q, s[0], s[1], s[2]); });
  Q.offset = P * k * k;
  var sol = qResolver(Q, p.semente), esc = []; for (i = 0; i < n; i++) if (sol.x[i]) esc.push(i);
  var kwh = 0; esc.forEach(function (i) { kwh += g[i]; }); som.forEach(function (s) { if (sol.x[s[0]] && sol.x[s[1]]) kwh -= s[2]; });
  return qRes("Escolha de posições de placas sob sombra (QUBO)", Q, sol, P, { escolhidas: esc, kwh_ano: kwh, k: k, atende_k: esc.length === k },
    "Sombra mútua entra só aos pares; a geração de cada posição vem do estudo solar (aba Energia solar).");
}
function dijkstra(n, ar, o, d) {
  var adj = [], dist = [], feito = [], i; for (i = 0; i < n; i++) { adj.push([]); dist.push(Infinity); feito.push(false); }
  ar.forEach(function (a) { adj[a[0]].push([a[1], a[2]]); adj[a[1]].push([a[0], a[2]]); }); dist[o] = 0;
  for (;;) { var v = -1; for (i = 0; i < n; i++) if (!feito[i] && dist[i] < Infinity && (v < 0 || dist[i] < dist[v])) v = i; if (v < 0) break; feito[v] = true;
    adj[v].forEach(function (x) { if (dist[v] + x[1] < dist[x[0]]) dist[x[0]] = dist[v] + x[1]; }); }
  return dist[d] === Infinity ? null : dist[d];
}
function qRota(p) {
  var nx = p.nx, ny = p.ny, blq = p.bloqueados || [], cp = num(p.custo_padrao, 1), ct = p.custo || {}, ar = [], v, i, j;
  for (v = 0; v < nx * ny; v++) { i = Math.floor(v / nx); j = v - i * nx;
    [[i, j + 1], [i + 1, j]].forEach(function (ab) { if (ab[0] < ny && ab[1] < nx) { var u = ab[0] * nx + ab[1];
      if (blq.indexOf(v) < 0 && blq.indexOf(u) < 0) { var c = nn(ct[v + "," + u]) ? ct[v + "," + u] : nn(ct[u + "," + v]) ? ct[u + "," + v] : cp; ar.push([v, u, c]); } } }); }
  var o = p.origem, d = p.destino, internos = [];
  for (v = 0; v < nx * ny; v++) if (blq.indexOf(v) < 0 && v !== o && v !== d) internos.push(v);
  var ne = ar.length, nomes = ar.map(function (a) { return "aresta_" + a[0] + "_" + a[1]; }).concat(internos.map(function (v) { return "aux_" + v; }));
  var Q = qNovo(ne + internos.length, nomes), sc = 0; ar.forEach(function (a) { sc += a[2]; });
  var P = p.penalidade || qPen(sc), x1, x2;
  ar.forEach(function (a, e) { qSoma(Q, e, e, a[2]); });
  var inc = {}; for (v = 0; v < nx * ny; v++) inc[v] = [];
  ar.forEach(function (a, e) { inc[a[0]].push(e); inc[a[1]].push(e); });
  for (v = 0; v < nx * ny; v++) inc[v].sort(function (a, b) { return a - b; });
  [o, d].forEach(function (v) { var L = inc[v]; L.forEach(function (e) { qSoma(Q, e, e, -P); });
    for (x1 = 0; x1 < L.length; x1++) for (x2 = x1 + 1; x2 < L.length; x2++) qSoma(Q, L[x1], L[x2], 2 * P); Q.offset += P; });
  internos.forEach(function (v, k) { var y = ne + k, L = inc[v];
    L.forEach(function (e) { qSoma(Q, e, e, P); qSoma(Q, e, y, -4 * P); });
    for (x1 = 0; x1 < L.length; x1++) for (x2 = x1 + 1; x2 < L.length; x2++) qSoma(Q, L[x1], L[x2], 2 * P);
    qSoma(Q, y, y, 4 * P); });
  var sol = qResolver(Q, p.semente), us = [], custo = 0;
  for (var e = 0; e < ne; e++) if (sol.x[e]) { us.push([ar[e][0], ar[e][1]]); custo += ar[e][2]; }
  var ref = dijkstra(nx * ny, ar, o, d);
  return qRes("Caminho de tubo numa grade (QUBO com restrição de grau)", Q, sol, P, { arestas: us, custo: custo, custo_dijkstra: ref, igual_ao_classico: ref != null && Math.abs(custo - ref) < 1e-9 },
    "Grade grossa; desníveis, diâmetro e perda de carga são das abas Água/Turbinas/AVAC (redes existentes).");
}
function qTopologia(p) {
  var nx = p.nx, ny = p.ny, M = p.mascara || zeros(nx * ny).map(function () { return 1; }), cel = [], s;
  for (s = 0; s < nx * ny; s++) if (M[s]) cel.push(s);
  var en = p.energia, emax = 0; cel.forEach(function (s) { if (en[s] > emax) emax = en[s]; }); emax = emax || 1;
  var beta = nn(p.suavidade) ? p.suavidade : premissa("sim.qubo.suavidade", 0.2), V = Math.round(p.fracao * cel.length);
  var P = p.penalidade || qPen(1 + 4 * beta), idx = {}; cel.forEach(function (s, k) { idx[s] = k; });
  var Q = qNovo(cel.length, cel.map(function (s) { return "celula_" + s; })), a, b;
  cel.forEach(function (s) { qSoma(Q, idx[s], idx[s], -en[s] / emax + P - 2 * P * V); });
  for (a = 0; a < cel.length; a++) for (b = a + 1; b < cel.length; b++) qSoma(Q, a, b, 2 * P);
  cel.forEach(function (s) { var i = Math.floor(s / nx), j = s - i * nx;
    [j + 1 < nx ? i * nx + j + 1 : null, i + 1 < ny ? (i + 1) * nx + j : null].forEach(function (u) {
      if (u != null && (u in idx)) { qSoma(Q, idx[s], idx[s], beta); qSoma(Q, idx[u], idx[u], beta); qSoma(Q, idx[s], idx[u], -2 * beta); } }); });
  (p.fixas || []).forEach(function (s) { if (s in idx) qSoma(Q, idx[s], idx[s], -2 * P * cel.length); });
  Q.offset = P * V * V;
  var sol = qResolver(Q, p.semente), nova = zeros(nx * ny); cel.forEach(function (s) { nova[s] = sol.x[idx[s]]; });
  return qRes("Topologia grossa de peça 2D (QUBO heurístico sobre a energia de deformação)", Q, sol, P, { mascara: nova, celulas: soma(nova), alvo: V },
    "Heurística de um passo, não é otimização topológica completa (SIMP). Reanalise a peça nova no CST.");
}
function qExportar(Q, problema, classico) {
  var quad = qLista(Q), hs = Q.linear.map(function (h) { return -h / 2; }), off = Q.offset + soma(Q.linear) / 2;
  quad.forEach(function (t) { hs[t[0]] -= t[2] / 4; hs[t[1]] -= t[2] / 4; off += t[2] / 4; });
  return { formato: "physis-qubo/1", problema: problema, n: Q.n, nomes: Q.nomes, linear: Q.linear, quadratico: quad, offset: Q.offset,
    ising: { convencao: "x = (1 - s)/2, s em {-1, +1}", h: hs, J: quad.map(function (t) { return [t[0], t[1], t[2] / 4]; }), offset: off }, solucao_classica: classico || null, aviso: AVISO_QUANTICO };
}

/* ══════════════ 7. BIOGÁS ══════════════ */
var DIAS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], DENS_CH4 = 0.716;
var AVISOS_SEG = ["Biogás é inflamável e o H₂S é tóxico e corrosivo: filtro de H₂S (limalha de ferro ou similar), dreno de condensado, válvula de alívio e corta-chamas antes do queimador ou do motor.",
  "Local ventilado, sem chama perto do gasômetro; nunca entrar no digestor sem ventilação e acompanhante.",
  "Digestato de dejetos ainda pode ter patógenos: aplicar no solo seguindo a orientação agronômica."];
/* mesmas contas do carbono.py / physis-carbono.js (combustao + tco2e) para GLP e diesel B */
function fatoresCarbono(F) {
  F = F || CFG.fatores || lerJsonScript("base-fatores-emissao") || (global.SIMULACAO_CASOS && global.SIMULACAO_CASOS.fatores_base);
  if (!F) throw FaltaDado(MARCADOR + " base de fatores de emissão (sistema/physis-fatores-emissao.json)");
  var gw = F.gwp[F.gwp.padrao], C = F.combustiveis, BIO = { biodiesel: 1, etanol_anidro: 1, etanol_hidratado: 1, lenha: 1, carvao_vegetal: 1 };
  var comb = function (cid, qtd) { var partes = [], M = F.misturas; if (M[cid]) { var m = M[cid]; partes.push([m.fossil, qtd * (1 - m.teor_bio)]); if (m.bio) partes.push([m.bio, qtd * m.teor_bio]); } else partes.push([cid, qtd]);
    var gs = {}; partes.forEach(function (pp) { var c = C[pp[0]], tj = pp[1] * c.mj / 1e6, e = c.estacionaria, ch4 = BIO[pp[0]] ? "CH4_bio" : "CH4_fossil";
      gs.CO2 = (gs.CO2 || 0) + tj * (c.co2 || 0); gs[ch4] = (gs[ch4] || 0) + tj * e.ch4; gs.N2O = (gs.N2O || 0) + tj * e.n2o; }); return gs; };
  var tco2e = function (gs) { var s = 0; Object.keys(gs).forEach(function (g) { s += gs[g] * (gw[g] || 0); }); return s / 1000; };
  var A = F.rede.anual, rede = (A[F.rede.padrao] || {}).valor, dej = {};
  Object.keys(F.agro.rebanho).forEach(function (k) { dej[k] = F.agro.rebanho[k].dejetos_ch4; });
  return { glp_t_por_kg: tco2e(comb("glp", 1)), diesel_t_por_l: tco2e(comb("diesel_b", 1)), rede_t_por_mwh: rede, gwp_ch4: gw.CH4_bio, diesel_mj_por_l: C.diesel.mj, dejetos_ch4_kg_cab_ano: dej };
}
function bSub(s) {
  var tab = premissa("sim.biogas.substratos") || {}, base = JSON.parse(JSON.stringify(tab[s.tipo] || {}));
  ["st", "sv", "bmp", "ch4", "k_ref", "npk", "esterco", "rebanho"].forEach(function (k) { if (nn(s[k])) base[k] = s[k]; });
  var falt = ["st", "sv", "bmp", "ch4"].filter(function (k) { return !nn(base[k]); });
  if (falt.length) throw FaltaDado(MARCADOR + " " + falt.join(", ").toUpperCase() + " do substrato '" + s.tipo + "' (análise de laboratório ou tabela [CONFERIR])");
  base.tipo = s.tipo; base.nome = base.nome || s.tipo; base.kg_dia = s.kg_dia; base.cabecas = nn(s.cabecas) ? s.cabecas : null; return base;
}
function kTemperatura(T, kRef) {
  var c = premissa("sim.biogas.cinetica") || {}; kRef = nn(kRef) ? kRef : c.k_ref_dia;
  if (!nn(kRef) || !nn(c.theta) || !nn(c.t_ref_c)) throw FaltaDado(MARCADOR + " cinética (premissa sim.biogas.cinetica)");
  return kRef * Math.pow(c.theta, T - c.t_ref_c);
}
function fracaoBmp(k, trh, modelo) { if (trh <= 0) return 0; return modelo === "pistonado" ? 1 - Math.exp(-k * trh) : k * trh / (1 + k * trh); }
function tempsDiarias(mensal) {
  var meio = [], acc = 0, out = []; DIAS.forEach(function (d) { meio.push(acc + d / 2); acc += d; });
  for (var dia = 0; dia < 365; dia++) {
    var t = dia + 0.5, m = 0, a, b, ta, tb; while (m < 11 && meio[m + 1] <= t) m++;
    if (t < meio[0]) { a = meio[11] - 365; b = meio[0]; ta = mensal[11]; tb = mensal[0]; }
    else if (m === 11) { a = meio[11]; b = meio[0] + 365; ta = mensal[11]; tb = mensal[0]; }
    else { a = meio[m]; b = meio[m + 1]; ta = mensal[m]; tb = mensal[m + 1]; }
    out.push(ta + (tb - ta) * (t - a) / (b - a));
  }
  return out;
}
function biogasSimular(p, fatores) {
  fatores = fatores || fatoresCarbono();
  var subs = p.substratos.map(bSub), tipos = premissa("sim.biogas.tipos_digestor") || {}, dg = p.digestor || {}, tipo = dg.tipo || "mistura_completa";
  var modelo = (tipos[tipo] || {}).modelo || "mistura", reg = p.regime || "mesofilico", temps = premissa("sim.biogas.temperaturas") || {}, avisos = [], i, m;
  var qIn = 0; subs.forEach(function (s) { qIn += s.kg_dia; }); qIn = qIn / 1000 + num(p.agua_l_dia, 0) / 1000;
  var folga = premissa("sim.biogas.folga_volume", 1.25), dim = null, vUtil;
  if (dg.volume_m3) vUtil = dg.volume_m3;
  else { var trhA = p.trh_alvo_dias || (premissa("sim.biogas.trh_min_dias") || {})[reg]; if (!nn(trhA)) throw FaltaDado(MARCADOR + " volume do digestor ou TRH alvo");
    vUtil = qIn * trhA; dim = { trh_alvo_dias: trhA, volume_util_m3: vUtil, volume_total_m3: vUtil * folga, folga: folga }; }
  var trh = qIn > 0 ? vUtil / qIn : 0, svDia = 0; subs.forEach(function (s) { svDia += s.kg_dia * s.st * s.sv; });
  var cov = vUtil > 0 ? svDia / vUtil : Infinity, covMax = (premissa("sim.biogas.cov_max") || {})[reg === "ambiente" ? "ambiente" : reg];
  if (nn(covMax) && cov > covMax) avisos.push("Sobrecarga: carga orgânica " + cov.toFixed(2) + " kg SV/m³·dia acima do limite " + covMax + " do regime (premissa sim.biogas.cov_max): risco de acidificação; aumente o volume ou reduza a carga.");
  var trhMin = (premissa("sim.biogas.trh_min_dias") || {})[reg];
  if (nn(trhMin) && trh < trhMin) avisos.push("TRH curto: " + trh.toFixed(1) + " dias, abaixo de " + trhMin + " dias para o regime (lavagem das bactérias).");
  var tMes;
  if (reg === "ambiente") { var tm = p.temperatura_mensal;
    if (!tm || tm.length !== 12) throw FaltaDado("local não informado: digestor sem aquecimento precisa da temperatura mensal do local da instalação (Início ou Planejador); nenhum padrão é usado");
    var ganho = premissa("sim.biogas.ganho_enterrado_c", 0); tMes = tm.map(function (t) { return t + ganho; }); }
  else { var tf = temps[reg]; if (!nn(tf)) throw FaltaDado(MARCADOR + " temperatura do regime '" + reg + "'"); tMes = zeros(12).map(function () { return tf; }); }
  var tMin = premissa("sim.biogas.t_min_c"), tMinMes = Math.min.apply(null, tMes);
  if (nn(tMin) && tMinMes < tMin) avisos.push("Temperatura baixa: " + tMinMes.toFixed(1) + " °C no mês mais frio (abaixo de " + tMin + " °C): a produção cai muito; pense em estufa, enterrar ou aquecer com o próprio biogás.");
  var tDia = tempsDiarias(tMes);
  var diario = tDia.map(function (T) { var bio = 0, ch4 = 0; subs.forEach(function (s) { var f = fracaoBmp(kTemperatura(T, s.k_ref), trh, modelo), b = s.kg_dia * s.st * s.sv * s.bmp * f; bio += b; ch4 += b * s.ch4; }); return [bio, ch4]; });
  var mensal = [], d0 = 0;
  DIAS.forEach(function (nd, m) { var bio = 0, ch4 = 0; for (var k = d0; k < d0 + nd; k++) bio += diario[k][0]; for (k = d0; k < d0 + nd; k++) ch4 += diario[k][1];
    mensal.push({ mes: m + 1, t_c: tMes[m], biogas_m3: bio, ch4_m3: ch4 }); d0 += nd; });
  var bioAno = 0, ch4Ano = 0; diario.forEach(function (x) { bioAno += x[0]; }); diario.forEach(function (x) { ch4Ano += x[1]; });
  var bioDia = bioAno / 365, bmpPot = 0; subs.forEach(function (s) { bmpPot += s.kg_dia * s.st * s.sv * s.bmp; });
  var pci = premissa("biogas.pci"), pciGlp = premissa("glp.pci"), etaEl = premissa("sim.biogas.eta_eletrica"), etaT = premissa("sim.biogas.eta_termica"), qh = premissa("sim.biogas.queimador_m3_h");
  var eTh = bioDia * pci, eEl = eTh * etaEl, horas = p.horas_gerador || premissa("sim.biogas.horas_gerador", 24), pkw = horas > 0 ? eEl / horas : 0;
  var fpM = p.fp_medido, fp = fpM && fpM > 0 && fpM <= 1 ? fpM : premissa("eletrica.fator_potencia_padrao"), skva = fp ? pkw / fp : null, qkvar = skva != null ? Math.sqrt(Math.max(0, skva * skva - pkw * pkw)) : null, fpMin = premissa("eletrica.fator_potencia_minimo");
  var tAmb = p.temperatura_mensal, aquec = null;
  if ((reg === "mesofilico" || reg === "termofilico") && tAmb && tAmb.length === 12) { aquec = 0; for (m = 0; m < 12; m++) aquec += qIn * 1000 * 4.186 * Math.max(0, tMes[m] - tAmb[m]) / 3600 * DIAS[m]; aquec /= 365; }
  var usos = p.usos || { glp: 1 }, fg = num(usos.glp, 0), fe = num(usos.eletricidade, 0), fd = num(usos.diesel, 0);
  if (fg + fe + fd > 1 + 1e-9) throw new Error("as frações de uso (glp + eletricidade + diesel) passam de 1");
  var evGlp = bioAno * fg * pci / pciGlp * fatores.glp_t_por_kg, evEl = eTh * 365 * fe * etaEl / 1000 * fatores.rede_t_por_mwh, evDi = eTh * 365 * fd * 3.6 / fatores.diesel_mj_por_l * fatores.diesel_t_por_l;
  var evDej = 0, vaz = premissa("sim.biogas.vazamento", 0);
  if (p.manejo_dejetos) subs.forEach(function (s) {
    if (s.esterco && s.cabecas && s.rebanho) { var f = fatores.dejetos_ch4_kg_cab_ano[s.rebanho]; if (!nn(f)) { avisos.push(MARCADOR + " CH₄ de dejetos do rebanho '" + s.rebanho + "' na base do Carbono"); return; }
      evDej += s.cabecas * f * (1 - vaz) * fatores.gwp_ch4 / 1000; }
    else if (s.esterco) avisos.push("Manejo de dejetos de '" + s.nome + "': informe o número de cabeças para contar o metano evitado.");
  });
  var vazT = ch4Ano * vaz * DENS_CH4 * fatores.gwp_ch4 / 1000, densB = premissa("sim.biogas.densidade_biogas", 1.15), digM3 = Math.max(0, qIn - bioDia * densB / 1000);
  var npk = { N: 0, P2O5: 0, K2O: 0 }, npkFalta = [];
  subs.forEach(function (s) { var n = s.npk; if (!n || ["N", "P2O5", "K2O"].some(function (k) { return !nn(n[k]); })) { npkFalta.push(s.nome); return; }
    ["N", "P2O5", "K2O"].forEach(function (k) { npk[k] += s.kg_dia / 1000 * n[k]; }); });
  if (npkFalta.length) avisos.push(MARCADOR + " N-P-K de: " + npkFalta.join(", ") + " (análise do digestato)");
  if (reg === "termofilico") avisos.push("Termofílico é mais sensível a variação de temperatura e amônia: controle diário.");
  var inc = premissa("sim.biogas.incerteza") || {}, ent = {};
  subs.forEach(function (s, i) {
    var fr = 0; tDia.forEach(function (T) { fr += fracaoBmp(kTemperatura(T, s.k_ref), trh, modelo); }); fr /= 365;
    [["kg", s.kg_dia, inc.kg_cv], ["st", s.st, inc.st_cv], ["sv", s.sv, inc.sv_cv], ["bmp", s.bmp, inc.bmp_cv], ["ch4", s.ch4, inc.ch4_cv]].forEach(function (x) {
      ent[x[0] + i] = x[2] ? { tipo: "normal", media: x[1], dp: x[1] * x[2] } : x[1]; });
    ent["fr" + i] = fr;
  });
  var mc = monteCarlo(ent, "biogas", p.mc || premissa("sim.mc.amostras", 2000), p.semente);
  avisos = avisos.concat(AVISOS_SEG);
  return resultado("Biogás: potencial (ST × SV × BMP) × fração alcançada por cinética de 1ª ordem com k(T) = k_ref·θ^(T−T_ref)",
    ["alimentação diária constante", "densidade da carga 1000 kg/m³", "modelo de reator: " + modelo, "temperatura do digestor = do regime ou a média mensal do local (+ ganho de enterrar)", "sem inibição (amônia, H₂S, óleo)"],
    [usada("sim.biogas.substratos"), usada("sim.biogas.cinetica"), usada("sim.biogas.cov_max"), usada("sim.biogas.trh_min_dias"), usada("sim.biogas.temperaturas"), usada("biogas.pci"), usada("glp.pci"),
      usada("sim.biogas.eta_eletrica"), usada("sim.biogas.eta_termica"), usada("eletrica.fator_potencia_padrao", fp), usada("sim.biogas.vazamento"), usada("sim.biogas.incerteza")],
    { dias: 365, meses: 12, substratos: subs.length },
    "Pré-dimensionamento. BMP e ST mudam com a dieta dos animais e a idade do resíduo: o ensaio de BMP do substrato real vale mais. Partida, codigestão desequilibrada e inibição não estão no modelo.",
    { q_entrada_m3_dia: qIn, volume_util_m3: vUtil, trh_dias: trh, cov_kg_sv_m3_dia: cov, cov_max: nn(covMax) ? covMax : null, dimensionamento: dim, modelo_reator: modelo, regime: reg,
      biogas_m3_dia: bioDia, ch4_m3_dia: ch4Ano / 365, biogas_m3_ano: bioAno, ch4_m3_ano: ch4Ano, potencial_bmp_m3_dia: bmpPot, fracao_media_bmp: bmpPot > 0 ? bioDia / bmpPot : null,
      mensal: mensal, diario_biogas_m3: diario.map(function (x) { return x[0]; }), temperatura_dia_c: tDia,
      energia: { termica_kwh_dia: eTh, eletrica_kwh_dia: eEl, calor_util_kwh_dia: eTh * etaT, glp_kg_dia: eTh / pciGlp, horas_queimador_dia: qh ? bioDia / qh : null, aquecimento_carga_kwh_dia: aquec },
      gerador: { p_kw: pkw, q_kvar: qkvar, s_kva: skva, fp: fp, horas_dia: horas, fp_fonte: fpM && fpM > 0 && fpM <= 1 ? "medido" : "premissa", fp_baixo: nn(fpMin) && nn(fp) && fp < fpMin },
      evitadas_t_ano: { glp: evGlp, eletricidade: evEl, diesel: evDi, dejetos: evDej, vazamento: -vazT, total: evGlp + evEl + evDi + evDej - vazT },
      carbono_ctx: { biogas_m3_dia: bioDia * fg, fonte: "Simulação de biogás (physis_hub.simulacao.biogas), parte usada no lugar do GLP" },
      digestato: { m3_dia: digM3, npk_kg_dia: npkFalta.length ? null : npk }, faixa_ch4_m3_dia: mc.percentis, faixa_media: mc.media }, avisos);
}

/* ══════════════ casos comuns (paridade) ══════════════ */
function rodarCaso(c) {
  var e = c.entrada;
  switch (c.solver) {
    case "termica.u_composicao": return uComposicao(e.composicao);
    case "termica.u_valor": return uValor(e.camadas, e.tipo, e.rsi, e.rse, e.ti, e.te);
    case "termica.transiente_1d": return transiente1d(e);
    case "termica.placa_2d": return placa2d(e);
    case "estrutura.portico": { var r = portico(e); if (e.verificar) r.verificacao = verificar(r, e.apoio_flambagem); return r; }
    case "estrutura.cst": return cst(e);
    case "estrutura.euler": return euler(e.E, e.I, e.L, e.apoio, e.K);
    case "fluidos.ventilacao_natural": return ventilacaoNatural(e);
    case "fluidos.lbm": return lbm(e);
    case "fluidos.eolica_serie": return eolicaSerie(e);
    case "terreno.escoamento": return escoamento(e.grade);
    case "terreno.escoamento_scs": return escoamentoScs(e.grade, e.chuva_mm, e.usos, e.grupo);
    case "terreno.usle": return usle(e.grade, e.R, e.K, e.C, e.P, e.comprimento_m);
    case "terreno.visada": return visada(e.grade, e.i, e.j, e.altura_obs, e.altura_alvo);
    case "terreno.declividade_aspecto": return declividadeAspecto(e.grade);
    case "terreno.scs_cn": return { q_mm: scsCn(e.chuva_mm, e.cn) };
    case "incerteza.monte_carlo": return monteCarlo(e.entradas, e.modelo, e.n, e.semente);
    case "qubo.paineis": return qPaineis(e);
    case "qubo.rota": return qRota(e);
    case "qubo.topologia": return qTopologia(e);
    case "biogas.simular": return biogasSimular(e, c.fatores || null);
    case "biogas.fatores_carbono": return fatoresCarbono(e.F);
  }
  throw new Error("solver desconhecido: " + c.solver);
}
function pega(o, cam) { return String(cam).split(".").reduce(function (a, k) { return a == null ? undefined : a[k]; }, o); }
function igual(v, esp, tol) {
  if (typeof esp === "number") return typeof v === "number" && Math.abs(v - esp) <= tol.abs + tol.rel * Math.abs(esp);
  if (Array.isArray(esp)) return Array.isArray(v) && v.length === esp.length && esp.every(function (x, i) { return igual(v[i], x, tol); });
  if (esp && typeof esp === "object") return v && typeof v === "object" && Object.keys(esp).every(function (k) { return igual(v[k], esp[k], tol); });
  return v === esp;
}
/* confere cada caso: valores do Python (paridade) e valores analíticos (benchmark) */
function autoteste(casos) {
  casos = casos || (global.SIMULACAO_CASOS || {}).casos || []; var linhas = [], falhas = 0, ok = 0;
  if (global.SIMULACAO_CASOS && global.SIMULACAO_CASOS.fatores_base) CFG.fatores = global.SIMULACAO_CASOS.fatores_base;
  casos.forEach(function (c) {
    var r, t0 = Date.now();
    try { r = rodarCaso(c); } catch (e) { falhas++; linhas.push({ ok: false, nome: c.id, info: "erro: " + (e && e.message) }); return; }
    var tolP = c.tolerancia || { rel: 1e-7, abs: 1e-9 }, f = 0;
    Object.keys(c.python || {}).forEach(function (k) { var v = pega(r, k); if (!igual(v, c.python[k], tolP)) { f++; linhas.push({ ok: false, nome: c.id + " · paridade " + k, info: "Python " + JSON.stringify(c.python[k]).slice(0, 120) + " × JS " + JSON.stringify(v).slice(0, 120) }); } else ok++; });
    (c.analitico || []).forEach(function (a) { var v = pega(r, a.caminho), tol = { rel: a.tol_rel || 0, abs: a.tol_abs || 0 };
      var bom = nn(a.contem) ? JSON.stringify(v || "").indexOf(a.contem) >= 0 : igual(v, a.valor, tol);
      if (!bom) { f++; linhas.push({ ok: false, nome: c.id + " · analítico " + a.nome, info: "esperado " + JSON.stringify(a.valor) + ", calculado " + JSON.stringify(v) }); } else ok++; });
    if (!r || r.aviso !== AVISO && c.solver !== "terreno.scs_cn" && c.solver !== "biogas.fatores_carbono") { f++; linhas.push({ ok: false, nome: c.id + " · envelope", info: "sem aviso de pré-dimensionamento" }); }
    falhas += f; linhas.push({ ok: !f, nome: c.id + " (" + (Date.now() - t0) + " ms)", info: f ? f + " falha(s)" : "" });
  });
  return { ok: ok, falhas: falhas, linhas: linhas };
}

/* ══════════════ TELA ══════════════ */
var E = function (s) { return typeof esc === "function" ? esc(s) : String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
var fmt = function (v, c) { return v == null || !isFinite(v) ? "—" : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: c == null ? 2 : c, maximumFractionDigits: c == null ? 2 : c }); };
var RAMPA_CALOR = ["#EFE8D6", "#E5D5AE", "#C9A227", "#C08A1E", "#A85432", "#7A2214"];
var RAMPA_AGUA = ["#E3E8DE", "#C3D0BD", "#8FB183", "#546A7B", "#2F5E4E", "#3D2A5C"];
var RAMPA_AR = ["#EEF4EA", "#CDDCC4", "#A8BFA0", "#7FA874", "#4A8A5A", "#1A4D2E"];
function cor(v, a, b, rampa) { if (v == null || !isFinite(v)) return "#D9D3C2"; var t = b > a ? (v - a) / (b - a) : 0; t = Math.max(0, Math.min(0.9999, t)); return rampa[Math.floor(t * rampa.length)]; }
function legenda(a, b, rampa, un) { var cd = Math.abs(b - a) < 0.1 ? 3 : Math.abs(b - a) < 10 ? 2 : 1;
  return "<p class='t2 pq'>" + rampa.map(function (c, i) { var v0 = a + (b - a) * i / rampa.length; return "<span style='display:inline-flex;align-items:center;gap:4px;margin-right:8px'><svg width='14' height='14' aria-hidden='true'><rect width='14' height='14' fill='" + c + "' stroke='#8A9182'/></svg>" + fmt(v0, cd) + "</span>"; }).join("") + E(un) + "</p>"; }
function svgCampo(id, titulo, desc, nx, ny, vals, M, rampa, un, logar) {
  var cel = Math.min(480 / nx, 360 / ny), W = cel * nx, H = cel * ny, cw = cel, ch = cel, vv = [], i, j, s;
  for (s = 0; s < nx * ny; s++) if ((!M || M[s]) && vals[s] != null && isFinite(vals[s])) vv.push(logar ? Math.log(1 + vals[s]) : vals[s]);
  var a = vv.length ? Math.min.apply(null, vv) : 0, b = vv.length ? Math.max.apply(null, vv) : 1, r = [];
  for (i = 0; i < ny; i++) for (j = 0; j < nx; j++) { s = i * nx + j; var v = (M && !M[s]) ? null : vals[s]; r.push("<rect x='" + (j * cw).toFixed(2) + "' y='" + (i * ch).toFixed(2) + "' width='" + (cw + 0.3).toFixed(2) + "' height='" + (ch + 0.3).toFixed(2) + "' fill='" + (v == null ? "#FAF9F5" : cor(logar ? Math.log(1 + v) : v, a, b, rampa)) + "'/>"); }
  return "<figure style='margin:0'><svg id='" + id + "' viewBox='0 0 " + W + " " + H.toFixed(1) + "' width='100%' style='max-width:" + W + "px' role='img' aria-labelledby='" + id + "-t " + id + "-d'><title id='" + id + "-t'>" + E(titulo) + "</title><desc id='" + id + "-d'>" + E(desc) + "</desc>" + r.join("") + "</svg>"
    + legenda(logar ? Math.exp(a) - 1 : a, logar ? Math.exp(b) - 1 : b, rampa, (logar ? " (escala logarítmica) " : " ") + un) + "</figure>";
}
function svgEstrutura(id, titulo, nos, els, desl, escalaPedida) {
  var xs = nos.map(function (n) { return n[0]; }), ys = nos.map(function (n) { return n[1]; }), x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs), y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
  var L = Math.max(x1 - x0, y1 - y0) || 1, dmax = 0; desl.forEach(function (d) { dmax = Math.max(dmax, Math.sqrt(d[0] * d[0] + d[1] * d[1])); });
  var esc = escalaPedida || (dmax > 0 ? 0.1 * L / dmax : 1), W = 480, H = 320, m = 30, sx = (W - 2 * m) / L, P = function (x, y) { return [(m + (x - x0) * sx).toFixed(1), (H - m - (y - y0) * sx).toFixed(1)]; };
  var lin = els.map(function (e) { var a = P(nos[e.i][0], nos[e.i][1]), b = P(nos[e.j][0], nos[e.j][1]); return "<line x1='" + a[0] + "' y1='" + a[1] + "' x2='" + b[0] + "' y2='" + b[1] + "' stroke='#8A9182' stroke-width='2' stroke-dasharray='5 4'/>"; }).join("");
  var def = els.map(function (e) { var a = P(nos[e.i][0] + esc * desl[e.i][0], nos[e.i][1] + esc * desl[e.i][1]), b = P(nos[e.j][0] + esc * desl[e.j][0], nos[e.j][1] + esc * desl[e.j][1]);
    return "<line x1='" + a[0] + "' y1='" + a[1] + "' x2='" + b[0] + "' y2='" + b[1] + "' stroke='#A85432' stroke-width='3'/>"; }).join("");
  return "<figure style='margin:0'><svg id='" + id + "' viewBox='0 0 " + W + " " + H + "' width='100%' style='max-width:" + W + "px' role='img' aria-labelledby='" + id + "-t'><title id='" + id + "-t'>" + E(titulo + " — tracejado: original; cheio: deformada × " + fmt(esc, 0)) + "</title>" + lin + def + "</svg><figcaption class='t2 pq'>Tracejado cinza: forma original. Linha cheia: deformada ampliada " + fmt(esc, 0) + " vezes.</figcaption></figure>";
}
function svgCst(id, titulo, nos, tris, desl, tens) {
  var xs = nos.map(function (n) { return n[0]; }), ys = nos.map(function (n) { return n[1]; }), x0 = Math.min.apply(null, xs), y0 = Math.min.apply(null, ys), L = Math.max(Math.max.apply(null, xs) - x0, Math.max.apply(null, ys) - y0) || 1;
  var dmax = 0; desl.forEach(function (d) { dmax = Math.max(dmax, Math.sqrt(d[0] * d[0] + d[1] * d[1])); });
  var esc = dmax > 0 ? 0.08 * L / dmax : 1, W = 480, H = 320, m = 20, sx = (W - 2 * m) / L, vm = tens.map(function (t) { return t.von_mises; }), a = Math.min.apply(null, vm), b = Math.max.apply(null, vm);
  var P = function (k) { return ((m + (nos[k][0] + esc * desl[k][0] - x0) * sx).toFixed(1)) + "," + ((H - m - (nos[k][1] + esc * desl[k][1] - y0) * sx).toFixed(1)); };
  var pol = tris.map(function (t, i) { return "<polygon points='" + P(t[0]) + " " + P(t[1]) + " " + P(t[2]) + "' fill='" + cor(vm[i], a, b, RAMPA_CALOR) + "' stroke='#D9D3C2' stroke-width='0.3'/>"; }).join("");
  return "<figure style='margin:0'><svg id='" + id + "' viewBox='0 0 " + W + " " + H + "' width='100%' style='max-width:" + W + "px' role='img' aria-labelledby='" + id + "-t'><title id='" + id + "-t'>" + E(titulo) + "</title>" + pol + "</svg>" + legenda(a / 1e6, b / 1e6, RAMPA_CALOR, "MPa (von Mises)") + "<figcaption class='t2 pq'>Deformada ampliada " + fmt(esc, 0) + " vezes.</figcaption></figure>";
}
function svgBarras(id, titulo, rot, vals, un) {
  var W = 480, H = 200, m = 30, mx = Math.max.apply(null, vals.concat([1e-9])), bw = (W - 2 * m) / vals.length;
  var r = vals.map(function (v, i) { var h = (H - 2 * m) * v / mx; return "<rect x='" + (m + i * bw + 2).toFixed(1) + "' y='" + (H - m - h).toFixed(1) + "' width='" + (bw - 4).toFixed(1) + "' height='" + h.toFixed(1) + "' fill='#4A8A5A'/><text x='" + (m + i * bw + bw / 2).toFixed(1) + "' y='" + (H - m + 14) + "' font-size='10' text-anchor='middle' fill='currentColor'>" + E(rot[i]) + "</text>"; }).join("");
  return "<figure style='margin:0'><svg id='" + id + "' viewBox='0 0 " + W + " " + H + "' width='100%' style='max-width:" + W + "px' role='img' aria-labelledby='" + id + "-t'><title id='" + id + "-t'>" + E(titulo + " (máximo " + fmt(mx, 1) + " " + un + ")") + "</title>" + r + "</svg></figure>";
}
function svgLinha(id, titulo, ys, un) {
  var W = 480, H = 200, m = 30, a = Math.min.apply(null, ys), b = Math.max.apply(null, ys); if (b === a) b = a + 1;
  var pts = ys.map(function (y, i) { return (m + (W - 2 * m) * i / Math.max(1, ys.length - 1)).toFixed(1) + "," + (H - m - (H - 2 * m) * (y - a) / (b - a)).toFixed(1); }).join(" ");
  return "<figure style='margin:0'><svg id='" + id + "' viewBox='0 0 " + W + " " + H + "' width='100%' style='max-width:" + W + "px' role='img' aria-labelledby='" + id + "-t'><title id='" + id + "-t'>" + E(titulo + " — de " + fmt(a, 2) + " a " + fmt(b, 2) + " " + un) + "</title><polyline points='" + pts + "' fill='none' stroke='#546A7B' stroke-width='2'/></svg></figure>";
}
function tabelaKV(cap, linhas) { return "<div class='rolagem'><table><caption>" + E(cap) + "</caption><tbody>" + linhas.map(function (l) { return "<tr><th scope='row'>" + E(l[0]) + "</th><td>" + l[1] + "</td></tr>"; }).join("") + "</tbody></table></div>"; }
function envelopeHtml(r) {
  if (!r) return "";
  var prem = (r.premissas_usadas || []).map(function (p) { return "<li><code>" + E(p.id) + "</code> (" + E(p.status) + ")</li>"; }).join("");
  return "<details><summary>Método, hipóteses, premissas e limites</summary><p><strong>Método:</strong> " + E(r.metodo) + "</p><p><strong>Malha/grade:</strong> " + E(JSON.stringify(r.malha)) + "</p><ul>" + (r.hipoteses || []).map(function (h) { return "<li>" + E(h) + "</li>"; }).join("") + "</ul>"
    + (prem ? "<p><strong>Premissas usadas:</strong></p><ul>" + prem + "</ul>" : "") + "<p><strong>Limites de validade:</strong> " + E(r.limites_validade) + "</p></details>"
    + ((r.avisos || []).length ? "<div class='faixa at' role='note'><ul>" + r.avisos.map(function (a) { return "<li>" + E(a) + "</li>"; }).join("") + "</ul></div>" : "")
    + "<p class='faixa in' role='note'>" + E(r.aviso) + "</p>";
}
/* desenho de um resultado conforme o tipo de solver */
function desenhoCaso(c, r, id) {
  var e = c.entrada, s = c.solver;
  if (s === "estrutura.portico" && (e.dim || 2) === 2) return svgEstrutura(id, c.nome, e.nos, e.elementos, r.deslocamentos)
    + tabelaKV("Resultados principais", [["Deslocamento máximo", fmt(r.desl_max * 1000, 3) + " mm"], ["Maior tensão normal", fmt(Math.max.apply(null, r.elementos.map(function (x) { return x.sigma_max; })) / 1e6, 2) + " MPa"]].concat(r.verificacao ? [["Verificação", r.verificacao.todos_ok ? "todos os elementos passam" : "há elemento acima do limite ou sem dado ([MARCADOR])"]] : []));
  if (s === "estrutura.cst") return svgCst(id, c.nome, e.nos, e.tris, r.deslocamentos, r.tensoes) + tabelaKV("Resultados principais", [["Deslocamento máximo", fmt(r.desl_max * 1000, 4) + " mm"], ["Von Mises máxima", fmt(r.von_mises_max / 1e6, 3) + " MPa"]]);
  if (s === "termica.placa_2d") return svgCampo(id, c.nome, "Campo de temperatura do corte", e.nx, e.ny, r.T, e.mascara, RAMPA_CALOR, "°C") + tabelaKV("Resultados principais", [["Temperatura mínima", fmt(r.t_min, 2) + " °C"], ["Temperatura máxima", fmt(r.t_max, 2) + " °C"]].concat(Object.keys(r.fluxos_w_por_m).map(function (k) { return ["Fluxo saindo por " + k, fmt(r.fluxos_w_por_m[k], 2) + " W/m"]; })));
  if (s === "termica.transiente_1d") return svgLinha(id, "Fluxo de calor na face interna ao longo do tempo", r.serie.map(function (x) { return x.q_int; }), "W/m²") + tabelaKV("Resultados principais", [["U", fmt(r.u, 3) + " W/m²K"], ["Atraso térmico", fmt(r.atraso_h, 1) + " h"], ["Fator de amortecimento", fmt(r.amortecimento, 3)]]);
  if (s === "termica.u_composicao" || s === "termica.u_valor") return tabelaKV("Transmitância", [["U calculado", fmt(r.u, 3) + " W/m²K"], ["U da base", fmt(r.u_base, 3)], ["Capacidade térmica", fmt(r.ct_kj_m2k, 1) + " kJ/m²K"], ["Carbono incorporado", r.carbono_kgco2e_m2 == null ? MARCADOR : fmt(r.carbono_kgco2e_m2, 1) + " kgCO₂e/m²"]]);
  if (s === "terreno.escoamento") return svgCampo(id, c.nome, "Acumulação de fluxo (células a montante)", e.grade.nx, e.grade.ny, r.acumulacao, null, RAMPA_AGUA, "células", true) + tabelaKV("Resultados", [["Depressões (sem saída)", String(r.sumidouros)]]);
  if (s === "terreno.escoamento_scs") return svgCampo(id, c.nome, "Volume de enxurrada acumulado", e.grade.nx, e.grade.ny, r.volume_acumulado_m3, null, RAMPA_AGUA, "m³", true) + tabelaKV("Resultados", [["Chuva do evento", fmt(r.chuva_mm, 0) + " mm"], ["Volume total escoado", fmt(r.volume_total_m3, 1) + " m³"]]);
  if (s === "fluidos.lbm") return svgCampo(id, c.nome + " (qualitativo, Fase 1)", "Velocidade do ar em unidades de rede; o bloco cinza claro é o obstáculo", e.nx, e.ny,
      r.vel.map(function (_, k) { var y = Math.floor(k / e.nx), x = k - y * e.nx; return r.vel[(e.ny - 1 - y) * e.nx + x]; }),
      (e.obstaculo || []).length ? r.vel.map(function (_, k) { var y = Math.floor(k / e.nx), x = k - y * e.nx; return e.obstaculo[(e.ny - 1 - y) * e.nx + x] ? 0 : 1; }) : null, RAMPA_AR, "u (rede)")
    + "<p class='faixa at' role='note'>Qualitativo, Fase 1: mostra esteira e aceleração, não números de projeto.</p>";
  if (s === "terreno.usle") return svgCampo(id, c.nome, "Perda de solo por célula", e.grade.nx, e.grade.ny, r.perda_t_ha_ano, null, RAMPA_CALOR, "t/ha·ano", true) + tabelaKV("Resultados", [["Média", fmt(r.media, 2) + " t/ha·ano"], ["Máxima", fmt(r.maxima, 2) + " t/ha·ano"]]);
  if (s === "terreno.visada") return svgCampo(id, c.nome, "Células visíveis (escuro) e escondidas (claro)", e.grade.nx, e.grade.ny, r.visivel, null, [RAMPA_AR[0], RAMPA_AR[5]], "0 = escondida, 1 = visível") + tabelaKV("Resultados", [["Parte visível", fmt(100 * r.fracao_visivel, 0) + " %"]]);
  if (s === "terreno.declividade_aspecto") return svgCampo(id, c.nome, "Declividade por célula", e.grade.nx, e.grade.ny, r.declividade_graus, null, RAMPA_CALOR, "graus");
  if (s === "fluidos.eolica_serie") return tabelaKV("Energia", [["Pela série", fmt(r.kwh_serie, 1) + " kWh"], ["Pela Weibull ajustada", fmt(r.kwh_weibull, 1) + " kWh"], ["k e c da Weibull", fmt(r.k, 2) + " e " + fmt(r.c, 2) + " m/s"], ["Vento médio no cubo", fmt(r.v_media_cubo, 2) + " m/s"]]);
  if (s === "fluidos.ventilacao_natural") return tabelaKV("Vazão", [["Chaminé", fmt(r.q_chamine_m3s, 3) + " m³/s"], ["Vento", fmt(r.q_vento_m3s, 3) + " m³/s"], ["Combinada", fmt(r.q_m3s, 3) + " m³/s"], ["Trocas de ar", fmt(r.trocas_h, 1) + " por hora"]]);
  if (s === "incerteza.monte_carlo") return tabelaKV("Faixa (percentis)", [["Média", fmt(r.media, 2)]].concat(Object.keys(r.percentis).map(function (k) { return ["P" + k, fmt(r.percentis[k], 2)]; })));
  if (s.indexOf("qubo.") === 0) return tabelaKV("Solução clássica", [["Método", E(r.solucao.metodo)], ["Energia do QUBO", fmt(r.solucao.energia, 3)], ["Resposta", E(JSON.stringify(r.escolhidas || r.arestas || r.celulas))]]) + "<p class='faixa at' role='note'>" + E(AVISO_QUANTICO) + "</p>";
  if (s === "biogas.simular") return svgBarras(id, "Biogás por mês", ["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"], r.mensal.map(function (m) { return m.biogas_m3; }), "m³")
    + tabelaKV("Resultados principais", [["Biogás", fmt(r.biogas_m3_dia, 2) + " m³/dia"], ["Metano", fmt(r.ch4_m3_dia, 2) + " m³/dia (faixa P5–P95: " + fmt(r.faixa_ch4_m3_dia["5"], 2) + " a " + fmt(r.faixa_ch4_m3_dia["95"], 2) + ")"],
      ["TRH", fmt(r.trh_dias, 1) + " dias"], ["Carga orgânica", fmt(r.cov_kg_sv_m3_dia, 2) + " kg SV/m³·dia"], ["Energia térmica", fmt(r.energia.termica_kwh_dia, 1) + " kWh/dia"],
      ["Gerador (P, Q, S, FP)", fmt(r.gerador.p_kw, 2) + " kW, " + fmt(r.gerador.q_kvar, 2) + " kvar, " + fmt(r.gerador.s_kva, 2) + " kVA, FP " + fmt(r.gerador.fp, 2) + " (" + r.gerador.fp_fonte + ")"],
      ["GLP equivalente", fmt(r.energia.glp_kg_dia, 2) + " kg/dia"], ["Horas de queimador", fmt(r.energia.horas_queimador_dia, 1) + " h/dia"], ["CO₂e evitado (total)", fmt(r.evitadas_t_ano.total, 2) + " t/ano"]]);
  return "<pre style='white-space:pre-wrap;word-break:break-all'>" + E(JSON.stringify(r).slice(0, 1500)) + "</pre>";
}
var ESTADO = { sel: null, entrada: null, res: null, erro: "" };
function U() { return typeof ui !== "undefined" && ui ? (ui.sim = ui.sim || ESTADO) : ESTADO; }
function casosDisponiveis() { return ((global.SIMULACAO_CASOS || {}).casos || []).filter(function (c) { return c.exemplo; }); }
function telaSimulacao() {
  var st = U(), cs = casosDisponiveis(), c = cs.filter(function (x) { return x.id === st.sel; })[0] || cs[0];
  var h = "<h1>Simulação (Fase 1)</h1><p class='t2'>Contas leves que rodam aqui mesmo, sem internet: calor em paredes e peças, estrutura (treliça, pórtico, chapa), ventilação natural, escoamento de ar qualitativo, terreno e enxurrada, faixas de incerteza, otimização em QUBO e biogás. Todo resultado é pré-dimensionamento para revisão do engenheiro.</p>";
  if (!c) return h + "<p class='faixa in' role='note'>Exemplos não carregados (sistema/simulacao-exemplos/casos.js).</p>";
  if (st.sel !== c.id || st.entrada == null) { st.sel = c.id; st.entrada = JSON.stringify(c.entrada, null, 1); st.res = null; st.erro = ""; }
  var r = st.res; if (!r && !st.erro) { try { r = rodarCaso(c); st.res = r; } catch (e) { st.erro = e.message; } }
  h += "<section class='cartao' aria-labelledby='h-sim-ex'><h2 id='h-sim-ex'>Exemplos (dados fictícios)</h2><div><label for='sim-sel'>Exemplo</label> <select id='sim-sel' data-sim-acao='sel'>"
    + cs.map(function (x) { return "<option value='" + E(x.id) + "'" + (x.id === c.id ? " selected" : "") + ">" + E(x.nome) + "</option>"; }).join("") + "</select></div><p class='t2'>" + E(c.descricao || "") + "</p><p class='faixa in' role='note'>Exemplo / dados fictícios.</p></section>";
  h += "<section class='cartao' aria-labelledby='h-sim-res'><h2 id='h-sim-res'>" + E(c.nome) + "</h2>" + (st.erro ? "<div class='faixa al' role='alert'>" + E(st.erro) + "</div>" : desenhoCaso(c, r, "sim-fig") + envelopeHtml(r)) + "</section>";
  h += "<section class='cartao' aria-labelledby='h-sim-ent'><h2 id='h-sim-ent'>Entrada (JSON)</h2><label for='sim-json'>Entrada do exemplo; mude e rode de novo</label><textarea id='sim-json' rows='8' style='width:100%' spellcheck='false'>" + E(st.entrada) + "</textarea>"
    + "<p><button type='button' data-sim-acao='rodar' id='sim-b-rodar'>Rodar de novo</button> <button type='button' data-sim-acao='repor' id='sim-b-repor'>Voltar ao exemplo</button> <span role='status' id='sim-msg' class='t2'></span></p></section>";
  return "<div id='sim-raiz'>" + h + "</div>";
}
function redesenhar() { if (typeof desenhar === "function") { desenhar(); return; } var r = typeof document !== "undefined" && document.getElementById("sim-raiz"); if (r) r.outerHTML = telaSimulacao(); }
if (typeof document !== "undefined" && !global.__simEventos) {
  global.__simEventos = true;
  document.addEventListener("change", function (ev) { var t = ev.target; if (t && t.getAttribute && t.getAttribute("data-sim-acao") === "sel") { var st = U(); st.sel = t.value; st.entrada = null; redesenhar(); var s = document.getElementById("sim-sel"); if (s) s.focus(); } });
  document.addEventListener("click", function (ev) {
    var b = ev.target && ev.target.closest ? ev.target.closest("[data-sim-acao]") : null; if (!b || b.tagName === "SELECT") return;
    var st = U(), a = b.getAttribute("data-sim-acao"), c = casosDisponiveis().filter(function (x) { return x.id === st.sel; })[0]; if (!c) return;
    if (a === "repor") { st.entrada = null; st.res = null; st.erro = ""; }
    if (a === "rodar") { var ta = document.getElementById("sim-json"); st.entrada = ta ? ta.value : st.entrada;
      try { var c2 = JSON.parse(JSON.stringify(c)); c2.entrada = JSON.parse(st.entrada); st.res = rodarCaso(c2); st.erro = ""; } catch (e) { st.res = null; st.erro = (e.faltaDado ? "" : "Entrada inválida: ") + e.message; } }
    redesenhar(); var f = document.getElementById(a === "rodar" ? "sim-b-rodar" : "sim-b-repor"); if (f) f.focus();
  });
}
/* cartão para outra aba: SIMULACAO.painel("biogas", entrada) etc. Devolve HTML com h2 (a aba dona já tem o h1). */
var PAINEIS = { u: ["termica.u_composicao", "Transmitância (U) da parede ou cobertura"], parede: ["termica.transiente_1d", "Inércia térmica da parede (atraso e amortecimento)"],
  ponte: ["termica.placa_2d", "Ponte térmica (corte 2D)"], estrutura: ["estrutura.portico", "Estrutura (treliça ou pórtico)"],
  ventilacao: ["fluidos.ventilacao_natural", "Ventilação natural"], lbm: ["fluidos.lbm", "Escoamento do ar (qualitativo, Fase 1)"], eolica: ["fluidos.eolica_serie", "Energia da turbina pela série de vento"],
  escoamento: ["terreno.escoamento", "Caminho da água no terreno (D8)"], enxurrada: ["terreno.escoamento_scs", "Enxurrada do evento de chuva (SCS-CN)"], erosao: ["terreno.usle", "Perda de solo (USLE)"],
  incerteza: ["incerteza.monte_carlo", "Faixa de incerteza (Monte Carlo)"], paineis: ["qubo.paineis", "Escolha de posições de placas (QUBO)"], biogas: ["biogas.simular", "Biodigestor: produção de biogás"] };
function painel(tipo, entrada, idBase) {
  var p = PAINEIS[tipo]; if (!p) return "";
  var id = idBase || ("sim-p-" + tipo), c = { id: id, nome: p[1], solver: p[0], entrada: entrada }, r;
  try { r = rodarCaso(c); } catch (e) { return "<section class='cartao' aria-labelledby='" + id + "-h'><h2 id='" + id + "-h'>" + E(p[1]) + "</h2><div class='faixa at' role='note'>" + E(e.message) + "</div></section>"; }
  return "<section class='cartao' aria-labelledby='" + id + "-h'><h2 id='" + id + "-h'>" + E(p[1]) + "</h2>" + desenhoCaso(c, r, id + "-fig") + envelopeHtml(r) + "</section>";
}

global.SIMULACAO = {
  AVISO: AVISO, PREMISSAS: PREM, premissa: premissa, configurar: function (o) { if (o.materiais) CFG.materiais = o.materiais; if (o.fatores) CFG.fatores = o.fatores; },
  comum: { Rng: Rng, tridiagonal: tridiagonal, percentil: percentil, resolverBanda: resolverBanda },
  termica: { uValor: uValor, uComposicao: uComposicao, perdaEnvoltoria: perdaEnvoltoria, transiente1d: transiente1d, placa2d: placa2d, placaAnalitica: placaAnalitica,
    hConveccaoVento: hConveccaoVento, hRadiacao: hRadiacao, solAr: solAr, mascaraDeSegmentos: mascaraDeSegmentos, poligonosParaSegmentos: poligonosParaSegmentos },
  estrutura: { secao: secao, portico: portico, euler: euler, verificar: verificar, cargaVento: cargaVento, empuxoRotor: empuxoRotor, malhaDeMascara: malhaDeMascara, cst: cst },
  fluidos: { ventilacaoNatural: ventilacaoNatural, lbm: lbm, eolicaSerie: eolicaSerie, weibullMomentos: weibullMomentos },
  terreno: { gradeDoMapeamento: gradeDoMapeamento, gradeDaGeometria: gradeDaGeometria, declividadeAspecto: declividadeAspecto, d8: d8, acumulacao: acumulacao, escoamento: escoamento, scsCn: scsCn, escoamentoScs: escoamentoScs, usle: usle, visada: visada },
  incerteza: { monteCarlo: monteCarlo, sortear: sortear, MODELOS: MODELOS },
  qubo: { novo: qNovo, soma: qSoma, energia: qEnergia, exato: qExato, recozimento: qRecozimento, resolver: qResolver, paineis: qPaineis, rota: qRota, topologia: qTopologia, exportar: qExportar, AVISO: AVISO_QUANTICO },
  biogas: { simular: biogasSimular, fatoresCarbono: fatoresCarbono, kTemperatura: kTemperatura, fracaoBmp: fracaoBmp },
  rodarCaso: rodarCaso, autoteste: autoteste, painel: painel, desenhoCaso: desenhoCaso
};
global.telaSimulacao = telaSimulacao;
global.SIMULACAO_I18N = {
  "Simulação (Fase 1)": "Simulation (Phase 1)", "Exemplos (dados fictícios)": "Examples (fictitious data)", "Exemplo": "Example", "Entrada (JSON)": "Input (JSON)",
  "Rodar de novo": "Run again", "Voltar ao exemplo": "Back to the example", "Exemplo / dados fictícios.": "Example / fictitious data.",
  "Método, hipóteses, premissas e limites": "Method, assumptions, premises and limits", "Resultados principais": "Main results",
  "Biodigestor: produção de biogás": "Digester: biogas production", "Transmitância (U) da parede ou cobertura": "Wall or roof thermal transmittance (U)",
  "Caminho da água no terreno (D8)": "Water path on the terrain (D8)", "Escoamento do ar (qualitativo, Fase 1)": "Airflow (qualitative, Phase 1)"
};
})(typeof window !== "undefined" ? window : this);
