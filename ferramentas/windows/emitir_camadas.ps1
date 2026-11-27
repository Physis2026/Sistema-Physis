# emitir_camadas.ps1 · prepara e baixa as camadas que faltam: clima (EPW), uso do solo, solos, CAR e risco
#   pwsh -ExecutionPolicy Bypass -File C:\physis\emitir_camadas.ps1
# Cada fonte é conferida AQUI (o endereço responde) antes de entrar em fontes-camadas.txt; o bot de camadas baixa,
# converte pelo GDAL do QGIS e recorta na janela das cidades da Physis. CAR e risco não têm download direto (o SICAR pede
# captcha; o SGB publica por município): o script abre as páginas oficiais e diz onde salvar; o arquivo entra sozinho depois.
param([string]$Pasta = "C:\physis\camadas", [string[]]$Ufs = @("RJ", "SP"))
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ProgressPreference = "SilentlyContinue"
$fontes = Join-Path $Pasta "fontes-camadas.txt"; $brutos = "C:\physis\dados-brutos\camadas"
New-Item -ItemType Directory -Force $Pasta, $brutos, "$brutos\car", "$brutos\risco" | Out-Null
$linhas = [System.Collections.Generic.List[string]]::new()
if (Test-Path $fontes) { Get-Content $fontes | ForEach-Object { $linhas.Add($_) } }
function Gravar($camada, $origem) {
  for ($i = $linhas.Count - 1; $i -ge 0; $i--) { if ($linhas[$i] -match ("^" + $camada + ";")) { $linhas.RemoveAt($i) } }
  $linhas.Add($camada + ";" + $origem); Set-Content -Encoding utf8 $fontes $linhas; Write-Host ("  [ OK  ] " + $camada + " -> " + $origem) }
