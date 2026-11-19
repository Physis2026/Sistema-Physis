"""Validação · planejado × gerado (M&V) — EM DESENVOLVIMENTO. Produto 3 do SustainKit (decisão de 18/11/2026):
compara, para cada instalação, o PLANEJADO (dimensionamento do módulo, Planejador ou premissas) com o MEDIDO (leituras
que o hub já guarda), mês a mês, e diz QUANTO, QUANDO, COMO e POR QUÊ. Espelho das contas em sistema/physis-validacao.js
(mesmas premissas validacao.*, fórmulas e regras; teste em tests/test_validacao.py). Texto simples em docs/VALIDACAO_MV.md.

NÃO confundir com physis_hub/mv*.py: aquilo é a gestão interna de M&V das quatro entidades da Physis.

De onde vem cada número:
- PLANEJADO: tabela validacao_plano, gravada pela equipe na aba (valores mensais com a FONTE: "Energia solar ·
  dimensionamento", "Turbinas · kwhAnoPlanejado", premissa…). Frota: o consumo esperado de cada veículo (cadastro da
  Frota) × os km medidos. Carbono: nasce dos planejados de Energia e da Frota, com o fator da rede e os fatores de
  combustão do Carbono (carbono.fator_rede, frota.co2e). Módulo sem plano diz "sem plano"; nada é inventado.
- MEDIDO: tabela medicao do hub (V6, MQTT, importações): média do dia × 24 h por medidor (a mesma regra do aprendizado
  de consumo), somada no mês, com a contagem de dias com leitura. Frota: abastecimentos do mês (ou a vazão) e km.
- CLIMA (a estação da Resiliência e o pluviômetro): irradiância medida (W/m² → kWh/m²·dia), chuva do mês e graus-dia
  de resfriamento das temperaturas do ar.

Contas:
- QUANTO: desvio = medido − planejado (absoluto) e ÷ planejado (%).
- QUANDO: o primeiro mês em que |desvio| passou de validacao.desvio_limite_pct e quantos meses seguidos durou.
- COMO: o equipamento (item) e a variável que mais pesaram no desvio do mês.
- POR QUÊ: regras com evidência e confiança (0 a 1): falha de dado (dias sem leitura), clima (irradiância, chuva ou
  graus-dia medidos × esperados), consumo anormal (o mesmo z robusto da Frota, frota.anomalia_consumo), premissa
  divergente (desvio no mesmo sentido por vários meses, com pouca variação) e efeito sazonal (plano igual todo mês e
  medido que segue a estação). Sem regra que case: "causa não identificada".
- LINHA DE BASE (no estilo do IPMVP): regressão linear simples (aprendizado.reta, só biblioteca padrão) do consumo do
  período de base contra graus-dia, irradiância ou produção; no período de relatório, o ajuste rotineiro é o consumo que a
  linha de base daria nas condições do relatório, e a economia sai da MESMA equação da aba Certificações:
  economia = (linha de base − período de relatório) ± ajustes (ipmvp_economia, espelho de VALIDACAO.ipmvp, que o
  mvEconomia() do painel chama).
Todos os limites são premissas validacao.* de sistema/physis-premissas.json, com status "conferir".
"""
from __future__ import annotations

import calendar
import hashlib
import json
import math
import re
import statistics
from datetime import datetime
from pathlib import Path

from . import aprendizado
from . import carbono
from . import clima as clima_mod
from . import frota as frota_mod
from . import nucleo
from . import validacao_modelos as vm
from . import validacao_nucleo as vn
from . import seguranca as seg

RAIZ = Path(__file__).resolve().parents[2]
ARQ_PREMISSAS = frota_mod.ARQ_PREMISSAS
FUSO = clima_mod.FUSO
MESES_MAX = 36

# Módulos comparados. sentido: "gerar" (abaixo do plano é perda) ou "consumir" (acima do plano é gasto a mais).
# clima: a grandeza do tempo que explica o desvio; sinal: +1 = desvio vai no mesmo sentido do clima (menos sol,
# menos geração; mais graus-dia, mais consumo), −1 = sentido contrário.
MODULOS = {
    "solar": {"nome": "Energia solar (geração)", "unidade": "kWh", "grandeza": "energia", "sentido": "gerar",
              "clima": "irradiancia", "sinal": 1},
    "agua": {"nome": "Água (consumo e reúso)", "unidade": "m³", "grandeza": "vazao", "sentido": "consumir",
             "clima": "chuva", "sinal": -1},
    "energia": {"nome": "Energia e AVAC (consumo)", "unidade": "kWh", "grandeza": "energia", "sentido": "consumir",
                "clima": "graus_dia", "sinal": 1},
    "turbinas": {"nome": "Turbinas (geração)", "unidade": "kWh", "grandeza": "energia", "sentido": "gerar",
                 "clima": None, "sinal": 1},
    "frota": {"nome": "Frota (combustível)", "unidade": "L", "grandeza": None, "sentido": "consumir",
              "clima": None, "sinal": 1},
    "carbono": {"nome": "Carbono (emissões)", "unidade": "tCO₂e", "grandeza": None, "sentido": "consumir",
                "clima": None, "sinal": 1},
}
SEM_PLANO = {
    "solar": "Sem plano: grave o planejado da usina (aba Energia solar · dimensionamento) para comparar.",
    "agua": "Sem plano: grave o consumo planejado (premissa de consumo por pessoa, projeto ou Planejador) para comparar.",
    "energia": "Sem plano: grave o consumo planejado (projeto, AVAC ou Planejador) para comparar.",
    "turbinas": "Sem plano: grave a energia planejada (aba Turbinas) para comparar.",
    "frota": "Sem plano: nenhum veículo tem o consumo esperado no cadastro da Frota.",
    "carbono": "Sem plano: o Carbono nasce dos planejados de Energia e da Frota, e nenhum dos dois tem plano.",
}
VARIAVEIS_BASE = {"graus_dia": "Graus-dia de resfriamento", "irradiancia": "Irradiação (kWh/m²·dia)",
                  "producao": "Produção ou ocupação (Gestão)"}
CAUSAS = {"falha_dado": "Equipamento desligado ou falha de dado", "clima": "Clima diferente do esperado",
          "consumo_anormal": "Consumo fora do normal aprendido", "premissa": "Premissa do projeto diverge do medido",
          "sazonal": "Efeito sazonal", "nao_identificada": "Causa não identificada"}

# reserva das premissas validacao.* (as mesmas de sistema/physis-premissas.json; todas "conferir")
PREMISSAS_PADRAO = {"validacao.desvio_limite_pct": 10.0, "validacao.cobertura_min_pct": 90.0,
                    "validacao.clima_min_pct": 10.0, "validacao.premissa_meses_min": 3,
                    "validacao.premissa_variacao_max_pct": 15.0, "validacao.plano_plano_max_pct": 2.0,
                    "validacao.anomalia_z": 3.5, "validacao.anomalia_amostra_min": 6,
                    "validacao.grau_dia_base_c": 18.3, "validacao.baseline_meses_min": 12,
                    "validacao.baseline_cvrmse_max_pct": 15.0,
                    "validacao.aceite_r2_min": 0.75, "validacao.aceite_nmbe_max_pct": 5.0, "validacao.aceite_cvrmse_diario_max_pct": 25.0,
                    "validacao.modelo_ganho_min_pct": 5.0, "validacao.ml_amostra_min": 365, "validacao.ml_k": 7,
                    "validacao.incerteza_confianca_pct": 68.0, "validacao.incerteza_max_pct": 50.0, "validacao.perda_dados_max_pct": 10.0,
                    "validacao.limpeza_z": 5.0, "validacao.travado_n": 12, "validacao.inspecao_dias_max": 90,
                    "validacao.revisao_aviso_dias": 30, "validacao.fdd_dias_min": 3,
                    "validacao.cv_k": 5, "validacao.aceite_cvrmse_ou_max_pct": 20.0, "validacao.cusum_k": 0.5, "validacao.cusum_h": 5.0,
                    "validacao.ip_confianca_pct": 95.0, "validacao.mc_n": 2000, "validacao.mc_confianca_pct": 95.0,
                    "validacao.nre_dias_min": 14, "validacao.nre_limite_pct": 10.0, "validacao.nre_z": 3.0,
                    **dict.fromkeys(vn.PREMISSAS_PEE)}        # perfil PEE (ANEEL): [MARCADOR] até ler o Guia de M&V
CHAVE_GESTAO = "gestao-physis:validacao-tarefas"     # tarefas da Gestão abertas pelo M&V (ciclo fechado com a manutenção)
CAUSAS_DE_FALHA = ("falha_dado", "consumo_anormal", "nao_identificada")   # equipamento ou operação: podem virar tarefa
VERSAO_CODIGO = "validacao-2"              # vai no anexo de rastreabilidade de todo relatório
OPCOES_IPMVP = {"A": "Medição isolada do parâmetro-chave", "B": "Medição isolada de todos os parâmetros",
                "C": "Instalação inteira (fatura ou medidor geral)", "D": "Simulação calibrada"}
PAPEIS = {"coleta": "Coleta dos dados", "analise": "Análise", "arquivo": "Arquivo", "relatorio": "Relatório"}
SECOES_RELATORIO = ["Descrição do projeto", "Método e opção IPMVP", "Dados observados", "Comparação com as metas",
                    "Análise de incerteza", "Evidências", "Recomendações", "Anexo de rastreabilidade"]
ACOES = {"falha_dado": "Conferir a alimentação e a comunicação do medidor e do nó; repor os dias perdidos se houver outra fonte.",
         "clima": "Nada a corrigir no equipamento: registrar o clima do período e levar à linha de base.",
         "consumo_anormal": "Inspecionar o equipamento e a operação (horário, ajuste, vazamento) e registrar a inspeção.",
         "premissa": "Revisar a premissa com a equipe e registrar a mudança no plano de M&V (com o motivo).",
         "sazonal": "Trocar o planejado igual todo mês por um planejado com estação.",
         "nao_identificada": "Inspeção em campo; registrar o que foi achado no diário de lições."}

S, NUM = str, (int, float)
ESQUEMAS = {
    "validacao_plano": {"id": (int, 10**9, False), "modulo": (S, 20, True), "item": (S, 60, True), "nome": (S, 80, False),
                        "ativo": (S, 80, False), "grandeza": (S, 30, False), "unidade": (S, 20, False),
                        "fonte": (S, 200, True), "meses": (dict, MESES_MAX, True), "clima": (dict, MESES_MAX, False),
                        "premissa": (S, 80, False)},
    "validacao_id": {"id": (int, 10**9, True)},
    "validacao_plano_mv": {"plano": (dict, 60, True), "motivo": (S, 300, True)},
    "validacao_medidor": {"id": (int, 10**9, False), "ativo": (S, 80, True), "tipo": (S, 60, True), "modelo": (S, 80, False),
                          "exatidao_pct": (NUM, 100, False), "incerteza_pct": (NUM, 100, False), "comissionamento": (S, 10, False),
                          "cal_ultima": (S, 10, False), "cal_proxima": (S, 10, False), "certificado_nome": (S, 160, False),
                          "certificado_sha256": (S, 64, False), "faixa_min": (NUM, 10**9, False), "faixa_max": (NUM, 10**9, False)},
    "validacao_licao": {"texto": (S, 2000, True)},
    "validacao_inspecao": {"ecm": (S, 60, True), "operando": (bool, None, True), "obs": (S, 500, False)},
    "validacao_nre": {"chave": (S, 40, True), "aprovar": (bool, None, True), "motivo": (S, 300, True)},
    "validacao_chave": {"chave": (S, 40, True)},
    "validacao_item": {"item": (S, 60, True)},
}
ESQUEMA = """
CREATE TABLE IF NOT EXISTS validacao_plano (
  id INTEGER PRIMARY KEY AUTOINCREMENT, modulo TEXT NOT NULL, item TEXT NOT NULL, nome TEXT NOT NULL DEFAULT '',
  ativo TEXT NOT NULL DEFAULT '', grandeza TEXT NOT NULL DEFAULT '', unidade TEXT NOT NULL DEFAULT '',
  fonte TEXT NOT NULL, meses TEXT NOT NULL, clima TEXT NOT NULL DEFAULT '{}', premissa TEXT NOT NULL DEFAULT '',
  criado REAL NOT NULL, atualizado REAL NOT NULL, por TEXT NOT NULL, UNIQUE(modulo, item));
CREATE TABLE IF NOT EXISTS validacao_plano_mv (
  versao INTEGER PRIMARY KEY AUTOINCREMENT, dados TEXT NOT NULL, motivo TEXT NOT NULL, por TEXT NOT NULL,
  quando REAL NOT NULL, registro TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS validacao_medidor (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ativo TEXT NOT NULL UNIQUE, dados TEXT NOT NULL, atualizado REAL NOT NULL, por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS validacao_licao (
  id INTEGER PRIMARY KEY AUTOINCREMENT, texto TEXT NOT NULL, quando REAL NOT NULL, por TEXT NOT NULL, registro TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS validacao_inspecao (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ecm TEXT NOT NULL, operando INTEGER NOT NULL, obs TEXT NOT NULL DEFAULT '',
  quando REAL NOT NULL, por TEXT NOT NULL, registro TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS validacao_modelo (
  hash TEXT PRIMARY KEY, item TEXT NOT NULL, ciclo TEXT NOT NULL, parametros TEXT NOT NULL, dados_hash TEXT NOT NULL, criado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS validacao_nre (
  chave TEXT PRIMARY KEY, item TEXT NOT NULL, dados TEXT NOT NULL, situacao TEXT NOT NULL, por TEXT NOT NULL DEFAULT '',
  motivo TEXT NOT NULL DEFAULT '', registro TEXT NOT NULL DEFAULT '', criado REAL NOT NULL, atualizado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS validacao_tarefa (
  chave TEXT PRIMARY KEY, dados TEXT NOT NULL, criado REAL NOT NULL, por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS validacao_resultado (
  id INTEGER PRIMARY KEY AUTOINCREMENT, item TEXT NOT NULL, dados TEXT NOT NULL, resumo TEXT NOT NULL, quando REAL NOT NULL,
  por TEXT NOT NULL, registro TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS validacao_alerta (
  chave TEXT PRIMARY KEY, item TEXT NOT NULL, inicio TEXT NOT NULL, fim TEXT NOT NULL, dados TEXT NOT NULL,
  criado REAL NOT NULL, atualizado REAL NOT NULL);
"""
_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_ITEM = re.compile(r"^[A-Za-z0-9_.-]{1,60}$")
_MES = re.compile(r"^(\d{4}-)?(0[1-9]|1[0-2])$")


