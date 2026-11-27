# physis_noite.ps1 · O ÚNICO arquivo para rodar: backup, atualização, instalações, camadas e testes (26/11/2026)
#   Primeira vez (à mão, PowerShell 7 como administrador):  pwsh -ExecutionPolicy Bypass -File C:\physis\physis_noite.ps1
#   Depois roda SOZINHO toda noite às 02:30 (ele mesmo se registra como \Physis\noturno). Pacote novo: deixe o .zip em
#   C:\physis ou em C:\physis\entrada-pacotes; ele aplica só se TODOS os testes passarem e volta atrás se o teste final falhar.
# Ordem: 0 backup completo da versão atual -> 1 pacotes (sistema e Instituto) -> 2 o que falta instalar e 2c atualização dos programas (programas, extras,
#        Linux no WSL com OpenFOAM/GROMACS/FEniCSx/CalculiX) -> 3 camadas -> 4 backup diário -> 5 teste final (volta atrás se
#        falhar) -> 6 zips da equipe (só quando entrou pacote novo e tudo passou). Relatório: C:\physis\noturno\ULTIMO.md
[Console]::OutputEncoding = [Text.Encoding]::UTF8; $env:PYTHONUTF8 = "1"; $ProgressPreference = "SilentlyContinue"
$P = "C:\physis"; $At = "$P\atualizar_physis.ps1"; $Repo = "$P\physis-ma-20261122-1bd599e"; $Ent = "$P\entrada-pacotes"; $Dir = "$P\noturno"
# 27/11/2026: o código em uso é o da pasta de integração (o pacote avança ela); a pasta antiga só guarda o histórico do git
$Cod = if (Test-Path "$P\physis-integracao-2026-11-25\ferramentas") { "$P\physis-integracao-2026-11-25" } else { $Repo }
New-Item -ItemType Directory -Force $Ent, "$Ent\aplicados", "$Ent\recusados", $Dir | Out-Null
$dia = Get-Date -Format "yyyyMMdd"; $rel = "$Dir\$dia.md"; $L = [System.Collections.Generic.List[string]]::new(); $nFalhas = 0
$estadoArq = "$Dir\estado.json"; $estado = @{}; if (Test-Path $estadoArq) { (Get-Content $estadoArq -Raw | ConvertFrom-Json).psobject.Properties | ForEach-Object { $estado[$_.Name] = $_.Value } }
function OK($t) { $script:L.Add("- [ OK  ] " + $t); Write-Host ("[ OK  ] " + $t) }
function AV($t) { $script:L.Add("- [AVISO] " + $t); Write-Host ("[AVISO] " + $t) }
function FA($t) { $script:L.Add("- [FALHA] " + $t); $script:nFalhas++; Write-Host ("[FALHA] " + $t) }
function Sec($t) { $script:L.Add(""); $script:L.Add("## " + $t); Write-Host ""; Write-Host ("==== " + $t + " ====") }
function PS1([string[]]$argsPs) { & pwsh -NoProfile -ExecutionPolicy Bypass -File @argsPs 2>&1 | Out-String }
# 26/11/2026: o log pode terminar com avisos depois do "OK": lê o arquivo todo; precisa ter "Ran N tests", "OK" e nenhum FAIL/ERROR/FAILED
function TestesOK { $tl = Get-ChildItem "$P\testes-pacote-*.log" | Sort-Object LastWriteTime | Select-Object -Last 1; if (-not $tl) { return $false }
  $tx = Get-Content $tl.FullName -Raw; return (($tx -cmatch '(?m)^Ran \d+ test') -and ($tx -cmatch '(?m)^OK') -and ($tx -cnotmatch '(?m)^(FAIL|ERROR):|^FAILED')) }
$L.Add("# Noite Physis " + (Get-Date -Format "dd/MM/yyyy HH:mm") + " · " + $env:COMPUTERNAME)
foreach ($req in $At, "$P\teste_final.ps1", "$P\backup_diario.ps1", "$P\emitir_camadas.ps1") { if (-not (Test-Path $req)) { FA ("falta " + $req) } }

