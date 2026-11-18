# Serviços abertos incorporados ao Sistema Physis (servidor da Physis)

Decisão: estas ferramentas **fazem parte do sistema** e são instaladas/configuradas pelo próprio pacote
(`servicos/` na raiz do repositório), não uma lista de infraestrutura à parte. Todas são software aberto,
hospedado pela Physis (regra 11 do `CLAUDE.md`). Testes estáticos: `tests/test_implantacao.py`.

| Perfil | Serviço | Para quê | Licença |
|---|---|---|---|
| `hub` | Physis Hub | Site, loja, Gestão interna, plataforma | Physis |
| `caddy` | Caddy 2.8 | TLS (Let's Encrypt ou CA própria), HSTS, **única porta aberta** | Apache-2.0 |
| `mosquitto` | Mosquitto 2.0 | MQTT interno (hub ↔ Node-RED) | EPL/EDL |
| `nodered` | Node-RED 4.0 | Automações visuais (login obrigatório) | Apache-2.0 |
| `superset` | Apache Superset 4.0 + PostgreSQL (metadados) | BI no lugar do Power BI | Apache-2.0 |
| `bi` | PostGIS 16-3.4 + instantâneo + exportador | Dados do hub para BI e mapas | GPL-2 (PostGIS) / Physis |
| `geoserver` | GeoServer 2.25 | Camadas IBGE, MapBiomas, SINIR e do hub (WMS/WFS/GeoJSON) | GPL-2 |
| `series` | TimescaleDB 2.15 | Leituras de alto volume (opcional) | Apache-2.0 (edição TSL p/ compressão) |
| `calc` | Physis Calc (pvlib, windpowerlib, EnergyPlus, EPANET/wntr, SWMM/pyswmm) | Motores de cálculo | BSD/MIT/domínio público |
| `documentos` | LibreOffice headless + veraPDF 1.26 (Java 17) | ODT/ODS → PDF/A-2b e validação PDF/A | MPL-2.0 / GPLv3+ ou MPLv2+ |
| `ia` / `ia-vllm` | Ollama 0.3 / vLLM 0.6 | IA local (lista do Eric, parte G) | MIT / Apache-2.0 |

## Subir

```
cd servicos
sudo PHYSIS_DADOS=/srv/physis PHYSIS_PACOTE=/srv/pacotes/physis-servidor ./preparar.sh
#   edite .env (COMPOSE_PROFILES) e env/caddy.env (domínios, PHYSIS_TLS=<e-mail> para Let's Encrypt)
docker compose config -q
docker compose up -d --build
docker compose ps            # todos "healthy"
```

`preparar.sh` é idempotente: cria `env/*.env` (0600) a partir de `env/*.env.exemplo`, gera os segredos com
`python3 secrets` (os compartilhados saem iguais nos dois lados: leitura do BI, exportador, séries, chave do calc),
cria as pastas com os donos certos, gera o arquivo de senhas do Mosquitto (hash pelo `mosquitto_passwd` da imagem) e o
hash bcrypt do Node-RED (senha em `env/nodered.senha`: guarde no cofre e apague). `env/*.env` e `.env` ficam fora do Git.

## Rede (só o Caddy publica portas)

```
internet ──443──► caddy ─┬─ borda (interna) ─► hub:8700, nodered:1880, superset:8088, geoserver:8080
                          │
hub ── motores (interna) ─► calc:8710, documentos:8720, ia:11434         hub ── iot (interna) ─► mosquitto:1883 ◄─ nodered
superset/exportador/geoserver ── dados (interna) ─► postgis      superset ── meta ─► superset-db
exportador/superset ── series (interna) ─► timescaledb            instantaneo: sem rede nenhuma
saída para a internet (sem porta aberta): hub (clima, e-mail), geoserver (WFS em cascata), caddy (ACME)
```

- O Caddy tem IP fixo na rede `borda` (172.30.10.2) = `PHYSIS_PROXY_CONFIAVEL` do hub; o hub roda com
  `PHYSIS_EXPOSTO=1`, `PHYSIS_HTTPS=1` e chaves por aparelho (`docs/SEGURANCA.md`).
- Node-RED, Superset e a administração do GeoServer só abrem das redes em `PHYSIS_REDES_EQUIPE` (VPN/escritório),
  além do login de cada um. WMS/WFS de leitura do GeoServer ficam abertos.
- Contêineres com `no-new-privileges`; hub, calc, exportador e instantâneo com sistema de arquivos só leitura e
  `cap_drop: ALL`; healthcheck e `restart: unless-stopped` em todos.
- Mosquitto do servidor é **interno**. As Caixinhas falam com o Mosquitto do Pi do cliente; para ligar Pi ↔ servidor,
  use VPN (WireGuard) — expor MQTT na internet fica fora deste desenho.

## BI sem tocar no banco vivo (o desenho mais seguro)

1. `instantaneo` (sem rede, mesmo uid do hub) copia o banco com a API de backup do SQLite a cada `INSTANTANEO_MIN`
   (padrão: 1×/dia às `INSTANTANEO_HORA`), confere `integrity_check` e troca o arquivo de uma vez.
2. `exportador` lê **só o instantâneo** (`immutable`, somente leitura) e grava, com o papel `exportador`, uma **lista
   fechada** de tabelas sem dado pessoal: `bi.medicao`, `bi.leitura` (sem o texto da linha), `bi.comando`,
   `bi.clima_observado`, `bi.clima_aposta`, `geo.hub_lugar`. Contas, sessões, e-mails, Gestão, loja e **Saúde nunca
   saem** (nós de Saúde são filtrados). Incremental por `seq`.
3. Superset conecta como `bi_leitor` (só `SELECT`, transação somente leitura). `PREVENT_UNSAFE_DB_CONNECTIONS` impede
   ligar o Superset a arquivos SQLite.

Por que não montar o `.db` do hub no Superset: o hub usa WAL; um leitor com o arquivo montado só leitura falha ou
segura o checkpoint, e o BI enxergaria tabelas com dados pessoais.

**Séries (perfil `series`)**: a mesma ponte grava `medida` no TimescaleDB (hypertable, compressão após 30 dias).
Para quase tempo real, use `INSTANTANEO_MIN=15`.

## Mapas (GeoServer)

`servicos/exportador/camadas.json` lista as camadas: hub (PostGIS `geo.hub_lugar`, também em GeoJSON em
`${PHYSIS_DADOS}/camadas/hub/`), IBGE (biomas, vegetação, pedologia, geomorfologia, clima; shapefiles baixados para
`${PHYSIS_DADOS}/camadas/ibge/<tema>`, ou WFS em cascata), MapBiomas (GeoTIFF recortado) e SINIR. **As URLs estão
marcadas [CONFERIR]**: confira no portal de cada fonte, anote data e licença. Depois:

```
set -a; . env/geoserver.env; . env/postgis.env; set +a
docker compose run --rm -e GEOSERVER_ADMIN_USER -e GEOSERVER_ADMIN_PASSWORD -e GEOSERVER_LEITOR_SENHA \
    exportador python /app/configurar_camadas.py
```

(idempotente; pula o que ainda não tem arquivo). GeoJSON de qualquer camada: WFS com `outputFormat=application/json`.

## Motores de cálculo (`calc`)

API local (rede `motores`, sem internet), JSON in/out, `Authorization: Bearer $PHYSIS_CALC_CHAVE`:

| Rota | Motor | Entrada principal | Saída |
|---|---|---|---|
| `GET /saude` | — | — | quais motores estão instalados |
| `POST /pv` | pvlib (PVWatts) | `lat, lon, kwp, inclinacao?, azimute?, ghi? (8760), temp_ar` | horário kW, mensal e anual kWh, kWh/kWp |
| `POST /eolica` | windpowerlib | `curva [{v,kw}]` ou `turbina`, `altura_cubo, rugosidade`, `velocidades` ou `weibull {k,c}` | energia, fator de capacidade |
| `POST /termica` | EnergyPlus 24.2 | `clima` + `ambiente` (formato da Carga Térmica, com U/α/FS resolvidos), `epw?` | pico (W, BTU/h, TR) e perfil do dia de projeto; anual com `.epw` |
| `POST /rede-agua` | EPANET (wntr) | `nos, reservatorios, tubos` | pressões, vazões, velocidades |
| `POST /drenagem` | SWMM (pyswmm) | `area_ha, impermeabilidade_pct, declividade_pct, chuva` | vazão de pico, volume, coeficiente |

`?somente_entrada=1` (térmica, rede, drenagem) devolve o IDF/INP montado sem rodar o motor. Sem a biblioteca: 503;
entrada errada: 400; ocupado: 429. Nada de valor inventado: a térmica exige U, α e FS (a plataforma já os resolve);
a drenagem usa padrões do manual do SWMM marcados `[CONFERIR]` e avisa quais usou.
EnergyPlus entra na imagem com `--build-arg INSTALAR_ENERGYPLUS=1 EPLUS_URL=... EPLUS_SHA256=...` (URL e hash a conferir
na página de releases). Arquivos `.epw` em `${PHYSIS_DADOS}/epw`.

### Como o hub chama (conectores)

`servicos/hub-conectores/calc_cliente.py` — funções prontas (só `urllib`, com tempo-limite, **nunca obrigatórias**:
sem `PHYSIS_CALC_URL` ou com o serviço fora, devolvem `None` e o hub usa as contas próprias):

```python
from physis_hub import servicos_abertos as sa      # quando o arquivo for copiado para physis_hub/

sa.calc_saude()                                      # {"ok": True, "motores": {...}} ou None
sa.pv_horario(-15.8, -47.9, 5.0, temp_ar=25)         # dict ou None
sa.eolica(30, 0.1, curva=[...], weibull={"k": 2, "c": 6})
sa.termica(clima, ambiente)                          # mesmo formato de cargatermica.calcular
sa.rede_agua(nos, reservatorios, tubos)
sa.drenagem(2.0, 60, 1.0, {"total_mm": 50, "duracao_min": 60})
sa.ia_saude()                                        # True/False
```

Variáveis do hub: `PHYSIS_CALC_URL` (compose: `http://calc:8710`), `PHYSIS_CALC_CHAVE`, `PHYSIS_CALC_TEMPO`.
Só aceita destino da rede local/interna (igual a `robos.destino_local`), salvo `PHYSIS_CALC_EXTERNO=1`.
A IA já está ligada no hub por `physis_hub/robos.py` (`IALocal`): no compose, `PHYSIS_IA_URL=http://ia:11434` e
`PHYSIS_IA_TIPO=ollama` (vLLM: `http://ia-vllm:8000`, `PHYSIS_IA_TIPO=openai`, `PHYSIS_IA_CHAVE`=`VLLM_API_KEY`).

## Documentos: PDF/A com LibreOffice e veraPDF (`documentos`)

Serviço `servicos/documentos/` (rede `motores`, sem internet, porta 8720 interna, `Authorization: Bearer $PHYSIS_DOC_CHAVE`):

| Rota | O que faz |
|---|---|
| `GET /saude` | `{"soffice": bool, "verapdf": bool}` |
| `POST /pdfa/converter?extensao=odt\|ods[&validar=1]` | corpo = ODT/ODS; devolve o PDF/A-2b (mesmo filtro de `physis_hub/documentos.PDFA_FILTRO`). Com `validar=1`, cabeçalho `X-Physis-PDFA: conforme \| nao-conforme \| nao-validado` |
| `POST /pdfa/validar?perfil=2b` | corpo = PDF; resumo do relatório do veraPDF: `compliant`, `perfil` (ex.: "PDF/A-2B"), `regras_ok`, `regras_falhas`, `falhas` (cláusula, teste, ocorrências, descrição) |

Sem o programa: 503 (o hub segue: hoje `documentos.converter_pdfa` usa o `soffice` local via `PHYSIS_SOFFICE` e devolve 501 sem ele).
Conector pronto: `servicos/hub-conectores/documentos_cliente.py` (`doc_saude()`, `pdfa_converter(odf, "odt")`,
`pdfa_validar(pdf)`; só `urllib`, tempo-limite `PHYSIS_DOC_TEMPO`, devolve `None` sem `PHYSIS_DOC_URL` ou com o serviço fora).
Ligação sugerida em `converter_pdfa`: sem `soffice` local e com `PHYSIS_DOC_URL` → `pdfa_converter`; depois mostrar o
selo "PDF/A-2b conferido pelo veraPDF" ou as regras que falharam.

**Licenças.** veraPDF tem licença dupla GPLv3+ / MPLv2+; LibreOffice é MPL-2.0. Os dois rodam como **programas
separados, num contêiner separado**, chamados por linha de comando e falados por HTTP: nada deles é ligado (importado)
no código do hub. Ao redistribuir a imagem, leve os avisos de licença e o código-fonte (ou o link) de ambos.

**Build.** O veraPDF entra com `--build-arg VERAPDF_URL=<zip "greenfield" do instalador> --build-arg VERAPDF_SHA256=<sha256>`
(versão fixada em `VERAPDF_VERSAO`; URL, hash e nomes dos pacotes do `verapdf-auto-install.xml` a **conferir** na página
de downloads do veraPDF). Sem esses argumentos, a imagem sobe só com o LibreOffice e `/pdfa/validar` responde 503.

## IA local

`ia` (Ollama) fica só na rede interna. Para baixar um modelo, ligue a saída só durante o download:

```
docker network connect physis_saida physis-ia-1
docker compose exec ia ollama pull <modelo escolhido pela lista do Eric>
docker network disconnect physis_saida physis-ia-1
```

Defina `PHYSIS_IA_MODELO` no `env/hub.env`. GPU NVIDIA: descomente `deploy:` no compose (precisa do
nvidia-container-toolkit). `ia-vllm` serve um modelo já copiado para `${PHYSIS_DADOS}/ia-vllm/atual`.

## Cópia de segurança do servidor

Tudo vive em `${PHYSIS_DADOS}` (pastas do host). Banco do hub: o mesmo `implantacao/backup.sh` com
`--banco ${PHYSIS_DADOS}/hub/physis-hub.db` (cópia online, cifrada com `age`, giro 7/4/12, espelho `rsync`).
PostgreSQL (Superset, PostGIS, Timescale): `docker compose exec postgis pg_dump -U physis_admin -Fc physis` (idem para
os outros) cifrado com `age` no mesmo destino — o PostGIS é derivado do hub e pode ser refeito pelo exportador.
Node-RED: `${PHYSIS_DADOS}/nodered` (fluxos; credenciais cifradas com `NODERED_CREDENCIAIS_SEGREDO`, guarde-o no cofre).

## O que depende da máquina (Eric) e não foi verificado

- Nada aqui rodou num Docker de verdade: `docker compose config`, build das imagens, healthchecks, versões fixadas
  (imagens e `requirements.txt`) e a inicialização do Superset/GeoServer precisam ser conferidos na máquina.
- Motores: só a montagem das entradas (IDF/INP) e a API foram testadas; pvlib, windpowerlib, wntr, pyswmm e o
  EnergyPlus não estavam instalados aqui (os testes pulam). O IDF segue os campos do EnergyPlus 24.2 de memória: rodar
  um caso e comparar com a Carga Térmica da plataforma.
- Documentos: instalação automática do veraPDF (nomes dos pacotes IzPack), o formato do relatório `--format mrr`
  (o resumo foi testado com um XML de exemplo no formato documentado) e a conversão real pelo LibreOffice da imagem.
- Caminho do `bcryptjs` dentro da imagem do Node-RED (usado pelo `preparar.sh`) e o comando `set-database-uri` do Superset 4.0.
- DNS dos domínios, e-mail do Let's Encrypt, redes da equipe (VPN), GPU para a IA, URLs das camadas [CONFERIR].
