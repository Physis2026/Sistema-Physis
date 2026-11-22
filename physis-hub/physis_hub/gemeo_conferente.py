"""Gêmeo digital · conferente automático com aprendizado contínuo (versão de TESTE, 22/11/2026).

    python -m physis_hub.gemeo_conferente ciclo      [--semente ARQ.json] [--limite 5]
    python -m physis_hub.gemeo_conferente relatorio
    python -m physis_hub.gemeo_conferente corrigir ID OPCAO [--nota TEXTO]

Pedido da dona (22/11/2026): o raciocínio de conferência que hoje é feito à mão (divergência entre fontes, peça abaixo
do terreno, soma das partes, elemento sem área) passa a ser feito pelo sistema, aprendendo com cada resposta e cada
correção (melhoria contínua).

O ciclo (pode rodar sozinho pelos programados do M&A):
1. detectar(projeto): acha os pontos a conferir na semente, cada um com opções fechadas (nunca um número novo: só
   escolher entre valores que já têm fonte, regra 1) e atributos explicáveis;
2. sugerir(modelo, achado): o modelo aprendido diz qual opção a dona tende a escolher e com que confiança; sem
   exemplos suficientes, vale a regra inicial (a decisão R1-1: fonte única planilha 20 + geometria da 03);
3. publicar(...): os achados novos viram perguntas no M&A (uma vez só, M&A centraliza), com a sugestão em primeiro;
4. sincronizar_respostas(...) e corrigir(...): cada resposta ou correção vira exemplo de treino;
5. treinar(exemplos): regressão logística um-contra-os-outros por tipo de achado (aprendizado.logistica, a mesma
   matemática leve do hub), versão nova a cada treino, com acerto medido (deixa-um-de-fora) e explicação em português.

Nada é aplicado sozinho: o sistema sugere; quem decide é a dona (a política de aplicação automática é decisão dela).
Os exemplos iniciais são as decisões reais já registradas no M&A (pg:…), não números inventados.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from . import aprendizado as A
from . import gemeo as G

ORIGEM = "casa-gemeo-digital"
APLICA = ["casa", "sistema-physis", "m&a"]
MIN_EXEMPLOS = 3            # por tipo de achado, para usar o modelo em vez da regra inicial
LIMITE_PUBLICAR = 5         # perguntas novas por ciclo (as mais importantes primeiro)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS gemeo_achado (
  id TEXT PRIMARY KEY, tipo TEXT NOT NULL, chave TEXT NOT NULL, descricao TEXT NOT NULL, opcoes TEXT NOT NULL,
  atributos TEXT NOT NULL, prioridade REAL NOT NULL DEFAULT 0, sugestao TEXT, confianca REAL, modelo_versao INTEGER,
  pergunta_id TEXT, escolha TEXT, origem_resposta TEXT, nota TEXT NOT NULL DEFAULT '', criado REAL NOT NULL,
  respondido REAL);
CREATE TABLE IF NOT EXISTS gemeo_modelo (
  versao INTEGER PRIMARY KEY, treinado_em REAL NOT NULL, n INTEGER NOT NULL, metricas TEXT NOT NULL,
  parametros TEXT NOT NULL);
"""

# opções fechadas por tipo de achado (chave → rótulo); a primeira é a regra inicial
OPCOES = {
    "divergencia": [("atual", "manter o valor da fonte única (planilha 20 / geometria da 03)"),
                    ("alternativa", "usar o valor alternativo (outra fonte do acervo)"),
                    ("marcador", "deixar vazio ou [CONFERIR] até uma fonte nova")],
    "terreno": [("aguardar", "terreno do modelo é aproximado: aguardar a topografia final"),
                ("intencional", "é corte ou plataforma intencional (registrar)"),
                ("erro_cota", "a cota está errada: corrigir na planilha 03")],
    "sem_area": [("referencia", "manter como referência (linha desativada ou de cálculo)"),
                 ("remover", "tirar da semente")],
    "soma": [("conferir_fonte", "a soma não fecha: conferir a planilha de origem"),
             ("aceitar", "aceitar a diferença (arredondamento)")],
}
TIPOS_FONTE = ("planilha20", "planilha03", "planilha18", "pdf", "doc", "calculo", "decisao", "outro")
CATEGORIAS = ("lote", "areas", "programa", "casa1", "energia", "agua", "esgoto", "drenagem", "alturas", "telhados",
              "implantacao", "outro")
