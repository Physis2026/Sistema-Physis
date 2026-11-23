"""Ecossistema de parcerias e mercado (bot "mercado", 22/11/2026): quem pode fornecer, testar, comprar, estagiar, investir,
ser laboratório, hub de inovação, supermercado parceiro, collab ou ponto de resíduos, em cada cidade onde a Physis atua
(depois Brasil e exterior), por área do ecossistema. Amplia o que já existe sem duplicar:
- fornecedores de energia solar com curadoria: physis_hub/fornecedores.py (Hub, Gestão → Fornecedores) continua o cadastro oficial;
- profissionais parceiros (instaladores, projetistas): physis_hub/parceiros.py;
- destinos de resíduos: physis_hub/residuos_gis.py (o mesmo cliente da Overpass é reaproveitado aqui).
Aqui fica o MAPEAMENTO (candidatos a conferir + cadastrados pela equipe), o mapa GIS em GeoJSON, as lacunas por cidade e
o catálogo de bases de dados abertas. Regra 1: nada é inventado; tudo que vem de fora nasce "a conferir" com a fonte.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import time
import urllib.request
from pathlib import Path

# Cidades onde a Physis atua hoje (clientes/clientes.json). Coordenadas = sede municipal, para o raio de busca [CONFERIR].
CIDADES_PADRAO = [
    {"id": "petropolis-rj", "nome": "Petrópolis", "uf": "RJ", "lat": -22.505, "lon": -43.179, "raio_km": 25,
     "origem": "Casa Physis (Lote 168) e sede · clientes.json"},
    {"id": "itirapua-sp", "nome": "Itirapuã", "uf": "SP", "lat": -20.641, "lon": -47.219, "raio_km": 40,
     "origem": "Fazenda Santa Clara · clientes.json"},
]
FASES = ["cidades atuais", "Brasil", "internacional"]

TIPOS = {   # tipo: (nome, consultas Overpass (tag=valor) ou [] quando só cadastro manual/fonte própria)
    "fabricante": ("Fabricante", []),
    "fornecedor": ("Fornecedor / distribuidor", [("shop", "electronics"), ("shop", "hardware"), ("shop", "electrical"), ("shop", "trade")]),
    "teste": ("Parceiro de teste (usa o produto em troca de parceria)", []),
    "compra_venda": ("Compra e venda", []),
    "estagio": ("Universidade / escola técnica (estágio)", [("amenity", "university"), ("amenity", "college")]),
    "laboratorio": ("Laboratório / bancada de testes", [("amenity", "research_institute"), ("office", "research")]),
    "hub_inovacao": ("Hub de inovação / coworking / incubadora", [("amenity", "coworking_space"), ("office", "coworking")]),
    "investidor": ("Investidor / fundo / patrocinador", []),
    "supermercado": ("Supermercado / varejo parceiro", [("shop", "supermarket")]),
    "collab": ("Collab de marketing (áreas parecidas)", []),
    "residuos": ("Troca de resíduos / ponto de coleta", [("amenity", "recycling")]),
    "instalador": ("Instalador / serviço técnico", [("craft", "electrician"), ("craft", "hvac"), ("craft", "plumber")]),
}

AREAS = {   # área do ecossistema: o que procurar (tipos) e o módulo/aba que usa
    "solar": (["fabricante", "fornecedor", "instalador", "laboratorio"], "Energia solar: fabricantes de módulos/inversores (INMETRO), distribuidores, instaladores; cadastro oficial em fornecedores.py"),
    "avac": (["fabricante", "fornecedor", "instalador", "supermercado", "laboratorio"], "AVAC: fabricantes (base de equipamentos INMETRO/CEC), fornecedores no mapa, varejo parceiro, laboratórios"),
    "iot_hardware": (["fabricante", "fornecedor", "teste", "laboratorio", "hub_inovacao"], "IoT/hardware: peças, sensores, placas, bancadas de teste (receptor/transmissor V6, Caixinha)"),
    "agua": (["fornecedor", "laboratorio", "teste"], "Qualidade da água: reagentes, eletrodos, laboratórios de análise"),
    "turbinas": (["fabricante", "fornecedor", "laboratorio"], "Turbinas eólicas e hidráulicas"),
    "sbn_bioconstrucao": (["fornecedor", "estagio", "laboratorio"], "SbN e bioconstrução: materiais, viveiros, ensaios"),
    "circular": (["residuos", "supermercado", "compra_venda"], "Economia circular: troca de resíduos, pontos de coleta e lixeiras Physis"),
    "cursos_inovastem": (["estagio", "hub_inovacao", "investidor", "collab"], "Cursos/InovaSTEM: universidades, hubs, patrocínio, collabs"),
    "investimento": (["investidor", "hub_inovacao"], "Captação: fundos, anjos, aceleradoras, patrocínio"),
}

# Bases de dados abertas para pesquisar e incluir (verificar o endereço no nó com internet: o bot testa e marca)
DADOS_ABERTOS = [
    ("osm", "OpenStreetMap (Overpass API)", "https://overpass-api.de/api/interpreter", "pontos: lojas, universidades, laboratórios, coleta", "mercado, residuos_gis"),
    ("ibge", "IBGE · API de localidades e malhas", "https://servicodados.ibge.gov.br/api/docs", "municípios, códigos, limites", "mercado, mapeamento"),
    ("cnpj", "Receita Federal · CNPJ (dados abertos)", "https://dados.gov.br/", "empresas por CNAE e município (fabricantes, distribuidores)", "mercado, fornecedores"),
    ("aneel", "ANEEL · dados abertos (geração distribuída)", "https://dadosabertos.aneel.gov.br/", "usinas solares por município, potência, instaladores", "mercado (solar)"),
    ("inmetro", "INMETRO · tabelas do PBE (equipamentos)", "https://www.gov.br/inmetro/", "módulos, inversores, ar-condicionado registrados", "equipamentos, solar, avac"),
    ("cec", "California Energy Commission · listas de equipamentos", "https://www.energy.ca.gov/", "inversores e módulos (referência internacional)", "equipamentos"),
    ("emec", "e-MEC · instituições e cursos", "https://emec.mec.gov.br/", "universidades e cursos por cidade (estágio)", "mercado (estagio)"),
    ("dgp", "CNPq · Diretório dos Grupos de Pesquisa", "https://dgp.cnpq.br/", "grupos e laboratórios por área", "mercado (laboratorio)"),
    ("lattes", "Plataforma Lattes", "https://lattes.cnpq.br/", "pesquisadores por tema", "mercado, editais"),
    ("sinir", "SINIR · resíduos sólidos", "https://sinir.gov.br/", "destinação de resíduos por município", "residuos_gis, circular"),
    ("cvm", "CVM · dados abertos (fundos)", "https://dados.cvm.gov.br/", "fundos e gestores (investidores)", "mercado (investidor)"),
    ("dadosgov", "Portal Brasileiro de Dados Abertos", "https://dados.gov.br/", "catálogo geral", "todos"),
    ("nasa_power", "NASA POWER", "https://power.larc.nasa.gov/", "irradiação, vento, temperatura", "solar, turbinas, avac"),
    ("inmet", "INMET · normais e estações", "https://portal.inmet.gov.br/", "clima", "aprendizado, avac"),
    ("cemaden", "CEMADEN · pluviômetros", "https://www.gov.br/cemaden/", "chuva medida", "aprendizado"),
    ("ana", "ANA · HidroWeb / SNIRH", "https://www.snirh.gov.br/hidroweb/", "rios e chuva", "agua, drenagem"),
    ("mapbiomas", "MapBiomas", "https://plataforma.brasil.mapbiomas.org/", "uso do solo", "mapeamento, sbn"),
    ("finep", "FINEP / BNDES / CNPq / FAPs (editais)", "https://www.finep.gov.br/", "chamadas públicas", "editais"),
]

ESQUEMA = """
CREATE TABLE IF NOT EXISTS mv_parceria (
  id TEXT PRIMARY KEY, nome TEXT NOT NULL, tipo TEXT NOT NULL, areas TEXT NOT NULL DEFAULT '[]', cidade TEXT NOT NULL DEFAULT '',
  uf TEXT NOT NULL DEFAULT '', pais TEXT NOT NULL DEFAULT 'BR', lat REAL, lon REAL, contato TEXT NOT NULL DEFAULT '',
  site TEXT NOT NULL DEFAULT '', modalidade TEXT NOT NULL DEFAULT '', fonte TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'a_conferir',
  notas TEXT NOT NULL DEFAULT '', criado REAL NOT NULL, visto REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mv_dado_aberto (id TEXT PRIMARY KEY, nome TEXT, url TEXT, conteudo TEXT, usa TEXT,
  status TEXT NOT NULL DEFAULT 'nao_testado', testado REAL);
"""
ESTADOS = ("a_conferir", "conferido", "contatado", "parceiro", "descartado")


def E_norm(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn").lower().strip()


def cidades(saida: Path | None = None) -> list[dict]:
    """cidades.json em PHYSIS_MV_SAIDA/ecossistema substitui o padrão (para acrescentar cidades, Brasil e exterior)."""
    from . import mv_bots
    f = Path(saida or (mv_bots.SAIDA / "ecossistema")) / "cidades.json"
    if f.is_file():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return CIDADES_PADRAO


def _id(fonte: str, ref: str) -> str:
    return f"{fonte}:{ref}"[:120]


def gravar(mv, p: dict, agora: float | None = None) -> bool:
    """Grava/atualiza um ponto. Não muda o estado de quem a equipe já conferiu. True se é novo."""
    agora = agora or time.time()
    if p.get("tipo") not in TIPOS:
        raise ValueError(f"tipo inválido: {p.get('tipo')}")
    ant = mv.db.execute("SELECT estado FROM mv_parceria WHERE id=?", (p["id"],)).fetchone()
    campos = (p["nome"][:200], p["tipo"], json.dumps(p.get("areas") or []), p.get("cidade", ""), p.get("uf", ""), p.get("pais", "BR"),
              p.get("lat"), p.get("lon"), p.get("contato", "")[:200], p.get("site", "")[:300], p.get("modalidade", "")[:120],
              p.get("fonte", "manual")[:120])
    if ant:
        mv.db.execute("UPDATE mv_parceria SET nome=?,tipo=?,areas=?,cidade=?,uf=?,pais=?,lat=?,lon=?,contato=?,site=?,modalidade=?,fonte=?,"
                      "visto=? WHERE id=?", (*campos, agora, p["id"]))
        return False
    mv.db.execute("INSERT INTO mv_parceria (id,nome,tipo,areas,cidade,uf,pais,lat,lon,contato,site,modalidade,fonte,estado,criado,visto) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (p["id"], *campos, p.get("estado", "a_conferir"), agora, agora))
    return True


def importar_csv(mv, texto: str, fonte: str = "planilha") -> dict:
    """Planilha da equipe (;): nome;tipo;areas(,);cidade;uf;lat;lon;site;contato;modalidade;estado."""
    n = 0
    for r in csv.DictReader(io.StringIO(texto), delimiter=";"):
        if not (r.get("nome") or "").strip():
            continue
        lat = float(r["lat"].replace(",", ".")) if (r.get("lat") or "").strip() else None
        lon = float(r["lon"].replace(",", ".")) if (r.get("lon") or "").strip() else None
        n += gravar(mv, {"id": _id(fonte, re.sub(r"\W+", "-", (r["nome"] + "-" + (r.get("cidade") or "")).lower())), "nome": r["nome"].strip(),
                         "tipo": r["tipo"].strip(), "areas": [a.strip() for a in (r.get("areas") or "").split(",") if a.strip()],
                         "cidade": r.get("cidade", ""), "uf": r.get("uf", ""), "lat": lat, "lon": lon, "site": r.get("site", ""),
                         "contato": r.get("contato", ""), "modalidade": r.get("modalidade", ""), "fonte": fonte,
                         "estado": (r.get("estado") or "conferido").strip() if (r.get("estado") or "").strip() in ESTADOS else "conferido"})
    mv.db.commit()
    return {"novos": n}


def consulta(cid: dict, tags: list[tuple[str, str]]) -> str:
    a = f"(around:{int(cid['raio_km'] * 1000)},{cid['lat']},{cid['lon']})"
    corpo = "".join(f'nwr["{k}"="{v}"]{a};' for k, v in tags)
    return f"[out:json][timeout:60];({corpo});out center tags 400;"


RENOVAR_DIAS = 180      # versão enxuta: o que foi consultado vale 6 meses


def descobrir(mv, cid: dict, buscar=None, tipos: list[str] | None = None, forcar: bool = False, agora: float | None = None) -> dict:
    """Candidatos do OpenStreetMap para os tipos com consulta, nesta cidade. Todos nascem 'a_conferir'. Sob demanda:
    cidade × tipo consultados há menos de 6 meses são pulados (a menos de forcar)."""
    from .residuos_gis import buscar_overpass
    buscar = buscar or buscar_overpass
    agora = agora or time.time()
    mv.db.execute("CREATE TABLE IF NOT EXISTS mv_mercado_consulta (cidade TEXT, tipo TEXT, quando REAL, PRIMARY KEY (cidade, tipo))")
    novos, por_tipo = 0, {}
    for tipo, (_, tags) in TIPOS.items():
        if not tags or (tipos and tipo not in tipos):
            continue
        ult = mv.db.execute("SELECT quando FROM mv_mercado_consulta WHERE cidade=? AND tipo=?", (cid["id"], tipo)).fetchone()
        if ult and not forcar and agora - ult[0] < RENOVAR_DIAS * 86400:
            por_tipo[tipo] = "guardado"
            continue
        j = buscar(consulta(cid, tags))
        n = 0
        for e in j.get("elements", []):
            t = e.get("tags") or {}
            nome = t.get("name")
            if not nome or not any(t.get(k) == v for k, v in tags):     # só o tipo cujas etiquetas o ponto tem
                continue
            lat = e.get("lat") or (e.get("center") or {}).get("lat")
            lon = e.get("lon") or (e.get("center") or {}).get("lon")
            areas = [a for a, (tipos, _) in AREAS.items() if tipo in tipos]
            n += gravar(mv, {"id": _id("osm", f"{e.get('type')}/{e.get('id')}"), "nome": nome, "tipo": tipo, "areas": areas,
                             "cidade": cid["nome"], "uf": cid["uf"], "lat": lat, "lon": lon, "site": t.get("website", ""),
                             "contato": t.get("phone", "") if t.get("phone") else "", "fonte": "OpenStreetMap (ODbL)"})
        por_tipo[tipo] = n
        novos += n
        mv.db.execute("INSERT OR REPLACE INTO mv_mercado_consulta VALUES (?,?,?)", (cid["id"], tipo, agora))
    mv.db.commit()
    return {"novos": novos, "por_tipo": por_tipo}


def geojson(mv, so_estado: tuple[str, ...] | None = None) -> dict:
    feats = []
    for r in mv.db.execute("SELECT id,nome,tipo,areas,cidade,uf,lat,lon,site,estado,fonte FROM mv_parceria WHERE lat IS NOT NULL AND lon IS NOT NULL"):
        if so_estado and r[9] not in so_estado:
            continue
        feats.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [r[7], r[6]]},
                      "properties": {"id": r[0], "nome": r[1], "tipo": r[2], "tipo_nome": TIPOS[r[2]][0], "areas": json.loads(r[3]),
                                     "cidade": r[4], "uf": r[5], "site": r[8], "estado": r[9], "fonte": r[10]}})
    return {"type": "FeatureCollection", "features": feats}


def lacunas(mv, cids: list[dict]) -> list[dict]:
    """Para cada cidade × área × tipo necessário: quantos pontos existem (qualquer estado) e quantos já conferidos."""
    out = []
    for c in cids:
        for area, (tipos, _) in AREAS.items():
            for t in tipos:
                tot, conf = mv.db.execute("SELECT COUNT(*), SUM(estado IN ('conferido','contatado','parceiro')) FROM mv_parceria "
                                          "WHERE cidade=? AND tipo=? AND areas LIKE ?", (c["nome"], t, f'%"{area}"%')).fetchone()
                out.append({"cidade": c["nome"], "area": area, "tipo": t, "total": tot, "conferidos": int(conf or 0)})
    return out


def testar_dados_abertos(mv, abrir=None) -> dict:
    abrir = abrir or (lambda u: urllib.request.urlopen(urllib.request.Request(u, method="HEAD", headers={"User-Agent": "PhysisMA/1.0"}), timeout=15).status)
    ok = falha = 0
    for i, nome, url, conteudo, usa in DADOS_ABERTOS:
        try:
            st = abrir(url)
            status = "ok" if int(st) < 400 else f"http {st}"
        except Exception as e:  # noqa: BLE001
            status = "sem resposta: " + type(e).__name__
        ok += status == "ok"
        falha += status != "ok"
        mv.db.execute("INSERT OR REPLACE INTO mv_dado_aberto VALUES (?,?,?,?,?,?,?)", (i, nome, url, conteudo, usa, status, time.time()))
    mv.db.commit()
    return {"ok": ok, "sem_resposta": falha}


def bot_mercado(mv, saida: Path | None = None, buscar=None, abrir=None, online: bool | None = None, cidade: str | None = None,
                area: str | None = None, forcar: bool = False) -> dict:
    """SOB DEMANDA (versão enxuta): /mercado <cidade> [área] no M&A, ou mv_cli bots mercado. Sem rotina."""
    from . import mv_bots, mv_comandos
    inicio = mv.nova_rodada()
    mv.db.executescript(ESQUEMA)
    pasta = Path(saida or (mv_bots.SAIDA / "ecossistema"))
    pasta.mkdir(parents=True, exist_ok=True)
    planilha = pasta / "parcerias.csv"            # a equipe acrescenta à mão: fabricantes, investidores, collabs, testes…
    if planilha.is_file():
        importar_csv(mv, planilha.read_text(encoding="utf-8-sig"), "planilha da equipe")
    cids = cidades(pasta)
    if cidade:
        alvo = [c for c in cids if E_norm(cidade) in (E_norm(c["nome"]), E_norm(c["id"]))]
        if not alvo:
            raise ValueError(f"cidade fora do mapa: {cidade} (acrescente em cidades.json)")
        cids_busca = alvo
    else:
        cids_busca = cids
    tipos_area = AREAS[area][0] if area in AREAS else None
    online = (os.environ.get("PHYSIS_MERCADO_ONLINE", "1") != "0") if online is None else online
    descoberta = {}
    if online:
        for c in cids_busca:
            try:
                descoberta[c["id"]] = descobrir(mv, c, buscar, tipos_area, forcar)
            except Exception as e:  # noqa: BLE001 — sem internet: segue com o que já tem
                descoberta[c["id"]] = {"erro": type(e).__name__}
                mv.alertar("mercado", "sem_internet", c["id"], "info", f"Busca do OpenStreetMap em {c['nome']} sem resposta ({type(e).__name__})",
                           "Rodar num nó com internet; a planilha parcerias.csv continua valendo")
        dados = testar_dados_abertos(mv, abrir)
    else:
        dados = {"pulado": True}
    lac = lacunas(mv, cids)
    a_conferir = mv.db.execute("SELECT tipo, cidade, COUNT(*) FROM mv_parceria WHERE estado='a_conferir' GROUP BY tipo, cidade").fetchall()
    cmd = mv_comandos.Comandos(mv)
    for tipo, cidade, n in a_conferir:                      # um pedido por cidade × tipo (sem enxurrada)
        ref = f"mercado:{cidade}:{tipo}"
        if not mv.db.execute("SELECT 1 FROM mv_pedido_bot WHERE comando=? AND estado IN ('rascunho','na_fila')", (ref,)).fetchone():
            cmd._pedido("mercado", ref, "", "rascunho", f"{n} candidato(s) do tipo \"{TIPOS[tipo][0]}\" em {cidade} para conferir "
                        "(fonte, contato e interesse em parceria). Lista no mapa de parcerias (parcerias.geojson).", origem="mercado")
    for l in lac:
        if l["total"] == 0 and TIPOS[l["tipo"]][1] == []:
            mv.alertar("mercado", "sem_cadastro", f"{l['cidade']}:{l['area']}:{l['tipo']}", "info",
                       f"{l['cidade']} · {l['area']}: nenhum \"{TIPOS[l['tipo']][0]}\" cadastrado (só pesquisa da equipe encontra)",
                       "Acrescentar em parcerias.csv (nome;tipo;areas;cidade;uf;lat;lon;site;contato;modalidade;estado)")
    (pasta / "parcerias.geojson").write_text(json.dumps(geojson(mv), ensure_ascii=False), encoding="utf-8")
    if not planilha.is_file():
        planilha.write_text("nome;tipo;areas;cidade;uf;lat;lon;site;contato;modalidade;estado\n", encoding="utf-8")
    md = ["# Mapa do ecossistema de parcerias", "", f"Fases: {' → '.join(FASES)}. Cidades: {', '.join(c['nome'] + '/' + c['uf'] for c in cids)}.", "",
          "## Lacunas por cidade e área (total · conferidos)", "", "| Cidade | Área | " + " | ".join(TIPOS[t][0].split(' (')[0] for t in TIPOS) + " |",
          "|---|---|" + "---|" * len(TIPOS)]
    for c in cids:
        for area in AREAS:
            cel = []
            for t in TIPOS:
                l = next((x for x in lac if x["cidade"] == c["nome"] and x["area"] == area and x["tipo"] == t), None)
                cel.append("—" if l is None else f"{l['total']}·{l['conferidos']}")
            md.append(f"| {c['nome']} | {area} | " + " | ".join(cel) + " |")
    md += ["", "## Bases de dados abertas", "", "| Base | Para quê | Usada em | Situação |", "|---|---|---|---|"]
    st = dict(mv.db.execute("SELECT id, status FROM mv_dado_aberto").fetchall())
    md += [f"| [{n}]({u}) | {c} | {us} | {st.get(i, 'não testado')} |" for i, n, u, c, us in DADOS_ABERTOS]
    (pasta / "mapa-ecossistema.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    total = mv.db.execute("SELECT COUNT(*) FROM mv_parceria").fetchone()[0]
    r = {"pontos": total, "a_conferir": sum(x[2] for x in a_conferir), "descoberta": descoberta, "dados_abertos": dados,
         "lacunas_vazias": sum(1 for l in lac if l["total"] == 0), "arquivo": str(pasta / "mapa-ecossistema.md")}
    mv.fechar_alertas_nao_vistos("mercado", inicio)
    mv.registrar_execucao("mercado", inicio, json.dumps(r, ensure_ascii=False, default=str))
    return r
