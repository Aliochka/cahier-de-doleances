"""Rejeu des1800 fusions à partir des résultats bruts, sans base ni calcul vectoriel."""

import gzip
import json
import subprocess

from common import HERE, PRIOR, ROOT, read, rows, sha, write
from rank import fuse


def gzrows(path):
    with gzip.open(path, "rt") as f:
        return [json.loads(line) for line in f]


def main():
    import numpy as np

    frozen = read(HERE / "preregistration.json")
    assert frozen["queries_sha256"] == sha(HERE / "queries.json") == sha(PRIOR / "queries.json")
    assert frozen["protocol_sha256"] == sha(HERE / "protocol.json")
    prior = read(HERE / "prior-audits-sha256.json")
    assert all(sha(ROOT / p) == h for p, h in prior.items())
    hist = rows(HERE / "data/history.jsonl")
    old = {d["id"]: d for d in rows(PRIOR / "data/corpus.jsonl")}
    assert len(hist) == 269 and all(d == old[d["id"]] for d in hist)
    branches = gzrows(HERE / "data/raw-branches.jsonl.gz")
    assert len(branches) == 180
    needed = set()
    for r in branches:
        for kind in ("global_lexical", "global_vector", "modern_lexical", "modern_vector"):
            branch = r[kind]
            assert len({x["g"] for x in branch}) == len(branch)
            assert all(x["rank"] >= 1 for x in branch)
            needed.update(x["g"] for x in branch)
    ids = {i: d["id"] for i, d in enumerate(hist)}
    seen_ids = set()
    seen_ord = set()
    actual = []
    base = []
    with gzip.open(HERE / "data/population-ids.jsonl.gz", "rt") as f:
        for count, line in enumerate(f, 1):
            d = json.loads(line)
            assert d["i"] == count - 1 and d["id"] not in seen_ids and d["ordinal"] not in seen_ord
            seen_ids.add(d["id"])
            seen_ord.add(d["ordinal"])
            actual.append(d["ordinal"])
            g = 269 + d["i"]
            if g in needed:
                ids[g] = d["id"]
            if count <= 240:
                base.append(d["id"])
    assert count == 1000000
    assert base == [d["id"] for d in rows(PRIOR / "data/corpus.jsonl") if d["status"] != "A"]
    n = read(HERE / "data/selection.json")["source_population"]
    permutation = np.random.Generator(np.random.PCG64(17892019)).permutation(n) + 1
    permutation = permutation[~np.isin(permutation, np.asarray(actual[:240]))]
    assert np.array_equal(actual[240:], permutation[: 1000000 - 240])
    assert needed <= ids.keys()
    expected = {
        (r["size"], r["query_id"], r["depth"], r["strategy"]): r
        for r in gzrows(HERE / "data/rankings.jsonl.gz")
        if r["method"] == "hybrid"
    }
    tracks = {
        (r["size"], r["query_id"], r["depth"], r["strategy"], r["g"]): r
        for r in gzrows(HERE / "data/witness-tracking.jsonl.gz")
        if r["method"] == "hybrid"
    }
    previous = {}
    counts = 0
    checked_tracks = 0
    for r in branches:
        size, qid = r["size"], r["query_id"]
        lr = {x["g"]: x["rank"] for kind in ("global_lexical", "modern_lexical") for x in r[kind]}
        vr = {x["g"]: x["rank"] for kind in ("global_vector", "modern_vector") for x in r[kind]}
        for h in r["historical"]:
            i = h["g"]
            vr[i] = h["vector_rank"]
            if h["lexical_rank"]:
                lr[i] = h["lexical_rank"]
            if (qid, i) in previous:
                oldscore, oldrank = previous[qid, i]
                assert h["vector_score"] == oldscore and h["vector_rank"] >= oldrank
            previous[qid, i] = (h["vector_score"], h["vector_rank"])
        for depth in read(HERE / "protocol.json")["depths"]:
            for strategy in ("global", "distributed_global_ranks"):
                if strategy == "global":
                    left = [x["g"] for x in r["global_lexical"][:depth]]
                    right = [x["g"] for x in r["global_vector"][:depth]]
                else:
                    left = sorted(
                        (h["g"] for h in r["historical"] if h["lexical_rank"]), key=lambda g: lr[g]
                    )[:depth] + [x["g"] for x in r["modern_lexical"][:depth]]
                    right = sorted(range(269), key=lambda g: vr[g])[:depth] + [
                        x["g"] for x in r["modern_vector"][:depth]
                    ]
                order, ranks, values = fuse(left, right, lr, vr, ids)
                actual_top = [
                    dict(rank=i, g=g, score=float(values[g])) for i, g in enumerate(order[:100], 1)
                ]
                assert actual_top == expected[size, qid, depth, strategy]["results"]
                for g in range(269):
                    key = size, qid, depth, strategy, g
                    if key in tracks:
                        t = tracks[key]
                        assert t["final_rank"] == ranks.get(g)
                        assert t["in_lexical_candidates"] == (g in left)
                        assert t["in_vector_candidates"] == (g in right)
                        checked_tracks += 1
                counts += 1
    assert counts == 1800 and checked_tracks == 16200
    judgments = read(HERE / "data/qualitative-judgments.json")
    pool = read(HERE / "data/qualitative-pool.json")
    assert len(pool) == len(judgments["judgments"]) == 445
    assert all(
        j["grade"] == j["original_judgment"]["grade"]
        and j["reason"] == j["original_judgment"]["reason"]
        for j in judgments["judgments"]
        if j["source"] == "inherited_1789_semantic_search"
    )
    assert all(r["top10_identical"] for r in read(HERE / "data/reference-reproduction.json"))
    # A per-corpus rank reset would incorrectly promote the historical item.
    correct = fuse(
        [0, 1], [0, 1], {0: 10000, 1: 1}, {0: 10000, 1: 2}, {0: "historic", 1: "modern"}
    )[0]
    compressed = fuse([0, 1], [0, 1], {0: 1, 1: 2}, {0: 1, 1: 2}, {0: "historic", 1: "modern"})[0]
    assert correct[0] == 1 and compressed[0] == 0
    diff = subprocess.check_output(
        ["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True
    ).splitlines()
    assert not diff
    write(
        HERE / "data/checks.json",
        dict(
            replayed_fusions=counts,
            verified_hybrid_witness_records=checked_tracks,
            all_witness_records=19440,
            unchanged_prior_audit_files=len(prior),
            reference_top10_reproductions=90,
            queries_identical=True,
            protocol_unchanged=True,
            nested_populations=True,
            unique_modern_units=1000000,
            deterministic_selection_reproduced=True,
            constant_historical_cosines=True,
            monotone_historical_vector_ranks=True,
            prior_judgments_unchanged=True,
            global_rank_vs_per_corpus_reset_counterexample_detected=True,
            no_database_connection_in_replay=True,
            tracked_application_diff=diff,
        ),
    )
    print(f"Replayed {counts} fusions; {checked_tracks} witness records; prior audits unchanged")


if __name__ == "__main__":
    main()
