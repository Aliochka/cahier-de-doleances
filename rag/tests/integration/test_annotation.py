"""Lecture documentaire RAG réelle sur fixtures synthétiques isolées."""

import pytest
from sqlalchemy import event, text

from cahier_rag.annotation.documents import Documents
from tests.integration.test_lexical import lexical  # noqa: F401
from tests.integration.test_storage import rag_databases, stored  # noqa: F401

pytestmark = pytest.mark.integration


def test_document_and_parent_are_readonly_and_faithful(request):
    engine, docs, sample = request.getfixturevalue("lexical")
    doc = docs[0]
    pair = ("q0", doc.document_id)
    reader = Documents(engine.guard.target, {pair: {"content_hash": doc.content_hash}})
    observed = []

    def check_readonly(connection, cursor, statement, params, context, many):
        if statement.startswith("SELECT rag.text_units"):
            with connection.connection.cursor() as probe:
                probe.execute("SHOW transaction_read_only")
                observed.append(probe.fetchone()[0])

    event.listen(engine.guard.target, "before_cursor_execute", check_readonly)
    try:
        assert reader.get(pair) == [doc.to_dict()]
        assert reader.get(pair, parent=True) == [doc.to_dict()]
        assert observed == ["on", "on", "on"]
    finally:
        event.remove(engine.guard.target, "before_cursor_execute", check_readonly)
    assert engine.guard.target.pool.checkedout() == 0
    with engine.guard.target.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
    reader.candidates[pair]["content_hash"] = "bad"
    with pytest.raises(ValueError):
        reader.get(pair)
    assert engine.guard.target.pool.checkedout() == 0
