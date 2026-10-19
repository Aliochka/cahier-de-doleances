"""Mesures multi-configurations ; séparer récupération complète et rejeu de fusion."""

import json
import time
from collections import Counter
from itertools import combinations

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.search.hybrid.experiments import summarize
from cahier_rag.search.hybrid.multi.artifacts import (
    LocalDocuments,
    baseline_prefixes,
    restore_sources,
    validate_bundle,
)
from cahier_rag.search.hybrid.multi.core import (
    CONFIGURATIONS,
    Retrieval,
    configuration,
    fuse,
    validated_weights,
)


def fuse_cached(sources):
    hybrids, traces, times = {}, {}, {}
    for name, weights in CONFIGURATIONS.items():
        before = time.perf_counter()
        results, trace = fuse({m: sources[m] for m, _ in weights}, dict(weights), k=60)
        times[name] = 1000 * (time.perf_counter() - before)
        hybrids[name], traces[name] = results[:100], trace
    return Retrieval(
        sources,
        hybrids,
        traces,
        {
            "fusion_ms": times,
            "sources_ms": None,
            "attributable_sequential_ms": None,
            "shared_session_ms": None,
        },
    )


def statistics(runs, traces, sources, scope):
    results = {}
    for name, rankings in runs.items():
        per = {}
        for qid, ids in rankings.items():
            per[qid] = {}
            for k in (10, 50, 100):
                chosen = ids[:k]
                docs = [scope.documents[d] for d in chosen]
                row = {
                    "returned": len(chosen),
                    "contributions": len({(d["corpus_id"], d["contribution_id"]) for d in docs}),
                    "short_lt60": sum(d["length"] < 60 for d in docs),
                    "other_text": sum(d["unit_type"] == "other_text" for d in docs),
                }
                if name in CONFIGURATIONS:
                    weights = dict(CONFIGURATIONS[name])
                    totals = {
                        m: sum(
                            traces[qid][name][d].get(m, {}).get("rrf_contribution", 0)
                            for d in chosen
                        )
                        for m in weights
                    }
                    denominator = sum(totals.values())
                    row["sources"] = {
                        m: {
                            "present": sum(m in traces[qid][name][d] for d in chosen),
                            "exclusive": sum(
                                set(traces[qid][name][d]) - {"rrf"} == {m} for d in chosen
                            ),
                            "rrf_sum": totals[m],
                            "rrf_share": totals[m] / denominator if denominator else None,
                        }
                        for m in weights
                    }
                    row["origin_combinations"] = dict(
                        Counter(
                            "+".join(sorted(set(traces[qid][name][d]) - {"rrf"})) for d in chosen
                        )
                    )
                per[qid][str(k)] = row
        results[name] = {"per_query": per, "totals": {}}
        for k in (10, 50, 100):
            rows = [v[str(k)] for v in per.values()]
            total = {n: sum(r[n] for r in rows) for n in ("returned", "short_lt60", "other_text")}
            total["queries_with_results"] = sum(r["returned"] > 0 for r in rows)
            total["unique_contributions"] = len(
                {
                    (scope.documents[d]["corpus_id"], scope.documents[d]["contribution_id"])
                    for ids in rankings.values()
                    for d in ids[:k]
                }
            )
            if name in CONFIGURATIONS:
                sources_sum = {
                    m: sum(r["sources"][m]["rrf_sum"] for r in rows)
                    for m, _ in CONFIGURATIONS[name]
                }
                denominator = sum(sources_sum.values())
                total["sources"] = {
                    m: {
                        "present": sum(r["sources"][m]["present"] for r in rows),
                        "exclusive": sum(r["sources"][m]["exclusive"] for r in rows),
                        "rrf_share": sources_sum[m] / denominator if denominator else None,
                    }
                    for m in sources_sum
                }
                total["origin_combinations"] = dict(
                    sum((Counter(r["origin_combinations"]) for r in rows), Counter())
                )
            results[name]["totals"][str(k)] = total
    overlaps = {}
    exclusive = {}
    for qid, rows in sources.items():
        sets = {m: {r["document_id"] for r in values} for m, values in rows.items()}
        overlaps[qid] = {
            a + "/" + b: len(sets[a] & sets[b]) for a, b in combinations(sorted(sets), 2)
        }
        exclusive[qid] = {
            m: len(s - set().union(*(v for n, v in sets.items() if n != m)))
            for m, s in sets.items()
        }
    return {"methods": results, "overlaps": overlaps, "exclusive_among_four_sources": exclusive}


