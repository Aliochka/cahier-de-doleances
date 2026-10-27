"""Production isolée, hypothèses automatiques puis application explicite des références."""

import collections
import datetime
import faulthandler
import gzip
import json
import re
import time

from common import (
    CORPUS,
    HERE,
    PILOT,
    REVISION,
    VERSION,
    compact,
    jlines,
    pages,
    read,
    rows,
    sha,
    source_ref,
    sources,
    write,
)
from fast_blocks import blocks, cache_nodes
from pilot_segment import subtract
from rules import INLINE_SIGN, segment
from rules import blocks as original_blocks


def gzip_rows(path, values):
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, filename="", mode="wb", mtime=0) as f:
            for value in values:
                f.write((json.dumps(value, ensure_ascii=False) + "\n").encode())


def document_id(s, c):
    return (
        f"ap1789-200-d1:{s.path.stem}:"
        + sha(f"{REVISION}|{s.sha256}|{c['divisions']}|{c['start']}|{c['end']}")[:20]
    )


def unit_id(did, u):
    return "ap1789-200-u1:" + sha(did)[:20] + ":" + sha(f"{u['start']}|{u['end']}")[:16]


def main():
    faulthandler.dump_traceback_later(30)
    clock = time.perf_counter()
    ss = sources()
    for source in ss.values():
        cache_nodes(source)
    print("Sources loaded", flush=True)
    selected = rows(HERE / "data/selection.jsonl")
    equality_checks = []
    for c in selected:
        if c["id"] in read(HERE / "protocol.json")["validation_ids"]:
            assert blocks(ss[c["volume"]], c) == original_blocks(ss[c["volume"]], c)
            equality_checks.append(c["id"])
    write(
        HERE / "data/block-cache-equivalence.json",
        dict(
            validation_candidates_checked=equality_checks,
            identical=True,
            change="pure memoization and first-child test, no classification or segmentation rule changed",
        ),
    )
    for name in ["freeze.json", "reference-freeze.json"]:
        assert all(sha((HERE / p).read_bytes()) == h for p, h in read(HERE / name)["files"].items())
    automatic = []
    auto_parents = []
    for index, c in enumerate(selected):
        if index % 20 == 0:
            print("Automatic candidates", index, flush=True)
        s = ss[c["volume"]]
        did = document_id(s, c)
        bs = blocks(s, c)
        proposals = segment(s, bs)
        auto_parents.append(
            dict(
                candidate_id=c["id"],
                document_id=did,
                volume=c["volume"],
                start=c["start"],
                end=c["end"],
                divisions=c["divisions"],
                full_text=s.text[c["start"] : c["end"]],
                blocks=bs,
            )
        )
        for u in proposals:
            automatic.append(
                dict(
                    u,
                    id=unit_id(did, u),
                    document_id=did,
                    candidate_id=c["id"],
                    volume=c["volume"],
                    status="B",
                    text=s.text[u["start"] : u["end"]],
                )
            )
    # Raw outputs are written before any decision or reference correction.
    jlines(HERE / "data/automatic-units.jsonl", automatic)
    print("Raw proposals saved", len(automatic), flush=True)
    gzip_rows(HERE / "data/automatic-parents.jsonl.gz", auto_parents)
    refs = {r["candidate_id"]: r for r in rows(HERE / "data/reference-documents.jsonl")}
    extra = HERE / "data/additional-parent-decisions.json"
    if extra.exists():
        refs.update({r["candidate_id"]: r for r in read(extra)})
    documents = []
    units = []
    retained = []
    crosswalk = []
    reviewlog = []
    for d in rows(PILOT / "data/documents.jsonl"):
        documents.append(
            dict(
                d,
                origin="inherited_pilot_30",
                record_status="prior_reviewed_document",
                candidate_id=None,
            )
        )
        crosswalk.append(
            dict(
                kind="legacy_parent",
                old_id=d["id"],
                new_id=d["id"],
                relation="unchanged_source_extent_and_id",
            )
        )
    for u in rows(PILOT / "data/units.jsonl"):
        units.append(
            dict(
                u,
                origin="inherited_pilot_30",
                validation_origin="previous_pilot_reference"
                if u["status"] == "A"
                else "previous_pilot_unverified",
            )
        )
        crosswalk.append(
            dict(
                kind="legacy_unit",
                old_id=u["id"],
                new_id=u["id"],
                relation="unchanged_source_extent_and_id",
            )
        )
    retained.extend(
        dict(r, origin="inherited_pilot_30")
        for r in rows(PILOT / "data/retained-unsegmented.jsonl")
    )
    for c in selected:
        s = ss[c["volume"]]
        ref = refs.get(c["id"])
        final = dict(c)
        original_id = document_id(s, c)
        if ref and ref["real"] and ref.get("parent_p"):
            final["start"], final["end"] = ref["parent_reference_span"]
        # Avoid changing a parent ID merely to trim source indentation.
        did = document_id(s, final)
        start, end = final["start"], final["end"]
        bs = blocks(s, final)
        title = c["title"]
        if title.strip().casefold() in {"cahier", "cahiers"}:
            first = s.node(c["xpath"]).find("p")
            title += " " + compact(first) if first is not None else ""
        status = (
            "quarantined_false_parent"
            if ref and not ref["real"]
            else "source_boundaries_reviewed"
            if ref
            else "automatic_unverified"
        )
        doc = dict(
            id=did,
            candidate_id=c["id"],
            corpus_id=CORPUS,
            origin="new_discovery",
            volume=c["volume"],
            title_display=title,
            full_text=s.text[start:end],
            full_text_sha256=sha(s.text[start:end]),
            source_text_start=start,
            source_text_end=end,
            divisions=c["divisions"],
            blocks=bs,
            pages=pages(s, start, end),
            metadata=dict(
                estate=None,
                estate_mention=c["estate_explicit"],
                estate_provenance="literal word in title/opening used for sampling; not a certified attribution of authorship",
                date=None,
            ),
            record_status=status,
            validation_split=c["validation_split"],
            uncertainties=c["uncertainties"] + (["not_documentarily_certified"] if not ref else []),
            method_version=VERSION,
            automatic_document_id=original_id,
            **source_ref(s),
        )
        if ref:
            doc["document_review"] = dict(
                classification=ref["kind"],
                reason=ref["reason"],
                reviewer=ref["reviewer"],
                boundary_scope="headings, opening, ending and neighboring titles reviewed; no complete OCR collation",
            )
        annotations = []
        for node in s.tree.xpath("//note"):
            a, b = s.span(node)
            if start <= a < b <= end:
                annotations.append(
                    dict(kind="editorial_note", start=a, end=b, xpath=s.tree.getpath(node))
                )
        for b in bs:
            if b["role"] not in {"body", "pb"}:
                annotations.append(
                    dict(kind=b["role"], start=b["start"], end=b["end"], xpath=b["xpath"])
                )
            if b["tag"] == "p" and b["role"] == "body":
                signature = INLINE_SIGN.search(s.text[b["start"] : b["end"]])
                if signature:
                    annotations.append(
                        dict(
                            kind="inline_signature_hypothesis",
                            start=b["start"] + signature.start(),
                            end=b["end"],
                            xpath=b["xpath"],
                        )
                    )
        sections = []
        for di, xp in enumerate(c["divisions"]):
            n = s.node(xp)
            a, b = s.span(n)
            sections.append(
                dict(
                    id="section-" + sha(did + xp)[:16],
                    kind="division" if di == 0 else "continuation_or_appendix_hypothesis",
                    xpath=xp,
                    start=max(a, start),
                    end=min(b, end),
                    title_exact=["".join(h.itertext()) for h in n.findall("head")],
                )
            )
        for b in bs:
            if b["role"] == "section_heading":
                sections.append(
                    dict(
                        id="section-" + sha(did + b["xpath"])[:16],
                        kind="paragraph_heading",
                        xpath=b["xpath"],
                        start=b["start"],
                        end=b["end"],
                        title_exact=s.text[b["start"] : b["end"]],
                    )
                )
        doc["sections"] = sections
        doc["annotations"] = annotations
        ps = [dict(u) for u in automatic if u["candidate_id"] == c["id"]]
        if ref:
            for w in ref["reference_windows"]:
                ps = [u for u in ps if not (u["start"] < w["end"] and u["end"] > w["start"])]
                for g in w["units"]:
                    ps.append(
                        dict(
                            g,
                            status="A",
                            rule="source_reference_before_prediction",
                            label_exact=None,
                        )
                    )
            if not ref["real"]:
                ps = []
        ps = [u for u in ps if start <= u["start"] < u["end"] <= end]
        ps.sort(key=lambda u: u["start"])
        final_units = []
        for order, u in enumerate(ps, 1):
            a, b = u["start"], u["end"]
            spans = subtract(
                a, b, [(n["start"], n["end"]) for n in annotations if n["kind"] == "editorial_note"]
            )
            text = "".join(s.text[x:y] for x, y in spans)
            label = u.get("label_exact")
            if label is None:
                m = re.match(
                    r"(?i)\s*(?:(?:Article|Art|Arf|Àri)['’.,\s]*(?:\d+(?:er|re|e)?|Ier|ler|il|er)?[.,;:]?|\d+\s*[°º®])",
                    s.text[a:b],
                )
                label = m.group() if m else None
            uid = unit_id(did, u)
            number = re.search(r"\d+", label or "")
            unit = dict(
                id=uid,
                document_id=did,
                candidate_id=c["id"],
                corpus_id=CORPUS,
                volume=c["volume"],
                order=order,
                status=u.get("status", "B"),
                validation_origin="Codex_held_out_source_reference"
                if u.get("status") == "A"
                else "automatic_not_individually_verified",
                rule=u["rule"],
                start=a,
                end=b,
                parent_start=a - start,
                parent_end=b - start,
                text_spans=spans,
                text=text,
                text_sha256=sha(text),
                label_exact=label,
                historical_number=number.group() if number else None,
                number_provenance="literal digits only; no OCR restoration",
                xml_blocks=u["xml_blocks"],
                pages=pages(s, a, b),
                method_version=VERSION,
                anchor="unit-" + uid.rsplit(":", 1)[-1],
                section_id=max(
                    (x for x in sections if x["start"] <= a),
                    key=lambda x: x["start"],
                    default=sections[0],
                )["id"],
                **source_ref(s),
            )
            final_units.append(unit)
        for i, u in enumerate(final_units):
            u["previous_unit_id"] = final_units[i - 1]["id"] if i else None
            u["next_unit_id"] = final_units[i + 1]["id"] if i + 1 < len(final_units) else None
        doc["unit_ids"] = [u["id"] for u in final_units]
        for raw in (u for u in automatic if u["candidate_id"] == c["id"]):
            matches = [
                u for u in final_units if u["start"] < raw["end"] and u["end"] > raw["start"]
            ]
            relation = (
                "same_id"
                if any(u["id"] == raw["id"] for u in matches)
                else "parent_id_changed_same_bounds"
                if any(u["start"] == raw["start"] and u["end"] == raw["end"] for u in matches)
                else "overlap_after_review"
                if matches
                else "excluded_or_retained_C"
            )
            crosswalk.append(
                dict(
                    kind="automatic_to_final_unit",
                    old_id=raw["id"],
                    new_ids=[u["id"] for u in matches],
                    candidate_id=c["id"],
                    relation=relation,
                    source_start=raw["start"],
                    source_end=raw["end"],
                )
            )
        units.extend(final_units)
        uncovered = subtract(start, end, [span for u in final_units for span in u["text_spans"]])
        for a, b in uncovered:
            if not s.text[a:b].strip():
                continue
            role = next(
                (x["role"] for x in bs if x["start"] <= a < x["end"]), "unclassified_retained"
            )
            retained.append(
                dict(
                    id="retained-" + sha(did + f"|{a}|{b}")[:20],
                    document_id=did,
                    corpus_id=CORPUS,
                    status="C",
                    kind="quarantined_false_parent_text"
                    if status == "quarantined_false_parent"
                    else "retained_range_not_certified_article",
                    role=role,
                    start=a,
                    end=b,
                    parent_start=a - start,
                    parent_end=b - start,
                    text=s.text[a:b],
                    volume=c["volume"],
                    source_sha256=s.sha256,
                    source_revision=REVISION,
                    xml_blocks=[x["xpath"] for x in bs if x["start"] < b and x["end"] > a],
                    pages=pages(s, a, b),
                    source_file=f"{s.path.stem}/{s.path.stem}.xml",
                    scan_url=f"https://purl.stanford.edu/{s.path.stem}",
                    method_version=VERSION,
                )
            )
        crosswalk.append(
            dict(
                kind="automatic_to_final_parent",
                candidate_id=c["id"],
                old_id=original_id,
                new_id=did,
                relation="parent_boundary_corrected"
                if original_id != did
                else "quarantined"
                if status == "quarantined_false_parent"
                else "same_extent",
            )
        )
        if ref:
            reviewlog.append(
                dict(
                    candidate_id=c["id"],
                    operation="held_out_source_review"
                    if c["validation_split"] == "held_out"
                    else "additional_source_heading_triage",
                    reference=ref["kind"],
                    parent_boundary_corrections=int(original_id != did),
                    gold_articles=sum(len(w["units"]) for w in ref["reference_windows"]),
                    judge="Codex non-independent",
                    human_validation_seconds=None,
                )
            )
        documents.append(doc)
    gzip_rows(HERE / "data/documents.jsonl.gz", documents)
    jlines(HERE / "data/units-A.jsonl", [u for u in units if u["status"] == "A"])
    gzip_rows(HERE / "data/units-B.jsonl.gz", [u for u in units if u["status"] == "B"])
    gzip_rows(HERE / "data/retained-C.jsonl.gz", retained)
    register = [
        {k: v for k, v in d.items() if k not in {"full_text", "blocks", "annotations"}}
        for d in documents
    ]
    write(HERE / "data/register.json", register)
    write(HERE / "data/crosswalk.json", crosswalk)
    write(
        HERE / "data/review-log.json",
        dict(
            operations=reviewlog,
            source_pack_started=read(HERE / "data/review-pack-provenance.json")["created_at"],
            reference_frozen=read(HERE / "reference-freeze.json")["created_at"],
            time_interpretation="timestamps of Codex workflow, not human validation durations",
            human_validation_seconds=None,
        ),
    )
    write(
        HERE / "data/extraction-summary.json",
        dict(
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            seconds=time.perf_counter() - clock,
            documents=len(documents),
            inherited=30,
            new=170,
            raw_new_article_proposals=len(automatic),
            statuses=dict(collections.Counter(u["status"] for u in units)),
            new_statuses=dict(
                collections.Counter(
                    u["status"] for u in units if u.get("origin") != "inherited_pilot_30"
                )
            ),
            retained_C_ranges=len(retained),
            parent_statuses=dict(collections.Counter(d["record_status"] for d in documents)),
            parent_corrections=sum(r["parent_boundary_corrections"] for r in reviewlog),
            new_reviewed_articles=sum(r["gold_articles"] for r in reviewlog),
        ),
    )
    print(
        "Extracted",
        len(documents),
        "registered records;",
        len(units),
        "A/B units;",
        len(retained),
        "retained C ranges",
    )
    faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    main()
