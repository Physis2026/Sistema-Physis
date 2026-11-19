"""Validação · planejado × gerado (M&V; em desenvolvimento; docs/VALIDACAO_MV.md): physis_hub/validacao.py e
sistema/physis-validacao.js.

Protege:
1. QUANTO: o desvio (absoluto e %) e a soma dos itens do módulo.
2. QUANDO: o primeiro mês fora do limite, a duração e os trechos.
3. POR QUÊ: cada regra (falha de dado, clima, consumo anormal, estação, premissa) e "causa não identificada".
4. Módulo sem plano diz "sem plano" (nada inventado), no puro e no estado do hub.
5. Linha de base por regressão (reta conhecida, r², CV(RMSE), avisos) e o IPMVP com ajuste rotineiro.
6. A equação do IPMVP é a MESMA da aba Certificações (mvEconomia chama VALIDACAO.ipmvp; Python dá o mesmo resultado).
7. O medido do hub (média do dia × 24 h, dias com leitura), o planejado gravado, o Carbono derivado e as rotas.
8. A aba está na Casa Physis (pesquisa, em desenvolvimento) e fora da loja pública; o espelho em JS tem as mesmas
   premissas, módulos e regras.
"""
import json
import math
import re
import sys
import unittest
from datetime import datetime
from pathlib import Path

from physis_hub import carbono, frota, validacao as va
from physis_hub.hub import Hub

RAIZ = Path(__file__).resolve().parents[2]
JS = RAIZ / "sistema" / "physis-validacao.js"
PAINEL = RAIZ / "physis-hub" / "web" / "painel.html"
PREMISSAS = RAIZ / "sistema" / "physis-premissas.json"
FUSO = va.FUSO
P = dict(va.PREMISSAS_PADRAO)


def linha(mes, p, m, dias=None, dm=30, cm=None, ce=None):
    d = va.desvio(p, m)
    return {"mes": mes, "planejado": p, "medido": m, "abs": d["abs"], "pct": d["pct"], "dias": dias, "dias_mes": dm,
            "cobertura_pct": None if dias is None else dias / dm * 100, "clima_medido": cm, "clima_esperado": ce}


INFO = {"sentido": "consumir", "sinal": 1, "clima": None, "plano_plano": False, "premissa": ""}


class Quanto(unittest.TestCase):
    def test_desvio(self):
        self.assertEqual(va.desvio(100.0, 85.0), {"abs": -15.0, "pct": -15.0})
        self.assertEqual(va.desvio(200.0, 230.0), {"abs": 30.0, "pct": 15.0})
        self.assertEqual(va.desvio(None, 10.0), {"abs": None, "pct": None})
        self.assertEqual(va.desvio(0.0, 10.0), {"abs": 10.0, "pct": None})       # sem % sobre planejado zero

    def test_plano_do_mes_e_meses(self):
        self.assertEqual(va.plano_do_mes({"03": 5.0}, "2026-03"), 5.0)            # ano típico (MM)
        self.assertEqual(va.plano_do_mes({"03": 5.0, "2026-03": 7.0}, "2026-03"), 7.0)   # o mês exato vale mais
        self.assertIsNone(va.plano_do_mes({"03": 5.0}, "2026-04"))
        self.assertEqual(va.meses_ate("2026-02", 3), ["2025-12", "2026-01", "2026-02"])
        self.assertEqual(va.dias_do_mes("2024-02"), 29)

    def test_comparar_e_soma_dos_itens(self):
        meses = ["2026-01", "2026-02"]
        a = va.comparar({"01": 100.0, "02": 100.0}, {"2026-01": {"valor": 90.0, "dias": 31, "dias_mes": 31},
                                                    "2026-02": {"valor": 120.0, "dias": 14, "dias_mes": 28}}, meses)
        self.assertAlmostEqual(a[0]["pct"], -10.0)
        self.assertAlmostEqual(a[1]["cobertura_pct"], 50.0)
        b = va.comparar({"01": 50.0, "02": 50.0}, {"2026-01": {"valor": 60.0, "dias": 31, "dias_mes": 31}}, meses)
        s = va.somar_itens([{"linhas": a}, {"linhas": b}], meses)
        self.assertEqual((s[0]["planejado"], s[0]["medido"]), (150.0, 150.0))
        self.assertEqual(s[1]["planejado"], 150.0)
        self.assertEqual(s[1]["medido"], 120.0)                                    # item sem medido fica fora da soma do medido
        self.assertEqual(s[1]["cobertura_pct"], 50.0)                              # o pior item do mês


class Quando(unittest.TestCase):
    def test_primeiro_mes_e_duracao(self):
        ls = [linha(f"2026-{i:02d}", 100, m) for i, m in enumerate([102, 95, 80, 85, 101, 70], start=1)]
        q = va.quando(ls, P)
        self.assertEqual(q["primeiro_mes"], "2026-03")
        self.assertEqual(q["duracao_meses"], 2)
        self.assertEqual(q["ultimo_mes"], "2026-04")
        self.assertTrue(q["continua"])                                             # junho ainda fora
        self.assertEqual([t["inicio"] for t in q["trechos"]], ["2026-03", "2026-06"])

    def test_dentro_do_limite_e_limite_exato(self):
        self.assertIsNone(va.quando([linha("2026-01", 100, 109), linha("2026-02", 100, 110)], P))   # 10 % não passa de 10 %
        self.assertIsNone(va.quando([linha("2026-01", None, 50)], P))


