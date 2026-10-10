import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ingest.structured_sources import download_resource


class Response(io.BytesIO):
    def __init__(self, payload, status, headers):
        super().__init__(payload)
        self.status = status
        self.headers = headers


class DownloadResumeTests(unittest.TestCase):
    def test_resume_uses_validator_and_preserves_complete_file(self):
        payload = b'[{"id":1},{"id":2}]'
        resource = {
            "url": "https://example.test/export.json",
            "format": "json",
            "title": "Fixture",
            "filesize": len(payload),
        }
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / "fixture.part").write_bytes(payload[:7])
            (folder / "fixture.http.json").write_text(
                json.dumps({"url": resource["url"], "etag": '"version1"'})
            )
            response = Response(
                payload[7:],
                206,
                {
                    "Content-Range": f"bytes 7-{len(payload) - 1}/{len(payload)}",
                    "ETag": '"version1"',
                },
            )
            with patch("ingest.structured_sources.urlopen", return_value=response) as request:
                download_resource(folder, resource, "fixture", "test-resource")
                headers = dict(request.call_args.args[0].header_items())
                self.assertEqual(headers["Range"], "bytes=7-")
                self.assertEqual(headers["If-range"], '"version1"')
            self.assertEqual((folder / "fixture.json").read_bytes(), payload)

    def test_server_sending_full_file_replaces_old_partial(self):
        payload = b'[{"id":2}]'
        resource = {
            "url": "https://example.test/export.json",
            "format": "json",
            "title": "Fixture",
            "filesize": len(payload),
        }
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            (folder / "fixture.part").write_bytes(b"old")
            (folder / "fixture.http.json").write_text(
                json.dumps({"url": resource["url"], "etag": '"version1"'})
            )
            with patch(
                "ingest.structured_sources.urlopen",
                return_value=Response(payload, 200, {"ETag": '"version2"'}),
            ):
                download_resource(folder, resource, "fixture", "test-resource")
            self.assertEqual((folder / "fixture.json").read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
