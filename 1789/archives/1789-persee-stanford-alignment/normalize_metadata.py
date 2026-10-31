"""Normalise les champs, sans transformer une date d’édition en date de rédaction."""

import collections
import re

from auditlib import HERE, jlines, read, save, sha
from fetch_metadata import CACHE, NS
from lxml import etree


def main():
    records = []
    for item in read(HERE / "data/sample.json"):
        path = CACHE / (item["id"] + ".xml")
        if not path.exists():
            records.append(dict(item, access_status="missing"))
            continue
        root = etree.parse(str(path))
        record = (
            root.getroot()
            if root.getroot().tag.endswith("}record")
            else root.find(".//o:record", NS)
        )
        if record is None:
            records.append(dict(item, access_status="oai_error"))
            continue
        fields = collections.defaultdict(list)
        for n in record.findall("o:metadata/*/*", NS):
            fields[etree.QName(n).localname].append(n.text or "")
        coverage = fields.get("coverage", [])
        m = re.search(r"(\d+)\s*[-–]\s*(\d+)", coverage[0] if coverage else "")
        if m:
            a, b = int(m[1]), int(m[2])
        else:
            n = re.search(r"\d+", coverage[0] if coverage else "")
            a = b = int(n[0]) if n else None
        title = fields.get("title", [item["title"]])[0]
        identifier = record.findtext("o:header/o:identifier", namespaces=NS)
        records.append(
            dict(
                item,
                title=title,
                oai_identifier=identifier,
                datestamp=record.findtext("o:header/o:datestamp", namespaces=NS),
                set_specs=record.xpath("o:header/o:setSpec/text()", namespaces=NS),
                dc_type=fields.get("type"),
                date_edition=fields.get("date"),
                date_historical=None,
                page_start=a,
                page_end=b,
                urls=fields.get("identifier"),
                is_part_of=fields.get("isPartOf"),
                bibliographic_citation=fields.get("bibliographicCitation"),
                rights=fields.get("rights"),
                access_rights=fields.get("accessRights"),
                language=fields.get("language"),
                raw_fields=dict(fields),
                metadata_sha256=sha(path.read_bytes()),
                access_status="obtained",
            )
        )
    jlines(HERE / "data/metadata.jsonl", records)
    summary = dict(
        records=len(records),
        access_status=dict(collections.Counter(r["access_status"] for r in records)),
        type_distribution=dict(
            collections.Counter((r.get("dc_type") or ["missing"])[0] for r in records)
        ),
        missing_pagination=sum(r.get("page_start") is None for r in records),
        missing_titles=sum(not r.get("title") for r in records),
        edition_years=dict(
            collections.Counter(x for r in records for x in (r.get("date_edition") or []))
        ),
    )
    pagination = []
    for name in ["volumes", "documents"]:
        original = etree.parse(str(CACHE / (name + ".xml")))
        follow = etree.parse(str(CACHE / (name + "-page2.xml")))

        def ids(t):
            return t.xpath("//o:record/o:header/o:identifier/text()", namespaces=NS)

        a, b = ids(original), ids(follow)
        token = follow.find(".//o:resumptionToken", NS)
        pagination.append(
            dict(
                set=name,
                page1_records=len(a),
                page2_records=len(b),
                overlap=sorted(set(a) & set(b)),
                page2_cursor=token.get("cursor") if token is not None else None,
                next_token_present=bool(token is not None and token.text),
                continued_with_only_verb_and_token=True,
                stopped_deliberately=True,
            )
        )
    save(HERE / "data/metadata-summary.json", summary)
    save(HERE / "data/pagination-check.json", pagination)
    print(summary)


if __name__ == "__main__":
    main()
