# ruff: noqa: E402
"""Primitives expérimentales : aucun import applicatif, aucune connexion réseau/SQL."""

import sys as _workspace_sys
from pathlib import Path as _WorkspacePath
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2]))
from cahier1789_paths import resolve_reference  # noqa: E402

import hashlib
import json
from pathlib import Path

from lxml import etree as ET

ROOT = Path(__file__).resolve().parent
REVISION = "926fd3cd986a3c3d411e93d1845fff6475cb2602"
METHOD = "pilot-1.0.0"
CORPUS = "cahiers-1789-ap-stanford"


def read(name):
    return json.loads((ROOT / name).read_text())


def write(name, value):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def compact(node):
    """Affichage d'inspection seulement, jamais utilisé pour les textes extraits."""
    return " ".join("".join(node.itertext()).split())


class Source:
    def __init__(self, path):
        path = resolve_reference(path)
        self.path = Path(path)
        self.sha256 = sha(self.path.read_bytes())
        self.tree = ET.parse(
            str(path),
            ET.XMLParser(load_dtd=False, resolve_entities=False, no_network=True, recover=False),
        )
        self.ranges = {}
        chunks = []
        cursor = 0

        def visit(node):
            nonlocal cursor
            start = cursor
            if node.text:
                chunks.append(node.text)
                cursor += len(node.text)
            for child in node:
                if isinstance(child.tag, str):
                    visit(child)
                if child.tail:
                    chunks.append(child.tail)
                    cursor += len(child.tail)
            self.ranges[self.tree.getpath(node)] = [start, cursor]

        visit(self.tree.getroot())
        self.text = "".join(chunks)
        self.pages = [(self.span(n)[0], dict(n.attrib)) for n in self.tree.xpath("//pb")]

    def node(self, xpath):
        return self.tree.xpath(xpath)[0]

    def span(self, node):
        return self.ranges[self.tree.getpath(node)]

    def page_at(self, position):
        preceding = [p for offset, p in self.pages if offset <= position]
        return preceding[-1] if preceding else None

    def pages_for(self, start, end):
        result = [self.page_at(start)]
        result += [p for offset, p in self.pages if start < offset < end]
        return [p for i, p in enumerate(result) if p and p not in result[:i]]


def load_sources(directory):
    result = {}
    for row in read("../1789-multicorpus/data/inventory.json")["volumes"][:6]:
        s = Source(Path(directory) / (row["druid"] + ".xml"))
        assert s.sha256 == row["sha256"], row["druid"]
        result[int(row["volume"])] = s
    return result
