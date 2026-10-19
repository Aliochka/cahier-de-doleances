"""Comparaison appariée, référence poolée commune et diagnostics sans inférence."""

import json
import math
from collections import defaultdict

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.reranking.cache import Cache
from cahier_rag.reranking.planning import load_plan, select_candidates
from cahier_rag.search.bm25.evaluation import reference_metrics
from cahier_rag.search.hybrid.multi.artifacts import load_bundle
from cahier_rag.search.hybrid.multi.evaluation import historical_references


def rerank(ids, scores):
    if len(set(ids)) != len(ids) or any(d not in scores for d in ids):
        raise ValueError("Classement dupliqué ou score absent.")
    if any(not math.isfinite(scores[d]) for d in ids):
        raise ValueError("Score non fini.")
    return sorted(ids, key=lambda d: (-scores[d], d))


def paired_test(values):
    if not values or len(values) > 20 or any(not math.isfinite(v) for v in values):
        raise ValueError("Entre 1 et 20 différences finies requises.")
    observed = abs(sum(values))
    nonzero = [abs(v) for v in values if v != 0]
    sums = [0.0]
    for value in nonzero:
        sums = [s + value for s in sums] + [s - value for s in sums]
    return sum(abs(s) >= observed - 1e-12 for s in sums) / len(sums)


def holm(pvalues):
    result, maximum = {}, 0.0
    ordered = sorted(pvalues, key=lambda k: (pvalues[k], k))
    for i, key in enumerate(ordered):
        maximum = max(maximum, min(1.0, pvalues[key] * (len(ordered) - i)))
        result[key] = maximum
    return result


