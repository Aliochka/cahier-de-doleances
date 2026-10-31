"""Collection corrections use temporary datasets and synthetic journals only."""

import tempfile
import unittest
from pathlib import Path

from articles import INPUT, Articles
from collection import rebuild
from reviewlib import Conflict, Store
from test_articles import synthetic_parents


class CollectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.store = Store(cls.root / "template.jsonl")
        synthetic_parents(cls.store, cls.store.journal)
        cls.parent_template = cls.store.journal.read_bytes()
        cls.data = cls.root / "data"
        cls.data.mkdir()
        for name in [
            "parents.jsonl.gz",
            "units-A.jsonl.gz",
            "units-B.jsonl.gz",
            "units-C.jsonl.gz",
        ]:
            (cls.data / name).symlink_to(INPUT / name)
        (cls.data / "complete.json").write_text("{}")
        cls.key = next(r["id"] for r in cls.store.records if r["persee_id"].endswith("_5_1_2333"))
        cls.real_parent = INPUT.parents[1] / "private/document-review/decisions.jsonl"
        # Actual private files are verified separately by production fingerprints; never opened for writing here.

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        root = self.root / self.id().split(".")[-1]
        root.mkdir()
        self.store.journal = root / "parents.jsonl"
        self.store.journal.write_bytes(self.parent_template)
        self.engine = Articles(
            self.store,
            root / "articles.jsonl",
            directory=self.data,
            override_directory=root / "overrides",
        )
        self.approve()

    def approve(self, start=None):
        r = self.store.by_id[self.key]
        state = self.store.state(r)
        span = state["selected"]
        self.store.save_decision(
            dict(
                document_id=self.key,
                source_version=self.store.source_version(r),
                previous_event_id=(state["event"] or {}).get("id"),
                start_id=start or span["start_id"],
                end_id=span["end_id"],
                endpoint_decisions=dict(start="corrected", end="corrected"),
                human_confirmation=True,
                reviewer="SYNTHETIC COLLECTION TEST",
                note="Temporary test, no real validation",
                active_seconds=0,
            )
        )

    def rebuild(self):
        return rebuild(
            self.store,
            self.engine,
            self.key,
            self.store.state(self.store.by_id[self.key])["event"]["id"],
        )

    def test_rebuild_is_versioned_and_survives_restart(self):
        self.assertNotIn(self.key, self.engine.parents)
        self.rebuild()
        self.assertIn(self.key, self.engine.parents)
        doc = self.engine.document(self.key)
        self.assertTrue(doc["units"])
        self.assertFalse(any(u["human_validated"] for u in doc["units"]))
        before = (self.engine.override_directory / "rebuilds.jsonl").read_bytes()
        again = Articles(
            self.store,
            self.engine.log.journal,
            directory=self.data,
            override_directory=self.engine.override_directory,
        )
        self.assertEqual(doc["units"], again.document(self.key)["units"])
        self.assertEqual(before, (self.engine.override_directory / "rebuilds.jsonl").read_bytes())
        self.rebuild()
        self.assertTrue(
            (self.engine.override_directory / "rebuilds.jsonl").read_bytes().startswith(before)
        )

    def test_rebuild_preserves_documentary_kind_override(self):
        self.store.automatic_corrections[self.key] = dict(
            changed=False, alignment="fort", resolved_alerts=[], documentary_kind="proces_verbal"
        )
        self.rebuild()
        self.assertEqual(self.engine.parents[self.key]["document_kind"], "proces_verbal")
        self.assertEqual(
            self.engine.parents[self.key]["metadata"], self.store.by_id[self.key]["metadata"]
        )

    def test_rebuild_never_erases_article_decisions(self):
        self.rebuild()
        doc = self.engine.document(self.key)
        unit = next(u for u in doc["units"] if u["type"] == "article")
        self.engine.save(
            dict(
                document_id=self.key,
                version=doc["version"],
                previous_event_id=None,
                action="validate",
                unit_ids=[unit["id"]],
                reviewer="SYNTHETIC COLLECTION TEST",
                confirmation=True,
                acknowledge_anomalies=True,
            )
        )
        original = self.engine.log.journal.read_bytes()
        retained = self.rebuild()
        self.assertTrue(retained["retained"])
        r = self.store.by_id[self.key]
        span = self.store.state(r)["selected"]
        b = self.store.block_maps[r["metadata"]["volume"]][span["start_id"]]
        next_block = next(
            q
            for q in self.store.blocks[r["metadata"]["volume"]][b["index"] + 1 :]
            if q["tag"] != "pb"
        )
        self.approve(next_block["id"])
        with self.assertRaises(Conflict):
            self.rebuild()
        self.assertEqual(original, self.engine.log.journal.read_bytes())

    def test_concurrent_parent_change_rejected(self):
        with self.assertRaises(Conflict):
            rebuild(self.store, self.engine, self.key, "obsolete-parent-event")
        self.assertFalse(self.engine.log.journal.exists())


if __name__ == "__main__":
    unittest.main()
