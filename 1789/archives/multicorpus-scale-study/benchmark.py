"""Coût exact en mémoire, séparé des lectures PostgreSQL et de l'encodage."""

import collections
import gzip
import json
import statistics
import time

from common import CACHE, HERE, read, write
from lexical import score
from rank import ordered_scores


def main():
    import numpy as np
    import psutil

    export = read(CACHE / "export.json")
    prep = read(CACHE / "scores.json")
    vectors = np.memmap(
        CACHE / "modern.f32", mode="r", dtype="<f4", shape=(export["segments"], 1024)
    )
    mapping = np.memmap(CACHE / "segment-unit.u32", mode="r", dtype="<u4")
    tf = np.load(CACHE / "term-counts.npy", mmap_mode="r", allow_pickle=False)
    lengths = np.load(CACHE / "lengths.npy", allow_pickle=False)
    from common import PRIOR

    query = np.load(PRIOR / "vectors/queries.npy", allow_pickle=False)
    tie = np.load(CACHE / "id-order.npy", allow_pickle=False)
    terms = {t: i for i, t in enumerate(prep["terms"])}
    process = psutil.Process()
    results = []
    for size in read(HERE / "protocol.json")["stages"]:
        start = time.perf_counter()
        rows = np.flatnonzero(mapping < size)
        mat = vectors if size == 1000000 else np.asarray(vectors[rows])
        indices = mapping if size == 1000000 else np.asarray(mapping[rows])
        prepare_seconds = time.perf_counter() - start
        localtie = tie[tie < 269 + size]
        values = []
        # Fixed queries spanning fiscality, justice and a digital counterexample.
        for qi in (0, 5, 24):
            start = time.perf_counter()
            raw = mat @ query[qi]
            best = np.full(size, -np.inf, dtype=np.float32)
            np.maximum.at(best, indices, raw)
            dot_ms = (time.perf_counter() - start) * 1000
            start = time.perf_counter()
            # Historical scoring is negligible and separately cached; this measures2019.
            localmodern = localtie[localtie >= 269] - 269
            ordered_scores(best, localmodern)
            vector_sort_ms = (time.perf_counter() - start) * 1000
            start = time.perf_counter()
            lex, _ = score(
                tf[: 269 + size], lengths[: 269 + size], [terms[t] for t in prep["query_terms"][qi]]
            )
            lexical_score_ms = (time.perf_counter() - start) * 1000
            start = time.perf_counter()
            ordered_scores(lex, localtie, positive=True)
            lexical_sort_ms = (time.perf_counter() - start) * 1000
            values.append(
                dict(
                    query_id=f"q{qi + 1:02}",
                    vector_dot_aggregation_ms=dot_ms,
                    vector_full_sort_ms=vector_sort_ms,
                    lexical_score_ms=lexical_score_ms,
                    lexical_full_sort_ms=lexical_sort_ms,
                )
            )
        results.append(
            dict(
                size=size,
                modern_segments=len(rows),
                raw_vector_bytes=len(rows) * 1024 * 4,
                subset_preparation_seconds=prepare_seconds,
                rss_bytes=process.memory_info().rss,
                measurements=values,
                median_ms={
                    k: statistics.median(v[k] for v in values) for k in values[0] if k != "query_id"
                },
            )
        )
        print(
            "Benchmark", size, "RSS GiB", round(process.memory_info().rss / 1024**3, 2), flush=True
        )
        del mat, indices
    # Exact duplicate text counts, not deduplication or weighting of the rankings.
    histogram = collections.Counter()
    duplicate_stats = []
    stages = set(read(HERE / "protocol.json")["stages"])
    with gzip.open(CACHE / "modern.jsonl.gz", "rt") as f:
        for i, line in enumerate(f, 1):
            d = json.loads(line)
            histogram[d["source_text_sha256"]] += 1
            if i in stages:
                duplicate_stats.append(
                    dict(
                        size=i,
                        distinct_text_hashes=len(histogram),
                        repeated_text_occurrences=i - len(histogram),
                        definition="Exact answer text SHA256; same short answer to different questions can repeat; not removed",
                    )
                )
    write(
        HERE / "data/performance.json",
        dict(
            kind="local exact in-memory, cached inputs; not PostgreSQL service latency",
            new_query_encodings=0,
            query_encoding_cost_included=False,
            blas_threads=4,
            per_stage=results,
            duplicate_text_counts=duplicate_stats,
            cache_bytes=sum(p.stat().st_size for p in CACHE.iterdir() if p.is_file()),
            sql_export_seconds=export["seconds"],
            lexical_preparation_seconds=prep["tokenization_seconds"],
            full_30_query_vector_score_seconds=sum(r["seconds"] for r in prep["vector_timings"]),
        ),
    )


if __name__ == "__main__":
    main()
