# Guia passo a passo: Sistema Physis no servidor local, bots, IA Physis e sites
Versão de 22/11/2026. Escrito a partir dos scripts do repositório (`mv_cli.py`, `instalar.ps1`, `instalar.sh`, `mv_servidor.py`).
Onde o guia diz **[CONFERIR]**, não foi possível testar daqui (sem acesso ao seu computador nem à internet geral).

Convenções: **negrito** = o que clicar ou escolher; `código` = o que digitar e depois apertar **Enter**.
Pastas usadas: código em `C:\physis\physis-sistema`, dados do M&A em `C:\physis\dados` (padrão do próprio M&A).

---

## Parte 0 · Correção urgente do link da Gestão (5 minutos)
Só uma linha muda: o link "Gestão" da faixa da Gestão interna apontava para `gestao-physis.html` (não existe).

1. Copie `URGENTE-link-gestao.patch` para `C:\physis\physis-sistema`.
2. Abra o **PowerShell** (tecla **Windows**, digite `PowerShell`, clique em **Windows PowerShell**). Não precisa ser Administrador.
3. `cd C:\physis\physis-sistema`
4. `git status` → deve dizer "nothing to commit, working tree clean". Se listar arquivos alterados, **pare** e me mande a lista.
5. `git apply --check URGENTE-link-gestao.patch` → não deve aparecer nada (silêncio = pode aplicar).
6. `git apply URGENTE-link-gestao.patch`
7. `python demos\gerar_demos.py` (refaz as demos do site a partir das telas).
8. Confira: abra `sistema\gestao-interna-physis.html` no navegador → clique em **Gestão** na faixa do topo → a página continua a mesma (antes dava "não encontrado").

> Se depois for aplicar o patch completo (Parte 2), desfaça antes esta correção, que já vem dentro dele: `git checkout -- sistema/gestao-interna-physis.html`.

---

## Parte 1 · Preparar o computador (uma vez só)

### 1.1 Python 3.10 ou mais novo
1. No navegador, abra **https://www.python.org/downloads/windows/** e clique em **Download Python 3.x.x** (o botão amarelo).
2. Abra o arquivo baixado (`python-3.x.x-amd64.exe`).
3. Na primeira tela, **marque** a caixa **Add python.exe to PATH** (embaixo). Clique em **Customize installation**.
4. Tela "Optional Features": deixe tudo marcado → **Next**.
5. Tela "Advanced Options": **marque** **Install Python 3.x for all users** (o instalador do Hub avisa se o Python for só de um usuário) → **Install**.
6. Janela "Deseja permitir que este aplicativo faça alterações?" → **Sim**.
7. No fim, se aparecer **Disable path length limit**, clique nele → **Sim** → **Close**.
8. Confira num PowerShell **novo**: `python --version` → deve mostrar `Python 3.10` ou mais.

### 1.2 Git
1. Abra **https://git-scm.com/download/win** → **Click here to download** (64-bit).
2. Abra o instalador → **Sim** no aviso do Windows.
3. Clique **Next** em todas as telas, mantendo o padrão. Únicas atenções:
   - "Choosing the default editor": pode trocar Vim por **Use Notepad as Git's default editor**.
   - "Adjusting your PATH": deixe **Git from the command line and also from 3rd-party software (Recommended)**.
4. **Install** → **Finish**. Confira: `git --version`.

### 1.3 Código
- Se ainda não tem: `mkdir C:\physis` · `cd C:\physis` · `git clone https://github.com/Physis2026/Sistema-Physis physis-sistema`
- Se já tem: `cd C:\physis\physis-sistema` · `git status` (limpo) · `git pull`

---

## Parte 2 · Aplicar a implementação final
1. Copie `implementacao-final.patch` para `C:\physis\physis-sistema`.
2. `cd C:\physis\physis-sistema`
3. `git apply --check implementacao-final.patch` → silêncio = ok. Se reclamar de `gestao-interna-physis.html`, faça a observação da Parte 0 e repita.
4. `git apply implementacao-final.patch`
5. `python demos\gerar_demos.py` (as demos ficaram fora do patch por tamanho; este comando as refaz).
6. Testes: `cd physis-hub` · `python -m unittest discover -s tests` → no fim deve aparecer **OK** (cerca de 1300 testes; leva alguns minutos). Se aparecer FAILED, me mande as últimas 30 linhas.

---

## Parte 3 · Configurar as variáveis (o que os bots precisam saber)
Caminho: tecla **Windows** → digite `variáveis` → clique em **Editar as variáveis de ambiente para sua conta** → na parte de cima ("Variáveis de usuário para …") clique em **Novo...** → preencha **Nome** e **Valor** → **OK**. Repita para cada linha. No fim, **OK** na janela principal e **feche e reabra** o PowerShell.

