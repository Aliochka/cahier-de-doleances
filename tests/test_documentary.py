"""Phase 1: pure editorial tests and opt-in tests in a newly created private cluster."""

import copy
import os
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from documentary.artifacts import CORPUS, DECISIONS, GENERATION, REFERENCE, Artifacts, keyed
from documentary.editorial import load_decisions, replay
from documentary.safety import Destination, UnsafeDestination
from documentary.storage import apply_editorial, import_collection, migrate, verify


def sample():
    doc = dict(id="doc", text_sha256="a" * 64, extent_id="extent", full_text="Été 😀\nfin")
    unit = dict(id="unit", document_id="doc", text_sha256="b" * 64)
    artifacts = SimpleNamespace(
        documents={"doc": doc}, units={"unit": unit}, metadata={"doc": {"title": "Source"}}
    )
    event = dict(
        decision_id="decision-1",
        revision_id="v1",
        sequence=1,
        corpus_id=CORPUS,
        source_generation=GENERATION,
        document_id="doc",
        unit_id="unit",
        expected_document_hash="a" * 64,
        expected_extent_id="extent",
        expected_unit_hash="b" * 64,
        property="search_enabled",
        value=False,
        reason_code="test",
        justification="Explicit test",
        evidence={"source": "synthetic"},
        decided_by="test",
        decided_at="2026-11-07T00:00:00Z",
        supersedes_id=None,
    )
    bundle = dict(
        format_version=1,
        revision_id="v1",
        corpus_id=CORPUS,
        source_generation=GENERATION,
        decisions=[event],
    )
    return artifacts, bundle


def test_editorial_exclusion_and_explicit_reintegration():
    artifacts, bundle = sample()
    assert replay(artifacts, bundle)["units"] == {"unit": False}
    bundle["decisions"].append(
        dict(
            bundle["decisions"][0],
            decision_id="decision-2",
            revision_id="v2",
            sequence=2,
            value=True,
            supersedes_id="decision-1",
        )
    )
    projected = replay(artifacts, bundle)
    assert projected["units"] == {"unit": True}
    assert not any(
        projected["documents"]["doc"][k] for k in ("readable", "searchable", "catalogue_visible")
    )


@pytest.mark.parametrize(
    "mutation",
    [
        {"expected_document_hash": "c" * 64},
        {"expected_extent_id": "old"},
        {"expected_unit_hash": "c" * 64},
        {"source_generation": "old"},
        {"property": "unknown"},
        {"value": "false"},
        {"supersedes_id": "missing"},
        {"evidence": {}},
        {"decided_at": "2026-11-07"},
    ],
)
def test_editorial_rejects_incompatible_or_ambiguous_decisions(mutation):
    artifacts, bundle = sample()
    bundle["decisions"][0].update(mutation)
    with pytest.raises((ValueError, KeyError)):
        replay(artifacts, bundle)


def test_editorial_rejects_concurrent_overrides():
    artifacts, bundle = sample()
    bundle["decisions"].append(dict(bundle["decisions"][0], decision_id="decision-2", sequence=2))
    with pytest.raises(ValueError, match="succession"):
        replay(artifacts, bundle)


