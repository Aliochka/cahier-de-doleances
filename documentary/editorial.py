"""Small immutable decision log, replayed without changing any source fingerprint."""

import json
from datetime import datetime

from .artifacts import CORPUS, GENERATION, canonical, sha

EVENT_FIELDS = frozenset(
    {
        "decision_id",
        "revision_id",
        "sequence",
        "corpus_id",
        "source_generation",
        "document_id",
        "unit_id",
        "expected_document_hash",
        "expected_extent_id",
        "expected_unit_hash",
        "property",
        "value",
        "reason_code",
        "justification",
        "evidence",
        "decided_by",
        "decided_at",
        "supersedes_id",
    }
)


def load_decisions(path):
    return json.loads(path.read_text())


def replay(artifacts, bundle):
    if (bundle["format_version"], bundle["corpus_id"], bundle["source_generation"]) != (
        1,
        CORPUS,
        GENERATION,
    ):
        raise ValueError("Unsupported editorial format or source generation")
    if not bundle["revision_id"]:
        raise ValueError("Editorial revision is required")
    documents = {
        key: dict(
            display_title=artifacts.metadata[key]["title"],
            warnings={},
            catalogue_visible=False,
            readable=False,
            searchable=False,
        )
        for key in artifacts.documents
    }
    units = dict.fromkeys(artifacts.units, True)
    seen, heads, sequence = {}, {}, set()
    for event in bundle["decisions"]:
        if set(event) != EVENT_FIELDS:
            raise ValueError("Editorial event fields must match format 1 exactly")
        doc = artifacts.documents[event["document_id"]]
        if event["decision_id"] in seen or (event["revision_id"], event["sequence"]) in sequence:
            raise ValueError("Duplicate editorial identity/sequence")
        if (
            event["corpus_id"],
            event["source_generation"],
            event["expected_document_hash"],
            event["expected_extent_id"],
        ) != (CORPUS, GENERATION, doc["text_sha256"], doc["extent_id"]):
            raise ValueError("Editorial document fingerprint or extent mismatch")
        if not all(
            event.get(k) for k in ("reason_code", "justification", "evidence", "decided_by")
        ):
            raise ValueError("Editorial provenance and justification required")
        if datetime.fromisoformat(event["decided_at"].replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("Editorial date must carry timezone")
        if type(event["sequence"]) is not int or event["sequence"] <= 0:
            raise ValueError("Invalid editorial sequence")
        prop, value = event["property"], event["value"]
        unit_id = event.get("unit_id")
        if prop == "search_enabled":
            unit = artifacts.units[unit_id]
            if (
                unit["document_id"] != doc["id"]
                or event.get("expected_unit_hash") != unit["text_sha256"]
                or type(value) is not bool
            ):
                raise ValueError("Editorial unit fingerprint/parent/value mismatch")
        elif unit_id is not None or event.get("expected_unit_hash") is not None:
            raise ValueError("Document decision cannot target a unit")
        key = (
            doc["id"],
            unit_id,
            prop,
            value.get("key") if prop == "warning" and isinstance(value, dict) else None,
        )
        if event.get("supersedes_id") != heads.get(key):
            raise ValueError("Explicit same-property succession required")
        target = documents[doc["id"]]
        if prop == "search_enabled":
            units[unit_id] = value
        elif prop == "display_title":
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError("Invalid display title")
            target["display_title"] = value or artifacts.metadata[doc["id"]]["title"]
        elif prop == "warning":
            if (
                not isinstance(value, dict)
                or not value.get("key")
                or type(value.get("enabled")) is not bool
            ):
                raise ValueError("Invalid warning")
            if value["enabled"]:
                if not isinstance(value.get("message"), str) or not value["message"].strip():
                    raise ValueError("Warning message required")
                if "start_offset" in value or "end_offset" in value:
                    a, z = value.get("start_offset"), value.get("end_offset")
                    if (
                        type(a) is not int
                        or type(z) is not int
                        or not 0 <= a < z <= len(doc["full_text"])
                    ):
                        raise ValueError("Invalid warning range")
                target["warnings"][value["key"]] = value
            else:
                target["warnings"].pop(value["key"], None)
        elif prop == "publication":
            if value != {"catalogue": False, "read": False, "search": False}:
                raise ValueError("Phase 1 does not authorize publication")
        else:
            raise ValueError("Unknown editorial property")
        seen[event["decision_id"]] = event
        heads[key] = event["decision_id"]
        sequence.add((event["revision_id"], event["sequence"]))
    return dict(documents=documents, units=units, hash=sha(canonical(bundle)))
