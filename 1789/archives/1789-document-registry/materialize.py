"""Recrée les copies de travail des snapshots, hors application et sans réseau."""

import gzip
import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
manifest = json.loads((here / "archive_manifest.json").read_text())
for entry in manifest["entries"]:
    archive = here / entry["archive"]
    target = here / entry["materialized"]
    compressed = archive.read_bytes()
    assert hashlib.sha256(compressed).hexdigest() == entry["sha256"], archive
    raw = gzip.decompress(compressed)
    assert hashlib.sha256(raw).hexdigest() == entry["decoded_sha256"], archive
    if target.exists():
        assert target.read_bytes() == raw, f"Existing working copy differs: {target}"
    else:
        target.write_bytes(raw)
print("Materialized/checked", len(manifest["entries"]), "local snapshots")
