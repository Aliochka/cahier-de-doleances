"""Global, isolated extraction using the existing registry, segmenter and human journals."""

import argparse
import gzip
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "tools/document-review"))
from articles import INPUT, Articles, canonical, subtract  # noqa: E402
from boundary_rules import effective  # noqa: E402
from boundary_rules import plan as boundary_plan  # noqa: E402
from boundary_rules import summary as boundary_summary  # noqa: E402
from reviewlib import AUDITS, PRIVATE, Store, module, rows, sha  # noqa: E402
from segmentation import VERSION as SEGMENTER_VERSION  # noqa: E402
from segmentation import run as segment  # noqa: E402

VERSION = "global-corpus-3"
CURRENT = BASE / "data/corpus/current.json"


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def jsonl(path, values):
    with Path(path).open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
            for v in values:
                compressed.write((canonical(v) + "\n").encode())


def current_directory():
    if not CURRENT.exists():
        return None
    path = (BASE / json.loads(CURRENT.read_text())["directory"]).resolve()
    if BASE.resolve() not in path.parents:
        raise ValueError("Invalid local corpus pointer")
    if not (path / "complete.json").exists():
        raise ValueError("Incomplete corpus")
    return path


def input_paths(store):
    return [
        BASE / "data/registry/registry.jsonl.gz",
        store.journal,
        PRIVATE / "article-decisions.jsonl",
        BASE / "extraction/segmentation.py",
        BASE / "extraction/boundary_rules.py",
        BASE / "extraction/documentary_finalization.py",
        BASE / "extraction/documentary-finalization.json",
        AUDITS / "1789-extraction-v2/rules_v2.py",
        AUDITS / "1789-extraction-200/rules.py",
        Path(__file__),
        BASE / "tools/document-review/articles.py",
        BASE / "tools/document-review/reviewlib.py",
        *(
            INPUT / n
            for n in [
                "parents.jsonl.gz",
                "units-A.jsonl.gz",
                "units-B.jsonl.gz",
                "units-C.jsonl.gz",
            ]
        ),
        *(s.path for s in store.sources.values()),
    ]


def create_parent(store, record, state):
    span = state["selected"]
    v = record["metadata"]["volume"]
    source = store.sources[v]
    a, z = span["start"], span["end"]
    if not (type(a) is int and type(z) is int and 0 <= a < z <= len(source.text)):
        raise ValueError("Invalid source extent")
    bs = store.selected_blocks(v, a, z)
    divisions = []
    blocks = []
    rules = module("production_existing_v2_roles", AUDITS / "1789-extraction-v2/rules_v2.py")
    v1 = sys.modules["rules"]
    first = True
    for b in bs:
        node = source.node(b["xpath"])
        ancestors = node.xpath('ancestor::*[starts-with(local-name(),"div")]')
        div = source.tree.getpath(ancestors[-1]) if ancestors else "body"
        if div not in divisions:
            divisions.append(div)
        role = v1.role(node, first=first and b["tag"] == "p")
        if b["tag"] == "p":
            first = False
        blocks.append(
            {
                **b,
                "start": max(a, b["start"]),
                "end": min(z, b["end"]),
                "division": divisions.index(div),
                "role": role,
            }
        )
    refined = {
        b["xpath"]: b["role"]
        for b in rules.role_blocks(source, dict(start=a, end=z, divisions=divisions))
    }
    for b in blocks:
        b["role"] = refined.get(b["xpath"], b["role"])
    notes = {}
    for b in bs:
        node = source.node(b["xpath"])
        for n in [node] if b["tag"] == "note" else node.iter("note"):
            x, y = source.span(n)
            if a <= x < y <= z:
                notes[x, y] = dict(
                    start=x, end=y, xpath=source.tree.getpath(n), role="XML_editorial_note"
                )
    extent = "ap1789-parent-version:" + sha(f"{record['id']}|{source.sha256}|{a}|{z}")[:24]
    sections = []
    headings = [b for b in blocks if b["role"] in {"heading", "section_heading"}]
    for i, b in enumerate(headings):
        sections.append(
            dict(
                id=extent + ":section:" + sha(b["xpath"])[:12],
                heading=source.text[b["start"] : b["end"]],
                start=b["start"],
                end=headings[i + 1]["start"] if i + 1 < len(headings) else z,
                xpath=b["xpath"],
                status="XML_or_role_proposal_not_human_verified",
            )
        )
    return dict(
        id=record["id"],
        corpus_id=record["corpus_id"],
        extent_id=extent,
        volume=v,
        persee_id=record["persee_id"],
        metadata=record["metadata"],
        source=record["source"],
        start=a,
        end=z,
        full_text=source.text[a:z],
        text_sha256=sha(source.text[a:z]),
        boundary_status=state["status"],
        boundary_origin=state["origin"],
        boundary_event_id=(state["event"] or {}).get("id"),
        automatic_original=record["boundaries"].get("proposal"),
        source_version=store.source_version(record),
        divisions=divisions,
        blocks=[{k: b[k] for k in ["id", "xpath", "start", "end", "tag", "role"]} for b in blocks],
        annotations=list(notes.values()),
        sections=sections,
        legacy_parent_ids=[],
        unit_ids=[],
    )


