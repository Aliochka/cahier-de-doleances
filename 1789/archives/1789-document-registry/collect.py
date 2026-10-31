"""Métadonnées publiques des 1305 identifiants METS seulement; aucun texte Persée."""

import datetime
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from lxml import etree

from lib import ALIGN, CACHE, HERE, NS, ROOT, jlines, read, save, sha

PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)


def records(data):
    root = etree.fromstring(data, parser=PARSER)
    assert not root.xpath('//*[namespace-uri()="http://www.tei-c.org/ns/1.0"]')
    return [root] if root.tag.endswith("}record") else root.findall(".//o:record", NS)


def fields(record):
    out = {}
    for n in record.findall("o:metadata/*/*", NS):
        out.setdefault(etree.QName(n).localname, []).append(n.text or "")
    return out


def request(label, params):
    assert params.get("metadataPrefix") in {None, "oai_dc"}
    path = CACHE / (label + ".xml")
    if path.exists():
        return path.read_bytes()
    url = "https://oai.persee.fr/oai?" + urllib.parse.urlencode(params)
    log = read(HERE / "data/access-log.json") if (HERE / "data/access-log.json").exists() else []
    entry = dict(
        label=label, url=url, date=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    clock = time.monotonic()
    time.sleep(1.2)
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "CahierDeDoleances-RegistryAudit/1.0 (public OAI metadata only; six issue catalogues)",
                "Accept": "application/xml,text/xml",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read(4 * 1024 * 1024 + 1)
            assert len(data) <= 4 * 1024 * 1024
            rs = records(data)
            root = etree.fromstring(data, parser=PARSER)
            entry.update(
                status=resp.status,
                bytes=len(data),
                sha256=sha(data),
                records=len(rs),
                oai_errors=[
                    dict(code=e.get("code"), text=e.text) for e in root.findall("o:error", NS)
                ],
            )
            path.write_bytes(data)
    except urllib.error.HTTPError as e:
        entry.update(status=e.code, error=str(e), retry_after=e.headers.get("Retry-After"))
        raise
    except Exception as e:
        entry.update(error_type=type(e).__name__, error=str(e))
        raise
    finally:
        entry["seconds"] = time.monotonic() - clock
        log.append(entry)
        save(HERE / "data/access-log.json", log)
    return data


def main():
    if not (HERE / "prior-audits-sha256.json").exists():
        save(
            HERE / "prior-audits-sha256.json",
            {
                str(p.relative_to(ROOT)): sha(p.read_bytes())
                for p in (HERE.parent).rglob("*")
                if p.is_file()
                and HERE not in p.parents
                and ".cache" not in p.parts
                and "__pycache__" not in p.parts
            },
        )
    catalogue = []
    for v in range(1, 7):
        path = ALIGN / ".cache" / f"mets-v{v}.xml"
        tree = etree.parse(str(path), parser=PARSER)
        for index, n in enumerate(tree.findall(".//mets:structMap//mets:div", NS)):
            if n.get("TYPE") != "griev":
                continue
            pid = n.get("ID", "").removeprefix("TdM_")
            assert f"_num_{v}_1_" in pid
            catalogue.append(
                dict(
                    id=pid,
                    volume=v,
                    title=n.get("LABEL"),
                    mets_type=n.get("TYPE"),
                    catalogue_order=index,
                    local_order=n.get("ORDER"),
                    ancestors=[
                        a.get("LABEL")
                        for a in n.iterancestors()
                        if a.tag == "{http://www.loc.gov/METS/}div"
                    ],
                    mets_sha256=sha(path.read_bytes()),
                    mets_xpath=tree.getpath(n),
                    document_url="https://www.persee.fr/doc/" + pid,
                )
            )
    assert len(catalogue) == 1305 and len({r["id"] for r in catalogue}) == 1305
    jlines(HERE / "data/catalogue.jsonl", catalogue)
    target = {r["id"] for r in catalogue}
    found = {}
    origins = {}

    def ingest(data, origin):
        for record in records(data):
            oid = record.findtext("o:header/o:identifier", namespaces=NS) or ""
            pid = oid.rsplit("/", 1)[-1]
            if pid in target:
                found[pid] = etree.tostring(record, encoding="utf-8")
                origins[pid] = origin

    for path in sorted((ALIGN / ".cache").glob("*.xml")):
        if path.name.startswith("arcpa_") or path.name in {"documents.xml", "documents-page2.xml"}:
            ingest(path.read_bytes(), str(path.relative_to(ROOT)))
    initial = len(found)
    print("Reused", initial, "DC notices;", len(catalogue), "catalogue entries", flush=True)
    # Follow existing opaque tokens, stopping at the target set or the first later-volume stretch.
    last = (ALIGN / ".cache/documents-page2.xml").read_bytes()
    outside_streak = 0
    for page in range(3, 103):
        root = etree.fromstring(last, parser=PARSER)
        token = root.find(".//o:resumptionToken", NS)
        if token is None or not token.text or len(found) == len(target):
            break
        last = request(
            f"list-documents-{page:03}", dict(verb="ListRecords", resumptionToken=token.text)
        )
        rr = records(last)
        ingest(last, f".cache/list-documents-{page:03}.xml")
        if etree.fromstring(last, parser=PARSER).find("o:error", NS) is not None:
            print("OAI error; stop pagination and use targeted metadata only", flush=True)
            break
        matched = sum(
            (r.findtext("o:header/o:identifier", namespaces=NS) or "").rsplit("/", 1)[-1] in target
            for r in rr
        )
        outside_streak = outside_streak + 1 if matched == 0 else 0
        if page % 10 == 0:
            print("metadata page", page, "target", len(found), "/1305", flush=True)
        if outside_streak >= 5:
            break
    for i, pid in enumerate(sorted(target - set(found)), 1):
        data = request(
            pid,
            dict(verb="GetRecord", metadataPrefix="oai_dc", identifier="oai:persee:article/" + pid),
        )
        ingest(data, ".cache/" + pid + ".xml")
        if i % 50 == 0:
            print("targeted metadata", i, "total", len(found), "/1305", flush=True)
    out = []
    for c in catalogue:
        pid = c["id"]
        raw = found.get(pid)
        if raw is None:
            out.append(dict(c, metadata_status="not_available"))
            continue
        root = etree.fromstring(raw, parser=PARSER)
        f = fields(root)
        coverage = f.get("coverage", [""])[0]
        mm = re.search(r"(\d+)\s*[-–]\s*(\d+)", coverage)
        if mm:
            a, b = int(mm[1]), int(mm[2])
        else:
            m = re.search(r"\d+", coverage)
            a = b = int(m[0]) if m else None
        actual_title = f.get("title", [c["title"]])[0]
        out.append(
            dict(
                c,
                title=actual_title,
                mets_title=c["title"],
                raw_fields=f,
                page_start=a,
                page_end=b,
                dc_type=f.get("type"),
                date_edition=f.get("date"),
                historical_date=None,
                bibliographic_citation=f.get("bibliographicCitation") or f.get("description"),
                metadata_status="available",
                oai_identifier=root.findtext("o:header/o:identifier", namespaces=NS),
                datestamp=root.findtext("o:header/o:datestamp", namespaces=NS),
                metadata_record_sha256=sha(raw),
                metadata_origin=origins[pid],
                anomalies=(
                    ["METS_DC_title_difference"]
                    if actual_title.strip() != c["title"].strip()
                    else []
                )
                + (["METS_DC_type_difference"] if f.get("type") != ["griev"] else [])
                + (["missing_pagination"] if a is None else []),
            )
        )
        (CACHE / (pid + "-record.xml")).write_bytes(raw)
    jlines(HERE / "data/metadata.jsonl", out)
    save(
        HERE / "data/collection-summary.json",
        dict(
            catalogue=1305,
            reused_dc=initial,
            obtained=len(found),
            missing=len(target - set(found)),
            target_only=True,
            requests=len(read(HERE / "data/access-log.json"))
            if (HERE / "data/access-log.json").exists()
            else 0,
        ),
    )
    print("Done metadata", len(found), flush=True)


if __name__ == "__main__":
    main()
