# Intercâmbio de dados entre plataformas

Versão de 18/11/2026.

## Em uma frase

A plataforma da Physis Engineering troca **conjuntos de dados combinados** com uma plataforma parceira (o Instituto
Physis ou qualquer outra instalação Physis) **sem dividir banco**: cada lado guarda o que é seu e só recebe o que a
direção dele aprovar.

Decisão de 18/11/2026: tudo o que é do Instituto Physis (a instalação dele e o Physis 3D) saiu deste sistema e foi para
o repositório próprio do Instituto. O que liga as duas plataformas agora é só este intercâmbio.

## Como funciona (passo a passo)

1. **Cada lado cadastra o outro** (Minha conta → "Intercâmbio com outras plataformas", só a direção):
   - **identificador** da outra plataforma (o `intercambio_id` dela; ex.: `instituto-physis`);
   - **nome** e **endereço** (`https://…`, ou o IP da VPN, como `http://100.101.1.2:8700`);
   - **o que esta instalação envia** e **o que aceita receber** (marcando os conjuntos).
2. **Chave combinada**: um lado clica em "Gerar chave nova" (a chave aparece **uma vez só**), passa ao outro lado por um
   canal seguro, e o outro cola em "Chave recebida do parceiro". A chave fica **só no arquivo de chaves do servidor**,
   nunca no código, nunca no banco, nunca no registro.
3. **Trocar**: "Puxar do parceiro" (pede os dados) ou "Enviar ao parceiro" (manda os dados). Os dois sentidos funcionam.
4. **Aprovar**: o que chega fica em "Chegou e espera aprovação". Só depois que a direção aprova é que os dados aparecem
   (`GET /api/intercambio/recebidos`, para a equipe).
5. **Registro**: tudo (cadastro, chave definida, envio, recebimento, recusa, aprovação) fica no registro encadeado do hub
   (tipo `intercambio`), com quantidades e resumos SHA-256, **sem o conteúdo** dos registros.

## Conjuntos de dados (lista de permissão)

Só saem os campos da lista. Campo pessoal só sai **com consentimento** marcado no registro (LGPD); sem ele, o campo é
retirado no envio e, se chegar sem consentimento, o registro é recusado.

| Conjunto | Campos que podem sair | Campos pessoais (só com consentimento) | De onde vem |
|---|---|---|---|
| `cursos_catalogo` | nome, descricao, link, gratuito, carga_horas, idioma, area, nivel | instrutor | os `cursos` do `instancia.json` |
| `projetos_resumo` | titulo, resumo, area, municipio, uf, situacao, ano, indicadores | cliente, responsavel | publicados pela direção (`POST /api/intercambio/publicar`) |
| `pecas_biblioteca` | nome, descricao, licenca, material, arquivo_nome, arquivo_sha256, arquivo_bytes, url, versao | autor_publico | publicados (a biblioteca 3D é do Instituto: a Physis recebe os dados e o SHA-256 do arquivo, não o arquivo) |
| `lotes_integridade` | lote, periodo_ini, periodo_fim, quantidade, fechado_em, resumo_lote | responsavel | tabela `integridade_lote` (docs/INTEGRIDADE_DADOS.md) |

Também é recusado: campo fora da lista, e-mail, CPF ou CNPJ escondido num campo aberto, link que não seja `https://`,
registro maior que 16 kB, pacote maior que 4 MB ou com mais de 2.000 registros.

## O contrato (`physis-intercambio/1`)

```
pacote   = {"esquema": "physis-intercambio/1", "origem", "destino", "dataset", "gerado_em", "registros": [...]}
registro = {"dataset", "id", "origem", "dados": {...}, "sha256"}
sha256   = SHA-256 do JSON canônico (chaves em ordem, sem espaços, UTF-8) de {dataset, id, origem, dados}
```

Qualquer plataforma que siga este contrato pode trocar dados com a Physis. O código é aberto
(`physis-hub/physis_hub/intercambio.py`, só biblioteca padrão do Python).

## Segurança

- **Assinatura** de cada pedido: `HMAC-SHA256(chave, esquema \n método \n caminho \n momento \n nonce \n SHA-256 do corpo)`,
  nos cabeçalhos `X-Physis-Origem`, `X-Physis-Momento` (segundos Unix), `X-Physis-Nonce` e `X-Physis-Assinatura`.
- **Sem repetição**: momento fora de ±5 minutos ou nonce já usado = recusado (`401` / `409`).
- **Resposta assinada** com o nonce do pedido: quem puxa confere que a resposta veio mesmo do parceiro.
- **Limites**: 120 pedidos a cada 10 minutos por parceiro (`PHYSIS_INTERCAMBIO_LIMITE`, ex.: `120/600`); 20 falhas de
  assinatura em 10 minutos bloqueiam o endereço.
- **Transporte**: só HTTPS ou rede local/VPN (endereço privado ou `100.64.0.0/10`). Sem HTTPS, o endereço do parceiro tem
  de ser um IP da rede local ou da VPN. As redes da VPN entram em `PHYSIS_REDE_LOCAL` (docs/SEGURANCA.md).
- **Só a direção** cadastra, gera chave, troca e aprova. Gerar ou remover chave pede a senha de novo (reautenticação).

## Rotas

Da outra plataforma (sem sessão; vale a assinatura e a lista do parceiro):

    GET  /api/intercambio/v1/oferta                 o que esta instalação envia e recebe deste parceiro
    GET  /api/intercambio/v1/dados/<conjunto>       pacote (puxar); ?desde=<segundos Unix> para só o que mudou
    POST /api/intercambio/v1/receber/<conjunto>     pacote (empurrar); fica pendente

Da direção (com sessão; `recebidos` também para a equipe):

    GET  /api/intercambio/estado | recebidos?dataset= | publicados?dataset=
    POST /api/intercambio/parceiro | parceiro/chave | parceiro/remover
    POST /api/intercambio/publicar | publicado/remover
    POST /api/intercambio/testar | puxar | enviar | revisar

## Configuração do servidor

| Variável ou campo | Padrão | Para quê |
|---|---|---|
| `PHYSIS_INTERCAMBIO_ID` ou `"intercambio_id"` no `instancia.json` | o `org` da instalação | Identificador desta plataforma (o parceiro cadastra com este nome) |
| `PHYSIS_INTERCAMBIO_CHAVES` ou `"intercambio_chaves"` | `intercambio-chaves.json` ao lado do banco | Arquivo das chaves (permissão 600; fora do Git; entra na cópia de segurança) |
| `PHYSIS_INTERCAMBIO_LIMITE` | `120/600` | Pedidos por parceiro por janela (segundos); `0` desliga |

## Testes

`physis-hub/tests/test_intercambio.py`: dois hubs de verdade no mesmo processo. Confere a troca assinada, a importação
pendente até a aprovação, o campo pessoal que não sai sem consentimento, a recusa de chave errada, de momento fora da
janela, de nonce repetido e de conjunto fora da lista, o registro alterado (SHA-256), o papel da direção e que a chave não
fica no banco.

## O que falta ([MARCADOR])

- Combinar com o Instituto o identificador, o endereço e quais conjuntos cada lado envia e recebe.
- Tela para publicar `projetos_resumo` e `pecas_biblioteca` (hoje pela rota `POST /api/intercambio/publicar`).
- Troca automática agendada (hoje é pelo botão).
