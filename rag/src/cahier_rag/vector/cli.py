"""Recherche vectorielle locale exacte ; aucune exécution des requêtes réservées."""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from cahier_rag.__main__ import open_store
from cahier_rag.config import load_settings
from cahier_rag.embeddings.core import EmbeddingEngine
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.embeddings.transformers_backend import TransformersBackend
from cahier_rag.evaluation.files import load_queries
from cahier_rag.evaluation.sampling import digest
from cahier_rag.representations.repository import RepresentationRepository
from cahier_rag.search.lexical import CorpusScope
from cahier_rag.vector.cache import generate
from cahier_rag.vector.engine import VectorEngine
from cahier_rag.vector.pipeline import index
from cahier_rag.vector.preparation import TokenConfig, atomic_json, load_prepared, prepare
from cahier_rag.vector.store import VectorStore, recipe


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=Path("evaluation/local/rag007/corpus.json"))
    parser.add_argument("--env-file")
    parser.add_argument("--models", type=Path, default=Path("models"))
    parser.add_argument("--directory", type=Path, default=Path("evaluation/local/rag013/bge-B"))
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    parser.add_argument("--precision", choices=["float32", "bfloat16"], default="bfloat16")
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--budget", type=int, default=1024)
    prep.add_argument("--overlap", type=int, default=128)
    for name in ("encode", "index", "resume"):
        sub = commands.add_parser(name)
        sub.add_argument("--batch-size", type=int, default=8)
        sub.add_argument("--unit-batch", type=int, default=25)
        sub.add_argument("--stop-after", type=int)
    commands.add_parser("status")
    commands.add_parser("verify")
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--questionnaire-id", type=int)
    search.add_argument("--unit-type", choices=["open_answer", "other_text"])
    develop = commands.add_parser("development")
    develop.add_argument("--queries", type=Path, default=Path("evaluation/queries.json"))
    develop.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    backend = None
    try:
        scope = CorpusScope(json.loads(args.sample.read_text()))
        with open_store(load_settings(env_file=args.env_file)) as storage:
            if args.command == "prepare":
                backend = TransformersBackend(MODELS["bge-m3"], args.models)
                result = prepare(
                    RepresentationRepository(storage.guard.target, scope),
                    backend,
                    args.directory,
                    TokenConfig(args.budget, args.overlap),
                )
            else:
                manifest = load_prepared(args.directory, scope)
                store = VectorStore(
                    storage.guard, scope, recipe(manifest, precision=args.precision)
                )
                if args.command in {"encode", "index", "resume"}:
                    backend = TransformersBackend(
                        MODELS["bge-m3"], args.models, device=args.device, precision=args.precision
                    )
                    if args.command == "encode":
                        result = generate(
                            args.directory,
                            scope,
                            EmbeddingEngine(backend),
                            store.configuration,
                            batch_size=args.batch_size,
                            unit_batch=args.unit_batch,
                            stop_after=args.stop_after,
                        )
                    else:
                        result = index(
                            store,
                            EmbeddingEngine(backend),
                            args.directory,
                            batch_size=args.batch_size,
                            unit_batch=args.unit_batch,
                            stop_after=args.stop_after,
                        )
                    atomic_json(args.directory / "index-report.json", result)
                elif args.command == "status":
                    result = store.status()
                    result.pop("manifest")
                    result = {
                        k: v.isoformat() if hasattr(v, "isoformat") else v
                        for k, v in result.items()
                    }
                elif args.command == "verify":
                    result = store.verify(require_complete=True)
                else:
                    backend = TransformersBackend(
                        MODELS["bge-m3"], args.models, device=args.device, precision=args.precision
                    )
                    engine = VectorEngine(store, EmbeddingEngine(backend)).load()

                    def search_query(query, limit=10, **filters):
                        return engine.search(query, limit=limit, **filters)

                    if args.command == "search":
                        result = [
                            r.to_dict()
                            for r in search_query(
                                args.query,
                                args.limit,
                                questionnaire_id=args.questionnaire_id,
                                unit_type=args.unit_type,
                            )
                        ]
                    else:
                        args.output.mkdir(parents=True, exist_ok=False)
                        queries = [
                            q for q in load_queries(args.queries) if q["split"] == "development"
                        ]
                        rankings, measures, scored = {}, [], {}
                        for query in queries:
                            started = time.perf_counter()
                            found = search_query(query["text"])
                            elapsed = time.perf_counter() - started
                            rankings[query["query_id"]] = [r.document.document_id for r in found]
                            scored[query["query_id"]] = [
                                {"document_id": r.document.document_id, "score": r.score}
                                for r in found
                            ]
                            measures.append(
                                {
                                    "query_id": query["query_id"],
                                    "seconds": elapsed,
                                    **engine.last_timings,
                                    "results": len(found),
                                    "contributions": len(
                                        {r.document.contribution_id for r in found}
                                    ),
                                }
                            )
                        atomic_json(args.output / "rankings.json", rankings)
                        atomic_json(args.output / "scores.json", scored)
                        times = sorted(m["seconds"] for m in measures)
                        result = {
                            "space_id": store.space_id,
                            "split": "development",
                            "limit": 10,
                            "sample_hash": scope.sample_hash,
                            "queries_hash": digest(queries),
                            "measures": measures,
                            "median_seconds": statistics.median(times),
                            "p95_seconds": times[max(0, int(len(times) * 0.95) - 1)],
                            "queries_with_results": sum(m["results"] > 0 for m in measures),
                        }
                        atomic_json(args.output / "report.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, SQLAlchemyError, OSError, KeyError, ImportError):
        print(
            "Opération refusée ou indisponible ; vérifier configuration, pgvector, artefacts et ressources. Aucun secret ni texte journalisé.",
            file=sys.stderr,
        )
        return 1
    finally:
        if backend is not None:
            backend.close()


if __name__ == "__main__":
    raise SystemExit(main())
