# baixar_opengeohub.ps1 · recorta o RJ das coleções úteis do OpenGeoHub (OpenLandMap) e salva em C:\physis\dados-brutos (27/11/2026)
#   pwsh -ExecutionPolicy Bypass -File C:\physis\baixar_opengeohub.ps1            (só MOSTRA qual arquivo escolheu em cada coleção)
#   pwsh -ExecutionPolicy Bypass -File C:\physis\baixar_opengeohub.ps1 -Baixar    (recorta e salva; um .json ao lado guarda fonte e licença)
# Escolha automática: média (m/mean) > mediana; camada de 0 a 30 cm quando houver; o período mais recente. Nada é inventado: a fonte é o arquivo.
param([switch]$Baixar, [string]$Raiz = "C:\physis")
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:GDAL_DISABLE_READDIR_ON_OPEN = "EMPTY_DIR"; $env:CPL_VSIL_CURL_ALLOWED_EXTENSIONS = ".tif"   # sem os 40 avisos 403 por arquivo
$api = "https://stac.opengeohub.org/v1"
$bboxRJ = @(-44.95, -23.40, -40.90, -20.70)
# nome curto (vira x_ogh_<nome> no inventário) · coleção · palavra que o arquivo precisa ter ('' = qualquer)
$alvos = @(
  @('uso_solo_glad', 'lc_glad.glcluc_go', ''), @('terreno_30m', 'gedtm_go', ''), @('tipo_solo', 'soil.types_ensemble_go', ''),
  @('argila', 'soil_texture_go', 'clay'), @('areia', 'soil_texture_go', 'sand'), @('silte', 'soil_texture_go', 'silt'),
  @('carbono_solo', 'oc_iso.10694.1995_go', ''), @('ph_solo', 'ph.h2o_iso.10390.2021.index_go', ''), @('densidade_solo', 'bd.core_iso.11272.2017.g.cm3_g_go', ''),
  @('pastagem', 'gpwggc_grasscls_go', ''), @('inundacao', 'surface.water_glad.sw.avg_go', ''), @('altura_arvores', 'treeheight_go', ''),
  @('chuva_anual', 'precipitation.total.accum_imerg.3b.annual_go', ''))
function Pontuar($h) {
  $n = ($h.Split('/')[-1]).ToLower(); $p = 0
  if ($n -match '_(sd|p16|p84|p025|p975|q0\.05|q0\.95|l\.|u\.|lower|upper|uncertainty|std)[_.]') { $p -= 100 }
  if ($n -match '_(m|mean)_') { $p += 20 } elseif ($n -match '_(md|p50|q0\.5|median)_') { $p += 10 }
  if ($n -match '_30m_') { $p += 6 } elseif ($n -match '_120m_') { $p += 2 }
  if ($n -match '0\.\.30cm|0cm\.\.30cm|0_30cm|0-30cm') { $p += 15 } elseif ($n -match 'b0cm|s0\.\.0cm|0\.\.5cm|0\.\.10cm') { $p += 8 }
  $anos = [regex]::Matches($n, '(19|20)\d{2}(?=\d{4})|(?<![\d])(19|20)\d{2}(?![\d])') | ForEach-Object { [int]$_.Value.Substring(0, 4) }
  if ($anos) { $p += (($anos | Measure-Object -Maximum).Maximum - 1900) / 10 }
  return $p }
$bin = (Get-ChildItem "C:\Program Files\QGIS*\bin" -Directory | Select-Object -First 1).FullName
$dest = "$Raiz\dados-brutos"; New-Item -ItemType Directory -Force $dest | Out-Null
$cache = @{}
foreach ($alvo in $alvos) {
  $nome = $alvo[0]; $col = $alvo[1]; $chave = $alvo[2]
  if (-not $cache.ContainsKey($col)) {
    $lista = @(); $url = "$api/collections/$col/items?limit=200"
    while ($url) { try { $j = Invoke-RestMethod $url -TimeoutSec 120 } catch { Write-Host ("  [ERRO] " + $col + ": " + $_.Exception.Message); break }
      foreach ($f in $j.features) { foreach ($pr in $f.assets.PSObject.Properties) { $h = [string]$pr.Value.href
        if ($h -match '[?&]url=([^&]+)') { $h = [uri]::UnescapeDataString($Matches[1]) }   # 'preview?url=...' é a miniatura: usa o .tif de dentro
        if ($h -match '^https?://[^?]+\.tif$') { $lista += $h } } }
      $prox = $j.links | Where-Object { $_.rel -eq "next" } | Select-Object -First 1; $url = if ($prox) { $prox.href } else { $null } }
    $lic = try { (Invoke-RestMethod "$api/collections/$col" -TimeoutSec 60).license } catch { "[CONFERIR]" }
    $cache[$col] = @{ tifs = @($lista | Select-Object -Unique); licenca = $lic } }
  $cands = @($cache[$col].tifs | Where-Object { -not $chave -or $_.Split('/')[-1] -match ('(?i)' + $chave) })
  if (-not $cands) { Write-Host ("  [FALTA] " + $nome + ": nenhum .tif em " + $col + $(if ($chave) { " com '" + $chave + "'" })); continue }
  $esc = $cands | Sort-Object { Pontuar $_ } -Descending | Select-Object -First 1
  Write-Host ("  " + $nome.PadRight(15) + " <- " + $esc.Split('/')[-1] + "  [" + $cache[$col].licenca + "] (" + $cands.Count + " opções)")
  if (-not $Baixar) { continue }
  $saida = Join-Path $dest ("opengeohub_" + $nome + "_rj.tif")
  if (Test-Path $saida) { Write-Host "      já existe: pulei"; continue }
  & "$bin\gdal_translate.exe" -q -projwin $bboxRJ[0] $bboxRJ[3] $bboxRJ[2] $bboxRJ[1] -projwin_srs EPSG:4326 -co COMPRESS=DEFLATE -co TILED=YES ("/vsicurl/" + $esc) $saida
  if (Test-Path $saida) {
    @{ fonte = $esc; colecao = $col; licenca = $cache[$col].licenca; catalogo = "$api/collections/$col"; recorte = "RJ " + ($bboxRJ -join ","); baixado_em = (Get-Date -Format s) } |
      ConvertTo-Json | Set-Content -Encoding utf8 ($saida -replace '\.tif$', '.json')
    Write-Host ("      OK " + [math]::Round((Get-Item $saida).Length / 1MB, 1) + " MB") }
  else { Write-Host "      [ERRO] não recortou (veja a mensagem do GDAL acima)" } }
if (-not $Baixar) { Write-Host ""; Write-Host "Confira as escolhas acima e rode de novo com -Baixar." }
else { Write-Host ""; Write-Host "Depois: pwsh -ExecutionPolicy Bypass -File C:\physis\inventariar_camadas.ps1 -Gravar" }
