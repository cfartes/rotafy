#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

# Fresh installation for the canonical domain. Only the new Rotafy project is reset.
install_dir=/opt/rotafy-tech
project=nexus-rotafy-tech
for executable in git python3 docker; do
    command -v "$executable" >/dev/null 2>&1 || { printf 'Dependência ausente: %s\n' "$executable" >&2; exit 1; }
done
docker compose version >/dev/null
docker info >/dev/null
if [[ -L "$install_dir" || ( -e "$install_dir" && ! -d "$install_dir" ) ]]; then
    printf 'Diretório de destino inválido: %s\n' "$install_dir" >&2
    exit 1
fi
if [[ -d "$install_dir" && "$(readlink -f "$install_dir")" != "$install_dir" ]]; then
    printf 'O destino deve resolver exatamente para /opt/rotafy-tech.\n' >&2
    exit 1
fi

# Clone before changing any running service; credentials are generated on the VPS.
staging="$(mktemp -d /opt/rotafy-install.XXXXXXXX)"
git clone --branch main https://github.com/cfartes/rotafy.git "$staging"
python3 -m py_compile "$staging/scripts/deploy_vps.py"
printf 'Preparando banco vazio e credenciais novas para %s.\n' "$project"
container_ids="$(docker ps -aq --filter "label=com.docker.compose.project=$project")"
volume_names="$(docker volume ls -q --filter "label=com.docker.compose.project=$project")"
if [[ -n "$volume_names" ]]; then
    mapfile -t volumes <<< "$volume_names"
    for volume in "${volumes[@]}"; do
        [[ "$volume" == "${project}_"* ]] || { printf 'Volume fora do projeto esperado.\n' >&2; exit 1; }
    done
fi
if [[ -n "$container_ids" ]]; then
    mapfile -t containers <<< "$container_ids"
    docker rm -f "${containers[@]}"
fi
if [[ -n "$volume_names" ]]; then docker volume rm "${volumes[@]}"; fi
if [[ -d "$install_dir" ]]; then
    mv -- "$install_dir" "${install_dir}.previous.$(date -u +%Y%m%dT%H%M%SZ).$$"
fi
mv -- "$staging" "$install_dir"
printf 'Instalando em %s. A instalação antiga será parada após a nova estar pronta.\n' "$install_dir"
exec python3 "$install_dir/scripts/deploy_vps.py" --replace-legacy "$@"
