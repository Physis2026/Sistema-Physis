# Fornecedores e equipamentos

Banco de fornecedores da energia solar (outras áreas na Fase 2), atualizado **região por região**, com planilha,
catálogos e mapa na Gestão interna (só equipe) e a vista "Fornecedores na sua região" na aba Energia solar (cliente).
Servidor: `physis_hub/fornecedores.py`; telas: `sistema/physis-fornecedores.js`; testes: `tests/test_fornecedores.py`.

**Dono: Ryan (fornecedores).** A direção cuida da curadoria (aprovar, suspender) e decide o que fica público.

## O que se guarda

- **Fornecedor**: razão social, nome público, CNPJ (conferido pelos dígitos), site, abrangência (nacional, regional,
  estadual, local), regiões atendidas (UF e/ou município pelo código IBGE; "BR" = o país todo), local da sede
  (latitude e longitude digitadas) e raio de atendimento para quem é local, categorias, notas internas.
- **Contatos**: só com o consentimento da pessoa (LGPD). Só a equipe vê. "Apagar (pedido de exclusão)" remove.
- **Equipamentos** (planilha): categoria, marca, modelo, link da folha de dados e, quando há classe igual, o id da base
  `sistema/physis-equipamentos.json` (ex.: `fv-perc-144`, `inv-string-mono-3-6`). A categoria precisa bater com a da base.
- **Instalação e integração** não é fornecedor: liga-se o fornecedor aos **profissionais parceiros** (`PARCEIROS.md`).
- **Prazo de entrega e pedido mínimo**: por região, opcionais.
- **Preço**: opcional e **só com data, região e fonte** (cotação ou catálogo). Nada é inventado; sem data não aparece.
  O cliente só vê preço de **catálogo**; cotação é interna.
- **Arquivos**: catálogos e folhas de dados em PDF, PNG, JPEG ou WEBP, até 20 MB, conferidos pelo conteúdo, guardados
  no servidor (pasta `PHYSIS_FORNECEDORES_PASTA`) com o resumo SHA-256. Download só da equipe; o cliente só baixa o que a
  direção marcou como público.
- **Histórico**: toda mudança fica registrada (quem, quando, o quê), em cadeia de resumos como o registro do hub. Não dá
  para editar nem apagar o histórico, e ele não guarda nome, e-mail nem telefone de contato.

## Como manter em dia, região por região (Ryan)

1. Abrir a Gestão → **Fornecedores e equipamentos** → **Fila por região**. As regiões com fornecedor desatualizado vêm
   primeiro. "Desatualizado" = a última atualização da região passou do limite da premissa
   `fornecedores.dias_desatualizado` (padrão 90 dias, **status conferir**: a direção confirma o número).
2. Em cada região: **Pedir atualização** cria uma tarefa na Gestão para o Ryan (chave `gestao-physis:fornecedores-tarefas`).
3. Atualizar de um destes jeitos:
   - um fornecedor por vez: abrir **Detalhes**, conferir e clicar **Dados conferidos hoje** na região;
   - em lote: **Importar e exportar CSV** → **Exportar a região** → corrigir na planilha → **Conferir o arquivo** (nada é
     gravado; mostra o resumo SHA-256) → **Gravar importação**. Se uma linha tiver erro, nada é gravado.
4. Quando nenhum fornecedor da região fica desatualizado, a tarefa fecha sozinha ("feita").

Colunas do CSV (separador `;` ou `,`; decimal com vírgula ou ponto):
`cnpj; categoria; marca; modelo; equipamento_id; prazo_entrega_dias; pedido_minimo_brl; preco; preco_unidade; preco_data; preco_fonte; preco_fonte_ref`.
O fornecedor precisa estar cadastrado antes (pelo CNPJ). Preço exige unidade, data (AAAA-MM-DD, não futura) e fonte
(`cotacao` ou `catalogo`); a região do preço é a da importação. Cada importação guarda o resumo SHA-256 do conteúdo
(o mesmo com `;` ou `,` e com qualquer quebra de linha) e o SHA-256 do arquivo.

## O que o cliente vê (aba Energia solar)

"Fornecedores na sua região", pelo local de `localDaInstalacao()` (Início/Planejador/Monitoramento):

- primeiro quem atende o **município**; se ninguém, quem atende o **estado todo**; se ninguém, quem atende o **Brasil**.
  A tela diz qual desses valeu;
