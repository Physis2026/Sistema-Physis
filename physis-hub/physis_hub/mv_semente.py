"""Semente do Physis M&V (versão de teste): metas 2027–2031, marcos e a Fase 0 jurídica/contábil até 31/01/2027,
a partir do documento 27 (decisões D31–D74) e da revisão estrutural de 18/11/2026.

Regra: nenhum número inventado. Metas sem alvo numérico confirmado ficam com alvo "[MARCADOR]". As datas da Fase 0 são
o plano proposto (D44, D55): tarefas com data_estimada=1 até a dona confirmar. Rodar de novo é seguro (INSERT OR REPLACE
mantém o estado já marcado pela equipe).
"""
from __future__ import annotations

from .mv import MV

FONTE27 = "Sistema Physis/27_Decisoes_Fase2_Estrutura_e_Physis_MV.md"
FONTE_REV = "Revisão estrutural Physis + Instituto + Casa (18/11/2026)"

METAS = [
    # id, frente, ano, título, indicador, alvo, fonte
    ("m-transv-fase0", "transversal", 2027, "Fase 0 fechada: Instituto e Casa Physis com CNPJ, contratos J5–J8 assinados",
     "Documentos J1–J8 e C1–C5 aprovados", "31/01/2027", FONTE27 + " (D44, D60)"),
    ("m-eng-sistema", "engineering", 2027, "Sistema Physis vendido: loja, plataforma do cliente e consultoria operando",
     "Módulos publicados na loja", "8 módulos (memo 07)", "19_Memos_Fase2/07"),
    ("m-inst-ict", "instituto", 2027, "Instituto Physis como ICT com política de inovação e NIT, apto a editais de PDI",
     "Editais submetidos / aprovados", "[MARCADOR]", FONTE_REV),
    ("m-inovastem-piloto", "inovastem", 2027, "Piloto InovaSTEM (trilhas T1 e T2)", "Participantes e taxa de conclusão",
     "20–25 mulheres; 80% de conclusão", FONTE_REV + " (O3)"),
    ("m-gsa", "transversal", 2027, "Global South Alliance ativa (Physis agora, Instituto depois)", "Contrato associativo e evento Rio 2027",
     "[MARCADOR]", FONTE27 + " (D67)"),
    ("m-casa-obra", "casa", 2028, "Lote 168 implantado (preparação + 24 meses)", "Avanço físico-financeiro",
     "R$ 2.005.461 com 15% de contingência", "Documento Técnico Instituto Physis e Lote 168 (4.4)"),
    ("m-inst-tea", "instituto", 2028, "Centro de apoio TEA (clínico ou socioassistencial, a definir)", "Centro em operação",
     "1,5 a 2 anos", FONTE27 + " (D35)"),
    ("m-casa-operacao", "casa", 2029, "Casa Physis operando: hospedagem, A&B, loja e óleos", "Receita do ano 3 (cenário base)",
     "R$ 1.195.625 (cenário base, a conferir)", "Documento Técnico 4.4 / 15_Plano_de_Negocios"),
    ("m-inovastem-hackathon", "inovastem", 2027, "Hackathon online InovaSTEM de segurança cibernética",
     "Inscritas/os, equipes e desafios concluídos", "[MARCADOR]", FONTE27 + " (D75)"),
    ("m-inovastem-rede", "inovastem", 2031, "Rede InovaSTEM consolidada (incl. InovaSTEM Delas)", "Pessoas formadas e polos",
     "[MARCADOR]", FONTE_REV),
    ("m-eng-2031", "engineering", 2031, "Physis Engineering: carteira e licenças (meta de 5 anos)", "Receita recorrente",
     "[MARCADOR]", "Physis 2027-2031 Strategic Architecture (EN)"),
]

