"""Read-only access to the technical collection. No historical decisions are written."""

import json

from reviewlib import HERE, rows


class TechnicalCollection:
    def __init__(self):
        base = HERE.parents[1]
        pointer = json.loads((base / "data/documents/current.json").read_text())
        self.directory = (base / pointer["directory"]).resolve()
        if (base / "data/documents").resolve() not in self.directory.parents:
            raise ValueError("Invalid reference collection path")
        self.manifest = json.loads((self.directory / "manifest.json").read_text())
        self.documents = {d["id"]: d for d in rows(self.directory / "documents.jsonl.gz")}
        self.metadata = {m["id"]: m for m in rows(self.directory / "metadata.jsonl.gz")}
        self.passages = {p["id"]: p for p in rows(self.directory / "passages.jsonl.gz")}

    def catalogue(self):
        return dict(
            summary=json.loads((self.directory / "summary.json").read_text()),
            sample=json.loads((self.directory / "visual-sample.json").read_text()),
            documents=[
                dict(
                    id=d["id"],
                    title=self.metadata[d["id"]]["title"],
                    volume=d["volume"],
                    kind=d["document_kind"],
                    passages=len(d["passage_ids"]),
                )
                for d in self.documents.values()
            ],
        )

    def document(self, document_id=None, passage_id=None):
        passage = self.passages[passage_id] if passage_id else None
        doc = self.documents[passage["document_id"] if passage else document_id]
        passage = passage or (self.passages[doc["passage_ids"][0]] if doc["passage_ids"] else None)
        return dict(
            document={k: v for k, v in doc.items() if k != "xml_blocks"},
            metadata=self.metadata[doc["id"]],
            passage=passage,
            passages=[
                {
                    k: self.passages[uid][k]
                    for k in [
                        "id",
                        "ordinal",
                        "token_count",
                        "start_in_document",
                        "end_in_document",
                    ]
                }
                for uid in doc["passage_ids"]
            ],
        )
