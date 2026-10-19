"""Rerankers simulés : préparation fidèle, déduplication, transactions et reprise."""

import json
import subprocess
import sys
from dataclasses import replace

import pytest

from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType
from cahier_rag.evaluation.sampling import describe, digest
from cahier_rag.reranking.cache import Cache
from cahier_rag.reranking.contracts import Pair, PreparationConfig, validate_scores
from cahier_rag.reranking.pipeline import latency_prefixes, run
from cahier_rag.reranking.planning import iter_units, load_plan, prepare, select_candidates
from cahier_rag.reranking.preparation import contextualize, segments
from cahier_rag.reranking.registry import MODELS
from cahier_rag.search.lexical import CorpusScope


class FakeBackend:
    def __init__(self, model="R1", budget=128):
        self.spec = MODELS[model]
        self.budget = budget
        self.calls = []
        self.device = "cuda"
        self.precision = "bfloat16"
        self.torch = None
        self.load_seconds = 0.01

    def load_tokenizer(self):
        pass

    def token_count(self, query, document):
        return len(query) + len(document) + 6

    def recipe(self):
        return {
            "model": self.spec.to_dict(),
            "budget": self.budget,
            "device": self.device,
            "precision": self.precision,
        }

    def load(self):
        pass

    def synchronize(self):
        pass

    def score(self, pairs):
        self.calls.extend(p.input_hash for p in pairs)
        return [float(len(p.document)) for p in pairs]

    def close(self):
        pass


@pytest.fixture
def plan_data(tmp_path, monkeypatch):
    first = TextUnit(
        "test",
        UnitType.OPEN_ANSWER,
        MAX_BIGINT,
        MAX_BIGINT,
        1,
        4,
        "Oui.",
        "Des transports ?",
        "Test",
        0,
        "text",
    )
    docs = [
        first,
        replace(
            first,
            answer_id=MAX_BIGINT - 1,
            contribution_id=MAX_BIGINT - 1,
            text="Des bus entre villages et gares. École !",
        ),
        replace(
            first,
            answer_id=MAX_BIGINT - 2,
            contribution_id=MAX_BIGINT - 2,
            text="Une longue phrase.\n\n" * 80,
        ),
    ]
    rows = [describe(d) | {"split": "development"} for d in docs]
    sample = {"documents": rows, "selected_hash": digest(rows)}
    scope = CorpusScope(sample, expected_hash=sample["selected_hash"], expected_size=len(docs))
    queries = [
        {
            "query_id": f"q{i}",
            "text": f"Bus {i} ?",
            "split": "development",
            "domain": "test",
            "category": "test",
            "version": "v1",
            "family": str(i),
        }
        for i in range(2)
    ]
    bundle = {
        "runs": {
            name: {q["query_id"]: [d.document_id for d in docs] for q in queries}
            for name in ("H1", "H5", "vector")
        },
        "report": {"manifest_hash": "source"},
    }
    import cahier_rag.reranking.planning as module

    monkeypatch.setattr(
        module, "load_bundle", lambda *a: (bundle, {"frozen_hash": "frozen"}, scope, queries)
    )

    class Repo:
        def __init__(self, *a):
            self.scope = scope

        def fetch(self, ids):
            return {d.document_id: d for d in docs if d.document_id in ids}

    monkeypatch.setattr(module, "LocalDocuments", Repo)

    class Memory:
        peak = 1234

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    monkeypatch.setattr("cahier_rag.reranking.pipeline.MemorySampler", Memory)
    backends = {m: FakeBackend(m) for m in MODELS}
    directory = tmp_path / "plan"
    manifest = prepare(
        tmp_path, directory, backends, PreparationConfig(budget=128, overlap_chars=8)
    )
    return directory, manifest, docs, scope, queries, bundle


def test_common_segmentation_preserves_text_offsets_and_bigints(plan_data):
    directory, manifest, docs, _, _, bundle = plan_data
    _, pairs = select_candidates(bundle)
    assert len(pairs) == len(manifest["pairs"]) == 6
    groups = list(iter_units(directory, manifest))
    for entry, items in groups:
        doc = next(d for d in docs if d.document_id == entry["document_id"])
        assert items[0].start == 0 and items[-1].end == len(doc.text)
        for i, item in enumerate(items):
            assert item.document == contextualize(
                doc.question_text,
                doc.text[item.start : item.end],
                PreparationConfig(budget=128, overlap_chars=8),
            )
            assert max(entry["segments"][i]["tokens"].values()) <= 128
            if i:
                assert item.start == items[i - 1].end - 8
        assert entry["source_hash"] == doc.content_hash
    assert str(MAX_BIGINT) in json.dumps(manifest)
    short = next(items for e, items in groups if e["document_id"] == docs[0].document_id)
    assert len(short) == 1


