"""Public author identity regressions with synthetic data and no database access."""

import json
import re
from datetime import datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.helpers import public_author


@pytest.fixture(
    params=[(False, "Pseudonyme synthétique"), (True, "Nom confidentiel"), (True, None)]
)
def public_pages(request, monkeypatch):
    from app.app import app
    from app.routers import answers, authors, search, seo

    anonymous, name = request.param
    author = {"id": 42, "name": name, "is_anonymous": anonymous, "answers_count": 23}
    now = datetime(2019, 3, 1)
    rows = [
        {
            "answer_id": i,
            "answer_text": f"Réponse synthétique {i}. " + "La culture pour tous. " * 5,
            "question_id": 7,
            "question_prompt": "Quelle culture ?",
            "author_id": 42,
            "author_name": name,
            "author_is_anonymous": anonymous,
            "submitted_at": now,
        }
        for i in range(23, 0, -1)
    ]
    calls = []

    class Result:
        def __init__(self, rows=(), scalar=None):
            self.rows = list(rows)
            self.value = scalar

        def mappings(self):
            return self

        def first(self):
            return self.rows[0] if self.rows else None

        def all(self):
            return self.rows

        def scalar(self):
            return self.value

        def scalar_one(self):
            return self.value

        def __iter__(self):
            return iter(self.rows)

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query, params=None):
            sql = str(query)
            params = params or {}
            calls.append((sql, params))
            if sql.startswith("SET LOCAL"):
                return Result()
            if "MAX(submitted_at)" in sql:
                return Result(scalar=now)
            if "MAX(c.submitted_at)" in sql:
                return Result([dict(author, lastmod=now)]) if "authors au" in sql else Result()
            if "JOIN question_stats" in sql:
                return Result()
            if "FROM authors" in sql and "JOIN authors" not in sql:
                return Result([author])
            if "COUNT(1)" in sql:
                return Result(scalar=23)
            if "WHERE a.id = :aid" in sql:
                return Result([rows[0]])
            if "FROM answers" in sql:
                selected = [r for r in rows if r["answer_id"] < params.get("last_id", 24)]
                offset = params.get("offset", 0)
                return Result(selected[offset : offset + params["limit"]])
            raise AssertionError(f"Unexpected query: {sql}")

    for module in (answers, search, seo):
        monkeypatch.setattr(module, "SessionLocal", Session)
    app.dependency_overrides[authors.get_db] = Session
    try:
        with TestClient(app) as client:
            yield client, author, calls
    finally:
        app.dependency_overrides.pop(authors.get_db)


def jsonld(response):
    return [
        json.loads(value)
        for value in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', response.text, re.DOTALL
        )
    ]


def test_public_identity_in_pages_metadata_links_and_sitemap(public_pages):
    client, stored, _ = public_pages
    original = stored.copy()
    public = public_author(stored["id"], stored["name"], stored["is_anonymous"])
    path = f"/authors/42-{public['slug']}"
    author_page = client.get(path)
    assert author_page.status_code == 200
    assert f'<h1 class="h1">{public["name"]}</h1>' in author_page.text
    assert f'/authors/42-{public["slug"]}"' in author_page.text  # canonical
    assert public["name"] in author_page.text.split("</head>")[0]  # title and metadata
    assert jsonld(author_page)[0]["about"]["name"] == public["name"]
    assert 'id="answer-23"' in author_page.text
    assert 'id="answer-4"' in author_page.text
    assert 'href="http://testserver/answers/23"' in author_page.text
    assert "openBookmarkModal('author', 42)" in author_page.text
    assert "author-controls" not in author_page.text

    responses = [author_page, client.get("/answers/23"), client.get("/sitemap.xml")]
    for query in ("", "culture"):
        responses.append(client.get("/search/answers", params={"q": query}))
    for response in responses:
        assert response.status_code == 200
        assert public["name"] in response.text or public["slug"] in response.text
        if stored["is_anonymous"] and stored["name"]:
            assert stored["name"] not in response.text
            assert "nom-confidentiel" not in response.text
    assert f"/authors/42-{public['slug']}" in responses[1].text
    assert jsonld(responses[1])[0]["author"]["name"] == public["name"]
    assert stored == original


@pytest.mark.parametrize("method", ["get", "head"])
def test_legacy_and_old_named_slugs_redirect_safely(public_pages, method):
    client, stored, _ = public_pages
    public = public_author(42, stored["name"], stored["is_anonymous"])
    for path in ("/authors/42", "/authors/42-nom-confidentiel"):
        response = getattr(client, method)(
            path, params={"q": "culture & écoles", "page": 2}, follow_redirects=False
        )
        assert response.status_code == 308
        target = urlsplit(response.headers["location"])
        assert target.path == f"/authors/42-{public['slug']}"
        assert parse_qs(target.query) == {"q": ["culture & écoles"], "page": ["2"]}
        assert "nom-confidentiel" not in response.headers["location"]
    assert client.head(f"/authors/42-{public['slug']}").status_code == 200


