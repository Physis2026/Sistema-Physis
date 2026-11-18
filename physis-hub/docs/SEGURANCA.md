# Segurança do servidor na internet

Código: `physis_hub/seguranca.py` (regras), `physis_hub/servidor.py` (onde cada rota usa as regras),
`physis_hub/hub.py` (sessão e papéis). Testes: `tests/test_seguranca.py`.

## Em uma frase

O Physis Hub não fala HTTPS sozinho: na internet ele fica **atrás de um proxy reverso** (Caddy ou nginx)
que cuida do certificado; o servidor confia nesse proxy (e só nele) para saber o IP de quem chama e se
o pedido veio por HTTPS.

## Variáveis de ambiente

| Variável | Padrão | O que faz |
|---|---|---|
| `PHYSIS_ENDERECO` | `0.0.0.0` | Onde o servidor escuta. Atrás de proxy na mesma máquina, use `127.0.0.1`. |
| `PHYSIS_PROXY_CONFIAVEL` | vazio | IPs/redes (CIDR, vírgulas) do proxy. Só deles valem `X-Forwarded-For` e `X-Forwarded-Proto`. Ex.: `127.0.0.1,::1`. |
| `PHYSIS_HTTPS` | vazio | `1` = o servidor só é alcançado por HTTPS (cookie `Secure` e HSTS sempre). |
| `PHYSIS_EXPOSTO` | vazio | `1` = ninguém conta como "rede local" (telemetria e aparelhos sem chave ficam fechados). Recomendado no servidor da internet. |
| `PHYSIS_REDE_LOCAL` | vazio | Redes extras tratadas como locais (ex.: VPN `100.64.0.0/10`). |
| `PHYSIS_ACEITAR_SEM_CHAVE` | vazio | Aparelhos sem chave: `1` aceita de qualquer lugar (fase 2, só em rede fechada), `0` nunca aceita, vazio = só da rede local. |
| `PHYSIS_TOKEN` | vazio | Chave única antiga (`X-Physis-Token`), agora comparada em tempo constante. Prefira as chaves por dispositivo. |
| `PHYSIS_PRIMEIRA_CONTA_EXTERNA` | vazio | `1` permite criar a **primeira** conta (que vira direção) de fora da rede local. Ligue só no momento de criar e desligue. |
| `PHYSIS_URL_PUBLICA` | vazio | Endereço público (ex.: `https://hub.physis…`). Defina sempre na internet: o link do e-mail de ativação não usa mais o cabeçalho `Host`. |
| `PHYSIS_LIMITE_PUBLICO` | `20/600` | Formulários públicos por IP: compra, pedido (loja e consultoria), suporte sem sessão. `fichas/segundos`; `0` desliga. |
| `PHYSIS_LIMITE_ARQUIVO` | `10/600` | Anexos de pedido (até 20 MB) por IP. |
| `PHYSIS_LIMITE_ENTRAR` | `10/300` | Login, criar conta, código de ativação e apagar conta, por IP (além do bloqueio por usuário: 5 erros = 30 s). |
| `PHYSIS_LIMITE_DISPOSITIVO` | `1200/60` | Entregas dos aparelhos por IP. |
| `PHYSIS_RETENCAO_DIAS_SESSAO` | `0` | >0: derruba sessões abertas há mais de N dias (as vencidas sempre saem). |
| `PHYSIS_RETENCAO_DIAS_ACESSO` | `183` | Registro de acessos (login, saída, erros): 6 meses (Marco Civil, art. 15) e apaga. |
| `PHYSIS_RETENCAO_DIAS_EMAIL_PENDENTE` | `30` | E-mails que nunca saíram (pendente/falhou) são apagados. |
| `PHYSIS_RETENCAO_DIAS_EMAIL_ENVIADO` | `365` | Texto dos e-mails enviados é apagado (fica assunto, estado e data). |
| `PHYSIS_RETENCAO_DIAS_PEDIDO` | `0` | >0: pedidos de proposta são anonimizados e os anexos apagados depois de N dias. |
| `PHYSIS_RETENCAO_DIAS_SUPORTE` | `0` | >0: chamados de suporte são anonimizados depois de N dias. |
| `PHYSIS_SESSAO_OCIOSA_MIN` | `720` | Sessão sem uso por N minutos cai (12 h). `0` desliga. |
| `PHYSIS_SESSAO_DIAS` | `30` | Vida máxima da sessão, mesmo em uso. |
| `PHYSIS_REAUT_MIN` | `10` | Depois do login ou de `/api/conta/reautenticar`, por quantos minutos as ações sensíveis valem sem pedir a senha de novo. |
| `PHYSIS_CSRF_ESTRITO` | vazio | `1` = com sessão, todo POST/PUT/DELETE precisa de `X-Physis-CSRF`. **Ligue depois que as telas mandarem o cabeçalho.** |
| `PHYSIS_ORIGENS` | vazio | Outras origens aceitas no `Origin` (ex.: `https://www.physis…`), além do `Host` e de `PHYSIS_URL_PUBLICA`. |
| `PHYSIS_CONFIRMAR_EMAIL` | vazio | `1` exige confirmar o e-mail, `0` nunca; vazio = exige quando há servidor de e-mail (`PHYSIS_SMTP_HOST`). Sem confirmar, a conta vale como **cliente**. |
| `PHYSIS_TERMOS_VERSAO` | vazio | Força a versão dos termos; sem ela, vale o `"versao"` de `sistema/physis-juridico.js` (lido ao subir). |
| `PHYSIS_CONSENTIMENTO_ESTRITO` | vazio | `1` = sem o aceite da versão atual dos termos, só as rotas da própria conta funcionam (403 `{"consentimento": true}`). **Ligue depois que as telas tiverem o aviso de aceite.** |
| `PHYSIS_SEGURANCA_CONTATO` | vazio | Contato do `/.well-known/security.txt` (e-mail ou https; padrão: e-mail de suporte). |
| `PHYSIS_SAUDE_V6` | `1` | Linhas `MED`/`PUL` (Saúde) pelo receptor, `/api/v6/linha` e MQTT vão para a Saúde (nunca para `medicao`). `0` = recusadas (`tipo_desconhecido`); `/api/saude/linha` segue aceitando. |
| `PHYSIS_INSTANCIA` | `instancia.json` ao lado de `physis_hub/` | Outro arquivo de configuração (por exemplo, uma segunda instalação do mesmo código; use também `PHYSIS_BANCO` próprio). |
| `PHYSIS_INTERCAMBIO_CHAVES` | `intercambio-chaves.json` ao lado do banco | Chaves combinadas com as plataformas parceiras (`docs/INTERCAMBIO.md`). Só neste arquivo (permissão 600), nunca no código nem no banco. |
| `PHYSIS_INTERCAMBIO_ID` | o `org` da instalação | Identificador desta plataforma no intercâmbio. |
| `PHYSIS_INTERCAMBIO_LIMITE` | `120/600` | Pedidos de cada parceiro por janela (segundos); `0` desliga. |

