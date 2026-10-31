#!/usr/bin/env python3
# ruff: noqa: E402
"""Contrôles locaux des mesures et de l'intégrité du premier audit, sans réseau."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import frozen_match  # noqa: E402

import argparse
import hashlib
import json
import re
from pathlib import Path

from compare import MAPPING, distance

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(value):
    return hashlib.sha256(value).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--downloads", type=Path)
    parser.add_argument("--reproduced", type=Path)
    args = parser.parse_args()
    data = HERE / "data"
    metrics = read(data / "metrics.json")
    assert metrics["paragraph_pairs"] == metrics["identical_paragraphs"] == 497
    pairs = read(data / "paragraph-pairs.json")
    assert len(pairs) == 497
    assert all(p["equal"] and p["artfl_sha256"] == p["stanford_sha256"] for p in pairs)
    assert len({(p["key"], p["paragraph"]) for p in pairs}) == 497
    documents = read(data / "documents.json")
    assert {d["key"] for d in documents} == set(MAPPING)
    assert len({d["persee_id"] for d in documents}) == 7
    assert sum(len(d["pages"]) for d in documents) == 27
    assert all(
        d["paragraphs_stanford"] == d["paragraphs_artfl"] == d["identical_paragraphs"]
        for d in documents
    )
    coverage = read(data / "coverage.json")
    assert coverage["entries"] == len(coverage["files"]) == 83
    assert {f"APvol{i:02d}.tei" for i in range(1, 7)}.issubset(
        {r["filename"] for r in coverage["files"]}
    )
    assert all(d["artfl_metadata"]["type"] == "cahier" for d in documents)
    probes = read(data / "probes.json")
    assert len(probes) == 5
    for p in probes:
        for provider, value in p["observed"].items():
            expected = distance(" ".join(value.split()).casefold(), p["reference"].casefold())
            assert p["character_edit_distances"][provider] == expected
            assert value.casefold() in p["contexts"][provider].casefold()
    assert metrics["exact_reference_units"] == {"stanford": 0, "artfl": 0, "persee": 4}
    mirecourt = next(p for p in probes if p["id"] == "mirecourt-art5")
    assert mirecourt["observed"]["persee"] == "libërté"
    assert mirecourt["character_edit_distances"] == {"stanford": 1, "artfl": 1, "persee": 1}
    controls = read(data / "completeness-controls.json")
    assert len(controls) == 2
    assert all(
        c["stanford_present"] and c["artfl_present"] and not c["persee_page_present"]
        for c in controls
    )
    assert read(data / "structure.json")["volume4_mets_griev_entries"] == 347
    provenance = read(HERE / "provenance.json")
    assert not provenance["previous_audit_changed_files"]
    assert len(provenance["previous_audit_files_sha256"]) == 35
    for name, checksum in provenance["previous_audit_files_sha256"].items():
        assert frozen_match(ROOT / name, checksum), name
    for target in re.findall(r"\]\(([^)]+)\)", (HERE / "README.md").read_text()):
        if "://" not in target:
            assert (HERE / target).exists(), target
    if args.downloads:
        for fingerprint in read(data / "download-fingerprints.json"):
            path = args.downloads / fingerprint["file"]
            assert path.stat().st_size == fingerprint["bytes"]
            assert sha(path.read_bytes()) == fingerprint["sha256"], path
    if args.reproduced:
        for path in data.glob("*.json"):
            assert path.read_bytes() == (args.reproduced / path.name).read_bytes(), path.name
    print(
        "OK : 7 cahiers, 497 paragraphes identiques, 5 anomalies ciblées, 2 contrôles de complétude, 27 pages référencées."
    )
    print("OK : 35 fichiers du premier audit inchangés ; liens locaux valides.")
    if args.downloads:
        print("OK : empreintes des téléchargements vérifiées.")
    if args.reproduced:
        print("OK : résultats JSON reproduits à l’identique.")


if __name__ == "__main__":
    main()
