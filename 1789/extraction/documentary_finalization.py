"""Apply source-examined decisions for the fixed 16-pair/23-notice finalization only.

This is a bounded documentary decision set, not a new discovery algorithm.
"""

import json
from pathlib import Path

MANIFEST = Path(__file__).with_name("documentary-finalization.json")


def apply(store, findings):
    data = json.loads(MANIFEST.read_text())
    if store.registry_sha != data["baseline_registry_sha256"]:
        raise ValueError("Documentary decision set requires its frozen registry")
    by_id = {r["document_id"]: r for r in findings}
    latest = store.latest()
    for repair in data["repairs"]:
        key = repair["document_id"]
        r = store.by_id[key]
        row = by_id[key]
        source = store.sources[repair["volume"]]
        if source.sha256 != repair["source_sha256"]:
            raise ValueError("Documentary decision/source fingerprint mismatch")
        a, z = repair["selected"]["start"], repair["selected"]["end"]
        if not 0 <= a < z <= len(source.text):
            raise ValueError("Invalid documentary decision range")
        for which in ["start", "end"]:
            node = source.node(repair[which + "_xpath"])
            x, y = source.span(node)
            text = source.text[x:y]
            quote = repair["opening_exact"] if which == "start" else repair["closing_exact"]
            if not (
                a <= x < y <= z
                and (text.startswith(quote) if which == "start" else text.endswith(quote))
            ):
                raise ValueError("Documentary XPath/position/evidence mismatch: " + key)
        state = store.state(r, latest)
        if state["event"] or state["stale"]:
            row["conflicts"].append(
                dict(
                    reason="human_decision_has_priority",
                    proposed=repair["selected"],
                    origin=data["version"],
                )
            )
            continue
        actual = row["selected"]
        actual_pair = (actual["start"], actual["end"]) if actual else None
        old = repair["expected_previous"]
        expected = (old["start"], old["end"]) if old else None
        if actual_pair != expected:
            row["conflicts"].append(
                dict(
                    reason="scoped_decision_baseline_changed",
                    expected=old,
                    actual=actual,
                    proposed=repair["selected"],
                )
            )
            continue
        row["selected"] = store.span_view(r, repair["selected"])
        row["alignment"] = "fort"
        row["source_review_status"] = "examined_by_Codex_not_human_validation"
        row["documentary_kind"] = repair["documentary_kind"]
        row["version"] = data["version"]
        row["actions"].append("scoped_documentary_source_examination")
        row["evidence"].append(dict(origin=str(MANIFEST.name), decision=repair))
        row["superseded_conflicts"] = row["conflicts"]
        row["conflicts"] = []
        codes = set(r["anomalies"]) | set((r["boundaries"].get("proposal") or {}).get("flags", []))
        for code in [
            "new_control_identity_error",
            "new_control_boundary_incorrect",
            "new_control_boundary_uncertain",
            "same_primary_anchor_multiple_notices",
        ]:
            if code in codes and not any(x["code"] == code for x in row["resolved_alerts"]):
                row["resolved_alerts"].append(
                    dict(
                        code=code,
                        reason="scoped_source_examination_replaces_original_hypothesis",
                        origin=data["version"],
                    )
                )
        tail = z
        while tail > a and source.text[tail - 1].isspace():
            tail -= 1
        pg = store.lib.base.page_index(source)[1](tail - 1)["page"]
        if pg == r["metadata"]["page_end"] and "end_page_mismatch_requires_review" in codes:
            if not any(
                x["code"] == "end_page_mismatch_requires_review" for x in row["resolved_alerts"]
            ):
                row["resolved_alerts"].append(
                    dict(
                        code="end_page_mismatch_requires_review",
                        reason="corrected_source_content_end_matches_metadata",
                        end_page=pg,
                    )
                )
        original = row["original_span"]
        row["changed"] = original is None or (a, z) != (original["start"], original["end"])
    return list(by_id.values())
