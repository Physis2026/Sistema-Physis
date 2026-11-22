/* explica-inovastem.js (22/11/2026): perguntas e respostas do bot de explicação do laboratório InovaSTEM e do módulo de
   modelagem 3D (motor: physis-explica.js). Texto para o público: sem nomes de ferramentas internas. */
(function (w) {
  "use strict";
  w.PHYSIS_EXPLICA = w.PHYSIS_EXPLICA || {};
  var itens = [
    { id: "oque", tema: { pt: "O que é o laboratório", en: "What the lab is" }, k: ["laboratorio", "lab", "inovastem", "physis", "3d", "serve", "what"],
      p: { pt: "O que dá para fazer aqui?", en: "What can I do here?" },
      r: { pt: "Desenhar e ajustar peças 3D, abrir modelos BIM, colocar um projeto num lugar do mapa, simular e imprimir. Tudo funciona no navegador, sem instalar nada, e muitas partes funcionam sem internet.",
           en: "Design and adjust 3D parts, open BIM models, place a project on the map, simulate and print. Everything runs in the browser, nothing to install, and many parts work offline." },
      ver: ["enviar", "pecas", "imprimir"] },
    { id: "enviar", tema: { pt: "Enviar arquivo ou foto", en: "Upload a file or photo" }, k: ["enviar", "arquivo", "foto", "imagem", "upload", "stl", "obj", "3mf", "photo"],
      p: { pt: "Que arquivos posso enviar?", en: "Which files can I upload?" },
      r: { pt: "STL, OBJ e 3MF para peças; IFC para modelos BIM; KML/KMZ (Google Earth), GeoJSON e GPX para lugares; e fotos, que viram relevo ou ponto de partida para um modelo 3D.",
           en: "STL, OBJ and 3MF for parts; IFC for BIM models; KML/KMZ (Google Earth), GeoJSON and GPX for places; and photos, which become a relief or a starting point for a 3D model." },
      ver: ["bot", "lugar"] },
    { id: "pecas", tema: { pt: "Peças 3D", en: "3D parts" }, k: ["peca", "pecas", "desenhar", "ajustar", "escala", "girar", "medida", "part", "parts"],
      p: { pt: "Como ajusto uma peça?", en: "How do I adjust a part?" },
      r: { pt: "Na subaba Peças 3D: escala, giro, espelho, pôr na mesa e medidas. A vista mostra as camadas e marca em vermelho as partes em balanço, que precisariam de suporte.",
           en: "In the 3D parts sub-tab: scale, rotate, mirror, lay flat and measure. The view shows the layers and marks overhangs, which would need supports, in red." },
      ver: ["dicas", "imprimir"] },
    { id: "dicas", tema: { pt: "Imprimir sem erro", en: "Print without errors" }, k: ["erro", "suporte", "aresta", "balanco", "forte", "filamento", "parede", "encaixe", "support", "error"],
      p: { pt: "Como fazer peças fortes, com pouco filamento e sem suporte?", en: "How do I make strong parts with little filament and no supports?" },
      r: { pt: "Malha fechada; a maior face plana apoiada na mesa; saliências até 45°; paredes em múltiplos do bico (0,4 mm → 1,2 / 1,6 / 2,0 mm); 3 perímetros com preenchimento de 15%; folga de 0,15 a 0,3 mm nos encaixes; peças maiores que 20 cm divididas com eixo, pinos ou parafusos.",
           en: "Closed mesh; largest flat face on the bed; overhangs up to 45°; walls in multiples of the nozzle (0.4 mm → 1.2 / 1.6 / 2.0 mm); 3 perimeters with 15% infill; 0.15–0.3 mm clearance on fits; parts larger than 20 cm split with a shaft, pins or screws." },
      ver: ["imprimir", "bot"] },
    { id: "imprimir", tema: { pt: "Fila de impressão", en: "Print queue" }, k: ["imprimir", "impressao", "fila", "impressora", "fatiar", "fatiador", "print", "printer"],
      p: { pt: "Como peço uma impressão?", en: "How do I request a print?" },
      r: { pt: "Escolha a peça, o material e as cópias e envie para a fila. O arquivo sai em STL em milímetros, com malha fechada, e abre no fatiador de qualquer impressora de filamento ou resina.",
           en: "Pick the part, material and copies and send it to the queue. The file is STL in millimetres with a closed mesh, and opens in any filament or resin printer's slicer." },
      ver: ["dicas"] },
    { id: "lugar", tema: { pt: "Lugar no mapa (GIS)", en: "Place on the map (GIS)" }, k: ["lugar", "mapa", "gis", "terreno", "kml", "google", "earth", "chuva", "place", "map"],
      p: { pt: "Como uso o mapa?", en: "How do I use the map?" },
      r: { pt: "Na subaba Lugar (GIS), envie o contorno (KML/KMZ do Google Earth, GeoJSON ou GPX) ou desenhe. Com ele, dá para estimar área, chuva que cai no terreno e água que pode ser captada.",
           en: "In the Place (GIS) sub-tab, upload the outline (Google Earth KML/KMZ, GeoJSON or GPX) or draw it. With it you can estimate area, rain falling on the site and water that can be harvested." },
      ver: ["bot"] },
    { id: "bim", tema: { pt: "Modelos BIM", en: "BIM models" }, k: ["bim", "ifc", "cad", "casa", "edificio", "planta", "building"],
      p: { pt: "O que são os modelos BIM?", en: "What are BIM models?" },
      r: { pt: "São modelos de construções com informação (paredes, portas, dutos, equipamentos). Na subaba Modelos BIM (CAD e IFC) você abre arquivos IFC e vê cada elemento.",
           en: "They are building models with information (walls, doors, ducts, equipment). In the BIM models (CAD and IFC) sub-tab you open IFC files and inspect each element." },
      ver: ["bot"] },
    { id: "bot", tema: { pt: "Bot de modelagem", en: "Modelling bot" }, k: ["bot", "gerar", "turbina", "estufa", "caixa", "pedido", "escrever", "generate"],
      p: { pt: "O que o bot de modelagem faz?", en: "What does the modelling bot do?" },
      r: { pt: "Você escreve o pedido (\"gere uma turbina para impressão 3D de 40 cm\", \"estufa de 3 x 6 m\", \"caixa para sensores 10 x 8 x 5 cm\") e ele gera o modelo, mostra cálculos simples e deixa baixar o arquivo. Se ele não entender, sugira a ideia em Desafios e projetos ou no Fórum.",
           en: "You type the request (\"generate a 40 cm wind turbine for 3D printing\", \"greenhouse 3 x 6 m\", \"sensor case 10 x 8 x 5 cm\") and it builds the model, shows simple calculations and lets you download the file. If it does not understand, suggest the idea in Challenges and projects or in the Forum." },
      ver: ["dicas"] }
  ];
  w.PHYSIS_EXPLICA["inovastem-lab"] = { itens: itens };
  w.PHYSIS_EXPLICA.modelagem3d = { itens: itens };
})(typeof window !== "undefined" ? window : this);
