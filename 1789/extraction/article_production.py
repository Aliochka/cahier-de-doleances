"""Regenerate articles from frozen V3 parents and explicit human decisions only.

Does not call any documentary discovery/alignment/boundary rule. No database/model access.
"""

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
import article_rules as rules  # noqa: E402
import production as old  # noqa: E402
from articles import Articles, canonical, subtract  # noqa: E402
from boundary_rules import effective  # noqa: E402
from reviewlib import Store, rows, sha  # noqa: E402

VERSION = "global-corpus-4"
BASELINE = BASE / "data/corpus/global-corpus-3-d0df8e19ee01"


def write_json(path, data):
    old.dump(path, data)


def to_unit(store, p, r, old_unit=None):
    source = store.sources[p["volume"]]
    spans = r["spans"]
    a, z = spans[0][0], spans[-1][1]
    if old_unit and spans == old_unit["text_spans"] and r["type"] == old_unit["type"]:
        return old_unit
    return dict(
        id=r["id"],
        parent_id=p["id"],
        parent_extent_id=p["extent_id"],
        corpus_id=p["corpus_id"],
        type=r["type"],
        status=r["source_status"],
        historical_number=r["number"],
        label_exact=r["label"],
        text="".join(source.text[x:y] for x, y in spans),
        start=a,
        end=z,
        text_spans=spans,
        parent_start=a - p["start"],
        parent_end=z - p["start"],
        parent_text_spans=[[x - p["start"], y - p["start"]] for x, y in spans],
        section_id=r["section_id"],
        origin_ids=r["origin_ids"],
        legacy_unit_ids=r["origin_ids"],
        source=p["source"],
        pages=source.pages_for(a, z),
        extraction_version=VERSION,
        segmentation_version=rules.VERSION,
        verification="automatic_not_human_verified",
        human_validated=False,
        xml_blocks=[
            dict(id=b["id"], xpath=b["xpath"], start=max(a, b["start"]), end=min(z, b["end"]))
            for b in store.selected_blocks(p["volume"], a, z)
            if b["tag"] != "pb"
        ],
    )


def quality(store, parent, record, candidates, change_index):
    flags = record.get("anomalies", [])
    uid = record["id"]
    kind = record["type"]
    info = dict(
        unit_id=uid,
        parent_id=parent["id"],
        volume=parent["volume"],
        type=kind,
        start=record["spans"][0][0],
        end=record["spans"][-1][1],
        last_event_id=record.get("last_event_id"),
        mechanisms=[],
        changes=change_index.get(uid, []),
    )
    human = record["human_validated"]
    info["human_validated"] = human
    if kind == "technical_passage":
        cls, why = rules.content_class(store, parent, record)
        info.update(content_class=cls, reason=why)
    elif kind in {"claim_passage", "paratext"}:
        info.update(
            content_class="claim_prose_proposal" if kind == "claim_passage" else "paratext",
            reason="existing_explicit_human_qualification",
        )
    elif kind == "section":
        info.update(
            content_class="historical_section_proposal",
            reason="explicit_heading_scope_kept_distinct_from_article",
        )
        if rules.REQUEST.search(record["text"]):
            info["mechanisms"].append("section_contains_request_prose")
    elif kind == "article":
        markers = [m for m in candidates if any(a < m["start"] < z for a, z in record["spans"])]
        if markers and not human:
            info["mechanisms"].append("possible_fusion_remaining")
        if any("répété" in f for f in flags):
            info["mechanisms"].append("repeated_number_not_proof_of_error")
        if any("irrégulière" in f for f in flags):
            before = [
                b
                for b in parent["blocks"]
                if b["end"] <= info["start"] and b["role"] in {"heading", "section_heading"}
            ]
            info["mechanisms"].append("sequence_irregularity_not_proof_of_error")
            if (
                before
                and info["start"] - before[-1]["end"] < 300
                and rules.number(record.get("number")) == 1
            ):
                info["mechanisms"].append("section_restart_supported_by_heading")
        if any("non reconnu" in f for f in flags):
            info["mechanisms"].append("OCR_label_uncertain")
        if len(record["text"]) > 12000:
            info["mechanisms"].append("long_article_not_necessarily_fused")
        info["content_class"] = "historical_numbered_article_proposal"
    if info["changes"]:
        info["mechanisms"].append("automatic_source_marker_correction")
    info["category"] = (
        "human_reference"
        if human
        else "probable_segmentation_error"
        if "possible_fusion_remaining" in info["mechanisms"]
        or info.get("content_class") == "possible_missed_article"
        else "documentary_irregularity"
        if info["mechanisms"]
        else "unresolved"
        if info.get("content_class") == "uncertain"
        else "regular_proposal"
    )
    return info