Rotas novas de 15/11/2026 (mesmas regras): `GET /api/cliente/estado`, `GET|PUT /api/cliente/estado/<chave>` e
`GET /api/cliente/perfil` exigem sessão (cliente ou acima) **sempre**, mesmo em instalação sem login; o PUT passa pelo
CSRF; só as chaves da lista (`perfil_cliente.py`), até 2 MB por chave e 32 MB por organização. `GET /api/central/clientes`
e `GET|POST /api/suporte/chamados/<numero>` (contatos e notas internas = dado pessoal) exigem a **equipe**; o cliente
só vê a situação e as respostas dos próprios chamados em `GET /api/suporte`.

Os limites e `PHYSIS_PROXY_CONFIAVEL`/`PHYSIS_ACEITAR_SEM_CHAVE` são lidos quando o servidor sobe; os demais, a cada pedido.

## O que mudou (por item da auditoria)

1. **Cookie e HTTPS.** O cookie `physis_sessao` ganha `Secure` quando o pedido veio por HTTPS
   (`PHYSIS_HTTPS=1` ou `X-Forwarded-Proto: https` de um proxy confiável); aí também sai
   `Strict-Transport-Security: max-age=31536000; includeSubDomains`. Cabeçalhos em toda resposta: CSP (igual),
   `Permissions-Policy` (câmera/microfone só na própria página e no servidor de chamadas; localização só na
   própria página; pagamento, USB, serial etc. desligados), `Cross-Origin-Opener-Policy: same-origin`,
   `Cross-Origin-Resource-Policy: same-origin`, `X-Frame-Options: SAMEORIGIN`. O cabeçalho `Server` não
   mostra mais a versão do Python. Erro inesperado devolve `500 {"erro": "erro interno"}`; o rastro vai só
   para o console do servidor.
