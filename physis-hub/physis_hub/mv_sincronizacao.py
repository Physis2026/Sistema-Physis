"""Atualização automática entre as cópias dos módulos compartilhados (pedido da dona, 22/11/2026).

Regra: quando um original compartilhado muda (ex.: barra de preferências, painel Desenvolvimento), a melhoria vai para
todos os outros. Vale a versão COMMITADA mais recente entre os repositórios.
- Sistema Physis (oficial e teste), Instituto e InovaSTEM: automático COM TESTE ANTES. Copia o original, roda o
  sincronizar.py do repositório (que leva o original para todas as páginas) e os testes de cópia. Se passarem, faz commit
  local "Sincronização automática (M&A)". Se falharem, desfaz e cria alerta no M&A. Nunca faz push.
- Repositório com alterações em andamento (trabalho de outra sessão ou pessoa) fica de fora nesta rodada, sem misturar.
- Plataformas de clientes: NUNCA automático. Cria duas aprovações no M&A, a da Physis e a do cliente; só depois das duas
  a plataforma é remontada (montar_clientes.py), à mão.
"""
import subprocess
import sys
import time
from pathlib import Path

from .mv import MV

BASE = Path("C:/physis")
REPOS = {"Sistema Physis (oficial)": BASE / "physis-sistema", "Sistema Physis (teste)": BASE / "physis-teste",
         "Instituto Physis": BASE / "instituto-physis", "InovaSTEM (ramo inovastem)": BASE / "instituto-physis-inovastem"}
ORIGINAIS = ["sistema/physis-preferencias.js", "sistema/physis-desenvolvimento.js", "sistema/physis-modelador.js"]
TESTES = ["tests.test_preferencias", "tests.test_mv_traducao"]
PLATAFORMAS = Path.home() / "OneDrive - Physis Engineering" / "Documents" / "Sistema Physis" / "_versoes_teste" / "2026-11-20_plataformas_iniciais"


def _git(repo: Path, *a, entrada: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, input=entrada, timeout=120)


def _versao(repo: Path, caminho: str):
    """(data do último commit, conteúdo em HEAD) do original, ou None."""
    t = _git(repo, "log", "-1", "--format=%ct", "--", caminho).stdout.decode().strip()
    c = _git(repo, "show", f"HEAD:{caminho}")
    return (int(t), c.stdout) if t and c.returncode == 0 else None


def _testes(repo: Path) -> tuple[bool, str]:
    hub = repo / "physis-hub"
    ok, saida = True, []
    for t in TESTES:
        if not (hub / "tests" / (t.split(".")[1] + ".py")).exists():
            continue
        r = subprocess.run([sys.executable, "-W", "ignore", "-m", "unittest", t], cwd=hub, capture_output=True, timeout=900)
        txt = (r.stdout + r.stderr).decode("utf-8", "replace").strip().splitlines()
        saida.append(f"{t}: {txt[-1] if txt else r.returncode}")
        ok = ok and r.returncode == 0
    return ok, "; ".join(saida)


