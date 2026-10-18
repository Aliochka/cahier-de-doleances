"""Deux moteurs PostgreSQL réels, encodeur synthétique et aucun jugement humain."""

import pytest

from cahier_rag.embeddings.core import EmbeddingEngine
from cahier_rag.search.flexible import FlexibleEngine
from cahier_rag.search.hybrid.core import HybridConfig, HybridEngine
from cahier_rag.vector.engine import VectorEngine
from tests.integration.test_lexical import lexical  # noqa: F401
from tests.integration.test_storage import rag_databases, stored  # noqa: F401
from tests.integration.test_vector import Backend, vector, vector_fixture  # noqa: F401

pytestmark = pytest.mark.integration


def test_real_engines_rrf_filters_provenance_and_determinism(request):
    store, groups, docs, _ = request.getfixturevalue("vector_fixture")
    store.commit(0, groups, [vector() for group in groups for _ in group])
    store.finish()
    lexical_engine = FlexibleEngine(store.guard, store.scope)
    vector_engine = VectorEngine(store, EmbeddingEngine(Backend())).load()
    try:
        hybrid = HybridEngine(lexical_engine, vector_engine, store.scope, HybridConfig(depth=6))
        found = hybrid.search("taxe carbone", limit=5)
        assert found and len({r.document.document_id for r in found}) == len(found)
        assert hybrid.search("taxe carbone", limit=5) == found
        assert all(r.document.to_dict() == docs[r.document.document_id].to_dict() for r in found)
        assert all(
            store.scope.documents[r.document.document_id]["split"] == "development" for r in found
        )
        assert all(int(r.to_dict()["document"]["answer_id"]) > 2**53 for r in found)
        other = hybrid.search("école", limit=5, questionnaire_id=10, unit_type="other_text")
        assert len(other) == 1 and other[0].document.unit_type.value == "other_text"
        assert hybrid.last_retrieval.measurements["common"] == 1
        empty_lexical = hybrid.search("zzzzintrouvable", limit=5)
        assert empty_lexical and not hybrid.last_retrieval.lexical
        assert all(
            "vector" in hybrid.last_retrieval.traces[r.document.document_id] for r in empty_lexical
        )
    finally:
        vector_engine.close()
