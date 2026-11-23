"""Gera sistema/physis-plantas.json a partir das planilhas v88 da Physis (Seletor_Plantas e Plano_Viveiro)."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from ler_xlsx import abrir, linhas  # noqa: E402

import os  # noqa: E402
B = Path(os.environ.get("PHYSIS_DOCS") or (Path.home() / "OneDrive - Physis Engineering" / "Documents")) / "Sistema Physis" / "Modulos em desenvolvimento"
SAIDA = Path(__file__).resolve().parents[1] / "sistema" / "physis-plantas.json"
FUNCOES = [("ar", "I", "Filtra o ar"), ("agua", "J", "Filtra a água"), ("solo", "K", "Recupera e filtra o solo"),
           ("barranco", "L", "Segura barranco"), ("nitrogenio", "M", "Fixa nitrogênio"), ("biomassa", "N", "Biomassa para composto e biogás"),
           ("polinizadores", "O", "Atrai polinizadores e abelhas"), ("alimento", "P", "Alimento para pessoas"), ("animais", "Q", "Alimento para animais"),
           ("protecao", "R", "Proteção (repele pragas, planta-isca)"), ("oleo", "S", "Óleo essencial"), ("medicinal", "T", "Erva medicinal"),
           ("sombra", "U", "Sombra e quebra-vento"), ("ornamental", "V", "Flores e ornamental")]


def tabela(arq, aba):
    z, ss, abas = abrir(arq)
    return list(linhas(z, ss, dict(abas)[aba]))


def num(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sel = B / "Seletor_Plantas_v88.xlsx"
    plantas = []
    for r, v in tabela(sel, "Catálogo"):
        if r < 2 or not v.get("B") or not str(v.get("A", "")).strip().isdigit():
            continue
        plantas.append({"n": int(v["A"]), "nome": v["B"], "cientifico": v.get("C", ""), "tipo": v.get("D", ""),
                        "origem": v.get("E", ""), "porte": v.get("F", ""), "luz": v.get("G", ""), "preco": num(v.get("H")),
                        "funcoes": [k for k, col, _ in FUNCOES if (v.get(col) or "").strip() == "✓"],
                        "espacos": [int(x) for x in re.findall(r"\d+", v.get("X", ""))],
                        "adaptacao": v.get("Y", ""), "plantio": v.get("Z", ""), "colheita": v.get("AA", ""), "imagem": ""})
    espacos = []
    for r, v in tabela(sel, "Mapa"):
        if r < 4 or not str(v.get("A", "")).strip().isdigit():
            continue
        covas = v.get("D", "")
        m2 = re.match(r"([\d.]+)\s*m²", str(covas))
        espacos.append({"n": int(v["A"]), "nome": v.get("B", ""), "zona": v.get("C", ""),
                        "covas": None if m2 else num(covas), "area_m2": num(m2.group(1)) if m2 else None,
                        "recomendada": v.get("F", "")})
    comb = {}
    for r, v in tabela(sel, "Combinações"):
        if r < 4 or not str(v.get("A", "")).strip().isdigit():
            continue
        comb[int(v["A"])] = {"A": v.get("D", ""), "B": v.get("E", ""), "C": v.get("F", "")}
    for e in espacos:
        e["combinacoes"] = comb.get(e["n"], {})
    # viveiro: passo zero (como produzir cada muda)
    viv = []
    pv = B / "Plano_Viveiro_v88.xlsx"
    if not pv.is_file():
        achados = list(B.rglob("Plano_Viveiro_v88.xlsx"))
        pv = achados[0] if achados else None
    cab = None
    if pv:
        for r, v in tabela(pv, "Passo zero"):
            vals = {k: str(x).strip() for k, x in v.items()}
            if cab is None:
                if any("Muda" in x or "muda" in x for x in vals.values()) and len(vals) >= 5:
                    cab = vals
                continue
            if len(vals) >= 4:
                viv.append({cab.get(k, k): x for k, x in vals.items() if x})
    dados = {"_leia": "Base de plantas, espaços, combinações e viveiro da Physis (planilhas v88 da Casa Physis). Ampliável para outros clientes: acrescente plantas e espaços.",
             "funcoes": [{"id": k, "nome": n} for k, _, n in FUNCOES], "plantas": plantas, "espacos": espacos, "viveiro": viv[:200]}
    SAIDA.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(plantas), "plantas ·", len(espacos), "espaços ·", len(viv), "linhas de viveiro · cabeçalho viveiro:", list((cab or {}).values())[:12])


if __name__ == "__main__":
    main()
