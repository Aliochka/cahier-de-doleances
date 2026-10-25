"""API et H1 sur deux bases _test, encodeur déterministe, contenus synthétiques."""

import asyncio
import threading
import time

import pytest
from cahier_rag.search.service import HybridSearch, SearchWorker
from cahier_rag.search.service.control import Budget, SearchTimeout
from cahier_rag.search.service.reader import create_search_engine
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from app.app import app
from app.hybrid_runtime import SearchBackend
from app.services.search_hydration import Hydrator
from app.services.search_snapshots import SnapshotCache
from rag.tests.integration.conftest import pg_source  # noqa: F401
from rag.tests.integration.test_search_service import Encoder, service_corpus  # noqa: F401


def wait_ready(backend):
    deadline = time.monotonic() + 5
    while not backend.worker.ready and time.monotonic() < deadline:
        time.sleep(0.01)
    assert backend.worker.ready


@pytest.fixture
def real_backend(request, monkeypatch):
    _, reader, _ = request.getfixturevalue("service_corpus")
    monkeypatch.setattr("cahier_rag.search.service.reader.check_reader_role", lambda c: None)
    service = HybridSearch(reader, Encoder())
    hydrator = Hydrator(create_search_engine(reader.source.url))
    backend = SearchBackend(
        SearchWorker(service), hydrator, SnapshotCache("test-api-signature-" * 3)
    )
    monkeypatch.setattr("app.hybrid_runtime.build_backend", lambda: backend)
    return backend


def test_two_database_api_hydration_batch_pagination_and_links(real_backend, monkeypatch):
    from sqlalchemy import event

    queries = []

    @event.listens_for(real_backend.hydrator.engine, "before_cursor_execute")
    def count(conn, cursor, statement, parameters, context, executemany):
        if "FROM public.answers a" in statement:
            queries.append(statement)

    with TestClient(app) as client:
        wait_ready(real_backend)
        first = client.get("/api/v1/search", params={"q": "Non", "page_size": 1})
        assert first.status_code == 200, first.text
        payload = first.json()
        assert len(queries) == 1  # Un lot pour toute la fenêtre de départ.
        assert payload["window"]["answer_count"] == 4  # Deux unités Autre dans la même réponse.
        assert int(payload["items"][0]["answer_id"]) > 2**53
        before = real_backend.worker.service.encoder.loads
        monkeypatch.setattr(real_backend.worker, "retrieve", forbidden_retrieval)
        second = client.get(
            "/api/v1/search", params={"q": "Non", "page_size": 1, "cursor": payload["next_cursor"]}
        )
        assert second.status_code == 200 and len(queries) == 2
        back = client.get(
            "/api/v1/search",
            params={"q": "Non", "page_size": 1, "cursor": second.json()["first_cursor"]},
        )
        assert back.json() == payload and len(queries) == 3
        assert real_backend.worker.service.encoder.loads == before == 1
        item = payload["items"][0]
        form_id = item["form"]["id"]
        contribution_id = item["contribution_id"]
        contribution = client.get(f"/api/v1/forms/{form_id}/contributions/{contribution_id}")
        assert contribution.status_code == 200
        assert item["answer_id"] in {a["id"] for a in contribution.json()["answers"]}
        assert (
            item["url"]
            == f"/forms/{form_id}/contributions/{contribution_id}#answer-{item['answer_id']}"
        )


async def forbidden_retrieval(*args, **kwargs):
    raise AssertionError("La pagination ne doit pas recalculer H1")


def test_application_unavailable_and_other_endpoints_independent(real_backend, monkeypatch):
    with TestClient(app) as client:
        wait_ready(real_backend)

        def broken(*args, **kwargs):
            from sqlalchemy.exc import OperationalError

            raise OperationalError("SECRET_URL", {}, Exception("SECRET_PASSWORD"))

        monkeypatch.setattr(real_backend.hydrator.engine, "connect", broken)
        failed = client.get("/api/v1/search", params={"q": "Non"})
        assert failed.status_code == 503 and "SECRET" not in failed.text
        assert failed.json()["error"]["code"] == "search_metadata_unavailable"
        real_backend.worker.service.ready = False
        assert client.get("/api/v1/forms").status_code == 200


