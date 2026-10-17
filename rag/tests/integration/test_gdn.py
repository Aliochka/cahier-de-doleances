"""Requêtes réelles sur le schéma migré, en lecture seule hors préparation des fixtures."""

import pytest
from sqlalchemy import event, text

from cahier_rag.contracts import UnitType
from cahier_rag.db import source_connection
from cahier_rag.sources.gdn import Cursor, GdnReader, SourceDataError

pytestmark = pytest.mark.integration


def reader(fixture, **kwargs):
    return GdnReader(fixture["engine"], contribution_id=fixture["contributions"][0], **kwargs)


def test_joins_texts_provenance_bigints_and_real_readonly(pg_source):
    recorded = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        recorded.append(statement)
        assert connection.connection.driver_connection.readonly is True
        assert statement.lstrip().upper().startswith("SELECT")

    event.listen(pg_source["engine"], "before_cursor_execute", observe)
    try:
        documents = list(reader(pg_source, batch_size=2).iter_documents())
    finally:
        event.remove(pg_source["engine"], "before_cursor_execute", observe)
    assert [item.text for item in documents] == ["Non", "Non", "Autre A", "Autre B", "Autre unique"]
    assert len({item.document_id for item in documents}) == 5
    document = documents[0]
    assert document.answer_id > 2**53
    assert document.contribution_id == pg_source["contributions"][0]
    assert document.questionnaire_id == pg_source["forms"][0]
    assert document.question_text == "Pourquoi ?"
    assert document.question_position == 1
    assert document.question_section == "Section"
    assert document.contribution_title == "Titre A"
    assert document.external_contribution_id.startswith("000:")
    assert document.submitted_at.year == 2019
    assert recorded
    assert pg_source["engine"].pool.checkedout() == 0


def test_pagination_and_resume_inside_same_answer(pg_source):
    extraction = reader(pg_source, batch_size=1)
    complete = list(extraction.iter_documents())
    for cut in range(1, len(complete) + 1):
        prefix = list(extraction.iter_documents(limit=cut))
        suffix = list(extraction.iter_documents(after=Cursor.after_document(prefix[-1])))
        assert [item.to_json() for item in prefix + suffix] == [item.to_json() for item in complete]
    assert list(extraction.iter_documents(limit=0)) == []


def test_batch_cursor_skips_empty_rows_and_can_resume(pg_source):
    extraction = reader(pg_source, batch_size=1)
    batches = list(extraction.iter_batches())
    assert any(not batch.documents for batch in batches)
    first = batches[0]
    rest = list(extraction.iter_documents(after=first.next_cursor))
    all_documents = [document for batch in batches for document in batch.documents]
    assert list(first.documents) + rest == all_documents
    assert batches[-1].exhausted


@pytest.mark.parametrize("kind,count", [(UnitType.OPEN_ANSWER, 2), (UnitType.OTHER_TEXT, 3)])
def test_unit_type_filters(pg_source, kind, count):
    documents = list(reader(pg_source, unit_type=kind).iter_documents())
    assert len(documents) == count
    assert all(document.unit_type == kind for document in documents)


def test_form_filter_and_long_text(pg_source):
    extraction = GdnReader(pg_source["engine"], questionnaire_id=pg_source["forms"][1])
    (document,) = extraction.iter_documents()
    assert document.contribution_id == pg_source["contributions"][1]
    assert document.text == "École\n" * 60_000
    assert document.contribution_title is None


def test_title_without_answers_remains_accessible(pg_source):
    extraction = GdnReader(pg_source["engine"], contribution_id=pg_source["contributions"][2])
    assert list(extraction.iter_documents()) == []
    metadata = extraction.get_contribution(pg_source["contributions"][2])
    assert metadata.title == "Un titre sans réponse"
    assert metadata.to_dict()["contribution_id"] == str(pg_source["contributions"][2])
    assert extraction.get_contribution(pg_source["forms"][0] + 90) is None


def test_inconsistent_question_form_is_not_silently_filtered_out(pg_source):
    with pg_source["writer"].begin() as connection:
        connection.execute(
            text("UPDATE contributions SET form_id=:form WHERE id=:id"),
            {"form": pg_source["forms"][1], "id": pg_source["contributions"][0]},
        )
    extraction = reader(pg_source, questionnaire_id=pg_source["forms"][0])
    with pytest.raises(SourceDataError, match="Rattachement incohérent"):
        list(extraction.iter_documents())
    assert pg_source["engine"].pool.checkedout() == 0


def test_invalid_json_is_reported_and_resources_are_released(pg_source):
    with pg_source["writer"].begin() as connection:
        connection.execute(
            text("UPDATE answers SET value_json='{broken' WHERE id=:id"),
            {"id": pg_source["answers"][2]},
        )
    with pytest.raises(SourceDataError, match="value_json invalide"):
        list(reader(pg_source).iter_documents())
    assert pg_source["engine"].pool.checkedout() == 0


def test_early_stop_holds_no_connection_or_transaction(pg_source):
    iterator = reader(pg_source, batch_size=1).iter_documents()
    assert next(iterator).text == "Non"
    assert pg_source["engine"].pool.checkedout() == 0
    iterator.close()
    assert pg_source["engine"].pool.checkedout() == 0
    with source_connection(pg_source["engine"]) as connection:
        assert connection.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
