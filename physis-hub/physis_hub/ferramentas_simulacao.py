"""Ferramentas abertas de simulação e desenho (pedido da dona de 24/11/2026): catálogo, detecção no servidor e o que cada
análise do bot de modelagem usa. Só software aberto (decisão da dona de 24/11/2026: ORCA e outros fechados ficam fora), instalado no servidor da Physis (regra 11); nada é baixado daqui.

    python -m physis_hub.ferramentas_simulacao          # o que está instalado neste computador
"""
from __future__ import annotations

import glob as _glob
import importlib.util
import json
import os
import shutil

# (id, nome, área, para quê, comandos/módulos que indicam instalado, licença, aberto?)
CATALOGO = [
    ("freecad", "FreeCAD", "mecanica", "CAD paramétrico 3D", ["freecad", "FreeCAD", "freecadcmd"], "LGPL", True),
    ("openfoam", "OpenFOAM", "mecanica", "CFD e térmica (calhas, dutos, estufas, rotores)", ["simpleFoam", "interFoam", "blockMesh"], "GPL", True),
    ("calculix", "CalculiX", "mecanica", "elementos finitos: estrutura, flambagem, térmica", ["ccx"], "GPL", True),
    ("code_aster", "Salome-Meca / Code_Aster", "mecanica", "mecânica estrutural avançada com pré e pós", ["as_run", "salome"], "GPL", True),
    ("elmer", "Elmer FEM", "fisica", "multifísica: fluidos, estrutura, eletromagnetismo, calor", ["ElmerSolver"], "GPL", True),
    ("openems", "openEMS", "fisica", "eletromagnetismo 3D (FDTD): antenas, sensores", ["openEMS"], "GPL", True),
    ("gazebo", "Gazebo", "fisica", "robótica, sensores e sistemas autônomos", ["gz", "gazebo"], "Apache-2.0", True),
    ("lammps", "LAMMPS", "fisica", "dinâmica molecular de materiais", ["lmp", "lmp_serial", "lmp_mpi"], "GPL", True),
    ("avogadro", "Avogadro", "quimica", "editor e visualizador molecular", ["avogadro2", "avogadro"], "BSD", True),
    ("psi4", "Psi4", "quimica", "química quântica ab initio", ["psi4"], "LGPL", True),
    ("rdkit", "RDKit", "quimica", "quimioinformática (Python)", ["py:rdkit"], "BSD", True),
    ("gromacs", "GROMACS", "biologia", "dinâmica molecular de biomoléculas", ["gmx", "gmx_mpi"], "LGPL", True),
    ("copasi", "COPASI", "biologia", "redes bioquímicas e vias metabólicas", ["CopasiSE", "CopasiUI"], "Artistic-2.0", True),
    ("cellblender", "CellBlender (MCell)", "biologia", "processos celulares e difusão molecular (extensão do Blender)", ["mcell", "blender"], "GPL/MIT", True),
    ("opensim", "OpenSim", "biologia", "modelagem musculoesquelética e movimento", ["opensim-cmd", "py:opensim"], "Apache-2.0", True),
    # BIM e instalações (só no Planejador e telas internas; decisão de 24/11/2026). Modelagem ≠ cálculo: as contas pelas NBR
    # ficam no Planejador/servidor (Python, IFC lido pelo próprio sistema); o BIM representa, compatibiliza e tira quantitativos.
    ("bonsai", "Bonsai (antigo BlenderBIM)", "bim", "BIM/IFC: MEP nativo (IfcPipeSegment, IfcDuctSegment), federação e detecção de interferências", ["blender"], "GPL-3.0", True),
    ("freecad_bim", "FreeCAD · BIM, TechDraw, FEM, CfdOF, Dodo, KiCadStepUp", "bim", "CAD mecânico completo: peças, montagens, pranchas, FEM (CalculiX), CFD (OpenFOAM), tubulação e chicotes", ["freecad", "FreeCAD", "freecadcmd"], "LGPL", True),
    ("openstudio", "OpenStudio + EnergyPlus", "bim", "carga térmica e desempenho energético do prédio (gbXML/IFC)", ["openstudio", "energyplus"], "BSD", True),
    ("ifcopenshell", "IfcOpenShell", "bim", "ler e escrever IFC em Python (scripts de verificação)", ["py:ifcopenshell"], "LGPL", True),
    # Automação predial e AVAC central (BMS) e solar (24/11/2026): protocolos abertos BACnet, Modbus e MQTT
    ("volttron", "Eclipse VOLTTRON", "eletrica", "supervisão e controle de AVAC central e energia (BACnet, Modbus)", ["volttron", "py:volttron"], "Apache-2.0", True),
    ("nodered", "Node-RED", "eletrica", "lógicas de automação visuais (rodízio de bombas, água gelada, horários) e painéis web", ["node-red"], "Apache-2.0", True),
    ("openbms", "OpenBMS", "eletrica", "sequências de controle de AVAC com BACnet e MQTT [CONFERIR licença e maturidade]", ["openbms"], "[CONFERIR]", True),
    ("scadabr", "ScadaBR / FUXA", "eletrica", "supervisório SCADA web (telas de CAG, alarmes, históricos via Modbus/BACnet)", ["fuxa", "scadabr"], "GPL / MIT", True),
    ("sam", "SAM (NREL)", "bim", "geração fotovoltaica e perdas (substitui PVsyst em estudos)", ["sam", "SAM"], "BSD-3", True),
    ("pvlib", "pvlib python", "bim", "irradiação, inclinação, espaçamento entre fileiras e inversores em Python", ["py:pvlib"], "BSD-3", True),
    ("qelectrotech", "QElectroTech", "eletrica", "quadros de automação e controle: multifilar, comando, potência, CLP, referências cruzadas, réguas de bornes, BOM e layout da placa", ["qelectrotech"], "GPL", True),
    ("librecad", "LibreCAD", "eletrica", "desenho 2D em DXF: furação da placa, recortes da porta, arquivos para corte a laser", ["librecad"], "GPL-2.0", True),
    ("kicad", "KiCad", "eletrica", "placas eletrônicas (caixas de sensores, ESP32)", ["kicad", "kicad-cli"], "GPL", True),
]
AREAS = {"mecanica": "Mecânica e engenharia (CAD/CAE/CFD)", "fisica": "Física (multifísica e eletromagnetismo)",
         "quimica": "Química (quântica e molecular)", "biologia": "Biologia e bioinformática", "eletrica": "IoT, quadros elétricos e automação", "bim": "BIM e instalações (Planejador)"}
