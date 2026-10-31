"""Loopback-only review server, no application/database dependencies."""

import argparse
import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from reviewlib import AUDITS, HERE, Conflict, Store


class ReviewServer(HTTPServer):
    def __init__(self, port, store, article_journal=None, article_export_directory=None):
        self.store = store
        self.article_journal = article_journal
        self.article_export_directory = (
            article_export_directory or AUDITS / "1789-article-review/data"
        )
        self._articles = None
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)

    def articles(self):
        if self._articles is None:
            from articles import Articles

            self._articles = Articles(self.store, self.article_journal)
        return self._articles


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Avoid logging document identifiers/text or reviewer names.
        pass

    def allowed(self):
        port = self.server.server_port
        return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def send(self, status, data, kind="application/json; charset=utf-8"):
        body = (
            json.dumps(data, ensure_ascii=False).encode()
            if kind.startswith("application/json")
            else data
        )
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'none'; frame-ancestors 'none'; form-action 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.allowed():
            return self.send(403, {"error": "Loopback Host required"})
        url = urlsplit(self.path)
        q = parse_qs(url.query)
        try:
            if url.path == "/api/meta":
                return self.send(
                    200, dict(token=self.server.token, stats=self.server.store.stats())
                )
            if url.path == "/api/list":
                return self.send(200, self.server.store.listing())
            if url.path == "/api/articles/campaign":
                path = HERE / "campaigns/five-cahiers.json"
                return self.send(200, json.loads(path.read_text()) if path.exists() else None)
            if url.path == "/api/articles/list":
                return self.send(200, self.server.articles().listing())
            if url.path == "/api/articles/document":
                return self.send(200, self.server.articles().document(q["id"][0]))
            if url.path == "/api/document":
                return self.send(
                    200,
                    self.server.store.document(
                        q["id"][0],
                        int(q.get("radius", ["6"])[0]),
                        q.get("start_id", [None])[0],
                        q.get("end_id", [None])[0],
                    ),
                )
            static = {
                "/": ("index.html", "text/html; charset=utf-8"),
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/articles.js": ("articles.js", "text/javascript; charset=utf-8"),
                "/style.css": ("style.css", "text/css; charset=utf-8"),
            }
            if url.path in static:
                name, kind = static[url.path]
                return self.send(200, (HERE / "static" / name).read_bytes(), kind)
            return self.send(404, {"error": "Not found"})
        except (ValueError, KeyError, IndexError) as e:
            return self.send(400, {"error": str(e)})
        except Exception:
            self.log_error("Read failed")
            return self.send(
                500, {"error": "Local source/journal read failed; see integrity controls"}
            )

    def do_POST(self):
        port = self.server.server_port
        if not self.allowed() or self.headers.get("Origin") not in {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }:
            return self.send(403, {"error": "Local origin required"})
        if not secrets.compare_digest(self.headers.get("X-Review-Token", ""), self.server.token):
            return self.send(403, {"error": "Review token required"})
        if self.path not in {
            "/api/decision",
            "/api/articles/decision",
            "/api/articles/preview",
            "/api/articles/export",
        }:
            return self.send(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 32768 or self.headers.get("Content-Type") != "application/json":
                return self.send(400, {"error": "Expected JSON, max 32 KiB"})
            payload = json.loads(self.rfile.read(length))
            if self.path == "/api/articles/preview":
                result = self.server.articles().preview(payload)
            elif self.path == "/api/articles/decision":
                result = self.server.articles().save(payload)
            elif self.path == "/api/articles/export":
                result = self.server.articles().write_export(self.server.article_export_directory)
            else:
                result = self.server.store.save_decision(payload)
            return self.send(200, result)
        except Conflict as e:
            return self.send(409, {"error": str(e)})
        except (ValueError, KeyError, TypeError) as e:
            return self.send(400, {"error": str(e)})
        except Exception:
            return self.send(500, {"error": "Journal write failed; do not discard local history"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=1789)
    parser.add_argument(
        "--article-journal",
        type=Path,
        help="Separate article journal; use a temporary path for tests",
    )
    parser.add_argument(
        "--journal",
        type=Path,
        help="Optional isolated decision journal; default .local/decisions.jsonl",
    )
    args = parser.parse_args()
    print("Loading existing registry and six local XML files...", flush=True)
    server = ReviewServer(args.port, Store(args.journal), args.article_journal)
    print(f"Review ready: http://127.0.0.1:{server.server_port} (Ctrl-C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
