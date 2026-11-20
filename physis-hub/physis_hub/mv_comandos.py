"""Caixa de comandos, bots por tarefa, bots programáveis e lista de aprovações do Physis M&A (VERSÃO DE TESTE, 20/11/2026;
decisões D101 e pedido da dona de 20/11: "incluir bots programáveis", "caixa de interação para comandos aos bots",
"lista de aprovações urgente para tudo que deve estar pronto até 23/11").

Regras:
- nada sai para fora: e-mail vira RASCUNHO na fila; documento vira ODT marcado VERSÃO DE TESTE e [CONFERIR], anexado à tarefa;
- texto livre (sem comando) vai para a FILA DO CLAUDE com o contexto da tarefa; quem processa é uma sessão do Claude (ou a IA
  Physis no servidor, em dezembro), com teto de custo; o resultado volta como rascunho e só vale depois de aprovado;
- bots programáveis repetem um comando por hora, dia ou semana; rodam junto com os bots agendados (mv_bots.rodar);
- a lista de aprovações registra a decisão da dona; aprovar NÃO grava nada no sistema oficial sozinho: a gravação (merge do
  ramo de teste, cópia dos documentos) é um passo separado, feito depois da aprovação.
"""
from __future__ import annotations

import json
import re
import shlex
import time
from datetime import date, datetime

from . import mv as mvmod
from .mv import MV, ErroMV

ESQUEMA = """
CREATE TABLE IF NOT EXISTS mv_pedido_bot (
  id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, comando TEXT NOT NULL, tarefa TEXT NOT NULL DEFAULT '',
  estado TEXT NOT NULL DEFAULT 'na_fila', resultado TEXT NOT NULL DEFAULT '', arquivo TEXT NOT NULL DEFAULT '',
  origem TEXT NOT NULL DEFAULT 'caixa', criado REAL NOT NULL, atualizado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mv_bot_prog (
  id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, comando TEXT NOT NULL, frequencia TEXT NOT NULL,
  ativo INTEGER NOT NULL DEFAULT 1, ultima REAL, criado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mv_aprovacao (
  id TEXT PRIMARY KEY, item TEXT NOT NULL, grupo TEXT NOT NULL DEFAULT '', prazo TEXT NOT NULL DEFAULT '',
  onde TEXT NOT NULL DEFAULT '', estado TEXT NOT NULL DEFAULT 'pendente', nota TEXT NOT NULL DEFAULT '',
  ordem INTEGER NOT NULL DEFAULT 100, decidido REAL, criado REAL NOT NULL);
CREATE TABLE IF NOT EXISTS mv_pergunta (
  id TEXT PRIMARY KEY, pergunta TEXT NOT NULL, opcoes TEXT NOT NULL DEFAULT '[]', origem TEXT NOT NULL DEFAULT '',
  aplica_em TEXT NOT NULL DEFAULT '[]', prazo TEXT NOT NULL DEFAULT '', resposta TEXT NOT NULL DEFAULT '', nota TEXT NOT NULL DEFAULT '',
  pedidos INTEGER NOT NULL DEFAULT 1, respondida REAL, criado REAL NOT NULL);
"""
SISTEMAS = ("sistema-physis", "instituto", "inovastem", "casa", "m&a", "templates", "documentos")
ESTADOS_PEDIDO = ("na_fila", "rascunho", "pronto", "aprovado", "descartado", "erro")
ESTADOS_APROV = ("pendente", "aprovado", "ajustar", "reprovado")
FREQUENCIAS = {"hora": 3600, "dia": 86400, "semana": 7 * 86400}
MODELOS = {
    "contrato": ("Modelo de contrato", ["Partes", "Objeto", "Prazo e cronograma", "Valor e forma de pagamento", "Obrigações das partes",
                                        "Propriedade intelectual", "Confidencialidade e LGPD", "Rescisão", "Foro", "Assinaturas"]),
    "oficio": ("Modelo de ofício", ["Destinatário", "Assunto", "Corpo", "Pedido", "Assinatura"]),
    "termo": ("Modelo de termo", ["Partes", "Objeto", "Condições", "Vigência", "Assinaturas"]),
    "ata": ("Modelo de ata", ["Data, local e participantes", "Pauta", "Discussão", "Decisões", "Encaminhamentos e responsáveis"]),
    "proposta": ("Modelo de proposta", ["Resumo", "Problema", "Solução", "Cronograma", "Orçamento", "Equipe", "Indicadores"]),
}
AJUDA = [
    "/modelo contrato|oficio|termo|ata|proposta <id da tarefa>: gera documento-modelo ODT (versão de teste) anexado à tarefa",
    "/contrato <id da tarefa>: atalho de /modelo contrato",
    "/email <id da tarefa> [assunto]: rascunho de e-mail na fila (você revisa e envia; nada sai sozinho)",
    "/checklist <id da tarefa>: passos e exigências propostos para a tarefa",
    "/revisar <id do arquivo>: confere um anexo (datas, nomes, marcadores, regras dos documentos)",
    "/imprimir <id do arquivo 3D> [material]: pedido de impressão 3D (aguarda aprovação)",
    "/rodar atrasos|documentos|resumo|backup|paginas|inovacao: roda um bot agora (paginas = checklist base, doc 43; inovacao = pesquisa diária aberta)",
    "/programar hora|dia|semana <comando>: repete um comando (bot programável)",
    "/aprovar <id> · /ajustar <id> [nota]: decide um item da lista de aprovações",
    "Texto sem barra: vai para a fila do Claude com o contexto (tarefa: escreva #id da tarefa no texto)",
]


