"""Explicit phase-4 exception for the previously verified LOCAL application cluster.

The original /tmp-only Destination remains unchanged. Never accepts a remote URL
or a different cluster, and never permits mutations outside documentary.
"""

import hashlib
import json
import re
from contextlib import contextmanager
from pathlib import Path

from cahier_rag.safety import inspect_database
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from .safety import UnsafeDestination

LOCAL_IDENTITY = dict(
    cluster_id="7697259424657850634",
    database_oid=2106636,
    database_name="cahier_rag",
    schema_revision=None,
)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class LocalApplicationDestination:
    def __init__(self, url, *, backup=None, writable=False):
        parsed = make_url(url)
        if (
            parsed.drivername != "postgresql+psycopg2"
            or parsed.host is not None
            or parsed.database != "cahier_rag"
            or set(parsed.query) != {"host"}
            or parsed.query["host"] != "/var/run/postgresql"
            or parsed.username not in {None, "ro"}
        ):
            raise UnsafeDestination(
                "Only the explicitly identified local Unix-socket cahier_rag is authorized"
            )
        self.writable = writable
        self.backup = Path(backup) if backup else None
        self.engine = create_engine(
            parsed,
            poolclass=NullPool,
            hide_parameters=True,
            connect_args={
                "connect_timeout": 3,
                "options": "-c statement_timeout=120000 -c lock_timeout=2000"
                + ("" if writable else " -c default_transaction_read_only=on"),
            },
        )
        self.migration = (Path(__file__).parent / "migrations/versions/doc_0001.sql").read_text()
        event.listen(self.engine, "before_cursor_execute", self._restrict)

    def _restrict(self, connection, cursor, statement, parameters, context, executemany):
        sql = statement.strip()
        if not connection.info.get("documentary_write"):
            if re.match(r"^(SELECT|SHOW|SET)\b", sql, re.I):
                return
            raise UnsafeDestination(
                "Mutations require the explicitly guarded documentary transaction"
            )
        if sql == self.migration.strip():
            return
        if re.match(
            r"^(SELECT|SHOW|SET|SAVEPOINT|RELEASE SAVEPOINT|ROLLBACK TO SAVEPOINT)\b", sql, re.I
        ):
            return
        if re.match(
            r"^(INSERT INTO|UPDATE|DELETE FROM|CREATE TABLE|ANALYZE) documentary\.", sql, re.I
        ):
            return
        if sql == "CREATE SCHEMA IF NOT EXISTS documentary":
            return
        if sql in {
            "GRANT USAGE ON SCHEMA documentary TO cahier_search_reader",
            "GRANT SELECT ON documentary.corpus,documentary.release,documentary.document,documentary.search_unit,documentary.lexical_term_statistics,documentary.alembic_version TO cahier_search_reader",
            "REVOKE ALL ON documentary.editorial_decision FROM cahier_search_reader",
        }:
            return
        raise UnsafeDestination(
            "Local documentary maintenance refuses any mutation outside documentary"
        )

    @contextmanager
    def transaction(self, *, readonly=False):
        if not readonly and not self.writable:
            raise UnsafeDestination("Read-only documentary application destination")
        with self.engine.connect() as c, c.begin():
            c.info["documentary_write"] = False
            if readonly:
                c.execute(text("SET TRANSACTION READ ONLY"))
            identity = inspect_database(c).to_dict()
            if (
                identity != LOCAL_IDENTITY
                or c.execute(text("SELECT inet_server_addr()")).scalar_one() is not None
            ):
                raise UnsafeDestination("Physical local application identity mismatch")
            if (
                c.execute(text("SELECT version_num FROM public.rag_alembic_version")).scalar_one()
                != "rag_0007"
            ):
                raise UnsafeDestination("Existing RAG revision must remain rag_0007")
            if not readonly:
                if self.backup is None:
                    raise UnsafeDestination("Verified backup manifest required before local writes")
                manifest = json.loads(self.backup.read_text())
                if manifest["target"] != identity:
                    raise UnsafeDestination("Backup target mismatch")
                for name, expected in manifest["files"].items():
                    if digest(self.backup.parent / name) != expected:
                        raise UnsafeDestination("Backup fingerprint mismatch")
                c.info["documentary_write"] = True
            try:
                yield c
            finally:
                c.info["documentary_write"] = False

    def close(self):
        self.engine.dispose()
