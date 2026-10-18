"""Expériences descriptives et pooling humain, sans mesure de pertinence."""

import time
from collections import Counter
from datetime import datetime, timezone

from cahier_rag.evaluation.sampling import digest
from cahier_rag.search.flexible import Method, configuration
from cahier_rag.search.lexical import Strategy
from cahier_rag.search.preparation import Preparation

EXPERIMENTS = (
    ("strict-answer", Method.STRICT, Strategy.ANSWER),
    ("partial-answer", Method.PARTIAL, Strategy.ANSWER),
    ("weighted-answer", Method.WEIGHTED, Strategy.ANSWER),
    ("weighted-question", Method.WEIGHTED, Strategy.QUESTION),
    ("weighted-title", Method.WEIGHTED, Strategy.TITLE),
)


def run_experiment(
    engine, queries, *, method, strategy, preparation=Preparation(), split="development", limit=10
):
    if split not in {"development", "evaluation"}:
        raise ValueError("Partition explicite requise.")
    configuration_value = configuration(method, strategy, preparation)
    verified = engine.validate()
    rankings = {}
    details = []
    all_parents = set()
    lengths = Counter()
    for query in queries:
        if query["split"] != split:
            continue
        started = time.perf_counter()
        results = engine.search(
            query["text"],
            method=method,
            strategy=strategy,
            preparation=preparation,
            limit=limit,
            split=split,
        )
        milliseconds = (time.perf_counter() - started) * 1000
        rankings[query["query_id"]] = [r.document.document_id for r in results]
        parents = {(r.document.corpus_id, r.document.contribution_id) for r in results}
        all_parents.update(parents)
        short = sum(len(r.document.text) < 60 for r in results)
        other = sum(r.document.unit_type.value == "other_text" for r in results)
        lengths.update(total=len(results), short=short, other=other)
        details.append(
            {
                "query_id": query["query_id"],
                "milliseconds": milliseconds,
                "returned": len(results),
                "unique_contributions": len(parents),
                "short_lt60": short,
                "other_text": other,
            }
        )
    timings = sorted(d["milliseconds"] for d in details)
    report = {
        "configuration": configuration_value,
        "index_configuration": verified["configuration"],
        "sample_hash": engine.scope.sample_hash,
        "queries_hash": digest(queries),
        "rankings_hash": digest(rankings),
        "split": split,
        "limit": limit,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "details": details,
        "summary": {
            "queries": len(details),
            "queries_with_results": sum(bool(d["returned"]) for d in details),
            "results": lengths["total"],
            "unique_contributions": len(all_parents),
            "short_lt60_fraction": lengths["short"] / lengths["total"]
            if lengths["total"]
            else None,
            "other_text_fraction": lengths["other"] / lengths["total"]
            if lengths["total"]
            else None,
            "median_ms": ((timings[(len(timings) - 1) // 2] + timings[len(timings) // 2]) / 2)
            if timings
            else None,
            "p95_ms": timings[(len(timings) - 1) * 95 // 100] if timings else None,
        },
        "quality_metrics": None,
        "warning": "Couverture et fonctionnement uniquement ; jugements humains absents.",
    }
    return rankings, report


def pool_candidates(queries, sample, runs, *, per_query=20, random_count=2, seed=20261019):
    """runs: méthode -> query_id -> liste ordonnée ; top, milieu et queue conservés."""
    if type(per_query) is not int or not 3 <= per_query <= 100 or not 0 <= random_count < per_query:
        raise ValueError(
            "Entre 3 et 100 candidats, avec une réserve aléatoire inférieure au plafond."
        )
    documents = {d["document_id"]: d for d in sample["documents"]}
    rows = []
    for query in queries:
        if query["split"] != "development":
            continue
        qid = query["query_id"]
        provenance = {}
        proposals = []
        for method, ranking in sorted(runs.items()):
            seen = set()
            values = ranking.get(qid, [])
            for rank, did in enumerate(values, 1):
                if did not in documents or documents[did]["split"] != "development" or did in seen:
                    raise ValueError("Candidat inconnu, dupliqué ou hors développement.")
                seen.add(did)
                provenance.setdefault(did, []).append({"method": method, "rank": rank})
                bucket = 0 if rank <= 3 else 1 if rank <= 10 else 2 if rank <= 20 else 3
                proposals.append((bucket, rank, method, did))
        chosen = []
        # Reserve places for mid/deep ranks instead of taking only the global top.
        buckets = {b: [] for b in range(4)}
        for bucket, rank, method, did in sorted(proposals):
            if did not in buckets[bucket]:
                buckets[bucket].append(did)
        while len(chosen) < per_query - random_count and any(buckets.values()):
            for bucket in range(4):
                while buckets[bucket] and buckets[bucket][0] in chosen:
                    buckets[bucket].pop(0)
                if buckets[bucket] and len(chosen) < per_query - random_count:
                    chosen.append(buckets[bucket].pop(0))
        random_ids = sorted(
            (
                did
                for did, d in documents.items()
                if d["split"] == "development" and did not in chosen
            ),
            key=lambda did: digest([seed, qid, did]),
        )[:random_count]
        selected = chosen + random_ids
        for did in selected:
            doc = documents[did]
            rows.append(
                {
                    "query_id": qid,
                    "document_id": did,
                    "grade": None,
                    "justification": None,
                    "judged_at": None,
                    "version": "v1",
                    "evaluator": None,
                    "found_by": provenance.get(did, []),
                    "random_control": did in random_ids,
                    "corpus_id": doc["corpus_id"],
                    "contribution_id": doc["contribution_id"],
                    "questionnaire_id": doc["questionnaire_id"],
                    "content_hash": doc["content_hash"],
                }
            )
    return rows
