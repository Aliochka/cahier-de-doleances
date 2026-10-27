"""Archive sans perte les grands JSONL et évite leur duplication dans le dépôt."""

import gzip
import io

from lib import HERE, save, sha

entries = []
for p in sorted((HERE / "data").glob("*.jsonl")):
    if p.stat().st_size < 300000:
        continue
    raw = p.read_bytes()
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0, compresslevel=9) as f:
        f.write(raw)
    encoded = buffer.getvalue()
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
save(HERE / "archive_manifest.json", dict(format="gzip JSONL UTF-8", entries=entries))
base = "/.cache/\n__pycache__/\n!*.json\n!*.jsonl\n!*.jsonl.gz\n!data/\n!data/**\n"
(HERE / ".gitignore").write_text(
    base
    + "\n# Large working copies are provided as lossless gzip archives.\n"
    + "".join("/" + x["materialized"] + "\n" for x in entries)
)
print(
    "Compressed",
    len(entries),
    "files:",
    sum(x["decoded_bytes"] for x in entries),
    "to",
    sum(x["archive_bytes"] for x in entries),
    "bytes",
)
