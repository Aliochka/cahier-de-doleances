"""Materialize the non-human whitespace classification overlay without re-extraction."""

import json
import os
import platform
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "tools/document-review"))
from articles import Articles, canonical  # noqa: E402
from collection import discover  # noqa: E402
from production import dump, jsonl  # noqa: E402
from reviewlib import Store, rows, sha  # noqa: E402


def main():
    store = Store()
    directory = discover()
    if directory is None:
        raise ValueError("No active corpus")
    store.automatic_corrections = {
        r["document_id"]: r for r in rows(directory / "boundary-resolutions.jsonl.gz")
    }
    engine = Articles(store, directory=directory)
    inputs = [
        Path(__file__).resolve(),
        BASE / "tools/document-review/articles.py",
        store.journal,
        engine.log.journal,
    ]
    inputs += [source.path for source in store.sources.values()]
    inputs += [
        directory / n
        for n in [
            "parents.jsonl.gz",
            "units-A.jsonl.gz",
            "units-B.jsonl.gz",
            "units-C.jsonl.gz",
            "complete.json",
        ]
    ]
    override = engine.override_directory / "rebuilds.jsonl"
    if override.exists():
        inputs.append(override)
        inputs.extend(engine.override_directory / r["artifact"] for r in rows(override))
    hashes = {str(p.relative_to(BASE.parent)): sha(p.read_bytes()) for p in inputs}
    events = engine.log.history()
    by_volume = defaultdict(Counter)
    records = []
    human_count = 0
    for key, p in engine.parents.items():
        _, own, _, _, stale = engine.state(key, events)
        engine.check(p, list(own.values()))
        for r in own.values():
            human_count += r["review_status"] in {"human_validated", "human_corrected"}
            if r["type"] != "technical_passage":
                continue
            count = by_volume[str(p["volume"])]
            count["C_total"] += 1
            text = engine.text(p, r)
            if not text.isspace():
                continue
            count["whitespace_C"] += 1
            if not engine.automatic_whitespace(p, r):
                count["protected_by_prior_decision"] += 1
                continue
            count["automatically_classified"] += 1
            records.append(
                dict(
                    unit_id=r["id"],
                    parent_id=key,
                    parent_extent_id=p["extent_id"],
                    volume=p["volume"],
                    original_type="technical_passage",
                    effective_type="paratext",
                    subtype="technical_whitespace",
                    classification_origin="deterministic_rule",
                    classification_version="unicode-whitespace-1",
                    validation_status="automatic_technical_paratext",
                    human_validated=False,
                    requires_human_classification=False,
                    indexing_eligible=False,
                    publication_ready=False,
                    text=text,
                    text_sha256=sha(text),
                    spans=r["spans"],
                    source=p["source"],
                    parent_spans=[[a - p["start"], z - p["start"]] for a, z in r["spans"]],
                    pages=store.sources[p["volume"]].pages_for(r["spans"][0][0], r["spans"][-1][1]),
                    origin_ids=r["origin_ids"],
                    prior_event_id=r.get("last_event_id"),
                    original_review_status=r["review_status"],
                )
            )
    totals = Counter()
    for counts in by_volume.values():
        totals.update(counts)
    for field in [
        "C_total",
        "whitespace_C",
        "automatically_classified",
        "protected_by_prior_decision",
    ]:
        totals.setdefault(field, 0)
        for counts in by_volume.values():
            counts.setdefault(field, 0)
    summary = dict(
        version="unicode-whitespace-1",
        python_version=platform.python_version(),
        unicode_version=unicodedata.unidata_version,
        generation=directory.name,
        totals=dict(totals),
        by_volume={v: dict(c) for v, c in sorted(by_volume.items())},
        parent_count=len(engine.parents),
        article_journal_events=len(events),
        human_reviewed_units_unchanged=human_count,
        rule="Python str.isspace(): nonempty, every source character whitespace; no strip, no punctuation rule, no zero-width-space/BOM rule",
        human_decisions_created=0,
        source_text_or_ranges_changed=False,
        raw_generations_and_journals_unchanged=True,
        inputs_sha256=hashes,
    )
    fingerprint = sha(canonical(hashes))
    root = BASE / "data/technical-paratext"
    out = root / ("whitespace-" + fingerprint[:12])
    records.sort(key=lambda r: (r["volume"], r["parent_id"], r["spans"][0][0], r["unit_id"]))
    if out.exists():
        assert rows(out / "classifications.jsonl.gz") == records
    else:
        out.mkdir(parents=True)
        jsonl(out / "classifications.jsonl.gz", records)
        dump(out / "summary.json", summary)
        dump(
            out / "complete.json",
            dict(
                files={
                    n: sha((out / n).read_bytes())
                    for n in ["classifications.jsonl.gz", "summary.json"]
                }
            ),
        )
    assert all(sha((BASE.parent / p).read_bytes()) == digest for p, digest in hashes.items())
    temp = root / "current.tmp"
    dump(temp, dict(directory=str(out.relative_to(BASE)), version="unicode-whitespace-1"))
    os.replace(temp, root / "current.json")
    public_summary = {k: v for k, v in summary.items() if k != "inputs_sha256"}
    dump(BASE / "docs/whitespace-summary.json", public_summary)
    print(json.dumps(public_summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
