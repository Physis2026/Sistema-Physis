# Renderização 3D e visual nos sistemas da Physis · VERSÃO DE TESTE (22/11/2026)

Ramo `teste/renderizacao-3d` (worktree `C:\physis\physis-render`). Sem merge no main sem aprovação da dona.
Regras seguidas: 1 (nenhum número inventado), 2 (programas: só aparência; o 3D do Planejador é função e só mudou por decisão da dona),
5 (acessibilidade), 6 (paleta, claro e escuro), 11 (software aberto hospedado pela Physis, sem internet).

## 1. Onde há renderização hoje

| Sistema | Arquivo | O que desenha | Como | Situação |
|---|---|---|---|---|
| Planejador | `modulos/planejador/planejador-physis.html`, `ver3D` | IFC em 3D e áreas dos ambientes | three.js 0.160 + web-ifc 0.0.66 de `/vendor/`; `MeshLambertMaterial`, céu 1,1 + sol 0,8, **sem sombras**, canvas de 360 px fixo, cores do IFC tratadas como lineares (ficam lavadas), fundo claro fixo `#F4F6F1` também no tema escuro | função (regra 2): não mexido |
| Planejador | `abrirMapa` | terreno no mapa (GIS) | MapLibre 4.7.1 + PMTiles de `/vendor/` | fundo `#EEF2EA` fixo, sem tema escuro |
| Planejador | plantas, perfis, gráficos | desenho 2D | SVG | vetorial, nítido |
| Plataforma | `physis-hub/web/painel.html` | 48 gráficos SVG; mapa "Destinos em volta" | SVG; MapLibre | escuro já trata traços do SVG; mapa com fundo claro fixo |
| Physis M&A | `physis-hub/web/mv.html`, `verModelo` | STL e OBJ em 3D | three.js de `/vendor/`; `MeshStandardMaterial`, sem sombras, laço de quadros contínuo (gasta bateria) | é da sessão do M&A: só proposta |
| SustainKit, SCADA, Gestão, consultoria, documento, município | vários | gráficos e diagramas | SVG; canvas só para recortar imagem e exportar PNG (`rasterizar`, 2×, fundo branco) | vetorial |
| Demos | `demos/*.html` | cópias geradas das telas acima | — | seguem os originais |

## 2. Programas abertos de renderização: comparação

| Programa | Licença | Sem internet, hospedado pela Physis | Lê | Qualidade | Peso | Situação do projeto |
|---|---|---|---|---|---|---|
| **three.js** (já em `/vendor/`) | MIT | sim | glTF/GLB (carregador), IFC pelo web-ifc | PBR, sombras, tom ACES no núcleo; SSAO/GTAO só nos módulos ES (`addons`), que o arquivo `three.min.js` 0.160 não traz | 0,67 MB | ativo |
| **web-ifc** (já em `/vendor/`) | MPL-2.0 | sim | IFC 2x3 e 4 | — (só geometria) | 5,5 MB + 1,2 MB wasm | ativo |
| **xeokit SDK** | AGPL-3.0 (há licença comercial à parte) | sim | IFC (convertido para XKT ou GLB), glTF, LAS, CityJSON | muito boa para BIM grande: SAO, arestas, cortes, precisão dupla | grande; novo conjunto de bibliotecas | ativo |
| **That Open** (antigo IFC.js: components, fragments) | MIT (components) + MPL-2.0 (web-ifc) | sim | IFC, fragments | boa; ferramentas BIM (medir, cortar, plantas) | grande; módulos ES; API muda rápido; licença do formato fragments a conferir | ativo |
| **Blender + Cycles** | GPL (Blender), Apache-2.0 (Cycles) | sim, instalado no servidor da Physis; roda sem tela (`blender -b`) | glTF/GLB nativo; IFC pelo complemento Bonsai (IfcOpenShell, LGPL) | fotorrealista (traçado de caminhos, removedor de ruído aberto) | ~0,4 GB instalado; GPU opcional | ativo |
| **LuxCoreRender** | Apache-2.0 | sim | pelo Blender (BlendLuxCore) ou Python | fotorrealista, sem viés (cáusticas) | médio | voltou a ter versão estável em 2025 (2.10; site lista 2.11) depois de anos parado |
| **appleseed** | MIT | sim | formato próprio, via Blender antigo | boa | médio | parado desde 2019: não recomendado |
| **POV-Ray** | AGPL-3.0 | sim | linguagem de cena própria (sem glTF/IFC) | boa, mas fluxo manual | leve | sem evolução relevante: não recomendado |

