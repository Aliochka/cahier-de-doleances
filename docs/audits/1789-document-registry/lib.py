"""Primitives isolées; imports antérieurs par chemin explicite, jamais leurs main()."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ALIGN = HERE.parent / "1789-persee-stanford-alignment"
V2 = HERE.parent / "1789-extraction-v2"
PILOT = HERE.parent / "1789-extraction-pilot"
V1 = HERE.parent / "1789-extraction-200"
CACHE = HERE / ".cache"
NS = {
    "o": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dct": "http://purl.org/dc/terms/",
    "mets": "http://www.loc.gov/METS/",
}


def module(alias, path):
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert Path(mod.__file__).resolve() == Path(path).resolve()
    return mod


_path = list(sys.path)
base_helpers = module("registry_source_helpers", ALIGN / "auditlib.py")
# The historical alignment explicitly imports auditlib; bind only during loading.
_previous = sys.modules.get("auditlib")
sys.modules["auditlib"] = base_helpers
base = module("registry_previous_alignment", ALIGN / "alignment.py")
if _previous is None:
    sys.modules.pop("auditlib", None)
else:
    sys.modules["auditlib"] = _previous
sys.path[:] = _path


def read(p):
    return json.loads(Path(p).read_text())


def rows(p):
    return [json.loads(s) for s in Path(p).read_text().splitlines() if s.strip()]


def sha(x):
    return hashlib.sha256(x.encode() if isinstance(x, str) else x).hexdigest()


def save(p, x):
    Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2) + "\n")


def jlines(p, rs):
    Path(p).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rs))


def sources():
    return base_helpers.load_sources()


compact = base_helpers.compact
fold = base_helpers.fold
source_ref = base_helpers.source_ref
