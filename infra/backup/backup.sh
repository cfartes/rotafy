#!/bin/sh
set -eu
umask 077
: "${RESTIC_REPOSITORY:?Configure o repositório externo}"
: "${RESTIC_PASSWORD:?Configure a senha de criptografia}"
case "$RESTIC_REPOSITORY" in
  s3:*) ;;
  *) echo 'Configure um repositório S3 externo à VPS.' >&2; exit 1 ;;
esac
if [ "$RESTIC_PASSWORD" = CHANGE_ME ]; then
  echo 'Configure a senha de criptografia.' >&2
  exit 1
fi
mkdir -p /tmp/rotafy-backup
trap 'rm -f /tmp/rotafy-backup/database.dump' EXIT
pg_dump --format=custom --file=/tmp/rotafy-backup/database.dump
restic backup /tmp/rotafy-backup/database.dump --tag rotafy-production --quiet
printf '{"event":"backup.completed"}\n'
