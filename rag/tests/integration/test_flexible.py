"""RAG-009 : français, phrases obligatoires, pondération, filtres et historique."""

import pytest

from cahier_rag.search.flexible import FlexibleEngine, Method
from cahier_rag.search.lexical import Strategy
from tests.integration.test_lexical import lexical  # noqa: F401
from tests.integration.test_storage import rag_databases, stored  # noqa: F401

pytestmark = pytest.mark.integration


def enhanced(request):
    original, docs, sample = request.getfixturevalue("lexical")
    return FlexibleEngine(original.guard, original.scope), original, docs


@pytest.mark.parametrize("method", [Method.PARTIAL, Method.WEIGHTED])
def test_natural_language_partial_short_and_other(request, method):
    engine, original, docs = enhanced(request)
    assert not original.search("Quelles contributions parlent de taxe carbone et de zirconium ?")
    result = engine.search(
        "Quelles contributions parlent de taxe carbone et de zirconium ?", method=method
    )
    assert {d.document.document_id for d in result} == {
        d.document_id for d in (docs[0], docs[1], docs[4])
    }
    assert engine.search("TVA", method=method)[0].document.to_json() == docs[2].to_json()
    assert (
        engine.search("Quelles réponses évoquent l’école ?", method=method)[0].document.document_id
        == docs[3].document_id
    )
    assert engine.search("éducation", method=method, unit_type="other_text")
    assert not engine.search("éducation", method=method, unit_type="open_answer")


@pytest.mark.parametrize("method", [Method.PARTIAL, Method.WEIGHTED])
def test_expressions_remain_mandatory_and_rankings_stable(request, method):
    engine, original, docs = enhanced(request)
    result = engine.search('Quelles contributions mentionnent "taxe carbone" ?', method=method)
    assert {r.document.document_id for r in result} == {d.document_id for d in docs[:2]}
    assert [r.document.document_id for r in result] == sorted(d.document_id for d in docs[:2])
    assert [r.to_dict() for r in result] == [
        r.to_dict()
        for r in engine.search('Quelles contributions mentionnent "taxe carbone" ?', method=method)
    ]
    assert not engine.search('"taxe carbone" -carbone', method=method)


def test_weighted_values_reward_coverage_and_do_not_cross_scope(request):
    engine, original, docs = enhanced(request)
    results = engine.search("TVA taxe carbone", method=Method.WEIGHTED)
    assert results[0].document.document_id in {d.document_id for d in (docs[0], docs[1], docs[4])}
    assert results[-1].document.document_id == docs[2].document_id
    assert not engine.search("Motextérieur")
    assert not engine.search("carbone", split="evaluation")
    assert not engine.search("carbone", questionnaire_id=10)
    assert len(engine.search("carbone", limit=1)) == 1
    assert (
        engine.search("patrimoine", strategy=Strategy.TITLE)[0].document.document_id
        == docs[5].document_id
    )
    assert not engine.search("patrimoine", strategy=Strategy.ANSWER)


def test_empty_stopwords_and_quoted_stopwords(request):
    engine, _, _ = enhanced(request)
    for query in ("", "Quelles contributions réponses ?", "le la et", '"le la" taxe', "-carbone"):
        assert engine.search(query) == []
    with pytest.raises(ValueError):
        engine.search(" ".join("terme" + str(i) for i in range(40)))


def test_strict_delegation_is_byte_identical_to_rag008(request):
    engine, original, _ = enhanced(request)
    for query in ("taxe carbone", '"taxe carbone"', "TVA", "l'école"):
        assert [r.to_dict() for r in engine.search(query, method=Method.STRICT)] == [
            r.to_dict() for r in original.search(query)
        ]


def test_precise_queries_preserve_original_order_and_bigints(request):
    engine, original, _ = enhanced(request)
    for query in ("TVA", '"taxe carbone"', "l'école"):
        baseline = [r.document.document_id for r in original.search(query)]
        for method in (Method.PARTIAL, Method.WEIGHTED):
            results = engine.search(query, method=method)
            assert [r.document.document_id for r in results] == baseline
            assert all(isinstance(r.to_dict()["document"]["answer_id"], str) for r in results)
