"""Phase-4 boundaries: no working-database writes in this test suite."""

import json
from dataclasses import asdict
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.documentary_access import DocumentaryRepository, document_url, reference_text
from app.multicorpus_runtime import CommonSnapshot, card
from app.services.search_snapshots import CursorError, SnapshotCache, query_hash
from documentary.local_application import LocalApplicationDestination
from documentary.safety import UnsafeDestination


def request(*, peer="127.0.0.1", host="localhost:8000", token="s" * 40, extra=None):
    headers = {"host": host, "x-documentary-preview": token, **(extra or {})}
    return Request(
        dict(
            type="http",
            method="GET",
            scheme="http",
            server=("127.0.0.1", 8000),
            client=(peer, 1),
            path="/",
            query_string=b"",
            headers=[(k.encode(), v.encode()) for k, v in headers.items()],
        )
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"peer": "203.0.113.8"},
        {"peer": "testclient"},
        {"host": "public.example"},
        {"token": "bad"},
        {"extra": {"x-forwarded-for": "127.0.0.1"}},
        {"extra": {"forwarded": "for=127.0.0.1"}},
    ],
)
def test_preview_rejects_nonlocal_or_spoofed_requests(monkeypatch, kwargs):
    from app.documentary_access import settings

    monkeypatch.setattr(settings, "ENV", "dev")
    repo = DocumentaryRepository(
        None, dict(expected_target={}, local_preview=True, preview_token="s" * 40)
    )
    assert repo.preview(request())
    assert not repo.preview(request(**kwargs))


def test_preview_never_authorized_by_production_setting(monkeypatch):
    from app.documentary_access import settings

    monkeypatch.setattr(settings, "ENV", "prod")
    repo = DocumentaryRepository(
        None, dict(expected_target={}, local_preview=True, preview_token="s" * 40)
    )
    assert not repo.preview(request())
    with pytest.raises(ValueError):
        repo.start()


def test_local_writer_refuses_other_databases_and_non_documentary_mutations():
    for url in [
        "postgresql+psycopg2://localhost/cahier_rag",
        "postgresql+psycopg2:///production?host=/var/run/postgresql",
        "postgresql+psycopg2:///cahier_rag?host=/tmp",
        "postgresql+psycopg2:///cahier_rag?host=/var/run/postgresql&service=other",
    ]:
        with pytest.raises(UnsafeDestination):
            LocalApplicationDestination(url)
    destination = LocalApplicationDestination(
        "postgresql+psycopg2:///cahier_rag?host=/var/run/postgresql"
    )
    try:
        for sql in [
            "UPDATE rag_full.documents SET record=NULL",
            "DROP SCHEMA rag_full CASCADE",
            "ALTER ROLE cahier_search_reader SUPERUSER",
            "DELETE FROM public.rag_alembic_version",
        ]:
            with pytest.raises(UnsafeDestination):
                destination._restrict(
                    SimpleNamespace(info={"documentary_write": True}), None, sql, None, None, None
                )
        with pytest.raises(UnsafeDestination):
            destination._restrict(
                SimpleNamespace(info={}),
                None,
                "UPDATE rag_full.spaces SET verified=false",
                None,
                None,
                None,
            )
        with pytest.raises(UnsafeDestination):
            with destination.transaction():
                pass
    finally:
        destination.close()


def test_snapshot_contains_only_references_and_binds_corpus_visibility():
    item = dict(
        key="2019:1",
        corpus="2019",
        document_id="1",
        rank=1,
        witness=dict(
            unit_id="unit",
            title="PRIVATE TITLE",
            branch="lexical",
            content_hash="hash",
            start_offset=0,
            end_offset=2,
        ),
        source_units=[
            dict(
                unit_id="unit",
                content_hash="hash",
                unit_type="open_answer",
                unit_index=0,
                text="PRIVATE TEXT",
            )
        ],
    )
    ref = card(item)
    assert "PRIVATE" not in json.dumps(asdict(ref))
    binding = json.dumps(dict(q="mot", corpus="2019", preview=True), sort_keys=True)
    snap = CommonSnapshot(
        query_hash(binding), 20, {"2019": {}}, "recipe", "version", 50, 50, (ref,)
    )
    cache = SnapshotCache("key" * 20)
    sid, _ = cache.put(snap)
    cursor = cache.cursor(sid, 0)
    assert cache.get(cursor, binding, 20)[1] is snap
    for changed in [
        dict(q="mot", corpus="tous", preview=True),
        dict(q="mot", corpus="2019", preview=False),
    ]:
        with pytest.raises(CursorError):
            cache.get(cursor, json.dumps(changed, sort_keys=True), 20)


def test_links_pin_the_release_and_unicode_passage_identity():
    assert (
        document_url("cahier:Été", "release-1", "passage:😀")
        == "/parcourir/1789/release-1/documents/cahier%3A%C3%89t%C3%A9?unit=passage%3A%F0%9F%98%80#passage-passage%3A%F0%9F%98%80"
    )
    assert reference_text(["Volume I", "pp. 1–2"]) == "Volume I\npp. 1–2"


def test_read_policy_never_confuses_verified_with_public():
    release = dict(
        state="verified",
        publication_authorized=False,
        source_manifest_hash="source",
        editorial_hash="editorial",
    )
    repo = DocumentaryRepository(
        None, dict(expected_target={}, source_manifest_hash="source", editorial_hash="editorial")
    )

    class Result:
        def mappings(self):
            return self

        def one_or_none(self):
            return release

        def scalar_one(self):
            return None

    c = SimpleNamespace(execute=lambda *args: Result())
    with pytest.raises(HTTPException) as ex:
        repo.read_gate(c, preview=False)
    assert ex.value.status_code == 404
    assert repo.read_gate(c, preview=True) is release


def test_documentary_model_recipe_must_match_shared_query_model():
    from cahier_rag.embeddings.registry import MODELS

    repo = DocumentaryRepository(None, dict(expected_target={}))
    repo.query_snapshot = "verified-snapshot"
    recipe = dict(
        version="historical-bge-1",
        model=MODELS["bge-m3"].to_dict(),
        input="exact technical passage only",
        precision="bfloat16",
        snapshot_hash="verified-snapshot",
    )
    repo.check_representations(dict(embedding_recipe=recipe))
    for mutation in [
        dict(input="title and question"),
        dict(snapshot_hash="other"),
        dict(precision="int8"),
    ]:
        with pytest.raises(HTTPException) as ex:
            repo.check_representations(dict(embedding_recipe=dict(recipe, **mutation)))
        assert ex.value.status_code == 503


def test_common_and_h1_share_the_original_bounded_snapshot_cache():
    from app.multicorpus_runtime import CommonIntegration

    cache = SnapshotCache("key" * 20)
    backend = SimpleNamespace(
        cache=cache,
        worker=SimpleNamespace(service=SimpleNamespace(reader=SimpleNamespace(target=None))),
    )
    integration = CommonIntegration(backend, dict(expected_target={}))
    try:
        assert integration.cache is cache
        assert integration.cache.max_bytes == 16 * 1024**2
    finally:
        integration.read_executor.shutdown()
        integration.worker._executor.shutdown()