# ══ Premissas ══════════════════════════════════════════════════════════════════════════════════
def premissas(dados=None) -> dict:
    """{id: valor} das premissas validacao.* (base sistema/physis-premissas.json ou a cópia do painel; sem nenhuma, a
    reserva marcada 'conferir')."""
    j = dados
    if j is None:
        for c in ARQ_PREMISSAS:
            try:
                j = json.loads(Path(c).read_text(encoding="utf-8"))
                break
            except (OSError, ValueError):
                continue
        else:
            j = frota_mod._do_painel(r"var PREMISSAS = (\{.*?\});\n")
    out = dict(PREMISSAS_PADRAO)
    for p in (j or {}).get("premissas") or []:
        if p.get("id") in out and isinstance(p.get("valor_padrao"), (int, float)) and not isinstance(p.get("valor_padrao"), bool):
            out[p["id"]] = p["valor_padrao"]
    return out


# ══ Contas puras (espelho em sistema/physis-validacao.js) ══════════════════════════════════════
def desvio(planejado: float | None, medido: float | None) -> dict:
    """QUANTO: absoluto (medido − planejado) e % sobre o planejado. Sem um dos dois, ou planejado ≤ 0 no %, None."""
    if planejado is None or medido is None:
        return {"abs": None, "pct": None}
    return {"abs": medido - planejado, "pct": (medido - planejado) / planejado * 100 if planejado > 0 else None}


def dias_do_mes(mes: str) -> int:
    return calendar.monthrange(int(mes[:4]), int(mes[5:7]))[1]


def meses_ate(ultimo: str, n: int) -> list[str]:
    """Os n meses (AAAA-MM) que terminam em `ultimo`, do mais antigo ao mais novo."""
    a, m = int(ultimo[:4]), int(ultimo[5:7])
    out = []
    for _ in range(n):
        out.append(f"{a:04d}-{m:02d}")
        m -= 1
        if m == 0:
            a, m = a - 1, 12
    return out[::-1]


def plano_do_mes(meses: dict | None, mes: str) -> float | None:
    """O planejado vale para o mês exato (AAAA-MM) ou, no ano típico do dimensionamento, para o mês do ano (MM)."""
    if not meses:
        return None
    v = meses.get(mes, meses.get(mes[5:7]))
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def cv_pct(vals: list[float]) -> float | None:
    """Coeficiente de variação (desvio-padrão populacional ÷ média) em %."""
    v = [x for x in vals if x is not None]
    if len(v) < 2:
        return 0.0 if v else None
    m = sum(v) / len(v)
    return statistics.pstdev(v) / abs(m) * 100 if m else None


def plano_plano(meses: dict | None, P: dict) -> bool:
    """O plano é igual em todos os meses (ano dividido por 12): não tem estação."""
    vals = [v for v in (meses or {}).values() if isinstance(v, (int, float))]
    c = cv_pct(vals)
    return len(vals) >= 2 and c is not None and c <= P["validacao.plano_plano_max_pct"]


def comparar(plano: dict | None, medido: dict, meses: list[str], clima: dict | None = None,
             clima_esperado: dict | None = None) -> list[dict]:
    """Linhas mês a mês: planejado, medido, desvio, dias com leitura e o clima medido × esperado do mês.
    medido = {mes: {valor, dias, dias_mes}}; clima = {mes: valor medido}; clima_esperado = {mes ou MM: valor}."""
    out = []
    for mes in meses:
        p = plano_do_mes(plano, mes)
        m = medido.get(mes) or {}
        v = m.get("valor")
        dm = m.get("dias_mes") or dias_do_mes(mes)
        dias = m.get("dias")
        d = desvio(p, v)
        out.append({"mes": mes, "planejado": p, "medido": v, "abs": d["abs"], "pct": d["pct"],
                    "dias": dias, "dias_mes": dm, "cobertura_pct": None if dias is None else dias / dm * 100,
                    "clima_medido": (clima or {}).get(mes), "clima_esperado": plano_do_mes(clima_esperado, mes)})
    return out


def fora(linha: dict, P: dict) -> bool:
    return linha.get("pct") is not None and abs(linha["pct"]) > P["validacao.desvio_limite_pct"]


def quando(linhas: list[dict], P: dict) -> dict | None:
    """QUANDO: o primeiro mês fora do limite, quantos meses seguidos durou, se continua no último mês e todos os trechos."""
    trechos, ini = [], None
    for i, l in enumerate(linhas):
        if fora(l, P):
            if ini is None:
                ini = i
        elif ini is not None:
            trechos.append((ini, i - 1))
            ini = None
    if ini is not None:
        trechos.append((ini, len(linhas) - 1))
    if not trechos:
        return None
    a, b = trechos[0]
    return {"primeiro_mes": linhas[a]["mes"], "duracao_meses": b - a + 1, "ultimo_mes": linhas[b]["mes"],
            "continua": trechos[-1][1] == len(linhas) - 1,
            "trechos": [{"inicio": linhas[x]["mes"], "fim": linhas[y]["mes"], "meses": y - x + 1} for x, y in trechos]}


def nivel(conf: float) -> str:
    return "alta" if conf >= 0.7 else "média" if conf >= 0.45 else "baixa" if conf > 0 else "—"


def _causa(cod: str, conf: float, evid: dict, texto: str) -> dict:
    conf = round(max(0.0, min(1.0, conf)), 2)
    return {"codigo": cod, "nome": CAUSAS[cod], "confianca": conf, "nivel": nivel(conf), "evidencia": evid, "texto": texto}


def _sinal(x: float) -> int:
    return (x > 0) - (x < 0)


def causas(linha: dict, historico: list[dict], info: dict, P: dict, ewma_alfa: float = 0.3,
           janela: list[dict] | None = None) -> list[dict]:
    """POR QUÊ: causas prováveis do desvio do mês, com evidência e confiança, da mais para a menos provável.
    linha: a linha do mês (de comparar); historico: as linhas anteriores do MESMO item (mais antiga primeiro);
    janela: todas as linhas do item no período analisado (sem ela, histórico + o mês): a média do período separa a
    estação de uma premissa; info: {sentido, sinal, clima, plano_plano, premissa}."""
    out, pct = [], linha.get("pct")
    if pct is None:
        return [_causa("nao_identificada", 0, {}, "Sem planejado ou sem medido no mês.")]
    jan = janela if janela is not None else historico + [linha]
    lim = P["validacao.desvio_limite_pct"]
    # 1. equipamento desligado ou falha de dado: dias sem leitura no mês
    cob, cob_min = linha.get("cobertura_pct"), P["validacao.cobertura_min_pct"]
    if cob is not None and cob < cob_min:
        conf = 0.95 if cob == 0 else min(0.9, 0.5 + (cob_min - cob) / 100)
        out.append(_causa("falha_dado", conf, {"dias": linha.get("dias"), "dias_mes": linha.get("dias_mes"), "cobertura_pct": cob,
                                               "cobertura_min_pct": cob_min},
                          f"{linha.get('dias')} de {linha.get('dias_mes')} dias com leitura ({cob:.0f} %; o mínimo é {cob_min:.0f} %)."))
    # 2. clima medido × esperado (estação da Resiliência, pluviômetro, temperatura do ar)
    cm, ce = linha.get("clima_medido"), linha.get("clima_esperado")
    if info.get("clima") and cm is not None and ce:
        dc = (cm - ce) / ce * 100
        if abs(dc) >= P["validacao.clima_min_pct"] and _sinal(dc) * info.get("sinal", 1) == _sinal(pct):
            explica = min(abs(dc), abs(pct)) / max(abs(dc), abs(pct))
            out.append(_causa("clima", 0.35 + 0.5 * explica, {"variavel": info["clima"], "medido": cm, "esperado": ce, "diferenca_pct": dc},
                              f"{info['clima']}: medido {cm:.2f} × esperado {ce:.2f} ({dc:+.0f} %)."))
    # 3. consumo anormal: o MESMO z robusto da Frota (frota.anomalia_consumo: mediana e MAD do próprio histórico), sobre a
    #    razão medido ÷ planejado do mês (tira a estação que o plano já prevê; na frota, é o L/100 km ÷ o esperado)
    if info.get("sentido") == "consumir" and pct > 0 and linha.get("medido") is not None and linha.get("planejado"):
        hist = [h["medido"] / h["planejado"] for h in historico if h.get("medido") is not None and h.get("planejado")
                and (h.get("cobertura_pct") is None or h["cobertura_pct"] >= cob_min)]
        a = frota_mod.anomalia_consumo(linha["medido"] / linha["planejado"], hist, P["validacao.anomalia_z"],
                                       int(P["validacao.anomalia_amostra_min"]), ewma_alfa, lim)
        if a["anomalo"]:
            out.append(_causa("consumo_anormal", 0.7, {"z": a["z"], "razao": a["valor"], "mediana": a["mediana"], "n": a["n"]},
                              f"razão medido ÷ planejado {a['valor']:.2f}; mediana {a['mediana']:.2f} de {a['n']} meses; z robusto {a['z']:.1f}."))
    # 4. efeito sazonal: plano igual todo mês e o medido do mês longe da média do período, no mesmo sentido do desvio
    sazonal = False
    if info.get("plano_plano"):
        meds = [h["medido"] for h in jan if h.get("medido") is not None]
        if len(meds) >= 3:
            mm = sum(meds) / len(meds)
            if mm and _sinal(linha["medido"] - mm) == _sinal(pct) and abs(linha["medido"] - mm) / mm * 100 >= lim / 2:
                sazonal = True
                out.append(_causa("sazonal", 0.5, {"media_medida": mm, "medido": linha["medido"]},
                                  f"O plano é igual todo mês; o medido do mês está {(linha['medido'] - mm) / mm * 100:+.0f} % da média medida."))
    # 5. premissa divergente: vários meses seguidos no mesmo sentido, pouca variação e o período todo puxado para esse
    #    lado; se a estação já explica, não é premissa
    seq = [linha]
    for h in reversed(historico):
        if h.get("pct") is None or abs(h["pct"]) <= lim or _sinal(h["pct"]) != _sinal(pct) \
                or (h.get("cobertura_pct") is not None and h["cobertura_pct"] < cob_min):
            break
        seq.append(h)
    todos = [h["pct"] for h in jan if h.get("pct") is not None] or [pct]
    media_ano = sum(todos) / len(todos)
    if not sazonal and (cob is None or cob >= cob_min) and len(seq) >= P["validacao.premissa_meses_min"] \
            and _sinal(media_ano) == _sinal(pct) and abs(media_ano) >= lim / 2:
        razoes = [s["medido"] / s["planejado"] for s in seq if s.get("planejado")]
        c = cv_pct(razoes)
        if c is not None and c <= P["validacao.premissa_variacao_max_pct"]:
            out.append(_causa("premissa", 0.65 if info.get("premissa") else 0.6,
                              {"meses": len(seq), "media_pct": sum(s["pct"] for s in seq) / len(seq), "cv_pct": c,
                               "premissa": info.get("premissa") or None},
                              f"{len(seq)} meses seguidos {'acima' if pct > 0 else 'abaixo'} do plano, variação de {c:.0f} %"
                              + (f"; premissa {info['premissa']}" if info.get("premissa") else "") + "."))
    if not out:
        out.append(_causa("nao_identificada", 0, {}, "Nenhuma regra explica o desvio: confira em campo."))
    return sorted(out, key=lambda c: -c["confianca"])


def como(itens: list[dict], mes: str) -> dict | None:
    """COMO: o item (equipamento) e a variável que mais pesaram no desvio do mês, com a parte dele no total."""
    lins = [(it, next((l for l in it["linhas"] if l["mes"] == mes), None)) for it in itens]
    lins = [(it, l) for it, l in lins if l and l.get("abs") is not None]
    if not lins:
        return None
    total = sum(l["abs"] for _, l in lins)
    it, l = max(lins, key=lambda x: abs(x[1]["abs"]))
    return {"item": it["item"], "nome": it.get("nome") or it["item"], "ativo": it.get("ativo") or "",
            "variavel": it.get("grandeza") or "", "abs": l["abs"], "pct": l["pct"],
            "parte_pct": abs(l["abs"]) / abs(total) * 100 if total else None}


