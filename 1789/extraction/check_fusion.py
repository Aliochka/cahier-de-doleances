"""Read-only G5/G6 comparison, exact source coverage and current human decisions."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "tools/document-review"))
from articles import Articles, canonical  # noqa: E402
from fusion_production import BASELINE  # noqa: E402
from reviewlib import Store, rows, sha  # noqa: E402


def check(directory):
    store = Store()
    store.automatic_corrections = {
        r["document_id"]: r for r in rows(BASELINE / "boundary-resolutions.jsonl.gz")
    }
    old, new = Articles(store, directory=BASELINE), Articles(store, directory=directory)
    journals = {p: sha(p.read_bytes()) for p in [store.journal, new.log.journal]}
    events = new.log.history()
    before, after = {}, {}
    assert set(old.parents) == set(new.parents)
    for key, p in new.parents.items():
        assert all(p[f] == old.parents[key][f] for f in p if f != "unit_ids")
        for engine, dest in [(old, before), (new, after)]:
            parent, rs, _, _, stale = engine.state(key, events)
            assert not stale
            engine.check(parent, list(rs.values()))
            dest.update(rs)
    changes = rows(directory / "fusion-changes.jsonl.gz")
    changed = {c["old_unit_id"] for c in changes}
    humans = [r for r in before.values() if r.get("last_event_id")]
    for r in humans:
        assert canonical(r) == canonical(after[r["id"]])
    for uid, r in before.items():
        if uid not in changed:
            assert canonical(r) == canonical(after[uid])
    for c in changes:
        original = before[c["old_unit_id"]]
        replacements = [after[uid] for uid in c["new_unit_ids"]]
        spans = sorted(s for r in replacements for s in r["spans"])
        assert sum(z - a for a, z in spans) == sum(z - a for a, z in original["spans"])
        assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))
        src = store.sources[old.parents[original["parent_id"]]["volume"]]
        assert "".join(src.text[a:z] for a, z in spans) == old.text(
            old.parents[original["parent_id"]], original
        )
        assert not original.get("last_event_id")
        prefix = min(replacements, key=lambda r: r["spans"][0][0])
        assert prefix["number"] == original["number"] and prefix["type"] == original["type"]
        for uid in c["new_claim_ids"]:
            claim = after[uid]
            assert claim["type"] == "article" and claim["number"] is None
            assert claim["review_status"] == "automatic_proposal" and not claim.get("last_event_id")
    crosswalk = {r["old_unit_id"]: r for r in rows(directory / "unit-crosswalk.jsonl.gz")}
    for c in changes:
        assert set(crosswalk[c["old_unit_id"]]["new_unit_ids"]) == set(c["new_unit_ids"])
    candidates = {h["id"]: h for h in rows(directory / "fusion-candidates.jsonl.gz")}
    plan = json.loads((BASE / "extraction/fusion-validation-v2.json").read_text())
    for filename, digest in plan["rule_files_sha256"].items():
        assert sha((BASE / "extraction" / filename).read_bytes()) == digest
    for h in plan["validation"]:
        assert h["parent_id"] not in plan["excluded_parent_ids"]
        assert candidates[h["id"]]["application"] == "applied_automatic_proposal"
    for h in plan["refusals"]:
        assert candidates[h["id"]]["application"] == "not_applied"
    rejected_plan = json.loads((BASE / "extraction/fusion-validation-plan.json").read_text())
    known_false = [
        h
        for h in rejected_plan["validation"]
        if any(
            h["parent_id"].endswith(s) for s in ["_2_1_1643", "_4_1_2118", "_6_1_2760", "_6_1_2545"]
        )
    ]
    assert len(known_false) == 4
    for h in known_false:
        assert not any(
            current["parent_id"] == h["parent_id"]
            and current["title_start"] == h["title_start"]
            and current["application"] == "applied_automatic_proposal"
            for current in candidates.values()
        )
    amiens = next(key for key in new.parents if key.endswith("_1_1_1547"))
    dotation = next(
        r for r in after.values() if r["parent_id"] == amiens and r["spans"][0][0] == 5643975
    )
    assert dotation["type"] == "article" and dotation["number"] is None
    assert dotation["spans"] == [[5643975, 5644604]]
    numbered = next(
        r for r in after.values() if r["parent_id"] == amiens and r["spans"][0][0] == 5640887
    )
    assert numbered["number"] == "2" and numbered["spans"] == [[5640887, 5643975]]
    untouched_files = [
        "inventory.jsonl.gz",
        "boundary-resolutions.jsonl.gz",
        "document-overlaps.jsonl.gz",
        "documentary-review.jsonl.gz",
        "unassigned-source.jsonl.gz",
    ]
    for name in untouched_files:
        assert (directory / name).read_bytes() == (BASELINE / name).read_bytes()
    old_workbench = json.loads((BASELINE / "article-workbench.json").read_text())
    workbench = json.loads((directory / "article-workbench.json").read_text())
    assert workbench["independent_sample"] == old_workbench["independent_sample"]
    assert workbench["examples"] == old_workbench["examples"]
    assert len(workbench["fusion_validation"]) == 16
    assert all(sha(p.read_bytes()) == digest for p, digest in journals.items())
    result = dict(
        passed=True,
        generation=directory.name,
        unchanged_parents=len(new.parents),
        unchanged_records=len(before) - len(changed),
        protected_current_records=len(humans),
        human_articles_preserved=sum(
            r["type"] == "article" and r["review_status"] in {"human_validated", "human_corrected"}
            for r in before.values()
        ),
        changed_source_units=len(changes),
        new_unnumbered_claims=sum(len(c["new_claim_ids"]) for c in changes),
        partition_and_exact_source_text=True,
        previous_workbench_preserved=True,
        amiens_number_2_and_dotation_separated=True,
        frozen_positive_controls_applied=len(plan["validation"]),
        frozen_refusals_not_applied=len(plan["refusals"]),
        rejected_v1_false_cuts_not_applied=len(known_false),
        before_types=dict(Counter(r["type"] for r in before.values())),
        after_types=dict(Counter(r["type"] for r in after.values())),
        human_journal_files_unchanged=True,
        parent_boundaries_unchanged=True,
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check(args.directory)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered)
