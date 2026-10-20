"""Contrat H1 persistant, profils injectables et admission sans réseau/modèle."""

import asyncio
import subprocess
import sys
import threading
from dataclasses import FrozenInstanceError, replace
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from cahier_rag.config import ConfigurationError, load_settings
from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType
from cahier_rag.embeddings.core import EmbeddingError
from cahier_rag.search.lexical import SearchResult
from cahier_rag.search.service import HybridSearch, SearchRecipe, SearchWorker, core, create_service
from cahier_rag.search.service.control import (
    Budget,
    InvalidQuery,
    SearchBusy,
    SearchCancelled,
    SearchNotReady,
    SearchTimeout,
)
from cahier_rag.search.service.reader import ReadConnection, ReadStore, create_search_engine


def document(index):
    return TextUnit(
        "gdn-2019",
        UnitType.OPEN_ANSWER,
        MAX_BIGINT - index,
        MAX_BIGINT - 1000,
        42 + index,
        4,
        "Non",
        "Pourquoi ?",
        "Formulaire",
        1,
        "text",
    )


class Encoder:
    def __init__(self):
        self.loads = self.closes = 0
        self.queries = []

    def load(self):
        self.loads += 1

    def encode_queries(self, inputs):
        self.queries.append(inputs[0].text)
        yield SimpleNamespace(vectors=[[1.0] + [0.0] * 1023])

    def close(self):
        self.closes += 1


@pytest.fixture
def service(monkeypatch):
    reader = MagicMock()
    reader.validate.return_value = "generation"
    encoder = Encoder()
    service = HybridSearch(reader, encoder)
    calls = []

    class Lexical:
        def __init__(self, store, **options):
            assert options == {"statistics": True, "prefilter": None}

        def lexical(self, query, *, limit):
            calls.append(("lexical", limit))
            return [SearchResult(document(i), 1 / (i + 1)) for i in range(limit)]

    def ann(store, vector, config, *, limit):
        calls.append(("ann", limit, config))
        assert len(vector) == 1024
        results = [SearchResult(document(i), 1 / (i + 1)) for i in reversed(range(limit))]
        return results, {
            "winners": [
                dict(
                    document_id=r.document.document_id,
                    segment_index=1,
                    representation_id="segment:" + r.document.document_id,
                    start_offset=1,
                    end_offset=3,
                )
                for r in results
            ]
        }

    monkeypatch.setattr(core, "TunedSearch", Lexical)
    monkeypatch.setattr(core, "ann_search", ann)
    service.calls = calls
    yield service
    service.close()


def test_persistent_load_recipe_bigint_and_provenance(service):
    with pytest.raises(SearchNotReady):
        service.retrieve("Non")
    service.start()
    service.start()
    first = service.retrieve(" Non ")
    second = service.retrieve("Non")
    assert first.hits == second.hits
    assert service.encoder.loads == 1
    assert service.encoder.queries[1:] == ["Non", "Non"]
    assert len(first.hits) == 50
    assert first.recipe_hash == SearchRecipe().fingerprint
    assert service.calls[1][2].ef_search == 1000
    assert service.calls[1][2].candidates == 400
    assert len({hit.document.answer_id for hit in first.hits}) == 50
    for hit in first.hits:
        assert hit.document.answer_id > 2**53
        assert hit.document.to_dict()["answer_id"] == str(hit.document.answer_id)
        assert hit.document.question_id != hit.document.answer_id
        assert hit.segment.index == 1
        assert hit.lexical_rank + hit.vector_rank == 51
    with pytest.raises(FrozenInstanceError):
        first.hits = ()


def test_depth_and_output_size_are_recipe_not_structural_limit(service):
    default = SearchRecipe()
    service.recipe = replace(default, depth=80, result_limit=75, version="experiment-depth80")
    service.start()
    result = service.retrieve("Non")
    assert len(result.hits) == 75
    assert service.calls[0] == ("lexical", 80)
    assert service.calls[1][1] == 80
    assert result.recipe_hash != default.fingerprint
    assert result.recipe_version == "experiment-depth80"
    assert default.depth == default.result_limit == 50


