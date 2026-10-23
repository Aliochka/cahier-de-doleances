"""Database selection stays inside pytest; no real database is contacted."""

from types import SimpleNamespace

import pytest


def test_server_ignores_test_database_url(monkeypatch):
    from app import db

    monkeypatch.setattr(db, "settings", SimpleNamespace(ENV="dev"))
    monkeypatch.setenv("DATABASE_URL", "postgresql:///application")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql:///isolated_test")
    assert db._pick_db_url() == "postgresql+psycopg2:///application"


def test_test_url_cannot_supply_missing_application_url(monkeypatch):
    from app import db

    monkeypatch.setattr(db, "settings", SimpleNamespace(ENV="dev"))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SCALINGO_POSTGRESQL_URL", raising=False)
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql:///isolated_test")
    with pytest.raises(RuntimeError, match="No database URL"):
        db._pick_db_url()


@pytest.fixture
def test_configuration(monkeypatch):
    from tests import conftest

    for key in ("TEST_DATABASE_URL", "GDN_IMPORT_TEST_DATABASE_URL"):
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql:///real_application")
    return conftest


def test_pytest_loads_its_private_file(test_configuration, monkeypatch):
    import os

    monkeypatch.setattr(
        test_configuration,
        "dotenv_values",
        lambda *args, **kwargs: {
            "TEST_DATABASE_URL": "postgresql:///disposable_test",
            "DATABASE_URL": "postgresql:///must_not_be_used",
        },
    )
    test_configuration.pytest_configure(None)
    assert os.environ["DATABASE_URL"] == "postgresql:///disposable_test"


def test_explicit_test_environment_wins(test_configuration, monkeypatch):
    import os

    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql:///ci_test")
    monkeypatch.setattr(
        test_configuration,
        "dotenv_values",
        lambda *args, **kwargs: {"TEST_DATABASE_URL": "postgresql:///file_test"},
    )
    test_configuration.pytest_configure(None)
    assert os.environ["DATABASE_URL"] == "postgresql:///ci_test"


@pytest.mark.parametrize("key", ["TEST_DATABASE_URL", "GDN_IMPORT_TEST_DATABASE_URL"])
def test_rejects_real_database_before_collection(test_configuration, monkeypatch, key):
    monkeypatch.setattr(test_configuration, "dotenv_values", lambda *a, **k: {})
    monkeypatch.setenv(key, "postgresql:///real_application")
    with pytest.raises(pytest.UsageError, match="base isolée"):
        test_configuration.pytest_configure(None)


def test_missing_test_configuration_never_uses_application_db(test_configuration, monkeypatch):
    import os

    monkeypatch.setattr(test_configuration, "dotenv_values", lambda *a, **k: {})
    test_configuration.pytest_configure(None)
    assert os.environ["DATABASE_URL"] == "postgresql://localhost:1/cahier_doleances_test"
