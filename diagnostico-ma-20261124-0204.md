# Diagnóstico do Physis M&A · 24/11/2026 02:04
Computador: PC-Physis · Windows/SO: Windows-11-10.0.26300-SP0 · Python: 3.12.10
Instalação: C:\physis\physis-ma-20261122-1bd599e\physis-hub

## 1. Versão
- Git: 7edad18 · 2026-11-23 22:13:53 -0300 · Marketing com aprovacao no M&A, fila do Claude, conta para edital, teste zero e backup completo
- **Há arquivos alterados sem commit nesta instalação** (guardar antes de atualizar):
  - M .gitignore
  -  M app-nativo/site/baixar.html
  -  M demos/gerar_demos.py
  -  M demos/physis-demo-casa-physis-inicial.html
  -  M demos/physis-demo-casa-physis.html
  -  M demos/physis-demo-cliente.html
  -  M demos/physis-demo-fazenda-mf.html
  -  M demos/physis-demo-monitoramento.html
  -  M demos/physis-demo-planejador.html
  -  M demos/physis-demo-santa-clara-v2.html
  -  M demos/physis-demo-santa-clara.html
  -  M demos/physis-demo-scada.html
  -  M demos/physis-demo-sustainkit.html
  -  M ferramentas/sincronizar.py
  -  M ferramentas/teste_zero.py
  -  M modulos/modelagem3d/modelagem-3d.html
  -  M modulos/planejador/planejador-physis.html
  -  M physis-hub/docs/VARIAVEIS.md
  -  M physis-hub/montar.py
  -  M physis-hub/physis_hub/ia_physis.py
  -  M physis-hub/physis_hub/mv_bots_extra.py
  -  M physis-hub/physis_hub/mv_cli.py
  -  M physis-hub/physis_hub/mv_clientes.py
  -  M physis-hub/physis_hub/mv_comandos.py
  -  M physis-hub/physis_hub/mv_vigia.py
  -  M physis-hub/physis_hub/servidor.py
  -  M physis-hub/tests/test_fila_e_edital.py
  -  M physis-hub/tests/test_marketing_ma.py
  -  M physis-hub/tests/test_mv_clientes.py
  -  M physis-hub/tests/test_mv_comandos.py
  -  M physis-hub/tests/test_preferencias_paginas.py
  -  M physis-hub/tests/test_sem_internet.py
  -  M physis-hub/tests/test_vendor.py
  -  M physis-hub/web/consultoria.html
  -  M physis-hub/web/documento.html
  -  M physis-hub/web/municipio.html
  -  M physis-hub/web/mv.html
  -  M physis-hub/web/painel.html
  -  M sistema/SustainKit_Definitivo.html
  -  M sistema/gestao-interna-physis.html
- Tem o trabalho do GitHub de 22/11 20h37 (6643e5b)? sim

## 2. Bots e módulos
- Bots instalados (29): acervo, atrasos, auditoria, backup, bancos, cursos, dados_iot, desenvolvimento, documentos, editais, fatos, financeiro, gestoes, ia, inovacao, kit, links, melhoria, mercado, paginas, repositorios, resumo, sala, semanal, sentinela, simulacao, sincronizacao, vencimentos, vigia

## 3. Agenda do Windows (PhysisMV)
- atrasos_8h: -20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots atrasos sala
- bots_hora:  "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots documentos gestoes dados_iot vigia sentinela
- hub: physis\physis-ma-20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.servidor
- painel: s\physis-ma-20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli servir
- resumo_7h: sis-ma-20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots diario
- revisao_semanal: -20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots semanal sala

