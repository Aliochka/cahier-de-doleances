#!/usr/bin/env python3
"""Vérifie uniquement les artefacts de cet audit ; aucune connexion base/réseau."""

import argparse
import hashlib
import json
from pathlib import Path

from extract import REVISION, digest, text_positions
from lxml import etree as ET

BASE = Path(__file__).resolve().parent


def read(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path)
    parser.add_argument("--reproduced", type=Path)
    args = parser.parse_args()
    documents = read("data/documents.json")
    passages = read("data/passages.json")
    inventory = read("data/inventory.json")
    assert inventory["revision"] == REVISION and not inventory["xml_errors"]
    assert len(inventory["volumes"]) == 83
    assert len(documents) == 7 and len(passages) == 28
    assert len({p["id"] for p in passages}) == 28
    docs = {d["id"]: d for d in documents}
    selections = {s["key"]: s for s in read("selection.json")}
    previous = {}
    for document in documents:
        assert document["source_revision"] == REVISION
        value = document["full_text_exact"]
        assert digest(value.encode()) == document["full_text_sha256"]
        xml = ET.parse(
            str(BASE / "data/documents" / (document["key"] + ".xml")),
            ET.XMLParser(load_dtd=False, resolve_entities=False, no_network=True),
        )
        assert "".join(xml.getroot().itertext()) == value
        assert (BASE / "data/documents" / (document["key"] + ".txt")).read_text() == value
        for block in document["blocks"]:
            assert block["text_exact"] == value[block["start"] : block["end"]]
        assert document["metadata"] == {
            k: selections[document["key"]][k] for k in document["metadata"]
        }
        if args.source:
            file = args.source / document["source_file"]
            assert digest(file.read_bytes()) == document["source_file_sha256"]
            tree = ET.parse(
                str(file), ET.XMLParser(load_dtd=False, resolve_entities=False, no_network=True)
            )
            (div,) = tree.xpath(document["xpath"])
            assert text_positions(div)[0] == value
    for passage in passages:
        document = docs[passage["document_id"]]
        full = document["full_text_exact"]
        spans = passage["source_spans"]
        assert all(s["text_exact"] == full[s["start"] : s["end"]] for s in spans)
        assert all(a["end"] <= b["start"] for a, b in zip(spans, spans[1:]))
        assert passage["text"] == passage["paragraph_separator"].join(
            s["text_exact"] for s in spans
        )
        assert digest(passage["text"].encode()) == passage["text_sha256"]
        identity = json.dumps(
            [REVISION, document["id"], [(s["start"], s["end"]) for s in spans]],
            separators=(",", ":"),
        )
        assert passage["id"] == "ap1789-exp-v1:" + digest(identity.encode())[:24]
        assert spans[0]["start"] >= previous.get(document["id"], 0)
        previous[document["id"]] = spans[-1]["end"]
        assert passage["context_reference"]["start"] == spans[0]["start"]
        assert passage["context_reference"]["end"] == spans[-1]["end"]
        assert all(
            s["page"] and s["page"]["canvas_url"] and s["page"]["image_service"] for s in spans
        )
    pages = read("data/source-pages.json")
    assert len(pages) == 6
    assert all(p["license"] is None for p in pages.values())
    # Le rôle des dates fait partie des garanties documentaires de l'échantillon.
    colmar = next(d for d in documents if d["key"] == "colmar-ville")
    assert colmar["metadata"]["date"] == "1789-03-24"
    assert colmar["date_elements"][0]["attributes"]["value"] == "1789-04-27"
    assert len(read("data/problematic/cases.json")) == 6
    if args.source:
        for case in read("data/problematic/cases.json"):
            file = args.source / case["druid"] / (case["druid"] + ".xml")
            tree = ET.parse(
                str(file), ET.XMLParser(load_dtd=False, resolve_entities=False, no_network=True)
            )
            (div,) = tree.xpath(case["xpath"])
            assert case["text_exact"] == "".join(div.itertext())
        for volume in inventory["volumes"]:
            assert digest((args.source / volume["file"]).read_bytes()) == volume["sha256"]
        tree = read("source-tree.json")
        assert tree["sha"] == REVISION and not tree["truncated"]
        blobs = [x for x in tree["tree"] if x["type"] == "blob"]
        assert len(blobs) == 88
        for blob in blobs:
            value = (args.source / blob["path"]).read_bytes()
            assert (
                hashlib.sha1(b"blob " + str(len(value)).encode() + b"\0" + value).hexdigest()
                == blob["sha"]
            )
    if args.reproduced:
        for name in [
            "inventory.json",
            "divisions.json",
            "screening.json",
            "documents.json",
            "passages.json",
            "source-pages.json",
        ]:
            assert (args.reproduced / name).read_bytes() == (BASE / "data" / name).read_bytes(), (
                name
            )
    print(
        "OK : 83 XML inventoriés ; 7 parents complets ; 28 passages uniques ; caractères, offsets, identifiants, métadonnées et liens IIIF cohérents."
    )
    if args.source:
        print(
            "OK : textes vérifiés contre les XML source et les 88 empreintes Git du snapshot figé."
        )
    if args.reproduced:
        print("OK : reproduction identique octet pour octet des six sorties JSON calculées.")


if __name__ == "__main__":
    main()
