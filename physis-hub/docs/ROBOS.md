# Robôs da Physis (`physis_hub/robos.py`)

Uma base comum (`Robo`) e seis robôs que **já funcionam por regras, sem internet**. A IA local entra depois,
pelo mesmo gancho, sem mudar as telas.

## 1. Formato de toda resposta

```json
{"ok": true, "robo": "suporte", "intencao": "exportar", "resposta": "texto em português",
 "fontes": [{"fonte": "docs/APPS.md", "secao": "...", "trecho": "...", "semelhanca": 0.31}],
 "confianca": 0.31, "revisao_humana": true, "dados": {}, "ia": {"usada": false}}
```

`revisao_humana: true` = mostrar o selo "Conferir antes de usar". Erro de pedido: `{"ok": false, "erro": "..."}` (HTTP 400).

## 2. Robôs

| Robô | Pedido (`POST /api/robos/<nome>`) | O que devolve | Situação |
|---|---|---|---|
| `suporte` | `{"pergunta", "abrir_chamado"?: true, "contato"?}` | Resposta tirada da documentação (`docs/*.md`, menos as notas internas), da explicação de cada módulo do hub e do curso PHY-INTRO do painel, por TF-IDF e cosseno, citando [n]. Confiança < 0,15 (ou só 1 palavra em comum): sugere chamado em `dados.escalar`; com `abrir_chamado`, abre pelo `hub.suporte_abrir` | Completo por regras |
| `precos` | `{"itens": [{"descricao","preco"}], "referencias"?: [{"descricao","min","max"}], "historico"?: [{"descricao","preco"}]}` | Cada item com `situacao` (`ok`, `acima`, `abaixo`, `sem_referencia`), `faixa`, `mediana`, `desvio_pct` e as referências achadas (semelhança ≥ 0,35). Faixa: min/max informados; senão Tukey (Q1 − 1,5·IQR a Q3 + 1,5·IQR) com 4+ preços; senão −30 %/+40 % da mediana. Também usa os preços do catálogo da loja do hub | Completo; fica melhor com o histórico de propostas da Gestão |
| `editais` | `{"editais"?: [...], "aceitos"?: [{"titulo","resumo"}], "hoje"?}` (sem `editais`, usa a lista guardada pelo coletor) | Ranking com nota 0–100 = 60 % semelhança (perfil Physis e editais aprovados antes) + 40 % regra de `editais.relevancia`; prazo vencido = 0; `motivos` em texto | Completo por regras |
| `marketing` | `{"temas": [...como na Gestão], "metricas": [{"tema_id" ou "tema" ou "area", "impressoes", "engajamentos" ou curtidas/comentarios/...}]}` | Taxa de engajamento esperada por tema (Beta-Binomial: começa na média geral com peso de 100 impressões; métricas de outros temas da mesma área contam 30 %), intervalo de 90 %, "pouco testado", e `nota_final` = metade a nota da Gestão (`nota()`), metade a aprendida | Completo; a redação dos posts é da IA local |
| `projetos` | `{"edital": {"titulo","resumo","prazo"?,"valor_max"?,"duracao_meses"?}}` | Esqueleto do projeto em 11 seções (objetivos, metodologia Mapear/Modelar/Checar/Documentar, metas e indicadores por área, cronograma, orçamento por rubrica, riscos), com `[A PREENCHER]` e `pendencias`. Sempre `revisao_humana` | Esqueleto completo; o texto corrido é da IA local |
| `pluviometro` | `{"dados": {"no","lat","lon","municipio","uf","pino","placa"?,"mm_por_pulso"?,"intervalo_s"?,"hub_url"?,"nome"?}}` | YAML do ESPHome (`dados.yaml`), `secrets.yaml` de exemplo, cadastro no hub e avisos de ligação. Recusa pinos de boot/flash/serial; avisa pull-up externo nos GPIO 34–39 | Gera o arquivo; **precisa do hardware e da mudança TIPO:PLUV abaixo** |
| `auto` | `{"pergunta"}` | Escolhe o robô pelas regras de intenção (preço, pluviômetro, edital, marketing, projeto; senão suporte) | — |

## 3. IA local (servidor de IA da Physis)

Desligada sem `PHYSIS_IA_URL`. Variáveis:

| Variável | Para quê |
|---|---|
| `PHYSIS_IA_URL` | `http://ia-physis:8000` (OpenAI: chama `/v1/chat/completions`) ou `http://ia-physis:11434/api/generate` (Ollama) |
| `PHYSIS_IA_MODELO` | nome do modelo no servidor (padrão `physis`) |
| `PHYSIS_IA_TEMPO` | tempo máximo em segundos (padrão 30) |
| `PHYSIS_IA_TIPO=ollama` | força o formato Ollama |
| `PHYSIS_IA_CHAVE` | se o servidor exigir `Authorization: Bearer` |
| `PHYSIS_IA_EXTERNO=1` | só se o servidor estiver fora da rede local (sem isso, endereço público é recusado) |

Garantias: só rede local por padrão; e-mail, CPF, CNPJ, telefone, CEP, coordenadas, links e nomes informados
são trocados por `[e-mail]`, `[pessoa]` etc. antes de sair; o log e `REGISTRO_IA` guardam só robô, tipo, bytes,
tempo e ok; se a IA falhar ou demorar, vale a resposta por regras (`ia.usada = false`).

