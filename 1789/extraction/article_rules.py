"""Additive article repairs supported by literal markers and existing number anchors.

Source characters are never corrected. Numeric hints are evidence, not historical labels.
"""

import re

import segmentation as previous
from articles import canonical, subtract
from reviewlib import sha

VERSION = "article-finalization-1"
NUMBER = r"(?:[0-9lIi](?:[ \t]+[0-9lIi]){1,2}|[0-9lIi]{1,3})(?:er|re|e)?"
PREFIX = re.compile(
    r"(?<!\w)(?:A[.:]?rt(?:icle)?|Ar[fl]|Àrt|Ârt|Àri|Ari)[.'’,:;\-]*\s*(?P<raw>"
    + NUMBER
    + r")(?P<suffix>[.,;:°º®*]?)",
    re.I,
)
BARE = re.compile(r"(?<!\w)(?P<raw>" + NUMBER + r')(?P<suffix>tt|[°º®*»«"”ad.,)])?')
CLAIM = re.compile(
    r"^(?:Que\b|Qu['’]|Les?\b|La\b|L['’]|Il\b|Nous\b|Nos\b|Nul\b|Tous?\b|Toute?s?\b|Demander\b|Supprimer\b|Abolir\b|Soit\b|On\b|Pour\b|D['’]|Suppression\b|Abolition\b|De\b|Des\b|Une?\b|Aux?\b)",
    re.I,
)
CITATION = re.compile(r"(?:\b(?:voir|suivant|selon|conformement|aux|des)|[ld]['’])\s*$", re.I)
REQUEST = re.compile(
    r"\b(?:demand(?:ent|ons|er)|suppli(?:ent|ons)|reclam(?:ent|ons)|desir(?:ent|ons)|soit (?:aboli|supprime|etabli)|qu['’](?:il|ils|elle)|que (?:le|la|les|tous|tout))\b",
    re.I,
)
CLOSING = re.compile(
    r"^(?:signe\b|signé\b|fait et arr[eê]t[eé]|clos et arr[eê]t[eé]|collationn[eé]|paraph[eé]|pour copie certifi[eé]e|nous publions|\(\d+\)\s*nous publions)",
    re.I,
)


def number(text):
    return previous.hint(re.sub(r"\s+", "", text or ""))


def record_number(record):
    n = number(record.get("number"))
    if n is not None:
        return n
    m = PREFIX.search(record.get("label") or "") or BARE.search(record.get("label") or "")
    return number(m["raw"]) if m else None


def scan(store, parent):
    src = store.sources[parent["volume"]]
    blocks = previous.blocks_for(store, parent)
    found = {}
    for i, b in enumerate(blocks):
        if b["tag"] != "p" or b["role"] in {"editorial_note", "closing_or_signature"}:
            continue
        text = src.text[b["start"] : b["end"]]
        notes = [src.span(n) for n in src.node(b["xpath"]).xpath(".//note")]
        prefix_ranges = []
        for style, pattern in [("prefix", PREFIX), ("bare", BARE)]:
            for m in pattern.finditer(text):
                if style == "bare" and any(a <= m.start() < z for a, z in prefix_ranges):
                    continue
                if style == "prefix":
                    prefix_ranges.append((m.start(), m.end()))
                pos = b["start"] + m.start()
                if any(a <= pos < z for a, z in notes):
                    continue
                at_start = bool(previous.LEADING.fullmatch(text[: m.start()]))
                if style == "bare" and not at_start:
                    continue
                if not at_start and CITATION.search(text[max(0, m.start() - 35) : m.start()]):
                    continue
                body = text[m.end() :].lstrip(' \t\n«»"“”\\')
                standalone = not body
                if standalone:
                    nxt = next((q for q in blocks[i + 1 :] if q["tag"] == "p"), None)
                    body = src.text[nxt["start"] : nxt["end"]].lstrip() if nxt else ""
                if (
                    not body
                    or not CLAIM.match(body)
                    or previous.MONEY_DATE.match(body)
                    or previous.REFERENCE.match(body)
                ):
                    continue
                if at_start:
                    pos = previous.trim(src.text, b["start"], b["end"])[0]
                raw = m["raw"]
                n = number(raw)
                if n is None:
                    continue
                found[pos] = dict(
                    start=pos,
                    raw_number=raw,
                    numeric_hint=n,
                    label=src.text[pos : b["start"] + m.end()],
                    literal_number=raw if re.fullmatch(r"\d+(?:er|re|e)?", raw, re.I) else None,
                    style=style,
                    paragraph_start=at_start,
                    standalone=standalone,
                    xpath=b["xpath"],
                    division=b["division"],
                    block_index=i,
                    body_prefix=body[:90],
                    rule_version=VERSION,
                )
    return sorted(found.values(), key=lambda r: r["start"])


