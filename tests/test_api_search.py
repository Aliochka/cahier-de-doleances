"""Search parity, keysets, public associations and bounded SQL on synthetic PostgreSQL data."""

import pytest

from app.schemas.search import AnswerSearchPage, CatalogSearchPage
from app.services.search import read_catalog_search


@pytest.fixture
def search_data(web_data):
    from app.models import Answer, Author, Contribution, Form, Question

    with web_data["factory"]() as db:
        authors = [
            Author(
                id=9007199254746100,
                name="Pseudonyme public",
                is_anonymous=False,
                email_hash="private-email",
                city="private-city",
            ),
            Author(id=9007199254746101, name="Nom privé", is_anonymous=True),
        ]
        db.add_all(authors)
        forms = [
            Form(
                id=9007199254746200 + i,
                name="Écologie et bibliothèque"
                if i < 4
                else "Bibliothèque écologie écologie écologie",
                source=f"synthetic-search-{i}",
            )
            for i in range(5)
        ]
        db.add_all(forms)
        db.flush()
        questions = [
            Question(
                id=1900000100 + i,
                question_code=f"Q{i}",
                form_id=forms[i % 5].id,
                prompt="Écologie et bibliothèque"
                if i < 4
                else "Bibliothèque écologie écologie écologie",
                type="text",
                position=i,
            )
            for i in range(5)
        ]
        # High question IDs work without answer stats (the old INTEGER stats limitation).
        big_question = Question(
            id=9007199254746300,
            question_code="QBIG",
            form_id=forms[0].id,
            prompt="Écologie et bibliothèque",
            type="single_choice",
            position=None,
        )
        db.add_all([*questions, big_question])
        db.flush()
        ids = []
        for index in range(25):
            c = Contribution(
                id=9007199254746400 + index,
                form_id=forms[0].id,
                author_id=authors[index % 2].id if index % 3 else None,
                raw_hash=f"synthetic-search-{index}",
                raw_json='{"private":"internal"}',
            )
            db.add(c)
            db.flush()
            body = (
                "Écologie et bibliothèque : il faut protéger la nature et rendre la culture accessible à tous.\n"
                * (300 if index == 24 else 2)
            )
            a = Answer(
                id=9007199254746500 + index,
                contribution_id=c.id,
                question_id=questions[0].id,
                position=1,
                text=body + "<script>source()</script>",
            )
            db.add(a)
            ids.append(a.id)
        short_c = Contribution(id=9007199254746450, form_id=forms[0].id)
        db.add(short_c)
        db.flush()
        db.add(
            Answer(
                id=9007199254746550,
                contribution_id=short_c.id,
                question_id=questions[0].id,
                text="Écologie",
            )
        )
        # Invalid association is excluded only by JSON; HTML retains historical filters.
        foreign_c = Contribution(id=9007199254746451, form_id=forms[1].id)
        db.add(foreign_c)
        db.flush()
        db.add(
            Answer(
                id=9007199254746551,
                contribution_id=foreign_c.id,
                question_id=questions[0].id,
                text="Écologie et bibliothèque " * 6,
            )
        )
        db.commit()
    return {
        "ids": [str(i) for i in reversed(ids)],
        "form": str(forms[0].id),
        "author": str(authors[0].id),
        "questions": [str(q.id) for q in questions],
        "big_question": str(big_question.id),
        "factory": web_data["factory"],
    }


@pytest.mark.integration
@pytest.mark.parametrize(
    "term",
    [
        "écologie",
        "ECOLOGIE",
        "ecologie",
        "écologie bibliothèque",
        '"écologie et bibliothèque"',
        "ecologie -inexistant",
        "ecologie OR inexistant",
        "ecologie! ; ' --",
    ],
)
def test_answer_terms_case_accents_operators_and_public_fields(client, search_data, term):
    response = client.get(
        "/api/v1/search/answers",
        params={"q": term, "page_size": 100},
        headers={"Accept": "text/html"},
    )
    assert response.status_code == 200
    result = response.json()
    AnswerSearchPage.model_validate(result)
    assert [item["id"] for item in result["items"]] == search_data["ids"]
    assert result["has_next"] is False and result["next_cursor"] is None
    for item in result["items"]:
        assert item["form"]["id"] == item["question"]["form_id"] == search_data["form"]
        assert (
            item["url"]
            == f"/forms/{search_data['form']}/contributions/{item['contribution_id']}#answer-{item['id']}"
        )
        assert len(item["text"]) <= 1000
        assert "<mark>" not in item["text"]
        if item["author"] and item["author"]["is_anonymous"]:
            assert item["author"]["name"].startswith("Auteur #")
    assert result["items"][0]["is_truncated"] is True
    assert (
        "Nom privé" not in response.text
        and "private" not in response.text
        and "raw_json" not in response.text
    )
    assert any(item["author"] is None for item in result["items"])
    assert any(
        item["author"] and item["author"]["name"] == "Pseudonyme public" for item in result["items"]
    )
    assert all(item["submitted_at"] is None for item in result["items"])


