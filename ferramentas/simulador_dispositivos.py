#!/usr/bin/env python3
"""SIMULADOR DE DISPOSITIVOS — SÓ PARA TESTE. Nunca rodar na instalação de um cliente de verdade.

Alimenta um hub Physis (pacote de cliente rodando no próprio computador) com aparelhos simulados, para ver os
módulos funcionando: Monitoramento, Água, energia, alertas, aprendizado e Indicadores. Instalação real não tem dado
inventado; este programa existe só para as versões de teste.

Como entra no hub (o mesmo caminho dos aparelhos de verdade, docs/PROTOCOLO.md e docs/EXTENSAO_V6.md):
  - linhas V6 em POST /api/v6/linha (o caminho dos aparelhos Wi-Fi). Sem conta: o hub aceita linha sem chave só da rede
    local (o "pareamento" local que já existe). Com --usuario (conta da direção): o simulador cria uma chave por aparelho
    em /api/dispositivos/chaves, com o rótulo "SIMULADO / teste · <nome>", e manda cada linha com a chave dele;
  - qualidade da água (pH, turbidez, cloro): não há tipo V6 para isso; vai, com --usuario, para a lista de leituras da aba
    Água (physis-ph-leituras), cada leitura com origem "simulador", simulado: true e obs "SIMULADO / teste".
Toda linha leva a chave extra SIM:SIMULADO/teste (o hub aceita chave desconhecida e guarda a linha inteira), e é por ela
que --limpar acha o que apagar.

Aparelhos (ID = --id-base + n; padrão 81 a 89):
  81 SOLO  nó de solo "Talhão A": umidade do solo (2 sensores), irrigação, temperatura e umidade do ar, solo, bateria
  82 SOLO  nó de solo "Talhão B"
  83 PLUV  pluviômetro de báscula (CHI mm no intervalo, PUL pulsos)
  84 ENE   medidor de energia (PW kW, QR kvar, S kVA, V, I, FP), com geração solar ao meio-dia
  85 HID   medidor de água (Q m³/h, PR bar)
  86 SEC   secador solar (TI UI TE UE TC VENT PESO IRR)
  87 VEI   caminhão SIMULADO (GPS, VEL, RUMO, FLX, NIV, ODO, IGN): ida e volta de hora em hora até a "cidade" (3 km)
  88 VEI   carro SIMULADO: uma viagem por dia ao vizinho
  89 VEI   trator SIMULADO (com HOR): linhas de ida e volta num talhão
Os veículos andam em volta do local da instalação (GET /api/clima → lugar; ou --lat/--lon; sem nenhum, um ponto de exemplo
avisado na tela), com uma linha a cada 2 min com o motor ligado e a cada 30 min parado, só nos últimos --dias-veiculos dias.
Com --usuario, o simulador cadastra os 3 veículos ("SIMULADO") e uma cerca de teste na aba Frota e combustível, e grava na aba
Validação (planejado × gerado) os planejados SIMULADOS dos medidores de energia (84) e de água (85): o consumo do próprio modelo
do simulador sem as anomalias, para que as anomalias e os dias sem leitura apareçam como desvio com causa.
Ciclo diário (sol, temperatura, umidade, consumo) e anomalias de propósito: sensor travado, salto de temperatura,
bateria descarregando, fator de potência baixo, dia de desperdício de energia, vazamento de madrugada, pH fora da faixa,
nível do caminhão caindo parado de madrugada (vazamento ou furto, um dia por semana) e o carro saindo da cerca (um dia por semana).

Uso:
  python ferramentas/simulador_dispositivos.py --hub http://localhost:8802 --uma-vez --dias 21
  python ferramentas/simulador_dispositivos.py --hub http://localhost:8802 --intervalo 30
  python ferramentas/simulador_dispositivos.py --hub http://localhost:8802 --uma-vez --usuario ana --senha-arquivo ~/senha.txt
  python ferramentas/simulador_dispositivos.py --limpar --banco <pasta-do-pacote>/physis-hub.db   (com o hub DESLIGADO)

Só aceita hub em localhost/127.0.0.1/[::1]; outro endereço só com --permitir-remoto. A senha vem de um arquivo
(--senha-arquivo) ou é pedida no terminal; nunca fica no código nem aparece na tela. Só biblioteca padrão do Python.
Guia: physis-hub/docs/TESTE_COM_SIMULADOR.md.
"""
from __future__ import annotations

import argparse
import getpass
import ipaddress
import json
import math
import random
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

FUSO = timezone(timedelta(hours=-3))           # Brasília, como o hub
MARCA = "SIMULADO/teste"                       # valor da chave extra SIM em toda linha
CAMPO_MARCA = f"SIM:{MARCA}"
ROTULO = "SIMULADO / teste"                    # nome dos aparelhos (rótulo da chave) e das leituras de água
LINHA_MAX = 240                                # protocolo.LINHA_MAX
LOTE_LINHAS = 200                              # linhas por POST (o hub aceita corpo de até 64 kB)
APARELHOS = (  # (n, TIPO, nome)
    (1, "SOLO", "Talhão A (solo e clima)"),
    (2, "SOLO", "Talhão B (solo e clima)"),
    (3, "PLUV", "Pluviômetro"),
    (4, "ENE", "Medidor de energia"),
    (5, "HID", "Medidor de água"),
    (6, "SEC", "Secador solar"),
    (7, "VEI", "Caminhão SIMULADO"),
    (8, "VEI", "Carro SIMULADO"),
    (9, "VEI", "Trator SIMULADO"),
)
# veículos (frota): n -> (placa, tipo, combustível, tanque L, consumo esperado, unidade); todos marcados SIMULADO
VEICULOS = {7: ("SIM-1A01", "caminhao", "diesel_b", 300.0, 35.0, "l_100km"), 8: ("SIM-2B02", "carro", "gasolina_c", 50.0, 10.0, "l_100km"),
            9: ("SIM-3C03", "trator", "diesel_b", 120.0, 8.0, "l_h")}
