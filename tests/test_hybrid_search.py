"""Contrat HTTP, provenance, curseurs et cycle de vie sans corpus de travail."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest
from cahier_rag.contracts import MAX_BIGINT
from cahier_rag.search.service.control import (
    Budget,
    SearchBusy,
    SearchNotReady,
    SearchTimeout,
    SearchUnavailable,
)
from cahier_rag.search.service.core import Hit, Ranking, SearchRecipe, Timings
from cahier_rag.sources.gdn import row_to_documents
from fastapi.testclient import TestClient

from app.app import app
from app.hybrid_runtime import SearchBackend
from app.routers.api_hybrid_search import calculate
from app.services.search_hydration import public_card
from app.services.search_snapshots import (
    CardReference,
    Snapshot,
    SnapshotCache,
    SnapshotExpired,
    SnapshotTooLarge,
    UnitReference,
    group_hits,
    query_hash,
)


def source_row(index=0, *, other=False):
    return dict(
        answer_id=MAX_BIGINT - index,
        contribution_id=MAX_BIGINT - 100 - index,
        question_id=MAX_BIGINT - 1000 - index,
        questionnaire_id=4,
        question_form_id=4,
        contribution_form_id=4,
        answer_text="Non",
        value_json='{"other_text":["Autre A","Autre B"],"private":"SECRET"}',
        answer_position=1,
        question_text="Pourquoi ?",
        question_type="multi_choice" if other else "text",
        question_position=1,
        question_section=None,
        question_code="Q1",
        questionnaire_name="Enquête",
        questionnaire_version="2019",
        questionnaire_source="source",
        contribution_title="PRIVATE_TITLE",
        contribution_source="source",
        external_contribution_id="PRIVATE_EXTERNAL",
        submitted_at=None,
    )


class Worker:
    def __init__(self, documents):
        self.calls = 0
        self.error = None
        self.service = SimpleNamespace(
            recipe=SearchRecipe(), reader=SimpleNamespace(generation="g"), ready=True
        )
        self.ranking = Ranking(
            "g",
            tuple(Hit(d, 0.01, i + 1, None, None) for i, d in enumerate(documents)),
            Timings(0, 0.01, 0.1, 0.02, 0.001, 0.131),
            self.service.recipe.fingerprint,
        )

    async def retrieve(self, q, *, budget):
        budget.check()
        self.calls += 1
        if self.error:
            raise self.error
        return self.ranking


class Hydration:
    def __init__(self, rows):
        self.rows = {row["answer_id"]: row for row in rows}
        self.calls = []
        self.error = None

    async def read(self, cards, budget):
        budget.check()
        self.calls.append(len(cards))
        if self.error:
            raise self.error
        return [public_card(c, self.rows.get(c.units[0].answer_id)) for c in cards], 0.001


@pytest.fixture
def hybrid():
    rows = [source_row(i) for i in range(45)]
    docs = [row_to_documents(row, "gdn-2019")[0] for row in rows]
    backend = SearchBackend(Worker(docs), Hydration(rows), SnapshotCache("test-signature-key-" * 3))
    with TestClient(app) as client:
        app.state.hybrid_search = backend
        yield client, backend
        app.state.hybrid_search = None


def test_http_order_pagination_return_first_and_no_recomputation(hybrid):
    client, backend = hybrid
    first = client.get("/api/v1/search", params={"q": " Non "}).json()
    assert first["q"] == "Non" and first["state"] == "results"
    assert len(first["items"]) == 20
    assert first["items"][0]["answer_id"] == str(MAX_BIGINT)
    assert first["items"][0]["question"]["id"] == str(MAX_BIGINT - 1000)
    assert first["window"] == dict(
        document_limit=50, retrieval_depth=50, answer_count=45, exhaustive=False
    )
    second = client.get(
        "/api/v1/search", params={"q": "Non", "cursor": first["next_cursor"]}
    ).json()
    third = client.get(
        "/api/v1/search", params={"q": "Non", "cursor": second["next_cursor"]}
    ).json()
    back = client.get("/api/v1/search", params={"q": "Non", "cursor": third["first_cursor"]}).json()
    assert back == first
    assert len(third["items"]) == 5 and not third["has_next"]
    assert backend.worker.calls == 1
    assert backend.hydrator.calls == [45, 20, 5, 20]
    ids = [i["answer_id"] for p in (first, second, third) for i in p["items"]]
    assert len(set(ids)) == len(ids) == 45
    serialized = str(first)
    assert all(
        word not in serialized
        for word in ("PRIVATE", "SECRET", "rrf_score", "embedding", "content_hash", "author")
    )
    assert first["items"][0]["url"].endswith("#answer-" + str(MAX_BIGINT))


@pytest.mark.parametrize(
    "params",
    [
        dict(q="x" * 513),
        dict(q="..."),
        dict(q='"non'),
        dict(q="Non", page_size=21),
        dict(q="Non", question_id="42"),
        dict(q="Non", engine="old"),
        dict(q="Non", cursor="bad"),
        [("q", "Non"), ("q", "Oui")],
    ],
)
def test_invalid_request_is_structured_and_does_not_search(hybrid, params):
    client, backend = hybrid
    result = client.get("/api/v1/search", params=params)
    assert result.status_code == 422
    assert set(result.json()) == {"error", "request_id"}
    assert backend.worker.calls == 0


def test_empty_is_idle_even_when_unavailable(hybrid):
    client, backend = hybrid
    app.state.hybrid_search = None
    result = client.get("/api/v1/search", params={"q": "  "})
    assert result.status_code == 200 and result.json()["state"] == "idle"
    assert backend.worker.calls == 0
    assert client.get("/api/v1/search", params={"q": "Non"}).status_code == 503


def test_zero_matches_and_all_sources_unavailable_are_distinct(hybrid):
    client, backend = hybrid
    backend.worker.ranking = replace(backend.worker.ranking, hits=())
    assert client.get("/api/v1/search", params={"q": "Non"}).json()["state"] == "empty"
    row = source_row()
    d = row_to_documents(row, "gdn-2019")[0]
    backend.worker.ranking = replace(backend.worker.ranking, hits=(Hit(d, 0.01, 1, None, None),))
    backend.hydrator.rows.clear()
    result = client.get("/api/v1/search", params={"q": "Non"}).json()
    assert result["state"] == "sources_unavailable" and result["warnings"][0]["count"] == 1


def test_source_removed_mid_navigation_does_not_shift_positions(hybrid):
    client, backend = hybrid
    first = client.get("/api/v1/search", params={"q": "Non"}).json()
    del backend.hydrator.rows[MAX_BIGINT - 20]
    second = client.get(
        "/api/v1/search", params={"q": "Non", "cursor": first["next_cursor"]}
    ).json()
    assert len(second["items"]) == 19 and second["items"][0]["rank"] == 22
    third = client.get(
        "/api/v1/search", params={"q": "Non", "cursor": second["next_cursor"]}
    ).json()
    assert third["items"][0]["rank"] == 41
    assert second["warnings"][0]["count"] == 1 and backend.worker.calls == 1


def test_global_inconsistency_disables_search(hybrid):
    client, backend = hybrid
    backend.hydrator.rows.clear()
    result = client.get("/api/v1/search", params={"q": "Non"})
    assert result.status_code == 503 and not backend.worker.service.ready
    assert not backend.cache.entries


@pytest.mark.parametrize(
    "error,status,code",
    [
        (SearchBusy(), 503, "search_busy"),
        (SearchNotReady(), 503, "search_not_ready"),
        (SearchUnavailable(), 503, "search_unavailable"),
        (SearchTimeout("sql"), 504, "search_sql_timeout"),
        (RuntimeError("postgresql://SECRET"), 500, "search_internal_error"),
    ],
)
def test_typed_failures_are_safe(hybrid, error, status, code):
    client, backend = hybrid
    backend.worker.error = error
    result = client.get("/api/v1/search", params={"q": "Non"})
    assert result.status_code == status
    assert "SECRET" not in result.text and "postgresql" not in result.text
    assert result.json()["error"]["retryable"]
    assert result.json()["error"]["code"] == code


def test_other_units_and_segments_are_grouped_without_merging_answers():
    row = source_row(other=True)
    docs = row_to_documents(row, "gdn-2019")
    second = row_to_documents(source_row(1), "gdn-2019")[0]
    hits = [
        Hit(docs[1], 0.1, 1, None, None),
        Hit(second, 0.09, 2, None, None),
        Hit(docs[0], 0.08, 3, None, None),
        Hit(docs[1], 0.07, 4, None, None),
    ]
    refs = group_hits(hits)
    assert len(refs) == 2 and len(refs[0].units) == 2
    card = public_card(refs[0], row)
    assert [t.text for t in card.texts] == ["Autre A", "Autre B"]
    assert card.rank == 1 and card.answer_id == str(row["answer_id"])
    assert public_card(refs[0], dict(row, contribution_form_id=5)) is None
    assert public_card(refs[0], dict(row, question_text="Changed")) is None


def test_cursor_expiration_eviction_tampering_and_payload_contains_no_text(hybrid):
    client, backend = hybrid
    first = client.get("/api/v1/search", params={"q": "Non"}).json()
    cursor = first["first_cursor"]
    for params in (
        {"q": "Oui", "cursor": cursor},
        {"q": "Non", "cursor": cursor, "page_size": 10},
        {"q": "Non", "cursor": cursor[:-3] + "abc"},
    ):
        assert client.get("/api/v1/search", params=params).status_code == 422
    assert "Pourquoi" not in str(backend.cache.entries) and "PRIVATE" not in str(
        backend.cache.entries
    )
    backend.cache.clear()
    assert client.get("/api/v1/search", params={"q": "Non", "cursor": cursor}).status_code == 410


def test_lru_ttl_and_byte_bound():
    now = [10.0]
    cache = SnapshotCache("K" * 32, capacity=2, ttl=600, clock=lambda: now[0])
    unit = UnitReference.from_hit(
        Hit(row_to_documents(source_row(), "gdn-2019")[0], 0.1, 1, None, None)
    )
    snap = Snapshot(query_hash("Non"), 20, "g", "r", "v", 50, 50, (CardReference(1, (unit,)),))
    a, _ = cache.put(snap)
    b, _ = cache.put(snap)
    cache.get(cache.cursor(a, 0), "Non", 20)
    cache.put(snap)
    with pytest.raises(SnapshotExpired):
        cache.get(cache.cursor(b, 0), "Non", 20)
    now[0] += 601
    with pytest.raises(SnapshotExpired):
        cache.get(cache.cursor(a, 0), "Non", 20)
    assert cache.payload_bytes == 0
    with pytest.raises(SnapshotTooLarge):
        SnapshotCache("K" * 32, max_bytes=10).put(snap)


def test_shared_deadline_includes_hydration(hybrid):
    _, backend = hybrid
    now = [0.0]
    budget = Budget(18, clock=lambda: now[0])

    async def slow(query, *, budget):
        now[0] = 17.9
        return backend.worker.ranking

    async def hydrate(cards, budget):
        now[0] = 18.1
        budget.check()

    backend.worker.retrieve = slow
    backend.hydrator.read = hydrate
    with pytest.raises(SearchTimeout):
        asyncio.run(calculate(backend, "Non", 20, None, budget, {}))


def test_search_access_log_redacts_query_and_cursor():
    import logging

    from app.logging_filters import RedactMagicLinkFilter

    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        "%s",
        ("GET /api/v1/search?q=SECRET_QUERY&cursor=SECRET_CURSOR HTTP/1.1",),
        None,
    )
    RedactMagicLinkFilter().filter(record)
    assert "SECRET" not in record.getMessage()


def test_failed_search_startup_does_not_block_documentary_endpoints(monkeypatch):
    import app.hybrid_runtime as runtime

    class Broken:
        cache = SnapshotCache("K" * 32)
        worker = Worker([])

        def __init__(self):
            self.worker.error = SearchNotReady()

        async def start(self):
            raise SearchNotReady()

        async def close(self):
            pass

    monkeypatch.setattr(runtime, "build_backend", Broken)
    with TestClient(app) as client:
        assert client.get("/openapi.json").status_code == 200
        assert client.get("/api/v1/search", params={"q": "Non"}).status_code == 503


def test_model_initialization_does_not_delay_documentary_startup(monkeypatch):
    import threading

    import app.hybrid_runtime as runtime

    entered = threading.Event()

    class Loading:
        cache = SnapshotCache("K" * 32)
        worker = Worker([])

        def __init__(self):
            self.worker.error = SearchNotReady()

        async def start(self):
            entered.set()
            await asyncio.Event().wait()

        async def close(self):
            pass

    monkeypatch.setattr(runtime, "build_backend", Loading)
    with TestClient(app) as client:
        assert entered.wait(1)
        assert client.get("/openapi.json").status_code == 200
        assert client.get("/api/v1/search", params={"q": "Non"}).status_code == 503
