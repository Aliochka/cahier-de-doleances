"""Source-supported thematic boundaries inside automatic units; no semantic chunking."""

import copy
import re
import unicodedata
from collections import defaultdict

import thematic
from articles import canonical, intersects, subtract
from reviewlib import sha

VERSION = "thematic-fusion-1"
DEPENDENT = re.compile(
    r"^(?:(?:Des?|Du|Les?)\s+)?(?:causes?|cons[ée]quences?|rem[èe]des?|effets?|applications?|conclusions?|principes?|moyens\b|motifs?|raisons?|observations?|consid[ée]rations?|suite|d[ée]veloppement|explications?|r[ée]ponses?|exemples?|nota|preuves?|remarques?|moyens d['’]ex[ée]cution)\b",
    re.I,
)
REQUEST = re.compile(
    thematic.REQUEST.pattern
    + r"|\bon demande\b|\b(?:d[ée]sirerait|d[ée]sireraient|r[ée]clam[ée]e?s?)\b|\bserait[- ](?:il )?(?:[àa] souhaiter|juste|utile|n[ée]cessaire)\b",
    re.I,
)
NUMBERS = re.compile(r"(?m)^\s*(?:(?:Art(?:icle)?|Arl|Arf|Ari|[ÀÂ]rt)[ .:]*[0-9lI]|[0-9]+[°.)])")
STOPWORDS = set(
    "pour dans avec sans entre sur sous tout tous toute toutes ceux celles leurs leur cette ces ainsi aussi ordre objets autres divers generales general communes ancien anciens saint sainte dont qui que quoi auront serait devront".split()
)


def tokens(text):
    # Matching only: original source characters/offsets are never changed.
    text = re.sub(r"-\s+", "", text)
    text = "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c)
    )
    return {t for t in re.findall(r"[a-z]{4,}", text) if t not in STOPWORDS}