def detect(store, parent, records):
    articles = sorted(
        [r for r in records if r["type"] == "article"], key=lambda r: r["spans"][0][0]
    )
    markers = scan(store, parent)
    blocks = previous.blocks_for(store, parent)
    source = store.sources[parent["volume"]]
    candidates = []
    for m in markers:
        if any(
            abs(r["spans"][0][0] - m["start"]) <= max(12, len(r.get("label") or "") + 3)
            for r in articles
        ):
            continue
        candidates.append(
            dict(
                m,
                confidence="suspect",
                evidence=[
                    "literal_source_marker",
                    "XML_paragraph_start"
                    if m["paragraph_start"]
                    else "explicit_inline_article_prefix",
                ],
            )
        )
    # A missing run must exactly bridge two existing article numbers, not merely fill a gap.
    for left, right in zip(articles, articles[1:]):
        a, z = left["spans"][0][0], right["spans"][0][0]
        ln, rn = record_number(left), record_number(right)
        if ln is None or rn is None or not 1 < rn - ln <= 9:
            continue
        between = [m for m in candidates if a < m["start"] < z]
        if [m["numeric_hint"] for m in between] != list(range(ln + 1, rn)):
            continue
        if any(
            a < b["start"] < z
            and b["role"] in {"heading", "section_heading", "closing_or_signature"}
            and not PREFIX.match(source.text[b["start"] : b["end"]].strip())
            for b in blocks
        ):
            continue
        old_bare = bool(
            BARE.match((left.get("label") or "").lstrip(" «»"))
            and BARE.match((right.get("label") or "").lstrip(" «»"))
        )
        divisions = {m["division"] for m in between}
        ldiv = next((b["division"] for b in blocks if b["start"] <= a < b["end"]), None)
        rdiv = next((b["division"] for b in blocks if b["start"] <= z < b["end"]), None)
        if len(divisions) != 1 or ldiv != rdiv or ldiv not in divisions:
            continue
        if any(m["style"] == "bare" and not old_bare for m in between):
            continue
        for m in between:
            m["confidence"] = "strong"
            m["evidence"] += [
                "existing_left_and_right_article_anchors",
                "complete_literal_number_sequence",
                "same_XML_division",
                "no_intervening_documentary_heading",
            ]
    # C-only runs: three explicit prefixed articles at paragraph starts, with visible structure.
    occupied = [span for r in records if r["type"] != "technical_passage" for span in r["spans"]]
    c_ranges = subtract([[parent["start"], parent["end"]]], occupied)
    for a, z in c_ranges:
        run = [m for m in candidates if a <= m["start"] < z]
        if len(run) < 3 or any(m["style"] != "prefix" or not m["paragraph_start"] for m in run):
            continue
        ns = [m["numeric_hint"] for m in run]
        if ns != list(range(ns[0], ns[0] + len(ns))):
            continue
        if any(
            run[0]["start"] < b["start"] < run[-1]["start"]
            and b["role"] in {"heading", "section_heading", "closing_or_signature"}
            and not PREFIX.match(source.text[b["start"] : b["end"]].strip())
            for b in blocks
        ):
            continue
        for m in run:
            m["confidence"] = "strong"
            m["evidence"] += [
                "three_or_more_explicit_prefixed_articles_in_C",
                "literal_contiguous_sequence",
            ]
    return candidates


def auto_record(parent, kind, spans, origins, marker=None):
    marker = marker or {}
    uid = "ap1789-article-final-1:" + sha(canonical([parent["extent_id"], kind, spans]))[:28]
    return dict(
        id=uid,
        parent_id=parent["id"],
        parent_extent_id=parent["extent_id"],
        type=kind,
        number=marker.get("literal_number"),
        label=marker.get("label"),
        number_origin="source_recognition",
        source_status="B" if kind == "article" else "C",
        review_status="automatic_proposal" if kind == "article" else "technical_unclassified",
        spans=spans,
        origin_ids=sorted(set(origins)),
        section_id=None,
        last_event_id=None,
    )