MARCOS = [
    ("k-mv-teste", "transversal", "2026-11-22", "Physis M&V em versão de teste", "m-transv-fase0", "Fase 2"),
    ("k-editais", "engineering", "2026-11-26", "Editais: caixa de entrada, estratégia e cronograma (teste)", "m-inst-ict", "Fase 2"),
    ("k-cursos", "inovastem", "2026-11-30", "Bot do acervo → trilhas de cursos (teste)", "m-inovastem-piloto", "Fase 2"),
    ("k-servidor", "transversal", "2026-12-20", "M&V e bots migrados para o servidor físico", "m-transv-fase0", "Fase 2"),
    ("k-fase0", "transversal", "2027-01-31", "Fase 0 fechada", "m-transv-fase0", "Fase 0"),
    ("k-inovastem", "inovastem", "2027-12-31", "Piloto InovaSTEM concluído [CONFERIR data]", "m-inovastem-piloto", "2027"),
    ("k-hackathon", "inovastem", "2027-06-30", "Hackathon online de segurança cibernética [CONFERIR data]", "m-inovastem-hackathon", "2027"),
    ("k-tea", "instituto", "2028-11-30", "Centro de apoio TEA [CONFERIR data]", "m-inst-tea", "2028"),
    ("k-obra", "casa", "2028-12-31", "Fim da implantação do lote [CONFERIR]", "m-casa-obra", "2028"),
    ("k-2031", "transversal", "2031-12-31", "Metas de 5 anos (2027–2031)", None, "2031"),
]

