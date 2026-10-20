"""Expériences RAG-027 locales ; le profil RAG-026 demeure accessible séparément."""

import argparse
import json
from pathlib import Path

from cahier_rag.__main__ import open_store
from cahier_rag.config import load_settings
from cahier_rag.fullcorpus.store import FullStore
from cahier_rag.tuning.experiments import encode_queries, lexical_benchmark, vector_benchmark
from cahier_rag.tuning.statistics import build_statistics


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "command", choices=["encode", "statistics", "lexical", "vectors", "report", "select"]
    )
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--directory", type=Path, default=Path("evaluation/local/rag027"))
    p.add_argument("--passes", type=int, default=3)
    p.add_argument("--reference", action="store_true")
    p.add_argument("--env-file", type=Path)
    args = p.parse_args(argv)
    args.directory.mkdir(parents=True, exist_ok=True)
    if args.command == "encode":
        data = encode_queries(args.root, args.directory)
        print(json.dumps(dict(queries=len(data["queries"]), load_seconds=data["load_seconds"])))
        return
    if args.command == "report":
        from cahier_rag.tuning.report import summarize

        result = summarize(args.directory)
        print(
            json.dumps(
                dict(queries=result["query_count"], report=str(args.directory / "comparison.json"))
            )
        )
        return
    with open_store(load_settings(env_file=args.env_file)) as storage:
        store = FullStore(storage.guard, "full")
        if args.command == "statistics":
            print(json.dumps(build_statistics(store)))
        elif args.command == "select":
            from cahier_rag.tuning.selection import save_selection

            result = save_selection(args.directory, store.state()["chain_hash"])
            print(
                json.dumps(
                    dict(selection_hash=result["selection_hash"], qualified=result["qualified"])
                )
            )
        elif args.command == "lexical":
            lexical_benchmark(store, args.root, args.directory, args.passes, args.reference)
        else:
            vector_benchmark(store, args.directory, args.root)


if __name__ == "__main__":
    main()
