"""API-002 regressions; database cases require the existing isolated test fixture."""

import html
import re
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.helpers import slugify


def answer_ids(response):
    return [int(value) for value in re.findall(r'id="answer-(\d+)"', response.text)]


@pytest.fixture
def question_client(monkeypatch):
    from app.app import app
    from app.routers import questions

    rows = [
        {
            "answer_id": i,
            "answer_text": "La culture et les bibliothèques pour tous. " * 3,
            "author_id": 42,
            "submitted_at": None if i > 23 else datetime(2019, 3, 1),
        }
        for i in range(49, 0, -1)
    ]

    class Result:
        def __init__(self, value):
            self.value = value

        def mappings(self):
            return self

        def first(self):
            return self.value

        def scalar_one(self):
            return self.value

        def all(self):
            return self.value

    class Session:
        def execute(self, query, params):
            sql = str(query)
            if "FROM questions WHERE" in sql:
                if params["qid"] != 7:
                    return Result(None)
                return Result({"id": 7, "prompt": "Quelle culture ?", "type": "text"})
            if "COUNT(1)" in sql:
                return Result(len(rows))
            assert "ORDER BY c.submitted_at DESC NULLS FIRST, a.id DESC" in sql
            selected = rows
            if "last_date" in params:
                date = datetime.fromisoformat(params["last_date"])
                selected = [
                    row
                    for row in rows
                    if row["submitted_at"] is not None
                    and (
                        row["submitted_at"] < date
                        or (row["submitted_at"] == date and row["answer_id"] < params["last_id"])
                    )
                ]
            elif "last_id" in params:
                assert "c.submitted_at IS NULL AND a.id < :last_id" in sql
                assert "OR c.submitted_at IS NOT NULL" in sql
                selected = [
                    row
                    for row in rows
                    if row["submitted_at"] is not None or row["answer_id"] < params["last_id"]
                ]
            return Result(selected[: params["limit"]])

    app.dependency_overrides[questions.get_db] = Session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(questions.get_db)


def test_question_pagination_crosses_null_dates_without_duplicates(question_client):
    url = "/questions/7-quelle-culture"
    collected = []
    for _ in range(3):
        response = question_client.get(url)
        assert response.status_code == 200
        collected.extend(answer_ids(response))
        links = re.findall(r'hx-get="([^"]*cursor=[^"]+)"', response.text)
        if not links:
            break
        url = html.unescape(links[0])
    assert collected == list(range(49, 0, -1))
    assert len(collected) == len(set(collected))


@pytest.mark.parametrize("method", ["get", "head"])
@pytest.mark.parametrize("path", ["/questions/7", "/questions/7-old-slug"])
def test_question_redirects_preserve_encoded_query_and_cursor(question_client, method, path):
    from app.routers.questions import _enc_cursor

    params = {
        "q": "culture & écoles + musées",
        "cursor": _enc_cursor({"id": 30, "date": None}),
        "partial": "1",
        "page": "2",
    }
    response = getattr(question_client, method)(path, params=params, follow_redirects=False)
    assert response.status_code == 308
    target = urlsplit(response.headers["location"])
    assert target.path == "/questions/7-quelle-culture"
    assert parse_qs(target.query) == {key: [value] for key, value in params.items()}


def test_old_question_partial_returns_real_answers_and_next_cursor(question_client):
    url = "/questions/7/partials/answers"
    first = question_client.get(url, params={"q": "culture"})
    assert first.status_code == 200
    assert "<html" not in first.text
    assert answer_ids(first) == list(range(49, 29, -1))
    next_url = html.unescape(re.search(r'hx-get="([^"]+)"', first.text)[1])
    cursor = parse_qs(urlsplit(next_url).query)["cursor"][0]
    second = question_client.get(url, params={"q": "culture", "cursor": cursor})
    assert second.status_code == 200
    assert answer_ids(second) == list(range(29, 9, -1))
    assert set(answer_ids(first)).isdisjoint(answer_ids(second))


@pytest.mark.parametrize(
    "value",
    [
        [],
        {},
        {"id": "bad", "date": None},
        {"id": True, "date": None},
        {"id": 1, "date": "bad"},
        {"id": 1, "date": []},
    ],
)
def test_invalid_question_cursor_returns_400(question_client, value):
    from app.routers.questions import _enc_cursor

    for path in ("/questions/7-quelle-culture", "/questions/7/partials/answers"):
        response = question_client.get(path, params={"cursor": _enc_cursor(value)})
        assert response.status_code == 400


@pytest.mark.parametrize("cursor", ["not-base64!", "x" * 1025])
def test_malformed_question_cursor_returns_400(question_client, cursor):
    response = question_client.get("/questions/7-quelle-culture", params={"cursor": cursor})
    assert response.status_code == 400


def test_old_question_partial_missing_question_returns_404(question_client):
    assert question_client.get("/questions/999/partials/answers").status_code == 404


@pytest.mark.integration
@pytest.mark.parametrize("null_count", [0, 7, 21, 23])
def test_question_null_date_pagination_on_postgresql(client, web_data, null_count):
    from sqlalchemy import select, update

    from app.models import Answer, Contribution

    with web_data["factory"]() as db:
        ids = db.scalars(
            select(Answer.contribution_id).where(Answer.id.in_(web_data["text_ids"][:null_count]))
        ).all()
        db.execute(update(Contribution).where(Contribution.id.in_(ids)).values(submitted_at=None))
        db.commit()
    first = client.get(f"/questions/{web_data['text_question']}")
    assert first.status_code == 200
    link = html.unescape(re.search(r'hx-get="([^"]*cursor=[^"]+)"', first.text)[1])
    second = client.get(link)
    assert second.status_code == 200
    ids = answer_ids(first) + answer_ids(second)
    assert len(ids) == len(set(ids)) == 23
    assert set(ids) == set(web_data["text_ids"])
    partial = client.get(f"/questions/{web_data['text_question']}/partials/answers")
    assert answer_ids(partial) == answer_ids(first)


@pytest.mark.integration
def test_author_lists_all_answers_ignores_q_and_has_stable_pages(client, web_data):
    from sqlalchemy import select

    from app.models import Answer, Contribution

    with web_data["factory"]() as db:
        author_id = db.scalar(
            select(Contribution.author_id).join(Answer).where(Answer.id == web_data["text_ids"][0])
        )
        expected = sorted(
            db.scalars(
                select(Answer.id).join(Contribution).where(Contribution.author_id == author_id)
            ).all(),
            reverse=True,
        )
    path = f"/authors/{author_id}-{slugify(f'Auteur #{author_id}')}"
    first = client.get(path)
    old_search = client.get(path, params={"q": "absent"})
    assert answer_ids(first) == answer_ids(old_search) == expected[:20]
    assert "Filtré par" not in old_search.text
    assert "&amp;q=" not in old_search.text
    next_url = html.unescape(re.search(r'href="([^"]+)"[^>]*rel="next"', first.text)[1])
    second = client.get(next_url)
    assert answer_ids(second) == expected[20:]
    assert client.get(f"/authors/{author_id}", params={"q": "absent", "page": 2}).status_code == 200