def test_answer_alternative_overflow_and_configuration(plan_data):
    _, _, docs, *_ = plan_data
    backend = FakeBackend()
    answer = list(segments("q", "Bus ?", docs[1], [backend], PreparationConfig("answer", 128, 8)))
    assert answer[0].document == docs[1].text
    with pytest.raises(ValueError, match="trop long"):
        list(segments("q", "x" * 500, docs[0], [backend], PreparationConfig(budget=128)))
    with pytest.raises(ValueError):
        PreparationConfig(aggregation="mean")
    with pytest.raises(TypeError):
        Pair("q", "d", "h", "query", "doc", 0, 3, 0, grade=3)


def test_atomic_reprise_and_score_reuse(plan_data, tmp_path):
    directory, manifest, *_ = plan_data
    cache = Cache(tmp_path / "scores.sqlite3")
    first = FakeBackend()
    initial = run(directory, "R1", first, cache, stop_after=2)
    assert initial["processed"] == 2 and not initial["complete"]
    second = FakeBackend()
    resumed = run(directory, "R1", second, cache)
    assert resumed["complete"] and resumed["reused"] == 2
    assert len(first.calls) + len(second.calls) == sum(
        len(e["segments"]) for e in manifest["pairs"]
    )
    assert not set(first.calls) & set(second.calls)
    third = FakeBackend()
    repeated = run(directory, "R1", third, cache)
    assert repeated["reused"] == 6 and not third.calls
    progress = json.loads((directory / "R1-progress.json").read_text())
    assert progress["status"] == "complete" and progress["processed"] == 6
    assert resumed["scoring_seconds_cumulative"] == repeated["scoring_seconds_cumulative"]
    cache.close()


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), True])
def test_invalid_output_rejects_entire_batch(plan_data, tmp_path, invalid):
    directory, *_ = plan_data
    backend = FakeBackend()
    backend.score = lambda pairs: [invalid] * len(pairs)
    cache = Cache(tmp_path / "scores.sqlite3")
    with pytest.raises(ValueError, match="invalides"):
        run(directory, "R1", backend, cache)
    assert cache.connection.execute("SELECT count(*) FROM scores").fetchone()[0] == 0
    assert cache.connection.execute("SELECT count(*) FROM batches").fetchone()[0] == 0
    assert json.loads((directory / "R1-progress.json").read_text())["status"] == "error"
    cache.close()


def test_model_recipe_and_plan_corruption_refused(plan_data, tmp_path):
    directory, _, *_ = plan_data
    changed = FakeBackend(budget=256)
    cache = Cache(tmp_path / "scores.sqlite3")
    with pytest.raises(ValueError, match="recette"):
        run(directory, "R1", changed, cache)
    cache.close()
    with (directory / "inputs.jsonl").open("a") as stream:
        stream.write("{}\n")
    with pytest.raises(ValueError, match="modifié"):
        load_plan(directory)


