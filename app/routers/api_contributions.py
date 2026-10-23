"""Public authors and complete contributions, separate from historical ordinal URLs."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.db import SessionLocal
from app.helpers import public_author
from app.routers.api_questions import limit_sql, question_fields
from app.schemas.contributions import (
    AuthorForm,
    AuthorFormsPage,
    ContributionAnswer,
    ContributionDetail,
    ContributionReference,
    SelectedOption,
)
from app.schemas.forms import ApiError
from app.schemas.questions import PathId, PublicAuthor, QueryId, QuestionForm
from app.search_errors import handle_search_errors
from app.services.authors import author_contributions, get_author
from app.services.contributions import (
    contribution_answers,
    contribution_neighbors,
    contribution_options,
    get_contribution,
    public_values,
    select_legacy_contribution,
)
from app.services.forms import get_form

router = APIRouter(
    prefix="/api/v1",
    tags=["Public authors and contributions"],
    responses={
        404: {
            "model": ApiError,
            "description": "Ressource introuvable ou contribution d'un autre formulaire.",
        },
        408: {"model": ApiError, "description": "Délai HTTP dépassé."},
        500: {"model": ApiError, "description": "Erreur inattendue, sans détails internes."},
        503: {"model": ApiError, "description": "Base indisponible."},
        504: {"model": ApiError, "description": "Délai SQL dépassé ; transaction annulée."},
    },
)


def author_fields(row) -> PublicAuthor:
    author = public_author(row["id"], row["name"], row["is_anonymous"])
    return PublicAuthor(
        **{**author, "id": str(author["id"])},
        url=f"/authors/{author['id']}-{author['slug']}",
    )


def existing_author(db, author_id: str):
    row = get_author(db, int(author_id))
    if row is None:
        raise HTTPException(404, "Auteur introuvable")
    return row


def reference(row) -> ContributionReference:
    return ContributionReference(
        id=str(row["id"]),
        submitted_at=row["submitted_at"],
        api_url=f"/api/v1/forms/{row['form_id']}/contributions/{row['id']}",
    )


@router.get(
    "/authors/{author_id}",
    response_model=PublicAuthor,
    operation_id="get_public_author",
    name="api_author_detail",
    summary="Consulter la représentation publique d'un auteur",
)
def author_detail(author_id: PathId) -> PublicAuthor:
    with SessionLocal() as db, handle_search_errors(db):
        limit_sql(db)
        return author_fields(existing_author(db, author_id))


@router.get(
    "/authors/{author_id}/forms",
    response_model=AuthorFormsPage,
    operation_id="list_public_author_forms",
    name="api_author_forms",
    summary="Formulaires regroupés dans un lot borné de contributions d'un auteur",
)
def author_forms(
    author_id: PathId,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    after_id: QueryId | None = None,
) -> AuthorFormsPage:
    with SessionLocal() as db, handle_search_errors(db):
        limit_sql(db)
        existing_author(db, author_id)
        rows = author_contributions(
            db, int(author_id), int(after_id) if after_id else 0, page_size + 1
        )
        has_next = len(rows) > page_size
        rows = rows[:page_size]
        forms: dict[int, AuthorForm] = {}
        for row in rows:
            fid = row["form_id"]
            if fid not in forms:
                forms[fid] = AuthorForm(
                    id=str(fid), name=row["form_name"], url=f"/forms/{fid}", contributions=[]
                )
            forms[fid].contributions.append(reference(row))
        return AuthorFormsPage(
            author_id=author_id,
            forms=list(forms.values()),
            page_size=page_size,
            has_next=has_next,
            next_after_id=str(rows[-1]["id"]) if has_next else None,
        )


def read_complete(
    db, form_id: int, contribution_id: int, legacy_index: int | None = None
) -> ContributionDetail:
    row = get_contribution(db, form_id, contribution_id)
    if row is None:
        raise HTTPException(404, "Contribution introuvable dans ce formulaire")
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
    options: dict[int, list[SelectedOption]] = {}
    for option in contribution_options(db, form_id, contribution_id):
        options.setdefault(option["answer_id"], []).append(
            SelectedOption(id=str(option["id"]), label=option["label"], position=option["position"])
        )
    answers = []
    for answer in contribution_answers(db, contribution_id, form_id):
        other, value = public_values(answer["value_json"], answer["type"])
        question = question_fields({**answer, "id": answer["question_id"]})
        answers.append(
            ContributionAnswer(
                id=str(answer["id"]),
                position=answer["answer_position"],
                question=question,
                text=answer["text"],
                selected_options=options.get(answer["id"], []),
                other_text=other,
                value=value,
            )
        )
    neighbors = contribution_neighbors(db, form_id, contribution_id, row["submitted_at"])
    return ContributionDetail(
        form=QuestionForm(id=str(form_id), name=row["form_name"], url=f"/forms/{form_id}"),
        contribution=reference(row),
        author=author,
        legacy_index=str(legacy_index) if legacy_index is not None else None,
        previous_id=str(neighbors["previous_id"]) if neighbors["previous_id"] is not None else None,
        next_id=str(neighbors["next_id"]) if neighbors["next_id"] is not None else None,
        answers=answers,
    )


@router.get(
    "/forms/{form_id}/contributions/{contribution_id}",
    response_model=ContributionDetail,
    operation_id="get_public_contribution",
    name="api_contribution_detail",
    summary="Consulter toutes les réponses d'une contribution par son ID en base",
)
def contribution_detail(form_id: PathId, contribution_id: PathId) -> ContributionDetail:
    with SessionLocal() as db, handle_search_errors(db):
        limit_sql(db)
        return read_complete(db, int(form_id), int(contribution_id))


@router.get(
    "/forms/{form_id}/contributions",
    response_model=ContributionDetail,
    operation_id="get_public_legacy_contribution",
    name="api_legacy_contribution",
    summary="Résoudre le paramètre historique contrib (rang, jamais ID en base)",
)
def legacy_contribution(
    form_id: PathId,
    contrib: Annotated[
        str,
        Query(
            max_length=19,
            description="Rang 1..M selon date ASC NULLS LAST, ID ASC. Invalide ou hors plage : repli/clamp historique.",
        ),
    ] = "1",
) -> ContributionDetail:
    with SessionLocal() as db, handle_search_errors(db):
        limit_sql(db)
        if get_form(db, int(form_id)) is None:
            raise HTTPException(404, "Formulaire introuvable")
        _, index, cid = select_legacy_contribution(db, int(form_id), contrib)
        if cid is None:
            raise HTTPException(404, "Aucune contribution dans ce formulaire")
        return read_complete(db, int(form_id), cid, index)
