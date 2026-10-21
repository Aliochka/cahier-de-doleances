"""Service hybride réutilisable ; aucune connexion ou inférence à l'import."""

from pathlib import Path

from cahier_rag.embeddings.core import EmbeddingEngine
from cahier_rag.embeddings.registry import MODELS
from cahier_rag.embeddings.transformers_backend import TransformersBackend
from cahier_rag.search.service.core import HybridSearch, SearchRecipe
from cahier_rag.search.service.reader import SearchReader, create_search_engine
from cahier_rag.search.service.worker import SearchWorker


def create_service(
    settings,
    models,
    *,
    device="cpu",
    precision="float32",
    threads=4,
    recipe=SearchRecipe(),
    publication=None,
):
    """L'appelant possède start/close ; aucune connexion avant start()."""
    source_url, target_url = settings.require_source_url(), settings.require_rag_url()
    source = create_search_engine(source_url)
    target = create_search_engine(target_url)
    encoder = EmbeddingEngine(
        TransformersBackend(
            MODELS["bge-m3"],
            Path(models),
            device=device,
            precision=precision,
            threads=threads,
        )
    )
    return HybridSearch(
        SearchReader(source, target, publication=publication), encoder, recipe=recipe
    )


__all__ = ["HybridSearch", "SearchRecipe", "SearchWorker", "create_service"]
