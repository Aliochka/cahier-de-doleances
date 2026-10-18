"""Couverture et mesures prudentes sur les classements existants, sans exécution moteur."""

from cahier_rag.evaluation.files import load_json, validate_judgments
from cahier_rag.evaluation.metrics import evaluate
from cahier_rag.evaluation.sampling import digest

METHODS = ("lexical", "vector", "hybrid")
KS = (5, 10, 20)
METRICS = ("precision_at_k", "recall_at_k", "mrr", "ndcg_at_k")


def load_rankings(directory, queries, sample):
    runs, report = load_json(directory / "runs.json"), load_json(directory / "report.json")
    development = {q["query_id"] for q in queries if q["split"] == "development"}
    docs = {d["document_id"]: d for d in sample["documents"]}
    if (
        digest(runs) != report["runs_hash"]
        or report["sample_hash"] != sample["selected_hash"]
        or report["queries_hash"] != digest([q for q in queries if q["split"] == "development"])
        or report["split"] != "development"
        or set(runs) != set(METHODS)
    ):
        raise ValueError("Classements de développement incompatibles.")
    for rankings in runs.values():
        if set(rankings) != development:
            raise ValueError("Jeu de requêtes incomplet ou réservé.")
        for ids in rankings.values():
            if len(ids) != len(set(ids)) or any(
                d not in docs or docs[d]["split"] != "development" for d in ids
            ):
                raise ValueError("Classement dupliqué, inconnu ou entre partitions.")
    return runs, {
        "runs_hash": digest(runs),
        "report_hash": digest(report),
        "baselines": report["baselines"],
        "configuration": report["configuration"],
    }