CATS_PLANEJADOR = ("ed", "pav", "agua", "inf", "perm")


def _id(tipo, chave):
    return "ga:" + hashlib.sha256(f"{tipo}|{chave}".encode()).hexdigest()[:12]


def tipo_fonte(f):
    s = str(f or "").lower()
    for pre, t in (("planilha 20", "planilha20"), ("planilha 03", "planilha03"), ("planilha 18", "planilha18"),
                   ("03 › ", "planilha03"), ("20 › ", "planilha20")):
        if s.startswith(pre):
            return t
    if ".pdf" in s or "prancha" in s:
        return "pdf"
    if s.startswith("doc ") or "doc 47" in s:
        return "doc"
    if s.startswith("calculad"):
        return "calculo"
    if "decisão" in s or "pg:" in s:
        return "decisao"
    return "outro"


def categoria(caminho):
    c = caminho.split(".")[0]
    return c if c in CATEGORIAS else "outro"


# ---------------------------------------------------------------- 1. detectar

def detectar(projeto, cota_terreno=None):
    """Achados da semente. `cota_terreno(x, y)`: função do terreno (padrão: a malha do IFC do gêmeo)."""
    from . import gemeo_ifc as GI
    g = projeto["gemeo"]
    out = []
    for cam, d in g["fonte_por_valor"].items():
        c = d.get("conferir")
        if not c:
            continue
        alt = c["alternativas"][0]
        num = isinstance(d.get("valor"), (int, float)) and isinstance(alt.get("valor"), (int, float))
        dif = abs(d["valor"] - alt["valor"]) / max(abs(d["valor"]), abs(alt["valor"]), 1e-9) if num else 0.0
        out.append(_achado("divergencia", cam, f"{c['divergencia']} · {cam}: {d.get('valor')} ({d['fonte']}) × "
                                               f"{alt.get('valor')} ({alt['fonte']})", {
            "fonte_atual": tipo_fonte(d["fonte"]), "fonte_alt": tipo_fonte(alt["fonte"]), "categoria": categoria(cam),
            "atual_vazio": d.get("valor") is None, "alt_texto": not isinstance(alt.get("valor"), (int, float)),
            "dif_rel": round(min(dif, 1.0), 4), "divergencia": c["divergencia"]}, prioridade=3 + min(dif, 1.0)))
    if cota_terreno is None:
        v, tri = GI.malha_terreno(projeto)
        cota_terreno = lambda x, y: GI.cota_no_terreno(v, tri, x, y)
    itens = {i["id"]: i for i in projeto["itens"]}
    from .gemeo_importar import tipo_planejador
    from .gemeo_versoes import CAT_PLANEJADOR
    for k, e in g["elementos"].items():
        it = itens[e["item_id"]]
        if e["sem_area"]:
            desc = str(e.get("descricao") or "")
            out.append(_achado("sem_area", k, f"{k}: linha da 03 com 0,01 m e área 0 ({desc[:80] or 'sem descrição'})", {
                "nao_cabe": "não cabe" in desc, "desativada": "desativad" in desc, "calc": k.startswith("calc_"),
                "sem_descricao": not desc}, prioridade=0.5))
            continue
        if e.get("piso_topo_m") is None:
            continue
        rel = GI.relacao_terreno(e, e["piso_topo_m"], cota_terreno(it["x"], it["y"]))
        if "[CONFERIR" in rel:
            dz = e["piso_topo_m"] - cota_terreno(it["x"], it["y"])
            cat = CAT_PLANEJADOR.get(tipo_planejador(k), "perm")
            out.append(_achado("terreno", k, f"{k}: {rel}", {
                "dz_abs": round(abs(dz), 2), "tem_corte": (e.get("corte_m3") or 0) > 0,
                "pilares": e.get("pilar_max_m") is not None, "cat": cat,
                "enterrado_no_texto": "enterr" in str(e.get("descricao") or "").lower()}, prioridade=1 + min(abs(dz), 5) / 5))
    fv = g["fonte_por_valor"]
    for campo in ("construida_m2", "projecao_m2"):
        partes = [d["valor"] for p, d in fv.items() if p.startswith("areas.quadro.") and p.endswith(campo) and ".total." not in p]
        tot = fv.get(f"areas.quadro.total.{campo}", {}).get("valor")
        if partes and tot is not None and abs(sum(partes) - tot) > 0.05:
            out.append(_achado("soma", f"areas.quadro.{campo}", f"quadro de áreas: soma {sum(partes):.2f} × total {tot}",
                               {"dif_abs": round(abs(sum(partes) - tot), 2)}, prioridade=2))
    return sorted(out, key=lambda a: -a["prioridade"])


