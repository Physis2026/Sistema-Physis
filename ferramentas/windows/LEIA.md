# Scripts do Windows (PC-PHYSIS)

A rotina da noite (`physis_noite.ps1`, passo 1b) copia estes arquivos para `C:\physis` quando o pacote traz versão nova.

| Script | Para quê |
|---|---|
| `physis_noite.ps1` | Rotina noturna: backup, pacotes com testes, instalações, camadas, teste final com volta atrás, regressão no navegador |
| `emitir_camadas.ps1` | Camadas básicas (inclui o risco do SGB pelo serviço ArcGIS oficial) |
| `baixar_opengeohub.ps1` | Recorte do RJ das coleções abertas do OpenGeoHub (solo, terreno, pastagem, inundação...) |
| `inventariar_camadas.ps1` | Inventário de C:\physis e registro das camadas extras (`-Gravar`) |
| `explorar_stac.ps1` | Explorar o catálogo STAC da OpenGeoHub |
