"""Stockage réel, reprise au milieu des Autre et absence d'écrasement."""

import os
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import event, func, inspect, select, text

from cahier_rag.config import load_settings
from cahier_rag.db import create_rag_engine
from cahier_rag.extraction import ExtractionError, ExtractionSpec
from cahier_rag.migrate import upgrade_schema
from cahier_rag.pipeline import run_extraction
from cahier_rag.safety import DatabaseGuard, DatabaseSafetyError
from cahier_rag.schema import manifests, memberships, units
from cahier_rag.sources.gdn import Cursor, GdnReader
from cahier_rag.storage import ConcurrentProgress, DocumentConflict, RagStore

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def rag_databases():
    source = os.getenv("RAG_TEST_DATABASE_URL")
    target = os.getenv("RAG_STORAGE_TEST_DATABASE_URL")
    if not source or not target:
        pytest.skip(
            "Définir RAG_TEST_DATABASE_URL et RAG_STORAGE_TEST_DATABASE_URL vers deux bases de test distinctes"
        )
    settings = load_settings(
        environ={"RAG_SOURCE_DATABASE_URL": source, "RAG_DATABASE_URL": target}
    )
    if not all(
        url.database.endswith("_test")
        for url in (settings.require_source_url(), settings.require_rag_url())
    ):
        pytest.fail("Les deux bases doivent être des bases _test explicitement dédiées")
    upgrade_schema(settings)
    return settings


@pytest.fixture
def stored(rag_databases, pg_source):
    target = create_rag_engine(rag_databases)
    store = RagStore(DatabaseGuard(pg_source["engine"], target))
    corpus = "rag005-test:" + uuid4().hex
    spec = ExtractionSpec(
        limit=5, corpus_id=corpus, contribution_id=pg_source["contributions"][0], batch_size=1
    )
    try:
        yield store, spec, pg_source
    finally:
        try:
            with store.guard.transaction() as (connection, source):
                connection.execute(
                    manifests.delete().where(manifests.c.parameters["corpus_id"].astext == corpus)
                )
                connection.execute(units.delete().where(units.c.corpus_id == corpus))
        finally:
            target.dispose()


def counts(store, spec):
    with store.guard.transaction() as (connection, source):
        return connection.execute(
            select(func.count()).select_from(units).where(units.c.corpus_id == spec.corpus_id)
        ).scalar_one()


def test_migration_is_independent_and_repeatable(rag_databases, stored):
    store, spec, fixture = stored
    upgrade_schema(rag_databases)
    with store.guard.transaction() as (connection, source):
        assert (
            connection.execute(
                text("SELECT version_num FROM public.rag_alembic_version")
            ).scalar_one()
            == "rag_0003"
        )
        assert set(inspect(connection).get_table_names(schema="rag")) == {
            "text_units",
            "extractions",
            "extraction_documents",
            "checkpoints",
            "lexical_corpora",
            "lexical_members",
            "lexical_vectors",
            "vector_spaces",
            "vector_representations",
        }
        assert (
            connection.execute(text("SELECT to_regclass('public.alembic_version')")).scalar_one()
            is None
        )
        assert "ix_rag_units_questionnaire" in {
            item["name"] for item in inspect(connection).get_indexes("text_units", schema="rag")
        }


def test_interrupted_resume_matches_uninterrupted_exactly(stored):
    store, spec, fixture = stored
    direct = run_extraction(store, store.create_extraction(spec).extraction_id)
    interrupted = store.create_extraction(spec)
    interrupted = run_extraction(store, interrupted.extraction_id, max_batches=5)
    assert interrupted.status == "running"
    assert interrupted.cursor.answer_id == fixture["answers"][2]
    assert interrupted.cursor.unit_index == 1
    assert fixture["engine"].pool.checkedout() == 0
    resumed = run_extraction(store, interrupted.extraction_id)
    assert resumed.status == direct.status == "completed"
    assert resumed.document_count == direct.document_count == 5
    expected = [unit.to_json() for unit in store.iter_documents(direct.extraction_id, batch_size=2)]
    assert [unit.to_json() for unit in store.iter_documents(resumed.extraction_id)] == expected
    assert counts(store, spec) == 5
    assert run_extraction(store, resumed.extraction_id) == resumed


