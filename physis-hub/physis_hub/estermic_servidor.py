"""Sistema Estermic à parte no servidor Windows (pedido da dona de 24/11/2026; aprovação no M&A: ap-p0-estermic-sistema).

Serve a ferramenta interna da Estermic (modulos/estermic/estermic-avac.html, com o AVAC completo: carga térmica, ar-condicionado,
ventilação, pressurização, aquecimento solar, piscina com filtragem e borda infinita, sauna, churrasqueira, dutos, água gelada,
quadro elétrico, equipamentos, BIM/IFC de instalações, GIS, financeiro e emissão) numa porta própria, separada do M&A, do Hub
e dos sites. O estado dos subprojetos fica no servidor (estermic.db na pasta de dados, com histórico), não só no navegador.

    cd C:\physis\physis-ma-20261122-1bd599e\physis-hub
    py -m physis_hub.estermic_servidor            # http://127.0.0.1:8704  (PHYSIS_ESTERMIC_PORTA / PHYSIS_ESTERMIC_ENDERECO)

Acesso: só este computador por padrão. Para a rede, PHYSIS_ESTERMIC_ENDERECO=0.0.0.0 e, obrigatório, PHYSIS_ESTERMIC_SENHA (usuário
"physis"; regra 12: senha só na variável de ambiente). Sem dependências (Python 3.10).
"""
from __future__ import annotations

import base64
import hmac
import json
import mimetypes
import re
import shutil
import subprocess
import sys
import tempfile
import os
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import mv as mvmod

RAIZ = Path(__file__).resolve().parents[2]
PAGINA = "/modulos/estermic/estermic-avac.html"
PERMITIDOS = ("sistema/", "modulos/estermic/", "vendor/")
MAX_ESTADO = 20 * 1024 * 1024
ESQUEMA = """CREATE TABLE IF NOT EXISTS estermic_estado (id INTEGER PRIMARY KEY AUTOINCREMENT, estado TEXT NOT NULL, gravado REAL NOT NULL, origem TEXT NOT NULL);"""


class Banco:
    def __init__(self, caminho: str | Path | None = None):
        self.caminho = str(caminho or (mvmod.pasta_padrao() / "estermic.db"))
        if self.caminho != ":memory:":
            Path(self.caminho).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.caminho, check_same_thread=False, timeout=30)
        self.db.executescript(ESQUEMA)
        self.trava = threading.Lock()

    def ler(self) -> dict | None:
        r = self.db.execute("SELECT estado, gravado FROM estermic_estado ORDER BY id DESC LIMIT 1").fetchone()
        return {"estado": json.loads(r[0]), "gravado": r[1]} if r else None

    def gravar(self, estado: dict, origem: str = "tela") -> float:
        if not isinstance(estado, dict) or not isinstance(estado.get("subprojetos"), list):
            raise ValueError("estado inválido (sem subprojetos)")
        txt = json.dumps(estado, ensure_ascii=False)
        with self.trava:
            ult = self.db.execute("SELECT estado FROM estermic_estado ORDER BY id DESC LIMIT 1").fetchone()
            agora = time.time()
            if not ult or ult[0] != txt:
                self.db.execute("INSERT INTO estermic_estado (estado, gravado, origem) VALUES (?,?,?)", (txt, agora, origem[:40]))
                # histórico: guarda as 200 últimas versões
                self.db.execute("DELETE FROM estermic_estado WHERE id NOT IN (SELECT id FROM estermic_estado ORDER BY id DESC LIMIT 200)")
                self.db.commit()
            return agora

    def historico(self, n: int = 30) -> list[dict]:
        return [{"id": a, "gravado": b, "origem": c} for a, b, c in
                self.db.execute("SELECT id, gravado, origem FROM estermic_estado ORDER BY id DESC LIMIT ?", (int(n),))]


def achar_programa(nomes: list[str], pastas_windows: list[str], variavel: str = "") -> str | None:
    """Executável pelo PATH, pela variável de ambiente ou pelas pastas de instalação comuns do Windows (FreeCAD, Tesseract)."""
    import glob
    if variavel and os.environ.get(variavel):
        return os.environ[variavel]
    for n in nomes:
        if shutil.which(n):
            return shutil.which(n)
    for g in pastas_windows:
        achados = sorted(glob.glob(g))
        if achados:
            return achados[-1]
    return None


