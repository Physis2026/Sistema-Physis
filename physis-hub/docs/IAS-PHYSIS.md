# As IAs da Physis (27/11/2026)

Nenhuma depende de serviço de terceiros (regra 11). O Claude **não** é usado pelo sistema (decisão da dona, 24/11 e 27/11/2026):
uma chave do Claude no ambiente é ignorada; só `PHYSIS_CLAUDE_PERMITIDO=1`, ligado à mão por quem administra, o colocaria na frente.

| IA | Onde roda | O que faz | Limites |
|---|---|---|---|
| **Regras (intenções)** | servidor, sem modelo | Reconhece pedidos comuns e roda o comando local: e-mail, checklist, contrato/ofício/termo/ata/proposta, atrasadas, rodar bots | Só os padrões conhecidos |
| **Ações do sistema** (`mv_autonomo.interpretar_acao`) | servidor, sem modelo | Pedido no imperativo para usar o sistema: criar tarefa (título, responsável, prazo, frente), programar bot, concluir tarefa. Mostra o que vai fazer e **só executa depois da aprovação** | Ação que ainda não sabe fazer vira "ação não reconhecida" (lista de melhorias), nada é mudado |
| **IA Physis extrativa** (`ia_physis`) | servidor, índice SQLite FTS5 | Responde com frases que existem nos documentos, cada uma com a fonte [n] | Não escreve fato novo; sem base, "[MARCADOR] Sem base nos documentos" |
| **IA Physis generativa** (`ia_generativa`) | servidor, modelo aberto no Ollama (padrão qwen2.5:7b) | Escreve o rascunho (resposta, e-mail, ata, proposta, post...) só com os trechos achados + as regras + as decisões da dona; número sem origem vira [MARCADOR] | Lenta em CPU; sem o modelo, cai na extrativa |
| **Robôs do hub** (`robos.py`: suporte, preços, editais, marketing, projetos, pluviômetro) | servidor | Respostas por regras; a IA local só melhora o texto | Revisão humana obrigatória |
| **Transcrição** (faster-whisper) | servidor | Áudio → texto, local | — |

Fluxo de um texto livre na caixa de comandos do M&A: pergunta → regras → ação do sistema? → IA (extrativa na hora, generativa
em segundo plano) → **rascunho** na aba Bots e comandos → você aprova, pede ajuste ou descarta. Nada sai sozinho.
Pedido que nem a IA local respondeu fica em `28_Physis_MV/fila-pedidos.md` (antes "fila-claude.md") e vira alerta com 24 h.
