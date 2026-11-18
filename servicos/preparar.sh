#!/usr/bin/env bash
# Prepara o servidor da Physis para o docker compose (idempotente; não troca segredo que já existe):
#   1. env/*.env a partir de env/*.env.exemplo, com segredos gerados (python3 secrets), 0600;
#      segredos que dois serviços precisam (ex.: senha de leitura do BI) saem iguais nos dois arquivos;
#   2. pastas de dados em ${PHYSIS_DADOS:-/srv/physis} com os donos certos;
#   3. senhas do Mosquitto (hash gerado pelo próprio mosquitto_passwd da imagem) e o hash bcrypt do Node-RED;
#   4. instancia.json do hub (cópia do pacote, se ainda não existir).
#
#   sudo PHYSIS_DADOS=/srv/physis PHYSIS_PACOTE=/srv/pacotes/physis-servidor ./preparar.sh
set -euo pipefail
umask 077
cd "$(dirname "${BASH_SOURCE[0]}")"
DADOS="${PHYSIS_DADOS:-/srv/physis}"
PACOTE="${PHYSIS_PACOTE:-../physis-hub}"

[[ -f .env ]] || { cp .env.exemplo .env; echo "criado .env (confira PHYSIS_DADOS, PHYSIS_PACOTE e COMPOSE_PROFILES)"; }

python3 - <<'PY'
import re, secrets
from pathlib import Path

env = Path("env")
COMPARTILHADOS = {  # (arquivo, chave) -> nome canônico do segredo
    ("superset-db", "POSTGRES_PASSWORD"): "SUPERSET_DB_SENHA", ("superset", "SUPERSET_DB_SENHA"): "SUPERSET_DB_SENHA",
    ("postgis", "BI_LEITOR_SENHA"): "BI_LEITOR_SENHA", ("superset", "BI_LEITOR_SENHA"): "BI_LEITOR_SENHA",
    ("timescale", "SERIES_LEITOR_SENHA"): "SERIES_LEITOR_SENHA", ("superset", "SERIES_LEITOR_SENHA"): "SERIES_LEITOR_SENHA",
    ("postgis", "EXPORTADOR_SENHA"): "EXPORTADOR_SENHA", ("timescale", "SERIES_SENHA"): "SERIES_SENHA",
    ("postgis", "GEOSERVER_LEITOR_SENHA"): "GEOSERVER_LEITOR_SENHA",
    ("hub", "PHYSIS_CALC_CHAVE"): "CALC_CHAVE", ("calc", "PHYSIS_CALC_CHAVE"): "CALC_CHAVE",
    ("hub", "PHYSIS_DOC_CHAVE"): "DOC_CHAVE", ("documentos", "PHYSIS_DOC_CHAVE"): "DOC_CHAVE",
    ("hub", "PHYSIS_IA_CHAVE"): "IA_CHAVE", ("ia-vllm", "VLLM_API_KEY"): "IA_CHAVE",
}
SECRETO = re.compile(r"(SENHA|PASSWORD|SECRET|SEGREDO|CHAVE|API_KEY)$")
NAO_GERAR = {"PHYSIS_SMTP_SENHA", "NODERED_ADMIN_HASH"}   # SMTP vem do Eric; o hash é feito depois

def ler(p):
    d = {}
    if p.is_file():
        for ln in p.read_text(encoding="utf-8").splitlines():
            if "=" in ln and not ln.lstrip().startswith("#"):
                k, v = ln.split("=", 1)
                d[k.strip()] = v.strip()
    return d

canon = {}
for ex in sorted(env.glob("*.env.exemplo")):
    nome = ex.name[:-len(".env.exemplo")]
    for k, v in ler(env / f"{nome}.env").items():
        c = COMPARTILHADOS.get((nome, k))
        if c and v:
            canon.setdefault(c, v)

