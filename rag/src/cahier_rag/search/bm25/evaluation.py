"""Réutilisation en lecture seule, compléments indépendants et métriques sur périmètre commun."""

import json
import sqlite3
from collections import Counter, defaultdict

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.files import validate_judgments
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.contracts import InferenceConfig, parse_output
from cahier_rag.judges.evaluation import engine_metrics, execution_summary
from cahier_rag.judges.models import MODELS
from cahier_rag.judges.planning import iter_inputs, load_plan
from cahier_rag.judges.protocols import V2, resolve
from cahier_rag.search.bm25.experiments import load_experiment


def load_records(directory, model, scope, queries):
    plan = load_plan(directory)
    run = json.loads((directory / (model + "-run.json")).read_text())
    recipe = run["recipe"]
    if (
        plan["prompt_version"] != V2
        or plan["sample_hash"] != scope.sample_hash
        or plan["query_hash"] != digest(queries)
        or not run["complete"]
        or run["plan_hash"] != plan["manifest_hash"]
        or digest(recipe) != run["recipe_hash"]
        or recipe["prompt_version"] != V2
        or recipe["prompt_hash"] != digest(resolve(V2))
        or recipe["model"] != MODELS[model].to_dict()
        or recipe["inference"] != InferenceConfig().to_dict()
    ):
        raise ValueError("Référence LLM incompatible ou incomplète.")
    query_index = {q["query_id"]: q for q in queries}
    cache_path = (directory.parent / "cache.sqlite3").resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(cache_path, uri=True)
    records = {}
    try:
        for item in iter_inputs(directory, plan):
            q = query_index[item.query_id]
            if (
                q["split"] != "development"
                or q["text"] != item.query
                or scope.documents[item.document_id]["split"] != "development"
                or scope.documents[item.document_id]["content_hash"] != item.source_hash
            ):
                raise ValueError("Référence hors partition ou contenu modifié.")
            row = connection.execute(
                "SELECT payload,result_hash FROM results WHERE recipe_hash=? AND input_hash=?",
                (run["recipe_hash"], item.input_hash),
            ).fetchone()
            if row is None:
                raise ValueError("Résultat de campagne manquant.")
            value = json.loads(row[0])
            if (
                digest(value) != row[1]
                or value["input_hash"] != item.input_hash
                or value["query_id"] != item.query_id
                or value["document_id"] != item.document_id
            ):
                raise ValueError("Jugement modifié.")
            if value["status"] == "valid":
                if parse_output(value["raw_output"]) != value["judgment"]:
                    raise ValueError("Sortie brute incompatible avec la note.")
            elif value["judgment"] is not None:
                raise ValueError("Échec de juge contenant une note.")
            records[item.query_id, item.document_id] = {
                "record": value,
                "input": item,
                "plan_hash": plan["manifest_hash"],
                "recipe_hash": run["recipe_hash"],
                "recipe": recipe,
                "campaign": plan["kind"],
            }
    finally:
        connection.close()
    return records, run, plan


def merge_records(old, new):
    if set(old) & set(new):
        raise ValueError("Complément réannotant un couple historique.")
    return old | new


def reference_metrics(runs, references, queries):
    expected = defaultdict(set)
    for records in references.values():
        for q, d in records:
            expected[q].add(d)
    grades = {m: defaultdict(dict) for m in references}
    for m, records in references.items():
        for (q, d), wrapped in records.items():
            value = wrapped["record"]
            if value["status"] == "valid":
                grades[m][q][d] = value["judgment"]["grade"]
    common = sorted(
        q for q, ids in expected.items() if all(set(grades[m][q]) == ids for m in grades)
    )
    metrics = {m: engine_metrics(runs, g, queries, expected) for m, g in grades.items()}
    common_metrics = {
        m: engine_metrics(
            {
                method: {q: ids for q, ids in ranks.items() if q in common}
                for method, ranks in runs.items()
            },
            g,
            [q for q in queries if q["query_id"] in common],
            expected,
        )
        for m, g in grades.items()
    }
    return metrics, common, common_metrics