def test_duplicate_source_ids_and_modified_reference_manifest(tmp_path):
    with pytest.raises(ValueError, match="Duplicate"):
        keyed([{"id": "same"}, {"id": "same"}])
    (tmp_path / "manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="manifest fingerprint"):
        Artifacts(tmp_path)


def test_warning_and_title_are_reversible_without_changing_source():
    artifacts, bundle = sample()
    before = copy.deepcopy(artifacts.documents)
    base = dict(bundle["decisions"][0], unit_id=None, expected_unit_hash=None)
    bundle["decisions"] = [
        dict(base, decision_id="title", sequence=1, property="display_title", value="Presentation"),
        dict(
            base,
            decision_id="warning",
            sequence=2,
            property="warning",
            value={
                "key": "lacuna",
                "enabled": True,
                "message": "Source warning",
                "start_offset": 4,
                "end_offset": 5,
            },
        ),
    ]
    projected = replay(artifacts, bundle)
    assert projected["documents"]["doc"]["display_title"] == "Presentation"
    assert projected["documents"]["doc"]["warnings"]["lacuna"]["start_offset"] == 4
    bundle["decisions"].extend(
        [
            dict(
                base,
                decision_id="reset-title",
                sequence=3,
                property="display_title",
                value=None,
                supersedes_id="title",
            ),
            dict(
                base,
                decision_id="reset-warning",
                sequence=4,
                property="warning",
                value={"key": "lacuna", "enabled": False},
                supersedes_id="warning",
            ),
        ]
    )
    projected = replay(artifacts, bundle)
    assert projected["documents"]["doc"]["display_title"] == "Source"
    assert projected["documents"]["doc"]["warnings"] == {}
    assert artifacts.documents == before


def test_publication_is_not_authorized():
    artifacts, bundle = sample()
    event = bundle["decisions"][0]
    bundle["decisions"] = [
        dict(
            event,
            property="publication",
            unit_id=None,
            expected_unit_hash=None,
            value={"catalogue": True, "read": True, "search": True},
        )
    ]
    with pytest.raises(ValueError, match="publication"):
        replay(artifacts, bundle)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg2://localhost/documentary_test",
        "postgresql+psycopg2:///production?host=/tmp",
        "postgresql+psycopg2:///documentary_test?host=/var/run/postgresql",
        "postgresql+psycopg2:///documentary_test?host=/tmp&service=production",
    ],
)
def test_rejects_implicit_or_non_private_destinations(url, tmp_path):
    with pytest.raises(UnsafeDestination):
        Destination(url, str(tmp_path), "123")


@pytest.fixture(scope="module")
def real_artifacts():
    if not REFERENCE.exists():
        pytest.skip("Immutable historical artifacts are local and not versioned")
    return Artifacts(), load_decisions(DECISIONS)


def test_real_artifacts_and_acquired_decisions(real_artifacts):
    artifacts, bundle = real_artifacts
    projection = replay(artifacts, bundle)
    assert artifacts.counts() == dict(
        notices=1305,
        documents=1267,
        probable_cahiers=1224,
        other_documents=43,
        units=11391,
        cahier_units=10750,
    )
    excluded = {key for key, enabled in projection["units"].items() if not enabled}
    assert excluded == {
        "ap1789-technical-passage-1:fffb19e46c6025e22b17d54c370c",
        "ap1789-technical-passage-1:32ae8c839247d77b503fba421372",
    }
    avallon = next(d for d in artifacts.documents.values() if d["id"].endswith("2_1_1602"))
    assert all(projection["units"][key] for key in avallon["passage_ids"])
    assert projection["documents"][avallon["id"]]["display_title"].startswith(
        "Cahier des habitants d'Aunay-la-Côte"
    )
    assert len(projection["documents"][avallon["id"]]["warnings"]) == 1


@pytest.fixture(scope="module")
def isolated_databases():
    configured = os.environ.get("DOCUMENTARY_TEST_PG_BIN")
    if not configured:
        pytest.skip("Set DOCUMENTARY_TEST_PG_BIN to explicitly create a NEW local test cluster")
    binary = Path(configured)
    with tempfile.TemporaryDirectory(prefix="doc-pg-") as tmp:
        root = Path(tmp)
        socket, data = root / "socket", root / "data"
        socket.mkdir()

        def run(name, *args):
            return subprocess.run(
                [str(binary / name), *map(str, args)], check=True, capture_output=True, text=True
            ).stdout

        run(
            "initdb",
            "-D",
            data,
            "-A",
            "trust",
            "--no-sync",
            "--username=doc_test_admin",
            "--encoding=UTF8",
            "--locale=C",
        )
        run(
            "pg_ctl",
            "-D",
            data,
            "-l",
            root / "postgres.log",
            "-o",
            f"-k {socket} -p 55489 -c listen_addresses=''",
            "-w",
            "start",
        )
        destinations = []
        try:
            for name in ("documentary_first_test", "documentary_rebuild_test"):
                run("createdb", "-h", socket, "-p", "55489", "-U", "doc_test_admin", name)
                system_id = run(
                    "psql",
                    "-XAt",
                    "-h",
                    socket,
                    "-p",
                    "55489",
                    "-U",
                    "doc_test_admin",
                    "-d",
                    name,
                    "-c",
                    "SELECT system_identifier FROM pg_control_system()",
                ).strip()
                destinations.append(
                    Destination(
                        f"postgresql+psycopg2://doc_test_admin@/{name}?host={socket}&port=55489",
                        data,
                        system_id,
                    )
                )
            yield destinations
        finally:
            for destination in destinations:
                destination.close()
            run("pg_ctl", "-D", data, "-m", "fast", "-w", "stop")