@pytest.mark.parametrize("value", ["", "...", "x" * 513, '"non', None])
def test_query_validation_before_model(service, value):
    with pytest.raises(InvalidQuery):
        service.retrieve(value)
    assert service.encoder.loads == 0


def test_no_silent_filtered_or_single_branch_search(service, monkeypatch):
    service.start()
    with pytest.raises(InvalidQuery):
        service.retrieve("Non", question_id=42)

    def broken(*args, **kwargs):
        raise SearchTimeout("sql")

    monkeypatch.setattr(core, "ann_search", broken)
    with pytest.raises(SearchTimeout):
        service.retrieve("Non")


def test_empty_lexical_is_successful_not_a_failure(service, monkeypatch):
    service.start()
    monkeypatch.setattr(
        core, "TunedSearch", lambda *a, **kw: SimpleNamespace(lexical=lambda *a, **kw: [])
    )
    result = service.retrieve("Comment")
    assert result.hits and all(hit.lexical_rank is None for hit in result.hits)


def test_model_failure_disables_readiness_without_reloading(service, monkeypatch):
    service.start()

    def broken(*args):
        raise EmbeddingError("OOM")

    monkeypatch.setattr(service.encoder, "encode_queries", broken)
    with pytest.raises(SearchNotReady):
        service.retrieve("Non")
    with pytest.raises(SearchNotReady):
        service.retrieve("Non")
    assert service.encoder.loads == 1


def test_start_failure_close_and_shutdown_are_idempotent(service):
    service.reader.validate.side_effect = SearchNotReady("corpus")
    with pytest.raises(SearchNotReady):
        service.start()
    assert not service.ready
    assert not service.encoder.loads
    service.close()
    service.close()
    service.reader.close.assert_called_once()
    with pytest.raises(SearchNotReady):
        service.start()


def test_budget_never_renews_total_or_sql_allowance():
    now = [10.0]
    budget = Budget(18, clock=lambda: now[0])
    with budget.phase("sql", 10):
        now[0] = 19
        assert budget.remaining() == 1
        with pytest.raises(SearchTimeout) as error:
            now[0] = 21
            budget.check()
        assert error.value.stage == "sql"
        now[0] = 19
    assert budget.remaining() == 9
    budget.cancellation.set()
    with pytest.raises(SearchCancelled):
        budget.check()


def test_each_sql_statement_resets_remaining_timeout():
    now = [10.0]
    budget = Budget(5, clock=lambda: now[0])
    connection = MagicMock()
    bounded = ReadConnection(connection, budget)
    bounded.execute("SET LOCAL statement_timeout='30s'")
    now[0] += 2
    bounded.execute("SELECT 1")
    calls = connection.execute.call_args_list
    assert calls[0].args[1] == {"timeout": "5000"}
    assert calls[2].args[1] == {"timeout": "3000"}
    now[0] += 4
    with pytest.raises(SearchTimeout):
        bounded.execute("SELECT 2")
    assert connection.execute.call_count == 4


def test_public_engine_and_store_expose_no_writes():
    engine = create_search_engine("postgresql+psycopg2:///never_connected")
    try:
        assert engine.get_execution_options()["postgresql_readonly"] is True
        assert engine.pool.size() == 2 and engine.pool._max_overflow == 0
        assert engine.pool.timeout() == 1
        store = ReadStore(None)
        assert not hasattr(store, "commit_vectors") and not hasattr(store, "initialize")
    finally:
        engine.dispose()


def test_service_requires_explicit_urls_before_creating_engines(tmp_path):
    with pytest.raises(ConfigurationError):
        create_service(
            load_settings(environ={"DATABASE_URL": "postgresql:///application"}), tmp_path
        )


def test_import_is_lazy_and_has_no_generative_dependency():
    subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
