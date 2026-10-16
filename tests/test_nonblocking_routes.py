"""Regression tests for blocking I/O and preserved account/email behavior."""

import asyncio
import threading
from datetime import datetime
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.app import app
from app.config import settings
from app.routers import bookmarks
from app.services.auth import auth_service
from app.services.email import email_service


def account():
    return SimpleNamespace(
        id=42,
        email="worker@example.org",
        created_at=datetime(2026, 1, 1),
        last_login=None,
        nationalities='["FR"]',
        profile_completed=True,
        author_id=None,
    )


async def wait_until_entered(entered):
    while not entered.is_set():
        await asyncio.sleep(0.001)


def test_mailjet_io_does_not_block_the_event_loop(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    threads = []

    def create(*, data):
        threads.append(threading.get_ident())
        assert data["Messages"][0]["To"][0]["Email"] == "worker@example.org"
        entered.set()
        if not release.wait(timeout=3):
            raise TimeoutError("test worker was not released")
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(
        email_service, "client", SimpleNamespace(send=SimpleNamespace(create=create))
    )

    async def exercise():
        task = asyncio.create_task(
            email_service.send_magic_link(
                "worker@example.org", "https://example.org/auth/verify/test"
            )
        )
        try:
            await asyncio.wait_for(wait_until_entered(entered), timeout=2)
            # The loop reaches this point while the synchronous network call is pending.
            assert not task.done()
            assert len(threads) == 1 and threads[0] != threading.get_ident()
        finally:
            release.set()
            result = await task
        assert result

    asyncio.run(exercise())


def test_slow_account_sql_does_not_block_another_request(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    threads = []

    def current_user(token):
        threads.append(threading.get_ident())
        entered.set()
        if not release.wait(timeout=3):
            raise TimeoutError("test worker was not released")
        return account()

    monkeypatch.setattr(auth_service, "get_current_user", current_user)

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            task = asyncio.create_task(client.get("/auth/me"))
            try:
                await asyncio.wait_for(wait_until_entered(entered), timeout=2)
                assert not task.done()
                response = await asyncio.wait_for(client.get("/openapi.json"), timeout=2)
                assert response.status_code == 200
                assert threads[0] != threading.get_ident()
            finally:
                release.set()
                profile = await task
            assert profile.status_code == 200
            assert profile.json()["nationalities"] == ["FR"]
            assert profile.headers["cache-control"] == "private, no-store"

    asyncio.run(exercise())


def test_bookmark_session_stays_in_one_worker_thread(monkeypatch):
    threads = []

    class WorkerSession:
        def __init__(self):
            threads.append(threading.get_ident())

        def __enter__(self):
            threads.append(threading.get_ident())
            return self

        def execute(self, statement):
            threads.append(threading.get_ident())
            return SimpleNamespace(scalar_one_or_none=lambda: 123)

        def commit(self):
            threads.append(threading.get_ident())

        def __exit__(self, *args):
            threads.append(threading.get_ident())

    monkeypatch.setattr(auth_service, "get_current_user", lambda token: account())
    monkeypatch.setattr(bookmarks, "SessionLocal", WorkerSession)

    async def exercise():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.post(
                "/bookmarks/answer/42", headers={"Origin": settings.BASE_URL}
            )
        assert response.status_code == 200 and response.json()["bookmark_id"] == 123
        assert len(threads) == 5 and len(set(threads)) == 1
        assert threads[0] != threading.get_ident()

    asyncio.run(exercise())


@pytest.mark.parametrize("outcome,status", [(200, 200), (503, 500), ("exception", 500)])
def test_magic_link_delivery_and_errors_use_existing_mailjet_client(monkeypatch, outcome, status):
    sent = []

    def create(*, data):
        sent.append(data)
        if outcome == "exception":
            raise RuntimeError("test-mailjet-internal-detail")
        return SimpleNamespace(status_code=outcome)

    monkeypatch.setattr(settings, "LOGIN_EMAIL_ENABLED", True)
    monkeypatch.setattr(
        email_service, "client", SimpleNamespace(send=SimpleNamespace(create=create))
    )
    with TestClient(app) as client:
        response = client.post(
            "/auth/send-link",
            json={"email": "worker@example.org"},
            headers={"Origin": settings.BASE_URL, "Accept": "application/json"},
        )
    assert response.status_code == status
    assert response.headers["cache-control"] == "private, no-store"
    assert "test-mailjet-internal-detail" not in response.text
    assert len(sent) == 1
    message = sent[0]["Messages"][0]
    token = message["TextPart"].split("/auth/verify/")[1].split()[0]
    assert auth_service.verify_magic_token(token) == "worker@example.org"


def test_mailjet_unavailable_remains_an_explicit_failure(monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "LOG_MAGIC_LINKS", False)
    monkeypatch.setattr(email_service, "client", None)
    with TestClient(app) as client:
        response = client.post(
            "/auth/send-link",
            json={"email": "worker@example.org"},
            headers={"Origin": settings.BASE_URL, "Accept": "application/json"},
        )
    assert response.status_code == 500
    assert not response.json().get("success", False)
    assert response.headers["cache-control"] == "private, no-store"
