"""Deux juges locaux : préparation, téléchargement, exécution limitée et calibration."""

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from cahier_rag.annotation.campaigns import Catalogue
from cahier_rag.annotation.consolidation import consolidate
from cahier_rag.annotation.session import atomic_json
from cahier_rag.config import load_settings
from cahier_rag.db import create_rag_engine
from cahier_rag.evaluation.cli import load_sample
from cahier_rag.evaluation.files import load_json, load_queries
from cahier_rag.evaluation.sampling import digest
from cahier_rag.judges.backend import TransformersJudge
from cahier_rag.judges.cache import Cache
from cahier_rag.judges.comparison import report
from cahier_rag.judges.contracts import PROMPT_VERSION, SYSTEM, InferenceConfig
from cahier_rag.judges.models import MODELS, download
from cahier_rag.judges.pipeline import run
from cahier_rag.judges.planning import load_plan, prepare
from cahier_rag.judges.reference import freeze, grades
from cahier_rag.representations.repository import RepresentationRepository
from cahier_rag.search.lexical import CorpusScope


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--models", type=Path, default=Path("models/judges"))
    parser.add_argument("--cache", type=Path, default=Path("evaluation/local/rag016/cache.sqlite3"))
    parser.add_argument("--env-file")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("models")
    down = sub.add_parser("download")
    down.add_argument("--judge", choices=MODELS, required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--kind", choices=["human60", "pools800", "top10"], required=True)
    prep.add_argument("--output", type=Path, required=True)
    infer = sub.add_parser("run")
    infer.add_argument("--plan", type=Path, required=True)
    infer.add_argument("--judge", choices=MODELS, required=True)
    infer.add_argument("--limit", type=int, required=True)
    infer.add_argument("--allow-full", action="store_true")
    infer.add_argument("--retry-failed", action="store_true")
    infer.add_argument("--batch-size", type=int, default=2)
    infer.add_argument("--max-input-tokens", type=int, default=24576)
    infer.add_argument("--max-new-tokens", type=int, default=192)
    infer.add_argument("--stop-after", type=int)
    check = sub.add_parser("compare")
    check.add_argument("--plan", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    check.add_argument("--reference", type=Path)
    frozen = sub.add_parser("freeze-reference")
    frozen.add_argument("--plan", type=Path, required=True)
    frozen.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    cache = None
    engine = None
    try:
        if args.command == "models":
            print(json.dumps([s.to_dict() for s in MODELS.values()], indent=2))
            return 0
        if args.command == "download":
            download(MODELS[args.judge], args.models)
            print("Snapshot officiel téléchargé et vérifié.")
            return 0
        if args.command == "run":
            config = InferenceConfig(args.batch_size, args.max_input_tokens, args.max_new_tokens)
            cache = Cache(args.cache)
            result = run(
                args.plan,
                TransformersJudge(MODELS[args.judge], args.models, config),
                config,
                cache,
                limit=args.limit,
                allow_full=args.allow_full,
                retry_failed=args.retry_failed,
                stop_after=args.stop_after,
            )
            print(
                json.dumps(
                    {k: result[k] for k in ("recipe_hash", "counts", "seconds", "complete")},
                    indent=2,
                )
            )
            return 0
        queries = load_queries(args.root / "evaluation/queries.json")
        sample = load_sample(args.root / "evaluation/local/rag007/corpus.json")
        scope = CorpusScope(sample)
        catalogue = Catalogue(args.root, queries, sample)
        if args.command == "prepare":
            sources = {}
            if args.kind == "human60":
                reference = consolidate(catalogue)
                if reference["conflicts"] or len(reference["judgments"]) != 60:
                    raise ValueError(
                        "La calibration exige exactement 60 couples humains résolus et sans conflit."
                    )
                pairs = {(r["query_id"], r["document_id"]) for r in reference["judgments"]}
                sources = {"human_sources": reference["sources"]}
            elif args.kind == "pools800":
                pools = {name: catalogue.load_pool(name) for name in catalogue.campaigns}
                pairs = {(r["query_id"], r["document_id"]) for rows in pools.values() for r in rows}
                if len(pairs) != 800:
                    raise ValueError("Les pools attendus ne totalisent pas 800 couples distincts.")
                sources = {"pool_hashes": {name: digest(rows) for name, rows in pools.items()}}
            else:
                from cahier_rag.annotation.reporting import load_rankings

                runs, metadata = load_rankings(
                    args.root / "evaluation/local/rag014/development-replay", queries, sample
                )
                pools = [catalogue.load_pool(name) for name in catalogue.campaigns]
                existing = {(r["query_id"], r["document_id"]) for rows in pools for r in rows}
                pairs = {
                    (qid, did)
                    for ranks in runs.values()
                    for qid, ids in ranks.items()
                    for did in ids[:10]
                } - existing
                sources = {
                    "rankings": metadata,
                    "excluded_pool_pairs_hash": digest(sorted(existing)),
                }
            engine = create_rag_engine(load_settings(env_file=args.env_file))
            manifest = prepare(
                args.output,
                pairs,
                RepresentationRepository(engine, scope),
                queries,
                kind=args.kind,
                source_hashes=sources,
            )
            print(
                json.dumps(
                    {
                        "count": len(manifest["entries"]),
                        "plan_hash": manifest["manifest_hash"],
                        "validation_count": sum(
                            e["subset"] == "validation" for e in manifest["entries"]
                        ),
                    },
                    indent=2,
                )
            )
            return 0
        manifest = load_plan(args.plan)
        if manifest["sample_hash"] != scope.sample_hash or manifest["query_hash"] != digest(
            queries
        ):
            raise ValueError("Plan incompatible avec le corpus ou les requêtes.")
        frozen_reference = None
        if args.command == "freeze-reference":
            frozen_reference = freeze(manifest, consolidate(catalogue))
            args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
            atomic_json(args.output / "reference.json", frozen_reference)
            print("Référence humaine figée séparément, sans commentaires ; sources inchangées.")
            return 0
        if args.reference:
            frozen_reference = load_json(args.reference)
            human = grades(manifest, frozen_reference)
        else:
            reference = consolidate(catalogue)
            if (
                manifest["kind"] == "human60"
                and manifest["source_hashes"]["human_sources"] != reference["sources"]
            ):
                raise ValueError(
                    "Référence humaine modifiée depuis le gel du plan ; sélectionner une référence figée."
                )
            human = {(r["query_id"], r["document_id"]): r["grade"] for r in reference["judgments"]}
        cache = Cache(args.cache)
        values = {}
        recipes = {}
        for key in MODELS:
            run_report = load_json(args.plan / (key + "-run.json"))
            if run_report["plan_hash"] != manifest["manifest_hash"] or not run_report["complete"]:
                raise ValueError("Les deux exécutions complètes du même plan sont nécessaires.")
            if (
                digest(run_report["recipe"]) != run_report["recipe_hash"]
                or run_report["recipe"]["model"] != MODELS[key].to_dict()
                or run_report["recipe"]["prompt_version"] != PROMPT_VERSION
                or run_report["recipe"]["prompt_hash"] != digest(SYSTEM)
            ):
                raise ValueError("Recettes des deux juges incompatibles ou interverties.")
            recipes[key] = run_report["recipe_hash"]
            values[key] = {
                entry["input_hash"]: cache.get(run_report["recipe_hash"], entry["input_hash"])
                for entry in manifest["entries"]
            }
        result = report(manifest, values, human)
        if frozen_reference:
            result["human_reference_hash"] = frozen_reference["reference_hash"]
        result["recipe_hashes"] = recipes
        args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
        atomic_json(args.output / "comparison.json", result)
        atomic_json(args.output / "human-review.json", result["review"])
        print(
            json.dumps({k: result[k] for k in ("models", "inter_judge", "disagreements")}, indent=2)
        )
        return 0
    except (ValueError, KeyError, TypeError, OSError, ImportError, SQLAlchemyError):
        print(
            "Opération refusée : vérifier plan, modèles, cache, référence et ressources. Aucun texte ni secret affiché.",
            file=sys.stderr,
        )
        return 2
    finally:
        if cache is not None:
            cache.close()
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
