"""Comparer les identités PostgreSQL plutôt que leurs URL ou alias."""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from cahier_rag import safety
from cahier_rag.safety import DatabaseGuard, DatabaseIdentity, DatabaseSafetyError, assert_distinct


def test_same_cluster_database_is_rejected_regardless_of_url():
    source = DatabaseIdentity("cluster", 123, "source")
    with pytest.raises(DatabaseSafetyError, match="même base"):
        assert_distinct(source, DatabaseIdentity("cluster", 123, "alias"))
    assert_distinct(source, DatabaseIdentity("cluster", 124, "rag"))
    assert_distinct(source, DatabaseIdentity("other-cluster", 123, "source"))


def test_unverifiable_identity_fails_closed_without_connection_details():
    connection = MagicMock()
    connection.execute.side_effect = OperationalError("PRIVATE", {}, Exception("PASSWORD"))
    with pytest.raises(DatabaseSafetyError) as error:
        safety.inspect_database(connection)
    assert "PRIVATE" not in str(error.value)
    assert "PASSWORD" not in str(error.value)


@pytest.mark.parametrize("problem", [None, "same", "corpus", "wrong_database"])
def test_guard_finishes_source_transaction_before_allowing_target(monkeypatch, problem):
    source = MagicMock()
    source.url = SimpleNamespace(database="source")
    target = MagicMock()
    target.url = SimpleNamespace(database="rag")
    connection = target.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = problem == "corpus"
    events = []

    @contextmanager
    def source_context(engine):
        events.append("source-open")
        yield source
        events.append("source-closed")

    def inspect(conn, *, source=False):
        if source:
            return DatabaseIdentity("c", 1, "source")
        return DatabaseIdentity(
            "c",
            1 if problem == "same" else 2,
            "unexpected" if problem == "wrong_database" else "rag",
        )

    monkeypatch.setattr(safety, "source_connection", source_context)
    monkeypatch.setattr(safety, "inspect_database", inspect)
    guard = DatabaseGuard(source, target)
    if problem:
        with pytest.raises(DatabaseSafetyError):
            with guard.transaction():
                pytest.fail("La transaction ne doit pas autoriser d'écriture")
    else:
        with guard.transaction():
            assert events == ["source-open", "source-closed"]
    connection.begin.return_value.__exit__.assert_called_once()
