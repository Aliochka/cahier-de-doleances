"""Consolidation synthétique, caches historiques strictement en lecture seule."""

import hashlib
import json

import pytest

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.cache import Cache
from cahier_rag.judges.contracts import InferenceConfig
from cahier_rag.judges.models import MODELS
from cahier_rag.judges.pipeline import run
from cahier_rag.judges.planning import prepare
from cahier_rag.judges.protocols import V2
from cahier_rag.search.bm25.evaluation import merge_records, reference_metrics, report_comparison
from cahier_rag.search.lexical import CorpusScope
from tests.unit.test_judges import Fake, data, lightweight  # noqa: F401


def test_missing_grades_common_queries_and_no_implicit_zero():
    runs = {
        m: {"q1": ["a", "b"], "q2": ["c", "d"]} for m in ("lexical", "vector", "bm25-A", "bm25-B")
    }
    queries = [
        {"query_id": q, "split": "development", "domain": "test", "category": "theme"}
        for q in ("q1", "q2")
    ]

    def row(grade):
        return {
            "record": {
                "status": "valid" if grade is not None else "invalid",
                "judgment": {"grade": grade} if grade is not None else None,
            }
        }

    reference = {
        "8b": {("q1", "a"): row(3), ("q1", "b"): row(0), ("q2", "c"): row(2), ("q2", "d"): row(2)},
        "14b": {
            ("q1", "a"): row(3),
            ("q1", "b"): row(None),
            ("q2", "c"): row(2),
            ("q2", "d"): row(2),
        },
    }
    metrics, common, filtered = reference_metrics(runs, reference, queries)
    assert common == ["q2"]
    unknown = metrics["14b"]["bm25-A"]["per_query"]["q1"]["5"]
    assert unknown["precision"] is None and unknown["pooled_ndcg"] is None
    assert unknown["coverage"]["unjudged"] == 1 and unknown["mrr"] == 1
    assert filtered["14b"]["lexical"]["aggregates"]["all"]["5"]["precision"]["defined_queries"] == 1
    with pytest.raises(ValueError, match="historique"):
        merge_records(reference["8b"], reference["8b"])


def test_real_pipeline_synthetic_complement_readonly_reuse(request, tmp_path):
    request.getfixturevalue("lightweight")
    _, queries, sample, docs = request.getfixturevalue("data")
    scope = CorpusScope(sample, expected_hash=sample["selected_hash"], expected_size=len(docs))

    class Repo:
        def __init__(self):
            self.scope = scope

        def fetch(self, ids):
            return {d.document_id: d for d in docs if d.document_id in ids}

    repo = Repo()
    runs = {
        m: {q["query_id"]: [d.document_id for d in docs] for q in queries}
        for m in ("lexical", "vector", "bm25-A", "bm25-B")
    }
    technical = {
        "sample_hash": scope.sample_hash,
        "queries_hash": digest(queries),
        "runs_hash": digest(runs),
    }
    technical["manifest_hash"] = digest(technical)
    experiment = tmp_path / "experiment"
    atomic_json(experiment / "runs.json", runs)
    atomic_json(experiment / "report.json", technical)
    old_path = tmp_path / "evaluation/local/rag017/pool"
    new_path = tmp_path / "evaluation/local/rag018/complement/pool"
    old_pairs = [(q["query_id"], d.document_id) for q in queries for d in docs[:3]]
    new_pairs = [(q["query_id"], docs[-1].document_id) for q in queries]
    old = prepare(
        old_path, old_pairs, repo, queries, kind="rag017", source_hashes={}, prompt_version=V2
    )
    pool = [{"query_id": q, "document_id": d, "origins": []} for q, d in new_pairs]
    prepare(
        new_path,
        new_pairs,
        repo,
        queries,
        kind="rag018",
        prompt_version=V2,
        source_hashes={
            "historical_plan": old["manifest_hash"],
            "experiment_hash": technical["manifest_hash"],
            "pool_hash": digest(pool),
        },
    )
    atomic_json(new_path / "pool.json", pool)
    for directory, n in ((old_path, 6), (new_path, 2)):
        cache = Cache(directory.parent / "cache.sqlite3")
        try:
            for model, spec in MODELS.items():
                fake = Fake()
                fake.spec = spec
                fake.prompt_version = V2
                run(directory, fake, InferenceConfig(), cache, limit=n, allow_full=True)
        finally:
            cache.close()
    protected = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in old_path.parent.rglob("*")
        if p.is_file()
    }
    report = report_comparison(tmp_path, experiment, new_path, tmp_path / "report1", scope, queries)
    report_comparison(tmp_path, experiment, new_path, tmp_path / "report2", scope, queries)
    assert (tmp_path / "report1/comparison.json").read_bytes() == (
        tmp_path / "report2/comparison.json"
    ).read_bytes()
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in protected.items())
    assert report["reuse"]["qwen3-8b"]["historical_valid"] == 6
    assert report["reuse"]["qwen3-8b"]["new_valid"] == 2
    rows = json.loads((tmp_path / "report1/qwen3-8b/judgments.json").read_text())
    assert len(rows) == 8 and all(r["judgment_origin"] == "llm" for r in rows)
