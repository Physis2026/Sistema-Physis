"""Caixas de upload do Physis M&A (VERSÃO DE TESTE, 19/11/2026; pedido da dona: "sempre incluir caixas de upload, para
armazenamento e leitura de dados").

Três destinos:
- **editais**: CSV no formato do banco (doc 31, separador ';') para importar, ou o PDF/ODT/DOCX do edital, vinculado a uma ficha;
- **documentos**: anexos (comprovantes, atas, rascunhos, imagens) vinculados a uma tarefa ou a um documento;
- **financas**: CSV/ODS de lançamentos para importar como "a conferir" (D70), ou extratos em PDF/imagem só guardados.

Regras:
- o arquivo fica FORA do OneDrive, junto ao banco (pasta_padrao()/arquivos/<destino>/<AAAA-MM>/), com sha256, origem e data;
- o tipo é conferido pelo conteúdo (assinatura do arquivo), não só pela extensão; limite de 10 MB;
- o mesmo arquivo (mesmo sha256) enviado de novo para o mesmo destino não é duplicado;
- CSV/ODS que alimentam o banco passam por PRÉVIA (versão de teste) e só entram com "Aplicar"; nada é aplicado duas vezes;
- descartar não apaga o arquivo do disco (só marca), para a auditoria poder conferir depois.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import re
import time
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from . import mv_editais
from .mv import ENTIDADES_FIN, MV, TIPOS_LANC, ErroMV, pasta_padrao

TAMANHO_MAX = 10 * 1024 * 1024
DESTINOS = {
    "editais": {"csv", "pdf", "odt", "ods", "docx", "xlsx"},
    "documentos": {"pdf", "odt", "ods", "odp", "docx", "xlsx", "pptx", "csv", "txt", "md", "png", "jpg", "jpeg"},
    "financas": {"csv", "ods", "pdf", "png", "jpg", "jpeg"},
}
IMPORTAVEIS = {("editais", "csv"), ("financas", "csv"), ("financas", "ods")}
ESQUEMA = """
CREATE TABLE IF NOT EXISTS mv_arquivo (
  id TEXT PRIMARY KEY, destino TEXT NOT NULL, ref TEXT NOT NULL DEFAULT '', nome TEXT NOT NULL, caminho TEXT NOT NULL,
  extensao TEXT NOT NULL, tamanho INTEGER NOT NULL, sha256 TEXT NOT NULL, estado TEXT NOT NULL DEFAULT 'recebido',
  resumo TEXT NOT NULL DEFAULT '', origem TEXT NOT NULL DEFAULT 'upload', criado REAL NOT NULL, aplicado REAL);
