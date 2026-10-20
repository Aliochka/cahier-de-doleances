"""Explicit public responses. BIGINT identifiers are decimal strings in JSON."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.choice_statistics import QuestionStatistics
from app.schemas.public_ids import PublicId


class FormSummary(BaseModel):
    id: PublicId
    name: str = Field(description="Nom public du formulaire historique.")
    questions_count: int = Field(ge=0, description="Nombre de questions, avec ou sans réponses.")
    url: str = Field(description="Chemin relatif de la page HTML historique.")


class FormQuestion(BaseModel):
    id: PublicId
    form_id: PublicId
    prompt: str
    type: str = Field(
        description="Type stocké, notamment text, single_choice ou multi_choice. Aucun recodage."
    )
    position: int | None = Field(
        description="Ordre déclaré dans le questionnaire ; peut être absent."
    )
    slug: str = Field(description="Slug construit avec le helper des routes HTML.")
    url: str = Field(description="Chemin relatif vers la question historique.")


class StatisticsAvailability(BaseModel):
    status: Literal["available", "unavailable"]
    reason: Literal["absent", "incompatible", "incomplete"] | None = None
    generation_id: str | None = None
    calculated_at: datetime | None = None
    method_version: str | None = None


class EnrichedFormQuestion(FormQuestion):
    answers_count: int | None = Field(default=None, ge=0)
    statistics: QuestionStatistics | None = None


class FormDetail(FormSummary):
    statistics_availability: StatisticsAvailability
    questions: list[EnrichedFormQuestion] = Field(
        description="Toutes les questions, selon COALESCE(position, 999999), puis id."
    )


class ApiError(BaseModel):
    detail: str
