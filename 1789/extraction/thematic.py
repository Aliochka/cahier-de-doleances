"""Conservative thematic structure over existing article/C ranges, never parent discovery."""

import re
from collections import defaultdict

from articles import canonical, intersects, subtract
from reviewlib import sha

VERSION = "thematic-1"
SPACE = re.compile(r"\s+")
REQUEST = re.compile(
    r"\b(?:demand(?:ent|ons|er|era|eront)|demande\s+(?:que|la|le|les|de\b|d['’]|l['’]|un\b|une\b)|d[ée]sir(?:e|ent|ons|er)|suppli(?:e|ent|ons|er)|r[ée]clam(?:e|ent|ons|er)|pri(?:e|ent|ons))\b|(?:^|[.;:]\s+)(?:Que\b|Qu['’])",
    re.I,
)
DOCUMENT = re.compile(
    r"\b(?:cahier|proc[èe]s.verbal|extrait|annexe|suppl[ée]ment|certifi|signature|comparant|d[ée]put[ée]s?)\b",
    re.I,
)
SENTENCE = re.compile(
    r"^(?:art(?:icle)?\b|[\d§]|que\b|qu['’]|il\b|ils\b|elle\b|elles\b|nous\b|on\b|lesdits\b|ledit\b|fait\b|sign[ée]|pour copie|ce\b|ces\b|cette\b|cet\b|ainsi\b|enfin\b|afin\b|et\b|mais\b|ou\b|donc\b)|\b(?:sera|seront|soit|soient|est|sont|doit|doivent|demande|demandent|d[ée]sirent|ordonne|arr[êe]te|admis|consenti|rejet[ée]|accept[ée]|adopt[ée])\b",
    re.I,
)
CLOSE = re.compile(
    r"^(?:sign[ée]|fait et|arr[êe]t[ée]|certifi|collationn|pour copie|ainsi d[ée]lib[ée]r[ée])",
    re.I,
)


def title(text, tag):
    compact = SPACE.sub(" ", text).strip()
    if not 3 <= len(compact) <= 110 or len(compact.split()) > 13 or not compact[0].isupper():
        return False
    if any(c.isdigit() for c in compact) or re.fullmatch(r"[IVXLCM. -]+", compact):
        return False
    if DOCUMENT.search(compact) or SENTENCE.search(compact) or REQUEST.search(compact):
        return False
    if any(c in compact for c in ";!?=«»") or not any(c.isalpha() for c in compact):
        return False
    # Ordinary paragraphs need a closed short label, not an arbitrary short line.
    return tag == "head" or compact.endswith((".", ":")) or compact.isupper()


def division(block):
    return block.get("division") or block["xpath"].rsplit("/", 1)[0]


