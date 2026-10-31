"""Read-only analysis of existing human decisions; no segmentation or inference."""

import copy
import json
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "1789/tools/document-review"))
from articles import HUMAN, Articles  # noqa: E402
from reviewlib import Store, rows, sha  # noqa: E402
from segmentation_comparison import comparison  # noqa: E402


def output(name, value):
    (HERE / "data" / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def bounds(record):
    return record["spans"][0][0], record["spans"][-1][1]


def shape(record):
    return record["type"], record["number"], record["spans"]


def main():
    real = ROOT / "1789/data/private/document-review/article-decisions.jsonl"
    private = HERE / ".local/article-decisions.snapshot.jsonl"
    if not private.exists():
        private.write_bytes(real.read_bytes())
    parent_real = ROOT / "1789/data/private/document-review/decisions.jsonl"
    parent_private = HERE / ".local/parent-decisions.snapshot.jsonl"
    if not parent_private.exists():
        parent_private.write_bytes(parent_real.read_bytes())
    s = Store(parent_private)
    a = Articles(s, private)
    events = a.log.history()
    campaign_path = ROOT / "1789/tools/document-review/campaigns/five-cahiers.json"
    campaign = json.loads(campaign_path.read_text())
    random_ids = {d["id"] for d in campaign["selected"]}
    old_comparison = rows(
        ROOT / "1789/data/segmentation-proposals/comparison.jsonl.gz"
    )
    old_comparison = {r["document_id"]: r for r in old_comparison}
    metrics = []
    flags = {}
    full = {}
    triage = []
    reviewed = {e["document_id"] for e in events}
    context_queue = set()
    for p in a.parents.values():
        base = list(a.base[p["id"]].values())
        articles = sorted([r for r in base if r["type"] == "article"], key=bounds)
        with patch("segmentation_comparison.comparison", return_value=None):
            old = a.anomalies(p, base)
        overlay = comparison(p)
        automatic = copy.deepcopy(overlay)
        if automatic and automatic.get("available"):
            automatic["markers"] = [m for m in automatic["markers"] if m["status"] != "review_note"]
        with patch("segmentation_comparison.comparison", return_value=automatic):
            auto = a.anomalies(p, base)
        all_flags = a.anomalies(p, base)
        for i, r in enumerate(articles):
            if auto[r["id"]]:
                context_queue.update(n["id"] for n in articles[max(0, i - 1) : i + 2])
        flags[p["id"]] = dict(old=old, auto=auto, all=all_flags, overlay=overlay)
        for r in articles:
            category = 3 if not a.parent_version(p)["ready"] else 2 if auto[r["id"]] else 1
            triage.append(
                dict(
                    document_id=p["id"],
                    unit_id=r["id"],
                    category=category,
                    old_flags=old[r["id"]],
                    automatic_flags=auto[r["id"]],
                    human_reviewed_document=p["id"] in reviewed,
                )
            )
        if p["id"] not in reviewed:
            continue
        parent, records, history, head, stale = a.state(p["id"], events)
        a.check(parent, list(records.values()))
        actual = [r for r in records.values() if r["type"] == "article"]
        accepted = [
            r
            for r in actual
            if r["review_status"] in HUMAN
            and any(shape(r) == shape(b) and b["id"] in r["origin_ids"] for b in articles)
        ]
        corrected = [r for r in actual if r["review_status"] in HUMAN and r not in accepted]
        base_changed = [b for b in articles if not any(shape(b) == shape(r) for r in actual)]
        valid_events = [e for e in history if e["action"] == "validate"]
        item = dict(
            id=p["id"],
            persee_id=p["persee_id"],
            title=p["metadata"]["title"],
            volume=p["volume"],
            group="random_five" if p["id"] in random_ids else "development_five",
            initial_articles=len(articles),
            final_articles=len(actual),
            human_reviewed_articles=sum(r["review_status"] in HUMAN for r in actual),
            accepted_without_change=len(accepted),
            corrected_or_created_final=len(corrected),
            initial_articles_changed=len(base_changed),
            new_articles=len(actual) - len(articles),
            actions=dict(Counter(e["action"] for e in history)),
            validation_operations=len(valid_events),
            individual_validation_operations=sum(
                sum(r["type"] == "article" for r in e["after"]) == 1 for e in valid_events
            ),
            group_validation_operations=sum(
                sum(r["type"] == "article" for r in e["after"]) > 1 for e in valid_events
            ),
            historical_uncertain_events=sum(e["action"] == "uncertain" for e in history),
            final_uncertain_articles=sum(r["review_status"] == "uncertain" for r in actual),
            final_uncertain_units=sum(r["review_status"] == "uncertain" for r in records.values()),
            classify_events=sum(e["action"] == "classify" for e in history),
            stale_events=len(stale),
            old_flagged_articles=sum(bool(old[r["id"]]) for r in articles),
            automatic_flagged_articles=sum(bool(auto[r["id"]]) for r in articles),
            accepted_with_old_flag=sum(
                bool(old[b["id"]]) for b in articles if any(shape(b) == shape(r) for r in accepted)
            ),
            accepted_with_auto_flag=sum(
                bool(auto[b["id"]]) for b in articles if any(shape(b) == shape(r) for r in accepted)
            ),
        )
        metrics.append(item)
        full[p["id"]] = dict(parent=p, initial=articles, actual=actual, base_changed=base_changed)
    # Manual incident catalogue, derived by examining before/after source ranges.
    annotations = json.loads((HERE / "annotations.json").read_text())
    errors = []
    by_event = {e["id"]: e for e in events}
    for note in annotations:
        es = [by_event[k] for k in note["event_ids"]]
        pid = es[0]["document_id"]
        p = a.parents[pid]
        before_articles = [r for e in es for r in e["before"] if r["type"] == "article"]
        original_ids = {
            oid
            for r in before_articles
            for oid in r["origin_ids"]
            if oid in a.base[pid] and a.base[pid][oid]["type"] == "article"
        }
        idx = [i for i, r in enumerate(full[pid]["initial"]) if r["id"] in original_ids]
        neighbours = {r["id"] for i in idx for r in full[pid]["initial"][max(0, i - 1) : i + 2]}
        relevant = []
        for e in es:
            for r in e["after"]:
                if r["type"] == "article":
                    relevant.append(bounds(r))
        if not idx:
            # A missing unit absent from the initial articles: context-only warning.
            start = min(x for x, z in relevant)
            neighbours = {r["id"] for r in full[pid]["initial"] if abs(bounds(r)[0] - start) < 1200}
        f = flags[pid]
        markers = f["overlay"]["markers"] if f["overlay"] and f["overlay"].get("available") else []
        initial_changed = [a.base[pid][i] for i in original_ids]

        def point_relevant(x):
            return any(b["spans"][0][0] <= x < b["spans"][-1][1] for b in initial_changed) or any(
                abs(x - a0) <= 30 for a0, z in relevant
            )

        marker_hits = [
            dict(start=m["start"], label=m["label"], status=m["status"])
            for m in markers
            if point_relevant(m["start"])
        ]
        roles = [r for r in old_comparison[pid]["role_changes"] if point_relevant(r["start"])]
        old_direct = any(f["old"][i] for i in original_ids)
        auto_direct = any(f["auto"][i] for i in original_ids)
        errors.append(
            dict(
                note,
                document_id=pid,
                persee_id=p["persee_id"],
                original_ids=sorted(original_ids),
                source_version=p["source"]["source_sha256"],
                source_spans_after=sorted(set(relevant)),
                old_direct_alert=old_direct,
                old_neighbour_alert=any(f["old"][i] for i in neighbours),
                automatic_direct_alert=auto_direct,
                automatic_marker_hits=[m for m in marker_hits if m["status"] != "review_note"],
                manual_notes=[m for m in marker_hits if m["status"] == "review_note"],
                role_difference_panel_signals=roles,
            )
        )
    for e in errors:
        e["proposed_context_queue_or_marker_hit"] = bool(
            set(e["original_ids"]) & context_queue
        ) or bool(e["automatic_marker_hits"])
    for m in metrics:
        es = [e for e in errors if e["document_id"] == m["id"]]
        m["incidents_by_primary_category"] = dict(Counter(e["category"] for e in es))
        m["confirmed_fusions"] = sum(e["category"] == "A" for e in es)
        m["possible_fusion_without_explicit_number"] = sum(
            e["subtype"] == "unmarked_prose_promoted_to_article" for e in es
        )
        m["incorrect_splits"] = sum(e["category"] == "B" for e in es)
        m["other_incidents"] = sum(e["category"] not in {"A", "B"} for e in es)
    groups = {}
    for name in ["development_five", "random_five"]:
        ms = [m for m in metrics if m["group"] == name]
        groups[name] = {
            key: sum(m[key] for m in ms)
            for key in [
                "initial_articles",
                "final_articles",
                "human_reviewed_articles",
                "accepted_without_change",
                "corrected_or_created_final",
                "initial_articles_changed",
                "new_articles",
                "confirmed_fusions",
                "possible_fusion_without_explicit_number",
                "other_incidents",
                "individual_validation_operations",
                "group_validation_operations",
                "final_uncertain_articles",
            ]
        }
    serious = [e for e in errors if e["severity"] == "major"]
    detection = dict(
        context_queue_all_initial_articles=len(context_queue),
        context_queue_unreviewed_initial_articles=sum(
            t["unit_id"] in context_queue and not t["human_reviewed_document"] for t in triage
        ),
        major_context_queue_or_marker_hits=sum(
            e["proposed_context_queue_or_marker_hit"] for e in serious
        ),
        incident_count=len(errors),
        major_incidents=len(serious),
        old_direct=sum(e["old_direct_alert"] for e in errors),
        automatic_direct=sum(e["automatic_direct_alert"] for e in errors),
        major_old_direct=sum(e["old_direct_alert"] for e in serious),
        major_automatic_direct=sum(e["automatic_direct_alert"] for e in serious),
        major_automatic_marker_hits=sum(bool(e["automatic_marker_hits"]) for e in serious),
        major_with_manual_note=sum(bool(e["manual_notes"]) for e in serious),
        triage_all_initial_articles=dict(Counter(t["category"] for t in triage)),
        triage_random_five=dict(
            Counter(t["category"] for t in triage if t["document_id"] in random_ids)
        ),
        triage_unreviewed_initial_articles=dict(
            Counter(t["category"] for t in triage if not t["human_reviewed_document"])
        ),
    )
    parent_history = s.history()
    parent_seconds = [
        e["active_seconds"]
        for e in parent_history
        if isinstance(e.get("active_seconds"), (int, float))
    ]
    mutation_events = {e["id"] for e in events if e["action"] not in {"validate", "uncertain"}}
    annotated_ids = [eid for note in annotations for eid in note["event_ids"]]
    assert set(annotated_ids) == mutation_events
    assert len(annotated_ids) == len(set(annotated_ids))
    validation_ids = [
        r["id"]
        for e in events
        if e["action"] == "validate"
        for r in e["after"]
        if r["type"] == "article"
    ]
    summary = dict(
        distinct_ids_ever_validated=len(set(validation_ids)),
        repeated_validate_operations=len(validation_ids) - len(set(validation_ids)),
        mutation_events_classified=len(mutation_events),
        events=len(events),
        cahiers=len(metrics),
        groups=groups,
        current_human_articles=sum(m["human_reviewed_articles"] for m in metrics),
        accepted_without_change=sum(m["accepted_without_change"] for m in metrics),
        corrected_or_created_final=sum(m["corrected_or_created_final"] for m in metrics),
        initial_articles_changed=sum(m["initial_articles_changed"] for m in metrics),
        new_articles=sum(m["new_articles"] for m in metrics),
        incident_categories=dict(Counter(e["category"] for e in errors)),
        human_article_duration_fields=sorted(
            {k for e in events for k in e if any(t in k for t in ["duration", "seconds"])}
        ),
        parent_instrumentation=dict(
            events=len(parent_history),
            events_with_active_seconds=len(parent_seconds),
            active_seconds_sum=sum(parent_seconds),
        ),
        reported_times_minutes=dict(previous_three_difficult=30, random_five=15),
        time_measurement="Approximate user statements, not measured active times",
        random_campaign_events_since_baseline=len(events) - campaign["journal_baseline_events"],
    )
    output("summary.json", summary)
    output("cahiers.json", metrics)
    output("errors.json", errors)
    output("detection.json", detection)
    for t in triage:
        t["in_context_queue"] = t["unit_id"] in context_queue
        t["category_status"] = "provisional_screening_not_validated_quality"
    output("triage.json", triage)
    output(
        "checks.json",
        dict(
            valid_hash_chained_journal=True,
            coverage_checks_passed=True,
            stale_events=sum(m["stale_events"] for m in metrics),
            real_journal_prefix_preserved=real.read_bytes().startswith(private.read_bytes()),
            human_decisions_written=0,
            segmentation_executed=False,
        ),
    )
    paths = [
        real,
        private,
        parent_real,
        parent_private,
        campaign_path,
        a.directory / "parents.jsonl.gz",
        *(a.directory / f"units-{x}.jsonl.gz" for x in "ABC"),
        ROOT / "1789/tools/document-review/articles.py",
        ROOT / "1789/extraction/segmentation.py",
        ROOT / "1789/data/segmentation-proposals/comparison.jsonl.gz",
        HERE / "annotations.json",
    ]
    paths.extend(source.path for source in s.sources.values())
    output(
        "provenance.json",
        dict(
            snapshot_events=len(events),
            files={
                str(path.relative_to(ROOT)): dict(
                    bytes=path.stat().st_size, sha256=sha(path.read_bytes())
                )
                for path in paths
            },
            source_revision="926fd3cd986a3c3d411e93d1845fff6475cb2602",
        ),
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(detection, indent=2))


if __name__ == "__main__":
    main()