def make_units(store, parent, proposed):
    source = store.sources[parent["volume"]]
    a, z = parent["start"], parent["end"]
    units = []

    def make(kind, x, y, spans, status, label=None, number=None, reason=None):
        if not spans:
            return
        text = "".join(source.text[c:d] for c, d in spans)
        if kind == "article" and not text.strip():
            raise ValueError("Empty article")
        uid = (
            "ap1789-global-unit-1:"
            + sha(canonical([parent["extent_id"], kind, spans, SEGMENTER_VERSION]))[:28]
        )
        section = next((s for s in reversed(parent["sections"]) if s["start"] <= x), None)
        units.append(
            dict(
                id=uid,
                parent_id=parent["id"],
                parent_extent_id=parent["extent_id"],
                corpus_id=parent["corpus_id"],
                type=kind,
                status=status,
                verification="automatic_not_human_verified",
                human_validated=False,
                historical_number=number,
                label_exact=label,
                text=text,
                text_sha256=sha(text),
                start=x,
                end=y,
                parent_start=x - a,
                parent_end=y - a,
                text_spans=spans,
                parent_text_spans=[[c - a, d - a] for c, d in spans],
                xml_blocks=[
                    dict(
                        id=b["id"], xpath=b["xpath"], start=max(x, b["start"]), end=min(y, b["end"])
                    )
                    for b in store.selected_blocks(parent["volume"], x, y)
                    if b["tag"] != "pb"
                ],
                pages=source.pages_for(x, y),
                source=parent["source"],
                section_id=section["id"] if section else None,
                extraction_version=VERSION,
                segmentation_version=SEGMENTER_VERSION,
                legacy_unit_ids=[],
                review_reason=reason,
                neighbour_order_status="technical_source_order_not_certified_historical_succession",
            )
        )

    for u in proposed:
        label = u.get("label_exact")
        marker = u.get("marker")
        if marker:
            number = marker["historical_number"]
        else:
            m = re.search(r"(?<!\w)\d+(?:er|re|e)?", label or "")
            number = m.group() if m else None
        make(
            "article",
            u["start"],
            u["end"],
            u["spans"],
            "B",
            label,
            number,
            "Existing segmenter proposal; not individually certified",
        )
    covered = [(x, y) for u in units for x, y in u["text_spans"]]
    for section in parent["sections"]:
        x, y = section["start"], section["end"]
        if y - x >= 80 and not any(c < y and x < d for c, d in covered):
            make(
                "section",
                x,
                y,
                [[x, y]],
                "B",
                reason="Historical/XML heading scope proposed, not a fabricated article",
            )
            covered.append((x, y))
    for x, y in subtract([[a, z]], covered):
        cursor = x
        for stop in [b["end"] for b in parent["blocks"] if x < b["end"] < y] + [y]:
            if stop - cursor >= 1800 or stop == y:
                make(
                    "technical_passage",
                    cursor,
                    stop,
                    [[cursor, stop]],
                    "C",
                    reason="Unsegmented exact source complement; not an historical article",
                )
                cursor = stop
    units.sort(key=lambda u: (u["start"], u["end"]))
    for i, u in enumerate(units):
        u.update(
            order=i + 1,
            previous_unit_id=units[i - 1]["id"] if i else None,
            next_unit_id=units[i + 1]["id"] if i + 1 < len(units) else None,
        )
    parent["unit_ids"] = [u["id"] for u in units]
    return units


