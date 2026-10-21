"""Opt-in H1 CPU benchmark; no recipe changes, writes only a new result file.

Never run during preparation. No model downloads. No citizen/query text in output.
"""

import argparse
import asyncio
import hashlib
import json
import math
import os
import resource
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def summary(rows, elapsed):
    times = sorted(row["seconds"] for row in rows if row["status"] == 200)

    def percentile(p):
        return times[math.ceil(p * len(times)) - 1] if times else None

    return {
        "requests": len(rows),
        "status_counts": dict(Counter(str(r["status"]) for r in rows)),
        "success_p50_seconds": percentile(0.50),
        "success_p95_seconds": percentile(0.95),
        "error_rate": 1 - len(times) / len(rows) if rows else 0,
        "success_requests_per_second": len(times) / elapsed if elapsed else 0,
        "elapsed_seconds": elapsed,
    }


def queries(path):
    payload = json.loads(Path(path).read_text())
    rows = payload["queries"]
    if any(r.get("split") == "evaluation" or not 1 <= len(r["text"]) <= 512 for r in rows):
        raise ValueError("Jeu réservé ou requête hors contrat public.")
    return rows


async def http_run(args, cases):
    import httpx

    parsed = urlsplit(args.base_url)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or parsed.query:
        raise ValueError("Origine HTTP(S) sans secret requise.")
    if not args.allow_remote and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Mesure distante à autoriser explicitement.")
    semaphore = asyncio.Semaphore(args.users)
    rows = []
    probes = []
    finished = asyncio.Event()
    async with httpx.AsyncClient(
        base_url=args.base_url, timeout=25, follow_redirects=True
    ) as client:

        async def one(case):
            async with semaphore:
                started = time.monotonic()
                try:
                    response = await client.get(args.path, params={"q": case["text"]})
                    status = response.status_code
                    code = None
                    if args.path == "/api/v1/search" and status != 200:
                        code = response.json().get("error", {}).get("code")
                except Exception:
                    status, code = "transport_error", None
                rows.append(
                    {
                        "query_id": case["query_id"],
                        "seconds": time.monotonic() - started,
                        "status": status,
                        "code": code,
                    }
                )

        async def probe():
            while not finished.is_set():
                for path in ("/api/v1/forms", args.statistics_path):
                    started = time.monotonic()
                    try:
                        status = (await client.get(path)).status_code
                    except Exception:
                        status = "transport_error"
                    probes.append(
                        {"path": path, "seconds": time.monotonic() - started, "status": status}
                    )
                try:
                    await asyncio.wait_for(finished.wait(), timeout=1)
                except TimeoutError:
                    pass

        task = asyncio.create_task(probe())
        started = time.monotonic()
        try:
            await asyncio.gather(*(one(case) for _ in range(args.repeats) for case in cases))
        finally:
            finished.set()
            await task
    elapsed = time.monotonic() - started
    return {
        "summary": summary(rows, elapsed),
        "requests": rows,
        "site_probes": probes,
        "site_summary": summary(probes, elapsed),
        "site_by_path": {
            path: summary([probe for probe in probes if probe["path"] == path], elapsed)
            for path in {probe["path"] for probe in probes}
        },
    }


def local_run(args, cases):
    import psutil

    process = psutil.Process()
    rows = []
    started = time.monotonic()
    if args.mode == "encoding":
        from cahier_rag.embeddings.core import EmbeddingEngine, EmbeddingInput
        from cahier_rag.embeddings.registry import MODELS
        from cahier_rag.embeddings.transformers_backend import TransformersBackend

        engine = EmbeddingEngine(
            TransformersBackend(
                MODELS["bge-m3"],
                Path(args.models),
                device="cpu",
                precision="float32",
                threads=args.threads,
            )
        )
        try:
            engine.load()
            if engine.backend.torch.version.cuda is not None:
                raise ValueError("Distribution CPU requise.")
            load_seconds = time.monotonic() - started
            next(engine.encode_queries([EmbeddingInput("warmup", "Transports publics", "warmup")]))
            started = time.monotonic()
            for _ in range(args.repeats):
                for case in cases:
                    before = time.monotonic()
                    next(
                        engine.encode_queries(
                            [EmbeddingInput(case["query_id"], case["text"], "benchmark")]
                        )
                    )
                    rows.append(
                        {
                            "query_id": case["query_id"],
                            "seconds": time.monotonic() - before,
                            "status": 200,
                        }
                    )
        finally:
            engine.close()
    else:
        from app.hybrid_runtime import build_backend

        os.environ["SEARCH_CPU_THREADS"] = str(args.threads)
        backend = build_backend()
        try:
            if backend.worker.service.encoder.backend.device != "cpu":
                raise ValueError("CPU requis.")
            backend.verify_source()
            backend.worker.service.start()
            load_seconds = time.monotonic() - started
            started = time.monotonic()
            for _ in range(args.repeats):
                for case in cases:
                    before = time.monotonic()
                    try:
                        ranking = backend.worker.service.retrieve(case["text"])
                        timing, status = asdict(ranking.timings), 200
                    except Exception as error:
                        timing, status = {}, getattr(error, "code", "search_error")
                    rows.append(
                        {
                            "query_id": case["query_id"],
                            "seconds": time.monotonic() - before,
                            "status": status,
                            "components": timing,
                        }
                    )
        finally:
            asyncio.run(backend.close())
    elapsed = time.monotonic() - started
    return {
        "summary": summary(rows, elapsed),
        "requests": rows,
        "load_seconds": load_seconds,
        "rss_final_bytes": process.memory_info().rss,
        "rss_peak_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--mode", choices=("encoding", "components", "http"), required=True)
    parser.add_argument("--queries", default="rag/evaluation/performance-rag027.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--repeats", type=int, choices=range(1, 21), default=10)
    parser.add_argument("--users", type=int, choices=(1, 5, 20), default=1)
    parser.add_argument("--threads", type=int, choices=(1, 2, 4), default=2)
    parser.add_argument("--models", default="/models")
    parser.add_argument("--base-url", default="http://127.0.0.1:8015")
    parser.add_argument("--allow-remote", action="store_true")
    parser.add_argument(
        "--path", choices=("/api/v1/search", "/recherche"), default="/api/v1/search"
    )
    parser.add_argument("--statistics-path", default="/api/v1/forms/4/stats")
    parser.add_argument(
        "--cache-state",
        required=True,
        choices=("model-cold", "warm", "postgres-cold-os-warm", "all-cold"),
    )
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("Exécution de benchmark non autorisée sans --execute.")
    if Path(args.output).exists():
        parser.error("Fichier de résultat déjà présent.")
    try:
        cases = queries(args.queries)
        result = (
            asyncio.run(http_run(args, cases)) if args.mode == "http" else local_run(args, cases)
        )
        result.update(
            mode=args.mode,
            users=args.users,
            cache_state=args.cache_state,
            threads=args.threads,
            queries_sha256=hashlib.sha256(Path(args.queries).read_bytes()).hexdigest(),
        )
        from app.search_admin import exclusive_json

        exclusive_json(args.output, result)
        print(json.dumps(result["summary"]))
        return 0
    except Exception:
        print('{"status":"failed","code":"benchmark_failed"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
