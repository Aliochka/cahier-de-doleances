"""RAG-027 : équivalence et filtres PostgreSQL sur cinq documents synthétiques."""

import pytest
from sqlalchemy import text

from cahier_rag.fullcorpus.pipeline import prepare_metadata
from cahier_rag.fullcorpus.search import FullSearch
from cahier_rag.fullcorpus.store import vector_hash
from cahier_rag.sources.gdn import GdnReader
from cahier_rag.tuning.lexical import TunedSearch
from cahier_rag.tuning.statistics import build_statistics
from cahier_rag.tuning.vector import AnnConfig, ann_search
from tests.integration.test_fullcorpus import full_store  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture
def tuning_store(request, pg_source):
    store = request.getfixturevalue("full_store")
    reader = GdnReader(
        pg_source["engine"], contribution_id=pg_source["contributions"][0], batch_size=100
    )
    batch = reader.read_batch(max_documents=5)
    store.commit_documents(batch, store.state())
    store.finish_extraction()
    vector = [1.0] + [0.0] * 1023
    rows = []
    for d in batch.documents:
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
            | dict(embedding=vector, vector_hash=vector_hash(vector))
        )
    store.commit_vectors(store.state(), 5, rows)
    store.verify()
    return store


@pytest.mark.parametrize(
    "query", ["Non", "Autre", "Non Autre", '"Autre A"', "Autre -Non", "rien inconnu"]
)
def test_unrolled_equivalence(tuning_store, query):
    store = tuning_store
    reference = FullSearch(store).lexical(query)
    for engine in (TunedSearch(store, statistics=False),):
        actual = engine.lexical(query)
        assert [(r.document.document_id, r.score) for r in actual] == [
            (r.document.document_id, r.score) for r in reference
        ]
    build_statistics(store)
    actual = TunedSearch(store).lexical(query)
    assert [(r.document.document_id, r.score) for r in actual] == [
        (r.document.document_id, r.score) for r in reference
    ]
    filtered = TunedSearch(store).lexical(query, unit_type="other_text")
    assert [(r.document.document_id, r.score) for r in filtered] == [
        (r.document.document_id, r.score)
        for r in FullSearch(store).lexical(query, unit_type="other_text")
    ]


def test_stats_integrity_ann_filters_and_approximation(tuning_store):
    store = tuning_store
    first = build_statistics(store)
    second = build_statistics(store)
    assert first["lexemes"] == second["lexemes"]
    rows, trace = ann_search(store, [1.0] + [0.0] * 1023, AnnConfig(800), limit=5)
    assert len(rows) == 5 and len(trace["winners"]) == 5
    assert all(isinstance(r.document.answer_id, int) and r.document.answer_id > 2**53 for r in rows)
    other, _ = ann_search(store, [1.0] + [0.0] * 1023, limit=5, unit_type="other_text")
    assert all(r.document.unit_type.value == "other_text" for r in other)
    assert TunedSearch(store, prefilter=100).lexical("Non")
    with store.guard.transaction() as (c, _):
        c.execute(
            text(
                "UPDATE rag_tuning.statistics SET corpus_hash='changed' WHERE space_id='pilot100k'"
            )
        )
    with pytest.raises(ValueError, match="incompatibles"):
        TunedSearch(store).lexical("Non")


def test_filtered_exact_uses_all_eligible_units(tuning_store):
    from cahier_rag.tuning.retrieval import search_vector

    rows, trace = search_vector(
        tuning_store, [1.0] + [0.0] * 1023, ann=True, limit=5, unit_type="other_text"
    )
    reference = FullSearch(tuning_store).vector(
        [1.0] + [0.0] * 1023, limit=5, unit_type="other_text"
    )
    assert [(r.document.document_id, r.score) for r in rows] == [
        (r.document.document_id, r.score) for r in reference
    ]
    assert trace["mode"] == "exact-filtered" and trace["ann_requested"]
