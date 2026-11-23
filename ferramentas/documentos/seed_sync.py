"""Sincroniza a semente embutida da Gestão ($y e as pessoas Fy) com sistema/gestao-fase2-tarefas.json."""
import json, re, io
from pathlib import Path
R = str(Path(__file__).resolve().parents[2] / "sistema") + "/"     # pasta do sistema, onde quer que esteja
G = R + "gestao-interna-physis.html"
g = io.open(G, encoding="utf-8", newline="").read()
pk = json.load(io.open(R + "gestao-fase2-tarefas.json", encoding="utf-8"))
T = pk["tabelas"]
proj = {p["projeto_id"]: p for p in T["projeto"]}
seed = []
for t in T["tarefa"]:
    ex = t.get("extras") or {}
    p = proj.get(t["projeto_id"], {})
    seed.append({"id": t["tarefa_id"], "pessoa": t["pessoa_id"], "h": t["horizonte"], "depende": t.get("depende_de"),
                 "projeto": ex.get("projeto_nome") or p.get("nome", ""), "projetoEn": (p.get("extras") or {}).get("nomeEn", ""),
                 "texto": t["titulo"], "textoEn": ex.get("tituloEn", "")})
m = re.search(r"\$y=(\[\{\"id\".*?\}\]),Fn=\[", g, re.S)
novo = json.dumps(seed, ensure_ascii=False, separators=(",", ":"))
g = g[:m.start(1)] + novo + g[m.end(1):]
# pessoas: quem aparece nas tarefas e ainda não está em Fy (papéis como "consultores", "adefinir-d21") entra no fim
fy = re.search(r"Fy=\[(.*?)\],", g, re.S)
tem = set(re.findall(r'\{id:"([^"]+)"', fy.group(1)))
pessoas = {p["pessoa_id"]: p for p in T["pessoa"]}
add = []
for pid in sorted({t["pessoa_id"] for t in T["tarefa"]} - tem):
    p = pessoas.get(pid, {"nome": pid, "idioma": "pt", "papel": "", "extras": {}})
    ex = p.get("extras") or {}
    add.append("{id:%s,nome:%s,lang:%s,papel:%s,papelEn:%s}" % tuple(json.dumps(x, ensure_ascii=False) for x in
               (pid, p.get("nome") or pid, p.get("idioma") or "pt", p.get("papel") or "", ex.get("papelEn") or "")))
if add:
    g = g[:fy.end(1)] + "," + ",".join(add) + g[fy.end(1):]
io.open(G, "w", encoding="utf-8", newline="").write(g)
print(len(seed), "tarefas;", "pessoas novas:", [a[4:a.find(",")] for a in add])