def test_same_text_different_ids_and_fidelity_are_preserved(stored):
    store, spec, fixture = stored
    state = run_extraction(store, store.create_extraction(spec).extraction_id)
    result = list(store.iter_documents(state.extraction_id))
    assert result[0].text == result[1].text == "Non"
    assert result[0].document_id != result[1].document_id
    assert result[0].answer_id > 2**53
    assert result[0].external_contribution_id.startswith("000:")
    source = GdnReader(
        fixture["engine"], corpus_id=spec.corpus_id, contribution_id=spec.contribution_id
    )
    assert [unit.to_json() for unit in result] == [
        unit.to_json() for unit in source.iter_documents(limit=5)
    ]


def test_exact_committed_batch_retry_is_idempotent(stored):
    store, spec, fixture = stored
    state = store.create_extraction(spec)
    reader = GdnReader(
        fixture["engine"],
        corpus_id=spec.corpus_id,
        contribution_id=spec.contribution_id,
        batch_size=1,
    )
    batch = reader.read_batch()
    first = store.persist_batch(state.extraction_id, batch, expected_revision=0, expected_spec=spec)
    second = store.persist_batch(
        state.extraction_id, batch, expected_revision=0, expected_spec=spec
    )
    assert first == second
    assert counts(store, spec) == 1


def test_conflicting_hash_rolls_back_entire_batch(stored):
    store, spec, fixture = stored
    reader = GdnReader(
        fixture["engine"],
        corpus_id=spec.corpus_id,
        contribution_id=spec.contribution_id,
        batch_size=2,
    )
    batch = reader.read_batch()
    first = store.create_extraction(spec)
    one = replace(
        batch,
        documents=batch.documents[:1],
        next_cursor=Cursor.after_document(batch.documents[0]),
        exhausted=False,
    )
    store.persist_batch(first.extraction_id, one, expected_revision=0, expected_spec=spec)
    second = store.create_extraction(spec)
    changed = replace(
        batch, documents=(replace(batch.documents[0], text="Contenu modifié"), batch.documents[1])
    )
    with pytest.raises(DocumentConflict):
        store.persist_batch(second.extraction_id, changed, expected_revision=0, expected_spec=spec)
    assert counts(store, spec) == 1
    assert store.get_state(second.extraction_id).document_count == 0
    with store.guard.transaction() as (connection, source):
        assert (
            connection.execute(
                select(func.count())
                .select_from(memberships)
                .where(memberships.c.extraction_id == second.extraction_id)
            ).scalar_one()
            == 0
        )


def test_failure_before_checkpoint_rolls_back_documents_and_associations(stored):
    store, spec, fixture = stored
    initial = store.create_extraction(spec)

    def fail(connection, cursor, statement, parameters, context, many):
        if statement.startswith("UPDATE rag.checkpoints"):
            raise RuntimeError("Interruption simulée avant checkpoint")

    event.listen(store.guard.target, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="Interruption simulée"):
            run_extraction(store, initial.extraction_id)
    finally:
        event.remove(store.guard.target, "before_cursor_execute", fail)
    assert counts(store, spec) == 0
    assert store.get_state(initial.extraction_id) == initial
    assert run_extraction(store, initial.extraction_id).document_count == 5


@pytest.mark.parametrize(
    "change",
    [
        {"limit": 4},
        {"questionnaire_id": 1},
        {"reader_version": "v2"},
        {"contract_version": 2},
        {"pipeline_version": 2},
        {"batch_size": 2},
    ],
)
def test_incompatible_resume_is_refused(stored, change):
    store, spec, fixture = stored
    initial = store.create_extraction(spec)
    state = run_extraction(store, initial.extraction_id, max_batches=1)
    with pytest.raises(ExtractionError):
        run_extraction(store, state.extraction_id, expected_spec=replace(spec, **change))
    assert store.get_state(state.extraction_id) == state


