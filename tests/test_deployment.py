"""Deployment and authentication regressions; PostgreSQL cases use only the test DB."""

import json
import logging
import os
import subprocess
import sys
from datetime import timedelta
from types import SimpleNamespace

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.config import Settings


def lan_env():
    return {
        "ENV": "prod",
        "SECRET_KEY": "test-only-secret-" * 4,
        "BASE_URL": "http://192.168.1.56:8000",
        "ALLOWED_HOSTS": "192.168.1.56,127.0.0.1,localhost",
        "COOKIE_SECURE": "false",
    }


@pytest.mark.parametrize(
    "override",
    [
        {"SECRET_KEY": ""},
        {"SECRET_KEY": "your-secret-key-change-in-production"},
        {"SECRET_KEY": "short"},
        {"ALLOWED_HOSTS": "*"},
        {"ALLOWED_HOSTS": "localhost"},
        {"BASE_URL": "http://public.example", "ALLOWED_HOSTS": "public.example"},
        {"BASE_URL": "http://192.168.1.56:8000/path"},
        {"COOKIE_SECURE": "maybe"},
        {"ENFORCE_HTTPS": "true"},
        {"LOG_MAGIC_LINKS": "true"},
        {"TRUSTED_PROXY_IPS": "*"},
        {"TEST_DATABASE_URL": "postgresql:///wrong"},
        {"ALEMBIC_DATABASE_URL": "postgresql:///wrong"},
        {"SCALINGO_POSTGRESQL_URL": "postgresql:///wrong"},
    ],
)
def test_unsafe_deployment_settings_are_rejected(override):
    with pytest.raises(ValueError):
        Settings(lan_env() | override)


def test_http_lan_requires_explicit_insecure_cookie_opt_in():
    env = lan_env()
    del env["COOKIE_SECURE"]
    with pytest.raises(ValueError):
        Settings(env)
    lan = Settings(lan_env())
    assert not lan.COOKIE_SECURE and not lan.ENFORCE_HTTPS
    public = Settings(
        lan_env()
        | {
            "BASE_URL": "https://cahierdedoleances.fr",
            "ALLOWED_HOSTS": "cahierdedoleances.fr",
            "COOKIE_SECURE": "true",
        }
    )
    assert public.COOKIE_SECURE and public.ENFORCE_HTTPS
    with pytest.raises(ValueError):
        Settings(lan_env() | {"BASE_URL": "https://192.168.1.56:8000"})


def test_jsonld_cannot_escape_script_and_keeps_custom_serialization():
    from decimal import Decimal

    from starlette.datastructures import URL

    from app.web import templates

    payload = '</script><script>alert("x")</script>'
    output = templates.env.from_string("<script>{{ value|tojson|safe }}</script>").render(
        value={"name": payload, "url": URL("http://example.test"), "number": Decimal("1.5")}
    )
    assert output.count("</script>") == 1
    data = json.loads(output.removeprefix("<script>").removesuffix("</script>"))
    assert data == {"name": payload, "url": "http://example.test", "number": 1.5}


def test_access_logs_redact_magic_link_tokens():
    from app.logging_filters import RedactMagicLinkFilter

    for args in (
        ("GET /auth/verify/secret-token HTTP/1.1",),
        {"request": "GET /auth/verify/secret-token HTTP/1.1"},
    ):
        record = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "%s", (), None)
        record.args = args
        RedactMagicLinkFilter().filter(record)
        assert "secret-token" not in str(record.args)
        assert "[REDACTED]" in str(record.args)