2. **Dados pessoais sempre com sessão da equipe**, com ou sem login na instalação: `/api/central/caixa`,
   `/api/central/arquivos`, `/api/central/arquivo/<id>`, `/api/central/emails`, `/api/central/instalacoes`,
   `/api/central/alocacao`, `/api/gestao/*`, `/api/loja/catalogo/interno`. `GET /api/suporte` sem sessão devolve
   só os contatos da Physis (`chamados: []`, `login: true`). **Instalação sem login** (`login:false`): a
   telemetria (`/api/painel`, `/api/leituras`, `/api/serie`, `/api/saude`, clima, comando) continua aberta
   **só para a rede local**; de fora (ou com `PHYSIS_EXPOSTO=1`) pede sessão. O servidor não passou a escutar
   só em `127.0.0.1` por padrão, porque o receptor da rede local precisa alcançá-lo; use `PHYSIS_ENDERECO`.
3. **Aparelhos.** Chave por dispositivo: a direção cria em `POST /api/dispositivos/chaves`
   `{"rotulo": "receptor galpão", "no": 7}` (sem `no` = chave de receptor, vale para qualquer nó; com `no`, só
   linhas `ID:7` passam e as outras voltam contadas em `recusadas_outro_no`). A resposta traz `chave`
   (`phk_…`) **uma única vez**; o banco guarda só o SHA-256. Listar: `GET /api/dispositivos/chaves`. Revogar:
   `POST /api/dispositivos/chaves/<id>/revogar` (vale na hora). O aparelho manda `Authorization: Bearer <chave>`
   ou `X-Physis-Chave: <chave>` em `/api/gateway/webhook`, `/api/hardware/gateway`, `/api/v6/linha` e
   `/api/saude/linha`. Chave errada ou revogada = 401 sempre. Sem chave: veja `PHYSIS_ACEITAR_SEM_CHAVE`
   (padrão: só da rede local, como o receptor V6 atual, que ainda não manda chave).
4. **Papéis.** No banco continuam `administrador` (= **direção**) e `operador` (= **equipe**); novo: `cliente`.
   A API aceita `direção`/`direcao` e `equipe` como apelidos. Só a direção: aprovar compra, publicar item da
   loja, gravar textos do site, contas, fontes de editais/eventos, chaves de dispositivo. Equipe: caixa,
   gestão, loja (gravar e revisar), e-mails, alocação. Cliente: a própria conta, senha, Meus dados, Saúde
   (com as regras de autorização da Saúde), suporte (vê só os chamados que abriu) e a telemetria da instalação.
5. **Limites por IP** (balde de fichas, em memória): ver `PHYSIS_LIMITE_*`. Passou do limite: `429` com
   `Retry-After` e `{"espera": s}`. O corpo é lido e descartado antes de fechar (até 24 MB, 5 s), para o
   Windows não cortar a conexão com RST. A primeira conta (que vira direção) só pode ser criada da rede local,
   salvo `PHYSIS_PRIMEIRA_CONTA_EXTERNA=1`.
6. **Sessão.** A tabela `sessao` guarda só o SHA-256 do token (`resumo`), mais `criado`, `ip` e `agente`
   (navegador). Busca pelo resumo e confere com `hmac.compare_digest`.
