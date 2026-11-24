# Passo a passo FINAL · Sistema Physis, Instituto Physis, Casa Physis e M&A local (23/11/2026)
Pasta do sistema: **`C:\physis\physis-ma-20261122-1bd599e`** · Instituto ao lado: **`C:\physis\instituto-physis`** · banco do M&A: **`C:\physis\dados`**

Testado aqui, reproduzindo esse layout: clone do GitHub + atualização = **idêntico** à versão final (Sistema e Instituto);
1338 testes do Sistema e 1261 do Instituto OK; 17 de 17 páginas completas (10 do Sistema e 7 do Instituto); a sincronização
automática levou os módulos compartilhados ao Instituto, testou e fez o commit; a plataforma da Casa Physis abriu sem erro.
**Não testado aqui:** o próprio Windows (agenda, avisos de segurança, `setx`).

## Arquivos (área de arquivos, raiz)
| Arquivo | Tamanho | Vai para |
|---|---|---|
| atualizacao-physis-2026-11-22.patch | 560 KB | `C:\physis\physis-ma-20261122-1bd599e` |
| instalar_tudo.py | 7 KB | `C:\physis\physis-ma-20261122-1bd599e` |
| INSTALAR-PHYSIS.bat | 1 KB | `C:\physis\physis-ma-20261122-1bd599e` |
| atualizacao-instituto-2026-11-23.patch | 1,2 MB | `C:\physis\instituto-physis` |
| diagnostico_ma.py | 12 KB | `C:\physis` |

> **Como rodar um arquivo .py:** salve o arquivo (não cole o código no PowerShell, porque o PowerShell não entende Python).
> Depois, no PowerShell: `cd` até a pasta e `py nome-do-arquivo.py`.

---

## 1. Antes de tudo (5 min)
1. `winget install Python.Python.3.12` e `winget install Git.Git`, depois feche e abra o PowerShell.
2. Agendador de Tarefas → **PhysisMV** → botão direito em cada tarefa → **Desabilitar**. Feche a janela do M&A antigo.
3. Ache e copie o banco atual:
   ```
   Get-ChildItem C:\physis -Recurse -Filter physis-mv.db -ErrorAction SilentlyContinue | Select-Object FullName, LastWriteTime
   New-Item -ItemType Directory -Force C:\physis\copias | Out-Null
   Copy-Item "<caminho mostrado acima>" "C:\physis\copias\physis-mv-$(Get-Date -Format yyyyMMdd-HHmm).db"
   ```

## 2. Sistema Physis na pasta nova
1. Veja o que já está em `C:\physis\physis-ma-20261122-1bd599e`:
   ```
   cd "C:\physis\physis-ma-20261122-1bd599e"
   git log -1 --oneline
   ```
   - Se mostrar **6643e5b** ("Trabalho em andamento 22/11"), siga para o item 2.
   - Se der erro ou mostrar outro código: o conteúdo não é o do GitHub atual. Renomeie a pasta para `physis-ma-20261122-1bd599e-antigo`
     (não apague) e baixe de novo:
     ```
     cd C:\physis
     git clone https://github.com/Physis2026/Sistema-Physis physis-ma-20261122-1bd599e
     ```
     Se a pasta antiga tinha mudanças próprias, guarde-a e me mande o `git log --oneline -5` dela.
2. Copie **atualizacao-physis-2026-11-22.patch**, **instalar_tudo.py** e **INSTALAR-PHYSIS.bat** para `C:\physis\physis-ma-20261122-1bd599e`.
3. **Banco:** se o banco do passo 1.3 estava em `C:\physis\dados`, não faça nada (a versão nova usa essa pasta). Se estava
   em outro lugar, rode no PowerShell **como Administrador**:
   ```
   setx PHYSIS_MV_DADOS "<pasta onde está o physis-mv.db>" /M
   ```
   Depois feche e abra o PowerShell.
4. Botão direito em **INSTALAR-PHYSIS.bat** → **Executar como administrador** → **Sim**
   (bloqueado? PowerShell como administrador: `cd "C:\physis\physis-ma-20261122-1bd599e"` e depois `py instalar_tudo.py`). O que deve aparecer:
   - `[3/10] ... aplicada agora`
   - `[4/10] Telas, cópias e demonstrações ... OK`
   - `[6/10] Banco do M&A ... já existe`. **Se disser "criado", pare:** confira o item 3.
   - `PRONTO!`, e o M&A abre em http://127.0.0.1:8710/
   - Se aparecer **"o patch não encaixa"**: o GitHub mudou de novo. Não force; me avise.