class Comandos:
    def __init__(self, mv: MV, arquivos=None):
        self.mv = mv
        self.arq = arquivos
        mv.db.executescript(ESQUEMA)
        mv.db.commit()

    # ------------------------------------------------------------ fila
    def _pedido(self, tipo: str, comando: str, tarefa: str = "", estado: str = "na_fila", resultado: str = "", arquivo: str = "",
                origem: str = "caixa") -> dict:
        agora = time.time()
        cur = self.mv.db.execute("INSERT INTO mv_pedido_bot (tipo,comando,tarefa,estado,resultado,arquivo,origem,criado,atualizado) "
                                 "VALUES (?,?,?,?,?,?,?,?,?)", (tipo, comando[:2000], tarefa, estado, resultado[:20000], arquivo,
                                                                 origem[:40], agora, agora))
        self.mv.db.commit()
        return self.pedido(cur.lastrowid)

    def pedido(self, pid: int) -> dict:
        r = self.mv.db.execute("SELECT * FROM mv_pedido_bot WHERE id=?", (int(pid),)).fetchone()
        if not r:
            raise ErroMV("pedido não encontrado")
        d = dict(r)
        d["quando"] = datetime.fromtimestamp(d["criado"]).strftime("%Y-%m-%d %H:%M")
        return d

    def fila(self, estado: str | None = None, limite: int = 200) -> list[dict]:
        q, a = "SELECT id FROM mv_pedido_bot", []
        if estado:
            q, a = q + " WHERE estado=?", [estado]
        return [self.pedido(r["id"]) for r in self.mv.db.execute(q + " ORDER BY criado DESC LIMIT ?", a + [int(limite)])]

    def decidir_pedido(self, pid: int, estado: str, resultado: str | None = None) -> dict:
        if estado not in ESTADOS_PEDIDO:
            raise ErroMV("estado inválido")
        p = self.pedido(pid)
        self.mv.db.execute("UPDATE mv_pedido_bot SET estado=?, resultado=?, atualizado=? WHERE id=?",
                           (estado, p["resultado"] if resultado is None else str(resultado)[:20000], time.time(), int(pid)))
        self.mv.db.commit()
        if p["tipo"] == "inovacao" and estado == "aprovado" and p["estado"] != "aprovado":
            # descoberta aprovada → entra como atividade em seguida (diretriz de 20/11/2026)
            self.mv.salvar_tarefa({"id": f"inov-{int(pid)}", "frente": "transversal", "projeto": "Inovação aberta (pesquisa diária)",
                                   "titulo": f"Avaliar e integrar: {p['comando'][:180]}", "responsavel": "Rafaella",
                                   "fonte": "bot inovacao", "data_estimada": True}, origem="bot:inovacao")
        return self.pedido(pid)

    # ------------------------------------------------------------ comandos
    def _tarefa(self, tid: str) -> dict:
        t = self.mv.tarefa(tid.lstrip("#"))
        if not t:
            raise ErroMV(f"tarefa não encontrada: {tid}")
        return t

    def executar(self, texto: str, origem: str = "caixa") -> dict:
        texto = str(texto or "").strip()
        if not texto:
            raise ErroMV("comando vazio")
        if len(texto) > 2000:
            raise ErroMV("comando com mais de 2000 caracteres")
        if not texto.startswith("/"):
            m = re.search(r"#([A-Za-z0-9_.:-]{1,80})", texto)
            tid = m.group(1) if m and self.mv.tarefa(m.group(1)) else ""
            return self._pedido("claude", texto, tid, "na_fila",
                                "Na fila do Claude. Volta como rascunho para você aprovar.", origem=origem)
        try:
            partes = shlex.split(texto[1:])
        except ValueError:
            partes = texto[1:].split()
        if not partes:
            raise ErroMV("comando vazio")
        cmd, args = partes[0].lower(), partes[1:]
        if cmd in ("ajuda", "help", "?"):
            return {"tipo": "ajuda", "estado": "pronto", "resultado": "\n".join(AJUDA)}
        if cmd == "contrato":
            cmd, args = "modelo", ["contrato"] + args
        if cmd == "modelo":
            if len(args) < 2 or args[0] not in MODELOS:
                raise ErroMV("use: /modelo contrato|oficio|termo|ata|proposta <id da tarefa>")
            return self.modelo(args[0], self._tarefa(args[1]), texto, origem)
        if cmd == "email":
            if not args:
                raise ErroMV("use: /email <id da tarefa> [assunto]")
            return self.email(self._tarefa(args[0]), " ".join(args[1:]), texto, origem)
        if cmd == "checklist":
            if not args:
                raise ErroMV("use: /checklist <id da tarefa>")
            return self.checklist(self._tarefa(args[0]), texto, origem)
        if cmd == "revisar":
            if not args:
                raise ErroMV("use: /revisar <id do arquivo>")
            return self.revisar(args[0], texto, origem)
        if cmd == "imprimir":
            if not args:
                raise ErroMV("use: /imprimir <id do arquivo 3D> [material]")
            return self.imprimir(args[0], " ".join(args[1:]), texto, origem)
        if cmd == "rodar":
            from . import mv_bots
            quais = [a for a in args if a in mv_bots.BOTS]
            if not quais:
                raise ErroMV("use: /rodar atrasos|documentos|resumo|backup")
            r = mv_bots.rodar(self.mv, quais)
            return self._pedido("rodar", texto, "", "pronto", json.dumps(r, ensure_ascii=False, default=str)[:5000], origem=origem)
        if cmd == "programar":
            if len(args) < 2 or args[0] not in FREQUENCIAS:
                raise ErroMV("use: /programar hora|dia|semana <comando>")
            return self.programar(" ".join(args[1:]), args[0])
        if cmd in ("aprovar", "ajustar", "reprovar"):
            if not args:
                raise ErroMV(f"use: /{cmd} <id do item>")
            est = {"aprovar": "aprovado", "ajustar": "ajustar", "reprovar": "reprovado"}[cmd]
            return {"tipo": "aprovacao", "estado": "pronto", "resultado": json.dumps(self.decidir(args[0], est, " ".join(args[1:])),
                                                                                    ensure_ascii=False)}
        raise ErroMV(f"comando desconhecido: /{cmd} (digite /ajuda)")

    def modelo(self, tipo: str, t: dict, texto: str, origem: str) -> dict:
        from . import documentos
        titulo, secoes = MODELOS[tipo]
        blocos = [{"t": "VERSÃO DE TESTE · gerado pelo bot do Physis M&A · revisar antes de usar · nada foi enviado"},
                  {"t": f"Tarefa: {t['titulo']} ({t['id']}) · Responsável: {t['responsavel'] or '[MARCADOR]'} · "
                        f"Prazo: {t['fim'] or '[MARCADOR]'}{' [CONFERIR]' if t['data_estimada'] else ''}"}]
        for sec in secoes:
            blocos += [{"h": 2, "t": sec}, {"t": "[MARCADOR] — preencher; não inventar valores, nomes nem cláusulas legais sem revisão do advogado."}]
        nome = f"{tipo}_{re.sub(r'[^A-Za-z0-9]+', '-', t['id'])[:40]}_{date.today().isoformat()}_TESTE.odt"
        b = documentos.odt(f"{titulo} · {t['titulo'][:80]}", blocos, sistema="Physis M&A (teste)")
        aid = ""
        if self.arq:
            aid = self.arq.guardar("documentos", nome, b, t["id"], origem="bot")["id"]
        return self._pedido("modelo", texto, t["id"], "rascunho", f"{titulo} gerado ({nome}). Abra, revise e aprove.", aid, origem)

    def email(self, t: dict, assunto: str, texto: str, origem: str) -> dict:
        corpo = (f"Assunto: {assunto or t['titulo'][:120]}\n\nOlá, [NOME],\n\n[MARCADOR: objetivo do contato sobre \"{t['titulo']}\"].\n\n"
                 f"Prazo de referência: {t['fim'] or '[MARCADOR]'}{' [CONFERIR]' if t['data_estimada'] else ''}.\n\n"
                 "Fico à disposição.\n\nRafaella\nPhysis Engineering\n\n— RASCUNHO do Physis M&A: revisar e enviar manualmente. Nada foi enviado.")
        return self._pedido("email", texto, t["id"], "rascunho", corpo, origem=origem)

    def checklist(self, t: dict, texto: str, origem: str) -> dict:
        base = ["Confirmar escopo e resultado esperado com a responsável", "Levantar exigências (lei, edital, contrato, norma) e fontes",
                "Listar documentos e dados necessários (anexar na tarefa)", "Fazer a versão de teste", "Revisão (outra pessoa)",
                "Aprovação da dona", "Gravar/enviar a versão oficial e registrar a data"]
        tl = t["titulo"].lower()
        if re.search(r"contrat|termo|acordo|estatuto", tl):
            base.insert(2, "Revisão jurídica (advogado) antes de assinar")
        if re.search(r"edital|proposta|bolsa|chamada", tl):
            base.insert(2, "Conferir requisitos e prazo no edital oficial (fonte verificada)")
        if re.search(r"cont[aá]b|fiscal|cnpj|tribut|nota", tl):
            base.insert(2, "Pergunta ao contador (Robson) registrada no roteiro 35/36")
        if re.search(r"3d|impress|modelo|bim|ifc", tl):
            base.insert(2, "Arquivo do modelo (STL/OBJ/IFC) anexado e conferido no visualizador")
        txt = "\n".join(f"- [ ] {x}" for x in base)
        return self._pedido("checklist", texto, t["id"], "rascunho", txt, origem=origem)

    def revisar(self, aid: str, texto: str, origem: str) -> dict:
        if not self.arq:
            raise ErroMV("revisão de arquivos indisponível")
        from pathlib import Path
        from . import mv_bots
        r = self.arq._linha(aid)
        conteudo = mv_bots.texto_de(Path(r["caminho"]))
        if not conteudo:
            res = "Sem texto legível (PDF/imagem): conferir manualmente."
        else:
            falhas, marc = mv_bots.conferir_texto(conteudo)
            res = (f"{len(falhas)} falha(s), {marc} marcador(es) a preencher.\n" +
                   "\n".join(f"- {f['texto']} → {f['decisao']}" for f in falhas)) if falhas or marc else "Nenhuma falha pelas regras atuais."
        return self._pedido("revisao", texto, r["ref"] or "", "pronto", res, aid, origem)

    def imprimir(self, aid: str, material: str, texto: str, origem: str) -> dict:
        if not self.arq:
            raise ErroMV("arquivos indisponíveis")
        r = self.arq._linha(aid)
        if r["destino"] != "modelos3d":
            raise ErroMV("só modelos 3D (aba Modelagem 3D) podem ir para impressão")
        res = (f"Pedido de impressão 3D: {r['nome']} · material: {material or '[MARCADOR]'} · aguarda aprovação.\n"
               "Depois de aprovado: baixar o arquivo e abrir no CrealityPrint (filamento) ou HALOT BOX (resina) no computador da impressora.")
        return self._pedido("impressao3d", texto, r["ref"] or "", "rascunho", res, aid, origem)

    # ------------------------------------------------------------ bots programáveis
    def programar(self, comando: str, frequencia: str, nome: str = "") -> dict:
        if frequencia not in FREQUENCIAS:
            raise ErroMV("frequência inválida (hora, dia, semana)")
        comando = comando.strip()
        if not comando.startswith("/") or comando.split()[0].lower() in ("/programar", "/aprovar", "/ajustar", "/reprovar"):
            raise ErroMV("programe um comando com barra (ex.: /rodar resumo, /checklist <tarefa>)")
        cur = self.mv.db.execute("INSERT INTO mv_bot_prog (nome,comando,frequencia,ativo,criado) VALUES (?,?,?,1,?)",
                                 (nome or comando[:60], comando[:500], frequencia, time.time()))
        self.mv.db.commit()
        return {"tipo": "programado", "estado": "pronto", "id": cur.lastrowid,
                "resultado": f"Bot programado: {comando} a cada {frequencia}."}

    def programados(self) -> list[dict]:
        return [dict(r) for r in self.mv.db.execute("SELECT * FROM mv_bot_prog ORDER BY id")]

    def alternar(self, bid: int, ativo: bool) -> dict:
        self.mv.db.execute("UPDATE mv_bot_prog SET ativo=? WHERE id=?", (1 if ativo else 0, int(bid)))
        self.mv.db.commit()
        return next((b for b in self.programados() if b["id"] == int(bid)), {})

    def rodar_programados(self, agora: float | None = None) -> list[dict]:
        agora = agora or time.time()
        out = []
        for b in self.programados():
            if not b["ativo"] or (b["ultima"] and agora - b["ultima"] < FREQUENCIAS[b["frequencia"]] - 60):
                continue
            try:
                r = self.executar(b["comando"], origem=f"programado:{b['id']}")
                out.append({"id": b["id"], "ok": True, "pedido": r.get("id")})
            except ErroMV as e:
                out.append({"id": b["id"], "ok": False, "erro": str(e)})
                self.mv.alertar("bots", "programado_falhou", str(b["id"]), "atencao", f"Bot programado '{b['nome']}' falhou: {e}",
                                "Corrigir o comando na aba Bots e comandos")
            self.mv.db.execute("UPDATE mv_bot_prog SET ultima=? WHERE id=?", (agora, b["id"]))
            self.mv.db.commit()
        return out

    # ------------------------------------------------------------ aprovações
    def semear_aprovacoes(self, itens: list[dict]) -> int:
        n = 0
        for i, it in enumerate(itens):
            if self.mv.db.execute("SELECT 1 FROM mv_aprovacao WHERE id=?", (it["id"],)).fetchone():
                continue
            self.mv.db.execute("INSERT INTO mv_aprovacao (id,item,grupo,prazo,onde,ordem,criado) VALUES (?,?,?,?,?,?,?)",
                               (it["id"], it["item"], it.get("grupo", ""), it.get("prazo", ""), it.get("onde", ""), i, time.time()))
            n += 1
        self.mv.db.commit()
        return n

    def aprovacoes(self) -> list[dict]:
        hoje = mvmod.HOJE().isoformat()
        out = []
        for r in self.mv.db.execute("SELECT * FROM mv_aprovacao ORDER BY prazo, ordem"):
            d = dict(r)
            d["atrasada"] = d["estado"] in ("pendente", "ajustar") and bool(d["prazo"]) and d["prazo"] < hoje
            out.append(d)
        return out

    def decidir(self, iid: str, estado: str, nota: str = "") -> dict:
        if estado not in ESTADOS_APROV:
            raise ErroMV("estado inválido (pendente, aprovado, ajustar, reprovado)")
        if not self.mv.db.execute("SELECT 1 FROM mv_aprovacao WHERE id=?", (iid,)).fetchone():
            raise ErroMV("item não encontrado")
        self.mv.db.execute("UPDATE mv_aprovacao SET estado=?, nota=?, decidido=? WHERE id=?",
                           (estado, str(nota or "")[:2000], time.time() if estado != "pendente" else None, iid))
        self.mv.db.commit()
        return dict(self.mv.db.execute("SELECT * FROM mv_aprovacao WHERE id=?", (iid,)).fetchone())


