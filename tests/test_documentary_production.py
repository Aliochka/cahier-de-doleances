"""Production guards tested offline; no working or production DB connection."""

import copy
import os
import subprocess
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from documentary.production import (
    APPLICATION_IDENTITY,
    IDENTITY,
    ProductionDestination,
    check_backup_proof,
)
from documentary.safety import UnsafeDestination
from tests.test_documentary import isolated_databases  # noqa: F401


def proof():
    completed = datetime.now(timezone.utc).isoformat()
    return dict(
        target=dict(IDENTITY),
        application=dict(APPLICATION_IDENTITY),
        operator="Test operator",
        restore_verified=True,
        backup_completed_at=completed,
        restore_completed_at=completed,
        restored_application_revision="forms_statistics_v1",
        restored_rag_revision="rag_0007",
        backups={
            k: dict(
                kind="pg_dump-full" if k in {"application", "search"} else k,
                path=f"/backups/postgresql/test/{k}",
                bytes=100,
                sha256="a" * 64,
            )
            for k in ("application", "search", "globals", "configuration")
        },
    )


@pytest.mark.parametrize(
    "change",
    [
        {"target": APPLICATION_IDENTITY},
        {"restore_verified": False},
        {"backup_completed_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()},
        {"operator": ""},
        {"restore_completed_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()},
        {"restore_completed_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()},
        {"restore_completed_at": "2026-11-08T12:00:00"},
        {"backups": {}},
    ],
)
def test_backup_proof_must_be_current_full_and_tied_to_both_databases(change):
    value = proof()
    value.update(change)
    with pytest.raises(UnsafeDestination):
        check_backup_proof(value)


def test_schema_only_or_unverified_archive_is_not_a_full_backup():
    value = proof()
    check_backup_proof(value)
    for field, bad in [
        ("kind", "schema-only"),
        ("sha256", "0" * 64),
        ("bytes", 0),
        ("path", "/tmp/backup"),
        ("path", "/backups/postgresql/../x"),
    ]:
        changed = copy.deepcopy(value)
        changed["backups"]["search"][field] = bad
        with pytest.raises(UnsafeDestination):
            check_backup_proof(changed)


def test_only_the_exact_readonly_lexical_validation_cte_is_permitted():
    from documentary.production import DF_VALIDATION_STATEMENT

    target = ProductionDestination(
        "postgresql+psycopg2://cahier_search_maintenance@127.0.0.1:55495/cahier_search"
    )
    connection = SimpleNamespace(info={"documentary_write": False})
    try:
        target._restrict(connection, None, DF_VALIDATION_STATEMENT, None, None, None)
        for sql in (
            "WITH gone AS (DELETE FROM rag_full.spaces RETURNING *) SELECT * FROM gone",
            DF_VALIDATION_STATEMENT + "; DELETE FROM documentary.release",
            "WITH expected AS (SELECT * FROM rag_full.spaces) SELECT * FROM expected",
        ):
            with pytest.raises(UnsafeDestination):
                target._restrict(connection, None, sql, None, None, None)
    finally:
        target.close()


def test_verified_full_physical_backup_covers_both_databases():
    value = proof()
    for key in ("application", "search"):
        value["backups"][key].update(
            kind="physical-cluster",
            integrity_file="backup_manifest",
            covers=["cahier_doleances", "cahier_search"],
        )
    check_backup_proof(value)
    value["backups"]["search"]["covers"] = ["cahier_doleances"]
    with pytest.raises(UnsafeDestination):
        check_backup_proof(value)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg2://cahier_search_maintenance@127.0.0.1:55495/cahier_doleances",
        "postgresql+psycopg2://cahier@127.0.0.1:55495/cahier_search",
        "postgresql+psycopg2://cahier_search_maintenance@192.168.1.185/cahier_search",
        "postgresql+psycopg2://cahier_search_maintenance@127.0.0.1:55495/cahier_search?options=bad",
    ],
)
def test_implicit_or_other_production_destinations_rejected_before_connection(url, monkeypatch):
    monkeypatch.setattr(
        "documentary.production.create_engine", lambda *a, **kw: pytest.fail("Unexpected engine")
    )
    with pytest.raises(UnsafeDestination):
        ProductionDestination(url)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE rag_full.spaces SET verified=false",
        "DELETE FROM rag_tuning.statistics",
        "DROP SCHEMA documentary CASCADE",
        "TRUNCATE documentary.document",
        "ALTER TABLE public.answers DROP COLUMN text",
        "CREATE EXTENSION vector",
        "GRANT ALL ON SCHEMA rag_full TO cahier_search_reader",
    ],
)
def test_gdn_and_destructive_mutations_rejected(sql):
    destination = ProductionDestination(
        "postgresql+psycopg2://cahier_search_maintenance@127.0.0.1:55495/cahier_search"
    )
    try:
        for enabled in (True, False):
            with pytest.raises(UnsafeDestination):
                destination._restrict(
                    SimpleNamespace(info={"documentary_write": enabled}),
                    None,
                    sql,
                    None,
                    None,
                    None,
                )
    finally:
        destination.close()


