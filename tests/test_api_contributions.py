"""Authors, complete contributions and historical ordinal compatibility."""

import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.schemas.contributions import AuthorFormsPage, ContributionDetail
from app.schemas.questions import PublicAuthor
from app.services.contributions import public_values


@pytest.fixture
def contribution_data(web_data):
    from app.models import Answer, AnswerOption, Author, Contribution, Form, Option, Question

    with web_data["factory"]() as db:
        public = Author(
            id=9007199254745001,
            name="Pseudonyme public",
            is_anonymous=False,
            email_hash="private-hash",
            source_author_id="private-source",
        )
        anonymous = Author(
            id=9007199254745002,
            name="Nom confidentiel de test",
            is_anonymous=True,
            city="private-city",
            age_range="private-age",
        )
        empty = Author(id=9007199254745003, name=None, is_anonymous=True)
        form = Form(id=9007199254745004, name="Questionnaire complet", source="private-import")
        other_form = Form(id=9007199254745005, name="Autre questionnaire")
        db.add_all([public, anonymous, empty, form, other_form])
        db.flush()
        questions = [
            Question(
                id=1900000010 + i,
                form_id=form.id,
                question_code=f"complete{i}",
                prompt=f"Question complète {i}",
                type=kind,
                position=position,
            )
            for i, (kind, position) in enumerate(
                [
                    ("text", 2),
                    ("single_choice", 0),
                    ("multi_choice", 1),
                    ("number", 3),
                    ("text", None),
                    ("text", 4),
                ]
            )
        ]
        foreign = Question(
            id=1900000020,
            form_id=other_form.id,
            question_code="foreign",
            prompt="Autre question",
            type="text",
            position=1,
        )
        db.add_all([*questions, foreign])
        db.flush()
        contributions = [
            Contribution(
                id=9007199254745100 + i,
                form_id=fid,
                author_id=aid,
                submitted_at=date,
                raw_json='{"private":"never expose"}',
                raw_hash=f"private-hash-{i}",
                import_batch_id="private-batch",
            )
            for i, (fid, aid, date) in enumerate(
                [
                    (form.id, public.id, datetime(2019, 1, 1)),
                    (form.id, public.id, datetime(2019, 1, 1)),
                    (other_form.id, public.id, None),
                    (form.id, anonymous.id, None),
                    (form.id, None, datetime(2018, 1, 1)),
                    (form.id, empty.id, None),
                ]
            )
        ]
        db.add_all(contributions)
        db.flush()
        first = contributions[0]
        rows = [
            Answer(
                id=9007199254745200 + i,
                contribution_id=first.id,
                question_id=qid,
                position=pos,
                text=value,
                value_json=metadata,
            )
            for i, (qid, pos, value, metadata) in enumerate(
                [
                    (questions[0].id, 2, "Second texte de la même question", None),
                    (
                        questions[0].id,
                        1,
                        "Texte intégral\n\n<script>source</script>" + " lecture" * 3000,
                        None,
                    ),
                    (questions[1].id, 1, "Choix A", None),
                    (
                        questions[2].id,
                        1,
                        "Choix A\nChoix B",
                        '{"other_text":["Autre proposition",{"private":"hidden"}],"private":"hidden"}',
                    ),
                    (
                        questions[3].id,
                        1,
                        None,
                        '{"value":"42","normalizations":{"private":"hidden"}}',
                    ),
                    (questions[4].id, 1, "", None),
                    # Malformed cross-form answer: the API must not associate it with this form.
                    (foreign.id, 1, "Une autre question du mauvais formulaire", None),
                ]
            )
        ]
        option_a = Option(
            id=9007199254745300, question_id=questions[2].id, code="a", label="Choix A", position=2
        )
        option_b = Option(
            id=9007199254745301, question_id=questions[2].id, code="b", label="Choix B", position=1
        )
        unique = Option(
            id=9007199254745302,
            question_id=questions[1].id,
            code="unique",
            label="Choix A",
            position=None,
        )
        db.add_all([*rows, option_a, option_b, unique])
        db.flush()
        db.add_all(
            [
                AnswerOption(answer_id=rows[3].id, option_id=option_a.id),
                AnswerOption(answer_id=rows[3].id, option_id=option_b.id),
                AnswerOption(answer_id=rows[2].id, option_id=unique.id),
            ]
        )
        for c, q in [
            (contributions[1], questions[0]),
            (contributions[2], foreign),
            (contributions[3], questions[0]),
            (contributions[4], questions[0]),
        ]:
            db.add(
                Answer(
                    contribution_id=c.id,
                    question_id=q.id,
                    position=1,
                    text="Une réponse de contrôle qui appartient bien à cette contribution et à ce formulaire.",
                )
            )
        db.commit()
        return dict(
            public=str(public.id),
            anonymous=str(anonymous.id),
            empty=str(empty.id),
            form=str(form.id),
            other_form=str(other_form.id),
            first=str(first.id),
            contributions=[str(c.id) for c in contributions],
            answers=[str(a.id) for a in rows],
            questions=[str(q.id) for q in questions],
        )


