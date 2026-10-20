"""Rapport descriptif rejouable ; aucune lecture de jugements ou requêtes réservées."""

import json
import time
from fractions import Fraction
from statistics import mean

from cahier_rag.fullcorpus.audit import fingerprint
from cahier_rag.tuning.experiments import compare_rankings, latency_summary
from cahier_rag.tuning.selection import load_selection
from cahier_rag.vector.preparation import atomic_json


def fusion(rankings, depth=50):
    """Même RRF 60 à poids égaux que H1 ; données descriptives sans texte citoyen."""
    scores, documents = {}, {}
    for rows in rankings:
        seen = set()
        for rank, row in enumerate(rows[:depth], 1):
            did = row["document_id"]
            if did in seen:
                continue
            seen.add(did)
            documents[did] = row
            scores[did] = scores.get(did, Fraction()) + Fraction(1, 60 + rank)
    ids = sorted(scores, key=lambda did: (-scores[did], did))[:depth]
    return [documents[did] | {"score": float(scores[did])} for did in ids]


def describe(rows):
    return dict(
        documents=len(rows),
        contributions=len({r["contribution_id"] for r in rows}),
        repeated_texts=len(rows) - len({r["text_hash"] for r in rows}),
        short_under60=sum(r["length"] < 60 for r in rows),
        other_text=sum(r["unit_type"] == "other_text" for r in rows),
    )


def summarize(directory):
    if (directory / "selection.json").exists():
        recipe = json.loads((directory / "vector-recipe.json").read_text())
        selected_manifest = load_selection(directory / "selection.json", recipe["corpus_hash"])
        for name, expected in selected_manifest["evidence"].items():
            if fingerprint(json.loads((directory / name).read_text())) != expected:
                raise ValueError("Mesures modifiées depuis la sélection figée.")
    baseline = json.loads((directory / "baseline/lexical.json").read_text())
    lexical = json.loads((directory / "lexical.json").read_text())
    vectors = json.loads((directory / "vector.json").read_text())
    reference = {x["query_id"]: x for x in baseline if x["status"] == "ok"}
    selected = {
        x["query_id"]: x
        for x in lexical
        if x["recipe"] == "equivalent-statistics" and x["status"] == "ok"
    }
    output = {
        "version": 1,
        "purpose": "descriptive-only-no-relevance-judgments",
        "query_count": len(vectors),
        "lexical": {},
        "ann": {},
        "hybrid": [],
        "timing_scope": "First observed and warm; no system cache flush. Fusion measured on cached rankings; pipeline times are estimates.",
    }
    groups = {"rag026": baseline}
    groups.update(
        {
            name: [x for x in lexical if x["recipe"] == name]
            for name in {x["recipe"] for x in lexical}
        }
    )
    for name, rows in sorted(groups.items()):
        warm = [r for r in rows if r["pass"] > 0]
        values = [r["total_seconds"] for r in warm if r["status"] == "ok"]
        info = dict(
            warm_seconds=latency_summary(values), failures=sum(r["status"] != "ok" for r in warm)
        )
        if name != "rag026":
            comparable = [r for r in rows if r["status"] == "ok" and r["query_id"] in reference]
            changed = [
                r["query_id"]
                for r in comparable
                if [(a["document_id"], a["score"]) for a in r["ranking"]]
                != [(a["id"], a["score"]) for a in reference[r["query_id"]]["ranking"]]
            ]
            info.update(
                comparable_runs=len(comparable),
                changed_runs=len(changed),
                changed_queries=sorted(set(changed)),
            )
        output["lexical"][name] = info
    for name in sorted(vectors[0]["profiles"]):
        rows = [v["profiles"][name] for v in vectors]
        info = {
            "seconds": latency_summary([s for r in rows for s in r["seconds"]]),
            "comparison": {},
        }
        for k in (10, 20, 50, 100):
            metrics = [r["comparison"][str(k)] for r in rows]
            info["comparison"][str(k)] = {
                key: dict(
                    mean=mean(m[key] for m in metrics),
                    minimum=min(m[key] for m in metrics),
                    maximum=max(m[key] for m in metrics),
                )
                for key in (
                    "id_overlap",
                    "text_overlap",
                    "context_overlap",
                    "distance_regret",
                    "max_distance_regret",
                    "boundary_equivalent",
                )
            }
        output["ann"][name] = info
    for v in vectors:
        qid = v["query_id"]
        left = selected[qid]["ranking"]
        variants = {
            "optimized": v["profiles"]["ef1000"]["ranking"][:50],
            "reference": v["rag026_depth50"],
            "exact": v["exact"][:50],
        }
        item = dict(query_id=qid, variants={})
        for name, right in variants.items():
            before = time.perf_counter()
            rows = fusion([left, right])
            fusion_seconds = time.perf_counter() - before
            lexical_seconds = selected[qid]["total_seconds"]
            if name == "reference":
                if qid not in reference:
                    item["variants"][name] = dict(unavailable="historical lexical timeout")
                    continue
                lexical_seconds = reference[qid]["total_seconds"]
            vector_seconds = (
                v["exact_seconds"]
                if name == "exact"
                else mean(
                    v["profiles"]["ef1000" if name == "optimized" else "reference"]["seconds"]
                )
            )
            item["variants"][name] = dict(
                ranking=rows,
                description=describe(rows),
                top10=describe(rows[:10]),
                fusion_seconds=fusion_seconds,
                estimated_retrieval_seconds=lexical_seconds + vector_seconds + fusion_seconds,
                source_overlap=len(
                    {r["document_id"] for r in left} & {r["document_id"] for r in right}
                ),
            )
        exact = item["variants"]["exact"]["ranking"]
        item["comparison_with_exact"] = {
            name: {str(k): compare_rankings(exact, value["ranking"], k) for k in (10, 50)}
            for name, value in item["variants"].items()
            if "ranking" in value
        }
        output["hybrid"].append(item)
    atomic_json(directory / "comparison.json", output)
    return output
