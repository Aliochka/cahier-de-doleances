"""Complément V2 sans correction du détecteur ni ajustement de seuil: file de candidats."""

from auditlib import HERE, PREVIOUS, jlines, rows


def main():
    v2 = rows(PREVIOUS / "data/v2-document-predictions.jsonl")
    lookup = {(p["volume"], p["anchor_xpath"]): p for p in v2}
    result = []
    for r in rows(HERE / "data/alignment-predictions.jsonl"):
        if r["metadata_type"] != ["griev"]:
            result.append(
                dict(persee_id=r["persee_id"], status="excluded_non_griev", candidates=[])
            )
            continue
        if r["status"] == "strong_proposal":
            result.append(
                dict(
                    persee_id=r["persee_id"],
                    status="metadata_strong_proposal_not_verified",
                    candidates=[r["candidates"][0]],
                    boundary=r["boundary"],
                )
            )
            continue
        supported = []
        for c in r["candidates"]:
            p = lookup.get((r["volume"], c["anchor_xpath"]))
            if (
                p
                and p["classification"] in {"autonomous", "associated"}
                and r["metadata_pages"][0] <= c["page"] <= r["metadata_pages"][1]
            ):
                supported.append(
                    dict(
                        c,
                        v2_id=p["id"],
                        v2_class=p["classification"],
                        v2_boundary=dict(start=p["start"], end=p["end"], divisions=p["divisions"]),
                    )
                )
        status = (
            "V2_supported_single_requires_review"
            if len(supported) == 1
            else "ambiguous_V2_supported_queue"
            if supported
            else "unresolved_no_V2_support"
        )
        result.append(
            dict(
                persee_id=r["persee_id"],
                status=status,
                candidates=supported,
                boundary=supported[0]["v2_boundary"] if len(supported) == 1 else None,
            )
        )
    jlines(HERE / "data/complementary-predictions.jsonl", result)


if __name__ == "__main__":
    main()