# id, frente, título, responsável, início, fim, depende_de, prioridade, meta, projeto
FASE0 = [
    # --- correções urgentes e pacote ao contador
    ("f0-docs-correcoes", "transversal", "Corrigir documentos: 2032→2031 (Docs 1–3 e Master), sede no Brasil, 'Rafaella', S2 Services é SARL (não ONG), bônus suspenso",
     "Rafaella", "2026-11-19", "2026-11-24", [], 1, "m-transv-fase0", "Correções D40/D42/D61/D66"),
    ("f0-d37-cenarios", "instituto", "D37: cenários Physis 3D e contrato da equipe (ganho Instituto × Casa/Engineering, riscos)",
     "Rafaella", "2026-11-19", "2026-11-24", [], 1, "m-inst-ict", "Fase 0 · estrutura"),
    ("f0-pacote-contador", "transversal", "Pacote do contador: Documento Técnico v2, e-mail revisado, perguntas A–E + D32b, D33, D34, D38, D39, D66, D68",
     "Rafaella", "2026-11-25", "2026-11-25", ["f0-docs-correcoes", "f0-d37-cenarios"], 0, "m-transv-fase0", "Fase 0 · contábil"),
    ("f0-advogado", "transversal", "Escolher advogado(a) com experiência em OSC/ICT/MROSC", "Rafaella", "2026-11-19", "2026-11-28", [], 1,
     "m-transv-fase0", "Fase 0 · jurídico"),
    ("f0-envio-contador", "transversal", "Enviar o pacote ao contador (rascunho aprovado pela dona)", "Rafaella", "2026-11-26", "2026-11-26",
     ["f0-pacote-contador"], 0, "m-transv-fase0", "Fase 0 · contábil"),
    ("f0-resp-contador", "transversal", "Receber e registrar as respostas do contador", "Contador [MARCADOR]", "2026-11-27", "2026-12-10",
     ["f0-envio-contador"], 1, "m-transv-fase0", "Fase 0 · contábil"),
    ("f0-lote-escritura", "transversal", "Lote 168: escritura e registro no RGI de Petrópolis (ITBI) — PRIORIDADE JURÍDICA 1 (D68)",
     "Rafaella + advogado", "2026-11-29", "2027-01-15", ["f0-advogado"], 0, "m-casa-obra", "Fase 0 · lote"),
    # --- jurídico
    ("j1-estatuto", "instituto", "J1 Estatuto do Instituto Physis (PDI/ICT, assistência social e saúde, NIT, vedação de distribuição, dissolução)",
     "Advogado [MARCADOR]", "2026-11-30", "2026-12-14", ["f0-advogado"], 0, "m-inst-ict", "Fase 0 · jurídico"),
    # J2 pelo kit de abertura 17 (decisão de 18/11/2026): assembleia em jan/2027, registro e CNPJ em fev/2027; a D60 (31/01) fica em risco
    ("j2-ata-cnpj", "instituto", "J2 Ata de constituição, registro em cartório e CNPJ do Instituto (kit 17: assembleia jan, CNPJ fev/2027)",
     "Rafaella + cartório", "2027-01-11", "2027-02-26", ["j1-estatuto"], 0, "m-inst-ict", "Fase 0 · jurídico"),
    ("f0-cnpj-casa", "casa", "Abrir CNPJ Casa Physis (D60): sócios (D33), CNAEs, regime", "Contador [MARCADOR]", "2026-12-11", "2027-01-15",
     ["f0-resp-contador"], 0, "m-casa-operacao", "Fase 0 · contábil"),
    ("j3-politica-inovacao", "instituto", "J3 Política de inovação (Decreto 9.283/2018)", "Advogado + Rafaella", "2026-12-15", "2027-01-10",
     ["j1-estatuto"], 1, "m-inst-ict", "Fase 0 · jurídico"),
    ("j4-nit", "instituto", "J4 Regimento do NIT", "Advogado + Rafaella", "2026-12-15", "2027-01-10", ["j1-estatuto"], 1, "m-inst-ict",
     "Fase 0 · jurídico"),
    ("j8-conselho", "instituto", "J8 Conselho fiscal e política de conflito de interesse (D63: impedimento de voto da dona)",
     "Advogado", "2026-12-15", "2027-01-08", ["j1-estatuto"], 1, "m-inst-ict", "Fase 0 · jurídico"),
    ("j5-cessao", "transversal", "J5 Cessões do lote: Zona 1 → Physis Eng., Zona 2 → Instituto, Zona 3 + restaurante → Casa (D32/D32b) + laudo",
     "Advogado + avaliador", "2027-03-01", "2027-03-12", ["f0-lote-escritura", "j2-ata-cnpj", "f0-cnpj-casa"], 0, "m-casa-obra",
     "Fase 0 · jurídico"),   # depois do CNPJ do Instituto (J2, fev/2027): a cessão da Zona 2 precisa do CNPJ
    ("j6-rateio", "transversal", "J6 Rateio de custos (PF, Physis, Instituto, Casa) com critério objetivo", "Advogado + contador",
     "2027-03-15", "2027-03-16", ["j5-cessao"], 1, "m-transv-fase0", "Fase 0 · jurídico"),
    ("j7-licenca-pi", "instituto", "J7 Licenciamento/transferência de tecnologia Instituto ↔ Physis/Casa (royalties, Physis 3D)",
     "Advogado", "2027-01-11", "2027-01-29", ["j4-nit", "f0-d37-cenarios"], 1, "m-inst-ict", "Fase 0 · jurídico"),
    # --- contábil
    ("c1-plano-contas", "transversal", "C1 Plano de contas segregado por entidade e projeto", "Contador", "2026-12-11", "2027-01-15",
     ["f0-resp-contador"], 1, "m-transv-fase0", "Fase 0 · contábil"),
    ("c2-memorando", "transversal", "C2 Memorando de enquadramento tributário (imunidade, ITG 2002)", "Contador + tributarista",
     "2026-12-11", "2027-01-15", ["f0-resp-contador"], 1, "m-transv-fase0", "Fase 0 · contábil"),
    ("c3-cnaes", "transversal", "C3 CNAEs por CNPJ (Instituto, Physis, Casa)", "Contador", "2026-12-11", "2026-12-20", ["f0-resp-contador"], 1,
     "m-transv-fase0", "Fase 0 · contábil"),
    ("c4-prestacao", "instituto", "C4 Modelo de prestação de contas (MROSC e recursos do exterior)", "Contador", "2027-01-16", "2027-01-29",
     ["c1-plano-contas"], 2, "m-inst-ict", "Fase 0 · contábil"),
    ("c5-bolsas", "instituto", "C5 Parecer de bolsas (D34 em aberto: prêmio científico × contrato separado)", "Contador + trabalhista",
     "2026-12-11", "2027-01-15", ["f0-resp-contador"], 1, "m-inst-ict", "Fase 0 · contábil"),
    # --- regulatório (início na Fase 0, conclusão depois)
    ("r1-zoneamento", "casa", "R1 Certidão de zoneamento (APA Petrópolis)", "Rafaella", "2026-11-24", "2026-12-22", [], 2, "m-casa-obra",
     "Fase 0 · licenças"),
    ("r2-consulta-previa", "casa", "R2 Consulta prévia na Prefeitura de Petrópolis", "Rafaella", "2026-12-23", "2027-02-28", ["r1-zoneamento"], 2,
     "m-casa-obra", "Fase 0 · licenças"),
    ("r3-planialtimetrico", "casa", "R3 Levantamento planialtimétrico", "Rafaella", "2026-11-24", "2026-12-22", [], 2, "m-casa-obra",
     "Fase 0 · licenças"),
    # --- operacional
    ("o1-acordo", "instituto", "O1 Plano de trabalho do acordo (AWPI França; S2 Services SARL Nairóbi — tratamento de empresa, D66)",
     "Rafaella", "2026-12-11", "2027-01-15", ["f0-resp-contador"], 2, "m-gsa", "Fase 0 · operacional"),
    ("o2-gsa", "transversal", "O2 Minuta GSA com cláusula de cessão de posição ao Instituto (D67)", "Advogado", "2026-12-01", "2027-01-15",
     ["f0-advogado"], 2, "m-gsa", "Fase 0 · operacional"),
    ("o3-inovastem", "inovastem", "O3 Plano de lançamento InovaSTEM (T1/T2, 20–25 mulheres, orçamento e captação)", "Rafaella + Marzia",
     "2026-12-01", "2027-01-31", [], 2, "m-inovastem-piloto", "Fase 0 · operacional"),
    ("hk-escopo", "inovastem", "Hackathon ciber (online): escopo, público, data, formato (CTF/desafios em ambiente próprio), premiação",
     "Rafaella + Marzia", "2026-12-01", "2026-12-20", [], 2, "m-inovastem-hackathon", "Hackathon segurança cibernética"),
    ("hk-regulamento", "inovastem", "Hackathon ciber: regulamento, termo de participação, código de conduta, LGPD e regra de ética "
     "(ataques só no ambiente do evento, divulgação responsável)", "Rafaella + advogado", "2026-12-21", "2027-01-31",
     ["hk-escopo", "f0-advogado"], 2, "m-inovastem-hackathon", "Hackathon segurança cibernética"),
    ("hk-plataforma", "inovastem", "Hackathon ciber: plataforma online e ambiente de desafios isolado (sem alvos reais), inscrições e placar",
     "Eric Oliveira + Erick Lopes", "2027-01-05", "2027-03-31", ["hk-escopo"], 3, "m-inovastem-hackathon", "Hackathon segurança cibernética"),
    ("hk-parceiros", "inovastem", "Hackathon ciber: parceiros, mentores, patrocínio e edital de apoio (cruzar com o bot de editais)",
     "Marzia", "2027-01-05", "2027-04-30", ["hk-escopo"], 3, "m-inovastem-hackathon", "Hackathon segurança cibernética"),
    ("o4-delas", "inovastem", "O4 Política InovaSTEM Delas (pares agora; clínico com o centro TEA, D41)", "Rafaella + advogado",
     "2026-12-01", "2027-01-20", ["f0-advogado"], 2, "m-inovastem-piloto", "Fase 0 · operacional"),
    ("o5-catalogo", "engineering", "O5 Catálogo de produtos e módulos no site (preços fixos na loja, D73)", "Rafaella + Eric + Marzia",
     "2026-11-24", "2026-12-20", [], 2, "m-eng-sistema", "Fase 0 · operacional"),
    ("o6-termos", "engineering", "O6 Termos de uso e privacidade (LGPD) — bloco 3 jurídico", "Rafaella + advogado", "2026-12-01", "2027-01-20",
     ["f0-advogado"], 2, "m-eng-sistema", "Fase 0 · operacional"),
    ("d43-auditoria", "transversal", "D43 Auditoria do site, LinkedIn e Instagram + concorrentes (captação)", "Claude + Marzia", "2026-11-24",
     "2026-12-05", [], 2, "m-eng-sistema", "Marca e captação"),
    ("d43-marcas", "transversal", "D43 Sistema de marcas (6 marcas) para validação: paletas, logos, templates", "Claude + Rafaella",
     "2026-12-06", "2026-12-19", ["d43-auditoria"], 2, "m-eng-sistema", "Marca e captação"),
    ("o7-comunicacao", "transversal", "O7 Plano de comunicação separando Physis (comercial) e Instituto (impacto)", "Marzia + Rafaella",
     "2026-12-20", "2027-01-31", ["d43-marcas"], 3, "m-inst-ict", "Fase 0 · operacional"),
    ("ap-apresentacoes", "transversal", "AP1–AP7 Apresentações de captação: indicadores, P&L por linha, cronograma, riscos, governança",
     "Rafaella + Marzia", "2026-12-20", "2027-01-31", ["d43-marcas", "f0-resp-contador"], 2, "m-casa-obra", "Marca e captação"),
    # --- editais com prazo aberto (doc 30, pesquisa de 18/11/2026)
    ("ed-bndes-garagem", "engineering", "Edital BNDES Garagem – Negócios de Impacto 2026/27 (faixa Tração; Cadimpacto obrigatório) — prazo 30/11",
     "Rafaella + Marzia", "2026-11-19", "2026-11-30", [], 0, "m-eng-sistema", "Editais"),
    ("ed-cnpq-inspiracao", "inovastem", "Edital CNPq/Petrobras 31/2026 InspirAÇÃO: articular IES parceira com a InovaSTEM — prazo 08/12",
     "Rafaella + Marzia", "2026-11-19", "2026-12-08", [], 1, "m-inovastem-piloto", "Editais"),
    ("ed-cnpq-maidai", "engineering", "Edital CNPq/CAPES 30/2026 MAI/DAI: universidade + Physis como empresa — prazo 11/12",
     "Rafaella + Erick Lopes", "2026-11-19", "2026-12-11", [], 2, "m-eng-sistema", "Editais"),
    ("ed-embrapii", "engineering", "EMBRAPII + Sebrae: escolher a Unidade (ex.: INT) e montar o plano de projeto do Physis M&V/SustainKit",
     "Rafaella + Eric Oliveira", "2026-12-01", "2026-12-22", [], 2, "m-eng-sistema", "Editais"),
    # --- construção do M&V e dos bots (D51, D55)
    ("mv-nucleo", "transversal", "Physis M&V: núcleo, Gantt, Kanban, matriz, roadmap, saúde, bots de atraso e documentos (teste)",
     "Claude", "2026-11-18", "2026-11-22", [], 0, "m-transv-fase0", "Physis M&V"),
    ("mv-editais", "engineering", "Editais: caixa de links (WhatsApp), coletor público, estratégia e cronograma reverso (teste)",
     "Claude + Marzia + Erick Lopes", "2026-11-23", "2026-11-26", ["mv-nucleo"], 0, "m-inst-ict", "Physis M&V"),
    ("mv-bots-frente", "transversal", "Bots por frente (D53) + eventos, oportunidades e parceiros", "Claude", "2026-11-23", "2026-11-28",
     ["mv-nucleo"], 1, "m-transv-fase0", "Physis M&V"),
    ("mv-acervo", "inovastem", "Bot do acervo → trilhas (InovaSTEM, Sistema Physis, Instituto) (teste)", "Claude", "2026-11-19", "2026-11-30",
     [], 1, "m-inovastem-piloto", "Physis M&V"),
    ("mv-parceiros", "engineering", "Bots de parceiros/fornecedores e templates; fila de e-mails com aprovação (D49)", "Claude + Ryan",
     "2026-11-26", "2026-11-30", ["mv-nucleo"], 2, "m-eng-sistema", "Physis M&V"),
    ("mv-servidor", "transversal", "Migrar M&V e bots para o servidor físico + IA Physis (D59)", "Eric Oliveira", "2026-12-01", "2026-12-20",
     ["mv-nucleo", "mv-editais"], 1, "m-transv-fase0", "Physis M&V"),
]


def semear(mv: MV) -> dict:
    for m in METAS:
        mv.db.execute("INSERT OR REPLACE INTO mv_meta VALUES (?,?,?,?,?,?,?)", m)
    for k in MARCOS:
        mv.db.execute("INSERT OR IGNORE INTO mv_marco (id,frente,data,titulo,meta,fase) VALUES (?,?,?,?,?,?)", k)
    mv.db.commit()
    n = 0
    for tid, fr, tit, resp, ini, fim, dep, pri, meta, proj in FASE0:
        ant = mv.tarefa(tid)
        mv.salvar_tarefa({"id": tid, "frente": fr, "titulo": tit, "responsavel": resp, "inicio": ini, "fim": fim,
                          "depende_de": dep, "prioridade": pri, "meta": meta, "projeto": proj,
                          "estado": ant["estado"] if ant else ("fazendo" if tid == "mv-nucleo" else "a_fazer"),
                          "bloqueio": ant["bloqueio"] if ant else "", "fonte": FONTE27,
                          "data_estimada": True}, origem="semente")
        n += 1
    return {"metas": len(METAS), "marcos": len(MARCOS), "tarefas": n}
