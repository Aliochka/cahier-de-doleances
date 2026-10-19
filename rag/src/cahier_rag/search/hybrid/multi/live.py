"""Adaptateurs des moteurs inchangés ; BGE-M3 chargé une fois par session."""

import json
from contextlib import contextmanager

from cahier_rag.__main__ import open_store
from cahier_rag.config import load_settings
from cahier_rag.search.bm25.index import BM25Index, Config
from cahier_rag.search.bm25.tokenizer import FrenchTokenizer
from cahier_rag.search.flexible import FlexibleEngine, Method
from cahier_rag.search.hybrid.integrity import verify_frozen
from cahier_rag.search.hybrid.multi.core import MultiHybridEngine
from cahier_rag.search.lexical import Strategy
from cahier_rag.search.preparation import Preparation


@contextmanager
def open_engine(root, scope, queries, *, env_file=None):
    # Aucun import de torch/transformers à l'import du module ou pour le rejeu.
    from cahier_rag.embeddings.core import EmbeddingEngine
    from cahier_rag.embeddings.registry import MODELS
    from cahier_rag.embeddings.transformers_backend import TransformersBackend
    from cahier_rag.vector.engine import VectorEngine
    from cahier_rag.vector.preparation import load_prepared
    from cahier_rag.vector.store import VectorStore, recipe

    frozen = verify_frozen(root / "evaluation/local/rag009/frozen.json", scope, queries)
    indexes, backend = {}, None
    try:
        with open_store(load_settings(env_file=env_file)) as storage:
            lexical = FlexibleEngine(storage.guard, scope)
            if lexical.validate()["configuration"] != frozen["index_configuration"]:
                raise ValueError("Index lexical différent du gel.")
            tokenizer = FrenchTokenizer(storage.guard.target)
            for variant in ("A", "B"):
                index = BM25Index(
                    root / "evaluation/local/rag018" / ("bm25-" + variant + ".sqlite3"),
                    scope,
                    tokenizer,
                    Config(variant),
                )
                indexes["bm25-" + variant] = index
                index.verify()
            directory = root / "evaluation/local/rag013/bge-B"
            prepared = load_prepared(directory, scope)
            vector_store = VectorStore(storage.guard, scope, recipe(prepared))
            baseline = json.loads((directory / "index-report.json").read_text())
            if vector_store.space_id != baseline["space_id"] or not baseline["complete"]:
                raise ValueError("Espace vectoriel différent du gel.")
            backend = TransformersBackend(
                MODELS["bge-m3"], root / "models", device="cuda", precision="bfloat16"
            )
            vector = VectorEngine(vector_store, EmbeddingEngine(backend)).load()

            def lexical_search(query, **filters):
                return lexical.search(
                    query,
                    method=Method.WEIGHTED,
                    strategy=Strategy.ANSWER,
                    preparation=Preparation(),
                    **filters,
                )

            yield MultiHybridEngine(
                {
                    "lexical": lexical_search,
                    "vector": vector.search,
                    **{name: index.search for name, index in indexes.items()},
                },
                scope,
            )
    finally:
        for index in indexes.values():
            index.close()
        if backend is not None:
            backend.close()
