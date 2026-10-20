"""Public question, answer and choice statistics contracts; IDs stay decimal strings."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import Path, Query
from pydantic import AfterValidator, BaseModel, Field

from app.schemas.choice_statistics import ChoiceCategory as ChoiceCategory
from app.schemas.choice_statistics import QuestionStatistics
from app.schemas.forms import FormQuestion, PublicId


def _bigint(value: str) -> str:
    if not 0 < int(value) <= 9223372036854775807:
        raise ValueError("Identifiant BIGINT positif requis")
    return value


PathId = Annotated[
    str,
    Path(
        pattern=r"^[0-9]+$",
        min_length=1,
        max_length=19,
        description="BIGINT positif, chaîne décimale.",
    ),
    AfterValidator(_bigint),
]


QueryId = Annotated[
    str,
    Query(
        pattern=r"^[0-9]+$",
        min_length=1,
        max_length=19,
        description="BIGINT positif, chaîne décimale.",
    ),
    AfterValidator(_bigint),
]


class QuestionForm(BaseModel):
    id: PublicId
    name: str
    url: str


class QuestionDetail(FormQuestion):
    form: QuestionForm
    display_mode: Literal["text", "choice"] = Field(
        description="choice pour single_choice/multi_choice ; text pour les autres types historiques."
    )


class PublicAuthor(BaseModel):
    id: PublicId
    name: str = Field(description="Nom public ou libellé neutre selon les règles d'anonymat.")
    is_anonymous: bool
    slug: str
    url: str


class PublicAnswer(BaseModel):
    id: PublicId
    question_id: PublicId
    contribution_id: PublicId
    text: str = Field(description="Texte brut public, pas du HTML fiable. À échapper au rendu.")
    is_truncated: bool = Field(
        description="Liste limitée à 20 000 caractères ; détail sans troncature."
    )
    submitted_at: datetime | None
    author: PublicAuthor | None
    url: str


class AnswerPage(BaseModel):
    question_id: PublicId
    items: list[PublicAnswer]
    page_size: int
    has_next: bool
    next_cursor: str | None = Field(
        description="Curseur opaque ; ne pas décoder ni convertir ses IDs."
    )


class AnswerDetail(PublicAnswer):
    question: FormQuestion


class FormQuestionStatistics(BaseModel):
    question: FormQuestion
    stats: QuestionStatistics


class FormStatistics(BaseModel):
    form: QuestionForm
    questions: list[FormQuestionStatistics] = Field(
        description="Choix uniques et multiples, COALESCE(position,999999), id ; inclut les questions sans réponse."
    )
