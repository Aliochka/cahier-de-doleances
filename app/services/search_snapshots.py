"""Instantanés compacts LRU et curseurs authentifiés, sans texte documentaire."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Literal


class CursorError(ValueError):
    pass


class SnapshotExpired(Exception):
    pass


class SnapshotTooLarge(Exception):
    pass


@dataclass(frozen=True)
class UnitReference:
    document_id: str
    answer_id: int
    question_id: int
    contribution_id: int
    form_id: int
    unit_type: str
    unit_index: int
    content_hash: str

    @classmethod
    def from_hit(cls, hit):
        d = hit.document
        return cls(
            d.document_id,
            d.answer_id,
            d.question_id,
            d.contribution_id,
            d.questionnaire_id,
            d.unit_type.value,
            d.unit_index,
            d.content_hash,
        )


@dataclass(frozen=True)
class CardReference:
    rank: int
    units: tuple[UnitReference, ...]


def group_hits(hits):
    grouped = OrderedDict()
    seen = set()
    for hit in hits:
        unit = UnitReference.from_hit(hit)
        if unit.document_id not in seen:
            grouped.setdefault(unit.answer_id, []).append(unit)
            seen.add(unit.document_id)
    return tuple(CardReference(i, tuple(units)) for i, units in enumerate(grouped.values(), 1))


def query_hash(query, question_id=None):
    identity = json.dumps({"q": query, "question_id": question_id}, sort_keys=True)
    return hashlib.sha256(identity.encode()).hexdigest()


@dataclass(frozen=True)
class Snapshot:
    query_hash: str
    page_size: int
    generation: str
    recipe_hash: str
    recipe_version: str
    document_limit: int
    retrieval_depth: int
    cards: tuple[CardReference, ...]
    omitted: int = 0
    mode: Literal["hybrid", "lexical"] = "hybrid"


class SnapshotCache:
    """Utilisé uniquement depuis l'event loop propriétaire du backend."""

    def __init__(
        self,
        key,
        *,
        ttl=600,
        capacity=256,
        max_bytes=16 * 1024**2,
        clock=time.monotonic,
        wall_clock=time.time,
    ):
        if not isinstance(key, str) or len(key.encode()) < 32:
            raise ValueError("SEARCH_CURSOR_KEY doit contenir au moins 32 octets.")
        self.key = key.encode()
        self.ttl, self.capacity, self.max_bytes = ttl, capacity, max_bytes
        self.clock, self.wall_clock = clock, wall_clock
        self.entries = OrderedDict()
        self.payload_bytes = 0

    def clear(self):
        self.entries.clear()
        self.payload_bytes = 0

    def _remove(self, sid):
        self.payload_bytes -= self.entries.pop(sid)[3]

    def _expire(self):
        for sid, (_, deadline, _, _) in list(self.entries.items()):
            if deadline <= self.clock():
                self._remove(sid)

    def put(self, snapshot):
        size = len(json.dumps(asdict(snapshot), ensure_ascii=False, separators=(",", ":")).encode())
        if size > self.max_bytes:
            raise SnapshotTooLarge()
        self._expire()
        while self.entries and (
            len(self.entries) >= self.capacity or self.payload_bytes + size > self.max_bytes
        ):
            self._remove(next(iter(self.entries)))
        sid = secrets.token_urlsafe(24)
        expires = datetime.fromtimestamp(self.wall_clock() + self.ttl, timezone.utc).isoformat()
        self.entries[sid] = (snapshot, self.clock() + self.ttl, expires, size)
        self.payload_bytes += size
        return sid, expires

    def cursor(self, sid, position):
        payload = json.dumps({"v": 1, "s": sid, "p": position}, separators=(",", ":")).encode()
        signature = hmac.digest(self.key, payload, "sha256")
        return base64.urlsafe_b64encode(payload + signature).decode().rstrip("=")

    def get(self, cursor, query, page_size, question_id=None):
        try:
            if not isinstance(cursor, str) or not 1 <= len(cursor) <= 1024:
                raise ValueError()
            raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
            payload, signature = raw[:-32], raw[-32:]
            if not hmac.compare_digest(hmac.digest(self.key, payload, "sha256"), signature):
                raise ValueError()
            value = json.loads(payload)
            if (
                set(value) != {"v", "s", "p"}
                or type(value["v"]) is not int
                or value["v"] != 1
                or not isinstance(value["s"], str)
                or type(value["p"]) is not int
                or value["p"] < 0
            ):
                raise ValueError()
        except (ValueError, TypeError, UnicodeError):
            raise CursorError() from None
        self._expire()
        sid, position = value["s"], value["p"]
        if sid not in self.entries:
            raise SnapshotExpired()
        snapshot, _, expires, _ = self.entries[sid]
        if (
            snapshot.query_hash != query_hash(query, question_id)
            or snapshot.page_size != page_size
            or position >= len(snapshot.cards)
            or position % page_size
        ):
            raise CursorError()
        self.entries.move_to_end(sid)
        return sid, snapshot, position, expires
