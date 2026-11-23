"""Gera um memo por bloco da Fase 2 (a partir do documento 18 e do mapa de kits) e um memo por pessoa."""
import json
import re
import sys
from pathlib import Path

import os  # noqa: E402
DOCS = Path(os.environ.get("PHYSIS_DOCS") or (Path.home() / "OneDrive - Physis Engineering" / "Documents")) / "Sistema Physis"
REPO = Path(__file__).resolve().parents[2]          # pasta do sistema, onde quer que esteja
SAIDA = DOCS / "19_Memos_Fase2"
SAIDA.mkdir(exist_ok=True)
doc = (DOCS / "18_Checklist_Implantacao_e_Responsaveis.md").read_text(encoding="utf-8")
kits = json.loads((REPO / "ferramentas" / "kits" / "modulos.json").read_text(encoding="utf-8"))["modulos"]
DATA = "15/11/2026 (atualizado em 15/11/2026, noite: mapa de responsabilidades novo)"
PESSOAS = ["Rafaella", "Eric Oliveira", "Arthur", "Erick Lopes", "Rafael", "Emerson", "Laura", "Marzia", "Ryan", "Leonardo Macedo",
           "Consultores técnicos", "Consultor especialista"]
PAPEIS = {"Consultores técnicos", "Consultor especialista"}   # papéis, não pessoas: procurados sem caixa

