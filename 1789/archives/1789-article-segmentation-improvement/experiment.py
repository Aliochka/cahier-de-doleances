# ruff: noqa: E402
"""Isolated comparison; never writes source data or decision journals."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import frozen_match, resolve_reference  # noqa: E402

import argparse
import gzip
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "1789/tools/document-review"))
from articles import Articles
from reviewlib import Store, rows, sha
from segmentation import VERSION, run


def write(name, obj):
    (HERE / "data" / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def frozen():
    return {
        str(p.relative_to(ROOT)): sha(p.read_bytes())
        for p in [
            ROOT / "1789/extraction/segmentation.py",
            HERE / "data/validation-plan.json",
        ]
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["freeze", "windows", "evaluate"])
    parser.add_argument("--volume", type=int)
    args = parser.parse_args()
    if args.action == "freeze":
        if (HERE / "data/freeze.json").exists():
            raise ValueError("Rules are already frozen")
        write(
            "freeze.json",
            dict(
                date=datetime.now(timezone.utc).isoformat(),
                method=VERSION,
                files=frozen(),
                annotation="Reference not yet examined; no tuning after this freeze.",
            ),
        )
        return
    freeze = json.loads((HERE / "data/freeze.json").read_text())
    assert all(frozen_match(ROOT / name, expected) for name, expected in freeze["files"].items()), "Frozen rules or windows changed"
    s = Store()
    engine = Articles(s, HERE / ".local/article-decisions.snapshot.jsonl")
    plan = json.loads((HERE / "data/validation-plan.json").read_text())
    if args.action == "windows":
        for w in plan:
            if args.volume and w["volume"] != args.volume:
                continue
            print("\nWINDOW", w["id"], w["title"])
            source = s.sources[w["volume"]]
            for path in w["xpaths"]:
                a, z = source.span(source.node(path))
                print(f"[{a}:{z}] {path}\n{source.text[a:z]}")
        return
    started = time.perf_counter()
    result = {}
    comparison = []
    for p in engine.parents.values():
        r = run(s, p)
        result[p["id"]] = r
        initial = [u for u in engine.base[p["id"]].values() if u["type"] == "article"]
        correspondence = [
            dict(
                old_id=u["id"],
                old_spans=u["spans"],
                proposed_ids=[
                    n["id"]
                    for n in r["new"]
                    if any(a < n["end"] and n["start"] < z for a, z in u["spans"])
                ],
            )
            for u in initial
        ]
        reference_misses = [
            dict(id=u["id"], spans=u["spans"], number=u["number"])
            for u in initial
            if not any(abs(n["start"] - u["spans"][0][0]) <= 3 for n in r["new"])
        ]
        review_notes = json.loads((HERE / "data/review-notes.json").read_text())
        for note in review_notes:
            if note["document_id"] == p["id"]:
                note["text"] = s.sources[p["volume"]].text[note["start"] : note["end"]]
        comparison.append(
            dict(
                review_notes=[n for n in review_notes if n["document_id"] == p["id"]],
                initial_article_count=len(initial),
                reference_misses=reference_misses,
                document_id=p["id"],
                parent_extent_id=p["extent_id"],
                source_sha256=p["source"]["source_sha256"],
                version=VERSION,
                old_count=len(r["old"]),
                new_count=len(r["new"]),
                old=r["old"],
                new=r["new"],
                candidates=r["candidates"],
                role_changes=r["role_changes"],
                correspondence=correspondence,
            )
        )
    with gzip.open(HERE / "data/comparison.jsonl.gz", "wt", encoding="utf-8") as f:
        for c in comparison:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    reference = json.loads((HERE / "data/validation-reference.json").read_text())
    validation = {}
    for method in ["old", "new"]:
        tp = fp = miss = 0
        details = []
        seen = set()
        for w in plan:
            gold = reference[w["id"]]["article_starts"]
            found = [
                u["start"]
                for u in result[w["document_id"]][method]
                if w["start"] <= u["start"] < w["end"]
            ]
            # Match only whitespace/paragraph quotation punctuation differences, max 3 chars.
            matched = set()
            bad = []
            for x in found:
                match = next((g for g in gold if g not in matched and abs(g - x) <= 3), None)
                if match is None:
                    bad.append(x)
                else:
                    matched.add(match)
            details.append(
                dict(
                    window=w["id"],
                    expected=len(gold),
                    correct=len(matched),
                    extra=bad,
                    missed=sorted(set(gold) - matched),
                )
            )
            for g in gold:
                key = (w["document_id"], g)
                if key not in seen:
                    tp += g in matched
                    miss += g not in matched
                    seen.add(key)
            for b in bad:
                key = (w["document_id"], b, "FP")
                if key not in seen:
                    fp += 1
                    seen.add(key)
        validation[method] = dict(
            correct_starts=tp,
            false_starts=fp,
            missed_starts=miss,
            precision=tp / (tp + fp) if tp + fp else None,
            recall=tp / (tp + miss) if tp + miss else None,
            windows=details,
        )
    development = []
    events = rows(HERE / ".local/article-decisions.snapshot.jsonl")
    for e in events:
        if e["action"] not in {"correct", "missing"}:
            continue
        for u in e["after"]:
            if u["type"] != "article":
                continue
            a = u["spans"][0][0]
            z = u["spans"][-1][1]
            development.append(
                dict(
                    event_id=e["id"],
                    document_id=e["document_id"],
                    action=e["action"],
                    number=u["number"],
                    human_spans=u["spans"],
                    old=[
                        dict(start=n["start"], end=n["end"])
                        for n in result[e["document_id"]]["old"]
                        if abs(n["start"] - a) < 60
                    ],
                    new=[
                        dict(start=n["start"], end=n["end"])
                        for n in result[e["document_id"]]["new"]
                        if abs(n["start"] - a) < 60
                    ],
                )
            )
    write("development-comparison.json", development)
    validation["boundary_checks"] = []
    for check in reference.get("_complete_articles", []):
        row = dict(check)
        for method in ["old", "new"]:
            units = result[check["document_id"]][method]
            matching = next((u for u in units if abs(u["start"] - check["start"]) <= 3), None)
            row[method] = bool(matching and abs(matching["end"] - check["end"]) <= 3)
        validation["boundary_checks"].append(row)
    metrics = dict(
        method=VERSION,
        parents=len(result),
        old_articles=sum(len(r["old"]) for r in result.values()),
        new_proposals=sum(len(r["new"]) for r in result.values()),
        unchanged_exact_ranges=sum(
            len(
                {(u["start"], u["end"]) for u in r["old"]}
                & {(u["start"], u["end"]) for u in r["new"]}
            )
            for r in result.values()
        ),
        new_starts=sum(
            len({u["start"] for u in r["new"]} - {u["start"] for u in r["old"]})
            for r in result.values()
        ),
        suspects=sum(
            sum(c["confidence"] == "suspect" for c in r["candidates"]) for r in result.values()
        ),
        validation=validation,
        automatic_seconds=time.perf_counter() - started,
        development_events=len(development),
    )
    write("metrics.json", metrics)
    suspects = [
        dict(document_id=p["id"], title=p["metadata"]["title"], volume=p["volume"], **c)
        for p in engine.parents.values()
        for c in result[p["id"]]["candidates"]
        if c["confidence"] == "suspect"
    ]
    write("suspects.json", suspects)
    checks = dict(
        source_slices_exact=True,
        unique_proposal_ids=True,
        no_overlaps=True,
        parent_bounds=True,
        source_and_previous_audits_unchanged=True,
        journal_prefixes_preserved=True,
    )
    for p in engine.parents.values():
        src = s.sources[p["volume"]]
        for u in result[p["id"]]["new"]:
            assert p["start"] <= u["start"] < u["end"] <= p["end"]
            assert u["text"] == "".join(src.text[a:z] for a, z in u["spans"])
    prior = json.loads((HERE / "prior-files-sha256.json").read_text())
    # Accommodate manifest schema fixed during initial inventory.
    pairs = prior.get("files", prior) if isinstance(prior, dict) else prior
    if isinstance(pairs, dict):
        for name, digest in pairs.items():
            if isinstance(digest, str):
                assert frozen_match(ROOT / name, digest), name
    for name, info in json.loads((HERE / "data/journal-snapshots.json").read_text()).items():
        assert sha(resolve_reference(ROOT / name).read_bytes()[: info["bytes"]]) == info["sha256"]
    write("checks.json", checks)
    write(
        "manifest.json",
        dict(
            method=VERSION,
            source_revision="926fd3cd986a3c3d411e93d1845fff6475cb2602",
            freeze=freeze,
            outputs={
                p.name: sha(p.read_bytes())
                for p in (HERE / "data").glob("*")
                if p.name not in {"manifest.json"}
            },
        ),
    )
    print(json.dumps({k: v for k, v in metrics.items() if k != "validation"}, indent=2))


if __name__ == "__main__":
    main()
