"""RRF pondérée : calcul exact, compatibilité historique, filtres et provenance."""

import json
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction

import pytest

from cahier_rag.contracts import MAX_BIGINT
from cahier_rag.search.hybrid.core import fuse as historical_fuse
from cahier_rag.search.hybrid.multi.core import (
    CONFIGURATIONS,
    MultiHybridEngine,
    configuration,
    fuse,
)
from tests.unit.test_hybrid import FakeEngine, result
from tests.unit.test_hybrid import corpus as hybrid_corpus  # noqa: F401


@pytest.fixture
def corpus(request):
    return request.getfixturevalue("hybrid_corpus")


def test_fixed_profiles_and_rrf_three_sources(corpus):
    docs, _ = corpus
    assert configuration()["k"] == 60 and configuration()["depth"] == 50
    assert sum(Fraction(w) for m, w in CONFIGURATIONS["H5"] if m != "vector") == Fraction(1, 2)
    assert dict(CONFIGURATIONS["H5"])["vector"] == "1/2"
    sources = {
        "lexical": [result(docs[0], 99), result(docs[1], 50)],
        "bm25-A": [result(docs[1], 10), result(docs[2], 5)],
        "vector": [result(docs[0], 0.9)],
    }
    rankings, traces = fuse(sources, dict(CONFIGURATIONS["H4"]))
    assert rankings[0].document == docs[0]
    assert rankings[0].score == float(Fraction(2, 61))
    balanced, trace = fuse(sources, dict(CONFIGURATIONS["H5"]))
    assert balanced[0].score == float(Fraction(3, 4 * 61))
    assert trace[docs[0].document_id]["vector"]["rrf_fraction"] == str(Fraction(1, 2 * 61))
    assert traces[docs[0].document_id]["lexical"]["score"] == 99
    assert str(MAX_BIGINT) in json.dumps(rankings[0].to_dict())


def test_h1_exactly_preserves_historical_results(corpus):
    docs, _ = corpus
    sources = {
        "lexical": [result(docs[0]), result(docs[0]), result(docs[1])],
        "vector": [result(docs[2]), result(docs[0])],
    }
    actual, _ = fuse(sources, dict(CONFIGURATIONS["H1"]))
    expected, _ = historical_fuse(sources)
    assert actual == expected
    assert fuse(dict(reversed(list(sources.items()))), dict(CONFIGURATIONS["H1"]))[0] == actual


def test_empty_duplicates_ties_and_distinct_citizens(corpus):
    docs, _ = corpus
    found, _ = fuse(
        {"a": [result(docs[0]), result(docs[0])], "b": [result(docs[1])], "c": []},
        {"a": 1, "b": 1, "c": 1},
    )
    assert len(found) == 2
    assert [r.document.document_id for r in found] == sorted(d.document_id for d in docs[:2])
    assert docs[0].text == docs[1].text and docs[0].contribution_id != docs[1].contribution_id
    assert fuse({"a": [], "b": []}, {"a": 1, "b": 1}) == ((), {})


@pytest.mark.parametrize(
    "weights", [{}, {"a": 0}, {"a": -1}, {"a": "nan"}, {"a": "inf"}, {"a": "1/0"}, {"b": 1}]
)
def test_bad_weights_refused(corpus, weights):
    docs, _ = corpus
    with pytest.raises(ValueError):
        fuse({"a": [result(docs[0])]}, weights)


def test_conflicts_and_invalid_scores(corpus):
    docs, _ = corpus
    with pytest.raises(ValueError, match="Contenu"):
        fuse(
            {"a": [result(docs[0])], "b": [result(replace(docs[0], text="modifié"))]},
            {"a": 1, "b": 1},
        )
    with pytest.raises(ValueError):
        fuse({"a": [result(docs[0], float("nan"))]}, {"a": 1})


def test_sources_called_once_filters_and_partition(corpus):
    docs, scope = corpus
    engines = {m: FakeEngine(scope, docs) for m in ("lexical", "vector", "bm25-A", "bm25-B")}
    engine = MultiHybridEngine({m: e.search for m, e in engines.items()}, scope)
    retrieved = engine.retrieve(
        "Question", split="development", questionnaire_id=4, unit_type="open_answer", limit=100
    )
    assert all(len(e.calls) == 1 for e in engines.values())
    assert all(e.calls[0][1]["limit"] == 50 for e in engines.values())
    assert all(
        r.document.questionnaire_id == 4 and r.document.unit_type.value == "open_answer"
        for results in retrieved.hybrids.values()
        for r in results
    )
    assert all(
        scope.documents[r.document.document_id]["split"] == "development"
        for results in retrieved.hybrids.values()
        for r in results
    )
    assert set(retrieved.measurements["fusion_ms"]) == set(CONFIGURATIONS)
    assert all(
        retrieved.measurements["attributable_sequential_ms"][p]
        >= retrieved.measurements["fusion_ms"][p]
        for p in CONFIGURATIONS
    )


def test_leaking_source_and_bad_limits_refused(corpus):
    docs, scope = corpus
    sources = {
        m: lambda query, **kw: [result(docs[-1])] for m in ("lexical", "vector", "bm25-A", "bm25-B")
    }
    engine = MultiHybridEngine(sources, scope)
    with pytest.raises(ValueError, match="partition"):
        engine.retrieve("Question")
    for bad in (0, 101, True):
        with pytest.raises(ValueError):
            engine.retrieve("Question", limit=bad)
    with pytest.raises(ValueError):
        engine.retrieve("Question", split="unknown")


def test_imports_without_models_or_backend():
    code = "import sys; import cahier_rag.search.hybrid.multi.core; assert not any(n in sys.modules for n in ('torch','transformers','fastapi','app'))"
    subprocess.run([sys.executable, "-c", code], check=True)
