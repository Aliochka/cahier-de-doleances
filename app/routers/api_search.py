"""Expose the historical PostgreSQL searches without HTML snippets or account data."""

import base64
import binascii
import json
import math
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from app.db import SessionLocal
from app.routers.api_contributions import author_fields
from app.routers.api_questions import limit_sql, question_fields
from app.schemas.forms import ApiError
from app.schemas.questions import QuestionForm
from app.schemas.search import (
    AnswerSearchPage,
    CatalogForm,
    CatalogQuestion,
    CatalogSearchPage,
    SearchAnswer,
)
from app.search_errors import handle_search_errors
from app.services.search import PREVIEW_MAXLEN, read_answer_search, read_catalog_search

router = APIRouter(
    prefix="/api/v1/search",
    tags=["Public search"],
    responses={
        408: {"model": ApiError, "description": "Délai HTTP dépassé."},
        500: {"model": ApiError, "description": "Erreur inattendue, sans détails internes."},
        503: {"model": ApiError, "description": "Base indisponible."},
        504: {"model": ApiError, "description": "Délai SQL dépassé ; transaction annulée."},
    },
)
SearchTerm = Annotated[
    str,
    Query(
        max_length=512,
        description="Terme recherché, espaces extérieurs retirés. Maximum 512 caractères.",
    ),
]
PageSize = Annotated[int, Query(ge=1, le=100)]
Cursor = Annotated[
    str | None,
    Query(
        min_length=1,
        max_length=1024,
        description="Curseur opaque renvoyé pour cette section et ce terme ; ne pas décoder côté frontend.",
    ),
]


def validate_cursor(value: str | None, *, scored: bool = False):
    if value is None:
        return
    try:
        raw = base64.b64decode(
            value + "=" * ((4 - len(value) % 4) % 4), altchars=b"-_", validate=True
        )
        cursor = json.loads(raw.decode())
        if not isinstance(cursor, dict) or set(cursor) != ({"id", "score"} if scored else {"id"}):
            raise ValueError()
        if type(cursor["id"]) is not int or not 0 < cursor["id"] <= 9223372036854775807:
            raise ValueError()
        if scored:
            score = cursor["score"]
            if (
                type(score) not in (int, float)
                or not math.isfinite(score)
                or not 0 <= score <= 3.4028234663852886e38
            ):
                raise ValueError()
    except (ValueError, TypeError, OverflowError, UnicodeDecodeError, binascii.Error):
        raise HTTPException(422, "Curseur invalide") from None


def form_fields(row) -> QuestionForm:
    return QuestionForm(
        id=str(row["form_id"]), name=row["form_name"], url=f"/forms/{row['form_id']}"
    )


@router.get(
    "/answers",
    response_model=AnswerSearchPage,
    operation_id="search_public_answers",
    name="api_search_answers",
    summary="Recherche plein texte des réponses, ordre historique ID décroissant",
)
def search_answers(
    q: SearchTerm = "", page_size: PageSize = 20, cursor: Cursor = None
) -> AnswerSearchPage:
    term = q.strip()
    validate_cursor(cursor)
    if len(term) < 2:
        return AnswerSearchPage(
            q=term, items=[], page_size=page_size, has_next=False, next_cursor=None
        )
    with SessionLocal() as db, handle_search_errors(db):
        rows, has_next, next_cursor = read_answer_search(
            db, term, cursor, page_size=page_size, public_context=True, max_text_len=PREVIEW_MAXLEN
        )
        items = []
        for row in rows:
            question = question_fields(
                {
                    "id": row["question_id"],
                    "form_id": row["form_id"],
                    "prompt": row["question_prompt"],
                    "type": row["question_type"],
                    "position": row["question_position"],
                }
            )
            author = (
                author_fields(
                    {
                        "id": row["author_id"],
                        "name": row["author_name"],
                        "is_anonymous": row["author_is_anonymous"],
                    }
                )
                if row["author_id"] is not None
                else None
            )
            if author is not None:
                author = author.model_copy(update={"url": f"/authors/{author.id}"})
            value = row["answer_text"] or ""
            items.append(
                SearchAnswer(
                    id=str(row["answer_id"]),
                    contribution_id=str(row["contribution_id"]),
                    text=value[:PREVIEW_MAXLEN],
                    is_truncated=row["is_truncated"] or len(value) > PREVIEW_MAXLEN,
                    submitted_at=row["submitted_at"],
                    author=author,
                    question=question,
                    form=form_fields(row),
                    url=f"/forms/{row['form_id']}/contributions/{row['contribution_id']}#answer-{row['answer_id']}",
                )
            )
        return AnswerSearchPage(
            q=term, items=items, page_size=page_size, has_next=has_next, next_cursor=next_cursor
        )


@router.get(
    "/catalog",
    response_model=CatalogSearchPage,
    operation_id="search_public_catalog",
    name="api_search_catalog",
    summary="Questions et formulaires, sections indépendantes classées par ts_rank puis ID",
)
def search_catalog(
    q: SearchTerm = "",
    page_size: PageSize = 20,
    cursor_forms: Cursor = None,
    cursor_questions: Cursor = None,
    section: Annotated[
        Literal["forms", "questions"] | None,
        Query(
            description="Omettre pour les deux sections ; une section limite la recherche et le SQL à celle-ci."
        ),
    ] = None,
) -> CatalogSearchPage:
    term = q.strip()
    validate_cursor(cursor_forms, scored=True)
    validate_cursor(cursor_questions, scored=True)
    if not term:
        return CatalogSearchPage(
            q=term,
            forms=[],
            questions=[],
            page_size=page_size,
            has_next_forms=False,
            has_next_questions=False,
            next_cursor_forms=None,
            next_cursor_questions=None,
        )
    with SessionLocal() as db, handle_search_errors(db):
        limit_sql(db)
        forms, questions, has_forms, has_questions, next_forms, next_questions = (
            read_catalog_search(
                db, term, cursor_forms, cursor_questions, section=section, page_size=page_size
            )
        )
        return CatalogSearchPage(
            q=term,
            forms=[
                CatalogForm(
                    id=str(row["id"]),
                    name=row["name"],
                    questions_count=row["questions_count"],
                    url=f"/forms/{row['id']}",
                )
                for row in forms
            ],
            questions=[
                CatalogQuestion(
                    **question_fields(row).model_dump(),
                    form=form_fields(row),
                    answers_count=row["answers_count"],
                )
                for row in questions
            ],
            page_size=page_size,
            has_next_forms=has_forms,
            has_next_questions=has_questions,
            next_cursor_forms=next_forms,
            next_cursor_questions=next_questions,
        )
