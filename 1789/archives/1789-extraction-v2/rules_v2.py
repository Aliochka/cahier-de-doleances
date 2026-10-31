"""V2: contexte documentaire et limites, sans réécriture du texte source."""

import re
import unicodedata

import rules as v1
from common import compact


def fold(text):
    return (
        "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
        .upper()
        .replace("’", "'")
    )


MISSING = re.compile(
    r"(?:CAHIERS?|DOCUMENTS?).{0,100}(?:MANQU(?:E|ENT)\b|NE SE TROUV.{0,15}PAS|N[' ]A.{0,15}(?:PU|ETE).{0,30}RETROUV|INTROUVABLE)|N[' ]AVONS PU.{0,80}(?:RETROUV|TROUV)|IMPOSSIBLE.{0,80}(?:TROUV|RETROUV)"
)
BEGIN = re.compile(
    r"^(?:CA[HIl1]I?ERS?\b|D[O0]LEANCES?\b|PLAINTES?\b|REMONTR\w*\b|MANDATS?\b|INSTRUCTIONS?\b)"
)
PART = re.compile(
    r"^(?:CHAPITRE|SECTION|CONSTITUTION|AGRICULTURE|COMMERCE|JUSTICES|FINANCES|RELIGION|PLAINTES LOCALES|DOLEANCES POUR (?:LE|LA|LES)|ARTICLES (?:PRELIMINAIRES|DIVERS))\b"
)
ANNEX = re.compile(
    r"^(?:DEMANDES PARTICULIERES|SUPPLEMENT|TRAVAIL|MEMOIRE|POUVOIRS|PROTESTATION)\b"
)
PROFESSIONAL = re.compile(
    r"MEDECINS|PROCUREURS|APOTHICAIRES|PERRUQUIERS|CORPS ET COMMUNAUT|CORPS DE|CORPS DES|MAITRES |COMPAGNIE DES|MARCHANDS"
)
LOCAL = re.compile(
    r"(?:PAROISSE|COMMUNAUTE|HABITANTS|ORDRE|CLERGE|NOBLESSE|TIERS.ETAT|BAILLIAGE|SENECHAUSSEE|VILLE)\b"
)
ARTICLE = re.compile(
    r"(?<!\w)(?:Article|Art|Arf|Àri)(?:\b|(?=(?:Ier|ler|1er)[.,]))['’.,\-;:]*\s*(\d+(?:er|re|e)?|ler|Ier|il|er)?[.,;:]?",
    re.I,
)
ORDINAL = v1.ORDINAL


def classify(node, title, opening, internal=False, enclosing_kind=None):
    """Six classes explicites ; incertitude conservée au lieu d'une admission forcée."""
    t = fold(title).strip()
    o = fold(opening)
    text = t + " " + o
    heads = " ".join(
        compact(h) for h in node.xpath('ancestor-or-self::*[starts-with(local-name(),"div")]/head')
    )
    context = fold(heads)
    years = [
        int(x)
        for x in re.findall(
            r"\b1[0-9]{3}\b", fold(" ".join(compact(h) for h in node.findall("head")))
        )
    ]
    evidence = []
    if "INTRODUCTION" in context or (years and max(years) < 1789):
        return "out_of_scope", "historical_or_editorial_context", ["context_heading_outside_1789"]
    if MISSING.search(text[:2200]):
        return "out_of_scope", "missing_document_notice", ["explicit_absence"]
    if PART.match(t):
        return "part", "section_heading", ["structural_section_title"]
    if internal and ("DOLEANCES POUR" in t or "PLAINTES LOCALES" in t):
        return "part", "internal_rubric", ["no_new_document_identity"]
    markers = sum(
        bool(ARTICLE.match(compact(p)) or ORDINAL.match(compact(p))) for p in node.findall("p")
    )
    substantive = markers >= 2 or bool(re.search(r"SUPPL|DEMAND|RECLAM|V[OŒ]EU|REMONT", o))
    if "PROCES" in t and "VERBAL" in t:
        if ("DOLEANCE" in t or "PLAINT" in t) and substantive:
            return "associated", "doleances_in_minutes", ["substantive_doleances_inside_PV"]
        return (
            "out_of_scope",
            "minutes_or_electoral_record",
            ["PV_without_explicit_doleances_title"],
        )
    if t.startswith(("LETTRE", "ARRET", "ORDONNANCE", "REGLEMENT")):
        return "out_of_scope", "administrative_or_regulatory_document", ["different_document_genre"]
    if t.startswith("EXTRAIT"):
        if "CAHIER" in text or "DOLEANCE" in text:
            return "associated", "published_extract", ["published_extract_not_assumed_complete"]
        return "out_of_scope", "other_extract", ["extract_without_substantive_cahier_title"]
    if ANNEX.match(t):
        if (
            "DOLEANCE" in text
            or "REMONT" in text
            or "CAHIER" in text
            or t.startswith(("DEMANDES PARTICULIERES", "TRAVAIL"))
        ):
            return (
                "associated",
                "annex_or_memorandum",
                ["associated_document_not_new_autonomous_cahier"],
            )
        return "uncertain", "other_memorandum", ["genre_not_established"]
    if PROFESSIONAL.search(t) and ("DOLEANCE" in t or "MEMOIRE" in t):
        return "associated", "professional_doleances", ["professional_subdocument"]
    if BEGIN.match(t):
        if internal:
            first = title.strip().split()[0] if title.strip() else ""
            canonical = fold(first) == "CAHIER" and first.isupper()
            new_locality = bool(LOCAL.search(text[:650]))
            if canonical and new_locality:
                return (
                    "autonomous",
                    "internal_cahier_title",
                    ["uppercase_cahier_and_new_document_identity"],
                )
            if (
                t.startswith(("DOLEANCE", "D0LEANCE", "PLAINT"))
                and new_locality
                and ("DE LA COMMUNAUTE" in text or "DE LA PAROISSE" in text)
            ):
                return "autonomous", "internal_local_doleances", ["local_document_identity"]
            return "part", "internal_title_without_autonomy", ["no_strong_document_restart"]
        if t.startswith(("CAHIER", "CAHIERS")) or (LOCAL.search(text[:650]) and substantive):
            return (
                "autonomous",
                "cahier_or_instructions",
                ["document_title_and_substantive_opening"],
            )
        return "uncertain", "possible_doleances", ["opening_requires_review"]
    if re.search(r"CAHIER|DOLEANCE|PLAINT|REMONTR", text[:1200]):
        return "uncertain", "documentary_mention", ["not_enough_to_infer_autonomy"]
    return "mention", "not_a_cahier_start", []


