"""Pilotes, campagne et interface personnelle, aucun déploiement public."""

import argparse
import json
from pathlib import Path

from cahier_rag.annotation.session import atomic_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.generation.planning import iter_inputs, load_plan
from cahier_rag.personal.campaign import PILOT, Cache, answer


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--directory", type=Path, required=True)
    run.add_argument("--method", choices=["direct", "two-step"], default="direct")
    run.add_argument("--token-filter", action="store_true")
    run.add_argument("--stage", choices=["pilot", "development"], default="pilot")
    serve = sub.add_parser("serve")
    serve.add_argument("--port", type=int, default=8770)
    serve.add_argument("--env-file")
    serve.add_argument("--corpus", choices=["rag007", "rag026"], default="rag007")
    serve.add_argument("--ann", action="store_true")
    serve.add_argument("--search-profile", choices=["rag026", "rag027"], default="rag026")
    args = p.parse_args(argv)
    if args.command == "serve":
        from cahier_rag.personal.web import serve

        return serve(
            args.root,
            port=args.port,
            env_file=args.env_file,
            corpus=args.corpus,
            ann=args.ann,
            search_profile=args.search_profile,
        )
    from cahier_rag.embeddings.snapshots import sha256_file
    from cahier_rag.personal.backend import Generator

    root = args.root.resolve()
    directory = args.directory.resolve()
    if not directory.is_relative_to(root / "evaluation/local/rag025"):
        raise ValueError("Expérience rag025 indépendante requise.")
    old = root / "evaluation/local/rag022/v2/plan"
    plan = load_plan(old, root)
    originals = [i for i, _ in iter_inputs(old, plan)]
    backend = Generator(root / "models/judges", token_filter=args.token_filter)
    cache = Cache(directory / "generation.sqlite3")
    try:
        recipe = {
            "backend": backend.recipe(),
            "method": args.method,
            "baseline": plan["plan_hash"],
            "inputs": [i.input_hash for i in originals],
            "code": {
                n: sha256_file(Path(__file__).parent / n)
                for n in ("backend.py", "contracts.py", "campaign.py")
            },
            "pilot": list(PILOT),
            "purpose": "development-only",
        }
        path = directory / "recipe.json"
        if path.exists():
            if json.loads(path.read_text()) != recipe:
                raise ValueError("Recette figée incompatible.")
        else:
            atomic_json(path, recipe)
        if args.stage == "development":
            selection = directory / "selection.json"
            if not selection.exists() or json.loads(selection.read_text())["recipe_hash"] != digest(
                recipe
            ):
                raise ValueError("Sélection explicite après inspection du pilote requise.")
        chosen = [i for i in originals if args.stage == "development" or i.query_id in PILOT]
        results = []
        for original in chosen:
            result = answer(original, backend, cache, method=args.method)
            results.append(
                {"query_id": original.query_id, "input_hash": original.input_hash, **result}
            )
            atomic_json(directory / (args.stage + "-results.json"), results)
            atomic_json(
                directory / "progress.json",
                {
                    "stage": args.stage,
                    "completed": len(results),
                    "total": len(chosen),
                    "valid": sum(r["status"] == "valid" for r in results),
                    "recipe_hash": digest(recipe),
                },
            )
            print(
                f"{len(results)}/{len(chosen)} {original.query_id} {result['status']}", flush=True
            )
            if result["status"] == "error":
                break
    finally:
        backend.close()
        cache.close()
    return 0 if len(results) == len(chosen) and all(r["status"] == "valid" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