@pytest.mark.integration
@pytest.mark.parametrize("accept", ["text/html", "*/*", "application/json"])
def test_public_author_confidentiality(client, contribution_data, accept):
    for key, label in [
        ("public", "Pseudonyme public"),
        ("anonymous", "Auteur #"),
        ("empty", "Auteur #"),
    ]:
        response = client.get(
            f"/api/v1/authors/{contribution_data[key]}", headers={"Accept": accept}
        )
        assert (
            response.status_code == 200 and response.headers["content-type"] == "application/json"
        )
        author = response.json()
        PublicAuthor.model_validate(author)
        assert set(author) == {"id", "name", "is_anonymous", "slug", "url"}
        assert author["name"].startswith(label)
        assert "private" not in response.text and "Nom confidentiel" not in response.text
        assert "set-cookie" not in response.headers
        html = client.get(author["url"])
        assert html.status_code == 200
        assert author["name"] in html.text
        assert "Nom confidentiel" not in html.text
        assert (
            client.get(f"/authors/{author['id']}", follow_redirects=False)
            .headers["location"]
            .endswith(author["url"])
        )


@pytest.mark.integration
def test_author_forms_keyset_grouping_and_empty(client, contribution_data):
    d = contribution_data
    url = f"/api/v1/authors/{d['public']}/forms"
    whole = client.get(url).json()
    AuthorFormsPage.model_validate(whole)
    assert [f["id"] for f in whole["forms"]] == [d["form"], d["other_form"]]
    assert [c["id"] for c in whole["forms"][0]["contributions"]] == d["contributions"][:2]
    assert [c["id"] for c in whole["forms"][1]["contributions"]] == [d["contributions"][2]]
    identifiers, after = [], None
    for _ in range(5):
        page = client.get(
            url, params={"page_size": 1, **({"after_id": after} if after else {})}
        ).json()
        assert len({form["id"] for form in page["forms"]}) == len(page["forms"])
        identifiers.extend(c["id"] for f in page["forms"] for c in f["contributions"])
        after = page["next_after_id"]
        if not page["has_next"]:
            assert after is None
            break
    assert identifiers == d["contributions"][:3]
    assert len(identifiers) == len(set(identifiers))
    assert client.get(f"/api/v1/authors/{d['empty']}/forms").json()["forms"] == []
    anonymous = client.get(f"/api/v1/authors/{d['anonymous']}/forms").json()
    assert len(anonymous["forms"]) == 1
    assert anonymous["forms"][0]["contributions"][0]["id"] == d["contributions"][3]
    for params in [
        {"page_size": 0},
        {"page_size": 101},
        {"after_id": "invalid"},
        {"after_id": "0"},
        {"after_id": "9223372036854775808"},
    ]:
        assert client.get(url, params=params).status_code == 422


