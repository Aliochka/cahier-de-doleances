"""Fusion, filtres et candidats synthétiques sans base, GPU ou annotations."""

import json
import subprocess
import sys
from dataclasses import replace
from fractions import Fraction
from types import SimpleNamespace

import pytest

from cahier_rag.contracts import MAX_BIGINT, TextUnit, UnitType
from cahier_rag.evaluation.sampling import describe, digest
from cahier_rag.search.hybrid.core import HybridConfig, HybridEngine, fuse
from cahier_rag.search.hybrid.experiments import compare
from cahier_rag.search.hybrid.pooling import prepare_pool
from cahier_rag.search.lexical import CorpusScope, SearchResult


@pytest.fixture
def corpus():
    docs = [
        TextUnit(
            "test",
            UnitType.OTHER_TEXT if i == 2 else UnitType.OPEN_ANSWER,
            MAX_BIGINT - i,
            MAX_BIGINT - 10 - i,
            1,
            4 if i != 2 else 10,
            "Même texte" if i < 2 else "Autre texte " + str(i),
            "Question ?",
            "Form",
            0,
            "text",
        )
        for i in range(8)
    ]
    metadata = [
        describe(d) | {"split": "evaluation" if i == 7 else "development"}
        for i, d in enumerate(docs)
    ]
    sample = {"documents": metadata, "selected_hash": digest(metadata)}
    scope = CorpusScope(sample, expected_hash=sample["selected_hash"], expected_size=len(docs))
    return docs, scope


def result(doc, score=1.0):
    return SearchResult(doc, score)


def test_rrf_calculation_and_source_scores(corpus):
    docs, _ = corpus
    values, traces = fuse(
        {
            "lexical": [result(docs[0], 99), result(docs[1], 50)],
            "vector": [result(docs[2], 0.9), result(docs[0], 0.8)],
        }
    )
    assert values[0].document == docs[0]
    assert values[0].score == float(Fraction(1, 61) + Fraction(1, 62))
    assert traces[docs[0].document_id]["lexical"]["score"] == 99
    assert traces[docs[0].document_id]["vector"]["rank"] == 2
    assert values[0].to_dict()["document"]["answer_id"] == str(MAX_BIGINT)


def test_ties_empty_and_duplicate_documents(corpus):
    docs, _ = corpus
    rankings = {
        "lexical": [result(docs[0]), result(docs[0]), result(docs[1])],
        "vector": [result(docs[2])],
    }
    values, traces = fuse(rankings)
    assert len(values) == 3
    assert [r.document.document_id for r in values[:2]] == sorted(
        [docs[0].document_id, docs[2].document_id]
    )
    assert traces[docs[1].document_id]["lexical"]["rank"] == 3
    assert fuse({"lexical": [], "vector": []}) == ((), {})
    assert len(fuse({"lexical": [], "vector": [result(docs[0])]})[0]) == 1
    assert fuse(dict(reversed(list(rankings.items())))) == (values, traces)
    assert docs[0].text == docs[1].text and docs[0].contribution_id != docs[1].contribution_id


def test_conflicting_content_and_nonfinite_scores(corpus):
    docs, _ = corpus
    with pytest.raises(ValueError, match="Contenu incompatible"):
        fuse({"lexical": [result(docs[0])], "vector": [result(replace(docs[0], text="changed"))]})
    with pytest.raises(ValueError):
        fuse({"lexical": [result(docs[0], float("nan"))]})


@pytest.mark.parametrize("k,depth", [(0, 50), (-1, 50), (True, 50), (60, 0), (60, 101), (60, 1.5)])
def test_invalid_parameters(k, depth):
    with pytest.raises(ValueError):
        HybridConfig(k, depth)


class FakeEngine:
    def __init__(self, scope, docs):
        self.scope, self.docs = scope, docs
        self.store = SimpleNamespace(scope=scope)
        self.calls = []

    def search(self, query, **filters):
        self.calls.append((query, filters))
        return [
            result(d)
            for d in self.docs
            if self.scope.documents[d.document_id]["split"] == filters["split"]
            and (
                filters["questionnaire_id"] is None
                or d.questionnaire_id == filters["questionnaire_id"]
            )
            and (filters["unit_type"] is None or d.unit_type == filters["unit_type"])
        ][: filters["limit"]]


