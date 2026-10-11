"""Explicit public responses. BIGINT identifiers are decimal strings in JSON."""

from typing import Annotated

from pydantic import BaseModel, Field

PublicId = Annotated[
    str,
    Field(
        pattern=r"^[0-9]+$",
        description="Identifiant historique BIGINT, chaîne décimale sans perte de précision.",
    ),
]


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


class FormDetail(FormSummary):
    questions: list[FormQuestion] = Field(
        description="Toutes les questions, selon COALESCE(position, 999999), puis id."
    )


class ApiError(BaseModel):
    detail: str
