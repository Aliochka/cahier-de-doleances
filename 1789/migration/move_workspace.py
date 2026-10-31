"""One-time physical relocation, preserving every payload byte and tracked-file inventory."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASE = REPO / "1789"
AUDITS = [
    *sorted((REPO / "docs/audits").glob("1789-*")),
    REPO / "docs/audits/multicorpus-scale-study",
]
DIRECTORIES = [(p, BASE / "archives" / p.name) for p in AUDITS]
DIRECTORIES += [(REPO / "docs/tools/1789-document-review", BASE / "tools/document-review")]
ACTIVE = {
    "1789-document-registry": "registry",
    "1789-first-article-corpus": "article-corpus",
    "1789-article-review": "review-exports",
    "1789-article-segmentation-improvement": "segmentation-proposals",
}
EXTRA = [
    (
        "1789/archives/1789-extraction-v2/.cache/sources",
        "1789/sources/stanford/926fd3cd986a3c3d411e93d1845fff6475cb2602",
    ),
    ("1789/archives/1789-document-registry/.cache", "1789/sources/persee/registry-cache"),
    ("1789/archives/1789-persee-stanford-alignment/.cache", "1789/sources/persee/alignment-cache"),
    ("1789/tools/document-review/.local", "1789/data/private/document-review"),
    ("1789/tools/document-review/segmentation.py", "1789/extraction/segmentation.py"),
]
EXTRA += [
    (f"1789/archives/{name}/data", f"1789/data/{dataset}") for name, dataset in ACTIVE.items()
]


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def destination(old):
    value = str(old.relative_to(REPO))
    for src, dst in DIRECTORIES:
        prefix = str(src.relative_to(REPO))
        if value == prefix or value.startswith(prefix + "/"):
            value = str(dst.relative_to(REPO)) + value[len(prefix) :]
            break
    if value == "docs/audits/LOCAL_DATA.md":
        value = "1789/docs/LOCAL_DATA.md"
    for src, dst in sorted(EXTRA, key=lambda v: -len(v[0])):
        if value == src or value.startswith(src + "/"):
            value = dst + value[len(src) :]
            break
    return value


def main():
    local = BASE / "migration/.local"
    inventory = local / "before.json"
    if inventory.exists():
        raise SystemExit("Relocation already inventoried; do not run twice")
    tracked = set(subprocess.check_output(["git", "ls-files", "-z"], cwd=REPO).decode().split("\0"))
    files = [p for src, _ in DIRECTORIES for p in src.rglob("*") if p.is_file()]
    files += [REPO / "docs/audits/LOCAL_DATA.md"]
    rows = []
    for p in files:
        rows.append(
            dict(
                old=str(p.relative_to(REPO)),
                new=destination(p),
                bytes=p.stat().st_size,
                sha256=digest(p),
                tracked=str(p.relative_to(REPO)) in tracked,
            )
        )
    inventory.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
    # Retain original code/doc bytes privately to audit path-only edits later.
    for p in files:
        if p.suffix in {".py", ".md", ".cjs", ".js", ".html", ".css"} or p.name == ".gitignore":
            target = local / "originals" / p.relative_to(REPO)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)
    for src, dst in DIRECTORIES:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    target = REPO / "1789/docs/LOCAL_DATA.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(REPO / "docs/audits/LOCAL_DATA.md"), str(target))
    for src, dst in EXTRA:
        source = REPO / src
        target = REPO / dst
        if not source.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        # Internal aliases preserve historical experiment-relative reads; actual data is unique.
        if src.endswith("/data") or src.endswith("/.cache"):
            source.symlink_to(os.path.relpath(target, source.parent), target_is_directory=True)
    assert all((REPO / r["new"]).is_file() and digest(REPO / r["new"]) == r["sha256"] for r in rows)
    public = dict(
        directory_moves=[
            dict(old=str(a.relative_to(REPO)), new=str(b.relative_to(REPO))) for a, b in DIRECTORIES
        ],
        extra_moves=[dict(old=a, new=b) for a, b in EXTRA],
        file_moves=[dict(old="docs/audits/LOCAL_DATA.md", new="1789/docs/LOCAL_DATA.md")],
        source_revision="926fd3cd986a3c3d411e93d1845fff6475cb2602",
    )
    (BASE / "migration/paths.json").write_text(
        json.dumps(public, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        "Moved",
        len(rows),
        "files;",
        sum(r["bytes"] for r in rows),
        "bytes, all initial hashes preserved.",
    )


if __name__ == "__main__":
    main()
