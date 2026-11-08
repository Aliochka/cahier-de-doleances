"""Read-only paragraph projection. All slicing uses canonical Unicode codepoints."""

import re


def reading_paragraphs(full, source_document, witness=None):
    """Keep XML blocks, including partial boundary blocks, without losing any text.

    Unknown/malformed XML positions fall back to blank-line paragraphs. A single
    newline never establishes a new historical paragraph. Neither the canonical
    text nor whitespace in the returned fragments is changed here.
    """
    origin = source_document.get("source_start")
    raw = source_document.get("xml_blocks")
    spans = []
    if isinstance(origin, int) and isinstance(raw, list):
        for b in raw:
            if not isinstance(b, dict):
                spans = []
                break
            a, z = b.get("start"), b.get("end")
            if not isinstance(a, int) or not isinstance(z, int) or a > z:
                spans = []
                break
            a, z = max(0, a - origin), min(len(full), z - origin)
            if a >= z:  # Empty page milestones do not create paragraphs.
                continue
            if spans and a < spans[-1][1]:
                spans = []
                break
            kind = (
                "heading"
                if b.get("tag") == "head"
                or b.get("role") in {"heading", "section_heading", "title"}
                else "paragraph"
            )
            spans.append((a, z, kind))

    ranges = []

    def fallback(a, z):
        start = a
        for match in re.finditer(r"\n[\t \r]*\n(?:[\t \r]*\n)*", full[a:z]):
            end = a + match.end()
            ranges.append([start, end, "paragraph"])
            start = end
        if start < z:
            ranges.append([start, z, "paragraph"])

    cursor = 0
    for a, z, kind in spans:
        if a > cursor:
            fallback(cursor, a)
        ranges.append([a, z, kind])
        cursor = z
    if cursor < len(full):
        fallback(cursor, len(full))

    # Formatting-only gaps belong to their neighbouring block, not an empty p.
    merged = []
    for a, z, kind in ranges:
        if not full[a:z].strip():
            if merged:
                merged[-1][1] = z
            continue
        merged.append([0 if not merged else a, z, kind])
    if not merged and full:
        merged = [[0, len(full), "paragraph"]]

    paragraphs = []
    anchored = False
    for a, z, kind in merged:
        cuts = {a, z}
        if witness:
            cuts.update(v for v in (witness["start_offset"], witness["end_offset"]) if a < v < z)
        points = sorted(cuts)
        fragments = []
        for start, end in zip(points, points[1:]):
            selected = bool(
                witness and start < witness["end_offset"] and end > witness["start_offset"]
            )
            anchor = "passage-" + witness["unit_id"] if selected and not anchored else None
            anchored |= selected
            fragments.append(dict(text=full[start:end], selected=selected, anchor=anchor))
        paragraphs.append(dict(kind=kind, start_offset=a, end_offset=z, fragments=fragments))
    return paragraphs