def test_documentary_import_needs_write_transaction_and_cannot_publish():
    destination = ProductionDestination(
        "postgresql+psycopg2://cahier_search_maintenance@127.0.0.1:55495/cahier_search"
    )
    try:
        with pytest.raises(UnsafeDestination):
            destination._restrict(
                SimpleNamespace(info={}),
                None,
                "UPDATE documentary.document SET display_title='x'",
                None,
                None,
                None,
            )
        with pytest.raises(UnsafeDestination):
            with destination.transaction():
                pass
        c = SimpleNamespace(execute=lambda *a: SimpleNamespace(scalar_one=lambda: True))
        with pytest.raises(UnsafeDestination, match="cannot activate"):
            destination._unpublished(c)
    finally:
        destination.close()


def test_explicit_import_overrides_only_its_session_readonly_default(monkeypatch):
    captured = []

    def engine(url, **kwargs):
        captured.append(kwargs["connect_args"]["options"])
        return SimpleNamespace(dispose=lambda: None)

    monkeypatch.setattr("documentary.production.create_engine", engine)
    monkeypatch.setattr("documentary.production.event.listen", lambda *args: None)
    url = "postgresql+psycopg2://cahier_search_maintenance@127.0.0.1:55495/cahier_search"
    readonly = ProductionDestination(url)
    writable = ProductionDestination(url, writable=True, backup_proof=proof())
    readonly.close()
    writable.close()
    assert captured == [
        "-c statement_timeout=120000 -c lock_timeout=2000 -c default_transaction_read_only=on",
        "-c statement_timeout=120000 -c lock_timeout=2000 -c default_transaction_read_only=off",
    ]


@pytest.fixture
def readonly_role_cluster():
    # This regression installs simulated GDN objects. Do not contaminate the
    # module-scoped cluster used by the independent migration/activation test.
    yield from isolated_databases.__wrapped__()


