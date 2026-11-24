# Conexões do M&A com Casa Physis, Marketing Physis e Instituto Physis (passo a passo)
Pré-requisito: o passo a passo de instalação feito (M&A em C:\physis\physis-ma-20261122-1bd599e e Instituto em C:\physis\instituto-physis).
Atalho usado abaixo: **"PowerShell do M&A"** = abrir o PowerShell e colar `cd C:\physis\physis-ma-20261122-1bd599e\physis-hub`.

| Conexão | O que liga | Como |
|---|---|---|
| Marketing | pasta OneDrive › Marketing Physis → M&A | automática (bot repositorios + IA + documentos) |
| Casa Physis | pasta OneDrive › Casa Physis → M&A; Gestão da Casa → M&A; plataforma da Casa | pasta automática; Gestão por exportação; plataforma no servidor |
| Instituto | repositório ao lado → sincronização; pasta OneDrive › Instituto Physis → M&A; Gestão do Instituto → M&A; Hub Physis ↔ Hub Instituto | automática; exportação; intercâmbio com chave |

---

## 1. Pastas do OneDrive (vale para os três)
1. Abra o Explorador de Arquivos e entre em **OneDrive - Physis Engineering › Documentos**.
2. Para cada pasta **Casa Physis**, **Instituto Physis**, **Sistema Physis** e **Marketing Physis**: botão direito → **Sempre manter neste dispositivo**.
   (Sem isso os arquivos ficam só na nuvem e os bots não leem.)
3. Confira no PowerShell do M&A:
   ```
   py -m physis_hub.mv_cli bots documentos repositorios
   ```
   Deve aparecer `"vistos":` com um número maior que 0 e **Marketing Physis** com o último commit.

---

## 2. Marketing Physis
Já está ligado: o M&A procura **Documentos › Marketing Physis** sozinho.
- Depois de mexer no marketing, salve no Git:
  ```
  cd "$env:OneDrive\Documents\Marketing Physis"
  git add -A
  git commit -m "o que mudou"
  ```
