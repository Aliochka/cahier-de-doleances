"""Vérification des destinations physiques avant toute écriture ou migration RAG."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import SQLAlchemyError

from cahier_rag.db import source_connection


class DatabaseSafetyError(ValueError):
    """Refus sûr, sans URL ni détail de connexion dans le message."""


@dataclass(frozen=True)
class DatabaseIdentity:
    cluster_id: str
    database_oid: int
    database_name: str
    schema_revision: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def inspect_database(connection: Connection, *, source: bool = False) -> DatabaseIdentity:
    try:
        row = (
            connection.execute(
                text("""
            SELECT c.system_identifier::text AS cluster_id, d.oid::bigint AS database_oid,
                   current_database() AS database_name
            FROM pg_catalog.pg_database d
            CROSS JOIN pg_catalog.pg_control_system() c
            WHERE d.datname = current_database()
        """)
            )
            .mappings()
            .one()
        )
        revision = None
        if (
            source
            and connection.execute(
                text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
            ).scalar_one()
        ):
            revision = connection.execute(
                text("SELECT version_num FROM public.alembic_version")
            ).scalar_one()
        return DatabaseIdentity(**row, schema_revision=revision)
    except SQLAlchemyError:
        raise DatabaseSafetyError(
            "Identité PostgreSQL invérifiable ; vérifier notamment le droit EXECUTE sur pg_control_system()."
        ) from None


def assert_distinct(source: DatabaseIdentity, target: DatabaseIdentity) -> None:
    if (source.cluster_id, source.database_oid) == (target.cluster_id, target.database_oid):
        raise DatabaseSafetyError("La source et la destination désignent la même base PostgreSQL.")


class DatabaseGuard:
    """Les moteurs restent explicites ; les transactions sources finissent avant la cible."""

    def __init__(self, source: Engine, target: Engine):
        self.source = source
        self.target = target

    def source_identity(self) -> DatabaseIdentity:
        with source_connection(self.source) as connection:
            identity = inspect_database(connection, source=True)
        if identity.database_name != self.source.url.database:
            raise DatabaseSafetyError("La base source réelle diffère de la base configurée.")
        return identity

    @contextmanager
    def transaction(self) -> Iterator[tuple[Connection, DatabaseIdentity]]:
        source = self.source_identity()
        with self.target.connect() as connection, connection.begin():
            target = inspect_database(connection)
            if target.database_name != self.target.url.database:
                raise DatabaseSafetyError("La base RAG réelle diffère de la base configurée.")
            assert_distinct(source, target)
            corpus_present = connection.execute(
                text("""
                SELECT to_regclass('public.answers') IS NOT NULL
                    OR to_regclass('public.contributions') IS NOT NULL
                    OR to_regclass('public.forms') IS NOT NULL
                    OR to_regclass('public.questions') IS NOT NULL
                    OR to_regclass('public.alembic_version') IS NOT NULL
            """)
            ).scalar_one()
            if corpus_present:
                raise DatabaseSafetyError(
                    "La destination contient un schéma applicatif source ; opération refusée."
                )
            yield connection, source
