# Diagnóstico do Physis M&A · 24/11/2026 15:38
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
  -  M physis-hub/docs/LISTA-DE-MODIFICACOES.md
  -  M physis-hub/docs/MV.md
  -  M physis-hub/docs/VARIAVEIS.md
  -  M physis-hub/montar.py
  -  M physis-hub/physis_hub/fornecedores.py
  -  M physis-hub/physis_hub/ia_physis.py
  -  M physis-hub/physis_hub/mv_auditoria.py
  -  M physis-hub/physis_hub/mv_bots.py
  -  M physis-hub/physis_hub/mv_bots_extra.py
  -  M physis-hub/physis_hub/mv_cli.py
  -  M physis-hub/physis_hub/mv_clientes.py
  -  M physis-hub/physis_hub/mv_comandos.py
  -  M physis-hub/physis_hub/mv_desenvolvimento.py
  -  M physis-hub/physis_hub/mv_integracoes.py
  -  M physis-hub/physis_hub/mv_kit.py
  -  M physis-hub/physis_hub/mv_sala.py
  -  M physis-hub/physis_hub/mv_vigia.py
  -  M physis-hub/physis_hub/servidor.py
  -  M physis-hub/tests/test_fila_e_edital.py
  -  M physis-hub/tests/test_marketing_ma.py
  -  M physis-hub/tests/test_mv_clientes.py
  -  M physis-hub/tests/test_mv_comandos.py
  -  M physis-hub/tests/test_preferencias_paginas.py
- Tem o trabalho do GitHub de 22/11 20h37 (6643e5b)? sim

## 2. Bots e módulos
- Bots instalados (30): acervo, atrasos, auditoria, backup, bancos, cursos, dados_iot, desenvolvimento, documentos, editais, fatos, financeiro, gestoes, ia, inovacao, kit, links, melhoria, mercado, modelos, paginas, repositorios, resumo, sala, semanal, sentinela, simulacao, sincronizacao, vencimentos, vigia

## 3. Agenda do Windows (PhysisMV)
- atrasos_8h: -20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots atrasos sala
- bots_hora:  "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots documentos gestoes dados_iot vigia sentinela
- hub: physis\physis-ma-20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.servidor
- painel: s\physis-ma-20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli servir
- resumo_7h: sis-ma-20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots diario
- revisao_semanal: -20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots semanal sala

## 4. Banco do M&A
- PHYSIS_MV_DADOS = C:\physis\dados
- Banco: C:\physis\dados\physis-mv.db · 2808 KB · alterado em 24/11/2026 12:48
- Tarefas: 869 · metas: 11 · alertas abertos: 44
- Tabela mv_alerta diferente do código: banco ['id', 'bot', 'tipo', 'ref', 'frente', 'gravidade', 'texto', 'acao', 'criado', 'visto', 'resolvido', 'responsavel', 'roteado_por'] × código ['id', 'bot', 'tipo', 'ref', 'frente', 'gravidade', 'texto', 'acao', 'criado', 'visto', 'resolvido']
- Tabela mv_lanc diferente do código: banco ['id', 'entidade', 'data', 'tipo', 'valor', 'descricao', 'projeto', 'fonte', 'conferido', 'criado', 'conta', 'subprojeto', 'sistema', 'loja', 'membro', 'cnpj_emissor', 'contrato', 'nf'] × código ['id', 'entidade', 'data', 'tipo', 'valor', 'descricao', 'projeto', 'fonte', 'conferido', 'criado']
- Última execução de cada bot:
  - acervo: há 8.6 h
  - atrasos: há 3.8 h
  - auditoria: há 8.6 h
  - backup: há 8.6 h
  - bancos: há 8.6 h
  - cli: há 40.0 h · ERRO: UnicodeEncodeError('charmap', '  →', 2, 3, 'character maps to <undefined>')
  - cursos: há 8.6 h
  - dados_iot: há 0.8 h
  - desenvolvimento: há 8.6 h
  - documentos: há 0.8 h
  - editais: há 8.6 h
  - fatos: há 8.6 h
  - financeiro: há 8.6 h
  - gestoes: há 0.8 h
  - ia: há 8.6 h
  - inovacao: há 8.6 h
  - kit: há 8.6 h
  - links: há 8.6 h
  - melhoria: há 8.6 h
  - paginas: há 8.6 h
  - radar: há 42.6 h
  - regressao: há 0.9 h
  - repositorios: há 8.6 h
  - resumo: há 8.6 h
  - sala: há 3.8 h
  - semanal: há 33.6 h
  - sentinela: há 0.8 h
  - simulacao: há 8.6 h
  - sinal: há 40.6 h · ERRO: KeyError('sinal')
  - sincronizacao: há 8.6 h
  - vencimentos: há 8.6 h
  - vigia: há 0.8 h
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
- Instituto Physis em C:\physis\instituto-physis: c82df45 2026-11-24 04:19:28 -0300 InovaSTEM Delas: sem o titulo repetido na aba
- Última sincronização: 24/11 07:01 · {"originais": {"sistema/physis-preferencias.js": {"fonte": "Sistema Physis (teste)", "commit": "2026-11-24 01:34"}, "sistema/physis-desenvolvimento.js": {"fonte": "InovaSTEM (ramo inovastem)", "commit": "2026-11-24 01:35"}, "sistema/explica-inovastem.js": {"fonte": "InovaSTEM (ramo inovastem)", "com

## 8. O que precisa ser atualizado
- [ ] Bots sem rodar há mais de 26 h: cli, radar, semanal, sinal (agenda parada ou computador desligado)

Para atualizar: PASSO-A-PASSO-ATUALIZADO.md (área de arquivos). Mande este relatório para a equipe.