def detect(store, parent, records, protected_spans=(), shared_spans=()):
    src = store.sources[parent["volume"]]
    blocks = [b for b in parent["blocks"] if b["tag"] in {"p", "head"}]
    by_div = defaultdict(list)
    stops = defaultdict(list)
    dependent = []
    for b in blocks:
        text = src.text[b["start"] : b["end"]]
        compact = thematic.SPACE.sub(" ", text).strip()
        div = thematic.division(b)
        if (
            b["tag"] == "head"
            or thematic.CLOSE.match(compact)
            or re.match(
                r"^(?:§|chapitre\b|section\b|titre\b|cahier\b|annexe\b|extrait\b)", compact, re.I
            )
        ):
            stops[div].append(b["start"])
        if DEPENDENT.match(compact):
            dependent.append(b)
            continue
        if (
            not thematic.title(compact, b["tag"])
            or re.search(
                r"\b(?:serait|seraient|pourrait|pourraient|devrait|devraient|peut|peuvent)\b",
                compact,
                re.I,
            )
            or any(c in compact for c in "[]")
            or b["role"] in {"editorial_note", "closing_or_signature", "title"}
        ):
            continue
        node = src.node(b["xpath"])
        if node.xpath("ancestor::note|descendant::note|ancestor::quote|ancestor::q|ancestor::cit"):
            continue
        by_div[div].append(b)
    hypotheses = []
    ordered = sorted(records, key=lambda r: r["spans"][0][0])
    for old in ordered:
        a, z = old["spans"][0][0], old["spans"][-1][1]
        if old["type"] not in {"article", "section", "technical_passage"}:
            continue
        local = [
            b
            for hs in by_div.values()
            for b in hs
            if a <= b["start"] < z and any(x <= b["start"] < y for x, y in old["spans"])
        ]
        local_independent_count = len(local)
        local += [
            b
            for b in dependent
            if a <= b["start"] < z and any(x <= b["start"] < y for x, y in old["spans"])
        ]
        local.sort(key=lambda b: b["start"])
        # Only an interior title is a fusion hypothesis; initial labels provide context.
        interior = [b for b in local if src.text[a : b["start"]].strip()]
        if not interior:
            continue
        for b in interior:
            div = thematic.division(b)
            following = [q for q in by_div[div] if q["start"] > b["start"]]
            stop = [x for x in stops[div] if b["end"] <= x]
            next_heading = following[0]["start"] if following else None
            next_stop = min(stop) if stop else None
            material_end = min(
                [x for x in [next_heading, next_stop, parent["end"]] if x is not None]
            )
            end = min(material_end, z)
            reasons = []
            evidence = ["isolated_XML_element", "literal_title_with_development"]
            note_spans = [[n["start"], n["end"]] for n in parent.get("annotations", [])]
            body_spans = subtract([[b["end"], end]], note_spans)
            body = "".join(src.text[x:y] for x, y in body_spans)
            body_ps = [
                q
                for q in blocks
                if b["end"] <= q["start"] < end
                and q["tag"] == "p"
                and q["role"] not in {"editorial_note", "closing_or_signature"}
            ]
            previous = [
                q
                for q in blocks
                if q["tag"] == "p"
                and a <= q["start"] < b["start"]
                and q["role"] not in {"editorial_note", "closing_or_signature"}
            ]
            prior = " ".join(src.text[q["start"] : q["end"]] for q in previous[-2:])
            title_tokens = tokens(src.text[b["start"] : b["end"]])
            shared = title_tokens & tokens(body)
            novel = shared - tokens(prior)
            next_unit = next(
                (r for r in ordered if r["spans"][0][0] >= z and r["type"] == "article"), None
            )
            next_numbered = bool(
                old["number"] is not None and next_unit and next_unit["number"] is not None
            )
            if local_independent_count >= 2:
                evidence.append("multiple_distinct_title_elements_in_same_unit")
            elif len(by_div[div]) >= 3 and next_numbered:
                evidence.append("repeated_heading_pattern_and_following_numbered_article")
            else:
                reasons.append("singleton_title_without_sufficient_neighbour_support")
            if not previous or not src.text[
                previous[-1]["start"] : previous[-1]["end"]
            ].rstrip().endswith((".", ";", "!", "?")):
                reasons.append("preceding_development_not_clearly_closed")
            else:
                evidence.append("preceding_paragraph_closes_with_punctuation")
            if (
                not body_ps
                or len(
                    thematic.SPACE.sub(
                        " ", src.text[body_ps[0]["start"] : body_ps[0]["end"]]
                    ).strip()
                )
                < 100
            ):
                reasons.append("development_too_short_or_missing")
            if not REQUEST.search(body):
                reasons.append("no_explicit_request_formula")
            else:
                evidence.append("explicit_historical_request_formula")
            if not shared:
                reasons.append("title_not_supported_by_development_vocabulary")
            elif not novel:
                reasons.append("same_vocabulary_as_preceding_development_requires_review")
            else:
                evidence.append(
                    "title_words_in_development_and_new_relative_to_previous_paragraphs"
                )
            if next_heading is not None and next_heading <= end:
                evidence.append("following_isolated_title_bounds_development")
            elif next_stop is not None and next_stop <= end:
                evidence.append("structural_heading_or_closure_bounds_development")
            elif next_numbered:
                evidence.append("following_numbered_unit_bounds_development")
            else:
                reasons.append("right_boundary_not_materially_established")
            if material_end > z and src.text[z:material_end].strip() and not next_numbered:
                reasons.append("development_may_continue_outside_unit")
            for q in body_ps:
                label = thematic.SPACE.sub(" ", src.text[q["start"] : q["end"]]).strip()
                if not label or DEPENDENT.match(label):
                    continue
                normal = label[0].upper() + label[1:]
                if (
                    len(label) <= 110
                    and not thematic.title(label, q["tag"])
                    and (thematic.title(normal, q["tag"]) or thematic.title(normal + ".", q["tag"]))
                ):
                    reasons.append("unclassified_heading_inside_scope_requires_review")
                    break
            if NUMBERS.search(body) or re.search(r"(?m)^\s*[IVXLCDM]{1,8}\.\s+", body):
                reasons.append("numbered_subdivision_inside_development_kept_together")
            if re.search(r"\bsign[ée]\b", body, re.I):
                reasons.append("signature_inside_development")
            if end - b["start"] > 12000:
                reasons.append("long_scope_requires_review")
            if re.match(
                r"^(?:La communaut[ée]|Les habitants|La paroisse|Le village)\s+(?:de\b|d['’])",
                body.lstrip(),
                re.I,
            ):
                reasons.append("locality_or_attached_document")
            if intersects([[b["start"], end]], shared_spans):
                reasons.append("known_shared_documentary_range")
            # No overwrite of human decisions, including raw ranges needed for journal replay.
            protected = (
                old.get("last_event_id") is not None
                or old["review_status"] in {"human_validated", "human_corrected", "uncertain"}
                or intersects(old["spans"], protected_spans)
            )
            if protected:
                reasons.append("human_history_has_priority_separate_proposal_only")
            if old["source_status"] == "A":
                reasons.append("previous_Codex_reference_kept_for_review")
            if any(q["xpath"] == b["xpath"] for q in dependent):
                reasons.append("dependent_subheading")
            hypotheses.append(
                dict(
                    id="ap1789-fusion-boundary-1:"
                    + sha(canonical([parent["extent_id"], old["id"], b["start"], end]))[:24],
                    parent_id=parent["id"],
                    parent_extent_id=parent["extent_id"],
                    volume=parent["volume"],
                    source_unit_id=old["id"],
                    source_type=old["type"],
                    source_number=old["number"],
                    source_spans=old["spans"],
                    title=src.text[b["start"] : b["end"]],
                    title_start=b["start"],
                    title_end=b["end"],
                    end=end,
                    xpath=b["xpath"],
                    division=div,
                    confidence="proposed" if not reasons else "uncertain",
                    reasons=reasons,
                    evidence=evidence,
                    matched_title_words=sorted(shared),
                    novel_title_words=sorted(novel),
                    protected=protected,
                    version=VERSION,
                )
            )
    return hypotheses


