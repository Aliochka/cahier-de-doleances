"""Loopback-only historical laboratory. Never mounted in the public application."""

import argparse
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import text

from .representations import JOIN, embed, gate, prepare_lexical, verify_representations
from .safety import Destination
from .search import HistoricalSearch
from .storage import SCOPE


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, body, content_type="application/json; charset=utf-8"):
        data = (
            json.dumps(body, ensure_ascii=False).encode()
            if content_type.startswith("application/json")
            else body
        )
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'",
        )
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in hosts or self.headers.get("Origin") not in {
            None,
            *[f"http://{h}" for h in hosts],
        }:
            return self.send(403, {"error": "Loopback origin required"})
        try:
            url = urlsplit(self.path)
            if url.path.startswith("/api/") and self.headers.get("Sec-Fetch-Site") == "cross-site":
                return self.send(403, {"error": "Same-site laboratory API required"})
            params = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path in {"/", "/document", "/lab.js", "/lab.css"}:
                name = {
                    "/": "lab.html",
                    "/document": "lab.html",
                    "/lab.js": "lab.js",
                    "/lab.css": "lab.css",
                }[url.path]
                mime = (
                    "text/javascript"
                    if name.endswith(".js")
                    else "text/css"
                    if name.endswith(".css")
                    else "text/html"
                )
                return self.send(
                    200,
                    (Path(__file__).parent / "static" / name).read_bytes(),
                    mime + "; charset=utf-8",
                )
            if url.path == "/api/search":
                result = self.server.search.search(
                    params.get("q", ""),
                    mode=params.get("mode", "hybrid"),
                    depth=int(params.get("depth", 50)),
                    volume=int(params["volume"]) if params.get("volume") else None,
                    estate=params.get("estate") or None,
                    place=params.get("place") or None,
                )
                return self.send(200, result)
            if url.path == "/api/document":
                with self.server.destination.transaction(readonly=True) as c:
                    gate(c)
                    # Full reading includes excluded units, but never non-candidate documents.
                    row = (
                        c.execute(
                            text(f"""SELECT d.document_id,d.display_title,d.full_text,d.warnings,
                        d.source_metadata->'metadata' AS metadata,d.provenance,
                        u.unit_id,u.start_offset,u.end_offset,u.searchable
                        FROM {JOIN} WHERE u.corpus_id=:corpus AND u.release_id=:release
                        AND d.candidate AND u.unit_id=:id"""),
                            dict(SCOPE, id=params.get("unit")),
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if row is None:
                        return self.send(404, {"error": "Unknown laboratory document/unit"})
                    # Slice Unicode on the server, never apply Python offsets to UTF-16 indices.
                    payload = dict(row)
                    full = payload.pop("full_text")
                    a, z = payload["start_offset"], payload["end_offset"]
                    payload.update(before=full[:a], highlight=full[a:z], after=full[z:])
                    return self.send(200, payload)
            return self.send(404, {"error": "Not found"})
        except ValueError as exc:
            return self.send(422, {"error": str(exc)})
        except RuntimeError as exc:
            return self.send(409, {"error": str(exc)})
        except Exception:
            return self.send(
                503,
                {
                    "error": "Historical laboratory unavailable; check its preparation and local database"
                },
            )


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "action",
        choices=["lexical", "embed", "verify", "search", "serve", "benchmark", "cold-benchmark"],
    )
    p.add_argument("--url", required=True)
    p.add_argument("--expected-data-directory", required=True)
    p.add_argument("--expected-system-id", required=True)
    p.add_argument("--precision", choices=["bfloat16", "float32"], default="bfloat16")
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--shard", type=int, default=None)
    p.add_argument("--port", type=int, default=1791)
    p.add_argument("--query", default="Agen agriculture")
    p.add_argument("--mode", choices=["lexical", "vector", "hybrid", "compare"], default="hybrid")
    p.add_argument("--depth", type=int, choices=[50, 100, 200], default=50)
    p.add_argument(
        "--output", type=Path, default=Path("1789/data/private/documentary/phase2-benchmark.json")
    )
    p.add_argument("--repeats", type=int, default=3)
    return p


def encode_worker(options, shard):
    destination = Destination(
        options.url, options.expected_data_directory, options.expected_system_id
    )
    try:
        return embed(
            destination,
            threads=options.threads,
            batch_size=options.batch_size,
            precision=options.precision,
            workers=options.workers,
            shard=shard,
        )
    finally:
        destination.close()


def main():
    args = parser().parse_args()
    destination = Destination(args.url, args.expected_data_directory, args.expected_system_id)
    service = None
    try:
        if args.action == "lexical":
            result = prepare_lexical(destination)
        elif args.action == "embed":
            if not 1 <= args.workers <= 8:
                raise ValueError("Workers must be between 1 and 8")
            if args.shard is not None:
                result = encode_worker(args, args.shard)
            else:
                with ProcessPoolExecutor(
                    max_workers=args.workers, mp_context=multiprocessing.get_context("spawn")
                ) as pool:
                    futures = [
                        pool.submit(encode_worker, args, index) for index in range(args.workers)
                    ]
                    result = [future.result() for future in futures]
        elif args.action == "verify":
            result = verify_representations(destination)
        elif args.action == "cold-benchmark":
            from .cold_benchmark import benchmark_clone

            result = benchmark_clone(
                destination, args.output.with_name("phase2-cold-postgres.json")
            )
        else:
            service = HistoricalSearch(destination, encoder_threads=args.threads)
            if args.action == "search":
                result = service.search(args.query, mode=args.mode, depth=args.depth)
            elif args.action == "benchmark":
                from .evaluation import benchmark

                result = benchmark(service, args.output, repeats=args.repeats)
            else:
                if not 1024 <= args.port <= 65535:
                    raise ValueError("Invalid local port")
                verify_representations(destination)
                server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
                server.search, server.destination = service, destination
                print(
                    f"Historical laboratory: http://127.0.0.1:{args.port} (unpublished local release)",
                    flush=True,
                )
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
                finally:
                    server.server_close()
                return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        message = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__
        print(json.dumps({"error": message}, ensure_ascii=False))
        return 1
    finally:
        if service:
            service.close()
        destination.close()


if __name__ == "__main__":
    raise SystemExit(main())
