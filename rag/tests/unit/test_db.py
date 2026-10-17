"""Fabriques paresseuses et cycle de transaction sans serveur PostgreSQL."""

from unittest.mock import MagicMock

import pytest

from cahier_rag import db
from cahier_rag.config import ConfigurationError, load_settings


@pytest.fixture
def settings():
    return load_settings(
        environ={
            "RAG_SOURCE_DATABASE_URL": "postgresql://reader@source-host/source",
            "RAG_DATABASE_URL": "postgresql://writer@rag-host/rag",
        }
    )


def test_engines_are_independent_lazy_and_source_defaults_to_read_only(settings):
    source = db.create_source_engine(settings)
    target = db.create_rag_engine(settings)
    try:
        # psycopg2 et les sockets sont interdits par la fixture automatique.
        assert source is not target
        assert source.url.host == "source-host"
        assert source.url.username == "reader"
        assert target.url.host == "rag-host"
        assert target.url.username == "writer"
        assert source.get_execution_options()["postgresql_readonly"] is True
        assert "postgresql_readonly" not in target.get_execution_options()
        assert source.hide_parameters and target.hide_parameters
        assert source.pool.timeout() == target.pool.timeout() == 5
    finally:
        source.dispose()
        target.dispose()


@pytest.mark.parametrize("factory", [db.create_source_engine, db.create_rag_engine])
def test_connect_timeout_cannot_be_overridden_by_url(factory, monkeypatch):
    import psycopg2

    settings = load_settings(
        environ={
            "RAG_SOURCE_DATABASE_URL": "postgresql:///source?connect_timeout=9999",
            "RAG_DATABASE_URL": "postgresql:///rag?connect_timeout=9999",
        }
    )
    received = {}

    def intercepted(*args, **kwargs):
        received.update(kwargs)
        raise RuntimeError("Connexion interceptée ; aucun serveur contacté.")

    monkeypatch.setattr(psycopg2, "connect", intercepted)
    engine = factory(settings)
    try:
        assert received == {}
        with pytest.raises(RuntimeError, match="interceptée"):
            engine.connect()
        assert received["connect_timeout"] == 5
    finally:
        engine.dispose()


@pytest.mark.parametrize("factory", [db.create_source_engine, db.create_rag_engine])
def test_missing_url_does_not_create_an_engine(factory, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Aucun moteur ne doit être créé sans URL dédiée.")

    monkeypatch.setattr(db, "create_engine", forbidden)
    with pytest.raises(ConfigurationError):
        factory(load_settings(environ={"DATABASE_URL": "postgresql:///backend"}))


@pytest.mark.parametrize("fail", [False, True])
def test_source_transaction_is_read_only_before_begin_and_always_closed(fail):
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execution_options.return_value = connection
    events = []
    connection.execution_options.side_effect = lambda **kwargs: (
        events.append(("options", kwargs)) or connection
    )
    transaction = connection.begin.return_value
    connection.begin.side_effect = lambda: events.append(("begin",)) or transaction

    def operation():
        with db.source_connection(engine) as active:
            assert active is connection
            assert events == [("options", {"postgresql_readonly": True}), ("begin",)]
            if fail:
                raise RuntimeError("échec du traitement")

    if fail:
        with pytest.raises(RuntimeError, match="échec"):
            operation()
    else:
        operation()
    transaction.__exit__.assert_called_once()
    engine.connect.return_value.__exit__.assert_called_once()
    assert transaction.__exit__.call_args.args[0] is (RuntimeError if fail else None)