INFO = {  # objetivo, prioridade, apoio (documentos e arquivos), depende de, entregável
 1: ("Colocar no ar o servidor da Physis com HTTPS, e-mail, cópias, serviços abertos e IA, para que plataforma, Gestão, loja e app funcionem pela internet com segurança.",
     "URGENTE: destrava e-mails, app instalável, Gestão compartilhada e o teste em campo. Antes de tudo, a PRIORIDADE 0 (Fase 1): chave do Claude, servidor com internet e acesso por VPN.",
     ["10_Perguntas_Eric_Infraestrutura.md (única lista que sai para fora; parte 0 = prioridade 0)", "physis-hub/docs/IA_CLAUDE.md (chave, tetos e custos do Claude)",
      "physis-hub/docs/SUPORTE_REMOTO.md (VPN e \"Permitir suporte\")", "16_Fase2_Exportacao_e_Teste_em_Campo.md",
      "physis-hub/docs/IMPLANTACAO.md", "physis-hub/docs/SERVICOS_ABERTOS.md", "physis-hub/docs/SEGURANCA.md", "physis-hub/docs/INTERCAMBIO.md (troca de dados com plataformas parceiras)",
      "physis-hub/docs/INCORPORAR_REVISOES.md (como aplicar as revisões da equipe)", "servicos/ (docker-compose e serviços)", "implantacao/ (instalador e backup)"],
     "Nada: é o primeiro bloco.", "Servidor no ar, com verificar.sh e healthchecks verdes e uma restauração de backup testada."),
 2: ("Deixar o sistema seguro para a internet e em conformidade com a LGPD.",
     "URGENTE (junto com o bloco 1).",
     ["physis-hub/docs/SEGURANCA.md (checklist ASVS nível 2)", "09_Minutas_Juridicas.md (privacidade)", "physis-hub/docs/SAUDE.md (dados sensíveis)"],
     "Bloco 1: servidor com HTTPS.", "Direção com 2FA, modo estrito ligado, chaves por aparelho e encarregado de dados publicado."),
 3: ("Transformar as minutas em textos válidos (termos, privacidade, licença, contratos, consentimento da Saúde).",
     "ALTA: os textos aparecem para todos os clientes.",
     ["09_Minutas_Juridicas.md", "sistema/physis-juridico.js (gerado por ferramentas/gerar_juridico.py)", "physis-hub/docs/PARCEIROS.md (regras de documentos)"],
     "Assessoria jurídica.", "Minutas aprovadas, marcadores preenchidos, gerar_juridico.py rodado e telas atualizadas."),
 4: ("Revisar cada módulo para passar de \"estimativa\" a \"projeto preliminar confiável\": dados \"verificar\", normas e casos reais.",
     "ALTA: começar pelos módulos vendidos (Planejamento, Solar, Água, Monitoramento, SustainKit, SCADA, Gestão, Certificação).",
     ["17_Metodologia_e_Normas.md (o que adequar em cada cálculo)", "Kit de revisão de cada módulo (pasta e ZIP com LEIA-ME e FICHA)",
      "physis-hub/docs/KITS_REVISAO.md (como revisar e devolver)", "physis-hub/docs/VALIDACAO_TELAS.md (telas por idioma e tema)",
      "sistema/physis-premissas.json (premissas \"conferir\")"],
     "Kits gerados depois do commit final da integração.", "Kit devolvido com a FICHA, validado e aplicado pelo Eric, com os testes passando."),
 5: ("Preparar e testar cada aparelho de campo e o firmware.",
     "ALTA para LoRa e Caixinha (teste em campo); MÉDIA para os demais.",
     ["firmware/ (código de cada aparelho)", "physis-hub/docs/MQTT.md", "physis-hub/docs/EXTENSAO_V6.md e PROTOCOLO.md", "firmware/saude/BLE_PERFIL.md",
      "physis-hub/docs/ROBOS.md §6 (pluviômetro)", "Kits hw-* de revisão"],
     "Bloco 1 (chaves dos aparelhos) para o teste exposto; na rede local pode começar já.", "Aparelho calibrado, com ID e chave, testado em bancada e pronto para o campo."),
 6: ("Publicar o app Physis para Android e iPhone.",
     "MÉDIA: o app pelo navegador já funciona com HTTPS.",
     ["physis-hub/docs/APP_NATIVO.md", "app-nativo/ (projeto, scripts e página de download)", "physis-hub/docs/APPS.md (PWA)"],
     "Bloco 1 (HTTPS e política de privacidade publicada) e bloco 3 (consentimento).", "App nas lojas e APK direto publicado, com QR codes testados em celulares reais."),
 7: ("Deixar site, loja, marketing, Gestão e Editais operando com os dados reais da Physis.",
     "ALTA: loja e consultoria são a porta de entrada dos clientes.",
     ["physis-hub/docs/GESTAO_NOVAS_ABAS.md", "physis-hub/docs/PARCEIROS.md", "Gestão interna → projetos \"Fase 2\"", "Consultoria (/consultoria) e loja (/loja/)",
      "21_Pagamento_Provedor_e_Integracao.md (pagamento, Fase 2)", "physis-hub/docs/DOCUMENTOS_AUTOMATICOS.md (modelos reais e aprovação)",
      "22_Links_e_Paineis.md (páginas online da equipe)"],
     "Bloco 3 para os textos legais da loja.", "Loja com os 8 módulos publicados, marcadores substituídos, pagamento decidido (integração na Fase 2), modelos reais enviados e rotinas de marketing e editais rodando."),
 8: ("Instalar no primeiro cliente e passar na semana de teste em campo.",
     "DEPOIS dos blocos 1, 2 e 5.",
     ["16_Fase2_Exportacao_e_Teste_em_Campo.md (roteiro)", "physis-hub/docs/IMPLANTACAO.md (checklist imprimível)", "implantacao/instalar.sh, verificar.sh"],
     "Blocos 1, 2 e 5.", "Critérios de \"passou\" atingidos e relatório da semana compartilhado para comentários."),
 9: ("Entregar ao cliente com treinamento e suporte definidos.",
     "Ao fim do bloco 8.",
     ["Curso de introdução (aba Cursos)", "LEIA-ME do pacote", "Gestão → Suporte Physis e Chamados"],
     "Bloco 8.", "Cliente treinado, contatos entregues e rotina de atualização e backup combinada."),
 10: ("Manter o sistema confiável depois da implantação.",
      "CONTÍNUO.",
      ["physis-hub/docs/IMPLANTACAO.md (verificar.sh)", "physis-hub/docs/APRENDIZADO.md", "17_Metodologia_e_Normas.md"],
      "Implantação concluída.", "Rotinas semanais e semestrais acontecendo e registradas na Gestão."),
}