| Nome | Valor | Obrigatório? |
|---|---|---|
| `PHYSIS_DOCS` | a pasta *Documents* do OneDrive, se não for `C:\Users\<você>\OneDrive - Physis Engineering\Documents` | só se o caminho for outro |
| `PHYSIS_IOT_MUDO_H` | horas sem leitura para considerar um sensor mudo (decisão de vocês) | para o bot dados-iot alertar |
| `PHYSIS_GESTOES_MAX_H` | idade máxima, em horas, da exportação de uma Gestão | para o bot gestões alertar |
| `PHYSIS_EDITAIS_AVISO_DIAS` | com quantos dias de antecedência avisar o prazo de edital | para o bot editais alertar |
| `PHYSIS_CERT_AVISO_DIAS` | dias de antecedência para o certificado HTTPS | só no servidor com domínio |
| `PHYSIS_DOMINIO` | o domínio público do Hub (ex.: o que estiver no Caddy) | só no servidor com domínio |
| `PHYSIS_CURSOS_PASTAS` | só se as pastas das plataformas de curso forem outras (formato na Parte 6) | não |

Sem os limites, os bots **não inventam valor**: mostram a medida e abrem um aviso "configuração pendente".

> O banco do Hub instalado pelo `instalar.ps1` fica em `C:\ProgramData\Physis\dados` e **só Administradores e o serviço leem**. Por isso, no notebook do dia a dia, não defina `PHYSIS_BANCO`: os bots dados-iot e bancos rodam no servidor (Parte 7).

---

## Parte 4 · Ligar os bots para rodarem sozinhos (agenda do Windows)
1. PowerShell **normal** (não Administrador): `cd C:\physis\physis-sistema\physis-hub`
2. Teste à mão primeiro: `python -m physis_hub.mv_cli bots vigia` → aparece um texto com chaves `{ }`, sem "Traceback".
3. Veja o que vai ser criado: `python -m physis_hub.mv_cli agenda` (só mostra).
4. Crie: `python -m physis_hub.mv_cli agenda --criar`
   - Se aparecer "Acesso negado": feche, abra o PowerShell **como Administrador** (tecla Windows → digite `PowerShell` → **botão direito** → **Executar como administrador** → **Sim**) e repita os passos 1 e 4.
5. Confira no **Agendador de Tarefas** (tecla Windows → digite `Agendador` → **Agendador de Tarefas**):
   - No painel da esquerda, abra **Biblioteca do Agendador de Tarefas** → pasta **PhysisMV**.
   - Devem existir **bots_hora** (de hora em hora), **atrasos_8h** (de 8 em 8 h), **resumo_7h** (todo dia às 7h), **revisao_semanal** (segunda às 6h) e **painel** (ao entrar no Windows).
   - Clique com o **botão direito** em **bots_hora** → **Executar**. Espere 1 minuto → **F5** → a coluna **Resultado da Última Execução** deve dizer **A operação foi concluída com êxito. (0x0)**.
   - As tarefas já foram criadas para rodar **quando o computador ligar, se perderam o horário**, e **também na bateria** (o próprio `mv_cli` ajusta isso).

O que roda:
- **De hora em hora:** atrasos, documentos, dados-iot, vigia, sentinela, sala.
- **Às 7h:** todos os 18 bots: atrasos, documentos, resumo, backup, páginas, inovação, links, editais, dados-iot, simulação, gestões, bancos, acervo, **ia** (índice da IA Physis), **cursos** (mapa de cursos), vigia, sentinela e sala.

---

## Parte 5 · Abrir as telas (os "sites" do sistema)
| Tela | Como abrir | Endereço |
|---|---|---|
| **Physis M&A** (gestão, Monitoramento, bots) | sobe sozinho ao entrar no Windows (tarefa *painel*); à mão: `python -m physis_hub.mv_cli servir` | **http://127.0.0.1:8710/** |
| **Mapa de integrações** | M&A → aba **Monitoramento** | (mesmo endereço) |
| **Sala dos bots** | arquivo gerado a cada rodada | `…\Sistema Physis\28_Physis_MV\sala-dos-bots.html` (duplo clique) |
| **IA Physis** | M&A: `http://127.0.0.1:8710/api/mv/ia?q=sua pergunta` (resposta em JSON) ou no PowerShell: `python -m physis_hub.mv_cli ia "sua pergunta"` | — |
| **Physis Hub** (loja, plataforma do cliente) | no servidor (Parte 7) | **http://<IP do servidor>:8700/** |
| **Gestão Physis interna** | no servidor | **http://<IP do servidor>:8700/gestao/** |

