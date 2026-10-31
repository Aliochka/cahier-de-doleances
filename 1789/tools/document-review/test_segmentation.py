"""Synthetic source fixtures; no journal or original source is written."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from lxml import etree
from reviewlib import Store
from segmentation import run


class SyntheticSource:
    def __init__(self, texts):
        self.text = "\n".join(texts)
        self.tree = etree.ElementTree(etree.Element("div3"))
        self.bounds = {}
        self.blocks = []
        pos = 0
        for text in texts:
            node = etree.SubElement(self.tree.getroot(), "p")
            node.text = text
            path = self.tree.getpath(node)
            self.bounds[path] = (pos, pos + len(text))
            self.blocks.append(
                dict(
                    xpath=path,
                    start=pos,
                    end=pos + len(text),
                    tag="p",
                    role="body",
                    division="/div3",
                )
            )
            pos += len(text) + 1

    def node(self, path):
        return self.tree.xpath(path)[0]

    def span(self, node):
        return self.bounds[self.tree.getpath(node)]


class SegmentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Resolves the original, unmodified V2 imports once.
        cls.tmp = tempfile.TemporaryDirectory()
        cls.store = Store(Path(cls.tmp.name) / "unused.jsonl")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def result(self, texts):
        source = SyntheticSource(texts)
        parent = dict(
            volume=1,
            start=0,
            end=len(source.text),
            blocks=source.blocks,
            annotations=[],
            extent_id="SYNTHETIC",
        )
        return run(SimpleNamespace(sources={1: source}), parent)

    def test_glued_bare_number(self):
        r = self.result(
            [
                "10° Nous demandons justice.",
                "11Nous demandons moins de frais.",
                "12° Nous demandons la liberté.",
            ]
        )
        self.assertTrue(
            any(c["raw_number"] == "11" and c["confidence"] == "proposed" for c in r["candidates"])
        )

    def test_ocr_letters_need_neighbours(self):
        r = self.result(
            [
                "10° Que justice soit rendue.",
                "llQue les frais diminuent.",
                "12° Que tous contribuent.",
            ]
        )
        c = next(c for c in r["candidates"] if c["raw_number"] == "ll")
        self.assertEqual(c["confidence"], "proposed")
        self.assertIsNone(c["historical_number"])

    def test_pronoun_not_number(self):
        r = self.result(
            [
                "Art. 10. Que justice soit rendue.",
                "Il sera permis de se réunir.",
                "Art. 12. Que tous contribuent.",
            ]
        )
        self.assertFalse(any(c["confidence"] == "proposed" for c in r["candidates"]))

    def test_amount_date_reference_and_sublist(self):
        r = self.result(
            [
                "Art. 1. Que la loi demeure.",
                "11 livres seront versées.",
                "12 mars 1789.",
                "Art. 11 du code demeure.",
                "1° Que soient lus les comptes.",
                "2° Que soit lu le budget.",
                "Art. 2. Que tous contribuent.",
            ]
        )
        self.assertFalse(any(c["confidence"] == "proposed" for c in r["candidates"]))

    def test_inline_explicit_articles(self):
        r = self.result(
            [
                "Art. 1. Que la loi demeure. Art. 2Que chacun soit libre. Art. 3. Que tous contribuent."
            ]
        )
        self.assertEqual(len(r["new"]), 3)

    def test_ambiguous_number_only_flagged(self):
        r = self.result(["10° Que justice soit rendue.", "ll* Que les frais diminuent."])
        self.assertTrue(
            any(c["raw_number"] == "ll" and c["confidence"] == "suspect" for c in r["candidates"])
        )

    def test_exact_source_text(self):
        texts = [
            "10° Que justice soit rendue.",
            "11Nous demandons moins de frais.",
            "12° Que tous contribuent.",
        ]
        r = self.result(texts)
        source = "\n".join(texts)
        for u in r["new"]:
            self.assertEqual(u["text"], "".join(source[a:z] for a, z in u["spans"]))

    def test_marker_heading_restored(self):
        source = SyntheticSource(
            [
                "Art. 5. Que justice soit rendue.",
                "ART. 6.",
                "Que la liberté demeure.",
                "Art. 7. Que tous contribuent.",
            ]
        )
        source.blocks[1]["role"] = "section_heading"
        parent = dict(
            volume=1,
            start=0,
            end=len(source.text),
            blocks=source.blocks,
            annotations=[],
            extent_id="SYNTHETIC",
        )
        r = run(SimpleNamespace(sources={1: source}), parent)
        self.assertEqual(len(r["new"]), 3)
        self.assertIn("Que la liberté demeure.", r["new"][1]["text"])

    def test_ambiguous_inline_ocr_is_only_a_review_proposal(self):
        r = self.result(
            ["10° Que justice soit rendue; ll* Que les frais diminuent; 12° Que tous contribuent."]
        )
        suspect = next(c for c in r["candidates"] if c["raw_number"] == "ll")
        self.assertEqual(suspect["confidence"], "suspect")
        self.assertTrue(suspect["inline"])
