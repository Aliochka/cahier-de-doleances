"""Pool RAG-009 de développement uniquement : rangs diversifiés et témoins aléatoires."""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from cahier_rag.__main__ import open_store
from cahier_rag.config import load_settings
from cahier_rag.evaluation.cli import load_sample
from cahier_rag.evaluation.files import load_queries, write_json
from cahier_rag.evaluation.sampling import digest
from cahier_rag.schema import units
from cahier_rag.search.experiments import EXPERIMENTS, pool_candidates
from cahier_rag.search.flexible import FlexibleEngine, configuration
from cahier_rag.search.lexical import CorpusScope
from cahier_rag.search.preparation import Preparation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-directory", type=Path, default=Path("evaluation/local/rag009/annotations")
    )
    parser.add_argument("--env-file")
    parser.add_argument("--per-query", type=int, default=20)
    parser.add_argument("--depth", type=int, default=30)
    parser.add_argument("--random-count", type=int, default=2)
    args = parser.parse_args()
    if (
        not 1 <= args.depth <= 100
        or not 3 <= args.per_query <= 100
        or not 0 <= args.random_count < args.per_query
    ):
        raise ValueError("Bornes de préparation invalides.")
    sample = load_sample("evaluation/local/rag007/corpus.json")
    queries = load_queries("evaluation/queries.json")
    args.output_directory.mkdir(parents=True, exist_ok=False)
    configurations = {}
    runs = {}
    with open_store(load_settings(env_file=args.env_file)) as store:
        engine = FlexibleEngine(store.guard, CorpusScope(sample))
        verified = engine.validate()
        for name, method, strategy in EXPERIMENTS:
            configurations[name] = configuration(method, strategy, Preparation())
            runs[name] = {}
            for query in queries:
                if query["split"] == "development":
                    results = engine.search(
                        query["text"],
                        method=method,
                        strategy=strategy,
                        split="development",
                        limit=args.depth,
                    )
                    runs[name][query["query_id"]] = [r.document.document_id for r in results]
            print("Candidats de développement :", name, flush=True)
        rows = pool_candidates(
            queries, sample, runs, per_query=args.per_query, random_count=args.random_count
        )
        identifiers = sorted({r["document_id"] for r in rows})
        references = {}
        for start in range(0, len(identifiers), 100):
            with store.guard.transaction() as (conn, source):
                values = (
                    conn.execute(
                        select(units.c.document_id, units.c.answer_id, units.c.question_id).where(
                            units.c.document_id.in_(identifiers[start : start + 100])
                        )
                    )
                    .mappings()
                    .all()
                )
            references.update(
                {
                    r["document_id"]: {
                        "answer_id": str(r["answer_id"]),
                        "question_id": str(r["question_id"]),
                    }
                    for r in values
                }
            )
        if len(references) != len(identifiers):
            raise ValueError("Référence documentaire absente.")
        for row in rows:
            row.update(references[row["document_id"]])
    write_json(args.output_directory / "runs.json", runs)
    write_json(args.output_directory / "pool.json", rows)
    write_json(
        args.output_directory / "manifest.json",
        {
            "version": 1,
            "split": "development",
            "sample_hash": sample["selected_hash"],
            "queries_hash": digest(queries),
            "configurations": configurations,
            "index_configuration": verified["configuration"],
            "seed": 20261019,
            "per_query": args.per_query,
            "depth": args.depth,
            "random_count": args.random_count,
            "pool_hash": digest(rows),
            "runs_hash": digest(runs),
            "candidate_count": len(rows),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "judgments_created": False,
        },
    )
    print("Paires non jugées :", len(rows))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, SQLAlchemyError):
        print(
            "Préparation refusée ; contrôler configuration et répertoire de sortie.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None