# ------------------------------------------------------------------ perguntas e decisões centralizadas (20/11/2026)
def _chave(texto: str) -> str:
    import hashlib
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFKD", str(texto)) if not unicodedata.combining(c)).lower()
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return "pg:" + hashlib.sha1(t.encode()).hexdigest()[:12]


def _garantir(mv: MV) -> None:
    """As funções de perguntas podem ser chamadas direto (linha de comando, outras sessões): criam as tabelas se faltarem."""
    mv.db.executescript(ESQUEMA)
    mv.db.commit()


def _perg(r) -> dict:
    d = dict(r)
    d["opcoes"] = json.loads(d["opcoes"])
    d["aplica_em"] = json.loads(d["aplica_em"])
    d["aberta"] = not d["resposta"]
    return d


def perguntar(mv: MV, pergunta: str, opcoes: list[str] | None = None, origem: str = "", aplica_em: list[str] | None = None,
              prazo: str = "") -> dict:
    """Registra a pergunta UMA vez. Se a mesma pergunta (mesmo texto, sem acento/pontuação) já existe, devolve a existente com a
    resposta, se houver (ja_existia=True): quem pergunta usa a resposta em vez de perguntar de novo à dona."""
    _garantir(mv)
    pergunta = str(pergunta or "").strip()
    if not pergunta or len(pergunta) > 1000:
        raise ErroMV("pergunta vazia ou longa demais")
    aplica = [a for a in (aplica_em or []) if a in SISTEMAS]
    pid = _chave(pergunta)
    r = mv.db.execute("SELECT * FROM mv_pergunta WHERE id=?", (pid,)).fetchone()
    if r:
        ant = _perg(r)
        novos = sorted(set(ant["aplica_em"]) | set(aplica))
        mv.db.execute("UPDATE mv_pergunta SET pedidos=pedidos+1, aplica_em=? WHERE id=?", (json.dumps(novos), pid))
        mv.db.commit()
        return {**_perg(mv.db.execute("SELECT * FROM mv_pergunta WHERE id=?", (pid,)).fetchone()), "ja_existia": True}
    mv.db.execute("INSERT INTO mv_pergunta (id,pergunta,opcoes,origem,aplica_em,prazo,criado) VALUES (?,?,?,?,?,?,?)",
                  (pid, pergunta, json.dumps([str(o)[:200] for o in (opcoes or [])][:6], ensure_ascii=False), str(origem)[:80],
                   json.dumps(aplica), str(prazo)[:10], time.time()))
    mv.db.commit()
    return {**_perg(mv.db.execute("SELECT * FROM mv_pergunta WHERE id=?", (pid,)).fetchone()), "ja_existia": False}