@pytest.mark.integration
def test_answer_pagination_preserves_id_order_without_duplicates(client, search_data):
    ids, cursor = [], None
    for _ in range(30):
        result = client.get(
            "/api/v1/search/answers",
            params={"q": "ecologie", "page_size": 4, **({"cursor": cursor} if cursor else {})},
        ).json()
        ids.extend(item["id"] for item in result["items"])
        cursor = result["next_cursor"]
        if not result["has_next"]:
            assert cursor is None
            break
    assert ids == search_data["ids"] and len(ids) == len(set(ids))
    absent = client.get("/api/v1/search/answers", params={"q": "introuvablezzzz"})
    assert absent.status_code == 200 and absent.json()["items"] == []


@pytest.mark.integration
@pytest.mark.parametrize("term", ["ecologie", "ÉCOLOGIE", "écologie bibliothèque"])
def test_catalog_score_id_pagination_matches_historical_service(client, search_data, term):
    with search_data["factory"]() as db:
        all_forms, all_questions, *_ = read_catalog_search(db, term, None, None, page_size=100)
    expected_forms = [str(r["id"]) for r in all_forms]
    expected_questions = [str(r["id"]) for r in all_questions]
    assert len(expected_forms) == 5 and len(expected_questions) == 6
    for rows in (all_forms, all_questions):
        assert [(r["score"], r["id"]) for r in rows] == sorted(
            [(r["score"], r["id"]) for r in rows], reverse=True
        )
        assert len({r["score"] for r in rows}) > 1
    for section, expected in [("forms", expected_forms), ("questions", expected_questions)]:
        result_ids, cursor = [], None
        for _ in range(10):
            response = client.get(
                "/api/v1/search/catalog",
                params={
                    "q": term,
                    "section": section,
                    "page_size": 2,
                    **({f"cursor_{section}": cursor} if cursor else {}),
                },
            )
            assert response.status_code == 200
            data = response.json()
            CatalogSearchPage.model_validate(data)
            result_ids.extend(item["id"] for item in data[section])
            assert data["questions" if section == "forms" else "forms"] == []
            for item in data[section]:
                assert item["kind"] == ("form" if section == "forms" else "question")
                if section == "questions":
                    assert item["form"]["id"] == item["form_id"]
                    assert item["url"] == f"/questions/{item['id']}-{item['slug']}"
                else:
                    assert item["url"] == f"/forms/{item['id']}"
            cursor = data[f"next_cursor_{section}"]
            if not data[f"has_next_{section}"]:
                assert cursor is None
                break
        assert result_ids == expected and len(result_ids) == len(set(result_ids))
    absent = client.get("/api/v1/search/catalog", params={"q": "introuvablezzzz"}).json()
    assert absent["forms"] == absent["questions"] == []


@pytest.mark.parametrize("endpoint,queries", [("answers", ["", " ", "x"]), ("catalog", ["", " "])])
def test_empty_and_short_queries_do_not_open_database(monkeypatch, endpoint, queries):
    from fastapi.testclient import TestClient

    from app.app import app
    from app.routers import api_search

    def forbidden():
        raise AssertionError("Empty search must not open a database session")

    monkeypatch.setattr(api_search, "SessionLocal", forbidden)
    with TestClient(app) as client:
        for q in queries:
            response = client.get(f"/api/v1/search/{endpoint}", params={"q": q})
            assert response.status_code == 200
            data = response.json()
            assert data.get("items", []) == data.get("forms", []) == data.get("questions", []) == []