def test_scores_formula_validation_and_cpu_prefix_measurement():
    assert validate_scores([1, 2.0], 2) == [1.0, 2.0]
    with pytest.raises(ValueError):
        validate_scores([1], 2)
    pairs = [{"query_id": "q", "document_id": str(i)} for i in range(50)]
    records = {("q", str(i)): {"batch_id": str(i // 2)} for i in range(50)}
    batches = [
        {
            "batch_id": str(i),
            "query_id": "q",
            "document_ids": [str(i * 2), str(i * 2 + 1)],
            "seconds": 0.1,
        }
        for i in range(25)
    ]
    measures = latency_prefixes({"pairs": pairs}, records, batches)
    assert measures["q"]["10"]["seconds"] == pytest.approx(0.5)
    assert measures["q"]["20"]["seconds"] == pytest.approx(1.0)
    assert measures["q"]["50"]["seconds"] == pytest.approx(2.5)


def test_no_heavy_imports_for_contracts_and_plans():
    code = "import sys; import cahier_rag.reranking; import cahier_rag.reranking.planning; assert not any(k in sys.modules for k in ('torch','transformers','app','fastapi'))"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_reranking_metrics_and_paired_tests():
    from cahier_rag.reranking.evaluation import holm, paired_test, rerank, summarize

    assert rerank(["b", "a", "c"], {"a": 2.0, "b": 2.0, "c": 1.0}) == ["a", "b", "c"]
    with pytest.raises(ValueError):
        rerank(["a", "a"], {"a": 1.0})
    with pytest.raises(ValueError):
        rerank(["a"], {})
    assert paired_test([1.0, 1.0, 1.0]) == 0.25
    assert paired_test([1.0, -1.0]) == 1.0
    assert paired_test([0.0, 0.0]) == 1.0
    assert holm({"a": 0.01, "b": 0.04, "c": 0.03}) == {"a": 0.03, "c": 0.06, "b": 0.06}
    assert summarize([1, 2, 3, 4]) == {"count": 4, "median": 2.5, "p95": 4}


def test_reranking_incomplete_judgments():
    from cahier_rag.search.bm25.evaluation import reference_metrics

    queries = [
        {"query_id": "q", "category": "theme", "domain": "fiscalite", "split": "development"}
    ]
    refs = {
        "judge": {
            ("q", "a"): {"record": {"status": "valid", "judgment": {"grade": 3}}},
            ("q", "b"): {"record": {"status": "invalid", "judgment": None}},
        }
    }
    runs = {"H1": {"q": ["a", "b"]}, "H1+R1": {"q": ["b", "a"]}}
    metrics, common, _ = reference_metrics(runs, refs, queries)
    assert common == []
    for data in metrics["judge"].values():
        assert data["per_query"]["q"]["5"]["precision"] is None
        assert data["per_query"]["q"]["5"]["pooled_ndcg"] is None


def test_cache_atomicity_conflicts_and_readonly(tmp_path):
    cache = Cache(tmp_path / "test.sqlite3")
    key = cache.register({"version": 1})
    good = {"query_id": "q", "document_id": "a", "score": 1.0, "segments": [{"score": 1.0}]}
    bad = {"query_id": "q", "document_id": "b", "score": 1.0, "segments": [{"score": 2.0}]}
    batch = {"batch_id": "lot"}
    with pytest.raises(ValueError):
        cache.commit(key, batch, [good, bad])
    assert cache.get(key, "q", "a") is None
    assert cache.batches(key) == []
    cache.commit(key, batch, [good])
    with pytest.raises(ValueError):
        cache.commit(key, batch, [dict(good, score=2.0, segments=[{"score": 2.0}])])
    assert cache.get(key, "q", "a") == good
    cache.close()
    cache = Cache(tmp_path / "test.sqlite3", readonly=True)
    assert cache.get(key, "q", "a") == good
    cache.close()


def test_search_result_adapter_preserves_bigint_provenance(plan_data):
    from cahier_rag.reranking.results import rerank_results
    from cahier_rag.search.lexical import SearchResult

    docs = plan_data[2]
    original = [SearchResult(d, 0.0) for d in docs]
    records = {d.document_id: {"score": 1.0, "source_hash": d.content_hash} for d in docs}
    ranked = rerank_results(original, records)
    assert {id(r.document) for r in ranked} == {id(d) for d in docs}
    assert ranked[0].document.document_id == min(records)
    assert ranked[0].to_dict()["document"]["answer_id"] == str(ranked[0].document.answer_id)
    with pytest.raises(ValueError):
        rerank_results(original, {})


def test_nine_pipeline_report_reproducible_and_blind(plan_data, tmp_path, monkeypatch):
    import cahier_rag.reranking.evaluation as module

    directory, manifest, docs, scope, queries, bundle = plan_data
    bundle["measurements"] = {
        q["query_id"]: {
            "sources_ms": {"vector": 3.0},
            "attributable_sequential_ms": {"H1": 5.0, "H5": 7.0},
        }
        for q in queries
    }
    cache = Cache(directory.parent / "scores.sqlite3")
    try:
        for model in ("R1", "R2"):
            run(directory, model, FakeBackend(model), cache)
    finally:
        cache.close()
    monkeypatch.setattr(
        module, "load_bundle", lambda *a: (bundle, {"frozen_hash": "frozen"}, scope, queries)
    )
    refs = {
        m: {
            (q["query_id"], d.document_id): {
                "record": {"status": "valid", "judgment": {"grade": i % 4}}
            }
            for q in queries
            for i, d in enumerate(docs)
        }
        for m in ("judge1", "judge2")
    }
    monkeypatch.setattr(module, "historical_references", lambda *a: (refs, {}))
    first = module.report_comparison(tmp_path, directory, tmp_path / "report1")
    second = module.report_comparison(tmp_path, directory, tmp_path / "report2")
    assert first == second
    assert len(first["common_complete_metrics"]["judge1"]) == 9
    assert len(first["paired_tests"]) == 12
    assert first["common_complete_queries"] == ["q0", "q1"]
    assert (tmp_path / "report1/report.md").read_bytes() == (
        tmp_path / "report2/report.md"
    ).read_bytes()
    assert first["judgment_origin"] == "llm" and not first["human_reference"]


def test_gpu_failure_does_not_commit_or_fallback(plan_data):
    directory, _, _, _, _, _ = plan_data
    cache = Cache(directory.parent / "oom.sqlite3")
    backend = FakeBackend()

    def fail(pairs):
        raise RuntimeError("simulated GPU failure")

    backend.score = fail
    with pytest.raises(RuntimeError):
        run(directory, "R1", backend, cache)
    assert cache.connection.execute("SELECT count(*) FROM scores").fetchone()[0] == 0
    assert cache.connection.execute("SELECT count(*) FROM batches").fetchone()[0] == 0
    assert json.loads((directory / "R1-progress.json").read_text())["status"] == "error"
    cache.close()
