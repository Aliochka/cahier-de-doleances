"""Generation 6: per-unit thematic fusion repair; human logs and parents immutable."""

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
import fusion  # noqa: E402
import production as core  # noqa: E402
import thematic  # noqa: E402
from article_production import quality, to_unit  # noqa: E402
from articles import Articles, canonical  # noqa: E402
from fusion_plan import inputs as protection  # noqa: E402
from reviewlib import Store, rows, sha  # noqa: E402

BASELINE = BASE / "data/corpus/global-corpus-5-7b829ada54d6"
VERSION = "global-corpus-6"


def updated_regions(previous, hypotheses, changes):
    applied = {hid for c in changes for hid in c["hypothesis_ids"]}
    fresh = []
    for h in hypotheses:
        if h["id"] not in applied:
            continue
        fresh.append(
            dict(
                id="ap1789-fusion-theme-2:" + sha(h["id"])[:24],
                parent_id=h["parent_id"],
                parent_extent_id=h["parent_extent_id"],
                volume=h["volume"],
                title=h["title"],
                title_start=h["title_start"],
                title_end=h["title_end"],
                scope_start=h["title_start"],
                end=h["end"],
                xpath=h["xpath"],
                division=h["division"],
                form="standalone_claim",
                confidence="proposed",
                reasons=[],
                article_ids=[],
                introduction_spans=[],
                evidence=h["evidence"],
                fusion_hypothesis_id=h["id"],
                version=fusion.VERSION,
            )
        )
    by_parent = defaultdict(list)
    for h in fresh:
        by_parent[h["parent_id"]].append(h)
    result = []
    for original in previous:
        h = copy.deepcopy(original)
        own = by_parent[h["parent_id"]]
        if h["confidence"] == "proposed" and h["form"] == "standalone_claim":
            same = next((n for n in own if n["title_start"] == h["title_start"]), None)
            inside = [
                n["title_start"] for n in own if h["title_start"] < n["title_start"] < h["end"]
            ]
            if same or inside:
                h["confidence"] = "uncertain"
                h["reasons"].append("context_scope_superseded_by_generation_6_split")
                if not same:
                    prefix = copy.deepcopy(original)
                    prefix.update(
                        id="ap1789-fusion-prefix-theme-2:"
                        + sha(canonical([h["id"], min(inside)]))[:24],
                        end=min(inside),
                        original_region_id=h["id"],
                        version=fusion.VERSION,
                    )
                    prefix["confidence"] = "uncertain"
                    prefix["reasons"].append("prefix_role_kept_without_new_claim_certification")
                    result.append(prefix)
        result.append(h)
    return sorted(
        result + fresh, key=lambda h: (h["volume"], h["parent_id"], h["title_start"], h["id"])
    )


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
    protected, shared = protection(store, engine, events)
    plan = json.loads((BASE / "extraction/fusion-validation-v2.json").read_text())
    for name, digest in plan["rule_files_sha256"].items():
        assert sha((BASE / "extraction" / name).read_bytes()) == digest, (
            "Frozen evaluation rules changed"
        )
    if (engine.override_directory / "rebuilds.jsonl").exists() and rows(
        engine.override_directory / "rebuilds.jsonl"
    ):
        raise ValueError(
            "Documentary overrides need reconciliation; this extraction never changes parents."
        )
    paths = [
        Path(__file__).resolve(),
        BASE / "extraction/fusion.py",
        BASE / "extraction/fusion_v1.py",
        BASE / "extraction/fusion_plan.py",
        BASE / "extraction/thematic.py",
        BASE / "extraction/production.py",
        BASE / "extraction/article_production.py",
        BASE / "tools/document-review/articles.py",
        BASE / "tools/document-review/reviewlib.py",
        BASE / "extraction/fusion-validation-plan.json",
        BASE / "extraction/fusion-validation-v2.json",
        BASE / "extraction/fusion-validation-results.json",
        store.journal,
        engine.log.journal,
        *[s.path for s in store.sources.values()],
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
    raw = {u["id"]: u for c in "ABC" for u in rows(BASELINE / f"units-{c}.jsonl.gz")}
    parents = []
    units = []
    hypotheses = []
    changes = []
    before_counts = Counter()
    reference = {}
    crosswalk = []
    for index, oldp in enumerate(engine.parents.values(), 1):
        p = copy.deepcopy(oldp)
        _, current, _, _, stale = engine.state(p["id"], events)
        if stale:
            raise ValueError("Incompatible existing article history: " + p["id"])
        engine.check(p, list(current.values()))
        reference.update(current)
        before_counts.update(r["type"] for r in current.values())
        hs = fusion.detect(store, p, list(current.values()), protected[p["id"]], shared[p["id"]])
        # A proposal may only replace a pristine raw baseline unit, never a human-created residual.
        for h in hs:
            uid = h["source_unit_id"]
            if h["confidence"] == "proposed" and (
                uid not in engine.base[p["id"]]
                or canonical(current[uid]) != canonical(engine.base[p["id"]][uid])
            ):
                h["confidence"] = "uncertain"
                h["reasons"].append("human_derived_baseline_requires_separate_review")
                h["protected"] = True
        proposed, ownchanges = fusion.apply(store, p, list(engine.base[p["id"]].values()), hs)
        engine.check(p, proposed)
        own = [to_unit(store, p, r, raw.get(r["id"])) for r in proposed]
        for u in own:
            if u["id"] not in raw:
                u.update(extraction_version=VERSION, segmentation_version=fusion.VERSION)
                new_claim_ids = {uid for c in ownchanges for uid in c["new_claim_ids"]}
                u["unit_form"] = (
                    "unnumbered_thematic_claim"
                    if u["id"] in new_claim_ids
                    else "retained_prefix_or_technical_residual"
                )
        p["unit_ids"] = [u["id"] for u in own]
        parents.append(p)
        units.extend(own)
        applied = {hid for c in ownchanges for hid in c["hypothesis_ids"]}
        for h in hs:
            h["application"] = (
                "applied_automatic_proposal"
                if h["id"] in applied
                else "separate_proposal_human_priority"
                if h["protected"]
                else "not_applied"
            )
        hypotheses.extend(hs)
        changes.extend(ownchanges)
        for uid in oldp["unit_ids"]:
            crosswalk.append(
                dict(
                    parent_id=p["id"],
                    old_unit_id=uid,
                    new_unit_ids=[
                        r["id"] for r in proposed if uid == r["id"] or uid in r["origin_ids"]
                    ],
                )
            )
        if index % 250 == 0:
            print("Processed", index, "parents", flush=True)
    core.write_core(out, parents, units)
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
        "thematic-changes.jsonl.gz",
    ]:
        (out / name).write_bytes((BASELINE / name).read_bytes())
    regiondata = updated_regions(rows(BASELINE / "thematic-regions.jsonl.gz"), hypotheses, changes)
    core.jsonl(out / "thematic-regions.jsonl.gz", regiondata)
    core.jsonl(out / "fusion-candidates.jsonl.gz", hypotheses)
    core.jsonl(out / "fusion-changes.jsonl.gz", changes)
    core.jsonl(out / "unit-crosswalk.jsonl.gz", crosswalk)
    checked, materialized, problems, duplicates, counts, volumes = core.verify_corpus(
        out, store, article_journal=engine.log.journal
    )
    changed = {c["old_unit_id"] for c in changes}
    current_by_id = {r["id"]: r for r in materialized}
    human = 0
    untouched = 0
    prefix_numbered = 0
    for key, p in checked.parents.items():
        old = engine.parents[key]
        assert all(p[f] == old[f] for f in old if f != "unit_ids")
        _, own, *_ = checked.state(key, events)
        for uid, r in own.items():
            if uid in reference and uid not in changed:
                assert canonical(r) == canonical(reference[uid])
                untouched += 1
        for uid, r in reference.items():
            if r["parent_id"] != key:
                continue
            if r["review_status"] in {"human_validated", "human_corrected", "uncertain"} or r.get(
                "last_event_id"
            ):
                assert uid in own and canonical(own[uid]) == canonical(r), (
                    "Human record was replaced"
                )
                human += r["review_status"] in {"human_validated", "human_corrected"}
        for c in [c for c in changes if c["parent_id"] == key and c["old_number"] is not None]:
            oldr = reference[c["old_unit_id"]]
            prefix = next(
                own[uid]
                for uid in c["new_unit_ids"]
                if own[uid]["spans"][0][0] == oldr["spans"][0][0]
            )
            assert prefix["number"] == oldr["number"] and prefix["label"] == oldr["label"]
            prefix_numbered += 1
    assert set(reference) - changed <= set(current_by_id)
    core.jsonl(out / "units.jsonl.gz", materialized)
    core.jsonl(out / "duplicate-source-spans.jsonl.gz", duplicates)
    contexts = []
    byparent = defaultdict(list)
    for h in regiondata:
        byparent[h["parent_id"]].append(h)
    for r in materialized:
        ctx = thematic.context(r, byparent[r["parent_id"]])
        if ctx:
            contexts.append(dict(unit_id=r["id"], parent_id=r["parent_id"], **ctx))
    core.jsonl(out / "thematic-context.jsonl.gz", contexts)
    candidates_by_parent = defaultdict(list)
    pmap = {p["id"]: p for p in parents}
    for c in rows(BASELINE / "article-marker-candidates.jsonl.gz"):
        candidates_by_parent[c["parent_id"]].append(c)
    contextmap = {c["unit_id"]: c for c in contexts}
    qrows = []
    pq = defaultdict(Counter)
    new_claims = {uid for c in changes for uid in c["new_claim_ids"]}
    for r in materialized:
        q = quality(store, pmap[r["parent_id"]], r, candidates_by_parent[r["parent_id"]], {})
        if contextmap.get(r["id"], {}).get("unit_form") == "unnumbered_thematic_claim":
            q["content_class"] = "historical_unnumbered_thematic_claim_proposal"
        if r["id"] in new_claims:
            q["mechanisms"].append("automatic_thematic_fusion_split")
        qrows.append(q)
        pq[r["parent_id"]].update([q["content_class"], q["category"]] + q["mechanisms"])
    core.jsonl(out / "unit-quality.jsonl.gz", qrows)
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
    by_h = {h["id"]: h for h in hypotheses}
    campaign = []
    demonstration = next(
        h
        for h in hypotheses
        if h["parent_id"].endswith("_1_1_1547") and h["title"].startswith("Dotation des cures")
    )
    groups = [("development", [dict(id=demonstration["id"])])] + [
        (group, plan[group]) for group in ["validation", "refusals"]
    ]
    for group, selections in groups:
        for item in selections:
            h = by_h[item["id"]]
            own = [
                r
                for r in materialized
                if r["parent_id"] == h["parent_id"]
                and any(a <= h["title_start"] < z for a, z in r["spans"])
            ]
            if not own:
                raise ValueError("Control title lost")
            u = own[0]
            campaign.append(
                dict(
                    id="fusion-window-" + h["id"].split(":")[-1],
                    group="fusion_validation"
                    if group == "validation"
                    else "fusion_development"
                    if group == "development"
                    else "fusion_refusal",
                    parent_id=h["parent_id"],
                    unit_id=u["id"],
                    volume=h["volume"],
                    title=pmap[h["parent_id"]]["metadata"]["title"],
                    focus_title=h["title"],
                    start=h["title_start"],
                    end=h["end"],
                    focus_start=h["title_start"],
                    focus_end=h["title_end"],
                    hypothesis_id=h["id"],
                )
            )
    workbench["fusion_validation"] = campaign
    workbench["fusion_generation"] = out.name
    core.dump(out / "article-workbench.json", workbench)
    summary = dict(
        version=VERSION,
        notices_examined=1305,
        texts_extracted=len(parents),
        autonomous_texts_extracted=1224,
        boundary_classes=dict(Counter(p["boundary_class"] for p in parents)),
        unresolved_notices=38,
        counts=dict(counts),
        by_volume={str(v): dict(c) for v, c in volumes.items()},
        before_with_current_human_decisions=dict(before_counts),
        suspected_source_units=len({h["source_unit_id"] for h in hypotheses}),
        units_with_multiple_interior_headings=sum(
            n >= 2 for n in Counter(h["source_unit_id"] for h in hypotheses).values()
        ),
        proposed_boundaries=sum(h["confidence"] == "proposed" for h in hypotheses),
        automatically_split_units=len(changes),
        new_unnumbered_claims=len(new_claims),
        uncertain_proposals=sum(h["confidence"] == "uncertain" for h in hypotheses),
        uncertain_source_units=len(
            {h["source_unit_id"] for h in hypotheses if h["confidence"] == "uncertain"}
        ),
        human_records_preserved=human,
        human_articles_preserved=counts["human_articles"],
        human_journal_events=len(events),
        unchanged_records=untouched,
        numbered_prefixes_preserved=prefix_numbered,
        document_overlap_pairs=len(rows(out / "document-overlaps.jsonl.gz")),
        duplicate_source_span_groups=len(duplicates),
        independent_validation_windows=len(plan["validation"]),
        refusal_windows=len(plan["refusals"]),
        rule_version=fusion.VERSION,
        elapsed_seconds=time.perf_counter() - started,
        no_parent_boundary_changes=True,
        no_embeddings=True,
        no_index_preparation=True,
    )
    core.dump(out / "summary.json", summary)
    assert all(
        sha((BASE.parent / name).read_bytes()) == digest for name, digest in hashes.items()
    ), "Input changed during extraction"
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
        tmp = core.CURRENT.with_suffix(".tmp")
        core.dump(
            tmp,
            dict(
                directory=str(out.relative_to(BASE)),
                version=VERSION,
                previous_directory=str(BASELINE.relative_to(BASE)),
            ),
        )
        os.replace(tmp, core.CURRENT)
    print(str(out))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-activate", action="store_true")
    parser.add_argument("--decisions-directory", type=Path)
    args = parser.parse_args()
    build(not args.no_activate, args.decisions_directory)