import cahier_rag.search.service
assert not any(name.startswith((
    'torch', 'transformers', 'cahier_rag.personal', 'cahier_rag.generation',
    'cahier_rag.context', 'cahier_rag.reranking',
)) for name in sys.modules)
""",
        ],
        check=True,
    )


def test_smoke_configuration_error_is_explicit_not_a_traceback(tmp_path, monkeypatch, capsys):
    import json

    from cahier_rag.search.service.__main__ import main

    for name in ("RAG_SOURCE_DATABASE_URL", "RAG_DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    env = tmp_path / "reader.env"
    env.write_text("# missing connection URLs\n")
    result = main(
        [
            "--env-file",
            str(env),
            "--models",
            str(tmp_path),
            "--device",
            "cpu",
            "--precision",
            "float32",
            "--query",
            "Non",
        ]
    )
    assert result == 1
    output = json.loads(capsys.readouterr().out)
    assert output["code"] == "configuration_error"
    assert "RAG_SOURCE_DATABASE_URL" in output["message"]


def test_monitor_cancels_only_borrowed_connection():
    budget = Budget(5)
    connection = MagicMock()
    cancelled = threading.Event()
    connection.cancel.side_effect = cancelled.set
    with budget.monitor():
        with budget.connection(connection):
            budget.cancellation.set()
            assert cancelled.wait(1)
    connection.cancel.assert_called_once()


def test_worker_timeout_retains_capacity_and_event_loop_is_free(service, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = service._encode

    def blocking(query):
        if query == "bloque":
            entered.set()
            assert release.wait(3)
        return original(query)

    async def scenario():
        worker = SearchWorker(service)
        await worker.start()
        monkeypatch.setattr(service, "_encode", blocking)
        try:
            first = asyncio.create_task(worker.retrieve("bloque", timeout=0.1))
            assert await asyncio.to_thread(entered.wait, 1)
            # L'event loop reste disponible pendant l'encodage bloqué.
            assert await asyncio.sleep(0, result="alive") == "alive"
            with pytest.raises(SearchTimeout):
                await first
            assert worker._pending == 1
            second = asyncio.create_task(worker.retrieve("deux"))
            third = asyncio.create_task(worker.retrieve("trois"))
            await asyncio.sleep(0)
            with pytest.raises(SearchBusy):
                await worker.retrieve("quatre")
            release.set()
            results = await asyncio.gather(second, third)
            assert all(r.hits for r in results)
            assert service.encoder.loads == 1
        finally:
            release.set()
            await worker.close()

    asyncio.run(scenario())


def test_worker_caller_cancellation_and_queued_expiration(service, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    original = service._encode

    def blocking(query):
        if query == "bloque":
            entered.set()
            assert release.wait(3)
        return original(query)

    async def scenario():
        worker = SearchWorker(service)
        await worker.start()
        monkeypatch.setattr(service, "_encode", blocking)
        try:
            first = asyncio.create_task(worker.retrieve("bloque"))
            assert await asyncio.to_thread(entered.wait, 1)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            with pytest.raises(SearchTimeout):
                await worker.retrieve("expire en file", timeout=0.05)
            assert "expire en file" not in service.encoder.queries
            assert worker._pending == 1
        finally:
            release.set()
            await worker.close()
        assert worker._pending == 0

    asyncio.run(scenario())


def test_source_identity_allows_only_audited_additive_migration():
    from cahier_rag.search.service.reader import compatible_source_identity

    indexed = {
        "cluster_id": "cluster",
        "database_oid": 42,
        "database_name": "source",
        "schema_revision": "remove_runtime_caches",
    }
    migrated = {**indexed, "schema_revision": "forms_statistics_v1"}
    assert compatible_source_identity(indexed, indexed)
    assert compatible_source_identity(indexed, migrated)
    assert compatible_source_identity(migrated, migrated)
    for key, value in [
        ("cluster_id", "other"),
        ("database_oid", 43),
        ("database_name", "other"),
        ("schema_revision", "unknown_future_migration"),
    ]:
        assert not compatible_source_identity(indexed, {**migrated, key: value})
    assert not compatible_source_identity(migrated, indexed)
    assert not compatible_source_identity(None, migrated)