class PorQue(unittest.TestCase):
    def codigos(self, cs):
        return [c["codigo"] for c in cs]

    def test_falha_de_dado(self):
        l = linha("2026-06", 600, 180, dias=9, dm=30)
        cs = va.causas(l, [], dict(INFO, sentido="gerar"), P)
        self.assertEqual(cs[0]["codigo"], "falha_dado")
        self.assertEqual(cs[0]["evidencia"]["dias"], 9)
        self.assertGreaterEqual(cs[0]["confianca"], 0.7)
        self.assertEqual(va.causas(linha("2026-06", 600, 0, dias=0), [], INFO, P)[0]["confianca"], 0.95)   # nenhum dia com leitura

    def test_clima(self):
        info = dict(INFO, sentido="gerar", clima="irradiancia")
        cs = va.causas(linha("2026-03", 700, 530, dias=31, dm=31, cm=3.6, ce=5.0), [], info, P)    # −28 % de sol, −24 % de geração
        self.assertEqual(cs[0]["codigo"], "clima")
        self.assertAlmostEqual(cs[0]["evidencia"]["diferenca_pct"], -28.0)
        self.assertGreater(cs[0]["confianca"], 0.7)
        # clima no sentido contrário do desvio não explica
        self.assertNotIn("clima", self.codigos(va.causas(linha("2026-03", 700, 530, cm=6.0, ce=5.0), [], info, P)))
        # graus-dia: mais calor, mais consumo
        info2 = dict(INFO, clima="graus_dia")
        self.assertIn("clima", self.codigos(va.causas(linha("2025-12", 1000, 1150, cm=260, ce=185), [], info2, P)))

    def test_consumo_anormal_com_a_conta_da_frota(self):
        hist = [linha(f"2026-{i:02d}", 100, m) for i, m in enumerate([99, 101, 100, 98, 102, 100, 101, 99], start=1)]
        l = linha("2026-09", 100, 138)
        cs = va.causas(l, hist, INFO, P)
        self.assertEqual(cs[0]["codigo"], "consumo_anormal")
        a = frota.anomalia_consumo(1.38, [h["medido"] / 100 for h in hist], P["validacao.anomalia_z"], P["validacao.anomalia_amostra_min"], 0.3, 10.0)
        self.assertAlmostEqual(cs[0]["evidencia"]["z"], a["z"])                    # a MESMA conta da Frota
        # com poucos meses, a regra não decide; geração (sentido "gerar") nunca é consumo anormal
        self.assertNotIn("consumo_anormal", self.codigos(va.causas(l, hist[:3], INFO, P)))
        self.assertNotIn("consumo_anormal", self.codigos(va.causas(l, hist, dict(INFO, sentido="gerar"), P)))

    def test_premissa(self):
        jan = [linha(f"2026-{i:02d}", 100, m) for i, m in enumerate([101, 99, 100, 121, 122, 120], start=1)]
        cs = va.causas(jan[-1], jan[:-1], dict(INFO, premissa="agua.per_capita"), P, janela=jan)
        cod = self.codigos(cs)
        self.assertIn("premissa", cod)
        pr = next(c for c in cs if c["codigo"] == "premissa")
        self.assertEqual(pr["evidencia"]["meses"], 3)
        self.assertEqual(pr["evidencia"]["premissa"], "agua.per_capita")
        self.assertEqual(pr["confianca"], 0.65)
        # dois meses só não bastam
        self.assertNotIn("premissa", self.codigos(va.causas(jan[-2], jan[:-2], INFO, P, janela=jan[:-1])))

    def test_sazonal_e_nao_premissa(self):
        meds = [100 * (1 + 0.2 * math.cos(2 * math.pi * k / 12)) for k in range(12)]
        jan = [linha(f"2026-{k + 1:02d}", 100, m) for k, m in enumerate(meds)]
        info = dict(INFO, plano_plano=True)
        cs = va.causas(jan[1], jan[:1], info, P, janela=jan)                       # fevereiro, no alto da estação
        self.assertEqual(self.codigos(cs)[0], "sazonal")
        self.assertNotIn("premissa", self.codigos(cs))
        self.assertTrue(va.plano_plano({f"{k:02d}": 19.77 for k in range(1, 13)}, P))
        self.assertFalse(va.plano_plano({"01": 10.0, "02": 20.0}, P))

    def test_causa_nao_identificada(self):
        cs = va.causas(linha("2026-05", 100, 125, dias=31, dm=31), [], INFO, P)
        self.assertEqual(self.codigos(cs), ["nao_identificada"])
        self.assertEqual(cs[0]["confianca"], 0)
        self.assertEqual(cs[0]["nome"], "Causa não identificada")

    def test_como(self):
        meses = ["2026-01"]
        it = lambda nome, p, m: {"item": nome, "nome": nome, "grandeza": "energia",
                                 "linhas": va.comparar({"01": p}, {"2026-01": {"valor": m, "dias": 31, "dias_mes": 31}}, meses)}
        c = va.como([it("inversor-1", 500, 380), it("inversor-2", 500, 490)], "2026-01")
        self.assertEqual(c["item"], "inversor-1")
        self.assertAlmostEqual(c["parte_pct"], 120 / 130 * 100)


class SemPlano(unittest.TestCase):
    def test_modulo_sem_plano_diz_que_nao_tem(self):
        r = va.analisar_modulo("turbinas", [{"item": "t1", "nome": "Turbina", "plano": None, "medido": {}}], ["2026-01"], P)
        self.assertFalse(r["tem_plano"])
        self.assertEqual(r["sem_plano"], va.SEM_PLANO["turbinas"])
        self.assertIn("Sem plano", r["sem_plano"])
        self.assertEqual((r["linhas"], r["total"], r["quando"]), ([], None, None))
        self.assertEqual(r["itens_sem_plano"], ["Turbina"])

    def test_hub_vazio_todos_sem_plano(self):
        h = Hub(relogio=lambda: datetime(2026, 11, 18, 12, tzinfo=FUSO).timestamp())
        e = va.Validacao(h).estado()
        self.assertEqual(e["meses"][-1], "2026-10")                               # o último mês completo
        self.assertEqual(len(e["meses"]), 12)
        self.assertEqual({m["modulo"]: m["tem_plano"] for m in e["modulos"]}, dict.fromkeys(va.MODULOS, False))
        for m in e["modulos"]:
            self.assertTrue(m["sem_plano"].startswith("Sem plano"))


class LinhaDeBase(unittest.TestCase):
    def test_reta_conhecida(self):
        am = [{"mes": f"2025-{i:02d}", "x": x, "y": 800 + 2.5 * x} for i, x in enumerate([200, 180, 150, 110, 70, 40, 35, 50, 80, 120, 150, 190], 1)]
        m = va.linha_de_base(am, P)
        self.assertAlmostEqual(m["a"], 2.5)
        self.assertAlmostEqual(m["b"], 800.0)
        self.assertAlmostEqual(m["r2"], 1.0)
        self.assertAlmostEqual(m["cv_rmse_pct"], 0.0, places=6)
        self.assertTrue(m["ok"])
        self.assertEqual(va.esperado(m, 100), 1050.0)

    def test_avisos(self):
        curta = [{"mes": "x", "x": x, "y": 10 * x} for x in (1, 2, 3, 4)]
        self.assertIn("Base de 4 meses", va.linha_de_base(curta, P)["aviso"])
        self.assertFalse(va.linha_de_base(curta[:2], P)["ok"])
        ruim = [{"mes": "x", "x": x, "y": y} for x, y in zip(range(12), [100, 300, 90, 280, 120, 310, 95, 260, 140, 330, 80, 290])]
        self.assertIn("CV(RMSE)", va.linha_de_base(ruim, P)["aviso"])

    def test_ipmvp_com_ajuste_rotineiro(self):
        base = [{"mes": f"b{i}", "x": x, "y": 800 + 2.5 * x} for i, x in enumerate([200, 180, 150, 110, 70, 40, 35, 50, 80, 120, 150, 190])]
        rel = [{"mes": f"r{i}", "x": x, "y": 0.9 * (800 + 2.5 * x)} for i, x in enumerate([230, 170, 160, 100, 75, 45, 30, 60, 90, 110, 160, 200])]
        r = va.ipmvp_regressao(base, rel, P)
        esp = sum(800 + 2.5 * s["x"] for s in rel)
        real = sum(s["y"] for s in rel)
        self.assertAlmostEqual(r["ajuste_rotineiro"], esp - sum(s["y"] for s in base))
        self.assertAlmostEqual(r["economia"]["economia"], esp - real)            # = (base − relatório) + ajuste
        self.assertAlmostEqual(r["economia"]["pct"], 10.0)
        self.assertEqual(va.graus_dia([17.0, 20.3, 25.3, None], 18.3), 2.0 + 7.0)


