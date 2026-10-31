"""Deux reprises à vecteurs figés ; aucune inférence ni accès externe."""

import subprocess
import sys

from common import HERE, ROOT, sha, write

STABLE = [
    "data/corpus.jsonl",
    "data/contemporary-segments.jsonl",
    "data/preparation.json",
    "data/historical-segments.jsonl",
    "data/rankings.jsonl",
    "data/review-pool.jsonl",
    "annotations.json",
    "data/metrics.json",
    "data/results.jsonl",
    "data/novelty.json",
    "COMPARISON.md",
    "GALLERY.md",
]


def main():
    snapshots = []
    for _ in range(2):
        for script in (
            "prepare.py",
            "search.py",
            "review-decisions.py",
            "evaluate.py",
            "diagnostics.py",
            "verify.py",
        ):
            subprocess.run(
                [sys.executable, str(HERE / script)],
                cwd=ROOT,
                check=True,
                stdout=subprocess.DEVNULL,
            )
        snapshots.append({p: sha(HERE / p) for p in STABLE})
    assert snapshots[0] == snapshots[1]
    write(
        HERE / "data/reproducibility.json",
        dict(
            mode="two cached-vector runs; no model inference repeated",
            identical_artifacts=len(STABLE),
            sha256=snapshots[1],
            excluded=["search-timings.json", "diagnostics.costs", "runtime timestamps"],
            queries_unchanged=True,
            raw_rankings_identical=True,
            judgments_identical=True,
            metrics_identical=True,
        ),
    )
    print(f"{len(STABLE)} artifacts identical across two runs")


if __name__ == "__main__":
    main()
