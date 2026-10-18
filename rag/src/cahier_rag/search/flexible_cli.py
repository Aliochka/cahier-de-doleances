"""CLI RAG-009 ; réglages exclusivement développement, évaluation réclamée une fois."""

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from cahier_rag.__main__ import open_store
from cahier_rag.config import load_settings
from cahier_rag.contracts import canonical_json
from cahier_rag.evaluation.cli import load_sample
from cahier_rag.evaluation.files import load_json, load_queries, write_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.search.experiments import EXPERIMENTS, run_experiment
from cahier_rag.search.flexible import FlexibleEngine, Method, configuration
from cahier_rag.search.lexical import CorpusScope, Strategy
from cahier_rag.search.preparation import Preparation


def implementation_hashes():
    directory = Path(__file__).parent
    return {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in (
            "lexical.py",
            "preparation.py",
            "flexible.py",
            "experiments.py",
            "flexible_cli.py",
        )
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", default="evaluation/local/rag007/corpus.json")
    parser.add_argument("--env-file")
    parser.add_argument("--queries", default="evaluation/queries.json")
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--method", choices=list(Method), default=Method.WEIGHTED)
    search.add_argument("--representation", choices=list(Strategy), default=Strategy.ANSWER)
    search.add_argument("--keep-generic", action="store_true")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--questionnaire-id", type=int)
    search.add_argument("--unit-type", choices=["open_answer", "other_text"])
    compare = commands.add_parser("compare")
    compare.add_argument("--output-directory", type=Path, required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--experiment-directory", type=Path, required=True)
    freeze.add_argument("--reason", required=True)
    freeze.add_argument("--output", type=Path, required=True)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--frozen", type=Path, required=True)
    evaluate.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        sample = load_sample(args.sample)
        scope = CorpusScope(sample)
        queries = load_queries(args.queries)
        if args.command == "freeze":
            report = load_json(args.experiment_directory / "report.json")
            if (
                report["split"] != "development"
                or report["sample_hash"] != scope.sample_hash
                or report["queries_hash"] != digest(queries)
            ):
                raise ValueError("Expérience de développement compatible requise.")
            frozen = {
                "implementation_hashes": implementation_hashes(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "configuration": report["configuration"],
                "sample_hash": scope.sample_hash,
                "queries_hash": digest(queries),
                "limit": report["limit"],
                "reason": args.reason,
                "development_report_hash": digest(report),
                "index_configuration": report["index_configuration"],
            }
            frozen["frozen_hash"] = digest(frozen)
            write_json(args.output, frozen)
            return 0
        with open_store(load_settings(env_file=args.env_file)) as store:
            engine = FlexibleEngine(store.guard, scope)
            if args.command == "search":
                results = engine.search(
                    args.query,
                    method=args.method,
                    strategy=args.representation,
                    preparation=Preparation(remove_generic=not args.keep_generic),
                    limit=args.limit,
                    questionnaire_id=args.questionnaire_id,
                    unit_type=args.unit_type,
                    split="development",
                )
                print(
                    canonical_json(
                        [{"document_id": r.document.document_id, "score": r.score} for r in results]
                    )
                )
            elif args.command == "compare":
                args.output_directory.mkdir(parents=True, exist_ok=False)
                for name, method, strategy in EXPERIMENTS:
                    directory = args.output_directory / name
                    directory.mkdir()
                    ranks, report = run_experiment(
                        engine, queries, method=method, strategy=strategy
                    )
                    write_json(directory / "results.json", ranks)
                    write_json(directory / "report.json", report)
                    print(name, report["summary"], flush=True)
            else:
                frozen = load_json(args.frozen)
                expected = dict(frozen)
                saved_hash = expected.pop("frozen_hash")
                cfg = frozen["configuration"]
                prep = (
                    Preparation(remove_generic=cfg["preparation"]["remove_generic"])
                    if cfg["preparation"]
                    else Preparation()
                )
                if (
                    digest(expected) != saved_hash
                    or frozen["implementation_hashes"] != implementation_hashes()
                    or frozen["sample_hash"] != scope.sample_hash
                    or frozen["queries_hash"] != digest(queries)
                    or configuration(cfg["method"], cfg["representation"], prep) != cfg
                    or engine.validate()["configuration"] != frozen["index_configuration"]
                ):
                    raise ValueError("Configuration gelée incompatible.")
                args.output_directory.mkdir(parents=True, exist_ok=False)
                # Exclusive claim persists even on failure: never silently rerun a held-out experiment.
                write_json(
                    args.frozen.with_name(args.frozen.stem + ".evaluation-claimed.json"),
                    {"frozen_hash": saved_hash},
                )
                ranks, report = run_experiment(
                    engine,
                    queries,
                    method=cfg["method"],
                    strategy=cfg["representation"],
                    preparation=prep,
                    split="evaluation",
                    limit=frozen["limit"],
                )
                report["frozen_hash"] = saved_hash
                write_json(args.output_directory / "results.json", ranks)
                write_json(args.output_directory / "report.json", report)
                print("Évaluation gelée exportée, sans mesure de pertinence.")
    except (ValueError, KeyError, TypeError, OSError, SQLAlchemyError):
        print(
            "Opération RAG-009 refusée : contrôler configuration, fichiers et état local.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
