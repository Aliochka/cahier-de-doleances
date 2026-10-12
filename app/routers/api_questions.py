"""Public versioned reads, using the historical keyset and statistics services."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text

from app.choice_stats import choice_statistics
from app.db import SessionLocal
from app.helpers import public_author, slugify
from app.schemas.forms import ApiError, FormQuestion
from app.schemas.questions import (
    AnswerDetail,
    AnswerPage,
    ChoiceCategory,
    PathId,
    PublicAnswer,
    PublicAuthor,
    QuestionDetail,
    QuestionForm,
    QuestionStatistics,
)
from app.search_errors import handle_search_errors
from app.services.answers import get_answer
from app.services.questions import MAX_TEXT_LEN, _dec_cursor, get_question, read_question_answers

router = APIRouter(
    prefix="/api/v1",
    tags=["Public questions and answers"],
    responses={
        404: {"model": ApiError, "description": "Ressource introuvable."},
        408: {"model": ApiError, "description": "Délai HTTP dépassé."},
        500: {"model": ApiError, "description": "Erreur inattendue, sans détails internes."},
        503: {"model": ApiError, "description": "Base indisponible."},
        504: {"model": ApiError, "description": "Délai SQL dépassé ; transaction annulée."},
    },
)


def question_fields(row) -> FormQuestion:
    slug = slugify(row["prompt"] or f"question-{row['id']}")
    return FormQuestion(
        id=str(row["id"]),
        form_id=str(row["form_id"]),
        prompt=row["prompt"],
        type=row["type"],
        position=row["position"],
        slug=slug,
        url=f"/questions/{row['id']}-{slug}",
    )


def answer_fields(row, question_id: int, *, truncate: bool) -> PublicAnswer:
    author = None
    if row["author_id"] is not None:
        projection = public_author(row["author_id"], row["author_name"], row["author_is_anonymous"])
        author = PublicAuthor(
            id=str(projection["id"]),
            name=projection["name"],
            slug=projection["slug"],
            is_anonymous=projection["is_anonymous"],
            url=f"/authors/{projection['id']}-{projection['slug']}",
        )
    value = row["answer_text"] or ""
    return PublicAnswer(
        id=str(row["answer_id"]),
        question_id=str(question_id),
        contribution_id=str(row["contribution_id"]),
        text=value[:MAX_TEXT_LEN] if truncate else value,
        is_truncated=truncate and len(value) > MAX_TEXT_LEN,
        submitted_at=row["submitted_at"],
        author=author,
        url=f"/answers/{row['answer_id']}",
    )


def existing_question(db, question_id: int):
    row = get_question(db, question_id)
    if row is None:
        raise HTTPException(404, "Question introuvable")
    return row


def limit_sql(db):
    # Same local deadline and rollback mechanism as API-003's costly searches.
    db.execute(text("SET LOCAL statement_timeout = '5000'"))


@router.get(
    "/questions/{question_id}",
    response_model=QuestionDetail,
    operation_id="get_public_question",
    name="api_question_detail",
    summary="Consulter une question sans ses réponses",
)
def question_detail(question_id: PathId) -> QuestionDetail:
    with SessionLocal() as db, handle_search_errors(db):
        limit_sql(db)
        row = existing_question(db, int(question_id))
        return QuestionDetail(
            **question_fields(row).model_dump(),
            form=QuestionForm(
                id=str(row["form_id"]), name=row["form_name"], url=f"/forms/{row['form_id']}"
            ),
            display_mode="choice" if row["type"] in ("single_choice", "multi_choice") else "text",
        )


@router.get(
    "/questions/{question_id}/answers",
    response_model=AnswerPage,
    operation_id="list_public_question_answers",
    name="api_question_answers",
    summary="Parcourir les réponses textuelles par curseur",
)
def question_answers(
    question_id: PathId,
    page_size: Annotated[int, Query(ge=1, le=100, description="20 par défaut, maximum 100.")] = 20,
    cursor: Annotated[
        str | None,
        Query(min_length=1, max_length=1024, description="Curseur opaque de la page précédente."),
    ] = None,
) -> AnswerPage:
    """Date DESC NULLS FIRST, id DESC ; une sentinelle, sans OFFSET ni comptage.

    Filtre historique : texte non vide pour choix, au moins 60 caractères nettoyés
    pour les autres types. Texte de liste limité à 20 000 caractères.
    """
    try:
        _dec_cursor(cursor)
    except HTTPException:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "cursor"),
                    "msg": "Curseur invalide",
                    "input": cursor,
                }
            ]
        ) from None
    with SessionLocal() as db, handle_search_errors(db):
        limit_sql(db)
        row = existing_question(db, int(question_id))
        rows, has_next, next_cursor, _ = read_question_answers(
            db,
            row["id"],
            row["type"],
            None,
            cursor,
            page_size=page_size,
            include_total=False,
        )
        return AnswerPage(
            question_id=str(row["id"]),
            items=[answer_fields(r, row["id"], truncate=True) for r in rows],
            page_size=page_size,
            has_next=has_next,
            next_cursor=next_cursor,
        )


@router.get(
    "/questions/{question_id}/stats",
    response_model=QuestionStatistics,
    operation_id="get_public_question_statistics",
    name="api_question_statistics",
    summary="Statistiques des choix, sans paramètres graphiques",
    responses={400: {"model": ApiError, "description": "Question non à choix."}},
)
def question_statistics(question_id: PathId) -> QuestionStatistics:
    """Pourcentages historiques par ligne de réponse ; leur somme peut dépasser 100 %.

    Contributions distinctes ≠ personnes uniques. Une réponse avec autre texte
    compte une fois dans la catégorie synthétique, pas une fois par texte.
    """
    with SessionLocal() as db, handle_search_errors(db):
        limit_sql(db)
        row = existing_question(db, int(question_id))
        if row["type"] not in ("single_choice", "multi_choice"):
            raise HTTPException(400, "Cette question n'est pas à choix")
        result = choice_statistics(db, row["id"], include_contributions=True)
        return QuestionStatistics(
            question_id=str(row["id"]),
            type=row["type"],
            total_answers=result["total_answers"],
            answered_contributions_count=result["answered_contributions_count"],
            total_selections=result["total_selections"],
            total_option_selections=result["total_selections"] - result["other_text_answers_count"],
            other_text_answers_count=result["other_text_answers_count"],
            categories=[
                ChoiceCategory(
                    option_id=str(r["option_id"]) if r["option_id"] else None,
                    kind="option" if r["option_id"] else "other_text",
                    label=r["label"],
                    position=r["position"],
                    count=r["count"],
                    percentage=r["percentage"],
                )
                for r in result["stats"]
            ],
        )


@router.get(
    "/answers/{answer_id}",
    response_model=AnswerDetail,
    operation_id="get_public_answer",
    name="api_answer_detail",
    summary="Consulter une réponse complète et sa question",
)
def answer_detail(answer_id: PathId) -> AnswerDetail:
    with SessionLocal() as db, handle_search_errors(db):
        limit_sql(db)
        row = get_answer(db, int(answer_id))
        if row is None:
            raise HTTPException(404, "Réponse introuvable")
        question = question_fields(
            {
                "id": row["question_id"],
                "form_id": row["form_id"],
                "prompt": row["question_prompt"],
                "type": row["question_type"],
                "position": row["question_position"],
            }
        )
        return AnswerDetail(
            **answer_fields(row, row["question_id"], truncate=False).model_dump(), question=question
        )
