"""Inspection locale reproductible, paragraphes numérotés sans modifier la source."""

import argparse

from common import compact, load_sources, read

parser = argparse.ArgumentParser()
parser.add_argument("sources")
parser.add_argument("key")
parser.add_argument("--length", type=int, default=200)
parser.add_argument("--first", type=int, default=1)
parser.add_argument("--last", type=int, default=10000)
args = parser.parse_args()
entry = next(d for d in read("decisions.json")["documents"] if d["key"] == args.key)
source = load_sources(args.sources)[entry["volume"]]
for xp in entry["divisions"]:
    d = source.node(xp)
    print("DIVISION", xp)
    print("TITRE", " | ".join(compact(h) for h in d.findall("head")))
    ps = d.findall("p")
    for i, p in enumerate(ps, 1):
        if args.first <= i <= args.last:
            print(f"p{i}: {compact(p)[: args.length]}")
    previous = d.xpath("preceding-sibling::div3[1]")
    following = d.xpath("following-sibling::div3[1]")
    print(
        "AVANT",
        " | ".join(compact(h) for h in previous[0].findall("head"))[:300]
        if previous
        else "début div2",
    )
    print(
        "APRÈS",
        " | ".join(compact(h) for h in following[0].findall("head"))[:300]
        if following
        else "fin div2",
    )
