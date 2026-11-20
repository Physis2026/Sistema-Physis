/* physis-conta.js v1 · 15/11/2026 · ORIGINAL ÚNICO: vai embutido, cópia igual, no bloco <script id="physis-conta">
 * da Gestão Physis (e, pelo integrador, no painel da plataforma). Não editar a cópia embutida: editar este arquivo.
 *
 * Telas da conta e da segurança, iguais em todo lugar. Sem nada de fora (sem internet, sem eval, sem biblioteca).
 * Todas as rotas são do servidor da Physis (physis_hub/servidor.py e seguranca.py; ver docs/SEGURANCA.md).
 *
 * CONTRATO
 *   PhysisConta.iniciar({ instancia, papel, idioma, aoMudar, lugarAvisos, termosUrl })
 *     instancia   : objeto de GET /api/instancia, ou null (aí o próprio módulo busca, se a tela veio do servidor)
 *     papel       : "administrador" | "operador" | "cliente" (se faltar, vale instancia.papel)
 *     idioma      : function () { return "pt" | "en"; }
 *     aoMudar     : function (o_que, dados) — chamado depois de: "senha", "2fa", "consentimento", "conta_apagada",
 *                   "convite", "chave", "reautenticado", "instancia"
 *     lugarAvisos : elemento ou seletor onde entram as faixas (e-mail a confirmar, consentimento); sem ele, faixa fixa embaixo
 *     termosUrl   : endereço da página dos Termos (opcional; sem ele, usa window.PHYSIS_JURIDICO numa janela, se houver)
 *     Instala UMA vez um embrulho em window.fetch:
 *       - POST/PUT/PATCH/DELETE para o mesmo servidor ganham o cabeçalho X-Physis-CSRF (token de /api/instancia,
 *         renovado pelas respostas de login que trazem "csrf");
 *       - 403 {reautenticar:true}: abre a janela "Confirme a sua senha" (senha + código 2FA se a conta tiver),
 *         POST /api/conta/reautenticar {senha, codigo?} e repete o pedido original uma vez;
 *       - 403 {csrf:true}: renova o token uma vez e repete;
 *       - 403 {confirmar_email:true}: faixa "Confirme o seu e-mail" (reenviar: POST /api/conta/confirmar/reenviar);
 *       - 403 {consentimento:true} ou instancia.consentimento_pendente: faixa com os Termos (versão
 *         instancia.termos_versao) e "Li e aceito" (POST /api/conta/consentimento {versao, aceito:true}).
 *   PhysisConta.telaMinhaConta() → HTML: senha (POST /api/conta/senha), verificação em duas etapas
 *       (POST /api/conta/2fa/iniciar|ativar|desativar), meus dados (GET /api/conta/meus-dados, POST /api/conta/apagar),
 *       retirar o consentimento (POST /api/conta/consentimento {aceito:false}).
 *   PhysisConta.telaConvites() → HTML (direção): convidar (POST /api/convites), lista (GET /api/convites),
 *       revogar (POST /api/convites/<id>/revogar).
 *   PhysisConta.telaChaves() → HTML (direção): chaves dos dispositivos (GET/POST /api/dispositivos/chaves,
 *       POST /api/dispositivos/chaves/<id>/revogar). A chave aparece uma vez só.
 *   PhysisConta.ligar(raiz) → liga os cliques (atributos data-pc-*) e carrega as listas das telas dentro de raiz.
 *   PhysisConta.I18N = { "texto em português": "English" } (todo texto fixo do módulo); PhysisConta.t(s).
 *   PhysisConta.instancia() → a última /api/instancia conhecida; PhysisConta.versao = "1".
 *
 * Aparência: classes .pc-*, só cores de docs/PALETA.md, tema escuro em html[data-tema="escuro"].
 * Acessibilidade: janelas com role=dialog e aria-modal, foco preso, Esc fecha, o foco volta; alvos de 44 px.
 */
