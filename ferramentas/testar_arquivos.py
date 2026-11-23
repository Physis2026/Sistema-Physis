#!/usr/bin/env python3
r"""Teste de leitura, revisão e salvamento de arquivos do Physis M&A (23/11/2026).

    cd C:\physis\physis-ma-20261122-1bd599e
    py ferramentas\testar_arquivos.py

A. LEITURA (só lê): em cada pasta do OneDrive que os bots usam, conta os arquivos e lê até 5 de cada tipo
   (md, txt, odt, ods, odp, docx, xlsx, pptx). Arquivo com tamanho mas sem texto = não leu (ex.: arquivo "só online").
B. REVISÃO (só lê): passa as regras do bot documentos nos arquivos lidos e conta falhas e [MARCADOR].
C. SALVAMENTO (numa pasta temporária, apagada no fim): gera ODT e versão zero do kit, relê; envia, confere e aplica
   uma planilha de finanças num banco de teste; descarta outra; move um arquivo para antigos/; copia o banco real
   (cópia de leitura) e confere a integridade da cópia. Na pasta de saída dos bots (28_Physis_MV) só cria e apaga
   um arquivo de 1 linha para saber se dá para gravar lá.
Nada do banco real nem dos documentos é alterado. O relatório fica em teste-arquivos-AAAAMMDD-HHMM.md nesta pasta.
"""
from __future__ import annotations

import base64
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "physis-hub"))
try:
    sys.stdout.reconfigure(errors="replace")
except (AttributeError, ValueError):
    pass

from physis_hub import mv_bots, mv_comandos, mv_kit, mv_semente, mv_arquivos, mv_repositorios  # noqa: E402
from physis_hub.mv import MV, pasta_padrao  # noqa: E402
from physis_hub.documentos import odt  # noqa: E402

TIPOS = (".md", ".txt", ".odt", ".ods", ".odp", ".docx", ".xlsx", ".pptx")
linhas, falhas = [], []


def diz(t: str = "") -> None:
    print(t, flush=True)
    linhas.append(t)


def item(nome: str, ok: bool, detalhe: str = "") -> None:
    diz(f"- {'OK   ' if ok else 'FALHA'} {nome}" + (f": {detalhe}" if detalhe else ""))
    if not ok:
        falhas.append(f"{nome}: {detalhe}")


def leitura_e_revisao() -> None:
    diz("## A. Leitura e B. revisão (só lê)")
    pastas = mv_bots.pastas_documentos() + mv_repositorios.caminhos_existentes()
    for pasta in pastas:
        if not pasta.is_dir():
            item(pasta.name, False, f"pasta não encontrada ({pasta})")
            continue
        total, por_tipo, lidos, sem_texto, com_falha, marcadores, erros = 0, {}, 0, [], 0, 0, []
        for dp, dirs, arqs in os.walk(pasta):
            if mv_bots.IGNORAR.search(dp + os.sep):
                dirs[:] = []
                continue
            for a in arqs:
                p = Path(dp) / a
                ext = p.suffix.lower()
                if ext not in mv_bots.EXTS or a.startswith(("~$", ".")):
                    continue
                total += 1
                if ext not in TIPOS or por_tipo.get(ext, 0) >= 5:
                    continue
                por_tipo[ext] = por_tipo.get(ext, 0) + 1
                try:
                    tam = p.stat().st_size
                    txt = mv_bots.texto_de(p)
                except Exception as e:  # noqa: BLE001
                    erros.append(f"{a} ({e!r})"[:120])
                    continue
                if tam > 0 and not txt.strip():
                    sem_texto.append(a)
                    continue
                lidos += 1
                f, m = mv_bots.conferir_texto(txt)
                com_falha += bool(f)
                marcadores += m
        diz(f"### {pasta.name}")
        item(f"{pasta.name}: arquivos encontrados", total > 0, f"{total} ({', '.join(f'{k}: {v}' for k, v in sorted(por_tipo.items())) or 'nenhum legível'} testados)")
        item(f"{pasta.name}: leitura", not erros and (lidos > 0 or not por_tipo), f"{lidos} lidos" + (f"; erros: {'; '.join(erros[:3])}" if erros else ""))
        if sem_texto:
            item(f"{pasta.name}: arquivos sem texto", False, f"{len(sem_texto)} (provável 'só online' no OneDrive ou arquivo vazio): {', '.join(sem_texto[:4])}")
        diz(f"- revisão: {com_falha} arquivo(s) com falha pelas regras, {marcadores} [MARCADOR] (informação, não é erro do teste)")


