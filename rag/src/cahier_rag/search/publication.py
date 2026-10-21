"""Signed, read-only installation binding; original corpus manifests stay intact.

This attests a bounded, explicitly approved sample, never exhaustive equivalence.
Maintenance DatabaseGuard/FullStore writers do not consume these attestations.
"""

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from cahier_rag.contracts import canonical_json
from cahier_rag.fullcorpus.audit import fingerprint

SAMPLE_SIZE = 96
PROOF_METHOD = "ordinal96-plus-form-type-v1"


class PublicationError(ValueError):
    pass


def compatible_identity(indexed, current):
    if indexed == current:
        return True
    if not isinstance(indexed, dict) or not isinstance(current, dict):
        return False
    return (indexed.get("schema_revision"), current.get("schema_revision")) == (
        "remove_runtime_caches",
        "forms_statistics_v1",
    ) and {**indexed, "schema_revision": "forms_statistics_v1"} == current


def logical_corpus(state):
    """Logical identity excludes the PostgreSQL installation, not provenance data."""
    return {
        "manifest": {k: v for k, v in state["manifest"].items() if k != "audit_source"},
        **{k: state[k] for k in ("chain_hash", "documents", "segments", "expected_units")},
    }


def sample_ordinals(count):
    if type(count) is not int or count < 1:
        raise ValueError("Corpus vide ou invalide.")
    size = min(count, SAMPLE_SIZE)
    return [1] if size == 1 else [1 + i * (count - 1) // (size - 1) for i in range(size)]


def require_key(key):
    if not isinstance(key, str) or len(key.encode()) < 32:
        raise ValueError("SEARCH_PUBLICATION_KEY requise, au moins 32 octets.")
    return key.encode()


def sign_publication(state, source, target, samples, key):
    """Call only after comparing the sampled full TextUnit content/provenance."""
    payload = {
        "version": 1,
        "publication_id": secrets.token_hex(16),
        "published_at": datetime.now(timezone.utc).isoformat(),
        "logical_id": fingerprint(logical_corpus(state)),
        "origin_manifest_hash": state["recipe_hash"],
        "origin_source": state["manifest"]["audit_source"],
        "source": source,
        "target": target,
        "proof": {"method": PROOF_METHOD, "samples": samples},
        "assurance": "sampled-content-and-provenance-not-exhaustive",
    }
    signature = hmac.new(require_key(key), canonical_json(payload).encode(), hashlib.sha256)
    return {"payload": payload, "signature": signature.hexdigest()}


class Publication:
    def __init__(self, path, key):
        self.path = Path(path)
        self.key = require_key(key)

    def validate(self, state, source, target):
        try:
            # Bound the administrative input; no query or citizen text is needed.
            with self.path.open("rb") as stream:
                raw = stream.read(128 * 1024 + 1)
            if len(raw) > 128 * 1024:
                raise ValueError()
            envelope = json.loads(raw)
            payload = envelope["payload"]
            signature = hmac.new(self.key, canonical_json(payload).encode(), hashlib.sha256)
            proof = payload["proof"]
            samples = proof["samples"]
            if (
                not hmac.compare_digest(signature.hexdigest(), envelope["signature"])
                or payload["version"] != 1
                or not payload["publication_id"]
                or payload["logical_id"] != fingerprint(logical_corpus(state))
                or payload["origin_manifest_hash"] != state["recipe_hash"]
                or payload["origin_source"] != state["manifest"]["audit_source"]
                or not compatible_identity(payload["source"], source)
                or payload["target"] != target
                or proof["method"] != PROOF_METHOD
                or not isinstance(samples, list)
                or not min(SAMPLE_SIZE, state["documents"]) <= len(samples) <= 512
                or len({s["document_id"] for s in samples}) != len(samples)
                or not set(sample_ordinals(state["documents"])) <= {s["ordinal"] for s in samples}
                or any(len(s["content_hash"]) != 64 for s in samples)
                or payload["assurance"] != "sampled-content-and-provenance-not-exhaustive"
            ):
                raise ValueError()
            return fingerprint(payload)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            raise PublicationError("Publication du corpus absente ou incompatible.") from None
