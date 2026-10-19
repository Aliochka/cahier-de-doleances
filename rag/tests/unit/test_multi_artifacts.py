"""Artefacts réels sur données synthétiques : gel, pooling et caches séparés."""

import hashlib

import pytest

from cahier_rag.annotation.session import atomic_json
from cahier_rag.judges.cache import Cache
from cahier_rag.judges.contracts import InferenceConfig
from cahier_rag.judges.models import MODELS
from cahier_rag.judges.pipeline import run
from cahier_rag.judges.planning import load_plan, prepare
from cahier_rag.judges.protocols import V2
from cahier_rag.search.hybrid.multi.artifacts import (
    FROZEN_INPUTS,
    freeze,
    load_frozen,
    validate_bundle,
)
from cahier_rag.search.hybrid.multi.core import MultiHybridEngine, configuration
from cahier_rag.search.hybrid.multi.evaluation import (
    candidate_pool,
    prepare_pool,
    report_comparison,
)
from cahier_rag.search.hybrid.multi.experiments import experiment
from cahier_rag.search.lexical import CorpusScope
from tests.unit.test_hybrid import FakeEngine
from tests.unit.test_judges import Fake, data, lightweight  # noqa: F401


@pytest.fixture
def bundle_data(request, tmp_path, monkeypatch):
    request.getfixturevalue("lightweight")
    _, queries, sample, docs = request.getfixturevalue("data")
    scope = CorpusScope(sample, expected_hash=sample["selected_hash"], expected_size=len(docs))
    engines = {m: FakeEngine(scope, docs) for m in ("lexical", "vector", "bm25-A", "bm25-B")}
    engine = MultiHybridEngine({m: e.search for m, e in engines.items()}, scope)
    ids = [d.document_id for d in docs]
    expected = {m: {q["query_id"]: ids for q in queries} for m in engines}
    import cahier_rag.search.hybrid.multi.experiments as module

    monkeypatch.setattr(
        module, "baseline_prefixes", lambda *a: (expected, {"manifest_hash": "base"})
    )
    atomic_json(
        tmp_path / "evaluation/local/rag014/development-replay/runs.json",
        {"hybrid": expected["lexical"]},
    )
    frozen = {"frozen_hash": "frozen", "configuration": configuration()}
    bundle = experiment(tmp_path, scope, queries, frozen, tmp_path / "experiment", engine=engine)
    import cahier_rag.search.hybrid.multi.evaluation as evaluation

    monkeypatch.setattr(evaluation, "load_bundle", lambda *args: (bundle, frozen, scope, queries))

    class Repo:
        def __init__(self, *a):
            self.scope = scope

        def fetch(self, chosen):
            return {d.document_id: d for d in docs if d.document_id in chosen}

    monkeypatch.setattr(evaluation, "LocalDocuments", Repo)
    return bundle, frozen, scope, queries, docs, Repo()


def test_bundle_integrity_and_reserved_partition(bundle_data, tmp_path):
    bundle, frozen, scope, queries, docs, _ = bundle_data
    validate_bundle(bundle, scope, queries, frozen)
    sources = {m: FakeEngine(scope, docs).search for m in ("lexical", "vector", "bm25-A", "bm25-B")}
    with pytest.raises(ValueError, match="configuration gelée"):
        experiment(
            tmp_path,
            scope,
            queries,
            frozen,
            tmp_path / "wrong",
            engine=MultiHybridEngine(sources, scope, k=61),
        )
    bundle["runs"]["H5"][queries[0]["query_id"]].append("outside")
    with pytest.raises(ValueError, match="modifié"):
        validate_bundle(bundle, scope, queries, frozen)


def test_frozen_configuration_and_input_fingerprints(bundle_data, tmp_path, monkeypatch):
    _, _, scope, queries, _, _ = bundle_data
    import cahier_rag.search.hybrid.multi.artifacts as module

    monkeypatch.setattr(module, "load_context", lambda root: (scope, queries))
    root = tmp_path / "frozen-root"
    for name in FROZEN_INPUTS:
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("synthetic", encoding="utf-8")
    directory = tmp_path / "config"
    value = freeze(root, directory)
    assert load_frozen(root, directory)[0] == value
    (root / FROZEN_INPUTS[-1]).write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError, match="modifiée"):
        load_frozen(root, directory)