def parent_problems(record, state):
    issues = list(
        dict.fromkeys(
            record.get("anomalies", [])
            + (record["boundaries"].get("proposal") or {}).get("flags", [])
        )
    )
    if state["stale"]:
        issues.append("stale_parent_decision")
    if record["alignment_status"] not in {"fort", "probable"}:
        issues.append("identity_" + record["alignment_status"])
    if state["status"] in {"uncertain", "blocked"}:
        issues.append("parent_" + state["status"])
    return issues


def extract_one(store, record, state, legacy=None, legacy_units=None):
    original_kind = record["document_kind"]
    if record.get("document_kind_reference"):
        record = {**record, "document_kind": record["document_kind_reference"]}
    item = dict(
        id=record["id"],
        persee_id=record["persee_id"],
        volume=record["metadata"]["volume"],
        title=record["metadata"]["title"],
        document_kind=record["document_kind"],
        document_kind_original=original_kind,
        document_kind_reference=record.get("document_kind_reference"),
        classification_origin="Codex_documentary_reference"
        if record.get("document_kind_reference")
        else "registry_automatic_hypothesis",
        metadata=record["metadata"],
        alignment_status=record["alignment_status"],
        boundary_proposal=record["boundaries"],
        alignment_candidates=record.get("candidates", []),
        source=record["source"],
        anomalies=parent_problems(record, state),
        boundary_class="unresolved",
        extraction_state="unresolved",
        parent_id=None,
    )
    if record["document_kind"] == "notice_absence":
        item["extraction_state"] = "absence_notice_not_a_cahier"
        return item, None, [], []
    span = state["selected"]
    if not span or span.get("start") is None or span.get("end") is None:
        return item, None, [], []
    try:
        if (
            legacy
            and state["status"] == "human_validated"
            and (span["start"], span["end"]) != (legacy["start"], legacy["end"])
        ):
            raise ValueError(
                "Protected legacy parent differs from the latest human boundary: explicit article reconciliation required; no automatic overwrite"
            )
        parent = dict(legacy) if legacy else create_parent(store, record, state)
        parent["document_kind"] = record["document_kind"]
        parent["anomalies"] = list(item["anomalies"])
        parent["boundary_class"] = (
            "human_validated"
            if state["status"] == "human_validated"
            else "automatic_suspect"
            if item["anomalies"]
            or state["status"] in {"uncertain", "blocked"}
            or record["alignment_status"] != "fort"
            else "automatic_no_alert"
        )
        if state["status"] in {"uncertain", "blocked"}:
            parent["boundary_class"] = "uncertain"
        parent["extraction_state"] = (
            "established_parent" if parent["boundary_class"] == "human_validated" else "provisional"
        )
        allow = (
            state["status"] not in {"uncertain", "blocked"}
            and (
                record["alignment_status"] in {"fort", "probable"}
                or state["status"] in {"human_validated", "codex_reviewed"}
            )
            and record["document_kind"] not in {"liste", "autre_document"}
        )
        raw = []
        if allow:
            try:
                result = segment(store, parent)
                raw = result["new"]
                parent["segmentation_alerts"] = [
                    c for c in result["candidates"] if c["confidence"] == "suspect"
                ]
            except (AssertionError, ValueError, KeyError, IndexError) as exc:
                parent["anomalies"].append("segmentation_failure:" + type(exc).__name__)
                parent["boundary_class"] = (
                    "automatic_suspect"
                    if state["status"] != "human_validated"
                    else "human_validated"
                )
                parent["segmentation_error"] = str(exc)
        else:
            parent["anomalies"].append("articles_withheld_pending_documentary_review")
        if legacy:
            own = list(legacy_units)
            parent["segmentation_policy"] = (
                "Original baseline retained for journal replay and inherited references; new OCR proposals stored separately"
            )
        else:
            own = make_units(store, parent, raw)
        item.update(
            parent_id=parent["id"],
            boundary_class=parent["boundary_class"],
            extraction_state=parent["extraction_state"],
            start=parent["start"],
            end=parent["end"],
            anomalies=parent["anomalies"],
        )
        return item, parent, own, raw
    except (ValueError, KeyError, IndexError) as exc:
        item["anomalies"].append("extraction_error:" + type(exc).__name__)
        item["error"] = str(exc)
        return item, None, [], []


