"""Programas do PC ligados à plataforma (25/11/2026: "FreeCAD, QGIS, Blender e os demais devem fazer cálculos pela plataforma").

Cada RECEITA é um uso pronto de um programa aberto instalado no servidor, rodado SEM tela (modo de linha de comando), com
entrada conferida e saída guardada: a equipe envia o arquivo pela página /programas (ou pela API), o servidor roda o
programa numa pasta só daquele trabalho, com tempo máximo, e devolve o resumo e os arquivos gerados.

Nada de comando livre: só as receitas abaixo, cada uma com a lista fixa de argumentos; parâmetro só de lista fechada ou
número com faixa. Arquivo .zip é aberto conferindo cada caminho (nada sai da pasta do trabalho).
Programa sem modo de linha de comando (QElectroTech, Avogadro, SAM) não tem receita: segue só "abrir no PC".
Serviços (Mosquitto, PostgreSQL, GeoServer, Node-RED, FUXA, Ollama) têm a receita "servicos.saude" (só confere a porta).
"""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
import zipfile
from pathlib import Path

ENTRADA_MAX = 200 * 1024 * 1024
TEMPO_PADRAO = 600
_PF = ["C:/Program Files", "C:/Program Files (x86)", os.path.expandvars("%LOCALAPPDATA%/Programs"), "C:/"]
# programa: (nomes no PATH, padrões no Windows relativos a _PF)
PROGRAMAS = {
    "freecad": (["freecadcmd", "FreeCADCmd"], ["FreeCAD*/bin/freecadcmd.exe", "FreeCAD*/bin/FreeCADCmd.exe"]),
    "gdal": (["ogrinfo"], ["QGIS*/bin/ogrinfo.exe", "OSGeo4W/bin/ogrinfo.exe"]),
    "qgis_process": (["qgis_process"], ["QGIS*/bin/qgis_process-qgis.bat", "QGIS*/bin/qgis_process-qgis-ltr.bat"]),
    "blender": (["blender"], ["Blender Foundation/Blender*/blender.exe"]),
    "kicad": (["kicad-cli"], ["KiCad/*/bin/kicad-cli.exe"]),
    "prusaslicer": (["prusa-slicer-console", "prusa-slicer"], ["Prusa3D/PrusaSlicer/prusa-slicer-console.exe", "Prusa3D/PrusaSlicer/prusa-slicer.exe"]),
    "librecad": (["librecad"], ["LibreCAD/librecad.exe"]),
    "calculix": (["ccx"], ["FreeCAD*/bin/ccx.exe"]),
    "tesseract": (["tesseract"], ["Tesseract-OCR/tesseract.exe"]),
    "energyplus": (["energyplus"], ["EnergyPlusV*/energyplus.exe"]),
    "openstudio": (["openstudio"], ["openstudio-*/bin/openstudio.exe"]),
    "elmer": (["ElmerSolver"], ["Elmer*/bin/ElmerSolver.exe"]),
    "lammps": (["lmp", "lmp_serial"], ["LAMMPS*/bin/lmp.exe"]),
    "copasi": (["CopasiSE"], ["copasi.org/COPASI*/bin/CopasiSE.exe"]),
    "opensim": (["opensim-cmd"], ["OpenSim*/bin/opensim-cmd.exe"]),
    "conda": (["conda"], ["miniforge3/Scripts/conda.exe"]),
    "python": ([], []),
}
SERVICOS = {"mosquitto": 1883, "postgresql": 5432, "geoserver": 8080, "node-red": 1880, "fuxa": 1881, "ollama": 11434}


def localizar(programa: str) -> str | None:
    if programa == "python":
        return sys.executable
    amb = os.environ.get("PHYSIS_PROGRAMA_" + programa.upper().replace("-", "_"))
    if amb and os.path.exists(amb):
        return amb
    nomes, pads = PROGRAMAS.get(programa, ([], []))
    for n in nomes:
        w = shutil.which(n)
        if w:
            return w
    if os.name == "nt":
        extras = [os.path.expanduser("~")] if programa == "conda" else []
        for base in _PF + extras:
            for p in pads:
                achados = sorted(glob.glob(os.path.join(base, p)))
                if achados:
                    return achados[-1]
    return None


