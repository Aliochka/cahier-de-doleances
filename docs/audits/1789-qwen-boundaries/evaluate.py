"""Compare des bornes XML sélectionnées à une référence distincte, jamais à la confiance LLM."""

import collections
import json
import math
import re
import statistics

from qcommon import HERE, jlines, rows, save


def ordinal(block_id):
    return int(block_id.split("-b")[1]) if block_id else None


def assess(w, ref, method, result):
    p = w["baseline"] if method == "A" else (result or {}).get("parsed")
    usable = bool(
        p
        and (method == "A" or p["decision"] == "propose")
        and p.get("start_id")
        and p.get("end_id")
    )
    row = dict(
        window_id=w["id"],
        method=method,
        persee_id=w["persee_id"],
        title=w["title"],
        reference_status=ref["status"],
        valid_output=(True if method == "A" else bool(p)),
        decision="propose"
        if method == "A" and p.get("raw")
        else ("no_proposal" if method == "A" else p["decision"] if p else "invalid"),
        uncertain=False if method == "A" else (p or {}).get("uncertain"),
        start_id=p.get("start_id") if p else None,
        end_id=p.get("end_id") if p else None,
        source_consistency_errors=[],
        exact=None,
        start_correct=None,
        end_correct=None,
        truncated=False,
        overwide=False,
        neighbour_title_absorbed=False,
        annex_misattributed=False,
        no_complete_block_in_A_span=(method == "A" and bool(p.get("raw")) and not usable),
    )
    if ref["status"] != "established":
        row["appropriate_abstention"] = bool(
            p and method != "A" and p["decision"] in {"abstain", "not_found"} and p["uncertain"]
        )
        return row
    row["start_correct"] = bool(usable and p["start_id"] == ref["start_id"])
    row["end_correct"] = bool(usable and p["end_id"] == ref["end_id"])
    row["exact"] = row["start_correct"] and row["end_correct"]
    if not usable:
        return row
    a, b = ordinal(p["start_id"]), ordinal(p["end_id"])
    ga, gb = ordinal(ref["start_id"]), ordinal(ref["end_id"])
    row["truncated"] = a > ga or b < gb
    row["overwide"] = a < ga or b > gb
    for n in w["blocks"]:
        pos = ordinal(n["id"])
        text = " ".join(n["text"].split())
        if (
            a <= pos <= b
            and not ga <= pos <= gb
            and n["tag"] != "pb"
            and re.match(r"^(?:CAHIER|MÉMOIRE|POUVOIRS|PROCÈS-VERBAL|ANNEXE|DOLÉANCES)", text)
        ):
            row["neighbour_title_absorbed"] = True
    for sig in p.get("signatures", []):
        if not a <= ordinal(sig) <= b:
            row["source_consistency_errors"].append("signature_outside_selected_bounds:" + sig)
    for aux in ref.get("annexes", []):
        x = ordinal(aux["start_id"])
        y = ordinal(aux.get("end_id"))
        if aux["relation"] == "excluded" and a <= x <= b:
            row["annex_misattributed"] = True
        if aux["relation"] == "included" and (a > x or (y is not None and b < y)):
            row["annex_misattributed"] = True
        for predaux in p.get("annexes", []):
            if ordinal(predaux["start_id"]) <= x <= ordinal(predaux["end_id"]) and predaux[
                "relation"
            ] not in {aux["relation"], "uncertain"}:
                row["annex_misattributed"] = True
    return row


