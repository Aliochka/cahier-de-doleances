"""Search failures and bookmark idempotence, including real PostgreSQL races."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import Insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from app.app import app
from app.config import settings
from app.models import Bookmark, User
from app.routers import bookmarks
from app.search_errors import SearchTimeout, handle_search_errors
from app.services.auth import auth_service


@pytest.mark.parametrize("inserted_id", [123, None])
@pytest.mark.parametrize("page_type", ["question", "answer", "author"])
def test_bookmark_insert_is_atomic_and_preserves_responses(monkeypatch, inserted_id, page_type):
    statements = []

    class BookmarkSession:
        committed = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, statement):
            statements.append(statement)
            return SimpleNamespace(scalar_one_or_none=lambda: inserted_id)

        def commit(self):
            self.committed = True

    session = BookmarkSession()
    monkeypatch.setattr(bookmarks, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        auth_service,
        "get_current_user",
        lambda token: SimpleNamespace(id=42, email="test@example.org"),
    )
    with TestClient(app) as client:
        response = client.post(f"/bookmarks/{page_type}/9", headers={"Origin": settings.BASE_URL})
    assert response.status_code == 200 and response.json()["success"]
    assert session.committed
    assert len(statements) == 1
    sql = str(statements[0])
    assert "ON CONFLICT ON CONSTRAINT unique_user_bookmark DO NOTHING" in sql
    assert "RETURNING bookmarks.id" in sql
    assert statements[0].compile().params == {"user_id": 42, "page_type": page_type, "page_id": 9}
    if inserted_id is None:
        assert response.json() == {"message": "Marque-page déjà existant", "success": True}
    else:
        assert response.json()["bookmark_id"] == inserted_id


@pytest.mark.integration
@pytest.mark.parametrize("code", ["57014", "22012"])
def test_postgresql_search_rollback_restores_transaction(web_data, code):
    with web_data["factory"]() as db:
        with pytest.raises(SearchTimeout if code == "57014" else DBAPIError):
            with handle_search_errors(db):
                if code == "57014":
                    db.execute(text("SET LOCAL statement_timeout = '5ms'"))
                    db.execute(text("SELECT pg_sleep(0.05)"))
                else:
                    # PostgreSQL division by zero gives an unexpected DBAPI error.
                    db.execute(text("SELECT 1 / 0"))
        assert db.execute(text("SELECT 1")).scalar_one() == 1


@pytest.mark.integration
@pytest.mark.parametrize("page_type", ["question", "answer", "author"])
def test_postgresql_bookmark_concurrency_and_user_isolation(test_engine, monkeypatch, page_type):
    """Separate committed connections are essential: fixture savepoints cannot model a race."""
    factory = sessionmaker(bind=test_engine, expire_on_commit=False)
    with factory() as db:
        users = [User(email=f"race-{uuid4().hex}@example.org") for _ in range(2)]
        db.add_all(users)
        db.commit()
        ids = [user.id for user in users]
    monkeypatch.setattr(auth_service, "get_current_user", lambda token: users[int(token)])
    barrier = Barrier(2)

    class RacingSession(Session):
        def execute(self, statement, *args, **kwargs):
            if isinstance(statement, Insert):
                barrier.wait(timeout=10)
            return super().execute(statement, *args, **kwargs)

    racing_factory = sessionmaker(bind=test_engine, class_=RacingSession, expire_on_commit=False)
    monkeypatch.setattr(bookmarks, "SessionLocal", racing_factory)
    path = f"/bookmarks/{page_type}/42"

    def add():
        with TestClient(app) as client:
            client.cookies.set("session_token", "0")
            return client.post(path, headers={"Origin": settings.BASE_URL})

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: add(), range(2)))
        assert [response.status_code for response in responses] == [200, 200]
        assert all(response.json()["success"] for response in responses)
        assert sum("bookmark_id" in response.json() for response in responses) == 1
        monkeypatch.setattr(bookmarks, "SessionLocal", factory)
        with TestClient(app, headers={"Origin": settings.BASE_URL}) as client:
            client.cookies.set("session_token", "0")
            assert client.post(path).json()["message"] == "Marque-page déjà existant"
            assert client.get(f"/bookmarks/check/{page_type}/42").json()["is_bookmarked"]
            client.cookies.set("session_token", "1")
            assert not client.get(f"/bookmarks/check/{page_type}/42").json()["is_bookmarked"]
            assert not client.delete(path).json()["success"]
            assert client.post(path).json()["success"]
            assert client.delete(path).json()["success"]
            client.cookies.set("session_token", "0")
            assert client.get(f"/bookmarks/check/{page_type}/42").json()["is_bookmarked"]
            with factory() as db:
                assert (
                    db.scalar(select(func.count(Bookmark.id)).where(Bookmark.user_id.in_(ids))) == 1
                )
            assert client.delete(path).json()["success"]
            assert not client.delete(path).json()["success"]
    finally:
        with factory() as db:
            db.execute(delete(Bookmark).where(Bookmark.user_id.in_(ids)))
            db.execute(delete(User).where(User.id.in_(ids)))
            db.commit()
