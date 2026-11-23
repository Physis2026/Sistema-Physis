#!/usr/bin/env python3
"""Teste de estresse do Physis Hub, sem hardware.

Sobe o hub numa porta local e o ataca pela mesma rota que o Receptor V6 usa.
Uso: python3 estresse.py [--ciclos 200] [--porta 8791]
Sai com codigo 0 se todos os cenarios passarem.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import tempfile
import threading
import time
import urllib.error
import urllib.request

from physis_hub import protocolo
from physis_hub.hub import Hub
from physis_hub.servidor import iniciar
from physis_hub.simulador import Simulador

RESULTADOS: list[dict] = []


def http(porta: int, metodo: str, rota: str, corpo: str | bytes | None = None, tipo="text/plain"):
    dados = corpo.encode() if isinstance(corpo, str) else corpo
    req = urllib.request.Request(f"http://127.0.0.1:{porta}{rota}", data=dados, method=metodo,
                                 headers={"Content-Type": tipo} if dados is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def cenario(nome: str, ok: bool, detalhe: str) -> None:
    RESULTADOS.append({"cenario": nome, "ok": bool(ok), "detalhe": detalhe})
    print(f"[{'OK ' if ok else 'FALHA'}] {nome}: {detalhe}")


def lotes(linhas: list[str], n: int = 8):
    for i in range(0, len(linhas), n):
        yield "\n".join(linhas[i:i + n]) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ciclos", type=int, default=200)
    ap.add_argument("--porta", type=int, default=8791)
    a = ap.parse_args()
    pasta = tempfile.mkdtemp(prefix="physis-estresse-")
    banco = os.path.join(pasta, "hub.db")
    hub = Hub(banco, org="org-teste", lugar="estresse")
    # o limitador por IP (seguranca.Limites) barraria o volume do teste; aqui o alvo é o hub, não o limitador
    os.environ.setdefault("PHYSIS_LIMITE_DISPOSITIVO", "1000000/60")
    srv = iniciar(hub, a.porta, endereco="127.0.0.1")
    rng = random.Random(11)

    # 1 ── Volume: 99 dispositivos, lotes de 8 como o receptor ────────────────
    sim = Simulador(solo=60, zona=9, col=24, com=6)
    enviadas, t0 = 0, time.perf_counter()
    for _ in range(a.ciclos):
        linhas = sim.passo(hub.comandos_pendentes())
        for lote in lotes(linhas):
            st, r = http(a.porta, "POST", "/api/gateway/webhook", lote)
            assert st == 200, r
        enviadas += len(linhas)
    dt = time.perf_counter() - t0
    c = hub.contagem
    cenario("volume", c["aceitas"] == enviadas and len(hub.nos) == 99,
            f"{enviadas} linhas de 99 dispositivos em {dt:.1f} s = {enviadas / dt:.0f} linhas/s "
            f"(o receptor gera cerca de 2 linhas/s com 99 nos)")

    # 2 ── Reentrega: o receptor repete o lote quando nao recebe o 200 ────────
    antes = c["aceitas"]
    linhas = sim.passo()
    for _ in range(3):
        for lote in lotes(linhas):
            http(a.porta, "POST", "/api/gateway/webhook", lote)
    cenario("reentrega", c["aceitas"] - antes == len(linhas) and c["duplicadas"] == 2 * len(linhas),
            f"lote enviado 3 vezes: {c['aceitas'] - antes} aceitas, {c['duplicadas']} duplicadas descartadas")

    # 3 ── Linhas defeituosas e linhas estranhas toleradas ────────────────────
    descartes_antes = dict(hub.descartes)
    esperado: dict[str, int] = {}
    corpo = ""
    for linha, motivo in sim.defeituosas():
        if motivo != "vazia":                 # linha vazia some no fatiamento do lote
            esperado[motivo] = esperado.get(motivo, 0) + 1
            corpo += linha + "\n"
    st, r = http(a.porta, "POST", "/api/gateway/webhook", corpo)
    obtido = {k: hub.descartes[k] - descartes_antes.get(k, 0) for k in esperado}
    antes = c["aceitas"]
    st2, r2 = http(a.porta, "POST", "/api/gateway/webhook", "\n".join(sim.toleradas()) + "\n")
    cenario("defeituosas", st == 200 and obtido == esperado and r["aceitas"] == 0,
            f"descartes por motivo: {obtido}")
    cenario("toleradas", st2 == 200 and c["aceitas"] - antes == len(sim.toleradas()) and r2["descartadas"] == 1,
            f"{c['aceitas'] - antes} linhas fora do comum aceitas; 1 pedaco sem ID descartado")

    # 4 ── Comandos: validos confirmados pelo no, invalidos recusados ─────────
    recusados = 0
    invalidos = ["CMD:03:LIM1:35,5", "CMD:03:LIM1:nan", "CMD:100:IRR1:1", "CMD:xx:IRR1:1", "CMD:03:IRR1:2",
                 "CMD:03:ABRIR:1", "CMD:03:SYNC:123", "{\"comando\":", "CMD:03:LIM1:" + "9" * 400, ""]
    for l in invalidos * 20:
        st, r = http(a.porta, "POST", "/api/comando", json.dumps({"comando": l}) if not l.startswith("{") else l,
                     "application/json")
        recusados += st == 400
    alvos = rng.sample(range(1, 61), 30)
    for no in alvos:
        http(a.porta, "POST", "/api/comando", json.dumps({"comando": f"CMD:{no:02d}:LIM1:{20 + no % 30}"}),
             "application/json")
    for _ in range(3):
        for lote in lotes(sim.passo(hub.comandos_pendentes())):
            http(a.porta, "POST", "/api/gateway/webhook", lote)
    estados = [x["estado"] for x in hub.painel()["comandos"]]
    conf = hub._db.execute("SELECT COUNT(*) FROM comando WHERE estado='confirmado'").fetchone()[0]
    cenario("comandos", recusados == len(invalidos) * 20 and conf == 30,
            f"{recusados} invalidos recusados; {conf} de 30 mudancas de limite confirmadas pelo no")

    # 5 ── Concorrencia: 8 remetentes e 4 leitores ao mesmo tempo ─────────────
    erros: list[str] = []
    antes = c["aceitas"]
    pacotes = [sim.passo() for _ in range(40)]
    total = sum(len(x) for x in pacotes)

    def remetente(parte):
        try:
            for linhas in parte:
                for lote in lotes(linhas):
                    st, _ = http(a.porta, "POST", "/api/gateway/webhook", lote)
                    if st != 200:
                        erros.append(f"status {st}")
        except Exception as exc:
            erros.append(repr(exc))

    def leitor():
        try:
            for _ in range(40):
                st, p = http(a.porta, "GET", "/api/painel")
                if st != 200 or len(p["nos"]) != 99:
                    erros.append("painel inconsistente")
        except Exception as exc:
            erros.append(repr(exc))

    fios = [threading.Thread(target=remetente, args=(pacotes[i::8],)) for i in range(8)]
    fios += [threading.Thread(target=leitor) for _ in range(4)]
    t0 = time.perf_counter()
    [f.start() for f in fios]
    [f.join() for f in fios]
    cenario("concorrencia", not erros and c["aceitas"] - antes == total,
            f"{total} linhas por 8 remetentes com 4 leitores em {time.perf_counter() - t0:.1f} s; erros: {len(erros)}")

    # 6 ── No que para de falar ───────────────────────────────────────────────
    hub.offline_s = 1
    for n in sim.nos[:5]:
        n.mudo = True
    time.sleep(1.3)
    for lote in lotes(sim.passo()):
        http(a.porta, "POST", "/api/gateway/webhook", lote)
    off = [x for x in hub.painel()["nos"] if not x["online"]]
    alarmes = [x for x in hub.alertas() if "sem falar" in x["texto"]]
    cenario("no_offline", len(off) == 5 and len(alarmes) == 5, f"{len(off)} nos offline, {len(alarmes)} alarmes")
    hub.offline_s = 160

    # 7 ── Entradas abusivas na API ───────────────────────────────────────────
    st_grande, _ = http(a.porta, "POST", "/api/gateway/webhook", "ID:01,U1:1.0\n" * 20000)
    st_rota, _ = http(a.porta, "GET", "/api/nao-existe")
    st_json, _ = http(a.porta, "POST", "/api/comando", "{quebrado", "application/json")
    st_vivo, _ = http(a.porta, "GET", "/api/painel")
    cenario("abuso", (st_grande, st_rota, st_json, st_vivo) == (413, 404, 400, 200),
            f"corpo de 260 kB -> {st_grande}; rota inexistente -> {st_rota}; JSON quebrado -> {st_json}; "
            f"hub segue respondendo -> {st_vivo}")

    # 8 ── Dispositivo Wi-Fi via ESP recebe o comando na resposta ─────────────
    http(a.porta, "POST", "/api/comando", json.dumps({"comando": "CMD:61:IRR2:1"}), "application/json")
    st, r = http(a.porta, "POST", "/api/v6/linha",
                 "ID:61,TIPO:ZONA,U1:40.0,IR1:0,U2:38.0,IR2:0,BOMBA:0,TMAX:15,LIM1:30.0,LIM2:30.0,TS:1794690000")
    cenario("esp_wifi", st == 200 and r.get("comandos") == ["CMD:61:IRR2:1"],
            f"resposta ao no 61 trouxe {r.get('comandos')}")

    # 9 ── Registro integro, e continua integro depois de reiniciar ───────────
    integra, n = hub.verificar_cadeia()
    fila = len(hub.fila_envio(100000))
    srv.shutdown()
    hub.fechar()
    hub2 = Hub(banco, org="org-teste", lugar="estresse")
    hub2.receber_lote("ID:01,U1:44.0,IR1:0,U2:44.0,IR2:0,LIM1:30.0,LIM2:30.0,TS:1794699999")
    hub2.comandar("CMD:01:PING")
    integra2, n2 = hub2.verificar_cadeia()
    hub2._db.execute("UPDATE registro SET conteudo='{}' WHERE seq=2")
    adulterada, _ = hub2.verificar_cadeia()
    hub2.fechar()
    cenario("registro", integra and integra2 and n2 > n and not adulterada and fila == n,
            f"{n} entradas integras; apos reinicio {n2}; adulteracao detectada: {not adulterada}; "
            f"{fila} na fila de envio ao servidor")

    falhas = [r for r in RESULTADOS if not r["ok"]]
    resumo = {"passaram": len(RESULTADOS) - len(falhas), "total": len(RESULTADOS),
              "linhas_recebidas": c["recebidas"], "aceitas": c["aceitas"], "duplicadas": c["duplicadas"],
              "descartes": dict(hub.descartes), "resultados": RESULTADOS}
    with open("relatorio_estresse.json", "w", encoding="utf-8") as f:
        json.dump(resumo, f, ensure_ascii=False, indent=2)
    print(f"\n{resumo['passaram']} de {resumo['total']} cenarios passaram. Relatorio em relatorio_estresse.json")
    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
