#!/usr/bin/env bash
# Apenas backup e migração incremental. Não recria banco nem serviços da aplicação.
set -Eeuo pipefail
umask 077
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$root"
[[ -f .env.production ]] || { echo 'Ambiente .env.production não encontrado nesta instalação.' >&2; exit 1; }
mapfile -t databases < <(docker ps -q --filter "label=com.docker.compose.project.working_dir=$root" --filter 'label=com.docker.compose.service=db')
[[ ${#databases[@]} -eq 1 ]] || { echo 'Não foi possível identificar um único banco ativo nesta pasta. Nenhum banco alterado.' >&2; exit 1; }
database="${databases[0]}"
project="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$database")"
[[ -n "$project" ]] || { echo 'Projeto Docker não identificado.' >&2; exit 1; }
mkdir -p -- "$root/backups"
backup="$root/backups/pre-migration-$(date -u +%Y%m%dT%H%M%SZ)-$$.dump"
docker exec "$database" pg_dump -U rotafy_owner -d rotafy -Fc > "$backup"
[[ "$(head -c 5 -- "$backup")" == 'PGDMP' ]] || { echo 'Backup inválido. Migração cancelada.' >&2; exit 1; }
printf 'Backup preservado em %s\n' "$backup"
# Reutiliza a imagem já instalada, montando somente as migrações do checkout atualizado.
# --no-deps evita recriar banco, API, web ou workers; --pull never evita trocar imagens.
docker compose --env-file .env.production -f compose.production.yaml -p "$project" \
  run --rm --no-deps --pull never --volume "$root/backend/migrations:/app/migrations:ro" migrate alembic upgrade head
printf 'Migração incremental concluída. Banco e serviços existentes preservados.\n'
printf 'Para disponibilizar os recursos novos na interface e API, atualize também a aplicação pelo script update_vps.sh.\n'