@pytest.mark.integration
def test_complete_contribution_choices_multiplicity_and_links(client, contribution_data):
    d = contribution_data
    response = client.get(f"/api/v1/forms/{d['form']}/contributions/{d['first']}")
    assert response.status_code == 200
    payload = response.json()
    ContributionDetail.model_validate(payload)
    assert payload["legacy_index"] is None
    assert payload["contribution"]["id"] == d["first"]
    assert payload["form"]["id"] == d["form"]
    assert payload["author"]["name"] == "Pseudonyme public"
    assert [a["id"] for a in payload["answers"]] == [
        d["answers"][2],
        d["answers"][3],
        d["answers"][1],
        d["answers"][0],
        d["answers"][4],
        d["answers"][5],
    ]
    assert d["questions"][5] not in [a["question"]["id"] for a in payload["answers"]]
    assert d["answers"][6] not in [a["id"] for a in payload["answers"]]
    assert payload["answers"][0]["selected_options"][0]["label"] == "Choix A"
    assert [o["label"] for o in payload["answers"][1]["selected_options"]] == ["Choix B", "Choix A"]
    assert payload["answers"][1]["other_text"] == ["Autre proposition"]
    assert payload["answers"][4]["value"] == "42" and payload["answers"][4]["text"] is None
    assert payload["answers"][5]["text"] == ""
    assert len(payload["answers"][2]["text"]) > 20000
    assert "private" not in response.text and "value_json" not in response.text
    targeted = client.get(f"/api/v1/answers/{d['answers'][1]}").json()
    assert targeted["contribution_id"] == d["first"]
    assert targeted["question"]["form_id"] == d["form"]
    assert targeted["id"] in [a["id"] for a in payload["answers"]]
    assert (
        client.get(f"/api/v1/forms/{d['other_form']}/contributions/{d['first']}").status_code == 404
    )
    assert (
        client.get(f"/api/v1/forms/{d['form']}/contributions/{d['contributions'][2]}").status_code
        == 404
    )
    anonymous = client.get(f"/api/v1/forms/{d['form']}/contributions/{d['contributions'][3]}")
    assert anonymous.json()["author"]["is_anonymous"]
    assert "Nom confidentiel" not in anonymous.text
    assert (
        client.get(f"/api/v1/forms/{d['form']}/contributions/{d['contributions'][4]}").json()[
            "author"
        ]
        is None
    )
    assert (
        client.get(f"/api/v1/forms/{d['form']}/contributions/{d['contributions'][5]}").json()[
            "answers"
        ]
        == []
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    "selector,rank",
    [("1", 1), ("2", 2), ("3", 3), ("invalid", 1), ("0", 1), ("-2", 1), ("", 1), ("99999", 5)],
)
def test_historical_ordinal_is_not_id(client, contribution_data, selector, rank):
    d = contribution_data
    response = client.get(f"/api/v1/forms/{d['form']}/contributions", params={"contrib": selector})
    assert response.status_code == 200
    payload = response.json()
    assert payload["legacy_index"] == str(rank)
    # Earliest dated contribution comes first, dates tied are ordered by ID, nulls last.
    expected = [
        d["contributions"][4],
        *d["contributions"][:2],
        d["contributions"][3],
        d["contributions"][5],
    ]
    # Five contributions in this form: the large requested rank is clamped to five.
    if selector == "99999":
        assert payload["legacy_index"] == "5"
        rank = 5
    assert payload["contribution"]["id"] == expected[rank - 1]
    html = client.get(f"/forms/{d['form']}", params={"contrib": selector})
    assert html.status_code == 200
    assert f"Contribution {rank} / 5" in html.text
    for answer in payload["answers"]:
        if answer["text"]:
            # Jinja historically keeps one answer per question; multiplicity remains in JSON.
            assert answer["question"]["prompt"] in html.text