def test_real_import_idempotence_rebuild_and_editorial_rollback(isolated_databases, real_artifacts):
    artifacts, bundle = real_artifacts
    first, rebuilt = isolated_databases
    for destination in (first, rebuilt):
        migrate(destination)
        migrate(destination)
        assert import_collection(destination, artifacts, bundle)["imported"] is True
        assert import_collection(destination, artifacts, bundle)["imported"] is False
        with destination.transaction(readonly=True) as c:
            assert verify(c, artifacts, bundle)["candidate_permitted_units"] == 10748
            assert (
                c.execute(text("SELECT version_num FROM documentary.alembic_version")).scalar_one()
                == "doc_0001"
            )
            assert (
                c.execute(
                    text(
                        "SELECT count(*) FROM pg_namespace WHERE nspname IN ('rag','rag_full','rag_tuning')"
                    )
                ).scalar_one()
                == 0
            )
            assert (
                c.execute(
                    text("SELECT count(*) FROM documentary.document WHERE NOT candidate")
                ).scalar_one()
                == 43
            )

    # A real SQL round trip preserves non-BMP offsets, not just Python's indexing.
    with first.transaction(readonly=True) as c:
        assert c.execute(text("SELECT substring('Été 😀 fin' FROM 5 FOR 1)")).scalar_one() == "😀"

    with first.transaction() as c:
        with pytest.raises(ValueError, match="differs"):
            with c.begin_nested():
                c.execute(
                    text(
                        "UPDATE documentary.document SET full_text=full_text || 'changed' WHERE edition_order=1"
                    )
                )
                verify(c, artifacts, bundle)
        with pytest.raises(Exception, match="ready"):
            with c.begin_nested():
                c.execute(
                    text("UPDATE documentary.corpus SET active_release_id=:release"),
                    {"release": GENERATION},
                )
        with pytest.raises(Exception):
            with c.begin_nested():
                c.execute(text("UPDATE documentary.release SET state='ready'"))

    changed = copy.deepcopy(bundle)
    changed["revision_id"] = "1789-editorial-test-2"
    original = bundle["decisions"][0]
    changed["decisions"].append(
        dict(
            original,
            decision_id="synthetic-reintegration",
            revision_id=changed["revision_id"],
            sequence=1,
            value=True,
            supersedes_id=original["decision_id"],
        )
    )
    assert apply_editorial(first, artifacts, bundle, changed)["excluded_units"] == 1
    with pytest.raises(ValueError, match="Release"):
        import_collection(
            first, artifacts, bundle
        )  # An older file cannot silently overwrite the policy.
    assert import_collection(first, artifacts, changed)["excluded_units"] == 1
    reverted = copy.deepcopy(changed)
    reverted["revision_id"] = "1789-editorial-test-3"
    reverted["decisions"].append(
        dict(
            original,
            decision_id="synthetic-reexclusion",
            revision_id=reverted["revision_id"],
            sequence=1,
            value=False,
            supersedes_id="synthetic-reintegration",
        )
    )
    assert apply_editorial(first, artifacts, changed, reverted)["excluded_units"] == 2
    corrupt = copy.deepcopy(reverted)
    corrupt["decisions"][-1]["expected_unit_hash"] = "0" * 64
    with pytest.raises(ValueError, match="fingerprint"):
        import_collection(first, artifacts, corrupt)
    with first.transaction(readonly=True) as c:
        assert verify(c, artifacts, reverted)["excluded_units"] == 2


def test_physical_guard_rejects_wrong_identity_and_gdn_marker(isolated_databases):
    first = isolated_databases[0]
    wrong = Destination(str(first.engine.url), first.data, "123")
    try:
        with pytest.raises(UnsafeDestination):
            with wrong.transaction():
                pytest.fail("Must not reach writer")
    finally:
        wrong.close()
    # Synthetic marker only in the newly created private cluster; never a real GDN table.
    engine = create_engine(first.engine.url)
    try:
        with engine.begin() as c:
            c.execute(text("CREATE SCHEMA rag_full"))
        with pytest.raises(UnsafeDestination):
            with first.transaction():
                pytest.fail("Must not write in an existing RAG destination")
    finally:
        with engine.begin() as c:
            c.execute(text("DROP SCHEMA rag_full"))
        engine.dispose()
