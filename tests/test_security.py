"""Account security tests never access a database or send real emails."""

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.app import app
from app.config import Settings, settings
from app.security import PRIVATE_CACHE_CONTROL
from app.services.auth import auth_service


@pytest.fixture
def account_client(monkeypatch):
    user = SimpleNamespace(
        id=42,
        email="security@example.org",
        created_at=datetime(2026, 1, 1),
        last_login=None,
        nationalities='["FR"]',
        profile_completed=True,
        author_id=None,
    )
    monkeypatch.setattr(settings, "BASE_URL", "https://cahierdedoleances.fr")
    monkeypatch.setattr(settings, "CSRF_TRUSTED_ORIGINS", [])
    monkeypatch.setattr(
        auth_service, "get_current_user", lambda token: user if token == "session" else None
    )
    monkeypatch.setattr(auth_service, "update_user_profile", lambda *args, **kwargs: user)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize(
    "origin",
    [
        "https://cahierdedoleances.fr",
        "http://localhost:8000",
        "http://127.0.0.1:8001",
        "http://192.168.1.56:8000",
        "https://deploy-preview-42--controlled.netlify.app",
    ],
)
def test_exact_origins_allow_authenticated_writes(account_client, monkeypatch, origin):
    monkeypatch.setattr(settings, "CSRF_TRUSTED_ORIGINS", [origin])
    account_client.cookies.set("session_token", "session")
    response = account_client.post(
        "/auth/complete-profile", json={"nationalities": ["FR"]}, headers={"Origin": origin}
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == PRIVATE_CACHE_CONTROL


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "null"},
        {"Origin": ""},
        {"Origin": "https://cahierdedoleances.fr.evil.example"},
        {"Origin": "https://evil.cahierdedoleances.fr"},
        {"Origin": "http://cahierdedoleances.fr"},
        {"Origin": "https://cahierdedoleances.fr:444"},
        {"Origin": "https://cahierdedoleances.fr:0"},
        {"Origin": "http://localhost:8000"},
        {"Origin": "https://cahierdedoleances.fr/path"},
        {"Origin": "https://cahierdedoleances.fr@evil.example"},
        {"Origin": "https://cahierdedoleances.fr,https://evil.example"},
        {"Origin": "https://deploy-preview-43--controlled.netlify.app"},
        {"Referer": "https://evil.example/account"},
        {"Origin": "null", "Referer": "https://cahierdedoleances.fr/account"},
        [("Origin", "https://cahierdedoleances.fr"), ("Origin", "https://evil.example")],
    ],
)
@pytest.mark.parametrize("authenticated", [False, True])
def test_origin_rejection_precedes_writes(account_client, headers, authenticated):
    if authenticated:
        account_client.cookies.set("session_token", "session")
    response = account_client.post(
        "/auth/complete-profile", json={"nationalities": ["FR"]}, headers=headers
    )
    assert response.status_code == 403
    assert response.headers["cache-control"] == PRIVATE_CACHE_CONTROL


def test_missing_origin_uses_exact_referer(account_client):
    response = account_client.post(
        "/auth/logout",
        headers={"Referer": "https://cahierdedoleances.fr/account?section=profile"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    assert "Path=/" in response.headers["set-cookie"]
    assert "Domain=" not in response.headers["set-cookie"]
    assert response.headers["cache-control"] == PRIVATE_CACHE_CONTROL


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/auth/send-link"),
        ("POST", "/auth/logout"),
        ("POST", "/auth/logout/"),
        ("POST", "/auth/complete-profile"),
        ("POST", "/bookmarks/question/42"),
        ("DELETE", "/bookmarks/author/42"),
    ],
)
def test_every_account_write_checks_origin(account_client, method, path):
    response = account_client.request(method, path, follow_redirects=False)
    assert response.status_code == 403
    assert response.headers["cache-control"] == PRIVATE_CACHE_CONTROL


@pytest.mark.parametrize(
    "method,path,body,status",
    [
        ("GET", "/auth/me", None, 401),
        ("GET", "/auth/author-info", None, 401),
        ("GET", "/auth/verify/invalid", None, 400),
        ("GET", "/bookmarks", None, 401),
        ("GET", "/bookmarks/check/question/42", None, 401),
        ("POST", "/auth/complete-profile", {"nationalities": ["FR"]}, 401),
        ("POST", "/auth/send-link", {"email": "invalid"}, 422),
        ("POST", "/bookmarks/question/42", None, 401),
        ("DELETE", "/bookmarks/question/42", None, 401),
    ],
)
def test_private_error_cache_policy(account_client, method, path, body, status):
    response = account_client.request(
        method, path, json=body, headers={"Origin": settings.BASE_URL}
    )
    assert response.status_code == status
    assert response.headers["cache-control"] == PRIVATE_CACHE_CONTROL


def test_profile_and_validation_remain_private(account_client):
    account_client.cookies.set("session_token", "session")
    response = account_client.get("/auth/me")
    assert response.json()["nationalities"] == ["FR"]
    assert response.headers["cache-control"] == PRIVATE_CACHE_CONTROL
    response = account_client.post(
        "/auth/complete-profile", json={"nationalities": []}, headers={"Origin": settings.BASE_URL}
    )
    assert response.status_code == 400
    assert response.headers["cache-control"] == PRIVATE_CACHE_CONTROL


@pytest.mark.parametrize("accept", ["application/json", "text/html"])
def test_unexpected_private_error_is_not_cached(account_client, monkeypatch, accept):
    def fail(token):
        raise RuntimeError("internal-test-detail")

    monkeypatch.setattr(auth_service, "get_current_user", fail)
    response = account_client.get("/auth/me", headers={"Accept": accept})
    assert response.status_code == 500
    assert "internal-test-detail" not in response.text
    assert response.headers["cache-control"] == PRIVATE_CACHE_CONTROL


def test_public_cache_is_unchanged_but_session_responses_are_private(account_client):
    path = "/static/css/reset.css"
    public = account_client.get(path)
    assert public.status_code == 200
    assert "no-store" not in public.headers.get("cache-control", "")
    assert "no-store" not in account_client.get("/missing-public-page").headers.get(
        "cache-control", ""
    )
    account_client.cookies.set("session_token", "expired")
    private = account_client.get(path)
    assert private.status_code == 200
    assert private.headers["cache-control"] == PRIVATE_CACHE_CONTROL
    missing = account_client.get("/missing-public-page")
    assert missing.status_code == 404
    assert missing.headers["cache-control"] == PRIVATE_CACHE_CONTROL


@pytest.mark.parametrize(
    "origin",
    ["*.netlify.app", "https://*.netlify.app", "https://example.org/path", "null", "https://a:bad"],
)
def test_extra_origins_must_be_exact(origin):
    with pytest.raises(ValueError):
        Settings({"CSRF_TRUSTED_ORIGINS": origin})
