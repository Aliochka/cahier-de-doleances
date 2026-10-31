"""Compare immutable corpus generations; no extraction, source or decision writes."""

import argparse
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def rows(directory, name):
    with gzip.open(directory / name, "rt") as f:
        return [json.loads(line) for line in f]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(before, after):
    bs = json.loads((before / "summary.json").read_text())
    ns = json.loads((after / "summary.json").read_text())
    bi = {r["id"]: r for r in rows(before, "inventory.jsonl.gz")}
    ni = {r["id"]: r for r in rows(after, "inventory.jsonl.gz")}
    bp = {r["id"]: r for r in rows(before, "parents.jsonl.gz")}
    np = {r["id"]: r for r in rows(after, "parents.jsonl.gz")}
    assert set(bi) == set(ni) and len(ni) == 1305
    assert set(bp) <= set(np), "A previously extracted document disappeared"
    assert all(
        bi[k]["metadata"] == ni[k]["metadata"] and bi[k]["source"] == ni[k]["source"] for k in bi
    )
    human_parents = [k for k, p in bp.items() if p["boundary_class"] == "human_validated"]
    assert len(human_parents) == 29
    assert all(
        (bp[k]["start"], bp[k]["end"], bp[k]["full_text"])
        == (np[k]["start"], np[k]["end"], np[k]["full_text"])
        and np[k]["boundary_class"] == "human_validated"
        for k in human_parents
    )
    bu = {u["id"]: u for u in rows(before, "units.jsonl.gz") if u["human_validated"]}
    nu = {u["id"]: u for u in rows(after, "units.jsonl.gz") if u["human_validated"]}
    assert len(bu) == len(nu) == 333 and set(bu) == set(nu)
    fields = [
        "id",
        "parent_id",
        "text",
        "spans",
        "historical_number",
        "review_status",
        "last_event_id",
    ]
    assert all(all(bu[k].get(f) == nu[k].get(f) for f in fields) for k in bu)
    for name in ["decisions.jsonl", "article-decisions.jsonl"]:
        assert (
            (before / ".private" / name).read_bytes()
            == (after / ".private" / name).read_bytes()
            == (BASE / "data/private/document-review" / name).read_bytes()
        )
    protected = []
    inputs = json.loads((before / "inputs.json").read_text())["files"]
    for name, expected in inputs.items():
        if "/sources/" in name or "/data/" in name:
            assert digest(BASE.parent / name) == expected, name
            protected.append(name)
    old_pairs = rows(before, "document-overlaps.jsonl.gz")
    new_pairs = rows(after, "document-overlaps.jsonl.gz")

    def pair_key(r):
        return tuple(sorted([r["left_id"], r["right_id"]]))

    assert {pair_key(r) for r in new_pairs} <= {pair_key(r) for r in old_pairs}, (
        "New documentary overlap introduced"
    )
    resolutions = rows(after, "boundary-resolutions.jsonl.gz")
    changes = {r["document_id"]: r for r in resolutions if r["changed"]}
    for k, r in changes.items():
        assert (np[k]["start"], np[k]["end"]) == (r["selected"]["start"], r["selected"]["end"])
    diagnoses = []
    new_keys = {pair_key(r) for r in new_pairs}
    for pair in old_pairs:
        keys = pair_key(pair)
        actions = {a for k in keys for a in changes.get(k, {}).get("actions", [])}
        if keys not in new_keys:
            family = (
                "wrong_shared_page_alignment"
                if "unique_explicit_opening_name_estate_and_page" in actions
                else "XML_division_contains_successive_cahiers"
            )
            status = "resolved_by_source_evidenced_boundary_change"
        elif any(ni[k]["document_kind"] != "cahier_autonome_probable" for k in keys):
            family = "associated_document_or_catalogue_level_overlap"
            status = "not_assumed_error_requires_documentary_attribution"
        elif pair["kind"] == "identical_extent":
            family = "same_text_wrong_identity_or_shared_document_unresolved"
            status = "unresolved_no_silent_merge"
        else:
            family = "remaining_containment_or_interleaving"
            status = "unresolved_no_arbitrary_cut"
        diagnoses.append(
            dict(
                pair=pair,
                documents=[
                    dict(id=k, title=ni[k]["title"], kind=ni[k]["document_kind"]) for k in keys
                ],
                family=family,
                status=status,
            )
        )
    old_duplicates = rows(before, "duplicate-source-spans.jsonl.gz")
    new_duplicates = rows(after, "duplicate-source-spans.jsonl.gz")

    # Reconcile source-span groups independently of regenerated unit identifiers.
    def span_key(r):
        return (r["source_sha256"], json.dumps(r["spans"], sort_keys=True))

    newer = {span_key(r) for r in new_duplicates}
    duplicate_dispositions = [
        dict(
            source_sha256=r["source_sha256"],
            spans=r["spans"],
            previous_unit_ids=r["unit_ids"],
            status="still_duplicated_requires_attribution"
            if span_key(r) in newer
            else "no_longer_duplicated_after_parent_repairs",
        )
        for r in old_duplicates
    ]
    queue = rows(after, "documentary-review.jsonl.gz")
    counters = Counter(d["family"] for d in diagnoses)
    cause_documents = {
        family: len({x["id"] for d in diagnoses if d["family"] == family for x in d["documents"]})
        for family in counters
    }
    missing = [
        r
        for r in bi.values()
        if not r["parent_id"] and r["extraction_state"] != "absence_notice_not_a_cahier"
    ]
    missing_counts = Counter(
        "recovered_with_explicit_opening"
        if ni[r["id"]]["parent_id"]
        else "associated_or_list_still_unlocated"
        if r["document_kind"] in {"liste", "document_associe", "proces_verbal"}
        else "cahier_still_unlocated"
        for r in missing
    )
    metrics = dict(
        before_generation=before.name,
        after_generation=after.name,
        before=bs,
        after=ns,
        corrected_documents=len(changes),
        recovered_documents=sorted(set(np) - set(bp)),
        overlap_causes=dict(counters),
        overlap_cause_documents=cause_documents,
        missing_notice_dispositions=dict(missing_counts),
        duplicate_dispositions=dict(Counter(r["status"] for r in duplicate_dispositions)),
        remaining_new_span_groups=sum(
            span_key(r) not in {span_key(x) for x in old_duplicates} for r in new_duplicates
        ),
        mandatory_review=sum(r["mandatory_review"] for r in queue),
        review_levels=dict(Counter(r["priority"] for r in queue)),
        checks=dict(
            notices_preserved=True,
            metadata_preserved=True,
            previously_extracted_documents_preserved=True,
            human_parent_boundaries_preserved=29,
            human_articles_preserved=333,
            real_journals_byte_identical=True,
            protected_data_source_files_unchanged=len(protected),
            no_new_overlap_pair=True,
            all_documentary_changes_applied=True,
        ),
    )
    return metrics, diagnoses, duplicate_dispositions


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--before", type=Path, required=True)
    p.add_argument("--after", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    metrics, overlaps, duplicates = compare(a.before, a.after)
    a.output.mkdir(parents=True, exist_ok=True)
    for name, data in [
        ("summary.json", metrics),
        ("overlap-dispositions.json", overlaps),
        ("duplicate-dispositions.json", duplicates),
    ]:
        (a.output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {k: v for k, v in metrics.items() if k not in {"before", "after"}},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
