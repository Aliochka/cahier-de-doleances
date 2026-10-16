"""First read-only versioned public API, sharing the HTML form queries."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path
from sqlalchemy.engine import RowMapping

from app.choice_stats import choice_statistics_many
from app.db import SessionLocal
from app.helpers import slugify
from app.routers.api_questions import limit_sql, question_fields, statistics_fields
from app.schemas.forms import ApiError, FormDetail, FormQuestion, FormSummary
from app.schemas.questions import FormQuestionStatistics, FormStatistics, PathId, QuestionForm
from app.search_errors import handle_search_errors
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


@router.get(
    "/{form_id}/stats",
    response_model=FormStatistics,
    operation_id="get_public_form_statistics",
    summary="Statistiques groupées des questions à choix du formulaire",
    responses={
        404: {"model": ApiError, "description": "Formulaire introuvable."},
        504: {"model": ApiError, "description": "Délai SQL dépassé ; transaction annulée."},
    },
)
def form_statistics(form_id: PathId) -> FormStatistics:
    """Cinq lectures SQL, zéro requête par question ; dénominateurs et arrondis historiques."""
    with SessionLocal() as db, handle_search_errors(db):
        limit_sql(db)
        form = get_form(db, int(form_id))
        if form is None:
            raise HTTPException(404, "Formulaire introuvable")
        questions = [
            q
            for q in form_questions(db, int(form_id))
            if q["type"] in ("single_choice", "multi_choice")
        ]
        statistics = choice_statistics_many(
            db, [q["id"] for q in questions], include_contributions=True
        )
        return FormStatistics(
            form=QuestionForm(id=str(form["id"]), name=form["name"], url=f"/forms/{form['id']}"),
            questions=[
                FormQuestionStatistics(
                    question=question_fields(q), stats=statistics_fields(q, statistics[q["id"]])
                )
                for q in questions
            ],
        )