class IpmvpIgualCertificacoes(unittest.TestCase):
    CASOS = [(1200.0, 1000.0, 0.0), (1200.0, 1000.0, 150.0), (1000.0, 1100.0, -50.0), (0.0, 10.0, 0.0), (None, 10.0, 5.0)]

    @staticmethod
    def certificacoes(base, rel, aj):
        """A conta da aba Certificações (mvEconomia, antes de virar compartilhada), escrita aqui para comparar."""
        econ = base - rel + aj if base is not None and rel is not None else None
        base_aj = base + aj if base is not None else None
        return econ, (econ / base_aj * 100 if econ is not None and base_aj > 0 else None)

    def test_python_igual(self):
        for b, r, a in self.CASOS:
            e = va.ipmvp_economia(b, r, a)
            self.assertEqual((e["economia"], e["pct"]), self.certificacoes(b, r, a), (b, r, a))

    @unittest.skipUnless(JS.is_file() and PAINEL.is_file(), "só no repositório")
    def test_uma_conta_so_na_tela(self):
        js = JS.read_text(encoding="utf-8")
        m = re.search(r"function ipmvp\(base, rel, aj\) \{(.*?)\n", js)
        self.assertIsNotNone(m)
        self.assertIn("const econ = base - rel + a, baseAj = base + a; return { econ, baseAj, pct: baseAj > 0 ? econ / baseAj * 100 : null };", js)
        p = PAINEL.read_text(encoding="utf-8")
        f = re.search(r"function mvEconomia\(c\)\{.*?\n(?=function )", p, re.S).group(0)
        self.assertIn("VALIDACAO.ipmvp(b ? b.v : null, p ? p.v : null, aj)", f)
        self.assertNotIn("b.v - p.v", f)                                          # a equação não foi duplicada
        self.assertIn("pct: ip.pct", f)


def _hub_com_energia(agora):
    h = Hub(relogio=lambda: agora)
    def medir(ativo, grandeza, dia, valor, horas=range(24)):
        for hh in horas:
            ts = int(datetime(int(dia[:4]), int(dia[5:7]), int(dia[8:10]), hh, tzinfo=FUSO).timestamp())
            v = valor + (0.1 if hh % 2 else -0.1) if grandeza == "energia" else valor   # varia um pouco (série parada é "travado")
            h._db.execute("INSERT INTO medicao(leitura,topico,grandeza,ativo,valor,ts,alarme) VALUES(0,'t',?,?,?,?,'ok')", (grandeza, ativo, v, ts))
    for d in range(1, 31):                                    # setembro inteiro: 2 kW
        medir("lugar01-no84", "energia", f"2026-09-{d:02d}", 2.0)
    for d in range(1, 10):                                    # outubro: só 9 dias (o medidor parou)
        medir("lugar01-no84", "energia", f"2026-10-{d:02d}", 2.0)
    for d in range(1, 31):                                    # temperatura do ar de setembro: 21,3 °C (3 graus-dia por dia)
        medir("lugar01-no81-ar", "temperatura", f"2026-09-{d:02d}", 21.3, horas=(6, 18))
    h._db.commit()
    return h


class NoHub(unittest.TestCase):
    AGORA = datetime(2026, 11, 18, 12, tzinfo=FUSO).timestamp()

    def setUp(self):
        self.h = _hub_com_energia(self.AGORA)
        self.v = va.Validacao(self.h, fatores=carbono.carregar())
        r = self.v.gravar_plano({"modulo": "energia", "item": "quadro", "nome": "Quadro geral", "ativo": "lugar01-no84", "grandeza": "energia",
                                 "fonte": "teste: 2 kW o dia todo", "meses": {f"{m:02d}": 48.0 * va.dias_do_mes(f"2026-{m:02d}") for m in range(1, 13)}}, "ana")
        self.assertTrue(r["ok"], r)

    def test_medido_do_hub_e_falha_de_dado(self):
        med = self.v.medido_mensal("lugar01-no84", "energia", ["2026-08", "2026-09", "2026-10"])
        self.assertIsNone(med["2026-08"]["valor"])                               # antes da primeira leitura: sem dado
        self.assertAlmostEqual(med["2026-09"]["valor"], 2.0 * 24 * 30)
        self.assertEqual((med["2026-10"]["dias"], med["2026-10"]["dias_mes"]), (9, 31))
        e = self.v.estado()
        en = next(m for m in e["modulos"] if m["modulo"] == "energia")
        self.assertTrue(en["tem_plano"])
        self.assertEqual(en["quando"]["primeiro_mes"], "2026-10")
        x = en["explicacoes"][0]
        self.assertEqual(x["causas"][0]["codigo"], "falha_dado")
        self.assertEqual(x["como"]["ativo"], "lugar01-no84")
        self.assertAlmostEqual(next(l for l in en["linhas"] if l["mes"] == "2026-09")["pct"], 0.0)

    def test_carbono_derivado_com_o_fator_do_carbono(self):
        e = self.v.estado()
        cb = next(m for m in e["modulos"] if m["modulo"] == "carbono")
        self.assertTrue(cb["tem_plano"])
        f = carbono.fator_rede(carbono.carregar(), None)
        set_ = next(l for l in cb["linhas"] if l["mes"] == "2026-09")
        self.assertAlmostEqual(set_["medido"], 1440.0 * f / 1000)
        self.assertFalse(next(m for m in e["modulos"] if m["modulo"] == "frota")["tem_plano"])   # sem frota ligada

    def test_frota_sem_consumo_esperado_fica_sem_plano(self):
        fr = frota.Frota(self.h, fatores=carbono.carregar())
        fr.gravar_veiculo({"tipo": "carro", "placa": "TST1A23", "combustivel": "gasolina_c"}, "ana")
        v = va.Validacao(self.h, frota=fr)
        m = next(x for x in v.estado()["modulos"] if x["modulo"] == "frota")
        self.assertFalse(m["tem_plano"])
        self.assertEqual(m["sem_plano"], va.SEM_PLANO["frota"])

    def test_linha_de_base_pela_rota(self):
        pid = self.v.planos()[0]["id"]
        r = self.v.baseline(pid, "graus_dia", ("2026-09", "2026-09"), ("2026-10", "2026-10"))
        self.assertTrue(r["ok"])
        self.assertEqual(r["modelo"]["n"], 1)                                     # um mês só: não dá regressão
        self.assertIsNone(r["economia"]["economia"])
        self.assertEqual(self.v.clima_mensal("graus_dia", ["2026-09"]), {"2026-09": 30 * 3.0})
        self.assertFalse(self.v.baseline(pid, "vento", ("2026-09", "2026-09"), ("2026-10", "2026-10"))["ok"])

    def test_plano_invalido(self):
        for d, erro in (({"modulo": "frota", "item": "x", "fonte": "f", "meses": {"01": 1}}, "módulo"),
                        ({"modulo": "solar", "item": "x y", "fonte": "f", "meses": {"01": 1}}, "item"),
                        ({"modulo": "solar", "item": "x", "fonte": " ", "meses": {"01": 1}}, "fonte"),
                        ({"modulo": "solar", "item": "x", "fonte": "f", "meses": {"13": 1}}, "mês"),
                        ({"modulo": "solar", "item": "x", "fonte": "f", "meses": {"01": -1}}, "mês")):
            r = self.v.gravar_plano(d, "ana")
            self.assertFalse(r["ok"])
            self.assertIn(erro, r["erro"])

    def test_rotas_e_papeis(self):
        cli, eq = {"usuario": "c", "papel": "cliente"}, {"usuario": "e", "papel": "operador"}
        self.assertEqual(self.v.rota("GET", "/api/validacao/estado", None)[0], 401)
        cod, r = self.v.rota("GET", "/api/validacao/estado", cli, None, {"meses": ["6"]})
        self.assertEqual((cod, len(r["meses"])), (200, 6))
        corpo = json.dumps({"modulo": "agua", "item": "hidro", "fonte": "teste", "meses": {"01": 10}})
        self.assertEqual(self.v.rota("POST", "/api/validacao/plano", cli, corpo)[0], 403)
        self.assertEqual(self.v.rota("POST", "/api/validacao/plano", eq, corpo)[0], 200)
        self.assertEqual(self.v.rota("POST", "/api/validacao/plano", eq, json.dumps({"modulo": "agua", "item": "h", "fonte": "f", "meses": {}, "x": 1}))[0], 400)
        pid = next(p["id"] for p in self.v.planos() if p["item"] == "hidro")
        self.assertEqual(self.v.rota("POST", "/api/validacao/plano/remover", eq, json.dumps({"id": pid}))[0], 200)
        self.assertEqual(self.v.rota("POST", "/api/validacao/plano/remover", eq, json.dumps({"id": pid}))[0], 404)


