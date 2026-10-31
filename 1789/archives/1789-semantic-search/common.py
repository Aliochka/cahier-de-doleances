# ruff: noqa: E402
"""Utilitaires de l'expérience locale ; aucun accès réseau ou PostgreSQL."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import resolve_reference  # noqa: E402

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRIOR = [
    HERE.parent / name
    for name in ("1789-multicorpus", "1789-sources-comparison", "1789-extraction-pilot")
]


def sha(path):
    h = hashlib.sha256()
    with resolve_reference(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def text_sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def read(path):
    return json.loads(resolve_reference(path).read_text())


def rows(path):
    with resolve_reference(path).open() as f:
        return [json.loads(line) for line in f if line.strip()]


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def write_rows(path, values):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(v, ensure_ascii=False) + "\n" for v in values))
