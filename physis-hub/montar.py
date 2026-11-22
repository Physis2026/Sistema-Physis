#!/usr/bin/env python3
"""Monta a plataforma de um cliente só com os módulos comprados.

É o passo que roda depois da confirmação do pagamento. Gera uma pasta (e um .zip)
com o computador central, a tela, a documentação e um `instancia.json` que diz
quais módulos estão ativos e que o primeiro acesso exige cadastro e senha.

  python3 montar.py --org fazenda-boa-vista --modulos monitoramento,sustainkit \\
                    --sustainkit /caminho/SustainKit_Definitivo.html --saida /tmp/entrega

Módulos aceitos: monitoramento, zonas, animais, sustainkit, supervisao.
A plataforma sai ZERADA: sem simulador e sem dados. Quem recebe liga os próprios dispositivos.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
# "animais" = coleiras + comedouros (nome antigo, aceito); os demais com aba "em desenvolvimento" na plataforma
MODULOS = ("monitoramento", "agua", "zonas", "animais", "coleiras", "comedouros", "sustainkit", "supervisao", "gestao",
           "painel", "planejador", "certificacoes", "solar", "avac", "turbinas", "sbn", "circular", "carbono",
           "resiliencia", "medicamentos", "pulseira", "cursos", "secador", "servidor-verde",
           "frota",         # Frota e combustível (em desenvolvimento, 18/11/2026)
           "validacao")     # Validação · planejado × gerado, M&V (em desenvolvimento, 18/11/2026)
LICENCA_PADRAO = "Licença Physis de Uso e Adaptação (minuta em revisão jurídica)"
VENDOR_ARQUIVOS = ("maplibre-gl.js", "maplibre-gl.css", "pmtiles.js", "web-ifc-api-iife.js", "web-ifc.wasm", "three.min.js",
                   "LEIA-ME.md", "LICENSE-maplibre-gl.txt", "LICENSE-three.txt",
                   # three.js 0.170 em módulos (vista 3D; mesma lista de servidor.THREE_MODULOS)
                   "three/LICENSE", "three/SHA256.json", "three/three.module.min.js") + tuple("three/addons/" + a for a in (
    "postprocessing/EffectComposer.js", "postprocessing/Pass.js", "postprocessing/RenderPass.js", "postprocessing/ShaderPass.js",
    "postprocessing/MaskPass.js", "postprocessing/OutputPass.js", "postprocessing/GTAOPass.js", "shaders/CopyShader.js",
    "shaders/OutputShader.js", "shaders/GTAOShader.js", "shaders/PoissonDenoiseShader.js", "math/SimplexNoise.js",
    "loaders/GLTFLoader.js", "utils/BufferGeometryUtils.js"))
# demonstrações públicas (demos/, servidas em /demo/<nome>/): só no pacote do servidor da Physis (o site)
DEMOS_ARQUIVOS = ("physis-demo-sustainkit.html", "physis-demo-scada.html", "physis-demo-monitoramento.html",
                  "physis-demo-planejador.html", "physis-demo-cliente.html")
# download do app (/app/baixar, /app/android.apk): só estes nomes saem de app-nativo/site; chave de assinatura nunca
APP_DOWNLOAD_ARQUIVOS = ("baixar.html", "android.apk", "android.apk.sha256")

GUIA = """# Sua plataforma Physis

Organização: {org} · Lugar: {lugar} · Módulos: {modulos}
Montada em {quando}.

## 1. Ligar

Precisa só de Python 3.10 ou mais novo, num computador ou Raspberry Pi da sua rede.

    python3 -m physis_hub.servidor

Abra no navegador `http://<endereço deste computador>:8700/`.

## 2. Primeiro acesso

Na primeira abertura a tela pede o seu nome, um usuário e uma senha de pelo menos 10 caracteres.
Quem cria esse acesso passa a ser a pessoa administradora. A senha fica guardada só neste
computador, de forma protegida; ninguém na Physis a recebe. Se for esquecida, apague o arquivo
`physis-hub.db` para recomeçar (isso apaga também os dados guardados).

## 3. A plataforma chega zerada

Sem equipamento, não há dados. Para ligar os seus dispositivos:

- **Receptor V6 da Physis:** na configuração do receptor, informe o endereço deste computador
  e a porta 8700. Ele entrega as leituras em `/api/gateway/webhook`.
- **Dispositivo próprio com Wi-Fi:** envie uma linha por leitura para `/api/v6/linha`.
  O formato está em `docs/PROTOCOLO.md` e `docs/EXTENSAO_V6.md`.
