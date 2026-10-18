"""Recherche et comparaisons RRF locales, CLI exclusivement développement."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from cahier_rag.__main__ import open_store
from cahier_rag.config import load_settings
from cahier_rag.embeddings.core import EmbeddingEngine
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.embeddings.transformers_backend import TransformersBackend
from cahier_rag.evaluation.files import load_queries
from cahier_rag.evaluation.sampling import digest
from cahier_rag.search.flexible import FlexibleEngine
from cahier_rag.search.hybrid.core import HybridConfig, HybridEngine
from cahier_rag.search.hybrid.experiments import compare
from cahier_rag.search.hybrid.integrity import verify_frozen
from cahier_rag.search.hybrid.pooling import prepare_pool
from cahier_rag.search.lexical import CorpusScope
from cahier_rag.vector.engine import VectorEngine
from cahier_rag.vector.preparation import atomic_json, load_prepared
from cahier_rag.vector.store import VectorStore, recipe


def load_bundle(directory):
    return {
        key: json.loads((directory / (key + ".json")).read_text())
        for key in ("report", "rankings", "runs", "diagnostics", "documents")
    }


def previous_pairs(pool_path, manifest_path, scope, queries):
    # Ces fichiers sont les candidats non annotés RAG-009, jamais la session RAG-010.
    rows = json.loads(pool_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    if (
        digest(rows) != manifest["pool_hash"]
        or len(rows) != manifest["candidate_count"]
        or manifest["sample_hash"] != scope.sample_hash
        or manifest["queries_hash"] != digest(queries)
        or manifest["split"] != "development"
    ):
        raise ValueError("Pool antérieur incompatible.")
    allowed_queries = {q["query_id"] for q in queries if q["split"] == "development"}
    pairs = set()
    for row in rows:
        qid, did = row["query_id"], row["document_id"]
        if (
            qid not in allowed_queries
            or did not in scope.documents
            or scope.documents[did]["split"] != "development"
        ):
            raise ValueError("Ancien candidat hors périmètre.")
        if (qid, did) in pairs:
            raise ValueError("Ancien pool contenant des doublons.")
        pairs.add((qid, did))
    return pairs


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=Path("evaluation/local/rag007/corpus.json"))
    parser.add_argument("--frozen", type=Path, default=Path("evaluation/local/rag009/frozen.json"))
    parser.add_argument("--queries", type=Path, default=Path("evaluation/queries.json"))
    parser.add_argument(
        "--vector-directory", type=Path, default=Path("evaluation/local/rag013/bge-B")
    )
    parser.add_argument("--models", type=Path, default=Path("models"))
    parser.add_argument("--env-file")
    parser.add_argument("--depth", type=int, default=50)
    parser.add_argument("--k", type=int, default=60)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--questionnaire-id", type=int)
    parser.add_argument("--unit-type", choices=["open_answer", "other_text"])
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search")
    search.add_argument("query")
    development = sub.add_parser("development")
    development.add_argument("--output", type=Path, required=True)
    pool = sub.add_parser("pool")
    pool.add_argument("--experiment", type=Path, required=True)
    pool.add_argument("--output", type=Path, required=True)
    pool.add_argument(
        "--previous-pool", type=Path, default=Path("evaluation/local/rag009/annotations/pool.json")
    )
    pool.add_argument(
        "--previous-manifest",
        type=Path,
        default=Path("evaluation/local/rag009/annotations/manifest.json"),
    )
    pool.add_argument("--per-query", type=int, default=20)
    pool.add_argument("--seed", type=int, default=20261021)
    args = parser.parse_args(argv)
    backend = None
    try:
        config = HybridConfig(args.k, args.depth)
        if type(args.limit) is not int or not 1 <= args.limit <= config.depth:
            raise ValueError("Limite incompatible avec la profondeur.")
        scope = CorpusScope(json.loads(args.sample.read_text()))
        queries = load_queries(args.queries)
        frozen = verify_frozen(args.frozen, scope, queries)
        if args.command == "pool":
            bundle = load_bundle(args.experiment)
            expected_queries = {q["query_id"] for q in queries if q["split"] == "development"}
            if set(bundle["runs"]["lexical"]) != expected_queries or bundle["report"][
                "queries_hash"
            ] != digest([q for q in queries if q["split"] == "development"]):
                raise ValueError("Jeu de requêtes de développement incompatible.")
            pairs = previous_pairs(args.previous_pool, args.previous_manifest, scope, queries)
            rows, manifest = prepare_pool(
                bundle, scope, pairs, per_query=args.per_query, seed=args.seed
            )
            manifest["implementation_hashes"] = {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in Path(__file__).parent.glob("*.py")
            }
            args.output.mkdir(parents=True, exist_ok=False)
            atomic_json(args.output / "pool.json", rows)
            atomic_json(args.output / "manifest.json", manifest)
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0
        if args.command == "development" and args.output.exists():
            raise ValueError("Dossier de sortie déjà existant.")
        with open_store(load_settings(env_file=args.env_file)) as storage:
            lexical = FlexibleEngine(storage.guard, scope)
            verified = lexical.validate()
            if verified["configuration"] != frozen["index_configuration"]:
                raise ValueError("Configuration de l'index lexical différente du gel.")
            prepared = load_prepared(args.vector_directory, scope)
            vector_store = VectorStore(storage.guard, scope, recipe(prepared))
            baseline = json.loads((args.vector_directory / "index-report.json").read_text())
            if vector_store.space_id != baseline["space_id"] or not baseline["complete"]:
                raise ValueError("Espace RAG-013 incompatible.")
            backend = TransformersBackend(
                MODELS["bge-m3"], args.models, device="cuda", precision="bfloat16"
            )
            vector = VectorEngine(vector_store, EmbeddingEngine(backend)).load()
            engine = HybridEngine(lexical, vector, scope, config)
            filters = dict(questionnaire_id=args.questionnaire_id, unit_type=args.unit_type)
            if args.command == "search":
                results = engine.search(args.query, limit=args.limit, **filters)
                print(
                    json.dumps(
                        {
                            "results": [r.to_dict() for r in results],
                            "contributions": {
                                r.document.document_id: engine.last_retrieval.traces[
                                    r.document.document_id
                                ]
                                for r in results
                            },
                            "measurements": engine.last_retrieval.measurements,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                bundle = compare(engine, queries, limit=args.limit, **filters)
                bundle["report"]["baselines"] = {
                    "lexical_frozen_hash": frozen["frozen_hash"],
                    "vector_space_id": vector_store.space_id,
                    "vector_hash": baseline["vectors_hash"],
                }
                bundle["report"]["implementation_hashes"] = {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in Path(__file__).parent.glob("*.py")
                }
                args.output.mkdir(parents=True, exist_ok=False)
                for key, value in bundle.items():
                    atomic_json(args.output / (key + ".json"), value)
                for method, ranking in bundle["rankings"].items():
                    atomic_json(args.output / (method + "-rankings.json"), ranking)
                print(
                    json.dumps(
                        {
                            key: bundle["report"][key]
                            for key in ("methods", "latency_ms", "configuration")
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
        return 0
    except (ValueError, KeyError, TypeError, OSError, ImportError, SQLAlchemyError):
        print(
            "Recherche hybride refusée : vérifier configuration, manifestes et ressources locales. Aucun texte ni secret journalisé.",
            file=sys.stderr,
        )
        return 1
    finally:
        if backend is not None:
            backend.close()


if __name__ == "__main__":
    raise SystemExit(main())
