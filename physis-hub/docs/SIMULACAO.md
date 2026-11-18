# Simulação (Fase 1)

Contas leves que rodam **no servidor** (Python, para relatórios e testes) e **no navegador, sem internet** (JavaScript), com o mesmo resultado. Pedido de 15/11/2026: tudo o que roda leve entra já na Fase 1; o que é pesado fica para a Fase 2, em contêiner Linux.

**Regra de ouro:** todo resultado traz o método, as hipóteses, as premissas usadas, o tamanho da malha ou grade e os limites de validade, e o aviso: *pré-dimensionamento para revisão do engenheiro; não aprova projeto*. Número que falta vira `[MARCADOR]`, e a conta para em vez de inventar.

## Onde está

| Arquivo | O que é |
|---|---|
| `physis-hub/physis_hub/simulacao/` | Motor em Python: `termica`, `estrutura`, `fluidos`, `terreno`, `incerteza`, `qubo`, `biogas`, `comum`, `casos`, `integracao`; `rota()` para o servidor |
| `sistema/physis-simulacao.js` | O mesmo motor no navegador (`window.SIMULACAO`), a aba `telaSimulacao()` e os cartões `SIMULACAO.painel(tipo, entrada)` para outras abas |
| `sistema/physis-simulacao-premissas.json` | Premissas novas, todas com status "conferir" |
| `sistema/simulacao-exemplos/` | Casos comuns: exemplos (dados fictícios) e testes analíticos, em `casos.json` e `casos.js` |
| `ferramentas/testes-navegador/conferir-simulacao.html` | Roda todos os casos no navegador e mostra passou/falhou e os desenhos |
| `physis_hub/simulacao/conteiner/` | Adaptador da trilha quântica (só roda em contêiner com Qiskit) |

Atualizar os casos depois de mudar uma conta: `cd physis-hub; python -m physis_hub.simulacao.casos --gravar` (também copia as premissas para dentro do JS). Depois abrir a página de conferência: tem de dar **TUDO OK**.

## O que cada método faz e quem usa

### 1. Calor
- **U de parede ou cobertura** (`termica.u_valor`, `u_composicao`): soma das resistências das camadas, com Rsi e Rse de premissa (iguais às da base de materiais). Também dá capacidade térmica, massa e carbono por m². Propriedades sempre da `physis-materiais.json`. Usos: Bioconstrução (taipa, adobe, BTC, cob, pau a pique, fardo de palha, cânhamo-cal, telhado verde), AVAC (a envoltória entra na carga: `perda_envoltoria`), Secador (câmara), SbN (telhado verde).
- **Parede ao longo do dia** (`transiente_1d`): diferenças finitas com passo implícito, explícito ou Crank-Nicolson. Com sol senoidal dá o **atraso térmico** e o **amortecimento**. Teste: decaimento contra a solução exata.
- **Corte 2D** (`placa_2d`): ponte térmica (pilar na parede); um polígono vira máscara com `mascara_de_segmentos`. Teste: placa quadrada contra a série de Fourier.
- **Convecção e radiação** por coeficientes de premissa (`h_conveccao_vento`, `h_radiacao`, `sol_ar`).

### 2. Estrutura (linear)
- **Treliça e pórtico 2D e 3D** (`estrutura.portico`): barra e viga de Euler-Bernoulli, apoios, cargas nos nós, carga distribuída, peso próprio. Saídas: deslocamentos, reações, normal, cortante, momento, torção e tensão.
- **Flambagem de Euler** (`euler`), **verificação** (`verificar`: tensão ≤ fy/FS e compressão ≤ Pcr/FS; sem fy vira `[MARCADOR]`).
- **Chapa 2D com triângulos CST** (`cst`, `malha_de_mascara`) para chapas e cortes de peças.
- **Vento**: só o método da pressão dinâmica é nomeado (ABNT NBR 6123); V0, S1, S2, S3 e Cf são digitados `[CONFERIR NA NORMA]`. **Rotor**: empuxo pelo disco atuador.
- Usos: suporte das placas (Solar), pérgolas e estruturas de bambu e madeira (Bioconstrução, com E de ensaio), torre e pá em balanço (Turbinas) e viveiro e estufa (SbN).

