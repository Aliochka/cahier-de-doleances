"""Toutes les unités sont indépendantes du réseau et des paramètres du développeur."""

import socket

import psycopg2
import pytest


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for name in (
        "RAG_SOURCE_DATABASE_URL",
        "RAG_DATABASE_URL",
        "DATABASE_URL",
        "TEST_DATABASE_URL",
        "ALEMBIC_DATABASE_URL",
        "SCALINGO_POSTGRESQL_URL",
    ):
        monkeypatch.delenv(name, raising=False)

    def forbidden(*args, **kwargs):
        raise AssertionError("Les tests unitaires ne doivent pas ouvrir de connexion.")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(psycopg2, "connect", forbidden)