@pytest.mark.parametrize("endpoint", ["answers", "catalog"])
@pytest.mark.parametrize(
    "params", [{"q": "x" * 513}, {"page_size": 0}, {"page_size": 101}, {"page_size": "abc"}]
)
def test_invalid_parameters_are_422(endpoint, params):
    from fastapi.testclient import TestClient

    from app.app import app

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/search/{endpoint}",
            params={"q": "culture", **params},
            headers={"Accept": "text/html", "HX-Request": "true"},
        )
    assert response.status_code == 422 and response.headers["content-type"].startswith(
        "application/json"
    )


@pytest.mark.parametrize(
    "endpoint,param,values",
    [
        (
            "answers",
            "cursor",
            [
                "",
                "!",
                "a" * 1025,
                [],
                {"id": "1"},
                {"id": True},
                {"id": 0},
                {"id": 9223372036854775808},
                {"id": 1, "score": 0},
            ],
        ),
        (
            "catalog",
            "cursor_forms",
            [
                "!",
                {"id": 1},
                {"id": 1, "score": float("nan")},
                {"id": 1, "score": float("inf")},
                {"id": 1, "score": -1},
                {"id": 1, "score": 1e39},
                {"id": 1, "score": True},
                {"id": 1, "score": "0"},
            ],
        ),
        ("catalog", "cursor_questions", ["!", {"id": "1", "score": 0}]),
    ],
)
def test_invalid_cursors_are_json_422(endpoint, param, values):
    from fastapi.testclient import TestClient

    from app.app import app
    from app.services.search import _enc_cursor

    with TestClient(app) as client:
        for value in values:
            cursor = value if isinstance(value, str) else _enc_cursor(value)
            response = client.get(
                f"/api/v1/search/{endpoint}", params={"q": "culture", param: cursor}
            )
            assert response.status_code == 422
            assert response.headers["content-type"].startswith("application/json")
        assert (
            client.get("/api/v1/search/catalog", params={"section": "invalid"}).status_code == 422
        )


