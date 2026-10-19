"""Expériences BM25 figées et pooling complémentaire sans lire de notes humaines."""

import json
import time
from collections import defaultdict
from itertools import combinations

from cahier_rag.annotation.reporting import load_rankings
from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.planning import load_plan, prepare
from cahier_rag.judges.protocols import V2
from cahier_rag.search.hybrid.experiments import summarize


def validate_runs(runs, scope, queries):
    qids = {q["query_id"] for q in queries if q["split"] == "development"}
    if set(runs) != {"lexical", "vector", "bm25-A", "bm25-B"}:
        raise ValueError("Quatre méthodes attendues.")
    for rankings in runs.values():
        if set(rankings) != qids:
            raise ValueError("Requêtes inconnues, réservées ou manquantes.")
        for ids in rankings.values():
            if len(ids) != len(set(ids)) or any(
                did not in scope.documents or scope.documents[did]["split"] != "development"
                for did in ids
            ):
                raise ValueError("Documents dupliqués ou hors développement.")


def compare(root, indexes, scope, queries, output):
    sample = json.loads((root / "evaluation/local/rag007/corpus.json").read_text())
    baselines, meta = load_rankings(root / "evaluation/local/rag018/baselines100", queries, sample)
    previous, old_meta = load_rankings(root / "evaluation/local/rag017/deepening", queries, sample)
    if meta["baselines"] != old_meta["baselines"] or baselines != previous:
        raise ValueError("Rejeu des moteurs gelés différent des références historiques.")
    runs = {m: baselines[m] for m in ("lexical", "vector")}
    times, recipes = {}, {}
    for name, engine in indexes.items():
        recipes[name] = engine.verify()
        ranks, latencies = {}, {}
        for q in queries:
            if q["split"] != "development":
                continue
            started = time.perf_counter()
            found = engine.search(q["text"], limit=100, split="development")
            latencies[q["query_id"]] = 1000 * (time.perf_counter() - started)
            ranks[q["query_id"]] = [r.document.document_id for r in found]
        runs[name], times[name] = ranks, latencies
    validate_runs(runs, scope, queries)
    baseline_report = json.loads(
        (root / "evaluation/local/rag018/baselines100/report.json").read_text()
    )
    for name, key in (("lexical", "lexical_ms"), ("vector", "vector_ms")):
        times[name] = {m["query_id"]: m[key] for m in baseline_report["measurements"]}
    description = {}
    for k in (50, 100):
        description[str(k)] = {}
        for name, ranks in runs.items():
            per = {}
            for qid, ids in ranks.items():
                docs = [scope.documents[d] for d in ids[:k]]
                per[qid] = {
                    "returned": len(docs),
                    "contributions": len({(d["corpus_id"], d["contribution_id"]) for d in docs}),
                    "short_lt60": sum(d["length"] < 60 for d in docs),
                    "other_text": sum(d["unit_type"] == "other_text" for d in docs),
                }
            description[str(k)][name] = {
                "per_query": per,
                "queries_with_results": sum(bool(x["returned"]) for x in per.values()),
                "latency_ms_top100": summarize(list(times[name].values())),
                "results": sum(x["returned"] for x in per.values()),
                "short_lt60": sum(x["short_lt60"] for x in per.values()),
                "other_text": sum(x["other_text"] for x in per.values()),
                "unique_contributions": len(
                    {
                        (scope.documents[d]["corpus_id"], scope.documents[d]["contribution_id"])
                        for ids in ranks.values()
                        for d in ids[:k]
                    }
                ),
            }
    overlaps = {
        str(k): {
            a + "/" + b: {
                qid: len(set(runs[a][qid][:k]) & set(runs[b][qid][:k])) for qid in runs[a]
            }
            for a, b in combinations(sorted(runs), 2)
        }
        for k in (50, 100)
    }
    report = {
        "sample_hash": scope.sample_hash,
        "queries_hash": digest(queries),
        "split": "development",
        "runs_hash": digest(runs),
        "recipes": recipes,
        "baseline_metadata": meta,
        "description": description,
        "overlaps": overlaps,
        "latencies_ms": times,
    }
    report["manifest_hash"] = digest(report)
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "runs.json", runs)
    atomic_json(output / "report.json", report)
    return report


def load_experiment(directory, scope, queries):
    runs = json.loads((directory / "runs.json").read_text())
    report = json.loads((directory / "report.json").read_text())
    payload = {k: v for k, v in report.items() if k != "manifest_hash"}
    if (
        digest(payload) != report["manifest_hash"]
        or digest(runs) != report["runs_hash"]
        or report["sample_hash"] != scope.sample_hash
        or report["queries_hash"] != digest(queries)
    ):
        raise ValueError("Expérience BM25 modifiée ou incompatible.")
    validate_runs(runs, scope, queries)
    return runs, report


def complement_pairs(runs, previous):
    historical = {(e["query_id"], e["document_id"]) for e in previous["entries"]}
    origins = defaultdict(list)
    for name in ("bm25-A", "bm25-B"):
        for qid, ids in sorted(runs[name].items()):
            for rank, did in enumerate(ids[:50], 1):
                origins[qid, did].append({"method": name, "rank": rank})
    return [
        dict(query_id=q, document_id=d, origins=origins[q, d])
        for q, d in sorted(set(origins) - historical)
    ], {
        "bm25_unique_pairs_top50": len(origins),
        "historical_pairs_reused": len(set(origins) & historical),
        "new_pairs": len(set(origins) - historical),
        "historical_invalid_policy": "preserved as missing; not reannotated",
    }


def prepare_complement(root, directory, repository, queries, experiment):
    runs, report = load_experiment(experiment, repository.scope, queries)
    old = load_plan(root / "evaluation/local/rag017/pool")
    if (
        old["sample_hash"] != repository.scope.sample_hash
        or old["query_hash"] != digest(queries)
        or old["prompt_version"] != V2
    ):
        raise ValueError("Ancien plan incompatible.")
    rows, counts = complement_pairs(runs, old)
    if not rows:
        raise ValueError("Aucun nouveau couple ; aucune inférence nécessaire.")
    manifest = prepare(
        directory,
        [(r["query_id"], r["document_id"]) for r in rows],
        repository,
        queries,
        kind="rag018",
        prompt_version=V2,
        source_hashes={
            "historical_plan": old["manifest_hash"],
            "experiment_hash": report["manifest_hash"],
            "pool_hash": digest(rows),
            "counts": counts,
        },
    )
    atomic_json(directory / "pool.json", rows)
    return manifest
