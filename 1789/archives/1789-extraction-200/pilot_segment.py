"""Règles du pilote reprises à l’identique pour comparaison et régression."""

import re

from common import compact

ARTICLE = re.compile(
    r"(?<!\w)(?:Article|Art|ART|ARTICLE)\b[.,\-;:]*\s*(\d+(?:er|re|e)?|ler|Ier|il)?[.,;:]?"
)

ORDINAL = re.compile(r"(?<!\w)\d{1,3}\s*[°ºo®*»«](?=\s|[A-ZÀ-Ü])")

CLOSE = re.compile(
    r"^(?:[-.,'’\s]*Sign[ée]|Fait[ ,]|Ainsi (?:fait|arrêté)|Arrêté le|Lecture ayant|Telles sont|Ces points|Pour copie|Collation|Gollation|Clos et|De tout quoi|Le présent cahier)",
    re.I,
)

CONTINUATION = re.compile(
    r"^(CHAPITRE\b|CONSTITUTION\b|AGRICULTURE\b|COMMERCE\b|JUSTICES\b|DEMANDES PARTICULIÈRES\b|TRAVAIL\b)",
    re.I,
)

START = re.compile(
    r"^(CAHIER\b|DEMANDES ET DOLÉANCES\b|DOLÉANCES ET (REPRÉSENTATIONS|REMONTRANCES)\b|PLAINTES,? DOLÉANCES\b)",
    re.I,
)

NOTE = re.compile(r"^\(?[.,]?\s*\d+\)\s*Nous publions", re.I)


def trim(text, start, end):
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def auto_role(node, index, count):
    text = compact(node)
    if node.tag == "head":
        return "heading"
    if node.tag == "note":
        return "editorial_note"
    if node.tag != "p":
        return node.tag
    if NOTE.match(text):
        return "editorial_note_unmarked"
    if CLOSE.match(text):
        return "closing_or_signature"
    if (
        index == 1
        and not ARTICLE.match(text)
        and not ORDINAL.match(text)
        and re.match(r"^(des? |du |concernant )", text, re.I)
    ):
        return "title"
    if len(text) < 150 and (text.isupper() or text.startswith("§")):
        return "section_heading"
    return "body"


def segment(source, blocks):
    """Priorité aux Art. ; les listes ordinales internes restent dans leur article.

    Pas de correction de caractères OCR. Une discontinuité de numérotation est un
    avertissement, jamais une autorisation à fabriquer un article absent.
    """
    result = []
    current = None
    mode = None
    previous_division = None
    body_roles = {"body", "supplement_body", "supporting_memorandum", "internal_subheading"}

    def finish():
        nonlocal current
        if current:
            current["start"], current["end"] = trim(source.text, current["start"], current["end"])
            result.append(current)
            current = None

    for block in blocks:
        if block["tag"] in {"pb", "note"} or block["role"] in {
            "editorial_note_unmarked",
            "editorial_running_header",
        }:
            continue
        if block["division"] != previous_division:
            finish()
            mode = None
            previous_division = block["division"]
        if block["role"] not in body_roles:
            finish()
            mode = None
            continue
        if block["tag"] != "p":
            continue
        a, b = block["start"], block["end"]
        text = source.text[a:b]
        # Ne jamais détecter les références d'articles à l'intérieur d'une note.
        node = source.node(block["xpath"])
        excluded = [source.span(n) for n in node.xpath(".//note")]
        explicit = [
            m
            for m in ARTICLE.finditer(text)
            if not any(x <= a + m.start() < y for x, y in excluded)
        ]
        if explicit:
            markers = explicit
            mode = "article"
        elif mode != "article":
            markers = list(ORDINAL.finditer(text))
            # Les occurrences dans la prose sont des candidats B, pas une preuve.
            mode = "ordinal" if markers else mode
        else:
            markers = []
        if not markers:
            if current:
                current["end"] = b
                current["xml_blocks"].append(block["xpath"])
            continue
        # Le texte avant un marqueur au milieu d'un p prolonge l'article précédent.
        if current:
            current["end"] = a + markers[0].start()
        for j, marker in enumerate(markers):
            finish()
            end = a + markers[j + 1].start() if j + 1 < len(markers) else b
            current = {
                "start": a + marker.start(),
                "end": end,
                "label_exact": marker.group(),
                "division": block["division"],
                "xml_blocks": [block["xpath"]],
                "rule": mode,
                "status": "B",
                "validation": "not_individually_verified",
            }
        # La dernière unité est prolongée par les paragraphes suivants.
    finish()
    return result


def subtract(start, end, excluded):
    spans = []
    cursor = start
    for a, b in sorted(excluded):
        if b <= cursor or a >= end:
            continue
        if a > cursor:
            spans.append([cursor, min(a, end)])
        cursor = max(cursor, b)
    if cursor < end:
        spans.append([cursor, end])
    return spans
