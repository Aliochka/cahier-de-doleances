"""Adaptateur facultatif de l'interface personnelle ; manifeste complet jamais chargé en RAM."""

import time
from types import SimpleNamespace

from cahier_rag.embeddings.core import EmbeddingEngine, EmbeddingInput
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.embeddings.transformers_backend import TransformersBackend
from cahier_rag.fullcorpus.audit import fingerprint
from cahier_rag.fullcorpus.search import FullSearch
from cahier_rag.fullcorpus.store import FullStore


def retrieve(guard, root, query, *, ann=False, profile="rag026"):
    store = FullStore(guard, "full")
    state = store.state()
    if not state["verified"]:
        raise ValueError("Le corpus RAG-026 doit être complet et vérifié.")
    engine = EmbeddingEngine(
        TransformersBackend(MODELS["bge-m3"], root / "models", device="cuda", precision="bfloat16")
    )
    try:
        started = time.perf_counter()
        engine.load()
        loaded = time.perf_counter()
        vector = next(
            engine.encode_queries([EmbeddingInput("query", query, fingerprint(query))])
        ).vectors[0]
        encoded = time.perf_counter()
        if profile == "rag027":
            from cahier_rag.search.hybrid.core import fuse
            from cahier_rag.tuning.lexical import TunedSearch
            from cahier_rag.tuning.selection import load_selection
            from cahier_rag.tuning.vector import AnnConfig, ann_search

            selection = load_selection(
                root / "evaluation/local/rag027/selection.json", state["chain_hash"]
            )
            search = TunedSearch(store)
            left = search.lexical(query, limit=50)
            lexical_end = time.perf_counter()
            if ann:
                right, trace = ann_search(store, vector, AnnConfig(**selection["ann"]), limit=50)
            else:
                right = search.vector(vector, limit=50)
            vector_end = time.perf_counter()
            results, traces = fuse({"lexical": left, "vector": right}, k=60)
            measurements = dict(
                lexical_seconds=lexical_end - encoded,
                vector_seconds=vector_end - lexical_end,
                fusion_seconds=time.perf_counter() - vector_end,
                search_total_seconds=time.perf_counter() - encoded,
                selection_hash=fingerprint(selection),
            )
        elif profile == "rag026":
            results, traces, measurements = FullSearch(store).hybrid(query, vector, ann=ann)
            measurements["search_total_seconds"] = measurements.pop("total_seconds")
        else:
            raise ValueError("Profil de recherche inconnu.")
        measurements.update(
            embedding_load_seconds=loaded - started, query_encoding_seconds=encoded - loaded
        )
    finally:
        engine.close()
    results = list(results[:50])
    # Seulement les preuves nécessaires à l'assembleur. La taille du corpus
    # provient du manifeste vérifié, pas de cette petite table de résultats.
    scope = SimpleNamespace(
        retrieval_method="H1+R2-personal-all-rag026",
        sample_hash=state["recipe_hash"],
        documents={
            r.document.document_id: {"content_hash": r.document.content_hash} for r in results
        },
    )
    recipe = dict(
        state["manifest"],
        vector_search="HNSW" if ann else "exact",
        search_profile=profile,
        aggregation="maximum segment cosine",
        measurements=measurements,
    )
    return results, traces, recipe, scope, state["documents"]