def evaluate_report(reference, runs, queries, sample):
    if (
        reference["sample_hash"] != sample["selected_hash"]
        or reference["queries_hash"] != digest(queries)
        or set(runs) != set(METHODS)
    ):
        raise ValueError("Référentiel ou moteurs incompatibles.")
    _, judged = validate_judgments(reference["judgments"], queries, sample)
    conflicts = {(r["query_id"], r["document_id"]) for r in reference["conflicts"]}
    available_pairs = {
        (r["query_id"], r["document_id"])
        for campaign in reference["campaigns"]
        for r in campaign["pending_pairs"]
    }
    available_pairs.update((r["query_id"], r["document_id"]) for r in reference["judgments"])
    available_pairs.update(conflicts)
    documents = {d["document_id"]: d for d in sample["documents"]}
    development = [q for q in queries if q["split"] == "development"]
    qids = {q["query_id"] for q in development}
    for method in METHODS:
        if set(runs[method]) != qids:
            raise ValueError("Requêtes de classement différentes du développement.")
    result = {
        "version": 1,
        "sample_hash": sample["selected_hash"],
        "queries_hash": digest(development),
        "reference_hash": digest(reference),
        "split": "development",
        "methods": {},
        "conflict_count": len(conflicts),
        "final_ranking": None,
        "warning": "Jugements incomplets : aucune conclusion définitive entre moteurs. Les non-jugés et conflits ne valent pas zéro.",
    }
    for method in METHODS:
        per_query = {}
        for query in development:
            qid, results = query["query_id"], runs[method][query["query_id"]]
            if len(results) != len(set(results)) or any(
                d not in documents or documents[d]["split"] != "development" for d in results
            ):
                raise ValueError("Résultats inconnus, dupliqués ou entre partitions.")
            grades = judged.get(qid, {})
            partition = {did for did, d in documents.items() if d["split"] == query["split"]}
            exhaustive = set(grades) == partition
            per_query[qid] = {}
            for k in KS:
                top = results[:k]
                known = [d for d in top if d in grades]
                unresolved = [d for d in top if (qid, d) in conflicts]
                unknown = [d for d in top if d not in grades and (qid, d) not in conflicts]
                strict = evaluate(results, grades, k=k, complete=exhaustive)
                condensed = [did for did in results if did in grades]
                condensed_metrics = (
                    evaluate(condensed, grades, k=min(k, len(condensed)), complete=True)
                    if condensed
                    else None
                )
                per_query[qid][str(k)] = {
                    "coverage": {
                        "returned": len(top),
                        "judged": len(known),
                        "unjudged": len(unknown),
                        "conflicts": len(unresolved),
                        "fraction": len(known) / len(top) if top else None,
                    },
                    "strict": strict,
                    "not_calculable": {
                        name: (
                            "Exige des jugements exhaustifs sur le corpus de la requête."
                            if name in {"recall_at_k", "ndcg_at_k"}
                            else "Des rangs déterminants ne sont pas jugés ou sont en conflit."
                        )
                        for name in METRICS
                        if strict[name] is None
                    },
                    "descriptive_judged_only": {
                        "label": "Sous-ensemble jugé uniquement ; sélection biaisée, pas une métrique complète du moteur.",
                        "judged_relevant_fraction_in_original_top_k": sum(
                            grades[d] >= 2 for d in known
                        )
                        / len(known)
                        if known
                        else None,
                        "mean_grade_in_original_top_k": sum(grades[d] for d in known) / len(known)
                        if known
                        else None,
                        "condensed_ranking_size": len(condensed),
                        "condensed_mrr": condensed_metrics["mrr"] if condensed_metrics else None,
                        "condensed_ndcg": condensed_metrics["ndcg_at_k"]
                        if condensed_metrics
                        else None,
                        "condensed_k": min(k, len(condensed)),
                        "condensed_scope": "Non-jugés retirés, rangs modifiés ; idéal limité aux jugements résolus disponibles. Aucune pertinence n'est déduite des absences.",
                    },
                    "available_in_campaign_pools": sum(
                        (qid, did) in available_pairs for did in top
                    ),
                    "missing_from_campaign_pools": [
                        did for did in top if (qid, did) not in available_pairs
                    ],
                    "pending_documents": unknown,
                    "conflicting_documents": unresolved,
                }
        summary = {}
        for k in KS:
            entries = [per_query[q["query_id"]][str(k)] for q in development]
            returned = sum(e["coverage"]["returned"] for e in entries)
            known = sum(e["coverage"]["judged"] for e in entries)
            summary[str(k)] = {
                "judged": known,
                "returned": returned,
                "coverage": known / returned if returned else None,
                "fully_covered_queries": sum(e["coverage"]["fraction"] == 1 for e in entries),
                "queries": len(entries),
                "insufficient_queries": [
                    q["query_id"]
                    for q in development
                    if per_query[q["query_id"]][str(k)]["coverage"]["returned"] > 0
                    and per_query[q["query_id"]][str(k)]["coverage"]["fraction"] != 1
                ],
                "empty_result_queries": [
                    q["query_id"]
                    for q in development
                    if per_query[q["query_id"]][str(k)]["coverage"]["returned"] == 0
                ],
                "metrics": {
                    name: summarize_defined([e["strict"][name] for e in entries])
                    for name in METRICS
                },
            }
        result["methods"][method] = {"per_query": per_query, "summary": summary}
    # Moyennes sur les mêmes requêtes seulement ; aucune sélection de gagnant.
    result["matched_queries"] = {}
    for k in KS:
        result["matched_queries"][str(k)] = {}
        for metric in METRICS:
            matched = [
                qid
                for qid in sorted(qids)
                if all(
                    result["methods"][m]["per_query"][qid][str(k)]["strict"][metric] is not None
                    for m in METHODS
                )
            ]
            result["matched_queries"][str(k)][metric] = {
                "query_ids": matched,
                "defined_queries": len(matched),
                "means": {
                    m: sum(
                        result["methods"][m]["per_query"][qid][str(k)]["strict"][metric]
                        for qid in matched
                    )
                    / len(matched)
                    if matched
                    else None
                    for m in METHODS
                },
                "warning": "Comparaison descriptive limitée aux mêmes requêtes calculables ; pas de classement définitif.",
            }
    return result


def summarize_defined(values):
    known = [v for v in values if v is not None]
    return {
        "mean": sum(known) / len(known) if known else None,
        "defined_queries": len(known),
        "total_queries": len(values),
    }
