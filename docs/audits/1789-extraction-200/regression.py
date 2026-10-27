"""Contrôles de développement, hors mesure de généralisation."""

import re

from common import HERE, PILOT, read, rows, sources, write
from rules import blocks, segment


def main():
    ss = sources()
    prior = rows(PILOT / "data/documents.jsonl")
    inventory = rows(HERE / "data/candidates.jsonl")
    results = []
    for d in prior:
        found = [
            c
            for c in inventory
            if c["classification"] == "document_candidate"
            and c["volume"] == d["volume"]
            and c["start"] == d["source_text_start"]
        ]
        c = found[0] if found else None
        results.append(
            dict(
                key=d["key"],
                detected=bool(c),
                candidate_id=c["id"] if c else None,
                exact_boundary=bool(c and c["end"] == d["source_text_end"]),
                same_nonwhite_extent=bool(
                    c
                    and ss[d["volume"]].text[c["start"] : c["end"]].strip()
                    == d["full_text"].strip()
                ),
                grouped_divisions=c["divisions"] if c else [],
            )
        )
    c = next(
        c
        for c in inventory
        if c["volume"] == 5
        and c["xpath"].endswith("/div2[1]/div3[3]")
        and c["classification"] == "document_candidate"
    )
    ps = segment(ss[5], blocks(ss[5], c))
    nums = [p["label_exact"] for p in ps]
    assert len(ps) == 38, nums
    assert [int(re.search(r"\d+", label).group()) for label in nums] == list(range(1, 39))
    assert len(ps[36]["xml_blocks"]) == 2
    assert "valeur." in ss[5].text[ps[36]["start"] : ps[36]["end"]]
    assert "Au surplus" not in ss[5].text[ps[-1]["start"] : ps[-1]["end"]]
    negatives = []
    for n in read(PILOT / "negative-cases.json"):
        candidates = [
            r
            for r in inventory
            if r["volume"] == n["volume"]
            and r["anchor_xpath"] == n["xpath"]
            and not r.get("internal")
        ]
        assert candidates and all(r["classification"] != "document_candidate" for r in candidates)
        negatives.append(
            dict(
                key=n["key"],
                expected=n["kind"],
                observed=[r["classification"] for r in candidates],
                standalone_rejected=True,
            )
        )
    write(
        HERE / "data/development-regression.json",
        dict(
            pilot=results,
            pecqueuse=dict(
                candidate_id=c["id"],
                articles=38,
                article37_xml_blocks=ps[36]["xml_blocks"],
                development_only=True,
            ),
            inherited_negative_cases=negatives,
            scope="30 development parents and Pecqueuse; not a generalization estimate",
        ),
    )
    print(
        "Development parents detected", sum(x["detected"] for x in results), "/30; Pecqueuse38 OK"
    )


if __name__ == "__main__":
    main()