(function (g) {
  "use strict";
  if (g.PhysisConta) return;

  /*I18N-INICIO*/
  var I18N = {
    "Confirme a sua senha": "Confirm your password",
    "Para continuar com esta ação, digite a sua senha de novo.": "To continue with this action, type your password again.",
    "Senha": "Password",
    "Código do aplicativo autenticador": "Authenticator app code",
    "Código de 6 dígitos, ou um código de recuperação.": "6-digit code, or a recovery code.",
    "Confirmar": "Confirm",
    "Cancelar": "Cancel",
    "Fechar": "Close",
    "Digite a senha.": "Type the password.",
    "Digite o código do aplicativo autenticador.": "Type the authenticator app code.",
    "O servidor não respondeu.": "The server did not answer.",
    "Não foi possível.": "It was not possible.",
    "Confirme o seu e-mail": "Confirm your e-mail",
    "Algumas partes ficam fechadas até você confirmar o seu e-mail pelo link que enviamos.": "Some parts stay closed until you confirm your e-mail through the link we sent.",
    "Reenviar o e-mail de confirmação": "Resend the confirmation e-mail",
    "E-mail de confirmação enviado. Veja a sua caixa de entrada.": "Confirmation e-mail sent. Check your inbox.",
    "O servidor ainda não tem e-mail configurado: a mensagem não saiu. [A CONFIGURAR NO SERVIDOR]": "The server has no e-mail set up yet: the message was not sent. [TO BE SET UP ON THE SERVER]",
    "Fechar o aviso": "Close the notice",
    "Os Termos de uso e a Política de privacidade": "The Terms of use and the Privacy policy",
    "Para continuar usando, leia e aceite a versão atual (versão {v}).": "To keep using it, read and accept the current version (version {v}).",
    "Ler os termos": "Read the terms",
    "Li e aceito": "I have read and accept",
    "Aceite registrado. Obrigado.": "Acceptance recorded. Thank you.",
    "Endereço dos termos: [A CONFIGURAR]": "Terms address: [TO BE SET UP]",
    "Termos de uso e Política de privacidade": "Terms of use and Privacy policy",
    "Minuta em revisão jurídica.": "Draft under legal review.",
    "Trocar a senha": "Change the password",
    "Senha atual": "Current password",
    "Senha nova": "New password",
    "Repita a senha nova": "Repeat the new password",
    "Use pelo menos {n} caracteres. Não há regra de letras, números ou símbolos: uma frase longa e fácil de lembrar é ótima.": "Use at least {n} characters. There is no rule about letters, numbers or symbols: a long, easy-to-remember phrase is great.",
    "As duas senhas novas não são iguais.": "The two new passwords are not the same.",
    "A senha nova precisa de pelo menos {n} caracteres.": "The new password needs at least {n} characters.",
    "Senha trocada.": "Password changed.",
    "Verificação em duas etapas": "Two-step verification",
    "Além da senha, a entrada pede um código de 6 dígitos que muda a cada 30 segundos, gerado por um aplicativo autenticador no seu celular. Recomendado para a direção.": "Besides the password, signing in asks for a 6-digit code that changes every 30 seconds, made by an authenticator app on your phone. Recommended for management.",
    "Situação: ligada.": "Status: on.",
    "Situação: desligada.": "Status: off.",
    "Situação: o servidor não informou.": "Status: the server did not say.",
    "Ligar a verificação em duas etapas": "Turn on two-step verification",
    "Passo 1. No aplicativo autenticador (TOTP), escolha acrescentar uma conta e digite esta chave:": "Step 1. In the authenticator app (TOTP), choose to add an account and type this key:",
    "Chave para o aplicativo": "Key for the app",
    "Copiar a chave": "Copy the key",
    "Endereço para aplicativos que aceitam colar (otpauth)": "Address for apps that accept pasting (otpauth)",
    "Copiar o endereço": "Copy the address",
    "A chave é secreta: não mande por e-mail nem por mensagem.": "The key is secret: do not send it by e-mail or message.",
    "Passo 2. Digite o código de 6 dígitos que o aplicativo mostra.": "Step 2. Type the 6-digit code the app shows.",
    "Código de 6 dígitos": "6-digit code",
    "Confirmar e ligar": "Confirm and turn on",
    "Desistir": "Give up",
    "Verificação em duas etapas ligada.": "Two-step verification is on.",
    "Códigos de recuperação": "Recovery codes",
    "Guarde estes códigos agora: eles não aparecem de novo. Cada um serve uma vez, se você perder o celular.": "Save these codes now: they will not appear again. Each one works once, if you lose your phone.",
    "Copiar os códigos": "Copy the codes",
    "Baixar em arquivo .txt": "Download as a .txt file",
    "Já guardei os códigos": "I have saved the codes",
    "Códigos de recuperação da conta Physis": "Physis account recovery codes",
    "Cada código entra uma vez só.": "Each code works only once.",
    "Para desligar, digite um código do aplicativo (ou um código de recuperação).": "To turn it off, type a code from the app (or a recovery code).",
    "Código": "Code",
    "Desligar a verificação em duas etapas": "Turn off two-step verification",
    "Verificação em duas etapas desligada.": "Two-step verification is off.",
    "Copiado.": "Copied.",
    "Não deu para copiar: selecione o texto e use Ctrl+C.": "Could not copy: select the text and press Ctrl+C.",
    "Arquivo baixado.": "File downloaded.",
    "Meus dados": "My data",
    "Tudo o que o servidor guarda sobre você (conta, entradas, pedidos, e-mails), num arquivo JSON. Direito previsto na LGPD (art. 18).": "Everything the server keeps about you (account, sign-ins, requests, e-mails), in a JSON file. A right under Brazil's LGPD (art. 18).",
    "Baixar os meus dados (JSON)": "Download my data (JSON)",
    "Apagar a minha conta": "Delete my account",
    "O que acontece:": "What happens:",
    "a conta e as sessões abertas são apagadas;": "the account and open sessions are deleted;",
    "pedidos e chamados ficam sem o seu nome e contato; os anexos dos pedidos são apagados;": "requests and tickets lose your name and contact; request attachments are deleted;",
    "e-mails ainda não enviados para você são apagados; os já enviados perdem o endereço e o texto;": "e-mails not yet sent to you are deleted; those already sent lose the address and text;",
    "compras ficam guardadas por 5 anos (obrigação fiscal), sem nome, e-mail, CPF, telefone e endereço;": "purchases stay for 5 years (tax obligation), without name, e-mail, CPF, phone and address;",
    "o registro de acessos fica até completar 6 meses (Marco Civil da Internet, art. 15);": "the access log stays until it is 6 months old (Brazilian Internet Act, art. 15);",
    "a última conta da direção não pode ser apagada: passe a direção a outra pessoa antes.": "the last management account cannot be deleted: hand management to someone else first.",
    "Não dá para desfazer.": "It cannot be undone.",
    "Sua senha": "Your password",
    "Código do aplicativo (se a verificação em duas etapas estiver ligada)": "App code (if two-step verification is on)",
    "Entendi que apagar a conta não pode ser desfeito.": "I understand that deleting the account cannot be undone.",
    "Marque que entendeu antes de apagar.": "Tick that you understand before deleting.",
    "Apagar a conta de vez?": "Delete the account for good?",
    "A conta e as sessões somem agora e você sai do sistema. Não dá para desfazer.": "The account and sessions are removed now and you are signed out. It cannot be undone.",
    "Sim, apagar a minha conta": "Yes, delete my account",
    "Conta apagada. Saindo…": "Account deleted. Signing out…",
    "Consentimento": "Consent",
    "Você pode retirar o aceite dos Termos de uso e da Política de privacidade. Sem ele, a conta pode ficar limitada até você aceitar de novo.": "You can withdraw your acceptance of the Terms of use and the Privacy policy. Without it, the account may be limited until you accept again.",
    "Retirar o meu consentimento": "Withdraw my consent",
    "Retirar o consentimento?": "Withdraw consent?",
    "O registro fica com a data. Para voltar a usar tudo, aceite os termos de novo.": "The record keeps the date. To use everything again, accept the terms again.",
    "Sim, retirar": "Yes, withdraw",
    "Consentimento retirado.": "Consent withdrawn.",
    "Aceite pendente: há uma versão nova dos termos.": "Acceptance pending: there is a new version of the terms.",
    "Convidar pessoa": "Invite a person",
    "A pessoa recebe um link por e-mail, escolhe o próprio nome e a senha. O convite vale 7 dias e pode ser revogado. Convite para a direção pede a sua senha de novo.": "The person gets a link by e-mail and chooses their own name and password. The invitation is valid for 7 days and can be revoked. Inviting to management asks for your password again.",
    "E-mail": "E-mail",
    "Papel": "Role",
    "Direção": "Management",
    "Equipe": "Team",
    "Cliente": "Client",
    "Nome (opcional)": "Name (optional)",
    "Enviar convite": "Send invitation",
    "Informe um e-mail válido.": "Enter a valid e-mail.",
    "Convite enviado para {e}. Vale 7 dias.": "Invitation sent to {e}. Valid for 7 days.",
    "Convite criado para {e}, mas o servidor ainda não tem e-mail configurado: a mensagem não saiu. [A CONFIGURAR NO SERVIDOR]": "Invitation created for {e}, but the server has no e-mail set up yet: the message was not sent. [TO BE SET UP ON THE SERVER]",
    "Convites": "Invitations",
    "Atualizar a lista": "Refresh the list",
    "Carregando…": "Loading…",
    "Nenhum convite ainda.": "No invitations yet.",
    "Nome": "Name",
    "Situação": "Status",
    "Vale até": "Valid until",
    "Ações": "Actions",
    "pendente": "pending",
    "aceito": "accepted",
    "vencido": "expired",
    "revogado": "revoked",
    "Revogar": "Revoke",
    "Revogar o convite de": "Revoke the invitation of",
    "Convite revogado.": "Invitation revoked.",
    "Só a direção vê e faz convites.": "Only management sees and sends invitations.",
    "Sem o servidor da Physis, esta parte não funciona.": "Without the Physis server, this part does not work.",
    "Chaves dos dispositivos": "Device keys",
    "Cada receptor ou nó manda os dados com uma chave. A chave aparece uma vez só, ao ser criada: grave no secrets.h do aparelho, nunca no código. Revogar vale na hora. Criar uma chave pede a sua senha de novo.": "Each receiver or node sends data with a key. The key appears only once, when created: store it in the device's secrets.h, never in code. Revoking takes effect at once. Creating a key asks for your password again.",
    "Nome da chave (por exemplo, o lugar)": "Key name (for example, the place)",
    "Nó (número de 0 a 9999)": "Node (number from 0 to 9999)",
    "Vazio = chave de receptor, que aceita qualquer nó.": "Empty = receiver key, which accepts any node.",
    "Criar chave": "Create key",
    "O nó vai de 0 a 9999.": "The node goes from 0 to 9999.",
    "Chave criada": "Key created",
    "Guarde a chave agora: ela não aparece de novo.": "Save the key now: it will not appear again.",
    "Chave do dispositivo": "Device key",
    "Já guardei a chave": "I have saved the key",
    "Nenhuma chave ainda.": "No keys yet.",
    "Nó": "Node",
    "todos (receptor)": "all (receiver)",
    "Criada em": "Created on",
    "Por": "By",
    "Último uso": "Last use",
    "ativa": "active",
    "revogada": "revoked",
    "nunca": "never",
    "Revogar a chave": "Revoke the key",
    "Revogar esta chave?": "Revoke this key?",
    "O aparelho que usa esta chave deixa de conseguir mandar dados na hora.": "The device using this key stops being able to send data at once.",
    "Sim, revogar": "Yes, revoke",
    "Chave revogada.": "Key revoked.",
    "Esta parte depende do servidor. [A CONFIGURAR NO SERVIDOR]": "This part depends on the server. [TO BE SET UP ON THE SERVER]",
    "Entre no servidor para usar esta parte.": "Sign in to the server to use this part.",
    "O seu papel não permite esta ação.": "Your role does not allow this action."
  };
  /*I18N-FIM*/

  var op = { instancia: null, papel: null, idioma: function () { return "pt"; }, aoMudar: null, lugarAvisos: null, termosUrl: "" };
  var csrf = null, instalado = false, fetchOrig = null, reautPromessa = null, iniciado = false;
  var est = { senhaMsg: null, tfa: null, tfaMsg: null, codigos: null, dadosMsg: null, consMsg: null,
              convMsg: null, convites: null, convErro: "", chaveMsg: null, chaves: null, chaveErro: "", chaveNova: null };

  function en() { try { return op.idioma && op.idioma() === "en"; } catch (e) { return false; } }
  function t(s) { return en() && Object.prototype.hasOwnProperty.call(I18N, s) ? I18N[s] : s; }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function servidor() { return /^https?:$/.test(location.protocol); }
  function papel() { return op.papel || (op.instancia && op.instancia.papel) || ""; }
  function direcao() { return papel() === "administrador"; }
  function avisar(o, d) { if (typeof op.aoMudar === "function") { try { op.aoMudar(o, d); } catch (e) { /* a tela que hospeda não derruba o módulo */ } } }
  function senhaMin() { var n = op.instancia && +op.instancia.senha_min; return n > 0 ? n : 12; }
  function dataHora(ts) { if (!ts) return "—"; var d = new Date(ts > 1e12 ? ts : ts * 1000); return isFinite(d) ? d.toLocaleString(en() ? "en-GB" : "pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—"; }
  function hoje() { var d = new Date(), p = function (n) { return (n < 10 ? "0" : "") + n; }; return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()); }

  /* ══ embrulho do fetch: CSRF, reautenticação, e-mail e consentimento ══ */
  function urlDe(entrada) { return typeof entrada === "string" ? entrada : (entrada && entrada.url) || String(entrada || ""); }
  function resolver(u) { try { return new URL(u, location.href); } catch (e) { return null; } }
  function mesmaOrigem(u) { var x = resolver(u); return !!x && x.origin === location.origin; }
  function caminho(u) { var x = resolver(u); return x ? x.pathname : ""; }
  function comCsrf(entrada, init) {
    var novo = {}, k;
    if (init) for (k in init) if (Object.prototype.hasOwnProperty.call(init, k)) novo[k] = init[k];
    var h = new Headers((init && init.headers) || (typeof entrada !== "string" && entrada && entrada.headers) || undefined);
    if (csrf) h.set("X-Physis-CSRF", csrf);
    novo.headers = h;
    return novo;
  }
  function guardarCsrf(j) { if (j && typeof j.csrf === "string" && j.csrf) csrf = j.csrf; }
  var ROTAS_COM_TOKEN = ["/api/instancia", "/api/conta/entrar", "/api/conta/criar", "/api/conta/convite/aceitar"];
  function olhar(url, r) {
    var c = caminho(url);
    if (ROTAS_COM_TOKEN.indexOf(c) >= 0 && r.ok) {
      r.clone().json().then(function (j) { guardarCsrf(j); if (c === "/api/instancia" && j && typeof j === "object") { op.instancia = j; if (j.consentimento_pendente) faixaConsentimento(j.termos_versao); } }, function () {});
    }
    return r;
  }
  function tratar(r, url, mandar, tentativa) {
    olhar(url, r);
    if (r.status !== 403 || !mesmaOrigem(url)) return r;
    return r.clone().json().then(function (j) {
      if (!j || typeof j !== "object") return r;
      var repetir = function () { return mandar().then(function (r2) { return tratar(r2, url, mandar, 1); }); };
      if (j.csrf === true && mandar && tentativa === 0) return renovarCsrf().then(repetir, function () { return r; });
      if (j.reautenticar && mandar && tentativa === 0) return pedirReautenticacao().then(function (ok) { return ok ? repetir() : r; });
      if (j.confirmar_email) faixaEmail();
      if (j.consentimento) faixaConsentimento(j.versao || (op.instancia && op.instancia.termos_versao));
      return r;
    }, function () { return r; });
  }
  function instalar() {
    if (instalado || typeof g.fetch !== "function") return;
    instalado = true; fetchOrig = g.fetch;
    g.fetch = function (entrada, init) {
      var url = urlDe(entrada), metodo = String((init && init.method) || (typeof entrada !== "string" && entrada && entrada.method) || "GET").toUpperCase();
      if (!mesmaOrigem(url)) return fetchOrig.apply(g, arguments);
      if (!/^(POST|PUT|PATCH|DELETE)$/.test(metodo)) return fetchOrig.apply(g, arguments).then(function (r) { return tratar(r, url, null, 1); });
      var reserva = typeof entrada !== "string" && entrada && entrada.clone ? entrada.clone() : null, usos = 0;
      var mandar = function () { var e = usos++ === 0 || !reserva ? entrada : reserva.clone(); return fetchOrig.call(g, e, comCsrf(entrada, init)); };
      return mandar().then(function (r) { return tratar(r, url, mandar, 0); });
    };
  }
  function bruto() { return fetchOrig || g.fetch; }
  function renovarCsrf() {
    return bruto().call(g, "/api/instancia", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (j) { guardarCsrf(j); if (j && typeof j === "object") op.instancia = j; return j; });
  }
  /* pedidos do próprio módulo: passam pelo embrulho (CSRF e reautenticação) */
  function pedir(url, corpo, metodo) {
    var init = corpo === undefined && !metodo ? { cache: "no-store" } : { method: metodo || "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo || {}) };
    return g.fetch(url, init).then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { j = j && typeof j === "object" ? j : {}; j._status = r.status; return j; }); },
      function () { return { ok: false, _status: 0, erro: t("O servidor não respondeu.") }; });
  }
  function erroDe(j) {
    if (j._status === 401) return t("Entre no servidor para usar esta parte.");
    if (j._status === 404 && !j.erro) return t("Esta parte depende do servidor. [A CONFIGURAR NO SERVIDOR]");
    if (j._status === 403 && !j.erro) return t("O seu papel não permite esta ação.");
    return j.erro || t("Não foi possível.");
  }

  /* ══ janelas acessíveis ══ */
  var nJan = 0;
  function abrirJanela(titulo, corpo, botoes, aoEnviar) {
    var antes = document.activeElement, id = "pc-jan-" + (++nJan);
    var fundo = document.createElement("div"); fundo.className = "pc-fundo";
    fundo.innerHTML = "<form class='pc-janela pc' role='dialog' aria-modal='true' aria-labelledby='" + id + "-t' aria-describedby='" + id + "-c' novalidate>" +
      "<h2 id='" + id + "-t' class='pc-h'>" + esc(titulo) + "</h2><div id='" + id + "-c'>" + corpo + "</div><p class='pc-msg' role='alert' data-pc-jmsg></p>" +
      "<div class='pc-barra'>" + botoes.map(function (b, i) { return "<button type='" + (i === 0 ? "submit" : "button") + "' class='pc-b" + (b.prim ? " pc-p" : "") + (b.perigo ? " pc-perigo" : "") + "' data-pc-jb='" + i + "'>" + esc(b.rotulo) + "</button>"; }).join("") + "</div></form>";
    document.body.appendChild(fundo);
    var form = fundo.firstChild, fechada = false;
    function focaveis() { return Array.prototype.filter.call(form.querySelectorAll("button,input,textarea,select,a[href],[tabindex]:not([tabindex='-1'])"), function (x) { return !x.disabled && x.offsetParent !== null; }); }
    function fechar(v) { if (fechada) return; fechada = true; fundo.remove(); document.removeEventListener("keydown", tecla, true); if (antes && antes.focus) { try { antes.focus(); } catch (e) {} } if (jan.aoFechar) jan.aoFechar(v); }
    function tecla(ev) {
      if (ev.key === "Escape") { ev.preventDefault(); fechar(false); return; }
      if (ev.key !== "Tab") return; var f = focaveis(); if (!f.length) return;
      var pri = f[0], ult = f[f.length - 1];
      if (ev.shiftKey && (document.activeElement === pri || !form.contains(document.activeElement))) { ev.preventDefault(); ult.focus(); }
      else if (!ev.shiftKey && (document.activeElement === ult || !form.contains(document.activeElement))) { ev.preventDefault(); pri.focus(); }
    }
    document.addEventListener("keydown", tecla, true);
    var jan = { form: fundo, fechar: fechar, aoFechar: null, msg: function (s) { var m = form.querySelector("[data-pc-jmsg]"); if (m) m.textContent = s || ""; } };
    form.addEventListener("submit", function (ev) { ev.preventDefault(); if (aoEnviar) aoEnviar(jan); else fechar(true); });
    form.addEventListener("click", function (ev) { var b = ev.target.closest ? ev.target.closest("[data-pc-jb]") : null; if (!b || b.type === "submit") return; var bb = botoes[+b.getAttribute("data-pc-jb")]; if (bb && bb.acao) bb.acao(jan); else fechar(false); });
    setTimeout(function () { var f = form.querySelector("input,textarea") || focaveis()[0]; if (f) f.focus(); }, 0);
    return jan;
  }
  function confirmar(titulo, texto, rotuloSim) {
    return new Promise(function (ok) {
      var j = abrirJanela(titulo, "<p>" + esc(texto) + "</p>", [{ rotulo: rotuloSim, prim: true, perigo: true }, { rotulo: t("Cancelar") }]);
      j.aoFechar = ok;
    });
  }
  function pedirReautenticacao() {
    if (reautPromessa) return reautPromessa;
    var com2fa = !!(op.instancia && op.instancia.dois_fatores);
    reautPromessa = new Promise(function (pronto) {
      var corpo = "<p>" + esc(t("Para continuar com esta ação, digite a sua senha de novo.")) + "</p>" +
        "<div class='pc-campo'><label for='pc-ra-senha'>" + esc(t("Senha")) + "</label><input id='pc-ra-senha' class='pc-c' type='password' autocomplete='current-password' required></div>" +
        "<div class='pc-campo' data-pc-ra-cod" + (com2fa ? "" : " hidden") + "><label for='pc-ra-cod'>" + esc(t("Código do aplicativo autenticador")) + "</label><div id='pc-ra-cod-aj' class='pc-aj'>" + esc(t("Código de 6 dígitos, ou um código de recuperação.")) + "</div><input id='pc-ra-cod' class='pc-c' inputmode='numeric' autocomplete='one-time-code' aria-describedby='pc-ra-cod-aj'></div>";
      var jan = abrirJanela(t("Confirme a sua senha"), corpo, [{ rotulo: t("Confirmar"), prim: true }, { rotulo: t("Cancelar") }], function (j) {
        var s = j.form.querySelector("#pc-ra-senha"), c = j.form.querySelector("#pc-ra-cod"), caixa = j.form.querySelector("[data-pc-ra-cod]");
        if (!s.value) { j.msg(t("Digite a senha.")); s.focus(); return; }
        var corpo2 = { senha: s.value }; if (!caixa.hidden && c.value.trim()) corpo2.codigo = c.value.trim();
        bruto().call(g, "/api/conta/reautenticar", comCsrf("/api/conta/reautenticar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo2) }))
          .then(function (r) { return r.json().catch(function () { return {}; }); })
          .then(function (x) {
            if (x && x.ok) { j.fechar(true); avisar("reautenticado"); return; }
            if (x && x.precisa_2fa) { caixa.hidden = false; j.msg(t("Digite o código do aplicativo autenticador.")); c.focus(); return; }
            j.msg((x && x.erro) || t("Não foi possível.")); s.select(); s.focus();
          }, function () { j.msg(t("O servidor não respondeu.")); });
      });
      jan.aoFechar = function (v) { reautPromessa = null; pronto(!!v); };
    });
    return reautPromessa;
  }

  /* ══ faixas de aviso ══ */
  function lugarFaixas() {
    var l = op.lugarAvisos; if (typeof l === "string") l = document.querySelector(l);
    if (l) return l;
    var x = document.getElementById("pc-faixas");
    if (!x) { x = document.createElement("div"); x.id = "pc-faixas"; x.className = "pc pc-faixas-fixas"; document.body.appendChild(x); }
    return x;
  }
  function faixa(id, html) {
    if (!document.body) return null;
    var f = document.getElementById(id);
    if (!f) { f = document.createElement("div"); f.id = id; f.className = "pc pc-faixa"; f.setAttribute("role", "region"); lugarFaixas().appendChild(f); }
    f.innerHTML = html + "<button type='button' class='pc-b pc-x' data-pc-faixa-x aria-label='" + esc(t("Fechar o aviso")) + "'>×</button>";
    if (!f._pc) { f._pc = true; ligarFaixa(f); }
    return f;
  }
  function ligarFaixa(f) {
    f.addEventListener("click", function (ev) {
      var b = ev.target.closest ? ev.target.closest("button,a") : null; if (!b) return;
      if (b.hasAttribute("data-pc-faixa-x")) { f.remove(); return; }
      if (b.hasAttribute("data-pc-reenviar")) { b.disabled = true; pedir("/api/conta/confirmar/reenviar", {}).then(function (j) { b.disabled = false; var m = f.querySelector("[data-pc-fmsg]"); if (m) m.textContent = j.ok ? (j.enviado ? t("E-mail de confirmação enviado. Veja a sua caixa de entrada.") : t("O servidor ainda não tem e-mail configurado: a mensagem não saiu. [A CONFIGURAR NO SERVIDOR]")) : erroDe(j); }); return; }
      if (b.hasAttribute("data-pc-aceitar")) { b.disabled = true; var v = b.getAttribute("data-pc-aceitar"); pedir("/api/conta/consentimento", { versao: v, aceito: true }).then(function (j) { b.disabled = false; var m = f.querySelector("[data-pc-fmsg]"); if (j.ok) { if (op.instancia) op.instancia.consentimento_pendente = false; f.innerHTML = "<p role='status'>" + esc(t("Aceite registrado. Obrigado.")) + "</p>"; setTimeout(function () { f.remove(); }, 2500); avisar("consentimento", { aceito: true, versao: v }); } else if (m) m.textContent = erroDe(j); }); return; }
      if (b.hasAttribute("data-pc-ler-termos")) { ev.preventDefault(); lerTermos(); }
    });
  }
  function faixaEmail() {
    faixa("pc-faixa-email", "<p><strong>" + esc(t("Confirme o seu e-mail")) + "</strong> · " + esc(t("Algumas partes ficam fechadas até você confirmar o seu e-mail pelo link que enviamos.")) + "</p>" +
      "<div class='pc-barra'><button type='button' class='pc-b pc-p' data-pc-reenviar>" + esc(t("Reenviar o e-mail de confirmação")) + "</button></div><p class='pc-msg' role='status' data-pc-fmsg></p>");
  }
  function linkTermos() {
    if (op.termosUrl) return "<a class='pc-b' href='" + esc(op.termosUrl) + "' target='_blank' rel='noopener'>" + esc(t("Ler os termos")) + "</a>";
    if (g.PHYSIS_JURIDICO) return "<button type='button' class='pc-b' data-pc-ler-termos>" + esc(t("Ler os termos")) + "</button>";
    return "<span class='pc-aj'>" + esc(t("Endereço dos termos: [A CONFIGURAR]")) + "</span>";
  }
  function faixaConsentimento(versao) {
    if (!versao) return;
    faixa("pc-faixa-termos", "<p><strong>" + esc(t("Os Termos de uso e a Política de privacidade")) + "</strong> · " + esc(t("Para continuar usando, leia e aceite a versão atual (versão {v}).").replace("{v}", versao)) + "</p>" +
      "<div class='pc-barra'>" + linkTermos() + "<button type='button' class='pc-b pc-p' data-pc-aceitar='" + esc(versao) + "'>" + esc(t("Li e aceito")) + "</button></div><p class='pc-msg' role='status' data-pc-fmsg></p>");
  }
  function lerTermos() {
    var J = g.PHYSIS_JURIDICO || {}, partes = [J.termos, J.privacidade].filter(Boolean), limpa = function (s) { return esc(String(s).replace(/\*\*/g, "")); };
    var corpo = "<p class='pc-aj'>" + esc((J.situacao ? t("Minuta em revisão jurídica.") : "") + (J.versao ? " · " + J.versao : "")) + "</p><div class='pc-rolar' tabindex='0'>" +
      partes.map(function (p) { return "<h3>" + esc(p.titulo || "") + "</h3>" + (p.blocos || []).map(function (b) { return "<h4>" + limpa(b.t || "") + "</h4>" + (b.p || []).map(function (x) { return "<p>" + limpa(x) + "</p>"; }).join(""); }).join(""); }).join("") + "</div>";
    abrirJanela(t("Termos de uso e Política de privacidade"), corpo, [{ rotulo: t("Fechar"), prim: true }]);
  }

  /* ══ telas ══ */
  function msgHtml(m) { return "<p class='pc-msg" + (m && m.erro ? " pc-erro" : m ? " pc-ok" : "") + "' role='status' aria-live='polite'>" + esc(m ? m.texto : "") + "</p>"; }
  function campo(id, rot, controle, aj) { return "<div class='pc-campo'><label for='" + id + "'>" + esc(rot) + "</label>" + (aj ? "<div id='" + id + "-aj' class='pc-aj'>" + esc(aj) + "</div>" : "") + controle + "</div>"; }
  function inp(id, tipo, extra, aj) { return "<input id='" + id + "' class='pc-c' type='" + (tipo || "text") + "'" + (aj ? " aria-describedby='" + id + "-aj'" : "") + (extra || "") + ">"; }
  function grupos4(s) { return String(s || "").replace(/\s+/g, "").replace(/(.{4})/g, "$1 ").trim(); }

  function corpoMinha() {
    var n = senhaMin(), dois = op.instancia ? op.instancia.dois_fatores : null, h = "";
    h += "<section class='pc-cartao' aria-labelledby='pc-h-senha'><h2 id='pc-h-senha' class='pc-h'>" + esc(t("Trocar a senha")) + "</h2><form data-pc-form='senha' novalidate>" +
      campo("pc-s-atual", t("Senha atual"), inp("pc-s-atual", "password", " autocomplete='current-password'")) +
      campo("pc-s-nova", t("Senha nova"), inp("pc-s-nova", "password", " autocomplete='new-password'", true), t("Use pelo menos {n} caracteres. Não há regra de letras, números ou símbolos: uma frase longa e fácil de lembrar é ótima.").replace("{n}", n)) +
      campo("pc-s-nova2", t("Repita a senha nova"), inp("pc-s-nova2", "password", " autocomplete='new-password'")) +
      "<div class='pc-barra'><button type='submit' class='pc-b pc-p'>" + esc(t("Trocar a senha")) + "</button></div>" + msgHtml(est.senhaMsg) + "</form></section>";
    h += "<section class='pc-cartao' aria-labelledby='pc-h-2fa'><h2 id='pc-h-2fa' class='pc-h' tabindex='-1'>" + esc(t("Verificação em duas etapas")) + "</h2><p>" + esc(t("Além da senha, a entrada pede um código de 6 dígitos que muda a cada 30 segundos, gerado por um aplicativo autenticador no seu celular. Recomendado para a direção.")) + "</p>";
    if (est.codigos) {
      var txt = est.codigos.join("\n");
      h += "<p class='pc-selo pc-ok'>" + esc(t("Verificação em duas etapas ligada.")) + "</p><h3 class='pc-h3' id='pc-h-rec' tabindex='-1'>" + esc(t("Códigos de recuperação")) + "</h3><p class='pc-selo pc-atencao'>" + esc(t("Guarde estes códigos agora: eles não aparecem de novo. Cada um serve uma vez, se você perder o celular.")) + "</p>" +
        "<ul class='pc-codigos' aria-labelledby='pc-h-rec'>" + est.codigos.map(function (c) { return "<li><code>" + esc(c) + "</code></li>"; }).join("") + "</ul>" +
        "<div class='pc-barra'><button type='button' class='pc-b' data-pc-copiar='" + esc(txt) + "'>" + esc(t("Copiar os códigos")) + "</button><button type='button' class='pc-b' data-pc-baixar-codigos>" + esc(t("Baixar em arquivo .txt")) + "</button><button type='button' class='pc-b pc-p' data-pc-codigos-ok>" + esc(t("Já guardei os códigos")) + "</button></div>";
    } else if (est.tfa) {
      h += "<p>" + esc(t("Passo 1. No aplicativo autenticador (TOTP), escolha acrescentar uma conta e digite esta chave:")) + "</p>" +
        "<p><span class='pc-aj'>" + esc(t("Chave para o aplicativo")) + "</span><br><code class='pc-chave' id='pc-2fa-seg' tabindex='-1'>" + esc(grupos4(est.tfa.segredo)) + "</code></p>" +
        "<div class='pc-barra'><button type='button' class='pc-b' data-pc-copiar='" + esc(est.tfa.segredo) + "'>" + esc(t("Copiar a chave")) + "</button></div>" +
        campo("pc-2fa-uri", t("Endereço para aplicativos que aceitam colar (otpauth)"), "<textarea id='pc-2fa-uri' class='pc-c' readonly rows='3' aria-describedby='pc-2fa-uri-aj'>" + esc(est.tfa.uri) + "</textarea>", t("A chave é secreta: não mande por e-mail nem por mensagem.")) +
        "<div class='pc-barra'><button type='button' class='pc-b' data-pc-copiar='" + esc(est.tfa.uri) + "'>" + esc(t("Copiar o endereço")) + "</button></div>" +
        "<form data-pc-form='2fa-ativar' novalidate><p>" + esc(t("Passo 2. Digite o código de 6 dígitos que o aplicativo mostra.")) + "</p>" +
        campo("pc-2fa-cod", t("Código de 6 dígitos"), inp("pc-2fa-cod", "text", " inputmode='numeric' autocomplete='one-time-code' maxlength='6' pattern='[0-9]*'")) +
        "<div class='pc-barra'><button type='submit' class='pc-b pc-p'>" + esc(t("Confirmar e ligar")) + "</button><button type='button' class='pc-b' data-pc-2fa-desistir>" + esc(t("Desistir")) + "</button></div></form>";
    } else if (dois === true) {
      h += "<p class='pc-selo pc-ok'>" + esc(t("Situação: ligada.")) + "</p><form data-pc-form='2fa-desligar' novalidate><p>" + esc(t("Para desligar, digite um código do aplicativo (ou um código de recuperação).")) + "</p>" +
        campo("pc-2fa-off", t("Código"), inp("pc-2fa-off", "text", " inputmode='numeric' autocomplete='one-time-code'")) +
        "<div class='pc-barra'><button type='submit' class='pc-b pc-perigo'>" + esc(t("Desligar a verificação em duas etapas")) + "</button></div></form>";
    } else {
      h += "<p class='pc-selo'>" + esc(dois === false ? t("Situação: desligada.") : t("Situação: o servidor não informou.")) + "</p><div class='pc-barra'><button type='button' class='pc-b pc-p' data-pc-2fa-iniciar>" + esc(t("Ligar a verificação em duas etapas")) + "</button></div>";
    }
    h += msgHtml(est.tfaMsg) + "</section>";
    h += "<section class='pc-cartao' aria-labelledby='pc-h-dados'><h2 id='pc-h-dados' class='pc-h'>" + esc(t("Meus dados")) + "</h2><p>" + esc(t("Tudo o que o servidor guarda sobre você (conta, entradas, pedidos, e-mails), num arquivo JSON. Direito previsto na LGPD (art. 18).")) + "</p>" +
      "<div class='pc-barra'><button type='button' class='pc-b' data-pc-meus-dados>" + esc(t("Baixar os meus dados (JSON)")) + "</button></div>" +
      "<h3 class='pc-h3'>" + esc(t("Apagar a minha conta")) + "</h3><p>" + esc(t("O que acontece:")) + "</p><ul>" +
      ["a conta e as sessões abertas são apagadas;", "pedidos e chamados ficam sem o seu nome e contato; os anexos dos pedidos são apagados;", "e-mails ainda não enviados para você são apagados; os já enviados perdem o endereço e o texto;",
       "compras ficam guardadas por 5 anos (obrigação fiscal), sem nome, e-mail, CPF, telefone e endereço;", "o registro de acessos fica até completar 6 meses (Marco Civil da Internet, art. 15);",
       "a última conta da direção não pode ser apagada: passe a direção a outra pessoa antes."].map(function (x) { return "<li>" + esc(t(x)) + "</li>"; }).join("") + "</ul><p><strong>" + esc(t("Não dá para desfazer.")) + "</strong></p>" +
      "<form data-pc-form='apagar' novalidate>" + campo("pc-ap-senha", t("Sua senha"), inp("pc-ap-senha", "password", " autocomplete='current-password'")) +
      (dois === false ? "" : campo("pc-ap-cod", t("Código do aplicativo (se a verificação em duas etapas estiver ligada)"), inp("pc-ap-cod", "text", " inputmode='numeric' autocomplete='one-time-code'"))) +
      "<label class='pc-chk'><input type='checkbox' id='pc-ap-ok'> " + esc(t("Entendi que apagar a conta não pode ser desfeito.")) + "</label>" +
      "<div class='pc-barra'><button type='submit' class='pc-b pc-perigo'>" + esc(t("Apagar a minha conta")) + "</button></div></form>" + msgHtml(est.dadosMsg) + "</section>";
    h += "<section class='pc-cartao' aria-labelledby='pc-h-cons'><h2 id='pc-h-cons' class='pc-h'>" + esc(t("Consentimento")) + "</h2>" +
      (op.instancia && op.instancia.consentimento_pendente ? "<p class='pc-selo pc-atencao'>" + esc(t("Aceite pendente: há uma versão nova dos termos.")) + "</p>" : "") +
      "<p>" + esc(t("Você pode retirar o aceite dos Termos de uso e da Política de privacidade. Sem ele, a conta pode ficar limitada até você aceitar de novo.")) + "</p>" +
      "<div class='pc-barra'>" + linkTermos() + "<button type='button' class='pc-b' data-pc-retirar>" + esc(t("Retirar o meu consentimento")) + "</button></div>" + msgHtml(est.consMsg) + "</section>";
    return h;
  }
  function corpoConvites() {
    if (!direcao()) return "<p class='pc-selo'>" + esc(t("Só a direção vê e faz convites.")) + "</p>";
    var h = "<section class='pc-cartao' aria-labelledby='pc-h-conv'><h2 id='pc-h-conv' class='pc-h'>" + esc(t("Convidar pessoa")) + "</h2><p>" + esc(t("A pessoa recebe um link por e-mail, escolhe o próprio nome e a senha. O convite vale 7 dias e pode ser revogado. Convite para a direção pede a sua senha de novo.")) + "</p>" +
      "<form data-pc-form='convite' novalidate><div class='pc-grade'>" + campo("pc-cv-email", t("E-mail"), inp("pc-cv-email", "email", " autocomplete='off' required aria-required='true'")) +
      campo("pc-cv-papel", t("Papel"), "<select id='pc-cv-papel' class='pc-c'><option value='equipe'>" + esc(t("Equipe")) + "</option><option value='direcao'>" + esc(t("Direção")) + "</option><option value='cliente'>" + esc(t("Cliente")) + "</option></select>") +
      campo("pc-cv-nome", t("Nome (opcional)"), inp("pc-cv-nome", "text", " autocomplete='off'")) + "</div>" +
      "<div class='pc-barra'><button type='submit' class='pc-b pc-p'>" + esc(t("Enviar convite")) + "</button></div>" + msgHtml(est.convMsg) + "</form></section>";
    h += "<section class='pc-cartao' aria-labelledby='pc-h-cl'><h2 id='pc-h-cl' class='pc-h'>" + esc(t("Convites")) + (est.convites ? " (" + est.convites.length + ")" : "") + "</h2><div class='pc-barra'><button type='button' class='pc-b' data-pc-convites-atualizar>" + esc(t("Atualizar a lista")) + "</button></div>";
    if (!servidor()) h += "<p class='pc-aj'>" + esc(t("Sem o servidor da Physis, esta parte não funciona.")) + "</p>";
    else if (est.convErro) h += "<p class='pc-msg pc-erro' role='alert'>" + esc(est.convErro) + "</p>";
    else if (!est.convites) h += "<p class='pc-aj'>" + esc(t("Carregando…")) + "</p>";
    else if (!est.convites.length) h += "<p class='pc-aj'>" + esc(t("Nenhum convite ainda.")) + "</p>";
    else {
      var nomeP = { administrador: t("Direção"), operador: t("Equipe"), cliente: t("Cliente") };
      h += "<div class='pc-rolar-x'><table class='pc-tab'><caption class='pc-so-leitor'>" + esc(t("Convites")) + "</caption><thead><tr><th scope='col'>" + esc(t("E-mail")) + "</th><th scope='col'>" + esc(t("Nome")) + "</th><th scope='col'>" + esc(t("Papel")) + "</th><th scope='col'>" + esc(t("Situação")) + "</th><th scope='col'>" + esc(t("Vale até")) + "</th><th scope='col'>" + esc(t("Ações")) + "</th></tr></thead><tbody>" +
        est.convites.map(function (c) { var cls = c.estado === "pendente" ? "pc-atencao" : c.estado === "aceito" ? "pc-ok" : "";
          return "<tr><th scope='row'>" + esc(c.email) + "</th><td>" + esc(c.nome || "—") + "</td><td>" + esc(nomeP[c.papel] || c.papel || "—") + "</td><td><span class='pc-etq " + cls + "'>" + esc(t(c.estado || "")) + "</span></td><td>" + esc(dataHora(c.expira)) + "</td><td>" +
            (c.estado === "pendente" ? "<button type='button' class='pc-b pc-pq' data-pc-revogar-convite='" + esc(c.id) + "' aria-label=\"" + esc(t("Revogar o convite de") + " " + c.email) + "\">" + esc(t("Revogar")) + "</button>" : "") + "</td></tr>"; }).join("") + "</tbody></table></div>";
    }
    return h + "</section>";
  }
  function corpoChaves() {
    if (!direcao()) return "<p class='pc-selo'>" + esc(t("O seu papel não permite esta ação.")) + "</p>";
    var h = "<section class='pc-cartao' aria-labelledby='pc-h-ch'><h2 id='pc-h-ch' class='pc-h'>" + esc(t("Chaves dos dispositivos")) + "</h2><p>" + esc(t("Cada receptor ou nó manda os dados com uma chave. A chave aparece uma vez só, ao ser criada: grave no secrets.h do aparelho, nunca no código. Revogar vale na hora. Criar uma chave pede a sua senha de novo.")) + "</p>";
    if (est.chaveNova) {
      h += "<div class='pc-destaque' role='group' aria-labelledby='pc-h-chn'><h3 class='pc-h3' id='pc-h-chn'>" + esc(t("Chave criada")) + (est.chaveNova.rotulo ? ": " + esc(est.chaveNova.rotulo) : "") + "</h3><p class='pc-selo pc-atencao'>" + esc(t("Guarde a chave agora: ela não aparece de novo.")) + "</p>" +
        campo("pc-ch-valor", t("Chave do dispositivo"), "<input id='pc-ch-valor' class='pc-c pc-mono' readonly value=\"" + esc(est.chaveNova.chave) + "\">") +
        "<div class='pc-barra'><button type='button' class='pc-b' data-pc-copiar='" + esc(est.chaveNova.chave) + "'>" + esc(t("Copiar a chave")) + "</button><button type='button' class='pc-b pc-p' data-pc-chave-ok>" + esc(t("Já guardei a chave")) + "</button></div></div>";
    }
    h += "<form data-pc-form='chave' novalidate><div class='pc-grade'>" + campo("pc-ch-rot", t("Nome da chave (por exemplo, o lugar)"), inp("pc-ch-rot", "text", " maxlength='80' autocomplete='off'")) +
      campo("pc-ch-no", t("Nó (número de 0 a 9999)"), inp("pc-ch-no", "number", " min='0' max='9999' inputmode='numeric'", true), t("Vazio = chave de receptor, que aceita qualquer nó.")) + "</div>" +
      "<div class='pc-barra'><button type='submit' class='pc-b pc-p'>" + esc(t("Criar chave")) + "</button><button type='button' class='pc-b' data-pc-chaves-atualizar>" + esc(t("Atualizar a lista")) + "</button></div>" + msgHtml(est.chaveMsg) + "</form>";
    if (!servidor()) h += "<p class='pc-aj'>" + esc(t("Sem o servidor da Physis, esta parte não funciona.")) + "</p>";
    else if (est.chaveErro) h += "<p class='pc-msg pc-erro' role='alert'>" + esc(est.chaveErro) + "</p>";
    else if (!est.chaves) h += "<p class='pc-aj'>" + esc(t("Carregando…")) + "</p>";
    else if (!est.chaves.length) h += "<p class='pc-aj'>" + esc(t("Nenhuma chave ainda.")) + "</p>";
    else h += "<div class='pc-rolar-x'><table class='pc-tab'><caption class='pc-so-leitor'>" + esc(t("Chaves dos dispositivos")) + "</caption><thead><tr><th scope='col'>" + esc(t("Nome")) + "</th><th scope='col'>" + esc(t("Nó")) + "</th><th scope='col'>" + esc(t("Criada em")) + "</th><th scope='col'>" + esc(t("Por")) + "</th><th scope='col'>" + esc(t("Último uso")) + "</th><th scope='col'>" + esc(t("Situação")) + "</th><th scope='col'>" + esc(t("Ações")) + "</th></tr></thead><tbody>" +
      est.chaves.map(function (c) { return "<tr><th scope='row'>" + esc(c.rotulo || "—") + "</th><td>" + esc(c.no == null ? t("todos (receptor)") : c.no) + "</td><td>" + esc(dataHora(c.criado)) + "</td><td>" + esc(c.por || "—") + "</td><td>" + esc(c.usado ? dataHora(c.usado) : t("nunca")) + "</td><td><span class='pc-etq " + (c.ativa ? "pc-ok" : "") + "'>" + esc(c.ativa ? t("ativa") : t("revogada")) + "</span></td><td>" +
        (c.ativa ? "<button type='button' class='pc-b pc-pq' data-pc-revogar-chave='" + esc(c.id) + "' aria-label=\"" + esc(t("Revogar a chave") + " " + (c.rotulo || c.id)) + "\">" + esc(t("Revogar")) + "</button>" : "") + "</td></tr>"; }).join("") + "</tbody></table></div>";
    return h + "</section>";
  }
  var CORPOS = { minha: corpoMinha, convites: corpoConvites, chaves: corpoChaves };
  function embrulho(nome) { return "<div class='pc pc-tela' data-pc-tela='" + nome + "'>" + CORPOS[nome]() + "</div>"; }
  function pintar(nome, foco) {
    var at = document.activeElement, eraDaTela = at && at.id && at.closest && at.closest("[data-pc-tela='" + nome + "']");
    if (!foco && eraDaTela) foco = document.getElementById(at.id) === at ? "#" + at.id : null;   // redesenhar não pode jogar o foco fora
    var l = document.querySelectorAll("[data-pc-tela='" + nome + "']");
    for (var i = 0; i < l.length; i++) l[i].innerHTML = CORPOS[nome]();
    if (foco) { var x = typeof foco === "string" ? document.querySelector(foco) : foco; if (x && x.focus) { try { x.focus(); } catch (e) {} } }
  }
  function carregarConvites() {
    if (!servidor() || !direcao()) return;
    pedir("/api/convites").then(function (j) { if (j.ok) { est.convites = j.convites || []; est.convErro = ""; } else est.convErro = erroDe(j); pintar("convites"); });
  }
  function carregarChaves() {
    if (!servidor() || !direcao()) return;
    pedir("/api/dispositivos/chaves").then(function (j) { if (j.ok) { est.chaves = j.chaves || []; est.chaveErro = ""; } else est.chaveErro = erroDe(j); pintar("chaves"); });
  }
  function copiar(txt, onde) {
    var fim = function (ok) { var m = onde && onde.closest ? onde.closest(".pc-cartao,.pc-faixa") : null, s = m && m.querySelector(".pc-msg"); if (s) { s.textContent = ok ? t("Copiado.") : t("Não deu para copiar: selecione o texto e use Ctrl+C."); } };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(function () { fim(true); }, function () { fim(false); }); else fim(false);
  }
  function baixar(nome, texto, tipo) {
    var u = URL.createObjectURL(new Blob([texto], { type: tipo || "text/plain;charset=utf-8" })), a = document.createElement("a");
    a.href = u; a.download = nome; document.body.appendChild(a); a.click(); a.remove(); setTimeout(function () { URL.revokeObjectURL(u); }, 2000);
  }
  function valor(raiz, id) { var x = (raiz.querySelector ? raiz.querySelector("#" + id) : null) || document.getElementById(id); return x ? (x.type === "checkbox" ? x.checked : x.value) : ""; }

  function aoEnviar(ev) {
    var f = ev.target, qual = f.getAttribute && f.getAttribute("data-pc-form"); if (!qual) return;
    ev.preventDefault();
    var v = function (id) { return valor(f, id); }, b = f.querySelector("button[type=submit]");
    if (qual === "senha") {
      var n = senhaMin(), nova = v("pc-s-nova");
      if (nova.length < n) { est.senhaMsg = { erro: true, texto: t("A senha nova precisa de pelo menos {n} caracteres.").replace("{n}", n) }; return pintar("minha", "#pc-s-nova"); }
      if (nova !== v("pc-s-nova2")) { est.senhaMsg = { erro: true, texto: t("As duas senhas novas não são iguais.") }; return pintar("minha", "#pc-s-nova2"); }
      if (b) b.disabled = true;
      return pedir("/api/conta/senha", { atual: v("pc-s-atual"), nova: nova }).then(function (j) { est.senhaMsg = j.ok ? { texto: t("Senha trocada.") } : { erro: true, texto: erroDe(j) }; pintar("minha", j.ok ? null : "#pc-s-atual"); if (j.ok) avisar("senha"); });
    }
    if (qual === "2fa-ativar") {
      var cod = String(v("pc-2fa-cod")).replace(/\s+/g, "");
      if (!cod) { est.tfaMsg = { erro: true, texto: t("Digite o código do aplicativo autenticador.") }; return pintar("minha", "#pc-2fa-cod"); }
      if (b) b.disabled = true;
      return pedir("/api/conta/2fa/ativar", { codigo: cod }).then(function (j) {
        if (j.ok) { est.codigos = j.recuperacao || []; est.tfa = null; est.tfaMsg = null; if (op.instancia) op.instancia.dois_fatores = true; pintar("minha", "#pc-h-rec"); avisar("2fa", { ligada: true }); }
        else { est.tfaMsg = { erro: true, texto: erroDe(j) }; pintar("minha", "#pc-2fa-cod"); }
      });
    }
    if (qual === "2fa-desligar") {
      var c2 = String(v("pc-2fa-off")).trim();
      if (!c2) { est.tfaMsg = { erro: true, texto: t("Digite o código do aplicativo autenticador.") }; return pintar("minha", "#pc-2fa-off"); }
      if (b) b.disabled = true;
      return pedir("/api/conta/2fa/desativar", { codigo: c2 }).then(function (j) {
        if (j.ok && op.instancia) op.instancia.dois_fatores = false;
        est.tfaMsg = j.ok ? { texto: t("Verificação em duas etapas desligada.") } : { erro: true, texto: erroDe(j) }; pintar("minha", j.ok ? "#pc-h-2fa" : "#pc-2fa-off"); if (j.ok) avisar("2fa", { ligada: false });
      });
    }
    if (qual === "apagar") {
      if (!v("pc-ap-senha")) { est.dadosMsg = { erro: true, texto: t("Digite a senha.") }; return pintar("minha", "#pc-ap-senha"); }
      if (!v("pc-ap-ok")) { est.dadosMsg = { erro: true, texto: t("Marque que entendeu antes de apagar.") }; return pintar("minha", "#pc-ap-ok"); }
      var corpo = { senha: v("pc-ap-senha") }, cc = String(v("pc-ap-cod") || "").trim(); if (cc) corpo.codigo = cc;
      return confirmar(t("Apagar a conta de vez?"), t("A conta e as sessões somem agora e você sai do sistema. Não dá para desfazer."), t("Sim, apagar a minha conta")).then(function (sim) {
        if (!sim) return;
        pedir("/api/conta/apagar", corpo).then(function (j) {
          if (j.ok) { est.dadosMsg = { texto: t("Conta apagada. Saindo…") }; pintar("minha"); if (typeof op.aoMudar === "function") avisar("conta_apagada", j); else setTimeout(function () { location.reload(); }, 1500); }
          else { est.dadosMsg = { erro: true, texto: erroDe(j) }; pintar("minha", j.precisa_2fa ? "#pc-ap-cod" : "#pc-ap-senha"); }
        });
      });
    }
    if (qual === "convite") {
      var em = String(v("pc-cv-email")).trim();
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(em)) { est.convMsg = { erro: true, texto: t("Informe um e-mail válido.") }; return pintar("convites", "#pc-cv-email"); }
      if (b) b.disabled = true;
      return pedir("/api/convites", { email: em, papel: v("pc-cv-papel"), nome: String(v("pc-cv-nome")).trim() }).then(function (j) {
        est.convMsg = j.ok ? { texto: (j.email_enviado ? t("Convite enviado para {e}. Vale 7 dias.") : t("Convite criado para {e}, mas o servidor ainda não tem e-mail configurado: a mensagem não saiu. [A CONFIGURAR NO SERVIDOR]")).replace("{e}", j.email || em) } : { erro: true, texto: erroDe(j) };
        pintar("convites", j.ok ? null : "#pc-cv-email"); if (j.ok) { carregarConvites(); avisar("convite", j); }
      });
    }
    if (qual === "chave") {
      var no = String(v("pc-ch-no")).trim(), corpoC = { rotulo: String(v("pc-ch-rot")).trim() };
      if (no !== "") { var nn = Number(no); if (!(nn >= 0 && nn <= 9999 && Math.floor(nn) === nn)) { est.chaveMsg = { erro: true, texto: t("O nó vai de 0 a 9999.") }; return pintar("chaves", "#pc-ch-no"); } corpoC.no = nn; }
      if (b) b.disabled = true;
      return pedir("/api/dispositivos/chaves", corpoC).then(function (j) {
        if (j.ok) { est.chaveNova = { chave: j.chave, rotulo: j.rotulo }; est.chaveMsg = null; pintar("chaves", "#pc-ch-valor"); carregarChaves(); avisar("chave", { id: j.id }); }
        else { est.chaveMsg = { erro: true, texto: erroDe(j) }; pintar("chaves", "#pc-ch-rot"); }
      });
    }
  }
  function aoClicar(ev) {
    var b = ev.target.closest ? ev.target.closest("button") : null; if (!b || !b.closest("[data-pc-tela]")) return;
    var id;
    if (b.hasAttribute("data-pc-copiar")) return copiar(b.getAttribute("data-pc-copiar"), b);
    if (b.hasAttribute("data-pc-2fa-iniciar")) { b.disabled = true; return pedir("/api/conta/2fa/iniciar", {}).then(function (j) { if (j.ok) { est.tfa = { segredo: j.segredo, uri: j.uri }; est.tfaMsg = null; pintar("minha", "#pc-2fa-seg"); } else { est.tfaMsg = { erro: true, texto: erroDe(j) }; pintar("minha", "[data-pc-2fa-iniciar]"); } }); }
    if (b.hasAttribute("data-pc-2fa-desistir")) { est.tfa = null; est.tfaMsg = null; return pintar("minha", "[data-pc-2fa-iniciar]"); }
    if (b.hasAttribute("data-pc-baixar-codigos")) { baixar("physis-codigos-de-recuperacao-" + hoje() + ".txt", t("Códigos de recuperação da conta Physis") + "\n" + t("Cada código entra uma vez só.") + "\n\n" + (est.codigos || []).join("\n") + "\n"); est.tfaMsg = { texto: t("Arquivo baixado.") }; return pintar("minha", "[data-pc-baixar-codigos]"); }
    if (b.hasAttribute("data-pc-codigos-ok")) { est.codigos = null; est.tfaMsg = { texto: t("Verificação em duas etapas ligada.") }; return pintar("minha", "#pc-h-2fa"); }
    if (b.hasAttribute("data-pc-meus-dados")) { b.disabled = true; return pedir("/api/conta/meus-dados").then(function (j) { b.disabled = false; if (j._status === 200) { delete j._status; baixar("physis-meus-dados-" + hoje() + ".json", JSON.stringify(j, null, 2), "application/json"); est.dadosMsg = { texto: t("Arquivo baixado.") }; } else est.dadosMsg = { erro: true, texto: erroDe(j) }; pintar("minha", "[data-pc-meus-dados]"); }); }
    if (b.hasAttribute("data-pc-retirar")) {
      return confirmar(t("Retirar o consentimento?"), t("O registro fica com a data. Para voltar a usar tudo, aceite os termos de novo."), t("Sim, retirar")).then(function (sim) {
        if (!sim) return; pedir("/api/conta/consentimento", { aceito: false }).then(function (j) { if (j.ok && op.instancia) op.instancia.consentimento_pendente = true; est.consMsg = j.ok ? { texto: t("Consentimento retirado.") } : { erro: true, texto: erroDe(j) }; pintar("minha", "[data-pc-retirar]"); if (j.ok) { avisar("consentimento", { aceito: false }); faixaConsentimento(op.instancia && op.instancia.termos_versao); } });
      });
    }
    if (b.hasAttribute("data-pc-ler-termos")) return lerTermos();
    if (b.hasAttribute("data-pc-convites-atualizar")) { est.convites = null; est.convErro = ""; pintar("convites", "[data-pc-convites-atualizar]"); return carregarConvites(); }
    if ((id = b.getAttribute("data-pc-revogar-convite"))) { b.disabled = true; return pedir("/api/convites/" + encodeURIComponent(id) + "/revogar", {}).then(function (j) { est.convMsg = j.ok ? { texto: t("Convite revogado.") } : { erro: true, texto: erroDe(j) }; carregarConvites(); pintar("convites", "[data-pc-convites-atualizar]"); }); }
    if (b.hasAttribute("data-pc-chaves-atualizar")) { est.chaves = null; est.chaveErro = ""; pintar("chaves", "[data-pc-chaves-atualizar]"); return carregarChaves(); }
    if (b.hasAttribute("data-pc-chave-ok")) { est.chaveNova = null; return pintar("chaves", "#pc-ch-rot"); }
    if ((id = b.getAttribute("data-pc-revogar-chave"))) {
      return confirmar(t("Revogar esta chave?"), t("O aparelho que usa esta chave deixa de conseguir mandar dados na hora."), t("Sim, revogar")).then(function (sim) {
        if (!sim) return; pedir("/api/dispositivos/chaves/" + encodeURIComponent(id) + "/revogar", {}).then(function (j) { est.chaveMsg = j.ok ? { texto: t("Chave revogada.") } : { erro: true, texto: erroDe(j) }; carregarChaves(); pintar("chaves", "[data-pc-chaves-atualizar]"); });
      });
    }
  }
  function ligar(raiz) {
    var r = typeof raiz === "string" ? document.querySelector(raiz) : (raiz || document.body); if (!r) return;
    estilo();
    if (!r._pcLigado) { r._pcLigado = true; r.addEventListener("submit", aoEnviar); r.addEventListener("click", aoClicar); }
    if (r.querySelector("[data-pc-tela='convites']")) carregarConvites();
    if (r.querySelector("[data-pc-tela='chaves']")) carregarChaves();
  }

  /* ══ aparência (.pc-*) · cores só de docs/PALETA.md ══ */
  function estilo() {
    if (document.getElementById("pc-estilo") || !document.head) return;
    var s = document.createElement("style"); s.id = "pc-estilo";
    s.textContent = [
      ".pc{--pc-sup:#FFFFFF;--pc-tinta:#1B1F23;--pc-fraca:#4A4F44;--pc-marca:#1A4D2E;--pc-linha:#D9D3C2;--pc-campo:#8A8270;--pc-ok-f:#DCEBD8;--pc-ok-t:#1F4A1C;--pc-at-f:#F6EAD0;--pc-at-t:#5C3F00;--pc-al-f:#F5E2D7;--pc-al-t:#7A2214;--pc-perigo:#A63A28;--pc-fundo:#F4F1EA;color:var(--pc-tinta)}",
      "html[data-tema=escuro] .pc{--pc-sup:#0F4535;--pc-tinta:#F4F1EA;--pc-fraca:#C3D0BD;--pc-marca:#D9A58C;--pc-linha:#2F5E4E;--pc-campo:#8A9182;--pc-ok-f:#1F4A1C;--pc-ok-t:#DCEBD8;--pc-at-f:#5C3F00;--pc-at-t:#E5D5AE;--pc-al-f:#5C2B2E;--pc-al-t:#FF8A80;--pc-perigo:#FF8A80;--pc-fundo:#0B3D2E}",
      ".pc-tela{display:grid;gap:14px;max-width:880px}",
      ".pc-cartao{background:var(--pc-sup);border:1px solid var(--pc-linha);border-radius:12px;padding:14px 16px;min-width:0}",
      ".pc-h{font:600 1.15em/1.3 'Josefin Sans','Century Gothic','Segoe UI',sans-serif;color:var(--pc-marca);margin:0 0 8px}",
      ".pc-h3{font-size:1em;color:var(--pc-marca);margin:12px 0 6px}",
      ".pc p{margin:6px 0}.pc ul{margin:6px 0;padding-left:20px}",
      ".pc-campo{display:grid;gap:3px;margin:8px 0}.pc-campo label{font-weight:600}",
      ".pc-aj{font-size:13.5px;color:var(--pc-fraca)}",
      ".pc-c{font:inherit;min-height:44px;border:1px solid var(--pc-campo);border-radius:8px;background:var(--pc-sup);color:var(--pc-tinta);padding:6px 10px;width:100%;box-sizing:border-box;max-width:100%}",
      "textarea.pc-c{min-height:72px;resize:vertical;word-break:break-all}",
      ".pc-mono,.pc code{font-family:ui-monospace,Consolas,'Courier New',monospace}",
      ".pc-grade{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:4px 14px}",
      ".pc-barra{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:8px 0}",
      ".pc-b{font:inherit;font-weight:600;min-height:44px;min-width:44px;padding:0 16px;border-radius:8px;border:1px solid var(--pc-marca);background:var(--pc-sup);color:var(--pc-marca);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;text-decoration:none;box-sizing:border-box}",
      ".pc-b.pc-p{background:#C2410C;border-color:#C2410C;color:#FFFFFF}",
      ".pc-b.pc-perigo{border-color:var(--pc-perigo);color:var(--pc-perigo)}",
      ".pc-b.pc-p.pc-perigo{background:var(--pc-perigo);color:var(--pc-sup)}",
      ".pc-b.pc-pq{min-height:44px;padding:0 12px;font-size:14px}",
      ".pc-b[disabled]{opacity:.6;cursor:wait}",
      ".pc :focus-visible,.pc-fundo :focus-visible{outline:3px solid var(--pc-marca);outline-offset:2px}",
      ".pc-msg{min-height:1.4em;font-weight:600;margin:6px 0}.pc-msg.pc-erro{color:var(--pc-al-t)}.pc-msg.pc-ok{color:var(--pc-ok-t)}",
      ".pc-selo{display:inline-block;padding:4px 10px;border-radius:8px;background:var(--pc-fundo);border:1px solid var(--pc-linha);font-weight:600}",
      ".pc-selo.pc-ok,.pc-etq.pc-ok{background:var(--pc-ok-f);color:var(--pc-ok-t);border-color:var(--pc-ok-f)}",
      ".pc-selo.pc-atencao,.pc-etq.pc-atencao{background:var(--pc-at-f);color:var(--pc-at-t);border-color:var(--pc-at-f)}",
      ".pc-etq{display:inline-block;font-size:13px;font-weight:700;padding:2px 8px;border-radius:6px;background:var(--pc-fundo);border:1px solid var(--pc-linha)}",
      ".pc-chave{display:inline-block;font-size:1.15em;letter-spacing:.06em;padding:6px 10px;border-radius:8px;background:var(--pc-fundo);border:1px solid var(--pc-linha);word-break:break-all}",
      ".pc-codigos{list-style:none;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:6px}",
      ".pc-codigos code{display:block;padding:6px 8px;border-radius:6px;background:var(--pc-fundo);border:1px solid var(--pc-linha);text-align:center}",
      ".pc-destaque{border:2px solid var(--pc-marca);border-radius:10px;padding:10px 12px;margin:8px 0}",
      ".pc-chk{display:flex;gap:8px;align-items:flex-start;min-height:44px;padding-top:10px}.pc-chk input{width:22px;height:22px;margin:0;flex:none}",
      ".pc-rolar-x{overflow-x:auto;max-width:100%;position:relative}",
      ".pc-tab{border-collapse:collapse;width:100%;font-size:14.5px}.pc-tab th,.pc-tab td{text-align:left;padding:6px 8px;border-top:1px solid var(--pc-linha);vertical-align:middle}.pc-tab thead th{font-size:13px;color:var(--pc-fraca);border-top:0}",
      ".pc-tab th[scope=row]{font-weight:600;word-break:break-word}",
      ".pc-so-leitor{position:absolute;width:1px;height:1px;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}",
      ".pc-fundo{position:fixed;inset:0;z-index:2147483000;background:rgba(20,24,15,.55);display:flex;align-items:center;justify-content:center;padding:16px;box-sizing:border-box}",
      ".pc-janela{background:var(--pc-sup);color:var(--pc-tinta);border-radius:12px;padding:18px 20px;width:min(520px,100%);max-height:calc(100vh - 32px);overflow:auto;box-sizing:border-box;font:16px/1.5 system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;box-shadow:0 8px 30px rgba(20,24,15,.35)}",
      ".pc-rolar{max-height:50vh;overflow:auto;border:1px solid var(--pc-linha);border-radius:8px;padding:8px 12px}",
      ".pc-faixas-fixas{position:fixed;left:50%;transform:translateX(-50%);bottom:16px;z-index:2147482900;width:min(92vw,560px);display:grid;gap:8px}",
      ".pc-faixa{position:relative;background:var(--pc-at-f);color:var(--pc-at-t);border-left:4px solid var(--pc-at-t);border-radius:10px;padding:10px 52px 10px 14px;font:15px/1.45 system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;box-shadow:0 4px 18px rgba(20,24,15,.2)}",
      ".pc-faixa .pc-b{background:var(--pc-sup);color:var(--pc-marca)}.pc-faixa .pc-b.pc-p{background:#C2410C;border-color:#C2410C;color:#FFFFFF}",
      ".pc-faixa .pc-x{position:absolute;top:6px;right:6px;padding:0;width:44px;font-size:20px}",
      "@media (max-width:480px){.pc-cartao{padding:12px}.pc-janela{padding:14px}}"
    ].join("\n");
    document.head.appendChild(s);
  }

  /* ══ início ══ */
  function iniciar(o) {
    o = o || {};
    if (o.idioma) op.idioma = o.idioma;
    if (o.aoMudar) op.aoMudar = o.aoMudar;
    if (o.lugarAvisos) op.lugarAvisos = o.lugarAvisos;
    if (o.termosUrl) op.termosUrl = String(o.termosUrl);
    if (o.papel) op.papel = o.papel;
    if (o.instancia && typeof o.instancia === "object") { op.instancia = o.instancia; guardarCsrf(o.instancia); }
    instalar();
    var pronto = function () {
      estilo();
      if (op.instancia && op.instancia.consentimento_pendente) faixaConsentimento(op.instancia.termos_versao);
      if (op.instancia && op.instancia.email_confirmado === false) faixaEmail();
    };
    if (!op.instancia && servidor() && !iniciado) {
      renovarCsrf().then(function () { avisar("instancia", op.instancia); if (document.body) pronto(); else document.addEventListener("DOMContentLoaded", pronto); }, function () {});
    } else if (document.body) pronto(); else document.addEventListener("DOMContentLoaded", pronto);
    iniciado = true;
    return g.PhysisConta;
  }

  g.PhysisConta = {
    versao: "1", I18N: I18N, t: t, iniciar: iniciar, ligar: ligar,
    telaMinhaConta: function () { estilo(); return embrulho("minha"); },
    telaConvites: function () { estilo(); return embrulho("convites"); },
    telaChaves: function () { estilo(); return embrulho("chaves"); },
    instancia: function () { return op.instancia; },
    reautenticar: pedirReautenticacao
  };
})(window);