Sec "0. Backup completo da versão atual (antes de mudar qualquer coisa)"
Push-Location $Repo; $o = py ferramentas\backup_completo.py --sem-documentos 2>&1 | Out-String; $c0 = $LASTEXITCODE; Pop-Location
$o | Set-Content "$Dir\$dia-backup-completo.log"
if ($c0 -eq 0) { OK "backup completo (código, bancos, sites, configuração) em C:\physis\backup-completo-*" }
else { FA "backup completo falhou: veja o log (nada foi atualizado)"; $L | Set-Content -Encoding utf8 $rel; Copy-Item $rel "$Dir\ULTIMO.md" -Force; exit 1 }

Sec "1. Pacotes novos"
$antes = (git -C $Repo rev-parse HEAD 2>$null); $aplicou = $false
Get-ChildItem "$P\pacote-*.zip", "$P\inovastem-*.zip" -ErrorAction SilentlyContinue | Where-Object { -not $estado[$_.Name] } | ForEach-Object { Copy-Item $_.FullName $Ent -Force }
$pac = Get-ChildItem "$Ent\pacote-*.zip" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
if ($pac) {
  Unblock-File $pac.FullName; $s = PS1 @($At, "-Etapa", "pacote", "-Arquivo", $pac.FullName)
  if (TestesOK) {
    $s = PS1 @($At, "-Etapa", "hub", "-Confirmo")
    foreach ($cli in @(@("casa-physis-inicial", "8701"), @("physis-site", "8703"))) { $s = PS1 @($At, "-Etapa", "cliente", "-Org", $cli[0], "-Porta", $cli[1], "-Confirmo") }
    $estado[$pac.Name] = (Get-Date).ToString("o"); Move-Item $pac.FullName "$Ent\aplicados\" -Force; OK ("sistema: " + $pac.Name + " aplicado (todos os testes OK)"); $aplicou = $true }
  else { $estado[$pac.Name] = "recusado"; Move-Item $pac.FullName "$Ent\recusados\" -Force; FA ("sistema: " + $pac.Name + " RECUSADO: testes falharam (portas não mudaram)") } }
else { OK "sistema: nenhum pacote novo" }
Get-ChildItem "$Ent\pacote-*.zip" -ErrorAction SilentlyContinue | ForEach-Object { $estado[$_.Name] = "substituido"; Move-Item $_.FullName "$Ent\aplicados\" -Force }
# -cmatch abaixo: "parado PID" (porta parada) NÃO é falha; só "PARADO:" ou teste FAIL/ERROR
$ins = Get-ChildItem "$Ent\inovastem-*.zip" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
if ($ins) {
  Unblock-File $ins.FullName; $s1 = PS1 @($At, "-Etapa", "inovastem", "-Arquivo", $ins.FullName, "-Confirmo"); $s2 = PS1 @($At, "-Etapa", "inovastem", "-Org", "gsa", "-Arquivo", $ins.FullName, "-Confirmo")
  if (($s1 + $s2) -cmatch 'PARADO:|(?m)^FAILED|(?m)^(FAIL|ERROR):') { $estado[$ins.Name] = "recusado"; Move-Item $ins.FullName "$Ent\recusados\" -Force; FA ("Instituto: " + $ins.Name + " recusado (testes)") }
  else { $estado[$ins.Name] = (Get-Date).ToString("o"); Move-Item $ins.FullName "$Ent\aplicados\" -Force; OK ("Instituto: " + $ins.Name + " aplicado (InovaSTEM 8702 e GSA 8705)"); $aplicou = $true } }
else { OK "Instituto: nenhum pacote novo" }
Get-ChildItem "$Ent\inovastem-*.zip" -ErrorAction SilentlyContinue | ForEach-Object { $estado[$_.Name] = "substituido"; Move-Item $_.FullName "$Ent\aplicados\" -Force }

Sec "1b. Scripts do Windows que vieram no pacote (ferramentas\windows -> C:\physis)"
$wf = "$Cod\ferramentas\windows"; $nScr = 0
if (Test-Path $wf) { foreach ($x in Get-ChildItem $wf -Filter *.ps1) { $dst = Join-Path $P $x.Name
    if (-not (Test-Path $dst) -or (Get-FileHash $dst).Hash -ne (Get-FileHash $x.FullName).Hash) { Copy-Item $x.FullName $dst -Force; Unblock-File $dst; $nScr++; OK ("script atualizado: " + $x.Name) } } }
if (-not $nScr) { OK "scripts do Windows já estão na versão do pacote" }

Sec "2. O que falta instalar"
if (Test-Path "$P\instalar_modulos.ps1") {
  $tab = PS1 @("$P\instalar_modulos.ps1"); $grupos = @("base", "mapas", "servicos", "engenharia", "eletrica", "firmware", "ciencia", "automacao", "ia")
  foreach ($g in $grupos) { if ($tab -match ("(?m)" + $g + ".*FALTA")) { $s = PS1 @("$P\instalar_modulos.ps1", "-Instalar", $g); OK ("grupo " + $g + ": instalação tentada") } }
  $tab2 = PS1 @("$P\instalar_modulos.ps1"); $falta = @($tab2 -split "\r?\n" | Where-Object { $_ -match 'FALTA' })
  if ($falta.Count) { AV ("ainda faltam " + $falta.Count + " programa(s): " + (($falta | Select-Object -First 8) -join " | ")) } else { OK "todos os programas da lista instalados" } }
if (Test-Path "$P\instalar_extras.ps1") { $s = PS1 @("$P\instalar_extras.ps1"); if ($s -match 'FALHA') { AV "extras (OpenSim/Elmer/Bonsai): download incompleto, tenta de novo amanhã" } else { OK "extras (OpenSim, Elmer, Bonsai) conferidos" } }
# Linux no WSL: OpenFOAM, GROMACS, FEniCSx (dolfinx) e CalculiX. Ubuntu instalado sem perguntas (usuário root).
$distros = (wsl -l -q 2>$null | Out-String) -replace "`0", ""
if ($distros -notmatch 'Ubuntu') {
  wsl --install -d Ubuntu --no-launch 2>&1 | Out-Null
  $ub = Get-Command ubuntu.exe -ErrorAction SilentlyContinue; if ($ub) { & $ub.Source install --root 2>&1 | Out-Null }
  $distros = (wsl -l -q 2>$null | Out-String) -replace "`0", ""
  if ($distros -match 'Ubuntu') { OK "Ubuntu instalado no WSL" } else { AV "Ubuntu no WSL pedido: pode precisar REINICIAR o PC uma vez; a próxima noite continua" } }
if ($distros -match 'Ubuntu') {
  $lin = wsl -d Ubuntu -u root -- bash -lc "export DEBIAN_FRONTEND=noninteractive; apt-get update -qq >/dev/null; for p in openfoam gromacs calculix-ccx python3-dolfinx; do dpkg -s `$p >/dev/null 2>&1 || apt-get install -y -qq `$p >/dev/null 2>&1; dpkg -s `$p >/dev/null 2>&1 && echo OK:`$p || echo FALTA:`$p; done" 2>&1 | Out-String
  foreach ($ln in ($lin -split "\r?\n" | Where-Object { $_ -match '^(OK|FALTA):' })) { if ($ln -like "OK:*") { OK ("Linux: " + $ln.Substring(3)) } else { AV ("Linux: " + $ln.Substring(6) + " não instalou (tenta de novo amanhã)") } }
  wsl --set-default Ubuntu 2>&1 | Out-Null }

# openEMS (zip do Windows baixado à mão) e VOLTTRON (Linux: ambiente próprio no Ubuntu do WSL), 26/11/2026
$procura = @("$P\dados-brutos\instaladores", "$env:USERPROFILE\Downloads", $P)
if (-not (Get-ChildItem "C:\openEMS" -Recurse -Filter openEMS.exe -ErrorAction SilentlyContinue | Select-Object -First 1)) {
  $oz = Get-ChildItem $procura -Filter "openEMS*.zip" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
  if ($oz) { try { Expand-Archive $oz.FullName "C:\openEMS" -Force; OK ("openEMS extraído em C:\openEMS (" + $oz.Name + ")") } catch { AV ("openEMS: " + $_.Exception.Message) } }
  else { AV "openEMS: zip do Windows não encontrado (C:\physis\dados-brutos\instaladores ou Downloads)" } }
else { OK "openEMS presente em C:\openEMS" }
if ($distros -match 'Ubuntu') {
  $vf = Get-ChildItem $procura -Filter "volttron*" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
  $orig = if ($vf) { "/mnt/" + $vf.FullName.Substring(0, 1).ToLower() + $vf.FullName.Substring(2).Replace('\', '/') } else { "volttron" }
  $vo = wsl -d Ubuntu -u root -- bash -lc ("test -x /opt/volttron/bin/volttron && echo JA || { apt-get install -y -qq python3-venv >/dev/null 2>&1; python3 -m venv /opt/volttron && { /opt/volttron/bin/pip install -q '" + $orig + "' >/dev/null 2>&1 || /opt/volttron/bin/pip install -q volttron >/dev/null 2>&1; }; test -x /opt/volttron/bin/volttron && echo OK || echo FALTA; }") 2>&1 | Out-String
  if ($vo -match 'JA|OK') { OK "VOLTTRON no Ubuntu do WSL (/opt/volttron)" } else { AV ("VOLTTRON não instalou a partir de " + $orig + " (tenta de novo amanhã)") } }

# OpenSEO (auditoria de SEO, MIT) no Ubuntu do WSL com Docker, porta 8720; transcrição local (faster-whisper)
if ($distros -match 'Ubuntu') {
  $so = wsl -d Ubuntu -u root -- bash -lc "command -v docker >/dev/null || apt-get install -y -qq docker.io >/dev/null 2>&1; service docker start >/dev/null 2>&1; sleep 3; docker ps -a --format '{{.Names}}' | grep -qx openseo || docker run -d --name openseo --restart unless-stopped -p 8720:3000 -e OPENSEO_ALLOW_PRIVATE=true -v openseo-data:/data ghcr.io/alexsilver8/open-seo >/dev/null 2>&1; docker start openseo >/dev/null 2>&1; docker ps --format '{{.Names}}' | grep -qx openseo && echo OK || echo FALTA" 2>&1 | Out-String
  if ($so -match 'OK') { OK "OpenSEO: http://127.0.0.1:8720" } else { AV "OpenSEO não subiu (Docker no WSL)" } }
py -c "import faster_whisper" 2>$null; if ($LASTEXITCODE -ne 0) { py -m pip install -q faster-whisper 2>&1 | Out-Null }
py -c "import faster_whisper" 2>$null; if ($LASTEXITCODE -eq 0) { OK "faster-whisper pronto (Programas > Whisper)" } else { AV "faster-whisper não instalou" }

Sec "2c. Atualização dos programas (winget), com o teste final logo depois (passo 5)"
# Ficam de fora os que quebram integrações numa troca de versão: Blender (o Bonsai depende da versão do Python dele),
# FreeCAD (macros), QGIS (caminho do GDAL) e Python (os pacotes pip). Esses: só à mão, com o teste final em seguida.
$fixos = "BlenderFoundation.Blender", "FreeCAD.FreeCAD", "OSGeo.QGIS", "Python.Python.3.12"
$lista = winget upgrade --accept-source-agreements --disable-interactivity 2>$null | Out-String
$ids = @(($lista -split "\r?\n") | ForEach-Object { if ($_ -match '\s([A-Za-z0-9][\w.+-]*\.[\w.+-]+)\s+\S+\s+\S+\s+winget\s*$') { $Matches[1] } } | Where-Object { $_ -notin $fixos } | Select-Object -Unique)
if (-not $ids) { OK "programas: nada para atualizar" }
foreach ($id in $ids) {
  winget upgrade --id $id --exact --silent --accept-source-agreements --accept-package-agreements --disable-interactivity 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { OK ("atualizado: " + $id) } else { AV ("não atualizou: " + $id + " (código " + $LASTEXITCODE + ")") } }
foreach ($f in $fixos) { if ($lista -match [regex]::Escape($f)) { AV ("há versão nova de " + $f + ": atualizar à mão e rodar o teste_final.ps1") } }

Sec "3. Camadas: básicas (inclui o risco do SGB, direto do serviço oficial), OpenGeoHub, inventário e EXTRAS"
$s = PS1 @("$P\emitir_camadas.ps1"); $s | Set-Content "$Dir\$dia-camadas.log"
$fl = ($s -split "\r?\n" | Where-Object { $_ -match '^Faltam' }) -join ""
if ($fl -and $fl -notmatch 'Faltam: *(nenhuma)? *·') { AV ("camadas básicas: " + $fl) } else { OK "camadas básicas completas (12/12)" }
if (Test-Path "$P\baixar_opengeohub.ps1") { $s = PS1 @("$P\baixar_opengeohub.ps1", "-Baixar"); $s | Set-Content "$Dir\$dia-opengeohub.log"
  $nOk = ([regex]::Matches($s, '(?m)^\s+OK ')).Count; $nPul = ([regex]::Matches($s, 'já existe')).Count; $nErr = ([regex]::Matches($s, '\[(ERRO|FALTA)\]')).Count
  if ($nErr) { AV ("OpenGeoHub: " + $nErr + " camada(s) com erro (veja " + $dia + "-opengeohub.log); " + ($nOk + $nPul) + " ok") } else { OK ("OpenGeoHub: " + ($nOk + $nPul) + " camadas (" + $nOk + " novas)") } }
if (Test-Path "$P\inventariar_camadas.ps1") { $s = PS1 @("$P\inventariar_camadas.ps1", "-Gravar"); $s | Set-Content "$Dir\$dia-inventario.log"
  if ($s -match 'Gravadas (\d+)') { OK ("inventário: " + $Matches[1] + " camadas extras registradas em fontes-camadas.txt") } else { AV "inventário não gravou: veja o log" } }
$s = py "$Cod\ferramentas\bot_camadas.py" --extras 2>&1 | Out-String; $s | Set-Content "$Dir\$dia-extras.log"
$ex = ($s -split "\r?\n" | Where-Object { $_ -match '^Extras instaladas' }) -join ""
$exFalta = @($s -split "\r?\n" | Where-Object { $_ -match '^x_\S+\s+falta' })
if ($ex) { if ($exFalta.Count) { AV ($ex + " · faltam: " + (($exFalta | ForEach-Object { ($_ -split '\s+')[0] }) -join ", ")) } else { OK $ex } } else { FA "bot das camadas extras não rodou (veja o log)" }
# pendências de camadas: o que falta vira lista com o motivo, no relatório e em pendencias-camadas.md (a equipe vê pela manhã)
$pend = [System.Collections.Generic.List[string]]::new(); $pend.Add("# Pendências de camadas · " + (Get-Date -Format "dd/MM/yyyy HH:mm")); $pend.Add("")
Get-Content "$Dir\$dia-camadas.log" | Where-Object { $_ -match '^\w+\s+falta' } | ForEach-Object { $pend.Add("- básica: " + $_.Trim()) }
$exFalta | ForEach-Object { $pend.Add("- extra: " + $_.Trim()) }
if ($pend.Count -eq 2) { $pend.Add("- nenhuma") }
$pend | Set-Content -Encoding utf8 "$P\camadas\pendencias-camadas.md"
$L.Add(""); $L.Add("### Pendências de camadas"); $pend | Select-Object -Skip 2 | ForEach-Object { $L.Add($_) }

Sec "4. Backup diário"
$s = PS1 @("$P\backup_diario.ps1"); if ($s -match '-> ok') { OK "backup diário feito" } else { AV "backup diário sem confirmação: veja C:\physis\backup-diario\ultimos-backups.log" }

Sec "5. Teste final"
$s = PS1 @("$P\teste_final.ps1")
$tf = Get-ChildItem "$P\teste-final-*.md" | Sort-Object LastWriteTime | Select-Object -Last 1
$m = if ($tf) { (Select-String -Path $tf.FullName -Pattern 'Resultado: (\d+) falha' | Select-Object -Last 1).Matches } else { $null }
$falhasTf = if ($m) { [int]$m[0].Groups[1].Value } else { 99 }
if ($falhasTf -eq 0) { OK ("teste final sem falhas (" + $tf.Name + ")") }
else {
  FA ("teste final com " + $falhasTf + " falha(s): " + $(if ($tf) { $tf.Name } else { "sem relatório" }))
  if ($aplicou -and $antes) {
    git -C $Repo reset --hard $antes | Out-Null; $s = PS1 @($At, "-Etapa", "reiniciar", "-Porta", "8700", "-Confirmo")
    foreach ($cli in @(@("casa-physis-inicial", "8701"), @("physis-site", "8703"))) { $s = PS1 @($At, "-Etapa", "voltar", "-Org", $cli[0], "-Porta", $cli[1], "-Confirmo") }
    AV ("VOLTOU à versão anterior do hub (" + $antes.Substring(0, 7) + ") e das instalações 8701/8703") } }

Sec "5b. Regressão no navegador (todas as abas, 1280 e 360 px, sem conta: demonstrações, laboratório e M&A local)"
py -c "import playwright" 2>$null; if ($LASTEXITCODE -ne 0) { py -m pip install -q playwright 2>&1 | Out-Null }
if (-not (Test-Path "$env:LOCALAPPDATA\ms-playwright\chromium-*")) { py -m playwright install chromium 2>&1 | Out-Null }
Push-Location $Repo; $o = py ferramentas\testes-navegador\regressao_navegador.py --saida "$Dir\$dia-navegador.md" 2>&1 | Out-String; $cn = $LASTEXITCODE; Pop-Location
$rn = ($o -split "\r?\n" | Where-Object { $_ -match '^\*\*Resultado' }) -join ""
if ($cn -eq 0) { OK ("navegador: " + $rn + " (" + $dia + "-navegador.md)") } elseif ($cn -eq 2) { AV "navegador: Playwright não instalou (tenta de novo amanhã)" } else { FA ("navegador: " + $rn + " (ver " + $dia + "-navegador.md)") }

Sec "6. Zips da equipe (por pessoa + páginas)"
if ($aplicou -and $nFalhas -eq 0) {
  $saida = "$P\compartilhar-" + (Get-Date -Format "yyyy-MM-dd"); Push-Location $Repo; $o = py ferramentas\emitir_compartilhamento.py --saida $saida 2>&1 | Out-String; $c6 = $LASTEXITCODE; Pop-Location
  if ($c6 -eq 0) { OK ("zips da equipe prontos e testados: " + $saida + "\kits\por-pessoa e " + $saida + "\paginas.zip") } else { FA ("compartilhamento barrado pelos testes: " + $saida + "\RELATORIO-TESTES.md") } }
else { OK "sem pacote novo (ou com falha): zips da equipe não refeitos" }

Sec "7. Agenda"
$tarefa = Get-ScheduledTask -TaskPath "\Physis\" -TaskName "noturno" -ErrorAction SilentlyContinue
$alvo = "$P\physis_noite.ps1"
if (-not $tarefa -or ($tarefa.Actions[0].Arguments -notmatch [regex]::Escape($alvo))) {
  try {
    $acao = New-ScheduledTaskAction -Execute "pwsh.exe" -Argument ("-NoProfile -ExecutionPolicy Bypass -File " + [char]34 + $alvo + [char]34)
    $gat = New-ScheduledTaskTrigger -Daily -At "02:30"
    $cfg = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Hours 6)
    $quem = New-ScheduledTaskPrincipal -UserId ($env:USERDOMAIN + "\" + $env:USERNAME) -LogonType S4U -RunLevel Highest
    Register-ScheduledTask -TaskPath "\Physis\" -TaskName "noturno" -Action $acao -Trigger $gat -Settings $cfg -Principal $quem -Force | Out-Null
    OK "tarefa \Physis\noturno: toda noite às 02:30 roda este arquivo" }
  catch { FA ("não registrou a tarefa da noite (rode como administrador): " + $_.Exception.Message) } }
else { OK "tarefa \Physis\noturno já aponta para este arquivo" }

$estado | ConvertTo-Json | Set-Content -Encoding utf8 $estadoArq
$L.Add(""); $L.Add("**Resultado: " + $nFalhas + " falha(s).** " + $(if ($nFalhas) { "Mande este arquivo ao agente." } else { "Tudo certo." }))
$L | Set-Content -Encoding utf8 $rel; Copy-Item $rel "$Dir\ULTIMO.md" -Force
Get-ChildItem $Dir -Filter "*.log" | Where-Object LastWriteTime -lt (Get-Date).AddDays(-30) | Remove-Item -ErrorAction SilentlyContinue
Write-Host ""; Write-Host ("Relatório: " + $rel)
exit $(if ($nFalhas) { 1 } else { 0 })
