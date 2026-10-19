"""Entrées aveugles et préparation séparée des listes de récupération."""

import math
from dataclasses import asdict, dataclass
from typing import Protocol

from cahier_rag.evaluation.sampling import digest


@dataclass(frozen=True)
class PreparationConfig:
    contextualization: str = "question_answer"
    budget: int = 1024
    overlap_chars: int = 128
    aggregation: str = "max"
    version: int = 1

    def __post_init__(self):
        if (
            self.contextualization not in {"question_answer", "answer"}
            or type(self.budget) is not int
            or not 64 <= self.budget <= 8192
            or type(self.overlap_chars) is not int
            or not 0 <= self.overlap_chars <= 512
            or self.aggregation != "max"
            or self.version != 1
        ):
            raise ValueError("Configuration de préparation invalide.")

    def to_dict(self):
        return asdict(self) | {
            "offsets": "unicode-codepoints, [start,end)",
            "segmentation": "joint-token-budget; paragraph/sentence preferred; no truncation",
        }


@dataclass(frozen=True)
class Pair:
    query_id: str
    document_id: str
    source_hash: str
    query: str
    document: str
    start: int
    end: int
    segment_index: int

    def __post_init__(self):
        if any(
            not isinstance(getattr(self, k), str) or not getattr(self, k).strip()
            for k in ("query_id", "document_id", "source_hash", "query", "document")
        ):
            raise ValueError("Identité et textes non vides requis.")
        if (
            any(type(v) is not int for v in (self.start, self.end, self.segment_index))
            or self.start < 0
            or self.end <= self.start
            or self.segment_index < 0
        ):
            raise ValueError("Positions de segment invalides.")

    def to_dict(self):
        return asdict(self)

    @property
    def input_hash(self):
        return digest(self.to_dict())


class RerankerBackend(Protocol):
    spec: object
    device: str
    precision: str

    def load_tokenizer(self): ...
    def token_count(self, query: str, document: str) -> int: ...
    def load(self): ...
    def score(self, pairs: list[Pair]) -> list[float]: ...
    def close(self): ...


def validate_scores(values, count):
    if len(values) != count or any(
        type(v) not in (int, float) or not math.isfinite(v) for v in values
    ):
        raise ValueError("Scores de reranking invalides ; lot non validé.")
    return [float(v) for v in values]