@pytest.mark.integration
def test_sql_budgets_no_count_and_indexed_plan(client, search_data):
    from sqlalchemy import event, text

    with search_data["factory"]() as db:
        connection = db.get_bind()
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith(("SELECT", "WITH")):
            statements.append((statement, parameters))

    event.listen(connection, "before_cursor_execute", record)
    query_for_plan = None
    try:
        for path, params, budget in [
            ("answers", {"q": "ecologie", "page_size": 2}, 1),
            ("catalog", {"q": "ecologie", "page_size": 2}, 2),
            ("catalog", {"q": "ecologie", "section": "forms"}, 1),
            ("catalog", {"q": "ecologie", "section": "questions"}, 1),
        ]:
            statements.clear()
            response = client.get(f"/api/v1/search/{path}", params=params)
            assert response.status_code == 200 and len(statements) == budget
            assert all("OFFSET" not in sql.upper() for sql, _ in statements)
            if path == "answers":
                assert "COUNT(" not in statements[0][0].upper()
                assert "LIMIT 1789" in statements[0][0]
                query_for_plan = statements[0]
            else:
                assert all("FROM answers" not in sql for sql, _ in statements)
            private = client.get(
                f"/api/v1/search/{path}",
                params=params,
                headers={"Cookie": "session_token=synthetic"},
            )
            assert private.json() == response.json()
            assert private.headers["cache-control"] == "private, no-store"
            assert "set-cookie" not in private.headers
    finally:
        event.remove(connection, "before_cursor_execute", record)
    with search_data["factory"]() as db:
        sql, params = query_for_plan
        db.execute(text("SET LOCAL enable_seqscan = false"))
        plan = (
            db.connection()
            .exec_driver_sql("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql, params)
            .scalar_one()[0]
        )

    def nodes(node):
        return [
            node,
            *[descendant for child in node.get("Plans", []) for descendant in nodes(child)],
        ]

    indexes = [n.get("Index Name") for n in nodes(plan["Plan"]) if "Index Name" in n]
    assert indexes
    assert plan["Plan"]["Actual Rows"] <= 3
    print({"synthetic_search_execution_ms": plan["Execution Time"], "indexes": indexes})


@pytest.mark.integration
def test_historical_candidate_cap_is_preserved(client, search_data):
    from sqlalchemy import text

    with search_data["factory"]() as db:
        db.execute(
            text("""
            INSERT INTO answers(id, contribution_id, question_id, position, text)
            SELECT 9007199254747000+g, 9007199254746400, 1900000100, g+100,
                   repeat('Zebracivique protège les initiatives publiques et les citoyens. ', 2)
            FROM generate_series(0,1794) g
        """)
        )
        db.commit()
    ids, cursor = [], None
    for _ in range(20):
        response = client.get(
            "/api/v1/search/answers",
            params={
                "q": "zebracivique",
                "page_size": 100,
                **({"cursor": cursor} if cursor else {}),
            },
        )
        assert response.status_code == 200
        payload = response.json()
        ids.extend(item["id"] for item in payload["items"])
        cursor = payload["next_cursor"]
        if not payload["has_next"]:
            break
    assert ids == [str(9007199254747000 + g) for g in range(1794, 5, -1)]
    assert len(ids) == len(set(ids)) == 1789


@pytest.mark.parametrize("code,status", [("57014", 504), ("42P01", 500), (None, 503)])
@pytest.mark.parametrize("endpoint", ["answers", "catalog"])
def test_sql_errors_and_rollback_are_json(monkeypatch, code, status, endpoint):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient
    from sqlalchemy.exc import OperationalError, ProgrammingError

    from app.app import app
    from app.routers import api_search

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
    monkeypatch.setattr(api_search, "SessionLocal", lambda: session)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(
            f"/api/v1/search/{endpoint}",
            params={"q": "culture"},
            headers={"Accept": "text/html", "HX-Request": "true"},
        )
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/json")
    assert "private SQL" not in response.text
    assert session.rolled_back


@pytest.mark.integration
def test_real_postgresql_timeout_rolls_back(client, web_data, monkeypatch):
    from sqlalchemy import text

    from app.routers import api_search

    def slow(db, *args, **kwargs):
        db.execute(text("SET LOCAL statement_timeout = '1'"))
        db.execute(text("SELECT pg_sleep(0.05)"))
        raise AssertionError("PostgreSQL should cancel the query")

    monkeypatch.setattr(api_search, "read_answer_search", slow)
    response = client.get("/api/v1/search/answers", params={"q": "culture"})
    assert response.status_code == 504
    with web_data["factory"]() as db:
        assert db.execute(text("SELECT 1")).scalar_one() == 1


def test_search_openapi_models_and_ids(tmp_path):
    import json

    from tests.test_openapi_export import run_export

    output = tmp_path / "schema.json"
    result = run_export("--output", output)
    assert result.returncode == 0, result.stderr
    schema = json.loads(output.read_text())
    for path in ("/api/v1/search/answers", "/api/v1/search/catalog"):
        operation = schema["paths"][path]["get"]
        assert {"200", "422", "500", "503", "504"} <= set(operation["responses"])
        parameters = {p["name"]: p["schema"] for p in operation["parameters"]}
        assert parameters["q"]["type"] == "string" and parameters["q"]["maxLength"] == 512
        assert parameters["page_size"]["maximum"] == 100
    for model in ("SearchAnswer", "CatalogForm", "CatalogQuestion"):
        assert schema["components"]["schemas"][model]["properties"]["id"]["type"] == "string"


@pytest.mark.integration
def test_results_resolve_to_full_contributions_and_plain_catalog_syntax(client, search_data):
    result = client.get("/api/v1/search/answers", params={"q": "ecologie -inexistant"}).json()
    assert result["items"]
    item = result["items"][0]
    target = client.get(
        f"/api/v1/forms/{item['form']['id']}/contributions/{item['contribution_id']}"
    )
    assert target.status_code == 200
    complete = next(a for a in target.json()["answers"] if a["id"] == item["id"])
    assert item["text"] == complete["text"][:1000]
    assert all(
        i["author"]["url"] == f"/authors/{i['author']['id']}"
        for i in result["items"]
        if i["author"]
    )
    catalog = client.get("/api/v1/search/catalog", params={"q": "ecologie -inexistant"}).json()
    assert catalog["forms"] == catalog["questions"] == []
