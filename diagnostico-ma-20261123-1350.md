# Diagnóstico do Physis M&A · 23/11/2026 13:50
Computador: PC-Physis · Windows/SO: Windows-11-10.0.26300-SP0 · Python: 3.12.10
Instalação: C:\physis\physis-ma-20261122-1bd599e\physis-hub

## 1. Versão
- Git: ebada82 · 2026-11-23 02:22:33 -0300 · Implementacao final do M&A 23/11/2026: 29 bots, pastas do OneDrive, aprovacoes, alertas, Hub e correcoes
- **Há arquivos alterados sem commit nesta instalação** (guardar antes de atualizar):
  - M physis-hub/physis_hub/mv_bots.py
  - ?? INSTALAR-PHYSIS.bat
  - ?? LEIA-ME.txt
  - ?? atualizacao-physis-2026-11-22.patch
  - ?? diagnostico-ma-20261123-0159.md
  - ?? diagnostico_ma.py
  - ?? guias/
  - ?? instalar_tudo.py
  - ?? physis-hub/diagnostico-ma-20261122-2243.md
  - ?? physis-hub/tests/test_sem_regras_registros.py
  - ?? teste-arquivos-20261123-0153.md
  - ?? teste-arquivos-20261123-0154.md
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
- Tarefas: 430 · metas: 11 · alertas abertos: 192
- Tabela mv_alerta diferente do código: banco ['id', 'bot', 'tipo', 'ref', 'frente', 'gravidade', 'texto', 'acao', 'criado', 'visto', 'resolvido', 'responsavel', 'roteado_por'] × código ['id', 'bot', 'tipo', 'ref', 'frente', 'gravidade', 'texto', 'acao', 'criado', 'visto', 'resolvido']
- Tabela mv_lanc diferente do código: banco ['id', 'entidade', 'data', 'tipo', 'valor', 'descricao', 'projeto', 'fonte', 'conferido', 'criado', 'conta', 'subprojeto', 'sistema', 'loja', 'membro', 'cnpj_emissor', 'contrato', 'nf'] × código ['id', 'entidade', 'data', 'tipo', 'valor', 'descricao', 'projeto', 'fonte', 'conferido', 'criado']
- Última execução de cada bot:
  - acervo: há 6.8 h
  - atrasos: há 5.0 h
  - auditoria: há 6.8 h
  - backup: há 6.8 h
  - bancos: há 6.8 h
  - cli: há 14.2 h · ERRO: UnicodeEncodeError('charmap', '  →', 2, 3, 'character maps to <undefined>')
  - cursos: há 6.8 h
  - dados_iot: há 1.0 h
  - desenvolvimento: há 6.8 h
  - documentos: há 1.0 h
  - editais: há 6.8 h
  - fatos: há 6.8 h
  - financeiro: há 6.8 h
  - gestoes: há 6.8 h
  - ia: há 6.8 h
  - inovacao: há 6.8 h
  - kit: há 6.8 h
  - links: há 6.8 h
  - melhoria: há 6.8 h
  - paginas: há 6.8 h
  - radar: há 16.8 h
  - regressao: há 0.0 h
  - repositorios: há 6.8 h
  - resumo: há 6.8 h
  - sala: há 5.0 h
  - semanal: há 7.8 h
  - sentinela: há 1.0 h
  - simulacao: há 6.8 h
  - sinal: há 14.8 h · ERRO: KeyError('sinal')
  - sincronizacao: há 6.8 h
  - vencimentos: há 6.8 h
  - vigia: há 1.0 h
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
- Última sincronização: 23/11 07:00 · {"originais": {"sistema/physis-preferencias.js": {"fonte": "Instituto Physis", "commit": "2026-11-22 01:28"}, "sistema/physis-desenvolvimento.js": {"fonte": "Instituto Physis", "commit": "2026-11-22 02:45"}, "sistema/physis-modelador.js": {"fonte": "Instituto Physis", "commit": "2026-11-22 02:45"}, 

## 8. O que precisa ser atualizado
- Nada: esta instalação já está na versão final.