CREATE INDEX IF NOT EXISTS mv_arquivo_destino ON mv_arquivo(destino, ref);
"""
_ID = re.compile(r"^arq:[0-9a-f]{16}$")
_REF = re.compile(r"^[^\x00-\x1f<>]{0,300}$")
_ZIP = {"ods", "odt", "odp", "docx", "xlsx", "pptx"}
_TEXTO = {"csv", "txt", "md"}
NOMES_ENT = {"casa": "casa", "casa physis": "casa", "engineering": "engineering", "physis engineering": "engineering",
             "instituto": "instituto", "instituto physis": "instituto", "pessoa fisica": "pessoa_fisica",
             "pessoa_fisica": "pessoa_fisica", "pf": "pessoa_fisica", "pessoa fisica (lote)": "pessoa_fisica"}
COLS_FIN = {"entidade": "entidade", "data": "data", "tipo": "tipo", "valor": "valor", "valor (r$)": "valor",
            "descricao": "descricao", "historico": "descricao", "projeto": "projeto", "fonte": "fonte", "documento": "fonte"}


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c)).strip().lower()


def nome_seguro(nome: str) -> str:
    base = Path(str(nome or "arquivo")).name
    base = _sem_acento(base).replace(" ", "_")
    base = re.sub(r"[^a-z0-9._-]", "", base).strip("._") or "arquivo"
    return base[-120:]


def conferir_tipo(dados: bytes, ext: str) -> None:
    """Confere a assinatura do conteúdo: um .pdf tem que ser PDF, um .ods tem que ser ZIP etc."""
    ok = {"pdf": dados[:5] == b"%PDF-", "png": dados[:8] == b"\x89PNG\r\n\x1a\n", "jpg": dados[:3] == b"\xff\xd8\xff",
          "jpeg": dados[:3] == b"\xff\xd8\xff"}.get(ext)
    if ext in _ZIP:
        ok = dados[:4] == b"PK\x03\x04" and zipfile.is_zipfile(io.BytesIO(dados))
    if ext in _TEXTO:
        ok = b"\x00" not in dados[:4096]
        if ok:
            try:
                ler_texto(dados)
            except UnicodeDecodeError:
                ok = False
    if not ok:
        raise ErroMV(f"o conteúdo não corresponde a um arquivo .{ext}")


def ler_texto(dados: bytes) -> str:
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        return dados.decode("cp1252")


def ler_csv(dados: bytes) -> list[dict]:
    txt = ler_texto(dados)
    prim = txt.splitlines()[0] if txt else ""
    sep = ";" if prim.count(";") >= prim.count(",") else ","
    return [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(io.StringIO(txt), delimiter=sep)]


def ler_ods(dados: bytes) -> list[dict]:
    """Primeira planilha de um ODS como lista de dicionários (cabeçalho na 1ª linha). Só biblioteca padrão."""
    ns = {"table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0", "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
          "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0"}
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        if z.getinfo("content.xml").file_size > 50 * 1024 * 1024:
            raise ErroMV("planilha grande demais")
        raiz = ET.fromstring(z.read("content.xml"))
    tab = raiz.find(".//table:table", ns)
    if tab is None:
        return []
    T = "{%s}" % ns["table"]
    linhas = []
    for row in tab.iter(T + "table-row"):
        rep_l = min(int(row.get(T + "number-rows-repeated", "1")), 1000)
        cels = []
        for c in row:
            if c.tag not in (T + "table-cell", T + "covered-table-cell"):
                continue
            rep = min(int(c.get(T + "number-columns-repeated", "1")), 200)
            v = c.get("{%s}value" % ns["office"]) or c.get("{%s}date-value" % ns["office"])
            if v is None:
                v = "\n".join("".join(p.itertext()) for p in c.findall("text:p", ns))
            cels += [v.strip()] * rep
        while cels and not cels[-1]:
            cels.pop()
        if cels:
            linhas += [cels] * rep_l
        if len(linhas) > 5000:
            break
    if not linhas:
        return []
    cab = linhas[0]
    return [{cab[i]: (l[i] if i < len(l) else "") for i in range(len(cab))} for l in linhas[1:]]


def valor_br(s: str) -> float:
    t = str(s).strip().replace("R$", "").replace(" ", "")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    v = float(t)
    return -v if neg else v


def data_iso(s: str) -> str:
    t = str(s).strip()[:10]
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", t)
    if m:
        t = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    datetime.strptime(t, "%Y-%m-%d")
    return t


class Arquivos:
    def __init__(self, mv: MV, pasta: str | Path | None = None):
        self.mv = mv
        if pasta:
            self.pasta = Path(pasta)
        elif mv.caminho == ":memory:":                 # testes: nunca gravar na pasta atual
            import tempfile
            self.pasta = Path(tempfile.mkdtemp(prefix="physis-mv-arquivos-"))
        else:
            self.pasta = Path(mv.caminho).parent / "arquivos"
        mv.db.executescript(ESQUEMA + mv_editais.ESQUEMA)
        mv.db.commit()

    # ------------------------------------------------------------ receber
    def enviar(self, destino: str, nome: str, conteudo_b64: str, ref: str = "") -> dict:
        if destino not in DESTINOS:
            raise ErroMV("destino inválido (editais, documentos ou financas)")
        if not _REF.match(str(ref or "")):
            raise ErroMV("vínculo inválido")
        ns = nome_seguro(nome)
        ext = ns.rsplit(".", 1)[-1] if "." in ns else ""
        if ext not in DESTINOS[destino]:
            raise ErroMV(f"tipo .{ext or '?'} não aceito aqui; aceitos: {', '.join(sorted(DESTINOS[destino]))}")
        try:
            dados = base64.b64decode(conteudo_b64 or "", validate=True)
        except ValueError:
            raise ErroMV("conteúdo inválido (base64)")
        if not dados:
            raise ErroMV("arquivo vazio")
        if len(dados) > TAMANHO_MAX:
            raise ErroMV("arquivo maior que 10 MB")
        conferir_tipo(dados, ext)
        sha = hashlib.sha256(dados).hexdigest()
        ja = self.mv.db.execute("SELECT * FROM mv_arquivo WHERE destino=? AND sha256=? AND estado!='descartado'", (destino, sha)).fetchone()
        if ja:
            d = self._dic(ja)
            d["duplicado"] = True
            return d
        aid = "arq:" + hashlib.sha256(f"{destino}:{sha}:{time.time()}".encode()).hexdigest()[:16]
        sub = self.pasta / destino / datetime.now().strftime("%Y-%m")
        sub.mkdir(parents=True, exist_ok=True)
        caminho = sub / f"{sha[:12]}_{ns}"
        caminho.write_bytes(dados)
        self.mv.db.execute("INSERT INTO mv_arquivo (id,destino,ref,nome,caminho,extensao,tamanho,sha256,estado,criado) "
                           "VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (aid, destino, str(ref or ""), Path(str(nome)).name[:200], str(caminho), ext, len(dados), sha,
                            "recebido" if (destino, ext) in IMPORTAVEIS else "guardado", time.time()))
        self.mv.db.commit()
        return self.arquivo(aid)

    # ------------------------------------------------------------ consultar
    @staticmethod
    def _dic(r) -> dict:
        d = dict(r)
        d.pop("caminho", None)          # o caminho no disco não sai pela API
        d["importavel"] = (d["destino"], d["extensao"]) in IMPORTAVEIS
        d["quando"] = datetime.fromtimestamp(d["criado"]).strftime("%Y-%m-%d %H:%M")
        return d

    def _linha(self, aid: str):
        if not _ID.match(str(aid or "")):
            raise ErroMV("id inválido")
        r = self.mv.db.execute("SELECT * FROM mv_arquivo WHERE id=?", (aid,)).fetchone()
        if not r:
            raise ErroMV("arquivo não encontrado")
        return r

    def arquivo(self, aid: str) -> dict:
        return self._dic(self._linha(aid))

    def listar(self, destino: str | None = None, ref: str | None = None) -> list[dict]:
        q, a = "SELECT * FROM mv_arquivo WHERE 1=1", []
        if destino:
            q, a = q + " AND destino=?", a + [destino]
        if ref:
            q, a = q + " AND ref=?", a + [ref]
        return [self._dic(r) for r in self.mv.db.execute(q + " ORDER BY criado DESC LIMIT 500", a)]

    def conteudo(self, aid: str) -> tuple[bytes, str]:
        r = self._linha(aid)
        p = Path(r["caminho"]).resolve()
        if self.pasta.resolve() not in p.parents:
            raise ErroMV("caminho fora da pasta de arquivos")
        return p.read_bytes(), r["nome"]

    # ------------------------------------------------------------ prévia e aplicação
    def _linhas(self, r) -> list[dict]:
        dados = Path(r["caminho"]).read_bytes()
        try:
            return ler_ods(dados) if r["extensao"] == "ods" else ler_csv(dados)
        except (KeyError, ET.ParseError, zipfile.BadZipFile, UnicodeDecodeError, csv.Error) as e:
            raise ErroMV(f"não consegui ler a planilha: {e}")

    def previa(self, aid: str) -> dict:
        r = self._linha(aid)
        if (r["destino"], r["extensao"]) not in IMPORTAVEIS:
            return {"id": aid, "importavel": False, "texto": "Arquivo guardado; não alimenta o banco."}
        linhas = self._linhas(r)
        return self._previa_editais(r, linhas) if r["destino"] == "editais" else self._previa_financas(linhas, aid)

    def _previa_editais(self, r, linhas: list[dict]) -> dict:
        if linhas and "titulo" not in linhas[0]:
            raise ErroMV("o CSV de editais precisa da coluna 'titulo' (formato do banco, doc 31, separador ';')")
        novos, atual, itens = 0, 0, []
        for l in linhas:
            eid = "ed:" + hashlib.sha1((l.get("chave") or l.get("titulo", "")).encode()).hexdigest()[:10]
            existe = self.mv.db.execute("SELECT 1 FROM mv_edital WHERE id=?", (eid,)).fetchone() is not None
            novos, atual = novos + (not existe), atual + existe
            itens.append({"titulo": l.get("titulo", "")[:160], "prazo": l.get("prazo", ""), "situacao": "atualiza" if existe else "novo"})
        return {"id": r["id"], "importavel": True, "destino": "editais", "total": len(linhas), "novos": novos,
                "atualizados": atual, "itens": itens[:200], "invalidas": []}

    def _previa_financas(self, linhas: list[dict], aid: str) -> dict:
        validas, invalidas, dup = [], [], 0
        for i, l in enumerate(linhas, start=2):
            x = {COLS_FIN[_sem_acento(k)]: v for k, v in l.items() if _sem_acento(k) in COLS_FIN}
            if not any(str(v).strip() for v in x.values()):
                continue
            try:
                ent = NOMES_ENT.get(_sem_acento(x.get("entidade", "")), _sem_acento(x.get("entidade", "")))
                if ent not in ENTIDADES_FIN:
                    raise ValueError(f"entidade '{x.get('entidade', '')}' (use: {', '.join(ENTIDADES_FIN)})")
                tipo = _sem_acento(x.get("tipo", ""))
                if tipo not in TIPOS_LANC:
                    raise ValueError(f"tipo '{x.get('tipo', '')}' (use: {', '.join(TIPOS_LANC)})")
                try:
                    data = data_iso(x.get("data", ""))
                except ValueError:
                    raise ValueError(f"data '{x.get('data', '')}' (AAAA-MM-DD ou DD/MM/AAAA)")
                try:
                    valor = valor_br(x.get("valor", ""))
                except ValueError:
                    raise ValueError(f"valor '{x.get('valor', '')}'")
                lanc = {"entidade": ent, "data": data, "tipo": tipo, "valor": valor, "descricao": x.get("descricao", "")[:300],
                        "projeto": x.get("projeto", "")[:120], "fonte": (x.get("fonte") or "")[:120]}
                ja = self.mv.db.execute("SELECT 1 FROM mv_lanc WHERE entidade=? AND data=? AND tipo=? AND abs(valor-?)<0.005 AND descricao=?",
                                        (ent, data, tipo, valor, lanc["descricao"])).fetchone()
                lanc["linha"] = i
                lanc["ja_lancado"] = ja is not None
                dup += ja is not None
                validas.append(lanc)
            except ValueError as e:
                invalidas.append({"linha": i, "erro": str(e)})
        return {"id": aid, "importavel": True, "destino": "financas", "total": len(validas) + len(invalidas),
                "validas": len(validas), "ja_lancados": dup, "itens": validas[:300], "invalidas": invalidas[:300],
                "aviso": "Entram como 'a conferir' até a contadora conferir (D70). Cada entidade fica separada."}

    def aplicar(self, aid: str) -> dict:
        r = self._linha(aid)
        if r["estado"] != "recebido":
            raise ErroMV(f"este arquivo já está '{r['estado']}'; nada foi aplicado de novo")
        if (r["destino"], r["extensao"]) not in IMPORTAVEIS:
            raise ErroMV("este arquivo só é guardado; não alimenta o banco")
        if r["destino"] == "editais":
            self.previa(aid)                    # mesma validação da prévia
            txt = ler_texto(Path(r["caminho"]).read_bytes())
            tmp = Path(r["caminho"]).with_suffix(".utf8.csv")
            tmp.write_text(txt, encoding="utf-8")
            try:
                res = mv_editais.Editais(self.mv).importar_csv(tmp)
            finally:
                tmp.unlink(missing_ok=True)
            resumo = f"{res['novos']} novo(s), {res['atualizados']} atualizado(s)"
        else:
            p = self._previa_financas(self._linhas(r), aid)
            if len(p["itens"]) != p["validas"]:
                raise ErroMV("arquivo com mais de 300 linhas: divida em partes")
            n = 0
            for l in p["itens"]:
                if l["ja_lancado"]:
                    continue
                self.mv.lancar({**{k: l[k] for k in ("entidade", "data", "tipo", "valor", "descricao", "projeto")},
                                "fonte": (l["fonte"] or "upload") + f" · {r['nome']}", "conferido": False})
                n += 1
            resumo = f"{n} lançamento(s) a conferir; {p['ja_lancados']} já existiam; {len(p['invalidas'])} linha(s) com erro ignorada(s)"
        self.mv.db.execute("UPDATE mv_arquivo SET estado='aplicado', aplicado=?, resumo=? WHERE id=?", (time.time(), resumo, aid))
        self.mv.db.commit()
        return {**self.arquivo(aid), "resultado": resumo}

    def descartar(self, aid: str) -> dict:
        r = self._linha(aid)
        if r["estado"] == "aplicado":
            raise ErroMV("já aplicado: corrija pelos lançamentos/fichas, não descartando o arquivo")
        self.mv.db.execute("UPDATE mv_arquivo SET estado='descartado' WHERE id=?", (aid,))
        self.mv.db.commit()
        return self.arquivo(aid)


MODELO_FINANCAS = "entidade;data;tipo;valor;descricao;projeto;fonte\ncasa;2026-11-19;despesa;1.234,56;[exemplo] material;Casa;NF 123\n"
