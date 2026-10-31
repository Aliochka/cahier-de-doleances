"""Additional descriptive measurements; never changes frozen rules or references."""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / "1789/tools/document-review"))
from articles import Articles
from reviewlib import Store, rows, sha
from segmentation import trim

s = Store()
a = Articles(s, HERE / ".local/article-decisions.snapshot.jsonl")
results = {r["document_id"]: r for r in rows(HERE / "data/comparison.jsonl.gz")}
counts = dict(
    initial_articles=0,
    initial_ranges_preserved_exactly=0,
    initial_A=0,
    initial_A_preserved_exactly=0,
)
for p in a.parents.values():
    proposed = {(u["start"], u["end"]) for u in results[p["id"]]["new"]}
    for u in a.base[p["id"]].values():
        if u["type"] != "article":
            continue
        counts["initial_articles"] += 1
        same = (u["spans"][0][0], u["spans"][-1][1]) in proposed
        counts["initial_ranges_preserved_exactly"] += same
        if u["source_status"] == "A":
            counts["initial_A"] += 1
            counts["initial_A_preserved_exactly"] += same
unique = {}
for e in rows(HERE / ".local/article-decisions.snapshot.jsonl"):
    if e["action"] not in {"correct", "missing"}:
        continue
    for u in e["after"]:
        if u["type"] == "article":
            unique[(e["document_id"], tuple(tuple(span) for span in u["spans"]))] = u
measure = {m: dict(exact=0, whitespace_trimmed=0, total=len(unique)) for m in ["old", "new"]}
for (pid, spans), u in unique.items():
    p = a.parents[pid]
    src = s.sources[p["volume"]]
    gold = (spans[0][0], spans[-1][1])
    gt = trim(src.text, *gold)
    for m in ["old", "new"]:
        us = results[pid][m]
        measure[m]["exact"] += any((v["start"], v["end"]) == gold for v in us)
        measure[m]["whitespace_trimmed"] += any(
            trim(src.text, v["start"], v["end"]) == gt for v in us
        )
counts["human_correction_ranges"] = measure
path = HERE / "data/metrics.json"
metrics = json.loads(path.read_text())
metrics.update(counts)
path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(counts, indent=2))

# Summarizing changes only derived metrics; refresh the output manifest afterwards.
manifest_path = HERE / "data/manifest.json"
manifest = json.loads(manifest_path.read_text())
manifest["outputs"] = {
    p.name: sha(p.read_bytes()) for p in (HERE / "data").glob("*") if p.name != "manifest.json"
}
manifest["scripts"] = {
    str(p.relative_to(HERE.parents[2])): sha(p.read_bytes())
    for p in [
        *HERE.glob("*.py"),
        *(HERE.parents[2] / "1789/tools/document-review").glob("*.py"),
    ]
}
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