def test_candidate_pool_dedup_and_known_invalid_not_reannotated():
    targets, missing = candidate_pool(
        {"H1": {"q": ["a", "b"]}, "H5": {"q": ["b", "c"]}}, {("q", "a"), ("q", "b")}
    )
    assert len(targets) == 3 and len(targets[1]["origins"]) == 2
    assert missing == [
        {"query_id": "q", "document_id": "c", "origins": [{"method": "H5", "rank": 2}]}
    ]


@pytest.mark.parametrize("mode", ["valid", "invalid", "zero", "complement"])
def test_reports_reuse_and_optional_complement(bundle_data, tmp_path, mode):
    _, _, scope, queries, docs, repo = bundle_data
    old_path = tmp_path / "evaluation/local/rag017/pool"
    newer_path = tmp_path / "evaluation/local/rag018/complement/pool"
    first = [(q["query_id"], d.document_id) for q in queries for d in docs[:3]]
    second = [(q["query_id"], docs[-1].document_id) for q in queries]
    if mode == "complement":
        second = second[:1]
    old = prepare(
        old_path, first, repo, queries, kind="rag017", prompt_version=V2, source_hashes={}
    )
    prepare(
        newer_path,
        second,
        repo,
        queries,
        kind="rag018",
        prompt_version=V2,
        source_hashes={"historical_plan": old["manifest_hash"]},
    )

    def execute(directory, count):
        cache = Cache(directory.parent / "cache.sqlite3")
        try:
            for model, spec in MODELS.items():
                fake = Fake()
                fake.spec = spec
                fake.prompt_version = V2
                if mode == "invalid" and model == "qwen3-14b":
                    fake.generate = lambda batch: ["invalid"] * len(batch)
                elif mode == "zero":
                    fake.generate = lambda batch: (
                        ['{"grade":0,"justification":"Hors sujet.","uncertain":false}'] * len(batch)
                    )
                run(directory, fake, InferenceConfig(), cache, limit=count, allow_full=True)
        finally:
            cache.close()

    execute(old_path, len(first))
    execute(newer_path, len(second))
    protected = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for directory in (old_path.parent, newer_path.parent)
        for p in directory.rglob("*")
        if p.is_file()
    }
    pool = tmp_path / "pool"
    manifest = prepare_pool(tmp_path, tmp_path / "frozen", tmp_path / "experiment", pool)
    if mode == "complement":
        assert manifest["counts"]["new_pairs"] == 1 and manifest["plan_hash"] is not None
        plan = load_plan(pool / "plan")
        assert len(plan["entries"]) == 1
        execute(pool / "plan", 1)
    else:
        assert manifest["counts"]["new_pairs"] == 0 and manifest["plan_hash"] is None
        assert not (pool / "plan").exists() and not (pool / "cache.sqlite3").exists()
    result = report_comparison(
        tmp_path, tmp_path / "frozen", tmp_path / "experiment", pool, tmp_path / "report1"
    )
    report_comparison(
        tmp_path, tmp_path / "frozen", tmp_path / "experiment", pool, tmp_path / "report2"
    )
    assert (tmp_path / "report1/comparison.json").read_bytes() == (
        tmp_path / "report2/comparison.json"
    ).read_bytes()
    assert (tmp_path / "report1/report.md").read_bytes() == (
        tmp_path / "report2/report.md"
    ).read_bytes()
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in protected.items())
    assert (
        result["judgment_origin"] == "llm" and result["reuse"]["qwen3-8b"]["reference_pairs"] == 8
    )
    if mode == "invalid":
        assert result["common_complete_queries"] == []
        assert (
            result["metrics"]["qwen3-14b"]["H1"]["per_query"][queries[0]["query_id"]]["5"][
                "precision"
            ]
            is None
        )
    else:
        assert len(result["common_complete_queries"]) == 2
    if mode == "zero":
        assert (
            result["common_complete_metrics"]["qwen3-8b"]["H1"]["aggregates"]["all"]["5"][
                "pooled_ndcg"
            ]["mean"]
            is None
        )
    if mode == "complement":
        assert result["reuse"]["qwen3-8b"]["new_valid"] == 1
    assert str(2**63 - 1) in (tmp_path / "report1/qwen3-8b/judgments.json").read_text()
