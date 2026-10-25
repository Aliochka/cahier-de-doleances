"""H1 sur deux bases _test, données synthétiques et transactions publiques READ ONLY."""

import os
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from cahier_rag.config import load_settings
from cahier_rag.db import create_rag_engine
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.fullcorpus.pipeline import prepare_metadata
from cahier_rag.fullcorpus.store import FullStore, vector_hash
from cahier_rag.safety import DatabaseGuard
from cahier_rag.search.hybrid.core import fuse
from cahier_rag.search.service import HybridSearch, SearchRecipe
from cahier_rag.search.service.control import (
    Budget,
    SearchNotReady,
    SearchTimeout,
    SearchUnavailable,
)
from cahier_rag.search.service.core import H1LexicalSearch
from cahier_rag.search.service.reader import ReadGuard, SearchReader, create_search_engine
from cahier_rag.sources.gdn import GdnReader
from cahier_rag.tuning.lexical import TunedSearch
from cahier_rag.tuning.statistics import build_statistics
from cahier_rag.tuning.vector import AnnConfig, ann_search
from cahier_rag.vector.preparation import TokenConfig


class Encoder:
    def __init__(self):
        self.loads = 0

    def load(self):
        self.loads += 1

    def encode_queries(self, inputs):
        yield SimpleNamespace(vectors=[[1.0] + [0.0] * 1023])

    def close(self):
        pass


pytestmark = pytest.mark.integration


@pytest.fixture
def service_corpus(pg_source):
    raw = os.getenv("RAG_STORAGE_TEST_DATABASE_URL")
    if not raw:
        pytest.skip("RAG_STORAGE_TEST_DATABASE_URL requise")
    settings = load_settings(environ={"RAG_DATABASE_URL": raw})
    url = settings.require_rag_url()
    if not url.database.endswith("_test"):
        pytest.fail("Le stockage doit être une base _test")
    target = create_rag_engine(settings)
    guard = DatabaseGuard(pg_source["engine"], target)
    store = FullStore(guard, "full")
    created = False
    try:
        with guard.transaction() as (connection, _):
            assert (
                connection.execute(
                    text("SELECT version_num FROM public.rag_alembic_version")
                ).scalar_one()
                == "rag_0007"
            )
            if connection.execute(
                text("SELECT 1 FROM rag_full.spaces WHERE space_id='full'")
            ).first():
                pytest.skip("Espace full de test déjà utilisé ; aucune donnée existante modifiée")
        manifest = dict(
            audit_source=guard.source_identity().to_dict(),
            space="full",
            corpus="gdn-2019",
            model=MODELS["bge-m3"].to_dict(),
            tokens=TokenConfig().to_dict(),
            normalize=True,
            storage="float32",
        )
        store.initialize(manifest, 5)
        created = True
        batch = GdnReader(
            pg_source["engine"], contribution_id=pg_source["contributions"][0]
        ).read_batch(max_documents=5)
        store.commit_documents(batch, store.state())
        store.finish_extraction()
        vector = [1.0] + [0.0] * 1023
        segments = []
        for index, document in enumerate(batch.documents):
            offsets = [(0, 2), (1, len(document.text))] if index == 0 else [(0, len(document.text))]
            for segment_index, (start, end) in enumerate(offsets):
                metadata = prepare_metadata(
                    document, store.state()["recipe_hash"], start, end, segment_index, 3
                )
                segments.append(
                    {
                        key: metadata[key]
                        for key in (
                            "document_id",
                            "segment_index",
                            "representation_id",
                            "start",
                            "end",
                            "tokens",
                            "content_hash",
                        )
                    }
                    | dict(embedding=vector, vector_hash=vector_hash(vector))
                )
        store.commit_vectors(store.state(), 5, segments)
        store.verify()
        build_statistics(store)
        reader = SearchReader(
            create_search_engine(pg_source["engine"].url), create_search_engine(url)
        )
        try:
            yield store, reader, batch.documents
        finally:
            reader.close()
    finally:
        try:
            if created:
                with guard.transaction() as (connection, _):
                    for table in (
                        "rag_tuning.term_statistics",
                        "rag_tuning.statistics",
                        "rag_full.segments",
                        "rag_full.documents",
                        "rag_full.spaces",
                    ):
                        connection.execute(text(f"DELETE FROM {table} WHERE space_id='full'"))
        finally:
            target.dispose()