# ── scripts levados para dentro dos programas (rodam no Python de cada um) ─────────────────────────────────────────────
FREECAD_PY = r'''
import json, sys, os
import FreeCAD, Part, Mesh
ent, sai = os.environ["PHYSIS_ENTRADA"], os.environ["PHYSIS_SAIDA"]
if ent.lower().endswith(".fcstd"):
    doc = FreeCAD.openDocument(ent); formas = [o.Shape for o in doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull()]
    forma = formas[0].fuse(formas[1:]) if len(formas) > 1 else formas[0]
else:
    forma = Part.read(ent)
bb = forma.BoundBox
r = {"volume_mm3": forma.Volume, "area_mm2": forma.Area, "solidos": len(forma.Solids), "faces": len(forma.Faces),
     "caixa_mm": [bb.XLength, bb.YLength, bb.ZLength]}
forma.exportStep(os.path.join(sai, "modelo.step"))
m = Mesh.Mesh(forma.tessellate(0.1)); m.write(os.path.join(sai, "modelo.stl")); r["triangulos_stl"] = m.CountFacets
open(os.path.join(sai, "resumo.json"), "w").write(json.dumps(r))
'''
BLENDER_PY = r'''
import bpy, json, os
ent, sai = os.environ["PHYSIS_ENTRADA"], os.environ["PHYSIS_SAIDA"]
bpy.ops.wm.read_factory_settings(use_empty=True)
ext = os.path.splitext(ent)[1].lower()
imp = {".stl": lambda: bpy.ops.wm.stl_import(filepath=ent), ".obj": lambda: bpy.ops.wm.obj_import(filepath=ent),
       ".ply": lambda: bpy.ops.wm.ply_import(filepath=ent), ".glb": lambda: bpy.ops.import_scene.gltf(filepath=ent),
       ".gltf": lambda: bpy.ops.import_scene.gltf(filepath=ent), ".fbx": lambda: bpy.ops.import_scene.fbx(filepath=ent)}[ext]
imp()
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
dims = [list(o.dimensions) for o in objs]
bpy.ops.export_scene.gltf(filepath=os.path.join(sai, "modelo.glb"))
open(os.path.join(sai, "resumo.json"), "w").write(json.dumps({"objetos": len(objs), "dimensoes": dims,
     "vertices": sum(len(o.data.vertices) for o in objs)}))
'''
RDKIT_PY = r'''
import json, os, sys
from rdkit import Chem
from rdkit.Chem import Descriptors, Crippen, rdMolDescriptors
out = []
for linha in open(os.environ["PHYSIS_ENTRADA"], encoding="utf-8"):
    s = linha.strip().split()[0] if linha.strip() else ""
    if not s: continue
    m = Chem.MolFromSmiles(s)
    out.append({"smiles": s, "valido": m is not None} if m is None else {"smiles": s, "valido": True, "massa_molar": Descriptors.MolWt(m),
               "logp": Crippen.MolLogP(m), "tpsa": rdMolDescriptors.CalcTPSA(m), "doadores_h": rdMolDescriptors.CalcNumHBD(m),
               "aceptores_h": rdMolDescriptors.CalcNumHBA(m), "formula": rdMolDescriptors.CalcMolFormula(m)})
open(os.path.join(os.environ["PHYSIS_SAIDA"], "resumo.json"), "w").write(json.dumps(out))
'''
GMSH_PY = r'''
import json, os, gmsh
ent, sai, tam = os.environ["PHYSIS_ENTRADA"], os.environ["PHYSIS_SAIDA"], float(os.environ.get("PHYSIS_TAMANHO", "5"))
gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 0)
gmsh.merge(ent); gmsh.option.setNumber("Mesh.MeshSizeMax", tam); gmsh.model.mesh.generate(3)
gmsh.write(os.path.join(sai, "malha.msh"))
n = len(gmsh.model.mesh.getNodes()[0]); t, e, _ = gmsh.model.mesh.getElements(3)
open(os.path.join(sai, "resumo.json"), "w").write(json.dumps({"nos": n, "elementos_3d": int(sum(len(x) for x in e)), "tamanho_max": tam}))
gmsh.finalize()
'''