PONTO_EXEMPLO = (-22.5051, -43.1784)            # o mesmo ponto de exemplo da tela (physis-frota.js), só sem o local da instalação
CERCA_KM = ((-4, -4), (-4, 5), (4, 5), (4, -4))  # cerca de teste: (km ao norte, km a leste) em volta do local
PASSO_VEI_S = 120
NOMES_VEI = {n: nome for n, tipo, nome in APARELHOS if tipo == "VEI"}
LIMITE_SOLO = 30.0
MM_POR_PULSO = 0.2794


# ── Guarda: só hub local ─────────────────────────────────────────────────────────────────────────
def hub_local(url: str) -> tuple[bool, str]:
    """(é local?, motivo). Local = http(s) em localhost, 127.0.0.0/8 ou ::1, sem usuário/senha no endereço."""
    try:
        u = urllib.parse.urlsplit(url)
        host = u.hostname or ""
        _ = u.port                                  # porta inválida levanta ValueError
    except ValueError:
        return False, "endereço inválido"
    if u.scheme not in ("http", "https"):
        return False, "use http:// ou https://"
    if u.username or u.password or "@" in u.netloc:
        return False, "endereço com usuário/senha não é aceito"
    if not host:
        return False, "endereço sem servidor"
    if host == "localhost":
        return True, ""
    try:
        if ipaddress.ip_address(host).is_loopback:
            return True, ""
    except ValueError:
        pass
    return False, f"{host} não é este computador (localhost/127.0.0.1)"


def conferir_hub(url: str, permitir_remoto: bool) -> str:
    """Devolve a URL base limpa ou levanta SystemExit com a explicação."""
    ok, motivo = hub_local(url)
    if not ok:
        if not permitir_remoto or motivo in ("endereço inválido", "use http:// ou https://",
                                              "endereço com usuário/senha não é aceito", "endereço sem servidor"):
            raise SystemExit(f"Recusado: {motivo}. O simulador é só para teste no próprio computador; "
                             "para um hub de teste em outra máquina, use --permitir-remoto (NUNCA no cliente real).")
        print(f"ATENÇÃO: hub remoto ({motivo}). Confirme que é uma instalação de TESTE.", file=sys.stderr)
    return url.rstrip("/")


# ── O mundo simulado ──────────────────────────────────────────────────────────────────────────────
def _rng(semente, *partes) -> random.Random:
    return random.Random(":".join(str(p) for p in (semente,) + partes))   # semente texto: igual em todo computador


def _f(v, casas=2) -> str:
    return "-" if v is None else f"{v:.{casas}f}"


def formatar(campos: list[tuple[str, str]]) -> str:
    """Linha V6: pares CHAVE:VALOR com vírgula, ponto decimal, a marca de simulado no fim."""
    linha = ",".join(f"{k}:{v}" for k, v in campos) + "," + CAMPO_MARCA
    if len(linha) > LINHA_MAX:
        raise ValueError(f"linha com {len(linha)} caracteres (máximo {LINHA_MAX})")
    return linha


