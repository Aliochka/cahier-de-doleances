import re
import sys

from lib import HERE, compact, rows, sources

ss = sources()
rr = {r["persee_id"]: r for r in rows(HERE / "data/registry-automatic.jsonl")}
for t in rows(HERE / "data/validation-sample.jsonl"):
    if not int(sys.argv[1]) <= t["index"] <= int(sys.argv[2]):
        continue
    r = rr[t["persee_id"]]
    s = ss[t["volume"]]
    m = r["metadata"]
    b = r["boundaries"]["proposal"]
    print(
        "\n#",
        t["index"],
        m["id"].split("_")[-1],
        t["volume"],
        m["title"],
        m["page_start"],
        m["page_end"],
        r["alignment_status"],
    )
    for i, c in enumerate(r["candidates"][:2]):
        n = s.node(c["xpath"])
        ps = n.findall("p")
        print("C", i, c["anchor_xpath"], c["title"][:210])
        if i == 0:
            print("O", " | ".join(compact(p)[:190] for p in ps[:3]))
            print("E", " | ".join(compact(p)[-220:] for p in ps[-2:]))
            print(
                "T",
                [
                    (j + 1, compact(p)[:130])
                    for j, p in enumerate(ps)
                    if re.match(
                        r"^(CAHIER|POUVOIRS|INSTRUCTIONS|PROCÈS|PROCES|DÉLIBÉRATION|DÉCLARATION|SUPPLÉMENT)",
                        compact(p),
                    )
                ],
            )
            print("B", None if not b else (b["start"], b["end"], b["end_page"], b["flags"]))
            print("AFTER", " ".join(s.text[b["end"] : b["end"] + 240].split()) if b else "")
