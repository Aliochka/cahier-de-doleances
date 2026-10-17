"""Recherche française réelle sur PostgreSQL, corpus synthétique strictement limité."""

import pytest

from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType
from cahier_rag.evaluation.files import load_judgments, write_json
from cahier_rag.evaluation.sampling import describe, digest
from cahier_rag.schema import lexical_corpora, lexical_vectors, units
from cahier_rag.search.evaluation import run_queries
from cahier_rag.search.lexical import CorpusScope, LexicalEngine, Strategy
from cahier_rag.storage import document_record
from tests.integration.test_storage import rag_databases, stored  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture
def lexical(request):
    store, spec, fixture = request.getfixturevalue("stored")
    texts = [
        "taxe carbone",
        "taxe carbone",
        "TVA",
        "L’école publique et l’éducation",
        "carbone taxe",
        "infrastructures hospitalières",
        "Motextérieur taxe carbone",
    ]
    docs = [
        TextUnit(
            corpus_id=spec.corpus_id,
            unit_type=UnitType.OTHER_TEXT if i == 3 else UnitType.OPEN_ANSWER,
            answer_id=MAX_BIGINT - i,
            contribution_id=MAX_BIGINT - i - 100,
            question_id=MAX_BIGINT - 200,
            questionnaire_id=10 if i == 3 else 4,
            text=value,
            question_text="Faut-il rétablir l’impôt sur la fortune ?"
            if i == 2
            else "Quelle solution ?",
            questionnaire_name="Synthétique",
            answer_position=0,
            question_type="multi_choice" if i == 3 else "text",
            contribution_title="Patrimoine" if i == 5 else None,
            external_contribution_id="000:external",
        )
        for i, value in enumerate(texts)
    ]
    selected = [
        describe(d) | {"split": "evaluation" if i == 5 else "development"}
        for i, d in enumerate(docs[:6])
    ]
    sample = {"documents": selected, "selected_hash": digest(selected)}
    scope = CorpusScope(sample, expected_hash=sample["selected_hash"], expected_size=6)
    engine = LexicalEngine(store.guard, scope)
    with store.guard.transaction() as (conn, source):
        conn.execute(units.insert(), [document_record(d) for d in docs])
    engine.rebuild()
    try:
        yield engine, docs, sample
    finally:
        with store.guard.transaction() as (conn, source):
            conn.execute(
                lexical_corpora.delete().where(lexical_corpora.c.sample_hash == scope.sample_hash)
            )


def ids(results):
    return [r.document.document_id for r in results]


def test_matching_order_ties_provenance_and_bigints(lexical):
    engine, docs, _ = lexical
    matches = engine.search("taxe carbone")
    assert set(ids(matches)) == {d.document_id for d in (docs[0], docs[1], docs[4])}
    assert matches[0].score == matches[1].score
    assert ids(matches) == sorted([docs[0].document_id, docs[1].document_id, docs[4].document_id])
    assert matches[0].document.to_json() in {d.to_json() for d in docs}
    assert int(matches[0].to_dict()["document"]["contribution_id"]) > 2**53
    assert matches[0].document.external_contribution_id == "000:external"
    assert ids(engine.search("taxe carbone")) == ids(matches)


def test_expressions_accents_apostrophes_and_other(lexical):
    engine, docs, _ = lexical
    assert set(ids(engine.search('"taxe carbone"'))) == {d.document_id for d in docs[:2]}
    assert ids(engine.search("école")) == [docs[3].document_id]
    assert ids(engine.search("l'école")) == [docs[3].document_id]
    assert ids(engine.search("éducation", unit_type=UnitType.OTHER_TEXT)) == [docs[3].document_id]
    assert not engine.search("éducation", unit_type=UnitType.OPEN_ANSWER)


def test_short_answers_context_and_title(lexical):
    engine, docs, _ = lexical
    assert ids(engine.search("TVA")) == [docs[2].document_id]
    assert not engine.search("fortune", strategy=Strategy.ANSWER)
    assert ids(engine.search("fortune", strategy=Strategy.QUESTION)) == [docs[2].document_id]
    assert not engine.search("patrimoine", strategy=Strategy.QUESTION)
    assert ids(engine.search("patrimoine", strategy=Strategy.TITLE)) == [docs[5].document_id]


