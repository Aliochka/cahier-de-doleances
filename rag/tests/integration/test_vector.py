"""Cosinus pgvector exact et reprise sur documents synthétiques, jamais sur le corpus."""

import json
from copy import deepcopy

import pytest
from sqlalchemy import event, text

from cahier_rag.embeddings.core import EmbeddingEngine
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.evaluation.sampling import digest
from cahier_rag.vector.pipeline import index
from cahier_rag.vector.preparation import TokenConfig, atomic_json, file_hash, segments
from cahier_rag.vector.store import VectorStore, recipe
from tests.integration.test_lexical import lexical  # noqa: F401
from tests.integration.test_storage import rag_databases, stored  # noqa: F401
from tests.unit.test_vector import CharacterTokenizer

pytestmark = pytest.mark.integration


@pytest.fixture
def vector_fixture(request, tmp_path):
    lexical_engine, docs, sample = request.getfixturevalue("lexical")
    scope = lexical_engine.scope
    docs = {d.document_id: d for d in docs}
    groups = [
        list(
            segments(
                docs[did],
                CharacterTokenizer(),
                TokenConfig(128, 8),
                scope.sample_hash,
                scope.documents[did]["split"],
            )
        )
        for did in sorted(scope.documents)
    ]
    # Deux segments explicites d'une unité courte : vérifier que SQL agrège avant LIMIT.
    from cahier_rag.vector.preparation import contextualize, representation_identity

    for n, group in enumerate(groups):
        unit = docs[group[0]["document_id"]]
        if unit.text == "taxe carbone":
            split_group = []
            for segment_index, (start, end) in enumerate(((0, 8), (6, len(unit.text)))):
                item = dict(group[0])
                item.update(
                    start=start,
                    end=end,
                    segment_index=segment_index,
                    text=contextualize(unit.question_text, unit.text[start:end]),
                )
                item["representation_id"] = representation_identity(item)
                item["content_hash"] = digest(
                    {k: v for k, v in item.items() if k != "content_hash"}
                )
                split_group.append(item)
            groups[n] = split_group
            break
    path = tmp_path / "representations.jsonl"
    path.write_text("".join(json.dumps(item) + "\n" for group in groups for item in group))
    manifest = {
        "version": 1,
        "configuration": TokenConfig(128, 8).to_dict(),
        "sample_hash": scope.sample_hash,
        "units": len(scope.documents),
        "segments": sum(map(len, groups)),
        "model": MODELS["bge-m3"].to_dict(),
        "snapshot_hash": "synthetic",
        "data_hash": file_hash(path),
    }
    manifest["manifest_hash"] = digest(manifest)
    atomic_json(tmp_path / "manifest.json", manifest)
    store = VectorStore(lexical_engine.guard, scope, recipe(manifest))
    store.initialize()
    try:
        yield store, groups, docs, tmp_path
    finally:
        with store.guard.transaction() as (connection, _):
            connection.execute(
                text("DELETE FROM rag.vector_spaces WHERE space_id=:id"), {"id": store.space_id}
            )


def vector(first=1.0, second=0.0):
    return [first, second] + [0.0] * 1022


def test_atomic_idempotence_conflict_and_retrieval(vector_fixture):
    store, groups, docs, _ = vector_fixture
    count = len(groups[0])
    store.commit(0, groups[:1], [vector()] * count)
    store.commit(0, groups[:1], [vector()] * count)
    assert store.status()["completed_units"] == 1
    with pytest.raises(ValueError, match="Conflit"):
        store.commit(0, groups[:1], [vector(0, 1)] * count)
    assert store.verify()["units"] == 1
    with pytest.raises(ValueError, match="incomplet"):
        store.search(vector())
    store.commit(1, groups[1:], [vector() for g in groups[1:] for _ in g])
    store.finish()
    matches = store.search(vector(), limit=100)
    expected = sorted(
        did for did, d in store.scope.documents.items() if d["split"] == "development"
    )
    assert [m.document.document_id for m in matches] == expected
    assert all(m.document.to_dict() == docs[m.document.document_id].to_dict() for m in matches)
    assert len({m.document.document_id for m in matches}) == len(matches)
    assert all(str(m.document.contribution_id).startswith("922337") for m in matches)
    other = store.search(vector(), unit_type="other_text", questionnaire_id=10)
    assert len(other) == 1
    assert all(
        store.scope.documents[m.document.document_id]["split"] == "evaluation"
        for m in store.search(vector(), split="evaluation")
    )


def test_atomicity_failure_before_checkpoint(vector_fixture):
    store, groups, _, _ = vector_fixture

    def fail(conn, cursor, statement, params, context, many):
        if "completed_units=completed_units" in statement:
            raise RuntimeError("synthetic interruption")

    event.listen(store.guard.target, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError):
            store.commit(0, groups[:1], [vector()] * len(groups[0]))
    finally:
        event.remove(store.guard.target, "before_cursor_execute", fail)
    assert store.verify()["units"] == 0
    store.commit(0, groups[:1], [vector()] * len(groups[0]))
    assert store.verify()["units"] == 1