class Mundo:
    """Estado dos aparelhos simulados. `linhas(t, passo_s)` avança o mundo de t - passo_s até t e devolve uma linha
    por aparelho. Determinístico pela semente (o mesmo período gera as mesmas linhas)."""

    def __init__(self, inicio: float, semente: str = "physis", id_base: int = 80, anomalias: float = 1.0,
                 centro: tuple[float, float] | None = None, veiculos_desde: float | None = None):
        if not 0 <= id_base <= 99 - len(APARELHOS):
            raise ValueError("--id-base precisa deixar os IDs entre 1 e 99")
        self.inicio, self.semente, self.id_base, self.anomalias = inicio, semente, id_base, anomalias
        self.u = {1: [44.0, 47.0], 2: [39.0, 41.0]}          # umidade do solo de cada sensor (%)
        self.irriga_ate = {1: 0.0, 2: 0.0}
        self.ultima_irrigacao = {1: -1e18, 2: -1e18}
        self.chuva_total = 0.0                               # mm desde que o pluviômetro "ligou" (para PUL)
        self.peso = 120.0                                    # kg no secador
        self.lote_inicio = inicio
        self.travado: dict[int, float] = {}
        self.centro = centro or PONTO_EXEMPLO
        self.veiculos_desde = inicio if veiculos_desde is None else veiculos_desde
        self.vei = {n: {"niv": 80.0 - 5 * (n - 7), "odo": 84200.0 if n == 7 else 31200.0 if n == 8 else None,
                        "hor": 1520.0 if n == 9 else None, "pos": None, "t": None} for n in VEICULOS}

    def ident(self, n: int) -> int:
        return self.id_base + n

    # tempo e clima
    @staticmethod
    def hora(t: float) -> float:
        d = datetime.fromtimestamp(t, FUSO)
        return d.hour + d.minute / 60 + d.second / 3600

    @staticmethod
    def dia(t: float) -> str:
        return datetime.fromtimestamp(t, FUSO).strftime("%Y-%m-%d")

    def n_dia(self, t: float) -> int:
        """Número do dia do calendário (Brasília); as anomalias de um dia inteiro valem da 0 h às 24 h."""
        return datetime.fromtimestamp(t, FUSO).toordinal()

    def chuva_do_dia(self, t: float) -> tuple[float, float, float]:
        """(início h, fim h, mm/h) da chuva do dia, ou (0, 0, 0). Cerca de 3 dias em 10 chovem, à tarde."""
        r = _rng(self.semente, "chuva", self.dia(t))
        if r.random() >= 0.3:
            return 0.0, 0.0, 0.0
        ini, dur, total = 13 + r.random() * 4, 1 + r.random() * 2, 4 + r.random() * 30
        return ini, ini + dur, total / dur

    def chuva_mm(self, t0: float, t1: float) -> float:
        """mm de chuva entre t0 e t1 (pode atravessar a meia-noite)."""
        mm, t = 0.0, t0
        while t < t1:
            d = datetime.fromtimestamp(t, FUSO)
            meia_noite = datetime(d.year, d.month, d.day, tzinfo=FUSO).timestamp()
            fim = min(t1, meia_noite + 86400)
            ini_h, fim_h, taxa = self.chuva_do_dia(t)
            if taxa:
                a, b = max(t, meia_noite + ini_h * 3600), min(fim, meia_noite + fim_h * 3600)
                if b > a:
                    mm += taxa * (b - a) / 3600
            t = fim
        return mm

    def sol(self, t: float) -> float:
        """0 a 1: altura do sol (6 h a 18 h), menor em dia de chuva."""
        h = self.hora(t)
        s = max(0.0, math.sin(math.pi * (h - 6) / 12)) if 6 <= h <= 18 else 0.0
        return s * (0.55 if self.chuva_do_dia(t)[2] else 1.0)

    def ar(self, t: float) -> tuple[float, float]:
        """(temperatura °C, umidade %) com atraso de ~2 h em relação ao sol."""
        lag = self.sol(t - 2 * 3600)
        r = _rng(self.semente, "ar", int(t // 60))
        temp = 17.0 + 12.0 * lag + r.gauss(0, 0.4)
        umid = min(98.0, max(25.0, 90.0 - 45.0 * lag + r.gauss(0, 1.5) + (8 if self.chuva_mm(t - 3600, t) else 0)))
        return temp, umid

    def _evento(self, t: float, nome: str, prob_por_hora: float, passo_s: float) -> bool:
        p = prob_por_hora * self.anomalias * passo_s / 3600
        return _rng(self.semente, "anom", nome, int(t)).random() < p

    # aparelhos
    def _solo(self, n: int, t: float, passo_s: float, chuva: float) -> list[tuple[str, str]]:
        dt = passo_s / 3600
        sol = self.sol(t)
        perda = (0.25 + 0.7 * sol) * dt                       # evapotranspiração (%/h × h)
        u = self.u[n]
        media = sum(u) / 2
        if media < LIMITE_SOLO and t - self.ultima_irrigacao[n] >= 2 * 3600 and not chuva:
            self.ultima_irrigacao[n], self.irriga_ate[n] = t, t + 15 * 60     # regra do nó: até 15 min, 2 h de espera
        irr = t <= self.irriga_ate[n]
        for i in range(2):
            u[i] += -perda * (1.0 + 0.1 * i) + 0.9 * chuva + (28.0 * dt if irr else 0.0)
            u[i] = min(95.0, max(5.0, u[i] + _rng(self.semente, "u", n, i, int(t)).gauss(0, 0.15)))
        u_mostra = list(u)
        # anomalia: sensor B do talhão B trava um dia por semana (mesmo valor o dia todo)
        if n == 2 and self.n_dia(t) % 7 == 3 and self.anomalias:
            self.travado.setdefault(self.n_dia(t), round(u[1], 1))
            u_mostra[1] = self.travado[self.n_dia(t)]
        temp, umid = self.ar(t)
        if n == 1 and self._evento(t, "salto", 0.01, passo_s):
            temp = 58.0                                       # anomalia: salto impossível de temperatura
        taxa = 0.25 + 0.7 * sol
        media = sum(u_mostra) / 2
        p1 = 0.0 if media <= LIMITE_SOLO else min(43200.0, (media - LIMITE_SOLO) / taxa * 60)
        if n == 1:   # bateria descarregando devagar (fica baixa perto do fim de 21 dias)
            bat = max(3.30, 4.05 - 0.028 * max(0.0, (t - self.inicio) / 86400)) + 0.03 * self.sol(t)
        else:
            bat = 3.95 + 0.1 * self.sol(t)
        return [("ID", f"{self.ident(n):02d}"), ("TIPO", "SOLO"), ("U1", _f(u_mostra[0], 1)), ("IR1", "1" if irr else "0"),
                ("U2", _f(u_mostra[1], 1)), ("IR2", "0"), ("T", _f(temp, 1)), ("UAR", _f(umid, 1)),
                ("TSOLO", _f(19.0 + 5.0 * self.sol(t - 3 * 3600), 1)), ("P1", _f(p1, 1)), ("P2", "-1"),
                ("LIM1", _f(LIMITE_SOLO, 1)), ("LIM2", _f(LIMITE_SOLO, 1)), ("BAT", _f(bat, 2))]

    def _pluv(self, t: float, chuva: float) -> list[tuple[str, str]]:
        self.chuva_total += chuva
        return [("ID", f"{self.ident(3):02d}"), ("TIPO", "PLUV"), ("CHI", _f(chuva, 2)),
                ("PUL", str(int(self.chuva_total / MM_POR_PULSO))), ("BAT", "-")]

    def _ene(self, t: float) -> list[tuple[str, str]]:
        h, nd = self.hora(t), self.n_dia(t)
        r = _rng(self.semente, "ene", int(t // 60))
        trabalho = 7 <= h < 17 and datetime.fromtimestamp(t, FUSO).weekday() < 6
        carga = (3.0 + (6.5 if trabalho else 0.0) + r.gauss(0, 0.3))
        if self.anomalias and nd % 9 == 4:
            carga *= 1.6                                      # anomalia: dia de desperdício
        gerado = 8.0 * self.sol(t)                            # placas solares atrás do medidor
        pw = carga - gerado                                   # negativo = injetando na rede
        fp_carga = 0.72 if (self.anomalias and nd % 5 == 2 and 9 <= h < 12) else 0.92
        qr = carga * math.tan(math.acos(fp_carga))            # reativo da carga (indutivo, +)
        s = math.hypot(pw, qr)
        v = 220.0 + r.gauss(0, 1.5)
        return [("ID", f"{self.ident(4):02d}"), ("TIPO", "ENE"), ("PW", _f(pw, 3)), ("QR", _f(qr, 3)), ("S", _f(s, 3)),
                ("V", _f(v, 1)), ("I", _f(s * 1000 / v, 2)), ("FP", _f(pw / s if s else 1.0, 3))]

    def _hid(self, t: float) -> list[tuple[str, str]]:
        h, nd = self.hora(t), self.n_dia(t)
        r = _rng(self.semente, "hid", int(t // 60))
        q = 0.15 if h < 6 or h >= 21 else 2.0 + 1.5 * math.sin(math.pi * (h - 6) / 15)
        irrigando = any(t <= self.irriga_ate[n] for n in (1, 2))
        q += (3.5 if irrigando else 0.0) + abs(r.gauss(0, 0.08))
        if self.anomalias and nd % 6 == 1 and 0 <= h < 5:
            q += 1.2                                          # anomalia: vazamento de madrugada
        return [("ID", f"{self.ident(5):02d}"), ("TIPO", "HID"), ("Q", _f(q, 3)), ("PR", _f(max(0.5, 3.0 - 0.18 * q), 2))]

    def _sec(self, t: float, passo_s: float) -> list[tuple[str, str]]:
        sol = self.sol(t)
        te, ue = self.ar(t)
        irr = 1000.0 * sol
        tc, ti = te + 0.035 * irr, te + 0.022 * irr
        ui = max(10.0, ue * (1.0 - 0.012 * (ti - te)))
        if t - self.lote_inicio > 5 * 86400:                  # lote novo a cada 5 dias
            self.peso, self.lote_inicio = 120.0, t
        self.peso = max(55.0, self.peso - 0.5 * sol * passo_s / 3600)
        return [("ID", f"{self.ident(6):02d}"), ("TIPO", "SEC"), ("TI", _f(ti, 1)), ("UI", _f(ui, 1)), ("TE", _f(te, 1)),
                ("UE", _f(ue, 1)), ("TC", _f(tc, 1)), ("VENT", "1" if ti > 38 else "0"), ("PESO", _f(self.peso, 2)),
                ("IRR", _f(irr, 0)), ("BAT", _f(3.9 + 0.15 * sol, 2))]

    # veículos (frota)
    def desloca(self, km_n: float, km_l: float) -> tuple[float, float]:
        lat0, lon0 = self.centro
        return lat0 + km_n / 110.574, lon0 + km_l / (111.32 * math.cos(math.radians(lat0)))

    @staticmethod
    def _ao_longo(wps, f: float):
        seg = [math.dist(wps[i - 1], wps[i]) for i in range(1, len(wps))]
        a = max(0.0, min(1.0, f)) * sum(seg)
        for i, d in enumerate(seg):
            if a <= d:
                k = a / d if d else 0.0
                return wps[i][0] + k * (wps[i + 1][0] - wps[i][0]), wps[i][1] + k * (wps[i + 1][1] - wps[i][1])
            a -= d
        return wps[-1]

    def _vei_estado(self, n: int, t: float) -> tuple[tuple[float, float], int]:
        """((km ao norte, km a leste), ignição) do veículo n no instante t."""
        h, nd = self.hora(t), self.n_dia(t)
        if n == 7:                 # caminhão: de hora em hora, 6 min até a cidade, carga com o motor desligado, 6 min de volta
            estrada = [(0, 0), (0.4, 1.2), (1.6, 2.2), (2.5, 3.0)]
            if 7 <= h < 17:
                m = (h - 7) * 60 % 60
                if m < 6:
                    return self._ao_longo(estrada, m / 6), 1
                if m < 30:
                    return estrada[-1], 0
                if m < 36:
                    return self._ao_longo(estrada, 1 - (m - 30) / 6), 1
            return (-0.03, 0.05), 0
        if n == 8:                 # carro: ida às 8 h, volta às 10 h 40; um dia por semana sai da cerca (7 km ao sul)
            fora = self.anomalias and nd % 7 == 2
            rota = [(0, 0), (-3.0, -1.5), (-7.0, -2.0)] if fora else [(0, 0), (-1.2, 1.5), (-2.6, 2.4)]
            dur = 0.2 if fora else 0.1
            if 8 <= h < 8 + dur:
                return self._ao_longo(rota, (h - 8) / dur), 1
            if 8 + dur <= h < 10.67:
                return rota[-1], 0
            if 10.67 <= h < 10.67 + dur:
                return self._ao_longo(rota, 1 - (h - 10.67) / dur), 1
            return (0.02, -0.04), 0
        if 7.5 <= h < 16:          # trator: linhas de 0,8 km a cerca de 6 km/h num talhão a oeste
            k = (h - 7.5) * 7.5
            i, fr = int(k), k - int(k)
            return (0.6 + (1 - fr if i % 2 else fr) * 0.8, -2.6 + 0.03 * (i % 30)), 1
        return (0.5, -2.5), 0

    def _vei(self, n: int, t: float) -> list[tuple[str, str]] | None:
        """Uma linha VEI do veículo n em t (None quando o veículo não manda nada neste instante)."""
        _, _, _, tanque, _, _ = VEICULOS[n]
        st = self.vei[n]
        (kn, kl), ign = self._vei_estado(n, t)
        lat, lon = self.desloca(kn, kl)
        ant = st["pos"] or (lat, lon)
        dt = max(1.0, t - st["t"]) if st["t"] is not None else float(PASSO_VEI_S)
        km = 2 * 6371.0088 * math.asin(math.sqrt(math.sin(math.radians(lat - ant[0]) / 2) ** 2 + math.cos(math.radians(ant[0]))
                                                  * math.cos(math.radians(lat)) * math.sin(math.radians(lon - ant[1]) / 2) ** 2))
        vel = km / (dt / 3600)
        anda = vel >= 1.0
        r = _rng(self.semente, "vei", n, int(t))
        if ign and anda:
            flx = 13 + 2 * r.random() if n == 7 else 4.5 + r.random() if n == 8 else 9 + 1.5 * r.random()
        else:
            flx = 2.2 if ign and n != 9 else 0.0
        st["niv"] -= flx * dt / 3600 / tanque * 100
        h, nd = self.hora(t), self.n_dia(t)
        vazando = bool(n == 7 and self.anomalias and nd % 7 == 5 and 2.0 <= h < 2.7)
        if vazando:
            st["niv"] -= 0.0042 * dt                          # ANOMALIA: o nível cai parado (cerca de 10 % em 40 min)
        if st["niv"] < 30 and ign and not vazando:
            st["niv"] = 95.0                                  # abastecido ao sair (o simulador não inventa abastecimento nem preço)
        if st["odo"] is not None:
            st["odo"] += km
        if st["hor"] is not None and ign:
            st["hor"] += dt / 3600
        st["pos"], st["t"] = (lat, lon), t
        if t < self.veiculos_desde or not (ign or vazando or (h * 60) % 30 < PASSO_VEI_S / 60):
            return None                                       # parado e desligado: uma linha a cada 30 min
        rumo = (math.degrees(math.atan2(lon - ant[1], lat - ant[0])) + 360) % 360 if anda else None
        c = [("ID", f"{self.ident(n):02d}"), ("TIPO", "VEI"), ("LAT", _f(lat, 6)), ("LON", _f(lon, 6)), ("VEL", _f(vel, 1)),
             ("RUMO", _f(rumo, 0)), ("FLX", _f(flx, 2)), ("NIV", _f(max(0.0, st["niv"]), 1))]
        if st["hor"] is not None:
            c.append(("HOR", _f(st["hor"], 2)))
        if st["odo"] is not None:
            c.append(("ODO", _f(st["odo"], 1)))
        return c + [("IGN", str(ign)), ("GPS", "1"), ("BAT", _f(3.95 + 0.1 * ign, 2))]

    def linhas_veiculos(self, t: float, passo_s: float) -> list[str]:
        """As linhas dos veículos no intervalo (t - passo_s, t], uma a cada PASSO_VEI_S (ou menos, se o passo for menor)."""
        out, sub = [], min(PASSO_VEI_S, passo_s)
        k = t - passo_s + sub
        while k <= t + 1e-6:
            for n in VEICULOS:
                c = self._vei(n, k)
                if c:
                    out.append(formatar(c + [("TS", str(int(k)))]))
            k += sub
        return out

    def linhas(self, t: float, passo_s: float) -> list[str]:
        """Uma linha por aparelho no instante t (TS = t), cobrindo o intervalo (t - passo_s, t]."""
        chuva = self.chuva_mm(t - passo_s, t)
        ts = ("TS", str(int(t)))
        out = []
        for campos in (self._solo(1, t, passo_s, chuva), self._solo(2, t, passo_s, chuva), self._pluv(t, chuva),
                       self._ene(t), self._hid(t), self._sec(t, passo_s)):
            out.append(formatar(campos + [ts]))
        return out + self.linhas_veiculos(t, passo_s)

    def agua(self, t: float) -> list[dict]:
        """Leituras de qualidade da água (antes e depois do filtro), marcadas como simuladas."""
        r = _rng(self.semente, "agua", int(t))
        q = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        ph_pos = 7.1 + r.gauss(0, 0.08)
        turb = abs(0.8 + r.gauss(0, 0.2))
        if self.anomalias and r.random() < 0.04:
            ph_pos, turb = 9.1, 6.5                           # anomalia: fora da faixa (alerta só com limite digitado)
        base = {"q": q, "t": round(self.ar(t)[0], 1), "valv": False, "origem": "simulador", "simulado": True, "obs": ROTULO}
        return [dict(base, ponto="pre", ph=round(6.8 + r.gauss(0, 0.05), 2), turb=round(turb * 3, 2), cloro=None),
                dict(base, ponto="pos", ph=round(ph_pos, 2), turb=round(turb, 2), cloro=round(max(0.0, 1.2 + r.gauss(0, 0.2)), 2))]


# ── Conversa com o hub ────────────────────────────────────────────────────────────────────────────
class _SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):        # um redirecionamento poderia levar a outro servidor: não segue
        return None


class Hub:
    def __init__(self, base: str, timeout: float = 30.0):
        self.base, self.timeout = base, timeout
        self.abrir = urllib.request.build_opener(_SemRedirecionar())
        self.csrf: str | None = None
        self.sessao: str | None = None           # cookie physis_sessao (guardado à mão: só vale para este hub)
        self.chaves: dict[int, str] = {}         # nó -> chave (só na memória, nunca impressa)

    def pedir(self, metodo: str, rota: str, corpo=None, tipo="application/json", chave: str | None = None):
        dados = None
        if corpo is not None:
            dados = (corpo if isinstance(corpo, str) else json.dumps(corpo, ensure_ascii=False)).encode("utf-8")
        h = {"Content-Type": tipo + "; charset=utf-8", "User-Agent": "physis-simulador-teste"}
        if self.csrf:
            h["X-Physis-CSRF"] = self.csrf
        if chave:
            h["Authorization"] = "Bearer " + chave
        if self.sessao:
            h["Cookie"] = "physis_sessao=" + self.sessao
        req = urllib.request.Request(self.base + rota, data=dados, method=metodo, headers=h)
        try:
            with self.abrir.open(req, timeout=self.timeout) as r:
                for ck in r.headers.get_all("Set-Cookie") or []:
                    nome, _, resto = ck.partition("=")
                    if nome.strip() == "physis_sessao":
                        self.sessao = resto.split(";", 1)[0] or None
                return r.status, json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode("utf-8") or "{}")
            except ValueError:
                return e.code, {}

    def entrar(self, usuario: str, senha: str) -> None:
        st, r = self.pedir("POST", "/api/conta/entrar", {"usuario": usuario, "senha": senha})
        if st == 200 and r.get("precisa_2fa"):
            codigo = getpass.getpass("Código de 2 fatores: ")
            st, r = self.pedir("POST", "/api/conta/entrar", {"usuario": usuario, "senha": senha, "codigo": codigo})
        if st != 200 or not r.get("ok"):
            raise SystemExit(f"Não entrou no hub (HTTP {st}): {r.get('erro', 'usuário ou senha')}")
        self.csrf = r.get("csrf")

    def preparar_chaves(self, mundo: Mundo) -> None:
        """Revoga as chaves simuladas antigas e cria uma por aparelho, com rótulo SIMULADO / teste (precisa da direção)."""
        st, r = self.pedir("GET", "/api/dispositivos/chaves")
        if st != 200:
            raise SystemExit(f"Sem acesso às chaves dos dispositivos (HTTP {st}): precisa de conta da direção.")
        lista = r.get("chaves") if isinstance(r, dict) else r
        for c in lista or []:
            if isinstance(c, dict) and c.get("ativa") and str(c.get("rotulo", "")).startswith(ROTULO):
                self.pedir("POST", f"/api/dispositivos/chaves/{int(c['id'])}/revogar", {})
        for n, tipo, nome in APARELHOS:
            no = mundo.ident(n)
            st, r = self.pedir("POST", "/api/dispositivos/chaves", {"no": no, "rotulo": f"{ROTULO} · {nome} ({tipo})"})
            if st != 200 or not r.get("chave"):
                raise SystemExit(f"Não criou a chave do nó {no} (HTTP {st}): {r.get('erro', '')}")
            self.chaves[no] = r["chave"]

    def enviar(self, linhas: list[str]) -> dict:
        """Manda as linhas em lotes (por nó, quando há chave por aparelho). Soma aceitas/duplicadas/descartadas."""
        total = {"aceitas": 0, "duplicadas": 0, "descartadas": 0}
        grupos: dict[int | None, list[str]] = {}
        for l in linhas:
            no = int(l.split(",", 1)[0].split(":", 1)[1]) if self.chaves else None
            grupos.setdefault(no, []).append(l)
        for no, ls in grupos.items():
            for i in range(0, len(ls), LOTE_LINHAS):
                for tentativa in range(5):
                    st, r = self.pedir("POST", "/api/v6/linha", "\n".join(ls[i:i + LOTE_LINHAS]), "text/plain",
                                       self.chaves.get(no) if no is not None else None)
                    if st == 429:
                        time.sleep(float(r.get("espera", 2)))
                        continue
                    break
                if st == 401:
                    raise SystemExit("O hub recusou linha sem chave (PHYSIS_ACEITAR_SEM_CHAVE=0 ou fora da rede local). "
                                     "Rode com --usuario (conta da direção) para o simulador criar as chaves.")
                if st != 200:
                    raise SystemExit(f"O hub respondeu HTTP {st}: {r.get('erro', '')}")
                for k in total:
                    total[k] += int(r.get(k, 0))
        return total

    def local(self) -> tuple[float, float] | None:
        """O local da instalação pelo hub (GET /api/clima → lugar), ou None."""
        st, r = self.pedir("GET", "/api/clima")
        lugar = ((r or {}).get("lugar") or {}) if st == 200 else {}
        try:
            return (float(lugar["lat"]), float(lugar["lon"])) if lugar.get("lat") is not None else None
        except (TypeError, ValueError, KeyError):
            return None

    def preparar_frota(self, mundo: Mundo) -> int:
        """Cadastra os veículos SIMULADOS (ligados aos nós 87 a 89) e a cerca de teste na aba Frota e combustível."""
        st, r = self.pedir("GET", "/api/frota/estado")
        if st != 200:
            print(f"  frota: sem acesso (HTTP {st}); os pontos ficam como nós sem veículo.", file=sys.stderr)
            return 0
        placas = {v.get("placa") for v in r.get("veiculos") or []}
        feitos = 0
        for n, (placa, tipo, comb, tanque, cons, un) in VEICULOS.items():
            if placa in placas:
                continue
            st, _ = self.pedir("POST", "/api/frota/veiculo", {"tipo": tipo, "placa": placa, "nome": NOMES_VEI[n], "combustivel": comb,
                                                            "tanque_l": tanque, "consumo_esperado": cons, "consumo_unidade": un,
                                                            "no": mundo.ident(n)})
            feitos += st == 200
        if not any(ROTULO in str(c.get("nome", "")) for c in r.get("cercas") or []):
            self.pedir("POST", "/api/frota/cerca", {"nome": f"Cerca de teste ({ROTULO})", "poligono": [list(mundo.desloca(a, b)) for a, b in CERCA_KM]})
        return feitos

    def preparar_validacao(self, mundo: Mundo) -> int:
        """Grava na aba Validação os planejados SIMULADOS do medidor de energia (nó 84) e do de água (nó 85): o consumo
        do próprio modelo do simulador, sem as anomalias, mês a mês. As anomalias e os dias sem leitura viram desvio."""
        st, r = self.pedir("GET", "/api/instancia")
        lugar = (r or {}).get("lugar") if st == 200 else None
        if not lugar:
            print(f"  validação: sem o lugar da instalação (HTTP {st}); pulei os planejados.", file=sys.stderr)
            return 0
        feitos = 0
        for p in planos_validacao(mundo, lugar):
            st, _ = self.pedir("POST", "/api/validacao/plano", p)
            feitos += st == 200
        return feitos

    def gravar_agua(self, novas: list[dict], manter: int = 2000) -> bool:
        """Junta as leituras simuladas às da aba Água (as de verdade ficam), com controle de versão."""
        for _ in range(3):
            st, r = self.pedir("GET", "/api/cliente/estado/physis-ph-leituras")
            if st not in (200, 404):
                print(f"  água: sem acesso (HTTP {st}); pulei a qualidade da água.", file=sys.stderr)
                return False
            versao = int(r.get("versao") or 0)
            try:
                atuais = json.loads(r.get("valor") or "[]")
            except ValueError:
                atuais = []
            reais = [x for x in atuais if not (isinstance(x, dict) and x.get("simulado"))]
            sim = [x for x in atuais if isinstance(x, dict) and x.get("simulado")]
            vistos = {(x.get("q"), x.get("ponto")) for x in sim}
            sim += [x for x in novas if (x["q"], x["ponto"]) not in vistos]
            lista = sorted(reais + sorted(sim, key=lambda x: x["q"])[-manter:], key=lambda x: str(x.get("q")))
            st, r = self.pedir("PUT", "/api/cliente/estado/physis-ph-leituras",
                               {"valor": json.dumps(lista, ensure_ascii=False), "versao": versao})
            if st == 200:
                return True
            if st != 409:
                print(f"  água: o hub recusou (HTTP {st}): {r.get('erro', '')}", file=sys.stderr)
                return False
        return False


# ── Limpar (com o hub desligado) ─────────────────────────────────────────────────────────────────
def planos_validacao(mundo: Mundo, lugar: str, ano: int | None = None) -> list[dict]:
    """Planejados SIMULADOS (aba Validação): por mês do ano, a média de 7 dias do modelo do simulador SEM anomalias,
    × 24 h × dias do mês (energia: kWh líquidos do medidor 84; água: m³ do medidor 85). Só para teste."""
    limpo = Mundo(mundo.inicio, mundo.semente, mundo.id_base, 0.0, centro=mundo.centro)
    ano = ano or datetime.fromtimestamp(mundo.inicio, FUSO).year
    ene, agua = {}, {}
    for m in range(1, 13):
        t0 = datetime(ano, m, 10, tzinfo=FUSO).timestamp()
        pws, qs = [], []
        for k in range(7 * 24 * 4):                           # 7 dias, de 15 em 15 min
            t = t0 + k * 900
            pws.append(float(dict(limpo._ene(t))["PW"]))
            qs.append(float(dict(limpo._hid(t))["Q"]))
        dias = (datetime(ano + (m == 12), m % 12 + 1, 1) - datetime(ano, m, 1)).days
        ene[f"{m:02d}"] = round(max(0.0, sum(pws) / len(pws)) * 24 * dias, 1)
        agua[f"{m:02d}"] = round(sum(qs) / len(qs) * 24 * dias, 2)
    fonte = f"{ROTULO}: consumo do modelo do simulador, sem as anomalias"
    return [{"modulo": "energia", "item": "simulado-energia", "nome": f"Medidor de energia ({ROTULO})", "ativo": f"{lugar}-no{mundo.ident(4):02d}",
             "grandeza": "energia", "fonte": fonte, "meses": ene},
            {"modulo": "agua", "item": "simulado-agua", "nome": f"Medidor de água ({ROTULO})", "ativo": f"{lugar}-no{mundo.ident(5):02d}",
             "grandeza": "vazao", "fonte": fonte, "meses": agua}]


def limpar(banco: Path) -> dict:
    """Apaga do banco as leituras simuladas (linha com SIM:SIMULADO/teste) e as medições delas, revoga as chaves
    "SIMULADO / teste", tira as leituras de água simuladas, refaz a chuva observada do pluviômetro e apaga os modelos
    aprendidos (o hub treina de novo ao ligar). O registro encadeado e os lotes de integridade não são apagados
    (são à prova de alteração de propósito): os eventos dos nós simulados continuam lá."""
    if not banco.is_file():
        raise SystemExit(f"Banco não encontrado: {banco}")
    db = sqlite3.connect(str(banco))
    try:
        tabelas = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        out = {"leituras": 0, "medicoes": 0, "chaves": 0, "agua": 0, "modelos": 0, "frota": 0}
        padrao = f"%{CAMPO_MARCA}%"
        if "leitura" in tabelas:
            seqs = [r[0] for r in db.execute("SELECT seq FROM leitura WHERE linha LIKE ?", (padrao,))]
            for i in range(0, len(seqs), 500):
                parte = seqs[i:i + 500]
                marcas = ",".join("?" * len(parte))
                if "medicao" in tabelas:
                    out["medicoes"] += db.execute(f"DELETE FROM medicao WHERE leitura IN ({marcas})", parte).rowcount
                out["leituras"] += db.execute(f"DELETE FROM leitura WHERE seq IN ({marcas})", parte).rowcount
        if "dispositivo_chave" in tabelas:
            out["chaves"] = db.execute("UPDATE dispositivo_chave SET revogado=? WHERE revogado IS NULL AND rotulo LIKE ?",
                                       (time.time(), ROTULO + "%")).rowcount
        if "cliente_estado" in tabelas:
            for org, valor, versao in db.execute("SELECT org, valor, versao FROM cliente_estado WHERE chave='physis-ph-leituras'").fetchall():
                try:
                    lista = json.loads(valor)
                except ValueError:
                    continue
                if not isinstance(lista, list):
                    continue
                reais = [x for x in lista if not (isinstance(x, dict) and x.get("simulado"))]
                if len(reais) != len(lista):
                    out["agua"] += len(lista) - len(reais)
                    db.execute("UPDATE cliente_estado SET valor=?, versao=?, atualizado=?, por=? WHERE org=? AND chave='physis-ph-leituras'",
                               (json.dumps(reais, ensure_ascii=False), versao + 1, time.time(), "simulador --limpar", org))
        if "clima_observado" in tabelas and "medicao" in tabelas and "leitura" in tabelas:
            # a chuva do pluviômetro (origem "physis") é refeita só com as leituras que ficaram
            db.execute("DELETE FROM clima_observado WHERE origem='physis'")
            por_dia: dict[str, dict[str, float]] = {}
            for ativo, quando, mm in db.execute("SELECT m.ativo, CASE WHEN m.ts > 0 THEN m.ts ELSE l.recebido END, m.valor "
                                                "FROM medicao m JOIN leitura l ON l.seq = m.leitura WHERE m.grandeza='chuva'"):
                dia = datetime.fromtimestamp(quando, FUSO).strftime("%Y-%m-%d")
                por_dia.setdefault(dia, {}).setdefault(ativo, 0.0)
                por_dia[dia][ativo] += mm
            for dia, ativos in por_dia.items():
                db.execute("INSERT OR REPLACE INTO clima_observado(dia,origem,mm,atualizado) VALUES(?,?,?,?)",
                           (dia, "physis", round(sum(ativos.values()) / len(ativos), 2), time.time()))
        if "frota_ponto" in tabelas:                    # pontos dos veículos simulados (linhas V6 marcadas)
            out["frota"] = db.execute("DELETE FROM frota_ponto WHERE origem='v6-simulado'").rowcount
        if "validacao_plano" in tabelas:                # planejados SIMULADOS da aba Validação
            out["validacao"] = db.execute("DELETE FROM validacao_plano WHERE fonte LIKE ?", (ROTULO + "%",)).rowcount
        if "modelo" in tabelas and out["leituras"]:
            out["modelos"] = db.execute("DELETE FROM modelo").rowcount
        db.commit()
        return out
    finally:
        db.close()


def _hub_no_ar(url: str) -> bool:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/", timeout=2):
            return True
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


# ── Programa ─────────────────────────────────────────────────────────────────────────────────────
def ler_senha(arquivo: str | None) -> str:
    if arquivo:
        try:
            return Path(arquivo).expanduser().read_text(encoding="utf-8").strip("\r\n")
        except OSError as exc:
            raise SystemExit(f"Não li o arquivo da senha: {exc.strerror or exc}") from None
    return getpass.getpass("Senha (não aparece na tela): ")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Simulador de dispositivos Physis — SÓ PARA TESTE (nunca no cliente real).")
    ap.add_argument("--hub", help="endereço do hub de teste, ex.: http://localhost:8802")
    ap.add_argument("--uma-vez", action="store_true", help="manda o histórico de --dias dias de uma vez e termina")
    ap.add_argument("--dias", type=float, default=21.0, help="dias de histórico no --uma-vez (padrão 21: o consumo aprende com 14)")
    ap.add_argument("--passo-min", type=float, default=15.0, help="minutos entre leituras no histórico (padrão 15)")
    ap.add_argument("--intervalo", type=float, default=30.0, help="segundos entre leituras no modo contínuo (padrão 30)")
    ap.add_argument("--id-base", type=int, default=80, help="IDs dos nós = base + 1..9 (padrão 81 a 89)")
    ap.add_argument("--dias-veiculos", type=float, default=7.0, help="dias de GPS dos veículos no --uma-vez (padrão 7)")
    ap.add_argument("--lat", type=float, help="latitude do centro das rotas (sem ela: o local do hub, ou um ponto de exemplo)")
    ap.add_argument("--lon", type=float, help="longitude do centro das rotas")
    ap.add_argument("--semente", default="physis", help="mesma semente, mesmos dados")
    ap.add_argument("--sem-anomalias", action="store_true", help="dados só normais")
    ap.add_argument("--usuario", help="conta da direção: cria chaves por aparelho, grava a água e treina os modelos")
    ap.add_argument("--senha-arquivo", help="arquivo local com a senha (sem ele, a senha é pedida no terminal)")
    ap.add_argument("--permitir-remoto", action="store_true", help="aceita hub fora deste computador (só hub de TESTE)")
    ap.add_argument("--limpar", action="store_true", help="apaga os dados simulados do banco (hub desligado)")
    ap.add_argument("--banco", help="arquivo do banco do pacote (para --limpar), ex.: physis-hub.db")
    a = ap.parse_args(argv)

    if a.limpar:
        if not a.banco:
            raise SystemExit("--limpar precisa de --banco <arquivo .db do pacote>.")
        if a.hub and _hub_no_ar(conferir_hub(a.hub, a.permitir_remoto)):
            raise SystemExit("O hub ainda está ligado. Desligue (Ctrl+C na janela dele) e rode o --limpar de novo.")
        r = limpar(Path(a.banco).expanduser())
        print(f"Limpo: {r['leituras']} leituras e {r['medicoes']} medições simuladas, {r['chaves']} chaves revogadas, "
              f"{r['agua']} leituras de água simuladas, {r['frota']} pontos de GPS simulados, {r['modelos']} modelos "
              "(o hub treina de novo ao ligar). Os veículos e a cerca SIMULADO saem na aba Frota (Veículos, Apagar).")
        return 0
    if not a.hub:
        ap.error("informe --hub (ex.: http://localhost:8802) ou --limpar")
    base = conferir_hub(a.hub, a.permitir_remoto)
    print(f"SIMULADOR (SÓ TESTE) → {base}. Aparelhos: "
          + ", ".join(f"{a.id_base + n:02d} {tipo} {nome}" for n, tipo, nome in APARELHOS))
    hub = Hub(base)
    logado = False
    centro = (a.lat, a.lon) if a.lat is not None and a.lon is not None else None
    if a.usuario:
        hub.entrar(a.usuario, ler_senha(a.senha_arquivo))
        logado = True
        hub.preparar_chaves(Mundo(time.time(), a.semente, a.id_base))
        print(f"Chaves criadas para {len(hub.chaves)} aparelhos (rótulo \"{ROTULO}\"; as chaves não são mostradas).")
    centro = centro or hub.local()
    if not centro:
        print(f"Sem local da instalação: os veículos andam em volta do ponto de exemplo {PONTO_EXEMPLO} (use --lat e --lon).")
    if logado:
        print(f"Frota: {hub.preparar_frota(Mundo(time.time(), a.semente, a.id_base, centro=centro))} veículos SIMULADOS cadastrados.")
        print(f"Validação: {hub.preparar_validacao(Mundo(time.time(), a.semente, a.id_base, centro=centro))} planejados SIMULADOS gravados.")
    else:
        print("Sem --usuario: linhas sem chave (o hub aceita só da rede local); qualidade da água fica de fora.")

    agora = time.time()
    if a.uma_vez:
        passo = max(60.0, a.passo_min * 60)
        mundo = Mundo(agora - a.dias * 86400, a.semente, a.id_base, 0.0 if a.sem_anomalias else 1.0, centro=centro,
                      veiculos_desde=agora - a.dias_veiculos * 86400)
        linhas, agua, t = [], [], mundo.inicio + passo
        while t <= agora:
            linhas += mundo.linhas(t, passo)
            if int(t // 3600) != int((t - passo) // 3600) and int(t // 3600) % 3 == 0:
                agua += mundo.agua(t)
            t += passo
        r = hub.enviar(linhas)
        print(f"Histórico de {a.dias:g} dias: {len(linhas)} linhas → aceitas {r['aceitas']}, duplicadas {r['duplicadas']}, "
              f"descartadas {r['descartadas']}.")
        if logado:
            if agua and hub.gravar_agua(agua):
                print(f"Água: {len(agua)} leituras simuladas na aba Água.")
            st, _ = hub.pedir("POST", "/api/aprendizado/treinar", {})
            print("Modelos treinados agora." if st == 200 else f"Treino não rodou (HTTP {st}); o hub treina às 3 h.")
        return 0

    mundo = Mundo(agora - a.dias * 86400, a.semente, a.id_base, 0.0 if a.sem_anomalias else 1.0, centro=centro)
    passo, anterior, ultima_agua = max(1.0, a.intervalo), agora - max(1.0, a.intervalo), 0.0
    print(f"Modo contínuo: uma leitura por aparelho a cada {passo:g} s. Ctrl+C para parar.")
    try:
        while True:
            t = time.time()
            r = hub.enviar(mundo.linhas(t, max(1.0, t - anterior)))
            anterior = t
            extra = ""
            if logado and t - ultima_agua >= 3600:
                if hub.gravar_agua(mundo.agua(t)):
                    extra = " · água gravada"
                ultima_agua = t
            print(f"{datetime.fromtimestamp(t, FUSO):%H:%M:%S} aceitas {r['aceitas']} descartadas {r['descartadas']}{extra}")
            time.sleep(passo)
    except KeyboardInterrupt:
        print("Parado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