- por item do projeto: módulo e inversor escolhidos na aba (ou na Planta solar), estrutura, proteção, cabos, bateria (se
  houver autonomia) e instalação (link para os profissionais parceiros);
- só fornecedor **aprovado e ativo**; só nome, site, região, data da última atualização (e se está desatualizada),
  produtos, prazo, pedido mínimo, preço de catálogo com data e fonte e catálogo público;
- sem local: "local não informado — preencha no Início".

## Mapa (só equipe)

SVG próprio, sem fundo de terceiros e sem biblioteca nova (como o mapa da Economia circular). Mostra a sede de cada
fornecedor, o raio dos locais, as UFs atendidas (ponto da capital; o mapa não tem os polígonos das UFs), a faixa
"atende todo o Brasil" e as instalações dos clientes (verde-azulado = tem fornecedor no município; vermelho = não tem).
Filtros: abrangência, categoria e situação. A mesma informação vai em tabela (leitor de tela).
Endereço → coordenadas: digitar latitude e longitude. Busca automática de endereço só com **Nominatim hospedado pela
Physis** (Fase 2); nenhum serviço de terceiros.

## Fase 2

- Portal do fornecedor: o próprio fornecedor atualiza dados, catálogo e preço (com login e curadoria da Physis).
- Preço automático: leitura de tabela/catálogo do fornecedor (só com data e fonte, como hoje).
- Outras categorias: água (bombas, filtros, cisternas), AVAC e materiais de bioconstrução (`SEGMENTOS`).
- Nominatim hospedado para achar as coordenadas pelo endereço; polígonos das UFs e municípios no mapa (IBGE, offline).

## Limites

- A conferência dos dados é humana; o sistema só marca o que está velho.
- O mapa usa coordenadas aproximadas das capitais para as UFs.
- O cliente vê a lista; o pedido de compra continua fora da plataforma.

## Integração (colar; não aplicado)

> Os quatro arquivos novos já estão prontos e testados. O que falta é ligar nos arquivos dos outros (servidor, painel,
> aba Solar, Gestão, mapa de variáveis e premissas). Tudo abaixo é texto para colar.

### `physis_hub/servidor.py`

```python
# topo, junto dos outros módulos
from . import fornecedores as fornecedores_mod
# docstring do topo (lista de rotas)
#  /api/fornecedores…                                                fornecedores e equipamentos (FORNECEDORES.md)
# logo depois de "for _k, _v in ESQUEMAS_ROTAS.items(): seg.ESQUEMAS.setdefault(_k, _v)"
for _k, _v in fornecedores_mod.ESQUEMAS.items():
    seg.ESQUEMAS.setdefault(_k, _v)
# em modulo(nome), no dicionário
"fornecedores": lambda: fornecedores_mod.Fornecedores(hub, pasta=fornecedores_mod.pasta_padrao(banco_da_instancia(instancia))),
# GET (junto de /api/parceiros, antes de qualquer _barrado)
if p.startswith("/api/fornecedores"):
    qf = self._exigir(seg.CLIENTE)          # o módulo decide: cliente só /regiao e arquivo público; resto equipe
    if qf:
        cod, r = modulo("fornecedores").rota("GET", p, qf, None, q)
        if isinstance(r, tuple):                       # ("bytes", nome, tipo, dados): CSV ou catálogo
            self._enviar_bytes(r[3], r[2], {"Content-Disposition": "attachment; filename*=UTF-8''" + quote(r[1]),
                                            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
        else:
            self._json(cod, r)
    return True
# POST em _rotas_novas_post_grandes (CSV até 1 MB e arquivo até 20 MB passam de 64 KB); CSRF já conferido antes
if p.startswith("/api/fornecedores"):
    qf = self._exigir(seg.EQUIPE)
    if not qf or (p in ("/api/fornecedores/importar", "/api/fornecedores/arquivo") and self._limitado("arquivo")):
        return True
    corpo = self._corpo_grande(fornecedores_mod.ARQ_MAX + 64 * 1024)
    if corpo is None and (self.headers.get("Content-Length") or "0").strip() == "0":
        corpo = b"{}"
    if corpo is None:
        self._recusar_corpo("arquivo grande demais (máximo 20 MB)")
        return True
    if p.endswith("/apagar") and not self._sensivel(qf):     # apagar fornecedor: senha recente (só direção; o módulo confere)
        return True
    self._json(*modulo("fornecedores").rota("POST", p, qf, corpo, parse_qs(u.query)))
    return True
```

