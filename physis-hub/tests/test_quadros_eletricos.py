"""Aba Quadros elétricos (sistema/physis-quadros.js): um quadro por módulo com o motor do QF-AVAC; Ar-condicionado e Piscina
vêm do AVAC; a aba existe na plataforma e a Caixinha aponta para ela."""
import json, shutil, subprocess, unittest
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
JS = r"""
globalThis.window=globalThis; globalThis.esc=s=>String(s); globalThis.n2=(v,c)=>String(v); globalThis.numBr=v=>String(v); globalThis.ui={}; globalThis.el=()=>null;
const st={}; globalThis.calcLer=k=>st[k]||{}; globalThis.calcGravar=(k,v)=>{st[k]=v};
require(%s); require(%s);
st.avac={e:window.AVAC.padrao()};
const c=[{nome:'Bomba',tipo:'bomba',kw:3,qtd:1,fases:'RST',comp:30},{nome:'AC',tipo:'ar_condicionado'}];
const r=window.QUADROS.calcQuadro(c), R=window.AVAC.calcular(st.avac.e);
st.quadros={q:{rural:{circ:c}}};
const h=window.telaQuadros();
console.log(JSON.stringify({bomba:[r.circ[0].in,r.circ[0].s,r.circ[0].situacao], ac:r.circ[1].kw, kWe:R.ac.kWe, h1:(h.match(/<h1/g)||[]).length, qgbt:h.includes('QGBT')}));
"""

@unittest.skipUnless(NODE, "sem node")
class Quadros(unittest.TestCase):
    def test_motor_e_avac(self):
        js = JS % (json.dumps(str(RAIZ / "sistema" / "physis-avac.js")), json.dumps(str(RAIZ / "sistema" / "physis-quadros.js")))
        r = subprocess.run([NODE, "-e", js], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(d["bomba"], [10, 2.5, "ok"])
        self.assertAlmostEqual(d["ac"], d["kWe"], places=6)     # Ar-condicionado vem do AVAC
        self.assertEqual(d["h1"], 1); self.assertTrue(d["qgbt"])

    def test_aba_na_plataforma(self):
        h = (RAIZ / "physis-hub" / "web" / "painel.html").read_text(encoding="utf-8")
        self.assertIn('["quadros","Quadros elétricos"]', h)
        self.assertIn('id="mod-quadros"', h)
        self.assertIn("quadros: () => typeof telaQuadros", h)

if __name__ == "__main__":
    unittest.main()
