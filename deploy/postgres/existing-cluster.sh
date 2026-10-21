#!/bin/bash
# Deliberately bypass docker-entrypoint.sh: no initdb, password setup or chown.
set -euo pipefail
fail() {
    echo "existing-cluster: $1" >&2
    exit 1
}

# Compose can discard the image CMD when it overrides ENTRYPOINT. An omitted
# command means the server, never initdb or the upstream initialization script.
if test "$#" = 0; then
    set -- postgres
fi
test "$1" = postgres || fail "only the postgres server command is allowed"
test "${PGDATA:-}" = /var/lib/postgresql/data || fail "unexpected or missing PGDATA"
test -f /run/ssd-mounted || fail "SSD marker is missing"
test -d "$PGDATA" || fail "cluster directory is missing"
test -r "$PGDATA/PG_VERSION" || fail "cluster PG_VERSION is missing or unreadable"
test "$(cat "$PGDATA/PG_VERSION")" = 17 || fail "cluster must be PostgreSQL 17"
test -f "$PGDATA/global/pg_control" || fail "cluster control file is missing"

# POSTGRES_USER is an SQL bootstrap role, not the operating-system owner. It
# may be cahier or unset on an existing cluster; no bootstrap is performed here.
owner="$(id -u postgres):$(id -g postgres)"
for path in "$PGDATA" "$PGDATA/PG_VERSION" "$PGDATA/global/pg_control"; do
    test "$(stat -c %u:%g "$path")" = "$owner" || fail "cluster file ownership mismatch"
done
image_version="${PG_VERSION:-}"
test "${image_version%%-*}" = 17.11 || fail "image must declare PostgreSQL 17.11"
server_version="$(postgres --version)"
[[ "$server_version" =~ ^postgres\ \(PostgreSQL\)\ 17\.11([[:space:]]|$) ]] \
    || fail "server binary must be PostgreSQL 17.11"
if test "$(id -u)" = 0; then
    exec gosu postgres "$@" -D "$PGDATA"
fi
test "$(id -u):$(id -g)" = "$owner" || fail "process must run as root or the postgres owner"
exec "$@" -D "$PGDATA"
