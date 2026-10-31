# ruff: noqa: E402
"""Contrôles de fidélité, relations, erreurs injectées et cas négatifs.

Ne certifie PAS la justesse historique des unités B : comparaison matérielle et
contrôle des seules frontières explicitement annotées dans la référence A.
"""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import frozen_match  # noqa: E402

import argparse
import copy
import json
from collections import Counter

from common import ROOT, load_sources, read, sha, write
from extract import auto_parent


def lines(name):
    return [json.loads(line) for line in (ROOT / "data" / name).read_text().splitlines()]


def validate(documents, units, sources):
    assert len(documents) == 30
    assert len({d["id"] for d in documents}) == 30
    assert len({u["id"] for u in units}) == len(units), "duplicate unit id"
    parents = {d["id"]: d for d in documents}
    by_parent = {d["id"]: [] for d in documents}
    # Un contrôle distinct par document évite que des unités exactes soient attribuées au mauvais parent.
    for d in documents:
        s = sources[d["volume"]]
        a, b = d["source_text_start"], d["source_text_end"]
        assert d["full_text"] == s.text[a:b], "parent reconstruction mismatch"
        assert sha(d["full_text"]) == d["full_text_sha256"]
        assert s.sha256 == d["source_sha256"]
        assert sha(s.text) == d["source_text_sha256"]
        assert s.text == "".join(s.tree.getroot().itertext()), "decoded text offset model mismatch"
        assert (ROOT / "data" / "parents" / (d["key"] + ".txt")).read_text() == d["full_text"]
        for block in d["blocks"]:
            assert s.span(s.node(block["xpath"])) == [block["start"], block["end"]]
            assert a <= block["start"] <= block["end"] <= b
        for annotation in d["annotations"]:
            assert a <= annotation["start"] <= annotation["end"] <= b
        # Les 30 parents ne doivent pas se recouvrir dans un même volume.
        for other in documents:
            if other["id"] != d["id"] and other["volume"] == d["volume"]:
                assert not (other["source_text_start"] < b and other["source_text_end"] > a), (
                    "parent overlap"
                )
    spans_seen = set()
    for u in units:
        assert u["document_id"] in parents, "unknown parent"
        d = parents[u["document_id"]]
        s = sources[d["volume"]]
        assert d["source_text_start"] <= u["start"] < u["end"] <= d["source_text_end"], (
            "wrong parent or invalid range"
        )
        assert u["parent_start"] == u["start"] - d["source_text_start"]
        assert u["parent_end"] == u["end"] - d["source_text_start"]
        assert u["source_sha256"] == d["source_sha256"]
        assert u["volume"] == d["volume"] and u["document_key"] == d["key"]
        assert u["section_id"] in {section["id"] for section in d["sections"]}
        key = (d["volume"], u["start"], u["end"])
        assert key not in spans_seen, "duplicate source range"
        spans_seen.add(key)
        text = "".join(s.text[a:b] for a, b in u["text_spans"])
        assert text == u["text"] and sha(text) == u["text_sha256"], "unit source mismatch"
        assert u["xml_blocks"]
        previous_end = u["start"]
        for a, b in u["text_spans"]:
            assert u["start"] <= a < b <= u["end"]
            assert previous_end <= a
            previous_end = b
        for xp in u["xml_blocks"]:
            pstart, pend = s.span(s.node(xp))
            assert pstart < u["end"] and pend > u["start"], "XML locator does not intersect unit"
        for ann in d["annotations"]:
            if ann["kind"] in {
                "editorial_note",
                "editorial_note_unmarked",
                "editorial_running_header",
                "signatures",
            }:
                assert not any(a < ann["end"] and b > ann["start"] for a, b in u["text_spans"]), (
                    "annotation mixed into article"
                )
        expected_pages = s.pages_for(u["start"], u["end"])
        assert [
            {k: v for k, v in p.items() if k != "image_service"} for p in u["pages"]
        ] == expected_pages
        by_parent[d["id"]].append(u)
    for d in documents:
        us = by_parent[d["id"]]
        assert [u["id"] for u in us] == d["unit_ids"], "parent navigation order mismatch"
        for i, u in enumerate(us):
            assert u["order"] == i + 1, "unit ordinal mismatch"
            assert u["previous_unit_id"] == (us[i - 1]["id"] if i else None)
            assert u["next_unit_id"] == (us[i + 1]["id"] if i + 1 < len(us) else None)
            if i:
                assert us[i - 1]["end"] <= u["start"], "units overlap or out of order"


