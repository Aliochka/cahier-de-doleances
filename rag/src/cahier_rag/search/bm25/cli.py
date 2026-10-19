"""CLI BM25 locale ; aucun lancement des requêtes réservées."""

import argparse
import json
import resource
from pathlib import Path

from cahier_rag.annotation.session import atomic_json
from cahier_rag.config import load_settings
from cahier_rag.db import create_rag_engine
from cahier_rag.evaluation.files import load_queries
from cahier_rag.representations.repository import RepresentationRepository
from cahier_rag.search.bm25.experiments import compare, prepare_complement
from cahier_rag.search.bm25.index import BM25Index, Config
from cahier_rag.search.bm25.tokenizer import FrenchTokenizer
from cahier_rag.search.lexical import CorpusScope


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--directory", type=Path, default=Path("evaluation/local/rag018"))
    parser.add_argument("--env-file")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--stop-after", type=int)
    sub.add_parser("verify")
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--variant", choices=("A", "B"), default="A")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--questionnaire-id", type=int)
    search.add_argument("--unit-type", choices=("open_answer", "other_text"))
    development = sub.add_parser("development")
    development.add_argument("--output", type=Path, required=True)
    pool = sub.add_parser("pool")
    pool.add_argument("--experiment", type=Path, required=True)
    pool.add_argument("--output", type=Path, required=True)
    report = sub.add_parser("report")
    report.add_argument("--experiment", type=Path, required=True)
    report.add_argument("--plan", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    queries = load_queries(args.root / "evaluation/queries.json")
    scope = CorpusScope(json.loads((args.root / "evaluation/local/rag007/corpus.json").read_text()))
    if args.command == "report":
        from cahier_rag.search.bm25.evaluation import report_comparison

        report_comparison(args.root, args.experiment, args.plan, args.output, scope, queries)
        return 0
    engine = create_rag_engine(load_settings(env_file=args.env_file))
    indexes = {}
    try:
        repository = RepresentationRepository(engine, scope)
        if args.command == "pool":
            result = prepare_complement(
                args.root, args.output, repository, queries, args.experiment
            )
            print(json.dumps({"pairs": len(result["entries"]), "hash": result["manifest_hash"]}))
            return 0
        tokenizer = FrenchTokenizer(engine)
        for variant in ("A", "B"):
            indexes["bm25-" + variant] = BM25Index(
                args.directory / ("bm25-" + variant + ".sqlite3"),
                scope,
                tokenizer,
                Config(variant),
                writable=args.command == "build",
            )
        if args.command == "build":
            for name, index in indexes.items():
                result = index.build(repository, stop_after=args.stop_after)
                result["process_peak_rss_bytes"] = (
                    resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
                )
                try:
                    result["integrity"] = index.verify()
                except ValueError:
                    if args.stop_after is None:
                        raise
                    result["incomplete"] = True
                atomic_json(args.directory / (name + "-build.json"), result)
        elif args.command == "verify":
            print(json.dumps({k: v.verify() for k, v in indexes.items()}, indent=2))
        elif args.command == "development":
            compare(args.root, indexes, scope, queries, args.output)
        else:
            results = indexes["bm25-" + args.variant].search(
                args.query,
                limit=args.limit,
                questionnaire_id=args.questionnaire_id,
                unit_type=args.unit_type,
                split="development",
            )
            print(json.dumps([r.to_dict() for r in results], ensure_ascii=False))
    finally:
        for index in indexes.values():
            index.close()
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
