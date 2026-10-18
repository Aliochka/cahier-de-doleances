"""Références LLM séparées ; nDCG explicitement limité au pool jugé."""

from collections import Counter, defaultdict
from itertools import combinations

from cahier_rag.annotation.reporting import evaluate_report, load_rankings
from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.cli import load_sample
from cahier_rag.evaluation.files import load_json, load_queries, validate_judgments
from cahier_rag.evaluation.metrics import evaluate
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.cache import Cache
from cahier_rag.judges.comparison import agreement
from cahier_rag.judges.models import MODELS
from cahier_rag.judges.planning import iter_inputs, load_plan
from cahier_rag.judges.protocols import V2, resolve

KS = (5, 10, 20, 50)


def execution_summary(directory, key, latest):
    """Additionner les passages, sans confondre lecture du cache et débit GPU."""
    passages = {}
    for path in sorted((directory / "history").glob(key + "-*.json")):
        passage = load_json(path)
        if path.name != key + "-" + digest(passage) + ".json":
            raise ValueError("Historique de passage modifié.")
        if (
            passage["recipe_hash"] == latest["recipe_hash"]
            and passage["plan_hash"] == latest["plan_hash"]
        ):
            passages[digest(passage)] = passage
    passages[digest(latest)] = latest
    values = list(passages.values())
    seconds = sum(r["seconds"] for r in values)
    generated = sum(r["counts"]["processed"] - r["counts"]["reused"] for r in values)
    return {
        "passages": len(values),
        "seconds": seconds,
        "load_seconds": sum(r["load_seconds"] for r in values),
        "generated_attempts": generated,
        "attempts_per_second_including_load": generated / seconds if seconds else None,
        "input_tokens": sum(r["input_tokens"] for r in values),
        "output_tokens_excluding_eos": sum(r["output_tokens_excluding_eos"] for r in values),
        "peak_rss_bytes": max(r["peak_rss_bytes"] for r in values),
        "peak_allocated_bytes": max(
            r.get("hardware", {}).get("peak_allocated_bytes", 0) for r in values
        ),
    }


def measure(ranking, grades, *, k, expected):
    if set(grades) - set(expected):
        raise ValueError("Jugement extérieur au pool.")
    strict = evaluate(ranking, grades, k=k, complete=False)
    pool_complete = set(grades) == set(expected)
    pooled = evaluate(ranking, grades, k=k, complete=pool_complete)
    top = ranking[:k]
    known = [d for d in top if d in grades]
    return {
        "precision": strict["precision_at_k"],
        "mrr": strict["mrr"],
        "pooled_ndcg": pooled["ndcg_at_k"] if pool_complete else None,
        "relevant_fraction": sum(grades[d] >= 2 for d in known) / len(top)
        if top and len(known) == len(top)
        else None,
        "coverage": {"returned": len(top), "judged": len(known), "unjudged": len(top) - len(known)},
        "grade_distribution": dict(sorted(Counter(grades[d] for d in known).items())),
        "pool_reference_complete": pool_complete,
        "pool_reference_size": len(expected),
        "corpus_reference_complete": False,
    }


def summarize(rows):
    return {
        metric: {
            "mean": sum(known) / len(known) if known else None,
            "defined_queries": len(known),
            "total_queries": len(rows),
        }
        for metric in ("precision", "mrr", "pooled_ndcg", "relevant_fraction")
        for known in [[row[metric] for row in rows if row[metric] is not None]]
    }


def engine_metrics(runs, judgments, queries, expected):
    result = {}
    for method, rankings in sorted(runs.items()):
        per = {
            qid: {
                str(k): measure(ids[:50], judgments.get(qid, {}), k=k, expected=expected[qid])
                for k in KS
            }
            for qid, ids in sorted(rankings.items())
        }
        groups = defaultdict(list)
        for q in queries:
            if q["split"] == "development":
                for group in ("all", "domain:" + q["domain"], "category:" + q["category"]):
                    groups[group].append(q["query_id"])
        result[method] = {
            "per_query": per,
            "aggregates": {
                g: {str(k): summarize([per[q][str(k)] for q in ids]) for k in KS}
                for g, ids in sorted(groups.items())
            },
        }
    return result