def test_real_readonly_role_can_import_only_through_explicit_guard(
    readonly_role_cluster, monkeypatch
):
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import InternalError

    destination = readonly_role_cluster[0]
    with destination.transaction() as c:
        c.execute(text("CREATE EXTENSION vector"))
        c.execute(text("CREATE ROLE cahier_search_maintenance LOGIN"))
        c.execute(text("ALTER ROLE cahier_search_maintenance SET default_transaction_read_only=on"))
        c.execute(text("CREATE ROLE cahier_documentary_owner NOLOGIN"))
        c.execute(text("CREATE ROLE cahier_search_reader NOLOGIN"))
        c.execute(text("GRANT cahier_documentary_owner TO cahier_search_maintenance"))
        c.execute(text("CREATE SCHEMA documentary AUTHORIZATION cahier_documentary_owner"))
        c.execute(text("CREATE TABLE public.rag_alembic_version(version_num text)"))
        c.execute(text("INSERT INTO public.rag_alembic_version VALUES ('rag_0007')"))
        c.execute(text("GRANT SELECT ON public.rag_alembic_version TO cahier_search_maintenance"))
        c.execute(
            text("GRANT EXECUTE ON FUNCTION pg_control_system() TO cahier_search_maintenance")
        )
        sid = c.execute(
            text("SELECT system_identifier::text FROM pg_control_system()")
        ).scalar_one()
        oid = c.execute(
            text("SELECT oid::int FROM pg_database WHERE datname=current_database()")
        ).scalar_one()
    identity = dict(
        cluster_id=sid,
        database_oid=oid,
        database_name=destination.engine.url.database,
        schema_revision=None,
    )
    monkeypatch.setattr("documentary.production.IDENTITY", identity)

    # Reproduce the actual production role default without touching production.
    original_engine = create_engine(
        destination.engine.url.set(username="cahier_search_maintenance")
    )
    try:
        with pytest.raises(InternalError) as refused:
            with original_engine.connect() as c, c.begin():
                c.execute(text("SET LOCAL ROLE cahier_documentary_owner"))
                c.execute(text("CREATE TABLE documentary.guard_probe(value text)"))
        assert refused.value.orig.pgcode == "25006"  # read_only_sql_transaction
    finally:
        original_engine.dispose()

    def isolated_engine(url, **kwargs):
        return create_engine(
            destination.engine.url.set(username="cahier_search_maintenance"), **kwargs
        )

    monkeypatch.setattr("documentary.production.create_engine", isolated_engine)
    value = proof()
    value["target"] = identity
    target = ProductionDestination(
        "postgresql+psycopg2://cahier_search_maintenance@127.0.0.1:55495/"
        + identity["database_name"],
        writable=True,
        backup_proof=value,
    )
    try:
        with target.transaction(readonly=True) as c:
            assert c.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
        with target.transaction() as c:
            assert c.execute(text("SHOW transaction_read_only")).scalar_one() == "off"
            assert c.execute(text("SELECT current_user")).scalar_one() == "cahier_documentary_owner"
            c.execute(text("CREATE TABLE documentary.guard_probe(value text)"))
            c.execute(text("INSERT INTO documentary.guard_probe VALUES ('authorized')"))
            with pytest.raises(UnsafeDestination):
                c.execute(text("UPDATE public.rag_alembic_version SET version_num='forbidden'"))
        with target.transaction(readonly=True) as c:
            assert c.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
            assert (
                c.execute(text("SELECT value FROM documentary.guard_probe")).scalar_one()
                == "authorized"
            )
        # Exercise the FULL transfer with the actual production SQL guard, not
        # an owner-only stand-in. Sources and vectors exist only in /tmp tests.
        from documentary.artifacts import DECISIONS, Artifacts
        from documentary.editorial import load_decisions
        from documentary.integrate_local import transfer
        from documentary.representations import ELIGIBLE, prepare_lexical, vector_hash
        from documentary.storage import import_collection, migrate

        source = readonly_role_cluster[1]
        migrate(source)
        import_collection(source, Artifacts(), load_decisions(DECISIONS))
        prepare_lexical(source)
        with source.transaction() as c:
            c.execute(
                text(
                    f"UPDATE documentary.search_unit u SET embedding=CAST(:v AS public.vector),embedding_hash=:h FROM documentary.document d WHERE u.corpus_id=d.corpus_id AND u.release_id=d.release_id AND u.document_id=d.document_id AND {ELIGIBLE}"
                ),
                dict(
                    corpus="cahiers-1789-ap-stanford",
                    release="reference-documents-2-7cbcaea79991",
                    v="[" + ",".join(["1"] + ["0"] * 1023) + "]",
                    h=vector_hash([1.0] + [0.0] * 1023),
                ),
            )
            c.execute(
                text(
                    "UPDATE documentary.release SET representations_ready=true,embedding_recipe='{}'::jsonb"
                )
            )
        result = transfer(source, target, reuse_lexical=True)
        assert result["vectors"] == 10748
        assert result["source_integrity"]["public_documents"] == 0
        # The real failed verification leaves data present and readiness false.
        # Replaying the guarded import must recover without duplicates/publication.
        with target.transaction() as c:
            c.execute(
                text(
                    "UPDATE documentary.release SET representations_ready=false,statistics_ready=false"
                )
            )
        replayed = transfer(source, target, reuse_lexical=True)
        assert replayed["source_integrity"] == result["source_integrity"]
        assert replayed["vectors"] == 10748
    finally:
        target.close()
    # A separate ordinary login keeps the role's read-only default unchanged.
    engine = create_engine(destination.engine.url.set(username="cahier_search_maintenance"))
    try:
        with engine.connect() as c:
            assert c.execute(text("SHOW default_transaction_read_only")).scalar_one() == "on"
            assert (
                c.execute(text("SELECT version_num FROM public.rag_alembic_version")).scalar_one()
                == "rag_0007"
            )
    finally:
        engine.dispose()


