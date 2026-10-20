"""Lecture publique bornée ; les gardes de maintenance restent inchangés."""

from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError, TimeoutError

from cahier_rag.embeddings.registry import MODELS
from cahier_rag.fullcorpus.audit import fingerprint
from cahier_rag.fullcorpus.store import FullStore
from cahier_rag.safety import DatabaseSafetyError, assert_distinct, inspect_database
from cahier_rag.search.service.control import (
    SearchNotReady,
    SearchTimeout,
    SearchUnavailable,
)
from cahier_rag.vector.preparation import TokenConfig


def create_search_engine(url):
    """URL dédiée validée par load_settings ; jamais de repli sur DATABASE_URL."""
    return create_engine(
        url,
        pool_size=2,
        max_overflow=0,
        pool_timeout=1,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "connect_timeout": 1,
            "options": "-c default_transaction_read_only=on -c statement_timeout=1000 "
            "-c lock_timeout=500",
        },
        execution_options={"postgresql_readonly": True},
    )


class ReadConnection:
    """Seule surface SQL nécessaire aux lecteurs existants.

    Chaque instruction reçoit le budget résiduel, y compris après les SET LOCAL
    historiques de 30 s. Une boucle ANN ne peut pas renouveler son budget.
    """

    def __init__(self, connection, budget):
        self.connection, self.budget = connection, budget

    def execute(self, statement, parameters=None):
        self.budget.check()
        remaining = max(1, int(self.budget.remaining() * 1000))
        self.connection.execute(
            text("SELECT set_config('statement_timeout', :timeout, true)"),
            {"timeout": str(remaining)},
        )
        return self.connection.execute(statement, parameters or {})


class ReadGuard:
    def __init__(self, source, target, budget):
        self.source, self.target, self.budget = source, target, budget

    @contextmanager
    def _connect(self, engine):
        try:
            self.budget.check()
            with engine.connect() as raw:
                raw = raw.execution_options(postgresql_readonly=True)
                with self.budget.connection(raw.connection.driver_connection), raw.begin():
                    yield ReadConnection(raw, self.budget)
            self.budget.check()
        except DBAPIError as exc:
            self.budget.check()
            if getattr(exc.orig, "pgcode", None) == "57014":
                raise SearchTimeout(self.budget.stage) from None
            raise SearchUnavailable("Connexion de recherche indisponible.") from None
        except (SQLAlchemyError, TimeoutError):
            self.budget.check()
            raise SearchUnavailable("Connexion de recherche indisponible.") from None
        except DatabaseSafetyError:
            self.budget.check()
            raise SearchNotReady("Identité PostgreSQL invérifiable.") from None

    def source_identity(self):
        with self._connect(self.source) as connection:
            identity = inspect_database(connection, source=True)
            if identity.database_name != self.source.url.database:
                raise SearchNotReady("Base source inattendue.")
            return identity

    @contextmanager
    def transaction(self):
        source = self.source_identity()
        with self._connect(self.target) as connection:
            target = inspect_database(connection)
            if target.database_name != self.target.url.database:
                raise SearchNotReady("Base de recherche inattendue.")
            try:
                assert_distinct(source, target)
            except DatabaseSafetyError:
                raise SearchNotReady(
                    "Les bases source et recherche doivent être distinctes."
                ) from None
            if connection.execute(
                text("""SELECT
                to_regclass('public.answers') IS NOT NULL OR
                to_regclass('public.contributions') IS NOT NULL OR
                to_regclass('public.questions') IS NOT NULL OR
                to_regclass('public.forms') IS NOT NULL OR
                to_regclass('public.alembic_version') IS NOT NULL""")
            ).scalar_one():
                raise SearchNotReady("Une base applicative ne peut pas servir de destination RAG.")
            yield connection, source