def salvamento() -> None:
    diz("")
    diz("## C. Salvamento (pasta temporária)")
    tmp = Path(tempfile.mkdtemp(prefix="physis-teste-arquivos-"))
    try:
        # 1. ODT gerado e relido
        arq = tmp / "teste.odt"
        arq.write_bytes(odt("Teste de salvamento", [{"t": "Linha de conferência do teste de arquivos."}], sistema="Physis M&A", logo_png=False))
        ok = zipfile.is_zipfile(arq) and "Linha de conferência" in mv_bots.texto_de(arq)
        item("gerar e reler ODT", ok)
        # 2. versão zero do kit
        mv = MV(":memory:")
        mv_semente.semear(mv)
        vz = tmp / "versao-zero.odt"
        vz.write_bytes(mv_kit.versao_zero(mv, "casa", "apresentacao"))
        t = mv_bots.texto_de(vz)
        item("versão zero do kit (ODT)", "[MARCADOR]" in t and len(t) > 50, f"{len(t)} caracteres")
        # 3. envio, prévia, aplicação e descarte (banco de teste)
        mvt = MV(str(tmp / "teste.db"))
        a = mv_arquivos.Arquivos(mvt, tmp / "arquivos")
        csv = "entidade;data;tipo;valor;descricao;projeto;fonte\ncasa;2026-11-23;despesa;10,50;teste de salvamento;Teste;NF 0\n"
        r = a.enviar("financas", "teste.csv", base64.b64encode(csv.encode()).decode())
        pv = a.previa(r["id"])
        ap = a.aplicar(r["id"])
        n = mvt.db.execute("SELECT COUNT(*) FROM mv_lanc WHERE descricao='teste de salvamento'").fetchone()[0]
        item("enviar → prévia → aplicar planilha", n == 1, f"prévia ok={bool(pv)}, aplicado={ap.get('estado', ap)}")
        r2 = a.enviar("documentos", "rascunho.md", base64.b64encode(b"# Rascunho\n\ntexto").decode())
        d = a.descartar(r2["id"])
        item("descartar arquivo enviado", d.get("estado") == "descartado", str(d.get("estado")))
        mvt.db.close()
        # 4. reprovado/descartado vai para antigos/
        f = tmp / "kit" / "artigo.odt"
        f.parent.mkdir()
        f.write_bytes(b"x")
        dest = mv_comandos.mover_para_antigos(f)
        item("mover para antigos/", dest.is_file() and not f.exists() and dest.parent.name == "antigos")
        # 5. cópia do banco real (leitura) e integridade
        real = pasta_padrao() / "physis-mv.db"
        if real.is_file():
            origem = sqlite3.connect(f"file:{real}?mode=ro", uri=True)
            copia = sqlite3.connect(tmp / "copia.db")
            origem.backup(copia)
            res = copia.execute("PRAGMA integrity_check").fetchone()[0]
            n = copia.execute("SELECT COUNT(*) FROM mv_tarefa").fetchone()[0]
            copia.close()
            origem.close()
            item("cópia do banco real + integridade", res == "ok", f"{res}; {n} tarefas na cópia")
        else:
            item("cópia do banco real", False, f"banco não encontrado em {real}")
        # 6. pode gravar na pasta de saída dos bots?
        saida = mv_bots.SAIDA
        try:
            saida.mkdir(parents=True, exist_ok=True)
            marca = saida / "_teste_escrita.tmp"
            marca.write_text("teste", encoding="utf-8")
            lido = marca.read_text(encoding="utf-8")
            marca.unlink()
            item("gravar na pasta dos bots", lido == "teste", str(saida))
        except OSError as e:
            item("gravar na pasta dos bots", False, f"{saida}: {e}")
    except Exception as e:  # noqa: BLE001
        item("salvamento", False, repr(e)[:300])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    diz(f"# Teste de arquivos do Physis M&A · {time.strftime('%d/%m/%Y %H:%M')}")
    diz(f"Documentos: {mv_bots.DOCS}")
    diz("")
    leitura_e_revisao()
    salvamento()
    diz("")
    diz("## Resultado")
    diz("- Tudo OK." if not falhas else "\n".join(f"- [ ] {f}" for f in falhas))
    rel = Path(__file__).resolve().parent.parent / f"teste-arquivos-{time.strftime('%Y%m%d-%H%M')}.md"
    rel.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"\nRelatório: {rel}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
