"""Affiche les éléments source pour contrôle; ne produit aucune annotation automatique."""

import sys

from lib import HERE, compact, rows, sources


def main():
    ss = sources()
    rr = {r["persee_id"]: r for r in rows(HERE / "data/registry-automatic.jsonl")}
    if len(sys.argv) > 1 and sys.argv[1] == "zones":
        for z in rows(HERE / "data/validation-zones.jsonl"):
            if len(sys.argv) > 2 and z["volume"] != int(sys.argv[2]):
                continue
            s = ss[z["volume"]]
            print("\nZONE", z["id"], z["xpaths"], z["start"], z["end"])
            print(s.text[z["start"] : z["end"]])
        return
    lo = int(sys.argv[1])
    hi = int(sys.argv[2])
    for sample in rows(HERE / "data/validation-sample.jsonl"):
        if not lo <= sample["index"] <= hi:
            continue
        r = rr[sample["persee_id"]]
        m = r["metadata"]
        s = ss[m["volume"]]
        b = r["boundaries"]["proposal"]
        print(
            "\n#",
            sample["index"],
            m["id"].split("_")[-1],
            "V",
            m["volume"],
            m["title"],
            m["page_start"],
            m["page_end"],
            r["alignment_status"],
            r["document_kind"],
        )
        print("B", b)
        for i, c in enumerate(r["candidates"][:3]):
            n = s.node(c["xpath"])
            ps = n.findall("p")
            print("C", i, c["anchor_xpath"], c["score"], c["title"][:350])
            print("OPEN", " | ".join(compact(p)[:340] for p in ps[:3]))
            print("CLOSE", " | ".join(compact(p)[-310:] for p in ps[-2:]))
            if i == 0:
                if b:
                    print(
                        "PROPOSED END:",
                        compact_text(s.text[max(b["start"], b["end"] - 1000) : b["end"]]),
                        "AFTER:",
                        compact_text(s.text[b["end"] : b["end"] + 600]),
                    )
                print(
                    "SHORT RUBRICS",
                    [
                        (j + 1, compact(p)[:210])
                        for j, p in enumerate(ps)
                        if len(compact(p)) < 160 and (j > 1)
                    ][:30],
                )
                prev = n.getprevious()
                nxt = n.getnext()
                print(
                    "PREV",
                    compact(prev)[-300:] if prev is not None else None,
                    "NEXT",
                    compact(nxt)[:350] if nxt is not None else None,
                )


def compact_text(t):
    return " ".join(t.split())


if __name__ == "__main__":
    main()
