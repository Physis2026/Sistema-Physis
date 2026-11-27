# inventariar_camadas.ps1 · mapa detalhado de todos os dados geográficos em C:\physis e as camadas EXTRAS que eles viram (27/11/2026)
#   pwsh -ExecutionPolicy Bypass -File C:\physis\inventariar_camadas.ps1            (só mostra: C:\physis\camadas\inventario-camadas.md)
#   pwsh -ExecutionPolicy Bypass -File C:\physis\inventariar_camadas.ps1 -Gravar    (+ grava as linhas extra: em fontes-camadas.txt)
# Depois de gravar: py C:\physis\physis-integracao-2026-11-25\ferramentas\bot_camadas.py --extras  (recorta e instala; a noite também faz)
param([switch]$Gravar, [string]$Raiz = "C:\physis")
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$fora = '(\.tar\.zip$|/exemplos/|/instituto-physis|/(backup|clientes|camadas/|\.git/|node_modules|physis-ma-|physis-integracao|juncao|instituto-integracao|dados-brutos/instaladores|blender|site-packages|minipaint|extraido))'
$arqs = @(Get-ChildItem $Raiz -Recurse -File -Include *.shp, *.gpkg, *.geojson, *.kml, *.kmz, *.tif, *.tiff, *.zip -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName.Replace('\', '/') -notmatch $fora -and $_.Name -notmatch '^(pacote|inovastem|juncao|ma-patches|DOCUMENTOS|kit-)' })
# regra (regex no caminho) → id da camada extra · nome · grupo. Ordem importa: a primeira que casar vale.
$R = @(
 @('(?i)jrc_agua_superficial[^/]*\.tif', 'x_agua_superficial', 'Água superficial 1984–2021 (JRC/Google)', 'agua'), @('(?i)soilgrids_agua[^/]*\.tif', 'x_solo_agua', 'Água no solo: retenção 33 e 1500 kPa (SoilGrids/ISRIC)', 'solo'),
 @('(?i)brazil-soil.*(carbon|cos|soc)[^/]*\.tif', 'x_solo_carbono', 'Carbono orgânico do solo (MapBiomas Solo)', 'solo'), @('(?i)brazil-soil.*(clay|argila|sand|areia|silt|silte|textur|granulo)[^/]*\.tif', 'x_solo_textura', 'Textura do solo (MapBiomas Solo)', 'solo'),
 @('(?i)/APPS?[_/.]', 'x_car_app', 'APP (CAR)', 'ambiental'), @('(?i)RESERVA_LEGAL', 'x_car_reserva_legal', 'Reserva legal (CAR)', 'ambiental'),
 @('(?i)AREA_CONSOLIDADA', 'x_car_area_consolidada', 'Área consolidada (CAR)', 'ambiental'), @('(?i)AREA_POUSIO', 'x_car_pousio', 'Área de pousio (CAR)', 'ambiental'),
 @('(?i)VEGETACAO_NATIVA', 'x_car_vegetacao_nativa', 'Vegetação nativa (CAR)', 'ambiental'), @('(?i)NASCENTE', 'x_car_nascentes', 'Nascentes (CAR)', 'agua'),
 @('(?i)SERVIDAO', 'x_car_servidao', 'Servidão administrativa (CAR)', 'ambiental'), @('(?i)USO_RESTRITO', 'x_car_uso_restrito', 'Uso restrito (CAR)', 'ambiental'),
 @('(?i)biodiversidade_mun', 'x_biodiversidade_municipio', 'Biodiversidade por município', 'ambiental'), @('(?i)biodiversidade_uf', 'x_biodiversidade_uf', 'Biodiversidade por UF', 'ambiental'),
 @('(?i)biodiversidade_regnat', 'x_biodiversidade_regiao', 'Biodiversidade por região natural', 'ambiental'), @('(?i)biodiversidade_50km', 'x_biodiversidade_grade50', 'Biodiversidade (grade 50 km)', 'ambiental'),
 @('(?i)mata.?atl', 'x_mata_atlantica', 'Mata Atlântica (bioma / lei)', 'ambiental'), @('(?i)bioma', 'x_biomas', 'Biomas', 'ambiental'),
 @('(?i)pasto|pastag', 'x_pastagem', 'Pastagem', 'uso do solo'), @('(?i)unidade.?conserv|/lim_unidade_conservacao|/uc_', 'x_unidades_conservacao', 'Unidades de conservação', 'ambiental'),
 @('(?i)terra.?indig', 'x_terras_indigenas', 'Terras indígenas', 'territorial'), @('(?i)quilomb', 'x_quilombolas', 'Territórios quilombolas', 'territorial'),
 @('(?i)VG_REG_FITO|fitofision', 'x_vegetacao_fitofisionomia', 'Regiões fitoecológicas / vegetação (IBGE)', 'ambiental'), @('(?i)/veg_', 'x_vegetacao_ibge', 'Vegetação (IBGE)', 'ambiental'), @('(?i)/hid_massa_dagua', 'x_massas_dagua', 'Massas d''água (IBGE)', 'agua'),
 @('(?i)/hid_barragem', 'x_barragens', 'Barragens (IBGE)', 'agua'), @('(?i)/hid_(canal|queda|corredeira|banco)', 'x_hidro_outros', 'Canais, quedas e bancos (IBGE)', 'agua'),
 @('(?i)/rel_curva_nivel|curva.?nivel', 'x_curvas_nivel', 'Curvas de nível', 'relevo'), @('(?i)/rel_ponto_cotado|ponto.?cotado', 'x_pontos_cotados', 'Pontos cotados', 'relevo'),
 @('(?i)/rel_isolinha', 'x_isolinhas', 'Isolinhas hipsométricas (IBGE)', 'relevo'), @('(?i)/rel_|declividade|geomorf', 'x_relevo_ibge', 'Relevo e geomorfologia', 'relevo'),
 @('(?i)/enc_trecho_energia', 'x_linhas_energia', 'Linhas de energia (IBGE)', 'energia'), @('(?i)/enc_subest', 'x_subestacoes', 'Subestações (IBGE)', 'energia'),
 @('(?i)/enc_(hidreletrica|termeletrica|est_gerad)', 'x_usinas', 'Usinas de energia (IBGE)', 'energia'), @('(?i)/dut_', 'x_dutos', 'Dutos (IBGE)', 'energia'),
 @('(?i)/tra_trecho_rodoviario|rodovi', 'x_estradas', 'Estradas (IBGE)', 'transporte'), @('(?i)/fer_', 'x_ferrovias', 'Ferrovias (IBGE)', 'transporte'),
 @('(?i)/hdv_', 'x_hidrovias_portos', 'Hidrovias e portos (IBGE)', 'transporte'), @('(?i)/aer_', 'x_aeroportos', 'Aeroportos (IBGE)', 'transporte'),
 @('(?i)/eco_ext_mineral|mineracao|anm', 'x_mineracao', 'Mineração', 'economia'), @('(?i)/loc_|localidade', 'x_localidades', 'Localidades (IBGE)', 'territorial'),
 @('(?i)/cbge_trecho_arruamento', 'x_arruamento', 'Arruamento (IBGE)', 'transporte'), @('(?i)/cbge_', 'x_edificacoes_ibge', 'Edificações e áreas construídas (IBGE)', 'territorial'), @('(?i)/lim_municipio|limite', 'x_limites_ibge', 'Limites (IBGE)', 'territorial'),
 @('(?i)hidrogeolog', 'x_hidrogeologia', 'Hidrogeologia (aquíferos)', 'agua'), @('(?i)geolog|litolog', 'x_geologia', 'Geologia', 'relevo'), @('(?i)terreno_sujeito_inundacao', 'x_terreno_inundavel', 'Terreno sujeito a inundação (IBGE)', 'risco'), @('(?i)suscetib|movimento.?massa|inunda', 'x_suscetibilidade', 'Suscetibilidade (movimentos de massa / inundação)', 'risco'))
$BASICAS = @{ solos = '(?i)solo|pedolog'; risco = '(?i)risco|setoriza'; hidrografia = '(?i)hid_trecho_drenagem|drenag|bho'; car = '(?i)AREA_IMOVEL'; uso_solo = '(?i)mapbiomas|coverage|cobertura|lulc|landcover' }
$L = [System.Collections.Generic.List[string]]::new(); $L.Add("# Inventário de dados geográficos em " + $Raiz + " · " + (Get-Date -Format "dd/MM/yyyy HH:mm")); $L.Add("")
$L.Add("| Arquivo | Tamanho | Vira a camada | Grupo |"); $L.Add("|---|---|---|---|")
$extras = [ordered]@{}; $semUso = [System.Collections.Generic.List[string]]::new()
foreach ($a in ($arqs | Sort-Object FullName)) {
  $c = $a.FullName.Replace('\', '/'); $mb = [math]::Round($a.Length / 1MB, 1); $alvo = ""; $grupo = ""
  foreach ($b in $BASICAS.Keys) { if ($c -match '(?i)brazil-soil|/opengeohub_') { break }; if ($c -match $BASICAS[$b] -and -not ($b -eq "solos" -and $c -match '(?i)amazonia|AML_')) { $alvo = "básica: " + $b; break } }
  if (-not $alvo -and $a.Name -match '(?i)^opengeohub_(.+)_rj\.tif$') {
    $base = $Matches[1].ToLower() -replace '[^a-z0-9]+', '_'
    $base = $base -replace '_go_.*$', ''
    $id = 'x_ogh_' + $base
    if ($id.Length -gt 42) { $id = $id.Substring(0, 42) }
    $id = $id.TrimEnd('_')
    $alvo = $id + ' · OpenLandMap'; $grupo = 'opengeohub'
    $extras[$id] = @($a.FullName, ('OpenLandMap: ' + $Matches[1]), 'opengeohub')
  }
  if (-not $alvo) { foreach ($regra in $R) { if ($c -match $regra[0]) { $alvo = $regra[1] + " · " + $regra[2]; $grupo = $regra[3]
        if (-not $extras.Contains($regra[1]) -or $a.Length -gt (Get-Item $extras[$regra[1]][0]).Length) { $extras[$regra[1]] = @($a.FullName, $regra[2], $regra[3]) }; break } } }
  if (-not $alvo) { $alvo = "—"; $semUso.Add($a.FullName) }
  if ($c -match '(?i)amazonia|AML_') { $alvo = "fora da área (Amazônia Legal)" }
  $L.Add("| " + $a.FullName + " | " + $mb + " MB | " + $alvo + " | " + $grupo + " |") }
$L.Add(""); $L.Add("## Camadas EXTRAS propostas (" + $extras.Count + ")"); $L.Add("")
foreach ($k in $extras.Keys) { $L.Add("- " + $k + " · " + $extras[$k][1] + " (" + $extras[$k][2] + ") ← " + $extras[$k][0]) }
$L.Add(""); $L.Add("## O que ainda falta (não há arquivo em C:\physis)"); $L.Add("")
foreach ($f in @(@("uso_solo", "MapBiomas: cobertura do Brasil (.tif)"), @("solos", "Pedologia IBGE 1:250 mil do RJ ou do Brasil"), @("risco", "Setorização de risco geológico do SGB (Petrópolis), shapefile/KML"),
   @("x_mata_atlantica", "Lei da Mata Atlântica / bioma (IBGE ou MMA)"), @("x_pastagem", "Pastagem (MapBiomas ou LAPIG)"), @("x_unidades_conservacao", "Unidades de conservação (MMA/CNUC)"),
   @("x_curvas_nivel", "Curvas de nível (IBGE 1:25 mil do RJ: bc25_rj_2016_rel)"), @("x_suscetibilidade", "Suscetibilidade a movimentos de massa e inundação (SGB)"))) {
  $tem = if ($f[0] -like "x_*") { $extras.Contains($f[0]) } else { [bool]($arqs | Where-Object { $_.FullName -match $BASICAS[$f[0]] -and $_.FullName -notmatch '(?i)amazonia|AML_' }) }
  if (-not $tem) { $L.Add("- " + $f[0] + " · " + $f[1]) } }
$L.Add(""); $L.Add("Sem camada reconhecida (" + $semUso.Count + "): ver a tabela (—). Renomeie com o tema no nome se for camada.")
New-Item -ItemType Directory -Force "$Raiz\camadas" | Out-Null
$L | Set-Content -Encoding utf8 "$Raiz\camadas\inventario-camadas.md"
$L | Select-Object -Last ($extras.Count + 16) | ForEach-Object { Write-Host $_ }
Write-Host ""; Write-Host ("Inventário completo: " + $Raiz + "\camadas\inventario-camadas.md (" + $arqs.Count + " arquivos)")
if ($Gravar) {
  $fontes = "$Raiz\camadas\fontes-camadas.txt"; $linhas = [System.Collections.Generic.List[string]]::new()
  if (Test-Path $fontes) { Get-Content $fontes | Where-Object { $_ -notmatch '^extra:' } | ForEach-Object { $linhas.Add($_) } }
  foreach ($k in $extras.Keys) { $linhas.Add("extra:" + $k + ";" + $extras[$k][0] + ";" + $extras[$k][1] + ";" + $extras[$k][2]) }
  Set-Content -Encoding utf8 $fontes $linhas; Write-Host ("Gravadas " + $extras.Count + " camadas extras em " + $fontes)
  Write-Host "Instalar agora: py C:\physis\physis-integracao-2026-11-25\ferramentas\bot_camadas.py --extras" }
