"""Conservative extension of the frozen V2 segmenter; proposals never replace decisions."""

import copy
import re

from reviewlib import AUDITS, module, sha

VERSION = "article-segmentation-1.0"
PREFIX = re.compile(
    r"(?<!\w)(?:Article|Art|Arf|Àri)[.'’,:;\-]*\s*(?P<raw>\d{1,3}(?:er|re|e)?|[lIi]{1,3}(?:er)?)(?!\d)(?P<suffix>[.,;:°º®*])?",
    re.I,
)
BARE = re.compile(
    r'(?<!\w)(?P<raw>\d{1,3}(?:er|re|e)?|[lIi]{1,3}|t)(?!\d)(?P<suffix>tt|[°ºo®*»«"”ad.,)])?'
)
LEADING = re.compile(r'^[\s«»"“”„\'’.,;:—–\-]*$')
BODY = re.compile(
    r"^(?:Que\b|Qu['’]|Les?\b|La\b|L['’]|Il\b|Nous\b|Nos\b|Nul\b|Tous?\b|Toute?s?\b|Demander\b|Supprimer\b|Abolir\b|Soit\b|On\b|Pour\b|D['’])",
    re.I,
)
MONEY_DATE = re.compile(
    r"^(?:livres?|sols?|sous|deniers?|millions?|pour\s*cent|%|janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\b",
    re.I,
)
RUBRIC = re.compile(r"^demandes\s+et\s+dol[ée]ances\s+qui\s+int[ée]ressent", re.I)
INTERSTITIAL = re.compile(r"^(?:Et,?\s+attendu\b|Nous\s+enjoignons\b)", re.I)
REFERENCE = re.compile(
    r"^(?:du\s+(?:code|règlement)|de\s+l['’](?:ordonnance|article)|de\s+la\s+loi)\b", re.I
)


def trim(text, a, z):
    while a < z and text[a].isspace():
        a += 1
    while a < z and text[z - 1].isspace():
        z -= 1
    return a, z


def hint(raw):
    literal = re.fullmatch(r"(\d+)(?:er|re|e)?", raw, re.I)
    if literal:
        return int(literal[1])
    token = raw.lower().replace("l", "1").replace("i", "1").replace("t", "1")
    return int(token) if token.isdigit() else None


def old_rules(store):
    return module("segmentation_previous_v2", AUDITS / "1789-extraction-v2/rules_v2.py")


def blocks_for(store, parent):
    source = store.sources[parent["volume"]]
    blocks = []
    for raw in parent["blocks"]:
        b = copy.deepcopy(raw)
        node = source.node(b["xpath"])
        ancestors = node.xpath('ancestor::*[starts-with(local-name(),"div")]')
        div = source.tree.getpath(ancestors[-1]) if ancestors else "body"
        b["division"] = div
        blocks.append(b)
    return blocks


def candidates(source, blocks):
    result = []
    for i, b in enumerate(blocks):
        if b["tag"] != "p" or b["role"] in {"editorial_note", "closing_or_signature"}:
            continue
        text = source.text[b["start"] : b["end"]]
        excluded = [source.span(n) for n in source.node(b["xpath"]).xpath(".//note")]
        found = []
        for kind, pattern in [("prefix", PREFIX), ("bare", BARE)]:
            for m in pattern.finditer(text):
                if any(a <= b["start"] + m.start() < z for a, z in excluded):
                    continue
                if kind == "bare" and any(a <= m.start() < z for a, z, _ in found):
                    continue
                prefix = text[: m.start()]
                at_start = bool(LEADING.fullmatch(prefix))
                inline = not at_start and bool(re.search(r'[.;!?]\s*[«»"“”]?\s*$', prefix))
                if not at_start and not inline:
                    continue
                body = text[m.end() :].lstrip()
                marker_only = not body.strip()
                if marker_only:
                    following = next(
                        (q for q in blocks[i + 1 :] if q["tag"] == "p" and q["end"] > q["start"]),
                        None,
                    )
                    body = (
                        source.text[following["start"] : following["end"]].lstrip()
                        if following
                        else ""
                    )
                if not body or body[0].isdigit() or MONEY_DATE.match(body):
                    continue
                if kind == "prefix" and REFERENCE.match(body):
                    continue
                strong_body = bool(BODY.match(body))
                glued = (
                    m.end() < len(text) and not text[m.end()].isspace() and text[m.end()].isalpha()
                )
                if not strong_body and not (
                    body[0].isupper() and (kind == "prefix" or m["suffix"])
                ):
                    continue
                if inline and not strong_body:
                    continue
                start = b["start"] + m.start()
                # Keep source punctuation with its own paragraph for new markers.
                if at_start:
                    start = trim(source.text, b["start"], b["end"])[0]
                raw = m["raw"]
                value = hint(raw)
                record = dict(
                    start=start,
                    number_start=b["start"] + m.start("raw"),
                    marker_end=b["start"] + m.end(),
                    raw_number=raw,
                    raw_label=source.text[start : b["start"] + m.end()],
                    numeric_hint=value,
                    historical_number=raw if re.fullmatch(r"\d+(?:er|re|e)?", raw, re.I) else None,
                    kind=kind,
                    suffix=m["suffix"],
                    block_index=i,
                    xpath=b["xpath"],
                    division=b["division"],
                    paragraph_start=at_start,
                    inline=inline,
                    glued=glued,
                    marker_only=marker_only,
                    strong_body=strong_body,
                    evidence=[],
                    confidence="suspect",
                )
                found.append((m.start(), m.end(), record))
        result.extend(r for _, _, r in found)
    unique = {r["number_start"]: r for r in result}
    return sorted(unique.values(), key=lambda r: r["start"])


