"""Bot cursos (22/11/2026): mapeia caminhos de cursos nos documentos da Physis, para a plataforma de cursos integrada
(Instituto Physis, Physis Engineering e InovaSTEM; a InovaSTEM é plataforma própria e atende várias frentes).

- Usa a IA Physis (índice próprio, sem terceiros) para achar os temas que aparecem em 2+ documentos de cada plataforma.
- Cada tema novo vira um pedido "Potencial de curso" para aprovação (nada é publicado sozinho).
- Rechecagem automática: quando documentos novos são compartilhados (ou mudam), o índice muda e o mapa é refeito.
- As trilhas começam em 30/11/2026 (decisão da dona). Até lá, só mapeamento; depois, o bot acervo propõe materiais
  para as trilhas aprovadas (trilhas.json).
Saída: Markdown e JSON em PHYSIS_MV_SAIDA/cursos (o JSON é o que a plataforma de cursos vai ler).
"""
from __future__ import annotations

import json
import os
import time
from datetime import date
from pathlib import Path

from . import mv as mvmod
from .ia_physis import IAPhysis, RAIZ_REPO, fontes_padrao

INICIO_TRILHAS = date(2026, 11, 30)
ESQUEMA = """CREATE TABLE IF NOT EXISTS mv_curso (plataforma TEXT NOT NULL, tema TEXT NOT NULL, arquivos TEXT NOT NULL,
  n INTEGER NOT NULL, nota REAL NOT NULL, primeiro REAL NOT NULL, visto REAL NOT NULL, PRIMARY KEY (plataforma, tema));"""


def plataformas() -> dict[str, list[Path]]:
    """Pastas de cada plataforma. PHYSIS_CURSOS_PASTAS (JSON {"plataforma": ["pasta", ...]}) substitui o padrão."""
    from . import mv_bots
    env = os.environ.get("PHYSIS_CURSOS_PASTAS", "").strip()
    if env:
        return {k: [Path(x) for x in v] for k, v in json.loads(env).items()}
    d = mv_bots.DOCS
    return {"Instituto Physis": [d / "Instituto Physis"],
            "Physis Engineering": [d / "Sistema Physis", RAIZ_REPO / "physis-hub" / "docs"],
            "InovaSTEM": [d / "Instituto Physis" / "InovaSTEM", d / "InovaSTEM"]}


def bot_cursos(mv, ia: IAPhysis | None = None, hoje: date | None = None, saida: Path | None = None) -> dict:
    from . import mv_bots, mv_comandos
    inicio = mv.nova_rodada()
    hoje = hoje or mvmod.HOJE()
    ia = ia or IAPhysis()
    plats = plataformas()
    grupos = fontes_padrao()
    grupos["cursos"] = [p for ps in plats.values() for p in ps]
    idx = ia.indexar(grupos)
    mv.db.execute(ESQUEMA)
    ult = mv.db.execute("SELECT MAX(fim) FROM mv_execucao WHERE bot='cursos' AND erro=''").fetchone()[0]
    if idx["atualizados"] == 0 and idx["removidos"] == 0 and ult and time.time() - ult < 7 * 86400:   # versão enxuta
        r = {"pulado": "nenhum documento novo ou alterado", "indice": {k: idx[k] for k in ("arquivos", "trechos")}}
        mv.registrar_execucao("cursos", inicio, json.dumps(r, ensure_ascii=False))
        return r
    cmd = mv_comandos.Comandos(mv)
    mapa, novos = {}, 0
    for nome, pastas in plats.items():
        existentes = [p for p in pastas if p.exists()]
        if not existentes:
            mv.alertar("cursos", "sem_pasta", nome, "info", f"{nome}: nenhuma pasta de documentos encontrada ({', '.join(map(str, pastas))})",
                       "Compartilhar os documentos nessa pasta ou definir PHYSIS_CURSOS_PASTAS; o bot rechecará sozinho")
            mapa[nome] = []
            continue
        temas = ia.temas([str(p) for p in existentes], n=12, min_docs=2)
        mapa[nome] = temas
        for t in temas:
            ant = mv.db.execute("SELECT n FROM mv_curso WHERE plataforma=? AND tema=?", (nome, t["tema"])).fetchone()
            agora = time.time()
            if not ant:
                novos += 1
                cmd._pedido("cursos", f"Potencial de curso · {nome}: {t['tema']}", "", "rascunho",
                            f"Plataforma: {nome}\nTema encontrado em {t['n_arquivos']} documento(s):\n- " + "\n- ".join(t["arquivos"][:12])
                            + "\n\nAprovar = a equipe avalia o curso (nome, público e conteúdo são decididos por pessoas).", origem="cursos")
                mv.db.execute("INSERT INTO mv_curso VALUES (?,?,?,?,?,?,?)", (nome, t["tema"], json.dumps(t["arquivos"]), t["n_arquivos"],
                                                                         t["nota"], agora, agora))
            else:
                mv.db.execute("UPDATE mv_curso SET arquivos=?, n=?, nota=?, visto=? WHERE plataforma=? AND tema=?",
                              (json.dumps(t["arquivos"]), t["n_arquivos"], t["nota"], agora, nome, t["tema"]))
    mv.db.commit()
    fase = "mapeamento (trilhas começam em 30/11/2026)" if hoje < INICIO_TRILHAS else "trilhas ativas: o bot acervo propõe materiais"
    pasta = Path(saida or (mv_bots.SAIDA / "cursos"))
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "mapa-de-cursos.json").write_text(json.dumps({"gerado": hoje.isoformat(), "fase": fase, "plataformas": mapa},
                                                          ensure_ascii=False, indent=1), encoding="utf-8")
    md = [f"# Mapa de potenciais cursos · {hoje.strftime('%d/%m/%Y')}", "", f"Fase: **{fase}**. Temas tirados dos documentos (2+ arquivos); "
          "nome, público e conteúdo dos cursos são decididos pela equipe.", ""]
    for nome, temas in mapa.items():
        md += [f"## {nome}", ""]
        if not temas:
            md += ["_Sem documentos compartilhados ainda._", ""]
            continue
        md += ["| Tema | Documentos | Exemplos |", "|---|---|---|"]
        md += [f"| {t['tema']} | {t['n_arquivos']} | {', '.join(Path(a).name for a in t['arquivos'][:3])} |" for t in temas]
        md.append("")
    (pasta / "mapa-de-cursos.md").write_text("\n".join(md), encoding="utf-8")
    r = {"fase": fase, "indice": {k: idx[k] for k in ("arquivos", "trechos", "atualizados")}, "temas_novos": novos,
         "temas": {k: len(v) for k, v in mapa.items()}, "arquivo": str(pasta / "mapa-de-cursos.md")}
    mv.fechar_alertas_nao_vistos("cursos", inicio)
    mv.registrar_execucao("cursos", inicio, json.dumps(r, ensure_ascii=False))
    return r
