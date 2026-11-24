"""Bot de modelagem: análises por objeto, perguntas quando falta dado e flambagem conferida (24/11/2026)."""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from physis_hub import ferramentas_simulacao as fs

MOD = Path(__file__).resolve().parents[2] / "sistema" / "physis-modelador.js"
NODE = shutil.which("node")
JS = """global.window={localStorage:{getItem:()=>null}};window.document={readyState:'complete',querySelectorAll:()=>[],documentElement:{}};
require(%s);const M=window.PhysisModelador;const a=JSON.parse(process.argv[1]);let out;
if(a.f==='peca'){const r=M.gerar.peca(a.t,'pt');out={calc:r.calc,inp:r.inp,ok:M.checar(r.malha).ok};}
else if(a.f==='perg'){out=M.perguntas(a.q,a.t,'pt');}else if(a.f==='ent'){out=M.entender(a.t);}else{out=M.analises(a.q,'pt');}
console.log(JSON.stringify(out));"""


def js(**a):
    r = subprocess.run([NODE, "-e", JS % json.dumps(str(MOD)), json.dumps(a)], capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout)


@unittest.skipUnless(NODE, "node não instalado")
class Modelador(unittest.TestCase):
    def test_entende_peca_longa_e_calha(self):
        self.assertEqual(js(f="ent", t="imprimir uma haste longa de 300 mm"), "peca")
        self.assertEqual(js(f="ent", t="gerar uma calha"), "agua")

    def test_pergunta_quando_falta(self):
        p = js(f="perg", q="peca", t="imprimir uma haste de 300 mm")
        self.assertTrue(any("E do material" in x for x in p))
        self.assertTrue(any("presa" in x for x in p))
        self.assertEqual(len(js(f="perg", q="", t="faça algo")), 4)
        self.assertEqual(js(f="perg", q="peca", t="haste de 300 mm diâmetro 8 mm E 3,5 GPa engastada e livre carga 10 N"), [])

    def test_analises(self):
        self.assertIn("OpenFOAM", json.dumps(js(f="an", q="agua"), ensure_ascii=False))
        self.assertIn("Flambagem", json.dumps(js(f="an", q="peca"), ensure_ascii=False))

    def test_sem_E_fica_marcador(self):
        r = js(f="peca", t="haste de 300 mm diâmetro 8 mm engastada e livre")
        self.assertIn("[MARCADOR]", json.dumps(r["calc"], ensure_ascii=False))
        self.assertIn("[MARCADOR_E_MPa]", r["inp"])

    def test_euler_bate_com_calculix(self):
        casos = [("haste de 300 mm diâmetro 8 mm E 3,5 GPa engastada e livre", 19.3),
                 ("haste de 300 mm diâmetro 8 mm E 3,5 GPa apoiada", 77.2),
                 ("haste de 300 mm diâmetro 8 mm E 3,5 GPa engastada nas duas", 308.7),
                 ("barra de 500 mm 20 x 4 mm E 2 GPa apoiada", 8.4)]
        for t, euler in casos:
            r = js(f="peca", t=t)
            self.assertTrue(r["ok"])
            txt = json.dumps(r["calc"], ensure_ascii=False)
            self.assertIn(f"{euler:.1f}".replace(".", ","), txt)
            if shutil.which("ccx"):
                d = Path(tempfile.mkdtemp())
                (d / "h.inp").write_text(r["inp"].replace("[MARCADOR_POISSON]", "0.35"), encoding="utf-8")
                subprocess.run(["ccx", "-i", "h"], cwd=d, capture_output=True, timeout=60)
                f = float(re.findall(r"\n\s+1\s+(\S+)", (d / "h.dat").read_text().split("B U C K")[1])[0])
                self.assertLess(abs(f - euler) / euler, 0.05, t)


class Catalogo(unittest.TestCase):
    def test_catalogo(self):
        s = fs.situacao(which=lambda x: "/usr/bin/ccx" if x == "ccx" else None)
        ids = {x["id"]: x for x in s}
        self.assertTrue(ids["calculix"]["instalado"])
        self.assertFalse(ids["openfoam"]["instalado"])
        self.assertNotIn("orca", ids)
        self.assertTrue(all(x["aberto"] for x in s))
        self.assertIn("qelectrotech", ids)
        self.assertEqual(len({x["area"] for x in s}), 6)
        self.assertIn("bonsai", ids)