function Responde($url) { try { $r = Invoke-WebRequest $url -Method Head -UseBasicParsing -TimeoutSec 60 -MaximumRedirection 5; return $r.StatusCode -lt 400 } catch { return $false } }
function Listar($url) { try { return (Invoke-WebRequest $url -UserAgent 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Physis' -UseBasicParsing -TimeoutSec 120).Links.href | Where-Object { $_ -and $_ -notmatch '^\?|^/$|^\.\./' } } catch { return @() } }

Write-Host "== 0. Arquivos vetoriais que já estão em C:\physis (procura pelo nome; o que está aqui tem prioridade)"
$excluir = '/exemplos/|/instituto-physis|/clientes|/blender|/site-packages/|/dados-brutos/instaladores/|/[.]git/|/node_modules/|/extraido|/physis-ma-|/physis-integracao|/backup|/camadas/[^/]+[.]geojson$'
$vetores = @(Get-ChildItem C:\physis -Recurse -File -Include *.zip, *.shp, *.gpkg, *.geojson, *.kml -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName.Replace('\', '/') -notmatch $excluir -and $_.Name -notmatch '^(pacote|inovastem|juncao|ma-patches)' })
$regras = [ordered]@{ solos = '(?i)solo|pedolog'; car = '(?i)(^|[-_. ])car([-_. ]|$)|sicar|imove|area_imovel'; risco = '(?i)risco|setoriza'; hidrografia = '(?i)_hid([-_. ]|$)|hidrograf|drenag|bho' }
$local = @{}
# zip só com documentos (PDF) ou banco .mdb do GeoMedia não é camada: confere o que há dentro antes de aceitar (27/11/2026)
Add-Type -AssemblyName System.IO.Compression.FileSystem
function TemVetor($arq) { if ($arq -notmatch '(?i)\.zip$') { return $true }
  try { $z = [IO.Compression.ZipFile]::OpenRead($arq); $ok = [bool]($z.Entries | Where-Object { $_.FullName -match '(?i)\.(shp|gpkg|geojson|kml|kmz)$' }); $z.Dispose(); return $ok } catch { return $false } }
foreach ($v in $vetores) { foreach ($c in $regras.Keys) { if ($v.Name -match $regras[$c] -and -not $local[$c]) {
  if (-not (TemVetor $v.FullName)) { Write-Host ("  [AVISO] " + $v.Name + " não tem mapa dentro (só documentos ou banco .mdb): ignorado para " + $c); continue }
  if ($c -eq "solos" -and $v.FullName -match '(?i)amazonia|AML_') { Write-Host ("  [AVISO] " + $v.Name + " cobre só a Amazônia Legal (não serve para RJ/SP): ignorado"); continue }
  $local[$c] = $v.FullName } } }
# rasters (26/11/2026): MapBiomas baixado à mão (GitHub/Drive) vira o uso do solo; o maior .tif com nome de cobertura
$tifs = @(Get-ChildItem C:\physis -Recurse -File -Include *.tif, *.tiff -ErrorAction SilentlyContinue | Where-Object { $_.FullName.Replace('\', '/') -notmatch $excluir -and $_.Name -match '(?i)mapbiomas|coverage|cobertura|lulc|uso.?(do.?)?solo|landcover' } | Sort-Object Length -Descending)
if ($tifs) { $local["uso_solo"] = $tifs[0].FullName; Write-Host ("  uso do solo (raster): " + $tifs[0].FullName + " (" + [math]::Round($tifs[0].Length / 1MB) + " MB)") }
elseif (Get-ChildItem C:\physis -Recurse -Directory -Filter "*mapbiomas*" -ErrorAction SilentlyContinue | Select-Object -First 1) { Write-Host "  [AVISO] achei pasta do MapBiomas, mas sem .tif dentro: o GitHub do MapBiomas tem os SCRIPTS; o mapa (.tif) sai do user-toolkit do MapBiomas no Earth Engine ou de outra fonte aberta; salve em dados-brutos com 'mapbiomas' no nome" }
# tira de fontes-camadas.txt o que já se sabe que não serve (pedologia só da Amazônia Legal não cobre RJ/SP)
for ($i = $linhas.Count - 1; $i -ge 0; $i--) { if ($linhas[$i] -match '(?i)^solos;.*(amazonia|AML_|_mdb\.zip)' -or $linhas[$i] -match '(?i)^risco;.*risco_petropolis_2022\.zip') { $linhas.RemoveAt($i) } }
Set-Content -Encoding utf8 $fontes $linhas
foreach ($c in $local.Keys) { Gravar $c $local[$c] }
$sobra = $vetores | Where-Object { $local.Values -notcontains $_.FullName }
if ($sobra) { Write-Host "  Vetoriais sem camada reconhecida pelo nome (renomeie com solos_, car_, risco_ ou hidro_ se forem dessas):"; $sobra | Select-Object -First 30 | ForEach-Object { Write-Host ("    " + $_.FullName) } }
if (-not $vetores) { Write-Host "  [AVISO] nenhum .zip/.shp/.gpkg/.geojson/.kml achado em C:\physis" }

Write-Host "== 1. Uso do solo · MapBiomas (Coleção 11, Brasil, 2025; o GDAL lê do endereço só a janela das cidades)"
# a coleção mais nova que responder (o nome do arquivo mudou entre as coleções); GET de 1 byte, porque alguns servidores recusam HEAD
$cands = @("https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/collection_11/lulc/coverage/brazil_coverage_2025.tif",
  "https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/collection11/lulc/coverage/brazil_coverage/brazil_coverage-col11_2025.tif",
  "https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/collection_10/lulc/coverage/brazil_coverage_2024.tif",
  "https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/collection_9/lclu/coverage/brasil_coverage_2023.tif")
function RespondeGet($url) { try { $r = Invoke-WebRequest $url -Headers @{ Range = "bytes=0-0" } -UseBasicParsing -TimeoutSec 60; return $r.StatusCode -lt 400 } catch { return $false } }
# 27/11/2026: o MapBiomas publica os mapas (.tif) num repositório público (storage.googleapis.com/mapbiomas-public); o nome muda
# a cada coleção. Aqui o script LISTA o repositório e escolhe a coleção e o ano mais novos de "coverage" do Brasil (sem cadastro).
function AcharMapBiomas {
  # 27/11/2026: o repositório não deixa LISTAR (403), mas cada arquivo é público. Testa os nomes usados pelo MapBiomas
  # (coleções 8 a 12, pastas lclu/lulc, brasil/brazil, anos 2020 a 2025), do mais novo para o mais antigo.
  $base = "https://storage.googleapis.com/mapbiomas-public/initiatives/brasil"
  foreach ($col in 12, 11, 10, 9, 8) { foreach ($ano in 2025, 2024, 2023, 2022, 2021, 2020) {
    foreach ($u in @(($base + "/collection_" + $col + "/lclu/coverage/brasil_coverage_" + $ano + ".tif"), ($base + "/collection_" + $col + "/lulc/coverage/brazil_coverage_" + $ano + ".tif"),
                     ($base + "/collection_" + $col + "/lulc/coverage/brasil_coverage_" + $ano + ".tif"), ($base + "/collection_" + $col + "/lclu/coverage/brazil_coverage_" + $ano + ".tif"),
                     ($base + "/collection" + $col + "/lulc/coverage/brazil_coverage/brazil_coverage-col" + $col + "_" + $ano + ".tif"))) {
      try { $r = Invoke-WebRequest $u -Method Head -UseBasicParsing -TimeoutSec 20 -ErrorAction Stop; if ($r.StatusCode -eq 200) { return $u } } catch { } } } }
  return $null }
if ($local["uso_solo"]) { $mb = $null } else { $mb = AcharMapBiomas; if ($mb) { Write-Host ("  MapBiomas achado no repositório público: " + $mb) } else { $mb = $cands | Where-Object { (Responde $_) -or (RespondeGet $_) } | Select-Object -First 1 } }
if ($local["uso_solo"]) { }
elseif ($mb) { Gravar "uso_solo" $mb } else { Write-Host "  [AVISO] nenhum endereço do MapBiomas respondeu: em https://brasil.mapbiomas.org/ (Downloads) copie o link do .tif do Brasil e me mande" }

Write-Host ("== 2. Clima · arquivos EPW (climate.onebuilding.org, TMYx das estações do INMET): " + ($Ufs -join ", "))
$cl = Join-Path $Pasta "clima"; New-Item -ItemType Directory -Force $cl | Out-Null
$base = "https://climate.onebuilding.org/WMO_Region_3_South_America/BRA_Brazil/"
# EPW já baixados à mão (C:\physis\ferramentas-abertas\dados\clima e dados-brutos): usados primeiro
foreach ($z in @(Get-ChildItem C:\physis\ferramentas-abertas\dados\clima, $brutos -Filter *.zip -ErrorAction SilentlyContinue | Where-Object Name -match '(?i)TMYx|INMET|epw')) {
  try { $tmp = Join-Path $brutos ("epw-" + $z.BaseName); Expand-Archive $z.FullName $tmp -Force
    $e = @(Get-ChildItem $tmp -Recurse -Filter *.epw); $e | Copy-Item -Destination $cl -Force
    if ($e) { Write-Host ("  [ OK  ] local: " + $z.Name + " (" + $e.Count + " .epw)") } else { Write-Host ("  [AVISO] " + $z.Name + " sem .epw dentro") } }
  catch { Write-Host ("  [AVISO] " + $z.Name + ": " + $_.Exception.Message) } }
$pastasUf = Listar $base | Where-Object { (($_ -split '/') | Where-Object { $_ })[-1] -match '^[A-Z]{2}_' }
if (-not $pastasUf) { Write-Host ("  [AVISO] não consegui listar " + $base + " (sem internet ou o site mudou)") }
foreach ($uf in $Ufs) {
  $sub = $pastasUf | ForEach-Object { (($_ -split '/') | Where-Object { $_ })[-1] + "/" } | Where-Object { $_ -match ("^" + $uf + "_") } | Select-Object -First 1
  if (-not $sub) { Write-Host ("  [AVISO] " + $uf + " sem pasta no climate.onebuilding.org"); continue }
  $zips = Listar ($base + $sub) | Where-Object { $_ -match 'TMYx.*\.zip$' } | ForEach-Object { Split-Path $_ -Leaf }
  if (-not $zips) { Write-Host ("  [AVISO] " + $uf + ": nenhum TMYx .zip em " + $base + $sub); continue }
  $porEst = $zips | Group-Object { ($_ -split '_TMYx')[0] } | ForEach-Object { $_.Group | Sort-Object | Select-Object -Last 1 }
  foreach ($z in $porEst) {
    $nome = Split-Path $z -Leaf; $dz = Join-Path $brutos $nome
    try { if (-not (Test-Path $dz)) { Invoke-WebRequest ($base + $sub + $z) -OutFile $dz -UseBasicParsing -TimeoutSec 300 }
      $tmp = Join-Path $brutos ("epw-" + [IO.Path]::GetFileNameWithoutExtension($nome)); Expand-Archive $dz $tmp -Force
      Get-ChildItem $tmp -Filter *.epw | Copy-Item -Destination $cl -Force; Write-Host ("  [ OK  ] " + $nome) }
    catch { Write-Host ("  [AVISO] " + $nome + ": " + $_.Exception.Message) } } }
$n = @(Get-ChildItem $cl -Filter *.epw -ErrorAction SilentlyContinue).Count
if ($n) { Set-Content -Encoding utf8 (Join-Path $cl "clima.epw.fonte.json") ('{"url":"' + $base + '","produto":"TMYx (estações do INMET) · climate.onebuilding.org","licenca":"conferir na página do site","arquivos":' + $n + ',"baixado":"' + (Get-Date -Format "yyyy-MM-dd") + '"}'); Write-Host ("  " + $n + " arquivo(s) EPW em " + $cl) }

Write-Host "== 3. Solos · IBGE, pedologia (procura o arquivo no servidor de downloads do IBGE)"
$ped = "https://geoftp.ibge.gov.br/informacoes_ambientais/pedologia/"
$script:achado = $null
function Procurar($url, $prof) { if ($prof -gt 3 -or $script:achado) { return }
  foreach ($h in (Listar $url)) { if ($script:achado) { return }
    if ($h -match '\.zip$' -and $h -match '(?i)brasil|_br_|bra') { $script:achado = $url + $h; return }
    if ($h -match '/$' -and $h -match '(?i)vetor|shape|250|5000|brasil') { Procurar ($url + $h) ($prof + 1) } } }
Procurar $ped 0
if ($local["solos"]) { }
elseif (Test-Path "$brutos\solos.zip") { Gravar "solos" "$brutos\solos.zip" }
elseif ($script:achado) { Gravar "solos" $script:achado }
else { Write-Host ("  [AVISO] não achei sozinho o arquivo nacional de solos. Abra " + $ped + ", baixe o shapefile (.zip) de pedologia e salve como " + $brutos + "\solos.zip; depois rode este script de novo") }

Write-Host "== 4. CAR · SICAR (arquivo em C:\physis; senão o serviço WFS oficial, só a janela das cidades)"
$car = Get-ChildItem "$brutos\car" -Filter *.zip -ErrorAction SilentlyContinue | Select-Object -First 1
$wfs = "https://geoserver.car.gov.br/geoserver/sicar/wfs"
if ($local["car"]) { }
elseif ($car) { Gravar "car" $car.FullName }
elseif (Responde ($wfs + "?service=WFS&request=GetCapabilities")) { Gravar "car" $wfs
  Write-Host "  (o bot traz todas as camadas do serviço na janela; para escolher uma, acrescente #nome_da_camada na linha car de fontes-camadas.txt)" }
else { Write-Host ("  [AVISO] o WFS do SICAR não respondeu: " + $wfs) }

Write-Host "== 5. Risco · SGB/CPRM, setorização de risco geológico (por município)"
if ($local["risco"]) { $ris = $null } else { $ris = Get-ChildItem "$brutos\risco" -Include *.zip, *.shp, *.kml, *.gpkg -Recurse -ErrorAction SilentlyContinue | Where-Object { TemVetor $_.FullName } | Select-Object -First 1 }
if ($local["risco"]) { }
elseif ($ris) { Gravar "risco" $ris.FullName }
else {
  # 27/11/2026: serviço ArcGIS REST oficial do SGB (setorização de risco geológico); o bot pega só os setores na janela das cidades
  $sgb = "https://geoportal.sgb.gov.br/server/rest/services/gestaoterritorial/risco/FeatureServer/0"
  try { $t = Invoke-RestMethod ($sgb + "?f=json") -TimeoutSec 60; Write-Host ("  serviço do SGB respondeu: " + $t.name); Gravar "risco" $sgb }
  catch { Write-Host ("  [AVISO] o serviço do SGB não respondeu agora (" + $_.Exception.Message + "); o bot tenta de novo na próxima noite") } }

Write-Host ""; Write-Host "== 6. Bot de camadas (baixa, converte e recorta o que está em fontes-camadas.txt)"
$bot = @("C:\physis\physis-integracao-2026-11-25\ferramentas\bot_camadas.py", "C:\physis\physis-ma-20261122-1bd599e\ferramentas\bot_camadas.py") | Where-Object { Test-Path $_ } | Select-Object -First 1
Write-Host ("  código: " + $bot)
py $bot --so uso_solo,solos,car,risco,clima,hidrografia
Write-Host ""; Write-Host "CAR ou solos baixados à mão: salve nas pastas indicadas e rode este script de novo. O risco vem do serviço do SGB."
