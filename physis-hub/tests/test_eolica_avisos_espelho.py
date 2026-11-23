"""Espelho da eólica (vento.py × sistema/physis-turbinas.js): avisos e viabilidade nas entradas-limite.
Ciclo de auditoria 2026-11-22: terreno desconhecido, terreno rugoso, Cp <= 0, diâmetro 0 e VPL negativo."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from physis_hub import vento

RAIZ = Path(__file__).resolve().parents[2]
JS = RAIZ / "sistema" / "physis-turbinas.js"
BASE = dict(diametro=3.7, cp=0.30, v_in=3, v_nom=11, v_out=25, altura_cubo=12, v_ref=5.5, h_ref=10, altitude=20, temperatura=27, perdas=10)
CASOS = {
    "base": dict(BASE),
    "terreno_desconhecido": dict(BASE, terreno="suburbano"),
    "urbano": dict(BASE, terreno="urbano"),
    "cp_negativo": dict(BASE, cp=-1),
    "diametro_zero": dict(BASE, diametro=0),
    "vpl_negativo": dict(BASE, custo=60000, tarifa=0.9),
}


class Avisos(unittest.TestCase):
    def test_python(self):
        r = {k: vento.eolica(v) for k, v in CASOS.items()}
        self.assertEqual(r["base"]["avisos"], [])
        self.assertTrue(any("não reconhecido" in a for a in r["terreno_desconhecido"]["avisos"]))
        self.assertTrue(any("rugoso" in a for a in r["urbano"]["avisos"]))
        self.assertTrue(any("Cp zero" in a for a in r["cp_negativo"]["avisos"]))
        self.assertTrue(any("Diâmetro" in a for a in r["diametro_zero"]["avisos"]))
        self.assertLess(r["vpl_negativo"]["invest"]["vpl"], 0)
        self.assertNotEqual(r["vpl_negativo"]["viabilidade"], "viavel")

    @unittest.skipUnless(shutil.which("node"), "sem Node.js nesta máquina")
    def test_js_igual_python(self):
        roteiro = ("const fs=require('fs'),vm=require('vm');const a=JSON.parse(fs.readFileSync(process.argv[process.argv.length-1],'utf8'));"
                   "global.window=global;global.document={addEventListener(){},querySelector(){return null},querySelectorAll(){return []}};"
                   "global.localStorage={getItem(){return null},setItem(){}};"
                   "const tx=fs.readFileSync(a.painel,'utf8'),i0=tx.indexOf('function analiseInvest(');let i=tx.indexOf('{',i0),n=0;"
                   "for(;i<tx.length;i++){if(tx[i]==='{')n++;else if(tx[i]==='}'&&--n===0)break;}"
                   "vm.runInThisContext(tx.slice(i0,i+1)+';window.analiseInvest=analiseInvest;');"
                   "vm.runInThisContext(fs.readFileSync(a.solar,'utf8'));vm.runInThisContext(fs.readFileSync(a.js,'utf8'));const o={};"
                   "for(const [k,p] of Object.entries(a.casos)){const r=window.TURBINAS.eolica(p);o[k]={avisos:r.avisos,viabilidade:r.viabilidade,aep:r.aep_kwh};}"
                   "process.stdout.write(JSON.stringify(o));")
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "e.json"
            arq.write_text(json.dumps({"js": str(JS), "solar": str(RAIZ / "sistema" / "physis-solar.js"), "painel": str(RAIZ / "physis-hub" / "web" / "painel.html"), "casos": CASOS}), encoding="utf-8")
            sai = subprocess.run(["node", "-e", roteiro, str(arq)], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(sai.returncode, 0, sai.stderr)
        js = json.loads(sai.stdout)
        for k, p in CASOS.items():
            py = vento.eolica(p)
            self.assertEqual(js[k]["avisos"], py["avisos"], k)
            self.assertEqual(js[k]["viabilidade"], py["viabilidade"], k)
            self.assertAlmostEqual(js[k]["aep"], py["aep_kwh"], delta=1e-6 * max(1.0, py["aep_kwh"]), msg=k)


if __name__ == "__main__":
    unittest.main()
