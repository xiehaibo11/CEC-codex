#!/usr/bin/env bash
# Create (or reuse) the two project databases and import the table schema.
# Idempotent for fresh environments; refuses to touch a non-empty database
# unless FORCE=1 so an accidental run can never clobber live data.
#
# Usage:
#   ./import.sh                          # containerized postgres (cec-codex-postgres)
#   PGCONTAINER=other-name ./import.sh   # different container name
#   FORCE=1 ./import.sh                  # import even into a non-empty database
#
# To restore full DATA afterwards, use the binary dumps in ../backups/ (see
# backups/README.md) - this script creates structure only.

set -euo pipefail
cd "$(dirname "$0")"

PGCONTAINER="${PGCONTAINER:-cec-codex-postgres}"
PGUSER="${PGUSER:-alpha_user}"

import_one() {
    local dbname="$1" schema_file="$2"

    if ! docker exec "$PGCONTAINER" psql -U "$PGUSER" -d postgres -t -A \
        -c "SELECT 1 FROM pg_database WHERE datname='${dbname}'" | grep -q 1; then
        echo ">> creating database ${dbname}"
        docker exec "$PGCONTAINER" psql -U "$PGUSER" -d postgres -c "CREATE DATABASE ${dbname};"
    fi

    local existing
    existing=$(docker exec "$PGCONTAINER" psql -U "$PGUSER" -d "$dbname" -t -A \
        -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")
    if [ "$existing" != "0" ] && [ "${FORCE:-0}" != "1" ]; then
        echo ">> ${dbname} already has ${existing} tables - skipping (set FORCE=1 to import anyway)"
        return
    fi

    echo ">> importing ${schema_file} into ${dbname}"
    docker exec -i "$PGCONTAINER" psql -U "$PGUSER" -d "$dbname" -v ON_ERROR_STOP=1 -q < "$schema_file"
    docker exec "$PGCONTAINER" psql -U "$PGUSER" -d "$dbname" -t -A \
        -c "SELECT count(*) || ' tables now in ${dbname}' FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';"
}

import_one "alpha_arena" "alpha_arena_schema.sql"
import_one "alpha_snapshots" "alpha_snapshots_schema.sql"
echo ">> done"
