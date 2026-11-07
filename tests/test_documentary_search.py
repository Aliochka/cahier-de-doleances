"""Historical search invariants; synthetic vectors only in newly created test databases."""

import copy
import json
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from sqlalchemy import text

from documentary.artifacts import DECISIONS, REFERENCE, Artifacts, canonical
from documentary.editorial import load_decisions
from documentary.lab import Handler
from documentary.representations import (
    ELIGIBLE,
    JOIN,
    prepare_lexical,
    vector_hash,
    verify_representations,
)
from documentary.search import HistoricalSearch, fuse, group
from documentary.storage import SCOPE, apply_editorial, import_collection, migrate
from tests.test_documentary import isolated_databases  # noqa: F401


def candidate(doc, unit, score, ordinal=1, **extra):
    return dict(
        document_id=doc,
        unit_id=unit,
        score=score,
        ordinal=ordinal,
        start_offset=0,
        end_offset=10,
        **extra,
    )


def test_group_before_limit_and_deterministic_ties():
    rows = [candidate("long", f"unit-{n}", 1 - n / 1000, n + 1) for n in range(100)]
    rows += [candidate("other", "other-unit", 0.9), candidate("third", "third-unit", 0.85)]
    assert [r["document_id"] for r in group(rows, 3)] == ["long", "other", "third"]
    assert len({r["document_id"] for r in group(rows, 3)}) == 3


def test_rrf_one_vote_per_document_and_witness():
    lexical = group(
        [candidate("a", "same", 1, text_match=True), candidate("b", "lex-b", 0.8, text_match=True)],
        50,
    )
    vector = group([candidate("b", "vec-b", 0.9), candidate("a", "same", 0.8)], 50, vector=True)
    result = fuse(lexical, vector, 50)
    assert [r["document_id"] for r in result] == ["a", "b"]
    assert result[0]["witness_origin"] == "both"
    assert result[1]["witness_origin"] == "vector"


class FakeEncoder:
    backend = SimpleNamespace(snapshot_hash="synthetic-test", precision="bfloat16")

    def encode_queries(self, *args, **kwargs):
        yield SimpleNamespace(vectors=[tuple([1.0] + [0.0] * 1023)])

    def close(self):
        pass


