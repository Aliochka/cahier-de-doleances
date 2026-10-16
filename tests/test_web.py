"""Regressions for pagination, choice grouping and removal of unused features."""

from xml.etree import ElementTree

import pytest


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
