#!/usr/bin/env python3
"""Audit hors application. Lecture locale du snapshot, aucune base ni réseau.
Usage: python extract.py /tmp/cahier-audit-1789/ap_tei-master --output /tmp/audit-output
Dépendance de l'environnement d'audit : lxml (aucune dépendance applicative ajoutée).
"""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from lxml import etree as ET

REVISION = "926fd3cd986a3c3d411e93d1845fff6475cb2602"
PARSER = ET.XMLParser(load_dtd=False, resolve_entities=False, no_network=True)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def compact(element):
    return " ".join("".join(element.itertext()).split())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inventory(source, out):
    mapping = {
        r["druid"]: r["volume"]
        for r in csv.DictReader((source / "vol-to-druid.csv").open(newline=""))
    }
    volumes, divisions, errors = [], [], []
    screening, duplicates = [], defaultdict(list)
    for file in sorted(source.glob("*/*.xml")):
        try:
            tree = ET.parse(str(file), PARSER)
        except ET.XMLSyntaxError as exc:
            errors.append({"file": str(file.relative_to(source)), "error": str(exc)})
            continue
        druid, volume = file.stem, mapping[file.stem]
        elements = Counter(e.tag for e in tree.iter() if isinstance(e.tag, str))
        rows = []
        for div in tree.xpath("//body//div3"):
            title = " ".join(compact(h) for h in div.findall("head"))
            opening = [compact(p) for p in div.findall("p")[:3]]
            row = dict(
                volume=volume,
                druid=druid,
                xpath=tree.getpath(div),
                type=div.get("type"),
                head=title,
                opening=opening,
                characters=len("".join(div.itertext())),
                paragraphs=len(div.findall("p")),
                items=len(div.findall(".//item")),
                cahier_word_in_head=bool(re.search(r"cahier|dol[ée]ance", title, re.I)),
                starts_cahier=bool(re.match(r"^CAHIER\b", title, re.I)),
            )
            rows.append(row)
        divisions.extend(rows)
        if volume in ("1", "2", "3", "4", "5", "6"):
            missing, markers, count = [], 0, 0
            for div, row in zip(tree.xpath("//body//div3"), rows):
                if not row["starts_cahier"]:
                    continue
                count += 1
                texts = [compact(p) for p in div.findall("p")]
                body = " ".join(texts)
                if len(body) < 1100 and re.search(
                    r"NOTA|manque|impossible|n.existe|ne se trouve|recherch", body, re.I
                ):
                    missing.append(
                        dict(volume=volume, xpath=row["xpath"], head=row["head"], body=body)
                    )
                duplicates[digest(compact(div).encode())].append(
                    dict(volume=volume, xpath=row["xpath"])
                )
                markers += sum(
                    bool(re.match(r"^(?:Article|Art)[.,]?\s*\d", p, re.I)) for p in texts
                )
            screening.append(
                dict(
                    volume=volume,
                    starts_cahier=count,
                    short_absence_notice_candidates=len(missing),
                    article_start_paragraphs_in_starts_cahier=markers,
                    absence_notices=missing,
                )
            )
        volumes.append(
            dict(
                volume=volume,
                druid=druid,
                file=str(file.relative_to(source)),
                sha256=digest(file.read_bytes()),
                bytes=file.stat().st_size,
                header_id=tree.find("teiHeader").get("id"),
                publication_dates=[
                    compact(x) for x in tree.findall("teiHeader/fileDesc/publicationStmt/date")
                ],
                elements=dict(elements),
                body_div3=len(rows),
                cahier_word_in_div3_heads=sum(x["cahier_word_in_head"] for x in rows),
                starts_cahier_div3=sum(x["starts_cahier"] for x in rows),
            )
        )
    volumes.sort(key=lambda v: (int(re.sub("[AB]", "", v["volume"])), v["volume"]))
    write(out / "inventory.json", dict(revision=REVISION, volumes=volumes, xml_errors=errors))
    write(out / "divisions.json", divisions)
    write(
        out / "screening.json",
        dict(
            method="Head starts CAHIER singular; absence notices: body length<1100 plus keywords. Not a document census. Duplicates: whitespace-folded division text.",
            volumes=sorted(screening, key=lambda x: int(x["volume"])),
            identical_division_groups=[v for v in duplicates.values() if len(v) > 1],
        ),
    )
    return volumes, divisions


