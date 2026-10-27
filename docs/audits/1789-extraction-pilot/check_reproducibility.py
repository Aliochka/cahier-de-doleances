"""Exécute deux fois le pilote et compare données/identifiants, hors chronométrage."""

import argparse
import subprocess
import sys

from common import ROOT, read, sha, write


def snapshot():
    files = sorted((ROOT / "data" / "parents").glob("*"))
    files += [
        ROOT / "data" / name
        for name in [
            "documents.jsonl",
            "units.jsonl",
            "retained-unsegmented.jsonl",
            "automatic-predictions.jsonl",
            "reference.json",
            "register.json",
            "provenance.json",
            "checks.json",
            "negative-results.json",
            "boundary-errors.json",
            "legacy-crosswalk.json",
            "navigation-examples.json",
            "proposal-review.json",
            "summary.json",
        ]
    ]
    value = {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in files}
    evaluation = read("data/evaluation.json")
    del evaluation["timing"]
    return value, evaluation


def main(directory):
    snapshots = []
    for _ in range(2):
        for script, args in [
            ("extract.py", [directory]),
            ("verify.py", [directory]),
            ("derive.py", []),
        ]:
            subprocess.run(
                [sys.executable, str(ROOT / script), *args],
                check=True,
                capture_output=True,
                text=True,
            )
        snapshots.append(snapshot())
    assert snapshots[0] == snapshots[1], "Non-deterministic data or metrics"
    write(
        "data/reproducibility.json",
        {
            "executions": 2,
            "identical_artifacts": len(snapshots[0][0]),
            "artifact_sha256": snapshots[0][0],
            "metrics_identical_excluding_timing": True,
            "excluded": [
                "timing and execution timestamp in evaluation.json",
                "independent documentary review log",
            ],
            "same_source_revision_and_decisions": True,
        },
    )
    print(len(snapshots[0][0]), "artifacts identical; metrics identical except timing")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sources")
    main(parser.parse_args().sources)
