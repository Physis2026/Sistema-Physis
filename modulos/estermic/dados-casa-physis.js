/* dados-casa-physis.js — VERSÃO DE TESTE (21/11/2026). Conjunto "DADOS CASA PHYSIS (revisão interna)" para a revisão do Ryan
   (23/11 às 13h59) se os dados da Estermic não chegarem até 22/11 (decisão da dona de 21/11).
   Regra: só dados dos documentos técnicos reais da Casa Physis, com a fonte em cada linha. O que falta fica [MARCADOR];
   área sem fonte fica sem número (null). Nada aqui é dado da Estermic.
   Fontes (pasta Casa Physis):
   [F1] 1_Tecnico_Casa_Physis/Editaveis/03_Planilha_Tecnica.xlsx — folhas Levantamento, Premissas, Implantação, Aquecimento
   [F2] 1_Tecnico_Casa_Physis/Editaveis/01_Memorial_Tecnico.docx — seções 5 (Arquitetura) e 10 (Conforto e insolação)
   [F3] 1_Tecnico_Casa_Physis/Editaveis/18_Equipamentos_e_Consumo.xlsx — folha Equipamentos
   [F4] Estratégia Geral - Casa Physis - Physis Engineering - Instituto - InovaSTEM/Documento Técnico Instituto Physis (OSC ICT) e Lote 168.docx — seção 4
   [F5] 1_Tecnico_Casa_Physis/Editaveis/10_Casa_1.docx
   Contrato: window.ESTERMIC_CONJUNTOS["casa-physis"]() -> estado completo para ESTERMIC.normalizar (precisa de estermic-avac.js antes). */
