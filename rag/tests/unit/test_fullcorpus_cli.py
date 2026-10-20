"""Séparation des périmètres et interface : pas de connexion ou dépendance GPU."""

import pytest

from cahier_rag.fullcorpus.search import FullSearch
from cahier_rag.personal.live import ask


class Store:
    space = "full"

    def state(self):
        return {"verified": False}


def test_incomplete_index_refused_before_database():
    with pytest.raises(ValueError, match="vérifié"):
        FullSearch(Store()).parameters(50, None, None, None)


@pytest.mark.parametrize("limit", [0, 101, True, -1])
def test_invalid_search_limit(limit):
    with pytest.raises(ValueError, match="Limite"):
        FullSearch(Store()).parameters(limit, None, None, None)


def test_unknown_partition_and_corpus():
    with pytest.raises(ValueError, match="Partition"):
        FullSearch(Store()).parameters(50, None, None, "test")
    with pytest.raises(ValueError, match="Corpus"):
        ask(".", "libre", corpus="unknown")


def test_ui_explicit_corpus():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from cahier_rag.personal.web import create_app

    with TestClient(
        create_app(lambda q, p: None, corpus="rag026"),
        base_url="http://127.0.0.1:8770",
        client=("127.0.0.1", 1234),
    ) as c:
        assert "RAG-026" in c.get("/api/state").json()["scope"]
        assert "RAG-007" not in c.get("/api/state").json()["scope"]
