#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_password="$APP_DB_PASSWORD" -v platform_password="$PLATFORM_DB_PASSWORD" <<'SQL'
CREATE ROLE rotafy_app LOGIN PASSWORD :'app_password' NOSUPERUSER NOBYPASSRLS;
CREATE ROLE rotafy_platform LOGIN PASSWORD :'platform_password' NOSUPERUSER NOBYPASSRLS;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO rotafy_app, rotafy_platform;
SQL

