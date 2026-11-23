# 🌳 Guia fácil: ligar o Physis M&A (até uma criança consegue)

Você vai precisar de: um computador com Windows, internet e **um adulto por perto** nos passos com 🧑.
Cada passo tem: **o que fazer**, **o que você vai ver** e **se der errado**.

---

## 👀 Quer só VER o M&A agora? (1 minuto)
1. Abra a pasta que recebeu e procure o arquivo **M&A-demonstracao.html**.
2. Dê **dois cliques** nele. Ele abre no navegador.
3. Clique nas abas lá em cima. A aba **Monitoramento** mostra as engrenagens girando.
- Os dados dessa versão são **de exemplo**. Para ver os dados de verdade, faça a instalação abaixo.

---

## 🧩 Parte 1: instalar dois programas (só na primeira vez)

### Passo 1: Python 🧑
1. No navegador, entre em **python.org/downloads/windows**.
2. Clique no botão amarelo **Download Python**.
3. Abra o arquivo que baixou.
4. Embaixo da janela, **marque o quadradinho** "Add python.exe to PATH". ✅
5. Clique em **Customize installation** → **Next**.
6. **Marque** "Install Python for all users" → **Install**.
7. Vai aparecer: *"Deseja permitir que este aplicativo faça alterações?"* → clique **Sim**. 🧑
8. No fim, se aparecer **Disable path length limit**, clique nele → **Sim** → **Close**.
- **Você vai ver:** "Setup was successful".
- **Se der errado:** feche e comece de novo pelo item 3.

### Passo 2: Git 🧑
1. Entre em **git-scm.com/download/win** → clique em **Click here to download**.
2. Abra o arquivo → **Sim**.
3. Aperte **Next** em todas as telas, sem mudar nada. No fim, **Install** → **Finish**.
- **Você vai ver:** a janela fecha sozinha.

---

## 📦 Parte 2: pegar o sistema (só na primeira vez)

**Recebeu o ZIP `Sistema-Physis-uso`?** Então é mais fácil:
1. Clique com o botão direito no ZIP → **Extrair tudo...**
2. Escreva `C:\physis` como destino → **Extrair**.
3. Pule direto para a **Parte 3**. Não precisa do Git nem do patch.

**Sem o ZIP**, faça assim:
1. Aperte a tecla **Windows** do teclado, escreva **PowerShell** e aperte **Enter**.
2. Uma janela azul abre. Escreva cada linha abaixo e aperte **Enter** depois de cada uma:
   - `mkdir C:\physis`
   - `cd C:\physis`
   - `git clone https://github.com/Physis2026/Sistema-Physis physis-sistema`
- **Você vai ver:** letras passando e, no fim, "done".
- **Se já existir:** se aparecer "already exists", tudo bem: a pasta já está lá.
3. Copie estes **3 arquivos** que você recebeu para a pasta **C:\physis\physis-sistema**:
   - **implementacao-final.patch**
   - **INSTALAR-PHYSIS.bat**
   - **instalar_tudo.py**
- **Se o Windows perguntar:** se aparecer "Substituir o arquivo?", clique em **Substituir**.

---

## 🚀 Parte 3: o botão mágico
1. Abra a pasta **C:\physis\physis-sistema**.
2. Dê **dois cliques** em **INSTALAR-PHYSIS.bat**. Se o Windows não deixar, use **INSTALAR-PHYSIS.py** (veja "Se a Microsoft não deixar instalar", logo abaixo).
3. Uma janela preta abre e mostra 10 passos, um por um:
   - `[1/10] Python ... OK`
   - `[3/10] Atualização (patch) ... aplicada agora`
   - `[5/10] Testes ...` ⏳ (espere: pode demorar alguns minutos)
   - … até `[10/10] Tela do M&A ... aberta`
4. O navegador abre sozinho no **Physis M&A**. 🎉
5. Na janela preta aparece **PRONTO!** Aperte qualquer tecla para fechar.

**Se aparecer "PAROU AQUI":**
- Leia a frase: ela diz o que fazer.
- Se falar de **administrador**: clique com o **botão direito** no INSTALAR-PHYSIS.bat → **Executar como administrador** → **Sim**. 🧑
- Se não entender: chame um adulto e mostre o arquivo **instalar-physis.log**, que fica na mesma pasta.

Pode rodar o botão mágico de novo quantas vezes quiser: o que já está feito é pulado.


---

## 🛡️ Se a Microsoft (Windows) não deixar instalar
Veja qual mensagem aparece e faça o que está na linha dela. 🧑

| O que aparece | O que fazer |
|---|---|
| **"O Windows protegeu o computador"** (tela azul do SmartScreen) | Clique em **Mais informações** → **Executar assim mesmo**. |
| O **.bat** não abre, some ou o antivírus avisa **"Ameaça encontrada"** | Use o outro instalador: dê **dois cliques** em **INSTALAR-PHYSIS.py** (mesma pasta). Ele faz a mesma coisa e é aberto pelo Python, que é assinado. |
| **"Este aplicativo foi bloqueado para sua proteção"** ou **"Controle Inteligente de Aplicativos bloqueou…"** (Windows 11) | Não use o .bat. Abra o **PowerShell**, digite `cd C:\physis\physis-sistema` e depois `py ferramentas\instalar_tudo.py`. |
| Arquivos do ZIP bloqueados ("Este arquivo veio de outro computador…") | **Antes de extrair:** botão direito no **ZIP** → **Propriedades** → embaixo, marque **Desbloquear** → **OK**. Depois extraia de novo. |
| Ao digitar `python`, abre a **Microsoft Store** | **Configurações** → **Aplicativos** → **Configurações avançadas de aplicativos** → **Aliases de execução de aplicativo** → desligue **python.exe** e **python3.exe**. Ou use `py` no lugar de `python`. |
| O instalador do **Python** não é permitido | **Opção A:** instale **"Python 3.12"** pela própria **Microsoft Store** (é da Python Software Foundation). **Opção B:** no PowerShell, `winget install Python.Python.3.12`. |
| **"Seu administrador bloqueou…"**, **"Esta configuração é gerenciada pela organização"** | O computador é controlado pela empresa ou escola. Só o responsável de TI libera. Peça para liberar o **Python 3.12** e a pasta **C:\physis**. |
| **"Acesso negado"** na agenda | Botão direito em **INSTALAR-PHYSIS.py** (ou .bat) → **Executar como administrador** → **Sim**. |