def _premissas_base():
    return {p["id"]: p for p in json.loads(PREMISSAS.read_text(encoding="utf-8"))["premissas"] if p["id"].startswith("validacao.")}


@unittest.skipUnless(JS.is_file() and PREMISSAS.is_file(), "só no repositório")
class EspelhoEPremissas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = JS.read_text(encoding="utf-8")

    def test_premissas_conferir_e_iguais(self):
        base = _premissas_base()
        self.assertEqual(set(base), set(va.PREMISSAS_PADRAO))
        for k, p in base.items():
            self.assertEqual(p["status"], "conferir", k)
            self.assertEqual(p["valor_padrao"], va.PREMISSAS_PADRAO[k], k)
        base = {k: v for k, v in base.items() if v["valor_padrao"] is not None}      # as do PEE são [MARCADOR]
        reserva = re.search(r"const PREMISSAS_RESERVA = \{(.*?)\};", self.js, re.S).group(1)
        js = {k: float(v) for k, v in re.findall(r'"(validacao\.[\w]+)":([\d.]+)', reserva)}
        self.assertEqual(js, {k: float(v) for k, v in va.PREMISSAS_PADRAO.items() if v is not None})
        self.assertEqual(va.premissas(), va.PREMISSAS_PADRAO)

    def test_modulos_e_regras_no_espelho(self):
        for k, c in va.MODULOS.items():
            self.assertIn(f'{k}:{{ nome:"{c["nome"]}", unidade:"{c["unidade"]}"', self.js)
            self.assertIn(f'sentido:"{c["sentido"]}"', self.js)
            self.assertIn(va.SEM_PLANO[k], self.js)
        for k, n in va.CAUSAS.items():
            self.assertIn(f'{k}:"{n}"', self.js)
        for trecho in ('causa("falha_dado", cob === 0 ? 0.95 : Math.min(0.9, 0.5 + (cobMin - cob) / 100)',
                       '0.35 + 0.5 * Math.min(Math.abs(dc), Math.abs(pct)) / Math.max(Math.abs(dc), Math.abs(pct))',
                       'FROTA.anomaliaConsumo(linha.medido / linha.planejado', 'info.premissa ? 0.65 : 0.6', 'causa("sazonal", 0.5',
                       'Math.abs(linha.medido - mm) / mm * 100 >= lim / 2', 'Math.abs(mediaAno) >= lim / 2'):
            self.assertIn(trecho, self.js)

    def test_tela_segura_e_acessivel(self):
        self.assertNotRegex(self.js, r"https?://")
        self.assertNotRegex(self.js, r"(?i)</script")
        self.assertNotRegex(self.js, r"\beval\s*\(|new Function")
        self.assertEqual(self.js.count("<h1>"), 1)
        for t in ('role="img"', "<caption", 'scope="col"', 'scope="row"', "aria-labelledby", 'aria-pressed', 'role="status"', "<label for="):
            self.assertIn(t, self.js)
        for cor in re.findall(r"#[0-9A-Fa-f]{6}\b", self.js):                      # só cores da paleta
            self.assertIn(cor.upper(), (RAIZ / "physis-hub" / "docs" / "PALETA.md").read_text(encoding="utf-8").upper())

    def test_demonstracao_simulada_com_clima_e_equipamento_desligado(self):
        """A Casa Physis simulada tem um desvio explicado pelo clima (solar) e outro por equipamento desligado (turbina)."""
        self.assertIn("k === SIM.mes_clima ? 0.72", self.js)
        self.assertIn("k === SIM.mes_offline ? SIM.dias_offline : dm", self.js)
        self.assertIn("Dados SIMULADOS da Casa Physis.", self.js)
        self.assertIn("(SIMULADO)", self.js)


