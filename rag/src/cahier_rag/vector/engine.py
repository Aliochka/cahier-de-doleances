"""Interface de recherche compatible avec les résultats lexicaux, indépendante du LLM."""

import time

from cahier_rag.embeddings.core import EmbeddingInput
from cahier_rag.evaluation.sampling import digest


class VectorEngine:
    def __init__(self, store, embeddings):
        self.store, self.embeddings = store, embeddings
        self.loaded = False
        self.last_timings = {}

    def load(self):
        backend = self.embeddings.backend
        config = self.store.configuration
        if (
            backend.spec.to_dict() != config["model"]
            or self.embeddings.dimension != 1024
            or not self.embeddings.normalize
            or backend.precision != config["precision"]
        ):
            raise ValueError("Encodeur de requêtes incompatible avec l'espace vectoriel.")
        backend.load_tokenizer()
        if backend.snapshot_hash != config["prepared"]["snapshot_hash"]:
            raise ValueError("Snapshot de requêtes incompatible avec l'espace.")
        self.store.verify(require_complete=True)
        self.embeddings.load()
        self.loaded = True
        return self

    def search(
        self, query, *, limit=10, split="development", questionnaire_id=None, unit_type=None
    ):
        if not self.loaded:
            raise ValueError("Charger explicitement le moteur avant une recherche.")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Requête non vide requise.")
        started = time.perf_counter()
        batch = next(
            self.embeddings.encode_queries([EmbeddingInput("query", query, digest(query))])
        )
        encoded = time.perf_counter()
        results = self.store.search(
            batch.vectors[0],
            limit=limit,
            split=split,
            questionnaire_id=questionnaire_id,
            unit_type=unit_type,
        )
        self.last_timings = {
            "encoding_seconds": encoded - started,
            "sql_seconds": time.perf_counter() - encoded,
        }
        return results

    def close(self):
        self.embeddings.close()
        self.loaded = False
