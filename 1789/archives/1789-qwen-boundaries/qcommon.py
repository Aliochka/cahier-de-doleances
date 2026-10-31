# ruff: noqa: E402
"""Accès en lecture aux helpers existants, isolé de l'application et des bases."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import resolve_reference  # noqa: E402

import gzip
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
AUDITS = HERE.parent
ROOT = HERE.parents[2]
REG = AUDITS / "1789-document-registry"


def sha(x):
    return hashlib.sha256(x.encode() if isinstance(x, str) else x).hexdigest()


def read(path):
    return json.loads(resolve_reference(path).read_text())


def rows(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as f:
            return [json.loads(line) for line in f if line.strip()]
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def save(path, x):
    Path(path).write_text(json.dumps(x, ensure_ascii=False, indent=2) + "\n")


def jlines(path, rs):
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rs))


def source_helpers():
    spec = importlib.util.spec_from_file_location("qwen_registry_helpers", REG / "lib.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def preserve():
    path = HERE / "prior-files-sha256.json"
    if not path.exists():
        files = [
            p
            for p in AUDITS.rglob("*")
            if p.is_file()
            and HERE not in p.parents
            and not any(x in p.parts for x in (".cache", "__pycache__"))
        ]
        files += [p for p in (ROOT / "rag/src").rglob("*.py")]
        files += [ROOT / "rag/pyproject.toml", ROOT / "rag/uv.lock"]
        save(path, {str(p.relative_to(ROOT)): sha(p.read_bytes()) for p in files if p.exists()})
