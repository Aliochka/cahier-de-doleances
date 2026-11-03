"""Read-only V4/V5 structural comparison, including all live human decisions."""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "tools/document-review"))
import thematic  # noqa: E402
from articles import Articles, canonical  # noqa: E402
from reviewlib import Store, rows, sha  # noqa: E402


def check(out):
    baseline = BASE / "data/corpus/global-corpus-4-b643646266f1"
    store = Store()
    store.automatic_corrections = {
        r["document_id"]: r for r in rows(baseline / "boundary-resolutions.jsonl.gz")
    }
    old = Articles(store, directory=baseline)
    new = Articles(store, directory=out)
    journal_hashes = {p: sha(p.read_bytes()) for p in [store.journal, new.log.journal]}
    events = new.log.history()
    before = {}
    after = {}
    oldcounts = Counter()
    newcounts = Counter()
    assert set(old.parents) == set(new.parents)
    for key, p in new.parents.items():
        assert all(
            p[f] == old.parents[key][f]
            for f in old.parents[key]
            if f not in {"sections", "unit_ids"}
        )
        for engine, dest, counts in [(old, before, oldcounts), (new, after, newcounts)]:
            parent, rs, *_ = engine.state(key, events)
            engine.check(parent, list(rs.values()))
            dest.update(rs)
            counts.update(r["type"] for r in rs.values())
    protected_parents = {e["document_id"] for e in events}
    protected_records = 0
    for key in protected_parents:
        old_records = old.state(key, events)[1]
        new_records = new.state(key, events)[1]
        assert canonical(old_records) == canonical(new_records)
        protected_records += len(old_records)
    raw_units = {u["id"]: u for status in "ABC" for u in rows(out / f"units-{status}.jsonl.gz")}
    for parent in new.parents.values():
        starts = [raw_units[uid]["start"] for uid in parent["unit_ids"]]
        assert starts == sorted(starts)
    previous_articles = [r for r in before.values() if r["type"] == "article"]
    for r in previous_articles:
        assert canonical(r) == canonical(after[r["id"]])
    previous_humans = [
        r for r in before.values() if r["review_status"] in {"human_validated", "human_corrected"}
    ]
    for r in previous_humans:
        assert canonical(r) == canonical(after[r["id"]])
    regions = rows(out / "thematic-regions.jsonl.gz")
    by_parent = defaultdict(list)
    for h in regions:
        p = new.parents[h["parent_id"]]
        src = store.sources[p["volume"]]
        assert src.text[h["title_start"] : h["title_end"]] == h["title"]
        assert p["start"] <= h["title_start"] < h["title_end"] <= h["end"] <= p["end"]
        by_parent[p["id"]].append(h)
    numbered = [r for r in previous_articles if r["number"] is not None]
    changes = rows(out / "thematic-changes.jsonl.gz")
    forms = Counter()
    before_forms = Counter()
    for target, counter in [(before, before_forms), (after, forms)]:
        for r in target.values():
            c = thematic.context(r, by_parent[r["parent_id"]])
            if c:
                counter[c["unit_form"]] += 1
    examples = []
    for v in range(1, 7):
        for form in ["standalone_claim", "section_with_articles"]:
            cs = sorted(
                [
                    h
                    for h in regions
                    if h["volume"] == v and h["form"] == form and h["confidence"] == "proposed"
                ],
                key=lambda h: h["id"],
            )
            if cs:
                h = cs[0]
                examples.append(
                    {
                        k: h[k]
                        for k in [
                            "parent_id",
                            "volume",
                            "title",
                            "title_start",
                            "title_end",
                            "end",
                            "xpath",
                            "form",
                        ]
                    }
                )
    assert len(examples) == 12
    # Actual human reference: keep classification, numbers, source spans and current IDs.
    beauvais_key = next(key for key in new.parents if key.endswith("_2_1_1639"))
    jurandes = next(
        r
        for r in after.values()
        if r["parent_id"] == beauvais_key
        and r["type"] == "article"
        and r["number"] is None
        and "Jurandes et maîtrises." in new.text(new.parents[beauvais_key], r)
    )
    assert jurandes["review_status"] in {"human_validated", "human_corrected"}
    assert new.thematic_context(jurandes)["unit_form"] == "unnumbered_thematic_claim"
    assert (
        "Numéro non reconnu ; vérifier le repère original."
        not in new.anomalies(new.parents[beauvais_key], [jurandes])[jurandes["id"]]
    )
    for name in ["document-overlaps.jsonl.gz", "unassigned-source.jsonl.gz", "inventory.jsonl.gz"]:
        assert (out / name).read_bytes() == (baseline / name).read_bytes()
    workbench = json.loads((out / "article-workbench.json").read_text())
    assert (
        workbench["independent_sample"]
        == json.loads((baseline / "article-workbench.json").read_text())["independent_sample"]
    )
    assert all(sha(p.read_bytes()) == digest for p, digest in journal_hashes.items())
    complete = json.loads((out / "complete.json").read_text())
    assert all(
        sha((out / name).read_bytes()) == digest for name, digest in complete["files"].items()
    )
    inputs = json.loads((out / "inputs.json").read_text())
    assert all(
        sha((BASE.parent / name).read_bytes()) == digest for name, digest in inputs["files"].items()
    )
    return dict(
        generation=out.name,
        before_with_current_decisions=dict(oldcounts),
        after=dict(newcounts),
        before_thematic_forms=dict(before_forms),
        after_thematic_forms=dict(forms),
        change_kinds=dict(Counter(c["kind"] for c in changes)),
        classification_only=dict(Counter(c["kind"] for c in changes if c["classification_only"])),
        proposed_regions=dict(Counter(h["form"] for h in regions if h["confidence"] == "proposed")),
        uncertain_regions=dict(
            Counter(h["form"] for h in regions if h["confidence"] == "uncertain")
        ),
        uncertainty_reasons=dict(Counter(reason for h in regions for reason in h["reasons"])),
        parent_count=len(new.parents),
        existing_articles_identical=len(previous_articles),
        numbered_articles_identical=len(numbered),
        human_records_identical=len(previous_humans),
        all_records_in_human_reviewed_parents_identical=protected_records,
        human_articles_identical=sum(r["type"] == "article" for r in previous_humans),
        human_journal_events=len(events),
        beauvais_human_reference_preserved=True,
        jurandes_title_and_development_kept_together=True,
        old_sample_preserved=True,
        source_and_journals_unchanged=True,
        source_checks=examples,
        source_checks_interpretation="12 limited documentary control windows across six volumes, examined by Codex; not independent human validation or accuracy measurement",
        parent_unit_indices_source_ordered=True,
        no_boundary_changes=True,
        no_embeddings=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("generation", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = check(args.generation)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text)