(function (global) {
"use strict";
const F1 = "03_Planilha_Tecnica.xlsx", F2 = "01_Memorial_Tecnico.docx", F3 = "18_Equipamentos_e_Consumo.xlsx", F4 = "Documento Técnico Instituto Physis (OSC ICT) e Lote 168.docx", F5 = "10_Casa_1.docx";
/* contas do módulo AVAC desligadas: o projeto dispensa ar-condicionado [F2 §10] e os documentos não trazem as entradas dos outros
   módulos (população por dormitório, consumo de água quente por pessoa, vazões); as listas do exemplo da planilha são esvaziadas
   para nenhum número do exemplo aparecer */
const avacSemExemplo = nome => ({ e:{ controle:{ nome, local:"Petrópolis / RJ", ativo:{ ac:false, vent:false, press:false, solar:false, piscina:false, dutos:false, lista:false, quadro:false } },
  tipologias:{ lista:[] }, ac:{ amb:[] }, vent:{ outros:[] }, dutos:{ sistemas:[] } } });
const local = { endereco:"Lote 168, Parque Bom Clima (APA Petrópolis)", municipio:"Petrópolis", uf:"RJ", lat:null, lon:null, altitude:null };
function eq(E, tag, sistema, descricao, qtd, potW, fonte) {
  return { tag, origem:"casa-physis", sistema, descricao, qtd, cap:potW == null ? null : potW / 1000, un:"kW", categoria:"", fabricante:"", modelo:"", baseId:"",
    fonte, pecas:E.pecasPadrao(sistema) }; }
function conjuntoCasaPhysis() {
  const E = global.ESTERMIC; if (!E) throw new Error("carregue estermic-avac.js antes");
  const fases = () => E.FASES_PADRAO.map(E.faseVazia);
  const sub = (id, nome, escopo, extra) => Object.assign({ id, nome, escopo, contrato:{ numero:"", valor:null, assinatura:"", prazoFinal:"", condicoes:"", iss:"" },
    fases:fases(), local:Object.assign({}, local), dados:{ avac:avacSemExemplo(nome) }, dadosConfirmados:false }, extra);
  return {
    versao:1, teste:true,
    cliente:{ id:"casa-physis", nome:"Casa Physis (dados de revisão interna)", cnpj:"", contato:"", email:"",
      explicacao:"Casa Physis no Lote 168: casa (Zona 1), área do Instituto com LAB, MEC e restaurante (Zona 2) e hospedagem em lofts (Zona 3). Conjunto usado só para a revisão interna do módulo; não é cliente." },
    marcaCliente:{ nome:"Casa Physis — revisão interna", logoPng:null, fonteTitulo:"", fonteTexto:"", corPrincipal:"", corTexto:"", corLinha:"" },
    conjunto:{ id:"casa-physis", rotulo:"DADOS CASA PHYSIS (revisão interna)",
      fontes:["[F1] Casa Physis/1_Tecnico_Casa_Physis/Editaveis/" + F1 + " (folhas Levantamento, Premissas, Implantação, Aquecimento)",
        "[F2] Casa Physis/1_Tecnico_Casa_Physis/Editaveis/" + F2 + " (seções 5 e 10)",
        "[F3] Casa Physis/1_Tecnico_Casa_Physis/Editaveis/" + F3 + " (folha Equipamentos)",
        "[F4] Casa Physis/Estratégia Geral/" + F4 + " (seção 4)",
        "[F5] Casa Physis/1_Tecnico_Casa_Physis/Editaveis/" + F5],
      premissas:[
        { t:"Lote 168, Parque Bom Clima, Petrópolis (RJ), APA Petrópolis; área do RGI 1.216 m² (usada nos índices); novo levantamento 1.455,95 m²", fonte:"[F1] Levantamento; [F4] §4" },
        { t:"Altitude ≈ 880 m; 432 graus-dia de aquecimento e 26 de resfriamento por ano", fonte:"[F2] §10" },
        { t:"O projeto dispensa ar-condicionado: ventilação cruzada, sombreamento, isolamento dos contêineres e bomba de calor reversível para as noites frias de maio a agosto", fonte:"[F2] §10" },
        { t:"Água quente por aquecedor solar (coletores ao norte, 25°) desde a primeira fase, com bomba de calor nos meses frios; fração solar do ano 0,918", fonte:"[F1] Aquecimento; [F2] §9" },
        { t:"Demanda anual de água quente: casa 3.282 kWh; hospedagem (7 unidades) 12.259 kWh; restaurante e funcionários 2.675 kWh", fonte:"[F1] Aquecimento" },
        { t:"Coordenadas geográficas do lote: não encontradas nos documentos [MARCADOR]", fonte:"—" }] },
    subprojetos:[
      sub("sp1", "Casa 1 (Zona 1)", "Casa para 6 moradores em contêineres: térreo com 2 contêineres de 40 pés (sala, cozinha e suíte acessível) e andar de cima com 2 contêineres de 20 pés em L; gourmet coberta, área comum e deck.", {
        ambientes:[
          { nome:"Térreo: sala, cozinha e suíte acessível (2 contêineres de 40 pés)", area:null, ocupacao:"6 moradores (casa)", fonte:"[F2] §5; [F1] Premissas" },
          { nome:"Andar de cima (2 contêineres de 20 pés em L)", area:null, ocupacao:"[MARCADOR]", fonte:"[F2] §5" },
          { nome:"Área comum integrada", area:136, ocupacao:"[MARCADOR]", fonte:"[F1] Implantação" },
          { nome:"Gourmet coberta", area:20.7, ocupacao:"[MARCADOR]", fonte:"[F1] Implantação" },
          { nome:"Deck", area:46.2, ocupacao:"[MARCADOR]", fonte:"[F1] Implantação" }],
        premissas:[{ t:"Moradores da casa: 6", fonte:"[F1] Premissas" }],
        alternativas:[
          { nome:"Sem ar-condicionado (adotada no estudo)", descricao:"Ventilação cruzada, sombreamento, isolamento dos contêineres, ventiladores de teto e bomba de calor reversível nas noites frias", fonte:"[F2] §10; [F3]" },
          { nome:"Casa modelo C (alternativa de arquitetura)", descricao:"Alvenaria leve, telhado de uma água ao norte; pavimento superior com suíte de 17,6 m², banho de 7,8 m², closet de 4,7 m²; área ≈ 61 m²", fonte:"[F2] §5; [F5]" }],
        equipamentos:[] }),
      sub("sp2", "LAB e MEC (Zona 2)", "Superbloco com dois edifícios de 2 contêineres de 20 pés em T: LAB (escritório multiuso; servidor, eletrônica, 3D, cosméticos e destilação em área limpa) e MEC (oficina; escritório e atelier).", {
        ambientes:[
          { nome:"LAB inferior: escritório multiuso", area:14.8, ocupacao:"8 lugares de dia, 4 camas à noite", fonte:"[F1] Implantação; [F2] §5" },
          { nome:"LAB superior: servidor, eletrônica, 3D e área limpa", area:14.8, ocupacao:"[MARCADOR]", fonte:"[F1] Implantação; [F2] §5" },
          { nome:"MEC inferior: oficina", area:14.8, ocupacao:"[MARCADOR]", fonte:"[F1] Implantação; [F2] §5" },
          { nome:"MEC superior: escritório e atelier", area:14.8, ocupacao:"[MARCADOR]", fonte:"[F1] Implantação; [F2] §5" }],
        premissas:[{ t:"Impressoras 3D no LAB superior com exaustão; exaustor na área limpa; exaustor de solda na oficina", fonte:"[F3]" }],
        alternativas:[], equipamentos:[] }),
      sub("sp3", "Restaurante e apoio (Zona 2)", "Restaurante circular em bioconstrução (cozinha de Ø 5,0 m com cobertura cônica, exaustão, fogão a biogás e indução), dois decks em arco, apoio de funcionários e lavabos.", {
        ambientes:[
          { nome:"Restaurante circular (cozinha Ø 5,0 m)", area:19.6, ocupacao:"[MARCADOR]", fonte:"[F1] Implantação; [F2] §5" },
          { nome:"Deck 1 em arco (coberto)", area:9.9, ocupacao:"[MARCADOR]", fonte:"[F1] Implantação" },
          { nome:"Deck 2 em arco", area:9.9, ocupacao:"[MARCADOR]", fonte:"[F1] Implantação" },
          { nome:"Apoio de funcionários", area:4.9, ocupacao:"4 funcionários (lote)", fonte:"[F1] Implantação; [F1] Premissas" },
          { nome:"2 lavabos", area:3, ocupacao:"[MARCADOR]", fonte:"[F1] Implantação" }],
        premissas:[{ t:"Coifa com exaustão e filtro de gordura na cozinha (NBR 14518)", fonte:"[F3]" }],
        alternativas:[], equipamentos:[] }),
      sub("sp4", "Hospedagem em lofts (Zona 3)", "Lofts de bioconstrução com banho, mini-cozinha e varanda lateral de 1,0 m: de 16 m² acessíveis (cama no térreo) e de 20 m² com mezanino.", {
        ambientes:[
          { nome:"Loft 1 (4 × 4)", area:16, ocupacao:"4 hóspedes", fonte:"[F1] Implantação; [F1] Premissas" },
          { nome:"Loft 2 (4 × 4)", area:16, ocupacao:"4 hóspedes", fonte:"[F1] Implantação; [F1] Premissas" },
          { nome:"Loft 3 (4 × 4, PCD)", area:16, ocupacao:"4 hóspedes", fonte:"[F1] Implantação; [F1] Premissas" },
          { nome:"Loft 4 (4 × 5, PCD)", area:20, ocupacao:"4 hóspedes", fonte:"[F1] Implantação; [F1] Premissas" },
          { nome:"Loft 5 (4 × 5, PCD)", area:20, ocupacao:"4 hóspedes", fonte:"[F1] Implantação; [F1] Premissas" },
          { nome:"Loft 6 (não cabe nas curvas de nível na versão atual)", area:null, ocupacao:"[MARCADOR]", fonte:"[F1] Implantação" },
          { nome:"Loft 7 (não cabe nas curvas de nível na versão atual)", area:null, ocupacao:"[MARCADOR]", fonte:"[F1] Implantação" }],
        premissas:[{ t:"Hóspedes: 7 lofts × 4 = 28; ocupação média 0,7", fonte:"[F1] Premissas" },
          { t:"Número de lofts diverge entre os documentos: sete [F4 §4.3] e cinco implantados [F1 Implantação] [CONFERIR]", fonte:"[F1]; [F4]" }],
        alternativas:[{ nome:"Sem ar-condicionado (adotada no estudo)", descricao:"Ventilador de teto no estar e aquecedor portátil com termostato nos 3 meses de inverno", fonte:"[F3]; [F2] §10" }],
        equipamentos:[] })],
    aprendizados:[] };
}
function comEquipamentos(estado) {
  const E = global.ESTERMIC, s = estado.subprojetos;
  s[0].equipamentos = [eq(E, "VE-01", "Ventilação", "Ventiladores de teto — quartos e sala (Procel A)", 4, 40, "[F3] Casa 1")];
  s[1].equipamentos = [eq(E, "VE-01", "Ventilação", "Exaustor da área limpa do LAB (linha da planilha soma iluminação LED e exaustor: 130 W)", 1, 130, "[F3] LAB"),
    eq(E, "VE-02", "Ventilação", "Exaustor de solda da oficina (MEC) — potência sem fonte", 1, null, "[F3] MEC")];
  s[2].equipamentos = [eq(E, "VE-01", "Ventilação", "Coifa com exaustão e filtro de gordura (NBR 14518)", 1, 370, "[F3] Restaurante"),
    eq(E, "BC-01", "Bomba de calor", "Secadora por bomba de calor (lavanderia do apoio) — potência sem fonte", 1, null, "[F3] Apoio de funcionários")];
  s[3].equipamentos = [eq(E, "VE-01", "Ventilação", "Ventilador de teto no estar dos lofts (Procel A)", 7, 40, "[F3] Hospedagem"),
    eq(E, "AQ-01", "Aquecimento", "Aquecedor portátil com termostato (3 meses de inverno)", 7, 1000, "[F3] Hospedagem")];
  return estado; }
global.ESTERMIC_CONJUNTOS = Object.assign(global.ESTERMIC_CONJUNTOS || {}, { "casa-physis": () => comEquipamentos(conjuntoCasaPhysis()) });
})(typeof window !== "undefined" ? window : this);
