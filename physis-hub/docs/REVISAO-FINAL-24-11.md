# Revisão final das inclusões · 24/11/2026

Revisão de tudo o que entrou de 22 a 24/11. Testes automáticos neste ambiente (Linux): **Sistema 1.513 OK** (12 pulados: precisam do
Edge/Windows ou de dados do OneDrive); **Instituto 1.254 OK** depois da correção: as 3 falhas antigas (ODF, espelho de carbono, paridade da simulação)
eram defeitos dos próprios testes (método faltando, argumento do Node, última casa decimal diferente entre Windows e Linux) e
foram corrigidas (instituto-revisao-24-11.patch). No PC da Physis: testes rápidos OK em 24/11; a bateria completa roda no
salvamento final (`--completo`).

| # | Inclusão | Como conferir (equipe) | Teste automático | Visto no navegador |
|---|---|---|---|---|
| 1 | Novo visual (guia de identidade) | Gestão, SustainKit, SCADA, Planejador | paleta e contraste | sim |
| 2 | Bots autônomos, sem Claude | M&A › Bots e comandos: pedido sem "/" | sim | — |
| 3 | IA Physis generativa local | `py -m physis_hub.mv_cli ia "pergunta"` | sim | modo generativa OK no PC da Physis |
| 4 | Planejador completo na Casa | Casa (8701) › Planejador › Módulos | sim | sim |
| 5 | Sprinklers e gêmeo digital (estático + simulado) | Planejador › Módulos | sim | sim |
| 6 | InovaSTEM: Impressão 3D única, Simulação por área, sem repetições | 8702/laboratorio | sim | sim |
| 7 | Edição manual de páginas | botão "Editar página" (com conta da direção) | sim | sim |
| 8 | AVAC completo (água gelada, pressão e NPSH, sauna, piscina, churrasqueira, tubulações, fiação, garagem, gás, CFM) | Estermic (8704) › Cálculo AVAC | sim | sim |
| 9 | Estermic à parte (8704), BIM antes do cálculo | http://localhost:8704 | sim | sim |
| 10 | IFC / PDF / rascunho → áreas, cálculo, DXF, IFC, .glb, render, OCR | Estermic › BIM e GIS | sim (IFC conferido no IfcOpenShell; .glb no trimesh) | sim |
| 11 | Simulações no servidor: CalculiX (suporte) e OpenFOAM (CFD de duto) | Estermic › Cálculo › Modelagens | sim (OpenFOAM a 7% de Darcy; CalculiX a 0,5% da conta) | sim |
| 12 | Seleção de modelos e fabricantes, blocos IFC | Estermic › Equipamentos | sim | sim |
| 13 | Fornecedores de AVAC (107 marcas) e bot de modelos dos catálogos | Gestão › Fornecedores; `/rodar modelos` | sim | — |
| 14 | Kit aprovado → documentos oficiais; tarefas Executar | `py -m physis_hub.mv_cli executar` | sim | rodado no PC da Physis (10 documentos) |
| 15 | Rede de água (EPANET) e camadas (IBGE, OSM) | ferramentas/rede_agua.py, baixar_camadas.py | sim (EPANET rodado) | — |
| 16 | Projetos municipais → Editais | ferramentas/municipais_para_editais.py | sim | prévia rodada no PC da Physis |
| 17 | Sentinela religa serviços caídos | alerta "religado" no M&A | sim | — |
| 18 | Atualização final e backup em zip | `py ferramentas\atualizacao_final.py --completo --salvar --backup` | sim | falta rodar com --backup |
| 19 | Verificador e lista de programas | `py ferramentas\verificar_programas.py` | — | rodado no PC da Physis |

## O que não dá para testar daqui (fica com a equipe)

- E-mail real (falta a senha de app do Microsoft 365; hoje a variável tem um texto de exemplo).
- Rede pública (26/11) e acesso da equipe pela rede local (firewall: LINKS-EQUIPE.md).
- OpenFOAM no Ubuntu do WSL (instalar com `sudo apt install openfoam`) e o render com o Blender do PC.
- Conteúdo: 58 documentos com falha pelas regras, 11 itens do kit que faltam, 7 a revisar, aprovações do grupo "Final 24/11".