def ocr(imagem: bytes, idioma: str = "por") -> dict:
    """Palavras e caixas pelo Tesseract (software aberto, instalado no servidor; 24/11/2026). Sem ele, diz como instalar."""
    exe = achar_programa(["tesseract"], ["C:/Program Files/Tesseract-OCR/tesseract.exe", "C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"], "PHYSIS_TESSERACT")
    if not exe:
        return {"ok": False, "erro": "Tesseract não instalado no servidor (Windows: winget install UB-Mannheim.TesseractOCR; Linux: apt install tesseract-ocr tesseract-ocr-por)"}
    with tempfile.TemporaryDirectory() as d:
        arq = Path(d) / "img"
        arq.write_bytes(imagem)
        r = subprocess.run([exe, str(arq), "stdout", "-l", idioma, "--psm", "11", "tsv"], capture_output=True, timeout=120)
        if r.returncode != 0 and idioma != "eng":
            r = subprocess.run([exe, str(arq), "stdout", "--psm", "11", "tsv"], capture_output=True, timeout=120)
    linhas = r.stdout.decode("utf-8", "replace").splitlines()
    palavras = []
    for l in linhas[1:]:
        c = l.split("\t")
        if len(c) >= 12 and c[11].strip() and c[10] not in ("-1", ""):
            try:
                if float(c[10]) < 30:
                    continue
                palavras.append({"t": c[11].strip(), "x": int(c[6]), "y": int(c[7]), "w": int(c[8]), "h": int(c[9]), "conf": float(c[10])})
            except ValueError:
                continue
    return {"ok": True, "palavras": palavras}


# ── 24/11/2026: modelagens rodando no próprio servidor Windows, com programas abertos instalados ──
def simular(pedido: dict) -> dict:
    """{"tipo": "suporte", "vao_m", "carga_kg", "b_mm", "h_mm", "E_GPa"} → viga biapoiada no CalculiX (flecha e tensão), com a conta
    de referência ao lado. Sem o CalculiX instalado, devolve só a conta e como instalar. Valores sempre digitados (nada de fábrica)."""
    t = (pedido or {}).get("tipo")
    if t == "cfd-duto":
        return cfd_duto(pedido)
    if t != "suporte":
        return {"ok": False, "erro": "tipos aceitos: suporte (viga de skid/base de equipamento, CalculiX) e cfd-duto (OpenFOAM). EnergyPlus e SAM: pacote de dados na aba Modelagens."}
    try:
        L, P, b, h, E = (float(pedido[k]) for k in ("vao_m", "carga_kg", "b_mm", "h_mm", "E_GPa"))
    except (KeyError, TypeError, ValueError):
        return {"ok": False, "erro": "informe vão (m), carga (kg), base e altura da seção (mm) e E (GPa)"}
    if min(L, P, b, h, E) <= 0:
        return {"ok": False, "erro": "valores precisam ser positivos"}
    F, Lmm, Emp = P * 9.81, L * 1000, E * 1000           # N, mm, MPa
    I, W = b * h ** 3 / 12, b * h ** 2 / 6
    ref = {"flecha_mm": F * Lmm ** 3 / (48 * Emp * I), "tensao_MPa": F * Lmm / 4 / W}
    exe = achar_programa(["ccx", "ccx_static"], ["C:/Program Files/FreeCAD*/bin/ccx.exe", "C:/Program Files/FreeCAD*/bin/calculix/ccx.exe"], "PHYSIS_CCX")
    if not exe:
        return {"ok": True, "programa": None, "referencia": ref, "aviso": "CalculiX não instalado (vem com o FreeCAD; ou PHYSIS_CCX=caminho do ccx.exe): só a conta de referência"}
    n = 20
    inp = ["*NODE"] + [f"{i + 1}, {Lmm * i / (2 * n):.4f}, 0, 0" for i in range(2 * n + 1)]
    inp += ["*ELEMENT, TYPE=B32, ELSET=V"] + [f"{i + 1}, {2 * i + 1}, {2 * i + 2}, {2 * i + 3}" for i in range(n)]
    inp += ["*MATERIAL, NAME=M", "*ELASTIC", f"{Emp}, 0.3", "*BEAM SECTION, ELSET=V, MATERIAL=M, SECTION=RECT", f"{b}, {h}", "0, 0, 1",
            "*BOUNDARY", "1, 1, 3", "1, 4, 4", f"{2 * n + 1}, 2, 3", "*STEP", "*STATIC", "*CLOAD", f"{n + 1}, 2, {-F}", "*NSET, NSET=TODOS, GENERATE", f"1, {2 * n + 1}, 1", "*NODE PRINT, NSET=TODOS", "U", "*END STEP"]
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "s.inp").write_text("\n".join(inp) + "\n", encoding="utf-8")
        subprocess.run([exe, "-i", "s"], cwd=d, capture_output=True, timeout=300)
        dat = (Path(d) / "s.dat").read_text(encoding="utf-8", errors="replace") if (Path(d) / "s.dat").exists() else ""
    uy = []
    for l in dat.splitlines():
        c = l.split()
        if len(c) == 4 and c[0].isdigit():
            try:
                uy.append(abs(float(c[2])))
            except ValueError:
                pass
    if not uy:
        return {"ok": False, "erro": "o CalculiX não devolveu deslocamentos", "referencia": ref}
    return {"ok": True, "programa": "CalculiX", "flecha_mm": max(uy), "referencia": ref}


