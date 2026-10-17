"""Validation locale, séparation des destinations et confidentialité des erreurs."""

import os

import pytest

from cahier_rag.config import ConfigurationError, load_settings


def test_only_rag_variables_are_read(monkeypatch):
    monkeypatch.setenv("RAG_SOURCE_DATABASE_URL", "postgresql:///source")
    monkeypatch.setenv("RAG_DATABASE_URL", "postgresql:///rag")
    monkeypatch.setenv("DATABASE_URL", "not-a-url")
    settings = load_settings()
    assert settings.require_source_url().database == "source"
    assert settings.require_rag_url().database == "rag"
    assert settings.require_source_url().drivername == "postgresql+psycopg2"


def test_missing_configuration_is_allowed_until_required():
    settings = load_settings(environ={})
    with pytest.raises(ConfigurationError, match="RAG_SOURCE_DATABASE_URL est requise"):
        settings.require_source_url()
    with pytest.raises(ConfigurationError, match="RAG_DATABASE_URL est requise"):
        settings.require_rag_url()


@pytest.mark.parametrize(
    "variable",
    ["DATABASE_URL", "TEST_DATABASE_URL", "ALEMBIC_DATABASE_URL", "SCALINGO_POSTGRESQL_URL"],
)
def test_no_backend_fallback(variable):
    settings = load_settings(environ={variable: "postgresql:///backend"})
    assert settings.source_url is None
    assert settings.rag_url is None


@pytest.mark.parametrize("variable", ["RAG_SOURCE_DATABASE_URL", "RAG_DATABASE_URL"])
@pytest.mark.parametrize(
    "value",
    [
        "not-a-url-secret",
        "sqlite:///source",
        "postgresql+asyncpg://localhost/source",
        "postgresql://localhost",
        "postgresql://localhost/",
        "postgresql://localhost:invalid/source",
        "postgresql://localhost:65536/source",
        "postgresql://localhost:0/source",
        "postgresql://localhost/source?service=secret-service",
        "postgresql://localhost/source?dbname=other",
        "postgresql://localhost/source?options=-c%20default_transaction_read_only=off",
        "postgresql://localhost/source?host=other-host",
        "postgresql://localhost:5432/source?port=5433",
        "postgresql://host1,host2/source",
        "postgresql:///source?host=one&host=two",
    ],
)
def test_invalid_urls_are_rejected_without_echoing_values(variable, value):
    with pytest.raises(ConfigurationError) as error:
        load_settings(environ={variable: value})
    assert variable in str(error.value)
    assert value not in str(error.value)
    assert error.value.__suppress_context__


@pytest.mark.parametrize(
    "source,target",
    [
        ("postgresql:///same", "postgresql:///same"),
        ("postgres://reader:one@HOST/same", "postgresql+psycopg2://writer:two@host:5432/same"),
        ("postgresql://localhost/same", "postgresql://127.0.0.1:5432/same"),
        ("postgresql:///same", "postgresql://[::1]/same"),
        ("postgresql:///same?host=/var/run/postgresql", "postgresql://localhost/same"),
        ("postgresql:///same?host=/run/postgresql&port=5432", "postgresql:///same"),
        ("postgresql://HOST./same?sslmode=require", "postgresql://host/same"),
    ],
)
def test_same_database_is_rejected_even_with_different_credentials(source, target):
    with pytest.raises(ConfigurationError, match="bases distinctes"):
        load_settings(environ={"RAG_SOURCE_DATABASE_URL": source, "RAG_DATABASE_URL": target})


@pytest.mark.parametrize(
    "source,target",
    [
        ("postgresql:///source", "postgresql:///rag"),
        ("postgresql://one/same", "postgresql://two/same"),
        ("postgresql://localhost:5432/same", "postgresql://localhost:5433/same"),
    ],
)
def test_distinct_destinations_are_allowed(source, target):
    settings = load_settings(
        environ={"RAG_SOURCE_DATABASE_URL": source, "RAG_DATABASE_URL": target}
    )
    assert settings.require_source_url() != settings.require_rag_url()


def test_root_and_current_dotenv_are_never_loaded_implicitly(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("RAG_SOURCE_DATABASE_URL=postgresql:///parent\n")
    child = tmp_path / "rag"
    child.mkdir()
    (child / ".env").write_text("RAG_DATABASE_URL=postgresql:///child\n")
    monkeypatch.chdir(child)
    settings = load_settings()
    assert settings.source_url is None
    assert settings.rag_url is None


def test_explicit_file_has_lower_precedence_and_does_not_mutate_environment(tmp_path, monkeypatch):
    config = tmp_path / "selected.env"
    config.write_text(
        "RAG_SOURCE_DATABASE_URL=postgresql:///source\n"
        "RAG_DATABASE_URL=postgresql:///old_rag\n"
        "DATABASE_URL=postgresql:///ignored\n"
    )
    monkeypatch.setenv("RAG_DATABASE_URL", "postgresql:///new_rag")
    before = dict(os.environ)
    settings = load_settings(env_file=config)
    assert settings.require_source_url().database == "source"
    assert settings.require_rag_url().database == "new_rag"
    assert dict(os.environ) == before


def test_dotenv_does_not_interpolate_backend_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql:///backend")
    config = tmp_path / "selected.env"
    config.write_text("RAG_SOURCE_DATABASE_URL=${DATABASE_URL}\n")
    with pytest.raises(ConfigurationError):
        load_settings(env_file=config)


def test_empty_environment_value_does_not_fall_back_to_file(tmp_path):
    config = tmp_path / "selected.env"
    config.write_text("RAG_SOURCE_DATABASE_URL=postgresql:///source\n")
    settings = load_settings(environ={"RAG_SOURCE_DATABASE_URL": " "}, env_file=config)
    with pytest.raises(ConfigurationError):
        settings.require_source_url()


def test_missing_file_is_an_explicit_safe_error(tmp_path):
    with pytest.raises(ConfigurationError, match="fichier.*illisible") as error:
        load_settings(env_file=tmp_path / "secret-filename")
    assert "secret-filename" not in str(error.value)


def test_settings_representation_and_errors_do_not_expose_secrets():
    secret = "never-print-this"
    source = f"postgresql://reader:{secret}@localhost/source?sslkey={secret}"
    settings = load_settings(environ={"RAG_SOURCE_DATABASE_URL": source})
    assert secret not in repr(settings)
    assert source not in str(settings)
    with pytest.raises(ConfigurationError) as error:
        load_settings(environ={"RAG_SOURCE_DATABASE_URL": f"postgresql://u:{secret}@h:bad/source"})
    assert secret not in str(error.value)
