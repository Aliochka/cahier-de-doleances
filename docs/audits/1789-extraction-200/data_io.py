"""Lecture des états A et B séparés ; aucun accès applicatif."""

import gzip
import json

from common import HERE, rows


def units():
    with gzip.open(HERE / "data/units-B.jsonl.gz", "rt") as f:
        return rows(HERE / "data/units-A.jsonl") + [json.loads(line) for line in f]
