"""Contrôle des règles V2 sur les seuls cas de développement connus."""

from common import HERE, PILOT, V1, jlines, read, rows, sources, write
from discover_v2 import predict
from fast_blocks import cache_nodes
from rules_v2 import role_blocks, segment


def main():
    ss = sources()
    for s in ss.values():
        cache_nodes(s)
    olddocs = rows(PILOT / "data/documents.jsonl")
    inv = rows(V1 / "data/candidates.jsonl")
    refs = read(PILOT / "data/reference.json")
    v1pred = rows(HERE / "data/development-v1-predictions.jsonl")
    predictions = []
    comparisons = []
    metrics = dict(gold=0, v1_exact=0, v2_exact=0, lost_previously_correct=0)
    for d in olddocs:
        s = ss[d["volume"]]
        c = next(
            c
            for c in inv
            if c["classification"] == "document_candidate"
            and c["volume"] == d["volume"]
            and c["start"] == d["source_text_start"]
        )
        ps = segment(s, role_blocks(s, c))
        predictions.extend(dict(u, document_key=d["key"], volume=d["volume"]) for u in ps)
        oldpairs = {(u["start"], u["end"]) for u in v1pred if u["document_key"] == d["key"]}
        newpairs = {(u["start"], u["end"]) for u in ps}
        for w in refs:
            if w["document_id"] != d["id"] or w["certainty"] != "A":
                continue
            for g in w["units"]:
                pair = (g["start"], g["end"])
                a = pair in oldpairs
                b = pair in newpairs
                metrics["gold"] += 1
                metrics["v1_exact"] += a
                metrics["v2_exact"] += b
                metrics["lost_previously_correct"] += a and not b
                comparisons.append(
                    dict(
                        document_key=d["key"],
                        start=g["start"],
                        end=g["end"],
                        v1_exact=a,
                        v2_exact=b,
                    )
                )
    allowed = {(d["volume"], xp) for d in olddocs for xp in d["divisions"]}
    known_refs = rows(V1 / "data/reference-documents.jsonl")
    known_selection = {c["id"]: c for c in rows(V1 / "data/selection.jsonl")}
    allowed |= {(r["volume"], r["source_xpath"]) for r in known_refs}
    allowed |= {
        (w["volume"], w["xpaths"][0].rsplit("/p", 1)[0])
        for w in rows(V1 / "data/non-detection-windows.jsonl")
    }
    allowed.add((5, "/TEI.2/text/body/div1/div2[1]/div3[3]"))
    dp = predict(ss, allowed)
    checks = []
    for ref in known_refs:
        c = known_selection[ref["candidate_id"]]
        r = next((r for r in dp if r["id"] == c["id"]), None)
        checks.append(
            dict(
                candidate_id=c["id"],
                expected_real=ref["real"],
                classification=r["classification"] if r else None,
                subtype=r["subtype"] if r else None,
                start=r["start"] if r else None,
                end=r["end"] if r else None,
                reason=ref["reason"],
            )
        )
    pec = next(
        r
        for r in dp
        if r["volume"] == 5 and r["xpath"].endswith("/div2[1]/div3[3]") and not r["internal"]
    )
    pp = segment(ss[5], role_blocks(ss[5], pec))
    assert len(pp) == 38
    assert len(pp[36]["xml_blocks"]) == 2
    write(
        HERE / "data/development-metrics.json",
        dict(
            segmentation=metrics,
            parent_cases=checks,
            pecqueuse_articles=38,
            scope="development only; all previously inspected documents, never validation",
        ),
    )
    jlines(HERE / "data/development-v2-predictions.jsonl", predictions)
    jlines(HERE / "data/development-pair-comparison.jsonl", comparisons)
    jlines(HERE / "data/development-document-predictions.jsonl", dp)
    print(metrics)
    for c in checks:
        print(c["candidate_id"], c["expected_real"], c["classification"], c["subtype"])


if __name__ == "__main__":
    main()