def engines(corpus, config=HybridConfig(depth=5)):
    docs, scope = corpus
    left = FakeEngine(scope, docs[:4] + docs[7:])
    right = FakeEngine(scope, docs[2:] + docs[1:2])
    return HybridEngine(left, right, scope, config)


def test_engine_filters_same_depth_partition_and_contract(corpus):
    engine = engines(corpus)
    found = engine.search("texte", limit=3, questionnaire_id=10, unit_type="other_text")
    assert len(found) == 1 and isinstance(found[0], SearchResult)
    left = engine.lexical.calls[-1][1]
    right = engine.vector.calls[-1][1]
    assert all(left[k] == right[k] for k in right)
    assert left["limit"] == 5 and left["split"] == "development"
    assert left["method"] == "weighted" and left["strategy"] == "answer"
    assert engine.search("texte", limit=2, split="evaluation")[0].document == corpus[0][7]
    with pytest.raises(ValueError):
        engine.search("texte", limit=6)
    with pytest.raises(ValueError):
        engine.search("texte", split=None)
    with pytest.raises(ValueError):
        engine.search(" ")


def test_incompatible_scope_and_leaking_engine(corpus):
    engine = engines(corpus)
    engine.vector.store = SimpleNamespace(scope=SimpleNamespace(sample_hash="wrong"))
    with pytest.raises(ValueError):
        HybridEngine(engine.lexical, engine.vector, engine.scope)
    engine = engines(corpus)
    engine.vector.search = lambda *a, **k: [result(corpus[0][7])]
    with pytest.raises(ValueError, match="partition"):
        engine.search("texte", limit=3)


def test_experiments_only_execute_development_and_export(corpus):
    engine = engines(corpus)
    queries = [
        {"query_id": "dev", "text": "texte", "split": "development"},
        {"query_id": "eval", "text": "MUST NOT RUN", "split": "evaluation"},
    ]
    bundle = compare(engine, queries, limit=3)
    assert len(engine.lexical.calls) == len(engine.vector.calls) == 1
    assert all(call[0] != "MUST NOT RUN" for call in engine.lexical.calls)
    assert set(bundle["rankings"]["hybrid"]) == {"dev"}
    assert bundle["report"]["quality_metrics"] is None
    assert bundle["report"]["rankings_hash"] == digest(bundle["rankings"])
    assert json.loads(json.dumps(bundle))["rankings"] == bundle["rankings"]
    assert bundle["report"]["measurements"][0]["union"] >= 5


def test_pool_reproducible_new_pairs_and_no_judgments(corpus):
    engine = engines(corpus)
    bundle = compare(
        engine, [{"query_id": "dev", "text": "texte", "split": "development"}], limit=3
    )
    previous = {("dev", corpus[0][0].document_id)}
    rows, manifest = prepare_pool(bundle, engine.scope, previous, per_query=4, seed=42)
    assert (rows, manifest) == prepare_pool(bundle, engine.scope, previous, per_query=4, seed=42)
    assert len(rows) == len({r["document_id"] for r in rows}) == 4
    assert not any(r["already_in_rag010"] for r in rows)
    assert all(r["grade"] is r["judged_at"] is r["evaluator"] is None for r in rows)
    assert all(r["found_by"] for r in rows)
    assert manifest["judgments_created"] is False
    assert {r["contribution_id"] for r in rows} <= {str(d.contribution_id) for d in corpus[0]}
    assert all(engine.scope.documents[r["document_id"]]["split"] == "development" for r in rows)
    rows, manifest = prepare_pool(bundle, engine.scope, previous, per_query=10)
    assert sum(r["already_in_rag010"] for r in rows) == 1
    assert manifest["statistics"]["deficit"] > 0
    bundle["runs"]["hybrid"]["dev"].reverse()
    with pytest.raises(ValueError, match="modifié"):
        prepare_pool(bundle, engine.scope, previous)