### 3. Fluidos simplificados
- **Redes de tubos e dutos: não duplicadas.** Tubos: `vento.perda_darcy`/`perda_hazen` (Turbinas); dutos: aba AVAC; calhas: `PhysisCalc.calhas`.
- **Ventilação natural** (`ventilacao_natural`): chaminé e vento com Cd e ΔCp de premissa. Usos: AVAC, Bioconstrução, Secador.
- **Lattice-Boltzmann D2Q9** (`lbm`): **qualitativo, Fase 1** — mostra esteira e aceleração do vento num corte de casa ou no secador. Nunca dá número de projeto.
- **Turbina com série de vento** (`eolica_serie`): reusa as contas de `vento.py` / `physis-turbinas.js` (curva, Weibull).

### 4. Terreno e água
- Declividade e aspecto (Horn), **D8** e acumulação, **SCS-CN** (enxurrada de um evento, CN por uso do solo de premissa), **USLE** (perda de solo; R, K, C, P digitados), **visada**.
- Grade de entrada: a do contrato do Mapeamento `physis-geometria-lugar/1` (`grade_da_geometria`) ou a `.asc` recortada (`grade_do_mapeamento`).
- Usos: Mapeamento, Resiliência (enxurrada, encosta), Água (onde captar), SbN (onde plantar, valas em nível, jardim de chuva).

### 5. Monte Carlo
- `monte_carlo(entradas, modelo)`: normal, uniforme, triangular, lognormal → média e percentis. Modelos prontos: `carbono`, `solar`, `payback`, `biogas`. Gerador mulberry32 (igual nos dois lados; o `random` do Python não teria espelho no navegador), semente fixa nos testes.

### 6. Otimização em QUBO (trilha quântica)
- Problemas pequenos: **placas sob sombra** (`paineis`), **caminho de tubo na grade** (`rota`, conferido com Dijkstra), **topologia grossa de peça 2D** (`topologia`, heurística).
- Resolvidos **agora no clássico**: exato (até 20 variáveis) ou recozimento simulado.
- `exportar()` grava o JSON `physis-qubo/1` (com a forma de Ising) para `conteiner/qubo_qiskit.py`, que só roda dentro de um contêiner Linux com Qiskit. O hub nunca importa qiskit (há teste).
- **Dito claramente:** solução quântica é pesquisa (P&D). Em simulador cabem cerca de 20 a 30 variáveis, que o clássico resolve na hora. Ela precisa dar o mesmo ótimo do clássico e **nunca entra em relatório nem certificação**.

### 7. Biogás (Economia circular)
- Por substrato: ST, SV, BMP e fração de CH₄ (premissa `sim.biogas.substratos`, "conferir"; "outro" sem valor = `[MARCADOR]`).
- Cinética de 1ª ordem com k(T) = k_ref·θ^(T − T_ref); fração do BMP no TRH (mistura completa ou fluxo pistonado). TRH longo → BMP.
- Regime psicrofílico, mesofílico, termofílico ou **sem aquecimento**, com a temperatura mensal **do local da instalação** (`hub.local_da_instalacao` + NASA POWER). Sem local, a conta para: nunca usa um padrão.
- Saídas: biogás e CH₄ por dia e por mês (365 dias), dimensionamento do volume, carga orgânica e avisos (sobrecarga, TRH curto, frio, H₂S e segurança), energia térmica e elétrica, GLP equivalente, horas de queimador, **P, Q, S e fator de potência do gerador**, CO₂e evitado (GLP pela mesma regra do `carbono.py` — teste confere igualdade —, rede, diesel, manejo de dejetos com os fatores da base do Carbono, menos vazamento), digestato e N-P-K, faixa de Monte Carlo.
- Calor útil (`energia.calor_util_kwh_dia`) serve ao Secador e ao AVAC.

## Testes

- `tests/test_simulacao.py`: U da parede, decaimento 1D, placa quadrada, balanço PL³/3EI (2D e 3D), carga distribuída, treliça, Euler, patch test do CST, chaminé, LBM (massa e estabilidade), D8 no plano, SCS-CN conhecido, Monte Carlo (média e semente), QUBO (força bruta, Ising), biogás (à mão, TRH longo, frio, sobrecarga, igual ao Carbono, `[MARCADOR]`), rotas.
- `tests/test_simulacao_paridade.py`: casos em dia, analíticos de cada caso, contrato do JS, cores da paleta, patch de variáveis sem colisão.
- Paridade Python × navegador: `conferir-simulacao.html` compara 156 valores com tolerância relativa de 1e-7 (resultado em 15/11/2026: **TUDO OK**).