def test_author_pagination_and_search_contract_are_preserved(public_pages):
    client, stored, calls = public_pages
    slug = public_author(42, stored["name"], stored["is_anonymous"])["slug"]
    page = client.get(f"/authors/42-{slug}", params={"page": 2})
    assert page.status_code == 200
    assert re.findall(r'id="answer-(\d+)"', page.text) == ["3", "2", "1"]
    # Exercise the existing filter with a stub, not a replacement SQL implementation.
    filtered = client.get(f"/authors/42-{slug}", params={"q": "culture", "page": 2})
    assert filtered.status_code == 200
    assert re.findall(r'id="answer-(\d+)"', filtered.text) == ["3", "2", "1"]
    assert any("answers_fts MATCH :q" in sql and params["q"] == "culture" for sql, params in calls)
    assert any("bm25(answers_fts)" in sql and params["offset"] == 20 for sql, params in calls)


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


def test_bookmarks_use_public_identity_without_mutating_the_author(public_pages, monkeypatch):
    from app.app import app
    from app.models import Answer, Author, Bookmark, Contribution, Question
    from app.routers import bookmarks

    client, stored, _ = public_pages
    author = Author(id=42, name=stored["name"], is_anonymous=stored["is_anonymous"])
    answer = Answer(id=23, text="Réponse synthétique", contribution_id=1, question_id=7)
    answer.question = Question(id=7, prompt="Quelle culture ?")
    contribution = Contribution(id=1, author=author)
    entries = [
        Bookmark(id=i, page_type=kind, page_id=page_id, created_at=datetime(2019, 3, 1))
        for i, kind, page_id in ((1, "author", 42), (2, "answer", 23))
    ]

    class Result:
        def __init__(self, value):
            self.value = value

        def scalars(self):
            return self

        def all(self):
            return self.value

        def scalar_one_or_none(self):
            return self.value

        def scalar(self):
            return self.value

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, query):
            sql = str(query)
            if "FROM bookmarks" in sql:
                return Result(entries)
            if "count(" in sql:
                return Result(23)
            if "FROM authors" in sql:
                return Result(author)
            if "FROM answers" in sql:
                return Result(answer)
            if "FROM contributions" in sql:
                return Result(contribution)
            raise AssertionError(f"Unexpected query: {sql}")

    monkeypatch.setattr(bookmarks, "SessionLocal", Session)
    app.dependency_overrides[bookmarks.get_current_user] = lambda: SimpleNamespace(id=99)
    try:
        response = client.get("/bookmarks")
        assert response.status_code == 200
        public = public_author(42, author.name, author.is_anonymous)
        assert public["name"] in response.text
        assert "/authors/42" in response.text
        assert "/answers/23" in response.text
        if author.is_anonymous and author.name:
            assert author.name not in response.text
        assert author.name == stored["name"]
        assert author.is_anonymous == stored["is_anonymous"]
        assert [entry.page_id for entry in entries] == [42, 23]
    finally:
        app.dependency_overrides.pop(bookmarks.get_current_user)


@pytest.mark.integration
@pytest.mark.parametrize(
    "anonymous,name", [(False, "Pseudonyme synthétique"), (True, "Nom confidentiel"), (True, None)]
)
def test_public_identity_and_author_bookmarks_on_postgresql(client, web_data, anonymous, name):
    from sqlalchemy import select

    from app.models import Answer, Author, Contribution
    from app.services.auth import auth_service

    with web_data["factory"]() as db:
        author_id = db.execute(
            select(Contribution.author_id)
            .join(Answer, Answer.contribution_id == Contribution.id)
            .where(Answer.id == web_data["text_ids"][0])
        ).scalar_one()
        author = db.get(Author, author_id)
        author.name = name
        author.is_anonymous = anonymous
        db.commit()

    public = public_author(author_id, name, anonymous)
    path = f"/authors/{author_id}-{public['slug']}"
    for url in (
        path,
        f"/answers/{web_data['text_ids'][0]}",
        "/search/answers?q=culture",
        "/sitemap.xml",
    ):
        response = client.get(url)
        assert response.status_code == 200
        if anonymous and name:
            assert name not in response.text
            assert "nom-confidentiel" not in response.text
    old = client.get(f"/authors/{author_id}-nom-confidentiel", follow_redirects=False)
    assert old.status_code == 308
    assert urlsplit(old.headers["location"]).path == path
    assert client.get(f"/authors/{author_id}").status_code == 200
    assert client.get(path, params={"page": 2}).status_code == 200

    login = client.get(
        f"/auth/verify/{auth_service.create_magic_token('anonymity@example.org')}",
        follow_redirects=False,
    )
    assert login.status_code == 302
    assert client.post("/auth/complete-profile", json={"nationalities": ["FR"]}).status_code == 200
    assert client.get("/auth/me").json()["nationalities"] == ["FR"]
    bookmark = f"/bookmarks/author/{author_id}"
    assert client.post(bookmark).json()["success"]
    assert client.get(f"/bookmarks/check/author/{author_id}").json()["is_bookmarked"]
    listing = client.get("/bookmarks")
    assert listing.status_code == 200
    assert public["name"] in listing.text
    if anonymous and name:
        assert name not in listing.text
    assert client.post("/auth/toggle-anonymity", json={"is_anonymous": False}).status_code == 404
    assert client.delete(bookmark).json()["success"]
    with web_data["factory"]() as db:
        author = db.get(Author, author_id)
        assert (author.name, author.is_anonymous) == (name, anonymous)
