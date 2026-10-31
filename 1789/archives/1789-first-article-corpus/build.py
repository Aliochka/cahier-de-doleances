"""Reproducible corpus from established parent boundaries; no new detector or LLM."""

import argparse
import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parents[1] / "tools/document-review"
sys.path.insert(0, str(TOOL))
from reviewlib import AUDITS, Store, load, module, rows, sha  # noqa: E402

VERSION = "first-article-corpus-1.0"


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def jsonl(path, values):
    data = "".join(
        json.dumps(v, ensure_ascii=False, sort_keys=True) + "\n" for v in values
    ).encode()
    # mtime zero and no original name: byte-for-byte reproducible compressed output.
    path.write_bytes(gzip.compress(data, mtime=0))


def subtract(a, z, spans):
    cursor = a
    for x, y in sorted(spans):
        if y <= cursor or x >= z:
            continue
        if cursor < x:
            yield cursor, min(x, z)
        cursor = max(cursor, y)
    if cursor < z:
        yield cursor, z


def run(output=None, journal=None):
    out = Path(output) if output else HERE / "data"
    out.mkdir(parents=True, exist_ok=True)
    store = Store(journal)
    journal_snapshot = store.journal.read_bytes() if store.journal.exists() else b""
    # This loads the exact previous segmenter and role rules, never their main().
    segmenter = module("first_article_rules_v2", AUDITS / "1789-extraction-v2/rules_v2.py")
    v1 = sys.modules["rules"]
    selection = load(HERE / "data/selection.json")
    legacy_parents = rows(AUDITS / "1789-extraction-pilot/data/documents.jsonl")
    legacy_units = rows(AUDITS / "1789-extraction-pilot/data/units.jsonl")
    reexamine = {
        r["legacy_unit_id"]: r
        for r in rows(AUDITS / "1789-extraction-v2/data/19-diagnoses.jsonl")
        if r["reference_reexamination_requested"]
    }
    ref_units = [u for u in legacy_units if u["status"] == "A"]
    # Newer V2 reviewed source references can supplement, never erase legacy IDs.
    for u in rows(AUDITS / "1789-extraction-v2/data/corpus-A.jsonl"):
        ref_units.append(
            dict(
                u,
                source_sha256=u["source_sha256"],
                text_spans=u.get("text_spans_without_xml_notes", [[u["start"], u["end"]]]),
            )
        )
    parents = []
    units = []
    crosswalk = []
    withheld = []
    raw_proposals = []
    latest = store.latest()
    for entry in selection:
        record = store.by_id[entry["document_id"]]
        v = record["metadata"]["volume"]
        s = store.sources[v]
        state = store.state(record, latest)
        span = state["selected"]
        if (
            state["status"] not in {"codex_reviewed", "human_validated"}
            or state["stale"]
            or not span
            or span["start"] is None
        ):
            withheld.append(
                dict(
                    document_id=record["id"],
                    reason="Parent boundaries not established or later human uncertainty/block",
                    status=state["status"],
                )
            )
            continue
        a, z = span["start"], span["end"]
        if not 0 <= a < z <= len(s.text):
            raise ValueError("Invalid parent source range")
        bs = store.selected_blocks(v, a, z)
        # Infer XML roles with the existing role function; do not replace them with semantic labels.
        divisions = []
        role_blocks = []
        first_p = True
        for b in bs:
            n = s.node(b["xpath"])
            ancestors = n.xpath('ancestor::*[starts-with(local-name(),"div")]')
            div = s.tree.getpath(ancestors[-1]) if ancestors else "body"
            if div not in divisions:
                divisions.append(div)
            role = v1.role(n, first=first_p and b["tag"] == "p")
            if b["tag"] == "p":
                first_p = False
            role_blocks.append(
                dict(
                    b,
                    division=divisions.index(div),
                    role=role,
                    start=max(a, b["start"]),
                    end=min(z, b["end"]),
                )
            )
        # Apply V2's actual role refinement as well as segment(); no rediscovery.
        role_refined = segmenter.role_blocks(s, dict(start=a, end=z, divisions=divisions))
        roles = {b["xpath"]: b["role"] for b in role_refined}
        for b in role_blocks:
            b["role"] = roles.get(b["xpath"], b["role"])
        proposals = segmenter.segment(s, role_blocks)
        raw_proposals.extend(dict(document_id=record["id"], **p) for p in proposals)
        notes = []
        seen_notes = set()
        for b in bs:
            node = s.node(b["xpath"])
            for n in [node] if b["tag"] == "note" else list(node.iter("note")):
                x, y = s.span(n)
                key = (x, y)
                if key not in seen_notes and a <= x < y <= z:
                    notes.append(
                        dict(start=x, end=y, xpath=s.tree.getpath(n), role="XML_editorial_note")
                    )
                    seen_notes.add(key)
        reviewed = []
        for u in ref_units:
            if u["source_sha256"] != s.sha256 or not a <= u["start"] < u["end"] <= z:
                continue
            if any(x["start"] == u["start"] and x["end"] == u["end"] for x in reviewed):
                continue
            spans = u.get("text_spans", [[u["start"], u["end"]]])
            # Only reuse references that still reconstruct the exact historical text.
            if "".join(s.text[x:y] for x, y in spans) != u["text"]:
                continue
            reviewed.append(
                dict(
                    u,
                    spans=spans,
                    status="B" if u["id"] in reexamine else "A",
                    review_origin="Inherited Codex TEI boundary examination; not human validation",
                    pending_reason=reexamine.get(u["id"], {}).get("diagnosis"),
                )
            )
        reviewed.sort(key=lambda u: (u["start"], u["end"]))
        for left, right in zip(reviewed, reviewed[1:]):
            if left["end"] > right["start"]:
                raise ValueError("Conflicting old article references; resolve before extraction")
        article_candidates = list(reviewed)
        for p in proposals:
            if any(p["start"] < r["end"] and r["start"] < p["end"] for r in reviewed):
                continue
            spans = list(subtract(p["start"], p["end"], [(n["start"], n["end"]) for n in notes]))
            if not spans or not "".join(s.text[x:y] for x, y in spans).strip():
                continue
            article_candidates.append(
                dict(
                    p,
                    spans=spans,
                    status="B",
                    review_origin="automatic V2 proposal, not individually examined",
                )
            )
        article_candidates.sort(key=lambda u: (u["start"], u["end"]))
        extent_id = "ap1789-parent-version:" + sha(f"{record['id']}|{s.sha256}|{a}|{z}")[:24]
        parent = dict(
            id=record["id"],
            corpus_id=record["corpus_id"],
            extent_id=extent_id,
            volume=v,
            persee_id=record["persee_id"],
            metadata=record["metadata"],
            source=record["source"],
            start=a,
            end=z,
            full_text=s.text[a:z],
            text_sha256=sha(s.text[a:z]),
            boundary_status=state["status"],
            boundary_origin=state["origin"],
            boundary_event_id=(state["event"] or {}).get("id"),
            automatic_original=record["boundaries"].get("proposal"),
            source_version=store.source_version(record),
            divisions=divisions,
            blocks=[
                {k: b[k] for k in ["id", "xpath", "start", "end", "tag", "role"]}
                for b in role_blocks
            ],
            annotations=notes,
            sections=[],
            legacy_parent_ids=[],
            unit_ids=[],
            note="Entire selected source interval, including notes/signatures/annexes; Codex examination is not independent historical certification",
        )
        for old in legacy_parents:
            if (
                old["source_sha256"] == s.sha256
                and old["source_text_start"] < z
                and a < old["source_text_end"]
            ):
                parent["legacy_parent_ids"].append(
                    dict(
                        id=old["id"],
                        relation="exact"
                        if (a, z) == (old["source_text_start"], old["source_text_end"])
                        else "overlapping_extent_not_equivalent",
                    )
                )
        sections = [
            b
            for i, b in enumerate(role_blocks)
            if b["role"] in {"section_heading", "heading"} and b["tag"] != "pb" and i > 1
        ]
        for i, b in enumerate(sections):
            parent["sections"].append(
                dict(
                    id=extent_id + ":section:" + sha(b["xpath"])[:12],
                    heading=s.text[b["start"] : b["end"]],
                    start=b["start"],
                    end=sections[i + 1]["start"] if i + 1 < len(sections) else z,
                    xpath=b["xpath"],
                    status="explicit_XML_or_role_proposal_not_human_verified",
                )
            )
        own = []

        def make(kind, x, y, spans, status, label=None, number=None, legacy=None, reason=None):
            text = "".join(s.text[c:d] for c, d in spans)
            uid = "ap1789-unit-1:" + sha(f"{extent_id}|{kind}|{spans}|{VERSION}")[:28]
            section = next(
                (section for section in reversed(parent["sections"]) if section["start"] <= x), None
            )
            links = [
                dict(id=b["id"], xpath=b["xpath"], start=max(x, b["start"]), end=min(y, b["end"]))
                for b in bs
                if b["tag"] != "pb" and b["start"] < y and x < b["end"]
            ]
            pages = s.pages_for(x, y)
            row = dict(
                id=uid,
                parent_id=record["id"],
                parent_extent_id=extent_id,
                corpus_id=record["corpus_id"],
                type=kind,
                status=status,
                verification="Codex_XML_boundary_examined"
                if status == "A"
                else "proposed_not_individually_verified",
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
                xml_blocks=links,
                pages=pages,
                source=record["source"],
                section_id=section["id"] if section else None,
                extraction_version=VERSION,
                legacy_unit_ids=legacy or [],
                review_reason=reason,
                search_eligible=kind == "article",
                neighbour_order_status="technical_source_order_not_certified_historical_succession",
            )
            own.append(row)
            return row

        for p in article_candidates:
            label = p.get("label_exact", p.get("label"))
            if p.get("historical_number") is not None:
                number = p["historical_number"]
            else:
                match = re.search(r"(?<!\w)\d+(?:er|re|e)?", label or "")
                number = match.group() if match else None
            make(
                "article",
                p["start"],
                p["end"],
                p["spans"],
                p["status"],
                label,
                number,
                [p["id"]] if p.get("id") else [],
                p.get("pending_reason") or p["review_origin"],
            )
        covered = [tuple(span) for u in own for span in u["text_spans"]]
        # A section without numbered articles can be represented as a section, never a fabricated article.
        for section in parent["sections"]:
            x, y = section["start"], section["end"]
            if any(c < y and x < d for c, d in covered):
                continue
            if len(s.text[x:y].strip()) < 80:
                continue
            make(
                "section",
                x,
                y,
                [[x, y]],
                "B",
                reason="Explicit heading; section scope proposed, not historical article",
            )
            covered.append((x, y))
        # Preserve every remaining source character as technical ranges, including paratext.
        for x, y in subtract(a, z, covered):
            chunks = []
            cursor = x
            breaks = [b["end"] for b in bs if x < b["end"] < y]
            for stop in breaks + [y]:
                if stop - cursor >= 1800 or stop == y:
                    chunks.append((cursor, stop))
                    cursor = stop
            for c, d in chunks:
                u = make(
                    "technical_passage",
                    c,
                    d,
                    [[c, d]],
                    "C",
                    reason="Technical complement by XML block positions; not an authentic historical article",
                )
                overlapping = [b for b in role_blocks if b["start"] < d and c < b["end"]]
                u["roles_present"] = sorted({b["role"] for b in overlapping})
                u["search_eligible"] = (
                    bool(s.text[c:d].strip())
                    and bool(overlapping)
                    and all(b["role"] == "body" for b in overlapping)
                )
        own.sort(key=lambda u: (u["start"], u["end"], u["type"]))
        for i, u in enumerate(own):
            u.update(
                order=i + 1,
                previous_unit_id=own[i - 1]["id"] if i else None,
                next_unit_id=own[i + 1]["id"] if i + 1 < len(own) else None,
            )
            parent["unit_ids"].append(u["id"])
            for old in u["legacy_unit_ids"]:
                crosswalk.append(
                    dict(
                        legacy_id=old,
                        new_id=u["id"],
                        document_id=record["id"],
                        relation="exact_source_text_and_ranges",
                        status=u["status"],
                    )
                )
        parents.append(parent)
        units.extend(own)
    if (store.journal.read_bytes() if store.journal.exists() else b"") != journal_snapshot:
        raise ValueError("Decision journal changed during extraction; rerun on a stable snapshot")
    jsonl(out / "parents.jsonl.gz", parents)
    for filename, rs in [
        ("units-A.jsonl.gz", [u for u in units if u["status"] == "A"]),
        ("units-B.jsonl.gz", [u for u in units if u["status"] == "B"]),
        ("units-C.jsonl.gz", [u for u in units if u["status"] == "C"]),
        ("automatic-proposals.jsonl.gz", raw_proposals),
    ]:
        jsonl(out / filename, rs)
    (out / "crosswalk.jsonl").write_text(
        "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in crosswalk)
    )
    write(out / "withheld.json", withheld)
    write(
        out / "source-manifest.json",
        dict(
            registry_sha256=store.registry_sha,
            human_decisions=dict(
                journal_sha256=sha(journal_snapshot),
                event_count=len(journal_snapshot.splitlines()),
                private_journal_not_exported=True,
            ),
            sources={v: s.sha256 for v, s in store.sources.items()},
            source_revision=store.records[0]["source"]["source_revision"],
            code={
                str(p.relative_to(HERE.parents[2])): sha(p.read_bytes())
                for p in [
                    Path(__file__),
                    TOOL / "reviewlib.py",
                    AUDITS / "1789-extraction-v2/rules_v2.py",
                    AUDITS / "1789-extraction-200/rules.py",
                    AUDITS / "1789-extraction-200/pilot_segment.py",
                    AUDITS / "1789-extraction-200/fast_blocks.py",
                ]
            },
        ),
    )
    write(out / "review-summary.json", store.stats())
    manifest = {
        p.name: dict(bytes=p.stat().st_size, sha256=sha(p.read_bytes()))
        for p in sorted(out.iterdir())
        if p.is_file()
        and p.name
        in {
            "parents.jsonl.gz",
            "units-A.jsonl.gz",
            "units-B.jsonl.gz",
            "units-C.jsonl.gz",
            "automatic-proposals.jsonl.gz",
            "crosswalk.jsonl",
            "source-manifest.json",
            "withheld.json",
        }
    }
    write(
        out / "extraction-manifest.json",
        dict(version=VERSION, files=manifest, full_corpus_local_not_versioned=True),
    )
    print(
        json.dumps(
            dict(
                prepared=len(selection),
                parents=len(parents),
                withheld=len(withheld),
                units_by_type=dict(Counter(u["type"] for u in units)),
                units_by_status=dict(Counter(u["status"] for u in units)),
            ),
            ensure_ascii=False,
        )
    )
    return parents, units


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--journal", type=Path)
    args = parser.parse_args()
    run(args.output, args.journal)
