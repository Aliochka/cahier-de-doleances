"""Configuration et contrats immuables des représentations préparées v1."""

from dataclasses import asdict, dataclass
from enum import StrEnum

from cahier_rag.contracts import TextUnit, canonical_json, validate_id
from cahier_rag.evaluation.sampling import digest

REPRESENTATION_VERSION = 1


class Strategy(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


@dataclass(frozen=True)
class PreparationConfig:
    strategy: Strategy
    segment_chars: int = 2000
    overlap_chars: int = 200
    short_chars: int = 60
    max_neighbors: int = 2
    neighbor_chars: int = 1000

    def __post_init__(self):
        if not isinstance(self.strategy, Strategy):
            raise ValueError("Stratégie A, B, C ou D requise.")
        if type(self.segment_chars) is not int:
            raise ValueError("segment_chars doit être un entier.")
        bounds = {
            "segment_chars": (8, 1000000),
            "overlap_chars": (0, self.segment_chars // 2),
            "short_chars": (1, 1000),
            "max_neighbors": (0, 8),
            "neighbor_chars": (1, 100000),
        }
        for name, (low, high) in bounds.items():
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"Paramètre {name} hors limites.")

    def to_dict(self):
        return asdict(self) | {
            "strategy_version": 1,
            "representation_version": REPRESENTATION_VERSION,
            "segmentation_version": 1,
            "context_policy": "rag007-selected-only",
            "offset_unit": "python-unicode-codepoint",
            "title_policy": "metadata-only",
            "neighbor_order": "structural-distance-then-position-v1",
        }

    @property
    def config_hash(self):
        return digest(self.to_dict())


@dataclass(frozen=True)
class SourceReference:
    document_id: str
    content_hash: str
    corpus_id: str
    contribution_id: int
    answer_id: int
    question_id: int
    questionnaire_id: int

    def __post_init__(self):
        for key in ("contribution_id", "answer_id", "question_id", "questionnaire_id"):
            validate_id(getattr(self, key), key)

    @classmethod
    def from_unit(cls, unit: TextUnit):
        return cls(**{name: getattr(unit, name) for name in cls.__dataclass_fields__})

    def to_dict(self):
        value = asdict(self)
        for key in ("contribution_id", "answer_id", "question_id", "questionnaire_id"):
            value[key] = str(value[key])
        return value


@dataclass(frozen=True)
class SourceSpan:
    document_id: str
    field: str
    source_start: int
    source_end: int
    output_start: int
    output_end: int
    role: str


@dataclass(frozen=True)
class PreparedContext:
    question_text: str
    questionnaire_name: str
    contribution_title: str | None
    question_position: int | None
    answer_position: int
    unit_type: str

    @classmethod
    def from_unit(cls, unit: TextUnit):
        return cls(**{key: getattr(unit, key) for key in cls.__dataclass_fields__})


@dataclass(frozen=True)
class PreparedRepresentation:
    config: PreparationConfig
    sample_hash: str
    split: str
    primary: SourceReference
    context: PreparedContext
    parent_unit_ids: tuple[str, ...]
    segment_index: int
    segment_start: int
    segment_end: int
    embedding_text: str
    sources: tuple[SourceReference, ...]
    spans: tuple[SourceSpan, ...]
    enriched: bool

    def __post_init__(self):
        if self.split not in {"development", "evaluation"}:
            raise ValueError("Partition inconnue.")
        if not 0 <= self.segment_start < self.segment_end or self.segment_index < 0:
            raise ValueError("Segment invalide.")
        if not self.embedding_text or self.primary not in self.sources:
            raise ValueError("Texte ou référence primaire absent.")
        ids = {ref.document_id for ref in self.sources}
        if len(ids) != len(self.sources) or not ids <= set(self.parent_unit_ids):
            raise ValueError("Références dupliquées ou hors parent.")
        for ref in self.sources:
            if (ref.corpus_id, ref.contribution_id, ref.questionnaire_id) != (
                self.primary.corpus_id,
                self.primary.contribution_id,
                self.primary.questionnaire_id,
            ):
                raise ValueError("Référence d’une autre contribution.")
        for span in self.spans:
            if (
                span.document_id not in ids
                or span.field not in {"text", "question_text"}
                or not 0 <= span.source_start <= span.source_end
                or not 0 <= span.output_start <= span.output_end <= len(self.embedding_text)
                or span.source_end - span.source_start != span.output_end - span.output_start
            ):
                raise ValueError("Position source ou sortie invalide.")

    @property
    def representation_id(self):
        identity = [
            REPRESENTATION_VERSION,
            self.config.config_hash,
            self.sample_hash,
            self.primary.document_id,
            self.segment_start,
            self.segment_end,
        ]
        return f"prepared:v1:{self.config.strategy}:{digest(identity)}"

    def _payload(self):
        return {
            "representation_version": REPRESENTATION_VERSION,
            "representation_id": self.representation_id,
            "strategy": self.config.strategy.value,
            "strategy_version": 1,
            "config_hash": self.config.config_hash,
            "sample_hash": self.sample_hash,
            "split": self.split,
            "primary": self.primary.to_dict(),
            "context": asdict(self.context),
            "parent": {
                "corpus_id": self.primary.corpus_id,
                "contribution_id": str(self.primary.contribution_id),
                "scope": "rag007-selected-only",
                "unit_ids": list(self.parent_unit_ids),
            },
            "segment": {
                "index": self.segment_index,
                "start": self.segment_start,
                "end": self.segment_end,
                "field": "text",
                "offset_unit": "python-unicode-codepoint",
            },
            "embedding_text": self.embedding_text,
            "sources": [s.to_dict() for s in self.sources],
            "spans": [asdict(s) for s in self.spans],
            "enriched": self.enriched,
        }

    @property
    def content_hash(self):
        return digest(self._payload())

    def to_dict(self):
        return self._payload() | {"content_hash": self.content_hash}

    def to_json(self):
        return canonical_json(self.to_dict())
