"""Aucune unité ne peut contacter un serveur, même si une base de test est configurée."""

import socket

import psycopg2
import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Les tests unitaires ne doivent pas ouvrir de connexion.")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(psycopg2, "connect", forbidden)
