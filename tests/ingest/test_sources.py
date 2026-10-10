"""Regression checks for source sampling: CSV records must stay intact."""
import csv
import io
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from ingest import sources


class SourceSamplingTests(unittest.TestCase):
    def test_multiline_and_multiple_choices_survive_sampling_and_cache(self):
        resource = {"id": "test-resource", "format": "csv", "title": "Fixture", "url": "https://example.test/export.csv"}
        payload = 'id,question\r\n1,"Transport|Vélo\nAutre précision"\r\n2,Non\r\n'.encode("utf-8-sig")
        with tempfile.TemporaryDirectory() as folder:
            args = Namespace(directory=Path(folder), full=False, rows=1)
            responses = [io.BytesIO(json.dumps({"resources": [resource]}).encode()), io.BytesIO(payload)]
            with patch.dict(sources.SOURCES, {"fixture": resource["id"]}, clear=True), patch.object(sources, "urlopen", side_effect=responses):
                sources.fetch(args)
            target = Path(folder) / "samples/fixture.csv"
            with target.open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows, [{"id": "1", "question": "Transport|Vélo\nAutre précision"}])
            manifest = json.loads(target.with_suffix(".manifest.json").read_text())
            self.assertEqual(manifest["sample_rows_written"], 1)
            self.assertEqual(manifest["sha256"], sources.digest(target))
            # A verified second run must not download the resource again.
            with patch.dict(sources.SOURCES, {"fixture": resource["id"]}, clear=True), patch.object(sources, "urlopen", return_value=io.BytesIO(json.dumps({"resources": [resource]}).encode())) as request:
                sources.fetch(args)
                self.assertEqual(request.call_count, 1)

    def test_malformed_row_is_rejected_before_publishing_sample(self):
        resource = {"id": "test-resource", "format": "csv", "title": "Fixture", "url": "https://example.test/export.csv"}
        with tempfile.TemporaryDirectory() as folder:
            args = Namespace(directory=Path(folder), full=False, rows=1)
            responses = [io.BytesIO(json.dumps({"resources": [resource]}).encode()), io.BytesIO(b"id,question\n1,yes,extra\n")]
            with patch.dict(sources.SOURCES, {"fixture": resource["id"]}, clear=True), patch.object(sources, "urlopen", side_effect=responses):
                with self.assertRaisesRegex(ValueError, "largeur incorrecte"):
                    sources.fetch(args)
            self.assertFalse((Path(folder) / "samples/fixture.csv").exists())


if __name__ == "__main__":
    unittest.main()
