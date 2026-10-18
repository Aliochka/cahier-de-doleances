"""Rapport complet synthétique : exports LLM, compatibilité et absence de faux zéros."""

import json

import pytest

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.cache import Cache
from cahier_rag.judges.contracts import InferenceConfig
from cahier_rag.judges.evaluation import report_campaign
from cahier_rag.judges.markdown import render
from cahier_rag.judges.models import MODELS
from cahier_rag.judges.pipeline import run
from cahier_rag.judges.protocols import V2, resolve
from tests.unit.test_judges import Fake, data, lightweight, small_plan  # noqa: F401


@pytest.mark.parametrize("invalid_second", [False, True])
def test_reports_reproducible_and_missing_explicit(request, tmp_path, monkeypatch, invalid_second):
    directory, manifest, scope = request.getfixturevalue("small_plan")
    request.getfixturevalue("lightweight")
    _, queries, sample, docs = request.getfixturevalue("data")
    rows = [
        {
            "query_id": e["query_id"],
            "document_id": e["document_id"],
            "query_hash": digest(
                next(q["text"] for q in queries if q["query_id"] == e["query_id"])
            ),
            "document_hash": e["source_hash"],
            "origins": [],
        }
        for e in manifest["entries"]
    ]
    metadata = {"frozen": "hash"}
    manifest["prompt_version"] = V2
    manifest["prompt_hash"] = digest(resolve(V2))
    manifest["source_hashes"] = {"pool_hash": digest(rows), "frozen_rankings": metadata}
    manifest.pop("manifest_hash")
    manifest["manifest_hash"] = digest(manifest)
    atomic_json(directory / "manifest.json", manifest)
    atomic_json(directory / "pool.json", rows)
    runs = {
        m: {q["query_id"]: [d.document_id for d in docs] for q in queries}
        for m in ("lexical", "vector", "hybrid")
    }
    import cahier_rag.judges.evaluation as module

    monkeypatch.setattr(module, "load_sample", lambda _: sample)
    monkeypatch.setattr(module, "load_queries", lambda _: queries)
    monkeypatch.setattr(module, "load_rankings", lambda *args: (runs, metadata))
    cache = Cache(directory.parent / "cache.sqlite3")
    try:
        for key, spec in MODELS.items():
            backend = Fake()
            backend.prompt_version = V2
            backend.spec = spec
            if invalid_second and key == "qwen3-14b":
                backend.generate = lambda batch: ["bad"] * len(batch)
            run(directory, backend, InferenceConfig(), cache, limit=8, allow_full=True)
    finally:
        cache.close()
    report = report_campaign(tmp_path, directory, tmp_path / "report1")
    report_campaign(tmp_path, directory, tmp_path / "report2")
    assert (tmp_path / "report1/comparison.json").read_bytes() == (
        tmp_path / "report2/comparison.json"
    ).read_bytes()
    assert report["judgment_origin"] == "llm" and not report["human_reference"]
    assert report["execution"]["qwen3-8b"]["passages"] == 1
    assert report["execution"]["qwen3-8b"]["generated_attempts"] == 8
    assert report["execution"]["qwen3-8b"]["seconds"] == report["runs"]["qwen3-8b"]["seconds"]
    left = dict(report, origin_counts={"z": 2, "a": 1})
    right = dict(report, origin_counts={"a": 1, "z": 2})
    assert render(left) == render(right)
    rows = json.loads((tmp_path / "report1/qwen3-8b/judgments.json").read_text())
    assert all(
        r["judgment_origin"] == "llm" and r["model"]["revision"] == MODELS["qwen3-8b"].revision
        for r in rows
    )
    assert str(2**63 - 1) in json.dumps(rows)
    assert (tmp_path / "report1/qwen3-8b/report-rag015.json").exists()
    other = report["metrics"]["qwen3-14b"]["lexical"]["per_query"]["q0"]["5"]
    if invalid_second:
        assert other["precision"] is None and other["pooled_ndcg"] is None
        assert other["coverage"]["unjudged"] == 4 and report["valid_common"] == 0
        assert report["common_complete_queries"] == []
    else:
        assert other["precision"] == 0.8 and other["coverage"]["unjudged"] == 0
        assert report["agreement"]["exact"] == 1
        assert len(report["common_complete_queries"]) == 2
