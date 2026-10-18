"""Préparation depuis PostgreSQL de test ; aucune modification des bases réelles."""

from dataclasses import replace

import pytest
from sqlalchemy import event

from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType
from cahier_rag.evaluation.sampling import describe, digest
from cahier_rag.representations.artifacts import generate, inspect_artifact
from cahier_rag.representations.cli import verify_replay
from cahier_rag.representations.contracts import PreparationConfig, Strategy
from cahier_rag.representations.repository import LIMITS, RepresentationRepository
from cahier_rag.schema import units
from cahier_rag.search.lexical import CorpusScope
from cahier_rag.storage import document_record
from tests.integration.test_storage import rag_databases, stored  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture
def prepared_data(request):
    store, spec, _ = request.getfixturevalue("stored")
    docs = [
        TextUnit(
            corpus_id=spec.corpus_id,
            unit_type=UnitType.OPEN_ANSWER,
            answer_id=MAX_BIGINT - i,
            contribution_id=MAX_BIGINT - 100 - (i == 2),
            question_id=10 + i,
            questionnaire_id=4,
            question_position=i,
            text=text,
            question_text=f"Question {i} ?",
            questionnaire_name="Synthétique",
            answer_position=0,
            question_type="text",
        )
        for i, text in enumerate(
            ("Oui", "Une réponse voisine.\n\n" * 100, "Évaluation indépendante", "Hors des 20 000")
        )
    ]
    selected = [
        describe(d) | {"split": "evaluation" if i == 2 else "development"}
        for i, d in enumerate(docs[:3])
    ]
    sample = {"documents": selected, "selected_hash": digest(selected)}
    scope = CorpusScope(sample, expected_size=3, expected_hash=sample["selected_hash"])
    with store.guard.transaction() as (connection, _):
        connection.execute(units.insert(), [document_record(d) for d in docs])
    return RepresentationRepository(store.guard.target, scope), docs


@pytest.mark.parametrize("strategy", list(Strategy))
def test_real_readonly_batches_artifacts_and_replay(prepared_data, tmp_path, strategy):
    repository, docs = prepared_data
    config = PreparationConfig(strategy, segment_chars=120, overlap_chars=12)
    read_only = []

    def check(connection, cursor, statement, params, context, many):
        if statement.startswith("SELECT rag.text_units"):
            with connection.connection.cursor() as probe:
                probe.execute("SHOW transaction_read_only")
                read_only.append(probe.fetchone()[0])

    event.listen(repository.engine, "before_cursor_execute", check)
    try:
        output = tmp_path / strategy
        ids = [d.document_id for d in docs[:3]]
        manifest = generate(
            repository, config, ids, output, selection={"synthetic": True}, batch_size=1
        )
        assert inspect_artifact(output, scope=repository.scope) == manifest
        assert verify_replay(repository, output, batch_size=3)["reproducible"]
        assert len(read_only) == 4 and set(read_only) == {"on"}
        parent = repository.parent(docs[0].document_id)
        assert {d.document_id for d in parent} == {d.document_id for d in docs[:2]}
        assert docs[3].document_id not in manifest["target_ids"]
        assert repository.engine.pool.checkedout() == 0
        iterator = repository.iter_prepared(ids, config, batch_size=1)
        next(iterator)
        assert repository.engine.pool.checkedout() == 0
        iterator.close()
    finally:
        event.remove(repository.engine, "before_cursor_execute", check)


def test_guard_limits_missing_and_corrupt_document(prepared_data, monkeypatch):
    repository, docs = prepared_data
    with pytest.raises(ValueError):
        repository.fetch([docs[3].document_id])
    monkeypatch.setitem(LIMITS, "max_batch_chars", 1)
    with pytest.raises(ValueError):
        repository.fetch([docs[0].document_id])
    assert repository.engine.pool.checkedout() == 0
    monkeypatch.undo()
    selected = [dict(v) for v in repository.scope.documents.values()]
    selected[0]["content_hash"] = "0" * 64
    scope = CorpusScope(
        {"documents": selected, "selected_hash": digest(selected)},
        expected_size=3,
        expected_hash=digest(selected),
    )
    invalid = RepresentationRepository(repository.engine, scope)
    with pytest.raises(ValueError):
        invalid.fetch([docs[0].document_id])
    assert repository.engine.pool.checkedout() == 0
    monkeypatch.setitem(LIMITS, "max_parent_units", 1)
    with pytest.raises(ValueError):
        repository.parent(docs[0].document_id)


def test_questionnaire_inconsistency_rejected(prepared_data):
    repository, docs = prepared_data
    # Une liste passée directement à la transformation ne peut changer de questionnaire.
    from cahier_rag.representations.prepare import prepare_unit

    with pytest.raises(ValueError):
        list(
            prepare_unit(
                docs[0],
                config=PreparationConfig(Strategy.D),
                sample_hash="s",
                split="development",
                parent=(replace(docs[1], questionnaire_id=5),),
            )
        )
