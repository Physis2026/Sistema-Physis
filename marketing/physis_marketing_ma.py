"""Aprovações do Marketing pelo M&A e pela Gestão (23/11/2026) · complemento do physis_marketing_bot.py.

Ligado com APROVACAO=ma no bot.env. Os conteúdos nascem na Gestão › Marketing e vão para a equipe;
(uma aprovação basta: Rafaella no M&A ou Marzia na Gestão). O M&A grava os aprovados em <BOT_DADOS>/conteudos_aprovados.csv
de hora em hora; este módulo lê essa lista no lugar do Slack (regra 11: o Slack fica só como opção).

  aprovacoes  aprovados ainda não tratados → BOT_MODO=manual/teste: entram em publicar_aprovados.csv (a equipe publica
              e marca "sim" na coluna publicado); BOT_MODO=producao: agenda no Postiz (Instagram exige arte em artes/<id>.*)
  lembretes   mostra o que publicar hoje e amanhã (o M&A também avisa); grava lembretes.txt em BOT_DADOS
"""
import csv
import datetime as dt
import glob
import os


def comandos(g):
    env, DADOS, FUSO = g["env"], g["DADOS"], g["FUSO"]
    MODO = env("BOT_MODO", "teste")
    entrada = os.path.join(DADOS, "conteudos_aprovados.csv")
    saida = os.path.join(DADOS, "publicar_aprovados.csv")

    def aprovados():
        if not os.path.exists(entrada):
            print("Ainda não há", entrada, "(o M&A grava de hora em hora quando há aprovados pelas duas)")
            return []
        return list(csv.DictReader(open(entrada, encoding="utf-8-sig"), delimiter=";"))

    def ja_tratados():
        if not os.path.exists(saida):
            return set()
        return {r["id"] for r in csv.DictReader(open(saida, encoding="utf-8-sig"), delimiter=";")}

    def quando(c):
        return dt.datetime.fromisoformat(f"{c['data']}T{(c.get('hora') or '09:00')[:5]}:00").replace(tzinfo=FUSO)

    def cmd_aprovacoes():
        os.makedirs(DADOS, exist_ok=True)
        os.makedirs(os.path.join(DADOS, "artes"), exist_ok=True)
        feitos, n = ja_tratados(), 0
        novo = not os.path.exists(saida)
        with open(saida, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f, delimiter=";")
            if novo:
                w.writerow(["id", "data", "hora", "redes", "titulo", "legenda", "modo", "situacao", "publicado"])
            for c in aprovados():
                if c["id"] in feitos or not c.get("data"):
                    continue
                q = quando(c)
                if q <= dt.datetime.now(FUSO):
                    w.writerow([c["id"], c["data"], c.get("hora", ""), c["redes"], c["titulo"], c["texto"][:500], MODO, "data já passou: ajuste na Gestão", "não"])
                    continue
                redes = [r for r in c["redes"].split(",") if r]
                situ = "publicar à mão"
                if MODO == "producao":
                    artes = sorted(glob.glob(os.path.join(DADOS, "artes", c["id"] + ".*")))
                    try:
                        if "instagram" in redes and not artes:
                            raise RuntimeError(f"Instagram exige arte em artes/{c['id']}.jpg (ou .png/.mp4)")
                        g["agendar"](redes, q, c["texto"], artes)
                        situ = "agendado no Postiz"
                    except Exception as e:  # noqa: BLE001
                        situ = f"não agendou: {str(e)[:120]}"
                elif MODO == "teste":
                    situ = "MODO TESTE: nada foi agendado"
                w.writerow([c["id"], c["data"], c.get("hora", ""), c["redes"], c["titulo"], c["texto"][:500], MODO, situ, "não"])
                n += 1
        print(f"{n} conteúdo(s) aprovado(s) novo(s) registrados em {saida}")

    def cmd_lembretes():
        hoje = dt.datetime.now(FUSO).date()
        linhas = []
        if os.path.exists(saida):
            for r in csv.DictReader(open(saida, encoding="utf-8-sig"), delimiter=";"):
                if r.get("publicado", "não").lower() != "sim" and r.get("data") in (hoje.isoformat(), (hoje + dt.timedelta(days=1)).isoformat()):
                    linhas.append(f"{r['data']} {r.get('hora','')} · {r['redes']} · {r['titulo']} ({r.get('situacao','')})")
        txt = "Publicar hoje/amanhã:\n" + ("\n".join(linhas) if linhas else "nada")
        print(txt)
        os.makedirs(DADOS, exist_ok=True)
        open(os.path.join(DADOS, "lembretes.txt"), "w", encoding="utf-8").write(txt + "\n")

    # Métricas sem API (23/11/2026: a conta Meta não foi aceita no developers.facebook.com): o que faltar na coleta
    # automática vem dos números anotados na Gestão › Marketing › Métricas (o M&A grava metricas_gestao.csv).
    coletar_api = g.get("coletar")
    if coletar_api:
        def coletar_com_gestao():
            linha = coletar_api()
            arq = os.path.join(DADOS, "metricas_gestao.csv")
            if os.path.exists(arq):
                ult = {}
                for r in csv.DictReader(open(arq, encoding="utf-8-sig"), delimiter=";"):
                    ult[(r.get("rede") or "").lower()] = r
                for chave, prefixos in (("ig_seguidores", ("insta",)), ("li_seguidores", ("linked",)), ("yt_inscritos", ("you",))):
                    if linha.get(chave) in (None, ""):
                        for rede, r in ult.items():
                            if rede.startswith(prefixos) and r.get("seguidores"):
                                linha[chave] = r["seguidores"]
                                linha[chave.split("_")[0] + "_fonte"] = "anotado na Gestão em " + (r.get("data") or "?")
            return linha
        g["coletar"] = coletar_com_gestao

    return {"aprovacoes": cmd_aprovacoes, "lembretes": cmd_lembretes}
