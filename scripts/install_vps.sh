#!/usr/bin/env bash
set -Eeuo pipefail
# Git sources must be readable by container users. The Python installer sets
# umask 077 for credentials, locks and database backups separately.
umask 022

# Run this script on the VPS; existing Docker/Traefik are prerequisites.
# Canonical production domain: rotafy.nexusdataanalytics.tech.
# Keep the existing directory and Compose project to preserve database volumes.
repo_url='https://github.com/cfartes/rotafy.git'
install_dir="${ROTAFY_INSTALL_DIR:-/opt/nexus-rotafy}"
for executable in git python3 docker; do
    if ! command -v "$executable" >/dev/null 2>&1; then
        printf 'Dependência ausente: %s. Instale antes de continuar.\n' "$executable" >&2
        exit 1
    fi
done
docker compose version >/dev/null
case "$install_dir" in
    /*) ;;
    *) printf 'ROTAFY_INSTALL_DIR deve ser absoluto.\n' >&2; exit 1 ;;
esac
if [[ "$install_dir" == '/' ]]; then
    printf 'Diretório de instalação inválido.\n' >&2
    exit 1
fi
if [[ -d "$install_dir/.git" ]]; then
    remote="$(git -C "$install_dir" remote get-url origin)"
    if [[ "$remote" != "$repo_url" && "$remote" != 'https://github.com/cfartes/rotafy' ]]; then
        printf 'O diretório pertence a outro repositório; nenhuma alteração realizada.\n' >&2
        exit 1
    fi
    if [[ -n "$(git -C "$install_dir" status --porcelain)" ]]; then
        printf 'Checkout possui alterações. Faça commit antes de instalar.\n' >&2
        exit 1
    fi
    if [[ "$(git -C "$install_dir" branch --show-current)" != 'main' ]]; then
        printf 'Instalação deve usar a branch main; nenhuma troca automática realizada.\n' >&2
        exit 1
    fi
    git -C "$install_dir" pull --ff-only origin main
else
    if [[ -e "$install_dir" ]]; then
        printf 'Diretório já existe sem Git. Use outro ROTAFY_INSTALL_DIR ou organize a instalação existente.\n' >&2
        exit 1
    fi
    git clone --branch main "$repo_url" "$install_dir"
fi
printf 'Instalando Nexus Rotafy em https://rotafy.nexusdataanalytics.tech\n'
exec python3 "$install_dir/scripts/deploy_vps.py" "$@"
