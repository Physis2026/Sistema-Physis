# Diagnóstico do Physis M&A · 23/11/2026 01:59
Computador: PC-Physis · Windows/SO: Windows-11-10.0.26300-SP0 · Python: 3.12.10
Instalação: C:\physis\physis-ma-20261122-1bd599e\physis-hub

## 1. Versão
- Git: 6643e5b · 2026-11-22 20:37:55 -0300 · Trabalho em andamento 22/11 (antes dos bots enxutos)
- **Há arquivos alterados sem commit nesta instalação** (guardar antes de atualizar):
  - M .gitattributes
  -  M .gitignore
  -  M app-nativo/site/baixar.html
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
  -  M ferramentas/documentos/backup_arquivos.py
  -  M ferramentas/documentos/gerar_memos.py
  -  M ferramentas/documentos/salvar_casa_physis.py
  -  M ferramentas/documentos/seed_sync.py
  -  M ferramentas/extrair_plantas.py
  -  M ferramentas/sincronizar.py
  -  M ferramentas/testes-navegador/gerar_harness.py
  -  M modulos/planejador/planejador-physis.html
  -  M physis-hub/docs/MV.md
  -  M physis-hub/estresse.py
  -  M physis-hub/physis_hub/mv.py
  -  M physis-hub/physis_hub/mv_bots.py
  -  M physis-hub/physis_hub/mv_cli.py
  -  M physis-hub/physis_hub/mv_comandos.py
  -  M physis-hub/physis_hub/mv_desenvolvimento.py
  -  M physis-hub/physis_hub/mv_mock.py
  -  M physis-hub/physis_hub/mv_paginas.py
  -  M physis-hub/physis_hub/mv_servidor.py
  -  M physis-hub/physis_hub/mv_sincronizacao.py
  -  M physis-hub/physis_hub/servidor.py
  -  M physis-hub/physis_hub/vento.py
  -  M physis-hub/tests/test_carbono_espelho.py
  -  M physis-hub/tests/test_odf.py
  -  M physis-hub/tests/test_preferencias_paginas.py
  -  M physis-hub/tests/test_simulacao_paridade.py
  -  M physis-hub/web/consultoria.html
  -  M physis-hub/web/documento.html
- Tem o trabalho do GitHub de 22/11 20h37 (6643e5b)? sim

## 2. Bots e módulos
- Bots instalados (29): acervo, atrasos, auditoria, backup, bancos, cursos, dados_iot, desenvolvimento, documentos, editais, fatos, financeiro, gestoes, ia, inovacao, kit, links, melhoria, mercado, paginas, repositorios, resumo, sala, semanal, sentinela, simulacao, sincronizacao, vencimentos, vigia

## 3. Agenda do Windows (PhysisMV)
- atrasos_8h: -20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots atrasos sala
- bots_hora: -hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots documentos dados_iot vigia sentinela
- hub: physis\physis-ma-20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.servidor
- painel: s\physis-ma-20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli servir
- resumo_7h: sis-ma-20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots diario
- revisao_semanal: -20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots semanal sala

## 4. Banco do M&A
- PHYSIS_MV_DADOS = C:\physis\dados
- Banco: C:\physis\dados\physis-mv.db · 2404 KB · alterado em 23/11/2026 01:25
- Tarefas: 430 · metas: 11 · alertas abertos: 180
- Tabela mv_alerta diferente do código: banco ['id', 'bot', 'tipo', 'ref', 'frente', 'gravidade', 'texto', 'acao', 'criado', 'visto', 'resolvido', 'responsavel', 'roteado_por'] × código ['id', 'bot', 'tipo', 'ref', 'frente', 'gravidade', 'texto', 'acao', 'criado', 'visto', 'resolvido']
- Tabela mv_lanc diferente do código: banco ['id', 'entidade', 'data', 'tipo', 'valor', 'descricao', 'projeto', 'fonte', 'conferido', 'criado', 'conta', 'subprojeto', 'sistema', 'loja', 'membro', 'cnpj_emissor', 'contrato', 'nf'] × código ['id', 'entidade', 'data', 'tipo', 'valor', 'descricao', 'projeto', 'fonte', 'conferido', 'criado']
- Última execução de cada bot:
  - acervo: há 1.7 h
  - atrasos: há 1.5 h
  - auditoria: há 0.3 h
  - backup: há 1.7 h
  - bancos: há 1.7 h
  - cli: há 2.3 h · ERRO: UnicodeEncodeError('charmap', '  →', 2, 3, 'character maps to <undefined>')
  - cursos: há 1.7 h
  - dados_iot: há 0.1 h
  - desenvolvimento: há 1.7 h
  - documentos: há 0.1 h
  - editais: há 1.7 h
  - fatos: há 1.7 h
  - financeiro: há 1.7 h
  - gestoes: há 1.7 h
  - ia: há 1.7 h
  - inovacao: há 19.0 h
  - kit: há 1.7 h
  - links: há 1.7 h
  - melhoria: há 1.7 h
  - paginas: há 1.7 h
  - radar: há 5.0 h
  - regressao: há 0.7 h
  - repositorios: há 1.7 h
  - resumo: há 1.5 h
  - sala: há 1.7 h
  - sentinela: há 0.1 h
  - simulacao: há 1.7 h
  - sinal: há 3.0 h · ERRO: KeyError('sinal')
  - sincronizacao: há 1.7 h
  - vencimentos: há 1.7 h
  - vigia: há 0.1 h
- Perguntas abertas na caixa: 41

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
- Instituto Physis em C:\physis\instituto-physis: 094e6e7 2026-11-22 02:45:31 -0300 Sincronização automática (M&A): originais compartilhados e cópias nas páginas
- Última sincronização: 23/11 00:16 · {"originais": {"sistema/physis-preferencias.js": {"fonte": "Instituto Physis", "commit": "2026-11-22 01:28"}, "sistema/physis-desenvolvimento.js": {"fonte": "Instituto Physis", "commit": "2026-11-22 02:45"}, "sistema/physis-modelador.js": {"fonte": "Instituto Physis", "commit": "2026-11-22 02:45"}, 

## 8. O que precisa ser atualizado
- Nada: esta instalação já está na versão final.
