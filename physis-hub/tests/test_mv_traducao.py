"""Tradução EN do Physis M&A (20/11/2026; dona: "nem todas as informações nas páginas em inglês estão sendo traduzidas, verificar
minuciosamente"). Todo texto fixo da tela (texto entre tags, placeholder, aria-label, title) que esteja em português precisa ter
tradução no dicionário EN da própria tela. Textos montados por script são conferidos pela auditoria no navegador (doc 43)."""
import html as H
import re
import unittest
from pathlib import Path

MV = Path(__file__).resolve().parents[1] / "web" / "mv.html"
PT = re.compile(r"[ãõçáéíóúâêôà]|\b(de|da|do|das|dos|para|com|sem|não|uma|por|que|tarefa|tarefas|prazo|frente|feitas|conferir|projeto|"
                r"projetos|nota|pessoa|documento|documentos|aprovar|enviar|lançamento|entidade|semana|hoje|escopo|fase|conta|resumo|"
                r"arquivo|galeria|todas|todos|novo|nova|buscar|ordenar)\b", re.I)
EXCECOES = {"Português", "English", "Physis M&A", "Physis Engineering · Physis M&A", "Physis Engineering", "Petrópolis/RJ"}


def dicionario(fonte: str) -> set[str]:
    chaves = set(re.findall(r'"((?:[^"\\]|\\.)*)"\s*:\s*"', fonte))
    chaves |= set(re.findall(r'EN\["((?:[^"\\]|\\.)*)"\]\s*=', fonte))
    return {c.replace('\\"', '"') for c in chaves}


def textos_fixos(fonte: str) -> set[str]:
    sem = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", "", fonte)
    corpo = sem[sem.find("<body"):]
    txt = {H.unescape(" ".join(t.split())) for t in re.findall(r">([^<>]+)<", corpo)}
    for a in ("placeholder", "aria-label", "title"):
        txt |= {H.unescape(v) for v in re.findall(rf'\b{a}="([^"$]+)"', corpo)}
    return {t for t in txt if t.strip() and PT.search(t) and t not in EXCECOES and not t.startswith("[")}


class TraducaoMA(unittest.TestCase):
    def test_todo_texto_fixo_tem_ingles(self):
        fonte = MV.read_text(encoding="utf-8")
        d = dicionario(fonte)
        faltam = sorted(t for t in textos_fixos(fonte) if t not in d)
        self.assertEqual(faltam, [], "textos fixos do M&A sem tradução em inglês")


if __name__ == "__main__":
    unittest.main()
