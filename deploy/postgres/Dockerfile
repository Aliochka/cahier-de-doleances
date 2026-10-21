# Registry metadata verified 2026-10-21: linux/amd64 PG_VERSION=17.11-1.pgdg13+2.
# Upstream v0.8.7 Dockerfile builds pgvector with OPTFLAGS="" from postgres:17-trixie.
FROM pgvector/pgvector:0.8.7-pg17-trixie@sha256:7a7e9f22015b67edb4bef5c59daeebcd7e74bfa570df6ce60ae01237c8648a84

RUN test "$PG_MAJOR" = 17 \
    && test "${PG_VERSION%%-*}" = 17.11 \
    && test -f /usr/share/postgresql/17/extension/vector.control \
    && grep -Eq "default_version[[:space:]]*=[[:space:]]*'0.8.7'" /usr/share/postgresql/17/extension/vector.control \
    && test -f /usr/lib/postgresql/17/lib/vector.so \
    && localedef -i fr_FR -c -f UTF-8 -A /usr/share/locale/locale.alias fr_FR.UTF-8

COPY deploy/postgres/existing-cluster.sh /usr/local/bin/existing-cluster.sh
ENTRYPOINT ["bash", "/usr/local/bin/existing-cluster.sh"]
CMD ["postgres"]
