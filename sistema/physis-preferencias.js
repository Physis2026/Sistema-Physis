/* physis-preferencias.js v3 · Preferências de leitura e acessibilidade das telas da Physis
   Barra com 3 controles: [Idioma: Português/English] [Modo de conforto ▾ (inclui o Tema: Claro/Escuro (verde)/Automático)] [Acessibilidade (PcD) ▾].
   Modo de conforto (neurodivergência: autismo, TDAH, dislexia): fundo verde, texto maior, mais espaçamento, menos estímulo,
   foco reforçado, fonte para dislexia, régua de leitura, leitura simplificada, lembrar onde parei.
   Acessibilidade (PcD): cegueira e baixa visão (leitores de tela, ouvir esta tela, alto contraste, zoom, atalhos),
   surdez (alertas visuais, Libras, legendas), fala (comunicação alternativa · CAA), mobilidade (teclado, comandos de voz).

   ORIGINAL ÚNICO: sistema/physis-preferencias.js (desde a v3 a antiga barra px-preferencias da plataforma, da Gestão e do
   SCADA é esta mesma, pela porta PxPref, no fim do arquivo). As telas são arquivos únicos, então cada uma leva uma CÓPIA IGUAL
   dentro do bloco script de id "physis-preferencias" (o arquivo inteiro, sem mudar nada). Quem copia é ferramentas/sincronizar.py
   (BLOCOS): physis-hub/web/painel.html, sistema/gestao-interna-physis.html, sistema/physis-scada-demo.html,
   physis-hub/web/consultoria.html, sistema/SustainKit_Definitivo.html, modulos/planejador/planejador-physis.html (e as demos
   geradas delas). O teste physis-hub/tests/test_preferencias.py confere que as cópias são iguais a este arquivo.

   Uso, uma vez por página, depois do conteúdo:
     PhysisPreferencias.iniciar({
       chave: "physis-pref",              // guardado no navegador; a mesma chave em todas as telas = a escolha acompanha a pessoa
       dicionario: { "Texto em português": "English text" },
       padroes: [[/^Pedido (\S+) recebido\.$/, "Request $1 received."]],   // textos montados na hora
       fragmentos: { "Captação de": "Harvesting of" },  // pedaços de textos montados com números ("Captação de " + n + " L")
       excecoes: ["Physis Engineering"],  // nomes próprios: iguais nas duas línguas
       ondeColocar: "#pp-lugar",          // elemento ou seletor onde a barra aparece (sem ele: início do <body>)
       variante: "sobre-verde",           // opcional: barra sobre fundo verde-escuro
       escalaPorZoom: true,               // texto maior por zoom (telas em px); false = a página usa var(--pp-escala)
       conteudo: "#conteudo",             // Alt+1, "Pular para o conteúdo" e "Ouvir esta tela"
       menu: "nav",                       // Alt+2
       busca: "[role=tablist]",           // Alt+3
       contato: "#f-desc",                // campo onde a CAA escreve quando nenhum campo está em uso
       relatar: "#contato",               // "Relatar barreira" sem abrirJuridico(): link do contato
       lembrar: { salvar: function () { return {}; }, restaurar: function (o) {} },  // opcional: aba aberta etc.
       esconderEmQuadro: true,            // aberta num quadro (iframe) da plataforma ou com html[data-em-quadro]: sem barra própria, segue a escolha de lá
       idiomaExterno: { atual, definir }, // tela que se traduz sozinha (o módulo só pede a troca; não traduz o DOM)
       suporte: function (frase) {},      // CAA sem campo em uso: leva a frase ao suporte da tela
       tela: "nome",                      // chave do "lembrar onde parei" (padrão: o endereço)
       aoMudar: function (estado) {}      // chamado depois de cada mudança
     });

   No <html>: data-tema="claro|escuro" (o que vale), data-tema-escolha="claro|escuro|auto", lang, a variável --pp-escala
   (1, 1.15 ou 1.3) e as classes physis-conforto, a11y-verde, a11y-texto-1 / a11y-texto-2, a11y-espaco, a11y-calma,
   a11y-foco, a11y-dislexia, a11y-regua, a11y-simples, a11y-contraste.
   Cada página define as próprias cores em html[data-tema="escuro"] e html.a11y-verde (os nomes das variáveis mudam de
   uma tela para outra) e o que some em html.a11y-simples (ou marca elementos com data-pp-secundario).
   Sem recurso de fora, sem avaliação de código: funciona com a Content-Security-Policy do servidor e sem internet.
   Comandos de voz usam o reconhecimento do navegador (no Chrome o áudio vai aos servidores do Google): começam desligados.

   Inglês: troca os textos (nós de texto e aria-label, title, placeholder, alt, label e value de botões) pelo par do
   dicionário, guarda o original para voltar ao português e acompanha o conteúdo novo (MutationObserver).
   O que não tem par fica em português e entra em PhysisPreferencias.faltando().
   Elementos com data-pp-manter (ou translate="no") não são traduzidos.

   Cores (versão de teste, 20/11/2026): guia de identidade Physis, PALETA.md "Tipos de tela". Claro = tipo B (creme, carvão,
   floresta #1A4D2E em contornos e links, botão principal #C2410C com texto branco); escuro = tipo A (verde profundo #0B3D2E,
   cartões #0F4535, linhas #2F5E4E, texto #F4F1EA, destaque pequeno #D9A58C). Foco e régua em terracota, nunca em azul. */
