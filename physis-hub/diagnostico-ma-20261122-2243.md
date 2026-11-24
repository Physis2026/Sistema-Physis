# Diagnóstico do Physis M&A · 22/11/2026 22:43
Computador: PC-Physis · Windows/SO: Windows-11-10.0.26300-SP0 · Python: 3.12.10
Instalação: C:\physis\physis-ma-20261122-1bd599e\physis-hub

## 1. Versão
- Git: 6643e5b Â· 2026-11-22 20:37:55 -0300 Â· Trabalho em andamento 22/11 (antes dos bots enxutos)
- **Há arquivos alterados sem commit nesta instalação** (guardar antes de atualizar).
- Tem o trabalho do GitHub de 22/11 20h37 (6643e5b)? sim

## 2. Bots e módulos
- Bots instalados (9): atrasos, backup, desenvolvimento, documentos, inovacao, links, paginas, resumo, sincronizacao

## 3. Agenda do Windows (PhysisMV)
- bots_8h: 122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots atrasos documentos
- resumo_7h: a\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots atrasos documentos resumo backup paginas inovacao links vencimentos
- semanal: ysis-ma-20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots radar
- sinal_hora: ysis-ma-20261122-1bd599e\physis-hub" && "C:\Users\rafae\AppData\Local\Programs\Python\Python312\pythonw.exe" -m physis_hub.mv_cli bots sinal

## 4. Banco do M&A
- PHYSIS_MV_DADOS = C:\physis\dados
- Banco: C:\physis\dados\physis-mv.db · 2248 KB · alterado em 22/11/2026 22:33
- Tarefas: 428 · metas: 11 · alertas abertos: 210
- Última execução de cada bot:
  - atrasos: há 1.7 h
  - backup: há 15.7 h
  - desenvolvimento: há 3.0 h
  - documentos: há 1.7 h
  - inovacao: há 15.7 h
  - links: há 15.7 h
  - paginas: há 15.7 h
  - radar: há 1.7 h
  - regressao: há 0.2 h
  - resumo: há 1.7 h
  - sincronizacao: há 3.0 h
  - vencimentos: há 1.7 h
- Perguntas abertas na caixa: 1

## 5. Servidor do M&A (http://127.0.0.1:8710)
- /api/mv/saude: responde (200)
- /api/mv/integracoes: HTTP 404
- /api/mv/ia?q=agua: HTTP 404

## 6. Marketing Physis
- C:\Users\rafae\OneDrive - Physis Engineering\Documents\Marketing Physis: existe · Git: sem commit

## 7. O que precisa ser atualizado
- [ ] Bots que faltam (20): acervo, auditoria, bancos, cursos, dados_iot, editais, fatos, financeiro, gestoes, ia, kit, melhoria, mercado, repositorios, sala, semanal, sentinela, simulacao, vencimentos, vigia
- [ ] Módulo mv_vigia.py (vigia e sentinela)
- [ ] Módulo mv_sala.py (sala dos bots)
- [ ] Módulo mv_bots_extra.py (editais, dados-iot, simulação, gestões, bancos, acervo)
- [ ] Módulo ia_physis.py (IA Physis)
- [ ] Módulo mv_cursos.py (mapa de cursos)
- [ ] Módulo mv_integracoes.py (aba Monitoramento)
- [ ] Módulo mv_auditoria.py (auditoria e caixa de perguntas)
- [ ] Módulo mv_ecossistema.py (mercado e parcerias (GIS))
- [ ] Módulo mv_financeiro.py (financeiro e vencimentos)
- [ ] Módulo mv_kit.py (kit 26/11, melhoria, semanal)
- [ ] Módulo mv_fatos.py (base de fatos)
- [ ] Módulo mv_repositorios.py (repositórios (Marketing Physis))
- [ ] Aba Monitoramento no mv.html
- [ ] Tarefa PhysisMV\atrasos_8h não existe (agenda da versão final)
- [ ] Tarefa PhysisMV\bots_hora não existe (agenda da versão final)
- [ ] Tarefa PhysisMV\painel não existe (agenda da versão final)
- [ ] Tarefa PhysisMV\revisao_semanal não existe (agenda da versão final)
- [ ] Rota /api/mv/integracoes (aba Monitoramento) não existe no servidor que está rodando
- [ ] Rota /api/mv/ia?q=agua (IA Physis) não existe no servidor que está rodando

Para atualizar: PASSO-A-PASSO-ATUALIZADO.md (área de arquivos). Mande este relatório para a equipe.