def summarize(values):
    values = sorted(values)
    if not values:
        return {"count": 0, "median": None, "p95": None}
    n = len(values)
    median = (values[n // 2] + values[(n - 1) // 2]) / 2
    return {"count": n, "median": median, "p95": values[math.ceil(n * 0.95) - 1]}


def comparisons(metrics, common):
    deltas, tests = {}, {}
    for judge, methods in metrics.items():
        deltas[judge] = {}
        for name in methods:
            if "+" not in name:
                continue
            base = name.split("+")[0]
            rows = {}
            for q in common:
                rows[q] = {}
                for k in ("5", "10", "20", "50"):
                    a = methods[base]["per_query"][q][k]
                    b = methods[name]["per_query"][q][k]
                    rows[q][k] = {
                        metric: b[metric] - a[metric]
                        if a[metric] is not None and b[metric] is not None
                        else None
                        for metric in ("precision", "pooled_ndcg", "mrr")
                    }
            deltas[judge][name] = rows
            values = [r["10"]["pooled_ndcg"] for r in rows.values()]
            values = [v for v in values if v is not None]
            key = judge + ":" + name
            tests[key] = {
                "n": len(values),
                "mean_delta_ndcg10": sum(values) / len(values) if values else None,
                "wins": sum(v > 1e-12 for v in values),
                "ties": sum(abs(v) <= 1e-12 for v in values),
                "losses": sum(v < -1e-12 for v in values),
                "p_two_sided": paired_test(values) if values else None,
            }
    corrected = holm(
        {k: v["p_two_sided"] for k, v in tests.items() if v["p_two_sided"] is not None}
    )
    for k, value in tests.items():
        value["p_holm_12"] = corrected.get(k)
    return deltas, tests


def performance(directory, manifest, model, run, cache, bundle, candidates):
    histories = [
        json.loads(p.read_text()) for p in sorted((directory / "history").glob(model + "-*.json"))
    ]
    histories = [h for h in histories if h["recipe_hash"] == run["recipe_hash"]]
    batches = cache.batches(run["recipe_hash"])
    costs = {}
    for b in batches:
        for did in b["document_ids"]:
            costs[b["query_id"], did] = b["seconds"] / len(b["document_ids"])
    pipelines = {}
    for name, ranks in candidates.items():
        rows = {}
        for q, ids in ranks.items():
            measurement = bundle["measurements"][q]
            retrieval = (
                measurement["sources_ms"]["vector"]
                if name == "V"
                else measurement["attributable_sequential_ms"][name]
            ) / 1000
            scoring = sum(costs[q, d] for d in ids)
            rows[q] = {
                "historical_retrieval_seconds": retrieval,
                "estimated_scoring_seconds": scoring,
                "estimated_pipeline_seconds": retrieval + scoring,
            }
        pipelines[name] = {
            "per_query": rows,
            "estimated_scoring": summarize([r["estimated_scoring_seconds"] for r in rows.values()]),
            "estimated_pipeline": summarize(
                [r["estimated_pipeline_seconds"] for r in rows.values()]
            ),
        }
    prefixes = {
        str(n): summarize(
            [
                rows[str(n)]["seconds"]
                for rows in run["latencies_prefix"].values()
                if str(n) in rows and rows[str(n)]["seconds"] is not None
            ]
        )
        for n in (10, 20, 50)
    }
    seconds = sum(b["seconds"] for b in batches)
    return {
        "model": model,
        "run_hash": digest(run),
        "load_seconds": [h["load_seconds"] for h in histories if h["load_seconds"]],
        "peak_rss_bytes": max(h["peak_rss_bytes"] for h in histories),
        "hardware": max(
            histories, key=lambda h: h.get("hardware", {}).get("peak_allocated_bytes", 0)
        ).get("hardware"),
        "unique_pairs": len(manifest["pairs"]),
        "segments": sum(b["segments"] for b in batches),
        "input_tokens": sum(b["input_tokens"] for b in batches),
        "scoring_seconds": seconds,
        "documents_per_second": len(manifest["pairs"]) / seconds,
        "tokens_per_second": sum(b["input_tokens"] for b in batches) / seconds,
        "measured_prefix_seconds": prefixes,
        "prefix_selection": "10/20/50 unique document IDs per query, not retrieval order; no repeated GPU inference",
        "pipelines": pipelines,
        "pipeline_policy": "Estimates: allocate each measured batch equally to member units; add historical retrieval. Not standalone pipeline measurements; excludes model load.",
    }


def render(result):
    lines = [
        "# RAG-020 — Comparaison des rerankers",
        "",
        "Référence LLM relevance-fr-v2, jamais une vérité humaine. Développement uniquement.",
        "",
        f"{result['pairs']} couples uniques, {result['segments']} segments ; {len(result['common_complete_queries'])}/20 requêtes communes entièrement jugées.",
        "",
        "nDCG : gain 2**note-1, idéal fixe sur les 3 254 couples RAG-017/018 par requête et juge, commun aux neuf pipelines. Non-jugés exclus, jamais remplacés par zéro ; aucun rappel exhaustif.",
        "",
        "| Juge | Pipeline | P@5 | P@10 | nDCG@5 | nDCG@10 | nDCG@20 | MRR@50 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]

    def f(v):
        return "—" if v is None else f"{v:.4f}"

    for judge, methods in result["common_complete_metrics"].items():
        for name, data in methods.items():
            a = data["aggregates"]["all"]
            vals = [
                a[k][m]["mean"]
                for k, m in (
                    ("5", "precision"),
                    ("10", "precision"),
                    ("5", "pooled_ndcg"),
                    ("10", "pooled_ndcg"),
                    ("20", "pooled_ndcg"),
                    ("50", "mrr"),
                )
            ]
            lines.append(f"| {judge} | {name} | " + " | ".join(map(f, vals)) + " |")
    lines += [
        "",
        "## Différences appariées sur nDCG@10",
        "",
        "| Juge/pipeline | Δ moyenne | Gains/égalités/pertes | p bilatéral | p Holm (12) |",
        "|---|---:|---|---:|---:|",
    ]
    for name, row in result["paired_tests"].items():
        lines.append(
            f"| {name} | {f(row['mean_delta_ndcg10'])} | {row['wins']}/{row['ties']}/{row['losses']} | {f(row['p_two_sided'])} | {f(row['p_holm_12'])} |"
        )
    lines += [
        "",
        "Tests exploratoires exacts par permutation des signes, correction de Holm sur douze comparaisons fixées. Les requêtes ne sont pas un échantillon aléatoire ; deux juges de même famille, dont un apparenté au reranker Qwen. Ne pas confondre significativité conditionnelle et validation humaine indépendante.",
        "",
        "## GPU : temps mesurés",
        "",
        "| Modèle | Chargements (s) | Score total (s) | docs/s | RAM pic (Go) | VRAM allouée (Go) | préfixe 10 médiane/P95 (s) | 20 | 50 |",
        "|---|---|---:|---:|---:|---:|---|---|---|",
    ]
    for m, p in result["performance"].items():
        cols = [
            "/".join(f(p["measured_prefix_seconds"][str(n)][k]) for k in ("median", "p95"))
            for n in (10, 20, 50)
        ]
        lines.append(
            f"| {m} | {', '.join(f(v) for v in p['load_seconds'])} | {f(p['scoring_seconds'])} | {f(p['documents_per_second'])} | {f(p['peak_rss_bytes'] / 1e9)} | {f((p['hardware'] or {}).get('peak_allocated_bytes', 0) / 1e9)} | "
            + " | ".join(cols)
            + " |"
        )
    lines += [
        "",
        "Ces préfixes sont les premiers identifiants uniques de chaque requête dans l'ordre figé, pas les rangs de récupération. Les estimations par pipeline, distinctes des mesures, sont dans comparison.json.",
        "",
        "## Différences par requête",
        "",
        "| Juge | Pipeline | Requête | Δ P@10 | Δ nDCG@10 |",
        "|---|---|---|---:|---:|",
    ]
    for judge, methods in result["deltas"].items():
        for name, rows in methods.items():
            for q, row in rows.items():
                lines.append(
                    f"| {judge} | {name} | {q} | {f(row['10']['precision'])} | {f(row['10']['pooled_ndcg'])} |"
                )
    lines += [
        "",
        "## Par thématique",
        "",
        "| Juge | Pipeline | Domaine | P@10 | nDCG@10 |",
        "|---|---|---|---:|---:|",
    ]
    for judge, methods in result["common_complete_metrics"].items():
        for name, data in methods.items():
            for group, values in data["aggregates"].items():
                if group.startswith("domain:"):
                    a = values["10"]
                    lines.append(
                        f"| {judge} | {name} | {group[7:]} | {f(a['precision']['mean'])} | {f(a['pooled_ndcg']['mean'])} |"
                    )
    lines += [
        "",
        "## CPU local, trois couples communs courts",
        "",
        "| Modèle | Chargement (s) | Latences individuelles (s) | RAM pic (Go) |",
        "|---|---:|---|---:|",
    ]
    for model, value in result.get("cpu", {}).items():
        lines.append(
            f"| {model} | {f(value['load_seconds'])} | {', '.join(f(r['seconds']) for r in value['rows'])} | {f(value['peak_rss_bytes'] / 1e9)} |"
        )
    lines += [
        "",
        "Ryzen 7950X, quatre threads, float32, premier passage inclus. Trois observations ne permettent pas une estimation fiable des percentiles ni une extrapolation à Wallace.",
        "",
        "## Estimations de pipeline, distinctes des mesures",
        "",
        "| Reranker | Pipeline | Reranking estimé médiane/P95 (s) | Récupération historique + reranking estimé médiane/P95 (s) |",
        "|---|---|---|---|",
    ]
    for model, value in result["performance"].items():
        for name, rows in value["pipelines"].items():
            a = rows["estimated_scoring"]
            b = rows["estimated_pipeline"]
            lines.append(
                f"| {model} | {name} | {f(a['median'])}/{f(a['p95'])} | {f(b['median'])}/{f(b['p95'])} |"
            )
    lines += [
        "",
        "Allocation amortie des mesures de lots uniques aux documents sélectionnés, ajout des temps historiques RAG-019 par requête, sans chargement. Les différences de longueurs et segments influencent ces coûts ; pas de mesure directe du pipeline complet.",
        "",
    ]
    return "\n".join(lines) + "\n"


def report_comparison(root, directory, output):
    manifest, candidates = load_plan(directory)
    bundle, frozen, scope, queries = load_bundle(
        root,
        root / "evaluation/local/rag019/configuration",
        root / "evaluation/local/rag019/development",
    )
    if (
        select_candidates(bundle)[0] != candidates
        or manifest["sample_hash"] != scope.sample_hash
        or manifest["queries_hash"] != digest(queries)
        or manifest["rag019_frozen_hash"] != frozen["frozen_hash"]
        or manifest["rag019_experiment_hash"] != bundle["report"]["manifest_hash"]
    ):
        raise ValueError("Classements ou corpus historiques différents du plan.")
    runs = dict(candidates)
    executions, score_exports = {}, {}
    cache = Cache(directory.parent / "scores.sqlite3", readonly=True)
    try:
        for model in ("R1", "R2"):
            run = json.loads((directory / (model + "-run.json")).read_text())
            expected = {
                "version": 1,
                "plan_hash": manifest["manifest_hash"],
                "backend": manifest["backends"][model],
                "batch_documents": manifest["batch_documents"],
                "batch_segments": manifest["batch_segments"],
                "preparation": manifest["configuration"],
            }
            if (
                not run["complete"]
                or run["recipe"] != expected
                or run["recipe_hash"] != digest(expected)
            ):
                raise ValueError("Inférence incomplète ou recette incompatible.")
            scores, records = defaultdict(dict), []
            for entry in manifest["pairs"]:
                value = cache.get(run["recipe_hash"], entry["query_id"], entry["document_id"])
                if (
                    value is None
                    or value["unit_input_hash"] != digest(entry)
                    or value["source_hash"] != entry["source_hash"]
                    or [v["input_hash"] for v in value["segments"]]
                    != [v["input_hash"] for v in entry["segments"]]
                ):
                    raise ValueError("Score ou référence absent/incompatible.")
                records.append(value)
                scores[entry["query_id"]][entry["document_id"]] = value["score"]
            score_exports[model] = records
            for name, rankings in candidates.items():
                runs[name + "+" + model] = {
                    q: rerank(ids, scores[q]) for q, ids in rankings.items()
                }
            executions[model] = performance(
                directory, manifest, model, run, cache, bundle, candidates
            )
    finally:
        cache.close()
    # First access to labels occurs only after both complete runs are validated.
    references, provenance = historical_references(root, scope, queries)
    targets = {(e["query_id"], e["document_id"]) for e in manifest["pairs"]}
    if any(not targets <= set(records) for records in references.values()):
        raise ValueError("Couples hors du référentiel historique.")
    metrics, common, common_metrics = reference_metrics(runs, references, queries)
    deltas, tests = comparisons(common_metrics, common)
    judges = sorted(deltas)
    disagreements = []
    if len(judges) == 2:
        for name in deltas[judges[0]]:
            for q in common:
                values = [deltas[j][name][q]["10"]["pooled_ndcg"] for j in judges]
                if values[0] * values[1] < 0:
                    disagreements.append(
                        {"pipeline": name, "query_id": q, "delta_ndcg10": dict(zip(judges, values))}
                    )
    cpu = {}
    for model in ("R1", "R2"):
        path = directory.parent / ("cpu-" + model + ".json")
        if path.exists():
            value = json.loads(path.read_text())
            if (
                value["plan_hash"] != manifest["manifest_hash"]
                or value["recipe"]["device"] != "cpu"
                or value["recipe"]["model"] != manifest["backends"][model]["model"]
            ):
                raise ValueError("Micro-benchmark CPU incompatible.")
            value["latency_seconds"] = summarize([r["seconds"] for r in value["rows"]])
            cpu[model] = value
    if len(cpu) == 2 and [r["input_hash"] for r in cpu["R1"]["rows"]] != [
        r["input_hash"] for r in cpu["R2"]["rows"]
    ]:
        raise ValueError("Couples CPU différents entre modèles.")
    result = {
        "version": 1,
        "judgment_origin": "llm",
        "human_reference": False,
        "plan_hash": manifest["manifest_hash"],
        "references": provenance,
        "pairs": len(manifest["pairs"]),
        "segments": sum(len(e["segments"]) for e in manifest["pairs"]),
        "metrics": metrics,
        "common_complete_queries": common,
        "common_complete_metrics": common_metrics,
        "deltas": deltas,
        "paired_tests": tests,
        "judge_disagreements": disagreements,
        "performance": executions,
        "cpu": cpu,
        "runs_hash": digest(runs),
    }
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "comparison.json", result)
    for name, rankings in runs.items():
        atomic_json(output / name / "runs.json", rankings)
    for model, records in score_exports.items():
        atomic_json(output / model / "scores.json", records)
    (output / "report.md").write_text(render(result), encoding="utf-8")
    return result
