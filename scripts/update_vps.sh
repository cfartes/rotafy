#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

# Update only the independent installation; never create or erase a database.
install_dir="${ROTAFY_INSTALL_DIR:-}"
if [[ -z "$install_dir" ]]; then
    if [[ -d "$PWD/.git" && -f "$PWD/.env.production" ]]; then
        install_dir="$PWD"
    elif [[ -d /opt/rotafy-tech/.git && -f /opt/rotafy-tech/.env.production && ! -d /opt/nexus-rotafy/.git ]]; then
        install_dir=/opt/rotafy-tech
    elif [[ -d /opt/nexus-rotafy/.git && -f /opt/nexus-rotafy/.env.production && ! -d /opt/rotafy-tech/.git ]]; then
        install_dir=/opt/nexus-rotafy
    else
        printf 'Entre na pasta da instalação ou informe ROTAFY_INSTALL_DIR.\n' >&2
        exit 1
    fi
fi
case "$install_dir" in
    /*) ;;
    *) printf 'ROTAFY_INSTALL_DIR deve ser absoluto.\n' >&2; exit 1 ;;
esac
for executable in git python3 docker; do
    command -v "$executable" >/dev/null 2>&1 || {
        printf 'Dependência ausente: %s.\n' "$executable" >&2
        exit 1
    }
done
if [[ ! -d "$install_dir/.git" || ! -f "$install_dir/.env.production" ]]; then
    printf 'Instalação existente não encontrada em %s. Este script não faz instalação inicial.\n' "$install_dir" >&2
    exit 1
fi
project="$(python3 - "$install_dir/.env.production" "$install_dir" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

project = None
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    key, separator, value = line.strip().partition("=")
    if separator and key == "DEPLOY_PROJECT":
        if value.startswith('"'):
            project = json.loads(value)
        else:
            project = value.strip("'")
active = subprocess.run([
    "docker", "ps", "--filter",
    "label=com.docker.compose.project.working_dir=" + sys.argv[2],
    "--filter", "label=com.docker.compose.service=db",
    "--format", '{{.Label "com.docker.compose.project"}}',
], check=True, capture_output=True, text=True).stdout.split()
if len(set(active)) > 1 or (active and project and project != active[0]):
    sys.exit("Projeto do ambiente não corresponde ao banco ativo nesta pasta.")
if not project and len(active) == 1:
    project = active[0]
if project not in ("nexus-rotafy-tech", "nexus-rotafy-prod"):
    sys.exit("Instalação Rotafy não identificada. Nenhum ambiente ou banco foi alterado.")
if project == "nexus-rotafy-prod" and active != [project]:
    sys.exit("Banco ativo de nexus-rotafy-prod não identificado nesta pasta.")
print(project)
PY
 )"
docker compose version >/dev/null
if ! docker volume inspect "${project}_database" >/dev/null 2>&1; then
    printf 'Banco da instalação independente não encontrado. Atualização interrompida para não criar outro banco.\n' >&2
    exit 1
fi

# Validate origin/branch and update sources without discarding local edits.
remote="$(git -C "$install_dir" remote get-url origin)"
if [[ "$remote" != 'https://github.com/cfartes/rotafy.git' && "$remote" != 'https://github.com/cfartes/rotafy' ]]; then
    printf 'O diretório pertence a outro repositório.\n' >&2
    exit 1
fi
if [[ -n "$(git -C "$install_dir" status --porcelain)" || "$(git -C "$install_dir" branch --show-current)" != 'main' ]]; then
    printf 'Use a branch main com checkout limpo; alterações locais não serão descartadas.\n' >&2
    exit 1
fi
git -C "$install_dir" pull --ff-only origin main
printf 'Atualizando https://rotafy.nexusdataanalytics.tech (projeto %s, pasta %s).\n' "$project" "$install_dir"
exec python3 "$install_dir/scripts/deploy_vps.py" --project "$project" "$@"