(function (global) {
  "use strict";
  var doc = global.document;
  if (!doc || global.PhysisPreferencias) return;

  var PADRAO = { v: 2, idioma: "pt", tema: "auto", conforto: false, verde: false, texto: 0, espaco: false, calma: false, foco: false,
    dislexia: false, regua: false, simples: false, lembrar: false, contraste: false, libras: false, voz: false, aviso: 4 };
  var BOOL = ["conforto", "verde", "espaco", "calma", "foco", "dislexia", "regua", "simples", "lembrar", "contraste", "libras", "voz"];
  var CLASSES = ["verde", "espaco", "calma", "foco", "dislexia", "regua", "simples", "contraste"];
  var ATRIBUTOS = ["aria-label", "title", "placeholder", "alt", "label", "aria-description", "aria-roledescription"];
  var IGNORAR = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, NOSCRIPT: 1, TEMPLATE: 1, CODE: 1, PRE: 1 };
  var ESCALAS = [1, 1.15, 1.3];
  var FRASES = ["ajuda", "entendi", "pessoa", "sim", "nao", "repetir"];

  /* textos da própria barra, nas duas línguas (a página não precisa traduzir) */
  var UI = {
    pt: { grupo: "Preferências de leitura e acessibilidade", idioma: "Idioma", tema: "Tema", claro: "Claro", escuro: "Escuro (verde)", auto: "Automático",
      conforto: "Modo de conforto", ligado: "ligado", a11y: "Acessibilidade (PcD)", fechar: "Fechar", padrao: "Voltar ao padrão",
      confT: "Modo de conforto", confD: "Para autismo, TDAH, dislexia e para quem se cansa com telas cheias. Vale para todas as telas da Physis e fica guardado neste aparelho.",
      confLiga: "Ligar o modo de conforto", confLigaD: "Tema escuro (verde), menos estímulo e mais espaçamento de uma vez.",
      verde: "Fundo verde", verdeD: "Cor de fundo suave, que cansa menos a vista.", texto: "Texto maior", t0: "Normal", t1: "Maior", t2: "Muito maior", aviso: "Tempo dos avisos que somem sozinhos", a4: "4 segundos", a8: "8 segundos", a15: "15 segundos",
      espaco: "Mais espaçamento", espacoD: "Mais espaço entre linhas, letras e palavras.",
      calma: "Menos estímulo", calmaD: "Sem animação nem transição, nada piscando, cores mais calmas, nada toca sozinho e menos janelas que se abrem.",
      foco: "Foco reforçado", focoD: "Contorno grosso no item em que você está.", dislexia: "Fonte para dislexia", dislexiaD: "Letras mais fáceis de distinguir (Atkinson Hyperlegible ou Lexend, já no aparelho).",
      regua: "Régua de leitura", reguaD: "Uma faixa acompanha o ponteiro ou o item em foco, para não perder a linha.",
      simples: "Modo leitura simplificada", simplesD: "Esconde enfeites e textos secundários e põe tudo numa coluna só.",
      lembrar: "Lembrar onde parei", lembrarD: "Ao voltar, a tela abre no mesmo ponto e na mesma aba.",
      a11yT: "Acessibilidade (PcD)", a11yD: "Recursos para pessoas com deficiência. Vale para todas as telas da Physis e fica guardado neste aparelho.",
      cegT: "Cegueira e baixa visão", cegD: "Funciona com leitores de tela (NVDA, JAWS, VoiceOver, TalkBack): link para pular ao conteúdo, regiões nomeadas, avisos lidos em voz alta e nome em cada controle.",
      ouvir: "Ouvir esta tela", pausar: "Pausar", continuar: "Continuar", parar: "Parar", ouvirD: "Lê o conteúdo principal, ou o trecho que você selecionar, com as vozes do próprio aparelho.",
      semVoz: "Este navegador não tem leitura em voz alta.", contraste: "Alto contraste", contrasteD: "Texto e bordas mais fortes.",
      zoom: "Zoom até 200% sem quebrar a tela: use Ctrl e + (no Mac, Cmd e +).", atalhos: "Atalhos de teclado",
      at1: "Alt+1: conteúdo", at2: "Alt+2: menu", at3: "Alt+3: busca ou abas", at0: "Alt+0: este painel", atEsc: "Esc: fecha o painel",
      surT: "Surdez", surD: "Todo aviso aparece na tela; nenhum depende só de som. Vídeos e áudios precisam de legenda.",
      libras: "Libras (VLibras)", librasD: "Começa desligado. O VLibras é aberto e do governo, mas carrega programas de fora; aqui ele será instalado no servidor da Physis.",
      librasOn: "O VLibras ainda não está instalado neste servidor. Enquanto isso, todo conteúdo tem texto escrito; peça à Physis a versão em Libras de qualquer tela pelo Relatar barreira.",
      falT: "Fala", falD: "Nenhuma função precisa de voz. Use as frases prontas: elas vão para o campo de texto em uso ou para o formulário de contato.",
      caa: "Comunicação alternativa (CAA)", ajuda: "Preciso de ajuda", entendi: "Não entendi", pessoa: "Quero falar com uma pessoa", sim: "Sim", nao: "Não", repetir: "Pode repetir de outro jeito?",
      caaMostra: "Mostre esta frase:", caaFoi: "Frase escrita no campo: ",
      mobT: "Mobilidade", mobD: "Tudo funciona pelo teclado, os botões têm pelo menos 44 px e não há tempo limite.",
      voz: "Comandos de voz", vozD: "Começa desligado. Atenção à privacidade (LGPD): no Chrome e no Edge o áudio é enviado aos servidores do Google ou da Microsoft para ser entendido. Comandos: ir para conteúdo, próximo, voltar, ler tela, aumentar texto, diminuir texto, parar.",
      semRec: "Este navegador não reconhece voz.", vozOuve: "Ouvindo comandos de voz.", vozErro: "Os comandos de voz pararam: ",
      relatar: "Relatar barreira", decT: "Declaração de acessibilidade",
      relatarD: "Descreva a barreira: o que tentou fazer, em que tela e o que aconteceu. Copie o relato e envie pelo canal de suporte da Physis.",
      relatarCampo: "O que aconteceu", copiar: "Copiar relato", copiado: "Relato copiado.", caaSup: "Frase levada ao suporte: ",
      decD: "Estas telas seguem a Lei Brasileira de Inclusão (Lei 13.146/2015), o eMAG e as diretrizes de acessibilidade digital do gov.br, a WCAG 2.2 nível AA e a ABNT NBR 17225.",
      pular: "Pular para o conteúdo", ok: "Preferência aplicada.", aEn: "English on. Texts not yet translated stay in Portuguese.", aPt: "Português ligado.",
      aEsc: "Tema escuro ligado.", aClaro: "Tema claro ligado.", aAuto: "Tema automático: segue o aparelho.",
      aConfOn: "Modo de conforto ligado: tema escuro (verde), menos estímulo e mais espaçamento.", aConfOff: "Modo de conforto desligado.", aPadrao: "Preferências de volta ao padrão.",
      lido: "Lendo a tela.", lidoFim: "Leitura parada." },
    en: { grupo: "Reading and accessibility preferences", idioma: "Language", tema: "Theme", claro: "Light", escuro: "Dark (green)", auto: "Automatic",
      conforto: "Comfort mode", ligado: "on", a11y: "Accessibility (disability)", fechar: "Close", padrao: "Back to default",
      confT: "Comfort mode", confD: "For autism, ADHD, dyslexia and anyone tired by busy screens. Applies to every Physis screen and is saved on this device.",
      confLiga: "Turn comfort mode on", confLigaD: "Green background, less stimulation and more spacing at once.",
      verde: "Green background", verdeD: "A soft background colour that is easier on the eyes.", texto: "Larger text", t0: "Normal", t1: "Larger", t2: "Much larger", aviso: "How long notices stay on screen", a4: "4 seconds", a8: "8 seconds", a15: "15 seconds",
      espaco: "More spacing", espacoD: "More space between lines, letters and words.",
      calma: "Less stimulation", calmaD: "No animation or transitions, nothing blinking, calmer colours, nothing plays by itself and fewer pop-ups.",
      foco: "Stronger focus", focoD: "Thick outline on the item you are on.", dislexia: "Dyslexia-friendly font", dislexiaD: "Letters that are easier to tell apart (Atkinson Hyperlegible or Lexend, already on the device).",
      regua: "Reading ruler", reguaD: "A band follows the pointer or the focused item, so you do not lose the line.",
      simples: "Simplified reading mode", simplesD: "Hides decorations and secondary text and puts everything in a single column.",
      lembrar: "Remember where I stopped", lembrarD: "When you come back, the screen opens at the same point and tab.",
      a11yT: "Accessibility (disability)", a11yD: "Features for people with disabilities. Applies to every Physis screen and is saved on this device.",
      cegT: "Blindness and low vision", cegD: "Works with screen readers (NVDA, JAWS, VoiceOver, TalkBack): skip link, named regions, alerts read aloud and a name on every control.",
      ouvir: "Listen to this screen", pausar: "Pause", continuar: "Resume", parar: "Stop", ouvirD: "Reads the main content, or the text you select, with the device's own voices.",
      semVoz: "This browser cannot read aloud.", contraste: "High contrast", contrasteD: "Stronger text and borders.",
      zoom: "Zoom up to 200% without breaking the screen: use Ctrl and + (on a Mac, Cmd and +).", atalhos: "Keyboard shortcuts",
      at1: "Alt+1: content", at2: "Alt+2: menu", at3: "Alt+3: search or tabs", at0: "Alt+0: this panel", atEsc: "Esc: closes the panel",
      surT: "Deafness", surD: "Every alert is shown on screen; none relies on sound alone. Videos and audio need captions.",
      libras: "Libras sign language (VLibras)", librasD: "Off by default. VLibras is open and government-made, but loads outside programs; here it will be installed on the Physis server.",
      librasOn: "VLibras is not installed on this server yet. Meanwhile, all content has written text; ask Physis for a Libras version of any screen through Report a barrier.",
      falT: "Speech", falD: "No function needs your voice. Use the ready phrases: they go into the text field in use or into the contact form.",
      caa: "Augmentative and alternative communication (AAC)", ajuda: "I need help", entendi: "I did not understand", pessoa: "I want to talk to a person", sim: "Yes", nao: "No", repetir: "Can you say it another way?",
      caaMostra: "Show this phrase:", caaFoi: "Phrase written in the field: ",
      mobT: "Mobility", mobD: "Everything works with the keyboard, buttons are at least 44 px and there are no time limits.",
      voz: "Voice commands", vozD: "Off by default. Privacy notice (LGPD): in Chrome and Edge the audio is sent to Google or Microsoft servers to be understood. Commands: go to content, next, back, read screen, bigger text, smaller text, stop.",
      semRec: "This browser does not recognise speech.", vozOuve: "Listening for voice commands.", vozErro: "Voice commands stopped: ",
      relatar: "Report a barrier", decT: "Accessibility statement",
      relatarD: "Describe the barrier: what you tried to do, on which screen and what happened. Copy the report and send it through the Physis support channel.",
      relatarCampo: "What happened", copiar: "Copy report", copiado: "Report copied.", caaSup: "Phrase taken to support: ",
      decD: "These screens follow the Brazilian Inclusion Law (Law 13.146/2015), eMAG and the gov.br digital accessibility guidelines, WCAG 2.2 level AA and ABNT NBR 17225.",
      pular: "Skip to content", ok: "Preference applied.", aEn: "English on. Texts not yet translated stay in Portuguese.", aPt: "Português ligado.",
      aEsc: "Dark theme on.", aClaro: "Light theme on.", aAuto: "Automatic theme: follows the device.",
      aConfOn: "Comfort mode on: green background, less stimulation and more spacing.", aConfOff: "Comfort mode off.", aPadrao: "Preferences back to default.",
      lido: "Reading the screen.", lidoFim: "Reading stopped." }
  };
  /* frases da CAA nas duas línguas: entram no dicionário para a tela também traduzir o que já foi escrito */

  var CSS = [
    /* barra */
    ".pp-barra{--pp-f:#FFFFFF;--pp-t:#1B1F23;--pp-l:#8A8270;--pp-a:#1A4D2E;--pp-at:#FFFFFF;position:relative;display:flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:14px;line-height:1.3;font-family:inherit;color:var(--pp-t)}",
    "html[data-tema=escuro] .pp-barra{--pp-f:#0F4535;--pp-t:#F4F1EA;--pp-l:#8A9182;--pp-a:#D9A58C;--pp-at:#0F4535}",
    ".pp-barra.pp-sobre-verde{--pp-f:transparent;--pp-t:#F4F1EA;--pp-l:#C3D0BD;--pp-a:#D9A58C;--pp-at:#0B3D2E}",
    ".pp-barra .pp-b,.pp-barra select{font:inherit;font-size:13px;font-weight:600;min-height:36px;min-width:36px;padding:0 10px;border-radius:8px;border:1px solid var(--pp-l);background:var(--pp-f);color:var(--pp-t);cursor:pointer;margin:0;line-height:1.2;width:auto}",
    ".pp-barra select option{background:#FFFFFF;color:#1B1F23}",
    ".pp-barra .pp-cx{display:inline-flex;align-items:center;gap:4px;font-size:13px;font-weight:600;color:var(--pp-t)}",
    ".pp-barra [hidden]{display:none!important}",
    ".pp-barra .pp-b[aria-expanded=true]{background:var(--pp-a);border-color:var(--pp-a);color:var(--pp-at)}",
    ".pp-barra .pp-b .pp-seta{display:inline-block;margin-left:4px;font-size:.8em}",
    ".pp-barra .pp-b .pp-on{font-weight:400}",
    ".pp-barra .pp-b:focus-visible,.pp-barra select:focus-visible,.pp-painel :focus-visible{outline:3px solid var(--pp-t);outline-offset:2px}",
    ".pp-painel{position:absolute;right:0;top:calc(100% + 6px);z-index:1000;width:400px;max-width:calc(100vw - 32px);max-height:calc(100vh - 110px);overflow:auto;background:#FFFFFF;color:#1B1F23;border:1px solid #8A8270;border-radius:12px;padding:14px 16px;box-shadow:0 8px 28px rgba(28,43,33,.22);text-align:left;font-size:15px;line-height:1.45;font-weight:400;letter-spacing:normal}",
    "html[data-tema=escuro] .pp-painel{background:#0F4535;color:#F4F1EA;border-color:#8A9182}",
    ".pp-painel[hidden],.pp-painel [hidden]{display:none!important}",
    ".pp-painel h2{font:700 17px/1.3 inherit;margin:0 0 2px;color:inherit;font-family:inherit}",
    ".pp-painel h3{font:700 15px/1.3 inherit;margin:14px 0 4px;color:inherit;font-family:inherit;border-top:1px solid #D9D3C2;padding-top:10px}",
    "html[data-tema=escuro] .pp-painel h3{border-color:#2F5E4E}",
    ".pp-painel p,.pp-painel .pp-d{display:block;font-size:13px;color:#4A4F44;margin:0 0 6px;font-weight:400}",
    "html[data-tema=escuro] .pp-painel p,html[data-tema=escuro] .pp-painel .pp-d{color:#C3D0BD}",
    ".pp-painel fieldset{border:1px solid #D9D3C2;border-radius:8px;margin:6px 0;padding:4px 10px 6px}",
    "html[data-tema=escuro] .pp-painel fieldset{border-color:#2F5E4E}",
    ".pp-painel legend{font-weight:700;padding:0 4px;font-size:14px}",
    ".pp-painel label{display:flex;gap:8px;align-items:flex-start;min-height:44px;padding:6px 0;cursor:pointer;font-weight:600;color:inherit;font-size:14px}",
    ".pp-painel fieldset label{display:inline-flex;min-height:36px;margin-right:12px}",
    ".pp-painel label .pp-d{font-weight:400;margin:2px 0 0}",
    ".pp-painel input{width:20px;height:20px;margin:1px 0 0;flex:none;accent-color:#1A4D2E}",
    "html[data-tema=escuro] .pp-painel input{accent-color:#D9A58C}",
    ".pp-painel ul{margin:0 0 6px;padding-left:18px;font-size:13px}",
    ".pp-painel .pp-acoes{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0}",
    ".pp-painel button{font:inherit;font-size:14px;font-weight:600;min-height:44px;padding:0 14px;border-radius:8px;border:1px solid #1A4D2E;background:#FFFFFF;color:#1A4D2E;cursor:pointer}",
    ".pp-painel button.pp-prim{background:#C2410C;border-color:#C2410C;color:#FFFFFF}",
    "html[data-tema=escuro] .pp-painel button{background:#0F4535;color:#F4F1EA;border-color:#D9A58C}",
    "html[data-tema=escuro] .pp-painel button.pp-prim{background:#C2410C;border-color:#C2410C;color:#FFFFFF}",
    ".pp-painel .pp-caa{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:6px;margin:6px 0}",
    ".pp-painel .pp-caa button{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:8px 6px;min-height:76px;font-size:13px;line-height:1.2;text-align:center}",
    ".pp-painel .pp-caa svg{width:28px;height:28px;flex:none}",
    ".pp-painel .pp-cartao{font-size:22px;font-weight:700;border:2px solid currentColor;border-radius:10px;padding:10px 12px;margin:6px 0}",
    ".pp-painel .pp-aviso{background:#F6EAD0;color:#5C3F00;border-radius:8px;padding:8px 10px;font-size:13px}",
    "html[data-tema=escuro] .pp-painel .pp-aviso{background:#33372E;color:#E5D5AE}",
    ".pp-so-leitor{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}",
    ".pp-pular{position:absolute;left:-9999px;top:8px;z-index:1001;background:#0B3D2E;color:#FFFFFF;padding:10px 14px;border-radius:8px;font-weight:600}",
    ".pp-pular:focus{left:8px}",
    "@media (max-width:560px){.pp-painel{position:fixed;left:16px;right:16px;top:auto;bottom:16px;width:auto;max-width:none;max-height:78vh}}",
    /* régua de leitura */
    ".pp-regua{position:fixed;left:0;right:0;height:2.4em;margin-top:-1.2em;pointer-events:none;z-index:999;border-top:2px solid #BB6B4A;border-bottom:2px solid #BB6B4A;background:rgba(255,246,223,.28);display:none}",
    "html.a11y-regua .pp-regua{display:block}",
    "html[data-tema=escuro] .pp-regua{border-color:#D9A58C;background:rgba(255,246,223,.12)}",
    /* preferências que valem para qualquer página */
    "html.a11y-texto-1.pp-zoom body{zoom:1.15}html.a11y-texto-2.pp-zoom body{zoom:1.3}",
    "html.a11y-espaco body{letter-spacing:.012em;word-spacing:.06em}",
    "html.a11y-espaco :is(p,li,dd,dt,label,td,th,figcaption,blockquote,summary,legend){line-height:1.8}",
    "html.a11y-contraste :is(input,select,textarea,button){border-width:2px}",
    "html.a11y-contraste a{text-decoration:underline;text-underline-offset:2px}",
    "html.a11y-calma *,html.a11y-calma *::before,html.a11y-calma *::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}",
    "html.a11y-calma{scroll-behavior:auto!important}html.a11y-calma :is(marquee,blink){display:none!important}",
    "html.a11y-simples [data-pp-secundario]{display:none!important}",
    "html.a11y-foco :focus-visible,html.a11y-foco :focus{outline:4px solid #BB6B4A!important;outline-offset:3px!important;box-shadow:0 0 0 7px #FFF6DF!important}",
    "html.a11y-foco[data-tema=escuro] :focus-visible,html.a11y-foco[data-tema=escuro] :focus{outline-color:#D9A58C!important;box-shadow:0 0 0 7px #0B3D2E!important}",
    "html.a11y-foco :focus:not(:focus-visible){outline:none!important;box-shadow:none!important}",
    "html.a11y-dislexia :is(body,button,input,select,textarea){font-family:\"Atkinson Hyperlegible\",Lexend,Verdana,Tahoma,sans-serif!important}",
    "html[data-tema=escuro]{color-scheme:dark}html[data-tema=claro]{color-scheme:light}"
  ].join("\n");

  var P = { op: null, estado: null, idiomaOriginal: "pt-BR", orig: new WeakMap(), origAttr: new WeakMap(), faltam: {}, obs: null,
    pausado: false, ui: {}, campo: null, rec: null, falando: false };

  function ler(chave) { try { return global.localStorage.getItem(chave); } catch (e) { return null; } }
  function gravar(chave, v) { try { global.localStorage.setItem(chave, v); } catch (e) {} }
  function tem(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
  function copia(o) { var r = {}; for (var k in o) if (tem(o, k)) r[k] = o[k]; return r; }
  function limpar(o) {
    var e = copia(PADRAO);
    if (o && typeof o === "object") {
      for (var x in o) if (tem(o, x) && !tem(PADRAO, x) && x !== "legivel" && x !== "fundoVerde") e[x] = o[x];   /* guarda o que outras telas gravam */
      if (o.fundoVerde) e.tema = "escuro";
      if (o.idioma === "en" || o.idioma === "pt") e.idioma = o.idioma;
      if (o.tema === "claro" || o.tema === "escuro" || o.tema === "auto") e.tema = o.tema;
      var t = parseInt(o.texto, 10); if (t === 0 || t === 1 || t === 2) e.texto = t; else if (o.texto === true) e.texto = 1;
      var av = parseInt(o.aviso, 10); if (av === 4 || av === 8 || av === 15) e.aviso = av;   /* tempo dos avisos (s), lido pelas telas que mostram avisos que somem */
      BOOL.forEach(function (k) { if (k in o) e[k] = !!o[k]; });
      if (o.legivel) e.dislexia = true;            /* nome da v1 */
      if (e.verde) { e.tema = "escuro"; e.verde = false; }   /* 20/11/2026: "fundo verde" e tema escuro viraram uma opção só */
    }
    return e;
  }
  function el(sel) { if (!sel) return null; if (typeof sel !== "string") return sel; try { return doc.querySelector(sel); } catch (e) { return null; } }

  /* lê a escolha guardada; na primeira vez, aproveita as chaves antigas da plataforma (painel.html) */
  function carregar() {
    var o = null;
    try { o = JSON.parse(ler(P.op.chave) || "null"); } catch (e) { o = null; }
    if (o) return limpar(o);
    var e = copia(PADRAO);
    if (ler("physis-idioma") === "en") e.idioma = "en";
    if (ler("physis-conforto") === "1") { e.conforto = true; e.espaco = true; e.calma = true; }
    if (ler("physis-fundo") === "verde") e.tema = "escuro";
    try { var pp = JSON.parse(ler("physis-passaporte") || "null"); if (pp) { e.texto = pp.texto ? 1 : 0; e.espaco = e.espaco || !!pp.espaco; e.contraste = !!pp.contraste; e.calma = e.calma || !!pp.calma; e.foco = !!pp.foco; } } catch (x) {}
    var t = ler("physis-pref-tema"); if (t === "claro" || t === "escuro" || t === "auto") e.tema = t;
    return e;
  }
  function guardar() {
    var e = P.estado;
    gravar(P.op.chave, JSON.stringify(e));
    gravar("physis-pref-tema", e.tema);      /* lido pelo script cedo (pxp-cedo) antes de a tela desenhar */
    /* espelho nas chaves antigas, para telas antigas seguirem a mesma escolha */
    gravar("physis-idioma", e.idioma);
    gravar("physis-conforto", e.conforto ? "1" : "0");
    gravar("physis-fundo", e.verde ? "verde" : "branco");
    var pp = {}; try { pp = JSON.parse(ler("physis-passaporte") || "{}") || {}; } catch (x) { pp = {}; }
    pp.texto = e.texto > 0; pp.espaco = e.espaco; pp.contraste = e.contraste; pp.calma = e.calma; pp.foco = e.foco;
    gravar("physis-passaporte", JSON.stringify(pp));
  }

  function sistemaEscuro() { try { return !!(global.matchMedia && global.matchMedia("(prefers-color-scheme: dark)").matches); } catch (e) { return false; } }
  /* o fundo verde é o escuro esverdeado: as telas o desenham com as cores do tema escuro mais html.a11y-verde */
  function temaEfetivo() { return P.estado.verde ? "escuro" : P.estado.tema === "auto" ? (sistemaEscuro() ? "escuro" : "claro") : P.estado.tema; }
  /* telas com tradução própria (plataforma, Gestão, SCADA): idiomaExterno = { atual(), definir(lingua, pelaPessoa) } */
  function externo() { var i = P.op && P.op.idiomaExterno; return i && typeof i.definir === "function" ? i : null; }
  function idiomaDaTela() { var i = externo(); if (i && i.atual) { try { return i.atual() === "en" ? "en" : "pt"; } catch (x) {} } return P.estado.idioma; }
  function txt(k) { return UI[P.estado && P.estado.idioma === "en" ? "en" : "pt"][k]; }

  /* ---------- aplicar no <html> ---------- */
  function aplicar(anunciar) {
    var r = doc.documentElement, e = P.estado, cl = r.classList;
    r.setAttribute("data-tema", temaEfetivo());
    r.setAttribute("data-tema-escolha", e.tema);
    cl.toggle("physis-conforto", e.conforto);
    cl.toggle("a11y-texto-1", e.texto === 1);
    cl.toggle("a11y-texto-2", e.texto === 2);
    CLASSES.forEach(function (k) { cl.toggle("a11y-" + k, !!e[k]); });
    cl.toggle("pp-zoom", P.op.escalaPorZoom !== false);
    r.style.setProperty("--pp-escala", String(ESCALAS[e.texto]));
    var meta = doc.querySelector('meta[name="theme-color"]'); if (meta) meta.setAttribute("content", "#0B3D2E");   // faixa superior verde profundo nos dois temas (guia de identidade)
    if (P.idiomaAplicado !== e.idioma) { P.idiomaAplicado = e.idioma; definirIdioma(e.idioma); }
    if (e.calma) pararMidias(doc);
    vozLigar(e.voz);
    desenharBarra();
    if (anunciar) dizer(anunciar);
    if (typeof P.op.aoMudar === "function") { try { P.op.aoMudar(estadoPublico()); } catch (x) { if (global.console) console.error(x); } }
  }
  function estadoPublico() { var o = copia(P.estado); o.temaEfetivo = temaEfetivo(); return o; }
  function mudar(patch, anuncio) {
    for (var k in patch) if (tem(patch, k)) P.estado[k] = patch[k];
    P.estado = limpar(P.estado);
    guardar();
    aplicar(anuncio);
  }

  /* ---------- montagem ---------- */
  function criar(tag, attrs, filhos) {
    var e = doc.createElement(tag);
    if (attrs) for (var k in attrs) if (tem(attrs, k) && attrs[k] != null && attrs[k] !== false) e.setAttribute(k, attrs[k] === true ? "" : attrs[k]);
    (filhos || []).forEach(function (f) { if (f != null) e.appendChild(typeof f === "string" ? doc.createTextNode(f) : f); });
    return e;
  }
  /* ícones simples da CAA (traço, sem cor própria: seguem a cor do texto) */
  var ICONES = {
    ajuda: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v6M12 16v1",
    entendi: "M9 9a3 3 0 1 1 4 2.8c-.7.3-1 .9-1 1.6V15M12 18v1M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z",
    pessoa: "M12 4a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7zM5 20c0-4 3.1-6.5 7-6.5s7 2.5 7 6.5",
    sim: "M4 12.5l5 5L20 6.5",
    nao: "M6 6l12 12M18 6L6 18",
    repetir: "M4 12a8 8 0 0 1 14-5.3M20 4v4h-4M20 12a8 8 0 0 1-14 5.3M4 20v-4h4"
  };
  function icone(nome) {
    var ns = "http" + "://www.w3.org/2000/svg", s = doc.createElementNS(ns, "svg"), p = doc.createElementNS(ns, "path");
    s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true"); s.setAttribute("focusable", "false");
    p.setAttribute("d", ICONES[nome]); p.setAttribute("fill", "none"); p.setAttribute("stroke", "currentColor"); p.setAttribute("stroke-width", "2"); p.setAttribute("stroke-linecap", "round"); p.setAttribute("stroke-linejoin", "round");
    s.appendChild(p); return s;
  }

  function montarBarra() {
    var lugar = el(P.op.ondeColocar), u = P.ui;
    u.regua = criar("div", { "class": "pp-regua", "aria-hidden": "true", "data-pp-manter": "" });
    doc.body.appendChild(u.regua);
    /* dentro de um quadro da plataforma (esconderEmQuadro): a barra fica na plataforma; aqui só se aplica a escolha */
    if (P.op.esconderEmQuadro) { var q = doc.documentElement.hasAttribute("data-em-quadro"); try { q = q || global.self !== global.top; } catch (e) { q = true; } if (q) return; }
    var barra = criar("div", { "class": "pp-barra" + (P.op.variante ? " pp-" + P.op.variante : ""), id: "pxp-barra", role: "group", "data-pp-manter": "", translate: "no", "data-physis-preferencias": "barra" });
    u.idiomaRot = criar("label", { "for": "pp-idioma", "class": "pp-cx" });
    u.idioma = criar("select", { id: "pp-idioma" }, [criar("option", { value: "pt", lang: "pt-BR" }, ["Português"]), criar("option", { value: "en", lang: "en" }, ["English"])]);
    u.idiomaRot.appendChild(u.idiomaTxt = criar("span")); u.idiomaRot.appendChild(u.idioma);
    u.temaRot = criar("label", { "for": "pp-tema", "class": "pp-cx" });
    u.tema = criar("select", { id: "pp-tema" }, [criar("option", { value: "claro" }), criar("option", { value: "escuro" }), criar("option", { value: "auto" })]);
    u.temaRot.appendChild(u.temaTxt = criar("span")); u.temaRot.appendChild(u.tema);
    u.conforto = criar("button", { type: "button", "class": "pp-b", id: "pp-conforto", "aria-expanded": "false", "aria-controls": "pp-painel-conforto" });
    u.a11y = criar("button", { type: "button", "class": "pp-b", id: "pp-a11y", "aria-expanded": "false", "aria-controls": "pp-painel-a11y" });
    u.pConf = criar("div", { "class": "pp-painel", id: "pp-painel-conforto", role: "region", "aria-labelledby": "pp-conf-t", hidden: true });
    u.pA11y = criar("div", { "class": "pp-painel", id: "pp-painel-a11y", role: "region", "aria-labelledby": "pp-a11y-t", hidden: true });
    u.anuncio = criar("div", { "class": "pp-so-leitor", role: "status", "aria-live": "polite" });
    /* 20/11/2026 (dona): o Tema fica só dentro do Modo de conforto — a barra tem Idioma, Modo de conforto e Acessibilidade.
       O seletor continua existindo (escondido) para as telas que o leem. */
    u.temaRot.hidden = true;
    [u.idiomaRot, u.temaRot, u.conforto, u.a11y, u.pConf, u.pA11y, u.anuncio].forEach(function (x) { barra.appendChild(x); });
    u.barra = barra;
    if (lugar) lugar.appendChild(barra); else doc.body.insertBefore(barra, doc.body.firstChild);

    u.idioma.addEventListener("change", function () { var en = u.idioma.value === "en"; P.pelaPessoa = true; mudar({ idioma: en ? "en" : "pt" }, en ? UI.en.aEn : UI.pt.aPt); });
    u.tema.addEventListener("change", function () { var v = u.tema.value; mudar({ tema: v }, v === "auto" ? "aAuto" : v === "escuro" ? "aEsc" : "aClaro"); });
    u.conforto.addEventListener("click", function () { abrir(u.pConf, u.conforto, u.pConf.hidden); });
    u.a11y.addEventListener("click", function () { abrir(u.pA11y, u.a11y, u.pA11y.hidden); });
    barra.addEventListener("keydown", function (ev) {
      if (ev.key !== "Escape") return;
      if (!u.pConf.hidden) { abrir(u.pConf, u.conforto, false); u.conforto.focus(); }
      else if (!u.pA11y.hidden) { abrir(u.pA11y, u.a11y, false); u.a11y.focus(); }
    });
    doc.addEventListener("click", function (ev) {
      if (!barra.contains(ev.target) && doc.contains(ev.target)) { abrir(u.pConf, u.conforto, false); abrir(u.pA11y, u.a11y, false); }
    });
    [u.pConf, u.pA11y].forEach(function (p) {
      p.addEventListener("change", function (ev) {
        var t = ev.target, k = t.getAttribute("data-pp"), patch = {};
        if (t.name === "pp-texto") return mudar({ texto: parseInt(t.value, 10) }, "ok");
        if (t.name === "pp-aviso") return mudar({ aviso: parseInt(t.value, 10) }, "ok");
        /* o Tema (dentro do Modo de conforto) vem antes do "data-pp": os botões de tema não têm essa marca (20/11/2026) */
        if (t.name === "pp-tema") return mudar({ tema: t.value }, t.value === "auto" ? "aAuto" : t.value === "escuro" ? "aEsc" : "aClaro");
        if (!k) return;
        if (k === "conforto") { patch = { conforto: t.checked, tema: t.checked ? "escuro" : "auto", calma: t.checked, espaco: t.checked }; return mudar(patch, t.checked ? "aConfOn" : "aConfOff"); }
        patch[k] = t.checked; mudar(patch, k === "libras" && t.checked ? "librasOn" : "ok");
      });
      p.addEventListener("click", function (ev) {
        var b = ev.target.closest ? ev.target.closest("button") : null; if (!b) return;
        var a = b.getAttribute("data-pp-acao");
        if (a === "fechar") { var dono = p === u.pConf ? u.conforto : u.a11y; abrir(p, dono, false); dono.focus(); }
        else if (a === "padrao") { var id = P.estado.idioma; P.estado = copia(PADRAO); mudar({ idioma: id }, "aPadrao"); }
        else if (a === "ouvir") ouvir();
        else if (a === "pausar") pausarFala();
        else if (a === "parar") pararFala();
        else if (a === "relatar") relatar();
        else if (a === "copiar-relato") copiarRelato();
        else if (a === "caa") caa(b.getAttribute("data-frase"));
      });
    });
  }
  function abrir(painel, botao, sim) {
    var u = P.ui;
    if (sim) { var outro = painel === u.pConf ? [u.pA11y, u.a11y] : [u.pConf, u.conforto]; outro[0].hidden = true; outro[1].setAttribute("aria-expanded", "false"); }
    painel.hidden = !sim; botao.setAttribute("aria-expanded", sim ? "true" : "false");
    if (sim) { var x = painel.querySelector("input,button"); if (x) x.focus(); }
  }

  function caixa(chave, rot, desc) {
    var dentro = [criar("span", null, [txt(rot)])];
    if (desc) dentro[0].appendChild(criar("span", { "class": "pp-d" }, [txt(desc)]));
    return criar("label", null, [criar("input", { type: "checkbox", "data-pp": chave, id: "pp-c-" + chave })].concat(dentro));
  }
  function botao(acao, rot, extra) { var a = { type: "button", "data-pp-acao": acao, id: "pp-b-" + acao + (extra ? "-" + extra : "") }; return criar("button", a, [txt(rot)]); }
  function desenharPaineis() {
    var u = P.ui, f;
    [u.pConf, u.pA11y].forEach(function (p) { while (p.firstChild) p.removeChild(p.firstChild); });
    /* conforto */
    f = u.pConf;
    f.appendChild(criar("h2", { id: "pp-conf-t" }, [txt("confT")]));
    f.appendChild(criar("p", null, [txt("confD")]));
    f.appendChild(caixa("conforto", "confLiga", "confLigaD"));
    /* tema dentro do modo de conforto: a mesma escolha da barra (o escuro é o verde do guia) */
    var ft = criar("fieldset", null, [criar("legend", null, [txt("tema")])]);
    ["claro", "escuro", "auto"].forEach(function (v) { ft.appendChild(criar("label", null, [criar("input", { type: "radio", name: "pp-tema", value: v, id: "pp-tema-" + v }), criar("span", null, [txt(v)])])); });
    f.appendChild(ft);
    var fs = criar("fieldset", null, [criar("legend", null, [txt("texto")])]);
    [0, 1, 2].forEach(function (n) { fs.appendChild(criar("label", null, [criar("input", { type: "radio", name: "pp-texto", value: String(n), id: "pp-texto-" + n }), criar("span", null, [txt("t" + n)])])); });
    f.appendChild(fs);
    var fa = criar("fieldset", null, [criar("legend", null, [txt("aviso")])]);
    [4, 8, 15].forEach(function (n) { fa.appendChild(criar("label", null, [criar("input", { type: "radio", name: "pp-aviso", value: String(n), id: "pp-aviso-" + n }), criar("span", null, [txt("a" + n)])])); });
    f.appendChild(fa);
    f.appendChild(caixa("espaco", "espaco", "espacoD"));
    f.appendChild(caixa("calma", "calma", "calmaD"));
    f.appendChild(caixa("foco", "foco", "focoD"));
    f.appendChild(caixa("dislexia", "dislexia", "dislexiaD"));
    f.appendChild(caixa("regua", "regua", "reguaD"));
    f.appendChild(caixa("simples", "simples", "simplesD"));
    f.appendChild(caixa("lembrar", "lembrar", "lembrarD"));
    f.appendChild(criar("div", { "class": "pp-acoes" }, [botao("padrao", "padrao", "c"), botao("fechar", "fechar", "c")]));
    f.lastChild.lastChild.className = "pp-prim";
    /* acessibilidade */
    f = u.pA11y;
    f.appendChild(criar("h2", { id: "pp-a11y-t" }, [txt("a11yT")]));
    f.appendChild(criar("p", null, [txt("a11yD")]));
    f.appendChild(criar("h3", null, [txt("cegT")]));
    f.appendChild(criar("p", null, [txt("cegD")]));
    if (global.speechSynthesis && global.SpeechSynthesisUtterance) {
      f.appendChild(criar("div", { "class": "pp-acoes" }, [botao("ouvir", "ouvir"), botao("pausar", "pausar"), botao("parar", "parar")]));
      f.appendChild(criar("p", null, [txt("ouvirD")]));
    }
    f.appendChild(caixa("contraste", "contraste", "contrasteD"));
    f.appendChild(criar("p", null, [txt("zoom")]));
    f.appendChild(criar("p", null, [criar("strong", null, [txt("atalhos")])]));
    f.appendChild(criar("ul", null, ["at1", "at2", "at3", "at0", "atEsc"].map(function (k) { return criar("li", null, [txt(k)]); })));
    f.appendChild(criar("h3", null, [txt("surT")]));
    f.appendChild(criar("p", null, [txt("surD")]));
    f.appendChild(caixa("libras", "libras", "librasD"));
    f.appendChild(criar("p", { "class": "pp-aviso", id: "pp-libras-aviso", role: "note" }, [txt("librasOn")]));
    f.appendChild(criar("h3", null, [txt("falT")]));
    f.appendChild(criar("p", null, [txt("falD")]));
    f.appendChild(criar("p", null, [criar("strong", { id: "pp-caa-t" }, [txt("caa")])]));
    var prancha = criar("div", { "class": "pp-caa", role: "group", "aria-labelledby": "pp-caa-t" });
    FRASES.forEach(function (k) { var b = criar("button", { type: "button", "data-pp-acao": "caa", "data-frase": k, id: "pp-caa-" + k }); b.appendChild(icone(k)); b.appendChild(criar("span", null, [txt(k)])); prancha.appendChild(b); });
    f.appendChild(prancha);
    u.cartao = criar("div", { "class": "pp-cartao", role: "status", "aria-live": "polite", hidden: true, id: "pp-caa-cartao" });
    f.appendChild(u.cartao);
    f.appendChild(criar("h3", null, [txt("mobT")]));
    f.appendChild(criar("p", null, [txt("mobD")]));
    if (global.SpeechRecognition || global.webkitSpeechRecognition) f.appendChild(caixa("voz", "voz", "vozD"));
    else f.appendChild(criar("p", null, [txt("semRec")]));
    u.vozMsg = criar("p", { role: "status", id: "pp-voz-msg" }); f.appendChild(u.vozMsg);
    f.appendChild(criar("h3", null, [txt("decT")]));
    f.appendChild(criar("p", null, [txt("decD")]));
    f.appendChild(criar("div", { "class": "pp-acoes" }, [botao("relatar", "relatar"), botao("padrao", "padrao", "a"), botao("fechar", "fechar", "a")]));
    f.lastChild.lastChild.className = "pp-prim";
    f.appendChild(criar("div", { id: "pp-relato", hidden: true }, [criar("p", null, [txt("relatarD")]),
      criar("label", { "for": "pp-relato-t", style: "min-height:0;display:block" }, [txt("relatarCampo")]),
      criar("textarea", { id: "pp-relato-t", rows: "4", style: "width:100%;font:inherit;font-size:14px;border:1px solid currentColor;border-radius:8px;padding:8px;background:inherit;color:inherit" }),
      criar("div", { "class": "pp-acoes" }, [botao("copiar-relato", "copiar")]), criar("p", { id: "pp-relato-msg", role: "status" })]));
  }
  function marcarPaineis() {
    var u = P.ui, e = P.estado;
    [u.pConf, u.pA11y].forEach(function (p) {
      p.querySelectorAll("input").forEach(function (i) {
        if (i.name === "pp-tema") i.checked = i.value === e.tema;
        else if (i.name === "pp-texto") i.checked = parseInt(i.value, 10) === e.texto;
        else if (i.name === "pp-aviso") i.checked = parseInt(i.value, 10) === (e.aviso || 4);
        else if (i.getAttribute("data-pp")) i.checked = !!e[i.getAttribute("data-pp")];
      });
    });
    var av = doc.getElementById("pp-libras-aviso"); if (av) av.hidden = !e.libras;
  }
  function desenharBarra() {
    var u = P.ui, e = P.estado; if (!u.barra) return;
    if (P.painelIdioma !== e.idioma) {
      P.painelIdioma = e.idioma;
      var ativo = doc.activeElement, foco = ativo && u.barra.contains(ativo) ? ativo.id : "";
      u.barra.setAttribute("aria-label", txt("grupo"));
      u.idiomaTxt.textContent = txt("idioma");
      u.temaTxt.textContent = txt("tema");
      u.tema.options[0].textContent = txt("claro"); u.tema.options[1].textContent = txt("escuro"); u.tema.options[2].textContent = txt("auto");
      desenharPaineis();
      if (foco) { var x = doc.getElementById(foco); if (x) x.focus(); }
    }
    u.idioma.value = e.idioma;
    u.tema.value = e.tema;
    u.conforto.textContent = txt("conforto");
    if (e.conforto) u.conforto.appendChild(criar("span", { "class": "pp-on" }, [" (" + txt("ligado") + ")"]));
    u.conforto.appendChild(criar("span", { "class": "pp-seta", "aria-hidden": "true" }, ["▾"]));
    u.a11y.textContent = txt("a11y");
    u.a11y.appendChild(criar("span", { "class": "pp-seta", "aria-hidden": "true" }, ["▾"]));
    marcarPaineis();
  }
  function dizer(chaveOuTexto) {
    var u = P.ui; if (!u.anuncio) return;
    var t = UI.pt[chaveOuTexto] ? txt(chaveOuTexto) : chaveOuTexto;
    u.anuncio.textContent = ""; setTimeout(function () { u.anuncio.textContent = t; }, 30);
  }

  /* ---------- pular, atalhos, régua, lembrar ---------- */
  function alvoConteudo() { var c = P.op.conteudo; if (typeof c === "function") { try { c = c(); } catch (e) { c = null; } } return el(c) || doc.querySelector("#px-conteudo") || doc.querySelector("main") || doc.querySelector("[role=main]"); }
  function irPara(x) {
    if (!x) return;
    if (!x.hasAttribute("tabindex") && !/^(A|BUTTON|INPUT|SELECT|TEXTAREA)$/.test(x.nodeName)) x.setAttribute("tabindex", "-1");
    x.focus(); try { x.scrollIntoView({ block: "start" }); } catch (e) {}
  }
  function montarPular() {
    if (doc.querySelector(".pular,.salto,.skip,.px-pular,[data-pp-pular]")) return;
    var a = criar("a", { "class": "pp-pular", href: "#", "data-pp-pular": "", "data-pp-manter": "" });
    P.ui.pular = a;
    a.addEventListener("click", function (ev) { ev.preventDefault(); irPara(alvoConteudo()); });
    doc.body.insertBefore(a, doc.body.firstChild);
  }
  function atalhos(ev) {
    if (!ev.altKey || ev.ctrlKey || ev.metaKey) return;
    var k = ev.key, c = ev.code;
    var n = /^Digit(\d)$/.test(c) ? c.slice(5) : (/^\d$/.test(k) ? k : null);
    if (n === "1") irPara(alvoConteudo());
    else if (n === "2") irPara(el(P.op.menu) || doc.querySelector("nav"));
    else if (n === "3") { var b = el(P.op.busca) || doc.querySelector("input[type=search],[role=search] input,[role=tablist]"); if (b && b.getAttribute("role") === "tablist") b = b.querySelector("[aria-selected=true],[role=tab]") || b; irPara(b); }
    else if (n === "0") { if (!P.ui.pA11y) return; abrir(P.ui.pA11y, P.ui.a11y, true); }
    else return;
    ev.preventDefault();
  }
  function regua(y) { var r = P.ui.regua; if (r && P.estado.regua) r.style.top = Math.round(y) + "px"; }
  function lugarChave() { return "physis-pref-lugar"; }
  function salvarLugar() {
    if (!P.estado || !P.estado.lembrar) return;
    var m = {}; try { m = JSON.parse(ler(lugarChave()) || "{}") || {}; } catch (e) { m = {}; }
    var o = { y: Math.round(global.scrollY || 0), hash: global.location.hash || "" };
    if (P.op.lembrar && typeof P.op.lembrar.salvar === "function") { try { o.pagina = P.op.lembrar.salvar(); } catch (e) {} }
    m[P.op.tela || global.location.pathname] = o;
    gravar(lugarChave(), JSON.stringify(m));
  }
  function restaurarLugar() {
    if (!P.estado.lembrar) return;
    var m = {}; try { m = JSON.parse(ler(lugarChave()) || "{}") || {}; } catch (e) { return; }
    var o = m[P.op.tela || global.location.pathname]; if (!o) return;
    if (P.op.lembrar && typeof P.op.lembrar.restaurar === "function" && o.pagina) { try { P.op.lembrar.restaurar(o.pagina); } catch (e) {} }
    if (o.hash && !global.location.hash) { try { global.history.replaceState(null, "", o.hash); global.dispatchEvent(new HashChangeEvent("hashchange")); } catch (e) {} }
    setTimeout(function () { global.scrollTo(0, o.y || 0); }, 60);
  }

  /* ---------- menos estímulo: nada toca sozinho; legendas ---------- */
  function pararMidias(raiz) {
    if (!raiz.querySelectorAll) return;
    raiz.querySelectorAll("video[autoplay],audio[autoplay]").forEach(function (m) { try { m.pause(); m.removeAttribute("autoplay"); } catch (e) {} });
  }
  function conferirLegendas(raiz) {
    if (!raiz.querySelectorAll || !global.console) return;
    var ms = raiz.nodeName === "VIDEO" || raiz.nodeName === "AUDIO" ? [raiz] : raiz.querySelectorAll("video,audio");
    Array.prototype.forEach.call(ms, function (m) {
      if (m.__ppLegenda) return; m.__ppLegenda = 1;
      if (!m.querySelector("track[kind=captions],track[kind=subtitles]")) console.warn("Physis acessibilidade: mídia sem legenda (<track kind=\"captions\">)", m);
    });
  }

  /* ---------- ouvir esta tela ---------- */
  function vozDe(lingua) {
    var vs = []; try { vs = global.speechSynthesis.getVoices() || []; } catch (e) {}
    var pref = lingua === "en" ? /^en/i : /^pt/i, br = lingua === "en" ? /^en-US/i : /^pt-BR/i;
    return vs.filter(function (v) { return br.test(v.lang); })[0] || vs.filter(function (v) { return pref.test(v.lang); })[0] || null;
  }
  function textoParaLer() {
    var sel = ""; try { sel = String(global.getSelection ? global.getSelection() : ""); } catch (e) {}
    if (sel.trim()) return sel;
    var a = alvoConteudo() || doc.body;
    return (a.innerText || a.textContent || "");
  }
  function ouvir() {
    var s = global.speechSynthesis; if (!s) return;
    s.cancel();
    var t = textoParaLer().replace(/\s+/g, " ").trim(); if (!t) return;
    var pedacos = t.match(/[^.!?;:]{1,220}[.!?;:]?/g) || [t], lingua = P.estado.idioma, voz = vozDe(lingua);
    pedacos.forEach(function (p) {
      var u = new global.SpeechSynthesisUtterance(p.trim());
      u.lang = lingua === "en" ? "en-US" : "pt-BR"; if (voz) u.voice = voz;
      s.speak(u);
    });
    P.falando = true; dizer("lido");
  }
  function pausarFala() {
    var s = global.speechSynthesis; if (!s) return;
    var b = doc.getElementById("pp-b-pausar");
    if (s.paused) { s.resume(); if (b) b.textContent = txt("pausar"); } else { s.pause(); if (b) b.textContent = txt("continuar"); }
  }
  function pararFala() { var s = global.speechSynthesis; if (s) { s.cancel(); P.falando = false; dizer("lidoFim"); } var b = doc.getElementById("pp-b-pausar"); if (b) b.textContent = txt("pausar"); }

  /* ---------- comunicação alternativa ---------- */
  function ehCampo(x) { return x && (x.nodeName === "TEXTAREA" || (x.nodeName === "INPUT" && /^(text|search|email|tel|url|)$/i.test(x.type || ""))) && !x.disabled && !x.readOnly; }
  function caa(k) {
    var frase = txt(k), alvo = ehCampo(P.campo) && doc.contains(P.campo) ? P.campo : el(P.op.contato);
    if (ehCampo(alvo)) {
      var ini = alvo.selectionStart, fim = alvo.selectionEnd, v = alvo.value, sep = v && !/\s$/.test(v.slice(0, ini == null ? v.length : ini)) ? " " : "";
      try { alvo.setRangeText(sep + frase, ini == null ? v.length : ini, fim == null ? v.length : fim, "end"); } catch (e) { alvo.value = v + sep + frase; }
      alvo.dispatchEvent(new Event("input", { bubbles: true }));
      abrir(P.ui.pA11y, P.ui.a11y, false);
      try { alvo.scrollIntoView({ block: "center" }); } catch (e) {}
      alvo.focus();
      dizer(txt("caaFoi") + frase);
    } else if (typeof P.op.suporte === "function") {
      abrir(P.ui.pA11y, P.ui.a11y, false);
      try { P.op.suporte(frase); } catch (e) {}
      dizer(txt("caaSup") + frase);
    } else {
      var c = P.ui.cartao; c.hidden = false; c.textContent = "";
      c.appendChild(criar("span", { "class": "pp-d" }, [txt("caaMostra")])); c.appendChild(doc.createTextNode(frase));
    }
  }
  function relatar() {
    if (typeof global.abrirJuridico === "function") { try { global.abrirJuridico("acessibilidade"); return; } catch (e) {} }
    var r = P.op.relatar;
    if (typeof r === "function") return r();
    if (typeof r === "string" && r.charAt(0) === "#") { abrir(P.ui.pA11y, P.ui.a11y, false); irPara(el(r)); var c = el(P.op.contato); if (ehCampo(c)) c.focus(); return; }
    if (typeof r === "string" && r) { global.location.href = r; return; }
    /* sem canal na página: o relato é escrito aqui e copiado, para enviar pelo suporte da Physis (funciona sem internet) */
    var box = doc.getElementById("pp-relato"); if (!box) return; box.hidden = false; var t = doc.getElementById("pp-relato-t"); if (t) t.focus();
  }
  function copiarRelato() {
    var t = doc.getElementById("pp-relato-t"), e = estadoPublico();
    var rel = (t && t.value.trim() ? t.value.trim() + "\n\n" : "") + "Tela: " + doc.title + "\nEndereço: " + global.location.pathname + global.location.hash +
      "\nQuando: " + new Date().toISOString() + "\nNavegador: " + global.navigator.userAgent + "\nPreferências: tema " + e.temaEfetivo +
      (e.conforto ? ", conforto" : "") + (e.texto ? ", texto maior" : "") + (e.contraste ? ", alto contraste" : "");
    var feito = false;
    try { if (global.navigator.clipboard && global.isSecureContext) { global.navigator.clipboard.writeText(rel); feito = true; } } catch (x) {}
    if (!feito) { var a = criar("textarea", { style: "position:fixed;left:-9999px", "aria-hidden": "true" }); a.value = rel; doc.body.appendChild(a); a.select(); try { doc.execCommand("copy"); } catch (x) {} doc.body.removeChild(a); }
    var m = doc.getElementById("pp-relato-msg"); if (m) m.textContent = txt("copiado");
    dizer("copiado");
  }

  /* ---------- comandos de voz ---------- */
  function focaveis() {
    return Array.prototype.filter.call(doc.querySelectorAll("a[href],button,input,select,textarea,[tabindex]"), function (x) {
      return !x.disabled && x.tabIndex >= 0 && !x.closest("[hidden],[inert]") && (x.offsetWidth || x.offsetHeight || x.getClientRects().length);
    });
  }
  function moverFoco(passo) { var l = focaveis(), i = l.indexOf(doc.activeElement); var x = l[(i + passo + l.length) % l.length]; if (x) x.focus(); }
  function comando(frase) {
    var f = frase.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    if (/conteudo|content/.test(f)) irPara(alvoConteudo());
    else if (/proximo|next/.test(f)) moverFoco(1);
    else if (/voltar|anterior|back|previous/.test(f)) moverFoco(-1);
    else if (/ler|leia|read/.test(f)) ouvir();
    else if (/aumentar|maior|bigger|larger/.test(f)) mudar({ texto: Math.min(2, P.estado.texto + 1) }, "ok");
    else if (/diminuir|menor|smaller/.test(f)) mudar({ texto: Math.max(0, P.estado.texto - 1) }, "ok");
    else if (/parar|pare|stop/.test(f)) pararFala();
    else return;
    if (P.ui.vozMsg) P.ui.vozMsg.textContent = "“" + frase.trim() + "”";
  }
  function vozLigar(sim) {
    var R = global.SpeechRecognition || global.webkitSpeechRecognition;
    if (!R) return;
    if (!sim) { if (P.rec) { var r0 = P.rec; P.rec = null; try { r0.stop(); } catch (e) {} if (P.ui.vozMsg) P.ui.vozMsg.textContent = ""; } return; }
    if (P.rec) { P.rec.lang = P.estado.idioma === "en" ? "en-US" : "pt-BR"; return; }
    var r = new R(); P.rec = r;
    r.lang = P.estado.idioma === "en" ? "en-US" : "pt-BR"; r.continuous = true; r.interimResults = false;
    r.onresult = function (ev) { for (var i = ev.resultIndex; i < ev.results.length; i++) if (ev.results[i].isFinal) comando(ev.results[i][0].transcript); };
    r.onerror = function (ev) { if (P.ui.vozMsg) P.ui.vozMsg.textContent = txt("vozErro") + (ev.error || ""); if (ev.error === "not-allowed" || ev.error === "service-not-allowed") { P.rec = null; mudar({ voz: false }, null); } };
    r.onend = function () { if (P.rec === r) { try { r.start(); } catch (e) {} } };
    try { r.start(); if (P.ui.vozMsg) P.ui.vozMsg.textContent = txt("vozOuve"); } catch (e) {}
  }

  /* ---------- inglês ---------- */
  var DIC = {}, RX = [], EXC = {};
  function chave(s) { return String(s).replace(/\s+/g, " ").trim(); }
  function temLetra(s) { return /[A-Za-zÀ-ÿ]/.test(s); }
  /* par de um texto já normalizado: dicionário, depois padrões (o segundo item pode ser texto com $1 ou função) */
  function par(k) {
    var v = DIC[k];
    if (v == null) for (var i = 0; i < RX.length; i++) { RX[i][0].lastIndex = 0; if (RX[i][0].test(k)) { v = k.replace(RX[i][0], RX[i][1]); break; } }
    return v;
  }
  /* textos montados no código ("Captação de " + n + " m³ ..."): troca os pedaços conhecidos (opção fragmentos), do maior
     para o menor e só em limite de palavra. Se sobrar palavra em português, o texto entra em faltando(). */
  var FRAG = null, FRAGRX = null, LETRA = /[A-Za-zÀ-ÿ]/;
  var PT_PALAVRA = /[áéíóúâêôãõç]|\b(de|do|da|dos|das|com|sem|para|por|não|um|uma|ou|no|na|nos|nas|em|que|ao|os|as|pelo|pela|entre|até|antes|depois|acima|abaixo)\b/i;
  function prepararFragmentos(f) {
    FRAG = {}; var ks = [];
    for (var k in f) if (tem(f, k)) { var c = chave(k); if (c.length >= 2) { FRAG[c] = f[k]; ks.push(c); } }
    ks.sort(function (a, b) { return b.length - a.length; });
    FRAGRX = ks.length ? new RegExp(ks.map(function (x) { return x.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("|"), "g") : null;
  }
  function fragmentos(k) {
    if (!FRAGRX) return null;
    var mudou = false, resto = "", ult = 0;
    var r = k.replace(FRAGRX, function (m, pos, tudo) {
      var antes = pos > 0 ? tudo.charAt(pos - 1) : "", depois = tudo.charAt(pos + m.length);
      if ((LETRA.test(m.charAt(0)) && LETRA.test(antes)) || (LETRA.test(m.charAt(m.length - 1)) && LETRA.test(depois))) return m;
      mudou = true; resto += tudo.slice(ult, pos) + " "; ult = pos + m.length; return FRAG[m];
    });
    if (!mudou) return null;
    resto += k.slice(ult);
    if (PT_PALAVRA.test(resto.replace(/\d[\d.,]*/g, " "))) P.faltam[k] = 1;
    return r;
  }
  function traduzir(s) {
    var k = chave(s); if (!k) return null;
    if (EXC[k]) return null;
    var v = par(k);
    if (v == null && k.indexOf(" · ") > 0) {          /* "A · B": traduz parte por parte, se todas tiverem par */
      var ps = k.split(" · "), ok = true;
      ps = ps.map(function (x) { var t = par(x); if (t == null && (EXC[x] || !temLetra(x))) t = x; if (t == null) ok = false; return t; });
      if (ok) v = ps.join(" · ");
    }
    if (v == null) { v = fragmentos(k); if (v != null) return (/^\s/.test(s) ? " " : "") + v + (/\s$/.test(s) ? " " : ""); }
    if (v == null) { if (temLetra(k)) P.faltam[k] = 1; return null; }
    return (/^\s/.test(s) ? " " : "") + v + (/\s$/.test(s) ? " " : "");
  }
  function pular(e) {
    for (; e && e.nodeType === 1; e = e.parentElement) {
      if (IGNORAR[e.nodeName]) return true;
      if (e.hasAttribute("data-pp-manter") || e.getAttribute("translate") === "no") return true;
      if (e.isContentEditable) return true;
    }
    return false;
  }
  function textoNo(n, en) {
    var o = P.orig.get(n);
    if (o && n.nodeValue !== o.pt && n.nodeValue !== o.en) { P.orig.delete(n); o = null; }   /* mudou por baixo: é texto novo */
    if (en) {
      var base = o ? o.pt : n.nodeValue, t = traduzir(base);
      if (t != null) { P.orig.set(n, { pt: base, en: t }); if (n.nodeValue !== t) n.nodeValue = t; }
    } else if (o) { if (n.nodeValue !== o.pt) n.nodeValue = o.pt; P.orig.delete(n); }
  }
  function atributosEl(e, en) {
    var mapa = P.origAttr.get(e) || {}, attrs = ATRIBUTOS.slice();
    if (e.nodeName === "INPUT" && /^(button|submit|reset)$/i.test(e.type)) attrs.push("value");
    attrs.forEach(function (a) {
      if (!e.hasAttribute(a)) return;
      var atual = e.getAttribute(a), o = mapa[a];
      if (o && atual !== o.pt && atual !== o.en) { delete mapa[a]; o = null; }
      if (en) { var base = o ? o.pt : atual, t = traduzir(base); if (t != null) { t = t.trim(); mapa[a] = { pt: base, en: t }; if (atual !== t) e.setAttribute(a, t); } }
      else if (o) { if (atual !== o.pt) e.setAttribute(a, o.pt); delete mapa[a]; }
    });
    P.origAttr.set(e, mapa);
  }
  function percorrer(raiz, en) {
    if (!raiz) return;
    if (raiz.nodeType === 3) { if (!pular(raiz.parentElement)) textoNo(raiz, en); return; }
    if (raiz.nodeType !== 1 && raiz.nodeType !== 9 && raiz.nodeType !== 11) return;
    if (raiz.nodeType === 1 && pular(raiz)) return;
    var w = doc.createTreeWalker(raiz, 5 /* elementos e textos */, {
      acceptNode: function (n) {
        if (n.nodeType === 1 && (IGNORAR[n.nodeName] || n.hasAttribute("data-pp-manter") || n.getAttribute("translate") === "no" || n.isContentEditable)) return 2;
        return 1;
      }
    });
    if (raiz.nodeType === 1) atributosEl(raiz, en);
    var n;
    while ((n = w.nextNode())) { if (n.nodeType === 3) textoNo(n, en); else atributosEl(n, en); }
  }
  function tituloDoc(en) {
    if (P.tituloPt == null) P.tituloPt = doc.title;
    if (doc.title !== P.tituloPt && doc.title !== P.tituloEn) P.tituloPt = doc.title;
    if (en) { var t = traduzir(P.tituloPt); P.tituloEn = t ? t.trim() : null; if (t) doc.title = t.trim(); } else if (doc.title !== P.tituloPt) doc.title = P.tituloPt;
  }
  function traduzLocal() { return P.estado.idioma === "en" && !P.pausado && !externo(); }
  function tudo() {
    if (externo()) return;
    var en = traduzLocal();
    percorrer(doc.body, en); tituloDoc(en);
    if (P.obs) P.obs.takeRecords();
  }
  function definirIdioma(qual) {
    var x = externo();
    if (x) {   /* a tela traduz a si mesma: só pede a troca, uma vez, quando ela ainda está na outra língua */
      var pela = !!P.pelaPessoa; P.pelaPessoa = false;
      if (idiomaDaTela() !== qual) { try { x.definir(qual, pela); } catch (e) { if (global.console) console.error(e); } }
    } else {
      doc.documentElement.setAttribute("lang", qual === "en" ? "en" : P.idiomaOriginal);
      tudo();
    }
    if (P.ui.pular) P.ui.pular.textContent = txt("pular");
    var pl = doc.querySelector("a.px-pular"); if (pl && !P.op.semFaixa) pl.textContent = txt("pular");
  }
  function observar() {
    if (!global.MutationObserver) return;
    P.obs = new MutationObserver(function (lista) {
      var en = traduzLocal();
      lista.forEach(function (m) {
        if (m.type === "childList") {
          for (var i = 0; i < m.addedNodes.length; i++) {
            var a = m.addedNodes[i];
            if (a.nodeType === 1) { conferirLegendas(a); if (P.estado.calma) pararMidias(a); }
            if (en && (a.nodeType !== 3 || !pular(a.parentElement))) percorrer(a, true);
          }
        } else if (!en) return;
        else if (m.type === "characterData") { if (!pular(m.target.parentElement)) textoNo(m.target, true); }
        else if (m.type === "attributes" && !pular(m.target)) atributosEl(m.target, true);
      });
      if (en) tituloDoc(true);
      P.obs.takeRecords();
    });
    P.obs.observe(doc.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATRIBUTOS.concat(["value"]) });
  }

  /* ---------- API ---------- */
  var API = {
    versao: 3,
    iniciar: function (op) {
      if (P.op) return API;
      P.op = op || {};
      P.op.chave = P.op.chave || "physis-pref";
      var d = P.op.dicionario || {};
      for (var k in d) if (tem(d, k)) DIC[chave(k)] = d[k];
      FRASES.forEach(function (f) { if (!DIC[UI.pt[f]]) DIC[UI.pt[f]] = UI.en[f]; });
      (P.op.padroes || []).forEach(function (p) { RX.push([p[0] instanceof RegExp ? p[0] : new RegExp(p[0]), p[1]]); });
      (P.op.excecoes || []).forEach(function (x) { EXC[chave(x)] = 1; });
      if (P.op.fragmentos) prepararFragmentos(P.op.fragmentos);
      P.idiomaOriginal = doc.documentElement.getAttribute("lang") || "pt-BR";
      if (!doc.getElementById("pp-estilo")) { var st = doc.createElement("style"); st.id = "pp-estilo"; st.textContent = CSS; (doc.head || doc.documentElement).appendChild(st); }
      P.estado = carregar();
      montarPular();
      montarBarra();
      aplicar(null);
      observar();
      conferirLegendas(doc);
      restaurarLugar();
      try {
        var mm = global.matchMedia("(prefers-color-scheme: dark)");
        var seguir = function () { if (P.estado.tema === "auto") aplicar(null); };
        if (mm.addEventListener) mm.addEventListener("change", seguir); else if (mm.addListener) mm.addListener(seguir);
      } catch (e) {}
      doc.addEventListener("keydown", atalhos);
      doc.addEventListener("focusin", function (ev) {
        var t = ev.target; if (P.ui.barra && P.ui.barra.contains(t)) return;
        if (ehCampo(t)) P.campo = t;
        if (P.estado.regua && t.getBoundingClientRect) { var r = t.getBoundingClientRect(); regua(r.top + r.height / 2); }
      });
      doc.addEventListener("pointermove", function (ev) { regua(ev.clientY); }, { passive: true });
      var tempo = null;
      global.addEventListener("scroll", function () { if (!P.estado.lembrar) return; clearTimeout(tempo); tempo = setTimeout(salvarLugar, 400); }, { passive: true });
      global.addEventListener("hashchange", salvarLugar);
      global.addEventListener("pagehide", salvarLugar);
      /* tela com tradução própria trocou de língua pelo botão dela: a barra e a escolha guardada acompanham */
      if (externo() && global.MutationObserver) {
        new MutationObserver(function () {
          var q = idiomaDaTela(); if (q === P.estado.idioma) return;
          P.estado.idioma = q; P.idiomaAplicado = q; guardar(); desenharBarra();
          if (typeof P.op.aoMudar === "function") { try { P.op.aoMudar(estadoPublico()); } catch (x) {} }
        }).observe(doc.documentElement, { attributes: true, attributeFilter: ["lang"] });
      }
      /* outra aba, ou a plataforma que abriu esta tela num quadro, mudou a escolha: segue */
      global.addEventListener("storage", function (ev) {
        if (ev.key !== P.op.chave && ev.key !== "physis-pref-tema" && ev.key !== "physis-idioma" && ev.key !== "physis-conforto" && ev.key !== "physis-fundo" && ev.key !== "physis-passaporte") return;
        var antes = JSON.stringify(P.estado), novo;
        if (ev.key === P.op.chave) { try { novo = limpar(JSON.parse(ev.newValue || "null")); } catch (e) { return; } }
        else {
          novo = copia(P.estado);
          if (ev.key === "physis-pref-tema" && /^(claro|escuro|auto)$/.test(ev.newValue || "")) novo.tema = ev.newValue;
          if (ev.key === "physis-idioma") novo.idioma = ev.newValue === "en" ? "en" : "pt";
          if (ev.key === "physis-conforto") novo.conforto = ev.newValue === "1";
          if (ev.key === "physis-fundo") novo.verde = ev.newValue === "verde";
          if (ev.key === "physis-passaporte") { try { var pp = JSON.parse(ev.newValue || "{}"); novo.texto = pp.texto ? Math.max(1, novo.texto) : 0; novo.espaco = !!pp.espaco; novo.contraste = !!pp.contraste; novo.calma = !!pp.calma; } catch (e) {} }
          novo = limpar(novo);
        }
        if (JSON.stringify(novo) === antes) return;
        P.estado = novo; gravar(P.op.chave, JSON.stringify(novo)); aplicar(null);
      });
      return API;
    },
    estado: function () { return P.estado ? estadoPublico() : null; },
    definir: function (patch) { if (P.estado) mudar(patch || {}, null); return API.estado(); },
    idioma: function () { return P.estado ? P.estado.idioma : "pt"; },
    /* tradução de um texto solto (para mensagens montadas no código); devolve o próprio texto se não houver par */
    t: function (s) { if (!P.estado || P.estado.idioma !== "en") return s; var r = traduzir(s); return r == null ? s : r; },
    /* par em inglês de um texto, qualquer que seja o idioma ligado (para usar dentro de padrões) */
    par: function (s) { var k = chave(s), r = par(k); if (r == null && k.indexOf(" · ") > 0) { r = traduzir(k); r = r == null ? null : r.trim(); } return r == null ? s : r; },
    acrescentar: function (dic, padroes) {
      for (var k in (dic || {})) if (tem(dic, k)) DIC[chave(k)] = dic[k];
      (padroes || []).forEach(function (p) { RX.push([p[0] instanceof RegExp ? p[0] : new RegExp(p[0]), p[1]]); });
      if (P.estado) tudo();
    },
    /* pausa a tradução (ex.: durante a edição de textos): a tela volta ao português até pausar(false) */
    pausar: function (sim) { P.pausado = !!sim; if (P.estado) tudo(); },
    reaplicar: function () { if (P.estado) tudo(); },
    abrirPainel: function (qual) { if (!P.ui.barra) return; if (qual === "conforto") abrir(P.ui.pConf, P.ui.conforto, true); else abrir(P.ui.pA11y, P.ui.a11y, true); },
    ouvir: ouvir, parar: pararFala,
    faltando: function () {
      P.faltam = {};
      if (P.estado && P.estado.idioma === "en") tudo();
      return Object.keys(P.faltam).filter(function (k) { return !DIC[k]; }).sort();
    }
  };
  global.PhysisPreferencias = API;

  /* ---------- PxPref: a mesma barra para as telas com tradução própria (plataforma, Gestão Physis, SCADA) ----------
     Era um segundo módulo (px-preferencias v1); desde a v3 é só esta porta de entrada para o mesmo código.
     PxPref.iniciar({ lugar, idioma:{atual,definir}, conteudo, menu, relatar, suporte, tela, lugarAtual, irPara, semFaixa, aoMudar })
     aoMudar recebe { tema (o que vale: claro|escuro), temaEscolha (claro|escuro|auto), idioma, conforto, verde, texto, ... }. */
  function formaPx(e) { if (!e) return null; var o = copia(e); o.temaEscolha = e.tema; o.tema = e.temaEfetivo; return o; }
  var PX = {
    versao: 3,
    iniciar: function (op) {
      op = op || {};
      var lembrar = op.lugarAtual || op.irPara ? { salvar: op.lugarAtual, restaurar: op.irPara } : null;
      API.iniciar({ chave: "physis-pref", ondeColocar: op.lugar, conteudo: op.conteudo, menu: op.menu, relatar: op.relatar, suporte: op.suporte,
        tela: op.tela, semFaixa: op.semFaixa, variante: op.variante, esconderEmQuadro: op.esconderEmQuadro !== false, idiomaExterno: op.idioma,
        lembrar: lembrar, aoMudar: op.aoMudar ? function (e) { op.aoMudar(formaPx(e)); } : null });
      return PX;
    },
    estado: function () { return formaPx(API.estado()); },
    definir: function (patch) { API.definir(patch); return PX.estado(); },
    redesenhar: function () { P.painelIdioma = null; desenharBarra(); },
    textos: UI
  };
  global.PxPref = PX;
})(typeof window !== "undefined" ? window : this);
