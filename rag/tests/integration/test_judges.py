"""Plans de jugements : lecture seule de documents synthétiques stockés en RAG."""

import pytest
from sqlalchemy import event

from cahier_rag.judges.planning import iter_inputs, prepare
from tests.integration.test_representations import prepared_data  # noqa: F401
from tests.integration.test_storage import rag_databases, stored  # noqa: F401

pytestmark = pytest.mark.integration


def test_blind_plan_reads_rag_without_writes(request, tmp_path):
    repository, documents = request.getfixturevalue("prepared_data")
    queries = [{"query_id": "dev-1", "text": "Une question synthétique", "split": "development"}]
    selected = documents[:2]
    observed = []

    def inspect_readonly(connection, cursor, statement, params, context, many):
        if statement.startswith("SELECT rag.text_units"):
            with connection.connection.cursor() as probe:
                probe.execute("SHOW transaction_read_only")
                observed.append(probe.fetchone()[0])

    event.listen(repository.engine, "before_cursor_execute", inspect_readonly)
    try:
        plan = tmp_path / "plan"
        manifest = prepare(
            plan,
            [("dev-1", d.document_id) for d in selected],
            repository,
            queries,
            kind="human60",
            source_hashes={"synthetic": True},
        )
        inputs = list(iter_inputs(plan, manifest))
        assert {i.document_id for i in inputs} == {d.document_id for d in selected}
        by_id = {d.document_id: d for d in selected}
        for item in inputs:
            assert item.answer == by_id[item.document_id].text
            assert item.question == by_id[item.document_id].question_text
            assert item.source_hash == by_id[item.document_id].content_hash
            assert set(item.messages()[1]) == {"role", "content"}
        assert observed and set(observed) == {"on"}
        assert repository.engine.pool.checkedout() == 0
        with pytest.raises(ValueError, match="hors développement"):
            prepare(
                tmp_path / "forbidden",
                [("dev-1", documents[2].document_id)],
                repository,
                queries,
                kind="human60",
                source_hashes={},
            )
    finally:
        event.remove(repository.engine, "before_cursor_execute", inspect_readonly)
