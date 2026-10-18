"""CLI des modèles locaux, plans communs, tokenization et benchmarks bornés."""

import argparse
import sys
from pathlib import Path

from cahier_rag.contracts import canonical_json
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.evaluation.files import load_json


def local_output(path):
    root = Path(__file__).resolve().parents[3] / "evaluation/local/rag012"
    if root.resolve() not in Path(path).resolve().parents:
        raise ValueError(
            "Sortie attendue dans un nouveau fichier/dossier de evaluation/local/rag012/."
        )
    Path(path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)


def main(argv=None):
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", type=Path, default=root / "models")
    parser.add_argument("--sample", type=Path, default=root / "evaluation/local/rag007/corpus.json")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list")
    show = commands.add_parser("show")
    show.add_argument("model", choices=MODELS)
    download = commands.add_parser("download")
    download.add_argument("model", choices=MODELS)
    tokens = commands.add_parser("tokens")
    tokens.add_argument("model", choices=MODELS)
    tokens.add_argument("directory", type=Path)
    plan = commands.add_parser("plan")
    for strategy in ("A", "B", "D"):
        plan.add_argument(
            f"--{strategy}",
            type=Path,
            default=root / f"evaluation/local/rag011/final-trial-{strategy}",
        )
    plan.add_argument("--C", type=Path, default=root / "evaluation/local/rag011/final-trial-C")
    plan.add_argument("--output", type=Path, required=True)
    bench = commands.add_parser("benchmark")
    bench.add_argument("model", choices=MODELS)
    bench.add_argument("--plan", type=Path, required=True)
    bench.add_argument("--output", type=Path, required=True)
    bench.add_argument("--device", choices=["cpu", "cuda"], required=True)
    bench.add_argument("--precision", choices=["float32", "bfloat16", "float16"])
    bench.add_argument("--threads", type=int, default=4)
    bench.add_argument("--batch-sizes", type=int, nargs="+", default=[8, 32])
    bench.add_argument("--queries-only", action="store_true")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            print(canonical_json({key: value.to_dict() for key, value in MODELS.items()}))
            return 0
        if args.command == "show":
            print(canonical_json(MODELS[args.model].to_dict()))
            return 0
        if args.command == "download":
            from cahier_rag.embeddings.snapshots import download

            download(MODELS[args.model], args.model_root)
            print(
                canonical_json({"downloaded": args.model, "revision": MODELS[args.model].revision})
            )
            return 0
        if args.command == "inspect":
            from cahier_rag.embeddings.benchmark import inspect_benchmark

            manifest, integrity = inspect_benchmark(args.directory)
            print(
                canonical_json(
                    {
                        key: manifest[key]
                        for key in (
                            "model",
                            "device",
                            "precision",
                            "load_seconds",
                            "queries",
                            "gpu_memory",
                            "ram",
                        )
                        if key in manifest
                    }
                )
            )
            print(canonical_json(integrity))
            return 0
        from cahier_rag.evaluation.cli import load_sample
        from cahier_rag.search.lexical import CorpusScope

        scope = CorpusScope(load_sample(args.sample))
        from cahier_rag.embeddings.transformers_backend import TransformersBackend

        if args.command == "tokens":
            from cahier_rag.embeddings.core import EmbeddingEngine
            from cahier_rag.embeddings.data import read_representations
            from cahier_rag.embeddings.planning import token_statistics

            backend = TransformersBackend(MODELS[args.model], args.model_root)
            _, inputs = read_representations(args.directory, scope)
            counts = EmbeddingEngine(backend).counts(inputs, role="document")
            print(canonical_json(token_statistics(counts, backend.max_tokens)))
            return 0
        if args.command == "plan":
            from cahier_rag.embeddings.planning import create_plan

            local_output(args.output)
            backends = {
                key: TransformersBackend(spec, args.model_root) for key, spec in MODELS.items()
            }
            result = create_plan(
                scope,
                {key: getattr(args, key) for key in ("A", "B", "D")},
                backends,
                args.output,
                c_directory=args.C,
            )
            print(
                canonical_json(
                    {
                        "plan_hash": result["plan_hash"],
                        "strategies": {
                            key: {
                                "common_representations": value["common_representations"],
                                "common_primary_units": value["common_primary_units"],
                            }
                            for key, value in result["strategies"].items()
                        },
                    }
                )
            )
            return 0
        if args.device == "cpu" and not args.queries_only:
            raise ValueError("Pour cette première comparaison CPU, utiliser --queries-only.")
        from cahier_rag.embeddings.benchmark import benchmark

        local_output(args.output)
        precision = args.precision or ("float32" if args.device == "cpu" else "bfloat16")
        backend = TransformersBackend(
            MODELS[args.model],
            args.model_root,
            device=args.device,
            precision=precision,
            threads=args.threads,
        )
        result = benchmark(
            backend,
            load_json(args.plan),
            scope,
            args.output,
            batch_sizes=tuple(args.batch_sizes),
            cpu_queries_only=args.queries_only,
        )
        print(
            canonical_json(
                {
                    "model": args.model,
                    "device": args.device,
                    "load_seconds": result["load_seconds"],
                    "query_median_seconds": result["queries"]["median_seconds"],
                    "manifest_hash": result["manifest_hash"],
                }
            )
        )
        return 0
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, ImportError):
        print(
            "Embedding refusé : vérifier modèle, snapshot, fenêtre, périphérique et fichiers locaux ; aucune troncature ni API distante.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
