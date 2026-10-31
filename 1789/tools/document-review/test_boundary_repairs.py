"""Documentary corrections against local XML; no decisions written, no article rules changed."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "extraction"))
from boundary_rules import exact_name, identity, plan  # noqa: E402
from reviewlib import PRIVATE, Store  # noqa: E402


class BoundaryRepairsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = {
            name: (PRIVATE / name).read_bytes()
            for name in ["decisions.jsonl", "article-decisions.jsonl"]
        }
        cls.store = Store()
        cls.states = {r["id"]: cls.store.state(r) for r in cls.store.records}
        cls.plan = plan(cls.store)
        cls.by_suffix = {r["persee_id"].split("_")[-1]: r for r in cls.plan}

    def test_typographic_splitting_is_not_fuzzy_ocr(self):
        self.assertTrue(exact_name("ermont", "d?Er-, mont"))
        self.assertTrue(exact_name("victoret", "Saint- Victoret"))
        self.assertFalse(exact_name("naux", "NaufC]"))
        self.assertFalse(exact_name("arles", "Charles"))

    def test_unique_name_corrects_wrong_shared_page(self):
        row = self.by_suffix["2168"]
        self.assertTrue(row["changed"])
        self.assertEqual(row["selected"]["start"], 4774125)
        text = self.store.sources[4].text[row["selected"]["start"] : row["selected"]["end"]]
        self.assertTrue(exact_name("ermont", text[:600]))
        self.assertNotEqual(row["selected"]["start"], self.by_suffix["2167"]["selected"]["start"])

    def test_general_end_rule_does_not_absorb_next_cahier(self):
        first = self.by_suffix["1536"]
        second = self.by_suffix["1537"]
        self.assertIn("stop_before_identified_next_cahier", first["actions"])
        self.assertEqual(first["selected"]["end"], second["selected"]["start"])
        self.assertEqual(second["selected"]["end"], self.by_suffix["1538"]["selected"]["start"])

    def test_missing_title_continuation_is_recovered_without_changing_text(self):
        row = self.by_suffix["2557"]
        self.assertIsNone(row["original_span"])
        self.assertEqual(row["selected"]["start"], 2111052)
        source = self.store.sources[6]
        self.assertIn(
            "Allauch", source.text[row["selected"]["start"] : row["selected"]["start"] + 500]
        )

    def test_annex_must_not_replace_cahier_identity(self):
        # The first draft would mistake these powers for the full Dijon cahier.
        row = self.by_suffix["1829"]
        self.assertFalse(row["changed"])
        record = self.store.by_id[row["document_id"]]
        self.assertFalse(
            identity(
                record,
                dict(
                    title="Pouvoirs relatifs aux mandats de rigueur donnés aux députés du tiers-état de Dijon"
                ),
            )
        )
        self.assertFalse(
            identity(
                dict(
                    metadata=dict(
                        title="Liste des comparants des trois ordres du baillage d’Avesnes"
                    ),
                    document_kind="liste",
                ),
                dict(title="Procès-verbal de la noblesse au bailliage d'Avesnes"),
            )
        )

    def test_human_boundaries_and_uncertain_digne_are_untouched(self):
        for r in self.plan:
            old = self.states[r["document_id"]]
            if old["event"]:
                self.assertEqual(r["selected"], old["selected"])
                self.assertFalse(r["changed"])
        self.assertEqual(self.states[self.by_suffix["1944"]["document_id"]]["status"], "uncertain")
        for name, data in self.original.items():
            self.assertEqual((PRIVATE / name).read_bytes(), data)

    def test_stale_error_alert_is_explained_only_when_reference_was_applied(self):
        resolved = {r["code"] for r in self.by_suffix["1532"]["resolved_alerts"]}
        self.assertIn("new_control_boundary_incorrect", resolved)
        uncertain = {r["code"] for r in self.by_suffix["1944"]["resolved_alerts"]}
        self.assertNotIn("new_control_boundary_incorrect", uncertain)

    def test_recovered_openings_do_not_include_previous_certification(self):
        for suffix, expected in [("2186", "Des plaintes"), ("2530", "VŒU DE LA NOBLESSE")]:
            row = self.by_suffix[suffix]
            span = row["selected"]
            text = self.store.sources[row["volume"]].text[span["start"] : span["end"]]
            self.assertTrue(text.startswith(expected))
        self.assertEqual(self.by_suffix["2797"]["documentary_kind"], "proces_verbal")

    def test_lauzet_and_revel_do_not_share_their_tail(self):
        lauzet = self.by_suffix["1952"]["selected"]
        revel = self.by_suffix["1953"]["selected"]
        self.assertLessEqual(self.by_suffix["1951"]["selected"]["end"], lauzet["start"])
        self.assertLessEqual(lauzet["end"], revel["start"])
        self.assertLessEqual(revel["end"], self.by_suffix["1955"]["selected"]["start"])

    def test_scoped_correction_cannot_replace_a_later_human_decision(self):
        import copy

        from documentary_finalization import apply

        findings = copy.deepcopy(self.plan)
        row = next(r for r in findings if r["persee_id"].endswith("_2238"))
        record = self.store.by_id[row["document_id"]]
        retained = copy.deepcopy(row["original_span"])
        row["selected"] = retained
        row["changed"] = False
        original_latest = self.store.latest
        latest = original_latest()
        latest[row["document_id"]] = dict(
            id="SYNTHETIC-NOT-WRITTEN",
            status="human_validated",
            retained=retained,
            source_version=self.store.source_version(record),
        )
        try:
            self.store.latest = lambda: latest
            result = next(
                r for r in apply(self.store, findings) if r["document_id"] == row["document_id"]
            )
            self.assertEqual(result["selected"], retained)
            self.assertTrue(
                any(c["reason"] == "human_decision_has_priority" for c in result["conflicts"])
            )
        finally:
            self.store.latest = original_latest
        for name, data in self.original.items():
            self.assertEqual((PRIVATE / name).read_bytes(), data)

    def test_all_changes_are_traceable_source_positions(self):
        for row in self.plan:
            if not row["changed"]:
                continue
            self.assertTrue(row["actions"])
            self.assertTrue(row["evidence"])
            span = row["selected"]
            v = row["volume"]
            self.assertLess(span["start"], span["end"])
            self.assertLessEqual(span["end"], len(self.store.sources[v].text))
            self.assertTrue(span["start_id"])
            self.assertTrue(span["end_id"])


if __name__ == "__main__":
    unittest.main()
