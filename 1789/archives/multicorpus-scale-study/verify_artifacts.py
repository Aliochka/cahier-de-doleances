# ruff: noqa: E402
"""Validation et manifeste des seuls livrables du nouvel audit, sans base."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import frozen_match  # noqa: E402

import datetime
import gzip
import importlib.metadata
import json
import platform
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

from common import HERE, ROOT, read, sha, write


def main():
    import numpy as np

    parsed = {}
    for p in sorted(HERE.rglob("*")):
        if p.is_dir() or "__pycache__" in p.parts:
            continue
        name = str(p.relative_to(HERE))
        if p.suffix == ".json":
            read(p)
            parsed[name] = "JSON"
        elif p.suffix == ".jsonl" or p.name.endswith(".jsonl.gz"):
            opener = gzip.open if p.suffix == ".gz" else Path.open
            with opener(p, "rt") as f:
                parsed[name] = sum(1 for line in f if json.loads(line))
        elif p.suffix == ".npz":
            with np.load(p, allow_pickle=False) as arrays:
                assert all(np.isfinite(arrays[k]).all() for k in arrays)
                parsed[name] = {k: list(arrays[k].shape) for k in arrays}
    # Reports may name the two generated manifests before this first run.
    generated = {HERE / "data/verification.json", HERE / "data/deliverables-sha256.json"}
    local_links = []
    for p in HERE.glob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", p.read_text()):
            if "://" in target or target.startswith("#"):
                continue
            path = (p.parent / unquote(target.split("#")[0])).resolve()
            assert path.exists() or path in generated, (p, target)
            local_links.append(str(path.relative_to(ROOT)))
    prior = read(HERE / "prior-audits-sha256.json")
    assert all(frozen_match(ROOT / p, h) for p, h in prior.items())
    assert (
        subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True).strip()
        == ""
    )
    for arguments in (
        [".venv/bin/ruff", "check", str(HERE.relative_to(ROOT))],
        [".venv/bin/ruff", "format", "--check", str(HERE.relative_to(ROOT))],
    ):
        subprocess.run(arguments, cwd=ROOT, check=True, capture_output=True, text=True)
    checks = read(HERE / "data/checks.json")
    assert checks["replayed_fusions"] == 1800
    with gzip.open(HERE / "data/result-documents.jsonl.gz", "rt") as f:
        documents = {d["g"]: d for d in (json.loads(line) for line in f)}
    with gzip.open(HERE / "data/rankings.jsonl.gz", "rt") as f:
        for line in f:
            assert all(r["g"] in documents for r in json.loads(line)["results"])
    for d in (
        json.loads(line)
        for line in (HERE / "data/qualitative-documents.jsonl").read_text().splitlines()
    ):
        assert documents[d["g"]]["text"] == d["text"]
        assert documents[d["g"]]["id"] == d["id"]
    packages = {}
    for package in ("numpy", "psutil", "psycopg2-binary", "torch", "transformers", "ruff"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = "not installed under this distribution name"
    plot_packages = {
        d.metadata["Name"]: d.version
        for d in importlib.metadata.distributions(path=["/tmp/multicorpus-scale-plot-tools"])
    }
    write(
        HERE / "data/verification.json",
        dict(
            verified_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            python=platform.python_version(),
            packages=packages,
            isolated_plot_packages=plot_packages,
            parsed_artifacts=parsed,
            local_markdown_links_checked=len(local_links),
            full_top100_documents=len(documents),
            full_text_coverage_of_all_stored_results=True,
            prior_audit_files_unchanged=len(prior),
            no_tracked_application_change=True,
            ruff_check="passed",
            ruff_format="passed",
            replay=checks,
            existing_tests=dict(
                command="PYTHONPATH=rag/src PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider rag/tests/unit/test_embeddings.py rag/tests/unit/test_hybrid.py",
                observed_result="36 passed in 1.00s",
                note="Executed during this mission; no database fixture or service started",
            ),
            figures_visually_reviewed=[
                "01-witness-ranks",
                "02-known-witness-recall",
                "03-result-composition",
                "04-candidate-depth",
                "05-first-pages",
            ],
            new_embeddings=0,
            database_connections_in_this_verification=0,
        ),
    )
    excluded = {"data/deliverables-sha256.json"}
    files = {
        str(p.relative_to(HERE)): sha(p)
        for p in sorted(HERE.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts and str(p.relative_to(HERE)) not in excluded
    }
    write(HERE / "data/deliverables-sha256.json", files)
    print(f"Verified {len(parsed)} structured artifacts and {len(local_links)} local links")
    print(f"Manifest: {len(files)} files; prior {len(prior)} files unchanged")


if __name__ == "__main__":
    main()
