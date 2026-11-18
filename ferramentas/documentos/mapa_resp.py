"""Mapa de responsabilidades da direção (15/11/2026, noite). Substitui as atribuições anteriores.
Cada área: lista de ids, o PRINCIPAL primeiro, depois os co-responsáveis.
Regra do principal: Rafaella quando ela é responsável direta (não "co-responsável"); senão a primeira pessoa
na ordem do texto da direção que lista a área; quando a direção escreveu "especialmente X", o primeiro de X.
Exceção: Revisão da consultoria fica com Leonardo Macedo (é a atribuição dele desde o início e a única com "e pacotes")."""
from collections import OrderedDict

ORDEM = ["rafaella", "erickoliveira", "ericklopes", "arthur", "rafael", "emerson", "ryan", "laura", "marzia", "leonardomacedo"]
NOME = {"rafaella": "Rafaella", "erickoliveira": "Eric Oliveira", "ericklopes": "Erick Lopes", "arthur": "Arthur",
        "rafael": "Rafael", "emerson": "Emerson", "ryan": "Ryan", "laura": "Laura", "marzia": "Marzia",
        "leonardomacedo": "Leonardo Macedo", "consultores": "Consultores técnicos",
        "consultorespecialista": "Consultor especialista"}
TODOS = list(ORDEM)

# chave: (nome mostrado, [principal, co...], origem)
AREAS = OrderedDict([
    ("planejador", ("Planejador (inclui o Mapeamento)", ["rafaella"] + [p for p in ORDEM if p != "rafaella"], "mapa")),
    ("site", ("Site", ["rafaella", "erickoliveira", "marzia"], "mapa")),
    ("loja", ("Loja", ["rafaella", "erickoliveira", "marzia"], "mapa")),
    ("gestao", ("Gestão interna", ["rafaella", "erickoliveira", "rafael", "laura", "marzia"], "mapa")),
    ("marketing", ("Marketing", ["marzia", "rafaella"], "mapa")),
    ("acessibilidade", ("Acessibilidade", ["rafaella", "arthur", "emerson", "leonardomacedo"], "mapa")),
    ("ingles", ("Inglês (inclui revisões do site em inglês)", ["rafaella", "laura", "marzia"], "mapa")),
    ("app", ("App", ["rafaella", "erickoliveira", "arthur", "emerson"], "mapa")),
    ("editais", ("Editais (gestão)", ["marzia", "ericklopes"], "mapa")),
    ("industria", ("Indústria (clientes industriais)", ["marzia", "laura", "ryan"], "mapa")),
    ("indicadores", ("Indicadores da plataforma", ["erickoliveira", "rafaella"], "mapa")),
    ("certificacoes", ("Certificações", ["ericklopes", "ryan", "laura", "rafaella"], "mapa")),
    ("scada", ("SCADA", ["ericklopes", "laura", "rafaella"], "mapa")),
    ("sbn", ("SbN", ["ericklopes", "rafaella"], "mapa")),
    ("secador", ("Secador solar", ["arthur", "laura", "rafaella"], "mapa")),
    ("circular", ("Economia circular", ["rafael", "rafaella"], "mapa")),
    ("resiliencia", ("Resiliência", ["arthur", "rafaella"], "mapa")),
    ("cursos", ("Cursos", ["laura", "marzia", "ryan", "leonardomacedo", "rafaella"], "mapa")),
    ("servidor", ("Servidor (inclui IA local)", ["erickoliveira"], "mapa")),
    ("instalacao", ("Instalação para clientes", ["erickoliveira", "ericklopes", "arthur", "rafael"], "mapa")),
    ("servidor_verde", ("Servidor verde", ["erickoliveira"], "mapa")),
    ("kits", ("Validar e aplicar os kits devolvidos", ["erickoliveira", "arthur"], "mapa")),
    ("sustainkit", ("SustainKit", ["ericklopes"], "mapa")),
    ("solar", ("Energia solar", ["ericklopes"], "mapa")),
    ("agua", ("Qualidade da água", ["ericklopes", "rafael"], "mapa")),
    ("quadros", ("Quadros elétricos e IoT", ["ericklopes"], "mapa")),
    ("hardware", ("Hardware", ["ericklopes", "arthur", "rafael", "emerson", "laura"], "mapa")),
    ("caixinha_fw", ("Firmware das Caixinhas", ["ericklopes", "arthur", "rafael", "emerson", "laura"], "mapa")),
    ("consultoria", ("Revisão da consultoria", ["leonardomacedo", "ericklopes", "arthur", "rafael"], "mapa")),
    ("pacotes", ("Revisão dos pacotes", ["leonardomacedo"], "mapa")),
    ("pdi", ("Gestão de projetos PDI (geral)", ["arthur"], "mapa")),
    ("monitoramento", ("Monitoramento verde", ["arthur"], "mapa")),
    ("lora", ("LoRa (transmissor e receptor)", ["arthur"], "mapa")),
    ("pluviometro", ("Pluviômetro", ["arthur"], "mapa")),
    ("saude", ("Saúde", ["rafael", "emerson"], "mapa")),
    ("coleira", ("Coleira", ["rafael"], "mapa")),
    ("remedios", ("Caixinha de remédios", ["rafael", "emerson"], "mapa")),
    ("pulseira", ("Pulseira", ["emerson"], "mapa")),
    ("turbinas", ("Turbinas", ["emerson", "ryan"], "mapa")),
    ("avac", ("AVAC", ["ryan"], "mapa")),
    ("fornecedores", ("Lista de fornecedores", ["ryan"], "mapa")),
    ("carbono", ("Carbono e ESG", ["marzia", "laura"], "mapa")),
    # fora do texto da direção: deduzido ou mantido como antes
    ("equipamentos", ("Equipamentos e fornecedores (D29)", ["ryan"], "mapa")),
    ("materiais", ("Materiais e bioconstrução (D29)", ["ericklopes"], "mapa")),
    ("seguranca", ("Segurança e LGPD (mantido como antes, D28)", ["rafaella", "erickoliveira", "arthur"], "mantido")),
    ("juridico", ("Jurídico (mantido como antes, D28)", ["rafaella"], "mantido")),
    ("premissas", ("Premissas \"conferir\"", ["consultores"], "mantido")),
    ("validacao_simulacoes", ("Validação das simulações (assinatura)", ["consultorespecialista"], "mapa")),
])

# kits de revisão (ferramentas/kits/modulos.json): id do kit -> áreas que somam os responsáveis (ordem: principal primeiro)
KITS = {
    "planejador": ["planejador"], "sustainkit": ["sustainkit"], "solar": ["solar"], "avac": ["avac"], "turbinas": ["turbinas"],
    "agua": ["agua"], "sbn": ["sbn"], "circular": ["circular"], "carbono": ["carbono"], "resiliencia": ["resiliencia"],
    "certificacoes": ["certificacoes"], "equipamentos": ["equipamentos", "materiais"], "monitoramento": ["monitoramento"],
    "saude": ["saude"], "scada": ["scada"], "cursos": ["cursos"], "secador": ["secador"], "servidor-verde": ["servidor_verde"],
    "acessibilidade": ["acessibilidade", "ingles"], "hw-lora": ["lora"], "hw-caixinha": ["caixinha_fw"],
    "hw-coleira": ["coleira"], "hw-pluviometro": ["pluviometro"], "hw-remedios": ["remedios"], "hw-pulseira": ["pulseira"],
    "servidor": ["servidor"], "mapeamento": ["planejador"],
}


def donos(*areas):
    out = []
    for a in areas:
        for p in AREAS[a][1]:
            if p not in out:
                out.append(p)
    return out
