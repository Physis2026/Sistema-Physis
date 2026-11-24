# Programas abertos e camadas de mapa

Só os links, em lista curta: LINKS-PROGRAMAS.md. Conferir o que já está instalado: py ferramentas/verificar_programas.py
 · instalação no Acer (Linux)

Versão de 24/11/2026. Só software aberto (decisão da dona: ORCA e outros fechados ficam fora).
Os links são os sites oficiais conhecidos; **[CONFERIR]** = abrir e confirmar a versão antes de instalar (não foi possível
abrir os sites a partir do ambiente onde este guia foi escrito). Sistema sugerido no Acer: Ubuntu 24.04 LTS.

Depois de instalar, confira o que o servidor enxerga:

    cd ~/physis/physis-sistema/physis-hub
    python3 -m physis_hub.ferramentas_simulacao

## 1. IA Physis (modelo aberto local)

| Programa | Site oficial | Instalar no Ubuntu |
|---|---|---|
| Ollama | https://ollama.com/download [CONFERIR] | `curl -fsSL https://ollama.com/install.sh \| sh` e depois `ollama pull qwen2.5:7b` |

Variáveis: `PHYSIS_IA_MODELO` (padrão qwen2.5:7b; computador lento: qwen2.5:3b), `PHYSIS_IA_TEMPO` (s), `PHYSIS_IA_MODO=extrativa` desliga o modelo.

## 2. Mecânica e engenharia (CAD / CAE / CFD)

| Programa | Para quê no sistema | Site oficial | Ubuntu |
|---|---|---|---|
| FreeCAD | CAD paramétrico; abrir STL/IFC do bot | https://www.freecad.org/downloads.php [CONFERIR] | `sudo apt install freecad` |
| OpenFOAM | CFD: calha, dutos, estufa, rotor (o sistema Estermic roda o CFD de duto) | https://openfoam.org/download/ (Foundation) ou https://www.openfoam.com/download (ESI) [CONFERIR] | `sudo apt install openfoam` (versão do Ubuntu, testada) ou repositório da Foundation |
| CalculiX | elementos finitos: flambagem (arquivo .inp do bot), estrutura, calor | http://www.calculix.de/ [CONFERIR] | `sudo apt install calculix-ccx` |
| Salome-Meca / Code_Aster | estrutura avançada com pré e pós | https://code-aster.org/ [CONFERIR] | contêiner/AppImage do site |
| Gmsh (malha) | malha para CalculiX/Elmer | https://gmsh.info/ [CONFERIR] | `sudo apt install gmsh` |

## 2b. BIM e instalações (só Planejador e telas internas)

Fluxo: modelagem ≠ cálculo. As contas pelas NBR (carga térmica, vazões, circuitos) ficam no Planejador e no servidor; o BIM
representa, compatibiliza e tira quantitativos.

| Programa | Para quê | Site oficial | Ubuntu |
|---|---|---|---|
| Bonsai (antigo BlenderBIM) | MEP nativo em IFC (dutos, tubos, eletrodutos), federação, interferências, pranchas | https://bonsaibim.org/ [CONFERIR] | extensão do Blender |
| FreeCAD (BIM, TechDraw, FEM, Assembly) | CAD mecânico de ponta a ponta | https://www.freecad.org/ [CONFERIR] | \`sudo apt install freecad\` |
| CfdOF (complemento do FreeCAD) | liga a peça ao OpenFOAM | Addon Manager do FreeCAD [CONFERIR] | dentro do FreeCAD |
| Dodo e KiCadStepUp (complementos) | tubulação/estruturas e chicotes/placas do KiCad | Addon Manager do FreeCAD [CONFERIR] | dentro do FreeCAD |
| OpenStudio + EnergyPlus | carga térmica e energia do prédio | https://openstudio.net/ · https://energyplus.net/ [CONFERIR] | instaladores .deb do site |
| IfcOpenShell | scripts Python que leem o IFC | https://ifcopenshell.org/ [CONFERIR] | \`pip install ifcopenshell\` |

Bibliotecas de fabricantes (ex.: BIMobject): só como fonte opcional de blocos IFC/STEP baixados e guardados no servidor
(regra 11: nada depende do site). Experimentais (acompanhar, não usar em produção): SolidCraft, BIMCraft, Construct CAD/Craft, Beamcraft [CONFERIR].

## 3. Física (multifísica e eletromagnetismo)