def run(directory):
    sources = load_sources(directory)
    documents, units = lines("documents.jsonl"), lines("units.jsonl")
    validate(documents, units, sources)
    reference = read("data/reference.json")
    gold = {
        (r["document_id"], u["start"], u["end"])
        for r in reference
        if r["certainty"] == "A"
        for u in r["units"]
    }
    accepted = {(u["document_id"], u["start"], u["end"]) for u in units if u["status"] == "A"}
    assert gold == accepted, "A must correspond exactly to reviewed boundaries"
    for r in lines("retained-unsegmented.jsonl"):
        d = next(d for d in documents if d["id"] == r["document_id"])
        s = sources[d["volume"]]
        assert s.text[r["start"] : r["end"]] == r["text"]
        assert d["source_text_start"] <= r["start"] < r["end"] <= d["source_text_end"]
        assert r["status"] == "C"
        assert not any(
            u["document_id"] == d["id"] and u["start"] < r["end"] and u["end"] > r["start"]
            for u in units
        )
    # Vérifier que les contrôles échouent réellement sur chacune des régressions visées.
    faults = []
    cases = [
        "duplicate",
        "invalid_range",
        "wrong_parent",
        "wrong_order",
        "changed_text",
        "changed_parent_text",
        "changed_source_fingerprint",
    ]
    for case in cases:
        ds, us = copy.deepcopy(documents), copy.deepcopy(units)
        if case == "duplicate":
            us.append(copy.deepcopy(us[0]))
        elif case == "invalid_range":
            us[0]["end"] = ds[0]["source_text_end"] + 1
        elif case == "wrong_parent":
            us[0]["document_id"] = ds[1]["id"]
        elif case == "wrong_order":
            us[0], us[1] = us[1], us[0]
        elif case == "changed_text":
            us[0]["text"] += " texte ajouté"
        elif case == "changed_parent_text":
            ds[0]["full_text"] += " texte ajouté"
        elif case == "changed_source_fingerprint":
            ds[0]["source_sha256"] = "0" * 64
        try:
            validate(ds, us, sources)
        except AssertionError:
            faults.append({"case": case, "detected": True})
        else:
            raise AssertionError("Undetected injected fault: " + case)
    negatives = []
    for case in read("negative-cases.json"):
        s = sources[case["volume"]]
        prediction = bool(auto_parent(s, case["xpath"]))
        node = s.node(case["xpath"])
        negatives.append(
            case
            | {
                "predicted_standalone_cahier": prediction,
                "correct": prediction == case["expected_standalone_cahier"],
                "title_exact": ["".join(n.itertext()) for n in node.findall("head")],
                "opening_exact": ["".join(n.itertext()) for n in node.findall("p")[:2]],
                "source_sha256": s.sha256,
            }
        )
    assert all(c["correct"] for c in negatives)
    baseline = read("prior-audits-sha256.json")
    for name, expected in baseline.items():
        assert frozen_match(ROOT.parent.parent.parent / name, expected), name
    duplicates = Counter(u["text_sha256"] for u in units)
    duplicate_texts = [
        {"text_sha256": h, "unit_ids": [u["id"] for u in units if u["text_sha256"] == h]}
        for h, n in duplicates.items()
        if n > 1
    ]
    result = {
        "parents": len(documents),
        "units": len(units),
        "reviewed_A": len(accepted),
        "retained_C_ranges": len(lines("retained-unsegmented.jsonl")),
        "negative_cases": len(negatives),
        "fault_injections": faults,
        "previous_audit_files_unchanged": len(baseline),
        "identical_texts_in_distinct_source_ranges": duplicate_texts,
        "note": "Des textes identiques dans deux sources distinctes sont signalés, jamais supprimés automatiquement.",
    }
    write("data/negative-results.json", negatives)
    write("data/checks.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sources")
    run(parser.parse_args().sources)
