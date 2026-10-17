"""Commandes locales RAG ; le diagnostic de configuration reste sans connexion."""

import argparse
import sys
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import replace
from importlib.metadata import version
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from cahier_rag.config import ConfigurationError, load_settings
from cahier_rag.contracts import UnitType, canonical_json
from cahier_rag.extraction import ExtractionError, ExtractionSpec
from cahier_rag.safety import DatabaseSafetyError
from cahier_rag.sources.gdn import SourceDataError


def positive_integer(value: str) -> int:
    try:
        parsed = int(value)
        if parsed <= 0:
            raise ValueError()
        return parsed
    except ValueError:
        raise argparse.ArgumentTypeError("Un entier strictement positif est requis.") from None


@contextmanager
def open_store(settings):
    from cahier_rag.db import create_rag_engine, create_source_engine
    from cahier_rag.safety import DatabaseGuard
    from cahier_rag.storage import RagStore

    source = create_source_engine(settings)
    target = None
    try:
        target = create_rag_engine(settings)
        yield RagStore(DatabaseGuard(source, target))
    finally:
        source.dispose()
        if target is not None:
            target.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version", action="version", version=f"cahier-rag {version('cahier-rag')}"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check-config", help="Valider les paramètres sans se connecter")
    check.add_argument("--env-file", help="Fichier local explicitement sélectionné")
    check.add_argument("--connection", choices=("all", "source", "rag"), default="all")
    upgrade = commands.add_parser(
        "schema-upgrade", help="Appliquer les migrations RAG après contrôle des bases"
    )
    upgrade.add_argument("--env-file")
    start = commands.add_parser("extract", help="Démarrer une extraction explicitement limitée")
    resume = commands.add_parser(
        "resume", help="Reprendre un manifeste existant sans changer ses paramètres"
    )
    status = commands.add_parser("status", help="Consulter la progression sans afficher les textes")
    for command in (start, resume, status):
        command.add_argument("--env-file")
    for command in (resume, status):
        command.add_argument("extraction_id", type=UUID)
    for command in (start, resume):
        command.add_argument("--limit", type=positive_integer, required=command is start)
        command.add_argument("--corpus-id", default="gdn-2019" if command is start else None)
        command.add_argument(
            "--batch-size", type=positive_integer, default=500 if command is start else None
        )
        command.add_argument("--questionnaire-id", type=positive_integer)
        command.add_argument("--max-source-rows", type=positive_integer)
        command.add_argument("--contribution-id", type=positive_integer)
        command.add_argument("--unit-type", choices=[item.value for item in UnitType])
        command.add_argument(
            "--max-batches", type=positive_integer, help="Arrêt volontaire après N lots validés"
        )
    args = parser.parse_args(argv)
    try:
        settings = load_settings(env_file=args.env_file)
        if args.command == "check-config":
            if args.connection in {"all", "source"}:
                settings.require_source_url()
            if args.connection in {"all", "rag"}:
                settings.require_rag_url()
            print("Configuration valide. Aucune connexion PostgreSQL ouverte.")
        elif args.command == "schema-upgrade":
            from cahier_rag.migrate import upgrade_schema

            upgrade_schema(settings)
            print("Schéma RAG à jour.")
        else:
            from cahier_rag.pipeline import run_extraction

            # Valider la limite avant de contacter une base.
            values = {}
            if args.command in {"extract", "resume"}:
                for name in (
                    "limit",
                    "corpus_id",
                    "batch_size",
                    "questionnaire_id",
                    "max_source_rows",
                    "contribution_id",
                    "unit_type",
                ):
                    value = getattr(args, name)
                    if value is not None:
                        values[name] = UnitType(value) if name == "unit_type" else value
            spec = ExtractionSpec(**values) if args.command == "extract" else None
            with open_store(settings) as store:
                if args.command == "extract":
                    state = store.create_extraction(spec)
                    # Afficher le manifeste avant tout lot pour permettre une reprise après SIGINT.
                    print(canonical_json(state.to_dict()), flush=True)
                else:
                    state = store.get_state(args.extraction_id)
                    if args.command == "resume":
                        spec = replace(state.spec, **values)
                if args.command != "status":
                    state = run_extraction(
                        store, state.extraction_id, expected_spec=spec, max_batches=args.max_batches
                    )
                print(canonical_json(state.to_dict()))
    except ConfigurationError as exc:
        print(f"Configuration incorrecte : {exc}", file=sys.stderr)
        return 2
    except (ExtractionError, DatabaseSafetyError, SourceDataError) as exc:
        print(f"Opération refusée : {exc}", file=sys.stderr)
        return 2
    except SQLAlchemyError:
        print(
            "Opération PostgreSQL impossible ; vérifier les bases, droits et migrations.",
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        print(
            "Extraction interrompue ; reprendre depuis le dernier checkpoint validé.",
            file=sys.stderr,
        )
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
