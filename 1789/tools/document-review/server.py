"""Loopback-only review server, no application/database dependencies."""

import argparse
import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from reviewlib import HERE, Conflict, Store, sha


class ReviewServer(HTTPServer):
    def __init__(
        self,
        port,
        store,
        article_journal=None,
        article_export_directory=None,
        corpus_directory="auto",
        override_directory=None,
    ):
        self.store = store
        self.corpus_directory = corpus_directory
        self.override_directory = override_directory
        self._inventory = None
        self._documentary_review = None
        self.article_journal = article_journal
        self.article_export_directory = (
            article_export_directory or HERE.parents[1] / "data/review-exports"
        )
        self._articles = None
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)

    def articles(self):
        if self._articles is None:
            from articles import INPUT, Articles
            from collection import discover

            directory = discover() if self.corpus_directory == "auto" else self.corpus_directory
            from reviewlib import rows

            resolutions = (directory / "boundary-resolutions.jsonl.gz") if directory else None
            if resolutions and resolutions.exists():
                self.store.automatic_corrections = {r["document_id"]: r for r in rows(resolutions)}
            self._articles = Articles(
                self.store,
                self.article_journal,
                directory=directory or INPUT,
                override_directory=self.override_directory,
            )
        return self._articles

    def corpus_info(self):
        engine = self.articles()
        path = engine.directory / "summary.json"
        if not (engine.directory / "complete.json").exists():
            return dict(available=False)
        return dict(
            available=True, summary=json.loads(path.read_text()), directory=engine.directory.name
        )

    def inventory(self):
        if self._inventory is None:
            from reviewlib import rows

            path = self.articles().directory / "inventory.jsonl.gz"
            self._inventory = {r["id"]: r for r in rows(path)} if path.exists() else {}
        return self._inventory

    def documentary_review(self):
        if self._documentary_review is None:
            from reviewlib import rows

            path = self.articles().directory / "documentary-review.jsonl.gz"
            self._documentary_review = (
                {r["document_id"]: r for r in rows(path)} if path.exists() else {}
            )
            snapshot = self.articles().directory / ".private/decisions.jsonl"
            self._generation_parent_events = (
                {r["document_id"]: r["id"] for r in rows(snapshot)} if snapshot.exists() else {}
            )
        return self._documentary_review

    def review_for(self, key, state=None):
        review = self.documentary_review().get(key)
        if not review:
            return None
        state = state or self.store.state(self.store.by_id[key])
        event = state.get("event") or {}
        if (
            state["status"] == "human_validated"
            and not state["stale"]
            and event.get("id") != self._generation_parent_events.get(key)
        ):
            return dict(
                review,
                generation_priority=review["priority"],
                priority="none",
                mandatory_review=False,
                reasons=["human_boundary_validated_since_generation"],
            )
        return review


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
                    200,
                    dict(
                        token=self.server.token,
                        stats=self.server.store.stats(),
                        corpus=self.server.corpus_info(),
                    ),
                )
            if url.path == "/api/list":
                listing = self.server.store.listing()
                inventory = self.server.inventory()
                latest = self.server.store.latest()
                for row in listing:
                    item = inventory.get(row["id"], {})
                    row.update(
                        extraction_state=item.get("extraction_state"),
                        boundary_class="human_validated"
                        if row["status"] == "human_validated"
                        else item.get("boundary_class"),
                        document_kind=item.get("document_kind"),
                        extracted=row["id"] in self.server.articles().parents,
                        documentary_review=self.server.review_for(
                            row["id"],
                            self.server.store.state(self.server.store.by_id[row["id"]], latest),
                        ),
                    )
                return self.send(200, listing)
            if url.path == "/api/corpus/unresolved":
                parents = self.server.articles().parents
                return self.send(
                    200,
                    [
                        {
                            k: r[k]
                            for k in [
                                "id",
                                "persee_id",
                                "title",
                                "volume",
                                "extraction_state",
                                "document_kind",
                                "anomalies",
                            ]
                        }
                        for r in self.server.inventory().values()
                        if r["id"] not in parents
                    ],
                )
            if url.path == "/api/volume/search":
                volume = int(q["volume"][0])
                query = q.get("query", [""])[0].casefold().strip()
                if volume not in self.server.store.blocks or len(query) < 3:
                    return self.send(
                        400, {"error": "Volume valide et au moins trois caractères requis."}
                    )
                hits = [
                    b for b in self.server.store.blocks[volume] if query in b["text"].casefold()
                ]
                return self.send(200, dict(total=len(hits), blocks=hits[:50]))
            if url.path == "/api/corpus/summary":
                return self.send(200, self.server.corpus_info())
            if url.path == "/api/boundary-campaign":
                path = HERE / "campaigns/twelve-boundaries.json"
                if not path.exists():
                    return self.send(200, None)
                campaign = json.loads(path.read_text())
                active = self.server.articles().directory.resolve()
                campaign["matches_active_generation"] = (
                    sha((active / "parents.jsonl.gz").read_bytes()) == campaign["parents_sha256"]
                )
                decisions = json.loads(
                    (HERE.parents[1] / "extraction/documentary-finalization.json").read_text()
                )
                campaign["blockers"] = decisions["blockers"]
                return self.send(200, campaign)
            if url.path == "/api/articles/workbench":
                path = self.server.articles().directory / "article-workbench.json"
                if not path.exists():
                    return self.send(200, None)
                workbench = json.loads(path.read_text())
                windows = (
                    workbench["independent_sample"]
                    + workbench["examples"]
                    + workbench.get("fusion_validation", [])
                )
                progress = self.server.articles().workbench_progress(windows)
                for window in windows:
                    window["review"] = progress[window["id"]]
                return self.send(200, workbench)
            if url.path == "/api/articles/campaign":
                path = HERE / "campaigns/five-cahiers.json"
                return self.send(200, json.loads(path.read_text()) if path.exists() else None)
            if url.path == "/api/articles/list":
                return self.send(200, self.server.articles().listing())
            if url.path == "/api/articles/document":
                return self.send(200, self.server.articles().document(q["id"][0]))
            if url.path == "/api/document":
                self.server.articles()  # Install active documentary proposals before displaying boundaries.
                doc = self.server.store.document(
                    q["id"][0],
                    int(q.get("radius", ["6"])[0]),
                    q.get("start_id", [None])[0],
                    q.get("end_id", [None])[0],
                )
                resolution = self.server.store.automatic_corrections.get(q["id"][0])
                if resolution:
                    from boundary_rules import effective

                    doc["record"] = effective(doc["record"], resolution)
                    doc["documentary_resolution"] = resolution
                doc["documentary_review"] = self.server.review_for(q["id"][0], doc["state"])
                return self.send(200, doc)
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
            "/api/articles/rebuild",
        }:
            return self.send(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 32768 or self.headers.get("Content-Type") != "application/json":
                return self.send(400, {"error": "Expected JSON, max 32 KiB"})
            payload = json.loads(self.rfile.read(length))
            if self.path == "/api/articles/rebuild":
                from collection import rebuild

                return self.send(
                    200,
                    rebuild(
                        self.server.store,
                        self.server.articles(),
                        payload["document_id"],
                        payload.get("parent_event_id"),
                    ),
                )
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
        help="Optional isolated decision journal; default 1789/data/private/document-review/decisions.jsonl",
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
