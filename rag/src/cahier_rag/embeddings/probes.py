"""Sondes longues : comptage seul et refus vérifié, aucun gros encodage implicite."""

from cahier_rag.embeddings.core import EmbeddingEngine, EmbeddingError, EmbeddingInput, InputTooLong
from cahier_rag.evaluation.sampling import digest
from cahier_rag.representations.contracts import PreparationConfig, Strategy
from cahier_rag.representations.prepare import prepare_unit
from cahier_rag.representations.repository import RepresentationRepository


def long_probes(backends, engine, scope):
    repository = RepresentationRepository(engine, scope)
    ids = sorted(
        (did for did, item in scope.documents.items() if item["split"] == "development"),
        key=lambda did: (-scope.documents[did]["length"], did),
    )[:3]
    docs = repository.fetch(ids)
    config = PreparationConfig(Strategy.A, segment_chars=1000000, overlap_chars=0)
    inputs = []
    for did in ids:
        prepared = list(
            prepare_unit(
                docs[did], config=config, sample_hash=scope.sample_hash, split="development"
            )
        )
        if len(prepared) != 1:
            raise EmbeddingError("Sonde longue dépassant un million de caractères.")
        p = prepared[0]
        inputs.append(EmbeddingInput(p.representation_id, p.embedding_text, p.content_hash, did))
    report = {
        "version": 1,
        "preparation": config.to_dict(),
        "scope": "development-tokenization-only",
        "inputs": [
            {
                "input_id": i.input_id,
                "primary_id": i.primary_id,
                "source_hash": i.source_hash,
                "characters": len(i.text),
            }
            for i in inputs
        ],
        "models": {},
    }
    for key, backend in backends.items():
        wrapper = EmbeddingEngine(backend)
        counts = wrapper.counts(inputs, role="document")
        synthetic = EmbeddingInput(
            "oversize-synthetic", "mot " * (backend.max_tokens + 1), digest("oversize-synthetic")
        )
        number = wrapper.counts([synthetic], role="document")[0]
        try:
            wrapper.require_fits([synthetic], role="document")
        except InputTooLong:
            refused = True
        else:
            raise EmbeddingError("La sonde surdimensionnée n’a pas été refusée.")
        report["models"][key] = {
            "counts": counts,
            "effective_limit": backend.max_tokens,
            "overflow_count": sum(n > backend.max_tokens for n in counts),
            "synthetic_overflow_tokens": number,
            "synthetic_refusal_verified": refused,
            "encoded_long_inputs": 0,
        }
    report["report_hash"] = digest(report)
    return report
