"""Mesures sur la référence gelée ; aucune adaptation des règles."""

import collections
import gzip
import json

from common import HERE, rows, sources, write
from data_io import units as load_units


def canon(s, a, b):
    while a < b and s.text[a].isspace():
        a += 1
    while b > a and s.text[b - 1].isspace():
        b -= 1
    return a, b


def main():
    ss = sources()
    auto = rows(HERE / "data/automatic-units.jsonl")
    sel = {c["id"]: c for c in rows(HERE / "data/selection.jsonl")}
    refs = rows(HERE / "data/reference-documents.jsonl")
    parent = []
    windows = []
    errors = []
    total = dict(
        gold=0,
        predicted=0,
        correct=0,
        correct_starts=0,
        correct_ends=0,
        missed=0,
        false_predictions=0,
        fused=0,
        split=0,
    )
    false_parent_predictions = 0
    for d in refs:
        cid = d["candidate_id"]
        c = sel[cid]
        s = ss[c["volume"]]
        matching = bool(
            d["real"] and canon(s, c["start"], c["end"]) == tuple(d["parent_reference_span"])
        )
        parent.append(
            dict(
                candidate_id=cid,
                volume=c["volume"],
                true_cahier=d["real"],
                kind=d["kind"],
                correct_parent_boundary=matching,
                automatic_span=[c["start"], c["end"]],
                reference_span=d.get("parent_reference_span"),
                reason=d["reason"],
            )
        )
        for wi, w in enumerate(d["reference_windows"]):
            predictions = [
                u for u in auto if u["candidate_id"] == cid and w["start"] <= u["start"] < w["end"]
            ]
            if not d["real"]:
                false_parent_predictions += len(predictions)
                continue
            gold = w["units"]
            gp = {(g["start"], g["end"]) for g in gold}
            pp = {(u["start"], u["end"]) for u in predictions}
            correct = len(gp & pp)
            cs = len({g[0] for g in gp} & {p[0] for p in pp})
            ce = len({g[1] for g in gp} & {p[1] for p in pp})
            fused = sum(
                sum(u["start"] <= g["start"] < u["end"] for g in gold) > 1 for u in predictions
            )
            split = sum(
                sum(g["start"] <= u["start"] < g["end"] for u in predictions) > 1 for g in gold
            )
            row = dict(
                candidate_id=cid,
                window=wi,
                volume=c["volume"],
                start=w["start"],
                end=w["end"],
                gold=len(gold),
                predicted=len(predictions),
                correct=correct,
                correct_starts=cs,
                correct_ends=ce,
                missed=len(gp - pp),
                false_predictions=len(pp - gp),
                fused=fused,
                split=split,
            )
            windows.append(row)
            for k in total:
                total[k] += row[k]
            for u in predictions:
                if (u["start"], u["end"]) in gp:
                    continue
                overlaps = [g for g in gold if g["start"] < u["end"] and g["end"] > u["start"]]
                errors.append(
                    dict(
                        candidate_id=cid,
                        window=wi,
                        prediction=u,
                        overlapping_reference=overlaps,
                        kind="fusion"
                        if sum(u["start"] <= g["start"] < u["end"] for g in gold) > 1
                        else "wrong_or_truncated_boundary",
                    )
                )
            for g in gold:
                if not any(u["start"] == g["start"] for u in predictions):
                    errors.append(
                        dict(candidate_id=cid, window=wi, kind="missed_article_start", reference=g)
                    )
    total["precision"] = total["correct"] / total["predicted"] if total["predicted"] else None
    total["recall"] = total["correct"] / total["gold"] if total["gold"] else None
    total["start_precision"] = (
        total["correct_starts"] / total["predicted"] if total["predicted"] else None
    )
    total["end_precision"] = (
        total["correct_ends"] / total["predicted"] if total["predicted"] else None
    )
    with gzip.open(HERE / "data/documents.jsonl.gz", "rt") as f:
        documents = [json.loads(line) for line in f]
    units = load_units()
    active = [d for d in documents if d["record_status"] != "quarantined_false_parent"]
    nonwhite = sum(sum(not c.isspace() for c in d["full_text"]) for d in active)
    a_chars = sum(sum(not c.isspace() for c in u["text"]) for u in units if u["status"] == "A")
    overlaps = []
    for i, d in enumerate(active):
        for e in active[:i]:
            if (
                d["volume"] == e["volume"]
                and d["source_text_start"] < e["source_text_end"]
                and e["source_text_start"] < d["source_text_end"]
            ):
                overlaps.append(dict(left=e["id"], right=d["id"], volume=d["volume"]))
    negatives = json.loads((HERE / "data/reference-negative.json").read_text())
    report = dict(
        parent_validation=dict(
            evaluated=len(parent),
            true_cahiers=sum(p["true_cahier"] for p in parent),
            false_positives=sum(not p["true_cahier"] for p in parent),
            precision=sum(p["true_cahier"] for p in parent) / len(parent),
            correct_boundaries=sum(p["correct_parent_boundary"] for p in parent),
            true_parent_boundary_errors=sum(
                p["true_cahier"] and not p["correct_parent_boundary"] for p in parent
            ),
            global_recall=None,
            scope="12 held-out selected candidates, balanced deliberate length/structure strata; Codex not independent human",
        ),
        parents=parent,
        article_validation_before_correction=total,
        windows=windows,
        false_parent_article_proposals_excluded_from_conditional_article_metrics=false_parent_predictions,
        negative_control=dict(
            windows=len(negatives),
            classifications=dict(collections.Counter(n["classification"] for n in negatives)),
            global_recall=None,
            scope="conditional uncovered paragraph windows; additional enclosing beginnings inspected; not exhaustive source-area census",
        ),
        final_corpus=dict(
            records=len(documents),
            quarantined=len(documents) - len(active),
            non_quarantined_hypotheses=len(active),
            verified_units_A=sum(u["status"] == "A" for u in units),
            proposed_units_B=sum(u["status"] == "B" for u in units),
            A_fraction=sum(u["status"] == "A" for u in units) / len(units),
            A_nonwhite_characters=a_chars,
            all_active_parent_nonwhite_characters=nonwhite,
            A_text_coverage=a_chars / nonwhite,
            new_A=sum(
                u["status"] == "A" and u.get("origin") != "inherited_pilot_30" for u in units
            ),
            overlapping_parent_hypotheses=overlaps,
        ),
        human_validation_seconds=None,
        independent_human_validation=False,
    )
    write(HERE / "data/evaluation.json", report)
    write(HERE / "data/article-errors.json", errors)
    print("Held-out parents:", report["parent_validation"])
    print("Held-out articles before correction:", total)
    print("Final corpus:", report["final_corpus"])


if __name__ == "__main__":
    main()