def render(glb: bytes) -> dict:
    """Modelo .glb → PNG pelo Blender do servidor (ferramentas/renderizar_glb.py, o mesmo do gêmeo da Casa Physis)."""
    import base64 as b64
    script = RAIZ / "ferramentas" / "renderizar_glb.py"
    with tempfile.TemporaryDirectory() as d:
        m, png = Path(d) / "planta.glb", Path(d) / "planta.png"
        m.write_bytes(glb)
        r = subprocess.run([sys.executable, str(script), str(m), str(png), "--largura", "1600", "--altura", "1000", "--amostras", "64"], capture_output=True, timeout=1800)
        if r.returncode != 0 or not png.exists():
            txt = (r.stdout + r.stderr).decode("utf-8", "replace")
            return {"ok": False, "erro": "Blender não encontrado no servidor (winget install BlenderFoundation.Blender ou PHYSIS_BLENDER)" if r.returncode == 2 else "render falhou: " + txt[-300:]}
        return {"ok": True, "png": b64.b64encode(png.read_bytes()).decode()}


# ── 24/11/2026: CFD de duto no OpenFOAM (simpleFoam, k-epsilon). Linux: direto; Windows: pelo WSL (OpenFOAM instalado no Ubuntu do WSL) ──
def _caso_duto(pasta: Path, L: float, a: float, b: float, v: float, nu: float, nx: int = 80, ny: int = 10, nz: int = 10, iters: int = 400) -> None:
    cab = lambda cls, obj: "FoamFile { version 2.0; format ascii; class %s; object %s; }\n" % (cls, obj)
    (pasta / "system").mkdir(parents=True); (pasta / "constant").mkdir(); (pasta / "0").mkdir()
    (pasta / "system/blockMeshDict").write_text(cab("dictionary", "blockMeshDict") + f"""convertToMeters 1;
vertices ((0 0 0) ({L} 0 0) ({L} {a} 0) (0 {a} 0) (0 0 {b}) ({L} 0 {b}) ({L} {a} {b}) (0 {a} {b}));
blocks (hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1));
boundary ( inlet {{ type patch; faces ((0 4 7 3)); }} outlet {{ type patch; faces ((1 2 6 5)); }}
  paredes {{ type wall; faces ((0 1 5 4) (3 7 6 2) (0 3 2 1) (4 5 6 7)); }} );
""")
    (pasta / "system/controlDict").write_text(cab("dictionary", "controlDict") + f"""application simpleFoam; startFrom startTime; startTime 0; stopAt endTime; endTime {iters};
deltaT 1; writeControl timeStep; writeInterval {iters}; purgeWrite 1; writeFormat ascii; writePrecision 8; runTimeModifiable false;
""")
    (pasta / "system/fvSchemes").write_text(cab("dictionary", "fvSchemes") + """ddtSchemes { default steadyState; } gradSchemes { default Gauss linear; }
divSchemes { default none; div(phi,U) bounded Gauss linearUpwind grad(U); div(phi,k) bounded Gauss upwind; div(phi,epsilon) bounded Gauss upwind;
  div((nuEff*dev2(T(grad(U))))) Gauss linear; }
laplacianSchemes { default Gauss linear corrected; } interpolationSchemes { default linear; } snGradSchemes { default corrected; }
wallDist { method meshWave; }
""")
    (pasta / "system/fvSolution").write_text(cab("dictionary", "fvSolution") + """solvers { p { solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol 0.05; }
  "(U|k|epsilon)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-7; relTol 0.1; } }
SIMPLE { nNonOrthogonalCorrectors 0; consistent yes; residualControl { p 1e-5; U 1e-5; "(k|epsilon)" 1e-5; } }
relaxationFactors { equations { U 0.9; ".*" 0.9; } }
""")
    (pasta / "constant/transportProperties").write_text(cab("dictionary", "transportProperties") + f"transportModel Newtonian; nu {nu};\n")
    (pasta / "constant/turbulenceProperties").write_text(cab("dictionary", "turbulenceProperties") + "simulationType RAS; RAS { RASModel kEpsilon; turbulence on; printCoeffs off; }\n")
    Dh = 2 * a * b / (a + b); k = 1.5 * (0.05 * v) ** 2; eps = 0.09 ** 0.75 * k ** 1.5 / (0.07 * Dh)
    campo = lambda cls, nome, dim, inter, ent, sai, par: (pasta / "0" / nome).write_text(cab(cls, nome) + f"dimensions {dim}; internalField uniform {inter};\n"
        f"boundaryField {{ inlet {{ {ent} }} outlet {{ {sai} }} paredes {{ {par} }} }}\n")
    campo("volVectorField", "U", "[0 1 -1 0 0 0 0]", f"({v} 0 0)", f"type fixedValue; value uniform ({v} 0 0);", "type zeroGradient;", "type noSlip;")
    campo("volScalarField", "p", "[0 2 -2 0 0 0 0]", "0", "type zeroGradient;", "type fixedValue; value uniform 0;", "type zeroGradient;")
    campo("volScalarField", "k", "[0 2 -2 0 0 0 0]", f"{k}", f"type fixedValue; value uniform {k};", "type zeroGradient;", f"type kqRWallFunction; value uniform {k};")
    campo("volScalarField", "epsilon", "[0 2 -3 0 0 0 0]", f"{eps}", f"type fixedValue; value uniform {eps};", "type zeroGradient;", f"type epsilonWallFunction; value uniform {eps};")
    campo("volScalarField", "nut", "[0 2 -1 0 0 0 0]", "0", "type calculated; value uniform 0;", "type calculated; value uniform 0;", "type nutkWallFunction; value uniform 0;")