| Programa | Site oficial | Ubuntu |
|---|---|---|
| Elmer FEM | https://www.elmerfem.org/ [CONFERIR] | PPA do Elmer (ver site) |
| openEMS | https://www.openems.de/ [CONFERIR] | `sudo apt install openems` [CONFERIR nome do pacote] |
| Gazebo | https://gazebosim.org/docs [CONFERIR] | repositório OSRF (ver site) |
| LAMMPS | https://www.lammps.org/download.html [CONFERIR] | `sudo apt install lammps` |

## 4. Química (só abertos)

| Programa | Site oficial | Ubuntu |
|---|---|---|
| Avogadro 2 | https://two.avogadro.cc/ [CONFERIR] | `sudo apt install avogadro` [CONFERIR versão 2] |
| Psi4 | https://psicode.org/installs/latest/ [CONFERIR] | conda-forge (ver site) |
| RDKit | https://www.rdkit.org/ [CONFERIR] | `pip install rdkit` |

## 5. Biologia e bioinformática

| Programa | Site oficial | Ubuntu |
|---|---|---|
| GROMACS | https://www.gromacs.org/ [CONFERIR] | `sudo apt install gromacs` |
| COPASI | https://copasi.org/Download/ [CONFERIR] | instalador do site |
| CellBlender (MCell) | https://mcell.org/ [CONFERIR] | extensão do Blender (`sudo apt install blender`) |
| OpenSim | https://simtk.org/projects/opensim [CONFERIR] | instalador do site |

## 6. IoT, quadros elétricos e automação

| Programa | Para quê | Site oficial | Ubuntu |
|---|---|---|---|
| QElectroTech | diagramas de quadros elétricos | https://qelectrotech.org/ [CONFERIR] | `sudo apt install qelectrotech` |
| LibreCAD | furação da placa e recortes da porta em DXF (corte a laser/usinagem) | https://librecad.org/ [CONFERIR] | `sudo apt install librecad` |
| KiCad | placas das caixas de sensores (ESP32) | https://www.kicad.org/download/ [CONFERIR] | `sudo apt install kicad` |
| ESPHome | firmware da Caixinha | https://esphome.io/ [CONFERIR] | `pip install esphome` |

Quadros: QElectroTech para o diagrama (referências cruzadas, numeração de fios, réguas de bornes, BOM em CSV) e LibreCAD para a
furação/recortes em DXF. Normas (decisão da dona de 24/11/2026: "todas as normas"; conferir edição e vigência de cada uma antes de usar [CONFERIR]):
IEC 60617 (símbolos), IEC 61082 (documentação), IEC 81346 (designação de componentes), ABNT NBR 5410 (instalações de baixa
tensão), ABNT NBR IEC 61439-1/-2 (conjuntos de manobra e controle), IEC 60204-1 (equipamento elétrico de máquinas), ABNT NBR 5444
(símbolos gráficos; conferir se ainda vigente), NR-10 (segurança em eletricidade) e NR-12 (máquinas). Modelo de folha no
QElectroTech: A3 e A4, carimbo da Physis, colunas 1–8 e numeração de fios por potencial e folha [MARCADOR: carimbo com dados da empresa].

Kits de automação e sugestões iniciais: montados a partir dos documentos da Physis; o que não estiver neles fica [MARCADOR].

## 6b. AVAC central e automação predial (BMS) e solar

Protocolos abertos de campo para não depender de fabricante: **BACnet** (IP e MS/TP), **Modbus** (RTU/TCP) e **MQTT** (o servidor
da Physis já usa MQTT; BACnet e Modbus ainda não estão ligados ao servidor: [MARCADOR: próxima etapa]).

| Programa | Para quê | Site oficial | Ubuntu |
|---|---|---|---|
| Eclipse VOLTTRON | controle de AVAC central e energia (BACnet/Modbus) | https://volttron.org/ [CONFERIR] | pip/instalador do site |
| Node-RED | lógicas visuais e painéis web | https://nodered.org/ [CONFERIR] | `sudo npm install -g --unsafe-perm node-red` |
| OpenBMS | sequências de AVAC (ASHRAE) com BACnet/MQTT | https://www.openbms.io/ [CONFERIR licença] | ver site |
| ScadaBR / FUXA | supervisório web (CAG, alarmes, históricos) | https://www.scadabr.com.br/ · https://github.com/frangoteam/FUXA [CONFERIR] | ver site |
| OpenStudio + EnergyPlus | carga térmica por zona com EPW (INMET/LabEEE) | ver seção 2b | |
| SAM (NREL) | geração FV, strings e perdas | https://sam.nrel.gov/ [CONFERIR] | instalador do site |
| pvlib python | irradiação, tilt, pitch, inversores | https://pvlib-python.readthedocs.io/ [CONFERIR] | `pip install pvlib` |
| Blender Sun Position / Ladybug Tools | trajetória solar e sombras sobre o modelo IFC | dentro do Blender [CONFERIR] | |

