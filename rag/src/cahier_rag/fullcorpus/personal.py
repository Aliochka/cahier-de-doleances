"""Adaptateur facultatif de l'interface personnelle ; manifeste complet jamais chargé en RAM."""

from types import SimpleNamespace

from cahier_rag.embeddings.core import EmbeddingEngine, EmbeddingInput
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.embeddings.transformers_backend import TransformersBackend
from cahier_rag.fullcorpus.audit import fingerprint
from cahier_rag.fullcorpus.search import FullSearch
from cahier_rag.fullcorpus.store import FullStore


def retrieve(guard, root, query, *, ann=False):
    store = FullStore(guard, "full")
    state = store.state()
    if not state["verified"]:
        raise ValueError("Le corpus RAG-026 doit être complet et vérifié.")
    engine = EmbeddingEngine(
        TransformersBackend(MODELS["bge-m3"], root / "models", device="cuda", precision="bfloat16")
    )
    try:
        engine.load()
        vector = next(
            engine.encode_queries([EmbeddingInput("query", query, fingerprint(query))])
        ).vectors[0]
        results, traces, measurements = FullSearch(store).hybrid(query, vector, ann=ann)
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
        aggregation="maximum segment cosine",
        measurements=measurements,
    )
    return results, traces, recipe, scope, state["documents"]