def run(store, parent):
    source = store.sources[parent["volume"]]
    rules = old_rules(store)
    original_blocks = blocks_for(store, parent)
    old = rules.segment(source, original_blocks)
    bs = copy.deepcopy(original_blocks)
    role_changes = []
    for i, b in enumerate(bs):
        if b["tag"] != "p":
            continue
        text = source.text[b["start"] : b["end"]].strip()
        match = PREFIX.fullmatch(text)
        if match and b["role"] == "section_heading":
            role_changes.append(
                dict(
                    xpath=b["xpath"],
                    reason="explicit_article_marker_misclassified_as_heading",
                    start=b["start"],
                )
            )
            b["role"] = "body"
        elif RUBRIC.match(text) and len(text) < 250 and not PREFIX.search(text):
            b["role"] = "section_heading"
            role_changes.append(
                dict(xpath=b["xpath"], reason="explicit_documentary_rubric", start=b["start"])
            )
        elif INTERSTITIAL.match(text):
            previous = next((q for q in reversed(bs[:i]) if q["tag"] == "p"), None)
            if previous and source.text[previous["start"] : previous["end"]].rstrip().endswith("»"):
                b["role"] = "section_heading"
                role_changes.append(
                    dict(
                        xpath=b["xpath"],
                        reason="prose_after_closed_numbered_quotation",
                        start=b["start"],
                    )
                )
    base = rules.segment(source, bs)
    cs = candidates(source, bs)
    for i, c in enumerate(cs):
        prev = cs[i - 1] if i else None
        nxt = cs[i + 1] if i + 1 < len(cs) else None
        n = c["numeric_hint"]
        pn = prev["numeric_hint"] if prev else None
        nn = nxt["numeric_hint"] if nxt else None
        left = n is not None and pn == n - 1
        right = n is not None and nn == n + 1
        between = bs[(prev["block_index"] + 1 if prev else 0) : c["block_index"]]
        section_before = any(q["role"] in {"section_heading", "heading"} for q in between)
        after = bs[c["block_index"] + 1 : (nxt["block_index"] if nxt else len(bs))]
        section_after = any(
            q["role"] in {"section_heading", "heading", "closing_or_signature"} for q in after
        )
        existing = next(
            (
                u
                for u in base
                if u["start"]
                <= c["number_start"]
                < u["start"] + max(len(u.get("label_exact") or ""), 15)
            ),
            None,
        )
        containing = next((u for u in old if u["start"] <= c["start"] < u["end"]), None)
        c["existing_start"] = existing["start"] if existing else None
        c["previous_hint"] = pn
        c["next_hint"] = nn
        c["evidence"] = [
            "XML_paragraph_start" if c["paragraph_start"] else "sentence_boundary_inside_XML_p"
        ]
        if left:
            c["evidence"].append("previous_number_agrees")
        if right:
            c["evidence"].append("next_number_agrees")
        if section_before:
            c["evidence"].append("structural_section_before")
        if section_after:
            c["evidence"].append("structural_section_after")
        if c["glued"]:
            c["evidence"].append("text_follows_marker_without_space")
        if c["historical_number"] is None:
            c["evidence"].append("OCR_number_hint_only_not_historical_number")
        if existing:
            c["confidence"] = "existing"
            continue
        explicit_style = containing and containing.get("rule") == "article" and not section_before
        if c["kind"] == "bare" and explicit_style:
            c["confidence"] = "rejected"
            c["evidence"].append("possible_internal_list_in_explicit_article")
            continue
        reset_ok = not (n == 1 and prev and pn != 0 and not section_before)
        regular = (
            c["suffix"] in {"°", "º", "o", "®", "*", "»", "«"}
            and c["historical_number"] is not None
        )
        degraded = c["suffix"] in {"a", "d", "tt", '"', "”"} or c["historical_number"] is None
        if c["kind"] == "prefix" and c["paragraph_start"]:
            c["confidence"] = "proposed"
            c["evidence"].append("explicit_Art_prefix")
        elif c["kind"] == "prefix" and left and right and c["strong_body"]:
            c["confidence"] = "proposed"
            c["evidence"].append("inline_explicit_prefix_with_two_number_neighbours")
        elif regular and c["paragraph_start"] and (left or right) and reset_ok:
            c["confidence"] = "proposed"
        elif (
            degraded
            and c["paragraph_start"]
            and c["strong_body"]
            and (
                (left and right)
                or (left and section_after)
                or (n == 1 and right and section_before)
            )
        ):
            c["confidence"] = "proposed"
        elif (
            c["suffix"] in {".", ",", ")"}
            and c["paragraph_start"]
            and c["strong_body"]
            and left
            and right
            and reset_ok
        ):
            c["confidence"] = "proposed"
            c["evidence"].append("punctuated_number_with_two_neighbours")
        elif (
            not c["suffix"]
            and c["paragraph_start"]
            and c["strong_body"]
            and left
            and right
            and (c["historical_number"] is not None or c["glued"])
        ):
            c["confidence"] = "proposed"
            c["evidence"].append("bare_number_confirmed_by_two_neighbours")
        elif c["inline"] and left and right and c["strong_body"] and regular:
            c["confidence"] = "proposed"
    additions = [c for c in cs if c["confidence"] == "proposed"]
    starts = {u["start"]: dict(u, origin="v2_with_role_checks") for u in base}
    for c in additions:
        starts[c["start"]] = dict(
            start=c["start"],
            label_exact=c["raw_label"],
            rule="contextual_marker",
            xml_blocks=[c["xpath"]],
            end=None,
            origin="new_contextual_marker",
            marker=c,
        )
    ordered = sorted(starts.values(), key=lambda u: u["start"])
    final = []
    for i, u in enumerate(ordered):
        start = u["start"]
        nxt = ordered[i + 1]["start"] if i + 1 < len(ordered) else parent["end"]
        enclosing = next((o for o in base if o["start"] <= start < o["end"]), None)
        end = min(enclosing["end"], nxt) if enclosing else nxt
        changed = u["end"] is None or (u["end"] and nxt < u["end"])
        if changed:
            following = next((b for b in bs if b["start"] <= nxt < b["end"]), None)
            if following and following["start"] > start:
                previous = [
                    b for b in bs if b["tag"] == "p" and start < b["end"] <= following["start"]
                ]
                if previous:
                    end = min(end, previous[-1]["end"])
            stop = next(
                (
                    b
                    for b in bs
                    if b["start"] > start
                    and b["start"] < end
                    and b["role"] in {"heading", "section_heading", "closing_or_signature"}
                ),
                None,
            )
            if stop:
                end = stop["start"]
            start, end = trim(source.text, start, end)
        if start >= end:
            continue
        notes = [
            (n["start"], n["end"])
            for n in parent.get("annotations", [])
            if n["start"] < end and start < n["end"]
        ]
        from articles import subtract

        spans = subtract([[start, end]], notes)
        row = dict(
            u,
            start=start,
            end=end,
            spans=spans,
            text="".join(source.text[a:z] for a, z in spans),
            status="B_proposed_not_human_validated",
            method=VERSION,
        )
        row["id"] = (
            "ap1789-seg-proposal-1:" + sha(f"{parent['extent_id']}|{start}|{end}|{VERSION}")[:24]
        )
        final.append(row)
    assert len({u["id"] for u in final}) == len(final)
    for left, right in zip(final, final[1:]):
        assert left["end"] <= right["start"]
    return dict(old=old, new=final, candidates=cs, role_changes=role_changes, version=VERSION)
