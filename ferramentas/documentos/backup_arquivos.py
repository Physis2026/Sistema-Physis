import datetime, shutil, sys, zipfile
from pathlib import Path
import os  # noqa: E402
RAIZ = Path(__file__).resolve().parents[2]          # pasta do sistema, onde quer que esteja
DOCS = Path(os.environ.get("PHYSIS_DOCS") or (Path.home() / "OneDrive - Physis Engineering" / "Documents")) / "Sistema Physis"
FORA = {".git", "__pycache__", "node_modules", "www", "_backup_git", "_backup_arquivos", "sistema_physis_fase1", "sistema_physis_ep_final",
        "_versoes_oficiais", "_versoes_teste"}   # versões congeladas já têm a sua própria cópia
# Backup só da Physis Engineering (decisão de 18/11/2026): nada do Instituto Physis, que tem plataforma e backup próprios.
NOMES_FORA = ("instituto", "physis-3d", "physis_3d", "impressao3d")
EXT_FORA = {".db", ".db-wal", ".db-shm", ".env", ".pfx", ".jks", ".keystore", ".pyc"}
destino = DOCS / "_backup_arquivos"
destino.mkdir(exist_ok=True)
carimbo = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
def juntar(z, base, prefixo):
    n = 0
    for p in base.rglob("*"):
        rel = p.relative_to(base)
        if any(parte in FORA for parte in rel.parts) or not p.is_file() or p.suffix.lower() in EXT_FORA or p.name.endswith(".env") \
                or any(n in parte.lower() for parte in rel.parts for n in NOMES_FORA):
            continue
        z.write(p, f"{prefixo}/{rel.as_posix()}"); n += 1
    return n
arq = destino / f"sistema-physis-arquivos-{carimbo}.zip"
with zipfile.ZipFile(arq, "w", zipfile.ZIP_DEFLATED) as z:
    a = juntar(z, RAIZ, "codigo")
    b = juntar(z, DOCS, "documentos")
print(arq, a, "arquivos de código,", b, "documentos,", round(arq.stat().st_size / 2**20, 1), "MB")
# sempre uma versão também na pasta Casa Physis, com o Physis M&V atualizado (decisão de 18/11/2026)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import salvar_casa_physis  # noqa: E402
salvar_casa_physis.salvar([arq])