def cfd_duto(pedido: dict, executar=None) -> dict:
    """{"comprimento_m","largura_m","altura_m","vazao_m3h","temp_C"} → perda de pressão no duto pelo OpenFOAM, com Darcy-Weisbach ao lado."""
    try:
        L, a, b, q = (float(pedido[k]) for k in ("comprimento_m", "largura_m", "altura_m", "vazao_m3h"))
        T = float(pedido.get("temp_C") or 20)
    except (KeyError, TypeError, ValueError):
        return {"ok": False, "erro": "informe comprimento, largura, altura (m) e vazão (m³/h)"}
    if min(L, a, b, q) <= 0:
        return {"ok": False, "erro": "valores precisam ser positivos"}
    Tk = T + 273.15; rho = 101325 / (287.05 * Tk); mu = 1.458e-6 * Tk ** 1.5 / (Tk + 110.4); nu = mu / rho
    v = q / 3600 / (a * b); Dh = 2 * a * b / (a + b); Re = v * Dh / nu
    import math
    f = 0.25 / math.log10(0.00009 / (3.7 * Dh) + 5.74 / Re ** 0.9) ** 2          # aço galvanizado 0,09 mm (mesma rugosidade padrão do AVAC)
    ref = {"velocidade_m_s": v, "reynolds": Re, "dp_darcy_Pa": f * L / Dh * rho * v * v / 2}
    linux = shutil.which("simpleFoam") and shutil.which("blockMesh")
    wsl = os.name == "nt" and shutil.which("wsl")
    if not (linux or wsl):
        return {"ok": True, "programa": None, "referencia": ref, "aviso": "OpenFOAM não encontrado (Windows: instale o WSL e, no Ubuntu do WSL, sudo apt install openfoam): só a conta de referência"}
    with tempfile.TemporaryDirectory() as d:
        caso = Path(d) / "duto"; _caso_duto(caso, L, a, b, v, nu)
        amb = ('for f in "$PHYSIS_OPENFOAM_BASHRC" /usr/share/openfoam/etc/bashrc /usr/lib/openfoam/openfoam*/etc/bashrc /opt/openfoam*/etc/bashrc; '
               'do [ -f "$f" ] && . "$f" > /dev/null 2>&1 && break; done; ')
        if linux:
            cmd = ["bash", "-c", amb + f"cd '{caso}' && blockMesh > log.mesh 2>&1 && simpleFoam > log.simple 2>&1"]
        else:
            p = str(caso).replace("\\", "/"); wp = "/mnt/" + p[0].lower() + p[2:]
            cmd = ["wsl", "-e", "bash", "-lc", amb + f"cd '{wp}' && blockMesh > log.mesh 2>&1 && simpleFoam > log.simple 2>&1"]
        r = (executar or subprocess.run)(cmd, capture_output=True, timeout=3600)
        tempos = sorted((p for p in caso.iterdir() if p.is_dir() and p.name.replace(".", "").isdigit() and p.name != "0"), key=lambda p: float(p.name))
        if not tempos or not (tempos[-1] / "p").exists():
            log = (caso / "log.simple").read_text(errors="replace")[-400:] if (caso / "log.simple").exists() else ""
            return {"ok": False, "erro": "o OpenFOAM não rodou: " + (log or str(getattr(r, "stderr", b""))[-300:]), "referencia": ref}
        txt = (tempos[-1] / "p").read_text(errors="replace")
        m = re.search(r"internalField\s+nonuniform\s+List<scalar>\s*(\d+)\s*\((.*?)\)\s*;", txt, re.S)
        if not m:
            return {"ok": False, "erro": "campo de pressão ilegível", "referencia": ref}
        vals = [float(x) for x in m.group(2).split()]
        nx, ny, nz = 80, 10, 10
        p0 = sum(vals[nx * (j + ny * k)] for j in range(ny) for k in range(nz)) / (ny * nz)    # 1ª camada de células (x = dx/2)
        dp = p0 * L / (L - L / nx / 2) * rho                                                   # estende até a entrada; p cinemática × ρ
        return {"ok": True, "programa": "OpenFOAM (simpleFoam, k-epsilon)", "dp_cfd_Pa": dp, "iteracoes": int(float(tempos[-1].name)), "referencia": ref,
                "nota": "malha de 8.000 células, funções de parede e trecho de entrada: diferenças de até cerca de 20% em relação a Darcy são esperadas"}


