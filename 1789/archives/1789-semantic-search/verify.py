# ruff: noqa: E402
"""Intégrité, fidélité, évaluations et contrôles négatifs de l'expérience."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import frozen_match  # noqa: E402

import copy
import math
import subprocess

from common import HERE, ROOT, read, rows, sha, text_sha, write


def validate_corpus(corpus, original):
    assert len({d["id"] for d in corpus}) == len(corpus) == 509
    assert sum(d["status"] == "A" for d in corpus) == 269
    for d in corpus:
        assert text_sha(d["text"]) == d["source_text_sha256"]
        if d["status"] == "A":
            u = original[d["id"]]
            assert u["status"] == "A"
            assert d["text"] == u["text"]
            assert d["parent_id"] == u["document_id"]
            assert d["references"]["text_spans"] == u["text_spans"]


def validate_segments(segments, docs, variant):
    import collections

    grouped = collections.defaultdict(list)
    for r in segments:
        d = docs[r["unit_id"]]
        assert 0 <= r["start"] < r["end"] <= len(d["text"])
        prefix = "" if variant == "A" else d["context_prefix"]
        assert r["text"] == prefix + d["text"][r["start"] : r["end"]]
        assert 1 <= r["tokens"] <= 1024
        grouped[d["id"]].append(r)
    for did, group in grouped.items():
        assert [r["segment_index"] for r in group] == list(range(len(group)))
        assert group[0]["start"] == 0 and group[-1]["end"] == len(docs[did]["text"])
        assert all(a["start"] < b["start"] <= a["end"] < b["end"] for a, b in zip(group, group[1:]))


def main():
    import numpy as np

    frozen = read(HERE / "preregistration.json")
    assert sha(HERE / "queries.json") == frozen["queries_sha256"]
    assert sha(HERE / "protocol.json") == frozen["protocol_sha256"]
    prior = read(HERE / "prior-audits-sha256.json")
    assert all(frozen_match(ROOT / p, h) for p, h in prior.items())
    preparation = read(HERE / "data/preparation.json")
    assert all(frozen_match(ROOT / p, h) for p, h in preparation["source_fingerprints"].items())
    assert preparation["corpus_sha256"] == sha(HERE / "data/corpus.jsonl")
    original = {u["id"]: u for u in rows(HERE.parent / "1789-extraction-pilot/data/units.jsonl")}
    corpus = rows(HERE / "data/corpus.jsonl")
    validate_corpus(corpus, original)
    docs = {d["id"]: d for d in corpus}
    modern = [d for d in corpus if d["status"] != "A"]
    assert len({d["parent_id"] for d in modern}) == 240
    encoding = read(HERE / "data/encoding.json")
    assert all(sha(HERE / "vectors" / p) == h for p, h in encoding["vector_files"].items())
    segments = rows(HERE / "data/historical-segments.jsonl")
    for variant in ("A", "B"):
        group = [r for r in segments if r["variant"] == variant]
        validate_segments(group, docs, variant)
        array = np.load(HERE / f"vectors/historical_{variant}.npy", allow_pickle=False)
        assert array.shape == (len(group), 1024)
    validate_segments(rows(HERE / "data/contemporary-segments.jsonl"), docs, "B")
    for name in ("historical_A", "historical_B", "contemporary", "queries", "precision-check-fp32"):
        arr = np.load(HERE / f"vectors/{name}.npy", allow_pickle=False)
        assert arr.dtype == np.float32 and arr.shape[1] == 1024
        assert np.isfinite(arr).all()
        assert np.max(np.abs(np.linalg.norm(arr, axis=1) - 1)) < 1e-5
    annotations = read(HERE / "annotations.json")
    assert annotations["pool_sha256"] == sha(HERE / "data/review-pool.jsonl")
    judgments = {(j["query_id"], j["unit_id"]): j for j in annotations["judgments"]}
    assert len(judgments) == 1155
    for j in judgments.values():
        assert j["grade"] in range(4) and j["reason"].strip()
        assert j["evidence_text"] == docs[j["unit_id"]]["text"]
    # An override must not leak its grade/reason to subsequent IDs in a group.
    short = {d["short_id"]: d["id"] for d in corpus}
    assert judgments["q08", short["h026"]]["grade"] == 0
    assert judgments["q08", short["h159"]]["grade"] == 2
    assert judgments["q26", short["h158"]]["grade"] == 1
    assert judgments["q28", short["h158"]]["grade"] == 1
    rankings = rows(HERE / "data/rankings.jsonl")
    assert len(rankings) == 300
    assert len({(r["query_id"], r["population"], r["method"]) for r in rankings}) == 300
    for r in rankings:
        result = r["results"]
        assert len({x["id"] for x in result}) == len(result)
        assert result == sorted(result, key=lambda x: (-x["score"], x["id"]))
        assert [x["rank"] for x in result] == list(range(1, len(result) + 1))
        assert all(math.isfinite(x["score"]) for x in result)
        if r["population"] == "historical":
            assert all(docs[x["id"]]["status"] == "A" for x in result)
        for x in result[:10]:
            assert (r["query_id"], x["id"]) in judgments
    # Corruption checks use copies in memory, never mutate the artifacts.
    mutations = []
    for name, mutate in (
        ("duplicate_id", lambda c: c.__setitem__(1, copy.deepcopy(c[0]))),
        ("altered_text", lambda c: c[0].__setitem__("text", c[0]["text"] + " MODERNISÉ")),
        ("wrong_parent", lambda c: c[0].__setitem__("parent_id", c[9]["parent_id"])),
        ("wrong_status", lambda c: c[0].__setitem__("status", "B")),
    ):
        copied = copy.deepcopy(corpus)
        mutate(copied)
        try:
            validate_corpus(copied, original)
        except AssertionError:
            mutations.append(name)
        else:
            raise AssertionError(f"Undetected corruption: {name}")
    for name, field, value in (
        ("bad_offset", "end", 99999999),
        ("altered_embedding_text", "text", "Réécriture moderne"),
    ):
        copied = copy.deepcopy([r for r in segments if r["variant"] == "A"])
        copied[0][field] = value
        try:
            validate_segments(copied, docs, "A")
        except AssertionError:
            mutations.append(name)
        else:
            raise AssertionError(name)
    diff = subprocess.check_output(
        ["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True
    ).splitlines()
    assert diff == []
    write(
        HERE / "data/checks.json",
        dict(
            corpus=509,
            historical_status_A=269,
            modern_distinct_parents=240,
            ranking_runs=300,
            annotated_top10_pool_pairs=1139,
            additional_judged_pairs=16,
            prior_audit_files_unchanged=len(prior),
            local_embedding_artifacts_unchanged=len(preparation["source_fingerprints"]),
            source_fidelity=True,
            segment_coverage=True,
            finite_unit_norm_vectors=True,
            all_top10_judged=True,
            query_and_protocol_unchanged=True,
            mutation_checks_detected=mutations,
            tracked_diff=diff,
            database_access=False,
            external_inference=False,
        ),
    )
    print("All integrity, fidelity, annotation and6 mutation checks passed")


if __name__ == "__main__":
    main()