class Backend:
    spec = MODELS["bge-m3"]
    precision = "bfloat16"
    dimension = 1024
    max_tokens = 8192
    snapshot_hash = "synthetic"

    def load_tokenizer(self):
        pass

    def load(self):
        pass

    def close(self):
        pass

    def token_lengths(self, texts, role):
        return [len(t) + 2 for t in texts]

    def encode(self, texts, role):
        return [vector() for t in texts]


def test_pipeline_interruption_resume_and_fingerprints(vector_fixture):
    store, _, _, directory = vector_fixture
    first = index(store, EmbeddingEngine(Backend()), directory, unit_batch=1, stop_after=2)
    assert first["interrupted"] and first["units"] == 2
    resumed = index(store, EmbeddingEngine(Backend()), directory, unit_batch=1)
    assert resumed["complete"] and resumed["units"] == 6
    checksum = resumed["vectors_hash"]
    assert index(store, EmbeddingEngine(Backend()), directory)["vectors_hash"] == checksum
    with store.guard.transaction() as (conn, _):
        conn.execute(
            text("DELETE FROM rag.vector_representations WHERE space_id=:id"),
            {"id": store.space_id},
        )
        conn.execute(
            text(
                "UPDATE rag.vector_spaces SET completed_units=0,completed_segments=0,state='building' WHERE space_id=:id"
            ),
            {"id": store.space_id},
        )
    assert (
        index(store, EmbeddingEngine(Backend()), directory, unit_batch=1)["vectors_hash"]
        == checksum
    )


def test_exact_scores_and_max_segment_aggregation(vector_fixture):
    store, groups, _, _ = vector_fixture
    vectors = []
    for n, group in enumerate(groups):
        if len(group) > 1:
            vectors.extend([vector(0, 1), vector(1, 0)])
        else:
            vectors.extend([vector(1, 0) if n % 2 else vector(0, 1)] * len(group))
    store.commit(0, groups, vectors)
    store.finish()
    scores = [r.score for r in store.search(vector(), limit=100)]
    assert scores == sorted(scores, reverse=True)
    assert set(scores) <= {0.0, 1.0}
    assert store.verify(require_complete=True)["complete"]


def test_reject_modified_scope_recipe_and_vectors(vector_fixture):
    store, groups, _, _ = vector_fixture
    changed = deepcopy(store.configuration)
    changed["model"]["revision"] = "wrong"
    with pytest.raises(ValueError):
        VectorStore(store.guard, store.scope, changed)
    with pytest.raises(ValueError):
        store.commit(0, groups[:1], [[1.0]] * len(groups[0]))
    assert store.verify()["units"] == 0


def test_vector_migration_roundtrip_only_on_empty_test_storage(request):
    settings = request.getfixturevalue("rag_databases")
    from alembic import command
    from alembic.config import Config

    from cahier_rag.db import create_rag_engine, source_connection
    from cahier_rag.migrate import upgrade_schema

    target = create_rag_engine(settings)
    try:
        assert target.url.database.endswith("_test")
        with source_connection(target) as connection:
            if connection.execute(text("SELECT count(*) FROM rag.vector_spaces")).scalar_one():
                pytest.skip("Roundtrip réservé au stockage vectoriel de test vide")
        config = Config()
        config.set_main_option("script_location", "cahier_rag:migrations")
        config.attributes["rag_settings"] = settings
        try:
            command.downgrade(config, "rag_0002")
            with source_connection(target) as connection:
                assert (
                    connection.execute(text("SELECT to_regclass('rag.vector_spaces')")).scalar_one()
                    is None
                )
                assert connection.execute(
                    text("SELECT extversion FROM pg_extension WHERE extname='vector'")
                ).scalar_one()
        finally:
            upgrade_schema(settings)
        with source_connection(target) as connection:
            assert (
                connection.execute(
                    text("SELECT version_num FROM public.rag_alembic_version")
                ).scalar_one()
                == "rag_0006"
            )
    finally:
        target.dispose()


def test_missing_segment_is_refused_even_with_complete_state(vector_fixture):
    store, groups, _, _ = vector_fixture
    store.commit(0, groups, [vector() for group in groups for _ in group])
    store.finish()
    with store.guard.transaction() as (connection, _):
        connection.execute(
            text(
                "DELETE FROM rag.vector_representations WHERE space_id=:id AND representation_id=:rid"
            ),
            {"id": store.space_id, "rid": groups[0][0]["representation_id"]},
        )
    with pytest.raises(ValueError):
        store.search(vector())
    with pytest.raises(ValueError):
        store.verify(require_complete=True)


def test_original_content_modification_is_refused(vector_fixture):
    store, groups, _, _ = vector_fixture
    store.commit(0, groups, [vector() for group in groups for _ in group])
    store.finish()
    with store.guard.transaction() as (connection, _):
        connection.execute(
            text("UPDATE rag.text_units SET text='synthetic modification' WHERE document_id=:id"),
            {"id": groups[0][0]["document_id"]},
        )
    with pytest.raises(ValueError):
        store.verify(require_complete=True)
