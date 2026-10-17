"""Adaptation du JSON normalisé, curseurs et fermeture avant remise des lots."""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from cahier_rag.contracts import MAX_BIGINT, UnitType
from cahier_rag.sources import gdn
from cahier_rag.sources.gdn import Cursor, GdnReader, SourceDataError, row_to_documents


def row(**changes):
    base = dict(
        answer_id=MAX_BIGINT,
        contribution_id=MAX_BIGINT - 1,
        question_id=MAX_BIGINT - 2,
        questionnaire_id=MAX_BIGINT - 3,
        question_form_id=MAX_BIGINT - 3,
        contribution_form_id=MAX_BIGINT - 3,
        answer_text="  Non\n",
        value_json=None,
        answer_position=1,
        question_text="Pourquoi ?",
        questionnaire_name="Enquête",
        contribution_title="Un titre distinct",
        question_position=2,
        question_section="Section",
        question_type="text",
        question_code="Q2",
        questionnaire_version="2019",
        questionnaire_source="official:form",
        contribution_source="gdn:source",
        external_contribution_id="0001:external",
        submitted_at=None,
    )
    return base | changes


@pytest.mark.parametrize("value", [None, "", "\n\t ", "\u2003"])
def test_unfilled_open_answers_emit_nothing(value):
    assert row_to_documents(row(answer_text=value), "gdn") == ()


def test_open_answer_preserves_text_and_separate_context():
    (document,) = row_to_documents(row(), "gdn")
    assert document.text == "  Non\n"
    assert document.contribution_title == "Un titre distinct"
    assert document.question_text == "Pourquoi ?"
    assert document.questionnaire_name == "Enquête"
    assert document.external_contribution_id == "0001:external"
    assert document.question_id == MAX_BIGINT - 2


@pytest.mark.parametrize("raw", [None, "{}", '{"labels":["Bus"]}', '{"other_text":[]}'])
def test_choice_labels_are_never_used_as_text(raw):
    assert (
        row_to_documents(
            row(question_type="single_choice", answer_text="Bus\nVélo", value_json=raw), "gdn"
        )
        == ()
    )


def test_other_elements_preserve_indices_duplicates_and_text():
    values = ["", " \t", "Taxi|Train\nÉcole", "Taxi|Train\nÉcole"]
    documents = row_to_documents(
        row(
            question_type="multi_choice",
            value_json=json.dumps({"labels": ["Bus"], "other_text": values}),
            answer_text="Bus\nTaxi|Train\nÉcole",
        ),
        "gdn",
    )
    assert [item.unit_index for item in documents] == [2, 3]
    assert [item.text for item in documents] == values[2:]
    assert documents[0].document_id != documents[1].document_id
    assert all(item.unit_type == UnitType.OTHER_TEXT for item in documents)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "{bad-private-text",
        "null",
        "[]",
        '{"other_text":null}',
        '{"other_text":"Taxi"}',
        '{"other_text":[42]}',
    ],
)
def test_invalid_choice_metadata_fails_without_fallback_or_text_disclosure(raw):
    with pytest.raises(SourceDataError) as error:
        row_to_documents(row(question_type="multi_choice", value_json=raw), "gdn")
    assert str(MAX_BIGINT) in str(error.value)
    assert "private-text" not in str(error.value)
    assert "Taxi" not in str(error.value)


@pytest.mark.parametrize(
    "changes",
    [{"contribution_form_id": 1}, {"contribution_id": None}, {"questionnaire_id": None}],
)
def test_incoherent_joins_fail_explicitly(changes):
    with pytest.raises(SourceDataError, match="Rattachement incohérent"):
        row_to_documents(row(**changes), "gdn")


def test_cursor_json_roundtrip_preserves_bigint_and_zero_index():
    cursor = Cursor(MAX_BIGINT, 0)
    assert Cursor.from_dict(json.loads(json.dumps(cursor.to_dict()))) == cursor
    assert Cursor(MAX_BIGINT).to_dict()["unit_index"] is None
    for value in (
        {"answer_id": float(MAX_BIGINT), "unit_index": 0},
        {"answer_id": "2.0", "unit_index": 0},
    ):
        with pytest.raises(ValueError):
            Cursor.from_dict(value)


def mock_query(monkeypatch, rows):
    connection = MagicMock()
    result = connection.execute.return_value.__enter__.return_value
    result.mappings.return_value.all.return_value = rows
    opened = []

    @contextmanager
    def fake_source(engine):
        opened.append(True)
        try:
            yield connection
        finally:
            opened.pop()

    monkeypatch.setattr(gdn, "source_connection", fake_source)
    return connection, result, opened


def test_sql_filters_are_bound_and_everything_is_closed_before_yield(monkeypatch):
    connection, result, opened = mock_query(monkeypatch, [row()])
    reader = GdnReader(
        MagicMock(),
        batch_size=7,
        questionnaire_id=9,
        contribution_id=10,
        unit_type=UnitType.OPEN_ANSWER,
    )
    documents = reader.iter_documents(after=Cursor(11))
    assert next(documents).text == "  Non\n"
    assert opened == []
    connection.execute.return_value.__exit__.assert_called_once()
    query, params = connection.execute.call_args.args
    sql = str(query)
    assert "OFFSET" not in sql
    assert "ORDER BY a.id ASC LIMIT :batch_size" in sql
    assert "a.id > :after_id" in sql
    assert "q.form_id = :questionnaire_id" in sql
    assert "a.contribution_id = :contribution_id" in sql
    assert params == {"batch_size": 7, "questionnaire_id": 9, "contribution_id": 10, "after_id": 11}
    documents.close()


def test_exception_closes_result_and_transaction(monkeypatch):
    connection, result, opened = mock_query(monkeypatch, [])
    result.mappings.side_effect = RuntimeError("synthetic error")
    with pytest.raises(RuntimeError):
        GdnReader(MagicMock()).read_batch()
    assert opened == []
    connection.execute.return_value.__exit__.assert_called_once()


def test_replay_inside_other_list_uses_greater_or_equal_and_original_indices(monkeypatch):
    connection, _, _ = mock_query(
        monkeypatch,
        [row(question_type="multi_choice", value_json='{"other_text":["A","","B","C"]}')],
    )
    reader = GdnReader(MagicMock(), batch_size=1)
    first = reader.read_batch(max_documents=1)
    assert first.documents[0].text == "A"
    assert first.next_cursor == Cursor(MAX_BIGINT, 0)
    second = reader.read_batch(after=first.next_cursor, max_documents=1)
    assert second.documents[0].text == "B"
    assert second.next_cursor == Cursor(MAX_BIGINT, 2)
    assert "a.id >= :after_id" in str(connection.execute.call_args.args[0])
    last = reader.read_batch(after=Cursor(MAX_BIGINT, 3))
    assert not last.documents
    assert last.next_cursor == Cursor(MAX_BIGINT)


def test_empty_rows_still_advance_and_zero_limit_opens_nothing(monkeypatch):
    connection, _, _ = mock_query(monkeypatch, [row(answer_text=" ")])
    reader = GdnReader(MagicMock())
    batch = reader.read_batch()
    assert batch.documents == ()
    assert batch.next_cursor == Cursor(MAX_BIGINT)
    assert batch.exhausted
    connection.reset_mock()
    assert list(reader.iter_documents(limit=0)) == []
    connection.execute.assert_not_called()
