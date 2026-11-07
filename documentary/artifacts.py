"""Read existing artifacts; never call historical extractors or normalise source text."""

import gzip
import hashlib
import json
from pathlib import Path

CORPUS = "cahiers-1789-ap-stanford"
GENERATION = "reference-documents-2-7cbcaea79991"
MANIFEST_SHA256 = "eb9f4533e95df62a8964fbd6a71d56c0446b7769f6fa9d80fcdd8c0111e08ff2"
ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "1789/data/documents" / GENERATION
DECISIONS = ROOT / "1789/editorial/decisions.json"


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def keyed(records, key="id"):
    result = {r[key]: r for r in records}
    if len(result) != len(records):
        raise ValueError("Duplicate artifact identifier")
    return result


class Artifacts:
    def __init__(self, directory=REFERENCE):
        self.directory = Path(directory).resolve()
        if self.directory == REFERENCE.resolve():
            pointer = json.loads((REFERENCE.parent / "current.json").read_text())
            if (ROOT / "1789" / pointer["directory"]).resolve() != self.directory:
                raise ValueError(
                    "Active collection differs from the explicitly supported reference"
                )
        manifest_bytes = (self.directory / "manifest.json").read_bytes()
        self.manifest_hash = sha(manifest_bytes)
        if self.manifest_hash != MANIFEST_SHA256:
            raise ValueError("Reference manifest fingerprint mismatch")
        self.manifest = json.loads(manifest_bytes)
        for filename, expected in self.manifest["files"].items():
            path = self.directory / filename
            if path.resolve().parent != self.directory or sha(path.read_bytes()) != expected:
                raise ValueError(f"Artifact fingerprint mismatch: {filename}")
        self.documents = keyed(rows(self.directory / "documents.jsonl.gz"))
        self.metadata = keyed(rows(self.directory / "metadata.jsonl.gz"))
        self.units = keyed(rows(self.directory / "passages.jsonl.gz"))
        self.inventory = rows(self.directory / "inventory.jsonl.gz")
        self.summary = json.loads((self.directory / "summary.json").read_text())
        self.validate()

    def validate(self):
        if self.summary["generation"] != GENERATION:
            raise ValueError("Unexpected reference generation")
        notices = keyed(self.inventory)
        if not set(self.documents) <= set(self.metadata) or set(self.metadata) != set(notices):
            raise ValueError("Document/metadata/inventory coverage differs")
        own = {key: [] for key in self.documents}
        for unit in self.units.values():
            doc = self.documents[unit["document_id"]]
            a, z = unit["start_in_document"], unit["end_in_document"]
            if not (
                type(a) is int
                and type(z) is int
                and 0 <= a < z <= len(doc["full_text"])
                and unit["text"] == doc["full_text"][a:z]
                and sha(unit["text"]) == unit["text_sha256"]
                and unit["document_extent_id"] == doc["extent_id"]
                and unit["source_start"] == doc["source_start"] + a
                and unit["source_end"] == doc["source_start"] + z
            ):
                raise ValueError("Invalid unit slice, offsets, extent or hash")
            own[doc["id"]].append(unit)
        for key, doc in self.documents.items():
            units = sorted(own[key], key=lambda r: r["ordinal"])
            if not (
                doc["corpus_id"] == CORPUS
                and sha(doc["full_text"]) == doc["text_sha256"]
                and doc["source_end"] - doc["source_start"] == len(doc["full_text"])
                and [u["id"] for u in units] == doc["passage_ids"]
                and [u["ordinal"] for u in units] == list(range(1, len(units) + 1))
                and units
                and units[0]["start_in_document"] == 0
                and units[-1]["end_in_document"] == len(doc["full_text"])
            ):
                raise ValueError("Invalid document hash, identity or unit ordering")
            for prev, nxt in zip(units, units[1:]):
                if not (
                    prev["start_in_document"]
                    < nxt["start_in_document"]
                    <= prev["end_in_document"]
                    < nxt["end_in_document"]
                ):
                    raise ValueError("Unit coverage gap or inconsistent overlap")
        counts = self.counts()
        expected = dict(
            notices=1305,
            documents=1267,
            probable_cahiers=1224,
            other_documents=43,
            units=11391,
            cahier_units=10750,
        )
        if counts != expected:
            raise ValueError(f"Reference inventory differs: {counts}")

    def counts(self):
        candidates = {
            k for k, d in self.documents.items() if d["document_kind"] == "cahier_autonome_probable"
        }
        return dict(
            notices=len(self.inventory),
            documents=len(self.documents),
            probable_cahiers=len(candidates),
            other_documents=len(self.documents) - len(candidates),
            units=len(self.units),
            cahier_units=sum(u["document_id"] in candidates for u in self.units.values()),
        )

    def document_rows(self, projection):
        ordered = sorted(
            self.documents.values(),
            key=lambda d: (d["volume"], d["source_start"], d["source_end"], d["id"]),
        )
        for ordinal, doc in enumerate(ordered, 1):
            meta = self.metadata[doc["id"]]
            yield dict(
                corpus_id=CORPUS,
                release_id=GENERATION,
                document_id=doc["id"],
                extent_id=doc["extent_id"],
                source_title=meta["title"],
                full_text=doc["full_text"],
                text_sha256=doc["text_sha256"],
                source_metadata={
                    "document": {k: v for k, v in doc.items() if k != "full_text"},
                    "metadata": meta,
                },
                provenance=doc["source"],
                edition_order=ordinal,
                order_locator={k: doc[k] for k in ("volume", "source_start", "source_end")},
                document_kind=doc["document_kind"],
                boundary_status=doc["boundary_status"],
                candidate=doc["document_kind"] == "cahier_autonome_probable",
                **projection["documents"][doc["id"]],
            )

    def unit_rows(self, projection):
        for unit in self.units.values():
            yield dict(
                corpus_id=CORPUS,
                release_id=GENERATION,
                unit_id=unit["id"],
                document_id=unit["document_id"],
                ordinal=unit["ordinal"],
                unit_type=unit["unit_type"],
                start_offset=unit["start_in_document"],
                end_offset=unit["end_in_document"],
                text_sha256=unit["text_sha256"],
                source_metadata={k: v for k, v in unit.items() if k != "text"},
                searchable=projection["units"][unit["id"]],
            )