for ex in sorted(env.glob("*.env.exemplo")):
    nome = ex.name[:-len(".env.exemplo")]
    alvo = env / f"{nome}.env"
    atual = ler(alvo)
    saida = []
    for ln in ex.read_text(encoding="utf-8").splitlines():
        if "=" not in ln or ln.lstrip().startswith("#"):
            saida.append(ln); continue
        k, v = ln.split("=", 1)
        k = k.strip()
        if atual.get(k):
            v = atual[k]
        elif not v and SECRETO.search(k) and k not in NAO_GERAR:
            c = COMPARTILHADOS.get((nome, k))
            v = canon.setdefault(c, secrets.token_urlsafe(32)) if c else secrets.token_urlsafe(32)
        saida.append(f"{k}={v}")
    d = dict(x.split("=", 1) for x in saida if "=" in x and not x.lstrip().startswith("#"))
    if nome == "exportador":
        if not d.get("PG_URL"):
            saida = [f"PG_URL=postgresql://exportador:{canon['EXPORTADOR_SENHA']}@postgis:5432/physis" if x.startswith("PG_URL=") else x for x in saida]
        if not d.get("SERIES_URL") and "SERIES_SENHA" in canon:
            saida = [f"SERIES_URL=postgresql://series_gravador:{canon['SERIES_SENHA']}@timescaledb:5432/series" if x.startswith("SERIES_URL=") else x for x in saida]
    alvo.write_text("\n".join(saida) + "\n", encoding="utf-8")
    alvo.chmod(0o600)
print("env/*.env prontos (segredos não mostrados)")
PY

# pastas de dados (hub e instantâneo: uid 10700; exportador: 10701 no grupo 10700)
install -d -m 0755 "$DADOS"
install -d -m 0750 -o 10700 -g 10700 "$DADOS/hub" "$DADOS/instantaneos"
install -d -m 0755 "$DADOS/hub-config" "$DADOS/camadas" "$DADOS/epw" "$DADOS/caddy/data" "$DADOS/caddy/config"
install -d -m 0755 -o 10701 -g 10700 "$DADOS/camadas/hub"
install -d -m 0750 -o 1000 -g 1000 "$DADOS/nodered"            # usuário node-red da imagem
install -d -m 0750 "$DADOS/mosquitto" "$DADOS/ia" "$DADOS/ia-vllm"
install -d -m 0750 -o 1883 -g 1883 "$DADOS/mosquitto/data"     # usuário mosquitto da imagem
if [[ ! -f "$DADOS/hub-config/instancia.json" ]]; then
  if [[ -f "$PACOTE/instancia.json" ]]; then install -m 0644 "$PACOTE/instancia.json" "$DADOS/hub-config/instancia.json"
  else printf '{"org": "physis", "lugar": "servidor", "login": true, "modulos": []}\n' > "$DADOS/hub-config/instancia.json"
       chmod 0644 "$DADOS/hub-config/instancia.json"; echo "aviso: instancia.json mínimo criado; troque pelo do pacote do servidor"; fi
fi

val() { grep -E "^$2=" "env/$1.env" | head -n1 | cut -d= -f2-; }

# senhas do Mosquitto: o hash é feito dentro da imagem; a senha entra pela entrada padrão (fora da linha de comando)
if command -v docker >/dev/null; then
  SENHAS="$DADOS/mosquitto/senhas"
  if [[ ! -s "$SENHAS" ]]; then
    printf 'physis-hub:%s\nnodered:%s\n' "$(val hub PHYSIS_MQTT_SENHA)" "$(val nodered NODERED_MQTT_SENHA)" > "$SENHAS"
    docker run --rm -v "$DADOS/mosquitto:/m" eclipse-mosquitto:2.0.18 mosquitto_passwd -U /m/senhas
    chown 1883:1883 "$SENHAS"; chmod 0600 "$SENHAS"
    echo "senhas do Mosquitto geradas"
  fi
  if [[ -z "$(val nodered NODERED_ADMIN_HASH)" ]]; then
    [[ -f env/nodered.senha ]] || python3 -c 'import secrets; print(secrets.token_urlsafe(18))' > env/nodered.senha
    chmod 0600 env/nodered.senha
    HASH="$(docker run --rm -i --entrypoint node nodered/node-red:4.0.2 -e \
      "const b=require('/usr/src/node-red/node_modules/bcryptjs');let s='';process.stdin.on('data',d=>s+=d).on('end',()=>console.log(b.hashSync(s.trim(),10)))" \
      < env/nodered.senha)"
    sed -i "s|^NODERED_ADMIN_HASH=.*|NODERED_ADMIN_HASH='${HASH}'|" env/nodered.env
    echo "Node-RED: senha do usuário em servicos/env/nodered.senha (guarde no cofre e apague o arquivo)"
  fi
else
  echo "aviso: docker não encontrado; senhas do Mosquitto e hash do Node-RED ficaram para depois"
fi
echo "Pronto. Próximo: docker compose config -q && docker compose up -d"