Fluxo AVAC central: Bonsai (zonas IfcSpace, dutos IfcDuctSegment, tubos IfcPipeSegment, IfcDistributionSystem, interferências)
→ OpenStudio/EnergyPlus (carga por zona) → perda de carga em Python (Darcy-Weisbach, perda constante) → Bonsai (rede modelada)
→ QElectroTech + LibreCAD (quadros da CAG e fan coils). Fluxo solar: Bonsai (IfcSolarDevice) → SAM/pvlib → QElectroTech (unifilar,
string box). Calculadoras online de dutos: só conferência opcional (regra 11); a conta oficial fica no servidor.

## 6c. OCR, rede de água e validação

| Programa | Para quê | Windows (PC da Physis) | Ubuntu |
|---|---|---|---|
| Tesseract OCR (+ português) | nomes e medidas escritos em fotos e rascunhos | `winget install UB-Mannheim.TesseractOCR` (e o idioma "por") [CONFERIR] | `sudo apt install tesseract-ocr tesseract-ocr-por` |
| EPANET / WNTR | simular a rede de água gerada por ferramentas/rede_agua.py | `py -m pip install wntr` | `pip install wntr` |
| IfcOpenShell | conferir os IFC gerados | `py -m pip install ifcopenshell` | `pip install ifcopenshell` |

## 7. Impressão 3D (uma aba só: Peças 3D)

| Programa | Site oficial | Ubuntu |
|---|---|---|
| PrusaSlicer (fatiador do servidor) | https://www.prusa3d.com/page/prusaslicer_424/ [CONFERIR] | `sudo apt install prusa-slicer` |
| Blender (render, CellBlender) | https://www.blender.org/download/ [CONFERIR] | `sudo apt install blender` |

## 8. Camadas de mapa pendentes (pasta `PHYSIS_CAMADAS`)

Nenhuma vem pronta: baixar da fonte oficial, recortar a região dos projetos (QGIS ou GDAL) e salvar com o nome da coluna "Arquivo".
Ferramentas: `sudo apt install qgis gdal-bin`. Conferir a licença de cada base antes de usar.

| Camada | Arquivo | Fonte oficial | Onde baixar |
|---|---|---|---|
| Limites municipais | limites.geojson | IBGE · Malhas territoriais | https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais.html [CONFERIR] |
| Relevo | relevo.asc | Copernicus DEM GLO-30 / TOPODATA (INPE) | https://dataspace.copernicus.eu/ · http://www.dsr.inpe.br/topodata/ [CONFERIR] |
| Hidrografia | hidrografia.geojson | ANA · BHO | https://metadados.snirh.gov.br/ [CONFERIR]; depois `ferramentas/hidrografia_servidor.py` |
| Uso do solo | uso_solo.asc + legenda | MapBiomas | https://brasil.mapbiomas.org/ [CONFERIR] |
| Solos | solos.geojson | Embrapa / IBGE | https://geoinfo.dados.embrapa.br/ [CONFERIR] |
| CAR | car.geojson | SICAR | https://consultapublica.car.gov.br/ [CONFERIR] |
| Clima (EPW) | clima/*.epw | INMET convertido em EPW | https://climate.onebuilding.org/ [CONFERIR] |
| Risco | risco.geojson | SGB/CPRM · CEMADEN | https://rigeo.sgb.gov.br/ [CONFERIR] |
| Irradiação | irradiacao.asc | INPE/LABREN · Atlas Solar | https://labren.ccst.inpe.br/atlas_2017.html [CONFERIR] |
| Vento | vento.asc | CEPEL/CRESESB · Atlas Eólico | https://cresesb.cepel.br/ [CONFERIR] |
| Rede elétrica | rede_eletrica.geojson | ANEEL · SIGEL | https://sigel.aneel.gov.br/ [CONFERIR] |
| Edificações e vias | osm.geojson | OpenStreetMap (ODbL) | https://download.geofabrik.de/south-america/brazil.html [CONFERIR] |

Depois: `export PHYSIS_CAMADAS=/srv/physis/camadas` no serviço do servidor e conferir na aba Mapeamento (camada "instalada").
