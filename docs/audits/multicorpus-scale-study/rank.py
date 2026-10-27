"""Classements globaux exacts, RRF et récupération distribuée sans quotas finaux."""

import collections
import gzip
import json
import time
from fractions import Fraction

from common import CACHE, HERE, PRIOR, read, rows, sha, write, write_rows
from lexical import score


def ordered_scores(values, id_order, positive=False):
    import numpy as np

    eligible = id_order
    if positive:
        eligible = eligible[values[eligible] > 0]
    order = eligible[np.argsort(-values[eligible], kind="stable")]
    ranks = np.zeros(len(values), dtype=np.int32)
    ranks[order] = np.arange(1, len(order) + 1, dtype=np.int32)
    return order, ranks


def fuse(left, right, lr, vr, ids):
    """RRF sur les rangs GLOBAUX, contribution seulement si récupéré par la branche."""
    values = {}
    for candidates, ranks in ((left, lr), (right, vr)):
        for raw in candidates:
            i = int(raw)
            r = int(ranks[i])
            assert r > 0
            values[i] = values.get(i, Fraction()) + Fraction(1, 60 + r)
    order = sorted(values, key=lambda i: (-values[i], ids[i]))
    return order, {i: r for r, i in enumerate(order, 1)}, values


def main():
    import numpy as np
    import psutil

    protocol = read(HERE / "protocol.json")
    assert sha(HERE / "queries.json") == read(HERE / "preregistration.json")["queries_sha256"]
    prep = read(CACHE / "scores.json")
    queries = read(HERE / "queries.json")["queries"]
    term_index = {t: i for i, t in enumerate(prep["terms"])}
    ids = np.load(CACHE / "ids.npy", mmap_mode="r", allow_pickle=False)
    all_id_order = np.load(CACHE / "id-order.npy", allow_pickle=False)
    tf = np.load(CACHE / "term-counts.npy", mmap_mode="r", allow_pickle=False)
    lengths = np.load(CACHE / "lengths.npy", allow_pickle=False)
    vector = np.load(CACHE / "vector-scores.npy", mmap_mode="r", allow_pickle=False)
    vectorB = np.load(CACHE / "historical-B-scores.npy", allow_pickle=False)
    historical = [d for d in rows(PRIOR / "data/corpus.jsonl") if d["status"] == "A"]
    hist_index = {d["id"]: i for i, d in enumerate(historical)}
    annotations = read(PRIOR / "annotations.json")["judgments"]
    byquery = collections.defaultdict(list)
    old_grades = {(j["query_id"], j["unit_id"]): j["grade"] for j in annotations}
    witnesses = []
    for j in annotations:
        if j["grade"] >= 2 and j["unit_id"] in hist_index:
            i = hist_index[j["unit_id"]]
            byquery[j["query_id"]].append((i, j))
            witnesses.append(
                dict(
                    query_id=j["query_id"],
                    g=i,
                    unit=historical[i],
                    original_judgment=j,
                    long_article=len(historical[i]["text"]) >= 1500,
                    ocr_case=historical[i]["document_key"] == "montigny-ostrevent",
                )
            )
    assert len(witnesses) == 270
    write_rows(HERE / "data/witnesses.jsonl", witnesses)
    write_rows(HERE / "data/history.jsonl", historical)
    old_runs = {
        (r["query_id"], r["population"], r["method"]): r
        for r in rows(PRIOR / "data/rankings.jsonl")
    }
    measurements = []
    summaries = []
    review_set = set()
    raw_records = []
    trace_records = []
    witness_records = []
    diagnostic = []
    baseline = []
    for size in protocol["stages"]:
        n = 269 + size
        id_order = all_id_order[all_id_order < n]
        stage_start = time.perf_counter()
        for qi, q in enumerate(queries):
            qid = q["id"]
            start = time.perf_counter()
            lex, stats = score(
                tf[:n], lengths[:n], [term_index[t] for t in prep["query_terms"][qi]]
            )
            lexical_score_ms = (time.perf_counter() - start) * 1000
            start = time.perf_counter()
            lo, lr = ordered_scores(lex, id_order, positive=True)
            lexical_sort_ms = (time.perf_counter() - start) * 1000
            start = time.perf_counter()
            vo, vr = ordered_scores(vector[qi, :n], id_order)
            vector_sort_ms = (time.perf_counter() - start) * 1000
            # This is a diagnostic of representation sensitivity, not a new model.
            altered = np.array(vector[qi, :n], copy=True)
            altered[:269] = vectorB[qi]
            _, br = ordered_scores(altered, id_order)
            diagnostic.append(
                dict(
                    size=size,
                    query_id=qid,
                    historical=[
                        dict(
                            g=i,
                            rank_A=int(vr[i]),
                            rank_B=int(br[i]),
                            score_A=float(vector[qi, i]),
                            score_B=float(vectorB[qi, i]),
                        )
                        for i in range(269)
                    ],
                )
            )
            lmodern = lo[lo >= 269][:1000]
            vmodern = vo[vo >= 269][:1000]
            lhistoric = lo[lo < 269]
            vhistoric = vo[vo < 269]
            raw_records.append(
                dict(
                    size=size,
                    query_id=qid,
                    lexical_statistics=stats,
                    global_lexical=[
                        dict(g=int(i), rank=int(lr[i]), score=float(lex[i])) for i in lo[:1000]
                    ],
                    global_vector=[
                        dict(g=int(i), rank=int(vr[i]), score=float(vector[qi, i]))
                        for i in vo[:1000]
                    ],
                    modern_lexical=[
                        dict(g=int(i), rank=int(lr[i]), score=float(lex[i])) for i in lmodern
                    ],
                    modern_vector=[
                        dict(g=int(i), rank=int(vr[i]), score=float(vector[qi, i])) for i in vmodern
                    ],
                    historical=[
                        dict(
                            g=i,
                            lexical_rank=int(lr[i]) or None,
                            vector_rank=int(vr[i]),
                            lexical_score=float(lex[i]),
                            vector_score=float(vector[qi, i]),
                        )
                        for i in range(269)
                    ],
                )
            )
            runs = [
                ("lexical", None, "global", list(map(int, lo[:100])), None, None, None),
                ("vector", None, "global", list(map(int, vo[:100])), None, None, None),
            ]
            for depth in protocol["depths"]:
                for strategy in protocol["strategies"]:
                    if strategy == "global":
                        lc, vc = lo[:depth], vo[:depth]
                    else:
                        lc = np.concatenate([lhistoric[:depth], lmodern[:depth]])
                        vc = np.concatenate([vhistoric[:depth], vmodern[:depth]])
                    start = time.perf_counter()
                    fused, fr, values = fuse(lc, vc, lr, vr, ids)
                    fusion_ms = (time.perf_counter() - start) * 1000
                    sets = (set(map(int, lc)), set(map(int, vc)))
                    runs.append(("hybrid", depth, strategy, fused, fr, sets, values))
                    measurements.append(
                        dict(
                            size=size,
                            query_id=qid,
                            strategy=strategy,
                            depth=depth,
                            lexical_score_ms=lexical_score_ms,
                            lexical_sort_ms=lexical_sort_ms,
                            vector_sort_ms=vector_sort_ms,
                            fusion_ms=fusion_ms,
                            lexical_candidates=len(lc),
                            vector_candidates=len(vc),
                            union_candidates=len(fused),
                            historical_candidates=sum(i < 269 for i in fused),
                        )
                    )
            for method, depth, strategy, order, fr, sets, values in runs:
                relevant = byquery[qid]
                ranks = lr if method == "lexical" else vr if method == "vector" else fr
                ls, vs = sets if sets else (set(map(int, lo[:50])), set(map(int, vo[:50])))

                def get_rank(i):
                    v = ranks.get(i) if isinstance(ranks, dict) else int(ranks[i])
                    return v or None

                recall = {
                    str(k): sum((get_rank(i) is not None and get_rank(i) <= k) for i, j in relevant)
                    for k in (10, 20, 50, 100)
                }
                candidate_hits = sum(i in ls or i in vs for i, j in relevant)
                hist_counts = {str(k): sum(i < 269 for i in order[:k]) for k in (10, 20, 50, 100)}
                known_bad = sum(
                    old_grades.get((qid, str(ids[i]))) == 0 for i in order[:10] if i < 269
                )
                summaries.append(
                    dict(
                        size=size,
                        query_id=qid,
                        method=method,
                        depth=depth,
                        strategy=strategy,
                        known_witnesses=len(relevant),
                        witnesses_at=recall,
                        candidate_witnesses_at_depth=candidate_hits,
                        historical_at=hist_counts,
                        known_historical_grade0_at10=known_bad,
                        returned_at10=min(10, len(order)),
                        union_candidates=len(order) if method == "hybrid" else None,
                    )
                )
                results = [
                    dict(
                        rank=k,
                        g=int(i),
                        score=float(values[i])
                        if values
                        else float(lex[i])
                        if method == "lexical"
                        else float(vector[qi, i]),
                    )
                    for k, i in enumerate(order[:100], 1)
                ]
                trace_records.append(
                    dict(
                        size=size,
                        query_id=qid,
                        method=method,
                        depth=depth,
                        strategy=strategy,
                        results=results,
                    )
                )
                if (
                    size in (240, 1000000)
                    and qid in protocol["qualitative_queries"]
                    and (
                        method in ("lexical", "vector")
                        or (strategy == "global" and depth in (50, 1000))
                        or (strategy == "distributed_global_ranks" and depth == 50)
                    )
                ):
                    review_set.update((qid, int(i)) for i in order[:10])
                for i, j in relevant:
                    witness_records.append(
                        dict(
                            size=size,
                            query_id=qid,
                            g=i,
                            unit_id=historical[i]["id"],
                            original_grade=j["grade"],
                            method=method,
                            depth=depth,
                            strategy=strategy,
                            lexical_rank=int(lr[i]) or None,
                            vector_rank=int(vr[i]),
                            lexical_score=float(lex[i]),
                            vector_score=float(vector[qi, i]),
                            in_lexical_candidates=i in ls,
                            in_vector_candidates=i in vs,
                            final_rank=get_rank(i),
                            candidate_depth=depth or 50,
                            final_score=float(values[i])
                            if values is not None and i in values
                            else None,
                        )
                    )
                if size == 240 and (
                    method in ("lexical", "vector")
                    or method == "hybrid"
                    and depth == 50
                    and strategy == "global"
                ):
                    previous = old_runs[
                        qid,
                        "mixed",
                        {"lexical": "lexical", "vector": "vector_A", "hybrid": "hybrid_A"}[method],
                    ]["results"][:10]
                    actual = [str(ids[i]) for i in order[:10]]
                    baseline.append(
                        dict(
                            query_id=qid,
                            method=method,
                            top10_identical=actual == [r["id"] for r in previous],
                            expected=[r["id"] for r in previous],
                            actual=actual,
                        )
                    )
            if qi % 10 == 0:
                print(
                    f"Rank size={size:,}, query={qid}; {time.perf_counter() - stage_start:.1f}s",
                    flush=True,
                )
        print(
            f"Finished size {size:,}; RSS {psutil.Process().memory_info().rss / 1024**3:.2f}GiB",
            flush=True,
        )
    for name, records in (
        ("raw-branches", raw_records),
        ("rankings", trace_records),
        ("witness-tracking", witness_records),
        ("representation-diagnostic", diagnostic),
    ):
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=(HERE / f"data/{name}.jsonl.gz").open("wb"), mtime=0
        ) as f:
            for r in records:
                f.write((json.dumps(r, ensure_ascii=False) + "\n").encode())
    write(HERE / "data/per-query-metrics.json", summaries)
    write(HERE / "data/ranking-costs.json", measurements)
    write(HERE / "data/reference-reproduction.json", baseline)
    write(
        HERE / "data/review-pairs.json", [dict(query_id=qid, g=i) for qid, i in sorted(review_set)]
    )
    print(
        f"{len(witness_records):,} witness trajectories; {len(review_set)} qualitative pairs; baseline top10 {sum(b['top10_identical'] for b in baseline)}/{len(baseline)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
