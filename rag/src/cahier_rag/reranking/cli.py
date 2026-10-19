"""Reranking local : préparation aveugle, inférence optionnelle et évaluation séparée."""

import argparse
import json
from pathlib import Path

from cahier_rag.reranking.contracts import PreparationConfig
from cahier_rag.reranking.registry import MODELS, download


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--models", type=Path, default=Path("models/rerankers"))
    parser.add_argument("--plan", type=Path, default=Path("evaluation/local/rag020/plan"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("models")
    downloading = sub.add_parser("download")
    downloading.add_argument("--model", choices=MODELS)
    preparing = sub.add_parser("prepare")
    preparing.add_argument(
        "--contextualization", choices=["question_answer", "answer"], default="question_answer"
    )
    preparing.add_argument("--budget", type=int, default=1024)
    preparing.add_argument("--overlap-chars", type=int, default=128)
    running = sub.add_parser("run")
    running.add_argument("--model", choices=MODELS, required=True)
    running.add_argument("--stop-after", type=int)
    cpu = sub.add_parser("cpu")
    cpu.add_argument("--model", choices=MODELS, required=True)
    cpu.add_argument("--output", type=Path, required=True)
    reporting = sub.add_parser("report")
    reporting.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "models":
        print(json.dumps({k: s.to_dict() for k, s in MODELS.items()}, indent=2))
    elif args.command == "download":
        for key, spec in MODELS.items():
            if args.model is None or args.model == key:
                download(spec, args.models)
                print(key, "snapshot vérifié", flush=True)
    elif args.command == "prepare":
        from cahier_rag.reranking.backend import TransformersReranker
        from cahier_rag.reranking.planning import prepare

        config = PreparationConfig(args.contextualization, args.budget, args.overlap_chars)
        backends = {
            m: TransformersReranker(s, args.models, budget=config.budget) for m, s in MODELS.items()
        }
        try:
            result = prepare(args.root, args.plan, backends, config)
            print(
                json.dumps(
                    {
                        "pairs": len(result["pairs"]),
                        "segments": sum(len(e["segments"]) for e in result["pairs"]),
                        "hash": result["manifest_hash"],
                    }
                )
            )
        finally:
            for backend in backends.values():
                backend.close()
    elif args.command in {"run", "cpu"}:
        from cahier_rag.reranking.backend import TransformersReranker
        from cahier_rag.reranking.planning import load_plan

        manifest, _ = load_plan(args.plan)
        backend = TransformersReranker(
            MODELS[args.model],
            args.models,
            device="cuda" if args.command == "run" else "cpu",
            budget=manifest["configuration"]["budget"],
        )
        if args.command == "run":
            from cahier_rag.reranking.cache import Cache
            from cahier_rag.reranking.pipeline import run

            cache = Cache(args.plan.parent / "scores.sqlite3")
            try:
                result = run(args.plan, args.model, backend, cache, stop_after=args.stop_after)
                print(
                    json.dumps(
                        {
                            k: result[k]
                            for k in (
                                "complete",
                                "processed",
                                "new",
                                "reused",
                                "load_seconds",
                                "scoring_seconds_cumulative",
                            )
                        },
                        indent=2,
                    )
                )
            finally:
                cache.close()
                backend.close()
        else:
            from cahier_rag.reranking.benchmark import cpu_benchmark

            result = cpu_benchmark(args.plan, backend, args.output)
            print(
                json.dumps(
                    {
                        "load_seconds": result["load_seconds"],
                        "seconds": [r["seconds"] for r in result["rows"]],
                    }
                )
            )
    else:
        from cahier_rag.reranking.evaluation import report_comparison

        report_comparison(args.root, args.plan, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