Esquemas (`fornecedores.ESQUEMAS`, estritos): `forn_cadastro`, `forn_editar`, `forn_regiao`, `forn_id`, `forn_equipamento`,
`forn_oferta`, `forn_preco`, `forn_contato`, `forn_curadoria`, `forn_arquivo_publico`, `forn_importar`, `forn_pedir`.
Limite por IP: categoria `arquivo` na importação e no upload. Pasta dos arquivos: `PHYSIS_FORNECEDORES_PASTA`
(padrão: pasta do banco + `/fornecedores-arquivos`; fora do Git e do pacote).

### Plataforma (`painel.html`) e aba Energia solar

- `ferramentas/embutir_bases.py`, em `MODULOS`: `"mod-fornecedores": S / "physis-fornecedores.js",  # Fornecedores na sua região (aba Solar)`
- `sistema/physis-solar.js`:
  ```js
  const SUBS_SOLAR = [["calculo", "Dimensionamento"], ["planta", "Planta solar (BIM)"], ["fornecedores", "Fornecedores na sua região"]];
  /* primeira linha de telaSolar(), antes do aviso de local (o módulo tem o seu "local não informado — preencha no Início") */
  if (subSolar() === "fornecedores") return TITULO_SOLAR + chipsSolar() + (window.FORNECEDORES ? FORNECEDORES.htmlSolar() : `<p class="faixa in" role="status">Fornecedores: módulo não instalado.</p>`);
  ```
  O módulo monta sozinho quando o `<div data-forn-solar>` aparece; lê `localDaInstalacao()`, `calcLer("solar")`,
  `physis-calc-planta-solar` e `window.SOLAR`. O botão "Ver profissionais parceiros" usa `data-aba="loja"`.

### Gestão interna (`gestao-interna-physis.html`)

- `ferramentas/sincronizar.py`: `"physis-fornecedores": RAIZ / "sistema" / "physis-fornecedores.js",  # fornecedores e equipamentos`
  (o mesmo `<script id="physis-fornecedores">` que os parceiros; o PhysisODF já está na Gestão).
- Menu: `["fornequip", "Fornecedores e equipamentos", null],` antes de `["parceiros", …]`; em `VISTAS` acrescentar
  `"fornequip"`; em `EN_MENU` `fornequip:"Suppliers and equipment"`; no mapa de foco `fornequip: "gr-fornequip"`; no CSS
  `html.gp:not(.gp-v-fornequip) #gr-fornequip, html.gp.gp-v-fornequip main#px-conteudo{display:none !important}`.
  (A aba antiga "Fornecedores e compras" (`forn`) continua: é a parte de compras do painel administrativo.)
- Em `garantir()`: acrescentar `["gr-fornequip", "gr-h-fornequip", null]` à lista; em `mostrar(id)`:
  `if (id === "fornequip") pintarFornequip();` e a função, igual à dos parceiros:
  ```js
  function pintarFornequip() {
    var s = document.getElementById("gr-fornequip"); if (!s || s._montado) return;
    var h = "<h1 id='gr-h-fornequip'>" + esc(L("Fornecedores e equipamentos", "Suppliers and equipment")) + "</h1>";
    if (!SRV || !window.FORNECEDORES || !window.FORNECEDORES.montarGestao) { s.innerHTML = h + semServidor(); return; }
    s.innerHTML = h + "<div id='fornecedores-gestao' class='gr-caixa'></div>"; s._montado = true;
    try { window.FORNECEDORES.montarGestao(document.getElementById("fornecedores-gestao")); }
    catch (e) { s.querySelector("#fornecedores-gestao").innerHTML = "<p class='gr-erro' role='alert'>" + esc(L("A tela de fornecedores não abriu.", "The supplier screen did not open.")) + "</p>"; }
  }
  ```
  As tarefas de "Pedir atualização" ficam na chave `gestao-physis:fornecedores-tarefas` (`{"_formato":
  "physis-fornecedores-tarefas/1", "tarefas":[{id, titulo, responsavel:"ryan", area:"fornecedores", regiao, prazo, estado}]}`);
  a lista de Atividades pode lê-la como as outras chaves.

### `sistema/physis-premissas.json` (premissa nova)

