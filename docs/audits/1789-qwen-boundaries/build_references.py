"""Référence exploratoire écrite avant toute inférence de validation."""

import re
from datetime import datetime, timezone

from qcommon import HERE, jlines, read, rows, save, sha


def main():
    decisions = read(HERE / "reference_decisions.json")
    windows = {w["id"]: w for w in rows(HERE / "data/windows.jsonl")}
    old = read(HERE / "data/preparation.json")["prior_review_exclusions"]
    out = []
    assert not (HERE / "data/validation-outputs.jsonl").exists(), (
        "Reference cannot be built after viewing model validation outputs"
    )
    for key, d in sorted(decisions.items()):
        w = windows[key]
        blocks = {b["id"]: b for b in w["blocks"]}
        a, b = blocks[d["start_id"]], blocks[d["end_id"]]
        assert a["start"] <= b["start"]
        path = re.sub(r"/(?:p|head|note|list)(?:\[.*)?$", "", a["xpath"])
        novel = path not in old[str(w["volume"])]
        out.append(
            dict(
                window_id=key,
                persee_id=w["persee_id"],
                volume=w["volume"],
                title=w["title"],
                **d,
                start=a["start"],
                end=b["end"],
                start_xpath=a["xpath"],
                end_xpath=b["xpath"],
                source_sha256=w["source"]["source_sha256"],
                novel_source_leaf=novel,
                evidence={"opening": a["text"], "closing": b["text"]},
                scope="first/last XML content blocks and adjoining source transitions examined; omitted middle not collated; no facsimile verification",
                reviewer="Codex exploratory documentary reference; before Qwen validation inference; not independent human",
            )
        )
    assert len(out) == 36
    jlines(HERE / "data/reference-validation.jsonl", out)
    freeze = read(HERE / "data/freeze.json")
    freeze["reference_frozen_at_utc"] = datetime.now(timezone.utc).isoformat()
    freeze["files"]["reference_decisions.json"] = sha(
        (HERE / "reference_decisions.json").read_bytes()
    )
    freeze["files"]["data/reference-validation.jsonl"] = sha(
        (HERE / "data/reference-validation.jsonl").read_bytes()
    )
    save(HERE / "data/freeze.json", freeze)
    print(
        "Frozen references",
        len(out),
        "novel source leaves",
        sum(r["novel_source_leaf"] for r in out),
    )
    print("Prior root overlaps", [r["window_id"] for r in out if not r["novel_source_leaf"]])


if __name__ == "__main__":
    main()
