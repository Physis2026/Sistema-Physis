"""AVAC: água gelada e complementos (piscina com filtragem e borda infinita, sauna, churrasqueira); Planejador: sprinklers (24/11/2026)."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
JS = """global.window=global;global.calcLer=()=>({});global.calcGravar=()=>{};global.esc=s=>String(s);global.n2=(v,c)=>v.toFixed(c);global.ui={};global.el=()=>null;
require(%s);const a=JSON.parse(process.argv[1]);console.log(JSON.stringify(a.f==='agua'?AVAC.calcAgua(a.e,a.R):AVAC.calcExtras(a.e,a.R)));"""


def avac(**a):
    r = subprocess.run([NODE, "-e", JS % json.dumps(str(RAIZ / "sistema" / "physis-avac.js")), json.dumps(a)], capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout)


@unittest.skipUnless(NODE, "node não instalado")
class Avac(unittest.TestCase):
    def test_agua_gelada(self):
        x = avac(f="agua", e={"ag": {"dT": 5, "vel": 2, "H": 30, "eta": 0.7}}, R={"ac": {"kWt": 351.7}})
        self.assertAlmostEqual(x["TR"], 100, 3)
        self.assertAlmostEqual(x["m3h"], 351.7 / (4.186 * 5) * 3.6, 6)
        self.assertAlmostEqual(x["Ph"], 9.81 * 30 * x["kgs"] / 1000, 6)
        self.assertEqual(x["falta"], [])

    def test_agua_sem_dados_nao_inventa(self):
        x = avac(f="agua", e={}, R={"ac": {"kWt": 100}})
        self.assertEqual(len(x["falta"]), 4)
        self.assertIsNone(x["Dmm"])          # NaN vira null no JSON: nada de valor de fábrica

    def test_complementos(self):
        x = avac(f="ext", e={"ext": {"volPisc": 90, "renov": 6, "bordaM": 10, "bordaVaz": 5, "bordaLm": 50, "saunaVol": 12, "saunaKwM3": 1,
                                     "saunaTrocas": 6, "coifaM": 2, "coifaVaz": 1500, "coifaVel": 5}}, R={})
        self.assertEqual((x["filt"], x["borda"], x["bombaTotal"], x["tanque"], x["sauna"], x["saunaVent"], x["chur"]), (15, 50, 65, 0.5, 12, 72, 3000))
        self.assertIsNone(avac(f="ext", e={}, R={})["sauna"])

    def test_abas_no_modulo(self):
        t = (RAIZ / "sistema" / "physis-avac.js").read_text(encoding="utf-8")
        for k in ('["agua", "Água gelada"]', '["sauna", "Sauna"]', '["tubos", "Tubulações', "agua:telaAgua", "sauna:telaSauna", "tubos:telaTubos",
                  "telaVentExtras(e, R)", "telaPiscinaExtras(e, R)", "Dutos e ventiladores", "Aquecimento solar"):
            self.assertIn(k, t)
        self.assertNotIn('"extras", "Piscina (filtragem e borda), sauna e churrasqueira"', t, "churrasqueira na exaustão, sauna separada")

    def test_dutos_por_exaustao_e_ar_exterior_e_quadro(self):
        js = """global.window=global;global.calcLer=()=>({});global.calcGravar=()=>{};global.esc=s=>String(s);global.n2=(v,c)=>v.toFixed(c);global.ui={};global.el=()=>null;
require(%s);const e=AVAC.padrao();e.vent.churr=[{id:'c1',n:'Ch',coifaM:2,vazM:1500}];e.vent.arExt=[{id:'a1',n:'AE',vazao:800}];
e.dutos.sistemas.push({nome:'D ch',fonte:'churr:c1',vazao:0,vel:6,reto:20,equiv:10,local:80,altura:300,tipo:''});e.dutos.sistemas.push({nome:'D ae',fonte:'arext:a1',vazao:0});
e.ext={saunaVol:12,saunaKwM3:1};e.tubos=[{n:'AQ',tipo:'quente',vazao:1.2,vmax:2,di:30}];const R=AVAC.calcular(e);
console.log(JSON.stringify({ch:R.vent.churr,ae:R.vent.arExt,d:R.dutos.sis.slice(-2).map(s=>s.vazao),sauna:R.quadro.circ.find(c=>c.id==='sauna'),tub:AVAC.calcTubos(e)}));"""
        r = subprocess.run([NODE, "-e", js % json.dumps(str(RAIZ / "sistema" / "physis-avac.js"))], capture_output=True, text=True, timeout=30)
        x = json.loads(r.stdout)
        self.assertEqual((x["ch"], x["ae"], x["d"]), (3000, 800, [3000, 800]))
        self.assertEqual((x["sauna"]["kw"], x["sauna"]["s"]), (12, 4), "fiação da sauna selecionada no quadro (NBR 5410)")
        self.assertEqual(x["tub"][0]["situacao"], "ok")


class Sprinkler(unittest.TestCase):
    def test_modulo_no_planejador(self):
        t = (RAIZ / "modulos" / "planejador" / "planejador-physis.html").read_text(encoding="utf-8")
        self.assertIn("id: 'sprinkler'", t)
        self.assertIn("NBR 10897", t)
        self.assertIn("padrao: { risco: '', area: null, dens: null, aop: null, cob: null, tempo: null", t, "sem valores de fábrica")