def text_positions(root):
    """Offsets en points de code dans itertext(), sans trim ni normalisation."""
    parts, spans, position = [], {}, 0

    def append(value):
        nonlocal position
        if value:
            parts.append(value)
            position += len(value)

    def visit(element):
        start = position
        append(element.text)
        for child in element:
            if isinstance(child.tag, str):
                visit(child)
            append(child.tail)
        spans[element] = (start, position)

    visit(root)
    value = "".join(parts)
    assert value == "".join(root.itertext())
    return value, spans


def extract_samples(source, out, evidence):
    selection = json.loads(Path(__file__).with_name("selection.json").read_text())
    passages, documents, source_pages = [], [], {}
    for item in selection:
        druid = item["druid"]
        file = source / druid / (druid + ".xml")
        tree = ET.parse(str(file), PARSER)
        (div,) = tree.xpath(item["xpath"])
        full_text, spans = text_positions(div)
        document_id = "ap1789-exp-v1:" + druid + ":" + digest(item["xpath"].encode())[:16]
        last_page, pages_at_node = None, {}
        for element in tree.iter():
            if element.tag == "pb":
                last_page = dict(id=element.get("id"), printed_label=element.get("n"))
            pages_at_node[element] = last_page

        manifest_path = evidence / (druid + ".manifest.json") if evidence else None
        manifest = (
            json.loads(manifest_path.read_text())
            if manifest_path and manifest_path.exists()
            else None
        )
        canvas_by_pb = {}
        if manifest:
            for canvas in manifest["sequences"][0]["canvases"]:
                for rendering in canvas.get("rendering", []):
                    pb_id = rendering["@id"].split("/")[-1].removesuffix(".jp2")
                    canvas_by_pb[pb_id] = dict(
                        canvas_url=canvas["@id"],
                        canvas_label=canvas["label"],
                        image_service=canvas["images"][0]["resource"]["service"]["@id"],
                    )
            source_pages[druid] = dict(
                manifest_url=manifest["@id"],
                manifest_sha256=digest(manifest_path.read_bytes()),
                attribution=manifest.get("attribution"),
                license=manifest.get("license"),
                pages={},
            )

        def page_for(element):
            page = pages_at_node[element]
            if page is None:
                return None
            result = page | canvas_by_pb.get(page["id"], {})
            if manifest:
                source_pages[druid]["pages"][page["id"]] = result
            return result

        title_elements = div.findall("head") + [
            div.findall("p")[n - 1] for n in item["title_paragraphs"]
        ]
        title_parts = ["".join(e.itertext()) for e in title_elements]
        blocks = [
            dict(
                xpath=tree.getpath(e),
                kind=e.tag,
                start=spans[e][0],
                end=spans[e][1],
                text_exact=full_text[slice(*spans[e])],
                page=page_for(e),
            )
            for e in div
            if isinstance(e.tag, str)
        ]
        doc = dict(
            id=document_id,
            key=item["key"],
            corpus_id="cahiers-1789-ap-stanford",
            source_revision=REVISION,
            source_file=f"{druid}/{druid}.xml",
            source_file_sha256=digest(file.read_bytes()),
            xpath=item["xpath"],
            source_url=f"https://github.com/StanfordUniversityLibraries/ap_tei/blob/{REVISION}/{druid}/{druid}.xml",
            scan_url=f"https://purl.stanford.edu/{druid}",
            volume=item["volume"],
            bibliography=dict(
                collection="Archives parlementaires",
                volume=item["volume"],
                publication_dates=[
                    compact(e) for e in tree.findall("teiHeader/fileDesc/publicationStmt/date")
                ],
                publication_places=[
                    compact(e) for e in tree.findall("teiHeader/fileDesc/publicationStmt/pubPlace")
                ],
                editors_exact=[
                    "".join(e.itertext())
                    for e in tree.findall("teiHeader/fileDesc/titleStmt/author")
                ],
                note_references=[
                    dict(xpath=tree.getpath(e), text_exact="".join(e.itertext()))
                    for e in div.iter("note")
                ],
                provenance="Edition metadata from the TEI volume header; notes may cite historical manuscript repositories without a modern archival identifier.",
            ),
            title=" ".join(" ".join(t.split()) for t in title_parts),
            title_parts_exact=title_parts,
            metadata={
                k: item[k]
                for k in [
                    "locality",
                    "territory",
                    "estate",
                    "date",
                    "date_provenance",
                    "metadata_provenance",
                ]
            },
            date_elements=[
                dict(
                    xpath=tree.getpath(e),
                    attributes=dict(e.attrib),
                    text_exact="".join(e.itertext()),
                )
                for e in div.iter("date")
            ],
            full_text_exact=full_text,
            full_text_sha256=digest(full_text.encode()),
            blocks=blocks,
            completeness="Whole selected TEI division, including notes and signatures; not a manuscript completeness certification.",
        )
        documents.append(doc)
        xml_path = out / "documents" / (item["key"] + ".xml")
        xml_path.parent.mkdir(exist_ok=True)
        xml_path.write_bytes(
            ET.tostring(div, encoding="utf-8", xml_declaration=True, with_tail=False)
        )
        (out / "documents" / (item["key"] + ".txt")).write_text(full_text, encoding="utf-8")

        for number, spec in enumerate(item["passages"], 1):
            source_spans = []
            for n in range(spec["from"], spec["to"] + 1):
                p = div.findall("p")[n - 1]
                start, end = spans[p]
                value = full_text[start:end]
                if spec.get("split_start"):
                    start += value.index(spec["split_start"])
                if spec.get("split_end"):
                    end = spans[p][0] + value.index(spec["split_end"])
                source_spans.append(
                    dict(
                        xpath=tree.getpath(p),
                        start=start,
                        end=end,
                        text_exact=full_text[start:end],
                        page=page_for(p),
                    )
                )
            assert spec["label"] in " ".join(source_spans[0]["text_exact"].split()), spec
            identity = json.dumps(
                [REVISION, document_id, [(s["start"], s["end"]) for s in source_spans]],
                separators=(",", ":"),
            )
            passage = dict(
                id="ap1789-exp-v1:" + digest(identity.encode())[:24],
                document_id=document_id,
                document_title=doc["title"],
                sample_ordinal=number,
                source_paragraphs=[spec["from"], spec["to"]],
                original_label=spec["label"],
                extraction_class="B",
                method="Explicit numbering, paragraph ranges reviewed in selection.json; no semantic splitting.",
                text="\n\n".join(s["text_exact"] for s in source_spans),
                paragraph_separator="\n\n",
                source_spans=source_spans,
                metadata=doc["metadata"],
                volume=item["volume"],
                source_url=doc["source_url"],
                scan_url=doc["scan_url"],
                context_reference=dict(
                    document_id=document_id,
                    start=source_spans[0]["start"],
                    end=source_spans[-1]["end"],
                ),
                uncertainties=([spec["warning"]] if spec.get("warning") else [])
                + [
                    "Exact Stanford transcription, not a corrected or modernized manuscript transcription."
                ],
            )
            passage["text_sha256"] = digest(passage["text"].encode())
            passages.append(passage)
    assert len(passages) == 28 and len(documents) == 7
    write(out / "documents.json", documents)
    write(out / "passages.json", passages)
    write(out / "source-pages.json", source_pages)
    print("Extraction:", len(documents), "documents,", len(passages), "passages")


def main():
    args = argparse.ArgumentParser()
    args.add_argument("source", type=Path)
    args.add_argument("--output", type=Path, required=True)
    args.add_argument("--evidence", type=Path)
    opts = args.parse_args()
    opts.output.mkdir(parents=True, exist_ok=True)
    volumes, divisions = inventory(opts.source, opts.output)
    for row in volumes:
        print(
            row["volume"],
            row["druid"],
            row["body_div3"],
            row["cahier_word_in_div3_heads"],
            row["starts_cahier_div3"],
        )
    extract_samples(opts.source, opts.output, opts.evidence)


if __name__ == "__main__":
    main()
