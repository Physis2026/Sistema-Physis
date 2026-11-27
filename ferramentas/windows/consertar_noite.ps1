# consertar_noite.ps1 · registra de novo a tarefa \Physis\noturno com o caminho certo do PowerShell 7 e confere os arquivos (27/11/2026)
#   pwsh -ExecutionPolicy Bypass -File C:\physis\consertar_noite.ps1            (só registra e confere)
#   pwsh -ExecutionPolicy Bypass -File C:\physis\consertar_noite.ps1 -RodarAgora (registra e já dispara a rodada; reinicia as portas no meio)
param([switch]$RodarAgora)
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$P = "C:\physis"; $ok = $true
Write-Host "== Arquivos que a noite precisa"
foreach ($f in "physis_noite.ps1", "atualizar_physis.ps1", "teste_final.ps1", "backup_diario.ps1", "emitir_camadas.ps1", "inventariar_camadas.ps1", "baixar_opengeohub.ps1") {
  if (Test-Path "$P\$f") { Unblock-File "$P\$f"; Write-Host ("  ok    " + $f) } else { Write-Host ("  FALTA " + $f + " (copie de outputs para C:\physis)") -ForegroundColor Red; if ($f -eq "physis_noite.ps1") { $ok = $false } } }
$pac = Get-ChildItem "$P\pacote-*.zip", "$P\entrada-pacotes\pacote-*.zip" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
Write-Host ("  pacote esperando: " + $(if ($pac) { $pac.Name } else { "nenhum (copie o pacote-XXXXXXX.zip mais novo para C:\physis)" }))
Write-Host "== Tarefa atual"
$x = schtasks /Query /TN "\Physis\noturno" /V /FO LIST 2>$null | Out-String
($x -split "\r?\n") | Where-Object { $_ -match '^(Tarefa a ser executada|Task To Run|Executar como usuário|Run As User)' } | ForEach-Object { Write-Host ("  " + $_.Trim()) }
if (-not $ok) { Write-Host "Sem C:\physis\physis_noite.ps1 não adianta registrar: copie o arquivo e rode de novo." -ForegroundColor Red; exit 1 }
$pw = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (-not $pw) { $pw = "C:\Program Files\PowerShell\7\pwsh.exe" }
if (-not (Test-Path $pw)) { Write-Host ("PowerShell 7 não encontrado em " + $pw) -ForegroundColor Red; exit 1 }
$acao = New-ScheduledTaskAction -Execute $pw -Argument '-NoProfile -ExecutionPolicy Bypass -File "C:\physis\physis_noite.ps1"' -WorkingDirectory $P
$gat = New-ScheduledTaskTrigger -Daily -At "02:30"
$conf = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Hours 6) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$quem = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Highest
Register-ScheduledTask -TaskPath "\Physis\" -TaskName "noturno" -Action $acao -Trigger $gat -Settings $conf -Principal $quem -Force | Out-Null
Write-Host ("== Registrada de novo: " + $pw + " -File C:\physis\physis_noite.ps1 · todo dia 02:30 · roda com a sua conta logada (o WSL e o py precisam dela) · se o PC estiver desligado às 02:30, roda ao ligar") -ForegroundColor Green
if ($RodarAgora) { Start-ScheduledTask -TaskPath "\Physis\" -TaskName "noturno"; Write-Host "Disparada agora. Acompanhe: Get-Content C:\physis\noturno\ULTIMO.md (aparece no fim) ou os .log em C:\physis\noturno" }
