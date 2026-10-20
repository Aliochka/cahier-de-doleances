"""Commandes explicites RAG-026, sans modèle chargé au simple import."""

import argparse
import json
from pathlib import Path

from cahier_rag.config import load_settings
from cahier_rag.db import create_rag_engine, create_source_engine
from cahier_rag.fullcorpus.audit import audit, fingerprint
from cahier_rag.fullcorpus.pipeline import embed, extract, recipe
from cahier_rag.fullcorpus.store import FullStore
from cahier_rag.safety import DatabaseGuard


def main(argv=None):
    parser = argparse.ArgumentParser(description="RAG-026 — corpus complet local")
    parser.add_argument("--env-file", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("audit")
    a.add_argument("--output", type=Path, required=True)
    sub.add_parser("migrate")
    for command in ("init", "extract", "embed", "status", "verify"):
        p = sub.add_parser(command)
        p.add_argument("--space", choices=["pilot100k", "full"], required=True)
        if command == "init":
            p.add_argument("--audit", type=Path, required=True)
            p.add_argument("--preflight", type=Path, required=True)
        if command in ("extract", "embed"):
            p.add_argument("--stop-after", type=int)
            p.add_argument("--log", type=Path)
        if command == "embed":
            p.add_argument("--batch-size", type=int, default=16)
    p = sub.add_parser("complete")
    p.add_argument("--directory", type=Path, required=True)
    p.add_argument("--batch-size", type=int, default=32)
    p.set_defaults(space="full")
    p = sub.add_parser("experiment")
    p.add_argument("--space", choices=["pilot100k", "full"], required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--vectors", type=Path)
    p = sub.add_parser("search")
    p.add_argument("--space", choices=["pilot100k", "full"], required=True)
    p.add_argument("--query", required=True)
    p.add_argument("--ann", action="store_true")
    p.add_argument("--questionnaire-id", type=int)
    p.add_argument("--unit-type", choices=["open_answer", "other_text"])
    args = parser.parse_args(argv)
    settings = load_settings(env_file=args.env_file)
    source, target = create_source_engine(settings), create_rag_engine(settings)
    guard = DatabaseGuard(source, target)
    try:
        if args.command == "audit":
            audit(source, target, args.output)
            return
        if args.command == "migrate":
            from alembic import command
            from alembic.config import Config

            config = Config()
            config.set_main_option("script_location", "cahier_rag:migrations")
            config.attributes["rag_settings"] = settings
            command.upgrade(config, "rag_0005")
            return
        store = FullStore(guard, args.space)
        if args.command == "complete":
            from cahier_rag.fullcorpus.run import complete

            complete(store, settings, args.directory, batch_size=args.batch_size)
            return
        if args.command == "init":
            report = json.loads(args.audit.read_text())
            if report["selection_hash"] != fingerprint(report["selection"]):
                raise ValueError("Inventaire altéré.")
            # Require an explicit resource report; pilot may use conservative
            # initial bounds; full requires measured pilot estimates.
            preflight = json.loads(args.preflight.read_text())
            if (
                not preflight.get("sufficient")
                or preflight.get("selection_hash") != report["selection_hash"]
            ):
                raise ValueError("Précontrôle de ressources absent/incompatible/insuffisant.")
            from cahier_rag.fullcorpus.pipeline import require_disk

            require_disk(Path.cwd(), preflight["required_free_bytes"])
            if args.space == "full" and not preflight.get("pilot_verified"):
                raise ValueError(
                    "Pilote vérifié et mesures réelles requis avant le corpus complet."
                )
            value = store.initialize(
                recipe(report, args.space), 100000 if args.space == "pilot100k" else report["units"]
            )
        elif args.command == "status":
            value = store.state()
        elif args.command == "extract":
            value = extract(store, stop_after=args.stop_after, log_path=args.log)
        elif args.command in ("embed", "experiment", "search"):
            from cahier_rag.embeddings.core import EmbeddingEngine
            from cahier_rag.embeddings.registry import MODELS
            from cahier_rag.embeddings.transformers_backend import TransformersBackend

            engine = EmbeddingEngine(
                TransformersBackend(
                    MODELS["bge-m3"], Path("models"), device="cuda", precision="bfloat16"
                )
            )
            if args.command == "embed":
                value = embed(
                    store,
                    engine,
                    batch_size=args.batch_size,
                    stop_after=args.stop_after,
                    log_path=args.log,
                )
            elif args.command == "experiment":
                from cahier_rag.fullcorpus.experiment import experiment

                value = experiment(store, engine, args.output, vectors_path=args.vectors)
            else:
                from cahier_rag.embeddings.core import EmbeddingInput
                from cahier_rag.fullcorpus.search import FullSearch

                engine.load()
                try:
                    vector = next(
                        engine.encode_queries(
                            [EmbeddingInput("query", args.query, fingerprint(args.query))]
                        )
                    ).vectors[0]
                finally:
                    engine.close()
                results, traces, metrics = FullSearch(store).hybrid(
                    args.query,
                    vector,
                    ann=args.ann,
                    questionnaire_id=args.questionnaire_id,
                    unit_type=args.unit_type,
                )
                value = dict(
                    results=[
                        dict(
                            document_id=r.document.document_id,
                            score=r.score,
                            contribution_id=str(r.document.contribution_id),
                            questionnaire_id=str(r.document.questionnaire_id),
                        )
                        for r in results[:10]
                    ],
                    traces=traces,
                    metrics=metrics,
                )
        else:
            value = store.verify()
        print(json.dumps(value, default=str, ensure_ascii=False, indent=2))
    finally:
        source.dispose()
        target.dispose()


if __name__ == "__main__":
    main()
