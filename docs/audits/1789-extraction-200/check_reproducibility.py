"""Rejoue une extraction et compare les résultats hors horodatages/durées."""

import platform

from common import CACHE, HERE, read, sha, write
from extract import main as extract_main

STABLE = [
    "automatic-units.jsonl",
    "automatic-parents.jsonl.gz",
    "documents.jsonl.gz",
    "units-A.jsonl",
    "units-B.jsonl.gz",
    "retained-C.jsonl.gz",
    "register.json",
    "crosswalk.json",
    "review-log.json",
    "block-cache-equivalence.json",
]


def main():
    before = {n: sha((HERE / "data" / n).read_bytes()) for n in STABLE}
    extract_main()
    after = {n: sha((HERE / "data" / n).read_bytes()) for n in STABLE}
    assert before == after
    resource = CACHE / "resources-final.txt"
    write(
        HERE / "data/reproducibility.json",
        dict(
            stable_files_identical=True,
            sha256=after,
            excluded="extraction-summary timestamps and measured durations",
            measured_resources=resource.read_text() if resource.exists() else None,
            source_cache="/tmp/cahier-1789-extraction-pilot/sources",
            python=platform.python_version(),
            isolated_lxml="6.0.2",
            rules_and_reference_frozen=True,
            aborted_attempts="Two preliminary runs interrupted: preceding-sibling materialization was quadratic. Exact block cache optimization checked against frozen function on12 held-out candidates. No extraction rule changed.",
            human_validation_seconds=None,
            initial_frozen_inventory_sha256=read(HERE / "data/inventory-summary.json")[
                "inventory_sha256"
            ],
        ),
    )
    print("Reproduced", len(STABLE), "identical data files")


if __name__ == "__main__":
    main()
