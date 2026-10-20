"""Grouped statistics retain single-question and historical semantics with a fixed SQL budget."""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.models import Answer, AnswerOption, Contribution, Form, Option, Question
from app.schemas.questions import FormStatistics

pytestmark = pytest.mark.integration


@pytest.fixture
def dashboard_data(web_data):
    with web_data["factory"]() as db:
        single = Question(
            form_id=web_data["form"],
            question_code="single",
            prompt="Choix unique",
            type="single_choice",
            position=0,
        )
        empty = Question(
            form_id=web_data["form"],
            question_code="empty",
            prompt="Choix vide",
            type="multi_choice",
            position=None,
        )
        db.add_all([single, empty])
        db.flush()
        zero = Option(
            id=9007199254740993,
            question_id=single.id,
            code="zero",
            label="Sans sélection",
            position=None,
        )
        selected = Option(question_id=single.id, code="oui", label="Oui", position=1)
        db.add_all([zero, selected])
        db.flush()
        contribution = Contribution(form_id=web_data["form"], title="Donnée synthétique privée")
        db.add(contribution)
        db.flush()
        for index in range(3):
            answer = Answer(
                question_id=single.id,
                contribution_id=contribution.id,
                position=index + 1,
                text="Oui",
                value_json=json.dumps({"other_text": ["Privé", "Autre"] if index == 0 else []}),
            )
            db.add(answer)
            db.flush()
            if index < 2:
                db.add(AnswerOption(answer_id=answer.id, option_id=selected.id))
        db.commit()
    publish(web_data)
    return {**web_data, "single": single.id, "empty": empty.id}


def test_grouped_parity_order_totals_and_public_fields(client, dashboard_data):
    data = dashboard_data
    response = client.get(
        f"/api/v1/forms/{data['form']}/stats", headers={"Accept": "text/html", "HX-Request": "true"}
    )
    assert response.status_code == 200
    payload = response.json()
    FormStatistics.model_validate(payload)
    assert set(payload) == {"form", "questions"}
    assert payload["form"]["id"] == str(data["form"])
    assert [entry["question"]["id"] for entry in payload["questions"]] == list(
        map(str, [data["single"], data["multi"], data["empty"]])
    )
    for entry in payload["questions"]:
        qid = entry["question"]["id"]
        assert entry["stats"] == client.get(f"/api/v1/questions/{qid}/stats").json()
        assert entry["stats"]["percentage_denominator"] == "total_answers"
        assert entry["stats"]["percentage_decimal_places"] == 2
    single, multi, empty = [e["stats"] for e in payload["questions"]]
    assert single["total_answers"] == 3
    assert single["answered_contributions_count"] == 1
    assert single["total_option_selections"] == 2
    assert single["other_text_answers_count"] == 1
    assert [c["percentage"] for c in single["categories"]] == [66.67, 0, 33.33]
    assert single["categories"][1]["option_id"] == "9007199254740993"
    assert single["categories"][2]["kind"] == "other_text"
    assert sum(c["percentage"] for c in multi["categories"]) == 150
    assert empty["categories"] == [] and empty["total_answers"] == 0
    for forbidden in (
        "value_json",
        "raw_json",
        'other_text": [',
        "Privé",
        "Donnée synthétique",
        "email",
        "token",
    ):
        assert forbidden not in response.text
    assert "set-cookie" not in response.headers


def test_empty_form_bigint_and_nonchoice_questions(client, web_data):
    with web_data["factory"]() as db:
        form = Form(id=9007199254740993, name="Sans statistiques", source="synthetic-dashboard")
        db.add(form)
        db.flush()
        db.add(
            Question(
                id=9007199254740993,
                form_id=form.id,
                question_code="text",
                prompt="Texte libre",
                type="text",
                position=None,
            )
        )
        db.commit()
    publish(web_data)
    payload = client.get(f"/api/v1/forms/{form.id}/stats").json()
    assert payload == {
        "form": {"id": str(form.id), "name": form.name, "url": f"/forms/{form.id}"},
        "questions": [],
    }
    with web_data["factory"]() as db:
        db.execute(text("UPDATE questions SET type='single_choice' WHERE id=:id"), {"id": form.id})
        db.commit()
    publish(web_data)
    payload = client.get(f"/api/v1/forms/{form.id}/stats").json()
    assert payload["questions"][0]["question"]["id"] == str(form.id)
    assert payload["questions"][0]["stats"]["total_answers"] == 0


@pytest.mark.parametrize(
    "identifier, status",
    [("999999999", 404), ("0", 422), ("-1", 422), ("abc", 422), ("9223372036854775808", 422)],
)
def test_errors_are_json(client, identifier, status):
    response = client.get(f"/api/v1/forms/{identifier}/stats", headers={"Accept": "text/html"})
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/json")
    assert "detail" in response.json()


def test_fixed_query_budget_and_no_answer_rows(client, dashboard_data):
    engine = dashboard_data["factory"].kw["bind"].engine
    statements = []

    def capture(_connection, _cursor, sql, _params, _ctx, _many):
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get(f"/api/v1/forms/{dashboard_data['form']}/stats")
        assert response.status_code == 200
        assert len(statements) == 3
        assert len(response.json()["questions"]) == 3
        assert not any("OFFSET" in sql.upper() or "SELECT *" in sql.upper() for sql in statements)
        assert not any("FROM answers" in s or "JOIN answer_options" in s for s in statements)
        statements.clear()
        for entry in response.json()["questions"]:
            assert (
                client.get(f"/api/v1/questions/{entry['question']['id']}/stats").status_code == 200
            )
        assert len(statements) == 6
    finally:
        event.remove(engine, "before_cursor_execute", capture)


@pytest.mark.parametrize("pgcode, status", [("57014", 504), ("42P01", 500), (None, 503)])
def test_database_errors_rollback_without_details(client, web_data, monkeypatch, pgcode, status):
    from app.routers import api_forms

    def fail(db, *_args, **_kwargs):
        raise (ProgrammingError if pgcode == "42P01" else OperationalError)(
            "private SQL", {}, SimpleNamespace(pgcode=pgcode)
        )

    monkeypatch.setattr(api_forms, "require_published", fail)
    response = client.get(
        f"/api/v1/forms/{web_data['form']}/stats", headers={"Accept": "text/html"}
    )
    assert response.status_code == status
    assert "private SQL" not in response.text
    with web_data["factory"]() as db:
        assert db.execute(text("SELECT 1")).scalar_one() == 1


def test_real_statement_timeout_rollback(client, web_data, monkeypatch):
    from app.routers import api_forms

    def timeout(db, *_args, **_kwargs):
        db.execute(text("SET LOCAL statement_timeout='1ms'"))
        db.execute(text("SELECT pg_sleep(0.05)"))

    monkeypatch.setattr(api_forms, "require_published", timeout)
    response = client.get(f"/api/v1/forms/{web_data['form']}/stats")
    assert response.status_code == 504
    with web_data["factory"]() as db:
        assert db.execute(text("SELECT 1")).scalar_one() == 1


def publish(data):
    from app.services.statistics_generation import generate
    with data["factory"]() as db:
        generate(db)
        db.commit()
