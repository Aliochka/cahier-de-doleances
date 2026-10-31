"""Contrôles de développement supplémentaires, explicitement hors validation nouvelle."""

from common import HERE, PILOT, V1, jlines, rows, sources, write
from fast_blocks import blocks, cache_nodes
from rules import segment as seg1
from rules_v2 import role_blocks, segment


def main():
    ss = sources()
    for s in ss.values():
        cache_nodes(s)
    inv = {c["id"]: c for c in rows(V1 / "data/candidates.jsonl")}
    refs = rows(V1 / "data/reference-documents.jsonl")
    metrics = {}
    comparisons = []
    for ver, fn, bfn in [("v1", seg1, blocks), ("v2", segment, role_blocks)]:
        count = exact = 0
        for r in refs:
            if not r["real"]:
                continue
            c = inv[r["candidate_id"]]
            pred = fn(ss[r["volume"]], bfn(ss[r["volume"]], c))
            pairs = {(u["start"], u["end"]) for u in pred}
            for w in r["reference_windows"]:
                for g in w["units"]:
                    ok = (g["start"], g["end"]) in pairs
                    count += 1
                    exact += ok
                    comparisons.append(
                        dict(
                            version=ver,
                            candidate_id=c["id"],
                            start=g["start"],
                            end=g["end"],
                            exact=ok,
                        )
                    )
        metrics[ver] = dict(reference_units=count, exact=exact, development_not_generalization=True)
    lookup = {
        (r["volume"], r["anchor_xpath"]): r
        for r in rows(HERE / "data/v2-document-predictions.jsonl")
    }
    parentchecks = []
    for d in rows(PILOT / "data/documents.jsonl"):
        r = lookup.get((d["volume"], d["divisions"][0]))
        parentchecks.append(
            dict(
                legacy_id=d["id"],
                key=d["key"],
                v2_class=r["classification"] if r else None,
                v2_divisions=r["divisions"] if r else [],
                expected_divisions=d["divisions"],
                autonomous_admitted=bool(r and r["classification"] == "autonomous"),
                bounds_match=bool(
                    r and (r["start"], r["end"]) == (d["source_text_start"], d["source_text_end"])
                ),
            )
        )
    jlines(HERE / "data/development-extra-article-comparison.jsonl", comparisons)
    jlines(HERE / "data/development-parent-regressions.jsonl", parentchecks)
    write(
        HERE / "data/development-extra-metrics.json",
        dict(
            articles=metrics,
            pilot_parents=len(parentchecks),
            autonomous_admitted=sum(r["autonomous_admitted"] for r in parentchecks),
            bounds_match=sum(r["bounds_match"] for r in parentchecks),
        ),
    )
    print(metrics)


if __name__ == "__main__":
    main()