def _achado(tipo, chave, descricao, atributos, prioridade=1.0):
    return {"id": _id(tipo, chave), "tipo": tipo, "chave": chave, "descricao": descricao, "atributos": atributos,
            "opcoes": [k for k, _ in OPCOES[tipo]], "prioridade": round(prioridade, 3)}


# ---------------------------------------------------------------- 2. atributos → vetor

def vetor(achado):
    a, t = achado["atributos"], achado["tipo"]
    if t == "divergencia":
        return ([1.0 if a["fonte_atual"] == f else 0.0 for f in TIPOS_FONTE] + [1.0 if a["fonte_alt"] == f else 0.0 for f in TIPOS_FONTE]
                + [1.0 if a["categoria"] == c else 0.0 for c in CATEGORIAS] + [float(a["atual_vazio"]), float(a["alt_texto"]), a["dif_rel"]])
    if t == "terreno":
        return [a["dz_abs"], float(a["tem_corte"]), float(a["pilares"]), float(a["enterrado_no_texto"])] + [
            1.0 if a["cat"] == c else 0.0 for c in CATS_PLANEJADOR]
    if t == "sem_area":
        return [float(a["nao_cabe"]), float(a["desativada"]), float(a["calc"]), float(a["sem_descricao"])]
    return [a.get("dif_abs", 0.0)]


# ---------------------------------------------------------------- 3. treinar e sugerir

def _treinar_tipo(exs):
    classes = sorted({e["escolha"] for e in exs})
    xs = [vetor(e) for e in exs]
    mu, sd = A.padronizar(xs)
    X = [A.aplicar_padrao(r, mu, sd) for r in xs]
    pesos = {c: A.logistica(X, [1 if e["escolha"] == c else 0 for e in exs], l2=0.1, iteracoes=400) for c in classes}
    return {"classes": classes, "mu": mu, "sd": sd, "pesos": pesos}


def _probs(m, achado):
    x = A.aplicar_padrao(vetor(achado), m["mu"], m["sd"])
    ps = {c: A.sigmoide(sum(w * v for w, v in zip(m["pesos"][c], x))) for c in m["classes"]}
    s = sum(ps.values()) or 1.0
    return {c: p / s for c, p in ps.items()}


def treinar(exemplos, agora=None):
    """Um modelo por tipo de achado (com ≥ MIN_EXEMPLOS e duas escolhas diferentes, senão frequência ou regra)."""
    por_tipo = {}
    for e in exemplos:
        por_tipo.setdefault(e["tipo"], []).append(e)
    modelos, metricas = {}, {}
    for t, exs in por_tipo.items():
        classes = {e["escolha"] for e in exs}
        if len(exs) >= MIN_EXEMPLOS and len(classes) >= 2:
            modelos[t] = {"modo": "logistica", **_treinar_tipo(exs)}
            acertos = 0  # deixa-um-de-fora: treina sem o exemplo e vê se acerta
            for i, e in enumerate(exs):
                resto = exs[:i] + exs[i + 1:]
                if len({r["escolha"] for r in resto}) < 2:
                    acertos += int(max(classes, key=lambda c: sum(r["escolha"] == c for r in resto)) == e["escolha"])
                    continue
                p = _probs(_treinar_tipo(resto), e)
                acertos += int(max(p, key=p.get) == e["escolha"])
            metricas[t] = {"n": len(exs), "acerto_loo": round(acertos / len(exs), 3)}
        else:
            freq = {c: sum(e["escolha"] == c for e in exs) for c in classes}
            modelos[t] = {"modo": "frequencia", "freq": freq}
            metricas[t] = {"n": len(exs), "acerto_loo": None}
    return {"treinado_em": agora if agora is not None else time.time(), "n": len(exemplos), "modelos": modelos,
            "metricas": metricas}