def responder(mv: MV, pid: str, resposta: str, nota: str = "") -> dict:
    _garantir(mv)
    if not mv.db.execute("SELECT 1 FROM mv_pergunta WHERE id=?", (pid,)).fetchone():
        raise ErroMV("pergunta não encontrada")
    if not str(resposta or "").strip():
        raise ErroMV("resposta vazia")
    mv.db.execute("UPDATE mv_pergunta SET resposta=?, nota=?, respondida=? WHERE id=?", (str(resposta)[:2000], str(nota)[:2000], time.time(), pid))
    mv.db.commit()
    return _perg(mv.db.execute("SELECT * FROM mv_pergunta WHERE id=?", (pid,)).fetchone())


def perguntas(mv: MV, abertas: bool | None = None, sistema: str | None = None) -> list[dict]:
    _garantir(mv)
    out = [_perg(r) for r in mv.db.execute("SELECT * FROM mv_pergunta ORDER BY respondida IS NOT NULL, prazo, criado")]
    if abertas is not None:
        out = [p for p in out if p["aberta"] == abertas]
    if sistema:
        out = [p for p in out if sistema in p["aplica_em"]]
    return out


# Lista inicial de aprovações urgentes (pedido de 20/11/2026; prazos até 23/11, InovaSTEM teste 24/11 e lançamento 26/11).
APROVACOES_23_11 = [
    {"id": "ap-tipos-tela", "grupo": "Identidade", "prazo": "2026-11-21", "item": "Tipos de tela A/B/C e Delas (PALETA.md, seção Tipos de tela)", "onde": "physis-teste/physis-hub/docs/PALETA.md"},
    {"id": "ap-mv-visual", "grupo": "Physis M&A", "prazo": "2026-11-21", "item": "M&A no visual do guia (claro B, escuro A) + Projetos + gráficos", "onde": "rede local · Physis M&A (teste)"},
    {"id": "ap-mv-bots", "grupo": "Physis M&A", "prazo": "2026-11-22", "item": "Caixa de comandos, bots por tarefa e bots programáveis", "onde": "aba Bots e comandos"},
    {"id": "ap-mv-3d", "grupo": "Modelagem 3D", "prazo": "2026-11-22", "item": "Aba Modelagem 3D: visualizador, galeria com licença, fila de impressão, escaneados", "onde": "aba Modelagem 3D"},
    {"id": "ap-telas-recolor", "grupo": "Identidade", "prazo": "2026-11-22", "item": "Plataforma do cliente, loja, Gestão, Planejador, SustainKit, SCADA e demos no novo visual", "onde": "ramo teste/identidade-guia"},
    {"id": "ap-site-inovastem", "grupo": "InovaSTEM", "prazo": "2026-11-23", "item": "Site InovaSTEM (tipo B claro, A escuro, Delas roxo) + 3D, versão de teste para o teste de 24/11", "onde": "sessão do site InovaSTEM"},
    {"id": "ap-logos", "grupo": "Identidade", "prazo": "2026-11-22", "item": "Logos para templates (recortes do guia ou SVG v0) por marca, claro e escuro", "onde": "Casa Physis/Identidade_Visual_v0_proposta"},
    {"id": "ap-modelos-docs", "grupo": "Documentos", "prazo": "2026-11-23", "item": "Modelos por tipo de documento (proposta, relatório, apresentação, CV, planilha, PDF, assinatura de e-mail)", "onde": "modelos _TESTE"},
    {"id": "ap-pacote-contador", "grupo": "Documentos", "prazo": "2026-11-22", "item": "Pacote para o contador (Robson) e roteiros 35/36 atualizados (fechar até 22/11 19h; lista em Envio_Contador_v0_TESTE/PENDENCIAS_ENVIO.md)", "onde": "Casa Physis/Envio_Contador_v0_TESTE"},
    {"id": "ap-rede-local", "grupo": "Infra", "prazo": "2026-11-20", "item": "Teste na rede local com senha de teste (sem internet pública)", "onde": "atalho Physis_teste_rede"},
    {"id": "ap-checklist-f23", "grupo": "Planejamento", "prazo": "2026-11-21", "item": "Checklist das Fases 2 e 3 (modelagens BIM, GIS, física, química, biológica, quântica, gêmeos digitais)", "onde": "Sistema Physis/42b"},
    {"id": "ap-p0-evento-14h", "grupo": "P0 · Rede Taças e Turbinas", "prazo": "2026-11-21", "item": "Aula de 40 min (empreendedorismo com PDI) + apresentação Physis/lançamento 0 InovaSTEM + previsões 2027: revisão interna até 14h (aprova: Rafaella)", "onde": "Casa Physis/Eventos_Rede_Tacas_Turbinas_21-11_TESTE"},
    {"id": "ap-p0-evento-18h", "grupo": "P0 · Rede Taças e Turbinas", "prazo": "2026-11-21", "item": "Envio externo dos materiais do evento às 18h (com QR codes inseridos na aprovação)", "onde": "depois do item de 14h"},
    {"id": "ap-p0-whatsapp", "grupo": "P0 · WhatsApp", "prazo": "2026-11-22", "item": "Estratégia de WhatsApp (Business existente: grupos, mensagens, automações) definida; teste a partir de 23/11", "onde": "doc 45"},
    {"id": "ap-p0-estermic-ryan", "grupo": "P0 · Estermic", "prazo": "2026-11-23", "item": "Sistema Estermic (AVAC personalizado, 4 subprojetos) · versão final interna ao Ryan às 13h59", "onde": "doc 44 + ramo de teste"},
    {"id": "ap-p0-estermic-teste", "grupo": "P0 · Estermic", "prazo": "2026-11-24", "item": "Emissão de teste do AVAC/Estermic (IFC, lista de equipamentos, relatório, memorial de cálculo, financeiro por fases)", "onde": "doc 44"},
    {"id": "ap-p0-independencia", "grupo": "P0 · Infra", "prazo": "2026-11-23", "item": "Sistemas e bots rodando sem o Claude (este PC + Acer), apps disponíveis para teste", "onde": "doc 45"},
    {"id": "ap-logos-vetor", "grupo": "Identidade", "prazo": "2026-11-23", "item": "Logos vetorizadas do ecossistema para compartilhar com parceiros (fiéis ao guia)", "onde": "Casa Physis/Identidade_Visual_v0_proposta"},
    {"id": "ap-gsa-25-11", "grupo": "Global South Alliance", "prazo": "2026-11-25", "item": "Alimentar a aba GSA após a reunião de alinhamento", "onde": "M&A → Clientes e projetos → GSA"},
    {"id": "ap-gravar-sistemas", "grupo": "Gravação", "prazo": "2026-11-23", "item": "Gravar o aprovado no Sistema Physis e no sistema do Instituto (merge do ramo de teste + cópias oficiais)", "onde": "depois das aprovações acima"},
]