Ver o M&A pelo celular ou outro PC da mesma rede (teste):
1. `python -m physis_hub.mv_cli servir --rede` → o PowerShell mostra o endereço (`http://192.168.x.x:8710/`) e onde está a senha (`C:\physis\dados\senha-teste-rede.txt`).
2. Se o Windows mostrar **"O Firewall do Windows Defender bloqueou alguns recursos deste aplicativo"**: **marque só Redes privadas**, **desmarque Redes públicas** → **Permitir acesso** → **Sim**.
3. No outro aparelho, abra o endereço → usuário `teste` → a senha do arquivo.
4. A rede precisa estar como **Privada**: **Configurações** → **Rede e Internet** → **Wi-Fi** (ou **Ethernet**) → clique na rede → **Tipo de perfil de rede** → **Privada**.

---

## Parte 6 · IA Physis e mapa de cursos
**IA Physis** (própria, sem terceiros):
- Primeiro índice: `python -m physis_hub.mv_cli ia --indexar` (lê a documentação, o código e as pastas Casa/Sistema/Instituto Physis do OneDrive; depois só relê o que mudou).
- Perguntar: `python -m physis_hub.mv_cli ia "qual a regra de limite da água?"` → resposta com [1], [2] e os arquivos de origem. Sem evidência, ela responde **"Não encontrei isso nos documentos da Physis."**
- O bot **ia** atualiza o índice todo dia às 7h.

**Mapa de cursos** (bot **cursos**, desde já; trilhas a partir de **30/11/2026**):
1. Compartilhe os documentos nas pastas do OneDrive:
   - **Instituto Physis** → `Documents\Instituto Physis\`
   - **InovaSTEM** (plataforma própria, várias frentes) → `Documents\Instituto Physis\InovaSTEM\` ou `Documents\InovaSTEM\`
   - **Physis Engineering** → `Documents\Sistema Physis\` (mais a documentação do sistema)
   - Outras pastas: variável `PHYSIS_CURSOS_PASTAS` = `{"InovaSTEM": ["D:\\cursos\\inovastem"], "Instituto Physis": ["…"], "Physis Engineering": ["…"]}`
2. O bot roda às 7h (ou já: `python -m physis_hub.mv_cli bots cursos`) e **rechecará sozinho** quando houver documento novo ou alterado.
3. Resultado: `Documents\Sistema Physis\28_Physis_MV\cursos\mapa-de-cursos.md` (para ler) e `mapa-de-cursos.json` (para a plataforma de cursos integrada).
4. Cada tema novo vira pedido em **M&A → Bots e comandos → Fila de pedidos e rascunhos**. Aprovar = a equipe avalia o curso; nome, público e conteúdo são decididos por vocês.
5. A partir de 30/11, para o bot **acervo** propor materiais, crie `Documents\Instituto Physis\InovaSTEM\trilhas.json`:
```json
{"T1": {"nome": "[nome da trilha 1]", "palavras": ["palavra1", "palavra2"]},
 "T2": {"nome": "[nome da trilha 2]", "palavras": ["palavra3"]}}
