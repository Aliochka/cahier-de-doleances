"""First read-only versioned public API, sharing the HTML form queries."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path
from sqlalchemy.engine import RowMapping

from app.db import SessionLocal
from app.helpers import slugify
from app.schemas.forms import ApiError, FormDetail, FormQuestion, FormSummary
from app.services.forms import form_questions, get_form, list_forms

router = APIRouter(
    prefix="/api/v1/forms",
    tags=["Public forms"],
    responses={
        500: {"model": ApiError, "description": "Erreur inattendue, sans détails internes."},
        503: {"model": ApiError, "description": "Base de données indisponible."},
        408: {"model": ApiError, "description": "Délai HTTP dépassé."},
    },
)


def summary(row: RowMapping) -> FormSummary:
    return FormSummary(
        id=str(row["id"]),
        name=row["name"],
        questions_count=row["questions_count"],
        url=f"/forms/{row['id']}",
    )


@router.get(
    "",
    response_model=list[FormSummary],
    operation_id="list_public_forms",
    summary="Lister les formulaires historiques",
)
def forms_list() -> list[FormSummary]:
    """Ordre stable par identifiant. Une liste vide reste une réponse 200."""
    with SessionLocal() as db:
        return [summary(row) for row in list_forms(db)]


@router.get(
    "/{form_id}",
    response_model=FormDetail,
    operation_id="get_public_form",
    summary="Consulter un formulaire et toutes ses questions",
    responses={404: {"model": ApiError, "description": "Formulaire introuvable."}},
)
def forms_detail(
    form_id: Annotated[
        int,
        Path(ge=1, le=9223372036854775807, description="Identifiant BIGINT positif du formulaire."),
    ],
) -> FormDetail:
    with SessionLocal() as db:
        form = get_form(db, form_id)
        if form is None:
            raise HTTPException(404, "Formulaire introuvable")
        questions = []
        for row in form_questions(db, form_id):
            slug = slugify(row["prompt"] or f"question-{row['id']}")
            questions.append(
                FormQuestion(
                    id=str(row["id"]),
                    form_id=str(row["form_id"]),
                    prompt=row["prompt"],
                    type=row["type"],
                    position=row["position"],
                    slug=slug,
                    url=f"/questions/{row['id']}-{slug}",
                )
            )
        return FormDetail(**summary(form).model_dump(), questions=questions)