def contradictions(metrics):
    models = sorted(metrics)
    result = []
    qids = metrics[models[0]]["lexical"]["per_query"]
    for qid in sorted(qids):
        for k in KS:
            for metric in ("precision", "pooled_ndcg", "mrr"):
                if metric == "mrr" and k != 50:
                    continue
                for a, b in combinations(("lexical", "vector", "hybrid"), 2):
                    differences = []
                    for model in models:
                        x = metrics[model][a]["per_query"][qid][str(k)][metric]
                        y = metrics[model][b]["per_query"][qid][str(k)][metric]
                        differences.append(None if x is None or y is None else x - y)
                    if (
                        all(d is not None for d in differences)
                        and differences[0] * differences[1] < -1e-12
                    ):
                        result.append(
                            {
                                "query_id": qid,
                                "k": k,
                                "metric": metric,
                                "methods": [a, b],
                                "differences": dict(zip(models, differences)),
                            }
                        )
    return result


def report_campaign(root, directory, output):
    manifest = load_plan(directory)
    if manifest["prompt_version"] != V2:
        raise ValueError("Rapport v2 uniquement.")
    sample = load_sample(root / "evaluation/local/rag007/corpus.json")
    queries = load_queries(root / "evaluation/queries.json")
    runs, metadata = load_rankings(
        root / "evaluation/local/rag014/development-replay", queries, sample
    )
    if (
        manifest["sample_hash"] != sample["selected_hash"]
        or manifest["query_hash"] != digest(queries)
        or metadata != manifest["source_hashes"]["frozen_rankings"]
    ):
        raise ValueError("Corpus, requêtes ou classements incompatibles.")
    pool = load_json(directory / "pool.json")
    if digest(pool) != manifest["source_hashes"]["pool_hash"]:
        raise ValueError("Pool modifié.")
    by_pair = {(r["query_id"], r["document_id"]): r for r in pool}
    if len(by_pair) != len(pool) or set(by_pair) != {
        (e["query_id"], e["document_id"]) for e in manifest["entries"]
    }:
        raise ValueError("Identités du pool incohérentes.")
    documents = {r["document_id"]: r for r in sample["documents"]}
    query_index = {q["query_id"]: q for q in queries}
    for item in iter_inputs(directory, manifest):
        row = by_pair[item.query_id, item.document_id]
        if (
            item.source_hash != documents[item.document_id]["content_hash"]
            or item.source_hash != row["document_hash"]
            or digest(item.query) != row["query_hash"]
            or item.query != query_index[item.query_id]["text"]
            or documents[item.document_id]["split"] != "development"
            or query_index[item.query_id]["split"] != "development"
        ):
            raise ValueError("Provenance ou partition incompatible.")
    expected = defaultdict(set)
    for q, d in by_pair:
        expected[q].add(d)
    exports = {}
    values = {}
    reports = {}
    metrics = {}
    cache = Cache(directory.parent / "cache.sqlite3")
    try:
        for key, spec in MODELS.items():
            run = load_json(directory / (key + "-run.json"))
            recipe = run["recipe"]
            if (
                run["plan_hash"] != manifest["manifest_hash"]
                or not run["complete"]
                or digest(recipe) != run["recipe_hash"]
                or recipe["model"] != spec.to_dict()
                or recipe["prompt_version"] != V2
                or recipe["prompt_hash"] != digest(resolve(V2))
            ):
                raise ValueError("Campagne incomplète ou recette incompatible.")
            rows = []
            records = {}
            for e in manifest["entries"]:
                value = cache.get(run["recipe_hash"], e["input_hash"])
                if (
                    value is None
                    or value["query_id"] != e["query_id"]
                    or value["document_id"] != e["document_id"]
                ):
                    raise ValueError("Jugement absent ou identité modifiée.")
                pair = e["query_id"], e["document_id"]
                records[pair] = value
                if value["status"] != "valid":
                    continue
                row = {
                    "query_id": pair[0],
                    "document_id": pair[1],
                    **value["judgment"],
                    "evaluator": "llm:" + key,
                    "judged_at": value["generated_at"],
                    "version": V2,
                    "judgment_origin": "llm",
                    "model": spec.to_dict(),
                    "recipe_hash": run["recipe_hash"],
                    "prompt_version": V2,
                    "prompt_hash": recipe["prompt_hash"],
                    "inference": recipe["inference"],
                    "document_hash": e["source_hash"],
                    "query_hash": by_pair[pair]["query_hash"],
                    "input_hash": e["input_hash"],
                    "plan_hash": manifest["manifest_hash"],
                }
                rows.append(row)
            _, judgments = validate_judgments(rows, queries, sample)
            exports[key] = rows
            values[key] = records
            reports[key] = run
            metrics[key] = engine_metrics(runs, judgments, queries, expected)
    finally:
        cache.close()
    ordered = sorted(by_pair)
    valid_pairs = [p for p in ordered if all(values[m][p]["status"] == "valid" for m in MODELS)]
    complete_queries = sorted(
        q for q, ids in expected.items() if all((q, d) in valid_pairs for d in ids)
    )
    common_metrics = {}
    for model in MODELS:
        grades = defaultdict(dict)
        for row in exports[model]:
            grades[row["query_id"]][row["document_id"]] = row["grade"]
        common_metrics[model] = engine_metrics(
            {m: {q: ids for q, ids in rankings.items() if q in complete_queries}
             for m, rankings in runs.items()},
            grades,
            [q for q in queries if q["query_id"] in complete_queries],
            expected,
        )

    def pair_grades(p):
        return tuple(values[m][p]["judgment"]["grade"] for m in MODELS)

    review = []
    for p in ordered:
        if p not in valid_pairs:
            reasons = ["invalid_judgment"]
        else:
            a, b = pair_grades(p)
            reasons = []
            if abs(a - b) >= 2:
                reasons.append("major")
            if (a >= 2) != (b >= 2):
                reasons.append("binary")
            if any(values[m][p]["judgment"]["uncertain"] for m in MODELS):
                reasons.append("uncertainty")
        if reasons:
            review.append(
                {
                    "query_id": p[0],
                    "document_id": p[1],
                    "reasons": reasons,
                    "grades": {m: values[m][p]["judgment"] for m in MODELS},
                }
            )
    result = {
        "version": 1,
        "judgment_origin": "llm",
        "human_reference": False,
        "plan_hash": manifest["manifest_hash"],
        "pool_size": len(pool),
        "pool_selection": manifest["source_hashes"].get("selection"),
        "pool_per_query": {q: len(ids) for q, ids in sorted(expected.items())},
        "unique_documents": len({d for q, d in by_pair}),
        "unique_contributions": len({documents[d]["contribution_id"] for q, d in by_pair}),
        "origin_counts": dict(
            Counter(source for row in pool for source in {o["source"] for o in row["origins"]})
        ),
        "ranking_metadata": metadata,
        "conventions": {
            "binary_relevance": "grade >=2",
            "ndcg_gain": "2**grade-1",
            "ndcg_reference": "all judged documents in the fixed pool for this query; NOT exhaustive corpus",
            "mrr": "first relevant in frozen top50; zero only if whole provided ranking judged",
            "unjudged": "never zero; metrics undefined when decisive ranks missing",
            "recall": "not computed",
        },
        "metrics": metrics,
        "common_complete_queries": complete_queries,
        "common_complete_metrics": common_metrics,
        "agreement": agreement([pair_grades(p) for p in valid_pairs]),
        "agreement_axes": list(MODELS),
        "valid_common": len(valid_pairs),
        "grade_distributions": {
            m: dict(sorted(Counter(r["grade"] for r in exports[m]).items())) for m in MODELS
        },
        "uncertainty": {m: sum(r["uncertain"] for r in exports[m]) for m in MODELS},
        "per_query_agreement": {
            q: agreement([pair_grades(p) for p in valid_pairs if p[0] == q])
            for q in sorted(expected)
        },
        "contradictions": contradictions(metrics),
        "review": review,
        "runs": reports,
        "execution": {m: execution_summary(directory, m, reports[m]) for m in MODELS},
    }
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    for model, rows in exports.items():
        reference = {
            "judgment_origin": "llm",
            "human_reference": False,
            "sample_hash": sample["selected_hash"],
            "queries_hash": digest(queries),
            "judgments": rows,
            "conflicts": [],
            "campaigns": [],
            "sources": [
                {
                    "plan_hash": manifest["manifest_hash"],
                    "recipe_hash": reports[model]["recipe_hash"],
                }
            ],
        }
        atomic_json(output / model / "judgments.json", rows)
        atomic_json(output / model / "reference.json", reference)
        conservative = evaluate_report(reference, runs, queries, sample)
        conservative["judgment_origin"] = "llm"
        conservative["human_reference"] = False
        atomic_json(output / model / "report-rag015.json", conservative)
    atomic_json(output / "comparison.json", result)
    atomic_json(output / "review.json", review)
    from cahier_rag.judges.markdown import render

    (output / "report.md").write_text(render(result), encoding="utf-8")
    return result