7. **LGPD.** `GET /api/conta/meus-dados`: conta (sem a senha), sessões, registro de acessos, pedidos/compras/
   chamados com o e-mail da pessoa, instalações, e-mails enviados a ela (só assunto/estado), entradas do
   registro encadeado que a citam, partes da Gestão que gravou. `POST /api/conta/apagar {"senha": "…"}`:
   apaga a conta e as sessões; compras ficam **anonimizadas** (valor, fatura, itens e datas ficam: registro
   fiscal, 5 anos); pedidos e chamados anonimizados, anexos apagados; e-mails pendentes apagados, enviados
   sem endereço e texto; Gestão passa a "[conta apagada]"; o registro de acessos fica até completar 6 meses
   (Marco Civil); o registro encadeado não muda (quebraria a cadeia) e ganha a entrada `lgpd` com só um
   resumo do usuário. A última conta da direção não pode se apagar (409). A retenção roda uma vez por dia.
   Saúde tem exportação e "apagar" próprios (`/api/saude/apagar`).

## Segunda parte: contas e "segurança máxima"

### Fluxos de conta (todos usam a fila `email_saida` + `correio.enviar_fila`)

O código de uso único vai no e-mail; o banco guarda só o SHA-256 (`conta_token`). Com `PHYSIS_URL_PUBLICA`, o e-mail
traz o link `https://…/conta/<fluxo>#t=<código>` (o código fica depois de `#`: não chega ao servidor nem aos registros
do proxy, e a página o tira da barra). Sem `PHYSIS_URL_PUBLICA`, o e-mail traz o caminho e o código para colar:
o servidor **nunca** monta link com o cabeçalho `Host` (que pode ser forjado). Os e-mails `conta-*` não aparecem na
fila da Gestão (`/api/central/emails` mostra só `conta_ocultos`) e o texto é apagado depois de enviado.

| Fluxo | Rotas | Regras |
|---|---|---|
| Esqueci a senha | `POST /api/conta/esqueci {usuario}` → `POST /api/conta/nova-senha {token, senha}` | Mesma resposta exista ou não a conta; 30 min; uso único; um pedido novo derruba os anteriores; no máximo 1 e-mail por minuto por conta; limite por IP; ao gravar, **todas as sessões caem**; a 2FA continua valendo. |
| Confirmar o e-mail | `POST /api/conta/confirmar {token}`; `POST /api/conta/confirmar/reenviar` (sessão) | Enviado ao criar conta pela direção (`/api/contas`). 3 dias. Sem confirmar (quando exigido), a conta vale como cliente (403 com `confirmar_email: true`). Contas antigas e a primeira conta já nascem confirmadas. |
| Convite | `POST /api/convites {email, papel, pessoa?, nome?}` (direção), `GET /api/convites`, `POST /api/convites/<id>/revogar`; a pessoa: `POST /api/conta/convite/ver {token}` e `POST /api/conta/convite/aceitar {token, nome, senha, consentimento}` | 7 dias; revogável; convite para a direção pede reautenticação; quem aceita escolhe nome e senha, entra já confirmado e já com sessão. |
| Consentimento | `POST /api/conta/consentimento {versao, aceito:true}`; retirar: `{aceito:false}` | Guarda versão, data e **resumo HMAC do IP** (tabela `consentimento`, mais o evento na cadeia). Versão nova dos termos = `consentimento_pendente: true` em `/api/instancia`. O convite exige o aceite. |

Páginas prontas servidas pelo próprio servidor: `/conta/esqueci`, `/conta/nova-senha`, `/conta/confirmar`,
`/conta/convite`. A página de entrada da Gestão (`/gestao` sem sessão) já tem "Esqueci a senha", o campo do código
2FA e o aceite dos termos na primeira conta.

### Outras proteções

- **Senha** (`seguranca.senha_fraca`): mínimo 12, máximo 256, sem regras de composição; recusa senhas comuns
  (lista embutida, inclusive com números no fim), sequências, poucos caracteres diferentes e senha quase igual ao usuário.
  Vale para criar conta, trocar, redefinir, convite e direção trocando a senha de alguém. Resumo PBKDF2-SHA256, 240 mil voltas, sal por conta.
