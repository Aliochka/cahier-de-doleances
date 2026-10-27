"""Restitue les fenêtres de travail à partir des archives locales, sans réseau ni GPU."""

import gzip
import hashlib
import json
from pathlib import Path

here = Path(__file__).resolve().parent
for x in json.loads((here / "archive_manifest.json").read_text())["entries"]:
    data = (here / x["archive"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == x["sha256"]
    raw = gzip.decompress(data)
    assert hashlib.sha256(raw).hexdigest() == x["decoded_sha256"]
    target = here / x["materialized"]
    if target.exists():
        assert target.read_bytes() == raw, "Existing working file differs: " + str(target)
    else:
        target.write_bytes(raw)
print("Local archives materialized/checked")
