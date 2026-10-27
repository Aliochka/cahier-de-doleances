"""Client OAI limité: métadonnées uniquement, cache, journal, une requête à la fois."""

import datetime
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
LOG = HERE / "data/access-log.json"
NS = {
    "o": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dct": "http://purl.org/dc/terms/",
    "mets": "http://www.loc.gov/METS/",
}


def get(label, params):
    assert params.get("metadataPrefix") in {None, "oai_dc", "mods", "persee_mets"}
    assert params.get("verb") in {"ListRecords", "GetRecord", "Identify", "ListMetadataFormats"}
    path = CACHE / (label + ".xml")
    if path.exists():
        return etree.fromstring(path.read_bytes())
    url = "https://oai.persee.fr/oai?" + urllib.parse.urlencode(params)
    log = json.loads(LOG.read_text())
    entry = dict(
        label=label, url=url, started_at=datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    start = time.monotonic()
    time.sleep(1.2)
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "CahierDeDoleances-DocumentaryAudit/1.0 (limited public metadata feasibility study)",
                "Accept": "application/xml,text/xml",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read(4 * 1024 * 1024 + 1)
            assert len(data) <= 4 * 1024 * 1024
            root = etree.fromstring(
                data, parser=etree.XMLParser(resolve_entities=False, no_network=True)
            )
            assert root.tag == "{http://www.openarchives.org/OAI/2.0/}OAI-PMH"
            assert not root.xpath('//*[namespace-uri()="http://www.tei-c.org/ns/1.0"]')
            entry.update(
                status=resp.status,
                final_url=resp.url,
                headers=dict(resp.headers),
                bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest(),
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
        entry["seconds"] = time.monotonic() - start
        log.append(entry)
        LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n")
    print(label, entry.get("status"), entry.get("bytes"), flush=True)
    return root


def main():
    for name in ["documents", "volumes"]:
        root = etree.parse(str(CACHE / (name + ".xml"))).getroot()
        token = root.find(".//o:resumptionToken", NS)
        assert token is not None and token.text
        get(name + "-page2", {"verb": "ListRecords", "resumptionToken": token.text})
    for v in range(1, 7):
        get(
            f"mets-v{v}",
            dict(
                verb="GetRecord",
                metadataPrefix="persee_mets",
                identifier=f"oai:persee:issue/arcpa_0000-0000_1879_num_{v}_1",
            ),
        )


if __name__ == "__main__":
    main()
