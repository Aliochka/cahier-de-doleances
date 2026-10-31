"""Extraction locale déterministe ; décisions documentaires et référence restent externes.

Les identifiants reposent sur la source figée, les XPath et les positions Unicode.
Le résultat automatique brut est enregistré AVANT l'application des décisions de revue.
"""

import argparse
import copy
import re
import time
from collections import Counter
from datetime import datetime, timezone

from common import CORPUS, METHOD, REVISION, ROOT, compact, load_sources, read, sha, write
from lxml import etree as ET

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


def locator(source, row, spec, window=False):
    base = row["divisions"][spec["division"]]
    a = source.node(f"{base}/p[{spec['first']}]")
    b = source.node(f"{base}/p[{spec['last']}]")
    start, end = source.span(a)[0], source.span(b)[1]
    if spec.get("start_quote"):
        start += source.text[start : source.span(a)[1]].index(spec["start_quote"])
    if spec.get("end_quote"):
        end = source.span(b)[0] + source.text[source.span(b)[0] : end].index(spec["end_quote"])
    return trim(source.text, start, end)


def auto_parent(source, first_xpath):
    first = source.node(first_xpath)
    title = " ".join(compact(h) for h in first.findall("head"))
    if not START.match(title):
        return None
    # Extraits/notices : tests conservateurs, pas une classification historique exhaustive.
    if re.search(
        r"\b(?:extrait|nous n'avons pu|n'avons pas|ne se trouve pas|impossible.{0,80}trouver ce cahier)\b",
        title + " " + " ".join(compact(p) for p in first.findall("p")[:2]),
        re.I,
    ):
        return None
    divisions = [first_xpath]
    for following in first.xpath("following-sibling::div3"):
        title = " ".join(compact(h) for h in following.findall("head"))
        if not CONTINUATION.match(title):
            break
        divisions.append(source.tree.getpath(following))
    return {
        "divisions": divisions,
        "start": source.span(first)[0],
        "end": source.span(source.node(divisions[-1]))[1],
    }


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


def blocks_for(source, row, reviewed):
    blocks = []
    for di, xp in enumerate(row["divisions"]):
        division = source.node(xp)
        ps = division.findall("p")
        for node in division:
            if not isinstance(node.tag, str):
                continue
            a, b = source.span(node)
            pn = ps.index(node) + 1 if node.tag == "p" else None
            role = auto_role(node, pn, len(ps))
            if reviewed and pn:
                for rule in row["regions"]:
                    if rule["division"] == di and rule["first"] <= pn <= rule["last"]:
                        role = rule["role"]
            if row.get("end_at") and reviewed:
                end_spec = row["end_at"]
                endpoint = source.span(
                    source.node(
                        row["divisions"][end_spec["division"]] + f"/p[{end_spec['paragraph']}]"
                    )
                )[1]
                if a >= endpoint:
                    continue
            blocks.append(
                {
                    "xpath": source.tree.getpath(node),
                    "division": di,
                    "paragraph": pn,
                    "tag": node.tag,
                    "start": a,
                    "end": b,
                    "role": role,
                }
            )
    return blocks


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


def jlines(name, rows):
    import json

    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / name).write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows)
    )


