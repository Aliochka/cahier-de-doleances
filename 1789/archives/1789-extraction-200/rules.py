"""Règles déterministes ; développées seulement sur le pilote et Pecqueuse."""

import re

from common import compact
from pilot_segment import CLOSE, NOTE, trim

# Recognition tolerates observed typographic variants, without rewriting source text.
TITLE = re.compile(
    r"^(?:[\W_]*)(?:CA[HIl]I?ER[8S]?\b|CAHIER\b|D[O0Ô]L[ÉEÈ]ANCE[S]?\b|PLAINTES?\b|REMONTRANCES?\b|DEMANDES ET D[O0]L[ÉE]ANCES\b)",
    re.I,
)
MENTION = re.compile(r"cah[iil1]ers?|dol[éeè]ances?|remontrances?", re.I)
INTRO = re.compile(
    r"^(?:des?|du|pour|par|que|r[ée]dig[ée])\b.{0,200}\b(?:d[ée]put[ée]s|habitants|communaut[ée]|paroisse|ordre|clerg[ée]|noblesse|tiers)",
    re.I,
)
MISSING = re.compile(
    r"(?:n['’]avons pu|n['’]a pu|pas [ée]t[ée] possible|impossible).{0,110}(?:trouv|retrouv)|cahier.{0,60}(?:introuvable|manquant)",
    re.I,
)
EXTRACT = re.compile(r"^\W*(?:extrait|fragment|abr[ée]g[ée])\b", re.I)
ANNEX = re.compile(
    r"^\W*(?:proc[èe]s.verbal|lettre|m[ée]moire|arr[êe]t[ée]?|protestation|d[ée]claration|instruction[s]? aux|pouvoirs|observations|r[ée]ponse)\b",
    re.I,
)
CONT = re.compile(
    r"^(?:CHAPITRE\b|CONSTITUTION\b|AGRICULTURE\b|COMMERCE\b|JUSTICES\b|DEMANDES PARTICULI[ÈE]RES\b|TRAVAIL\b|SUPPL[ÉE]MENT AU CAHIER\b)",
    re.I,
)
ARTICLE = re.compile(
    r"(?<!\w)(?:Article|Art|Arf)\b['’.,\-;:]*\s*(\d+(?:er|re|e)?|ler|Ier|il)?[.,;:]?", re.I
)
ORDINAL = re.compile(r"(?<!\w)\d{1,3}\s*[°ºo®*»«](?=\s|[-.,:;A-ZÀ-Ü])")
FINAL = re.compile(
    r"^(?:Ce fut fait|Ce pr[ée]sent cahier|Au surplus|Lesdits articles|Les pr[ée]sents articles|Ainsi arr[êe]t[ée]|Arr[êe]t[ée] en|Tels sont|En foi de|Donn[ée] [àa]|Dont acte|D[ée]lib[ée]r[ée]|Pouvoirs|Le pr[ée]sent cahier)",
    re.I,
)
INLINE_SIGN = re.compile(r"(?<!\w)Sign[ée]\s+[A-ZÀ-Ü]", re.I)


def classify(title, opening, length, structural=True):
    text = title + " " + opening
    signals = []
    if MENTION.search(title):
        signals.append("documentary_title_word")
    if TITLE.match(title):
        signals.append("title_start_formula")
    if re.search(
        r"(?:cahier|dol[ée]ances).{0,100}(?:habitants|ordre|communaut[ée]|paroisse)|(?:habitants|ordre|communaut[ée]|paroisse).{0,100}(?:cahier|dol[ée]ances)",
        text,
        re.I,
    ):
        signals.append("documentary_opening")
    if re.search(r"\b(?:clerg[ée]|noblesse|tiers[ -][ée]tat)\b", title + " " + opening[:300], re.I):
        signals.append("explicit_estate_word")
    if MISSING.search(text[:1400]):
        return "notice_missing", signals + ["absence_formula"]
    if EXTRACT.match(title):
        return "published_extract", signals + ["extract_title"]
    if CONT.match(title):
        return "continuation", signals + ["continuation_title"]
    if ANNEX.match(title) and not TITLE.match(title):
        return "attached_or_other_document", signals + ["other_document_title"]
    if structural and (TITLE.match(title) or "documentary_opening" in signals):
        if length < 220:
            return "uncertain_short_notice", signals + ["very_short_text"]
        return "document_candidate", signals
    return "incidental_or_uncertain", signals