def test_filters_limit_and_scope_exclusion(lexical):
    engine, docs, _ = lexical
    assert not engine.search("Motextérieur")
    assert not engine.search("carbone", questionnaire_id=10)
    assert not engine.search("carbone", split="evaluation")
    assert len(engine.search("carbone", limit=1)) == 1
    assert engine.validate()["documents"] == 6


def test_rebuild_is_reproducible_and_rollback_preserves_old_index(lexical):
    engine, docs, _ = lexical
    before = [r.to_dict() for r in engine.search("carbone")]
    engine.rebuild()
    assert [r.to_dict() for r in engine.search("carbone")] == before
    with engine.guard.transaction() as (conn, source):
        conn.execute(
            units.update()
            .where(units.c.document_id == docs[0].document_id)
            .values(text="Altération synthétique")
        )
    with pytest.raises(ValueError):
        engine.rebuild()
    with engine.guard.transaction() as (conn, source):
        conn.execute(
            units.update()
            .where(units.c.document_id == docs[0].document_id)
            .values(text=docs[0].text)
        )
    assert [r.to_dict() for r in engine.search("carbone")] == before


def test_incomplete_index_is_refused(lexical):
    engine, docs, _ = lexical
    with engine.guard.transaction() as (conn, source):
        conn.execute(
            lexical_vectors.delete().where(
                lexical_vectors.c.sample_hash == engine.scope.sample_hash,
                lexical_vectors.c.document_id == docs[0].document_id,
            )
        )
    with pytest.raises(ValueError):
        engine.search("carbone")


def test_run_exports_are_compatible_without_inventing_judgments(lexical, tmp_path):
    engine, docs, sample = lexical
    queries = [
        dict(query_id="dev", text="carbone", split="development"),
        dict(query_id="eval", text="hospitalières", split="evaluation"),
    ]
    rankings, candidates, report = run_queries(engine, queries, limit=3)
    assert set(rankings) == {"dev"}
    assert report["quality_metrics"] is None
    assert all(r["grade"] is None for r in candidates)
    assert report["timings"][0]["milliseconds"] >= 0
    path = tmp_path / "pending.json"
    write_json(path, candidates)
    with pytest.raises(ValueError):
        load_judgments(path, queries, sample)
    second = run_queries(engine, queries, limit=3)
    assert second[0] == rankings
    assert second[2]["rankings_hash"] == report["rankings_hash"]
    evaluation, _, _ = run_queries(engine, queries, split="evaluation")
    assert evaluation == {"eval": [docs[5].document_id]}


def test_stopwords_and_websearch_input_are_safe(lexical):
    engine, _, _ = lexical
    assert engine.search("le la et") == []
    engine.search('""" )( bizarre \\ query <->')


def test_known_human_judgments_can_score_exported_synthetic_results(lexical):
    from cahier_rag.evaluation.metrics import aggregate

    engine, docs, sample = lexical
    queries = [
        dict(query_id="q", text='"taxe carbone"', split="development", category="expression")
    ]
    ranks, pending, report = run_queries(engine, queries, limit=2)
    judgments = {"q": {d.document_id: 3 for d in docs[:2]}}
    scores = aggregate(queries, ranks, judgments, k=2)
    assert scores["per_query"]["q"]["precision_at_k"] == 1
    assert scores["per_query"]["q"]["recall_at_k"] is None
    assert report["quality_metrics"] is None
    assert all(candidate["grade"] is None for candidate in pending)


@pytest.mark.parametrize("changed", [{"version": 99}, {"server_version": "future-version"}])
def test_changed_index_configuration_requires_rebuild(lexical, changed):
    engine, _, _ = lexical
    from sqlalchemy import select

    with engine.guard.transaction() as (conn, source):
        original = conn.execute(
            select(lexical_corpora.c.configuration).where(
                lexical_corpora.c.sample_hash == engine.scope.sample_hash
            )
        ).scalar_one()
        conn.execute(
            lexical_corpora.update()
            .where(lexical_corpora.c.sample_hash == engine.scope.sample_hash)
            .values(configuration=original | changed)
        )
    with pytest.raises(ValueError):
        engine.search("carbone")
