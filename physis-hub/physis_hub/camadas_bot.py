"""Bot de camadas (25/11/2026: "fazer o bot de camadas para baixar e converter cada uma da fonte oficial").

Roda sozinho na rodada diária do M&A (bot "camadas") e também à mão (ferramentas/bot_camadas.py). Para cada camada do catálogo
de mapeamento.py que falta (ou que passou de PHYSIS_CAMADAS_DIAS dias, padrão: só quando falta), na janela das cidades onde a
Physis atua (mv_ecossistema.cidades: Petrópolis, Itirapuã ... + cidades.json):

  automático, sem cadastro:
    hidrografia     ← OpenStreetMap (rios, córregos, canais e nascentes) — provisória até a BHO da ANA em fontes-camadas.txt
    rede_eletrica   ← OpenStreetMap (linhas e subestações) — provisória até o SIGEL da ANEEL em fontes-camadas.txt
    irradiacao(+12) ← NASA POWER, climatologia (kWh/m²·dia, grade de 0,5°) — provisória até o Atlas do LABREN
    vento           ← NASA POWER, climatologia (m/s a 50 m, grade de 0,5°) — provisória até o Atlas do CRESESB
  pelo endereço oficial escrito em PHYSIS_CAMADAS/fontes-camadas.txt (uma linha: camada;https://...):
    uso_solo, solos, car, risco, clima (e as quatro acima, quando houver o arquivo oficial: ele SUBSTITUI a provisória)
    conversão pelo GDAL do QGIS (ogr2ogr / gdal_translate): vetor → GeoJSON em WGS84 recortado na janela;
    raster → grade .asc recortada; clima: .zip/.epw → PHYSIS_CAMADAS/clima/*.epw.

Regra 1: nada é inventado. Cada arquivo ganha <arquivo>.fonte.json (endereço, data, licença declarada pela fonte, se é provisória)
e o relatório diz o que faltou e por quê. Sem internet, sem GDAL ou sem endereço oficial: a camada fica "falta" com o motivo.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

URL_OVERPASS = "https://overpass-api.de/api/interpreter"
URL_POWER = ("https://power.larc.nasa.gov/api/temporal/climatology/point?parameters={p}&community=RE"
             "&longitude={lon:.4f}&latitude={lat:.4f}&format=JSON")
MESES = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
GRADE = 0.5                    # resolução da NASA POWER (graus)
MAX_PONTOS = 300               # pedidos à NASA POWER por rodada
MAX_JANELA = 0.5               # lado máximo de cada janela do Overpass (graus)
VETOR_OFICIAL = {"hidrografia", "rede_eletrica", "solos", "car", "risco"}
RASTER_OFICIAL = {"uso_solo", "irradiacao", "vento"}
ARQUIVO = {"hidrografia": "hidrografia.geojson", "rede_eletrica": "rede_eletrica.geojson", "solos": "solos.geojson",
           "car": "car.geojson", "risco": "risco.geojson", "uso_solo": "uso_solo.asc", "irradiacao": "irradiacao.asc",
           "vento": "vento.asc", "clima": "clima"}
TODAS = list(ARQUIVO)


def buscar(url: str, dados: bytes | None = None, tempo: int = 180) -> bytes:
    req = urllib.request.Request(url, data=dados, headers={"User-Agent": "Physis-bot-camadas/1 (servidor da Physis)"})
    with urllib.request.urlopen(req, timeout=tempo) as r:
        return r.read()


def janelas(cids: list[dict]) -> list[tuple[float, float, float, float]]:
    """(oeste, sul, leste, norte) de cada cidade: raio_km em graus (1° ≈ 111 km), lado limitado a MAX_JANELA."""
    out = []
    for c in cids:
        d = min(float(c.get("raio_km") or 20) / 111.0, MAX_JANELA / 2)
        out.append((round(c["lon"] - d, 4), round(c["lat"] - d, 4), round(c["lon"] + d, 4), round(c["lat"] + d, 4)))
    return out


def uniao(js) -> tuple[float, float, float, float]:
    return (min(j[0] for j in js), min(j[1] for j in js), max(j[2] for j in js), max(j[3] for j in js))


def _fonte(destino: Path, **k) -> None:
    k.setdefault("baixado", time.strftime("%Y-%m-%d"))
    Path(str(destino) + ".fonte.json").write_text(json.dumps(k, ensure_ascii=False, indent=1), encoding="utf-8")


# ── OpenStreetMap (hidrografia e rede elétrica) ──────────────────────────────────────────────────────────────────────────
CONSULTAS = {"hidrografia": ['way["waterway"~"^(river|stream|canal)$"]', 'node["natural"="spring"]'],
             "rede_eletrica": ['way["power"~"^(line|minor_line)$"]', 'way["power"="substation"]', 'node["power"="substation"]']}


def osm_camada(camada: str, js, pegar=buscar) -> dict:
    feats, vistos = [], set()
    for o, s, l, n in js:
        partes = "".join(f"{q}({s},{o},{n},{l});" for q in CONSULTAS[camada])
        j = json.loads(pegar(URL_OVERPASS, urllib.parse.urlencode({"data": f"[out:json][timeout:120];({partes});out geom;"}).encode()).decode("utf-8"))
        for el in j.get("elements", []):
            chave = (el.get("type"), el.get("id"))
            if chave in vistos:
                continue
            vistos.add(chave)
            t = el.get("tags", {})
            if el.get("type") == "node":
                geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
            else:
                g = el.get("geometry") or []
                if len(g) < 2:
                    continue
                cs = [[p["lon"], p["lat"]] for p in g]
                geom = ({"type": "Polygon", "coordinates": [cs]} if t.get("power") == "substation" and cs[0] == cs[-1] and len(cs) >= 4
                        else {"type": "LineString", "coordinates": cs})
            props = {"osm_id": el.get("id"), "nome": t.get("name"),
                     "tipo": t.get("waterway") or ("nascente" if t.get("natural") == "spring" else None) or t.get("power"),
                     "tensao_v": t.get("voltage"), "operador": t.get("operator")}
            feats.append({"type": "Feature", "geometry": geom, "properties": {k: v for k, v in props.items() if v}})
    return {"type": "FeatureCollection", "features": feats}


# ── NASA POWER (irradiação e vento, climatologia) ────────────────────────────────────────────────────────────────────────
def power_grade(js, pegar=buscar) -> dict:
    """Pontos da grade de 0,5° que cobrem a união das janelas: {(lon, lat): {"sol": {mes: v, "ANN": v}, "vento": v}}."""
    import math
    o, s, l, n = uniao(js)
    lons = [round(x * GRADE, 4) for x in range(math.floor(o / GRADE), math.ceil(l / GRADE) + 1)]
    lats = [round(y * GRADE, 4) for y in range(math.floor(s / GRADE), math.ceil(n / GRADE) + 1)]
    if len(lons) * len(lats) > MAX_PONTOS:
        raise ValueError(f"janela grande demais para a NASA POWER ({len(lons) * len(lats)} pontos; máximo {MAX_PONTOS})")
    pts = {}
    for la in lats:
        for lo in lons:
            j = json.loads(pegar(URL_POWER.format(p="ALLSKY_SFC_SW_DWN,WS50M", lon=lo, lat=la)).decode("utf-8"))
            par = j["properties"]["parameter"]
            pts[(lo, la)] = {"sol": par["ALLSKY_SFC_SW_DWN"], "vento": par["WS50M"].get("ANN")}
    return {"lons": lons, "lats": lats, "pontos": pts}


def grava_asc(destino: Path, g: dict, valor) -> None:
    """Grade ESRI ASCII com centro das células nos pontos da NASA POWER (linha de cima = norte)."""
    lons, lats = g["lons"], sorted(g["lats"], reverse=True)
    linhas = [f"ncols {len(lons)}", f"nrows {len(lats)}", f"xllcenter {lons[0]}", f"yllcenter {lats[-1]}", f"cellsize {GRADE}",
              "NODATA_value -9999"]
    for la in lats:
        vs = []
        for lo in lons:
            v = valor(g["pontos"][(lo, la)])
            vs.append("-9999" if v is None or v == -999 else f"{float(v):.3f}")
        linhas.append(" ".join(vs))
    destino.write_text("\n".join(linhas) + "\n", encoding="ascii")


# ── GDAL do QGIS (fontes oficiais) ───────────────────────────────────────────────────────────────────────────────────────
def achar_gdal(prog: str) -> str | None:
    exe = shutil.which(prog)
    if exe:
        return exe
    for raiz in (Path("C:/Program Files"), Path("C:/OSGeo4W")):
        for p in sorted(raiz.glob(f"QGIS*/bin/{prog}.exe"), reverse=True) + sorted(raiz.glob(f"bin/{prog}.exe")):
            return str(p)
    return None


def _maior(pasta: Path, exts: tuple[str, ...]) -> Path | None:
    achados = [p for p in pasta.rglob("*") if p.suffix.lower() in exts]
    return max(achados, key=lambda p: p.stat().st_size) if achados else None


def oficial(camada: str, url: str, pasta: Path, brutos: Path, js, pegar=buscar, rodar=subprocess.run) -> str:
    """Baixa o arquivo oficial e converte. Devolve o caminho gravado; erro = ValueError com o motivo."""
    d = brutos / camada
    d.mkdir(parents=True, exist_ok=True)
    nome = (urllib.parse.urlparse(url).path.rsplit("/", 1)[-1] or camada)[:120]
    arq = d / nome
    arq.write_bytes(pegar(url))
    if zipfile.is_zipfile(arq):
        with zipfile.ZipFile(arq) as z:
            z.extractall(d / "extraido")
        base = d / "extraido"
    else:
        base = d
    o, s, l, n = uniao(js)
    if camada == "clima":
        dest = pasta / "clima"
        dest.mkdir(exist_ok=True)
        epws = list(base.rglob("*.epw"))
        if not epws:
            raise ValueError("o arquivo não tem .epw")
        for e in epws:
            shutil.copy2(e, dest / e.name)
        _fonte(dest / epws[0].name, url=url, camada=camada, arquivos=[e.name for e in epws])
        return str(dest)
    destino = pasta / ARQUIVO[camada]
    if camada in VETOR_OFICIAL:
        src = arq if arq.suffix.lower() in (".geojson", ".json", ".gpkg", ".shp", ".kml") else _maior(base, (".shp", ".gpkg", ".geojson", ".json", ".kml"))
        if not src:
            raise ValueError("nenhum vetor (.shp, .gpkg, .geojson, .kml) no arquivo")
        exe = achar_gdal("ogr2ogr")
        if not exe:
            raise ValueError("ogr2ogr não encontrado (vem com o QGIS)")
        tmp = destino.with_suffix(".novo.geojson")
        tmp.unlink(missing_ok=True)
        r = rodar([exe, "-f", "GeoJSON", "-t_srs", "EPSG:4326", "-spat", str(o), str(s), str(l), str(n), "-spat_srs", "EPSG:4326",
                   "-lco", "RFC7946=YES", str(tmp), str(src)], capture_output=True, text=True, timeout=1800)
    else:
        src = arq if arq.suffix.lower() in (".tif", ".tiff", ".asc", ".img") else _maior(base, (".tif", ".tiff", ".asc", ".img"))
        if not src:
            raise ValueError("nenhum raster (.tif, .asc, .img) no arquivo")
        exe = achar_gdal("gdal_translate")
        if not exe:
            raise ValueError("gdal_translate não encontrado (vem com o QGIS)")
        tmp = destino.with_suffix(".novo.asc")
        warp = achar_gdal("gdalwarp")
        entrada = str(src)
        if warp:                                          # garante WGS84 antes de recortar
            w = d / "wgs84.tif"
            rodar([warp, "-overwrite", "-t_srs", "EPSG:4326", "-te", str(o), str(s), str(l), str(n), str(src), str(w)],
                  capture_output=True, text=True, timeout=1800)
            if w.is_file():
                entrada = str(w)
        r = rodar([exe, "-of", "AAIGrid", "-projwin", str(o), str(n), str(l), str(s), entrada, str(tmp)],
                  capture_output=True, text=True, timeout=1800)
    if getattr(r, "returncode", 1) != 0 or not tmp.is_file():
        raise ValueError("conversão falhou: " + (getattr(r, "stderr", "") or "")[-300:])
    tmp.replace(destino)
    _fonte(destino, url=url, camada=camada, oficial=True, janela=[o, s, l, n])
    return str(destino)


def ler_fontes(pasta: Path) -> dict[str, str]:
    f = pasta / "fontes-camadas.txt"
    out = {}
    if f.is_file():
        for l in f.read_text(encoding="utf-8-sig").splitlines():
            if ";" in l and not l.lstrip().startswith("#"):
                c, u = [x.strip() for x in l.split(";", 1)]
                if c in ARQUIVO and u.startswith(("https://", "http://")):
                    out[c] = u
    return out


def modelo_fontes() -> str:
    return ("# fontes-camadas.txt · uma linha por camada: camada;endereço do arquivo OFICIAL (.zip, .shp, .gpkg, .geojson, .tif, .epw)\n"
            "# O bot de camadas baixa, converte (GDAL do QGIS) e recorta na janela das cidades da Physis. Camadas: "
            + ", ".join(TODAS) + "\n# Exemplo (troque pelo endereço conferido na página oficial):\n# uso_solo;https://.../mapbiomas_colecao_X_RJ.tif\n")


def rodar_bot(pasta: Path, cids: list[dict], quais: list[str] | None = None, forcar: bool = False, pegar=buscar, rodar=subprocess.run,
              brutos: Path | None = None) -> dict:
    pasta.mkdir(parents=True, exist_ok=True)
    if not (pasta / "fontes-camadas.txt").is_file():
        (pasta / "fontes-camadas.txt").write_text(modelo_fontes(), encoding="utf-8")
    brutos = brutos or (pasta.parent / "dados-brutos" / "camadas")
    js = janelas(cids)
    fontes = ler_fontes(pasta)
    dias = float(os.environ.get("PHYSIS_CAMADAS_DIAS") or 0)
    res = {}

    def precisa(c):
        p = pasta / ARQUIVO[c]
        if forcar or not p.exists():
            return True
        meta = Path(str(p) + ".fonte.json")
        provisoria = meta.is_file() and json.loads(meta.read_text(encoding="utf-8")).get("provisoria")
        if provisoria and c in fontes:
            return True                                    # chegou o endereço oficial: troca a provisória
        return bool(dias) and (time.time() - p.stat().st_mtime) > dias * 86400

    power = None
    for c in quais or TODAS:
        if not precisa(c):
            res[c] = {"situacao": "ok", "arquivo": str(pasta / ARQUIVO[c])}
            continue
        try:
            if c in fontes:
                res[c] = {"situacao": "baixada (oficial)", "arquivo": oficial(c, fontes[c], pasta, brutos, js, pegar, rodar), "fonte": fontes[c]}
            elif c in CONSULTAS:
                gj = osm_camada(c, js, pegar)
                gj["_fonte"] = {"url": URL_OVERPASS, "licenca": "© colaboradores do OpenStreetMap, ODbL 1.0", "janelas": js}
                (pasta / ARQUIVO[c]).write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
                _fonte(pasta / ARQUIVO[c], url=URL_OVERPASS, provisoria=True, licenca="ODbL 1.0 (OpenStreetMap)",
                       oficial_pendente="ANA · BHO" if c == "hidrografia" else "ANEEL · SIGEL", feicoes=len(gj["features"]))
                res[c] = {"situacao": "baixada (provisória: OpenStreetMap)", "feicoes": len(gj["features"]), "arquivo": str(pasta / ARQUIVO[c])}
            elif c in ("irradiacao", "vento"):
                power = power or power_grade(js, pegar)
                if c == "irradiacao":
                    grava_asc(pasta / "irradiacao.asc", power, lambda p: p["sol"].get("ANN"))
                    for i, m in enumerate(MESES, start=1):
                        grava_asc(pasta / f"irradiacao_{i:02d}.asc", power, lambda p, m=m: p["sol"].get(m))
                else:
                    grava_asc(pasta / "vento.asc", power, lambda p: p["vento"])
                _fonte(pasta / ARQUIVO[c], url="https://power.larc.nasa.gov/", provisoria=True,
                       produto="NASA POWER, climatologia " + ("ALLSKY_SFC_SW_DWN (kWh/m²·dia)" if c == "irradiacao" else "WS50M (m/s a 50 m)"),
                       licenca="dados públicos da NASA, citar a fonte", oficial_pendente="INPE/LABREN" if c == "irradiacao" else "CEPEL/CRESESB",
                       grade_graus=GRADE)
                res[c] = {"situacao": "baixada (provisória: NASA POWER)", "pontos": len(power["pontos"]), "arquivo": str(pasta / ARQUIVO[c])}
            else:
                res[c] = {"situacao": "falta", "motivo": "sem endereço oficial em fontes-camadas.txt (a fonte exige download pela página ou cadastro)"}
        except Exception as e:  # noqa: BLE001 — uma camada com defeito não para as outras
            res[c] = {"situacao": "falta", "motivo": f"{type(e).__name__}: {str(e)[:200]}"}
    return {"pasta": str(pasta), "janelas": js, "camadas": res,
            "faltam": [c for c, r in res.items() if r["situacao"] == "falta"],
            "provisorias": [c for c, r in res.items() if "provisória" in r["situacao"]]}


def bot_camadas(mv, pasta: Path | None = None) -> dict:
    """Bot do M&A (rodada diária). Sem PHYSIS_CAMADAS: só avisa."""
    from . import mv_comandos, mv_ecossistema
    inicio = mv.nova_rodada()
    alvo = pasta or (Path(os.environ["PHYSIS_CAMADAS"]) if os.environ.get("PHYSIS_CAMADAS") else None)
    if not alvo:
        r = {"aviso": "PHYSIS_CAMADAS não definida"}
    else:
        r = rodar_bot(Path(alvo), mv_ecossistema.cidades())
        if r["faltam"]:
            ref = "camadas:faltam:" + ",".join(sorted(r["faltam"]))
            if not mv.db.execute("SELECT 1 FROM mv_pedido_bot WHERE comando=?", (ref,)).fetchone():
                mv_comandos.Comandos(mv)._pedido("camadas", ref, "", "rascunho",
                                                 "Camadas sem fonte automática: " + ", ".join(sorted(r["faltam"]))
                                                 + ". Escrever o endereço oficial em " + str(Path(alvo) / "fontes-camadas.txt")
                                                 + " (camada;https://...); o bot baixa e converte na próxima rodada.", str(alvo), origem="camadas")
    mv.registrar_execucao("camadas", inicio, json.dumps(r, ensure_ascii=False, default=str))
    return r