- **2FA (TOTP, RFC 6238)**, opcional (recomendado para a direção): `POST /api/conta/2fa/iniciar` (reautenticação) →
  `{segredo, uri}`; `POST /api/conta/2fa/ativar {codigo}` → 10 códigos de recuperação (aparecem uma vez; guardados
  como resumo); `POST /api/conta/2fa/desativar {codigo}` (reautenticação). Login com 2FA: o primeiro POST devolve
  401 `{precisa_2fa: true}`; o segundo manda `codigo`. Código não pode ser reusado; o de recuperação é gasto.
- **Sessão**: ociosidade (12 h) e vida máxima (30 dias); `visto` gravado no máximo 1×/min.
- **Reautenticação** (`POST /api/conta/reautenticar {senha, codigo?}`): aprovar compra, dar/mudar papel, desativar
  ou trocar a senha de outra conta, convite para a direção, criar chave de dispositivo, ligar/desligar 2FA. Sem ela:
  403 `{reautenticar: true}`. Apagar a própria conta já pede a senha (e o código, se houver 2FA).
- **CSRF**: cookie `SameSite=Strict`; em POST/PUT/DELETE, `Origin` (ou `Referer`) de outro site (ou `null`) com
  sessão, ou em qualquer `/api/conta/*`, = 403 `{csrf: true}`; `X-Physis-CSRF` errado = 403; ausente = 403 só com
  `PHYSIS_CSRF_ESTRITO=1`. O token sai em `/api/instancia` (`csrf`) e na resposta do login. É um HMAC do token
  da sessão com o segredo do servidor (tabela `segredo`, 32 bytes de `secrets`).
- **Entrada**: todo JSON passa por `seguranca.carregar_json` (sem NaN/Infinity, números até 30 dígitos,
  profundidade ≤ 20, ≤ 20 mil itens); as rotas de conta, suporte, chaves e convites têm esquema (tipo e tamanho por
  campo; nas rotas novas, campo desconhecido = 400).
- **Arquivos**: anexos públicos conferem o conteúdo com a extensão (PDF `%PDF-`, Office novo `PK`, Office antigo
  OLE, CSV sem byte nulo) e recusam executáveis (PE, ELF, Mach-O, `#!`, WebAssembly); arquivos da Gestão recusam
  executáveis e nunca voltam como HTML/SVG/JS/XML (`application/octet-stream`, `attachment`, `nosniff`).
- **Eventos de segurança na cadeia** (`tipo='seguranca'`): entrou, senha errada, bloqueado, saiu, senha trocada,
  senha esquecida pedida, senha redefinida, e-mail confirmado, convite criado/revogado/aceito, consentimento
  aceito/retirado, 2FA ligada/desligada, código de recuperação usado, reautenticação falhou. Sem e-mail: `ref` é um
  HMAC do usuário e `ip` um HMAC do IP. CSRF recusado e acessos ficam em `acesso_log` (6 meses).
- **security.txt**: `/.well-known/security.txt` (RFC 9116).

## Checklist OWASP ASVS 4.0.3, nível 2 (o que se aplica a este servidor)

