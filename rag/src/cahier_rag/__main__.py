"""Diagnostic local sans réseau, PostgreSQL, backend ni GPU."""

import argparse
import sys
from collections.abc import Sequence
from importlib.metadata import version

from cahier_rag.config import ConfigurationError, load_settings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version", action="version", version=f"cahier-rag {version('cahier-rag')}"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-config", help="Valider les paramètres sans se connecter")
    check.add_argument("--env-file", help="Fichier local explicitement sélectionné")
    check.add_argument("--connection", choices=("all", "source", "rag"), default="all")
    args = parser.parse_args(argv)
    try:
        settings = load_settings(env_file=args.env_file)
        if args.connection in {"all", "source"}:
            settings.require_source_url()
        if args.connection in {"all", "rag"}:
            settings.require_rag_url()
    except ConfigurationError as exc:
        print(f"Configuration incorrecte : {exc}", file=sys.stderr)
        return 2
    print("Configuration valide. Aucune connexion PostgreSQL ouverte.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
