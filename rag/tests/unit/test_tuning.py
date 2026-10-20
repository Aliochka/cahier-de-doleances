"""Configurations, métriques descriptives et isolation des caches RAG-027."""

from dataclasses import replace

import pytest

from cahier_rag.personal.campaign import Cache
from cahier_rag.tuning.experiments import compare_rankings, latency_summary
from cahier_rag.tuning.vector import AnnConfig


@pytest.mark.parametrize(
    "changes",
    [
        {"ef_search": True},
        {"ef_search": 1001},
        {"candidates": 0},
        {"iterative": "relaxed_order"},
        {"max_scan_tuples": 0},
        {"scan_mem_multiplier": 5},
    ],
)
def test_ann_parameters(changes):
    with pytest.raises(ValueError):
        replace(AnnConfig(), **changes)


def test_identity_text_and_context_overlap_are_distinct():
    exact = [
        dict(document_id="9007199254740993", text_hash="same", context_hash="q1", score=0.9),
        dict(document_id="2", text_hash="other", context_hash="q2", score=0.8),
    ]
    ann = [
        dict(document_id="other-citizen", text_hash="same", context_hash="q1", score=0.9),
        dict(document_id="new", text_hash="other", context_hash="q3", score=0.7),
    ]
    result = compare_rankings(exact, ann, 2)
    assert result["id_overlap"] == 0 and result["text_overlap"] == 1
    assert result["context_overlap"] == 0.5
    assert result["distance_regret"] == pytest.approx(0.05)
    assert len(result["missing_ids"]) == 2


def test_no_judgment_or_empty_metric():
    assert compare_rankings([], [], 10)["id_overlap"] is None
    assert latency_summary([]) is None
    assert latency_summary([1, 4, 2, 3]) == dict(n=4, minimum=1, median=2.5, p95=4, maximum=4)


def test_explicit_cache_namespace_and_resume(tmp_path):
    path = tmp_path / "rag027" / "personal.sqlite3"
    with pytest.raises(ValueError):
        Cache(path)
    cache = Cache(path, namespace="rag027")
    cache.put("key", {"human": False})
    cache.close()
    cache = Cache(path, namespace="rag027")
    assert cache.get("key") == {"human": False}
    cache.close()
    with pytest.raises(ValueError):
        Cache(path, namespace="rag026")


def test_selection_integrity_and_corpus(tmp_path):
    import json

    from cahier_rag.tuning.selection import load_selection, save_selection

    for name in ("lexical.json", "vector.json", "selection-policy.json"):
        (tmp_path / name).write_text("{}")
    selection = save_selection(tmp_path, "corpus")
    assert not selection["qualified"]
    assert load_selection(tmp_path / "selection.json", "corpus") == selection
    with pytest.raises(ValueError, match="incompatible"):
        load_selection(tmp_path / "selection.json", "another-corpus")
    selection["ann"]["ef_search"] = 400
    (tmp_path / "selection.json").write_text(json.dumps(selection))
    with pytest.raises(ValueError, match="modifiée"):
        load_selection(tmp_path / "selection.json", "corpus")


def test_cached_fusion_matches_runtime_and_preserves_occurrences():
    from types import SimpleNamespace

    from cahier_rag.search.hybrid.core import fuse
    from cahier_rag.search.lexical import SearchResult
    from cahier_rag.tuning.report import fusion

    left = [dict(document_id="9007199254740993", score=0.8), dict(document_id="other", score=0.5)]
    right = [dict(document_id="other", score=0.7), dict(document_id="third", score=0.4)]

    def objects(rows):
        return [
            SearchResult(
                SimpleNamespace(document_id=r["document_id"], content_hash="same-text"), r["score"]
            )
            for r in rows
        ]

    actual, _ = fuse({"lexical": objects(left), "vector": objects(right)}, k=60)
    assert [(r["document_id"], r["score"]) for r in fusion([left, right])] == [
        (r.document.document_id, r.score) for r in actual
    ]
    assert len(fusion([left, [], right])) == 3


def test_report_is_reproducible_except_measured_fusion_cost():
    from cahier_rag.tuning.report import fusion

    rows = [dict(document_id="b", score=0.9), dict(document_id="a", score=0.9)]
    assert fusion([rows, []]) == fusion([rows, []])
    assert [x["document_id"] for x in fusion([rows, list(reversed(rows))])] == ["a", "b"]


def test_local_state_identifies_optimized_corpus_without_models():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from cahier_rag.personal.web import create_app

    with TestClient(
        create_app(lambda q, p: None, corpus="rag026", search_profile="rag027", ann=True),
        base_url="http://127.0.0.1:8770",
        client=("127.0.0.1", 1234),
    ) as client:
        state = client.get("/api/state").json()
        assert state["search_profile"] == "rag027"
        assert state["vector_search"] == "ANN"
        assert "approximatif" in state["scope"]


def test_report_refuses_modified_measurements(tmp_path):
    import json

    from cahier_rag.tuning.report import summarize
    from cahier_rag.tuning.selection import save_selection

    for name in ("lexical.json", "vector.json", "selection-policy.json"):
        (tmp_path / name).write_text("{}")
    save_selection(tmp_path, "corpus")
    (tmp_path / "vector-recipe.json").write_text(json.dumps({"corpus_hash": "corpus"}))
    (tmp_path / "vector.json").write_text('{"modified":true}')
    with pytest.raises(ValueError, match="Mesures modifiées"):
        summarize(tmp_path)