def sugerir(modelo, achado):
    """(opção, confiança, explicação). Nunca sai das opções fechadas do achado."""
    m = (modelo or {}).get("modelos", {}).get(achado["tipo"])
    ops = achado["opcoes"]
    if m and m["modo"] == "logistica":
        p = _probs(m, achado)
        p = {c: v for c, v in p.items() if c in ops} or {ops[0]: 1.0}
        c = max(p, key=p.get)
        met = modelo["metricas"][achado["tipo"]]
        return c, round(p[c], 3), (f"aprendido com {met['n']} decisões da dona neste tipo (acerto {met['acerto_loo']:.0%} "
                                   "deixando cada uma de fora)")
    if m and m["modo"] == "frequencia":
        tot = sum(m["freq"].values())
        c = max(m["freq"], key=m["freq"].get)
        if c in ops:
            return c, round(m["freq"][c] / tot, 3), f"a dona escolheu isto {m['freq'][c]} de {tot} vezes neste tipo"
    return ops[0], 0.5, "regra inicial (ainda sem decisões suficientes neste tipo): fonte única, doc 47 §7"


def explicar(modelo):
    """Texto em português: o que o sistema aprendeu até agora."""
    if not modelo or not modelo.get("n"):
        return "Ainda sem decisões registradas: o conferente usa as regras iniciais (fonte única planilha 20 + 03)."
    linhas = [f"Conferente treinado com {modelo['n']} decisões da dona."]
    for t, met in sorted(modelo["metricas"].items()):
        m = modelo["modelos"][t]
        if m["modo"] == "logistica":
            linhas.append(f"· {t}: {met['n']} decisões; acerto {met['acerto_loo']:.0%} deixando cada uma de fora; "
                          f"escolhas vistas: {', '.join(m['classes'])}.")
        else:
            linhas.append(f"· {t}: {met['n']} decisões ({', '.join(f'{c} {n}×' for c, n in m['freq'].items())}); "
                          "poucas para um modelo, vale a frequência.")
    return "\n".join(linhas)


# ---------------------------------------------------------------- exemplos iniciais: decisões reais do M&A

def exemplos_iniciais(projeto):
    """As decisões já tomadas pela dona sobre a semente (21–22/11/2026), como exemplos de treino. Cada uma aponta a
    pergunta do M&A de onde veio; o achado é recalculado da semente, só a escolha vem da decisão."""
    decisoes = {  # caminho com [CONFERIR] → (escolha, pergunta do M&A)
        "lote.area_m2": ("atual", "pg:178d054ba7c7"), "areas.projecao_m2": ("atual", "pg:178d054ba7c7"),
        "areas.projecao_pct": ("atual", "pg:178d054ba7c7"), "energia.fv.placas": ("atual", "pg:178d054ba7c7"),
        "energia.fv.kwp": ("atual", "pg:178d054ba7c7"), "programa.lofts": ("atual", "pg:178d054ba7c7"),
        "casa1.cota_piso_m": ("atual", "pg:178d054ba7c7"), "energia.consumo_kwh_mes": ("marcador", "pg:310a1c0db09d"),
        "telhados.inclinacao_graus": ("alternativa", "pg:74fabc0568d2"), "alturas.pavimento_m": ("marcador", "pg:58d2e859f36a"),
    }
    out = []
    for a in detectar(projeto):
        if a["tipo"] == "divergencia" and a["chave"] in decisoes:
            esc, pg = decisoes[a["chave"]]
            out.append({**a, "escolha": esc, "origem_resposta": "semente", "nota": f"decisão registrada em {pg}"})
    return out


# ---------------------------------------------------------------- banco (M&A) e ciclo

def _garantir(db):
    db.executescript(ESQUEMA)
    db.commit()


