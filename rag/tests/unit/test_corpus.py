"""Adaptations limitées nécessaires au cadre réparti RAG-007."""

from unittest.mock import MagicMock

import pytest

from cahier_rag.contracts import MAX_BIGINT
from cahier_rag.evaluation.sampling import describe, select_described_sample
from cahier_rag.extraction import ExtractionError, ExtractionSpec
from cahier_rag.sources.gdn import GdnReader
from tests.unit.test_evaluation import sample, unit
from tests.unit.test_gdn import mock_query, row


def test_legacy_spec_preserves_serialization_and_hash():
    old = ExtractionSpec(limit=10).to_dict()
    assert "contribution_ids" not in old
    assert ExtractionSpec.from_dict(old).to_dict() == old
    new = ExtractionSpec(limit=10, contribution_ids=(1, MAX_BIGINT))
    assert new.to_dict()["contribution_ids"] == ["1", str(MAX_BIGINT)]
    assert ExtractionSpec.from_dict(new.to_dict()) == new
    assert new.fingerprint != ExtractionSpec(limit=10).fingerprint


@pytest.mark.parametrize("ids", [(), (2, 1), (1, 1), (0,), (True,), tuple(range(1, 502)), [1]])
def test_explicit_scope_is_bounded_and_unambiguous(ids):
    with pytest.raises((ValueError, ExtractionError)):
        ExtractionSpec(limit=1, contribution_ids=ids)


def test_individual_and_list_filters_cannot_be_mixed():
    with pytest.raises(ExtractionError):
        ExtractionSpec(limit=1, contribution_id=1, contribution_ids=(1,))


def test_reader_list_filter_uses_bound_parameters(monkeypatch):
    connection, _, _ = mock_query(monkeypatch, [row()])
    reader = GdnReader(MagicMock(), contribution_ids=(1, MAX_BIGINT))
    reader.read_batch()
    query, parameters = connection.execute.call_args.args
    assert "contribution_ids" in str(query)
    assert parameters["contribution_ids"] == (1, MAX_BIGINT)


def test_repeated_selections_can_use_summaries_without_retaining_texts():
    docs = [unit(i) for i in range(30)]
    expected = sample(docs)
    descriptions = [describe(doc) for doc in docs]
    actual = select_described_sample(
        descriptions, size=10, seed=42, method="random", frame={"version": "test"}
    )
    assert actual["selected_hash"] == expected["selected_hash"]
    assert all("strata" not in doc for doc in descriptions)


def test_operational_union_is_exact_and_keeps_shared_partitions():
    import runpy
    from pathlib import Path

    from cahier_rag.contracts import UnitType

    operation = runpy.run_path(str(Path(__file__).parents[2] / "scripts/constitute_corpus.py"))
    rows = []
    for i in range(24000):
        changes = dict(contribution_id=i // 2 + 1, questionnaire_id=(4, 5, 7, 10)[i % 4])
        if i < 200:
            changes["text"] = "Long synthétique " * 150 + str(i)
        elif i < 400:
            changes["unit_type"] = UnitType.OTHER_TEXT
        elif i < 700:
            changes["text"] = "Doublon " + str(i % 100)
        rows.append(describe(unit(i, **changes)))
    random_sample, stratified, final = operation["selections"](rows, {"version": "synthetic"})
    assert len(final["documents"]) == 20000
    assert not stratified["shortfalls"]
    index = {d["document_id"]: d["split"] for d in final["documents"]}
    assert len(index) == 20000
    assert all(
        index[d["document_id"]] == d["split"]
        for sample in (random_sample, stratified)
        for d in sample["documents"]
    )
