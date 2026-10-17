"""CLI locale : échantillons, candidats et mesures sans moteur."""

import argparse
import itertools
import sys
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from cahier_rag.evaluation.files import (
    candidates,
    load_json,
    load_judgments,
    load_queries,
    write_json,
)
from cahier_rag.evaluation.metrics import aggregate
from cahier_rag.evaluation.sampling import digest, select_sample


def load_sample(path):
    sample = load_json(path)
    if not isinstance(sample, dict) or sample.get("sample_version") != 1:
        raise ValueError("Version d’échantillon inconnue.")
    docs = sample["documents"]
    if not isinstance(docs, list) or not all(isinstance(d, dict) for d in docs):
        raise ValueError("Liste documentaire requise.")
    if sample["selected_hash"] != digest(docs) or len({d["document_id"] for d in docs}) != len(
        docs
    ):
        raise ValueError("Échantillon altéré ou dupliqué.")
    links = {}
    for doc in docs:
        if doc["split"] not in {"development", "evaluation"}:
            raise ValueError("Partition invalide.")
        for key in (
            ("contribution", doc["corpus_id"], doc["contribution_id"]),
            ("text", doc["text_hash"]),
        ):
            if links.setdefault(key, doc["split"]) != doc["split"]:
                raise ValueError("Fuite entre partitions documentaires.")
    return sample


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("sample")
    build.add_argument("--extraction", type=UUID, action="append", required=True)
    build.add_argument("--size", type=int, required=True)
    build.add_argument("--seed", type=int, required=True)
    build.add_argument("--split-seed", type=int, default=1729)
    build.add_argument("--method", choices=["random", "stratified"], required=True)
    build.add_argument("--corpus-version", required=True)
    build.add_argument("--max-candidates", type=int, default=100000)
    build.add_argument("--allow-shortfall", action="store_true")
    build.add_argument("--quotas", help="Objet JSON strate -> quota minimal")
    build.add_argument("--env-file")
    build.add_argument("--output", required=True)
    info = commands.add_parser("describe")
    prep = commands.add_parser("candidates")
    score = commands.add_parser("score")
    for cmd in (info, prep, score):
        cmd.add_argument("--sample", required=True)
    for cmd in (prep, score):
        cmd.add_argument("--queries", required=True)
        cmd.add_argument("--output", required=True)
    prep.add_argument("--per-query", type=int, default=20)
    score.add_argument("--judgments", required=True)
    score.add_argument(
        "--results", required=True, help="Objet JSON query_id -> liste ordonnée de document_id"
    )
    score.add_argument("--k", type=int, default=10)
    score.add_argument(
        "--complete", action="store_true", help="Exiger tous les documents jugés par requête"
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "sample":
            from cahier_rag.__main__ import open_store
            from cahier_rag.config import load_settings

            if len(args.extraction) > 20 or not args.corpus_version.strip():
                raise ValueError("Au plus 20 extractions et une version explicite requises.")
            with open_store(load_settings(env_file=args.env_file)) as store:
                states = [store.get_state(key) for key in sorted(set(args.extraction), key=str)]
                if any(s.status != "completed" for s in states):
                    raise ValueError("Le cadre doit contenir uniquement des extractions terminées.")
                frame = {
                    "corpus_version": args.corpus_version,
                    "extractions": [s.to_dict() for s in states],
                }
                sample = select_sample(
                    itertools.chain.from_iterable(
                        store.iter_documents(s.extraction_id) for s in states
                    ),
                    size=args.size,
                    seed=args.seed,
                    method=args.method,
                    frame=frame,
                    max_candidates=args.max_candidates,
                    split_seed=args.split_seed,
                    quotas=load_json(args.quotas) if args.quotas else None,
                )
            if not args.allow_shortfall and (sample["shortfalls"] or sample["size_shortfall"]):
                raise ValueError(
                    "Cadre insuffisant pour la taille ou les quotas ; aucun fichier produit."
                )
            write_json(args.output, sample)
            print(sample["statistics"])
        else:
            sample = load_sample(args.sample)
            if args.command == "describe":
                print(
                    {
                        "selected": len(sample["documents"]),
                        "statistics": sample["statistics"],
                        "shortfalls": sample["shortfalls"],
                        "size_shortfall": sample["size_shortfall"],
                    }
                )
                return 0
            queries = load_queries(args.queries)
            if args.command == "candidates":
                write_json(args.output, candidates(queries, sample, per_query=args.per_query))
            else:
                _, judgments = load_judgments(args.judgments, queries, sample)
                runs = load_json(args.results)
                if not isinstance(runs, dict):
                    raise ValueError("Objet de résultats requis.")
                index = {d["document_id"]: d for d in sample["documents"]}
                for query in queries:
                    qid = query["query_id"]
                    ranking = runs.get(qid, [])
                    if not isinstance(ranking, list) or any(
                        d not in index or index[d]["split"] != query["split"] for d in ranking
                    ):
                        raise ValueError("Résultat inconnu ou hors partition.")
                    if args.complete and set(judgments.get(qid, {})) != {
                        d for d in index if index[d]["split"] == query["split"]
                    }:
                        raise ValueError("Jugements exhaustifs requis pour --complete.")
                report = aggregate(queries, runs, judgments, k=args.k, complete=args.complete)
                report["sample_hash"] = sample["selected_hash"]
                report["queries_hash"] = digest(queries)
                report["judgments_hash"] = digest(load_json(args.judgments))
                report["results_hash"] = digest(runs)
                write_json(args.output, report)
    except (ValueError, KeyError, TypeError, OSError, SQLAlchemyError):
        print(
            "Évaluation refusée : vérifier paramètres, références, fichiers et configuration.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