Se nenhuma linha servir: tire uma **foto da mensagem** e mande para a equipe.

---

## 🖥️ Parte 4: usar o M&A todo dia
- O M&A abre sozinho quando você entra no Windows. O endereço é **http://127.0.0.1:8710/**. Dica: salve nos favoritos ⭐.
- Os bots trabalham sozinhos: **de hora em hora** e **às 7h da manhã**. Você não precisa fazer nada.

| Quero… | Clico em… |
|---|---|
| ver as engrenagens e se os bots estão bem | aba **Monitoramento** (anel verde = trabalhando, amarelo = atenção, vermelho = problema, cinza = parado) |
| responder o que o sistema perguntou | aba **Aprovações** → **Perguntas** → clique numa opção ou escreva e aperte **Responder** |
| aprovar o que os bots prepararam | aba **Bots e comandos** → **Fila de pedidos e rascunhos** |
| rodar os bots agora | botão laranja **Rodar bots agora** (no topo) |

---

## ❓ Parte 5: a caixa de perguntas (para o adulto que decide) 🧑
O sistema criou **perguntas específicas** para cada coisa que só uma pessoa pode decidir. Elas ficam em **Aprovações → Perguntas**. Por exemplo:
- Quantas horas sem sinal para dizer que um sensor parou?
- Com quantos dias de antecedência avisar o prazo de um edital?
- O que fazer com cada tarefa que passa do prazo da Fase 0 (31/01/2027)? Antecipar, tirar da fase ou registrar exceção.
- Quais são as trilhas T1 e T2 do InovaSTEM?
- A IA fica só dentro da Physis ou o Claude continua como opção?

Respondeu um **número** (como "6")? Os bots passam a usar esse número **na próxima rodada**. Você não precisa mexer em mais nada.

---

## 🧭 Parte 6: o plano final
Todo dia às 7h, o bot **auditoria**:
- confere se cada bot está ligado em tudo (agenda, vigia, sala, mapa, documentação e testes);
- procura o que falta;
- escreve o **plano de intervenção**: quem faz, o quê, como e quando fica pronto.

O plano fica em: **Documentos › Sistema Physis › 28_Physis_MV › intervencao › plano-de-intervencao.md**.

---

## 📅 Parte 7: toda semana e o kit de 26/11
- **Toda segunda às 6h**, o bot **semanal** faz a revisão completa: todos os bots, o mapa de parcerias e o kit. O relatório fica em **28_Physis_MV › semanal**.
- O bot **kit** mostra, por pilar, quais documentos faltam para 26/11 e cria uma **versão zero** de cada um em **28_Physis_MV › kit-26-11 › versao-zero**. Abra, complete os [MARCADOR] e aprove na aba **Bots e comandos**. 🧑
- O bot **mercado** só roda quando você pede: na caixa **Comando aos bots** do M&A, escreva `/mercado Petrópolis avac` (cidade e área). O mapa fica em **28_Physis_MV › ecossistema**. Fabricantes, investidores e collabs: planilha **parcerias.csv** nessa pasta.
- **Prazos** (fiscal, contratos, ACTs, certidões): preencha **28_Physis_MV › vencimentos › vencimentos.csv**. O bot **vencimentos** cria o arquivo **calendario-de-vencimentos.ics**: dê dois cliques para pôr na sua agenda.
- **Base de fatos:** os textos oficiais (visão, missão, razão social…) ficam em **28_Physis_MV › fatos › fatos.json**. O que faltar aparece como pergunta na aba **Aprovações**. 🧑

---

## 📣 Parte 8: o repositório do marketing
- A pasta do marketing fica no OneDrive: **Documentos › Marketing Physis** (C:\Users\<você>\OneDrive - Physis Engineering\Documents\Marketing Physis). O M&A acha sozinho.
- 🧑 Cuidado com o OneDrive e o Git: clique com o botão direito na pasta **Marketing Physis** → **Sempre manter neste dispositivo**. E só uma pessoa faz commit de cada vez (duas pessoas mexendo na mesma pasta ao mesmo tempo pode estragar o Git).
- Todo dia o bot **repositorios** confere: último commit, arquivos alterados sem commit e se existe cópia fora do computador. Os documentos do marketing passam a contar no bot **documentos** e na **IA Physis**.
- Depois de mexer no marketing, salve no Git: `cd "$env:OneDrive\Documents\Marketing Physis"`, depois `git add -A` e `git commit -m "o que mudou"`.

---

## ✅ Lista final (marque um por um)
- [ ] Botão mágico terminou com **PRONTO!**
- [ ] O M&A abre em **http://127.0.0.1:8710/**.
- [ ] A aba **Monitoramento** mostra as engrenagens.
- [ ] Na aba **Aprovações → Perguntas**, as perguntas foram respondidas. 🧑
- [ ] No dia seguinte, o **plano de intervenção** tem menos itens.
