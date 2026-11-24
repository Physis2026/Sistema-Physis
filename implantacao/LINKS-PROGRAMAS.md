# Programas para baixar e instalar (só os links) · 24/11/2026

Use primeiro o verificador, que mostra o que já está instalado e instala o que falta pelo winget:

    cd C:\physis\physis-ma-20261122-1bd599e
    py ferramentas\verificar_programas.py
    py ferramentas\verificar_programas.py --instalar

IDs do winget com [CONFERIR] e links: conferir antes (não deu para consultar daqui). Todos são software aberto.

## A. Rodam direto no Windows (sem máquina virtual)

| Programa | Para quê | Instalar |
|---|---|---|
| Ollama + modelo | IA Physis | `winget install Ollama.Ollama` e `ollama pull qwen2.5:7b` |
| Node.js | testes | `winget install OpenJS.NodeJS.LTS` |
| Blender | render do gêmeo e da planta | `winget install BlenderFoundation.Blender` |
| FreeCAD (traz o CalculiX) | CAD, BIM, FEM, suporte/skid | `winget install FreeCAD.FreeCAD` |
| Tesseract OCR | ler nomes em fotos | `winget install UB-Mannheim.TesseractOCR` |
| QGIS | camadas de mapa | `winget install OSGeo.QGIS` |
| LibreCAD | DXF, furação de painéis | `winget install LibreCAD.LibreCAD` |
| QElectroTech | quadros elétricos | `winget install QElectroTech.QElectroTech` (conferido) |
| KiCad | placas eletrônicas | `winget install KiCad.KiCad` |
| PrusaSlicer | fatiador 3D | `winget install Prusa3D.PrusaSlicer` |
| EnergyPlus | térmica horária | não está no winget: instalador .exe em https://github.com/NREL/EnergyPlus/releases |
| OpenStudio | interface do EnergyPlus | instalador em https://github.com/NREL/OpenStudio/releases (a versão da Microsoft Store não é a usada) |
| Avogadro 2 | moléculas (InovaSTEM) | `winget install OpenChemistry.Avogadro2` (conferido) |
| COPASI | bioquímica (InovaSTEM) | https://copasi.org/Download/ [CONFERIR] |
| OpenSim | biomecânica (InovaSTEM) | https://simtk.org/projects/opensim [CONFERIR] |
| Bibliotecas Python | EPANET, IFC, solar, química | `py -m pip install wntr ifcopenshell pvlib rdkit` |

## B. Precisam de Linux: WSL no Windows (agora) ou o Acer (depois)

    wsl --install -d Ubuntu          (reinicia o computador; na primeira abertura cria usuário e senha do Ubuntu)

Depois, no Ubuntu (abra "Ubuntu" no menu Iniciar):

    sudo apt update && sudo apt install -y openfoam gromacs

| Programa | Para quê | Onde |
|---|---|---|
| OpenFOAM | CFD de dutos (o sistema Estermic chama pelo WSL) | `sudo apt install openfoam` no Ubuntu do WSL ou no Acer |
| GROMACS | dinâmica molecular | `sudo apt install gromacs` |
| Code_Aster / Salome-Meca | estrutura avançada | https://code-aster.org [CONFERIR] |
| Gazebo | robótica | https://gazebosim.org [CONFERIR] |

## C. No Acer (Linux), quando for migrar

Tudo da seção A tem versão Linux (`sudo apt install blender freecad tesseract-ocr tesseract-ocr-por qgis librecad qelectrotech kicad prusa-slicer openfoam gromacs`),
mais o Ollama (`curl -fsSL https://ollama.com/install.sh | sh`). Detalhes e camadas de mapa: PROGRAMAS-E-CAMADAS-ACER.md.