```

---

## Parte 7 · Servidor local do Physis Hub (o "servidor físico")
### 7A · Mini PC com Windows 10/11
1. Faça as Partes 1 e 2 no mini PC.
2. PowerShell **como Administrador** (botão direito → **Executar como administrador** → **Sim**).
3. `cd C:\physis\physis-sistema\implantacao`
4. `powershell -ExecutionPolicy Bypass -File .\instalar.ps1 -Firewall -Pacote C:\physis\physis-sistema\pacotes\physis-servidor`
   - **Use o `-Pacote`:** é o pacote do servidor da Physis (loja, plataforma, **Gestão em /gestao/**, consultoria, demos e montador), que vem pronto no ZIP. Sem ele, o Hub sobe **sem a Gestão**.
   - Para remontar o pacote (por exemplo, com outros módulos): `cd C:\physis\physis-sistema\physis-hub` e depois `python montar.py --org physis-engineering --nome "Physis Engineering Ltda." --modulos monitoramento,agua,sustainkit,supervisao,planejador,gestao --sustainkit ..\sistema\SustainKit_Definitivo.html --supervisao ..\sistema\physis-scada-demo.html --planejador ..\modulos\planejador\planejador-physis.html --gestao ..\sistema\gestao-interna-physis.html --saida ..\pacotes\physis-servidor`
   - Ele confere o Python, copia o código para `C:\Physis\versoes\<data>`, cria `C:\ProgramData\Physis` (dados, protegidos), registra a tarefa **PhysisHub** (sobe ao ligar e reinicia se cair) e a cópia diária **PhysisBackup** (2h30).
   - Aviso **"falta …\backup.env"**: copie `implantacao\backup.env.exemplo` para `C:\ProgramData\Physis\backup.env` e preencha (destino e senha da cópia cifrada; **não** coloque no Git).
   - `-Firewall` abre a porta 8700 **só para a rede local** e **só nos perfis Privado/Domínio**. Marque a rede como **Privada** (Parte 5, passo 4).
5. No fim, ele roda o `verificar.ps1` sozinho: tudo deve sair **[ OK ]**.
6. No navegador de qualquer PC da rede: **http://<IP do mini PC>:8700/** → **crie a primeira conta** (ela vira a direção). Para ver o IP: `ipconfig` → "Endereço IPv4".
7. Bots no servidor: faça a Parte 4 no mini PC e defina `PHYSIS_BANCO` = `C:\ProgramData\Physis\dados\physis-hub.db`. Como só Administradores leem essa pasta, crie a agenda **no PowerShell como Administrador**.

### 7B · Raspberry Pi ou mini PC com Linux (Debian 12 / Raspberry Pi OS)
1. Terminal: `sudo apt update && sudo apt install -y git python3` → digite a senha → **Y** se perguntar.
2. `git clone https://github.com/Physis2026/Sistema-Physis ~/physis-sistema && cd ~/physis-sistema` → `git apply ~/implementacao-final.patch`
3. `cd implantacao && sudo ./instalar.sh` → ele **pergunta** cada opcional:
   - **Mosquitto** (sensores da Caixinha): **s** se houver sensores ESPHome.
   - **Caddy**: **lan** (HTTPS na rede local, certificado próprio) ou **dominio** (Let's Encrypt; precisa do domínio, de um e-mail e das portas 80/443 chegando ao aparelho).
   - **ufw** (firewall): **s**.
4. `sudo /opt/physis/implantacao/verificar.sh` → tudo **[ OK ]**.
5. Abra **http://<IP>:8700/** (ou **https://** com Caddy). No modo **lan**, o navegador avisa "certificado não confiável" na primeira vez: é o certificado local do Caddy. Clique em **Avançado** → **Continuar** só se o endereço for o do seu aparelho. **[CONFERIR]** a instalação da CA local nos aparelhos (docs/IMPLANTACAO.md).
6. Bots no Linux: troque a agenda do Windows por um *timer* do systemd ou um `cron` com os mesmos comandos da Parte 4. **[CONFERIR]**: o `mv_cli agenda` hoje só gera a agenda do Windows.

---

## Parte 8 · Sites externos usados nas telas
Daqui não foi possível testar (este ambiente não tem internet geral), por isso o bot **links** marcou os 8 como "sem resposta". No seu computador:
1. Abra cada endereço; todos são **públicos e gratuitos para consulta**:
   - https://cresesb.cepel.br/index.php?section=sundata (irradiação solar)
   - https://re.jrc.ec.europa.eu/pvg_tools/pt/ (PVGIS)
   - https://portal.inmet.gov.br/normais (normais climatológicas)
   - https://www.snirh.gov.br/hidroweb/ (HidroWeb)
   - https://www.ibge.gov.br/geociencias/downloads-geociencias.html (bases do IBGE)
   - https://geosgb.sgb.gov.br/ (geologia, SGB)
   - https://plataforma.brasil.mapbiomas.org/ (uso do solo)
   - https://portal.opentopography.org/datasets (relevo)
2. **[CONFERIR]**: para **baixar** dados, OpenTopography e MapBiomas costumam pedir **cadastro gratuito** (botão de login/cadastro no topo). Consultar não precisa.
3. Depois rode `python -m physis_hub.mv_cli bots links`: num computador com internet, os alertas que não forem reais **fecham sozinhos**.

---

## Parte 9 · Conferência final (marque um a um)
- [ ] Parte 0: o link **Gestão** abre a própria Gestão.
- [ ] `python -m unittest discover -s tests` → **OK**.
- [ ] Agendador → **PhysisMV** → 3 tarefas, resultado **0x0**.
- [ ] **http://127.0.0.1:8710/** → aba **Monitoramento** mostra as engrenagens e os anéis (verde = trabalhando).
- [ ] `python -m physis_hub.mv_cli ia "limite da água"` responde com fonte.
- [ ] `…\28_Physis_MV\cursos\mapa-de-cursos.md` existe depois do bot **cursos**.
- [ ] Servidor: `verificar.ps1` / `verificar.sh` → tudo **[ OK ]**; **http://<IP>:8700/** abre.
- [ ] Variáveis de limite definidas: os avisos "configuração pendente" somem na rodada seguinte.
