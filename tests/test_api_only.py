"""The backend serves JSON while React owns browser pages."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.app import app, search_timeout_handler
from app.search_errors import SearchTimeout


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/search/answers",
        "/search/questions",
        "/api/v1/search/answers",
        "/api/v1/search/catalog",
        "/questions/1",
        "/answers/1",
        "/authors/1",
        "/forms/1",
        "/forms/1/dashboard",
        "/bookmarks",
        "/static/css/reset.css",
    ],
)
def test_retired_frontend_routes_return_json_404(path):
    with TestClient(app) as client:
        response = client.get(path, headers={"Accept": "text/html"})
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_search_timeout_is_json_for_browser_requests():
    isolated = FastAPI()
    isolated.add_exception_handler(SearchTimeout, search_timeout_handler)

    @isolated.get("/api/v1/questions/1/answers")
    def timeout():
        raise SearchTimeout()

    with TestClient(isolated) as client:
        response = client.get("/api/v1/questions/1/answers", headers={"Accept": "text/html"})
    assert response.status_code == 504
    assert response.json() == {"detail": "Le délai de réponse a été dépassé."}
    assert response.headers["cache-control"] == "no-store"
    assert not any(name.startswith("hx-") for name in response.headers)
