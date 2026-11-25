# Variáveis de ambiente do servidor (índice gerado do código)

Gerado por `ferramentas/listar_variaveis.py`. Cada variável aparece com o arquivo, a linha e o trecho onde é lida (o padrão,
quando existe, está no trecho). Segredos (senhas, chaves) nunca vão no código: só no arquivo de ambiente (regra 12).

| Variável | Onde é lida | Trecho do código |
|---|---|---|
| `PHYSIS_ACEITAR_SEM_CHAVE` | servidor.py:852 | `sem_chave = os.environ.get("PHYSIS_ACEITAR_SEM_CHAVE", "").strip()   # "1" aceita, "0" recusa, vazio: só rede local` |
| `PHYSIS_ACERVO` | mv_bots_extra.py:532 | `p = Path(pasta or os.environ.get("PHYSIS_ACERVO") or (base / "acervo"))` |
| `PHYSIS_APP_DOWNLOAD` | servidor.py:620 | `env = (os.environ.get("PHYSIS_APP_DOWNLOAD") or "").strip()` |
| `PHYSIS_BANCO` | mv_bots_extra.py:119 (+2) | `arq = Path(banco or os.environ.get("PHYSIS_BANCO") or "physis-hub.db")` |
| `PHYSIS_BIBLIOTECA_PASTA` | documentos_auto.py:482 | `self.pasta_bib = Path(pasta_biblioteca or os.environ.get("PHYSIS_BIBLIOTECA_PASTA") or (RAIZ / "dados" / "biblioteca"))` |
| `PHYSIS_CADASTRO_ABERTO` | servidor.py:797 | `cadastro_aberto = bool(instancia.get("cadastro_aberto")) or os.environ.get("PHYSIS_CADASTRO_ABERTO") == "1"` |
| `PHYSIS_CALC_CHAVE` | calc_cliente.py:61 | `chave = os.environ.get("PHYSIS_CALC_CHAVE")` |
| `PHYSIS_CALC_EXTERNO` | calc_cliente.py:51 | `if url and not destino_local(url) and os.environ.get("PHYSIS_CALC_EXTERNO") != "1":` |
| `PHYSIS_CALC_TEMPO` | calc_cliente.py:93 (+1) | `t = float(tempo or os.environ.get("PHYSIS_CALC_TEMPO") or 60)` |
| `PHYSIS_CALC_URL` | calc_cliente.py:50 | `url = (os.environ.get("PHYSIS_CALC_URL") or "").strip().rstrip("/")` |
| `PHYSIS_CAMADAS` | camadas_bot.py:444 (+2) | `alvo = pasta or (Path(os.environ["PHYSIS_CAMADAS"]) if os.environ.get("PHYSIS_CAMADAS") else None)` |
| `PHYSIS_CAMADAS_BRASIL` | camadas_bot.py:449 | `if os.environ.get("PHYSIS_CAMADAS_BRASIL") == "1":          # Brasil completo: refeito a cada 30 dias (o resto retoma)` |
| `PHYSIS_CAMADAS_DIAS` | camadas_bot.py:250 | `dias = float(os.environ.get("PHYSIS_CAMADAS_DIAS") or 0)` |
| `PHYSIS_CASA_EDITAVEIS` | gemeo_importar.py:39 | `PASTA_PADRAO = Path(os.environ.get("PHYSIS_CASA_EDITAVEIS") or (` |
| `PHYSIS_CATALOGO` | catalogo_modelos.py:136 | `amb = os.environ.get("PHYSIS_CATALOGO", "").strip()` |
| `PHYSIS_CEP_PROVEDOR` | cep.py:57 | `v = os.environ.get("PHYSIS_CEP_PROVEDOR", "brasilapi,viacep") if valor is None else valor` |
| `PHYSIS_CERT_AVISO_DIAS` | mv_bots_extra.py:501 (+1) | `aviso = _limite("PHYSIS_CERT_AVISO_DIAS")` |
| `PHYSIS_CHAMADAS` | servidor.py:798 (+1) | `csp = politica(os.environ.get("PHYSIS_CHAMADAS") or instancia.get("chamadas"))` |
| `PHYSIS_CLAUDE_AVISOS` | ia_claude.py:140 | `v = tuple(sorted({float(x) for x in (os.environ.get("PHYSIS_CLAUDE_AVISOS") or "0.8,1").split(",") if x.strip()}))` |
| `PHYSIS_CLAUDE_AVISO_EMAIL` | robos.py:1005 | `para = os.environ.get("PHYSIS_CLAUDE_AVISO_EMAIL") or ctx.get("suporte_email") or ""` |
| `PHYSIS_CLAUDE_CHAVE` | ia_claude.py:120 | `return (os.environ.get("PHYSIS_CLAUDE_CHAVE") or os.environ.get("ANTHROPIC_API_KEY") or "").strip()` |
| `PHYSIS_CLAUDE_CHAVE_ARQUIVO` | ia_claude.py:113 | `arq = (os.environ.get("PHYSIS_CLAUDE_CHAVE_ARQUIVO") or "").strip()` |
| `PHYSIS_CLAUDE_TETOS_ROBO` | ia_claude.py:126 | `extra = json.loads(os.environ.get("PHYSIS_CLAUDE_TETOS_ROBO") or "{}")` |
| `PHYSIS_CLAUDE_TETO_ROBO_USD` | ia_claude.py:132 | `outro = float(os.environ.get("PHYSIS_CLAUDE_TETO_ROBO_USD") or 3)` |
| `PHYSIS_CLIMA` | servidor.py:2861 (+1) | `if os.environ.get("PHYSIS_CLIMA", "1") != "0":     # PHYSIS_CLIMA=0 desliga as consultas (sem internet de propósito)` |
| `PHYSIS_CONFIRMAR_EMAIL` | seguranca.py:830 | `v = os.environ.get("PHYSIS_CONFIRMAR_EMAIL", "").strip()` |
| `PHYSIS_CONSENTIMENTO_ESTRITO` | seguranca.py:887 | `return os.environ.get("PHYSIS_CONSENTIMENTO_ESTRITO") == "1"` |
| `PHYSIS_CSRF_ESTRITO` | seguranca.py:1127 | `return os.environ.get("PHYSIS_CSRF_ESTRITO") == "1"` |
| `PHYSIS_CURSOS_PASTAS` | mv_cursos.py:30 | `env = os.environ.get("PHYSIS_CURSOS_PASTAS", "").strip()` |
| `PHYSIS_DOCS` | mv_bots.py:29 (+1) | `if os.environ.get("PHYSIS_DOCS"):` |
| `PHYSIS_DOC_CHAVE` | documentos_cliente.py:53 | `chave = os.environ.get("PHYSIS_DOC_CHAVE")` |
| `PHYSIS_DOC_EXTERNO` | documentos_cliente.py:40 | `if url and (not url.startswith(("http://", "https://")) or (not _local(url) and os.environ.get("PHYSIS_DOC_EXTERNO") != "1")):` |
| `PHYSIS_DOC_RETENCAO_DIAS` | documentos.py:1205 | `dias = float(os.environ.get("PHYSIS_DOC_RETENCAO_DIAS") or 180)` |
| `PHYSIS_DOC_TEMPO` | documentos_cliente.py:70 | `return float(os.environ.get("PHYSIS_DOC_TEMPO") or 120)` |
| `PHYSIS_DOC_URL` | documentos_cliente.py:39 | `url = (os.environ.get("PHYSIS_DOC_URL") or "").strip().rstrip("/")` |
| `PHYSIS_DOMINIO` | mv_bots_extra.py:496 | `dom = os.environ.get("PHYSIS_DOMINIO")` |
| `PHYSIS_DOMINIO_EMAIL` | hub.py:479 (+1) | `dominio = (os.environ.get("PHYSIS_DOMINIO_EMAIL") or "").strip().lower().lstrip("@")` |
| `PHYSIS_DWG2DXF` | servidor.py:113 | `exe = programa or os.environ.get("PHYSIS_DWG2DXF") or shutil.which("dwg2dxf")` |
| `PHYSIS_EDITAIS_ACESSO` | editais.py:435 | `v = os.environ.get("PHYSIS_EDITAIS_ACESSO")` |
| `PHYSIS_EDITAIS_AVISO_DIAS` | mv_bots_extra.py:91 (+1) | `aviso = _limite("PHYSIS_EDITAIS_AVISO_DIAS")` |
| `PHYSIS_EDITAIS_CSV` | mv_bots_extra.py:84 | `arq = Path(csv or os.environ.get("PHYSIS_EDITAIS_CSV") or (mv_bots.DOCS / "Sistema Physis" / "31_Editais" / "banco_editais.csv"))` |
| `PHYSIS_EDITAIS_PASTA` | servidor.py:803 | `pasta_editais = Path(os.environ.get("PHYSIS_EDITAIS_PASTA") or (Path(banco_da_instancia(instancia)).resolve().parent / "editais"))` |
| `PHYSIS_ENDERECO` | servidor.py:2886 | `endereco = os.environ.get("PHYSIS_ENDERECO") or "0.0.0.0"` |
| `PHYSIS_ENTREGAS` | servidor.py:270 | `saida = Path(os.environ.get("PHYSIS_ENTREGAS") or (raiz / "entregas"))` |
| `PHYSIS_ESTERMIC_ENDERECO` | estermic_servidor.py:447 | `endereco = endereco or os.environ.get("PHYSIS_ESTERMIC_ENDERECO") or "127.0.0.1"` |
| `PHYSIS_ESTERMIC_PORTA` | estermic_servidor.py:446 | `porta = int(porta or os.environ.get("PHYSIS_ESTERMIC_PORTA") or 8704)` |
| `PHYSIS_ESTERMIC_SENHA` | estermic_servidor.py:448 | `senha = os.environ.get("PHYSIS_ESTERMIC_SENHA") or None` |
| `PHYSIS_EXIGIR_LOGIN` | servidor.py:795 | `exige_login = bool(instancia.get("login")) or os.environ.get("PHYSIS_EXIGIR_LOGIN") == "1"` |
| `PHYSIS_EXPOSTO` | seguranca.py:124 | `if os.environ.get("PHYSIS_EXPOSTO") == "1":` |
| `PHYSIS_FILA_CONEXOES` | rede_http.py:19 | `request_queue_size = max(5, int(os.environ.get("PHYSIS_FILA_CONEXOES") or 128))` |
| `PHYSIS_FORNECEDORES_PASTA` | fornecedores.py:202 (+1) | `return Path(os.environ.get("PHYSIS_FORNECEDORES_PASTA") or (Path(banco).resolve().parent / "fornecedores-arquivos"))` |
| `PHYSIS_FROTA_PASTA` | frota.py:689 (+1) | `self.pasta = Path(pasta or os.environ.get("PHYSIS_FROTA_PASTA") or (RAIZ / "dados" / "frota-comprovantes"))` |
| `PHYSIS_GEMEO` | gemeo_painel.py:23 (+1) | `if os.environ.get("PHYSIS_GEMEO"):` |
| `PHYSIS_GESTAO_BANCOS` | mv_bots_extra.py:185 | `cfg = os.environ.get("PHYSIS_GESTAO_BANCOS", "")` |
| `PHYSIS_GESTOES_MAX_H` | mv_bots_extra.py:444 (+1) | `lim = _limite("PHYSIS_GESTOES_MAX_H")` |
| `PHYSIS_GIS_PONTO_URL` | gis.py:93 | `ponto = ler_ponto(self.buscar(os.environ.get("PHYSIS_GIS_PONTO_URL", URL_PONTO).format(par=par, lat=la, lon=lo)), par)` |
| `PHYSIS_GIS_REGIAO_URL` | gis.py:100 | `regiao = ler_regiao(self.buscar(os.environ.get("PHYSIS_GIS_REGIAO_URL", URL_REGIAO).format(` |
| `PHYSIS_HIDROGRAFIA` | gis.py:447 (+2) | `caminho = caminho or os.environ.get("PHYSIS_HIDROGRAFIA", "")` |
| `PHYSIS_HTTPS` | seguranca.py:108 | `if os.environ.get("PHYSIS_HTTPS") == "1":` |
| `PHYSIS_IA_CHAVE` | calc_cliente.py:140 (+1) | `chave = os.environ.get("PHYSIS_IA_CHAVE")` |
| `PHYSIS_IA_EXTERNO` | calc_cliente.py:135 (+1) | `if not url or (not destino_local(url) and os.environ.get("PHYSIS_IA_EXTERNO") != "1"):` |
| `PHYSIS_IA_MODELO` | ia_generativa.py:116 (+3) | `modelo = modelo or os.environ.get("PHYSIS_IA_MODELO") or "qwen2.5:7b"` |
| `PHYSIS_IA_MODO` | ia_generativa.py:155 (+1) | `if (modo or os.environ.get("PHYSIS_IA_MODO") or "generativa").lower() == "extrativa":` |
| `PHYSIS_IA_PASTAS` | ia_physis.py:96 | `extra = os.environ.get("PHYSIS_IA_PASTAS", "")` |
| `PHYSIS_IA_TEMPO` | ia_generativa.py:120 (+1) | `with abrir(req, timeout=float(os.environ.get("PHYSIS_IA_TEMPO") or TEMPO_LIMITE)) as r:` |
| `PHYSIS_IA_TIPO` | calc_cliente.py:138 (+1) | `caminho = "/api/tags" if os.environ.get("PHYSIS_IA_TIPO") == "ollama" or "/api/" in url else "/v1/models"` |
| `PHYSIS_IA_URL` | calc_cliente.py:134 (+4) | `url = (os.environ.get("PHYSIS_IA_URL") or "").strip().rstrip("/")` |
| `PHYSIS_INDICADORES_LENTO_MS` | indicadores.py:475 | `lento = float(os.environ.get("PHYSIS_INDICADORES_LENTO_MS") or 1500)` |
| `PHYSIS_INDICADORES_RETENCAO_DIAS` | indicadores.py:337 | `dias = float(os.environ.get("PHYSIS_INDICADORES_RETENCAO_DIAS") or 400) if dias is None else dias` |
| `PHYSIS_INOVASTEM_BANCO` | mv_inovastem.py:27 | `return Path(os.environ.get("PHYSIS_INOVASTEM_BANCO") or (RAIZ_REPO.parent / "clientes" / "physis-inovastem" / "physis-inovastem.db"))` |
| `PHYSIS_INSTANCIA` | hub.py:71 (+1) | `return json.loads(Path(os.environ.get("PHYSIS_INSTANCIA") or INSTANCIA_PADRAO).read_text(encoding="utf-8"))` |
| `PHYSIS_INTERCAMBIO_CHAVES` | servidor.py:837 | `os.environ.get("PHYSIS_INTERCAMBIO_CHAVES") or instancia.get("intercambio_chaves")` |
| `PHYSIS_INTERCAMBIO_ID` | servidor.py:836 | `hub, instancia.get("intercambio_id") or os.environ.get("PHYSIS_INTERCAMBIO_ID") or hub.org,` |
| `PHYSIS_INTERCAMBIO_LIMITE` | intercambio.py:200 | `lim = seg.ler_limite(os.environ.get("PHYSIS_INTERCAMBIO_LIMITE"), "120/600")` |
| `PHYSIS_IOT_MUDO_H` | mv_bots_extra.py:124 (+1) | `lim = _limite("PHYSIS_IOT_MUDO_H")` |
| `PHYSIS_LOJA_CATALOGO` | servidor.py:2823 | `arq = Path(caminho or os.environ.get("PHYSIS_LOJA_CATALOGO") or LOJA_CATALOGO_INICIAL)` |
| `PHYSIS_LOTE_DIARIO` | hub.py:756 | `if os.environ.get("PHYSIS_LOTE_DIARIO", "1").strip() == "0":` |
| `PHYSIS_LUGAR` | servidor.py:2851 | `lugar=os.environ.get("PHYSIS_LUGAR", inst.get("lugar", "lugar01")),` |
| `PHYSIS_MAPAS` | servidor.py:133 | `return Path(os.environ.get("PHYSIS_MAPAS") or (WEB.parent / "mapas"))` |
| `PHYSIS_MAPEAMENTO_PASTA` | mapeamento.py:993 | `self.pasta = Path(pasta or os.environ.get("PHYSIS_MAPEAMENTO_PASTA") or "mapeamento-arquivos")` |
| `PHYSIS_MARKETING_DADOS` | mv_bots_extra.py:341 (+1) | `pasta = Path(pasta or os.environ.get("PHYSIS_MARKETING_DADOS") or (mv_bots.DOCS / "Marketing Physis" / "dados"))` |
| `PHYSIS_MERCADO_ONLINE` | mv_ecossistema.py:250 | `online = (os.environ.get("PHYSIS_MERCADO_ONLINE", "1") != "0") if online is None else online` |
| `PHYSIS_MODELOS_PASTA` | documentos_auto.py:67 | `p = (os.environ.get("PHYSIS_MODELOS_PASTA") or "").strip()` |
| `PHYSIS_MV_BACKUP` | mv_bots.py:410 | `BACKUP_DIR = Path(os.environ.get("PHYSIS_MV_BACKUP") or (DOCS / "Sistema Physis" / "28_Physis_MV" / "backup"))` |
| `PHYSIS_MV_DADOS` | mv.py:88 | `p = Path(os.environ.get("PHYSIS_MV_DADOS") or (Path(__file__).resolve().parents[3] / "dados"))` |
| `PHYSIS_MV_GESTOES` | mv_bots_extra.py:423 | `p = Path(pasta or os.environ.get("PHYSIS_MV_GESTOES") or (mv_bots.DOCS / "Sistema Physis" / "28_Physis_MV" / "gestoes"))` |
| `PHYSIS_MV_NOS` | mv_bots.py:457 | `NOS_DIR = Path(os.environ.get("PHYSIS_MV_NOS") or (DOCS / "Sistema Physis" / "28_Physis_MV" / "nos"))` |
| `PHYSIS_MV_PORTA` | mv_servidor.py:46 | `PORTA = int(os.environ.get("PHYSIS_MV_PORTA") or 8710)` |
| `PHYSIS_MV_SAIDA` | mv_bots.py:50 | `SAIDA = Path(os.environ.get("PHYSIS_MV_SAIDA") or (DOCS / "Sistema Physis" / "28_Physis_MV"))` |
| `PHYSIS_NF_PROVEDOR` | documentos_auto.py:336 | `return EmissorAsaas() if os.environ.get("PHYSIS_NF_PROVEDOR") == "asaas" else EmissorNF()` |
| `PHYSIS_NOMINATIM_URL` | cep.py:87 | `base = os.environ.get("PHYSIS_NOMINATIM_URL", "").rstrip("/")` |
| `PHYSIS_NOTAS` | mv_financeiro.py:106 | `pasta = Path(pasta_notas or os.environ.get("PHYSIS_NOTAS") or (mv_bots.DOCS / "Sistema Physis" / "notas"))` |
| `PHYSIS_ORG` | servidor.py:2850 | `org=os.environ.get("PHYSIS_ORG", inst.get("org", "org-teste")),` |
| `PHYSIS_ORIGENS` | seguranca.py:1146 | `for extra in [url_publica] + (os.environ.get("PHYSIS_ORIGENS") or "").split(","):` |
| `PHYSIS_OVERPASS_URL` | residuos_gis.py:83 | `url = os.environ.get("PHYSIS_OVERPASS_URL", URL_OVERPASS)` |
| `PHYSIS_PEGADA` | pegada_servidor.py:173 | `env = os.environ.get("PHYSIS_PEGADA", "").strip()` |
| `PHYSIS_PG_HOST` | mv_bots_extra.py:490 (+2) | `if shutil.which("pg_isready") and os.environ.get("PHYSIS_PG_HOST"):` |
| `PHYSIS_PORTA` | servidor.py:2846 | `porta = int(os.environ.get("PHYSIS_PORTA", "8700"))` |
| `PHYSIS_PRIMEIRA_CONTA_EXTERNA` | servidor.py:2720 | `if not hub.tem_conta() and not self._local() and os.environ.get("PHYSIS_PRIMEIRA_CONTA_EXTERNA") != "1":` |
| `PHYSIS_PROXY_CONFIAVEL` | seguranca.py:72 | `bruto = os.environ.get("PHYSIS_PROXY_CONFIAVEL", "") if valor is None else valor` |
| `PHYSIS_PY` | camadas_bot.py:375 | `m = rodar([os.environ.get("PHYSIS_PY") or sys_executable(), str(ferr), "--ufs", ",".join(UFS_BR), "--camada", c,` |
| `PHYSIS_RAIZ_INSTITUTO` | mv_paginas.py:39 | `INSTITUTO = Path(os.environ.get("PHYSIS_RAIZ_INSTITUTO") or (Path(__file__).resolve().parents[3] / "instituto-physis"))   # ao lado do sistema` |
| `PHYSIS_RAIZ_SISTEMA` | mv_paginas.py:18 | `RAIZ = Path(os.environ.get("PHYSIS_RAIZ_SISTEMA") or Path(__file__).resolve().parents[2])` |
| `PHYSIS_REDE_LOCAL` | seguranca.py:129 | `redes = REDES_LOCAIS + tuple(proxies_confiaveis(os.environ.get("PHYSIS_REDE_LOCAL", "")))` |
| `PHYSIS_REPOSITORIOS` | mv_repositorios.py:32 | `env = os.environ.get("PHYSIS_REPOSITORIOS", "").strip()` |
| `PHYSIS_RX_URL` | servidor.py:792 (+1) | `rx = os.environ.get("PHYSIS_RX_URL")` |
| `PHYSIS_SAUDE_V6` | protocolo.py:53 | `return os.environ.get("PHYSIS_SAUDE_V6", "1").strip() != "0"` |
| `PHYSIS_SEGURANCA_CONTATO` | servidor.py:1891 | `txt = seg.security_txt(os.environ.get("PHYSIS_SEGURANCA_CONTATO") or os.environ.get("PHYSIS_SUPORTE_EMAIL")` |
| `PHYSIS_SIMULAR` | servidor.py:2856 | `sim = os.environ.get("PHYSIS_SIMULAR")` |
| `PHYSIS_SINCRO_REPOS` | mv_sincronizacao.py:26 (+1) | `REPOS = json.loads(os.environ["PHYSIS_SINCRO_REPOS"]) if os.environ.get("PHYSIS_SINCRO_REPOS") else {` |
| `PHYSIS_SMTP_HOST` | correio.py:25 (+2) | `return bool(os.environ.get("PHYSIS_SMTP_HOST"))` |
| `PHYSIS_SMTP_PORTA` | correio.py:32 | `porta = int(os.environ.get("PHYSIS_SMTP_PORTA", "587"))` |
| `PHYSIS_SMTP_REMETENTE` | correio.py:35 | `remetente = os.environ.get("PHYSIS_SMTP_REMETENTE", usuario)` |
| `PHYSIS_SMTP_SENHA` | correio.py:34 | `senha = os.environ.get("PHYSIS_SMTP_SENHA", "")` |
| `PHYSIS_SMTP_USUARIO` | correio.py:33 | `usuario = os.environ.get("PHYSIS_SMTP_USUARIO", "")` |
| `PHYSIS_SOFFICE` | documentos.py:514 | `return programa or os.environ.get("PHYSIS_SOFFICE") or shutil.which("soffice") or shutil.which("libreoffice")` |
| `PHYSIS_SUPORTE_CONTAS` | suporte_remoto.py:69 | `v = os.environ.get("PHYSIS_SUPORTE_CONTAS", "") if valor is None else valor` |
| `PHYSIS_SUPORTE_EMAIL` | servidor.py:813 (+3) | `"suporte_email": os.environ.get("PHYSIS_SUPORTE_EMAIL") or instancia.get("suporte_email") or ""})` |
| `PHYSIS_SUPORTE_REDES` | suporte_remoto.py:57 | `v = os.environ.get("PHYSIS_SUPORTE_REDES", "") if valor is None else valor` |
| `PHYSIS_SUPORTE_WHATSAPP` | servidor.py:2151 | `contatos = {"whatsapp": re.sub(r"\D", "", os.environ.get("PHYSIS_SUPORTE_WHATSAPP") or instancia.get("suporte_whatsapp") or ""),` |
| `PHYSIS_TERMOS_VERSAO` | seguranca.py:843 (+1) | `if os.environ.get("PHYSIS_TERMOS_VERSAO"):` |
| `PHYSIS_TOKEN` | servidor.py:2887 | `srv = iniciar(hub, porta, os.environ.get("PHYSIS_TOKEN"), endereco=endereco, clima=clima)` |
| `PHYSIS_TRILHAS` | mv_bots_extra.py:533 | `t = Path(trilhas or os.environ.get("PHYSIS_TRILHAS") or (base / "trilhas.json"))` |
| `PHYSIS_URL_PUBLICA` | servidor.py:801 | `url_publica = (os.environ.get("PHYSIS_URL_PUBLICA") or instancia.get("url_publica") or "").rstrip("/")` |
| `PHYSIS_VENTO_URL` | vento.py:94 | `d = ler_vento(self.b.buscar(os.environ.get("PHYSIS_VENTO_URL", URL_VENTO).format(lat=la, lon=lo)))` |
| `PHYSIS_WHATSAPP_PROVEDOR` | alertas_clima.py:188 | `p = (os.environ.get("PHYSIS_WHATSAPP_PROVEDOR") or "").strip().lower()` |
