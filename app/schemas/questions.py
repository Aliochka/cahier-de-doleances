"""Public question, answer and choice statistics contracts; IDs stay decimal strings."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import Path, Query
from pydantic import AfterValidator, BaseModel, Field

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


class ChoiceCategory(BaseModel):
    option_id: PublicId | None = Field(description="Null pour la catégorie synthétique other_text.")
    kind: Literal["option", "other_text"]
    label: str
    position: int | None
    count: int = Field(ge=0, description="Sélections de l'option, ou réponses avec autre texte.")
    percentage: float = Field(
        ge=0, description="100 × count / total_answers, arrondi à 2 décimales."
    )


class QuestionStatistics(BaseModel):
    question_id: PublicId
    type: Literal["single_choice", "multi_choice"]
    total_answers: int = Field(
        ge=0, description="Lignes answers, compteur historique maintenu par triggers."
    )
    answered_contributions_count: int = Field(
        ge=0, description="Contributions distinctes ayant une réponse ; pas des personnes uniques."
    )
    total_selections: int = Field(
        ge=0,
        description="Somme historique des catégories, incluant une catégorie autre texte par réponse.",
    )
    total_option_selections: int = Field(
        ge=0, description="Liens answer_options, hors catégorie autre texte."
    )
    other_text_answers_count: int = Field(ge=0)
    percentage_denominator: Literal["total_answers"] = "total_answers"
    percentage_decimal_places: Literal[2] = 2
    categories: list[ChoiceCategory] = Field(
        description="Options par position ASC NULLS LAST, id ASC ; autre texte ajouté en fin s'il existe."
    )