Fontes consultadas em 22/11/2026: [LuxCoreRender 2.10 (CG Channel)](https://www.cgchannel.com/2025/05/luxcorerender-2-10-and-blendluxcore-2-10-have-been-released/),
[luxcorerender.org/download](https://luxcorerender.org/download/), [xeokit-sdk (GitHub)](https://github.com/xeokit/xeokit-sdk),
[engine_web-ifc (GitHub)](https://github.com/ThatOpen/engine_web-ifc). Licenças de That Open fragments e o que mudou no LuxCore 2.11: [CONFERIR].

## 3. Recomendação

**No navegador: continuar com three.js + web-ifc (já hospedados), pelo módulo novo `sistema/physis-3d.js`.**
Não precisa de biblioteca nova nem de internet, dá a maior parte do ganho visual (luz, sombras, cor certa, arestas) e cabe nos arquivos
únicos que os programas já são. xeokit fica como caminho futuro **só se** aparecerem modelos BIM grandes demais para o three.js;
That Open, se a Physis precisar de ferramentas BIM (cortes, medições) além de ver.

**Para imagens de apresentação: exportar GLB da vista 3D → Blender/Cycles no servidor da Physis**, como opção. O caminho principal
continua sendo o PNG em alta resolução direto do navegador (até 4× a vista, máximo 8.192 px de lado). LuxCore entra como segunda opção
dentro do Blender. Nada depende do renderizador offline para funcionar.

## 4. O que foi feito neste ramo (só aparência, fora dos programas)

- `sistema/physis-3d.js` (novo, AGPL-3.0): vista 3D com céu + sol, sombras suaves (PCF), materiais PBR, tom ACES, cores do IFC no
  espaço de cor certo (sRGB), arestas, enquadramento pelos vértices do modelo (lote girado ocupa a vista), vistas prontas
  (isométrica, de cima, frente, lateral), altura ajustável (360/540/720 px), tela cheia, PNG 1×/2×/4×, GLB (glTF 2.0 binário,
  um nó por elemento, com o nome do IFC). Desenha só quando muda (sem laço de quadros). Fundo e arestas seguem as variáveis da
  tela e redesenham ao trocar Claro/Escuro/Automático. Teclado: setas giram, Shift+setas movem, + e − aproximam, 0 volta.
  Alvos de 44 px, barra com nome, vista focável com instruções, avisos em `aria-live`. O sol é de apresentação, não estudo solar
  (o norte do modelo não é lido).
- `modulos/planejador/visualizador-3d-teste.html` (novo): compara lado a lado a vista atual do Planejador (reproduzida igual) com a
  nova; caixa de envio de IFC (arrastar ou escolher); `?ifc=` só do mesmo servidor; barra de preferências única.
- `ferramentas/sincronizar.py`: a página de teste entra nas cópias; bloco novo `physis-3d`.
- `physis-hub/tests/test_render_3d.py`: 10 testes (sem internet, paleta, claro/escuro, acessibilidade, cópias iguais, upload,
  Planejador sem mudança, formato GLB).

Verificado no navegador em 22/11/2026 com `casa-physis-rev0.ifc` do ramo do gêmeo (93 peças, ~0,6 s): claro e escuro, quatro
vistas, PNG 4× (2.164 × 1.672 px), GLB de 151 kB conferido (cabeçalho, blocos e 93 malhas), 320 px sem rolagem lateral, todos os
controles com 44 px. Capturas antes/depois em `docs/renderizacao/`. Não verificado: abrir o GLB no Blender (não instalado aqui),
leitor de tela real, celular de verdade.

## 5. Decisões da dona (22/11/2026, caixas de perguntas, registradas no M&A, origem `renderizacao-3d`)

| Pergunta | Resposta | M&A | Feito neste ramo |
|---|---|---|---|
| Trocar o 3D do Planejador pela `physis-3d.js`? | Trocar, em teste | pg:cf499965b745 | `ver3D` agora desenha pela vista comum (bloco `physis-3d` copiado por `sincronizar.py`); a conta das áreas é a mesma linha de antes. Conferido com um IFC de dois ambientes: 20,00 e 9,00 m², iguais à conta antiga. Plataforma (`painel.html`) e demos regeneradas. |
| Blender no servidor para imagens de apresentação? | Sim, como opção | pg:b88441eec95b | `ferramentas/renderizar_glb.py` + `ferramentas/blender_cena.py` (GLB → Cycles, vistas e enquadramento iguais aos do navegador, fundo da paleta por composição de pixels, que não depende do compositor do Blender 5). Sem Blender, avisa e sai com 2. **Testado com o Blender 5.3** (instalado pelo winget a pedido da dona): IFC novo do gêmeo (177 peças, GLB de 815 kB), 1600×1000 px com 64 amostras em ~70 s, fundos `#F4F1EA` e `#0B3D2E`; teste automático roda o Blender quando ele existe. |
| three.js em módulos ES? | Agora, em teste | pg:ea1020f44c18 | `ferramentas/baixar_three.py` baixou three.js 0.170.0 (núcleo + 14 addons) do jsDelivr e conferiu cada arquivo com o SHA-256 publicado (`vendor/three/SHA256.json`). O servidor entrega só a lista (`THREE_MODULOS`); `montar.py` leva para o pacote. A vista carrega por importmap, com oclusão de ambiente (GTAO) e leitura de GLB; sem os módulos, cai no `three.min.js` 0.160 sem esses dois recursos. |

Capturas novas: `claro-iso-depois.png` (com oclusão de ambiente), `claro-iso-depois-sem-oclusao.png`, `escuro-iso-depois.png`,
`planejador-ambientes-escuro.png` (dentro do Planejador, tema escuro), `navegador-ifc-novo-claro.png` e
`blender-cycles-claro.png` (o mesmo IFC novo do gêmeo no navegador e no Blender/Cycles).

## 6. Ainda pendente

- Instalar o Blender no servidor da Physis (nesta máquina já está: Blender 5.3).
- Merge no main: só com a aprovação da dona depois de ver o Planejador no ramo `teste/renderizacao-3d`.
- Propostas para outras sessões, sem mexer aqui: mapas com fundo do tema escuro; vista STL/OBJ do M&A pela `physis-3d.js` (hoje
  com laço de quadros contínuo); `rasterizar` exportar com fundo do tema; acabamentos dos PDFs 09/09b no IFC do gêmeo (pedido
  enviado à sessão do gêmeo em 22/11/2026).
