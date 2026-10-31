# ruff: noqa: E402
"""Fidélité, rattachement, navigation et tests d'erreurs injectées, sans base."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import frozen_match  # noqa: E402

import copy
import gzip
import json

from common import HERE, PILOT, REPO, REVISION, read, rows, sha, source_ref, sources, write
from data_io import units as load_units
from fast_blocks import cache_nodes


def check_unit(u, d, s):
    assert u["document_id"] == d["id"]
    a, b = u["start"], u["end"]
    start, end = d["source_text_start"], d["source_text_end"]
    assert start <= a < b <= end
    assert u["parent_start"] == a - start and u["parent_end"] == b - start
    spans = u["text_spans"]
    assert all(a <= x < y <= b for x, y in spans)
    assert all(spans[i - 1][1] <= spans[i][0] for i in range(1, len(spans)))
    assert u["text"] == "".join(s.text[x:y] for x, y in spans)
    assert u["text_sha256"] == sha(u["text"])
    assert d["full_text"][a - start : b - start] == s.text[a:b]
    for xp in u["xml_blocks"]:
        assert s.node(xp) is not None


def main():
    ss = sources()
    write(
        HERE / "data/source-manifest.json",
        dict(
            revision=REVISION,
            volumes=[
                dict(volume=v, bytes=s.path.stat().st_size, **source_ref(s)) for v, s in ss.items()
            ],
            no_source_download=True,
        ),
    )
    for s in ss.values():
        cache_nodes(s)
    for name in ["freeze.json", "reference-freeze.json"]:
        assert all(frozen_match(HERE / p, h) for p, h in read(HERE / name)["files"].items())
    old = read(HERE / "prior-audits-sha256.json")
    assert all(frozen_match(REPO / p, h) for p, h in old.items())
    with gzip.open(HERE / "data/documents.jsonl.gz", "rt") as f:
        docs = [json.loads(line) for line in f]
    byid = {d["id"]: d for d in docs}
    us = load_units()
    assert len(docs) == len(byid) == 200
    assert len(us) == len({u["id"] for u in us})
    assert len({(u["document_id"], u["start"], u["end"]) for u in us}) == len(us)
    for d in docs:
        s = ss[d["volume"]]
        assert d["full_text"] == s.text[d["source_text_start"] : d["source_text_end"]]
        current = sorted([u for u in us if u["document_id"] == d["id"]], key=lambda u: u["start"])
        assert d["unit_ids"] == [u["id"] for u in current]
        for i, u in enumerate(current):
            check_unit(u, d, s)
            assert u["order"] == i + 1
            assert u["previous_unit_id"] == (current[i - 1]["id"] if i else None)
            assert u["next_unit_id"] == (current[i + 1]["id"] if i + 1 < len(current) else None)
            if i:
                assert current[i - 1]["end"] <= u["start"]
    with gzip.open(HERE / "data/retained-C.jsonl.gz", "rt") as f:
        retained = [json.loads(line) for line in f]
    for r in retained:
        d = byid[r["document_id"]]
        s = ss[d["volume"]]
        assert r["text"] == s.text[r["start"] : r["end"]]
        assert d["source_text_start"] <= r["start"] < r["end"] <= d["source_text_end"]
    for d in docs:
        if d["origin"] == "inherited_pilot_30":
            continue
        spans = sorted(
            [span for u in us if u["document_id"] == d["id"] for span in u["text_spans"]]
            + [[r["start"], r["end"]] for r in retained if r["document_id"] == d["id"]]
        )
        cursor = d["source_text_start"]
        s = ss[d["volume"]]
        for a, b in spans:
            assert a >= cursor and not s.text[cursor:a].strip()
            cursor = b
        assert not s.text[cursor : d["source_text_end"]].strip()
    prior_d = {d["id"]: d for d in rows(PILOT / "data/documents.jsonl")}
    prior_u = {u["id"]: u for u in rows(PILOT / "data/units.jsonl")}
    current_u = {u["id"]: u for u in us}
    assert all(byid[did]["full_text"] == d["full_text"] for did, d in prior_d.items())
    assert all(all(current_u[uid][k] == v for k, v in u.items()) for uid, u in prior_u.items())
    gold = {
        (d["candidate_id"], u["start"], u["end"])
        for d in rows(HERE / "data/reference-documents.jsonl")
        for w in d["reference_windows"]
        for u in w["units"]
    }
    new_A = [u for u in us if u["status"] == "A" and u.get("origin") != "inherited_pilot_30"]
    assert len(new_A) == len(gold) == 48
    assert {(u["candidate_id"], u["start"], u["end"]) for u in new_A} == gold
    raw = {u["id"]: u for u in rows(HERE / "data/automatic-units.jsonl")}
    links = [
        x for x in read(HERE / "data/crosswalk.json") if x["kind"] == "automatic_to_final_unit"
    ]
    assert {x["old_id"] for x in links} == raw.keys()
    assert len(links) == len(raw) == 5445
    current = {u["id"]: u for u in us}
    for link in links:
        before = raw[link["old_id"]]
        for uid in link["new_ids"]:
            after = current[uid]
            assert before["start"] < after["end"] and after["start"] < before["end"]
    # Deliberate invalid records must fail: not tests that merely echo a regex.
    sample = new_A[0]
    parent = byid[sample["document_id"]]
    s = ss[parent["volume"]]
    faults = {
        "text_rewritten": lambda u: u.update(text=u["text"] + " CORRECTION"),
        "wrong_parent_id": lambda u: u.update(document_id="wrong-parent"),
        "outside_parent": lambda u: u.update(start=parent["source_text_start"] - 1),
        "bad_parent_offset": lambda u: u.update(parent_start=u["parent_start"] + 1),
        "bad_source_span": lambda u: u.update(text_spans=[[u["start"], u["end"] + 1]]),
        "bad_text_hash": lambda u: u.update(text_sha256="0" * 64),
    }
    detected = []
    for name, mutate in faults.items():
        damaged = copy.deepcopy(sample)
        mutate(damaged)
        try:
            check_unit(damaged, parent, s)
        except AssertionError:
            detected.append(name)
    assert len(detected) == len(faults)
    write(
        HERE / "data/checks.json",
        dict(
            documents=200,
            units=len(us),
            retained_C=len(retained),
            source_faithfulness=True,
            parent_and_xml_ranges=True,
            all_new_text_retained_between_AB_and_C=True,
            unique_unit_ids=True,
            no_duplicate_unit_intervals=True,
            neighbor_navigation=True,
            legacy_parents_preserved=30,
            legacy_units_preserved=759,
            new_A_reference_matches=48,
            automatic_unit_crosswalks_checked=5445,
            frozen_rules_unchanged=True,
            frozen_reference_unchanged=True,
            prior_audit_files_unchanged=len(old),
            injected_faults_detected=detected,
            no_database_access=True,
        ),
    )
    print(
        "Verified",
        len(docs),
        "parents,",
        len(us),
        "units;",
        len(detected),
        "injected faults detected;",
        len(old),
        "prior files unchanged",
    )


if __name__ == "__main__":
    main()