# receita: programa, nome, extensões de entrada (None = sem arquivo), parâmetros {nome: lista fechada ou (min, max)}, montar(...)
def _argv_freecad(exe, ent, sai, p):
    return [exe, os.path.join(sai, "_freecad.py")], {"_freecad.py": FREECAD_PY}


def _argv_blender(exe, ent, sai, p):
    return [exe, "-b", "--factory-startup", "--python", os.path.join(sai, "_blender.py")], {"_blender.py": BLENDER_PY}


def _argv_py(script):
    return lambda exe, ent, sai, p: ([exe, os.path.join(sai, "_script.py")], {"_script.py": script})


RECEITAS = {
    "freecad.solido": {"programa": "freecad", "nome": "FreeCAD · volume, área e caixa do sólido; exporta STEP e STL",
                       "entrada": [".step", ".stp", ".iges", ".igs", ".brep", ".fcstd"], "params": {}, "montar": _argv_freecad},
    "qgis.vetor": {"programa": "gdal", "nome": "QGIS/GDAL · vetor (SHP, GPKG, KML, DXF, GeoJSON, ZIP) → GeoJSON em WGS84 + resumo",
                   "entrada": [".shp", ".zip", ".gpkg", ".kml", ".dxf", ".geojson", ".json", ".gml"], "params": {},
                   "montar": lambda exe, ent, sai, p: ([str(Path(exe).with_name("ogr2ogr" + Path(exe).suffix)), "-f", "GeoJSON", "-t_srs", "EPSG:4326",
                                                        os.path.join(sai, "camada.geojson"), ("/vsizip/" + ent) if ent.lower().endswith(".zip") else ent], {})},
    "qgis.raster": {"programa": "gdal", "nome": "QGIS/GDAL · raster (TIF, ASC, IMG): metadados e estatísticas",
                    "entrada": [".tif", ".tiff", ".asc", ".img", ".vrt"], "params": {},
                    "montar": lambda exe, ent, sai, p: ([str(Path(exe).with_name("gdalinfo" + Path(exe).suffix)), "-json", "-stats", ent], {}),
                    "saida_stdout": "resumo.json"},
    "qgis.processo": {"programa": "qgis_process", "nome": "QGIS · algoritmo de processamento (área de influência ou reprojeção)",
                      "entrada": [".geojson", ".gpkg", ".shp", ".zip", ".kml"], "params": {"algoritmo": ["native:buffer", "native:reprojectlayer", "native:fixgeometries", "native:centroids"],
                                                                                           "distancia": (0, 100000)},
                      "montar": lambda exe, ent, sai, p: ([exe, "run", p["algoritmo"], "--", "INPUT=" + ent, "OUTPUT=" + os.path.join(sai, "saida.geojson")]
                                                          + (["DISTANCE=" + str(p.get("distancia", 10))] if p["algoritmo"] == "native:buffer" else [])
                                                          + (["TARGET_CRS=EPSG:4326"] if p["algoritmo"] == "native:reprojectlayer" else []), {})},
    "blender.glb": {"programa": "blender", "nome": "Blender · STL/OBJ/PLY/FBX/GLB → GLB (vista 3D da plataforma) + dimensões",
                    "entrada": [".stl", ".obj", ".ply", ".fbx", ".glb", ".gltf"], "params": {}, "montar": _argv_blender},
    "kicad.gerber": {"programa": "kicad", "nome": "KiCad · placa (.kicad_pcb) → Gerber e furação para fabricar",
                     "entrada": [".kicad_pcb"], "params": {},
                     "montar": lambda exe, ent, sai, p: ([exe, "pcb", "export", "gerbers", "--output", sai + os.sep, ent], {})},
    "kicad.esquema_pdf": {"programa": "kicad", "nome": "KiCad · esquema (.kicad_sch) → PDF",
                          "entrada": [".kicad_sch"], "params": {},
                          "montar": lambda exe, ent, sai, p: ([exe, "sch", "export", "pdf", "--output", os.path.join(sai, "esquema.pdf"), ent], {})},
    "prusaslicer.fatiar": {"programa": "prusaslicer", "nome": "PrusaSlicer · STL/3MF → G-code, com tempo e filamento estimados",
                           "entrada": [".stl", ".3mf", ".obj"], "params": {"camada_mm": (0.05, 0.4), "preenchimento_pct": (0, 100)},
                           "montar": lambda exe, ent, sai, p: ([exe, "--export-gcode", "--layer-height", str(p.get("camada_mm", 0.2)),
                                                                "--fill-density", str(int(p.get("preenchimento_pct", 20))) + "%", "-o", os.path.join(sai, "peca.gcode"), ent], {})},
    "librecad.pdf": {"programa": "librecad", "nome": "LibreCAD · DXF → PDF", "entrada": [".dxf"], "params": {},
                     "montar": lambda exe, ent, sai, p: ([exe, "dxf2pdf", "-o", os.path.join(sai, "desenho.pdf"), ent], {})},
    "calculix.rodar": {"programa": "calculix", "nome": "CalculiX · roda o modelo de elementos finitos (.inp) e devolve .frd/.dat",
                       "entrada": [".inp"], "params": {}, "cwd_entrada": True,
                       "montar": lambda exe, ent, sai, p: ([exe, "-i", os.path.splitext(os.path.basename(ent))[0]], {})},
    "gmsh.malha": {"programa": "python", "nome": "Gmsh · malha 3D de um STEP/IGES/BREP (para CalculiX, Elmer, OpenFOAM)",
                   "entrada": [".step", ".stp", ".iges", ".igs", ".brep", ".geo"], "params": {"tamanho": (0.01, 1000)}, "montar": _argv_py(GMSH_PY)},
    "tesseract.ocr": {"programa": "tesseract", "nome": "Tesseract · texto de imagem escaneada (português)",
                      "entrada": [".png", ".jpg", ".jpeg", ".tif", ".tiff"], "params": {"idioma": ["por", "eng", "por+eng"]},
                      "montar": lambda exe, ent, sai, p: ([exe, ent, os.path.join(sai, "texto"), "-l", p.get("idioma", "por")], {})},
    "rdkit.descritores": {"programa": "python", "nome": "RDKit · descritores de moléculas (um SMILES por linha)",
                          "entrada": [".txt", ".smi", ".csv"], "params": {}, "montar": _argv_py(RDKIT_PY)},
    "energyplus.idf": {"programa": "energyplus", "nome": "EnergyPlus · roda um IDF com o clima mais perto (EPW da camada clima)",
                       "entrada": [".idf"], "params": {}, "precisa_epw": True,
                       "montar": lambda exe, ent, sai, p: ([exe, "-w", p["_epw"], "-d", sai, "-r", ent], {})},
    "openstudio.osw": {"programa": "openstudio", "nome": "OpenStudio · roda um workflow (.osw, ou .zip com o .osw e os arquivos)",
                       "entrada": [".osw", ".zip"], "params": {}, "procura": "*.osw",
                       "montar": lambda exe, ent, sai, p: ([exe, "run", "-w", ent], {})},
    "elmer.sif": {"programa": "elmer", "nome": "Elmer FEM · roda o caso (.zip com o .sif e a malha)", "entrada": [".zip", ".sif"], "params": {},
                  "procura": "*.sif", "cwd_entrada": True, "montar": lambda exe, ent, sai, p: ([exe, os.path.basename(ent)], {})},
    "lammps.in": {"programa": "lammps", "nome": "LAMMPS · roda o script (.in, ou .zip com o script e os dados)", "entrada": [".in", ".lammps", ".zip"],
                  "params": {}, "procura": "in.*", "cwd_entrada": True, "montar": lambda exe, ent, sai, p: ([exe, "-in", os.path.basename(ent)], {})},
    "copasi.cps": {"programa": "copasi", "nome": "COPASI · roda as tarefas marcadas do modelo (.cps)", "entrada": [".cps"], "params": {},
                   "cwd_entrada": True, "montar": lambda exe, ent, sai, p: ([exe, ent], {})},
    "psi4.energia": {"programa": "conda", "nome": "Psi4 · energia de ponto único (XYZ) pelo ambiente conda psi4", "entrada": [".xyz"],
                     "params": {"metodo": ["scf", "b3lyp", "mp2"], "base": ["sto-3g", "6-31g*", "cc-pvdz"]},
                     "montar": lambda exe, ent, sai, p: ([exe, "run", "-n", "psi4", "python", os.path.join(sai, "_psi4.py")], {"_psi4.py":
                         "import psi4, json, os\nxyz=open(%r).read().strip().splitlines()[2:]\nm=psi4.geometry('\\n'.join(xyz))\npsi4.set_output_file(os.path.join(%r,'psi4.out'))\n"
                         "e=psi4.energy(%r)\nopen(os.path.join(%r,'resumo.json'),'w').write(json.dumps({'energia_hartree':e,'metodo':%r}))\n"
                         % (ent, sai, p.get("metodo", "scf") + "/" + p.get("base", "sto-3g"), sai, p.get("metodo", "scf") + "/" + p.get("base", "sto-3g"))})},
    "opensim.ferramenta": {"programa": "opensim", "nome": "OpenSim · roda uma ferramenta (.zip com o setup .xml e os arquivos)", "entrada": [".zip", ".xml"],
                           "params": {}, "procura": "*.xml", "cwd_entrada": True, "montar": lambda exe, ent, sai, p: ([exe, "run-tool", os.path.basename(ent)], {})},
    "servicos.saude": {"programa": None, "nome": "Serviços do servidor: Mosquitto, PostgreSQL, GeoServer, Node-RED, FUXA, Ollama (porta respondendo)",
                       "entrada": None, "params": {}},
}


