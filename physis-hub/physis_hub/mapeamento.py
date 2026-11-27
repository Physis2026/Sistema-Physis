"""Mapeamento: o "contexto do lugar" que os outros módulos leem (Fase 1, pedido de 15/11/2026).

O Mapeamento depende do Início (dados obrigatórios do cliente) e do lote do Planejador. Ele junta:
1. Catálogo de camadas GIS abertas (CAMADAS): o servidor lê as camadas INSTALADAS numa pasta configurada
   (PHYSIS_CAMADAS) e entrega cada uma recortada na janela do lote. Vetor = GeoJSON; raster = grade ESRI ASCII
   (.asc), gerada uma vez a partir do GeoTIFF oficial pelo passo GDAL documentado em docs/MAPEAMENTO.md (o GDAL
   roda num contêiner Linux; aqui dentro só biblioteca padrão). NENHUM dado vem copiado no repositório: os nomes
   de fonte, produto e licença estão marcados [CONFERIR] até o engenheiro conferir na página oficial.
2. Arquivos do cliente: GeoJSON, KML/KMZ (XML da biblioteca padrão) e Shapefile em .zip (.shp/.dbf/.prj, leitor
   próprio de pontos, linhas e polígonos). Sistema de coordenadas aceito: EPSG:4326 (WGS 84) e EPSG:4674 (SIRGAS
   2000 geográfico), que é tratado como igual ao WGS 84 (diferença abaixo de 1 m, irrelevante no planejamento;
   anotado no índice). Projetado (UTM etc.) é recusado com a instrução de reprojetar. Arquivos e índice ficam no
   SQLite com o SHA-256 (integridade).
3. Contexto do lugar: um documento JSON por instalação, com a fonte de CADA campo; camada que falta vira
   "camada não instalada" (nunca um valor inventado).
4. Sol nas superfícies: irradiação mensal e anual em cada água de telhado, fachada e célula do terreno, com a mesma
   conta de PhysisCalc.fatorPlano (Liu e Jordan, fração difusa de Erbs) mais a sombra do horizonte (terreno e caixas
   dos prédios vizinhos, por marcha de raio). Espelho em sistema/physis-mapeamento.js.

Rotas: veja rota() no fim do arquivo (o servidor só repassa).
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import sqlite3
import struct
import time
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ESQUEMA_CONTEXTO = "physis-contexto-lugar/1"
ESQUEMA_INCIDENCIA = "physis-incidencia/1"
CONFERIR = "[CONFERIR]"

# ═══════════════ 1. Catálogo de camadas ═══════════════
# Uma entrada por camada. "arquivo" é relativo à pasta PHYSIS_CAMADAS. Tudo o que diz fonte, produto e licença
# está marcado [CONFERIR]: o engenheiro confere na página oficial antes de instalar (ninguém copia dado aqui).
_C = CONFERIR
CAMADAS: list[dict] = [
    {"id": "limites", "nome": {"pt": "Limites municipais e estaduais", "en": "Municipal and state boundaries"},
     "finalidade": {"pt": "Município e UF do lote; enquadramento legal", "en": "Plot municipality and state; legal framing"},
     "consumidores": ["inicio", "planejador", "carbono", "resiliencia"],
     "fonte": {"nome": f"IBGE {_C}", "produto": f"Malhas territoriais / malha municipal {_C}", "licenca": f"dados públicos do IBGE, uso livre com citação da fonte {_C}"},
     "formato": "vetor", "arquivo": "limites.geojson", "chave_config": "PHYSIS_CAMADAS/limites.geojson"},
    {"id": "relevo", "nome": {"pt": "Relevo e declividade", "en": "Terrain and slope"},
     "finalidade": {"pt": "Altitude e declividade do lote; APP de encosta e topo de morro; sombra do horizonte",
                    "en": "Plot elevation and slope; slope and hilltop APP; horizon shading"},
     "consumidores": ["planejador", "solar", "resiliencia", "sbn", "agua"],
     "fonte": {"nome": f"Copernicus DEM (ESA) ou SRTM (NASA/USGS) ou TOPODATA (INPE) {_C}",
               "produto": f"Copernicus DEM GLO-30 / SRTM 1 arc-second / TOPODATA {_C}",
               "licenca": f"Copernicus DEM: licença própria, uso livre com atribuição; SRTM: domínio público; TOPODATA: uso livre com citação {_C}"},
     "formato": "raster", "arquivo": "relevo.asc", "chave_config": "PHYSIS_CAMADAS/relevo.asc"},
    {"id": "hidrografia", "nome": {"pt": "Hidrografia (rios e nascentes)", "en": "Hydrography (rivers and springs)"},
     "finalidade": {"pt": "Rios e nascentes perto do lote; faixa de APP (calculada no Planejador)", "en": "Rivers and springs near the plot; APP strip (computed in the Planner)"},
     "consumidores": ["planejador", "agua", "sbn", "resiliencia"],
     "fonte": {"nome": f"ANA {_C}", "produto": f"Base Hidrográfica Ottocodificada (BHO) {_C}", "licenca": f"dados abertos da ANA {_C}"},
     "formato": "vetor", "arquivo": "hidrografia.geojson", "chave_config": "PHYSIS_HIDROGRAFIA ou PHYSIS_CAMADAS/hidrografia.geojson",
     "rota_existente": "/api/gis/hidrografia"},
    {"id": "uso_solo", "nome": {"pt": "Uso e cobertura do solo", "en": "Land use and land cover"},
     "finalidade": {"pt": "Parcela de mata, pasto, agricultura e área urbana no lote", "en": "Share of forest, pasture, farming and urban area in the plot"},
     "consumidores": ["sbn", "carbono", "planejador"],
     "fonte": {"nome": f"MapBiomas {_C}", "produto": f"Coleção anual de cobertura e uso (versão e ano {_C})", "licenca": f"CC BY 4.0 {_C}"},
     "formato": "raster", "arquivo": "uso_solo.asc", "legenda": "uso_solo.legenda.json", "chave_config": "PHYSIS_CAMADAS/uso_solo.asc (+ uso_solo.legenda.json)"},
    {"id": "solos", "nome": {"pt": "Solos", "en": "Soils"},
     "finalidade": {"pt": "Classe de solo do lote: fundação, infiltração, plantio", "en": "Plot soil class: foundations, infiltration, planting"},
     "consumidores": ["planejador", "sbn", "agua"],
     "fonte": {"nome": f"Embrapa Solos / IBGE {_C}", "produto": f"Mapa de Solos do Brasil (escala {_C})", "licenca": f"uso livre com citação {_C}"},
     "formato": "vetor", "arquivo": "solos.geojson", "chave_config": "PHYSIS_CAMADAS/solos.geojson"},
    {"id": "car", "nome": {"pt": "Cadastro Ambiental Rural (CAR)", "en": "Rural Environmental Registry (CAR)"},
     "finalidade": {"pt": "Imóveis rurais cadastrados que tocam o lote (código do imóvel, sem dado pessoal)", "en": "Registered rural properties touching the plot (property code, no personal data)"},
     "consumidores": ["planejador", "sbn", "carbono"],
     "fonte": {"nome": f"SICAR / Serviço Florestal Brasileiro {_C}", "produto": f"Base pública do CAR por município {_C}", "licenca": f"dados públicos {_C}; tratar como dado sensível pela LGPD se vier nome ou CPF"},
     "formato": "vetor", "arquivo": "car.geojson", "chave_config": "PHYSIS_CAMADAS/car.geojson"},
    {"id": "clima", "nome": {"pt": "Clima (arquivos EPW)", "en": "Climate (EPW files)"},
     "finalidade": {"pt": "Temperatura, irradiação e vento hora a hora para AVAC e EnergyPlus", "en": "Hourly temperature, irradiation and wind for HVAC and EnergyPlus"},
     "consumidores": ["avac", "solar", "carbono", "resiliencia"],
     "fonte": {"nome": f"INMET (estações) convertido em EPW {_C}", "produto": f"Arquivos climáticos EPW das estações do INMET {_C}", "licenca": f"dados públicos do INMET; licença do arquivo EPW conforme quem converteu {_C}"},
     "formato": "epw", "arquivo": "clima", "chave_config": "PHYSIS_CAMADAS/clima/*.epw (o mais perto do lote)"},
    {"id": "risco", "nome": {"pt": "Áreas de risco (deslizamento e inundação)", "en": "Risk areas (landslide and flood)"},
     "finalidade": {"pt": "Setores de risco que tocam o lote", "en": "Risk sectors touching the plot"},
     "consumidores": ["resiliencia", "planejador"],
     "fonte": {"nome": f"SGB/CPRM e CEMADEN {_C}", "produto": f"Setorização de riscos geológicos (SGB) e municípios monitorados (CEMADEN) {_C}", "licenca": f"dados públicos {_C}"},
     "formato": "vetor", "arquivo": "risco.geojson", "chave_config": "PHYSIS_CAMADAS/risco.geojson"},
    {"id": "irradiacao", "nome": {"pt": "Irradiação solar (atlas)", "en": "Solar irradiation (atlas)"},
     "finalidade": {"pt": "Irradiação global horizontal média do lugar", "en": "Mean global horizontal irradiation at the site"},
     "consumidores": ["solar", "avac", "secador", "mapeamento"],
     "fonte": {"nome": f"INPE / LABREN {_C}", "produto": f"Atlas Brasileiro de Energia Solar, 2ª edição {_C}", "licenca": f"uso livre com citação {_C}"},
     "formato": "raster", "arquivo": "irradiacao.asc", "mensal": "irradiacao_{mes:02d}.asc", "unidade": "kWh/m²·dia",
     "chave_config": "PHYSIS_CAMADAS/irradiacao.asc (+ irradiacao_01.asc … irradiacao_12.asc, opcionais)"},
    {"id": "vento", "nome": {"pt": "Vento (atlas eólico)", "en": "Wind (wind atlas)"},
     "finalidade": {"pt": "Velocidade média do vento para turbinas e ventilação natural", "en": "Mean wind speed for turbines and natural ventilation"},
     "consumidores": ["turbinas", "avac", "resiliencia"],
     "fonte": {"nome": f"CEPEL / CRESESB {_C}", "produto": f"Atlas do Potencial Eólico Brasileiro (altura {_C})", "licenca": f"uso livre com citação {_C}"},
     "formato": "raster", "arquivo": "vento.asc", "unidade": "m/s", "chave_config": "PHYSIS_CAMADAS/vento.asc"},
    {"id": "rede_eletrica", "nome": {"pt": "Rede elétrica (linhas e subestações)", "en": "Power grid (lines and substations)"},
     "finalidade": {"pt": "Distância até a rede para conexão de geração", "en": "Distance to the grid for generation hookup"},
     "consumidores": ["solar", "turbinas"],
     "fonte": {"nome": f"ANEEL {_C}", "produto": f"SIGEL (Sistema de Informações Georreferenciadas do Setor Elétrico) {_C}", "licenca": f"dados abertos da ANEEL {_C}"},
     "formato": "vetor", "arquivo": "rede_eletrica.geojson", "chave_config": "PHYSIS_CAMADAS/rede_eletrica.geojson"},
    {"id": "osm", "nome": {"pt": "Edificações e vias (OpenStreetMap)", "en": "Buildings and roads (OpenStreetMap)"},
     "finalidade": {"pt": "Prédios vizinhos (sombra) e acesso viário", "en": "Neighbouring buildings (shading) and road access"},
     "consumidores": ["mapeamento", "planejador", "avac", "circular"],
     "fonte": {"nome": f"OpenStreetMap (© colaboradores do OpenStreetMap) {_C}", "produto": f"Extrato regional (edificações e vias) {_C}",
               "licenca": f"ODbL 1.0: atribuição e compartilhamento pela mesma licença do banco derivado {_C}"},
     "formato": "vetor", "arquivo": "osm.geojson", "chave_config": "PHYSIS_CAMADAS/osm.geojson"},
]
POR_ID = {c["id"]: c for c in CAMADAS}

MAX_BBOX_GRAUS = 0.25            # janela máxima (≈ 27 km), igual à da hidrografia
MAX_FEICOES = 2000               # por resposta de camada
MAX_VERTICES = 100_000
MAX_CAMADA_BYTES = 256 * 1024 * 1024      # camada maior: recortar a região com o GDAL antes (docs/MAPEAMENTO.md)
MAX_CELULAS = 250_000            # células de raster lidas por pedido
MAX_EPW_BYTES = 8 * 1024 * 1024
_CACHE: dict = {}


def pasta_camadas(pasta: str | os.PathLike | None = None) -> Path | None:
    p = pasta if pasta is not None else os.environ.get("PHYSIS_CAMADAS", "")
    return Path(p) if p else None


def _mosaico(c: dict, pasta: Path | None) -> list[dict] | None:
    """Camada em mosaico (estados inteiros, 24/11/2026): pasta <nome>/ com indice.json = [{"arquivo", "bbox"}].
    Os ladrilhos têm sobreposição maior que a janela máxima (ferramentas/mosaico_camadas.py), então toda janela
    válida cabe inteira em pelo menos um ladrilho e o arquivo único continua sendo lido do mesmo jeito."""
    if not pasta or c["formato"] == "epw":
        return None
    ind = pasta / Path(c["arquivo"]).stem / "indice.json"
    if not ind.is_file():
        return None
    try:
        lista = _ler_json_cache(ind)
        return [x for x in lista if isinstance(x, dict) and "arquivo" in x and len(x.get("bbox") or []) == 4]
    except (OSError, ValueError):
        return None


def _arquivo(c: dict, pasta: Path | None, b=None) -> Path | None:
    if c["id"] == "hidrografia" and os.environ.get("PHYSIS_HIDROGRAFIA"):
        return Path(os.environ["PHYSIS_HIDROGRAFIA"])
    if pasta is None:
        return None
    unico = pasta / c["arquivo"]
    if unico.exists() or b is None:
        return unico
    m = _mosaico(c, pasta)
    if m:
        base = pasta / Path(c["arquivo"]).stem
        for x in m:
            o, s, l, n = x["bbox"]
            if o <= b[0] and s <= b[1] and l >= b[2] and n >= b[3]:
                return base / x["arquivo"]
        return None                     # janela fora dos estados instalados
    return unico


def _instalada(c: dict, pasta: Path | None) -> bool:
    a = _arquivo(c, pasta)
    if a is None:
        return False
    if c["formato"] == "epw":
        return a.is_dir() and any(a.glob("*.epw"))
    return a.is_file() or bool(_mosaico(c, pasta))


def _meta_fonte(arquivo) -> dict:
    """<arquivo>.fonte.json gravado pelo bot de camadas (endereço, data, provisória, licença)."""
    try:
        m = Path(str(arquivo) + ".fonte.json")
        return json.loads(m.read_text(encoding="utf-8")) if m.is_file() and m.stat().st_size < 1_000_000 else {}
    except (OSError, ValueError):
        return {}


def extras(pasta: Path | None) -> list[dict]:
    """Camadas extras instaladas pelo bot (extras/indice.json, 27/11/2026): APP/CAR, biodiversidade, energia, vegetação..."""
    if not pasta:
        return []
    ind = pasta / "extras" / "indice.json"
    try:
        lista = _ler_json_cache(ind) if ind.is_file() else []
    except (OSError, ValueError):
        return []
    out = []
    for x in lista if isinstance(lista, list) else []:
        if not (isinstance(x, dict) and re.match(r"^x_[a-z0-9_]{1,40}$", str(x.get("id", ""))) and x.get("formato") in ("vetor", "raster")
                and str(x.get("arquivo", "")).startswith("extras/") and ".." not in str(x.get("arquivo"))):
            continue
        d = dict(x)
        nome = d.get("nome") if isinstance(d.get("nome"), dict) else {"pt": str(d.get("nome") or d["id"]), "en": str(d.get("nome") or d["id"])}
        d["nome"] = nome
        d.setdefault("grupo", "extras")
        d["fonte"] = {"nome": "[CONFERIR]", "produto": nome["pt"], "licenca": "[CONFERIR]", **(d.get("fonte") if isinstance(d.get("fonte"), dict) else {})}
        d.setdefault("finalidade", {"pt": "camada extra (" + str(d["grupo"]) + ")", "en": "extra layer"})
        d.setdefault("consumidores", ["mapeamento"])
        d.setdefault("chave_config", "fontes-camadas.txt (extra:" + d["id"] + ")")
        out.append(d)
    return out


def catalogo(pasta=None) -> list[dict]:
    """Catálogo com o estado de cada camada nesta instalação ('instalada' ou 'nao_instalada')."""
    p = pasta_camadas(pasta)
    out = []
    for c in CAMADAS:
        d = json.loads(json.dumps(c))
        d["status"] = "instalada" if _instalada(c, p) else "nao_instalada"
        out.append(d)
    for c in extras(p):
        d = dict(c, extra=True); d["status"] = "instalada" if (p / c["arquivo"]).is_file() else "nao_instalada"
        out.append(d)
    return out


# ── janela e geometria ──
def validar_bbox(bbox) -> list[float]:
    if isinstance(bbox, str):
        bbox = bbox.split(",")
    try:
        b = [float(x) for x in bbox]
    except (TypeError, ValueError):
        raise ValueError("bbox = lon_min,lat_min,lon_max,lat_max")
    if len(b) != 4 or not all(math.isfinite(x) for x in b) or b[0] >= b[2] or b[1] >= b[3]:
        raise ValueError("bbox = lon_min,lat_min,lon_max,lat_max")
    if not (-180 <= b[0] and b[2] <= 180 and -90 <= b[1] and b[3] <= 90):
        raise ValueError("bbox fora das coordenadas geográficas")
    if b[2] - b[0] > MAX_BBOX_GRAUS or b[3] - b[1] > MAX_BBOX_GRAUS:
        raise ValueError(f"janela grande demais (máximo {MAX_BBOX_GRAUS}° de lado)")
    return b


def _dentro(p, b) -> bool:
    return b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]


def _liang_barsky(a, c, b):
    """Recorta o segmento a→c na janela b; devolve (p0, p1) ou None."""
    x0, y0, dx, dy = a[0], a[1], c[0] - a[0], c[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - b[0]), (dx, b[2] - x0), (-dy, y0 - b[1]), (dy, b[3] - y0)):
        if p == 0:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            if r > t1:
                return None
            t0 = max(t0, r)
        else:
            if r < t0:
                return None
            t1 = min(t1, r)
    return [x0 + t0 * dx, y0 + t0 * dy], [x0 + t1 * dx, y0 + t1 * dy]


def recortar_linha(coords, b) -> list[list]:
    partes, atual = [], []
    for i in range(len(coords) - 1):
        s = _liang_barsky(coords[i], coords[i + 1], b)
        if s is None:
            if len(atual) >= 2:
                partes.append(atual)
            atual = []
            continue
        p0, p1 = [round(v, 7) for v in s[0]], [round(v, 7) for v in s[1]]
        if atual and atual[-1] == p0:
            atual.append(p1)
        else:
            if len(atual) >= 2:
                partes.append(atual)
            atual = [p0, p1]
    if len(atual) >= 2:
        partes.append(atual)
    return partes


def recortar_anel(anel, b) -> list:
    """Sutherland–Hodgman do anel contra o retângulo b (o resultado é um anel fechado, ou [])."""
    pts = [list(p[:2]) for p in anel]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    for lado in range(4):
        if not pts:
            break
        dentro = (lambda p: p[0] >= b[0]), (lambda p: p[0] <= b[2]), (lambda p: p[1] >= b[1]), (lambda p: p[1] <= b[3])
        f = dentro[lado]

        def cruza(p, q, lado=lado):
            if lado < 2:
                x = b[0] if lado == 0 else b[2]
                t = (x - p[0]) / (q[0] - p[0])
                return [x, p[1] + t * (q[1] - p[1])]
            y = b[1] if lado == 2 else b[3]
            t = (y - p[1]) / (q[1] - p[1])
            return [p[0] + t * (q[0] - p[0]), y]
        novo = []
        for i, q in enumerate(pts):
            p = pts[i - 1]
            if f(q):
                if not f(p):
                    novo.append(cruza(p, q))
                novo.append(q)
            elif f(p):
                novo.append(cruza(p, q))
        pts = novo
    if len(pts) < 3:
        return []
    pts = [[round(x, 7), round(y, 7)] for x, y in pts]
    return pts + [pts[0]]


def recortar_geometria(g: dict, b) -> dict | None:
    t, c = (g or {}).get("type"), (g or {}).get("coordinates")
    if c is None:
        return None
    if t == "Point":
        return g if _dentro(c, b) else None
    if t == "MultiPoint":
        r = [p for p in c if _dentro(p, b)]
        return {"type": "MultiPoint", "coordinates": r} if r else None
    if t in ("LineString", "MultiLineString"):
        partes = [x for l in ([c] if t == "LineString" else c) for x in recortar_linha(l, b)]
        if not partes:
            return None
        return {"type": "LineString", "coordinates": partes[0]} if len(partes) == 1 else {"type": "MultiLineString", "coordinates": partes}
    if t in ("Polygon", "MultiPolygon"):
        polys = []
        for poly in ([c] if t == "Polygon" else c):
            ext = recortar_anel(poly[0], b) if poly else []
            if ext:
                polys.append([ext] + [a for a in (recortar_anel(r, b) for r in poly[1:]) if a])
        if not polys:
            return None
        return {"type": "Polygon", "coordinates": polys[0]} if len(polys) == 1 else {"type": "MultiPolygon", "coordinates": polys}
    return None


def _n_vertices(g) -> int:
    def conta(c):
        return 1 if c and isinstance(c[0], (int, float)) else sum(conta(x) for x in c)
    try:
        return conta(g.get("coordinates") or [])
    except (TypeError, AttributeError):
        return 0


def _ler_json_cache(caminho: Path) -> dict:
    st = caminho.stat()
    if st.st_size > MAX_CAMADA_BYTES:
        raise ValueError("camada grande demais: recorte a região com o GDAL (docs/MAPEAMENTO.md)")
    c = _CACHE.get(str(caminho))
    if c and c[0] == st.st_mtime:
        return c[1]
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    _CACHE[str(caminho)] = (st.st_mtime, dados)
    return dados


def recortar_vetor(caminho: Path, b) -> dict:
    dados = _ler_json_cache(caminho)
    feats, nv, cortado = [], 0, False
    for f in dados.get("features") or []:
        g = recortar_geometria((f or {}).get("geometry") or {}, b)
        if g is None:
            continue
        feats.append({"type": "Feature", "properties": (f or {}).get("properties") or {}, "geometry": g})
        nv += _n_vertices(g)
        if len(feats) >= MAX_FEICOES or nv >= MAX_VERTICES:
            cortado = True
            break
    return {"type": "FeatureCollection", "features": feats, "cortado": cortado, "fonte_arquivo": str(dados.get("fonte") or "")}


# ── raster ESRI ASCII (.asc) ──
def ler_asc_janela(caminho: Path, b) -> dict:
    """Lê só as linhas e colunas da grade cujo centro cai na janela b (lon/lat). Valores None = sem dado."""
    with open(caminho, encoding="ascii", errors="strict") as f:
        cab = {}
        while len(cab) < 6:
            pos = f.tell()
            linha = f.readline()
            if not linha:
                break
            partes = linha.split()
            if len(partes) == 2 and re.fullmatch(r"[A-Za-z_]+", partes[0]):
                cab[partes[0].lower()] = float(partes[1])
            else:
                f.seek(pos)
                break
        try:
            nc, nr, cs = int(cab["ncols"]), int(cab["nrows"]), cab["cellsize"]
        except KeyError:
            raise ValueError("grade .asc sem cabeçalho (ncols, nrows, xllcorner, yllcorner, cellsize)")
        if "xllcenter" in cab:
            x0, y0 = cab["xllcenter"] - cs / 2, cab["yllcenter"] - cs / 2
        else:
            x0, y0 = cab["xllcorner"], cab["yllcorner"]
        nd = cab.get("nodata_value")
        c0 = max(0, math.ceil((b[0] - x0) / cs - 0.5))
        c1 = min(nc - 1, math.floor((b[2] - x0) / cs - 0.5))
        # linha r (de cima para baixo) tem centro y = y0 + (nr - r - 0.5)·cs
        r0 = max(0, math.ceil(nr - 0.5 - (b[3] - y0) / cs))
        r1 = min(nr - 1, math.floor(nr - 0.5 - (b[1] - y0) / cs))
        if c1 < c0 or r1 < r0:
            # 25/11/2026: grade grossa (ex.: NASA POWER, 0,5°) e lote pequeno: nenhum centro cai na janela. Se a janela está
            # dentro da grade, vale a célula que contém o centro da janela (o valor daquele lugar, sem interpolar).
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            cc, rr = math.floor((cx - x0) / cs), math.floor(nr - (cy - y0) / cs)
            if not (0 <= cc < nc and 0 <= rr < nr):
                return {"nx": 0, "ny": 0, "cs": cs, "valores": [], "lon0": None, "lat0": None}
            c0 = c1 = cc
            r0 = r1 = rr
        if (c1 - c0 + 1) * (r1 - r0 + 1) > MAX_CELULAS:
            raise ValueError("janela com células demais para esta grade")
        vals = []
        r = 0
        for linha in f:
            if r > r1:
                break
            if r >= r0:
                cel = linha.split()
                if len(cel) < nc:
                    raise ValueError("grade .asc com linha curta")
                for c in range(c0, c1 + 1):
                    v = float(cel[c])
                    vals.append(None if (nd is not None and v == nd) or not math.isfinite(v) else v)
            r += 1
    return {"nx": c1 - c0 + 1, "ny": r1 - r0 + 1, "cs": cs, "valores": vals,
            "lon0": x0 + (c0 + 0.5) * cs, "lat0": y0 + (nr - r0 - 0.5) * cs}     # centro da célula de cima à esquerda


def _celulas(j: dict, poligono=None):
    """(lon, lat, valor) de cada célula; com polígono, só as de centro dentro dele."""
    for i in range(j["ny"]):
        lat = j["lat0"] - i * j["cs"]
        for k in range(j["nx"]):
            lon = j["lon0"] + k * j["cs"]
            if poligono and not dentro_poligono((lon, lat), poligono):
                continue
            yield lon, lat, j["valores"][i * j["nx"] + k], i, k


def resumo_raster(j: dict, poligono=None) -> dict:
    v = [c[2] for c in _celulas(j, poligono) if c[2] is not None]
    if not v:
        return {"n": 0}
    v.sort()
    return {"n": len(v), "min": v[0], "max": v[-1], "media": sum(v) / len(v), "p50": v[len(v) // 2]}


def declividade_raster(j: dict, poligono=None) -> dict:
    """Declividade (%) por diferenças centrais; célula em graus convertida em metros na latitude do lote."""
    if j["nx"] < 3 or j["ny"] < 3:
        return {"n": 0}
    lat_m = j["lat0"] - j["ny"] * j["cs"] / 2
    dxm, dym = j["cs"] * 111320 * math.cos(math.radians(lat_m)), j["cs"] * 110540
    Z, nx = j["valores"], j["nx"]
    out = []
    for lon, lat, z, i, k in _celulas(j, poligono):
        if z is None or i in (0, j["ny"] - 1) or k in (0, nx - 1):
            continue
        e, w, n, s = Z[i * nx + k + 1], Z[i * nx + k - 1], Z[(i - 1) * nx + k], Z[(i + 1) * nx + k]
        if None in (e, w, n, s):
            continue
        out.append(100 * math.hypot((e - w) / (2 * dxm), (n - s) / (2 * dym)))
    if not out:
        return {"n": 0}
    out.sort()
    return {"n": len(out), "media_pct": sum(out) / len(out), "p50_pct": out[len(out) // 2], "p90_pct": out[min(len(out) - 1, int(0.9 * len(out)))],
            "max_pct": out[-1], "fracao_acima_30pct": sum(1 for x in out if x > 30) / len(out),
            "fracao_acima_100pct": sum(1 for x in out if x > 100) / len(out)}


def classes_raster(j: dict, poligono=None, legenda: dict | None = None) -> list[dict]:
    cont: dict = {}
    for c in _celulas(j, poligono):
        if c[2] is not None:
            k = int(round(c[2]))
            cont[k] = cont.get(k, 0) + 1
    n = sum(cont.values()) or 1
    leg = legenda or {}
    return [{"classe": k, "nome": leg.get(str(k)), "fracao": v / n} for k, v in sorted(cont.items(), key=lambda x: -x[1])]


def camada(id_: str, bbox, pasta=None, poligono=None) -> dict:
    """Uma camada recortada na janela: vetor (GeoJSON) ou raster (resumo)."""
    c = POR_ID.get(id_) or {x["id"]: x for x in extras(pasta_camadas(pasta))}.get(id_)
    if not c:
        return {"ok": False, "erro": "camada desconhecida"}
    try:
        b = validar_bbox(bbox)
    except ValueError as e:
        return {"ok": False, "erro": str(e)}
    p = pasta_camadas(pasta)
    if not _instalada(c, p):
        return {"ok": False, "sem_camada": True, "camada": id_, "erro": "camada não instalada neste servidor"}
    base = {"ok": True, "camada": id_, "fonte": c["fonte"], "bbox": b}
    a = _arquivo(c, p, b)
    if a is None or (c["formato"] != "epw" and not a.is_file()):
        return {"ok": False, "sem_camada": True, "camada": id_, "erro": "lugar fora da região instalada desta camada"}
    try:
        if c["formato"] == "vetor":
            return {**base, "tipo": "vetor", "geojson": recortar_vetor(a, b)}
        if c["formato"] == "raster":
            j = ler_asc_janela(a, b)
            r = {**base, "tipo": "raster", "resumo": resumo_raster(j, poligono), "celula_graus": j["cs"]}
            if id_ == "relevo":
                r["declividade"] = declividade_raster(j, poligono)
            if id_ == "uso_solo":
                leg = None
                meta = _meta_fonte(a)
                if meta.get("provisoria"):          # GLAD/OpenGeoHub no lugar do MapBiomas: nunca aplicar a legenda do MapBiomas
                    r["provisoria"] = str(meta.get("produto") or "fonte provisória") + " · " + str(meta.get("legenda") or "")
                elif p and (p / c["legenda"]).is_file():
                    leg = json.loads((p / c["legenda"]).read_text(encoding="utf-8"))
                r["classes"] = classes_raster(j, poligono, leg)
            if c.get("extra") or str(id_).startswith("x_"):
                r["banda"] = c.get("banda") or {}
            if id_ == "irradiacao" and p:
                meses = []
                for m in range(1, 13):
                    am = p / c["mensal"].format(mes=m)
                    meses.append(resumo_raster(ler_asc_janela(am, b), poligono).get("media") if am.is_file() else None)
                r["mensal"] = meses if all(x is not None for x in meses) else None
            return r
        if c["formato"] == "epw":
            lat, lon = (b[1] + b[3]) / 2, (b[0] + b[2]) / 2
            return {**base, "tipo": "epw", "clima": epw_mais_proximo(a, lat, lon)}
    except (OSError, ValueError, UnicodeDecodeError) as e:
        return {"ok": False, "camada": id_, "erro": f"camada ilegível: {e}"}
    return {"ok": False, "erro": "formato desconhecido"}


# ── EPW (texto CSV, leitor próprio) ──
def _epw_cabecalho(caminho: Path):
    with open(caminho, encoding="latin-1") as f:
        p = f.readline().strip().split(",")
    if not p or p[0].upper() != "LOCATION" or len(p) < 10:
        return None
    try:
        return {"cidade": p[1], "uf": p[2], "pais": p[3], "fonte": p[4], "wmo": p[5], "lat": float(p[6]), "lon": float(p[7]), "altitude_m": float(p[9])}
    except ValueError:
        return None


def resumo_epw(caminho: Path) -> dict:
    if caminho.stat().st_size > MAX_EPW_BYTES:
        raise ValueError("arquivo EPW grande demais")
    cab = _epw_cabecalho(caminho) or {}
    t = [[] for _ in range(12)]
    ghi = [0.0] * 12
    horas = [0] * 12
    vento = []
    with open(caminho, encoding="latin-1") as f:
        for i, linha in enumerate(f):
            if i < 8:
                continue
            c = linha.split(",")
            if len(c) < 22:
                continue
            try:
                m = int(c[1]) - 1
                tb, g, ws = float(c[6]), float(c[13]), float(c[21])
            except ValueError:
                continue
            if not 0 <= m < 12:
                continue
            horas[m] += 1
            if tb < 99:
                t[m].append(tb)
            if g < 9999:
                ghi[m] += g
            if ws < 999:
                vento.append(ws)
    if sum(horas) < 8000:
        raise ValueError("EPW incompleto (menos de 8.000 horas)")
    return {**cab, "temp_media_c": [sum(x) / len(x) if x else None for x in t],
            "ghi_kwh_m2_dia": [ghi[m] / 1000 / (horas[m] / 24) if horas[m] else None for m in range(12)],
            "ghi_anual_kwh_m2": sum(ghi) / 1000, "vento_medio_m_s": sum(vento) / len(vento) if vento else None, "arquivo": caminho.name}


def epw_mais_proximo(pasta: Path, lat: float, lon: float) -> dict:
    melhor = None
    for a in sorted(pasta.glob("*.epw")):
        cab = _epw_cabecalho(a)
        if cab:
            d = distancia_m((lon, lat), (cab["lon"], cab["lat"]))
            if melhor is None or d < melhor[0]:
                melhor = (d, a)
    if melhor is None:
        raise ValueError("nenhum EPW legível na pasta")
    r = resumo_epw(melhor[1])
    r["distancia_km"] = melhor[0] / 1000
    return r


# ── geometria plana local (lon/lat → metros) ──
def distancia_m(a, b) -> float:
    k = 111320 * math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * k, (a[1] - b[1]) * 110540)


def _dist_seg_m(p, a, c) -> float:
    k = 111320 * math.cos(math.radians(p[1]))
    ax, ay, cx, cy = (a[0] - p[0]) * k, (a[1] - p[1]) * 110540, (c[0] - p[0]) * k, (c[1] - p[1]) * 110540
    dx, dy = cx - ax, cy - ay
    t = max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy or 1)))
    return math.hypot(ax + t * dx, ay + t * dy)


def distancia_geometria_m(p, g: dict) -> float | None:
    t, c = g.get("type"), g.get("coordinates")
    if t == "Point":
        return distancia_m(p, c)
    if t == "MultiPoint":
        return min((distancia_m(p, q) for q in c), default=None)
    linhas = {"LineString": [c], "MultiLineString": c, "Polygon": c, "MultiPolygon": [r for poly in (c or []) for r in poly]}.get(t)
    if not linhas:
        return None
    if t in ("Polygon", "MultiPolygon") and dentro_geometria(p, g):
        return 0.0
    d = None
    for l in linhas:
        for i in range(len(l) - 1):
            x = _dist_seg_m(p, l[i], l[i + 1])
            d = x if d is None or x < d else d
    return d


def dentro_poligono(p, anel) -> bool:
    c = False
    j = len(anel) - 1
    for i in range(len(anel)):
        xi, yi = anel[i][0], anel[i][1]
        xj, yj = anel[j][0], anel[j][1]
        if (yi > p[1]) != (yj > p[1]) and p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


def dentro_geometria(p, g: dict) -> bool:
    t, c = g.get("type"), g.get("coordinates") or []
    polys = [c] if t == "Polygon" else c if t == "MultiPolygon" else []
    for poly in polys:
        if poly and dentro_poligono(p, poly[0]) and not any(dentro_poligono(p, h) for h in poly[1:]):
            return True
    return False


def area_m2(anel) -> float:
    if len(anel) < 3:
        return 0.0
    lat0 = sum(p[1] for p in anel) / len(anel)
    k = 111320 * math.cos(math.radians(lat0))
    xy = [((p[0]) * k, p[1] * 110540) for p in anel]
    s = 0.0
    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % len(xy)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


# ═══════════════ 2. Arquivos do cliente ═══════════════
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_ZIP_DESCOMPACTADO = 80 * 1024 * 1024
MAX_UPLOAD_FEICOES = 20_000
MAX_UPLOAD_VERTICES = 500_000
NOTA_SIRGAS = ("SIRGAS 2000 geográfico (EPSG:4674) tratado como WGS 84 (EPSG:4326): os dois diferem menos de 1 m, "
               "o que não muda o planejamento. Para levantamento de precisão, reprojete com transformação oficial.")


class ArquivoInvalido(ValueError):
    pass


def _crs_de_nome(nome: str) -> str | None:
    n = (nome or "").upper().replace(" ", "")
    if re.search(r"EPSG:+4326\b|EPSG::4326|CRS84|OGC:1\.3:CRS84|WGS_?84$", n):
        return "EPSG:4326"
    if re.search(r"EPSG:+4674\b|EPSG::4674", n):
        return "EPSG:4674"
    return None


def crs_do_prj(wkt: str) -> str:
    """WKT do .prj → 'EPSG:4326' ou 'EPSG:4674'. Projetado ou outro datum = ArquivoInvalido."""
    w = (wkt or "").upper()
    if not w.strip():
        raise ArquivoInvalido("o .prj está vazio")
    if w.lstrip().startswith(("PROJCS", "PROJCRS")):
        raise ArquivoInvalido("o Shapefile está em coordenadas projetadas (ex.: UTM). Reprojete para EPSG:4326 (WGS 84) no QGIS ou com ogr2ogr e envie de novo.")
    if not w.lstrip().startswith(("GEOGCS", "GEOGCRS", "GEODCRS")):
        raise ArquivoInvalido("o .prj não descreve um sistema geográfico reconhecido")
    if "SIRGAS" in w and "2000" in w:
        return "EPSG:4674"
    if re.search(r"WGS[ _]?(19)?84", w):
        return "EPSG:4326"
    raise ArquivoInvalido("datum não aceito: use WGS 84 (EPSG:4326) ou SIRGAS 2000 geográfico (EPSG:4674)")


def _conferir_coordenadas(fc: dict) -> None:
    nf = len(fc["features"])
    if nf == 0:
        raise ArquivoInvalido("o arquivo não tem feições")
    if nf > MAX_UPLOAD_FEICOES:
        raise ArquivoInvalido(f"feições demais (máximo {MAX_UPLOAD_FEICOES})")
    nv = 0
    for f in fc["features"]:
        g = f.get("geometry")
        if g is None:
            continue
        nv += _n_vertices(g)
        for p in _pontos(g):
            if not (len(p) >= 2 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in p[:2])):
                raise ArquivoInvalido("coordenada inválida")
            if not (-180 <= p[0] <= 180 and -90 <= p[1] <= 90):
                raise ArquivoInvalido("coordenadas fora da faixa de longitude e latitude: o arquivo parece projetado (ex.: UTM). Reprojete para EPSG:4326.")
    if nv > MAX_UPLOAD_VERTICES:
        raise ArquivoInvalido(f"vértices demais (máximo {MAX_UPLOAD_VERTICES})")


def _pontos(g):
    def anda(c):
        if c and isinstance(c[0], (int, float)):
            yield c
        else:
            for x in c or []:
                yield from anda(x)
    yield from anda(g.get("coordinates") or [])


TIPOS_GEOJSON = {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}


def ler_geojson(dados: bytes) -> dict:
    try:
        j = json.loads(dados.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError):
        raise ArquivoInvalido("GeoJSON ilegível (JSON inválido ou fora de UTF-8)")
    crs, nota = "EPSG:4326", ""
    if isinstance(j, dict) and isinstance(j.get("crs"), dict):          # membro antigo (GeoJSON 2008)
        nome = ((j["crs"].get("properties") or {}).get("name")) or ""
        crs = _crs_de_nome(nome)
        if crs is None:
            raise ArquivoInvalido(f"sistema de coordenadas não aceito ({nome[:60]}): use EPSG:4326")
    if isinstance(j, dict) and j.get("type") == "Feature":
        j = {"type": "FeatureCollection", "features": [j]}
    elif isinstance(j, dict) and j.get("type") in TIPOS_GEOJSON | {"GeometryCollection"}:
        j = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": j}]}
    if not (isinstance(j, dict) and j.get("type") == "FeatureCollection" and isinstance(j.get("features"), list)):
        raise ArquivoInvalido("não é um GeoJSON (FeatureCollection, Feature ou geometria)")
    feats = []
    for f in j["features"]:
        g = (f or {}).get("geometry") if isinstance(f, dict) else None
        if g is not None and g.get("type") not in TIPOS_GEOJSON:
            raise ArquivoInvalido(f"geometria não aceita: {str(g.get('type'))[:30]} (aceitas: pontos, linhas e polígonos)")
        pr = (f or {}).get("properties") if isinstance(f, dict) else None
        feats.append({"type": "Feature", "properties": pr if isinstance(pr, dict) else {}, "geometry": g})
    fc = {"type": "FeatureCollection", "features": feats}
    _conferir_coordenadas(fc)
    if crs == "EPSG:4674":
        nota = NOTA_SIRGAS
    return {"geojson": fc, "crs": crs, "nota_crs": nota}


# ── KML / KMZ ──
def _sem_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _coords_kml(txt: str) -> list:
    out = []
    for t in (txt or "").split():
        p = t.split(",")
        try:
            out.append([float(p[0]), float(p[1])])
        except (ValueError, IndexError):
            raise ArquivoInvalido("coordenada KML inválida")
    return out


def _geom_kml(el) -> list[dict]:
    t = _sem_ns(el.tag)
    filho = lambda e, nome: next((x for x in e.iter() if _sem_ns(x.tag) == nome), None)
    if t == "Point":
        c = _coords_kml(getattr(filho(el, "coordinates"), "text", ""))
        return [{"type": "Point", "coordinates": c[0]}] if c else []
    if t == "LineString":
        c = _coords_kml(getattr(filho(el, "coordinates"), "text", ""))
        return [{"type": "LineString", "coordinates": c}] if len(c) >= 2 else []
    if t == "Polygon":
        aneis = []
        for parte in el:
            n = _sem_ns(parte.tag)
            if n in ("outerBoundaryIs", "innerBoundaryIs"):
                c = _coords_kml(getattr(filho(parte, "coordinates"), "text", ""))
                if len(c) >= 3:
                    if c[0] != c[-1]:
                        c.append(c[0])
                    aneis.insert(0, c) if n == "outerBoundaryIs" else aneis.append(c)
        return [{"type": "Polygon", "coordinates": aneis}] if aneis else []
    if t == "MultiGeometry":
        return [g for x in el for g in _geom_kml(x)]
    if t in ("Model", "Track", "MultiTrack"):
        raise ArquivoInvalido(f"elemento KML não aceito: {t} (aceitos: pontos, linhas e polígonos)")
    return []


def ler_kml(dados: bytes) -> dict:
    if dados[:2] == b"PK":
        try:
            z = zipfile.ZipFile(io.BytesIO(dados))
        except zipfile.BadZipFile:
            raise ArquivoInvalido("KMZ ilegível")
        nomes = [i for i in z.infolist() if i.filename.lower().endswith(".kml")]
        if not nomes or nomes[0].file_size > MAX_ZIP_DESCOMPACTADO:
            raise ArquivoInvalido("KMZ sem .kml (ou grande demais)")
        dados = z.read(nomes[0])
    cabeca = dados[:4096].upper()
    if b"<!DOCTYPE" in cabeca or b"<!ENTITY" in dados.upper():
        raise ArquivoInvalido("KML com DOCTYPE ou ENTITY não é aceito (segurança)")
    try:
        raiz = ET.fromstring(dados)
    except ET.ParseError:
        raise ArquivoInvalido("KML ilegível (XML inválido)")
    feats = []
    for pm in raiz.iter():
        if _sem_ns(pm.tag) != "Placemark":
            continue
        props = {}
        for x in pm:
            n = _sem_ns(x.tag)
            if n in ("name", "description") and x.text:
                props["nome" if n == "name" else "descricao"] = x.text.strip()[:500]
            if n == "ExtendedData":
                for d in x.iter():
                    if _sem_ns(d.tag) == "Data" and d.get("name"):
                        v = next((y.text for y in d if _sem_ns(y.tag) == "value"), None)
                        props[d.get("name")[:60]] = (v or "")[:500]
                    if _sem_ns(d.tag) == "SimpleData" and d.get("name"):
                        props[d.get("name")[:60]] = (d.text or "")[:500]
        geoms = [g for x in pm for g in _geom_kml(x)]
        for g in geoms:
            feats.append({"type": "Feature", "properties": dict(props), "geometry": g})
    fc = {"type": "FeatureCollection", "features": feats}
    _conferir_coordenadas(fc)
    return {"geojson": fc, "crs": "EPSG:4326", "nota_crs": "KML é sempre WGS 84 (EPSG:4326) pela especificação OGC."}


# ── Shapefile (.zip com .shp, .dbf, .prj) ──
TIPOS_SHP = {0: "Null", 1: "Point", 3: "PolyLine", 5: "Polygon", 8: "MultiPoint",
             11: "PointZ", 13: "PolyLineZ", 15: "PolygonZ", 18: "MultiPointZ",
             21: "PointM", 23: "PolyLineM", 25: "PolygonM", 28: "MultiPointM"}


def _anel_horario(anel) -> bool:
    s = 0.0
    for i in range(len(anel) - 1):
        s += (anel[i + 1][0] - anel[i][0]) * (anel[i + 1][1] + anel[i][1])
    return s > 0


def ler_shp(shp: bytes) -> list:
    """Geometrias GeoJSON (ou None) de cada registro do .shp. Só pontos, linhas e polígonos (com Z/M ignorados)."""
    if len(shp) < 100 or struct.unpack(">i", shp[0:4])[0] != 9994:
        raise ArquivoInvalido(".shp ilegível (cabeçalho)")
    tipo = struct.unpack("<i", shp[32:36])[0]
    if tipo not in TIPOS_SHP:
        raise ArquivoInvalido(f"tipo de Shapefile não aceito ({tipo}{', MultiPatch' if tipo == 31 else ''}): só pontos, linhas e polígonos")
    out, pos = [], 100
    while pos + 8 <= len(shp):
        tam = struct.unpack(">i", shp[pos + 4:pos + 8])[0] * 2
        rec = shp[pos + 8:pos + 8 + tam]
        pos += 8 + tam
        if len(rec) < 4:
            raise ArquivoInvalido(".shp cortado")
        t = struct.unpack("<i", rec[0:4])[0]
        if t == 0:
            out.append(None)
            continue
        if t not in TIPOS_SHP:
            raise ArquivoInvalido(f"registro de tipo não aceito ({t})")
        base = t % 10
        try:
            if base == 1:
                x, y = struct.unpack("<2d", rec[4:20])
                out.append({"type": "Point", "coordinates": [x, y]})
            elif base == 8:
                n = struct.unpack("<i", rec[36:40])[0]
                pts = [list(struct.unpack("<2d", rec[40 + 16 * i:56 + 16 * i])) for i in range(n)]
                out.append({"type": "MultiPoint", "coordinates": pts})
            else:                                   # 3 (linha) ou 5 (polígono)
                npart, npts = struct.unpack("<2i", rec[36:44])
                partes = list(struct.unpack(f"<{npart}i", rec[44:44 + 4 * npart]))
                p0 = 44 + 4 * npart
                pts = [list(struct.unpack("<2d", rec[p0 + 16 * i:p0 + 16 + 16 * i])) for i in range(npts)]
                aneis = [pts[partes[i]:(partes[i + 1] if i + 1 < npart else npts)] for i in range(npart)]
                if base == 3:
                    aneis = [a for a in aneis if len(a) >= 2]
                    out.append({"type": "LineString", "coordinates": aneis[0]} if len(aneis) == 1 else {"type": "MultiLineString", "coordinates": aneis})
                else:
                    polys = []
                    for a in aneis:
                        if len(a) < 4:
                            continue
                        if _anel_horario(a) or not polys:          # anel externo: horário no Shapefile
                            polys.append([a[::-1] if _anel_horario(a) else a])
                        else:                                       # furo: vai ao polígono que o contém
                            dono = next((p for p in reversed(polys) if dentro_poligono(a[0], p[0])), polys[-1])
                            dono.append(a)
                    out.append({"type": "Polygon", "coordinates": polys[0]} if len(polys) == 1 else {"type": "MultiPolygon", "coordinates": polys})
        except struct.error:
            raise ArquivoInvalido(".shp cortado ou corrompido")
    return out


def ler_dbf(dbf: bytes, codificacao: str = "latin-1") -> list[dict]:
    if len(dbf) < 32:
        raise ArquivoInvalido(".dbf ilegível")
    n, hdr, rlen = struct.unpack("<IHH", dbf[4:12])
    campos, pos = [], 32
    while pos + 32 <= hdr and dbf[pos] != 0x0D:
        nome = dbf[pos:pos + 11].split(b"\x00")[0].decode("latin-1").strip()
        campos.append((nome, chr(dbf[pos + 11]), dbf[pos + 16]))
        pos += 32
    out = []
    for r in range(n):
        ini = hdr + r * rlen
        rec = dbf[ini:ini + rlen]
        if len(rec) < rlen:
            raise ArquivoInvalido(".dbf cortado")
        if rec[:1] == b"*":
            out.append(None)                         # registro apagado
            continue
        d, p = {}, 1
        for nome, tipo, tam in campos:
            bruto = rec[p:p + tam]
            p += tam
            txt = bruto.decode(codificacao, errors="replace").strip()
            if tipo in "NF":
                try:
                    v = float(txt) if txt and txt.strip("*") else None
                    d[nome] = int(v) if v is not None and v.is_integer() and "." not in txt else v
                except ValueError:
                    d[nome] = None
            elif tipo == "L":
                d[nome] = True if txt[:1] in "TtYy" else False if txt[:1] in "FfNn" else None
            elif tipo == "D":
                d[nome] = f"{txt[0:4]}-{txt[4:6]}-{txt[6:8]}" if len(txt) == 8 else None
            else:
                d[nome] = txt[:500]
        out.append(d)
    return out


def ler_shapefile_zip(dados: bytes) -> dict:
    try:
        z = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile:
        raise ArquivoInvalido("o Shapefile deve vir num .zip com .shp, .dbf e .prj")
    infos = [i for i in z.infolist() if not i.is_dir()]
    if len(infos) > 50 or sum(i.file_size for i in infos) > MAX_ZIP_DESCOMPACTADO:
        raise ArquivoInvalido("zip grande demais ou com arquivos demais")
    porext: dict = {}
    for i in infos:
        ext = i.filename.rsplit(".", 1)[-1].lower() if "." in i.filename else ""
        porext.setdefault(ext, []).append(i)
    if len(porext.get("shp", [])) != 1:
        raise ArquivoInvalido("o zip precisa de exatamente um .shp (envie uma camada por vez)")
    for ext in ("dbf", "prj"):
        if not porext.get(ext):
            raise ArquivoInvalido(f"falta o .{ext} no zip (o .prj diz o sistema de coordenadas)")
    crs = crs_do_prj(z.read(porext["prj"][0]).decode("latin-1"))
    cod = "latin-1"
    if porext.get("cpg"):
        c = z.read(porext["cpg"][0]).decode("ascii", errors="ignore").strip().lower()
        cod = "utf-8" if "utf" in c and "8" in c else "latin-1"
    geoms = ler_shp(z.read(porext["shp"][0]))
    props = ler_dbf(z.read(porext["dbf"][0]), cod)
    if len(props) != len(geoms):
        raise ArquivoInvalido(".shp e .dbf com números de registros diferentes")
    feats = [{"type": "Feature", "properties": p, "geometry": g} for g, p in zip(geoms, props) if p is not None]
    fc = {"type": "FeatureCollection", "features": feats}
    _conferir_coordenadas(fc)
    return {"geojson": fc, "crs": crs, "nota_crs": NOTA_SIRGAS if crs == "EPSG:4674" else ""}


def ler_arquivo(nome: str, dados: bytes) -> dict:
    if len(dados) > MAX_UPLOAD_BYTES:
        raise ArquivoInvalido(f"arquivo grande demais (máximo {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
    ext = (nome or "").rsplit(".", 1)[-1].lower() if "." in (nome or "") else ""
    if ext in ("geojson", "json"):
        r, fmt = ler_geojson(dados), "geojson"
    elif ext in ("kml", "kmz"):
        r, fmt = ler_kml(dados), ext
    elif ext == "zip":
        r, fmt = ler_shapefile_zip(dados), "shapefile"
    else:
        raise ArquivoInvalido("formato não aceito: envie GeoJSON, KML/KMZ ou Shapefile (.zip com .shp, .dbf e .prj)")
    r["formato"] = fmt
    return r


def _bbox_fc(fc: dict):
    xs, ys = [], []
    for f in fc["features"]:
        if f.get("geometry"):
            for p in _pontos(f["geometry"]):
                xs.append(p[0])
                ys.append(p[1])
    return [min(xs), min(ys), max(xs), max(ys)] if xs else None


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Uploads:
    """Arquivos do cliente: original e GeoJSON padronizado em disco, índice no SQLite com os dois SHA-256."""
    ESQUEMA = ("CREATE TABLE IF NOT EXISTS mapeamento_upload (id TEXT PRIMARY KEY, instalacao TEXT NOT NULL, nome TEXT NOT NULL, "
               "formato TEXT NOT NULL, crs TEXT NOT NULL, nota_crs TEXT NOT NULL, feicoes INTEGER NOT NULL, bbox TEXT, "
               "sha256 TEXT NOT NULL, sha256_geojson TEXT NOT NULL, bytes INTEGER NOT NULL, quando REAL NOT NULL, quem TEXT NOT NULL)")

    def __init__(self, con: sqlite3.Connection, pasta: str | os.PathLike | None = None):
        self.con = con
        self.pasta = Path(pasta or os.environ.get("PHYSIS_MAPEAMENTO_PASTA") or "mapeamento-arquivos")
        con.execute(self.ESQUEMA)
        con.commit()

    def _caminhos(self, id_: str, formato: str):
        ext = {"shapefile": "zip"}.get(formato, formato)
        return self.pasta / f"{id_}.{ext}", self.pasta / f"{id_}.norm.geojson"

    def guardar(self, nome: str, dados: bytes, instalacao: str = "", quem: str = "") -> dict:
        nome = re.sub(r"[^\w.\- ]", "_", (nome or "arquivo").rsplit("/", 1)[-1].rsplit("\\", 1)[-1])[:120]
        r = ler_arquivo(nome, dados)
        h = sha256(dados)
        id_ = h[:24]
        ant = self.con.execute("SELECT id FROM mapeamento_upload WHERE id=?", (id_,)).fetchone()
        if ant:
            return {"ok": True, "repetido": True, **self.info(id_)}
        norm = json.dumps(r["geojson"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.pasta.mkdir(parents=True, exist_ok=True)
        orig, ng = self._caminhos(id_, r["formato"])
        orig.write_bytes(dados)
        ng.write_bytes(norm)
        self.con.execute("INSERT INTO mapeamento_upload VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (id_, instalacao or "", nome, r["formato"], r["crs"], r["nota_crs"], len(r["geojson"]["features"]),
                          json.dumps(_bbox_fc(r["geojson"])), h, sha256(norm), len(dados), time.time(), quem or ""))
        self.con.commit()
        return {"ok": True, "repetido": False, **self.info(id_)}

    def info(self, id_: str) -> dict:
        l = self.con.execute("SELECT id,instalacao,nome,formato,crs,nota_crs,feicoes,bbox,sha256,sha256_geojson,bytes,quando FROM mapeamento_upload WHERE id=?", (id_,)).fetchone()
        if not l:
            return {}
        return {"id": l[0], "instalacao": l[1], "nome": l[2], "formato": l[3], "crs": l[4], "nota_crs": l[5], "feicoes": l[6],
                "bbox": json.loads(l[7]) if l[7] else None, "sha256": l[8], "sha256_geojson": l[9], "bytes": l[10], "quando": l[11]}

    def listar(self, instalacao: str | None = None) -> list[dict]:
        q = "SELECT id FROM mapeamento_upload" + (" WHERE instalacao=?" if instalacao is not None else "") + " ORDER BY quando DESC"
        return [self.info(r[0]) for r in self.con.execute(q, (instalacao,) if instalacao is not None else ())]

    def conferir(self, id_: str) -> dict:
        """Recalcula os SHA-256 do original e do GeoJSON guardados e compara com o índice."""
        i = self.info(id_)
        if not i:
            return {"ok": False, "erro": "arquivo não encontrado"}
        orig, ng = self._caminhos(id_, i["formato"])
        try:
            a, b = sha256(orig.read_bytes()), sha256(ng.read_bytes())
        except OSError:
            return {"ok": False, "integro": False, "erro": "arquivo sumiu do disco"}
        return {"ok": True, "integro": a == i["sha256"] and b == i["sha256_geojson"]}

    def geojson(self, id_: str) -> dict | None:
        i = self.info(id_)
        if not i or not self.conferir(id_).get("integro"):
            return None
        return json.loads(self._caminhos(id_, i["formato"])[1].read_text(encoding="utf-8"))

    def apagar(self, id_: str) -> bool:
        i = self.info(id_)
        if not i:
            return False
        for c in self._caminhos(id_, i["formato"]):
            try:
                c.unlink()
            except OSError:
                pass
        self.con.execute("DELETE FROM mapeamento_upload WHERE id=?", (id_,))
        self.con.commit()
        return True


# ═══════════════ 3. Contexto do lugar ═══════════════
def poligono_do_lote(local: dict | None, lote: dict | None = None) -> list | None:
    """Anel [[lon, lat], …] do lote: do estado do Planejador (physis.terreno/1.0, metros locais) ou do local."""
    if isinstance(lote, dict) and lote.get("schema") == "physis.terreno/1.0":
        t = lote.get("terreno") or {}
        if t.get("lat0") is not None and t.get("lon0") is not None and len(t.get("poly") or []) >= 3:
            k = 111320 * math.cos(math.radians(t["lat0"]))
            return [[t["lon0"] + p[0] / k, t["lat0"] + p[1] / 110540] for p in t["poly"]]
    for fonte in (lote, local):
        p = (fonte or {}).get("poligono") if isinstance(fonte, dict) else None
        if isinstance(p, dict) and p.get("type") == "Polygon":
            p = (p.get("coordinates") or [None])[0]
        if isinstance(p, list) and len(p) >= 3 and all(isinstance(x, (list, tuple)) and len(x) >= 2 for x in p):
            return [[float(x[0]), float(x[1])] for x in p]
    return None


def janela_do_lote(poligono, lat, lon, folga_m: float = 300.0):
    if poligono:
        xs, ys = [p[0] for p in poligono], [p[1] for p in poligono]
        lat_c = (min(ys) + max(ys)) / 2
    elif lat is not None and lon is not None:
        xs, ys, lat_c = [lon], [lat], lat
    else:
        return None
    dlon, dlat = folga_m / (111320 * math.cos(math.radians(lat_c))), folga_m / 110540
    return [min(xs) - dlon, min(ys) - dlat, max(xs) + dlon, max(ys) + dlat]


def _campo(valor, unidade, fonte, camada=None, situacao="ok", nota=""):
    d = {"valor": valor, "unidade": unidade, "fonte": fonte, "camada": camada, "situacao": situacao}
    if nota:
        d["nota"] = nota
    return d


def _fonte_txt(c: dict) -> str:
    f = c["fonte"]
    return f"{f['produto']} — {f['nome']}; licença: {f['licenca']}"


def construir_contexto(local: dict | None, lote: dict | None = None, pasta=None, uploads: list | None = None,
                       irradiacao_solar: dict | None = None, instalacao: str = "", agora: float | None = None) -> dict:
    """Contexto do lugar, com a fonte de cada campo. local = Hub.local_da_instalacao() (Início > Planejador > …);
    lote = estado do Planejador (opcional); irradiacao_solar = a mesma base da aba Solar ({'meses': [12], 'fonte': …})."""
    local = local or {}
    lat, lon = local.get("lat"), local.get("lon")
    poly = poligono_do_lote(local, lote)
    if poly and (lat is None or lon is None):
        lon, lat = sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)
    fonte_local = str(local.get("fonte") or "nao_informado")
    campos: dict = {}
    faltam: list = []
    doc = {"esquema": ESQUEMA_CONTEXTO, "instalacao": instalacao, "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(agora or time.time())),
           "depende_de": ["inicio", "planejador"], "campos": campos, "faltam": faltam, "uploads": [], "avisos": []}
    campos["coordenadas"] = _campo({"lat": lat, "lon": lon} if lat is not None else None, "grau (WGS 84)", f"local da instalação ({fonte_local})",
                                   situacao="ok" if lat is not None else "sem_dado")
    campos["municipio"] = _campo({"municipio": local.get("municipio"), "uf": local.get("uf")} if local.get("municipio") else None, "texto",
                                 "Início (dados obrigatórios do cliente)", situacao="ok" if local.get("municipio") else "sem_dado")
    if poly:
        campos["area_lote_m2"] = _campo(round(area_m2(poly), 1), "m²", "polígono do lote do Planejador")
    elif local.get("area_m2"):
        campos["area_lote_m2"] = _campo(local["area_m2"], "m²", f"área declarada ({fonte_local})")
    else:
        campos["area_lote_m2"] = _campo(None, "m²", "Planejador (lote) ou Início (área)", situacao="sem_dado")
    if lat is None:
        doc["avisos"].append("Sem localização: preencha os dados obrigatórios no Início (ou o lote no Planejador). Nada foi buscado.")
        doc["integridade"] = {"sha256": _resumo(doc)}
        return doc
    b = janela_do_lote(poly, lat, lon)
    centro = (lon, lat)
    p = pasta_camadas(pasta)

    def falta(campo_id, cid, motivo="camada não instalada"):
        c = POR_ID[cid]
        faltam.append({"campo": campo_id, "camada": cid, "nome": c["nome"], "motivo": motivo, "como_instalar": c["chave_config"]})
        campos[campo_id] = _campo(None, "", _fonte_txt(c), cid, "camada_nao_instalada" if motivo == "camada não instalada" else "erro", motivo if motivo != "camada não instalada" else "")

    def pega(cid):
        r = camada(cid, b, p, poly)
        return r if r.get("ok") else None, r

    # relevo e declividade
    r, bruto = pega("relevo")
    if r:
        campos["declividade"] = _campo(r["declividade"], "%", _fonte_txt(POR_ID["relevo"]), "relevo",
                                       nota="APP de encosta acima de 45° (100 %) pela premissa app.declividade; conferir na lei [CONFERIR NA LEI]")
        campos["altitude_m"] = _campo(r["resumo"], "m", _fonte_txt(POR_ID["relevo"]), "relevo")
    else:
        falta("declividade", "relevo", bruto.get("erro") if not bruto.get("sem_camada") else "camada não instalada")
    # hidrografia
    r, bruto = pega("hidrografia")
    if r:
        fs = r["geojson"]["features"]
        rios = [f for f in fs if f["geometry"]["type"] in ("LineString", "MultiLineString")]
        nasc = [f for f in fs if f["geometry"]["type"] in ("Point", "MultiPoint")]
        dist = lambda l: min((d for d in (distancia_geometria_m(centro, f["geometry"]) for f in l) if d is not None), default=None)
        campos["hidrografia"] = _campo({"rios": len(rios), "nascentes": len(nasc), "rio_mais_proximo_m": dist(rios), "nascente_mais_proxima_m": dist(nasc),
                                        "nomes": sorted({str(f["properties"].get("nome") or f["properties"].get("name") or "") for f in rios} - {""})[:20]},
                                       "contagem; m", _fonte_txt(POR_ID["hidrografia"]), "hidrografia",
                                       nota="A faixa de APP é desenhada no Planejador (premissas app.faixa_rio e app.raio_nascente) [CONFERIR NA LEI].")
    else:
        falta("hidrografia", "hidrografia", "camada não instalada" if bruto.get("sem_camada") else bruto.get("erro", ""))
    # uso do solo
    r, bruto = pega("uso_solo")
    if r:
        campos["uso_solo"] = _campo(r["classes"], "fração da área", (r["provisoria"].split(" · ")[0] + " (provisória)") if r.get("provisoria") else _fonte_txt(POR_ID["uso_solo"]), "uso_solo",
                                    nota=("PROVISÓRIA: " + r["provisoria"]) if r.get("provisoria") else
                                    ("" if any(c["nome"] for c in r["classes"]) else "sem legenda instalada: só o código da classe"))
    else:
        falta("uso_solo", "uso_solo", "camada não instalada" if bruto.get("sem_camada") else bruto.get("erro", ""))
    # vetores com "o que contém o centro" ou "o que toca o lote"
    for cid, campo_id in (("solos", "solos"), ("limites", "limites")):
        r, bruto = pega(cid)
        if r:
            dono = next((f for f in r["geojson"]["features"] if dentro_geometria(centro, f["geometry"])), None)
            campos[campo_id] = _campo(dono["properties"] if dono else None, "atributos da base", _fonte_txt(POR_ID[cid]), cid,
                                      "ok" if dono else "sem_dado")
        else:
            falta(campo_id, cid, "camada não instalada" if bruto.get("sem_camada") else bruto.get("erro", ""))
    r, bruto = pega("car")
    if r:
        cods = [str(f["properties"].get("cod_imovel") or f["properties"].get("COD_IMOVEL") or "") for f in r["geojson"]["features"]]
        campos["car"] = _campo({"imoveis": len(cods), "codigos": sorted(set(c for c in cods if c))[:50]}, "contagem", _fonte_txt(POR_ID["car"]), "car")
    else:
        falta("car", "car", "camada não instalada" if bruto.get("sem_camada") else bruto.get("erro", ""))
    r, bruto = pega("risco")
    if r:
        fs = r["geojson"]["features"]
        no_lote = [f for f in fs if (poly and any(dentro_geometria(q, f["geometry"]) for q in poly + [list(centro)])) or dentro_geometria(centro, f["geometry"])]
        campos["risco"] = _campo({"setores_na_janela": len(fs), "setores_no_lote": len(no_lote),
                                  "atributos": [f["properties"] for f in no_lote][:20]}, "contagem", _fonte_txt(POR_ID["risco"]), "risco",
                                 nota="Bandeira, não laudo: risco no lote pede vistoria (Resiliência).")
    else:
        falta("risco", "risco", "camada não instalada" if bruto.get("sem_camada") else bruto.get("erro", ""))
    r, bruto = pega("rede_eletrica")
    if r:
        ds = [d for d in (distancia_geometria_m(centro, f["geometry"]) for f in r["geojson"]["features"]) if d is not None]
        campos["rede_eletrica"] = _campo({"feicoes": len(ds), "mais_proxima_m": min(ds) if ds else None}, "m", _fonte_txt(POR_ID["rede_eletrica"]), "rede_eletrica")
    else:
        falta("rede_eletrica", "rede_eletrica", "camada não instalada" if bruto.get("sem_camada") else bruto.get("erro", ""))
    r, bruto = pega("osm")
    if r:
        fs = r["geojson"]["features"]
        ed = [f for f in fs if f["properties"].get("building") not in (None, "", "no")]
        vias = [f for f in fs if f["properties"].get("highway")]
        campos["osm"] = _campo({"edificacoes": len(ed), "vias": len(vias)}, "contagem", _fonte_txt(POR_ID["osm"]), "osm")
    else:
        falta("osm", "osm", "camada não instalada" if bruto.get("sem_camada") else bruto.get("erro", ""))
    # clima (EPW)
    r, bruto = pega("clima")
    if r:
        cl = r["clima"]
        campos["clima"] = _campo({k: cl.get(k) for k in ("cidade", "uf", "wmo", "distancia_km", "temp_media_c", "vento_medio_m_s", "arquivo")},
                                 "°C; m/s; km", _fonte_txt(POR_ID["clima"]) + f"; arquivo {cl.get('arquivo')}", "clima")
    else:
        falta("clima", "clima", "camada não instalada" if bruto.get("sem_camada") else bruto.get("erro", ""))
    # irradiação: atlas instalado; senão a mesma base da aba Solar; senão falta
    r, bruto = pega("irradiacao")
    if r and r["resumo"].get("n"):
        campos["irradiacao"] = _campo({"anual_kwh_m2_dia": r["resumo"]["media"], "mensal_kwh_m2_dia": r.get("mensal")}, "kWh/m²·dia",
                                      _fonte_txt(POR_ID["irradiacao"]), "irradiacao")
    elif irradiacao_solar and isinstance(irradiacao_solar.get("meses"), list) and len(irradiacao_solar["meses"]) == 12:
        m = irradiacao_solar["meses"]
        campos["irradiacao"] = _campo({"anual_kwh_m2_dia": sum(m) / 12, "mensal_kwh_m2_dia": m}, "kWh/m²·dia",
                                      str(irradiacao_solar.get("fonte") or "NASA POWER, média de longo prazo (mesma base da aba Solar)"), None,
                                      nota="atlas LABREN não instalado: usada a base da aba Solar")
    else:
        falta("irradiacao", "irradiacao", "camada não instalada" if (bruto.get("sem_camada") or r) else bruto.get("erro", ""))
    r, bruto = pega("vento")
    if r and r["resumo"].get("n"):
        campos["vento"] = _campo({"media_m_s": r["resumo"]["media"]}, "m/s", _fonte_txt(POR_ID["vento"]), "vento")
    else:
        falta("vento", "vento", "camada não instalada" if (bruto.get("sem_camada") or r) else bruto.get("erro", ""))
    # camadas EXTRAS instaladas (27/11/2026): o que cada uma diz deste lugar, com a fonte; valor bruto da base (sem conversão inventada)
    ex_out = []
    for c in extras(p):
        if not (p / c["arquivo"]).is_file():
            continue
        r = camada(c["id"], b, p, poly)
        item = {"id": c["id"], "nome": c["nome"]["pt"], "grupo": c.get("grupo"), "fonte": _fonte_txt(c), "formato": c["formato"]}
        if not r.get("ok"):
            item.update(situacao="sem_dado", motivo=r.get("erro", ""))
        elif r["tipo"] == "vetor":
            fs = r["geojson"]["features"]
            no_lugar = [f for f in fs if dentro_geometria(centro, f["geometry"]) or (poly and any(dentro_geometria(q, f["geometry"]) for q in poly))]
            ds = [d for d in (distancia_geometria_m(centro, f["geometry"]) for f in fs) if d is not None]
            item.update(situacao="ok", valor={"feicoes_na_janela": len(fs), "no_lote": len(no_lugar), "mais_proxima_m": round(min(ds), 1) if ds else None,
                                              "atributos_no_lote": [f["properties"] for f in no_lugar][:5]}, unidade="contagem; m")
        else:
            rs = r.get("resumo") or {}
            bd = r.get("banda") or {}
            item.update(situacao="ok" if rs.get("n") else "sem_dado", valor=rs, unidade=bd.get("unit") or "valor da base",
                        nota=("escala da base: x" + str(bd.get("scale")) + (" + " + str(bd.get("offset")) if bd.get("offset") else "")) if bd.get("scale") not in (None, 1, 1.0)
                        else "valor bruto da base: conferir a unidade na documentação da fonte [CONFERIR]")
        ex_out.append(item)
    if ex_out:
        doc["extras"] = ex_out
    doc["janela"] = b
    doc["poligono_lote"] = poly
    doc["uploads"] = [{k: u.get(k) for k in ("id", "nome", "formato", "crs", "feicoes", "sha256")} for u in (uploads or [])]
    doc["integridade"] = {"sha256": _resumo(doc)}
    return doc


def _resumo(doc: dict) -> str:
    d = {k: v for k, v in doc.items() if k not in ("integridade", "gerado_em")}
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


# ═══════════════ 4. Sol nas superfícies (espelho de sistema/physis-mapeamento.js) ═══════════════
DIAS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
DIA_REP = [17, 47, 75, 105, 135, 162, 198, 228, 258, 288, 318, 344]     # os mesmos de physis-calc-comum.js
PASSOS_DIA = 240              # passos do dia médio do mês (os mesmos de PhysisCalc.fatorPlano)
SETORES = 36                  # horizonte em setores de 10°
RAD = math.pi / 180


def h0_mensal(lat: float) -> list[float]:
    out = []
    f = lat * RAD
    for n in DIA_REP:
        d = 23.45 * math.sin(RAD * 360 * (284 + n) / 365) * RAD
        ws = math.acos(max(-1.0, min(1.0, -math.tan(f) * math.tan(d))))
        E = 1 + 0.033 * math.cos(2 * math.pi * n / 365)
        out.append(24 / math.pi * 1.367 * E * (math.cos(f) * math.cos(d) * math.sin(ws) + ws * math.sin(f) * math.sin(d)))
    return out


def normal(incl: float, azim: float):
    b, A = incl * RAD, azim * RAD
    return (math.sin(b) * math.sin(A), math.sin(b) * math.cos(A), math.cos(b))


def setor(az_rad: float) -> int:
    return int(round((az_rad / RAD % 360) / (360 / SETORES))) % SETORES


def incidencia_superficie(H: list, lat: float, incl: float, azim: float, horizonte: list | None = None, albedo: float = 0.2) -> dict:
    """Irradiação no plano (kWh/m²·dia por mês e kWh/m²·ano) com sombra do horizonte.
    Sem horizonte, é igual a PhysisCalc.fatorPlano × H. Azimute: 0 = norte, 90 = leste (para onde a face aponta).
    horizonte: SETORES ângulos de elevação (rad), setor k centrado em k·10° a partir do norte, no sentido horário."""
    hz = horizonte or [0.0] * SETORES
    svf = sum(math.cos(max(0.0, h)) ** 2 for h in hz) / len(hz)           # fração do céu vista (horizonte isotrópico)
    n = normal(incl, azim)
    b = incl * RAD
    f = lat * RAD
    H0 = h0_mensal(lat)
    mensal, sem, fator = [], [], []
    for m, dn in enumerate(DIA_REP):
        h = float(H[m] or 0)
        if not h > 0:
            mensal.append(0.0); sem.append(0.0); fator.append(1.0)
            continue
        d = 23.45 * math.sin(RAD * 360 * (284 + dn) / 365) * RAD
        ws = math.acos(max(-1.0, min(1.0, -math.tan(f) * math.tan(d))))
        sP = sPs = sH = 0.0
        for k in range(PASSOS_DIA):
            w = -ws + (k + 0.5) * 2 * ws / PASSOS_DIA
            s = (-math.cos(d) * math.sin(w), math.sin(d) * math.cos(f) - math.cos(d) * math.sin(f) * math.cos(w),
                 math.sin(f) * math.sin(d) + math.cos(f) * math.cos(d) * math.cos(w))
            if s[2] <= 0:
                continue
            sH += s[2]
            c = max(0.0, n[0] * s[0] + n[1] * s[1] + n[2] * s[2])
            sP += c
            if c > 0 and math.asin(min(1.0, s[2])) > hz[setor(math.atan2(s[0], s[1]))]:
                sPs += c
        Rb, Rbs = (sP / sH, sPs / sH) if sH > 0 else (1.0, 1.0)
        kt = max(0.3, min(0.8, h / H0[m]))
        fd = (1.391 - 3.560 * kt + 4.189 * kt ** 2 - 2.137 * kt ** 3) if ws <= 81.4 * RAD else (1.311 - 3.022 * kt + 3.427 * kt ** 2 - 1.821 * kt ** 3)
        f_sem = (1 - fd) * Rb + fd * (1 + math.cos(b)) / 2 + albedo * (1 - math.cos(b)) / 2
        f_com = (1 - fd) * Rbs + fd * (1 + math.cos(b)) / 2 * svf + albedo * (1 - math.cos(b)) / 2
        if b == 0 and not horizonte:
            f_sem = f_com = 1.0
        mensal.append(h * f_com)
        sem.append(h * f_sem)
        fator.append(f_com)
    anual = sum(mensal[m] * DIAS[m] for m in range(12))
    anual_sem = sum(sem[m] * DIAS[m] for m in range(12))
    anual_h = sum(float(H[m] or 0) * DIAS[m] for m in range(12))
    return {"mensal_kwh_m2_dia": mensal, "anual_kwh_m2": anual, "anual_sem_sombra_kwh_m2": anual_sem,
            "fator_anual": anual / anual_h if anual_h > 0 else None, "sombra_pct": 100 * (1 - anual / anual_sem) if anual_sem > 0 else 0.0,
            "ceu_visivel": svf}


def z_grade(g: dict, x: float, y: float) -> float:
    fi = min(max((x - g["x0"]) / g["cs"], 0.0), g["nx"] - 1.001)
    fj = min(max((y - g["y0"]) / g["cs"], 0.0), g["ny"] - 1.001)
    i, j = int(fi), int(fj)
    u, v = fi - i, fj - j
    Z, n = g["Z"], g["nx"]
    return Z[j * n + i] * (1 - u) * (1 - v) + Z[j * n + i + 1] * u * (1 - v) + Z[(j + 1) * n + i] * (1 - u) * v + Z[(j + 1) * n + i + 1] * u * v


def _raio_caixa(px, py, dx, dy, c: dict):
    """Distância (no plano) em que o raio entra na caixa girada c (x, y, w, d, rot em graus); None se não cruza."""
    r = -(c.get("rot") or 0) * RAD
    ox, oy = px - c["x"], py - c["y"]
    lx, ly = ox * math.cos(r) - oy * math.sin(r), ox * math.sin(r) + oy * math.cos(r)
    vx, vy = dx * math.cos(r) - dy * math.sin(r), dx * math.sin(r) + dy * math.cos(r)
    t0, t1 = -math.inf, math.inf
    for o, v, meia in ((lx, vx, c["w"] / 2), (ly, vy, c["d"] / 2)):
        if abs(v) < 1e-12:
            if abs(o) > meia:
                return None
            continue
        a, b = (-meia - o) / v, (meia - o) / v
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
    if t1 < max(t0, 0):
        return None
    return max(t0, 0.0)


def horizonte(x: float, y: float, z: float, grade: dict | None = None, caixas: list | None = None, ignorar=None, alcance: float | None = None) -> list[float]:
    """Elevação do horizonte (rad) em SETORES direções, por marcha de raio no terreno e nas caixas dos prédios."""
    out = [0.0] * SETORES
    if grade:
        alcance = alcance or math.hypot(grade["nx"], grade["ny"]) * grade["cs"]
        passo = grade["cs"] * 0.5
    for k in range(SETORES):
        az = k * 360 / SETORES * RAD
        dx, dy = math.sin(az), math.cos(az)
        melhor = 0.0
        if grade:
            t = grade["cs"]
            while t <= alcance:
                qx, qy = x + dx * t, y + dy * t
                if not (grade["x0"] <= qx <= grade["x0"] + (grade["nx"] - 1) * grade["cs"] and grade["y0"] <= qy <= grade["y0"] + (grade["ny"] - 1) * grade["cs"]):
                    break
                melhor = max(melhor, math.atan2(z_grade(grade, qx, qy) - z, t))
                t += passo
        for c in caixas or []:
            if ignorar is not None and c.get("id") == ignorar:
                continue
            t = _raio_caixa(x, y, dx, dy, c)
            if t is None:
                continue
            if t < 0.01:
                continue                                  # ponto dentro da caixa: é a própria superfície
            topo = (c.get("z0") or 0.0) + c["h"]
            melhor = max(melhor, math.atan2(topo - z, t))
        out[k] = melhor
    return out


def planos_telhado(caixa: dict) -> list[dict]:
    """Águas do telhado de uma caixa (x, y, w, d, rot, h, z0, incl, azim, aguas = 1, 2 ou 4)."""
    incl = caixa.get("incl")
    if incl is None or incl == "":
        return []
    incl, az0, n = float(incl), float(caixa.get("azim") or 0), int(caixa.get("aguas") or 1)
    n = n if n in (1, 2, 4) else 1
    proj = caixa["w"] * caixa["d"] / n
    return [{"id": f"{caixa.get('id', 'ed')}-agua{k + 1}", "nome": f"{caixa.get('nome', 'Edificação')} · água {k + 1}", "tipo": "telhado",
             "x": caixa["x"], "y": caixa["y"], "z": (caixa.get("z0") or 0.0) + caixa["h"] + 0.05, "incl": incl,
             "azim": (az0 + k * 360 / n) % 360, "area_m2": proj / max(0.05, math.cos(incl * RAD)), "caixa": caixa.get("id")} for k in range(n)]


def fachadas(caixa: dict) -> list[dict]:
    r = (caixa.get("rot") or 0) * RAD
    out = []
    for k, (lx, ly, larg) in enumerate(((0, -caixa["d"] / 2, caixa["w"]), (caixa["w"] / 2, 0, caixa["d"]), (0, caixa["d"] / 2, caixa["w"]), (-caixa["w"] / 2, 0, caixa["d"]))):
        nx_, ny_ = (lx, ly)
        ex, ey = nx_ * math.cos(r) - ny_ * math.sin(r), nx_ * math.sin(r) + ny_ * math.cos(r)
        nrm = math.hypot(ex, ey) or 1
        out.append({"id": f"{caixa.get('id', 'ed')}-fachada{k + 1}", "nome": f"{caixa.get('nome', 'Edificação')} · fachada {k + 1}", "tipo": "fachada",
                    "x": caixa["x"] + ex + 0.05 * ex / nrm, "y": caixa["y"] + ey + 0.05 * ey / nrm, "z": (caixa.get("z0") or 0.0) + caixa["h"] / 2,
                    "incl": 90.0, "azim": math.degrees(math.atan2(ex, ey)) % 360, "area_m2": larg * caixa["h"], "caixa": caixa.get("id")})
    return out


def celulas_terreno(grade: dict, max_celulas: int = 400, dentro=None) -> list[dict]:
    """Células do terreno como superfícies (declividade e orientação por diferenças centrais, como o Planejador)."""
    nx, ny, cs, Z = grade["nx"], grade["ny"], grade["cs"], grade["Z"]
    passo = max(1, math.ceil(math.sqrt(max(1, (nx - 2) * (ny - 2)) / max_celulas)))
    out = []
    for j in range(1, ny - 1, passo):
        for i in range(1, nx - 1, passo):
            x, y = grade["x0"] + i * cs, grade["y0"] + j * cs
            if dentro and not dentro((x, y)):
                continue
            dx = (Z[j * nx + i + 1] - Z[j * nx + i - 1]) / (2 * cs)
            dy = (Z[(j + 1) * nx + i] - Z[(j - 1) * nx + i]) / (2 * cs)
            out.append({"id": f"t{i}-{j}", "tipo": "terreno", "i": i, "j": j, "x": x, "y": y, "z": Z[j * nx + i] + 0.05,
                        "incl": math.degrees(math.atan(math.hypot(dx, dy))), "azim": math.degrees(math.atan2(-dx, -dy)) % 360, "area_m2": (cs * passo) ** 2})
    return out


def incidencia(H: list, lat: float, superficies: list, grade: dict | None = None, caixas: list | None = None, albedo: float = 0.2,
               fonte_irradiacao: str = "") -> dict:
    """Irradiação de cada superfície (telhado, fachada, terreno), com sombra do terreno e dos prédios."""
    if not (isinstance(H, list) and len(H) == 12 and all(isinstance(v, (int, float)) and v >= 0 for v in H)):
        raise ValueError("irradiação do lugar: 12 valores mensais (kWh/m²·dia)")
    if not -90 <= lat <= 90:
        raise ValueError("latitude inválida")
    out = []
    for s in superficies:
        hz = horizonte(s["x"], s["y"], s["z"], grade, caixas, ignorar=s.get("caixa")) if (grade or caixas) else None
        r = incidencia_superficie(H, lat, float(s.get("incl") or 0), float(s.get("azim") or 0), hz, albedo)
        out.append({**{k: s.get(k) for k in ("id", "nome", "tipo", "incl", "azim", "area_m2", "i", "j")}, **r})
    return {"esquema": ESQUEMA_INCIDENCIA, "lat": lat, "irradiacao_horizontal": H, "fonte_irradiacao": fonte_irradiacao,
            "albedo": albedo, "superficies": out, "metodo": "Liu e Jordan isotrópico com fração difusa de Erbs (= PhysisCalc.fatorPlano) "
            "e horizonte por marcha de raio em 36 setores (terreno e caixas)"}


# ═══════════════ 5. Planta solar (BIM): curva desde o nascer do sol, carta solar e arranjo das placas ═══════════════
# Espelho de sistema/physis-mapeamento.js. A energia do mês e do ano é a da aba Solar (window.SOLAR.calcular com o
# fator do plano daqui, já com a sombra); a temperatura da célula e as perdas são as da aba Solar (tCelula, fTemp,
# PERDAS_PADRAO, copiadas aqui só para o teste, que confere que são as mesmas do physis-solar.js).
PERDAS_SOLAR = {"sombra": 0, "sujeira": 2, "mismatch": 1.5, "cabos_cc": 1.5, "cabos_ca": 1}     # = PERDAS_PADRAO de physis-solar.js
DIA_21 = [21, 52, 80, 111, 141, 172, 202, 233, 264, 294, 325, 355]          # dia 21 de cada mês (carta solar)
SOLSTICIO_JUN, SOLSTICIO_DEZ, EQUINOCIO_MAR, EQUINOCIO_SET = 172, 355, 80, 266


def declinacao(dn: int) -> float:
    return 23.45 * math.sin(RAD * 360 * (284 + dn) / 365) * RAD


def sol_em(lat: float, dn: int, hora_solar: float) -> dict:
    """Posição do sol (mesmo vetor de PhysisCalc.fatorPlano): altura e azimute (0 = norte, 90 = leste), em graus."""
    f, d, w = lat * RAD, declinacao(dn), (hora_solar - 12) * 15 * RAD
    s = (-math.cos(d) * math.sin(w), math.sin(d) * math.cos(f) - math.cos(d) * math.sin(f) * math.cos(w),
         math.sin(f) * math.sin(d) + math.cos(f) * math.cos(d) * math.cos(w))
    return {"altura": math.degrees(math.asin(max(-1.0, min(1.0, s[2])))), "azimute": math.degrees(math.atan2(s[0], s[1])) % 360, "vetor": s}


def nascer_por(lat: float, dn: int) -> tuple[float, float]:
    ws = math.acos(max(-1.0, min(1.0, -math.tan(lat * RAD) * math.tan(declinacao(dn)))))
    return 12 - math.degrees(ws) / 15, 12 + math.degrees(ws) / 15


def carta_solar(lat: float, horizonte_rad: list | None = None) -> dict:
    """Caminho do sol no dia 21 de cada mês, hora a hora (hora solar), nascer e pôr do sol e o perfil do horizonte."""
    dias = []
    for m, dn in enumerate(DIA_21):
        n0, n1 = nascer_por(lat, dn)
        pts = [{"hora": h, **{k: v for k, v in sol_em(lat, dn, h).items() if k != "vetor"}} for h in range(math.ceil(n0), math.floor(n1) + 1)]
        dias.append({"mes": m + 1, "dia_do_ano": dn, "nascer_h": n0, "por_h": n1, "pontos": [p for p in pts if p["altura"] > 0]})
    return {"lat": lat, "dias": dias, "horizonte_graus": [math.degrees(h) for h in (horizonte_rad or [0.0] * SETORES)], "hora": "solar (meio-dia = sol mais alto)"}


def curva_diaria(H_dia: float, lat: float, dn: int, incl: float, azim: float, horizonte_rad: list | None = None, albedo: float = 0.2,
                 passo_h: float = 0.25, total_plano: float | None = None) -> dict:
    """Irradiância no plano ao longo do dia, do nascer ao pôr do sol (W/m²), a partir da irradiação do dia (kWh/m²·dia):
    distribuição horária de Collares-Pereira e Rabl (global) e de Liu e Jordan (difusa) — Duffie & Beckman, cap. 2.13;
    fração difusa de Erbs como em fatorPlano. total_plano (kWh/m²·dia, da incidência mensal) reescala a curva para fechar
    exatamente com o mesmo total da aba Solar."""
    hz = horizonte_rad or [0.0] * SETORES
    svf = sum(math.cos(max(0.0, h)) ** 2 for h in hz) / len(hz)
    f, d = lat * RAD, declinacao(dn)
    ws = math.acos(max(-1.0, min(1.0, -math.tan(f) * math.tan(d))))
    n = normal(incl, azim)
    b = incl * RAD
    E = 1 + 0.033 * math.cos(2 * math.pi * dn / 365)
    h0 = 24 / math.pi * 1.367 * E * (math.cos(f) * math.cos(d) * math.sin(ws) + ws * math.sin(f) * math.sin(d))
    kt = max(0.3, min(0.8, H_dia / h0)) if h0 > 0 else 0.5
    fd = (1.391 - 3.560 * kt + 4.189 * kt ** 2 - 2.137 * kt ** 3) if ws <= 81.4 * RAD else (1.311 - 3.022 * kt + 3.427 * kt ** 2 - 1.821 * kt ** 3)
    Hd = fd * H_dia
    a_ = 0.409 + 0.5016 * math.sin(ws - 60 * RAD)
    b_ = 0.6609 - 0.4767 * math.sin(ws - 60 * RAD)
    den = math.sin(ws) - ws * math.cos(ws)
    n0, n1 = 12 - math.degrees(ws) / 15, 12 + math.degrees(ws) / 15
    pts = []
    npassos = max(1, math.ceil((n1 - n0) / passo_h))
    passo_h = (n1 - n0) / npassos                      # passos iguais do nascer ao pôr: curva simétrica ao meio-dia solar
    for k in range(npassos):
        h = n0 + (k + 0.5) * passo_h
        w = (h - 12) * 15 * RAD
        rd = (math.pi / 24) * (math.cos(w) - math.cos(ws)) / den
        rt = rd * (a_ + b_ * math.cos(w))
        I, Id = H_dia * rt, Hd * rd
        Ib = max(0.0, I - Id)
        s = (-math.cos(d) * math.sin(w), math.sin(d) * math.cos(f) - math.cos(d) * math.sin(f) * math.cos(w),
             math.sin(f) * math.sin(d) + math.cos(f) * math.cos(d) * math.cos(w))
        cz = max(s[2], 0.0)
        ct = max(0.0, n[0] * s[0] + n[1] * s[1] + n[2] * s[2])
        visivel = cz > 0 and math.asin(min(1.0, cz)) > hz[setor(math.atan2(s[0], s[1]))]
        rb = ct / cz if cz > 0.02 else 0.0
        g = (Ib * rb if visivel else 0.0) + Id * (1 + math.cos(b)) / 2 * svf + I * albedo * (1 - math.cos(b)) / 2
        pts.append([h, max(0.0, g) * 1000])          # kWh/m² por hora → W/m² médio na hora
    soma = sum(p[1] for p in pts) * passo_h / 1000
    if total_plano is not None and soma > 0:
        esc = total_plano / soma
        pts = [[p[0], p[1] * esc] for p in pts]
        soma = total_plano
    return {"dia_do_ano": dn, "nascer_h": n0, "por_h": n1, "passo_h": passo_h, "pontos": pts, "total_kwh_m2": soma}


def fator_perdas(perdas: dict | None = None, eta_inv: float = 0.973) -> float:
    L = {**PERDAS_SOLAR, **(perdas or {})}
    return ((1 - L["sombra"] / 100) * (1 - L["sujeira"] / 100) * (1 - L["mismatch"] / 100) * (1 - L["cabos_cc"] / 100)
            * eta_inv * (1 - L["cabos_ca"] / 100))


def potencia_ca(curva: dict, kwp: float, t_amb: float, noct: float, gamma_pct: float, perdas: dict | None = None, eta_inv: float = 0.973) -> list:
    """Potência CA estimada (kW) em cada ponto da curva: kWp × G/1000 × fator de temperatura (NOCT) × perdas da aba Solar."""
    fx = fator_perdas(perdas, eta_inv)
    out = []
    for h, g in curva["pontos"]:
        tc = t_amb + (noct - 20) / 800 * g
        out.append([h, kwp * g / 1000 * (1 + gamma_pct / 100 * (tc - 25)) * fx])
    return out


def sombra_entre_fileiras(lat: float, incl: float, azim: float, profundidade_m: float, altura_m: float, passo_m: float,
                          dia: int, horas: tuple) -> dict:
    """Uma fileira sombreia a de trás? Sombra ao longo da direção das fileiras = h·cos(Δaz)/tan(altura do sol)."""
    vao = passo_m - profundidade_m
    pior = 0.0
    det = []
    for h in horas:
        s = sol_em(lat, dia, h)
        if s["altura"] <= 0:
            det.append({"hora": h, "altura": s["altura"], "sombra_m": None, "nota": "sol abaixo do horizonte"})
            continue
        L = altura_m * math.cos((s["azimute"] - azim) * RAD) / math.tan(s["altura"] * RAD)
        pior = max(pior, L)
        det.append({"hora": h, "altura": s["altura"], "azimute": s["azimute"], "sombra_m": L})
    passo_min = profundidade_m + pior
    return {"sombreia": pior > vao + 1e-9, "vao_m": vao, "sombra_max_m": pior, "passo_minimo_m": passo_min, "dia": dia, "horas": list(horas), "detalhe": det}


def _dist_seg_xy(p, a, c) -> float:
    dx, dy = c[0] - a[0], c[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy or 1)))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _cabe(cantos, poligono, afastamento) -> bool:
    for q in cantos:
        if not dentro_poligono(q, poligono):
            return False
        if afastamento > 0 and min(_dist_seg_xy(q, poligono[i], poligono[(i + 1) % len(poligono)]) for i in range(len(poligono))) < afastamento - 1e-9:
            return False
    return True


def arranjo(poligono: list, modulo: dict, *, orientacao: str = "retrato", empilhados: int = 1, incl: float = 0.0, azim: float = 0.0,
            afastamento_m: float, folga_m: float, passo_m: float | None = None, plano: str = "solo", lat: float | None = None,
            dia_critico: int | None = None, horas_criticas: tuple | None = None, obstaculos: list | None = None) -> dict:
    """Placas numa superfície. poligono: [[x, y], …] em metros (solo: x leste, y norte; telhado: coordenadas no plano da
    água, y subindo a água e azim = orientação da água). modulo: comprimento_m, largura_m, pmax (W).
    Solo ou laje: mesas com 'empilhados' módulos inclinados 'incl' para 'azim', em fileiras com passo 'passo_m' (vazio =
    passo mínimo sem sombra no dia e nas horas críticas). Telhado inclinado: rente à água, fileiras encostadas."""
    L, W = float(modulo["comprimento_m"]), float(modulo["largura_m"])
    if not (L > 0 and W > 0 and modulo.get("pmax", 0) > 0):
        raise ValueError("módulo sem dimensões ou potência")
    dv, du = (L, W) if orientacao == "retrato" else (W, L)          # dimensão no sentido da inclinação e ao longo da fileira
    n = max(1, int(empilhados))
    if plano == "telhado":
        A = 0.0                                                      # no plano da água: y sobe a água
        prof, alt, sombra = n * dv, 0.0, None
        passo = prof + folga_m
    else:
        A = azim * RAD
        prof, alt = n * dv * math.cos(incl * RAD), n * dv * math.sin(incl * RAD)
        dc = dia_critico if dia_critico is not None else (SOLSTICIO_JUN if (lat or 0) < 0 else SOLSTICIO_DEZ)
        if lat is not None and incl > 0 and not horas_criticas:
            raise ValueError("horas críticas da sombra entre fileiras: premissas solar.arranjo_hora_critica_inicio e _fim [CONFERIR]")
        sombra = sombra_entre_fileiras(lat, incl, azim, prof, alt, prof, dc, horas_criticas) if lat is not None and incl > 0 else None
        passo = passo_m if passo_m else (max(prof + folga_m, sombra["passo_minimo_m"]) if sombra else prof + folga_m)
        if sombra:
            sombra = sombra_entre_fileiras(lat, incl, azim, prof, alt, passo, dc, horas_criticas)
    fx, fy = math.sin(A), math.cos(A)            # para onde as placas olham
    ux, uy = fy, -fx                             # ao longo da fileira
    loc = [[p[0] * ux + p[1] * uy, p[0] * fx + p[1] * fy] for p in poligono]
    glob = lambda u, v: [u * ux + v * fx, u * uy + v * fy]
    us, vs = [p[0] for p in loc], [p[1] for p in loc]
    obs = [[[q[0] * ux + q[1] * uy, q[0] * fx + q[1] * fy] for q in ob] for ob in (obstaculos or [])]      # edificações no solo
    mods, mesas = [], 0
    v = max(vs) - afastamento_m - prof          # a primeira fileira fica na frente (lado para onde as placas olham)
    while v >= min(vs) + afastamento_m - 1e-9:
        u = min(us) + afastamento_m
        while u + du <= max(us) - afastamento_m + 1e-9:
            cantos = [[u, v], [u + du, v], [u + du, v + prof], [u, v + prof]]
            livre = not any(any(dentro_poligono(q, ob) for q in cantos + [[u + du / 2, v + prof / 2]]) or any(dentro_poligono(q, cantos) for q in ob) for ob in obs)
            if livre and _cabe(cantos, loc, afastamento_m):
                mesas += 1
                for k in range(n):
                    vc = v + prof - (k + 0.5) * prof / n
                    mods.append({"x": glob(u + du / 2, vc)[0], "y": glob(u + du / 2, vc)[1], "fileira": None})
            u += du + folga_m
        v -= passo
    kwp = len(mods) * modulo["pmax"] / 1000
    return {"modulos": len(mods), "mesas": mesas, "kwp": kwp, "area_modulos_m2": len(mods) * L * W, "area_ocupada_m2": mesas * du * prof,
            "passo_m": passo, "profundidade_mesa_m": prof, "altura_mesa_m": alt, "orientacao": orientacao, "empilhados": n,
            "incl": incl if plano != "telhado" else None, "azim": azim if plano != "telhado" else None, "plano": plano,
            "sombra_entre_fileiras": sombra, "posicoes": mods}


# ═══════════════ 6. Contrato de geometria para o motor de simulação (physis_hub/simulacao, de outro agente) ═══════════════
ESQUEMA_GEOMETRIA = "physis-geometria-lugar/1"


def geometria_para_simulacao(lat, lon, grade: dict | None = None, caixas: list | None = None, superficies: list | None = None,
                             elementos_bim: list | None = None, materiais_base: dict | None = None) -> dict:
    """Só dados (nenhuma conta) para calor, estrutura, fluidos, hidrologia e Monte Carlo: terreno em grade (metros locais,
    x leste, y norte), caixas das edificações, superfícies com orientação e irradiação, e os materiais de cada elemento
    BIM com densidade, condutividade, calor específico e carbono da base sistema/physis-materiais.json."""
    mats = materiais_base or {}
    els = []
    for e in elementos_bim or []:
        ms = []
        for m in e.get("materiais") or []:
            b = mats.get(m.get("id")) or {}
            ms.append({"id": m.get("id"), "quantidade": m.get("quantidade"), "unidade": m.get("unidade"),
                       "densidade_kg_m3": b.get("densidade"), "condutividade_w_mk": b.get("condutividade"),
                       "calor_especifico_j_kgk": b.get("calor_especifico"), "carbono_kgco2e_kg": (b.get("carbono_incorporado") or {}).get("valor")})
        els.append({"id": e.get("id"), "tipo": e.get("tipo"), "posicao_m": e.get("posicao") or {}, "caixa_m": e.get("caixa") or {}, "materiais": ms})
    g = None
    if grade:
        g = {k: grade[k] for k in ("x0", "y0", "cs", "nx", "ny")}
        g.update({"Z": list(grade["Z"]), "unidade": "m", "ordem": "Z[j·nx + i]: j do sul para o norte, i do oeste para o leste"})
    return {"esquema": ESQUEMA_GEOMETRIA, "origem": {"lat": lat, "lon": lon, "conversao": "x = (lon − lon0)·111320·cos(lat0); y = (lat − lat0)·110540 (como o Planejador)"},
            "terreno": g, "edificacoes": [{k: c.get(k) for k in ("id", "nome", "x", "y", "w", "d", "rot", "h", "z0")} for c in caixas or []],
            "superficies": [{k: s.get(k) for k in ("id", "tipo", "x", "y", "z", "incl", "azim", "area_m2", "anual_kwh_m2", "mensal_kwh_m2_dia")} for s in superficies or []],
            "elementos_bim": els}


# ═══════════════ Rotas (o servidor só repassa) ═══════════════
def rota(metodo: str, caminho: str, q: dict, corpo: bytes | None, *, hub=None, uploads: Uploads | None = None,
         pasta=None, nome_arquivo: str = "", quem: str = "", irradiacao_solar: dict | None = None):
    """(código, dict) para as rotas /api/mapeamento/…, ou None se o caminho não é daqui.
    IFC: (código, bytes, tipo) para o arquivo."""
    if not caminho.startswith("/api/mapeamento"):
        return None
    sub = caminho[len("/api/mapeamento"):].rstrip("/")
    arg = lambda k, d="": (q.get(k) or [d])[0]
    inst = str(getattr(hub, "instancia", {}).get("id", "") if hub is not None and isinstance(getattr(hub, "instancia", None), dict) else "")
    if metodo == "GET" and sub == "/camadas":
        return 200, {"ok": True, "camadas": catalogo(pasta)}
    if metodo == "GET" and sub == "/camada":
        r = camada(arg("id"), arg("bbox"), pasta)
        return (200 if r.get("ok") or r.get("sem_camada") else 400), r
    if metodo == "GET" and sub == "/contexto":
        local = hub.local_da_instalacao() if hub is not None and hasattr(hub, "local_da_instalacao") else {}
        ups = uploads.listar(inst) if uploads else []
        return 200, {"ok": True, "contexto": construir_contexto(local, None, pasta, ups, irradiacao_solar, inst)}
    if metodo == "POST" and sub == "/contexto":
        try:
            d = json.loads((corpo or b"{}").decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return 400, {"ok": False, "erro": "JSON inválido"}
        local = hub.local_da_instalacao() if hub is not None and hasattr(hub, "local_da_instalacao") else (d.get("local") or {})
        ups = uploads.listar(inst) if uploads else []
        return 200, {"ok": True, "contexto": construir_contexto(local, d.get("lote"), pasta, ups, d.get("irradiacao_solar") or irradiacao_solar, inst)}
    if sub == "/uploads" and metodo == "GET":
        return 200, {"ok": True, "uploads": uploads.listar(inst) if uploads else []}
    if sub == "/upload" and metodo == "POST":
        if uploads is None:
            return 503, {"ok": False, "erro": "armazenamento indisponível"}
        try:
            return 200, uploads.guardar(nome_arquivo, corpo or b"", inst, quem)
        except ArquivoInvalido as e:
            return 400, {"ok": False, "erro": str(e)}
    if sub == "/upload" and metodo == "GET":
        g = uploads.geojson(arg("id")) if uploads else None
        if g is None:
            return 404, {"ok": False, "erro": "arquivo não encontrado ou com integridade quebrada"}
        return 200, {"ok": True, "geojson": g, "info": uploads.info(arg("id"))}
    if sub == "/upload" and metodo == "DELETE":
        return (200, {"ok": True}) if uploads and uploads.apagar(arg("id")) else (404, {"ok": False, "erro": "arquivo não encontrado"})
    if sub == "/incidencia" and metodo == "POST":
        try:
            d = json.loads((corpo or b"{}").decode("utf-8"))
            sup = d.get("superficies") or []
            if len(sup) > 2000:
                raise ValueError("superfícies demais (máximo 2.000)")
            return 200, {"ok": True, **incidencia(d.get("H"), float(d.get("lat")), sup, d.get("grade"), d.get("caixas"),
                                                  float(d.get("albedo", 0.2)), str(d.get("fonte_irradiacao") or ""))}
        except (UnicodeDecodeError, ValueError, TypeError, KeyError) as e:
            return 400, {"ok": False, "erro": str(e)}
    if sub == "/planta-solar" and metodo == "POST":
        try:
            d = json.loads((corpo or b"{}").decode("utf-8"))
            a = d.get("arranjo") or {}
            r = arranjo(d["poligono"], d["modulo"], orientacao=a.get("orientacao", "retrato"), empilhados=int(a.get("empilhados", 1)),
                        incl=float(a.get("incl", 0)), azim=float(a.get("azim", 0)), afastamento_m=float(a["afastamento_m"]),
                        folga_m=float(a["folga_m"]), passo_m=a.get("passo_m"), plano=a.get("plano", "solo"),
                        lat=d.get("lat"), dia_critico=a.get("dia_critico"), horas_criticas=tuple(a["horas_criticas"]), obstaculos=d.get("obstaculos"))
            r.pop("posicoes", None) if len(r["posicoes"]) > 5000 else None
            return 200, {"ok": True, "arranjo": r, "carta_solar": carta_solar(float(d["lat"])) if d.get("lat") is not None else None}
        except (UnicodeDecodeError, ValueError, TypeError, KeyError) as e:
            return 400, {"ok": False, "erro": f"entrada inválida: {e}"}
    if sub == "/ifc" and metodo == "POST":
        from . import ifc as ifc_mod
        try:
            d = json.loads((corpo or b"{}").decode("utf-8"))
            texto = ifc_mod.escrever(d)
        except (UnicodeDecodeError, ValueError, TypeError, KeyError) as e:
            return 400, {"ok": False, "erro": str(e)}
        return 200, texto.encode("utf-8"), "application/x-step"
    if sub == "/ifc/ler" and metodo == "POST":
        from . import ifc as ifc_mod
        try:
            return 200, {"ok": True, "resumo": ifc_mod.ler(corpo or b"")}
        except ValueError as e:
            return 400, {"ok": False, "erro": str(e)}
        except (AttributeError, IndexError, KeyError, TypeError) as e:   # IFC fora do padrão STEP: avisa, não derruba (26/11/2026)
            return 400, {"ok": False, "erro": "IFC fora do padrão (não deu para ler): " + type(e).__name__}
    return 404, {"ok": False, "erro": "rota do mapeamento desconhecida"}
