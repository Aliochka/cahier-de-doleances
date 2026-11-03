"""Only synthetic journals; real parent/article journals are never written."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from articles import INPUT, Articles
from reviewlib import Conflict, Store, rows, sha


def synthetic_parents(store, journal):
    """Create explicitly synthetic parent approvals matching the immutable test input."""
    store.journal = Path(journal)
    for p in rows(INPUT / "parents.jsonl.gz"):
        r = store.by_id[p["id"]]
        bs = store.selected_blocks(p["volume"], p["start"], p["end"])
        content = [
            b for b in bs if b["tag"] != "pb" and b["start"] >= p["start"] and b["end"] <= p["end"]
        ]
        payload = dict(
            document_id=p["id"],
            source_version=store.source_version(r),
            previous_event_id=None,
            start_id=content[0]["id"],
            end_id=content[-1]["id"],
            endpoint_decisions={"start": "corrected", "end": "corrected"},
            reviewer="SYNTHETIC TEST PARENT — NOT A REAL REVIEW",
            human_confirmation=True,
            note="Temporary automated test fixture",
            active_seconds=0,
        )
        store.save_decision(payload)


class ArticleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.store = Store(Path(cls.tmp.name) / "template-parents.jsonl")
        synthetic_parents(cls.store, cls.store.journal)
        cls.parent_template = cls.store.journal.read_bytes()
        cls.real_journal = Path("1789/data/private/document-review/decisions.jsonl")
        cls.real_sha = sha(cls.real_journal.read_bytes())
        cls.real_articles = Path("1789/data/private/document-review/article-decisions.jsonl")
        cls.real_article_sha = sha(
            cls.real_articles.read_bytes() if cls.real_articles.exists() else b""
        )

    @classmethod
    def tearDownClass(cls):
        assert sha(cls.real_journal.read_bytes()) == cls.real_sha
        assert (
            sha(cls.real_articles.read_bytes() if cls.real_articles.exists() else b"")
            == cls.real_article_sha
        )
        cls.tmp.cleanup()

    def setUp(self):
        name = self.id().split(".")[-1]
        self.store.journal = Path(self.tmp.name) / (name + "-parents.jsonl")
        self.store.journal.write_bytes(self.parent_template)
        self.engine = Articles(self.store, Path(self.tmp.name) / (name + "-articles.jsonl"))
        self.key = next(
            p["id"] for p in self.engine.parents.values() if p["persee_id"].endswith("_5_1_2339")
        )
        self.doc = self.engine.document(self.key)
        self.articles = [u for u in self.doc["units"] if u["type"] == "article"]

    def payload(self, action, ids, **extra):
        d = self.engine.document(self.key)
        return dict(
            document_id=self.key,
            version=d["version"],
            previous_event_id=d["previous_event_id"],
            action=action,
            unit_ids=ids,
            reviewer="SYNTHETIC ARTICLE REVIEW — TEST ONLY",
            note="Synthetic test, no historical claim",
            confirmation=True,
            **extra,
        )

    def save(self, payload):
        if payload["action"] not in {"validate", "uncertain", "undo"}:
            payload["preview_digest"] = self.engine.preview(payload)["digest"]
        return self.engine.save(payload)

    def current(self):
        return self.engine.document(self.key)

    def test_initial_state(self):
        units, summary, _ = self.engine.export()
        self.assertEqual(summary["by_type"]["article"], 719)
        self.assertEqual(summary["human_validated_units"], 0)
        self.assertEqual(summary["by_source_status"]["A"], 217)
        self.assertEqual(len(self.articles), 9)
        self.assertTrue(all(not a["anomalies"] for a in self.articles))
        self.assertEqual(len(units), 1516)

    def test_classification_on_proposed_parent_is_saved_without_approving_parent(self):
        real_state = self.store.state

        def proposed(record, *args, **kwargs):
            state = real_state(record, *args, **kwargs)
            if record["id"] == self.key:
                state = dict(state, status="proposed", event=None)
            return state

        with patch.object(self.store, "state", side_effect=proposed):
            doc = self.current()
            self.assertTrue(doc["version"]["parent"]["reviewable"])
            self.assertFalse(doc["version"]["parent"]["ready"])
            passage = next(
                u for u in doc["units"] if u["type"] == "technical_passage" and u["text"].strip()
            )
            self.save(self.payload("classify", [passage["id"]], type="paratext"))
            classified = next(u for u in self.current()["units"] if u["spans"] == passage["spans"])
            self.assertEqual(classified["type"], "paratext")
            self.assertTrue(classified["human_validated"])
            self.assertFalse(classified["indexing_eligible"])
            self.assertFalse(classified["publication_ready"])
            restarted = Articles(self.store, self.engine.log.journal)
            self.assertEqual(restarted.document(self.key)["units"], self.current()["units"])
            self.assertEqual(self.store.state(self.store.by_id[self.key])["status"], "proposed")

    def test_article_validation_on_proposed_parent_does_not_make_export_eligible(self):
        original_state = self.store.state

        def proposed(record, *args, **kwargs):
            state = original_state(record, *args, **kwargs)
            return dict(state, status="proposed", event=None) if record["id"] == self.key else state

        with patch.object(self.store, "state", side_effect=proposed):
            self.save(self.payload("validate", [u["id"] for u in self.articles]))
            articles = [u for u in self.current()["units"] if u["type"] == "article"]
            self.assertEqual(sum(u["human_validated"] for u in articles), 9)
            self.assertTrue(
                all(not u["indexing_eligible"] and not u["publication_ready"] for u in articles)
            )
            self.assertFalse(self.current()["version"]["parent"]["ready"])

    def test_uncertain_or_blocked_parent_still_rejects_classification(self):
        real_state = self.store.state
        for status in ["uncertain", "blocked"]:

            def uncertain(record, *args, **kwargs):
                state = real_state(record, *args, **kwargs)
                return dict(state, status=status) if record["id"] == self.key else state

            with patch.object(self.store, "state", side_effect=uncertain):
                c = next(u for u in self.current()["units"] if u["type"] == "technical_passage")
                with self.assertRaises(Conflict):
                    self.engine.preview(self.payload("classify", [c["id"]], type="paratext"))
        self.assertEqual(self.engine.log.history(), [])

    def test_unicode_whitespace_rule_never_absorbs_punctuation_or_text(self):
        record = dict(
            type="technical_passage", review_status="technical_unclassified", last_event_id=None
        )
        with patch.object(self.engine, "text", side_effect=lambda p, r: r["fixture_text"]):
            for text in [" ", "\t\n\r", "\u00a0", "\u202f\u2003\u3000", " \u00a0\t\n"]:
                self.assertTrue(
                    self.engine.automatic_whitespace({}, dict(record, fixture_text=text))
                )
            self.assertTrue(
                self.engine.automatic_whitespace(
                    {},
                    dict(
                        record,
                        fixture_text=" ",
                        last_event_id="human-created-residual-not-a-classification",
                    ),
                )
            )
            for text in ["", ".", " — ", "\n;\t", "a", " 1 ", "\u200b", "\ufeff"]:
                self.assertFalse(
                    self.engine.automatic_whitespace({}, dict(record, fixture_text=text))
                )
            for status, event in [
                ("human_validated", "human-event"),
                ("human_corrected", "human-event"),
                ("uncertain", "human-event"),
            ]:
                self.assertFalse(
                    self.engine.automatic_whitespace(
                        {},
                        dict(record, fixture_text=" ", review_status=status, last_event_id=event),
                    )
                )
            self.assertFalse(
                self.engine.automatic_whitespace({}, dict(record, fixture_text=" ", type="article"))
            )

    def test_automatic_whitespace_keeps_source_and_does_not_create_human_decision(self):
        parent, records, *_ = self.engine.state(self.key)
        white = next(r for r in records.values() if self.engine.automatic_whitespace(parent, r))
        shown = next(u for u in self.current()["units"] if u["id"] == white["id"])
        self.assertEqual(shown["type"], "paratext")
        self.assertEqual(shown["original_type"], "technical_passage")
        self.assertEqual(shown["validation_status"], "automatic_technical_paratext")
        self.assertFalse(shown["requires_human_classification"])
        self.assertFalse(shown["human_validated"])
        self.assertFalse(shown["indexing_eligible"])
        self.assertEqual(shown["spans"], white["spans"])
        self.assertEqual(shown["text"], self.engine.text(parent, white))
        self.assertEqual(self.engine.state(self.key)[1][white["id"]], white)
        self.assertEqual(self.engine.log.history(), [])
        listing = next(p for p in self.engine.listing() if p["id"] == self.key)
        self.assertGreater(listing["automatic_technical_paratext"], 0)
        self.assertEqual(listing["human_reviewed"], 0)
        self.save(self.payload("uncertain", [white["id"]]))
        resumed = Articles(self.store, self.engine.log.journal).document(self.key)
        human = next(u for u in resumed["units"] if u["id"] == white["id"])
        self.assertEqual(human["validation_status"], "uncertain")
        self.assertIsNone(human["automatic_classification"])
        self.assertTrue(human["requires_human_classification"])

    def test_workbench_tracks_target_not_whole_cahier_and_handles_undo(self):
        def window(unit, key):
            return dict(
                id=key, parent_id=self.key, unit_id=unit["id"], start=unit["start"], end=unit["end"]
            )

        windows = [window(self.articles[0], "first"), window(self.articles[1], "second")]
        self.assertEqual(self.engine.workbench_progress(windows)["first"]["status"], "pending")
        self.current()  # Reading never marks anything done.
        self.assertEqual(self.engine.workbench_progress(windows)["first"]["status"], "pending")
        self.save(self.payload("validate", [self.articles[0]["id"]]))
        progress = self.engine.workbench_progress(windows)
        self.assertEqual(progress["first"]["status"], "completed")
        self.assertEqual(progress["second"]["status"], "pending")
        self.assertEqual(
            Articles(self.store, self.engine.log.journal).workbench_progress(windows), progress
        )
        self.save(self.payload("undo", []))
        self.assertEqual(self.engine.workbench_progress(windows)["first"]["status"], "pending")
        self.save(self.payload("uncertain", [self.articles[0]["id"]]))
        self.assertEqual(self.engine.workbench_progress(windows)["first"]["status"], "uncertain")

    def test_workbench_follows_reclassified_passage_and_preserves_window_id(self):
        passage = next(
            u for u in self.doc["units"] if u["type"] == "technical_passage" and u["text"].strip()
        )
        windows = [
            dict(
                id="C",
                parent_id=self.key,
                unit_id=passage["id"],
                start=passage["start"],
                end=passage["end"],
            )
        ]
        self.save(self.payload("classify", [passage["id"]], type="paratext"))
        self.assertNotIn(passage["id"], {u["id"] for u in self.current()["units"]})
        self.assertEqual(self.engine.workbench_progress(windows)["C"]["status"], "completed")

    def test_classify_C_as_article_respects_selected_range_and_keeps_remainder(self):
        c = max(
            (u for u in self.doc["units"] if u["type"] == "technical_passage"),
            key=lambda u: len(u["text"]),
        )
        self.save(
            self.payload(
                "classify",
                [c["id"]],
                type="article",
                number="5",
                start=c["start"] + 1,
                end=c["end"] - 1,
            )
        )
        doc = self.current()
        new = next(
            u for u in doc["units"] if u["type"] == "article" and u["start"] == c["start"] + 1
        )
        self.assertEqual(new["number"], "5")
        self.assertEqual(new["number_origin"], "human_attribution")
        self.assertTrue(new["human_validated"])
        self.assertLessEqual(new["end"], c["end"] - 1)
        p, records, *_ = self.engine.state(self.key)
        self.engine.check(p, list(records.values()))
        self.assertEqual(new["text"], self.engine.text(p, records[new["id"]]))
        self.assertTrue(
            any(
                u["original_type"] == "technical_passage" and u["start"] == c["start"]
                for u in doc["units"]
            )
        )
        self.save(self.payload("undo", []))
        self.assertTrue(any(u["id"] == c["id"] for u in self.current()["units"]))

    def test_classify_C_as_article_can_keep_full_range_without_inventing_number(self):
        c = next(
            u for u in self.doc["units"] if u["type"] == "technical_passage" and u["text"].strip()
        )
        self.save(self.payload("classify", [c["id"]], type="article"))
        article = next(
            u
            for u in self.current()["units"]
            if u["type"] == "article" and u["start"] == c["start"]
        )
        self.assertIsNone(article["number"])
        self.assertEqual(article["text"], c["text"])

    def test_group_validation_and_historic_undo(self):
        self.save(self.payload("validate", [u["id"] for u in self.articles]))
        self.assertEqual(sum(u["human_validated"] for u in self.current()["units"]), 9)
        self.assertEqual(len(self.engine.log.history()[0]["after"]), 9)
        self.save(self.payload("undo", []))
        self.assertEqual(sum(u["human_validated"] for u in self.current()["units"]), 0)
        self.assertEqual(len(self.engine.log.history()), 2)

    def test_individual_equals_group(self):
        self.save(self.payload("validate", [u["id"] for u in self.articles]))
        grouped = self.current()["units"]
        self.engine.log.journal = Path(self.tmp.name) / "individual-new.jsonl"
        for u in self.articles:
            self.save(self.payload("validate", [u["id"]]))
        singles = self.current()["units"]
        for g, s in zip(grouped, singles):
            for field in [
                "id",
                "text",
                "spans",
                "human_validated",
                "validation_status",
                "indexing_eligible",
            ]:
                self.assertEqual(g[field], s[field])

    def test_uncertainty_not_silently_grouped(self):
        self.save(self.payload("uncertain", [self.articles[0]["id"]]))
        with self.assertRaises(ValueError):
            self.save(self.payload("validate", [u["id"] for u in self.articles]))
        self.assertEqual(len(self.engine.log.history()), 1)
        self.save(self.payload("validate", [self.articles[0]["id"]], acknowledge_anomalies=True))
        self.assertTrue(
            next(u for u in self.current()["units"] if u["id"] == self.articles[0]["id"])[
                "human_validated"
            ]
        )

    def test_split_inside_paragraph_and_merge(self):
        u = self.articles[0]
        point = u["start"] + len(u["text"]) // 2
        self.save(self.payload("split", [u["id"]], point=point, number="1a", second_number="1b"))
        split = [
            r
            for r in self.current()["units"]
            if u["id"] in r["origin_ids"] and r["type"] == "article"
        ]
        self.assertEqual(len(split), 2)
        self.assertEqual("".join(r["text"] for r in split), u["text"])
        self.save(self.payload("merge", [r["id"] for r in split], type="article", number="1er"))
        merged = [
            r
            for r in self.current()["units"]
            if u["id"] in r["origin_ids"] and r["type"] == "article"
        ]
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["text"], u["text"])
        self.assertEqual(len(merged[0]["xml_blocks"]), len(u["xml_blocks"]))

    def test_correction_does_not_delete_remainder(self):
        u = self.articles[0]
        self.save(
            self.payload(
                "correct",
                [u["id"]],
                start=u["start"] + 8,
                end=u["end"] - 5,
                type="article",
                number=u["number"],
            )
        )
        doc = self.current()
        p = self.engine.parents[self.key]
        self.engine.check(p, [{k: v for k, v in r.items() if k not in []} for r in doc["units"]])
        raw = self.store.sources[p["volume"]].text
        coverage = sorted((a, z) for r in doc["units"] for a, z in r["spans"])
        self.assertEqual("".join(raw[a:z] for a, z in coverage), p["full_text"])

    def test_overlapping_other_article_rejected(self):
        a, b = self.articles[:2]
        with self.assertRaises(ValueError):
            self.engine.preview(
                self.payload("correct", [a["id"]], start=a["start"], end=b["end"], type="article")
            )
        with self.assertRaises(ValueError):
            self.engine.preview(
                self.payload(
                    "merge", [self.articles[0]["id"], self.articles[2]["id"]], type="article"
                )
            )
        self.assertEqual(self.engine.log.history(), [])

    def test_classification_and_missing_article_are_distinct(self):
        c = max(
            (u for u in self.doc["units"] if u["type"] == "technical_passage"),
            key=lambda u: len(u["text"]),
        )
        self.save(self.payload("classify", [c["id"]], type="paratext"))
        classified = next(u for u in self.current()["units"] if u["spans"] == c["spans"])
        self.assertEqual(classified["type"], "paratext")
        self.assertFalse(classified["indexing_eligible"])
        self.save(self.payload("undo", []))
        self.save(self.payload("classify", [c["id"]], type="claim_passage"))
        claim = next(u for u in self.current()["units"] if u["spans"] == c["spans"])
        self.assertEqual(claim["type"], "claim_passage")
        self.assertIsNone(claim["number"])
        self.assertTrue(claim["indexing_eligible"])
        self.save(self.payload("undo", []))
        self.save(
            self.payload("missing", [], start=c["start"], end=c["end"], type="article", number=None)
        )
        self.assertEqual(len([u for u in self.current()["units"] if u["type"] == "article"]), 10)

    def test_number_correction_does_not_rewrite_text(self):
        u = self.articles[0]
        self.save(self.payload("number", [u["id"]], number="I"))
        updated = next(x for x in self.current()["units"] if x["id"] == u["id"])
        self.assertEqual(updated["number"], "I")
        self.assertEqual(updated["text"], u["text"])
        self.assertEqual(updated["number_origin"], "human_attribution")

    def test_stale_parent_cannot_keep_validation(self):
        self.save(self.payload("validate", [self.articles[0]["id"]]))
        record = self.store.by_id[self.key]
        state = self.store.state(record)
        span = state["selected"]
        self.store.save_decision(
            dict(
                document_id=self.key,
                source_version=self.store.source_version(record),
                previous_event_id=state["event"]["id"],
                start_id=span["start_id"],
                end_id=span["end_id"],
                endpoint_decisions={"start": "accepted", "end": "uncertain"},
                reviewer="SYNTHETIC PARENT CHANGE",
                human_confirmation=False,
                note="Temporary test only",
                active_seconds=0,
            )
        )
        doc = self.current()
        self.assertIsNotNone(doc["warning"])
        self.assertFalse(any(u["indexing_eligible"] for u in doc["units"]))
        self.assertFalse(any(u["human_validated"] for u in doc["units"]))
        with self.assertRaises(Conflict):
            self.save(self.payload("validate", [self.articles[1]["id"]]))

    def test_parent_boundary_correction_invalidates_articles(self):
        self.save(self.payload("validate", [self.articles[0]["id"]]))
        record = self.store.by_id[self.key]
        state = self.store.state(record)
        span = state["selected"]
        last = self.store.resolve(record, span["end_id"])
        earlier = next(
            b
            for b in reversed(self.store.blocks[record["metadata"]["volume"]][: last["index"]])
            if b["tag"] != "pb"
        )
        self.store.save_decision(
            dict(
                document_id=self.key,
                source_version=self.store.source_version(record),
                previous_event_id=state["event"]["id"],
                start_id=span["start_id"],
                end_id=earlier["id"],
                endpoint_decisions={"start": "corrected", "end": "corrected"},
                reviewer="SYNTHETIC GEOMETRY CHANGE",
                human_confirmation=True,
                note="Test only",
                active_seconds=0,
            )
        )
        doc = self.current()
        self.assertFalse(doc["version"]["parent"]["compatible"])
        self.assertFalse(any(u["human_validated"] or u["indexing_eligible"] for u in doc["units"]))
        self.assertTrue(any(u["validation_status"] == "review_required" for u in doc["units"]))

    def test_regenerated_parent_version_does_not_reuse_human_decisions(self):
        import gzip
        import json

        self.save(self.payload("validate", [self.articles[0]["id"]]))
        directory = Path(self.tmp.name) / "regenerated-input"
        directory.mkdir()
        parents = rows(INPUT / "parents.jsonl.gz")
        target = next(p for p in parents if p["id"] == self.key)
        target["extent_id"] += ":synthetic-new-version"
        (directory / "parents.jsonl.gz").write_bytes(
            gzip.compress(("".join(json.dumps(p) + "\n" for p in parents)).encode())
        )
        for status in "ABC":
            units = rows(INPUT / f"units-{status}.jsonl.gz")
            for unit in units:
                if unit["parent_id"] == self.key:
                    unit["parent_extent_id"] = target["extent_id"]
            (directory / f"units-{status}.jsonl.gz").write_bytes(
                gzip.compress(("".join(json.dumps(u) + "\n" for u in units)).encode())
            )
        regenerated = Articles(self.store, self.engine.log.journal, directory)
        doc = regenerated.document(self.key)
        self.assertEqual(len(doc["stale_events"]), 1)
        self.assertFalse(any(u["human_validated"] or u["indexing_eligible"] for u in doc["units"]))
        self.assertEqual(len(regenerated.log.history()), 1)

    def test_stale_tabs_and_fake_ranges_rejected(self):
        old = self.payload("validate", [self.articles[0]["id"]])
        self.save(old)
        with self.assertRaises(Conflict):
            self.save(old)
        with self.assertRaises(ValueError):
            self.engine.preview(
                self.payload("correct", [self.articles[0]["id"]], start=-1, end=10, type="article")
            )
        bad = self.payload("validate", [self.articles[1]["id"]])
        bad["confirmation"] = "true"
        with self.assertRaises(ValueError):
            self.engine.save(bad)
        self.assertEqual(len(self.engine.log.history()), 1)

    def test_replay_reproducible_export_and_journal_tamper(self):
        self.save(self.payload("validate", [self.articles[0]["id"]]))
        self.engine.write_export(Path(self.tmp.name) / "export-one")
        replay = Articles(self.store, self.engine.log.journal)
        replay.write_export(Path(self.tmp.name) / "export-two")
        for name in ["units.jsonl.gz", "summary.json", "manifest.json", "invalidated.jsonl.gz"]:
            self.assertEqual(
                (Path(self.tmp.name) / "export-one" / name).read_bytes(),
                (Path(self.tmp.name) / "export-two" / name).read_bytes(),
            )
        text = self.engine.log.journal.read_text()
        self.engine.log.journal.write_text(text.replace("Synthetic test", "Altered test"))
        with self.assertRaises(ValueError):
            replay.log.history()

    def test_ferrieres_sections_and_long_multiblock_article(self):
        key = next(
            p["id"] for p in self.engine.parents.values() if p["persee_id"].endswith("_4_1_2175")
        )
        doc = self.engine.document(key)
        self.assertEqual(len([u for u in doc["units"] if u["type"] == "article"]), 25)
        self.assertTrue(any("COMMERCE" in (u["section"] or "") for u in doc["units"]))
        units, _, _ = self.engine.export()
        self.assertTrue(any(u["type"] == "article" and len(u["xml_blocks"]) > 2 for u in units))
        self.assertTrue(
            any(u["type"] == "technical_passage" and len(u["text"]) > 1800 for u in units)
        )

    def test_new_fusion_flags_block_groups_but_keep_human_priority(self):
        unit = self.articles[0]
        marker = dict(start=unit["start"] + 40, label="TEST 2°", status="suspect")
        proposals = dict(available=True, markers=[marker])
        with patch("segmentation_comparison.comparison", return_value=proposals):
            current = self.current()
            flagged = next(u for u in current["units"] if u["id"] == unit["id"])
            self.assertTrue(any("Fusion potentielle" in f for f in flagged["anomalies"]))
            with self.assertRaises(ValueError):
                self.save(
                    self.payload("validate", [self.articles[0]["id"], self.articles[1]["id"]])
                )
            payload = self.payload("validate", [unit["id"]])
            payload["acknowledge_anomalies"] = True
            self.save(payload)
            reviewed = next(u for u in self.current()["units"] if u["id"] == unit["id"])
            self.assertTrue(reviewed["human_validated"])
            self.assertFalse(any("Fusion potentielle" in f for f in reviewed["anomalies"]))
            replay = Articles(self.store, self.engine.log.journal)
            self.assertEqual(
                replay.state(self.key)[1][unit["id"]]["review_status"], "human_validated"
            )

    def test_optional_comparison_never_changes_units_or_history(self):
        before = self.engine.state(self.key)
        doc = self.engine.document(self.key)
        self.assertIn("segmentation_comparison", doc)
        self.assertEqual(before, self.engine.state(self.key))


if __name__ == "__main__":
    unittest.main()
