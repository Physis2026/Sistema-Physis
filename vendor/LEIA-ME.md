# vendor/ — bibliotecas de terceiros guardadas dentro do sistema

O sistema roda sem internet. O que antes vinha de CDN fica aqui e é embutido nos programas por
`ferramentas/embutir_bibliotecas.py`. Não edite estes arquivos à mão.

| Arquivo | Origem | Licença | Conferência |
|---|---|---|---|
| jszip.min.js | JSZip 3.10.1 (cdnjs) | MIT ou GPLv3 (aviso no cabeçalho do arquivo) | SHA-512 igual ao publicado pelo cdnjs (14/11/2026) |
| pdf.min.js | pdf.js 3.11.174, Mozilla (cdnjs) | Apache 2.0 (aviso no cabeçalho) | SHA-512 igual ao publicado pelo cdnjs (14/11/2026) |
| pdf.worker.min.js | pdf.js 3.11.174, Mozilla (cdnjs) | Apache 2.0 (aviso no cabeçalho) | SHA-512 igual ao publicado pelo cdnjs (14/11/2026) |
| fontes/lexend-latin-{300,400,500,600}-normal.woff2 | @fontsource/lexend 5.2.11 | SIL OFL 1.1 (fontes/LICENSE-Lexend-OFL.txt) | — |
| fontes/atkinson-hyperlegible-latin-{400,700}-normal.woff2 | @fontsource/atkinson-hyperlegible 5.2.8 | SIL OFL 1.1 (fontes/LICENSE-Atkinson-OFL.txt) | — |

Mapa e BIM (baixados em 14/11/2026 do jsDelivr; SHA-256 igual ao publicado pelo jsDelivr). Por serem
grandes, **não vão embutidos**: o servidor entrega em `/vendor/<arquivo>` e o Planejador carrega quando precisa.

| Arquivo | Origem | Licença |
|---|---|---|
| maplibre-gl.js, maplibre-gl.css | MapLibre GL JS 4.7.1 | BSD-3-Clause (LICENSE-maplibre-gl.txt) |
| pmtiles.js | PMTiles 3.2.1 (Protomaps) | BSD-3-Clause (declarada no package.json) |
| web-ifc-api-iife.js, web-ifc.wasm | web-ifc 0.0.66 (That Open Company) | MPL-2.0 (repositório ThatOpen/engine_web-ifc; conferir) |
| three.min.js | three.js 0.160.0 | MIT (LICENSE-three.txt) |
| three/ (three.module.min.js e 14 arquivos de addons/) | three.js 0.170.0 em módulos ES (vista 3D: oclusão de ambiente GTAO e leitor glTF; TESTE de 22/11/2026, M&A pg:ea1020f44c18) | MIT (three/LICENSE) |

O three.js em módulos é baixado por `python ferramentas/baixar_three.py`, que confere cada arquivo com o SHA-256 publicado pelo
jsDelivr e grava `three/SHA256.json`; os arquivos não são alterados (as páginas resolvem `three` e `three/addons/` por importmap).
`three.min.js` (0.160) continua para o M&A e como reserva da vista 3D.

Para atualizar uma versão: baixe a nova, confira o SHA-512 com o publicado pela fonte, troque o
arquivo aqui, atualize esta tabela e rode `python ferramentas/embutir_bibliotecas.py`.
