#!/usr/bin/env python3
r"""Backup completo do servidor Physis (23/11/2026) · base para montar o Acer (Linux).

    cd C:\physis\physis-ma-20261122-1bd599e
    py ferramentas\backup_completo.py                 # cria C:\physis\backup-completo-AAAAMMDD-HHMM
    py ferramentas\backup_completo.py --sem-documentos  # sem a cópia das pastas do OneDrive (mais rápido)

Só LÊ o que está em uso; escreve apenas na pasta nova. Leva:
  1 codigo/     todos os repositórios Git de C:\physis (todos os ramos, num .bundle cada) + arquivos ainda não salvos
  2 bancos/     cópia consistente de cada banco SQLite (M&A, Gestão/site, Casa, InovaSTEM, Hub) + conferência de integridade
  3 sites/      as instalações montadas em C:\physis\clientes (sem os bancos, que já estão em bancos/)
  4 documentos/ as pastas do OneDrive que os bots leem (Sistema, Casa, Instituto, GSA, Estermic, Marketing)
  5 config/     agenda do Windows (XML), variáveis PHYSIS_* (senhas mascaradas), Caddy
  MANIFESTO.md (o que tem, tamanhos, SHA256, integridade) e RESTAURAR-NO-ACER.md (passo a passo Linux)
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "physis-hub"))
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass
from physis_hub import mv_bots, mv_repositorios  # noqa: E402
from physis_hub.mv import pasta_padrao  # noqa: E402

BASE = RAIZ.parent                                   # C:\physis
SEGREDO = ("SENHA", "TOKEN", "CHAVE", "SECRET", "KEY", "PASS")
manifesto: list[str] = []
problemas: list[str] = []


def diz(t: str) -> None:
    print(t, flush=True)
    manifesto.append(t)


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def tamanho(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else (p.stat().st_size if p.exists() else 0)


def mb(n: int) -> str:
    return f"{n / 1048576:.1f} MB"


def git(pasta: Path, *a: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(pasta), *a], capture_output=True, text=True, encoding="utf-8", errors="replace")


def codigo(dest: Path) -> None:
    diz("\n## 1. Código (repositórios Git)")
    (dest / "codigo").mkdir(parents=True)
    for rep in sorted(p for p in BASE.iterdir() if (p / ".git").exists() and not p.name.startswith("backup")):
        b = dest / "codigo" / f"{rep.name}.bundle"
        r = git(rep, "bundle", "create", str(b), "--all")
        if r.returncode != 0 or not b.is_file():
            problemas.append(f"bundle de {rep.name}: {r.stderr.strip()[:200]}")
            continue
        ok = git(rep, "bundle", "verify", str(b)).returncode == 0
        ramos = git(rep, "branch", "--format=%(refname:short) %(objectname:short)").stdout.strip().replace("\n", ", ")
        nao = [l[3:].strip().strip('"') for l in git(rep, "status", "--porcelain").stdout.splitlines()]
        if nao:
            pasta_ns = dest / "codigo" / f"{rep.name}-nao-salvos"
            for rel in nao:
                o = rep / rel
                if o.is_file():
                    (pasta_ns / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(o, pasta_ns / rel)
        diz(f"- {rep.name}: {mb(b.stat().st_size)} · verificado: {'sim' if ok else 'NÃO'} · ramos: {ramos}"
            + (f" · {len(nao)} arquivo(s) não salvos copiados" if nao else ""))
        if not ok:
            problemas.append(f"bundle de {rep.name} não passou na verificação")


def bancos(dest: Path) -> None:
    diz("\n## 2. Bancos de dados")
    achados = list(pasta_padrao().glob("*.db"))
    cli = BASE / "clientes"
    if cli.is_dir():
        achados += [p for p in cli.rglob("*.db")]
    achados += [p for p in (RAIZ / "physis-hub").glob("*.db")]
    for db in sorted(set(achados)):
        if db.name.startswith("backup-"):
            continue
        rel = db.relative_to(BASE) if str(db).startswith(str(BASE)) else Path(db.name)
        alvo = dest / "bancos" / rel
        alvo.parent.mkdir(parents=True, exist_ok=True)
        try:
            o = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=30)
            d = sqlite3.connect(alvo)
            o.backup(d)
            res = d.execute("PRAGMA integrity_check").fetchone()[0]
            d.close()
            o.close()
        except sqlite3.Error as e:
            res = f"erro: {e}"
        diz(f"- {rel}: {mb(alvo.stat().st_size) if alvo.exists() else '-'} · integridade: {res} · SHA256 {sha(alvo)[:16] if alvo.exists() else '-'}")
        if res != "ok":
            problemas.append(f"banco {rel}: {res}")


def sites(dest: Path) -> None:
    diz("\n## 3. Sites montados (C:\\physis\\clientes)")
    cli = BASE / "clientes"
    if not cli.is_dir():
        diz("- (nenhum)")
        return
    ign = shutil.ignore_patterns("*.db", "*.db-wal", "*.db-shm", "__pycache__")
    for s in sorted(p for p in cli.iterdir() if p.is_dir()):
        shutil.copytree(s, dest / "sites" / s.name, ignore=ign)
        diz(f"- {s.name}: {mb(tamanho(dest / 'sites' / s.name))}")


def documentos(dest: Path) -> None:
    diz("\n## 4. Documentos (OneDrive)")
    for pasta in mv_bots.pastas_documentos() + mv_repositorios.caminhos_existentes():
        if not pasta.is_dir():
            diz(f"- {pasta.name}: pasta não encontrada")
            continue
        n, falhas = 0, []
        for f in pasta.rglob("*"):
            if not f.is_file() or ".git" in f.parts:
                continue
            alvo = dest / "documentos" / pasta.name / f.relative_to(pasta)
            try:
                alvo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, alvo)
                n += 1
            except OSError as e:
                falhas.append(f"{f.name} ({e.__class__.__name__})")
        diz(f"- {pasta.name}: {n} arquivo(s), {mb(tamanho(dest / 'documentos' / pasta.name))}"
            + (f" · {len(falhas)} não copiados (só online?): {', '.join(falhas[:5])}" if falhas else ""))
        if falhas:
            problemas.append(f"{pasta.name}: {len(falhas)} arquivo(s) não copiados")


def config(dest: Path) -> None:
    diz("\n## 5. Configuração")
    c = dest / "config"
    (c / "agenda").mkdir(parents=True)
    if os.name == "nt":
        lst = subprocess.run(["schtasks", "/Query", "/FO", "CSV", "/NH"], capture_output=True, text=True, errors="replace").stdout
        nomes = sorted({l.split('","')[0].strip('"') for l in lst.splitlines() if "\\Physis" in l})
        for n in nomes:
            x = subprocess.run(["schtasks", "/Query", "/TN", n, "/XML"], capture_output=True, text=True, errors="replace").stdout
            (c / "agenda" / (n.strip("\\").replace("\\", "__") + ".xml")).write_text(x, encoding="utf-8")
        diz(f"- agenda: {len(nomes)} tarefa(s) exportadas")
    var = [f"{k}={'***' if any(s in k.upper() for s in SEGREDO) else v}" for k, v in sorted(os.environ.items()) if k.startswith("PHYSIS_")]
    (c / "variaveis.txt").write_text("\n".join(var) + "\n", encoding="utf-8")
    diz(f"- variáveis PHYSIS_*: {len(var)} (senhas e chaves mascaradas: anote-as à parte)")
    for p in [Path.home() / "AppData" / "Local" / "PhysisMarketing" / "caddy" / "Caddyfile", BASE / "caddy-teste" / "Caddyfile-teste-local"]:
        if p.is_file():
            (c / "caddy").mkdir(exist_ok=True)
            shutil.copy2(p, c / "caddy" / p.name)
    diz("- Caddy: " + (", ".join(x.name for x in (c / "caddy").glob("*")) if (c / "caddy").is_dir() else "nenhum arquivo"))


RESTAURAR = """# Restaurar no Acer (Linux) · rascunho de 23/11/2026 [CONFERIR na instalação]

