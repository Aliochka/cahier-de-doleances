# ruff: noqa: E402
"""Verify exact source fidelity, journal isolation and previous-audit fingerprints."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import frozen_match, resolve_reference  # noqa: E402

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parents[1] / "tools/document-review"))
from articles import Articles  # noqa: E402
from reviewlib import Store, load, rows, sha  # noqa: E402


def main():
    store = Store()
    engine = Articles(store)
    units = rows(HERE / "data/units.jsonl.gz")
    summary = load(HERE / "data/summary.json")
    unchanged = 0
    for file, fingerprint in load(HERE / "prior-files-sha256.json").items():
        content = resolve_reference(ROOT / file).read_bytes()
        unchanged += sha(content) == fingerprint
        if resolve_reference(ROOT / file) == ROOT / "1789/data/private/document-review/decisions.jsonl":
            baseline = load(HERE / "data/input-manifest.json")["parent_journal_baseline"]
            assert (
                len(content) >= baseline["bytes"]
                and sha(content[: baseline["bytes"]]) == fingerprint
            ), "Parent journal was rewritten"
            store.history()  # Legitimate future appends are allowed; the full chain must validate.
        else:
            assert frozen_match(ROOT / file, fingerprint), ("Protected file changed", file)
    for name, fingerprint in load(HERE / "data/manifest.json").items():
        assert frozen_match(HERE / "data" / name, fingerprint), ("Export fingerprint", name)
    for unit in units:
        p = engine.parents[unit["parent_id"]]
        source = store.sources[p["volume"]]
        assert p["source"]["source_sha256"] == source.sha256
        assert p["start"] <= unit["start"] < unit["end"] <= p["end"]
        assert unit["text"] == "".join(source.text[a:z] for a, z in unit["spans"])
        assert unit["text"] == "".join(p["full_text"][a:z] for a, z in unit["parent_spans"])
        assert unit["text_sha256"] == sha(unit["text"])
        if unit["type"] in {"technical_passage", "paratext"}:
            assert not unit["indexing_eligible"]
        if not unit["parent_version"]["ready"]:
            assert not unit["indexing_eligible"] and not unit["publication_ready"]
    assert len(units) == len({u["id"] for u in units})
    for key, p in engine.parents.items():
        engine.check(p, [r for r in units if r["parent_id"] == key])
    _, current, _ = engine.export()
    assert summary == current, "Export stale relative to source/journals"
    checks = dict(
        ok=True,
        units=len(units),
        articles=sum(u["type"] == "article" for u in units),
        parents=len(engine.parents),
        exact_source_fidelity=True,
        no_overlap_or_text_loss=True,
        previous_files_unchanged=unchanged,
        parent_journal_unchanged=sha(store.journal.read_bytes())
        == load(HERE / "data/input-manifest.json")["parent_journal_baseline"]["sha256"],
        parent_journal_append_only=True,
        real_article_events=summary["article_journal_events"],
    )
    (HERE / "data/checks.json").write_text(json.dumps(checks, indent=2) + "\n")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