def somar_itens(itens: list[dict], meses: list[str]) -> list[dict]:
    """Linhas do módulo: soma dos itens que têm plano. Dias com leitura = o pior item do mês."""
    out = []
    for i, mes in enumerate(meses):
        ls = [it["linhas"][i] for it in itens]
        p = [l["planejado"] for l in ls if l["planejado"] is not None]
        m = [l["medido"] for l in ls if l["medido"] is not None and l["planejado"] is not None]
        pl = sum(p) if p else None
        me = sum(m) if m else None
        d = desvio(pl, me)
        cobs = [l["cobertura_pct"] for l in ls if l.get("cobertura_pct") is not None]
        out.append({"mes": mes, "planejado": pl, "medido": me, "abs": d["abs"], "pct": d["pct"],
                    "cobertura_pct": min(cobs) if cobs else None})
    return out


def analisar_modulo(mod: str, itens: list[dict], meses: list[str], P: dict, ewma_alfa: float = 0.3) -> dict:
    """Um módulo inteiro: itens (cada um com plano, medido e clima) → linhas, QUANDO, e COMO e POR QUÊ de cada mês fora.
    itens: [{item, nome, ativo, grandeza, fonte, premissa, plano: {mes|MM: v} | None, medido: {mes: {...}},
             clima: {mes: v}, clima_esperado: {mes|MM: v}}]"""
    cfg = MODULOS[mod]
    com_plano = [it for it in itens if it.get("plano")]
    base = {"modulo": mod, "nome": cfg["nome"], "unidade": cfg["unidade"], "sentido": cfg["sentido"], "meses": meses}
    if not com_plano:
        return dict(base, tem_plano=False, sem_plano=SEM_PLANO[mod], itens=[], linhas=[], quando=None, explicacoes=[], total=None,
                    itens_sem_plano=[it.get("nome") or it.get("item") for it in itens])
    out_it = []
    for it in com_plano:
        lin = comparar(it["plano"], it.get("medido") or {}, meses, it.get("clima"), it.get("clima_esperado"))
        out_it.append({"item": it["item"], "nome": it.get("nome") or it["item"], "ativo": it.get("ativo") or "",
                       "grandeza": it.get("grandeza") or cfg["grandeza"] or "", "fonte": it.get("fonte") or "",
                       "premissa": it.get("premissa") or "", "plano_plano": plano_plano(it["plano"], P), "linhas": lin,
                       "extra": it.get("extra") or {}})
    linhas = somar_itens(out_it, meses)
    expl = []
    for i, l in enumerate(linhas):
        if not fora(l, P):
            continue
        c = como(out_it, l["mes"])
        it = next((x for x in out_it if c and x["item"] == c["item"]), out_it[0])
        info = {"sentido": cfg["sentido"], "sinal": cfg["sinal"], "clima": cfg["clima"], "plano_plano": it["plano_plano"],
                "premissa": it["premissa"]}
        expl.append({"mes": l["mes"], "abs": l["abs"], "pct": l["pct"], "como": c,
                     "causas": causas(it["linhas"][i], it["linhas"][:i], info, P, ewma_alfa, it["linhas"])})
    tp = [l for l in linhas if l["planejado"] is not None and l["medido"] is not None]
    tot_p, tot_m = sum(l["planejado"] for l in tp), sum(l["medido"] for l in tp)
    return dict(base, tem_plano=True, sem_plano="", itens=out_it, linhas=linhas, quando=quando(linhas, P), explicacoes=expl,
                total=dict(desvio(tot_p, tot_m), planejado=tot_p, medido=tot_m, meses=len(tp)),
                itens_sem_plano=[it.get("nome") or it.get("item") for it in itens if not it.get("plano")])


# ══ Linha de base e equação do IPMVP ══════════════════════════════════════════════════════════
def ipmvp_economia(base: float | None, rel: float | None, aj: float = 0.0) -> dict:
    """Equação geral do IPMVP, a MESMA da aba Certificações (painel: mvEconomia → VALIDACAO.ipmvp):
    economia = (linha de base − período de relatório) ± ajustes; a % é sobre a linha de base já ajustada."""
    a = aj or 0.0
    if base is None or rel is None:
        return {"economia": None, "base_ajustada": None if base is None else base + a, "pct": None}
    econ, baj = base - rel + a, base + a
    return {"economia": econ, "base_ajustada": baj, "pct": econ / baj * 100 if baj > 0 else None}


def graus_dia(temperaturas: list[float], base_c: float) -> float:
    """Graus-dia de resfriamento: Σ max(0, T_média do dia − base) sobre os dias."""
    return sum(max(0.0, t - base_c) for t in temperaturas if t is not None)


def linha_de_base(amostras: list[dict], P: dict) -> dict:
    """Regressão linear simples y = a·x + b do período de base (aprendizado.reta, biblioteca padrão).
    amostras: [{mes, y, x}]. Devolve a, b, r², CV(RMSE) em % e se a base é longa e boa o bastante."""
    am = [s for s in amostras if s.get("y") is not None and s.get("x") is not None]
    n = len(am)
    if n < 3:
        return {"ok": False, "n": n, "a": None, "b": None, "r2": None, "cv_rmse_pct": None,
                "aviso": f"Só {n} meses com consumo e variável: a regressão precisa de pelo menos 3."}
    xs, ys = [s["x"] for s in am], [s["y"] for s in am]
    a, b, r2 = aprendizado.reta(xs, ys)
    sse = sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys))
    my = sum(ys) / n
    cv = math.sqrt(sse / (n - 2)) / my * 100 if n > 2 and my else None
    avisos = []
    if n < P["validacao.baseline_meses_min"]:
        avisos.append(f"Base de {n} meses: o recomendado é {int(P['validacao.baseline_meses_min'])} (um ciclo inteiro de operação).")
    if cv is not None and cv > P["validacao.baseline_cvrmse_max_pct"]:
        avisos.append(f"CV(RMSE) de {cv:.1f} %: acima de {P['validacao.baseline_cvrmse_max_pct']:.0f} %, o modelo explica pouco.")
    return {"ok": not avisos, "n": n, "a": a, "b": b, "r2": r2, "cv_rmse_pct": cv, "aviso": " ".join(avisos)}


def esperado(modelo: dict, x: float) -> float | None:
    return None if modelo.get("a") is None or x is None else modelo["a"] * x + modelo["b"]


def ipmvp_regressao(base_am: list[dict], rel_am: list[dict], P: dict, aj_nao_rotineiro: float = 0.0) -> dict:
    """IPMVP com linha de base por regressão: ajuste rotineiro = Σ consumo que a base daria nas condições do relatório
    − Σ consumo medido na base; economia pela equação geral (ipmvp_economia)."""
    mod = linha_de_base(base_am, P)
    if mod["a"] is None:
        return {"modelo": mod, "base": None, "relatorio": None, "ajuste_rotineiro": None, "ajuste_nao_rotineiro": aj_nao_rotineiro,
                "esperado_relatorio": None, "economia": ipmvp_economia(None, None)}
    yb = sum(s["y"] for s in base_am if s.get("y") is not None)
    rel = [s for s in rel_am if s.get("y") is not None and s.get("x") is not None]
    yr = sum(s["y"] for s in rel)
    er = sum(esperado(mod, s["x"]) for s in rel)
    aj = er - yb
    return {"modelo": mod, "base": yb, "relatorio": yr, "ajuste_rotineiro": aj, "ajuste_nao_rotineiro": aj_nao_rotineiro,
            "esperado_relatorio": er, "meses_relatorio": len(rel),
            "linhas": [dict(s, esperado=esperado(mod, s["x"])) for s in rel],
            "economia": ipmvp_economia(yb, yr, aj + (aj_nao_rotineiro or 0.0))}


# ══ Validação dos planos gravados ═════════════════════════════════════════════════════════════
def validar_plano(d: dict) -> tuple[dict | None, str]:
    if d.get("modulo") not in MODULOS or d["modulo"] in ("frota", "carbono"):
        return None, "módulo: solar, agua, energia ou turbinas (frota e carbono vêm sozinhos)"
    if not _ITEM.match(str(d.get("item") or "")):
        return None, "item: letras, números, ponto, hífen ou sublinhado (até 60)"
    if not str(d.get("fonte") or "").strip():
        return None, "diga a fonte do planejado (aba, projeto ou premissa)"
    meses = {}
    for k, v in (d.get("meses") or {}).items():
        if not _MES.match(str(k)) or isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            return None, f"mês {str(k)[:10]}: chave AAAA-MM ou MM e valor ≥ 0"
        meses[str(k)] = float(v)
    if not meses:
        return None, "sem nenhum mês planejado"
    clima = {}
    for k, v in (d.get("clima") or {}).items():
        if not _MES.match(str(k)) or isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            return None, f"clima esperado do mês {str(k)[:10]}: chave AAAA-MM ou MM e valor ≥ 0"
        clima[str(k)] = float(v)
    cfg = MODULOS[d["modulo"]]
    return {"modulo": d["modulo"], "item": d["item"], "nome": str(d.get("nome") or "").strip()[:80],
            "ativo": str(d.get("ativo") or "").strip()[:80], "grandeza": str(d.get("grandeza") or cfg["grandeza"] or ""),
            "unidade": str(d.get("unidade") or cfg["unidade"]), "fonte": str(d["fonte"]).strip()[:200], "meses": meses,
            "clima": clima, "premissa": str(d.get("premissa") or "").strip()[:80]}, ""


def validar_plano_mv(d: dict) -> tuple[dict | None, str]:
    """Plano de M&V da instalação (estilo IPMVP, citado só pelo nome). Opção D pede o programa de simulação, a versão e
    os arquivos de entrada e saída com o SHA-256. Papéis por função; a competência é só um campo (nunca presumida)."""
    if not isinstance(d, dict):
        return None, "plano inválido"
    s = lambda k, n=600: str(d.get(k) or "").strip()[:n]
    lst = lambda k: [str(x).strip()[:200] for x in (d.get(k) or []) if str(x).strip()][:40] if isinstance(d.get(k) or [], list) else []
    op = s("opcao", 1).upper()
    if op not in OPCOES_IPMVP:
        return None, "opção IPMVP: A, B, C ou D"
    for k, nome in (("escopo", "escopo"), ("fronteira", "fronteira de medição"), ("justificativa", "justificativa da opção"),
                    ("metodo", "método de cálculo")):
        if not s(k):
            return None, f"falta {nome}"
    for k in ("base_ini", "base_fim", "rel_ini", "rel_fim"):
        if s(k) and not re.fullmatch(r"\d{4}-\d{2}", s(k)):
            return None, f"{k}: AAAA-MM"
    if s("base_ini") and s("base_fim") and s("base_ini") > s("base_fim") or s("rel_ini") and s("rel_fim") and s("rel_ini") > s("rel_fim"):
        return None, "períodos: início antes do fim"
    if s("revisao_anual") and not _DATA.match(s("revisao_anual")):
        return None, "revisão anual: AAAA-MM-DD"
    papeis = []
    for x in (d.get("papeis") or [])[:20]:
        if not isinstance(x, dict) or x.get("papel") not in PAPEIS:
            return None, "papel: coleta, analise, arquivo ou relatorio"
        papeis.append({"papel": x["papel"], "pessoa": str(x.get("pessoa") or "").strip()[:80],
                       "competencia": str(x.get("competencia") or "").strip()[:120]})
    ecms = [{"id": str(x.get("id") or "").strip()[:60], "nome": str(x.get("nome") or "").strip()[:120]}
            for x in (d.get("ecms") or [])[:30] if isinstance(x, dict) and str(x.get("id") or "").strip()]
    sim = None
    if op == "D":
        x = d.get("simulacao") if isinstance(d.get("simulacao"), dict) else {}
        sw, ver = str(x.get("software") or "").strip()[:80], str(x.get("versao") or "").strip()[:40]
        if not sw or not ver:
            return None, "opção D: informe o programa de simulação e a versão"
        arqs = []
        for a in (x.get("arquivos") or [])[:40]:
            if not isinstance(a, dict) or not _SHA.match(str(a.get("sha256") or "").lower()):
                return None, "opção D: cada arquivo de entrada e saída com o SHA-256 (64 letras hexadecimais)"
            arqs.append({"nome": str(a.get("nome") or "").strip()[:160], "sha256": str(a["sha256"]).lower(),
                         "papel": "saida" if a.get("papel") == "saida" else "entrada"})
        if not arqs:
            return None, "opção D: guarde as cópias dos arquivos de entrada e saída (nome e SHA-256)"
        sim = {"software": sw, "versao": ver, "arquivos": arqs}
        for k in ("envoltoria_antes", "envoltoria_depois"):
            if isinstance(x.get(k), list):
                sim[k] = [{"nome": str(i.get("nome") or "")[:80], "area": float(i["area"]), "u": float(i["u"])} for i in x[k][:50]
                          if isinstance(i, dict) and isinstance(i.get("area"), (int, float)) and isinstance(i.get("u"), (int, float))]
        for k in ("ti", "cop"):
            if isinstance(x.get(k), (int, float)) and not isinstance(x.get(k), bool) and x[k] > 0:
                sim[k] = float(x[k])
    num_ = lambda k: (float(d[k]) if isinstance(d.get(k), (int, float)) and not isinstance(d.get(k), bool) and d[k] > 0 else None)
    return {"escopo": s("escopo"), "fronteira": s("fronteira"), "opcao": op, "justificativa": s("justificativa"),
            "metodo": s("metodo"), "fontes": lst("fontes"), "variaveis_independentes": lst("variaveis_independentes"),
            "fatores_estaticos": lst("fatores_estaticos"), "base_ini": s("base_ini", 7), "base_fim": s("base_fim", 7),
            "rel_ini": s("rel_ini", 7), "rel_fim": s("rel_fim", 7), "papeis": papeis, "formato": s("formato", 200),
            "periodicidade": s("periodicidade", 100), "qa": lst("qa"), "revisao_anual": s("revisao_anual", 10), "ecms": ecms,
            "area_m2": num_("area_m2"), "ocupantes": num_("ocupantes"), "simulacao": sim,
            "politica_faltantes": d.get("politica_faltantes") if d.get("politica_faltantes") in vn.POLITICAS else "excluir",
            "tarifa_kwh": num_("tarifa_kwh"), "tarifa_m3": num_("tarifa_m3"), "tarifa_fonte": s("tarifa_fonte", 200),
            "meta_economia": num_("meta_economia"), "cmms_automatico": d.get("cmms_automatico") is True,
            "faturas": {str(k)[:7]: float(v) for k, v in (d.get("faturas") or {}).items()
                        if re.fullmatch(r"\d{4}-\d{2}", str(k)) and isinstance(v, (int, float)) and not isinstance(v, bool)}
            if isinstance(d.get("faturas"), dict) else {},
            "perfil": d.get("perfil") if d.get("perfil") in vn.PERFIS else "geral", "pee": _pee(d.get("pee")) if d.get("perfil") == "pee" else None}, ""