# análise do bot de modelagem → ferramenta
ANALISE = {"cfd": "openfoam", "fea": "calculix", "multi": "elmer", "cad": "freecad", "aster": "code_aster", "ele": "qelectrotech"}


# Windows: os instaladores põem os programas em "Arquivos de Programas" sem colocar no PATH, então só o which() não acha
# (verificação no PC-PHYSIS, 24/11/2026: FreeCAD, KiCad, Avogadro... instalados, mas "instalado": false aqui).
# Mesmos lugares que ferramentas/verificar_programas.py procura. PHYSIS_FERRAMENTA_<ID> (ex.: PHYSIS_FERRAMENTA_FREECAD)
# aponta um executável fora desses lugares.
_PF = ["C:/Program Files", "C:/Program Files (x86)", os.path.expandvars("%LOCALAPPDATA%/Programs")]
LOCAIS_WINDOWS = {
    "freecad": ["FreeCAD*/bin/FreeCAD.exe", "FreeCAD*/bin/freecadcmd.exe"],
    "freecad_bim": ["FreeCAD*/bin/FreeCAD.exe"],
    "calculix": ["FreeCAD*/bin/ccx.exe", "FreeCAD*/bin/ccx*.exe"],
    "avogadro": ["Avogadro2/bin/avogadro2.exe", "Avogadro*/bin/avogadro2.exe"],
    "kicad": ["KiCad/*/bin/kicad.exe", "KiCad/*/bin/kicad-cli.exe"],
    "librecad": ["LibreCAD/librecad.exe"],
    "qelectrotech": ["QElectroTech*/bin/qelectrotech.exe", "QElectroTech*/qelectrotech.exe"],
    "bonsai": ["Blender Foundation/Blender*/blender.exe"],
    "cellblender": [],
    "copasi": ["copasi.org/COPASI*/bin/CopasiUI.exe"],
    "elmer": ["Elmer*/bin/ElmerSolver.exe"],
    "lammps": ["LAMMPS*/bin/lmp.exe"],
    "openstudio": ["OpenStudio*/bin/openstudio.exe"],
    "sam": ["SAM/*/SAM.exe"],
}
LOCAIS_RAIZ = {"openstudio": ["C:/openstudio-*/bin/openstudio.exe", "C:/EnergyPlusV*/energyplus.exe"],
               "opensim": ["C:/OpenSim*/bin/opensim-cmd.exe"], "openems": ["C:/openEMS/openEMS.exe"]}


def instalado_windows(id_: str, achar=_glob.glob) -> bool:
    if os.environ.get(f"PHYSIS_FERRAMENTA_{id_.upper()}") and os.path.exists(os.environ[f"PHYSIS_FERRAMENTA_{id_.upper()}"]):
        return True
    pads = [f"{b}/{p}" for b in _PF for p in LOCAIS_WINDOWS.get(id_, [])] + LOCAIS_RAIZ.get(id_, [])
    return any(achar(p) for p in pads)


def instalado(sinais: list[str], which=shutil.which) -> bool:
    for s in sinais:
        if s.startswith("py:"):
            if importlib.util.find_spec(s[3:]) is not None:
                return True
        elif which(s):
            return True
    return False


def situacao(which=shutil.which, windows: bool | None = None, achar=_glob.glob) -> list[dict]:
    win = (os.name == "nt") if windows is None else windows
    return [{"id": i, "nome": n, "area": AREAS[a], "uso": u, "licenca": lic, "aberto": ab,
             "instalado": (instalado(sin, which) or (win and instalado_windows(i, achar))) if ab else False}
            for i, n, a, u, sin, lic, ab in CATALOGO]


if __name__ == "__main__":
    print(json.dumps(situacao(), ensure_ascii=False, indent=1))

# Projetos experimentais citados pela dona (24/11/2026): acompanhar, NÃO instalar em produção até haver versão estável
# conferida: SolidCraft, BIMCraft, Construct CAD / Construct Craft, Beamcraft [CONFERIR repositório e licença].
EXPERIMENTAIS = ["SolidCraft", "BIMCraft", "Construct CAD / Construct Craft", "Beamcraft"]
