"""Public author and complete contribution responses; never serialize ORM objects."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.forms import FormQuestion, PublicId
from app.schemas.questions import PublicAuthor, QuestionForm


class ContributionReference(BaseModel):
    id: PublicId
    submitted_at: datetime | None
    api_url: str = Field(
        description="Lecture JSON par ID de contribution, pas par rang historique."
    )


class AuthorForm(QuestionForm):
    contributions: list[ContributionReference]


class AuthorFormsPage(BaseModel):
    author_id: PublicId
    forms: list[AuthorForm] = Field(
        description="Formulaires sans doublons dans ce lot de contributions."
    )
    page_size: int
    has_next: bool
    next_after_id: PublicId | None = Field(
        description="Dernier ID du lot. Pagination des contributions, pas des formulaires ; un formulaire peut réapparaître dans un lot suivant."
    )


class SelectedOption(BaseModel):
    id: PublicId
    label: str
    position: int | None


class ContributionAnswer(BaseModel):
    id: PublicId = Field(description="Ancre frontend possible : answer-{id}.")
    position: int | None = Field(description="Position de la réponse au sein d'une même question.")
    question: FormQuestion
    text: str | None = Field(
        description="Texte public brut complet ; null et vide conservés pour les lignes existantes."
    )
    selected_options: list[SelectedOption]
    other_text: list[str]
    value: str | None = Field(
        description="Valeur publique des questions number/scale/date ; aucun JSON brut."
    )


class ContributionDetail(BaseModel):
    form: QuestionForm
    contribution: ContributionReference
    author: PublicAuthor | None
    legacy_index: PublicId | None = Field(
        default=None,
        description="Rang historique 1..M, uniquement lors d'une résolution par contrib. Ce n'est pas l'ID en base.",
    )
    answers: list[ContributionAnswer] = Field(
        description="Lignes réelles uniquement, par COALESCE(question.position,999999), question.id, answer.position NULLS LAST, answer.id."
    )