def test_runtime_matches_h1_and_deduplicates_segments(service_corpus, monkeypatch):
    store, reader, documents = service_corpus
    # Le propriétaire est volontairement refusé par la readiness publique.
    with pytest.raises(SearchNotReady, match="rôle"):
        reader.validate(Budget())
    # Fixtures administrées par le propriétaire : contourner ce seul contrôle
    # ici, jamais dans le service. READ ONLY reste réellement imposé aux deux bases.
    monkeypatch.setattr("cahier_rag.search.service.reader.check_reader_role", lambda c: None)
    service = HybridSearch(reader, Encoder())
    service.start()
    try:
        actual = service.retrieve("Non")
        left = TunedSearch(store).lexical("Non", limit=50)
        right, _ = ann_search(store, [1.0] + [0.0] * 1023, AnnConfig(1000), limit=50)
        reference, _ = fuse({"lexical": left, "vector": right}, k=60)
        assert [(h.document.document_id, h.rrf_score) for h in actual.hits] == [
            (r.document.document_id, r.score) for r in reference
        ]
        assert len(actual.hits) == len(documents) == 5  # Six segments, cinq documents.
        assert len({h.document.answer_id for h in actual.hits}) < len(
            actual.hits
        )  # Autre multiple.
        assert all(h.document.answer_id > 2**53 for h in actual.hits)
        sources = {document.document_id: document for document in documents}
        assert all(h.document == sources[h.document.document_id] for h in actual.hits)
        assert actual.recipe_hash == SearchRecipe().fingerprint
        assert service.retrieve("Non").hits == actual.hits
        assert service.encoder.loads == 1
    finally:
        service.close()


def test_real_readonly_timeout_rollback_and_maintenance_guard(service_corpus):
    store, reader, _ = service_corpus
    budget = Budget()
    guard = ReadGuard(reader.source, reader.target, budget)
    with pytest.raises(SearchUnavailable):
        with guard.transaction() as (connection, _):
            assert connection.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
            connection.execute(text("UPDATE rag_full.spaces SET documents=documents WHERE false"))
    with budget.monitor(), pytest.raises(SearchTimeout):
        with budget.phase("sql", 0.1), guard.transaction() as (connection, _):
            connection.execute(text("SELECT pg_sleep(1)"))
    # Le même pool redevient utilisable après les erreurs.
    with ReadGuard(reader.source, reader.target, Budget()).transaction() as (connection, _):
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
    assert store.state()["verified"]  # Le garde de maintenance est inchangé.


def test_readiness_rejects_stats_drift(service_corpus, monkeypatch):
    store, reader, _ = service_corpus
    monkeypatch.setattr("cahier_rag.search.service.reader.check_reader_role", lambda c: None)
    reader.validate(Budget())
    with store.guard.transaction() as (connection, _):
        connection.execute(
            text(
                "UPDATE rag_tuning.statistics SET corpus_hash='incompatible' WHERE space_id='full'"
            )
        )
    with pytest.raises(SearchNotReady, match="Statistiques"):
        reader.validate(Budget())


def test_read_guard_rejects_same_physical_database(service_corpus):
    _, reader, _ = service_corpus
    guard = ReadGuard(reader.source, reader.source, Budget())
    with pytest.raises(SearchNotReady, match="distinctes"):
        with guard.transaction():
            pytest.fail("Deux URL ne suffisent pas à distinguer physiquement les bases")


def test_generation_change_requires_restart(service_corpus, monkeypatch):
    store, reader, _ = service_corpus
    monkeypatch.setattr("cahier_rag.search.service.reader.check_reader_role", lambda c: None)
    reader.validate(Budget())
    with store.guard.transaction() as (connection, _):
        connection.execute(
            text("UPDATE rag_full.spaces SET chain_hash='next-generation' WHERE space_id='full'")
        )
        connection.execute(
            text(
                "UPDATE rag_tuning.statistics SET corpus_hash='next-generation' WHERE space_id='full'"
            )
        )
    with pytest.raises(SearchNotReady, match="génération"):
        reader.validate(Budget())


@pytest.mark.parametrize("exact_limit", [0, 5000])
def test_question_filter_before_branch_limits(service_corpus, monkeypatch, exact_limit):
    monkeypatch.setattr("cahier_rag.tuning.vector.EXACT_QUESTION_LIMIT", exact_limit)
    store, reader, documents = service_corpus
    monkeypatch.setattr("cahier_rag.search.service.reader.check_reader_role", lambda c: None)
    service = HybridSearch(reader, Encoder(), recipe=SearchRecipe(depth=1, result_limit=2))
    try:
        service.start()
        for qid in {d.question_id for d in documents}:
            left = H1LexicalSearch(store).lexical("Non", limit=1, question_id=qid)
            right, _ = ann_search(store, [1.0] + [0.0] * 1023, limit=1, question_id=qid)
            assert right and all(r.document.question_id == qid for r in right)
            assert all(r.document.question_id == qid for r in left)
            all_results, trace = ann_search(store, [1.0] + [0.0] * 1023, question_id=qid)
            assert len(all_results) == sum(d.question_id == qid for d in documents)
            assert trace["mode"] == ("exact-question" if exact_limit else "ann")
            ranking = service.retrieve("Non", question_id=qid)
            assert ranking.hits and all(h.document.question_id == qid for h in ranking.hits)
        assert not service.retrieve("Non", question_id=1).hits
    finally:
        service.close()
