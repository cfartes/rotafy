#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

# Update only the independent installation; never create or erase a database.
install_dir="${ROTAFY_INSTALL_DIR:-/opt/rotafy-tech}"
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
python3 - "$install_dir/.env.production" <<'PY'
import json
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
if project != "nexus-rotafy-tech":
    sys.exit("Instalação não identificada como nexus-rotafy-tech. Atualização interrompida; nenhuma credencial ou banco foi alterado.")
PY
docker compose version >/dev/null
if ! docker volume inspect nexus-rotafy-tech_database >/dev/null 2>&1; then
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
printf 'Atualizando https://rotafy.nexusdataanalytics.tech (projeto nexus-rotafy-tech).\n'
exec python3 "$install_dir/scripts/deploy_vps.py" "$@"
