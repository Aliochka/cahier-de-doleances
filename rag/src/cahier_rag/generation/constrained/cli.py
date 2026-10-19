"""Décodage contraint RAG-023, cache et artefacts indépendants."""

import argparse
import json
from pathlib import Path


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4])
    p.add_argument("--plan", type=Path, default=Path("evaluation/local/rag023/plan"))
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    run = sub.add_parser("run")
    run.add_argument("--stage", choices=["pilot", "development"], default="pilot")
    run.add_argument("--stop-after", type=int)
    run.add_argument("--retry-errors", action="store_true")
    sub.add_parser("report")
    args = p.parse_args(argv)
    if args.command == "report":
        from cahier_rag.generation.constrained.reporting import report

        result = report(args.root, args.plan)
        print(json.dumps(result))
        return 0
    from cahier_rag.generation.constrained.backend import ConstrainedGenerator
    from cahier_rag.generation.contracts import InferenceConfig

    backend = ConstrainedGenerator(args.root / "models/judges", InferenceConfig())
    try:
        if args.command == "prepare":
            from cahier_rag.generation.constrained.planning import prepare

            value = prepare(args.root, args.plan, backend)
            print(
                json.dumps(
                    {
                        "plan_hash": value["plan_hash"],
                        "queries": len(value["entries"]),
                        "prompt_changed": False,
                    }
                )
            )
        else:
            from cahier_rag.generation.constrained.cache import Cache
            from cahier_rag.generation.constrained.pipeline import run

            cache = Cache(args.plan.parent / "generation.sqlite3")
            try:
                value = run(
                    args.plan,
                    backend,
                    cache,
                    stage=args.stage,
                    stop_after=args.stop_after,
                    root=args.root,
                    retry_errors=args.retry_errors,
                )
                print(json.dumps(value))
            finally:
                cache.close()
    finally:
        backend.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
