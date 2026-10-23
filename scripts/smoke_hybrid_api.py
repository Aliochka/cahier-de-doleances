"""Vérification locale bornée de SEARCH-004, sans fixture ni écriture SQL.

Utiliser l'environnement backend racine préparé par uv sync --locked. Ne pas définir
TEST_DATABASE_URL. La sortie contient uniquement statuts, effectifs et durées.
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    if os.environ.get("TEST_DATABASE_URL"):
        raise SystemExit("Retirer TEST_DATABASE_URL pour cette vérification du corpus local.")
    from fastapi.testclient import TestClient

    from app.app import app
    from app.routers import api_hybrid_search

    metrics = []
    api_hybrid_search.observe = metrics.append
    results = []
    with TestClient(app) as client:
        backend = app.state.hybrid_search
        assert client.get("/api/v1/forms").status_code == 200
        loading_status = client.get("/api/v1/search", params={"q": "Initialisation"}).status_code
        assert loading_status in (200, 503)
        deadline = time.monotonic() + 120
        while backend is not None and not backend.worker.ready and time.monotonic() < deadline:
            time.sleep(0.05)
        assert backend is not None and backend.worker.ready, "Recherche non prête"
        model_id = id(backend.worker.service.encoder.backend.model)
        count = 0
        retrieve = backend.worker.retrieve

        async def counted(*args, **kwargs):
            nonlocal count
            count += 1
            return await retrieve(*args, **kwargs)

        backend.worker.retrieve = counted

        def request(params):
            started = time.monotonic()
            response = client.get("/api/v1/search", params=params)
            assert response.status_code == 200, f"Recherche HTTP {response.status_code}"
            results.append({"http_seconds": time.monotonic() - started, **metrics[-1]})
            return response.json()

        query = "Comment améliorer les transports publics ?"
        first = request({"q": query})
        assert first["items"] and first["has_next"]
        second = request({"q": query, "cursor": first["next_cursor"]})
        back = request({"q": query, "cursor": second["first_cursor"]})
        assert first == back and count == 1
        assert not (
            {i["answer_id"] for i in first["items"]} & {i["answer_id"] for i in second["items"]}
        )
        item = first["items"][0]
        contribution = client.get(
            f"/api/v1/forms/{item['form']['id']}/contributions/{item['contribution_id']}"
        )
        assert contribution.status_code == 200
        assert item["answer_id"] in {answer["id"] for answer in contribution.json()["answers"]}
        assert item["url"].endswith("#answer-" + item["answer_id"])
        another = request({"q": "Comment réduire les dépenses contraintes ?"})
        assert another["items"] and count == 2
        assert id(backend.worker.service.encoder.backend.model) == model_id
        print(
            json.dumps(
                {
                    "ready": True,
                    "model_load_seconds": backend.worker.service.load_seconds,
                    "h1_calls": count,
                    "model_reused": True,
                    "documentary_during_startup": True,
                    "search_during_startup_status": loading_status,
                    "first_page_items": len(first["items"]),
                    "window_answers": first["window"]["answer_count"],
                    "contribution_link": "verified",
                    "requests": results,
                }
            )
        )


if __name__ == "__main__":
    main()