| ASVS | Requisito | Onde / situação |
|---|---|---|
| V1.4 | Controle de acesso no servidor, num ponto só | `_exigir`/`seg.pode` (papéis) e `_sensivel` — feito |
| V2.1.1–2.1.2 | Senha ≥ 12, até ≥ 64 | 12 a 256 — feito |
| V2.1.7 | Senha conferida contra lista de senhas vazadas/comuns | lista embutida (pequena; sem consulta externa por escolha) — parcial |
| V2.1.9 | Sem regras de composição | feito |
| V2.2.1 | Anti-automação (limite) | por usuário (5 erros = 30 s) e por IP (`PHYSIS_LIMITE_ENTRAR`) — feito |
| V2.4.1 | Senha com hash resistente e sal | PBKDF2-SHA256 240k, sal 16 bytes — feito |
| V2.5.1–2.5.4 | Recuperação: segredo aleatório, curto, uso único, sem dica | 32 bytes, 30 min, uso único, resposta igual — feito |
| V2.5.6 | Recuperação não desliga o 2º fator | 2FA continua — feito |
| V2.5.7 | Avisar a pessoa | e-mail de recuperação; aviso de "senha trocada" — pendente (evento só na cadeia) |
| V2.7/2.8 | OTP: uso único, janela curta, sem reuso | TOTP ±1 passo, `totp_ultimo` — feito |
| V2.8.4 | Segredo TOTP protegido | guardado no banco em texto (base32); proteja o arquivo do banco — parcial |
| V3.2.1–3.2.3 | Token novo no login, 128+ bits, cookie seguro | `token_urlsafe(32)` novo a cada login — feito |
| V3.2.4 | Token guardado com hash | SHA-256 — feito |
| V3.3.1 | Sair invalida no servidor | `DELETE` da sessão — feito |
| V3.3.2 | Reautenticação periódica | ociosidade 12 h, vida 30 dias — feito |
| V3.3.3 | Opção de encerrar as outras sessões após trocar senha | redefinição derruba todas; troca voluntária: pendente |
| V3.4.1–3.4.3 | Cookie `Secure`, `HttpOnly`, `SameSite` | feito (`Secure` por HTTPS) |
| V3.7.1 | Reautenticar para ações sensíveis | `_sensivel` — feito |
| V4.1.1–4.1.3 | Controle de acesso no servidor, menor privilégio, negar por padrão | papéis; dados pessoais só equipe — feito |
| V4.2.2 | Anti-CSRF | SameSite + Origin + token — feito (token obrigatório só com `PHYSIS_CSRF_ESTRITO=1`) |
| V4.3.1 | 2FA para administração | opcional — recomendado ligar para a direção |
| V5.1.3–5.1.4 | Validação de entrada por tipo/tamanho | `carregar_json` + `validar` — feito nas rotas de conta; demais rotas validam no hub |
| V5.3 | Codificação de saída / XSS | JSON com `Content-Type` correto, `nosniff`, CSP — feito |
| V7.1.1–7.1.2 | Não registrar segredos nem dados sensíveis | eventos com pseudônimo; senhas e tokens nunca — feito |
| V7.2.1–7.2.2 | Registrar eventos de autenticação e de acesso negado | cadeia + `acesso_log` — feito |
| V7.3.1–7.3.3 | Registro protegido contra alteração | cadeia de resumos (`verificar_cadeia`) — feito |
| V7.4.1 | Erro genérico, sem rastro | 500 `erro interno` — feito |
| V8.2.1 | Dados sensíveis sem cache | `Cache-Control: no-store` no JSON — feito |
| V8.3.1–8.3.2 | Exportar e apagar os próprios dados | `meus-dados`, `apagar` — feito |
| V8.3.8 | Retenção | `PHYSIS_RETENCAO_DIAS_*` — feito |
| V9.1.1–9.1.3 | TLS forte | no proxy (Caddy/nginx, TLS 1.2+) — **servidor do Eric** |
| V12.1.1 | Limite de tamanho de upload | 64 KB JSON, 20 MB anexos, 50 MB DWG — feito |
| V12.2.1 | Conferir o tipo pelo conteúdo | assinaturas — feito |
| V12.5.2 | Arquivo enviado nunca executa como HTML/JS | `attachment` + `octet-stream` — feito |
| V13.2.3 | API com CSRF | idem V4.2.2 |
| V14.4.1–14.4.7 | Cabeçalhos (CSP, nosniff, HSTS, Referrer-Policy, frame-ancestors) | feito |
| V14.5.3 | CORS restrito | o servidor não manda cabeçalhos CORS (só a própria origem) — feito |
| V10.3.2 / V14.2 | Dependências | só biblioteca padrão do Python — feito |

Fora do código (operação): backup cifrado do banco, firewall, atualização do sistema operacional, rotação dos
segredos SMTP e o proxy com TLS (seção abaixo).

## Migração (o que acontece ao subir a versão nova)