1. Instalar: git, python3 (3.10+), caddy.
2. Código: para cada arquivo em codigo/*.bundle:
       git clone codigo/physis-ma-20261122-1bd599e.bundle /srv/physis/sistema
   (troque o nome da pasta; o ramo main é o que roda; os ramos teste/* ficam guardados)
   Arquivos "nao-salvos": copiar por cima da pasta clonada correspondente.
3. Bancos: copiar bancos/dados/*.db para /srv/physis/dados/ e definir PHYSIS_MV_DADOS=/srv/physis/dados.
   Bancos dos sites: bancos/clientes/<site>/*.db para dentro de cada site em /srv/physis/clientes/<site>/.
4. Sites: copiar sites/* para /srv/physis/clientes/.
5. Documentos: copiar documentos/* para a pasta de documentos do Acer e definir PHYSIS_DOCS.
6. Serviços: um serviço systemd por site (PHYSIS_PORTA 8700/8701/8702/8703, PHYSIS_ENDERECO=127.0.0.1,
   PHYSIS_PROXY_CONFIAVEL=127.0.0.1,::1, PHYSIS_EXPOSTO=1, PHYSIS_URL_PUBLICA) e um para o M&A (mv_cli servir);
   agenda dos bots com timers do systemd (equivalentes às tarefas em config/agenda).
7. Caddy: config/caddy/Caddyfile em /etc/caddy/Caddyfile; DNS apontando para o IP do Acer.
8. Rodar o teste zero (ferramentas/teste_zero.py) no Acer antes de liberar a equipe.
"""


def main(argv: list[str]) -> int:
    dest = BASE / f"backup-completo-{time.strftime('%Y%m%d-%H%M')}"
    if "--destino" in argv:
        dest = Path(argv[argv.index("--destino") + 1])
    dest.mkdir(parents=True, exist_ok=False)
    diz(f"# Backup completo do servidor Physis · {time.strftime('%d/%m/%Y %H:%M')}")
    diz(f"Pasta: {dest}")
    codigo(dest)
    bancos(dest)
    sites(dest)
    if "--sem-documentos" not in argv:
        documentos(dest)
    config(dest)
    (dest / "RESTAURAR-NO-ACER.md").write_text(RESTAURAR, encoding="utf-8")
    diz(f"\n## Total: {mb(tamanho(dest))}")
    diz("## Resultado: " + ("TUDO OK ✅" if not problemas else "COM PENDÊNCIAS"))
    for p in problemas:
        diz(f"- [ ] {p}")
    (dest / "MANIFESTO.md").write_text("\n".join(manifesto) + "\n", encoding="utf-8")
    return 0 if not problemas else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
