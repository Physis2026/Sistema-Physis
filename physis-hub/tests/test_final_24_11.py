"""Rodada final de 24/11/2026: pressão e NPSH dos circuitos, croqui → IFC, OCR, rede de água (EPANET) e modelagens do AVAC."""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
STUB = "global.window=global;global.calcLer=()=>({});global.calcGravar=()=>{};global.esc=s=>String(s);global.n2=(v,c)=>v.toFixed(c);global.ui={};global.el=()=>null;"


def node(js):
    return json.loads(subprocess.run([NODE, "-e", STUB + js], capture_output=True, text=True, timeout=60).stdout)


@unittest.skipUnless(NODE, "node não instalado")
class Circuitos(unittest.TestCase):
    def test_agua_e_npsh(self):
        x = node("require(%s);const p=AVAC.propAgua(7),q=AVAC.propAgua(70);const c=AVAC.calcCircuito({T:7,L:200,di:102.3,rug:0.046,K:15,dPeq:80,Psuc:250,npshr:3},60.5);"
                 "const s=AVAC.calcCircuito({tipo:'aberto',T:70,L:60,di:26,rug:0.0015,K:10,dPeq:20,dz:12,Psuc:101.3,npshr:7.5},1.2);"
                 "console.log(JSON.stringify({p,q,c,s,f:AVAC.calcCircuito({},10).falta.length,m:AVAC.modelagensDe(AVAC.padrao(),AVAC.calcular(AVAC.padrao())).map(m=>m.programa)}))"
                 % json.dumps(str(RAIZ / "sistema" / "physis-avac.js")))
        self.assertAlmostEqual(x["p"]["mu"], 1.43e-3, delta=0.03e-3)        # tabelas de água: 7 °C
        self.assertAlmostEqual(x["q"]["pv"], 31.2, delta=0.3)              # 70 °C: ~31,2 kPa
        self.assertAlmostEqual(x["c"]["dPtot"], x["c"]["dPat"] + x["c"]["dPloc"] + 80, places=6)
        self.assertFalse(x["c"]["aberto"])
        self.assertIn("cavitação", x["s"]["alerta"], "água a 70 °C com NPSHr alto")
        self.assertEqual(x["f"], 4)
        self.assertIn("EPANET", x["m"]); self.assertIn("EnergyPlus + OpenStudio", x["m"])

    def test_croqui_para_ifc(self):
        r = {"escala_m_por_px": 0.01, "paredes_m": [[0, 0], [10, 0], [10, 6], [0, 6]],
             "ambientes": [{"nome": "Sala", "area_m2": 30, "laco_m": [[0.1, 0.1], [5, 0.1], [5, 5.9], [0.1, 5.9]]}]}
        x = node("require(%s);require(%s);const t=PhysisCroqui.ifc(%s,2.8,'t');console.log(JSON.stringify({e:PhysisIFC.espacos(t),l:PhysisIFC.ler(t).elementos_por_tipo}))"
                 % (json.dumps(str(RAIZ / "sistema" / "physis-croqui.js")), json.dumps(str(RAIZ / "sistema" / "physis-ifc.js")), json.dumps(r)))
        self.assertEqual((x["e"][0]["nome"], x["e"][0]["area_m2"], x["e"][0]["altura_m"]), ("Sala", 30, 2.8))
        self.assertEqual(x["l"], {"IFCWALL": 1})


class Rede(unittest.TestCase):
    def test_epanet(self):
        spec = importlib.util.spec_from_file_location("rede_agua", RAIZ / "ferramentas" / "rede_agua.py")
        ra = importlib.util.module_from_spec(spec); spec.loader.exec_module(ra)
        d = 0.0009
        vias = {"features": [{"geometry": {"type": "LineString", "coordinates": [[-43.18 + i * d, -22.5 + j * d] for j in range(3)]}, "properties": {"tipo": "via", "classe": "residential"}} for i in range(3)]
                + [{"geometry": {"type": "LineString", "coordinates": [[-43.18 + j * d, -22.5 + i * d] for j in range(3)]}, "properties": {"tipo": "via", "classe": "residential"}} for i in range(3)]}
        rel = {"nx": 10, "ny": 10, "x0": -43.181, "y0": -22.501, "cel": 0.0005, "sem": -9999, "z": [800.0] * 100}
        rede = ra.montar(vias, rel, 1000, 150, 1.2, 1.5, 140, {"residential": 75}, (-43.1812, -22.5012, 840))
        self.assertEqual(len(rede["nos"]), 9)
        self.assertAlmostEqual(rede["q_max_Ls"], 1000 * 150 / 86400 * 1.8, places=6)
        txt = ra.inp(rede)
        self.assertIn("[JUNCTIONS]", txt); self.assertIn("Headloss H-W", txt)
        self.assertEqual(ra.main(["--vias", "x", "--relevo", "y", "--populacao", "1", "--per-capita", "1", "--reservatorio=0,0,0"]), 2, "sem premissas não gera")
        try:
            import wntr  # noqa: F401
        except ImportError:
            return
        p = Path(tempfile.mkdtemp()) / "r.inp"; p.write_text(txt, encoding="utf-8")
        import wntr
        wn = wntr.network.WaterNetworkModel(str(p)); res = wntr.sim.EpanetSimulator(wn).run_sim()
        self.assertGreater(res.node["pressure"].iloc[0][wn.junction_name_list].min(), 30)


class Ocr(unittest.TestCase):
    def test_ocr(self):
        from physis_hub import estermic_servidor as es
        exe = es.achar_programa(["tesseract"], ["C:/Program Files/Tesseract-OCR/tesseract.exe", "C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"], "PHYSIS_TESSERACT")
        if not exe:
            self.assertFalse(es.ocr(b"x")["ok"]); return
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            self.skipTest("Pillow não instalado")
        im = Image.new("RGB", (400, 120), "white"); dr = ImageDraw.Draw(im)
        try:
            fn = ImageFont.truetype("DejaVuSans.ttf", 48)
        except OSError:
            self.skipTest("fonte de teste ausente")
        dr.text((20, 30), "QUARTO", fill="black", font=fn)
        p = Path(tempfile.mkdtemp()) / "q.png"; im.save(p)
        self.assertIn("QUARTO", [w["t"] for w in es.ocr(p.read_bytes())["palavras"]])


class Simular(unittest.TestCase):
    def test_suporte_calculix_ou_referencia(self):
        from physis_hub import estermic_servidor as es
        r = es.simular({"tipo": "suporte", "vao_m": 2, "carga_kg": 500, "b_mm": 50, "h_mm": 100, "E_GPa": 200})
        self.assertTrue(r["ok"]); self.assertAlmostEqual(r["referencia"]["flecha_mm"], 0.981, places=3)
        if r["programa"]:
            self.assertLess(abs(r["flecha_mm"] - 0.981) / 0.981, 0.03)
        self.assertFalse(es.simular({"tipo": "suporte"})["ok"], "sem valores digitados não simula")
