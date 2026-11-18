"""Frota e combustível (EM DESENVOLVIMENTO): caminhões, carros, tratores e máquinas, abastecimentos, GPS e sensores
de consumo. Espelho das contas em sistema/physis-frota.js (mesmas fórmulas e premissas; teste em tests/test_frota.py).

Tabelas (no banco do hub): frota_veiculo, frota_abastecimento, frota_ponto, frota_cerca, frota_arquivo,
frota_importacao e frota_config.

De onde vem cada dado:
- veículo (tipo, placa ou etiqueta, combustível, tanque, consumo esperado, nó V6 ligado): digitado pela equipe;
- abastecimento (data, litros, preço com fonte, odômetro ou horímetro, comprovante opcional): digitado pela equipe ou
  importado do CSV do cartão-combustível (validado, tudo ou nada, com resumo SHA-256);
- telemetria (GPS, velocidade, rumo, vazão e nível de combustível, horímetro, odômetro): linha V6 TIPO:VEI (rastreador,
  leitor OBD-II/CAN, medidor de vazão) que o hub entrega aqui (Hub.frota_receptor), ou o CSV exportado do rastreador.
Contas: distância (haversine, ou odômetro quando houver), consumo por km e por hora, marcha lenta, combustível por
veículo/dia/mês, CO₂e pelo MESMO caminho do Carbono (carbono.combustao, uso "movel", base physis-fatores-emissao.json).
Alertas: consumo acima do normal aprendido (z robusto com mediana e MAD, e média móvel exponencial, dizendo o tamanho
da amostra), queda de nível sem andar (vazamento ou furto), marcha lenta longa e saída da cerca desenhada. Os limites
são premissas frota.* de sistema/physis-premissas.json, todas com status "conferir".

LGPD: a posição de um veículo mostra onde a pessoa que dirige está (dado pessoal). Motorista é só um código opcional
(nada de nome, CPF ou telefone aqui); a exportação sai sem o código do motorista, a não ser que a direção peça. Os pontos
de GPS são apagados depois de frota.retencao_dias (configurável pela direção). Comprovantes: só a equipe vê.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path

from . import carbono
from . import clima as clima_mod
from . import integridade
from . import seguranca as seg
from .fornecedores import ARQ_TIPOS

RAIZ = Path(__file__).resolve().parents[2]
ARQ_PREMISSAS = (RAIZ / "sistema" / "physis-premissas.json", Path(__file__).resolve().parents[1] / "web" / "physis-premissas.json")
PAINEL = Path(__file__).resolve().parents[1] / "web" / "painel.html"   # no pacote do cliente, as bases vão embutidas nele
FUSO = clima_mod.FUSO
R_TERRA_KM = 6371.0088                 # raio médio da Terra (IUGG), o mesmo de physis-circular-mapa.js
K_MAD = 0.6745                         # z robusto = 0,6745 × (x − mediana) / MAD (Iglewicz e Hoaglin, 1993)
INTERVALO_MAX_S = 900                  # buraco maior que 15 min entre dois pontos: não integra vazão nem soma marcha lenta
TIPOS = {"caminhao": "Caminhão", "carro": "Carro", "trator": "Trator", "maquina": "Máquina", "outro": "Outro"}
# combustíveis: a lista da Combustão móvel do Carbono (sistema/physis-carbono.js) mais o biodiesel (B100)
COMBUSTIVEIS = ("diesel_b", "gasolina_c", "etanol_hidratado", "gnv", "biodiesel", "diesel")
UNIDADES_CONSUMO = {"l_100km": "L/100 km", "l_h": "L/h"}
FONTES_PRECO = {"nota": "Nota fiscal", "cartao": "Cartão-combustível", "bomba": "Preço da bomba", "estimado": "Estimado"}
ARQ_MAX = 10 * 1024 * 1024             # comprovante: até 10 MB (PDF ou imagem)
CSV_MAX = 4 * 1024 * 1024
CSV_LINHAS = {"rastreador": 50000, "cartao": 5000}
CSV_COLUNAS = {"rastreador": ("data_hora", "lat", "lon", "vel", "rumo", "flx", "niv", "hor", "odo"),
               "cartao": ("data", "litros", "preco_l", "odometro", "horimetro", "motorista")}
CSV_OBRIGATORIAS = {"rastreador": ("data_hora", "lat", "lon"), "cartao": ("data", "litros")}
PONTOS_ESTADO_DIAS = 31                # pontos lidos para alertas e totais do estado
AVISO_LGPD = ("A posição de um veículo mostra onde a pessoa que dirige está: é dado pessoal (LGPD). Avise quem dirige, "
              "use só para a gestão da frota e guarde pelo tempo da retenção. O motorista é só um código opcional; "
              "a exportação sai sem ele.")
_ID = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")
_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# premissas (todas "conferir"): id -> reserva usada só sem a base de premissas
PREMISSAS_PADRAO = {"frota.anomalia_z": 3.5, "frota.anomalia_desvio_min_pct": 15.0, "frota.anomalia_amostra_min": 8, "frota.ewma_alfa": 0.3,
                    "frota.queda_nivel_pct": 5.0, "frota.parado_distancia_km": 0.2, "frota.marcha_lenta_vel_kmh": 3.0,
                    "frota.marcha_lenta_min": 20.0, "frota.gps_salto_kmh": 200.0, "frota.retencao_dias": 365}

ESQUEMA = """
CREATE TABLE IF NOT EXISTS frota_veiculo (
  id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, placa TEXT NOT NULL, nome TEXT NOT NULL DEFAULT '',
  combustivel TEXT NOT NULL, tanque_l REAL, consumo_esperado REAL, consumo_unidade TEXT NOT NULL DEFAULT 'l_100km',
  no INTEGER, motorista TEXT NOT NULL DEFAULT '', ativo INTEGER NOT NULL DEFAULT 1, criado REAL NOT NULL,
  atualizado REAL NOT NULL, por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS frota_abastecimento (
  id INTEGER PRIMARY KEY AUTOINCREMENT, veiculo INTEGER NOT NULL, data TEXT NOT NULL, litros REAL NOT NULL,
  preco_l REAL, preco_fonte TEXT NOT NULL DEFAULT '', odometro REAL, horimetro REAL, motorista TEXT NOT NULL DEFAULT '',
  comprovante INTEGER, origem TEXT NOT NULL DEFAULT 'manual', criado REAL NOT NULL, por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS frota_ponto (
  id INTEGER PRIMARY KEY AUTOINCREMENT, chave TEXT NOT NULL, veiculo INTEGER, no INTEGER, ts REAL NOT NULL,
  lat REAL, lon REAL, vel REAL, rumo REAL, flx REAL, niv REAL, hor REAL, odo REAL, ign INTEGER,
  origem TEXT NOT NULL, UNIQUE (chave, ts));
CREATE INDEX IF NOT EXISTS frota_ponto_vts ON frota_ponto(veiculo, ts);
CREATE TABLE IF NOT EXISTS frota_cerca (
  id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, poligono TEXT NOT NULL, veiculos TEXT NOT NULL DEFAULT '[]',
  ativa INTEGER NOT NULL DEFAULT 1, criado REAL NOT NULL, por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS frota_arquivo (
  id INTEGER PRIMARY KEY AUTOINCREMENT, veiculo INTEGER NOT NULL, nome TEXT NOT NULL, mime TEXT NOT NULL,
  tamanho INTEGER NOT NULL, sha256 TEXT NOT NULL, arquivo TEXT NOT NULL, criado REAL NOT NULL, por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS frota_importacao (
  id INTEGER PRIMARY KEY AUTOINCREMENT, veiculo INTEGER NOT NULL, tipo TEXT NOT NULL, nome_arquivo TEXT NOT NULL DEFAULT '',
  linhas INTEGER NOT NULL, novas INTEGER NOT NULL, resumo TEXT NOT NULL, arquivo_sha256 TEXT NOT NULL, quando REAL NOT NULL,
  por TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS frota_config (chave TEXT PRIMARY KEY, valor TEXT NOT NULL, quando REAL NOT NULL, por TEXT NOT NULL);
"""

# Esquemas dos corpos JSON (entram em seg.ESQUEMAS pelo servidor; o módulo também valida, estrito)
S, NUM = str, (int, float)
ESQUEMAS = {
    "frota_veiculo": {"id": (int, 10**9, False), "tipo": (S, 20, True), "placa": (S, 20, True), "nome": (S, 80, False),
                      "combustivel": (S, 30, True), "tanque_l": (NUM, 100000, False), "consumo_esperado": (NUM, 10000, False),
                      "consumo_unidade": (S, 10, False), "no": (int, 99, False), "motorista": (S, 40, False),
                      "ativo": (bool, None, False)},
    "frota_abastecimento": {"veiculo": (int, 10**9, True), "data": (S, 10, True), "litros": (NUM, 100000, True),
                            "preco_l": (NUM, 10000, False), "preco_fonte": (S, 20, False), "odometro": (NUM, 10**8, False),
                            "horimetro": (NUM, 10**7, False), "motorista": (S, 40, False), "comprovante": (int, 10**9, False)},
    "frota_cerca": {"id": (int, 10**9, False), "nome": (S, 80, True), "poligono": (list, 500, True),
                    "veiculos": (list, 500, False), "ativa": (bool, None, False)},
    "frota_importar": {"veiculo": (int, 10**9, True), "tipo": (S, 20, True), "csv": (S, CSV_MAX, True),
                       "nome": (S, 160, False), "simular": (bool, None, False)},
    "frota_config": {"retencao_dias": (int, 3650, True)},
    "frota_id": {"id": (int, 10**9, True)},
}


# ══ Premissas ══════════════════════════════════════════════════════════════════════════════════
def _do_painel(padrao: str):
    """JSON embutido no painel (pacote do cliente, sem a pasta sistema/): bloco que casa com `padrao` (grupo 1)."""
    try:
        m = re.search(padrao, PAINEL.read_text(encoding="utf-8"), re.S)
        return json.loads(m.group(1)) if m else None
    except (OSError, ValueError):
        return None


def fatores() -> dict | None:
    """A base de fatores do Carbono: sistema/physis-fatores-emissao.json ou, no pacote, a cópia embutida no painel
    (base-fatores-emissao, a mesma que a tela do Carbono usa). Sem nenhuma: None (CO₂e não calculado)."""
    try:
        return carbono.carregar()
    except (OSError, ValueError):
        return _do_painel(r'<script type="application/json" id="base-fatores-emissao">(\{.*?\})</script>')


def premissas(dados=None) -> dict:
    """{id: valor} das premissas frota.* (base sistema/physis-premissas.json ou a cópia embutida no painel; sem
    nenhuma, a reserva marcada 'conferir')."""
    j = dados
    if j is None:
        for c in ARQ_PREMISSAS:
            try:
                j = json.loads(Path(c).read_text(encoding="utf-8"))
                break
            except (OSError, ValueError):
                continue
        else:
            j = _do_painel(r"var PREMISSAS = (\{.*?\});\n")
    out = dict(PREMISSAS_PADRAO)
    for p in (j or {}).get("premissas") or []:
        if p.get("id") in out and isinstance(p.get("valor_padrao"), (int, float)):
            out[p["id"]] = p["valor_padrao"]
    return out


# ══ Contas puras (espelho em sistema/physis-frota.js) ═════════════════════════════════════════
def haversine_km(la1: float, lo1: float, la2: float, lo2: float) -> float:
    r = math.pi / 180
    dp, dl = (la2 - la1) * r, (lo2 - lo1) * r
    a = math.sin(dp / 2) ** 2 + math.cos(la1 * r) * math.cos(la2 * r) * math.sin(dl / 2) ** 2
    return 2 * R_TERRA_KM * math.asin(math.sqrt(min(1.0, a)))


def _tem_pos(p: dict) -> bool:
    return p.get("lat") is not None and p.get("lon") is not None


def distancia(pontos: list[dict], salto_kmh: float) -> dict:
    """{"km", "km_gps", "km_odometro", "fonte", "descartados"}. Pontos em ordem de tempo. GPS: soma dos trechos, sem os
    saltos (velocidade implícita acima de salto_kmh). Odômetro: último menos o primeiro, quando os dois existem e crescem."""
    km, desc, ant = 0.0, 0, None
    for p in pontos:
        if not _tem_pos(p):
            continue
        if ant is not None:
            d, dt = haversine_km(ant["lat"], ant["lon"], p["lat"], p["lon"]), p["ts"] - ant["ts"]
            if dt > 0 and d / (dt / 3600) > salto_kmh:
                desc += 1
                continue                       # o ponto saltado não vira referência
            km += d
        ant = p
    odos = [p["odo"] for p in pontos if p.get("odo") is not None]
    km_odo = odos[-1] - odos[0] if len(odos) >= 2 and odos[-1] >= odos[0] else None
    usa_odo = km_odo is not None and km_odo > 0
    return {"km": km_odo if usa_odo else km, "km_gps": km, "km_odometro": km_odo, "fonte": "odometro" if usa_odo else "gps",
            "descartados": desc}


def litros_do_fluxo(pontos: list[dict]) -> float | None:
    """Integral da vazão (L/h) no tempo, pelos trapézios; buraco maior que INTERVALO_MAX_S não entra. None sem vazão."""
    com = [p for p in pontos if p.get("flx") is not None]
    if len(com) < 2:
        return None
    tot = 0.0
    for a, b in zip(com, com[1:]):
        dt = b["ts"] - a["ts"]
        if 0 < dt <= INTERVALO_MAX_S:
            tot += (a["flx"] + b["flx"]) / 2 * dt / 3600
    return tot


def trechos_com_vazao(pontos: list[dict], salto_kmh: float) -> dict:
    """Litros, km e horas de motor só nos trechos com vazão medida nas duas pontas (até INTERVALO_MAX_S): é a base do
    consumo, para litros e distância saírem dos MESMOS trechos (o odômetro do dia inteiro com a vazão de parte do dia
    daria um consumo errado). {"litros" (None sem vazão), "km", "horas"}."""
    litros = km = horas = 0.0
    n = 0
    for a, b in zip(pontos, pontos[1:]):
        if a.get("flx") is None or b.get("flx") is None:
            continue
        dt = b["ts"] - a["ts"]
        if not 0 < dt <= INTERVALO_MAX_S:
            continue
        n += 1
        litros += (a["flx"] + b["flx"]) / 2 * dt / 3600
        if a["flx"] > 0 or b["flx"] > 0:
            horas += dt / 3600
        if _tem_pos(a) and _tem_pos(b):
            d = haversine_km(a["lat"], a["lon"], b["lat"], b["lon"])
            if d / (dt / 3600) <= salto_kmh:
                km += d
    return {"litros": litros if n else None, "km": km, "horas": horas}


def _motor_ligado(p: dict) -> bool | None:
    if p.get("ign") is not None:
        return bool(p["ign"])
    if p.get("flx") is not None:
        return p["flx"] > 0
    return None


def horas_motor(pontos: list[dict]) -> float | None:
    """Horas de motor: horímetro (último − primeiro) ou, sem ele, o tempo com ignição/vazão entre pontos próximos."""
    hs = [p["hor"] for p in pontos if p.get("hor") is not None]
    if len(hs) >= 2 and hs[-1] >= hs[0]:
        return hs[-1] - hs[0]
    tot, tem = 0.0, False
    for a, b in zip(pontos, pontos[1:]):
        lig = _motor_ligado(a)
        if lig is None:
            continue
        tem = True
        dt = b["ts"] - a["ts"]
        if lig and 0 < dt <= INTERVALO_MAX_S:
            tot += dt / 3600
    return tot if tem else None


def marcha_lenta(pontos: list[dict], vel_lim: float, min_lim: float) -> dict:
    """Motor ligado (ignição ou vazão > 0) e velocidade abaixo de vel_lim. {"horas", "eventos": [{ts_ini, ts_fim, min, lat, lon}]}:
    as horas somam todo trecho parado com motor ligado; evento é o trecho de min_lim minutos ou mais."""
    horas, eventos, ini, ult = 0.0, [], None, None

    def fecha():
        if ini is not None and ult is not None:
            m = (ult["ts"] - ini["ts"]) / 60
            if m >= min_lim:
                eventos.append({"ts_ini": ini["ts"], "ts_fim": ult["ts"], "min": m, "lat": ini.get("lat"), "lon": ini.get("lon")})
    for i, p in enumerate(pontos):
        parado = p.get("vel") is not None and p["vel"] < vel_lim and _motor_ligado(p) is True
        if parado and ini is not None and p["ts"] - ult["ts"] > INTERVALO_MAX_S:
            fecha()
            ini = None
        if parado:
            if ini is None:
                ini = p
            else:
                horas += (p["ts"] - ult["ts"]) / 3600
            ult = p
        elif ini is not None:
            fecha()
            ini, ult = None, None
    fecha()
    return {"horas": horas, "eventos": eventos}


def consumo(litros: float | None, km: float | None, horas: float | None) -> dict:
    """{"l_100km", "l_h", "km_l"}: None quando falta o dado ou a base é zero."""
    l100 = litros / km * 100 if litros is not None and km and km > 0 else None
    lh = litros / horas if litros is not None and horas and horas > 0 else None
    return {"l_100km": l100, "l_h": lh, "km_l": km / litros if litros and km is not None and litros > 0 else None}


def normal_aprendido(amostras: list[float], alfa: float) -> dict:
    """Normal de consumo de um veículo: mediana, MAD, média móvel exponencial (EWMA) e o tamanho da amostra."""
    v = [float(x) for x in amostras if x is not None and math.isfinite(x)]
    if not v:
        return {"n": 0, "mediana": None, "mad": None, "ewma": None}
    med = statistics.median(v)
    mad = statistics.median([abs(x - med) for x in v])
    e = v[0]
    for x in v[1:]:
        e = alfa * x + (1 - alfa) * e
    return {"n": len(v), "mediana": med, "mad": mad, "ewma": e}


def anomalia_consumo(valor: float, historico: list[float], z_lim: float, n_min: int, alfa: float, desvio_min_pct: float = 0.0) -> dict:
    """Consumo acima do normal aprendido? z robusto = 0,6745·(x − mediana)/MAD contra o histórico (sem o próprio valor)
    E pelo menos desvio_min_pct acima da mediana (diferença pequena demais para importar não alerta, mesmo com MAD
    pequeno de poucas amostras). Com menos de n_min amostras, ou MAD zero, não decide (diz por quê). Só o lado de cima."""
    nm = normal_aprendido(historico, alfa)
    out = dict(nm, valor=valor, z=None, anomalo=False, motivo="")
    if nm["n"] < n_min:
        out["motivo"] = f"aprendendo: {nm['n']} de {n_min} amostras"
        return out
    if not nm["mad"]:
        out["motivo"] = "amostras sem variação (MAD zero): não dá para dizer o normal"
        return out
    out["z"] = K_MAD * (valor - nm["mediana"]) / nm["mad"]
    out["anomalo"] = out["z"] > z_lim and valor >= nm["mediana"] * (1 + desvio_min_pct / 100)
    return out


def ponto_no_poligono(lat: float, lon: float, poligono: list) -> bool:
    """Raio cruzando as arestas (x = longitude, y = latitude). Polígono: [[lat, lon], ...] (3 vértices ou mais)."""
    dentro, n = False, len(poligono)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        yi, xi = poligono[i][0], poligono[i][1]
        yj, xj = poligono[j][0], poligono[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def saidas_da_cerca(pontos: list[dict], cercas: list[dict], veiculo: int | None = None) -> list[dict]:
    """Eventos de saída: o ponto anterior estava dentro da cerca e este está fora. Cerca: {id, nome, poligono, veiculos, ativa};
    veiculos vazio = vale para todos."""
    out = []
    for c in cercas:
        if not c.get("ativa", True) or len(c.get("poligono") or []) < 3:
            continue
        if c.get("veiculos") and veiculo is not None and veiculo not in c["veiculos"]:
            continue
        antes = None
        for p in pontos:
            if not _tem_pos(p):
                continue
            agora = ponto_no_poligono(p["lat"], p["lon"], c["poligono"])
            if antes is True and not agora:
                out.append({"cerca": c.get("id"), "nome": c.get("nome", ""), "ts": p["ts"], "lat": p["lat"], "lon": p["lon"]})
            antes = agora
    return out


def quedas_sem_andar(pontos: list[dict], queda_pct: float, dist_max_km: float, vel_lim: float,
                     tanque_l: float | None = None) -> list[dict]:
    """Nível de combustível que cai com o veículo parado (vazamento ou furto possível). Janela: desde um ponto, o veículo
    não se afasta mais que dist_max_km nem passa de vel_lim; a queda de nível menos o que a vazão mediu (convertido em %
    do tanque) chega a queda_pct. Subida de nível (abastecimento) reinicia a janela."""
    com = [p for p in pontos if p.get("niv") is not None]
    out, i = [], 0
    while i < len(com):
        s, j, ev, litros = com[i], i + 1, None, 0.0
        while j < len(com):
            p, q = com[j], com[j - 1]
            andou = (_tem_pos(s) and _tem_pos(p) and haversine_km(s["lat"], s["lon"], p["lat"], p["lon"]) > dist_max_km) \
                or (p.get("vel") is not None and p["vel"] >= vel_lim) or p["ts"] - q["ts"] > 6 * 3600 or p["ts"] - s["ts"] > 48 * 3600
            if andou or p["niv"] > q["niv"] + 0.5:
                break
            dt = p["ts"] - q["ts"]             # vazão medida na janela (trapézios, como litros_do_fluxo)
            if p.get("flx") is not None and q.get("flx") is not None and 0 < dt <= INTERVALO_MAX_S:
                litros += (p["flx"] + q["flx"]) / 2 * dt / 3600
            gasto_pct = litros / tanque_l * 100 if tanque_l else 0.0
            queda = s["niv"] - p["niv"] - gasto_pct
            if queda >= queda_pct and (ev is None or queda >= ev["queda_pct"]):   # a janela segue: um evento só, até o fim
                ev = {"ts_ini": s["ts"], "ts_fim": p["ts"], "queda_pct": queda,
                      "litros": queda / 100 * tanque_l if tanque_l else None, "lat": p.get("lat"), "lon": p.get("lon")}
            j += 1
        if ev:
            out.append(ev)
        i = j if ev else i + 1
    return out


def dia_de(ts: float) -> str:
    return datetime.fromtimestamp(ts, FUSO).strftime("%Y-%m-%d")


def por_dia(pontos: list[dict], salto_kmh: float, vel_lim: float, min_lim: float) -> dict:
    """{dia: {km, km_fonte, litros_fluxo, horas_motor, horas_marcha_lenta, l_100km, l_h, pontos}} (fuso de Brasília)."""
    grupos: dict[str, list] = {}
    for p in pontos:
        grupos.setdefault(dia_de(p["ts"]), []).append(p)
    out = {}
    for d, ps in sorted(grupos.items()):
        dist, lf, hm = distancia(ps, salto_kmh), litros_do_fluxo(ps), horas_motor(ps)
        ml = marcha_lenta(ps, vel_lim, min_lim)
        tv = trechos_com_vazao(ps, salto_kmh)
        c = consumo(tv["litros"], tv["km"], tv["horas"])
        out[d] = {"km": dist["km"], "km_fonte": dist["fonte"], "litros_fluxo": lf, "horas_motor": hm,
                  "horas_marcha_lenta": ml["horas"], "l_100km": c["l_100km"], "l_h": c["l_h"], "pontos": len(ps)}
    return out


def consumo_entre_abastecimentos(abast: list[dict], unidade: str) -> list[dict]:
    """Método do tanque cheio: litros do abastecimento ÷ (odômetro, ou horímetro, deste − do anterior). [{data, valor}]."""
    campo = "horimetro" if unidade == "l_h" else "odometro"
    ab = sorted([a for a in abast if a.get(campo) is not None], key=lambda a: (a["data"], a[campo]))
    out = []
    for a, b in zip(ab, ab[1:]):
        delta = b[campo] - a[campo]
        if delta > 0:
            out.append({"data": b["data"], "valor": b["litros"] / delta * (1 if unidade == "l_h" else 100), "abastecimento": b.get("id")})
    return out


def amostras_consumo(dias: dict, abast: list[dict], unidade: str, hoje: str | None = None) -> list[dict]:
    """Amostras para o normal aprendido: o consumo de cada dia COMPLETO medido pela vazão (o dia de hoje, ainda pela
    metade, não entra); sem vazão, o do tanque cheio."""
    k = "l_h" if unidade == "l_h" else "l_100km"
    med = [{"data": d, "valor": x[k], "fonte": "vazão"} for d, x in sorted(dias.items())
           if x.get(k) is not None and x.get("litros_fluxo") and (hoje is None or d < hoje)]
    if med:
        return med
    return [dict(x, fonte="abastecimentos") for x in consumo_entre_abastecimentos(abast, unidade)]


def co2e(comb: str, litros: float, F: dict | None = None, gwp: str | None = None) -> dict:
    """tCO₂e (fóssil) e tCO₂ biogênico de `litros` de combustível em veículo: o MESMO caminho do Carbono
    (carbono.combustao com uso "movel" e carbono.tco2e com o GWP padrão da base)."""
    F = F or fatores()
    if not F:
        return {"t": None, "bio_t": None, "gases": {}}
    gw = carbono.gwp_de(F, gwp or F["gwp"]["padrao"])
    g, bio = carbono.combustao(F, comb, float(litros or 0), "movel")
    return {"t": carbono.tco2e(g, gw), "bio_t": bio / 1000, "gases": g}


def para_carbono(veiculos: list[dict], abast: list[dict], ano: str, fluxo_por_veiculo: dict | None = None) -> list[dict]:
    """Linhas da Combustão móvel medidas na frota, por combustível: [{comb, qtd, q:"medido", fonte, n}]. Os abastecimentos
    do ano valem; veículo sem abastecimento no ano entra com os litros medidos pela vazão (fluxo_por_veiculo: {id: litros
    no ano}, sem os pontos simulados). Sem dado medido, lista vazia (o Carbono usa o digitado)."""
    comb_de = {v["id"]: v["combustivel"] for v in veiculos}
    soma: dict[str, dict] = {}
    com_abast = set()
    for a in abast:
        if str(a.get("data", ""))[:4] != str(ano) or a.get("veiculo") not in comb_de:
            continue
        c = comb_de[a["veiculo"]]
        x = soma.setdefault(c, {"qtd": 0.0, "n": 0, "fluxo": 0.0})
        x["qtd"] += float(a["litros"])
        x["n"] += 1
        com_abast.add(a["veiculo"])
    for vid, l in (fluxo_por_veiculo or {}).items():
        if vid in comb_de and vid not in com_abast and l and l > 0:
            x = soma.setdefault(comb_de[vid], {"qtd": 0.0, "n": 0, "fluxo": 0.0})
            x["qtd"] += l
            x["fluxo"] += l
    out = []
    for c in COMBUSTIVEIS:
        if c in soma and soma[c]["qtd"] > 0:
            x = soma[c]
            partes = []
            if x["n"]:
                partes.append(f"{x['n']} abastecimento{'s' if x['n'] != 1 else ''} de {ano}")
            if x["fluxo"]:
                partes.append(f"{x['fluxo']:.0f} L pela vazão")
            out.append({"comb": c, "qtd": round(x["qtd"], 3), "q": "medido", "fonte": "Frota e combustível: " + " e ".join(partes)})
    return out


def custos_por_mes(abast: list[dict]) -> dict:
    """{mes: {litros, custo, sem_preco}} para a Gestão (Financeiro); abastecimento sem preço conta litros, não custo."""
    out: dict[str, dict] = {}
    for a in abast:
        m = str(a.get("data", ""))[:7]
        x = out.setdefault(m, {"litros": 0.0, "custo": 0.0, "sem_preco": 0})
        x["litros"] += float(a["litros"])
        if a.get("preco_l") is not None:
            x["custo"] += float(a["litros"]) * float(a["preco_l"])
        else:
            x["sem_preco"] += 1
    return dict(sorted(out.items()))


# ══ Validação ════════════════════════════════════════════════════════════════════════════════
def _f(v) -> float | None:
    """Número de célula ou de campo (aceita vírgula decimal); None vazio; ValueError se não for número."""
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if not math.isfinite(v):
            raise ValueError
        return float(v)
    s = str(v).strip().replace(" ", "")
    if not s or s.lower() in ("-", "nan", "null", "n/d"):
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    x = float(s)
    if not math.isfinite(x):
        raise ValueError
    return x


def validar_veiculo(d: dict, nos_usados: dict | None = None) -> tuple[dict | None, str]:
    tipo = str(d.get("tipo") or "").strip().lower()
    if tipo not in TIPOS:
        return None, "tipo: " + ", ".join(TIPOS)
    placa = re.sub(r"\s+", " ", str(d.get("placa") or "")).strip().upper()
    if not 1 <= len(placa) <= 20:
        return None, "informe a placa ou a etiqueta do veículo"
    comb = str(d.get("combustivel") or "")
    if comb not in COMBUSTIVEIS:
        return None, "combustível: " + ", ".join(COMBUSTIVEIS)
    un = str(d.get("consumo_unidade") or ("l_h" if tipo in ("trator", "maquina") else "l_100km"))
    if un not in UNIDADES_CONSUMO:
        return None, "unidade do consumo: l_100km ou l_h"
    try:
        tanque, cons = _f(d.get("tanque_l")), _f(d.get("consumo_esperado"))
    except ValueError:
        return None, "tanque e consumo esperado são números"
    if tanque is not None and not 0 < tanque <= 100000:
        return None, "tanque em litros (maior que zero)"
    if cons is not None and not 0 < cons <= 10000:
        return None, "consumo esperado maior que zero"
    no = d.get("no")
    if no is not None and not (isinstance(no, int) and 1 <= no <= 99):
        return None, "nó V6 entre 1 e 99"
    mot = str(d.get("motorista") or "").strip()
    if mot and not _ID.match(mot):
        return None, "motorista: só um código (letras, números, - _ .), sem nome nem documento"
    return {"tipo": tipo, "placa": placa, "nome": str(d.get("nome") or "").strip()[:80], "combustivel": comb, "tanque_l": tanque,
            "consumo_esperado": cons, "consumo_unidade": un, "no": no, "motorista": mot,
            "ativo": 1 if d.get("ativo", True) else 0}, ""


def validar_abastecimento(d: dict, hoje: str, veiculo: dict | None = None) -> tuple[dict | None, str, list]:
    """(abastecimento, erro, avisos). Preço só com a fonte. Litros acima do tanque: aviso (não erro)."""
    data = str(d.get("data") or "").strip()
    if not _DATA.match(data):
        return None, "data no formato AAAA-MM-DD", []
    try:
        datetime.strptime(data, "%Y-%m-%d")
    except ValueError:
        return None, "data inválida", []
    if data > hoje:
        return None, "data no futuro", []
    try:
        litros, preco, odo, hor = (_f(d.get(k)) for k in ("litros", "preco_l", "odometro", "horimetro"))
    except ValueError:
        return None, "litros, preço, odômetro e horímetro são números", []
    if litros is None or not 0 < litros <= 100000:
        return None, "litros maior que zero", []
    fonte = str(d.get("preco_fonte") or "").strip()
    if preco is not None:
        if preco < 0:
            return None, "preço por litro não negativo", []
        if fonte not in FONTES_PRECO:
            return None, "preço precisa da fonte: " + ", ".join(FONTES_PRECO), []
    else:
        fonte = ""
    if (odo is not None and odo < 0) or (hor is not None and hor < 0):
        return None, "odômetro e horímetro não negativos", []
    mot = str(d.get("motorista") or "").strip()
    if mot and not _ID.match(mot):
        return None, "motorista: só um código, sem nome nem documento", []
    avisos = []
    if veiculo and veiculo.get("tanque_l") and litros > veiculo["tanque_l"]:
        avisos.append("litros acima do tanque cadastrado: confira o tanque ou o abastecimento")
    return {"data": data, "litros": litros, "preco_l": preco, "preco_fonte": fonte, "odometro": odo, "horimetro": hor,
            "motorista": mot}, "", avisos


def validar_poligono(pol) -> tuple[list | None, str]:
    if not isinstance(pol, list) or not 3 <= len(pol) <= 500:
        return None, "a cerca precisa de 3 a 500 vértices"
    out = []
    for v in pol:
        try:
            la, lo = float(v[0]), float(v[1])
        except (TypeError, ValueError, IndexError):
            return None, "vértice [latitude, longitude]"
        if not (-90 <= la <= 90 and -180 <= lo <= 180) or not (math.isfinite(la) and math.isfinite(lo)):
            return None, "vértice fora da Terra"
        out.append([round(la, 7), round(lo, 7)])
    return out, ""


def _data_hora(s: str) -> float:
    """Epoch (s) de 'AAAA-MM-DD HH:MM[:SS]' (hora de Brasília), 'AAAA-MM-DDTHH:MM[:SS][Z|±hh:mm]' ou epoch."""
    s = str(s or "").strip()
    if re.fullmatch(r"\d{9,10}(\.\d+)?", s):
        return float(s)
    t = s.replace("T", " ")
    tz = None
    if t.endswith("Z"):
        t, tz = t[:-1], "Z"
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?)([+-]\d{2}:\d{2})?", t)
    if not m:
        raise ValueError
    fmt = "%Y-%m-%d %H:%M:%S" if len(m.group(1)) == 19 else "%Y-%m-%d %H:%M"
    d = datetime.strptime(m.group(1), fmt)
    if tz == "Z":
        return d.replace(tzinfo=clima_mod.timezone.utc).timestamp() if hasattr(clima_mod, "timezone") else \
            (d - datetime(1970, 1, 1)).total_seconds()
    if m.group(2):
        sinal = 1 if m.group(2)[0] == "+" else -1
        hh, mm = int(m.group(2)[1:3]), int(m.group(2)[4:6])
        return d.replace(tzinfo=timezone.utc).timestamp() - sinal * (hh * 3600 + mm * 60)
    return d.replace(tzinfo=FUSO).timestamp()


def ler_csv(texto: str, tipo: str, hoje: str) -> tuple[list[dict], list[str]]:
    """Valida o CSV inteiro (separador ; ou ,; vírgula decimal com ;). Tudo ou nada: qualquer erro recusa o arquivo."""
    if tipo not in CSV_COLUNAS:
        return [], ["tipo: rastreador ou cartao"]
    texto = (texto or "").lstrip("﻿")
    if not texto.strip():
        return [], ["CSV vazio"]
    primeira = texto.splitlines()[0]
    sep = ";" if primeira.count(";") >= primeira.count(",") and ";" in primeira else ","
    leitor = csv.reader(io.StringIO(texto), delimiter=sep)
    cab = [c.strip().lower() for c in next(leitor)]
    desconhecidas = [c for c in cab if c not in CSV_COLUNAS[tipo]]
    if desconhecidas:
        return [], ["colunas desconhecidas: " + ", ".join(desconhecidas[:5]) + " (aceitas: " + ", ".join(CSV_COLUNAS[tipo]) + ")"]
    faltam = [c for c in CSV_OBRIGATORIAS[tipo] if c not in cab]
    if faltam:
        return [], ["faltam as colunas " + ", ".join(faltam)]
    if len(set(cab)) != len(cab):
        return [], ["coluna repetida"]
    linhas, erros = [], []
    for n, cel in enumerate(leitor, start=2):
        if not any(x.strip() for x in cel):
            continue
        if len(linhas) >= CSV_LINHAS[tipo]:
            erros.append(f"mais de {CSV_LINHAS[tipo]} linhas")
            break
        if len(cel) != len(cab):
            erros.append(f"linha {n}: {len(cel)} colunas, esperado {len(cab)}")
            continue
        v = dict(zip(cab, (x.strip() for x in cel)))
        try:
            if tipo == "rastreador":
                p = {"ts": _data_hora(v["data_hora"])}
                for k in ("lat", "lon", "vel", "rumo", "flx", "niv", "hor", "odo"):
                    p[k] = _f(v.get(k))
            else:
                p = {"data": v["data"], "litros": _f(v["litros"]), "preco_l": _f(v.get("preco_l")),
                     "odometro": _f(v.get("odometro")), "horimetro": _f(v.get("horimetro")), "motorista": v.get("motorista", "")}
        except (ValueError, KeyError):
            erros.append(f"linha {n}: número ou data inválida")
            continue
        if tipo == "rastreador":
            if p["lat"] is None or p["lon"] is None or not (-90 <= p["lat"] <= 90 and -180 <= p["lon"] <= 180):
                erros.append(f"linha {n}: latitude e longitude")
                continue
            if not 1_700_000_000 <= p["ts"] <= 4_102_444_800:
                erros.append(f"linha {n}: data e hora fora do intervalo aceito")
                continue
            ruim = [k for k, (lo, hi) in (("vel", (0, math.inf)), ("rumo", (0, 360)), ("flx", (0, math.inf)), ("niv", (0, 100)),
                                          ("hor", (0, math.inf)), ("odo", (0, math.inf))) if p[k] is not None and not lo <= p[k] <= hi]
            if ruim:
                erros.append(f"linha {n}: fora da faixa física ({', '.join(ruim)})")
                continue
        else:
            a, erro, _ = validar_abastecimento(dict(p, preco_fonte="cartao" if p["preco_l"] is not None else ""), hoje)
            if not a:
                erros.append(f"linha {n}: {erro}")
                continue
            p = a
        linhas.append(p)
    if not linhas and not erros:
        erros.append("nenhuma linha de dados")
    return linhas, erros


# ══ Banco ════════════════════════════════════════════════════════════════════════════════════
class Frota:
    COLS_V = ("id", "tipo", "placa", "nome", "combustivel", "tanque_l", "consumo_esperado", "consumo_unidade", "no",
              "motorista", "ativo", "criado", "atualizado", "por")
    COLS_A = ("id", "veiculo", "data", "litros", "preco_l", "preco_fonte", "odometro", "horimetro", "motorista",
              "comprovante", "origem", "criado", "por")
    COLS_P = ("veiculo", "no", "ts", "lat", "lon", "vel", "rumo", "flx", "niv", "hor", "odo", "ign", "origem")

    def __init__(self, hub, relogio=None, pasta: str | Path | None = None, premissas_base=None, fatores=None):
        self.hub = hub
        self.relogio = relogio or hub.relogio
        self.P = premissas(premissas_base)
        self._F = fatores
        self.pasta = Path(pasta or os.environ.get("PHYSIS_FROTA_PASTA") or (RAIZ / "dados" / "frota-comprovantes"))
        self._limpo_em = 0.0
        with hub._trava:
            hub._db.executescript(ESQUEMA)
            hub._db.commit()

    @property
    def _db(self):
        return self.hub._db

    def F(self) -> dict:
        if self._F is None:
            self._F = fatores() or {}
        return self._F

    def _hoje(self) -> str:
        return dia_de(self.relogio())

    def retencao_dias(self) -> int:
        r = self._db.execute("SELECT valor FROM frota_config WHERE chave='retencao_dias'").fetchone()
        try:
            return max(1, int(r[0])) if r else int(self.P["frota.retencao_dias"])
        except (TypeError, ValueError):
            return int(self.P["frota.retencao_dias"])

    # ── leitura ───────────────────────────────────────────────────────────────────────────
    def veiculos(self) -> list[dict]:
        return [dict(zip(self.COLS_V, r)) for r in self._db.execute(f"SELECT {','.join(self.COLS_V)} FROM frota_veiculo ORDER BY id")]

    def _veiculo(self, vid: int) -> dict | None:
        r = self._db.execute(f"SELECT {','.join(self.COLS_V)} FROM frota_veiculo WHERE id=?", (int(vid),)).fetchone()
        return dict(zip(self.COLS_V, r)) if r else None

    def abastecimentos(self, veiculo: int | None = None, limite: int = 5000) -> list[dict]:
        q, par = f"SELECT {','.join(self.COLS_A)} FROM frota_abastecimento", ()
        if veiculo is not None:
            q, par = q + " WHERE veiculo=?", (int(veiculo),)
        return [dict(zip(self.COLS_A, r)) for r in self._db.execute(q + " ORDER BY data DESC, id DESC LIMIT ?", par + (int(limite),))]

    def pontos(self, veiculo: int, desde: float, ate: float | None = None, limite: int = 20000) -> list[dict]:
        rs = self._db.execute(f"SELECT {','.join(self.COLS_P)} FROM frota_ponto WHERE veiculo=? AND ts>=? AND ts<=? ORDER BY ts LIMIT ?",
                              (int(veiculo), float(desde), float(ate if ate is not None else 9e12), int(limite)))
        return [{k: v for k, v in zip(self.COLS_P, r)} for r in rs]

    def cercas(self) -> list[dict]:
        out = []
        for i, n, p, vs, a in self._db.execute("SELECT id, nome, poligono, veiculos, ativa FROM frota_cerca ORDER BY id"):
            out.append({"id": i, "nome": n, "poligono": json.loads(p), "veiculos": json.loads(vs), "ativa": bool(a)})
        return out

    # ── telemetria (V6 TIPO:VEI pelo hub) ─────────────────────────────────────────────────
    def receber_v6(self, est: dict, ts: float, linha: str = "") -> bool:
        """Chamado pelo hub (com a trava do hub) para cada linha VEI aceita. Guarda o ponto do veículo ligado ao nó;
        nó sem veículo também fica (aparece em "nós sem veículo")."""
        no = est.get("id")
        gps_ok = est.get("gps") is not False
        p = {"lat": est.get("lat") if gps_ok else None, "lon": est.get("lon") if gps_ok else None}
        for k in ("vel", "rumo", "flx", "niv", "hor", "odo"):
            p[k] = est.get(k)
        p["ign"] = None if est.get("ign") is None else int(bool(est["ign"]))
        if all(v is None for v in p.values()):
            return False
        r = self._db.execute("SELECT id FROM frota_veiculo WHERE no=? AND ativo=1 ORDER BY id LIMIT 1", (int(no),)).fetchone()
        vid = r[0] if r else None
        origem = "v6-simulado" if "SIM:SIMULADO" in (linha or "") else "v6"
        cur = self._db.execute("INSERT OR IGNORE INTO frota_ponto(chave,veiculo,no,ts,lat,lon,vel,rumo,flx,niv,hor,odo,ign,origem) "
                               "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (f"v{vid}" if vid else f"n{no}", vid, no, float(ts), p["lat"], p["lon"], p["vel"], p["rumo"],
                                p["flx"], p["niv"], p["hor"], p["odo"], p["ign"], origem))
        self._limpar_antigos()
        return cur.rowcount > 0

    def _limpar_antigos(self, forcar: bool = False) -> int:
        """Retenção (LGPD): apaga pontos mais velhos que retencao_dias. No máximo uma vez por hora."""
        agora = self.relogio()
        if not forcar and agora - self._limpo_em < 3600:
            return 0
        self._limpo_em = agora
        n = self._db.execute("DELETE FROM frota_ponto WHERE ts < ?", (agora - self.retencao_dias() * 86400,)).rowcount
        return n

    # ── escrita ───────────────────────────────────────────────────────────────────────────
    def gravar_veiculo(self, d: dict, quem: str) -> dict:
        v, erro = validar_veiculo(d)
        if not v:
            return {"ok": False, "erro": erro}
        agora = self.relogio()
        with self.hub._trava:
            if v["no"] is not None:
                r = self._db.execute("SELECT id FROM frota_veiculo WHERE no=? AND ativo=1 AND id<>?", (v["no"], int(d.get("id") or 0))).fetchone()
                if r:
                    return {"ok": False, "erro": f"o nó {v['no']:02d} já está ligado a outro veículo"}
            if d.get("id"):
                if not self._veiculo(d["id"]):
                    return {"ok": False, "erro": "veículo desconhecido", "codigo": 404}
                self._db.execute("UPDATE frota_veiculo SET tipo=?,placa=?,nome=?,combustivel=?,tanque_l=?,consumo_esperado=?,consumo_unidade=?,"
                                 "no=?,motorista=?,ativo=?,atualizado=?,por=? WHERE id=?",
                                 (v["tipo"], v["placa"], v["nome"], v["combustivel"], v["tanque_l"], v["consumo_esperado"],
                                  v["consumo_unidade"], v["no"], v["motorista"], v["ativo"], agora, quem, int(d["id"])))
                vid = int(d["id"])
            else:
                vid = self._db.execute("INSERT INTO frota_veiculo(tipo,placa,nome,combustivel,tanque_l,consumo_esperado,consumo_unidade,no,"
                                       "motorista,ativo,criado,atualizado,por) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                       (v["tipo"], v["placa"], v["nome"], v["combustivel"], v["tanque_l"], v["consumo_esperado"],
                                        v["consumo_unidade"], v["no"], v["motorista"], v["ativo"], agora, agora, quem)).lastrowid
            if v["no"] is not None and v["ativo"]:     # pontos do nó que chegaram antes de ligar: passam para o veículo
                self._db.execute("UPDATE OR IGNORE frota_ponto SET veiculo=?, chave=? WHERE veiculo IS NULL AND no=?", (vid, f"v{vid}", v["no"]))
            self.hub.registrar("frota", quem, {"o_que": "veiculo", "id": vid})
            self._db.commit()
        return {"ok": True, "id": vid}

    def remover_veiculo(self, vid: int, quem: str) -> dict:
        with self.hub._trava:
            if not self._veiculo(vid):
                return {"ok": False, "erro": "veículo desconhecido", "codigo": 404}
            for (arq,) in self._db.execute("SELECT arquivo FROM frota_arquivo WHERE veiculo=?", (int(vid),)).fetchall():
                self._apagar_arquivo_se_orfao(arq, int(vid))
            for t in ("frota_ponto", "frota_abastecimento", "frota_arquivo", "frota_importacao"):
                self._db.execute(f"DELETE FROM {t} WHERE veiculo=?", (int(vid),))
            self._db.execute("DELETE FROM frota_veiculo WHERE id=?", (int(vid),))
            self.hub.registrar("frota", quem, {"o_que": "veiculo apagado", "id": int(vid)})
            self._db.commit()
        return {"ok": True}

    def abastecer(self, d: dict, quem: str, origem: str = "manual") -> dict:
        v = self._veiculo(d.get("veiculo") or 0)
        if not v:
            return {"ok": False, "erro": "veículo desconhecido", "codigo": 404}
        a, erro, avisos = validar_abastecimento(d, self._hoje(), v)
        if not a:
            return {"ok": False, "erro": erro}
        comp = d.get("comprovante")
        if comp is not None and not self._db.execute("SELECT 1 FROM frota_arquivo WHERE id=? AND veiculo=?", (int(comp), v["id"])).fetchone():
            return {"ok": False, "erro": "comprovante desconhecido"}
        with self.hub._trava:
            aid = self._db.execute("INSERT INTO frota_abastecimento(veiculo,data,litros,preco_l,preco_fonte,odometro,horimetro,motorista,"
                                   "comprovante,origem,criado,por) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                                   (v["id"], a["data"], a["litros"], a["preco_l"], a["preco_fonte"], a["odometro"], a["horimetro"],
                                    a["motorista"], comp, origem, self.relogio(), quem)).lastrowid
            self.hub.registrar("frota", quem, {"o_que": "abastecimento", "id": aid, "veiculo": v["id"]})
            self._db.commit()
        return {"ok": True, "id": aid, "avisos": avisos}

    def remover_abastecimento(self, aid: int, quem: str) -> dict:
        with self.hub._trava:
            n = self._db.execute("DELETE FROM frota_abastecimento WHERE id=?", (int(aid),)).rowcount
            if n:
                self.hub.registrar("frota", quem, {"o_que": "abastecimento apagado", "id": int(aid)})
            self._db.commit()
        return {"ok": n > 0} if n else {"ok": False, "erro": "abastecimento desconhecido", "codigo": 404}

    def gravar_cerca(self, d: dict, quem: str) -> dict:
        pol, erro = validar_poligono(d.get("poligono"))
        if not pol:
            return {"ok": False, "erro": erro}
        nome = str(d.get("nome") or "").strip()[:80]
        if not nome:
            return {"ok": False, "erro": "nome da cerca"}
        ids = {v["id"] for v in self.veiculos()}
        vs = d.get("veiculos") or []
        if any(not isinstance(x, int) or x not in ids for x in vs):
            return {"ok": False, "erro": "veículo desconhecido na cerca"}
        with self.hub._trava:
            if d.get("id"):
                n = self._db.execute("UPDATE frota_cerca SET nome=?, poligono=?, veiculos=?, ativa=? WHERE id=?",
                                     (nome, json.dumps(pol), json.dumps(sorted(set(vs))), 0 if d.get("ativa") is False else 1, int(d["id"]))).rowcount
                if not n:
                    return {"ok": False, "erro": "cerca desconhecida", "codigo": 404}
                cid = int(d["id"])
            else:
                cid = self._db.execute("INSERT INTO frota_cerca(nome,poligono,veiculos,ativa,criado,por) VALUES(?,?,?,?,?,?)",
                                       (nome, json.dumps(pol), json.dumps(sorted(set(vs))), 0 if d.get("ativa") is False else 1,
                                        self.relogio(), quem)).lastrowid
            self.hub.registrar("frota", quem, {"o_que": "cerca", "id": cid})
            self._db.commit()
        return {"ok": True, "id": cid}

    def remover_cerca(self, cid: int, quem: str) -> dict:
        with self.hub._trava:
            n = self._db.execute("DELETE FROM frota_cerca WHERE id=?", (int(cid),)).rowcount
            self._db.commit()
        return {"ok": True} if n else {"ok": False, "erro": "cerca desconhecida", "codigo": 404}

    def configurar(self, d: dict, quem: str) -> dict:
        dias = d.get("retencao_dias")
        if not isinstance(dias, int) or not 1 <= dias <= 3650:
            return {"ok": False, "erro": "retenção de 1 a 3650 dias"}
        with self.hub._trava:
            self._db.execute("INSERT OR REPLACE INTO frota_config(chave,valor,quando,por) VALUES('retencao_dias',?,?,?)",
                             (str(dias), self.relogio(), quem))
            apagados = self._limpar_antigos(forcar=True)
            self.hub.registrar("frota", quem, {"o_que": "retencao", "dias": dias, "pontos_apagados": apagados})
            self._db.commit()
        return {"ok": True, "retencao_dias": dias, "pontos_apagados": apagados}

    # ── comprovantes (só a equipe) ────────────────────────────────────────────────────────
    def comprovante_por(self, veiculo: int, nome: str, dados: bytes, quem: str) -> dict:
        if not self._veiculo(veiculo):
            return {"ok": False, "erro": "veículo desconhecido", "codigo": 404}
        nome = (nome or "comprovante").replace("\\", "/").rsplit("/", 1)[-1].strip()[:120] or "comprovante"
        if not dados:
            return {"ok": False, "erro": "arquivo vazio"}
        if len(dados) > ARQ_MAX:
            return {"ok": False, "erro": "arquivo maior que 10 MB"}
        if seg.eh_executavel(dados):
            return {"ok": False, "erro": "arquivo executável não é aceito"}
        ext = os.path.splitext(nome.lower())[1]
        if ext not in ARQ_TIPOS:
            return {"ok": False, "erro": "tipo não aceito: PDF, PNG, JPEG ou WEBP"}
        mime, assin = ARQ_TIPOS[ext]
        if not any(dados.startswith(a) for a in assin) or (ext == ".webp" and dados[8:12] != b"WEBP"):
            return {"ok": False, "erro": "o conteúdo do arquivo não confere com a extensão"}
        sha = hashlib.sha256(dados).hexdigest()
        self.pasta.mkdir(parents=True, exist_ok=True)
        arq = sha + ext                                  # nome no disco = resumo (nada vindo de quem enviou)
        destino = self.pasta / arq
        if not destino.is_file():
            tmp = destino.with_suffix(destino.suffix + ".tmp")
            tmp.write_bytes(dados)
            os.replace(tmp, destino)
        with self.hub._trava:
            aid = self._db.execute("INSERT INTO frota_arquivo(veiculo,nome,mime,tamanho,sha256,arquivo,criado,por) VALUES(?,?,?,?,?,?,?,?)",
                                   (int(veiculo), nome, mime, len(dados), sha, arq, self.relogio(), quem)).lastrowid
            self.hub.registrar("frota", quem, {"o_que": "comprovante", "id": aid, "sha256": sha})
            self._db.commit()
        return {"ok": True, "id": aid, "sha256": sha, "tamanho": len(dados)}

    def comprovante(self, aid: int) -> tuple[str, str, bytes] | None:
        r = self._db.execute("SELECT nome, mime, sha256, arquivo FROM frota_arquivo WHERE id=?", (int(aid),)).fetchone()
        if not r:
            return None
        try:
            dados = (self.pasta / r[3]).read_bytes()
        except OSError:
            return None
        if hashlib.sha256(dados).hexdigest() != r[2]:
            return None                                  # arquivo mexido no disco: não entrega
        return r[0], r[1], dados

    def _apagar_arquivo_se_orfao(self, arq: str, veiculo: int) -> None:
        if not self._db.execute("SELECT 1 FROM frota_arquivo WHERE arquivo=? AND veiculo<>?", (arq, veiculo)).fetchone():
            try:
                (self.pasta / arq).unlink()
            except OSError:
                pass

    # ── importação CSV ────────────────────────────────────────────────────────────────────
    @staticmethod
    def resumo_importacao(veiculo: int, tipo: str, linhas: list[dict]) -> str:
        return integridade.resumo({"veiculo": veiculo, "tipo": tipo, "colunas": list(CSV_COLUNAS[tipo]), "linhas": linhas})

    def importar(self, d: dict, quem: str) -> dict:
        v = self._veiculo(d.get("veiculo") or 0)
        if not v:
            return {"ok": False, "erro": "veículo desconhecido", "codigo": 404}
        tipo, texto = str(d.get("tipo") or ""), str(d.get("csv") or "")
        linhas, erros = ler_csv(texto, tipo, self._hoje())
        if erros:
            return {"ok": False, "erro": "CSV recusado: nada foi gravado", "erros": erros[:50]}
        resumo = self.resumo_importacao(v["id"], tipo, linhas)
        bruto = hashlib.sha256(texto.lstrip("﻿").replace("\r\n", "\n").encode("utf-8")).hexdigest()
        info = {"linhas": len(linhas), "resumo": resumo, "arquivo_sha256": bruto, "tipo": tipo, "veiculo": v["id"]}
        if d.get("simular"):
            return dict(info, ok=True, simulado=True)
        novas = 0
        with self.hub._trava:
            imp = self._db.execute("INSERT INTO frota_importacao(veiculo,tipo,nome_arquivo,linhas,novas,resumo,arquivo_sha256,quando,por) "
                                   "VALUES(?,?,?,?,0,?,?,?,?)", (v["id"], tipo, str(d.get("nome") or "")[:160], len(linhas), resumo,
                                                                  bruto, self.relogio(), quem)).lastrowid
            for p in linhas:
                if tipo == "rastreador":
                    novas += self._db.execute(
                        "INSERT OR IGNORE INTO frota_ponto(chave,veiculo,no,ts,lat,lon,vel,rumo,flx,niv,hor,odo,ign,origem) "
                        "VALUES(?,?,NULL,?,?,?,?,?,?,?,?,?,NULL,?)",
                        (f"v{v['id']}", v["id"], p["ts"], p["lat"], p["lon"], p["vel"], p["rumo"], p["flx"], p["niv"], p["hor"],
                         p["odo"], f"csv:{imp}")).rowcount
                else:
                    if self._db.execute("SELECT 1 FROM frota_abastecimento WHERE veiculo=? AND data=? AND litros=? AND "
                                        "IFNULL(odometro,-1)=IFNULL(?,-1)", (v["id"], p["data"], p["litros"], p["odometro"])).fetchone():
                        continue                            # o mesmo abastecimento importado de novo não duplica
                    self._db.execute("INSERT INTO frota_abastecimento(veiculo,data,litros,preco_l,preco_fonte,odometro,horimetro,motorista,"
                                     "comprovante,origem,criado,por) VALUES(?,?,?,?,?,?,?,?,NULL,?,?,?)",
                                     (v["id"], p["data"], p["litros"], p["preco_l"], p["preco_fonte"], p["odometro"], p["horimetro"],
                                      p["motorista"], f"csv:{imp}", self.relogio(), quem))
                    novas += 1
            self._db.execute("UPDATE frota_importacao SET novas=? WHERE id=?", (novas, imp))
            self.hub.registrar("frota", quem, {"o_que": "importacao", "id": imp, "resumo": resumo})
            self._db.commit()
        return dict(info, ok=True, importacao=imp, novas=novas)

    # ── contas por veículo ────────────────────────────────────────────────────────────────
    def analise(self, v: dict, pontos: list[dict], abast: list[dict], cercas: list[dict]) -> dict:
        P = self.P
        dias = por_dia(pontos, P["frota.gps_salto_kmh"], P["frota.marcha_lenta_vel_kmh"], P["frota.marcha_lenta_min"])
        amostras = amostras_consumo(dias, abast, v["consumo_unidade"], self._hoje())
        alertas = []
        if amostras:
            ult = amostras[-1]
            r = anomalia_consumo(ult["valor"], [a["valor"] for a in amostras[:-1]], P["frota.anomalia_z"],
                                 int(P["frota.anomalia_amostra_min"]), P["frota.ewma_alfa"], P["frota.anomalia_desvio_min_pct"])
            normal = r
            if r["anomalo"]:
                alertas.append({"tipo": "consumo", "nivel": "atencao", "ts": None, "data": ult["data"],
                                "valor": ult["valor"], "unidade": UNIDADES_CONSUMO[v["consumo_unidade"]], "z": r["z"],
                                "mediana": r["mediana"], "ewma": r["ewma"], "n": r["n"], "fonte": ult["fonte"]})
        else:
            normal = dict(normal_aprendido([], P["frota.ewma_alfa"]), motivo="sem amostras de consumo ainda")
        for q in quedas_sem_andar(pontos, P["frota.queda_nivel_pct"], P["frota.parado_distancia_km"],
                                  P["frota.marcha_lenta_vel_kmh"], v.get("tanque_l")):
            alertas.append(dict(q, tipo="queda_nivel", nivel="alarme", ts=q["ts_fim"]))
        for m in marcha_lenta(pontos, P["frota.marcha_lenta_vel_kmh"], P["frota.marcha_lenta_min"])["eventos"]:
            alertas.append(dict(m, tipo="marcha_lenta", nivel="atencao", ts=m["ts_fim"]))
        for s in saidas_da_cerca(pontos, cercas, v["id"]):
            alertas.append(dict(s, tipo="cerca", nivel="alarme"))
        ult = next((p for p in reversed(pontos) if _tem_pos(p)), None)
        ult_any = pontos[-1] if pontos else None
        return {"dias": dias, "amostras": amostras[-60:], "normal": normal, "alertas": alertas,
                "ultima": ({k: ult_any.get(k) for k in ("ts", "vel", "rumo", "flx", "niv", "hor", "odo", "ign", "origem")}
                           | ({"lat": ult["lat"], "lon": ult["lon"], "ts_pos": ult["ts"]} if ult else {})) if ult_any else None,
                "simulado": any(str(p.get("origem", "")).endswith("simulado") for p in pontos)}

    def estado(self, ano: str | None = None, completo: bool = False) -> dict:
        """Tudo o que a aba precisa: veículos com a última posição, abastecimentos, cercas, alertas, totais por dia e mês,
        CO₂e, linhas para o Carbono e custos para a Gestão. completo=False tira o código do motorista (LGPD)."""
        agora = self.relogio()
        with self.hub._trava:
            self._limpar_antigos()
            vs, abast, cercas = self.veiculos(), self.abastecimentos(), self.cercas()
            desde = agora - PONTOS_ESTADO_DIAS * 86400
            pts = {v["id"]: self.pontos(v["id"], desde) for v in vs}
            soltos = [{"no": n, "pontos": c, "ultimo": t} for n, c, t in self._db.execute(
                "SELECT no, COUNT(*), MAX(ts) FROM frota_ponto WHERE veiculo IS NULL GROUP BY no ORDER BY no")]
            ano = str(ano or datetime.fromtimestamp(agora, FUSO).year)
            ini_ano = datetime(int(ano), 1, 1, tzinfo=FUSO).timestamp()
            fluxo_ano = {}
            for v in vs:
                ps = [p for p in self.pontos(v["id"], ini_ano, datetime(int(ano) + 1, 1, 1, tzinfo=FUSO).timestamp(), 200000)
                      if not str(p.get("origem", "")).endswith("simulado")]
                fluxo_ano[v["id"]] = litros_do_fluxo(ps) or 0.0
        F = self.F()
        out_v, alertas, por_mes = [], [], {}
        for v in vs:
            ab_v = [a for a in abast if a["veiculo"] == v["id"]]
            an = self.analise(v, pts[v["id"]], sorted(ab_v, key=lambda a: a["data"]), cercas)
            litros_ab = sum(a["litros"] for a in ab_v)
            emis = co2e(v["combustivel"], litros_ab, F)
            for d, x in an["dias"].items():
                m = por_mes.setdefault(d[:7], {}).setdefault(v["id"], {"km": 0.0, "litros_fluxo": 0.0, "horas_motor": 0.0, "horas_marcha_lenta": 0.0})
                m["km"] += x["km"] or 0.0
                m["litros_fluxo"] += x["litros_fluxo"] or 0.0
                m["horas_motor"] += x["horas_motor"] or 0.0
                m["horas_marcha_lenta"] += x["horas_marcha_lenta"] or 0.0
            for al in an["alertas"]:
                alertas.append(dict(al, veiculo=v["id"], placa=v["placa"]))
            vv = dict(v, analise=an, litros_abastecidos=litros_ab, co2e_t=emis["t"], co2_bio_t=emis["bio_t"])
            if not completo:
                vv["motorista"] = ""
            out_v.append(vv)
        ab_out = [dict(a, motorista=a["motorista"] if completo else "") for a in abast[:500]]
        alertas.sort(key=lambda a: -(a.get("ts") or 0))
        return {"ok": True, "agora": agora, "veiculos": out_v, "abastecimentos": ab_out, "cercas": cercas, "alertas": alertas,
                "por_mes": por_mes, "nos_sem_veiculo": soltos, "ano": ano,
                "para_carbono": para_carbono(vs, abast, ano, fluxo_ano), "custos_por_mes": custos_por_mes(abast),
                "premissas": {k: v for k, v in self.P.items()}, "premissas_status": "conferir", "retencao_dias": self.retencao_dias(),
                "aviso_lgpd": AVISO_LGPD, "tipos": TIPOS, "combustiveis": list(COMBUSTIVEIS), "fontes_preco": FONTES_PRECO}

    def rota_do_dia(self, vid: int, dia: str) -> dict:
        v = self._veiculo(vid)
        if not v:
            return {"ok": False, "erro": "veículo desconhecido", "codigo": 404}
        if not _DATA.match(dia or ""):
            return {"ok": False, "erro": "dia no formato AAAA-MM-DD"}
        ini = datetime.strptime(dia, "%Y-%m-%d").replace(tzinfo=FUSO).timestamp()
        with self.hub._trava:
            ps = self.pontos(vid, ini, ini + 86400 - 0.001, 20000)
        P = self.P
        dist, lf, hm = distancia(ps, P["frota.gps_salto_kmh"]), litros_do_fluxo(ps), horas_motor(ps)
        tv = trechos_com_vazao(ps, P["frota.gps_salto_kmh"])
        return {"ok": True, "veiculo": vid, "dia": dia, "pontos": ps, "distancia": dist, "litros_fluxo": lf, "horas_motor": hm,
                "consumo": consumo(tv["litros"], tv["km"], tv["horas"]),
                "marcha_lenta": marcha_lenta(ps, P["frota.marcha_lenta_vel_kmh"], P["frota.marcha_lenta_min"])}

    def exportar_csv(self, tipo: str, com_motorista: bool = False) -> tuple[str | None, str]:
        """CSV (; e vírgula decimal) dos abastecimentos ou dos pontos. Sem o código do motorista, a não ser com_motorista."""
        cel = lambda x: "" if x is None else (f"{x}".replace(".", ",") if isinstance(x, float) else
                                              ("'" + str(x) if str(x)[:1] in ("=", "+", "-", "@") else str(x)))
        placas = {v["id"]: v["placa"] for v in self.veiculos()}
        linhas = []
        if tipo == "abastecimentos":
            cab = ["placa", "data", "litros", "preco_l", "preco_fonte", "odometro", "horimetro", "origem"] + (["motorista"] if com_motorista else [])
            for a in reversed(self.abastecimentos(limite=100000)):
                linhas.append([placas.get(a["veiculo"], ""), a["data"], a["litros"], a["preco_l"], a["preco_fonte"], a["odometro"],
                               a["horimetro"], a["origem"]] + ([a["motorista"]] if com_motorista else []))
        elif tipo == "pontos":
            cab = ["placa", "data_hora", "lat", "lon", "vel", "rumo", "flx", "niv", "hor", "odo", "origem"]
            for r in self._db.execute("SELECT veiculo, ts, lat, lon, vel, rumo, flx, niv, hor, odo, origem FROM frota_ponto "
                                      "WHERE veiculo IS NOT NULL ORDER BY veiculo, ts LIMIT 200000"):
                linhas.append([placas.get(r[0], "")] + [datetime.fromtimestamp(r[1], FUSO).strftime("%Y-%m-%d %H:%M:%S")] + list(r[2:]))
        else:
            return None, "tipo: abastecimentos ou pontos"
        txt = "\n".join(";".join(cel(x) for x in l) for l in [cab] + linhas) + "\n"
        return txt, f"frota-{tipo}-{self._hoje()}.csv"

    # ── rotas (o servidor confere sessão, CSRF e limite por IP antes) ─────────────────────
    def rota(self, metodo: str, caminho: str, conta: dict | None, corpo=None, consulta: dict | None = None):
        """(código, resposta). Resposta dict, ou ("bytes", nome, mime, dados).
        GET  /api/frota/estado?ano=          cliente+ (código do motorista só para a direção com ?motoristas=1)
        GET  /api/frota/rota?veiculo=&dia=   cliente+
        GET  /api/frota/exportar?tipo=abastecimentos|pontos[&motoristas=1]   equipe (motoristas: só a direção)
        GET  /api/frota/comprovante/<id>     equipe
        POST /api/frota/veiculo | abastecimento | abastecimento/remover | cerca | cerca/remover | importar   equipe
        POST /api/frota/comprovante?veiculo=&nome=   corpo = bytes do arquivo, equipe
        POST /api/frota/veiculo/remover | config     direção"""
        if not caminho.startswith("/api/frota"):
            return None
        if not conta:
            return 401, {"ok": False, "erro": "entre com usuario e senha", "login": True}
        consulta = consulta or {}
        g = lambda k, n=40: str((consulta.get(k) or [""])[0])[:n]
        cliente, equipe, direcao = seg.pode(conta, seg.CLIENTE), seg.pode(conta, seg.EQUIPE), seg.pode(conta, seg.DIRECAO)
        quem = conta.get("usuario") or "?"
        negado = (403, {"ok": False, "erro": "o seu papel não permite esta ação"})
        resp = lambda r: (r.pop("codigo", 200 if r.get("ok") else 400), r)
        p = caminho.rstrip("/")
        if metodo == "GET":
            if not cliente:
                return negado
            if p == "/api/frota/estado":
                ano = g("ano", 4)
                return 200, self.estado(ano if re.fullmatch(r"\d{4}", ano) else None, completo=direcao and g("motoristas") == "1")
            if p == "/api/frota/rota":
                vid = g("veiculo", 12)
                return resp(self.rota_do_dia(int(vid) if vid.isdigit() else 0, g("dia", 10)))
            if not equipe:
                return negado
            if p == "/api/frota/exportar":
                com = g("motoristas") == "1"
                if com and not direcao:
                    return negado
                txt, nome = self.exportar_csv(g("tipo", 20), com)
                if txt is None:
                    return 400, {"ok": False, "erro": nome}
                return 200, ("bytes", nome, "text/csv; charset=utf-8", ("﻿" + txt).encode("utf-8"))
            m = re.fullmatch(r"/api/frota/comprovante/(\d{1,12})", p)
            if m:
                a = self.comprovante(int(m.group(1)))
                return (200, ("bytes", a[0], a[1], a[2])) if a else (404, {"ok": False, "erro": "comprovante não encontrado"})
            return 404, {"ok": False, "erro": "rota desconhecida"}
        if metodo != "POST":
            return 405, {"ok": False, "erro": "método não aceito"}
        if not equipe:
            return negado
        if p == "/api/frota/comprovante":
            dados = corpo if isinstance(corpo, (bytes, bytearray)) else (corpo or "").encode("utf-8")
            vid = g("veiculo", 12)
            return resp(self.comprovante_por(int(vid) if vid.isdigit() else 0, g("nome", 160), bytes(dados), quem))
        rotas = {"/api/frota/veiculo": ("frota_veiculo", lambda d: self.gravar_veiculo(d, quem), False),
                 "/api/frota/veiculo/remover": ("frota_id", lambda d: self.remover_veiculo(d["id"], quem), True),
                 "/api/frota/abastecimento": ("frota_abastecimento", lambda d: self.abastecer(d, quem), False),
                 "/api/frota/abastecimento/remover": ("frota_id", lambda d: self.remover_abastecimento(d["id"], quem), False),
                 "/api/frota/cerca": ("frota_cerca", lambda d: self.gravar_cerca(d, quem), False),
                 "/api/frota/cerca/remover": ("frota_id", lambda d: self.remover_cerca(d["id"], quem), False),
                 "/api/frota/importar": ("frota_importar", lambda d: self.importar(d, quem), False),
                 "/api/frota/config": ("frota_config", lambda d: self.configurar(d, quem), True)}
        if p not in rotas:
            return 404, {"ok": False, "erro": "rota desconhecida"}
        esq, fazer, so_direcao = rotas[p]
        if so_direcao and not direcao:
            return negado
        try:
            d = seg.carregar_json(corpo or "{}")
        except ValueError:
            return 400, {"ok": False, "erro": "json invalido"}
        erro = seg.validar(d, seg.ESQUEMAS.get(esq) or ESQUEMAS[esq], estrito=True)
        if erro:
            return 400, {"ok": False, "erro": erro}
        return resp(fazer(d))


def pasta_padrao(banco: str | os.PathLike) -> Path:
    """PHYSIS_FROTA_PASTA ou a pasta do banco + /frota-comprovantes (mesmo padrão dos fornecedores)."""
    return Path(os.environ.get("PHYSIS_FROTA_PASTA") or (Path(banco).resolve().parent / "frota-comprovantes"))

