"""Mesures strictes : aucune assimilation implicite des non-jugés à zéro."""

import math
from collections import defaultdict


def evaluate(results, judgments, *, k=10, complete=False):
    if type(k) is not int or k <= 0 or type(complete) is not bool:
        raise ValueError("Paramètres de mesure invalides.")
    if len(results) != len(set(results)):
        raise ValueError("Résultats dupliqués.")
    if any(type(v) is not int or not 0 <= v <= 3 for v in judgments.values()):
        raise ValueError("Notes invalides.")
    top = results[:k]
    judged = sum(d in judgments for d in top)
    relevant = {d for d, grade in judgments.items() if grade >= 2}
    fully_judged = judged == len(top) and bool(judgments)
    precision = sum(d in relevant for d in top) / k if fully_judged else None
    recall = (
        sum(d in relevant for d in top) / len(relevant)
        if fully_judged and complete and relevant
        else None
    )
    # MRR is defined over the full provided ranking, independently of k.
    rr = None
    if judgments:
        for rank, doc in enumerate(results, 1):
            if doc not in judgments:
                break
            if doc in relevant:
                rr = 1 / rank
                break
        else:
            rr = 0.0
    ideal = sorted(judgments.values(), reverse=True)[:k]
    idcg = sum((2**grade - 1) / math.log2(i + 2) for i, grade in enumerate(ideal))
    ndcg = (
        sum((2 ** judgments[d] - 1) / math.log2(i + 2) for i, d in enumerate(top)) / idcg
        if fully_judged and complete and idcg
        else None
    )
    return {
        "precision_at_k": precision,
        "recall_at_k": recall,
        "mrr": rr,
        "ndcg_at_k": ndcg,
        "k": k,
        "judged_at_k": judged,
        "returned_at_k": len(top),
        "judged_fraction": judged / len(top) if top else None,
        "judgment_count": len(judgments),
        "complete_judgments": complete,
        "warning": None if complete else "Jugements incomplets : Recall et nDCG non publiés.",
    }


def aggregate(queries, runs, judgments, *, k=10, complete=False):
    known = {q["query_id"] for q in queries}
    if set(runs) - known or set(judgments) - known:
        raise ValueError("Requête inconnue.")
    groups = defaultdict(list)
    per_query = {}
    for query in queries:
        qid = query["query_id"]
        score = evaluate(runs.get(qid, []), judgments.get(qid, {}), k=k, complete=complete)
        per_query[qid] = score
        for group in ("all", f"category:{query['category']}", f"split:{query['split']}"):
            groups[group].append(score)
    summary = {}
    for group, scores in groups.items():
        summary[group] = {}
        for metric in ("precision_at_k", "recall_at_k", "mrr", "ndcg_at_k"):
            values = [s[metric] for s in scores if s[metric] is not None]
            summary[group][metric] = {
                "mean": sum(values) / len(values) if values else None,
                "defined_queries": len(values),
                "total_queries": len(scores),
            }
    return {"per_query": per_query, "aggregates": summary}
