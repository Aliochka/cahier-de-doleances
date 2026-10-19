"""Référence commune des neuf méthodes, compléments indépendants et échecs préservés."""

import json
from itertools import combinations

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.files import validate_judgments
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.models import MODELS
from cahier_rag.judges.planning import load_plan, prepare
from cahier_rag.judges.protocols import V2
from cahier_rag.search.bm25.evaluation import load_records, merge_records, reference_metrics
from cahier_rag.search.hybrid.multi.artifacts import LocalDocuments, load_bundle
from cahier_rag.search.hybrid.multi.core import CONFIGURATIONS


def historical_references(root, scope, queries):
    references, metadata = {}, {}
    for model in MODELS:
        first, old_run, old_plan = load_records(
            root / "evaluation/local/rag017/pool", model, scope, queries
        )
        second, new_run, new_plan = load_records(
            root / "evaluation/local/rag018/complement/pool", model, scope, queries
        )
        if (
            old_run["recipe_hash"] != new_run["recipe_hash"]
            or new_plan["source_hashes"]["historical_plan"] != old_plan["manifest_hash"]
            or old_plan["kind"] != "rag017"
            or new_plan["kind"] != "rag018"
        ):
            raise ValueError("Références historiques incompatibles.")
        references[model] = merge_records(first, second)
        metadata[model] = {
            "recipe_hash": old_run["recipe_hash"],
            "plans": [old_plan["manifest_hash"], new_plan["manifest_hash"]],
            "records_hash": digest(
                [
                    [q, d, digest(value["record"])]
                    for (q, d), value in sorted(references[model].items())
                ]
            ),
        }
    keys = [set(values) for values in references.values()]
    if any(keys[0] != keys[i] for i in range(1, len(keys))):
        raise ValueError("Périmètres historiques différents entre juges.")
    return references, metadata


def candidate_pool(runs, known):
    origins = {}
    for name, rankings in sorted(runs.items()):
        for qid, ids in sorted(rankings.items()):
            for rank, did in enumerate(ids[:50], 1):
                origins.setdefault((qid, did), []).append({"method": name, "rank": rank})
    targets = [
        {"query_id": q, "document_id": d, "origins": origins[q, d]} for q, d in sorted(origins)
    ]
    missing = [r for r in targets if (r["query_id"], r["document_id"]) not in known]
    return targets, missing


def prepare_pool(root, frozen_directory, experiment, output):
    bundle, frozen, scope, queries = load_bundle(root, frozen_directory, experiment)
    references, metadata = historical_references(root, scope, queries)
    known = set(next(iter(references.values())))
    targets, rows = candidate_pool(bundle["runs"], known)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "version": 1,
        "frozen_hash": frozen["frozen_hash"],
        "experiment_hash": bundle["report"]["manifest_hash"],
        "sample_hash": scope.sample_hash,
        "queries_hash": digest(queries),
        "historical_references": metadata,
        "targets_hash": digest(targets),
        "pool_hash": digest(rows),
        "plan_hash": None,
        "counts": {
            "target_unique_pairs_top50": len(targets),
            "known_pairs_reused": len(targets) - len(rows),
            "new_pairs": len(rows),
            "historical_invalid": {
                m: sum(v["record"]["status"] != "valid" for v in records.values())
                for m, records in references.items()
            },
        },
        "invalid_policy": "historical known failures remain unjudged; no reannotation",
    }
    if rows:
        plan = prepare(
            output / "plan",
            [(r["query_id"], r["document_id"]) for r in rows],
            LocalDocuments(root / "evaluation/local/rag018/bm25-A.sqlite3", scope),
            queries,
            kind="rag019",
            prompt_version=V2,
            source_hashes={
                "frozen_hash": frozen["frozen_hash"],
                "experiment_hash": manifest["experiment_hash"],
                "pool_hash": manifest["pool_hash"],
            },
        )
        manifest["plan_hash"] = plan["manifest_hash"]
    manifest["manifest_hash"] = digest(manifest)
    atomic_json(output / "manifest.json", manifest)
    atomic_json(output / "targets.json", targets)
    atomic_json(output / "pool.json", rows)
    return manifest


def load_pool(directory, bundle, frozen, scope, queries, metadata, known):
    manifest = json.loads((directory / "manifest.json").read_text())
    rows = json.loads((directory / "pool.json").read_text())
    targets = json.loads((directory / "targets.json").read_text())
    body = {k: v for k, v in manifest.items() if k != "manifest_hash"}
    expected_targets, expected_rows = candidate_pool(bundle["runs"], known)
    if (
        digest(body) != manifest["manifest_hash"]
        or manifest["frozen_hash"] != frozen["frozen_hash"]
        or manifest["experiment_hash"] != bundle["report"]["manifest_hash"]
        or manifest["historical_references"] != metadata
        or manifest["sample_hash"] != scope.sample_hash
        or manifest["queries_hash"] != digest(queries)
        or digest(targets) != manifest["targets_hash"]
        or digest(rows) != manifest["pool_hash"]
        or targets != expected_targets
        or rows != expected_rows
        or manifest["counts"]["new_pairs"] != len(rows)
    ):
        raise ValueError("Pool ou références modifiés.")
    if bool(rows) != (manifest["plan_hash"] is not None):
        raise ValueError("Plan complémentaire incohérent.")
    return manifest, rows, targets


