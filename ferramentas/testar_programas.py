#!/usr/bin/env python3
r"""Teste dos programas ligados à plataforma, no próprio servidor (sem tela, sem internet):

    py ferramentas\testar_programas.py

Para cada receita de physis_hub/programas_externos.py cria uma entrada pequena de exemplo (cubo, ponto, grade, molécula,
DXF, script LJ do LAMMPS, exemplo do EnergyPlus), roda e diz: ok, erro (com o motivo) ou pulado (programa não instalado
ou sem exemplo). Grava C:\physis\teste-programas-AAAAMMDD-HHMM.md.
"""
import glob
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "physis-hub"))
from physis_hub import programas_externos as pe  # noqa: E402

STL = "solid cubo\n" + "".join(
    f"facet normal 0 0 0\nouter loop\nvertex {a}\nvertex {b}\nvertex {c}\nendloop\nendfacet\n" for a, b, c in [
        ("0 0 0", "10 0 0", "10 10 0"), ("0 0 0", "10 10 0", "0 10 0"), ("0 0 10", "10 10 10", "10 0 10"), ("0 0 10", "0 10 10", "10 10 10"),
        ("0 0 0", "10 0 10", "10 0 0"), ("0 0 0", "0 0 10", "10 0 10"), ("0 10 0", "10 10 0", "10 10 10"), ("0 10 0", "10 10 10", "0 10 10"),
        ("0 0 0", "0 10 0", "0 10 10"), ("0 0 0", "0 10 10", "0 0 10"), ("10 0 0", "10 10 10", "10 10 0"), ("10 0 0", "10 0 10", "10 10 10")]) + "endsolid cubo\n"
GEOJSON = json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"nome": "Petrópolis"},
                      "geometry": {"type": "Point", "coordinates": [-43.18, -22.50]}}]})
ASC = "ncols 2\nnrows 2\nxllcorner -43.5\nyllcorner -23\ncellsize 0.5\nNODATA_value -9999\n1 2\n3 4\n"
DXF = "0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n30\n0\n11\n100\n21\n50\n31\n0\n0\nENDSEC\n0\nEOF\n"
LJ = "units lj\natom_style atomic\nlattice fcc 0.8442\nregion caixa block 0 4 0 4 0 4\ncreate_box 1 caixa\ncreate_atoms 1 box\nmass 1 1.0\n" \
     "velocity all create 3.0 87287\npair_style lj/cut 2.5\npair_coeff 1 1 1.0 1.0 2.5\nfix 1 all nve\nthermo 50\nrun 100\n"
AGUA = "3\nagua\nO 0.000 0.000 0.117\nH 0.000 0.757 -0.469\nH 0.000 -0.757 -0.469\n"


def amostras(d: Path) -> dict:
    a = {"blender.glb": ("cubo.stl", STL.encode()), "prusaslicer.fatiar": ("cubo.stl", STL.encode()),
         "qgis.vetor": ("ponto.geojson", GEOJSON.encode()), "qgis.processo": ("ponto.geojson", GEOJSON.encode()),
         "qgis.raster": ("grade.asc", ASC.encode()), "librecad.pdf": ("linha.dxf", DXF.encode()),
         "rdkit.descritores": ("moleculas.smi", b"CCO\nc1ccccc1\n"), "lammps.in": ("in.lj", LJ.encode()), "psi4.energia": ("agua.xyz", AGUA.encode()),
         "gmsh.malha": ("caixa.geo", b'SetFactory("OpenCASCADE");\nBox(1) = {0,0,0,10,10,10};\n'), "servicos.saude": ("", b"")}
    try:                                     # cubo STEP para o FreeCAD, gerado pelo Gmsh (se houver)
        import gmsh
        gmsh.initialize(); gmsh.option.setNumber("General.Terminal", 0); gmsh.model.occ.addBox(0, 0, 0, 10, 10, 10); gmsh.model.occ.synchronize()
        gmsh.write(str(d / "cubo.step")); gmsh.finalize()
        a["freecad.solido"] = ("cubo.step", (d / "cubo.step").read_bytes())
    except Exception:  # noqa: BLE001
        pass
    try:                                     # imagem com texto para o OCR
        from PIL import Image, ImageDraw
        im = Image.new("L", (600, 120), 255); ImageDraw.Draw(im).text((20, 40), "Physis teste de leitura 2026", fill=0)
        im = im.resize((1800, 360)); im.save(d / "texto.png"); a["tesseract.ocr"] = ("texto.png", (d / "texto.png").read_bytes())
    except Exception:  # noqa: BLE001
        pass
    ep = pe.localizar("energyplus")
    if ep:
        ex = sorted(glob.glob(str(Path(ep).parent / "ExampleFiles" / "1ZoneUncontrolled.idf")))
        if ex:
            a["energyplus.idf"] = ("1ZoneUncontrolled.idf", Path(ex[0]).read_bytes())
    kc = pe.localizar("kicad")
    if kc:
        pcb = sorted(glob.glob(str(Path(kc).parent.parent / "share" / "kicad" / "demos" / "*" / "*.kicad_pcb")))
        if pcb:
            a["kicad.gerber"] = (Path(pcb[0]).name, Path(pcb[0]).read_bytes())
    return a


def main() -> int:
    d = Path(tempfile.mkdtemp(prefix="physis-teste-prog-"))
    pg = pe.Programas(d / "trabalhos")
    am = amostras(d)
    linhas = ["# Teste dos programas pela plataforma · " + time.strftime("%d/%m/%Y %H:%M"), "", "| Receita | Programa | Situação | Detalhe |", "|---|---|---|---|"]
    disp = {r["id"]: r for r in pe.disponiveis()}
    for rid, r in pe.RECEITAS.items():
        if not disp[rid]["disponivel"]:
            sit, det = "pulado", "programa não instalado"
        elif rid not in am:
            sit, det = "pulado", "sem exemplo automático (testar com um arquivo real na página /programas)"
        else:
            nome, dados = am[rid]
            ini = pg.iniciar(rid, dados or None, nome, {}, "teste", esperar=True)
            if not ini.get("ok"):
                sit, det = "erro", ini.get("erro", "")
            else:
                e = pg.estado(ini["id"])
                sit = "ok" if e["estado"] == "ok" else "erro"
                det = (json.dumps(e.get("resumo"), ensure_ascii=False)[:160] if e.get("resumo") else ", ".join(a["nome"] for a in e["arquivos"])[:160]) if sit == "ok" else (e.get("erro") or "")[-200:]
        linhas.append(f"| {rid} | {r['programa'] or 'serviços'} | {sit} | {str(det).replace('|', '/').replace(chr(10), ' ')} |")
        print(f"{rid:22} {sit:7} {str(det)[:110]}")
    rel = Path("C:/physis" if os.name == "nt" else tempfile.gettempdir()) / ("teste-programas-" + time.strftime("%Y%m%d-%H%M") + ".md")
    rel.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print("\nRelatório:", rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