## Fase 1 × Fase 2

| Hoje (Fase 1, leve) | Fase 2 (contêiner Linux, pesado) | Licença |
|---|---|---|
| U, transiente 1D, corte 2D | FEniCSx (física sob medida), CalculiX térmico | LGPL-3.0; GPL-2.0+ |
| Pórtico, treliça, CST | CalculiX (+ Gmsh, ParaView); Code_Aster + SALOME para casos industriais | GPL-2.0+ (Gmsh GPL-2.0+ com exceção; ParaView BSD-3); GPL-3.0; LGPL |
| Malha por máscara | Gmsh | GPL-2.0+ com exceção de linkagem |
| Ventilação por fórmula, LBM qualitativo | OpenFOAM (escolher **uma** linha: Foundation v14 **ou** ESI v2606); SU2 para pás | GPL-3.0; LGPL-2.1 |
| Sol por superfície (Mapeamento) | Radiance + Ladybug Tools | Radiance License 2.0 (variante BSD); **AGPL-3.0** |
| Carga térmica de uma zona | EnergyPlus + OpenStudio multizona | variante BSD-3 (cláusula de nome) |
| — (grãos no secador) | Yade (DEM; LIGGGHTS-PUBLIC está parado desde 2017) ou Project Chrono | GPL-2.0+; BSD-3 |
| — (sistemas térmico/elétrico/controle) | OpenModelica (compila FMU; a FMU roda na Fase 1) | **AGPL-3.0** (ou OSMC-PL) |
| QUBO clássico | Qiskit + Aer, PennyLane — só simulador, só P&D | Apache-2.0 |

Licenças vindas do catálogo verificado `23b_Catalogo_Software_Aberto.md`. **AGPL (Ladybug Tools, OpenModelica):** se modificarmos e oferecermos como serviço web, temos de publicar o código modificado; usar sem modificar ou isolar como serviço separado. **PrePoMax** é só Windows: fica fora do servidor (só estação de trabalho). Versões exatas: `[CONFERIR]` na hora de montar as imagens.

## Tarefas do Eric para a Fase 2 (servidor)

1. Imagem `calculix` (ccx + Gmsh + ParaView `pvbatch`) com volume de trabalho e fila de jobs; limite de CPU e memória por job.
2. Imagem `openfoam` de **uma** distribuição só (Foundation v14 ou ESI v2606), com casos-modelo de vento em prédio e de câmara de secador.
3. Imagem `fenicsx` (imagem oficial `[CONFERIR]`) para calor e umidade em parede de terra.
4. Imagem `energyplus` + OpenStudio, e Radiance; Ladybug Tools como serviço separado e sem modificação (AGPL).
5. Imagem `yade` (DEM do secador) e, se preciso, `chrono`.
6. Imagem `openmodelica` (`omc`) só para compilar FMU.
7. Imagem `qubo-qiskit` a partir de `physis_hub/simulacao/conteiner/Containerfile.qiskit` (versões fixadas), sem acesso à rede de produção; só P&D.
8. Fila de jobs com rota no hub (`/api/simulacao/fase2/...`), guarda de resultados com hash (integridade) e limpeza.
9. Dados: EPW do lugar (já há o leitor no Mapeamento), modelo de elevação do lote, ensaios de material (E, fy de bambu, madeira e filamentos; BMP dos substratos), arquivos de malha dos casos-modelo.
10. Teste de regressão: o mesmo caso da Fase 1 rodado no solver da Fase 2 tem de bater na ordem de grandeza (benchmarks deste documento).

## Patch de integração (para quem é dono de cada arquivo)

**Embutir no painel** (`ferramentas/embutir_bases.py`, em `MODULOS`, nesta ordem):

    "mod-simulacao-casos": S / "simulacao-exemplos" / "casos.js",   # exemplos (dados fictícios)
    "mod-simulacao": S / "physis-simulacao.js",                     # aba Simulação + cartões nas outras abas

O módulo lê sozinho `base-materiais`, `base-fatores-emissao`, `window.PhysisCalc` e `window.TURBINAS`.

