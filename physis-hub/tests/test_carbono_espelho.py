"""Espelho do Carbono (regra 4): physis-carbono.js e physis_hub/carbono.py dão as mesmas emissões evitadas.

Protege (ruptura R5 do mapa de variáveis, 15/11/2026):
1. As evitadas têm as mesmas parcelas nos dois lados (solar, biogás, reciclagem, reúso).
2. Mesma entrada → mesmo resultado: com Node.js na máquina, o JS roda de verdade e é comparado ao Python;
   sem Node, o teste pula (o Windows da versão 0 não tem Node; o servidor Linux pode ter).
3. Contas de mesa: o biogás no lugar do GLP vale o GLP que deixa de queimar (premissas biogas.pci e glp.pci);
   a reciclagem vale o aterro evitado menos a reciclagem, nunca negativa.
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from physis_hub import carbono as cb

RAIZ = Path(__file__).resolve().parents[2]
JS = RAIZ / "sistema" / "physis-carbono.js"
NO_REPO = JS.is_file() and cb.BASE.is_file() and cb.PREMISSAS.is_file()

ESTADO = {"v": 2, "kwh": "24000", "solar_kwh": "9000", "estac": [], "rede": {"fator": "nucleo"}}
CTX = {"rc": [{"tipo": "papel", "qtd": "200", "un": "kg_mes", "rota": "reciclagem"},
              {"tipo": "pet", "qtd": "50", "un": "kg_mes", "rota": "reversa"},
              {"tipo": "alimentos", "qtd": "300", "un": "kg_mes", "rota": "biodigestor"},
              {"tipo": "rejeito", "qtd": "100", "un": "kg_mes", "rota": "aterro"}],
       "esgoto": {"pessoas": 0, "reuso_m3_dia": 2}}


def perto(tc, a, b, tol=1e-6):
    tc.assertTrue(abs(a - b) <= tol * max(abs(b), 1.0), f"{a} difere de {b}")


@unittest.skipUnless(NO_REPO, "só no repositório")
class EspelhoCarbono(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.F = cb.carregar()
        cls.js = JS.read_text(encoding="utf-8")

    def test_mesmas_parcelas_das_evitadas(self):
        m = re.search(r"const evit = \{(.*?)\};", self.js)
        self.assertIsNotNone(m, "linha das evitadas mudou no JS")
        chaves_js = set(re.findall(r"(\w+):", m.group(1)))
        r = cb.calcular(ESTADO, CTX, self.F)
        self.assertEqual(set(r["evitadas"]), chaves_js)
        perto(self, r["evitadas_t"], sum(r["evitadas"].values()))

    def test_biogas_vale_o_glp_que_deixa_de_queimar(self):
        r = cb.calcular(ESTADO, dict(CTX, biogas={"biogas_m3_dia": 10, "fonte": "Planejador"}), self.F)
        kg_glp = 10 * 365 * cb.premissa("biogas.pci") / cb.premissa("glp.pci")
        glp = cb.calcular({"v": 2, "estac": [{"comb": "glp", "qtd": str(kg_glp)}]}, {}, self.F)
        perto(self, r["evitadas"]["biogas"], glp["e1"])
        perto(self, r["biogas_m3"], 3650)
        # sem o registro: a soma do plano (rota biodigestor) com a premissa residuos.biogas_por_kg
        r2 = cb.calcular(ESTADO, CTX, self.F)
        perto(self, r2["biogas_m3"], 300 * 12 * cb.premissa("residuos.biogas_por_kg")["alimentos"])

    def test_reciclagem_e_aterro_evitado(self):
        r = cb.calcular(ESTADO, CTX, self.F)
        gw = cb.gwp_de(self.F, self.F["gwp"]["padrao"])
        esperado = 0.0
        for tipo, kg in (("papel", 200), ("pet", 50)):
            t = kg * 12 / 1000
            esperado += max(0.0, cb.tco2e(cb.residuo(self.F, tipo, t, "aterro"), gw) - cb.tco2e(cb.residuo(self.F, tipo, t, "reciclagem"), gw))
        perto(self, r["evitadas"]["reciclagem"], esperado)
        self.assertGreaterEqual(r["evitadas"]["reciclagem"], 0.0)

    def test_padroes_do_js_iguais_as_premissas(self):
        prem = cb.premissa("residuos.biogas_por_kg")
        m = re.search(r"const BIOG_PAD = \{([^}]*)\}", self.js)
        self.assertIsNotNone(m, "BIOG_PAD sumiu do JS")
        js_pad = {k: float(v) for k, v in re.findall(r"(\w+):([0-9.]+)", m.group(1))}
        self.assertEqual(js_pad, cb.BIOG_PAD)
        for k, v in cb.BIOG_PAD.items():
            self.assertEqual(prem[k], v, k)
        pcis = dict(re.findall(r'PREM\("((?:biogas|glp)\.pci)", ([0-9.]+)\)', self.js))
        self.assertEqual({k: float(v) for k, v in pcis.items()}, cb.PCI_PAD)
        self.assertEqual(cb.premissa("biogas.pci"), cb.PCI_PAD["biogas.pci"])
        self.assertEqual(cb.premissa("glp.pci"), cb.PCI_PAD["glp.pci"])

    @unittest.skipUnless(shutil.which("node"), "sem Node.js nesta máquina")
    def test_js_e_python_mesma_entrada_mesmo_resultado(self):
        script = (
            "const fs=require('fs'),vm=require('vm');const a=JSON.parse(fs.readFileSync(process.argv[process.argv.length-1],'utf8'));"
            "global.window=global;global.document={addEventListener(){},getElementById(){return null;}};"
            "global.PHYSIS_FATORES_EMISSAO=a.F;vm.runInThisContext(fs.readFileSync(a.js,'utf8'));"
            "const R=window.PhysisCarbono.calcular(a.estado,a.ctx,a.F);"
            "process.stdout.write(JSON.stringify({evitadas:R.evitadas,e1:R.e1,e2:R.e2_loc,e3:R.e3}));")
        with tempfile.TemporaryDirectory() as d:
            arq = Path(d) / "entrada.json"
            arq.write_text(json.dumps({"F": self.F, "estado": ESTADO, "ctx": CTX, "js": str(JS)}), encoding="utf-8")
            sai = subprocess.run(["node", "-e", script, str(arq)], capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(sai.returncode, 0, sai.stderr)
        js = json.loads(sai.stdout)
        py = cb.calcular(ESTADO, CTX, self.F)
        for k, v in js["evitadas"].items():
            perto(self, py["evitadas"][k], v, 1e-9)
        perto(self, py["e1"], js["e1"], 1e-9)
        perto(self, py["e2_loc"], js["e2"], 1e-9)
        perto(self, py["e3"], js["e3"], 1e-9)


if __name__ == "__main__":
    unittest.main()
