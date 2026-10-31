"""Resolve frozen provenance paths without changing source data or historical manifests."""

import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPO = BASE.parent
PLAN = json.loads((BASE / "migration/paths.json").read_text())
MOVES = [(r["old"], r["new"]) for r in PLAN["directory_moves"] + PLAN["file_moves"]]
EXTRA = sorted([(r["old"], r["new"]) for r in PLAN["extra_moves"]], key=lambda pair: -len(pair[0]))
REVISION = PLAN["source_revision"]
LEGACY_CACHE = {
    "/tmp/cahier-1789-extraction-pilot/sources": BASE / "sources/stanford" / REVISION,
    "/tmp/cahier-1789-extraction-200": BASE / ".cache/1789-extraction-200",
    "/tmp/cahier-1789-extraction-v2": BASE / ".cache/1789-extraction-v2",
    "/tmp/cahier-multicorpus-scale-study": BASE / ".cache/multicorpus-scale-study",
}


def resolve_reference(path):
    """Only file locations are translated; identifiers, texts and stored JSON stay intact."""
    path = Path(path)
    if path.is_absolute():
        try:
            value = str(path.relative_to(REPO))
        except ValueError:
            value = str(path)
            for old, new in LEGACY_CACHE.items():
                if value == old or value.startswith(old + "/"):
                    return Path(str(new) + value[len(old) :])
            return path
    else:
        value = str(path)
        if not value.startswith(("docs/audits/", "docs/tools/", "1789/")):
            return path
    for old, new in MOVES:
        if value == old or value.startswith(old + "/"):
            value = new + value[len(old) :]
            break
    for old, new in EXTRA:
        if value == old or value.startswith(old + "/"):
            value = new + value[len(old) :]
            break
    return REPO / value


def frozen_match(path, expected):
    """Accept identical bytes, or an explicitly inventoried code/doc path-only migration.

    Changed datasets and journals never receive an exception. Historical fingerprints
    which already failed before the move are deliberately not silently accepted.
    """
    actual_path = resolve_reference(path)
    actual = hashlib.sha256(actual_path.read_bytes()).hexdigest()
    if actual == expected:
        return True
    changes_path = BASE / "migration/code-path-changes.json"
    if not changes_path.exists():
        return False
    try:
        key = str(actual_path.relative_to(REPO))
    except ValueError:
        return False
    change = json.loads(changes_path.read_text()).get(key)
    return bool(change and change["before_sha256"] == expected and change["after_sha256"] == actual)