def disponiveis() -> list[dict]:
    out = []
    for rid, r in RECEITAS.items():
        exe = localizar(r["programa"]) if r["programa"] else "servico"
        ok = bool(exe)
        if ok and r["programa"] == "python":
            mod = {"gmsh.malha": "gmsh", "rdkit.descritores": "rdkit"}.get(rid)
            import importlib.util
            ok = importlib.util.find_spec(mod) is not None if mod else True
        out.append({"id": rid, "nome": r["nome"], "programa": r["programa"], "disponivel": ok, "entrada": r["entrada"],
                    "params": {k: (v if isinstance(v, list) else {"min": v[0], "max": v[1]}) for k, v in r["params"].items()}})
    return out


def _params(r: dict, brutos: dict) -> tuple[dict | None, str | None]:
    out = {}
    for k, v in (brutos or {}).items():
        if k not in r["params"]:
            return None, f"parâmetro desconhecido: {k}"
        regra = r["params"][k]
        if isinstance(regra, list):
            if v not in regra:
                return None, f"{k}: " + ", ".join(regra)
            out[k] = v
        else:
            try:
                x = float(str(v).replace(",", "."))
            except ValueError:
                return None, f"{k}: número"
            if not regra[0] <= x <= regra[1]:
                return None, f"{k} entre {regra[0]:g} e {regra[1]:g}"
            out[k] = x
    for k, regra in r["params"].items():
        if isinstance(regra, list) and k not in out:
            out[k] = regra[0]
    return out, None


