"""Regressions for pagination, choice grouping and removal of unused features."""

import html
import re
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree

import pytest
from sqlalchemy import text


@pytest.mark.integration
def test_optional_contribution_metric_preserves_historical_choice_statistics(web_data):
    from app.choice_stats import choice_statistics

    with web_data["factory"]() as db:
        historical = choice_statistics(db, web_data["multi"])
        extended = choice_statistics(db, web_data["multi"], include_contributions=True)
    assert historical["answered_contributions_count"] is None
    assert extended["answered_contributions_count"] == 2
    assert extended["total_answers"] == historical["total_answers"] == 2
    assert extended["total_selections"] == historical["total_selections"] == 3
    assert extended["stats"] == historical["stats"]
    assert extended["other_text_answers_count"] == 0


@pytest.mark.integration
@pytest.mark.parametrize("query", ["", "culture"])
def test_search_pagination_has_exactly_one_card_per_answer(client, web_data, query):
    first = client.get("/search/answers", params={"q": query})
    assert first.status_code == 200
    first_ids = [int(i) for i in re.findall(r'id="answer-(\d+)"', first.text)]
    assert len(first_ids) == len(set(first_ids)) == 20
    next_url = html.unescape(re.search(r'hx-get="([^"]*cursor=[^"]+)"', first.text)[1])
    cursor = parse_qs(urlsplit(next_url).query)["cursor"][0]
    second = client.get("/search/answers", params={"q": query, "cursor": cursor, "partial": "true"})
    assert second.status_code == 200, (next_url, second.text)
    second_ids = [int(i) for i in re.findall(r'id="answer-(\d+)"', second.text)]
    assert len(second_ids) == len(set(second_ids)) == 3
    assert set(first_ids).isdisjoint(second_ids)
    assert set(first_ids + second_ids) == set(web_data["text_ids"])
    assert "<html" not in second.text
    assert "search-load-more-sentinel" not in second.text
    assert "<script>alert" not in first.text
    assert "set-language" not in first.text


@pytest.mark.integration
def test_choice_stats_and_dashboard_reflect_changes_immediately(client, web_data):
    url = f"/questions/{web_data['multi']}/stats"
    first = client.get(url).json()
    assert first["total_answers"] == 2
    assert first["total_selections"] == 3
    assert [(s["label"], s["count"], s["percentage"]) for s in first["stats"]] == [
        ("Vélo", 1, 50.0),
        ("Bus", 2, 100.0),
    ]
    dashboard = f"/forms/{web_data['form']}/dashboard"
    assert "Vélo" in client.get(dashboard).text
    with web_data["factory"]() as db:
        db.execute(
            text("UPDATE options SET label='Vélo électrique' WHERE id=:id"),
            {"id": web_data["bike"]},
        )
        db.execute(text("DELETE FROM answer_options WHERE option_id=:id"), {"id": web_data["bike"]})
        db.commit()
    second = client.get(url).json()
    assert second["total_answers"] == 2
    assert second["total_selections"] == 2
    assert second["stats"][0]["label"] == "Vélo électrique"
    assert second["stats"][0]["count"] == 0
    assert "Vélo électrique" in client.get(dashboard).text


@pytest.mark.integration
def test_templates_render_without_translation_or_dynamic_og_routes(client, web_data):
    paths = [
        "/",
        "/search/questions?q=culture",
        f"/forms/{web_data['form']}",
        f"/forms/{web_data['form']}/dashboard-stats",
        f"/answers/{web_data['choice_answer']}",
        f"/questions/{web_data['multi']}",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        assert "language-switcher" not in response.text
        assert "/og/" not in response.text
        if "<html" in response.text:
            assert 'content="http://testserver/static/img/og-default.jpg"' in response.text
    assert client.get("/static/img/og-default.jpg").status_code == 200


@pytest.mark.integration
def test_sitemap_uses_configured_origin_and_ignores_forwarded_host(client, web_data, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "BASE_URL", "http://testserver")
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    for host in ("premier.example", "second.example"):
        response = client.get("/sitemap.xml", headers={"x-forwarded-host": host})
        assert response.status_code == 200
        urls = [
            n.text for n in ElementTree.fromstring(response.text).findall("s:url/s:loc", namespace)
        ]
        assert f"http://testserver/forms/{web_data['form']}" in urls
        assert all(url.startswith("http://testserver/") for url in urls)
    assert client.head("/sitemap.xml").content == b""
    robots = client.get("/robots.txt")
    assert "Sitemap: http://testserver/sitemap.xml" in robots.text
    assert client.head("/robots.txt").content == b""


def test_retired_routes_are_not_registered():
    from fastapi.testclient import TestClient

    from app.app import app

    with TestClient(app) as client:
        for path in (
            "/mentions",
            "/topics",
            "/og/test",
            "/og/status",
            "/sitemap/clear-cache",
            "/set-language/fr",
        ):
            assert client.get(path).status_code == 404


@pytest.mark.integration
@pytest.mark.parametrize("section", ["forms", "questions"])
@pytest.mark.parametrize("query", ["", "culture"])
def test_question_and_form_search_pagination_preserves_all_results(
    client, web_data, section, query
):
    from app.models import Form, Question

    with web_data["factory"]() as db:
        expected = []
        for index in range(23):
            if section == "forms":
                item = Form(name=f"Culture formulaire {index}")
            else:
                item = Question(
                    form_id=web_data["form"],
                    question_code=f"EXTRA{index}",
                    prompt=f"Culture question {index}",
                    type="text",
                )
            db.add(item)
            db.flush()
            expected.append(item.id)
        db.commit()
    if section == "forms" and not query:
        expected.append(web_data["form"])
    if section == "questions":
        expected.append(web_data["text_question"])
        if not query:
            expected.append(web_data["multi"])
    pattern = (
        r'href="[^" ]*/forms/(\d+)/dashboard"'
        if section == "forms"
        else r'<a href="[^" ]*/questions/(\d+)-'
    )
    first = client.get(
        "/search/questions", params={"q": query, "section": section, "partial": "true"}
    )
    assert first.status_code == 200
    first_ids = [int(i) for i in re.findall(pattern, first.text)]
    assert len(first_ids) == len(set(first_ids)) == 20
    next_url = html.unescape(re.search(r'hx-get="([^"]*cursor_[^"]+)"', first.text)[1])
    second = client.get(next_url)
    assert second.status_code == 200, (next_url, second.text)
    second_ids = [int(i) for i in re.findall(pattern, second.text)]
    assert len(second_ids) == len(set(second_ids)) == len(expected) - 20, (next_url, second.text)
    assert set(first_ids).isdisjoint(second_ids)
    assert set(first_ids + second_ids) == set(expected)
