"""Material corruption tests and actual human-decision propagation (temporary only)."""

import copy
import tempfile
import unittest
from pathlib import Path

from build import HERE, Store, load, rows, run, sha
from verify import validate


class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.store = Store(Path(cls.temp.name) / "never-real-decisions.jsonl")
        real_journal = Store().journal
        cls.real_journal_sha = sha(real_journal.read_bytes() if real_journal.exists() else b"")
        cls.parents = rows(HERE / "data/parents.jsonl.gz")
        cls.units = sum([rows(HERE / f"data/units-{status}.jsonl.gz") for status in "ABC"], [])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_full_corpus(self):
        self.assertTrue(validate(self.store, self.parents, self.units))
        withheld = load(HERE / "data/withheld.json")
        self.assertEqual(len(self.parents) + len(withheld), 30)
        self.assertEqual(len({p["persee_id"] for p in self.parents}), len(self.parents))
        self.assertTrue(
            {p["document_id"] for p in withheld}.isdisjoint({p["id"] for p in self.parents})
        )

    def test_corruptions_detected(self):
        target = next(i for i, u in enumerate(self.units) if u["type"] == "article")
        for change in [
            "text",
            "parent_id",
            "parent_start",
            "end",
            "duplicate",
            "missing_technical",
        ]:
            units = copy.deepcopy(self.units)
            if change == "text":
                units[target]["text"] = "Modernised replacement"
            elif change == "parent_id":
                units[target]["parent_id"] = "wrong-parent"
            elif change == "parent_start":
                units[target]["parent_start"] += 1
            elif change == "end":
                units[target]["end"] = 10**10
            elif change == "duplicate":
                units.append(copy.deepcopy(units[target]))
            elif change == "missing_technical":
                units.pop(next(i for i, u in enumerate(units) if u["type"] == "technical_passage"))
            with self.subTest(change=change), self.assertRaises(AssertionError):
                validate(self.store, self.parents, units)

    def test_human_uncertainty_withholds_parent_and_reproduces(self):
        store = self.store
        record = store.by_id[self.parents[0]["id"]]
        span = store.state(record)["selected"]
        payload = dict(
            document_id=record["id"],
            source_version=store.source_version(record),
            previous_event_id=None,
            start_id=span["start_id"],
            end_id=span["end_id"],
            endpoint_decisions={"start": "uncertain", "end": "uncertain"},
            reviewer="SYNTHETIC INTEGRATION TEST",
            human_confirmation=False,
            note="Test only",
            active_seconds=0,
        )
        store.save_decision(payload)
        out1 = Path(self.temp.name) / "first"
        out2 = Path(self.temp.name) / "second"
        parents, units = run(out1, store.journal)
        self.assertEqual(len(parents), 29)
        self.assertNotIn(record["id"], {p["id"] for p in parents})
        self.assertTrue(validate(store, parents, units))
        run(out2, store.journal)
        for name in [
            "parents.jsonl.gz",
            "units-A.jsonl.gz",
            "units-B.jsonl.gz",
            "units-C.jsonl.gz",
            "automatic-proposals.jsonl.gz",
            "crosswalk.jsonl",
            "source-manifest.json",
            "extraction-manifest.json",
        ]:
            self.assertEqual((out1 / name).read_bytes(), (out2 / name).read_bytes(), name)
        # Main export and actual journal remain completely unaffected.
        self.assertEqual(len(rows(HERE / "data/parents.jsonl.gz")), len(self.parents))
        real_journal = Store().journal
        self.assertEqual(
            sha(real_journal.read_bytes() if real_journal.exists() else b""), self.real_journal_sha
        )


if __name__ == "__main__":
    unittest.main()
