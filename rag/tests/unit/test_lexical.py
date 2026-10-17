"""Périmètre lexical vérifiable hors PostgreSQL et paramètres bornés."""

from unittest.mock import MagicMock

import pytest

from cahier_rag.evaluation.sampling import describe, digest
from cahier_rag.search.lexical import CorpusScope, LexicalEngine
from tests.unit.test_evaluation import unit


def scope():
    docs = [describe(unit(i)) | {"split": "development"} for i in range(3)]
    sample = {"documents": docs, "selected_hash": digest(docs)}
    return CorpusScope(sample, expected_hash=sample["selected_hash"], expected_size=3)


def test_default_scope_refuses_anything_other_than_rag007():
    with pytest.raises(ValueError):
        CorpusScope({"documents": [], "selected_hash": "unknown"})


@pytest.mark.parametrize(
    "query,kwargs",
    [
        ("", {}),
        ("x" * 1001, {}),
        ("x", {"limit": 0}),
        ("x", {"limit": 1001}),
        ("x", {"limit": True}),
        ("x", {"split": "all"}),
        ("x", {"questionnaire_id": 1.2}),
        ("x", {"unit_type": "invalid"}),
        ("x", {"strategy": "invalid"}),
    ],
)
def test_parameters_fail_before_opening_any_connection(query, kwargs):
    guard = MagicMock()
    engine = LexicalEngine(guard, scope())
    with pytest.raises(ValueError):
        engine.search(query, **kwargs)
    guard.transaction.assert_not_called()


def test_tampered_scope_is_refused():
    docs = [describe(unit(1)) | {"split": "development"}]
    with pytest.raises(ValueError):
        CorpusScope(
            {"documents": docs, "selected_hash": "wrong"}, expected_hash="wrong", expected_size=1
        )


def test_scope_is_an_immutable_snapshot():
    frozen = scope()
    key = next(iter(frozen.documents))
    with pytest.raises(TypeError):
        frozen.documents[key]["split"] = "evaluation"
    with pytest.raises(TypeError):
        frozen.documents["outside"] = {}


@pytest.mark.parametrize("extra,expected", [([], "development"), (["--split", "all"], None)])
def test_cli_protects_evaluation_partition_by_default(monkeypatch, extra, expected):
    from contextlib import contextmanager

    from cahier_rag.search import cli

    engine = MagicMock()
    engine.search.return_value = []

    @contextmanager
    def opened(settings):
        store = MagicMock()
        yield store

    monkeypatch.setattr(cli, "load_sample", lambda path: {})
    monkeypatch.setattr(cli, "CorpusScope", lambda value: scope())
    monkeypatch.setattr(cli, "load_settings", lambda **kwargs: None)
    monkeypatch.setattr(cli, "open_store", opened)
    monkeypatch.setattr(cli, "LexicalEngine", lambda guard, corpus: engine)
    assert cli.main(["search", "taxe"] + extra) == 0
    assert engine.search.call_args.kwargs["split"] == expected
