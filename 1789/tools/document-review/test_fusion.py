"""Synthetic thematic fusion controls, source partition and human priority."""

import copy
import unittest
from types import SimpleNamespace

from articles import canonical
from fusion import apply, detect, record
from test_segmentation import SyntheticSource

PREFIX = "2° Dans les campagnes, la rémunération des curés doit tenir compte du nombre des habitants. Les vicaires reçoivent une pension, prise sur les dîmes et les bénéfices."
DOTATION = "Dotation des cures de l'ordre de Malte et vicariats d'icelles."
BODY = "Les cures et vicariats de l'ordre de Malte doivent jouir des mêmes avantages que les autres cures. On demande qu'el- le ssoient gouvernées par le même régime et ne reconnaissent que les autorités ordinaires."
RETIRE = "Retraite pour les anciens ecclésiastiques qui auront travaillé dans le\n saint ministère."
ARGUMENT = "Un développement consacré à une retraite honorable et à une pension après de longues années de service dans le ministère, avec plusieurs arguments de continuité mais sans nouvelle demande explicite."


class FusionTests(unittest.TestCase):
    def fixture(self, middle=None, kind="article"):
        texts = (
            [PREFIX, DOTATION, BODY, RETIRE, ARGUMENT, "Art. 3. Que la justice soit rendue."]
            if middle is None
            else [PREFIX] + middle + ["Art. 3. Que la justice soit rendue."]
        )
        src = SyntheticSource(texts)
        p = dict(
            id="TEST",
            volume=1,
            start=0,
            end=len(src.text),
            extent_id="TEST-EXTENT",
            blocks=src.blocks,
            annotations=[],
        )
        old = record(p, kind, [[0, src.blocks[-1]["start"]]], ["original"])
        old.update(
            id="old",
            number="2" if kind == "article" else None,
            label="2°" if kind == "article" else None,
            source_status="B" if kind != "technical_passage" else "C",
        )
        nxt = record(p, "article", [[src.blocks[-1]["start"], len(src.text)]], ["next"])
        nxt.update(id="next", number="3", label="Art. 3.")
        return SimpleNamespace(sources={1: src}), p, [old, nxt]

    def partition(self, store, parent, rs):
        spans = sorted(s for r in rs for s in r["spans"])
        self.assertEqual(spans[0][0], 0)
        self.assertEqual(spans[-1][1], parent["end"])
        self.assertTrue(all(a[1] == b[0] for a, b in zip(spans, spans[1:])))
        self.assertEqual(
            "".join(store.sources[1].text[a:z] for a, z in spans), store.sources[1].text
        )

    def test_amiens_shape_splits_numbered_prefix_and_literal_unnumbered_title(self):
        store, p, rs = self.fixture()
        hs = detect(store, p, rs)
        out, changes = apply(store, p, rs, hs)
        h = next(h for h in hs if "Dotation" in h["title"])
        self.assertEqual(h["confidence"], "proposed", h["reasons"])
        self.assertEqual(len(changes), 1)
        numbered = next(r for r in out if r["number"] == "2")
        self.assertEqual(numbered["spans"], [[0, h["title_start"]]])
        claim = next(r for r in out if r["type"] == "article" and r["number"] is None)
        self.assertEqual(claim["spans"], [[h["title_start"], store.sources[1].blocks[3]["start"]]])
        self.assertEqual(
            "".join(store.sources[1].text[a:z] for a, z in claim["spans"]),
            DOTATION + "\n" + BODY + "\n",
        )
        self.assertEqual(next(r for r in out if r["id"] == "next"), rs[-1])
        self.assertTrue(any(r["type"] == "technical_passage" for r in out))
        self.partition(store, p, out)
        self.assertEqual(canonical(out), canonical(apply(store, p, rs, hs)[0]))

    def test_same_mechanism_applies_to_sections_and_C(self):
        for kind in ["section", "technical_passage"]:
            store, p, rs = self.fixture(kind=kind)
            out, changes = apply(store, p, rs, detect(store, p, rs))
            self.assertEqual(len(changes), 1)
            self.assertTrue(any(r["type"] == "article" and r["number"] is None for r in out))
            self.assertTrue(any(r["type"] == kind and r["spans"][0][0] == 0 for r in out))
            self.partition(store, p, out)

    def test_motifs_and_rhetorical_subtitles_remain_inside_original_development(self):
        store, p, rs = self.fixture(["Motifs et raisons.", BODY, "Conséquences.", BODY])
        hs = detect(store, p, rs)
        out, changes = apply(store, p, rs, hs)
        self.assertFalse(changes)
        self.assertEqual(out, rs)
        self.assertTrue(any("dependent_subheading" in h["reasons"] for h in hs))

    def test_ordinary_conditional_sentence_is_not_a_title(self):
        store, p, rs = self.fixture(
            ["La répartition de cet impôt serait presque insensible.", BODY, RETIRE, ARGUMENT]
        )
        hs = detect(store, p, rs)
        self.assertFalse(any("répartition" in h["title"] for h in hs))

    def test_no_request_false_match_from_qu_on_descriptive_quote(self):
        body = "Les lettres de cachet sont présentées ici avec les abus qu'on a constatés autrefois, dans une explication descriptive qui expose ce qui sera décidé par les représentants sans exprimer de nouvelle requête."
        store, p, rs = self.fixture(["Lettres de cachet.", body, RETIRE, ARGUMENT])
        hs = detect(store, p, rs)
        h = next(h for h in hs if h["title"].startswith("Lettres"))
        self.assertIn("no_explicit_request_formula", h["reasons"])

    def test_numbers_and_dates_are_not_theme_titles(self):
        store, p, rs = self.fixture(
            ["15 livres seront versées.", "13 avril 1789.", "Art. 5. Que le commerce soit libre."]
        )
        self.assertFalse(detect(store, p, rs))

    def test_numbered_sublists_or_unclassified_heading_block_automatic_split(self):
        for insert in ["Art. 1. Que les frais diminuent.", "commerce."]:
            store, p, rs = self.fixture([DOTATION, BODY, insert, BODY, RETIRE, ARGUMENT])
            h = next(h for h in detect(store, p, rs) if "Dotation" in h["title"])
            self.assertEqual(h["confidence"], "uncertain")

    def test_ocr_ordinal_body_is_not_reclassified_as_unnumbered(self):
        body = "36d Ils demandèrent que les reconnaissances féodales ne puissent être exigées qu'une fois et que les frais restent à la charge des seigneurs, sans imposer une charge nouvelle aux habitants."
        store, p, rs = self.fixture(["Terme des reconnaissances féodales.", body, RETIRE, ARGUMENT])
        h = next(h for h in detect(store, p, rs) if h["title"].startswith("Terme"))
        self.assertIn("numbered_subdivision_inside_development_kept_together", h["reasons"])

    def test_future_tense_and_participant_names_are_not_titles(self):
        for label in [
            "Feront l'état des offices vénaux, de leurs finances et de leurs gages.",
            "Louis-Joseph Simon, prêtre, fondé de pouvoir du curé de Domremy.",
        ]:
            store, p, rs = self.fixture([label, BODY, RETIRE, ARGUMENT])
            self.assertFalse(any(h["title"].strip() == label for h in detect(store, p, rs)))

    def test_incomplete_considerants_before_arrete_remain_unseparated(self):
        body = "Les représentants demandent que la constitution militaire soit améliorée dans toutes les provinces et considèrent le service des officiers, dont la récompense doit être garantie par des pensions convenables,"
        store, p, rs = self.fixture(["Constitution militaire.", body, "ARRÊTÉ.", BODY])
        h = next(h for h in detect(store, p, rs) if h["title"].startswith("Constitution"))
        self.assertIn("development_not_concluded_before_boundary", h["reasons"])

    def test_human_records_and_replay_ranges_are_never_replaced(self):
        store, p, rs = self.fixture()
        before = copy.deepcopy(rs)
        hs = detect(store, p, rs, protected_spans=rs[0]["spans"])
        self.assertTrue(all(h["protected"] for h in hs))
        out, changes = apply(store, p, rs, hs)
        self.assertFalse(changes)
        self.assertEqual(out, before)
        strong = detect(store, p, rs)
        for status in ["human_validated", "human_corrected", "uncertain"]:
            human = copy.deepcopy(rs)
            human[0]["review_status"] = status
            human[0]["last_event_id"] = "SYNTHETIC"
            out, changes = apply(store, p, human, strong)
            self.assertFalse(changes)
            self.assertEqual(out, human)

    def test_shared_documentary_range_is_only_a_separate_signal(self):
        store, p, rs = self.fixture()
        hs = detect(store, p, rs, shared_spans=rs[0]["spans"])
        out, changes = apply(store, p, rs, hs)
        self.assertFalse(changes)
        self.assertEqual(out, rs)
        self.assertTrue(any("known_shared_documentary_range" in h["reasons"] for h in hs))


if __name__ == "__main__":
    unittest.main()
