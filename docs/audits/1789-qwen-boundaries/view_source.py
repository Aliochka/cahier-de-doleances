"""Inspection de référence : texte source seulement, jamais sorties Qwen ni proposition A."""

import re
import sys

from qcommon import HERE, rows

for w in rows(HERE / "data/windows.jsonl"):
    if w["split"] != sys.argv[1] or not int(sys.argv[2]) <= int(w["id"].split("-")[-1]) <= int(
        sys.argv[3]
    ):
        continue
    print(
        "\n###",
        w["id"],
        w["persee_id"].split("_")[-1],
        w["title"],
        w["pages"],
        "OMISSIONS",
        [(x["omitted_blocks"], x["start"], x["end"]) for x in w["omissions"]],
    )
    for b in w["blocks"]:
        if b["tag"] == "pb":
            print(b["id"], "PAGE", b["pb"])
            continue
        t = " ".join(b["text"].split())
        iskey = b["tag"] in {"head", "note"} or re.match(
            r"^(?:CAHIER|POUVOIRS|DOLÉANCES|INSTRUCTIONS|MÉMOIRE|PROCÈS|De |Des |Du |Ce |Sign|Collation|Paraph|Certifi|Fait|Clos|Arrêt|ANNEXE|SUPPL|S[EÉ]CONDE PARTIE|PREMI[EÈ]RE PARTIE)",
            t,
        )
        if iskey or len(t) < 150:
            print(b["id"], b["tag"], b["page"], b["xpath"].split("/")[-1], t[:260])
        if re.search(r"Sign[eé]|collationn|ne varietur|Fait et arr[eê]t", t, re.I):
            print(b["id"], "TAIL", t[-400:])
