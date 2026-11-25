# Inventário: programas, plugins, serviços e camadas · Windows (PC-PHYSIS) × VM Linux
25/11/2026. "Windows" = instala e roda no PC-PHYSIS. "VM" = vai para a máquina virtual Linux (Ubuntu) depois.
Situação no PC pela última verificação (verificar_programas.py / instalar_modulos.ps1). Conferir: py ferramentas\verificar_programas.py

## Motores de cálculo e simulação
| Programa | Para quê | Licença | Recursos | Onde | Situação |
|---|---|---|---|---|---|
| EnergyPlus | carga térmica horária (8760 h), piscina | BSD-3 (própria) | 1,0 núcleo · 1 GB · 2 GB disco | Windows | instalado |
| OpenStudio | interface do EnergyPlus | BSD | — | Windows | instalado |
| pvlib python | irradiação, FV | BSD-3 | 0,5 núcleo · 0,5 GB · 1 GB | Windows | instalado |
| windpowerlib | energia eólica | MIT | 0,2 núcleo · 0,3 GB | Windows (pip) | falta: py -m pip install windpowerlib |
| EPANET (WNTR) | rede de água e pressões | MIT | 0,2 núcleo · 0,2 GB | Windows | instalado |
| SWMM (pyswmm) | drenagem e chuva | domínio público | 0,5 núcleo · 0,3 GB | Windows (pip) | falta: py -m pip install pyswmm |
| SAM (NREL) | FV e perdas | BSD-3 | — | Windows | falta (instalador) |
| CalculiX | elementos finitos | GPL | — | Windows (vem no FreeCAD) | instalado |
| FreeCAD | CAD, BIM, FEM | LGPL | — | Windows | instalado |
| Elmer FEM | multifísica | GPL | — | Windows | falta (instalador funet) |
| openEMS | eletromagnetismo | GPL | — | Windows (ZIP) | falta |
| LAMMPS | dinâmica molecular | GPL | — | Windows | falta |
| Avogadro 2 | moléculas | BSD | — | Windows | instalado |
| RDKit | quimioinformática | BSD | — | Windows | instalado |
| Psi4 | química quântica | LGPL | — | Windows (conda) | falta (Miniforge instalado) |
| COPASI | redes bioquímicas | Artistic-2.0 | — | Windows | falta |
| OpenSim | biomecânica | Apache-2.0 | — | Windows | falta |
| SALOME (pré/pós) | malha e resultados | LGPL | — | Windows | falta |
| OpenFOAM | CFD (dutos, estufas) | GPL | — | **VM** | — |
| Code_Aster | estrutura avançada | GPL | — | **VM** | — |
| Gazebo | robótica | Apache-2.0 | — | **VM** | — |
| GROMACS | biomoléculas | LGPL | — | **VM** (ou Windows sem GPU) | — |
| FEniCSx | EDP por elementos finitos | LGPL | — | **VM** | — |
| Gmsh | malhas | GPL | — | Windows | conferir |

## Plugins / extensões
| Plugin | Em | Onde | Situação |
|---|---|---|---|
| Bonsai (BlenderBIM) | Blender | Windows | falta |
| CellBlender (MCell) | Blender | Windows | falta |
| CfdOF | FreeCAD (precisa do OpenFOAM) | Windows + OpenFOAM na **VM** | falta |
| Dodo, KiCadStepUp | FreeCAD | Windows | falta (Addon Manager) |
| IfcOpenShell | Python | Windows | instalado |

## Desenho, eletrônica, automação
| Programa | Onde | Situação |
|---|---|---|
| QElectroTech, LibreCAD, KiCad, PrusaSlicer, QGIS, Blender, Tesseract (+ idioma por) | Windows | instalados (falta o idioma "por" do OCR) |
| Node-RED, FUXA | Windows | instalados |
| VOLTTRON | **VM** | — |
| OpenBMS, ScadaBR | **VM** (Java/Linux) | — |

## Serviços do servidor (docker-compose do projeto)
| Serviço | Onde | Situação |
|---|---|---|
| Caddy (HTTPS) | Windows ou VM | falta (configuração segura com o agente) |
| Mosquitto (MQTT) | Windows ou VM | falta |
| PostgreSQL + PostGIS, TimescaleDB | Windows ou VM | falta |
| GeoServer (Java 17) | Windows ou VM | falta |
| Superset (BI) | **VM** (Docker) | — |
| Ollama + qwen2.5:7b | Windows | instalado |

## Camadas de mapa (C:\physis\camadas)
| Camada | Situação | Próximo passo |
|---|---|---|
| limites | instalada | — |
| osm (edificações e vias) | instalada | ampliar a janela por projeto |
| relevo | ladrilhos baixados (RJ, DF, SP, MG, GO, BA) | rodar montar_relevo.ps1 corrigido |
| hidrografia (BHO/ANA), uso do solo (MapBiomas), solos (Embrapa), CAR, risco (SGB), clima (EPW), irradiação (LABREN), vento (CRESESB), rede elétrica (SIGEL) | não instaladas | baixar das fontes oficiais e converter (GUIA-CAMADAS-WINDOWS.md); mosaico por estado |
