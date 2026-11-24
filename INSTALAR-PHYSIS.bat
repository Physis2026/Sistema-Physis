@echo off
rem Instalador de um clique do Physis M&A. Pode rodar de novo quantas vezes quiser.
cd /d "%~dp0"
set INST=ferramentas\instalar_tudo.py
if not exist "%INST%" set INST=instalar_tudo.py
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 "%INST%" %*
) else (
  python "%INST%" %*
)
echo.
pause