@unittest.skipUnless(PAINEL.is_file(), "painel ausente")
class AbaNaCasaPhysisForaDaLoja(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = PAINEL.read_text(encoding="utf-8")

    def lista(self, nome):
        return set(re.findall(r'"([\w-]+)"', re.search(rf"const {nome} = new Set\(\[(.*?)\]\)", self.h).group(1)))

    def test_aba_em_desenvolvimento_na_casa_physis(self):
        self.assertIn('["validacao","Validação · planejado × gerado (M&V)"]', self.h)
        self.assertIn("validacao", self.lista("ABAS_DEV"))
        self.assertIn("validacao", self.lista("COM_INTERFACE"))
        self.assertIn('validacao: () => typeof telaValidacao === "function" ? seloDev(telaValidacao(),', self.h)
        self.assertIn('<script id="mod-validacao">', self.h)
        self.assertIn("window.VALIDACAO_I18N,", self.h)
        self.assertIn("MODS_PLAN.validacao = {", self.h)
        cli = json.loads((RAIZ / "clientes" / "clientes.json").read_text(encoding="utf-8"))
        casa = next(c for c in cli["clientes"] if c.get("org") == "casa-physis")
        self.assertIn("validacao", casa["modulos"])
        self.assertTrue(casa.get("pesquisa"))

    def test_fora_da_loja_publica(self):
        self.assertNotIn("validacao", self.lista("LOJA_VENDA"))
        self.assertNotIn("validacao", self.lista("ABAS_VENDA"))
        self.assertIn('{ id:"validacao", g:"pdi", cod:"Uso interno"', self.h)     # só na loja interna, como a Frota
        self.assertEqual(Hub.ITEM_MODULOS["validacao"], ("validacao",))
        self.assertIn("validacao", Hub.MODULOS_PLATAFORMA)
        sys.path.insert(0, str(RAIZ / "demos"))
        import gerar_demos
        self.assertNotIn("validacao", gerar_demos.MODULOS_DEMO)
        sys.path.insert(0, str(RAIZ / "physis-hub"))
        import montar
        self.assertIn("validacao", montar.MODULOS)

    def test_links_de_certificacoes_n4_e_sustainkit(self):
        self.assertIn('No nível 4, a medição contínua fica na aba Validação', self.h)
        self.assertIn('<button type="button" data-aba="validacao">Abrir a Validação</button>', self.h)
        f = re.search(r"function telaSustainkit\(d\)\{.*?\n", self.h).group(0)
        self.assertIn('data-aba="validacao"', f)


# ══ Checklist de excelência e M&V 2.0 (núcleo) ═══════════════════════════════════════════════
from physis_hub import integridade, validacao_modelos as vm, validacao_nucleo as vn   # noqa: E402

PT = dict(va.premissas())


def _hub_horario():
    """Dois anos de dados de hora em hora (SIMULADOS no teste): base, medida de 12 % no relatório, um equipamento novo
    em 01/06/2026 (+0,4 kW o dia todo) e quatro dias com consumo 80 % acima em março."""
    import random as _r
    agora = datetime(2026, 11, 18, 12, tzinfo=FUSO).timestamp()
    h = Hub(relogio=lambda: agora)
    r = _r.Random(1)
    t, fim, rows = datetime(2024, 11, 1, tzinfo=FUSO).timestamp(), datetime(2026, 11, 1, tzinfo=FUSO).timestamp(), []
    while t < fim:
        dt = datetime.fromtimestamp(t, FUSO)
        T = 21 + 5 * math.cos(2 * math.pi * (dt.timetuple().tm_yday - 15) / 365)
        rel, dia = dt.strftime("%Y-%m") >= "2025-11", dt.strftime("%Y-%m-%d")
        kw = (0.9 + (1.5 if 8 <= dt.hour < 18 else 0) + 0.12 * max(0, T - 19.5)) * (0.88 if rel else 1)
        kw += 0.4 if dia >= "2026-06-01" else 0
        kw *= 1.8 if dia in ("2026-03-10", "2026-03-11", "2026-03-12", "2026-03-13") else 1
        rows.append((0, "t", "energia", "lugar01-no84", kw * (1 + r.gauss(0, 0.03)), int(t), "ok"))
        if dt.hour in (0, 6, 12, 18):
            rows.append((0, "t", "temperatura", "lugar01-no81-ar", T + r.gauss(0, 0.5), int(t), "ok"))
        t += 3600
    h._db.executemany("INSERT INTO medicao(leitura,topico,grandeza,ativo,valor,ts,alarme) VALUES(?,?,?,?,?,?,?)", rows)
    h._db.commit()
    v = va.Validacao(h, fatores=carbono.carregar())
    v.gravar_plano({"modulo": "energia", "item": "quadro", "ativo": "lugar01-no84", "grandeza": "energia", "fonte": "teste",
                    "meses": {f"{m:02d}": 1500.0 for m in range(1, 13)}}, "ana")
    v.gravar_plano_mv({"escopo": "Casa de teste", "fronteira": "medidor geral", "opcao": "C", "justificativa": "medidas juntas",
                       "metodo": "ponto de mudança diário", "base_ini": "2024-11", "base_fim": "2025-10", "rel_ini": "2025-11",
                       "rel_fim": "2026-10", "tarifa_kwh": 0.9, "meta_economia": 3000.0, "ecms": [{"id": "avac", "nome": "AVAC"}]}, "inicial", "ana")
    return h, v


class Modelos(unittest.TestCase):
    def test_metricas(self):
        m = vm.metricas([10.0, 12.0, 14.0, 16.0], [11.0, 12.0, 13.0, 16.0], 2)
        self.assertAlmostEqual(m["r2"], 1 - 2 / 20)
        self.assertAlmostEqual(m["erro_padrao"], 1.0)                              # √(2 ÷ (4 − 2))
        self.assertAlmostEqual(m["cv_rmse_pct"], 1.0 / 13 * 100)
        self.assertAlmostEqual(m["nmbe_pct"], 0.0)
        self.assertAlmostEqual(vm.metricas([10.0, 10.0, 10.0], [9.0, 9.0, 9.0], 1)["nmbe_pct"], 3 / (2 * 10) * 100)

    def test_escolhe_3p_e_validacao_cruzada(self):
        import random as _r
        r = _r.Random(3)
        xs = [10 + 20 * i / 199 for i in range(200)]
        ys = [10 + 2 * max(0, x - 20) + r.gauss(0, 0.3) for x in xs]
        e = vm.escolher_modelo(xs, ys, PT)
        self.assertEqual(e["escolhido"]["tipo"], "3P")
        self.assertAlmostEqual(e["escolhido"]["cps"][0], 20.0, delta=1.0)
        c = vn.escolher_por_cv(xs, ys, PT)
        self.assertEqual(c["escolhido"]["tipo"], "3P")
        self.assertTrue(all(m["cv_fora_pct"] is not None for m in c["candidatos"]))
        lin = [5 + 0.5 * x + r.gauss(0, 0.2) for x in xs]
        self.assertEqual(vm.escolher_modelo(xs, lin, PT)["escolhido"]["tipo"], "2P")
        d = vn.diagnostico(e["escolhido"], xs, ys)
        self.assertLess(d["p_valores"][1]["p"], 0.001)
        self.assertIn("durbin_watson", d["residuos"])
        self.assertTrue(vn.aceite_minimo(e["escolhido"], PT)["ok"])

    def test_incerteza_dentro_e_fora(self):
        dentro = vm.incerteza_economia(5.0, 365, 365, 0.12, PT)
        fora = vm.incerteza_economia(40.0, 30, 10, 0.02, PT)
        self.assertEqual(dentro["veredito"], "dentro")
        self.assertEqual(fora["veredito"], "fora do limite")
        self.assertGreater(fora["incerteza_pct"], PT["validacao.incerteza_max_pct"])
        self.assertAlmostEqual(vm.t_student(68.0, 1e6), 0.99446, places=3)
        self.assertEqual(vm.incerteza_economia(5.0, 10, 10, None, PT)["veredito"], "sem_dado")


class Limpeza(unittest.TestCase):
    def test_marca_e_guarda_o_original(self):
        pts = [{"id": i, "ts": 1000 + i * 900, "valor": 2.0 + 0.1 * (i % 3)} for i in range(60)]
        pts[10]["valor"] = 50.0                                                   # salto isolado
        for i in range(30, 45):
            pts[i]["valor"] = 3.333                                               # travado
        pts.append({"id": 99, "ts": pts[5]["ts"], "valor": 2.1})                  # carimbo repetido
        r = vm.limpar_serie(pts, PT, "energia", (0, 500), agora=10**9)
        o = {p["id"]: p for p in r["pontos"]}
        self.assertEqual(o[10]["original"], 50.0)
        self.assertIsNone(o[10]["valor"])
        self.assertIn("atipico", o[10]["marcas"])
        self.assertIn("travado", o[40]["marcas"])
        self.assertEqual(o[40]["original"], 3.333)
        self.assertIn("ts_duplicado", o[99]["marcas"])
        self.assertEqual(o[3]["valor"], o[3]["original"])                        # ponto bom não muda
        neg = vm.limpar_serie([{"id": 1, "ts": 100, "valor": -2.0}, {"id": 2, "ts": 200, "valor": 3.0}], PT, "vazao")
        self.assertEqual(neg["pontos"][0]["marcas"], ["negativo"])
        self.assertEqual(neg["pontos"][0]["original"], -2.0)
        self.assertEqual(r["granularidade"], "15 min")

    def test_degrau_de_operacao_nao_e_atipico(self):
        pts = [{"id": i, "ts": i * 3600, "valor": (2.5 if 8 <= i % 24 < 18 else 1.0) + 0.01 * (i % 5)} for i in range(24 * 7)]
        self.assertNotIn("atipico", vm.limpar_serie(pts, PT, "energia")["resumo"])

    def test_politica_de_faltantes(self):
        P2 = dict(PT, **{"validacao.travado_n": 999})
        pts = [{"id": i, "ts": datetime(2026, 1, 1, tzinfo=FUSO).timestamp() + i * 3600, "valor": 1.0} for i in range(48) if not 5 <= i < 15]
        ex = vn.agregar(vm.limpar_serie(pts, P2, "energia")["pontos"], FUSO, "excluir", 90)
        self.assertTrue(ex["dias"]["2026-01-01"]["excluido"])
        lin = vn.agregar(vm.limpar_serie(pts, P2, "energia")["pontos"], FUSO, "linear", 90)
        self.assertAlmostEqual(lin["dias"]["2026-01-01"]["y"], 24.0)
        self.assertEqual(lin["dias"]["2026-01-01"]["imputados"], 10)
        self.assertAlmostEqual(lin["faltantes"]["2026-01"]["faltantes_pct"], 10 / 48 * 100)


class PlanoMedidoresEDados(unittest.TestCase):
    def test_calibracao_vencida(self):
        a = {x["tipo"] for x in va.alertas_medidor({"cal_proxima": "2026-01-01", "exatidao_pct": None}, "2026-11-18")}
        self.assertEqual(a, {"calibracao_vencida", "exatidao_desconhecida", "sem_certificado"})
        ok = va.alertas_medidor({"cal_proxima": "2027-01-01", "exatidao_pct": 1.0, "certificado_sha256": "a" * 64}, "2026-11-18")
        self.assertEqual(ok, [])

    def test_opcao_d_exige_programa_e_versao(self):
        base = {"escopo": "e", "fronteira": "f", "opcao": "D", "justificativa": "j", "metodo": "m"}
        self.assertIn("programa de simulação", va.validar_plano_mv(base)[1])
        self.assertIn("SHA-256", va.validar_plano_mv(dict(base, simulacao={"software": "X", "versao": "1"}))[1])
        pl, erro = va.validar_plano_mv(dict(base, simulacao={"software": "X", "versao": "1", "arquivos": [{"nome": "a.idf", "sha256": "b" * 64}]}))
        self.assertEqual(erro, "")
        self.assertEqual(pl["simulacao"]["versao"], "1")
        self.assertIn("opção IPMVP", va.validar_plano_mv(dict(base, opcao="E"))[1])

    def test_contrafactual_d_com_a_simulacao_da_plataforma(self):
        sim = {"envoltoria_antes": [{"nome": "parede", "area": 100.0, "u": 2.5}], "envoltoria_depois": [{"nome": "parede", "area": 100.0, "u": 0.8}],
               "ti": 24.0, "cop": 3.0}
        c = vn.contrafactual_d(sim, {"2026-01-01": 32.0, "2026-01-02": 30.0})
        self.assertAlmostEqual(c["saida"]["economia_kwh"], (2.5 - 0.8) * 100 * (8 + 6) * 24 / 1000 / 3)
        self.assertIn("simulacao.termica", c["software"])
        self.assertEqual({a["papel"] for a in c["arquivos"]}, {"entrada", "saida"})

    def test_versoes_no_registro_encadeado(self):
        h = Hub(relogio=lambda: 1794600000)
        v = va.Validacao(h)
        pl = {"escopo": "e", "fronteira": "f", "opcao": "C", "justificativa": "j", "metodo": "m",
              "papeis": [{"papel": "analise", "pessoa": "Erick Lopes"}]}
        self.assertFalse(v.gravar_plano_mv(pl, "", "ana")["ok"])                 # sem motivo, não grava
        self.assertTrue(v.gravar_plano_mv(pl, "inicial", "ana")["ok"])
        self.assertTrue(v.gravar_plano_mv(dict(pl, escopo="e2"), "escopo mudou", "rafael")["ok"])
        pm = v.plano_mv()
        self.assertEqual((pm["versao"], len(pm["versoes"]), pm["atual"]["escopo"]), (2, 2, "e2"))
        self.assertEqual(pm["atual"]["papeis"][0]["competencia"], "")             # competência nunca presumida
        regs = h._db.execute("SELECT origem, conteudo FROM registro WHERE tipo='validacao_plano_mv' ORDER BY seq").fetchall()
        self.assertEqual([r[0] for r in regs], ["ana", "rafael"])
        self.assertIn("escopo mudou", regs[1][1])
        self.assertTrue(h.verificar_cadeia()[0])

    def test_secoes_do_relatorio(self):
        r = va.relatorio_blocos({"modulos": [], "plano_mv": {"atual": {"opcao": "D", "simulacao": {"software": "X", "versao": "1", "arquivos": []}}}})
        titulos = [b["t"] for b in r["blocos"] if b.get("h") == 2]
        self.assertEqual(titulos, va.SECOES_RELATORIO)
        self.assertTrue(any("X versão 1" in str(b.get("t")) for b in r["blocos"]))
        js = JS.read_text(encoding="utf-8")
        self.assertIn("const SECOES_RELATORIO = " + json.dumps(va.SECOES_RELATORIO, ensure_ascii=False).replace('","', '", "') + ";", js)


class Nucleo(unittest.TestCase):
    def test_cusum_deriva(self):
        estavel = [0.1 * ((i * 7) % 5 - 2) for i in range(100)]
        self.assertFalse(vn.cusum(estavel, PT, media=0.0, desvio=0.2)["alarme"])
        deriva = estavel[:50] + [x + 0.3 for x in estavel[50:]]
        c = vn.cusum(deriva, PT, media=0.0, desvio=0.2)
        self.assertTrue(c["alarme"])
        self.assertEqual(c["lado"], "acima")
        self.assertGreaterEqual(c["indice"], 50)

    def test_monte_carlo_semente_e_sensibilidade(self):
        args = {"esperado": 10000.0, "medido": 8800.0, "m_dias": 365, "erro_padrao": 2.0, "rho": 0.1, "exatidao_pct": 2.0, "imputados": 20}
        a, b = vn.monte_carlo(**args, P=PT, semente="x"), vn.monte_carlo(**args, P=PT, semente="x")
        self.assertEqual((a["ic_inf"], a["ic_sup"]), (b["ic_inf"], b["ic_sup"]))
        self.assertLess(a["ic_inf"], 1200.0)
        self.assertGreater(a["ic_sup"], 1200.0)
        self.assertEqual(a["confianca_pct"], 95.0)
        s = vn.sensibilidade(args, PT, "x")
        self.assertEqual(s[0]["fonte"], "medidor")                                # 2 % de 8.800 kWh pesa mais que o modelo
        self.assertAlmostEqual(sum(x["parte_pct"] for x in s), 100.0)
        s2 = vn.sensibilidade(dict(args, exatidao_pct=0.1, erro_padrao=8.0), PT, "x")
        self.assertEqual(s2[0]["fonte"], "modelo")

    def test_fdd_so_fora_do_intervalo_e_risco(self):
        serie = [{"dia": f"2026-01-{d:02d}", "esperado": 100.0, "medido": 120.0} for d in range(1, 8)]
        self.assertEqual(vn.fdd_intervalo(serie, 20.0, 365, PT), [])           # +20 %, mas dentro do intervalo (σ grande)
        al = vn.fdd_intervalo(serie, 2.0, 365, PT, tarifa=1.0)
        self.assertEqual(len(al), 1)
        self.assertEqual(al[0]["dias"], 7)
        self.assertGreater(al[0]["rs_em_risco"], 0)
        ord_ = vn.ordenar_por_risco([{"rs_em_risco": 10.0}, {"rs_em_risco": None, "excesso": 99.0}, {"rs_em_risco": 50.0}])
        self.assertEqual([x["rs_em_risco"] for x in ord_], [50.0, 10.0, None])

    def test_projecao_por_persistencia(self):
        serie = [{"acumulada": 10.0 * (i + 1)} for i in range(30)]
        p = vn.projecao_persistencia(serie, 365, 5000.0, tarifa=1.0)
        self.assertAlmostEqual(p["projetada"], 3650.0)
        self.assertTrue(p["risco"])
        self.assertAlmostEqual(p["rs_em_risco"], 1350.0)
        self.assertFalse(vn.projecao_persistencia(serie, 365, 3000.0)["risco"])

    def test_amostragem_pee(self):
        n5 = vn.tamanho_amostra(1000, 0.5, 90.0, 10.0)
        n2 = vn.tamanho_amostra(1000, 0.5, 90.0, 5.0)
        self.assertGreater(n2, n5)                                                 # precisão mais apertada, amostra maior
        self.assertLessEqual(vn.tamanho_amostra(10, 0.5, 90.0, 1.0), 10)
        self.assertGreater(vn.precisao_alcancada(1000, 30, 50.0, 10.0, 90.0), vn.precisao_alcancada(1000, 300, 50.0, 10.0, 90.0))
        self.assertFalse(vn.plano_amostral([{"N": 100}], None, None)["ok"])       # sem número: aguarda o Guia

    def test_premissas_pee_sao_marcadores(self):
        base = json.loads(PREMISSAS.read_text(encoding="utf-8"))["premissas"]
        pee = [p for p in base if p["id"].startswith("validacao.pee.")]
        self.assertEqual({p["id"] for p in pee}, set(vn.PREMISSAS_PEE))
        for p in pee:
            self.assertIsNone(p["valor_padrao"], p["id"])
            self.assertIn("[MARCADOR: conferir no Guia de M&V da ANEEL]", p["fonte"])
            self.assertEqual(p["status"], "conferir")

    def test_perfil_pee_no_plano_e_no_relatorio(self):
        base = {"escopo": "e", "fronteira": "f", "opcao": "A", "justificativa": "j", "metodo": "m"}
        geral, _ = va.validar_plano_mv(base)
        self.assertEqual((geral["perfil"], geral["pee"]), ("geral", None))
        pl, _ = va.validar_plano_mv(dict(base, perfil="pee", pee={"energia_economizada_mwh_ano": 120.0, "reducao_demanda_ponta_kw": 35.0,
                                                                  "rcb": 0.6, "custo_mv": 5000, "custo_total": 100000, "confianca_pct": 90, "precisao_pct": 10,
                                                                  "estratos": [{"nome": "lâmpadas", "N": 800, "cv": 0.5}]}))
        r = vn.resumo_pee(pl["pee"], PT)
        for k in ("energia_economizada_mwh_ano", "reducao_demanda_ponta_kw", "rcb", "rcb_entradas", "custo_check", "erro_pct", "precisao_pct", "confianca_pct"):
            self.assertIn(k, r)
        self.assertAlmostEqual(r["custo_check"]["parte_pct"], 5.0)
        self.assertEqual(r["custo_check"]["situacao"], "aguardando Guia")         # limite é [MARCADOR]
        self.assertEqual(r["amostragem"]["estratos"][0]["n_amostra"], vn.tamanho_amostra(800, 0.5, 90, 10))
        self.assertEqual(set(r["aguardando_guia"]), set(vn.PREMISSAS_PEE))
        rel = va.relatorio_blocos({"modulos": [], "pee": r})
        self.assertTrue(any("PEE" in str((b.get("tabela") or {}).get("legenda")) for b in rel["blocos"]))


class NucleoNoHub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h, cls.v = _hub_horario()
        cls.e = cls.v.estado()
        cls.x = cls.e["mv2"][0]

    def test_modelo_versao_com_hash_e_fonte_do_clima(self):
        x = self.x
        self.assertIn(x["modelo"]["tipo"], ("2P", "3P", "4P", "5P", "ML"))
        self.assertTrue(x["aceite_minimo"]["ok"])
        self.assertEqual(len(x["modelo_versao"]["hash"]), 64)
        self.assertEqual(x["fonte_temperatura"], "estação do lugar (temperatura do ar)")
        self.assertEqual(x["granularidade"], "hora")
        self.assertEqual(x["politica_faltantes"], "excluir")
        n = self.h._db.execute("SELECT COUNT(*) FROM validacao_modelo").fetchone()[0]
        self.v.estado()
        self.assertEqual(self.h._db.execute("SELECT COUNT(*) FROM validacao_modelo").fetchone()[0], n)   # mesmo dado: mesma versão
        self.assertIsNotNone(x["horario"])

    def test_fdd_alarma_os_dias_de_marco_por_rs(self):
        al = self.x["alarmes"]
        self.assertTrue(any(a["inicio"] == "2026-03-10" and a["lado"] == "acima" for a in al))
        self.assertEqual(al, vn.ordenar_por_risco(al))
        self.assertTrue(all(a["rs_em_risco"] is not None for a in al))

    def test_nre_pendente_ate_aprovar(self):
        nres = self.x["nres"]
        self.assertEqual(len(nres), 1)
        n = nres[0]
        self.assertEqual((n["situacao"], n["classe"]), ("pendente", "equipamento_novo"))
        self.assertEqual(n["inicio"][:7], "2026-06")
        self.assertEqual(self.x["ajuste_nao_rotineiro"], 0)                       # pendente não entra na conta
        self.assertFalse(self.v.decidir_nre(n["chave"], True, "", "ana")["ok"])
        r = self.v.decidir_nre(n["chave"], True, "geladeira nova confirmada em campo", "rafael")
        self.assertTrue(r["ok"])
        x2 = self.v.estado()["mv2"][0]
        self.assertAlmostEqual(x2["economia_ajustada"], x2["economia"] + n["ajuste_proposto"])
        self.assertEqual(self.h._db.execute("SELECT COUNT(*) FROM registro WHERE tipo='validacao_nre'").fetchone()[0], 1)

    def test_projecao_e_monte_carlo(self):
        x = self.x
        self.assertTrue(x["projecao"]["risco"])                                   # meta de 3.000 kWh não será atingida
        mc = x["monte_carlo"]
        self.assertLess(mc["ic_inf"], x["economia"])
        self.assertGreater(mc["ic_sup"], x["economia"])
        self.assertEqual(x["sensibilidade"][0]["fonte"], "modelo")                # medidor sem exatidão cadastrada
        self.assertIn("veredito", x["incerteza"])

    def test_tarefa_na_gestao(self):
        a = self.x["alarmes"][0]
        r = self.v.criar_tarefa(a, "arthur")
        self.assertTrue(r["ok"])
        g = json.loads(self.h.gestao_ler()[va.CHAVE_GESTAO]["valor"])
        self.assertEqual(g["_formato"], "physis-validacao-tarefas/1")
        self.assertEqual(g["tarefas"][-1]["evidencia"]["chave"], a["chave"])
        self.assertTrue(self.v.criar_tarefa(a, "arthur")["ja_existia"])           # idempotente
        self.assertEqual(len(json.loads(self.h.gestao_ler()[va.CHAVE_GESTAO]["valor"])["tarefas"]), 1)

    def test_resultado_verificado_no_lote_de_integridade(self):
        r = self.v.verificar_resultado(self.x, "erick")
        self.assertEqual(len(r["resumo"]), 64)
        self.assertEqual(r["dados"]["modelo_hash"], self.x["modelo_versao"]["hash"])
        integridade.preparar(self.h._db)
        regs, _ = integridade.registros_do_dia(self.h._db, NoHub.AGORA - 86400, NoHub.AGORA + 86400, org="org-teste", lugar="lugar01")
        ev = [x for x in regs if x["grandeza"] == "economia_verificada"]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["metodo"]["resumo_resultado"], r["resumo"])
        self.assertEqual(vn.resumo(ev[0]["metodo"]["resultado"]), r["resumo"])   # terceiro confere sem os dados brutos
        lote = integridade.fechar_lote(ev, lote_id="t", periodo=("a", "b"), responsavel="teste", dicionario="d", fechado_em="x")
        self.assertTrue(integridade.conferir_lote(lote)[0])

    def test_pacote_de_auditoria_reproduz_a_conta(self):
        pk = self.v.pacote_auditoria("quadro")
        self.assertTrue(pk.pop("ok"))
        for k in ("dados_brutos", "limpeza", "modelo", "calculo", "hashes", "politica", "temperaturas"):
            self.assertIn(k, pk)
        pk2 = json.loads(json.dumps(pk))                                          # o arquivo exportado, relido
        c = vn.conferir_pacote(pk2, va.premissas())
        self.assertTrue(c["ok"])
        self.assertAlmostEqual(c["economia"], self.x["economia"], places=6)
        pk2["dados_brutos"][100]["valor"] += 5
        self.assertFalse(vn.conferir_pacote(pk2, va.premissas())["ok"])

    def test_temperatura_de_fonte_aberta_sem_estacao(self):
        h = Hub(relogio=lambda: NoHub.AGORA)
        h._db.execute("CREATE TABLE IF NOT EXISTS clima_fonte (fonte TEXT PRIMARY KEY, dados TEXT NOT NULL, consultado REAL NOT NULL, erro TEXT NOT NULL DEFAULT '', erro_em REAL)")
        h._db.execute("INSERT INTO clima_fonte(fonte,dados,consultado) VALUES('openmeteo', ?, 0)", (json.dumps({"dias": [{"dia": "2026-11-18", "tmax": 30, "tmin": 20}]}),))
        t, fonte = va.Validacao(h).temperaturas_dia(0)
        self.assertEqual(t, {"2026-11-18": 25.0})
        self.assertIn("Open-Meteo", fonte)


if __name__ == "__main__":
    unittest.main()