def inversions(metrics, common):
    models = list(MODELS)
    rows = []
    for q in common:
        for a, b in combinations(CONFIGURATIONS, 2):
            for k in ("5", "10", "20", "50"):
                for metric in ("precision", "pooled_ndcg", "mrr"):
                    if metric == "mrr" and k != "50":
                        continue
                    if any(
                        metrics[m][n]["per_query"][q][k][metric] is None
                        for m in models
                        for n in (a, b)
                    ):
                        continue
                    differences = {
                        m: metrics[m][a]["per_query"][q][k][metric]
                        - metrics[m][b]["per_query"][q][k][metric]
                        for m in models
                    }
                    if differences[models[0]] * differences[models[1]] < -1e-12:
                        rows.append(
                            {
                                "query_id": q,
                                "methods": [a, b],
                                "k": int(k),
                                "metric": metric,
                                "differences": differences,
                            }
                        )
    return rows


def report_comparison(root, frozen_directory, experiment, pool_directory, output):
    bundle, frozen, scope, queries = load_bundle(root, frozen_directory, experiment)
    references, metadata = historical_references(root, scope, queries)
    known = set(next(iter(references.values())))
    manifest, rows, targets = load_pool(
        pool_directory, bundle, frozen, scope, queries, metadata, known
    )
    if rows:
        plan = load_plan(pool_directory / "plan")
        if plan["manifest_hash"] != manifest["plan_hash"] or {
            (e["query_id"], e["document_id"]) for e in plan["entries"]
        } != {(r["query_id"], r["document_id"]) for r in rows}:
            raise ValueError("Plan incompatible avec le complément.")
        for model in MODELS:
            extra, run, _ = load_records(pool_directory / "plan", model, scope, queries)
            if run["recipe_hash"] != metadata[model]["recipe_hash"]:
                raise ValueError("Recette complémentaire différente des références.")
            references[model] = merge_records(references[model], extra)
    metrics, common, common_metrics = reference_metrics(bundle["runs"], references, queries)
    exports = {}
    reuse = {}
    sample = {
        "documents": [dict(d) for d in scope.documents.values()],
        "selected_hash": scope.sample_hash,
    }
    wanted = {(r["query_id"], r["document_id"]) for r in targets}
    for model, records in references.items():
        valid = []
        for (q, d), value in sorted(records.items()):
            row = value["record"]
            if row["status"] != "valid":
                continue
            valid.append(
                {
                    "query_id": q,
                    "document_id": d,
                    **row["judgment"],
                    "judged_at": row["generated_at"],
                    "version": V2,
                    "evaluator": "llm:" + model,
                    "judgment_origin": "llm",
                    "campaign": value["campaign"],
                    "plan_hash": value["plan_hash"],
                    "recipe_hash": value["recipe_hash"],
                    "input_hash": value["input"].input_hash,
                    "document_hash": value["input"].source_hash,
                    "query_hash": digest(value["input"].query),
                    "model": value["recipe"]["model"],
                    "inference": value["recipe"]["inference"],
                    "prompt_hash": value["recipe"]["prompt_hash"],
                }
            )
        validate_judgments(valid, queries, sample)
        exports[model] = valid
        reuse[model] = {
            "reference_pairs": len(records),
            "valid_reference_pairs": len(valid),
            "target_pairs": len(wanted),
            "target_valid": sum(
                p in records and records[p]["record"]["status"] == "valid" for p in wanted
            ),
            "new_valid": sum(
                v["record"]["status"] == "valid" for p, v in records.items() if p not in known
            ),
            "historical_invalid": sum(
                v["record"]["status"] != "valid" for p, v in records.items() if p in known
            ),
        }
    deltas = {}
    for model, methods in metrics.items():
        deltas[model] = {}
        for q in sorted(bundle["runs"]["H1"]):
            deltas[model][q] = {}
            for name in methods:
                if name == "H1":
                    continue
                deltas[model][q][name] = {}
                for k in ("5", "10", "20", "50"):
                    candidate = methods[name]["per_query"][q][k]
                    baseline = methods["H1"]["per_query"][q][k]
                    deltas[model][q][name][k] = {
                        metric: candidate[metric] - baseline[metric]
                        if candidate[metric] is not None and baseline[metric] is not None
                        else None
                        for metric in ("precision", "pooled_ndcg", "mrr")
                    }
    result = {
        "version": 1,
        "judgment_origin": "llm",
        "human_reference": False,
        "frozen_hash": frozen["frozen_hash"],
        "experiment_hash": bundle["report"]["manifest_hash"],
        "pool_hash": manifest["manifest_hash"],
        "metrics": metrics,
        "common_complete_queries": common,
        "common_complete_metrics": common_metrics,
        "reuse": reuse,
        "deltas_from_H1": deltas,
        "judge_inversions": inversions(metrics, common),
        "ndcg_reference": "fixed cumulative RAG017/018 plus only new RAG019 pairs; not exhaustive corpus",
        "recall": None,
        "configuration": frozen["configuration"],
    }
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "comparison.json", result)
    for model, values in exports.items():
        atomic_json(output / model / "judgments.json", values)
    from cahier_rag.search.hybrid.multi.markdown import render

    (output / "report.md").write_text(render(result, bundle), encoding="utf-8")
    return result
