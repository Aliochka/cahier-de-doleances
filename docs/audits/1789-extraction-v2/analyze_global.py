"""Diff complet V1/V2; rapprochement par ancre, sans changement d'identifiant ancien."""

import collections

from common import HERE, PILOT, V1, jlines, rows, write


def main():
    old = rows(V1 / "data/candidates.jsonl")
    v1 = [p for p in old if p["classification"] == "document_candidate"]
    v2 = rows(HERE / "data/v2-document-predictions.jsonl")
    admitted = [
        p
        for p in v2
        if p["classification"] in {"autonomous", "associated"} and not p.get("attached_to")
    ]

    def key(p):
        return p["volume"], p["anchor_xpath"]

    lookup = {key(p): p for p in v2}
    orig = {key(p): p for p in v1}
    changes = []
    for k in sorted(set(lookup) | set(orig)):
        a = orig.get(k)
        b = lookup.get(k)
        if not a and (not b or b["classification"] not in {"autonomous", "associated"}):
            continue
        changes.append(
            dict(
                volume=k[0],
                anchor_xpath=k[1],
                v1_id=a["id"] if a else None,
                v2_id=b["id"] if b else None,
                v1_span=[a["start"], a["end"]] if a else None,
                v2_span=[b["start"], b["end"]] if b else None,
                v2_class=b["classification"] if b else "not_in_leaf_frame",
                v2_subtype=b["subtype"] if b else None,
                v2_attached_to=b.get("attached_to") if b else None,
                title=(b or a)["title"],
                same_identifier=bool(a and b and a["id"] == b["id"]),
                bounds_changed=bool(a and b and (a["start"], a["end"]) != (b["start"], b["end"])),
                review_status="automatic_diff_not_documentary_certification",
            )
        )
    jlines(HERE / "data/v1-v2-document-diff.jsonl", changes)
    cross = []
    for d in rows(PILOT / "data/documents.jsonl"):
        b = lookup.get((d["volume"], d["divisions"][0]))
        cross.append(
            dict(
                legacy_document_id=d["id"],
                legacy_key=d["key"],
                legacy_source_span=[d["source_text_start"], d["source_text_end"]],
                v2_candidate_id=b["id"] if b else None,
                v2_source_span=[b["start"], b["end"]] if b else None,
                equivalent_bounds=bool(
                    b and (d["source_text_start"], d["source_text_end"]) == (b["start"], b["end"])
                ),
                legacy_reference_authority="unchanged original pilot; V2 hypothesis does not replace it",
            )
        )
    jlines(HERE / "data/legacy-document-crosswalk.jsonl", cross)
    anomalies = []
    for p in v2:
        if p["end"] <= p["start"]:
            anomalies.append(dict(id=p["id"], kind="non_positive_span"))
        if p["classification"] in {"autonomous", "associated"} and p["end"] - p["start"] < 220:
            anomalies.append(
                dict(
                    id=p["id"],
                    kind="short_admitted_hypothesis",
                    volume=p["volume"],
                    title=p["title"],
                )
            )
        if (
            p["classification"] in {"autonomous", "associated"}
            and "internal_documents_separated" in p["uncertainties"]
        ):
            anomalies.append(
                dict(
                    id=p["id"],
                    kind="split_root_requires_review",
                    volume=p["volume"],
                    title=p["title"],
                )
            )
    jlines(HERE / "data/global-anomalies.jsonl", anomalies)
    summary = dict(
        v1_all_signals=len(old),
        v1_admitted=len(v1),
        v2_all_classified_anchors=len(v2),
        v2_admitted_including_attached=sum(
            p["classification"] in {"autonomous", "associated"} for p in v2
        ),
        v2_parent_hypotheses_without_attached=len(admitted),
        v1_reclassified=dict(collections.Counter(r["v2_class"] for r in changes if r["v1_id"])),
        old_admitted_missing_from_leaf_frame=sum(
            bool(r["v1_id"]) and r["v2_id"] is None for r in changes
        ),
        added_admitted_anchors=sum(
            r["v1_id"] is None and r["v2_class"] in {"autonomous", "associated"} for r in changes
        ),
        old_admitted_ids_preserved=sum(r["same_identifier"] for r in changes),
        matched_bounds_changed=sum(r["bounds_changed"] for r in changes),
        old30_exact_parent_hypotheses=sum(r["equivalent_bounds"] for r in cross),
        anomalies=len(anomalies),
        anomaly_types=dict(collections.Counter(a["kind"] for a in anomalies)),
        by_volume={
            str(v): dict(
                v1=sum(p["volume"] == v for p in v1),
                v2_autonomous=sum(
                    p["volume"] == v and p["classification"] == "autonomous" for p in v2
                ),
                v2_associated=sum(
                    p["volume"] == v and p["classification"] == "associated" for p in v2
                ),
            )
            for v in range(1, 7)
        },
        all_global_predictions_unverified=True,
    )
    write(HERE / "data/global-comparison.json", summary)
    print(summary)


if __name__ == "__main__":
    main()
