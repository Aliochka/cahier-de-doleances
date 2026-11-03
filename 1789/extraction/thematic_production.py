"""Generation 5: thematic units, frozen V4 parents, unchanged numbered segmentation."""

import argparse
import copy
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "tools/document-review"))
import production as core  # noqa: E402
import thematic  # noqa: E402
from article_production import quality, to_unit  # noqa: E402
from articles import Articles, canonical  # noqa: E402
from reviewlib import Store, rows, sha  # noqa: E402

BASELINE = BASE / "data/corpus/global-corpus-4-b643646266f1"
VERSION = "global-corpus-5"


def build(activate=True, decisions_directory=None):
    started = time.perf_counter()
    decisions_directory = decisions_directory.resolve() if decisions_directory else None
    store = Store(decisions_directory / "decisions.jsonl" if decisions_directory else None)
    store.automatic_corrections = {
        r["document_id"]: r for r in rows(BASELINE / "boundary-resolutions.jsonl.gz")
    }
    engine = Articles(
        store,
        journal=decisions_directory / "article-decisions.jsonl" if decisions_directory else None,
        directory=BASELINE,
    )
    events = engine.log.history()
    protected = {e["document_id"] for e in events}
    if (engine.override_directory / "rebuilds.jsonl").exists() and rows(
        engine.override_directory / "rebuilds.jsonl"
    ):
        raise ValueError(
            "Parent overrides require explicit reconciliation; this production does not change documentary boundaries."
        )
    paths = [
        Path(__file__).resolve(),
        BASE / "extraction/thematic.py",
        BASE / "extraction/production.py",
        BASE / "extraction/article_production.py",
        BASE / "extraction/article_rules.py",
        BASE / "tools/document-review/articles.py",
        BASE / "tools/document-review/reviewlib.py",
        store.journal,
        engine.log.journal,
        *[s.path for s in store.sources.values()],
        BASE / "data/registry/registry.jsonl.gz",
    ]
    paths += [p for p in BASELINE.iterdir() if p.is_file()]
    hashes = {str(p.relative_to(BASE.parent)): sha(p.read_bytes()) for p in paths}
    out = BASE / "data/corpus" / (VERSION + "-" + sha(canonical(hashes))[:12])
    if out.exists():
        raise ValueError("Immutable generation already exists: " + str(out))
    out.mkdir(parents=True)
    (out / ".private").mkdir()
    for p in [store.journal, engine.log.journal]:
        (out / ".private" / p.name).write_bytes(p.read_bytes())
    core.dump(
        out / "inputs.json",
        dict(version=VERSION, baseline=str(BASELINE.relative_to(BASE)), files=hashes),
    )
    raw = {u["id"]: u for status in "ABC" for u in rows(BASELINE / f"units-{status}.jsonl.gz")}
    parents = []
    units = []
    regions = []
    changes = []
    before_counts = Counter()
    numbered_reference = {}
    article_reference = {}
    shared_ranges = defaultdict(list)
    for pair in rows(BASELINE / "document-overlaps.jsonl.gz"):
        for key in [pair["left_id"], pair["right_id"]]:
            shared_ranges[key].append([pair["start"], pair["end"]])
    human_reference = {}
    crosswalk = []
    for i, old_parent in enumerate(engine.parents.values(), 1):
        p = copy.deepcopy(old_parent)
        _, folded, _, _, stale = engine.state(p["id"], events)
        if stale:
            raise ValueError("Existing incompatible article decisions: " + p["id"])
        before_counts.update(r["type"] for r in folded.values())
        for r in folded.values():
            if r["type"] == "article":
                article_reference[r["id"]] = canonical(r)
            if r["type"] == "article" and r["number"] is not None:
                numbered_reference[r["id"]] = canonical(r)
            if r["review_status"] in {"human_validated", "human_corrected"}:
                human_reference[r["id"]] = canonical(r)
        hs = thematic.regions(store, p, list(folded.values()), shared_ranges[p["id"]])
        records = list(engine.base[p["id"]].values())
        records, modifications = thematic.apply(
            store, p, records, hs, protected_parent=p["id"] in protected
        )
        for h in hs:
            if p["id"] in protected:
                h["application"] = "parent_with_human_history_preserved"
            if h["confidence"] == "proposed" and h["form"] == "section_with_articles":
                p["sections"].append(
                    dict(
                        id=h["id"],
                        heading=h["title"],
                        start=h["title_start"],
                        end=h["end"],
                        xpath=h["xpath"],
                        status="thematic_source_structure_proposal_not_human_verified",
                    )
                )
        engine.check(p, records)
        records.sort(key=lambda r: (r["spans"][0][0], r["spans"][-1][1], r["id"]))
        own = [to_unit(store, p, r, raw.get(r["id"])) for r in records]
        for u in own:
            if u["id"] not in raw:
                u.update(
                    extraction_version=VERSION,
                    segmentation_version=thematic.VERSION,
                    unit_form="unnumbered_thematic_claim"
                    if u["type"] == "article"
                    else "thematic_heading"
                    if u["type"] == "section"
                    else "residual_technical_passage",
                )
        p["unit_ids"] = [r["id"] for r in own]
        for oldid in old_parent["unit_ids"]:
            crosswalk.append(
                dict(
                    parent_id=p["id"],
                    old_unit_id=oldid,
                    new_unit_ids=[
                        r["id"] for r in records if r["id"] == oldid or oldid in r["origin_ids"]
                    ],
                )
            )
        parents.append(p)
        units.extend(own)
        regions.extend(hs)
        changes.extend(modifications)
        if i % 250 == 0:
            print("Processed", i, "parents", flush=True)
    core.write_core(out, parents, units)
    # Preserve the registry and every documentary finding verbatim; no boundary rules run.
    for name in [
        "inventory.jsonl.gz",
        "boundary-resolutions.jsonl.gz",
        "documentary-review.jsonl.gz",
        "automatic-proposals.jsonl.gz",
        "document-overlaps.jsonl.gz",
        "unassigned-source.jsonl.gz",
        "article-changes.jsonl.gz",
        "article-marker-candidates.jsonl.gz",
        "parent-human-updates.jsonl.gz",
    ]:
        (out / name).write_bytes((BASELINE / name).read_bytes())
    core.jsonl(out / "thematic-regions.jsonl.gz", regions)
    core.jsonl(out / "thematic-changes.jsonl.gz", changes)
    core.jsonl(out / "unit-crosswalk.jsonl.gz", crosswalk)
    checked, current, problems, duplicates, counts, volumes = core.verify_corpus(
        out, store, article_journal=engine.log.journal
    )
    current_map = {r["id"]: r for r in current}
    # Exact event records, independent of display/context metadata.
    for key in checked.parents:
        p, rr, *_ = checked.state(key, events)
        old = engine.parents[key]
        assert all(p[f] == old[f] for f in old if f not in {"unit_ids", "sections"})
        for r in rr.values():
            if r["id"] in article_reference:
                assert canonical(r) == article_reference[r["id"]]
            if r["id"] in numbered_reference:
                assert canonical(r) == numbered_reference[r["id"]]
            if r["id"] in human_reference:
                assert canonical(r) == human_reference[r["id"]]
    assert set(article_reference).issubset(current_map)
    assert set(numbered_reference).issubset(current_map) and set(human_reference).issubset(
        current_map
    )
    core.jsonl(out / "units.jsonl.gz", current)
    core.jsonl(out / "duplicate-source-spans.jsonl.gz", duplicates)
    contexts = []
    by_parent = defaultdict(list)
    for h in regions:
        by_parent[h["parent_id"]].append(h)
    for r in current:
        context = thematic.context(r, by_parent[r["parent_id"]])
        if context:
            contexts.append(dict(unit_id=r["id"], parent_id=r["parent_id"], **context))
    core.jsonl(out / "thematic-context.jsonl.gz", contexts)
    pmap = {p["id"]: p for p in parents}
    markers = defaultdict(list)
    for c in rows(BASELINE / "article-marker-candidates.jsonl.gz"):
        markers[c["parent_id"]].append(c)
    change_index = defaultdict(list)
    for c in rows(BASELINE / "article-changes.jsonl.gz"):
        for key in c["after_ids"]:
            change_index[key].append(c["kind"])
    qrows = []
    context_map = {c["unit_id"]: c for c in contexts}
    for r in current:
        q = quality(store, pmap[r["parent_id"]], r, markers[r["parent_id"]], change_index)
        if context_map.get(r["id"], {}).get("unit_form") == "unnumbered_thematic_claim":
            q["content_class"] = "historical_unnumbered_thematic_claim_proposal"
        qrows.append(q)
    core.jsonl(out / "unit-quality.jsonl.gz", qrows)
    pq = defaultdict(Counter)
    for q in qrows:
        pq[q["parent_id"]].update([q["content_class"], q["category"]] + q["mechanisms"])
    for c in contexts:
        if c["unit_form"] in {
            "article_in_thematic_section",
            "thematic_heading",
            "section_introduction",
        }:
            pq[c["parent_id"]].update(["thematic_section_context"])
    core.dump(
        out / "article-quality-summary.json",
        dict(
            by_parent={k: dict(v) for k, v in pq.items()},
            content_classes=dict(Counter(q["content_class"] for q in qrows)),
            mechanisms=dict(Counter(m for q in qrows for m in q["mechanisms"])),
            categories=dict(Counter(q["category"] for q in qrows)),
        ),
    )
    workbench = json.loads((BASELINE / "article-workbench.json").read_text())
    new_examples = []
    for volume in range(1, 7):
        for form in ["standalone_claim", "section_with_articles"]:
            candidates = [
                h
                for h in regions
                if h["volume"] == volume
                and h["form"] == form
                and h["confidence"] == "proposed"
                and h["parent_id"] not in protected
                and any(
                    c["region_id"] == h["id"]
                    and c["unit_form"]
                    in (
                        {"unnumbered_thematic_claim"}
                        if form == "standalone_claim"
                        else {"thematic_heading", "article_in_thematic_section"}
                    )
                    for c in contexts
                )
            ]
            if not candidates:
                continue
            h = min(candidates, key=lambda h: sha(h["id"]))
            preferred = [
                c
                for c in contexts
                if c["region_id"] == h["id"]
                and c["unit_form"]
                in (
                    {"unnumbered_thematic_claim"}
                    if form == "standalone_claim"
                    else {"thematic_heading", "article_in_thematic_section"}
                )
            ]
            c = min(
                preferred,
                key=lambda c: (
                    c["unit_form"] != "thematic_heading",
                    current_map[c["unit_id"]]["start"],
                ),
            )
            r = current_map[c["unit_id"]]
            new_examples.append(
                dict(
                    id="theme-window-" + h["id"].split(":")[-1],
                    group="thematic_structure",
                    theme_form=form,
                    parent_id=h["parent_id"],
                    unit_id=r["id"],
                    volume=volume,
                    start=r["start"],
                    end=r["end"],
                    title=pmap[h["parent_id"]]["metadata"]["title"],
                )
            )
    workbench["examples"].extend(new_examples)
    workbench["thematic_generation"] = out.name
    core.dump(out / "article-workbench.json", workbench)
    summary = dict(
        version=VERSION,
        notices_examined=1305,
        texts_extracted=len(parents),
        autonomous_texts_extracted=sum(
            p["document_kind"] == "cahier_autonome_probable" for p in parents
        ),
        boundary_classes=dict(Counter(p["boundary_class"] for p in parents)),
        unresolved_notices=38,
        counts=dict(counts),
        by_volume={str(v): dict(c) for v, c in volumes.items()},
        document_overlap_pairs=len(rows(out / "document-overlaps.jsonl.gz")),
        duplicate_source_span_groups=len(duplicates),
        baseline_snapshot_articles=39243,
        before_with_current_human_decisions=dict(before_counts),
        thematic_candidates=len(regions),
        thematic_proposed=sum(h["confidence"] == "proposed" for h in regions),
        thematic_uncertain=sum(h["confidence"] == "uncertain" for h in regions),
        new_unnumbered_claims=sum(c["kind"] == "unnumbered_thematic_claim" for c in changes),
        new_heading_units=sum(c["kind"] == "thematic_heading" for c in changes),
        classification_only_changes=sum(c["classification_only"] for c in changes),
        new_source_boundaries=sum(not c["classification_only"] for c in changes),
        requalified_C_units=len(
            {
                uid
                for c in changes
                for uid in c["before_ids"]
                if uid in raw and raw[uid]["type"] == "technical_passage"
            }
        ),
        requalified_section_units=len(
            {
                uid
                for c in changes
                for uid in c["before_ids"]
                if uid in raw and raw[uid]["type"] == "section"
            }
        ),
        unnumbered_articles=sum(r["type"] == "article" and r["number"] is None for r in current),
        thematic_unnumbered_articles=sum(
            c["unit_form"] == "unnumbered_thematic_claim" for c in contexts
        ),
        thematic_sections_with_articles=sum(
            h["confidence"] == "proposed" and h["form"] == "section_with_articles" for h in regions
        ),
        thematic_article_relations=sum(
            c["unit_form"] == "article_in_thematic_section" for c in contexts
        ),
        human_article_records_preserved=sum(
            current_map[k]["type"] == "article" for k in human_reference
        ),
        human_records_preserved=len(human_reference),
        numbered_article_records_preserved=len(numbered_reference),
        existing_article_records_preserved=len(article_reference),
        human_journal_events=len(events),
        protected_human_parents=len(protected),
        thematic_examples=len(new_examples),
        elapsed_seconds=time.perf_counter() - started,
        no_boundary_changes=True,
        no_numbered_segmentation_changes=True,
        no_embeddings=True,
        no_index_preparation=True,
    )
    core.dump(out / "summary.json", summary)
    assert all(
        sha((BASE.parent / name).read_bytes()) == digest for name, digest in hashes.items()
    ), "Input changed during build"
    core.dump(
        out / "complete.json",
        dict(
            version=VERSION,
            files={p.name: sha(p.read_bytes()) for p in out.iterdir() if p.is_file()},
            human_preservation_verified=True,
            all_unit_source_coverage_verified=True,
        ),
    )
    if activate:
        temp = core.CURRENT.with_suffix(".tmp")
        core.dump(
            temp,
            dict(
                directory=str(out.relative_to(BASE)),
                version=VERSION,
                previous_directory=str(BASELINE.relative_to(BASE)),
            ),
        )
        os.replace(temp, core.CURRENT)
    print(str(out))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-activate", action="store_true")
    parser.add_argument(
        "--decisions-directory",
        type=Path,
        help="Replay an immutable private journal snapshot for reproduction",
    )
    args = parser.parse_args()
    build(not args.no_activate, args.decisions_directory)