- **Todas as sessões abertas caem uma vez** (a tabela `sessao` antiga, com token em texto, é apagada e
  recriada). Cada pessoa entra de novo.
- Tabelas novas criadas sozinhas: `dispositivo_chave`, `acesso_log`, `segredo`, `conta_token`, `consentimento`;
  colunas novas em `conta` (`confirmado`, `consentimento_*`, `totp_*`) e `sessao` (`visto`, `reauth`).
  Contas que já existiam ficam **confirmadas**; o consentimento delas fica **pendente** até aceitarem a versão atual.
- Senha mínima passa de 10 para 12 caracteres e recusa senhas comuns (só ao criar ou trocar; as senhas atuais
  continuam entrando).
- `POST /api/contas` por quem não é da direção: era 400 (o hub recusava), agora 403 (o servidor barra antes).
- Papéis: nada muda no banco. Contas `operador` seguem como equipe; quem precisa aprovar compras, publicar
  na loja ou editar o site tem de ser `administrador` (direção).
- Instalações `login:false` acessadas de fora da rede local passam a pedir login.
- Receptor V6 na rede local continua entregando sem chave. Se o hub for exposto (`PHYSIS_EXPOSTO=1`) ou o
  receptor falar por um proxy, crie uma chave para ele (ou, só em rede fechada na fase 2,
  `PHYSIS_ACEITAR_SEM_CHAVE=1`). Quando todo aparelho tiver chave: `PHYSIS_ACEITAR_SEM_CHAVE=0`.

## Servidor da internet (máquina do Eric): proxy reverso com TLS

Variáveis do serviço do hub:

```
PHYSIS_ENDERECO=127.0.0.1
PHYSIS_PORTA=8700
PHYSIS_PROXY_CONFIAVEL=127.0.0.1,::1
PHYSIS_EXPOSTO=1
PHYSIS_URL_PUBLICA=https://hub.exemplo.com.br
PHYSIS_ACEITAR_SEM_CHAVE=0
```

**Caddy** (`/etc/caddy/Caddyfile`; certificado Let's Encrypt automático, já manda `X-Forwarded-For` e
`X-Forwarded-Proto`):

```
hub.exemplo.com.br {
    encode gzip
    request_body {
        max_size 60MB
    }
    reverse_proxy 127.0.0.1:8700 {
        header_up X-Forwarded-For {remote_host}
    }
}
```

**nginx** (certificado com `certbot --nginx -d hub.exemplo.com.br`):

```
server {
    listen 80;
    server_name hub.exemplo.com.br;
    return 301 https://$host$request_uri;
}
server {
    listen 443 ssl http2;
    server_name hub.exemplo.com.br;
    ssl_certificate     /etc/letsencrypt/live/hub.exemplo.com.br/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/hub.exemplo.com.br/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 60m;          # DWG até 50 MB
    location / {
        proxy_pass http://127.0.0.1:8700;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;   # substitui (não acumula) o que o cliente mandou
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

Conferir depois de subir:

- `curl -I https://hub.exemplo.com.br/api/instancia` mostra `Strict-Transport-Security`.
- Entrar pela tela: o cookie `physis_sessao` aparece com `Secure; HttpOnly; SameSite=Strict`.
- `curl https://hub.exemplo.com.br/api/central/caixa` devolve 401.
- Firewall: só 80/443 abertos; a porta 8700 não deve responder de fora.
- A primeira conta: crie por um túnel SSH (`ssh -L 8700:127.0.0.1:8700 eric@servidor` e abra
  `http://localhost:8700/gestao`, que conta como rede local) ou ligue `PHYSIS_PRIMEIRA_CONTA_EXTERNA=1` só
  durante a criação.

## Limites conhecidos

- Os baldes de limite vivem na memória de um processo: reiniciar zera; vários processos não dividem baldes.
- Sem `PHYSIS_PROXY_CONFIAVEL`, atrás de um proxy todo mundo parece vir do IP do proxy: os limites passam a
  valer para todos juntos. Configure-o.
- O proxy confiável que não manda `X-Forwarded-For` faz o pedido contar como "de fora" (mais seguro).