def build(no_activate=False, history_baseline=None):
    started = time.perf_counter()
    store = Store()
    frozen = rows(BASELINE / "boundary-resolutions.jsonl.gz")
    store.automatic_corrections = {r["document_id"]: r for r in frozen}
    engine = Articles(store, directory=BASELINE)
    events = engine.log.history()
    reviewed_parents = {e["document_id"] for e in events}
    latest = store.latest()
    history_baseline = (history_baseline or old.current_directory() or BASELINE).resolve()
    history_engine = Articles(store, directory=history_baseline)
    paths = [
        Path(__file__),
        BASE / "extraction/article_rules.py",
        BASE / "extraction/article-rule-checks.json",
        BASE / "extraction/segmentation.py",
        BASE / "extraction/production.py",
        BASE / "tools/document-review/articles.py",
        BASE / "tools/document-review/reviewlib.py",
        BASE / "data/registry/registry.jsonl.gz",
        BASE / "data/article-corpus/parents.jsonl.gz",
        store.journal,
        engine.log.journal,
        *[
            BASELINE / n
            for n in [
                "parents.jsonl.gz",
                "units-A.jsonl.gz",
                "units-B.jsonl.gz",
                "units-C.jsonl.gz",
                "inventory.jsonl.gz",
                "boundary-resolutions.jsonl.gz",
                "complete.json",
                "documentary-review.jsonl.gz",
                "automatic-proposals.jsonl.gz",
            ]
        ],
        *[s.path for s in store.sources.values()],
    ]
    paths.extend(
        history_baseline / name
        for name in [
            "parents.jsonl.gz",
            "units-A.jsonl.gz",
            "units-B.jsonl.gz",
            "units-C.jsonl.gz",
            "complete.json",
        ]
    )
    override_log = engine.override_directory / "rebuilds.jsonl"
    if override_log.exists():
        paths.append(override_log)
        paths.extend(engine.override_directory / r["artifact"] for r in rows(override_log))
    hashes = {str(p.relative_to(BASE.parent)): sha(p.read_bytes()) for p in paths}
    fingerprint = sha(canonical(hashes))
    out = BASE / "data/corpus" / f"{VERSION}-{fingerprint[:12]}"
    if (out / "complete.json").exists():
        raise ValueError("Immutable generation already exists; use --verify-only")
    out.mkdir(parents=True, exist_ok=True)
    (out / ".private").mkdir(exist_ok=True)
    for p in [store.journal, engine.log.journal]:
        (out / ".private" / p.name).write_bytes(p.read_bytes())
    write_json(
        out / "inputs.json",
        dict(
            version=VERSION,
            fingerprint=fingerprint,
            baseline=str(BASELINE.relative_to(BASE)),
            human_history_baseline=str(history_baseline.resolve().relative_to(BASE.resolve())),
            files=hashes,
        ),
    )
    inventory = copy.deepcopy(rows(BASELINE / "inventory.jsonl.gz"))
    iv = {r["id"]: r for r in inventory}
    raw_units = {
        u["id"]: u for status in "ABC" for u in rows(BASELINE / f"units-{status}.jsonl.gz")
    }
    history_units = {
        u["id"]: u for status in "ABC" for u in rows(history_baseline / f"units-{status}.jsonl.gz")
    }
    # Existing override artifacts, if present, are immutable and source-checked by Articles.
    original_parents = {p["id"]: p for p in rows(BASELINE / "parents.jsonl.gz")}
    parents = []
    units = []
    all_candidates = []
    changes = []
    rebuilds = []
    crosswalk = []
    for index, (key, original) in enumerate(engine.parents.items(), 1):
        original_for_history = (
            history_engine.parents.get(key, original) if key in reviewed_parents else original
        )
        p = copy.deepcopy(original_for_history)
        p.pop("overlap_ids", None)
        r = store.by_id[key]
        state = store.state(r, latest)
        span = state["selected"] or {}
        incompatible = (span.get("start"), span.get("end")) != (p["start"], p["end"])
        newly_ready = state[
            "status"
        ] == "human_validated" and "articles_withheld_pending_documentary_review" in p.get(
            "anomalies", []
        )
        if (incompatible or newly_ready) and state["status"] == "human_validated":
            if key in reviewed_parents:
                raise ValueError(
                    "Explicit article reconciliation required for changed human-reviewed parent: "
                    + key
                )
            entry, p, own, _ = old.extract_one(
                store, effective(r, store.automatic_corrections.get(key)), state
            )
            if p is None:
                raise ValueError("Human parent reconstruction failed: " + key)
            iv[key].update(entry)
            rebuilds.append(
                dict(
                    document_id=key,
                    before=dict(
                        start=original_parents[key]["start"],
                        end=original_parents[key]["end"],
                        extent_id=original_parents[key]["extent_id"],
                    ),
                    after=dict(start=p["start"], end=p["end"], extent_id=p["extent_id"]),
                    parent_event_id=state["event"]["id"],
                    reason="apply_recorded_human_boundary_or_release_previously_uncertain_parent",
                    text_changed_beyond_whitespace=original_parents[key]["full_text"].strip()
                    != p["full_text"].strip(),
                )
            )
            records = [Articles.record_from_unit(p, u) for u in own]
        else:
            own_engine = history_engine if key in reviewed_parents else engine
            records = list(own_engine.base[key].values())
            raw = history_units if key in reviewed_parents else raw_units
            own = [raw.get(x["id"]) or to_unit(store, p, x) for x in records]
        # Human readiness changes class, not the recorded overlap/documentary evidence.
        if state["status"] == "human_validated":
            p.update(
                boundary_class="human_validated",
                boundary_status="human_validated",
                boundary_event_id=state["event"]["id"],
                extraction_state="established_parent",
            )
        current_records, candidates, repairs = rules.repair(
            store, p, records, protected_parent=key in reviewed_parents
        )
        engine.check(p, current_records)
        before = {u["id"]: u for u in own}
        new = [to_unit(store, p, x, before.get(x["id"])) for x in current_records]
        for change in repairs:
            changes.append(
                dict(parent_id=key, volume=p["volume"], **change, rule_version=rules.VERSION)
            )
        for c in candidates:
            all_candidates.append(
                dict(
                    parent_id=key, volume=p["volume"], protected_parent=key in reviewed_parents, **c
                )
            )
        original_own = [raw_units[uid] for uid in original_parents[key]["unit_ids"]]
        for old_unit in original_own:
            related = [
                u["id"]
                for u in new
                if old_unit["id"] in u.get("origin_ids", []) or u["id"] == old_unit["id"]
            ]
            if not related and (incompatible or newly_ready):
                related = [
                    u["id"]
                    for u in new
                    if any(
                        x < z and a < y
                        for x, y in old_unit["text_spans"]
                        for a, z in u["text_spans"]
                    )
                ]
            crosswalk.append(
                dict(
                    old_unit_id=old_unit["id"],
                    parent_id=key,
                    new_unit_ids=related,
                    status="unchanged"
                    if related == [old_unit["id"]]
                    else "recorded_human_parent_rebuild"
                    if (incompatible or newly_ready)
                    else "source_range_split_or_recovered",
                )
            )
        p["unit_ids"] = [u["id"] for u in new]
        parents.append(p)
        units.extend(new)
        iv[key].update(
            parent_id=key,
            start=p["start"],
            end=p["end"],
            boundary_class=p["boundary_class"],
            extraction_state=p["extraction_state"],
        )
        if index % 200 == 0:
            print("Processed", index, "parents", flush=True)
    pairs = old.overlaps(parents, inventory)
    old.write_core(out, parents, units)
    for name in ["documentary-review.jsonl.gz", "automatic-proposals.jsonl.gz"]:
        (out / name).write_bytes((BASELINE / name).read_bytes())
    old.jsonl(out / "inventory.jsonl.gz", inventory)
    old.jsonl(out / "boundary-resolutions.jsonl.gz", frozen)
    old.jsonl(out / "parent-human-updates.jsonl.gz", rebuilds)
    old.jsonl(out / "article-changes.jsonl.gz", changes)
    old.jsonl(out / "article-marker-candidates.jsonl.gz", all_candidates)
    old.jsonl(out / "unit-crosswalk.jsonl.gz", crosswalk)
    old.jsonl(out / "document-overlaps.jsonl.gz", pairs)
    checked, current, problems, duplicates, counts, volumes = old.verify_corpus(out, store)
    # The verified output folds every real human event over the unmodified human baselines.
    old.jsonl(out / "units.jsonl.gz", current)
    old.jsonl(out / "duplicate-source-spans.jsonl.gz", duplicates)
    pmap = {p["id"]: p for p in parents}
    by_parent = defaultdict(list)
    for c in all_candidates:
        by_parent[c["parent_id"]].append(c)
    change_index = defaultdict(list)
    for c in changes:
        for key in c["after_ids"]:
            change_index[key].append(c["kind"])
    qualities = [
        quality(store, pmap[r["parent_id"]], r, by_parent[r["parent_id"]], change_index)
        for r in current
    ]
    old.jsonl(out / "unit-quality.jsonl.gz", qualities)
    parent_quality = defaultdict(Counter)
    for q in qualities:
        parent_quality[q["parent_id"]].update([q["content_class"], q["category"]] + q["mechanisms"])
    parent_quality = {k: dict(v) for k, v in parent_quality.items()}
    write_json(
        out / "article-quality-summary.json",
        dict(
            by_parent=parent_quality,
            content_classes=dict(Counter(q["content_class"] for q in qualities)),
            mechanisms=dict(Counter(m for q in qualities for m in q["mechanisms"])),
            categories=dict(Counter(q["category"] for q in qualities)),
        ),
    )
    uncovered = []
    for v, source in store.sources.items():
        covered = [[p["start"], p["end"]] for p in parents if p["volume"] == v]
        outside = subtract([[0, len(source.text)]], covered)
        for a, z in outside:
            uncovered.append(
                dict(
                    volume=v,
                    start=a,
                    end=z,
                    text=source.text[a:z],
                    source_sha256=source.sha256,
                    role="outside_extracted_documents_not_assumed_cahier",
                )
            )
        union_len = len(source.text) - sum(z - a for a, z in outside)
        assert union_len >= 0 and union_len + sum(z - a for a, z in outside) == len(source.text)
    old.jsonl(out / "unassigned-source.jsonl.gz", uncovered)
    summary = dict(
        version=VERSION,
        notices_examined=len(inventory),
        texts_extracted=len(parents),
        autonomous_texts_extracted=sum(
            p["document_kind"] == "cahier_autonome_probable" for p in parents
        ),
        boundary_classes=dict(Counter(p["boundary_class"] for p in parents)),
        unresolved_notices=sum(not r["parent_id"] for r in inventory),
        counts=dict(counts),
        by_volume={str(v): dict(x) for v, x in volumes.items()},
        document_overlap_pairs=len(pairs),
        duplicate_source_span_groups=len(duplicates),
        article_rules_version=rules.VERSION,
        parent_updates_applied=len(rebuilds),
        automatically_split_units=sum(c["kind"] == "split_fused_article" for c in changes),
        articles_recovered_from_C=sum(c["kind"] == "recover_article_from_C" for c in changes),
        total_parent_characters=sum(len(p["full_text"]) for p in parents),
        total_parent_utf8_bytes=sum(len(p["full_text"].encode()) for p in parents),
        unassigned_source_characters=sum(r["end"] - r["start"] for r in uncovered),
        elapsed_seconds=time.perf_counter() - started,
        no_embeddings=True,
        no_index_preparation=True,
        no_boundary_discovery=True,
    )
    workbench = prepare_workbench(out, store, current, qualities, changes, reviewed_parents)
    write_json(out / "article-workbench.json", workbench)
    write_json(out / "summary.json", summary)
    assert all(sha(p.read_bytes()) == hashes[str(p.relative_to(BASE.parent))] for p in paths), (
        "Input changed during build"
    )
    write_json(
        out / "complete.json",
        dict(
            version=VERSION,
            input_fingerprint=fingerprint,
            files={
                p.name: sha(p.read_bytes())
                for p in out.iterdir()
                if p.is_file() and p.name != "complete.json"
            },
            human_preservation_verified=True,
            all_unit_source_coverage_verified=True,
        ),
    )
    if not no_activate:
        temp = old.CURRENT.with_suffix(".tmp")
        write_json(
            temp,
            dict(
                directory=str(out.relative_to(BASE)),
                version=VERSION,
                previous_directory=str(BASELINE.relative_to(BASE)),
            ),
        )
        os.replace(temp, old.CURRENT)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return out


