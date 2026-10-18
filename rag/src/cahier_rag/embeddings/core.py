"""Interface interchangeable et intégrité des vecteurs, sans numpy ni torch."""

import hashlib
import math
import sys
from array import array
from dataclasses import dataclass
from typing import Protocol

from cahier_rag.evaluation.sampling import digest


class EmbeddingError(ValueError):
    """Erreur publique sans texte documentaire ni paramètres sensibles."""


class InputTooLong(EmbeddingError):
    def __init__(self, items, limit):
        self.items = tuple(items)
        self.limit = limit
        super().__init__(
            f"{len(items)} entrée(s) dépassent la limite de {limit} tokens ; aucune troncature."
        )


@dataclass(frozen=True)
class EmbeddingInput:
    input_id: str
    text: str
    source_hash: str
    primary_id: str | None = None

    def __post_init__(self):
        if not self.input_id or not isinstance(self.text, str) or not self.text.strip():
            raise EmbeddingError("Identifiant et texte non vides requis.")

    def fingerprint(self):
        return digest(
            {
                "id": self.input_id,
                "text": self.text,
                "source_hash": self.source_hash,
                "primary_id": self.primary_id,
            }
        )


class Backend(Protocol):
    dimension: int
    max_tokens: int

    def load(self): ...
    def token_lengths(self, texts: list[str], role: str) -> list[int]: ...
    def encode(self, texts: list[str], role: str) -> list[list[float]]: ...
    def close(self): ...


@dataclass(frozen=True)
class VectorBatch:
    identifiers: tuple[str, ...]
    vectors: tuple[tuple[float, ...], ...]
    token_lengths: tuple[int, ...]
    input_hashes: tuple[str, ...]
    normalized: bool

    def binary(self):
        values = array("f", (x for row in self.vectors for x in row))
        if sys.byteorder != "little":
            values.byteswap()
        return values.tobytes()

    @property
    def output_hash(self):
        return hashlib.sha256(self.binary()).hexdigest()


def validate_vectors(vectors, *, expected_rows, dimension, normalize):
    if len(vectors) != expected_rows:
        raise EmbeddingError("Nombre de vecteurs différent du nombre d’entrées.")
    output = []
    for row in vectors:
        try:
            valid = len(row) == dimension and all(math.isfinite(x) for x in row)
        except (TypeError, ValueError, OverflowError):
            valid = False
        if not valid:
            raise EmbeddingError(
                "Vecteur de dimension incorrecte ou contenant une valeur non finie."
            )
        if not normalize and any(abs(float(x)) > 3.402823466e38 for x in row):
            raise EmbeddingError("Valeur hors du domaine de stockage float32.")
        norm = math.sqrt(math.fsum(float(x) * float(x) for x in row))
        if norm <= 1e-12:
            raise EmbeddingError("Vecteur nul.")
        result = tuple(float(x) / norm if normalize else float(x) for x in row)
        if normalize and abs(math.sqrt(math.fsum(x * x for x in result)) - 1) > 1e-5:
            raise EmbeddingError("Norme incorrecte.")
        output.append(result)
    return tuple(output)


class EmbeddingEngine:
    def __init__(self, backend: Backend, *, normalize=True):
        self.backend = backend
        self.normalize = normalize
        self.loaded = False

    def load(self):
        if self.loaded:
            return self
        self.backend.load()
        self.loaded = True
        return self

    @property
    def dimension(self):
        return self.backend.dimension

    def counts(self, inputs, *, role):
        if role not in {"document", "query"}:
            raise EmbeddingError("Rôle document ou query requis.")
        if len(inputs) > 2048 or len({i.input_id for i in inputs}) != len(inputs):
            raise EmbeddingError("Entrées dupliquées ou lot supérieur à 2048 représentations.")
        counts = self.backend.token_lengths([i.text for i in inputs], role)
        if len(counts) != len(inputs) or any(type(n) is not int or n < 1 for n in counts):
            raise EmbeddingError("Comptage de tokens invalide.")
        return counts

    def require_fits(self, inputs, *, role):
        counts = self.counts(inputs, role=role)
        overflow = [(i.input_id, n) for i, n in zip(inputs, counts) if n > self.backend.max_tokens]
        if overflow:
            raise InputTooLong(overflow, self.backend.max_tokens)
        return counts

    def encode(self, inputs, *, role, batch_size=8):
        if not self.loaded:
            raise EmbeddingError("Charger explicitement le modèle avant l’encodage.")
        if type(batch_size) is not int or not 1 <= batch_size <= 64:
            raise EmbeddingError("Taille de lot entre 1 et 64 requise.")
        counts = self.require_fits(inputs, role=role)
        for start in range(0, len(inputs), batch_size):
            batch = inputs[start : start + batch_size]
            try:
                raw = self.backend.encode([i.text for i in batch], role)
            except (RuntimeError, MemoryError):
                raise EmbeddingError(
                    "Échec CPU/GPU pendant l’encodage ; réduire le lot ou vérifier le périphérique."
                ) from None
            vectors = validate_vectors(
                raw, expected_rows=len(batch), dimension=self.dimension, normalize=self.normalize
            )
            yield VectorBatch(
                tuple(i.input_id for i in batch),
                vectors,
                tuple(counts[start : start + len(batch)]),
                tuple(i.fingerprint() for i in batch),
                self.normalize,
            )

    def encode_documents(self, inputs, *, batch_size=8):
        return self.encode(inputs, role="document", batch_size=batch_size)

    def encode_queries(self, inputs, *, batch_size=1):
        return self.encode(inputs, role="query", batch_size=batch_size)

    def close(self):
        self.backend.close()
        self.loaded = False
