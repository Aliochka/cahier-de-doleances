"""Recherche documentaire après gel, sans changement des règles ni des prédictions."""

import re

from lib import HERE, base, compact, fold, rows, sources

ss = sources()
rr = {r["persee_id"]: r for r in rows(HERE / "data/registry-automatic.jsonl")}
terms = {
    10: r"bassigny",
    18: r"massugas",
    21: r"cahier|tiers",
    25: r"cahier|noblesse",
    28: r"agneau",
    41: r"lauzet",
    49: r"uzent|usent",
    54: r"fourque",
    56: r"gif\b",
    60: r"maroll|marott",
    73: r"pontivy",
    76: r"cahier|instructions",
    89: r"greasqu|greasque",
}
for t in rows(HERE / "data/validation-sample.jsonl"):
    if t["index"] not in terms:
        continue
    r = rr[t["persee_id"]]
    s = ss[t["volume"]]
    _, at = base.page_index(s)
    m = r["metadata"]
    print("\n#", t["index"], m["title"])
    found = []
    for n in s.tree.xpath("//text/body//p | //text/body//head"):
        a, b = s.span(n)
        page = at(a)["page"]
        if page is None or not m["page_start"] - 2 <= page <= m["page_end"] + 1:
            continue
        txt = compact(n)
        if re.search(terms[t["index"]], fold(txt)) and (
            len(txt) < 750 or t["index"] not in {21, 25, 76}
        ):
            found.append((s.tree.getpath(n), a, page, txt[:480]))
    for f in found[:12]:
        print(f)