def regions(store, parent, records, shared_ranges=()):
    source = store.sources[parent["volume"]]
    first_paragraph = {}
    for block in parent["blocks"]:
        if block["tag"] == "p":
            first_paragraph.setdefault(division(block), block["start"])
    groups = defaultdict(list)
    boundaries = defaultdict(list)
    for b in parent["blocks"]:
        if b["tag"] not in {"head", "p"}:
            continue
        text = source.text[b["start"] : b["end"]]
        structural = re.match(
            r"^(?:§|chapitre\b|section\b|titre\b|annexe\b|extrait\b|cahier\b|nota\b|certification\b)",
            text.strip(),
            re.I,
        )
        if b["tag"] == "head" or CLOSE.match(text.strip()) or structural:
            boundaries[division(b)].append(b["start"])
        if not title(text, b["tag"]) or b["role"] in {
            "editorial_note",
            "closing_or_signature",
            "title",
        }:
            continue
        if b["tag"] == "head" and b["start"] <= first_paragraph.get(division(b), parent["end"]):
            continue
        node = source.node(b["xpath"])
        if node.xpath("ancestor::note|descendant::note"):
            continue
        # Real title lines are represented by their own element, no internal wrapped prose.
        if "\n" in text.strip():
            continue
        groups[division(b)].append(b)
    result = []
    for division_path, heads in groups.items():
        # A run of independent thematic labels is needed for plain p titles.
        cluster = len(heads) >= 3
        for i, b in enumerate(heads):
            end = heads[i + 1]["start"] if i + 1 < len(heads) else parent["end"]
            division_end = max(q["end"] for q in parent["blocks"] if division(q) == division_path)
            end = min(end, division_end)
            stops = [pos for pos in boundaries[division_path] if b["end"] <= pos < end]
            if stops:
                end = min(stops)
            body_spans = subtract(
                [[b["end"], end]], [[n["start"], n["end"]] for n in parent.get("annotations", [])]
            )
            text = "".join(source.text[a:z] for a, z in body_spans)
            children = [
                r
                for r in records
                if r["type"] == "article"
                and r["number"] is not None
                and b["end"] <= r["spans"][0][0] < end
            ]
            crossing = [
                r
                for r in records
                if r["type"] == "article"
                and r["number"] is not None
                and any(a < b["end"] and b["start"] < z for a, z in r["spans"])
            ]
            request = bool(REQUEST.search(text))
            form = (
                "section_with_articles"
                if len(children) >= 2
                else "standalone_claim"
                if not children and request
                else "uncertain"
            )
            reasons = []
            if intersects([[b["start"], end]], shared_ranges):
                reasons.append("known_shared_documentary_range_kept_unsegmented")
            if not cluster and b["tag"] != "head":
                reasons.append("insufficient_repeated_thematic_structure")
            if crossing:
                reasons.append("title_inside_numbered_article_kept_unchanged")
            if end - b["start"] > 14000:
                reasons.append("long_scope_requires_review")
            following = [
                q
                for q in parent["blocks"]
                if q["tag"] == "p"
                and b["end"] <= q["start"] < end
                and q["role"] not in {"editorial_note", "closing_or_signature"}
            ]
            if form == "standalone_claim":
                first_body = (
                    source.text[following[0]["start"] : following[0]["end"]].strip()
                    if following
                    else ""
                )
                if len(SPACE.sub(" ", first_body)) < 140:
                    reasons.append("first_body_too_short_to_distinguish_list_item_from_title")
                if re.match(
                    r"^(?:La communaut[ée]|Les habitants|La paroisse|Le village)\s+(?:de\b|d['’])",
                    first_body,
                    re.I,
                ):
                    reasons.append("locality_or_associated_document_requires_review")
            if any(
                r["spans"][-1][1] > end and source.text[end : r["spans"][-1][1]].strip()
                for r in children
            ):
                reasons.append("numbered_article_crosses_next_heading")
            for q in following:
                label = source.text[q["start"] : q["end"]].strip()
                if (
                    label
                    and label[0].islower()
                    and len(label) <= 70
                    and title(label[0].upper() + label[1:], q["tag"])
                ):
                    reasons.append("possible_lowercase_heading_inside_scope")
                    break
            if form == "standalone_claim" and re.search(
                r"(?m)^\s*(?:(?:Art(?:icle)?|Arl|Arf|Ari|[ÀÂ]rt)[ .:]*[0-9lI]|[0-9]+[°.)])", text
            ):
                reasons.append("possible_numbered_articles_in_prose")
            if re.search(r"\bsign[ée]\b", text, re.I):
                reasons.append("signature_inside_scope_requires_review")
            if not text.strip():
                reasons.append("no_development")
            if form == "uncertain":
                reasons.append("role_not_established")
            # Never infer an autonomous unit at an unmarked end of document.
            closed = i + 1 < len(heads) or bool(stops)
            if not closed:
                reasons.append("unmarked_end_of_thematic_run")
            rid = "ap1789-theme-1:" + sha(canonical([parent["extent_id"], b["xpath"], end]))[:24]
            scope_start = b["start"]
            while scope_start > parent["start"] and source.text[scope_start - 1].isspace():
                scope_start -= 1
            result.append(
                dict(
                    id=rid,
                    parent_id=parent["id"],
                    volume=parent["volume"],
                    title=source.text[b["start"] : b["end"]],
                    scope_start=scope_start,
                    parent_extent_id=parent["extent_id"],
                    title_start=b["start"],
                    title_end=b["end"],
                    end=end,
                    xpath=b["xpath"],
                    division=division_path,
                    form=form,
                    confidence="proposed" if not reasons else "uncertain",
                    reasons=reasons,
                    article_ids=[r["id"] for r in children],
                    introduction_spans=[[b["end"], children[0]["spans"][0][0]]]
                    if children and source.text[b["end"] : children[0]["spans"][0][0]].strip()
                    else [],
                    evidence=[
                        "isolated_XML_element",
                        "repeated_thematic_labels" if cluster else "explicit_XML_head",
                        "numbered_articles_in_scope"
                        if children
                        else "request_formula_in_development"
                        if request
                        else "no_sufficient_claim_evidence",
                    ],
                    version=VERSION,
                )
            )
    return sorted(result, key=lambda r: r["title_start"])


