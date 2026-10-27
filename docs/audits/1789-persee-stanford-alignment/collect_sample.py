"""Récupère uniquement DC pour les 72 notices pré-enregistrées; réutilise les lots OAI."""

import json

from fetch_metadata import CACHE, HERE, NS, get
from lxml import etree


def main():
    cached = {}
    for name in ["documents", "documents-page2"]:
        root = etree.parse(str(CACHE / (name + ".xml")))
        for r in root.findall(".//o:record", NS):
            cached[r.findtext("o:header/o:identifier", namespaces=NS)] = r
    for c in json.loads((HERE / "data/sample.json").read_text()):
        identifier = "oai:persee:article/" + c["id"]
        path = CACHE / (c["id"] + ".xml")
        if path.exists():
            continue
        if identifier in cached:
            path.write_bytes(
                etree.tostring(cached[identifier], encoding="utf-8", xml_declaration=True)
            )
            continue
        try:
            get(c["id"], dict(verb="GetRecord", metadataPrefix="oai_dc", identifier=identifier))
        except Exception as e:
            print("Stopped on access problem", repr(e), flush=True)
            break


if __name__ == "__main__":
    main()
