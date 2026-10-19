"""Micro-mesure CPU limitée ; résultats distincts du cache de l'expérience GPU."""

import time

from cahier_rag.annotation.session import atomic_json
from cahier_rag.embeddings.benchmark import MemorySampler
from cahier_rag.reranking.contracts import validate_scores
from cahier_rag.reranking.planning import iter_units, load_plan


def cpu_benchmark(directory, backend, output):
    if backend.device != "cpu":
        raise ValueError("Benchmark CPU exclusivement.")
    manifest, _ = load_plan(directory)
    chosen = []
    iterator = iter_units(directory, manifest)
    try:
        for entry, items in iterator:
            if len(items) == 1 and max(entry["segments"][0]["tokens"].values()) <= 256:
                chosen.append(items[0])
            if len(chosen) == 3:
                break
    finally:
        iterator.close()
    if len(chosen) < 3:
        raise ValueError("Trois couples courts requis pour le benchmark CPU borné.")
    if output.exists():
        raise ValueError("Sortie CPU existante.")
    rows = []
    with MemorySampler() as memory:
        try:
            backend.load()
            for item in chosen:
                before = time.perf_counter()
                score = validate_scores(backend.score([item]), 1)[0]
                elapsed = time.perf_counter() - before
                rows.append(
                    {
                        "query_id": item.query_id,
                        "document_id": item.document_id,
                        "input_hash": item.input_hash,
                        "tokens": backend.token_count(item.query, item.document),
                        "seconds": elapsed,
                        "score": score,
                    }
                )
            result = {
                "recipe": backend.recipe(),
                "plan_hash": manifest["manifest_hash"],
                "batch_size": 1,
                "load_seconds": backend.load_seconds,
                "rows": rows,
                "peak_rss_bytes": memory.peak,
                "warning": "Local Ryzen 7950X, 4 threads; no extrapolation to Wallace; first forward included",
            }
        finally:
            backend.close()
    result["peak_rss_bytes"] = memory.peak
    atomic_json(output, result)
    return result