def repair(store, parent, records, protected_parent=False):
    records = list(records)
    cs = detect(store, parent, records)
    strong = [c for c in cs if c["confidence"] == "strong"]
    changes = []
    if protected_parent:
        return records, cs, changes
    source = store.sources[parent["volume"]]
    result = {r["id"]: r for r in records}
    # Splits never move an existing end and preserve every source span, including whitespace.
    for old in records:
        if old["type"] != "article" or old["review_status"] in {
            "human_validated",
            "human_corrected",
            "uncertain",
        }:
            continue
        points = [
            m
            for m in strong
            if old["spans"][0][0] < m["start"] < old["spans"][-1][1]
            and any(a < m["start"] < z for a, z in old["spans"])
        ]
        if not points:
            continue
        spans = old["spans"]
        bounds = [spans[0][0]] + [m["start"] for m in points] + [spans[-1][1]]
        children = []
        for i, (a, z) in enumerate(zip(bounds, bounds[1:])):
            pieces = [[max(x, a), min(y, z)] for x, y in spans if max(x, a) < min(y, z)]
            marker = points[i - 1] if i else dict(literal_number=old["number"], label=old["label"])
            children.append(
                auto_record(parent, "article", pieces, old["origin_ids"] + [old["id"]], marker)
            )
        if any(not "".join(source.text[a:z] for a, z in r["spans"]).strip() for r in children):
            continue
        result.pop(old["id"])
        result.update((r["id"], r) for r in children)
        changes.append(
            dict(
                kind="split_fused_article",
                before_ids=[old["id"]],
                after_ids=[r["id"] for r in children],
                markers=points,
                old_spans=old["spans"],
                new_spans=[r["spans"] for r in children],
            )
        )
    # Recover only from the exact complement of existing non-C units.
    occupied = [
        span for r in result.values() if r["type"] != "technical_passage" for span in r["spans"]
    ]
    notes = [[n["start"], n["end"]] for n in parent.get("annotations", [])]
    blocks = previous.blocks_for(store, parent)
    recover = []
    for a, z in subtract([[parent["start"], parent["end"]]], occupied):
        markers = [m for m in strong if a <= m["start"] < z]
        for i, m in enumerate(markers):
            end = markers[i + 1]["start"] if i + 1 < len(markers) else z
            stop = next(
                (
                    b["start"]
                    for b in blocks
                    if m["start"] < b["start"] < end
                    and (
                        b["role"] in {"heading", "section_heading", "closing_or_signature"}
                        or CLOSING.match(source.text[b["start"] : b["end"]].strip())
                    )
                    and not PREFIX.match(source.text[b["start"] : b["end"]].strip())
                ),
                None,
            )
            if stop:
                end = stop
            start, end = previous.trim(source.text, m["start"], end)
            spans = subtract([[start, end]], notes)
            if not spans or not "".join(source.text[x:y] for x, y in spans).strip():
                continue
            origins = [
                r["id"]
                for r in records
                if r["type"] == "technical_passage"
                and any(x < end and start < y for x, y in r["spans"])
            ]
            if not origins:
                continue
            new = auto_record(parent, "article", spans, origins, m)
            recover.append(new)
            changes.append(
                dict(
                    kind="recover_article_from_C",
                    before_ids=origins,
                    after_ids=[new["id"]],
                    markers=[m],
                    old_spans=[],
                    new_spans=[spans],
                )
            )
    if recover:
        occupied = [span for r in recover for span in r["spans"]]
        for old in list(result.values()):
            if old["type"] != "technical_passage":
                continue
            remaining = subtract(old["spans"], occupied)
            if remaining == old["spans"]:
                continue
            result.pop(old["id"])
            if remaining:
                new = auto_record(
                    parent, "technical_passage", remaining, old["origin_ids"] + [old["id"]]
                )
                result[new["id"]] = new
        result.update((r["id"], r) for r in recover)
    return sorted(result.values(), key=lambda r: r["spans"][0][0]), cs, changes


def content_class(store, parent, record):
    source = store.sources[parent["volume"]]
    text = "".join(source.text[a:z] for a, z in record["spans"])
    stripped = text.strip()
    if not stripped or re.fullmatch(r"[\W_]+", stripped):
        return "paratext", "whitespace_or_punctuation_only"
    blocks = [
        b
        for b in parent["blocks"]
        if any(
            b["start"] < z
            and a < b["end"]
            and source.text[max(a, b["start"]) : min(z, b["end"])].strip()
            for a, z in record["spans"]
        )
    ]
    if blocks and all(b["tag"] in {"head", "note"} for b in blocks):
        return "paratext", "explicit_XML_head_or_note"
    if CLOSING.match(stripped) and not REQUEST.search(stripped) and not PREFIX.search(stripped):
        return "paratext", "explicit_closing_or_editorial_formula_without_claim_marker"
    if len(stripped) < 160 and re.fullmatch(
        r"(?:[§.\s\dIVXivx-]+|(?:CHAPITRE|SECTION|TITRE)\s+[\w. -]+)", stripped
    ):
        return "paratext", "short_explicit_rubric_without_body"
    if PREFIX.match(stripped) or BARE.match(stripped):
        return "possible_missed_article", "literal_numbered_marker_requires_context"
    if REQUEST.search(stripped) and len(stripped) > 80:
        return "claim_prose_proposal", "request_formula_in_unsegmented_text_not_human_verified"
    return "uncertain", "no_deterministic_documentary_classification"
