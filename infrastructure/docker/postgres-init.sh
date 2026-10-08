#!/bin/sh
set -eu

# The image's bootstrap user runs migrations; the application cannot bypass RLS.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -v ON_ERROR_STOP=1 <<'SQL'
\getenv database_name POSTGRES_DB
\getenv app_password NORIS_APP_DB_PASSWORD
CREATE ROLE noris_app WITH LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT CONNECT ON DATABASE :"database_name" TO noris_app;
GRANT USAGE ON SCHEMA public TO noris_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO noris_app;
SQL
