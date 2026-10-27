"""Compression sans perte des grandes fenêtres, jamais des poids ou des anciens audits."""

import gzip

from qcommon import HERE, save, sha

entries = []
for p in sorted((HERE / "data").glob("*.jsonl")):
    if p.stat().st_size < 300000:
        continue
    raw = p.read_bytes()
    encoded = gzip.compress(raw, compresslevel=9, mtime=0)
    target = p.with_suffix(p.suffix + ".gz")
    target.write_bytes(encoded)
    entries.append(
        dict(
            archive=str(target.relative_to(HERE)),
            materialized=str(p.relative_to(HERE)),
            sha256=sha(encoded),
            decoded_sha256=sha(raw),
            decoded_bytes=len(raw),
            archive_bytes=len(encoded),
            records=raw.count(b"\n"),
        )
    )
save(HERE / "archive_manifest.json", dict(format="gzip UTF-8 JSONL", entries=entries))
(HERE / ".gitignore").write_text(
    "/.cache/\n__pycache__/\n!*.json\n!*.jsonl\n!*.gz\n!data/\n!data/**\n"
    + "".join("/" + x["materialized"] + "\n" for x in entries)
)
print(
    "Archived",
    len(entries),
    "files",
    sum(x["decoded_bytes"] for x in entries),
    "→",
    sum(x["archive_bytes"] for x in entries),
    "bytes",
)
