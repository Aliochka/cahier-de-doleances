"""Public question API, keyset pagination and parity with the historical statistics."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select, text, update
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.models import Answer, AnswerOption, Author, Contribution, Option, Question
from app.schemas.questions import AnswerDetail, AnswerPage, QuestionDetail, QuestionStatistics


@pytest.mark.integration
@pytest.mark.parametrize(
    "kind",
    ["text", "free_text", "single_choice", "multi_choice", "scale", "number", "date", "future"],
)
def test_question_detail_types_and_public_fields(client, web_data, kind):
    with web_data["factory"]() as db:
        question = Question(
            id=9007199254740993,
            form_id=web_data["form"],
            question_code="internal-code",
            prompt="Question sans réponse ?",
            type=kind,
            position=None,
            options_json='{"internal":true}',
        )
        db.add(question)
        db.commit()
    response = client.get(f"/api/v1/questions/{question.id}", headers={"Accept": "text/html"})
    assert response.status_code == 200
    payload = response.json()
    QuestionDetail.model_validate(payload)
    assert payload["id"] == "9007199254740993"
    assert payload["type"] == kind
    assert payload["position"] is None
    assert payload["display_mode"] == (
        "choice" if kind in {"single_choice", "multi_choice"} else "text"
    )
    assert payload["form"] == {
        "id": str(web_data["form"]),
        "name": "Formulaire de contrôle",
        "url": f"/forms/{web_data['form']}",
    }
    assert payload["url"] == f"/questions/{question.id}-{payload['slug']}"
    assert set(payload) == {
        "id",
        "form_id",
        "prompt",
        "type",
        "position",
        "slug",
        "url",
        "form",
        "display_mode",
    }
    assert "internal" not in response.text
    assert "set-cookie" not in response.headers


@pytest.mark.integration
@pytest.mark.parametrize("null_count", [0, 7, 21, 23])
@pytest.mark.parametrize("page_size", [1, 7, 20, 100])
def test_keyset_pages_are_stable_and_complete(client, web_data, null_count, page_size):
    with web_data["factory"]() as db:
        rows = db.execute(
            select(Answer.id, Answer.contribution_id)
            .where(Answer.id.in_(web_data["text_ids"]))
            .order_by(Answer.id)
        ).all()
        dates = {}
        for index, row in enumerate(rows):
            date = None if index < null_count else datetime(2019, 3, 1) + timedelta(days=index % 3)
            dates[row.id] = date
            db.execute(
                update(Contribution)
                .where(Contribution.id == row.contribution_id)
                .values(submitted_at=date)
            )
        db.commit()
    path = f"/api/v1/questions/{web_data['text_question']}/answers"
    identifiers = []
    cursor = None
    for _ in range(24):
        params = {"page_size": page_size}
        if cursor:
            params["cursor"] = cursor
        response = client.get(path, params=params)
        assert response.status_code == 200
        page = response.json()
        AnswerPage.model_validate(page)
        assert page["page_size"] == page_size
        assert len(page["items"]) <= page_size
        identifiers.extend(int(answer["id"]) for answer in page["items"])
        cursor = page["next_cursor"]
        if not page["has_next"]:
            assert cursor is None
            break
        assert cursor
    expected = sorted(
        dates, key=lambda identifier: (dates[identifier] or datetime.max, identifier), reverse=True
    )
    assert identifiers == expected
    assert len(set(identifiers)) == len(identifiers) == 23
    assert client.get(path).json()["page_size"] == 20


@pytest.mark.integration
def test_text_filters_truncation_bigints_and_answer_detail(client, web_data):
    with web_data["factory"]() as db:
        author = Author(
            id=9007199254740997,
            name="Nom synthétique confidentiel",
            is_anonymous=True,
            email_hash="internal-hash",
        )
        contribution = Contribution(
            id=9007199254740995,
            form_id=web_data["form"],
            author=author,
            submitted_at=None,
            raw_json="private-import",
        )
        answer = Answer(
            id=9007199254740993,
            contribution=contribution,
            question_id=web_data["text_question"],
            text="é" * 20001,
        )
        db.add(answer)
        db.add_all(
            [
                Answer(
                    contribution=contribution,
                    question_id=web_data["text_question"],
                    text=value,
                    position=i + 2,
                )
                for i, value in enumerate([None, "  ", "court"])
            ]
        )
        db.commit()
    page = client.get(
        f"/api/v1/questions/{web_data['text_question']}/answers", params={"page_size": 100}
    ).json()
    assert len(page["items"]) == 24
    item = next(a for a in page["items"] if a["id"] == str(answer.id))
    assert item["contribution_id"] == str(contribution.id)
    assert item["submitted_at"] is None
    assert item["is_truncated"] is True
    assert len(item["text"]) == 20000
    assert item["author"]["id"] == str(author.id)
    assert item["author"]["name"] == f"Auteur #{author.id}"
    assert "confidentiel" not in str(page)
    assert "internal-hash" not in str(page)
    assert "private-import" not in str(page)
    assert set(item) == {
        "id",
        "question_id",
        "contribution_id",
        "text",
        "is_truncated",
        "submitted_at",
        "author",
        "url",
    }
    response = client.get(item["url"].replace("/answers/", "/api/v1/answers/"))
    detail = response.json()
    AnswerDetail.model_validate(detail)
    assert detail["text"] == answer.text
    assert detail["is_truncated"] is False
    assert detail["question"]["id"] == str(web_data["text_question"])
    assert detail["question"]["form_id"] == str(web_data["form"])
    assert "confidentiel" not in response.text
    assert client.get(item["url"]).status_code == 200
    first = client.get(
        f"/api/v1/questions/{web_data['text_question']}/answers", params={"page_size": 1}
    ).json()
    assert first["items"][0]["id"] == "9007199254740993"
    following = client.get(
        f"/api/v1/questions/{web_data['text_question']}/answers",
        params={"page_size": 1, "cursor": first["next_cursor"]},
    ).json()
    assert following["items"][0]["id"] != first["items"][0]["id"]


@pytest.mark.integration
@pytest.mark.parametrize(
    "anonymous,name", [(False, "Pseudonyme public"), (True, "Nom confidentiel"), (True, None)]
)
def test_author_projection_on_list_and_detail(client, web_data, anonymous, name):
    with web_data["factory"]() as db:
        author_id = db.scalar(
            select(Contribution.author_id).join(Answer).where(Answer.id == web_data["text_ids"][0])
        )
        db.execute(
            update(Author).where(Author.id == author_id).values(is_anonymous=anonymous, name=name)
        )
        db.commit()
    payload = client.get(f"/api/v1/questions/{web_data['text_question']}/answers").json()
    detail = client.get(f"/api/v1/answers/{payload['items'][0]['id']}").json()
    for item in [payload["items"][0], detail]:
        assert item["author"]["name"] == (name if not anonymous else f"Auteur #{author_id}")
        assert item["author"]["is_anonymous"] is anonymous
        if anonymous:
            assert "confidentiel" not in str(item)


@pytest.mark.integration
def test_missing_author_and_empty_answers(client, web_data):
    with web_data["factory"]() as db:
        db.execute(update(Contribution).values(author_id=None))
        question = Question(
            form_id=web_data["form"], question_code="empty", prompt="Sans réponses", type="text"
        )
        db.add(question)
        db.commit()
    page = client.get(f"/api/v1/questions/{web_data['text_question']}/answers").json()
    assert all(item["author"] is None for item in page["items"])
    assert client.get(f"/api/v1/answers/{web_data['text_ids'][0]}").json()["author"] is None
    assert client.get(f"/api/v1/questions/{question.id}/answers").json() == {
        "question_id": str(question.id),
        "items": [],
        "page_size": 20,
        "has_next": False,
        "next_cursor": None,
    }


@pytest.mark.integration
def test_multi_stats_other_text_empty_options_and_distinct_contributions(client, web_data):
    with web_data["factory"]() as db:
        source = db.get(Answer, web_data["choice_answer"])
        source.value_json = '{"other_text":["texte synthétique 1","texte synthétique 2"]}'
        duplicate = Answer(
            question_id=web_data["multi"],
            contribution_id=source.contribution_id,
            position=2,
            text="Vélo",
            value_json='{"other_text":[]}',
        )
        unused = Option(
            id=9007199254740993,
            question_id=web_data["multi"],
            label="Option sans sélection",
            code="unused",
            position=None,
        )
        db.add_all([duplicate, unused])
        db.flush()
        db.add(AnswerOption(answer_id=duplicate.id, option_id=web_data["bike"]))
        db.commit()
    api = client.get(f"/api/v1/questions/{web_data['multi']}/stats").json()
    QuestionStatistics.model_validate(api)
    assert api["total_answers"] == 3
    assert api["answered_contributions_count"] == 2
    assert api["total_selections"] == 5
    assert api["total_option_selections"] == 4
    assert api["other_text_answers_count"] == 1
    assert api["percentage_denominator"] == "total_answers"
    assert api["percentage_decimal_places"] == 2
    assert [(c["label"], c["count"], c["percentage"]) for c in api["categories"]] == [
        ("Vélo", 2, 66.67),
        ("Bus", 2, 66.67),
        ("Option sans sélection", 0, 0),
        ("Autre (texte libre)", 1, 33.33),
    ]
    assert api["categories"][2]["option_id"] == "9007199254740993"
    assert api["categories"][-1]["option_id"] is None
    assert api["categories"][-1]["kind"] == "other_text"
    legacy = client.get(f"/questions/{web_data['multi']}/stats").json()
    assert api["total_answers"] == legacy["total_answers"]
    assert api["total_selections"] == legacy["total_selections"]
    assert [(c["label"], c["count"], c["percentage"]) for c in api["categories"]] == [
        (c["label"], c["count"], c["percentage"]) for c in legacy["stats"]
    ]
    assert "Option sans sélection" in client.get(f"/forms/{web_data['form']}/dashboard").text


@pytest.mark.integration
def test_single_choice_percentages_and_empty_statistics(client, web_data):
    with web_data["factory"]() as db:
        question = Question(
            form_id=web_data["form"],
            question_code="single",
            prompt="Choix unique",
            type="single_choice",
        )
        db.add(question)
        db.flush()
        options = [
            Option(
                question_id=question.id,
                code=str(i),
                label=f"Option {i}",
                position=1 if i < 2 else None,
            )
            for i in range(3)
        ]
        db.add_all(options)
        db.commit()
    empty = client.get(f"/api/v1/questions/{question.id}/stats").json()
    assert (
        empty["total_answers"]
        == empty["answered_contributions_count"]
        == empty["total_selections"]
        == 0
    )
    assert [c["option_id"] for c in empty["categories"]] == [str(o.id) for o in options]
    assert all(c["count"] == c["percentage"] == 0 for c in empty["categories"])
    with web_data["factory"]() as db:
        contributions = db.scalars(select(Contribution.id).order_by(Contribution.id).limit(3)).all()
        for i, cid in enumerate(contributions):
            answer = Answer(
                contribution_id=cid,
                question_id=question.id,
                text=f"Option {i % 2}",
                value_json='{"other_text":[]}',
            )
            db.add(answer)
            db.flush()
            db.add(AnswerOption(answer_id=answer.id, option_id=options[i % 2].id))
        db.commit()
    stats = client.get(f"/api/v1/questions/{question.id}/stats").json()
    assert (
        stats["total_answers"]
        == stats["answered_contributions_count"]
        == stats["total_option_selections"]
        == 3
    )
    assert [c["percentage"] for c in stats["categories"]] == [66.67, 33.33, 0]
    assert len(client.get(f"/api/v1/questions/{question.id}/answers").json()["items"]) == 3
    assert client.get(f"/api/v1/questions/{web_data['text_question']}/stats").status_code == 400


@pytest.mark.parametrize("accept", ["text/html", "*/*", "application/json"])
@pytest.mark.parametrize("identifier", ["invalid", "0", "-1", "9223372036854775808"])
def test_invalid_identifiers_are_json_without_database(monkeypatch, accept, identifier):
    from app.app import app
    from app.routers import api_questions

    def forbidden():
        raise AssertionError("Invalid input must not connect")

    monkeypatch.setattr(api_questions, "SessionLocal", forbidden)
    with TestClient(app) as browser:
        for path in [
            f"/questions/{identifier}",
            f"/questions/{identifier}/answers",
            f"/questions/{identifier}/stats",
            f"/answers/{identifier}",
        ]:
            response = browser.get(f"/api/v1{path}", headers={"Accept": accept})
            assert response.status_code == 422
            assert response.headers["content-type"] == "application/json"


@pytest.mark.parametrize(
    "params",
    [
        {"page_size": 0},
        {"page_size": 101},
        {"page_size": "bad"},
        {"cursor": ""},
        {"cursor": "bad!"},
        {"cursor": "x" * 1025},
    ],
)
def test_invalid_pagination_without_database(monkeypatch, params):
    from app.app import app
    from app.routers import api_questions

    monkeypatch.setattr(api_questions, "SessionLocal", lambda: pytest.fail("Unexpected connection"))
    with TestClient(app) as browser:
        assert browser.get("/api/v1/questions/1/answers", params=params).status_code == 422


@pytest.mark.parametrize(
    "value",
    [
        [],
        {},
        {"id": True, "date": None},
        {"id": "1", "date": None},
        {"id": 9223372036854775808, "date": None},
        {"id": 1, "date": "invalid"},
    ],
)
def test_invalid_cursor_shape_without_database(monkeypatch, value):
    from app.app import app
    from app.routers import api_questions
    from app.services.questions import _enc_cursor

    monkeypatch.setattr(api_questions, "SessionLocal", lambda: pytest.fail("Unexpected connection"))
    with TestClient(app) as browser:
        response = browser.get("/api/v1/questions/1/answers", params={"cursor": _enc_cursor(value)})
        assert response.status_code == 422
        assert response.headers["content-type"] == "application/json"
        assert isinstance(response.json()["detail"], list)
        assert response.json()["detail"][0]["loc"] == ["query", "cursor"]


def test_unexpected_errors_do_not_leak(monkeypatch):
    from app.app import app
    from app.routers import api_questions

    def fail():
        raise RuntimeError("private SQL / import / token")

    monkeypatch.setattr(api_questions, "SessionLocal", fail)
    with TestClient(app, raise_server_exceptions=False) as browser:
        for path in ["/questions/1", "/questions/1/answers", "/questions/1/stats", "/answers/1"]:
            response = browser.get(f"/api/v1{path}", headers={"Accept": "text/html"})
            assert response.status_code == 500
            assert response.json() == {"detail": "Internal server error"}


@pytest.mark.integration
def test_missing_resources_and_html_parity(client, web_data):
    for path in [
        "/questions/9223372036854775807",
        "/questions/9223372036854775807/answers",
        "/questions/9223372036854775807/stats",
        "/answers/9223372036854775807",
    ]:
        response = client.get(f"/api/v1{path}", headers={"Accept": "text/html"})
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/json"
    detail = client.get(f"/api/v1/questions/{web_data['text_question']}").json()
    html = client.get(detail["url"])
    assert html.status_code == 200
    assert detail["prompt"] in html.text
    for answer in client.get(f"/api/v1/questions/{detail['id']}/answers").json()["items"]:
        assert f'id="answer-{answer["id"]}"' in html.text
    partial = client.get(f"/questions/{detail['id']}/partials/answers", params={"q": "culture"})
    assert partial.status_code == 200 and "<html" not in partial.text


@pytest.mark.integration
def test_query_budget_no_offset_or_page_count(client, web_data):
    statements = []
    with web_data["factory"]() as db:
        connection = db.get_bind()

        def record(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(connection, "before_cursor_execute", record)
        try:
            for path, expected in [
                (f"/questions/{web_data['text_question']}", 1),
                (f"/questions/{web_data['text_question']}/answers", 2),
                (f"/questions/{web_data['multi']}/stats", 4),
                (f"/answers/{web_data['text_ids'][0]}", 1),
            ]:
                statements.clear()
                assert client.get(f"/api/v1{path}").status_code == 200
                assert len(statements) == expected
                if path.endswith("/answers"):
                    assert all(
                        "OFFSET" not in sql.upper() and "COUNT(" not in sql.upper()
                        for sql in statements
                    )
        finally:
            event.remove(connection, "before_cursor_execute", record)


@pytest.mark.parametrize("accept", ["text/html", "application/json"])
@pytest.mark.parametrize("code,status", [("57014", 504), ("42P01", 500), (None, 503)])
def test_sql_errors_are_safe_json_and_rollback(monkeypatch, accept, code, status):
    from app.app import app
    from app.routers import api_questions

    class Session:
        rolled_back = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute(self, *args):
            error = ProgrammingError if code == "42P01" else OperationalError
            raise error("private SQL", {}, SimpleNamespace(pgcode=code))

        def rollback(self):
            self.rolled_back = True

    session = Session()
    monkeypatch.setattr(api_questions, "SessionLocal", lambda: session)
    with TestClient(app, raise_server_exceptions=False) as browser:
        for path in ["/questions/1", "/questions/1/answers", "/questions/1/stats", "/answers/1"]:
            response = browser.get(
                f"/api/v1{path}", headers={"Accept": accept, "HX-Request": "true"}
            )
            assert response.status_code == status
            assert response.headers["content-type"] == "application/json"
            assert "private" not in response.text
            assert "set-cookie" not in response.headers
            assert session.rolled_back


@pytest.mark.integration
def test_real_postgresql_timeout_recovers_transaction(client, web_data, monkeypatch):
    from app.routers import api_questions

    def expire(db, question_id):
        db.execute(text("SET LOCAL statement_timeout = '1ms'"))
        db.execute(text("SELECT pg_sleep(0.05)"))

    monkeypatch.setattr(api_questions, "existing_question", expire)
    response = client.get(
        f"/api/v1/questions/{web_data['text_question']}", headers={"Accept": "text/html"}
    )
    assert response.status_code == 504
    assert response.headers["content-type"] == "application/json"
    assert "pg_sleep" not in response.text
    with web_data["factory"]() as db:
        assert db.execute(text("SELECT 1")).scalar_one() == 1


@pytest.mark.integration
def test_public_payload_independent_of_cookies(client, web_data):
    for path in [
        f"/questions/{web_data['text_question']}",
        f"/questions/{web_data['text_question']}/answers",
        f"/questions/{web_data['multi']}/stats",
        f"/answers/{web_data['text_ids'][0]}",
    ]:
        public = client.get(f"/api/v1{path}")
        session = client.get(f"/api/v1{path}", headers={"Cookie": "session_token=invalid"})
        assert session.json() == public.json()
        assert session.headers["cache-control"] == "private, no-store"
        assert "set-cookie" not in session.headers


def test_api_route_names_preserve_historical_reverse_urls():
    from app.app import app

    assert (
        str(app.url_path_for("question_detail", question_id=1, slug="question"))
        == "/questions/1-question"
    )
    assert str(app.url_path_for("answer_detail", answer_id=1)) == "/answers/1"
    assert (
        str(app.url_path_for("api_question_detail", question_id="9007199254740993"))
        == "/api/v1/questions/9007199254740993"
    )
    assert (
        str(app.url_path_for("api_answer_detail", answer_id="9007199254740993"))
        == "/api/v1/answers/9007199254740993"
    )