def exemplos_do_banco(db):
    _garantir(db)
    out = []
    for r in db.execute("SELECT * FROM gemeo_achado WHERE escolha IS NOT NULL"):
        out.append({"id": r["id"], "tipo": r["tipo"], "chave": r["chave"], "atributos": json.loads(r["atributos"]),
                    "opcoes": json.loads(r["opcoes"]), "escolha": r["escolha"], "origem_resposta": r["origem_resposta"]})
    return out


def salvar_modelo(db, modelo):
    _garantir(db)
    v = (db.execute("SELECT MAX(versao) FROM gemeo_modelo").fetchone()[0] or 0) + 1
    db.execute("INSERT INTO gemeo_modelo VALUES (?,?,?,?,?)", (v, modelo["treinado_em"], modelo["n"],
                                                               json.dumps(modelo["metricas"]), json.dumps(modelo["modelos"])))
    db.commit()
    return v


def ultimo_modelo(db):
    _garantir(db)
    r = db.execute("SELECT * FROM gemeo_modelo ORDER BY versao DESC LIMIT 1").fetchone()
    if not r:
        return None, 0
    return {"treinado_em": r["treinado_em"], "n": r["n"], "metricas": json.loads(r["metricas"]),
            "modelos": json.loads(r["parametros"])}, r["versao"]


def _rotulos(achado, sug, conf):
    rot = dict(OPCOES[achado["tipo"]])
    ordem = [sug] + [o for o in achado["opcoes"] if o != sug]
    return [rot[o] + (f" (sugestão do sistema, {conf:.0%})" if o == sug else "") for o in ordem]


def publicar(mv, achados, modelo, versao, limite=LIMITE_PUBLICAR, agora=None):
    """Grava os achados (uma vez só) e publica no M&A as perguntas novas, até `limite` por ciclo."""
    from . import mv_comandos as C
    db = mv.db
    _garantir(db)
    agora = agora if agora is not None else time.time()
    novas = 0
    for a in achados:
        r = db.execute("SELECT escolha, pergunta_id FROM gemeo_achado WHERE id=?", (a["id"],)).fetchone()
        sug, conf, _ = sugerir(modelo, a)
        if r is None:
            db.execute("INSERT INTO gemeo_achado (id,tipo,chave,descricao,opcoes,atributos,prioridade,sugestao,confianca,"
                       "modelo_versao,criado) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (a["id"], a["tipo"], a["chave"], a["descricao"], json.dumps(a["opcoes"]), json.dumps(a["atributos"]),
                        a["prioridade"], sug, conf, versao, agora))
        elif r["escolha"] is None:
            db.execute("UPDATE gemeo_achado SET sugestao=?, confianca=?, modelo_versao=? WHERE id=?", (sug, conf, versao, a["id"]))
        if (r is None or (r["escolha"] is None and not r["pergunta_id"])) and novas < limite:
            q = C.perguntar(mv, f"Gêmeo (conferente automático) · {a['descricao']}"[:1000], _rotulos(a, sug, conf),
                            origem=ORIGEM, aplica_em=APLICA)
            db.execute("UPDATE gemeo_achado SET pergunta_id=? WHERE id=?", (q["id"], a["id"]))
            novas += 1
    db.commit()
    return novas


def sincronizar_respostas(mv, agora=None):
    """Respostas dadas no M&A → escolha do achado (exemplo de treino)."""
    from . import mv_comandos as C
    db = mv.db
    _garantir(db)
    n = 0
    for r in db.execute("SELECT id, tipo, pergunta_id FROM gemeo_achado WHERE escolha IS NULL AND pergunta_id IS NOT NULL").fetchall():
        p = db.execute("SELECT resposta, nota FROM mv_pergunta WHERE id=?", (r["pergunta_id"],)).fetchone()
        if not p or not p["resposta"]:
            continue
        esc = next((k for k, rot in OPCOES[r["tipo"]] if p["resposta"].startswith(rot)), None)
        if esc:
            db.execute("UPDATE gemeo_achado SET escolha=?, origem_resposta='caixa', nota=?, respondido=? WHERE id=?",
                       (esc, p["nota"] or "", agora or time.time(), r["id"]))
            n += 1
    db.commit()
    return n


