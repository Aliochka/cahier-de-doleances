"""Fusion réelle sur PostgreSQL de test et BM25 SQLite synthétique."""

import pytest

from cahier_rag.embeddings.core import EmbeddingEngine
from cahier_rag.representations.repository import RepresentationRepository
from cahier_rag.search.bm25.index import BM25Index, Config
from cahier_rag.search.bm25.tokenizer import FrenchTokenizer
from cahier_rag.search.flexible import FlexibleEngine, Method
from cahier_rag.search.hybrid.multi.core import MultiHybridEngine
from cahier_rag.vector.engine import VectorEngine
from tests.integration.test_lexical import lexical  # noqa: F401
from tests.integration.test_storage import rag_databases, stored  # noqa: F401
from tests.integration.test_vector import Backend, vector, vector_fixture  # noqa: F401

pytestmark = pytest.mark.integration


def test_postgresql_bm25_multisource_filters_and_provenance(request, tmp_path):
    store, groups, docs, _ = request.getfixturevalue("vector_fixture")
    store.commit(0, groups, [vector() for group in groups for _ in group])
    store.finish()
    lex = FlexibleEngine(store.guard, store.scope)
    vec = VectorEngine(store, EmbeddingEngine(Backend())).load()
    tokenizer = FrenchTokenizer(store.guard.target)
    repo = RepresentationRepository(store.guard.target, store.scope)
    indexes = {}
    try:
        for variant in ("A", "B"):
            index = BM25Index(
                tmp_path / (variant + ".sqlite3"),
                store.scope,
                tokenizer,
                Config(variant),
                writable=True,
            )
            indexes["bm25-" + variant] = index
            index.build(repo)
            index.verify()

        def lexical_search(query, **filters):
            return lex.search(query, method=Method.WEIGHTED, **filters)

        engine = MultiHybridEngine(
            {
                "lexical": lexical_search,
                "vector": vec.search,
                **{m: v.search for m, v in indexes.items()},
            },
            store.scope,
        )
        result = engine.retrieve("taxe carbone", limit=100)
        repeated = engine.retrieve("taxe carbone", limit=100)
        assert result.hybrids == repeated.hybrids and result.traces == repeated.traces
        for found in result.hybrids.values():
            assert len(found) == len({r.document.document_id for r in found})
            assert all(
                r.document.to_dict() == docs[r.document.document_id].to_dict() for r in found
            )
        filtered = engine.retrieve("école", questionnaire_id=10, unit_type="other_text", limit=50)
        assert all(
            len(results) == 1 and results[0].document.unit_type.value == "other_text"
            for results in filtered.hybrids.values()
        )
        assert all(
            int(r.to_dict()["document"]["answer_id"]) > 2**53
            for values in result.hybrids.values()
            for r in values
        )
    finally:
        vec.close()
        for index in indexes.values():
            index.close()
