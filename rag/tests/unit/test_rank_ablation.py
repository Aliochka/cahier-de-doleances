"""Contrats d'ablation : rangs RRF historiques, inconnus et groupes coupés."""

import importlib.util
from pathlib import Path

from cahier_rag.search.hybrid.core import fuse
from tests.unit.test_hybrid import corpus, result  # noqa: F401

spec = importlib.util.spec_from_file_location(
    "rank_ablation", Path(__file__).resolve().parents[2] / "scripts/evaluate_rank_ablation.py"
)
ablation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ablation)


def test_rrf_matches_historical_fusion(corpus):  # noqa: F811
    docs, _ = corpus
    lexical, vector = docs[:6], list(reversed(docs[2:7]))
    expected, _ = fuse(
        {"lexical": [result(d) for d in lexical], "vector": [result(d) for d in vector]}
    )
    assert ablation.rrf([d.document_id for d in lexical], [d.document_id for d in vector]) == [
        r.document.document_id for r in expected
    ]


def test_unjudged_top10_is_undefined_and_cannot_enter_paired_means():
    ids = [str(i) for i in range(10)]
    runs = {
        f"{family}:{v}": {"q": ids} for family in ("lexical", "hybrid") for v in ablation.VARIANTS
    }
    runs["lexical:sans-rang"] = {"q": ids[:-1] + ["unknown"]}
    references = {
        m: {("q", did): {"record": {"status": "valid", "judgment": {"grade": 3}}} for did in ids}
        for m in ("judge-a", "judge-b")
    }
    metrics, paired = ablation.evaluate_runs(runs, references)
    assert metrics["judge-a"]["lexical:sans-rang"]["q"]["precision"] is None
    assert metrics["judge-a"]["lexical:sans-rang"]["q"]["pooled_ndcg"] is None
    assert paired["lexical"]["precision"]["queries"] == []
    assert paired["hybrid"]["pooled_ndcg"]["means"]["judge-a"]["hybrid:original"] == 1.0


def test_boundary_ties_include_candidates_beyond_depth50():
    rows = [(f"{i:03}", 0.8) for i in range(70)]
    stats = ablation.tie_statistics(rows)
    assert stats["50"]["boundary_group_size"] == 70
    assert stats["50"]["boundary_group_selected"] == 50
    assert stats["10"]["boundary_straddles_cutoff"]
    assert set(d for d, _ in rows[:10]).isdisjoint(d for d, _ in ablation.reverse_ties(rows)[:10])