def overlaps(parents, inventory):
    inv = {r["id"]: r for r in inventory}
    pairs = []
    by_volume = defaultdict(list)
    for p in parents:
        by_volume[p["volume"]].append(p)
    for volume, ps in by_volume.items():
        active = []
        for p in sorted(ps, key=lambda q: (q["start"], q["end"])):
            active = [q for q in active if q["end"] > p["start"]]
            for q in active:
                pair = dict(
                    volume=volume,
                    left_id=q["id"],
                    right_id=p["id"],
                    start=max(p["start"], q["start"]),
                    end=min(p["end"], q["end"]),
                    kind="identical_extent"
                    if (p["start"], p["end"]) == (q["start"], q["end"])
                    else "containment"
                    if q["end"] >= p["end"]
                    else "partial_overlap",
                    status="unresolved_not_silently_deduplicated",
                )
                pairs.append(pair)
                for r in [p, q]:
                    r.setdefault("overlap_ids", []).append(q["id"] if r is p else p["id"])
                    if "overlapping_document_proposals" not in r["anomalies"]:
                        r["anomalies"].append("overlapping_document_proposals")
                    if r["boundary_class"] == "automatic_no_alert":
                        r["boundary_class"] = "automatic_suspect"
                    inv[r["id"]]["boundary_class"] = r["boundary_class"]
                    inv[r["id"]]["anomalies"] = r["anomalies"]
                if (
                    pair["kind"] == "containment"
                    and p["document_kind"] != "cahier_autonome_probable"
                ):
                    p.setdefault("related_document_candidates", []).append(
                        dict(
                            id=q["id"],
                            relation="contained_source_interval_not_certified_attachment",
                        )
                    )
            active.append(p)
    return pairs


def write_core(out, parents, units):
    jsonl(out / "parents.jsonl.gz", parents)
    for status in "ABC":
        jsonl(out / f"units-{status}.jsonl.gz", [u for u in units if u["status"] == status])


