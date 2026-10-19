"""Préparation locale de contextes documentaires, sans génération."""

import argparse
import json
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    sub = parser.add_subparsers(dest="command", required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--output", type=Path, required=True)
    build = sub.add_parser("build")
    build.add_argument("--protocol", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--query-limit", type=int, default=20)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("directory", type=Path)
    verify = sub.add_parser("verify")
    verify.add_argument("--protocol", type=Path, required=True)
    verify.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "freeze":
            from cahier_rag.context.experiments import freeze

            value = freeze(args.root, args.output)
            print(
                json.dumps(
                    {
                        "protocol_hash": value["protocol_hash"],
                        "configurations": list(value["configurations"]),
                    }
                )
            )
        elif args.command == "build":
            from cahier_rag.context.experiments import run

            value = run(args.root, args.protocol, args.output, query_limit=args.query_limit)
            print(
                json.dumps(
                    {
                        k: value[k]
                        for k in ("contexts", "seconds", "contexts_bytes", "manifest_hash")
                    }
                )
            )
        elif args.command == "verify":
            from cahier_rag.context.validation import verify

            print(json.dumps(verify(args.root, args.protocol, args.directory)))
        else:
            value = json.loads((args.directory / "manifest.json").read_text())
            print(json.dumps(value, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, FileNotFoundError, ModuleNotFoundError):
        parser.exit(
            2,
            "Erreur : paramètres, dépendances optionnelles ou artefacts incompatibles. Aucun contexte valide publié.\n",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
