# explorar_stac.ps1 · catálogo STAC da OpenGeoHub (OpenLandMap): lista as coleções úteis e recorta o RJ direto do .tif na nuvem
#   pwsh -ExecutionPolicy Bypass -File C:\physis\explorar_stac.ps1                      (lista coleções de solo, cobertura, relevo, água, clima)
#   pwsh -ExecutionPolicy Bypass -File C:\physis\explorar_stac.ps1 -Colecao <id>        (mostra os arquivos .tif da coleção)
#   pwsh -ExecutionPolicy Bypass -File C:\physis\explorar_stac.ps1 -Colecao <id> -Baixar <n>   (recorta o RJ do arquivo n e salva em dados-brutos)
param([string]$Colecao = "", [int]$Baixar = -1, [string]$Raiz = "C:\physis")
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$api = "https://stac.opengeohub.org/v1"
$bboxRJ = @(-44.95, -23.40, -40.90, -20.70)
if (-not $Colecao) {
  $cols = @(); $url = "$api/collections"
  while ($url) { $j = Invoke-RestMethod $url -TimeoutSec 60; $cols += $j.collections
    $prox = $j.links | Where-Object { $_.rel -eq "next" } | Select-Object -First 1; $url = if ($prox) { $prox.href } else { $null } }
  Write-Host ("Coleções no catálogo: " + $cols.Count)
  $tema = '(?i)soil|solo|clay|sand|silt|carbon|organic|bulk|texture|land.?cover|lulc|landuse|dtm|dem|elevation|slope|water|flood|precip|temperature|wind|forest|vegetation'
  $cols | Where-Object { ($_.id + " " + $_.title + " " + ($_.keywords -join " ")) -match $tema } | Sort-Object id |
    ForEach-Object { $tt = ($_.title -replace '\s+', ' '); "{0,-55} {1}  [{2}]" -f $_.id, $tt.Substring(0, [math]::Min(70, $tt.Length)), $_.license }
  Write-Host ""; Write-Host "Escolha uma e rode de novo com -Colecao <id>."; exit 0 }
$it = Invoke-RestMethod "$api/collections/$Colecao/items?limit=200" -TimeoutSec 120
$tifs = @(); foreach ($f in $it.features) { foreach ($p in $f.assets.PSObject.Properties) { if ($p.Value.href -match '\.tif') { $tifs += [pscustomobject]@{ item = $f.id; nome = $p.Name; href = $p.Value.href } } } }
$c = Invoke-RestMethod "$api/collections/$Colecao" -TimeoutSec 60
Write-Host ("Coleção: " + $c.title + " · licença: " + $c.license)
for ($i = 0; $i -lt $tifs.Count; $i++) { "{0,3}  {1}  {2}" -f $i, $tifs[$i].item, $tifs[$i].href }
if ($Baixar -lt 0) { Write-Host ""; Write-Host "Para recortar o RJ: -Baixar <número>"; exit 0 }
$t = $tifs[$Baixar]; if (-not $t) { Write-Host "número fora da lista"; exit 1 }
$bin = (Get-ChildItem "C:\Program Files\QGIS*\bin" -Directory | Select-Object -First 1).FullName
New-Item -ItemType Directory -Force "$Raiz\dados-brutos" | Out-Null
$nomeArq = ("opengeohub_" + $Colecao + "_" + ($t.href.Split('/')[-1] -replace '\.tif.*$', '') + "_rj.tif") -replace '[^A-Za-z0-9_.\-]', '_'
$saida = Join-Path "$Raiz\dados-brutos" $nomeArq
& "$bin\gdal_translate.exe" -projwin $bboxRJ[0] $bboxRJ[3] $bboxRJ[2] $bboxRJ[1] -projwin_srs EPSG:4326 -co COMPRESS=DEFLATE ("/vsicurl/" + $t.href) $saida
if (Test-Path $saida) { Write-Host ("OK: " + $saida + " (" + [math]::Round((Get-Item $saida).Length / 1MB, 1) + " MB) · fonte " + $t.href + " · licença " + $c.license) }
else { Write-Host "não recortou: veja o erro do GDAL acima" }
