"""RAG-026 sur bases _test uniquement ; jamais sur corpus réel."""

import os

import pytest
from sqlalchemy import text

from cahier_rag.config import load_settings
from cahier_rag.db import create_rag_engine
from cahier_rag.fullcorpus.store import FullStore, vector_hash
from cahier_rag.migrate import upgrade_schema
from cahier_rag.safety import DatabaseGuard
from cahier_rag.sources.gdn import GdnReader

pytestmark = pytest.mark.integration


@pytest.fixture
def full_store(pg_source):
    raw = os.getenv("RAG_STORAGE_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("RAG_STORAGE_TEST_DATABASE_URL requise")
    settings = load_settings(
        environ={"RAG_SOURCE_DATABASE_URL": str(pg_source["engine"].url), "RAG_DATABASE_URL": raw}
    )
    if not settings.require_rag_url().database.endswith("_test"):
        pytest.fail("Base _test obligatoire")
    upgrade_schema(settings)
    target = create_rag_engine(settings)
    guard = DatabaseGuard(pg_source["engine"], target)
    store = FullStore(guard, "pilot100k")
    manifest = {"audit_source": guard.source_identity().to_dict(), "test": True}
    try:
        store.initialize(manifest, 5)
        yield store
    finally:
        with guard.transaction() as (c, _):
            c.execute(text("DELETE FROM rag_tuning.term_statistics WHERE space_id='pilot100k'"))
            c.execute(text("DELETE FROM rag_tuning.statistics WHERE space_id='pilot100k'"))
            c.execute(text("DELETE FROM rag_full.segments WHERE space_id='pilot100k'"))
            c.execute(text("DELETE FROM rag_full.documents WHERE space_id='pilot100k'"))
            c.execute(text("DELETE FROM rag_full.spaces WHERE space_id='pilot100k'"))
        target.dispose()


def test_atomic_resume_and_integrity(full_store, pg_source):
    store = full_store
    reader = GdnReader(
        pg_source["engine"], contribution_id=pg_source["contributions"][0], batch_size=2
    )
    before = store.state()
    first = reader.read_batch(max_documents=2)
    store.commit_documents(first, before)
    with pytest.raises(ValueError, match="concurrente"):
        store.commit_documents(first, before)
    with pytest.raises(ValueError, match="incompatible"):
        store.initialize({"audit_source": before["manifest"]["audit_source"], "test": False}, 5)
    while store.state()["documents"] < 5:
        state = store.state()
        batch = reader.read_batch(after=store.cursor(state), max_documents=5 - state["documents"])
        store.commit_documents(batch, state)
    store.finish_extraction()
    actual = store.documents()
    expected = list(reader.iter_documents(limit=5))
    assert [d.to_json() for _, d in actual] == [d.to_json() for d in expected]
    vector = [1.0, -0.0, 0.0012148848618380725] + [0.0] * 1021
    from cahier_rag.fullcorpus.pipeline import prepare_metadata

    rows = []
    for _, d in actual:
        p = prepare_metadata(d, store.state()["recipe_hash"], 0, len(d.text), 0, 3)
        rows.append(
            {
                k: p[k]
                for k in (
                    "document_id",
                    "segment_index",
                    "representation_id",
                    "start",
                    "end",
                    "tokens",
                    "content_hash",
                )
            }
            | dict(vector_hash=vector_hash(vector), embedding=vector)
        )
    state = store.state()
    # Duplicate segment fails after attempted writes; documents/checkpoint unchanged.
    with pytest.raises(Exception):
        store.commit_vectors(state, 5, rows + [rows[0]])
    assert store.state()["vector_cursor"] == 0
    store.commit_vectors(state, 5, rows)
    assert store.verify()["documents"] == 5
    assert store.state()["verified"]
    assert [d.answer_id for _, d in actual] == [d.answer_id for d in expected]

    from cahier_rag.fullcorpus.search import FullSearch

    search = FullSearch(store)
    lexical = search.lexical("Non", limit=5)
    assert lexical and all(
        r.document.contribution_id == expected[0].contribution_id for r in lexical
    )
    exact = search.vector(vector, limit=5)
    ann = search.vector(vector, limit=5, ann=True)
    assert len(exact) == len(ann) == 5
    assert [r.document.document_id for r in exact] == sorted(d.document_id for d in expected)
    assert {r.document.document_id for r in exact} == {r.document.document_id for r in ann}
    assert not search.vector(vector, questionnaire_id=1)
    hybrid, traces, measures = search.hybrid("Non", vector, depth=5)
    assert hybrid and traces and measures["total_seconds"] >= 0