def verify_corpus(out, store=None):
    store = store or Store()
    resolutions_path = out / "boundary-resolutions.jsonl.gz"
    if resolutions_path.exists():
        store.automatic_corrections = {r["document_id"]: r for r in rows(resolutions_path)}
    engine = Articles(store, directory=out)
    inventory = rows(out / "inventory.jsonl.gz")
    parents = engine.parents
    assert len(inventory) == 1305 and len({r["id"] for r in inventory}) == 1305
    assert set(parents).issubset({r["id"] for r in inventory})
    events = engine.log.history()
    human_reference = {}
    for event in events:
        for old in event["before"]:
            human_reference.pop((event["document_id"], old["id"]), None)
        for new in event["after"]:
            human_reference[event["document_id"], new["id"]] = new
    checked_humans = 0
    current = []
    counts = Counter()
    volumes = defaultdict(Counter)
    problems = []
    duplicate_spans = defaultdict(list)
    for key, p in parents.items():
        parent, records, history, head, stale = engine.state(key, events)
        assert parent["volume"] == store.by_id[key]["metadata"]["volume"]
        assert parent["persee_id"] == store.by_id[key]["persee_id"]
        engine.check(parent, list(records.values()))
        assert not stale, (key, "stale article history")
        for record in records.values():
            if record["review_status"] in {"human_validated", "human_corrected"}:
                assert engine.parent_version(p)["compatible"], (
                    "A human article requires explicit reconciliation with the changed parent"
                )
                assert (key, record["id"]) in human_reference and canonical(record) == canonical(
                    human_reference[key, record["id"]]
                ), "Human record changed"
                if record["type"] == "article":
                    checked_humans += 1
        flags = engine.anomalies(p, list(records.values()))
        ordered = sorted(
            records.values(), key=lambda r: (r["spans"][0][0], r["spans"][-1][1], r["id"])
        )
        for i, r in enumerate(ordered):
            text = engine.text(p, r)
            a, z = r["spans"][0][0], r["spans"][-1][1]
            assert r["type"] != "article" or text.strip()
            alerts = list(flags[r["id"]])
            human = r["review_status"] in {"human_validated", "human_corrected"}
            if (
                r["type"] == "article"
                and len(text) > 12000
                and "unusually_long_article_over_12000_chars" not in alerts
            ):
                alerts.append("unusually_long_article_over_12000_chars")
            row = dict(
                r,
                text=text,
                text_sha256=sha(text),
                start=a,
                end=z,
                parent_start=a - p["start"],
                parent_end=z - p["start"],
                pages=store.sources[p["volume"]].pages_for(a, z),
                volume=p["volume"],
                parent_boundary_class=p["boundary_class"],
                documentary_anomalies=p.get("anomalies", []),
                source=p["source"],
                order=i + 1,
                previous_unit_id=ordered[i - 1]["id"] if i else None,
                next_unit_id=ordered[i + 1]["id"] if i + 1 < len(ordered) else None,
                human_validated=human,
                anomalies=alerts,
            )
            current.append(row)
            counts[r["type"]] += 1
            volumes[p["volume"]][r["type"]] += 1
            if r["type"] == "article":
                counts["human_articles" if human else "automatic_articles"] += 1
                volumes[p["volume"]]["human_articles" if human else "automatic_articles"] += 1
                if alerts:
                    counts["articles_with_anomalies"] += 1
                    volumes[p["volume"]]["articles_with_anomalies"] += 1
                duplicate_spans[(p["source"]["source_sha256"], canonical(r["spans"]))].append(
                    r["id"]
                )
            if alerts:
                problems.append(
                    dict(
                        document_id=key,
                        unit_id=r["id"],
                        severity="segmentation_review",
                        anomalies=alerts,
                    )
                )
    expected = sum(
        r["type"] == "article" and r["review_status"] in {"human_validated", "human_corrected"}
        for r in human_reference.values()
    )
    assert checked_humans == expected, "A current human article disappeared"
    assert len({u["id"] for u in current}) == len(current)
    duplicates = [
        dict(
            unit_ids=ids,
            source_sha256=source,
            spans=json.loads(spans),
            status="same_source_in_multiple_documents_review_required",
        )
        for (source, spans), ids in duplicate_spans.items()
        if len(ids) > 1
    ]
    return engine, current, problems, duplicates, counts, volumes


