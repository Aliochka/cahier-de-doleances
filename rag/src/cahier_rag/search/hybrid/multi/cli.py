"""Configurations RAG-019, exécution réelle, rejeu CPU et comparaison des jugements."""

import argparse
import json
from pathlib import Path

from cahier_rag.search.hybrid.multi.artifacts import freeze, load_bundle, load_frozen
from cahier_rag.search.hybrid.multi.experiments import experiment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[5])
    parser.add_argument(
        "--frozen", type=Path, default=Path("evaluation/local/rag019/configuration")
    )
    parser.add_argument("--env-file")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("freeze")
    live = sub.add_parser("development")
    live.add_argument("--output", type=Path, required=True)
    replay = sub.add_parser("replay")
    replay.add_argument("--experiment", type=Path, required=True)
    replay.add_argument("--output", type=Path, required=True)
    pool = sub.add_parser("pool")
    pool.add_argument("--experiment", type=Path, required=True)
    pool.add_argument("--output", type=Path, required=True)
    report = sub.add_parser("report")
    report.add_argument("--experiment", type=Path, required=True)
    report.add_argument("--pool", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--profile", choices=["H1", "H2", "H3", "H4", "H5"], default="H1")
    search.add_argument("--questionnaire-id", type=int)
    search.add_argument("--unit-type", choices=["open_answer", "other_text"])
    search.add_argument("--limit", type=int, default=10)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        print(json.dumps(freeze(args.root, args.frozen)["configuration"], indent=2))
        return 0
    frozen, scope, queries = load_frozen(args.root, args.frozen)
    if args.command in {"development", "search"}:
        from cahier_rag.search.hybrid.multi.live import open_engine

        with open_engine(args.root, scope, queries, env_file=args.env_file) as engine:
            if args.command == "development":
                experiment(args.root, scope, queries, frozen, args.output, engine=engine)
            else:
                retrieval = engine.retrieve(
                    args.query,
                    split="development",
                    questionnaire_id=args.questionnaire_id,
                    unit_type=args.unit_type,
                    limit=args.limit,
                )
                print(
                    json.dumps(
                        {
                            "results": [r.to_dict() for r in retrieval.hybrids[args.profile]],
                            "traces": retrieval.traces[args.profile],
                            "measurements": retrieval.measurements,
                        },
                        ensure_ascii=False,
                    )
                )
    elif args.command == "replay":
        bundle, *_ = load_bundle(args.root, args.frozen, args.experiment)
        experiment(args.root, scope, queries, frozen, args.output, cached=bundle)
    elif args.command == "pool":
        from cahier_rag.search.hybrid.multi.evaluation import prepare_pool

        print(
            json.dumps(
                prepare_pool(args.root, args.frozen, args.experiment, args.output)["counts"],
                indent=2,
            )
        )
    else:
        from cahier_rag.search.hybrid.multi.evaluation import report_comparison

        report_comparison(args.root, args.frozen, args.experiment, args.pool, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
