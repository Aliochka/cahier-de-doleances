"""Shared statistical definitions, independent of document contracts."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.public_ids import PublicId


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
