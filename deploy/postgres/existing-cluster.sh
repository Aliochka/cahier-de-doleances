#!/bin/bash
# Deliberately bypass docker-entrypoint.sh: no initdb, password setup or chown.
set -euo pipefail
test "${PGDATA:-}" = /var/lib/postgresql/data
test -f /run/ssd-mounted
test -r "$PGDATA/PG_VERSION"
test "$(cat "$PGDATA/PG_VERSION")" = 17
test -f "$PGDATA/global/pg_control"
test "$(stat -c %u "$PGDATA")" = "$(id -u postgres)"
test "$(stat -c %u "$PGDATA/global/pg_control")" = "$(id -u postgres)"
test "${1:-}" = postgres
test "${PG_VERSION%%-*}" = 17.11
if test "$(id -u)" = 0; then
    exec gosu postgres "$@" -D "$PGDATA"
fi
test "$(id -u)" = "$(id -u postgres)"
exec "$@" -D "$PGDATA"
