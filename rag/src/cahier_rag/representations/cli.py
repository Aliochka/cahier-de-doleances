"""CLI locale de préparation/inspection/rejeu, sans modèle ni nouvel index."""

import argparse
import hashlib
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from cahier_rag.config import load_settings
from cahier_rag.contracts import canonical_json
from cahier_rag.db import create_rag_engine
from cahier_rag.evaluation.cli import load_sample
from cahier_rag.evaluation.sampling import digest
from cahier_rag.representations.artifacts import (
    generate,
    implementation_hashes,
    inspect_artifact,
    select_targets,
)
from cahier_rag.representations.contracts import PreparationConfig, Strategy
from cahier_rag.representations.repository import RepresentationRepository
from cahier_rag.search.lexical import CorpusScope


def config_from_dict(value):
    names = PreparationConfig.__dataclass_fields__
    kwargs = {key: value[key] for key in names}
    kwargs["strategy"] = Strategy(kwargs["strategy"])
    config = PreparationConfig(**kwargs)
    if config.to_dict() != value:
        raise ValueError("Version de configuration incompatible.")
    return config


def verify_replay(repository, output, *, batch_size=50):
    manifest = inspect_artifact(output, scope=repository.scope)
    if manifest["implementation_hashes"] != implementation_hashes():
        raise ValueError("Le code de préparation a changé depuis la génération.")
    config = config_from_dict(manifest["configuration"])
    file_hash, logical = hashlib.sha256(), hashlib.sha256()
    for representation in repository.iter_prepared(
        manifest["target_ids"], config, batch_size=batch_size
    ):
        file_hash.update((representation.to_json() + "\n").encode())
        logical.update(
            (representation.representation_id + ":" + representation.content_hash + "\n").encode()
        )
    if (
        file_hash.hexdigest() != manifest["data_sha256"]
        or logical.hexdigest() != manifest["representations_hash"]
    ):
        raise ValueError("Rejeu différent de l’artefact existant.")
    return {
        "reproducible": True,
        "data_sha256": file_hash.hexdigest(),
        "target_units": len(manifest["target_ids"]),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", default="evaluation/local/rag007/corpus.json")
    parser.add_argument("--env-file")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("generate")
    build.add_argument("--strategy", choices=list(Strategy), required=True)
    build.add_argument("--limit", type=int, required=True)
    build.add_argument(
        "--split", choices=["development", "evaluation", "all"], default="development"
    )
    build.add_argument("--seed", type=int, default=20261021)
    build.add_argument("--batch-size", type=int, default=50)
    for name, default in (
        ("segment-chars", 2000),
        ("overlap-chars", 200),
        ("short-chars", 60),
        ("max-neighbors", 2),
        ("neighbor-chars", 1000),
    ):
        build.add_argument(f"--{name}", type=int, default=default)
    build.add_argument("--output", type=Path, required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("directory", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--batch-size", type=int, default=50)
    parent = commands.add_parser("parent")
    parent.add_argument("document_id")
    parent.add_argument("--show-text", action="store_true")
    args = parser.parse_args(argv)
    engine = None
    try:
        sample = load_sample(args.sample)
        scope = CorpusScope(sample)
        if args.command == "inspect":
            manifest = inspect_artifact(args.directory, scope=scope)
            print(
                canonical_json(
                    {
                        "configuration": manifest["configuration"],
                        "statistics": manifest["statistics"],
                        "manifest_hash": manifest["manifest_hash"],
                    }
                )
            )
            return 0
        if args.command == "generate":
            config = PreparationConfig(
                strategy=Strategy(args.strategy),
                **{
                    name: getattr(args, name)
                    for name in PreparationConfig.__dataclass_fields__
                    if name != "strategy"
                },
            )
            target_ids = select_targets(scope, limit=args.limit, split=args.split, seed=args.seed)
            # Interdire les sorties dans les sources historiques ou à l’extérieur des artefacts.
            root = Path(__file__).resolve().parents[3] / "evaluation/local/rag011"
            resolved = args.output.resolve()
            if root.resolve() not in resolved.parents:
                raise ValueError(
                    "La sortie doit être un nouveau sous-dossier de evaluation/local/rag011/."
                )
        engine = create_rag_engine(load_settings(env_file=args.env_file))
        repository = RepresentationRepository(engine, scope)
        if args.command == "generate":
            manifest = generate(
                repository,
                config,
                target_ids,
                args.output,
                selection={
                    "limit": args.limit,
                    "split": args.split,
                    "seed": args.seed,
                    "method": "sha256-seed-document-id-v1",
                },
                batch_size=args.batch_size,
                corpus_version=sample.get("frame", {}).get("corpus_version"),
                source_manifest={
                    "sha256": hashlib.sha256(Path(args.sample).read_bytes()).hexdigest(),
                    "manifest_digest": digest(sample),
                    "frame_hash": sample.get("frame_hash"),
                    "extraction_ids": [
                        e["extraction_id"] for e in sample.get("frame", {}).get("extractions", [])
                    ],
                },
            )
            print(canonical_json(manifest["statistics"]))
        elif args.command == "verify":
            print(
                canonical_json(
                    verify_replay(repository, args.directory, batch_size=args.batch_size)
                )
            )
        else:
            documents = repository.parent(args.document_id)
            print(
                canonical_json(
                    {
                        "context_policy": "rag007-selected-only",
                        "documents": [
                            d.to_dict()
                            if args.show_text
                            else {
                                "document_id": d.document_id,
                                "content_hash": d.content_hash,
                                "contribution_id": str(d.contribution_id),
                                "length": len(d.text),
                            }
                            for d in documents
                        ],
                    }
                )
            )
        return 0
    except (ValueError, KeyError, TypeError, OSError, SQLAlchemyError):
        print(
            "Préparation refusée : vérifier paramètres, corpus, références et fichiers ; aucun texte source modifié.",
            file=sys.stderr,
        )
        return 2
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
