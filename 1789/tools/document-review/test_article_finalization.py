"""Source-preserving repairs and false-cut controls; all fixtures are synthetic."""

import unittest
from types import SimpleNamespace

from article_rules import content_class, repair
from test_segmentation import SyntheticSource


class FinalArticleTests(unittest.TestCase):
    def fixture(self, texts, left=1, right=3, bare=False, all_c=False):
        source = SyntheticSource(texts)
        parent = dict(
            id="TEST",
            volume=1,
            start=0,
            end=len(source.text),
            blocks=source.blocks,
            annotations=[],
            extent_id="SYNTHETIC",
        )

        def unit(uid, kind, a, z, n=None):
            return dict(
                id=uid,
                parent_id="TEST",
                parent_extent_id="SYNTHETIC",
                type=kind,
                number=str(n) if n is not None else None,
                label=(str(n) + "°" if bare else "Art. " + str(n) + ".") if n else None,
                review_status="automatic_proposal",
                source_status="B" if n else "C",
                origin_ids=[uid],
                section_id=None,
                last_event_id=None,
                spans=[[a, z]],
            )

        end = source.blocks[-1]["start"]
        records = (
            [unit("C", "technical_passage", 0, len(source.text))]
            if all_c
            else [
                unit("left", "article", 0, end, left),
                unit("right", "article", end, len(source.text), right),
            ]
        )
        return SimpleNamespace(sources={1: source}), parent, records

    def assert_partition(self, store, parent, records):
        spans = sorted(s for r in records for s in r["spans"])
        self.assertEqual(spans[0][0], 0)
        self.assertEqual(spans[-1][1], parent["end"])
        self.assertTrue(all(a[1] == b[0] for a, b in zip(spans, spans[1:])))
        self.assertEqual(
            "".join(store.sources[1].text[a:z] for a, z in spans), store.sources[1].text
        )

    def test_damaged_prefix_and_exact_partition(self):
        store, p, rs = self.fixture(
            [
                "Art. 1. Que justice soit rendue.",
                "A:rt. 2. Que les frais diminuent.",
                "Suite sans nouveau numéro.",
                "Art. 3. Que tous contribuent.",
            ]
        )
        out, cs, changes = repair(store, p, rs)
        self.assertEqual(len(changes), 1)
        self.assertEqual(len([r for r in out if r["type"] == "article"]), 3)
        self.assert_partition(store, p, out)

    def test_ocr_hint_never_invents_historical_number(self):
        store, p, rs = self.fixture(
            [
                "10° Que justice soit rendue.",
                "l lQue les frais diminuent.",
                "12° Que tous contribuent.",
            ],
            10,
            12,
            True,
        )
        out, cs, changes = repair(store, p, rs)
        self.assertEqual(len(changes), 1)
        self.assertEqual(cs[0]["numeric_hint"], 11)
        self.assertIsNone(out[1]["number"])
        self.assert_partition(store, p, out)

    def test_dates_amounts_citations_and_sublist_not_split(self):
        for middle in [
            "2 livres seront payées.",
            "2 avril 1789.",
            "Il sera permis de se réunir.",
            "Voir l’Art. 2. Que justice soit rendue.",
            "2° Que les frais diminuent.",
        ]:
            with self.subTest(middle=middle):
                store, p, rs = self.fixture(
                    ["Art. 1. Que justice soit rendue.", middle, "Art. 3. Que tous contribuent."]
                )
                out, _, changes = repair(store, p, rs)
                self.assertEqual(changes, [])
                self.assertEqual(out, rs)

    def test_human_parent_preserved(self):
        store, p, rs = self.fixture(
            [
                "Art. 1. Que justice soit rendue.",
                "Àrt. 2. Que les frais diminuent.",
                "Art. 3. Que tous contribuent.",
            ]
        )
        out, _, changes = repair(store, p, rs, protected_parent=True)
        self.assertEqual(out, rs)
        self.assertEqual(changes, [])

    def test_c_recovery_keeps_signature(self):
        store, p, rs = self.fixture(
            [
                "Préambule conservé.",
                "A:rt. 1. Que justice soit rendue.",
                "A:rt. 2. Que les frais diminuent.",
                "A:rt. 3. Que tous contribuent.",
                "Signé Dupont.",
            ],
            all_c=True,
        )
        p["blocks"][-1]["role"] = "closing_or_signature"
        out, _, changes = repair(store, p, rs)
        self.assertEqual(len(changes), 3)
        self.assertEqual(sum(r["type"] == "article" for r in out), 3)
        self.assert_partition(store, p, out)
        self.assertTrue(
            any(
                "Signé" in "".join(store.sources[1].text[a:z] for a, z in r["spans"])
                for r in out
                if r["type"] == "technical_passage"
            )
        )

    def test_prose_with_false_heading_role_not_discarded(self):
        store, p, rs = self.fixture(
            [
                "Que les frais de justice soient diminués et que les justiciables puissent obtenir la protection de leurs droits."
            ],
            all_c=True,
        )
        p["blocks"][0]["role"] = "section_heading"
        self.assertEqual(content_class(store, p, rs[0])[0], "claim_prose_proposal")


if __name__ == "__main__":
    unittest.main()
