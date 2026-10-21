"""Prepare a reviewed restore list for a preinstalled pgvector extension.

No database connection. Keep all data/indexes; skip only vector extension ownership.
"""

import argparse
import os
import re
import subprocess


def restore_catalog(catalog):
    lines = catalog.splitlines(keepends=True)
    extension = re.compile(r"\bEXTENSION - vector(?:\s|$)")
    comment = re.compile(r"\bCOMMENT - EXTENSION vector(?:\s|$)")
    if sum(bool(extension.search(line)) for line in lines if not line.startswith(";")) != 1:
        raise ValueError("Archive complète avec une extension vector requise.")
    for required in (
        "TABLE DATA rag_full spaces",
        "TABLE DATA rag_full documents_full",
        "TABLE DATA rag_full segments_full",
        "TABLE DATA public rag_alembic_version",
        "TABLE DATA rag_tuning term_statistics",
        "INDEX rag_full segments_full_hnsw",
        "INDEX rag_full documents_full_search_vector_idx",
    ):
        if required not in catalog:
            raise ValueError("Archive incomplète : objet requis absent.")
    return "".join(
        line for line in lines if not extension.search(line) and not comment.search(line)
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        result = subprocess.run(
            ["pg_restore", "--list", args.archive], check=True, capture_output=True, text=True
        )
        filtered = restore_catalog(result.stdout)
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(filtered)
        print("Restore list ready; pgvector must be preinstalled at version 0.8.7.")
        return 0
    except Exception:
        print("Archive validation failed; no database was contacted.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