def record(parent, kind, spans, origins, old=None):
    uid = "ap1789-fusion-unit-1:" + sha(canonical([parent["extent_id"], kind, spans]))[:26]
    if old:
        r = copy.deepcopy(old)
        r.update(
            id=uid,
            spans=spans,
            origin_ids=sorted(set(old["origin_ids"] + [old["id"]])),
            last_event_id=None,
        )
        return r
    return dict(
        id=uid,
        parent_id=parent["id"],
        parent_extent_id=parent["extent_id"],
        type=kind,
        number=None,
        label=None,
        number_origin="none",
        source_status="B" if kind == "article" else "C",
        review_status="automatic_proposal" if kind == "article" else "technical_unclassified",
        spans=spans,
        origin_ids=sorted(set(origins)),
        section_id=None,
        last_event_id=None,
    )


def apply(store, parent, records, hypotheses):
    result = {r["id"]: r for r in records}
    changes = []
    notes = [[n["start"], n["end"]] for n in parent.get("annotations", [])]
    for old in records:
        if (
            old.get("last_event_id")
            or old["review_status"] in {"human_validated", "human_corrected", "uncertain"}
            or old["source_status"] == "A"
        ):
            continue
        hs = sorted(
            [
                h
                for h in hypotheses
                if h["source_unit_id"] == old["id"] and h["confidence"] == "proposed"
            ],
            key=lambda h: h["title_start"],
        )
        if not hs:
            continue
        # An accepted scope must be wholly contained in its source unit, possibly excluding notes.
        if any(h["end"] > old["spans"][-1][1] for h in hs):
            continue
        claimed = []
        children = []
        origins = old["origin_ids"] + [old["id"]]
        for h in hs:
            spans = subtract([[h["title_start"], h["end"]]], notes)
            spans = [
                [max(a, x), min(z, y)]
                for a, z in spans
                for x, y in old["spans"]
                if max(a, x) < min(z, y)
            ]
            if not spans:
                continue
            child = record(parent, "article", spans, origins)
            child["section_id"] = old["section_id"]
            children.append(child)
            claimed.extend(spans)
        if not children:
            continue
        prefix_end = hs[0]["title_start"]
        prefix = [[a, min(z, prefix_end)] for a, z in old["spans"] if a < min(z, prefix_end)]
        if prefix:
            first = record(parent, old["type"], prefix, origins, old=old)
            children.append(first)
            claimed.extend(prefix)
        for span in subtract(old["spans"], claimed):
            children.append(record(parent, "technical_passage", [span], origins))
        # Reject zero-length/overlapping suggestions rather than changing source coverage.
        spans = sorted(s for r in children for s in r["spans"])
        if sum(z - a for a, z in spans) != sum(z - a for a, z in old["spans"]) or any(
            a[1] > b[0] for a, b in zip(spans, spans[1:])
        ):
            raise ValueError("Invalid thematic fusion partition")
        result.pop(old["id"])
        result.update((r["id"], r) for r in children)
        changes.append(
            dict(
                parent_id=parent["id"],
                old_unit_id=old["id"],
                old_type=old["type"],
                old_number=old["number"],
                old_spans=old["spans"],
                new_unit_ids=[r["id"] for r in sorted(children, key=lambda r: r["spans"][0][0])],
                new_claim_ids=[
                    r["id"]
                    for r in children
                    if r["type"] == "article"
                    and r["number"] is None
                    and r["spans"][0][0] >= prefix_end
                ],
                hypothesis_ids=[h["id"] for h in hs],
                prefix_retained=bool(prefix),
                version=VERSION,
            )
        )
    return sorted(result.values(), key=lambda r: r["spans"][0][0]), changes