def new_record(parent, kind, spans, origins, section=None):
    return dict(
        id="ap1789-thematic-unit-1:" + sha(canonical([parent["extent_id"], kind, spans]))[:26],
        parent_id=parent["id"],
        parent_extent_id=parent["extent_id"],
        type=kind,
        number=None,
        label=None,
        number_origin="none",
        source_status="B" if kind in {"article", "section"} else "C",
        review_status="automatic_proposal"
        if kind in {"article", "section"}
        else "technical_unclassified",
        spans=spans,
        origin_ids=sorted(set(origins)),
        section_id=section,
        last_event_id=None,
    )


def apply(store, parent, records, hypotheses, protected_parent=False):
    result = {r["id"]: r for r in records}
    changes = []
    if protected_parent:
        return list(result.values()), changes
    notes = [[n["start"], n["end"]] for n in parent.get("annotations", [])]
    for h in hypotheses:
        if h["confidence"] != "proposed":
            continue
        a = h["title_start"]
        z = h["end"] if h["form"] == "standalone_claim" else h["title_end"]
        spans = subtract([[a, z]], notes)
        own = [r for r in result.values() if intersects(r["spans"], spans)]
        if not own or any(
            r["type"] not in {"technical_passage", "section"}
            or r["source_status"] == "A"
            or r.get("last_event_id")
            or r["review_status"] not in {"automatic_proposal", "technical_unclassified"}
            for r in own
        ):
            h["application"] = "existing_article_or_reviewed_ranges_preserved"
            continue
        kind = "article" if h["form"] == "standalone_claim" else "section"
        origins = [k for r in own for k in r["origin_ids"] + [r["id"]]]
        fresh = new_record(parent, kind, spans, origins, h["id"] if kind == "section" else None)
        if len(own) == 1 and own[0]["type"] == kind and own[0]["spans"] == spans:
            h["application"] = "existing_unit_kept"
            continue
        for old in own:
            result.pop(old["id"])
            rest = subtract(old["spans"], spans)
            if rest:
                # Keep each residual source interval separate: no synthetic concatenation of prose.
                for piece in rest:
                    residual = new_record(
                        parent, "technical_passage", [piece], old["origin_ids"] + [old["id"]]
                    )
                    result[residual["id"]] = residual
        result[fresh["id"]] = fresh
        h["application"] = "automatic_proposal_created"
        changes.append(
            dict(
                region_id=h["id"],
                parent_id=parent["id"],
                kind="unnumbered_thematic_claim" if kind == "article" else "thematic_heading",
                before_ids=[r["id"] for r in own],
                before_types=[r["type"] for r in own],
                old_spans=[r["spans"] for r in own],
                classification_only=len(own) == 1 and own[0]["spans"] == spans,
                after_id=fresh["id"],
                spans=spans,
                form=h["form"],
            )
        )
    return sorted(result.values(), key=lambda r: r["spans"][0][0]), changes


def context(record, hypotheses):
    a, z = record["spans"][0][0], record["spans"][-1][1]
    eligible = [
        h
        for h in hypotheses
        if h["confidence"] == "proposed"
        and h.get("scope_start", h["title_start"]) <= a < z <= h["end"]
    ]
    if not eligible:
        return None
    h = max(eligible, key=lambda h: h["title_start"])
    form = (
        "unnumbered_thematic_claim"
        if record["type"] == "article"
        and record["number"] is None
        and a <= h["title_end"]
        and h["form"] == "standalone_claim"
        else "article_in_thematic_section"
        if record["type"] == "article" and h["form"] == "section_with_articles"
        else "thematic_heading"
        if record["type"] == "section" and a <= h["title_end"]
        else "section_introduction"
        if h["introduction_spans"] and a >= h["title_end"] and z <= h["introduction_spans"][0][1]
        else "thematic_context"
    )
    return dict(
        region_id=h["id"],
        section_id=h["id"] if h["form"] == "section_with_articles" else None,
        title=h["title"],
        title_start=h["title_start"],
        title_end=h["title_end"],
        xpath=h["xpath"],
        unit_form=form,
        status="source_structure_proposal_not_human_certification",
        version=VERSION,
    )