def _extrair(zp: Path, destino: Path) -> None:
    with zipfile.ZipFile(zp) as z:
        total = 0
        for m in z.infolist():
            alvo = (destino / m.filename).resolve()
            if destino.resolve() not in alvo.parents and alvo != destino.resolve():
                raise ValueError("zip com caminho fora da pasta")
            total += m.file_size
            if total > 2 * ENTRADA_MAX:
                raise ValueError("zip grande demais depois de aberto")
        z.extractall(destino)


def _epw_perto(pasta_camadas: str | None) -> str | None:
    p = Path(pasta_camadas or os.environ.get("PHYSIS_CAMADAS") or "") / "clima"
    epws = sorted(p.glob("*.epw")) if p.is_dir() else []
    return str(epws[0]) if epws else None


class Programas:
    def __init__(self, pasta: str | Path, rodar=subprocess.run, localizar_=localizar):
        self.pasta = Path(pasta); self.pasta.mkdir(parents=True, exist_ok=True)
        self.rodar, self.loc = rodar, localizar_
        self._trava = threading.Lock(); self.trabalhos: dict[str, dict] = {}

    def iniciar(self, receita: str, dados: bytes | None, nome: str, params: dict, quem: str, esperar: bool = False) -> dict:
        r = RECEITAS.get(receita)
        if not r:
            return {"ok": False, "erro": "receita desconhecida", "codigo": 404}
        p, erro = _params(r, params)
        if erro:
            return {"ok": False, "erro": erro}
        jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        d = self.pasta / jid; ent_dir, sai = d / "entrada", d / "saida"
        ent_dir.mkdir(parents=True); sai.mkdir()
        ent = None
        if r["entrada"] is not None:
            nome = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(nome or ""))[:100]
            ext = os.path.splitext(nome)[1].lower()
            if not dados or ext not in r["entrada"]:
                shutil.rmtree(d, ignore_errors=True)
                return {"ok": False, "erro": "envie um arquivo " + ", ".join(r["entrada"])}
            if len(dados) > ENTRADA_MAX:
                shutil.rmtree(d, ignore_errors=True)
                return {"ok": False, "erro": "arquivo maior que 200 MB"}
            ent = ent_dir / nome; ent.write_bytes(dados)
            if ext == ".zip" and r.get("procura"):
                try:
                    _extrair(ent, ent_dir)
                except (ValueError, zipfile.BadZipFile) as e:
                    shutil.rmtree(d, ignore_errors=True)
                    return {"ok": False, "erro": str(e)}
                achado = sorted(ent_dir.rglob(r["procura"]))
                if not achado:
                    shutil.rmtree(d, ignore_errors=True)
                    return {"ok": False, "erro": "o zip não tem " + r["procura"]}
                ent = achado[0]
        if r.get("precisa_epw"):
            p["_epw"] = _epw_perto(None)
            if not p["_epw"]:
                shutil.rmtree(d, ignore_errors=True)
                return {"ok": False, "erro": "sem arquivo de clima (camada clima vazia: rode emitir_camadas.ps1)"}
        t = {"id": jid, "receita": receita, "estado": "rodando", "inicio": time.time(), "quem": quem, "params": {k: v for k, v in p.items() if not k.startswith("_")}}
        with self._trava:
            self.trabalhos[jid] = t
        (d / "trabalho.json").write_text(json.dumps(t, ensure_ascii=False), encoding="utf-8")
        th = threading.Thread(target=self._rodar, args=(jid, r, ent, sai, p), daemon=True)
        th.start()
        if esperar:
            th.join()
        return {"ok": True, "id": jid, "estado": self.trabalhos[jid]["estado"]}

    def _rodar(self, jid, r, ent, sai, p):
        t = self.trabalhos[jid]
        try:
            if r["programa"] is None:                                   # serviços: só a porta
                res = {}
                for n, porta in SERVICOS.items():
                    with socket.socket() as s:
                        s.settimeout(2)
                        res[n] = {"porta": porta, "no_ar": s.connect_ex(("127.0.0.1", porta)) == 0}
                (sai / "resumo.json").write_text(json.dumps(res), encoding="utf-8")
                t.update(estado="ok", codigo=0)
                return
            exe = self.loc(r["programa"])
            if not exe:
                t.update(estado="erro", erro=f"{r['programa']} não está instalado neste servidor"); return
            argv, scripts = r["montar"](exe, str(ent) if ent else "", str(sai), p)
            env_o4w = Path(exe).parent / "o4w_env.bat"
            if r["programa"] == "gdal" and os.name == "nt" and env_o4w.is_file():      # GDAL do QGIS precisa do ambiente dele (PROJ)
                argv = ["cmd", "/c", f'call "{env_o4w}" >nul && ' + subprocess.list2cmdline(argv)]
            for nome, texto in scripts.items():
                (sai / nome).write_text(texto, encoding="utf-8")
            env = dict(os.environ, PHYSIS_ENTRADA=str(ent or ""), PHYSIS_SAIDA=str(sai), PHYSIS_TAMANHO=str(p.get("tamanho", 5)))
            cwd = str(Path(ent).parent) if r.get("cwd_entrada") and ent else str(sai)
            x = self.rodar(argv, capture_output=True, text=True, timeout=TEMPO_PADRAO, cwd=cwd, env=env)
            if r.get("cwd_entrada") and ent:                            # programas que escrevem ao lado da entrada
                for f in Path(ent).parent.iterdir():
                    if f.is_file() and f != Path(ent) and f.suffix.lower() not in (".zip",) and not (sai / f.name).exists():
                        shutil.copy2(f, sai / f.name)
            if r.get("saida_stdout"):
                (sai / r["saida_stdout"]).write_text(x.stdout or "", encoding="utf-8")
            (sai / "registro.txt").write_text(((x.stdout or "") + "\n" + (x.stderr or ""))[-200000:], encoding="utf-8")
            for nome in scripts:
                (sai / nome).unlink(missing_ok=True)
            t.update(estado="ok" if x.returncode == 0 else "erro", codigo=x.returncode,
                     erro="" if x.returncode == 0 else ((x.stderr or x.stdout or "")[-600:]))
            if r["programa"] == "prusaslicer":
                g = sai / "peca.gcode"
                if g.is_file():
                    cab = g.read_text(encoding="utf-8", errors="replace")[-20000:]
                    res = {k: m.group(1).strip() for k, pat in (("tempo_estimado", r"estimated printing time \(normal mode\) = (.+)"),
                                                                ("filamento_m", r"filament used \[mm\] = (.+)"), ("filamento_g", r"filament used \[g\] = (.+)"))
                           for m in [re.search(pat, cab)] if m}
                    (sai / "resumo.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
        except subprocess.TimeoutExpired:
            t.update(estado="erro", erro=f"passou de {TEMPO_PADRAO} s")
        except Exception as e:  # noqa: BLE001 — o trabalho registra o erro; o servidor segue
            t.update(estado="erro", erro=f"{type(e).__name__}: {e}")
        finally:
            t["fim"] = time.time()
            (sai.parent / "trabalho.json").write_text(json.dumps(t, ensure_ascii=False, default=str), encoding="utf-8")

    def estado(self, jid: str) -> dict:
        if not re.fullmatch(r"[0-9-]+[0-9a-f]{6}", jid or ""):
            return {"ok": False, "erro": "trabalho inválido", "codigo": 404}
        d = self.pasta / jid
        t = self.trabalhos.get(jid) or (json.loads((d / "trabalho.json").read_text(encoding="utf-8")) if (d / "trabalho.json").is_file() else None)
        if not t:
            return {"ok": False, "erro": "trabalho não encontrado", "codigo": 404}
        sai = d / "saida"
        arqs = [{"nome": f.name, "kb": round(f.stat().st_size / 1024)} for f in sorted(sai.iterdir()) if f.is_file()] if sai.is_dir() else []
        resumo = None
        if (sai / "resumo.json").is_file():
            try:
                resumo = json.loads((sai / "resumo.json").read_text(encoding="utf-8"))
            except ValueError:
                resumo = None
        return {"ok": True, **t, "arquivos": arqs, "resumo": resumo}

    def arquivo(self, jid: str, nome: str) -> tuple[str, bytes] | None:
        if not re.fullmatch(r"[0-9-]+[0-9a-f]{6}", jid or "") or not re.fullmatch(r"[A-Za-z0-9._-]{1,120}", nome or ""):
            return None
        f = self.pasta / jid / "saida" / nome
        return (f.name, f.read_bytes()) if f.is_file() else None

    def lista(self, limite: int = 50) -> list[dict]:
        out = []
        for d in sorted((x for x in self.pasta.iterdir() if x.is_dir()), reverse=True)[:limite]:
            if (d / "trabalho.json").is_file():
                try:
                    out.append(json.loads((d / "trabalho.json").read_text(encoding="utf-8")))
                except ValueError:
                    pass
        return out