def test_jwt_expiration_signature_and_token_purpose(monkeypatch):
    import jwt

    from app.services.auth import auth_service

    magic = auth_service.create_magic_token("audit@example.org")
    session = auth_service.create_session_token(42)
    assert auth_service.verify_magic_token(magic) == "audit@example.org"
    assert auth_service.verify_session_token(session) == 42
    assert auth_service.verify_magic_token(session) is None
    assert auth_service.verify_session_token(magic) is None
    assert (
        auth_service.verify_magic_token(
            auth_service.create_magic_token("audit@example.org", timedelta(seconds=-1))
        )
        is None
    )
    forged = jwt.encode({"sub": "42", "type": "session"}, "another-secret-" * 4, algorithm="HS256")
    assert auth_service.verify_session_token(forged) is None


@pytest.mark.parametrize("secure", [False, True])
def test_login_and_logout_cookie_flags(secure, monkeypatch):
    from app.app import app
    from app.config import settings
    from app.services.auth import auth_service

    monkeypatch.setattr(settings, "COOKIE_SECURE", secure)
    monkeypatch.setattr(auth_service, "get_or_create_user", lambda email: SimpleNamespace(id=42))
    with TestClient(app) as client:
        response = client.get(
            f"/auth/verify/{auth_service.create_magic_token('audit@example.org')}",
            follow_redirects=False,
        )
        assert response.status_code == 302
        cookie = response.headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=lax" in cookie
        assert ("Secure" in cookie) == secure
        logout = client.post("/auth/logout", follow_redirects=False)
        assert ("Secure" in logout.headers["set-cookie"]) == secure
        assert "Max-Age=0" in logout.headers["set-cookie"]


@pytest.mark.parametrize("origin", ["http://192.168.1.56:8000", "https://cahierdedoleances.fr"])
def test_magic_links_use_configured_origin(monkeypatch, origin):
    from app.app import app
    from app.config import settings
    from app.services.email import email_service

    links = []

    async def capture(email, link):
        links.append(link)
        return True

    monkeypatch.setattr(settings, "BASE_URL", origin)
    monkeypatch.setattr(email_service, "send_magic_link", capture)
    with TestClient(app) as client:
        response = client.post(
            "/auth/send-link",
            json={"email": "audit@example.org"},
            headers={"x-forwarded-host": "attacker.example", "x-forwarded-proto": "https"},
        )
        assert response.status_code == 200
    assert links[0].startswith(f"{origin}/auth/verify/")


def test_production_email_failure_does_not_log_login_token(monkeypatch, capsys):
    import asyncio

    from app.config import settings
    from app.services.email import email_service

    monkeypatch.setattr(settings, "LOG_MAGIC_LINKS", False)
    monkeypatch.setattr(email_service, "client", None)
    assert not asyncio.run(
        email_service.send_magic_link(
            "audit@example.org", "http://localhost/auth/verify/secret-token"
        )
    )
    assert "secret-token" not in capsys.readouterr().out


def test_health_failure_is_generic_and_read_only(monkeypatch):
    from app.app import app
    from app.routers import health

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def begin(self):
            return self

        def execute(self, query):
            queries.append(str(query))
            if str(query) == "SELECT 1":
                raise OperationalError("", {}, Exception("secret-password"))

    queries = []
    monkeypatch.setattr(health, "engine", SimpleNamespace(connect=Connection))
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert queries[0] == "SET TRANSACTION READ ONLY"


def test_production_lan_host_validation_and_no_https_redirect():
    env = dict(os.environ) | lan_env()
    for name in ("TEST_DATABASE_URL", "ALEMBIC_DATABASE_URL", "SCALINGO_POSTGRESQL_URL"):
        env.pop(name, None)
    env["DATABASE_URL"] = "postgresql:///unused"
    code = """
from fastapi.testclient import TestClient
from app.app import app
with TestClient(app, base_url="http://192.168.1.56:8000") as client:
    response = client.get("/static/css/reset.css", follow_redirects=False,
                          headers={"x-forwarded-host": "attacker.example", "x-forwarded-proto": "https"})
    assert response.status_code == 200
    assert client.get("/static/css/reset.css", headers={"host": "attacker.example"}).status_code == 400
    assert client.get("/auth/me").status_code == 401
"""
    subprocess.run(
        [sys.executable, "-c", code], env=env, check=True, capture_output=True, text=True
    )