def _pee(x) -> dict:
    """Campos do perfil PEE (ANEEL): números digitados com a fonte; as exigências ficam nas premissas validacao.pee.*."""
    x = x if isinstance(x, dict) else {}
    n = lambda v: float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None
    est = [{"nome": str(e.get("nome") or "")[:80], "N": int(e["N"]), "cv": n(e.get("cv")) or 0.5, "n_medido": int(e.get("n_medido") or 0),
            "media": n(e.get("media")), "desvio": n(e.get("desvio"))} for e in (x.get("estratos") or [])[:20]
           if isinstance(e, dict) and isinstance(e.get("N"), int) and e["N"] > 0]
    return {"energia_economizada_mwh_ano": n(x.get("energia_economizada_mwh_ano")), "reducao_demanda_ponta_kw": n(x.get("reducao_demanda_ponta_kw")),
            "rcb": n(x.get("rcb")), "rcb_entradas": {str(k)[:60]: n(v) for k, v in (x.get("rcb_entradas") or {}).items()} if isinstance(x.get("rcb_entradas"), dict) else {},
            "custo_mv": n(x.get("custo_mv")), "custo_total": n(x.get("custo_total")), "erro_pct": n(x.get("erro_pct")),
            "precisao_pct": n(x.get("precisao_pct")), "confianca_pct": n(x.get("confianca_pct")), "estratos": est,
            "fonte": str(x.get("fonte") or "")[:200]}


def alertas_medidor(m: dict, hoje: str) -> list[dict]:
    """Calibração vencida ou sem data, e exatidão desconhecida ([CONFERIR])."""
    out = []
    if not m.get("cal_proxima"):
        out.append({"tipo": "sem_calibracao", "texto": "Sem data da próxima calibração [CONFERIR]."})
    elif m["cal_proxima"] < hoje:
        out.append({"tipo": "calibracao_vencida", "texto": f"Calibração vencida em {m['cal_proxima']}."})
    if m.get("exatidao_pct") is None:
        out.append({"tipo": "exatidao_desconhecida", "texto": "Exatidão do medidor desconhecida [CONFERIR]."})
    if not m.get("certificado_sha256"):
        out.append({"tipo": "sem_certificado", "texto": "Sem certificado de calibração (arquivo ou SHA-256)."})
    return out


def enpis(plano_mv: dict | None, consumo_base: dict, consumo_rel: dict) -> list[dict]:
    """Indicadores de desempenho (EnPI) e linha de base energética (EnB) no conceito da ISO 50006 (citada só pelo nome):
    consumo ÷ normalizador no período de base × no de relatório. consumo_*: {energia_kwh, agua_m3, producao, frota_l, frota_km}."""
    pm = plano_mv or {}
    defs = [("kWh/m²", "energia_kwh", pm.get("area_m2"), "área do plano de M&V"),
            ("kWh por unidade produzida", "energia_kwh", "producao", "produção da Gestão"),
            ("m³/pessoa", "agua_m3", pm.get("ocupantes"), "ocupantes do plano de M&V"),
            ("L/100 km", "frota_l", "frota_km", "km medidos da frota")]
    out = []
    for nome, k, norm, fonte in defs:
        def val(c):
            v = c.get(k)
            d = c.get(norm) if isinstance(norm, str) else norm
            if v is None or not d:
                return None
            return v / d * (100 if nome == "L/100 km" else 1)
        b, r = val(consumo_base), val(consumo_rel)
        out.append({"enpi": nome, "fonte_normalizador": fonte, "base": b, "relatorio": r,
                    "variacao_pct": (r - b) / b * 100 if b and r is not None else None,
                    "enb": consumo_base.get(k), "sem_dado": b is None and r is None})
    return out


def relatorio_blocos(est: dict) -> dict:
    """Relatório padrão de M&V em blocos (o mesmo modelo de documentos.py e physis-odf.js), com as seções fixas
    SECOES_RELATORIO; o anexo liga cada número à fonte (leituras, fator, premissas, ajustes e versão do modelo)."""
    pm = (est.get("plano_mv") or {}).get("atual") or {}
    b = [{"h": 1, "t": "Relatório de medição e verificação · planejado × medido"}]
    sec = iter(SECOES_RELATORIO)
    b.append({"h": 2, "t": next(sec)})
    b.append({"t": f"Escopo: {pm.get('escopo') or '[A DEFINIR]'}. Fronteira de medição: {pm.get('fronteira') or '[A DEFINIR]'}."})
    b.append({"t": "Medidas de eficiência (ECM): " + (", ".join(e["nome"] or e["id"] for e in pm.get("ecms") or []) or "[A DEFINIR]") + "."})
    b.append({"h": 2, "t": next(sec)})
    op = pm.get("opcao")
    b.append({"t": f"Opção IPMVP: {op + ' · ' + OPCOES_IPMVP[op] if op else '[A DEFINIR]'}. Justificativa: {pm.get('justificativa') or '[A DEFINIR]'}. "
                   f"Método: {pm.get('metodo') or '[A DEFINIR]'}."})
    if op == "D" and pm.get("simulacao"):
        s = pm["simulacao"]
        b.append({"t": f"Simulação: {s['software']} versão {s['versao']}."})
        b.append({"tabela": {"cab": ["Arquivo", "Papel", "SHA-256"], "linhas": [[a["nome"], a["papel"], a["sha256"]] for a in s["arquivos"]],
                             "legenda": "Cópias dos arquivos de entrada e saída da simulação"}})
    b.append({"h": 2, "t": next(sec)})
    for m in est.get("modulos") or []:
        if m.get("tem_plano"):
            b.append({"tabela": {"cab": ["Mês", "Planejado", "Medido", "Desvio (%)"], "legenda": m["nome"] + " (" + m["unidade"] + ")",
                                 "linhas": [[l["mes"], _f(l["planejado"]), _f(l["medido"]), _f(l["pct"], 1)] for l in m["linhas"]]}})
    q = est.get("qualidade") or []
    if q:
        b.append({"tabela": {"cab": ["Medidor", "Granularidade", "Perda de dados (%)", "Marcados"], "legenda": "Qualidade dos dados",
                             "linhas": [[x["ativo"], x["granularidade"], _f(x["perda_pct"], 1), str(sum(x["resumo"].values()))] for x in q]}})
    b.append({"h": 2, "t": next(sec)})
    b.append({"tabela": {"cab": ["Módulo", "Planejado", "Medido", "Desvio (%)", "Primeiro mês fora"], "legenda": "Comparação com as metas do plano",
                         "linhas": [[m["nome"], _f((m.get("total") or {}).get("planejado")), _f((m.get("total") or {}).get("medido")),
                                     _f((m.get("total") or {}).get("pct"), 1), (m.get("quando") or {}).get("primeiro_mes", "—") if m.get("tem_plano") else m["sem_plano"]]
                                    for m in est.get("modulos") or []]}})
    if est.get("enpis"):
        b.append({"tabela": {"cab": ["EnPI", "Base", "Relatório", "Variação (%)"], "legenda": "Indicadores de desempenho (EnPI)",
                             "linhas": [[e["enpi"], _f(e["base"], 2), _f(e["relatorio"], 2), _f(e["variacao_pct"], 1)] for e in est["enpis"]]}})
    pee = est.get("pee")
    if pee:
        b.append({"tabela": {"cab": ["Campo do PEE (ANEEL)", "Valor"], "legenda": "Perfil PEE (ANEEL): números do projeto; exigências aguardando o Guia de M&V",
                             "linhas": [["Energia economizada (MWh/ano)", _f(pee["energia_economizada_mwh_ano"], 1)], ["Redução de demanda na ponta (kW)", _f(pee["reducao_demanda_ponta_kw"], 1)],
                                        ["RCB", _f(pee["rcb"], 2)], ["Custo da M&V / custo total (%)", _f(pee["custo_check"]["parte_pct"], 1) + " · " + pee["custo_check"]["situacao"]],
                                        ["Erro / precisão / confiança alcançados (%)", " / ".join(_f(pee[k], 1) for k in ("erro_pct", "precisao_pct", "confianca_pct"))]]}})
    b.append({"h": 2, "t": next(sec)})
    for x in est.get("mv2") or []:
        i = x.get("incerteza") or {}
        b.append({"t": f"{x['nome']}: incerteza fracional {_f(i.get('incerteza_pct'), 1)} % a {_f(i.get('confianca_pct'), 0)} % de confiança; "
                       f"limite {_f(i.get('limite_pct'), 0)} %: {i.get('veredito', 'sem dado')}."})
        mc = x.get("monte_carlo") or {}
        if mc:
            b.append({"t": f"Monte Carlo: economia {_f(mc.get('economia'))} com IC de {_f(mc.get('confianca_pct'))} % de {_f(mc.get('ic_inf'))} a {_f(mc.get('ic_sup'))}; "
                           "fontes: " + ", ".join(f"{s['nome']} {_f(s['parte_pct'])} %" for s in x.get("sensibilidade") or []) + "."})
    if not est.get("mv2"):
        b.append({"t": "Sem modelo diário: defina os períodos de base e de relatório no plano de M&V."})
    b.append({"h": 2, "t": next(sec)})
    b.append({"t": [f"{m['nome']} · {x['mes']}: {', '.join(c['nome'] + ' (' + str(c['confianca']) + ')' for c in x['causas'])}"
                    for m in est.get("modulos") or [] for x in m.get("explicacoes") or []] or ["Nenhum mês fora do limite."], "lista": True})
    b.append({"t": [f"Inspeção {i['ecm']} em {i['dia']}: {'operando' if i['operando'] else 'NÃO operando'}" for i in est.get("inspecoes") or []]
              or ["Nenhuma inspeção periódica registrada."], "lista": True})
    b.append({"h": 2, "t": next(sec)})
    acoes = {ACOES[c["codigo"]] for m in est.get("modulos") or [] for x in m.get("explicacoes") or [] for c in x["causas"][:1]}
    acoes |= {a["acao"] for x in est.get("mv2") or [] for a in x.get("alarmes") or []}
    b.append({"t": sorted(acoes) or ["Manter o plano de coleta e a revisão anual."], "lista": True})
    b.append({"h": 2, "t": next(sec)})
    r = est.get("rastreio") or {}
    b.append({"tabela": {"cab": ["Número", "Fonte"], "legenda": "Rastreabilidade",
                         "linhas": [[k, v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, sort_keys=True)] for k, v in sorted(r.items())]}})
    return {"blocos": b, "secoes": SECOES_RELATORIO}


def _f(v, c: int = 0) -> str:
    return "—" if v is None else f"{v:.{c}f}".replace(".", ",")


def _mes_de(ts: float) -> str:
    return datetime.fromtimestamp(ts, FUSO).strftime("%Y-%m")