**Aba** (`painel.html`): `["simulacao","Simulação"]` em `ABAS` (grupo 2, modelagem) e `simulacao: () => typeof telaSimulacao === "function" ? telaSimulacao() : telaPlanejado("simulacao")` em `TELAS`. Módulo `simulacao` já existe em `physis-variaveis.json` (classe "pesquisa"). I18N: juntar `window.SIMULACAO_I18N`.

**Cartões dentro das abas existentes** (`SIMULACAO.painel(tipo, entrada)` devolve uma seção com h2):

| Aba | Cartão | Entrada |
|---|---|---|
| Economia circular · biodigestor | `"biogas"` | substratos do plano RC com rota biodigestor (alimentos→`restos_alimentos`, esterco_bov→`esterco_bovino`, esterco_sui→`esterco_suino`, cama_aviario, colheita→`residuos_colheita`), kg/dia = qtd × RC_UN ÷ 30; `temperatura_mensal` do `localDaInstalacao()` + camada de temperatura do GIS. Depois `calcGravar("physis-calc-biogas", r.carbono_ctx)` para o Carbono |
| AVAC · carga térmica | `"u"` e `SIMULACAO.termica.perdaEnvoltoria` | composição da parede/cobertura escolhida; calor do biogás (`energia.calor_util_kwh_dia`) |
| Secador | `"ventilacao"`; calor do biogás | aberturas e alturas da câmara |
| Mapeamento · relevo | `"escoamento"`, `"enxurrada"`, `"erosao"` | `{geometria: lerLS("physis-geometria-lugar")}` (rota) ou `{grade: SIMULACAO.terreno.gradeDaGeometria(geo)}` |
| SbN | `"enxurrada"` (onde plantar, valas); `"u"` com `telhado_verde_extensivo` | idem |
| Resiliência | `"enxurrada"`, `"erosao"` | idem |
| Turbinas · eólica | `"eolica"`, `"estrutura"` (torre) | série de vento; torre como no exemplo `ex_torre_turbina` |
| Energia solar | `"estrutura"` (suporte), `"paineis"` (QUBO), `"incerteza"` modelo `solar` | |
| Carbono | `"incerteza"` modelo `carbono` | atividades e fatores com desvio |

**Rotas** (`servidor.py`, no `do_POST`, junto das outras com sessão):

    from . import simulacao as simulacao_mod
    ...
    if u.path.startswith("/api/simulacao/"):
        q = self._sessao_ou_401()
        if not q:
            return
        try:
            d = seg.carregar_json(self._corpo() or "{}")
        except ValueError:
            return self._json(400, {"ok": False, "erro": "json invalido"})
        ctx = None
        if u.path == "/api/simulacao/biogas" and isinstance(d, dict) and d.get("regime") == "ambiente" and not d.get("temperatura_mensal"):
            ctx = simulacao_mod.biogas.clima_do_local(hub, irradiacao)
            if not ctx.get("ok"):
                return self._json(422, {"ok": False, "erro": ctx["erro"], "marcador": True})
        codigo, r = simulacao_mod.rota(u.path, d if isinstance(d, dict) else {}, ctx)
        return self._json(codigo, r)

Rotas: `termica/u|1d|2d|envoltoria`, `estrutura/portico|cst|euler`, `fluidos/ventilacao|lbm|eolica`, `terreno/escoamento|declividade|scs|usle|visada` (aceitam `grade` ou `geometria`), `incerteza`, `qubo/paineis|rota|topologia` (devolvem também a `exportacao` physis-qubo/1), `biogas`. Erro de dado faltando: 422 com `[MARCADOR]`; caso grande demais para o notebook: 400.

**Premissas**: juntar todas as entradas de `sistema/physis-simulacao-premissas.json` em `sistema/physis-premissas.json` (ids `sim.*`, sem colisão; `python -m physis_hub.simulacao.integracao premissas` imprime a lista). Depois de juntar, rodar `python -m physis_hub.simulacao.casos --gravar`.

**Variáveis**: `python -m physis_hub.simulacao.integracao variaveis` imprime 18 variáveis calculadas (`sim.*`, `bio.*`), 36 de premissa (`premissa.sim.*`), 8 fluxos e o acréscimo de `simulacao` aos produtores de `rc.biogas`.
