"""Isolated local documentary review. Never imports application code or writes sources."""

import bisect
import contextlib
import fcntl
import gzip
import hashlib
import importlib.util
import json
import math
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AUDITS = ROOT / "1789/archives"
PRIVATE = ROOT / "1789/data/private/document-review"
sys.path.insert(0, str(ROOT / "1789/extraction"))
sys.path.insert(0, str(ROOT / "1789"))
REGISTRY = ROOT / "1789/data/registry/registry.jsonl.gz"
BATCH = ROOT / "1789/data/article-corpus/selection.json"
VERSION = "document-review-1.0"
STATUSES = ["proposed", "codex_reviewed", "human_validated", "uncertain", "blocked"]


def sha(data):
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def rows(path):
    path = Path(path)
    with (
        gzip.open(path, "rt", encoding="utf-8")
        if path.suffix == ".gz"
        else path.open(encoding="utf-8")
    ) as f:
        return [json.loads(line) for line in f if line.strip()]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Conflict(ValueError):
    pass


class Store:
    def __init__(self, journal=None):
        self.automatic_corrections = {}
        self.records = rows(REGISTRY)
        self.by_id = {r["id"]: r for r in self.records}
        self.registry_sha = sha(REGISTRY.read_bytes())
        self.lib = module(
            "document_review_source_helpers", AUDITS / "1789-document-registry/lib.py"
        )
        self.sources = self.lib.sources()
        self.blocks = {}
        self.block_maps = {}
        self.starts = {}
        self.ends = {}
        for v, source in self.sources.items():
            _, page_at = self.lib.base.page_index(source)
            bs = []
            for n in source.tree.xpath(
                "//text/body//*[self::p or self::head or self::note or self::pb][not(ancestor::p or ancestor::head or ancestor::note)]"
            ):
                a, b = source.span(n)
                text = source.text[a:b]
                if n.tag != "pb" and not text.strip():
                    continue
                bs.append(
                    dict(
                        id=f"v{v}-b{len(bs) + 1:06d}",
                        xpath=source.tree.getpath(n),
                        start=a,
                        end=b,
                        tag=n.tag,
                        text=text,
                        page=page_at(a),
                        index=len(bs),
                    )
                )
            self.blocks[v] = bs
            self.block_maps[v] = {b["id"]: b for b in bs}
            self.starts[v] = [b["start"] for b in bs]
            self.ends[v] = [b["end"] for b in bs]
        self.references = {}
        # Only references established by source examination, never model predictions.
        for split in ["development", "validation"]:
            for r in rows(AUDITS / f"1789-qwen-boundaries/data/reference-{split}.jsonl"):
                if r["status"] == "established":
                    key = "ap1789-registry-p1:" + r["persee_id"]
                    self.references[key] = dict(
                        start=r["start"],
                        end=r["end"],
                        origin=f"1789-qwen-boundaries/data/reference-{split}.jsonl",
                        reason=r["reason"],
                        reviewer="Codex",
                        source_sha256=r["source_sha256"],
                    )
        self.journal = Path(journal) if journal else PRIVATE / "decisions.jsonl"
        self.batch = load(BATCH) if BATCH.exists() else []
        self.batch_map = {r["document_id"]: r for r in self.batch}
        self.inherited_parents = {
            p["id"]: p for p in rows(AUDITS / "1789-extraction-pilot/data/documents.jsonl")
        }

    def source_version(self, record):
        return dict(
            registry_sha256=self.registry_sha,
            source_sha256=self.sources[record["metadata"]["volume"]].sha256,
            source_revision=record["source"]["source_revision"],
            block_version="qwen-boundary-blocks-v1",
        )

    def selected_blocks(self, v, start, end):
        i = bisect.bisect_right(self.ends[v], start)
        j = bisect.bisect_left(self.starts[v], end)
        return self.blocks[v][i:j]

    def span_view(self, record, span):
        if not span:
            return None
        v = record["metadata"]["volume"]
        a, z = span["start"], span["end"]
        bs = [b for b in self.selected_blocks(v, a, z) if b["tag"] != "pb"]
        if not bs:
            return dict(
                start=a,
                end=z,
                start_id=None,
                end_id=None,
                inside_block=True,
                start_inside_block=True,
                end_inside_block=True,
            )
        first, last = bs[0], bs[-1]
        text = self.sources[v].text
        # Whitespace around a complete XML block is harmless; partial content never snapped silently.
        start_partial = first["start"] < a or bool(text[a : first["start"]].strip())
        end_partial = last["end"] > z or bool(text[last["end"] : z].strip())
        return dict(
            start=a,
            end=z,
            start_id=first["id"],
            end_id=last["id"],
            inside_block=bool(start_partial or end_partial),
            start_inside_block=start_partial,
            end_inside_block=end_partial,
        )

    def base(self, record):
        correction = self.automatic_corrections.get(record["id"])
        if correction and correction["changed"]:
            if correction["source_sha256"] != self.sources[record["metadata"]["volume"]].sha256:
                raise ValueError("Documentary correction/source fingerprint mismatch")
            return (
                correction["selected"],
                "proposed",
                correction["version"] + ":source_evidenced_proposal",
            )
        if record["id"] in self.references:
            ref = self.references[record["id"]]
            if ref["source_sha256"] != self.sources[record["metadata"]["volume"]].sha256:
                raise ValueError("Reference/source fingerprint mismatch")
            return ref, "codex_reviewed", ref["origin"]
        boundary = record["boundaries"]
        ref = boundary.get("verified_reference")
        if boundary.get("status") == "verifiees" and ref:
            return ref, "codex_reviewed", "1789-document-registry:verified_reference"
        entry = self.batch_map.get(record["id"], {})
        inherited = self.inherited_parents.get(entry.get("legacy_parent_id"))
        if inherited and inherited["boundary_review"].startswith("verified_xml"):
            if inherited["source_sha256"] != self.sources[record["metadata"]["volume"]].sha256:
                raise ValueError("Inherited parent/source mismatch")
            return (
                dict(start=inherited["source_text_start"], end=inherited["source_text_end"]),
                "codex_reviewed",
                "1789-extraction-pilot:" + inherited["id"],
            )
        return boundary.get("proposal"), "proposed", "1789-document-registry:proposal"

    @contextlib.contextmanager
    def locked_journal(self):
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        with self.journal.open("a+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.seek(0)
                yield f
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def history(self):
        if not self.journal.exists():
            return []
        events = rows(self.journal)
        previous = None
        for e in events:
            raw = {k: val for k, val in e.items() if k != "event_hash"}
            if (
                e["previous_hash"] != previous
                or sha(json.dumps(raw, sort_keys=True, ensure_ascii=False)) != e["event_hash"]
            ):
                raise ValueError("Journal integrity error; do not overwrite this journal")
            previous = e["event_hash"]
        return events

    def latest(self):
        return {e["document_id"]: e for e in self.history()}

    def state(self, record, latest=None):
        latest = self.latest() if latest is None else latest
        base, status, origin = self.base(record)
        view = self.span_view(record, base)
        event = latest.get(record["id"])
        if event and event["source_version"] != self.source_version(record):
            return dict(status="blocked", selected=view, origin=origin, event=event, stale=True)
        return dict(
            status=event["status"] if event else status,
            selected=event["retained"] if event else view,
            origin=origin,
            event=event,
            stale=False,
        )

    def summary(self, record, latest):
        state = self.state(record, latest)
        return dict(
            id=record["id"],
            persee_id=record["persee_id"],
            title=record["metadata"]["title"],
            volume=record["metadata"]["volume"],
            pages=[record["metadata"]["page_start"], record["metadata"]["page_end"]],
            status=state["status"],
            alignment=record["alignment_status"],
            priority=record["review_priority"],
            batch=record["id"] in self.batch_map,
        )

    def listing(self):
        latest = self.latest()
        return [self.summary(r, latest) for r in self.records]

    def document(self, key, radius=6, draft_start=None, draft_end=None):
        r = self.by_id[key]
        v = r["metadata"]["volume"]
        state = self.state(r)
        span = dict(state["selected"] or {})
        for which, identifier in [("start", draft_start), ("end", draft_end)]:
            if identifier:
                self.resolve(r, identifier)
                span[which + "_id"] = identifier
        radius = max(2, min(int(radius), 2000))
        panels = {}
        for which, page in [
            ("start", r["metadata"]["page_start"]),
            ("end", r["metadata"]["page_end"]),
        ]:
            anchor = self.block_maps[v].get(span.get(which + "_id"))
            if anchor is None:
                anchor = next(
                    (b for b in self.blocks[v] if b["page"].get("page") == page), self.blocks[v][0]
                )
            i = anchor["index"]
            panels[which] = dict(
                anchor_id=anchor["id"],
                blocks=self.blocks[v][max(0, i - radius) : i + radius + 1],
                more_before=i - radius > 0,
                more_after=i + radius + 1 < len(self.blocks[v]),
            )
        alternatives = []
        for c in r["candidates"]:
            alternatives.append(
                dict(
                    title=c["title"],
                    xpath=c["anchor_xpath"],
                    score=c["score"],
                    span=self.span_view(
                        r, dict(start=c.get("display_start", c["start"]), end=c["leaf_end"])
                    ),
                )
            )
        events = [e for e in self.history() if e["document_id"] == key]
        return dict(
            record=r,
            state=state,
            panels=panels,
            radius=radius,
            alternatives=alternatives,
            source_version=self.source_version(r),
            history=events,
            batch=self.batch_map.get(key),
            offsets="Unicode codepoints, half-open source range; last selected block included",
        )

    def resolve(self, record, identifier):
        b = self.block_maps[record["metadata"]["volume"]].get(identifier)
        if not b or b["tag"] == "pb" or not b["text"].strip():
            raise ValueError("Select an existing content block from this volume")
        return b

    def save_decision(self, payload):
        r = self.by_id[payload["document_id"]]
        if payload.get("source_version") != self.source_version(r):
            raise Conflict("Sources changed; reload before recording")
        actor = str(payload.get("reviewer", "")).strip()
        note = str(payload.get("note", ""))
        if not actor or len(actor) > 160 or len(note) > 8000:
            raise ValueError("Reviewer required; note max 8000 characters")
        endpoint = payload.get("endpoint_decisions", {})
        choices = {"accepted", "corrected", "uncertain", "inside_block", "blocked"}
        if set(endpoint) != {"start", "end"} or any(x not in choices for x in endpoint.values()):
            raise ValueError("Both endpoint decisions are required")
        selected = {}
        for k in ["start", "end"]:
            ident = payload.get(k + "_id")
            selected[k + "_id"] = self.resolve(r, ident)["id"] if ident else None
        if all(selected.values()):
            a = self.resolve(r, selected["start_id"])["start"]
            z = self.resolve(r, selected["end_id"])["end"]
            if a >= z:
                raise ValueError("Start must precede end")
            selected.update(start=a, end=z, inside_block=False)
        else:
            selected.update(start=None, end=None, inside_block=True)
        if "blocked" in endpoint.values():
            status = "blocked"
        elif any(x in {"uncertain", "inside_block"} for x in endpoint.values()):
            status = "uncertain"
        else:
            if payload.get("human_confirmation") is not True or not all(
                selected[k] for k in ["start_id", "end_id"]
            ):
                raise ValueError("Explicit human confirmation and two existing blocks required")
            status = "human_validated"
        seconds = payload.get("active_seconds", 0)
        if (
            isinstance(seconds, bool)
            or not isinstance(seconds, (float, int))
            or not math.isfinite(seconds)
            or not 0 <= seconds <= 86400
        ):
            raise ValueError("Invalid measured time")
        base, _, origin = self.base(r)
        automatic = self.span_view(r, r["boundaries"].get("proposal"))
        initial = self.span_view(r, base)
        for k in ["start", "end"]:
            if endpoint[k] == "accepted" and (
                not initial
                or initial.get(k + "_id") != selected.get(k + "_id")
                or initial.get(k + "_inside_block", initial["inside_block"])
            ):
                raise ValueError(
                    "Accepted endpoint must match the complete initial block; otherwise choose corrected/inside block"
                )
        with self.locked_journal() as f:
            history = self.history()
            prev = next((e for e in reversed(history) if e["document_id"] == r["id"]), None)
            if payload.get("previous_event_id") != (prev["id"] if prev else None):
                raise Conflict("A newer decision exists; reload to review it")
            event = dict(
                id=str(uuid.uuid4()),
                document_id=r["id"],
                persee_id=r["persee_id"],
                previous_event_id=prev["id"] if prev else None,
                previous_hash=history[-1]["event_hash"] if history else None,
                date=datetime.now(timezone.utc).isoformat(),
                reviewer=actor,
                actor_type="human",
                human_confirmation=payload.get("human_confirmation") is True,
                automatic_initial=automatic,
                reference_initial=initial,
                reference_origin=origin,
                retained=selected,
                endpoint_decisions=endpoint,
                endpoint_changed={
                    k: selected.get(k + "_id") != (initial or {}).get(k + "_id")
                    for k in ["start", "end"]
                },
                status=status,
                note=note,
                source_version=self.source_version(r),
                tool_version=VERSION,
                active_seconds=round(seconds, 3),
                time_method="browser focused/visible activity; pauses after 60s inactivity; exploratory estimate",
            )
            event["event_hash"] = sha(json.dumps(event, sort_keys=True, ensure_ascii=False))
            f.seek(0, os.SEEK_END)
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return event

    def stats(self):
        events = self.history()
        latest = self.latest()
        return dict(
            events=len(events),
            examined_documents=len(latest),
            human_validated=sum(e["status"] == "human_validated" for e in latest.values()),
            uncertain=sum(e["status"] == "uncertain" for e in latest.values()),
            blocked=sum(e["status"] == "blocked" for e in latest.values()),
            accepted_endpoints=sum(
                list(e["endpoint_decisions"].values()).count("accepted") for e in latest.values()
            ),
            corrected_endpoints=sum(
                e["endpoint_decisions"][k] == "corrected"
                and e.get("endpoint_changed", {}).get(
                    k, e["retained"].get(k + "_id") != (e["reference_initial"] or {}).get(k + "_id")
                )
                for e in latest.values()
                for k in ["start", "end"]
            ),
            measured_active_seconds=sum(e["active_seconds"] for e in events),
            warning="User activity estimate, not script runtime or independent time study",
        )