def run(directory):
    started = datetime.now(timezone.utc).isoformat()
    wall, cpu = time.perf_counter(), time.process_time()
    sources = load_sources(directory)
    loaded = time.perf_counter()
    decisions = read("decisions.json")
    docs, units, predictions, refs, registers, retained = [], [], [], [], [], []
    old_docs = {d["key"]: d for d in read("../1789-multicorpus/data/documents.json")}
    external = {
        d["stanford_document_id"]: d for d in read("../1789-sources-comparison/data/documents.json")
    }
    old_passages = read("../1789-multicorpus/data/passages.json")
    metrics = {"documents": [], "windows": []}
    for row in decisions["documents"]:
        source = sources[row["volume"]]
        first = source.node(row["divisions"][0])
        start = source.span(first)[0]
        end = source.span(source.node(row["divisions"][-1]))[1]
        if row.get("end_at"):
            spec = row["end_at"]
            end = source.span(
                source.node(row["divisions"][spec["division"]] + f"/p[{spec['paragraph']}]")
            )[1]
        druid = source.path.stem
        identity = sha(f"{REVISION}|{source.sha256}|{row['divisions']}|{start}|{end}")[:20]
        doc_id = f"ap1789-pilot-d1:{druid}:{identity}"
        auto = auto_parent(source, row["divisions"][0])
        parent_match = bool(
            auto
            and auto["start"] == start
            and auto["end"] == end
            and auto["divisions"] == row["divisions"]
        )
        raw_blocks = blocks_for(source, row, False)
        blocks = blocks_for(source, row, True)
        sections = []
        for di, xp in enumerate(row["divisions"]):
            node = source.node(xp)
            a, b = source.span(node)
            sections.append(
                {
                    "id": "section-" + sha(doc_id + xp)[:16],
                    "kind": "division",
                    "xpath": xp,
                    "division": di,
                    "start": a,
                    "end": min(b, end),
                    "title_exact": ["".join(h.itertext()) for h in node.findall("head")],
                }
            )
            headings = [
                block
                for block in blocks
                if block["division"] == di and block["role"] == "section_heading"
            ]
            for i, heading in enumerate(headings):
                following = headings[i + 1]["start"] if i + 1 < len(headings) else min(b, end)
                sections.append(
                    {
                        "id": "section-" + sha(doc_id + heading["xpath"])[:16],
                        "kind": "paragraph_heading",
                        "xpath": heading["xpath"],
                        "division": di,
                        "start": heading["start"],
                        "end": following,
                        "title_exact": [source.text[heading["start"] : heading["end"]]],
                    }
                )
        raw = segment(source, raw_blocks)
        proposals = segment(source, blocks)
        raw_end = auto["end"] if auto else source.span(first)[1]
        raw = [u for u in raw if start <= u["start"] < raw_end]
        for u in raw:
            u.update(document_id=doc_id, document_key=row["key"])
        predictions.extend(raw)
        annotations = []
        for node in source.tree.xpath("//note"):
            a, b = source.span(node)
            if start <= a < end:
                annotations.append(
                    {
                        "kind": "editorial_note",
                        "start": a,
                        "end": b,
                        "xpath": source.tree.getpath(node),
                    }
                )
        for b in blocks:
            if b["role"] != "body" and b["tag"] not in {"pb", "head", "note"}:
                annotations.append(
                    {"kind": b["role"], "start": b["start"], "end": b["end"], "xpath": b["xpath"]}
                )
        for rule in row.get("inline_roles", []):
            node = source.node(row["divisions"][rule["division"]] + f"/p[{rule['paragraph']}]")
            a, b = source.span(node)
            a += source.text[a:b].index(rule["start_quote"])
            annotations.append(
                {
                    "kind": rule["role"],
                    "start": a,
                    "end": b,
                    "xpath": source.tree.getpath(node),
                    "decision": "reviewed_inline_boundary",
                }
            )
        all_gold = []
        for wi, window in enumerate(row["reference_windows"]):
            wa, wb = locator(source, row, window, True)
            gold = []
            for spec in window["units"]:
                a, b = locator(source, row, spec)
                assert wa <= a < b <= wb, (row["key"], a, b, wa, wb)
                gold.append(
                    {
                        "start": a,
                        "end": b,
                        "division": spec["division"],
                        "xml_blocks": [
                            row["divisions"][spec["division"]] + f"/p[{i}]"
                            for i in range(spec["first"], spec["last"] + 1)
                        ],
                        "status": "A" if window.get("certainty", "A") == "A" else "B",
                        "validation": "xml_boundaries_reviewed"
                        if window.get("certainty", "A") == "A"
                        else "boundary_uncertain",
                        "reference_window": wi,
                        "rule": "reviewed_reference",
                        "label_exact": None,
                        "label_length": spec.get("label_length"),
                    }
                )
            ref = {
                "document_id": doc_id,
                "document_key": row["key"],
                "window": wi,
                "start": wa,
                "end": wb,
                "certainty": window.get("certainty", "A"),
                "basis": window["review_basis"],
                "comment": window["comment"],
                "units": gold,
            }
            refs.append(ref)
            if ref["certainty"] == "A":
                predicted = [p for p in raw if wa <= p["start"] < wb]
                pairs = {(u["start"], u["end"]) for u in gold}
                starts, ends = {u["start"] for u in gold}, {u["end"] for u in gold}
                ps, pe = {u["start"] for u in predicted}, {u["end"] for u in predicted}
                metrics["windows"].append(
                    {
                        "document_key": row["key"],
                        "window": wi,
                        "gold": len(gold),
                        "predicted": len(predicted),
                        "correct_starts": len(ps & starts),
                        "missed_starts": len(starts - ps),
                        "wrong_starts": len(ps - starts),
                        "correct_ends": len(pe & ends),
                        "missed_ends": len(ends - pe),
                        "wrong_ends": len(pe - ends),
                        "correct_units": sum((u["start"], u["end"]) in pairs for u in predicted),
                    }
                )
                # Correction explicite limitée aux fenêtres contrôlées ; jamais validation implicite du reste.
                proposals = [p for p in proposals if not (p["start"] < wb and p["end"] > wa)]
                proposals.extend(copy.deepcopy(gold))
                all_gold.extend(gold)
        proposals.sort(key=lambda p: p["start"])
        # Les signatures intégrées ne sont pas du texte de revendication.
        excluded_kinds = {
            "editorial_note",
            "editorial_note_unmarked",
            "editorial_running_header",
            "signatures",
        }
        excluded = [(a["start"], a["end"]) for a in annotations if a["kind"] in excluded_kinds]
        doc_units = []
        for order, u in enumerate(proposals, 1):
            spans = subtract(u["start"], u["end"], excluded)
            if not spans:
                continue
            uid = f"ap1789-pilot-u1:{identity}:{sha(str((u['start'], u['end'])))[:16]}"
            text = "".join(source.text[a:b] for a, b in spans)
            first_p = source.text[u["start"] : u["end"]]
            marker = ARTICLE.match(first_p) or ORDINAL.match(first_p)
            if not marker:
                near = ARTICLE.search(first_p[:20]) or ORDINAL.search(first_p[:20])
                marker = near if near and near.start() <= 3 else None
            label = (
                u["label_exact"]
                if u["label_exact"] is not None
                else first_p[: marker.end()]
                if marker
                else None
            )
            # Cas OCR dont le marqueur n'est pas reconnu : la référence peut fournir
            # la longueur exacte du préfixe, sans substituer le numéro historique.
            if not label and u.get("label_length"):
                label = first_p[: u["label_length"]]
            notes = [
                a
                for a in annotations
                if a["kind"] in excluded_kinds and a["start"] < u["end"] and a["end"] > u["start"]
            ]
            data = {
                **u,
                "id": uid,
                "anchor": "unit-" + uid.split(":")[-1],
                "document_id": doc_id,
                "corpus_id": CORPUS,
                "order": order,
                "label_exact": label,
                "historical_number": None,
                "kind": "documentary_article_candidate",
                "text": text,
                "text_sha256": sha(text),
                "text_spans": spans,
                "parent_start": u["start"] - start,
                "parent_end": u["end"] - start,
                "section": u["division"],
                "pages": source.pages_for(u["start"], u["end"]),
                "separated_annotations": notes,
                "source_revision": REVISION,
                "method_version": METHOD,
                "source_sha256": source.sha256,
                "legacy_passage_ids": [],
            }
            enclosing = [s for s in sections if s["start"] <= u["start"] < s["end"]]
            data["section_id"] = min(enclosing, key=lambda s: s["end"] - s["start"])["id"]
            data["source_file"] = f"{druid}/{druid}.xml"
            data["source_url"] = (
                f"https://github.com/StanfordUniversityLibraries/ap_tei/blob/{REVISION}/{druid}/{druid}.xml"
            )
            data["scan_url"] = f"https://purl.stanford.edu/{druid}"
            data["document_key"] = row["key"]
            data["volume"] = row["volume"]
            data["document_title"] = row["title_display"]
            data["metadata"] = {
                k: row[k]
                for k in [
                    "estate",
                    "locality",
                    "territory",
                    "date",
                    "metadata_provenance",
                    "date_provenance",
                ]
            }
            data["historical_number"] = (
                re.search(r"\d+(?:er|re|e)?", label).group()
                if marker and label and re.search(r"\d+(?:er|re|e)?", label)
                else None
            )
            data["number_provenance"] = (
                "literal token in label, no OCR restoration" if data["historical_number"] else None
            )
            if row["key"] == "mirecourt-noblesse" and u["division"] > 0:
                data["kind"] = "attached_document_numbered_unit_candidate"
            if any(
                b["role"] == "supplement_body" and b["start"] <= u["start"] < b["end"]
                for b in blocks
            ):
                data["kind"] = "supplement_numbered_unit_candidate"
            # Les anciens identifiants ne sont associés que sur égalité exacte du texte.
            for old in old_passages:
                if (
                    old.get("document_id") == old_docs.get(row["key"], {}).get("id")
                    and old.get("text") == text
                ):
                    data["legacy_passage_ids"].append(old["id"])
            doc_units.append(data)
        for i, u in enumerate(doc_units):
            u["previous_unit_id"] = doc_units[i - 1]["id"] if i else None
            u["next_unit_id"] = doc_units[i + 1]["id"] if i + 1 < len(doc_units) else None
            u["warnings"] = [] if u["status"] == "A" else ["boundaries_not_individually_verified"]
            if not u["historical_number"]:
                u["warnings"].append("number_not_reliably_read")
        units.extend(doc_units)
        # Chaque octet XML original reste dans la source figée ; les positions concernent son texte décodé.
        pages = source.pages_for(start, end)
        for p in pages:
            p["image_service"] = (
                f"https://stacks.stanford.edu/image/iiif/{druid}%2F{p['id']}"
                if p.get("id")
                else None
            )
        titles = [
            {"xpath": source.tree.getpath(h), "text": "".join(h.itertext())}
            for h in first.findall("head")
        ]
        for rule in row["regions"]:
            if rule["role"] == "title" and rule["division"] == 0:
                for n in range(rule["first"], rule["last"] + 1):
                    p = source.node(row["divisions"][rule["division"]] + f"/p[{n}]")
                    titles.append({"xpath": source.tree.getpath(p), "text": "".join(p.itertext())})
        full = source.text[start:end]
        header = source.tree.find("teiHeader")
        document = {
            "id": doc_id,
            "key": row["key"],
            "corpus_id": CORPUS,
            "title_display": row["title_display"],
            "title_parts_exact": titles,
            "date_elements_exact": [
                {
                    "xpath": source.tree.getpath(n),
                    "attributes": dict(n.attrib),
                    "text": "".join(n.itertext()),
                    "start": source.span(n)[0],
                    "end": source.span(n)[1],
                }
                for xp in row["divisions"]
                for n in source.node(xp).xpath(".//date")
                if start <= source.span(n)[0] < end
            ],
            "full_text": full,
            "full_text_sha256": sha(full),
            "source_text_start": start,
            "source_text_end": end,
            "offset_convention": "Unicode codepoints in decoded XML itertext, half-open; no whitespace folding, no Unicode normalization",
            "source_file": f"{druid}/{druid}.xml",
            "source_sha256": source.sha256,
            "source_text_sha256": sha(source.text),
            "source_revision": REVISION,
            "source_url": f"https://github.com/StanfordUniversityLibraries/ap_tei/blob/{REVISION}/{druid}/{druid}.xml",
            "scan_url": f"https://purl.stanford.edu/{druid}",
            "volume": row["volume"],
            "divisions": row["divisions"],
            "pages": pages,
            "blocks": blocks,
            "sections": sections,
            "bibliography": {
                "collection": "Archives parlementaires, première série",
                "edition_dates_exact": [
                    "".join(n.itertext()) for n in header.xpath(".//sourceDesc//date")
                ],
                "source_description_exact": "".join(header.find("fileDesc/sourceDesc").itertext()),
                "historical_original": "Cahier de 1789 publié dans l’édition du XIXe siècle ; aucune assimilation au manuscrit original.",
            },
            "annotations": annotations,
            "unit_ids": [u["id"] for u in doc_units],
            "metadata": {
                k: row[k]
                for k in [
                    "estate",
                    "locality",
                    "territory",
                    "date",
                    "metadata_provenance",
                    "date_provenance",
                ]
            },
            "territorial_context_title_exact": [
                "".join(h.itertext()) for h in first.getparent().findall("head")
            ],
            "boundary_review": row["boundary_review"],
            "uncertainties": row["uncertainties"],
            "legacy_document_id": old_docs.get(row["key"], {}).get("id"),
            "legacy_extent_changed": len(row["divisions"]) > 1 if row["key"] in old_docs else None,
            "method_version": METHOD,
        }
        previous_external = external.get(document["legacy_document_id"])
        document["catalogue_crosschecks"] = (
            [
                {
                    "url": previous_external["persee_url"],
                    "id": previous_external["persee_id"],
                    "provenance": "Correspondance déjà vérifiée dans 1789-sources-comparison/data/documents.json ; aucune nouvelle collecte.",
                    "use": "Contrôle bibliographique secondaire, pas source du texte ni garantie de licence.",
                }
            ]
            if previous_external
            else []
        )
        if row["key"] == "ferrieres":
            document["catalogue_crosschecks"].append(
                {
                    "url": "https://www.persee.fr/doc/arcpa_0000-0000_1879_num_4_1_2175",
                    "id": "arcpa_0000-0000_1879_num_4_1_2175",
                    "provenance": "1789-sources-comparison/data/structure.json : notice unique Ferrières ; pas nouveau téléchargement.",
                    "use": "Corroboration du regroupement, avec vérification XML et scan Stanford.",
                }
            )
        # Couverture explicite : même les lacunes du segmenteur sont conservées dans le parent.
        document["unsegmented_ranges"] = subtract(
            start, end, [(u["start"], u["end"]) for u in doc_units]
        )
        body_roles = {
            "body",
            "supplement_body",
            "supporting_memorandum",
            "preamble",
            "preamble_with_quotation",
            "additional_request",
            "additional_observation",
            "protest_appendix",
            "mandate",
        }
        for block in blocks:
            if block["role"] not in body_roles or block["tag"] != "p":
                continue
            for a, b in subtract(
                block["start"], block["end"], [(u["start"], u["end"]) for u in doc_units] + excluded
            ):
                if not source.text[a:b].strip():
                    continue
                retained.append(
                    {
                        "id": "retained-" + sha(doc_id + str((a, b)))[:20],
                        "document_id": doc_id,
                        "document_key": row["key"],
                        "status": "C",
                        "kind": "unsegmented_source_range_not_an_article",
                        "role": block["role"],
                        "start": a,
                        "end": b,
                        "parent_start": a - start,
                        "parent_end": b - start,
                        "text": source.text[a:b],
                        "xpath": block["xpath"],
                        "reason": "Conservé dans le parent ; pas de limite d’article certifiée, pas de segmentation sémantique.",
                        "source_sha256": source.sha256,
                        "source_revision": REVISION,
                    }
                )
        docs.append(document)
        (ROOT / "data" / "parents").mkdir(parents=True, exist_ok=True)
        (ROOT / "data" / "parents" / (row["key"] + ".txt")).write_text(full)
        scoped = []
        for xp in row["divisions"]:
            node = copy.deepcopy(source.node(xp))
            if row.get("end_at") and xp == row["divisions"][-1]:
                # Retirer les enfants dont le début est après la frontière corrigée.
                for original, copied in zip(source.node(xp), list(node)):
                    if source.span(original)[0] >= end:
                        node.remove(copied)
            scoped.append(ET.tostring(node, encoding="unicode", with_tail=False))
        (ROOT / "data" / "parents" / (row["key"] + ".xml")).write_text(
            "<pilot_document>\n" + "\n".join(scoped) + "\n</pilot_document>\n"
        )
        changed_roles = sum(a["role"] != b["role"] for a, b in zip(raw_blocks, blocks))

        def countable(value):
            return sum(not c.isspace() for c in value)

        metrics["documents"].append(
            {
                "key": row["key"],
                "volume": row["volume"],
                "automatic_parent_matches_reference": parent_match,
                "automatic_parent": auto,
                "reviewed_start": start,
                "reviewed_end": end,
                "parent_correction_required": not parent_match,
                "manual_structure_decisions": len(row["regions"])
                + len(row.get("inline_roles", [])),
                "paragraph_roles_changed": changed_roles,
                "automatic_units_before_review": len(raw),
                "units_after_review": len(doc_units),
                "A": sum(u["status"] == "A" for u in doc_units),
                "B": sum(u["status"] == "B" for u in doc_units),
                "parent_non_whitespace_characters": countable(full),
                "A_non_whitespace_characters": sum(
                    countable(u["text"]) for u in doc_units if u["status"] == "A"
                ),
                "boundaries_uncertain_after_review": False,
                "human_review_seconds": None,
            }
        )
        registers.append(
            {
                k: v
                for k, v in document.items()
                if k not in {"full_text", "blocks", "annotations", "unsegmented_ranges"}
            }
            | {
                "selection_reason": row["selection_reason"],
                "previous_audit": row["previous_audit"],
                "sections": sections,
                "automatic_boundary_matches_review": parent_match,
            }
        )
    totals = Counter()
    for w in metrics["windows"]:
        totals.update({k: v for k, v in w.items() if isinstance(v, int) and k != "window"})
    metrics["aggregate_reviewed_windows"] = dict(totals)
    for kind in ["starts", "ends"]:
        correct = totals[f"correct_{kind}"]
        metrics["aggregate_reviewed_windows"][f"{kind}_precision"] = (
            correct / totals["predicted"] if totals["predicted"] else None
        )
        metrics["aggregate_reviewed_windows"][f"{kind}_recall"] = (
            correct / totals["gold"] if totals["gold"] else None
        )
    metrics["aggregate_reviewed_windows"]["unit_precision"] = (
        totals["correct_units"] / totals["predicted"]
    )
    metrics["aggregate_reviewed_windows"]["unit_recall"] = totals["correct_units"] / totals["gold"]
    metrics["timing"] = {
        "run_started_utc": started,
        "load_parse_offset_seconds": loaded - wall,
        "whole_run_seconds": time.perf_counter() - wall,
        "process_cpu_seconds": time.process_time() - cpu,
        "human_validation_seconds": None,
        "note": "Mesures de la commande uniquement ; revue Codex et mise au point non assimilables à du travail humain chronométré.",
    }
    jlines("documents.jsonl", docs)
    jlines("units.jsonl", units)
    jlines("automatic-predictions.jsonl", predictions)
    jlines("retained-unsegmented.jsonl", retained)
    write("data/reference.json", refs)
    write("data/register.json", registers)
    metrics["timing"]["whole_run_seconds"] = time.perf_counter() - wall
    metrics["timing"]["process_cpu_seconds"] = time.process_time() - cpu
    metrics["timing"]["scope"] = (
        "Chargement, positions, extraction et écritures du corpus ; hors écriture finale des métriques/provenance et hors téléchargement."
    )
    write("data/evaluation.json", metrics)
    write(
        "data/provenance.json",
        {
            "revision": REVISION,
            "method": METHOD,
            "decisions_sha256": sha((ROOT / "decisions.json").read_bytes()),
            "extractor_sha256": sha((ROOT / "extract.py").read_bytes()),
            "common_sha256": sha((ROOT / "common.py").read_bytes()),
            "sources": [
                {
                    "volume": v,
                    "file": s.path.name,
                    "sha256": s.sha256,
                    "decoded_text_sha256": sha(s.text),
                }
                for v, s in sources.items()
            ],
            "parser": {
                "name": "lxml.etree",
                "version": list(ET.LXML_VERSION),
                "load_dtd": False,
                "resolve_entities": False,
                "no_network": True,
                "recover": False,
            },
            "previous_audits_modified": False,
            "application_modified": False,
            "database_access": False,
            "embeddings_generated": False,
        },
    )
    print(f"{len(docs)} parents, {len(units)} unités ; A={sum(u['status'] == 'A' for u in units)}")
    print(metrics["aggregate_reviewed_windows"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sources")
    run(parser.parse_args().sources)
