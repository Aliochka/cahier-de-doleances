"""Commandes lexicales locales, sans LLM ni API HTTP."""

import argparse
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from cahier_rag.__main__ import open_store
from cahier_rag.config import load_settings
from cahier_rag.contracts import UnitType, canonical_json
from cahier_rag.evaluation.cli import load_sample
from cahier_rag.evaluation.files import load_queries, write_json
from cahier_rag.search.evaluation import run_queries
from cahier_rag.search.lexical import CorpusScope, LexicalEngine, Strategy


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", default="evaluation/local/rag007/corpus.json")
    parser.add_argument("--env-file")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("rebuild")
    commands.add_parser("verify")
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--strategy", choices=list(Strategy), default=Strategy.ANSWER)
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--questionnaire-id", type=int)
    search.add_argument("--unit-type", choices=list(UnitType))
    search.add_argument(
        "--split", choices=["development", "evaluation", "all"], default="development"
    )
    search.add_argument(
        "--show-text",
        action="store_true",
        help="Afficher les documents complets, potentiellement personnels",
    )
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--queries", default="evaluation/queries.json")
    evaluate.add_argument("--split", choices=["development", "evaluation"], default="development")
    evaluate.add_argument("--strategy", choices=list(Strategy), default=Strategy.ANSWER)
    evaluate.add_argument("--limit", type=int, default=10)
    evaluate.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        scope = CorpusScope(load_sample(args.sample))
        with open_store(load_settings(env_file=args.env_file)) as store:
            engine = LexicalEngine(store.guard, scope)
            if args.command == "rebuild":
                print(canonical_json(engine.rebuild()))
            elif args.command == "verify":
                print(canonical_json(engine.validate()))
            elif args.command == "search":
                results = engine.search(
                    args.query,
                    strategy=args.strategy,
                    limit=args.limit,
                    questionnaire_id=args.questionnaire_id,
                    unit_type=args.unit_type,
                    split=None if args.split == "all" else args.split,
                )
                print(
                    canonical_json(
                        [
                            r.to_dict()
                            if args.show_text
                            else {"document_id": r.document.document_id, "score": r.score}
                            for r in results
                        ]
                    )
                )
            else:
                queries = load_queries(args.queries)
                directory = args.output_directory
                directory.mkdir(parents=True, exist_ok=True)
                paths = [
                    directory / name for name in ("results.json", "candidates.json", "report.json")
                ]
                if any(path.exists() for path in paths):
                    raise ValueError("Ne pas écraser une expérience existante.")
                values = run_queries(
                    engine, queries, strategy=args.strategy, split=args.split, limit=args.limit
                )
                for path, value in zip(paths, values):
                    write_json(path, value)
                print("Classements et candidats non jugés exportés ; aucune mesure de qualité.")
    except (ValueError, KeyError, TypeError, OSError, SQLAlchemyError):
        print(
            "Recherche refusée : vérifier manifeste, configuration et état de l’index.",
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        print("Opération interrompue.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