def render(report):
    def fmt(v):
        return "—" if v is None else f"{v:.3f}"

    common = report["common_complete_queries"]
    lines = [
        "# RAG-018 — Comparaison BM25",
        "",
        "Jugements LLM v2 séparés ; aucune référence humaine ni rappel exhaustif.",
        "",
        f"Requêtes entièrement jugées par les deux modèles : **{len(common)} sur 20**.",
        "Les métriques comparées utilisent ces mêmes requêtes pour tous les moteurs. Les requêtes exclues et toutes les couvertures figurent dans comparison.json.",
        "",
        "nDCG poolée : idéal sur l'union fixe RAG-017 + complément BM25 pour chaque requête et juge ; gain 2**grade-1. Ce changement de pool rend la nDCG non directement comparable aux chiffres publiés dans RAG-017. Les non-jugés ne valent jamais zéro.",
        "",
        "| Juge | Moteur | k | P@k | nDCG poolée@k | MRR@50 |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for model, methods in report["common_complete_metrics"].items():
        for name, data in methods.items():
            for k in ("5", "10", "20", "50"):
                aggregate = data["aggregates"].get("all", {}).get(k, {})

                def mean(metric):
                    return fmt(aggregate.get(metric, {}).get("mean"))

                lines.append(
                    f"| {model} | {name} | {k} | {mean('precision')} | {mean('pooled_ndcg')} | {mean('mrr')} |"
                )
    lines += [
        "",
        "## Réutilisation et échecs",
        "",
        f"{report['reuse']}",
        "",
        "Les trois sorties historiques invalides restent invalides et n'ont pas été réannotées. Les origines et recettes sont conservées dans les exports ; les sources n'ont pas été modifiées.",
        "",
        "## Comparaisons par requête",
        "",
        "| Juge | Requête | Méthode | Δ P@10 / lexical | Δ nDCG poolée@10 / lexical |",
        "|---|---|---|---:|---:|",
    ]
    for model, rows in report["deltas"].items():
        for q, methods in rows.items():
            for name, values in methods.items():
                lines.append(
                    f"| {model} | {q} | {name} | {fmt(values['10']['precision'])} | {fmt(values['10']['pooled_ndcg'])} |"
                )
    lines += [
        "",
        "## Par thématique, mêmes requêtes complètes",
        "",
        "| Juge | Domaine | Moteur | P@10 | nDCG poolée@10 |",
        "|---|---|---|---:|---:|",
    ]
    for model, methods in report["common_complete_metrics"].items():
        for name, data in methods.items():
            for group, ks in data["aggregates"].items():
                if group.startswith("domain:"):
                    row = ks["10"]
                    lines.append(
                        f"| {model} | {group[7:]} | {name} | {fmt(row['precision']['mean'])} | {fmt(row['pooled_ndcg']['mean'])} |"
                    )
    lines += [
        "",
        "Deux modèles de même famille, pooling dépendant des moteurs, requêtes de développement uniquement. Les variantes n'ont pas été réglées sur ces notes. Une validation humaine indépendante reste nécessaire.",
        "",
    ]
    return "\n".join(lines)


def report_comparison(root, experiment, directory, output, scope, queries):
    runs, technical = load_experiment(experiment, scope, queries)
    old_directory = root / "evaluation/local/rag017/pool"
    new_manifest = load_plan(directory)
    if (
        new_manifest["kind"] != "rag018"
        or new_manifest["source_hashes"]["experiment_hash"] != technical["manifest_hash"]
    ):
        raise ValueError("Complément indépendant incompatible avec l'expérience.")
    pool = json.loads((directory / "pool.json").read_text())
    if digest(pool) != new_manifest["source_hashes"]["pool_hash"]:
        raise ValueError("Origines du complément modifiées.")
    pairs = {(r["query_id"], r["document_id"]) for r in pool}
    if len(pairs) != len(pool) or pairs != {
        (e["query_id"], e["document_id"]) for e in new_manifest["entries"]
    }:
        raise ValueError("Couples du complément différents du plan.")
    references, exports, reuse, execution = {}, {}, {}, {}
    sample = {
        "documents": [dict(d) for d in scope.documents.values()],
        "selected_hash": scope.sample_hash,
    }
    for model in MODELS:
        old, old_run, old_plan = load_records(old_directory, model, scope, queries)
        new, run, plan = load_records(directory, model, scope, queries)
        if (
            old_run["recipe_hash"] != run["recipe_hash"]
            or old_plan["manifest_hash"] != plan["source_hashes"]["historical_plan"]
        ):
            raise ValueError("Recettes historiques et complémentaires différentes.")
        merged = merge_records(old, new)
        references[model] = merged
        rows = []
        for (qid, did), wrapped in sorted(merged.items()):
            value = wrapped["record"]
            if value["status"] != "valid":
                continue
            rows.append(
                {
                    "query_id": qid,
                    "document_id": did,
                    **value["judgment"],
                    "judged_at": value["generated_at"],
                    "evaluator": "llm:" + model,
                    "version": V2,
                    "judgment_origin": "llm",
                    "campaign": wrapped["campaign"],
                    "model": wrapped["recipe"]["model"],
                    "inference": wrapped["recipe"]["inference"],
                    "recipe_hash": wrapped["recipe_hash"],
                    "plan_hash": wrapped["plan_hash"],
                    "input_hash": wrapped["input"].input_hash,
                    "document_hash": wrapped["input"].source_hash,
                    "query_hash": digest(wrapped["input"].query),
                    "prompt_version": V2,
                    "prompt_hash": wrapped["recipe"]["prompt_hash"],
                }
            )
        validate_judgments(rows, queries, sample)
        exports[model] = rows
        bm_pairs = {
            (q, d)
            for name in ("bm25-A", "bm25-B")
            for q, ids in runs[name].items()
            for d in ids[:50]
        }
        reuse[model] = {
            "historical_valid": sum(v["record"]["status"] == "valid" for v in old.values()),
            "historical_invalid": sum(v["record"]["status"] != "valid" for v in old.values()),
            "bm25_historical_valid_reused": sum(
                p in old and old[p]["record"]["status"] == "valid" for p in bm_pairs
            ),
            "new_pairs": len(new),
            "new_valid": sum(v["record"]["status"] == "valid" for v in new.values()),
            "new_invalid": sum(v["record"]["status"] != "valid" for v in new.values()),
        }
        execution[model] = execution_summary(directory, model, run)
    metrics, common, common_metrics = reference_metrics(runs, references, queries)
    deltas = {}
    for model, methods in metrics.items():
        deltas[model] = {}
        for qid in sorted(runs["lexical"]):
            deltas[model][qid] = {}
            for name in ("bm25-A", "bm25-B", "vector"):
                deltas[model][qid][name] = {}
                for k in ("5", "10", "20", "50"):
                    base = methods["lexical"]["per_query"][qid][k]
                    candidate = methods[name]["per_query"][qid][k]
                    deltas[model][qid][name][k] = {
                        metric: candidate[metric] - base[metric]
                        if candidate[metric] is not None and base[metric] is not None
                        else None
                        for metric in ("precision", "pooled_ndcg", "mrr")
                    }
    result = {
        "version": 1,
        "judgment_origin": "llm",
        "human_reference": False,
        "sample_hash": scope.sample_hash,
        "experiment_hash": technical["manifest_hash"],
        "complement_plan": new_manifest["manifest_hash"],
        "metrics": metrics,
        "common_complete_queries": common,
        "common_complete_metrics": common_metrics,
        "deltas": deltas,
        "reuse": reuse,
        "execution": execution,
        "grade_distributions": {
            m: dict(sorted(Counter(r["grade"] for r in rows).items()))
            for m, rows in exports.items()
        },
    }
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "comparison.json", result)
    for model, rows in exports.items():
        atomic_json(output / model / "judgments.json", rows)
    (output / "report.md").write_text(render(result), encoding="utf-8")
    return result
