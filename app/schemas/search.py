"""Independent search responses, plain text only and lossless public IDs."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.forms import FormQuestion, FormSummary, PublicId
from app.schemas.questions import PublicAuthor, QuestionForm


class SearchAnswer(BaseModel):
    id: PublicId
    contribution_id: PublicId
    text: str = Field(
        description="Préfixe brut fidèle, 1 000 caractères maximum, sans HTML ajouté."
    )
    is_truncated: bool
    submitted_at: datetime | None
    author: PublicAuthor | None
    question: FormQuestion
    form: QuestionForm
    url: str = Field(description="Page React de contribution par ID, avec ancre answer-{id}.")


class AnswerSearchPage(BaseModel):
    q: str
    items: list[SearchAnswer]
    page_size: int
    has_next: bool
    next_cursor: str | None = Field(
        description="Curseur opaque ID décroissant, à réutiliser uniquement avec le même terme."
    )


class CatalogForm(FormSummary):
    kind: Literal["form"] = "form"


class CatalogQuestion(FormQuestion):
    kind: Literal["question"] = "question"
    form: QuestionForm
    answers_count: int = Field(
        ge=0, description="Compteur historique de question, sans comptage des résultats."
    )


class CatalogSearchPage(BaseModel):
    q: str
    forms: list[CatalogForm]
    questions: list[CatalogQuestion]
    page_size: int = Field(description="Limite par section, pas un total combiné.")
    has_next_forms: bool
    has_next_questions: bool
    next_cursor_forms: str | None = Field(
        description="Curseur opaque score/ID de la section formulaires."
    )
    next_cursor_questions: str | None = Field(
        description="Curseur opaque score/ID de la section questions."
    )
