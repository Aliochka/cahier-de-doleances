"""Génération documentaire locale RAG-022, sans relancer les moteurs."""

import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--plan", type=Path, default=Path("evaluation/local/rag022/v2/plan"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    running = sub.add_parser("run")
    running.add_argument("--stage", choices=["pilot", "development"], default="pilot")
    running.add_argument("--stop-after", type=int)
    running.add_argument("--retry-errors", action="store_true")
    sub.add_parser("report")
    args = parser.parse_args(argv)
    if args.command == "report":
        from cahier_rag.generation.reporting import report

        print(json.dumps(report(args.plan, args.root), ensure_ascii=False))
        return 0
    from cahier_rag.generation.backend import LocalGenerator
    from cahier_rag.generation.contracts import InferenceConfig

    backend = LocalGenerator(args.root / "models/judges", InferenceConfig())
    try:
        if args.command == "prepare":
            from cahier_rag.generation.planning import prepare

            value = prepare(args.root, args.plan, backend)
            print(
                json.dumps(
                    {
                        "plan_hash": value["plan_hash"],
                        "queries": len(value["entries"]),
                        "prompt_tokens": [e["prompt_tokens"] for e in value["entries"]],
                    }
                )
            )
        else:
            from cahier_rag.generation.cache import Cache
            from cahier_rag.generation.pipeline import run

            cache = Cache(args.plan.parent / "generation.sqlite3")
            try:
                value = run(
                    args.plan,
                    backend,
                    cache,
                    stage=args.stage,
                    stop_after=args.stop_after,
                    retry_errors=args.retry_errors,
                    root=args.root,
                )
                print(json.dumps(value, ensure_ascii=False))
            finally:
                cache.close()
    finally:
        backend.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
