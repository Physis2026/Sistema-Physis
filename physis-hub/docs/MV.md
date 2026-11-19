# Physis M&V (versão de teste)

Gestão de **nível 2** que junta as quatro frentes: Casa Physis, Physis Engineering, Instituto Physis e InovaSTEM, mais a frente
Transversal (jurídico, contábil, lote, marca e o próprio M&V). Cada plataforma continua com a sua Gestão interna. O M&V mede, cruza
prazos e dependências e avisa onde é preciso intervir. Decisões: documento 27 de `Sistema Physis` (D31 a D75).

## Onde está

| Parte | Arquivo |
|---|---|
| Núcleo (banco, CPM, visões, financeiro, alertas) | `physis_hub/mv.py` |
| Bots (atrasos, documentos, resumo) | `physis_hub/mv_bots.py` |
| Semente (metas 2027–2031, marcos, Fase 0 até 31/01/2027) | `physis_hub/mv_semente.py` |
| Servidor local + exportação | `physis_hub/mv_servidor.py` |
| Linha de comando e agenda do Windows | `physis_hub/mv_cli.py` |
| Tela | `web/mv.html` |
| Testes | `tests/test_mv.py` |

O banco é **próprio** (`physis-mv.db`) e fica **fora do OneDrive**, em `C:\physis\dados` ou em `PHYSIS_MV_DADOS`, porque a sincronização
corrompe SQLite. Os resumos diários vão para `Sistema Physis\28_Physis_MV\resumos` (`PHYSIS_MV_SAIDA`).

## Comandos

    cd physis-hub
    python -m physis_hub.mv_cli semear
    python -m physis_hub.mv_cli importar "<...>\Sistema Physis\18_Checklist_para_importar_na_Gestao.json"
    python -m physis_hub.mv_cli bots                # documentos, atrasos e resumo
    python -m physis_hub.mv_cli servir              # http://127.0.0.1:8710/
    python -m physis_hub.mv_cli agenda --criar      # tarefas agendadas do Windows (D58)
    python -m unittest tests.test_mv

## Visões
- **Saúde**: nota de 0 a 100 por frente. Perde, em proporção às tarefas abertas, até 50 pontos por atraso, 30 por bloqueio e 20 por prazo em risco. Mostra também alertas abertos, documentos e a última execução de cada bot.
- **Gantt e caminho crítico** (CPM em dias corridos): o caminho crítico é a sequência mais longa de cada cadeia de dependências com 2 ou mais tarefas. Uma tarefa fica com **prazo em risco** quando as dependências empurram o fim para depois do prazo. Data estimada aparece tracejada, com [CONFERIR].
- **Kanban** com troca de estado. Ao bloquear uma tarefa, a tela pede o motivo e de quem ela depende.
- **Matriz de pendências**: tarefas abertas, atrasadas e bloqueadas por pessoa e por frente.
- **Roadmap 2027–2031**: metas, marcos e quantas tarefas sustentam cada meta. Também mostra quantas tarefas ainda não estão ligadas a nenhuma meta.
- **Alertas e intervenções**, **Documentos** e **Financeiro**. No financeiro, cada entidade aparece separada e nunca somada às outras. O que não foi conferido pelo contador fica "a conferir" (D70).
- **Download** de cada visão em ODS, ODT ou PDF/A. O PDF precisa do LibreOffice (`soffice`); sem ele, o servidor avisa e oferece ODT ou ODS.

## Bots (rodam sozinhos, D56 e D58)
- **atrasos** (de hora em hora), que detecta:
  - tarefa vencida, com a intervenção sugerida (replanejar, resolver o bloqueio, dividir em entregas menores ou reatribuir);
  - tarefa bloqueada;
  - dependência ainda aberta a até 3 dias do início;
  - prazo em risco;
  - ciclo de dependências;
  - tarefa sem responsável;
  - data estimada no caminho crítico.
- **documentos** (de hora em hora): varre `Casa Physis`, `Sistema Physis` e `Instituto Physis` (sem as pastas de código, backup e kits) e confere:
  - **idade × validade** por tipo: apresentação 90 dias, contrato 365, planilha 180, memo 30, plano 180, documento 180. A idade vem da data gravada dentro do arquivo, então uma cópia recente de conteúdo antigo continua velha;
  - **regras das decisões**: horizonte 2031 (D40), sede no Brasil (D42), grafia Rafaella (D61), S2 Services é SARL (D66), bônus sobre vendas (D34);
  - **marcadores** ([MARCADOR], [A PREENCHER], [CONFERIR], "a definir");
  - **falha de template**: autor e data falsos deixados pelo gerador (python-docx ou python-pptx, "Steve Canny", 2013).
  Cada documento com falha vira alerta e uma tarefa "Corrigir…".
- **resumo** (diário, às 7h): Markdown e ODT com a saúde, os alertas que pedem intervenção, o caminho crítico dos próximos 14 dias e os documentos com falha.

Os alertas são idempotentes: o mesmo problema não se repete e é fechado sozinho quando some. Nada sai para fora: e-mails e documentos
continuam passando por aprovação humana (D49).

## Segurança (fase de teste)
Ouve só em `127.0.0.1` e confere o cabeçalho Host. Todo POST exige o cabeçalho `X-Physis-MV: 1`, que uma página de outro site não consegue enviar.
Na migração para o servidor físico (dezembro, Eric), entram as contas e os papéis da Gestão e o HTTPS pelo proxy.

## Ainda não feito (próximas entregas)
- Editais (26/11), bots por frente, bot do acervo → trilhas (30/11), parceiros e fornecedores com a fila de e-mails.
- Leitura direta das Gestões internas em vez da exportação JSON.
- IA (Claude, teto de US$ 50/mês) nos bots de editais e acervo. Os bots desta versão funcionam só por regras.
