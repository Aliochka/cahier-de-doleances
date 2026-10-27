"""Ouvertures/transitions/clôtures source, sans A ni Qwen; extraits d'inspection signalés."""

import re
import sys

from qcommon import HERE, rows

for w in rows(HERE / "data/windows.jsonl"):
    if w["split"] != sys.argv[1] or not int(sys.argv[2]) <= int(w["id"].split("-")[-1]) <= int(
        sys.argv[3]
    ):
        continue
    print("\n#", w["id"], w["persee_id"].split("_")[-1], w["title"], w["pages"])
    bs = w["blocks"]
    display = set()
    tails = set()
    for i, b in enumerate(bs):
        t = " ".join(b["text"].split())
        if b["tag"] == "head" or (
            len(t) < 600
            and re.match(
                r"^(?:CAHIER|POUVOIRS|DOLÉANCES|INSTRUCTIONS|MÉMOIRE|PROCÈS|ANNEXE|SUPPLÉMENT)", t
            )
        ):
            display.update(range(max(0, i - 2), min(len(bs), i + 3)))
        if b["tag"] != "pb" and re.search(
            r"(?:^Sign[eé]|[,.] Sign[eé]|Collationn|[Pp]araph[eé]|[Ff]ait et arr[eê]t|[Cc]los et arr[eê]t|[Oo]nt sign[eé])",
            t,
        ):
            display.add(i)
            tails.add(i)
    for i in sorted(display):
        b = bs[i]
        if b["tag"] == "pb":
            print(b["id"], "PAGE", b["page"])
            continue
        t = " ".join(b["text"].split())
        print(b["id"], b["tag"], b["page"], t[:210] if i not in tails else t[-370:])
    print("GAPS", w["omissions"])