@pytest.mark.integration
def test_query_budgets_and_public_cache(client, contribution_data, web_data):
    d = contribution_data
    statements = []
    with web_data["factory"]() as db:
        connection = db.get_bind()

    def record(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(connection, "before_cursor_execute", record)
    try:
        for path, count in [
            (f"/authors/{d['public']}", 1),
            (f"/authors/{d['public']}/forms", 2),
            (f"/forms/{d['form']}/contributions/{d['first']}", 3),
            (f"/forms/{d['form']}/contributions?contrib=2", 6),
        ]:
            statements.clear()
            url = f"/api/v1{path}"
            public = client.get(url)
            assert public.status_code == 200 and len(statements) == count
            if "/authors/" in path:
                assert all(
                    "OFFSET" not in s.upper() and "COUNT(" not in s.upper() for s in statements
                )
                if path.endswith("/forms"):
                    assert all("a.text" not in s for s in statements)
            private = client.get(url, headers={"Cookie": "session_token=invalid"})
            assert public.json() == private.json()
            assert private.headers["cache-control"] == "private, no-store"
            assert "set-cookie" not in private.headers
    finally:
        event.remove(connection, "before_cursor_execute", record)


@pytest.mark.parametrize("code,status", [("57014", 504), ("42P01", 500), (None, 503)])
def test_sql_failures_json_and_rollback(monkeypatch, code, status):
    from app.app import app
    from app.routers import api_contributions

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
    monkeypatch.setattr(api_contributions, "SessionLocal", lambda: session)
    with TestClient(app, raise_server_exceptions=False) as client:
        for path in [
            "/authors/1",
            "/authors/1/forms",
            "/forms/1/contributions/1",
            "/forms/1/contributions?contrib=1",
        ]:
            session.rolled_back = False
            response = client.get(
                f"/api/v1{path}", headers={"Accept": "text/html", "HX-Request": "true"}
            )
            assert response.status_code == status
            assert response.headers["content-type"] == "application/json"
            assert "private SQL" not in response.text
            assert session.rolled_back


@pytest.mark.integration
def test_real_timeout_recovers(client, web_data, monkeypatch):
    from app.routers import api_contributions

    def expire(db, author_id):
        db.execute(text("SET LOCAL statement_timeout = '1ms'"))
        db.execute(text("SELECT pg_sleep(0.05)"))

    monkeypatch.setattr(api_contributions, "existing_author", expire)
    assert client.get("/api/v1/authors/1").status_code == 504
    with web_data["factory"]() as db:
        assert db.execute(text("SELECT 1")).scalar_one() == 1


@pytest.mark.parametrize(
    "path",
    [
        "/authors/{id}",
        "/authors/{id}/forms",
        "/forms/{id}/contributions/1",
        "/forms/1/contributions/{id}",
        "/forms/{id}/contributions",
    ],
)
@pytest.mark.parametrize(
    "identifier,status",
    [("invalid", 422), ("0", 422), ("9223372036854775808", 422), ("9223372036854775807", 404)],
)
@pytest.mark.integration
def test_missing_and_invalid_ids(client, path, identifier, status):
    response = client.get(f"/api/v1{path.format(id=identifier)}", headers={"Accept": "text/html"})
    assert response.status_code == status
    assert response.headers["content-type"] == "application/json"


@pytest.mark.parametrize(
    "raw,kind,expected",
    [
        ('{"value":"42","secret":"hidden"}', "number", ([], "42")),
        ('{"value":{"private":"hidden"}}', "number", ([], None)),
        (
            '{"other_text":["texte",{"private":"hidden"},null,42]}',
            "multi_choice",
            (["texte"], None),
        ),
        ('{"other_text":"hidden"}', "multi_choice", ([], None)),
        ('{"value":"hidden","other_text":["hidden"]}', "text", ([], None)),
        ("not JSON", "multi_choice", ([], None)),
    ],
)
def test_value_projection_whitelist(raw, kind, expected):
    assert public_values(raw, kind) == expected


def test_openapi_contract_ids_and_names(tmp_path):
    from tests.test_openapi_export import run_export

    output = tmp_path / "api.json"
    result = run_export("--output", output)
    assert result.returncode == 0, result.stderr
    schema = json.loads(output.read_text())
    expected = {
        "/api/v1/authors/{author_id}": "get_public_author",
        "/api/v1/authors/{author_id}/forms": "list_public_author_forms",
        "/api/v1/forms/{form_id}/contributions/{contribution_id}": "get_public_contribution",
        "/api/v1/forms/{form_id}/contributions": "get_public_legacy_contribution",
    }
    for path, operation_id in expected.items():
        operation = schema["paths"][path]["get"]
        assert operation["operationId"] == operation_id
        assert {"200", "404", "422", "500", "503", "504"} <= operation["responses"].keys()
        for parameter in operation["parameters"]:
            if parameter["in"] == "path" or parameter["name"] == "after_id":
                assert (
                    parameter["schema"].get("type") == "string"
                    or parameter["schema"]["anyOf"][0]["type"] == "string"
                )
    operations = [op["operationId"] for route in schema["paths"].values() for op in route.values()]
    assert len(operations) == len(set(operations))
    for model, field in [
        ("PublicAuthor", "id"),
        ("ContributionReference", "id"),
        ("ContributionAnswer", "id"),
        ("SelectedOption", "id"),
    ]:
        assert schema["components"]["schemas"][model]["properties"][field]["type"] == "string"
    # Reversed route names continue to designate HTML, never the new API.
    from app.app import app

    assert str(app.url_path_for("author_detail", author_id=1, slug="auteur")) == "/authors/1-auteur"
    assert str(app.url_path_for("form_detail", form_id=1)) == "/forms/1"
