# ruff: noqa: E402
"""Outils isolés ; reprise en lecture des primitives de provenance du pilote."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import resolve_reference  # noqa: E402

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "1789-extraction-200"))
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PILOT = HERE.parent / "1789-extraction-pilot"
CACHE = HERE.parents[1] / ".cache/1789-extraction-v2"
SOURCES = HERE.parents[1] / "sources/stanford/926fd3cd986a3c3d411e93d1845fff6475cb2602"
REVISION = "926fd3cd986a3c3d411e93d1845fff6475cb2602"
VERSION = "discovery-v2"
CORPUS = "cahiers-1789-ap-stanford"
spec = importlib.util.spec_from_file_location("pilot_provenance", PILOT / "common.py")
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
Source = pilot.Source
compact = pilot.compact


def read(path):
    return json.loads(resolve_reference(path).read_text())


def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def jlines(path, values):
    Path(path).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in values))


def sources():
    return pilot.load_sources(SOURCES)


def pages(source, start, end):
    return [
        dict(
            p,
            image_service=f"https://stacks.stanford.edu/image/iiif/{source.path.stem}%2F{p['id']}",
        )
        for p in source.pages_for(start, end)
    ]


def source_ref(source):
    d = source.path.stem
    return dict(
        source_file=f"{d}/{d}.xml",
        source_sha256=source.sha256,
        source_revision=REVISION,
        source_url=f"https://github.com/StanfordUniversityLibraries/ap_tei/blob/{REVISION}/{d}/{d}.xml",
        scan_url=f"https://purl.stanford.edu/{d}",
        offsets="half-open Unicode codepoints in decoded XML itertext; no whitespace normalization",
    )


V1 = HERE.parent / "1789-extraction-200"
sys.path.append(str(V1))
