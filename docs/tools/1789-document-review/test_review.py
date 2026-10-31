"""Real local sources; writes synthetic decisions only to temporary journals."""

import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from reviewlib import Conflict, Store, sha
from server import ReviewServer


class ReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.store = Store(Path(cls.temp.name) / "initial.jsonl")
        cls.server = ReviewServer(0, cls.store)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def setUp(self):
        self.store.journal = Path(self.temp.name) / (self.id().split(".")[-1] + ".jsonl")
        self.record = self.store.records[0]
        self.before = sha(self.store.sources[1].text)

    def payload(self):
        span = self.store.state(self.record)["selected"]
        return dict(
            document_id=self.record["id"],
            source_version=self.store.source_version(self.record),
            previous_event_id=None,
            start_id=span["start_id"],
            end_id=span["end_id"],
            endpoint_decisions={"start": "accepted", "end": "accepted"},
            reviewer="SYNTHETIC TEST ONLY",
            human_confirmation=True,
            note="Temporary test",
            active_seconds=1.25,
        )

    def test_accept_resume_and_history(self):
        p = self.payload()
        first = self.store.save_decision(p)
        self.assertEqual(first["status"], "human_validated")
        self.assertEqual(self.store.state(self.record)["event"]["id"], first["id"])
        p["previous_event_id"] = first["id"]
        p["note"] = "Second version"
        self.store.save_decision(p)
        self.assertEqual(len(self.store.history()), 2)
        self.assertEqual(self.store.stats()["examined_documents"], 1)
        self.assertEqual(sha(self.store.sources[1].text), self.before)

    def test_corrected_block_is_exact(self):
        p = self.payload()
        block = self.store.resolve(self.record, p["end_id"])
        previous = next(
            b for b in reversed(self.store.blocks[1][: block["index"]]) if b["tag"] != "pb"
        )
        p["end_id"] = previous["id"]
        p["endpoint_decisions"]["end"] = "corrected"
        result = self.store.save_decision(p)
        self.assertEqual(result["retained"]["end"], previous["end"])
        self.assertEqual(self.store.stats()["corrected_endpoints"], 1)

    def test_uncertain_internal_and_blocked_not_validation(self):
        for status, expected in [
            ("uncertain", "uncertain"),
            ("inside_block", "uncertain"),
            ("blocked", "blocked"),
        ]:
            p = self.payload()
            p["endpoint_decisions"]["end"] = status
            p["human_confirmation"] = False
            p["previous_event_id"] = self.store.latest().get(self.record["id"], {}).get("id")
            self.assertEqual(self.store.save_decision(p)["status"], expected)
        self.assertEqual(self.store.stats()["human_validated"], 0)

    def test_invalid_ids_order_and_confirmation(self):
        p = self.payload()
        for change in [
            dict(start_id="invented"),
            dict(start_id=p["end_id"], end_id=p["start_id"]),
            dict(human_confirmation=False),
            dict(human_confirmation="false"),
            dict(source_version={}),
            dict(active_seconds=float("nan")),
        ]:
            bad = copy.deepcopy(p)
            bad.update(change)
            with self.assertRaises(ValueError):
                self.store.save_decision(bad)
        pb = next(b["id"] for b in self.store.blocks[1] if b["tag"] == "pb")
        p["start_id"] = pb
        with self.assertRaises(ValueError):
            self.store.save_decision(p)
        self.assertEqual(self.store.history(), [])

    def test_optimistic_lock(self):
        p = self.payload()
        self.store.save_decision(p)
        with self.assertRaises(Conflict):
            self.store.save_decision(p)
        self.assertEqual(len(self.store.history()), 1)

    def test_tampered_journal_refused(self):
        self.store.save_decision(self.payload())
        self.store.journal.write_text(
            self.store.journal.read_text().replace("Temporary test", "Tampered")
        )
        with self.assertRaises(ValueError):
            self.store.history()

    def test_loopback_host_origin_and_token(self):
        with urlopen(self.url + "/api/meta") as r:
            meta = json.load(r)
        for headers in [
            {"Host": "evil.example"},
            {"Origin": "https://evil.example", "X-Review-Token": meta["token"]},
            {"Origin": self.url},
        ]:
            request = Request(
                self.url + "/api/decision",
                data=json.dumps(self.payload()).encode(),
                headers={"Content-Type": "application/json", **headers},
            )
            with self.assertRaises(HTTPError) as e:
                urlopen(request)
            self.assertEqual(e.exception.code, 403)
        request = Request(
            self.url + "/api/decision",
            data=json.dumps(self.payload()).encode(),
            headers={
                "Content-Type": "application/json",
                "Origin": self.url,
                "X-Review-Token": meta["token"],
            },
        )
        with urlopen(request) as r:
            self.assertEqual(json.load(r)["status"], "human_validated")

    def test_api_context_is_exact_and_registry_unchanged(self):
        url = self.url + "/api/document?id=" + self.record["id"] + "&radius=12"
        with urlopen(url) as response:
            doc = json.load(response)
        for panel in doc["panels"].values():
            for b in panel["blocks"]:
                self.assertEqual(b["text"], self.store.sources[1].text[b["start"] : b["end"]])
        self.assertEqual(len(self.store.listing()), 1305)
        self.assertEqual(self.store.stats()["events"], 0)


if __name__ == "__main__":
    unittest.main()