def role(node, first=False):
    text = compact(node)
    if node.tag == "head":
        return "heading"
    if node.tag == "note" or NOTE.match(text):
        return "editorial_note"
    if node.tag != "p":
        return node.tag
    if CLOSE.match(text) or FINAL.match(text):
        return "closing_or_signature"
    if first and INTRO.match(text) and not ARTICLE.match(text):
        return "title"
    if len(text) < 150 and (text.isupper() or text.startswith("§")):
        return "section_heading"
    return "body"


def blocks(source, document):
    output = []
    for di, xp in enumerate(document["divisions"]):
        node = source.node(xp)
        for child in node:
            if not isinstance(child.tag, str):
                continue
            a, b = source.span(child)
            if b <= document["start"] or a >= document["end"]:
                continue
            if child.tag.startswith("div"):
                continue
            xpchild = source.tree.getpath(child)
            rr = role(
                child, first=child.tag == "p" and len(child.xpath("preceding-sibling::p")) == 0
            )
            a, b = max(a, document["start"]), min(b, document["end"])
            output.append(
                dict(
                    xpath=xpchild,
                    division=di,
                    tag=child.tag,
                    start=a,
                    end=b,
                    role=rr,
                    line=child.sourceline,
                )
            )
    return sorted(output, key=lambda b: (b["start"], b["end"]))


def segment(source, bs):
    """Adaptation du segmenteur du pilote ; les articles se prolongent entre p."""
    result = []
    current = None
    mode = None
    previous_division = None

    def finish():
        nonlocal current
        if current:
            current["start"], current["end"] = trim(source.text, current["start"], current["end"])
            if current["start"] < current["end"]:
                result.append(current)
            current = None

    for block in bs:
        if block["tag"] in {"pb", "note"} or block["role"] == "editorial_note":
            continue
        if block["division"] != previous_division:
            finish()
            mode = None
            previous_division = block["division"]
        if block["role"] != "body":
            finish()
            mode = None
            continue
        if block["tag"] != "p":
            continue
        a, b = block["start"], block["end"]
        text = source.text[a:b]
        excluded = [source.span(n) for n in source.node(block["xpath"]).xpath(".//note")]
        markers = [
            m
            for m in ARTICLE.finditer(text)
            if not any(x <= a + m.start() < y for x, y in excluded)
        ]
        # Lower-case references within prose are not article starts by themselves.
        markers = [
            m
            for m in markers
            if m.start() == 0 or m.group()[0].isupper() or not text[: m.start()].strip()
        ]
        if markers:
            mode = "article"
        elif mode != "article":
            markers = list(ORDINAL.finditer(text))
            mode = "ordinal" if markers else mode
        if not markers:
            if current:
                current["end"] = b
                current["xml_blocks"].append(block["xpath"])
        else:
            if current:
                current["end"] = a + markers[0].start()
            for j, m in enumerate(markers):
                finish()
                current = dict(
                    start=a + m.start(),
                    end=a + markers[j + 1].start() if j + 1 < len(markers) else b,
                    label_exact=m.group(),
                    division=block["division"],
                    xml_blocks=[block["xpath"]],
                    rule=mode,
                )
        # A signature in the same paragraph must not be absorbed into an article.
        sig = INLINE_SIGN.search(text)
        if current and sig and a + sig.start() > current["start"]:
            current["end"] = a + sig.start()
            finish()
            mode = None
    finish()
    return result
