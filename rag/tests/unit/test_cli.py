"""Diagnostics sans réseau, avec erreurs explicites et sans secrets."""

import pytest

from cahier_rag.__main__ import main


def test_diagnostic_accepts_explicit_file_without_connecting(tmp_path, capsys):
    config = tmp_path / "chosen.env"
    config.write_text(
        "RAG_SOURCE_DATABASE_URL=postgresql://reader:secret@localhost/source\n"
        "RAG_DATABASE_URL=postgresql://writer:secret@localhost/rag\n"
    )
    assert main(["check-config", "--env-file", str(config)]) == 0
    output = capsys.readouterr()
    assert "Aucune connexion" in output.out
    assert "secret" not in output.out + output.err


def test_diagnostic_requires_both_roles_by_default(monkeypatch, capsys):
    monkeypatch.setenv("RAG_SOURCE_DATABASE_URL", "postgresql:///source")
    assert main(["check-config"]) == 2
    assert "RAG_DATABASE_URL est requise" in capsys.readouterr().err


@pytest.mark.parametrize(
    "role,variable", [("source", "RAG_SOURCE_DATABASE_URL"), ("rag", "RAG_DATABASE_URL")]
)
def test_one_connection_can_be_validated_independently(role, variable, monkeypatch):
    monkeypatch.setenv(variable, "postgresql:///configured")
    assert main(["check-config", "--connection", role]) == 0


def test_invalid_configuration_fails_without_secret_or_traceback(monkeypatch, capsys):
    monkeypatch.setenv("RAG_SOURCE_DATABASE_URL", "postgresql://u:TOP-SECRET@host:bad/source")
    assert main(["check-config"]) == 2
    output = capsys.readouterr()
    assert "RAG_SOURCE_DATABASE_URL" in output.err
    assert "TOP-SECRET" not in output.out + output.err
    assert "Traceback" not in output.err