def main():
    windows = rows(HERE / "data/windows.jsonl")
    allrows = []
    summary = {}
    for split in ["development", "validation"]:
        refs = {r["window_id"]: r for r in rows(HERE / f"data/reference-{split}.jsonl")}
        path = HERE / f"data/{split}-outputs.jsonl"
        outputs = rows(path) if path.exists() else []
        latest = {(r["window_id"], r["method"]): r for r in outputs}
        ss = [w for w in windows if w["split"] == split]
        by = {}
        for w in ss:
            ref = refs[w["id"]]
            for method in ["A", "B", "C"]:
                result = latest.get((w["id"], method))
                if method != "A" and result is None:
                    continue
                row = assess(w, ref, method, result)
                row["split"] = split
                row["known_initial_boundary_incorrect"] = ref.get(
                    "known_initial_boundary_incorrect", False
                )
                by[(w["id"], method)] = row
                allrows.append(row)
        metrics = {}
        nexact = sum(r["status"] == "established" for r in refs.values())
        for method in ["A", "B", "C"]:
            rs = [r for r in by.values() if r["method"] == method]
            exact = [r for r in rs if r["reference_status"] == "established"]
            runs = [r for r in outputs if r["method"] == method]
            metric = dict(
                cases=len(rs),
                adjudicable_reference_cases=nexact,
                exact=sum(r["exact"] is True for r in rs),
                wrong_starts=sum(
                    r["start_correct"] is False and r["decision"] == "propose" for r in exact
                ),
                wrong_ends=sum(
                    r["end_correct"] is False and r["decision"] == "propose" for r in exact
                ),
                truncated=sum(r["truncated"] for r in rs),
                overwide=sum(r["overwide"] for r in rs),
                neighbour_title_absorbed=sum(r["neighbour_title_absorbed"] for r in rs),
                annex_misattributed=sum(r["annex_misattributed"] for r in rs),
                abstentions=sum(
                    r["decision"] in {"abstain", "not_found", "no_proposal"} for r in rs
                ),
                invalid=sum(not r["valid_output"] for r in rs),
                reported_uncertain=sum(r["uncertain"] is True for r in rs),
                signature_consistency_failures=sum(
                    bool(r["source_consistency_errors"]) for r in rs
                ),
                appropriate_abstentions_uncertain_reference=sum(
                    r.get("appropriate_abstention", False) for r in rs
                ),
            )
            if method != "A":
                eligible = [r for r in exact if (r["window_id"], "A") in by]
                metric.update(
                    corrected_initially_wrong=sum(
                        not by[(r["window_id"], "A")]["exact"] and r["exact"] for r in eligible
                    ),
                    new_wrong_proposals_on_initially_correct=sum(
                        by[(r["window_id"], "A")]["exact"]
                        and not r["exact"]
                        and r["decision"] == "propose"
                        for r in eligible
                    ),
                    initially_correct_lost_to_invalid_or_abstention=sum(
                        by[(r["window_id"], "A")]["exact"] and r["decision"] != "propose"
                        for r in eligible
                    ),
                    confident_wrong_proposals=sum(
                        not r["exact"] and r["decision"] == "propose" and not r["uncertain"]
                        for r in exact
                    ),
                    uncertain_wrong_proposals=sum(
                        not r["exact"] and r["decision"] == "propose" and r["uncertain"] is True
                        for r in exact
                    ),
                    uncertain_correct=sum(r["exact"] and r["uncertain"] is True for r in exact),
                )
                metric["net_corrected_minus_degraded"] = (
                    metric["corrected_initially_wrong"]
                    - metric["new_wrong_proposals_on_initially_correct"]
                )
                metric["known_15_errors_fully_corrected"] = sum(
                    r["known_initial_boundary_incorrect"] and r["exact"] is True for r in rs
                )
                if runs:
                    secs = [r["seconds"] for r in runs]
                    metric["inference"] = dict(
                        calls=len(runs),
                        total_seconds=sum(secs),
                        median_seconds=statistics.median(secs),
                        mean_seconds=statistics.mean(secs),
                        p95_seconds=sorted(secs)[math.ceil(0.95 * len(secs)) - 1],
                        max_peak_allocated_gib=max(r["peak_allocated_bytes"] for r in runs) / 2**30,
                        max_peak_reserved_gib=max(r["peak_reserved_bytes"] for r in runs) / 2**30,
                        input_tokens_min=min(r["input_tokens"] for r in runs),
                        input_tokens_max=max(r["input_tokens"] for r in runs),
                        output_tokens_total=sum(r.get("output_tokens", 0) for r in runs),
                        seconds_projection_1305_at_observed_median=statistics.median(secs) * 1305,
                    )
            metrics[method] = metric
        # Pre-existing structural alerts, no fitting to reference/predictions.
        suspect = {
            w["id"]
            for w in ss
            if (w["baseline"].get("raw") or {}).get("flags")
            or not w["baseline"]["start_visible"]
            or not w["baseline"]["end_visible"]
        }
        groups = {}
        for label, ids in [
            ("suspect", suspect),
            ("no_structural_alert", {w["id"] for w in ss} - suspect),
        ]:
            group = {}
            for method in ["A", "B", "C"]:
                rs = [
                    r
                    for (key, m), r in by.items()
                    if m == method and key in ids and r["reference_status"] == "established"
                ]
                group[method] = dict(
                    cases=len(rs),
                    exact=sum(r["exact"] for r in rs),
                    wrong_proposals=sum(not r["exact"] and r["decision"] == "propose" for r in rs),
                )
            groups[label] = group
        summary[split] = dict(
            methods=metrics,
            reference_status=dict(collections.Counter(r["status"] for r in refs.values())),
            structural_alert_groups=groups,
            model_calls_expected=2 * len(ss),
            model_calls_observed=len(outputs),
            reference_independent_human=False,
            counts_not_additive=True,
        )
    jlines(HERE / "data/comparison.jsonl", allrows)
    save(HERE / "data/metrics.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