def test_role_migration_and_prepared_activation_on_new_cluster_only(isolated_databases):  # noqa: F811
    from sqlalchemy import text

    from documentary.artifacts import DECISIONS, REFERENCE, Artifacts
    from documentary.editorial import load_decisions
    from documentary.integrate_local import transfer
    from documentary.representations import ELIGIBLE, prepare_lexical, vector_hash
    from documentary.storage import import_collection, migrate

    if not REFERENCE.exists():
        pytest.skip("Local immutable collection unavailable")
    destination = isolated_databases[0]
    url = destination.engine.url
    assert url.database.endswith("_test") and url.query["host"].startswith("/tmp/")
    binary = Path(os.environ["DOCUMENTARY_TEST_PG_BIN"])
    common = [
        str(binary / "psql"),
        "-XqAt",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        url.query["host"],
        "-p",
        url.query["port"],
        "-U",
        url.username,
        "-d",
        url.database,
    ]

    def psql(sql, *variables):
        return subprocess.run(common + list(variables), input=sql, capture_output=True, text=True)

    with destination.transaction() as c:
        c.execute(text("CREATE EXTENSION vector"))
        c.execute(text("CREATE ROLE cahier_search_maintenance LOGIN"))
        c.execute(text("CREATE ROLE cahier_search_reader LOGIN"))
        c.execute(text("CREATE TABLE public.rag_alembic_version(version_num text)"))
        c.execute(text("INSERT INTO public.rag_alembic_version VALUES ('rag_0007')"))
        c.execute(text("CREATE SCHEMA rag_full"))
        c.execute(text("CREATE TABLE rag_full.preserved(value text)"))
        c.execute(text("INSERT INTO rag_full.preserved VALUES ('unchanged')"))
        identity = c.execute(
            text("SELECT system_identifier::text FROM pg_control_system()")
        ).scalar_one()
        oid = c.execute(
            text("SELECT oid::int FROM pg_database WHERE datname=current_database()")
        ).scalar_one()

    def isolated_sql(filename):
        return (
            (Path("deploy/documentary") / filename)
            .read_text()
            .replace(IDENTITY["cluster_id"], identity)
            .replace("'cahier_search'", "'" + url.database + "'")
            .replace("<>634726", "<>" + str(oid))
            .replace("current_user<>'cahier'", "current_user<>'" + url.username + "'")
        )

    # The unmodified production SQL must refuse this isolated physical database.
    original = (Path("deploy/documentary") / "provision-gavroche.sql").read_text()
    assert psql(original).returncode != 0
    result = psql(isolated_sql("provision-gavroche.sql"))
    assert result.returncode == 0, result.stderr
    assert psql(isolated_sql("provision-gavroche.sql")).returncode == 0

    class Owner:
        @contextmanager
        def transaction(self, *, readonly=False):
            with destination.engine.connect() as c, c.begin():
                c.execute(text("SET LOCAL ROLE cahier_documentary_owner"))
                if readonly:
                    c.execute(text("SET TRANSACTION READ ONLY"))
                yield c

    owner = Owner()
    migrate(owner)
    migrate(owner)
    artifacts = Artifacts()
    import_collection(owner, artifacts, load_decisions(DECISIONS))
    prepare_lexical(owner)
    from sqlalchemy.exc import ProgrammingError

    # The dedicated owner has no privilege to write GDN objects.
    with owner.transaction() as c:
        with pytest.raises(ProgrammingError):
            c.execute(text("UPDATE rag_full.preserved SET value='forbidden'"))

    # Synthetic test vectors only. No model, inference or corpus-of-work writes.
    with owner.transaction() as c:
        c.execute(
            text(
                f"UPDATE documentary.search_unit u SET embedding=CAST(:v AS public.vector),embedding_hash=:h FROM documentary.document d WHERE u.corpus_id=d.corpus_id AND u.release_id=d.release_id AND u.document_id=d.document_id AND {ELIGIBLE}"
            ),
            dict(
                corpus="cahiers-1789-ap-stanford",
                release="reference-documents-2-7cbcaea79991",
                v="[" + ",".join(["1"] + ["0"] * 1023) + "]",
                h=vector_hash([1.0] + [0.0] * 1023),
            ),
        )
        c.execute(
            text("""UPDATE documentary.release SET representations_ready=true,
          embedding_recipe='{"model":{"revision":"5617a9f61b028005a4858fdac845db406aefb181"}}'::jsonb""")
        )

    # Transfer and replay use only the second fresh database in this private cluster.
    copied = transfer(owner, isolated_databases[1], reuse_lexical=True)
    assert copied["vectors"] == 10748 and not copied["lexical_rebuilt_on_target"]
    rebuilt = transfer(owner, isolated_databases[1])
    assert rebuilt["vectors"] == 10748 and rebuilt["lexical_rebuilt_on_target"]

    # Reusing C-locale derivatives in a French database must fail closed.
    # This database is also NEW and belongs to the same private /tmp test cluster.
    from documentary.safety import Destination

    subprocess.run(
        [
            str(binary / "createdb"),
            "-h",
            url.query["host"],
            "-p",
            url.query["port"],
            "-U",
            url.username,
            "--template=template0",
            "--locale=fr_FR.UTF-8",
            "documentary_french_test",
        ],
        check=True,
        capture_output=True,
    )
    french = Destination(url.set(database="documentary_french_test"), destination.data, identity)
    try:
        with pytest.raises(ValueError, match="representations differ"):
            transfer(owner, french, reuse_lexical=True)
        with french.transaction(readonly=True) as c:
            assert (
                c.execute(
                    text(
                        "SELECT statistics_ready OR representations_ready OR publication_authorized FROM documentary.release"
                    )
                ).scalar_one()
                is False
            )
    finally:
        french.close()

    variables = [
        "-v",
        "approval_id=isolated-test-authorization",
        "-v",
        "approval_sha256=" + "a" * 64,
        "-v",
        "decided_by=Test operator",
        "-v",
        "approved_at=" + datetime.now(timezone.utc).isoformat(),
    ]
    sql = isolated_sql("activate-1789.sql")
    assert psql(sql, *variables, "-v", "authorize_publication=false").returncode != 0
    result = psql(sql, *variables, "-v", "authorize_publication=true")
    assert result.returncode == 0, result.stderr
    with owner.transaction(readonly=True) as c:
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM documentary.document WHERE readable AND searchable AND catalogue_visible"
                )
            ).scalar_one()
            == 1224
        )
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM documentary.editorial_decision WHERE property='publication'"
                )
            ).scalar_one()
            == 1224
        )
        assert (
            c.execute(
                text("SELECT count(*) FROM documentary.document WHERE NOT candidate AND readable")
            ).scalar_one()
            == 0
        )
        assert (
            c.execute(
                text("SELECT count(*) FROM documentary.search_unit WHERE NOT searchable")
            ).scalar_one()
            == 2
        )
    with destination.engine.connect() as c:
        assert c.execute(text("SELECT value FROM rag_full.preserved")).scalar_one() == "unchanged"
        assert not c.execute(
            text(
                "SELECT has_database_privilege('cahier_documentary_owner',current_database(),'CREATE')"
            )
        ).scalar_one()
    assert psql(sql, *variables, "-v", "authorize_publication=true").returncode != 0