def documentary_review(inventory, resolutions, pairs):
    """Document-level priorities, deliberately separate from article segmentation alerts."""
    explanations = {r["document_id"]: r for r in resolutions}
    overlaps_by_id = defaultdict(list)
    for pair in pairs:
        for key in [pair["left_id"], pair["right_id"]]:
            overlaps_by_id[key].append(pair)
    queue = []
    for r in inventory:
        x = explanations[r["id"]]
        flags = set(r["anomalies"])
        kind = r["document_kind"]
        if (
            r["boundary_class"] == "human_validated"
            or r["extraction_state"] == "absence_notice_not_a_cahier"
        ):
            priority = (
                "high"
                if any(c.get("proposed") for c in x["conflicts"])
                and r["boundary_class"] == "human_validated"
                else "none"
            )
            reasons = [
                "human_boundary_preserved_with_documentary_alternative"
                if priority == "high"
                else "human_boundary_preserved"
                if r["boundary_class"] == "human_validated"
                else "document_announced_absent"
            ]
        elif (
            overlaps_by_id[r["id"]]
            or any(f.startswith("identity_") for f in flags)
            or flags
            & {
                "new_control_identity_error",
                "new_control_boundary_incorrect",
                "new_control_source_composite_or_interleaved_columns",
                "parent_uncertain",
            }
        ):
            priority = "high"
            reasons = sorted(
                flags
                | ({"overlap_requires_attribution_review"} if overlaps_by_id[r["id"]] else set())
            )
        elif r["parent_id"] is None:
            priority = "medium"
            reasons = [
                "associated_document_not_located"
                if kind in {"liste", "document_associe", "proces_verbal"}
                else "cahier_not_located"
            ]
        elif (
            r["alignment_status"] == "probable"
            or x["conflicts"]
            or flags
            & {
                "end_page_mismatch_requires_review",
                "following_section_or_attached_piece_within_metadata_pages",
                "new_control_boundary_uncertain",
                "new_control_classification_disagreement",
                "same_primary_anchor_multiple_notices",
            }
        ):
            priority = "medium"
            reasons = sorted(
                flags
                | ({"documentary_alternatives_require_review"} if x["conflicts"] else set())
                | (
                    {"alignment_probable_not_independently_established"}
                    if r["alignment_status"] == "probable"
                    else set()
                )
            )
        else:
            priority = "low"
            reasons = sorted(flags) or ["sampling_only_no_documentary_alert_detected"]
        queue.append(
            dict(
                document_id=r["id"],
                persee_id=r["persee_id"],
                title=r["title"],
                volume=r["volume"],
                priority=priority,
                mandatory_review=priority in {"high", "medium"},
                reasons=reasons,
                corrected=x["changed"],
                resolved_alerts=x["resolved_alerts"],
                conflicts=x["conflicts"],
                url="/?document=" + r["id"],
                overlaps=overlaps_by_id[r["id"]],
            )
        )
    order = {"high": 0, "medium": 1, "low": 2, "none": 3}
    return sorted(queue, key=lambda r: (order[r["priority"]], r["volume"], r["document_id"]))


