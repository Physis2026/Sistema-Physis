"""CFD de duto (OpenFOAM, Linux ou WSL), modelo 3D .glb da planta e bot de modelos dos fabricantes (24/11/2026)."""
import json
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

from physis_hub import estermic_servidor as es, mv_modelos
from physis_hub.mv import MV

RAIZ = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")


class Cfd(unittest.TestCase):
    def test_duto(self):
        r = es.simular({"tipo": "cfd-duto", "comprimento_m": 5, "largura_m": 0.4, "altura_m": 0.3, "vazao_m3h": 2000, "temp_C": 20})
        if not r["ok"] and "OpenFOAM" in str(r.get("erro")):   # WSL sem distribuição Linux (PC de produção)
            self.skipTest("OpenFOAM presente mas não roda: " + str(r["erro"])[:120])
        self.assertTrue(r["ok"], r)
        self.assertAlmostEqual(r["referencia"]["velocidade_m_s"], 2000 / 3600 / 0.12, places=6)
        if r.get("programa"):                      # com OpenFOAM: perto de Darcy-Weisbach
            self.assertLess(abs(r["dp_cfd_Pa"] - r["referencia"]["dp_darcy_Pa"]) / r["referencia"]["dp_darcy_Pa"], 0.25)
        self.assertFalse(es.simular({"tipo": "cfd-duto"})["ok"])


@unittest.skipUnless(NODE, "node não instalado")
class Glb(unittest.TestCase):
    def test_glb_valido(self):
        js = ("global.window=global;require(%s);const r={escala_m_por_px:0.01,paredes_m:[[0,0],[10,0],[10,6],[0,6]],ambientes:[{nome:'Sala',area_m2:30,laco_m:[[0.1,0.1],[6,0.1],[6,3],[4,3],[4,5.9],[0.1,5.9]]}]};"
              "process.stdout.write(Buffer.from(PhysisCroqui.glb(r,2.8,0.15)).toString('base64'))") % json.dumps(str(RAIZ / "sistema" / "physis-croqui.js"))
        import base64
        b = base64.b64decode(subprocess.run([NODE, "-e", js], capture_output=True, text=True, timeout=30).stdout)
        magic, ver, total = struct.unpack("<III", b[:12])
        self.assertEqual((magic, ver, total), (0x46546C67, 2, len(b)))
        n = struct.unpack("<I", b[12:16])[0]; g = json.loads(b[20:20 + n])
        self.assertEqual(len(g["meshes"][0]["primitives"]), 2)
        self.assertAlmostEqual(g["accessors"][0]["max"][1], 0.0, places=6)      # piso no chão
        self.assertAlmostEqual(max(a.get("max", [0, 0, 0])[1] for a in g["accessors"]), 2.8, places=4)


class Modelos(unittest.TestCase):
    def test_catalogo_vira_rascunho(self):
        d = Path(tempfile.mkdtemp()); (d / "cat.txt").write_text("Linha Daikin FTKC12TVL e RXF35. Carrier 42LUCA12C5. NBR 16401.", encoding="utf-8")
        mv = MV(":memory:"); r = mv_modelos.bot_modelos(mv, d, d / "saida")
        self.assertEqual((r["arquivos_lidos"], r["fabricantes_com_modelos"], r["rascunhos_novos"]), (1, 2, 2))
        csvt = (d / "saida" / "modelos_propostos.csv").read_text(encoding="utf-8-sig")
        self.assertIn("Daikin;", csvt); self.assertNotIn("NBR", csvt.split("\n", 1)[1].split(";")[2:3][0] if ";" in csvt else "")
        self.assertEqual(mv_modelos.bot_modelos(mv, d, d / "saida")["rascunhos_novos"], 0, "não repete o pedido")
