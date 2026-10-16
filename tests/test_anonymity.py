"""Public author identity regressions with synthetic data and no database access."""

from fastapi.testclient import TestClient

from app.helpers import public_author


def test_anonymity_mutation_is_removed():
    from app.app import app
    from app.services.auth import auth_service

    with TestClient(app) as client:
        assert (
            client.post(
                "/auth/toggle-anonymity", json={"is_anonymous": False, "display_name": "Test"}
            ).status_code
            == 404
        )
    assert "/auth/toggle-anonymity" not in app.openapi()["paths"]
    assert not hasattr(auth_service, "toggle_author_anonymity")


def test_missing_author_status_does_not_expose_a_name():
    assert public_author(42, "Nom confidentiel", None)["name"] == "Auteur #42"
    assert public_author(None, "Nom confidentiel", None)["name"] == "Auteur anonyme"