Hoje a IA é usada (quando ligada) para: redigir a resposta do **suporte** a partir dos trechos achados e
redigir o roteiro do **projetos** (esboço de projeto). Os outros robôs devolvem números e não dependem dela.

## 4. Rotas (colar em `servidor.py`)

No topo: `from . import robos as robos_mod`. Em `criar_manipulador`, depois de `editais_col`:

```python
    robos = robos_mod.criar_robos({"hub": hub, "editais": editais_col,
                                   "suporte_email": os.environ.get("PHYSIS_SUPORTE_EMAIL") or instancia.get("suporte_email") or ""})
```

`do_GET`:

```python
            if u.path == "/api/robos":
                if not self._sessao_ou_401():
                    return
                return self._json(200, {"ok": True, "robos": robos_mod.listar(robos)})
```

`do_POST` (depois de `corpo = self._corpo()`):

```python
            if u.path.startswith("/api/robos/"):
                q = self._sessao_ou_401()
                if not q:
                    return
                try:
                    d = json.loads(corpo or "{}")
                except ValueError:
                    return self._json(400, {"ok": False, "erro": "json invalido"})
                nome = u.path.rsplit("/", 1)[-1]
                d = d if isinstance(d, dict) else {}
                d["_quem"] = q["usuario"]                  # quem abre o chamado do suporte (vem da sessão, nunca do corpo)
                cod, r = robos_mod.atender(nome, d, robos)
                return self._json(cod, r)
```

## 5. Onde cada robô aparece (telas)

| Robô | Onde | Como |
|---|---|---|
| suporte | Painel **e** Gestão → **Suporte Physis**, acima do formulário de chamado | Caixa "Pergunte antes de abrir um chamado". Mostrar `resposta`, as `fontes` como notas [n] e, se `dados.escalar`, o botão "Abrir chamado com esta pergunta" (reenviar com `abrir_chamado: true`) |
| precos | Gestão → **Propostas** (cada proposta) | Botão "Conferir preços": envia os itens da proposta + `historico` = itens das propostas aceitas; pinta a linha (acima = vermelho, abaixo = âmbar, sem referência = cinza) com a faixa no `title` |
| editais | Gestão → **Editais** | Coluna "Nota Physis" e ordenação por ela; `motivos` no detalhe. `aceitos` = editais marcados como aprovados |
| marketing | Gestão → **Marketing → Temas** | Coluna "Engaja ~x %" e "nota final"; selo "pouco testado". As métricas vêm da aba de métricas que a Gestão já tem |
| projetos | Gestão → **Editais** (botão "Esboçar projeto" no edital) | Abre o esqueleto em seções editáveis, com as `pendencias` como lista de conferência; selo de revisão sempre |
| pluviometro | Painel → **Monitoramento verde → Acrescentar pluviômetro** (e Gestão → Manutenção) | Formulário (nó, pino, placa, lugar já preenchido) → botões "Baixar YAML" e "Baixar secrets de exemplo" + avisos |

## 6. TIPO:PLUV (pluviômetro de báscula) — feito no hub em 15/11/2026

Situação: itens 1 a 5 abaixo feitos no servidor (`protocolo.py`, `adaptador.py`, `nucleo.py`, `hub.py`, `clima.py`,
`alertas_clima.py`; testes em `tests/test_pluviometro_saude.py`). Falta: `physis-nucleo.js` (grandezas `chuva` e
`chuva_intensidade`, com a integração das telas), os dois `protocolo.cpp` e o pluviômetro físico (calibração).

Linha V6: `ID:31,TIPO:PLUV,CHI:0.20,PUL:44,BAT:-,TS:1794600000`

| Chave | Significado |
|---|---|
| `CHI` | mm de chuva no intervalo (pulsos × mm por pulso; padrão 0,2794 mm, calibrar com 1 L medido) |
| `PUL` | pulsos desde que o aparelho ligou (para conferir perda de linhas) |

Mudanças para o hub aceitar (fazer junto, como manda `EXTENSAO_V6.md`):
1. `protocolo.py`: `TIPOS_CONHECIDOS += ("PLUV",)` e chaves `CHI` (0–200) e `PUL` (inteiro ≥ 0).
2. `adaptador.py`: `TIPOS["PLUV"]`; `interpretar` lê `chi`/`pul`; `adaptar` gera grandeza `chuva` (ativo `<lugar>-noXX`).
3. `nucleo.py`: `FAIXAS["chuva"] = (0, 200, "mm")` e entra em `GRANDEZAS_NOVAS` (e no `physis-nucleo.js`).
4. Hub: soma do `CHI` do dia → `clima.observar(dia, "physis", mm)` (o pluviômetro do lugar vale mais que o CEMADEN no placar e no modelo de chuva).
5. `EXTENSAO_V6.md` e `PROTOCOLO.md`: linha nova na tabela.

O YAML gerado manda a linha por `POST /api/v6/linha` (como a Caixinha, `firmware_ref/no_wifi_v6`), usa
`pulse_counter` sem PCNT com filtro de 50 ms (a báscula quica), `sntp` para o `TS` e `!secret` para Wi-Fi e OTA.
Conferir a sintaxe `http_request.post` com a versão do ESPHome instalada (`request_headers` desde 2024.8).