class Validacao:
    """Leitura do medido no banco do hub, planos gravados e o estado da aba (GET /api/validacao/estado)."""

    COLS = ("id", "modulo", "item", "nome", "ativo", "grandeza", "unidade", "fonte", "meses", "clima", "premissa",
            "criado", "atualizado", "por")

    def __init__(self, hub, relogio=None, premissas_base=None, frota=None, fatores=None):
        self.hub = hub
        self.relogio = relogio or hub.relogio
        self.P = premissas(premissas_base)
        self.frota = frota                     # frota_mod.Frota do servidor (None: a frota fica "sem plano")
        self._F = fatores
        with hub._trava:
            hub._db.executescript(ESQUEMA)
            hub._db.commit()

    @property
    def _db(self):
        return self.hub._db

    def F(self) -> dict:
        if self._F is None:
            self._F = frota_mod.fatores() or {}
        return self._F

    # ── planos ────────────────────────────────────────────────────────────────────────────
    def planos(self, modulo: str | None = None) -> list[dict]:
        sql = f"SELECT {','.join(self.COLS)} FROM validacao_plano" + (" WHERE modulo=?" if modulo else "") + " ORDER BY modulo, item"
        out = []
        for r in self._db.execute(sql, (modulo,) if modulo else ()):
            d = dict(zip(self.COLS, r))
            d["meses"], d["clima"] = json.loads(d["meses"] or "{}"), json.loads(d["clima"] or "{}")
            out.append(d)
        return out

    def gravar_plano(self, d: dict, quem: str) -> dict:
        p, erro = validar_plano(d)
        if erro:
            return {"ok": False, "erro": erro}
        agora = self.relogio()
        with self.hub._trava:
            self._db.execute(
                "INSERT INTO validacao_plano(modulo,item,nome,ativo,grandeza,unidade,fonte,meses,clima,premissa,criado,atualizado,por) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(modulo,item) DO UPDATE SET nome=excluded.nome, ativo=excluded.ativo, "
                "grandeza=excluded.grandeza, unidade=excluded.unidade, fonte=excluded.fonte, meses=excluded.meses, "
                "clima=excluded.clima, premissa=excluded.premissa, atualizado=excluded.atualizado, por=excluded.por",
                (p["modulo"], p["item"], p["nome"], p["ativo"], p["grandeza"], p["unidade"], p["fonte"],
                 json.dumps(p["meses"]), json.dumps(p["clima"]), p["premissa"], agora, agora, quem))
            self._db.commit()
            rid = self._db.execute("SELECT id FROM validacao_plano WHERE modulo=? AND item=?", (p["modulo"], p["item"])).fetchone()[0]
        return {"ok": True, "id": rid}

    def remover_plano(self, pid: int, quem: str) -> dict:
        with self.hub._trava:
            n = self._db.execute("DELETE FROM validacao_plano WHERE id=?", (int(pid),)).rowcount
            self._db.commit()
        return {"ok": True} if n else {"ok": False, "erro": "plano não encontrado", "codigo": 404}

    # ── medido ────────────────────────────────────────────────────────────────────────────
    def medido_mensal(self, ativo: str, grandeza: str, meses: list[str]) -> dict:
        """{mes: {valor, dias, dias_mes}}: média do dia × 24 h (kW → kWh/dia; m³/h → m³/dia), somada no mês."""
        if not ativo or not grandeza or not meses:
            return {}
        t0 = datetime.strptime(meses[0] + "-01", "%Y-%m-%d").replace(tzinfo=FUSO).timestamp()
        lim = self.serie_limpa(ativo, grandeza, t0)
        por: dict[str, list[float]] = {}
        seqs: dict[str, list[int]] = {}
        for o in lim["pontos"]:
            if o["valor"] is None:
                continue                                       # marcado na limpeza: o original fica na tabela medicao
            d = aprendizado._dia(o["ts"])
            por.setdefault(d, []).append(o["valor"])
            seqs.setdefault(d[:7], []).append(o["id"])
        out: dict[str, dict] = {}
        for dia, vals in por.items():
            x = out.setdefault(dia[:7], {"valor": 0.0, "dias": 0, "dias_mes": dias_do_mes(dia[:7])})
            x["valor"] += sum(vals) / len(vals) * 24.0
            x["dias"] += 1
        for m, s in seqs.items():
            out[m]["leituras"] = {"seq_min": min(s), "seq_max": max(s), "n": len(s)}
        # antes da primeira leitura do medidor: sem dado (None); depois dela, mês sem nenhuma leitura = 0 dias (falha de dado)
        primeiro = min(out) if out else None
        return {m: out.get(m) or {"valor": None if primeiro is None or m < primeiro else 0.0, "dias": 0, "dias_mes": dias_do_mes(m)}
                for m in meses}

    def serie_limpa(self, ativo: str, grandeza: str, desde: float) -> dict:
        """As leituras do medidor desde `desde`, limpas (validacao_modelos.limpar_serie): cada ponto guarda o original e a
        marca; a tabela medicao nunca é alterada. A faixa vem do cadastro do medidor ou do contrato physis/1."""
        pts = [{"id": s, "ts": ts, "valor": v} for s, ts, v in self._db.execute(
            "SELECT seq, ts, valor FROM medicao WHERE ativo=? AND grandeza=? AND ts>=? ORDER BY seq", (ativo, grandeza, int(desde)))]
        med = self.medidor(ativo) or {}
        f = nucleo.FAIXAS.get(grandeza)
        faixa = (med.get("faixa_min", f[0] if f else None), med.get("faixa_max", f[1] if f else None))
        return vm.limpar_serie(pts, self.P, grandeza, faixa, self.relogio())

    def diario(self, ativo: str, grandeza: str, desde: float) -> dict:
        """{dia: {y (média × 24 h), x (temperatura média do ar)}} na granularidade de dia, só com pontos válidos."""
        por: dict[str, list[float]] = {}
        for o in self.serie_limpa(ativo, grandeza, desde)["pontos"]:
            if o["valor"] is not None:
                por.setdefault(aprendizado._dia(o["ts"]), []).append(o["valor"])
        temp: dict[str, list[float]] = {}
        for ts, v in self._db.execute("SELECT ts, valor FROM medicao WHERE grandeza='temperatura' AND ativo LIKE '%-ar' AND ts>=?", (int(desde),)):
            temp.setdefault(aprendizado._dia(ts), []).append(v)
        return {d: {"y": sum(v) / len(v) * 24, "x": (sum(temp[d]) / len(temp[d])) if temp.get(d) else None} for d, v in por.items()}

    # ── plano de M&V, medidores, lições e inspeções (tudo no registro encadeado do hub) ──
    def plano_mv(self) -> dict:
        vs = [{"versao": v, "dados": json.loads(d), "motivo": m, "por": por, "quando": q, "registro": r}
              for v, d, m, por, q, r in self._db.execute("SELECT versao, dados, motivo, por, quando, registro FROM validacao_plano_mv ORDER BY versao")]
        return {"atual": vs[-1]["dados"] if vs else None, "versao": vs[-1]["versao"] if vs else 0,
                "versoes": [{k: v for k, v in x.items() if k != "dados"} for x in vs]}

    def gravar_plano_mv(self, d: dict, motivo: str, quem: str) -> dict:
        pl, erro = validar_plano_mv(d)
        if erro:
            return {"ok": False, "erro": erro}
        if not str(motivo or "").strip():
            return {"ok": False, "erro": "diga o motivo da mudança"}
        texto = json.dumps(pl, ensure_ascii=False, sort_keys=True)
        anterior = self.plano_mv()
        rid = self.hub.registrar("validacao_plano_mv", quem, {"versao": anterior["versao"] + 1, "motivo": str(motivo).strip()[:300],
                                                               "sha256": hashlib.sha256(texto.encode()).hexdigest()})
        with self.hub._trava:
            cur = self._db.execute("INSERT INTO validacao_plano_mv(dados,motivo,por,quando,registro) VALUES(?,?,?,?,?)",
                                   (texto, str(motivo).strip()[:300], quem, self.relogio(), rid))
            self._db.commit()
        return {"ok": True, "versao": cur.lastrowid, "registro": rid}

    def medidores(self) -> list[dict]:
        hoje = datetime.fromtimestamp(self.relogio(), FUSO).strftime("%Y-%m-%d")
        out = []
        for i, a, d in self._db.execute("SELECT id, ativo, dados FROM validacao_medidor ORDER BY ativo"):
            m = dict(json.loads(d), id=i, ativo=a)
            m["alertas"] = alertas_medidor(m, hoje)
            out.append(m)
        return out

    def medidor(self, ativo: str) -> dict | None:
        r = self._db.execute("SELECT dados FROM validacao_medidor WHERE ativo=?", (ativo,)).fetchone()
        return json.loads(r[0]) if r else None

    def gravar_medidor(self, d: dict, quem: str) -> dict:
        for k in ("comissionamento", "cal_ultima", "cal_proxima"):
            if d.get(k) and not _DATA.match(str(d[k])):
                return {"ok": False, "erro": f"{k}: AAAA-MM-DD"}
        if d.get("certificado_sha256") and not _SHA.match(str(d["certificado_sha256"]).lower()):
            return {"ok": False, "erro": "certificado: SHA-256 com 64 letras hexadecimais"}
        dados = {k: d.get(k) for k in ESQUEMAS["validacao_medidor"] if k not in ("id", "ativo") and d.get(k) is not None}
        if "certificado_sha256" in dados:
            dados["certificado_sha256"] = dados["certificado_sha256"].lower()
        rid = self.hub.registrar("validacao_medidor", quem, {"ativo": d["ativo"], "dados": dados})
        with self.hub._trava:
            self._db.execute("INSERT INTO validacao_medidor(ativo,dados,atualizado,por) VALUES(?,?,?,?) ON CONFLICT(ativo) DO UPDATE SET "
                             "dados=excluded.dados, atualizado=excluded.atualizado, por=excluded.por",
                             (d["ativo"], json.dumps(dados, ensure_ascii=False), self.relogio(), quem))
            self._db.commit()
        return {"ok": True, "registro": rid}

    def licoes(self) -> list[dict]:
        return [{"id": i, "texto": t_, "quando": q, "por": p} for i, t_, q, p in
                self._db.execute("SELECT id, texto, quando, por FROM validacao_licao ORDER BY id DESC LIMIT 200")]

    def gravar_licao(self, texto: str, quem: str) -> dict:
        if not str(texto or "").strip():
            return {"ok": False, "erro": "escreva a lição"}
        rid = self.hub.registrar("validacao_licao", quem, {"texto": str(texto).strip()[:2000]})
        with self.hub._trava:
            self._db.execute("INSERT INTO validacao_licao(texto,quando,por,registro) VALUES(?,?,?,?)", (str(texto).strip()[:2000], self.relogio(), quem, rid))
            self._db.commit()
        return {"ok": True, "registro": rid}

    def inspecoes(self) -> list[dict]:
        return [{"id": i, "ecm": e, "operando": bool(o), "obs": ob, "dia": datetime.fromtimestamp(q, FUSO).strftime("%Y-%m-%d"), "por": p}
                for i, e, o, ob, q, p in self._db.execute("SELECT id, ecm, operando, obs, quando, por FROM validacao_inspecao ORDER BY id DESC LIMIT 500")]

    def gravar_inspecao(self, d: dict, quem: str) -> dict:
        rid = self.hub.registrar("validacao_inspecao", quem, {"ecm": d["ecm"], "operando": bool(d["operando"]), "obs": d.get("obs") or ""})
        with self.hub._trava:
            self._db.execute("INSERT INTO validacao_inspecao(ecm,operando,obs,quando,por,registro) VALUES(?,?,?,?,?,?)",
                             (d["ecm"][:60], int(bool(d["operando"])), str(d.get("obs") or "")[:500], self.relogio(), quem, rid))
            self._db.commit()
        return {"ok": True, "registro": rid}

    def _tarefa_do_alerta(self, chave: str, quem: str) -> dict:
        r = self._db.execute("SELECT dados FROM validacao_alerta WHERE chave=?", (chave,)).fetchone()
        return self.criar_tarefa(json.loads(r[0]), quem) if r else {"ok": False, "erro": "alerta não encontrado", "codigo": 404}

    def _verificar_item(self, item: str, quem: str) -> dict:
        x = next((m for m in self.mv2(self.plano_mv()["atual"], self.planos()) if m["item"] == item), None)
        if not x or x.get("economia") is None or not x.get("monte_carlo"):
            return {"ok": False, "erro": "sem economia calculada para este item", "codigo": 404}
        return self.verificar_resultado(x, quem)

    def tarefas(self, pm: dict | None, inspecoes: list[dict], medidores: list[dict]) -> list[dict]:
        """Revisão anual do plano de M&V, inspeções periódicas das ECM e calibrações: o que está pendente ou atrasado."""
        hoje = datetime.fromtimestamp(self.relogio(), FUSO).date()
        out = []
        ra = (pm or {}).get("revisao_anual")
        if not pm:
            out.append({"tipo": "plano_mv", "situacao": "pendente", "texto": "Escrever o plano de M&V da instalação."})
        elif not ra:
            out.append({"tipo": "revisao_anual", "situacao": "pendente", "texto": "Marcar a data da revisão anual do plano de M&V."})
        else:
            dias = (datetime.strptime(ra, "%Y-%m-%d").date() - hoje).days
            if dias < 0:
                out.append({"tipo": "revisao_anual", "situacao": "atrasada", "texto": f"Revisão anual do plano de M&V atrasada desde {ra}."})
            elif dias <= self.P["validacao.revisao_aviso_dias"]:
                out.append({"tipo": "revisao_anual", "situacao": "pendente", "texto": f"Revisão anual do plano de M&V em {ra}."})
        for e in (pm or {}).get("ecms") or []:
            ult = next((i for i in inspecoes if i["ecm"] == e["id"]), None)
            if not ult or (hoje - datetime.strptime(ult["dia"], "%Y-%m-%d").date()).days > self.P["validacao.inspecao_dias_max"]:
                out.append({"tipo": "inspecao", "situacao": "atrasada" if ult else "pendente", "ecm": e["id"],
                            "texto": f"Inspeção periódica da medida {e['nome'] or e['id']}: confirmar que continua operando."})
            elif not ult["operando"]:
                out.append({"tipo": "inspecao", "situacao": "atrasada", "ecm": e["id"], "texto": f"A medida {e['nome'] or e['id']} não estava operando na última inspeção."})
        for m in medidores:
            for a in m["alertas"]:
                if a["tipo"] in ("calibracao_vencida", "sem_calibracao"):
                    out.append({"tipo": "calibracao", "situacao": "atrasada" if a["tipo"] == "calibracao_vencida" else "pendente",
                                "ativo": m["ativo"], "texto": f"{m['ativo']}: {a['texto']}"})
        return out

    def temperaturas_dia(self, desde: float) -> tuple[dict, str]:
        """Temperatura média do dia: a estação da Resiliência (temperatura do ar no hub) ou, sem ela, a previsão/observação
        de fonte aberta que o hub já guarda (clima_fonte, Open-Meteo, com cache no servidor e sem internet na hora)."""
        temp: dict[str, list[float]] = {}
        for ts, v in self._db.execute("SELECT ts, valor FROM medicao WHERE grandeza='temperatura' AND ativo LIKE '%-ar' AND ts>=?", (int(desde),)):
            temp.setdefault(aprendizado._dia(ts), []).append(v)
        if temp:
            return {d: sum(v) / len(v) for d, v in temp.items()}, "estação do lugar (temperatura do ar)"
        try:
            r = self._db.execute("SELECT dados FROM clima_fonte WHERE fonte='openmeteo'").fetchone()
            dias = (json.loads(r[0]) or {}).get("dias") or [] if r else []
            out = {x["dia"]: (x["tmax"] + x["tmin"]) / 2 for x in dias if x.get("tmax") is not None and x.get("tmin") is not None}
            if out:
                return out, "fonte aberta guardada no hub (Open-Meteo, cache)"
        except Exception:      # noqa: BLE001 — banco sem a tabela do clima
            pass
        return {}, "sem temperatura"

    def nres(self, item: str | None = None) -> list[dict]:
        sql = "SELECT chave, item, dados, situacao, por, motivo, registro FROM validacao_nre" + (" WHERE item=?" if item else "") + " ORDER BY criado"
        return [dict(json.loads(dd), chave=c, item=i, situacao=s_, por=p_, motivo=m_, registro=r_)
                for c, i, dd, s_, p_, m_, r_ in self._db.execute(sql, (item,) if item else ())]

    def decidir_nre(self, chave: str, aprovar: bool, motivo: str, quem: str) -> dict:
        """Ajuste não rotineiro só vale depois da aprovação de uma pessoa; a decisão vai para o registro encadeado."""
        r = self._db.execute("SELECT situacao FROM validacao_nre WHERE chave=?", (chave,)).fetchone()
        if not r:
            return {"ok": False, "erro": "evento não encontrado", "codigo": 404}
        if not str(motivo or "").strip():
            return {"ok": False, "erro": "diga o motivo"}
        sit = "aprovado" if aprovar else "recusado"
        rid = self.hub.registrar("validacao_nre", quem, {"chave": chave, "situacao": sit, "motivo": str(motivo)[:300]})
        with self.hub._trava:
            self._db.execute("UPDATE validacao_nre SET situacao=?, por=?, motivo=?, registro=?, atualizado=? WHERE chave=?",
                             (sit, quem, str(motivo)[:300], rid, self.relogio(), chave))
            self._db.commit()
        return {"ok": True, "situacao": sit, "registro": rid}

    def criar_tarefa(self, alerta: dict, quem: str) -> dict:
        """Ciclo fechado com a manutenção: o alerta vira tarefa na Gestão (chave gestao-physis:validacao-tarefas), com a
        evidência. Idempotente: o mesmo alerta não abre duas tarefas."""
        if self._db.execute("SELECT 1 FROM validacao_tarefa WHERE chave=?", (alerta["chave"],)).fetchone():
            return {"ok": True, "ja_existia": True}
        tarefa = {"id": "va-" + alerta["chave"][:12], "titulo": f"M&V: {alerta.get('causa_nome', 'desvio')} em {alerta.get('item')} "
                                                               f"({alerta.get('inicio')} a {alerta.get('fim')})",
                  "origem": "validacao", "estado": "aberta", "acao": alerta.get("acao", ""),
                  "evidencia": {k: alerta.get(k) for k in ("item", "inicio", "fim", "dias", "esperado", "medido", "desvio_pct", "lado",
                                                           "excesso", "rs_em_risco", "causa", "chave")},
                  "criado": datetime.fromtimestamp(self.relogio(), FUSO).strftime("%Y-%m-%d"), "por": quem}
        with self.hub._trava:
            self._db.execute("INSERT INTO validacao_tarefa(chave,dados,criado,por) VALUES(?,?,?,?)",
                             (alerta["chave"], json.dumps(tarefa, ensure_ascii=False), self.relogio(), quem))
            self._db.commit()
        todas = [json.loads(r[0]) for r in self._db.execute("SELECT dados FROM validacao_tarefa ORDER BY criado")]
        valor = json.dumps({"_formato": "physis-validacao-tarefas/1", "tarefas": todas}, ensure_ascii=False)
        for _ in range(3):
            atual = self.hub.gestao_ler().get(CHAVE_GESTAO)
            if self.hub.gestao_gravar(CHAVE_GESTAO, valor, atual["versao"] if atual else 0, quem).get("ok"):
                break
        self.hub.registrar("validacao_tarefa", quem, {"chave": alerta["chave"], "tarefa": tarefa["id"]})
        return {"ok": True, "tarefa": tarefa}

    def verificar_resultado(self, x: dict, quem: str) -> dict:
        """Resultado de economia verificado (período, valor, IC, resumo do modelo e dos dados) vira um registro SHA-256 que
        entra no lote diário de integridade (integridade.registros_do_dia): terceiros conferem sem ver os dados brutos."""
        mc = x.get("monte_carlo") or {}
        dados = {"item": x["item"], "periodo": x["periodo"], "economia": x["economia"], "ic_inf": mc.get("ic_inf"), "ic_sup": mc.get("ic_sup"),
                 "confianca_pct": mc.get("confianca_pct"), "unidade": x.get("unidade", "kWh"), "modelo_hash": (x.get("modelo_versao") or {}).get("hash"),
                 "dados_hash": x.get("dados_hash"), "versao_codigo": VERSAO_CODIGO}
        rz = vn.resumo(dados)
        rid = self.hub.registrar("validacao_resultado", quem, dict(dados, resumo=rz))
        with self.hub._trava:
            self._db.execute("INSERT INTO validacao_resultado(item,dados,resumo,quando,por,registro) VALUES(?,?,?,?,?,?)",
                             (x["item"], json.dumps(dados, ensure_ascii=False, sort_keys=True), rz, self.relogio(), quem, rid))
            self._db.commit()
        return {"ok": True, "resumo": rz, "registro": rid, "dados": dados}

    def mv2(self, pm: dict | None, planos: list[dict], com_pacote: bool = False) -> list[dict]:
        """Núcleo M&V 2.0, por medidor de energia ou água com plano: dados de intervalo (granularidade nativa, limpos, com a
        política de faltantes do plano), modelo diário escolhido por validação cruzada (2P a 5P e k-NN) e modelo horário,
        retreinado a cada ciclo (versão com hash), deriva do modelo e do sensor (CUSUM), economia acumulada, Monte Carlo
        com sensibilidade, incerteza fracional, eventos não rotineiros com aprovação, FDD contra o intervalo de previsão,
        projeção por persistência, R$ em risco, tarefa na Gestão e conferência com a fatura."""
        if not pm or not (pm.get("base_ini") and pm.get("base_fim") and pm.get("rel_ini")):
            return []
        out = []
        t0 = datetime.strptime(pm["base_ini"] + "-01", "%Y-%m-%d").replace(tzinfo=FUSO).timestamp()
        rel_fim = pm.get("rel_fim") or "9999-12"
        temps, fonte_t = self.temperaturas_dia(t0)
        pol = pm.get("politica_faltantes") or "excluir"
        for p in planos:
            if p["modulo"] not in ("energia", "agua") or not p["ativo"]:
                continue
            lim = self.serie_limpa(p["ativo"], p["grandeza"], t0)
            ag = vn.agregar(lim["pontos"], FUSO, pol, self.P["validacao.cobertura_min_pct"])
            dias = ag["dias"]
            usa = lambda d: not dias[d].get("excluido") and temps.get(d) is not None
            base = [(d, temps[d], dias[d]["y"]) for d in sorted(dias) if pm["base_ini"] <= d[:7] <= pm["base_fim"] and usa(d)]
            xs, ys = [b[1] for b in base], [b[2] for b in base]
            esc = vn.escolher_por_cv(xs, ys, self.P) if len(xs) >= 10 else {"candidatos": [], "escolhido": None}
            mod = esc["escolhido"]
            horas_base = {h: v for h, v in ag["horas"].items() if pm["base_ini"] <= h[:7] <= pm["base_fim"]}
            hor = vn.ajustar_horario([(h, v, temps.get(h[:10])) for h, v in sorted(horas_base.items()) if temps.get(h[:10]) is not None])
            brutos = [{"id": o["id"], "ts": o["ts"], "valor": o["original"]} for o in lim["pontos"]]
            dados_hash = vn.resumo(brutos)
            ciclo = datetime.fromtimestamp(self.relogio(), FUSO).strftime("%Y-%m")
            ver = vn.versao_modelo(mod, dados_hash, ciclo) if mod else None
            if ver:                                  # retreino a cada ciclo; versão nova só quando dados ou parâmetros mudam
                with self.hub._trava:
                    self._db.execute("INSERT OR IGNORE INTO validacao_modelo(hash,item,ciclo,parametros,dados_hash,criado) VALUES(?,?,?,?,?,?)",
                                     (ver["hash"], p["item"], ciclo, json.dumps(ver["parametros"]), dados_hash, self.relogio()))
                    self._db.commit()
            rel_dias = [d for d in sorted(dias) if pm["rel_ini"] <= d[:7] <= rel_fim and temps.get(d) is not None]
            imput = 0
            serie_in = []
            for d in rel_dias:
                if dias[d].get("excluido"):
                    if pol == "modelo" and mod:
                        serie_in.append({"dia": d, "x": temps[d], "y": vm.prever(mod, temps[d])})
                        imput += 1
                    continue
                serie_in.append({"dia": d, "x": temps[d], "y": dias[d]["y"]})
                imput += 1 if dias[d].get("imputados") else 0
            serie = vm.economia_acumulada(mod, serie_in)
            esp, med = sum(s["esperado"] for s in serie), sum(s["medido"] for s in serie)
            econ = esp - med if serie else None
            res_b = [y - vm.prever(mod, x) for x, y in zip(xs, ys)] if mod else []
            se = (mod["metricas"].get("erro_padrao") or 0.0) if mod else 0.0
            rho = vm.autocorrelacao(res_b)
            inc = vm.incerteza_economia(mod["metricas"]["cv_rmse_pct"] if mod else None, len(xs), len(serie),
                                        econ / esp if econ is not None and esp else None, self.P, mod["metricas"]["p"] if mod else 2, rho)
            medr = self.medidor(p["ativo"]) or {}
            mc_args = {"esperado": esp, "medido": med, "m_dias": len(serie), "erro_padrao": se, "rho": rho,
                       "exatidao_pct": medr.get("exatidao_pct"), "imputados": imput}
            mc = vn.monte_carlo(**mc_args, P=self.P, semente=dados_hash) if serie and mod else None
            sens = vn.sensibilidade(mc_args, self.P, dados_hash) if mc else []
            # deriva: do modelo (CUSUM dos resíduos do relatório em torno do nível do 1º mês) e do sensor (carga de base)
            res_r = [s["medido"] - s["esperado"] for s in serie]
            d_mod = vn.cusum(res_r, self.P, media=statistics.mean(res_r[:30]) if len(res_r) >= 30 else None, desvio=se or None)
            minimos: dict[str, float] = {}
            for h, v in ag["horas"].items():
                minimos[h[:10]] = min(minimos.get(h[:10], v), v)
            bl_base = [v for d, v in sorted(minimos.items()) if pm["base_ini"] <= d[:7] <= pm["base_fim"]]
            fat_dif = [(sum(x["y"] for d, x in dias.items() if d[:7] == mes) - v) / v for mes, v in sorted((pm.get("faturas") or {}).items()) if v]
            if len(fat_dif) >= 3:                 # referência independente: a fatura da distribuidora (CUSUM da diferença mensal)
                d_sen = dict(vn.cusum(fat_dif, self.P, media=0.0, desvio=statistics.pstdev(fat_dif) or 0.01), referencia="fatura")
            else:                                 # sem fatura: a carga de base do período de base (referência fraca: a medida também a move)
                ref = bl_base
                d_sen = dict(vn.cusum([v for _, v in sorted(minimos.items())], self.P, media=statistics.mean(ref) if len(ref) >= 3 else None,
                                      desvio=statistics.pstdev(ref) if len(ref) >= 3 else None), referencia="carga de base do período de base (confirme com a fatura)")
            # eventos não rotineiros: pendentes até a aprovação de uma pessoa
            horas_rel = {h: v for h, v in ag["horas"].items() if pm["rel_ini"] <= h[:7] <= rel_fim}
            horas_res = {h: v - vn.prever_horario(hor, h, temps[h[:10]]) for h, v in horas_rel.items() if hor and temps.get(h[:10]) is not None}
            nre = vn.detectar_nre([(s["dia"], s["medido"] - s["esperado"]) for s in serie], esp / len(serie) if serie else 0, self.P,
                                  horas_res or None)
            if nre:
                chave = hashlib.sha256(f"{p['item']}|{nre['inicio']}".encode()).hexdigest()[:24]
                with self.hub._trava:
                    self._db.execute("INSERT OR IGNORE INTO validacao_nre(chave,item,dados,situacao,criado,atualizado) VALUES(?,?,?,?,?,?)",
                                     (chave, p["item"], json.dumps(nre, ensure_ascii=False), "pendente", self.relogio(), self.relogio()))
                    self._db.commit()
            nres = self.nres(p["item"])
            aj_nr = sum(n["ajuste_proposto"] for n in nres if n["situacao"] == "aprovado")
            # FDD contra o intervalo de previsão, por R$ em risco
            tarifa = pm.get("tarifa_kwh") if p["modulo"] == "energia" else pm.get("tarifa_m3")
            alarmes = []
            # FDD com o modelo do PERÍODO DE RELATÓRIO (retreinado a cada ciclo: já inclui a medida), só acima do intervalo
            rx, ry = [s["x"] for s in serie_in], [s["y"] for s in serie_in]
            mrel = vm.escolher_modelo(rx, ry, self.P)["escolhido"] if len(rx) >= 10 else None
            serie_rel = vm.economia_acumulada(mrel, serie_in) if mrel else []
            se_rel = mrel["metricas"]["erro_padrao"] if mrel else 0.0
            for tr in [x_ for x_ in vn.fdd_intervalo(serie_rel, se_rel, len(rx), self.P, tarifa) if x_["lado"] == "acima"]:
                linha = {"mes": tr["inicio"], "planejado": tr["esperado"], "medido": tr["medido"], "pct": tr["desvio_pct"],
                         "abs": tr["medido"] - tr["esperado"], "cobertura_pct": None, "dias": None, "dias_mes": tr["dias"],
                         "clima_medido": None, "clima_esperado": None}
                cs = causas(linha, [], {"sentido": "consumir", "sinal": 1, "clima": None, "plano_plano": False, "premissa": p["premissa"]}, self.P)
                chave = hashlib.sha256(f"{p['item']}|{tr['inicio']}".encode()).hexdigest()[:24]
                a_ = dict(tr, chave=chave, item=p["item"], causa=cs[0]["codigo"], causa_nome=cs[0]["nome"], acao=ACOES[cs[0]["codigo"]])
                with self.hub._trava:            # idempotente: o mesmo trecho não vira alerta duas vezes; só o fim anda
                    self._db.execute("INSERT INTO validacao_alerta(chave,item,inicio,fim,dados,criado,atualizado) VALUES(?,?,?,?,?,?,?) "
                                     "ON CONFLICT(chave) DO UPDATE SET fim=excluded.fim, dados=excluded.dados, atualizado=excluded.atualizado",
                                     (chave, p["item"], tr["inicio"], tr["fim"], json.dumps(a_, ensure_ascii=False), self.relogio(), self.relogio()))
                    self._db.commit()
                a_["tarefa"] = bool(self._db.execute("SELECT 1 FROM validacao_tarefa WHERE chave=?", (chave,)).fetchone())
                if pm.get("cmms_automatico") and a_["causa"] in CAUSAS_DE_FALHA and not a_["tarefa"]:
                    a_["tarefa"] = self.criar_tarefa(a_, "automático (M&V)")["ok"]
                alarmes.append(a_)
            alarmes = vn.ordenar_por_risco(alarmes)
            rel_ini_d = datetime.strptime(pm["rel_ini"] + "-01", "%Y-%m-%d")
            fim_mes = pm.get("rel_fim") or rel_dias[-1][:7] if rel_dias else pm["rel_ini"]
            rel_fim_d = datetime.strptime(fim_mes + "-" + str(dias_do_mes(fim_mes)), "%Y-%m-%d")
            proj = vn.projecao_persistencia(serie, (rel_fim_d - rel_ini_d).days + 1, pm.get("meta_economia"), tarifa)
            fatura = []
            for mes, v in sorted((pm.get("faturas") or {}).items()):
                soma = sum(x["y"] for d, x in dias.items() if d[:7] == mes)
                fatura.append({"mes": mes, "fatura": v, "intervalo": soma or None, "diferenca_pct": (soma - v) / v * 100 if v and soma else None})
            contra = vn.contrafactual_d(pm["simulacao"], {d: temps.get(d) for d in rel_dias}) \
                if pm.get("opcao") == "D" and pm.get("simulacao") and pm["simulacao"].get("envoltoria_antes") and pm["simulacao"].get("cop") else None
            item = {"item": p["item"], "nome": p["nome"] or p["item"], "ativo": p["ativo"], "modelo": _sem_dados(mod),
                    "candidatos": [_sem_dados(c) for c in esc["candidatos"]], "aceite": vm.aceite(mod, self.P, self.P["validacao.aceite_cvrmse_diario_max_pct"]),
                    "aceite_minimo": vn.aceite_minimo(mod, self.P), "diagnostico": vn.diagnostico(mod, xs, ys) if mod else {},
                    "horario": _sem_dados(hor), "n_base": len(xs), "fonte_temperatura": fonte_t, "granularidade": lim["granularidade"],
                    "politica_faltantes": pol, "politica_nome": vn.POLITICAS[pol], "faltantes": ag["faltantes"], "imputados": imput,
                    "modelo_versao": ver, "dados_hash": dados_hash, "economia_acumulada": serie[-400:], "economia": econ,
                    "economia_ajustada": None if econ is None else econ + aj_nr, "ajuste_nao_rotineiro": aj_nr, "esperado": esp, "medido": med,
                    "incerteza": inc, "monte_carlo": mc, "sensibilidade": sens, "deriva_modelo": _cusum_curto(d_mod), "deriva_sensor": _cusum_curto(d_sen),
                    "nres": nres, "alarmes": alarmes, "projecao": proj, "fatura": fatura, "contrafactual": contra,
                    "periodo": [rel_dias[0], rel_dias[-1]] if rel_dias else None, "unidade": "kWh" if p["modulo"] == "energia" else "m³"}
            if com_pacote and ver:
                f = nucleo.FAIXAS.get(p["grandeza"])
                item["pacote"] = vn.montar_pacote(brutos, p["grandeza"], ((self.medidor(p["ativo"]) or {}).get("faixa_min", f[0] if f else None),
                                                  (self.medidor(p["ativo"]) or {}).get("faixa_max", f[1] if f else None)), self.relogio(), -180, pol,
                                                  {d: temps[d] for d in rel_dias}, ver, (pm["rel_ini"] + "-01", rel_fim + "-31"), self.P, self.P)
            out.append(item)
        return out

    def pacote_auditoria(self, item: str) -> dict:
        pm = self.plano_mv()["atual"]
        x = next((m for m in self.mv2(pm, self.planos(), com_pacote=True) if m["item"] == item), None)
        if not x or not x.get("pacote"):
            return {"ok": False, "erro": "sem modelo para este item (defina o plano de M&V e os períodos)", "codigo": 404}
        return dict(x["pacote"], ok=True)

    def clima_mensal(self, tipo: str | None, meses: list[str]) -> dict:
        """Clima medido por mês: irradiância média (kWh/m²·dia), chuva do mês (mm) ou graus-dia de resfriamento."""
        if not tipo or not meses:
            return {}
        t0 = int(datetime.strptime(meses[0] + "-01", "%Y-%m-%d").replace(tzinfo=FUSO).timestamp())
        dias: dict[str, list[float]] = {}
        if tipo == "irradiancia":
            for ts, v in self._db.execute("SELECT ts, valor FROM medicao WHERE grandeza='irradiancia' AND ts>=?", (t0,)):
                dias.setdefault(aprendizado._dia(ts), []).append(v)
            mes: dict[str, list[float]] = {}
            for d, vs in dias.items():
                mes.setdefault(d[:7], []).append(sum(vs) / len(vs) * 24 / 1000)
            return {m: sum(v) / len(v) for m, v in mes.items() if m in meses}
        if tipo == "chuva":
            tot: dict[str, float] = {}
            for ts, v in self._db.execute("SELECT ts, valor FROM medicao WHERE grandeza='chuva' AND ts>=?", (t0,)):
                k = _mes_de(ts)
                tot[k] = tot.get(k, 0.0) + v
            if not tot:
                try:
                    for dia, mm in self._db.execute("SELECT dia, MAX(mm) FROM clima_observado GROUP BY dia"):
                        tot[dia[:7]] = tot.get(dia[:7], 0.0) + mm
                except Exception:      # noqa: BLE001 — banco sem a tabela do clima
                    pass
            return {m: v for m, v in tot.items() if m in meses}
        if tipo == "graus_dia":
            for ts, v in self._db.execute("SELECT ts, valor FROM medicao WHERE grandeza='temperatura' AND ativo LIKE '%-ar' AND ts>=?", (t0,)):
                dias.setdefault(aprendizado._dia(ts), []).append(v)
            mes2: dict[str, list[float]] = {}
            for d, vs in dias.items():
                mes2.setdefault(d[:7], []).append(sum(vs) / len(vs))
            return {m: graus_dia(v, self.P["validacao.grau_dia_base_c"]) for m, v in mes2.items() if m in meses}
        return {}

    # ── frota e carbono (nascem de outros módulos) ────────────────────────────────────────────
    def itens_frota(self, meses: list[str]) -> list[dict]:
        if self.frota is None or not meses:
            return []
        t0 = datetime.strptime(meses[0] + "-01", "%Y-%m-%d").replace(tzinfo=FUSO).timestamp()
        P = self.frota.P
        out = []
        for v in self.frota.veiculos():
            if not v.get("ativo", 1):
                continue
            pts = self.frota.pontos(v["id"], t0, None, 200000)
            dias = frota_mod.por_dia(pts, P["frota.gps_salto_kmh"], P["frota.marcha_lenta_vel_kmh"], P["frota.marcha_lenta_min"])
            km, hm, lf, dd = {}, {}, {}, {}
            for d, o in dias.items():
                k = d[:7]
                km[k] = km.get(k, 0.0) + (o.get("km") or 0.0)
                hm[k] = hm.get(k, 0.0) + (o.get("horas_motor") or 0.0)
                lf[k] = lf.get(k, 0.0) + (o.get("litros_fluxo") or 0.0)
                dd[k] = dd.get(k, 0) + 1
            ab: dict[str, float] = {}
            for a in self.frota.abastecimentos(v["id"]):
                ab[str(a["data"])[:7]] = ab.get(str(a["data"])[:7], 0.0) + float(a["litros"])
            esp, por_h = v.get("consumo_esperado"), v.get("consumo_unidade") == "l_h"
            plano, medido, extra = {}, {}, {}
            for m in meses:
                base = hm.get(m) if por_h else km.get(m)
                litros = ab.get(m, lf.get(m))
                if esp and base:
                    plano[m] = esp * base if por_h else esp * base / 100
                medido[m] = {"valor": litros, "dias": None, "dias_mes": dias_do_mes(m)}
                extra[m] = {"base": base, "unidade_base": "h" if por_h else "km",
                            "consumo_medido": (litros / base if por_h else litros / base * 100) if litros and base else None,
                            "consumo_esperado": esp, "combustivel": v.get("combustivel")}
            out.append({"item": f"veiculo-{v['id']}", "nome": v.get("placa") + (f" · {v['nome']}" if v.get("nome") else ""),
                        "ativo": f"no{v['no']:02d}" if v.get("no") is not None else "", "grandeza": "combustivel_l",
                        "fonte": "Frota e combustível · consumo esperado do cadastro × km (ou horas) medidos",
                        "premissa": "", "plano": plano or None, "medido": medido, "extra": extra, "combustivel": v.get("combustivel")})
        return out

    def itens_carbono(self, energia: list[dict], frota: list[dict], meses: list[str]) -> list[dict]:
        """Carbono planejado e medido: kWh × fator da rede do Carbono e litros × fatores de combustão (frota.co2e)."""
        F = self.F()
        if not F:
            return []
        try:
            f_rede = carbono.fator_rede(F, None)
        except (KeyError, TypeError):
            return []
        out = []
        for it in energia:
            if not it.get("plano"):
                continue
            plano = {m: v * f_rede / 1000 for m in meses if (v := plano_do_mes(it["plano"], m)) is not None}
            med = {m: {"valor": None if (x := (it["medido"].get(m) or {}).get("valor")) is None else x * f_rede / 1000,
                       "dias": (it["medido"].get(m) or {}).get("dias"), "dias_mes": dias_do_mes(m)} for m in meses}
            out.append({"item": "rede-" + it["item"], "nome": f"{it.get('nome') or it['item']} · rede elétrica", "ativo": it.get("ativo", ""),
                        "grandeza": "tco2e", "fonte": f"Energia × fator da rede do Carbono ({f_rede} tCO₂/MWh)", "premissa": "",
                        "plano": plano or None, "medido": med})
        for it in frota:
            if not it.get("plano"):
                continue
            k = frota_mod.co2e(it.get("combustivel") or "diesel_b", 1.0, F)["t"]
            if k is None:
                continue
            plano = {m: v * k for m, v in it["plano"].items()}
            med = {m: {"valor": None if x.get("valor") is None else x["valor"] * k, "dias": None, "dias_mes": dias_do_mes(m)}
                   for m, x in it["medido"].items()}
            out.append({"item": "comb-" + it["item"], "nome": f"{it['nome']} · combustível", "ativo": it.get("ativo", ""),
                        "grandeza": "tco2e", "fonte": "Frota × fatores de combustão móvel do Carbono", "premissa": "",
                        "plano": plano or None, "medido": med})
        return out

    # ── estado da aba ─────────────────────────────────────────────────────────────────────
    def estado(self, n_meses: int = 12, ultimo: str | None = None) -> dict:
        agora = self.relogio()
        if not ultimo:
            hoje = datetime.fromtimestamp(agora, FUSO)
            a, m = (hoje.year, hoje.month - 1) if hoje.month > 1 else (hoje.year - 1, 12)
            ultimo = f"{a:04d}-{m:02d}"                       # o último mês completo
        meses = meses_ate(ultimo, max(1, min(MESES_MAX, int(n_meses))))
        planos = self.planos()
        alfa = frota_mod.premissas().get("frota.ewma_alfa", 0.3)
        itens: dict[str, list[dict]] = {k: [] for k in MODULOS}
        for p in planos:
            cfg = MODULOS[p["modulo"]]
            itens[p["modulo"]].append({"item": p["item"], "nome": p["nome"], "ativo": p["ativo"], "grandeza": p["grandeza"],
                                       "fonte": p["fonte"], "premissa": p["premissa"], "plano": p["meses"],
                                       "medido": self.medido_mensal(p["ativo"], p["grandeza"], meses),
                                       "clima": self.clima_mensal(cfg["clima"], meses), "clima_esperado": p["clima"] or None})
        itens["frota"] = self.itens_frota(meses)
        itens["carbono"] = self.itens_carbono(itens["energia"], itens["frota"], meses)
        mods = [analisar_modulo(k, itens[k], meses, self.P, alfa) for k in MODULOS]
        pmv = self.plano_mv()
        pm = pmv["atual"]
        meds, insp = self.medidores(), self.inspecoes()
        t0 = datetime.strptime(meses[0] + "-01", "%Y-%m-%d").replace(tzinfo=FUSO).timestamp()
        qual = []
        for p in planos:
            if p["ativo"]:
                q = self.serie_limpa(p["ativo"], p["grandeza"], t0)
                qual.append({"ativo": p["ativo"], "item": p["item"], "granularidade": q["granularidade"], "passo_s": q["passo_s"],
                             "n": q["n"], "validos": q["validos"], "perda_pct": q["perda_pct"], "perda_ok": q["perda_ok"],
                             "resumo": q["resumo"], "lacunas": len(q["lacunas"]),
                             "exemplos": [o for o in q["pontos"] if o["marcas"]][:20]})
        soma = lambda mod, a, b: sum(l["medido"] for m in mods if m["modulo"] == mod for l in m["linhas"]
                                     if l["medido"] is not None and a <= l["mes"] <= b) or None
        a0, a1 = (pm or {}).get("base_ini") or meses[0], (pm or {}).get("base_fim") or meses[len(meses) // 2 - 1]
        r0, r1 = (pm or {}).get("rel_ini") or meses[len(meses) // 2], (pm or {}).get("rel_fim") or meses[-1]
        fkm = lambda a, b: sum((it["extra"].get(m) or {}).get("base") or 0 for it in itens["frota"] for m in it.get("extra", {}) if a <= m <= b) or None
        en = enpis(pm, {"energia_kwh": soma("energia", a0, a1), "agua_m3": soma("agua", a0, a1), "frota_l": soma("frota", a0, a1), "frota_km": fkm(a0, a1)},
                   {"energia_kwh": soma("energia", r0, r1), "agua_m3": soma("agua", r0, r1), "frota_l": soma("frota", r0, r1), "frota_km": fkm(r0, r1)})
        try:
            f_rede = carbono.fator_rede(self.F(), None) if self.F() else None
        except (KeyError, TypeError):
            f_rede = None
        rastreio = {"versao_codigo": VERSAO_CODIGO, "plano_mv_versao": pmv["versao"], "fator_rede_tco2_mwh": f_rede,
                    "premissas": {k: v for k, v in self.P.items()}, "periodos": {"base": [a0, a1], "relatorio": [r0, r1]}}
        for m in mods:
            for it in m["itens"]:
                lei = {l["mes"]: (it_med.get(l["mes"]) or {}).get("leituras") for l in it["linhas"]
                       for it_med in [next((x["medido"] for x in itens[m["modulo"]] if x["item"] == it["item"]), {})]}
                rastreio[f"leituras.{m['modulo']}.{it['item']}"] = {k: v for k, v in lei.items() if v}
        mv2 = self.mv2(pm, planos)
        for x in mv2:
            rastreio[f"modelo.{x['item']}"] = {"tipo": (x["modelo"] or {}).get("tipo"), "coef": (x["modelo"] or {}).get("coef"),
                                               "pontos_de_mudanca": (x["modelo"] or {}).get("cps"), "versao": VERSAO_CODIGO}
        est = {"ok": True, "agora": agora, "meses": meses, "premissas": self.P, "modulos": mods, "planos": planos,
               "variaveis_base": VARIAVEIS_BASE, "plano_mv": pmv, "opcoes_ipmvp": OPCOES_IPMVP, "papeis": PAPEIS,
               "medidores": meds, "qualidade": qual, "enpis": en, "mv2": mv2, "inspecoes": insp, "licoes": self.licoes(),
               "tarefas": self.tarefas(pm, insp, meds), "rastreio": rastreio, "secoes_relatorio": SECOES_RELATORIO,
               "versao_codigo": VERSAO_CODIGO, "perfis": vn.PERFIS,
               "pee": vn.resumo_pee(pm.get("pee") or {}, self.P) if pm and pm.get("perfil") == "pee" else None}
        return est

    def baseline(self, plano_id: int, var: str, base: tuple[str, str], rel: tuple[str, str]) -> dict:
        """IPMVP com linha de base por regressão para um item gravado: y = medido do item, x = a variável escolhida."""
        p = next((x for x in self.planos() if x["id"] == plano_id), None)
        if not p:
            return {"ok": False, "erro": "plano não encontrado", "codigo": 404}
        if var not in VARIAVEIS_BASE:
            return {"ok": False, "erro": "variável: graus_dia, irradiancia ou producao"}
        if not all(_MES.match(x) and len(x) == 7 for x in (*base, *rel)) or base[0] > base[1] or rel[0] > rel[1]:
            return {"ok": False, "erro": "períodos em AAAA-MM, início antes do fim"}
        meses = sorted(set(meses_ate(base[1], 1 + _n(base)) + meses_ate(rel[1], 1 + _n(rel))))
        med = self.medido_mensal(p["ativo"], p["grandeza"], meses)
        if var == "producao":
            prod = aprendizado._producao_gestao(self._db)
            xs = {m: sum(v for d, v in prod.items() if d[:7] == m) or None for m in meses}
        else:
            xs = self.clima_mensal(var, meses)
        am = lambda a, b: [{"mes": m, "y": (med.get(m) or {}).get("valor"), "x": xs.get(m)} for m in meses if a <= m <= b]
        r = ipmvp_regressao(am(*base), am(*rel), self.P)
        return dict(r, ok=True, plano=p["id"], variavel=var)

    # ── rotas ─────────────────────────────────────────────────────────────────────────────
    def rota(self, metodo: str, caminho: str, conta: dict | None, corpo=None, consulta: dict | None = None):
        """(código, resposta).
        GET  /api/validacao/estado?meses=&ultimo=AAAA-MM                         cliente+
        GET  /api/validacao/baseline?plano=&var=&base_ini=&base_fim=&rel_ini=&rel_fim=   cliente+
        GET  /api/validacao/relatorio                                             cliente+ (blocos do relatório padrão)
        POST /api/validacao/plano | plano/remover | plano-mv | medidor | licao | inspecao   equipe (tudo no registro encadeado)"""
        if not caminho.startswith("/api/validacao"):
            return None
        if not conta:
            return 401, {"ok": False, "erro": "entre com usuario e senha", "login": True}
        consulta = consulta or {}
        g = lambda k, n=10: str((consulta.get(k) or [""])[0])[:n]
        negado = (403, {"ok": False, "erro": "o seu papel não permite esta ação"})
        resp = lambda r: (r.pop("codigo", 200 if r.get("ok") else 400), r)
        p = caminho.rstrip("/")
        if metodo == "GET":
            if not seg.pode(conta, seg.CLIENTE):
                return negado
            if p == "/api/validacao/estado":
                n = g("meses", 3)
                ult = g("ultimo", 7)
                return 200, self.estado(int(n) if n.isdigit() else 12, ult if re.fullmatch(r"\d{4}-\d{2}", ult) else None)
            if p == "/api/validacao/baseline":
                pid = g("plano", 12)
                return resp(self.baseline(int(pid) if pid.isdigit() else 0, g("var", 20), (g("base_ini", 7), g("base_fim", 7)),
                                          (g("rel_ini", 7), g("rel_fim", 7))))
            if p == "/api/validacao/auditoria":
                r = self.pacote_auditoria(g("item", 60))
                if not r.get("ok"):
                    return resp(r)
                r.pop("ok")
                return 200, ("bytes", f"validacao-auditoria-{g('item', 60)}.json", "application/json; charset=utf-8",
                             json.dumps(r, ensure_ascii=False, sort_keys=True, indent=1).encode("utf-8"))
            if p == "/api/validacao/relatorio":
                return 200, dict(relatorio_blocos(self.estado()), ok=True)
            return 404, {"ok": False, "erro": "rota desconhecida"}
        if metodo != "POST":
            return 405, {"ok": False, "erro": "método não aceito"}
        if not seg.pode(conta, seg.EQUIPE):
            return negado
        quem = conta.get("usuario") or "?"
        rotas = {"/api/validacao/plano": ("validacao_plano", lambda d: self.gravar_plano(d, quem)),
                 "/api/validacao/plano/remover": ("validacao_id", lambda d: self.remover_plano(d["id"], quem)),
                 "/api/validacao/plano-mv": ("validacao_plano_mv", lambda d: self.gravar_plano_mv(d["plano"], d["motivo"], quem)),
                 "/api/validacao/medidor": ("validacao_medidor", lambda d: self.gravar_medidor(d, quem)),
                 "/api/validacao/licao": ("validacao_licao", lambda d: self.gravar_licao(d["texto"], quem)),
                 "/api/validacao/inspecao": ("validacao_inspecao", lambda d: self.gravar_inspecao(d, quem)),
                 "/api/validacao/nre": ("validacao_nre", lambda d: self.decidir_nre(d["chave"], d["aprovar"], d["motivo"], quem)),
                 "/api/validacao/tarefa": ("validacao_chave", lambda d: self._tarefa_do_alerta(d["chave"], quem)),
                 "/api/validacao/verificar": ("validacao_item", lambda d: self._verificar_item(d["item"], quem))}
        if p not in rotas:
            return 404, {"ok": False, "erro": "rota desconhecida"}
        esq, fazer = rotas[p]
        try:
            d = seg.carregar_json(corpo or "{}")
        except ValueError:
            return 400, {"ok": False, "erro": "json invalido"}
        erro = seg.validar(d, seg.ESQUEMAS.get(esq) or ESQUEMAS[esq], estrito=True)
        if erro:
            return 400, {"ok": False, "erro": erro}
        return resp(fazer(d))


def _cusum_curto(c: dict) -> dict:
    """O CUSUM sem as séries inteiras (a tela mostra o alarme, o dia e o último valor)."""
    return {"alarme": c["alarme"], "indice": c["indice"], "lado": c["lado"], "referencia": c.get("referencia"),
            "s_mais": c["s_mais"][-1] if c["s_mais"] else None, "s_menos": c["s_menos"][-1] if c["s_menos"] else None}


def _sem_dados(m: dict | None) -> dict | None:
    """O modelo sem os dados de treino (o k-NN guarda os pontos; a tela não precisa deles)."""
    return None if m is None else {k: v for k, v in m.items() if k != "dados"}


def _n(periodo: tuple[str, str]) -> int:
    (a1, m1), (a2, m2) = (map(int, periodo[0].split("-")), map(int, periodo[1].split("-")))
    return (a2 - a1) * 12 + (m2 - m1)


__all__ = ["Validacao", "desvio", "comparar", "quando", "causas", "como", "analisar_modulo", "ipmvp_economia",
           "linha_de_base", "ipmvp_regressao", "graus_dia", "premissas", "MODULOS", "ESQUEMAS"]