```json
{"id": "fornecedores.dias_desatualizado", "grandeza": "Dias até os dados de um fornecedor numa região ficarem desatualizados",
 "valor_padrao": 90, "unidade": "dias", "opcoes": [
   {"rotulo": "Mercado estável", "valor": 180, "quando": "regiões com poucos fornecedores e preço que muda pouco"},
   {"rotulo": "Padrão", "valor": 90, "quando": "revisão trimestral da fila do Ryan"},
   {"rotulo": "Mercado agitado", "valor": 30, "quando": "preço de módulo mudando todo mês"}],
 "fonte": "política interna da Physis (proposta; a direção confirma)", "status": "conferir",
 "nota": "Usado por physis_hub/fornecedores.py (premissa_dias); sem a base, 90."}
```

### `sistema/physis-variaveis.json` (variáveis novas; módulo `solar`, só equipe exceto a primeira)

```json
[{"id": "solar.fornecedores_regiao", "nome": {"pt": "Fornecedores na sua região", "en": "Suppliers in your region"}, "unidade": "lista",
  "tipo": "calculated", "modulo": "solar", "produtores": ["solar"], "origem": {"api": "GET /api/fornecedores/regiao"},
  "formula": "município → UF → Brasil (cada passo só se o anterior não tiver ninguém); só aprovado e ativo; campos públicos",
  "onde": [{"arquivo": "physis-hub/physis_hub/fornecedores.py", "linha": 1026, "simbolo": "na_regiao"},
           {"arquivo": "sistema/physis-fornecedores.js", "linha": 143, "simbolo": "montarSolar"}],
  "consumidores": [{"modulo": "solar", "tela": "Fornecedores na sua região", "necessario": false, "modo": "sugestao"}],
  "armazenamento": ["tabelas fornecedor*, banco do hub"], "frequencia": "quando a aba abre", "agregacao": "por item do projeto",
  "faixa": {"min": null, "max": null, "fonte": "—"}, "qualidade": ["desatualizado se a região passou de fornecedores.dias_desatualizado"],
  "lote": "nao", "premissas": ["fornecedores.dias_desatualizado"], "entradas": ["lugar.municipio_uf", "solar.modulo", "solar.inversor"]},
 {"id": "fornecedores.ultima_atualizacao_regiao", "nome": {"pt": "Última atualização do fornecedor na região", "en": "Supplier's last update in the region"},
  "unidade": "data", "tipo": "typed", "modulo": "solar", "produtores": ["solar"], "origem": {"campo": "Gestão · Fornecedores e equipamentos (região, CSV)"},
  "formula": null, "onde": [{"arquivo": "physis-hub/physis_hub/fornecedores.py", "linha": 282, "simbolo": "desatualizado"}],
  "consumidores": [{"modulo": "solar", "tela": "Fornecedores na sua região", "necessario": false, "modo": "automatico"}],
  "armazenamento": ["tabela fornecedor_regiao.atualizado"], "frequencia": "quando a equipe confere ou importa", "agregacao": "por fornecedor e região",
  "faixa": {"min": null, "max": null, "fonte": "—"}, "qualidade": [], "lote": "nao", "premissas": ["fornecedores.dias_desatualizado"], "entradas": []},
 {"id": "fornecedores.preco", "nome": {"pt": "Preço de fornecedor (com data, região e fonte)", "en": "Supplier price (with date, region and source)"},
  "unidade": "R$ por unidade informada", "tipo": "typed", "modulo": "solar", "produtores": ["solar"], "origem": {"campo": "Gestão · preço ou CSV"},
  "formula": null, "onde": [{"arquivo": "physis-hub/physis_hub/fornecedores.py", "linha": 285, "simbolo": "validar_preco"}],
  "consumidores": [{"modulo": "solar", "tela": "Fornecedores na sua região (só catálogo)", "necessario": false, "modo": "sugestao"}],
  "armazenamento": ["tabela fornecedor_preco"], "frequencia": "quando a equipe registra", "agregacao": "por oferta e região",
  "faixa": {"min": 0, "max": null, "fonte": "> 0"}, "qualidade": ["sem data, região ou fonte não entra nem sai"], "lote": "nao", "premissas": [], "entradas": []}]
```
(Conferir as linhas com `tests/test_variaveis.py` depois de colar; os símbolos existem nos arquivos.)