secoes = re.split(r"\n(?=## \d+\. )", doc)
blocos = {}
for s in secoes:
    m = re.match(r"## (\d+)\. ([^\n]+)", s)
    if m:
        corpo_s = re.split(r"\n(?=## (?!\d+\. ))", s.split("\n", 1)[1])[0]   # para no próximo título sem número
        blocos[int(m.group(1))] = (re.sub(r"\s*\([^)]*\)\s*$", "", m.group(2)).strip(), corpo_s.strip())

indice = []
for n, (titulo, corpo) in sorted(blocos.items()):
    obj, prio, apoio, dep, entrega = INFO[n]
    corpo = re.sub(r"\n---\s*$", "", corpo).strip()
    resp = sorted({p for p in PESSOAS if re.search(r"\b" + re.escape(p) + r"(?!\w)", corpo, re.I if p in PAPEIS else 0)}
                  | ({"Eric Oliveira"} if "Eric" in corpo else set()),
                  key=PESSOAS.index)
    kits_txt = ""
    if n in (4, 5):
        ks = [k for k in kits if (k.get("tipo") == "modulo") == (n == 4) and k.get("tipo") != "servidor"]
        kits_txt = "\n## Kits de revisão deste bloco\n\n| Kit | Responsáveis | O que revisar |\n|---|---|---|\n" + "\n".join(
            f"| `kit-{k['id']}` · {k['nome']} | {', '.join(k['responsaveis'])} | {k.get('o_que_revisar', '')} |" for k in ks) + "\n"
    memo = f"""# Memo Fase 2 · Bloco {n}: {titulo}

**Para:** {', '.join(resp) or 'equipe'} · **De:** direção (Sistema Physis) · **Data:** {DATA}
**Prioridade:** {prio}

## Objetivo
{obj}

## Depende de
{dep}

## Entregável (quando o bloco está pronto)
{entrega}

## Tarefas, responsáveis e critério de "feito"
As mesmas tarefas estão na Gestão interna, no projeto **"Fase 2 · {n}. {titulo}"**, uma para cada pessoa. Marque lá quando concluir.

{corpo}
{kits_txt}
## Documentos e arquivos de apoio
{chr(10).join('- ' + a for a in apoio)}

## Como registrar e pedir ajuda
- **Andamento:** marque as tarefas na Gestão interna (Plano de ação). Bloqueios vão como comentário na tarefa, com a pessoa de quem você depende.
- **Revisões de módulo:** devolva o ZIP do kit com a FICHA_REVISAO preenchida. O Eric valida e aplica (`INCORPORAR_REVISOES.md`).
- **Dúvidas técnicas sobre o sistema:** Gestão → Suporte Physis, ou a direção.
- **Nada de dados de clientes por WhatsApp ou e-mail pessoal:** use a Gestão (LGPD).
"""
    import unicodedata
    sem = "".join(c for c in unicodedata.normalize("NFD", titulo) if unicodedata.category(c) != "Mn")
    nome = f"{n:02d}_Bloco_{re.sub(r'[^A-Za-z0-9]+', '_', sem).strip('_')}.md"
    (SAIDA / nome).write_text(memo, encoding="utf-8", newline="\n")
    indice.append((n, titulo, nome, prio, ", ".join(resp)))

# memo por pessoa
tarefas_json = json.loads((DOCS / "18_Checklist_para_importar_na_Gestao.json").read_text(encoding="utf-8"))
nomes = {p["pessoa_id"]: p["nome"] for p in tarefas_json["tabelas"]["pessoa"]}
porp = {}
for t in tarefas_json["tabelas"]["tarefa"]:
    porp.setdefault(nomes[t["pessoa_id"]], {}).setdefault(t["extras"]["projeto_nome"], []).append(t["titulo"])
sys.path.insert(0, str(Path(__file__).parent))
from mapa_resp import AREAS, NOME as NOME_ID  # noqa: E402
ID_DE = {v: k for k, v in NOME_ID.items()}


