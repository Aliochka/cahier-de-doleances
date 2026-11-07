"""Reproducible laboratory observations, not relevance judgements or a gold set."""

import json
import platform
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sqlalchemy import text

from .representations import gate

QUERIES = [
    ("geographic", "Agen"),
    ("geographic", "Amiens"),
    ("geographic", "Beauvais"),
    ("geographic", "Saint-Pierre-le-Moutier"),
    ("theme", "Suppression des privilèges"),
    ("theme", "Impôts et fiscalité"),
    ("theme", "Justice seigneuriale"),
    ("theme", "Abolition des corporations"),
    ("theme", "Éducation des enfants"),
    ("theme", "Entretien des routes"),
    ("combined", "Agen agriculture"),
    ("combined", "Amiens traitement des curés"),
    ("combined", "Beauvais jurandes"),
    ("combined", "Noblesse fiscalité"),
    ("difficult", "roi"),
    ("difficult", "gabelle"),
    ("difficult", "liberté syndicale"),
    ("difficult", "zxqv1789inexistant"),
    ("difficult", "claire et pruise"),
    ("difficult", "suppression des lettres de cachet"),
]


def distributions(samples):
    if not samples:
        return {}
    ordered = sorted(samples)
    return {
        "n": len(samples),
        "p50": statistics.median(samples),
        "p95": ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))],
        "p99": ordered[min(len(ordered) - 1, int(0.99 * len(ordered)))],
        "min": ordered[0],
        "max": ordered[-1],
    }


def benchmark(service, output, *, repeats=3):
    if not 1 <= repeats <= 10:
        raise ValueError("Benchmark repeats must be 1–10")
    records, comparisons = [], []
    # First use includes model load; OS/PostgreSQL caches are deliberately not called cold.
    first = service.search("Agen agriculture", mode="compare")
    cold = {
        "kind": "first application query; model cold, DB/OS cache uncontrolled",
        "timings": first["timings"],
    }
    for category, query in QUERIES:
        response = service.search(query, mode="compare", depth=50)
        comparisons.append(
            {
                "category": category,
                "query": query,
                "lexical": [
                    {"title": r["title"], "document_id": r["document_id"], "score": r["score"]}
                    for r in response["lexical"][:5]
                ],
                "vector": [
                    {"title": r["title"], "document_id": r["document_id"], "score": r["score"]}
                    for r in response["vector"][:5]
                ],
                "hybrid": [
                    {
                        "title": r["title"],
                        "document_id": r["document_id"],
                        "unit_id": r["witness"]["unit_id"],
                        "excerpt": r["excerpt"],
                        "witness_origin": r["witness_origin"],
                        "score": r["score"],
                    }
                    for r in response["items"][:5]
                ],
                "judgement": None,
            }
        )
    for depth in (50, 100, 200):
        for mode in ("lexical", "vector", "hybrid"):
            for repeat in range(repeats):
                for query in ("Agen agriculture", "roi", "zxqv1789inexistant"):
                    response = service.search(query, mode=mode, depth=depth)
                    records.append(
                        {
                            "depth": depth,
                            "mode": mode,
                            "repeat": repeat,
                            "query": query,
                            "documents": len(response["items"]),
                            "timings": response["timings"],
                        }
                    )

    def simultaneous(index):
        start = time.perf_counter()
        try:
            result = service.search("justice seigneuriale", mode="hybrid")
            return {
                "accepted": True,
                "seconds": time.perf_counter() - start,
                "timings": result["timings"],
            }
        except RuntimeError:
            return {
                "accepted": False,
                "seconds": time.perf_counter() - start,
                "reason": "bounded single-encoder admission",
            }

    with ThreadPoolExecutor(max_workers=4) as pool:
        concurrent = list(pool.map(simultaneous, range(4)))
    service.search("Agen agriculture", mode="compare")
    summaries = {}
    for depth in (50, 100, 200):
        for mode in ("lexical", "vector", "hybrid"):
            subset = [r for r in records if r["depth"] == depth and r["mode"] == mode]
            summaries[f"{mode}-{depth}"] = {
                key: distributions([r["timings"][key] for r in subset]) for key in first["timings"]
            }
    with service.destination.transaction(readonly=True) as c:
        release = gate(c)
        plans = {
            name: c.execute(
                text("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) " + sql), params
            ).scalar_one()
            for name, (sql, params) in service.last_sql.items()
        }
    result = {
        "hardware": platform.platform(),
        "cold_application": cold,
        "warm": summaries,
        "records": records,
        "concurrent": concurrent,
        "comparisons": comparisons,
        "plans": plans,
        "embedding_recipe": release["embedding_recipe"],
        "lexical_recipe": release["lexical_recipe"],
        "limits": [
            "No gold judgements; query examples are not ground truth",
            "OS page cache not flushed; first-use application measurement is not a cold-disk measurement",
            "No ANN; vector grouping occurs after exact full eligible scan and before document limit",
        ],
    }
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return {
        "output": str(output),
        "requests": len(records),
        "warm": summaries,
        "cold_application": cold,
        "concurrent": concurrent,
    }