@pytest.mark.integration
def test_accounts_profiles_and_bookmarks_on_http(client, web_data, monkeypatch):
    from app.config import settings
    from app.services.auth import auth_service

    monkeypatch.setattr(settings, "COOKIE_SECURE", False)
    response = client.get(
        f"/auth/verify/{auth_service.create_magic_token('deployment@example.org')}",
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/complete-profile", json={"nationalities": ["FR"]}).status_code == 200
    assert client.get("/auth/me").json()["profile_completed"]
    path = f"/bookmarks/question/{web_data['multi']}"
    assert client.post(path).status_code == 200
    assert client.get("/bookmarks").status_code == 200
    assert client.delete(path).json()["success"]
    client.post("/auth/logout", follow_redirects=False)
    assert client.get("/auth/me").status_code == 401


@pytest.mark.integration
def test_preflight_checks_schema_and_reports_drift_without_writes(test_engine):
    from app.deployment_check import inspect_schema

    with test_engine.connect() as connection, connection.begin():
        connection.execute(text("SET TRANSACTION READ ONLY"))
        report = inspect_schema(connection, "remove_runtime_caches")
        assert not report["errors"]
        assert connection.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
        drift = inspect_schema(connection, "unknown_revision")
        assert len(drift["errors"]) == 2


def test_deployment_compose_owns_no_postgres_or_data_volume():
    from pathlib import Path

    compose = yaml.safe_load(Path("compose.deploy.yml").read_text())
    assert set(compose["services"]) == {"app", "caddy"}
    assert set(compose["volumes"]) == {"caddy-data", "caddy-config"}
    assert "volumes" not in compose["services"]["app"]
    assert "ports" not in compose["services"]["app"]
    assert "postgres-existing" not in compose["services"]["caddy"]["networks"]
    assert compose["networks"]["proxy-private"]["internal"]
    assert (
        compose["services"]["caddy"]["networks"]["proxy-private"]["ipv4_address"] == "172.30.80.2"
    )
    assert compose["networks"]["postgres-existing"] == {
        "external": True,
        "name": "cahier-de-doleances_cahier-internal",
    }
    assert "alembic" not in str(compose)


def test_preflight_dns_failure_returns_nonzero_without_credentials(monkeypatch, capsys):
    import socket

    from app import deployment_check

    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://cahier:DO_NOT_PRINT@cahier-postgres:5432/cahier_doleances"
    )
    for name in ("TEST_DATABASE_URL", "ALEMBIC_DATABASE_URL", "SCALINGO_POSTGRESQL_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sys, "argv", ["deployment_check"])

    def fail(*args, **kwargs):
        raise socket.gaierror("DO_NOT_PRINT")

    monkeypatch.setattr(socket, "getaddrinfo", fail)
    assert deployment_check.main() == 1
    output = capsys.readouterr().out
    assert "DO_NOT_PRINT" not in output
    assert json.loads(output)["status"] == "failed"


@pytest.mark.integration
def test_health_success_on_test_database(test_engine, monkeypatch):
    from app.app import app
    from app.routers import health

    monkeypatch.setattr(health, "engine", test_engine)
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}


@pytest.mark.parametrize("code", ["57014", "42P01"])
def test_search_rolls_back_failed_transactions_and_only_masks_timeouts(code, monkeypatch):
    from starlette.requests import Request

    from app.routers import search

    class Session:
        rolled_back = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query, *args):
            sql = str(query)
            if sql.startswith("SET LOCAL"):
                assert not self.rolled_back
                return None
            raise OperationalError("", {}, SimpleNamespace(pgcode=code))

        def rollback(self):
            self.rolled_back = True

    session = Session()
    monkeypatch.setattr(search, "SessionLocal", lambda: session)
    request = Request({"type": "http", "method": "GET", "path": "/search/answers", "headers": []})
    monkeypatch.setattr(search.templates, "TemplateResponse", lambda request, name, ctx: ctx)
    if code == "57014":
        assert (
            search.search_answers(request, q="culture", page=1, cursor=None, partial=False)[
                "answers"
            ]
            == []
        )
    else:
        with pytest.raises(OperationalError):
            search.search_answers(request, q="culture", page=1, cursor=None, partial=False)
    assert session.rolled_back


