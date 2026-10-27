"""Mesures locales; sépare identité, ambiguïté, frontières et simple présence des candidats."""

import collections

from auditlib import HERE, PREVIOUS, jlines, read, rows, save, sha


def verify_freezes():
    for name in ["rules-freeze.json", "complementary-freeze.json", "annotations-freeze.json"]:
        for f, h in read(HERE / name)["files"].items():
            assert sha((HERE / f).read_bytes()) == h, (name, f)


def main():
    verify_freezes()
    pred = {r["persee_id"]: r for r in rows(HERE / "data/alignment-predictions.jsonl")}
    cp = {r["persee_id"]: r for r in rows(HERE / "data/complementary-predictions.jsonl")}
    meta = {r["id"]: r for r in rows(HERE / "data/metadata.jsonl")}
    v2 = {
        (p["volume"], p["anchor_xpath"]): p
        for p in rows(PREVIOUS / "data/v2-document-predictions.jsonl")
    }
    results = []
    for ref in rows(HERE / "data/annotations.jsonl"):
        pid = ref["persee_id"]
        r = pred[pid]
        m = meta[pid]
        c = cp[pid]
        is_target = ref["kind"] != "not_cahier"
        g = ref.get("boundary_reference")
        a = v2.get((ref["volume"], ref.get("target_anchor")))
        a_admitted = bool(a and a["classification"] in {"autonomous", "associated"})
        if not is_target:
            results.append(
                dict(
                    persee_id=pid,
                    volume=r["volume"],
                    title=r["title"],
                    selection=m["selection"],
                    target=False,
                    dc_type=m["dc_type"],
                    type_griev_false_cahier=(m["dc_type"] == ["griev"]),
                    reason=ref["reason"],
                    B_raw_status=r["status"],
                    C_status=c["status"],
                )
            )
            continue
        good = set(ref["acceptable_identity_anchors"])
        best = r["candidates"][0] if r["candidates"] else None
        if ref["identity_review"] == "uncertain":
            b_outcome = "uncertain_identity_or_scope"
        elif best and best["anchor_xpath"] in good:
            b_outcome = "correct_compatible_identity"
        else:
            b_outcome = "incorrect_identity"
        cc = c["candidates"]
        c_hit = any(p["anchor_xpath"] in good for p in cc)
        if ref["identity_review"] == "uncertain":
            c_outcome = "uncertain_identity_or_scope"
        elif c_hit:
            c_outcome = (
                "correct_unique_proposal" if len(cc) == 1 else "correct_target_in_ambiguous_queue"
            )
        elif cc:
            c_outcome = "incorrect_candidates"
        else:
            c_outcome = "not_found"

        def bounds(p):
            if not g:
                return None
            if p is None:
                return dict(available=False, start=False, end=False, both=False)
            return dict(
                available=True,
                start=p["start"] == g["start"],
                end=p["end"] == g["end"],
                both=(p["start"], p["end"]) == (g["start"], g["end"]),
                proposed_start=p["start"],
                proposed_end=p["end"],
                expected_start=g["start"],
                expected_end=g["end"],
            )

        a_bounds = dict(start=a["start"], end=a["end"]) if a_admitted else None
        results.append(
            dict(
                persee_id=pid,
                volume=r["volume"],
                title=r["title"],
                selection=m["selection"],
                target=True,
                kind=ref["kind"],
                reference_anchor=ref["target_anchor"],
                A_admitted=a_admitted,
                A_class=a["classification"] if a else None,
                A_strict_autonomous=bool(a and a["classification"] == "autonomous"),
                B_status=r["status"],
                B_top_identity=b_outcome,
                B_confidence_score=best["score"] if best else None,
                B_primary_anchor=best["anchor_xpath"] if best else None,
                B_proposed=r["status"] != "not_found",
                C_status=c["status"],
                C_identity=c_outcome,
                C_candidates=len(cc),
                C_target_present=c_hit,
                A_boundaries=bounds(a_bounds),
                B_boundaries=bounds(r["boundary"]),
                C_boundaries=bounds(c.get("boundary")),
                review_reason=ref["identity_reason"],
                reference_boundary_scope=g["scope"] if g else None,
            )
        )
    jlines(HERE / "data/comparisons.jsonl", results)
    jlines(
        HERE / "data/correspondences.jsonl",
        [
            dict(
                metadata=meta[r["persee_id"]],
                predictions=pred[r["persee_id"]],
                complementary=cp[r["persee_id"]],
                review=r,
            )
            for r in results
        ],
    )

    def aggregate(rr):
        tt = [r for r in rr if r["target"]]
        bb = [r for r in tt if r["B_proposed"]]
        strong = [r for r in tt if r["B_status"] == "strong_proposal"]
        boundary = [r for r in tt if r["B_boundaries"] is not None]
        return dict(
            notices=len(rr),
            target_documents=len(tt),
            target_kinds=dict(collections.Counter(r["kind"] for r in tt)),
            non_cahiers=len(rr) - len(tt),
            type_griev_false_cahiers=sum(r.get("type_griev_false_cahier", False) for r in rr),
            A_admitted=sum(r["A_admitted"] for r in tt),
            A_autonomous=sum(r["A_strict_autonomous"] for r in tt),
            B_proposals=len(bb),
            B_status=dict(collections.Counter(r["B_status"] for r in tt)),
            B_proposed_judgments=dict(collections.Counter(r["B_top_identity"] for r in bb)),
            B_all_top_judgments_including_abstentions=dict(
                collections.Counter(r["B_top_identity"] for r in tt)
            ),
            B_strong_judgments=dict(collections.Counter(r["B_top_identity"] for r in strong)),
            C_status=dict(collections.Counter(r["C_status"] for r in tt)),
            C_judgments=dict(collections.Counter(r["C_identity"] for r in tt)),
            C_target_in_candidate_queue=sum(r["C_target_present"] for r in tt),
            boundary_reviewed=len(boundary),
            boundaries={
                ver: dict(
                    proposed=sum(r[ver + "_boundaries"]["available"] for r in boundary),
                    start_correct=sum(r[ver + "_boundaries"]["start"] for r in boundary),
                    end_correct=sum(r[ver + "_boundaries"]["end"] for r in boundary),
                    both_correct=sum(r[ver + "_boundaries"]["both"] for r in boundary),
                )
                for ver in ["A", "B", "C"]
            },
        )

    unseen = set(read(HERE / "complementary-freeze.json")["unexamined_new_ids"])
    metrics = dict(
        all=aggregate(results),
        development=aggregate([r for r in results if r["selection"] == "development_control"]),
        new_hash=aggregate([r for r in results if r["selection"] == "new_hash_sample"]),
        complementary_unexamined_subset=aggregate([r for r in results if r["persee_id"] in unseen]),
        limitations=[
            "Codex exploratory non-independent judgments, predictions visible",
            "Identity judgments do not certify exact XML boundaries or historical text accuracy",
            "Boundary reference is a declared Stanford documentary policy, not exact Persée text-zone equivalence",
            "METS selection covers six issue catalogues; not a statistically representative sample or exhaustive recall test",
            "C formalized after source packs volumes1–3; untouched comparison limited to recorded volumes4–6 hash subset",
        ],
    )
    save(HERE / "data/metrics.json", metrics)
    print(metrics["all"])
    print("new", metrics["new_hash"])
    print("C fresh", metrics["complementary_unexamined_subset"])


if __name__ == "__main__":
    main()
