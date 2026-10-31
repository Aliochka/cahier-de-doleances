"""Read-only preservation checks; writes only migration bookkeeping, never corpus data."""

import ast
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASE = REPO / "1789"
sys.path.insert(0, str(BASE))
from cahier1789_paths import resolve_reference  # noqa: E402

CODE = {".py", ".md", ".cjs", ".js", ".html", ".css", ".toml", ".sh"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inventory = json.loads((BASE / "migration/.local/before.json").read_text())
    changes = {}
    payloads = 0
    runtime = 0
    for r in inventory:
        target = REPO / r["new"]
        assert target.is_file(), ("Missing relocated file", r["old"], r["new"])
        current = digest(target)
        allowed = target.suffix in CODE or target.name == ".gitignore"
        if current != r["sha256"]:
            if target.suffix == ".pyc":
                runtime += 1
                continue
            assert allowed, ("Corpus data changed", r["old"], r["new"])
            changes[r["new"]] = dict(
                old=r["old"],
                before_sha256=r["sha256"],
                after_sha256=current,
                reason="relocation_paths_imports_or_readonly_manifest_compatibility",
            )
        if not allowed and target.suffix != ".pyc":
            payloads += 1
        assert resolve_reference(REPO / r["old"]) == target, ("Mapping disagreement", r["old"])
    (BASE / "migration/code-path-changes.json").write_text(
        json.dumps(changes, ensure_ascii=False, indent=2) + "\n"
    )
    rules = [
        r
        for r in inventory
        if Path(r["old"]).name in {"rules.py", "rules_v2.py", "segmentation.py"}
    ]
    assert all(digest(REPO / r["new"]) == r["sha256"] for r in rules), "Extraction rules changed"
    syntax = []
    for p in BASE.rglob("*.py"):
        if any(x in p.parts for x in [".local", ".cache"]):
            continue
        ast.parse(p.read_text(), filename=str(p))
        syntax.append(str(p.relative_to(REPO)))
    sys.path.insert(0, str(BASE / "tools/document-review"))
    from articles import Articles
    from reviewlib import Store

    store = Store()
    engine = Articles(store)
    events = engine.log.history()
    humans = 0
    stale = 0
    for key in engine.parents:
        parent, records, history, head, old = engine.state(key, events)
        engine.check(parent, list(records.values()))
        humans += sum(
            r["type"] == "article" and r["review_status"] in {"human_validated", "human_corrected"}
            for r in records.values()
        )
        stale += len(old)
    assert len(store.records) == 1305 and len(engine.parents) == 29
    assert sum(r["type"] == "article" for rs in engine.base.values() for r in rs.values()) == 719
    assert humans == 333 and stale == 0
    old_sources = REPO / "docs/tools/1789-document-review"
    assert not old_sources.exists()
    report = dict(
        original_files=len(inventory),
        original_bytes=sum(r["bytes"] for r in inventory),
        payload_files_preserved_bit_for_bit=payloads,
        missing_files=0,
        approved_code_doc_path_changes=len(changes),
        generated_bytecode_changes=runtime,
        unchanged_extraction_rule_files=[r["new"] for r in rules],
        python_syntax_checked=len(syntax),
        stanford_volumes=len(store.sources),
        registry_notices=len(store.records),
        parents=len(engine.parents),
        initial_articles=719,
        current_human_articles=humans,
        article_events=len(events),
        parent_events=len(store.history()),
        stale_article_decisions=stale,
        new_extraction_run=False,
        database_access=False,
    )
    (BASE / "migration/verification.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