ENTRAR_HTML = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Entrar · Estermic</title><style>
body{font-family:system-ui,sans-serif;background:#F6F4EE;color:#1B1F23;margin:0;display:flex;min-height:100vh;align-items:center;justify-content:center}
main{background:#FFFFFF;border:1px solid #D9D3C2;border-radius:12px;padding:2rem;max-width:380px;width:calc(100% - 2rem)}
h1{font-family:Fraunces,Georgia,serif;color:#33512F;margin-top:0}label{display:block;margin:.8rem 0 .3rem}
input{width:100%;min-height:44px;font:inherit;padding:.4rem .6rem;border:1px solid #6B6B5E;border-radius:8px;box-sizing:border-box}
button{margin-top:1rem;min-height:44px;width:100%;font:inherit;background:#33512F;color:#FFFFFF;border:0;border-radius:8px;cursor:pointer}
:focus-visible{outline:3px solid #C2410C;outline-offset:2px}#erro{color:#9B1C1C;min-height:1.4em}
@media (prefers-color-scheme: dark){body{background:#1B1F23;color:#F6F4EE}main{background:#22282C;border-color:#4A4F44}h1{color:#B9D3B0}input{background:#1B1F23;color:#F6F4EE}}
</style></head><body><main><h1>Estermic</h1><p>Entre com a senha da Estermic.</p>
<form id="f"><label for="senha">Senha</label><input id="senha" type="password" autocomplete="current-password" required>
<p id="erro" role="alert"></p><button type="submit">Entrar</button></form></main>
<script>document.getElementById("f").addEventListener("submit",function(ev){ev.preventDefault();
fetch("/api/estermic/entrar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({senha:document.getElementById("senha").value})})
.then(function(r){if(r.ok){location.reload();}else{document.getElementById("erro").textContent=r.status===429?"Muitas tentativas: espere alguns minutos.":"Senha incorreta.";}})
.catch(function(){document.getElementById("erro").textContent="Sem ligação com o servidor.";});});</script></body></html>"""
SESSAO_S = 12 * 3600


def fabrica(banco: Banco, senha: str | None):
    import secrets as _sec
    import time as _t
    chave_sessao = _sec.token_bytes(32)          # as sessões valem até o servidor reiniciar
    falhas: dict = {}

    def _token() -> str:
        exp = str(int(_t.time()) + SESSAO_S)
        return exp + "." + hmac.new(chave_sessao, exp.encode(), "sha256").hexdigest()

    def _token_ok(tk: str) -> bool:
        exp, _, sig = (tk or "").partition(".")
        return exp.isdigit() and int(exp) > _t.time() and hmac.compare_digest(sig, hmac.new(chave_sessao, exp.encode(), "sha256").hexdigest())

    def _confere(p: str) -> bool:
        return bool((senha is True and conferir_senha(p)) or (senha not in (None, True) and hmac.compare_digest(p, senha)))

    class H(BaseHTTPRequestHandler):
        server_version = "PhysisEstermic/1"

        def log_message(self, *a):        # sem log no console (pythonw)
            pass

        def _auth(self) -> bool:
            if not senha:
                return True
            # sessão pela página de entrada (cookie) ou Basic (scripts). Sem nenhum dos dois: a PÁGINA de entrada, nunca a
            # janela de senha do navegador (pedido de 25/11/2026); nas rotas /api, 401 em JSON
            for parte in (self.headers.get("Cookie") or "").split(";"):
                k, _, v = parte.strip().partition("=")
                if k == "estermic_sessao" and _token_ok(v):
                    return True
            h = self.headers.get("Authorization", "")
            if h.startswith("Basic "):
                try:
                    u, _, p = base64.b64decode(h[6:]).decode("utf-8").partition(":")
                    if u.strip().lower() == "physis" and _confere(p):
                        return True
                except Exception:  # noqa: BLE001
                    pass
            if self.command == "GET" and not self.path.startswith("/api/"):
                b = ENTRAR_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return False
            self._json(401, {"erro": "entre pela página da Estermic"})
            return False

        def _entrar(self):
            ip = self.client_address[0]
            n, ate = falhas.get(ip, (0, 0.0))
            if _t.time() < ate:
                return self._json(429, {"erro": "muitas tentativas"})
            try:
                tam = int(self.headers.get("Content-Length") or 0)
                d = json.loads(self.rfile.read(tam).decode("utf-8")) if 0 < tam <= 4096 else {}
            except ValueError:
                d = {}
            if senha and _confere(str(d.get("senha") or "")):
                falhas.pop(ip, None)
                b = b'{"ok": true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Set-Cookie", "estermic_sessao=" + _token() + "; Path=/; Max-Age=" + str(SESSAO_S) + "; HttpOnly; SameSite=Strict")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)
                return None
            n += 1
            falhas[ip] = (n, _t.time() + 300 if n >= 10 else 0.0)
            return self._json(401, {"erro": "senha incorreta"})

        def _json(self, cod: int, obj) -> None:
            b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(cod)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):  # noqa: N802
            if not self._auth():
                return
            p = self.path.split("?", 1)[0]
            if p in ("/", "/estermic"):
                self.send_response(302)
                self.send_header("Location", PAGINA + "?cliente=estermic")
                self.end_headers()
                return
            if p == "/api/estermic/estado":
                return self._json(200, banco.ler() or {"estado": None})
            if p == "/api/estermic/historico":
                return self._json(200, {"versoes": banco.historico()})
            if p == "/api/estermic/saude":
                return self._json(200, {"ok": True, "sistema": "estermic"})
            rel = p.lstrip("/")
            if ".." in rel or not rel.startswith(PERMITIDOS):
                return self._json(404, {"erro": "não encontrado"})
            arq = RAIZ / rel
            if not arq.is_file():
                return self._json(404, {"erro": "não encontrado"})
            dados = arq.read_bytes()
            tipo = mimetypes.guess_type(arq.name)[0] or ("application/wasm" if arq.suffix == ".wasm" else "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", tipo + ("; charset=utf-8" if tipo.startswith("text/") or tipo.endswith("javascript") else ""))
            self.send_header("Content-Length", str(len(dados)))
            self.end_headers()
            self.wfile.write(dados)

        def do_POST(self):  # noqa: N802
            if self.path.split("?", 1)[0] == "/api/estermic/entrar":
                return self._entrar()
            if not self._auth():
                return
            if self.path.split("?", 1)[0] == "/api/estermic/render":
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > 50 * 1024 * 1024:
                    return self._json(413, {"erro": "modelo vazio ou maior que 50 MB"})
                return self._json(200, render(self.rfile.read(n)))
            if self.path.split("?", 1)[0] == "/api/estermic/simular":
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > 100000:
                    return self._json(413, {"erro": "pedido inválido"})
                try:
                    return self._json(200, simular(json.loads(self.rfile.read(n).decode("utf-8"))))
                except ValueError:
                    return self._json(400, {"erro": "json inválido"})
            if self.path.split("?", 1)[0] != "/api/estermic/ocr":
                return self._json(404, {"erro": "não encontrado"})
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > 20 * 1024 * 1024:
                return self._json(413, {"erro": "imagem vazia ou maior que 20 MB"})
            return self._json(200, ocr(self.rfile.read(n)))

        def do_PUT(self):  # noqa: N802
            if not self._auth():
                return
            if self.path.split("?", 1)[0] != "/api/estermic/estado":
                return self._json(404, {"erro": "não encontrado"})
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_ESTADO:
                return self._json(413, {"erro": "tamanho inválido"})
            try:
                corpo = json.loads(self.rfile.read(n).decode("utf-8"))
                return self._json(200, {"ok": True, "gravado": banco.gravar(corpo.get("estado"), str(corpo.get("origem") or "tela"))})
            except (ValueError, AttributeError) as e:
                return self._json(400, {"erro": str(e)})

    return H


ARQ_SENHA = "estermic-senha.json"     # na pasta de dados (fora do Git): sal e resumo PBKDF2, nunca a senha


def definir_senha(nova: str, pasta: Path | None = None) -> Path:
    import hashlib
    sal = os.urandom(16)
    arq = Path(pasta or mvmod.pasta_padrao()) / ARQ_SENHA
    arq.write_text(json.dumps({"usuario": "physis", "sal": sal.hex(), "resumo": hashlib.pbkdf2_hmac("sha256", nova.encode(), sal, 200000).hex()}), encoding="utf-8")
    return arq


def conferir_senha(dada: str, pasta: Path | None = None) -> bool | None:
    import hashlib
    arq = Path(pasta or mvmod.pasta_padrao()) / ARQ_SENHA
    if not arq.is_file():
        return None
    d = json.loads(arq.read_text(encoding="utf-8"))
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", dada.encode(), bytes.fromhex(d["sal"]), 200000).hex(), d["resumo"])


def servir(porta: int | None = None, endereco: str | None = None, banco: Banco | None = None) -> ThreadingHTTPServer:
    porta = int(porta or os.environ.get("PHYSIS_ESTERMIC_PORTA") or 8704)
    endereco = endereco or os.environ.get("PHYSIS_ESTERMIC_ENDERECO") or "127.0.0.1"
    senha = os.environ.get("PHYSIS_ESTERMIC_SENHA") or None
    if not senha and (Path(mvmod.pasta_padrao()) / ARQ_SENHA).is_file():
        senha = True                                   # senha pelo arquivo com resumo (py -m physis_hub.estermic_servidor --senha)
    if endereco not in ("127.0.0.1", "localhost") and not senha:
        raise SystemExit("Para abrir na rede, defina PHYSIS_ESTERMIC_SENHA (setx PHYSIS_ESTERMIC_SENHA ...).")
    return ThreadingHTTPServer((endereco, porta), fabrica(banco or Banco(), senha))


if __name__ == "__main__":
    if "--senha" in sys.argv:
        import getpass
        n1 = getpass.getpass("Senha nova da Estermic (usuário physis, mínimo 12 caracteres): ")
        if n1 != getpass.getpass("Repita: ") or len(n1) < 12:
            print("Senhas diferentes ou curtas. Nada foi mudado."); sys.exit(1)
        print("Gravada em", definir_senha(n1), "(só o resumo). Religue a Estermic.")
        sys.exit(0)
    s = servir()
    print(f"Physis Estermic em http://{s.server_address[0]}:{s.server_address[1]}{PAGINA}")
    s.serve_forever()
