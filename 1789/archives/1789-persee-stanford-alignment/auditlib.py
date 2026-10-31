# ruff: noqa: E402
"""Primitives isolées; reprise en lecture des sources figées et helpers antérieurs."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import resolve_reference  # noqa: E402

import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "1789-extraction-v2"
sys.path.insert(0, str(PREVIOUS))
from common import compact as compact, source_ref as source_ref, sources  # noqa: E402
from fast_blocks import cache_nodes  # noqa: E402


def sha(x):
    return hashlib.sha256(x.encode() if isinstance(x, str) else x).hexdigest()


def read(p):
    return json.loads(resolve_reference(p).read_text())


def rows(p):
    return [json.loads(s) for s in Path(p).read_text().splitlines() if s.strip()]


def save(p, x):
    Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2) + "\n")


def jlines(p, rs):
    Path(p).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rs))


def fold(s):
    s = "".join(
        c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"-\s+", "", s)).strip()


def load_sources():
    ss = sources()
    for s in ss.values():
        cache_nodes(s)
    return ss
