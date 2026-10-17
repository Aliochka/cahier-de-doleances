"""Unités textuelles fidèles à la source, distinctes des futurs segments d'embedding."""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from urllib.parse import quote

CONTRACT_VERSION = 1
MAX_BIGINT = 2**63 - 1


class UnitType(StrEnum):
    OPEN_ANSWER = "open_answer"
    OTHER_TEXT = "other_text"


def validate_id(value: int, name: str) -> None:
    if type(value) is not int or not 1 <= value <= MAX_BIGINT:
        raise ValueError(f"{name} doit être un entier BIGINT positif.")


def canonical_json(value: dict) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


@dataclass(frozen=True)
class TextUnit:
    corpus_id: str
    unit_type: UnitType
    answer_id: int
    contribution_id: int
    question_id: int
    questionnaire_id: int
    text: str
    question_text: str
    questionnaire_name: str
    answer_position: int
    question_type: str
    unit_index: int = 0
    contribution_title: str | None = None
    question_position: int | None = None
    question_section: str | None = None
    question_code: str | None = None
    questionnaire_version: str | None = None
    questionnaire_source: str | None = None
    contribution_source: str | None = None
    external_contribution_id: str | None = None
    submitted_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("answer_id", "contribution_id", "question_id", "questionnaire_id"):
            validate_id(getattr(self, name), name)
        if not isinstance(self.corpus_id, str) or not self.corpus_id.strip():
            raise ValueError("corpus_id est requis.")
        if not isinstance(self.unit_type, UnitType):
            raise ValueError("unit_type doit être un UnitType.")
        if type(self.unit_index) is not int or self.unit_index < 0:
            raise ValueError("unit_index doit être un entier positif ou nul.")
        if self.unit_type == UnitType.OPEN_ANSWER and self.unit_index != 0:
            raise ValueError("Une réponse ouverte possède uniquement l'indice 0.")
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Une unité documentaire doit contenir du texte non blanc.")
        for name in ("question_text", "questionnaire_name", "question_type"):
            if not isinstance(getattr(self, name), str):
                raise ValueError(f"{name} doit être une chaîne.")
        for name in (
            "contribution_title",
            "question_section",
            "question_code",
            "questionnaire_version",
            "questionnaire_source",
            "contribution_source",
            "external_contribution_id",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"{name} doit être une chaîne ou None.")
        if type(self.answer_position) is not int or (
            self.question_position is not None and type(self.question_position) is not int
        ):
            raise ValueError("Les positions doivent être des entiers.")
        if self.submitted_at is not None and not isinstance(self.submitted_at, datetime):
            raise ValueError("submitted_at doit être un datetime ou None.")

    @property
    def document_id(self) -> str:
        corpus = quote(self.corpus_id, safe="")
        return f"text-unit:v{CONTRACT_VERSION}:{corpus}:{self.unit_type.value}:{self.answer_id}:{self.unit_index}"

    def _payload(self) -> dict:
        payload = asdict(self)
        for name in ("answer_id", "contribution_id", "question_id", "questionnaire_id"):
            payload[name] = str(payload[name])
        payload["unit_type"] = self.unit_type.value
        payload["submitted_at"] = self.submitted_at.isoformat() if self.submitted_at else None
        payload["contract_version"] = CONTRACT_VERSION
        return payload

    @property
    def content_hash(self) -> str:
        # Texte, contexte ET provenance : aucune normalisation Unicode ou linguistique.
        return hashlib.sha256(canonical_json(self._payload()).encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        payload = self._payload()
        payload["document_id"] = self.document_id
        payload["content_hash"] = self.content_hash
        return payload

    def to_json(self) -> str:
        return canonical_json(self.to_dict())


@dataclass(frozen=True)
class ContributionMetadata:
    """Métadonnées consultables même si une contribution n'a aucun texte ouvert."""

    corpus_id: str
    contribution_id: int
    questionnaire_id: int
    questionnaire_name: str
    title: str | None
    source: str | None
    external_id: str | None
    submitted_at: datetime | None
    questionnaire_version: str | None
    questionnaire_source: str | None

    def __post_init__(self) -> None:
        validate_id(self.contribution_id, "contribution_id")
        validate_id(self.questionnaire_id, "questionnaire_id")

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["contribution_id"] = str(self.contribution_id)
        payload["questionnaire_id"] = str(self.questionnaire_id)
        payload["submitted_at"] = self.submitted_at.isoformat() if self.submitted_at else None
        return payload
