"""Classements et candidats humains : aucun jugement ni score de qualité."""

import time
from datetime import datetime, timezone

from cahier_rag.evaluation.sampling import digest
from cahier_rag.search.lexical import Strategy


def run_queries(engine, queries, *, strategy=Strategy.ANSWER, split="development", limit=10):
    strategy = Strategy(strategy)
    if split not in {"development", "evaluation"}:
        raise ValueError("Partition explicite requise.")
    verified = engine.validate()
    rankings = {}
    candidates = []
    timings = []
    for query in queries:
        if query["split"] != split:
            continue
        started = time.perf_counter()
        results = engine.search(query["text"], strategy=strategy, split=split, limit=limit)
        elapsed = (time.perf_counter() - started) * 1000
        rankings[query["query_id"]] = [result.document.document_id for result in results]
        timings.append(
            {"query_id": query["query_id"], "milliseconds": elapsed, "returned": len(results)}
        )
        candidates.extend(
            {
                "query_id": query["query_id"],
                "document_id": result.document.document_id,
                "grade": None,
                "justification": None,
                "judged_at": None,
                "version": "v1",
                "evaluator": None,
            }
            for result in results
        )
    metadata = {
        "sample_hash": engine.scope.sample_hash,
        "configuration": verified["configuration"],
        "strategy": strategy.value,
        "split": split,
        "limit": limit,
        "queries_hash": digest(queries),
        "rankings_hash": digest(rankings),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "timings": timings,
        "quality_metrics": None,
        "warning": "Aucun jugement humain : aucun score de qualité calculé.",
    }
    return rankings, candidates, metadata