def prepare_workbench(out, store, units, qualities, changes, reviewed_parents):
    import random

    rng = random.Random(178939072)
    qmap = {q["unit_id"]: q for q in qualities}
    by_id = {u["id"]: u for u in units}
    validation_path = BASE / "extraction/article-rule-checks.json"
    validation = (
        json.loads(validation_path.read_text()) if validation_path.exists() else {"cases": []}
    )
    historical_development = {p["id"] for p in rows(BASE / "data/article-corpus/parents.jsonl.gz")}
    historical_development.update(
        p["id"] for p in rows(BASELINE / "parents.jsonl.gz") if p.get("legacy_parent_ids")
    )
    # Digne was also in the original pilot but withheld from the 29-parent article corpus.
    historical_development.add("ap1789-registry-p1:arcpa_0000-0000_1879_num_3_1_1944")
    excluded = (
        set(reviewed_parents)
        | historical_development
        | {r["parent_id"] for r in validation["cases"]}
    )
    selected = []
    populations = {}
    for v in range(1, 7):
        for group in ["regular_article", "C_window"]:
            eligible = [
                u
                for u in units
                if u["volume"] == v
                and u["parent_id"] not in excluded
                and not u["human_validated"]
                and (
                    (
                        group == "regular_article"
                        and u["type"] == "article"
                        and not u["anomalies"]
                        and not qmap[u["id"]]["mechanisms"]
                        and u["source_status"] != "A"
                    )
                    or (
                        group == "C_window"
                        and u["type"] == "technical_passage"
                        and len(u["text"].strip()) >= 80
                    )
                )
            ]
            eligible.sort(key=lambda u: u["id"])
            populations[f"{v}:{group}"] = dict(
                count=len(eligible), ids_sha256=sha("\n".join(u["id"] for u in eligible))
            )
            if len(eligible) < 2:
                raise ValueError("Insufficient held-out sample candidates")
            for u in rng.sample(eligible, 2):
                selected.append(
                    dict(
                        id="sample-" + sha(u["id"])[:16],
                        group=group,
                        parent_id=u["parent_id"],
                        unit_id=u["id"],
                        volume=v,
                        start=u["start"],
                        end=u["end"],
                        title=store.by_id[u["parent_id"]]["metadata"]["title"],
                    )
                )
    # Bounded representative cases; the full machine inventory is not a manual to-do list.
    examples = []
    for kind in ["split_fused_article", "recover_article_from_C"]:
        own = sorted(
            [c for c in changes if c["kind"] == kind],
            key=lambda c: sha(canonical([c["parent_id"], c["new_spans"]])),
        )[:6]
        for c in own:
            u = by_id[c["after_ids"][-1]]
            examples.append(
                dict(
                    id="change-" + sha(u["id"])[:16],
                    group="automatic_correction",
                    parent_id=u["parent_id"],
                    unit_id=u["id"],
                    volume=u["volume"],
                    start=u["start"],
                    end=u["end"],
                    title=store.by_id[u["parent_id"]]["metadata"]["title"],
                )
            )
    for cls in ["possible_missed_article", "claim_prose_proposal", "uncertain"]:
        own = sorted(
            [q for q in qualities if q.get("content_class") == cls and not q["human_validated"]],
            key=lambda q: sha(q["unit_id"]),
        )[:2]
        for q in own:
            examples.append(
                dict(
                    id="case-" + sha(q["unit_id"])[:16],
                    group="targeted_case",
                    parent_id=q["parent_id"],
                    unit_id=q["unit_id"],
                    volume=q["volume"],
                    start=q["start"],
                    end=q["end"],
                    title=store.by_id[q["parent_id"]]["metadata"]["title"],
                )
            )
    return dict(
        version="article-workbench-1",
        seed=178939072,
        rules_sha256=sha((BASE / "extraction/article_rules.py").read_bytes()),
        generation=out.name,
        independent_sample=selected,
        examples=examples,
        populations=populations,
        excluded_development_parent_ids=sorted(excluded),
        human_decisions_created=0,
        sampling_method="Volumes 1..6; regular article then nonempty C; random.Random(seed).sample(sorted(eligible unit IDs),2) for each stratum. No difficulty selection; exclude original pilot, human-development and rule-check parents.",
        interpretation="Proposals and heuristic classes, never human validations or measured global reliability.",
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--no-activate", action="store_true")
    p.add_argument("--verify-only", type=Path)
    p.add_argument(
        "--history-baseline",
        type=Path,
        help="Pin immutable raw baselines used to replay human article history; defaults to active generation",
    )
    args = p.parse_args()
    if args.verify_only:
        out = args.verify_only
        _, current, _, _, counts, _ = old.verify_corpus(out)
        assert [canonical(r) for r in rows(out / "units.jsonl.gz")] == [
            canonical(r) for r in current
        ]
        complete = json.loads((out / "complete.json").read_text())
        assert all(
            sha((out / name).read_bytes()) == digest for name, digest in complete["files"].items()
        )
        print(json.dumps(dict(counts)))
        return
    build(args.no_activate, args.history_baseline)


if __name__ == "__main__":
    main()