def test_real_hydration_timeout_rolls_back_and_releases_pool(real_backend):
    hydrator = real_backend.hydrator
    entered = threading.Event()

    def delay(conn, cursor, statement, parameters, context, executemany):
        if "FROM public.answers a" in statement:
            entered.set()
            return "SELECT pg_sleep(5)", ()
        return statement, parameters

    async def scenario():
        from app.services.search_snapshots import group_hits

        ranking = real_backend.worker.service.retrieve("Non")
        event.listen(hydrator.engine, "before_cursor_execute", delay, retval=True)
        with pytest.raises(SearchTimeout):
            await hydrator.read(group_hits(ranking.hits), Budget(0.2))
        for _ in range(100):
            if hydrator.pending == 0:
                break
            await asyncio.sleep(0.01)
        event.remove(hydrator.engine, "before_cursor_execute", delay)
        assert entered.is_set()
        assert hydrator.pending == 0
        with hydrator.engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1

    with TestClient(app):
        wait_ready(real_backend)
        asyncio.run(scenario())


def test_cancelled_api_keeps_worker_busy_and_other_endpoints_responsive(real_backend, monkeypatch):
    import httpx

    entered, release = threading.Event(), threading.Event()
    service = real_backend.worker.service
    original = service._encode

    def blocked(query):
        entered.set()
        assert release.wait(3)
        return original(query)

    async def scenario():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            search = asyncio.create_task(client.get("/api/v1/search", params={"q": "Non"}))
            assert await asyncio.to_thread(entered.wait, 1)
            forms = await asyncio.wait_for(client.get("/api/v1/forms"), timeout=1)
            assert forms.status_code == 200
            search.cancel()
            with pytest.raises(asyncio.CancelledError):
                await search
            assert real_backend.worker._pending == 1
            release.set()
            for _ in range(100):
                if real_backend.worker._pending == 0:
                    break
                await asyncio.sleep(0.01)
            assert real_backend.worker._pending == 0

    with TestClient(app):
        wait_ready(real_backend)
        monkeypatch.setattr(service, "_encode", blocked)
        try:
            asyncio.run(scenario())
        finally:
            release.set()


def test_question_h1_keeps_lexical_order_and_pages_without_encoding(
    real_backend, request, monkeypatch
):
    from cahier_rag.search.service import core
    from cahier_rag.search.service.core import H1LexicalSearch

    store, _, documents = request.getfixturevalue("service_corpus")
    qid = next(d.question_id for d in documents if d.unit_type.value == "open_answer")
    reference = H1LexicalSearch(store).lexical("Non", question_id=qid)

    def forbidden(*args, **kwargs):
        pytest.fail("Question search must not use BGE-M3, ANN or RRF")

    with TestClient(app) as client:
        wait_ready(real_backend)
        monkeypatch.setattr(real_backend.worker.service, "_encode", forbidden)
        monkeypatch.setattr(core, "ann_search", forbidden)
        monkeypatch.setattr(core, "fuse", forbidden)
        params = {"q": "Non", "question_id": str(qid), "page_size": 1}
        response = client.get("/api/v1/search", params=params)
        assert response.status_code == 200, response.text
        first = response.json()
        assert first["mode"] == "lexical"
        assert first["items"][0]["answer_id"] == str(reference[0].document.answer_id)
        assert first["has_next"]
        monkeypatch.setattr(real_backend.worker, "retrieve", forbidden_retrieval)
        second = client.get("/api/v1/search", params={**params, "cursor": first["next_cursor"]})
        assert second.status_code == 200
        assert second.json()["items"][0]["answer_id"] == str(reference[1].document.answer_id)
        assert second.json()["items"][0]["question"]["id"] == str(qid)
