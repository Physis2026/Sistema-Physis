#!/usr/bin/env python3
r"""Programas abertos que o sistema usa: o que já está instalado neste Windows, o que falta e como instalar (24/11/2026).

    py ferramentas\verificar_programas.py              # confere e mostra a tabela
    py ferramentas\verificar_programas.py --instalar   # instala pelo winget só o que roda direto no Windows e ainda falta

Os que precisam de Linux (OpenFOAM, Code_Aster, Gazebo, GROMACS) rodam no WSL (Ubuntu dentro do Windows) ou no Acer.
IDs do winget marcados [CONFERIR] foram escritos sem poder consultar o winget daqui: se o winget não achar, use o link.
"""
from __future__ import annotations

import glob
import importlib.util
import os
import shutil
import subprocess
import sys

# nome, para quê, winget id (ou None), executáveis/pastas/módulo python que provam que está instalado, link, precisa de WSL/Linux
PROGRAMAS = [
    ("Ollama + modelo qwen2.5:7b", "IA Physis generativa", "Ollama.Ollama", ["ollama"], "https://ollama.com/download", False),
    ("Node.js", "testes do bot de modelagem", "OpenJS.NodeJS.LTS", ["node"], "https://nodejs.org", False),
    ("Blender", "render do gêmeo e da planta", "BlenderFoundation.Blender", ["blender", "C:/Program Files/Blender Foundation/Blender*/blender.exe"], "https://www.blender.org/download/", False),
    ("FreeCAD (inclui CalculiX)", "CAD, BIM, FEM; suporte/skid e flambagem", "FreeCAD.FreeCAD", ["freecad", "ccx", "C:/Program Files/FreeCAD*/bin/FreeCAD.exe"], "https://www.freecad.org/downloads.php", False),
    ("Tesseract OCR", "nomes e medidas em fotos e rascunhos", "UB-Mannheim.TesseractOCR", ["tesseract", "C:/Program Files/Tesseract-OCR/tesseract.exe"], "https://github.com/UB-Mannheim/tesseract/wiki", False),
    ("QGIS", "camadas de mapa (recorte e conversão)", "OSGeo.QGIS", ["qgis", "C:/Program Files/QGIS*/bin/qgis-bin.exe"], "https://qgis.org/download/", False),
    ("LibreCAD", "DXF da planta e furação de painéis", "LibreCAD.LibreCAD", ["librecad", "C:/Program Files*/LibreCAD/librecad.exe"], "https://librecad.org/", False),
    ("QElectroTech", "quadros elétricos e automação", "QElectroTech.QElectroTech", ["qelectrotech", "C:/Program Files*/QElectroTech*/bin/qelectrotech.exe"], "https://qelectrotech.org/download.php", False),
    ("KiCad", "placas das caixas de sensores", "KiCad.KiCad", ["kicad", "C:/Program Files/KiCad/*/bin/kicad.exe"], "https://www.kicad.org/download/windows/", False),
    ("PrusaSlicer", "fatiador da impressão 3D", "Prusa3D.PrusaSlicer", ["prusa-slicer", "C:/Program Files/Prusa3D/PrusaSlicer/prusa-slicer.exe"], "https://www.prusa3d.com/page/prusaslicer_424/", False),
    ("EnergyPlus", "simulação térmica horária", None, ["energyplus", "C:/EnergyPlusV*/energyplus.exe"], "https://github.com/NREL/EnergyPlus/releases (instalador .exe do Windows; não está no winget)", False),
    ("OpenStudio", "interface do EnergyPlus", None, ["openstudio", "C:/openstudio-*/bin/openstudio.exe"], "https://github.com/NREL/OpenStudio/releases (no winget só há uma versão da Microsoft Store, não usada)", False),
    ("EPANET (via WNTR)", "rede de água e pressões", None, ["py:wntr"], "py -m pip install wntr", False),
    ("IfcOpenShell", "conferir IFC", None, ["py:ifcopenshell"], "py -m pip install ifcopenshell", False),
    ("pvlib", "geração solar", None, ["py:pvlib"], "py -m pip install pvlib", False),
    ("RDKit", "química (InovaSTEM)", None, ["py:rdkit"], "py -m pip install rdkit", False),
    ("Avogadro 2", "moléculas (InovaSTEM)", "OpenChemistry.Avogadro2", ["avogadro2", "C:/Program Files/Avogadro2/bin/avogadro2.exe"], "https://two.avogadro.cc/", False),
    ("COPASI", "redes bioquímicas (InovaSTEM)", None, ["CopasiUI", "C:/Program Files/copasi.org/COPASI*/bin/CopasiUI.exe"], "https://copasi.org/Download/", False),
    ("OpenSim", "biomecânica (InovaSTEM)", None, ["opensim-cmd", "C:/OpenSim*/bin/opensim-cmd.exe"], "https://simtk.org/projects/opensim", False),
    ("WSL + Ubuntu", "base para os programas de Linux", None, ["wsl"], "wsl --install -d Ubuntu", False),
    ("OpenFOAM (no WSL ou no Acer)", "CFD de dutos", None, ["wsl:simpleFoam", "simpleFoam"], "no Ubuntu: sudo apt install openfoam", True),
    ("Code_Aster / Salome-Meca", "mecânica estrutural avançada", None, ["as_run"], "https://code-aster.org (Linux)", True),
    ("Gazebo", "robótica", None, ["gz"], "https://gazebosim.org (Linux)", True),
    ("GROMACS", "dinâmica molecular", None, ["gmx"], "no Ubuntu: sudo apt install gromacs", True),
]


def instalado(provas, winget_txt: str = "", wid: str | None = None) -> bool:
    for p in provas:
        if p.startswith("py:"):
            if importlib.util.find_spec(p[3:]) is not None:
                return True
        elif p.startswith("wsl:"):
            if os.name == "nt" and shutil.which("wsl"):
                try:
                    r = subprocess.run(["wsl", "-e", "bash", "-lc", f"command -v {p[4:]} || ls /usr/share/openfoam/etc/bashrc"], capture_output=True, timeout=30)
                    if r.returncode == 0 and r.stdout.strip():
                        return True
                except (OSError, subprocess.TimeoutExpired):
                    pass
        elif ("/" in p and glob.glob(p)) or shutil.which(p):
            return True
    return bool(wid and wid.split()[0] in winget_txt)


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    wtxt = ""
    if os.name == "nt" and shutil.which("winget"):
        try:
            wtxt = subprocess.run(["winget", "list", "--accept-source-agreements"], capture_output=True, timeout=120).stdout.decode("utf-8", "replace")
        except (OSError, subprocess.TimeoutExpired):
            pass
    faltam = []
    print(f"{'Programa':34} {'Situação':12} Como instalar")
    for nome, uso, wid, provas, link, linux in PROGRAMAS:
        ok = instalado(provas, wtxt, wid)
        como = ("WSL/Acer: " if linux else "") + (f"winget install {wid}" if wid else link)
        print(f"{nome:34} {'instalado' if ok else 'FALTA':12} {como}")
        if not ok and wid and not linux and "[CONFERIR]" not in wid:
            faltam.append(wid)
    if "--instalar" in argv and faltam:
        for wid in faltam:
            print("instalando", wid); subprocess.run(["winget", "install", "-e", "--id", wid, "--accept-package-agreements", "--accept-source-agreements"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