def test_postgres_historical_search(isolated_databases):  # noqa: F811 - imported pytest fixture
    if not REFERENCE.exists():
        pytest.skip("Restore local immutable historical artifacts for the corpus integration test")
    destination = isolated_databases[0]
    artifacts = Artifacts()
    migrate(destination)
    import_collection(destination, artifacts, load_decisions(DECISIONS))
    statistics = prepare_lexical(destination)
    assert statistics["units"] == 10748
    with destination.transaction() as c:
        c.execute(
            text(f"""UPDATE documentary.search_unit u SET embedding=CAST(:v AS public.vector),embedding_hash=:hash
            FROM documentary.document d WHERE u.corpus_id=d.corpus_id AND u.release_id=d.release_id
            AND u.document_id=d.document_id AND {ELIGIBLE}"""),
            dict(
                SCOPE,
                v="[" + ",".join(["1"] + ["0"] * 1023) + "]",
                hash=vector_hash([1.0] + [0.0] * 1023),
            ),
        )
        from cahier_rag.embeddings.registry import MODELS

        c.execute(
            text("""UPDATE documentary.release SET representations_ready=true,
            embedding_recipe=CAST(:recipe AS jsonb)"""),
            {
                "recipe": canonical(
                    {
                        "precision": "bfloat16",
                        "snapshot_hash": "synthetic-test",
                        "version": "historical-bge-1",
                        "model": MODELS["bge-m3"].to_dict(),
                        "input": "exact technical passage only",
                    }
                )
            },
        )
    assert verify_representations(destination)["vectors"] == 10748
    service = HistoricalSearch(destination)
    service.model = FakeEncoder()
    for depth in (50, 100, 200):
        for mode in ("lexical", "vector", "hybrid"):
            result = service.search("Agen agriculture", mode=mode, depth=depth)
            assert len(result["items"]) <= depth
            assert len({r["document_id"] for r in result["items"]}) == len(result["items"])
            assert not any(
                r["witness"]["unit_id"]
                in {
                    "ap1789-technical-passage-1:fffb19e46c6025e22b17d54c370c",
                    "ap1789-technical-passage-1:32ae8c839247d77b503fba421372",
                }
                for r in result["items"]
            )
            assert all(
                artifacts.documents[r["document_id"]]["document_kind"] == "cahier_autonome_probable"
                for r in result["items"]
            )
    result = service.search("Agen", mode="lexical")
    assert any("Agen" in r["title"] for r in result["items"])
    # A controlled derived-field fixture proves metadata-only retrieval without
    # pretending that a real geographic query necessarily lacks body matches.
    with destination.transaction() as c:
        target = c.execute(
            text(
                "SELECT document_id,metadata_vector::text FROM documentary.document WHERE candidate ORDER BY edition_order LIMIT 1"
            )
        ).one()
        c.execute(
            text(
                "UPDATE documentary.document SET metadata_vector=metadata_vector || to_tsvector('french','metadonneesseulesintrouvables') WHERE document_id=:id"
            ),
            {"id": target[0]},
        )
    result = service.search("metadonneesseulesintrouvables", mode="lexical")
    assert result["items"] and all(r["match_origin"] == "metadata" for r in result["items"])
    assert all(r["excerpt_selection"] == "opening" for r in result["items"])
    with destination.transaction() as c:
        c.execute(
            text(
                "UPDATE documentary.document SET metadata_vector=CAST(:v AS tsvector) WHERE document_id=:id"
            ),
            {"id": target[0], "v": target[1]},
        )
    for query in ("Agen agriculture", "Amiens clergé", "Beauvais jurandes"):
        assert service.search(query, mode="lexical")["items"]
    assert service.search("zxqv1789inexistant", mode="lexical")["items"] == []
    assert service.search("roi", mode="hybrid", place="zxqv1789inexistant")["items"] == []
    for kwargs in ({"volume": 1}, {"estate": "clergé"}, {"place": "Agen"}):
        result = service.search("roi", mode="hybrid", **kwargs)
        for item in result["items"]:
            if "volume" in kwargs:
                assert item["metadata"]["volume"] == 1
            if "estate" in kwargs:
                assert "clergé" in item["metadata"]["historical_orders"]
            if "place" in kwargs:
                assert (
                    "agen" in item["title"].lower()
                    or "agen" in item["metadata"]["origin"]["label"].lower()
                )
    with destination.transaction(readonly=True) as c:
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM documentary.document WHERE readable OR searchable OR catalogue_visible"
                )
            ).scalar_one()
            == 0
        )
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM pg_indexes WHERE schemaname='documentary' AND indexdef ILIKE '%hnsw%'"
                )
            ).scalar_one()
            == 0
        )
        assert (
            c.execute(
                text(
                    f"SELECT count(*) FROM {JOIN} WHERE {ELIGIBLE} AND d.document_id LIKE '%2_1_1578'"
                ),
                SCOPE,
            ).scalar_one()
            == 2
        )
        assert (
            c.execute(
                text(
                    f"SELECT count(*) FROM {JOIN} WHERE {ELIGIBLE} AND d.document_id LIKE '%2_1_1602'"
                ),
                SCOPE,
            ).scalar_one()
            == 8
        )
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.search, server.destination = service, destination
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with pytest.raises(HTTPError) as denied:
            urlopen(Request(url, headers={"Host": "production.example"}))
        assert denied.value.code == 403
        excluded = "ap1789-technical-passage-1:fffb19e46c6025e22b17d54c370c"
        with urlopen(url + "/api/document?unit=" + excluded) as response:
            document = json.load(response)
        assert not document["searchable"] and document["warnings"] and document["highlight"]
        other = next(
            d
            for d in artifacts.documents.values()
            if d["document_kind"] != "cahier_autonome_probable"
        )
        with pytest.raises(HTTPError) as denied:
            urlopen(url + "/api/document?unit=" + other["passage_ids"][0])
        assert denied.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    service.lock.acquire()
    try:
        with pytest.raises(RuntimeError, match="busy"):
            service.search("Agen")
    finally:
        service.lock.release()
    previous = load_decisions(DECISIONS)
    changed = copy.deepcopy(previous)
    changed["revision_id"] = "synthetic-historical-reintegration"
    changed["decisions"].append(
        dict(
            previous["decisions"][0],
            decision_id="synthetic-phase2-reintegration",
            revision_id=changed["revision_id"],
            sequence=1,
            value=True,
            supersedes_id=previous["decisions"][0]["decision_id"],
        )
    )
    apply_editorial(destination, artifacts, previous, changed)
    with destination.transaction(readonly=True) as c:
        assert (
            c.execute(
                text("SELECT representations_ready OR statistics_ready FROM documentary.release")
            ).scalar_one()
            is False
        )
        assert (
            c.execute(
                text("SELECT count(*) FROM documentary.search_unit WHERE embedding IS NOT NULL")
            ).scalar_one()
            == 10748
        )
    with pytest.raises(ValueError):
        service.search("roi", mode="hybrid")
    service.close()
