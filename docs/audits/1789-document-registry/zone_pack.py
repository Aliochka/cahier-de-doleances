import sys

from lib import HERE, compact, rows, sources

ss = sources()
for z in rows(HERE / "data/validation-zones.jsonl"):
    if not int(sys.argv[1]) <= z["volume"] <= int(sys.argv[2]):
        continue
    s = ss[z["volume"]]
    print("\nZONE", z["id"], z["start"], z["end"])
    for path in z["xpaths"]:
        n = s.node(path)
        print("PATH", path)
        for child in n:
            print(s.tree.getpath(child).split("/")[-1], repr(s.span(child)), compact(child))