def experiment(root, scope, queries, frozen, output, *, engine=None, cached=None):
    """Live : chaque moteur une fois/requête. Cached : aucune récupération/embedding."""
    if (engine is None) == (cached is None):
        raise ValueError("Choisir récupération réelle ou rejeu de fusion.")
    if engine is not None and (
        engine.k != frozen["configuration"]["k"]
        or engine.depth != frozen["configuration"]["depth"]
        or engine.profiles
        != {name: validated_weights(dict(weights)) for name, weights in CONFIGURATIONS.items()}
    ):
        raise ValueError("Moteur différent de la configuration gelée.")
    expected, baseline = baseline_prefixes(root, scope, queries)
    historic = json.loads(
        (root / "evaluation/local/rag014/development-replay/runs.json").read_text()
    )
    sources, traces, measurements = {}, {}, {}
    runs = {m: {} for m in (*expected, *CONFIGURATIONS)}
    repository = (
        LocalDocuments(root / "evaluation/local/rag018/bm25-A.sqlite3", scope) if cached else None
    )
    for q in queries:
        if q["split"] != "development":
            continue
        qid = q["query_id"]
        if engine is not None:
            retrieval = engine.retrieve(q["text"], split="development", limit=100)
        else:
            restored = restore_sources(cached["sources"][qid], repository, scope)
            retrieval = fuse_cached(restored)
        for name, values in retrieval.sources.items():
            ids = [r.document.document_id for r in values]
            if ids != expected[name][qid]:
                raise ValueError("Source différente du préfixe gelé RAG-018.")
            runs[name][qid] = ids
        sources[qid] = {
            m: [
                {
                    "document_id": r.document.document_id,
                    "score": r.score,
                    "content_hash": r.document.content_hash,
                }
                for r in values
            ]
            for m, values in retrieval.sources.items()
        }
        for name, values in retrieval.hybrids.items():
            runs[name][qid] = [r.document.document_id for r in values]
        if runs["H1"][qid][:50] != historic["hybrid"][qid][:50]:
            raise ValueError("H1 ne reproduit pas RAG-014.")
        traces[qid], measurements[qid] = retrieval.traces, retrieval.measurements
    stats = statistics(runs, traces, sources, scope)
    latency = {
        "fusion_ms": {
            name: summarize([m["fusion_ms"][name] for m in measurements.values()])
            for name in CONFIGURATIONS
        }
    }
    if engine is not None:
        latency["sources_ms"] = {
            name: summarize([m["sources_ms"][name] for m in measurements.values()])
            for name in expected
        }
        latency["attributable_sequential_ms"] = {
            name: summarize([m["attributable_sequential_ms"][name] for m in measurements.values()])
            for name in CONFIGURATIONS
        }
        latency["shared_session_ms"] = summarize(
            [m["shared_session_ms"] for m in measurements.values()]
        )
    report = {
        "version": 1,
        "mode": "live" if engine else "cached_fusion_only",
        "frozen_hash": frozen["frozen_hash"],
        "sample_hash": scope.sample_hash,
        "queries_hash": digest(queries),
        "split": "development",
        "configuration": configuration(),
        "baseline_manifest": baseline["manifest_hash"],
        "latency": latency,
        "filters": {"questionnaire_id": None, "unit_type": None},
        "h1_matches_rag014": True,
        "quality_metrics": None,
    }
    bundle = {
        "runs": runs,
        "sources": sources,
        "traces": traces,
        "measurements": measurements,
        "statistics": stats,
    }
    report.update({name + "_hash": digest(value) for name, value in bundle.items()})
    report["manifest_hash"] = digest(report)
    bundle["report"] = report
    validate_bundle(bundle, scope, queries, frozen)
    output.mkdir(parents=True, exist_ok=False)
    for key, value in bundle.items():
        atomic_json(output / (key + ".json"), value)
    return bundle