def build(output=None, resume=False, activate=True):
    started = time.perf_counter()
    store = Store()
    base = Articles(store)
    paths = input_paths(store)
    fingerprints = {str(p.relative_to(BASE.parent)): sha(p.read_bytes()) for p in paths}
    fingerprint = sha(canonical(dict(version=VERSION, inputs=fingerprints)))
    out = Path(output) if output else BASE / "data/corpus" / f"{VERSION}-{fingerprint[:12]}"
    if (out / "complete.json").exists():
        raise ValueError(
            "Immutable output exists; use --verify-only or select a new output directory"
        )
    out.mkdir(parents=True, exist_ok=True)
    checkpoint = out / "checkpoints"
    checkpoint.mkdir(exist_ok=True)
    frozen = out / "inputs.json"
    if frozen.exists():
        assert json.loads(frozen.read_text())["fingerprint"] == fingerprint, "Resume inputs changed"
    else:
        dump(
            frozen,
            dict(
                fingerprint=fingerprint,
                version=VERSION,
                source_revision="926fd3cd986a3c3d411e93d1845fff6475cb2602",
                files=fingerprints,
            ),
        )
        snapshots = out / ".private"
        snapshots.mkdir(exist_ok=True)
        for p in [store.journal, base.log.journal]:
            (snapshots / p.name).write_bytes(p.read_bytes())
    resolutions = boundary_plan(store)
    store.automatic_corrections = {r["document_id"]: r for r in resolutions}
    jsonl(out / "boundary-resolutions.jsonl.gz", resolutions)
    latest = store.latest()
    all_inventory = []
    all_parents = []
    all_units = []
    all_raw = []
    legacy_units = {key: [] for key in base.parents}
    for status in "ABC":
        for u in rows(INPUT / f"units-{status}.jsonl.gz"):
            legacy_units[u["parent_id"]].append(u)
    for volume in range(1, 7):
        path = checkpoint / f"volume-{volume}.jsonl.gz"
        if resume and path.exists():
            batch = rows(path)
        else:
            batch = []
            for r in [r for r in store.records if r["metadata"]["volume"] == volume]:
                entry, parent, own, raw = extract_one(
                    store,
                    effective(r, store.automatic_corrections[r["id"]]),
                    store.state(r, latest),
                    base.parents.get(r["id"]),
                    legacy_units.get(r["id"]),
                )
                resolution = store.automatic_corrections[r["id"]]
                entry["document_kind_original"] = r["document_kind"]
                entry["documentary_resolution"] = resolution
                entry["original_registry_boundaries"] = r["boundaries"]
                if parent:
                    parent["documentary_resolution"] = resolution
                batch.append(dict(inventory=entry, parent=parent, units=own, raw=raw))
            jsonl(path, batch)
        for r in batch:
            all_inventory.append(r["inventory"])
            if r["parent"]:
                all_parents.append(r["parent"])
                all_units.extend(r["units"])
                all_raw.extend(dict(parent_id=r["parent"]["id"], **u) for u in r["raw"])
        print(
            f"Volume {volume}: {len(batch)} notices, {sum(r['parent'] is not None for r in batch)} textes, {sum(len(r['units']) for r in batch)} unités",
            flush=True,
        )
    pairs = overlaps(all_parents, all_inventory)
    write_core(out, all_parents, all_units)
    jsonl(out / "inventory.jsonl.gz", all_inventory)
    jsonl(out / "automatic-proposals.jsonl.gz", all_raw)
    jsonl(out / "document-overlaps.jsonl.gz", pairs)
    jsonl(
        out / "provisional-documents.jsonl.gz",
        [
            dict(
                id=p["id"],
                volume=p["volume"],
                boundary_class=p["boundary_class"],
                anomalies=p["anomalies"],
                start=p["start"],
                end=p["end"],
                source=p["source"],
            )
            for p in all_parents
            if p["boundary_class"] in {"automatic_suspect", "uncertain"}
        ],
    )
    documentary_reviews = documentary_review(all_inventory, resolutions, pairs)
    jsonl(out / "documentary-review.jsonl.gz", documentary_reviews)
    engine, current, problems, duplicates, counts, volumes = verify_corpus(out, store)
    jsonl(out / "units.jsonl.gz", current)
    jsonl(out / "duplicate-source-spans.jsonl.gz", duplicates)
    for p in all_parents:
        if p["anomalies"] or p["boundary_class"] in {"uncertain", "automatic_suspect"}:
            problems.append(
                dict(
                    document_id=p["id"],
                    severity="high_documentary",
                    anomalies=p["anomalies"],
                    boundary_class=p["boundary_class"],
                )
            )
    for row in all_inventory:
        if row["parent_id"] is None:
            problems.append(
                dict(
                    document_id=row["id"],
                    severity="informational_absence_notice"
                    if row["extraction_state"] == "absence_notice_not_a_cahier"
                    else "unresolved_document",
                    anomalies=row["anomalies"],
                    state=row["extraction_state"],
                )
            )
    problems.sort(
        key=lambda r: (
            {
                "unresolved_document": 0,
                "high_documentary": 1,
                "segmentation_review": 2,
                "informational_absence_notice": 3,
            }[r["severity"]],
            r["document_id"],
        )
    )
    jsonl(out / "review-queue.jsonl.gz", problems)
    uncovered = []
    parentvol = defaultdict(list)
    for p in all_parents:
        parentvol[p["volume"]].append([p["start"], p["end"]])
    for v, source in store.sources.items():
        for a, z in subtract([[0, len(source.text)]], parentvol[v]):
            uncovered.append(
                dict(
                    volume=v,
                    start=a,
                    end=z,
                    text=source.text[a:z],
                    source_sha256=source.sha256,
                    role="outside_extracted_documents_not_assumed_cahier",
                )
            )
    jsonl(out / "unassigned-source.jsonl.gz", uncovered)
    statuses = Counter(p["boundary_class"] for p in all_parents)
    # Source intervals outside the extracted parents remain exactly recoverable.
    for volume, source in store.sources.items():
        own = [(r["start"], r["end"]) for r in uncovered if r["volume"] == volume]
        merged = []
        for a, z in sorted(parentvol[volume]):
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], z)
            else:
                merged.append([a, z])
        assert sum(z - a for a, z in merged) + sum(z - a for a, z in own) == len(source.text)
    summary = dict(
        version=VERSION,
        documentary_repairs=boundary_summary(resolutions),
        documentary_review_levels=dict(Counter(r["priority"] for r in documentary_reviews)),
        notices_examined=len(all_inventory),
        document_kinds=dict(Counter(r["document_kind"] for r in all_inventory)),
        autonomous_probable=sum(
            r["document_kind"] == "cahier_autonome_probable" for r in all_inventory
        ),
        texts_extracted=len(all_parents),
        autonomous_texts_extracted=sum(
            p["document_kind"] == "cahier_autonome_probable" for p in all_parents
        ),
        boundary_classes=dict(statuses),
        unresolved_notices=sum(r["parent_id"] is None for r in all_inventory),
        absence_notices=sum(
            r["extraction_state"] == "absence_notice_not_a_cahier" for r in all_inventory
        ),
        unresolved_without_usable_span=sum(
            r["parent_id"] is None and r["extraction_state"] != "absence_notice_not_a_cahier"
            for r in all_inventory
        ),
        counts=dict(counts),
        by_volume={
            str(v): dict(
                notices=sum(r["volume"] == v for r in all_inventory),
                texts=sum(p["volume"] == v for p in all_parents),
                autonomous_texts=sum(
                    p["volume"] == v and p["document_kind"] == "cahier_autonome_probable"
                    for p in all_parents
                ),
                unresolved=sum(r["volume"] == v and r["parent_id"] is None for r in all_inventory),
                boundary_classes=dict(
                    Counter(p["boundary_class"] for p in all_parents if p["volume"] == v)
                ),
                **volumes[v],
            )
            for v in range(1, 7)
        },
        document_overlap_pairs=len(pairs),
        duplicate_source_span_groups=len(duplicates),
        total_parent_characters=sum(len(p["full_text"]) for p in all_parents),
        total_parent_utf8_bytes=sum(len(p["full_text"].encode()) for p in all_parents),
        unassigned_source_characters=sum(r["end"] - r["start"] for r in uncovered),
        review_queue_entries=len(problems),
        elapsed_seconds=time.perf_counter() - started,
        no_embeddings=True,
        no_index_preparation=True,
    )
    dump(out / "summary.json", summary)
    assert all(
        sha(p.read_bytes()) == fingerprints[str(p.relative_to(BASE.parent))] for p in paths
    ), "Protected input changed during build"
    dump(
        out / "complete.json",
        dict(
            input_fingerprint=fingerprint,
            files={
                p.name: sha(p.read_bytes())
                for p in out.iterdir()
                if p.is_file() and p.name != "complete.json"
            },
            human_preservation_verified=True,
            all_unit_source_coverage_verified=True,
        ),
    )
    if activate:
        CURRENT.parent.mkdir(parents=True, exist_ok=True)
        tmp = CURRENT.with_suffix(".tmp")
        dump(tmp, dict(directory=str(out.relative_to(BASE)), version=VERSION))
        os.replace(tmp, CURRENT)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path)
    p.add_argument("--resume", action="store_true")
    p.add_argument(
        "--no-activate",
        action="store_true",
        help="Build without changing the active local collection",
    )
    p.add_argument("--verify-only", type=Path)
    args = p.parse_args()
    if args.verify_only:
        _, current, _, _, counts, _ = verify_corpus(args.verify_only)
        materialized = rows(args.verify_only / "units.jsonl.gz")
        assert [canonical(u) for u in materialized] == [canonical(u) for u in current], (
            "Materialized corpus differs from current decisions; regenerate a version or export corrections"
        )
        complete = json.loads((args.verify_only / "complete.json").read_text())
        for name, digest in complete["files"].items():
            assert sha((args.verify_only / name).read_bytes()) == digest, name
        print(dict(counts))
        return
    build(args.output, args.resume, not args.no_activate)


if __name__ == "__main__":
    main()