## 3. Instituto Physis ao lado (integração)
```
cd C:\physis
git clone https://github.com/Physis2026/instituto-physis
cd instituto-physis
git checkout ciclo/2026-11-22
```
(A branch `ciclo` tem as correções de hoje, com 1261 testes OK. Peça a quem cuida do repositório para juntá-la na main.)
Copie **atualizacao-instituto-2026-11-23.patch** para `C:\physis\instituto-physis` e rode, **nesta ordem**:
```
git apply atualizacao-instituto-2026-11-23.patch
py "C:\physis\physis-ma-20261122-1bd599e\ferramentas\padronizar_paginas.py" --raiz C:\physis\instituto-physis --razao "Instituto Physis" --lista instituto
py ferramentas\sincronizar.py
py ferramentas\embutir_bases.py
py demos\gerar_demos.py
py ferramentas\montar_lab_inovastem.py
cd physis-hub
py -m unittest discover -s tests
cd ..
git add -A
git commit -m "Padronização das páginas do Instituto (fontes do guia, rodapé Instituto Physis, paleta do Instituto)"
```
Os testes devem terminar com **OK**. O rodapé do Instituto diz **"Instituto Physis"**: ele ainda não tem CNPJ, e a razão social não foi inventada.
A InovaSTEM fica sem esse rodapé, porque é marca própria.

## 4. Salvar no GitHub (branches separadas, sem mexer na main)
```
cd "C:\physis\physis-ma-20261122-1bd599e"
git checkout -b implementacao-2026-11-23
git add -A
git commit -m "Implementação final 22-23/11/2026"
git push -u origin implementacao-2026-11-23
cd C:\physis\instituto-physis
git checkout -b padronizacao-2026-11-23
git push -u origin padronizacao-2026-11-23
```
No GitHub, abra um *pull request* de cada branch e combine com quem fez o "trabalho em andamento" de 22/11.

## 5. Deixar rodando sem ninguém logado
Agendador → **PhysisMV** → em **bots_hora**, **atrasos_8h**, **resumo_7h** e **revisao_semanal**: Propriedades → **Executar estando o usuário
conectado ou não** + **privilégios mais altos** → OK → senha. Na tarefa **painel**: Disparadores → **Na inicialização**.
Apague as tarefas antigas desabilitadas que não estão nessa lista.
Se a tarefa rodar com outro usuário sem nome e e-mail no Git, a sincronização agora usa uma identidade própria e avisa se o commit falhar.

## 6. Conferir a integração (o teste do M&A que está rodando)
Salve **diagnostico_ma.py** em `C:\physis` e rode:
```
cd C:\physis
py diagnostico_ma.py "C:\physis\physis-ma-20261122-1bd599e"
```
- Seção 7 (Integração): "Instituto Physis em C:\physis\instituto-physis" e a última sincronização.
- Seção 8: idealmente "Nada". Mande o arquivo **diagnostico-ma-*.md** que ele cria, se tiver algum item.
- No M&A: a aba **Monitoramento** mostra o Instituto, a Casa Physis, o Marketing e os bots; a aba **Alertas** não deve ter "páginas do Instituto".
- Forçar a sincronização agora:
  ```
  cd "C:\physis\physis-ma-20261122-1bd599e\physis-hub"
  py -m physis_hub.mv_cli bots sincronizacao
  ```
  O resultado esperado é "Instituto Physis: em dia" ou "atualizado, testado e com commit".

## 7. Casa Physis (plataforma do cliente, opcional no servidor)
```
cd "C:\physis\physis-ma-20261122-1bd599e\physis-hub"
py montar_clientes.py --saida C:\physis\plataformas --so casa-physis-inicial
cd C:\physis\plataformas\physis-casa-physis-inicial
$env:PHYSIS_PORTA="8701"; $env:PHYSIS_BANCO="C:\physis\dados\casa-physis.db"; py -m physis_hub.servidor
```
Abra http://127.0.0.1:8701/ e crie o primeiro acesso. A Gestão interna (/gestao/) **não** existe ali, porque é só do servidor da Physis, e isso é esperado.

## 8. Computador reserva
Faça os passos 1, 2 (sem o item 4) e 3 no mesmo layout. Depois crie só o sinal de vida:
```
schtasks /Create /F /SC HOURLY /TN "PhysisMV\sinal_de_vida" /TR "cmd /c cd /d C:\physis\physis-ma-20261122-1bd599e\physis-hub && py -3 -m physis_hub.mv_cli bots vigia"
```
Se o principal parar:
1. Copie a cópia mais nova de `OneDrive\Documents\Sistema Physis\28_Physis_MV\backup` para `C:\physis\dados\physis-mv.db`.
2. Rode o **INSTALAR-PHYSIS.bat** como administrador.
3. Apague a tarefa `sinal_de_vida`.