def test_https_proxy_order_trust_and_local_health_probe():
    env = (
        dict(os.environ)
        | lan_env()
        | {
            "BASE_URL": "https://cahierdedoleances.fr",
            "ALLOWED_HOSTS": "cahierdedoleances.fr,localhost",
            "COOKIE_SECURE": "true",
            "ENFORCE_HTTPS": "true",
            "TRUSTED_PROXY_IPS": "172.30.80.2",
            "DATABASE_URL": "postgresql:///unused",
        }
    )
    for name in ("TEST_DATABASE_URL", "ALEMBIC_DATABASE_URL", "SCALINGO_POSTGRESQL_URL"):
        env.pop(name, None)
    code = """
import asyncio
from app.app import app

async def request(peer, path, proto=None, host="cahierdedoleances.fr"):
    messages = []
    headers = [(b"host", host.encode())]
    if proto:
        headers.append((b"x-forwarded-proto", proto.encode()))
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "GET", "scheme": "http", "path": path,
             "raw_path": path.encode(), "query_string": b"", "root_path": "",
             "headers": headers, "client": (peer, 1234), "server": ("app", 8000)}
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    async def send(message):
        messages.append(message)
    await app(scope, receive, send)
    return next(m for m in messages if m["type"] == "http.response.start")

async def main():
    path = "/static/css/reset.css"
    assert (await request("172.30.80.2", path, "https"))["status"] == 200
    assert (await request("198.51.100.7", path, "https"))["status"] == 307
    assert (await request("172.30.80.2", path, "http"))["status"] == 307
    assert (await request("172.30.80.2", path, "https", "evil.example"))["status"] == 400
    # Prove the real readiness route is reached without connecting to any DB.
    from types import SimpleNamespace
    from app.routers import health
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def begin(self): return self
        def execute(self, query): pass
    health.engine = SimpleNamespace(connect=Connection)
    assert (await request("127.0.0.1", "/healthz", host="localhost"))["status"] == 200
    assert (await request("198.51.100.7", "/healthz"))["status"] == 307
    assert (await request("127.0.0.1", path))["status"] == 307

asyncio.run(main())
"""
    subprocess.run(
        [sys.executable, "-c", code], env=env, check=True, capture_output=True, text=True
    )


def test_disabled_email_login_does_not_issue_or_send_tokens(monkeypatch):
    from app.app import app
    from app.config import settings
    from app.services.auth import auth_service

    monkeypatch.setattr(settings, "LOGIN_EMAIL_ENABLED", False)

    def forbidden(*args):
        pytest.fail("Disabled login must not generate a token")

    monkeypatch.setattr(auth_service, "create_magic_token", forbidden)
    with TestClient(app) as client:
        response = client.post("/auth/send-link", json={"email": "audit@example.org"})
        assert response.status_code == 503
        assert "temporairement" in response.json()["detail"]


def test_unavailable_login_forms_are_hidden():
    from app.web import templates

    rendered = templates.env.get_template("base/base.html").render(
        LOGIN_EMAIL_ENABLED=False,
        request=SimpleNamespace(
            url_for=lambda *args, **kwargs: "/static/asset", url=SimpleNamespace(path="/")
        ),
    )
    assert 'hidden id="login-form"' in rendered
    assert 'hidden id="bookmark-login-form"' in rendered
    assert "connexion par courriel est temporairement indisponible" in rendered
