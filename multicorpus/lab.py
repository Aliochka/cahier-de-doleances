"""Loopback multicorpus CLI/server. Not imported by any public application."""

import argparse
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from cahier_rag.embeddings.core import EmbeddingEngine
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.embeddings.transformers_backend import TransformersBackend
from cahier_rag.search.service.control import Budget, SearchBusy, SearchError, SearchTimeout
from cahier_rag.search.service.core import HybridSearch

from documentary.lab import Handler as HistoricalHandler
from documentary.representations import MODELS as MODEL_DIRECTORY
from documentary.safety import Destination

from .adapters import DocumentaryAdapter, GdnAdapter
from .core import MultiSearch
from .environment import hydration_engine, local_reader


class Handler(HistoricalHandler):
    def do_GET(self):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if self.headers.get("Host") not in hosts or self.headers.get("Origin") not in {
            None,
            *[f"http://{h}" for h in hosts],
        }:
            return self.send(403, {"error": "Loopback origin required"})
        url = urlsplit(self.path)
        if url.path.startswith("/api/") and self.headers.get("Sec-Fetch-Site") == "cross-site":
            return self.send(403, {"error": "Same-site laboratory API required"})
        if url.path == "/api/document":
            return super().do_GET()
        try:
            params = {k: v[0] for k, v in parse_qs(url.query).items()}
            if url.path in {"/", "/document", "/2019/answer", "/multi.js", "/lab.css"}:
                if url.path == "/lab.css":
                    return super().do_GET()
                name = "multi.js" if url.path.endswith(".js") else "multi.html"
                return self.send(
                    200,
                    (Path(__file__).parent / "static" / name).read_bytes(),
                    "text/javascript; charset=utf-8"
                    if name.endswith(".js")
                    else "text/html; charset=utf-8",
                )
            if url.path == "/api/search":
                if set(params) - {
                    "q",
                    "corpus",
                    "mode",
                    "depth",
                    "question",
                    "volume",
                    "estate",
                    "place",
                }:
                    raise ValueError("Unknown laboratory search parameter")
                return self.send(
                    200,
                    self.server.search.search(
                        params.get("q", ""),
                        corpus=params.get("corpus", "tous"),
                        mode=params.get("mode", "hybrid"),
                        depth=int(params.get("depth", 50)),
                        question=int(params["question"]) if params.get("question") else None,
                        volume=int(params["volume"]) if params.get("volume") else None,
                        estate=params.get("estate") or None,
                        place=params.get("place") or None,
                    ),
                )
            if url.path == "/api/answer":
                budget = Budget(3)
                with budget.monitor():
                    payload = self.server.search.adapters["2019"].answer(
                        params.get("id", ""), budget
                    )
                return self.send(200, payload)
            if url.path == "/api/h1":
                # Separate reference experiment, actual unchanged H1 and its own deadline.
                if not self.server.search.lock.acquire(blocking=False):
                    raise SearchBusy("Laboratory busy")
                try:
                    result = self.server.search.h1.retrieve(params.get("q", ""))
                    return self.send(
                        200,
                        dict(
                            recipe=result.recipe_version,
                            generation=result.generation,
                            timings=result.timings.__dict__,
                            items=[
                                dict(
                                    answer_id=str(h.document.answer_id),
                                    unit_id=h.document.document_id,
                                    contribution_id=str(h.document.contribution_id),
                                    title=h.document.question_text,
                                    excerpt=h.document.text[:850],
                                    lexical_rank=h.lexical_rank,
                                    vector_rank=h.vector_rank,
                                    score=h.rrf_score,
                                )
                                for h in result.hits
                            ],
                            laboratory_only=True,
                        ),
                    )
                finally:
                    self.server.search.lock.release()
            return self.send(404, {"error": "Unknown laboratory resource"})
        except ValueError as exc:
            return self.send(422, {"error": str(exc)})
        except SearchBusy as exc:
            return self.send(409, {"error": str(exc)})
        except SearchTimeout as exc:
            return self.send(504, {"error": str(exc)})
        except Exception:
            return self.send(503, {"error": "Local multicorpus laboratory unavailable"})


def build(args):
    expected = json.loads(Path(args.identities).read_text())
    reader = local_reader(args.gdn_env, expected)
    source = hydration_engine(args.hydration_url, expected["source"])
    destination = Destination(args.url, args.expected_data_directory, args.expected_system_id)
    historical = DocumentaryAdapter(destination)
    encoder = EmbeddingEngine(
        TransformersBackend(
            MODELS["bge-m3"], MODEL_DIRECTORY, device="cpu", precision="float32", threads=4
        )
    )
    h1 = HybridSearch(reader, encoder)
    try:
        h1.start()
        # Check both stores against the exact same revision/snapshot, different documented precision.
        identity = historical.identity(Budget(10))
        if (
            identity["embedding_recipe"]["model"] != MODELS["bge-m3"].to_dict()
            or identity["embedding_recipe"]["snapshot_hash"] != encoder.backend.snapshot_hash
        ):
            raise ValueError("Historical and shared query model identities differ")
        return MultiSearch([GdnAdapter(reader, source), historical], encoder, h1=h1), destination
    except Exception:
        h1.close()
        source.dispose()
        destination.close()
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["serve", "search", "benchmark", "verify"])
    p.add_argument("--gdn-env", required=True)
    p.add_argument("--hydration-url", required=True)
    p.add_argument(
        "--identities",
        required=True,
        help="Explicit expected source/target physical identities JSON",
    )
    p.add_argument("--url", required=True)
    p.add_argument("--expected-data-directory", required=True)
    p.add_argument("--expected-system-id", required=True)
    p.add_argument("--port", type=int, default=1792)
    p.add_argument("--query", default="Suppression des privilèges")
    p.add_argument("--corpus", choices=["2019", "1789", "tous"], default="tous")
    p.add_argument("--mode", choices=["lexical", "vector", "hybrid", "compare"], default="compare")
    p.add_argument("--depth", type=int, choices=[50, 100, 200], default=50)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--output", type=Path, default=Path("private/search/phase3/results.json"))
    args = p.parse_args()
    service = destination = None
    try:
        service, destination = build(args)
        if args.action == "serve":
            if not 1024 <= args.port <= 65535:
                raise ValueError("Invalid laboratory port")
            server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
            server.search, server.destination = service, destination
            print(f"Multicorpus laboratory http://127.0.0.1:{args.port}/", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return
        if args.action == "search":
            result = service.search(
                args.query, corpus=args.corpus, mode=args.mode, depth=args.depth
            )
        elif args.action == "benchmark":
            from .evaluation import benchmark

            result = benchmark(service, args.output, resume=args.resume)
        else:
            result = {k: a.identity(Budget(10)) for k, a in service.adapters.items()}
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    finally:
        if service:
            service.h1.close()
        if service:
            service.adapters["2019"].source.dispose()
        if destination:
            destination.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # No URL, SQL parameters, role credentials or raw source in CLI errors.
        message = str(exc) if isinstance(exc, (ValueError, SearchError)) else type(exc).__name__
        print(json.dumps({"error": message}), flush=True)
        raise SystemExit(1) from None