def test_concurrent_stale_checkpoint_cannot_skip_documents(stored):
    store, spec, fixture = stored
    state = run_extraction(store, store.create_extraction(spec).extraction_id, max_batches=1)
    reader = GdnReader(
        fixture["engine"],
        corpus_id=spec.corpus_id,
        contribution_id=spec.contribution_id,
        batch_size=1,
    )
    batch = reader.read_batch(after=state.cursor)
    with pytest.raises(ConcurrentProgress):
        store.persist_batch(state.extraction_id, batch, expected_revision=0, expected_spec=spec)
    assert store.get_state(state.extraction_id) == state


def test_runtime_alias_to_source_is_refused_before_any_write(stored):
    store, spec, fixture = stored
    source_url = fixture["engine"].url.set(query={"application_name": "rag005-target-alias"})
    settings = load_settings(
        environ={"RAG_DATABASE_URL": source_url.render_as_string(hide_password=False)}
    )
    wrong_target = create_rag_engine(settings)
    try:
        with pytest.raises(DatabaseSafetyError, match="même base"):
            RagStore(DatabaseGuard(fixture["engine"], wrong_target)).create_extraction(spec)
        with fixture["engine"].connect() as connection:
            assert (
                connection.execute(text("SELECT to_regclass('rag.text_units')")).scalar_one()
                is None
            )
    finally:
        wrong_target.dispose()


def test_empty_filter_finishes_and_checkpoint_remains_valid(stored):
    store, spec, fixture = stored
    spec = replace(spec, contribution_id=fixture["contributions"][2])
    state = run_extraction(store, store.create_extraction(spec).extraction_id)
    assert state.status == "completed"
    assert state.completion_reason == "source_exhausted"
    assert state.document_count == 0
    assert state.cursor is None


