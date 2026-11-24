"""IFC da arquitetura → áreas dos espaços e preenchimento inicial do cálculo (24/11/2026)."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
IFC = "\n".join(["ISO-10303-21;", "HEADER;", "FILE_SCHEMA(('IFC4'));", "ENDSEC;", "DATA;", "#1=IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.);",
    "#2=IFCSPACE('g1',$,'101','',$,$,$,'Sala de reunião',.ELEMENT.,.INTERNAL.,$);", "#3=IFCQUANTITYAREA('NetFloorArea',$,$,24.5,$);",
    "#4=IFCELEMENTQUANTITY('g2',$,'Q',$,$,(#3));", "#5=IFCRELDEFINESBYPROPERTIES('g3',$,$,$,(#2),#4);",
    "#10=IFCCARTESIANPOINT((0.,0.));", "#11=IFCAXIS2PLACEMENT2D(#10,$);", "#12=IFCRECTANGLEPROFILEDEF(.AREA.,$,#11,4000.,5000.);",
    "#13=IFCEXTRUDEDAREASOLID(#12,$,$,2800.);", "#14=IFCSHAPEREPRESENTATION($,'Body','SweptSolid',(#13));", "#15=IFCPRODUCTDEFINITIONSHAPE($,$,(#14));",
    "#16=IFCSPACE('g4',$,'102','',$,$,#15,'Garagem',.ELEMENT.,.INTERNAL.,$);",
    "#20=IFCPROPERTYSINGLEVALUE('NetPlannedArea',$,IFCAREAMEASURE(8.25),$);", "#21=IFCPROPERTYSET('g5',$,'P',$,(#20));",
    "#22=IFCSPACE('g6',$,'103','',$,$,$,'Banheiro',.ELEMENT.,.INTERNAL.,$);", "#23=IFCRELDEFINESBYPROPERTIES('g7',$,$,$,(#22),#21);",
    "#24=IFCSPACE('g8',$,'104','',$,$,$,'Depósito sem área',.ELEMENT.,.INTERNAL.,$);", "ENDSEC;", "END-ISO-10303-21;"])
JS = """global.window=global;require(%s);require(%s);require(%s);const esp=PhysisIFC.espacos(%s);
const e=ESTERMIC.preencherDoIfc(AVAC.padrao(),esp,'t.ifc');console.log(JSON.stringify({esp,amb:e.ac.amb,gar:e.vent.garArea,banh:e.tipologias.lista[0].banh,o:e.origemIfc,R:AVAC.calcular(e).ac.amb.length}));"""


@unittest.skipUnless(NODE, "node não instalado")
class AreasDoIfc(unittest.TestCase):
    def test_areas_e_preenchimento(self):
        g = globals()
        stub = "global.calcLer=()=>({});global.calcGravar=()=>{};global.esc=s=>String(s);global.n2=(v,c)=>v.toFixed(c);global.ui={};global.el=()=>null;"
        js = stub + JS % (json.dumps(str(RAIZ / "sistema" / "physis-ifc.js")), json.dumps(str(RAIZ / "sistema" / "physis-avac.js")),
                          json.dumps(str(RAIZ / "modulos" / "estermic" / "estermic-avac.js")), json.dumps(IFC))
        r = subprocess.run([NODE, "-e", js], capture_output=True, text=True, timeout=30)
        x = json.loads(r.stdout)
        self.assertEqual([(s["nome_longo"], s["area_m2"], s["fonte"]) for s in x["esp"]],
                         [("Sala de reunião", 24.5, "quantidade do IFC"), ("Garagem", 20, "geometria do IFC"), ("Banheiro", 8.25, "propriedade do IFC"),
                          ("Depósito sem área", None, "sem área no IFC")])
        self.assertEqual([(a["n"], a["area"]) for a in x["amb"]], [("Sala de reunião", 24.5)])
        self.assertEqual((x["gar"], x["banh"]), (20, 1))
        self.assertEqual(x["o"]["sem_area"], ["Depósito sem área"], "sem área não é inventada")
        self.assertEqual(x["R"], 1)


@unittest.skipUnless(NODE, "node não instalado")
class AreasDoPdf(unittest.TestCase):
    def test_rotulos(self):
        itens = [{"s": "SALA DE REUNIAO", "x": 120, "y": 170, "p": 1}, {"s": "24,50 m2", "x": 130, "y": 155, "p": 1},
                 {"s": "GARAGEM", "x": 400, "y": 170, "p": 1}, {"s": "A = 80,00 m²", "x": 405, "y": 155, "p": 1},
                 {"s": "BANHEIRO 3,20 m2", "x": 600, "y": 170, "p": 1}, {"s": "ESCALA 1:100", "x": 10, "y": 10, "p": 1}]
        js = "global.window=global;require(%s);console.log(JSON.stringify(ESTERMIC.espacosDoTexto(%s)))" % (
            json.dumps(str(RAIZ / "modulos" / "estermic" / "estermic-avac.js")), json.dumps(itens))
        x = json.loads(subprocess.run([NODE, "-e", js], capture_output=True, text=True, timeout=30).stdout)
        self.assertEqual([(e["nome"], e["area_m2"]) for e in x], [("SALA DE REUNIAO", 24.5), ("GARAGEM", 80), ("BANHEIRO", 3.2)])


@unittest.skipUnless(NODE, "node não instalado")
class CasaPhysisECroqui(unittest.TestCase):
    def rodar(self, js):
        r = subprocess.run([NODE, "-e", js], capture_output=True, text=True, timeout=60)
        return json.loads(r.stdout)

    def test_ifc_do_gemeo_da_casa(self):
        stub = "global.window=global;global.calcLer=()=>({});global.calcGravar=()=>{};global.esc=s=>String(s);global.n2=(v,c)=>v.toFixed(c);global.ui={};global.el=()=>null;"
        js = stub + "require(%s);require(%s);require(%s);const esp=PhysisIFC.espacos(require('fs').readFileSync(%s,'utf8'));const e=ESTERMIC.preencherDoIfc(AVAC.padrao(),esp,'casa');console.log(JSON.stringify({n:esp.length,pisc:e.piscina.area,gar:e.vent.garArea,amb:e.ac.amb.length}))" % (
            json.dumps(str(RAIZ / "sistema" / "physis-ifc.js")), json.dumps(str(RAIZ / "sistema" / "physis-avac.js")),
            json.dumps(str(RAIZ / "modulos" / "estermic" / "estermic-avac.js")), json.dumps(str(RAIZ / "modulos" / "planejador" / "gemeo" / "casa-physis-rev0.ifc")))
        x = self.rodar(js)
        self.assertEqual(x["n"], 31)
        self.assertEqual(x["pisc"], 24, "só a piscina (lago e tanque de peixes não)")
        self.assertEqual(x["gar"], 50, "vagas da Rua H; acesso e corredor não contam como garagem")
        self.assertGreater(x["amb"], 5)

    def test_retificar_rascunho_torto(self):
        js = ("global.window=global;require(%s);const P=PhysisCroqui;let l=[];const R=(x,y)=>[x+Math.sin(x*7+y)*3,y+Math.cos(x+y*5)*3];"
              "for(let x=0;x<=600;x+=20)l.push(R(x,0));for(let y=0;y<=400;y+=20)l.push(R(600,y));for(let x=600;x>=0;x-=20)l.push(R(x,400));for(let y=400;y>=0;y-=20)l.push(R(0,y));"
              "const r=P.retificar(l);let a=0;for(let i=0;i<r.length;i++){const p=r[i],q=r[(i+1)%%r.length];a+=p[0]*q[1]-q[0]*p[1];}console.log(JSON.stringify({n:r.length,a:Math.abs(a)/2}))") % json.dumps(str(RAIZ / "sistema" / "physis-croqui.js"))
        x = self.rodar(js)
        self.assertEqual(x["n"], 4, "rascunho torto vira retângulo")
        self.assertLess(abs(x["a"] - 240000) / 240000, 0.02)