def check_reader_role(connection):
    """Les options READ ONLY ne compensent pas un rôle propriétaire/écrivain."""
    unsafe = connection.execute(
        text("""SELECT
        (SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls
         FROM pg_roles WHERE rolname=current_user)
        OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member=
                   (SELECT oid FROM pg_roles WHERE rolname=current_user))
        OR EXISTS (
          SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname IN ('rag','rag_full','rag_tuning') AND c.relkind IN ('r','p')
          AND (has_table_privilege(c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER')
               OR pg_has_role(c.relowner,'MEMBER')))
        OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspname IN ('public','rag','rag_full','rag_tuning')
                   AND has_schema_privilege(oid,'CREATE'))
        OR has_database_privilege(current_database(),'CREATE')""")
    ).scalar_one()
    if unsafe:
        raise SearchNotReady(
            "Le rôle de recherche doit être non propriétaire et limité à la lecture."
        )


class ReadStore:
    """Sous-ensemble de FullStore requis par TunedSearch/ann_search."""

    space = "full"

    def __init__(self, guard):
        self.guard = guard

    def state(self, connection=None):
        return FullStore(self.guard, self.space).state(connection)


class SearchReader:
    """Ne possède aucune méthode d'import, de migration ou d'écriture."""

    space = "full"

    def __init__(self, source, target):
        self.source, self.target = source, target
        self.generation = None

    def store(self, budget):
        return ReadStore(ReadGuard(self.source, self.target, budget))

    def validate(self, budget):
        store = self.store(budget)
        with store.guard.transaction() as (connection, source):
            check_reader_role(connection)
            state = store.state(connection)
            manifest = state["manifest"]
            expected = dict(model=MODELS["bge-m3"].to_dict(), tokens=TokenConfig().to_dict())
            if (
                not all(state[k] for k in ("verified", "extraction_complete", "vectors_complete"))
                or state["documents"] != state["expected_units"]
                or state["documents"] != state["vector_cursor"]
                or state["segments"] < state["documents"]
                or manifest.get("audit_source") != source.to_dict()
                or manifest.get("space") != self.space
                or manifest.get("corpus") != "gdn-2019"
                or manifest.get("normalize") is not True
                or manifest.get("storage") != "float32"
                or any(manifest.get(key) != value for key, value in expected.items())
            ):
                raise SearchNotReady("Corpus ou recette d'embedding incompatible.")
            revision = connection.execute(
                text("SELECT version_num FROM public.rag_alembic_version")
            ).scalar_one()
            stats = (
                connection.execute(
                    text("""SELECT documents,corpus_hash,version
                FROM rag_tuning.statistics WHERE space_id=:space"""),
                    {"space": self.space},
                )
                .mappings()
                .one_or_none()
            )
            indexes = (
                connection.execute(
                    text("""SELECT c.relname,i.indisvalid,i.indisready,am.amname
                FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid
                JOIN pg_class t ON t.oid=i.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace
                JOIN pg_am am ON am.oid=c.relam
                WHERE n.nspname='rag_full' AND t.relname IN ('documents_full','segments_full')
                AND am.amname IN ('gin','hnsw')""")
                )
                .mappings()
                .all()
            )
            if (
                revision != "rag_0007"
                or stats is None
                or stats["version"] != 1
                or stats["documents"] != state["documents"]
                or stats["corpus_hash"] != state["chain_hash"]
                or not any(
                    i["amname"] == "gin" and i["indisvalid"] and i["indisready"] for i in indexes
                )
                or not any(
                    i["relname"] == "segments_full_hnsw" and i["indisvalid"] and i["indisready"]
                    for i in indexes
                )
            ):
                raise SearchNotReady("Statistiques, révision ou index incompatibles.")
        generation = fingerprint(
            {key: state[key] for key in ("recipe_hash", "chain_hash", "documents")}
        )
        if self.generation is not None and generation != self.generation:
            raise SearchNotReady("La génération du corpus a changé ; redémarrer le service.")
        self.generation = generation
        return generation

    def close(self):
        self.source.dispose()
        self.target.dispose()