- **Sem equipamento:** na tela "Teste e diagnóstico", injete uma linha de exemplo.
{sk}
## 4. Código aberto

Todo o código está nesta pasta e pode ser estudado e adaptado. Licença: {licenca}

## 5. Conferir a instalação

    python3 -m unittest discover -s tests
"""


def texto_licenca(nome: str) -> str:
    """O texto da licença que vai no pacote: o das minutas (sistema/physis-juridico.js), quando existir."""
    arq = AQUI.parent / "sistema" / "physis-juridico.js"
    try:
        dados = json.loads(arq.read_text(encoding="utf-8").split("window.PHYSIS_JURIDICO = ", 1)[1].rstrip().rstrip(";"))
        linhas = [nome, "", f"Situação: {dados['situacao']} · versão de {dados['versao']}", ""]
        for b in dados["licenca"]["blocos"]:
            linhas += [b["t"]] if b["t"] else []
            linhas += [re.sub(r"\*\*?([^*]+)\*\*?", r"\1", x) for x in b["p"]] + [""]
        return "\n".join(linhas)
    except (OSError, IndexError, KeyError, ValueError):
        return nome + "\n"


def escrever_manual(pasta: Path, modulos: list[str], cliente: str) -> Path:
    """Rascunho do manual desta compra (só os módulos do pacote) em manual/: .md para revisar e .odt.
    Não é o manual emitido: a versão final passa pela fila de emissão (revisão e aprovação) no servidor da Physis."""
    if str(AQUI) not in sys.path:
        sys.path.insert(0, str(AQUI))
    from physis_hub import documentos_auto
    c = documentos_auto.compor_manual(modulos, {"cliente": {"nome": cliente}, "hoje": time.strftime("%d/%m/%Y")})
    (pasta / "manual").mkdir(exist_ok=True)
    md = pasta / "manual" / "MANUAL-RASCUNHO.md"
    md.write_text(c["texto"], encoding="utf-8", newline="\n")       # UTF-8 com LF também quando montado no Windows
    (pasta / "manual" / "MANUAL-RASCUNHO.odt").write_bytes(documentos_auto.odt_de_texto(c["texto"], "Manual da plataforma Physis", rascunho=True))
    return md


def montar(org: str, lugar: str, modulos: list[str], saida: Path, sustainkit: Path | None, licenca: str,
           supervisao: Path | None = None, gestao: Path | None = None, planejador: Path | None = None,
           pesquisa: bool = False, nome: str = "", cursos: list | None = None, suporte: dict | None = None,
           pegada: dict | None = None, marca: dict | None = None) -> Path:
    """marca (opcional): marca própria da instalação, como a da Casa Physis ({nome, logo_texto, logo_clara, logo_escura},
    logos = caminhos de arquivos SVG). As logos vão para web/marca/ e o painel as mostra no lugar da logo da Physis."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,63}", org):
        raise SystemExit("org: use de 2 a 64 letras minúsculas, números, ponto, hífen ou sublinhado")
    desconhecidos = [m for m in modulos if m not in MODULOS]
    if desconhecidos:              # lista vazia é a plataforma básica: Início e Cursos
        raise SystemExit(f"módulos aceitos: {', '.join(MODULOS)}; recebi: {', '.join(desconhecidos) or 'nenhum'}")
    if "sustainkit" in modulos and (sustainkit is None or not sustainkit.is_file()):
        raise SystemExit("o módulo sustainkit precisa de --sustainkit apontando para o arquivo HTML do SustainKit")
    if "supervisao" in modulos and (supervisao is None or not supervisao.is_file()):
        raise SystemExit("o módulo supervisao precisa de --supervisao apontando para o arquivo HTML da supervisão")
    if "planejador" in modulos and (planejador is None or not planejador.is_file()):
        raise SystemExit("o módulo planejador precisa de --planejador apontando para o arquivo HTML do Planejador")
    pasta = saida / f"physis-{org}"
    if pasta.exists():
        shutil.rmtree(pasta)
    (pasta / "web").mkdir(parents=True)
    shutil.copytree(AQUI / "physis_hub", pasta / "physis_hub", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(AQUI / "tests", pasta / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(AQUI / "docs", pasta / "docs")
    shutil.copy2(AQUI / "web" / "painel.html", pasta / "web" / "painel.html")
    if org == "physis-site":    # a loja do site abre com o catálogo inicial (servidor.semear_loja; ferramentas/gerar_loja_catalogo.py)
        shutil.copy2(AQUI.parent / "sistema" / "loja-catalogo-inicial.json", pasta / "loja-catalogo-inicial.json")
    if (AQUI / "web" / "app").is_dir():      # app instalável no celular (manifesto, ícones, service worker)
        shutil.copytree(AQUI / "web" / "app", pasta / "web" / "app")
    # documento para comentários (/documento/<id>): toda plataforma tem equipe que publica e revisor que comenta
    if (AQUI / "web" / "documento.html").is_file():
        shutil.copy2(AQUI / "web" / "documento.html", pasta / "web" / "documento.html")
    # painel municipal de resiliência (/municipio): com o módulo resiliência ou na instalação de pesquisa
    if ("resiliencia" in modulos or pesquisa) and (AQUI / "web" / "municipio.html").is_file():
        shutil.copy2(AQUI / "web" / "municipio.html", pasta / "web" / "municipio.html")
    # termos, privacidade e acessibilidade (/termos, /privacidade, /acessibilidade) e a versão dos termos do consentimento
    juridico = AQUI.parent / "sistema" / "physis-juridico.js"
    if juridico.is_file():
        shutil.copy2(juridico, pasta / "web" / "physis-juridico.js")
    # página de download do app (/app/baixar): o publicado (com APK e SHA-256) ou, sem ele, a página modelo
    if (gestao is not None and gestao.is_file()) or pesquisa:
        site =AQUI.parent / "app-nativo" / "site"
        origens = [site / "publicar" / n for n in APP_DOWNLOAD_ARQUIVOS if (site / "publicar" / n).is_file()]
        if not origens and (site / "baixar.html").is_file():
            origens = [site / "baixar.html"]
        if origens:
            (pasta / "app-download").mkdir()
            for o in origens:
                shutil.copy2(o, pasta / "app-download" / o.name)
    if (AQUI.parent / "implantacao").is_dir():   # instalador do Raspberry/mini PC, backup, atualização e verificação
        shutil.copytree(AQUI.parent / "implantacao", pasta / "implantacao", ignore=shutil.ignore_patterns("*.env"))
    if "sustainkit" in modulos:
        shutil.copy2(sustainkit, pasta / "web" / "sustainkit.html")
    if "supervisao" in modulos:
        shutil.copy2(supervisao, pasta / "web" / "supervisao.html")
    if "planejador" in modulos:
        shutil.copy2(planejador, pasta / "web" / "planejador.html")
    if "planejador" in modulos or (gestao is not None and gestao.is_file()):
        # mapa e leitor BIM do Planejador: bibliotecas abertas, entregues pelo próprio servidor (sem internet).
        # O pacote do servidor da Physis também leva, para montar sozinho a plataforma de quem compra.
        (pasta / "web" / "vendor").mkdir(exist_ok=True)
        for nome in VENDOR_ARQUIVOS:
            origem = next((p for p in (AQUI.parent / "vendor" / nome, AQUI / "web" / "vendor" / nome) if p.is_file()), None)
            if origem:
                (pasta / "web" / "vendor" / nome).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origem, pasta / "web" / "vendor" / nome)
    if gestao is not None and gestao.is_file():      # só o pacote interno da Physis leva o programa de gestão interna
        shutil.copy2(gestao, pasta / "web" / "gestao.html")
        if (AQUI / "web" / "consultoria.html").exists():      # página pública de consultoria do site da Physis
            shutil.copy2(AQUI / "web" / "consultoria.html", pasta / "web" / "consultoria.html")
        demos = [AQUI.parent / "demos" / n for n in DEMOS_ARQUIVOS if (AQUI.parent / "demos" / n).is_file()]
        if demos:                                           # demonstrações do site (/demo/<nome>/)
            (pasta / "web" / "demos").mkdir(exist_ok=True)
            for d in demos:
                shutil.copy2(d, pasta / "web" / "demos" / d.name)
        # o servidor da Physis monta sozinho a plataforma de quem compra: leva o montador e os programas
        shutil.copy2(AQUI / "montar.py", pasta / "montar.py")
        (pasta / "programas").mkdir(exist_ok=True)
        for prog in (sustainkit, supervisao, planejador):
            if prog is not None and prog.is_file():
                shutil.copy2(prog, pasta / "programas" / prog.name)
    inst = {"org": org, "lugar": lugar, "modulos": modulos, "login": True, "licenca": licenca,
            "montada_em": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if nome:
        inst["nome"] = nome
    if pesquisa:      # instalação de pesquisa: mostra também o que está em desenvolvimento, marcado como tal
        inst["pesquisa"] = True
    # cursos da aba Cursos: comprados ou liberados gratuitamente pela Physis ({nome, link https, gratuito, carga...})
    inst["cursos"] = [c for c in (cursos or []) if isinstance(c, dict) and c.get("nome")]
    # canais de suporte da Physis (configuração, nunca no código): e-mail e WhatsApp da Gestão → Suporte
    if suporte:
        inst["suporte_email"] = str(suporte.get("email") or "")
        inst["suporte_whatsapp"] = str(suporte.get("whatsapp") or "")
    if pegada:          # pegada do servidor (docs/PEGADA_SERVIDOR.md): classe da máquina, lugar e forma de contar
        inst["pegada_servidor"] = pegada
    if marca:           # marca própria (ex.: Casa Physis): nome, texto do título e logos clara e escura, servidas em /marca/
        m = {k: str(marca[k])[:80] for k in ("nome", "logo_texto") if marca.get(k)}
        for tom in ("clara", "escura"):
            origem = Path(marca.get(f"logo_{tom}") or "")
            if origem.suffix.lower() == ".svg" and origem.is_file():
                (pasta / "web" / "marca").mkdir(exist_ok=True)
                shutil.copy2(origem, pasta / "web" / "marca" / f"logo-{tom}.svg")
                m[f"logo_{tom}"] = f"/marca/logo-{tom}.svg"
        inst["instalacao"], inst["marca"] = org, m
    (pasta / "instancia.json").write_text(json.dumps(inst, ensure_ascii=False, indent=2), encoding="utf-8")
    (pasta / "LICENSE").write_text(texto_licenca(licenca), encoding="utf-8")
    sk = ("- **SustainKit:** já funciona, sem equipamento. Abra pela aba SustainKit.\n"
          if "sustainkit" in modulos else "")
    (pasta / "LEIA-ME.md").write_text(GUIA.format(org=org, lugar=lugar, modulos=", ".join(modulos),
                                                  quando=time.strftime("%d/%m/%Y"), sk=sk, licenca=licenca), encoding="utf-8")
    if (AQUI / "modelos").is_dir():          # modelos dos documentos automáticos (docs/DOCUMENTOS_AUTOMATICOS.md)
        shutil.copytree(AQUI / "modelos", pasta / "modelos")
    escrever_manual(pasta, modulos, nome or org)
    pacote = saida / f"physis-{org}.zip"
    with zipfile.ZipFile(pacote, "w", zipfile.ZIP_DEFLATED) as z:
        for arq in sorted(pasta.rglob("*")):
            if arq.is_file():
                z.write(arq, arq.relative_to(saida))
    return pacote


def main() -> None:
    ap = argparse.ArgumentParser(description="Monta a plataforma de um cliente com os módulos comprados.")
    ap.add_argument("--org", required=True)
    ap.add_argument("--lugar", default="lugar01")
    ap.add_argument("--modulos", required=True, help="lista separada por vírgula")
    ap.add_argument("--sustainkit", type=Path)
    ap.add_argument("--supervisao", type=Path, help="arquivo HTML da supervisão (physis-scada-demo.html)")
    ap.add_argument("--gestao", type=Path, help="arquivo HTML da gestão (gestao-physis.html)")
    ap.add_argument("--planejador", type=Path, help="arquivo HTML do Planejador Physis")
    ap.add_argument("--pesquisa", action="store_true", help="instalação de pesquisa: mostra também o que está em desenvolvimento")
    ap.add_argument("--nome", default="", help="nome do cliente para a tela")
    ap.add_argument("--licenca", default=LICENCA_PADRAO)
    ap.add_argument("--saida", type=Path, default=Path("entregas"))
    ap.add_argument("--suporte-email", default="", help="e-mail de suporte desta instalação")
    ap.add_argument("--suporte-whatsapp", default="", help="WhatsApp de suporte desta instalação")
    a = ap.parse_args()
    a.saida.mkdir(parents=True, exist_ok=True)
    suporte = {"email": a.suporte_email, "whatsapp": a.suporte_whatsapp} if (a.suporte_email or a.suporte_whatsapp) else None
    pacote = montar(a.org, a.lugar, [m.strip() for m in a.modulos.split(",") if m.strip()], a.saida, a.sustainkit, a.licenca,
                    a.supervisao, a.gestao, a.planejador, a.pesquisa, a.nome, None, suporte)
    print(f"Montado: {pacote} ({pacote.stat().st_size // 1024} kB)")


if __name__ == "__main__":
    main()
