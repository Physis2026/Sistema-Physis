# verificar_noite.ps1 · a rodada das 02:30 funcionou? versão em uso, portas, M&A e fila dos bots (27/11/2026)
#   pwsh -ExecutionPolicy Bypass -File C:\physis\verificar_noite.ps1
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$P = "C:\physis"; $Int = "$P\physis-integracao-2026-11-25"; $esperado = "80b9d2f"
function L($t, $cor = "Gray") { Write-Host $t -ForegroundColor $cor }
L "== 1. Tarefa da noite (\Physis\noturno)" Cyan
$t = schtasks /Query /TN "\Physis\noturno" /V /FO LIST 2>$null | Out-String
if (-not $t) { L "  [FALHA] tarefa \Physis\noturno não existe" Red } else {
  ($t -split "\r?\n") | Where-Object { $_ -match '^(Status|Last Run Time|Last Result|Next Run Time|Task To Run|Hora da última execução|Último resultado|Próxima execução|Tarefa a ser executada|Executar como usuário|Run As User)' } | ForEach-Object { L ("  " + $_.Trim()) }
  if ($t -match '(Last Result|Último resultado):\s*(\S+)') { if ($Matches[2] -in @("-2147024894", "0x80070002")) { L "  [FALHA] código 0x80070002 = ARQUIVO NÃO ENCONTRADO: a tarefa aponta para um programa ou script que não existe (rode o conserto do passo 1)" Red }
    elseif ($Matches[2] -in @("0", "0x0")) { L "  [ OK ] última execução terminou sem erro (código 0)" Green } else { L ("  [ATENÇÃO] código da última execução: " + $Matches[2]) Yellow } } }
L "== 2. Relatório da noite" Cyan
$u = "$P\noturno\ULTIMO.md"
if (Test-Path $u) { $r = Get-Content $u; $quando = (Get-Item $u).LastWriteTime
  L ("  " + $r[0] + "  (arquivo de " + $quando.ToString("dd/MM HH:mm") + ")")
  if ($quando -lt (Get-Date).Date.AddHours(2)) { L "  [ATENÇÃO] o relatório não é desta madrugada: a rodada das 02:30 de hoje não terminou ou não rodou" Yellow }
  $fa = @($r | Where-Object { $_ -match '\[FALHA\]' }); $av = @($r | Where-Object { $_ -match '\[AVISO\]' })
  L ("  falhas: " + $fa.Count + " · avisos: " + $av.Count) $(if ($fa.Count) { "Red" } else { "Green" })
  $fa + $av | ForEach-Object { L ("    " + $_) } }
else { L "  [FALHA] não há C:\physis\noturno\ULTIMO.md (a noite nunca terminou)" Red }
$log = Get-ChildItem "$P\noturno\*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime | Select-Object -Last 1
if ($log) { L ("  último log: " + $log.Name + " (" + $log.LastWriteTime.ToString("dd/MM HH:mm") + ")") }
L "== 3. Versão em uso" Cyan
$v = (git -C $Int log --oneline -1 2>$null); L ("  integração: " + $v)
if ($v -match "^$esperado") { L "  [ OK ] pacote $esperado aplicado" Green } else { L "  [ATENÇÃO] ainda não está no pacote $esperado (veja C:\physis\entrada-pacotes\recusados e o testes-pacote-*.log)" Yellow }
Get-ChildItem "$P\entrada-pacotes\recusados\*.zip" -ErrorAction SilentlyContinue | ForEach-Object { L ("  recusado: " + $_.Name) Yellow }
L "== 4. Portas" Cyan
foreach ($p in 8700, 8701, 8702, 8703, 8704, 8705, 8710) {
  try { $w = Invoke-WebRequest "http://127.0.0.1:$p/" -UseBasicParsing -TimeoutSec 10 -MaximumRedirection 3; L ("  " + $p + " ok (" + $w.StatusCode + ")") Green }
  catch { $c = $_.Exception.Response.StatusCode.value__; if ($c -in 401, 403) { L ("  " + $p + " ok (pede login)") Green } else { L ("  " + $p + " SEM RESPOSTA: " + $_.Exception.Message) Red } } }
L "== 5. M&A (8710): a tela que o navegador recebe e a fila dos bots" Cyan
foreach ($c in "/", "/mv", "/mv.html") { try { $w = Invoke-WebRequest ("http://127.0.0.1:8710" + $c) -UseBasicParsing -TimeoutSec 10
    if ($w.Content -match 'atualizarSozinho') { L ("  " + $c + ": tela com atualização automática (a cada 60 s) · Cache-Control: " + $w.Headers["Cache-Control"]) Green; break } } catch { } }
$db = Get-ChildItem $P -Recurse -Filter "mv*.db" -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch 'backup' } | Sort-Object LastWriteTime | Select-Object -Last 1
if ($db) { L ("  banco do M&A: " + $db.FullName + " (gravado " + $db.LastWriteTime.ToString("dd/MM HH:mm") + ")")
  $q = "import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print('pedidos por estado:',dict(c.execute(""SELECT estado,COUNT(*) FROM mv_pedido_bot GROUP BY estado"").fetchall()));" +
       "print('ultimas execucoes:');[print(' ',r) for r in c.execute(""SELECT bot,datetime(inicio,'unixepoch','localtime'),substr(resumo,1,70),substr(erro,1,90) FROM mv_execucao ORDER BY inicio DESC LIMIT 8"")]"
  py -c $q $db.FullName 2>&1 | ForEach-Object { L ("  " + $_) } }
$fc = Get-ChildItem $P -Recurse -Filter "fila-claude.md" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($fc) { L ("  fila de pedidos sem resposta: " + $fc.FullName) ; Get-Content $fc.FullName | Select-Object -First 12 | ForEach-Object { L ("    " + $_) } }
L "== 6. Camadas" Cyan
if (Test-Path "$P\camadas\pendencias-camadas.md") { Get-Content "$P\camadas\pendencias-camadas.md" | ForEach-Object { L ("  " + $_) } } else { L "  (ainda sem pendencias-camadas.md: aparece depois da primeira noite com o pacote novo)" }
