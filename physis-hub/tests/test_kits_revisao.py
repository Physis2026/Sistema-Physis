"""Kits de revisão por módulo (ferramentas/gerar_kits_revisao.py e ferramentas/validar_devolucao.py).

1. O gerador cria um kit para cada módulo de ferramentas/kits/modulos.json, com os responsáveis confirmados,
   e o MANIFESTO.json tem o SHA-256 certo de cada arquivo.
2. O validador aceita kit sem mudança e mudança de valor; recusa chave ou id apagado, tipo trocado,
   referência mudada, script ou endereço de internet, arquivo a mais e segredo em arquivo de texto.
3. Se a parte do arquivo mudou no sistema depois do kit, para (junção em 3 vias).
4. A aplicação mantém a formatação do arquivo e, no Git, vai para uma branch revisao/... e volta.
Os testes do validador rodam numa cópia temporária (não dependem do que outros estão mudando no repositório).
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
FERR = RAIZ / "ferramentas"
NO_REPO = (FERR / "gerar_kits_revisao.py").is_file() and (FERR / "kits" / "modulos.json").is_file()
if NO_REPO:
    sys.path.insert(0, str(FERR))
    import gerar_kits_revisao as G  # noqa: E402
    import validar_devolucao as V  # noqa: E402

RESPONSAVEIS = {
    "planejador": ["Rafaella", "Eric Oliveira", "Erick Lopes", "Arthur", "Rafael", "Emerson", "Ryan", "Laura", "Marzia",
                   "Leonardo Macedo"],
    "sustainkit": ["Erick Lopes"], "solar": ["Erick Lopes"], "avac": ["Ryan"], "turbinas": ["Emerson", "Ryan"],
    "agua": ["Erick Lopes", "Rafael"], "sbn": ["Erick Lopes", "Rafaella"], "circular": ["Rafael", "Rafaella"],
    "carbono": ["Marzia", "Laura"], "resiliencia": ["Arthur", "Rafaella"],
    "certificacoes": ["Erick Lopes", "Ryan", "Laura", "Rafaella"], "equipamentos": ["Ryan", "Erick Lopes"],
    "monitoramento": ["Arthur"], "saude": ["Rafael", "Emerson"], "scada": ["Erick Lopes", "Laura", "Rafaella"],
    "cursos": ["Laura", "Marzia", "Ryan", "Leonardo Macedo", "Rafaella"], "secador": ["Arthur", "Laura", "Rafaella"],
    "frota": ["Rafael"],                                    # decisão de 18/11/2026
    "validacao": ["Erick Lopes", "Arthur", "Rafael"],       # Validação · planejado × gerado (M&V), decisão de 18/11/2026
    "servidor-verde": ["Eric Oliveira"],
    "acessibilidade": ["Rafaella", "Arthur", "Emerson", "Leonardo Macedo", "Laura", "Marzia"],
    "mapeamento": ["Rafaella", "Eric Oliveira", "Erick Lopes", "Arthur", "Rafael", "Emerson", "Ryan", "Laura", "Marzia",
                   "Leonardo Macedo"],                      # os do Planejador (principal: Rafaella)
    "hw-lora": ["Arthur"], "hw-caixinha": ["Erick Lopes", "Arthur", "Rafael", "Emerson", "Laura"],
    "hw-coleira": ["Rafael"], "hw-pluviometro": ["Arthur"], "hw-remedios": ["Rafael", "Emerson"],
    "hw-pulseira": ["Emerson"], "servidor": ["Eric Oliveira"],
}
DATA = "2026-11-15"
COPIAR = ["sistema/physis-metodologia.json", "sistema/physis-premissas.json", "sistema/physis-plantas.json",
          "sistema/physis-fatores-emissao.json", "sistema/physis-sbn.js", "sistema/physis-i18n-modulos.json",
          "firmware/caixinha/esphome/irrigacao-zona1.yaml", "firmware/pluviometro/parametros.json",
          "firmware/saude/parametros-pulseira.json", "ferramentas/kits/modulos.json"]
EXTERNO = r"https?://|//cdn|\bwww\.|@import|<link\b|src=[\"'](?!data:)[^\"'#]"


def git_ok():
    try:
        return subprocess.run([G.git_exe(), "--version"], capture_output=True).returncode == 0
    except OSError:
        return False


@unittest.skipUnless(NO_REPO, "só no repositório")
class TestGerador(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="kits-"))
        cls.mapa = G.carregar_mapa()
        cls.saida = cls.tmp / "kits"
        with contextlib.redirect_stdout(io.StringIO()):
            G.main(["--saida", str(cls.saida), "--data", DATA, "--sem-zip", "--documentos", str(cls.tmp / "nada")])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_mapa_com_responsaveis_confirmados(self):
        self.assertEqual({m["id"]: m["responsaveis"] for m in self.mapa["modulos"]}, RESPONSAVEIS)

    def test_arquivos_do_mapa_existem_e_sem_segredo(self):
        for m in self.mapa["modulos"]:
            for e in m["editaveis"]:
                self.assertTrue((RAIZ / e["arquivo"]).is_file(), e["arquivo"])
            for r in m["referencia"] + [c["arquivo"] for c in m["conferir"]]:
                self.assertTrue((RAIZ / r).is_file(), r)
                self.assertNotRegex(r, r"secrets\.(h|ya?ml)$|(^|/)\.env$")
            for t in m["testes"]:
                self.assertTrue((RAIZ / "physis-hub" / "tests" / f"{t}.py").is_file(), t)

    def test_um_kit_por_modulo_com_manifesto_valido(self):
        for m in self.mapa["modulos"]:
            kit = self.saida / f"kit-{m['id']}-{DATA}"
            for nome in ("LEIA-ME.md", "FICHA_REVISAO.md", "MANIFESTO.json", "editaveis/_KIT.json"):
                self.assertTrue((kit / nome).is_file(), f"{kit.name}/{nome}")
            man = json.loads((kit / "MANIFESTO.json").read_text(encoding="utf-8"))
            self.assertEqual(man["responsaveis"], RESPONSAVEIS[m["id"]])
            self.assertEqual(man["formato"], G.FORMATO)
            for e in man["editaveis"]:
                self.assertEqual(G.sha256_arquivo(kit / e["arquivo_kit"]), e["sha256_kit"], e["arquivo_kit"])
                self.assertTrue(e["arquivo_kit"].startswith("editaveis/"))
            for r in man["referencia"]:
                self.assertEqual(G.sha256_arquivo(kit / r["arquivo_kit"]), r["sha256"], r["arquivo_kit"])
            for nome, h in man["outros"].items():
                self.assertEqual(G.sha256_arquivo(kit / nome), h, nome)
            guardado = self.saida / "_manifestos" / f"{kit.name}.json"
            self.assertEqual(guardado.read_bytes(), (kit / "MANIFESTO.json").read_bytes())
            leia = (kit / "LEIA-ME.md").read_text(encoding="utf-8")
            for trecho in ("Como devolver", "Como mudar um arquivo sem estragar", ", ".join(m["responsaveis"])):
                self.assertIn(trecho, leia)
            self.assertNotIn("\r\n", leia)

    def test_trocas_previa_e_parametros_em_todo_kit(self):
        for m in self.mapa["modulos"]:
            kit = self.saida / f"kit-{m['id']}-{DATA}"
            man = json.loads((kit / "MANIFESTO.json").read_text(encoding="utf-8"))
            tipos = [e["tipo"] for e in man["editaveis"]]
            self.assertIn("trocas", tipos, m["id"])
            self.assertTrue((kit / "editaveis" / "trocas-de-texto.json").is_file())
            self.assertTrue((kit / "referencia/ferramentas/kits/previsualizar.html").is_file(), m["id"])
            self.assertTrue((kit / "ABRIR-PREVIA.html").is_file(), m["id"])
            self.assertIn("ABRIR-PREVIA.html", (kit / "LEIA-ME.md").read_text(encoding="utf-8"))
            self.assertTrue([t for t in tipos if t != "trocas"], f"{m['id']}: sem arquivo editável de dados")
        for mid, arq in (("hw-pluviometro", "firmware/pluviometro/parametros.json"),
                         ("hw-pulseira", "firmware/saude/parametros-pulseira.json"),
                         ("hw-remedios", "firmware/saude/parametros-caixinha.json")):
            man = json.loads((self.saida / f"kit-{mid}-{DATA}" / "MANIFESTO.json").read_text(encoding="utf-8"))
            e = [x for x in man["editaveis"] if x.get("fonte") == arq]
            self.assertTrue(e, mid)
            self.assertTrue(e[0]["bloqueadas"], "contrato do aparelho bloqueado")

    def test_previsualizar_sem_recurso_externo(self):
        modelo = (FERR / "kits" / "previsualizar.html").read_text(encoding="utf-8")
        self.assertNotRegex(modelo, EXTERNO)
        self.assertEqual(modelo.count('<script type="application/json" id="previa-dados">null</script>'), 1)
        self.assertIn("URL.createObjectURL", modelo)
        previa = (self.saida / f"kit-sbn-{DATA}" / "ABRIR-PREVIA.html").read_text(encoding="utf-8")
        i = previa.index('id="previa-dados">') + len('id="previa-dados">')
        dados = json.loads(previa[i:previa.index("</script>", i)])
        self.assertEqual(dados["aba"], "sbn")
        self.assertEqual(dados["blocos"]["sistema/physis-plantas.json"], "base-plantas")
        self.assertEqual(dados["blocos"]["sistema/physis-metodologia.json"], "mod-metodologia")
        self.assertIn("sistema/physis-plantas.json", dados["originais"])
        self.assertIn("base-premissas-previa", dados["plataforma"])
        self.assertNotIn("</script", previa[i:previa.index("</script>", i)])

    def test_i18n_cortado_por_modulo(self):
        man = json.loads((self.saida / f"kit-sbn-{DATA}" / "MANIFESTO.json").read_text(encoding="utf-8"))
        e = [x for x in man["editaveis"] if (x.get("fonte") or "").endswith("physis-i18n-modulos.json")][0]
        self.assertEqual(e["tipo"], "json-partes")
        self.assertTrue(e["partes"] and all(p[0] == "I18N" for p in e["partes"]))
        resto = json.loads((self.saida / f"kit-acessibilidade-{DATA}" / "MANIFESTO.json").read_text(encoding="utf-8"))
        r = [x for x in resto["editaveis"] if (x.get("fonte") or "").endswith("physis-i18n-modulos.json")][0]
        sbn = {json.dumps(p) for p in e["partes"]}
        self.assertFalse(sbn & {json.dumps(p) for p in r["partes"]}, "frase de módulo não vai para o 'resto'")
        self.assertIn(["I18N_RX"], r["partes"])

    def test_parametros_coerentes_com_firmware_e_hub(self):
        from physis_hub import robos, saude
        ble = (RAIZ / "firmware/saude/BLE_PERFIL.md").read_text(encoding="utf-8")
        js = (RAIZ / "sistema/physis-ble.js").read_text(encoding="utf-8")
        def valor(arq, pid):
            d = json.loads((RAIZ / arq).read_text(encoding="utf-8"))
            return [p for p in d["parametros"] if p["id"] == pid][0]["valor"]
        for arq in ("firmware/saude/parametros-pulseira.json", "firmware/saude/parametros-caixinha.json"):
            d = json.loads((RAIZ / arq).read_text(encoding="utf-8"))
            for k, v in d["ble"].items():
                if re.fullmatch(r"[0-9a-f-]{36}", str(v)):
                    self.assertIn(v, ble, f"{arq} {k}")
                    self.assertIn(v, js.lower(), f"{arq} {k}")
        self.assertEqual(valor("firmware/saude/parametros-caixinha.json", "tolerancia_min"), saude.TOLERANCIA_MIN)
        self.assertEqual(valor("firmware/saude/parametros-caixinha.json", "janela_antecipada_min"), saude.ANTES_MIN)
        self.assertEqual(valor("firmware/saude/parametros-pulseira.json", "bateria_baixa_v"), saude.BAT_BAIXA_V)
        self.assertIsNone(valor("firmware/saude/parametros-pulseira.json", "limite_bpm"), "limite clínico não vem de fábrica")
        self.assertEqual(valor("firmware/pluviometro/parametros.json", "mm_por_basculada"), robos.MM_POR_PULSO)

    def test_partes_so_do_modulo(self):
        man = json.loads((self.saida / f"kit-sbn-{DATA}" / "MANIFESTO.json").read_text(encoding="utf-8"))
        met = [e for e in man["editaveis"] if e["fonte"] == "sistema/physis-metodologia.json"][0]
        self.assertEqual(met["tipo"], "json-partes")
        self.assertIn(["modulos", "sbn"], met["partes"])
        self.assertFalse([p for p in met["partes"] if p[0] == "modulos" and p[1] != "sbn"])
        self.assertIn("copiar_metodologia_js", met["pos_aplicar"])


@unittest.skipUnless(NO_REPO, "só no repositório")
class TestValidador(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="devolucao-"))
        self.raiz = self.tmp / "repo"
        for rel in COPIAR:
            (self.raiz / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(RAIZ / rel, self.raiz / rel)
        self.kits = self.tmp / "kits"
        mapa = G.carregar_mapa(self.raiz / "ferramentas" / "kits" / "modulos.json")
        self.mods = {m["id"]: m for m in mapa["modulos"]}
        for mid in ("sbn", "carbono", "hw-caixinha", "hw-pluviometro", "hw-pulseira"):
            G.gerar_kit(self.mods[mid], mapa, self.kits, DATA, self.raiz, self.tmp / "nada", zipar=False, commit="",
                        previa=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def kit(self, mid):
        return self.kits / f"kit-{mid}-{DATA}"

    def devolver(self, mid, mudar=None, extras=None, com_referencia=None, ficha=True):
        """ZIP com editaveis/ (com as mudanças) e a ficha. mudar: {arquivo_kit: função(dados) ou bytes}."""
        kit = self.kit(mid)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for arq in sorted((kit / "editaveis").rglob("*")):
                if not arq.is_file():
                    continue
                rel = arq.relative_to(kit).as_posix()
                dados = arq.read_bytes()
                if mudar and rel in mudar:
                    f = mudar[rel]
                    if callable(f):
                        d = json.loads(dados.decode("utf-8"))
                        d = f(d) or d
                        dados = json.dumps(d, ensure_ascii=False, indent=2).encode("utf-8")
                    else:
                        dados = f
                z.writestr(f"{kit.name}/{rel}", dados)
            for rel, dados in (extras or {}).items():
                z.writestr(f"{kit.name}/{rel}", dados)
            for rel, dados in (com_referencia or {}).items():
                z.writestr(f"{kit.name}/{rel}", dados)
            if ficha:
                z.writestr(f"{kit.name}/FICHA_REVISAO.md", "**Revisor(a):** Teste\n")
        p = self.tmp / f"dev-{mid}.zip"
        p.write_bytes(buf.getvalue())
        return p

    def validar(self, p):
        return V.validar(p, self.raiz, kits=str(self.kits))

    def assertRecusa(self, res, trecho):
        self.assertTrue(res["erros"], "deveria recusar")
        self.assertTrue(any(trecho in e for e in res["erros"]), res["erros"])
        self.assertEqual(res["plano"], {})

    PL = "editaveis/sistema/physis-plantas.json"
    MET = "editaveis/sistema/physis-metodologia__parte-sbn.json"
    FAT = "editaveis/sistema/physis-fatores-emissao.json"

    def test_kit_sem_mudanca_aceito(self):
        res = self.validar(self.devolver("sbn"))
        self.assertEqual(res["erros"], [])
        self.assertEqual(res["plano"], {})

    def test_mudanca_de_valor_aceita_e_formato_mantido(self):
        def m(d):
            d["plantas"][0]["espacamento"]["entre_plantas_m"] = 6
        res = self.validar(self.devolver("sbn", {self.PL: m}))
        self.assertEqual(res["erros"], [])
        self.assertTrue(any("entre_plantas_m: era 5, ficou 6" in x for x in res["mudancas"]), res["mudancas"])
        novo = res["plano"]["sistema/physis-plantas.json"].decode("utf-8")
        velho = (self.raiz / "sistema" / "physis-plantas.json").read_text(encoding="utf-8")
        dif = [1 for a, b in zip(velho.splitlines(), novo.splitlines()) if a != b]
        self.assertEqual(len(dif), 1, "só a linha do valor muda")
        self.assertEqual(len(velho.splitlines()), len(novo.splitlines()))
        esperado = json.loads(velho)
        esperado["plantas"][0]["espacamento"]["entre_plantas_m"] = 6
        self.assertEqual(json.loads(novo), esperado)

    def test_conferido_e_registro_novo_aceitos(self):
        def m(d):
            d["rede"]["anual"]["2023"]["verificar"] = False
            d["rede"]["anual"]["2023"]["conferido"] = {"por": "Laura", "em": "2026-11-20", "fonte": "MCTI, média anual 2023"}
        res = self.validar(self.devolver("carbono", {self.FAT: m}))
        self.assertEqual(res["erros"], [])
        novo = json.loads(res["plano"]["sistema/physis-fatores-emissao.json"])
        self.assertEqual(novo["rede"]["anual"]["2023"]["conferido"]["por"], "Laura")

        def nova_planta(d):
            p = json.loads(json.dumps(d["plantas"][0]))
            p["n"] = max(x["n"] for x in d["plantas"]) + 1
            p["nome"] = "Planta de teste"
            d["plantas"].append(p)
        res = self.validar(self.devolver("sbn", {self.PL: nova_planta}))
        self.assertEqual(res["erros"], [])
        self.assertTrue(any("registro novo" in x for x in res["mudancas"]))
        self.assertEqual(len(json.loads(res["plano"]["sistema/physis-plantas.json"])["plantas"]),
                         len(json.loads((self.raiz / "sistema/physis-plantas.json").read_text(encoding="utf-8"))["plantas"]) + 1)

    def test_conferido_incompleto_recusado(self):
        def m(d):
            d["rede"]["anual"]["2023"]["conferido"] = {"por": "Laura"}
        self.assertRecusa(self.validar(self.devolver("carbono", {self.FAT: m})), "conferido")

    def test_chave_apagada_recusada(self):
        def m(d):
            del d["plantas"][0]["espacamento"]
        self.assertRecusa(self.validar(self.devolver("sbn", {self.PL: m})), "apagada")

    def test_id_apagado_ou_trocado_recusado(self):
        def apaga(d):
            d["plantas"].pop(3)
        self.assertRecusa(self.validar(self.devolver("sbn", {self.PL: apaga})), "registro apagado")

        def troca(d):
            d["plantas"][0]["n"] = 99999
        self.assertRecusa(self.validar(self.devolver("sbn", {self.PL: troca})), "registro apagado")

    def test_tipo_trocado_e_chave_nova_recusados(self):
        def m(d):
            d["plantas"][0]["espacamento"]["entre_plantas_m"] = "cinco"
        self.assertRecusa(self.validar(self.devolver("sbn", {self.PL: m})), "tipo mudou")

        def n(d):
            d["plantas"][0]["inventado"] = 1
        self.assertRecusa(self.validar(self.devolver("sbn", {self.PL: n})), "não é permitida")

    def test_registro_novo_incompleto_recusado(self):
        def m(d):
            d["plantas"].append({"n": 999999, "nome": "Só nome"})
        self.assertRecusa(self.validar(self.devolver("sbn", {self.PL: m})), "sem os campos")

    def test_referencia_mudada_recusada(self):
        kit = self.kit("sbn")
        ref = (kit / "referencia/sistema/physis-sbn.js").read_bytes() + b"\n// mudei\n"
        res = self.validar(self.devolver("sbn", com_referencia={"referencia/sistema/physis-sbn.js": ref}))
        self.assertRecusa(res, "referência foi mudado")

    def test_referencia_igual_aceita(self):
        kit = self.kit("sbn")
        ref = (kit / "referencia/sistema/physis-sbn.js").read_bytes()
        res = self.validar(self.devolver("sbn", com_referencia={"referencia/sistema/physis-sbn.js": ref}))
        self.assertEqual(res["erros"], [])

    def test_script_e_endereco_recusados(self):
        for valor, trecho in (("<script>alert(1)</script>", "script"),
                              ("ver https://exemplo.com/tabela", "endereço de internet"),
                              ("<img src=x onerror=alert(1)>", "tag HTML")):
            def m(d, v=valor):
                d["plantas"][0]["nome"] = v
            self.assertRecusa(self.validar(self.devolver("sbn", {self.PL: m})), trecho)

    def test_parte_do_modulo_com_caminho_trocado_recusada(self):
        def m(d):
            d["partes"][0]["caminho"] = ["modulos", "agua"]
        self.assertRecusa(self.validar(self.devolver("sbn", {self.MET: m})), "caminho")

    def test_parte_do_modulo_aceita(self):
        def m(d):
            d["partes"][0]["valor"]["resumo"] = "Resumo revisado pela engenharia."
        res = self.validar(self.devolver("sbn", {self.MET: m}))
        self.assertEqual(res["erros"], [])
        novo = json.loads(res["plano"]["sistema/physis-metodologia.json"])
        self.assertEqual(novo["modulos"]["sbn"]["resumo"], "Resumo revisado pela engenharia.")
        self.assertIn("copiar_metodologia_js", res["pos_aplicar"])

    def test_arquivo_a_mais_recusado(self):
        res = self.validar(self.devolver("sbn", extras={"editaveis/sistema/outro.json": b"{}"}))
        self.assertRecusa(res, "não é arquivo editável")

    def test_json_quebrado_recusado(self):
        self.assertRecusa(self.validar(self.devolver("sbn", {self.PL: b'{"plantas": [}'})), "não abre")

    def test_caminho_perigoso_no_zip_recusado(self):
        p = self.tmp / "mau.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("../fora.txt", "x")
        self.assertTrue(self.validar(p)["erros"])

    def test_deriva_no_sistema_para(self):
        def m(d):
            d["plantas"][0]["espacamento"]["entre_plantas_m"] = 6
        dev = self.devolver("sbn", {self.PL: m})
        arq = self.raiz / "sistema" / "physis-plantas.json"
        d = json.loads(arq.read_text(encoding="utf-8"))
        d["plantas"][1]["nome"] = d["plantas"][1]["nome"] + " (mudado no sistema)"
        arq.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        self.assertRecusa(self.validar(dev), "3 vias")

    def test_deriva_em_outra_parte_nao_atrapalha(self):
        def m(d):
            d["partes"][0]["valor"]["resumo"] = "Resumo novo."
        dev = self.devolver("sbn", {self.MET: m})
        arq = self.raiz / "sistema" / "physis-metodologia.json"
        d = json.loads(arq.read_text(encoding="utf-8"))
        d["modulos"]["agua"]["resumo"] = "Outro módulo mudou no meio tempo."
        arq.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        res = self.validar(dev)
        self.assertEqual(res["erros"], [])
        novo = json.loads(res["plano"]["sistema/physis-metodologia.json"])
        self.assertEqual(novo["modulos"]["agua"]["resumo"], "Outro módulo mudou no meio tempo.")
        self.assertEqual(novo["modulos"]["sbn"]["resumo"], "Resumo novo.")

    def test_texto_com_segredo_recusado(self):
        yaml = "editaveis/firmware/caixinha/esphome/irrigacao-zona1.yaml"
        orig = (self.kit("hw-caixinha") / yaml).read_bytes()
        ok = self.validar(self.devolver("hw-caixinha", {yaml: orig + b"\n# tempo maximo conferido em campo\n"}))
        self.assertEqual(ok["erros"], [])
        self.assertIn("firmware/caixinha/esphome/irrigacao-zona1.yaml", ok["plano"])
        mau = self.validar(self.devolver("hw-caixinha", {yaml: orig + b'\nwifi_password: "MinhaSenha123"\n'}))
        self.assertRecusa(mau, "senha")

    TR = "editaveis/trocas-de-texto.json"

    def frase_unica(self):
        js = (self.raiz / "sistema/physis-sbn.js").read_text(encoding="utf-8")
        for m in re.finditer(r'"([A-Za-zÀ-ú][A-Za-zÀ-ú ,.()]{14,60})"', js):
            s = m.group(1)
            if js.count(s) == 1 and not V.CODIGO_TROCA.search(s):
                return s
        self.skipTest("sem frase única no physis-sbn.js")

    def trocas(self, *lista):
        def m(d):
            d["trocas"] = [dict(zip(("arquivo", "antes", "depois", "motivo"), x)) for x in lista]
        return {self.TR: m}

    def test_troca_de_texto_valida_aceita_e_aplicada(self):
        s = self.frase_unica()
        res = self.validar(self.devolver("sbn", self.trocas(("sistema/physis-sbn.js", s, s + " revisado", "clareza"))))
        self.assertEqual(res["erros"], [])
        self.assertIn(s + " revisado", res["plano"]["sistema/physis-sbn.js"].decode("utf-8"))
        self.assertIn("embutir_bases", res["pos_aplicar"])

    def test_troca_com_codigo_recusada(self):
        s = self.frase_unica()
        for depois in (s + " <b>x</b>", s + "; alert(1)", s + " {x}", "ver https://exemplo.com", s + " =>"):
            res = self.validar(self.devolver("sbn", self.trocas(("sistema/physis-sbn.js", s, depois, "teste"))))
            self.assertRecusa(res, "sinal de código")
        res = self.validar(self.devolver("sbn", self.trocas(("sistema/physis-sbn.js", s, s + ' "x"', "aspas"))))
        self.assertRecusa(res, "aspas")

    def test_troca_com_antes_repetido_ou_arquivo_proibido_recusada(self):
        res = self.validar(self.devolver("sbn", self.trocas(("sistema/physis-sbn.js", "function", "funcao", "x"))))
        self.assertRecusa(res, "exatamente")
        res = self.validar(self.devolver("sbn", self.trocas(("physis-hub/physis_hub/saude.py", "TOLERANCIA", "X", "x"))))
        self.assertRecusa(res, "permitidos")

    def test_ingles_da_parte_do_modulo(self):
        nome = "editaveis/sistema/physis-i18n-modulos__parte-sbn.json"
        if not (self.kit("sbn") / nome).is_file():
            self.skipTest("sem frases de inglês do SbN")
        def m(d):
            d["partes"][0]["valor"] = d["partes"][0]["valor"] + " (reviewed)"
        res = self.validar(self.devolver("sbn", {nome: m}))
        self.assertEqual(res["erros"], [])
        self.assertIn("sistema/physis-i18n-modulos.json", res["plano"])

        def mau(d):
            d["partes"][0]["valor"] = "<script>x</script>"
        self.assertRecusa(self.validar(self.devolver("sbn", {nome: mau})), "script")

    def test_parametros_do_aparelho(self):
        pl = "editaveis/firmware/pluviometro/parametros.json"
        def ok(d):
            p = [x for x in d["parametros"] if x["id"] == "mm_por_basculada"][0]
            p["valor"], p["verificar"] = 0.25, False
            p["conferido"] = {"por": "Arthur", "em": "2026-11-20", "fonte": "calibração com 1 L"}
        self.assertEqual(self.validar(self.devolver("hw-pluviometro", {pl: ok}))["erros"], [])
        def fora(d):
            [x for x in d["parametros"] if x["id"] == "mm_por_basculada"][0]["valor"] = 9.0
        self.assertRecusa(self.validar(self.devolver("hw-pluviometro", {pl: fora})), "fora da faixa")
        pu = "editaveis/firmware/saude/parametros-pulseira.json"
        def ble(d):
            d["ble"]["servico_pulseira"] = "00000000-0000-0000-0000-000000000000"
        self.assertRecusa(self.validar(self.devolver("hw-pulseira", {pu: ble})), "não pode mudar")
        def bpm(d):
            [x for x in d["parametros"] if x["id"] == "limite_bpm"][0]["valor"] = 140
        self.assertEqual(self.validar(self.devolver("hw-pulseira", {pu: bpm}))["erros"], [])

    @unittest.skipUnless(git_ok(), "precisa do git")
    def test_aplicar_numa_branch_e_voltar(self):
        g = [G.git_exe(), "-C", str(self.raiz)]
        for cmd in (["init", "-q", "-b", "main"], ["config", "user.email", "teste@physis.local"],
                    ["config", "user.name", "Teste"], ["config", "core.autocrlf", "false"],
                    ["add", "-A"], ["commit", "-q", "-m", "base"]):
            subprocess.run(g + cmd, check=True, capture_output=True)

        def m(d):
            d["plantas"][0]["espacamento"]["entre_plantas_m"] = 7
        dev = self.devolver("sbn", {self.PL: m})
        res = self.validar(dev)
        self.assertEqual(res["erros"], [])
        antes = (self.raiz / "sistema/physis-plantas.json").read_bytes()
        (self.raiz / "sujo.txt").write_text("x")
        with self.assertRaises(RuntimeError):
            V.aplicar(res, self.raiz, testes=False)
        (self.raiz / "sujo.txt").unlink()
        ap = V.aplicar(res, self.raiz, testes=False)
        self.assertTrue(ap["branch"].startswith("revisao/sbn-"))
        atual = subprocess.run(g + ["rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True).stdout.strip()
        self.assertEqual(atual, "main", "volta para a branch de antes")
        self.assertEqual((self.raiz / "sistema/physis-plantas.json").read_bytes(), antes, "main não muda")
        na_branch = subprocess.run(g + ["show", f"{ap['branch']}:sistema/physis-plantas.json"],
                                   capture_output=True).stdout
        self.assertEqual(json.loads(na_branch)["plantas"][0]["espacamento"]["entre_plantas_m"], 7)
        texto = V.relatorio(res, dev, ap)
        self.assertIn("git merge --no-ff", texto)


if __name__ == "__main__":
    unittest.main()