def test_imports_and_pooling_do_not_load_gpu_or_annotation():
    code = """
import sys
import sqlalchemy
sqlalchemy.create_engine=lambda *a,**k: (_ for _ in ()).throw(AssertionError('database'))
import cahier_rag.search.hybrid.cli
assert not any(m in sys.modules for m in ('torch','transformers','numpy','fastapi','app','cahier_rag.annotation.session'))
"""
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_pool_rank_bands_origins_seed_and_parent_diversity(corpus):
    base = corpus[0][0]
    docs = [
        replace(base, answer_id=i + 1, contribution_id=100 + i // 2, text=f"Texte {i}")
        for i in range(80)
    ]
    metadata = [describe(d) | {"split": "development"} for d in docs]
    sample = {"documents": metadata, "selected_hash": digest(metadata)}
    scope = CorpusScope(sample, expected_hash=sample["selected_hash"], expected_size=80)
    engine = HybridEngine(FakeEngine(scope, docs[:50]), FakeEngine(scope, docs[30:]), scope)
    bundle = compare(engine, [{"query_id": "dev", "text": "texte", "split": "development"}])
    rows, manifest = prepare_pool(bundle, scope, set(), per_query=20, seed=42)
    assert {r["origin"] for r in rows} == {"common", "lexical_only", "vector_only"}
    assert {tag for r in rows for tag in r["selection_tags"]} >= {
        "top_1_10",
        "middle_11_25",
        "deep_26_plus",
    }
    assert len({r["contribution_id"] for r in rows}) == len(rows)
    different, _ = prepare_pool(bundle, scope, set(), per_query=20, seed=43)
    assert different != rows
    assert manifest["statistics"]["deficit"] == 0


def test_score_rescaling_does_not_affect_rrf(corpus):
    docs, _ = corpus
    a = [result(docs[0], 10), result(docs[1], 1)]
    b = [result(docs[1], 0.9), result(docs[2], 0.5)]
    original, _ = fuse({"lexical": a, "vector": b})
    scaled, _ = fuse({"lexical": [replace(r, score=r.score * 1000000) for r in a], "vector": b})
    assert original == scaled


def test_previous_pairs_reads_only_frozen_candidates(tmp_path, corpus, monkeypatch):
    from pathlib import Path

    from cahier_rag.search.hybrid.cli import previous_pairs

    docs, scope = corpus
    queries = [{"query_id": "dev", "split": "development"}]
    rows = [{"query_id": "dev", "document_id": docs[0].document_id}]
    pool = tmp_path / "pool.json"
    manifest = tmp_path / "manifest.json"
    pool.write_text(json.dumps(rows))
    manifest.write_text(
        json.dumps(
            {
                "pool_hash": digest(rows),
                "candidate_count": 1,
                "sample_hash": scope.sample_hash,
                "queries_hash": digest(queries),
                "split": "development",
            }
        )
    )
    old = Path.read_text
    accessed = []

    def safe_read(path, *args, **kwargs):
        assert path in (pool, manifest), "No session or judgment access allowed"
        accessed.append(path)
        return old(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", safe_read)
    assert previous_pairs(pool, manifest, scope, queries) == {("dev", docs[0].document_id)}
    assert accessed == [pool, manifest]


def test_frozen_manifest_integrity_and_recipe_rejection(tmp_path, corpus):
    import hashlib
    from pathlib import Path

    import cahier_rag.search.hybrid.integrity as integrity
    from cahier_rag.search.flexible import Method, configuration
    from cahier_rag.search.lexical import Strategy
    from cahier_rag.search.preparation import Preparation

    scope = corpus[1]
    queries = [{"query_id": "dev", "text": "texte", "split": "development"}]
    directory = Path(integrity.__file__).resolve().parent.parent
    payload = {
        "sample_hash": scope.sample_hash,
        "queries_hash": digest(queries),
        "configuration": configuration(Method.WEIGHTED, Strategy.ANSWER, Preparation()),
        "implementation_hashes": {
            name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in (
                "lexical.py",
                "preparation.py",
                "flexible.py",
                "experiments.py",
                "flexible_cli.py",
            )
        },
    }
    path = tmp_path / "frozen.json"

    def write(value):
        path.write_text(json.dumps(dict(value, frozen_hash=digest(value))))

    write(payload)
    assert integrity.verify_frozen(path, scope, queries)["sample_hash"] == scope.sample_hash
    payload["implementation_hashes"].pop("lexical.py")
    write(payload)
    with pytest.raises(ValueError):
        integrity.verify_frozen(path, scope, queries)
