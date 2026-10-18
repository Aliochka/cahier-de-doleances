"""v2 : sélection, aveuglement, reprise séparée et mesures de référence poolée."""

import json
import math

import pytest

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.cache import Cache
from cahier_rag.judges.campaign import pool
from cahier_rag.judges.contracts import PROMPT_VERSION, SYSTEM, InferenceConfig, JudgeInput
from cahier_rag.judges.evaluation import contradictions, engine_metrics, measure
from cahier_rag.judges.pipeline import run
from cahier_rag.judges.protocols import V2, plan_limit, resolve
from tests.unit.test_judges import Fake, data, lightweight, small_plan  # noqa: F401


def test_protocol_v1_unchanged_and_v2_intent():
    assert resolve(PROMPT_VERSION) == SYSTEM
    assert plan_limit(PROMPT_VERSION) == 1500 and plan_limit(V2) == 3000
    item = JudgeInput(
        "q", str(2**63 - 1), "hash", "Question ?", "Oui", "Question originale", "Titre"
    )
    v2 = item.messages(V2)
    assert "La note 3 ne récompense pas la longueur" in v2[0]["content"]
    assert "supprimons le Sénat" in v2[0]["content"]
    assert "Créer des lignes de bus" in v2[0]["content"]
    assert str(2**63 - 1) not in v2[1]["content"]
    assert item.messages()[0]["content"] == SYSTEM
    with pytest.raises(ValueError):
        resolve("unknown")


def test_pool_reproducible_deduplicated_and_deep_prefix():
    lex = {f"q{i}": [str(j) for j in range(50)] for i in range(20)}
    vec = {q: [str(j) for j in range(25, 75)] for q in lex}
    runs = {"lexical": lex, "vector": vec, "hybrid": lex}
    deep = {
        "lexical": {q: [str(j) for j in range(100)] for q in lex},
        "vector": {q: [str(j) for j in range(25, 125)] for q in lex},
    }
    rows, meta = pool(
        runs, {"old": [{"query_id": "q0", "document_id": "0"}]}, [], deep, target=2000
    )
    assert len(rows) == len({(r["query_id"], r["document_id"]) for r in rows}) == 2000
    assert meta["initial_union"] == 1500 and meta["added"] == 500
    assert pool(runs, {"old": [{"query_id": "q0", "document_id": "0"}]}, [], deep, target=2000) == (
        rows,
        meta,
    )
    assert any(len(r["origins"]) > 1 for r in rows)
    deep["vector"]["q0"][0] = "bad"
    with pytest.raises(ValueError, match="Préfixe"):
        pool(runs, {}, [], deep, target=2000)


def test_v2_independent_recipe_and_reprise(request, tmp_path):
    directory, manifest, _ = request.getfixturevalue("small_plan")
    request.getfixturevalue("lightweight")
    cache = Cache(tmp_path / "cache.db")
    try:
        first = run(directory, Fake(), InferenceConfig(), cache, limit=8)
        manifest["prompt_version"] = V2
        manifest["prompt_hash"] = digest(resolve(V2))
        manifest.pop("manifest_hash")
        manifest["manifest_hash"] = digest(manifest)
        atomic_json(directory / "manifest.json", manifest)
        with pytest.raises(ValueError, match="Protocole"):
            run(directory, Fake(), InferenceConfig(), cache, limit=8, allow_full=True)
        backend = Fake()
        backend.prompt_version = V2
        stopped = run(
            directory, backend, InferenceConfig(), cache, limit=8, allow_full=True, stop_after=2
        )
        assert first["recipe_hash"] != stopped["recipe_hash"]
        resumed = run(directory, backend, InferenceConfig(), cache, limit=8, allow_full=True)
        assert resumed["complete"] and resumed["counts"]["reused"] == 2 and backend.calls == 8
        progress = json.loads((directory / "qwen3-8b-progress.json").read_text())
        assert progress["counts"]["valid"] == 8
        assert progress["complete"] and progress["eta_seconds"] == 0
        assert len(list((directory / "history").glob("*.json"))) == 2
        cached = run(directory, backend, InferenceConfig(), cache, limit=8, allow_full=True)
        progress = json.loads((directory / "qwen3-8b-progress.json").read_text())
        assert cached["counts"]["reused"] == progress["counts"]["reused"] == 8
        assert progress["complete"] and backend.calls == 8
    finally:
        cache.close()


def test_metrics_missing_is_not_zero_and_pool_idcg():
    grades = {"a": 3, "b": 0, "c": 2}
    value = measure(["b", "a"], grades, k=2, expected=grades)
    assert value["precision"] == 0.5 and value["mrr"] == 0.5
    expected = (7 / math.log2(3)) / (7 + 3 / math.log2(3))
    assert value["pooled_ndcg"] == pytest.approx(expected)
    missing = measure(["b", "a"], {"a": 3, "c": 2}, k=2, expected=grades)
    assert (
        missing["precision"] is None and missing["mrr"] is None and missing["pooled_ndcg"] is None
    )
    assert missing["coverage"]["unjudged"] == 1
    assert value["corpus_reference_complete"] is False


def test_opposite_engine_order_detected():
    queries = [{"query_id": "q", "split": "development", "category": "c", "domain": "d"}]
    runs = {"lexical": {"q": ["a", "b"]}, "vector": {"q": ["b", "a"]}, "hybrid": {"q": ["a", "b"]}}
    result = {
        m: engine_metrics(runs, {"q": g}, queries, {"q": {"a", "b"}})
        for m, g in [("first", {"a": 3, "b": 0}), ("second", {"a": 0, "b": 3})]
    }
    assert any(r["metric"] == "mrr" for r in contradictions(result))
    assert result["first"]["lexical"]["aggregates"]["domain:d"]["5"]["precision"]["mean"] == 0.2
