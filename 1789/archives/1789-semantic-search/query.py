"""Requête interactive facultative sur le pilote, sans toucher au jeu évalué."""

import argparse
import json
import sys
import unicodedata

from common import HERE, ROOT, read, rows, sha, text_sha
from search import BM25, French, hybrid, vector_rank


def main():
    import numpy as np

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--population", choices=("historical", "mixed"), default="mixed")
    parser.add_argument(
        "--method",
        choices=("lexical", "vector_A", "vector_B", "hybrid_A", "hybrid_B"),
        default="vector_A",
    )
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    query = unicodedata.normalize("NFC", args.query).strip()
    if not query or len(query) > 512 or not 1 <= args.limit <= 50:
        parser.error("Requête de1–512 caractères ; limite de1–50 résultats.")
    assert sha(HERE / "data/corpus.jsonl") == read(HERE / "data/preparation.json")["corpus_sha256"]
    corpus = rows(HERE / "data/corpus.jsonl")
    docs = {d["id"]: d for d in corpus}
    selected = [d for d in corpus if args.population == "mixed" or d["status"] == "A"]
    french = French()
    lex, _ = BM25(selected, french).search(query)
    french.close()
    if args.method == "lexical":
        result = lex
    else:
        for p, h in read(HERE / "data/encoding.json")["vector_files"].items():
            assert sha(HERE / "vectors" / p) == h
        known = read(HERE / "queries.json")["queries"]
        index = next((i for i, q in enumerate(known) if q["text"] == query), None)
        if index is not None:
            qvec = np.load(HERE / "vectors/queries.npy", allow_pickle=False)[index]
        else:
            sys.path.insert(0, str(ROOT / "rag/src"))
            from cahier_rag.embeddings.core import EmbeddingEngine, EmbeddingInput
            from cahier_rag.embeddings.registry import MODELS
            from cahier_rag.embeddings.transformers_backend import TransformersBackend

            engine = EmbeddingEngine(
                TransformersBackend(
                    MODELS["bge-m3"],
                    ROOT / "rag/models",
                    device="cpu",
                    precision="float32",
                    threads=4,
                )
            )
            try:
                engine.load()
                inp = EmbeddingInput("interactive-query", query, text_sha(query))
                qvec = np.asarray(next(engine.encode_queries([inp])).vectors[0], dtype=np.float32)
            finally:
                engine.close()
        variant = args.method[-1]
        matrix = np.concatenate(
            [
                np.load(HERE / f"vectors/historical_{variant}.npy", allow_pickle=False),
                np.load(HERE / "vectors/contemporary.npy", allow_pickle=False),
            ]
        )
        refs = [
            r for r in rows(HERE / "data/historical-segments.jsonl") if r["variant"] == variant
        ] + rows(HERE / "data/contemporary-segments.jsonl")
        result = vector_rank(qvec, matrix, refs, {d["id"] for d in selected})
        if args.method.startswith("hybrid"):
            result = hybrid(lex, result, docs)
    output = dict(
        query=query,
        population=args.population,
        method=args.method,
        score_kind="BM25"
        if args.method == "lexical"
        else "RRF"
        if args.method.startswith("hybrid")
        else "cosine_similarity",
        not_a_probability=True,
        results=[
            dict(
                rank=i,
                **r,
                corpus=docs[r["id"]]["corpus"],
                text=docs[r["id"]]["text"],
                parent_id=docs[r["id"]]["parent_id"],
                title=docs[r["id"]]["title"],
                references=docs[r["id"]]["references"],
            )
            for i, r in enumerate(result[: args.limit], 1)
        ],
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