def test_two_concurrent_retries_only_commit_once(stored):
    from concurrent.futures import ThreadPoolExecutor

    store, spec, fixture = stored
    state = store.create_extraction(spec)
    reader = GdnReader(
        fixture["engine"],
        corpus_id=spec.corpus_id,
        contribution_id=spec.contribution_id,
        batch_size=1,
    )
    batch = reader.read_batch()

    def persist():
        return store.persist_batch(
            state.extraction_id, batch, expected_revision=0, expected_spec=spec
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = list(executor.map(lambda _: persist(), range(2)))
    assert first == second
    assert first.revision == first.document_count == counts(store, spec) == 1


def test_failure_after_commit_resumes_from_durable_checkpoint(stored, monkeypatch):
    store, spec, fixture = stored
    state = store.create_extraction(spec)
    persist = store.persist_batch

    def committed_then_failed(*args, **kwargs):
        persist(*args, **kwargs)
        raise RuntimeError("Réponse au commit perdue")

    with monkeypatch.context() as patch:
        patch.setattr(store, "persist_batch", committed_then_failed)
        with pytest.raises(RuntimeError, match="commit perdue"):
            run_extraction(store, state.extraction_id)
    assert store.get_state(state.extraction_id).document_count == 1
    resumed = run_extraction(store, state.extraction_id)
    expected = list(
        GdnReader(
            fixture["engine"], corpus_id=spec.corpus_id, contribution_id=spec.contribution_id
        ).iter_documents(limit=5)
    )
    assert [unit.to_json() for unit in store.iter_documents(resumed.extraction_id)] == [
        unit.to_json() for unit in expected
    ]


def test_source_identity_change_refuses_resume(stored, monkeypatch):
    store, spec, fixture = stored
    initial = store.create_extraction(spec)
    identity = store.guard.source_identity()
    with monkeypatch.context() as patch:
        patch.setattr(
            store.guard, "source_identity", lambda: replace(identity, schema_revision="changed")
        )
        with pytest.raises(ExtractionError, match="source a changé"):
            run_extraction(store, initial.extraction_id)
    assert store.get_state(initial.extraction_id) == initial


def test_row_budget_is_durable_and_resume_cannot_increase_it(stored):
    store, spec, fixture = stored
    spec = replace(spec, max_source_rows=1)
    state = run_extraction(store, store.create_extraction(spec).extraction_id)
    assert state.status == "completed"
    assert state.completion_reason == "source_row_limit"
    assert state.source_row_count == 1
    assert state.document_count == 1
    with pytest.raises(ExtractionError):
        run_extraction(store, state.extraction_id, expected_spec=replace(spec, max_source_rows=2))


def test_storage_all_four_bigint_ids_near_signed_limit(stored):
    from cahier_rag.contracts import MAX_BIGINT
    from cahier_rag.sources.gdn import DocumentBatch

    store, spec, fixture = stored
    spec = replace(spec, contribution_id=None, limit=1)
    original = next(
        GdnReader(
            fixture["engine"], corpus_id=spec.corpus_id, contribution_id=fixture["contributions"][0]
        ).iter_documents()
    )
    unit = replace(
        original,
        answer_id=MAX_BIGINT,
        contribution_id=MAX_BIGINT - 1,
        question_id=MAX_BIGINT - 2,
        questionnaire_id=MAX_BIGINT - 3,
    )
    batch = DocumentBatch((unit,), Cursor.after_document(unit), False, 1)
    state = store.create_extraction(spec)
    store.persist_batch(state.extraction_id, batch, expected_revision=0, expected_spec=spec)
    (restored,) = store.iter_documents(state.extraction_id)
    assert restored.to_json() == unit.to_json()


def test_cli_extract_status_and_resume(stored, rag_databases, monkeypatch, capsys):
    import json

    from cahier_rag.__main__ import main

    store, spec, fixture = stored
    monkeypatch.setenv(
        "RAG_SOURCE_DATABASE_URL",
        rag_databases.require_source_url().render_as_string(hide_password=False),
    )
    monkeypatch.setenv(
        "RAG_DATABASE_URL", rag_databases.require_rag_url().render_as_string(hide_password=False)
    )
    assert (
        main(
            [
                "extract",
                "--limit",
                "5",
                "--batch-size",
                "1",
                "--corpus-id",
                spec.corpus_id,
                "--contribution-id",
                str(spec.contribution_id),
                "--max-batches",
                "1",
            ]
        )
        == 0
    )
    messages = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    identity = messages[-1]["extraction_id"]
    assert messages[-1]["status"] == "running"
    assert messages[-1]["document_count"] == 1
    assert main(["status", identity]) == 0
    assert json.loads(capsys.readouterr().out)["document_count"] == 1
    assert main(["resume", identity, "--limit", "6"]) == 2
    assert "incompatibles" in capsys.readouterr().err
    assert main(["resume", identity]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"


def test_migration_rejects_actual_source_even_if_engine_factory_is_misdirected(
    stored, rag_databases, monkeypatch
):
    from cahier_rag import db

    store, spec, fixture = stored
    with monkeypatch.context() as patch:
        patch.setattr(db, "create_rag_engine", lambda settings: fixture["writer"])
        with pytest.raises(DatabaseSafetyError, match="même base"):
            upgrade_schema(rag_databases)
    with fixture["engine"].connect() as connection:
        assert (
            connection.execute(
                text("SELECT to_regclass('public.rag_alembic_version')")
            ).scalar_one()
            is None
        )


def test_sampling_reuses_persisted_units_without_source_modification(stored):
    from cahier_rag.evaluation.sampling import select_sample

    store, spec, fixture = stored
    state = store.create_extraction(spec)
    run_extraction(store, state.extraction_id)
    options = dict(size=3, seed=17, method="random", frame={"version": "synthetic"})
    a = select_sample(store.iter_documents(state.extraction_id), **options)
    b = select_sample(store.iter_documents(state.extraction_id), **options)
    assert a["selected_hash"] == b["selected_hash"]
    assert a["candidate_count"] == 5
    assert len({d["document_id"] for d in a["documents"]}) == 3


def test_explicit_contribution_list_resumes_and_rejects_changed_scope(stored):
    store, spec, fixture = stored
    selected = replace(spec, contribution_id=None, contribution_ids=(fixture["contributions"][0],))
    state = store.create_extraction(selected)
    paused = run_extraction(store, state.extraction_id, max_batches=1)
    assert paused.status == "running"
    with pytest.raises(ExtractionError):
        run_extraction(
            store,
            state.extraction_id,
            expected_spec=replace(selected, contribution_ids=(fixture["contributions"][1],)),
        )
    complete = run_extraction(store, state.extraction_id, expected_spec=selected)
    assert complete.document_count == 5
    assert {d.contribution_id for d in store.iter_documents(state.extraction_id)} == set(
        selected.contribution_ids
    )