def rodar(mv: MV, aplicar: bool = True) -> dict:
    res = {"originais": {}, "repos": {}, "plataformas": [], "alertas": 0}
    # 1. versão mais recente de cada original
    novos = {}
    for cam in ORIGINAIS:
        vs = {n: _versao(r, cam) for n, r in REPOS.items() if r.exists()}
        vs = {n: v for n, v in vs.items() if v}
        if not vs:
            continue
        dono = max(vs, key=lambda n: vs[n][0])
        novos[cam] = vs[dono][1]
        res["originais"][cam] = {"fonte": dono, "commit": time.strftime("%Y-%m-%d %H:%M", time.localtime(vs[dono][0]))}
    # 2. cada repositório: copia, sincroniza, testa, commit ou desfaz
    for nome, repo in REPOS.items():
        if not repo.exists():
            continue
        if _git(repo, "status", "--porcelain").stdout.strip():
            res["repos"][nome] = "pulado: há alterações em andamento (nada misturado)"
            continue
        trocados = []
        for cam, cont in novos.items():
            alvo = repo / cam
            atual = alvo.read_bytes() if alvo.exists() else None
            if atual is None or atual.replace(b"\r\n", b"\n") != cont.replace(b"\r\n", b"\n"):
                trocados.append(cam)
                if aplicar:
                    alvo.parent.mkdir(parents=True, exist_ok=True)
                    alvo.write_bytes(cont)
        if not aplicar:
            res["repos"][nome] = f"{len(trocados)} original(is) a atualizar" if trocados else "em dia"
            continue
        sinc = repo / "ferramentas" / "sincronizar.py"
        if sinc.exists():
            subprocess.run([sys.executable, str(sinc)], cwd=repo, capture_output=True, timeout=600)
        demos = repo / "demos" / "gerar_demos.py"           # as demos levam cópias das páginas: geradas de novo
        if demos.exists():
            subprocess.run([sys.executable, str(demos)], cwd=repo, capture_output=True, timeout=600)
        mudou = _git(repo, "status", "--porcelain").stdout.decode().strip()
        if not mudou:
            res["repos"][nome] = "em dia"
            continue
        ok, txt = _testes(repo)
        if ok:
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "Sincronização automática (M&A): originais compartilhados e cópias nas páginas\n\n"
                 + "\n".join(f"- {c} (fonte: {res['originais'][c]['fonte']})" for c in trocados) + f"\n\nTestes: {txt}")
            res["repos"][nome] = f"atualizado e testado ({len(mudou.splitlines())} arquivo(s)); {txt}"
        else:
            _git(repo, "checkout", "--", ".")
            _git(repo, "clean", "-fdq", "--", *trocados) if trocados else None
            res["repos"][nome] = f"DESFEITO: testes falharam ({txt})"
            mv.alertar("sincronizacao", "testes_falharam", nome, "alerta", f"{nome}: sincronização automática desfeita porque os testes falharam",
                       f"Ver {txt}. Corrigir o original e deixar o bot tentar de novo na próxima hora.")
            res["alertas"] += 1
    # 3. plataformas de clientes: só com duas aprovações (Physis e cliente)
    if PLATAFORMAS.is_dir():
        for d in sorted(p for p in PLATAFORMAS.iterdir() if p.is_dir()):
            dif = []
            for c, cont in novos.items():
                ident = Path(c).stem                      # bloco embutido nas páginas: <script id="physis-preferencias">
                abre = f'<script id="{ident}">\n'
                orig = cont.decode("utf-8", "replace").replace("\r\n", "\n")
                for h in d.rglob("*.html"):
                    t = h.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
                    i = t.find(abre)
                    if i >= 0 and t[i + len(abre):t.find("</script>", i)] != orig:
                        dif.append(c)
                        break
            if not dif or not aplicar:
                if dif:
                    res["plataformas"].append({"cliente": d.name.replace("physis-", ""), "arquivos": dif, "situacao": "precisaria de 2 aprovações"})
                continue
            cli = d.name.replace("physis-", "")
            for quem, rot in (("physis", "1/2 aprovação da Physis"), ("cliente", "2/2 aprovação do cliente")):
                iid = f"ap-plat-{cli}-{quem}"
                if not mv.db.execute("SELECT 1 FROM mv_aprovacao WHERE id=?", (iid,)).fetchone():
                    mv.db.execute("INSERT INTO mv_aprovacao (id, item, grupo, prazo, onde, estado, nota, ordem, criado) VALUES (?,?,?,?,?,?,?,?,?)",
                                  (iid, f"Atualizar a plataforma {cli} com as melhorias de {', '.join(dif)} ({rot})", "Atualização de plataforma",
                                   "", str(d), "pendente", "Só remontar (montar_clientes.py) depois das duas aprovações", 90, time.time()))
            mv.db.commit()
            res["plataformas"].append({"cliente": cli, "arquivos": dif, "situacao": "aguarda 2 aprovações (Physis e cliente)"})
    return res