def eh_co(titulo):
    """Cópia de co-responsável: termina em "(com <nome do principal>)"."""
    m = re.search(r" \(com ([^()]*)\)$", titulo)
    return bool(m) and m.group(1) in ID_DE


linhas = [f"# Memo Fase 2 · Quem faz o quê\n\n**Data:** {DATA} · Fonte: documento 18, Gestão interna (projetos \"Fase 2\") "
          "e o mapa de responsabilidades da direção (15/11/2026, noite).\n",
          "Cada pessoa tem **a sua cópia** de cada tarefa na Gestão, para marcar quando concluir. A cópia de quem lidera diz "
          "\"(responsável principal; com …)\"; a cópia de quem ajuda diz \"(com <nome de quem lidera>)\".\n"]
for p in PESSOAS:
    if p in PAPEIS and p not in porp:
        continue
    todas = [t for v in porp.get(p, {}).values() for t in v]
    total, n_co = len(todas), sum(1 for t in todas if eh_co(t))
    meus = [k for k in kits if p in k["responsaveis"]]
    linhas.append(f"\n## {p} · {total} tarefas ({total - n_co} como principal, {n_co} como co-responsável)\n")
    pid = ID_DE.get(p)
    if pid:
        princ = [a[0] for a in AREAS.values() if a[1] and a[1][0] == pid]
        co = [a[0] for a in AREAS.values() if pid in a[1][1:]]
        linhas.append("**Áreas (principal):** " + (", ".join(princ) or "nenhuma") + "  \n**Co-responsável em:** " + (", ".join(co) or "nenhuma") + "\n")
    if meus:
        linhas.append("**Kits de revisão:** " + ", ".join(f"`kit-{k['id']}` ({k['nome']})" for k in meus) + "\n")
    for proj in sorted(porp.get(p, {}), key=lambda x: int(re.search(r"· (\d+)\.", x).group(1))):
        linhas.append(f"\n### {proj}\n")
        linhas += [f"- [ ] {t}" for t in sorted(porp[p][proj], key=eh_co)]   # as de principal primeiro
(SAIDA / "11_Quem_faz_o_que.md").write_text("\n".join(linhas) + "\n", encoding="utf-8", newline="\n")

leia = [f"# Memos da Fase 2: índice\n\n**Data:** {DATA}\n",
        "Um memo por bloco, com objetivo, prioridade, dependências, entregável, tarefas com responsáveis e critério de \"feito\", kits e documentos de apoio. O memo **11** reúne as tarefas de cada pessoa.\n",
        "## Ordem para revisar o mais rápido possível\n",
        "1. **Agora, em paralelo:**\n   - prioridade 0 do Eric, no bloco 1 (chave do Claude, servidor com internet e VPN; Fase 1);\n   - blocos 1 e 2 (servidor e segurança: Eric, com Rafaella e Arthur);\n   - bloco 3 (jurídico: Rafaella);\n   - bloco 4 (cada responsável abre o seu kit assim que for enviado);\n   - bloco 7 (loja e consultoria).",
        "2. **Assim que o servidor estiver no ar:**\n   - bloco 5 (aparelhos com chave);\n   - bloco 6 (app);\n   - Gestão compartilhada.",
        "3. **Com os blocos 1, 2 e 5 prontos:** bloco 8 (campo), depois o 9 (entrega) e o 10 (contínuo).",
        "4. **Ritmo sugerido:**\n   - reunião curta semanal (Gestão → Reuniões), olhando só o que está atrasado ou bloqueado;\n   - cada kit devolvido em até 10 dias úteis.\n",
        "## Memos\n", "| Bloco | Arquivo | Prioridade | Responsáveis |", "|---|---|---|---|"]
leia += [f"| {n}. {t} | [{a}]({a}) | {p.split(':')[0]} | {r} |" for n, t, a, p, r in indice]
leia.append("| Quem faz o quê | [11_Quem_faz_o_que.md](11_Quem_faz_o_que.md) | — | todos |")
(SAIDA / "00_LEIA-ME.md").write_text("\n".join(leia) + "\n", encoding="utf-8", newline="\n")
print("memos:", len(indice) + 2, "em", SAIDA)