## 4. Banco do M&A
- PHYSIS_MV_DADOS = C:\physis\dados
- Banco: C:\physis\dados\physis-mv.db · 2688 KB · alterado em 24/11/2026 00:07
- Tarefas: 855 · metas: 11 · alertas abertos: 11
- Tabela mv_alerta diferente do código: banco ['id', 'bot', 'tipo', 'ref', 'frente', 'gravidade', 'texto', 'acao', 'criado', 'visto', 'resolvido', 'responsavel', 'roteado_por'] × código ['id', 'bot', 'tipo', 'ref', 'frente', 'gravidade', 'texto', 'acao', 'criado', 'visto', 'resolvido']
- Tabela mv_lanc diferente do código: banco ['id', 'entidade', 'data', 'tipo', 'valor', 'descricao', 'projeto', 'fonte', 'conferido', 'criado', 'conta', 'subprojeto', 'sistema', 'loja', 'membro', 'cnpj_emissor', 'contrato', 'nf'] × código ['id', 'entidade', 'data', 'tipo', 'valor', 'descricao', 'projeto', 'fonte', 'conferido', 'criado']
- Última execução de cada bot:
  - acervo: há 10.7 h
  - atrasos: há 0.5 h
  - auditoria: há 4.0 h
  - backup: há 10.7 h
  - bancos: há 10.7 h
  - cli: há 26.4 h · ERRO: UnicodeEncodeError('charmap', '  →', 2, 3, 'character maps to <undefined>')
  - cursos: há 10.7 h
  - dados_iot: há 1.0 h
  - desenvolvimento: há 0.5 h
  - documentos: há 0.5 h
  - editais: há 10.7 h
  - fatos: há 10.7 h
  - financeiro: há 10.7 h
  - gestoes: há 1.0 h
  - ia: há 10.7 h
  - inovacao: há 19.1 h
  - kit: há 0.5 h
  - links: há 10.7 h
  - melhoria: há 10.7 h
  - paginas: há 10.7 h
  - radar: há 29.0 h
  - regressao: há 0.2 h
  - repositorios: há 10.7 h
  - resumo: há 0.5 h
  - sala: há 0.5 h
  - semanal: há 20.1 h
  - sentinela: há 1.0 h
  - simulacao: há 10.7 h
  - sinal: há 27.1 h · ERRO: KeyError('sinal')
  - sincronizacao: há 0.5 h
  - vencimentos: há 10.7 h
  - vigia: há 1.0 h
- Perguntas abertas na caixa: 0

## 5. Servidor do M&A (http://127.0.0.1:8710)
- /api/mv/saude: responde (200)
- /api/mv/integracoes: responde (200)
- /api/mv/ia?q=agua: responde (200)

## 6. Pastas do OneDrive lidas pelos bots
- Documents: C:\Users\rafae\OneDrive - Physis Engineering\Documents
- Sistema Physis: OK (Sistema Physis)
- Casa Physis: OK (Casa Physis)
- Instituto Physis: OK (Instituto Physis)
- Global Sourh Alliance: OK (Global Sourh Alliance)
- Estermic: OK (Estermic)
- C:\Users\rafae\OneDrive - Physis Engineering\Documents\Marketing Physis: existe · Git: sem commit

## 7. Integração (Instituto Physis e sincronização)
- Instituto Physis em C:\physis\instituto-physis: a63a562 2026-11-24 01:28:30 -0300 InovaSTEM: uma aba de Impressao 3D (fila dentro), Simulacao por area com previsao da modelagem e programas abertos, sem terreno/construcao, sem repeticoes
- Última sincronização: 24/11 01:35 · {"originais": {"sistema/physis-preferencias.js": {"fonte": "Instituto Physis", "commit": "2026-11-22 01:28"}, "sistema/physis-desenvolvimento.js": {"fonte": "Instituto Physis", "commit": "2026-11-22 02:45"}, "sistema/explica-inovastem.js": {"fonte": "InovaSTEM (ramo inovastem)", "commit": "2026-11-2

## 8. O que precisa ser atualizado
- [ ] Bots sem rodar há mais de 26 h: cli, radar, sinal (agenda parada ou computador desligado)

Para atualizar: PASSO-A-PASSO-ATUALIZADO.md (área de arquivos). Mande este relatório para a equipe.
