"""Retrouve les19 références non reproduites et les confronte aux deux sorties brutes."""

from common import HERE, PILOT, V1, jlines, read, rows, sources, write
from fast_blocks import blocks, cache_nodes
from rules import segment


def main():
    ss = sources()
    for s in ss.values():
        cache_nodes(s)
    docs = rows(PILOT / "data/documents.jsonl")
    inv = rows(V1 / "data/candidates.jsonl")
    refs = read(PILOT / "data/reference.json")
    oldraw = rows(PILOT / "data/automatic-predictions.jsonl")
    legacy = rows(PILOT / "data/units.jsonl")
    differences = []
    allpred = []
    correct = 0
    total = 0
    for d in docs:
        s = ss[d["volume"]]
        c = next(
            c
            for c in inv
            if c["classification"] == "document_candidate"
            and c["volume"] == d["volume"]
            and c["start"] == d["source_text_start"]
        )
        predictions = segment(s, blocks(s, c))
        allpred.extend(dict(u, document_key=d["key"], volume=d["volume"]) for u in predictions)
        for w in refs:
            if w["document_id"] != d["id"] or w["certainty"] != "A":
                continue
            pairs = {(u["start"], u["end"]) for u in predictions}
            for g in w["units"]:
                total += 1
                if (g["start"], g["end"]) in pairs:
                    correct += 1
                    continue
                oldmatch = [
                    u
                    for u in oldraw
                    if u["document_id"] == d["id"]
                    and (u["start"], u["end"]) == (g["start"], g["end"])
                ]
                overlaps = [
                    u for u in predictions if u["start"] < g["end"] and u["end"] > g["start"]
                ]
                older = [
                    u
                    for u in oldraw
                    if u["document_id"] == d["id"]
                    and u["start"] < g["end"]
                    and u["end"] > g["start"]
                ]
                uid = next(
                    u["id"]
                    for u in legacy
                    if u["document_id"] == d["id"]
                    and u["start"] == g["start"]
                    and u["end"] == g["end"]
                )
                a = min([g["start"]] + [u["start"] for u in overlaps])
                b = max([g["end"]] + [u["end"] for u in overlaps])
                differences.append(
                    dict(
                        index=len(differences) + 1,
                        document_key=d["key"],
                        document_id=d["id"],
                        legacy_unit_id=uid,
                        volume=d["volume"],
                        reference=g,
                        reference_text=s.text[g["start"] : g["end"]],
                        v1_predictions=[
                            dict(u, text=s.text[u["start"] : u["end"]]) for u in overlaps
                        ],
                        pilot_raw_predictions=[
                            dict(u, text=s.text[u["start"] : u["end"]]) for u in older
                        ],
                        pilot_raw_was_exact=bool(oldmatch),
                        source_context_start=a,
                        source_context_end=b,
                        source_context=s.text[a:b],
                        source_sha256=s.sha256,
                    )
                )
    assert (correct, total, len(differences)) == (250, 269, 19)
    jlines(HERE / "data/segmentation-differences-19.jsonl", differences)
    jlines(HERE / "data/development-v1-predictions.jsonl", allpred)
    write(
        HERE / "data/difference-summary.json",
        dict(
            reference_units=269,
            v1_exact=250,
            differences=19,
            new_regressions_vs_pilot_raw=sum(r["pilot_raw_was_exact"] for r in differences),
            persistent_mismatches=sum(not r["pilot_raw_was_exact"] for r in differences),
        ),
    )
    for r in differences:
        print(
            "\n",
            r["index"],
            r["document_key"],
            "OLDRAWEXACT",
            r["pilot_raw_was_exact"],
            "REF",
            r["reference"]["start"],
            r["reference"]["end"],
            "XML",
            r["reference"]["xml_blocks"],
        )
        print("REFERENCE", " ".join(r["reference_text"].split()))
        for u in r["v1_predictions"]:
            print(
                "V1",
                u["start"],
                u["end"],
                "PREFIX",
                repr(u["text"][:180]),
                "TAIL",
                repr(u["text"][-220:]),
            )
            a, b = u["start"], u["end"]
            ga, gb = r["reference"]["start"], r["reference"]["end"]
            s = ss[r["volume"]]
            if a < ga:
                print("EXTRA_BEFORE", " ".join(s.text[a:ga].split())[:700])
            if b > gb:
                print("EXTRA_AFTER", " ".join(s.text[gb:b].split())[:900])
    print(read(HERE / "data/difference-summary.json"))


if __name__ == "__main__":
    main()