def title_of(node):
    heads = [compact(h) for h in node.findall("head")]
    ps = node.findall("p")
    title = " ".join(heads)
    if not title and ps:
        first = compact(ps[0])
        if len(first) < 240:
            title = first
            if fold(first).strip() in {"CAHIER", "CAHIERS"} and len(ps) > 1:
                title += " " + compact(ps[1])
    return title, " ".join(compact(p) for p in ps[:3])


def role_blocks(source, document):
    from fast_blocks import blocks

    bs = blocks(source, document)
    # Short nominal headings immediately before a new numbered article are structural.
    ps = [b for b in bs if b["tag"] == "p"]
    for i, b in enumerate(ps[:-1]):
        text = compact(source.node(b["xpath"]))
        next_text = compact(source.node(ps[i + 1]["xpath"]))
        previous_text = compact(source.node(ps[i - 1]["xpath"])) if i else ""
        follows_bare_marker = bool(
            ARTICLE.fullmatch(previous_text) or ORDINAL.fullmatch(previous_text)
        )
        nominal = bool(
            text
            and text[0].isupper()
            and len(text) < 95
            and len(text.split()) <= 12
            and text.endswith(".")
            and not re.search(r"\b(?:QUE|SOIT|SERA|SONT|EST|DEVR|PEUT|ILS|ON)\b", fold(text))
        )
        if (
            nominal
            and not follows_bare_marker
            and not ARTICLE.match(text)
            and not ORDINAL.match(text)
            and (ARTICLE.match(next_text) or ORDINAL.match(next_text))
        ):
            b["role"] = "section_heading"
        if re.match(r"^(?:Seront tenus les députés|Les députés seront tenus)", text, re.I):
            b["role"] = "closing_or_signature"
    return bs


def segment(source, bs):
    """Même priorité Art./ordinal que V1, avec ponctuation préfixe conservée dans son p."""
    result = []
    current = None
    mode = None
    previous = None

    def finish():
        nonlocal current
        if current:
            current["start"], current["end"] = v1.trim(
                source.text, current["start"], current["end"]
            )
            if current["start"] < current["end"]:
                result.append(current)
            current = None

    for block in bs:
        if block["tag"] in {"pb", "note"} or block["role"] == "editorial_note":
            continue
        if block["division"] != previous:
            finish()
            mode = None
            previous = block["division"]
        if block["role"] != "body":
            finish()
            mode = None
            continue
        if block["tag"] != "p":
            continue
        a, b = block["start"], block["end"]
        text = source.text[a:b]
        excluded = [source.span(n) for n in source.node(block["xpath"]).xpath(".//note")]
        matches = [
            m
            for m in ARTICLE.finditer(text)
            if not any(x <= a + m.start() < y for x, y in excluded)
            and (m.start() == 0 or m.group()[0].isupper() or not text[: m.start()].strip())
        ]
        if matches:
            mode = "article"
        elif mode != "article":
            matches = list(ORDINAL.finditer(text))
            mode = "ordinal" if matches else mode
        markers = []
        for m in matches:
            pos = m.start()
            if text[:pos].strip() and re.fullmatch(r"[\s,.;:—–\-]+", text[:pos]):
                pos = len(text[:pos]) - len(text[:pos].lstrip())
            markers.append((pos, m.end(), text[pos : m.end()]))
        if not markers:
            if current:
                current["end"] = b
                current["xml_blocks"].append(block["xpath"])
        else:
            if current:
                current["end"] = a + markers[0][0]
            for j, (pos, stop, label) in enumerate(markers):
                finish()
                current = dict(
                    start=a + pos,
                    end=a + markers[j + 1][0] if j + 1 < len(markers) else b,
                    label_exact=label,
                    division=block["division"],
                    xml_blocks=[block["xpath"]],
                    rule=mode,
                )
        sig = v1.INLINE_SIGN.search(text)
        if current and sig and a + sig.start() > current["start"]:
            current["end"] = a + sig.start()
            finish()
            mode = None
    finish()
    return result