def corrigir(mv, achado_id, escolha, nota="", agora=None):
    """Correção explícita (erro do sistema ou mudança de ideia): vale como exemplo e responde a pergunta do M&A."""
    from . import mv_comandos as C
    db = mv.db
    _garantir(db)
    r = db.execute("SELECT tipo, pergunta_id FROM gemeo_achado WHERE id=?", (achado_id,)).fetchone()
    if not r:
        raise ValueError("achado não encontrado")
    rot = dict(OPCOES[r["tipo"]])
    if escolha not in rot:
        raise ValueError(f"opção inválida: {escolha} (aceitas: {', '.join(rot)})")
    db.execute("UPDATE gemeo_achado SET escolha=?, origem_resposta='correcao', nota=?, respondido=? WHERE id=?",
               (escolha, nota, agora or time.time(), achado_id))
    db.commit()
    if r["pergunta_id"]:
        C.responder(mv, r["pergunta_id"], rot[escolha], ("correção: " + nota) if nota else "correção")


def gravar_exemplos_iniciais(db, exemplos, agora=None):
    _garantir(db)
    n = 0
    for e in exemplos:
        if db.execute("SELECT 1 FROM gemeo_achado WHERE id=?", (e["id"],)).fetchone():
            continue
        db.execute("INSERT INTO gemeo_achado (id,tipo,chave,descricao,opcoes,atributos,prioridade,escolha,origem_resposta,"
                   "nota,criado,respondido) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                   (e["id"], e["tipo"], e["chave"], e["descricao"], json.dumps(e["opcoes"]), json.dumps(e["atributos"]),
                    e["prioridade"], e["escolha"], "semente", e["nota"], agora or time.time(), agora or time.time()))
        n += 1
    db.commit()
    return n


def ciclo(mv, projeto, limite=LIMITE_PUBLICAR, agora=None):
    """Um passo de melhoria contínua: respostas → treino (versão nova) → achados → perguntas novas no M&A."""
    db = mv.db
    ini = gravar_exemplos_iniciais(db, exemplos_iniciais(projeto), agora)
    resp = sincronizar_respostas(mv, agora)
    modelo = treinar(exemplos_do_banco(db), agora)
    versao = salvar_modelo(db, modelo)
    achados = detectar(projeto)
    novas = publicar(mv, achados, modelo, versao, limite, agora)
    pend = db.execute("SELECT COUNT(*) FROM gemeo_achado WHERE escolha IS NULL").fetchone()[0]
    return {"exemplos_iniciais": ini, "respostas_novas": resp, "modelo_versao": versao, "achados": len(achados),
            "perguntas_novas": novas, "pendentes": pend, "explicacao": explicar(modelo)}


def main(argv=None):
    from .mv import MV
    from . import gemeo_importar as I
    ap = argparse.ArgumentParser(description="Conferente automático do gêmeo, com aprendizado contínuo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("ciclo")
    c.add_argument("--semente", default=str(I.SEMENTE_ARQ))
    c.add_argument("--limite", type=int, default=LIMITE_PUBLICAR)
    sub.add_parser("relatorio")
    k = sub.add_parser("corrigir")
    k.add_argument("id")
    k.add_argument("opcao")
    k.add_argument("--nota", default="")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    mv = MV()
    if a.cmd == "ciclo":
        r = ciclo(mv, G.carregar(a.semente), a.limite)
        print(json.dumps({k: v for k, v in r.items() if k != "explicacao"}, ensure_ascii=False))
        print(r["explicacao"])
    elif a.cmd == "relatorio":
        modelo, v = ultimo_modelo(mv.db)
        print(f"modelo versão {v}")
        print(explicar(modelo))
        for r in mv.db.execute("SELECT id, tipo, chave, sugestao, confianca, escolha FROM gemeo_achado ORDER BY prioridade DESC"):
            print(f"{r['id']}  {r['tipo']:<11} {r['chave']:<28} sugestão {r['sugestao'] or '-':<12} "
                  f"{(r['confianca'] or 0):.0%}  escolha {r['escolha'] or '(pendente)'}")
    else:
        corrigir(mv, a.id, a.opcao, a.nota)
        print("correção registrada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
