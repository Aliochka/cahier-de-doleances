"""Public form contract and parity with the historical HTML views."""

import warnings

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.schemas.forms import FormDetail, FormSummary


@pytest.mark.integration
def test_list_detail_and_html_parity(client, web_data):
    from app.models import Form, Question

    with web_data["factory"]() as db:
        empty = Form(id=9007199254740993, name="Sans questions", source="internal")
        db.add(empty)
        db.flush()
        single = Question(
            form_id=web_data["form"],
            question_code="unique",
            prompt="Choix unique ?",
            type="single_choice",
            position=0,
        )
        late = Question(
            form_id=web_data["form"],
            question_code="late",
            prompt="Sans position ?",
            type="text",
            position=None,
        )
        db.execute(
            text("UPDATE questions SET position=2 WHERE id=:id"), {"id": web_data["text_question"]}
        )
        db.add_all([single, late])
        db.commit()
        single_id, late_id = single.id, late.id

    listing = client.get("/api/v1/forms", headers={"Accept": "text/html"})
    assert listing.status_code == 200
    rows = listing.json()
    assert [int(row["id"]) for row in rows] == sorted(int(row["id"]) for row in rows)
    with web_data["factory"]() as db:
        assert len(rows) == db.execute(text("SELECT count(*) FROM forms")).scalar_one()
    assert next(row for row in rows if row["id"] == str(empty.id))["questions_count"] == 0
    for row in rows:
        assert set(row) == {"id", "name", "questions_count", "url"}
        FormSummary.model_validate(row)
    assert "set-cookie" not in listing.headers

    detail = client.get(f"/api/v1/forms/{web_data['form']}").json()
    FormDetail.model_validate(detail)
    assert detail["questions_count"] == 4
    assert [q["id"] for q in detail["questions"]] == [
        str(single_id),
        str(web_data["text_question"]),
        str(web_data["multi"]),
        str(late_id),
    ]
    assert [q["type"] for q in detail["questions"]] == [
        "single_choice",
        "text",
        "multi_choice",
        "text",
    ]
    assert detail["questions"][-1]["position"] is None
    for question in detail["questions"]:
        assert set(question) == {
            "id",
            "form_id",
            "prompt",
            "type",
            "position",
            "slug",
            "url",
            "answers_count",
            "statistics",
        }
        assert question["form_id"] == str(web_data["form"])
        assert question["url"] == f"/questions/{question['id']}-{question['slug']}"
    assert client.get(f"/api/v1/forms/{empty.id}").json()["questions"] == []


@pytest.mark.integration
@pytest.mark.parametrize("accept", ["text/html", "*/*", "application/json"])
def test_errors_are_json(client, accept):
    for identifier, status in [
        ("9223372036854775807", 404),
        ("invalid", 422),
        ("0", 422),
        ("9223372036854775808", 422),
    ]:
        response = client.get(f"/api/v1/forms/{identifier}", headers={"Accept": accept})
        assert response.status_code == status
        assert response.headers["content-type"] == "application/json"
        assert "detail" in response.json()


@pytest.mark.integration
def test_query_budget(client, web_data):
    statements = []
    with web_data["factory"]() as db:
        connection = db.get_bind()

        def record(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(connection, "before_cursor_execute", record)
        try:
            assert client.get("/api/v1/forms").status_code == 200
            assert len(statements) == 1
            statements.clear()
            assert client.get(f"/api/v1/forms/{web_data['form']}").status_code == 200
            assert len(statements) == 3
            assert all(
                "FROM contributions" not in sql and "FROM answers" not in sql for sql in statements
            )
        finally:
            event.remove(connection, "before_cursor_execute", record)


@pytest.mark.integration
def test_empty_listing(client, web_data):
    with web_data["factory"]() as db:
        for table in (
            "answer_options",
            "answers",
            "contribution_topics",
            "contributions",
            "options",
            "question_stats",
            "questions",
            "forms",
        ):
            db.execute(text(f"DELETE FROM {table}"))
        db.commit()
    assert client.get("/api/v1/forms").json() == []


def test_openapi_operation_ids():
    from app.app import app

    app.openapi_schema = None
    with warnings.catch_warnings(record=True) as caught:
        schema = app.openapi()
    operations = [
        schema["paths"][path]["get"]["operationId"]
        for path in ["/api/v1/forms", "/api/v1/forms/{form_id}"]
    ]
    assert operations == ["list_public_forms", "get_public_form"]
    all_ids = [
        operation["operationId"]
        for path in schema["paths"].values()
        for method, operation in path.items()
        if method in {"get", "post", "delete", "put", "patch"}
    ]
    for identifier in operations:
        assert all_ids.count(identifier) == 1
        assert not any(identifier in str(w.message) for w in caught)
    assert schema["components"]["schemas"]["FormSummary"]["properties"]["id"]["type"] == "string"
    assert schema["components"]["schemas"]["FormQuestion"]["properties"]["position"]["anyOf"] == [
        {"type": "integer"},
        {"type": "null"},
    ]


@pytest.mark.parametrize("accept", ["text/html", "*/*", "application/json"])
@pytest.mark.parametrize(
    "error,status",
    [
        (OperationalError("private SQL", {}, Exception("private host")), 503),
        (ProgrammingError("private SQL", {}, Exception("private schema")), 500),
        (RuntimeError("private token"), 500),
    ],
)
def test_database_and_unexpected_errors(monkeypatch, accept, error, status):
    from app.app import app
    from app.routers import api_forms

    def fail():
        raise error

    monkeypatch.setattr(api_forms, "SessionLocal", fail)
    with TestClient(app, raise_server_exceptions=False) as browser:
        response = browser.get("/api/v1/forms", headers={"Accept": accept})
    assert response.status_code == status
    assert response.headers["content-type"] == "application/json"
    assert "private" not in response.text
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("accept", ["text/html", "*/*", "application/json"])
def test_http_timeout_stays_json(monkeypatch, accept):
    import asyncio
    import json

    from starlette.requests import Request

    from app.app import TimeoutMiddleware

    async def expired(awaitable, timeout):
        awaitable.close()
        raise asyncio.TimeoutError

    async def next_response(request):
        raise AssertionError("The forced timeout must prevent this call")

    monkeypatch.setattr(asyncio, "wait_for", expired)
    request = Request(
        {"type": "http", "path": "/api/v1/forms", "headers": [(b"accept", accept.encode())]}
    )
    response = asyncio.run(TimeoutMiddleware(None).dispatch(request, next_response))
    assert response.status_code == 408
    assert response.media_type == "application/json"
    assert json.loads(response.body) == {"detail": "Request timeout"}


@pytest.mark.integration
def test_public_payload_does_not_depend_on_session_cookie(client):
    public = client.get("/api/v1/forms")
    with_cookie = client.get(
        "/api/v1/forms", headers={"Cookie": "session_token=invalid", "Accept": "text/html"}
    )
    assert public.json() == with_cookie.json()
    assert "set-cookie" not in with_cookie.headers
    # Preserve API-003's conservative policy for any request carrying a session.
    assert with_cookie.headers["cache-control"] == "private, no-store"
    assert (
        client.get("/api/v1/missing", headers={"Accept": "text/html"}).headers["content-type"]
        == "application/json"
    )