- Conferir: no M&A (http://127.0.0.1:8710/), aba **Monitoramento** → engrenagem **Marketing Physis (repositório)**.
  Aba **Alertas**: se aparecer "sem cópia fora deste computador", é porque falta o remote (ver abaixo).
- Cópia fora do computador (recomendado): crie um repositório vazio **Physis2026/marketing-physis** no GitHub e depois:
  ```
  git remote add origin https://github.com/Physis2026/marketing-physis
  git push -u origin main
  ```

---

## 3. Casa Physis
### 3a. Documentos
Automático: tudo em **Documentos › Casa Physis** é lido pelo bot documentos (validade, [MARCADOR], regras) e entra na IA Physis.

### 3b. Gestão da Casa → M&A (tarefas e projetos)
1. Abra a Gestão da Casa Physis e clique em **Fazer cópia** (botão no topo). O arquivo **.json** vai para Downloads.
2. Mova o arquivo para **Documentos › Sistema Physis › 28_Physis_MV › gestoes** e renomeie para **casa.json**
   (crie a pasta `gestoes` se não existir).
3. No PowerShell do M&A:
   ```
   py -m physis_hub.mv_cli importar "$env:OneDrive\Documents\Sistema Physis\28_Physis_MV\gestoes\casa.json" --frente casa
   ```
4. Conferir: M&A → aba **Tarefas**, filtro **Frente: Casa Physis**. Daqui em diante o bot **gestoes** avisa quando houver cópia nova sem importar.

### 3c. Plataforma da Casa Physis (no servidor, porta 8701)
No PowerShell do M&A:
```
py montar_clientes.py --saida C:\physis\plataformas --so casa-physis-inicial
cd C:\physis\plataformas\physis-casa-physis-inicial
$env:PHYSIS_PORTA="8701"; $env:PHYSIS_BANCO="C:\physis\dados\casa-physis.db"; py -m physis_hub.servidor
```
Abra **http://127.0.0.1:8701/** e crie o primeiro acesso. Para deixar ligada sempre, use o `instalar.ps1 -Pacote C:\physis\plataformas\physis-casa-physis-inicial -Porta 8701`
(PowerShell como administrador, na pasta `implantacao` do sistema).

---

## 4. Instituto Physis
### 4a. Repositório ao lado (módulos compartilhados)
Já ligado pelo passo 8 da instalação. Conferir no PowerShell do M&A:
```
py -m physis_hub.mv_cli bots sincronizacao
```
Esperado: **"Instituto Physis": "em dia"** ou **"atualizado, testado e com commit"**. Se disser **"pulado: há alterações em andamento"**:
```
cd C:\physis\instituto-physis
git status
git add -A
git commit -m "..."
```

### 4b. Documentos e editais
Automático: **Documentos › Instituto Physis** (documentos, editais, cursos). Trilhas da InovaSTEM: arquivo **trilhas.json** em
**Documentos › Instituto Physis › InovaSTEM** (a partir de 30/11).

### 4c. Gestão do Instituto → M&A
Igual ao 3b: **Fazer cópia** na Gestão do Instituto → salvar como **instituto.json** em `28_Physis_MV\gestoes` → importar:
```
py -m physis_hub.mv_cli importar "$env:OneDrive\Documents\Sistema Physis\28_Physis_MV\gestoes\instituto.json" --frente instituto
```
(InovaSTEM separada: `inovastem.json` com `--frente inovastem`.)

### 4d. Intercâmbio Hub Physis ↔ Hub Instituto (cursos, projetos, biblioteca 3D, lotes)
É a única troca de dados entre as duas plataformas: cada uma guarda o seu banco e só recebe o que a direção aprovar.
Dados de saúde nunca passam.
1. **Subir o Hub do Instituto** (porta 8702), num PowerShell:
   ```
   cd C:\physis\instituto-physis\physis-hub
   $env:PHYSIS_PORTA="8702"; $env:PHYSIS_BANCO="C:\physis\dados\instituto-hub.db"; py -m physis_hub.servidor
   ```
   Abra http://127.0.0.1:8702/ e crie o primeiro acesso (direção).
2. **Hub da Physis** (porta 8700) ligado, pelo servidor instalado ou com `py -m physis_hub.servidor` na pasta `physis-hub` do sistema.
3. **Nos dois Hubs**, entrando como direção: **Minha conta → Intercâmbio com outras plataformas**.
   - Anote o **identificador desta instalação**, mostrado no topo da tela, nos dois lados.
   - Clique em **cadastrar o outro lado**:
     - **identificador:** o que você anotou no outro Hub;
     - **nome:** "Instituto Physis" ou "Physis Engineering";
     - **endereço:** `http://127.0.0.1:8702` (no Hub da Physis) ou `http://127.0.0.1:8700` (no Hub do Instituto).
       Em computadores diferentes, use o IP da rede ou da VPN, por exemplo `http://192.168.0.10:8700`.
   - Marque **o que envia** e **o que aceita**: `cursos_catalogo`, `projetos_resumo`, `pecas_biblioteca`, `lotes_integridade`.
4. **Chave combinada:** num lado, **Gerar chave nova** (ela aparece **uma vez só**). Copie e, no outro lado, cole em **Chave recebida do parceiro** → Salvar.
   Passe a chave por um canal seguro, nunca por e-mail aberto.
5. **Testar** e depois **Puxar do parceiro**. O que chega aparece em **Chegou e espera aprovação** → a direção **Aprova**.
6. Pronto: os cursos do Instituto passam a aparecer na plataforma da Physis, e a biblioteca 3D, no Instituto.

---

## 5. Conferir tudo de uma vez
```
cd C:\physis
py diagnostico_ma.py "C:\physis\physis-ma-20261122-1bd599e"
```
- Seção 6 (Marketing) e seção 7 (Integração: Instituto e sincronização) sem erro.
- Seção 8: "Nada".
- M&A → aba **Monitoramento**: engrenagens do Instituto, da Casa Physis e do Marketing ligadas.
