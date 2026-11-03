"""Synthetic structure, exact coverage and negative controls; no human log writes."""

import copy
import re
import unittest
from types import SimpleNamespace

from articles import subtract
from test_segmentation import SyntheticSource
from thematic import apply, context, new_record, regions, title

BODY = (
    "Les habitants demandent la suppression des privilèges et une répartition plus juste des charges publiques. "
    "Ils désirent que les droits de chacun soient garantis par des règles claires, communes et effectivement observées."
)


class ThematicTests(unittest.TestCase):
    def fixture(self, texts, numbered=False):
        src = SyntheticSource(texts)
        parent = dict(
            id="test",
            volume=1,
            start=0,
            end=len(src.text),
            extent_id="test-extent",
            blocks=src.blocks,
            annotations=[],
        )
        store = SimpleNamespace(sources={1: src})
        records = []
        if numbered:
            for b, text in zip(src.blocks, texts):
                m = re.match(r"Art\. (\d+)\.", text)
                if m:
                    r = new_record(parent, "article", [[b["start"], b["end"]]], ["initial"])
                    r["number"] = m[1]
                    records.append(r)
        for span in subtract([[0, len(src.text)]], [span for r in records for span in r["spans"]]):
            records.append(new_record(parent, "technical_passage", [span], ["initial"]))
        return store, parent, records

    def partition(self, store, parent, records):
        spans = sorted(s for r in records for s in r["spans"])
        self.assertEqual(spans[0][0], 0)
        self.assertEqual(spans[-1][1], parent["end"])
        self.assertTrue(all(a[1] == b[0] for a, b in zip(spans, spans[1:])))
        self.assertEqual(
            "".join(store.sources[1].text[a:z] for a, z in spans), store.sources[1].text
        )

    def test_title_and_multiple_paragraphs_form_one_unnumbered_claim(self):
        store, p, rs = self.fixture(
            [
                "Jurandes et maîtrises.",
                BODY,
                "Toutes les corporations désirent une réforme.",
                "Commerce.",
                BODY,
                "Agriculture.",
                BODY,
                "Signé Dupont.",
            ]
        )
        hs = regions(store, p, rs)
        out, changes = apply(store, p, rs, hs)
        first = next(r for r in out if r["type"] == "article" and r["spans"][0][0] == 0)
        self.assertIsNone(first["number"])
        self.assertEqual(first["spans"][-1][1], store.sources[1].blocks[3]["start"])
        self.assertEqual(context(first, hs)["unit_form"], "unnumbered_thematic_claim")
        self.partition(store, p, out)
        self.assertTrue(
            any(
                "Signé" in "".join(store.sources[1].text[a:z] for a, z in r["spans"])
                for r in out
                if r["type"] == "technical_passage"
            )
        )

    def test_section_intro_and_numbered_articles_remain_distinct(self):
        store, p, rs = self.fixture(
            [
                "Commerce.",
                BODY,
                "Art. 1. Que les droits soient réduits.",
                "Art. 2. Que les péages soient abolis.",
                "Justice.",
                BODY,
                "Agriculture.",
                BODY,
                "Signé Dupont.",
            ],
            numbered=True,
        )
        original = {r["id"]: copy.deepcopy(r) for r in rs if r["type"] == "article"}
        hs = regions(store, p, rs)
        out, _ = apply(store, p, rs, hs)
        for r in out:
            if r["id"] in original:
                self.assertEqual(r, original[r["id"]])
        h = next(h for h in hs if h["title"].strip() == "Commerce.")
        self.assertEqual(h["form"], "section_with_articles")
        self.assertEqual(len(h["article_ids"]), 2)
        self.assertTrue(h["introduction_spans"])
        self.assertTrue(
            any(r["type"] == "section" and r["spans"] == [[0, len("Commerce.")]] for r in out)
        )
        intro = next(
            r
            for r in out
            if r["type"] == "technical_passage"
            and any(a <= store.sources[1].blocks[1]["start"] < z for a, z in r["spans"])
        )
        self.assertEqual(context(intro, hs)["unit_form"], "section_introduction")
        self.partition(store, p, out)

    def test_known_shared_documentary_range_is_not_resegmented(self):
        store, p, rs = self.fixture(
            ["Justice.", BODY, "Commerce.", BODY, "Agriculture.", BODY, "Signé Dupont."]
        )
        hs = regions(store, p, rs, shared_ranges=[[0, p["end"]]])
        out, changes = apply(store, p, rs, hs)
        self.assertEqual(out, rs)
        self.assertEqual(changes, [])
        self.assertTrue(
            all("known_shared_documentary_range_kept_unsegmented" in h["reasons"] for h in hs)
        )

    def test_human_parent_is_unchanged(self):
        store, p, rs = self.fixture(
            ["Justice.", BODY, "Commerce.", BODY, "Agriculture.", BODY, "Signé Dupont."]
        )
        before = copy.deepcopy(rs)
        out, changes = apply(store, p, rs, regions(store, p, rs), protected_parent=True)
        self.assertEqual(out, before)
        self.assertEqual(changes, [])

    def test_short_lines_dates_and_votes_are_not_thematic_claims(self):
        for text in [
            "Du 13 mars 1789.",
            "Le clergé. Non admis cet article.",
            "CAHIER DES HABITANTS",
            "Art. 2. Que justice soit rendue.",
            "II.",
        ]:
            self.assertFalse(title(text, "p"), text)
        store, p, rs = self.fixture(
            [
                "Uniformité des mesures.",
                "Liberté du roulage.",
                BODY,
                "Commerce.",
                BODY,
                "Justice.",
                BODY,
                "Signé Dupont.",
            ]
        )
        h = regions(store, p, rs)[0]
        self.assertEqual(h["confidence"], "uncertain")
        self.assertTrue(
            set(h["reasons"])
            & {"first_body_too_short_to_distinguish_list_item_from_title", "no_development"}
        )

    def test_unrecognized_numbered_prose_is_not_renamed_unnumbered(self):
        store, p, rs = self.fixture(
            [
                "Justice.",
                BODY,
                "Art. 1. Que les frais diminuent.",
                "Art. 2. Que les délais diminuent.",
                "Commerce.",
                BODY,
                "Agriculture.",
                BODY,
                "Signé Dupont.",
            ]
        )
        h = regions(store, p, rs)[0]
        self.assertIn("possible_numbered_articles_in_prose", h["reasons"])
        self.assertEqual(h["confidence"], "uncertain")

    def test_lowercase_possible_heading_keeps_scope_uncertain(self):
        store, p, rs = self.fixture(
            [
                "Clergé.",
                BODY,
                "commerce.",
                BODY,
                "Justice.",
                BODY,
                "Agriculture.",
                BODY,
                "Signé Dupont.",
            ]
        )
        h = regions(store, p, rs)[0]
        self.assertIn("possible_lowercase_heading_inside_scope", h["reasons"])
        self.assertEqual(h["confidence"], "uncertain")

    def test_request_only_in_editorial_note_is_not_a_claim(self):
        store, p, rs = self.fixture(
            [
                "Justice.",
                "Description du système sans demande explicite. " * 5,
                BODY,
                "Commerce.",
                BODY,
                "Agriculture.",
                BODY,
                "Signé Dupont.",
            ]
        )
        note = store.sources[1].blocks[2]
        note["role"] = "editorial_note"
        p["annotations"] = [dict(start=note["start"], end=note["end"])]
        h = regions(store, p, rs)[0]
        self.assertEqual(h["form"], "uncertain")


if __name__ == "__main__":
    unittest.main()
