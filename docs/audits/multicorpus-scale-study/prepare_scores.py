"""Cache de scores exacts et statistiques lexicales ; aucun modèle chargé."""

import gzip
import json
import time

from common import CACHE, HERE, PRIOR, read, rows, sha, write
from lexical import French, prepare_text, query_terms


def main():
    import numpy as np
    import psutil

    started = time.perf_counter()
    report = read(CACHE / "export.json")
    assert report["complete"] and report["documents"] == 1000000
    assert all(sha(CACHE / p) == h for p, h in report["files"].items())
    history = [d for d in rows(PRIOR / "data/corpus.jsonl") if d["status"] == "A"]
    questions = read(HERE / "queries.json")["queries"]
    french = French()
    perquery = query_terms(questions, french)
    terms = sorted({t for ts in perquery for t in ts})
    term_index = {t: i for i, t in enumerate(terms)}
    total = 269 + report["documents"]
    counts = np.lib.format.open_memmap(
        CACHE / "term-counts.npy", mode="w+", dtype=np.uint32, shape=(total, len(terms))
    )
    counts[:] = 0
    lengths = np.zeros(total, dtype=np.uint32)
    parents = np.zeros(report["documents"], dtype=np.int64)
    forms = np.zeros(report["documents"], dtype=np.int16)
    ids = []
    for i, d in enumerate(history):
        ids.append(d["id"])
        lengths[i], cc = prepare_text(d["text"], french, term_index)
        for j, value in cc:
            counts[i, j] = value
    history_end = time.perf_counter()
    with gzip.open(CACHE / "modern.jsonl.gz", "rt") as f:
        for i, line in enumerate(f):
            d = json.loads(line)
            assert d["i"] == i
            at = 269 + i
            ids.append(d["id"])
            lengths[at], cc = prepare_text(d["text"], french, term_index)
            for j, value in cc:
                counts[at, j] = value
            parents[i] = int(d["parent_id"])
            forms[i] = int(d["questionnaire_id"])
            if i % 100000 == 0:
                print(
                    f"Lexical preparation {i:,}/1,000,000; {time.perf_counter() - started:.1f}s",
                    flush=True,
                )
    assert i == 999999 and len(set(ids)) == total
    counts.flush()
    np.save(CACHE / "lengths.npy", lengths, allow_pickle=False)
    np.save(CACHE / "parents.npy", parents, allow_pickle=False)
    np.save(CACHE / "forms.npy", forms, allow_pickle=False)
    # Stable lexical ID order, reused for every method's score ties.
    id_order = np.asarray(sorted(range(total), key=lambda i: ids[i]), dtype=np.int32)
    np.save(CACHE / "id-order.npy", id_order, allow_pickle=False)
    np.save(CACHE / "ids.npy", np.asarray(ids), allow_pickle=False)
    token_seconds = time.perf_counter() - history_end
    distinct_stems = len(french.cache)
    french.close()
    query = np.load(PRIOR / "vectors/queries.npy", allow_pickle=False)
    matrix = np.memmap(
        CACHE / "modern.f32", mode="r", dtype="<f4", shape=(report["segments"], 1024)
    )
    segment_unit = np.memmap(CACHE / "segment-unit.u32", mode="r", dtype="<u4")
    scores = np.lib.format.open_memmap(
        CACHE / "vector-scores.npy", mode="w+", dtype=np.float32, shape=(30, total)
    )
    historical_vectors = np.load(PRIOR / "vectors/historical_A.npy", allow_pickle=False)
    hs = [r for r in rows(PRIOR / "data/historical-segments.jsonl") if r["variant"] == "A"]
    hi = {d["id"]: i for i, d in enumerate(history)}
    hmap = np.array([hi[r["unit_id"]] for r in hs])
    timing = []
    for qi, q in enumerate(questions):
        start = time.perf_counter()
        values = matrix @ query[qi]
        best = np.full(report["documents"], -np.inf, dtype=np.float32)
        np.maximum.at(best, segment_unit, values)
        hbest = np.full(269, -np.inf, dtype=np.float32)
        np.maximum.at(hbest, hmap, historical_vectors @ query[qi])
        scores[qi] = np.concatenate([hbest, best])
        assert np.isfinite(scores[qi]).all()
        timing.append(dict(query_id=q["id"], seconds=time.perf_counter() - start))
        if qi % 5 == 0:
            print(f"Exact vector scores {qi + 1}/30", flush=True)
    scores.flush()
    hB = np.load(PRIOR / "vectors/historical_B.npy", allow_pickle=False)
    hsB = [r for r in rows(PRIOR / "data/historical-segments.jsonl") if r["variant"] == "B"]
    bmap = np.array([hi[r["unit_id"]] for r in hsB])
    b = np.full((30, 269), -np.inf, dtype=np.float32)
    for qi in range(30):
        np.maximum.at(b[qi], bmap, hB @ query[qi])
    np.save(CACHE / "historical-B-scores.npy", b, allow_pickle=False)
    stages = []
    for size in read(HERE / "protocol.json")["stages"]:
        stages.append(
            dict(
                size=size,
                distinct_parents=len(np.unique(parents[:size])),
                additional_answers_same_parent=size - len(np.unique(parents[:size])),
                questionnaires={
                    str(k): int(v) for k, v in zip(*np.unique(forms[:size], return_counts=True))
                },
                sum_lexical_lengths=int(lengths[: 269 + size].sum()),
                mean_lexical_length=float(lengths[: 269 + size].mean()),
            )
        )
    artifacts = [
        "term-counts.npy",
        "lengths.npy",
        "parents.npy",
        "forms.npy",
        "ids.npy",
        "id-order.npy",
        "vector-scores.npy",
        "historical-B-scores.npy",
    ]
    write(
        CACHE / "scores.json",
        dict(
            terms=terms,
            query_terms=perquery,
            queries_sha256=sha(HERE / "queries.json"),
            export_sha256=sha(CACHE / "export.json"),
            total_seconds=time.perf_counter() - started,
            tokenization_seconds=token_seconds,
            distinct_stems=distinct_stems,
            vector_timings=timing,
            stages=stages,
            rss_bytes=psutil.Process().memory_info().rss,
            cache=str(CACHE),
            files={p: sha(CACHE / p) for p in artifacts},
        ),
    )
    write(HERE / "data/preparation.json", read(CACHE / "scores.json"))
    print("Prepared full exact score cache", flush=True)


if __name__ == "__main__":
    main()
