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
