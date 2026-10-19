"""Texte citoyen, métadonnées et informations techniques explicitement séparés."""

from dataclasses import asdict, dataclass

from cahier_rag.contracts import TextUnit
from cahier_rag.evaluation.sampling import digest


@dataclass(frozen=True)
class ContextConfig:
    selection: str = "S2"
    parent_mode: str = "P1"
    document_budget: int = 8192
    max_primary: int = 20
    excerpt_tokens: int = 768
    min_partial_tokens: int = 32
    max_neighbors: int = 2
    expansion_fraction: float = 0.2
    near_jaccard: float = 0.9
    near_length_ratio: float = 0.9
    near_min_words: int = 8
    instructions_reserved: int = 512
    answer_reserved: int = 1024
    envelope_reserved: int = 128
    version: int = 1

    def __post_init__(self):
        integers = (
            "document_budget",
            "max_primary",
            "excerpt_tokens",
            "min_partial_tokens",
            "max_neighbors",
            "near_min_words",
            "instructions_reserved",
            "answer_reserved",
            "envelope_reserved",
        )
        if (
            self.selection not in {"S1", "S2", "S3"}
            or self.parent_mode not in {"P0", "P1", "P2"}
            or any(type(getattr(self, k)) is not int or getattr(self, k) < 0 for k in integers)
            or not 256 <= self.document_budget <= 32768
            or not 1 <= self.max_primary <= 50
            or not 32 <= self.excerpt_tokens <= 2048
            or not 1 <= self.min_partial_tokens <= self.excerpt_tokens
            or not 0 <= self.max_neighbors <= 4
            or not 1 <= self.near_min_words <= 100
            or type(self.expansion_fraction) not in (int, float)
            or not 0 <= self.expansion_fraction <= 0.25
            or type(self.near_jaccard) not in (int, float)
            or not 0.5 <= self.near_jaccard <= 1
            or type(self.near_length_ratio) not in (int, float)
            or not 0.5 <= self.near_length_ratio <= 1
            or type(self.version) is not int
            or self.version != 1
        ):
            raise ValueError("Configuration de contexte invalide.")

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ContextSource:
    unit: TextUnit
    sample_hash: str
    start: int
    end: int
    method: str
    rank: int | None
    role: str = "primary"
    parent_document_id: str | None = None

    def __post_init__(self):
        if (
            not isinstance(self.unit, TextUnit)
            or not self.sample_hash
            or not self.method
            or type(self.start) is not int
            or type(self.end) is not int
            or not 0 <= self.start < self.end <= len(self.unit.text)
            or self.role not in {"primary", "complementary"}
            or (
                self.role == "primary"
                and (
                    type(self.rank) is not int
                    or self.rank < 1
                    or self.parent_document_id is not None
                )
            )
            or (
                self.role == "complementary"
                and (self.rank is not None or not self.parent_document_id)
            )
        ):
            raise ValueError("Source de contexte ou positions invalides.")

    @property
    def reference(self):
        return "context-source:v1:" + digest(
            [self.sample_hash, self.unit.document_id, self.start, self.end]
        )

    @property
    def citizen_text(self):
        return self.unit.text[self.start : self.end]

    def to_dict(self):
        u = self.unit
        return {
            "reference": self.reference,
            "citizen_text": self.citizen_text,
            "metadata": {
                "document_id": u.document_id,
                "document_hash": u.content_hash,
                "corpus_id": u.corpus_id,
                "contribution_id": str(u.contribution_id),
                "answer_id": str(u.answer_id),
                "question_id": str(u.question_id),
                "questionnaire_id": str(u.questionnaire_id),
                "unit_type": u.unit_type.value,
                "unit_index": u.unit_index,
                "question_text": u.question_text,
                "questionnaire_name": u.questionnaire_name,
                "contribution_title": u.contribution_title,
                "question_position": u.question_position,
                "answer_position": u.answer_position,
                "question_section": u.question_section,
                "question_code": u.question_code,
                "source": u.contribution_source,
                "external_contribution_id": u.external_contribution_id,
                "questionnaire_source": u.questionnaire_source,
                "questionnaire_version": u.questionnaire_version,
                "submitted_at": u.submitted_at.isoformat() if u.submitted_at else None,
            },
            "technical": {
                "contract_version": 1,
                "sample_hash": self.sample_hash,
                "role": self.role,
                "retrieval": {
                    "method": self.method,
                    "rank": self.rank,
                    "direct": self.role == "primary",
                },
                "parent_document_id": self.parent_document_id,
                "excerpt": {
                    "start": self.start,
                    "end": self.end,
                    "original_length": len(u.text),
                    "offsets": "unicode-codepoints [start,end)",
                },
                "omitted_ranges": [
                    [a, b] for a, b in ((0, self.start), (self.end, len(u.text))) if a < b
                ],
                "public_url": None,
                "link_target": {
                    "corpus_id": u.corpus_id,
                    "contribution_id": str(u.contribution_id),
                    "question_id": str(u.question_id),
                    "answer_id": str(u.answer_id),
                    "unit_index": u.unit_index,
                },
            },
        }
